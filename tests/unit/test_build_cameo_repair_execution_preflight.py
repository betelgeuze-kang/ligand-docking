from __future__ import annotations

import json
from pathlib import Path

from tools import build_cameo_repair_execution_preflight as mod


def _repair() -> dict:
    return {
        "summary": {
            "status": "cameo_validation_repair_work_order_ready",
            "action_executed": False,
            "outbound_email_enabled": False,
            "external_state_mutated": False,
            "native_local_accuracy_used": False,
        },
        "rows": [
            {
                "step": "selection",
                "needed_now": True,
                "input_required": "candidates_csv",
                "input_value": "runs/candidates.csv",
                "command": "python3 tools/build_cameo_model1_selection_packet.py --candidates-csv runs/candidates.csv",
                "action_executed": False,
            }
        ],
    }


def _inputs() -> dict:
    return {
        "summary": {
            "status": "cameo_operator_inputs_ready_pending_official_results",
            "blocker_count": 0,
            "action_executed": False,
            "outbound_email_enabled": False,
            "external_state_mutated": False,
            "native_local_accuracy_used": False,
        }
    }


def test_build_cameo_repair_execution_preflight_tool_writes_outputs(tmp_path: Path) -> None:
    repair_json = tmp_path / "repair.json"
    input_json = tmp_path / "input_validation.json"
    out_json = tmp_path / "preflight.json"
    out_csv = tmp_path / "preflight.csv"
    out_md = tmp_path / "preflight.md"
    repair_json.write_text(json.dumps(_repair()) + "\n", encoding="utf-8")
    input_json.write_text(json.dumps(_inputs()) + "\n", encoding="utf-8")

    mod.main(
        [
            "--repair-json",
            str(repair_json),
            "--operator-input-validation-json",
            str(input_json),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "cameo_repair_execution_preflight_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("step,needed_now,")
    assert "CAMEO Repair Execution Preflight" in out_md.read_text(encoding="utf-8")
