#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

from tools.lib.artifacts import (
    artifact as _artifact,
    read_json as _read_json,
    resolve as _resolve,
    summary as _summary,
    write_json as _write_json,
)

DEFAULT_LOCAL_ACCURACY_JSON = "runs/accuracy_gate_local_delivery_preflight_current.json"
DEFAULT_OPENMM_EXTERNAL_JSON = "runs/openmm_2bead_strict_multitarget_current_accuracy_external.json"
DEFAULT_OPENMM_STABILITY_JSON = "runs/openmm_2bead_strict_multitarget_current_long_stability_validation.json"
DEFAULT_GPCR_RANKING_JSON = (
    "runs/external_validation_2026-05-13_gpcr_a1_independent_repeat_r2_"
    "set1_core_blind_gpcr_core_full_p0_n100000_r1_stage5_ranking_summary.json"
)
DEFAULT_GPCR_CORE_DIAGNOSTICS_JSON = "runs/gpcr_core_rank_diagnostics_current.json"
DEFAULT_GPCR_DRD2_REPAIR_JSON = "runs/gpcr_drd2_pose_generation_repair_packet_current.json"
DEFAULT_GPCR_DRD2_BACKMAPPING_SUPPORT_JSON = "runs/gpcr_drd2_atom_typed_backmapping_support_current.json"
DEFAULT_GPCR_DRD2_HARD_DECOY_ENVELOPE_JSON = "runs/gpcr_drd2_hard_decoy_penalty_envelope_current.json"
DEFAULT_GPCR_DRD2_FULL_FORCEFIELD_READINESS_JSON = (
    "runs/gpcr_drd2_full_forcefield_minimization_readiness_current.json"
)
DEFAULT_GPCR_DRD2_PARAMETERIZATION_PROBE_JSON = (
    "runs/gpcr_drd2_openmm_forcefield_parameterization_probe_current.json"
)
DEFAULT_GPCR_DRD2_PROTEIN_REPAIR_JSON = "runs/gpcr_drd2_protein_amber14_parameterization_repair_current.json"
DEFAULT_GPCR_POSE_GAP_JSON = "runs/gpcr_false_support_discriminator_v16_adaptive_frozen_gap_packet_current.json"
DEFAULT_STRUCTURE_SCORECARD_JSON = "runs/structure_refinement_scorecard_current.json"
DEFAULT_WETLAB_TRANSLATION_JSON = "runs/wetlab_tcruzi_pde_translation_quality_packet_current.json"
DEFAULT_WETLAB_ALLATOM_REVIEW_JSON = "runs/wetlab_tcruzi_pde_allatom_review_packet_current.json"
DEFAULT_COMMERCIAL_READINESS_JSON = "runs/commercialization_readiness_current.json"
DEFAULT_OUT_JSON = "runs/accuracy_parity_scorecard_current.json"
DEFAULT_OUT_MD = "runs/accuracy_parity_scorecard_current.md"

PHYSICS_TARGET_MIN = 5
PHYSICS_TARGET_DEFAULT_GOAL = 11
GPCR_PR_AUC_MIN = 0.55
GPCR_PR_AUC_CI_LOW_MIN = 0.45
GPCR_TOPK_MIN = 0.50
POSE_ATOM_COVERAGE_MIN = 0.50
WETLAB_TRANSLATION_SCORE_MIN = 80.0


def _float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _int(value: Any) -> int | None:
    out = _float(value)
    return int(out) if out is not None else None


def _bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y", "pass"}:
        return True
    if text in {"false", "0", "no", "n", "fail"}:
        return False
    return None


def _topk_hit_rate(payload: dict[str, Any], *, k: int = 20) -> float | None:
    for key in ("topk_unique", "topk"):
        rows = payload.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            if _int(row.get("k")) == k:
                return _float(row.get("hit_rate"))
    return None


def _ranking_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = _summary(payload)
    if summary:
        return summary
    stage6 = payload.get("stages", {}).get("stage6_operational_gate") if isinstance(payload.get("stages"), dict) else {}
    if isinstance(stage6, dict) and stage6:
        return {
            "claim_promotion_allowed": stage6.get("claim_promotion_allowed"),
            "ranking_pr_auc": _float(stage6.get("ranking_pr_auc")),
            "ranking_pr_auc_ci_low": _float(stage6.get("ranking_pr_auc_ci_low")),
            "ranking_topk_hit_rate": _float(stage6.get("ranking_topk_hit_rate")),
            "positive_count": _int(stage6.get("ranking_positive_count")),
            "ranking_score_col_used": stage6.get("ranking_score_col_used"),
        }
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    metrics_ci_unique = payload.get("metrics_ci_unique") if isinstance(payload.get("metrics_ci_unique"), dict) else {}
    metrics_ci = payload.get("metrics_ci") if isinstance(payload.get("metrics_ci"), dict) else {}
    pr_ci = metrics_ci_unique.get("pr_auc") if isinstance(metrics_ci_unique.get("pr_auc"), dict) else {}
    if not pr_ci:
        pr_ci = metrics_ci.get("pr_auc") if isinstance(metrics_ci.get("pr_auc"), dict) else {}
    return {
        "claim_promotion_allowed": payload.get("claim_promotion_allowed"),
        "blockers": payload.get("blockers", []),
        "ranking_pr_auc": _float(metrics.get("pr_auc_unique_key") or metrics.get("pr_auc")),
        "ranking_pr_auc_ci_low": _float(pr_ci.get("low")),
        "ranking_topk_hit_rate": _topk_hit_rate(payload, k=20),
        "positive_count": _int(metrics.get("positive_count_unique_key") or metrics.get("positive_count")),
        "ranking_score_col_used": metrics.get("probability_score_col_used") or payload.get("score_col"),
    }


