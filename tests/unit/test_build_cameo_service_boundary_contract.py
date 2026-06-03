from __future__ import annotations

import json
from pathlib import Path

from tests.unit.test_betelgeuze_cameo_service_boundary import _root
from tools import build_cameo_service_boundary_contract as mod


def test_build_cameo_service_boundary_contract_tool_writes_outputs(tmp_path: Path) -> None:
    root = _root(tmp_path / "repo")
    out_json = tmp_path / "service_boundary.json"
    out_csv = tmp_path / "service_boundary.csv"
    out_md = tmp_path / "service_boundary.md"

    mod.main(
        [
            "--root",
            str(root),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "cameo_service_boundary_contract_ready"
    assert payload["summary"]["service_boundary_ready"] is True
    assert payload["summary"]["server_started"] is False
    assert payload["summary"]["external_state_mutated"] is False
    assert out_csv.read_text(encoding="utf-8").startswith("check,status,")
    assert "CAMEO Service Boundary Contract" in out_md.read_text(encoding="utf-8")
