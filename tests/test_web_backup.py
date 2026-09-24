"""Tests for the streaming production backup restore path."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import subprocess
import sqlite3
import tarfile

import pytest

from deploy import backup_web


def archive_bytes() -> bytes:
    content = BytesIO()
    with tarfile.open(fileobj=content, mode="w") as archive:
        database = b"sqlite snapshot"
        database_info = tarfile.TarInfo("data/hjk_sell.db")
        database_info.size = len(database)
        archive.addfile(database_info, BytesIO(database))

        photo_directory = tarfile.TarInfo("data/photos/")
        photo_directory.type = tarfile.DIRTYPE
        archive.addfile(photo_directory)

        photo = b"photo bytes"
        photo_info = tarfile.TarInfo("data/photos/item.jpg")
        photo_info.size = len(photo)
        archive.addfile(photo_info, BytesIO(photo))
    return content.getvalue()


class FakeResticProcess:
    def __init__(self, payload: bytes, return_code: int) -> None:
        self.stdout = BytesIO(payload)
        self.return_code = return_code
        self.killed = False

    def wait(self) -> int:
        return self.return_code

    def poll(self) -> int | None:
        return self.return_code

    def kill(self) -> None:
        self.killed = True
        self.return_code = -9


def install_fake_restic(monkeypatch, process: FakeResticProcess) -> None:
    monkeypatch.setattr(backup_web.shutil, "which", lambda _name: "restic")

    def popen(arguments: list[str], *, stdout):
        assert arguments[1:] == ["dump", "deadbeef", backup_web.ARCHIVE_NAME]
        assert stdout == subprocess.PIPE
        return process

    monkeypatch.setattr(backup_web.subprocess, "Popen", popen)


def test_dump_snapshot_streams_database_and_photos_into_target(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "restore"
    target.mkdir()
    process = FakeResticProcess(archive_bytes(), return_code=0)
    install_fake_restic(monkeypatch, process)

    backup_web.dump_snapshot("deadbeef", target)

    assert (target / "data" / "hjk_sell.db").read_bytes() == b"sqlite snapshot"
    assert (target / "data" / "photos" / "item.jpg").read_bytes() == b"photo bytes"
    assert process.killed is False


def test_dump_snapshot_rejects_nonzero_restic_exit(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "restore"
    target.mkdir()
    process = FakeResticProcess(archive_bytes(), return_code=2)
    install_fake_restic(monkeypatch, process)

    with pytest.raises(subprocess.CalledProcessError):
        backup_web.dump_snapshot("deadbeef", target)


def test_validate_restored_media_detects_missing_database_photo(tmp_path: Path) -> None:
    database = tmp_path / "hjk_sell.db"
    photos = tmp_path / "photos"
    photos.mkdir()
    photo = photos / "item.jpg"
    photo.write_bytes(b"photo")
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE items (photo_path TEXT)")
        db.execute("INSERT INTO items (photo_path) VALUES (?)", ("/data/data/photos/item.jpg",))

    backup_web.validate_restored_media(database, photos)
    photo.unlink()

    with pytest.raises(RuntimeError, match="missing a photo"):
        backup_web.validate_restored_media(database, photos)
