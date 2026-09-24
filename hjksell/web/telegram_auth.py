"""Validation helpers for Telegram Mini App initData and short-lived sessions."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import hmac
import json
import time
from urllib.parse import parse_qsl


@dataclass(frozen=True)
class TelegramIdentity:
    user_id: int


def validate_init_data(
    init_data: str,
    bot_token: str,
    *,
    now: int | None = None,
    max_age_seconds: int = 86_400,
) -> TelegramIdentity:
    """Verify Telegram's HMAC and the freshness of a Mini App launch payload."""

    try:
        if not init_data or len(init_data) > 16_384:
            raise ValueError
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
        values = dict(pairs)
        if len(values) != len(pairs) or "hash" not in values:
            raise ValueError
        received_hash = values.pop("hash")
        if len(received_hash) != 64:
            raise ValueError
        data_check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
        secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), sha256).digest()
        expected_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), sha256).hexdigest()
        if not hmac.compare_digest(expected_hash, received_hash):
            raise ValueError
        auth_date = int(values["auth_date"])
        current_time = int(time.time()) if now is None else now
        if auth_date > current_time + 60 or current_time - auth_date > max_age_seconds:
            raise ValueError
        user_data = json.loads(values["user"])
        user_id = user_data["id"]
        if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
            raise ValueError
        return TelegramIdentity(user_id=user_id)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Не удалось проверить вход через Telegram. Откройте приложение из Telegram ещё раз.") from exc


def issue_session_cookie(user_id: int, bot_token: str, *, now: int | None = None) -> str:
    expires_at = (int(time.time()) if now is None else now) + 43_200
    payload = f"{user_id}.{expires_at}"
    signature = _session_signature(payload, bot_token)
    return f"{payload}.{signature}"


def validate_session_cookie(value: str, bot_token: str, *, now: int | None = None) -> int | None:
    try:
        user_text, expiry_text, signature = value.split(".", 2)
        user_id, expires_at = int(user_text), int(expiry_text)
        payload = f"{user_id}.{expires_at}"
        current_time = int(time.time()) if now is None else now
        if user_id <= 0 or expires_at < current_time or expires_at > current_time + 43_200:
            return None
        if not hmac.compare_digest(_session_signature(payload, bot_token), signature):
            return None
        return user_id
    except (ValueError, TypeError):
        return None


def authenticate_request(
    init_data: str | None,
    session_cookie: str,
    bot_token: str,
    *,
    now: int | None = None,
) -> tuple[int | None, bool]:
    """Prefer fresh Telegram data, then fall back to an existing signed session."""

    if init_data:
        try:
            return validate_init_data(init_data, bot_token, now=now).user_id, True
        except ValueError:
            pass
    return validate_session_cookie(session_cookie, bot_token, now=now), False


def _session_signature(payload: str, bot_token: str) -> str:
    key = hmac.new(bot_token.encode("utf-8"), b"HJKsellTelegramSession", sha256).digest()
    return hmac.new(key, payload.encode("ascii"), sha256).hexdigest()
