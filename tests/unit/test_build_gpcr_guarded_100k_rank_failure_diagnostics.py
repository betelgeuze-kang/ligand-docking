from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from tools import build_gpcr_guarded_100k_rank_failure_diagnostics as mod

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


def _pdb_atom(record: str, serial: int, atom: str, resn: str, chain: str, resi: int, x: float, y: float, z: float) -> str:
    return (
        f"{record:<6}{serial:5d} {atom:^4s} {resn:>3s} {chain:1s}{resi:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00           {atom[0]:>2s}"
    )


def test_atom_anchor_diagnostics_selects_native_acidic_pocket_anchor(tmp_path: Path) -> None:
    pdb = tmp_path / "native.pdb"
    pdb.write_text(
        "\n".join(
            [
                _pdb_atom("ATOM", 1, "OD1", "ASP", "A", 114, 0.0, 0.0, 0.0),
                _pdb_atom("ATOM", 2, "OD2", "ASP", "A", 114, 0.5, 0.0, 0.0),
                _pdb_atom("ATOM", 3, "OE1", "GLU", "A", 200, 20.0, 0.0, 0.0),
                _pdb_atom("HETATM", 4, "C1", "LIG", "A", 900, 0.0, 0.0, 2.5),
                _pdb_atom("HETATM", 5, "C2", "LIG", "A", 900, 0.5, 0.0, 2.5),
                _pdb_atom("HETATM", 6, "C3", "LIG", "A", 900, 0.0, 0.5, 2.5),
                _pdb_atom("HETATM", 7, "C4", "LIG", "A", 900, 0.5, 0.5, 2.5),
                _pdb_atom("HETATM", 8, "C5", "LIG", "A", 900, 0.0, 0.0, 3.0),
                "END",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    npz = tmp_path / "traj.npz"
    np.savez(
        npz,
        ligand_frames=np.asarray([[[0.0, 0.0, 2.0]], [[0.0, 0.0, 5.0]], [[0.0, 0.0, 7.0]]], dtype=np.float32),
        protein_atom_frames=np.asarray(
            [
                [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0], [20.0, 0.0, 0.0]],
                [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0], [20.0, 0.0, 0.0]],
                [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0], [20.0, 0.0, 0.0]],
            ],
            dtype=np.float32,
        ),
    )

    payload = mod._atom_anchor_diagnostics(
        {"protein_structure_source_path": str(pdb), "trajectory_npz": str(npz)}
    )

    assert payload["available"] is True
    assert payload["basis"] == "native_pdb_acidic_anchor_plus_trajectory_npz"
    assert payload["anchor_template"]["anchor_resn"] == "ASP"
    assert payload["anchor_template"]["anchor_resi"] == "114"
    assert payload["anchor_min_distance_A"] == 2.0
    assert payload["anchor_contact_fraction_le_4A"] == 1 / 3
    assert payload["anchor_contact_fraction_le_6A"] == 2 / 3

    trajectory_pose = mod._trajectory_pose_preservation_proxy({"trajectory_npz": str(npz)})
    assert trajectory_pose["available"] is True
    assert trajectory_pose["basis"] == "trajectory_ligand_frames_first_frame_rmsd"
    assert trajectory_pose["frame_count"] == 3
    assert np.isclose(trajectory_pose["p90_frame_rmsd_A"], 4.6)
    assert trajectory_pose["support_proxy"] == 0.0

    trajectory_survival = mod._trajectory_survival_proxy(
        {
            "trajectory_ligand_presence_fraction": "1.0",
            "frame_contact_presence_fraction": "0.5",
            "clash_frame_fraction": "0.25",
        }
    )
    assert trajectory_survival["available"] is True
    assert trajectory_survival["basis"] == "trajectory_ligand_presence_contact_presence_clash_absence"
    assert trajectory_survival["support_proxy"] == 0.75


def test_rank_failure_packet_flags_non_adrb2_tail_positive_and_decoy_intrusion(tmp_path: Path) -> None:
    rows_csv = tmp_path / "rows.csv"
    stage3_csv = tmp_path / "stage3.csv"
    ci_json = tmp_path / "ci.json"
    readiness_json = tmp_path / "readiness.json"
    _write_csv(
        rows_csv,
        [
            {
                "target": "ADRB2_GPCR_BLIND",
                "ligand_id": "adrb2_pos",
                "is_binder": "1",
                "reference_binding_kcal_mol": "-9.0",
                "binding_score_composite_v7": "-15.0",
                "mean_min_distance_A": "4.1",
            },
            *[
                {
                    "target": "CHEMBL217_DRD2_HUMAN",
                    "ligand_id": f"decoy_drd2_{idx}",
                    "is_binder": "0",
                    "reference_binding_kcal_mol": "-2.95",
                    "binding_score_composite_v7": str(-12.0 + idx * 0.1),
                    "mean_min_distance_A": "4.2",
                }
                for idx in range(21)
            ],
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "is_binder": "1",
                "reference_binding_kcal_mol": "-14.7",
                "binding_score_composite_v7": "-3.0",
                "mean_min_distance_A": "4.9",
            },
        ],
    )
    _write_csv(
        stage3_csv,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "ligand_affinity_hint": "0.33",
                "ligand_h_donors": "2",
                "ligand_h_acceptors": "4",
                "binding_energy_mmpbsa_kcal_mol_proxy": "-0.04",
                "mean_min_distance_A": "4.9",
                "contact_fraction": "0.002",
            }
        ],
    )
    _write_json(
        ci_json,
        {
            "summary": {
                "ranking_pr_auc": 0.2,
                "ranking_pr_auc_ci_low": 0.01,
                "ranking_topk_hit_rate": 0.1,
                "ranking_positive_count": 2,
                "threshold": 0.45,
            }
        },
    )
    _write_json(readiness_json, {"summary": {"blockers": ["ci_low_below_threshold"]}})

    payload = mod.build_packet(
        rows_csv=rows_csv,
        stage3_csv=stage3_csv,
        ci_json=ci_json,
        readiness_json=readiness_json,
        generated_at_local="2026-05-03T00:00:00+09:00",
    )

    assert payload["summary"]["status"] == "blocked_ranking_quality"
    assert payload["summary"]["claim_promotion_allowed"] is False
    assert payload["summary"]["scorer_apply_allowed"] is False
    assert payload["summary"]["next_action"] in {
        "shadow_replay_acidic_anchor_overcontact_prior_gate_v4",
        "build_claim_locked_fixed_reference_live_gpcr_v5_shadow_after_v4_reject",
        "return_to_drd2_pose_physics_rescue_after_v5_reject",
        "run_score_only_shadow_replay_class_a_motif_shadow_v6",
        "rework_class_a_motif_shadow_v6_after_replay_reject",
        "run_score_only_shadow_replay_class_a_anchor_geometry_shadow_v7",
        "rework_class_a_anchor_geometry_shadow_v7_after_replay_reject",
        "guarded_review_class_a_anchor_geometry_shadow_v7",
        "build_atom_window_cache_then_run_direct_atom_anchor_window_shadow_v8",
        "rework_direct_atom_anchor_window_shadow_v8_after_replay_reject",
        "guarded_review_direct_atom_anchor_window_shadow_v8",
        "run_v2_preserved_score_only_shadow_replay_atom_window_excess_polar_v9",
        "reject_atom_window_excess_polar_shadow_v9_return_to_pose_generation_and_decoy_design",
        "guarded_review_atom_window_excess_polar_shadow_v9",
    }
    assert payload["summary"]["non_adrb2_tail_positive_count"] == 1
    assert "non_adrb2_positive_tail_rank" in payload["summary"]["blockers"]
    assert "target_internal_decoy_intrusion" in payload["summary"]["blockers"]
    assert "Do not relaunch" in payload["summary"]["next_required_step"]
    assert "guarded apply" in payload["summary"]["next_required_step"]
    assert "full 100k claim review" in payload["summary"]["next_required_step"]
    drd2 = [row for row in payload["positive_rank_diagnostics"] if row["ligand_id"] == "CHEMBL301265"][0]
    assert drd2["global_rank"] == 23
    assert drd2["within_target_rank"] == 22
    assert drd2["features"]["ligand_affinity_hint"] == 0.33


