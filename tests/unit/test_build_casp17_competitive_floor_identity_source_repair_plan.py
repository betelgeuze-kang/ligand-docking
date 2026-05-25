from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_competitive_floor_identity_source_repair_plan as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["benchmark_id", "target_id", "scope", "operator_row_status", "blockers"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _args(tmp_path: Path, candidate_json: Path, preflight_csv: Path) -> list[str]:
    return [
        "--identity-candidate-json",
        str(candidate_json),
        "--operator-preflight-csv",
        str(preflight_csv),
        "--out-json",
        str(tmp_path / "repair.json"),
        "--out-csv",
        str(tmp_path / "repair.csv"),
        "--out-md",
        str(tmp_path / "REPAIR.md"),
    ]


def test_source_repair_plan_prioritizes_target_identity_before_downstream_work(tmp_path: Path) -> None:
    candidate_json = tmp_path / "candidate.json"
    preflight_csv = tmp_path / "preflight.csv"
    _write_json(
        candidate_json,
        {
            "summary": {
                "identity_candidate_status": "awaiting_candidate_sources",
                "source_candidate_count": 1,
                "source_ready_candidate_count": 0,
                "source_blocked_candidate_count": 1,
            }
        },
    )
    _write_csv(
        preflight_csv,
        [
            {
                "benchmark_id": "hist_REQUIRED_MONOMER_001",
                "target_id": "REQUIRED_MONOMER_001",
                "scope": "monomer",
                "operator_row_status": "blocked",
                "blockers": (
                    "placeholder_target_id,prediction_pdb_not_found,native_pdb_not_found,"
                    "leakage_clearance_required,ablation_layer_prediction_pdb_missing,"
                    "selected_model_rank_required_1_to_5"
                ),
            }
        ],
    )
    args = mod.parse_args(_args(tmp_path, candidate_json, preflight_csv))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["source_repair_status"] == "awaiting_target_identity"
    assert payload["summary"]["blocked_source_row_count"] == 1
    assert payload["summary"]["repair_action_count"] == 5
    assert payload["summary"]["target_identity_action_count"] == 1
    assert payload["summary"]["core_file_action_count"] == 1
    assert payload["summary"]["provenance_action_count"] == 1
    assert payload["summary"]["ablation_action_count"] == 1
    assert payload["summary"]["calibration_action_count"] == 1
    assert payload["rows"][0]["repair_phase"] == "target_identity"
    assert _read_csv(tmp_path / "repair.csv")[0]["repair_phase"] == "target_identity"
    assert (tmp_path / "REPAIR.md").is_file()


def test_source_repair_plan_passes_when_preflight_has_no_blocked_rows(tmp_path: Path) -> None:
    candidate_json = tmp_path / "candidate.json"
    preflight_csv = tmp_path / "preflight.csv"
    _write_json(
        candidate_json,
        {
            "summary": {
                "identity_candidate_status": "ready_for_intake_sync",
                "source_candidate_count": 1,
                "source_ready_candidate_count": 1,
                "source_blocked_candidate_count": 0,
            }
        },
    )
    _write_csv(
        preflight_csv,
        [
            {
                "benchmark_id": "hist_T9001",
                "target_id": "T9001",
                "scope": "monomer",
                "operator_row_status": "ready",
                "blockers": "",
            }
        ],
    )
    args = mod.parse_args(_args(tmp_path, candidate_json, preflight_csv))

    payload = mod.build_payload(args)

    assert payload["summary"]["source_repair_status"] == "ready_for_identity_candidates"
    assert payload["summary"]["repair_action_count"] == 0
    assert payload["summary"]["source_ready_candidate_count"] == 1
