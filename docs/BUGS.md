# Bug register

## FIXED — regression-sensitive

### Telegram Settings Check → Save thread-affinity crash

The historical crash was caused by polling-worker diagnostics crossing through a Python lambda and performing GUI/QObject work in the polling thread. Current code uses a typed signal directly to a GUI Qt Slot and cooperative worker/API shutdown. Preserve this architecture and validate real polling separately from startup tests.

### QTabBar.clear() startup crash

PySide6 QTabBar has no `clear()`. Catalog and Analytics rebuild tabs with `removeTab(0)` loops while signals are blocked, preserving the selected `portfolio_id`.

### PyInstaller entry-point import failure

The root `run_hjksell.py` entry point is required; do not package directly from `hjksell/__main__.py`.

### Incorrect QDesktopServices import

`QDesktopServices` belongs to `PySide6.QtGui`.

### Green Neon Graphite glow

Eight-digit strings such as `#a05bff44` were interpreted by Qt as `#AARRGGBB`, producing green RGB channels instead of CSS-like RGBA ordering. Current Catalog interaction effects use explicit `QColor(r, g, b, a)`. Keep this convention for translucent effects.

### Old blue Catalog inputs

The shared old QLineEdit styling affected `exchangeRate`, `monthlyExpense`, and `saleInput`. Current Catalog-scoped selectors use graphite normal state and violet focus. Preserve this without broad Analytics repainting.

## Current experimental state

The Catalog loss-metric issue is corrected in the current uncommitted worktree: `catalog_metric_tone()` and `tone` selectors cover Profit, X, ROI, zero disposal, and cancellation. Item result labels are repolished after their row is attached below `catalogRoot`, so the scoped selectors match during the real MainWindow paint path. This remains regression-sensitive until the user completes real screenshot/manual verification. If current code differs, inspect it before changing this entry.