def _metric(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 6)
    return value


def _row(
    *,
    axis: str,
    comparator: str,
    status: str,
    claim_scope: str,
    source_artifacts: list[str],
    metrics: dict[str, Any],
    thresholds: dict[str, Any],
    blockers: list[str],
    next_required_step: str,
) -> dict[str, Any]:
    claim_allowed = status == "pass"
    return {
        "axis": axis,
        "comparator": comparator,
        "status": status,
        "claim_scope": claim_scope,
        "commercial_parity_claim_allowed": claim_allowed,
        "claim_promotion_allowed": claim_allowed,
        "source_artifacts": source_artifacts,
        "metrics": {key: _metric(value) for key, value in metrics.items()},
        "thresholds": thresholds,
        "blockers": blockers,
        "next_required_step": next_required_step,
    }


def _physics_row(
    *,
    local_accuracy_json: str | Path,
    openmm_external_json: str | Path,
    openmm_stability_json: str | Path,
) -> dict[str, Any]:
    local_payload = _read_json(local_accuracy_json)
    openmm_payload = _read_json(openmm_external_json)
    stability_payload = _read_json(openmm_stability_json)
    local_summary = _summary(local_payload)
    local_parity = local_payload.get("parity_summary", {})
    local_parity = local_parity if isinstance(local_parity, dict) else {}
    openmm_summary = _summary(openmm_payload)
    stability_summary = _summary(stability_payload)

    local_pass = _bool(local_summary.get("pass"))
    openmm_targets = _int(openmm_summary.get("targets"))
    stability_targets = _int(stability_summary.get("targets"))
    avg_rmsd = _float(openmm_summary.get("avg_rmsd"))
    energy_drift = _float(stability_summary.get("avg_energy_drift_ratio_mean"))

    blockers: list[str] = []
    if local_pass is not True:
        blockers.append("local_accuracy_gate_not_green")
    if openmm_targets is None or openmm_targets < PHYSICS_TARGET_MIN:
        blockers.append("openmm_reference_target_count_too_small")
    if stability_targets is None or stability_targets < PHYSICS_TARGET_MIN:
        blockers.append("openmm_stability_target_count_too_small")

    status = "pass" if not blockers else "restricted_pass" if local_pass is True and avg_rmsd is not None else "blocked"
    claim_scope = (
        "restricted local physics/kernel path only"
        if status == "restricted_pass"
        else "broad OpenMM-class physics/dynamics parity"
    )
    return _row(
        axis="physics_dynamics",
        comparator="OpenMM",
        status=status,
        claim_scope=claim_scope,
        source_artifacts=[_artifact(local_accuracy_json), _artifact(openmm_external_json), _artifact(openmm_stability_json)],
        metrics={
            "local_accuracy_pass": local_pass,
            "local_targets": _int(local_summary.get("targets")),
            "avg_neighbor_jaccard": _float(local_parity.get("avg_neighbor_jaccard")),
            "avg_force_rmse_raw": _float(local_parity.get("avg_force_rmse_raw")),
            "openmm_reference_targets": openmm_targets,
            "openmm_avg_rmsd": avg_rmsd,
            "openmm_stability_targets": stability_targets,
            "openmm_energy_drift_ratio_mean": energy_drift,
        },
        thresholds={
            "openmm_reference_targets_min": PHYSICS_TARGET_MIN,
            "openmm_stability_targets_min": PHYSICS_TARGET_MIN,
            "openmm_default_commercial_evidence_targets": PHYSICS_TARGET_DEFAULT_GOAL,
            "requires_force_energy_trajectory_distribution_parity": True,
        },
        blockers=blockers,
        next_required_step=(
            "OpenMM multi-target count gate is green; keep the 11-target current artifacts attached and expand "
            "force/energy distribution, restart determinism, and protein-ligand system-class evidence."
            if not blockers
            else "Regenerate the OpenMM current artifacts with at least five reference and stability targets; "
            "the default commercialization evidence goal is the full 11-target challenge set."
        ),
    )