def test_latest_v6_spec_review_accepts_claim_locked_active_locked_shadow_spec(tmp_path: Path) -> None:
    spec_json = tmp_path / "gpcr_residual_prototype_spec_class_a_motif_shadow_v6.json"
    _write_json(
        spec_json,
        {
            "summary": {"prototype_variant": "gpcr_core_class_a_motif_shadow_v6"},
            "prototype": {
                "constraints": {
                    "claim_locked_candidate": True,
                    "shadow_only_candidate": True,
                    "active_score_locked_to_base": True,
                    "scorer_apply_allowed": False,
                    "broad_gpcr_claim_allowed": False,
                    "target_identity_feature_allowed": False,
                    "label_feature_allowed": False,
                    "rank_feature_allowed": False,
                    "ligand_id_feature_allowed": False,
                    "reference_binding_value_allowed": False,
                },
                "tuning": {
                    "variant": "gpcr_core_class_a_motif_shadow_v6",
                    "scope": "class_a_aminergic_opioid_like_orthosteric_sublane",
                },
                "linear_rescore": {
                    "terms": [
                        {"feature": "binding_score_composite_v7_prior_active", "weight": 1.0},
                        {"feature": "class_a_orthosteric_motif_support_proxy", "weight": -0.75},
                        {"feature": "class_a_prior_overreward_invalid_overanchor_pressure", "weight": 1.10},
                    ],
                },
            },
        },
    )

    review = mod._latest_v6_spec_review(spec_json)

    assert review["status"] == "ready_for_score_only_shadow_replay"
    assert review["next_action"] == "run_score_only_shadow_replay_class_a_motif_shadow_v6"
    assert review["active_score_locked_to_base"] is True
    assert review["scorer_apply_allowed"] is False
    assert review["broad_gpcr_claim_allowed"] is False
    assert review["forbidden_feature_flags_green"] is True
    assert review["linear_term_features"] == [
        "binding_score_composite_v7_prior_active",
        "class_a_orthosteric_motif_support_proxy",
        "class_a_prior_overreward_invalid_overanchor_pressure",
    ]


def test_latest_v6_replay_review_rejects_when_below_v2_baseline(tmp_path: Path, monkeypatch) -> None:
    eval_json = tmp_path / "v6_eval.json"
    summary_json = tmp_path / "v6_summary.json"
    _write_json(
        eval_json,
        {
            "metrics_unique": {"pr_auc": 0.36},
            "metrics_ci_unique": {"pr_auc": {"low": 0.01}},
            "topk_unique": [{"k": 20, "hit_rate": 0.15}],
        },
    )
    _write_json(
        summary_json,
        {
            "summary": {"active_score_locked_to_base": True, "active_delta_max_abs": 0.0},
            "residual_prototype": {
                "shadow_only_active_locked": True,
                "class_a_motif_support_positive_count": 10,
                "class_a_prior_overreward_invalid_overanchor_positive_count": 3,
            },
        },
    )
    monkeypatch.setattr(mod, "DEFAULT_V6_REPLAY_EVAL_JSON", str(eval_json))
    monkeypatch.setattr(mod, "DEFAULT_V6_REPLAY_SUMMARY_JSON", str(summary_json))

    review = mod._latest_v6_replay_review()

    assert review["status"] == "reject_evidence"
    assert review["next_action"] == "rework_class_a_motif_shadow_v6_after_replay_reject"
    assert review["beats_v2_shadow_baseline"] is False
    assert review["v2_baseline_label_basis"] == "frozen_r2_matching_labels"
    assert review["v2_pr_auc_baseline"] == mod.FROZEN_R2_V2_SHADOW_PR_AUC_BASELINE
    assert review["v2_pr_auc_ci_low_baseline"] == mod.FROZEN_R2_V2_SHADOW_PR_AUC_CI_LOW_BASELINE
    assert review["active_score_locked_to_base"] is True
    assert review["active_delta_max_abs"] == 0.0


