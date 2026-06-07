from __future__ import annotations

from betelgeuze_cameo.repair_preflight import build_repair_execution_preflight


def _repair(status: str = "cameo_validation_repair_work_order_ready", candidates_csv: str = "runs/candidates.csv", models_csv: str = "runs/models.csv") -> dict:
    return {
        "summary": {
            "status": status,
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
                "input_value": candidates_csv,
                "command": f"python3 tools/build_cameo_model1_selection_packet.py --candidates-csv {candidates_csv}",
                "action_executed": False,
            },
            {
                "step": "format",
                "needed_now": True,
                "input_required": "models_csv",
                "input_value": models_csv,
                "command": f"python3 tools/build_cameo_format_validation_packet.py --models-csv {models_csv}",
                "action_executed": False,
            },
            {
                "step": "handoff",
                "needed_now": True,
                "input_required": "",
                "input_value": "",
                "command": "python3 tools/build_cameo_dry_run_handoff_packet.py",
                "action_executed": False,
            },
            {
                "step": "performance",
                "needed_now": True,
                "input_required": "official_results_csv_optional",
                "input_value": "",
                "command": "python3 tools/build_cameo_performance_scorecard.py",
                "action_executed": False,
            },
            {
                "step": "readiness_refresh",
                "needed_now": True,
                "input_required": "",
                "input_value": "",
                "command": "python3 tools/build_cameo_validation_readiness_gate.py",
                "action_executed": False,
            },
        ],
    }


def _inputs(status: str = "cameo_operator_inputs_ready_pending_official_results", blocker_count: int = 0) -> dict:
    return {
        "summary": {
            "status": status,
            "blocker_count": blocker_count,
            "action_executed": False,
            "outbound_email_enabled": False,
            "external_state_mutated": False,
            "native_local_accuracy_used": False,
        }
    }


def test_cameo_repair_execution_preflight_ready_for_checked_inputs() -> None:
    payload = build_repair_execution_preflight(_repair(), _inputs())

    assert payload["summary"]["status"] == "cameo_repair_execution_preflight_ready"
    assert payload["summary"]["action_executed"] is False
    assert payload["summary"]["outbound_email_enabled"] is False
    assert payload["summary"]["external_state_mutated"] is False
    assert all(row["preflight_status"] == "pass" for row in payload["rows"])


def test_cameo_repair_execution_preflight_allows_not_required_work_order() -> None:
    payload = build_repair_execution_preflight(_repair(status="cameo_validation_repair_not_required"), _inputs())

    assert payload["summary"]["status"] == "cameo_repair_execution_not_required"
    assert payload["summary"]["blocker_count"] == 0
    assert all(row["preflight_status"] == "pass" for row in payload["rows"])


def test_cameo_repair_execution_preflight_blocks_operator_placeholders() -> None:
    payload = build_repair_execution_preflight(
        _repair(
            status="operator_input_required",
            candidates_csv="OPERATOR_FILL_CAMEO_CANDIDATES_CSV",
            models_csv="OPERATOR_FILL_CAMEO_SELECTED_MODELS_CSV",
        ),
        _inputs("blocked_cameo_operator_input_validation", blocker_count=3),
    )

    assert payload["summary"]["status"] == "blocked_cameo_repair_execution_preflight"
    codes = {blocker["code"] for blocker in payload["blockers"]}
    assert "repair_work_order_not_ready" in codes
    assert "operator_inputs_not_ready" in codes
    assert any("operator_placeholder_present" in blocker["reason"] for blocker in payload["blockers"])
