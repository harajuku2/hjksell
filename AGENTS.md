# HJKsell Agent Memory

## What this project is

HJKsell is a local Windows 10/11 PySide6 desktop application for tracking a Vinted clothing resale business. It uses SQLite, SQLAlchemy, Alembic, httpx/Telegram Bot API, and PyInstaller. V1 has no server, cloud storage, accounts, or paid infrastructure.

## Before every task

1. Read this file.
2. Read [PROJECT_SPEC.md](./PROJECT_SPEC.md) when product behavior is involved.
3. Read [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) for architecture-sensitive work.
4. Read [docs/BUGS.md](./docs/BUGS.md) and [docs/TASKS.md](./docs/TASKS.md).
5. Run `git status --short` and inspect the actual relevant diff/code.
6. Treat current source and Git state as authoritative; historical checkpoints are context only.
7. Make the smallest task-scoped change.

Source-of-truth order: current code/Git state, current specification and docs, historical checkpoints.

## Absolute safety rules

- Never delete, reset, clean, overwrite, or migrate `%LOCALAPPDATA%\HJKsell` without explicit authorization.
- Never touch its database, photos, logs, Telegram configuration/state, or `telegram_imports` as part of ordinary development.
- Never expose or log Telegram bot tokens or credentials.
- Never add secrets to source or documentation.
- Do not commit, tag, build, or stage unless explicitly requested.

## Architectural invariants

- UI uses services and repositories; do not put arbitrary SQLite queries in UI.
- Money uses `Decimal`, not float.
- `portfolio_id` is identity. `Portfolio.name` is editable presentation only.
- `sale_price_byn is None` means unsold/in stock. `sale_price_byn == 0` means completed zero-revenue disposal.
- Purchase month and sale month are independent. An Item keeps its historical exchange rate.
- Items are soft-deleted through `deleted_at`.
- Telegram tokens, channels, offsets, imports, and polling workers are portfolio-specific.
- Telegram diagnostics use a typed Qt signal directly to a GUI Qt Slot; do not insert a Python lambda or use `QThread.terminate()` for normal shutdown.
- `QTabBar` has no `clear()`; rebuild tabs with `removeTab()` loops.
- Packaging is clean PyInstaller ONEDIR through `run_hjksell.py`, not `hjksell/__main__.py`.
- Purple is brand/interaction. Green, red, amber, and neutral retain financial/status meaning.

## Standard workflow

For a normal change: inspect → implement minimally → targeted/full tests → manual verification where relevant → report. For a crash or regression: reproduce → diagnose and prove the root cause → minimal fix → regression test → full pytest → manual verification. Pytest does not replace GUI, Telegram, or EXE testing.

Before a commit, run `git diff --check`; commit only explicitly approved files.

## Quick commands

- Development: `.\.venv\Scripts\python.exe -m hjksell`
- Tests: `.\.venv\Scripts\python.exe -m pytest -q`
- Build: `.\build.ps1` (clean ONEDIR; only run when explicitly requested)

## Current Git context

- Stable release: tag `v1.0.0` at commit `c65bba1`.
- Development checkpoint: `febdb68 Add post-v1.0 sales and portfolio QoL improvements`.
- The Neon Graphite Catalog and Analytics work is recorded in checkpoint commit `d8a8e66`; the current packaging change is limited to `build.ps1`.
- `SESSION_CHECKPOINT.md` is historical and already exists in checkpoint history; do not modify or stage it automatically.

## Documentation map

- [PROJECT_SPEC.md](./PROJECT_SPEC.md): detailed product passport.
- [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md): current code architecture and data flows.
- [docs/DEVELOPMENT.md](./docs/DEVELOPMENT.md): safe development and validation workflow.
- [docs/DECISIONS.md](./docs/DECISIONS.md): durable architecture decisions.
- [docs/BUGS.md](./docs/BUGS.md): regression-sensitive bug register.
- [docs/TASKS.md](./docs/TASKS.md): current work state.
- [docs/CHANGELOG.md](./docs/CHANGELOG.md): meaningful project milestones.

## Memory maintenance

After a significant task, determine which documented facts changed and update only affected docs. Move resolved entries in TASKS/BUGS, add short CHANGELOG entries for meaningful milestones, and add DECISIONS only for durable choices. Never paste session transcripts, secrets, or user data into documentation. Documentation must describe current code, not intended code.