def test_latest_v7_spec_review_accepts_anchor_geometry_shadow_contract(tmp_path: Path) -> None:
    spec_json = tmp_path / "gpcr_residual_prototype_spec_class_a_anchor_geometry_shadow_v7.json"
    _write_json(
        spec_json,
        {
            "summary": {"prototype_variant": "gpcr_core_class_a_anchor_geometry_shadow_v7"},
            "prototype": {
                "constraints": {
                    "claim_locked_candidate": True,
                    "shadow_only_candidate": True,
                    "active_score_locked_to_base": True,
                    "scorer_apply_allowed": False,
                    "broad_gpcr_claim_allowed": False,
                    "target_identity_feature_allowed": False,
                    "label_feature_allowed": False,
                    "rank_feature_allowed": False,
                    "ligand_id_feature_allowed": False,
                    "reference_binding_value_allowed": False,
                },
                "tuning": {
                    "variant": "gpcr_core_class_a_anchor_geometry_shadow_v7",
                    "scope": "class_a_aminergic_opioid_like_orthosteric_sublane",
                },
                "linear_rescore": {
                    "terms": [
                        {"feature": "binding_score_composite_v7_prior_active", "weight": 1.0},
                        {"feature": "class_a_charge_complemented_anchor_geometry_proxy", "weight": -0.60},
                        {"feature": "class_a_orthosteric_occupancy_proxy", "weight": -0.35},
                        {"feature": "class_a_pose_survival_support_proxy", "weight": -0.25},
                        {"feature": "class_a_invalid_anchor_prior_pressure_v7", "weight": 1.20},
                    ],
                },
            },
        },
    )

    review = mod._latest_v7_spec_review(spec_json)

    assert review["status"] == "ready_for_score_only_shadow_replay"
    assert review["next_action"] == "run_score_only_shadow_replay_class_a_anchor_geometry_shadow_v7"
    assert review["active_score_locked_to_base"] is True
    assert review["scorer_apply_allowed"] is False
    assert review["broad_gpcr_claim_allowed"] is False
    assert review["forbidden_feature_flags_green"] is True
    assert review["linear_term_features"] == [
        "binding_score_composite_v7_prior_active",
        "class_a_charge_complemented_anchor_geometry_proxy",
        "class_a_invalid_anchor_prior_pressure_v7",
        "class_a_orthosteric_occupancy_proxy",
        "class_a_pose_survival_support_proxy",
    ]


def test_latest_v7_replay_review_routes_reject_for_below_v2_result(tmp_path: Path, monkeypatch) -> None:
    eval_json = tmp_path / "v7_eval.json"
    summary_json = tmp_path / "v7_summary.json"
    _write_json(
        eval_json,
        {
            "metrics_unique": {"pr_auc": 0.40},
            "metrics_ci_unique": {"pr_auc": {"low": 0.08}},
            "topk_unique": [{"k": 20, "hit_rate": 0.20}],
        },
    )
    _write_json(
        summary_json,
        {
            "summary": {"active_score_locked_to_base": True, "active_delta_max_abs": 0.0},
            "residual_prototype": {
                "shadow_only_active_locked": True,
                "class_a_charge_complemented_anchor_geometry_positive_count": 4,
                "class_a_orthosteric_occupancy_positive_count": 6,
                "class_a_pose_survival_support_positive_count": 5,
                "class_a_invalid_anchor_prior_pressure_v7_positive_count": 3,
            },
        },
    )
    monkeypatch.setattr(mod, "DEFAULT_V7_REPLAY_EVAL_JSON", str(eval_json))
    monkeypatch.setattr(mod, "DEFAULT_V7_REPLAY_SUMMARY_JSON", str(summary_json))

    review = mod._latest_v7_replay_review()

    assert review["status"] == "reject_evidence"
    assert review["next_action"] == "rework_class_a_anchor_geometry_shadow_v7_after_replay_reject"
    assert review["beats_v2_shadow_baseline"] is False
    assert review["v2_baseline_label_basis"] == "frozen_r2_matching_labels"
    assert review["v2_pr_auc_baseline"] == mod.FROZEN_R2_V2_SHADOW_PR_AUC_BASELINE
    assert review["v2_pr_auc_ci_low_baseline"] == mod.FROZEN_R2_V2_SHADOW_PR_AUC_CI_LOW_BASELINE
    assert review["active_score_locked_to_base"] is True
    assert review["charge_complemented_anchor_positive_count"] == 4


def test_latest_v8_spec_review_accepts_direct_atom_window_shadow_contract(tmp_path: Path) -> None:
    spec_json = tmp_path / "gpcr_residual_prototype_spec_direct_atom_anchor_window_shadow_v8.json"
    _write_json(
        spec_json,
        {
            "summary": {"prototype_variant": "gpcr_core_direct_atom_anchor_window_shadow_v8"},
            "prototype": {
                "constraints": {
                    "claim_locked_candidate": True,
                    "shadow_only_candidate": True,
                    "active_score_locked_to_base": True,
                    "requires_precomputed_atom_window_features": True,
                    "scorer_apply_allowed": False,
                    "broad_gpcr_claim_allowed": False,
                    "target_identity_feature_allowed": False,
                    "label_feature_allowed": False,
                    "rank_feature_allowed": False,
                    "ligand_id_feature_allowed": False,
                    "reference_binding_value_allowed": False,
                },
                "tuning": {
                    "variant": "gpcr_core_direct_atom_anchor_window_shadow_v8",
                    "scope": "class_a_aminergic_opioid_like_orthosteric_sublane",
                },
                "linear_rescore": {
                    "terms": [
                        {"feature": "binding_score_composite_v7_prior_active", "weight": 1.0},
                        {"feature": "class_a_direct_atom_window_anchor_geometry_proxy", "weight": -0.75},
                        {"feature": "class_a_atom_window_pose_survival_proxy", "weight": -0.20},
                        {"feature": "class_a_hydrophobic_overcontact_pressure_v8", "weight": 1.35},
                    ],
                },
            },
        },
    )

    review = mod._latest_v8_spec_review(spec_json)

    assert review["status"] == "ready_for_feature_cache_and_score_only_shadow_replay"
    assert review["next_action"] == "build_atom_window_cache_then_run_direct_atom_anchor_window_shadow_v8"
    assert review["requires_precomputed_atom_window_features"] is True
    assert review["active_score_locked_to_base"] is True
    assert review["scorer_apply_allowed"] is False
    assert review["broad_gpcr_claim_allowed"] is False
    assert review["forbidden_feature_flags_green"] is True
    assert review["linear_term_features"] == [
        "binding_score_composite_v7_prior_active",
        "class_a_atom_window_pose_survival_proxy",
        "class_a_direct_atom_window_anchor_geometry_proxy",
        "class_a_hydrophobic_overcontact_pressure_v8",
    ]


