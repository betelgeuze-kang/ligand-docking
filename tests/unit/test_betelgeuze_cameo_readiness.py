from __future__ import annotations

import json
from pathlib import Path

from betelgeuze_cameo.readiness import build_cameo_validation_readiness_gate
from tools import build_cameo_validation_readiness_gate as tool


def _selection() -> dict:
    return {"summary": {"selection_status": "cameo_model1_selection_ready", "target_id": "CAMEO100", "native_or_external_accuracy_used": False}}


def _format() -> dict:
    return {"summary": {"status": "cameo_format_validation_ready", "target_id": "CAMEO100", "native_or_external_accuracy_used": False}}


def _handoff() -> dict:
    return {
        "summary": {
            "status": "cameo_handoff_dry_run_ready",
            "target_id": "CAMEO100",
            "native_or_external_accuracy_used": False,
            "outbound_email_enabled": False,
            "external_state_mutated": False,
        }
    }


def _performance(status: str = "cameo_performance_evidence_ready") -> dict:
    return {
        "summary": {
            "status": status,
            "target_id": "CAMEO100",
            "official_cameo_results_used": status == "cameo_performance_evidence_ready",
            "native_local_accuracy_used": False,
            "outbound_email_enabled": False,
            "external_state_mutated": False,
        }
    }


def test_cameo_validation_readiness_blocks_missing_artifacts() -> None:
    payload = build_cameo_validation_readiness_gate(
        selection_packet={},
        format_packet={},
        handoff_packet={},
        performance_packet={},
    )
    codes = {blocker["code"] for blocker in payload["blockers"]}

    assert payload["summary"]["status"] == "blocked_cameo_validation_readiness"
    assert payload["summary"]["missing_stage_count"] == 4
    assert "selection_artifact_missing" in codes
    assert "performance_artifact_missing" in codes


def test_cameo_validation_readiness_pending_official_results() -> None:
    payload = build_cameo_validation_readiness_gate(
        selection_packet=_selection(),
        format_packet=_format(),
        handoff_packet=_handoff(),
        performance_packet=_performance("cameo_performance_pending_official_results"),
    )

    assert payload["summary"]["status"] == "cameo_validation_pending_official_results"
    assert payload["summary"]["ready_stage_count"] == 4
    assert payload["blockers"] == []


def test_cameo_validation_readiness_evidence_ready() -> None:
    payload = build_cameo_validation_readiness_gate(
        selection_packet=_selection(),
        format_packet=_format(),
        handoff_packet=_handoff(),
        performance_packet=_performance(),
    )

    assert payload["summary"]["status"] == "cameo_validation_evidence_ready"
    assert payload["summary"]["official_cameo_results_used"] is True
    assert payload["summary"]["native_local_accuracy_used"] is False


def test_cameo_validation_readiness_blocks_claim_boundary_violation() -> None:
    selection = _selection()
    selection["summary"]["native_or_external_accuracy_used"] = True
    payload = build_cameo_validation_readiness_gate(
        selection_packet=selection,
        format_packet=_format(),
        handoff_packet=_handoff(),
        performance_packet=_performance(),
    )

    assert payload["summary"]["status"] == "blocked_cameo_validation_readiness"
    assert any(blocker["code"] == "selection_claim_boundary_invalid" for blocker in payload["blockers"])


def test_cameo_validation_readiness_tool_writes_outputs(tmp_path: Path) -> None:
    selection_json = tmp_path / "selection.json"
    format_json = tmp_path / "format.json"
    handoff_json = tmp_path / "handoff.json"
    performance_json = tmp_path / "performance.json"
    out_json = tmp_path / "readiness.json"
    out_csv = tmp_path / "readiness.csv"
    out_md = tmp_path / "readiness.md"
    selection_json.write_text(json.dumps(_selection()) + "\n", encoding="utf-8")
    format_json.write_text(json.dumps(_format()) + "\n", encoding="utf-8")
    handoff_json.write_text(json.dumps(_handoff()) + "\n", encoding="utf-8")
    performance_json.write_text(json.dumps(_performance()) + "\n", encoding="utf-8")

    tool.main(
        [
            "--selection-json",
            str(selection_json),
            "--format-json",
            str(format_json),
            "--handoff-json",
            str(handoff_json),
            "--performance-json",
            str(performance_json),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "cameo_validation_evidence_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("stage,path,")
    assert "CAMEO Validation Readiness Gate" in out_md.read_text(encoding="utf-8")
