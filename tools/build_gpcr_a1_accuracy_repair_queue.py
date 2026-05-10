#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

from tools.lib.artifacts import (
    artifact as _artifact,
    read_json as _read_json,
    resolve as _resolve,
    summary as _summary,
    write_json as _write_json,
)

DEFAULT_ACCURACY_SCORECARD_JSON = "runs/accuracy_parity_scorecard_current.json"
DEFAULT_DRD2_REPAIR_JSON = "runs/gpcr_drd2_pose_generation_repair_packet_current.json"
DEFAULT_DRD2_BACKMAPPING_SUPPORT_JSON = "runs/gpcr_drd2_atom_typed_backmapping_support_current.json"
DEFAULT_DRD2_FULL_FORCEFIELD_READINESS_JSON = "runs/gpcr_drd2_full_forcefield_minimization_readiness_current.json"
DEFAULT_DRD2_PARAMETERIZATION_PROBE_JSON = "runs/gpcr_drd2_openmm_forcefield_parameterization_probe_current.json"
DEFAULT_DRD2_PROTEIN_REPAIR_JSON = "runs/gpcr_drd2_protein_amber14_parameterization_repair_current.json"
DEFAULT_DRD2_HARD_DECOY_ENVELOPE_JSON = "runs/gpcr_drd2_hard_decoy_penalty_envelope_current.json"
DEFAULT_DRD2_WEAKBASE_REPLAY_JSON = "runs/gpcr_drd2_weakbase_false_support_shadow_replay_summary_current.json"
DEFAULT_HTR2A_REPAIR_PACKET_JSON = "runs/gpcr_htr2a_anchor_support_repair_packet_current.json"
DEFAULT_HTR2A_TOPOLOGY_PROBE_JSON = "runs/gpcr_htr2a_atom_typed_topology_probe_current.json"
DEFAULT_HTR2A_LIFE_SCIENCE_EVIDENCE_JSON = "runs/gpcr_htr2a_life_science_evidence_packet_current.json"
DEFAULT_HTR2A_TOPOLOGY_REPLAY_JSON = "runs/gpcr_htr2a_topology_support_shadow_replay_summary_current.json"
DEFAULT_OPRM1_LIFE_SCIENCE_EVIDENCE_JSON = "runs/gpcr_oprm1_life_science_evidence_packet_current.json"
DEFAULT_OPRM1_TOPOLOGY_REPLAY_JSON = "runs/gpcr_oprm1_topology_pose_shadow_replay_summary_current.json"
DEFAULT_SHADOW_CLAIM_REVIEW_JSON = "runs/gpcr_guarded_shadow_claim_review_current.json"
DEFAULT_POSE_GAP_JSON = "runs/gpcr_false_support_discriminator_v16_adaptive_frozen_gap_packet_current.json"
DEFAULT_RANKING_JSON = "runs/gpcr_guarded_100k_rank_failure_diagnostics_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_a1_accuracy_repair_queue_current.json"
DEFAULT_OUT_MD = "runs/gpcr_a1_accuracy_repair_queue_current.md"


def _float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    value_float = _float(value)
    return int(value_float) if value_float is not None else None


def _target_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("target_summaries", [])
    return rows if isinstance(rows, list) else []


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
            "ranking_unique_auc": _float(stage6.get("ranking_unique_auc") or stage6.get("ranking_auc")),
            "ranking_pr_auc": _float(stage6.get("ranking_pr_auc")),
            "ranking_pr_auc_ci_low": _float(stage6.get("ranking_pr_auc_ci_low")),
            "ranking_topk_hit_rate": _float(stage6.get("ranking_topk_hit_rate")),
            "ranking_positive_count": _int(stage6.get("ranking_positive_count")),
            "ranking_score_col_used": stage6.get("ranking_score_col_used"),
        }
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    metrics_ci_unique = payload.get("metrics_ci_unique") if isinstance(payload.get("metrics_ci_unique"), dict) else {}
    metrics_ci = payload.get("metrics_ci") if isinstance(payload.get("metrics_ci"), dict) else {}
    pr_ci = metrics_ci_unique.get("pr_auc") if isinstance(metrics_ci_unique.get("pr_auc"), dict) else {}
    if not pr_ci:
        pr_ci = metrics_ci.get("pr_auc") if isinstance(metrics_ci.get("pr_auc"), dict) else {}
    return {
        "ranking_unique_auc": _float(metrics.get("roc_auc_unique_key") or metrics.get("roc_auc")),
        "ranking_pr_auc": _float(metrics.get("pr_auc_unique_key") or metrics.get("pr_auc")),
        "ranking_pr_auc_ci_low": _float(pr_ci.get("low")),
        "ranking_topk_hit_rate": _topk_hit_rate(payload, k=20),
        "ranking_positive_count": _int(metrics.get("positive_count_unique_key") or metrics.get("positive_count")),
        "ranking_score_col_used": metrics.get("probability_score_col_used") or payload.get("score_col"),
    }


def _queue_row(
    *,
    priority: int,
    repair_id: str,
    target: str,
    ligand_id: str,
    blocker_group: str,
    source_artifacts: list[str],
    current_evidence: dict[str, Any],
    acceptance_checks: list[str],
    next_action: str,
    status: str = "open",
) -> dict[str, Any]:
    return {
        "priority": priority,
        "repair_id": repair_id,
        "target": target,
        "ligand_id": ligand_id,
        "blocker_group": blocker_group,
        "status": status,
        "claim_promotion_allowed": False,
        "source_artifacts": source_artifacts,
        "current_evidence": current_evidence,
        "acceptance_checks": acceptance_checks,
        "next_action": next_action,
    }


