# Current tasks

## NOW

- Keep the accepted Neon Graphite Catalog and Analytics UI stable.
- Preserve the verified ONEDIR candidate and user data while making only task-scoped changes.
- Validate the Web Catalog and Web-owned Telegram import pipeline while keeping all development data under `.web-dev/`.
- Keep live Web refresh non-destructive for active edits and expose per-portfolio Telegram reset without deleting catalogue history.

## NEXT

- Get the first successful run of `.github/workflows/public-readiness.yml` after the repository is pushed to GitHub; it covers the complete suite, production dependency audit, image build, Caddy validation, and isolated public-mode startup/auth smoke test. Review Dependabot's weekly update PRs before merging them.
- Before public users: validate the Restic backup/restore drill on the chosen Linux host, configure the HTTPS domain and persistent storage, then deploy. Host purchase/account access, domain, and off-site backup target are still needed from the owner.

## LATER / TECH DEBT

- No speculative product features are recorded here.
- No known release-blocking visual or packaging findings remain after manual EXE validation.
