# Changelog

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
- Updated Catalog and Analytics formulas so other income contributes to `ПРОДАЖИ` and net profit, while advertising contributes only to net profit.
- Allowed zero-cost Items, with undefined X/ROI displayed as `—`, and accepted Telegram caption `0`.
- Added centralized runtime typography roles with Oswald as the single visible family across Catalog and Analytics; Kulag Sha remains registered and packaged for reversible experimentation, and Onest remains available as fallback.
