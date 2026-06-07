from __future__ import annotations

import json
from pathlib import Path

from tools.cameo import build_cameo_operator_input_kit as mod


def _repair_work_order(status: str = "operator_input_required") -> dict:
    return {
        "summary": {
            "status": status,
            "target_id": "CAMEO100",
            "blocked_stages": ["selection", "format", "handoff", "performance"],
            "operator_input_missing_count": 2,
            "operator_input_missing": ["candidates_csv", "models_csv"],
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
                "command": "python3 tools/build_cameo_model1_selection_packet.py --candidates-csv OPERATOR_FILL_CAMEO_CANDIDATES_CSV",
            },
            {
                "step": "format",
                "needed_now": True,
                "input_required": "models_csv",
                "command": "python3 tools/build_cameo_format_validation_packet.py --models-csv OPERATOR_FILL_CAMEO_SELECTED_MODELS_CSV",
            },
        ],
    }


def test_cameo_operator_input_kit_summarizes_required_templates(tmp_path: Path) -> None:
    payload = mod.build_input_kit(_repair_work_order(), out_dir=tmp_path / "kit")
    summary = payload["summary"]

    assert summary["status"] == "cameo_operator_input_kit_ready"
    assert summary["template_count"] == 3
    assert summary["required_template_count"] == 3
    assert summary["operator_input_missing"] == ["candidates_csv", "models_csv"]
    assert summary["action_executed"] is False
    assert summary["outbound_email_enabled"] is False
    assert summary["external_state_mutated"] is False
    assert summary["native_local_accuracy_used"] is False
    assert {row["template"] for row in payload["rows"]} == {
        "candidates_template.csv",
        "models_template.csv",
        "official_results_template.csv",
    }


def test_cameo_operator_input_kit_blocks_without_repair_work_order(tmp_path: Path) -> None:
    payload = mod.build_input_kit({}, out_dir=tmp_path / "kit")

    assert payload["summary"]["status"] == "blocked_cameo_operator_input_kit"
    assert payload["blockers"][0]["code"] == "repair_work_order_missing"
    assert payload["summary"]["action_executed"] is False


def test_cameo_operator_input_kit_tool_writes_templates(tmp_path: Path) -> None:
    repair_json = tmp_path / "repair.json"
    out_dir = tmp_path / "kit"
    repair_json.write_text(json.dumps(_repair_work_order()) + "\n", encoding="utf-8")

    mod.main(["--repair-work-order-json", str(repair_json), "--out-dir", str(out_dir)])

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["summary"]["status"] == "cameo_operator_input_kit_ready"
    assert (out_dir / "candidates_template.csv").read_text(encoding="utf-8").startswith("target_id,candidate_id,")
    assert "OPERATOR_FILL_INTERNAL_CANDIDATE_ID" in (out_dir / "candidates_template.csv").read_text(encoding="utf-8")
    assert "OPERATOR_FILL_1_TO_5_MODEL1_IS_1" in (out_dir / "models_template.csv").read_text(encoding="utf-8")
    assert "official_cameo" in (out_dir / "official_results_template.csv").read_text(encoding="utf-8")
    assert "CAMEO Operator Input Kit" in (out_dir / "README.md").read_text(encoding="utf-8")
    assert (out_dir / "manifest.csv").read_text(encoding="utf-8").startswith("template,path,")
