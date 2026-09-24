# HJKsell architecture

## Runtime and storage

`run_hjksell.py` is the PyInstaller and development entry point. `hjksell.app.main()` configures logging, initializes SQLite, creates `QApplication`, applies the stylesheet, and shows `MainWindow`.

`get_app_paths()` resolves user data under `%LOCALAPPDATA%\HJKsell`:

- `data/hjk_sell.db`
- `data/photos/`
- `logs/app.log`

The repository itself must not become the user-data directory.

The web application runs independently from the desktop application. Development resolves only under repository-local `.web-dev/`. Public mode is opt-in via `HJKSELL_ENV=production`, requires `HJKSELL_MINI_APP_BOT_TOKEN`, `HJKSELL_TOKEN_ENCRYPTION_KEY`, and an absolute persistent `HJKSELL_DATA_DIR`, and never seeds the local МОЯ/ДРУГА portfolios. Public API requests authenticate with Telegram `initData` or a short-lived signed secure cookie for same-origin photo rendering; a stale initData falls back to a still-valid cookie, but only fresh initData renews it. Protected API JSON and media responses use `Cache-Control: private, no-store` and vary on the authentication cookie and Telegram initData header. Public startup fails closed if the configured database contains a portfolio without a verified Telegram owner. Portfolios are scoped to the validated Telegram user ID. Per-portfolio Telegram import tokens are encrypted at rest in public mode. `WebTelegramManager` owns Web polling through the shared Telegram importer and uses the public data mount in deployment.

In public mode, Settings offers an authenticated erase-all-data action for the current Telegram user. It removes all of that user's portfolio records and referenced photos from live storage; it is not available in local Web development. Encrypted off-site backup snapshots are independent and expire on their configured retention schedule.

## Layers

The Catalog and Analytics windows call services and repositories rather than issuing arbitrary SQL. SQLAlchemy models live in `hjksell/database/models.py`; repositories encapsulate persistence; services contain use cases and Decimal calculations; UI owns Qt presentation and user interaction.

Important modules:

- `hjksell/ui/main_window.py`: Catalog, portfolio tabs, filters, Item rows, sale editing, expenses, Telegram settings/polling ownership.
- `hjksell/ui/analytics_window.py`: separate Analytics window and four approved KPI groups.
- `hjksell/ui/typography.py`: runtime font registration and semantic display, interface, metric, and input roles. All visible roles currently resolve to registered Oswald; Kulag Sha remains registered and packaged for reversible experimentation.
- `hjksell/ui/neon_widgets.py`: lightweight painted Catalog surfaces, including the continuous atmospheric backplate and rounded photo well.
- `hjksell/services/items.py`: Item creation and sale/cancel transitions.
- `hjksell/services/finance.py`: Decimal cost, profit, X, ROI, and parsing.
- `hjksell/services/analytics.py`: period-aware metrics; internal `revenue` naming remains.
- `hjksell/repositories/*`: database access.
- `hjksell/services/telegram.py` and `repositories/telegram_repository.py`: Bot API, import, diagnostics, portfolio-specific state.
- `hjksell/services/photos.py`: local photo copying.
- `hjksell/services/catalog.py`: Catalog filter semantics shared by desktop and web adapters.
- `hjksell/web/app.py`: local FastAPI routes and isolated runtime wiring.
- `hjksell/web/telegram.py`: Web lifecycle orchestration for one cooperative Telegram worker per configured portfolio.
- `hjksell/web/catalog.py`: JSON response assembly over the existing repositories, `AnalyticsService`, and Decimal finance helpers.
- `hjksell/web/static/`: no-build responsive Catalog frontend. It uses locally served Onest and Oswald font assets, while visual state remains a presentation concern separate from the shared service and repository logic.

## Domain flows

### Item creation and sale

Manual creation or Telegram import creates an Item with `portfolio_id`, purchase PLN, current exchange rate snapshot, calculated BYN cost, purchase date, and optional photo path. Later rate changes do not recalculate existing Items.

Sale input is BYN. A positive or zero value completes a sale and records a sale date. Clearing an existing sale field cancels it, clearing sale price/date and returning the Item to stock. Editing an existing non-empty sale keeps its existing sale date. Zero is not treated as unsold.

### Financial semantics