def test_packet_adds_drd2_pose_physics_anchor_proxy_diagnostics_from_latest_rows(tmp_path: Path) -> None:
    rows_csv = tmp_path / "rows.csv"
    stage3_csv = tmp_path / "stage3.csv"
    ci_json = tmp_path / "ci.json"
    readiness_json = tmp_path / "readiness.json"
    decoy_a_npz = tmp_path / "decoy_a_traj.npz"
    decoy_b_npz = tmp_path / "decoy_b_traj.npz"
    positive_npz = tmp_path / "positive_traj.npz"
    adrb2_npz = tmp_path / "adrb2_traj.npz"
    np.savez(
        decoy_a_npz,
        ligand_frames=np.asarray([[[0.0, 0.0, 0.0]], [[0.0, 0.0, 4.0]], [[0.0, 0.0, 8.0]]]),
    )
    np.savez(
        decoy_b_npz,
        ligand_frames=np.asarray([[[0.0, 0.0, 0.0]], [[0.0, 0.0, 3.0]], [[0.0, 0.0, 6.0]]]),
    )
    np.savez(
        positive_npz,
        ligand_frames=np.asarray([[[0.0, 0.0, 0.0]], [[0.0, 0.0, 0.4]], [[0.0, 0.0, 0.8]]]),
    )
    np.savez(
        adrb2_npz,
        ligand_frames=np.asarray([[[0.0, 0.0, 0.0]], [[0.0, 0.0, 0.5]], [[0.0, 0.0, 1.0]]]),
    )
    _write_csv(
        rows_csv,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "decoy_drd2_cluster_a",
                "is_binder": "0",
                "reference_binding_kcal_mol": "-2.95",
                "binding_score_composite_v7_residual_active": "-12.0",
                "mean_min_distance_A": "4.3",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "decoy_drd2_cluster_b",
                "is_binder": "0",
                "reference_binding_kcal_mol": "-2.95",
                "binding_score_composite_v7_residual_active": "-11.5",
                "mean_min_distance_A": "4.4",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "is_binder": "1",
                "reference_binding_kcal_mol": "-14.7",
                "binding_score_composite_v7_residual_active": "-6.0",
                "mean_min_distance_A": "4.9",
            },
            {
                "target": "ADRB2_GPCR_BLIND",
                "ligand_id": "adrb2_pos",
                "is_binder": "1",
                "reference_binding_kcal_mol": "-9.0",
                "binding_score_composite_v7_residual_active": "-15.0",
                "mean_min_distance_A": "4.1",
            },
        ],
    )
    _write_csv(
        stage3_csv,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "decoy_drd2_cluster_a",
                "ligand_smiles": "CCCOc1ccccc1C(F)(F)F",
                "binding_energy_mmpbsa_kcal_mol_proxy": "-0.55",
                "stability_score": "0.005",
                "contact_fraction": "0.006",
                "mean_min_distance_A": "4.3",
                "ligand_affinity_hint": "0.55",
                "ligand_onsps_norm": "0.15",
                "residual_shadow_prior_pressure": "1.4",
                "pose_preservation_rmsd_A": "5.5",
                "local_minimization_survival_fraction": "0.20",
                "trajectory_npz": str(decoy_a_npz),
                "trajectory_ligand_presence_fraction": "1.0",
                "frame_contact_presence_fraction": "0.2",
                "clash_frame_fraction": "0.5",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "decoy_drd2_cluster_b",
                "ligand_smiles": "CCc1ccc(-c2ccccc2)cc1",
                "binding_energy_mmpbsa_kcal_mol_proxy": "-0.20",
                "stability_score": "0.002",
                "contact_fraction": "0.002",
                "mean_min_distance_A": "4.4",
                "ligand_affinity_hint": "0.58",
                "ligand_onsps_norm": "0.15",
                "residual_shadow_prior_pressure": "2.0",
                "pose_preservation_rmsd_A": "4.8",
                "local_minimization_survival_fraction": "0.30",
                "trajectory_npz": str(decoy_b_npz),
                "trajectory_ligand_presence_fraction": "1.0",
                "frame_contact_presence_fraction": "0.1",
                "clash_frame_fraction": "0.8",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "ligand_smiles": "CCCN[C@H]1CCc2nc(N)sc2C1",
                "binding_energy_mmpbsa_kcal_mol_proxy": "-0.08",
                "stability_score": "0.001",
                "contact_fraction": "0.001",
                "mean_min_distance_A": "4.9",
                "ligand_affinity_hint": "0.33",
                "ligand_onsps_norm": "0.1",
                "residual_shadow_prior_pressure": "0.0",
                "pose_preservation_rmsd_A": "1.8",
                "local_minimization_survival_fraction": "0.80",
                "trajectory_npz": str(positive_npz),
                "trajectory_ligand_presence_fraction": "1.0",
                "frame_contact_presence_fraction": "1.0",
                "clash_frame_fraction": "0.0",
            },
            {
                "target": "ADRB2_GPCR_BLIND",
                "ligand_id": "adrb2_pos",
                "ligand_smiles": "CC(C)NCC(O)COc1ccccc1",
                "binding_energy_mmpbsa_kcal_mol_proxy": "-0.30",
                "stability_score": "0.004",
                "contact_fraction": "0.005",
                "mean_min_distance_A": "4.1",
                "ligand_affinity_hint": "0.40",
                "ligand_onsps_norm": "0.1",
                "residual_shadow_prior_pressure": "0.0",
                "pose_preservation_rmsd_A": "2.5",
                "local_minimization_survival_fraction": "0.75",
                "trajectory_npz": str(adrb2_npz),
                "trajectory_ligand_presence_fraction": "1.0",
                "frame_contact_presence_fraction": "1.0",
                "clash_frame_fraction": "0.0",
            },
        ],
    )
    _write_json(ci_json, {"summary": {"ranking_pr_auc_ci_low": 0.02, "ranking_topk_hit_rate": 0.1}})
    _write_json(readiness_json, {"summary": {"blockers": []}})

    payload = mod.build_packet(
        rows_csv=rows_csv,
        stage3_csv=stage3_csv,
        ci_json=ci_json,
        readiness_json=readiness_json,
        generated_at_local="2026-05-03T00:00:00+09:00",
    )

    assert payload["summary"]["claim_promotion_allowed"] is False
    assert payload["summary"]["scorer_apply_allowed"] is False
    assert payload["summary"]["next_action"] in {
        "shadow_replay_acidic_anchor_overcontact_prior_gate_v4",
        "build_claim_locked_fixed_reference_live_gpcr_v5_shadow_after_v4_reject",
        "return_to_drd2_pose_physics_rescue_after_v5_reject",
        "run_score_only_shadow_replay_class_a_motif_shadow_v6",
        "rework_class_a_motif_shadow_v6_after_replay_reject",
        "run_score_only_shadow_replay_class_a_anchor_geometry_shadow_v7",
        "rework_class_a_anchor_geometry_shadow_v7_after_replay_reject",
        "guarded_review_class_a_anchor_geometry_shadow_v7",
        "build_atom_window_cache_then_run_direct_atom_anchor_window_shadow_v8",
        "rework_direct_atom_anchor_window_shadow_v8_after_replay_reject",
        "guarded_review_direct_atom_anchor_window_shadow_v8",
        "run_v2_preserved_score_only_shadow_replay_atom_window_excess_polar_v9",
        "reject_atom_window_excess_polar_shadow_v9_return_to_pose_generation_and_decoy_design",
        "guarded_review_atom_window_excess_polar_shadow_v9",
    }
    packet = payload["drd2_pose_physics_diagnostics"]
    assert packet["metadata"]["feature_basis"] == "stage3_csv_proxy_not_atom_anchor"
    assert "contact_fraction" in packet["metadata"]["proxy_source_columns"]
    assert packet["positive"]["ligand_id"] == "CHEMBL301265"
    assert packet["positive"]["rank"] == 4
    assert packet["positive"]["within_target_rank"] == 3
    assert set(packet["positive"]["diagnostics"]) == {
        "conserved_anchor_proxy",
        "pose_physics_support",
        "prior_overreward_without_anchor",
    }
    assert [row["ligand_id"] for row in packet["top_decoy_cluster"]["rows"]] == [
        "decoy_drd2_cluster_a",
        "decoy_drd2_cluster_b",
    ]
    assert packet["top_decoy_cluster"]["mean_diagnostics"]["prior_overreward_without_anchor"] > 0.0
    positive_proxies = packet["positive"]["pose_physics_rescue_proxies"]
    assert positive_proxies["chemistry_heuristics"]["basic_amine_like"] is True
    assert positive_proxies["chemistry_heuristics"]["amine_anchor_support_proxy"] == 1.0
    assert positive_proxies["pose_preservation_rmsd_proxy"]["value"] == 1.8
    assert positive_proxies["local_minimization_survival_proxy"]["support_proxy"] == 0.8
    assert positive_proxies["trajectory_pose_preservation_proxy"]["available"] is True
    assert np.isclose(positive_proxies["trajectory_pose_preservation_proxy"]["p90_frame_rmsd_A"], 0.72)
    assert np.isclose(positive_proxies["trajectory_pose_preservation_proxy"]["support_proxy"], 0.82)
    assert positive_proxies["trajectory_survival_proxy"]["support_proxy"] == 1.0
    cluster_proxy_summary = packet["top_decoy_cluster"]["mean_rescue_proxy_diagnostics"]
    assert cluster_proxy_summary["smiles_available_count"] == 2
    assert cluster_proxy_summary["basic_amine_like_count"] == 0
    assert cluster_proxy_summary["pose_preservation_rmsd_available_count"] == 2
    assert cluster_proxy_summary["trajectory_pose_preservation_available_count"] == 2
    assert cluster_proxy_summary["trajectory_pose_support_mean"] == 0.0
    assert np.isclose(cluster_proxy_summary["trajectory_survival_support_mean"], 0.5)
    rescue = payload["drd2_pose_physics_rescue_after_v5_reject_packet"]
    assert rescue["next_action"] == "return_to_drd2_pose_physics_rescue_after_v5_reject"
    assert rescue["diagnostic_only"] is True
    assert rescue["local_only"] is True
    assert rescue["bounded_no_full_100k"] is True
    assert rescue["claim_promotion_allowed"] is False
    assert rescue["scorer_apply_allowed"] is False
    assert rescue["threshold_relaxation_allowed"] is False
    assert rescue["target_identity_feature_allowed"] is False
    comparison = rescue["positive_vs_top_decoy_cluster"]
    assert comparison["positive_chemistry_heuristics"]["basic_amine_like"] is True
    assert comparison["positive_trajectory_pose_preservation_proxy"]["available"] is True
    assert comparison["amine_anchor_support_separation_positive_minus_decoy_mean"] == 1.0
    assert np.isclose(comparison["trajectory_pose_support_separation_positive_minus_decoy_mean"], 0.82)
    assert np.isclose(comparison["trajectory_survival_support_separation_positive_minus_decoy_mean"], 0.5)