def _ligand_ranking_row(
    *,
    gpcr_ranking_json: str | Path,
    gpcr_core_diagnostics_json: str | Path,
) -> dict[str, Any]:
    ranking_summary = _ranking_summary(_read_json(gpcr_ranking_json))
    core_summary = _summary(_read_json(gpcr_core_diagnostics_json))
    pr_auc = _float(ranking_summary.get("ranking_pr_auc"))
    ci_low = _float(ranking_summary.get("ranking_pr_auc_ci_low"))
    topk = _float(ranking_summary.get("ranking_topk_hit_rate"))
    claim_allowed = _bool(ranking_summary.get("claim_promotion_allowed"))
    blockers = list(ranking_summary.get("blockers") or [])
    if pr_auc is None or pr_auc < GPCR_PR_AUC_MIN:
        blockers.append("ranking_pr_auc_below_threshold")
    if ci_low is None or ci_low < GPCR_PR_AUC_CI_LOW_MIN:
        blockers.append("ranking_pr_auc_ci_low_below_threshold")
    if topk is None or topk < GPCR_TOPK_MIN:
        blockers.append("topk_hit_rate_below_threshold")
    if claim_allowed is not True:
        blockers.append("claim_promotion_not_allowed")
    blockers = sorted(set(blockers))
    metric_blockers = [
        blocker
        for blocker in blockers
        if blocker
        in {
            "ranking_pr_auc_below_threshold",
            "ranking_pr_auc_ci_low_below_threshold",
            "topk_hit_rate_below_threshold",
        }
    ]
    if not metric_blockers and "claim_promotion_not_allowed" in blockers:
        next_required_step = (
            "GPCR ranking metrics clear the local guarded thresholds; keep claim promotion false until the "
            "accuracy scorecard, leakage/pose guardrails, and an independent repeat are reviewed."
        )
        status = "restricted_pass"
    elif blockers:
        next_required_step = (
            "Repair DRD2/HTR2A/OPRM1 pose-supported ranking, rebuild hard decoys, then rerun guarded "
            "100k review before any Schrödinger-class ligand-ranking claim."
        )
        status = "blocked"
    else:
        next_required_step = (
            "Maintain green ligand-ranking parity under the unchanged thresholds while keeping router/platform "
            "promotion separate from this scorecard row."
        )
        status = "pass"
    return _row(
        axis="ligand_ranking",
        comparator="Schrodinger Glide/FEP+ class ranking",
        status=status,
        claim_scope="broad GPCR ligand ranking/docking parity",
        source_artifacts=[_artifact(gpcr_ranking_json), _artifact(gpcr_core_diagnostics_json)],
        metrics={
            "ranking_pr_auc": pr_auc,
            "ranking_pr_auc_ci_low": ci_low,
            "ranking_topk_hit_rate": topk,
            "positive_count": _int(ranking_summary.get("positive_count")),
            "ranking_score_col_used": ranking_summary.get("ranking_score_col_used"),
            "worst_positive_global_rank": _int(ranking_summary.get("worst_positive_global_rank")),
            "worst_positive_within_target_rank": _int(ranking_summary.get("worst_positive_within_target_rank")),
            "core_claim_safe": _bool(core_summary.get("claim_safe")),
            "core_primary_blocker_task": core_summary.get("primary_blocker_task"),
        },
        thresholds={
            "ranking_pr_auc_min": GPCR_PR_AUC_MIN,
            "ranking_pr_auc_ci_low_min": GPCR_PR_AUC_CI_LOW_MIN,
            "ranking_topk_hit_rate_min": GPCR_TOPK_MIN,
            "requires_pose_supported_decoy_resistance": True,
        },
        blockers=blockers,
        next_required_step=next_required_step,
    )


