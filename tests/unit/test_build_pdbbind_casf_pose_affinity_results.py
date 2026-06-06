from __future__ import annotations

import argparse
import csv
import pickle
from pathlib import Path

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


def test_build_pdbbind_casf_pose_affinity_results_scores_pose_success(tmp_path: Path) -> None:
    data = tmp_path / "casf" / "data_5_sdf"
    data.mkdir(parents=True)
    _dump(data / "1abc", _mol())
    _dump(data / "1abc_1", _mol(offset=0.5))
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
        )
    )

    assert payload["summary"]["status"] == "pdbbind_casf_pose_affinity_results_ready"
    assert payload["summary"]["pose_success_rate"] == 1.0
    assert payload["summary"]["pose_row_success_rate"] == 1.0
    assert payload["summary"]["complex_pose_success_rate"] == 1.0
    assert _rows(out_csv)[0]["complex_id"] == "1abc"


def test_build_pdbbind_casf_pose_affinity_results_uses_best_pose_per_complex(tmp_path: Path) -> None:
    data = tmp_path / "casf" / "data_5_sdf"
    data.mkdir(parents=True)
    _dump(data / "1abc", _mol())
    _dump(data / "1abc_1", _mol(offset=5.0))
    _dump(data / "1abc_2", _mol(offset=0.5))

    payload = build_results(
        argparse.Namespace(
            dataset_artifact=str(tmp_path / "casf"),
            max_poses=0,
            threshold=0.35,
            pose_success_rmsd_a=2.0,
            out_csv=str(tmp_path / "results.csv"),
            out_json=str(tmp_path / "results.json"),
            out_md=str(tmp_path / "results.md"),
        )
    )

    assert payload["summary"]["status"] == "pdbbind_casf_pose_affinity_results_ready"
    assert payload["summary"]["pose_row_success_rate"] == 0.5
    assert payload["summary"]["complex_pose_success_rate"] == 1.0


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
        )
    )

    assert payload["summary"]["status"] == "blocked_pdbbind_casf_pose_affinity_results"
    assert "pose_files_missing" in payload["summary"]["blockers"]
