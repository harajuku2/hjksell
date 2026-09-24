# Changelog

- Public deployment restore drills now reject snapshots with missing or unsafe item-photo references, in addition to SQLite integrity failures.

## 2026-09-23

- Added the first public Mini App security foundation: server-side Telegram initData validation, owner-scoped portfolios and photos, signed same-origin media sessions, and explicit persistent-storage configuration. Public mode does not seed desktop portfolios; deployment and operational checks remain outstanding.
- Prepared a single-instance Docker Compose deployment with Caddy-managed HTTPS, non-root read-only app container, explicit persistent data mount, secret-file inputs, health checks, and a Linux host checklist. The image still needs validation on a Linux Docker host.
- Made public startup fail closed when its database contains portfolios without verified Telegram owners, preventing accidental reuse of desktop or development data.
- Kept active Mini App sessions usable when Telegram leaves stale initData in an open WebView: an existing signed cookie is accepted as fallback and is renewed only by fresh Telegram data.
- Added baseline HSTS, content-type-sniffing, and referrer-policy headers at the HTTPS proxy without imposing an unverified Content Security Policy on Telegram's WebView.
- Prepared a daily Restic off-site backup and isolated restore-drill path: SQLite online snapshot with integrity check, streamed photos, encrypted repository, retention, and a target guard that prevents restoration over production data.
- Limited proxied request bodies to 6 MB before FastAPI reads them, and pinned Caddy to 2.10+ where that request-body guard is available.
- Added a secret-free Linux CI workflow for the full test suite, production image build, Caddy validation, and isolated public-mode container/auth smoke test.
- Disabled HTTP caching for authenticated API data and owner-scoped photos, including unauthorized responses, to prevent private WebView data from being reused by browser or shared caches.
- Changed Restic restore verification to stream directly from the repository into its isolated target, avoiding a full photo archive on the host's RAM-backed `/run` filesystem.
- Added an SHA-pinned `pip-audit` CI gate for the exact production Python dependency set.
- Enabled weekly Dependabot update PRs for Python dependencies, Docker images, and GitHub Actions.
- Added a public-mode-only owner-scoped data-erasure control that removes a user's records and referenced photos; documented that encrypted backups retain snapshots on their independent schedule.

- Reworked Catalog month summaries into purchase cohorts: monthly ROI uses all invested capital, the upper profit field shows realized Item profit, and the lower total profit field shows the monthly cash result after sales, income, advertising, expenses, and all purchases.
- Expanded both Web currency selectors to the full supported currency set and made official-rate requests bypass a stale local proxy, restoring the `Актуальный курс` action.
- Added a Settings control for a portfolio-scoped automatic purchase expense. It converts the saved amount into the purchase currency once, applies only to subsequently created Items, and leaves each Item's three-dot expense override intact.
- Added a per-Item purchase-currency expense to the desktop and Web action menus; it recalculates historical cost, profit, X, ROI, warehouse value, and Analytics, while a blank saved value clears the expense.
- Replaced the Web Catalog header actions with a stable five-zone bottom navigator for Catalog, Analytics, Telegram, manual Item creation, and Settings; Telegram keeps a scoped portfolio picker while the primary portfolio selector remains in the header.
- Reworked Web currency selection into a compact graphite panel and an opaque full-screen currency list on every viewport; Analytics now concludes Result with illuminated net profit and Efficiency with illuminated average X.
- Added portfolio-scoped multi-currency defaults for the Web Catalog, historical currency codes on Items, official NBRB cross-rate lookup, and dynamic currency labels without rewriting existing purchases.
- Compacted the Web Catalog phone layout, removed transform-based mobile surface motion, reduced the dragon backdrop blur, added persistent mobile Portfolio/Analytics tabs, and highlighted net profit as the primary green result.
- Renamed the analytics item-only result to `ПРИБЫЛЬ С ПРОДАЖ`, making its separation from additional monthly income explicit.
- Reworked the supplied dragon backdrop with a lighter contour-preserving blur, changed the mobile tabs into an edge-to-edge bottom sheet with only a top border, and added an explicit close control to the mobile currency picker.
- Replaced the backdrop with the user-supplied blurred image asset, preserving its dark contour treatment exactly as provided.
- Kept sales and ROI isolated from monthly additional income: other income and advertising now affect only net profit, while expenses alone affect ROI after expenses.

