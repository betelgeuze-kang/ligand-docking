from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_product_operational_gate_repair_work_order as mod


def _blocked_preflight() -> dict:
    return {
        "summary": {
            "status": "blocked_product_execution_preflight",
            "target_id": "ADRB2",
            "family": "gpcr",
            "blocker_count": 3,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
        },
        "blockers": [
            {
                "code": "operational_gate_eval_unique_keys_impossible",
                "severity": "hard",
                "reason": "Operational gate requires at least 200 eval unique keys, but the configured split has 29.",
            },
            {
                "code": "operational_gate_ef1_threshold_impossible",
                "severity": "hard",
                "reason": "Operational gate requires EF1 >= 1.2, but eval prevalence caps max possible EF1 at 1.11538.",
            },
            {
                "code": "planned_artifact_already_present",
                "severity": "hard",
                "reason": "Planned post-execution artifact already exists and could be stale.",
            },
        ],
        "operational_gate_feasibility_checks": [
            {
                "check": "operational_gate_feasibility",
                "status": "fail",
                "eval_unique_keys": 29,
                "eval_positive_keys": 26,
                "ef1_max_possible": 1.1153846153846154,
                "gate_min_eval_unique_keys": 200,
                "gate_ef1_min": 1.2,
            }
        ],
    }


def test_product_operational_gate_repair_work_order_computes_eval_deficits() -> None:
    payload = mod.build_product_operational_gate_repair_work_order(
        preflight_packet=_blocked_preflight(),
        preflight_path="runs/product_execution_preflight_current.json",
    )
    summary = payload["summary"]

    assert summary["status"] == "product_operational_gate_repair_work_order_ready"
    assert summary["repair_required"] is True
    assert summary["current_eval_unique_keys"] == 29
    assert summary["current_eval_positive_keys"] == 26
    assert summary["current_eval_negative_keys"] == 3
    assert summary["additional_eval_unique_keys_needed"] == 171
    assert summary["max_positive_keys_at_gate_min"] == 166
    assert summary["required_negative_keys_at_gate_min"] == 34
    assert summary["additional_negative_keys_needed"] == 31
    assert summary["pure_negative_additions_needed"] == 171
    assert summary["active_only_expansion_can_satisfy_gate"] is False
    assert summary["execution_enabled"] is False
    assert summary["docking_results_emitted"] is False
    assert summary["external_state_mutated"] is False

    by_item = {row["repair_item"]: row for row in payload["rows"]}
    assert by_item["eval_panel_size_deficit"]["status"] == "repair_required"
    assert by_item["eval_negative_decoy_deficit"]["status"] == "repair_required"
    assert "additional_negative_keys_needed=31" in by_item["eval_negative_decoy_deficit"]["required"]
    assert by_item["active_only_expansion_guard"]["status"] == "blocked"
    assert by_item["stale_planned_artifact_guard"]["status"] == "repair_required"


def test_product_operational_gate_repair_work_order_not_required_when_gate_passes() -> None:
    preflight = _blocked_preflight()
    preflight["summary"]["status"] = "product_execution_preflight_ready"
    preflight["summary"]["blocker_count"] = 0
    preflight["blockers"] = []
    preflight["operational_gate_feasibility_checks"][0].update(
        {
            "status": "pass",
            "eval_unique_keys": 240,
            "eval_positive_keys": 40,
            "ef1_max_possible": 6.0,
        }
    )

    payload = mod.build_product_operational_gate_repair_work_order(preflight_packet=preflight)

    assert payload["summary"]["status"] == "product_operational_gate_repair_not_required"
    assert payload["summary"]["repair_required"] is False
    assert payload["rows"][0]["repair_item"] == "operational_gate_feasibility"
    assert payload["rows"][0]["status"] == "ready"


def test_product_operational_gate_repair_work_order_tool_writes_outputs(tmp_path: Path) -> None:
    preflight_json = tmp_path / "preflight.json"
    out_json = tmp_path / "repair.json"
    out_csv = tmp_path / "repair.csv"
    out_md = tmp_path / "repair.md"
    preflight_json.write_text(json.dumps(_blocked_preflight()) + "\n", encoding="utf-8")

    mod.main(
        [
            "--preflight-json",
            str(preflight_json),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["additional_eval_unique_keys_needed"] == 171
    assert out_csv.read_text(encoding="utf-8").startswith("sequence,repair_item,")
    assert "Product Operational Gate Repair Work Order" in out_md.read_text(encoding="utf-8")
