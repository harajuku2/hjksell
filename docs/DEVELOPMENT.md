# Development guide

## Safe start

From `C:\HJKsell`, inspect `git status --short` and `git diff --stat`. Preserve unrelated user changes. Never access or alter `%LOCALAPPDATA%\HJKsell` for ordinary tests or UI work.

Use the project interpreter:

`.\.venv\Scripts\python.exe -m hjksell`

Run tests:

`.\.venv\Scripts\python.exe -m pytest -q`

Run the isolated local web skeleton:

`.\.venv\Scripts\python.exe -m hjksell.web`

Then open `http://127.0.0.1:8765`. The backend and static frontend share one localhost origin, so no CORS configuration or Node build is required. Web development data is created only at `C:\HJKsell\.web-dev\data\hjk_sell_web_dev.db`; development photos remain under the same ignored `.web-dev` root. Web Telegram settings are entered in the Telegram panel; polling is owned by the Web backend and never uses the desktop database. The panel supports token validation, discovered-channel selection, and per-portfolio `Отключить и очистить`; this clears Telegram configuration and polling state but leaves catalogue data intact. Live refresh pauses while a Catalog or Telegram field has unsaved input or an Item action menu is open, so background polling cannot replace the user's draft, focus, or menu. Exchange-rate edits remain local until explicitly saved, and an open Item menu closes only on an explicit click outside it. Expanded/collapsed months are preserved independently for each portfolio.

Before committing, run:

`git diff --check`

There is no configured project linter or formatter in the repository. Do not invent one. `build.ps1` is the explicit clean ONEDIR build command and must not be run casually because it removes project `build/`, `dist/`, and `HJKsell.spec` artifacts.

## Validation expectations

Automated tests cover services, repositories, finance, Analytics, Telegram parsing/isolation, and selected Qt behavior. They do not prove visual quality, real Telegram behavior, or packaged EXE behavior. Manual GUI checks are required after UI changes; real Telegram and EXE checks are separate release validation.

For regressions use: reproduce → inspect traceback/logs → prove root cause → minimal fix → regression test → full pytest → manual check.

## Test/data safety

Tests should use temporary directories or in-memory SQLite. Web API tests inject their own temporary `AppPaths`. Production database, photos, logs, Telegram settings, and imports under `%LOCALAPPDATA%\HJKsell` are out of scope. Never print token values.

## Current checkpoint state

Checkpoint commits `d8a8e66`, `48f4ed8`, and `0cacf5d` record the approved Neon Graphite Catalog and Analytics work, Onest/icon assets, scoped styling, semantic metric tones, packaging integration, and related tests. The Catalog and Analytics UI, including the financial render fix, were manually accepted in the packaged ONEDIR EXE, and the Windows taskbar icon was manually verified. Current development adds portfolio/month-scoped income fields and zero-cost Item support; validate the real Catalog manually after changes.