## V1.0.0 — `c65bba1`

- Stable local Windows release.
- 44 tests passed at release.
- Manual EXE, Catalog, Analytics, Telegram configuration, independent imports, and restart validation were performed before release.

## Post-V1.0 development checkpoint — `febdb68`

- Reversible sales and completed zero-price disposal.
- Catalog `БЕЗ ВЫРУЧКИ` state and `УШЛА НА БЛАГОЕ ДЕЛО` badge.
- Editable portfolio display names with `portfolio_id` identity preservation.
- QTabBar rebuild regression fix.
- Analytics grouping and visible `ПРОДАЖИ` terminology.
- Item lower metrics label-above-value layout.
- Checkpoint suite was 55 passed.

## Neon Graphite and packaging checkpoint — `d8a8e66` plus current packaging change

The approved Catalog and Analytics work is recorded in checkpoint commit `d8a8e66` and includes:

- Onest variable font and SIL OFL license under `assets/fonts/onest/`;
- QFontDatabase loading and gradient HJKsell branding;
- Catalog-scoped graphite/violet styling and inputs;
- AmbientHeader and selective violet states;
- compact Item metric grid and subtle Item separation;
- Catalog semantic tone handling for Profit/X/ROI;
- regression tests for glow state and financial semantic transitions.

- Analytics keeps the four approved groups/order, calculations, and semantic tones while using scoped Neon Graphite styling, Onest gradient title, compact KPI cells, and violet chart accents.
- The Catalog financial semantic render bug is fixed with production-level repolish and render regression coverage.
- The full suite is 62 passed.
- The current `build.ps1` change adds the Onest font directory to the existing PyInstaller ONEDIR package.
- The resulting EXE was manually tested successfully with existing Items, photos, portfolios, Catalog, Analytics, and user data intact.
- The current follow-up adds the multi-size `assets/icons/hjksell.ico` application icon to both Qt startup and the existing ONEDIR package.
- The original icon artwork is preserved as `assets/icons/hjksell-source.webp`; the user manually verified the dragon on the Windows taskbar. Explorer's old icon was confirmed to be Windows icon caching because a renamed copy of the same EXE displayed the new icon immediately.

## Monthly income and free-item support

- Added persisted portfolio/month-scoped `ДРУГИЕ ДОХОДЫ` and `РЕКЛАМА` values alongside monthly expenses.
- Updated Catalog and Analytics formulas so other income and advertising contribute only to net profit and never change `ПРОДАЖИ`, X, or ROI.
- Allowed zero-cost Items, with undefined X/ROI displayed as `—`, and accepted Telegram caption `0`.
- Added centralized runtime typography roles with Oswald as the single visible family across Catalog and Analytics; Kulag Sha remains registered and packaged for reversible experimentation, and Onest remains available as fallback.

## V2 Catalog visual prototype

- Added a continuous atmospheric graphite backplate, translucent Catalog workspace, painted Item information islands, rounded photo wells, material-style controls, and a restrained violet scrollbar.
- Removed Catalog portfolio/filter drop-shadow effects whose rectangular widget bounds created visible glow boundaries.

## Local web skeleton Phase 1

- Hardened the mobile Catalog layout for real-device use: contained date inputs and Item photos, opaque Item menus, centered action dots, brighter semantic status rails, viewport-safe currency controls, edge-to-edge bottom navigation zones, and an empty reserved brand slot in the header.
- Reordered the Web Catalog so a fresh portfolio view starts with all months collapsed, keeps the current month first, and places its compact summary directly below it; neutralized Item and currency menu surfaces to opaque graphite.
- Reordered Item metrics so Profit occupies the former ROI position and is framed as the primary positive/negative neon result, with ROI moving into the former Profit position.
- Made desktop Item profit a stronger semantic neon value without a frame, retained the framed mobile treatment, added a fast mobile return-to-top control, and normalized Item action menus to opaque monochrome graphite.
- Made the mobile bottom navigation fully opaque through its safe-area surface, moved mobile Item profit into a left-shifted focal row, placed the desktop Analytics toggle last for immediate return to portfolios, and removed focus/message flicker after a successful current-rate lookup.
- Added a portfolio picker directly to Analytics and reserved a third, empty Settings tab in the mobile navigation.

