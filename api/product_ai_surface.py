from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/product", tags=["product-ai-surface"])

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_AI_DECISION_GRAPH_ARTIFACT = ROOT / "runs" / "product_ai_decision_graph_contract_current.json"
PRODUCT_POSE_SAMPLING_READINESS_ARTIFACT = ROOT / "runs" / "product_pose_sampling_readiness_current.json"
PRODUCT_AI_REPORT_UX_ARTIFACT = ROOT / "runs" / "product_ai_report_ux_contract_current.json"
RESIDUAL_MODEL_REGISTRY_ARTIFACT = ROOT / "runs" / "residual_model_registry_current.json"


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


@router.get("/ai-decision-graph")
async def get_product_ai_decision_graph() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_AI_DECISION_GRAPH_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    edges = packet.get("edges") if isinstance(packet.get("edges"), list) else []
    if not summary:
        return {
            "status": "missing_product_ai_decision_graph_contract",
            "artifact_path": str(PRODUCT_AI_DECISION_GRAPH_ARTIFACT),
            "closed_loop_decision_graph_ready": False,
            "production_ai_inference_enabled": False,
            "node_count": 0,
            "ready_node_count": 0,
            "blocked_node_count": 1,
            "edge_count": 0,
            "ready_edge_count": 0,
            "blocked_edge_count": 0,
            "ordered_graph_path": [],
            "structure_quality_node_ready": False,
            "binding_site_node_ready": False,
            "pose_generation_node_ready": False,
            "scoring_node_ready": False,
            "uncertainty_abstention_node_ready": False,
            "report_node_ready": False,
            "customer_report_ux_node_ready": False,
            "fail_closed_transition_ready": False,
            "viewer_interaction_surface_ready": False,
            "interaction_rationale_ready": False,
            "ligand_selection_rationale_ready": False,
            "counterfactual_rescue_suggestion_ready": False,
            "evidence_traceability_ready": False,
            "uncertainty_abstention_detail": "",
            "nodes": [],
            "edges": [],
            "execution_enabled": False,
            "docking_results_emitted": False,
            "model_inference_executed": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product AI decision graph endpoint only; local contract artifact is missing. It does not run "
                "prediction, docking, scoring, model inference, training, report rendering, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_AI_DECISION_GRAPH_ARTIFACT),
        "closed_loop_decision_graph_ready": bool(summary.get("closed_loop_decision_graph_ready") is True),
        "production_ai_inference_enabled": bool(summary.get("production_ai_inference_enabled") is True),
        "node_count": int(summary.get("node_count") or 0),
        "ready_node_count": int(summary.get("ready_node_count") or 0),
        "blocked_node_count": int(summary.get("blocked_node_count") or 0),
        "edge_count": int(summary.get("edge_count") or 0),
        "ready_edge_count": int(summary.get("ready_edge_count") or 0),
        "blocked_edge_count": int(summary.get("blocked_edge_count") or 0),
        "ordered_graph_path": list(summary.get("ordered_graph_path") or []),
        "structure_quality_node_ready": bool(summary.get("structure_quality_node_ready") is True),
        "binding_site_node_ready": bool(summary.get("binding_site_node_ready") is True),
        "pose_generation_node_ready": bool(summary.get("pose_generation_node_ready") is True),
        "scoring_node_ready": bool(summary.get("scoring_node_ready") is True),
        "uncertainty_abstention_node_ready": bool(summary.get("uncertainty_abstention_node_ready") is True),
        "report_node_ready": bool(summary.get("report_node_ready") is True),
        "customer_report_ux_node_ready": bool(summary.get("customer_report_ux_node_ready") is True),
        "fail_closed_transition_ready": bool(summary.get("fail_closed_transition_ready") is True),
        "viewer_interaction_surface_ready": bool(summary.get("viewer_interaction_surface_ready") is True),
        "interaction_rationale_ready": bool(summary.get("interaction_rationale_ready") is True),
        "ligand_selection_rationale_ready": bool(summary.get("ligand_selection_rationale_ready") is True),
        "counterfactual_rescue_suggestion_ready": bool(
            summary.get("counterfactual_rescue_suggestion_ready") is True
        ),
        "evidence_traceability_ready": bool(summary.get("evidence_traceability_ready") is True),
        "uncertainty_abstention_detail": summary.get("uncertainty_abstention_detail", ""),
        "nodes": rows,
        "edges": edges,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "model_inference_executed": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/pose-sampling-readiness")
async def get_product_pose_sampling_readiness() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_POSE_SAMPLING_READINESS_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_product_pose_sampling_readiness",
            "artifact_path": str(PRODUCT_POSE_SAMPLING_READINESS_ARTIFACT),
            "pose_sampling_readiness_ready": False,
            "pose_generation_contract_ready": False,
            "pocket_detection_ready": False,
            "multi_start_pose_ensemble_ready": False,
            "pose_centroid_pocket_bound_ready": False,
            "pose_rmsd_diversity_surface_ready": False,
            "bounded_cross_docking_induced_fit_guard_ready": False,
            "pose_claim_boundary_guard_ready": False,
            "check_count": 0,
            "pass_count": 0,
            "blocker_count": 1,
            "pose_count": 0,
            "requested_pose_start_count": 0,
            "cluster_count": 0,
            "cross_docking_pose_count": 0,
            "pocket_method": "",
            "max_pose_centroid_distance_a": 0.0,
            "claim_grade_pose_accuracy_ready": False,
            "claim_grade_induced_fit_ready": False,
            "claim_grade_cross_docking_ready": False,
            "checks": [],
            "blockers": [],
            "next_required_step": "",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product pose-sampling readiness endpoint only; the local pose-sampling artifact is missing "
                "or invalid. It does not run docking, generate customer poses, claim pose accuracy, upload, "
                "email, delete, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_POSE_SAMPLING_READINESS_ARTIFACT),
        "pose_sampling_readiness_ready": bool(summary.get("pose_sampling_readiness_ready") is True),
        "pose_generation_contract_ready": bool(summary.get("pose_generation_contract_ready") is True),
        "pocket_detection_ready": bool(summary.get("pocket_detection_ready") is True),
        "multi_start_pose_ensemble_ready": bool(summary.get("multi_start_pose_ensemble_ready") is True),
        "pose_centroid_pocket_bound_ready": bool(summary.get("pose_centroid_pocket_bound_ready") is True),
        "pose_rmsd_diversity_surface_ready": bool(summary.get("pose_rmsd_diversity_surface_ready") is True),
        "bounded_cross_docking_induced_fit_guard_ready": bool(
            summary.get("bounded_cross_docking_induced_fit_guard_ready") is True
        ),
        "pose_claim_boundary_guard_ready": bool(summary.get("pose_claim_boundary_guard_ready") is True),
        "check_count": int(summary.get("check_count") or 0),
        "pass_count": int(summary.get("pass_count") or 0),
        "blocker_count": int(summary.get("blocker_count") or 0),
        "pose_count": int(summary.get("pose_count") or 0),
        "requested_pose_start_count": int(summary.get("requested_pose_start_count") or 0),
        "cluster_count": int(summary.get("cluster_count") or 0),
        "cross_docking_pose_count": int(summary.get("cross_docking_pose_count") or 0),
        "pocket_method": summary.get("pocket_method", ""),
        "max_pose_centroid_distance_a": float(summary.get("max_pose_centroid_distance_a") or 0.0),
        "claim_grade_pose_accuracy_ready": bool(summary.get("claim_grade_pose_accuracy_ready") is True),
        "claim_grade_induced_fit_ready": bool(summary.get("claim_grade_induced_fit_ready") is True),
        "claim_grade_cross_docking_ready": bool(summary.get("claim_grade_cross_docking_ready") is True),
        "checks": rows,
        "blockers": blockers,
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/ai-report-ux")
async def get_product_ai_report_ux() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_AI_REPORT_UX_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_product_ai_report_ux_contract",
            "artifact_path": str(PRODUCT_AI_REPORT_UX_ARTIFACT),
            "ai_report_ux_ready": False,
            "structured_customer_report_ready": False,
            "customer_report_delivery_contract_ready": False,
            "customer_report_evidence_binding_ready": False,
            "customer_report_required_block_count": 0,
            "customer_report_ready_block_count": 0,
            "customer_report_blocked_block_count": 1,
            "customer_report_required_blocks": [],
            "customer_report_ready_blocks": [],
            "customer_report_missing_blocks": [],
            "customer_report_card_ready": False,
            "customer_report_card": {},
            "customer_report_viewer_binding_ready": False,
            "viewer_customer_report_binding_ready": False,
            "canonical_customer_report_required_blocks": [],
            "section_count": 0,
            "ready_section_count": 0,
            "blocked_section_count": 1,
            "binding_site_explanation_ready": False,
            "pose_comparison_ready": False,
            "interaction_rationale_ready": False,
            "ligand_selection_rationale_ready": False,
            "uncertainty_narrative_ready": False,
            "counterfactual_rescue_suggestion_ready": False,
            "evidence_traceability_ready": False,
            "scope_claim_limit_ready": False,
            "selection_rationale": "",
            "primary_abstention_reason": "",
            "what_would_change_decision": "",
            "allowed_scope_families": [],
            "blocked_claim_scopes": [],
            "claim_blocked_domains": [],
            "general_platform_claim_allowed": False,
            "viewer_ready": False,
            "viewer_index": "",
            "viewer_app": "",
            "viewer_interaction_surface_ready": False,
            "report_sections": [],
            "execution_enabled": False,
            "docking_results_emitted": False,
            "model_inference_executed": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product AI report UX endpoint only; local UX contract artifact is missing. It does not render a "
                "browser, run docking, run model inference, train models, upload, email, delete, or mutate external state."
            ),
        }
    report_card = summary.get("customer_report_card")
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_AI_REPORT_UX_ARTIFACT),
        "ai_report_ux_ready": bool(summary.get("ai_report_ux_ready") is True),
        "structured_customer_report_ready": bool(summary.get("structured_customer_report_ready") is True),
        "customer_report_delivery_contract_ready": bool(
            summary.get("customer_report_delivery_contract_ready") is True
        ),
        "customer_report_evidence_binding_ready": bool(
            summary.get("customer_report_evidence_binding_ready") is True
        ),
        "customer_report_required_block_count": int(summary.get("customer_report_required_block_count") or 0),
        "customer_report_ready_block_count": int(summary.get("customer_report_ready_block_count") or 0),
        "customer_report_blocked_block_count": int(summary.get("customer_report_blocked_block_count") or 0),
        "customer_report_required_blocks": list(summary.get("customer_report_required_blocks") or []),
        "customer_report_ready_blocks": list(summary.get("customer_report_ready_blocks") or []),
        "customer_report_missing_blocks": list(summary.get("customer_report_missing_blocks") or []),
        "customer_report_card_ready": bool(summary.get("customer_report_card_ready") is True),
        "customer_report_card": report_card if isinstance(report_card, dict) else {},
        "customer_report_viewer_binding_ready": bool(summary.get("customer_report_viewer_binding_ready") is True),
        "viewer_customer_report_binding_ready": bool(summary.get("viewer_customer_report_binding_ready") is True),
        "canonical_customer_report_required_blocks": list(
            summary.get("canonical_customer_report_required_blocks") or []
        ),
        "section_count": int(summary.get("section_count") or 0),
        "ready_section_count": int(summary.get("ready_section_count") or 0),
        "blocked_section_count": int(summary.get("blocked_section_count") or 0),
        "binding_site_explanation_ready": bool(summary.get("binding_site_explanation_ready") is True),
        "pose_comparison_ready": bool(summary.get("pose_comparison_ready") is True),
        "interaction_rationale_ready": bool(summary.get("interaction_rationale_ready") is True),
        "ligand_selection_rationale_ready": bool(summary.get("ligand_selection_rationale_ready") is True),
        "uncertainty_narrative_ready": bool(summary.get("uncertainty_narrative_ready") is True),
        "counterfactual_rescue_suggestion_ready": bool(
            summary.get("counterfactual_rescue_suggestion_ready") is True
        ),
        "evidence_traceability_ready": bool(summary.get("evidence_traceability_ready") is True),
        "scope_claim_limit_ready": bool(summary.get("scope_claim_limit_ready") is True),
        "selection_rationale": summary.get("selection_rationale", ""),
        "primary_abstention_reason": summary.get("primary_abstention_reason", ""),
        "what_would_change_decision": summary.get("what_would_change_decision", ""),
        "allowed_scope_families": list(summary.get("allowed_scope_families") or []),
        "blocked_claim_scopes": list(summary.get("blocked_claim_scopes") or []),
        "claim_blocked_domains": list(summary.get("claim_blocked_domains") or []),
        "general_platform_claim_allowed": bool(summary.get("general_platform_claim_allowed") is True),
        "viewer_ready": bool(summary.get("viewer_ready") is True),
        "viewer_index": summary.get("viewer_index", ""),
        "viewer_app": summary.get("viewer_app", ""),
        "viewer_interaction_surface_ready": bool(summary.get("viewer_interaction_surface_ready") is True),
        "report_sections": rows,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "model_inference_executed": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/residual-model-registry")
