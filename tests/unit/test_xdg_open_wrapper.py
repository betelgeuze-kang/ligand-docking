from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from tools.xdg_open_wrapper import normalized_target


def test_normalized_target_decodes_existing_percent_encoded_local_path(tmp_path: Path) -> None:
    target = tmp_path / "한글 폴더"
    target.mkdir()
    encoded = str(target.parent / quote(target.name, safe=""))
    assert normalized_target(encoded) == str(target)


def test_normalized_target_decodes_existing_file_uri_without_query(tmp_path: Path) -> None:
    target = tmp_path / "분자동역학"
    target.mkdir()
    encoded_uri = f"file://{quote(str(target), safe='/')}"
    assert normalized_target(encoded_uri) == str(target)


def test_normalized_target_keeps_file_uri_with_query() -> None:
    raw = "file:///tmp/viewer.html?source=row_provenance_csv&row=1"
    assert normalized_target(raw) == raw


def test_normalized_target_keeps_http_url() -> None:
    raw = "https://example.com/a%20b"
    assert normalized_target(raw) == raw
