from __future__ import annotations

import json
from pathlib import Path

from tools import build_casp17_transition_surface_contract as mod


def _write_api_surface(root: Path, *, include_router: bool = True) -> None:
    (root / "api").mkdir()
    (root / "api" / "casp17.py").write_text(
        '@router.get("/upload")\n'
        '@router.get("/transition")\n'
        'decision = "casp17_current_upload_decision_rule_gate_current.json"\n'
        'runway = "casp17_current_upload_operator_action_runway_current.json"\n'
        'lock = "casp17_current_upload_active_manifest_lock_current.json"\n'
        'large = "large_cleanup_surface_drilldown_current.json"\n'
        'protected = "protected_cleanup_payload_review_current.json"\n'
        'approval = "cleanup_execution_approval_gate_current.json"\n'
        'postcheck = "cleanup_postcheck_contract_current.json"\n'
        'completion = "cleanup_completion_gate_current.json"\n'
        'upload_executed = False\n'
        'delete_executed = False\n'
        'native_accuracy_computed = False\n'
        'external_state_mutated = False\n',
        encoding="utf-8",
    )
    (root / "api" / "main.py").write_text(
        "from api.casp17 import router as casp17_router\napp.include_router(casp17_router)\n" if include_router else "",
        encoding="utf-8",
    )


def test_casp17_transition_surface_contract_ready(tmp_path: Path) -> None:
    _write_api_surface(tmp_path)

    payload = mod.build_casp17_transition_surface_contract(root=tmp_path)

    summary = payload["summary"]
    assert summary["status"] == "casp17_transition_surface_contract_ready"
    assert summary["surface_ready"] is True
    assert summary["casp17_upload_endpoint_present"] is True
    assert summary["casp17_transition_endpoint_present"] is True
    assert summary["casp17_upload_artifacts_referenced"] is True
    assert summary["casp17_cleanup_artifacts_referenced"] is True
    assert summary["casp17_cleanup_gate_artifacts_referenced"] is True
    assert summary["upload_executed"] is False
    assert summary["delete_executed"] is False
    assert summary["native_accuracy_computed"] is False
    assert summary["external_state_mutated"] is False
    assert payload["blockers"] == []


def test_casp17_transition_surface_contract_blocks_unmounted_router(tmp_path: Path) -> None:
    _write_api_surface(tmp_path, include_router=False)

    payload = mod.build_casp17_transition_surface_contract(root=tmp_path)

    assert payload["summary"]["status"] == "blocked_casp17_transition_surface_contract"
    assert payload["summary"]["casp17_router_registered"] is False
    assert any(blocker["code"] == "casp17_router_registered_not_ready" for blocker in payload["blockers"])


def test_casp17_transition_surface_contract_tool_writes_outputs(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _write_api_surface(root)
    out_json = tmp_path / "surface.json"
    out_csv = tmp_path / "surface.csv"
    out_md = tmp_path / "surface.md"

    mod.main(["--root", str(root), "--out-json", str(out_json), "--out-csv", str(out_csv), "--out-md", str(out_md)])

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "casp17_transition_surface_contract_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("check,status,")
    assert "CASP17 Transition Surface Contract" in out_md.read_text(encoding="utf-8")
