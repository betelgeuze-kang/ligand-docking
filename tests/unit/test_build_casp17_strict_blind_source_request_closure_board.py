from __future__ import annotations

import json
from pathlib import Path

from tools.casp17 import build_casp17_strict_blind_source_request_closure_board as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _args(tmp_path: Path) -> list[str]:
    return [
        "--source-request-packet-json",
        str(tmp_path / "requests.json"),
        "--fulfillment-gate-json",
        str(tmp_path / "fulfillment.json"),
        "--operator-fill-worklist-json",
        str(tmp_path / "fill.json"),
        "--operator-sync-plan-json",
        str(tmp_path / "sync.json"),
        "--first-unlock-handoff-json",
        str(tmp_path / "handoff.json"),
        "--first-unlock-evidence-packet-json",
        str(tmp_path / "evidence_packet.json"),
        "--first-unlock-evidence-review-gate-json",
        str(tmp_path / "evidence_review.json"),
        "--first-unlock-evidence-sync-plan-json",
        str(tmp_path / "evidence_sync.json"),
        "--source-gate-operator-packet-json",
        str(tmp_path / "operator.json"),
        "--internal-source-gate-json",
        str(tmp_path / "gate.json"),
        "--internal-apply-plan-json",
        str(tmp_path / "apply.json"),
        "--first-slot-closure-kit-json",
        str(tmp_path / "first_slot.json"),
        "--batch-runway-json",
        str(tmp_path / "batch.json"),
        "--out-json",
        str(tmp_path / "closure.json"),
        "--out-csv",
        str(tmp_path / "closure.csv"),
        "--out-md",
        str(tmp_path / "CLOSURE.md"),
    ]


