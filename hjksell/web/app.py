"""FastAPI boundary for the isolated HJKsell web development skeleton."""

from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Annotated

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from ..config import AppPaths
from ..database.connection import initialize_database
from ..repositories.item_repository import ItemRepository
from ..repositories.portfolio_repository import PortfolioRepository
from ..repositories.settings_repository import SettingsRepository
from ..repositories.telegram_repository import TelegramRepository
from ..services.finance import parse_decimal
from ..services.items import ItemService
from ..services.photos import PhotoService
from ..services.portfolios import PortfolioService
from ..services.telegram import TelegramApiClient, _safe_error
from .catalog import CatalogQueryService, decimal_text
from .config import web_dev_paths
from .schemas import (
    CatalogFilter,
    ExchangeRateUpdate,
    ItemCreate,
    ItemUpdate,
    MonthlyValuesUpdate,
    PortfolioRename,
    SaleUpdate,
    SaleDateUpdate,
    TelegramConfigUpdate,
    TelegramTokenCheck,
)
from .telegram import WebTelegramManager

ALLOWED_IMAGE_TYPES = {
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
    ".webp": {"image/webp"},
    ".gif": {"image/gif"},
    ".bmp": {"image/bmp"},
}
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


def create_app(paths: AppPaths | None = None) -> FastAPI:
    resolved_paths = paths or web_dev_paths()
    engine, session_factory = initialize_database(resolved_paths)
    static_root = Path(__file__).with_name("static")

    telegram_manager = WebTelegramManager(session_factory, resolved_paths)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        telegram_manager.start()
        try:
            yield
        finally:
            telegram_manager.stop()

    app = FastAPI(title="HJKsell Web Skeleton", version="0.1.0", lifespan=lifespan)
    app.state.paths = resolved_paths
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.telegram_manager = telegram_manager

    def session_dependency():
        with session_factory() as session:
            yield session

    SessionDependency = Annotated[Session, Depends(session_dependency)]

    def portfolio_or_404(session: Session, portfolio_id: int):
        portfolio = PortfolioRepository(session).get(portfolio_id)
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
        return {"status": "ok", "data_scope": "isolated-web-development"}

    @app.get("/api/portfolios")
    def portfolios(session: SessionDependency) -> list[dict]:
        return [{"id": portfolio.id, "name": portfolio.name} for portfolio in PortfolioRepository(session).list_all()]

    @app.put("/api/portfolios/{portfolio_id}")
    def rename_portfolio(portfolio_id: int, payload: PortfolioRename, session: SessionDependency) -> dict:
        portfolio = portfolio_or_404(session, portfolio_id)
        try:
            renamed = PortfolioService(PortfolioRepository(session)).rename(portfolio, payload.name)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        session.commit()
        return {"id": renamed.id, "name": renamed.name}

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

    @app.put("/api/settings/exchange-rate")
    def update_exchange_rate(payload: ExchangeRateUpdate, session: SessionDependency) -> dict:
        try:
            value = parse_decimal(payload.rate, field_name="курс", positive=True)
            saved = SettingsRepository(session).set_exchange_rate(value)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        session.commit()
        return {"exchange_rate": decimal_text(saved, "0.0001")}

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
        stored = PhotoService(resolved_paths).save_photo_bytes(content, suffix)
        ItemRepository(session).replace_photo(item, stored)
        session.commit()
        return CatalogQueryService(session, resolved_paths.photos).item(item)

    @app.get("/api/dev-media/{filename}")
    def development_media(filename: str) -> FileResponse:
        if Path(filename).name != filename or Path(filename).suffix.lower() not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=404, detail="Изображение не найдено.")
        media_root = resolved_paths.photos.resolve()
        target = (media_root / filename).resolve()
        if target.parent != media_root or not target.is_file():
            raise HTTPException(status_code=404, detail="Изображение не найдено.")
        return FileResponse(target)

    app.mount("/", StaticFiles(directory=static_root, html=True), name="web")
    return app
