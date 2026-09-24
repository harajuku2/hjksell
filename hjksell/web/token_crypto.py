"""Authenticated encryption adapter for per-portfolio Telegram bot tokens."""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


class TelegramTokenCipher:
    PREFIX = "fernet:v1:"

    def __init__(self, key: str) -> None:
        try:
            self._fernet = Fernet(key.encode("ascii"))
        except (UnicodeEncodeError, ValueError) as exc:
            raise RuntimeError("HJKSELL_TOKEN_ENCRYPTION_KEY должен быть корректным ключом Fernet.") from exc

    def encrypt(self, token: str) -> str:
        return self.PREFIX + self._fernet.encrypt(token.encode("utf-8")).decode("ascii")

    def decrypt(self, value: str) -> str:
        if not value.startswith(self.PREFIX):
            raise RuntimeError(
                "В базе найден незашифрованный Telegram-токен. Публичный режим остановлен; выполните защищённую миграцию данных."
            )
        try:
            return self._fernet.decrypt(value[len(self.PREFIX):].encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeError) as exc:
            raise RuntimeError("Не удалось расшифровать Telegram-токен. Проверьте ключ хостинга.") from exc
