from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_gpcr_a1_accuracy_repair_queue as mod

ROOT = Path(__file__).resolve().parents[2]


def test_default_pose_gap_uses_latest_v16_adaptive_packet() -> None:
    assert (
        mod.DEFAULT_POSE_GAP_JSON
        == "runs/gpcr_false_support_discriminator_v16_adaptive_frozen_gap_packet_current.json"
    )
    assert (
        mod.DEFAULT_HTR2A_TOPOLOGY_REPLAY_JSON
        == "runs/gpcr_htr2a_topology_support_shadow_replay_summary_current.json"
    )
    assert (
        mod.DEFAULT_OPRM1_TOPOLOGY_REPLAY_JSON
        == "runs/gpcr_oprm1_topology_pose_shadow_replay_summary_current.json"
    )
    assert (
        mod.DEFAULT_DRD2_WEAKBASE_REPLAY_JSON
        == "runs/gpcr_drd2_weakbase_false_support_shadow_replay_summary_current.json"
    )
    assert mod.DEFAULT_SHADOW_CLAIM_REVIEW_JSON == "runs/gpcr_guarded_shadow_claim_review_current.json"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_build_queue_prioritizes_drd2_backmapping_before_rerun(tmp_path: Path) -> None:
    scorecard = tmp_path / "scorecard.json"
    drd2 = tmp_path / "drd2.json"
    support = tmp_path / "support.json"
    readiness = tmp_path / "readiness.json"
    parameterization_probe = tmp_path / "parameterization_probe.json"
    protein_repair = tmp_path / "protein_repair.json"
    hard_decoy_envelope = tmp_path / "hard_decoy_envelope.json"
    drd2_weakbase_replay = tmp_path / "drd2_weakbase_replay.json"
    htr2a_repair_packet = tmp_path / "htr2a_repair_packet.json"
    htr2a_topology_probe = tmp_path / "htr2a_topology_probe.json"
    htr2a_life_science = tmp_path / "htr2a_life_science.json"
    htr2a_topology_replay = tmp_path / "htr2a_topology_replay.json"
    oprm1_life_science = tmp_path / "oprm1_life_science.json"
    oprm1_topology_replay = tmp_path / "oprm1_topology_replay.json"
    shadow_claim_review = tmp_path / "shadow_claim_review.json"
    pose_gap = tmp_path / "pose_gap.json"
    ranking = tmp_path / "ranking.json"
    _write_json(scorecard, {"summary": {"status": "blocked_accuracy_parity"}})
    _write_json(
        drd2,
        {
            "summary": {
                "target": "CHEMBL217_DRD2_HUMAN",
                "positive_ligand_id": "CHEMBL301265",
                "positive_global_rank": 18923,
                "positive_within_target_rank": 5315,
                "decoys_above_positive_count": 5314,
                "positive_backmapping_atom_coverage_ratio": 0.142857,
                "positive_ligand_frame_atom_count": 2,
                "positive_smiles_heavy_atom_count": 14,
                "overanchored_decoy_count": 3,
                "atom_window_like_decoy_count": 2,
                "multipolar_basic_decoy_count": 1,
            }
        },
    )
    _write_json(
        support,
        {
            "summary": {
                "status": "drd2_atom_typed_backmapping_blocked",
                "selected_row_count": 17,
                "blocked_row_count": 17,
                "positive_backmapping_atom_coverage_ratio": 0.142857,
                "positive_full_atom_typed_backmapping_ready": False,
                "positive_minimum_coverage_gate_pass": False,
                "positive_pose_preservation_rmsd_A_p90": 0.27,
                "positive_local_minimization_survival_fraction": None,
                "positive_local_minimization_survival_engine_kind": None,
                "positive_local_minimization_survival_claim_scope": None,
                "positive_local_minimization_survival_hard_decoy_evidence_allowed": False,
                "positive_local_minimization_survival_source_blockers": [],
                "positive_blockers": [
                    "backmapped_pdb_missing",
                    "backmapping_atom_coverage_below_min",
                    "cationic_center_anchor_not_atom_typed",
                    "full_atom_typed_backmapping_missing",
                    "local_minimization_survival_missing",
                ],
                "claim_promotion_allowed": False,
                "scorer_apply_allowed": False,
                "hard_decoy_rebuild_allowed": False,
                "guarded_100k_rerun_allowed": False,
                "next_required_step": "Generate claim-grade full-forcefield DRD2 local-minimization survival evidence before hard-decoy rebuild or guarded 100k claim review.",
            }
        },
    )
    _write_json(
        readiness,
        {
            "summary": {
                "status": "blocked",
                "full_forcefield_minimization_ready": False,
                "protein_parameterization_available": False,
                "ligand_parameterization_available": False,
                "missing_dependencies": ["openff.toolkit", "openmmforcefields", "pdbfixer"],
                "missing_assets": ["chimerax_tleap"],
            }
        },
    )
    _write_json(
        parameterization_probe,
        {
            "summary": {
                "claim_grade_parameterization_ready": False,
                "local_probe_partial": True,
                "ligand_template_parameterization_available": True,
            }
        },
    )
    _write_json(
        protein_repair,
        {
            "summary": {
                "missing_heavy_atom_residue_count": 70,
                "incomplete_histidine_count": 2,
                "claim_grade_repair_allowed": False,
            }
        },
    )
    _write_json(hard_decoy_envelope, {"summary": {}})
    _write_json(drd2_weakbase_replay, {"summary": {}})
    _write_json(htr2a_repair_packet, {"summary": {}})
    _write_json(htr2a_topology_probe, {"summary": {}})
    _write_json(htr2a_life_science, {"summary": {}})
    _write_json(htr2a_topology_replay, {"summary": {}})
    _write_json(oprm1_life_science, {"summary": {}})
    _write_json(oprm1_topology_replay, {"summary": {}})
    _write_json(shadow_claim_review, {"summary": {}})
    _write_json(
        pose_gap,
        {
            "target_summaries": [
                {
                    "target": "CHEMBL224_HTR2A_HUMAN",
                    "ligand_id": "CHEMBL83894",
                    "global_rank": 304,
                    "target_rank": 129,
                    "decoys_above_positive": 128,
                    "label_free_support_pressure": 0.0,
                    "pose_preservation_support": 0.3941,
                    "coarse_centroid_preservation_rmsd_A_mean": 2.21,
                    "blockers": ["positive_anchor_support_missing"],
                },
                {
                    "target": "CHEMBL233_OPRM1_HUMAN",
                    "ligand_id": "CHEMBL331883",
                    "global_rank": 1379,
                    "target_rank": 322,
                    "decoys_above_positive": 321,
                    "label_free_support_pressure": 0.0,
                    "pose_preservation_support": 0.0,
                    "coarse_centroid_preservation_rmsd_A_mean": 34.16,
                    "blockers": ["positive_pose_backmapping_collapse"],
                },
            ]
        },
    )
    _write_json(
        ranking,
        {
            "summary": {
                "ranking_pr_auc": 0.5187,
                "ranking_pr_auc_ci_low": 0.1486,
                "ranking_topk_hit_rate": 0.25,
                "worst_positive_global_rank": 18923,
                "worst_positive_within_target_rank": 5315,
            }
        },
    )

    payload = mod.build_queue(
        accuracy_scorecard_json=scorecard,
        drd2_repair_json=drd2,
        drd2_backmapping_support_json=support,
        drd2_full_forcefield_readiness_json=readiness,
        drd2_parameterization_probe_json=parameterization_probe,
        drd2_protein_repair_json=protein_repair,
        drd2_hard_decoy_envelope_json=hard_decoy_envelope,
        drd2_weakbase_replay_json=drd2_weakbase_replay,
        htr2a_repair_packet_json=htr2a_repair_packet,
        htr2a_topology_probe_json=htr2a_topology_probe,
        htr2a_life_science_evidence_json=htr2a_life_science,
        htr2a_topology_replay_json=htr2a_topology_replay,
        oprm1_life_science_evidence_json=oprm1_life_science,
        oprm1_topology_replay_json=oprm1_topology_replay,
        shadow_claim_review_json=shadow_claim_review,
        pose_gap_json=pose_gap,
        ranking_json=ranking,
        generated_at_local="2026-05-06T00:00:00+09:00",
    )
    summary = payload["summary"]
    rows = payload["rows"]
    top_evidence = rows[0]["current_evidence"]
    hard_decoy_evidence = rows[1]["current_evidence"]
    assert summary["status"] == "open_a1_repair_queue"
    assert summary["top_priority_repair_id"] == "drd2_claim_grade_full_forcefield_local_minimization"
    assert summary["guarded_100k_rerun_allowed_now"] is False
    assert top_evidence["support_status"] == "drd2_atom_typed_backmapping_blocked"
    assert top_evidence["selected_row_count"] == 17
    assert top_evidence["blocked_row_count"] == 17
    assert top_evidence["positive_backmapping_atom_coverage_ratio"] == 0.142857
    assert top_evidence["positive_full_atom_typed_backmapping_ready"] is False
    assert top_evidence["positive_minimum_coverage_gate_pass"] is False
    assert top_evidence["positive_pose_preservation_rmsd_A_p90"] == 0.27
    assert top_evidence["positive_local_minimization_survival_fraction"] is None
    assert top_evidence["positive_local_minimization_survival_hard_decoy_evidence_allowed"] is False
    assert top_evidence["hard_decoy_rebuild_allowed"] is False
    assert top_evidence["full_forcefield_readiness_status"] == "blocked"
    assert top_evidence["full_forcefield_minimization_ready"] is False
    assert top_evidence["protein_parameterization_available"] is False
    assert top_evidence["ligand_parameterization_available"] is False
    assert top_evidence["ligand_template_parameterization_available"] is True
    assert top_evidence["local_parameterization_probe_partial"] is True
    assert top_evidence["claim_grade_parameterization_ready"] is False
    assert top_evidence["protein_missing_heavy_atom_residue_count"] == 70
    assert top_evidence["protein_incomplete_histidine_count"] == 2
    assert top_evidence["protein_claim_grade_repair_allowed"] is False
    assert top_evidence["missing_forcefield_dependencies"] == [
        "openff.toolkit",
        "openmmforcefields",
        "pdbfixer",
    ]
    assert top_evidence["missing_forcefield_assets"] == ["chimerax_tleap"]
    assert top_evidence["claim_promotion_allowed"] is False
    assert top_evidence["scorer_apply_allowed"] is False
    assert top_evidence["guarded_100k_rerun_allowed"] is False
    assert top_evidence["positive_blockers"] == [
        "backmapped_pdb_missing",
        "backmapping_atom_coverage_below_min",
        "cationic_center_anchor_not_atom_typed",
        "full_atom_typed_backmapping_missing",
        "local_minimization_survival_missing",
    ]
    assert (
        top_evidence["next_required_step"]
        == "Generate claim-grade full-forcefield DRD2 local-minimization survival evidence before hard-decoy rebuild or guarded 100k claim review."
    )
    assert "drd2_atom_typed_backmapping_blocked" in rows[0]["next_action"]
    assert "protein_parameterization_available=false" in rows[0]["next_action"]
    assert "ligand_parameterization_available=false" in rows[0]["next_action"]
    assert "ligand_template_parameterization_available=true" in rows[0]["next_action"]
    assert "claim_grade_parameterization_ready=false" in rows[0]["next_action"]
    assert "protein_missing_heavy_atom_residue_count=70" in rows[0]["next_action"]
    assert "real protein-ligand forcefield parameterization path" in rows[0]["next_action"]
    assert hard_decoy_evidence["hard_decoy_rebuild_allowed"] is False
    assert hard_decoy_evidence["positive_full_atom_typed_backmapping_ready"] is False
    assert hard_decoy_evidence["positive_local_minimization_survival_fraction"] is None
    assert rows[-1]["repair_id"] == "guarded_100k_claim_review_rerun"
    assert {row["repair_id"] for row in rows} == {
        "drd2_claim_grade_full_forcefield_local_minimization",
        "drd2_hard_decoy_slice_rebuild",
        "htr2a_anchor_support_repair",
        "oprm1_pose_backmapping_repair",
        "guarded_100k_claim_review_rerun",
    }


