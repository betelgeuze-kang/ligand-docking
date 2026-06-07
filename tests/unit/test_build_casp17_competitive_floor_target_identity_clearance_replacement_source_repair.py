from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_competitive_floor_target_identity_clearance_replacement_source_repair as mod


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


def _fasta(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(">candidate\nACDEFGHIKLMNPQRSTVWY\n", encoding="utf-8")


def _args(tmp_path: Path) -> list[str]:
    return [
        "--replacement-queue-json",
        str(tmp_path / "replacement_queue.json"),
        "--target-watchlist-csv",
        str(tmp_path / "watchlist.csv"),
        "--out-dir",
        str(tmp_path / "source_repair"),
        "--out-json",
        str(tmp_path / "source_repair.json"),
        "--out-csv",
        str(tmp_path / "source_repair.csv"),
        "--out-md",
        str(tmp_path / "SOURCE_REPAIR.md"),
    ]


def _candidate(candidate_id: str, *, blockers: str = "", candidate_status: str = "queued") -> dict[str, str]:
    return {
        "replace_target_id": "H1001",
        "replace_target_name": "Collision target",
        "candidate_target_id": candidate_id,
        "candidate_target_name": f"{candidate_id} candidate",
        "candidate_status": candidate_status,
        "prediction_pdb": "",
        "ts_prediction_pdb": "",
        "raw_validation_json": "",
        "scorecard_json": "",
        "blockers": blockers,
    }


def test_replacement_source_repair_splits_source_states(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_json(
        tmp_path / "replacement_queue.json",
        {
            "summary": {"replacement_queue_status": "blocked_replacement_candidates"},
            "rows": [
                _candidate("H2001", blockers="local_prediction_missing"),
                _candidate("H2002", blockers="current_target_name_collision,local_prediction_missing"),
                _candidate("H2003", blockers="local_prediction_missing"),
                _candidate("H2004", blockers="local_prediction_missing"),
                _candidate("H2005"),
                _candidate("H2006"),
            ],
        },
    )
    _write_csv(
        tmp_path / "watchlist.csv",
        [
            {
                "target_id": "H2001",
                "cancellation_date": "",
                "lane_recommendation": "out_of_scope_cancelled",
                "recommended_action": "ignore_for_selected_lanes",
            },
            {"target_id": "H2002", "lane_recommendation": "difficult_protein_complexes"},
            {"target_id": "H2003", "lane_recommendation": "difficult_protein_complexes"},
            {"target_id": "H2004", "lane_recommendation": "difficult_protein_complexes"},
            {"target_id": "H2005", "lane_recommendation": "difficult_protein_complexes"},
            {"target_id": "H2006", "lane_recommendation": "difficult_protein_complexes"},
        ],
    )
    _fasta(tmp_path / "casp17" / "replacement_source_fasta" / "H2004.fasta")
    _pdb(tmp_path / "runs" / "casp17_prediction_jobs_current" / "H2005" / "H2005_model_1.pdb")
    _fasta(tmp_path / "casp17" / "replacement_source_fasta" / "H2006.fasta")
    _pdb(tmp_path / "runs" / "casp17_prediction_jobs_current" / "H2006" / "H2006_model_1.pdb")
    _pdb(tmp_path / "runs" / "casp17_predictions_current" / "H2006TS.pdb")
    _write_json(
        tmp_path / "runs" / "casp17_internal_physics_raw_validations_current" / "H2006_raw_confidence_calibration.json",
        {"summary": {"target_id": "H2006"}},
    )
    _write_json(
        tmp_path / "runs" / "casp17_internal_scorecards_current" / "H2006_internal_scorecard.json",
        {"summary": {"target_id": "H2006"}},
    )
    args = mod.parse_args(_args(tmp_path))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["replacement_source_repair_status"] == "source_ready"
    assert summary["candidate_count"] == 6
    assert summary["source_ready_count"] == 1
    assert summary["ready_for_prediction_count"] == 1
    assert summary["ready_for_validation_scorecard_count"] == 1
    assert summary["awaiting_sequence_count"] == 1
    assert summary["blocked_cancelled_count"] == 1
    assert summary["blocked_current_collision_count"] == 1
    by_id = {row["candidate_target_id"]: row for row in payload["rows"]}
    assert by_id["H2001"]["source_repair_status"] == "blocked_cancelled_target"
    assert by_id["H2001"]["lane_recommendation"] == "out_of_scope_cancelled"
    assert by_id["H2002"]["source_repair_status"] == "blocked_current_target_collision"
    assert by_id["H2003"]["source_repair_status"] == "awaiting_sequence"
    assert by_id["H2004"]["source_repair_status"] == "ready_for_prediction_run"
    assert by_id["H2005"]["source_repair_status"] == "ready_for_validation_scorecard"
    assert by_id["H2006"]["source_repair_status"] == "source_ready"
    assert "--sequence-path" in by_id["H2004"]["validation_command"]
    assert "validate_casp17_backend_contract.py" in by_id["H2004"]["validation_command"]
    assert (
        "tools/casp17/build_casp17_competitive_floor_target_identity_clearance_replacement_scorecard.py"
        in by_id["H2004"]["scorecard_command"]
    )
    assert (tmp_path / by_id["H2001"]["source_repair_md"]).is_file()
    assert (tmp_path / "SOURCE_REPAIR.md").is_file()


def test_replacement_source_repair_handles_empty_queue(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_json(tmp_path / "replacement_queue.json", {"summary": {}, "rows": []})
    _write_csv(tmp_path / "watchlist.csv", [])
    args = mod.parse_args(_args(tmp_path))

    payload = mod.build_payload(args)

    assert payload["summary"]["replacement_source_repair_status"] == "no_replacement_candidates"
    assert payload["summary"]["candidate_count"] == 0
    assert payload["rows"] == []
