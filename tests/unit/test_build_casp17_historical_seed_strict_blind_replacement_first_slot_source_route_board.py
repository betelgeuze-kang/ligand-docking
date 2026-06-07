from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_historical_seed_strict_blind_replacement_first_slot_source_route_board as mod


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
        "--feasibility-board-json",
        str(tmp_path / "feasibility_board.json"),
        "--route-dir",
        str(tmp_path / "routes"),
        "--out-json",
        str(tmp_path / "source_route.json"),
        "--out-csv",
        str(tmp_path / "source_route.csv"),
        "--out-md",
        str(tmp_path / "SOURCE_ROUTE.md"),
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
                "required_target_id": "REQUIRED_MONOMER_001",
                "scope": "monomer",
            },
            "rows": [
                {
                    "target_id": "HIST_POST",
                    "scope": "monomer",
                    "candidate_status": "blocked_chronology_not_strict_blind",
                    "prediction_created_at": "2026-02-19",
                    "native_release_date": "2004-05-13",
                },
                {
                    "target_id": "HIST_COMPLEX",
                    "scope": "complex",
                    "candidate_status": "blocked_first_slot_candidate_review",
                    "prediction_created_at": "2026-05-17",
                    "native_release_date": "",
                },
            ],
        },
    )
    _write_json(
        tmp_path / "feasibility_board.json",
        {
            "summary": {
                "strict_blind_replacement_first_slot_repair_feasibility_board_status": (
                    "first_slot_current_local_candidate_source_required"
                )
            },
            "rows": [
                {
                    "action_id": "first_slot_repair_001",
                    "target_id": "HIST_POST",
                    "blocker": "prediction_not_before_native",
                    "feasibility_status": "not_repairable_with_current_prediction",
                    "next_route": "source_external_pre_native_prediction_or_replace_candidate",
                },
                {
                    "action_id": "first_slot_repair_002",
                    "target_id": "HIST_POST",
                    "blocker": "strict_blind_not_eligible",
                    "feasibility_status": "blocked_by_post_native_prediction",
                    "next_route": "source_external_pre_native_prediction_or_replace_candidate",
                },
                {
                    "action_id": "first_slot_repair_003",
                    "target_id": "HIST_COMPLEX",
                    "blocker": "native_authority_missing",
                    "feasibility_status": "repairable_operator_source_required",
                    "next_route": "attach_authoritative_source_file_or_reference",
                },
                {
                    "action_id": "first_slot_repair_004",
                    "target_id": "HIST_COMPLEX",
                    "blocker": "prediction_not_before_native",
                    "feasibility_status": "needs_chronology_date_evidence",
                    "next_route": "fill_prediction_created_at_and_native_release_date",
                },
            ],
        },
    )


def test_source_route_board_blocks_post_native_monomer_and_defers_complex_context(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    args = mod.parse_args(_args(tmp_path))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["strict_blind_replacement_first_slot_source_route_board_status"] == (
        "first_slot_requires_pre_native_monomer_source_or_replacement"
    )
    assert summary["required_benchmark_id"] == "hist_REQUIRED_MONOMER_001"
    assert summary["required_scope"] == "monomer"
    assert summary["route_count"] == 2
    assert summary["in_scope_route_count"] == 1
    assert summary["out_of_scope_route_count"] == 1
    assert summary["allowed_for_first_slot_count"] == 0
    assert summary["in_scope_external_required_count"] == 1
    assert summary["in_scope_external_action_count"] == 2
    assert summary["out_of_scope_source_required_count"] == 1
    assert summary["out_of_scope_date_required_count"] == 1
    assert summary["first_external_target_id"] == "HIST_POST"

    rows = payload["rows"]
    assert rows[0]["route_status"] == "in_scope_current_candidate_disqualified_post_native"
    assert rows[0]["allowed_for_first_slot"] == "False"
    assert rows[1]["route_status"] == "out_of_scope_context_only_for_first_slot"

    written_rows = _read_csv(tmp_path / "source_route.csv")
    assert len(written_rows) == 2
    assert (tmp_path / "routes" / "01_hist_post" / "SOURCE_ROUTE.md").is_file()
    assert (tmp_path / "SOURCE_ROUTE.md").read_text(encoding="utf-8").startswith("# CASP17")


def test_source_route_board_reports_missing_inputs(tmp_path: Path) -> None:
    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["strict_blind_replacement_first_slot_source_route_board_status"] == (
        "blocked_missing_input"
    )
    assert "first_slot_local_candidate_board_json_missing" in payload["summary"]["input_blockers"]
    assert "first_slot_repair_feasibility_board_json_missing" in payload["summary"]["input_blockers"]
