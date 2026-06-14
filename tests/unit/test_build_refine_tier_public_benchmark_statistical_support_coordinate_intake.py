from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_refine_tier_public_benchmark_statistical_support_coordinate_intake as mod


def _pdb_text(residue_count: int = 5, atoms_per_residue: int = 5) -> str:
    lines = []
    atom_index = 1
    for residue_index in range(1, residue_count + 1):
        for offset in range(atoms_per_residue):
            lines.append(
                f"ATOM  {atom_index:5d}  CA  ALA A{residue_index:4d}    "
                f"{float(atom_index):8.3f}{float(offset):8.3f}{float(residue_index):8.3f}"
                "  1.00 20.00           C"
            )
            atom_index += 1
    lines.append("END")
    return "\n".join(lines) + "\n"


def _candidate_queue(path: Path, receptor_path: Path) -> None:
    rows = [
        {
            "candidate_queue_id": "stat_support_candidate_001",
            "expansion_slot_id": "refine_tier_public_benchmark_stat_support_expansion_001",
            "suggested_work_order_id": "refine_tier_public_benchmark_stat_support_expansion_001",
            "target_id": "new1",
            "pose_id": "new1_020",
            "required_split": "holdout",
            "suggested_split": "holdout",
            "ligand_pose_artifact": str(path.parent / "data_5_sdf" / "new1_020"),
            "ligand_pose_artifact_present": True,
            "receptor_coordinate_artifact": str(path.parent / "new1" / "new1_receptor.pdb"),
            "receptor_coordinate_artifact_present": False,
            "expected_archive_member_examples": "pdbbind/new1/new1_protein.pdb",
            "suggested_public_coordinate_urls": "https://files.rcsb.org/download/NEW1.cif",
            "suggested_local_coordinate_paths": str(path.parent / "new1" / "new1_receptor.pdb"),
        },
        {
            "candidate_queue_id": "stat_support_candidate_002",
            "expansion_slot_id": "refine_tier_public_benchmark_stat_support_expansion_002",
            "suggested_work_order_id": "refine_tier_public_benchmark_stat_support_expansion_002",
            "target_id": "new2",
            "pose_id": "new2_030",
            "required_split": "fit_or_holdout",
            "suggested_split": "fit",
            "ligand_pose_artifact": str(path.parent / "data_5_sdf" / "new2_030"),
            "ligand_pose_artifact_present": True,
            "receptor_coordinate_artifact": str(receptor_path),
            "receptor_coordinate_artifact_present": True,
            "expected_archive_member_examples": "pdbbind/new2/new2_protein.pdb",
            "suggested_public_coordinate_urls": "https://files.rcsb.org/download/NEW2.cif",
            "suggested_local_coordinate_paths": str(receptor_path),
        },
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "refine_tier_public_benchmark_statistical_support_candidate_queue_ready",
                    "selected_candidate_count": 2,
                    "experimental_deltaG_prefilled_count": 2,
                },
                "rows": rows,
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_coordinate_intake_validates_present_and_missing_receptor_coordinates(tmp_path: Path) -> None:
    queue_json = tmp_path / "runs" / "candidate_queue.json"
    receptor_path = tmp_path / "dataset" / "new2" / "new2_receptor.pdb"
    receptor_path.parent.mkdir(parents=True, exist_ok=True)
    receptor_path.write_text(_pdb_text(), encoding="utf-8")
    _candidate_queue(queue_json, receptor_path)

    payload = mod.build_refine_tier_public_benchmark_statistical_support_coordinate_intake(
        candidate_queue_json=queue_json,
        root=tmp_path,
    )
    summary = payload["summary"]
    intake_rows = payload["intake_rows"]
    validation_rows = payload["validation_rows"]

    assert summary["status"] == "refine_tier_public_benchmark_statistical_support_coordinate_intake_ready"
    assert summary["coordinate_intake_row_count"] == 2
    assert summary["coordinate_intake_artifact_present_row_count"] == 1
    assert summary["coordinate_intake_missing_row_count"] == 1
    assert summary["coordinate_validation_pass_row_count"] == 1
    assert summary["coordinate_validation_blocked_row_count"] == 1
    assert summary["coordinate_validation_missing_row_count"] == 1
    assert summary["candidate_ready_for_metric_materialization_count"] == 1
    assert summary["candidate_ready_for_canonical_intake_count"] == 0
    assert summary["coordinate_intake_suggested_local_path_candidate_count"] == 2
    assert summary["coordinate_intake_suggested_local_path_present_count"] == 1
    assert summary["coordinate_intake_suggested_local_path_present_target_count"] == 1
    assert summary["coordinate_intake_suggested_local_path_missing_target_count"] == 1
    assert summary["coordinate_intake_expected_archive_member_example_count"] == 2
    assert intake_rows[0]["coordinate_intake_status"] == "blocked_coordinate_artifact_missing"
    assert intake_rows[0]["suggested_local_coordinate_path_count"] == 1
    assert intake_rows[0]["suggested_local_coordinate_path_present_count"] == 0
    assert intake_rows[0]["local_coordinate_inventory_status"] == "no_local_coordinate_candidate_present"
    assert intake_rows[1]["suggested_local_coordinate_path_present_count"] == 1
    assert intake_rows[1]["first_present_suggested_local_coordinate_path"] == str(receptor_path)
    assert intake_rows[1]["local_coordinate_inventory_status"] == "local_coordinate_candidate_present"
    assert validation_rows[0]["coordinate_validation_status"] == "blocked"
    assert validation_rows[1]["coordinate_validation_status"] == "pass"
    assert validation_rows[1]["coordinate_atom_record_count"] == 25


