from __future__ import annotations

import json
from pathlib import Path

from tools.build_wetlab_tcruzi_pde_allatom_review_packet import build_payload


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_build_wetlab_tcruzi_pde_allatom_review_packet(tmp_path: Path) -> None:
    scoring_json = tmp_path / "summary.json"
    claim_json = tmp_path / "claim_readiness.json"
    scoring_json.write_text(
        json.dumps(
            {
                "topk": [
                    {
                        "ligand_id": "lig_a",
                        "mean_min_distance_A": 2.2,
                        "binding_energy_proxy": -1.0,
                        "binding_energy_mmpbsa_kcal_mol_proxy": -1.0,
                        "binding_energy_mmpbsa_std": 0.1,
                        "stability_score": 0.4,
                        "contact_fraction": 0.6,
                        "trajectory_frames": 220,
                        "ligand_model": "3bead_implicit_hbond",
                        "backmapped_pdb": "a.pdb",
                        "score_json": "a.json",
                        "replicate_count": 3,
                        "replicate_pass_fraction": 0.667,
                        "median_mean_min_distance_A": 2.25,
                        "mean_min_distance_iqr_A": 0.2,
                        "median_contact_fraction": 0.58,
                        "pose_cluster_dominance": 0.71,
                        "pose_preservation_rmsd_A": 1.2,
                        "backmapping_consistency_score": 0.83,
                        "local_minimization_survival_fraction": 0.78,
                    },
                    {
                        "ligand_id": "lig_b",
                        "mean_min_distance_A": 2.9,
                        "binding_energy_proxy": -0.8,
                        "binding_energy_mmpbsa_kcal_mol_proxy": -0.8,
                        "binding_energy_mmpbsa_std": 0.2,
                        "stability_score": 0.3,
                        "contact_fraction": 0.5,
                        "trajectory_frames": 210,
                        "ligand_model": "3bead_implicit_hbond",
                        "backmapped_pdb": "b.pdb",
                        "score_json": "b.json",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    _write_json(
        claim_json,
        {
            "summary": {
                "policy_version": "test_policy_v1",
                "pass_core_gate": True,
                "claim_ready_for_allatom": False,
            }
        },
    )
    lane_payload = {
        "summary": {
            "shard_id": "20_of_20",
            "selected_command_kind": "pseudo_allatom_backmapping_rescore",
            "selected_threshold_A": 2.5,
            "allatom_ligand_model": "3bead_implicit_hbond",
        },
        "rows": [
            {
                "ligand_id": "lig_a",
                "compound_name": "cmpd-a",
                "compound_name_resolution": "human_readable",
                "smiles": "CC",
                "source_three_bead_priority_rank": 1,
                "source_rescue_review_band": "strict_pass",
                "source_three_bead_contact_fraction": 0.64,
                "source_three_bead_trajectory_frames": 180,
                "translation_gate_version": "three_bead_to_allatom_translation_v1",
                "translation_gate_band_bucket": "strict",
                "translation_gate_score": 86.0,
                "translation_gate_status": "pass",
                "translation_gate_pass": True,
                "translation_gate_required_check_count": 3,
                "translation_gate_required_pass_count": 3,
                "translation_gate_optional_check_count": 2,
                "translation_gate_optional_pass_count": 2,
                "translation_gate_failed_checks": [],
                "translation_gate_warning_checks": [],
                "translation_gate_passed_checks": ["distance_within_translation_near_band"],
                "translation_gate_requires_pose_tightening": False,
                "translation_gate_reason": "translation looks strong",
                "stronger_physics_shortlist_version": "stronger_physics_shortlist_v1",
                "shortlist_tier": "tier1_gold",
                "shortlist_promising": True,
                "recommended_next_expensive_lane": "ensemble_explicit_water_mmgbsa",
                "recommended_next_expensive_lane_priority": 1,
                "recommended_next_expensive_lane_reason": "strong strict candidate",
            },
            {
                "ligand_id": "lig_b",
                "compound_name": "cmpd-b",
                "compound_name_resolution": "human_readable",
                "smiles": "CCC",
                "source_three_bead_priority_rank": 2,
                "source_rescue_review_band": "near_band",
            },
        ],
    }
    runner_payload = {"summary": {"allatom_summary_json": str(scoring_json), "scoring_status": "pass", "execution_mode": "pseudo_allatom_backmapping_scoring_executed"}}
    payload = build_payload(lane_payload, runner_payload, claim_readiness_json=str(claim_json))
    summary = payload["summary"]
    assert summary["packet_ready_for_operator_review"] is True
    assert summary["wetlab_gate_pass"] is True
    assert summary["claim_gate_available"] is True
    assert summary["claim_gate_source"] == "claim_readiness_json"
    assert summary["claim_gate_policy_version"] == "test_policy_v1"
    assert summary["claim_gate_semantics_version"] == "claim_equivalence_semantics_v2"
    assert summary["claim_gate_requirement_mode"] == "semi_hard"
    assert summary["claim_gate_requirement_provenance"] == "target_group_default"
    assert summary["claim_gate_target_group"] == "neglected_disease_priority_v1"
    assert summary["claim_gate_required_for_final_wetlab"] is True
    assert summary["claim_gate_required_for_commercial_readiness"] is True
    assert summary["claim_ready_for_allatom"] is False
    assert summary["claim_gate_status"] == "claim_blocked"
    assert summary["claim_gate_satisfied"] is False
    assert summary["claim_gate_primary_action"] == "resolve_claim_equivalence_gate"
    assert summary["wetlab_final_gate_pass"] is False
    assert summary["wetlab_final_gate_mode"] == "band_plus_semi_hard_claim_ready_for_allatom"
    assert summary["wetlab_final_gate_failed_metrics"] == ["claim_ready_for_allatom"]
    assert summary["wetlab_final_gate_missing_metrics"] == []
    assert summary["wetlab_final_gate_required_next_actions"] == [
        "resolve_claim_equivalence_gate",
        "produce_claim_equivalence_packet",
    ]
    assert summary["commercial_schema_version"] == "wetlab_commercial_grade_v1"
    assert summary["commercial_hard_gate_pass_v1"] is False
    assert summary["commercial_decision_class_v1"] == "commercial_borderline_refine"
    assert summary["commercial_risk_bucket_v1"] == "moderate"
    assert summary["commercial_hard_gate_failed_metric_count_v1"] == 1
    assert summary["commercial_hard_gate_missing_metric_count_v1"] == 0
    assert "claim_ready_for_allatom" in summary["commercial_hard_gate_failed_metrics_v1"]
    assert summary["commercial_soft_score_v1"] > 90.0
    assert summary["commercial_confidence_score_v1"] >= 79.0
    assert summary["commercial_consistency_score_v1"] == 80.0
    assert summary["commercial_schema_version_v2"] == "wetlab_commercial_grade_v2"
    assert summary["commercial_hard_gate_pass_v2"] is False
    assert summary["commercial_decision_class_v2"] == "commercial_borderline_refine"
    assert summary["commercial_robustness_inputs_available_v2"] is True
    assert summary["commercial_replicate_count_v2"] == 3
    assert summary["commercial_pose_consistency_score_v2"] is not None
    assert summary["commercial_claim_requirement_mode_v2"] == "semi_hard"
    assert summary["commercial_claim_primary_action_v2"] == "resolve_claim_equivalence_gate"
    assert summary["translation_gate_version"] == "three_bead_to_allatom_translation_v1"
    assert summary["translation_gate_focus_status"] == "pass"
    assert summary["focus_shortlist_tier"] == "tier1_gold"
    assert summary["recommended_next_expensive_lane"] == "ensemble_explicit_water_mmgbsa"
    assert summary["promoted_candidate_count"] == 2
    assert summary["under_2p5_candidate_count"] == 1
    assert summary["near_candidate_count"] == 1
    assert summary["best_ligand_id"] == "lig_a"
    assert payload["rows"][0]["commercial_hard_gate_pass_v1"] is False
    assert payload["rows"][0]["commercial_hard_gate_pass_v2"] is False
    assert payload["rows"][0]["commercial_claim_requirement_mode_v2"] == "semi_hard"
    assert payload["rows"][0]["translation_gate_status"] == "pass"
    assert payload["rows"][0]["recommended_next_expensive_lane"] == "ensemble_explicit_water_mmgbsa"
    assert "resolve_claim_equivalence_gate" in payload["rows"][0]["commercial_upgrade_actions_v1"]
    assert "semi-hard claim/equivalence requirement is cleared" in summary["next_required_step"]


def test_build_wetlab_tcruzi_pde_allatom_review_packet_uses_strict_candidate_as_best_metric(
    tmp_path: Path,
) -> None:
    scoring_json = tmp_path / "summary.json"
    scoring_json.write_text(
        json.dumps(
            {
                "topk": [
                    {
                        "ligand_id": "lig_near_first",
                        "mean_min_distance_A": 2.756,
                        "binding_energy_proxy": -2.0,
                        "trajectory_frames": 220,
                    },
                    {
                        "ligand_id": "t_cruzi_pde_20_of_20_095609",
                        "mean_min_distance_A": 0.672,
                        "binding_energy_proxy": -1.0,
                        "trajectory_frames": 220,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    lane_payload = {
        "summary": {
            "shard_id": "20_of_20",
            "selected_command_kind": "pseudo_allatom_backmapping_rescore",
            "selected_threshold_A": 2.5,
        },
        "rows": [
            {"ligand_id": "lig_near_first", "compound_name": "Near First"},
            {
                "ligand_id": "t_cruzi_pde_20_of_20_095609",
                "compound_name": "Strict Candidate",
                "compound_name_human_readable": "Strict Candidate",
            },
        ],
    }
    runner_payload = {"summary": {"allatom_summary_json": str(scoring_json)}}

    payload = build_payload(lane_payload, runner_payload)

    summary = payload["summary"]
    assert summary["wetlab_gate_pass"] is True
    assert summary["under_2p5_candidate_count"] == 1
    assert summary["best_ligand_id"] == "t_cruzi_pde_20_of_20_095609"
    assert summary["best_mean_min_distance_A"] == 0.672
    assert payload["rows"][0]["ligand_id"] == "lig_near_first"


def test_build_wetlab_tcruzi_pde_allatom_review_packet_requires_claim_artifact_for_final_gate(
    tmp_path: Path,
) -> None:
    scoring_json = tmp_path / "summary.json"
    scoring_json.write_text(
        json.dumps(
            {
                "topk": [
                    {
                        "ligand_id": "lig_a",
                        "mean_min_distance_A": 2.2,
                        "binding_energy_proxy": -1.0,
                        "binding_energy_mmpbsa_kcal_mol_proxy": -1.0,
                        "binding_energy_mmpbsa_std": 0.1,
                        "stability_score": 0.4,
                        "contact_fraction": 0.6,
                        "trajectory_frames": 220,
                        "ligand_model": "3bead_implicit_hbond",
                        "backmapped_pdb": "a.pdb",
                        "score_json": "a.json",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    lane_payload = {
        "summary": {
            "shard_id": "20_of_20",
            "selected_command_kind": "pseudo_allatom_backmapping_rescore",
            "selected_threshold_A": 2.5,
            "allatom_ligand_model": "3bead_implicit_hbond",
        },
        "rows": [{"ligand_id": "lig_a"}],
    }
    runner_payload = {
        "summary": {
            "allatom_summary_json": str(scoring_json),
            "scoring_status": "pass",
            "execution_mode": "pseudo_allatom_backmapping_scoring_executed",
        }
    }

    payload = build_payload(lane_payload, runner_payload)
    summary = payload["summary"]

    assert summary["wetlab_gate_pass"] is True
    assert summary["claim_gate_available"] is False
    assert summary["claim_gate_requirement_mode"] == "semi_hard"
    assert summary["claim_gate_status"] == "claim_required_unavailable"
    assert summary["claim_gate_primary_action"] == "produce_claim_equivalence_packet"
    assert summary["wetlab_final_gate_pass"] is False
    assert summary["wetlab_final_gate_missing_metrics"] == ["claim_gate_required_unavailable"]
    assert summary["wetlab_final_gate_required_next_actions"] == [
        "produce_claim_equivalence_packet",
        "resolve_claim_equivalence_gate",
    ]
    assert "claim_gate_required_unavailable" in summary["commercial_hard_gate_missing_metrics_v1"]
    assert "claim_gate_required_unavailable" in summary["commercial_hard_gate_missing_metrics_v2"]


def test_build_wetlab_tcruzi_pde_allatom_review_packet_passes_when_claim_ready(tmp_path: Path) -> None:
    scoring_json = tmp_path / "summary.json"
    claim_json = tmp_path / "claim_readiness.json"
    scoring_json.write_text(
        json.dumps(
            {
                "topk": [
                    {
                        "ligand_id": "lig_a",
                        "mean_min_distance_A": 2.2,
                        "binding_energy_proxy": -1.0,
                        "binding_energy_mmpbsa_kcal_mol_proxy": -1.0,
                        "binding_energy_mmpbsa_std": 0.1,
                        "stability_score": 0.4,
                        "contact_fraction": 0.6,
                        "trajectory_frames": 220,
                        "ligand_model": "3bead_implicit_hbond",
                        "backmapped_pdb": "a.pdb",
                        "score_json": "a.json",
                        "replicate_count": 3,
                        "replicate_pass_fraction": 0.667,
                        "median_mean_min_distance_A": 2.25,
                        "mean_min_distance_iqr_A": 0.2,
                        "median_contact_fraction": 0.58,
                        "pose_cluster_dominance": 0.71,
                        "pose_preservation_rmsd_A": 1.2,
                        "backmapping_consistency_score": 0.83,
                        "local_minimization_survival_fraction": 0.78,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    _write_json(
        claim_json,
        {
            "summary": {
                "policy_version": "test_policy_v1",
                "pass_core_gate": True,
                "claim_ready_for_allatom": True,
            }
        },
    )
    lane_payload = {
        "summary": {
            "shard_id": "20_of_20",
            "selected_command_kind": "pseudo_allatom_backmapping_rescore",
            "selected_threshold_A": 2.5,
            "allatom_ligand_model": "3bead_implicit_hbond",
        },
        "rows": [
            {
                "ligand_id": "lig_a",
                "compound_name": "cmpd-a",
                "compound_name_resolution": "human_readable",
                "smiles": "CC",
                "source_three_bead_priority_rank": 1,
                "source_rescue_review_band": "strict_pass",
                "source_three_bead_contact_fraction": 0.64,
                "source_three_bead_trajectory_frames": 180,
                "translation_gate_version": "three_bead_to_allatom_translation_v1",
                "translation_gate_band_bucket": "strict",
                "translation_gate_score": 86.0,
                "translation_gate_status": "pass",
                "translation_gate_pass": True,
                "translation_gate_required_check_count": 3,
                "translation_gate_required_pass_count": 3,
                "translation_gate_optional_check_count": 2,
                "translation_gate_optional_pass_count": 2,
                "translation_gate_failed_checks": [],
                "translation_gate_warning_checks": [],
                "translation_gate_passed_checks": ["distance_within_translation_near_band"],
                "translation_gate_requires_pose_tightening": False,
                "translation_gate_reason": "translation looks strong",
                "stronger_physics_shortlist_version": "stronger_physics_shortlist_v1",
                "shortlist_tier": "tier1_gold",
                "shortlist_promising": True,
                "recommended_next_expensive_lane": "ensemble_explicit_water_mmgbsa",
                "recommended_next_expensive_lane_priority": 1,
                "recommended_next_expensive_lane_reason": "strong strict candidate",
            }
        ],
    }
    runner_payload = {
        "summary": {
            "allatom_summary_json": str(scoring_json),
            "scoring_status": "pass",
            "execution_mode": "pseudo_allatom_backmapping_scoring_executed",
        }
    }
    payload = build_payload(lane_payload, runner_payload, claim_readiness_json=str(claim_json))
    summary = payload["summary"]
    assert summary["claim_gate_available"] is True
    assert summary["claim_gate_requirement_mode"] == "semi_hard"
    assert summary["claim_ready_for_allatom"] is True
    assert summary["wetlab_final_gate_pass"] is True
    assert summary["wetlab_final_gate_failed_metrics"] == []
    assert summary["wetlab_final_gate_mode"] == "band_plus_semi_hard_claim_ready_for_allatom"
    assert summary["commercial_schema_version_v2"] == "wetlab_commercial_grade_v2"
    assert summary["commercial_robustness_inputs_available_v2"] is True
    assert summary["commercial_robustness_metric_count_v2"] == 9
    assert summary["commercial_replicate_count_v2"] == 3
    assert summary["commercial_replicate_pass_fraction_v2"] == 0.667
    assert summary["commercial_hard_gate_pass_v2"] is True
    assert summary["commercial_decision_class_v2"] == "commercial_wetlab_ready"
    assert summary["commercial_risk_bucket_v2"] == "low"
    assert summary["commercial_overall_score_v2"] >= 87.0
    assert summary["commercial_confidence_score_v2"] >= 80.0
    assert summary["commercial_primary_upgrade_actions_v2"] == []
    assert summary["next_required_step"].startswith(
        "Review the promoted PDE pseudo all-atom top-4 packet, keep the default lane closed,"
    )
    assert "strict_only gate pass" in summary["next_required_step"]
    assert payload["rows"][0]["translation_gate_status"] == "pass"
    assert payload["rows"][0]["recommended_next_expensive_lane"] == "ensemble_explicit_water_mmgbsa"
    assert payload["rows"][0]["commercial_hard_gate_pass_v2"] is True