def _write_blocked_inputs(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "requests.json",
        {
            "summary": {
                "source_request_packet_status": "awaiting_pre_native_source_or_candidate_replacement",
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "required_target_id": "REQUIRED_MONOMER_001",
                "required_scope": "monomer",
                "operator_template_ready_count": 0,
                "operator_template_awaiting_count": 17,
                "request_count": 17,
                "first_request_blocker": "prediction_not_before_native",
                "first_missing_operator_field": "source_id",
                "first_next_action": "attach pre-native source",
            }
        },
    )
    _write_json(
        tmp_path / "fulfillment.json",
        {
            "summary": {
                "source_request_fulfillment_gate_status": "awaiting_source_request_operator_values",
                "ready_request_count": 0,
                "blocked_request_count": 17,
                "request_count": 17,
                "first_blocker": "source_id_missing",
                "first_next_action": "fill operator_value for source_id",
            }
        },
    )
    _write_json(
        tmp_path / "fill.json",
        {
            "summary": {
                "source_request_operator_fill_worklist_status": "awaiting_source_request_operator_values",
                "field_ready_count": 0,
                "operator_value_missing_count": 187,
                "field_action_count": 187,
                "first_blocker": "operator_value_missing",
                "first_next_action": "fill operator_value for source_id",
            }
        },
    )
    _write_json(
        tmp_path / "sync.json",
        {
            "summary": {
                "source_request_operator_sync_plan_status": "awaiting_source_request_fulfillment",
                "ready_sync_action_count": 0,
                "blocked_sync_action_count": 1,
                "sync_action_count": 0,
                "first_blocker": "source_id_missing",
                "first_next_action": "fill operator_value for source_id",
            }
        },
    )
    _write_json(
        tmp_path / "handoff.json",
        {
            "summary": {
                "first_unlock_handoff_status": "awaiting_first_unlock_operator_values",
                "ready_field_count": 0,
                "blocked_field_count": 11,
                "field_count": 11,
                "first_blocker": "operator_value_missing",
                "first_next_action": "fill operator_value for source_id",
            }
        },
    )
    _write_json(
        tmp_path / "evidence_packet.json",
        {
            "summary": {
                "first_unlock_evidence_packet_status": "awaiting_first_unlock_evidence_collection",
                "ready_field_count": 0,
                "open_field_count": 11,
                "field_count": 11,
                "first_blocker": "operator_value_missing",
                "first_next_action": "collect evidence for source_id",
            }
        },
    )
    _write_json(
        tmp_path / "evidence_review.json",
        {
            "summary": {
                "first_unlock_evidence_review_gate_status": "awaiting_first_unlock_evidence_review",
                "ready_field_count": 0,
                "blocked_field_count": 11,
                "field_count": 11,
                "first_blocker": "template_operator_value_missing",
                "first_next_action": "fill operator_value for source_id in operator_evidence_template.csv",
            }
        },
    )
    _write_json(
        tmp_path / "evidence_sync.json",
        {
            "summary": {
                "first_unlock_evidence_sync_plan_status": "awaiting_first_unlock_evidence_review",
                "ready_action_count": 0,
                "blocked_action_count": 11,
                "action_count": 11,
                "first_blocker": "template_operator_value_missing",
                "first_next_action": "complete first-unlock evidence review before syncing into the source gate",
            }
        },
    )
    _write_json(
        tmp_path / "operator.json",
        {
            "summary": {
                "source_gate_operator_packet_status": "awaiting_source_gate_operator_values",
                "operator_ready_count": 0,
                "operator_awaiting_count": 11,
                "first_field_key": "source_id",
                "first_operator_status": "awaiting_operator_value",
                "first_next_action": "set source_id",
            }
        },
    )
    _write_json(
        tmp_path / "gate.json",
        {
            "summary": {
                "internal_prediction_source_gate_status": "awaiting_internal_prediction_source_gate_fields",
                "pass_count": 3,
                "blocked_count": 13,
                "check_count": 16,
                "first_blocker": "internal_source_id_missing_or_external",
                "first_next_action": "set source_id",
            }
        },
    )
    _write_json(
        tmp_path / "apply.json",
        {
            "summary": {
                "internal_prediction_source_apply_plan_status": "blocked_until_internal_prediction_source_gate_passes",
                "ready_action_count": 0,
                "blocked_action_count": 16,
                "action_count": 16,
                "first_blocker": "internal_prediction_source_gate_not_ready",
                "first_next_action": "copy verified prediction",
            }
        },
    )
    _write_json(
        tmp_path / "first_slot.json",
        {
            "summary": {
                "first_slot_closure_kit_status": "blocked_on_internal_prediction_source_gate",
                "step_ready_count": 0,
                "step_blocked_count": 7,
                "step_count": 7,
                "first_blocker": "internal_source_id_missing_or_external",
                "first_next_action": "set source_id",
            }
        },
    )
    _write_json(
        tmp_path / "batch.json",
        {
            "summary": {
                "batch_closure_runway_status": "blocked_on_first_slot_internal_prediction_source",
                "ready_slot_count": 0,
                "blocked_slot_count": 40,
                "slot_count": 40,
                "first_blocker": "internal_source_id_missing_or_external",
                "first_next_action": "set source_id",
            }
        },
    )


def test_source_request_closure_board_orders_blocked_first_slot_runway(tmp_path: Path) -> None:
    _write_blocked_inputs(tmp_path)

    args = mod.parse_args(_args(tmp_path))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["strict_blind_source_request_closure_board_status"] == (
        "awaiting_strict_blind_source_request_closure"
    )
    assert summary["required_benchmark_id"] == "hist_REQUIRED_MONOMER_001"
    assert summary["stage_count"] == 13
    assert summary["ready_stage_count"] == 0
    assert summary["blocked_stage_count"] == 13
    assert summary["first_blocked_stage_id"] == "source_request_packet"
    assert summary["first_blocker"] == "prediction_not_before_native"
    assert payload["rows"][0]["stage_id"] == "source_request_packet"
    assert payload["rows"][0]["stage_status"] == "stage_blocked"
    assert payload["rows"][4]["stage_id"] == "first_unlock_handoff"
    assert payload["rows"][7]["stage_id"] == "first_unlock_evidence_sync_plan"
    assert (tmp_path / "CLOSURE.md").is_file()


