from __future__ import annotations

import csv
import json
import pickle
from pathlib import Path

import pytest

from tools.product import (
    materialize_refine_tier_public_benchmark_statistical_support_metric_candidates as mod,
)

pytest.importorskip("rdkit")

from rdkit import Chem  # noqa: E402
from rdkit.Geometry import Point3D  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _mol_with_coords(offset: float = 0.0) -> object:
    mol = Chem.MolFromSmiles("CCO")
    conf = Chem.Conformer(mol.GetNumAtoms())
    coords = [(0.0 + offset, 0.0, 0.0), (1.5 + offset, 0.0, 0.0), (2.6 + offset, 0.8, 0.0)]
    for idx, (x, y, z) in enumerate(coords):
        conf.SetAtomPosition(idx, Point3D(x, y, z))
    mol.AddConformer(conf)
    return mol


def _write_mol(path: Path, mol: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pickle.dumps(mol))


def _pdb_atom(serial: int, atom: str, residue: str, residue_id: int, x: float, y: float, z: float) -> str:
    element = atom.strip()[0]
    return (
        f"ATOM  {serial:5d} {atom:<4}{residue:>3} A{residue_id:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00          {element:>2}"
    )


def _write_receptor(path: Path) -> None:
    lines = []
    serial = 1
    for residue_id in range(1, 7):
        base = float(residue_id - 1)
        for atom, dx, dy, dz in (
            ("N", 0.0, 0.0, 0.0),
            ("CA", 0.4, 0.8, 0.0),
            ("C", 0.8, 0.0, 0.0),
            ("O", 1.0, -0.6, 0.0),
        ):
            lines.append(_pdb_atom(serial, atom, "ALA", residue_id, base + dx, dy, dz))
            serial += 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_candidate_fill_computes_three_values_without_touching_expected_payload(tmp_path: Path) -> None:
    dataset = tmp_path / "data" / "public_benchmarks" / "pdbbind_casf_pose_affinity"
    pose_path = dataset / "data_5_sdf" / "t001_001"
    reference_path = dataset / "data_5_sdf" / "t001"
    receptor_path = dataset / "t001" / "t001_complex.pdb"
    expected_payload = tmp_path / "runs" / "metric_sources" / "expansion_001_dockq.json"
    _write_mol(pose_path, _mol_with_coords(0.05))
    _write_mol(reference_path, _mol_with_coords(0.0))
    _write_receptor(receptor_path)
    readiness = {
        "summary": {"status": "refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_ready"},
        "rows": [
            {
                "expansion_slot_id": "expansion_001",
                "candidate_queue_id": "candidate_001",
                "suggested_work_order_id": "expansion_001",
                "target_id": "t001",
                "pose_id": "t001_001",
                "suggested_split": "holdout",
                "required_split": "holdout",
                "ligand_pose_artifact": str(pose_path),
                "receptor_coordinate_artifact": str(receptor_path),
                "required_metric_input_artifacts": f"{pose_path};{receptor_path}",
                "deltaG_experimental_kcal_mol": "-5.0",
            }
        ],
    }
    templates = {
        "summary": {"status": "refine_tier_public_benchmark_statistical_support_metric_source_templates_ready"},
        "rows": [
            {
                "template_id": "template_001",
                "expansion_slot_id": "expansion_001",
                "candidate_queue_id": "candidate_001",
                "suggested_work_order_id": "expansion_001",
                "target_id": "t001",
                "pose_id": "t001_001",
                "metric_name": metric,
                "metric_source_artifact": str(expected_payload).replace("_dockq", f"_{metric}"),
            }
            for metric in ("dockq", "lddt_pli", "internal_deltaG")
        ],
    }
    _write_json(tmp_path / "runs" / "readiness.json", readiness)
    _write_json(tmp_path / "runs" / "templates.json", templates)
    _write_csv(
        tmp_path / "runs" / "existing.csv",
        [
            {
                "work_order_id": "seed_001",
                "target_id": "seed",
                "split": "fit",
                "internal_refine_proxy_score": "-4.0",
                "deltaG_experimental_kcal_mol": "-4.5",
            }
        ],
    )

    payload = mod.materialize_refine_tier_public_benchmark_statistical_support_metric_candidates(
        metric_source_templates_json=tmp_path / "runs" / "templates.json",
        metric_materialization_readiness_json=tmp_path / "runs" / "readiness.json",
        existing_materialization_csv=tmp_path / "runs" / "existing.csv",
        out_json=tmp_path / "config" / "candidate.json",
        out_csv=tmp_path / "runs" / "candidate.csv",
        out_md=tmp_path / "docs" / "candidate.md",
        root=tmp_path,
        generated_at_utc="2026-06-14T00:00:00Z",
    )

    summary = payload["summary"]
    assert summary["status"] == "refine_tier_public_benchmark_statistical_support_metric_candidates_ready"
    assert summary["candidate_row_count"] == 3
    assert summary["candidate_pass_row_count"] == 3
    assert summary["metric_value_candidate_count"] == 3
    assert summary["expected_metric_source_artifact_touched_count"] == 0
    assert not expected_payload.exists()
    assert payload["rows"][0]["payload_write_allowed"] is False
    assert payload["rows"][0]["auxiliary_reference_ligand_artifact"] == str(reference_path)
    assert "REQUIRES_OPERATOR_APPROVAL" == payload["rows"][0]["approval_token_candidate"]
