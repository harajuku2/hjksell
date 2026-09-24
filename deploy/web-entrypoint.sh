#!/bin/sh
set -eu

export HJKSELL_MINI_APP_BOT_TOKEN="$(cat "$HJKSELL_MINI_APP_BOT_TOKEN_FILE")"
export HJKSELL_TOKEN_ENCRYPTION_KEY="$(cat "$HJKSELL_TOKEN_ENCRYPTION_KEY_FILE")"
unset HJKSELL_MINI_APP_BOT_TOKEN_FILE HJKSELL_TOKEN_ENCRYPTION_KEY_FILE

exec python -m uvicorn hjksell.web.run:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --proxy-headers \
    --forwarded-allow-ips='*'
