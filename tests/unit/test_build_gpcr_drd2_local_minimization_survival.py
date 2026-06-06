from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from tools.gpcr_replay import build_gpcr_drd2_local_minimization_survival as mod

ROOT = Path(__file__).resolve().parents[2]


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _synthetic_protein_ligand_npz(path: Path) -> None:
    ligand_frames = np.asarray(
        [
            [[3.20, 0.05, 0.00], [4.35, 0.05, 0.00], [5.50, 0.05, 0.00]],
            [[3.25, 0.10, 0.00], [4.40, 0.10, 0.00], [5.55, 0.10, 0.00]],
            [[3.15, -0.05, 0.00], [4.30, -0.05, 0.00], [5.45, -0.05, 0.00]],
        ],
        dtype=np.float32,
    )
    protein_atom_frames = np.asarray(
        [
            [[0.00, 0.00, 0.00], [0.20, 0.00, 0.00]],
            [[0.00, 0.00, 0.00], [0.20, 0.00, 0.00]],
            [[0.00, 0.00, 0.00], [0.20, 0.00, 0.00]],
        ],
        dtype=np.float32,
    )
    np.savez(
        path,
        ligand_frames=ligand_frames,
        protein_atom_frames=protein_atom_frames,
        ligand_atom_atomic_numbers=np.asarray([7, 6, 6], dtype=np.int16),
        ligand_atom_elements=np.asarray(["N", "C", "C"], dtype="<U3"),
        ligand_basic_amine_atom_indices=np.asarray([0], dtype=np.int32),
        ligand_backmapping_anchor_atom_indices=np.asarray([0, 1], dtype=np.int32),
    )


def test_openmm_custom_minimizer_measures_survival_but_keeps_hard_gate_false(tmp_path: Path) -> None:
    pytest.importorskip("openmm")
    npz_path = tmp_path / "positive.npz"
    _synthetic_protein_ligand_npz(npz_path)
    input_csv = tmp_path / "repair_rows.csv"
    _write_csv(
        input_csv,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "is_positive": "True",
                "ligand_smiles": "NCC",
                "trajectory_npz": str(npz_path),
            }
        ],
    )

    payload = mod.build_survival(
        input_csv=input_csv,
        requested_engine="openmm_custom",
        max_frames_per_row=3,
        openmm_max_iterations=50,
        generated_at_local="2026-05-06T00:00:00+09:00",
    )

    summary = payload["summary"]
    row = payload["rows"][0]
    assert row["engine_kind"] == mod.OPENMM_CUSTOM_ENGINE
    assert row["frame_count"] == 3
    assert row["attempted_frame_count"] == 3
    assert row["minimized_frame_count"] == 3
    assert row["survival_fraction"] == 1.0
    assert row["rmsd_A_p90"] is not None
    assert row["survival_claim_scope"] == "bounded_custom_protein_ligand_not_full_forcefield"
    assert "full_protein_ligand_forcefield_parameterization_unavailable" in row["blockers"]
    assert summary["positive_local_minimization_survival_fraction"] == 1.0
    assert summary["positive_engine_kind"] == mod.OPENMM_CUSTOM_ENGINE
    assert summary["hard_decoy_rebuild_evidence_allowed"] is False
    assert payload["claim_boundary"]["full_protein_ligand_forcefield_minimization_claimed"] is False
    assert payload["claim_boundary"]["bounded_custom_force_not_equivalent_to_full_forcefield"] is True