- Web portfolios own an independent default purchase currency, accounting/sale currency, and exchange rate. These defaults apply only when a new Item is created.
- Every Item stores its historical purchase and sale ISO currency codes alongside its historical exchange rate. Existing Items are never relabeled or recalculated when portfolio defaults change.
- The accounting/sale currency cannot change after a portfolio has Item or monthly financial history, preventing totals from mixing different money units. Purchase currency and future rates may still change.
- Optional current-rate lookup uses the official NBRB daily-rate API and derives cross-rates through BYN while respecting each published currency scale.
- An Item can also carry a non-negative `purchase_expense` in its historical purchase currency. Blank editing clears it to zero; historical cost is `(purchase price + purchase expense) x historical exchange rate`.
- Each portfolio can define an optional automatic per-Item expense in Settings. The configured source-currency amount is converted once to the current purchase currency and stored as the new Item's historical `purchase_expense`; existing Items are never changed, and an individual Item expense remains editable from its action menu.
- profit = sale BYN - historical cost BYN;
- X = sale / cost when cost is non-zero;
- ROI = profit / cost × 100% when cost is non-zero;
- zero-price disposal has revenue 0, negative profit, X 0, and ROI -100% when cost is positive.
- Free Items may have zero historical cost; their profit is still calculated, while X and ROI are undefined and displayed as `—`.
- Monthly `other_income_byn` and `advertising_byn` are stored with expenses by `portfolio_id` and calendar month. Detailed Analytics keeps those values separate from item sales, X, and ROI.

Catalog month widgets are purchase cohorts: their sales and sold count cover only Items purchased in that month, even if they sold later. They show both realized Item profit and the monthly cash result, `total_profit = sales + other income + advertising − expenses − all cohort investment`. The widget ROI is `(all cohort investment + total_profit) / all cohort investment`, so 100% means the invested capital was returned without profit. Detailed Analytics still keeps purchase and sale periods independent and reports its existing calendar-period metrics.

### Catalog state

Filters are `ВСЕ`, `В НАЛИЧИИ`, `ПРОДАНО`, and `БЕЗ ВЫРУЧКИ`. They map respectively to all active Items, `sale_price_byn is None`, positive sale price, and sale price zero. Zero-sale status text is `УШЛА НА БЛАГОЕ ДЕЛО`; status amber is intentionally separate from negative financial metric red.

### Portfolios

 Portfolios are independent persisted records; desktop/development initialization seeds two defaults, while public initialization starts empty and creates a first portfolio for each validated Telegram user. `portfolio_id` is identity for Items, expenses, Analytics, Telegram config, channels, offsets, and imports. Public portfolios include `owner_telegram_id`; every API lookup must verify both portfolio ID and authenticated owner. `Portfolio.name` is editable display text and must not be used to rediscover identity or reset renamed portfolios.

### Telegram

Each portfolio has its own token, channel binding, update offset, imports, API client, importer, and polling worker. Posts are one photo plus a numeric PLN caption; accepted forms include comma or dot decimals. Photos are downloaded locally. Polling is automatic at about 50 seconds; desktop also supports a manual poll action. Web settings can validate a token, select a discovered channel, and clear the token, binding, and offset for one portfolio without deleting catalogue Items or import history. Reconfiguration clears old Web diagnostics so a previous unbound-channel message cannot be displayed as the result of a successful binding.

`TelegramQtWorker.diagnostics` is a typed signal carrying portfolio ID and payload, connected directly to a GUI Qt Slot. The Web runtime uses `WebTelegramManager` and the shared thread-friendly `TelegramWorker`; it does not create a second importer or finance implementation. Shutdown is cooperative: stop flags/events, API close/interruption, thread quit, and wait. Never restore a global token, log credentials, insert a Python lambda between worker and GUI, or use `QThread.terminate()` as normal shutdown.

### Database and migrations

The current SQLAlchemy model includes portfolios, items with historical purchase expenses, portfolio currency settings, monthly expenses/income, settings, exchange-rate history, Telegram channels/configs/imports. Alembic migrations are in `alembic/versions/`; `0001` is the initial schema, `0005_portfolio_telegram_configs.py` introduced portfolio-specific Telegram configuration, `0006_monthly_income_fields.py` adds the two monthly income columns, `0007_portfolio_currencies.py` preserves historical Item currency codes and adds portfolio defaults, `0008_item_purchase_expense.py` adds the item-level purchase-currency expense, `0009_portfolio_automatic_expense.py` adds the per-portfolio automatic expense setting, `0010_telegram_portfolio_owners.py` adds Telegram ownership, and `0011_portfolio_scoped_discovered_channels.py` scopes unbound Web channel discoveries to their portfolio. `initialize_database()` can seed desktop/development portfolios or initialize an empty public tenant database.

## Analytics

Desktop Analytics is a separate window; Web Analytics is a dedicated view in the same local application. Both use `AnalyticsService` and the approved groups `РЕЗУЛЬТАТ`, `ЭФФЕКТИВНОСТЬ`, `ЗАКУПКИ И СКЛАД`, and `СРЕДНИЕ ПОКАЗАТЕЛИ`; graph titles include `ПРОДАЖИ ПО МЕСЯЦАМ`, `ЧИСТАЯ ПРИБЫЛЬ ПО МЕСЯЦАМ`, and `ВЛОЖЕНО ПО МЕСЯЦАМ`. Do not duplicate metric formulas in presentation code.

## Packaging

`build.ps1` invokes PyInstaller with `run_hjksell.py`, Alembic data, icon/font assets, and PySide6 collection, producing clean ONEDIR output. Onest remains a packaged fallback; Kulag Sha and official Google Fonts Oswald are also packaged for centralized runtime typography.
