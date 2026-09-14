# Development guide

## Safe start

From `C:\HJKsell`, inspect `git status --short` and `git diff --stat`. Preserve unrelated user changes. Never access or alter `%LOCALAPPDATA%\HJKsell` for ordinary tests or UI work.

Use the project interpreter:

`.\.venv\Scripts\python.exe -m hjksell`

Run tests:

`.\.venv\Scripts\python.exe -m pytest -q`

Before committing, run:

`git diff --check`

There is no configured project linter or formatter in the repository. Do not invent one. `build.ps1` is the explicit clean ONEDIR build command and must not be run casually because it removes project `build/`, `dist/`, and `HJKsell.spec` artifacts.

## Validation expectations

Automated tests cover services, repositories, finance, Analytics, Telegram parsing/isolation, and selected Qt behavior. They do not prove visual quality, real Telegram behavior, or packaged EXE behavior. Manual GUI checks are required after UI changes; real Telegram and EXE checks are separate release validation.

For regressions use: reproduce → inspect traceback/logs → prove root cause → minimal fix → regression test → full pytest → manual check.

## Test/data safety

Tests should use temporary directories or in-memory SQLite. Production database, photos, logs, Telegram settings, and imports under `%LOCALAPPDATA%\HJKsell` are out of scope. Never print token values.

## Current uncommitted work

The worktree after checkpoint `febdb68` contains an uncommitted Neon Graphite Catalog experiment. Current code includes Onest assets and OFL license, QFontDatabase loading, Catalog-scoped styling, gradient branding, AmbientHeader, graphite inputs/violet focus, compact Item metrics, semantic Catalog metric tones, and related tests. Treat this as experimental and not released. A real screenshot/manual review is still required before any packaging or checkpoint decision.
