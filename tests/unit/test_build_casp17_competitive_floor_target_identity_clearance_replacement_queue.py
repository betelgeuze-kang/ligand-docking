from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_competitive_floor_target_identity_clearance_replacement_queue as mod


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
        fieldnames = ["target_id"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _pdb(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("ATOM      1  CA  ALA A   1       1.000   2.000   3.000  1.00 70.00           C\n", encoding="utf-8")


def _args(tmp_path: Path) -> list[str]:
    return [
        "--adjudication-json",
        str(tmp_path / "adjudication.json"),
        "--target-watchlist-csv",
        str(tmp_path / "watchlist.csv"),
        "--current-target-csv",
        str(tmp_path / "current_targets.csv"),
        "--out-json",
        str(tmp_path / "replacement.json"),
        "--out-csv",
        str(tmp_path / "replacement.csv"),
        "--out-md",
        str(tmp_path / "REPLACEMENT.md"),
        "--max-candidates-per-target",
        "4",
    ]


def test_replacement_queue_ranks_ready_and_blocked_candidates(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_json(
        tmp_path / "adjudication.json",
        {
            "rows": [
                {
                    "target_id": "H1001",
                    "target_name": "Collision source",
                    "replacement_required": "true",
                }
            ]
        },
    )
    _write_csv(
        tmp_path / "watchlist.csv",
        [
            {
                "target_id": "H2001",
                "target_type": "Prot",
                "deadline_class": "closed",
                "residues": "100",
                "stoichiometry": "A1",
                "description": "Ready replacement",
                "entry_date": "2026-01-01",
                "qa_expiration": "2026-01-10",
            },
            {
                "target_id": "H2002",
                "target_type": "Prot",
                "deadline_class": "closed",
                "residues": "200",
                "stoichiometry": "A1",
                "description": "Current collision",
                "entry_date": "2026-01-02",
                "qa_expiration": "2026-01-11",
            },
            {
                "target_id": "H2003",
                "target_type": "Prot",
                "deadline_class": "closed",
                "residues": "300",
                "stoichiometry": "A1",
                "description": "Missing prediction",
                "entry_date": "2026-01-03",
                "qa_expiration": "2026-01-12",
            },
        ],
    )
    _write_csv(tmp_path / "current_targets.csv", [{"target_id": "H3001", "protein_name": "Current collision"}])
    _pdb(tmp_path / "runs" / "casp17_prediction_jobs_current" / "H2001" / "H2001_model_1.pdb")
    _pdb(tmp_path / "runs" / "casp17_predictions_current" / "H2001TS.pdb")
    _write_json(
        tmp_path / "runs" / "casp17_internal_physics_raw_validations_current" / "H2001_raw_confidence_calibration.json",
        {"summary": {"target_id": "H2001"}},
    )
    _write_json(
        tmp_path / "runs" / "casp17_internal_scorecards_current" / "H2001_internal_scorecard.json",
        {"summary": {"target_id": "H2001"}},
    )
    args = mod.parse_args(_args(tmp_path))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["replacement_queue_status"] == "candidate_ready_for_operator_clearance"
    assert payload["summary"]["ready_candidate_count"] == 1
    assert payload["summary"]["blocked_missing_prediction_count"] == 1
    assert payload["summary"]["blocked_current_collision_count"] == 1
    rows = payload["rows"]
    assert rows[0]["candidate_target_id"] == "H2001"
    assert rows[0]["candidate_status"] == "candidate_ready_for_operator_clearance"
    by_id = {row["candidate_target_id"]: row for row in rows}
    assert by_id["H2002"]["candidate_status"] == "blocked_current_target_collision"
    assert by_id["H2003"]["candidate_status"] == "blocked_missing_local_prediction"
    assert (tmp_path / "REPLACEMENT.md").is_file()


def test_replacement_queue_handles_no_required_replacements(tmp_path: Path) -> None:
    _write_json(tmp_path / "adjudication.json", {"rows": [{"target_id": "H1001", "replacement_required": "false"}]})
    _write_csv(tmp_path / "watchlist.csv", [])
    _write_csv(tmp_path / "current_targets.csv", [])
    args = mod.parse_args(_args(tmp_path))

    payload = mod.build_payload(args)

    assert payload["summary"]["replacement_queue_status"] == "no_replacements_required"
    assert payload["summary"]["replacement_required_target_count"] == 0
    assert payload["rows"] == []
