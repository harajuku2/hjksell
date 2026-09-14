# Architecture decisions

## V1 local architecture

**Context:** V1. **Decision:** use a local Windows PySide6 app with SQLite under LocalAppData. **Reason:** no server, cloud, account, or recurring cost. **Do not break:** source and user data remain separate; V2 portability is preserved through repositories/services.

## Layer separation

**Context:** V1. **Decision:** UI → services → repositories → SQLAlchemy/database. **Reason:** storage can later be replaced by an API and UI must not contain arbitrary SQL. **Do not break:** keep financial/use-case logic out of widgets.

## Portfolio identity

**Context:** post-V1 portfolio rename fix. **Decision:** `portfolio_id` is identity; `Portfolio.name` is presentation. **Reason:** users may rename portfolios without moving Items, expenses, Analytics, or Telegram state. **Do not break:** never use display names for lookup or binding.

## Historical exchange rate

**Context:** finance core. **Decision:** snapshot current PLN/BYN rate on Item creation. **Reason:** historical cost must remain stable. **Do not break:** changing the current rate never recalculates old Items.

## Sale state

**Context:** post-V1 sale QoL. **Decision:** nullable sale price distinguishes unsold (`None`) from completed zero-revenue disposal (`Decimal("0")`); no new persisted status was introduced. **Reason:** zero disposals need sale date and financial participation. **Do not break:** never use truthiness for sale state.

## Soft delete

**Context:** V1. **Decision:** Items use `deleted_at`; normal Catalog and statistics exclude deleted rows. **Do not break:** do not replace with destructive delete without product approval.

## Telegram isolation and threading

**Context:** V1 production fixes. **Decision:** token, channel, offset, imports, API/import service, and polling worker are portfolio-specific; diagnostics use a typed Qt signal directly to a GUI Slot; shutdown is cooperative. **Reason:** prevent cross-portfolio state leaks and thread-affinity crashes. **Do not break:** no global token, Python lambda bridge, or normal `QThread.terminate()`.

## Packaging entry point

**Context:** V1 release. **Decision:** PyInstaller uses root `run_hjksell.py` and clean ONEDIR. **Reason:** direct packaging from `hjksell/__main__.py` caused an import failure. **Do not break:** preserve the root entry point and ONEDIR strategy.

## Qt compatibility

**Context:** portfolio rename regression. **Decision:** QTabBar rebuilds remove tabs in a loop because QTabBar has no `clear()`. `QDesktopServices` comes from `PySide6.QtGui`. **Do not break:** preserve supported APIs in both Catalog and Analytics.

## User terminology

**Context:** post-V1 Analytics/catalog terminology. **Decision:** visible total sale amount is `ПРОДАЖИ` / `ПРОДАЖИ ПО МЕСЯЦАМ`; internal calculation fields such as `revenue` remain unchanged. `БЕЗ ВЫРУЧКИ` remains the intentional zero-sale filter.

## Neon Graphite visual direction

**Context:** approved Catalog and Analytics visual pass recorded in checkpoint `d8a8e66`. **Decision:** use near-black graphite, Onest, limited gradient branding, selective violet interaction light, and independent financial semantic colors. **Reason:** premium product direction without gaming/RGB styling. **Do not break:** violet is never a substitute for positive green, negative red, amber disposal status, or neutral values. Analytics preserves the approved four groups, order, calculations, and semantic tones.
