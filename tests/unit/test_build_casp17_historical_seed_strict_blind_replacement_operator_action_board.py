from __future__ import annotations

import json
from pathlib import Path

from tools.casp17 import build_casp17_historical_seed_strict_blind_replacement_operator_action_board as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _row(field: str, *, status: str = "awaiting_operator_value", blockers: str | None = None) -> dict:
    return {
        "queue_rank": 1,
        "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
        "field_name": field,
        "required_policy": "operator_supplied_non_placeholder",
        "operator_value": "REQUIRED_VALUE" if status.startswith("awaiting") else "HIST_TARGET",
        "evidence_ref": "REQUIRED_OPERATOR_EVIDENCE_REF" if status.startswith("awaiting") else "local/evidence.md",
        "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE" if status.startswith("awaiting") else "cleared",
        "destination_intake_csv": "intake.csv",
        "operator_values_csv": "operator_values.csv",
        "gate_status": status,
        "blockers": blockers
        if blockers is not None
        else (
            "operator_value_required,evidence_ref_required,operator_clearance_required"
            if status.startswith("awaiting")
            else ""
        ),
        "next_action": "fill operator value",
    }


def _args(tmp_path: Path) -> list[str]:
    return [
        "--operator-gate-json",
        str(tmp_path / "operator_gate.json"),
        "--out-json",
        str(tmp_path / "operator_actions.json"),
        "--out-csv",
        str(tmp_path / "operator_actions.csv"),
        "--out-md",
        str(tmp_path / "OPERATOR_ACTIONS.md"),
    ]


def test_operator_action_board_expands_open_operator_rows(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "operator_gate.json",
        {
            "summary": {"strict_blind_replacement_operator_value_gate_status": "awaiting_operator_values"},
            "rows": [
                _row("replacement_target_id"),
                _row("replacement_benchmark_id"),
                _row("operator_clearance"),
            ],
        },
    )

    args = mod.parse_args(_args(tmp_path))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["strict_blind_replacement_operator_action_board_status"] == (
        "awaiting_strict_blind_operator_actions"
    )
    assert summary["action_count"] == 3
    assert summary["open_operator_value_count"] == 3
    assert summary["open_evidence_ref_count"] == 3
    assert summary["open_operator_clearance_count"] == 3
    assert summary["replacement_target_id_missing_count"] == 1
    assert summary["operator_clearance_value_missing_count"] == 1
    assert summary["first_open_action_id"] == "strict_blind_operator_001"
    assert payload["rows"][0]["action_status"] == "open_operator_value"
    assert payload["rows"][0]["operator_value_present"] == "false"
    assert (tmp_path / "operator_actions.csv").is_file()
    assert "Claim Boundary" in (tmp_path / "OPERATOR_ACTIONS.md").read_text(encoding="utf-8")


def test_operator_action_board_marks_ready_rows(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "operator_gate.json",
        {
            "summary": {"strict_blind_replacement_operator_value_gate_status": "ready_for_operator_value_apply"},
            "rows": [_row("replacement_target_id", status="ready_to_apply")],
        },
    )

    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["strict_blind_replacement_operator_action_board_status"] == (
        "strict_blind_operator_actions_ready_for_apply"
    )
    assert payload["summary"]["ready_for_apply_count"] == 1
    assert payload["summary"]["open_operator_value_count"] == 0
    assert payload["rows"][0]["action_status"] == "ready_to_apply"


def test_operator_action_board_reports_missing_inputs(tmp_path: Path) -> None:
    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["strict_blind_replacement_operator_action_board_status"] == "blocked_missing_input"
    assert "strict_blind_replacement_operator_value_gate_json_missing" in payload["summary"]["input_blockers"]
