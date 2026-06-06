from __future__ import annotations

import json
from pathlib import Path

from tools.casp17 import build_casp17_historical_seed_strict_blind_replacement_cycle as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _args(tmp_path: Path) -> list[str]:
    return [
        "--queue-json",
        str(tmp_path / "queue.json"),
        "--intake-json",
        str(tmp_path / "intake.json"),
        "--dropzones-json",
        str(tmp_path / "dropzones.json"),
        "--quality-json",
        str(tmp_path / "quality.json"),
        "--import-json",
        str(tmp_path / "import.json"),
        "--operator-json",
        str(tmp_path / "operator.json"),
        "--operator-action-board-json",
        str(tmp_path / "operator_action_board.json"),
        "--promotion-json",
        str(tmp_path / "promotion.json"),
        "--out-json",
        str(tmp_path / "cycle.json"),
        "--out-csv",
        str(tmp_path / "cycle.csv"),
        "--out-md",
        str(tmp_path / "CYCLE.md"),
    ]


def _write_current_like_inputs(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "queue.json",
        {
            "summary": {
                "strict_blind_replacement_queue_status": "strict_blind_replacement_queue_open",
                "scaffold_slot_count": 40,
                "strict_blind_ready_slot_count": 0,
                "first_open_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "first_next_action": "select a non-current historical target",
            }
        },
    )
    _write_json(
        tmp_path / "intake.json",
        {
            "summary": {
                "strict_blind_replacement_intake_status": "awaiting_strict_blind_replacement_intake",
                "intake_slot_count": 40,
                "ready_for_preflight_count": 0,
                "blocked_or_awaiting_count": 40,
                "missing_field_count": 640,
                "first_open_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "first_next_action": "fill replacement_candidate_intake.csv",
            }
        },
    )
    _write_json(
        tmp_path / "dropzones.json",
        {
            "summary": {
                "strict_blind_replacement_evidence_dropzone_status": "awaiting_strict_blind_evidence_files",
                "dropzone_count": 40,
                "ready_for_intake_patch_count": 0,
                "awaiting_file_count": 40,
                "file_present_count": 0,
                "file_missing_count": 240,
                "first_open_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "first_next_action": "place strict-blind evidence files",
            }
        },
    )
    _write_json(
        tmp_path / "quality.json",
        {
            "summary": {
                "strict_blind_replacement_evidence_quality_audit_status": (
                    "awaiting_strict_blind_evidence_quality_files"
                ),
                "slot_count": 40,
                "ready_for_quality_review_count": 0,
                "awaiting_evidence_files_count": 40,
                "blocked_evidence_quality_count": 0,
                "pdb_valid_slot_count": 0,
                "prediction_native_distinct_count": 0,
                "first_open_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "first_next_action": "place all six strict-blind evidence files",
            }
        },
    )
    _write_json(
        tmp_path / "import.json",
        {
            "summary": {
                "strict_blind_replacement_evidence_import_gate_status": "awaiting_strict_blind_evidence_import",
                "action_count": 640,
                "ready_for_apply_count": 0,
                "applied_count": 0,
                "already_applied_count": 0,
                "awaiting_file_count": 240,
                "awaiting_operator_value_count": 400,
                "blocked_count": 0,
                "first_open_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "first_next_action": "place the missing evidence file",
            }
        },
    )
    _write_json(
        tmp_path / "operator.json",
        {
            "summary": {
                "strict_blind_replacement_operator_value_gate_status": "awaiting_operator_values",
                "action_count": 400,
                "ready_for_apply_count": 0,
                "applied_count": 0,
                "already_applied_count": 0,
                "awaiting_operator_value_count": 400,
                "awaiting_evidence_ref_count": 0,
                "awaiting_operator_clearance_count": 0,
                "blocked_count": 0,
                "first_open_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "first_next_action": "fill operator_value",
            }
        },
    )
    _write_json(
        tmp_path / "operator_action_board.json",
        {
            "summary": {
                "strict_blind_replacement_operator_action_board_status": (
                    "awaiting_strict_blind_operator_actions"
                ),
                "action_count": 400,
                "ready_for_apply_count": 0,
                "applied_count": 0,
                "already_applied_count": 0,
                "open_operator_value_count": 400,
                "open_evidence_ref_count": 400,
                "open_operator_clearance_count": 400,
                "blocked_count": 0,
                "first_open_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "first_next_action": "fill operator_value for replacement_target_id",
            }
        },
    )
    _write_json(
        tmp_path / "promotion.json",
        {
            "summary": {
                "strict_blind_replacement_promotion_gate_status": (
                    "awaiting_strict_blind_replacement_promotion"
                ),
                "slot_count": 40,
                "ready_for_competitive_proof_count": 0,
                "blocked_review_count": 0,
                "awaiting_file_evidence_count": 40,
                "awaiting_operator_values_count": 40,
                "awaiting_intake_preflight_count": 40,
                "first_open_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "first_next_action": "place required strict-blind evidence files",
            }
        },
    )


