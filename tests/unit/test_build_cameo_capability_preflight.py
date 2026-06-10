from __future__ import annotations

import json
from pathlib import Path

from tools import build_cameo_capability_preflight as mod


def test_build_cameo_capability_preflight_tool_writes_outputs(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path
    (root / "api").mkdir()
    (root / "api" / "main.py").write_text("from api import cameo\napp.include_router(cameo.router)\n", encoding="utf-8")
    (root / "api" / "cameo.py").write_text(
        'router = APIRouter(prefix="/cameo")\n@router.post("/targets")\ndef f(): pass\n@router.get("/operations")\ndef g(): pass\n@router.get("/architecture-validation")\ndef a(): pass\n@router.get("/official-results")\ndef h(): pass\n@router.get("/registration-approval")\ndef i(): pass\n@router.get("/api-contract")\ndef j(): pass\n@router.get("/service-boundary")\ndef k(): pass\n',
        encoding="utf-8",
    )
    (root / "betelgeuze_cameo").mkdir()
    (root / "betelgeuze_cameo" / "intake.py").write_text("# intake\n", encoding="utf-8")
    (root / "betelgeuze_cameo" / "cli.py").write_text("# cli\n", encoding="utf-8")
    validation_json = root / "validation.json"
    repair_json = root / "repair.json"
    out_json = root / "capability.json"
    out_csv = root / "capability.csv"
    out_md = root / "capability.md"
    validation_json.write_text(json.dumps({"summary": {"status": "blocked_cameo_validation_readiness"}}) + "\n", encoding="utf-8")
    repair_json.write_text(json.dumps({"summary": {"status": "blocked_cameo_repair_execution_preflight"}}) + "\n", encoding="utf-8")
    monkeypatch.setattr(mod, "ROOT", root)

    mod.main(
        [
            "--validation-json",
            str(validation_json),
            "--repair-preflight-json",
            str(repair_json),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    summary = json.loads(out_json.read_text(encoding="utf-8"))["summary"]
    assert summary["status"] == "cameo_development_capability_preflight_ready"
    assert summary["api_operations_route_registered"] is True
    assert summary["local_status_cli_present"] is True
    assert summary["public_registration_allowed"] is False
    assert out_csv.read_text(encoding="utf-8").startswith("check,status,")
    assert "CAMEO Capability Preflight" in out_md.read_text(encoding="utf-8")


def test_build_cameo_capability_preflight_blocks_registration_request(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path
    (root / "api").mkdir()
    (root / "api" / "main.py").write_text("from api import cameo\napp.include_router(cameo.router)\n", encoding="utf-8")
    (root / "api" / "cameo.py").write_text(
        'router = APIRouter(prefix="/cameo")\n@router.get("/targets")\ndef f(): pass\n@router.get("/operations")\ndef g(): pass\n@router.get("/architecture-validation")\ndef a(): pass\n@router.get("/official-results")\ndef h(): pass\n@router.get("/registration-approval")\ndef i(): pass\n@router.get("/api-contract")\ndef j(): pass\n@router.get("/service-boundary")\ndef k(): pass\n',
        encoding="utf-8",
    )
    (root / "betelgeuze_cameo").mkdir()
    (root / "betelgeuze_cameo" / "intake.py").write_text("# intake\n", encoding="utf-8")
    (root / "betelgeuze_cameo" / "cli.py").write_text("# cli\n", encoding="utf-8")
    validation_json = root / "validation.json"
    repair_json = root / "repair.json"
    out_json = root / "capability.json"
    validation_json.write_text(json.dumps({"summary": {"status": "blocked_cameo_validation_readiness"}}) + "\n", encoding="utf-8")
    repair_json.write_text(json.dumps({"summary": {"status": "blocked_cameo_repair_execution_preflight"}}) + "\n", encoding="utf-8")
    monkeypatch.setattr(mod, "ROOT", root)

    mod.main(
        [
            "--validation-json",
            str(validation_json),
            "--repair-preflight-json",
            str(repair_json),
            "--public-registration-requested",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(root / "capability.csv"),
            "--out-md",
            str(root / "capability.md"),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "blocked_cameo_capability_preflight"


def test_build_cameo_capability_preflight_blocks_missing_architecture_validation_route(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path
    (root / "api").mkdir()
    (root / "api" / "main.py").write_text("from api import cameo\napp.include_router(cameo.router)\n", encoding="utf-8")
    (root / "api" / "cameo.py").write_text(
        'router = APIRouter(prefix="/cameo")\n@router.post("/targets")\ndef f(): pass\n@router.get("/operations")\ndef g(): pass\n@router.get("/official-results")\ndef h(): pass\n@router.get("/registration-approval")\ndef i(): pass\n',
        encoding="utf-8",
    )
    (root / "betelgeuze_cameo").mkdir()
    (root / "betelgeuze_cameo" / "intake.py").write_text("# intake\n", encoding="utf-8")
    (root / "betelgeuze_cameo" / "cli.py").write_text("# cli\n", encoding="utf-8")
    validation_json = root / "validation.json"
    repair_json = root / "repair.json"
    out_json = root / "capability.json"
    validation_json.write_text(json.dumps({"summary": {"status": "blocked_cameo_validation_readiness"}}) + "\n", encoding="utf-8")
    repair_json.write_text(json.dumps({"summary": {"status": "blocked_cameo_repair_execution_preflight"}}) + "\n", encoding="utf-8")
    monkeypatch.setattr(mod, "ROOT", root)

    mod.main(
        [
            "--repo-root",
            str(root),
            "--validation-json",
            str(validation_json),
            "--repair-preflight-json",
            str(repair_json),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(root / "capability.csv"),
            "--out-md",
            str(root / "capability.md"),
        ]
    )

    summary = json.loads(out_json.read_text(encoding="utf-8"))["summary"]
    assert summary["status"] == "blocked_cameo_capability_preflight"
    assert summary["api_operations_route_registered"] is False
