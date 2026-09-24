"""Create and safely inspect encrypted Restic backups of Web data."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
from urllib.parse import quote


ARCHIVE_NAME = "hjksell-data.tar"
SNAPSHOT_ID_RE = re.compile(r"^[0-9a-f]{8,64}$")


def environment() -> tuple[Path, Path]:
    data_root_text = os.environ.get("HJKSELL_DATA_DIR", "")
    repository = os.environ.get("RESTIC_REPOSITORY", "")
    password_file = Path(os.environ.get("RESTIC_PASSWORD_FILE", ""))
    if not data_root_text or not Path(data_root_text).is_absolute():
        raise RuntimeError("HJKSELL_DATA_DIR must be an absolute host data path.")
    if not repository or not password_file.is_file():
        raise RuntimeError("Set RESTIC_REPOSITORY and a readable RESTIC_PASSWORD_FILE.")
    return Path(data_root_text).resolve(strict=True), password_file


def runtime_directory() -> Path:
    path = Path(os.environ.get("RESTIC_CACHE_DIR", "/run/hjksell-backup/cache")).parent
    if not path.is_dir():
        raise RuntimeError("The private systemd runtime directory is missing.")
    return path


def snapshot_database(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise RuntimeError(f"Database not found: {source}")
    source_uri = f"file:{quote(source.as_posix(), safe='/')}?mode=ro"
    with sqlite3.connect(source_uri, uri=True, timeout=30) as origin:
        with sqlite3.connect(destination) as snapshot:
            origin.backup(snapshot, pages=256, sleep=0.05)
            result = snapshot.execute("PRAGMA integrity_check").fetchone()
            if result is None or result[0] != "ok":
                raise RuntimeError("The SQLite backup failed its integrity check.")


def restic(*arguments: str, stdout=None) -> None:
    executable = shutil.which("restic")
    if executable is None:
        raise RuntimeError("Install the Restic command-line client on the host first.")
    subprocess.run([executable, *arguments], check=True, stdout=stdout)


def initialize_repository() -> None:
    environment()
    restic("init")


def list_snapshots() -> None:
    environment()
    restic("snapshots", "--tag", "hjksell")


def create_backup() -> None:
    data_root, _ = environment()
    database = data_root / "data" / "hjk_sell.db"
    photos = data_root / "data" / "photos"
    if not photos.is_dir():
        raise RuntimeError(f"Photo directory not found: {photos}")

    with tempfile.TemporaryDirectory(prefix="snapshot-", dir=runtime_directory()) as temporary:
        database_snapshot = Path(temporary) / "hjk_sell.db"
        snapshot_database(database, database_snapshot)
        executable = shutil.which("restic")
        if executable is None:
            raise RuntimeError("Install the Restic command-line client on the host first.")
        restic(
            "backup",
            "--stdin-from-command",
            "--stdin-filename",
            ARCHIVE_NAME,
            "--tag",
            "hjksell",
            "--host",
            "hjksell-production",
            "--",
            sys.executable,
            str(Path(__file__).resolve()),
            "stream",
            "--database",
            str(database_snapshot),
            "--photos",
            str(photos),
        )

    restic(
        "forget",
        "--tag",
        "hjksell",
        "--host",
        "hjksell-production",
        "--keep-daily",
        "14",
        "--keep-weekly",
        "8",
        "--keep-monthly",
        "12",
        "--prune",
    )


def dump_snapshot(snapshot_id: str, target: Path) -> None:
    executable = shutil.which("restic")
    if executable is None:
        raise RuntimeError("Install the Restic command-line client on the host first.")
    arguments = [executable, "dump", snapshot_id, ARCHIVE_NAME]
    process = subprocess.Popen(arguments, stdout=subprocess.PIPE)
    if process.stdout is None:
        process.kill()
        process.wait()
        raise RuntimeError("Could not open the Restic restore stream.")

    try:
        with process.stdout as stream:
            with tarfile.open(fileobj=stream, mode="r|") as archive:
                archive.extractall(path=target, filter="data")
        return_code = process.wait()
        if return_code:
            raise subprocess.CalledProcessError(return_code, arguments)
    except BaseException:
        if process.poll() is None:
            process.kill()
        process.wait()
        raise


def validate_restored_media(database: Path, photos: Path) -> None:
    """Ensure each database photo reference resolves inside the restored media tree."""

    database_uri = f"file:{quote(database.as_posix(), safe='/')}?mode=ro"
    with sqlite3.connect(database_uri, uri=True) as db:
        photo_paths = [row[0] for row in db.execute(
            "SELECT photo_path FROM items WHERE photo_path IS NOT NULL"
        )]

    media_root = photos.resolve(strict=True)
    for photo_path in photo_paths:
        reference = Path(photo_path)
        if reference.parent.name != "photos" or reference.name in {"", ".", ".."}:
            raise RuntimeError("The restored database contains an invalid photo reference.")
        candidate = media_root / reference.name
        try:
            resolved = candidate.resolve(strict=True)
        except FileNotFoundError as exc:
            raise RuntimeError("The backup is missing a photo referenced by its database.") from exc
        if resolved.parent != media_root or not resolved.is_file():
            raise RuntimeError("A restored photo reference escapes the photo directory.")


def stream_archive(database_snapshot: Path, photos: Path) -> None:
    if not database_snapshot.is_file() or not photos.is_dir():
        raise RuntimeError("The backup stream source is missing its database snapshot or photos.")
    with tarfile.open(fileobj=sys.stdout.buffer, mode="w|") as archive:
        archive.add(database_snapshot, arcname="data/hjk_sell.db")
        archive.add(photos, arcname="data/photos")


def restore_snapshot(snapshot_id: str, target: Path) -> None:
    data_root, _ = environment()
    if not SNAPSHOT_ID_RE.fullmatch(snapshot_id):
        raise ValueError("Use a Restic snapshot ID containing only hexadecimal characters.")
    if not target.is_absolute() or not target.is_dir() or any(target.iterdir()):
        raise ValueError("Restore target must be an existing, empty absolute directory.")
    resolved_target = target.resolve(strict=True)
    if resolved_target == data_root or resolved_target in data_root.parents or data_root in resolved_target.parents:
        raise ValueError("Restore target must be completely separate from production data.")

    dump_snapshot(snapshot_id, resolved_target)

    restored_database = resolved_target / "data" / "hjk_sell.db"
    restored_photos = resolved_target / "data" / "photos"
    if not restored_database.is_file() or not restored_photos.is_dir():
        raise RuntimeError("The restored backup is missing the database or photo directory.")
    with sqlite3.connect(f"file:{quote(restored_database.as_posix(), safe='/')}?mode=ro", uri=True) as db:
        result = db.execute("PRAGMA integrity_check").fetchone()
    if result is None or result[0] != "ok":
        raise RuntimeError("The restored database failed its integrity check.")
    validate_restored_media(restored_database, restored_photos)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("init", "backup", "stream", "list", "restore"))
    parser.add_argument("snapshot_id", nargs="?")
    parser.add_argument("--target", type=Path)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--photos", type=Path)
    args = parser.parse_args()

    if args.action == "init":
        initialize_repository()
    elif args.action == "backup":
        create_backup()
    elif args.action == "stream":
        if args.database is None or args.photos is None:
            parser.error("stream requires --database and --photos")
        stream_archive(args.database, args.photos)
    elif args.action == "list":
        list_snapshots()
    else:
        if not args.snapshot_id or args.target is None:
            parser.error("restore requires SNAPSHOT_ID and --target pointing to an empty directory")
        restore_snapshot(args.snapshot_id, args.target)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"HJKsell backup failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
