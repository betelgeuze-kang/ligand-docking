from __future__ import annotations

import json
from pathlib import Path

from tools import build_casp17_strict_blind_first_unlock_handoff as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _args(tmp_path: Path) -> list[str]:
    return [
        "--unlock-plan-json",
        str(tmp_path / "unlock.json"),
        "--closure-board-json",
        str(tmp_path / "closure.json"),
        "--source-request-packet-json",
        str(tmp_path / "requests.json"),
        "--operator-fill-worklist-json",
        str(tmp_path / "fills.json"),
        "--source-gate-operator-packet-json",
        str(tmp_path / "operator.json"),
        "--internal-source-gate-json",
        str(tmp_path / "gate.json"),
        "--out-json",
        str(tmp_path / "handoff.json"),
        "--out-csv",
        str(tmp_path / "handoff.csv"),
        "--out-md",
        str(tmp_path / "HANDOFF.md"),
    ]


def _write_inputs(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "unlock.json",
        {
            "summary": {
                "historical_winner_normalized_unlock_plan_status": "awaiting_historical_winner_normalized_unlocks",
                "first_blocked_action_id": "close_first_source_request",
            }
        },
    )
    _write_json(
        tmp_path / "closure.json",
        {
            "summary": {
                "strict_blind_source_request_closure_board_status": "awaiting_strict_blind_source_request_closure",
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "required_target_id": "REQUIRED_MONOMER_001",
                "required_scope": "monomer",
            }
        },
    )
    _write_json(
        tmp_path / "requests.json",
        {
            "rows": [
                {
                    "candidate_rank": 1,
                    "candidate_scope": "monomer",
                    "candidate_target_id": "HIST_BBA5",
                    "current_native_pdb": "native.pdb",
                    "current_prediction_pdb": "post_native_prediction.pdb",
                    "first_blocker": "prediction_not_before_native",
                    "native_authority_ref": "rcsb:1T8J",
                    "native_release_date": "2004-05-13",
                    "next_action": "attach pre-native prediction",
                    "operator_template_csv": "request/operator_source_values_template.csv",
                    "prediction_created_at": "2026-02-19",
                    "request_id": "source_request_001",
                    "request_kind": "pre_native_prediction_source_required",
                    "required_operator_fields": "source_id,prediction_pdb,prediction_created_at",
                }
            ]
        },
    )
    _write_json(
        tmp_path / "fills.json",
        {
            "rows": [
                {
                    "request_id": "source_request_001",
                    "field_key": "source_id",
                    "fill_status": "awaiting_operator_value",
                    "value_status": "operator_value_missing",
                    "evidence_status": "evidence_required_missing",
                    "first_blocker": "operator_value_missing",
                    "next_action": "fill operator_value for source_id",
                },
                {
                    "request_id": "source_request_001",
                    "field_key": "prediction_pdb",
                    "fill_status": "awaiting_operator_value",
                    "value_status": "operator_value_missing",
                    "evidence_status": "evidence_required_missing",
                    "first_blocker": "operator_value_missing",
                    "next_action": "fill operator_value for prediction_pdb",
                },
                {
                    "request_id": "source_request_001",
                    "field_key": "prediction_created_at",
                    "fill_status": "awaiting_operator_value",
                    "value_status": "operator_value_missing",
                    "evidence_status": "evidence_required_missing",
                    "first_blocker": "operator_value_missing",
                    "next_action": "fill operator_value for prediction_created_at",
                },
            ]
        },
    )
    _write_json(
        tmp_path / "operator.json",
        {
            "operator_rows": [
                {
                    "field_key": "source_id",
                    "fill_kind": "manifest_value",
                    "operator_status": "awaiting_operator_value",
                    "required_format": "internal source id",
                    "destination": "manifest.csv",
                },
                {
                    "field_key": "prediction_pdb",
                    "fill_kind": "file",
                    "operator_status": "awaiting_operator_value",
                    "required_format": "local pre-native prediction PDB path",
                    "destination": "",
                },
                {
                    "field_key": "prediction_created_at",
                    "fill_kind": "manifest_value",
                    "operator_status": "awaiting_operator_value",
                    "required_format": "YYYY-MM-DD",
                    "destination": "manifest.csv",
                },
            ]
        },
    )
    _write_json(
        tmp_path / "gate.json",
        {
            "summary": {
                "internal_prediction_source_gate_status": "awaiting_internal_prediction_source_gate_fields"
            }
        },
    )


def test_first_unlock_handoff_surfaces_first_blocked_operator_field(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    args = mod.parse_args(_args(tmp_path))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["first_unlock_handoff_status"] == "awaiting_first_unlock_operator_values"
    assert summary["request_id"] == "source_request_001"
    assert summary["candidate_target_id"] == "HIST_BBA5"
    assert summary["field_count"] == 3
    assert summary["ready_field_count"] == 0
    assert summary["blocked_field_count"] == 3
    assert summary["first_blocked_field_key"] == "source_id"
    assert summary["first_blocker"] == "operator_value_missing"
    assert payload["rows"][0]["destination"] == "manifest.csv"
    assert (tmp_path / "HANDOFF.md").is_file()


def test_first_unlock_handoff_ready_when_all_fields_ready(tmp_path: Path) -> None:
    _write_inputs(tmp_path)
    _write_json(
        tmp_path / "fills.json",
        {
            "rows": [
                {
                    "request_id": "source_request_001",
                    "field_key": "source_id",
                    "fill_status": "field_ready_for_fulfillment_gate",
                    "value_status": "value_present",
                    "evidence_status": "evidence_present",
                },
                {
                    "request_id": "source_request_001",
                    "field_key": "prediction_pdb",
                    "fill_status": "field_ready_for_fulfillment_gate",
                    "value_status": "value_present",
                    "evidence_status": "evidence_present",
                },
                {
                    "request_id": "source_request_001",
                    "field_key": "prediction_created_at",
                    "fill_status": "field_ready_for_fulfillment_gate",
                    "value_status": "value_present",
                    "evidence_status": "evidence_present",
                },
            ]
        },
    )

    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["first_unlock_handoff_status"] == "first_unlock_handoff_ready_for_source_gate_review"
    assert payload["summary"]["ready_field_count"] == 3
    assert payload["summary"]["blocked_field_count"] == 0
    assert payload["summary"]["first_blocked_field_key"] == ""


def test_first_unlock_handoff_blocks_missing_inputs(tmp_path: Path) -> None:
    args = mod.parse_args(_args(tmp_path))
    payload = mod.build_payload(args)

    assert payload["summary"]["first_unlock_handoff_status"] == "blocked_missing_inputs"
    assert "unlock_plan_json_missing" in payload["summary"]["input_blockers"]
