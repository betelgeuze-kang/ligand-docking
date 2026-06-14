#!/usr/bin/env python3
"""Read-only frontier packet for science accuracy versus commercial parity claims."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_ACCURACY_JSON = "runs/accuracy_parity_scorecard_current.json"
DEFAULT_GPCR_BROAD_JSON = "runs/gpcr_broad_claim_scope_readiness_current.json"
DEFAULT_ENGINE_REFINEMENT_JSON = "runs/engine_refinement_tier_readiness_current.json"
DEFAULT_PUBLIC_BENCHMARK_JSON = "runs/refine_tier_public_benchmark_readiness_current.json"
DEFAULT_PUBLIC_BENCHMARK_MATERIALIZATION_JSON = (
    "runs/refine_tier_public_benchmark_metric_source_materialization_current.json"
)
DEFAULT_PUBLIC_BENCHMARK_MATERIALIZED_APPLY_JSON = (
    "runs/refine_tier_public_benchmark_work_order_apply_materialized_current.json"
)
DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_WORK_ORDER_JSON = (
    "runs/refine_tier_public_benchmark_statistical_support_work_order_current.json"
)
DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_METRIC_MATERIALIZATION_READINESS_JSON = (
    "runs/refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_current.json"
)
DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_METRIC_SOURCE_TEMPLATES_JSON = (
    "runs/refine_tier_public_benchmark_statistical_support_metric_source_templates_current.json"
)
DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_FETCH_R4_PREFLIGHT_JSON = (
    "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_current.json"
)
DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_FETCH_OPERATOR_RECEIPT_JSON = (
    "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_current.json"
)
DEFAULT_PUBLIC_BENCHMARK_CLAIM_GRADE_GAP_AUDIT_JSON = (
    "runs/refine_tier_public_benchmark_claim_grade_gap_audit_current.json"
)
DEFAULT_ENGINE_RECEIPT_JSON = "runs/engine_refinement_claim_evidence_receipt_current.json"
DEFAULT_ENGINE_PRIORITY_JSON = "runs/engine_refinement_claim_evidence_priority_packet_current.json"
DEFAULT_POSE_SAMPLING_JSON = "runs/product_pose_sampling_readiness_current.json"
DEFAULT_OUT_JSON = "runs/science_accuracy_frontier_current.json"
DEFAULT_OUT_MD = "runs/science_accuracy_frontier_current.md"

CLAIM_BOUNDARY = (
    "Science accuracy frontier only; it separates metric-ready restricted lanes from broad GPCR and "
    "OpenMM/Schrödinger-grade commercial parity claims. It reads local artifacts only and does not run "
    "docking/MD, fill public benchmark evidence, approve operator receipts, or promote claims."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json(path_like: str | Path) -> tuple[dict[str, Any], bool]:
    path = _resolve(path_like)
    if not path.is_file():
        return {}, False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, True
    return (payload if isinstance(payload, dict) else {}), True


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    if isinstance(summary, dict):
        return summary
    if payload.get("status"):
        return payload
    return {}


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def _float(value: Any) -> float | None:
    try:
        out = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return out


def _list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str) and value:
        return [item for item in value.split(";") if item]
    return []


def build_science_accuracy_frontier(
    *,
    accuracy_json: str | Path = DEFAULT_ACCURACY_JSON,
    gpcr_broad_json: str | Path = DEFAULT_GPCR_BROAD_JSON,
    engine_refinement_json: str | Path = DEFAULT_ENGINE_REFINEMENT_JSON,
    public_benchmark_json: str | Path = DEFAULT_PUBLIC_BENCHMARK_JSON,
    public_benchmark_materialization_json: str | Path = DEFAULT_PUBLIC_BENCHMARK_MATERIALIZATION_JSON,
    public_benchmark_materialized_apply_json: str | Path = DEFAULT_PUBLIC_BENCHMARK_MATERIALIZED_APPLY_JSON,
    public_benchmark_statistical_support_work_order_json: str
    | Path = DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_WORK_ORDER_JSON,
    public_benchmark_statistical_support_metric_materialization_readiness_json: str
    | Path = DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_METRIC_MATERIALIZATION_READINESS_JSON,
    public_benchmark_statistical_support_metric_source_templates_json: str
    | Path = DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_METRIC_SOURCE_TEMPLATES_JSON,
    public_benchmark_statistical_support_coordinate_fetch_r4_preflight_json: str
    | Path = DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_FETCH_R4_PREFLIGHT_JSON,
    public_benchmark_statistical_support_coordinate_fetch_operator_receipt_json: str
    | Path = DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_FETCH_OPERATOR_RECEIPT_JSON,
    public_benchmark_claim_grade_gap_audit_json: str
    | Path = DEFAULT_PUBLIC_BENCHMARK_CLAIM_GRADE_GAP_AUDIT_JSON,
    engine_receipt_json: str | Path = DEFAULT_ENGINE_RECEIPT_JSON,
    engine_priority_json: str | Path = DEFAULT_ENGINE_PRIORITY_JSON,
    pose_sampling_json: str | Path = DEFAULT_POSE_SAMPLING_JSON,
) -> dict[str, Any]:
    accuracy_payload, accuracy_present = _read_json(accuracy_json)
    gpcr_payload, gpcr_present = _read_json(gpcr_broad_json)
    engine_payload, engine_present = _read_json(engine_refinement_json)
    public_payload, public_present = _read_json(public_benchmark_json)
    materialization_payload, materialization_present = _read_json(public_benchmark_materialization_json)
    materialized_apply_payload, materialized_apply_present = _read_json(public_benchmark_materialized_apply_json)
    statistical_work_order_payload, statistical_work_order_present = _read_json(
        public_benchmark_statistical_support_work_order_json
    )
    metric_materialization_readiness_payload, metric_materialization_readiness_present = _read_json(
        public_benchmark_statistical_support_metric_materialization_readiness_json
    )
    metric_source_templates_payload, metric_source_templates_present = _read_json(
        public_benchmark_statistical_support_metric_source_templates_json
    )
    coordinate_fetch_r4_preflight_payload, coordinate_fetch_r4_preflight_present = _read_json(
        public_benchmark_statistical_support_coordinate_fetch_r4_preflight_json
    )
    coordinate_fetch_operator_receipt_payload, coordinate_fetch_operator_receipt_present = _read_json(
        public_benchmark_statistical_support_coordinate_fetch_operator_receipt_json
    )
    claim_grade_gap_audit_payload, claim_grade_gap_audit_present = _read_json(
        public_benchmark_claim_grade_gap_audit_json
    )
    receipt_payload, receipt_present = _read_json(engine_receipt_json)
    priority_payload, priority_present = _read_json(engine_priority_json)
    pose_payload, pose_present = _read_json(pose_sampling_json)

    accuracy = _summary(accuracy_payload)
    gpcr = _summary(gpcr_payload)
    engine = _summary(engine_payload)
    public = _summary(public_payload)
    materialization = _summary(materialization_payload)
    materialized_apply = _summary(materialized_apply_payload)
    statistical_work_order = _summary(statistical_work_order_payload)
    metric_materialization_readiness = _summary(metric_materialization_readiness_payload)
    metric_source_templates = _summary(metric_source_templates_payload)
    coordinate_fetch_r4_preflight = _summary(coordinate_fetch_r4_preflight_payload)
    coordinate_fetch_operator_receipt = _summary(coordinate_fetch_operator_receipt_payload)
    claim_grade_gap_audit = _summary(claim_grade_gap_audit_payload)
    receipt = _summary(receipt_payload)
    priority = _summary(priority_payload)
    pose = _summary(pose_payload)

    ligand_metric_ready = bool(
        accuracy.get("accuracy_parity_ligand_ranking_metric_thresholds_pass") is True
        and accuracy.get("accuracy_parity_ligand_ranking_claim_scope_lock_only") is True
        and _int(accuracy.get("accuracy_parity_ligand_ranking_metric_blocker_count")) == 0
    )
    if not ligand_metric_ready:
        ligand_metric_ready = bool(
            accuracy.get("status") == "blocked_accuracy_parity"
            and _int(accuracy.get("blocked_row_count")) == 0
            and _int(accuracy.get("missing_row_count")) == 0
            and any("broad_gpcr_claim_not_allowed" in item for item in _list(accuracy.get("top_blockers")))
        )

    gpcr_input_ready = bool(
        gpcr.get("target_heldout_family_guardrail_ready") is True
        and gpcr.get("guarded_100k_claim_review_inputs_ready") is True
        and gpcr.get("target_heldout_broad_scope_review_input_ready") is True
        and gpcr.get("accuracy_parity_metric_ready") is True
    )
    gpcr_claim_ready = bool(gpcr.get("claim_promotion_allowed") is True)
    gpcr_router_ready = bool(gpcr.get("router_claim_allowed") is True)

    engine_internal_ready = bool(
        engine.get("engine_refinement_tier_ready") is True
        and engine.get("status") == "engine_refinement_tier_ready"
        and _int(engine.get("blocked_count")) == 0
    )
    public_benchmark_ready = bool(public.get("claim_grade_public_benchmark_ready") is True)
    public_work_order_ready = bool(public.get("operator_work_order_ready") is True)
    public_required_rows = _int(public.get("min_total_rows_required"), 8)
    public_materialized_metric_ready = bool(
        materialization_present
        and materialization.get("status") == "refine_tier_public_benchmark_metric_sources_materialized"
        and _int(materialization.get("materialized_row_count")) >= public_required_rows
        and _int(materialization.get("metric_evidence_pass_row_count")) >= public_required_rows
        and _int(materialization.get("metric_evidence_blocked_row_count")) == 0
        and bool(materialization.get("free_energy_spearman_gate_ready") is True)
    )
    public_materialized_apply_ready = bool(
        materialized_apply_present
        and materialized_apply.get("status") == "refine_tier_public_benchmark_work_order_apply_ready"
        and bool(materialized_apply.get("apply_ready") is True)
        and _int(materialized_apply.get("blocked_row_count")) == 0
        and _int(materialized_apply.get("metric_evidence_pass_row_count")) >= public_required_rows
        and _int(materialized_apply.get("metric_evidence_contract_blocked_row_count")) == 0
    )
    public_benchmark_science_metric_ready = bool(
        public_benchmark_ready or (public_materialized_metric_ready and public_materialized_apply_ready)
    )
    public_materialized_statistical_support_ready = bool(
        materialization.get("claim_grade_public_benchmark_statistical_support_ready") is True
    )
    public_statistical_support_work_order_ready = bool(
        statistical_work_order_present
        and statistical_work_order.get("status")
        == "refine_tier_public_benchmark_statistical_support_work_order_ready"
        and statistical_work_order.get("work_order_ready") is True
    )
    public_statistical_support_metric_materialization_readiness_ready = bool(
        metric_materialization_readiness_present
        and metric_materialization_readiness.get("status")
        == "refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_ready"
        and metric_materialization_readiness.get("metric_materialization_readiness_ready") is True
    )
    public_statistical_support_metric_materialization_all_candidates_ready = bool(
        metric_materialization_readiness.get("metric_materialization_all_candidates_ready") is True
    )
    public_statistical_support_metric_source_templates_ready = bool(
        metric_source_templates_present
        and metric_source_templates.get("status")
        == "refine_tier_public_benchmark_statistical_support_metric_source_templates_ready"
        and metric_source_templates.get("metric_source_templates_ready") is True
    )
    public_statistical_support_coordinate_fetch_r4_preflight_ready = bool(
        coordinate_fetch_r4_preflight_present
        and coordinate_fetch_r4_preflight.get("status")
        == "refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready"
        and coordinate_fetch_r4_preflight.get("r4_preflight_ready") is True
    )
    public_statistical_support_coordinate_fetch_operator_receipt_ready = bool(
        coordinate_fetch_operator_receipt_present
        and coordinate_fetch_operator_receipt.get("status")
        == "refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_ready"
        and coordinate_fetch_operator_receipt.get("operator_receipt_ready") is True
    )
    public_claim_grade_gap_audit_ready = bool(
        claim_grade_gap_audit_present
        and claim_grade_gap_audit.get("status") == "refine_tier_public_benchmark_claim_grade_gap_audit_ready"
        and claim_grade_gap_audit.get("claim_grade_gap_audit_ready") is True
    )
    engine_receipt_ready = bool(receipt.get("claim_promotion_evidence_receipt_ready") is True)
    engine_priority_ready = bool(priority.get("priority_packet_ready") is True)
    pose_surface_ready = bool(
        pose.get("status") == "product_pose_sampling_readiness_ready"
        and pose.get("pose_generation_contract_ready") is True
        and pose.get("pocket_detection_ready") is True
    )

    restricted_science_accuracy_ready = bool(ligand_metric_ready and gpcr_input_ready and engine_internal_ready)
    openmm_schrodinger_claim_ready = bool(
        engine_internal_ready
        and public_benchmark_ready
        and engine_receipt_ready
        and bool(engine.get("claim_promotion_allowed") is True)
    )
    broad_commercial_accuracy_claim_ready = bool(
        gpcr_claim_ready and gpcr_router_ready and openmm_schrodinger_claim_ready and pose_surface_ready
    )

    blockers: list[str] = []
    if not accuracy_present:
        blockers.append("accuracy_parity_scorecard_missing")
    if not gpcr_present:
        blockers.append("gpcr_broad_claim_scope_readiness_missing")
    if not engine_present:
        blockers.append("engine_refinement_tier_readiness_missing")
    if not public_present:
        blockers.append("refine_tier_public_benchmark_readiness_missing")
    if not receipt_present:
        blockers.append("engine_refinement_claim_evidence_receipt_missing")
    if not priority_present:
        blockers.append("engine_refinement_claim_evidence_priority_packet_missing")
    if not pose_present:
        blockers.append("product_pose_sampling_readiness_missing")
    if not ligand_metric_ready:
        blockers.append("gpcr_ligand_metric_not_ready")
    if not gpcr_input_ready:
        blockers.append("gpcr_target_heldout_or_guarded_input_not_ready")
    if not gpcr_claim_ready:
        blockers.append("gpcr_broad_claim_review_not_approved")
    if not gpcr_router_ready:
        blockers.append("gpcr_scorer_router_promotion_not_approved")
    if not engine_internal_ready:
        blockers.append("engine_refinement_internal_surface_not_ready")
    if not public_benchmark_science_metric_ready:
        blockers.append("openmm_schrodinger_public_benchmark_metric_candidate_not_ready")
    elif not public_benchmark_ready:
        blockers.append("openmm_schrodinger_public_benchmark_not_promoted_to_canonical_intake")
    if (
        public_benchmark_science_metric_ready
        and not public_benchmark_ready
        and not public_materialized_statistical_support_ready
    ):
        blockers.append("openmm_schrodinger_public_benchmark_statistical_support_not_claim_grade")
        if not public_claim_grade_gap_audit_ready:
            blockers.append("openmm_schrodinger_public_benchmark_claim_grade_gap_audit_not_ready")
        if not public_statistical_support_work_order_ready:
            blockers.append("openmm_schrodinger_public_benchmark_statistical_support_work_order_missing")
        if (
            metric_materialization_readiness_present
            and public_statistical_support_metric_materialization_readiness_ready
            and not public_statistical_support_metric_materialization_all_candidates_ready
        ):
            blockers.append(
                "openmm_schrodinger_public_benchmark_statistical_support_metric_sources_not_materialized"
            )
            if not public_statistical_support_metric_source_templates_ready:
                blockers.append(
                    "openmm_schrodinger_public_benchmark_statistical_support_metric_source_templates_not_ready"
                )
            if not coordinate_fetch_r4_preflight_present:
                blockers.append(
                    "openmm_schrodinger_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_missing"
                )
            elif (
                public_statistical_support_coordinate_fetch_r4_preflight_ready
                and _int(coordinate_fetch_r4_preflight.get("fetch_required_row_count")) > 0
                and coordinate_fetch_r4_preflight.get("download_executed") is not True
            ):
                blockers.append(
                    "openmm_schrodinger_public_benchmark_statistical_support_coordinate_fetch_r4_approval_required"
                )
                if not coordinate_fetch_operator_receipt_present:
                    blockers.append(
                        "openmm_schrodinger_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_missing"
                    )
                elif not public_statistical_support_coordinate_fetch_operator_receipt_ready:
                    blockers.append(
                        "openmm_schrodinger_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_not_ready"
                    )
    if not engine_receipt_ready:
        blockers.append("engine_refinement_claim_evidence_receipt_not_ready")
    if not pose_surface_ready:
        blockers.append("pose_sampling_contract_not_ready")

    status = (
        "science_accuracy_frontier_commercial_parity_ready"
        if broad_commercial_accuracy_claim_ready and not blockers
        else "blocked_science_accuracy_frontier"
    )
    if restricted_science_accuracy_ready and public_benchmark_science_metric_ready:
        next_required_step = (
            "Restricted science accuracy and the current 8-row materialized R9 metric evidence are ready, but broad "
            "commercial parity remains blocked by GPCR claim/router approval, canonical intake promotion, "
            "R9 statistical-support limits, R9 statistical-support coordinate-fetch R4 approval, coordinate "
            "operator receipt, coordinate validation/materialization, and R9 evidence receipts."
        )
    elif restricted_science_accuracy_ready:
        next_required_step = (
            "Restricted science accuracy is ready, but broad commercial parity remains blocked by GPCR "
            "claim/router approval and OpenMM/Schrödinger public benchmark plus R9 evidence receipts."
        )
    else:
        next_required_step = "Repair tracked science accuracy metric inputs before reviewing commercial parity claims."

    summary = {
        "packet_type": "science_accuracy_frontier",
        "status": status,
        "restricted_science_accuracy_ready": restricted_science_accuracy_ready,
        "broad_commercial_accuracy_claim_ready": broad_commercial_accuracy_claim_ready,
        "gpcr_ligand_metric_ready": ligand_metric_ready,
        "gpcr_target_heldout_guarded_inputs_ready": gpcr_input_ready,
        "gpcr_broad_claim_ready": gpcr_claim_ready,
        "gpcr_scorer_router_ready": gpcr_router_ready,
        "gpcr_broad_claim_review_receipt_ready": bool(gpcr.get("broad_claim_review_receipt_ready") is True),
        "gpcr_broad_claim_review_receipt_status": str(gpcr.get("broad_claim_review_receipt_status", "")),
        "gpcr_broad_claim_review_receipt_row_count": _int(gpcr.get("broad_claim_review_receipt_row_count")),
        "gpcr_broad_claim_review_receipt_pass_row_count": _int(
            gpcr.get("broad_claim_review_receipt_pass_row_count")
        ),
        "gpcr_broad_claim_review_receipt_blocked_row_count": _int(
            gpcr.get("broad_claim_review_receipt_blocked_row_count")
        ),
        "gpcr_broad_claim_review_receipt_first_blocked_review_id": str(
            gpcr.get("broad_claim_review_receipt_first_blocked_review_id", "")
        ),
        "gpcr_broad_claim_review_receipt_approval_token_required": str(
            gpcr.get("broad_claim_review_receipt_approval_token_required", "")
        ),
        "gpcr_active_scorer_gate_ready": bool(gpcr.get("active_scorer_gate_ready") is True),
        "gpcr_scorer_router_promotion_gate_receipt_approved": bool(
            gpcr.get("scorer_router_promotion_gate_receipt_approved") is True
        ),
        "engine_refinement_internal_surface_ready": engine_internal_ready,
        "openmm_schrodinger_public_benchmark_ready": public_benchmark_ready,
        "openmm_schrodinger_public_benchmark_science_ready": public_benchmark_science_metric_ready,
        "public_benchmark_materialized_metric_ready": public_materialized_metric_ready,
        "public_benchmark_materialized_apply_ready": public_materialized_apply_ready,
        "public_benchmark_materialized_row_count": _int(materialization.get("materialized_row_count")),
        "public_benchmark_materialized_blocked_row_count": _int(materialization.get("blocked_row_count")),
        "public_benchmark_materialized_metric_evidence_pass_row_count": _int(
            materialization.get("metric_evidence_pass_row_count")
        ),
        "public_benchmark_materialized_metric_evidence_blocked_row_count": _int(
            materialization.get("metric_evidence_blocked_row_count")
        ),
        "public_benchmark_materialized_free_energy_pair_count": _int(materialization.get("free_energy_pair_count")),
        "public_benchmark_materialized_free_energy_fit_pair_count": _int(
            materialization.get("free_energy_fit_pair_count")
        ),
        "public_benchmark_materialized_free_energy_holdout_pair_count": _int(
            materialization.get("free_energy_holdout_pair_count")
        ),
        "public_benchmark_materialized_free_energy_unknown_split_pair_count": _int(
            materialization.get("free_energy_unknown_split_pair_count")
        ),
        "public_benchmark_materialized_free_energy_spearman": _float(materialization.get("free_energy_spearman")),
        "public_benchmark_materialized_free_energy_spearman_gate_ready": bool(
            materialization.get("free_energy_spearman_gate_ready") is True
        ),
        "public_benchmark_materialized_free_energy_spearman_bootstrap_p05": _float(
            materialization.get("free_energy_spearman_bootstrap_p05")
        ),
        "public_benchmark_materialized_free_energy_spearman_bootstrap_p50": _float(
            materialization.get("free_energy_spearman_bootstrap_p50")
        ),
        "public_benchmark_materialized_free_energy_spearman_bootstrap_p95": _float(
            materialization.get("free_energy_spearman_bootstrap_p95")
        ),
        "public_benchmark_materialized_claim_grade_statistical_support_ready": (
            public_materialized_statistical_support_ready
        ),
        "public_benchmark_materialized_claim_grade_statistical_support_blocker_count": _int(
            materialization.get("claim_grade_public_benchmark_statistical_support_blocker_count")
        ),
        "public_benchmark_materialized_claim_grade_statistical_support_blockers": _list(
            materialization.get("claim_grade_public_benchmark_statistical_support_blockers")
        ),
        "public_benchmark_materialized_min_claim_grade_public_benchmark_pairs_required": _int(
            materialization.get("min_claim_grade_public_benchmark_pairs_required")
        ),
        "public_benchmark_materialized_min_claim_grade_holdout_pairs_required": _int(
            materialization.get("min_claim_grade_holdout_pairs_required")
        ),
        "public_benchmark_materialized_min_claim_grade_bootstrap_spearman_low_required": _float(
            materialization.get("min_claim_grade_bootstrap_spearman_low_required")
        ),
        "public_benchmark_claim_grade_gap_audit_present": claim_grade_gap_audit_present,
        "public_benchmark_claim_grade_gap_audit_ready": public_claim_grade_gap_audit_ready,
        "public_benchmark_claim_grade_gap_audit_status": str(claim_grade_gap_audit.get("status", "")),
        "public_benchmark_claim_grade_gap_audit_claim_grade_statistical_support_ready": bool(
            claim_grade_gap_audit.get("claim_grade_statistical_support_ready") is True
        ),
        "public_benchmark_claim_grade_gap_audit_canonical_intake_promotion_allowed": bool(
            claim_grade_gap_audit.get("canonical_intake_promotion_allowed") is True
        ),
        "public_benchmark_claim_grade_gap_audit_bootstrap_retest_required": bool(
            claim_grade_gap_audit.get("bootstrap_retest_required") is True
        ),
        "public_benchmark_claim_grade_gap_audit_observed_public_benchmark_pair_count": _int(
            claim_grade_gap_audit.get("observed_public_benchmark_pair_count")
        ),
        "public_benchmark_claim_grade_gap_audit_observed_holdout_pair_count": _int(
            claim_grade_gap_audit.get("observed_holdout_pair_count")
        ),
        "public_benchmark_claim_grade_gap_audit_observed_bootstrap_spearman_p05": _float(
            claim_grade_gap_audit.get("observed_bootstrap_spearman_p05")
        ),
        "public_benchmark_claim_grade_gap_audit_observed_bootstrap_spearman_p50": _float(
            claim_grade_gap_audit.get("observed_bootstrap_spearman_p50")
        ),
        "public_benchmark_claim_grade_gap_audit_observed_bootstrap_spearman_p95": _float(
            claim_grade_gap_audit.get("observed_bootstrap_spearman_p95")
        ),
        "public_benchmark_claim_grade_gap_audit_bootstrap_spearman_p05_deficit": _float(
            claim_grade_gap_audit.get("bootstrap_spearman_p05_deficit")
        ),
        "public_benchmark_claim_grade_gap_audit_minimum_new_pair_count": _int(
            claim_grade_gap_audit.get("minimum_new_pair_count")
        ),
        "public_benchmark_claim_grade_gap_audit_minimum_new_holdout_pair_count": _int(
            claim_grade_gap_audit.get("minimum_new_holdout_pair_count")
        ),
        "public_benchmark_claim_grade_gap_audit_coordinate_validation_pass_row_count": _int(
            claim_grade_gap_audit.get("coordinate_validation_pass_row_count")
        ),
        "public_benchmark_claim_grade_gap_audit_coordinate_validation_blocked_row_count": _int(
            claim_grade_gap_audit.get("coordinate_validation_blocked_row_count")
        ),
        "public_benchmark_claim_grade_gap_audit_coordinate_validation_deficit": _int(
            claim_grade_gap_audit.get("coordinate_validation_deficit")
        ),
        "public_benchmark_claim_grade_gap_audit_metric_source_payload_fill_ready_row_count": _int(
            claim_grade_gap_audit.get("metric_source_payload_fill_ready_row_count")
        ),
        "public_benchmark_claim_grade_gap_audit_metric_source_payload_fill_blocked_row_count": _int(
            claim_grade_gap_audit.get("metric_source_payload_fill_blocked_row_count")
        ),
        "public_benchmark_claim_grade_gap_audit_metric_source_payload_fill_deficit": _int(
            claim_grade_gap_audit.get("metric_source_payload_fill_deficit")
        ),
        "public_benchmark_claim_grade_gap_audit_planned_metric_source_payload_count": _int(
            claim_grade_gap_audit.get("planned_metric_source_payload_count")
        ),
        "public_benchmark_claim_grade_gap_audit_coordinate_fetch_r4_fetch_required_row_count": _int(
            claim_grade_gap_audit.get("coordinate_fetch_r4_fetch_required_row_count")
        ),
        "public_benchmark_claim_grade_gap_audit_coordinate_fetch_r4_download_executed": bool(
            claim_grade_gap_audit.get("coordinate_fetch_r4_download_executed") is True
        ),
        "public_benchmark_claim_grade_gap_audit_gap_row_count": _int(
            claim_grade_gap_audit.get("gap_row_count")
        ),
        "public_benchmark_claim_grade_gap_audit_blocked_gap_row_count": _int(
            claim_grade_gap_audit.get("blocked_gap_row_count")
        ),
        "public_benchmark_claim_grade_gap_audit_pass_gap_row_count": _int(
            claim_grade_gap_audit.get("pass_gap_row_count")
        ),
        "public_benchmark_claim_grade_gap_audit_blocker_count": _int(
            claim_grade_gap_audit.get("blocker_count")
        ),
        "public_benchmark_claim_grade_gap_audit_top_science_gap_id": str(
            claim_grade_gap_audit.get("top_science_gap_id", "")
        ),
        "public_benchmark_claim_grade_gap_audit_top_statistical_gap_id": str(
            claim_grade_gap_audit.get("top_statistical_gap_id", "")
        ),
        "public_benchmark_claim_grade_gap_audit_next_required_step": str(
            claim_grade_gap_audit.get("next_required_step", "")
        ),
        "public_benchmark_materialized_apply_blocked_row_count": _int(
            materialized_apply.get("blocked_row_count")
        ),
        "public_benchmark_materialized_apply_metric_evidence_pass_row_count": _int(
            materialized_apply.get("metric_evidence_pass_row_count")
        ),
        "public_benchmark_materialized_apply_metric_evidence_contract_blocked_row_count": _int(
            materialized_apply.get("metric_evidence_contract_blocked_row_count")
        ),
        "public_benchmark_statistical_support_work_order_ready": public_statistical_support_work_order_ready,
        "public_benchmark_statistical_support_work_order_status": str(
            statistical_work_order.get("status", "")
        ),
        "public_benchmark_statistical_support_work_order_expansion_slot_count": _int(
            statistical_work_order.get("expansion_slot_count")
        ),
        "public_benchmark_statistical_support_work_order_minimum_new_pair_count": _int(
            statistical_work_order.get("minimum_new_pair_count")
        ),
        "public_benchmark_statistical_support_work_order_minimum_new_holdout_pair_count": _int(
            statistical_work_order.get("minimum_new_holdout_pair_count")
        ),
        "public_benchmark_statistical_support_work_order_minimum_new_fit_or_holdout_pair_count": _int(
            statistical_work_order.get("minimum_new_fit_or_holdout_pair_count")
        ),
        "public_benchmark_statistical_support_work_order_bootstrap_retest_required": bool(
            statistical_work_order.get("bootstrap_retest_required") is True
        ),
        "public_benchmark_statistical_support_work_order_canonical_intake_promotion_allowed": bool(
            statistical_work_order.get("canonical_intake_promotion_allowed") is True
        ),
        "public_benchmark_statistical_support_metric_materialization_readiness_present": (
            metric_materialization_readiness_present
        ),
        "public_benchmark_statistical_support_metric_materialization_readiness_ready": (
            public_statistical_support_metric_materialization_readiness_ready
        ),
        "public_benchmark_statistical_support_metric_materialization_status": str(
            metric_materialization_readiness.get("status", "")
        ),
        "public_benchmark_statistical_support_metric_materialization_all_candidates_ready": (
            public_statistical_support_metric_materialization_all_candidates_ready
        ),
        "public_benchmark_statistical_support_metric_materialization_row_count": _int(
            metric_materialization_readiness.get("metric_materialization_row_count")
        ),
        "public_benchmark_statistical_support_metric_materialization_candidate_ready_count": _int(
            metric_materialization_readiness.get("metric_materialization_candidate_ready_count")
        ),
        "public_benchmark_statistical_support_metric_materialization_candidate_blocked_count": _int(
            metric_materialization_readiness.get("metric_materialization_candidate_blocked_count")
        ),
        "public_benchmark_statistical_support_metric_materialization_input_artifact_contract_ready": bool(
            metric_materialization_readiness.get("metric_materialization_input_artifact_contract_ready") is True
        ),
        "public_benchmark_statistical_support_metric_materialization_required_input_artifact_count": _int(
            metric_materialization_readiness.get("required_metric_input_artifact_count")
        ),
        "public_benchmark_statistical_support_metric_materialization_present_required_input_artifact_count": _int(
            metric_materialization_readiness.get("present_required_metric_input_artifact_count")
        ),
        "public_benchmark_statistical_support_metric_materialization_missing_required_input_artifact_count": _int(
            metric_materialization_readiness.get("missing_required_metric_input_artifact_count")
        ),
        "public_benchmark_statistical_support_metric_materialization_missing_required_input_artifact_row_count": _int(
            metric_materialization_readiness.get("missing_required_metric_input_artifact_row_count")
        ),
        "public_benchmark_statistical_support_metric_materialization_coordinate_validation_pass_row_count": _int(
            metric_materialization_readiness.get("coordinate_validation_pass_row_count")
        ),
        "public_benchmark_statistical_support_metric_materialization_coordinate_validation_blocked_row_count": _int(
            metric_materialization_readiness.get("coordinate_validation_blocked_row_count")
        ),
        "public_benchmark_statistical_support_metric_materialization_existing_metric_source_payload_count": _int(
            metric_materialization_readiness.get("existing_metric_source_payload_count")
        ),
        "public_benchmark_statistical_support_metric_materialization_planned_metric_source_payload_count": _int(
            metric_materialization_readiness.get("planned_metric_source_payload_count")
        ),
        "public_benchmark_statistical_support_metric_materialization_required_metric_source_payloads": str(
            metric_materialization_readiness.get("required_metric_source_payloads", "")
        ),
        "public_benchmark_statistical_support_metric_materialization_required_metric_source_payload_field_count": _int(
            metric_materialization_readiness.get("required_metric_source_payload_field_count")
        ),
        "public_benchmark_statistical_support_metric_materialization_required_metric_source_payload_fields": str(
            metric_materialization_readiness.get("required_metric_source_payload_fields", "")
        ),
        "public_benchmark_statistical_support_metric_materialization_claim_grade_statistical_support_ready": bool(
            metric_materialization_readiness.get("claim_grade_statistical_support_ready") is True
        ),
        "public_benchmark_statistical_support_metric_materialization_next_required_step": str(
            metric_materialization_readiness.get("next_required_step", "")
        ),
        "public_benchmark_statistical_support_metric_source_templates_present": metric_source_templates_present,
        "public_benchmark_statistical_support_metric_source_templates_ready": (
            public_statistical_support_metric_source_templates_ready
        ),
        "public_benchmark_statistical_support_metric_source_templates_status": str(
            metric_source_templates.get("status", "")
        ),
        "public_benchmark_statistical_support_metric_source_templates_template_row_count": _int(
            metric_source_templates.get("template_row_count")
        ),
        "public_benchmark_statistical_support_metric_source_templates_template_candidate_row_count": _int(
            metric_source_templates.get("template_candidate_row_count")
        ),
        "public_benchmark_statistical_support_metric_source_templates_template_metric_name_count": _int(
            metric_source_templates.get("template_metric_name_count")
        ),
        "public_benchmark_statistical_support_metric_source_templates_template_metric_source_artifact_path_row_count": _int(
            metric_source_templates.get("template_metric_source_artifact_path_row_count")
        ),
        "public_benchmark_statistical_support_metric_source_templates_template_payload_required_fields_present_row_count": _int(
            metric_source_templates.get("template_payload_required_fields_present_row_count")
        ),
        "public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count": _int(
            metric_source_templates.get("metric_source_payload_fill_ready_row_count")
        ),
        "public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count": _int(
            metric_source_templates.get("metric_source_payload_fill_blocked_row_count")
        ),
        "public_benchmark_statistical_support_metric_source_templates_coordinate_validation_blocked_template_row_count": _int(
            metric_source_templates.get("coordinate_validation_blocked_template_row_count")
        ),
        "public_benchmark_statistical_support_metric_source_templates_missing_required_input_template_row_count": _int(
            metric_source_templates.get("missing_required_input_template_row_count")
        ),
        "public_benchmark_statistical_support_metric_source_templates_existing_metric_source_payload_present_row_count": _int(
            metric_source_templates.get("existing_metric_source_payload_present_row_count")
        ),
        "public_benchmark_statistical_support_metric_source_templates_placeholder_value_count": _int(
            metric_source_templates.get("placeholder_value_count")
        ),
        "public_benchmark_statistical_support_metric_source_templates_placeholder_method_count": _int(
            metric_source_templates.get("placeholder_method_count")
        ),
        "public_benchmark_statistical_support_metric_source_templates_placeholder_operator_id_count": _int(
            metric_source_templates.get("placeholder_operator_id_count")
        ),
        "public_benchmark_statistical_support_metric_source_templates_placeholder_reviewed_at_utc_count": _int(
            metric_source_templates.get("placeholder_reviewed_at_utc_count")
        ),
        "public_benchmark_statistical_support_metric_source_templates_placeholder_license_ok_count": _int(
            metric_source_templates.get("placeholder_license_ok_count")
        ),
        "public_benchmark_statistical_support_metric_source_templates_external_engine_calls_total": _int(
            metric_source_templates.get("external_engine_calls_total")
        ),
        "public_benchmark_statistical_support_metric_source_templates_canonical_intake_promotion_allowed": bool(
            metric_source_templates.get("canonical_intake_promotion_allowed") is True
        ),
        "public_benchmark_statistical_support_metric_source_templates_next_required_step": str(
            metric_source_templates.get("next_required_step", "")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_r4_preflight_present": (
            coordinate_fetch_r4_preflight_present
        ),
        "public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready": (
            public_statistical_support_coordinate_fetch_r4_preflight_ready
        ),
        "public_benchmark_statistical_support_coordinate_fetch_r4_preflight_status": str(
            coordinate_fetch_r4_preflight.get("status", "")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_r4_row_count": _int(
            coordinate_fetch_r4_preflight.get("r4_row_count")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_r4_ready_for_review_row_count": _int(
            coordinate_fetch_r4_preflight.get("ready_for_r4_review_row_count")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_r4_blocked_row_count": _int(
            coordinate_fetch_r4_preflight.get("blocked_r4_row_count")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_r4_fetch_required_row_count": _int(
            coordinate_fetch_r4_preflight.get("fetch_required_row_count")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_r4_metric_materialization_blocked_row_count": _int(
            coordinate_fetch_r4_preflight.get("metric_materialization_blocked_row_count")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_r4_planned_metric_source_payload_count": _int(
            coordinate_fetch_r4_preflight.get("planned_metric_source_payload_count")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_r4_authorized_for_external_download": bool(
            coordinate_fetch_r4_preflight.get("authorized_for_external_download") is True
        ),
        "public_benchmark_statistical_support_coordinate_fetch_r4_download_executed": bool(
            coordinate_fetch_r4_preflight.get("download_executed") is True
        ),
        "public_benchmark_statistical_support_coordinate_fetch_r4_external_state_mutated": bool(
            coordinate_fetch_r4_preflight.get("external_state_mutated") is True
        ),
        "public_benchmark_statistical_support_coordinate_fetch_r4_approval_token_required": str(
            coordinate_fetch_r4_preflight.get("approval_token_required", "")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_r4_execute_command": str(
            coordinate_fetch_r4_preflight.get("execute_command", "")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_present": (
            coordinate_fetch_operator_receipt_present
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_ready": (
            public_statistical_support_coordinate_fetch_operator_receipt_ready
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_status": str(
            coordinate_fetch_operator_receipt.get("status", "")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_csv_present": bool(
            coordinate_fetch_operator_receipt.get("receipt_csv_present") is True
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_row_count": _int(
            coordinate_fetch_operator_receipt.get("receipt_row_count")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_required_r4_review_count": _int(
            coordinate_fetch_operator_receipt.get("required_r4_review_count")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_pass_row_count": _int(
            coordinate_fetch_operator_receipt.get("pass_row_count")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_blocked_row_count": _int(
            coordinate_fetch_operator_receipt.get("blocked_row_count")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_approved_fetch_count": _int(
            coordinate_fetch_operator_receipt.get("approved_fetch_count")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_authorized_for_external_download": bool(
            coordinate_fetch_operator_receipt.get("authorized_for_external_download") is True
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_download_executed": bool(
            coordinate_fetch_operator_receipt.get("download_executed") is True
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_canonical_intake_promotion_allowed": bool(
            coordinate_fetch_operator_receipt.get("canonical_intake_promotion_allowed") is True
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_claim_promotion_allowed": bool(
            coordinate_fetch_operator_receipt.get("claim_promotion_allowed") is True
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_external_state_mutated": bool(
            coordinate_fetch_operator_receipt.get("external_state_mutated") is True
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_first_blocked_review_id": str(
            coordinate_fetch_operator_receipt.get("first_blocked_review_id", "")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_first_blocked_target_id": str(
            coordinate_fetch_operator_receipt.get("first_blocked_target_id", "")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_first_blocked_pose_id": str(
            coordinate_fetch_operator_receipt.get("first_blocked_pose_id", "")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_most_common_row_blocker": str(
            coordinate_fetch_operator_receipt.get("most_common_row_blocker", "")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_approval_token_required": str(
            coordinate_fetch_operator_receipt.get("approval_token_required", "")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_execute_command": str(
            coordinate_fetch_operator_receipt.get("execute_command", "")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_blocker_count": _int(
            coordinate_fetch_operator_receipt.get("blocker_count")
        ),
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_next_required_step": str(
            coordinate_fetch_operator_receipt.get("next_required_step", "")
        ),
        "openmm_schrodinger_claim_ready": openmm_schrodinger_claim_ready,
        "engine_refinement_claim_evidence_receipt_ready": engine_receipt_ready,
        "engine_refinement_claim_evidence_priority_packet_ready": engine_priority_ready,
        "pose_sampling_contract_ready": pose_surface_ready,
        "accuracy_parity_status": str(accuracy.get("status", "")),
        "gpcr_broad_claim_scope_status": str(gpcr.get("status", "")),
        "engine_refinement_tier_status": str(engine.get("status", "")),
        "refine_tier_public_benchmark_status": str(public.get("status", "")),
        "engine_refinement_claim_evidence_receipt_status": str(receipt.get("status", "")),
        "engine_refinement_claim_evidence_priority_packet_status": str(priority.get("status", "")),
        "product_pose_sampling_readiness_status": str(pose.get("status", "")),
        "accuracy_metric_blocker_count": _int(accuracy.get("accuracy_parity_ligand_ranking_metric_blocker_count")),
        "gpcr_broad_claim_blocker_count": _int(gpcr.get("blocker_count")),
        "engine_refinement_claim_blocker_count": _int(engine.get("claim_promotion_blocker_count")),
        "public_benchmark_blocker_count": _int(public.get("blocker_count")),
        "public_benchmark_required_row_count": _int(public.get("min_total_rows_required")),
        "public_benchmark_current_row_count": _int(public.get("row_count")),
        "public_benchmark_work_order_row_count": _int(public.get("work_order_row_count")),
        "public_benchmark_work_order_seeded_row_count": _int(public.get("work_order_seeded_row_count")),
        "public_benchmark_work_order_prefilled_operator_field_count": _int(
            public.get("work_order_prefilled_operator_field_count")
        ),
        "public_benchmark_work_order_pending_operator_field_count": _int(
            public.get("work_order_pending_operator_field_count")
        ),
        "public_benchmark_work_order_experimental_deltaG_prefilled_count": _int(
            public.get("work_order_experimental_deltaG_prefilled_count")
        ),
        "public_benchmark_work_order_experimental_deltaG_source_parsed_count": _int(
            public.get("work_order_experimental_deltaG_source_parsed_count")
        ),
        "public_benchmark_work_order_pending_license_ok_count": _int(
            public.get("work_order_pending_license_ok_count")
        ),
        "public_benchmark_work_order_pending_dockq_count": _int(public.get("work_order_pending_dockq_count")),
        "public_benchmark_work_order_pending_lddt_pli_count": _int(
            public.get("work_order_pending_lddt_pli_count")
        ),
        "public_benchmark_work_order_pending_internal_deltaG_count": _int(
            public.get("work_order_pending_internal_deltaG_count")
        ),
        "public_benchmark_work_order_pending_experimental_deltaG_count": _int(
            public.get("work_order_pending_experimental_deltaG_count")
        ),
        "public_benchmark_work_order_remaining_nonlicense_science_field_count": _int(
            public.get("work_order_remaining_nonlicense_science_field_count")
        ),
        "public_benchmark_work_order_current_local_source_prefill_ready_field_count": _int(
            public.get("work_order_current_local_source_prefill_ready_field_count")
        ),
        "public_benchmark_work_order_local_receptor_coordinate_file_count": _int(
            public.get("work_order_local_receptor_coordinate_file_count")
        ),
        "public_benchmark_work_order_tar_ligand_pose_member_count": _int(
            public.get("work_order_tar_ligand_pose_member_count")
        ),
        "public_benchmark_work_order_tar_receptor_coordinate_member_count": _int(
            public.get("work_order_tar_receptor_coordinate_member_count")
        ),
        "public_benchmark_work_order_tar_ligand_only_archive_count": _int(
            public.get("work_order_tar_ligand_only_archive_count")
        ),
        "public_benchmark_work_order_science_input_gap_row_count": _int(
            public.get("work_order_science_input_gap_row_count")
        ),
        "public_benchmark_work_order_science_input_gap_blocked_row_count": _int(
            public.get("work_order_science_input_gap_blocked_row_count")
        ),
        "public_benchmark_work_order_local_ligand_pose_artifact_count": _int(
            public.get("work_order_local_ligand_pose_artifact_count")
        ),
        "public_benchmark_work_order_missing_ligand_pose_artifact_count": _int(
            public.get("work_order_missing_ligand_pose_artifact_count")
        ),
        "public_benchmark_work_order_receptor_coordinate_ready_row_count": _int(
            public.get("work_order_receptor_coordinate_ready_row_count")
        ),
        "public_benchmark_work_order_missing_receptor_coordinate_row_count": _int(
            public.get("work_order_missing_receptor_coordinate_row_count")
        ),
        "public_benchmark_work_order_receptor_coordinate_intake_row_count": _int(
            public.get("work_order_receptor_coordinate_intake_row_count")
        ),
        "public_benchmark_work_order_receptor_coordinate_intake_matched_row_count": _int(
            public.get("work_order_receptor_coordinate_intake_matched_row_count")
        ),
        "public_benchmark_work_order_receptor_coordinate_intake_missing_row_count": _int(
            public.get("work_order_receptor_coordinate_intake_missing_row_count")
        ),
        "public_benchmark_work_order_receptor_coordinate_intake_suggested_public_url_row_count": _int(
            public.get("work_order_receptor_coordinate_intake_suggested_public_url_row_count")
        ),
        "public_benchmark_work_order_receptor_coordinate_intake_suggested_local_path_row_count": _int(
            public.get("work_order_receptor_coordinate_intake_suggested_local_path_row_count")
        ),
        "public_benchmark_work_order_receptor_coordinate_intake_operator_review_required_row_count": _int(
            public.get("work_order_receptor_coordinate_intake_operator_review_required_row_count")
        ),
        "public_benchmark_work_order_receptor_coordinate_validation_row_count": _int(
            public.get("work_order_receptor_coordinate_validation_row_count")
        ),
        "public_benchmark_work_order_receptor_coordinate_validation_ready_row_count": _int(
            public.get("work_order_receptor_coordinate_validation_ready_row_count")
        ),
        "public_benchmark_work_order_receptor_coordinate_validation_blocked_row_count": _int(
            public.get("work_order_receptor_coordinate_validation_blocked_row_count")
        ),
        "public_benchmark_work_order_receptor_coordinate_validation_missing_row_count": _int(
            public.get("work_order_receptor_coordinate_validation_missing_row_count")
        ),
        "public_benchmark_work_order_receptor_coordinate_validation_below_min_atom_row_count": _int(
            public.get("work_order_receptor_coordinate_validation_below_min_atom_row_count")
        ),
        "public_benchmark_work_order_receptor_coordinate_validation_below_min_macromolecule_row_count": _int(
            public.get("work_order_receptor_coordinate_validation_below_min_macromolecule_row_count")
        ),
        "public_benchmark_work_order_receptor_coordinate_validation_below_min_protein_like_row_count": _int(
            public.get("work_order_receptor_coordinate_validation_below_min_protein_like_row_count")
        ),
        "public_benchmark_work_order_receptor_coordinate_validation_min_atom_records": _int(
            public.get("work_order_receptor_coordinate_validation_min_atom_records")
        ),
        "public_benchmark_work_order_receptor_coordinate_validation_min_macromolecule_atom_records": _int(
            public.get("work_order_receptor_coordinate_validation_min_macromolecule_atom_records")
        ),
        "public_benchmark_work_order_receptor_coordinate_validation_min_distinct_residues": _int(
            public.get("work_order_receptor_coordinate_validation_min_distinct_residues")
        ),
        "public_benchmark_work_order_receptor_coordinate_validation_min_protein_like_residues": _int(
            public.get("work_order_receptor_coordinate_validation_min_protein_like_residues")
        ),
        "public_benchmark_work_order_metric_evidence_required": bool(
            public.get("work_order_metric_evidence_required") is True
        ),
        "public_benchmark_work_order_metric_evidence_row_count": _int(
            public.get("work_order_metric_evidence_row_count")
        ),
        "public_benchmark_work_order_metric_evidence_ready_row_count": _int(
            public.get("work_order_metric_evidence_ready_row_count")
        ),
        "public_benchmark_work_order_metric_evidence_blocked_row_count": _int(
            public.get("work_order_metric_evidence_blocked_row_count")
        ),
        "public_benchmark_work_order_metric_evidence_missing_required_input_artifact_row_count": _int(
            public.get("work_order_metric_evidence_missing_required_input_artifact_row_count")
        ),
        "public_benchmark_work_order_metric_evidence_missing_required_input_artifact_sha256_row_count": _int(
            public.get("work_order_metric_evidence_missing_required_input_artifact_sha256_row_count")
        ),
        "public_benchmark_work_order_metric_evidence_missing_dockq_source_row_count": _int(
            public.get("work_order_metric_evidence_missing_dockq_source_row_count")
        ),
        "public_benchmark_work_order_metric_evidence_missing_lddt_pli_source_row_count": _int(
            public.get("work_order_metric_evidence_missing_lddt_pli_source_row_count")
        ),
        "public_benchmark_work_order_metric_evidence_missing_internal_deltaG_source_row_count": _int(
            public.get("work_order_metric_evidence_missing_internal_deltaG_source_row_count")
        ),
        "public_benchmark_work_order_ligand_pose_only_row_count": _int(
            public.get("work_order_ligand_pose_only_row_count")
        ),
        "public_benchmark_work_order_missing_interaction_metric_source_row_count": _int(
            public.get("work_order_missing_interaction_metric_source_row_count")
        ),
        "public_benchmark_work_order_missing_internal_deltaG_source_row_count": _int(
            public.get("work_order_missing_internal_deltaG_source_row_count")
        ),
        "public_benchmark_work_order_seed_interaction_metric_column_count": _int(
            public.get("work_order_seed_interaction_metric_column_count")
        ),
        "public_benchmark_work_order_seed_internal_deltaG_column_count": _int(
            public.get("work_order_seed_internal_deltaG_column_count")
        ),
        "public_benchmark_work_order_seed_candidate_row_count": _int(
            public.get("work_order_seed_candidate_row_count")
        ),
        "public_benchmark_work_order_seed_distinct_target_count": _int(
            public.get("work_order_seed_distinct_target_count")
        ),
        "engine_refinement_receipt_blocked_row_count": _int(receipt.get("blocked_row_count")),
        "engine_refinement_priority_top_blocker_id": str(priority.get("top_blocker_id", "")),
        "engine_refinement_priority_top_required_input": str(priority.get("top_required_input", "")),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": next_required_step,
    }
    return {
        "summary": summary,
        "source_artifacts": {
            "accuracy_parity_scorecard": str(accuracy_json),
            "gpcr_broad_claim_scope_readiness": str(gpcr_broad_json),
            "engine_refinement_tier_readiness": str(engine_refinement_json),
            "refine_tier_public_benchmark_readiness": str(public_benchmark_json),
            "refine_tier_public_benchmark_metric_source_materialization": str(
                public_benchmark_materialization_json
            ),
            "refine_tier_public_benchmark_work_order_apply_materialized": str(
                public_benchmark_materialized_apply_json
            ),
            "refine_tier_public_benchmark_statistical_support_work_order": str(
                public_benchmark_statistical_support_work_order_json
            ),
            "refine_tier_public_benchmark_statistical_support_metric_materialization_readiness": str(
                public_benchmark_statistical_support_metric_materialization_readiness_json
            ),
            "refine_tier_public_benchmark_statistical_support_metric_source_templates": str(
                public_benchmark_statistical_support_metric_source_templates_json
            ),
            "refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight": str(
                public_benchmark_statistical_support_coordinate_fetch_r4_preflight_json
            ),
            "refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt": str(
                public_benchmark_statistical_support_coordinate_fetch_operator_receipt_json
            ),
            "refine_tier_public_benchmark_claim_grade_gap_audit": str(
                public_benchmark_claim_grade_gap_audit_json
            ),
            "engine_refinement_claim_evidence_receipt": str(engine_receipt_json),
            "engine_refinement_claim_evidence_priority_packet": str(engine_priority_json),
            "product_pose_sampling_readiness": str(pose_sampling_json),
        },
    }


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Science Accuracy Frontier",
        "",
        f"- status: `{summary['status']}`",
        f"- restricted_science_accuracy_ready: `{summary['restricted_science_accuracy_ready']}`",
        f"- broad_commercial_accuracy_claim_ready: `{summary['broad_commercial_accuracy_claim_ready']}`",
        f"- gpcr_ligand_metric_ready: `{summary['gpcr_ligand_metric_ready']}`",
        f"- gpcr_target_heldout_guarded_inputs_ready: `{summary['gpcr_target_heldout_guarded_inputs_ready']}`",
        f"- engine_refinement_internal_surface_ready: `{summary['engine_refinement_internal_surface_ready']}`",
        f"- openmm_schrodinger_public_benchmark_ready: `{summary['openmm_schrodinger_public_benchmark_ready']}`",
        f"- openmm_schrodinger_public_benchmark_science_ready: `{summary['openmm_schrodinger_public_benchmark_science_ready']}`",
        f"- public_benchmark_materialized_metric_ready: `{summary['public_benchmark_materialized_metric_ready']}`",
        f"- public_benchmark_materialized_apply_ready: `{summary['public_benchmark_materialized_apply_ready']}`",
        f"- public_benchmark_materialized_rows/blocked: `{summary['public_benchmark_materialized_row_count']}/{summary['public_benchmark_materialized_blocked_row_count']}`",
        f"- public_benchmark_materialized_metric_evidence_pass/blocked: `{summary['public_benchmark_materialized_metric_evidence_pass_row_count']}/{summary['public_benchmark_materialized_metric_evidence_blocked_row_count']}`",
        f"- public_benchmark_materialized_free_energy_spearman/gate: `{summary['public_benchmark_materialized_free_energy_spearman']}/{summary['public_benchmark_materialized_free_energy_spearman_gate_ready']}`",
        "- public_benchmark_materialized_spearman_bootstrap_p05/p50/p95: "
        f"`{summary['public_benchmark_materialized_free_energy_spearman_bootstrap_p05']}/"
        f"{summary['public_benchmark_materialized_free_energy_spearman_bootstrap_p50']}/"
        f"{summary['public_benchmark_materialized_free_energy_spearman_bootstrap_p95']}`",
        "- public_benchmark_materialized_claim_grade_statistical_support_ready: "
        f"`{summary['public_benchmark_materialized_claim_grade_statistical_support_ready']}`",
        "- public_benchmark_claim_grade_gap_audit_ready/blocked_gaps: "
        f"`{summary['public_benchmark_claim_grade_gap_audit_ready']}/"
        f"{summary['public_benchmark_claim_grade_gap_audit_blocked_gap_row_count']}`",
        "- public_benchmark_claim_grade_gap_audit_observed_pair/holdout/p05_deficit: "
        f"`{summary['public_benchmark_claim_grade_gap_audit_observed_public_benchmark_pair_count']}/"
        f"{summary['public_benchmark_claim_grade_gap_audit_observed_holdout_pair_count']}/"
        f"{summary['public_benchmark_claim_grade_gap_audit_bootstrap_spearman_p05_deficit']}`",
        "- public_benchmark_claim_grade_gap_audit_coordinate_validation_pass/blocked: "
        f"`{summary['public_benchmark_claim_grade_gap_audit_coordinate_validation_pass_row_count']}/"
        f"{summary['public_benchmark_claim_grade_gap_audit_coordinate_validation_blocked_row_count']}`",
        "- public_benchmark_claim_grade_gap_audit_metric_source_payload_fill_ready/blocked: "
        f"`{summary['public_benchmark_claim_grade_gap_audit_metric_source_payload_fill_ready_row_count']}/"
        f"{summary['public_benchmark_claim_grade_gap_audit_metric_source_payload_fill_blocked_row_count']}`",
        "- public_benchmark_claim_grade_gap_audit_top_science_gap_id: "
        f"`{summary['public_benchmark_claim_grade_gap_audit_top_science_gap_id']}`",
        "- public_benchmark_statistical_support_work_order_ready: "
        f"`{summary['public_benchmark_statistical_support_work_order_ready']}`",
        "- public_benchmark_statistical_support_work_order_expansion/holdout_slots: "
        f"`{summary['public_benchmark_statistical_support_work_order_expansion_slot_count']}/"
        f"{summary['public_benchmark_statistical_support_work_order_minimum_new_holdout_pair_count']}`",
        "- public_benchmark_statistical_support_metric_materialization_ready/all_candidates_ready: "
        f"`{summary['public_benchmark_statistical_support_metric_materialization_readiness_ready']}/"
        f"{summary['public_benchmark_statistical_support_metric_materialization_all_candidates_ready']}`",
        "- public_benchmark_statistical_support_metric_materialization_row/ready/blocked: "
        f"`{summary['public_benchmark_statistical_support_metric_materialization_row_count']}/"
        f"{summary['public_benchmark_statistical_support_metric_materialization_candidate_ready_count']}/"
        f"{summary['public_benchmark_statistical_support_metric_materialization_candidate_blocked_count']}`",
        "- public_benchmark_statistical_support_metric_materialization_input_artifact_contract_ready: "
        f"`{summary['public_benchmark_statistical_support_metric_materialization_input_artifact_contract_ready']}`",
        "- public_benchmark_statistical_support_metric_materialization_required_input_present_missing: "
        f"`{summary['public_benchmark_statistical_support_metric_materialization_required_input_artifact_count']}/"
        f"{summary['public_benchmark_statistical_support_metric_materialization_present_required_input_artifact_count']}/"
        f"{summary['public_benchmark_statistical_support_metric_materialization_missing_required_input_artifact_count']}`",
        "- public_benchmark_statistical_support_coordinate_validation_pass/blocked: "
        f"`{summary['public_benchmark_statistical_support_metric_materialization_coordinate_validation_pass_row_count']}/"
        f"{summary['public_benchmark_statistical_support_metric_materialization_coordinate_validation_blocked_row_count']}`",
        "- public_benchmark_statistical_support_metric_source_payload_existing/planned: "
        f"`{summary['public_benchmark_statistical_support_metric_materialization_existing_metric_source_payload_count']}/"
        f"{summary['public_benchmark_statistical_support_metric_materialization_planned_metric_source_payload_count']}`",
        "- public_benchmark_statistical_support_required_metric_source_payloads: "
        f"`{summary['public_benchmark_statistical_support_metric_materialization_required_metric_source_payloads']}`",
        "- public_benchmark_statistical_support_metric_source_templates_ready: "
        f"`{summary['public_benchmark_statistical_support_metric_source_templates_ready']}`",
        "- public_benchmark_statistical_support_metric_source_templates_row/fill_ready/fill_blocked: "
        f"`{summary['public_benchmark_statistical_support_metric_source_templates_template_row_count']}/"
        f"{summary['public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count']}/"
        f"{summary['public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count']}`",
        "- public_benchmark_statistical_support_coordinate_fetch_r4_ready/review/fetch_required: "
        f"`{summary['public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready']}/"
        f"{summary['public_benchmark_statistical_support_coordinate_fetch_r4_ready_for_review_row_count']}/"
        f"{summary['public_benchmark_statistical_support_coordinate_fetch_r4_fetch_required_row_count']}`",
        "- public_benchmark_statistical_support_coordinate_fetch_r4_download_executed: "
        f"`{summary['public_benchmark_statistical_support_coordinate_fetch_r4_download_executed']}`",
        "- public_benchmark_statistical_support_coordinate_fetch_operator_receipt_ready/blocked: "
        f"`{summary['public_benchmark_statistical_support_coordinate_fetch_operator_receipt_ready']}/"
        f"{summary['public_benchmark_statistical_support_coordinate_fetch_operator_receipt_blocked_row_count']}`",
        "- public_benchmark_statistical_support_coordinate_fetch_operator_receipt_first_blocked: "
        f"`{summary['public_benchmark_statistical_support_coordinate_fetch_operator_receipt_first_blocked_review_id']}/"
        f"{summary['public_benchmark_statistical_support_coordinate_fetch_operator_receipt_most_common_row_blocker']}`",
        f"- engine_refinement_claim_evidence_receipt_ready: `{summary['engine_refinement_claim_evidence_receipt_ready']}`",
        f"- public_benchmark_work_order_seeded_row_count: `{summary['public_benchmark_work_order_seeded_row_count']}`",
        f"- public_benchmark_work_order_prefilled_operator_field_count: `{summary['public_benchmark_work_order_prefilled_operator_field_count']}`",
        f"- public_benchmark_work_order_pending_operator_field_count: `{summary['public_benchmark_work_order_pending_operator_field_count']}`",
        f"- public_benchmark_work_order_receptor_coordinate_validation_ready/blocked: `{summary['public_benchmark_work_order_receptor_coordinate_validation_ready_row_count']}/{summary['public_benchmark_work_order_receptor_coordinate_validation_blocked_row_count']}`",
        f"- public_benchmark_work_order_receptor_coordinate_validation_min_atom_records: `{summary['public_benchmark_work_order_receptor_coordinate_validation_min_atom_records']}`",
        f"- public_benchmark_work_order_receptor_coordinate_validation_min_macromolecule_atom_records: `{summary['public_benchmark_work_order_receptor_coordinate_validation_min_macromolecule_atom_records']}`",
        f"- public_benchmark_work_order_receptor_coordinate_validation_min_distinct_residues: `{summary['public_benchmark_work_order_receptor_coordinate_validation_min_distinct_residues']}`",
        f"- public_benchmark_work_order_receptor_coordinate_validation_min_protein_like_residues: `{summary['public_benchmark_work_order_receptor_coordinate_validation_min_protein_like_residues']}`",
        f"- public_benchmark_work_order_metric_evidence_ready/blocked: `{summary['public_benchmark_work_order_metric_evidence_ready_row_count']}/{summary['public_benchmark_work_order_metric_evidence_blocked_row_count']}`",
        f"- public_benchmark_work_order_metric_evidence_missing_required_input_artifacts: `{summary['public_benchmark_work_order_metric_evidence_missing_required_input_artifact_row_count']}`",
        f"- blockers: `{summary['blocker_count']}`",
        "",
        "## Blockers",
    ]
    lines.extend(f"- `{blocker}`" for blocker in summary["blockers"])
    if not summary["blockers"]:
        lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build the read-only science accuracy frontier packet.")
    parser.add_argument("--accuracy-json", default=DEFAULT_ACCURACY_JSON)
    parser.add_argument("--gpcr-broad-json", default=DEFAULT_GPCR_BROAD_JSON)
    parser.add_argument("--engine-refinement-json", default=DEFAULT_ENGINE_REFINEMENT_JSON)
    parser.add_argument("--public-benchmark-json", default=DEFAULT_PUBLIC_BENCHMARK_JSON)
    parser.add_argument(
        "--public-benchmark-materialization-json",
        default=DEFAULT_PUBLIC_BENCHMARK_MATERIALIZATION_JSON,
    )
    parser.add_argument(
        "--public-benchmark-materialized-apply-json",
        default=DEFAULT_PUBLIC_BENCHMARK_MATERIALIZED_APPLY_JSON,
    )
    parser.add_argument(
        "--public-benchmark-statistical-support-work-order-json",
        default=DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_WORK_ORDER_JSON,
    )
    parser.add_argument(
        "--public-benchmark-statistical-support-metric-materialization-readiness-json",
        default=DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_METRIC_MATERIALIZATION_READINESS_JSON,
    )
    parser.add_argument(
        "--public-benchmark-statistical-support-metric-source-templates-json",
        default=DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_METRIC_SOURCE_TEMPLATES_JSON,
    )
    parser.add_argument(
        "--public-benchmark-statistical-support-coordinate-fetch-r4-preflight-json",
        default=DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_FETCH_R4_PREFLIGHT_JSON,
    )
    parser.add_argument(
        "--public-benchmark-statistical-support-coordinate-fetch-operator-receipt-json",
        default=DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_FETCH_OPERATOR_RECEIPT_JSON,
    )
    parser.add_argument(
        "--public-benchmark-claim-grade-gap-audit-json",
        default=DEFAULT_PUBLIC_BENCHMARK_CLAIM_GRADE_GAP_AUDIT_JSON,
    )
    parser.add_argument("--engine-receipt-json", default=DEFAULT_ENGINE_RECEIPT_JSON)
    parser.add_argument("--engine-priority-json", default=DEFAULT_ENGINE_PRIORITY_JSON)
    parser.add_argument("--pose-sampling-json", default=DEFAULT_POSE_SAMPLING_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    payload = build_science_accuracy_frontier(
        accuracy_json=args.accuracy_json,
        gpcr_broad_json=args.gpcr_broad_json,
        engine_refinement_json=args.engine_refinement_json,
        public_benchmark_json=args.public_benchmark_json,
        public_benchmark_materialization_json=args.public_benchmark_materialization_json,
        public_benchmark_materialized_apply_json=args.public_benchmark_materialized_apply_json,
        public_benchmark_statistical_support_work_order_json=(
            args.public_benchmark_statistical_support_work_order_json
        ),
        public_benchmark_statistical_support_metric_materialization_readiness_json=(
            args.public_benchmark_statistical_support_metric_materialization_readiness_json
        ),
        public_benchmark_statistical_support_metric_source_templates_json=(
            args.public_benchmark_statistical_support_metric_source_templates_json
        ),
        public_benchmark_statistical_support_coordinate_fetch_r4_preflight_json=(
            args.public_benchmark_statistical_support_coordinate_fetch_r4_preflight_json
        ),
        public_benchmark_statistical_support_coordinate_fetch_operator_receipt_json=(
            args.public_benchmark_statistical_support_coordinate_fetch_operator_receipt_json
        ),
        public_benchmark_claim_grade_gap_audit_json=args.public_benchmark_claim_grade_gap_audit_json,
        engine_receipt_json=args.engine_receipt_json,
        engine_priority_json=args.engine_priority_json,
        pose_sampling_json=args.pose_sampling_json,
    )
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
