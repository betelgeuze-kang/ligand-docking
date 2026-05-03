#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_OUT_JSON = "runs/gpcr_residual_prototype_spec_current.json"
DEFAULT_OUT_CSV = "runs/gpcr_residual_prototype_spec_current.csv"
DEFAULT_OUT_MD = "runs/gpcr_residual_prototype_spec_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _feature_rows(variant: str) -> list[dict[str, Any]]:
    rows = [
        {
            "feature_name": "ligand_h_donors",
            "role": "prior_penalty",
            "direction": "penalize_when_high_without_support",
            "rationale": "High donor counts are over-rewarded in v7 relative to geometry/contact evidence.",
        },
        {
            "feature_name": "ligand_h_acceptors",
            "role": "prior_penalty",
            "direction": "penalize_when_high_without_support",
            "rationale": "Acceptor-rich hard decoys rise too high under the current GPCR composite.",
        },
        {
            "feature_name": "ligand_rot_bonds",
            "role": "prior_penalty",
            "direction": "penalize_when_high_without_support",
            "rationale": "Flexible decoys benefit from current prior weights and need structural support checks.",
        },
        {
            "feature_name": "ligand_logp",
            "role": "calibration_penalty",
            "direction": "penalize_low_logp_when_geometry_is_weak",
            "rationale": "Low-logP priors are currently rewarded through run-level scaling and shift under larger libraries.",
        },
        {
            "feature_name": "ligand_affinity_hint",
            "role": "prior_penalty",
            "direction": "penalize_when_hint_disagrees_with_md",
            "rationale": "Affinity hints need a mismatch penalty when contact/distance evidence is weak.",
        },
        {
            "feature_name": "binding_energy_proxy",
            "role": "support_signal",
            "direction": "reward_only_when_consistent",
            "rationale": "Energy should support positive correction but not dominate when other structural signals are weak.",
        },
        {
            "feature_name": "contact_fraction",
            "role": "support_signal",
            "direction": "reward_when_high",
            "rationale": "Low-contact decoys are slipping through; contact should anchor positive correction.",
        },
        {
            "feature_name": "stability_score",
            "role": "support_signal",
            "direction": "reward_when_high",
            "rationale": "The residual should trust stable trajectories more than prior-favorable but unstable ones.",
        },
        {
            "feature_name": "mean_min_distance_A",
            "role": "guardrail_signal",
            "direction": "penalize_when_far",
            "rationale": "Current GPCR v7 gives distance zero weight, which allows far-but-prior-like decoys through.",
        },
        {
            "feature_name": "prior_structure_mismatch",
            "role": "interaction_term",
            "direction": "penalize_when_high",
            "rationale": "Explicitly capture donor/acceptor/rotor richness without matching contact and distance support.",
        },
    ]
    if variant == "narrow_v2":
        for row in rows:
            if row["feature_name"] in {
                "ligand_h_donors",
                "ligand_h_acceptors",
                "ligand_rot_bonds",
                "ligand_logp",
                "ligand_affinity_hint",
            }:
                row["rationale"] += " Narrow-v2 only activates these behind explicit distance/contact mismatch gates."
    if variant == "gpcr_core_decoy_intrusion_v1":
        rows.extend(
            [
                {
                    "feature_name": "low_donor_acceptor_rotor_pressure",
                    "role": "intrusion_prior",
                    "direction": "penalize_when_low_with_high_logp_and_contact_support",
                    "rationale": "Core 100k false positives include compact hydrophobic decoys that v7 ranks above smaller beta-blocker anchors.",
                },
                {
                    "feature_name": "intrusion_contact_support",
                    "role": "intrusion_gate",
                    "direction": "activate_only_when_contact_support_is_high",
                    "rationale": "The candidate should target top-rank decoy intrusion without broadly penalizing weak/noisy rows.",
                },
            ]
        )
    if variant == "gpcr_core_linear_rescore_v1":
        rows.extend(
            [
                {
                    "feature_name": "z_ligand_affinity_hint",
                    "role": "linear_rescore_anchor",
                    "direction": "reward_when_high",
                    "rationale": "Replay search found affinity hint support helps recover core PR-AUC while preserving ChEMBL50 top-k.",
                },
                {
                    "feature_name": "z_ligand_logp",
                    "role": "linear_rescore_anchor",
                    "direction": "reward_when_high",
                    "rationale": "Core top-rank decoy intrusion is enriched for lower-logP rows than the protected beta-blocker anchors.",
                },
                {
                    "feature_name": "z_ligand_rot_bonds",
                    "role": "linear_rescore_anchor",
                    "direction": "reward_when_high",
                    "rationale": "Flexible beta-blocker-like anchors need protection from compact hard-decoy intrusion in 100k scale-up.",
                },
            ]
        )
    if variant == "gpcr_core_mismatch_contact_rescore_v1":
        rows.extend(
            [
                {
                    "feature_name": "donor_prior_decoy_intrusion",
                    "role": "failure_tag_gate",
                    "direction": "penalize_when_donor_prior_is_high_without_contact_support",
                    "rationale": "Current 100k failure tags show donor-rich decoys outranking core binders despite weak support.",
                },
                {
                    "feature_name": "weak_contact_prior_mismatch",
                    "role": "contact_mismatch_gate",
                    "direction": "activate_only_when_contact_is_weak_relative_to_prior_pressure",
                    "rationale": "The candidate should focus on prior-favorable rows whose contact evidence does not support the rank.",
                },
                {
                    "feature_name": "affinity_hint_md_support_mismatch",
                    "role": "affinity_md_guard",
                    "direction": "penalize_when_affinity_hint_disagrees_with_md_support",
                    "rationale": "Affinity hints must not rescue rows when contact and MD support are weak.",
                },
                {
                    "feature_name": "no_existing_score_column_recovers_gate",
                    "role": "comparison_only_guard",
                    "direction": "require_guarded_candidate_review",
                    "rationale": "Failure analysis found no existing score column recovers the 100k gate, so this remains evidence-only.",
                },
            ]
        )
    if variant == "gpcr_core_structure_support_rescore_v1":
        rows.extend(
            [
                {
                    "feature_name": "z_ligand_logp",
                    "role": "structure_support_rescore_anchor",
                    "direction": "reward_higher_lipophilicity_when_structure_support_is_consistent",
                    "rationale": "Replay on the measured 100k failure slice recovered top20 retention only when beta-blocker-like lipophilicity was protected.",
                },
                {
                    "feature_name": "z_ligand_rot_bonds",
                    "role": "structure_support_rescore_anchor",
                    "direction": "reward_flexible_anchor_like_rows",
                    "rationale": "Flexible ADRB2 anchors were displaced by compact hard decoys in the failed core 100k lanes.",
                },
                {
                    "feature_name": "z_contact_fraction",
                    "role": "structure_support_signal",
                    "direction": "reward_contact_support",
                    "rationale": "Contact support is retained as a required replay signal before any guarded apply rerun.",
                },
                {
                    "feature_name": "z_mean_min_distance_A",
                    "role": "structure_support_guard",
                    "direction": "penalize_far_distance",
                    "rationale": "Far-distance rows need a mild penalty so residual rescue does not become prior-only.",
                },
                {
                    "feature_name": "z_stability_score",
                    "role": "stability_over_support_guard",
                    "direction": "penalize_over-supported_decoys_in_replay",
                    "rationale": "The failed 100k slice shows some decoys with apparent stability support but poor top20 label behavior; this remains replay-only until a fresh full run passes.",
                },
            ]
        )
    if variant == "gpcr_core_family_balanced_rescore_v1":
        rows.extend(
            [
                {
                    "feature_name": "family_balanced_pose_energy_support",
                    "role": "family_balanced_rescore_anchor",
                    "direction": "reward_pose_energy_support_without_target_identity",
                    "rationale": "The frozen non-ADRB2 100k rerun shows coverage/family gates are green, but non-ADRB2 positives remain tail-ranked; the next scorer must use shared pose/energy support rather than target labels.",
                },
                {
                    "feature_name": "non_adrb2_tail_rank_blocker",
                    "role": "failure_tag_gate",
                    "direction": "diagnostic_only",
                    "rationale": "Rank diagnostics show HTR2A, OPRM1, and DRD2 positives still sit outside the claim-review top-k region.",
                },
                {
                    "feature_name": "donor_rich_decoy_intrusion",
                    "role": "intrusion_guard",
                    "direction": "penalize_high_donor_without_pose_support",
                    "rationale": "Donor-rich hard decoys can outrank true non-ADRB2 positives when prior-rich chemistry is not backed by contact, distance, and energy support.",
                },
                {
                    "feature_name": "claim_locked_family_balanced_replay",
                    "role": "claim_boundary",
                    "direction": "comparison_only",
                    "rationale": "This candidate opens only shadow/replay/guarded-apply evidence and cannot authorize router, platform, or delivery-claim promotion.",
                },
            ]
        )
    if variant in {
        "gpcr_core_family_anchor_rescore_v2",
        "gpcr_core_family_anchor_ci_stability_v3",
        "gpcr_core_acidic_anchor_overcontact_prior_gate_v4",
    }:
        rows.extend(
            [
                {
                    "feature_name": "gpcr_smiles_present_proxy",
                    "role": "chemistry_availability_gate",
                    "direction": "gate_chemistry_penalties_when_ligand_smiles_is_present",
                    "rationale": (
                        "Anchor-chemistry mismatch pressure must not treat missing SMILES as evidence that a row lacks "
                        "basic-amine chemistry. This target-agnostic availability gate prevents false penalty on "
                        "chemistry-missing rows."
                    ),
                },
                {
                    "feature_name": "gpcr_conserved_anchor_proxy",
                    "role": "conserved_anchor_proxy",
                    "direction": "reward_shared_anchor_like_pose_physics_without_target_identity",
                    "rationale": (
                        "Proxy for aminergic GPCR conserved-anchor behavior such as Asp3.32 salt-bridge support, "
                        "aromatic-cage compatibility, and orthosteric occupancy. Current implementation is stage3 "
                        "pose/physics proxy only and must not encode target identity."
                    ),
                },
                {
                    "feature_name": "gpcr_basic_amine_proxy",
                    "role": "conserved_anchor_chemistry_proxy",
                    "direction": "reward_basic_amine_chemistry_for_shared_aminergic_gpcr_anchor",
                    "rationale": (
                        "DRD2 diagnostics show the positive contacts the acidic anchor, but hard decoys can over-anchor "
                        "without basic amine chemistry. This target-agnostic chemistry proxy separates shared aminergic "
                        "GPCR anchor compatibility from hydrophobic contact overreward."
                    ),
                },
                {
                    "feature_name": "pose_physics_support",
                    "role": "pose_physics_support",
                    "direction": "reward_when_energy_contact_stability_and_distance_agree",
                    "rationale": "DRD2 rescue should come from shared pose/physics support rather than ligand-prior overreward.",
                },
                {
                    "feature_name": "prior_overreward_without_anchor",
                    "role": "prior_gate",
                    "direction": "penalize_prior_reward_when_anchor_proxy_is_absent",
                    "rationale": "Affinity, MW, logP, rotor, and polar priors should only help when the row has pose-anchor support.",
                },
                {
                    "feature_name": "target_internal_pairwise_pressure",
                    "role": "pairwise_hard_decoy_proxy",
                    "direction": "diagnostic_only",
                    "rationale": (
                        "Replay diagnostic for the next pairwise hard-decoy loss. Live scoring must not use target "
                        "labels or binder labels, so this remains diagnostic-only before claim review."
                    ),
                },
                {
                    "feature_name": "gpcr_pose_chemistry_hard_decoy_pressure",
                    "role": "target_agnostic_hard_decoy_pressure",
                    "direction": "penalize_prior_or_over_anchor_rows_without_basic_amine_support",
                    "rationale": (
                        "Active shadow/replay pressure uses only ligand chemistry plus pose/physics proxies to suppress "
                        "hydrophobic low-polar basic-amine or over-anchor decoy-like rows without target identity, labels, "
                        "or threshold relaxation."
                    ),
                },
                {
                    "feature_name": "gpcr_anchor_chemistry_mismatch_pressure",
                    "role": "target_agnostic_anchor_chemistry_pressure",
                    "direction": "penalize_anchor_like_pose_support_without_basic_amine_chemistry",
                    "rationale": (
                        "DRD2 hard rows need extra pressure when pose/physics support looks anchor-like but the "
                        "shared aminergic basic-amine chemistry proxy is absent. This uses only ligand chemistry and "
                        "pose/physics support proxies."
                    ),
                },
                {
                    "feature_name": "target_internal_pairwise_replay_diagnostic",
                    "role": "pairwise_replay_diagnostic",
                    "direction": "diagnostic_only",
                    "rationale": (
                        "Reserved output column for target-internal hard-decoy replay analysis. It is not a linear "
                        "scorer term because true pairwise replay may require target/label context unavailable in live scoring."
                    ),
                },
                {
                    "feature_name": "drd2_pose_physics_rescue_slice",
                    "role": "failure_slice",
                    "direction": "diagnostic_only",
                    "rationale": "Latest r2 evidence shows DRD2 positive tail-rank is the remaining PR-AUC/CI-low blocker.",
                },
                {
                    "feature_name": "claim_locked_family_anchor_replay",
                    "role": "claim_boundary",
                    "direction": "comparison_only",
                    "rationale": "This v2 lane opens only diagnostics, shadow/replay, and guarded-apply evidence; no delivery/router/platform promotion.",
                },
            ]
        )
    if variant == "gpcr_core_family_anchor_ci_stability_v3":
        rows.extend(
            [
                {
                    "feature_name": "acidic_anchor_overcontact_pressure_probe",
                    "role": "acidic_anchor_geometry_diagnostic",
                    "direction": "diagnostic_only",
                    "rationale": (
                        "DRD2 rank-failure diagnostics suggest many top hard decoys may be over-contacting conserved "
                        "acidic anchor geometry. This remains a replay-only geometry probe until it is shown to improve "
                        "CI-low without target identity, labels, ranks, ligand IDs, or reference-value leakage."
                    ),
                },
                {
                    "feature_name": "bootstrap_ci_low_stability_probe",
                    "role": "ci_low_stability_diagnostic",
                    "direction": "diagnostic_only",
                    "rationale": (
                        "The v2 shadow point PR-AUC improved, but bootstrap PR-AUC CI-low remains below the 0.45 "
                        "gate. This v3 lane records the stability gap explicitly before any scorer or claim promotion."
                    ),
                },
                {
                    "feature_name": "family_anchor_v2_score_preservation",
                    "role": "evidence_preservation",
                    "direction": "comparison_only",
                    "rationale": (
                        "Preserve v2 as the scored replay baseline and add only CI-low diagnostics until bootstrap "
                        "support explains the unstable lower tail."
                    ),
                },
            ]
        )
    if variant == "gpcr_core_acidic_anchor_overcontact_prior_gate_v4":
        rows.extend(
            [
                {
                    "feature_name": "gpcr_acidic_anchor_overcontact_prior_gate",
                    "role": "target_agnostic_overcontact_prior_gate",
                    "direction": "penalize_anchor_overcontact_only_when_ligand_prior_is_overrewarded",
                    "rationale": (
                        "Post-v3 diagnostics point to acidic-anchor overcontact as a candidate blocker, but live "
                        "scoring must only use shared pose/physics and ligand chemistry proxies. This gate activates "
                        "only when anchor-like contact is high, basic-amine support is absent, and ligand prior pressure "
                        "is overrewarded."
                    ),
                },
                {
                    "feature_name": "gpcr_acidic_anchor_overcontact_prior_gate_shadow_score",
                    "role": "claim_locked_shadow_score",
                    "direction": "diagnostic_only",
                    "rationale": (
                        "Candidate score is emitted for shadow comparison only; it cannot authorize active claims, "
                        "router promotion, threshold relaxation, or broad GPCR delivery assertions."
                    ),
                },
            ]
        )
    if variant == "gpcr_adrb2_beta_blocker_pharmacophore_v1":
        rows.extend(
            [
                {
                    "feature_name": "aryloxypropanolamine_smarts_match",
                    "role": "target_specific_pharmacophore_reward",
                    "direction": "reward_when_present",
                    "rationale": (
                        "ADRB2 core 100k blockers are beta-blocker-like aryloxypropanolamines; this target-specific "
                        "shadow prior must not be promoted as a general GPCR family claim."
                    ),
                },
                {
                    "feature_name": "ligand_smiles",
                    "role": "pharmacophore_input",
                    "direction": "smarts_match_only",
                    "rationale": "The candidate uses only local ligand SMILES and a declared SMARTS pattern.",
                },
            ]
        )
    return rows


