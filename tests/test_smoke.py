"""Smoke tests for the stage-one application shell."""

from __future__ import annotations

from pathlib import Path

from hjksell.config import get_app_paths


def test_app_paths_are_under_local_app_data(monkeypatch) -> None:
    local_app_data = Path("C:/Users/Test/AppData/Local")
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))

    paths = get_app_paths()

    assert paths.root == local_app_data / "HJKsell"
    assert paths.database == paths.data / "hjk_sell.db"
    assert paths.photos == paths.data / "photos"
    assert paths.log_file == paths.logs / "app.log"