def test_packet_adds_drd2_label_free_motif_aware_diagnostic(tmp_path: Path) -> None:
    rows_csv = tmp_path / "rows.csv"
    stage3_csv = tmp_path / "stage3.csv"
    ci_json = tmp_path / "ci.json"
    readiness_json = tmp_path / "readiness.json"
    positive_npz = tmp_path / "positive_traj.npz"
    decoy_a_npz = tmp_path / "decoy_a_traj.npz"
    decoy_b_npz = tmp_path / "decoy_b_traj.npz"
    np.savez(
        positive_npz,
        ligand_frames=np.asarray([[[0.0, 0.0, 0.0]], [[0.0, 0.0, 0.5]], [[0.0, 0.0, 1.0]]]),
    )
    np.savez(
        decoy_a_npz,
        ligand_frames=np.asarray([[[0.0, 0.0, 0.0]], [[0.0, 0.0, 4.0]], [[0.0, 0.0, 8.0]]]),
    )
    np.savez(
        decoy_b_npz,
        ligand_frames=np.asarray([[[0.0, 0.0, 0.0]], [[0.0, 0.0, 3.5]], [[0.0, 0.0, 7.0]]]),
    )
    _write_csv(
        rows_csv,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "decoy_no_amine_overanchor_prior_a",
                "is_binder": "0",
                "binding_score_composite_v7_residual_active": "-12.0",
                "mean_min_distance_A": "3.3",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "decoy_no_amine_overanchor_prior_b",
                "is_binder": "0",
                "binding_score_composite_v7_residual_active": "-11.0",
                "mean_min_distance_A": "3.4",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "is_binder": "1",
                "binding_score_composite_v7_residual_active": "-6.0",
                "mean_min_distance_A": "4.9",
            },
        ],
    )
    _write_csv(
        stage3_csv,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "decoy_no_amine_overanchor_prior_a",
                "ligand_smiles": "CCOc1ccc(F)cc1",
                "contact_fraction": "0.006",
                "mean_min_distance_A": "3.3",
                "binding_energy_mmpbsa_kcal_mol_proxy": "-0.55",
                "stability_score": "0.006",
                "residual_shadow_prior_pressure": "1.3",
                "trajectory_npz": str(decoy_a_npz),
                "trajectory_ligand_presence_fraction": "1.0",
                "frame_contact_presence_fraction": "0.2",
                "clash_frame_fraction": "0.6",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "decoy_no_amine_overanchor_prior_b",
                "ligand_smiles": "CCc1ccc(Cl)cc1",
                "contact_fraction": "0.0055",
                "mean_min_distance_A": "3.4",
                "binding_energy_mmpbsa_kcal_mol_proxy": "-0.45",
                "stability_score": "0.005",
                "residual_shadow_prior_pressure": "1.1",
                "trajectory_npz": str(decoy_b_npz),
                "trajectory_ligand_presence_fraction": "1.0",
                "frame_contact_presence_fraction": "0.1",
                "clash_frame_fraction": "0.7",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "ligand_smiles": "CCCN[C@H]1CCc2nc(N)sc2C1",
                "contact_fraction": "0.001",
                "mean_min_distance_A": "4.9",
                "binding_energy_mmpbsa_kcal_mol_proxy": "-0.08",
                "stability_score": "0.001",
                "residual_shadow_prior_pressure": "0.0",
                "trajectory_npz": str(positive_npz),
                "trajectory_ligand_presence_fraction": "1.0",
                "frame_contact_presence_fraction": "1.0",
                "clash_frame_fraction": "0.0",
            },
        ],
    )
    _write_json(ci_json, {"summary": {"ranking_pr_auc_ci_low": 0.02, "ranking_topk_hit_rate": 0.1}})
    _write_json(readiness_json, {"summary": {"blockers": []}})

    payload = mod.build_packet(
        rows_csv=rows_csv,
        stage3_csv=stage3_csv,
        ci_json=ci_json,
        readiness_json=readiness_json,
        generated_at_local="2026-05-03T00:00:00+09:00",
    )

    packet = payload["class_a_aminergic_opioid_orthosteric_motif_diagnostic"]
    assert packet["sublane"] == "class_a_aminergic_opioid_orthosteric_motif_diagnostic"
    assert packet["diagnostic_only"] is True
    assert packet["label_free"] is True
    assert packet["claim_promotion_allowed"] is False
    assert packet["scorer_apply_allowed"] is False
    assert packet["router_claim_allowed"] is False
    assert packet["platform_claim_allowed"] is False
    metadata = packet["metadata"]
    assert metadata["claim_promotion_allowed"] is False
    assert metadata["scorer_apply_allowed"] is False
    assert metadata["router_claim_allowed"] is False
    assert metadata["platform_claim_allowed"] is False
    assert {"target", "is_binder", "rank", "ligand_id", "reference_binding"}.issubset(
        set(metadata["forbidden_live_features"])
    )
    comparison = packet["positive_vs_top_decoy_cluster"]
    positive = comparison["positive"]
    decoys = comparison["top_decoy_cluster"]
    assert positive["cationic_basic_amine_support"]["basic_amine_like"] is True
    assert positive["acidic_anchor_window_overanchor_validity"]["acidic_overanchor_flag"] is False
    assert np.isclose(positive["trajectory_pose_survival_proxy"]["pose_support_proxy"], 0.775)
    assert positive["trajectory_pose_survival_proxy"]["survival_support_proxy"] == 1.0
    assert positive["ligand_prior_pressure"]["prior_high_flag"] is False
    assert decoys["cationic_basic_amine_support"]["basic_amine_like_count"] == 0
    assert decoys["acidic_anchor_window_overanchor_validity"]["acidic_overanchor_count"] == 2
    assert decoys["trajectory_pose_survival_proxy"]["pose_support_mean"] == 0.0
    assert decoys["ligand_prior_pressure"]["prior_high_count"] == 2
    assert comparison["basic_amine_absent_acidic_overanchor_prior_high_cluster_count"] == 2
    assert comparison["basic_amine_absent_acidic_overanchor_prior_high_cluster_ligand_ids"] == [
        "decoy_no_amine_overanchor_prior_a",
        "decoy_no_amine_overanchor_prior_b",
    ]
    assert comparison["basic_amine_absent_acidic_overanchor_prior_high_cluster_coverage"] == 1.0
    markdown = mod.render_markdown(payload)
    assert "## DRD2 Label-Free Motif-Aware Diagnostic" in markdown
    assert "sublane: `class_a_aminergic_opioid_orthosteric_motif_diagnostic`" in markdown
    assert "basic_amine_absent_acidic_overanchor_prior_high_cluster_count: `2`" in markdown


