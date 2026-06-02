from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_competitive_floor_target_identity_clearance_replacement_workorder as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _args(tmp_path: Path) -> list[str]:
    return [
        "--replacement-queue-json",
        str(tmp_path / "replacement_queue.json"),
        "--out-dir",
        str(tmp_path / "replacement_workorders"),
        "--out-json",
        str(tmp_path / "replacement_workorder.json"),
        "--out-csv",
        str(tmp_path / "replacement_workorder.csv"),
        "--out-md",
        str(tmp_path / "REPLACEMENT_WORKORDER.md"),
    ]


def _ready_row(replace_id: str, candidate_id: str, *, rank: int = 1) -> dict[str, str]:
    return {
        "replace_target_id": replace_id,
        "replace_target_name": f"Blocked {replace_id}",
        "candidate_target_id": candidate_id,
        "candidate_target_name": f"Candidate {candidate_id}",
        "candidate_status": "candidate_ready_for_operator_clearance",
        "candidate_rank": str(rank),
        "stoichiometry": "A1B1",
        "prediction_pdb": f"runs/casp17_prediction_jobs_current/{candidate_id}/{candidate_id}_model_1.pdb",
        "raw_validation_json": (
            f"runs/casp17_internal_physics_raw_validations_current/"
            f"{candidate_id}_raw_confidence_calibration.json"
        ),
        "scorecard_json": f"runs/casp17_internal_scorecards_current/{candidate_id}_internal_scorecard.json",
    }


def test_replacement_workorder_selects_unique_ready_candidate_and_blocks_duplicate(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_json(
        tmp_path / "replacement_queue.json",
        {
            "summary": {"replacement_queue_status": "candidate_ready_for_operator_clearance"},
            "rows": [_ready_row("H1001", "H2001"), _ready_row("H1002", "H2001")],
        },
    )
    args = mod.parse_args(_args(tmp_path))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["replacement_workorder_status"] == (
        "partial_replacement_workorders_ready_for_operator_intake"
    )
    assert payload["summary"]["selected_workorder_count"] == 1
    assert payload["summary"]["duplicate_candidate_blocked_count"] == 1
    assert payload["summary"]["native_dropzone_readme_count"] == 1
    by_replace = {row["replace_target_id"]: row for row in payload["rows"]}
    assert by_replace["H1001"]["selection_status"] == "selected_for_replacement_workorder"
    assert by_replace["H1001"]["scope"] == "complex"
    assert by_replace["H1001"]["native_dropzone_pdb"].endswith("H2001_native.pdb")
    assert by_replace["H1001"]["native_dropzone_folder"].endswith("native")
    assert by_replace["H1001"]["native_dropzone_readme"].endswith("native/README.md")
    assert Path(by_replace["H1001"]["native_dropzone_readme"]).is_file()
    assert by_replace["H1002"]["selection_status"] == "blocked_duplicate_candidate_assignment"
    assert by_replace["H1002"]["duplicate_candidate_for_replace_target_ids"] == "H1001"
    assert (tmp_path / "replacement_workorder.json").is_file()
    assert (tmp_path / "REPLACEMENT_WORKORDER.md").is_file()
    manifest_rows = _read_csv(Path(by_replace["H1001"]["manifest_stub_csv"]))
    assert manifest_rows[0]["benchmark_id"] == "hist_H2001_replacement_for_H1001"
    assert manifest_rows[0]["target_id"] == "H2001"


def test_replacement_workorder_uses_next_ready_candidate_when_first_is_duplicate(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_json(
        tmp_path / "replacement_queue.json",
        {
            "rows": [
                _ready_row("H1001", "H2001", rank=1),
                _ready_row("H1002", "H2001", rank=1),
                _ready_row("H1002", "H2002", rank=2),
            ]
        },
    )
    args = mod.parse_args(_args(tmp_path))

    payload = mod.build_payload(args)

    assert payload["summary"]["replacement_workorder_status"] == (
        "replacement_workorders_ready_for_operator_intake"
    )
    assert payload["summary"]["selected_workorder_count"] == 2
    by_replace = {row["replace_target_id"]: row for row in payload["rows"]}
    assert by_replace["H1001"]["target_id"] == "H2001"
    assert by_replace["H1002"]["target_id"] == "H2002"


def test_replacement_workorder_reports_no_ready_candidate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_json(
        tmp_path / "replacement_queue.json",
        {
            "rows": [
                {
                    "replace_target_id": "H1001",
                    "replace_target_name": "Blocked target",
                    "candidate_target_id": "H2001",
                    "candidate_target_name": "Missing prediction",
                    "candidate_status": "blocked_missing_local_prediction",
                    "candidate_rank": "1",
                    "stoichiometry": "A1",
                }
            ]
        },
    )
    args = mod.parse_args(_args(tmp_path))

    payload = mod.build_payload(args)

    assert payload["summary"]["replacement_workorder_status"] == "blocked_replacement_workorders"
    assert payload["summary"]["selected_workorder_count"] == 0
    assert payload["summary"]["no_ready_candidate_blocked_count"] == 1
    assert payload["rows"][0]["selection_status"] == "blocked_no_ready_replacement_candidate"
    assert "ready_replacement_candidate_missing" in payload["rows"][0]["blockers"]