def test_coordinate_intake_prefers_existing_complex_coordinate_from_suggested_paths(tmp_path: Path) -> None:
    queue_json = tmp_path / "runs" / "candidate_queue.json"
    dataset_dir = tmp_path / "dataset"
    receptor_path = dataset_dir / "new1" / "new1_receptor.pdb"
    complex_path = dataset_dir / "new1" / "new1_complex.pdb"
    complex_path.parent.mkdir(parents=True, exist_ok=True)
    complex_path.write_text(_pdb_text(), encoding="utf-8")
    ligand = dataset_dir / "data_5_sdf" / "new1_020"
    ligand.parent.mkdir(parents=True, exist_ok=True)
    ligand.write_text("pose\n", encoding="utf-8")
    queue_json.parent.mkdir(parents=True, exist_ok=True)
    queue_json.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "refine_tier_public_benchmark_statistical_support_candidate_queue_ready",
                    "selected_candidate_count": 1,
                    "experimental_deltaG_prefilled_count": 1,
                },
                "rows": [
                    {
                        "candidate_queue_id": "stat_support_candidate_001",
                        "expansion_slot_id": "refine_tier_public_benchmark_stat_support_expansion_001",
                        "suggested_work_order_id": (
                            "refine_tier_public_benchmark_stat_support_expansion_001"
                        ),
                        "target_id": "new1",
                        "pose_id": "new1_020",
                        "required_split": "holdout",
                        "suggested_split": "holdout",
                        "ligand_pose_artifact": str(ligand),
                        "ligand_pose_artifact_present": True,
                        "receptor_coordinate_artifact": str(receptor_path),
                        "receptor_coordinate_artifact_present": False,
                        "suggested_public_coordinate_urls": "https://files.rcsb.org/download/NEW1.pdb",
                        "suggested_local_coordinate_paths": f"{receptor_path};{complex_path}",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    payload = mod.build_refine_tier_public_benchmark_statistical_support_coordinate_intake(
        candidate_queue_json=queue_json,
        root=tmp_path,
    )

    assert payload["summary"]["coordinate_intake_artifact_present_row_count"] == 1
    assert payload["summary"]["coordinate_validation_pass_row_count"] == 1
    assert payload["summary"]["coordinate_intake_suggested_local_path_candidate_count"] == 2
    assert payload["summary"]["coordinate_intake_suggested_local_path_present_count"] == 1
    assert payload["summary"]["coordinate_intake_suggested_local_path_present_target_count"] == 1
    assert payload["intake_rows"][0]["current_receptor_coordinate_artifact"] == str(complex_path)
    assert payload["intake_rows"][0]["suggested_local_coordinate_path_count"] == 2
    assert payload["intake_rows"][0]["suggested_local_coordinate_path_present_count"] == 1
    assert payload["intake_rows"][0]["first_present_suggested_local_coordinate_path"] == str(complex_path)
    assert payload["validation_rows"][0]["coordinate_validation_status"] == "pass"


def test_coordinate_intake_cli_writes_json_csv_and_markdown(tmp_path: Path) -> None:
    queue_json = tmp_path / "candidate_queue.json"
    receptor_path = tmp_path / "dataset" / "new2" / "new2_receptor.pdb"
    receptor_path.parent.mkdir(parents=True, exist_ok=True)
    receptor_path.write_text(_pdb_text(), encoding="utf-8")
    _candidate_queue(queue_json, receptor_path)
    out_json = tmp_path / "coordinate_intake.json"
    out_intake_csv = tmp_path / "coordinate_intake.csv"
    out_validation_csv = tmp_path / "coordinate_validation.csv"
    out_md = tmp_path / "coordinate_intake.md"

    mod.main(
        [
            "--candidate-queue-json",
            str(queue_json),
            "--out-json",
            str(out_json),
            "--out-intake-csv",
            str(out_intake_csv),
            "--out-validation-csv",
            str(out_validation_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    intake_rows = list(csv.DictReader(out_intake_csv.open("r", encoding="utf-8", newline="")))
    validation_rows = list(csv.DictReader(out_validation_csv.open("r", encoding="utf-8", newline="")))
    assert payload["summary"]["coordinate_intake_row_count"] == 2
    assert payload["summary"]["coordinate_intake_suggested_local_path_present_target_count"] == 1
    assert len(intake_rows) == 2
    assert len(validation_rows) == 2
    assert intake_rows[0]["suggested_local_coordinate_path_present_count"] == "0"
    assert intake_rows[1]["suggested_local_coordinate_path_present_count"] == "1"
    assert "Statistical Support Coordinate Intake" in out_md.read_text(encoding="utf-8")