def build_queue(
    *,
    accuracy_scorecard_json: str | Path = DEFAULT_ACCURACY_SCORECARD_JSON,
    drd2_repair_json: str | Path = DEFAULT_DRD2_REPAIR_JSON,
    drd2_backmapping_support_json: str | Path = DEFAULT_DRD2_BACKMAPPING_SUPPORT_JSON,
    drd2_full_forcefield_readiness_json: str | Path = DEFAULT_DRD2_FULL_FORCEFIELD_READINESS_JSON,
    drd2_parameterization_probe_json: str | Path = DEFAULT_DRD2_PARAMETERIZATION_PROBE_JSON,
    drd2_protein_repair_json: str | Path = DEFAULT_DRD2_PROTEIN_REPAIR_JSON,
    drd2_hard_decoy_envelope_json: str | Path = DEFAULT_DRD2_HARD_DECOY_ENVELOPE_JSON,
    drd2_weakbase_replay_json: str | Path = DEFAULT_DRD2_WEAKBASE_REPLAY_JSON,
    htr2a_repair_packet_json: str | Path = DEFAULT_HTR2A_REPAIR_PACKET_JSON,
    htr2a_topology_probe_json: str | Path = DEFAULT_HTR2A_TOPOLOGY_PROBE_JSON,
    htr2a_life_science_evidence_json: str | Path = DEFAULT_HTR2A_LIFE_SCIENCE_EVIDENCE_JSON,
    htr2a_topology_replay_json: str | Path = DEFAULT_HTR2A_TOPOLOGY_REPLAY_JSON,
    oprm1_life_science_evidence_json: str | Path = DEFAULT_OPRM1_LIFE_SCIENCE_EVIDENCE_JSON,
    oprm1_topology_replay_json: str | Path = DEFAULT_OPRM1_TOPOLOGY_REPLAY_JSON,
    shadow_claim_review_json: str | Path = DEFAULT_SHADOW_CLAIM_REVIEW_JSON,
    pose_gap_json: str | Path = DEFAULT_POSE_GAP_JSON,
    ranking_json: str | Path = DEFAULT_RANKING_JSON,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    scorecard = _read_json(accuracy_scorecard_json)
    drd2 = _read_json(drd2_repair_json)
    support = _read_json(drd2_backmapping_support_json)
    readiness = _read_json(drd2_full_forcefield_readiness_json)
    parameterization_probe = _read_json(drd2_parameterization_probe_json)
    protein_repair = _read_json(drd2_protein_repair_json)
    hard_decoy_envelope = _read_json(drd2_hard_decoy_envelope_json)
    drd2_weakbase_replay = _read_json(drd2_weakbase_replay_json)
    htr2a_repair_packet = _read_json(htr2a_repair_packet_json)
    htr2a_topology_probe = _read_json(htr2a_topology_probe_json)
    htr2a_life_science_evidence = _read_json(htr2a_life_science_evidence_json)
    htr2a_topology_replay = _read_json(htr2a_topology_replay_json)
    oprm1_life_science_evidence = _read_json(oprm1_life_science_evidence_json)
    oprm1_topology_replay = _read_json(oprm1_topology_replay_json)
    shadow_claim_review = _read_json(shadow_claim_review_json)
    pose_gap = _read_json(pose_gap_json)
    ranking = _read_json(ranking_json)
    drd2_summary = _summary(drd2)
    support_summary = _summary(support)
    readiness_summary = _summary(readiness)
    parameterization_summary = _summary(parameterization_probe)
    protein_repair_summary = _summary(protein_repair)
    hard_decoy_envelope_summary = _summary(hard_decoy_envelope)
    drd2_weakbase_replay_summary = _summary(drd2_weakbase_replay)
    htr2a_repair_summary = _summary(htr2a_repair_packet)
    htr2a_topology_probe_summary = _summary(htr2a_topology_probe)
    htr2a_life_science_summary = _summary(htr2a_life_science_evidence)
    htr2a_topology_replay_summary = _summary(htr2a_topology_replay)
    oprm1_life_science_summary = _summary(oprm1_life_science_evidence)
    oprm1_topology_replay_summary = _summary(oprm1_topology_replay)
    shadow_claim_review_summary = _summary(shadow_claim_review)
    ranking_summary = _ranking_summary(ranking)
    target_rows = _target_rows(pose_gap)
    support_status = str(support_summary.get("status") or "").strip()
    support_next_required_step = str(support_summary.get("next_required_step") or "").strip()
    selected_row_count = _int(support_summary.get("selected_row_count"))
    blocked_row_count = _int(support_summary.get("blocked_row_count"))
    positive_blockers = [str(blocker) for blocker in support_summary.get("positive_blockers") or []]
    positive_backmapping_atom_coverage_ratio = _float(support_summary.get("positive_backmapping_atom_coverage_ratio"))
    if positive_backmapping_atom_coverage_ratio is None:
        positive_backmapping_atom_coverage_ratio = _float(drd2_summary.get("positive_backmapping_atom_coverage_ratio"))
    positive_full_atom_typed_backmapping_ready = bool(support_summary.get("positive_full_atom_typed_backmapping_ready"))
    positive_minimum_coverage_gate_pass = bool(support_summary.get("positive_minimum_coverage_gate_pass"))
    positive_pose_preservation_rmsd_A_p90 = _float(support_summary.get("positive_pose_preservation_rmsd_A_p90"))
    positive_local_minimization_survival_fraction = _float(
        support_summary.get("positive_local_minimization_survival_fraction")
    )
    positive_local_minimization_survival_engine_kind = str(
        support_summary.get("positive_local_minimization_survival_engine_kind") or ""
    ).strip()
    positive_local_minimization_survival_claim_scope = str(
        support_summary.get("positive_local_minimization_survival_claim_scope") or ""
    ).strip()
    positive_local_minimization_survival_hard_decoy_evidence_allowed = bool(
        support_summary.get("positive_local_minimization_survival_hard_decoy_evidence_allowed")
    )
    positive_local_minimization_survival_source_blockers = [
        str(blocker) for blocker in support_summary.get("positive_local_minimization_survival_source_blockers") or []
    ]
    hard_decoy_rebuild_allowed = bool(support_summary.get("hard_decoy_rebuild_allowed"))
    claim_promotion_allowed = bool(support_summary.get("claim_promotion_allowed"))
    scorer_apply_allowed = bool(support_summary.get("scorer_apply_allowed"))
    guarded_100k_rerun_allowed = bool(support_summary.get("guarded_100k_rerun_allowed"))
    full_forcefield_minimization_ready = bool(readiness_summary.get("full_forcefield_minimization_ready"))
    protein_parameterization_available = bool(readiness_summary.get("protein_parameterization_available"))
    ligand_parameterization_available = bool(readiness_summary.get("ligand_parameterization_available"))
    ligand_template_parameterization_available = bool(
        parameterization_summary.get("ligand_template_parameterization_available")
    )
    local_parameterization_probe_partial = bool(parameterization_summary.get("local_probe_partial"))
    claim_grade_parameterization_ready = bool(parameterization_summary.get("claim_grade_parameterization_ready"))
    protein_missing_heavy_atom_residue_count = _int(protein_repair_summary.get("missing_heavy_atom_residue_count"))
    protein_incomplete_histidine_count = _int(protein_repair_summary.get("incomplete_histidine_count"))
    protein_claim_grade_repair_allowed = bool(protein_repair_summary.get("claim_grade_repair_allowed"))
    missing_forcefield_dependencies = [str(item) for item in readiness_summary.get("missing_dependencies") or []]
    missing_forcefield_assets = [str(item) for item in readiness_summary.get("missing_assets") or []]
    support_evidence = {
        "support_status": support_status or None,
        "selected_row_count": selected_row_count,
        "blocked_row_count": blocked_row_count,
        "positive_backmapping_atom_coverage_ratio": positive_backmapping_atom_coverage_ratio,
        "positive_full_atom_typed_backmapping_ready": positive_full_atom_typed_backmapping_ready,
        "positive_minimum_coverage_gate_pass": positive_minimum_coverage_gate_pass,
        "positive_pose_preservation_rmsd_A_p90": positive_pose_preservation_rmsd_A_p90,
        "positive_local_minimization_survival_fraction": positive_local_minimization_survival_fraction,
        "positive_local_minimization_survival_engine_kind": positive_local_minimization_survival_engine_kind or None,
        "positive_local_minimization_survival_claim_scope": positive_local_minimization_survival_claim_scope or None,
        "positive_local_minimization_survival_hard_decoy_evidence_allowed": (
            positive_local_minimization_survival_hard_decoy_evidence_allowed
        ),
        "positive_local_minimization_survival_source_blockers": (
            positive_local_minimization_survival_source_blockers
        ),
        "hard_decoy_rebuild_allowed": hard_decoy_rebuild_allowed,
        "claim_promotion_allowed": claim_promotion_allowed,
        "scorer_apply_allowed": scorer_apply_allowed,
        "guarded_100k_rerun_allowed": guarded_100k_rerun_allowed,
        "full_forcefield_readiness_status": readiness_summary.get("status"),
        "full_forcefield_minimization_ready": full_forcefield_minimization_ready,
        "protein_parameterization_available": protein_parameterization_available,
        "ligand_parameterization_available": ligand_parameterization_available,
        "ligand_template_parameterization_available": ligand_template_parameterization_available,
        "local_parameterization_probe_partial": local_parameterization_probe_partial,
        "claim_grade_parameterization_ready": claim_grade_parameterization_ready,
        "protein_missing_heavy_atom_residue_count": protein_missing_heavy_atom_residue_count,
        "protein_incomplete_histidine_count": protein_incomplete_histidine_count,
        "protein_claim_grade_repair_allowed": protein_claim_grade_repair_allowed,
        "missing_forcefield_dependencies": missing_forcefield_dependencies,
        "missing_forcefield_assets": missing_forcefield_assets,
        "positive_blockers": positive_blockers,
        "next_required_step": support_next_required_step or None,
    }

    source_artifacts = {
        "scorecard": _artifact(accuracy_scorecard_json),
        "drd2_repair": _artifact(drd2_repair_json),
        "drd2_backmapping_support": _artifact(drd2_backmapping_support_json),
        "drd2_full_forcefield_readiness": _artifact(drd2_full_forcefield_readiness_json),
        "drd2_parameterization_probe": _artifact(drd2_parameterization_probe_json),
        "drd2_protein_repair": _artifact(drd2_protein_repair_json),
        "drd2_hard_decoy_envelope": _artifact(drd2_hard_decoy_envelope_json),
        "drd2_weakbase_replay": _artifact(drd2_weakbase_replay_json),
        "htr2a_repair_packet": _artifact(htr2a_repair_packet_json),
        "htr2a_topology_probe": _artifact(htr2a_topology_probe_json),
        "htr2a_life_science_evidence": _artifact(htr2a_life_science_evidence_json),
        "htr2a_topology_replay": _artifact(htr2a_topology_replay_json),
        "oprm1_life_science_evidence": _artifact(oprm1_life_science_evidence_json),
        "oprm1_topology_replay": _artifact(oprm1_topology_replay_json),
        "shadow_claim_review": _artifact(shadow_claim_review_json),
        "pose_gap": _artifact(pose_gap_json),
        "ranking": _artifact(ranking_json),
    }

    forcefield_repair_done = bool(
        full_forcefield_minimization_ready
        and protein_parameterization_available
        and ligand_parameterization_available
        and claim_grade_parameterization_ready
        and positive_local_minimization_survival_fraction is not None
        and positive_local_minimization_survival_hard_decoy_evidence_allowed
        and hard_decoy_rebuild_allowed
    )
    hard_decoy_envelope_status = str(hard_decoy_envelope_summary.get("status") or "").strip()
    hard_decoy_slice_rebuild_done = bool(
        forcefield_repair_done
        and hard_decoy_envelope_status == "slice_pairwise_green_diagnostic_only"
        and _int(hard_decoy_envelope_summary.get("bounded_best_positive_rank")) == 1
        and _int(hard_decoy_envelope_summary.get("bounded_best_decoys_above_positive_count")) == 0
        and _int(hard_decoy_envelope_summary.get("bounded_best_valid_anchor_challenge_above_positive_count")) == 0
    )
    drd2_weakbase_replay_status = str(drd2_weakbase_replay_summary.get("status") or "").strip()
    htr2a_topology_replay_status = str(htr2a_topology_replay_summary.get("status") or "").strip()
    htr2a_topology_replay_done = bool(
        htr2a_topology_replay_status
        == "htr2a_topology_support_shadow_replay_selected_slice_green_claim_locked"
        and _int(htr2a_topology_replay_summary.get("selected_htr2a_target_rank")) == 1
        and _int(htr2a_topology_replay_summary.get("selected_htr2a_decoys_above_positive")) == 0
        and _int(htr2a_topology_replay_summary.get("selected_non_htr2a_regression_count")) == 0
        and not bool(htr2a_topology_replay_summary.get("claim_promotion_allowed"))
        and not bool(htr2a_topology_replay_summary.get("scorer_apply_allowed"))
        and not bool(htr2a_topology_replay_summary.get("guarded_100k_rerun_allowed"))
    )
    oprm1_topology_replay_status = str(oprm1_topology_replay_summary.get("status") or "").strip()
    oprm1_topology_replay_done = bool(
        oprm1_topology_replay_status == "oprm1_topology_pose_shadow_replay_selected_slice_green_claim_locked"
        and _int(oprm1_topology_replay_summary.get("selected_oprm1_target_rank")) == 1
        and _int(oprm1_topology_replay_summary.get("selected_oprm1_decoys_above_positive")) == 0
        and _int(oprm1_topology_replay_summary.get("selected_non_oprm1_regression_count")) == 0
        and not bool(oprm1_topology_replay_summary.get("claim_promotion_allowed"))
        and not bool(oprm1_topology_replay_summary.get("scorer_apply_allowed"))
        and not bool(oprm1_topology_replay_summary.get("guarded_100k_rerun_allowed"))
    )
    guarded_review_ready = bool(hard_decoy_slice_rebuild_done and htr2a_topology_replay_done and oprm1_topology_replay_done)
    shadow_review_status = str(shadow_claim_review_summary.get("status") or "").strip()
    shadow_review_blockers = [str(item) for item in shadow_claim_review_summary.get("blockers") or []]
    shadow_review_passed = bool(shadow_claim_review_summary.get("guarded_shadow_claim_review_passed"))
    ranking_pr_auc = _float(ranking_summary.get("ranking_pr_auc"))
    ranking_pr_auc_ci_low = _float(ranking_summary.get("ranking_pr_auc_ci_low"))
    ranking_topk_hit_rate = _float(ranking_summary.get("ranking_topk_hit_rate"))
    full_guarded_review_passed = bool(
        guarded_review_ready
        and ranking_pr_auc is not None
        and ranking_pr_auc >= 0.55
        and ranking_pr_auc_ci_low is not None
        and ranking_pr_auc_ci_low >= 0.45
        and ranking_topk_hit_rate is not None
        and ranking_topk_hit_rate >= 0.50
    )
    rows: list[dict[str, Any]] = [
        _queue_row(
            priority=1,
            repair_id="drd2_claim_grade_full_forcefield_local_minimization",
            target=str(drd2_summary.get("target") or "CHEMBL217_DRD2_HUMAN"),
            ligand_id=str(drd2_summary.get("positive_ligand_id") or "CHEMBL301265"),
            blocker_group="claim_grade_forcefield_evidence",
            source_artifacts=[
                source_artifacts["drd2_repair"],
                source_artifacts["drd2_backmapping_support"],
                source_artifacts["drd2_full_forcefield_readiness"],
                source_artifacts["drd2_parameterization_probe"],
                source_artifacts["drd2_protein_repair"],
                source_artifacts["scorecard"],
            ],
            current_evidence={
                **support_evidence,
                "positive_global_rank": _int(drd2_summary.get("positive_global_rank")),
                "positive_within_target_rank": _int(drd2_summary.get("positive_within_target_rank")),
                "decoys_above_positive_count": _int(drd2_summary.get("decoys_above_positive_count")),
                "positive_ligand_frame_atom_count": _int(drd2_summary.get("positive_ligand_frame_atom_count")),
                "positive_smiles_heavy_atom_count": _int(drd2_summary.get("positive_smiles_heavy_atom_count")),
            },
            acceptance_checks=[
                "full_forcefield_minimization_ready flips true from a real OpenMM protein-ligand System build",
                "protein_parameterization_available and ligand_parameterization_available both flip true",
                "positive_local_minimization_survival_claim_scope becomes full_protein_ligand_forcefield",
                "positive_local_minimization_survival_fraction is populated from claim-grade full-forcefield local-minimization evidence",
                "positive_blockers clears local_minimization_survival_not_claim_grade and local_minimization_survival_missing",
                "hard_decoy_rebuild_allowed flips true before any hard-decoy rebuild or guarded 100k review",
            ],
            next_action=(
                "Completed: DRD2 now has integrated OpenMM protein-ligand parameterization and claim-grade "
                "full-forcefield local-minimization survival evidence; move to hard-decoy slice rebuild."
                if forcefield_repair_done
                else f"Support packet is still `{support_status or 'drd2_atom_typed_backmapping_blocked'}` "
                f"(`positive_backmapping_atom_coverage_ratio={positive_backmapping_atom_coverage_ratio}`, "
                f"`positive_full_atom_typed_backmapping_ready={str(positive_full_atom_typed_backmapping_ready).lower()}`, "
                f"`positive_pose_preservation_rmsd_A_p90={positive_pose_preservation_rmsd_A_p90}`, "
                f"`positive_local_minimization_survival_fraction={positive_local_minimization_survival_fraction}`, "
                f"`positive_local_minimization_survival_claim_scope={positive_local_minimization_survival_claim_scope or None}`, "
                f"`hard_decoy_rebuild_allowed={str(hard_decoy_rebuild_allowed).lower()}`); readiness probe is "
                f"`{readiness_summary.get('status') or 'missing'}` "
                f"(`full_forcefield_minimization_ready={str(full_forcefield_minimization_ready).lower()}`, "
                f"`protein_parameterization_available={str(protein_parameterization_available).lower()}`, "
                f"`ligand_parameterization_available={str(ligand_parameterization_available).lower()}`, "
                f"`ligand_template_parameterization_available={str(ligand_template_parameterization_available).lower()}`, "
                f"`local_parameterization_probe_partial={str(local_parameterization_probe_partial).lower()}`, "
                f"`claim_grade_parameterization_ready={str(claim_grade_parameterization_ready).lower()}`, "
                f"`protein_missing_heavy_atom_residue_count={protein_missing_heavy_atom_residue_count}`, "
                f"`protein_incomplete_histidine_count={protein_incomplete_histidine_count}`, "
                f"`missing_dependencies={missing_forcefield_dependencies}`, "
                f"`missing_assets={missing_forcefield_assets}`). "
                "Build a real protein-ligand forcefield parameterization path, then rerun local-min survival before "
                "reopening hard-decoy rebuild or guarded 100k review."
            ),
            status="completed" if forcefield_repair_done else "open",
        ),
        _queue_row(
            priority=2,
            repair_id="drd2_hard_decoy_slice_rebuild",
            target=str(drd2_summary.get("target") or "CHEMBL217_DRD2_HUMAN"),
            ligand_id=str(drd2_summary.get("positive_ligand_id") or "CHEMBL301265"),
            blocker_group="hard_decoy_design",
            source_artifacts=[
                source_artifacts["drd2_repair"],
                source_artifacts["drd2_backmapping_support"],
                source_artifacts["drd2_full_forcefield_readiness"],
                source_artifacts["drd2_parameterization_probe"],
                source_artifacts["drd2_protein_repair"],
                source_artifacts["drd2_hard_decoy_envelope"],
                source_artifacts["drd2_weakbase_replay"],
                source_artifacts["ranking"],
            ],
            current_evidence={
                **support_evidence,
                "hard_decoy_envelope_status": hard_decoy_envelope_status or None,
                "hard_decoy_bounded_best_positive_rank": _int(
                    hard_decoy_envelope_summary.get("bounded_best_positive_rank")
                ),
                "hard_decoy_bounded_best_decoys_above_positive_count": _int(
                    hard_decoy_envelope_summary.get("bounded_best_decoys_above_positive_count")
                ),
                "hard_decoy_bounded_best_valid_anchor_challenge_above_positive_count": _int(
                    hard_decoy_envelope_summary.get("bounded_best_valid_anchor_challenge_above_positive_count")
                ),
                "hard_decoy_bounded_best_penalty_weight": _float(
                    hard_decoy_envelope_summary.get("bounded_best_penalty_weight")
                ),
                "hard_decoy_bounded_best_support_weight": _float(
                    hard_decoy_envelope_summary.get("bounded_best_support_weight")
                ),
                "hard_decoy_next_required_step": hard_decoy_envelope_summary.get("next_required_step"),
                "drd2_weakbase_replay_status": drd2_weakbase_replay_status or None,
                "drd2_weakbase_replay_selected_weight": _float(
                    drd2_weakbase_replay_summary.get("selected_weight")
                ),
                "drd2_weakbase_replay_before_drd2_target_rank": _int(
                    drd2_weakbase_replay_summary.get("before_drd2_target_rank")
                ),
                "drd2_weakbase_replay_selected_drd2_target_rank": _int(
                    drd2_weakbase_replay_summary.get("selected_drd2_target_rank")
                ),
                "drd2_weakbase_replay_selected_drd2_decoys_above_positive": _int(
                    drd2_weakbase_replay_summary.get("selected_drd2_decoys_above_positive")
                ),
                "drd2_weakbase_replay_selected_non_drd2_positive_regression_count": _int(
                    drd2_weakbase_replay_summary.get("selected_non_drd2_positive_regression_count")
                ),
                "drd2_weakbase_replay_selected_ranking_pr_auc": _float(
                    drd2_weakbase_replay_summary.get("selected_ranking_pr_auc")
                ),
                "overanchored_decoy_count": _int(drd2_summary.get("overanchored_decoy_count")),
                "atom_window_like_decoy_count": _int(drd2_summary.get("atom_window_like_decoy_count")),
                "multipolar_basic_decoy_count": _int(drd2_summary.get("multipolar_basic_decoy_count")),
                "ranking_pr_auc": _float(ranking_summary.get("ranking_pr_auc")),
                "ranking_pr_auc_ci_low": _float(ranking_summary.get("ranking_pr_auc_ci_low")),
                "ranking_topk_hit_rate": _float(ranking_summary.get("ranking_topk_hit_rate")),
            },
            acceptance_checks=[
                "hard_decoy_rebuild_allowed is true before any hard-decoy slice rebuild",
                "positive_full_atom_typed_backmapping_ready stays true and positive_local_minimization_survival_fraction is recorded on the positive row",
                "hard-decoy rows carry slice labels: overanchor, multipolar_basic, valid_anchor",
                "bounded hard-decoy envelope status is slice_pairwise_green_diagnostic_only",
                "bounded_best_positive_rank == 1",
                "bounded_best_decoys_above_positive_count == 0",
                "bounded_best_valid_anchor_challenge_above_positive_count == 0",
                "ranking_pr_auc >= 0.55",
                "ranking_pr_auc_ci_low >= 0.45",
                "ranking_topk_hit_rate >= 0.50",
            ],
            next_action=(
                "Completed: DRD2 selected hard-decoy slice is pairwise-green under the bounded label-free pressure "
                "envelope. Do not promote the claim or scorer; move the active repair focus to target-portable "
                "HTR2A/OPRM1 anchor/pose support."
                if hard_decoy_slice_rebuild_done
                else "Rebuild and rerun DRD2 hard-decoy slices now that `hard_decoy_rebuild_allowed=true`; keep scorer "
                "apply and guarded 100k review locked until overanchor, multipolar-basic, and valid-anchor challenge "
                "slices pass without threshold relaxation."
                if hard_decoy_rebuild_allowed
                else "Hold hard-decoy rebuild until the support packet flips `hard_decoy_rebuild_allowed` true; then "
                "split DRD2 decoys into overanchor, multipolar-basic, and valid-anchor challenge slices and rerun "
                "ranking diagnostics without relaxing thresholds."
            ),
            status="completed" if hard_decoy_slice_rebuild_done else "open",
        ),
    ]

    for target_row in target_rows:
        target = str(target_row.get("target") or "")
        ligand_id = str(target_row.get("ligand_id") or "")
        blockers = set(target_row.get("blockers") or [])
        if target == "CHEMBL224_HTR2A_HUMAN" and blockers:
            rows.append(
                _queue_row(
                    priority=3,
                    repair_id="htr2a_anchor_support_repair",
                    target=target,
                    ligand_id=ligand_id,
                    blocker_group="target_portable_anchor_support",
                    source_artifacts=[
                        source_artifacts["pose_gap"],
                        source_artifacts["htr2a_repair_packet"],
                        source_artifacts["htr2a_topology_probe"],
                        source_artifacts["htr2a_life_science_evidence"],
                        source_artifacts["htr2a_topology_replay"],
                    ],
                    current_evidence={
                        "global_rank": _int(target_row.get("global_rank")),
                        "target_rank": _int(target_row.get("target_rank")),
                        "decoys_above_positive": _int(target_row.get("decoys_above_positive")),
                        "label_free_support_pressure": _float(target_row.get("label_free_support_pressure")),
                        "pose_preservation_support": _float(target_row.get("pose_preservation_support")),
                        "pose_rmsd_A": _float(target_row.get("coarse_centroid_preservation_rmsd_A_mean")),
                        "htr2a_repair_packet_status": htr2a_repair_summary.get("status"),
                        "htr2a_positive_target_rank": _int(htr2a_repair_summary.get("positive_target_rank")),
                        "htr2a_base_score_locked_decoys_above_positive_count": _int(
                            htr2a_repair_summary.get("base_score_locked_decoys_above_positive_count")
                        ),
                        "htr2a_generic_anchor_signature_decoys_above_positive_count": _int(
                            htr2a_repair_summary.get("generic_anchor_signature_decoys_above_positive_count")
                        ),
                        "htr2a_pose_advantaged_decoys_above_positive_count": _int(
                            htr2a_repair_summary.get("pose_advantaged_decoys_above_positive_count")
                        ),
                        "htr2a_next_required_step": htr2a_repair_summary.get("next_required_step"),
                        "htr2a_topology_probe_status": htr2a_topology_probe_summary.get("status"),
                        "htr2a_topology_probe_positive_support": _float(
                            htr2a_topology_probe_summary.get("positive_topology_probe_support")
                        ),
                        "htr2a_topology_probe_max_decoy_support": _float(
                            htr2a_topology_probe_summary.get("max_decoy_topology_probe_support")
                        ),
                        "htr2a_topology_probe_decoy_support_positive_or_higher_count": _int(
                            htr2a_topology_probe_summary.get("decoy_support_positive_or_higher_count")
                        ),
                        "htr2a_topology_probe_next_required_step": htr2a_topology_probe_summary.get(
                            "next_required_step"
                        ),
                        "htr2a_life_science_evidence_status": htr2a_life_science_summary.get("status"),
                        "htr2a_life_science_chembl_min_ki_nM": _float(
                            htr2a_life_science_summary.get("chembl_min_ki_nM")
                        ),
                        "htr2a_life_science_chembl_max_pchembl_value": _float(
                            htr2a_life_science_summary.get("chembl_max_pchembl_value")
                        ),
                        "htr2a_life_science_pubchem_cid": htr2a_life_science_summary.get("pubchem_cid"),
                        "htr2a_life_science_rcsb_entry_id": htr2a_life_science_summary.get("rcsb_entry_id"),
                        "htr2a_life_science_uniprot_reviewed_accession": htr2a_life_science_summary.get(
                            "uniprot_reviewed_accession"
                        ),
                        "htr2a_topology_replay_status": htr2a_topology_replay_summary.get("status"),
                        "htr2a_topology_replay_selected_support_weight": _float(
                            htr2a_topology_replay_summary.get("selected_support_weight")
                        ),
                        "htr2a_topology_replay_selected_htr2a_target_rank": _int(
                            htr2a_topology_replay_summary.get("selected_htr2a_target_rank")
                        ),
                        "htr2a_topology_replay_selected_htr2a_decoys_above_positive": _int(
                            htr2a_topology_replay_summary.get("selected_htr2a_decoys_above_positive")
                        ),
                        "htr2a_topology_replay_selected_non_htr2a_regression_count": _int(
                            htr2a_topology_replay_summary.get("selected_non_htr2a_regression_count")
                        ),
                        "htr2a_topology_replay_topology_support_row_count": _int(
                            htr2a_topology_replay_summary.get("topology_support_row_count")
                        ),
                    },
                    acceptance_checks=[
                        "positive_anchor_support_missing is cleared",
                        "decoy_anchor_support_exceeds_positive is cleared",
                        "base_score_locked_decoys_above_positive_count == 0 after replay",
                        "generic_anchor_signature_decoys_above_positive_count == 0 or is explicitly separated by atom-typed evidence",
                        "pose_preservation_support >= 0.50",
                        "claim-locked frozen shadow replay selected_htr2a_target_rank == 1",
                        "claim-locked frozen shadow replay selected_htr2a_decoys_above_positive == 0",
                        "selected_non_htr2a_regression_count == 0 for DRD2 and OPRM1",
                        "claim_promotion_allowed, scorer_apply_allowed, and guarded_100k_rerun_allowed stay false",
                    ],
                    next_action=(
                        (
                            "Completed: HTR2A topology support is claim-locked and selected-slice green in frozen "
                            "shadow replay without DRD2/OPRM1 regression. Do not promote the active scorer or claim; "
                            "move active focus to OPRM1 pose/backmapping repair."
                        )
                        if htr2a_topology_replay_done
                        else
                        (
                            "HTR2A atom-typed topology probe separates the current selected slice diagnostically; "
                            "prototype it as a claim-locked frozen shadow replay feature, require HTR2A target-rank "
                            "1 without DRD2/OPRM1 regression, and keep active scorer/guarded 100k locked."
                        )
                        if htr2a_topology_probe_summary.get("status")
                        == "htr2a_atom_typed_topology_probe_separates_current_slice_diagnostic_only"
                        and htr2a_life_science_summary.get("status")
                        == "life_science_evidence_supports_claim_locked_htr2a_topology_probe"
                        else (
                            "HTR2A topology probe separates the current selected slice diagnostically, but "
                            "life-science evidence is incomplete; finish ChEMBL/PubChem/RCSB/UniProt/BindingDB "
                            "checks before frozen shadow replay."
                        )
                        if htr2a_topology_probe_summary.get("status")
                        == "htr2a_atom_typed_topology_probe_separates_current_slice_diagnostic_only"
                        else
                        str(htr2a_repair_summary.get("next_required_step") or "").strip()
                        or "Add target-portable anchor support for the HTR2A positive and penalize decoy-only "
                        "anchor support before applying any residual scorer."
                    ),
                    status="completed" if htr2a_topology_replay_done else "open",
                )
            )
        if target == "CHEMBL233_OPRM1_HUMAN" and blockers:
            rows.append(
                _queue_row(
                    priority=4,
                    repair_id="oprm1_pose_backmapping_repair",
                    target=target,
                    ligand_id=ligand_id,
                    blocker_group="pose_survival",
                    source_artifacts=[
                        source_artifacts["pose_gap"],
                        source_artifacts["oprm1_life_science_evidence"],
                        source_artifacts["oprm1_topology_replay"],
                    ],
                    current_evidence={
                        "global_rank": _int(target_row.get("global_rank")),
                        "target_rank": _int(target_row.get("target_rank")),
                        "decoys_above_positive": _int(target_row.get("decoys_above_positive")),
                        "label_free_support_pressure": _float(target_row.get("label_free_support_pressure")),
                        "pose_preservation_support": _float(target_row.get("pose_preservation_support")),
                        "pose_rmsd_A": _float(target_row.get("coarse_centroid_preservation_rmsd_A_mean")),
                        "oprm1_life_science_evidence_status": oprm1_life_science_summary.get("status"),
                        "oprm1_life_science_chembl_min_ki_nM": _float(
                            oprm1_life_science_summary.get("chembl_min_ki_nM")
                        ),
                        "oprm1_life_science_pubchem_cid": oprm1_life_science_summary.get("pubchem_cid"),
                        "oprm1_life_science_rcsb_entry_id": oprm1_life_science_summary.get("rcsb_entry_id"),
                        "oprm1_life_science_uniprot_reviewed_accession": oprm1_life_science_summary.get(
                            "uniprot_reviewed_accession"
                        ),
                        "oprm1_topology_replay_status": oprm1_topology_replay_summary.get("status"),
                        "oprm1_topology_replay_selected_support_weight": _float(
                            oprm1_topology_replay_summary.get("selected_support_weight")
                        ),
                        "oprm1_topology_replay_selected_oprm1_target_rank": _int(
                            oprm1_topology_replay_summary.get("selected_oprm1_target_rank")
                        ),
                        "oprm1_topology_replay_selected_oprm1_decoys_above_positive": _int(
                            oprm1_topology_replay_summary.get("selected_oprm1_decoys_above_positive")
                        ),
                        "oprm1_topology_replay_selected_non_oprm1_regression_count": _int(
                            oprm1_topology_replay_summary.get("selected_non_oprm1_regression_count")
                        ),
                        "oprm1_topology_replay_selected_top20_positive_count": _int(
                            oprm1_topology_replay_summary.get("selected_top20_positive_count")
                        ),
                        "oprm1_topology_replay_topology_pose_support_row_count": _int(
                            oprm1_topology_replay_summary.get("topology_pose_support_row_count")
                        ),
                    },
                    acceptance_checks=[
                        "positive_anchor_support_missing is cleared",
                        "positive_pose_preservation_borderline is cleared",
                        "pose_preservation_support >= 0.50",
                        "coarse_centroid_preservation_rmsd_A_mean <= 6.0",
                        "target_decoys_above_positive is cleared or kept as an explicit blocker before guarded review",
                        "claim-locked frozen shadow replay selected_oprm1_target_rank == 1",
                        "claim-locked frozen shadow replay selected_oprm1_decoys_above_positive == 0",
                        "selected_non_oprm1_regression_count == 0 for DRD2 and HTR2A",
                        "selected_top20_positive_count == 3 before guarded claim review",
                    ],
                    next_action=(
                        (
                            "Completed: OPRM1 topology/pose support is claim-locked and selected-slice green in "
                            "frozen shadow replay without DRD2/HTR2A regression. Do not promote the active scorer "
                            "or claim; prepare guarded 100k claim review next."
                        )
                        if oprm1_topology_replay_done
                        else
                        "Repair OPRM1 positive anchor support and pose survival before letting global rank recovery "
                        "count as broad GPCR evidence; v16 adaptive still leaves target-internal decoy intrusion open."
                    ),
                    status="completed" if oprm1_topology_replay_done else "open",
                )
            )

    rows.append(
        _queue_row(
            priority=5,
            repair_id="guarded_100k_claim_review_rerun",
            target="gpcr_family_balanced",
            ligand_id="all_non_adrb2_positives",
            blocker_group="claim_review",
            source_artifacts=[
                source_artifacts["scorecard"],
                source_artifacts["ranking"],
                source_artifacts["drd2_weakbase_replay"],
                source_artifacts["shadow_claim_review"],
            ],
            current_evidence={
                "scorecard_status": _summary(scorecard).get("status"),
                "ranking_pr_auc": ranking_pr_auc,
                "ranking_pr_auc_ci_low": ranking_pr_auc_ci_low,
                "ranking_topk_hit_rate": ranking_topk_hit_rate,
                "worst_positive_global_rank": _int(ranking_summary.get("worst_positive_global_rank")),
                "worst_positive_within_target_rank": _int(ranking_summary.get("worst_positive_within_target_rank")),
                "ranking_positive_count": _int(ranking_summary.get("ranking_positive_count")),
                "ranking_score_col_used": ranking_summary.get("ranking_score_col_used"),
                "full_guarded_review_passed": full_guarded_review_passed,
                "pre_review_repair_gates_completed": guarded_review_ready,
                "shadow_claim_review_status": shadow_review_status or None,
                "shadow_claim_review_passed": shadow_review_passed,
                "shadow_input_rows": _int(shadow_claim_review_summary.get("input_rows")),
                "shadow_ranking_pr_auc": _float(shadow_claim_review_summary.get("ranking_pr_auc")),
                "shadow_ranking_pr_auc_ci_low": _float(shadow_claim_review_summary.get("ranking_pr_auc_ci_low")),
                "shadow_top20_positive_count": _int(shadow_claim_review_summary.get("top20_positive_count")),
                "shadow_top20_positive_recall": _float(shadow_claim_review_summary.get("top20_positive_recall")),
                "shadow_top20_slot_hit_rate": _float(shadow_claim_review_summary.get("top20_slot_hit_rate")),
                "shadow_all_positive_target_rank_1": (
                    bool(shadow_claim_review_summary.get("all_positive_target_rank_1"))
                    if shadow_claim_review_summary
                    else None
                ),
                "shadow_review_blockers": shadow_review_blockers,
            },
            acceptance_checks=[
                "A0 scorecard ligand_ranking row becomes pass",
                "A0 scorecard pose_geometry row becomes pass",
                "ranking_pr_auc >= 0.55",
                "ranking_pr_auc_ci_low >= 0.45",
                "ranking_topk_hit_rate >= 0.50",
                "no target-identity feature leakage",
                "no threshold relaxation",
            ],
            next_action=(
                "Completed: full guarded 100k ranking review clears PR-AUC, PR-AUC CI-low, and top20 hit-rate "
                "under the unchanged gate. Regenerate the accuracy parity scorecard and run an independent repeat "
                "before any commercial parity or router-promotion claim."
                if full_guarded_review_passed
                else
                (
                    "Guarded shadow claim review is still blocked "
                    f"(`status={shadow_review_status}`, `blockers={shadow_review_blockers}`); repair the DRD2 "
                    "decoy intrusion and PR-AUC CI-low stability before a full guarded 100k claim review can count "
                    "toward commercial parity."
                    if "target_internal_positive_rank_not_1" in shadow_review_blockers
                    else "Guarded shadow claim review has cleared point PR-AUC, top20 positive recall, and target-rank "
                    "checks, but is still blocked by PR-AUC CI-low stability; expand non-leaky GPCR positive coverage "
                    "and rerun the full guarded 100k review before any commercial parity claim."
                )
                if guarded_review_ready and shadow_review_status.startswith("blocked_")
                else (
                    "Guarded shadow claim review is diagnostic-green only; run the full guarded 100k GPCR claim "
                    "review and regenerate runs/accuracy_parity_scorecard_current.json before considering promotion."
                )
                if guarded_review_ready and shadow_review_passed
                else
                "Run the guarded 100k GPCR claim review and regenerate runs/accuracy_parity_scorecard_current.json; "
                "claim promotion remains blocked until PR-AUC, CI-low, top20, leakage, and pose-geometry gates pass."
                if guarded_review_ready
                else "Only after rows 1-4 close, rerun the guarded 100k GPCR claim review and regenerate "
                "runs/accuracy_parity_scorecard_current.json."
            ),
            status="completed" if full_guarded_review_passed else "open",
        )
    )

    open_rows = [row for row in rows if row["status"] == "open"]
    top_row = open_rows[0] if open_rows else rows[-1]
    queue_status = "open_a1_repair_queue" if open_rows else "a1_accuracy_repair_queue_cleared_claim_locked"
    summary = {
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": queue_status,
        "queue_row_count": len(rows),
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "guarded_100k_rerun_allowed_now": guarded_review_ready,
        "full_guarded_100k_review_passed": full_guarded_review_passed,
        "open_queue_row_count": len(open_rows),
        "drd2_weakbase_false_support_replay_status": drd2_weakbase_replay_status or None,
        "guarded_shadow_claim_review_status": shadow_review_status or None,
        "guarded_shadow_claim_review_passed": shadow_review_passed,
        "top_priority_repair_id": top_row["repair_id"],
        "top_priority_target": top_row["target"],
        "top_priority_blocker_group": top_row["blocker_group"],
        "next_required_step": top_row["next_action"],
    }
    return {
        "packet_type": "gpcr_a1_accuracy_repair_queue",
        "summary": summary,
        "rows": rows,
        "claim_boundary": {
            "claim_promotion_allowed": False,
            "scorer_apply_allowed": False,
            "guarded_100k_rerun_allowed_now": guarded_review_ready,
            "guarded_shadow_claim_review_passed": shadow_review_passed,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
        },
    }


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# GPCR A1 Accuracy Repair Queue",
        "",
        "## Summary",
        "",
        f"- status: `{summary['status']}`",
        f"- queue_row_count: `{summary['queue_row_count']}`",
        f"- claim_promotion_allowed: `{str(summary['claim_promotion_allowed']).lower()}`",
        f"- guarded_100k_rerun_allowed_now: `{str(summary['guarded_100k_rerun_allowed_now']).lower()}`",
        f"- top_priority_repair_id: `{summary['top_priority_repair_id']}`",
        "",
        "## Queue",
        "",
        "| Priority | Repair ID | Target | Blocker group | Status |",
        "|---:|---|---|---|---|",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority']} | `{row['repair_id']}` | `{row['target']}` | "
            f"`{row['blocker_group']}` | `{row['status']}` |"
        )
    lines.extend(["", "## Details", ""])
    for row in payload["rows"]:
        lines.extend([f"### P{row['priority']} - {row['repair_id']}", ""])
        lines.append(f"- target: `{row['target']}`")
        lines.append(f"- ligand_id: `{row['ligand_id']}`")
        lines.append(f"- source_artifacts: `{', '.join(row['source_artifacts'])}`")
        lines.append("- acceptance_checks:")
        for check in row["acceptance_checks"]:
            lines.append(f"  - `{check}`")
        lines.append(f"- next_action: {row['next_action']}")
        lines.append("")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the A1 GPCR accuracy repair queue.")
    parser.add_argument("--accuracy-scorecard-json", default=DEFAULT_ACCURACY_SCORECARD_JSON)
    parser.add_argument("--drd2-repair-json", default=DEFAULT_DRD2_REPAIR_JSON)
    parser.add_argument("--drd2-backmapping-support-json", default=DEFAULT_DRD2_BACKMAPPING_SUPPORT_JSON)
    parser.add_argument("--drd2-full-forcefield-readiness-json", default=DEFAULT_DRD2_FULL_FORCEFIELD_READINESS_JSON)
    parser.add_argument("--drd2-parameterization-probe-json", default=DEFAULT_DRD2_PARAMETERIZATION_PROBE_JSON)
    parser.add_argument("--drd2-protein-repair-json", default=DEFAULT_DRD2_PROTEIN_REPAIR_JSON)
    parser.add_argument("--drd2-hard-decoy-envelope-json", default=DEFAULT_DRD2_HARD_DECOY_ENVELOPE_JSON)
    parser.add_argument("--drd2-weakbase-replay-json", default=DEFAULT_DRD2_WEAKBASE_REPLAY_JSON)
    parser.add_argument("--htr2a-repair-packet-json", default=DEFAULT_HTR2A_REPAIR_PACKET_JSON)
    parser.add_argument("--htr2a-topology-probe-json", default=DEFAULT_HTR2A_TOPOLOGY_PROBE_JSON)
    parser.add_argument("--htr2a-life-science-evidence-json", default=DEFAULT_HTR2A_LIFE_SCIENCE_EVIDENCE_JSON)
    parser.add_argument("--htr2a-topology-replay-json", default=DEFAULT_HTR2A_TOPOLOGY_REPLAY_JSON)
    parser.add_argument("--oprm1-life-science-evidence-json", default=DEFAULT_OPRM1_LIFE_SCIENCE_EVIDENCE_JSON)
    parser.add_argument("--oprm1-topology-replay-json", default=DEFAULT_OPRM1_TOPOLOGY_REPLAY_JSON)
    parser.add_argument("--shadow-claim-review-json", default=DEFAULT_SHADOW_CLAIM_REVIEW_JSON)
    parser.add_argument("--pose-gap-json", default=DEFAULT_POSE_GAP_JSON)
    parser.add_argument("--ranking-json", default=DEFAULT_RANKING_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_queue(
        accuracy_scorecard_json=args.accuracy_scorecard_json,
        drd2_repair_json=args.drd2_repair_json,
        drd2_backmapping_support_json=args.drd2_backmapping_support_json,
        drd2_full_forcefield_readiness_json=args.drd2_full_forcefield_readiness_json,
        drd2_parameterization_probe_json=args.drd2_parameterization_probe_json,
        drd2_protein_repair_json=args.drd2_protein_repair_json,
        drd2_hard_decoy_envelope_json=args.drd2_hard_decoy_envelope_json,
        drd2_weakbase_replay_json=args.drd2_weakbase_replay_json,
        htr2a_repair_packet_json=args.htr2a_repair_packet_json,
        htr2a_topology_probe_json=args.htr2a_topology_probe_json,
        htr2a_life_science_evidence_json=args.htr2a_life_science_evidence_json,
        htr2a_topology_replay_json=args.htr2a_topology_replay_json,
        oprm1_life_science_evidence_json=args.oprm1_life_science_evidence_json,
        oprm1_topology_replay_json=args.oprm1_topology_replay_json,
        shadow_claim_review_json=args.shadow_claim_review_json,
        pose_gap_json=args.pose_gap_json,
        ranking_json=args.ranking_json,
    )
    _write_json(args.out_json, payload)
    out_md = _resolve(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_md(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
