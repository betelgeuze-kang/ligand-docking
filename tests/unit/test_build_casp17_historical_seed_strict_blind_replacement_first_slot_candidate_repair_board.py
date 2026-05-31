from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_historical_seed_strict_blind_replacement_first_slot_candidate_repair_board as mod


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
        "--repair-dir",
        str(tmp_path / "repairs"),
        "--out-json",
        str(tmp_path / "repair_board.json"),
        "--out-csv",
        str(tmp_path / "repair_board.csv"),
        "--out-md",
        str(tmp_path / "REPAIR_BOARD.md"),
    ]


def _write_candidate_board(tmp_path: Path) -> None:
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
                    "candidate_rank": 1,
                    "target_id": "HIST_A",
                    "benchmark_id": "hist_a",
                    "scope": "monomer",
                    "candidate_status": "blocked_chronology_not_strict_blind",
                    "candidate_folder": "casp17/candidates/01_hist_a",
                    "prediction_created_at": "2021-01-01",
                    "native_release_date": "2020-01-01",
                    "no_leak_dossier": "casp17/no_leak/A.md",
                    "ablation_manifest_ref": "casp17/ablation/A.csv",
                    "calibration_values_ref": "casp17/calibration/A.csv",
                    "blockers": (
                        "prediction_not_before_native,no_leak_not_ready,"
                        "ablation_not_ready,calibration_not_ready,strict_blind_not_eligible"
                    ),
                },
                {
                    "candidate_rank": 2,
                    "target_id": "HIST_B",
                    "benchmark_id": "hist_b",
                    "scope": "complex",
                    "candidate_status": "blocked_first_slot_candidate_review",
                    "candidate_folder": "casp17/candidates/02_hist_b",
                    "prediction_pdb": "",
                    "native_pdb": "",
                    "native_authority_ref": "",
                    "blockers": "prediction_missing,native_missing,native_authority_missing",
                },
            ],
        },
    )


def test_repair_board_expands_candidate_blockers_to_actions(tmp_path: Path) -> None:
    _write_candidate_board(tmp_path)

    args = mod.parse_args(_args(tmp_path))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["strict_blind_replacement_first_slot_candidate_repair_board_status"] == (
        "awaiting_first_slot_candidate_repairs"
    )
    assert summary["required_benchmark_id"] == "hist_REQUIRED_MONOMER_001"
    assert summary["action_count"] == 8
    assert summary["open_repair_action_count"] == 7
    assert summary["blocked_action_count"] == 1
    assert summary["chronology_action_count"] == 1
    assert summary["no_leak_action_count"] == 1
    assert summary["ablation_action_count"] == 1
    assert summary["calibration_action_count"] == 1
    assert summary["prediction_file_action_count"] == 1
    assert summary["native_file_action_count"] == 1
    assert summary["native_authority_action_count"] == 1
    assert summary["eligibility_action_count"] == 1
    assert summary["first_open_repair_class"] == "chronology"
    assert summary["first_open_blocker"] == "prediction_not_before_native"

    rows = payload["rows"]
    assert rows[0]["action_id"] == "first_slot_repair_001"
    assert rows[0]["priority"] == 1
    assert rows[0]["repair_class"] == "chronology"
    assert "prediction_created_at=2021-01-01" in rows[0]["evidence_pointer"]
    assert any(row["action_status"] == "blocked_waiting_on_primary_repairs" for row in rows)

    written_rows = _read_csv(tmp_path / "repair_board.csv")
    assert len(written_rows) == 8
    assert (tmp_path / "repairs" / "01_hist_a" / "prediction_not_before_native" / "REPAIR_ACTION.md").is_file()
    assert (tmp_path / "REPAIR_BOARD.md").read_text(encoding="utf-8").startswith("# CASP17")


def test_repair_board_reports_clear_when_candidates_have_no_blockers(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "candidate_board.json",
        {
            "summary": {"required_benchmark_id": "hist_REQUIRED_MONOMER_001", "candidate_count": 1},
            "rows": [
                {
                    "candidate_rank": 1,
                    "target_id": "HIST_READY",
                    "benchmark_id": "hist_ready",
                    "scope": "monomer",
                    "candidate_status": "ready_for_first_slot_operator_clearance",
                    "blockers": "",
                }
            ],
        },
    )

    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["strict_blind_replacement_first_slot_candidate_repair_board_status"] == (
        "first_slot_candidate_repair_clear"
    )
    assert payload["summary"]["action_count"] == 0


def test_repair_board_reports_missing_candidate_board(tmp_path: Path) -> None:
    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["strict_blind_replacement_first_slot_candidate_repair_board_status"] == (
        "blocked_missing_input"
    )
    assert "first_slot_local_candidate_board_json_missing" in payload["summary"]["input_blockers"]