def test_cycle_reports_first_evidence_file_bottleneck(tmp_path: Path) -> None:
    _write_current_like_inputs(tmp_path)

    args = mod.parse_args(_args(tmp_path))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["strict_blind_replacement_cycle_status"] == "awaiting_evidence_files"
    assert summary["slot_count"] == 40
    assert summary["evidence_file_missing_count"] == 240
    assert summary["operator_awaiting_value_count"] == 400
    assert summary["operator_action_board_open_value_count"] == 400
    assert summary["operator_action_board_open_evidence_count"] == 400
    assert summary["operator_action_board_open_clearance_count"] == 400
    assert summary["promotion_ready_count"] == 0
    assert summary["first_blocking_stage"] == "evidence_dropzones"
    assert summary["first_open_benchmark_id"] == "hist_REQUIRED_MONOMER_001"
    assert [row["stage"] for row in payload["rows"]] == [
        "queue",
        "intake",
        "evidence_dropzones",
        "evidence_quality",
        "evidence_import",
        "operator_values",
        "operator_action_board",
        "promotion",
    ]
    assert (tmp_path / "cycle.csv").is_file()
    assert "Claim Boundary" in (tmp_path / "CYCLE.md").read_text(encoding="utf-8")


def test_cycle_reports_ready_when_all_promoted(tmp_path: Path) -> None:
    _write_current_like_inputs(tmp_path)
    _write_json(
        tmp_path / "dropzones.json",
        {
            "summary": {
                "strict_blind_replacement_evidence_dropzone_status": "strict_blind_evidence_files_ready",
                "dropzone_count": 40,
                "ready_for_intake_patch_count": 40,
                "awaiting_file_count": 0,
                "file_present_count": 240,
                "file_missing_count": 0,
                "first_open_benchmark_id": "",
                "first_next_action": "",
            }
        },
    )
    _write_json(
        tmp_path / "quality.json",
        {
            "summary": {
                "strict_blind_replacement_evidence_quality_audit_status": (
                    "strict_blind_evidence_quality_ready_for_operator_review"
                ),
                "slot_count": 40,
                "ready_for_quality_review_count": 40,
                "awaiting_evidence_files_count": 0,
                "blocked_evidence_quality_count": 0,
                "pdb_valid_slot_count": 40,
                "prediction_native_distinct_count": 40,
            }
        },
    )
    _write_json(
        tmp_path / "promotion.json",
        {
            "summary": {
                "strict_blind_replacement_promotion_gate_status": (
                    "strict_blind_replacements_ready_for_competitive_proof"
                ),
                "slot_count": 40,
                "ready_for_competitive_proof_count": 40,
                "blocked_review_count": 0,
            }
        },
    )

    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["strict_blind_replacement_cycle_status"] == (
        "strict_blind_replacements_ready_for_competitive_proof"
    )
    assert payload["summary"]["first_blocking_stage"] == "promotion"
    assert payload["summary"]["promotion_ready_count"] == 40


def test_cycle_reports_missing_inputs(tmp_path: Path) -> None:
    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["strict_blind_replacement_cycle_status"] == "blocked_missing_input"
    assert "queue_json_missing" in payload["summary"]["input_blockers"]
    assert "operator_action_board_json_missing" in payload["summary"]["input_blockers"]
