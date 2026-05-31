from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_historical_seed_strict_blind_replacement_first_slot_repair_feasibility_board as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _args(tmp_path: Path) -> list[str]:
    return [
        "--candidate-board-json",
        str(tmp_path / "candidate_board.json"),
        "--repair-board-json",
        str(tmp_path / "repair_board.json"),
        "--out-json",
        str(tmp_path / "feasibility.json"),
        "--out-csv",
        str(tmp_path / "feasibility.csv"),
        "--out-md",
        str(tmp_path / "FEASIBILITY.md"),
    ]


def _write_inputs(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "candidate_board.json",
        {
            "summary": {
                "strict_blind_replacement_first_slot_local_candidate_board_status": (
                    "first_slot_local_candidates_review_only"
                ),
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "candidate_count": 2,
            },
            "rows": [
                {
                    "target_id": "HIST_POST",
                    "prediction_created_at": "2026-02-19",
                    "native_release_date": "2004-05-13",
                },
                {
                    "target_id": "HIST_MISSING",
                    "prediction_created_at": "",
                    "native_release_date": "",
                },
            ],
        },
    )
    _write_json(
        tmp_path / "repair_board.json",
        {
            "summary": {
                "strict_blind_replacement_first_slot_candidate_repair_board_status": (
                    "awaiting_first_slot_candidate_repairs"
                )
            },
            "rows": [
                {
                    "action_id": "first_slot_repair_001",
                    "target_id": "HIST_POST",
                    "repair_class": "chronology",
                    "blocker": "prediction_not_before_native",
                    "action_status": "open_repair_action",
                },
                {
                    "action_id": "first_slot_repair_002",
                    "target_id": "HIST_POST",
                    "repair_class": "eligibility",
                    "blocker": "strict_blind_not_eligible",
                    "action_status": "blocked_waiting_on_primary_repairs",
                },
                {
                    "action_id": "first_slot_repair_003",
                    "target_id": "HIST_MISSING",
                    "repair_class": "native_file",
                    "blocker": "native_missing",
                    "action_status": "open_repair_action",
                    "next_action": "attach authoritative native PDB",
                },
                {
                    "action_id": "first_slot_repair_004",
                    "target_id": "HIST_MISSING",
                    "repair_class": "chronology",
                    "blocker": "prediction_not_before_native",
                    "action_status": "open_repair_action",
                },
            ],
        },
    )


def test_feasibility_board_routes_post_native_predictions_to_external_source(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    args = mod.parse_args(_args(tmp_path))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["strict_blind_replacement_first_slot_repair_feasibility_board_status"] == (
        "first_slot_current_local_candidate_source_required"
    )
    assert summary["required_benchmark_id"] == "hist_REQUIRED_MONOMER_001"
    assert summary["action_count"] == 4
    assert summary["not_repairable_with_current_prediction_count"] == 1
    assert summary["blocked_by_post_native_prediction_count"] == 1
    assert summary["external_pre_native_artifact_required_action_count"] == 2
    assert summary["external_pre_native_artifact_required_target_count"] == 1
    assert summary["repairable_operator_source_required_count"] == 1
    assert summary["needs_chronology_date_evidence_count"] == 1
    assert summary["blocked_by_primary_repairs_count"] == 0
    assert summary["repairable_current_prediction_pre_native_count"] == 0
    assert summary["first_external_action_id"] == "first_slot_repair_001"
    assert summary["first_actionable_action_id"] == "first_slot_repair_003"

    rows = payload["rows"]
    assert rows[0]["feasibility_status"] == "not_repairable_with_current_prediction"
    assert rows[0]["current_prediction_before_native"] == "False"
    assert rows[2]["feasibility_status"] == "repairable_operator_source_required"
    assert rows[3]["feasibility_status"] == "needs_chronology_date_evidence"

    written_rows = _read_csv(tmp_path / "feasibility.csv")
    assert len(written_rows) == 4
    assert (tmp_path / "FEASIBILITY.md").read_text(encoding="utf-8").startswith("# CASP17")


def test_feasibility_board_reports_missing_inputs(tmp_path: Path) -> None:
    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["strict_blind_replacement_first_slot_repair_feasibility_board_status"] == (
        "blocked_missing_input"
    )
    assert "first_slot_local_candidate_board_json_missing" in payload["summary"]["input_blockers"]
    assert "first_slot_candidate_repair_board_json_missing" in payload["summary"]["input_blockers"]
