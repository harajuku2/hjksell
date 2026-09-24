# Public Web Deployment

The local Windows application and its database are not the public service. Deploy the Web app as a separate single-instance service with one durable, private disk. SQLite and uploaded photos both live on that disk; do not run multiple app replicas against this database. `Dockerfile.web`, `compose.yaml`, and `Caddyfile` provide the prepared single-host setup: the app is private to the Compose network, Caddy terminates HTTPS, limits request bodies to 6 MB before proxying, sets basic transport/security headers, and SQLite/photos use an explicit host path.

## Runtime

- Install `requirements-web.txt` and run `python -m hjksell.web`.
- Set `HJKSELL_ENV=production`.
- Set `HJKSELL_DATA_DIR` to the absolute mount path of the provider's persistent disk.
- Set `HJKSELL_MINI_APP_BOT_TOKEN` as a host secret. This is the launcher Mini App bot token, not a per-portfolio import token.
- Set `HJKSELL_TOKEN_ENCRYPTION_KEY` as a second host secret. Generate a Fernet key with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`; keep a protected backup because losing or changing it makes saved import-bot tokens unreadable.
- Let the provider supply `PORT`; the app binds to `0.0.0.0` and defaults to port 8765 for local use.
- Terminate HTTPS at the provider or a trusted reverse proxy. Session cookies are Secure and production startup requires a token and persistent data path.

## Prepare the host

1. Create an Ubuntu 24.04 VPS and point a domain's A record to its public IPv4 address. In the VPS provider's network firewall, allow inbound TCP 22, 80, and 443; UDP 443 is optional for HTTP/3. Do not expose port 8765. The Compose file publishes only Caddy's web ports; the application port is private to the Compose network. Docker-published ports can bypass UFW rules, so do not rely on UFW alone to restrict public container ports. If host-level filtering is also required, configure and verify it in Docker's `DOCKER-USER` chain.
2. Install Docker Engine and the Docker Compose plugin from Docker's official repository.
3. Clone or securely transfer the reviewed application source to `/opt/hjksell`.
4. Copy `.env.example` to `.env` and set the actual public domain and absolute host paths. Keep `.env` private; it contains paths, not secret values.
5. Create `/srv/hjksell` owned by UID/GID 10001 for application data. Create the two secret files outside the checkout, owned by UID/GID 10001 with mode `0400`; put the Mini App bot token and a generated Fernet key in their respective files. Never commit either secret.
6. From `/opt/hjksell`, run `docker compose config` to validate configuration, then `docker compose up -d --build`. Confirm `docker compose ps` reports both services healthy and open `https://<your-domain>/api/health`.

The public process refuses to start if the configured database contains portfolios without a verified Telegram owner. Keep the production data directory new and separate; do not point it at the Windows desktop database or `.web-dev/`.

The current development machine does not have Docker available, so the image and Compose configuration still require validation on the actual Linux host before public use. The readiness workflow also audits pinned production Python dependencies against known vulnerability reports. Dependabot proposes weekly updates for production Python packages, Docker images, and workflow actions; review and test each update before merging. Do not transfer the working tree to a public host or invite users until the tests, dependency audit, Linux startup, TLS, authentication, and backup/restore checks below pass.

## Encrypted off-site backups

`deploy/backup_web.py` uses SQLite's online backup API to make a transactionally consistent database snapshot, checks it with `PRAGMA integrity_check`, then streams that snapshot plus the photos directly into Restic. Plain photo archives are not written to disk; only the temporary SQLite snapshot is placed in systemd's private runtime directory. Restic encrypts the streamed archive before it leaves the server. Retention is 14 daily, 8 weekly, and 12 monthly snapshots.

1. Choose a separate off-site Restic repository (for example, an SFTP or S3-compatible backup account), install the Restic CLI on the VPS, and generate a strong repository password. Keep a protected offline copy of that password; losing it makes backups unrecoverable.
2. Create `/etc/hjksell/backup.env`, readable only by UID/GID 10001, with `HJKSELL_DATA_DIR=/srv/hjksell`, `RESTIC_REPOSITORY=<off-site repository>`, `RESTIC_PASSWORD_FILE=/etc/hjksell/restic-password`, and `RESTIC_CACHE_DIR=/run/hjksell-backup/cache`. Configure remote credentials through the provider's protected credential mechanism; never put them in Git or the project `.env`.
3. Install `deploy/hjksell-backup.service`, `deploy/hjksell-backup-init.service`, `deploy/hjksell-backup-list.service`, `deploy/hjksell-backup-restore@.service`, and `deploy/hjksell-backup.timer` into `/etc/systemd/system/`. Start `hjksell-backup-init.service` exactly once to initialize the repository, then run `hjksell-backup.service` once and inspect its journal for success.
4. Enable `hjksell-backup.timer`. Confirm the first snapshot exists by running `systemctl start hjksell-backup-list.service` and inspecting its journal.
5. For a restore drill, copy a snapshot ID from that journal and start `hjksell-backup-restore@<snapshot-id>.service`. It streams the archive into a private temporary directory under `/run` instead of buffering the full photo archive, refuses to overwrite production data, validates archive paths, checks SQLite integrity, and verifies that every database photo reference exists inside the restored photo directory. Inspect the restored photos under `/run/hjksell-restore-<snapshot-id>/data/photos` and launch a temporary isolated instance before considering any production recovery.

## Before inviting users

1. Configure a domain and verify HTTPS.
2. Create a dedicated Telegram bot for launching HJKsell and save its token only in the host's secret manager.
3. After HTTPS is active, configure the URL in `@BotFather`. For the simplest launch path, set the bot's menu button with `/setmenubutton` (or Bot Settings > Menu Button) to the HTTPS URL. Optionally configure it as the bot's Main Mini App to add a profile Launch app button and `t.me/<bot>?startapp` link. The web client already loads Telegram's `telegram-web-app.js` in `<head>` and sends raw `initData` to the backend; never authenticate from `initDataUnsafe` or a browser-only URL.
4. Verify Telegram initData authentication, cross-user portfolio denial, photo privacy, encrypted token storage, and Telegram import on the deployed service.
5. Configure automated encrypted backups for both the SQLite database and photos, then perform a restore drill.
6. Publish clear privacy and data-retention information before broad public access. Users can erase their Telegram-owned portfolios, records, Telegram settings, and referenced photos from the live store; encrypted Restic snapshots follow their separately configured retention schedule.

Do not copy `%LOCALAPPDATA%\HJKsell` or `.web-dev/` into production by default. A data import, if desired, must be separately requested and planned.