def test_packet_adds_drd2_target_internal_pairwise_rank_failure_diagnostic(tmp_path: Path) -> None:
    rows_csv = tmp_path / "rows.csv"
    stage3_csv = tmp_path / "stage3.csv"
    ci_json = tmp_path / "ci.json"
    readiness_json = tmp_path / "readiness.json"
    _write_csv(
        rows_csv,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "decoy_drd2_best",
                "is_binder": "0",
                "binding_score_composite_v7_residual_active": "-12.0",
                "mean_min_distance_A": "4.0",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "decoy_drd2_second",
                "is_binder": "0",
                "binding_score_composite_v7_residual_active": "-9.0",
                "mean_min_distance_A": "4.2",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "is_binder": "1",
                "binding_score_composite_v7_residual_active": "-6.0",
                "mean_min_distance_A": "4.9",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "decoy_drd2_below_positive",
                "is_binder": "0",
                "binding_score_composite_v7_residual_active": "-4.0",
                "mean_min_distance_A": "5.5",
            },
        ],
    )
    _write_csv(
        stage3_csv,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "decoy_drd2_best",
                "contact_fraction": "0.008",
                "mean_min_distance_A": "3.2",
                "binding_energy_mmpbsa_kcal_mol_proxy": "-0.60",
                "stability_score": "0.006",
                "residual_shadow_prior_pressure": "1.5",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "decoy_drd2_second",
                "contact_fraction": "0.007",
                "mean_min_distance_A": "3.6",
                "binding_energy_mmpbsa_kcal_mol_proxy": "-0.40",
                "stability_score": "0.005",
                "residual_shadow_prior_pressure": "1.2",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "contact_fraction": "0.001",
                "mean_min_distance_A": "4.9",
                "binding_energy_mmpbsa_kcal_mol_proxy": "-0.08",
                "stability_score": "0.001",
                "residual_shadow_prior_pressure": "0.0",
            },
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "decoy_drd2_below_positive",
                "contact_fraction": "0.001",
                "mean_min_distance_A": "5.5",
                "binding_energy_mmpbsa_kcal_mol_proxy": "-0.02",
                "stability_score": "0.001",
                "residual_shadow_prior_pressure": "0.1",
            },
        ],
    )
    _write_json(ci_json, {"summary": {"ranking_pr_auc_ci_low": 0.02, "ranking_topk_hit_rate": 0.1}})
    _write_json(readiness_json, {"summary": {"blockers": []}})

    payload = mod.build_packet(
        rows_csv=rows_csv,
        stage3_csv=stage3_csv,
        ci_json=ci_json,
        readiness_json=readiness_json,
        generated_at_local="2026-05-03T00:00:00+09:00",
    )

    packet = payload["drd2_target_internal_pairwise_diagnostic"]
    assert packet["metadata"]["diagnostic_only"] is True
    assert packet["metadata"]["replay_only"] is True
    assert packet["metadata"]["claim_promotion_allowed"] is False
    assert "target" in packet["metadata"]["forbidden_live_features"]
    assert packet["positive"]["ligand_id"] == "CHEMBL301265"
    assert packet["positive"]["score"] == -6.0
    assert packet["positive"]["within_target_rank"] == 3
    assert packet["decoys_above_positive_count"] == 2
    assert packet["decoys_above_positive_fraction"] == 2 / 3
    assert packet["top12_decoy_margin_vs_positive"]["best_margin"] == -6.0
    assert packet["top50_decoy_margin_vs_positive"]["best_margin"] == -6.0
    assert packet["pairwise_win_rate"] == 1 / 3
    assert packet["shadow_replay_snapshot"]["not_claim_evidence"] is True
    assert packet["shadow_replay_snapshot"]["ci_low_computed"] is True
    assert packet["shadow_replay_snapshot"]["family_anchor_v2_shadow_pr_auc"] == 0.5767474245351905
    assert packet["shadow_replay_snapshot"]["family_anchor_v2_shadow_pr_auc_ci_low"] == 0.21066694653866244
    assert packet["shadow_replay_snapshot"]["family_anchor_v2_shadow_drd2_global_rank"] == 8562
    assert packet["shadow_replay_snapshot"]["family_anchor_v2_shadow_drd2_decoys_above_positive_count"] == 2434
    assert packet["shadow_replay_snapshot"]["family_anchor_v2_shadow_drd2_pairwise_win_rate"] == 0.7565756575657565
    assert packet["shadow_replay_snapshot"]["family_anchor_v2_shadow_claim_review_status"] == "blocked_ci_low_below_threshold"
    assert "shadow_replay_pr_auc_ci_low_below_threshold" in packet["guarded_validation_prep"]["blockers"]
    assert packet["guarded_validation_prep"]["ready_for_guarded_apply"] is False
    summary = packet["top_decoy_cluster_anchor_overanchoring_summary"]
    assert summary["cluster_size"] == 3
    assert summary["overanchored_decoy_count"] == 2
    assert summary["mean_prior_overreward_without_anchor"] > 0.0
    acidic = packet["acidic_anchor_overcontact_probe"]
    assert acidic["diagnostic_only"] is True
    assert acidic["probe_name"] == "acidic_anchor_overcontact_pressure_probe"
    assert acidic["selected_decoy_count"] == 3
    assert acidic["atom_anchor_available_count"] == 0
    assert acidic["claim_promotion_allowed"] is False
    assert acidic["scorer_apply_allowed"] is False
    post_v3 = payload["post_v3_acidic_anchor_review"]
    assert post_v3["diagnostic_only"] is True
    assert post_v3["candidate_variant"] == "gpcr_core_acidic_anchor_overcontact_prior_gate_v4"
    assert post_v3["candidate_role"] == "shadow_only_guarded_comparison_direction"
    assert post_v3["claim_promotion_allowed"] is False
    assert post_v3["scorer_apply_allowed"] is False
    assert post_v3["required_scaling_mode"] == "fixed_family_reference"
    assert post_v3["selected_decoy_count"] == 3
    assert post_v3["atom_anchor_available_count"] == 0
    assert post_v3["overcontact_signal_present"] is False
    assert post_v3["short_replay_acceptance"]["drd2_decoys_above_positive_must_be_below"] == 2434
    assert "latest_v4_replay" in post_v3

    markdown = mod.render_markdown(payload)
    assert "## DRD2 Target-Internal Pairwise Diagnostic" in markdown
    assert "decoys_above_positive_count: `2`" in markdown
    assert "pairwise_win_rate: `0.3333333333333333`" in markdown
    assert "acidic_anchor_probe_available_count: `0`" in markdown
    assert "post_v3_candidate_variant: `gpcr_core_acidic_anchor_overcontact_prior_gate_v4`" in markdown
    assert "post_v3_required_scaling_mode: `fixed_family_reference`" in markdown
    assert "post_v4_candidate_variant: `gpcr_core_fixed_reference_live_shadow_v5`" in markdown
    assert "fixed_reference_v2_formula_pr_auc_approx: `0.0076`" in markdown
    assert "fixed_reference_safe_to_port_v2_or_v4_weights: `false`" in markdown
    assert "fixed_reference_pose_chemistry_pressure_nonzero: `4164`" in markdown
    assert "shadow_replay_pr_auc_ci_low: `0.21066694653866244`" in markdown
    assert "shadow_replay_drd2_decoys_above_positive_count: `2434`" in markdown
    assert "shadow_replay_claim_review_status: `blocked_ci_low_below_threshold`" in markdown