def test_source_request_closure_board_ready_when_all_stages_ready(tmp_path: Path) -> None:
    _write_blocked_inputs(tmp_path)
    _write_json(
        tmp_path / "requests.json",
        {"summary": {"source_request_packet_status": "source_request_packet_ready", "request_count": 2, "operator_template_ready_count": 2, "operator_template_awaiting_count": 0, "required_benchmark_id": "hist_REQUIRED_MONOMER_001", "required_target_id": "REQUIRED_MONOMER_001", "required_scope": "monomer"}},
    )
    _write_json(
        tmp_path / "fulfillment.json",
        {"summary": {"source_request_fulfillment_gate_status": "source_request_fulfillment_ready", "ready_request_count": 2, "blocked_request_count": 0, "request_count": 2}},
    )
    _write_json(
        tmp_path / "fill.json",
        {"summary": {"source_request_operator_fill_worklist_status": "source_request_operator_values_ready", "field_ready_count": 4, "operator_value_missing_count": 0, "field_action_count": 4}},
    )
    _write_json(
        tmp_path / "sync.json",
        {"summary": {"source_request_operator_sync_plan_status": "source_request_operator_sync_ready_dry_run", "ready_sync_action_count": 4, "blocked_sync_action_count": 0, "sync_action_count": 4}},
    )
    _write_json(
        tmp_path / "handoff.json",
        {"summary": {"first_unlock_handoff_status": "first_unlock_handoff_ready_for_source_gate_review", "ready_field_count": 4, "blocked_field_count": 0, "field_count": 4}},
    )
    _write_json(
        tmp_path / "evidence_packet.json",
        {"summary": {"first_unlock_evidence_packet_status": "first_unlock_evidence_packet_ready_for_source_gate_review", "ready_field_count": 4, "open_field_count": 0, "field_count": 4}},
    )
    _write_json(
        tmp_path / "evidence_review.json",
        {"summary": {"first_unlock_evidence_review_gate_status": "first_unlock_evidence_ready_for_source_gate_sync", "ready_field_count": 4, "blocked_field_count": 0, "field_count": 4}},
    )
    _write_json(
        tmp_path / "evidence_sync.json",
        {"summary": {"first_unlock_evidence_sync_plan_status": "first_unlock_evidence_sync_ready_dry_run", "ready_action_count": 4, "blocked_action_count": 0, "action_count": 4}},
    )
    _write_json(
        tmp_path / "operator.json",
        {"summary": {"source_gate_operator_packet_status": "source_gate_operator_values_ready", "operator_ready_count": 4, "operator_awaiting_count": 0}},
    )
    _write_json(
        tmp_path / "gate.json",
        {"summary": {"internal_prediction_source_gate_status": "internal_prediction_source_gate_ready", "pass_count": 4, "blocked_count": 0, "check_count": 4}},
    )
    _write_json(
        tmp_path / "apply.json",
        {"summary": {"internal_prediction_source_apply_plan_status": "internal_prediction_source_apply_ready_dry_run", "ready_action_count": 4, "blocked_action_count": 0, "action_count": 4}},
    )
    _write_json(
        tmp_path / "first_slot.json",
        {"summary": {"first_slot_closure_kit_status": "first_slot_closure_ready", "step_ready_count": 7, "step_blocked_count": 0, "step_count": 7}},
    )
    _write_json(
        tmp_path / "batch.json",
        {"summary": {"batch_closure_runway_status": "batch_closure_runway_ready", "ready_slot_count": 40, "blocked_slot_count": 0, "slot_count": 40}},
    )

    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["strict_blind_source_request_closure_board_status"] == (
        "strict_blind_source_request_closure_ready_for_first_slot"
    )
    assert payload["summary"]["ready_stage_count"] == 13
    assert payload["summary"]["blocked_stage_count"] == 0
    assert {row["stage_status"] for row in payload["rows"]} == {"stage_ready"}


def test_source_request_closure_board_blocks_missing_inputs(tmp_path: Path) -> None:
    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["strict_blind_source_request_closure_board_status"] == "blocked_missing_inputs"
    assert "source_request_packet_json_missing" in payload["summary"]["input_blockers"]
    assert payload["rows"] == []
