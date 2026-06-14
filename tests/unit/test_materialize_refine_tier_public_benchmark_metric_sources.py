from __future__ import annotations

import csv
import json
import pickle
from pathlib import Path

import pytest

from tools.product import materialize_refine_tier_public_benchmark_metric_sources as mod
from tools.product.build_refine_tier_public_benchmark_readiness import (
    _metric_source_payload_validation,
)

pytest.importorskip("rdkit")

from rdkit import Chem  # noqa: E402
from rdkit.Geometry import Point3D  # noqa: E402


def _write_rows(path: Path, rows: list[dict[str, object]]) -> None:
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


def test_materializes_metric_sources_and_pass_metric_evidence(tmp_path: Path) -> None:
    dataset = tmp_path / "data" / "public_benchmarks" / "pdbbind_casf_pose_affinity"
    pose_path = dataset / "data_5_sdf" / "t001_001"
    reference_path = dataset / "data_5_sdf" / "t001"
    receptor_path = dataset / "t001" / "t001_receptor.pdb"
    _write_mol(pose_path, _mol_with_coords(0.05))
    _write_mol(reference_path, _mol_with_coords(0.0))
    _write_receptor(receptor_path)

    work_order_csv = tmp_path / "runs" / "work_order.csv"
    science_gap_csv = tmp_path / "runs" / "science_gap.csv"
    _write_rows(
        work_order_csv,
        [
            {
                "work_order_id": "refine_tier_public_benchmark_seeded_001",
                "target_input_csv": str(tmp_path / "config" / "intake.csv"),
                "template_row_index": "1",
                "benchmark_id": "PDBBIND_CASF_T001_T001_001",
                "target_id": "t001",
                "benchmark_family": "pdbbind_casf_refine_tier_public_seed",
                "split": "fit",
                "provenance_kind": "pdbbind",
                "provenance_id": "PDBBind/CASF:t001:t001_001",
                "license_ok": "OPERATOR_CONFIRM_TRUE",
                "external_engine_calls": "0",
                "pose_rmsd_A": "0.05",
                "dockq": "OPERATOR_FILL_DOCKQ",
                "lddt_pli": "OPERATOR_FILL_LDDT_PLI",
                "deltaG_mm_gbsa_kcal_mol": "OPERATOR_FILL_INTERNAL_REFINE_DG",
                "dockq_source_artifact": "OPERATOR_FILL_DOCKQ_SOURCE_ARTIFACT",
                "lddt_pli_source_artifact": "OPERATOR_FILL_LDDT_PLI_SOURCE_ARTIFACT",
                "internal_deltaG_source_artifact": "OPERATOR_FILL_INTERNAL_DELTAG_SOURCE_ARTIFACT",
                "deltaG_experimental_kcal_mol": "-5.0",
                "operator_action": "append_validated_public_benchmark_row",
                "acceptance_rule": "test",
                "external_state_mutated": "False",
            }
        ],
    )
    _write_rows(
        science_gap_csv,
        [
            {
                "work_order_id": "refine_tier_public_benchmark_seeded_001",
                "target_id": "t001",
                "pose_id": "t001_001",
                "ligand_pose_artifact": str(pose_path),
                "ligand_pose_artifact_present": "True",
                "receptor_coordinate_artifact": str(receptor_path),
                "receptor_coordinate_artifact_present": "True",
            }
        ],
    )

    payload = mod.materialize_refine_tier_public_benchmark_metric_sources(
        work_order_csv=work_order_csv,
        science_input_gap_csv=science_gap_csv,
        out_json=tmp_path / "runs" / "materialized.json",
        out_csv=tmp_path / "runs" / "materialized.csv",
        out_md=tmp_path / "runs" / "materialized.md",
        out_filled_work_order_csv=tmp_path / "runs" / "filled_work_order.csv",
        out_metric_evidence_csv=tmp_path / "runs" / "metric_evidence.csv",
        out_source_dir=tmp_path / "runs" / "metric_sources",
        reviewed_at_utc="2026-06-14T00:00:00Z",
    )

    summary = payload["summary"]
    assert summary["materialized_row_count"] == 1
    assert summary["metric_evidence_pass_row_count"] == 1
    assert summary["metric_evidence_blocked_row_count"] == 0
    assert summary["free_energy_pair_count"] == 1
    assert summary["free_energy_fit_pair_count"] == 1
    assert summary["free_energy_holdout_pair_count"] == 0
    assert summary["bootstrap_valid_sample_count"] == 0
    assert summary["free_energy_spearman_bootstrap_p05"] is None
    assert summary["claim_grade_public_benchmark_statistical_support_ready"] is False
    assert summary["claim_grade_public_benchmark_statistical_support_blocker_count"] == 3
    assert summary["claim_grade_public_benchmark_statistical_support_blockers"] == [
        "claim_grade_public_benchmark_pair_count_below_minimum",
        "claim_grade_public_benchmark_holdout_pair_count_below_minimum",
        "claim_grade_public_benchmark_bootstrap_spearman_low_below_minimum",
    ]

    filled_rows = list(csv.DictReader((tmp_path / "runs" / "filled_work_order.csv").open()))
    assert filled_rows[0]["license_ok"] == "True"
    assert filled_rows[0]["dockq_source_artifact"].endswith("_dockq.json")

    source_payload = json.loads(Path(filled_rows[0]["dockq_source_artifact"]).read_text(encoding="utf-8"))
    validation = _metric_source_payload_validation(
        filled_rows[0]["dockq_source_artifact"],
        expected_metric_name="dockq",
        expected_target_id="t001",
        expected_pose_id="t001_001",
        expected_value=filled_rows[0]["dockq"],
        expected_input_artifacts=[str(pose_path), str(receptor_path)],
    )
    assert source_payload["external_engine_calls"] == 0
    assert validation["payload_valid"] is True
