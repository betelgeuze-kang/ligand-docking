from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan as mod


def _write_coordinate_intake(path: Path) -> None:
    dataset_dir = path.parent / "dataset"
    present_receptor = dataset_dir / "new2" / "new2_receptor.pdb"
    present_receptor.parent.mkdir(parents=True, exist_ok=True)
    present_receptor.write_text("ATOM      1  CA  ALA A   1       1.000   1.000   1.000  1.00 20.00           C\n", encoding="utf-8")
    missing_receptor = dataset_dir / "new1" / "new1_receptor.pdb"
    missing_complex = dataset_dir / "new1" / "new1_complex.pdb"
    payload = {
        "summary": {
            "status": "refine_tier_public_benchmark_statistical_support_coordinate_intake_ready",
            "coordinate_intake_row_count": 2,
            "coordinate_validation_pass_row_count": 1,
            "coordinate_validation_blocked_row_count": 1,
        },
        "intake_rows": [
            {
                "candidate_queue_id": "stat_support_candidate_001",
                "expansion_slot_id": "refine_tier_public_benchmark_stat_support_expansion_001",
                "suggested_work_order_id": "refine_tier_public_benchmark_stat_support_expansion_001",
                "target_id": "new1",
                "pose_id": "new1_020",
                "required_split": "holdout",
                "suggested_split": "holdout",
                "current_receptor_coordinate_artifact": str(missing_receptor),
                "receptor_coordinate_artifact_present": False,
                "suggested_public_coordinate_urls": (
                    "https://files.rcsb.org/download/NEW1.cif;"
                    "https://files.rcsb.org/download/NEW1.pdb"
                ),
                "suggested_local_coordinate_paths": f"{missing_receptor};{missing_complex}",
                "operator_coordinate_source_review_required": "confirm_source",
            },
            {
                "candidate_queue_id": "stat_support_candidate_002",
                "expansion_slot_id": "refine_tier_public_benchmark_stat_support_expansion_002",
                "suggested_work_order_id": "refine_tier_public_benchmark_stat_support_expansion_002",
                "target_id": "new2",
                "pose_id": "new2_030",
                "required_split": "fit_or_holdout",
                "suggested_split": "fit",
                "current_receptor_coordinate_artifact": str(present_receptor),
                "receptor_coordinate_artifact_present": True,
                "suggested_public_coordinate_urls": "https://files.rcsb.org/download/NEW2.pdb",
                "suggested_local_coordinate_paths": str(present_receptor),
                "operator_coordinate_source_review_required": "confirm_source",
            },
        ],
        "validation_rows": [
            {
                "candidate_queue_id": "stat_support_candidate_001",
                "target_id": "new1",
                "coordinate_validation_status": "blocked",
            },
            {
                "candidate_queue_id": "stat_support_candidate_002",
                "target_id": "new2",
                "coordinate_validation_status": "pass",
            },
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def test_coordinate_fetch_plan_separates_missing_and_validated_coordinates(tmp_path: Path) -> None:
    coordinate_intake = tmp_path / "runs" / "coordinate_intake.json"
    _write_coordinate_intake(coordinate_intake)

    payload = mod.build_refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan(
        coordinate_intake_json=coordinate_intake,
        root=tmp_path,
    )
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["status"] == "refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan_ready"
    assert summary["coordinate_fetch_row_count"] == 2
    assert summary["coordinate_fetch_required_row_count"] == 1
    assert summary["coordinate_fetch_blocked_row_count"] == 1
    assert summary["coordinate_fetch_primary_url_row_count"] == 2
    assert summary["coordinate_fetch_staging_destination_row_count"] == 2
    assert summary["coordinate_fetch_current_artifact_present_row_count"] == 1
    assert summary["coordinate_fetch_ready_for_validation_row_count"] == 1
    assert summary["coordinate_fetch_external_download_executed"] is False
    assert rows[0]["source_url_primary"] == "https://files.rcsb.org/download/NEW1.pdb"
    assert rows[0]["staging_destination_path"].endswith("new1_complex.pdb")
    assert rows[0]["fetch_required"] is True
    assert rows[1]["coordinate_fetch_status"] == "coordinate_artifact_already_validated"
    assert all(row["external_state_mutated"] is False for row in rows)


def test_coordinate_fetch_plan_cli_writes_json_csv_and_markdown(tmp_path: Path) -> None:
    coordinate_intake = tmp_path / "coordinate_intake.json"
    out_json = tmp_path / "fetch_plan.json"
    out_csv = tmp_path / "fetch_plan.csv"
    out_md = tmp_path / "fetch_plan.md"
    _write_coordinate_intake(coordinate_intake)

    mod.main(
        [
            "--coordinate-intake-json",
            str(coordinate_intake),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    rows = list(csv.DictReader(out_csv.open("r", encoding="utf-8", newline="")))
    assert payload["summary"]["coordinate_fetch_row_count"] == 2
    assert len(rows) == 2
    assert "Coordinate Fetch Plan" in out_md.read_text(encoding="utf-8")