def test_build_queue_advances_after_drd2_hard_decoy_slice_is_green(tmp_path: Path) -> None:
    scorecard = tmp_path / "scorecard.json"
    drd2 = tmp_path / "drd2.json"
    support = tmp_path / "support.json"
    readiness = tmp_path / "readiness.json"
    parameterization_probe = tmp_path / "parameterization_probe.json"
    protein_repair = tmp_path / "protein_repair.json"
    hard_decoy_envelope = tmp_path / "hard_decoy_envelope.json"
    drd2_weakbase_replay = tmp_path / "drd2_weakbase_replay.json"
    htr2a_repair_packet = tmp_path / "htr2a_repair_packet.json"
    htr2a_topology_probe = tmp_path / "htr2a_topology_probe.json"
    htr2a_life_science = tmp_path / "htr2a_life_science.json"
    htr2a_topology_replay = tmp_path / "htr2a_topology_replay.json"
    oprm1_life_science = tmp_path / "oprm1_life_science.json"
    oprm1_topology_replay = tmp_path / "oprm1_topology_replay.json"
    shadow_claim_review = tmp_path / "shadow_claim_review.json"
    pose_gap = tmp_path / "pose_gap.json"
    ranking = tmp_path / "ranking.json"

    _write_json(scorecard, {"summary": {"status": "blocked_accuracy_parity"}})
    _write_json(
        drd2,
        {
            "summary": {
                "target": "CHEMBL217_DRD2_HUMAN",
                "positive_ligand_id": "CHEMBL301265",
                "overanchored_decoy_count": 25,
                "atom_window_like_decoy_count": 0,
                "multipolar_basic_decoy_count": 13,
            }
        },
    )
    _write_json(
        htr2a_life_science,
        {
            "summary": {
                "status": "life_science_evidence_supports_claim_locked_htr2a_topology_probe",
                "chembl_min_ki_nM": 0.04,
                "chembl_max_pchembl_value": 10.4,
                "pubchem_cid": 60785,
                "rcsb_entry_id": "6A93",
                "uniprot_reviewed_accession": "P28223",
            }
        },
    )
    _write_json(
        htr2a_topology_probe,
        {
            "summary": {
                "status": "htr2a_atom_typed_topology_probe_separates_current_slice_diagnostic_only",
                "positive_topology_probe_support": 1.0,
                "max_decoy_topology_probe_support": 0.0,
                "decoy_support_positive_or_higher_count": 0,
                "next_required_step": "Replay topology support claim-locked before apply.",
            }
        },
    )
    _write_json(htr2a_topology_replay, {"summary": {}})
    _write_json(
        oprm1_life_science,
        {
            "summary": {
                "status": "life_science_evidence_supports_claim_locked_oprm1_topology_pose_probe",
                "chembl_min_ki_nM": 0.013,
                "pubchem_cid": 10021831,
                "rcsb_entry_id": "8EF6",
                "uniprot_reviewed_accession": "P35372",
            }
        },
    )
    _write_json(oprm1_topology_replay, {"summary": {}})
    _write_json(drd2_weakbase_replay, {"summary": {}})
    _write_json(shadow_claim_review, {"summary": {}})
    _write_json(
        support,
        {
            "summary": {
                "status": "drd2_atom_typed_backmapping_support_ready",
                "positive_backmapping_atom_coverage_ratio": 1.0,
                "positive_full_atom_typed_backmapping_ready": True,
                "positive_minimum_coverage_gate_pass": True,
                "positive_pose_preservation_rmsd_A_p90": 0.1399,
                "positive_local_minimization_survival_fraction": 1.0,
                "positive_local_minimization_survival_claim_scope": "full_protein_ligand_forcefield",
                "positive_local_minimization_survival_hard_decoy_evidence_allowed": True,
                "positive_blockers": [],
                "hard_decoy_rebuild_allowed": True,
                "claim_promotion_allowed": False,
                "scorer_apply_allowed": False,
                "guarded_100k_rerun_allowed": False,
            }
        },
    )
    _write_json(
        readiness,
        {
            "summary": {
                "status": "ready",
                "full_forcefield_minimization_ready": True,
                "protein_parameterization_available": True,
                "ligand_parameterization_available": True,
            }
        },
    )
    _write_json(
        parameterization_probe,
        {
            "summary": {
                "claim_grade_parameterization_ready": True,
                "local_probe_partial": False,
                "ligand_template_parameterization_available": True,
            }
        },
    )
    _write_json(
        protein_repair,
        {
            "summary": {
                "missing_heavy_atom_residue_count": 0,
                "incomplete_histidine_count": 0,
                "claim_grade_repair_allowed": True,
            }
        },
    )
    _write_json(
        hard_decoy_envelope,
        {
            "summary": {
                "status": "slice_pairwise_green_diagnostic_only",
                "bounded_best_positive_rank": 1,
                "bounded_best_decoys_above_positive_count": 0,
                "bounded_best_valid_anchor_challenge_above_positive_count": 0,
                "bounded_best_penalty_weight": 6.0,
                "bounded_best_support_weight": 16.0,
                "next_required_step": "Promote only the feature contract, not the claim.",
            }
        },
    )
    _write_json(
        htr2a_repair_packet,
        {
            "summary": {
                "status": "blocked_htr2a_anchor_signature_nonidentifiable",
                "positive_target_rank": 6,
                "base_score_locked_decoys_above_positive_count": 5,
                "generic_anchor_signature_decoys_above_positive_count": 4,
                "pose_advantaged_decoys_above_positive_count": 5,
                "next_required_step": "Build a target-portable atom-typed HTR2A anchor probe before any guarded rerun.",
            }
        },
    )
    _write_json(
        pose_gap,
        {
            "target_summaries": [
                {
                    "target": "CHEMBL224_HTR2A_HUMAN",
                    "ligand_id": "CHEMBL83894",
                    "global_rank": 22,
                    "target_rank": 6,
                    "decoys_above_positive": 5,
                    "label_free_support_pressure": 0.0,
                    "pose_preservation_support": 0.39,
                    "coarse_centroid_preservation_rmsd_A_mean": 2.2,
                    "blockers": ["positive_anchor_support_missing"],
                },
                {
                    "target": "CHEMBL233_OPRM1_HUMAN",
                    "ligand_id": "CHEMBL331883",
                    "global_rank": 399,
                    "target_rank": 158,
                    "decoys_above_positive": 157,
                    "label_free_support_pressure": 0.0,
                    "pose_preservation_support": 0.0,
                    "coarse_centroid_preservation_rmsd_A_mean": 34.16,
                    "blockers": ["positive_anchor_support_missing"],
                },
            ]
        },
    )
    _write_json(
        ranking,
        {
            "summary": {
                "ranking_pr_auc": 0.5187,
                "ranking_pr_auc_ci_low": 0.1486,
                "ranking_topk_hit_rate": 0.25,
            }
        },
    )

    payload = mod.build_queue(
        accuracy_scorecard_json=scorecard,
        drd2_repair_json=drd2,
        drd2_backmapping_support_json=support,
        drd2_full_forcefield_readiness_json=readiness,
        drd2_parameterization_probe_json=parameterization_probe,
        drd2_protein_repair_json=protein_repair,
        drd2_hard_decoy_envelope_json=hard_decoy_envelope,
        drd2_weakbase_replay_json=drd2_weakbase_replay,
        htr2a_repair_packet_json=htr2a_repair_packet,
        htr2a_topology_probe_json=htr2a_topology_probe,
        htr2a_life_science_evidence_json=htr2a_life_science,
        htr2a_topology_replay_json=htr2a_topology_replay,
        oprm1_life_science_evidence_json=oprm1_life_science,
        oprm1_topology_replay_json=oprm1_topology_replay,
        shadow_claim_review_json=shadow_claim_review,
        pose_gap_json=pose_gap,
        ranking_json=ranking,
        generated_at_local="2026-05-09T00:00:00+09:00",
    )

    summary = payload["summary"]
    rows = {row["repair_id"]: row for row in payload["rows"]}
    hard_decoy_evidence = rows["drd2_hard_decoy_slice_rebuild"]["current_evidence"]
    htr2a_evidence = rows["htr2a_anchor_support_repair"]["current_evidence"]
    assert rows["drd2_claim_grade_full_forcefield_local_minimization"]["status"] == "completed"
    assert rows["drd2_hard_decoy_slice_rebuild"]["status"] == "completed"
    assert summary["top_priority_repair_id"] == "htr2a_anchor_support_repair"
    assert summary["top_priority_blocker_group"] == "target_portable_anchor_support"
    assert hard_decoy_evidence["hard_decoy_envelope_status"] == "slice_pairwise_green_diagnostic_only"
    assert hard_decoy_evidence["hard_decoy_bounded_best_positive_rank"] == 1
    assert hard_decoy_evidence["hard_decoy_bounded_best_decoys_above_positive_count"] == 0
    assert "target-portable HTR2A/OPRM1" in rows["drd2_hard_decoy_slice_rebuild"]["next_action"]
    assert htr2a_evidence["htr2a_repair_packet_status"] == "blocked_htr2a_anchor_signature_nonidentifiable"
    assert htr2a_evidence["htr2a_base_score_locked_decoys_above_positive_count"] == 5
    assert htr2a_evidence["htr2a_generic_anchor_signature_decoys_above_positive_count"] == 4
    assert htr2a_evidence["htr2a_topology_probe_status"] == (
        "htr2a_atom_typed_topology_probe_separates_current_slice_diagnostic_only"
    )
    assert htr2a_evidence["htr2a_topology_probe_positive_support"] == 1.0
    assert htr2a_evidence["htr2a_topology_probe_max_decoy_support"] == 0.0
    assert htr2a_evidence["htr2a_life_science_evidence_status"] == (
        "life_science_evidence_supports_claim_locked_htr2a_topology_probe"
    )
    assert htr2a_evidence["htr2a_life_science_chembl_min_ki_nM"] == 0.04
    assert htr2a_evidence["htr2a_life_science_rcsb_entry_id"] == "6A93"
    assert htr2a_evidence["htr2a_topology_replay_status"] is None
    assert "claim-locked frozen shadow replay" in rows["htr2a_anchor_support_repair"]["next_action"]

    _write_json(
        htr2a_topology_replay,
        {
            "summary": {
                "status": "htr2a_topology_support_shadow_replay_selected_slice_green_claim_locked",
                "claim_promotion_allowed": False,
                "scorer_apply_allowed": False,
                "guarded_100k_rerun_allowed": False,
                "topology_support_row_count": 1,
                "selected_support_weight": 0.5,
                "selected_htr2a_target_rank": 1,
                "selected_htr2a_decoys_above_positive": 0,
                "selected_non_htr2a_regression_count": 0,
            }
        },
    )
    replay_payload = mod.build_queue(
        accuracy_scorecard_json=scorecard,
        drd2_repair_json=drd2,
        drd2_backmapping_support_json=support,
        drd2_full_forcefield_readiness_json=readiness,
        drd2_parameterization_probe_json=parameterization_probe,
        drd2_protein_repair_json=protein_repair,
        drd2_hard_decoy_envelope_json=hard_decoy_envelope,
        drd2_weakbase_replay_json=drd2_weakbase_replay,
        htr2a_repair_packet_json=htr2a_repair_packet,
        htr2a_topology_probe_json=htr2a_topology_probe,
        htr2a_life_science_evidence_json=htr2a_life_science,
        htr2a_topology_replay_json=htr2a_topology_replay,
        oprm1_life_science_evidence_json=oprm1_life_science,
        oprm1_topology_replay_json=oprm1_topology_replay,
        shadow_claim_review_json=shadow_claim_review,
        pose_gap_json=pose_gap,
        ranking_json=ranking,
        generated_at_local="2026-05-09T00:30:00+09:00",
    )
    replay_rows = {row["repair_id"]: row for row in replay_payload["rows"]}
    replay_htr2a = replay_rows["htr2a_anchor_support_repair"]
    replay_evidence = replay_htr2a["current_evidence"]
    assert replay_htr2a["status"] == "completed"
    assert replay_payload["summary"]["top_priority_repair_id"] == "oprm1_pose_backmapping_repair"
    assert replay_evidence["htr2a_topology_replay_selected_support_weight"] == 0.5
    assert replay_evidence["htr2a_topology_replay_selected_htr2a_target_rank"] == 1
    assert replay_evidence["htr2a_topology_replay_selected_htr2a_decoys_above_positive"] == 0
    assert replay_evidence["htr2a_topology_replay_selected_non_htr2a_regression_count"] == 0
    assert "move active focus to OPRM1" in replay_htr2a["next_action"]

    _write_json(
        oprm1_topology_replay,
        {
            "summary": {
                "status": "oprm1_topology_pose_shadow_replay_selected_slice_green_claim_locked",
                "claim_promotion_allowed": False,
                "scorer_apply_allowed": False,
                "guarded_100k_rerun_allowed": False,
                "topology_pose_support_row_count": 1,
                "selected_support_weight": 1.5,
                "selected_oprm1_target_rank": 1,
                "selected_oprm1_decoys_above_positive": 0,
                "selected_non_oprm1_regression_count": 0,
                "selected_top20_positive_count": 3,
            }
        },
    )
    _write_json(
        shadow_claim_review,
        {
            "summary": {
                "status": "blocked_guarded_shadow_claim_review",
                "guarded_shadow_claim_review_passed": False,
                "input_rows": 30000,
                "ranking_pr_auc": 0.5888888888888889,
                "ranking_pr_auc_ci_low": 0.2604166666666667,
                "top20_positive_count": 3,
                "top20_positive_recall": 1.0,
                "top20_slot_hit_rate": 0.15,
                "all_positive_target_rank_1": False,
                "blockers": [
                    "ranking_pr_auc_ci_low_below_threshold",
                    "target_internal_positive_rank_not_1",
                ],
            }
        },
    )
    oprm1_payload = mod.build_queue(
        accuracy_scorecard_json=scorecard,
        drd2_repair_json=drd2,
        drd2_backmapping_support_json=support,
        drd2_full_forcefield_readiness_json=readiness,
        drd2_parameterization_probe_json=parameterization_probe,
        drd2_protein_repair_json=protein_repair,
        drd2_hard_decoy_envelope_json=hard_decoy_envelope,
        drd2_weakbase_replay_json=drd2_weakbase_replay,
        htr2a_repair_packet_json=htr2a_repair_packet,
        htr2a_topology_probe_json=htr2a_topology_probe,
        htr2a_life_science_evidence_json=htr2a_life_science,
        htr2a_topology_replay_json=htr2a_topology_replay,
        oprm1_life_science_evidence_json=oprm1_life_science,
        oprm1_topology_replay_json=oprm1_topology_replay,
        shadow_claim_review_json=shadow_claim_review,
        pose_gap_json=pose_gap,
        ranking_json=ranking,
        generated_at_local="2026-05-09T01:00:00+09:00",
    )
    oprm1_rows = {row["repair_id"]: row for row in oprm1_payload["rows"]}
    oprm1_evidence = oprm1_rows["oprm1_pose_backmapping_repair"]["current_evidence"]
    claim_review_evidence = oprm1_rows["guarded_100k_claim_review_rerun"]["current_evidence"]
    assert oprm1_rows["oprm1_pose_backmapping_repair"]["status"] == "completed"
    assert oprm1_payload["summary"]["top_priority_repair_id"] == "guarded_100k_claim_review_rerun"
    assert oprm1_payload["summary"]["guarded_shadow_claim_review_status"] == "blocked_guarded_shadow_claim_review"
    assert oprm1_evidence["oprm1_topology_replay_selected_support_weight"] == 1.5
    assert oprm1_evidence["oprm1_topology_replay_selected_top20_positive_count"] == 3
    assert claim_review_evidence["shadow_ranking_pr_auc"] == 0.5888888888888889
    assert claim_review_evidence["shadow_ranking_pr_auc_ci_low"] == 0.2604166666666667
    assert claim_review_evidence["shadow_all_positive_target_rank_1"] is False
    assert claim_review_evidence["shadow_review_blockers"] == [
        "ranking_pr_auc_ci_low_below_threshold",
        "target_internal_positive_rank_not_1",
    ]
    assert "prepare guarded 100k claim review" in oprm1_rows["oprm1_pose_backmapping_repair"]["next_action"]
    assert "DRD2 decoy intrusion" in oprm1_rows["guarded_100k_claim_review_rerun"]["next_action"]


