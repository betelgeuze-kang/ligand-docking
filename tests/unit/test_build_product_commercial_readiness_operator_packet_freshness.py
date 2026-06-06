from __future__ import annotations

import json
from pathlib import Path

from tools import build_product_commercial_readiness_operator_packet as packet_mod
from tools.product import build_product_commercial_readiness_operator_packet_freshness as mod


def _goal_audit(action_id: str = "production_ai_return_summary") -> dict:
    return {
        "summary": {
            "goal_complete": False,
            "commercial_readiness_next_action_matrix": [
                {
                    "action_id": action_id,
                    "status": "blocked",
                    "gap_id": "production_ai_inference_checkpoint",
                    "release_blocker": True,
                    "artifact": "runs/residual_force_trajectory_regeneration_current_summary.json",
                    "required_operator_inputs": ["queue_rows"],
                    "operator_completion_packet_ready": True,
                    "operator_completion_packet": {"artifact_id": "returned_summary_json"},
                    "next_action": "Return the completed GPU summary JSON.",
                    "execution_command": "python3 tools/generate_ligand_trajectory_engine.py --prod-mode",
                    "validation_command": "python3 tools/build_residual_force_gpu_worker_return_receipt.py",
                }
            ],
        }
    }


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_product_commercial_readiness_operator_packet_freshness_passes_when_fingerprints_match(tmp_path: Path) -> None:
    goal_path = tmp_path / "goal.json"
    operator_path = tmp_path / "operator.json"
    goal = _goal_audit()
    _write_json(goal_path, goal)
    operator = packet_mod.build_product_commercial_readiness_operator_packet(
        goal_audit_packet=goal,
        goal_audit_path=str(goal_path),
    )
    _write_json(operator_path, operator)

    payload = mod.build_product_commercial_readiness_operator_packet_freshness(
        goal_audit_packet=goal,
        operator_packet=operator,
        goal_audit_path=str(goal_path),
        operator_packet_path=str(operator_path),
    )

    summary = payload["summary"]
    assert summary["status"] == "product_commercial_readiness_operator_packet_freshness_ready"
    assert summary["freshness_ready"] is True
    assert summary["fail_count"] == 0
    assert summary["current_goal_audit_sha256"] == summary["operator_goal_audit_sha256"]
    assert summary["current_commercial_readiness_matrix_sha256"] == (
        summary["operator_commercial_readiness_matrix_sha256"]
    )
    assert summary["current_first_action_id"] == "production_ai_return_summary"
    assert summary["command_references_ready"] is True
    assert summary["operator_python_tool_reference_count"] >= 2
    assert summary["operator_missing_python_tool_reference_count"] == 0
    assert "tools/build_residual_force_gpu_worker_return_receipt.py" in summary[
        "operator_python_tool_references"
    ]
    assert all(row["status"] == "pass" for row in payload["rows"])
    assert summary["execution_enabled"] is False
    assert summary["checkpoint_promoted"] is False


def test_product_commercial_readiness_operator_packet_freshness_blocks_stale_matrix(tmp_path: Path) -> None:
    goal_path = tmp_path / "goal.json"
    original_goal = _goal_audit()
    _write_json(goal_path, original_goal)
    operator = packet_mod.build_product_commercial_readiness_operator_packet(
        goal_audit_packet=original_goal,
        goal_audit_path=str(goal_path),
    )
    stale_goal = _goal_audit("transporter_next_slot_exact_evidence")
    _write_json(goal_path, stale_goal)

    payload = mod.build_product_commercial_readiness_operator_packet_freshness(
        goal_audit_packet=stale_goal,
        operator_packet=operator,
        goal_audit_path=str(goal_path),
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_product_commercial_readiness_operator_packet_freshness"
    assert summary["freshness_ready"] is False
    assert "goal_audit_sha256_matches" in summary["failed_check_ids"]
    assert "commercial_readiness_matrix_sha256_matches" in summary["failed_check_ids"]
    assert "first_action_id_matches" in summary["failed_check_ids"]
    assert summary["current_first_action_id"] == "transporter_next_slot_exact_evidence"
    assert summary["operator_first_action_id"] == "production_ai_return_summary"


def test_product_commercial_readiness_operator_packet_freshness_blocks_missing_tool_reference(
    tmp_path: Path,
) -> None:
    goal_path = tmp_path / "goal.json"
    operator_path = tmp_path / "operator.json"
    goal = _goal_audit()
    _write_json(goal_path, goal)
    operator = packet_mod.build_product_commercial_readiness_operator_packet(
        goal_audit_packet=goal,
        goal_audit_path=str(goal_path),
    )
    operator["rows"][0]["validation_command"] = "python3 tools/build_missing_operator_step.py"
    _write_json(operator_path, operator)

    payload = mod.build_product_commercial_readiness_operator_packet_freshness(
        goal_audit_packet=goal,
        operator_packet=operator,
        goal_audit_path=str(goal_path),
        operator_packet_path=str(operator_path),
    )

    summary = payload["summary"]
    assert summary["freshness_ready"] is False
    assert summary["command_references_ready"] is False
    assert "operator_python_tool_references_exist" in summary["failed_check_ids"]
    assert summary["operator_missing_python_tool_references"] == [
        "tools/build_missing_operator_step.py"
    ]


def test_product_commercial_readiness_operator_packet_freshness_tool_writes_outputs(tmp_path: Path) -> None:
    goal_path = tmp_path / "goal.json"
    operator_path = tmp_path / "operator.json"
    out_json = tmp_path / "freshness.json"
    out_csv = tmp_path / "freshness.csv"
    out_md = tmp_path / "freshness.md"
    goal = _goal_audit()
    _write_json(goal_path, goal)
    operator = packet_mod.build_product_commercial_readiness_operator_packet(
        goal_audit_packet=goal,
        goal_audit_path=str(goal_path),
    )
    _write_json(operator_path, operator)

    mod.main(
        [
            "--goal-audit-json",
            str(goal_path),
            "--operator-packet-json",
            str(operator_path),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["freshness_ready"] is True
    assert payload["summary"]["command_references_ready"] is True
    assert out_csv.read_text(encoding="utf-8").startswith("check_id,status,")
    md_text = out_md.read_text(encoding="utf-8")
    assert "Product Commercial Readiness Operator Packet Freshness" in md_text
    assert "goal_audit_sha256_matches" in md_text
    assert "command_references_ready" in md_text
