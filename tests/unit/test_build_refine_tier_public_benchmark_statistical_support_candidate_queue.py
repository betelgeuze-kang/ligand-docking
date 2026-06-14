from __future__ import annotations

import csv
import io
import json
import tarfile
from pathlib import Path

from tools.product import build_refine_tier_public_benchmark_statistical_support_candidate_queue as mod


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_stat_work_order(path: Path, slot_count: int = 3) -> None:
    rows = []
    for index in range(1, slot_count + 1):
        required_split = "holdout" if index <= 2 else "fit_or_holdout"
        rows.append(
            {
                "expansion_slot_id": f"refine_tier_public_benchmark_stat_support_expansion_{index:03d}",
                "required_split": required_split,
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "refine_tier_public_benchmark_statistical_support_work_order_ready",
                    "expansion_slot_count": slot_count,
                },
                "rows": rows,
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _add_tar_text(archive: tarfile.TarFile, name: str, text: str) -> None:
    data = text.encode("utf-8")
    info = tarfile.TarInfo(name)
    info.size = len(data)
    archive.addfile(info, io.BytesIO(data))


def test_statistical_support_candidate_queue_selects_nonoverlapping_slots(tmp_path: Path) -> None:
    stat_json = tmp_path / "runs" / "stat.json"
    current_work_order = tmp_path / "runs" / "work_order.csv"
    seed_csv = tmp_path / "runs" / "seed.csv"
    affinity_tsv = tmp_path / "data" / "affinity.tsv"
    dataset_dir = tmp_path / "data" / "pdbbind"
    _write_stat_work_order(stat_json)
    _write_csv(
        current_work_order,
        [{"work_order_id": "seeded_001", "target_id": "old1"}],
        ["work_order_id", "target_id"],
    )
    seed_rows = [
        {
            "suite_id": "pdbbind_casf_pose_affinity",
            "complex_id": "old1",
            "pose_id": "old1_001",
            "pose_rmsd_A": "0.01",
            "pose_artifact": str(dataset_dir / "data_5_sdf" / "old1_001"),
            "blocker_count": 0,
            "blockers": "",
        },
        {
            "suite_id": "pdbbind_casf_pose_affinity",
            "complex_id": "new1",
            "pose_id": "new1_020",
            "pose_rmsd_A": "0.20",
            "pose_artifact": str(dataset_dir / "data_5_sdf" / "new1_020"),
            "blocker_count": 0,
            "blockers": "",
        },
        {
            "suite_id": "pdbbind_casf_pose_affinity",
            "complex_id": "new1",
            "pose_id": "new1_090",
            "pose_rmsd_A": "0.90",
            "pose_artifact": str(dataset_dir / "data_5_sdf" / "new1_090"),
            "blocker_count": 0,
            "blockers": "",
        },
        {
            "suite_id": "pdbbind_casf_pose_affinity",
            "complex_id": "new2",
            "pose_id": "new2_030",
            "pose_rmsd_A": "0.30",
            "pose_artifact": str(dataset_dir / "data_5_sdf" / "new2_030"),
            "blocker_count": 0,
            "blockers": "",
        },
        {
            "suite_id": "pdbbind_casf_pose_affinity",
            "complex_id": "new3",
            "pose_id": "new3_040",
            "pose_rmsd_A": "0.40",
            "pose_artifact": str(dataset_dir / "data_5_sdf" / "new3_040"),
            "blocker_count": 0,
            "blockers": "",
        },
    ]
    for row in seed_rows:
        path = Path(str(row["pose_artifact"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("pose\n", encoding="utf-8")
    _write_csv(
        seed_csv,
        seed_rows,
        ["suite_id", "complex_id", "pose_id", "pose_rmsd_A", "pose_artifact", "blocker_count", "blockers"],
    )
    affinity_tsv.parent.mkdir(parents=True, exist_ok=True)
    affinity_tsv.write_text("new1\t7.0\nnew2\t8.0\nnew3\t9.0\n", encoding="utf-8")

    payload = mod.build_refine_tier_public_benchmark_statistical_support_candidate_queue(
        statistical_support_work_order_json=stat_json,
        current_work_order_csv=current_work_order,
        seed_csv=seed_csv,
        affinity_tsv=affinity_tsv,
        dataset_dir=dataset_dir,
        root=tmp_path,
    )
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["status"] == "refine_tier_public_benchmark_statistical_support_candidate_queue_ready"
    assert summary["selected_candidate_count"] == 3
    assert summary["holdout_selected_candidate_count"] == 2
    assert summary["fit_or_holdout_selected_candidate_count"] == 1
    assert summary["candidate_source_excluded_existing_target_row_count"] == 1
    assert summary["ligand_pose_artifact_present_count"] == 3
    assert summary["receptor_coordinate_artifact_present_count"] == 0
    assert summary["experimental_deltaG_prefilled_count"] == 3
    assert rows[0]["target_id"] == "new1"
    assert rows[0]["pose_id"] == "new1_020"
    assert rows[0]["required_split"] == "holdout"
    assert rows[0]["candidate_blockers"] == "receptor_coordinate_artifact_missing"
    assert rows[2]["suggested_split"] == "fit"
    assert rows[2]["candidate_ready_for_canonical_intake"] is False
    assert all(row["external_state_mutated"] is False for row in rows)


def test_statistical_support_candidate_queue_uses_local_archive_receptor_member(tmp_path: Path) -> None:
    stat_json = tmp_path / "runs" / "stat.json"
    current_work_order = tmp_path / "runs" / "work_order.csv"
    seed_csv = tmp_path / "runs" / "seed.csv"
    affinity_tsv = tmp_path / "data" / "affinity.tsv"
    dataset_dir = tmp_path / "data" / "pdbbind"
    ligand = dataset_dir / "data_5_sdf" / "new1_020"
    ligand.parent.mkdir(parents=True, exist_ok=True)
    ligand.write_text("pose\n", encoding="utf-8")
    archive_path = dataset_dir / "local_coordinates.tar"
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "w") as archive:
        _add_tar_text(archive, "pdbbind/new1/new1_protein.pdb", "ATOM      1  CA  ALA A   1\n")
    _write_stat_work_order(stat_json, slot_count=1)
    _write_csv(current_work_order, [], ["work_order_id", "target_id"])
    _write_csv(
        seed_csv,
        [
            {
                "suite_id": "pdbbind_casf_pose_affinity",
                "complex_id": "new1",
                "pose_id": "new1_020",
                "pose_rmsd_A": "0.20",
                "pose_artifact": str(ligand),
                "blocker_count": 0,
                "blockers": "",
            }
        ],
        ["suite_id", "complex_id", "pose_id", "pose_rmsd_A", "pose_artifact", "blocker_count", "blockers"],
    )
    affinity_tsv.parent.mkdir(parents=True, exist_ok=True)
    affinity_tsv.write_text("new1\t7.0\n", encoding="utf-8")

    payload = mod.build_refine_tier_public_benchmark_statistical_support_candidate_queue(
        statistical_support_work_order_json=stat_json,
        current_work_order_csv=current_work_order,
        seed_csv=seed_csv,
        affinity_tsv=affinity_tsv,
        dataset_dir=dataset_dir,
        root=tmp_path,
    )

    summary = payload["summary"]
    row = payload["rows"][0]
    assert summary["receptor_coordinate_artifact_present_count"] == 1
    assert summary["candidate_ready_for_metric_materialization_count"] == 1
    assert row["receptor_coordinate_artifact"].endswith(
        "local_coordinates.tar::pdbbind/new1/new1_protein.pdb"
    )
    assert row["receptor_coordinate_artifact_present"] is True
    assert row["candidate_ready_for_metric_materialization"] is True
    assert row["candidate_blockers"] == ""


def test_statistical_support_candidate_queue_cli_writes_outputs(tmp_path: Path) -> None:
    stat_json = tmp_path / "stat.json"
    current_work_order = tmp_path / "work_order.csv"
    seed_csv = tmp_path / "seed.csv"
    affinity_tsv = tmp_path / "affinity.tsv"
    dataset_dir = tmp_path / "dataset"
    out_json = tmp_path / "queue.json"
    out_csv = tmp_path / "queue.csv"
    out_md = tmp_path / "queue.md"
    _write_stat_work_order(stat_json, slot_count=1)
    _write_csv(current_work_order, [], ["work_order_id", "target_id"])
    ligand = dataset_dir / "data_5_sdf" / "new1_020"
    ligand.parent.mkdir(parents=True, exist_ok=True)
    ligand.write_text("pose\n", encoding="utf-8")
    _write_csv(
        seed_csv,
        [
            {
                "suite_id": "pdbbind_casf_pose_affinity",
                "complex_id": "new1",
                "pose_id": "new1_020",
                "pose_rmsd_A": "0.20",
                "pose_artifact": str(ligand),
                "blocker_count": 0,
                "blockers": "",
            }
        ],
        ["suite_id", "complex_id", "pose_id", "pose_rmsd_A", "pose_artifact", "blocker_count", "blockers"],
    )
    affinity_tsv.write_text("new1\t7.0\n", encoding="utf-8")

    mod.main(
        [
            "--statistical-support-work-order-json",
            str(stat_json),
            "--current-work-order-csv",
            str(current_work_order),
            "--seed-csv",
            str(seed_csv),
            "--affinity-tsv",
            str(affinity_tsv),
            "--dataset-dir",
            str(dataset_dir),
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
    assert payload["summary"]["selected_candidate_count"] == 1
    assert len(rows) == 1
    assert "Statistical Support Candidate Queue" in out_md.read_text(encoding="utf-8")
