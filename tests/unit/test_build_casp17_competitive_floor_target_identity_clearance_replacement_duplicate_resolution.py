from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import (
    build_casp17_competitive_floor_target_identity_clearance_replacement_duplicate_resolution as mod,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _args(tmp_path: Path) -> list[str]:
    return [
        "--replacement-queue-json",
        str(tmp_path / "queue.json"),
        "--replacement-workorder-json",
        str(tmp_path / "workorder.json"),
        "--replacement-source-repair-json",
        str(tmp_path / "source_repair.json"),
        "--out-json",
        str(tmp_path / "duplicate_resolution.json"),
        "--out-csv",
        str(tmp_path / "duplicate_resolution.csv"),
        "--out-md",
        str(tmp_path / "DUPLICATE_RESOLUTION.md"),
    ]


def _queue_row(replace_id: str, candidate_id: str, *, rank: int, status: str = mod.READY_STATUS) -> dict[str, str]:
    blockers = "" if status == mod.READY_STATUS else "local_prediction_missing"
    return {
        "replace_target_id": replace_id,
        "replace_target_name": f"Blocked {replace_id}",
        "candidate_target_id": candidate_id,
        "candidate_target_name": f"Candidate {candidate_id}",
        "candidate_rank": str(rank),
        "candidate_status": status,
        "blockers": blockers,
        "prediction_pdb": f"runs/casp17_prediction_jobs_current/{candidate_id}/{candidate_id}_model_1.pdb"
        if status == mod.READY_STATUS
        else "",
        "raw_validation_json": (
            f"runs/casp17_internal_physics_raw_validations_current/{candidate_id}_raw_confidence_calibration.json"
            if status == mod.READY_STATUS
            else ""
        ),
        "scorecard_json": f"runs/casp17_internal_scorecards_current/{candidate_id}_internal_scorecard.json"
        if status == mod.READY_STATUS
        else "",
    }


def _source_row(candidate_id: str, *, status: str = mod.SOURCE_READY_STATUS, blockers: str = "") -> dict[str, str]:
    return {
        "candidate_target_id": candidate_id,
        "candidate_target_name": f"Candidate {candidate_id}",
        "source_repair_status": status,
        "blockers": blockers,
        "next_action": "move this replacement candidate into operator clearance review"
        if status == mod.SOURCE_READY_STATUS
        else "repair this source candidate before replacement review",
    }


def test_duplicate_resolution_finds_safe_unique_ready_candidate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_json(
        tmp_path / "queue.json",
        {
            "rows": [
                _queue_row("H1001", "H2001", rank=1),
                _queue_row("H1002", "H2001", rank=1),
                _queue_row("H1002", "H2002", rank=2),
            ]
        },
    )
    _write_json(
        tmp_path / "workorder.json",
        {
            "rows": [
                {
                    "replace_target_id": "H1001",
                    "target_id": "H2001",
                    "selection_status": "selected_for_replacement_workorder",
                },
                {
                    "replace_target_id": "H1002",
                    "target_id": "H2001",
                    "selection_status": mod.DUPLICATE_STATUS,
                    "duplicate_candidate_for_replace_target_ids": "H1001",
                },
            ]
        },
    )
    _write_json(
        tmp_path / "source_repair.json",
        {"rows": [_source_row("H2001"), _source_row("H2002")]},
    )
    args = mod.parse_args(_args(tmp_path))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["duplicate_resolution_status"] == "ready_unique_replacement_available"
    assert payload["summary"]["safe_unique_ready_candidate_count"] == 1
    assert payload["summary"]["duplicate_ready_candidate_count"] == 1
    by_candidate = {row["candidate_target_id"]: row for row in payload["rows"]}
    assert by_candidate["H2001"]["resolution_status"] == mod.DUPLICATE_STATUS
    assert by_candidate["H2002"]["resolution_status"] == "safe_unique_ready_candidate"
    assert by_candidate["H2002"]["safe_unique_ready_candidate"] == "true"
    csv_rows = _read_csv(tmp_path / "duplicate_resolution.csv")
    assert len(csv_rows) == 2
    assert (tmp_path / "DUPLICATE_RESOLUTION.md").is_file()


def test_duplicate_resolution_blocks_when_only_duplicate_and_unsafe_alternatives(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_json(
        tmp_path / "queue.json",
        {
            "rows": [
                _queue_row("H1002", "H2001", rank=1),
                _queue_row("H1002", "H2003", rank=2, status="blocked_missing_local_prediction"),
                _queue_row("H1002", "H2004", rank=3, status="blocked_current_target_collision"),
            ]
        },
    )
    _write_json(
        tmp_path / "workorder.json",
        {
            "rows": [
                {
                    "replace_target_id": "H1001",
                    "target_id": "H2001",
                    "selection_status": "selected_for_replacement_workorder",
                },
                {
                    "replace_target_id": "H1002",
                    "target_id": "H2001",
                    "selection_status": mod.DUPLICATE_STATUS,
                    "duplicate_candidate_for_replace_target_ids": "H1001",
                },
            ]
        },
    )
    _write_json(
        tmp_path / "source_repair.json",
        {
            "rows": [
                _source_row("H2001"),
                _source_row("H2003", status="blocked_cancelled_target", blockers="target_cancelled"),
                _source_row(
                    "H2004",
                    status="blocked_current_target_collision",
                    blockers="current_target_name_collision",
                ),
            ]
        },
    )
    args = mod.parse_args(_args(tmp_path))

    payload = mod.build_payload(args)

    assert payload["summary"]["duplicate_resolution_status"] == "operator_decision_required"
    assert payload["summary"]["safe_unique_ready_candidate_count"] == 0
    assert payload["summary"]["duplicate_ready_candidate_count"] == 1
    assert payload["summary"]["blocked_cancelled_count"] == 1
    assert payload["summary"]["blocked_current_collision_count"] == 1
    assert payload["summary"]["blocked_missing_prediction_count"] == 2
    assert payload["summary"]["first_open_replace_target_id"] == "H1002"
    assert payload["summary"]["first_open_next_action"] == mod.NO_SAFE_UNIQUE_ACTION
    by_candidate = {row["candidate_target_id"]: row for row in payload["rows"]}
    assert by_candidate["H2001"]["resolution_status"] == mod.DUPLICATE_STATUS
    assert "duplicate_candidate_target_id" in by_candidate["H2001"]["blockers"]
    assert by_candidate["H2003"]["resolution_status"] == "blocked_cancelled_target"
    assert by_candidate["H2004"]["resolution_status"] == "blocked_current_target_collision"
