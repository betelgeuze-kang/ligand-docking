from __future__ import annotations

import json
from pathlib import Path

from tools import build_casp17_historical_seed_first_clearance_closure_board as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _args(tmp_path: Path) -> list[str]:
    return [
        "--operator-kit-json",
        str(tmp_path / "kit.json"),
        "--no-leak-gate-json",
        str(tmp_path / "gate.json"),
        "--evidence-packet-json",
        str(tmp_path / "packet.json"),
        "--evidence-review-gate-json",
        str(tmp_path / "review.json"),
        "--evidence-sync-plan-json",
        str(tmp_path / "sync.json"),
        "--clearance-to-identity-sync-json",
        str(tmp_path / "identity.json"),
        "--out-json",
        str(tmp_path / "closure.json"),
        "--out-csv",
        str(tmp_path / "closure.csv"),
        "--out-md",
        str(tmp_path / "CLOSURE.md"),
    ]


def _write_blocked_inputs(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "kit.json",
        {
            "summary": {
                "first_clearance_kit_status": "operator_no_leak_intake_ready",
                "target_id": "HIST_CHIGNOLIN",
                "benchmark_id": "hist_seed_chignolin",
                "ready_candidate_field_count": 7,
                "no_leak_field_count": 10,
                "total_field_count": 17,
                "promotion_preview_status": "waiting_on_operator_no_leak_fields",
                "promotion_preview_csv": "kit/promotion_preview.csv",
                "next_action": "fill no-leak evidence",
            }
        },
    )
    _write_json(
        tmp_path / "gate.json",
        {
            "summary": {
                "first_clearance_no_leak_gate_status": "awaiting_operator_no_leak_values",
                "target_id": "HIST_CHIGNOLIN",
                "benchmark_id": "hist_seed_chignolin",
                "ready_field_count": 0,
                "blocked_field_count": 10,
                "field_count": 10,
                "first_blocker": "operator_value_missing",
                "next_action": "fill no-leak intake",
            }
        },
    )
    _write_json(
        tmp_path / "packet.json",
        {
            "summary": {
                "first_clearance_no_leak_evidence_packet_status": (
                    "awaiting_first_clearance_no_leak_evidence_collection"
                ),
                "ready_field_count": 0,
                "open_field_count": 10,
                "field_count": 10,
                "first_blocker": "operator_value_missing",
                "first_open_kind": "independent_no_leak_evidence",
                "next_action": "collect evidence for no_leak_evidence_ref",
            }
        },
    )
    _write_json(
        tmp_path / "review.json",
        {
            "summary": {
                "first_clearance_no_leak_evidence_review_gate_status": (
                    "awaiting_first_clearance_no_leak_evidence_review"
                ),
                "ready_field_count": 0,
                "blocked_field_count": 10,
                "field_count": 10,
                "first_blocker": "template_operator_value_missing",
                "next_action": "fill operator_value",
            }
        },
    )
    _write_json(
        tmp_path / "sync.json",
        {
            "summary": {
                "first_clearance_no_leak_evidence_sync_plan_status": (
                    "awaiting_first_clearance_no_leak_evidence_review"
                ),
                "ready_action_count": 0,
                "blocked_action_count": 10,
                "action_count": 10,
                "first_blocker": "template_operator_value_missing",
                "next_action": "complete review gate",
            }
        },
    )
    _write_json(
        tmp_path / "identity.json",
        {
            "summary": {
                "seed_to_identity_sync_status": "waiting_on_cleared_seed_manifest",
                "ready_to_sync_count": 0,
                "waiting_intake_count": 15,
                "blocked_count": 0,
                "intake_row_count": 15,
                "first_next_action": "clear historical seed rows",
            }
        },
    )


def test_first_clearance_closure_board_orders_blocked_operator_runway(tmp_path: Path) -> None:
    _write_blocked_inputs(tmp_path)

    args = mod.parse_args(_args(tmp_path))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["first_clearance_closure_board_status"] == "awaiting_first_clearance_no_leak_closure"
    assert summary["target_id"] == "HIST_CHIGNOLIN"
    assert summary["benchmark_id"] == "hist_seed_chignolin"
    assert summary["stage_count"] == 7
    assert summary["ready_stage_count"] == 1
    assert summary["blocked_stage_count"] == 6
    assert summary["first_blocked_stage_id"] == "evidence_packet"
    assert summary["first_blocker"] == "operator_value_missing"
    assert payload["rows"][0]["stage_id"] == "operator_kit"
    assert payload["rows"][0]["stage_status"] == "stage_ready"
    assert payload["rows"][1]["stage_id"] == "evidence_packet"
    assert payload["rows"][1]["stage_status"] == "stage_blocked"
    assert (tmp_path / "CLOSURE.md").is_file()


def test_first_clearance_closure_board_ready_when_all_stages_ready(tmp_path: Path) -> None:
    _write_blocked_inputs(tmp_path)
    _write_json(
        tmp_path / "packet.json",
        {"summary": {"first_clearance_no_leak_evidence_packet_status": "first_clearance_no_leak_evidence_packet_ready_for_review", "ready_field_count": 10, "open_field_count": 0, "field_count": 10}},
    )
    _write_json(
        tmp_path / "review.json",
        {"summary": {"first_clearance_no_leak_evidence_review_gate_status": "first_clearance_no_leak_evidence_ready_for_operator_fill", "ready_field_count": 10, "blocked_field_count": 0, "field_count": 10}},
    )
    _write_json(
        tmp_path / "sync.json",
        {"summary": {"first_clearance_no_leak_evidence_sync_plan_status": "first_clearance_no_leak_evidence_sync_ready_dry_run", "ready_action_count": 10, "blocked_action_count": 0, "action_count": 10}},
    )
    _write_json(
        tmp_path / "gate.json",
        {"summary": {"first_clearance_no_leak_gate_status": "first_clearance_no_leak_ready_for_promotion_review", "ready_field_count": 10, "blocked_field_count": 0, "field_count": 10}},
    )
    _write_json(
        tmp_path / "kit.json",
        {
            "summary": {
                "first_clearance_kit_status": "operator_no_leak_intake_ready",
                "target_id": "HIST_CHIGNOLIN",
                "benchmark_id": "hist_seed_chignolin",
                "ready_candidate_field_count": 7,
                "no_leak_field_count": 10,
                "total_field_count": 17,
                "promotion_preview_status": "promotion_preview_ready",
            }
        },
    )
    _write_json(
        tmp_path / "identity.json",
        {"summary": {"seed_to_identity_sync_status": "seed_to_identity_sync_ready_dry_run", "ready_to_sync_count": 1, "waiting_intake_count": 0, "blocked_count": 0, "intake_row_count": 1}},
    )

    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["first_clearance_closure_board_status"] == (
        "first_clearance_closure_ready_for_identity_sync"
    )
    assert payload["summary"]["ready_stage_count"] == 7
    assert payload["summary"]["blocked_stage_count"] == 0
    assert {row["stage_status"] for row in payload["rows"]} == {"stage_ready"}


def test_first_clearance_closure_board_blocks_missing_inputs(tmp_path: Path) -> None:
    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["first_clearance_closure_board_status"] == "blocked_missing_inputs"
    assert "operator_kit_json_missing" in payload["summary"]["input_blockers"]
    assert payload["rows"] == []
