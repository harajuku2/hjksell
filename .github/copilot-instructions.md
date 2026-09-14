# HJKsell instructions

Read [`/AGENTS.md`](../AGENTS.md) before every task and follow its safety, source-of-truth, and architecture rules. Read [`PROJECT_SPEC.md`](../PROJECT_SPEC.md) and the linked docs when relevant.

Inspect current Git status and code before editing. Keep changes minimal. Diagnose and prove crash/regression causes before fixing them. Never touch `%LOCALAPPDATA%\HJKsell` destructively, expose Telegram tokens, or use display portfolio names as identity. Preserve `None` versus zero sale semantics, Decimal finance, portfolio-specific Telegram state, direct Qt signal-to-Slot delivery, cooperative polling shutdown, supported QTabBar APIs, and ONEDIR packaging.

Run relevant tests and `git diff --check`. Do not claim manual GUI, Telegram, or EXE validation unless it was actually performed. After significant work, update only the vendor-neutral project-memory docs made stale by the change.