def test_packet_reads_latest_stage5_ranking_summary_metrics(tmp_path: Path) -> None:
    rows_csv = tmp_path / "rows.csv"
    stage3_csv = tmp_path / "stage3.csv"
    stage5_json = tmp_path / "stage5.json"
    readiness_json = tmp_path / "readiness.json"
    _write_csv(
        rows_csv,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "is_binder": "1",
                "binding_score_composite_v7_residual_active": "-1.0",
            }
        ],
    )
    _write_csv(stage3_csv, [{"target": "CHEMBL217_DRD2_HUMAN", "ligand_id": "CHEMBL301265"}])
    _write_json(
        stage5_json,
        {
            "metrics_unique": {"pr_auc": 0.518, "positive_count": 9},
            "metrics_ci_unique": {"pr_auc": {"low": 0.148}},
            "topk_unique": [{"k": 20, "hit_rate": 0.25}],
        },
    )
    _write_json(readiness_json, {"summary": {"blockers": []}})

    payload = mod.build_packet(
        rows_csv=rows_csv,
        stage3_csv=stage3_csv,
        ci_json=stage5_json,
        readiness_json=readiness_json,
        generated_at_local="2026-05-03T00:00:00+09:00",
    )

    assert payload["summary"]["ranking_pr_auc"] == 0.518
    assert payload["summary"]["ranking_pr_auc_ci_low"] == 0.148
    assert payload["summary"]["ranking_topk_hit_rate"] == 0.25
    assert payload["summary"]["blockers"] == ["ci_low_below_threshold"]


