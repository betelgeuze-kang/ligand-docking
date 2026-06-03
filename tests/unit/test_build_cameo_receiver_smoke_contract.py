from __future__ import annotations

import json
from pathlib import Path

from tools import build_cameo_receiver_smoke_contract as mod


def _write_receiver_sources(root: Path) -> None:
    (root / "api").mkdir()
    (root / "api" / "main.py").write_text("from api import cameo\napp.include_router(cameo.router)\n", encoding="utf-8")
    (root / "api" / "cameo.py").write_text('router = APIRouter(prefix="/cameo")\n@router.get("/targets")\ndef f(): pass\n', encoding="utf-8")


def test_build_cameo_receiver_smoke_contract_tool_writes_outputs(tmp_path: Path) -> None:
    _write_receiver_sources(tmp_path)
    out_json = tmp_path / "receiver_smoke.json"
    out_csv = tmp_path / "receiver_smoke.csv"
    out_md = tmp_path / "receiver_smoke.md"

    mod.main(
        [
            "--root",
            str(tmp_path),
            "--api-dependency-json",
            str(tmp_path / "missing_api_dependency.json"),
            "--no-runtime-smoke",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    summary = json.loads(out_json.read_text(encoding="utf-8"))["summary"]
    assert summary["status"] == "cameo_receiver_static_smoke_ready"
    assert summary["source_route_present"] is True
    assert summary["runtime_smoke_requested"] is False
    assert out_csv.read_text(encoding="utf-8").startswith("check,status,")
    assert "CAMEO Receiver Smoke Contract" in out_md.read_text(encoding="utf-8")
