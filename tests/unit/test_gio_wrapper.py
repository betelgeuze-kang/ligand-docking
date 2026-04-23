from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from tools.gio_wrapper import normalized_target


def test_gio_wrapper_decodes_existing_percent_encoded_local_path(tmp_path: Path) -> None:
    target = tmp_path / "경로 테스트"
    target.mkdir()
    encoded = str(target.parent / quote(target.name, safe=""))
    assert normalized_target(encoded) == str(target)


def test_gio_wrapper_decodes_existing_file_uri_without_query(tmp_path: Path) -> None:
    target = tmp_path / "한글"
    target.mkdir()
    encoded_uri = f"file://{quote(str(target), safe='/')}"
    assert normalized_target(encoded_uri) == str(target)


def test_gio_wrapper_keeps_non_file_url() -> None:
    raw = "https://example.com/%ED%95%9C%EA%B8%80"
    assert normalized_target(raw) == raw