def _pose_geometry_row(
    *,
    gpcr_drd2_repair_json: str | Path,
    gpcr_drd2_backmapping_support_json: str | Path,
    gpcr_drd2_hard_decoy_envelope_json: str | Path,
    gpcr_drd2_full_forcefield_readiness_json: str | Path,
    gpcr_drd2_parameterization_probe_json: str | Path,
    gpcr_drd2_protein_repair_json: str | Path,
    gpcr_pose_gap_json: str | Path,
) -> dict[str, Any]:
    drd2_summary = _summary(_read_json(gpcr_drd2_repair_json))
    support_summary = _summary(_read_json(gpcr_drd2_backmapping_support_json))
    hard_decoy_envelope_summary = _summary(_read_json(gpcr_drd2_hard_decoy_envelope_json))
    readiness_summary = _summary(_read_json(gpcr_drd2_full_forcefield_readiness_json))
    parameterization_summary = _summary(_read_json(gpcr_drd2_parameterization_probe_json))
    protein_repair_summary = _summary(_read_json(gpcr_drd2_protein_repair_json))
    gap_summary = _summary(_read_json(gpcr_pose_gap_json))
    coverage = _float(support_summary.get("positive_backmapping_atom_coverage_ratio"))
    if coverage is None:
        coverage = _float(drd2_summary.get("positive_backmapping_atom_coverage_ratio"))
    pose_p90 = _float(support_summary.get("positive_pose_preservation_rmsd_A_p90"))
    local_min_survival = _float(support_summary.get("positive_local_minimization_survival_fraction"))
    blockers = list(drd2_summary.get("blockers") or [])
    blockers.extend(list((gap_summary.get("blocker_counts") or {}).keys()))
    blockers.extend(list(support_summary.get("positive_blockers") or []))
    if pose_p90 is not None:
        blockers = [blocker for blocker in blockers if blocker != "pose_preservation_rmsd_missing"]
    if local_min_survival is not None:
        blockers = [blocker for blocker in blockers if blocker != "local_minimization_survival_missing"]
    if coverage is not None and coverage >= POSE_ATOM_COVERAGE_MIN:
        blockers = [
            blocker
            for blocker in blockers
            if blocker
            not in {
                "backmapping_atom_coverage_below_min",
                "positive_backmapping_atom_coverage_below_threshold",
                "full_atom_typed_backmapping_missing",
                "cationic_center_anchor_not_atom_typed",
                "backmapped_pdb_missing",
                "positive_backmapping_atom_coverage_low",
            }
        ]
    if pose_p90 is not None and pose_p90 <= 2.0:
        blockers = [blocker for blocker in blockers if blocker != "positive_pose_preservation_borderline"]
    hard_decoy_envelope_green = (
        str(hard_decoy_envelope_summary.get("status") or "").strip() == "slice_pairwise_green_diagnostic_only"
    )
    hard_decoy_rebuild_allowed = _bool(support_summary.get("hard_decoy_rebuild_allowed")) is True
    if hard_decoy_envelope_green and hard_decoy_rebuild_allowed:
        blockers = [
            blocker
            for blocker in blockers
            if blocker
            not in {
                "drd2_positive_tail_rank",
                "overanchored_decoy_cluster_present",
                "multipolar_basic_decoy_intrusion_present",
                "positive_anchor_support_missing",
                "target_decoys_above_positive",
                "decoy_anchor_support_exceeds_positive",
                "base_score_decoy_intrusion",
                "multipolar_decoy_pressure_not_sufficient",
            }
        ]
    if local_min_survival is None:
        blockers.append("local_minimization_survival_missing")
    if _bool(readiness_summary.get("full_forcefield_minimization_ready")) is not True:
        blockers.append("full_forcefield_minimization_not_ready")
    if _bool(readiness_summary.get("protein_parameterization_available")) is not True:
        blockers.append("protein_parameterization_unavailable")
    if (_int(protein_repair_summary.get("missing_heavy_atom_residue_count")) or 0) > 0:
        blockers.append("protein_missing_heavy_atom_residues_present")
    ligand_partial_ready = _bool(parameterization_summary.get("ligand_template_parameterization_available")) is True
    if _bool(readiness_summary.get("ligand_parameterization_available")) is not True and not ligand_partial_ready:
        blockers.append("ligand_parameterization_unavailable")
    if ligand_partial_ready and _bool(parameterization_summary.get("claim_grade_parameterization_ready")) is not True:
        blockers.append("ligand_parameterization_ligand_only_not_full_complex")
    if coverage is None or coverage < POSE_ATOM_COVERAGE_MIN:
        blockers.append("positive_backmapping_atom_coverage_below_threshold")
    if _bool(drd2_summary.get("claim_promotion_allowed")) is not True and not (
        hard_decoy_envelope_green and hard_decoy_rebuild_allowed
    ):
        blockers.append("claim_promotion_not_allowed")
    blockers = sorted(set(str(item) for item in blockers if str(item)))
    return _row(
        axis="pose_geometry",
        comparator="commercial docking pose geometry",
        status="blocked" if blockers else "pass",
        claim_scope="target-portable GPCR pose/backmapping geometry",
        source_artifacts=[
            _artifact(gpcr_drd2_repair_json),
            _artifact(gpcr_drd2_backmapping_support_json),
            _artifact(gpcr_drd2_hard_decoy_envelope_json),
            _artifact(gpcr_drd2_full_forcefield_readiness_json),
            _artifact(gpcr_drd2_parameterization_probe_json),
            _artifact(gpcr_drd2_protein_repair_json),
            _artifact(gpcr_pose_gap_json),
        ],
        metrics={
            "drd2_positive_global_rank": _int(drd2_summary.get("positive_global_rank")),
            "drd2_positive_within_target_rank": _int(drd2_summary.get("positive_within_target_rank")),
            "drd2_decoys_above_positive_count": _int(drd2_summary.get("decoys_above_positive_count")),
            "drd2_positive_backmapping_atom_coverage_ratio": coverage,
            "drd2_positive_full_atom_typed_backmapping_ready": _bool(
                support_summary.get("positive_full_atom_typed_backmapping_ready")
            ),
            "drd2_positive_pose_preservation_rmsd_A_p90": pose_p90,
            "drd2_positive_local_minimization_survival_fraction": local_min_survival,
            "drd2_hard_decoy_envelope_status": hard_decoy_envelope_summary.get("status"),
            "drd2_hard_decoy_rebuild_allowed": hard_decoy_rebuild_allowed,
            "drd2_hard_decoy_bounded_best_positive_rank": _int(
                hard_decoy_envelope_summary.get("bounded_best_positive_rank")
            ),
            "drd2_full_forcefield_minimization_ready": _bool(
                readiness_summary.get("full_forcefield_minimization_ready")
            ),
            "drd2_protein_parameterization_available": _bool(
                readiness_summary.get("protein_parameterization_available")
            ),
            "drd2_ligand_parameterization_available": _bool(
                readiness_summary.get("ligand_parameterization_available")
            ),
            "drd2_ligand_template_parameterization_available": _bool(
                parameterization_summary.get("ligand_template_parameterization_available")
            ),
            "drd2_local_parameterization_probe_partial": _bool(parameterization_summary.get("local_probe_partial")),
            "drd2_claim_grade_parameterization_ready": _bool(
                parameterization_summary.get("claim_grade_parameterization_ready")
            ),
            "drd2_protein_missing_heavy_atom_residue_count": _int(
                protein_repair_summary.get("missing_heavy_atom_residue_count")
            ),
            "drd2_incomplete_histidine_count": _int(protein_repair_summary.get("incomplete_histidine_count")),
            "drd2_protein_claim_grade_repair_allowed": _bool(
                protein_repair_summary.get("claim_grade_repair_allowed")
            ),
            "drd2_missing_forcefield_dependencies": readiness_summary.get("missing_dependencies") or [],
            "drd2_missing_forcefield_assets": readiness_summary.get("missing_assets") or [],
            "pose_gap_blocked_positive_count": _int(gap_summary.get("blocked_positive_count")),
            "pose_gap_top20_positive_count": _int(gap_summary.get("top20_positive_count")),
        },
        thresholds={
            "positive_backmapping_atom_coverage_min": POSE_ATOM_COVERAGE_MIN,
            "requires_pose_preservation_rmsd": True,
            "requires_local_minimization_survival": True,
            "requires_full_protein_ligand_forcefield_parameterization": True,
        },
        blockers=blockers,
        next_required_step=(
            "DRD2 full-forcefield survival is now available; rebuild hard-decoy challenge slices and clear "
            "target-internal overanchor/multipolar/anchor-support blockers before guarded 100k review."
        ),
    )


def _structure_row(*, structure_scorecard_json: str | Path) -> dict[str, Any]:
    payload = _read_json(structure_scorecard_json)
    summary = _summary(payload)
    if not payload:
        return _row(
            axis="structure_refinement",
            comparator="GALAXY/GalaxyWEB class structure refinement",
            status="missing",
            claim_scope="broad protein structure/refinement parity",
            source_artifacts=[_artifact(structure_scorecard_json)],
            metrics={
                "structure_scorecard_available": False,
                "rmsd_available": False,
                "tm_score_available": False,
                "gdt_available": False,
                "lddt_available": False,
                "dockq_available": False,
            },
            thresholds={
                "requires_rmsd": True,
                "requires_tm_score": True,
                "requires_gdt": True,
                "requires_lddt_or_molprobity": True,
                "requires_dockq_for_complexes": True,
            },
            blockers=["structure_refinement_scorecard_missing"],
            next_required_step=(
                "Build a frozen GALAXY-style structure/refinement scorecard with RMSD, TM-score, GDT, "
                "lDDT/MolProbity, and DockQ/interface RMSD where applicable."
            ),
        )
    blockers = list(summary.get("blockers") or [])
    if _bool(summary.get("claim_promotion_allowed")) is not True:
        blockers.append("claim_promotion_not_allowed")
    return _row(
        axis="structure_refinement",
        comparator="GALAXY/GalaxyWEB class structure refinement",
        status="blocked" if blockers else "pass",
        claim_scope="broad protein structure/refinement parity",
        source_artifacts=[_artifact(structure_scorecard_json)],
        metrics={
            "structure_scorecard_available": True,
            "target_count": _int(summary.get("target_count")),
            "rmsd_pass": _bool(summary.get("rmsd_pass")),
            "tm_score_pass": _bool(summary.get("tm_score_pass")),
            "gdt_pass": _bool(summary.get("gdt_pass")),
            "lddt_pass": _bool(summary.get("lddt_pass")),
            "dockq_pass": _bool(summary.get("dockq_pass")),
            "metric_backend": summary.get("metric_backend"),
            "chain_aware_canonical_ca_matching": _bool(summary.get("chain_aware_canonical_ca_matching")),
            "tm_score_true_metric_available_count": _int(summary.get("tm_score_true_metric_available_count")),
            "gdt_ts_true_metric_available_count": _int(summary.get("gdt_ts_true_metric_available_count")),
            "lddt_ca_true_metric_available_count": _int(summary.get("lddt_ca_true_metric_available_count")),
            "best_tm_score": _float(summary.get("best_tm_score")),
            "best_gdt_ts": _float(summary.get("best_gdt_ts")),
            "best_lddt_ca": _float(summary.get("best_lddt_ca")),
            "molprobity_full_atom_quality_caveat": _bool(summary.get("molprobity_full_atom_quality_caveat")),
        },
        thresholds={
            "requires_rmsd": True,
            "requires_tm_score": True,
            "requires_gdt": True,
            "requires_lddt_or_molprobity": True,
            "requires_dockq_for_complexes": True,
        },
        blockers=sorted(set(blockers)),
        next_required_step="Close all frozen structure/refinement metrics before using GALAXY-level language.",
    )


