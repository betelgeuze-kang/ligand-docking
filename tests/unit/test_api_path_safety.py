from __future__ import annotations

from pathlib import Path

import pytest

from api.path_safety import PathSafetyError, resolve_existing_file_under, resolve_under_root


def test_resolve_existing_file_under_accepts_root_child(tmp_path: Path) -> None:
    root = tmp_path / "job"
    root.mkdir()
    artifact = root / "result.json"
    artifact.write_text("{}", encoding="utf-8")

    assert resolve_existing_file_under(root, "result.json") == artifact.resolve()
    assert resolve_existing_file_under(root, artifact) == artifact.resolve()


def test_resolve_under_root_rejects_parent_escape(tmp_path: Path) -> None:
    root = tmp_path / "job"
    root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")

    with pytest.raises(PathSafetyError):
        resolve_existing_file_under(root, outside)

    with pytest.raises(PathSafetyError):
        resolve_under_root(root, "../outside.json")


def test_resolve_existing_file_under_requires_file(tmp_path: Path) -> None:
    root = tmp_path / "job"
    root.mkdir()

    with pytest.raises(FileNotFoundError):
        resolve_existing_file_under(root, "missing.json")