def build_payload(*, variant: str = "current") -> dict[str, Any]:
    feature_rows = _feature_rows(variant)
    constraints = {
        "max_abs_delta_score": 1.5,
        "yellow_band_abs_delta_score": 0.75,
        "preserve_top2_binders": True,
        "require_energy_contact_support_for_positive_delta": True,
        "fallback_on_ood": True,
        "fallback_on_low_confidence": True,
        "reference_scaling_mode": "fixed_family_reference",
    }
    tuning: dict[str, Any] = {"variant": "current"}
    interactions = [
        "high_donor_acceptor_rotor_with_weak_contact",
        "high_donor_acceptor_rotor_with_far_distance",
        "low_logp_with_weak_energy",
        "high_affinity_hint_with_weak_md_evidence",
    ]
    next_step = (
        "Run equal-size GPCR A/B with shadow residual telemetry, then use the comparison artifacts "
        "to decide whether an apply-mode experiment is safe for the 100k commercialization path."
    )

    if variant == "narrow_v2":
        constraints = {
            **constraints,
            "max_abs_delta_score": 0.75,
            "yellow_band_abs_delta_score": 0.35,
        }
        tuning = {
            "variant": "narrow_v2",
            "prior_weight_h_donors": 0.22,
            "prior_weight_h_acceptors": 0.20,
            "prior_weight_rot_bonds": 0.10,
            "prior_weight_neg_logp": 0.06,
            "weakness_weight_distance": 0.80,
            "weakness_weight_neg_contact": 0.70,
            "weakness_weight_neg_stability": 0.25,
            "weakness_weight_energy": 0.15,
            "support_weight_neg_energy": 0.20,
            "support_weight_contact": 0.35,
            "support_weight_stability": 0.10,
            "support_weight_neg_distance": 0.35,
            "interaction_bias": 0.20,
            "affinity_mismatch_weight": 0.12,
            "affinity_interaction_bias": 0.15,
            "support_penalty_weight": 0.08,
            "min_prior_pressure_for_delta": 0.85,
            "min_structural_weakness_for_delta": 0.90,
            "max_structural_support_for_delta": 0.20,
            "min_raw_delta_for_activation": 0.25,
            "require_distance_above_z": 0.35,
            "require_contact_below_z": -0.20,
        }
        interactions = [
            "prior_pressure_only_when_distance_is_far",
            "prior_pressure_only_when_contact_is_weak",
            "affinity_hint_only_when_md_is_weak_and_support_is_low",
        ]
        next_step = (
            "Run a locked-decoy GPCR shadow A/B with narrow-v2 gating, verify PR-AUC no longer regresses, "
            "then run locked-decoy apply only if the shadow telemetry remains claim-safe."
        )
    elif variant == "chembl50_v3":
        constraints = {
            **constraints,
            "max_abs_delta_score": 0.50,
            "yellow_band_abs_delta_score": 0.20,
        }
        tuning = {
            "variant": "chembl50_v3",
            "prior_weight_h_donors": 0.18,
            "prior_weight_h_acceptors": 0.16,
            "prior_weight_rot_bonds": 0.08,
            "prior_weight_neg_logp": 0.04,
            "weakness_weight_distance": 0.85,
            "weakness_weight_neg_contact": 0.78,
            "weakness_weight_neg_stability": 0.18,
            "weakness_weight_energy": 0.10,
            "support_weight_neg_energy": 0.15,
            "support_weight_contact": 0.30,
            "support_weight_stability": 0.08,
            "support_weight_neg_distance": 0.40,
            "interaction_bias": 0.12,
            "affinity_mismatch_weight": 0.08,
            "affinity_interaction_bias": 0.10,
            "support_penalty_weight": 0.05,
            "min_prior_pressure_for_delta": 0.92,
            "min_structural_weakness_for_delta": 0.95,
            "max_structural_support_for_delta": 0.12,
            "min_raw_delta_for_activation": 0.30,
            "require_distance_above_z": 0.45,
            "require_contact_below_z": -0.30,
            "chembl50_abstain_on_borderline_support": True,
        }
        interactions = [
            "chembl50_prior_pressure_only_when_distance_is_far",
            "chembl50_prior_pressure_only_when_contact_is_weak",
            "chembl50_abstain_when_support_is_borderline",
        ]
        next_step = (
            "Use this chembl50-focused v3 as the next locked-decoy shadow candidate. It should only fire on stronger "
            "distance/contact mismatch and abstain on borderline support before any apply-mode retry."
        )
    elif variant == "chembl50_v4":
        constraints = {
            **constraints,
            "max_abs_delta_score": 0.35,
            "yellow_band_abs_delta_score": 0.12,
        }
        tuning = {
            "variant": "chembl50_v4",
            "prior_weight_h_donors": 0.14,
            "prior_weight_h_acceptors": 0.12,
            "prior_weight_rot_bonds": 0.06,
            "prior_weight_neg_logp": 0.03,
            "weakness_weight_distance": 0.90,
            "weakness_weight_neg_contact": 0.84,
            "weakness_weight_neg_stability": 0.14,
            "weakness_weight_energy": 0.08,
            "support_weight_neg_energy": 0.12,
            "support_weight_contact": 0.26,
            "support_weight_stability": 0.06,
            "support_weight_neg_distance": 0.42,
            "interaction_bias": 0.08,
            "affinity_mismatch_weight": 0.06,
            "affinity_interaction_bias": 0.08,
            "support_penalty_weight": 0.03,
            "min_prior_pressure_for_delta": 0.96,
            "min_structural_weakness_for_delta": 0.98,
            "max_structural_support_for_delta": 0.08,
            "min_raw_delta_for_activation": 0.38,
            "require_distance_above_z": 0.55,
            "require_contact_below_z": -0.35,
            "chembl50_abstain_on_borderline_support": True,
            "core_guard_abstain_on_small_margin": True,
        }
        interactions = [
            "chembl50_v4_prior_pressure_only_when_distance_is_far",
            "chembl50_v4_prior_pressure_only_when_contact_is_weak",
            "chembl50_v4_abstain_when_support_is_borderline_or_core_like",
        ]
        next_step = (
            "Use chembl50_v4 as a narrower core-guard shadow candidate. The goal is to preserve the chembl50 OOD gain "
            "while shrinking active deltas enough that gpcr_core_full no longer regresses before any apply-mode retry."
        )
    elif variant == "gpcr_core_decoy_intrusion_v1":
        constraints = {
            **constraints,
            "max_abs_delta_score": 1.0,
            "yellow_band_abs_delta_score": 0.50,
        }
        tuning = {
            "variant": "gpcr_core_decoy_intrusion_v1",
            "prior_weight_h_donors": 0.0,
            "prior_weight_h_acceptors": 0.0,
            "prior_weight_rot_bonds": 0.0,
            "prior_weight_neg_logp": 0.0,
            "weakness_weight_distance": 0.0,
            "weakness_weight_neg_contact": 0.0,
            "weakness_weight_neg_stability": 0.0,
            "weakness_weight_energy": 0.0,
            "support_weight_neg_energy": 0.0,
            "support_weight_contact": 0.0,
            "support_weight_stability": 0.0,
            "support_weight_neg_distance": 0.0,
            "interaction_bias": 0.0,
            "affinity_mismatch_weight": 0.0,
            "affinity_interaction_bias": 0.0,
            "support_penalty_weight": 0.0,
            "min_prior_pressure_for_delta": 0.0,
            "min_structural_weakness_for_delta": 0.0,
            "max_structural_support_for_delta": 1.0e9,
            "min_raw_delta_for_activation": 0.0,
            "require_distance_above_z": -1.0e9,
            "require_contact_below_z": 1.0e9,
            "intrusion_weight_low_h_donors": 0.80,
            "intrusion_weight_low_h_acceptors": 0.80,
            "intrusion_weight_low_rot_bonds": 0.50,
            "intrusion_weight_high_logp": 0.70,
            "intrusion_weight_low_affinity": 0.50,
            "intrusion_weight_contact": 0.90,
            "intrusion_weight_stability": 0.40,
            "intrusion_weight_neg_energy": 0.0,
            "intrusion_weight_neg_distance": 0.30,
            "intrusion_contact_bias": 0.25,
            "min_intrusion_prior_pressure_for_delta": 1.00,
            "min_intrusion_contact_support_for_delta": 1.00,
            "min_intrusion_raw_delta_for_activation": 0.25,
            "max_intrusion_affinity_z": 0.25,
            "require_intrusion_contact_above_z": 0.20,
            "require_intrusion_distance_below_z": 0.25,
        }
        interactions = [
            "compact_hydrophobic_low_affinity_decoy_intrusion",
            "intrusion_delta_only_when_contact_support_is_high",
            "protect_beta_blocker_like_and_chembl50_high_affinity_rows",
        ]
        next_step = (
            "Run this core-decoy intrusion candidate in shadow mode first. Promote to apply-mode only if core top20 "
            "false positives receive explainable deltas while core anchors and ChEMBL50 high-affinity positives remain protected."
        )
    elif variant == "gpcr_core_linear_rescore_v1":
        constraints = {
            **constraints,
            "max_abs_delta_score": 0.0,
            "yellow_band_abs_delta_score": 0.0,
            "linear_rescore_candidate": True,
        }
        tuning = {
            "variant": "gpcr_core_linear_rescore_v1",
            "candidate_source": "local_replay_search_2026-04-30",
            "core_replay_pr_auc": 0.5681939351990422,
            "core_replay_top20_hit_rate": 0.20,
            "chembl50_replay_pr_auc": 0.8552083283821192,
            "chembl50_replay_top20_hit_rate": 1.0,
        }
        interactions = [
            "linear_rescore_rewards_affinity_hint_logp_and_rotor_support",
            "linear_rescore_keeps_v7_as_primary_score_component",
            "requires_blind_apply_run_before_claim_or_router_promotion",
        ]
        next_step = (
            "Run gpcr_core_linear_rescore_v1 as a guarded apply candidate on core and ChEMBL50 100k. "
            "Replay crossed the core PR-AUC/top20 floor, but this remains an overfit-risk candidate until the full blind run and CI gate pass."
        )
    elif variant == "gpcr_core_mismatch_contact_rescore_v1":
        constraints = {
            **constraints,
            "max_abs_delta_score": 0.80,
            "yellow_band_abs_delta_score": 0.30,
            "comparison_only_candidate": True,
            "structure_support_gate": {
                "enabled": True,
                "required_before_claim": True,
                "full_100k_gate_green": False,
            },
            "router_promotion_allowed": False,
            "apply_mode_claim_allowed": False,
            "claim_safe_assertion_allowed": False,
            "broad_gpcr_claim_allowed": False,
        }
        tuning = {
            "variant": "gpcr_core_mismatch_contact_rescore_v1",
            "candidate_source": "gpcr_100k_failure_analysis_current",
            "failure_tags": [
                "donor_prior_decoy_intrusion",
                "weak_contact_prior_mismatch",
                "affinity_hint_md_support_mismatch",
                "no_existing_score_column_recovers_gate",
            ],
            "prior_weight_h_donors": 0.30,
            "prior_weight_h_acceptors": 0.16,
            "prior_weight_rot_bonds": 0.10,
            "weakness_weight_neg_contact": 0.85,
            "weakness_weight_distance": 0.45,
            "affinity_md_support_mismatch_weight": 0.25,
            "support_weight_contact": 0.20,
            "support_weight_stability": 0.08,
            "support_weight_neg_energy": 0.10,
            "min_prior_pressure_for_delta": 0.80,
            "min_contact_mismatch_z_for_delta": 0.35,
            "max_md_support_for_affinity_hint_delta": 0.15,
            "min_raw_delta_for_activation": 0.20,
            "require_no_existing_score_recovery_gate": True,
        }
        interactions = [
            "donor_prior_decoy_intrusion_only_with_contact_mismatch",
            "affinity_hint_penalty_only_when_md_support_is_weak",
            "no_existing_score_column_recovers_gate_keeps_candidate_guarded",
            "no_router_or_general_gpcr_family_promotion",
        ]
        next_step = (
            "Run gpcr_core_mismatch_contact_rescore_v1 only as comparison telemetry or guarded apply evidence. "
            "It targets measured donor/contact/affinity mismatch tags, but must not become a claim-safe or broad GPCR router candidate."
        )
    elif variant == "gpcr_core_structure_support_rescore_v1":
        constraints = {
            **constraints,
            "max_abs_delta_score": 0.0,
            "yellow_band_abs_delta_score": 0.0,
            "comparison_only_candidate": True,
            "structure_support_gate": {
                "enabled": True,
                "required_before_claim": True,
                "full_100k_gate_green": False,
            },
            "router_promotion_allowed": False,
            "apply_mode_claim_allowed": False,
            "claim_safe_assertion_allowed": False,
            "broad_gpcr_claim_allowed": False,
            "replay_source_artifact": "runs/external_validation_2026-05-02_mismatch_contact_apply_safesync_r3_set1_core_blind_gpcr_core_full_p0_n100000_r1_stage3_scores.csv",
            "replay_pr_auc": 0.6125,
            "replay_top20_hit_rate": 0.20,
        }
        tuning = {
            "variant": "gpcr_core_structure_support_rescore_v1",
            "candidate_source": "local_replay_search_2026-05-03",
            "replay_pr_auc": 0.6125,
            "replay_top20_hit_rate": 0.20,
            "replay_positive_ranks": [1, 2, 4, 6, 22, 193],
            "replay_score_formula": (
                "binding_score_composite_v7 - 2*z_ligand_logp - 0.5*z_ligand_rot_bonds "
                "+ 0.5*z_mean_min_distance_A - z_contact_fraction + z_stability_score"
            ),
        }
        interactions = [
            "structure_support_replay_only_until_full_100k_gate_green",
            "reward_lipophilic_flexible_anchor_like_rows",
            "require_contact_and_distance_support_in_replay",
            "no_router_or_general_gpcr_family_promotion",
        ]
        next_step = (
            "Run gpcr_core_structure_support_rescore_v1 as a claim-locked comparison candidate only. "
            "The replay metric crosses the core PR-AUC/top20 floor on one measured 100k failure slice, but it must pass a fresh full 100k run and ChEMBL50 preservation before any claim discussion."
        )
    elif variant == "gpcr_core_family_balanced_rescore_v1":
        constraints = {
            **constraints,
            "max_abs_delta_score": 0.0,
            "yellow_band_abs_delta_score": 0.0,
            "comparison_only_candidate": True,
            "claim_locked_candidate": True,
            "family_balanced_rescore_candidate": True,
            "router_promotion_allowed": False,
            "platform_promotion_allowed": False,
            "apply_mode_claim_allowed": False,
            "claim_safe_assertion_allowed": False,
            "broad_gpcr_claim_allowed": False,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
            "target_identity_feature_allowed": False,
            "diagnostic_source_artifact": "runs/gpcr_guarded_100k_rank_failure_diagnostics_current.json",
            "required_before_claim": [
                "shadow_or_replay_evidence",
                "guarded_apply_evidence",
                "full_100k_ci_low_top20_claim_review_green",
            ],
        }
        tuning = {
            "variant": "gpcr_core_family_balanced_rescore_v1",
            "candidate_source": "gpcr_guarded_100k_rank_failure_diagnostics_current",
            "failure_tags": [
                "ci_low_below_threshold",
                "top20_stability_not_green",
                "non_adrb2_positive_tail_rank",
                "target_internal_decoy_intrusion",
            ],
            "current_guarded_100k_pr_auc": 0.22869872098030358,
            "current_guarded_100k_pr_auc_ci_low": 0.0019312183264511504,
            "current_guarded_100k_top20_hit_rate": 0.10,
            "current_non_adrb2_positive_tail_count": 3,
            "local_replay_pr_auc": 0.5593,
            "local_replay_top20_hit_rate": 0.25,
            "local_replay_positive_ranks": [1, 2, 3, 4, 5, 282, 762, 2957, 18915],
            "replay_score_formula": (
                "0.242*z_binding_energy_mmpbsa_kcal_mol_proxy + 0.551*z_mean_min_distance_A "
                "+ 0.226*z_stability_score - 0.553*z_contact_fraction "
                "- 4.052*z_ligand_affinity_hint - 1.956*z_ligand_onsps_norm "
                "- 0.078*z_ligand_mw + 0.264*z_ligand_logp + 0.122*z_ligand_rot_bonds "
                "- 0.226*z_ligand_h_donors + 0.461*z_ligand_h_acceptors "
                "+ 0.215*z_binding_energy_mmpbsa_std"
            ),
        }
        interactions = [
            "family_balanced_pose_energy_support",
            "donor_rich_decoy_intrusion_penalty_without_target_identity",
            "non_adrb2_tail_rank_recovery_requires_guarded_evidence",
            "full_100k_ci_low_top20_gate_required",
            "no_router_platform_or_claim_promotion",
        ]
        next_step = (
            "Run gpcr_core_family_balanced_rescore_v1 as a claim-locked replay/shadow candidate on the frozen "
            "non-ADRB2 guarded 100k evidence. Only open guarded apply after replay improves non-ADRB2 tail ranks "
            "without threshold relaxation, target identity features, or claim promotion."
        )
    elif variant == "gpcr_core_family_anchor_rescore_v2":
        constraints = {
            **constraints,
            "max_abs_delta_score": 0.0,
            "yellow_band_abs_delta_score": 0.0,
            "comparison_only_candidate": True,
            "claim_locked_candidate": True,
            "family_anchor_rescore_candidate": True,
            "router_promotion_allowed": False,
            "platform_promotion_allowed": False,
            "apply_mode_claim_allowed": False,
            "scorer_apply_allowed": False,
            "claim_safe_assertion_allowed": False,
            "broad_gpcr_claim_allowed": False,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
            "target_identity_feature_allowed": False,
            "atom_level_anchor_status": "proxy_pending",
            "diagnostic_source_artifact": "runs/gpcr_guarded_100k_rank_failure_diagnostics_current.json#drd2_pose_physics_diagnostics",
            "required_before_claim": [
                "drd2_pose_physics_diagnostics",
                "family_anchor_shadow_or_replay_evidence",
                "guarded_apply_evidence",
                "full_100k_ci_low_top20_claim_review_green",
            ],
        }
        tuning = {
            "variant": "gpcr_core_family_anchor_rescore_v2",
            "candidate_source": "latest_family_balanced_frozen_r2",
            "failure_tags": [
                "drd2_positive_tail_rank",
                "prior_overreward_without_anchor",
                "target_internal_decoy_intrusion",
                "ci_low_below_threshold",
            ],
            "latest_guarded_100k_pr_auc": 0.5186945103743427,
            "latest_guarded_100k_pr_auc_ci_low": 0.1485815545422209,
            "latest_guarded_100k_top20_hit_rate": 0.25,
            "latest_drd2_positive_global_rank": 18923,
            "latest_drd2_positive_within_target_rank": 5315,
            "anchor_proxy_mode": "stage3_pose_physics_proxy",
            "target_identity_feature_allowed": False,
            "replay_score_formula": (
                "1.00*binding_score_composite_v7_prior_active - 4.00*gpcr_basic_amine_proxy "
                "- 0.10*gpcr_conserved_anchor_proxy + 0.20*prior_overreward_without_anchor "
                "+ 3.00*gpcr_pose_chemistry_hard_decoy_pressure "
                "+ 1.40*gpcr_anchor_chemistry_mismatch_pressure"
            ),
        }
        interactions = [
            "drd2_pose_physics_rescue_first",
            "conserved_anchor_proxy_without_target_identity",
            "basic_amine_anchor_chemistry_without_target_identity",
            "ligand_prior_reward_only_when_anchor_proxy_present",
            "target_internal_pairwise_hard_decoy_pressure",
            "full_100k_ci_low_top20_gate_required",
            "no_target_identity_features",
            "no_router_platform_or_claim_promotion",
        ]
        next_step = (
            "Run gpcr_core_family_anchor_rescore_v2 only as a claim-locked shadow/replay candidate on the latest "
            "family-balanced frozen 100k evidence. It should rescue the DRD2 positive by shared pose/physics anchor "
            "support and penalize prior-only hard decoys before any guarded apply or full 100k claim review."
        )
    elif variant == "gpcr_core_family_anchor_ci_stability_v3":
        constraints = {
            **constraints,
            "max_abs_delta_score": 0.0,
            "yellow_band_abs_delta_score": 0.0,
            "comparison_only_candidate": True,
            "claim_locked_candidate": True,
            "diagnostic_only_candidate": True,
            "family_anchor_ci_stability_candidate": True,
            "router_promotion_allowed": False,
            "platform_promotion_allowed": False,
            "apply_mode_claim_allowed": False,
            "scorer_apply_allowed": False,
            "claim_safe_assertion_allowed": False,
            "broad_gpcr_claim_allowed": False,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
            "target_identity_feature_allowed": False,
            "ci_low_threshold": 0.45,
            "diagnostic_source_artifact": "runs/gpcr_guarded_100k_rank_failure_diagnostics_current.json#ci_low_stability_metadata",
            "required_before_claim": [
                "ci_low_stability_metadata",
                "acidic_anchor_overcontact_pressure_probe",
                "bootstrap_positive_support_instability_review",
                "family_anchor_v2_score_preserved_as_baseline",
                "full_100k_ci_low_top20_claim_review_green",
            ],
        }
        tuning = {
            "variant": "gpcr_core_family_anchor_ci_stability_v3",
            "candidate_source": "family_anchor_v2_shadow_ci_low_blocker",
            "failure_tags": [
                "v2_point_pr_auc_improved",
                "v2_bootstrap_pr_auc_ci_low_below_threshold",
                "bootstrap_positive_support_instability",
                "claim_promotion_blocked",
            ],
            "v2_shadow_pr_auc": 0.5767474245351905,
            "v2_shadow_pr_auc_ci_low": 0.21066694653866244,
            "v2_shadow_pr_auc_ci_low_threshold": 0.45,
            "v2_shadow_pr_auc_ci_low_gap_to_threshold": 0.23933305346133758,
            "v2_shadow_top20_hit_rate": 0.25,
            "scorer_change": "none",
            "target_identity_feature_allowed": False,
        }
        interactions = [
            "acidic_anchor_overcontact_pressure_probe",
            "bootstrap_ci_low_stability_probe",
            "ci_low_stability_metadata_required",
            "family_anchor_v2_score_preserved_as_baseline",
            "no_new_live_scorer_terms",
            "no_target_identity_features",
            "no_router_platform_or_claim_promotion",
        ]
        next_step = (
            "Use gpcr_core_family_anchor_ci_stability_v3 as a diagnostic-only packet to explain why v2 shadow "
            "PR-AUC CI-low remains below 0.45. Keep v2 scoring evidence frozen and do not open guarded apply until "
            "bootstrap CI-low stability is green."
        )
    elif variant == "gpcr_core_acidic_anchor_overcontact_prior_gate_v4":
        constraints = {
            **constraints,
            "max_abs_delta_score": 0.0,
            "yellow_band_abs_delta_score": 0.0,
            "comparison_only_candidate": True,
            "claim_locked_candidate": True,
            "shadow_only_candidate": True,
            "diagnostic_only_candidate": True,
            "acidic_anchor_overcontact_prior_gate_candidate": True,
            "router_promotion_allowed": False,
            "platform_promotion_allowed": False,
            "apply_mode_claim_allowed": False,
            "scorer_apply_allowed": False,
            "claim_safe_assertion_allowed": False,
            "broad_gpcr_claim_allowed": False,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
            "target_identity_feature_allowed": False,
            "label_feature_allowed": False,
            "rank_feature_allowed": False,
            "ligand_id_feature_allowed": False,
            "reference_binding_value_allowed": False,
            "diagnostic_source_artifact": "runs/gpcr_guarded_100k_rank_failure_diagnostics_current.json#post_v3_acidic_anchor_review",
            "required_before_claim": [
                "shadow_only_overcontact_prior_gate_telemetry",
                "leakage_review_no_target_label_rank_id_reference_inputs",
                "family_anchor_v2_and_v3_behavior_preserved",
                "fresh_full_100k_ci_low_top20_claim_review_green",
            ],
        }
        tuning = {
            "variant": "gpcr_core_acidic_anchor_overcontact_prior_gate_v4",
            "candidate_source": "post_v3_acidic_anchor_overcontact_prior_gate",
            "failure_tags": [
                "acidic_anchor_overcontact_pressure_probe",
                "prior_overreward_without_anchor",
                "basic_amine_absent_anchor_overcontact",
                "claim_promotion_blocked",
            ],
            "scorer_change": "shadow_only_linear_candidate",
            "target_identity_feature_allowed": False,
            "label_feature_allowed": False,
            "rank_feature_allowed": False,
            "ligand_id_feature_allowed": False,
            "reference_binding_value_allowed": False,
            "threshold_relaxation_allowed": False,
            "replay_score_formula": (
                "binding_score_composite_v7_prior_active "
                "+ 2.25*gpcr_acidic_anchor_overcontact_prior_gate"
            ),
        }
        interactions = [
            "post_v3_acidic_anchor_overcontact_prior_gate",
            "overcontact_gate_requires_prior_overreward_without_anchor",
            "no_target_identity_labels_ranks_ligand_ids_or_reference_values",
            "threshold_relaxation_forbidden",
            "shadow_only_active_claim_disabled",
            "no_router_platform_or_claim_promotion",
        ]
        next_step = (
            "Run gpcr_core_acidic_anchor_overcontact_prior_gate_v4 only as a claim-locked shadow diagnostic after "
            "v3. It probes whether acidic-anchor overcontact plus prior overreward explains hard-decoy pressure "
            "without target identity, labels, ranks, ligand IDs, reference binding values, or threshold relaxation."
        )
    elif variant == "gpcr_adrb2_beta_blocker_pharmacophore_v1":
        constraints = {
            **constraints,
            "max_abs_delta_score": 0.0,
            "yellow_band_abs_delta_score": 4.0,
            "target_specific_pharmacophore_candidate": True,
            "router_promotion_allowed": False,
        }
        tuning = {
            "variant": "gpcr_adrb2_beta_blocker_pharmacophore_v1",
            "pharmacophore_reward_score": 8.0,
            "pharmacophore_smarts": "aryloxypropanolamine",
            "scope": "ADRB2_GPCR_BLIND_beta_blocker_like_only",
        }
        interactions = [
            "target_specific_adrb2_beta_blocker_pharmacophore_shadow_only",
            "reward_declared_aryloxypropanolamine_match",
            "no_router_or_general_gpcr_family_promotion",
        ]
        next_step = (
            "Run as shadow-only on the GPCR core 100k lane, evaluate the residual shadow score separately, "
            "and keep any improvement scoped to ADRB2 beta-blocker-like evidence until non-leaky family validation exists."
        )

    return {
        "summary": {
            "family": "gpcr",
            "prototype_mode": "shadow_only",
            "prototype_status": "shadow_runtime_ready",
            "prototype_variant": variant,
            "source_failure_slice": "gpcr_core_full_100k",
            "source_failure_artifact": "runs/gpcr_100k_failure_analysis_current.md",
            "source_validity_artifact": "runs/ligand_scaleup_100k_test_audit_current.md",
            "next_required_step": next_step,
        },
        "prototype": {
            "family": "gpcr",
            "domain_token": "gpcr",
            "apply_stage": "stage5_ranking",
            "training_focus": {
                "positive_anchor_count": 6,
                "false_positive_focus_topk": 20,
                "failure_rank_shift_target": "reduce last positive rank shift from +122 toward baseline-like top-k retention",
            },
            "constraints": constraints,
            "interactions": interactions,
            "tuning": tuning,
            "linear_rescore": (
                {
                    "enabled": True,
                    "combine_mode": "replace",
                    "intercept": 0.0,
                    "terms": [
                        {"feature": "binding_score_composite_v7", "weight": 0.6560744988396956},
                        {"feature": "z_binding_energy_mmpbsa_kcal_mol_proxy", "weight": 0.06898074371659835},
                        {"feature": "z_ligand_affinity_hint", "weight": -1.2316300252578614},
                        {"feature": "z_ligand_logp", "weight": -1.2116692638345479},
                        {"feature": "z_ligand_mw", "weight": 0.027722286583714784},
                        {"feature": "z_ligand_h_donors", "weight": -0.2874434467251168},
                        {"feature": "z_ligand_h_acceptors", "weight": 0.03213238193362028},
                        {"feature": "z_ligand_rot_bonds", "weight": -0.5706661687175658},
                        {"feature": "z_contact_fraction", "weight": 0.20125635810931242},
                        {"feature": "z_stability_score", "weight": 0.31932524360428327},
                        {"feature": "z_mean_min_distance_A", "weight": 0.45613011893835237},
                    ],
                }
                if variant == "gpcr_core_linear_rescore_v1"
                else {
                    "enabled": True,
                    "combine_mode": "replace",
                    "intercept": 0.0,
                    "terms": [
                        {"feature": "binding_score_composite_v7", "weight": 1.0},
                        {"feature": "z_ligand_logp", "weight": -2.0},
                        {"feature": "z_ligand_rot_bonds", "weight": -0.5},
                        {"feature": "z_mean_min_distance_A", "weight": 0.5},
                        {"feature": "z_contact_fraction", "weight": -1.0},
                        {"feature": "z_stability_score", "weight": 1.0},
                    ],
                }
                if variant == "gpcr_core_structure_support_rescore_v1"
                else {
                    "enabled": True,
                    "combine_mode": "replace",
                    "intercept": 0.0,
                    "terms": [
                        {"feature": "z_binding_energy_mmpbsa_kcal_mol_proxy", "weight": 0.242},
                        {"feature": "z_mean_min_distance_A", "weight": 0.551},
                        {"feature": "z_stability_score", "weight": 0.226},
                        {"feature": "z_contact_fraction", "weight": -0.553},
                        {"feature": "z_ligand_affinity_hint", "weight": -4.052},
                        {"feature": "z_ligand_onsps_norm", "weight": -1.956},
                        {"feature": "z_ligand_mw", "weight": -0.078},
                        {"feature": "z_ligand_logp", "weight": 0.264},
                        {"feature": "z_ligand_rot_bonds", "weight": 0.122},
                        {"feature": "z_ligand_h_donors", "weight": -0.226},
                        {"feature": "z_ligand_h_acceptors", "weight": 0.461},
                        {"feature": "z_binding_energy_mmpbsa_std", "weight": 0.215},
                    ],
                }
                if variant == "gpcr_core_family_balanced_rescore_v1"
                else {
                    "enabled": True,
                    "combine_mode": "replace",
                    "intercept": 0.0,
                    "terms": [
                        {"feature": "binding_score_composite_v7_prior_active", "weight": 1.0},
                        {"feature": "gpcr_basic_amine_proxy", "weight": -4.0},
                        {"feature": "gpcr_conserved_anchor_proxy", "weight": -0.1},
                        {"feature": "prior_overreward_without_anchor", "weight": 0.2},
                        {"feature": "gpcr_pose_chemistry_hard_decoy_pressure", "weight": 3.0},
                        {"feature": "gpcr_anchor_chemistry_mismatch_pressure", "weight": 1.4},
                    ],
                }
                if variant == "gpcr_core_family_anchor_rescore_v2"
                else {
                    "enabled": True,
                    "combine_mode": "replace",
                    "intercept": 0.0,
                    "terms": [
                        {"feature": "binding_score_composite_v7_prior_active", "weight": 1.0},
                        {"feature": "gpcr_acidic_anchor_overcontact_prior_gate", "weight": 2.25},
                    ],
                }
                if variant == "gpcr_core_acidic_anchor_overcontact_prior_gate_v4"
                else {"enabled": False}
            ),
            "feature_rows": feature_rows,
            "evidence_files": [
                "runs/gpcr_100k_failure_analysis_current.md",
                "runs/global_residual_correction_target_list_current.md",
                "runs/ligand_scaleup_100k_test_audit_current.md",
                "runs/ligand_cascade_speedup_envelope_current.md",
                "runs/gpcr_residual_apply_decision_current.md",
            ],
        },
        "feature_rows": feature_rows,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    proto = payload["prototype"]
    tuning = proto.get("tuning", {}) if isinstance(proto.get("tuning", {}), dict) else {}
    lines = [
        "# GPCR Residual Prototype Spec",
        "",
        f"- family: `{summary['family']}`",
        f"- prototype_mode: `{summary['prototype_mode']}`",
        f"- prototype_status: `{summary['prototype_status']}`",
        f"- prototype_variant: `{summary.get('prototype_variant', 'current')}`",
        f"- source_failure_slice: `{summary['source_failure_slice']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Constraints",
        "",
        f"- max_abs_delta_score: `{proto['constraints']['max_abs_delta_score']}`",
        f"- yellow_band_abs_delta_score: `{proto['constraints']['yellow_band_abs_delta_score']}`",
        f"- preserve_top2_binders: `{proto['constraints']['preserve_top2_binders']}`",
        f"- require_energy_contact_support_for_positive_delta: `{proto['constraints']['require_energy_contact_support_for_positive_delta']}`",
        f"- reference_scaling_mode: `{proto['constraints']['reference_scaling_mode']}`",
        f"- structure_support_gate: `{proto['constraints'].get('structure_support_gate', {})}`",
        "",
        "## Tuning",
        "",
        f"- variant: `{tuning.get('variant', 'current')}`",
        f"- min_prior_pressure_for_delta: `{tuning.get('min_prior_pressure_for_delta', 0.0)}`",
        f"- min_structural_weakness_for_delta: `{tuning.get('min_structural_weakness_for_delta', 0.0)}`",
        f"- max_structural_support_for_delta: `{tuning.get('max_structural_support_for_delta', 'unbounded')}`",
        f"- require_distance_above_z: `{tuning.get('require_distance_above_z', 'off')}`",
        f"- require_contact_below_z: `{tuning.get('require_contact_below_z', 'off')}`",
        f"- min_intrusion_prior_pressure_for_delta: `{tuning.get('min_intrusion_prior_pressure_for_delta', 'off')}`",
        f"- min_intrusion_contact_support_for_delta: `{tuning.get('min_intrusion_contact_support_for_delta', 'off')}`",
        f"- linear_rescore_enabled: `{proto.get('linear_rescore', {}).get('enabled', False)}`",
        "",
        "## Feature Targets",
        "",
        "| feature_name | role | direction | rationale |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["feature_rows"]:
        lines.append(
            f"| {row['feature_name']} | {row['role']} | {row['direction']} | {row['rationale']} |"
        )
    lines.extend(["", "## Interaction Terms", ""])
    for item in proto["interactions"]:
        lines.append(f"- `{item}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the current GPCR residual prototype spec from the measured 100k failure slice.")
    parser.add_argument(
        "--variant",
        choices=[
            "current",
            "narrow_v2",
            "chembl50_v3",
            "chembl50_v4",
            "gpcr_core_decoy_intrusion_v1",
            "gpcr_core_linear_rescore_v1",
            "gpcr_core_mismatch_contact_rescore_v1",
            "gpcr_core_structure_support_rescore_v1",
            "gpcr_core_family_balanced_rescore_v1",
            "gpcr_core_family_anchor_rescore_v2",
            "gpcr_core_family_anchor_ci_stability_v3",
            "gpcr_core_acidic_anchor_overcontact_prior_gate_v4",
            "gpcr_adrb2_beta_blocker_pharmacophore_v1",
        ],
        default="current",
    )
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(variant=str(args.variant))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(out_csv, payload["feature_rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
