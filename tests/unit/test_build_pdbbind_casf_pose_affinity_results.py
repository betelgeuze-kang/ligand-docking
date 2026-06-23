from __future__ import annotations

import argparse
import csv
import pickle
from pathlib import Path

import pytest
from rdkit import Chem
from rdkit.Geometry import Point3D

from tools.build_pdbbind_casf_pose_affinity_results import build_results


def _mol(offset: float = 0.0) -> Chem.Mol:
    mol = Chem.AddHs(Chem.MolFromSmiles("CCO"))
    conformer = Chem.Conformer(mol.GetNumAtoms())
    for atom in mol.GetAtoms():
        idx = atom.GetIdx()
        conformer.SetAtomPosition(idx, Point3D(float(idx) + offset, 0.0, 0.0))
    mol.AddConformer(conformer)
    return mol


def _dump(path: Path, mol: Chem.Mol) -> None:
    path.write_bytes(pickle.dumps((mol, Chem.MolFromSmiles("CC"))))


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _metadata(path: Path, rows: list[dict[str, object]]) -> Path:
    fields = [
        "pose_id",
        "complex_id",
        "active_label",
        "affinity_label",
        "score",
        "baseline_score",
        "split_id",
        "runtime_ms",
        "peak_memory_mb",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})
    return path


def test_build_pdbbind_casf_pose_affinity_results_scores_pose_success(tmp_path: Path) -> None:
    data = tmp_path / "casf" / "data_5_sdf"
    data.mkdir(parents=True)
    _dump(data / "1abc", _mol())
    _dump(data / "1abc_1", _mol(offset=0.5))
    _dump(data / "1abc_2", _mol(offset=5.0))
    metadata = _metadata(
        tmp_path / "gold.csv",
        [
            {
                "pose_id": "1abc_1",
                "complex_id": "1abc",
                "active_label": "1",
                "affinity_label": "9.0",
                "score": "-9.0",
                "baseline_score": "-1.0",
                "split_id": "heldout",
                "runtime_ms": "10",
                "peak_memory_mb": "100",
            },
            {
                "pose_id": "1abc_2",
                "complex_id": "1abc",
                "active_label": "0",
                "affinity_label": "1.0",
                "score": "-1.0",
                "baseline_score": "-9.0",
                "split_id": "heldout",
                "runtime_ms": "12",
                "peak_memory_mb": "120",
            },
        ],
    )
    out_csv = tmp_path / "results.csv"

    payload = build_results(
        argparse.Namespace(
            dataset_artifact=str(tmp_path / "casf"),
            max_poses=0,
            threshold=0.35,
            pose_success_rmsd_a=2.0,
            out_csv=str(out_csv),
            out_json=str(tmp_path / "results.json"),
            out_md=str(tmp_path / "results.md"),
            gold_metadata_csv=str(metadata),
        )
    )

    assert payload["summary"]["status"] == "pdbbind_casf_pose_affinity_results_ready"
    assert payload["summary"]["pose_success_rate"] == 1.0
    assert payload["summary"]["pose_row_success_rate"] == 0.5
    assert payload["summary"]["complex_pose_success_rate"] == 1.0
    assert payload["summary"]["top1_mean_rmsd_A"] == 0.5
    assert payload["summary"]["top5_best_mean_rmsd_A"] == 0.5
    assert payload["summary"]["top1_pose_success_rate"] == 1.0
    assert payload["summary"]["top5_pose_success_rate"] == 1.0
    assert payload["summary"]["ranking_spearman"] == pytest.approx(1.0)
    assert payload["summary"]["baseline_ranking_spearman"] == pytest.approx(-1.0)
    assert payload["summary"]["refine_ranking_spearman_delta"] == pytest.approx(2.0)
    assert payload["summary"]["decoy_rejection_rate"] == 1.0
    assert payload["summary"]["mean_runtime_ms"] == 11.0
    assert payload["summary"]["peak_memory_mb"] == 120.0
    assert _rows(out_csv)[0]["complex_id"] == "1abc"


