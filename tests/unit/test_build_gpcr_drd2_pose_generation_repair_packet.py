from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from tools import build_gpcr_drd2_pose_generation_repair_packet as mod

ROOT = Path(__file__).resolve().parents[2]


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_build_packet_blocks_claim_and_flags_pose_generation_repair_requirements(tmp_path: Path) -> None:
    rows_csv = tmp_path / "rows.csv"
    stage3_csv = tmp_path / "stage3.csv"
    atom_cache_csv = tmp_path / "atom_cache.csv"
    diagnostics_json = tmp_path / "diagnostics.json"
    pos_npz = tmp_path / "pos.npz"
    decoy_npz = tmp_path / "decoy.npz"
    np.savez(
        pos_npz,
        ligand_frames=np.zeros((3, 2, 3), dtype=np.float32),
        protein_atom_frames=np.zeros((3, 4, 3), dtype=np.float32),
        frame_indices=np.asarray([0, 1, 2], dtype=np.int32),
    )
    np.savez(
        decoy_npz,
        ligand_frames=np.zeros((3, 6, 3), dtype=np.float32),
        protein_atom_frames=np.zeros((3, 4, 3), dtype=np.float32),
        frame_indices=np.asarray([0, 1, 2], dtype=np.int32),
    )
    decoy_rank_rows = [
        {
            "target": "CHEMBL217_DRD2_HUMAN",
            "ligand_id": f"DRD2_DECOY_{idx:03d}",
            "is_binder": "0",
            "binding_score_composite_v7": str(-20.0 + idx * 0.01),
            "mean_min_distance_A": "2.4",
        }
        for idx in range(105)
    ]
    _write_csv(
        rows_csv,
        [
            *decoy_rank_rows,
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "is_binder": "1",
                "binding_score_composite_v7": "-1.0",
                "mean_min_distance_A": "4.8",
            },
            {
                "target": "ADRB2_GPCR_BLIND",
                "ligand_id": "ADRB2_POS",
                "is_binder": "1",
                "binding_score_composite_v7": "-30.0",
                "mean_min_distance_A": "3.1",
            },
        ],
    )
    _write_csv(
        stage3_csv,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "ligand_smiles": "CN(C)CCc1ccccc1",
                "trajectory_npz": str(pos_npz),
                "binding_energy_mmpbsa_kcal_mol_proxy": "-0.01",
                "contact_fraction": "0.001",
                "stability_score": "0.10",
                "ligand_h_donors": "1",
                "ligand_h_acceptors": "2",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "DRD2_DECOY_000",
                "ligand_smiles": "NCCN(CCO)CCO",
                "trajectory_npz": str(decoy_npz),
                "binding_energy_mmpbsa_kcal_mol_proxy": "-0.30",
                "contact_fraction": "0.80",
                "stability_score": "0.90",
                "ligand_h_donors": "3",
                "ligand_h_acceptors": "6",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "DRD2_DECOY_001",
                "ligand_smiles": "NCCN(CCO)CCO",
                "trajectory_npz": str(decoy_npz),
                "binding_energy_mmpbsa_kcal_mol_proxy": "-0.20",
                "contact_fraction": "0.70",
                "stability_score": "0.80",
                "ligand_h_donors": "3",
                "ligand_h_acceptors": "6",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "DRD2_DECOY_002",
                "ligand_smiles": "CCCCCCc1ccccc1",
                "trajectory_npz": str(decoy_npz),
                "binding_energy_mmpbsa_kcal_mol_proxy": "-0.10",
                "contact_fraction": "0.60",
                "stability_score": "0.70",
                "ligand_h_donors": "0",
                "ligand_h_acceptors": "0",
            },
        ],
    )
    _write_csv(
        atom_cache_csv,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "class_a_atom_anchor_available": "1",
                "class_a_atom_anchor_min_distance_A": "3.4",
                "class_a_atom_anchor_p10_distance_A": "3.5",
                "class_a_atom_anchor_mean_distance_A": "3.8",
                "class_a_atom_anchor_contact_fraction_le_2p8A": "0.0",
                "class_a_atom_anchor_contact_fraction_2p8_4p2A": "0.7",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "DRD2_DECOY_000",
                "class_a_atom_anchor_available": "1",
                "class_a_atom_anchor_min_distance_A": "2.1",
                "class_a_atom_anchor_p10_distance_A": "2.2",
                "class_a_atom_anchor_mean_distance_A": "2.4",
                "class_a_atom_anchor_contact_fraction_le_2p8A": "0.8",
                "class_a_atom_anchor_contact_fraction_2p8_4p2A": "0.8",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "DRD2_DECOY_001",
                "class_a_atom_anchor_available": "1",
                "class_a_atom_anchor_min_distance_A": "2.3",
                "class_a_atom_anchor_p10_distance_A": "2.4",
                "class_a_atom_anchor_mean_distance_A": "2.6",
                "class_a_atom_anchor_contact_fraction_le_2p8A": "0.6",
                "class_a_atom_anchor_contact_fraction_2p8_4p2A": "0.9",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "DRD2_DECOY_002",
                "class_a_atom_anchor_available": "1",
                "class_a_atom_anchor_min_distance_A": "2.2",
                "class_a_atom_anchor_p10_distance_A": "2.3",
                "class_a_atom_anchor_mean_distance_A": "2.7",
                "class_a_atom_anchor_contact_fraction_le_2p8A": "0.7",
                "class_a_atom_anchor_contact_fraction_2p8_4p2A": "0.1",
            },
        ],
    )
    _write_json(
        diagnostics_json,
        {
            "drd2_pose_physics_diagnostics": {
                "positive_pose_preservation_rmsd_A": None,
                "positive_local_minimization_survival_support": None,
            }
        },
    )

    payload, repair_rows = mod.build_packet(
        rows_csv=rows_csv,
        stage3_csv=stage3_csv,
        atom_cache_csv=atom_cache_csv,
        diagnostics_json=diagnostics_json,
        top_decoys=3,
        generated_at_local="2026-05-05T00:00:00+09:00",
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_pose_generation_repair_required"
    assert summary["claim_promotion_allowed"] is False
    assert summary["scorer_apply_allowed"] is False
    assert summary["decoys_above_positive_count"] == 105
    assert summary["inspected_decoy_count"] == 3
    assert summary["overanchored_decoy_count"] == 3
    assert summary["multipolar_basic_decoy_count"] == 2
    assert summary["positive_within_target_rank"] == 106
    assert summary["positive_backmapping_atom_coverage_ratio"] is not None
    assert summary["positive_backmapping_atom_coverage_ratio"] < 0.5
    assert {
        "drd2_positive_tail_rank",
        "positive_backmapping_atom_coverage_low",
        "pose_preservation_rmsd_missing",
        "local_minimization_survival_missing",
        "overanchored_decoy_cluster_present",
        "multipolar_basic_decoy_intrusion_present",
    }.issubset(set(summary["blockers"]))
    assert payload["claim_boundary"]["full_100k_claim_review_allowed"] is False
    assert payload["positive_row"]["failure_tags"] == [
        "positive_tail_rank",
        "positive_backmapping_atom_coverage_low",
        "positive_contact_fraction_weak",
        "positive_binding_proxy_weak",
    ]
    assert any("decoy_overanchor_too_close" in row["failure_tags"] for row in repair_rows if not row["is_positive"])
    assert "repair_drd2_pose_generation_backmapping" in summary["next_action"]


def test_repair_packet_cli_writes_json_markdown_and_rows(tmp_path: Path) -> None:
    rows_csv = tmp_path / "rows.csv"
    stage3_csv = tmp_path / "stage3.csv"
    atom_cache_csv = tmp_path / "atom_cache.csv"
    diagnostics_json = tmp_path / "diagnostics.json"
    pos_npz = tmp_path / "pos.npz"
    np.savez(pos_npz, ligand_frames=np.zeros((1, 2, 3), dtype=np.float32))
    _write_csv(
        rows_csv,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "DRD2_DECOY",
                "is_binder": "0",
                "binding_score_composite_v7": "-2.0",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "is_binder": "1",
                "binding_score_composite_v7": "-1.0",
            },
        ],
    )
    _write_csv(
        stage3_csv,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "ligand_smiles": "CN(C)CCc1ccccc1",
                "trajectory_npz": str(pos_npz),
            }
        ],
    )
    _write_csv(
        atom_cache_csv,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "DRD2_DECOY",
                "class_a_atom_anchor_available": "1",
                "class_a_atom_anchor_min_distance_A": "2.2",
                "class_a_atom_anchor_contact_fraction_le_2p8A": "0.9",
                "class_a_atom_anchor_contact_fraction_2p8_4p2A": "0.0",
            }
        ],
    )
    _write_json(diagnostics_json, {"drd2_pose_physics_diagnostics": {}})
    out_json = tmp_path / "packet.json"
    out_md = tmp_path / "packet.md"
    out_csv = tmp_path / "packet_rows.csv"

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_drd2_pose_generation_repair_packet.py"),
            "--rows-csv",
            str(rows_csv),
            "--stage3-csv",
            str(stage3_csv),
            "--atom-cache-csv",
            str(atom_cache_csv),
            "--diagnostics-json",
            str(diagnostics_json),
            "--top-decoys",
            "1",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--out-csv",
            str(out_csv),
        ],
        check=True,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert result.returncode == 0
    assert payload["summary"]["status"] == "blocked_pose_generation_repair_required"
    assert "GPCR DRD2 Pose Generation Repair Packet" in out_md.read_text(encoding="utf-8")
    assert "CHEMBL301265" in out_csv.read_text(encoding="utf-8")
