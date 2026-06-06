from __future__ import annotations

import json
from pathlib import Path

from tools.cameo import build_cameo_validation_repair_work_order as mod


def _readiness(status: str = "blocked_cameo_validation_readiness") -> dict:
    return {
        "summary": {
            "status": status,
            "target_id": "CAMEO100",
            "blocker_count": 4,
            "external_state_mutated": False,
        },
        "blockers": [
            {"code": "selection_artifact_missing", "stage": "selection"},
            {"code": "format_artifact_missing", "stage": "format"},
            {"code": "handoff_artifact_missing", "stage": "handoff"},
            {"code": "performance_artifact_missing", "stage": "performance"},
        ],
        "rows": [
            {"stage": "selection", "ready": False},
            {"stage": "format", "ready": False},
            {"stage": "handoff", "ready": False},
            {"stage": "performance", "ready": False},
        ],
    }


def test_cameo_validation_repair_work_order_requires_operator_inputs_for_missing_sources() -> None:
    payload = mod.build_work_order(_readiness(), readiness_json="readiness.json")
    summary = payload["summary"]

    assert summary["status"] == "operator_input_required"
    assert summary["operator_input_missing"] == ["candidates_csv", "models_csv"]
    assert summary["action_executed"] is False
    assert summary["outbound_email_enabled"] is False
    assert summary["external_state_mutated"] is False
    assert payload["rows"][0]["command"].startswith("python3 tools/build_cameo_model1_selection_packet.py")


def test_cameo_validation_repair_work_order_ready_with_operator_inputs() -> None:
    payload = mod.build_work_order(
        _readiness(),
        candidates_csv="runs/cameo_candidates.csv",
        models_csv="runs/cameo_models.csv",
        official_results_csv="runs/cameo_official_results.csv",
        target_id="CAMEO100",
    )
    commands = {row["step"]: row["command"] for row in payload["rows"]}

    assert payload["summary"]["status"] == "cameo_validation_repair_work_order_ready"
    assert payload["summary"]["operator_input_missing_count"] == 0
    assert "--target-id CAMEO100" in commands["selection"]
    assert "--models-csv runs/cameo_models.csv" in commands["format"]
    assert "--results-csv runs/cameo_official_results.csv" in commands["performance"]


def test_cameo_validation_repair_work_order_not_required_when_ready() -> None:
    payload = mod.build_work_order({"summary": {"status": "cameo_validation_evidence_ready"}})

    assert payload["summary"]["status"] == "cameo_validation_repair_not_required"
    assert payload["summary"]["blocked_stage_count"] == 0


def test_cameo_validation_repair_work_order_tool_writes_outputs(tmp_path: Path) -> None:
    readiness_json = tmp_path / "readiness.json"
    out_json = tmp_path / "work_order.json"
    out_csv = tmp_path / "work_order.csv"
    out_md = tmp_path / "work_order.md"
    readiness_json.write_text(json.dumps(_readiness()) + "\n", encoding="utf-8")

    mod.main(
        [
            "--readiness-json",
            str(readiness_json),
            "--candidates-csv",
            "runs/cameo_candidates.csv",
            "--models-csv",
            "runs/cameo_models.csv",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "cameo_validation_repair_work_order_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("step,needed_now,")
    assert "CAMEO Validation Repair Work Order" in out_md.read_text(encoding="utf-8")