async def get_product_residual_model_registry() -> dict[str, Any]:
    packet = _read_json_object(RESIDUAL_MODEL_REGISTRY_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_residual_model_registry",
            "artifact_path": str(RESIDUAL_MODEL_REGISTRY_ARTIFACT),
            "registry_ready": False,
            "product_model_layer_ready": False,
            "production_ai_inference_subject_active": False,
            "default_residual_mode": "",
            "production_promotion_allowed": False,
            "production_mode_allowed": False,
            "customer_facing_auto_correction_allowed": False,
            "customer_facing_score_mutation_allowed": False,
            "customer_facing_ranking_mutation_allowed": False,
            "trained_model_checkpoint_count": 0,
            "candidate_checkpoint_count": 0,
            "checkpoint_preflight_ready": False,
            "production_checkpoint_blocked": True,
            "production_promotion_blocked_reason": "missing_residual_model_registry",
            "checkpoint_primary_blocker": "",
            "checkpoint_missing_output_fields": [],
            "checkpoint_missing_adapter_output_policy_fields": [],
            "selected_sidecar_ready": False,
            "selected_sidecar_status": "",
            "selected_sidecar_blockers": [],
            "selected_sidecar_missing_output_fields": [],
            "selected_sidecar_training_contract_ready": False,
            "selected_sidecar_training_contract_missing_label_fields": [],
            "selected_sidecar_force_receipt_ready": False,
            "selected_sidecar_force_receipt_operator_verified": False,
            "selected_sidecar_force_receipt_operator_verified_true_count": 0,
            "selected_sidecar_force_receipt_expected_queue_rows": 0,
            "required_output_fields": [],
            "required_output_fields_present": False,
            "component_count": 0,
            "required_component_count": 0,
            "required_components_present": False,
            "components": [],
            "source_artifacts": [],
            "next_required_step": "Run python3 tools/build_residual_model_registry.py.",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "model_promoted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product residual-model-registry endpoint only; the local registry artifact is missing. "
                "It does not train models, run inference, create checkpoints, promote production mode, or mutate external state."
            ),
        }
    production_ai_inference_subject_active = bool(
        summary.get("production_promotion_allowed") is True
        and summary.get("production_mode_allowed") is True
        and int(summary.get("trained_model_checkpoint_count") or 0) > 0
        and str(summary.get("default_residual_mode") or "") != "shadow"
    )
    return {
        "status": summary.get("status", ""),
        "artifact_path": str(RESIDUAL_MODEL_REGISTRY_ARTIFACT),
        "registry_ready": bool(summary.get("registry_ready") is True),
        "product_model_layer_ready": bool(summary.get("product_model_layer_ready") is True),
        "production_ai_inference_subject_active": production_ai_inference_subject_active,
        "default_residual_mode": summary.get("default_residual_mode", ""),
        "production_promotion_allowed": bool(summary.get("production_promotion_allowed") is True),
        "production_mode_allowed": bool(summary.get("production_mode_allowed") is True),
        "customer_facing_auto_correction_allowed": bool(
            summary.get("customer_facing_auto_correction_allowed") is True
        ),
        "customer_facing_score_mutation_allowed": bool(
            summary.get("customer_facing_score_mutation_allowed") is True
        ),
        "customer_facing_ranking_mutation_allowed": bool(
            summary.get("customer_facing_ranking_mutation_allowed") is True
        ),
        "trained_model_checkpoint_count": int(summary.get("trained_model_checkpoint_count") or 0),
        "candidate_checkpoint_count": int(summary.get("candidate_checkpoint_count") or 0),
        "checkpoint_preflight_ready": bool(summary.get("checkpoint_preflight_ready") is True),
        "production_checkpoint_blocked": bool(summary.get("production_checkpoint_blocked") is True),
        "production_promotion_blocked_reason": summary.get("production_promotion_blocked_reason", ""),
        "checkpoint_primary_blocker": summary.get("checkpoint_primary_blocker", ""),
        "checkpoint_missing_output_fields": list(summary.get("checkpoint_missing_output_fields") or []),
        "checkpoint_missing_adapter_output_policy_fields": list(
            summary.get("checkpoint_missing_adapter_output_policy_fields") or []
        ),
        "selected_sidecar_ready": bool(summary.get("selected_sidecar_ready") is True),
        "selected_sidecar_status": summary.get("selected_sidecar_status", ""),
        "selected_sidecar_blockers": list(summary.get("selected_sidecar_blockers") or []),
        "selected_sidecar_missing_output_fields": list(summary.get("selected_sidecar_missing_output_fields") or []),
        "selected_sidecar_training_contract_ready": bool(
            summary.get("selected_sidecar_training_contract_ready") is True
        ),
        "selected_sidecar_training_contract_missing_label_fields": list(
            summary.get("selected_sidecar_training_contract_missing_label_fields") or []
        ),
        "selected_sidecar_force_receipt_ready": bool(summary.get("selected_sidecar_force_receipt_ready") is True),
        "selected_sidecar_force_receipt_operator_verified": bool(
            summary.get("selected_sidecar_force_receipt_operator_verified") is True
        ),
        "selected_sidecar_force_receipt_operator_verified_true_count": int(
            summary.get("selected_sidecar_force_receipt_operator_verified_true_count") or 0
        ),
        "selected_sidecar_force_receipt_expected_queue_rows": int(
            summary.get("selected_sidecar_force_receipt_expected_queue_rows") or 0
        ),
        "required_output_fields": list(summary.get("required_output_fields") or []),
        "required_output_fields_present": bool(summary.get("required_output_fields_present") is True),
        "component_count": int(summary.get("component_count") or 0),
        "required_component_count": int(summary.get("required_component_count") or 0),
        "required_components_present": bool(summary.get("required_components_present") is True),
        "components": rows,
        "source_artifacts": list(summary.get("source_artifacts") or []),
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }
