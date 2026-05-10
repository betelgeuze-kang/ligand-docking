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
        "gpcr_core_fixed_reference_live_shadow_v5",
        "gpcr_core_class_a_motif_shadow_v6",
        "gpcr_core_class_a_anchor_geometry_shadow_v7",
        "gpcr_core_direct_atom_anchor_window_shadow_v8",
        "gpcr_core_atom_window_excess_polar_shadow_v9",
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
    if variant == "gpcr_core_fixed_reference_live_shadow_v5":
        rows.extend(
            [
                {
                    "feature_name": "fixed_reference_scaling_enabled",
                    "role": "fixed_reference_activation_gate",
                    "direction": "activate_only_under_fixed_family_reference_scaling",
                    "rationale": (
                        "The v5 shadow scorer is live only when frozen family reference scaling is active; "
                        "run-local scaling emits telemetry but no pressure."
                    ),
                },
                {
                    "feature_name": "fixed_reference_pose_prior_support",
                    "role": "target_agnostic_support_guard",
                    "direction": "protect_shared_anchor_pose_physics_and_basic_amine_support",
                    "rationale": (
                        "Preserves the v2 family-anchor baseline by treating shared pose/physics and basic-amine "
                        "compatibility as support, without target, label, rank, ligand-id, or reference-binding inputs."
                    ),
                },
                {
                    "feature_name": "fixed_reference_live_overreward_pressure",
                    "role": "fixed_reference_live_shadow_pressure",
                    "direction": "penalize_prior_overreward_without_pose_chemistry_support",
                    "rationale": (
                        "Post-v4 reject candidate pressure avoids porting v2/v4 weights and uses only target-agnostic "
                        "pressures observed to remain live in the fixed-reference replay."
                    ),
                },
                {
                    "feature_name": "fixed_reference_prior_weakness_pressure",
                    "role": "fixed_reference_live_shadow_pressure_component",
                    "direction": "target_agnostic_prior_weakness_alias",
                    "rationale": (
                        "Renames the target-free prior weakness component for v5 governance so the scorer does not "
                        "appear to depend on target-internal rank, label, ligand ID, or reference-binding inputs."
                    ),
                },
                {
                    "feature_name": "fixed_reference_feature_collapse_probe",
                    "role": "feature_collapse_telemetry",
                    "direction": "diagnostic_only",
                    "rationale": (
                        "Fixed-reference replay showed conserved-anchor, pose-physics, and acidic-overcontact "
                        "features collapsed to near-zero activation; v5 records this instead of treating collapse "
                        "as evidence of success."
                    ),
                },
                {
                    "feature_name": "family_anchor_v2_best_baseline_lock",
                    "role": "baseline_preservation",
                    "direction": "comparison_only",
                    "rationale": (
                        "v2 remains the best accepted baseline; v5 only emits shadow diagnostics and cannot replace "
                        "v2 for claims or active ranking."
                    ),
                },
            ]
        )
    if variant == "gpcr_core_class_a_motif_shadow_v6":
        rows.extend(
            [
                {
                    "feature_name": "class_a_aminergic_opioid_orthosteric_sublane_scope",
                    "role": "claim_locked_scope",
                    "direction": "narrow_class_a_orthosteric_sublane_not_broad_gpcr",
                    "rationale": (
                        "v6 is explicitly scoped to Class A aminergic/opioid-like orthosteric-lane motif behavior, "
                        "not broad GPCR family delivery or router claims."
                    ),
                },
                {
                    "feature_name": "class_a_orthosteric_motif_support_proxy",
                    "role": "motif_support_proxy",
                    "direction": "reward_basic_amine_pose_trajectory_support",
                    "rationale": (
                        "Uses only existing SMILES basic-amine heuristic plus pose, trajectory, and support proxies "
                        "to approximate active-state orthosteric motif compatibility."
                    ),
                },
                {
                    "feature_name": "class_a_prior_overreward_invalid_overanchor_pressure",
                    "role": "shadow_pressure",
                    "direction": "penalize_prior_overreward_or_invalid_overanchor_without_motif_support",
                    "rationale": (
                        "Separates prior-rich or overanchored rows from supported orthosteric motif-like rows without "
                        "target, binder label, rank, ligand ID, or reference-binding inputs."
                    ),
                },
                {
                    "feature_name": "class_a_motif_shadow_score",
                    "role": "claim_locked_shadow_score",
                    "direction": "shadow_only_active_score_locked_to_base",
                    "rationale": (
                        "Candidate emits a score-only shadow column. Apply mode is intentionally active-locked to "
                        "the base score until fresh guarded evidence exists."
                    ),
                },
                {
                    "feature_name": "family_anchor_v2_donor_baseline_lock",
                    "role": "baseline_preservation",
                    "direction": "comparison_only",
                    "rationale": "v2 remains the donor/baseline lane; v6 may not replace active ranking or claims.",
                },
                {
                    "feature_name": "v4_v5_tombstone_reject_preservation",
                    "role": "reject_history_preservation",
                    "direction": "diagnostic_only",
                    "rationale": "v4 and v5 remain preserved as tombstone reject evidence rather than promoted baselines.",
                },
            ]
        )
    if variant == "gpcr_core_class_a_anchor_geometry_shadow_v7":
        rows.extend(
            [
                {
                    "feature_name": "class_a_aminergic_opioid_orthosteric_sublane_scope",
                    "role": "claim_locked_scope",
                    "direction": "narrow_class_a_orthosteric_sublane_not_broad_gpcr",
                    "rationale": (
                        "v7 is explicitly scoped to Class A aminergic/opioid-like orthosteric sublane anchor "
                        "geometry. It must not be used for broad GPCR family delivery, router, or platform claims."
                    ),
                },
                {
                    "feature_name": "class_a_charge_complemented_anchor_geometry_proxy",
                    "role": "anchor_geometry_support_proxy",
                    "direction": "reward_basic_amine_charge_complemented_anchor_geometry",
                    "rationale": (
                        "Uses only the existing SMILES basic-amine heuristic plus pose/contact/distance/energy "
                        "proxies to approximate charge-complemented orthosteric anchor geometry."
                    ),
                },
                {
                    "feature_name": "class_a_orthosteric_occupancy_proxy",
                    "role": "orthosteric_occupancy_support_proxy",
                    "direction": "reward_contact_distance_energy_occupancy_support",
                    "rationale": (
                        "Live proxy for orthosteric pocket occupancy from stage3 contact, distance, stability, and "
                        "energy columns only; no target, label, rank, ligand-id, or reference-binding inputs."
                    ),
                },
                {
                    "feature_name": "class_a_pose_survival_support_proxy",
                    "role": "pose_survival_support_proxy",
                    "direction": "reward_trajectory_survival_and_pose_physics_support",
                    "rationale": (
                        "Separates supported Class A sublane poses from prior-only rows by using trajectory/stability, "
                        "contact, distance, and energy proxies without claim leakage."
                    ),
                },
                {
                    "feature_name": "class_a_invalid_anchor_prior_pressure_v7",
                    "role": "shadow_pressure",
                    "direction": "penalize_invalid_anchor_or_prior_pressure_without_geometry_support",
                    "rationale": (
                        "Penalizes prior-rich, anchorless, or invalid-overanchor rows only when not supported by "
                        "charge-complemented anchor geometry, orthosteric occupancy, and pose survival."
                    ),
                },
                {
                    "feature_name": "class_a_anchor_geometry_shadow_score_v7",
                    "role": "claim_locked_shadow_score",
                    "direction": "shadow_only_active_score_locked_to_base",
                    "rationale": (
                        "Candidate emits a score-only shadow column. Apply mode remains active-locked to the base "
                        "binding score until fresh guarded evidence exists."
                    ),
                },
                {
                    "feature_name": "family_anchor_v2_donor_baseline_lock",
                    "role": "baseline_preservation",
                    "direction": "comparison_only",
                    "rationale": "v2 remains the donor/baseline lane; v7 may not replace active ranking or claims.",
                },
                {
                    "feature_name": "v4_v5_v6_reject_preservation",
                    "role": "reject_history_preservation",
                    "direction": "diagnostic_only",
                    "rationale": "v4, v5, and the rejected v6 packet remain preserved as reject evidence rather than promoted baselines.",
                },
            ]
        )
    if variant in {
        "gpcr_core_direct_atom_anchor_window_shadow_v8",
        "gpcr_core_atom_window_excess_polar_shadow_v9",
    }:
        rows.extend(
            [
                {
                    "feature_name": "class_a_direct_atom_window_anchor_geometry_proxy",
                    "role": "direct_atom_window_support",
                    "direction": "reward_basic_amine_when_anchor_distance_stays_in_2p8_to_4p2A_window",
                    "rationale": (
                        "Uses precomputed native acidic-anchor trajectory distances instead of stage3 proxy-only "
                        "contact/distance signals. This keeps the next scorer contract focused on atom-window "
                        "geometry after the v7 proxy replay reject."
                    ),
                },
                {
                    "feature_name": "class_a_hydrophobic_overcontact_pressure_v8",
                    "role": "direct_atom_window_pressure",
                    "direction": "penalize_hydrophobic_or_low_polar_rows_with_too_close_acidic_anchor_contact",
                    "rationale": (
                        "DRD2 diagnostics show top decoys can over-contact the acidic anchor. This pressure uses "
                        "only ligand chemistry plus precomputed atom-window distances to separate true anchor "
                        "geometry from hydrophobic overcontact."
                    ),
                },
                {
                    "feature_name": "class_a_atom_anchor_feature_available_proxy",
                    "role": "feature_availability_telemetry",
                    "direction": "diagnostic_only_no_missing_feature_penalty",
                    "rationale": (
                        "Rows without precomputed atom-window features must not be treated as failures. Missing "
                        "direct features are telemetry only and keep the active score locked to base."
                    ),
                },
                {
                    "feature_name": "class_a_atom_window_shadow_score_v8",
                    "role": "claim_locked_shadow_score",
                    "direction": "shadow_only_active_score_locked_to_base",
                    "rationale": (
                        "Candidate emits a score-only shadow column. Apply mode remains active-locked to the base "
                        "binding score until fresh guarded evidence exists."
                    ),
                },
                {
                    "feature_name": "class_a_excess_polar_anchor_pressure_v9",
                    "role": "direct_atom_window_pressure",
                    "direction": "penalize_multipolar_basic_amine_decoys_when_atom_window_reward_is_active",
                    "rationale": (
                        "The v8 replay promoted DRD2 hard decoys that had basic-amine and atom-window support but "
                        "excess donor/acceptor burden. This pressure is target-free and label-free, and only "
                        "activates behind precomputed atom-window support."
                    ),
                },
                {
                    "feature_name": "class_a_compact_amine_window_support_v9",
                    "role": "direct_atom_window_support",
                    "direction": "reward_compact_basic_amine_atom_window_support_without_target_identity",
                    "rationale": (
                        "Supports compact Class A aminergic-like ligands when atom-window geometry is present, while "
                        "avoiding reward for donor/acceptor-heavy multipolar decoys."
                    ),
                },
                {
                    "feature_name": "v7_reject_preservation",
                    "role": "reject_history_preservation",
                    "direction": "diagnostic_only",
                    "rationale": (
                        "v7 remains preserved as reject/rework evidence; v8 must not silently promote v7 proxy "
                        "terms or broad GPCR/basic-amine wording."
                    ),
                },
            ]
        )
    if variant == "gpcr_core_cationic_pose_distortion_shadow_v10":
        rows.extend(
            [
                {
                    "feature_name": "base_score",
                    "role": "selected_slice_score_anchor",
                    "direction": "preserve_base_score_as_formula_anchor",
                    "rationale": (
                        "v10 is replayed first on the repaired DRD2 hard-decoy slice. It reuses the slice packet's "
                        "frozen base score instead of changing the active production score."
                    ),
                },
                {
                    "feature_name": "label_free_penalty_pressure",
                    "role": "cationic_pose_distortion_pressure",
                    "direction": "penalize_invalid_overanchor_hydrophobic_multipolar_and_pose_distorted_decoys",
                    "rationale": (
                        "The selected slice separates DRD2 rank inversion into label-free pressures: invalid close "
                        "overanchor without basic amine, hydrophobic overcontact, multipolar basic overanchor, "
                        "cationic-window mismatch, and pose distortion."
                    ),
                },
                {
                    "feature_name": "label_free_support_pressure",
                    "role": "cationic_pose_preservation_support",
                    "direction": "reward_repaired_positive_anchor_window_and_pose_preservation_support",
                    "rationale": (
                        "Support only comes from cationic-center geometry, atom-window support, compact anchor "
                        "support, and pose-preservation telemetry already materialized in the hard-decoy slice."
                    ),
                },
                {
                    "feature_name": "cationic_center_geometry_available",
                    "role": "feature_availability_telemetry",
                    "direction": "diagnostic_only_no_missing_feature_penalty",
                    "rationale": (
                        "Rows without cationic-center telemetry are tracked as missing telemetry, not as negative "
                        "evidence or claim blockers."
                    ),
                },
                {
                    "feature_name": "pose_distortion_pressure",
                    "role": "pose_generation_repair_pressure",
                    "direction": "penalize_distorted_valid_anchor_rows_only_in_shadow_replay",
                    "rationale": (
                        "The repair lane showed apparent anchor support can still be distorted after pseudo-allatom "
                        "backmapping. v10 keeps this as a claim-locked pressure until broader caches exist."
                    ),
                },
                {
                    "feature_name": "v8_v9_reject_preservation",
                    "role": "reject_history_preservation",
                    "direction": "diagnostic_only",
                    "rationale": "v8 and v9 remain preserved as reject/rework evidence, not promoted scoring baselines.",
                },
            ]
        )
    if variant == "gpcr_core_cationic_weakbase_rescue_shadow_v11":
        rows.extend(
            [
                {
                    "feature_name": "base_score",
                    "role": "selected_slice_score_anchor",
                    "direction": "preserve_base_score_as_formula_anchor",
                    "rationale": (
                        "v11 keeps the base score as the active-lock anchor and only evaluates a claim-locked "
                        "shadow score."
                    ),
                },
                {
                    "feature_name": "label_free_penalty_pressure",
                    "role": "cationic_pose_distortion_pressure",
                    "direction": "penalize_invalid_overanchor_hydrophobic_multipolar_and_pose_distorted_decoys",
                    "rationale": "Carries the v10 label-free decoy pressure contract forward unchanged.",
                },
                {
                    "feature_name": "weak_base_rescue_support_pressure",
                    "role": "weak_base_conditional_anchor_support",
                    "direction": "reward_cationic_pose_support_only_when_base_score_is_weak",
                    "rationale": (
                        "all_basic anchor placement rescued the DRD2 positive but also overpromoted already-strong "
                        "decoys. This term gates anchor support by weak/borderline base score instead of rewarding "
                        "all valid anchors."
                    ),
                },
                {
                    "feature_name": "weak_base_rescue_gate",
                    "role": "score_conditioning_telemetry",
                    "direction": "diagnostic_only_label_free_score_condition",
                    "rationale": (
                        "Telemetry for the continuous weak-base gate. It uses the base score only, not target, label, "
                        "rank, ligand_id, or reference-binding features."
                    ),
                },
                {
                    "feature_name": "v10_selected_slice_rework_preservation",
                    "role": "reject_history_preservation",
                    "direction": "diagnostic_only",
                    "rationale": "v10 remains selected-slice green/rework evidence and is not silently promoted to a claim.",
                },
            ]
        )
    if variant == "gpcr_core_synthetic_anchor_penalty_shadow_v12":
        rows.extend(
            [
                {
                    "feature_name": "base_score",
                    "role": "true_base_score_anchor",
                    "direction": "preserve_true_binding_score_composite_v7_as_formula_anchor",
                    "rationale": (
                        "v12 explicitly uses the immutable v7 base score from the frozen feature cache. Stale "
                        "residual-active columns are not allowed to seed the replay."
                    ),
                },
                {
                    "feature_name": "gpcr_synthetic_anchor_saturation_pressure_v12",
                    "role": "synthetic_anchor_penalty",
                    "direction": "penalize_all_basic_forced_anchor_support_when_it_saturates",
                    "rationale": (
                        "The complete v11 true-base frozen replay showed all_basic placement creates many "
                        "support=1.0 decoys. Saturated support is treated as a label-free artifact pressure, not "
                        "as better anchor geometry."
                    ),
                },
                {
                    "feature_name": "gpcr_moderate_multi_basic_weakbase_support_v12",
                    "role": "moderate_anchor_support_reward",
                    "direction": "reward_only_plausible_moderate_multi_basic_support_with_pose_preservation",
                    "rationale": (
                        "DRD2 rescue signal sits in a moderate support window rather than at synthetic saturation. "
                        "This term keeps support conditional on weak-base score, multi-basic chemistry, and "
                        "centroid-preserving pseudo-allatom repair."
                    ),
                },
                {
                    "feature_name": "gpcr_plausible_anchor_window_support_v12",
                    "role": "support_window_telemetry",
                    "direction": "diagnostic_only_separates_moderate_from_saturated_anchor_support",
                    "rationale": "Records the label-free window that blocks monotonic closer-or-more-saturated-is-better scoring.",
                },
                {
                    "feature_name": "v11_full_frozen_replay_blocker_preservation",
                    "role": "reject_history_preservation",
                    "direction": "diagnostic_only",
                    "rationale": (
                        "v11 remains selected-slice green but full true-base frozen replay is blocked. v12 may only "
                        "be shadow evidence until CI-low/top20 and family-held-out gates are green."
                    ),
                },
            ]
        )
    if variant == "gpcr_core_pose_support_gap_shadow_v13":
        rows.extend(
            [
                {
                    "feature_name": "base_score",
                    "role": "true_base_score_anchor",
                    "direction": "preserve_true_binding_score_composite_v7_as_formula_anchor",
                    "rationale": "v13 keeps the same true-base frozen score anchor as v12 and remains shadow-only.",
                },
                {
                    "feature_name": "gpcr_unsupported_strong_base_pressure_v13",
                    "role": "unsupported_base_intrusion_pressure",
                    "direction": "penalize_strong_base_score_rows_without_anchor_or_weakbase_support",
                    "rationale": (
                        "The v12 gap packet shows HTR2A/OPRM1 are still blocked by strong base-score decoys with "
                        "little portable support. This target-free pressure demotes overconfident unsupported rows "
                        "instead of rewarding labels."
                    ),
                },
                {
                    "feature_name": "gpcr_pose_gap_strong_base_pressure_v13",
                    "role": "pose_gap_intrusion_pressure",
                    "direction": "penalize_strong_base_score_rows_when_pose_survival_support_is_missing",
                    "rationale": (
                        "OPRM1 still has a pose/backmapping collapse signal. The pressure is gated by strong base "
                        "score so it suppresses unsupported decoy intrusion without directly penalizing weakly scored "
                        "positive rows."
                    ),
                },
                {
                    "feature_name": "multipolar_basic_pressure",
                    "role": "carryover_decoy_pressure",
                    "direction": "penalize_multipolar_basic_decoy_intrusion",
                    "rationale": "The v12 gap packet keeps multipolar decoy pressure as a remaining HTR2A/OPRM1 blocker.",
                },
                {
                    "feature_name": "v12_shadow_review_preservation",
                    "role": "reject_history_preservation",
                    "direction": "diagnostic_only",
                    "rationale": "v12 remains DRD2-recovery shadow evidence, not a promoted claim or guarded apply scorer.",
                },
            ]
        )
    if variant == "gpcr_core_truebase_anchor_occupancy_shadow_v14":
        rows.extend(
            [
                {
                    "feature_name": "base_score",
                    "role": "true_base_score_anchor",
                    "direction": "preserve_true_binding_score_composite_v7_as_formula_anchor",
                    "rationale": (
                        "v14 keeps the frozen true-base score as the replay anchor and explicitly avoids stale "
                        "residual-active score columns when computing support-gap pressure."
                    ),
                },
                {
                    "feature_name": "gpcr_true_base_score_for_gap_v14",
                    "role": "true_base_score_gap_telemetry",
                    "direction": "diagnostic_only_uses_cached_base_score_when_present",
                    "rationale": (
                        "The v13 review showed some OPRM1 decoys kept zero unsupported-pressure because replay-active "
                        "score context could diverge from the cached true-base score. v14 records the exact score used "
                        "for the true-base strong-decoy gate."
                    ),
                },
                {
                    "feature_name": "gpcr_cationic_anchor_occupancy_support_v14",
                    "role": "cationic_center_occupancy_support",
                    "direction": "reward_basic_cationic_center_window_only_with_pose_survival",
                    "rationale": (
                        "HTR2A had cationic-center window occupancy but failed the stricter all-atom support path. "
                        "This target-free support term is gated by basic chemistry, cationic-center distance window, "
                        "and pose preservation; it does not use target, label, rank, ligand_id, or reference binding."
                    ),
                },
                {
                    "feature_name": "gpcr_truebase_unsupported_strong_base_pressure_v14",
                    "role": "truebase_unsupported_decoy_pressure",
                    "direction": "penalize_cached_true_base_strong_rows_without_portable_support",
                    "rationale": (
                        "Strong true-base rows without anchor/occupancy/weak-base support are demoted as decoy "
                        "intrusion candidates. This is a label-free guard against unsupported OPRM1-style rank "
                        "intrusion."
                    ),
                },
                {
                    "feature_name": "gpcr_truebase_pose_gap_pressure_v14",
                    "role": "truebase_pose_gap_pressure",
                    "direction": "penalize_cached_true_base_strong_rows_when_pose_survival_is_missing",
                    "rationale": (
                        "Pose/backmapping collapse remains an OPRM1 blocker. v14 gates the pose-gap penalty by "
                        "cached true-base strength so weakly scored positive rows are not manually lifted or punished."
                    ),
                },
                {
                    "feature_name": "gpcr_truebase_backmapping_collapse_pressure_v14",
                    "role": "truebase_backmapping_collapse_pressure",
                    "direction": "penalize_strong_truebase_rows_with_near_zero_pose_preservation",
                    "rationale": (
                        "This pressure isolates hard collapse cases from borderline pose-preservation rows and keeps "
                        "the correction tied to portable geometry rather than target-specific labels."
                    ),
                },
                {
                    "feature_name": "gpcr_truebase_overclose_artifact_pressure_v14",
                    "role": "truebase_cationic_overclose_artifact_pressure",
                    "direction": "penalize_strong_truebase_rows_with_cationic_center_overclose_and_pose_gap",
                    "rationale": (
                        "Acidic-anchor proximity is not monotonic reward. v14 treats cationic-center overclose plus "
                        "pose-gap as artifact pressure when the cached true-base score is already very strong."
                    ),
                },
                {
                    "feature_name": "v13_shadow_review_preservation",
                    "role": "reject_history_preservation",
                    "direction": "diagnostic_only",
                    "rationale": "v13 remains a useful DRD2/HTR2A direction signal but not a promoted scorer.",
                },
            ]
        )
    if variant == "gpcr_core_truebase_gap_penalty_shadow_v15":
        rows.extend(
            [
                {
                    "feature_name": "base_score",
                    "role": "true_base_score_anchor",
                    "direction": "preserve_true_binding_score_composite_v7_as_formula_anchor",
                    "rationale": "v15 keeps the immutable true-base score anchor and remains shadow-only.",
                },
                {
                    "feature_name": "gpcr_truebase_unsupported_strong_base_pressure_v15",
                    "role": "truebase_unsupported_decoy_pressure",
                    "direction": "penalize_cached_true_base_strong_rows_without_v13_portable_support",
                    "rationale": (
                        "v14 showed cationic-center occupancy reward overpromotes HTR2A decoys. v15 removes that "
                        "reward and uses cached true-base pressure only when the stricter v13 support signal is missing."
                    ),
                },
                {
                    "feature_name": "gpcr_truebase_pose_gap_pressure_v15",
                    "role": "truebase_pose_gap_pressure",
                    "direction": "penalize_cached_true_base_strong_rows_when_pose_survival_is_missing",
                    "rationale": (
                        "The pose-gap penalty stays tied to cached true-base score and pose preservation, without "
                        "target, label, rank, ligand_id, reference-binding, or cationic-occupancy reward features."
                    ),
                },
                {
                    "feature_name": "gpcr_truebase_backmapping_collapse_pressure_v14",
                    "role": "truebase_backmapping_collapse_pressure",
                    "direction": "carry_forward_truebase_collapse_pressure_without_reward",
                    "rationale": "v15 keeps the v14 collapse pressure but removes the v14 cationic occupancy reward.",
                },
                {
                    "feature_name": "gpcr_truebase_overclose_artifact_pressure_v14",
                    "role": "truebase_cationic_overclose_artifact_pressure",
                    "direction": "carry_forward_overclose_artifact_penalty_without_reward",
                    "rationale": "Overclose remains artifact pressure, never monotonic anchor reward.",
                },
                {
                    "feature_name": "gpcr_cationic_anchor_occupancy_support_v14",
                    "role": "rejected_reward_telemetry",
                    "direction": "diagnostic_only_not_used_as_reward_in_v15",
                    "rationale": "v14 replay preserved this as reject/rework telemetry after HTR2A decoy overpromotion.",
                },
                {
                    "feature_name": "v14_shadow_rework_preservation",
                    "role": "reject_history_preservation",
                    "direction": "diagnostic_only",
                    "rationale": "v14 is preserved as evidence that cationic-center occupancy reward is unsafe.",
                },
            ]
        )
    if variant == "gpcr_core_false_support_discriminator_shadow_v16":
        rows.extend(
            [
                {
                    "feature_name": "base_score",
                    "role": "true_base_score_anchor",
                    "direction": "preserve_true_binding_score_composite_v7_as_formula_anchor",
                    "rationale": "v16 keeps the immutable true-base score anchor and remains shadow-only.",
                },
                {
                    "feature_name": "gpcr_false_support_saturation_pressure_v16",
                    "role": "false_support_decoy_pressure",
                    "direction": "penalize_high_label_free_support_when_weakbase_support_is_absent",
                    "rationale": (
                        "v15 still leaves HTR2A decoys above the positive because label-free support can saturate "
                        "without weak-base support. This pressure is target-free and only uses cached true-base, "
                        "support, weak-support, and basic-count telemetry."
                    ),
                },
                {
                    "feature_name": "gpcr_nonbasic_truebase_noanchor_pressure_v16",
                    "role": "nonbasic_noanchor_intrusion_pressure",
                    "direction": "penalize_nonbasic_strong_truebase_rows_without_anchor_support",
                    "rationale": (
                        "Class A aminergic/opioid-like orthosteric rows without a basic center and without portable "
                        "anchor support should not dominate the frozen replay solely through true-base score."
                    ),
                },
                {
                    "feature_name": "gpcr_basic_collapse_truebase_noanchor_pressure_v16",
                    "role": "basic_collapse_noanchor_intrusion_pressure",
                    "direction": "penalize_strong_truebase_basic_rows_with_pose_collapse_and_no_support",
                    "rationale": (
                        "OPRM1 remains dominated by no-support pose-collapse decoys. v16 demotes only strong "
                        "true-base collapse rows, while weakly scored collapse positives remain blocked rather than "
                        "manually rescued."
                    ),
                },
                {
                    "feature_name": "v15_shadow_review_preservation",
                    "role": "baseline_preservation",
                    "direction": "diagnostic_only",
                    "rationale": "v15 is the current best frozen shadow and stays the comparator for v16.",
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
    elif variant == "gpcr_core_fixed_reference_live_shadow_v5":
        constraints = {
            **constraints,
            "max_abs_delta_score": 0.0,
            "yellow_band_abs_delta_score": 0.0,
            "comparison_only_candidate": True,
            "claim_locked_candidate": True,
            "shadow_only_candidate": True,
            "diagnostic_only_candidate": True,
            "fixed_reference_live_shadow_candidate": True,
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
            "reference_scaling_mode": "fixed_family_reference",
            "best_baseline_variant": "gpcr_core_family_anchor_rescore_v2",
            "rejected_predecessor_variant": "gpcr_core_acidic_anchor_overcontact_prior_gate_v4",
            "fixed_reference_v2_formula_replay_pr_auc_approx": 0.0076,
            "fixed_reference_v2_formula_replay_top20_hit_rate": 0.0,
            "diagnostic_source_artifact": "runs/gpcr_guarded_100k_rank_failure_diagnostics_current.json#post_v4_fixed_reference_redesign",
            "required_before_claim": [
                "score_only_shadow_replay_beats_v2_without_metric_regression",
                "leakage_review_no_target_label_rank_ligand_id_reference_inputs",
                "family_anchor_v2_remains_best_baseline",
                "fresh_full_100k_ci_low_top20_claim_review_green",
            ],
        }
        tuning = {
            "variant": "gpcr_core_fixed_reference_live_shadow_v5",
            "candidate_source": "post_v4_reject_fixed_reference_live_redesign",
            "rejected_predecessor_variant": "gpcr_core_acidic_anchor_overcontact_prior_gate_v4",
            "best_baseline_variant": "gpcr_core_family_anchor_rescore_v2",
            "scorer_change": "shadow_only_fixed_reference_live_linear_candidate",
            "target_identity_feature_allowed": False,
            "label_feature_allowed": False,
            "rank_feature_allowed": False,
            "ligand_id_feature_allowed": False,
            "reference_binding_value_allowed": False,
            "threshold_relaxation_allowed": False,
            "fixed_reference_scaling_required": True,
            "fixed_reference_replay_feature_collapse": {
                "rows": 40000,
                "gpcr_conserved_anchor_proxy_nonzero": 1,
                "pose_physics_support_nonzero": 1,
                "gpcr_acidic_anchor_overcontact_prior_gate_nonzero": 0,
                "target_internal_pairwise_pressure_nonzero": 17768,
                "fixed_reference_prior_weakness_pressure_nonzero": 17768,
                "gpcr_pose_chemistry_hard_decoy_pressure_nonzero": 4164,
            },
            "fixed_reference_v2_formula_replay": {
                "pr_auc_approx": 0.0076,
                "top20_hit_rate": 0.0,
                "interpretation": "do_not_port_v2_or_v4_weights_under_fixed_reference_scaling",
            },
            "replay_score_formula": (
                "binding_score_composite_v7_prior_active "
                "+ 1.25*fixed_reference_live_overreward_pressure"
            ),
        }
        interactions = [
            "fixed_family_reference_scaling_required_for_live_pressure",
            "v2_preserved_as_best_baseline",
            "post_v4_reject_shadow_only_redesign",
            "record_fixed_reference_feature_collapse",
            "use_only_fixed_reference_live_pressures",
            "no_target_identity_labels_ranks_ligand_ids_or_reference_values",
            "threshold_relaxation_forbidden",
            "shadow_only_active_claim_disabled",
            "no_router_platform_or_claim_promotion",
        ]
        next_step = (
            "Run gpcr_core_fixed_reference_live_shadow_v5 only as a score-only shadow replay under fixed-family "
            "reference scaling. Keep v2 as the baseline, treat v4 as reject evidence, and do not run a fresh full "
            "100k job or claim review from this packet."
        )
    elif variant == "gpcr_core_class_a_motif_shadow_v6":
        constraints = {
            **constraints,
            "max_abs_delta_score": 0.0,
            "yellow_band_abs_delta_score": 0.0,
            "comparison_only_candidate": True,
            "claim_locked_candidate": True,
            "shadow_only_candidate": True,
            "active_score_locked_to_base": True,
            "class_a_aminergic_opioid_orthosteric_sublane_candidate": True,
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
            "best_baseline_variant": "gpcr_core_family_anchor_rescore_v2",
            "baseline_role": "v2_donor_baseline",
            "tombstone_reject_variants": [
                "gpcr_core_acidic_anchor_overcontact_prior_gate_v4",
                "gpcr_core_fixed_reference_live_shadow_v5",
            ],
            "allowed_live_feature_families": [
                "existing_smiles_basic_amine_heuristic",
                "pose_trajectory_support_proxy",
                "prior_overreward_pressure",
                "invalid_overanchor_pressure",
            ],
            "forbidden_live_feature_families": [
                "target",
                "is_binder",
                "rank",
                "ligand_id",
                "reference_binding",
            ],
            "required_before_claim": [
                "score_only_shadow_replay_beats_v2_without_metric_regression",
                "leakage_review_no_target_is_binder_rank_ligand_id_reference_binding_inputs",
                "v2_remains_donor_baseline",
                "v4_v5_remain_tombstone_rejects",
                "fresh_full_100k_ci_low_top20_claim_review_green",
            ],
        }
        tuning = {
            "variant": "gpcr_core_class_a_motif_shadow_v6",
            "candidate_source": "post_v5_class_a_motif_shadow_design",
            "scorer_change": "shadow_only_class_a_motif_linear_candidate",
            "scope": "class_a_aminergic_opioid_like_orthosteric_sublane",
            "broad_gpcr_claim_allowed": False,
            "active_score_locked_to_base": True,
            "best_baseline_variant": "gpcr_core_family_anchor_rescore_v2",
            "baseline_role": "v2_donor_baseline",
            "tombstone_reject_variants": [
                "gpcr_core_acidic_anchor_overcontact_prior_gate_v4",
                "gpcr_core_fixed_reference_live_shadow_v5",
            ],
            "target_identity_feature_allowed": False,
            "label_feature_allowed": False,
            "rank_feature_allowed": False,
            "ligand_id_feature_allowed": False,
            "reference_binding_value_allowed": False,
            "live_feature_policy": "label_free_basic_amine_pose_trajectory_support_prior_overreward_invalid_overanchor_only",
            "replay_score_formula": (
                "binding_score_composite_v7_prior_active "
                "- 0.75*class_a_orthosteric_motif_support_proxy "
                "+ 1.10*class_a_prior_overreward_invalid_overanchor_pressure"
            ),
        }
        interactions = [
            "class_a_aminergic_opioid_like_orthosteric_sublane_not_broad_gpcr",
            "active_score_locked_to_base_even_in_apply_mode",
            "basic_amine_pose_trajectory_support_only",
            "prior_overreward_invalid_overanchor_pressure_only",
            "no_target_is_binder_rank_ligand_id_or_reference_binding_features",
            "v2_preserved_as_donor_baseline",
            "v4_v5_preserved_as_tombstone_rejects",
            "no_router_platform_or_claim_promotion",
        ]
        next_step = (
            "Run gpcr_core_class_a_motif_shadow_v6 only as score-only shadow/spec telemetry for the Class A "
            "aminergic/opioid-like orthosteric sublane. Do not launch a full 100k rerun from this packet; v2 "
            "remains the donor baseline and v4/v5 remain tombstone rejects."
        )
    elif variant == "gpcr_core_class_a_anchor_geometry_shadow_v7":
        constraints = {
            **constraints,
            "max_abs_delta_score": 0.0,
            "yellow_band_abs_delta_score": 0.0,
            "comparison_only_candidate": True,
            "claim_locked_candidate": True,
            "shadow_only_candidate": True,
            "score_only_candidate": True,
            "active_score_locked_to_base": True,
            "class_a_aminergic_opioid_orthosteric_sublane_candidate": True,
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
            "best_baseline_variant": "gpcr_core_family_anchor_rescore_v2",
            "baseline_role": "v2_donor_baseline",
            "rejected_predecessor_variant": "gpcr_core_class_a_motif_shadow_v6",
            "tombstone_reject_variants": [
                "gpcr_core_acidic_anchor_overcontact_prior_gate_v4",
                "gpcr_core_fixed_reference_live_shadow_v5",
                "gpcr_core_class_a_motif_shadow_v6",
            ],
            "allowed_live_feature_families": [
                "existing_smiles_basic_amine_heuristic",
                "stage3_pose_contact_distance_energy_proxy",
                "trajectory_survival_support_proxy",
                "invalid_anchor_prior_pressure",
            ],
            "forbidden_live_feature_families": [
                "target",
                "is_binder",
                "rank",
                "ligand_id",
                "reference_binding",
                "threshold_relaxation",
                "fake_pass",
            ],
            "required_before_claim": [
                "score_only_shadow_replay_beats_v2_without_metric_regression",
                "leakage_review_no_target_is_binder_rank_ligand_id_reference_binding_inputs",
                "v2_remains_donor_baseline",
                "v4_v5_v6_remain_reject_history",
                "fresh_full_100k_ci_low_top20_claim_review_green",
            ],
        }
        tuning = {
            "variant": "gpcr_core_class_a_anchor_geometry_shadow_v7",
            "candidate_source": "post_v6_reject_class_a_anchor_geometry_shadow_design",
            "scorer_change": "score_only_shadow_class_a_anchor_geometry_linear_candidate",
            "scope": "class_a_aminergic_opioid_like_orthosteric_sublane",
            "broad_gpcr_claim_allowed": False,
            "active_score_locked_to_base": True,
            "best_baseline_variant": "gpcr_core_family_anchor_rescore_v2",
            "baseline_role": "v2_donor_baseline",
            "rejected_predecessor_variant": "gpcr_core_class_a_motif_shadow_v6",
            "tombstone_reject_variants": [
                "gpcr_core_acidic_anchor_overcontact_prior_gate_v4",
                "gpcr_core_fixed_reference_live_shadow_v5",
                "gpcr_core_class_a_motif_shadow_v6",
            ],
            "target_identity_feature_allowed": False,
            "label_feature_allowed": False,
            "rank_feature_allowed": False,
            "ligand_id_feature_allowed": False,
            "reference_binding_value_allowed": False,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
            "live_feature_policy": (
                "label_free_target_free_basic_amine_stage3_pose_trajectory_contact_energy_anchor_geometry_only"
            ),
            "replay_score_formula": (
                "binding_score_composite_v7_prior_active "
                "- 0.55*class_a_charge_complemented_anchor_geometry_proxy "
                "- 0.35*class_a_orthosteric_occupancy_proxy "
                "- 0.45*class_a_pose_survival_support_proxy "
                "+ 1.20*class_a_invalid_anchor_prior_pressure_v7"
            ),
        }
        interactions = [
            "class_a_aminergic_opioid_like_orthosteric_sublane_not_broad_gpcr",
            "active_score_locked_to_base_even_in_apply_mode",
            "score_only_shadow_candidate",
            "charge_complemented_anchor_geometry_support_only",
            "orthosteric_occupancy_and_pose_survival_support_only",
            "invalid_anchor_prior_pressure_only",
            "no_target_is_binder_rank_ligand_id_reference_binding_threshold_relaxation_or_fake_pass_features",
            "v2_preserved_as_donor_baseline",
            "v4_v5_v6_preserved_as_reject_history",
            "v6_reject_preserved_not_promoted",
            "no_router_platform_or_claim_promotion",
        ]
        next_step = (
            "Run gpcr_core_class_a_anchor_geometry_shadow_v7 only as score-only shadow/spec telemetry for the "
            "Class A aminergic/opioid-like orthosteric sublane. Keep v2 as the donor baseline and preserve "
            "v4/v5/v6 as reject history; do not use this packet for broad GPCR claims."
        )
    elif variant == "gpcr_core_direct_atom_anchor_window_shadow_v8":
        constraints = {
            **constraints,
            "max_abs_delta_score": 0.0,
            "yellow_band_abs_delta_score": 0.0,
            "comparison_only_candidate": True,
            "claim_locked_candidate": True,
            "shadow_only_candidate": True,
            "score_only_candidate": True,
            "active_score_locked_to_base": True,
            "class_a_aminergic_opioid_orthosteric_sublane_candidate": True,
            "requires_precomputed_atom_window_features": True,
            "missing_atom_window_features_are_not_negative_evidence": True,
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
            "best_baseline_variant": "gpcr_core_family_anchor_rescore_v2",
            "baseline_role": "frozen_r2_v2_matching_label_comparator",
            "rejected_predecessor_variant": "gpcr_core_class_a_anchor_geometry_shadow_v7",
            "tombstone_reject_variants": [
                "gpcr_core_acidic_anchor_overcontact_prior_gate_v4",
                "gpcr_core_fixed_reference_live_shadow_v5",
                "gpcr_core_class_a_motif_shadow_v6",
                "gpcr_core_class_a_anchor_geometry_shadow_v7",
            ],
            "allowed_live_feature_families": [
                "precomputed_native_acidic_anchor_distance_window_features",
                "existing_smiles_basic_amine_heuristic",
                "ligand_logp_and_polarity_hydrophobic_pressure",
                "existing_pose_survival_proxy",
            ],
            "forbidden_live_feature_families": [
                "target",
                "is_binder",
                "rank",
                "ligand_id",
                "reference_binding",
                "threshold_relaxation",
                "fake_pass",
            ],
            "required_before_claim": [
                "atom_window_feature_cache_materialized",
                "score_only_shadow_replay_beats_frozen_r2_v2_without_metric_regression",
                "leakage_review_no_target_is_binder_rank_ligand_id_reference_binding_inputs",
                "v7_remains_reject_history",
                "fresh_full_100k_ci_low_top20_claim_review_green",
            ],
        }
        tuning = {
            "variant": "gpcr_core_direct_atom_anchor_window_shadow_v8",
            "candidate_source": "post_v7_reject_direct_atom_window_design",
            "scorer_change": "score_only_shadow_direct_atom_window_linear_candidate",
            "scope": "class_a_aminergic_opioid_like_orthosteric_sublane",
            "broad_gpcr_claim_allowed": False,
            "active_score_locked_to_base": True,
            "best_baseline_variant": "gpcr_core_family_anchor_rescore_v2",
            "baseline_role": "frozen_r2_v2_matching_label_comparator",
            "rejected_predecessor_variant": "gpcr_core_class_a_anchor_geometry_shadow_v7",
            "target_identity_feature_allowed": False,
            "label_feature_allowed": False,
            "rank_feature_allowed": False,
            "ligand_id_feature_allowed": False,
            "reference_binding_value_allowed": False,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
            "atom_anchor_window_A": [2.8, 4.2],
            "overcontact_distance_A": 2.8,
            "live_feature_policy": (
                "label_free_precomputed_atom_window_features_plus_smiles_hydrophobic_pressure_only"
            ),
            "replay_score_formula": (
                "binding_score_composite_v7_prior_active "
                "- 0.75*class_a_direct_atom_window_anchor_geometry_proxy "
                "- 0.20*class_a_atom_window_pose_survival_proxy "
                "+ 1.35*class_a_hydrophobic_overcontact_pressure_v8"
            ),
        }
        interactions = [
            "direct_atom_window_features_not_stage3_proxy_recombination",
            "class_a_aminergic_opioid_like_orthosteric_sublane_not_broad_gpcr",
            "active_score_locked_to_base_even_in_apply_mode",
            "missing_atom_window_features_are_telemetry_not_negative_evidence",
            "hydrophobic_overcontact_penalty_without_target_or_label_inputs",
            "no_target_is_binder_rank_ligand_id_reference_binding_threshold_relaxation_or_fake_pass_features",
            "v2_frozen_r2_matching_label_comparator_preserved",
            "v7_preserved_as_reject_history",
            "no_router_platform_or_claim_promotion",
        ]
        next_step = (
            "Materialize atom-window anchor features into a local cache, then run "
            "gpcr_core_direct_atom_anchor_window_shadow_v8 only as score-only shadow/spec telemetry. "
            "Do not launch guarded apply or broad GPCR claims from this packet."
        )
    elif variant == "gpcr_core_atom_window_excess_polar_shadow_v9":
        constraints = {
            **constraints,
            "max_abs_delta_score": 0.0,
            "yellow_band_abs_delta_score": 0.0,
            "comparison_only_candidate": True,
            "claim_locked_candidate": True,
            "shadow_only_candidate": True,
            "score_only_candidate": True,
            "active_score_locked_to_base": True,
            "class_a_aminergic_opioid_orthosteric_sublane_candidate": True,
            "requires_precomputed_atom_window_features": True,
            "missing_atom_window_features_are_not_negative_evidence": True,
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
            "best_baseline_variant": "gpcr_core_family_anchor_rescore_v2",
            "baseline_role": "frozen_r2_v2_matching_label_comparator",
            "rejected_predecessor_variant": "gpcr_core_direct_atom_anchor_window_shadow_v8",
            "tombstone_reject_variants": [
                "gpcr_core_acidic_anchor_overcontact_prior_gate_v4",
                "gpcr_core_fixed_reference_live_shadow_v5",
                "gpcr_core_class_a_motif_shadow_v6",
                "gpcr_core_class_a_anchor_geometry_shadow_v7",
                "gpcr_core_direct_atom_anchor_window_shadow_v8",
            ],
            "allowed_live_feature_families": [
                "precomputed_native_acidic_anchor_distance_window_features",
                "existing_smiles_basic_amine_heuristic",
                "ligand_h_donor_acceptor_rotatable_bond_counts",
                "ligand_logp_and_polarity_hydrophobic_pressure",
                "existing_pose_survival_proxy",
            ],
            "forbidden_live_feature_families": [
                "target",
                "is_binder",
                "rank",
                "ligand_id",
                "reference_binding",
                "threshold_relaxation",
                "fake_pass",
            ],
            "required_before_claim": [
                "atom_window_feature_cache_materialized_with_positive_labels",
                "base_anchored_score_only_shadow_replay_beats_frozen_r2_v2_without_metric_regression",
                "excess_polar_pressure_reduces_drd2_decoy_intrusion_without_top20_regression",
                "leakage_review_no_target_is_binder_rank_ligand_id_reference_binding_inputs",
                "fresh_full_100k_ci_low_top20_claim_review_green",
            ],
        }
        tuning = {
            "variant": "gpcr_core_atom_window_excess_polar_shadow_v9",
            "candidate_source": "post_v8_reject_multipolar_decoy_pressure_design",
            "scorer_change": "score_only_shadow_atom_window_excess_polar_linear_candidate",
            "scope": "class_a_aminergic_opioid_like_orthosteric_sublane",
            "broad_gpcr_claim_allowed": False,
            "active_score_locked_to_base": True,
            "best_baseline_variant": "gpcr_core_family_anchor_rescore_v2",
            "baseline_role": "frozen_r2_v2_matching_label_comparator",
            "rejected_predecessor_variant": "gpcr_core_direct_atom_anchor_window_shadow_v8",
            "target_identity_feature_allowed": False,
            "label_feature_allowed": False,
            "rank_feature_allowed": False,
            "ligand_id_feature_allowed": False,
            "reference_binding_value_allowed": False,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
            "atom_anchor_window_A": [2.8, 4.2],
            "overcontact_distance_A": 2.8,
            "excess_polar_pressure_basis": ["ligand_h_donors", "ligand_h_acceptors", "ligand_rot_bonds"],
            "live_feature_policy": (
                "label_free_precomputed_atom_window_features_plus_smiles_and_ligand_count_pressure_only"
            ),
            "replay_score_formula": (
                "binding_score_composite_v7_prior_active "
                "- 0.55*class_a_direct_atom_window_anchor_geometry_proxy "
                "- 0.15*class_a_atom_window_pose_survival_proxy "
                "- 0.20*class_a_compact_amine_window_support_v9 "
                "+ 1.35*class_a_hydrophobic_overcontact_pressure_v8 "
                "+ 2.75*class_a_excess_polar_anchor_pressure_v9"
            ),
        }
        interactions = [
            "direct_atom_window_features_not_stage3_proxy_recombination",
            "excess_polar_pressure_targets_v8_multipolar_decoy_intrusion",
            "class_a_aminergic_opioid_like_orthosteric_sublane_not_broad_gpcr",
            "active_score_locked_to_base_even_in_apply_mode",
            "missing_atom_window_features_are_telemetry_not_negative_evidence",
            "no_target_is_binder_rank_ligand_id_reference_binding_threshold_relaxation_or_fake_pass_features",
            "v2_frozen_r2_matching_label_comparator_preserved",
            "v8_preserved_as_reject_history",
            "no_router_platform_or_claim_promotion",
        ]
        next_step = (
            "Run gpcr_core_atom_window_excess_polar_shadow_v9 as a base-anchored, score-only shadow replay. "
            "It may only become a guarded candidate if it beats the frozen-r2 v2 comparator without Top20 or "
            "CI-low regression."
        )
    elif variant == "gpcr_core_cationic_pose_distortion_shadow_v10":
        constraints = {
            **constraints,
            "max_abs_delta_score": 0.0,
            "yellow_band_abs_delta_score": 0.0,
            "comparison_only_candidate": True,
            "claim_locked_candidate": True,
            "shadow_only_candidate": True,
            "score_only_candidate": True,
            "selected_repaired_slice_candidate": True,
            "active_score_locked_to_base": True,
            "class_a_aminergic_opioid_orthosteric_sublane_candidate": True,
            "requires_precomputed_drd2_repair_slice_features": True,
            "requires_precomputed_atom_window_features": True,
            "requires_precomputed_cationic_center_features": True,
            "missing_repair_slice_features_are_not_negative_evidence": True,
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
            "best_baseline_variant": "gpcr_core_family_anchor_rescore_v2",
            "baseline_role": "frozen_r2_v2_matching_label_comparator",
            "candidate_source_artifact": "runs/gpcr_drd2_hard_decoy_penalty_envelope_current.json",
            "rejected_predecessor_variant": "gpcr_core_atom_window_excess_polar_shadow_v9",
            "tombstone_reject_variants": [
                "gpcr_core_acidic_anchor_overcontact_prior_gate_v4",
                "gpcr_core_fixed_reference_live_shadow_v5",
                "gpcr_core_class_a_motif_shadow_v6",
                "gpcr_core_class_a_anchor_geometry_shadow_v7",
                "gpcr_core_direct_atom_anchor_window_shadow_v8",
                "gpcr_core_atom_window_excess_polar_shadow_v9",
            ],
            "allowed_live_feature_families": [
                "selected_repaired_drd2_slice_base_score",
                "precomputed_atom_window_features",
                "precomputed_cationic_center_features",
                "label_free_pose_distortion_pressure",
                "label_free_anchor_support_pressure",
            ],
            "forbidden_live_feature_families": [
                "target",
                "is_binder",
                "rank",
                "ligand_id",
                "reference_binding",
                "threshold_relaxation",
                "fake_pass",
            ],
            "required_before_claim": [
                "materialize_equivalent_feature_cache_without_labels_for_frozen_non_adrb2_rows",
                "selected_slice_shadow_replay_green_is_not_sufficient_for_claim",
                "leakage_review_no_target_is_binder_rank_ligand_id_reference_binding_inputs",
                "v8_v9_remain_reject_history",
                "fresh_full_100k_ci_low_top20_claim_review_green",
                "family_held_out_scorecard_green",
            ],
        }
        tuning = {
            "variant": "gpcr_core_cationic_pose_distortion_shadow_v10",
            "candidate_source": "drd2_hard_decoy_penalty_envelope_current",
            "scorer_change": "selected_repaired_slice_score_only_shadow_candidate",
            "scope": "class_a_aminergic_opioid_like_orthosteric_sublane",
            "broad_gpcr_claim_allowed": False,
            "active_score_locked_to_base": True,
            "best_baseline_variant": "gpcr_core_family_anchor_rescore_v2",
            "baseline_role": "frozen_r2_v2_matching_label_comparator",
            "rejected_predecessor_variant": "gpcr_core_atom_window_excess_polar_shadow_v9",
            "target_identity_feature_allowed": False,
            "label_feature_allowed": False,
            "rank_feature_allowed": False,
            "ligand_id_feature_allowed": False,
            "reference_binding_value_allowed": False,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
            "penalty_weight": 6.0,
            "support_weight": 16.0,
            "bounded_envelope_positive_rank": 1,
            "bounded_envelope_decoys_above_positive_count": 0,
            "bounded_envelope_valid_anchor_challenge_above_positive_count": 0,
            "live_feature_policy": (
                "selected_slice_precomputed_label_free_cationic_center_pose_distortion_pressures_only"
            ),
            "replay_score_formula": (
                "base_score "
                "+ 6.0*label_free_penalty_pressure "
                "- 16.0*label_free_support_pressure"
            ),
        }
        interactions = [
            "selected_repaired_drd2_slice_only_not_full_gpcr_claim",
            "cationic_center_geometry_uses_closest_basic_amine_not_target_identity",
            "pose_distortion_pressure_is_label_free_and_precomputed",
            "active_score_locked_to_base_even_in_apply_mode",
            "missing_repair_slice_features_are_telemetry_not_negative_evidence",
            "no_target_is_binder_rank_ligand_id_reference_binding_threshold_relaxation_or_fake_pass_features",
            "v2_frozen_r2_matching_label_comparator_preserved",
            "v8_v9_preserved_as_reject_history",
            "no_router_platform_or_claim_promotion",
        ]
        next_step = (
            "Replay gpcr_core_cationic_pose_distortion_shadow_v10 on the repaired DRD2 hard-decoy slice only. "
            "If the selected slice remains green, build an equivalent label-free feature cache for frozen "
            "non-ADRB2 rows before any guarded 100k rerun or claim discussion."
        )
    elif variant == "gpcr_core_cationic_weakbase_rescue_shadow_v11":
        constraints = {
            **constraints,
            "max_abs_delta_score": 0.0,
            "yellow_band_abs_delta_score": 0.0,
            "comparison_only_candidate": True,
            "claim_locked_candidate": True,
            "shadow_only_candidate": True,
            "score_only_candidate": True,
            "selected_repaired_slice_candidate": True,
            "active_score_locked_to_base": True,
            "class_a_aminergic_opioid_orthosteric_sublane_candidate": True,
            "requires_precomputed_drd2_repair_slice_features": True,
            "requires_precomputed_frozen_row_v10_features": True,
            "requires_weak_base_rescue_gate": True,
            "missing_repair_slice_features_are_not_negative_evidence": True,
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
            "best_baseline_variant": "gpcr_core_family_anchor_rescore_v2",
            "baseline_role": "frozen_r2_v2_matching_label_comparator",
            "candidate_source_artifact": "runs/gpcr_cationic_pose_distortion_frozen_cache_mode_review_current.json",
            "rejected_predecessor_variant": "gpcr_core_cationic_pose_distortion_shadow_v10",
            "tombstone_reject_variants": [
                "gpcr_core_acidic_anchor_overcontact_prior_gate_v4",
                "gpcr_core_fixed_reference_live_shadow_v5",
                "gpcr_core_class_a_motif_shadow_v6",
                "gpcr_core_class_a_anchor_geometry_shadow_v7",
                "gpcr_core_direct_atom_anchor_window_shadow_v8",
                "gpcr_core_atom_window_excess_polar_shadow_v9",
                "gpcr_core_cationic_pose_distortion_shadow_v10",
            ],
            "allowed_live_feature_families": [
                "selected_repaired_drd2_slice_base_score",
                "precomputed_cationic_center_features",
                "label_free_pose_distortion_pressure",
                "label_free_anchor_support_pressure",
                "weak_base_score_conditioning",
            ],
            "forbidden_live_feature_families": [
                "target",
                "is_binder",
                "rank",
                "ligand_id",
                "reference_binding",
                "threshold_relaxation",
                "fake_pass",
            ],
            "required_before_claim": [
                "complete_frozen_row_feature_cache_without_labels",
                "weak_base_rescue_shadow_replay_beats_frozen_r2_v2_without_top20_regression",
                "leakage_review_no_target_is_binder_rank_ligand_id_reference_binding_inputs",
                "fresh_full_100k_ci_low_top20_claim_review_green",
                "family_held_out_scorecard_green",
            ],
        }
        tuning = {
            "variant": "gpcr_core_cationic_weakbase_rescue_shadow_v11",
            "candidate_source": "v10_frozen_cache_mode_review_allbasic_decoy_overpromotion",
            "scorer_change": "weak_base_conditional_cationic_pose_rescue_shadow_candidate",
            "scope": "class_a_aminergic_opioid_like_orthosteric_sublane",
            "broad_gpcr_claim_allowed": False,
            "active_score_locked_to_base": True,
            "best_baseline_variant": "gpcr_core_family_anchor_rescore_v2",
            "baseline_role": "frozen_r2_v2_matching_label_comparator",
            "rejected_predecessor_variant": "gpcr_core_cationic_pose_distortion_shadow_v10",
            "target_identity_feature_allowed": False,
            "label_feature_allowed": False,
            "rank_feature_allowed": False,
            "ligand_id_feature_allowed": False,
            "reference_binding_value_allowed": False,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
            "penalty_weight": 6.0,
            "weak_base_support_weight": 18.0,
            "weak_base_gate_formula": "clip((base_score + 6.0) / 6.0, 0.0, 1.0)",
            "live_feature_policy": "label_free_precomputed_cationic_pose_pressures_plus_base_score_conditioning_only",
            "replay_score_formula": (
                "base_score "
                "+ 6.0*label_free_penalty_pressure "
                "- 18.0*weak_base_rescue_support_pressure"
            ),
        }
        interactions = [
            "weak_base_support_rescues_borderline_rows_not_already_strong_decoys",
            "selected_repaired_drd2_slice_only_not_full_gpcr_claim",
            "cationic_center_geometry_uses_closest_basic_amine_not_target_identity",
            "pose_distortion_pressure_is_label_free_and_precomputed",
            "active_score_locked_to_base_even_in_apply_mode",
            "no_target_is_binder_rank_ligand_id_reference_binding_threshold_relaxation_or_fake_pass_features",
            "v2_frozen_r2_matching_label_comparator_preserved",
            "v10_preserved_as_selected_slice_rework_history",
            "no_router_platform_or_claim_promotion",
        ]
        next_step = (
            "Replay gpcr_core_cationic_weakbase_rescue_shadow_v11 on the repaired DRD2 slice and frozen-row "
            "partial caches. Only if it avoids all-basic decoy overpromotion should a complete frozen-row cache and "
            "guarded 100k candidate be considered."
        )
    elif variant == "gpcr_core_synthetic_anchor_penalty_shadow_v12":
        constraints = {
            **constraints,
            "max_abs_delta_score": 0.0,
            "yellow_band_abs_delta_score": 0.0,
            "comparison_only_candidate": True,
            "claim_locked_candidate": True,
            "shadow_only_candidate": True,
            "score_only_candidate": True,
            "active_score_locked_to_base": True,
            "class_a_aminergic_opioid_orthosteric_sublane_candidate": True,
            "requires_precomputed_frozen_row_v10_features": True,
            "requires_true_base_score_cache": True,
            "requires_synthetic_anchor_saturation_pressure": True,
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
            "best_baseline_variant": "gpcr_core_cationic_weakbase_rescue_shadow_v11",
            "baseline_role": "complete_true_base_frozen_v11_blocked_comparator",
            "candidate_source_artifact": "runs/gpcr_cationic_weakbase_v11_frozen_shadow_replay_review_current.json",
            "rejected_predecessor_variant": "gpcr_core_cationic_weakbase_rescue_shadow_v11",
            "allowed_live_feature_families": [
                "true_base_score",
                "precomputed_cationic_center_features",
                "label_free_pose_distortion_pressure",
                "label_free_anchor_support_pressure",
                "weak_base_score_conditioning",
                "synthetic_anchor_saturation_pressure",
                "moderate_multi_basic_support_window",
            ],
            "forbidden_live_feature_families": [
                "target",
                "is_binder",
                "rank",
                "ligand_id",
                "reference_binding",
                "threshold_relaxation",
                "fake_pass",
            ],
            "required_before_claim": [
                "v12_shadow_replay_top20_positive_count_above_zero_without_family_collapse",
                "leakage_review_no_target_is_binder_rank_ligand_id_reference_binding_inputs",
                "fresh_full_100k_ci_low_top20_claim_review_green",
                "family_held_out_scorecard_green",
            ],
        }
        tuning = {
            "variant": "gpcr_core_synthetic_anchor_penalty_shadow_v12",
            "candidate_source": "v11_full_true_base_frozen_replay_allbasic_overpromotion",
            "scorer_change": "penalize_saturated_all_basic_support_reward_moderate_multi_basic_support",
            "scope": "class_a_aminergic_opioid_like_orthosteric_sublane",
            "broad_gpcr_claim_allowed": False,
            "active_score_locked_to_base": True,
            "best_baseline_variant": "gpcr_core_cationic_weakbase_rescue_shadow_v11",
            "baseline_role": "complete_true_base_frozen_v11_blocked_comparator",
            "rejected_predecessor_variant": "gpcr_core_cationic_weakbase_rescue_shadow_v11",
            "target_identity_feature_allowed": False,
            "label_feature_allowed": False,
            "rank_feature_allowed": False,
            "ligand_id_feature_allowed": False,
            "reference_binding_value_allowed": False,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
            "penalty_weight": 4.0,
            "synthetic_anchor_saturation_penalty_weight": 8.0,
            "moderate_multi_basic_support_weight": 20.0,
            "synthetic_anchor_saturation_formula": "clip((label_free_support_pressure - 0.90) / 0.08, 0.0, 1.0) behind all_basic",
            "moderate_support_formula": (
                "weak_base_rescue_support_pressure * window(0.35..0.86 support) * multi_basic_gate * "
                "pose_preservation_gate"
            ),
            "live_feature_policy": "true_base_score_plus_label_free_saturation_penalty_and_moderate_support_only",
            "replay_score_formula": (
                "base_score "
                "+ 4.0*label_free_penalty_pressure "
                "+ 8.0*gpcr_synthetic_anchor_saturation_pressure_v12 "
                "- 20.0*gpcr_moderate_multi_basic_weakbase_support_v12"
            ),
        }
        interactions = [
            "full_true_base_frozen_v11_blocker_preserved",
            "saturated_all_basic_anchor_support_is_penalty_not_reward",
            "moderate_multi_basic_support_is_rewarded_only_with_pose_preservation",
            "active_score_locked_to_base_even_in_apply_mode",
            "no_target_is_binder_rank_ligand_id_reference_binding_threshold_relaxation_or_fake_pass_features",
            "no_router_platform_or_claim_promotion",
        ]
        next_step = (
            "Replay gpcr_core_synthetic_anchor_penalty_shadow_v12 on the complete true-base frozen cationic cache. "
            "It can only remain a claim-locked shadow candidate unless top20, CI-low, family-held-out, and leakage "
            "reviews are all green."
        )
    elif variant == "gpcr_core_pose_support_gap_shadow_v13":
        constraints = {
            **constraints,
            "max_abs_delta_score": 0.0,
            "yellow_band_abs_delta_score": 0.0,
            "comparison_only_candidate": True,
            "claim_locked_candidate": True,
            "shadow_only_candidate": True,
            "score_only_candidate": True,
            "active_score_locked_to_base": True,
            "class_a_aminergic_opioid_orthosteric_sublane_candidate": True,
            "requires_precomputed_frozen_row_v10_features": True,
            "requires_true_base_score_cache": True,
            "requires_v12_gap_packet_review": True,
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
            "best_baseline_variant": "gpcr_core_synthetic_anchor_penalty_shadow_v12",
            "baseline_role": "v12_drd2_recovery_family_blocked_comparator",
            "candidate_source_artifact": "runs/gpcr_frozen_pose_support_gap_packet_current.json",
            "blocked_v12_targets": ["CHEMBL224_HTR2A_HUMAN", "CHEMBL233_OPRM1_HUMAN"],
            "allowed_live_feature_families": [
                "true_base_score",
                "label_free_pose_distortion_pressure",
                "synthetic_anchor_saturation_pressure",
                "moderate_multi_basic_support_window",
                "unsupported_strong_base_score_pressure",
                "pose_gap_strong_base_score_pressure",
                "multipolar_basic_pressure",
            ],
            "forbidden_live_feature_families": [
                "target",
                "is_binder",
                "rank",
                "ligand_id",
                "reference_binding",
                "threshold_relaxation",
                "fake_pass",
            ],
            "required_before_claim": [
                "v13_shadow_replay_improves_htr2a_oprm1_without_drd2_regression",
                "leakage_review_no_target_is_binder_rank_ligand_id_reference_binding_inputs",
                "fresh_full_100k_ci_low_top20_claim_review_green",
                "family_held_out_scorecard_green",
            ],
        }
        tuning = {
            "variant": "gpcr_core_pose_support_gap_shadow_v13",
            "candidate_source": "v12_frozen_pose_support_gap_packet",
            "scorer_change": "penalize_unsupported_strong_base_score_and_pose_gap_intrusion",
            "scope": "class_a_aminergic_opioid_like_orthosteric_sublane",
            "broad_gpcr_claim_allowed": False,
            "active_score_locked_to_base": True,
            "best_baseline_variant": "gpcr_core_synthetic_anchor_penalty_shadow_v12",
            "baseline_role": "v12_drd2_recovery_family_blocked_comparator",
            "target_identity_feature_allowed": False,
            "label_feature_allowed": False,
            "rank_feature_allowed": False,
            "ligand_id_feature_allowed": False,
            "reference_binding_value_allowed": False,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
            "penalty_weight": 4.0,
            "synthetic_anchor_saturation_penalty_weight": 8.0,
            "moderate_multi_basic_support_weight": 20.0,
            "unsupported_strong_base_pressure_weight": 28.0,
            "pose_gap_strong_base_pressure_weight": 12.0,
            "multipolar_basic_pressure_weight": 4.0,
            "unsupported_strong_base_formula": "clip((-6.0 - base_score) / 2.0, 0.0, inf) * no_support_gate",
            "pose_gap_strong_base_formula": "clip((-6.0 - base_score) / 2.0, 0.0, inf) * pose_gap_gate",
            "live_feature_policy": "true_base_score_plus_label_free_support_gap_pressures_only",
            "replay_score_formula": (
                "base_score "
                "+ 4.0*label_free_penalty_pressure "
                "+ 8.0*gpcr_synthetic_anchor_saturation_pressure_v12 "
                "- 20.0*gpcr_moderate_multi_basic_weakbase_support_v12 "
                "+ 28.0*gpcr_unsupported_strong_base_pressure_v13 "
                "+ 12.0*gpcr_pose_gap_strong_base_pressure_v13 "
                "+ 4.0*multipolar_basic_pressure"
            ),
        }
        interactions = [
            "v12_drd2_recovery_preserved",
            "unsupported_strong_base_score_is_decoy_intrusion_pressure",
            "pose_gap_pressure_is_gated_by_strong_base_score",
            "multipolar_basic_pressure_carryover_for_htr2a_oprm1",
            "active_score_locked_to_base_even_in_apply_mode",
            "no_target_is_binder_rank_ligand_id_reference_binding_threshold_relaxation_or_fake_pass_features",
            "no_router_platform_or_claim_promotion",
        ]
        next_step = (
            "Replay gpcr_core_pose_support_gap_shadow_v13 on the complete true-base frozen cationic cache. "
            "Treat it as v13 planning evidence only: it must improve HTR2A/OPRM1 without DRD2 regression and "
            "still requires full 100k CI-low/top20 review before any claim discussion."
        )
    elif variant == "gpcr_core_truebase_anchor_occupancy_shadow_v14":
        constraints = {
            **constraints,
            "max_abs_delta_score": 0.0,
            "yellow_band_abs_delta_score": 0.0,
            "comparison_only_candidate": True,
            "claim_locked_candidate": True,
            "shadow_only_candidate": True,
            "score_only_candidate": True,
            "active_score_locked_to_base": True,
            "class_a_aminergic_opioid_orthosteric_sublane_candidate": True,
            "requires_precomputed_frozen_row_v10_features": True,
            "requires_true_base_score_cache": True,
            "requires_v13_gap_packet_review": True,
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
            "best_baseline_variant": "gpcr_core_pose_support_gap_shadow_v13",
            "baseline_role": "v13_drd2_htr2a_direction_oprm1_blocked_comparator",
            "candidate_source_artifact": "runs/gpcr_pose_support_gap_v13_frozen_gap_packet_current.json",
            "blocked_v13_targets": ["CHEMBL224_HTR2A_HUMAN", "CHEMBL233_OPRM1_HUMAN"],
            "allowed_live_feature_families": [
                "cached_true_base_score",
                "label_free_pose_distortion_pressure",
                "synthetic_anchor_saturation_pressure",
                "moderate_multi_basic_support_window",
                "cationic_center_occupancy_support",
                "truebase_unsupported_strong_base_pressure",
                "truebase_pose_gap_pressure",
                "truebase_backmapping_collapse_pressure",
                "truebase_cationic_overclose_artifact_pressure",
                "multipolar_basic_pressure",
            ],
            "forbidden_live_feature_families": [
                "target",
                "is_binder",
                "rank",
                "ligand_id",
                "reference_binding",
                "threshold_relaxation",
                "fake_pass",
            ],
            "required_before_claim": [
                "v14_shadow_replay_improves_htr2a_oprm1_without_drd2_regression",
                "leakage_review_no_target_is_binder_rank_ligand_id_reference_binding_inputs",
                "fresh_full_100k_ci_low_top20_claim_review_green",
                "family_held_out_scorecard_green",
            ],
        }
        tuning = {
            "variant": "gpcr_core_truebase_anchor_occupancy_shadow_v14",
            "candidate_source": "v13_frozen_pose_support_gap_packet",
            "scorer_change": "use_cached_true_base_gap_pressure_and_cationic_center_occupancy_support",
            "scope": "class_a_aminergic_opioid_like_orthosteric_sublane",
            "broad_gpcr_claim_allowed": False,
            "active_score_locked_to_base": True,
            "best_baseline_variant": "gpcr_core_pose_support_gap_shadow_v13",
            "baseline_role": "v13_drd2_htr2a_direction_oprm1_blocked_comparator",
            "target_identity_feature_allowed": False,
            "label_feature_allowed": False,
            "rank_feature_allowed": False,
            "ligand_id_feature_allowed": False,
            "reference_binding_value_allowed": False,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
            "penalty_weight": 4.0,
            "synthetic_anchor_saturation_penalty_weight": 8.0,
            "moderate_multi_basic_support_weight": 20.0,
            "truebase_unsupported_strong_base_pressure_weight": 28.0,
            "truebase_pose_gap_pressure_weight": 12.0,
            "truebase_backmapping_collapse_pressure_weight": 8.0,
            "truebase_overclose_artifact_pressure_weight": 10.0,
            "cationic_anchor_occupancy_support_weight": 8.0,
            "multipolar_basic_pressure_weight": 4.0,
            "truebase_formula": "coalesce(cached base_score, binding_score_composite_v7)",
            "cationic_anchor_occupancy_formula": (
                "basic_gate * cationic_center_window_fraction * (1 - cationic_center_too_close_fraction) * "
                "pose_preservation_support"
            ),
            "truebase_unsupported_formula": "clip((-6.0 - true_base_score) / 2.0, 0.0, inf) * no_support_gate_v14",
            "truebase_pose_gap_formula": "clip((-6.0 - true_base_score) / 2.0, 0.0, inf) * pose_gap_gate",
            "live_feature_policy": "cached_true_base_score_plus_label_free_cationic_occupancy_and_pose_gap_pressures_only",
            "replay_score_formula": (
                "base_score "
                "+ 4.0*label_free_penalty_pressure "
                "+ 8.0*gpcr_synthetic_anchor_saturation_pressure_v12 "
                "- 20.0*gpcr_moderate_multi_basic_weakbase_support_v12 "
                "+ 28.0*gpcr_truebase_unsupported_strong_base_pressure_v14 "
                "+ 12.0*gpcr_truebase_pose_gap_pressure_v14 "
                "+ 8.0*gpcr_truebase_backmapping_collapse_pressure_v14 "
                "+ 10.0*gpcr_truebase_overclose_artifact_pressure_v14 "
                "- 8.0*gpcr_cationic_anchor_occupancy_support_v14 "
                "+ 4.0*multipolar_basic_pressure"
            ),
        }
        interactions = [
            "v13_drd2_recovery_preserved_as_comparator",
            "cached_true_base_score_is_used_for_gap_pressure",
            "cationic_center_window_is_support_only_with_pose_survival",
            "strong_truebase_unsupported_rows_are_demoted_without_label_or_target_features",
            "active_score_locked_to_base_even_in_apply_mode",
            "no_target_is_binder_rank_ligand_id_reference_binding_threshold_relaxation_or_fake_pass_features",
            "no_router_platform_or_claim_promotion",
        ]
        next_step = (
            "Replay gpcr_core_truebase_anchor_occupancy_shadow_v14 on the complete true-base frozen cationic cache. "
            "Keep it claim-locked unless it improves HTR2A/OPRM1 without DRD2 regression and later passes full "
            "100k CI-low/top20 plus family-held-out reviews."
        )
    elif variant == "gpcr_core_truebase_gap_penalty_shadow_v15":
        constraints = {
            **constraints,
            "max_abs_delta_score": 0.0,
            "yellow_band_abs_delta_score": 0.0,
            "comparison_only_candidate": True,
            "claim_locked_candidate": True,
            "shadow_only_candidate": True,
            "score_only_candidate": True,
            "active_score_locked_to_base": True,
            "class_a_aminergic_opioid_orthosteric_sublane_candidate": True,
            "requires_precomputed_frozen_row_v10_features": True,
            "requires_true_base_score_cache": True,
            "requires_v14_rework_review": True,
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
            "best_baseline_variant": "gpcr_core_pose_support_gap_shadow_v13",
            "rejected_predecessor_variant": "gpcr_core_truebase_anchor_occupancy_shadow_v14",
            "baseline_role": "v13_support_gap_comparator_v14_reward_rework",
            "candidate_source_artifact": "runs/gpcr_truebase_anchor_occupancy_v14_frozen_gap_packet_current.json",
            "blocked_v14_targets": ["CHEMBL224_HTR2A_HUMAN", "CHEMBL233_OPRM1_HUMAN"],
            "allowed_live_feature_families": [
                "cached_true_base_score",
                "label_free_pose_distortion_pressure",
                "synthetic_anchor_saturation_pressure",
                "moderate_multi_basic_support_window",
                "truebase_unsupported_strong_base_pressure",
                "truebase_pose_gap_pressure",
                "truebase_backmapping_collapse_pressure",
                "truebase_cationic_overclose_artifact_pressure",
                "multipolar_basic_pressure",
            ],
            "forbidden_live_feature_families": [
                "target",
                "is_binder",
                "rank",
                "ligand_id",
                "reference_binding",
                "threshold_relaxation",
                "fake_pass",
                "cationic_anchor_occupancy_reward",
            ],
            "required_before_claim": [
                "v15_shadow_replay_improves_htr2a_oprm1_without_drd2_regression",
                "leakage_review_no_target_is_binder_rank_ligand_id_reference_binding_inputs",
                "fresh_full_100k_ci_low_top20_claim_review_green",
                "family_held_out_scorecard_green",
            ],
        }
        tuning = {
            "variant": "gpcr_core_truebase_gap_penalty_shadow_v15",
            "candidate_source": "v14_cationic_occupancy_reward_rework",
            "scorer_change": "remove_cationic_occupancy_reward_keep_cached_truebase_support_gap_penalty",
            "scope": "class_a_aminergic_opioid_like_orthosteric_sublane",
            "broad_gpcr_claim_allowed": False,
            "active_score_locked_to_base": True,
            "best_baseline_variant": "gpcr_core_pose_support_gap_shadow_v13",
            "rejected_predecessor_variant": "gpcr_core_truebase_anchor_occupancy_shadow_v14",
            "target_identity_feature_allowed": False,
            "label_feature_allowed": False,
            "rank_feature_allowed": False,
            "ligand_id_feature_allowed": False,
            "reference_binding_value_allowed": False,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
            "penalty_weight": 4.0,
            "synthetic_anchor_saturation_penalty_weight": 8.0,
            "moderate_multi_basic_support_weight": 20.0,
            "truebase_unsupported_strong_base_pressure_weight": 28.0,
            "truebase_pose_gap_pressure_weight": 12.0,
            "truebase_backmapping_collapse_pressure_weight": 8.0,
            "truebase_overclose_artifact_pressure_weight": 10.0,
            "multipolar_basic_pressure_weight": 4.0,
            "truebase_formula": "coalesce(cached base_score, binding_score_composite_v7)",
            "truebase_unsupported_formula": "clip((-6.0 - true_base_score) / 2.0, 0.0, inf) * v13_no_support_gate",
            "truebase_pose_gap_formula": "clip((-6.0 - true_base_score) / 2.0, 0.0, inf) * pose_gap_gate",
            "live_feature_policy": "cached_true_base_score_plus_label_free_truebase_penalties_no_occupancy_reward",
            "replay_score_formula": (
                "base_score "
                "+ 4.0*label_free_penalty_pressure "
                "+ 8.0*gpcr_synthetic_anchor_saturation_pressure_v12 "
                "- 20.0*gpcr_moderate_multi_basic_weakbase_support_v12 "
                "+ 28.0*gpcr_truebase_unsupported_strong_base_pressure_v15 "
                "+ 12.0*gpcr_truebase_pose_gap_pressure_v15 "
                "+ 8.0*gpcr_truebase_backmapping_collapse_pressure_v14 "
                "+ 10.0*gpcr_truebase_overclose_artifact_pressure_v14 "
                "+ 4.0*multipolar_basic_pressure"
            ),
        }
        interactions = [
            "v14_cationic_occupancy_reward_rejected_for_htr2a_decoy_overpromotion",
            "cached_true_base_score_is_used_for_gap_pressure",
            "cationic_center_occupancy_is_diagnostic_only_not_reward",
            "strong_truebase_unsupported_rows_are_demoted_without_label_or_target_features",
            "active_score_locked_to_base_even_in_apply_mode",
            "no_target_is_binder_rank_ligand_id_reference_binding_threshold_relaxation_or_fake_pass_features",
            "no_router_platform_or_claim_promotion",
        ]
        next_step = (
            "Replay gpcr_core_truebase_gap_penalty_shadow_v15 on the complete true-base frozen cationic cache. "
            "It must beat v13/v14 on HTR2A and OPRM1 without DRD2 regression before any guarded 100k rerun planning."
        )
    elif variant == "gpcr_core_false_support_discriminator_shadow_v16":
        constraints = {
            **constraints,
            "max_abs_delta_score": 0.0,
            "yellow_band_abs_delta_score": 0.0,
            "comparison_only_candidate": True,
            "claim_locked_candidate": True,
            "shadow_only_candidate": True,
            "score_only_candidate": True,
            "active_score_locked_to_base": True,
            "class_a_aminergic_opioid_orthosteric_sublane_candidate": True,
            "requires_precomputed_frozen_row_v10_features": True,
            "requires_true_base_score_cache": True,
            "requires_v15_gap_packet_review": True,
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
            "best_baseline_variant": "gpcr_core_truebase_gap_penalty_shadow_v15",
            "baseline_role": "v15_best_current_frozen_shadow_comparator",
            "candidate_source_artifact": "runs/gpcr_truebase_gap_penalty_v15_frozen_gap_packet_current.json",
            "blocked_v15_targets": ["CHEMBL224_HTR2A_HUMAN", "CHEMBL233_OPRM1_HUMAN"],
            "allowed_live_feature_families": [
                "cached_true_base_score",
                "label_free_pose_distortion_pressure",
                "synthetic_anchor_saturation_pressure",
                "moderate_multi_basic_support_window",
                "truebase_unsupported_strong_base_pressure",
                "truebase_pose_gap_pressure",
                "truebase_backmapping_collapse_pressure",
                "truebase_cationic_overclose_artifact_pressure",
                "false_support_saturation_pressure",
                "nonbasic_noanchor_intrusion_pressure",
                "basic_collapse_noanchor_intrusion_pressure",
                "multipolar_basic_pressure",
            ],
            "forbidden_live_feature_families": [
                "target",
                "is_binder",
                "rank",
                "ligand_id",
                "reference_binding",
                "threshold_relaxation",
                "fake_pass",
                "cationic_anchor_occupancy_reward",
            ],
            "required_before_claim": [
                "v16_shadow_replay_improves_htr2a_oprm1_without_drd2_regression",
                "leakage_review_no_target_is_binder_rank_ligand_id_reference_binding_inputs",
                "fresh_full_100k_ci_low_top20_claim_review_green",
                "family_held_out_scorecard_green",
            ],
        }
        tuning = {
            "variant": "gpcr_core_false_support_discriminator_shadow_v16",
            "candidate_source": "v15_frozen_gap_packet",
            "scorer_change": "add_false_support_and_noanchor_intrusion_pressures_without_rewards",
            "scope": "class_a_aminergic_opioid_like_orthosteric_sublane",
            "broad_gpcr_claim_allowed": False,
            "active_score_locked_to_base": True,
            "best_baseline_variant": "gpcr_core_truebase_gap_penalty_shadow_v15",
            "target_identity_feature_allowed": False,
            "label_feature_allowed": False,
            "rank_feature_allowed": False,
            "ligand_id_feature_allowed": False,
            "reference_binding_value_allowed": False,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
            "penalty_weight": 4.0,
            "synthetic_anchor_saturation_penalty_weight": 8.0,
            "moderate_multi_basic_support_weight": 20.0,
            "truebase_unsupported_strong_base_pressure_weight": 28.0,
            "truebase_pose_gap_pressure_weight": 12.0,
            "truebase_backmapping_collapse_pressure_weight": 8.0,
            "truebase_overclose_artifact_pressure_weight": 10.0,
            "false_support_saturation_pressure_weight": 10.0,
            "nonbasic_truebase_noanchor_pressure_weight": 6.0,
            "basic_collapse_truebase_noanchor_pressure_weight": 6.0,
            "multipolar_basic_pressure_weight": 4.0,
            "false_support_formula": (
                "window(label_free_support_pressure>0.35) * weak_support_missing * "
                "low_basic_count_gate * soft_truebase_intrusion_gate"
            ),
            "nonbasic_noanchor_formula": "nonbasic_gate * v13_no_support_gate * soft_truebase_noanchor_gate",
            "basic_collapse_noanchor_formula": "basic_gate * v13_no_support_gate * collapse_gate * strong_truebase_gate",
            "live_feature_policy": "cached_true_base_score_plus_label_free_decoy_pressures_no_rewards",
            "replay_score_formula": (
                "base_score "
                "+ 4.0*label_free_penalty_pressure "
                "+ 8.0*gpcr_synthetic_anchor_saturation_pressure_v12 "
                "- 20.0*gpcr_moderate_multi_basic_weakbase_support_v12 "
                "+ 28.0*gpcr_truebase_unsupported_strong_base_pressure_v15 "
                "+ 12.0*gpcr_truebase_pose_gap_pressure_v15 "
                "+ 8.0*gpcr_truebase_backmapping_collapse_pressure_v14 "
                "+ 10.0*gpcr_truebase_overclose_artifact_pressure_v14 "
                "+ 10.0*gpcr_false_support_saturation_pressure_v16 "
                "+ 6.0*gpcr_nonbasic_truebase_noanchor_pressure_v16 "
                "+ 6.0*gpcr_basic_collapse_truebase_noanchor_pressure_v16 "
                "+ 4.0*multipolar_basic_pressure"
            ),
        }
        interactions = [
            "v15_best_frozen_shadow_preserved_as_comparator",
            "false_support_saturation_is_penalty_not_reward",
            "nonbasic_noanchor_truebase_intrusion_is_penalized",
            "basic_pose_collapse_noanchor_intrusion_is_penalized_only_when_truebase_is_strong",
            "active_score_locked_to_base_even_in_apply_mode",
            "no_target_is_binder_rank_ligand_id_reference_binding_threshold_relaxation_or_fake_pass_features",
            "no_router_platform_or_claim_promotion",
        ]
        next_step = (
            "Replay gpcr_core_false_support_discriminator_shadow_v16 on the complete true-base frozen cationic cache. "
            "It must improve HTR2A/OPRM1 without DRD2 regression and still remains claim-locked until full 100k "
            "CI-low/top20 plus family-held-out reviews are green."
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
                else {
                    "enabled": True,
                    "combine_mode": "replace",
                    "intercept": 0.0,
                    "terms": [
                        {"feature": "binding_score_composite_v7_prior_active", "weight": 1.0},
                        {"feature": "fixed_reference_live_overreward_pressure", "weight": 1.25},
                    ],
                }
                if variant == "gpcr_core_fixed_reference_live_shadow_v5"
                else {
                    "enabled": True,
                    "combine_mode": "replace",
                    "intercept": 0.0,
                    "terms": [
                        {"feature": "binding_score_composite_v7_prior_active", "weight": 1.0},
                        {"feature": "class_a_orthosteric_motif_support_proxy", "weight": -0.75},
                        {"feature": "class_a_prior_overreward_invalid_overanchor_pressure", "weight": 1.10},
                    ],
                }
                if variant == "gpcr_core_class_a_motif_shadow_v6"
                else {
                    "enabled": True,
                    "combine_mode": "replace",
                    "intercept": 0.0,
                    "terms": [
                        {"feature": "binding_score_composite_v7_prior_active", "weight": 1.0},
                        {"feature": "class_a_charge_complemented_anchor_geometry_proxy", "weight": -0.55},
                        {"feature": "class_a_orthosteric_occupancy_proxy", "weight": -0.35},
                        {"feature": "class_a_pose_survival_support_proxy", "weight": -0.45},
                        {"feature": "class_a_invalid_anchor_prior_pressure_v7", "weight": 1.20},
                    ],
                }
                if variant == "gpcr_core_class_a_anchor_geometry_shadow_v7"
                else {
                    "enabled": True,
                    "combine_mode": "replace",
                    "intercept": 0.0,
                    "terms": [
                        {"feature": "binding_score_composite_v7_prior_active", "weight": 1.0},
                        {"feature": "class_a_direct_atom_window_anchor_geometry_proxy", "weight": -0.75},
                        {"feature": "class_a_atom_window_pose_survival_proxy", "weight": -0.20},
                        {"feature": "class_a_hydrophobic_overcontact_pressure_v8", "weight": 1.35},
                    ],
                }
                if variant == "gpcr_core_direct_atom_anchor_window_shadow_v8"
                else {
                    "enabled": True,
                    "combine_mode": "replace",
                    "intercept": 0.0,
                    "terms": [
                        {"feature": "binding_score_composite_v7_prior_active", "weight": 1.0},
                        {"feature": "class_a_direct_atom_window_anchor_geometry_proxy", "weight": -0.55},
                        {"feature": "class_a_atom_window_pose_survival_proxy", "weight": -0.15},
                        {"feature": "class_a_compact_amine_window_support_v9", "weight": -0.20},
                        {"feature": "class_a_hydrophobic_overcontact_pressure_v8", "weight": 1.35},
                        {"feature": "class_a_excess_polar_anchor_pressure_v9", "weight": 2.75},
                    ],
                }
                if variant == "gpcr_core_atom_window_excess_polar_shadow_v9"
                else {
                    "enabled": True,
                    "combine_mode": "replace",
                    "intercept": 0.0,
                    "terms": [
                        {"feature": "base_score", "weight": 1.0},
                        {"feature": "label_free_penalty_pressure", "weight": 6.0},
                        {"feature": "label_free_support_pressure", "weight": -16.0},
                    ],
                }
                if variant == "gpcr_core_cationic_pose_distortion_shadow_v10"
                else {
                    "enabled": True,
                    "combine_mode": "replace",
                    "intercept": 0.0,
                    "terms": [
                        {"feature": "base_score", "weight": 1.0},
                        {"feature": "label_free_penalty_pressure", "weight": 6.0},
                        {"feature": "weak_base_rescue_support_pressure", "weight": -18.0},
                    ],
                }
                if variant == "gpcr_core_cationic_weakbase_rescue_shadow_v11"
                else {
                    "enabled": True,
                    "combine_mode": "replace",
                    "intercept": 0.0,
                    "terms": [
                        {"feature": "base_score", "weight": 1.0},
                        {"feature": "label_free_penalty_pressure", "weight": 4.0},
                        {"feature": "gpcr_synthetic_anchor_saturation_pressure_v12", "weight": 8.0},
                        {"feature": "gpcr_moderate_multi_basic_weakbase_support_v12", "weight": -20.0},
                    ],
                }
                if variant == "gpcr_core_synthetic_anchor_penalty_shadow_v12"
                else {
                    "enabled": True,
                    "combine_mode": "replace",
                    "intercept": 0.0,
                    "terms": [
                        {"feature": "base_score", "weight": 1.0},
                        {"feature": "label_free_penalty_pressure", "weight": 4.0},
                        {"feature": "gpcr_synthetic_anchor_saturation_pressure_v12", "weight": 8.0},
                        {"feature": "gpcr_moderate_multi_basic_weakbase_support_v12", "weight": -20.0},
                        {"feature": "gpcr_unsupported_strong_base_pressure_v13", "weight": 28.0},
                        {"feature": "gpcr_pose_gap_strong_base_pressure_v13", "weight": 12.0},
                        {"feature": "multipolar_basic_pressure", "weight": 4.0},
                    ],
                }
                if variant == "gpcr_core_pose_support_gap_shadow_v13"
                else {
                    "enabled": True,
                    "combine_mode": "replace",
                    "intercept": 0.0,
                    "terms": [
                        {"feature": "base_score", "weight": 1.0},
                        {"feature": "label_free_penalty_pressure", "weight": 4.0},
                        {"feature": "gpcr_synthetic_anchor_saturation_pressure_v12", "weight": 8.0},
                        {"feature": "gpcr_moderate_multi_basic_weakbase_support_v12", "weight": -20.0},
                        {"feature": "gpcr_truebase_unsupported_strong_base_pressure_v14", "weight": 28.0},
                        {"feature": "gpcr_truebase_pose_gap_pressure_v14", "weight": 12.0},
                        {"feature": "gpcr_truebase_backmapping_collapse_pressure_v14", "weight": 8.0},
                        {"feature": "gpcr_truebase_overclose_artifact_pressure_v14", "weight": 10.0},
                        {"feature": "gpcr_cationic_anchor_occupancy_support_v14", "weight": -8.0},
                        {"feature": "multipolar_basic_pressure", "weight": 4.0},
                    ],
                }
                if variant == "gpcr_core_truebase_anchor_occupancy_shadow_v14"
                else {
                    "enabled": True,
                    "combine_mode": "replace",
                    "intercept": 0.0,
                    "terms": [
                        {"feature": "base_score", "weight": 1.0},
                        {"feature": "label_free_penalty_pressure", "weight": 4.0},
                        {"feature": "gpcr_synthetic_anchor_saturation_pressure_v12", "weight": 8.0},
                        {"feature": "gpcr_moderate_multi_basic_weakbase_support_v12", "weight": -20.0},
                        {"feature": "gpcr_truebase_unsupported_strong_base_pressure_v15", "weight": 28.0},
                        {"feature": "gpcr_truebase_pose_gap_pressure_v15", "weight": 12.0},
                        {"feature": "gpcr_truebase_backmapping_collapse_pressure_v14", "weight": 8.0},
                        {"feature": "gpcr_truebase_overclose_artifact_pressure_v14", "weight": 10.0},
                        {"feature": "multipolar_basic_pressure", "weight": 4.0},
                    ],
                }
                if variant == "gpcr_core_truebase_gap_penalty_shadow_v15"
                else {
                    "enabled": True,
                    "combine_mode": "replace",
                    "intercept": 0.0,
                    "terms": [
                        {"feature": "base_score", "weight": 1.0},
                        {"feature": "label_free_penalty_pressure", "weight": 4.0},
                        {"feature": "gpcr_synthetic_anchor_saturation_pressure_v12", "weight": 8.0},
                        {"feature": "gpcr_moderate_multi_basic_weakbase_support_v12", "weight": -20.0},
                        {"feature": "gpcr_truebase_unsupported_strong_base_pressure_v15", "weight": 28.0},
                        {"feature": "gpcr_truebase_pose_gap_pressure_v15", "weight": 12.0},
                        {"feature": "gpcr_truebase_backmapping_collapse_pressure_v14", "weight": 8.0},
                        {"feature": "gpcr_truebase_overclose_artifact_pressure_v14", "weight": 10.0},
                        {"feature": "gpcr_false_support_saturation_pressure_v16", "weight": 10.0},
                        {"feature": "gpcr_nonbasic_truebase_noanchor_pressure_v16", "weight": 6.0},
                        {"feature": "gpcr_basic_collapse_truebase_noanchor_pressure_v16", "weight": 6.0},
                        {"feature": "multipolar_basic_pressure", "weight": 4.0},
                    ],
                }
                if variant == "gpcr_core_false_support_discriminator_shadow_v16"
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
            "gpcr_core_fixed_reference_live_shadow_v5",
            "gpcr_core_class_a_motif_shadow_v6",
            "gpcr_core_class_a_anchor_geometry_shadow_v7",
            "gpcr_core_direct_atom_anchor_window_shadow_v8",
            "gpcr_core_atom_window_excess_polar_shadow_v9",
            "gpcr_core_cationic_pose_distortion_shadow_v10",
            "gpcr_core_cationic_weakbase_rescue_shadow_v11",
            "gpcr_core_synthetic_anchor_penalty_shadow_v12",
            "gpcr_core_pose_support_gap_shadow_v13",
            "gpcr_core_truebase_anchor_occupancy_shadow_v14",
            "gpcr_core_truebase_gap_penalty_shadow_v15",
            "gpcr_core_false_support_discriminator_shadow_v16",
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
