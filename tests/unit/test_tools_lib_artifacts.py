from __future__ import annotations

from pathlib import Path

from tools.lib import artifacts


def test_json_and_csv_helpers_roundtrip(tmp_path: Path) -> None:
    payload = {"summary": {"status": "ok"}, "path": tmp_path / "x.txt"}
    json_path = tmp_path / "packet.json"
    csv_path = tmp_path / "rows.csv"

    artifacts.write_json(json_path, payload)
    artifacts.write_csv(csv_path, [{"a": 1, "b": "two"}, {"a": 3, "c": "four"}])

    loaded = artifacts.read_json(json_path)
    rows = artifacts.read_csv(csv_path)
    assert loaded["summary"]["status"] == "ok"
    assert artifacts.summary(loaded) == {"status": "ok"}
    assert rows[0]["a"] == "1"
    assert rows[1]["c"] == "four"


def test_short_error_and_text_helpers() -> None:
    assert artifacts.text(None) == ""
    assert artifacts.truthy("yes") is True
    assert artifacts.truthy("no") is False
    assert artifacts.short_error(ValueError("x" * 20), limit=16).endswith("...")