def test_build_pdbbind_casf_pose_affinity_results_uses_best_pose_per_complex(tmp_path: Path) -> None:
    data = tmp_path / "casf" / "data_5_sdf"
    data.mkdir(parents=True)
    _dump(data / "1abc", _mol())
    _dump(data / "1abc_1", _mol(offset=5.0))
    _dump(data / "1abc_2", _mol(offset=0.5))
    _dump(data / "1abc_3", _mol(offset=6.0))
    metadata = _metadata(
        tmp_path / "gold.csv",
        [
            {
                "pose_id": "1abc_1",
                "complex_id": "1abc",
                "active_label": "1",
                "affinity_label": "9.0",
                "score": "-9.0",
                "baseline_score": "-1.0",
                "runtime_ms": "10",
                "peak_memory_mb": "100",
            },
            {
                "pose_id": "1abc_2",
                "complex_id": "1abc",
                "active_label": "1",
                "affinity_label": "8.0",
                "score": "-8.0",
                "baseline_score": "-2.0",
                "runtime_ms": "11",
                "peak_memory_mb": "101",
            },
            {
                "pose_id": "1abc_3",
                "complex_id": "1abc",
                "active_label": "0",
                "affinity_label": "1.0",
                "score": "-1.0",
                "baseline_score": "-9.0",
                "runtime_ms": "12",
                "peak_memory_mb": "102",
            },
        ],
    )

    payload = build_results(
        argparse.Namespace(
            dataset_artifact=str(tmp_path / "casf"),
            max_poses=0,
            threshold=0.35,
            pose_success_rmsd_a=2.0,
            out_csv=str(tmp_path / "results.csv"),
            out_json=str(tmp_path / "results.json"),
            out_md=str(tmp_path / "results.md"),
            gold_metadata_csv=str(metadata),
        )
    )

    assert payload["summary"]["status"] == "pdbbind_casf_pose_affinity_results_ready"
    assert payload["summary"]["pose_row_success_rate"] == 1 / 3
    assert payload["summary"]["complex_pose_success_rate"] == 1.0
    assert payload["summary"]["top1_mean_rmsd_A"] == 5.0
    assert payload["summary"]["top5_best_mean_rmsd_A"] == 0.5
    assert payload["summary"]["top1_pose_success_rate"] == 0.0
    assert payload["summary"]["top5_pose_success_rate"] == 1.0


def test_build_pdbbind_casf_pose_affinity_results_blocks_without_poses(tmp_path: Path) -> None:
    (tmp_path / "casf" / "data_5_sdf").mkdir(parents=True)

    payload = build_results(
        argparse.Namespace(
            dataset_artifact=str(tmp_path / "casf"),
            max_poses=0,
            threshold=0.35,
            pose_success_rmsd_a=2.0,
            out_csv=str(tmp_path / "results.csv"),
            out_json=str(tmp_path / "results.json"),
            out_md=str(tmp_path / "results.md"),
            gold_metadata_csv="",
        )
    )

    assert payload["summary"]["status"] == "blocked_pdbbind_casf_pose_affinity_results"
    assert "pose_files_missing" in payload["summary"]["blockers"]


def test_build_pdbbind_casf_pose_affinity_results_blocks_without_gold_metadata(tmp_path: Path) -> None:
    data = tmp_path / "casf" / "data_5_sdf"
    data.mkdir(parents=True)
    _dump(data / "1abc", _mol())
    _dump(data / "1abc_1", _mol(offset=0.5))

    payload = build_results(
        argparse.Namespace(
            dataset_artifact=str(tmp_path / "casf"),
            max_poses=0,
            threshold=0.35,
            pose_success_rmsd_a=2.0,
            out_csv=str(tmp_path / "results.csv"),
            out_json=str(tmp_path / "results.json"),
            out_md=str(tmp_path / "results.md"),
            gold_metadata_csv="",
        )
    )

    assert payload["summary"]["status"] == "blocked_pdbbind_casf_pose_affinity_results"
    assert "gold_metrics_blocked" in payload["summary"]["blockers"]
    assert "affinity_labels_missing" in payload["summary"]["gold_metric_blockers"]


def test_build_pdbbind_casf_pose_affinity_results_blocks_partial_references(tmp_path: Path) -> None:
    data = tmp_path / "casf" / "data_5_sdf"
    data.mkdir(parents=True)
    _dump(data / "1abc", _mol())
    _dump(data / "1abc_1", _mol(offset=0.5))
    _dump(data / "2def_1", _mol(offset=0.5))
    metadata = _metadata(
        tmp_path / "gold.csv",
        [
            {
                "pose_id": "1abc_1",
                "complex_id": "1abc",
                "active_label": "1",
                "affinity_label": "9.0",
                "score": "-9.0",
                "baseline_score": "-1.0",
                "runtime_ms": "10",
                "peak_memory_mb": "100",
            },
            {
                "pose_id": "2def_1",
                "complex_id": "2def",
                "active_label": "0",
                "affinity_label": "1.0",
                "score": "-1.0",
                "baseline_score": "-9.0",
                "runtime_ms": "11",
                "peak_memory_mb": "101",
            },
        ],
    )

    payload = build_results(
        argparse.Namespace(
            dataset_artifact=str(tmp_path / "casf"),
            max_poses=0,
            threshold=0.35,
            pose_success_rmsd_a=2.0,
            out_csv=str(tmp_path / "results.csv"),
            out_json=str(tmp_path / "results.json"),
            out_md=str(tmp_path / "results.md"),
            gold_metadata_csv=str(metadata),
        )
    )

    assert payload["summary"]["status"] == "blocked_pdbbind_casf_pose_affinity_results"
    assert "row_level_benchmark_blockers_present" in payload["summary"]["blockers"]
    assert "gold_metrics_blocked" in payload["summary"]["blockers"]
