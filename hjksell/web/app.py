"""FastAPI boundary for the isolated HJKsell web development skeleton."""

from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
import mimetypes
import os
from pathlib import Path
from typing import Annotated

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import AppPaths
from ..database.connection import initialize_database
from ..database.models import Item, Portfolio
from ..repositories.item_repository import ItemRepository
from ..repositories.portfolio_repository import PortfolioRepository
from ..repositories.settings_repository import PURCHASE_CURRENCIES, SettingsRepository
from ..repositories.telegram_repository import TelegramRepository
from ..services.analytics import AnalyticsService, PeriodPreset
from ..services.finance import parse_decimal
from ..services.exchange_rates import OfficialExchangeRateService
from ..services.items import ItemService
from ..services.photos import PhotoService
from ..services.portfolios import PortfolioService
from ..services.telegram import TelegramApiClient, _safe_error
from .catalog import CatalogQueryService, decimal_text
from .config import web_dev_paths, web_production_paths
from .schemas import (
    AutomaticExpenseUpdate,
    CatalogFilter,
    CurrencySettingsUpdate,
    ExchangeRateUpdate,
    ItemCreate,
    ItemUpdate,
    MonthlyValuesUpdate,
    PortfolioCreate,
    PortfolioRename,
    SaleUpdate,
    SaleDateUpdate,
    TelegramConfigUpdate,
    TelegramTokenCheck,
)
from .telegram import WebTelegramManager
from .telegram_auth import authenticate_request, issue_session_cookie

ALLOWED_IMAGE_TYPES = {
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
    ".webp": {"image/webp"},
    ".gif": {"image/gif"},
    ".bmp": {"image/bmp"},
}

# Windows does not always register font MIME types. StaticFiles needs this
# mapping so browser font loading stays reliable on a clean local machine.
mimetypes.add_type("font/ttf", ".ttf")
MAX_IMAGE_BYTES = 5 * 1024 * 1024


def image_signature_matches(content: bytes, suffix: str) -> bool:
    signatures = {
        ".jpg": content.startswith(b"\xff\xd8\xff"),
        ".jpeg": content.startswith(b"\xff\xd8\xff"),
        ".png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        ".gif": content.startswith((b"GIF87a", b"GIF89a")),
        ".bmp": content.startswith(b"BM"),
        ".webp": content.startswith(b"RIFF") and content[8:12] == b"WEBP",
    }
    return signatures.get(suffix, False)