def _wetlab_row(
    *,
    wetlab_translation_json: str | Path,
    wetlab_allatom_review_json: str | Path,
    commercial_readiness_json: str | Path,
) -> dict[str, Any]:
    wetlab_summary = _summary(_read_json(wetlab_translation_json))
    allatom_review_summary = _summary(_read_json(wetlab_allatom_review_json))
    readiness_summary = _summary(_read_json(commercial_readiness_json))
    translation_ready = _bool(wetlab_summary.get("translation_quality_ready"))
    focus_score = _float(allatom_review_summary.get("translation_gate_focus_score"))
    if focus_score is None:
        focus_score = _float(wetlab_summary.get("translation_gate_focus_score"))
    translation_focus_status = (
        allatom_review_summary.get("translation_gate_focus_status")
        or wetlab_summary.get("translation_gate_focus_status")
    )
    commercial_hard_gate_pass = _bool(allatom_review_summary.get("commercial_hard_gate_pass_v2"))
    if commercial_hard_gate_pass is None:
        commercial_hard_gate_pass = _bool(wetlab_summary.get("commercial_hard_gate_pass"))
    blockers: list[str] = []
    primary = wetlab_summary.get("primary_blocker")
    if primary:
        blockers.append(str(primary))
    blockers.extend(str(item) for item in wetlab_summary.get("failed_quality_axes") or [])
    blockers.extend(f"missing_{item}" for item in wetlab_summary.get("missing_quality_axes") or [])
    blockers.extend(str(item) for item in allatom_review_summary.get("commercial_hard_gate_failed_metrics_v2") or [])
    blockers.extend(f"missing_{item}" for item in allatom_review_summary.get("commercial_hard_gate_missing_metrics_v2") or [])
    if translation_ready is not True:
        blockers.append("translation_quality_not_ready")
    if focus_score is None or focus_score < WETLAB_TRANSLATION_SCORE_MIN:
        blockers.append("translation_focus_score_below_threshold")
    if str(translation_focus_status or "").strip().lower() in {"fail", "blocked"}:
        blockers.append("translation_gate_focus_failed")
    if commercial_hard_gate_pass is False:
        blockers.append("commercial_hard_gate_blocked")
    if _bool(wetlab_summary.get("claim_promotion_allowed")) is not True:
        blockers.append("claim_promotion_not_allowed")
    blockers = sorted(set(blockers))
    next_required_step = str(allatom_review_summary.get("next_required_step") or "").strip()
    if not next_required_step:
        next_required_step = (
            "Close binding-energy proxy, pose RMSD, backmapping consistency, local minimization survival, "
            "and replicate pass fraction before broad wetlab translation claims."
        )
    return _row(
        axis="wetlab_translation",
        comparator="AI discovery platform wetlab translation",
        status="blocked" if blockers else "pass",
        claim_scope="broad prospective wetlab translation/commercial discovery parity",
        source_artifacts=[
            _artifact(wetlab_translation_json),
            _artifact(wetlab_allatom_review_json),
            _artifact(commercial_readiness_json),
        ],
        metrics={
            "translation_quality_ready": translation_ready,
            "translation_gate_focus_status": translation_focus_status,
            "translation_gate_focus_source_status": allatom_review_summary.get("translation_gate_focus_source_status"),
            "translation_gate_focus_hard_status": allatom_review_summary.get("translation_gate_focus_hard_status"),
            "translation_gate_focus_score": focus_score,
            "commercial_hard_gate_pass": commercial_hard_gate_pass,
            "commercial_overall_score_v2": _float(allatom_review_summary.get("commercial_overall_score_v2")),
            "commercial_decision_class_v2": allatom_review_summary.get("commercial_decision_class_v2"),
            "commercial_risk_bucket_v2": allatom_review_summary.get("commercial_risk_bucket_v2"),
            "commercial_primary_upgrade_actions_v2": allatom_review_summary.get("commercial_primary_upgrade_actions_v2") or [],
            "best_mean_min_distance_A": _float(wetlab_summary.get("best_mean_min_distance_A")),
            "best_binding_energy_proxy": _float(wetlab_summary.get("best_binding_energy_proxy")),
            "core_commercial_lane_score": _float(readiness_summary.get("core_commercial_lane_score")),
            "all_category_expansion_score": _float(readiness_summary.get("all_category_expansion_score")),
            "ligand_scaleup_commercialization_ready_suite_count": _int(
                readiness_summary.get("ligand_scaleup_commercialization_ready_suite_count")
            ),
            "ligand_scaleup_suite_count": _int(readiness_summary.get("ligand_scaleup_suite_count")),
        },
        thresholds={
            "translation_gate_focus_score_min": WETLAB_TRANSLATION_SCORE_MIN,
            "requires_pose_rmsd": True,
            "requires_backmapping_consistency": True,
            "requires_local_minimization_survival": True,
            "requires_replicate_pass_fraction": True,
        },
        blockers=blockers,
        next_required_step=next_required_step,
    )