def test_packet_adds_ci_low_stability_metadata_when_bootstrap_ci_is_present(tmp_path: Path) -> None:
    rows_csv = tmp_path / "rows.csv"
    stage3_csv = tmp_path / "stage3.csv"
    stage5_json = tmp_path / "stage5.json"
    readiness_json = tmp_path / "readiness.json"
    _write_csv(
        rows_csv,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "is_binder": "1",
                "binding_score_composite_v7_residual_active": "-1.0",
            }
        ],
    )
    _write_csv(stage3_csv, [{"target": "CHEMBL217_DRD2_HUMAN", "ligand_id": "CHEMBL301265"}])
    _write_json(
        stage5_json,
        {
            "metrics_unique": {"pr_auc": 0.5767474245351905, "positive_count": 9},
            "metrics_ci_unique": {"pr_auc": {"low": 0.21066694653866244, "high": 0.91}},
            "topk_unique": [{"k": 20, "hit_rate": 0.25}],
        },
    )
    _write_json(readiness_json, {"summary": {"blockers": []}})

    payload = mod.build_packet(
        rows_csv=rows_csv,
        stage3_csv=stage3_csv,
        ci_json=stage5_json,
        readiness_json=readiness_json,
        generated_at_local="2026-05-03T00:00:00+09:00",
    )

    metadata = payload["ci_low_stability_metadata"]
    assert metadata["ci_low_computed"] is True
    assert metadata["diagnostic_only"] is True
    assert metadata["claim_promotion_allowed"] is False
    assert metadata["scorer_apply_allowed"] is False
    assert metadata["base_pr_auc"] == 0.5767474245351905
    assert metadata["base_pr_auc_ci_low"] == 0.21066694653866244
    assert metadata["v2_shadow_pr_auc"] == 0.5767474245351905
    assert metadata["v2_shadow_pr_auc_ci_low"] == 0.21066694653866244
    assert metadata["v2_shadow_drd2_decoys_above_positive_count"] == 2434
    assert metadata["v2_shadow_drd2_pairwise_win_rate"] == 0.7565756575657565
    assert metadata["ci_low_threshold"] == 0.45
    assert metadata["ci_low_gap_to_threshold"] == 0.23933305346133757
    assert metadata["ci_low_status"] == "blocked_below_threshold"
    assert metadata["recommended_next_action"] == "gpcr_core_family_anchor_ci_stability_v3_diagnostic_only"
    assert "do_not_promote_from_point_pr_auc" in metadata["blockers"]
    assert "bootstrap_positive_support_instability" in metadata["stability_hypotheses"]

    markdown = mod.render_markdown(payload)
    assert "## CI-Low Stability Metadata" in markdown
    assert "v2_shadow_pr_auc_ci_low: `0.21066694653866244`" in markdown
    assert "ci_low_gap_to_threshold: `0.23933305346133757`" in markdown
    assert "recommended_next_action: `gpcr_core_family_anchor_ci_stability_v3_diagnostic_only`" in markdown


def test_cli_writes_json_and_markdown(tmp_path: Path) -> None:
    rows_csv = tmp_path / "rows.csv"
    stage3_csv = tmp_path / "stage3.csv"
    ci_json = tmp_path / "ci.json"
    readiness_json = tmp_path / "readiness.json"
    out_json = tmp_path / "diag.json"
    out_md = tmp_path / "diag.md"
    _write_csv(
        rows_csv,
        [
            {
                "target": "ADRB2_GPCR_BLIND",
                "ligand_id": "adrb2_pos",
                "is_binder": "1",
                "reference_binding_kcal_mol": "-9.0",
                "binding_score_composite_v7": "-15.0",
                "mean_min_distance_A": "4.1",
            },
            {
                "target": "ADRB2_GPCR_BLIND",
                "ligand_id": "adrb2_decoy",
                "is_binder": "0",
                "reference_binding_kcal_mol": "-2.95",
                "binding_score_composite_v7": "-2.0",
                "mean_min_distance_A": "5.1",
            },
        ],
    )
    _write_csv(stage3_csv, [{"target": "ADRB2_GPCR_BLIND", "ligand_id": "adrb2_pos"}])
    _write_json(ci_json, {"summary": {"ranking_pr_auc_ci_low": 0.5, "ranking_topk_hit_rate": 0.25}})
    _write_json(readiness_json, {"summary": {"blockers": []}})

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_guarded_100k_rank_failure_diagnostics.py"),
            "--rows-csv",
            str(rows_csv),
            "--stage3-csv",
            str(stage3_csv),
            "--ci-json",
            str(ci_json),
            "--readiness-json",
            str(readiness_json),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    markdown = out_md.read_text(encoding="utf-8")
    assert result.returncode == 0
    assert payload["packet_type"] == "gpcr_guarded_100k_rank_failure_diagnostics"
    assert "GPCR Guarded 100k Rank Failure Diagnostics" in markdown
    assert "scorer_apply_allowed: `false`" in markdown
    assert (
        "shadow_replay_acidic_anchor_overcontact_prior_gate_v4" in markdown
        or "build_claim_locked_fixed_reference_live_gpcr_v5_shadow_after_v4_reject" in markdown
        or "return_to_drd2_pose_physics_rescue_after_v5_reject" in markdown
        or "run_score_only_shadow_replay_class_a_motif_shadow_v6" in markdown
        or "rework_class_a_motif_shadow_v6_after_replay_reject" in markdown
        or "run_score_only_shadow_replay_class_a_anchor_geometry_shadow_v7" in markdown
        or "rework_class_a_anchor_geometry_shadow_v7_after_replay_reject" in markdown
        or "guarded_review_class_a_anchor_geometry_shadow_v7" in markdown
    )