def test_static_anchor_coords_enable_protein_ligand_bounded_engine_for_prod_light_repair(tmp_path: Path) -> None:
    pytest.importorskip("openmm")
    npz_path = tmp_path / "prod_light_repaired.npz"
    np.savez(
        npz_path,
        ligand_frames=np.asarray(
            [
                [[3.20, 0.05, 0.00], [4.35, 0.05, 0.00], [5.50, 0.05, 0.00]],
                [[3.25, 0.10, 0.00], [4.40, 0.10, 0.00], [5.55, 0.10, 0.00]],
            ],
            dtype=np.float32,
        ),
        ligand_atom_atomic_numbers=np.asarray([7, 6, 6], dtype=np.int16),
        ligand_basic_amine_atom_indices=np.asarray([0], dtype=np.int32),
        ligand_backmapping_static_anchor_coords=np.asarray([[0.00, 0.00, 0.00], [0.20, 0.00, 0.00]], dtype=np.float32),
    )
    input_csv = tmp_path / "repair_rows.csv"
    _write_csv(
        input_csv,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "is_positive": "True",
                "ligand_smiles": "NCC",
                "trajectory_npz": str(npz_path),
            }
        ],
    )

    payload = mod.build_survival(
        input_csv=input_csv,
        requested_engine="openmm_custom_protein_ligand_bounded",
        max_frames_per_row=2,
        openmm_max_iterations=50,
        generated_at_local="2026-05-06T00:00:00+09:00",
    )

    row = payload["rows"][0]
    assert row["engine_kind"] == mod.OPENMM_CUSTOM_ENGINE
    assert row["protein_atom_count"] == 2
    assert row["survival_claim_scope"] == "bounded_custom_protein_ligand_not_full_forcefield"
    assert row["survival_fraction"] == 1.0


def test_rdkit_uff_ligand_only_is_tagged_and_not_promoted(tmp_path: Path) -> None:
    pytest.importorskip("rdkit")
    npz_path = tmp_path / "ligand_only.npz"
    np.savez(
        npz_path,
        ligand_frames=np.asarray(
            [
                [[0.0, 0.0, 0.0], [1.54, 0.0, 0.0]],
                [[0.0, 0.1, 0.0], [1.54, 0.1, 0.0]],
            ],
            dtype=np.float32,
        ),
        ligand_atom_atomic_numbers=np.asarray([6, 6], dtype=np.int16),
        ligand_atom_elements=np.asarray(["C", "C"], dtype="<U3"),
    )
    input_csv = tmp_path / "repair_rows.csv"
    _write_csv(
        input_csv,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "is_positive": "True",
                "ligand_smiles": "CC",
                "trajectory_npz": str(npz_path),
            }
        ],
    )

    payload = mod.build_survival(
        input_csv=input_csv,
        requested_engine="rdkit_uff_ligand_only",
        max_frames_per_row=2,
        generated_at_local="2026-05-06T00:00:00+09:00",
    )

    row = payload["rows"][0]
    assert row["engine_kind"] == mod.RDKIT_LIGAND_ONLY_ENGINE
    assert row["survival_claim_scope"] == "ligand_only"
    assert row["survival_fraction"] is not None
    assert "ligand_only_not_protein_ligand_minimization" in row["blockers"]
    assert payload["summary"]["hard_decoy_rebuild_evidence_allowed"] is False
    assert payload["claim_boundary"]["ligand_only_evidence_not_promoted"] is True
    assert "must not be promoted" in payload["summary"]["claim_boundary"]


def test_cli_writes_json_csv_and_markdown_outputs(tmp_path: Path) -> None:
    pytest.importorskip("rdkit")
    npz_path = tmp_path / "ligand_only.npz"
    np.savez(
        npz_path,
        ligand_frames=np.asarray([[[0.0, 0.0, 0.0], [1.54, 0.0, 0.0]]], dtype=np.float32),
        ligand_atom_atomic_numbers=np.asarray([6, 6], dtype=np.int16),
    )
    input_csv = tmp_path / "repair_rows.csv"
    out_json = tmp_path / "survival.json"
    out_csv = tmp_path / "survival.csv"
    out_md = tmp_path / "survival.md"
    _write_csv(
        input_csv,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "is_positive": "True",
                "ligand_smiles": "CC",
                "trajectory_npz": str(npz_path),
            }
        ],
    )

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/gpcr_replay/build_gpcr_drd2_local_minimization_survival.py"),
            "--input-csv",
            str(input_csv),
            "--engine",
            "rdkit_uff_ligand_only",
            "--max-frames-per-row",
            "1",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["packet_type"] == "gpcr_drd2_local_minimization_survival"
    assert payload["rows"][0]["survival_claim_scope"] == "ligand_only"
    assert "rdkit_uff_ligand_only" in out_csv.read_text(encoding="utf-8")
    assert "GPCR DRD2 Local-Minimization Survival" in out_md.read_text(encoding="utf-8")