- Added an isolated FastAPI backend over the existing repositories, ItemService, AnalyticsService, finance helpers, and shared Catalog filter semantics.
- Added a neutral no-build Catalog frontend with portfolio switching, historical FX-safe Item creation, exact sale filters, month-owned financial values, complete month collapse, sales/cancellation, development photos, and soft deletion.
- Added Web-owned Telegram polling and configuration over the shared importer, with portfolio-scoped status, channel binding, duplicate-safe imports, and live Catalog refresh.
- Protected unsaved Catalog and Telegram field drafts from live refresh replacement; added per-portfolio Telegram disconnect/clear and removed the redundant manual refresh button.
- Made Web Telegram messages state-based, cleared stale diagnostics on reconfiguration, removed the unused manual polling control, and preserved each portfolio's collapsed-month state through live refresh.
- Preserved unsaved exchange-rate edits and open Item action menus through live refresh; menus now close only after an explicit click outside the menu.
- Reordered the Web Catalog to match the desktop information flow: header controls, month metrics, month values, and full-width photo-first Item rows with a right-side action menu; added responsive mobile stacking.
- Made the current-month summary widget visible only while its month is collapsed, avoiding duplicate KPIs when the month is open.
- Added monthly invested amount as the first metric in the collapsed summary widget, with a full-width profit row on mobile.
- Kept newly added Web items first within their purchase date and raised the open item menu above following rows; reduced menu spacing for compact desktop and mobile use.
- Kept web SQLite and media under ignored `.web-dev/`; the web runtime does not resolve or access `%LOCALAPPDATA%\HJKsell`.
- Reworked the Web Catalog into a responsive graphite-and-lavender visual system with local Onest and Oswald fonts, animated filter selection, semantic Item edge states, and mobile-first breakpoints while preserving the established Catalog information layout and shared backend logic.
- Prevented unchanged Telegram polling refreshes from rebuilding the Catalog DOM and replaying reveal animations, eliminating periodic visual flicker. Replaced the native portfolio selector presentation with backend-driven accessible tabs that keep the active portfolio visibly selected on desktop and mobile.
- Added a local dark textile Catalog backdrop with restrained glass surfaces, preserving financial color semantics and the established Catalog layout. Item photos now open in a click-anywhere-to-close full-size viewer, while mobile Item cards use a full-width contained photo treatment to avoid aggressive cropping.
- Replaced the first Catalog texture with an asymmetrical Japanese-inspired dragon, ink, silk, and lacquer backdrop. Increased translucency and physical glass treatment across the large Catalog surfaces while keeping controls darker for reliable input and metric legibility.
- Replaced the illustrated backdrop with a minimal black-and-lavender liquid backplate and raised the Web Catalog surfaces to a clear glossy glass treatment. Item financial/status typography now reflects domain semantics: lavender historical cost, green/red positive and negative metrics, green sold, amber in-stock, and violet no-revenue completion.
- Added a responsive Web Analytics view backed by the existing `AnalyticsService`, with net profit as the primary result metric. Replaced fixed portfolio tabs with a backend-driven selector and creation flow; every new portfolio starts empty and retains independent Catalog, monthly finance, Analytics, and Telegram state.
- Shifted the Web visual system to transparent graphite gloss with sharp specular edges, minimal blur, restrained dark-violet reflection, and preserved semantic financial colors.
- Replaced browser-native portfolio and analytics period popups with local glass listboxes, kept the primary analytics metric inside its result band, added action-driven reveals for the add-item and Telegram panels, and moved the backdrop to a blurred black-and-graphite dragon treatment with edge reflections on glass surfaces.
- Unified Catalog and Analytics panel, selector, and Item-menu motion into the same reversible open/close transition; restored `ЧИСТАЯ ПРИБЫЛЬ` to a bounded result-grid cell and applied the user-provided dragon raster as the CSS-blurred Web backdrop.
- Added protected Web portfolio deletion with cleanup of portfolio-scoped Items, monthly values, and Telegram records; matched the new-portfolio form typography to the shared interface font.
# 2026-09-23

- Added an explicit production web mode foundation: Telegram Mini App initData verification, owner-scoped portfolios, and required persistent data path configuration. Local development remains isolated and keeps its seeded portfolios.
- Encrypted per-portfolio Telegram import-bot tokens in public mode and scoped discovered channels to their owning portfolio. Added a provider-neutral single-instance deployment guide and a slim Web dependency set.
