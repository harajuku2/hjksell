"""Local photo storage used by manual entry and photo replacement."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Protocol

from ..config import AppPaths, ensure_app_directories


class PhotoStorage(Protocol):
    """Storage boundary consumed by manual and Telegram item creation."""

    def save_photo_bytes(self, content: bytes, suffix: str = ".jpg") -> str:
        ...


class PhotoService:
    def __init__(self, paths: AppPaths) -> None:
        self.paths = ensure_app_directories(paths)

    def copy_photo(self, source: str | Path) -> str:
        source_path = Path(source)
        if not source_path.is_file():
            raise ValueError("Файл фотографии не найден.")
        suffix = source_path.suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}:
            raise ValueError("Выберите файл изображения.")
        destination = self.paths.photos / f"{uuid.uuid4().hex}{suffix}"
        shutil.copy2(source_path, destination)
        return str(destination)

    def save_photo_bytes(self, content: bytes, suffix: str = ".jpg") -> str:
        """Store a downloaded image once and return its local path."""

        if not content:
            raise ValueError("Telegram вернул пустое фото.")
        normalized_suffix = suffix.lower() if suffix else ".jpg"
        if not normalized_suffix.startswith("."):
            normalized_suffix = f".{normalized_suffix}"
        if normalized_suffix not in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}:
            normalized_suffix = ".jpg"
        destination = self.paths.photos / f"{uuid.uuid4().hex}{normalized_suffix}"
        destination.write_bytes(content)
        return str(destination)

    def delete_photo_paths(self, photo_paths: list[str]) -> int:
        """Delete known item photos without following paths outside the media root."""

        media_root = self.paths.photos.resolve(strict=True)
        deleted = 0
        for photo_path in set(photo_paths):
            candidate = Path(photo_path)
            if candidate.parent.resolve(strict=True) != media_root:
                raise ValueError("Отказано в удалении фотографии за пределами хранилища HJKsell.")
            try:
                candidate.unlink(missing_ok=True)
            except OSError as exc:
                raise RuntimeError("Не удалось полностью очистить фотографии портфеля.") from exc
            deleted += 1
        return deleted
