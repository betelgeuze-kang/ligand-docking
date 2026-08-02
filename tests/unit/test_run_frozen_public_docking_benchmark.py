"""Frozen public docking benchmark execution harness tests."""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "product" / "run_frozen_public_docking_benchmark.py"


@pytest.fixture(scope="module")
def runner():
    spec = importlib.util.spec_from_file_location(
        "run_frozen_public_docking_benchmark_under_test", MODULE_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _atom_line(
    serial: int,
    atom_name: str,
    residue: str,
    chain: str,
    residue_number: int,
    xyz: tuple[float, float, float],
    element: str,
    *,
    record: str = "HETATM",
) -> str:
    return (
        f"{record:<6}{serial:5d} {atom_name:^4} {residue:>3} {chain:1}"
        f"{residue_number:4d}    {xyz[0]:8.3f}{xyz[1]:8.3f}{xyz[2]:8.3f}"
        f"  1.00 10.00          {element:>2}"
    )


def _ethanol_complex() -> str:
    lines = [
        _atom_line(1, "CA", "ALA", "A", 1, (10.0, 0.0, 0.0), "C", record="ATOM"),
        _atom_line(2, "C1", "LIG", "A", 500, (0.0, 0.0, 0.0), "C"),
        _atom_line(3, "C2", "LIG", "A", 500, (1.5, 0.0, 0.0), "C"),
        _atom_line(4, "O1", "LIG", "A", 500, (2.8, 0.0, 0.0), "O"),
        _atom_line(5, "O", "HOH", "A", 900, (5.0, 5.0, 5.0), "O"),
        _atom_line(6, "ZN", "ZN", "A", 901, (4.0, 4.0, 4.0), "ZN"),
        "CONECT    2    3",
        "CONECT    3    2    4",
        "CONECT    4    3",
        "END",
    ]
    return "\n".join(lines) + "\n"


def test_reference_extraction_graph_mapping_and_rmsd(runner):
    reference, blockers = runner.extract_reference_ligand(_ethanol_complex(), "LIG")
    assert blockers == []
    assert reference["atom_count"] == 3
    assert reference["chain_id"] == "A"
    assert reference["residue_number"] == "500"

    template, matches, graph_blockers = runner.build_reference_graph(reference, "CCO")
    assert graph_blockers == []
    assert template.GetNumAtoms() == 3
    assert matches
    rmsd = runner.symmetry_aware_pose_rmsd(
        reference["coordinates"],
        reference["coordinates"],
        matches,
    )
    assert rmsd == pytest.approx(0.0)


def test_symmetry_aware_rmsd_uses_graph_permutations_without_superposition(runner):
    reference = [[-1.0, 0.0, 0.0], [1.0, 0.0, 0.0]]
    reversed_pose = [[1.0, 0.0, 0.0], [-1.0, 0.0, 0.0]]
    assert runner.symmetry_aware_pose_rmsd(
        reversed_pose,
        reference,
        [(0, 1), (1, 0)],
    ) == pytest.approx(0.0)

    translated = [[2.0, 0.0, 0.0], [4.0, 0.0, 0.0]]
    assert runner.symmetry_aware_pose_rmsd(
        translated,
        reference,
        [(0, 1)],
    ) > 2.0


def test_receptor_stripping_removes_native_ligand_and_solvent(runner):
    stripped = runner.strip_receptor_for_docking(_ethanol_complex(), "LIG")
    assert " LIG " not in stripped
    assert " HOH " not in stripped
    assert " ZN " in stripped
    assert stripped.count("ATOM") == 1
    assert "CONECT" not in stripped


def _protein_pdb(
    coordinates: np.ndarray,
    *,
    chain: str,
    start_serial: int = 1,
) -> str:
    lines = [
        _atom_line(
            start_serial + index,
            "CA",
            "ALA",
            chain,
            index + 1,
            tuple(float(value) for value in xyz),
            "C",
            record="ATOM",
        )
        for index, xyz in enumerate(coordinates)
    ]
    return "\n".join([*lines, "END", ""])


def test_apo_alignment_transforms_holo_reference_into_receptor_frame(runner):
    indices = np.arange(40, dtype=np.float64)
    source_ca = np.column_stack(
        [indices * 0.8, np.sin(indices * 0.4) * 3.0, np.cos(indices * 0.25) * 2.0]
    )
    rotation = np.asarray(
        [
            [0.0, -1.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    translation = np.asarray([7.0, -3.0, 2.0])
    receptor_ca = source_ca @ rotation + translation
    ligand = np.asarray([[1.0, 2.0, 3.0], [2.0, 2.0, 3.0]])

    transformed, evidence, blockers = runner.align_reference_coordinates(
        _protein_pdb(source_ca, chain="A"),
        _protein_pdb(receptor_ca, chain="B"),
        ligand,
    )
    assert blockers == []
    assert transformed is not None
    assert transformed == pytest.approx(ligand @ rotation + translation, abs=2e-3)
    assert evidence["aligned_ca_count"] == 40
    assert evidence["inlier_ca_count"] == 40
    assert evidence["sequence_identity"] == 1.0
    assert evidence["inlier_ca_rmsd_a"] < 0.01


def test_explicit_hydrogen_is_removed_for_heavy_atom_pose_evaluation(runner):
    normalized, evidence, blockers = runner.normalize_heavy_atom_smiles("[H]/N=C/C")
    assert blockers == []
    assert evidence["explicit_hydrogen_count_removed"] == 1
    assert "[H]" not in normalized
    from rdkit import Chem

    molecule = Chem.MolFromSmiles(normalized)
    assert molecule is not None
    assert all(atom.GetAtomicNum() != 1 for atom in molecule.GetAtoms())


def _surface(
    *,
    top1: bool,
    top3: bool,
    top5: bool,
    runtime: float,
    geometric: bool = True,
    chemical: bool = True,
) -> dict:
    return {
        "status": "docking_result_bundle_ready",
        "blockers": [],
        "pose_ensemble": {
            "poses": [
                {
                    "rank": 1,
                    "geometric_valid": geometric,
                    "chemistry_valid": chemical,
                }
            ]
        },
        "evaluation": {
            "top1_success": top1,
            "top3_success": top3,
            "top5_success": top5,
            "evaluation_failed": False,
        },
        "measured_runtime_seconds": {"end_to_end": runtime},
    }


def test_metric_aggregation_uses_the_full_failure_denominator(runner):
    results = [
        {
            "failed": False,
            "strata": {
                "rotor_count": "rigid",
                "ligand_size": "small",
            },
            "surfaces": {
                "engine_v2": _surface(
                    top1=True,
                    top3=True,
                    top5=True,
                    runtime=1.0,
                )
            },
        },
        {
            "failed": True,
            "strata": {
                "rotor_count": "flexible",
                "ligand_size": "large",
            },
            "surfaces": {},
        },
    ]
    metrics, interval = runner.aggregate_subject_metrics(
        results,
        candidate_budget=8,
        bootstrap_iterations=200,
        bootstrap_seed=11,
    )
    assert metrics["attempted_case_count"] == 2
    assert metrics["top1_rmsd_success_rate_2a"] == 0.5
    assert metrics["top3_success_rate"] == 0.5
    assert metrics["top5_success_rate"] == 0.5
    assert metrics["full_case_failure_rate"] == 0.5
    assert metrics["geometric_validity_rate"] == 0.5
    assert metrics["chemical_validity_rate"] == 0.5
    assert metrics["runtime_seconds_median"] == 0.5
    assert metrics["rotor_subgroup_success"] == {"flexible": 0.0, "rigid": 1.0}
    assert interval["point_estimate"] == 0.5
    assert interval["ci_low"] <= 0.5 <= interval["ci_high"]


def test_unexpected_case_exception_becomes_a_counted_failure(runner, monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(runner, "run_case", explode)
    result = runner.run_case_fail_closed(
        {
            "case_id": "case_1",
            "target_id": "pdb:1AAA",
            "ligand_id": "ccd:LIG",
            "strata": {"rotor_count": "rigid"},
        },
        {},
    )
    assert result["failed"] is True
    assert result["blockers"] == ["unhandled_case_execution_error:RuntimeError"]


def test_frozen_input_loader_rejects_case_set_hash_drift(runner, tmp_path):
    cases_path = tmp_path / "cases.csv"
    columns = [
        "case_id",
        "target_id",
        "ligand_id",
        "provenance_id",
        *runner.REQUIRED_STRATIFICATION_AXES,
    ]
    row = {
        "case_id": "case_1",
        "target_id": "pdb:1AAA",
        "ligand_id": "ccd:LIG",
        "provenance_id": "rcsb:1AAA",
        **{axis: f"{axis}_bucket" for axis in runner.REQUIRED_STRATIFICATION_AXES},
    }
    with cases_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerow(row)
    cases = runner._read_cases(cases_path)
    receipt_path = tmp_path / "receipt.json"
    receipt = {
        "summary": {
            "case_set_hash": runner._case_set_hash(cases),
            "case_count": 1,
            "frozen_case_set": True,
            "frozen_at_utc": "2026-07-27T00:00:00Z",
        },
        "cases": [{"case_id": "case_1", "evidence": {"receptor_entry_id": "1AAA"}}],
    }
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    loaded, evidence, _, blockers = runner.load_frozen_inputs(
        cases_csv=cases_path,
        collection_receipt_json=receipt_path,
    )
    assert len(loaded) == 1
    assert evidence["case_1"]["receptor_entry_id"] == "1AAA"
    assert blockers == []

    row["target_id"] = "pdb:CHANGED"
    with cases_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerow(row)
    _, _, _, drift_blockers = runner.load_frozen_inputs(
        cases_csv=cases_path,
        collection_receipt_json=receipt_path,
    )
    assert "collection_receipt_case_set_hash_mismatch" in drift_blockers
