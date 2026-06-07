from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.product.fetch_public_benchmark_native_structure import fetch_native


class _FakeResponse:
    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def read(self) -> bytes:
        return b"ATOM      1  CA  GLY A   1       0.0   0.0   0.0  1.00 10.00           C\n"


def _args(tmp_path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        suite_id="dude_z_decoy_smoke",
        target="AA2AR",
        pdb_id="3EML",
        source_url="https://files.rcsb.org/download/3EML.pdb",
        out_pdb=str(tmp_path / "aa2ar.pdb"),
        out_json=str(tmp_path / "fetch.json"),
        out_md=str(tmp_path / "fetch.md"),
        timeout_seconds=3,
        overwrite=False,
    )


def test_fetch_public_benchmark_native_structure_blocks_without_token(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD", raising=False)

    payload = fetch_native(_args(tmp_path))

    assert payload["summary"]["status"] == "blocked_public_benchmark_native_structure_fetch"
    assert "approval_token_missing" in payload["summary"]["blockers"]
    assert payload["summary"]["download_executed"] is False
    assert not (tmp_path / "aa2ar.pdb").exists()


def test_fetch_public_benchmark_native_structure_downloads_with_token(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD", "1")
    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: _FakeResponse())

    payload = fetch_native(_args(tmp_path))

    assert payload["summary"]["status"] == "public_benchmark_native_structure_ready"
    assert payload["summary"]["download_executed"] is True
    assert payload["summary"]["out_pdb_present"] is True
    assert json.loads((tmp_path / "fetch.json").read_text(encoding="utf-8"))["summary"]["pdb_id"] == "3EML"