def build_scorecard(
    *,
    local_accuracy_json: str | Path = DEFAULT_LOCAL_ACCURACY_JSON,
    openmm_external_json: str | Path = DEFAULT_OPENMM_EXTERNAL_JSON,
    openmm_stability_json: str | Path = DEFAULT_OPENMM_STABILITY_JSON,
    gpcr_ranking_json: str | Path = DEFAULT_GPCR_RANKING_JSON,
    gpcr_core_diagnostics_json: str | Path = DEFAULT_GPCR_CORE_DIAGNOSTICS_JSON,
    gpcr_drd2_repair_json: str | Path = DEFAULT_GPCR_DRD2_REPAIR_JSON,
    gpcr_drd2_backmapping_support_json: str | Path = DEFAULT_GPCR_DRD2_BACKMAPPING_SUPPORT_JSON,
    gpcr_drd2_hard_decoy_envelope_json: str | Path = DEFAULT_GPCR_DRD2_HARD_DECOY_ENVELOPE_JSON,
    gpcr_drd2_full_forcefield_readiness_json: str | Path = DEFAULT_GPCR_DRD2_FULL_FORCEFIELD_READINESS_JSON,
    gpcr_drd2_parameterization_probe_json: str | Path = DEFAULT_GPCR_DRD2_PARAMETERIZATION_PROBE_JSON,
    gpcr_drd2_protein_repair_json: str | Path = DEFAULT_GPCR_DRD2_PROTEIN_REPAIR_JSON,
    gpcr_pose_gap_json: str | Path = DEFAULT_GPCR_POSE_GAP_JSON,
    structure_scorecard_json: str | Path = DEFAULT_STRUCTURE_SCORECARD_JSON,
    wetlab_translation_json: str | Path = DEFAULT_WETLAB_TRANSLATION_JSON,
    wetlab_allatom_review_json: str | Path = DEFAULT_WETLAB_ALLATOM_REVIEW_JSON,
    commercial_readiness_json: str | Path = DEFAULT_COMMERCIAL_READINESS_JSON,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    rows = [
        _physics_row(
            local_accuracy_json=local_accuracy_json,
            openmm_external_json=openmm_external_json,
            openmm_stability_json=openmm_stability_json,
        ),
        _ligand_ranking_row(
            gpcr_ranking_json=gpcr_ranking_json,
            gpcr_core_diagnostics_json=gpcr_core_diagnostics_json,
        ),
        _pose_geometry_row(
            gpcr_drd2_repair_json=gpcr_drd2_repair_json,
            gpcr_drd2_backmapping_support_json=gpcr_drd2_backmapping_support_json,
            gpcr_drd2_hard_decoy_envelope_json=gpcr_drd2_hard_decoy_envelope_json,
            gpcr_drd2_full_forcefield_readiness_json=gpcr_drd2_full_forcefield_readiness_json,
            gpcr_drd2_parameterization_probe_json=gpcr_drd2_parameterization_probe_json,
            gpcr_drd2_protein_repair_json=gpcr_drd2_protein_repair_json,
            gpcr_pose_gap_json=gpcr_pose_gap_json,
        ),
        _structure_row(structure_scorecard_json=structure_scorecard_json),
        _wetlab_row(
            wetlab_translation_json=wetlab_translation_json,
            wetlab_allatom_review_json=wetlab_allatom_review_json,
            commercial_readiness_json=commercial_readiness_json,
        ),
    ]
    blocked_rows = [row for row in rows if row["status"] == "blocked"]
    missing_rows = [row for row in rows if row["status"] == "missing"]
    restricted_rows = [row for row in rows if row["status"] == "restricted_pass"]
    pass_rows = [row for row in rows if row["status"] == "pass"]
    top_blockers = []
    for row in rows:
        for blocker in row["blockers"][:5]:
            top_blockers.append(f"{row['axis']}:{blocker}")
    overall_allowed = len(blocked_rows) == 0 and len(missing_rows) == 0
    status = "green" if overall_allowed else "blocked_accuracy_parity"
    if overall_allowed:
        restricted_estimate = "80-85"
        broad_accuracy_estimate = "70-80"
        broad_platform_estimate = "55-65"
        next_required_step = (
            "Maintain the green tracked scorecard, keep scorer/router/platform deployment as a separate guardrail, "
            "and expand external held-out coverage before making unbounded commercial-platform claims."
        )
    else:
        restricted_estimate = "70-75"
        broad_accuracy_estimate = "40-50"
        broad_platform_estimate = "35-45"
        next_required_step = (
            "Keep API/productization deferred. First close A0/A1: maintain this scorecard, repair GPCR "
            "pose-supported ranking, then expand OpenMM and structure/refinement parity suites."
        )
    summary = {
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "row_count": len(rows),
        "pass_row_count": len(pass_rows),
        "restricted_pass_row_count": len(restricted_rows),
        "blocked_row_count": len(blocked_rows),
        "missing_row_count": len(missing_rows),
        "overall_commercial_tool_accuracy_parity_allowed": overall_allowed,
        "openmm_class_claim_allowed": rows[0]["commercial_parity_claim_allowed"],
        "schrodinger_class_claim_allowed": rows[1]["commercial_parity_claim_allowed"],
        "galaxy_class_claim_allowed": rows[3]["commercial_parity_claim_allowed"],
        "ai_discovery_platform_claim_allowed": rows[4]["commercial_parity_claim_allowed"],
        "current_restricted_local_delivery_estimate_pct": restricted_estimate,
        "current_broad_accuracy_parity_estimate_pct": broad_accuracy_estimate,
        "current_broad_commercial_platform_estimate_pct": broad_platform_estimate,
        "top_blockers": top_blockers[:12],
        "next_required_step": next_required_step,
    }
    return {
        "packet_type": "accuracy_parity_scorecard",
        "summary": summary,
        "rows": rows,
        "claim_boundary": {
            "commercial_tool_accuracy_parity_allowed": overall_allowed,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
            "scorecard_rows_must_map_to_frozen_artifacts": True,
            "api_productization_out_of_scope": True,
        },
    }


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Accuracy Parity Scorecard",
        "",
        "## Summary",
        "",
        f"- status: `{summary['status']}`",
        f"- overall_commercial_tool_accuracy_parity_allowed: `{str(summary['overall_commercial_tool_accuracy_parity_allowed']).lower()}`",
        f"- pass/restricted/blocked/missing: `{summary['pass_row_count']}` / `{summary['restricted_pass_row_count']}` / `{summary['blocked_row_count']}` / `{summary['missing_row_count']}`",
        f"- restricted_local_delivery_estimate_pct: `{summary['current_restricted_local_delivery_estimate_pct']}`",
        f"- broad_accuracy_parity_estimate_pct: `{summary['current_broad_accuracy_parity_estimate_pct']}`",
        f"- broad_commercial_platform_estimate_pct: `{summary['current_broad_commercial_platform_estimate_pct']}`",
        "",
        "## Axis Rows",
        "",
        "| Axis | Comparator | Status | Claim allowed | Key blockers |",
        "|---|---|---|---:|---|",
    ]
    for row in payload["rows"]:
        blockers = ", ".join(f"`{item}`" for item in row["blockers"][:4]) or "none"
        lines.append(
            f"| `{row['axis']}` | {row['comparator']} | `{row['status']}` | "
            f"`{str(row['commercial_parity_claim_allowed']).lower()}` | {blockers} |"
        )
    lines.extend(["", "## Metrics", ""])
    for row in payload["rows"]:
        lines.extend([f"### {row['axis']}", ""])
        lines.append(f"- claim_scope: `{row['claim_scope']}`")
        lines.append(f"- status: `{row['status']}`")
        lines.append(f"- source_artifacts: `{', '.join(row['source_artifacts'])}`")
        for key, value in row["metrics"].items():
            lines.append(f"- {key}: `{value}`")
        lines.append(f"- next_required_step: {row['next_required_step']}")
        lines.append("")
    lines.extend(["## Next Required Step", "", f"- {summary['next_required_step']}", ""])
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the commercial-tool accuracy parity scorecard.")
    parser.add_argument("--local-accuracy-json", default=DEFAULT_LOCAL_ACCURACY_JSON)
    parser.add_argument("--openmm-external-json", default=DEFAULT_OPENMM_EXTERNAL_JSON)
    parser.add_argument("--openmm-stability-json", default=DEFAULT_OPENMM_STABILITY_JSON)
    parser.add_argument("--gpcr-ranking-json", default=DEFAULT_GPCR_RANKING_JSON)
    parser.add_argument("--gpcr-core-diagnostics-json", default=DEFAULT_GPCR_CORE_DIAGNOSTICS_JSON)
    parser.add_argument("--gpcr-drd2-repair-json", default=DEFAULT_GPCR_DRD2_REPAIR_JSON)
    parser.add_argument("--gpcr-drd2-backmapping-support-json", default=DEFAULT_GPCR_DRD2_BACKMAPPING_SUPPORT_JSON)
    parser.add_argument("--gpcr-drd2-hard-decoy-envelope-json", default=DEFAULT_GPCR_DRD2_HARD_DECOY_ENVELOPE_JSON)
    parser.add_argument(
        "--gpcr-drd2-full-forcefield-readiness-json",
        default=DEFAULT_GPCR_DRD2_FULL_FORCEFIELD_READINESS_JSON,
    )
    parser.add_argument("--gpcr-drd2-parameterization-probe-json", default=DEFAULT_GPCR_DRD2_PARAMETERIZATION_PROBE_JSON)
    parser.add_argument("--gpcr-drd2-protein-repair-json", default=DEFAULT_GPCR_DRD2_PROTEIN_REPAIR_JSON)
    parser.add_argument("--gpcr-pose-gap-json", default=DEFAULT_GPCR_POSE_GAP_JSON)
    parser.add_argument("--structure-scorecard-json", default=DEFAULT_STRUCTURE_SCORECARD_JSON)
    parser.add_argument("--wetlab-translation-json", default=DEFAULT_WETLAB_TRANSLATION_JSON)
    parser.add_argument("--wetlab-allatom-review-json", default=DEFAULT_WETLAB_ALLATOM_REVIEW_JSON)
    parser.add_argument("--commercial-readiness-json", default=DEFAULT_COMMERCIAL_READINESS_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_scorecard(
        local_accuracy_json=args.local_accuracy_json,
        openmm_external_json=args.openmm_external_json,
        openmm_stability_json=args.openmm_stability_json,
        gpcr_ranking_json=args.gpcr_ranking_json,
        gpcr_core_diagnostics_json=args.gpcr_core_diagnostics_json,
        gpcr_drd2_repair_json=args.gpcr_drd2_repair_json,
        gpcr_drd2_backmapping_support_json=args.gpcr_drd2_backmapping_support_json,
        gpcr_drd2_hard_decoy_envelope_json=args.gpcr_drd2_hard_decoy_envelope_json,
        gpcr_drd2_full_forcefield_readiness_json=args.gpcr_drd2_full_forcefield_readiness_json,
        gpcr_drd2_parameterization_probe_json=args.gpcr_drd2_parameterization_probe_json,
        gpcr_drd2_protein_repair_json=args.gpcr_drd2_protein_repair_json,
        gpcr_pose_gap_json=args.gpcr_pose_gap_json,
        structure_scorecard_json=args.structure_scorecard_json,
        wetlab_translation_json=args.wetlab_translation_json,
        wetlab_allatom_review_json=args.wetlab_allatom_review_json,
        commercial_readiness_json=args.commercial_readiness_json,
    )
    _write_json(args.out_json, payload)
    out_md = _resolve(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_md(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
