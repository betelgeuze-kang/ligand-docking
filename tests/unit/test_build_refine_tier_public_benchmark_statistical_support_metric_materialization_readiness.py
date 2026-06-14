import csv
import json
from pathlib import Path

from tools.product import (
    build_refine_tier_public_benchmark_statistical_support_metric_materialization_readiness as mod,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_validation_csv(path: Path) -> None:
    rows = [
        {
            "candidate_queue_id": "stat_support_candidate_001",
            "target_id": "new1",
            "pose_id": "new1_001",
            "receptor_coordinate_artifact": "dataset/new1/new1_complex.pdb",
            "coordinate_validation_status": "pass",
            "blockers": "",
        },
        {
            "candidate_queue_id": "stat_support_candidate_002",
            "target_id": "new2",
            "pose_id": "new2_002",
            "receptor_coordinate_artifact": "",
            "coordinate_validation_status": "blocked",
            "blockers": "receptor_coordinate_missing",
        },
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _candidate_queue(tmp_path: Path) -> dict:
    ligand_1 = tmp_path / "dataset" / "data_5_sdf" / "new1_001"
    ligand_2 = tmp_path / "dataset" / "data_5_sdf" / "new2_002"
    ligand_1.parent.mkdir(parents=True, exist_ok=True)
    ligand_1.write_text("ligand1\n", encoding="utf-8")
    ligand_2.write_text("ligand2\n", encoding="utf-8")
    return {
        "summary": {
            "status": "refine_tier_public_benchmark_statistical_support_candidate_queue_ready",
            "selected_candidate_count": 2,
        },
        "rows": [
            {
                "candidate_queue_id": "stat_support_candidate_001",
                "expansion_slot_id": "expansion_001",
                "suggested_work_order_id": "work_001",
                "target_id": "new1",
                "pose_id": "new1_001",
                "required_split": "holdout",
                "suggested_split": "holdout",
                "ligand_pose_artifact": "dataset/data_5_sdf/new1_001",
                "ligand_pose_artifact_present": True,
                "deltaG_experimental_kcal_mol": "-8.0",
                "dockq_source_artifact": "runs/sources/work_001_dockq.json",
                "lddt_pli_source_artifact": "runs/sources/work_001_lddt_pli.json",
                "internal_deltaG_source_artifact": "runs/sources/work_001_internal_deltaG.json",
            },
            {
                "candidate_queue_id": "stat_support_candidate_002",
                "expansion_slot_id": "expansion_002",
                "suggested_work_order_id": "work_002",
                "target_id": "new2",
                "pose_id": "new2_002",
                "required_split": "fit_or_holdout",
                "suggested_split": "fit",
                "ligand_pose_artifact": "dataset/data_5_sdf/new2_002",
                "ligand_pose_artifact_present": True,
                "deltaG_experimental_kcal_mol": "-7.0",
                "dockq_source_artifact": "runs/sources/work_002_dockq.json",
                "lddt_pli_source_artifact": "runs/sources/work_002_lddt_pli.json",
                "internal_deltaG_source_artifact": "runs/sources/work_002_internal_deltaG.json",
            },
        ],
    }


def _coordinate_intake() -> dict:
    return {
        "summary": {
            "status": "refine_tier_public_benchmark_statistical_support_coordinate_intake_ready",
        },
        "validation_rows": [
            {
                "candidate_queue_id": "stat_support_candidate_001",
                "target_id": "new1",
                "pose_id": "new1_001",
                "receptor_coordinate_artifact": "dataset/new1/new1_complex.pdb",
                "coordinate_validation_status": "pass",
                "blockers": "",
            },
            {
                "candidate_queue_id": "stat_support_candidate_002",
                "target_id": "new2",
                "pose_id": "new2_002",
                "receptor_coordinate_artifact": "",
                "coordinate_validation_status": "blocked",
                "blockers": "receptor_coordinate_missing",
            },
        ],
    }


def test_metric_materialization_readiness_counts_ready_and_blocked_candidates(
    tmp_path: Path,
) -> None:
    candidate_queue_json = tmp_path / "runs" / "candidate_queue.json"
    coordinate_intake_json = tmp_path / "runs" / "coordinate_intake.json"
    validation_csv = tmp_path / "runs" / "coordinate_validation.csv"
    _write_json(candidate_queue_json, _candidate_queue(tmp_path))
    _write_json(coordinate_intake_json, _coordinate_intake())
    _write_validation_csv(validation_csv)

    payload = mod.build_refine_tier_public_benchmark_statistical_support_metric_materialization_readiness(
        candidate_queue_json=candidate_queue_json,
        coordinate_intake_json=coordinate_intake_json,
        coordinate_validation_csv=validation_csv,
        root=tmp_path,
    )

    summary = payload["summary"]
    assert summary["status"] == (
        "refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_ready"
    )
    assert summary["metric_materialization_readiness_ready"] is True
    assert summary["metric_materialization_all_candidates_ready"] is False
    assert summary["metric_materialization_row_count"] == 2
    assert summary["metric_materialization_candidate_ready_count"] == 1
    assert summary["metric_materialization_candidate_blocked_count"] == 1
    assert summary["coordinate_validation_pass_row_count"] == 1
    assert summary["coordinate_validation_blocked_row_count"] == 1
    assert summary["planned_metric_source_payload_count"] == 6
    assert summary["existing_metric_source_payload_count"] == 0
    assert summary["canonical_intake_promotion_allowed"] is False
    assert summary["external_state_mutated"] is False
    assert payload["rows"][0]["metric_materialization_status"] == (
        "ready_for_metric_source_materialization"
    )
    assert payload["rows"][1]["metric_materialization_blockers"] == "coordinate_validation_not_pass"


def test_metric_materialization_readiness_blocks_missing_coordinate_intake(
    tmp_path: Path,
) -> None:
    candidate_queue_json = tmp_path / "runs" / "candidate_queue.json"
    validation_csv = tmp_path / "runs" / "coordinate_validation.csv"
    _write_json(candidate_queue_json, _candidate_queue(tmp_path))
    _write_validation_csv(validation_csv)

    payload = mod.build_refine_tier_public_benchmark_statistical_support_metric_materialization_readiness(
        candidate_queue_json=candidate_queue_json,
        coordinate_intake_json=tmp_path / "runs" / "missing.json",
        coordinate_validation_csv=validation_csv,
        root=tmp_path,
    )

    assert payload["summary"]["status"] == (
        "blocked_refine_tier_public_benchmark_statistical_support_metric_materialization_readiness"
    )
    assert payload["summary"]["blockers"] == ["coordinate_intake_missing", "coordinate_intake_not_ready"]


def test_metric_materialization_readiness_cli_writes_outputs(tmp_path: Path) -> None:
    candidate_queue_json = tmp_path / "runs" / "candidate_queue.json"
    coordinate_intake_json = tmp_path / "runs" / "coordinate_intake.json"
    validation_csv = tmp_path / "runs" / "coordinate_validation.csv"
    out_json = tmp_path / "runs" / "readiness.json"
    out_csv = tmp_path / "runs" / "readiness.csv"
    out_md = tmp_path / "runs" / "readiness.md"
    _write_json(candidate_queue_json, _candidate_queue(tmp_path))
    _write_json(coordinate_intake_json, _coordinate_intake())
    _write_validation_csv(validation_csv)

    mod.main(
        [
            "--candidate-queue-json",
            str(candidate_queue_json),
            "--coordinate-intake-json",
            str(coordinate_intake_json),
            "--coordinate-validation-csv",
            str(validation_csv),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["metric_materialization_row_count"] == 2
    assert "blocked_metric_source_materialization_inputs" in out_csv.read_text(encoding="utf-8")
    assert "Metric Materialization Readiness" in out_md.read_text(encoding="utf-8")