def create_app(paths: AppPaths | None = None, *, public_mode: bool | None = None) -> FastAPI:
    if public_mode is None:
        public_mode = os.environ.get("HJKSELL_ENV", "development").strip().casefold() == "production"
    bot_token = os.environ.get("HJKSELL_MINI_APP_BOT_TOKEN", "").strip() if public_mode else ""
    if public_mode and not bot_token:
        raise RuntimeError("Для production задайте HJKSELL_MINI_APP_BOT_TOKEN через секреты хостинга.")
    token_cipher = None
    if public_mode:
        encryption_key = os.environ.get("HJKSELL_TOKEN_ENCRYPTION_KEY", "").strip()
        if not encryption_key:
            raise RuntimeError("Для production задайте HJKSELL_TOKEN_ENCRYPTION_KEY через секреты хостинга.")
        from .token_crypto import TelegramTokenCipher

        token_cipher = TelegramTokenCipher(encryption_key)
    resolved_paths = paths or (web_production_paths() if public_mode else web_dev_paths())
    engine, session_factory = initialize_database(
        resolved_paths,
        seed_default_portfolios=not public_mode,
        session_info={} if token_cipher is None else {"telegram_token_cipher": token_cipher},
    )
    if public_mode:
        with session_factory() as session:
            has_unowned_portfolios = session.scalar(
                select(Portfolio.id).where(Portfolio.owner_telegram_id.is_(None)).limit(1)
            ) is not None
        if has_unowned_portfolios:
            engine.dispose()
            raise RuntimeError(
                "Публичный режим остановлен: в постоянной базе найдены портфели без Telegram-владельца. "
                "Используйте отдельное пустое хранилище; не подключайте локальную базу HJKsell."
            )
    static_root = Path(__file__).with_name("static")
    font_root = Path(__file__).parents[2] / "assets" / "fonts"

    telegram_manager = WebTelegramManager(session_factory, resolved_paths)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        telegram_manager.start()
        try:
            yield
        finally:
            telegram_manager.stop()

    app = FastAPI(
        title="HJKsell",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if public_mode else "/docs",
        redoc_url=None if public_mode else "/redoc",
        openapi_url=None if public_mode else "/openapi.json",
    )
    app.state.paths = resolved_paths
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.telegram_manager = telegram_manager
    app.state.public_mode = public_mode

    @app.middleware("http")
    async def disable_cache_for_web_shell(request: Request, call_next):
        requires_telegram_auth = (
            public_mode
            and request.url.path.startswith("/api/")
            and request.url.path != "/api/health"
        )
        if requires_telegram_auth:
            init_data = request.headers.get("X-Telegram-Init-Data")
            user_id, fresh_init_data = authenticate_request(
                init_data,
                request.cookies.get("hjksell_session", ""),
                bot_token,
            )
            if user_id is None:
                response = JSONResponse(
                    status_code=401,
                    content={"detail": "Откройте HJKsell из Telegram."},
                )
                response.headers["Cache-Control"] = "private, no-store"
                response.headers["Vary"] = "Cookie, X-Telegram-Init-Data"
                return response
            request.state.telegram_user_id = user_id
            request.state.fresh_telegram_init_data = fresh_init_data
        response = await call_next(request)
        if requires_telegram_auth:
            response.headers["Cache-Control"] = "private, no-store"
            response.headers["Vary"] = "Cookie, X-Telegram-Init-Data"
            if request.state.fresh_telegram_init_data:
                response.set_cookie(
                    "hjksell_session",
                    issue_session_cookie(request.state.telegram_user_id, bot_token),
                    max_age=43_200,
                    httponly=True,
                    secure=True,
                    samesite="lax",
                    path="/",
                )
        if request.url.path in {"/", "/index.html", "/styles.css", "/app.js"}:
            response.headers["Cache-Control"] = "no-store"
        return response

    def session_dependency(request: Request):
        with session_factory() as session:
            session.info["telegram_user_id"] = getattr(request.state, "telegram_user_id", None)
            yield session

    SessionDependency = Annotated[Session, Depends(session_dependency)]

    def portfolio_or_404(session: Session, portfolio_id: int):
        owner_id = session.info.get("telegram_user_id")
        repository = PortfolioRepository(session)
        portfolio = (
            repository.get_for_owner(portfolio_id, owner_id)
            if owner_id is not None
            else repository.get(portfolio_id)
        )
        if portfolio is None:
            raise HTTPException(status_code=404, detail="Портфель не найден.")
        return portfolio

    def item_or_404(session: Session, portfolio_id: int, item_id: int):
        portfolio_or_404(session, portfolio_id)
        item = ItemRepository(session).get(item_id, portfolio_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Вещь не найдена в этом портфеле.")
        return item

    @app.get("/api/health")
    def health() -> dict:
        return {
            "status": "ok",
            "data_scope": "telegram-user" if public_mode else "isolated-web-development",
            "data_deletion_enabled": public_mode,
        }

    @app.get("/api/portfolios")
    def portfolios(session: SessionDependency) -> list[dict]:
        repository = PortfolioRepository(session)
        owner_id = session.info.get("telegram_user_id")
        if owner_id is None:
            owned = repository.list_all()
        else:
            owned = repository.list_for_owner(owner_id)
            if not owned:
                owned = [PortfolioService(repository).create("Мой портфель", owner_id)]
                session.commit()
        return [{"id": portfolio.id, "name": portfolio.name} for portfolio in owned]

    @app.post("/api/portfolios", status_code=201)
    def create_portfolio(payload: PortfolioCreate, session: SessionDependency) -> dict:
        try:
            portfolio = PortfolioService(PortfolioRepository(session)).create(
                payload.name, session.info.get("telegram_user_id")
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        session.commit()
        return {"id": portfolio.id, "name": portfolio.name}

    @app.put("/api/portfolios/{portfolio_id}")
    def rename_portfolio(portfolio_id: int, payload: PortfolioRename, session: SessionDependency) -> dict:
        portfolio = portfolio_or_404(session, portfolio_id)
        try:
            renamed = PortfolioService(PortfolioRepository(session)).rename(portfolio, payload.name)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        session.commit()
        return {"id": renamed.id, "name": renamed.name}

    @app.delete("/api/portfolios/{portfolio_id}")
    def delete_portfolio(portfolio_id: int, session: SessionDependency) -> dict:
        repository = PortfolioRepository(session)
        portfolio = portfolio_or_404(session, portfolio_id)
        owner_id = session.info.get("telegram_user_id")
        portfolios_for_owner = (
            PortfolioRepository(session).list_all()
            if owner_id is None
            else PortfolioRepository(session).list_for_owner(owner_id)
        )
        minimum_portfolios = 2 if owner_id is None else 1
        if len(portfolios_for_owner) <= minimum_portfolios:
            minimum_label = "два портфеля" if owner_id is None else "единственный портфель"
            raise HTTPException(status_code=422, detail=f"Нельзя удалить {minimum_label}.")
        telegram_manager.remove(portfolio_id)
        deleted_id = portfolio.id
        deleted_name = portfolio.name
        photo_paths = repository.photo_paths_for_portfolio(portfolio_id)
        repository.delete(portfolio)
        session.commit()
        try:
            PhotoService(resolved_paths).delete_photo_paths(photo_paths)
        except (OSError, RuntimeError, ValueError) as exc:
            raise HTTPException(
                status_code=500,
                detail="Портфель удалён, но не удалось полностью очистить фотографии. Обратитесь к администратору сервера.",
            ) from exc
        return {"id": deleted_id, "name": deleted_name}

    @app.delete("/api/me/data")
    def delete_my_data(session: SessionDependency) -> dict:
        owner_id = session.info.get("telegram_user_id")
        if not public_mode or owner_id is None:
            raise HTTPException(status_code=404, detail="Маршрут не найден.")

        repository = PortfolioRepository(session)
        portfolio_ids = [portfolio.id for portfolio in repository.list_for_owner(owner_id)]
        for portfolio_id in portfolio_ids:
            telegram_manager.remove(portfolio_id)
        try:
            photo_paths = repository.delete_all_for_owner(owner_id)
            session.commit()
        except Exception:
            session.rollback()
            for portfolio_id in portfolio_ids:
                telegram_manager.reconfigure(portfolio_id)
            raise

        try:
            deleted_photos = PhotoService(resolved_paths).delete_photo_paths(photo_paths)
        except (OSError, RuntimeError, ValueError) as exc:
            raise HTTPException(
                status_code=500,
                detail="Записи удалены, но не удалось полностью очистить фотографии. Обратитесь к администратору сервера.",
            ) from exc
        return {"deleted": True, "deleted_portfolios": len(portfolio_ids), "deleted_photos": deleted_photos}

    @app.get("/api/telegram/status")
    def telegram_status(portfolio_id: int, session: SessionDependency) -> dict:
        portfolio_or_404(session, portfolio_id)
        return telegram_manager.status(portfolio_id)

    @app.post("/api/telegram/validate")
    def validate_telegram_token(payload: TelegramTokenCheck) -> dict:
        client: TelegramApiClient | None = None
        try:
            client = TelegramApiClient(payload.token)
            bot = client.validate_token()
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=_safe_error(exc)) from exc
        finally:
            if client is not None:
                client.close()
        return {
            "valid": True,
            "username": bot.get("username"),
            "name": bot.get("first_name") or bot.get("username") or "бот",
        }

    @app.put("/api/telegram/config")
    def update_telegram_config(payload: TelegramConfigUpdate, session: SessionDependency) -> dict:
        portfolio_or_404(session, payload.portfolio_id)
        repository = TelegramRepository(session)
        try:
            if payload.token is not None:
                repository.set_token(payload.portfolio_id, payload.token)
            if payload.channel_id is not None and payload.channel_id.strip():
                repository.bind_channel(payload.portfolio_id, payload.channel_id)
            session.commit()
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        telegram_manager.reconfigure(payload.portfolio_id)
        return telegram_manager.status(payload.portfolio_id)

    @app.delete("/api/telegram/config")
    def clear_telegram_config(portfolio_id: int, session: SessionDependency) -> dict:
        portfolio_or_404(session, portfolio_id)
        TelegramRepository(session).clear_config(portfolio_id)
        session.commit()
        telegram_manager.reconfigure(portfolio_id)
        return telegram_manager.status(portfolio_id)

    @app.get("/api/catalog")
    def catalog(
        session: SessionDependency,
        portfolio_id: int,
        filter: CatalogFilter = "all",
        year: int | None = None,
        month: int | None = Query(default=None, ge=1, le=12),
    ) -> dict:
        portfolio_or_404(session, portfolio_id)
        if (year is None) != (month is None):
            raise HTTPException(status_code=422, detail="Год и месяц нужно передавать вместе.")
        return CatalogQueryService(session, resolved_paths.photos).catalog(portfolio_id, filter, year, month)

    @app.get("/api/analytics")
    def analytics(
        session: SessionDependency,
        portfolio_id: int,
        period: PeriodPreset = PeriodPreset.CURRENT_MONTH,
    ) -> dict:
        portfolio_or_404(session, portfolio_id)
        report = AnalyticsService(ItemRepository(session)).report(portfolio_id, period)
        metrics = report.metrics
        money_fields = {
            "revenue", "realized_profit", "net_profit", "total_profit", "expenses", "invested",
            "warehouse_value", "average_cost", "average_sale", "average_profit",
        }
        decimal_fields = {
            "roi", "roi_after_expenses", "average_x", "best_x", "worst_x", "average_sale_days",
        }
        count_fields = {"sold_count", "purchased_count", "in_stock_count"}
        serialized = {
            key: (
                getattr(metrics, key)
                if key in count_fields
                else decimal_text(getattr(metrics, key))
            )
            for key in money_fields | decimal_fields | count_fields
        }
        return {
            "portfolio_id": portfolio_id,
            "preset": period.value,
            "period": {
                "start": report.period.start_date.isoformat(),
                "end": report.period.end_date.isoformat(),
            },
            "metrics": serialized,
            "monthly": [
                {
                    "year": entry.year,
                    "month": entry.month,
                    "revenue": decimal_text(entry.revenue),
                    "net_profit": decimal_text(entry.net_profit),
                    "invested": decimal_text(entry.invested),
                }
                for entry in report.monthly
            ],
        }

    @app.put("/api/settings/exchange-rate")
    def update_exchange_rate(payload: ExchangeRateUpdate, session: SessionDependency) -> dict:
        if session.info.get("telegram_user_id") is not None and payload.portfolio_id is None:
            raise HTTPException(status_code=422, detail="Для сохранения курса выберите портфель.")
        if payload.portfolio_id is not None:
            portfolio_or_404(session, payload.portfolio_id)
        try:
            value = parse_decimal(payload.rate, field_name="курс", positive=True)
            saved = SettingsRepository(session).set_exchange_rate(value, payload.portfolio_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        session.commit()
        return {"exchange_rate": decimal_text(saved, "0.0001")}

    @app.get("/api/settings/currencies")
    def currency_settings(portfolio_id: int, session: SessionDependency) -> dict:
        portfolio_or_404(session, portfolio_id)
        profile = SettingsRepository(session).currency_profile(portfolio_id)
        return {
            "portfolio_id": portfolio_id,
            "purchase_currency": profile.purchase_currency,
            "sale_currency": profile.sale_currency,
            "exchange_rate": decimal_text(profile.exchange_rate, "0.0001"),
        }

    @app.put("/api/settings/currencies")
    def update_currency_settings(payload: CurrencySettingsUpdate, session: SessionDependency) -> dict:
        portfolio_or_404(session, payload.portfolio_id)
        try:
            value = parse_decimal(payload.rate, field_name="курс", positive=True)
            settings = SettingsRepository(session)
            current = settings.currency_profile(payload.portfolio_id)
            requested_sale_currency = payload.sale_currency.strip().upper()
            if (
                requested_sale_currency != current.sale_currency
                and ItemRepository(session).has_financial_history(payload.portfolio_id)
            ):
                raise ValueError(
                    "Валюту продажи можно изменить только в пустом портфеле, иначе финансовые итоги смешают разные валюты."
                )
            profile = settings.set_currency_profile(
                payload.portfolio_id,
                payload.purchase_currency,
                payload.sale_currency,
                value,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        session.commit()
        return {
            "portfolio_id": payload.portfolio_id,
            "purchase_currency": profile.purchase_currency,
            "sale_currency": profile.sale_currency,
            "exchange_rate": decimal_text(profile.exchange_rate, "0.0001"),
        }

    @app.get("/api/settings/automatic-expense")
    def automatic_expense_settings(portfolio_id: int, session: SessionDependency) -> dict:
        portfolio_or_404(session, portfolio_id)
        profile = SettingsRepository(session).currency_profile(portfolio_id)
        return {
            "portfolio_id": portfolio_id,
            "amount": decimal_text(profile.automatic_expense_amount),
            "expense_currency": profile.automatic_expense_currency,
            "purchase_currency": profile.purchase_currency,
            "purchase_rate": decimal_text(profile.automatic_expense_purchase_rate, "0.0001"),
        }

    @app.put("/api/settings/automatic-expense")
    def update_automatic_expense(payload: AutomaticExpenseUpdate, session: SessionDependency) -> dict:
        portfolio_or_404(session, payload.portfolio_id)
        try:
            amount = parse_decimal(payload.amount, field_name="автоматический расход", non_negative=True)
            expense_currency = payload.expense_currency.strip().upper()
            if expense_currency not in PURCHASE_CURRENCIES:
                raise ValueError("Валюта автоматического расхода не поддерживается.")
            settings = SettingsRepository(session)
            current = settings.currency_profile(payload.portfolio_id)
            purchase_rate = Decimal("1.0000")
            if amount and expense_currency != current.purchase_currency:
                purchase_rate, _ = OfficialExchangeRateService().latest(
                    expense_currency,
                    current.purchase_currency,
                )
            profile = settings.set_automatic_expense(
                payload.portfolio_id,
                amount,
                expense_currency,
                purchase_rate,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail="Не удалось получить курс для автоматического расхода. Попробуйте сохранить ещё раз.",
            ) from exc
        session.commit()
        return {
            "portfolio_id": payload.portfolio_id,
            "amount": decimal_text(profile.automatic_expense_amount),
            "expense_currency": profile.automatic_expense_currency,
            "purchase_currency": profile.purchase_currency,
            "purchase_rate": decimal_text(profile.automatic_expense_purchase_rate, "0.0001"),
        }

    @app.get("/api/exchange-rates/latest")
    def latest_exchange_rate(purchase_currency: str, sale_currency: str) -> dict:
        try:
            current_rate, effective_date = OfficialExchangeRateService().latest(
                purchase_currency,
                sale_currency,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail="Не удалось получить официальный курс. Введите курс вручную.",
            ) from exc
        return {
            "purchase_currency": purchase_currency.strip().upper(),
            "sale_currency": sale_currency.strip().upper(),
            "exchange_rate": decimal_text(current_rate, "0.0001"),
            "effective_date": effective_date.isoformat(),
            "source": "Национальный банк Республики Беларусь",
        }

    @app.put("/api/monthly-values")
    def update_monthly_values(payload: MonthlyValuesUpdate, session: SessionDependency) -> dict:
        portfolio_or_404(session, payload.portfolio_id)
        if not 1 <= payload.month <= 12:
            raise HTTPException(status_code=422, detail="Некорректный месяц.")
        try:
            expenses = parse_decimal(payload.expenses, field_name="расходы", non_negative=True).quantize(Decimal("0.01"))
            other_income = parse_decimal(
                payload.other_income, field_name="другие доходы", non_negative=True
            ).quantize(Decimal("0.01"))
            advertising = parse_decimal(
                payload.advertising, field_name="рекламу", non_negative=True
            ).quantize(Decimal("0.01"))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        repository = ItemRepository(session)
        repository.set_monthly_expense(payload.portfolio_id, payload.year, payload.month, expenses)
        repository.set_monthly_other_income(payload.portfolio_id, payload.year, payload.month, other_income)
        repository.set_monthly_advertising(payload.portfolio_id, payload.year, payload.month, advertising)
        session.commit()
        return CatalogQueryService(session, resolved_paths.photos).catalog(
            payload.portfolio_id, "all", payload.year, payload.month
        )["months"][0]

    @app.post("/api/items", status_code=201)
    def create_item(payload: ItemCreate, session: SessionDependency) -> dict:
        portfolio_or_404(session, payload.portfolio_id)
        try:
            item = ItemService(ItemRepository(session), SettingsRepository(session)).create_from_text(
                payload.portfolio_id, payload.purchase_price_pln, payload.purchase_date
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        session.commit()
        return CatalogQueryService(session, resolved_paths.photos).item(item)

    @app.put("/api/items/{item_id}")
    def update_item(item_id: int, payload: ItemUpdate, session: SessionDependency) -> dict:
        item = item_or_404(session, payload.portfolio_id, item_id)
        try:
            ItemService(ItemRepository(session), SettingsRepository(session)).update_purchase_details(
                item,
                purchase_price_text=payload.purchase_price_pln,
                purchase_expense_text=payload.purchase_expense,
                purchase_date=payload.purchase_date,
                exchange_rate_text=payload.exchange_rate,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        session.commit()
        return CatalogQueryService(session, resolved_paths.photos).item(item)

    @app.put("/api/items/{item_id}/sale")
    def update_sale(item_id: int, payload: SaleUpdate, session: SessionDependency) -> dict:
        item = item_or_404(session, payload.portfolio_id, item_id)
        try:
            ItemService(ItemRepository(session), SettingsRepository(session)).sell(
                item, payload.sale_price_byn, payload.sale_date or date.today()
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        session.commit()
        return CatalogQueryService(session, resolved_paths.photos).item(item)

    @app.put("/api/items/{item_id}/sale-date")
    def update_sale_date(item_id: int, payload: SaleDateUpdate, session: SessionDependency) -> dict:
        item = item_or_404(session, payload.portfolio_id, item_id)
        try:
            ItemService(ItemRepository(session), SettingsRepository(session)).update_sale_date(item, payload.sale_date)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        session.commit()
        return CatalogQueryService(session, resolved_paths.photos).item(item)

    @app.delete("/api/items/{item_id}")
    def soft_delete_item(item_id: int, portfolio_id: int, session: SessionDependency) -> dict:
        item = item_or_404(session, portfolio_id, item_id)
        ItemRepository(session).soft_delete(item)
        session.commit()
        return {"deleted": True, "item_id": item_id}

    @app.post("/api/items/{item_id}/photo")
    def replace_photo(
        item_id: int,
        portfolio_id: int,
        filename: str,
        session: SessionDependency,
        content_type: Annotated[str | None, Header()] = None,
        content: Annotated[bytes, Body(media_type="application/octet-stream")] = b"",
    ) -> dict:
        item = item_or_404(session, portfolio_id, item_id)
        suffix = Path(filename).suffix.lower()
        if Path(filename).name != filename or suffix not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=422, detail="Некорректное имя или формат изображения.")
        if content_type not in ALLOWED_IMAGE_TYPES[suffix]:
            raise HTTPException(status_code=422, detail="Тип изображения не соответствует расширению.")
        if not content or len(content) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=422, detail="Изображение пустое или превышает 5 MB.")
        if not image_signature_matches(content, suffix):
            raise HTTPException(status_code=422, detail="Содержимое не соответствует формату изображения.")
        previous_photo_path = item.photo_path
        stored = PhotoService(resolved_paths).save_photo_bytes(content, suffix)
        ItemRepository(session).replace_photo(item, stored)
        session.commit()
        if previous_photo_path:
            PhotoService(resolved_paths).delete_photo_paths([previous_photo_path])
        return CatalogQueryService(session, resolved_paths.photos).item(item)

    @app.get("/api/dev-media/{filename}")
    def development_media(filename: str, portfolio_id: int, session: SessionDependency) -> FileResponse:
        if Path(filename).name != filename or Path(filename).suffix.lower() not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=404, detail="Изображение не найдено.")
        portfolio_or_404(session, portfolio_id)
        media_root = resolved_paths.photos.resolve()
        target = (media_root / filename).resolve()
        if target.parent != media_root or not target.is_file():
            raise HTTPException(status_code=404, detail="Изображение не найдено.")
        matching_item = session.scalar(
            select(Item.id).where(
                Item.portfolio_id == portfolio_id,
                Item.photo_path == str(target),
                Item.deleted_at.is_(None),
            ).limit(1)
        )
        if matching_item is None:
            raise HTTPException(status_code=404, detail="Изображение не найдено.")
        return FileResponse(target)

    app.mount("/fonts", StaticFiles(directory=font_root), name="fonts")
    app.mount("/", StaticFiles(directory=static_root, html=True), name="web")
    return app
