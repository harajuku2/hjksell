"""Local photo storage used by manual entry and photo replacement."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from ..config import AppPaths, ensure_app_directories


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