def test_cli_writes_queue_artifacts(tmp_path: Path) -> None:
    scorecard = tmp_path / "scorecard.json"
    drd2 = tmp_path / "drd2.json"
    support = tmp_path / "support.json"
    readiness = tmp_path / "readiness.json"
    parameterization_probe = tmp_path / "parameterization_probe.json"
    protein_repair = tmp_path / "protein_repair.json"
    hard_decoy_envelope = tmp_path / "hard_decoy_envelope.json"
    drd2_weakbase_replay = tmp_path / "drd2_weakbase_replay.json"
    htr2a_repair_packet = tmp_path / "htr2a_repair_packet.json"
    htr2a_topology_probe = tmp_path / "htr2a_topology_probe.json"
    htr2a_life_science = tmp_path / "htr2a_life_science.json"
    htr2a_topology_replay = tmp_path / "htr2a_topology_replay.json"
    oprm1_life_science = tmp_path / "oprm1_life_science.json"
    oprm1_topology_replay = tmp_path / "oprm1_topology_replay.json"
    shadow_claim_review = tmp_path / "shadow_claim_review.json"
    pose_gap = tmp_path / "pose_gap.json"
    ranking = tmp_path / "ranking.json"
    out_json = tmp_path / "queue.json"
    out_md = tmp_path / "queue.md"
    _write_json(scorecard, {"summary": {"status": "blocked_accuracy_parity"}})
    _write_json(drd2, {"summary": {}})
    _write_json(support, {"summary": {}})
    _write_json(readiness, {"summary": {}})
    _write_json(parameterization_probe, {"summary": {}})
    _write_json(protein_repair, {"summary": {}})
    _write_json(hard_decoy_envelope, {"summary": {}})
    _write_json(drd2_weakbase_replay, {"summary": {}})
    _write_json(htr2a_repair_packet, {"summary": {}})
    _write_json(htr2a_topology_probe, {"summary": {}})
    _write_json(htr2a_life_science, {"summary": {}})
    _write_json(htr2a_topology_replay, {"summary": {}})
    _write_json(oprm1_life_science, {"summary": {}})
    _write_json(oprm1_topology_replay, {"summary": {}})
    _write_json(shadow_claim_review, {"summary": {}})
    _write_json(pose_gap, {"target_summaries": []})
    _write_json(ranking, {"summary": {}})

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_a1_accuracy_repair_queue.py"),
            "--accuracy-scorecard-json",
            str(scorecard),
            "--drd2-repair-json",
            str(drd2),
            "--drd2-backmapping-support-json",
            str(support),
            "--drd2-full-forcefield-readiness-json",
            str(readiness),
            "--drd2-parameterization-probe-json",
            str(parameterization_probe),
            "--drd2-protein-repair-json",
            str(protein_repair),
            "--drd2-hard-decoy-envelope-json",
            str(hard_decoy_envelope),
            "--drd2-weakbase-replay-json",
            str(drd2_weakbase_replay),
            "--htr2a-repair-packet-json",
            str(htr2a_repair_packet),
            "--htr2a-topology-probe-json",
            str(htr2a_topology_probe),
            "--htr2a-life-science-evidence-json",
            str(htr2a_life_science),
            "--htr2a-topology-replay-json",
            str(htr2a_topology_replay),
            "--oprm1-life-science-evidence-json",
            str(oprm1_life_science),
            "--oprm1-topology-replay-json",
            str(oprm1_topology_replay),
            "--shadow-claim-review-json",
            str(shadow_claim_review),
            "--pose-gap-json",
            str(pose_gap),
            "--ranking-json",
            str(ranking),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        cwd=ROOT,
        check=True,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    rendered_md = out_md.read_text(encoding="utf-8")
    assert payload["packet_type"] == "gpcr_a1_accuracy_repair_queue"
    assert "GPCR A1 Accuracy Repair Queue" in rendered_md
    assert "full_forcefield_minimization_ready flips true" in rendered_md
    assert "real protein-ligand forcefield parameterization path" in rendered_md
