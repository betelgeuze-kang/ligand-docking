"""Phase-2 tests: all-atom, explicit, FEP, cross-docking, refine training, external metrics."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch

from betelgeuze_product.structure_analysis import analyze_structure_source
from core.allatom_forcefield import allatom_energy
from core.explicit_solvent import explicit_solvation_energy
from core.fep import estimate_binding_fep
from core.mm_gbsa import compute_full_refine_stack
from core.pose_generation import generate_cross_docking_poses, induced_fit_relax, sample_sidechain_rotamers
from core.structure_metrics_external import try_molprobity_clashscore
from tools import train_residual_production_score_model as train_mod
from tools.product.build_refine_tier_residual_training_dataset import enrich_refine_tier_labels


def _prot() -> np.ndarray:
    return np.asarray([[0, 0, 0], [3.8, 0, 0], [7.6, 0, 0], [0, 3.8, 0]], dtype=np.float32)


def _lig() -> np.ndarray:
    return np.asarray([[-1, 2, 0], [1, 2, 0]], dtype=np.float32)


def test_allatom_explicit_fep_stack():
    aa = allatom_energy(_prot(), ["C"] * 4)
    assert aa["bond_count"] >= 1
    ex = explicit_solvation_energy(_prot(), ["C"] * 4)
    assert ex["water_count"] >= 0
    fep = estimate_binding_fep(_prot(), _lig(), n_windows=5, n_bootstrap=2)
    assert fep["status"] == "fep_estimate_ready"
    stack = compute_full_refine_stack(_prot(), _lig(), include_explicit=True, include_fep=True)
    assert "gb_sa" in stack and "allatom" in stack and "fep" in stack


def test_cross_docking_and_induced_fit():
    cross = generate_cross_docking_poses("CCO", _prot(), n_starts=2, induced_fit=True)
    assert cross["mode"] == "cross_docking"
    assert cross["pose_count"] == 2
    fit = induced_fit_relax(_prot(), _lig())
    assert fit["status"] == "induced_fit_relaxed"
    atoms = [
        {"chain_id": "A", "resname": "SER", "residue_id": "10", "xyz": np.asarray([0, 0, 0])},
        {"chain_id": "A", "resname": "ASP", "residue_id": "11", "xyz": np.asarray([3.8, 0, 0])},
    ]
    rot = sample_sidechain_rotamers(atoms)
    assert len(rot) >= 2


def test_refine_tier_training_enrichment_and_model_features(tmp_path: Path):
    dataset = tmp_path / "dataset.csv"
    stage3 = tmp_path / "stage3.csv"
    enriched = tmp_path / "enriched.csv"
    dataset.write_text(
        "target,family,ligand_id,is_binder,role,reference_binding_kcal_mol,raw_score,score_col,delta_score,corrected_score,mean_min_distance_A,source_csv,label_source\n"
        "ADRB2,gpcr,lig1,1,fit,-9.0,-8.0,binding_score_composite_v7,-1.0,-9.0,3.0,fixture,fixture\n"
        "ADRB2,gpcr,lig2,0,fit,-2.0,-1.0,binding_score_composite_v7,-1.0,-2.0,3.5,fixture,fixture\n",
        encoding="utf-8",
    )
    stage3.write_text(
        "target,ligand_id,binding_energy_mmpbsa_kcal_mol_proxy,deltaG_mm_gbsa_kcal_mol,physics_refinement_confidence\n"
        "ADRB2,lig1,-6.0,-5.2,0.85\n"
        "ADRB2,lig2,-1.0,-0.5,0.55\n",
        encoding="utf-8",
    )
    summary = enrich_refine_tier_labels(input_csv=dataset, stage3_csv=stage3, out_csv=enriched)
    assert summary["refine_tier_label_rows"] == 2

    # pad dataset for training minimum rows
    rows = enriched.read_text(encoding="utf-8").strip().splitlines()
    header = rows[0]
    body = rows[1:]
    padded = tmp_path / "padded.csv"
    padded.write_text(header + "\n" + "\n".join(body * 20) + "\n", encoding="utf-8")
    checkpoint = tmp_path / "model.pt"
    train_summary = train_mod.train_residual_production_score_model(
        input_csv=str(padded),
        out_checkpoint=str(checkpoint),
        epochs=1,
        hidden_dim=16,
        batch_size=8,
        device_name="cpu",
    )
    assert "refine_confidence" in train_summary["feature_names"] or "mm_gbsa_delta" in train_summary["feature_names"]
    assert checkpoint.exists()


def test_external_metric_adapter_falls_back_to_proxy():
    pdb = "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C\n"
    clash = try_molprobity_clashscore(pdb)
    assert clash["source"] == "internal_proxy"
    assert clash["value"] is not None
    product = analyze_structure_source({"pdb_content": pdb})
    assert product["molprobity_clashscore_source"] == "internal_proxy"


def test_physics_refinement_full_stack_backend(tmp_path: Path):
    from tools.run_ligand_physics_refinement import build_parser, run_refinement

    scores = tmp_path / "stage3.csv"
    scores.write_text(
        "target,ligand_id,binding_energy_mmpbsa_kcal_mol_proxy,binding_score_composite_v7,mean_min_distance_A,contact_fraction,stability_score\n"
        + "\n".join(
            f"ADRB2,lig{i},{-6.0 + 0.01 * i},{-7.0 + 0.01 * i},{3.0 + 0.02 * i},0.3,0.2"
            for i in range(20)
        )
        + "\n",
        encoding="utf-8",
    )
    out_csv = tmp_path / "out.csv"
    args = build_parser().parse_args(
        [
            "--scores-csv",
            str(scores),
            "--score-col",
            "binding_score_composite_v7",
            "--backend",
            "internal_full_stack_v1",
            "--topk-global",
            "8",
            "--out-csv",
            str(out_csv),
        ]
    )
    summary = run_refinement(args)
    assert summary["pass"] is True
    assert summary["selected_count"] == 8
    assert out_csv.exists()


def test_cross_docking_pose_seed_rotation_diversifies_initial_pose():
    from tools.generate_ligand_trajectory_engine import _compose_ligand_xyz

    row = {
        "pocket_x": 5.0,
        "pocket_y": 0.0,
        "pocket_z": 0.0,
        "ligand_bead0_x": -0.8,
        "ligand_bead0_y": 0.0,
        "ligand_bead0_z": 0.0,
        "ligand_bead1_x": 0.8,
        "ligand_bead1_y": 0.0,
        "ligand_bead1_z": 0.0,
    }
    base = _compose_ligand_xyz(row, cross_docking_angle_rad=0.0)
    rotated = _compose_ligand_xyz(row, cross_docking_angle_rad=float(np.pi) / 2.0)
    # default angle preserves legacy behavior
    assert np.allclose(base, np.asarray([[4.2, 0.0, 0.0], [5.8, 0.0, 0.0]], dtype=np.float32))
    # rotation moves beads off the x-axis but keeps pocket center
    assert not np.allclose(base, rotated)
    assert np.allclose(rotated.mean(axis=0), base.mean(axis=0), atol=1e-5)


def test_docking_request_pose_generation_contract_surface():
    from betelgeuze_product.docking_request import build_docking_job_record

    pdb_lines = []
    for i in range(12):
        x = (i % 4) * 3.8
        y = (i // 4) * 3.8
        pdb_lines.append(
            f"ATOM  {i + 1:5d}  CA  ALA A{i + 1:4d}    {x:8.3f}{y:8.3f}{0.0:8.3f}  1.00  0.00           C"
        )
    pdb = "\n".join(pdb_lines) + "\n"
    record = build_docking_job_record(
        {
            "request_type": "structure_analysis_ligand_docking",
            "family": "gpcr",
            "target_id": "ADRB2",
            "pdb_content": pdb,
            "ligands": [{"ligand_id": "lig_1", "smiles": "CCO"}],
        },
        job_id="job_pose",
    )
    assert "pose_generation_contract" in record
    assert record["pose_generation_contract"]["execution_enabled"] is False
    assert record["execution_enabled"] is False
    node = next(n for n in record["ai_decision_graph_trace"] if n["node_id"] == "pose_generation_contract")
    assert "pose_generation_modes" in node["evidence"]
