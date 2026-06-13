from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from api.config import settings
from api.docking_dispatch import dispatch_docking_job_if_eligible
from api.job_store import SQLiteJobStore
from betelgeuze_product.docking_request import build_docking_job_record, persist_docking_job_record
from betelgeuze_product.job_orchestration import (
    cancel_job_record,
    job_history,
    list_job_records,
    retry_job_record,
)
from betelgeuze_product.license_decision import APPROVAL_TOKEN as LICENSE_APPROVAL_TOKEN
from betelgeuze_product.license_decision import DECISION_CREATE_LICENSE, REQUIRED_FIELDS as LICENSE_REQUIRED_FIELDS
from betelgeuze_product.structure_analysis import analyze_structure_source
from api.product_accounting import (
    commercial_delta_force_closure_fields as _commercial_delta_force_closure_fields,
    commercial_engine_refinement_claim_fields as _commercial_engine_refinement_claim_fields,
    commercial_first_parallelizable_source_modality_fields as _commercial_first_parallelizable_source_modality_fields,
    commercial_first_worker_runtime_receipt_fields as _commercial_first_worker_runtime_receipt_fields,
    commercial_handoff_closure_acceptance_fields as _commercial_handoff_closure_acceptance_fields,
    commercial_production_ai_registry_promotion_fields as _commercial_production_ai_registry_promotion_fields,
    commercial_production_ai_return_fields as _commercial_production_ai_return_fields,
    commercial_scope_breadth_evidence_receipt_fields as _commercial_scope_breadth_evidence_receipt_fields,
    commercial_scope_closure_fields as _commercial_scope_closure_fields,
)

router = APIRouter(prefix="/product", tags=["product"])
ROOT = Path(__file__).resolve().parents[1]
PRODUCT_CAPABILITY_ARTIFACT = ROOT / "runs" / "product_capability_surface_contract_current.json"
PRODUCT_ARCHITECTURE_ARTIFACT = ROOT / "runs" / "product_architecture_contract_current.json"
ARCHITECTURE_VALIDATION_REPORT_ARTIFACT = ROOT / "runs" / "architecture_validation_package_report_current.json"
COMPETITION_EXTERNAL_OPERATOR_TRACK_ARTIFACT = ROOT / "runs" / "competition_external_operator_track_current.json"
PRODUCT_SERVICE_BOUNDARY_ARTIFACT = ROOT / "runs" / "product_service_boundary_contract_current.json"
PRODUCT_API_CONTRACT_ARTIFACT = ROOT / "runs" / "product_api_contract_current.json"
PRODUCT_OPERATIONAL_QUALITY_ARTIFACT = ROOT / "runs" / "product_operational_quality_contract_current.json"
PRODUCT_SECURITY_DEPLOYMENT_ARTIFACT = ROOT / "runs" / "product_security_deployment_contract_current.json"
PRODUCT_RELEASE_OPERATIONS_ARTIFACT = ROOT / "runs" / "product_release_operations_dossier_current.json"
PRODUCT_EXECUTION_APPROVAL_ARTIFACT = ROOT / "runs" / "product_execution_approval_gate_current.json"
PRODUCT_PUBLIC_BENCHMARK_WORK_ORDER_ARTIFACT = ROOT / "runs" / "product_public_benchmark_work_order_current.json"
EXTERNAL_METRIC_SCORECARD_ARTIFACT = ROOT / "runs" / "external_metric_scorecard_current.json"
PRODUCT_TRAJECTORY_SLA_CONTRACT_ARTIFACT = ROOT / "runs" / "product_trajectory_sla_contract_current.json"
PRODUCT_JOB_ORCHESTRATION_CONTRACT_ARTIFACT = ROOT / "runs" / "product_job_orchestration_contract_current.json"
PRODUCT_AI_DECISION_GRAPH_ARTIFACT = ROOT / "runs" / "product_ai_decision_graph_contract_current.json"
PRODUCT_POSE_SAMPLING_READINESS_ARTIFACT = ROOT / "runs" / "product_pose_sampling_readiness_current.json"
PRODUCT_AI_REPORT_UX_ARTIFACT = ROOT / "runs" / "product_ai_report_ux_contract_current.json"
CAMEO_VALIDATION_OPERATIONS_ARTIFACT = ROOT / "runs" / "cameo_validation_operations_dossier_current.json"
CAMEO_OFFICIAL_RESULTS_ARTIFACT = ROOT / "runs" / "cameo_official_results_intake_gate_current.json"
CAMEO_OFFICIAL_RESULTS_TEMPLATE = ROOT / "runs" / "cameo_official_results_operator_template_current.csv"
CAMEO_OFFICIAL_RESULTS_INTAKE = ROOT / "runs" / "cameo_official_results_operator_intake.csv"
CAMEO_PUBLIC_REGISTRATION_ARTIFACT = ROOT / "runs" / "cameo_public_registration_approval_gate_current.json"
CAMEO_PUBLIC_REGISTRATION_TEMPLATE = ROOT / "runs" / "cameo_public_registration_operator_approval_template_current.csv"
CAMEO_PUBLIC_REGISTRATION_INTAKE = ROOT / "runs" / "cameo_public_registration_operator_approval_intake.csv"
PRODUCT_LICENSE_DECISION_ARTIFACT = ROOT / "runs" / "product_license_decision_gate_current.json"
PRODUCT_LICENSE_DECISION_PACKET_ARTIFACT = ROOT / "runs" / "product_license_decision_packet_current.json"
PRODUCT_LICENSE_FILE_WORK_ORDER_ARTIFACT = ROOT / "runs" / "product_license_file_creation_work_order_current.json"
PRODUCT_LICENSE_DECISION_TEMPLATE = ROOT / "runs" / "product_license_decision_operator_template_current.csv"
PRODUCT_LICENSE_DECISION_INTAKE = ROOT / "runs" / "product_license_decision_operator_intake.csv"
PRODUCT_COMMERCIAL_INDEPENDENCE_ARTIFACT = ROOT / "runs" / "product_commercial_independence_gate_current.json"
GOAL_RELEASE_DECISION_ARTIFACT = ROOT / "runs" / "goal_release_decision_gate_current.json"
PRODUCT_GOAL_COMPLETION_AUDIT_ARTIFACT = ROOT / "runs" / "product_goal_completion_audit_current.json"
GOAL_READINESS_ROLLUP_ARTIFACT = ROOT / "runs" / "goal_readiness_rollup_current.json"
PRODUCT_COMMERCIAL_READINESS_OPERATOR_PACKET_ARTIFACT = (
    ROOT / "runs" / "product_commercial_readiness_operator_packet_current.json"
)
PRODUCT_COMMERCIAL_READINESS_OPERATOR_PACKET_FRESHNESS_ARTIFACT = (
    ROOT / "runs" / "product_commercial_readiness_operator_packet_freshness_current.json"
)
PRODUCT_COMMERCIAL_READINESS_EXECUTION_LADDER_ARTIFACT = (
    ROOT / "runs" / "product_commercial_readiness_execution_ladder_current.json"
)
PRODUCT_COMMERCIAL_READINESS_HANDOFF_BUNDLE_ARTIFACT = (
    ROOT / "runs" / "product_commercial_readiness_handoff_bundle_current.json"
)
PRODUCT_FULL_COMMERCIAL_BLOCKER_EVIDENCE_MATRIX_ARTIFACT = (
    ROOT / "runs" / "product_full_commercial_blocker_evidence_matrix_current.json"
)
PRODUCT_SCOPE_BREADTH_CONTRACT_ARTIFACT = ROOT / "runs" / "product_scope_breadth_contract_current.json"
PRODUCT_SCOPE_CLAIM_GUARD_ARTIFACT = ROOT / "runs" / "product_scope_breadth_closure_checklist_current.json"
PRODUCT_SCOPE_EVIDENCE_PRIORITY_ARTIFACT = (
    ROOT / "runs" / "product_scope_breadth_evidence_priority_packet_current.json"
)
PRODUCT_SCOPE_EVIDENCE_INTAKE_READINESS_ARTIFACT = (
    ROOT / "runs" / "product_scope_breadth_evidence_intake_readiness_current.json"
)
TRANSPORTER_MANUAL_REVIEW_INTAKE_ARTIFACT = ROOT / "runs" / "transporter_manual_review_intake_template_current.json"
PXR_EXACT_REVIEW_INTAKE_ARTIFACT = ROOT / "runs" / "pxr_exact_evidence_review_intake_template_current.json"
AQP1_OPERATOR_VALIDATION_CANDIDATE_ARTIFACT = (
    ROOT / "runs" / "aqp1_operator_validation_candidate_packet_current.json"
)
AQP1_DIRECT_BINDING_PROCUREMENT_ARTIFACT = (
    ROOT / "runs" / "aqp1_direct_binding_procurement_packet_current.json"
)
PRODUCT_PRODUCTION_AI_CHECKPOINT_READINESS_ARTIFACT = (
    ROOT / "runs" / "product_production_ai_checkpoint_readiness_current.json"
)
PRODUCT_PRODUCTION_AI_PROMOTION_WORKBENCH_ARTIFACT = (
    ROOT / "runs" / "product_production_ai_promotion_workbench_current.json"
)
PRODUCT_PRODUCTION_AI_GPU_RETURN_INTAKE_ARTIFACT = (
    ROOT / "runs" / "product_production_ai_gpu_return_intake_current.json"
)
RESIDUAL_MODEL_REGISTRY_ARTIFACT = ROOT / "runs" / "residual_model_registry_current.json"
RESIDUAL_PRODUCTION_CHECKPOINT_WORK_ORDER_ARTIFACT = (
    ROOT / "runs" / "residual_production_checkpoint_work_order_current.json"
)
RESIDUAL_PRODUCTION_TRAINING_DATA_CONTRACT_ARTIFACT = (
    ROOT / "runs" / "residual_production_training_data_contract_current.json"
)
RESIDUAL_FORCE_GPU_WORKER_RETURN_RECEIPT_ARTIFACT = ROOT / "runs" / "residual_force_gpu_worker_return_receipt_current.json"
RESIDUAL_FORCE_GPU_WORKER_HANDOFF_ARTIFACT = ROOT / "runs" / "residual_force_gpu_worker_handoff_package_current.json"
RESIDUAL_FORCE_GPU_WORKER_DISPATCH_MANIFEST_ARTIFACT = (
    ROOT / "runs" / "residual_force_gpu_worker_dispatch_manifest_current.json"
)
RESIDUAL_FORCE_GPU_WORKER_DISPATCH_BUNDLE_ARTIFACT = (
    ROOT / "runs" / "residual_force_gpu_worker_dispatch_bundle_current.json"
)
RESIDUAL_FORCE_GPU_WORKER_EXECUTION_RUNBOOK_ARTIFACT = (
    ROOT / "runs" / "residual_force_gpu_worker_execution_runbook_current.json"
)
ROCM_ENVIRONMENT_MANIFEST_ARTIFACT = ROOT / "runs" / "rocm_environment_manifest_current.json"


class LigandInput(BaseModel):
    ligand_id: str | None = None
    smiles: str | None = None
    sdf_path: str | None = None
    mol2_path: str | None = None
    pdbqt_path: str | None = None
    inchi: str | None = None
    compound_id: str | None = None


class DockingJobRequest(BaseModel):
    request_type: str = "structure_analysis_ligand_docking"
    family: str
    customer_id: str | None = None
    user_id: str | None = None
    target_id: str | None = None
    target_name: str | None = None
    pdb_id: str | None = None
    pdb_path: str | None = None
    pdb_content: str | None = None
    mmcif_path: str | None = None
    mmcif_content: str | None = None
    ligands: list[LigandInput] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StructureAnalysisRequest(BaseModel):
    pdb_id: str | None = None
    pdb_path: str | None = None
    pdb_content: str | None = None
    mmcif_path: str | None = None
    mmcif_content: str | None = None


class JobActionRequest(BaseModel):
    reason: str | None = None
    actor: str | None = None


def _model_to_dict(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _jobs_dir() -> Path:
    return Path(settings.results_storage_path) / "product_docking_jobs"


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


def _goal_readiness_rollup_lane_surface(readiness: dict[str, Any]) -> dict[str, Any]:
    readiness = readiness or {}
    return {
        "release_complete_vs_operator_pending_lane": readiness.get(
            "release_complete_vs_operator_pending_lane", ""
        ),
        "goal_completion_audit_goal_complete": readiness.get("goal_completion_audit_goal_complete"),
        "release_complete_lane_ready": readiness.get("release_complete_lane_ready"),
        "operator_pending_lane_ready": readiness.get("operator_pending_lane_ready"),
        "operator_or_external_pending_lane_count": int(
            readiness.get("operator_or_external_pending_lane_count") or 0
        ),
        "release_complete_vs_operator_pending_matrix": list(
            readiness.get("release_complete_vs_operator_pending_matrix") or []
        ),
    }


@router.post("/docking/jobs")
async def submit_docking_job(payload: DockingJobRequest, request: Request) -> dict[str, Any]:
    record = build_docking_job_record(
        _model_to_dict(payload),
        source_host=request.client.host if request.client else "",
        residual_registry_packet=_read_json_object(RESIDUAL_MODEL_REGISTRY_ARTIFACT),
        scope_claim_guard_packet=_read_json_object(PRODUCT_SCOPE_CLAIM_GUARD_ARTIFACT),
    )
    path = persist_docking_job_record(record, _jobs_dir())
    dispatch_outcome = dispatch_docking_job_if_eligible(
        record,
        jobs_dir=_jobs_dir(),
        store=SQLiteJobStore(settings.api_job_store_path),
    )
    return {
        "job_id": record["job_id"],
        "status": record["status"],
        "customer_id": record["customer_id"],
        "user_id": record["user_id"],
        "validation_status": record["validation_status"],
        "blocker_count": len(record["blockers"]),
        "warning_count": len(record["warnings"]),
        "structure_analysis_status": record["structure_analysis_status"],
        "structure_source_available": record["structure_source_available"],
        "structure_atom_count": record["structure_atom_count"],
        "structure_chain_count": record["structure_chain_count"],
        "structure_ligand_like_residue_count": record["structure_ligand_like_residue_count"],
        "execution_enabled": record["execution_enabled"],
        "docking_results_emitted": record["docking_results_emitted"],
        "production_ai_inference_subject_active": record["production_ai_inference_subject_active"],
        "production_ai_correction_applied": record["production_ai_correction_applied"],
        "production_ai_abstention_enforced": record["production_ai_abstention_enforced"],
        "production_ai_abstention_reason": record["production_ai_abstention_reason"],
        "production_ai_what_would_change_decision": record["production_ai_what_would_change_decision"],
        "production_ai_default_residual_mode": record["production_ai_default_residual_mode"],
        "production_ai_promotion_allowed": record["production_ai_promotion_allowed"],
        "production_ai_customer_facing_auto_correction_allowed": record[
            "production_ai_customer_facing_auto_correction_allowed"
        ],
        "production_ai_customer_facing_score_mutation_allowed": record[
            "production_ai_customer_facing_score_mutation_allowed"
        ],
        "production_ai_customer_facing_ranking_mutation_allowed": record[
            "production_ai_customer_facing_ranking_mutation_allowed"
        ],
        "production_ai_trained_checkpoint_count": record["production_ai_trained_checkpoint_count"],
        "production_ai_selected_sidecar_ready": record["production_ai_selected_sidecar_ready"],
        "production_ai_selected_sidecar_missing_output_fields": record[
            "production_ai_selected_sidecar_missing_output_fields"
        ],
        "production_ai_blocked_reason": record["production_ai_blocked_reason"],
        "scope_claim_guard_ready": record["scope_claim_guard_ready"],
        "scope_claim_allowed_for_request": record["scope_claim_allowed_for_request"],
        "scope_claim_status": record["scope_claim_status"],
        "allowed_scope_families": record["allowed_scope_families"],
        "blocked_claim_scopes": record["blocked_claim_scopes"],
        "claim_blocked_domains": record["claim_blocked_domains"],
        "general_platform_claim_allowed": record["general_platform_claim_allowed"],
        "scope_claim_boundary_detail": record["scope_claim_boundary_detail"],
        "ai_decision_graph_trace_ready": record["ai_decision_graph_trace_ready"],
        "ai_decision_graph_ordered_path": record["ai_decision_graph_ordered_path"],
        "ai_decision_graph_node_count": record["ai_decision_graph_node_count"],
        "ai_decision_graph_edge_count": record["ai_decision_graph_edge_count"],
        "ai_decision_graph_blocked_node_ids": record["ai_decision_graph_blocked_node_ids"],
        "ai_decision_graph_abstention_node_id": record["ai_decision_graph_abstention_node_id"],
        "ai_decision_graph_current_node_id": record["ai_decision_graph_current_node_id"],
        "ai_decision_graph_trace": record["ai_decision_graph_trace"],
        "ai_decision_graph_edges": record["ai_decision_graph_edges"],
        "customer_report_explanation_ready": record["customer_report_explanation_ready"],
        "customer_report_card_ready": record["customer_report_card_ready"],
        "customer_report_delivery_contract_ready": record["customer_report_delivery_contract_ready"],
        "customer_report_evidence_binding_ready": record["customer_report_evidence_binding_ready"],
        "customer_report_selection_rationale_ready": record["customer_report_selection_rationale_ready"],
        "customer_report_uncertainty_posture_ready": record["customer_report_uncertainty_posture_ready"],
        "customer_report_prohibited_claims_ready": record["customer_report_prohibited_claims_ready"],
        "customer_report_selection_rationale": record["customer_report_selection_rationale"],
        "customer_report_uncertainty_posture": record["customer_report_uncertainty_posture"],
        "customer_report_prohibited_claims": record["customer_report_prohibited_claims"],
        "customer_report_required_block_count": record["customer_report_required_block_count"],
        "customer_report_ready_block_count": record["customer_report_ready_block_count"],
        "customer_report_blocked_block_count": record["customer_report_blocked_block_count"],
        "customer_report_section_count": record["customer_report_section_count"],
        "customer_report_required_blocks": record["customer_report_required_blocks"],
        "customer_report_ready_blocks": record["customer_report_ready_blocks"],
        "customer_report_missing_blocks": record["customer_report_missing_blocks"],
        "customer_report_primary_abstention_reason": record["customer_report_primary_abstention_reason"],
        "customer_report_what_would_change_decision": record["customer_report_what_would_change_decision"],
        "customer_report_card": record["customer_report_card"],
        "customer_report_sections": record["customer_report_sections"],
        "progress_percent": record["progress_percent"],
        "progress_state": record["progress_state"],
        "current_step": record["current_step"],
        "worker_state": record["worker_state"],
        "worker_lease_id": record["worker_lease_id"],
        "worker_id": record["worker_id"],
        "heartbeat_at_utc": record["heartbeat_at_utc"],
        "worker_cancel_acknowledged": record["worker_cancel_acknowledged"],
        "worker_cancel_acknowledged_at_utc": record["worker_cancel_acknowledged_at_utc"],
        "queue_status": record["queue_status"],
        "queue_position": record["queue_position"],
        "max_retry_attempts": record["max_retry_attempts"],
        "retry_policy": record["retry_policy"],
        "retry_limit_reached": record["retry_limit_reached"],
        "progress_percent_range_valid": record["progress_percent_range_valid"],
        "status_progress_contract_ready": record["status_progress_contract_ready"],
        "workflow_controls_ready": record["workflow_controls_ready"],
        "workflow_control_links": record["workflow_control_links"],
        "workflow_allowed_actions": record["workflow_allowed_actions"],
        "workflow_disabled_actions": record["workflow_disabled_actions"],
        "workflow_next_customer_actions": record["workflow_next_customer_actions"],
        "status_transition_contract": record["status_transition_contract"],
        "status_snapshot_persisted": record["status_snapshot_persisted"],
        "job_retention_policy": record["job_retention_policy"],
        "job_retention_days": record["job_retention_days"],
        "rerun_manifest_ready": record["rerun_manifest_ready"],
        "reproducible_rerun_ready": record["reproducible_rerun_ready"],
        "long_running_status_persistence_ready": record["long_running_status_persistence_ready"],
        "ledger_path": str(path),
        "engine_dispatch_ready": record.get("engine_dispatch_ready", False),
        "worker_dispatch_enqueued": bool(dispatch_outcome.get("dispatched", False)),
        "worker_dispatch_reason": str(dispatch_outcome.get("reason", "")),
        "claim_boundary": record["claim_boundary"],
    }


@router.post("/structure/analyze")
async def analyze_product_structure(payload: StructureAnalysisRequest) -> dict[str, Any]:
    analysis = analyze_structure_source(_model_to_dict(payload), root=ROOT)
    return {
        **analysis,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
    }


@router.get("/capabilities")
async def get_product_capabilities() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_CAPABILITY_ARTIFACT)
    summary = packet.get("summary") if isinstance(packet.get("summary"), dict) else {}
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_product_capability_surface_contract",
            "artifact_path": str(PRODUCT_CAPABILITY_ARTIFACT),
            "capability_count": 0,
            "ready_capability_count": 0,
            "blocked_capability_count": 1,
            "allowed_scope_families": [],
            "restricted_scope_claim_guard_ready": False,
            "blocked_claim_scopes": ["capability_surface_contract_missing"],
            "general_platform_claim_allowed": False,
            "scope_claim_boundary_detail": "missing_product_capability_surface_contract",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product capability endpoint only; the local capability surface artifact is missing or invalid. "
                "It does not run docking, emit scientific results, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_CAPABILITY_ARTIFACT),
        "target_id": summary.get("target_id", ""),
        "family": summary.get("family", ""),
        "ligand_count": int(summary.get("ligand_count") or 0),
        "capability_count": int(summary.get("capability_count") or 0),
        "ready_capability_count": int(summary.get("ready_capability_count") or 0),
        "blocked_capability_count": int(summary.get("blocked_capability_count") or 0),
        "structure_analysis_capability_ready": bool(summary.get("structure_analysis_capability_ready") is True),
        "ligand_docking_capability_ready": bool(summary.get("ligand_docking_capability_ready") is True),
        "local_delivery_bundle_capability_ready": bool(summary.get("local_delivery_bundle_capability_ready") is True),
        "api_surface_ready": bool(summary.get("api_surface_ready") is True),
        "product_service_boundary_endpoint_present": bool(summary.get("product_service_boundary_endpoint_present") is True),
        "product_api_contract_endpoint_present": bool(summary.get("product_api_contract_endpoint_present") is True),
        "guarded_claims_ready": bool(summary.get("guarded_claims_ready") is True),
        "allowed_scope_families": summary.get("allowed_scope_families", []),
        "restricted_scope_claim_guard_ready": bool(summary.get("restricted_scope_claim_guard_ready") is True),
        "blocked_claim_scopes": summary.get("blocked_claim_scopes", []),
        "general_platform_claim_allowed": bool(summary.get("general_platform_claim_allowed") is True),
        "restricted_unattended_execution_ready": bool(summary.get("restricted_unattended_execution_ready") is True),
        "restricted_unattended_execution_runtime_ready": bool(summary.get("restricted_unattended_execution_runtime_ready") is True),
        "scope_claim_boundary_detail": summary.get("scope_claim_boundary_detail", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "capabilities": rows,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/architecture")
async def get_product_architecture() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_ARCHITECTURE_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    approval_required = packet.get("approval_required") if isinstance(packet.get("approval_required"), list) else []
    if not summary:
        return {
            "status": "missing_product_architecture_contract",
            "artifact_path": str(PRODUCT_ARCHITECTURE_ARTIFACT),
            "local_architecture_surface_ready": False,
            "architecture_release_ready": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "cameo_submission_executed": False,
            "casp_submission_executed": False,
            "cleanup_executed": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product architecture endpoint only; the local product architecture contract is missing or invalid. "
                "It does not run docking, submit predictions, delete files, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status")
        or (
            "product_scope_breadth_closure_checklist_ready"
            if summary.get("closure_checklist_ready") is True
            else "blocked_product_scope_breadth_closure_checklist"
        ),
        "artifact_path": str(PRODUCT_ARCHITECTURE_ARTIFACT),
        "local_architecture_surface_ready": bool(summary.get("local_architecture_surface_ready") is True),
        "architecture_release_ready": bool(summary.get("architecture_release_ready") is True),
        "lane_count": int(summary.get("lane_count") or 0),
        "ready_lane_count": int(summary.get("ready_lane_count") or 0),
        "blocked_lane_count": int(summary.get("blocked_lane_count") or 0),
        "approval_required_lane_count": int(summary.get("approval_required_lane_count") or 0),
        "structure_analysis_product_surface_ready": bool(summary.get("structure_analysis_product_surface_ready") is True),
        "ligand_docking_execution_contract_ready": bool(summary.get("ligand_docking_execution_contract_ready") is True),
        "commercial_independence_ready": bool(summary.get("commercial_independence_ready") is True),
        "product_service_boundary_ready": bool(summary.get("product_service_boundary_ready") is True),
        "product_api_contract_ready": bool(summary.get("product_api_contract_ready") is True),
        "cameo_local_surface_ready": bool(summary.get("cameo_local_surface_ready") is True),
        "cameo_service_boundary_ready": bool(summary.get("cameo_service_boundary_ready") is True),
        "cameo_service_boundary_status": summary.get("cameo_service_boundary_status", ""),
        "cameo_service_boundary_api_route_count": int(summary.get("cameo_service_boundary_api_route_count") or 0),
        "cameo_service_boundary_cli_command_count": int(summary.get("cameo_service_boundary_cli_command_count") or 0),
        "cameo_api_contract_ready": bool(summary.get("cameo_api_contract_ready") is True),
        "cameo_api_contract_status": summary.get("cameo_api_contract_status", ""),
        "cameo_api_contract_expected_route_count": int(summary.get("cameo_api_contract_expected_route_count") or 0),
        "cameo_api_contract_missing_route_count": int(summary.get("cameo_api_contract_missing_route_count") or 0),
        "cameo_api_contract_status_response_missing_key_count": int(
            summary.get("cameo_api_contract_status_response_missing_key_count") or 0
        ),
        "cameo_architecture_validation_ready": bool(summary.get("cameo_architecture_validation_ready") is True),
        "cleanup_control_surface_ready": bool(summary.get("cleanup_control_surface_ready") is True),
        "cleanup_postcheck_contract_ready": bool(summary.get("cleanup_postcheck_contract_ready") is True),
        "cleanup_postcheck_row_count": int(summary.get("cleanup_postcheck_row_count") or 0),
        "cleanup_postcheck_blocked_row_count": int(summary.get("cleanup_postcheck_blocked_row_count") or 0),
        "cleanup_postcheck_global_refresh_command_count": int(summary.get("cleanup_postcheck_global_refresh_command_count") or 0),
        "ligand_heavy_cleanup_preflight_ready": bool(summary.get("ligand_heavy_cleanup_preflight_ready") is True),
        "casp17_transition_surface_ready": bool(summary.get("casp17_transition_surface_ready") is True),
        "cleanup_execution_approved": bool(summary.get("cleanup_execution_approved") is True),
        "cleanup_reclaim_size_gb": float(summary.get("cleanup_reclaim_size_gb") or 0.0),
        "release_allowed": bool(summary.get("release_allowed") is True),
        "lanes": rows,
        "blockers": blockers,
        "approval_required": approval_required,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "cameo_submission_executed": False,
        "casp_submission_executed": False,
        "cleanup_executed": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/architecture-validation")
async def get_product_architecture_validation() -> dict[str, Any]:
    packet = _read_json_object(ARCHITECTURE_VALIDATION_REPORT_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    warnings = packet.get("overclaim_warnings") if isinstance(packet.get("overclaim_warnings"), list) else []
    external = _summary(_read_json_object(COMPETITION_EXTERNAL_OPERATOR_TRACK_ARTIFACT))
    if not summary:
        return {
            "status": "missing_architecture_validation_package_report",
            "artifact_path": str(ARCHITECTURE_VALIDATION_REPORT_ARTIFACT),
            "architecture_validation_all_packages_complete": False,
            "package_a_complete": False,
            "package_b_complete": False,
            "package_c_complete": False,
            "evidence_depth_tier": "accounting_only",
            "overclaim_warning_count": 0,
            "execution_enabled": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product architecture-validation endpoint only; the local architecture validation report is missing. "
                "It does not run benchmarks, promote claims, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(ARCHITECTURE_VALIDATION_REPORT_ARTIFACT),
        "architecture_validation_all_packages_complete": bool(
            summary.get("status") == "architecture_validation_all_packages_complete"
        ),
        "package_a_complete": bool(summary.get("package_a_complete") is True),
        "package_b_complete": bool(summary.get("package_b_complete") is True),
        "package_c_complete": bool(summary.get("package_c_complete") is True),
        "open_required_test_ids": list(summary.get("open_required_test_ids") or []),
        "overclaim_open_test_ids": list(summary.get("overclaim_open_test_ids") or []),
        "evidence_depth_tier": summary.get("evidence_depth_tier", "accounting_only"),
        "overclaim_warning_count": int(summary.get("overclaim_warning_count") or 0),
        "overclaim_hard_warning_count": int(summary.get("overclaim_hard_warning_count") or 0),
        "competition_external_operator_track_status": external.get("status", ""),
        "competition_external_blocked_track_count": int(external.get("blocked_track_count") or 0),
        "rows": rows,
        "overclaim_warnings": warnings,
        "execution_enabled": False,
        "claim_promotion_allowed": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/service-boundary")
async def get_product_service_boundary() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_SERVICE_BOUNDARY_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_product_service_boundary_contract",
            "artifact_path": str(PRODUCT_SERVICE_BOUNDARY_ARTIFACT),
            "service_boundary_ready": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "license_file_written": False,
            "bundle_assembled": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product service-boundary endpoint only; the local service-boundary contract is missing or invalid. "
                "It does not run docking, write licenses, assemble bundles, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_SERVICE_BOUNDARY_ARTIFACT),
        "service_boundary_ready": bool(summary.get("service_boundary_ready") is True),
        "check_count": int(summary.get("check_count") or 0),
        "pass_count": int(summary.get("pass_count") or 0),
        "blocker_count": int(summary.get("blocker_count") or 0),
        "api_route_count": int(summary.get("api_route_count") or 0),
        "expected_api_route_count": int(summary.get("expected_api_route_count") or 0),
        "cli_command_count": int(summary.get("cli_command_count") or 0),
        "expected_cli_command_count": int(summary.get("expected_cli_command_count") or 0),
        "artifact_registry_mismatch_count": int(summary.get("artifact_registry_mismatch_count") or 0),
        "console_script_ready": bool(summary.get("console_script_ready") is True),
        "checks": rows,
        "blockers": blockers,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "license_file_written": False,
        "bundle_assembled": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/api-contract")
async def get_product_api_contract() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_API_CONTRACT_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_product_api_contract",
            "artifact_path": str(PRODUCT_API_CONTRACT_ARTIFACT),
            "api_contract_ready": False,
            "check_count": 0,
            "blocker_count": 1,
            "server_started": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "license_file_written": False,
            "bundle_assembled": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product API contract endpoint only; the local API contract artifact is missing or invalid. "
                "It does not start a server, run docking, write licenses, assemble bundles, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_API_CONTRACT_ARTIFACT),
        "api_contract_ready": bool(summary.get("api_contract_ready") is True),
        "check_count": int(summary.get("check_count") or 0),
        "pass_count": int(summary.get("pass_count") or 0),
        "blocker_count": int(summary.get("blocker_count") or 0),
        "expected_route_count": int(summary.get("expected_route_count") or 0),
        "missing_route_count": int(summary.get("missing_route_count") or 0),
        "request_model_count": int(summary.get("request_model_count") or 0),
        "missing_request_model_field_count": int(summary.get("missing_request_model_field_count") or 0),
        "docking_response_missing_key_count": int(summary.get("docking_response_missing_key_count") or 0),
        "status_response_missing_key_count": int(summary.get("status_response_missing_key_count") or 0),
        "checks": rows,
        "blockers": blockers,
        "server_started": False,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "license_file_written": False,
        "bundle_assembled": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/operational-quality")
async def get_product_operational_quality() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_OPERATIONAL_QUALITY_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_product_operational_quality_contract",
            "artifact_path": str(PRODUCT_OPERATIONAL_QUALITY_ARTIFACT),
            "operational_quality_ready": False,
            "blocker_count": 1,
            "production_ai_correction_fail_closed_ready": False,
            "production_ai_shadow_abstention_ready": False,
            "production_ai_guarded_active_ready": False,
            "sample_production_ai_inference_subject_active": False,
            "sample_production_ai_correction_applied": False,
            "sample_production_ai_abstention_enforced": False,
            "sample_production_ai_default_residual_mode": "",
            "sample_production_ai_promotion_allowed": False,
            "sample_production_ai_customer_facing_auto_correction_allowed": False,
            "sample_production_ai_customer_facing_score_mutation_allowed": False,
            "sample_production_ai_customer_facing_ranking_mutation_allowed": False,
            "sample_production_ai_trained_checkpoint_count": 0,
            "sample_production_ai_selected_sidecar_ready": False,
            "sample_production_ai_selected_sidecar_missing_output_fields": [],
            "checks": [],
            "blockers": [],
            "input_payload_persisted": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "license_file_written": False,
            "bundle_assembled": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product operational-quality endpoint only; the local operational-quality artifact is missing or invalid. "
                "It does not run docking, persist jobs, emit scientific results, upload data, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_OPERATIONAL_QUALITY_ARTIFACT),
        "operational_quality_ready": bool(summary.get("operational_quality_ready") is True),
        "check_count": int(summary.get("check_count") or 0),
        "pass_count": int(summary.get("pass_count") or 0),
        "blocker_count": int(summary.get("blocker_count") or 0),
        "fail_closed_docking_intake_ready": bool(summary.get("fail_closed_docking_intake_ready") is True),
        "production_ai_correction_fail_closed_ready": bool(
            summary.get("production_ai_correction_fail_closed_ready") is True
        ),
        "production_ai_shadow_abstention_ready": bool(summary.get("production_ai_shadow_abstention_ready") is True),
        "production_ai_guarded_active_ready": bool(summary.get("production_ai_guarded_active_ready") is True),
        "sample_production_ai_inference_subject_active": bool(
            summary.get("sample_production_ai_inference_subject_active") is True
        ),
        "sample_production_ai_correction_applied": bool(summary.get("sample_production_ai_correction_applied") is True),
        "sample_production_ai_abstention_enforced": bool(
            summary.get("sample_production_ai_abstention_enforced") is True
        ),
        "sample_production_ai_default_residual_mode": summary.get("sample_production_ai_default_residual_mode", ""),
        "sample_production_ai_promotion_allowed": bool(summary.get("sample_production_ai_promotion_allowed") is True),
        "sample_production_ai_customer_facing_auto_correction_allowed": bool(
            summary.get("sample_production_ai_customer_facing_auto_correction_allowed") is True
        ),
        "sample_production_ai_customer_facing_score_mutation_allowed": bool(
            summary.get("sample_production_ai_customer_facing_score_mutation_allowed") is True
        ),
        "sample_production_ai_customer_facing_ranking_mutation_allowed": bool(
            summary.get("sample_production_ai_customer_facing_ranking_mutation_allowed") is True
        ),
        "sample_production_ai_trained_checkpoint_count": int(
            summary.get("sample_production_ai_trained_checkpoint_count") or 0
        ),
        "sample_production_ai_selected_sidecar_ready": bool(
            summary.get("sample_production_ai_selected_sidecar_ready") is True
        ),
        "sample_production_ai_selected_sidecar_missing_output_fields": list(
            summary.get("sample_production_ai_selected_sidecar_missing_output_fields") or []
        ),
        "ledger_payload_privacy_ready": bool(summary.get("ledger_payload_privacy_ready") is True),
        "request_traceability_ready": bool(summary.get("request_traceability_ready") is True),
        "scope_limit_enforcement_ready": bool(summary.get("scope_limit_enforcement_ready") is True),
        "heavy_artifact_policy_ready": bool(summary.get("heavy_artifact_policy_ready") is True),
        "input_payload_persisted": bool(summary.get("input_payload_persisted") is True),
        "allowed_scope_families": summary.get("allowed_scope_families", []),
        "max_p0_ligand_count": int(summary.get("max_p0_ligand_count") or 0),
        "sample_request_sha256": summary.get("sample_request_sha256", ""),
        "checks": rows,
        "blockers": blockers,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "license_file_written": False,
        "bundle_assembled": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/security-deployment-contract")
async def get_product_security_deployment_contract() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_SECURITY_DEPLOYMENT_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_product_security_deployment_contract",
            "artifact_path": str(PRODUCT_SECURITY_DEPLOYMENT_ARTIFACT),
            "security_deployment_ready": False,
            "check_count": 0,
            "pass_count": 0,
            "blocker_count": 1,
            "auth_ready": False,
            "tenant_isolation_ready": False,
            "rate_limit_ready": False,
            "tenant_quota_ready": False,
            "payload_limit_ready": False,
            "path_allowlist_ready": False,
            "audit_log_ready": False,
            "audit_retention_ready": False,
            "blocked_request_audit_ready": False,
            "security_headers_ready": False,
            "fail_closed_block_response_ready": False,
            "audit_redaction_ready": False,
            "hosted_external_exposure_guard_ready": False,
            "hosted_external_exposure_allowed": False,
            "hosted_exposure_approval_token_required": "APPROVE_HOSTED_PRODUCT_API_EXPOSURE",
            "hosted_secret_injection_ready": False,
            "tls_termination_operator_verified": False,
            "hosted_secret_injection_operator_verified": False,
            "hosted_tls_termination_operator_verified": False,
            "hosted_deployment_contract_ready": False,
            "hosted_deployment_currently_satisfied": False,
            "hosted_deployment_blocked_stage_count": 0,
            "hosted_deployment_blocked_stage_ids": [],
            "hosted_deployment_next_stage_id": "",
            "hosted_deployment_next_stage_required": "",
            "secret_rotation_contract_ready": False,
            "backup_dr_contract_ready": False,
            "pager_alert_contract_ready": False,
            "middleware_registered": False,
            "sbom_ready": False,
            "container_image_ready": False,
            "metrics_endpoint_ready": False,
            "metrics_secret_free_ready": False,
            "rollback_ready": False,
            "security_policy_ready": False,
            "sbom_rows": [],
            "checks": [],
            "blockers": [],
            "next_required_step": "Run python3 tools/build_product_security_deployment_contract.py.",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product security-deployment-contract endpoint only; the local deployment contract artifact is missing. "
                "It does not start servers, expose APIs, inject secrets, build containers, deploy, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status", ""),
        "artifact_path": str(PRODUCT_SECURITY_DEPLOYMENT_ARTIFACT),
        "security_deployment_ready": bool(summary.get("security_deployment_ready") is True),
        "check_count": int(summary.get("check_count") or 0),
        "pass_count": int(summary.get("pass_count") or 0),
        "blocker_count": int(summary.get("blocker_count") or 0),
        "auth_ready": bool(summary.get("auth_ready") is True),
        "tenant_isolation_ready": bool(summary.get("tenant_isolation_ready") is True),
        "rate_limit_ready": bool(summary.get("rate_limit_ready") is True),
        "tenant_quota_ready": bool(summary.get("tenant_quota_ready") is True),
        "payload_limit_ready": bool(summary.get("payload_limit_ready") is True),
        "path_allowlist_ready": bool(summary.get("path_allowlist_ready") is True),
        "audit_log_ready": bool(summary.get("audit_log_ready") is True),
        "audit_retention_ready": bool(summary.get("audit_retention_ready") is True),
        "blocked_request_audit_ready": bool(summary.get("blocked_request_audit_ready") is True),
        "security_headers_ready": bool(summary.get("security_headers_ready") is True),
        "fail_closed_block_response_ready": bool(summary.get("fail_closed_block_response_ready") is True),
        "audit_redaction_ready": bool(summary.get("audit_redaction_ready") is True),
        "hosted_external_exposure_guard_ready": bool(
            summary.get("hosted_external_exposure_guard_ready") is True
        ),
        "hosted_external_exposure_allowed": bool(summary.get("hosted_external_exposure_allowed") is True),
        "hosted_exposure_approval_token_required": summary.get(
            "hosted_exposure_approval_token_required", ""
        ),
        "hosted_secret_injection_ready": bool(summary.get("hosted_secret_injection_ready") is True),
        "tls_termination_operator_verified": bool(summary.get("tls_termination_operator_verified") is True),
        "hosted_secret_injection_operator_verified": bool(
            summary.get("hosted_secret_injection_operator_verified") is True
        ),
        "hosted_tls_termination_operator_verified": bool(
            summary.get("hosted_tls_termination_operator_verified") is True
        ),
        "hosted_deployment_contract_ready": bool(summary.get("hosted_deployment_contract_ready") is True),
        "hosted_deployment_currently_satisfied": bool(
            summary.get("hosted_deployment_currently_satisfied") is True
        ),
        "hosted_deployment_blocked_stage_count": int(
            summary.get("hosted_deployment_blocked_stage_count") or 0
        ),
        "hosted_deployment_blocked_stage_ids": list(
            summary.get("hosted_deployment_blocked_stage_ids") or []
        ),
        "hosted_deployment_next_stage_id": summary.get("hosted_deployment_next_stage_id", ""),
        "hosted_deployment_next_stage_required": summary.get(
            "hosted_deployment_next_stage_required", ""
        ),
        "secret_rotation_contract_ready": bool(
            summary.get("secret_rotation_contract_ready") is True
        ),
        "backup_dr_contract_ready": bool(summary.get("backup_dr_contract_ready") is True),
        "pager_alert_contract_ready": bool(summary.get("pager_alert_contract_ready") is True),
        "middleware_registered": bool(summary.get("middleware_registered") is True),
        "sbom_ready": bool(summary.get("sbom_ready") is True),
        "container_image_ready": bool(summary.get("container_image_ready") is True),
        "metrics_endpoint_ready": bool(summary.get("metrics_endpoint_ready") is True),
        "metrics_secret_free_ready": bool(summary.get("metrics_secret_free_ready") is True),
        "rollback_ready": bool(summary.get("rollback_ready") is True),
        "security_policy_ready": bool(summary.get("security_policy_ready") is True),
        "sbom_rows": list(summary.get("sbom_rows") or []),
        "checks": rows,
        "blockers": blockers,
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/external-metrics")
async def get_product_external_metrics() -> dict[str, Any]:
    packet = _read_json_object(EXTERNAL_METRIC_SCORECARD_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_external_metric_scorecard",
            "artifact_path": str(EXTERNAL_METRIC_SCORECARD_ARTIFACT),
            "claim_scope": "",
            "claim_promotion_allowed": False,
            "row_count": 0,
            "blocked_row_count": 0,
            "evaluated_row_count": 0,
            "rows": [],
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product external-metrics endpoint only; the local external metric scorecard artifact is missing. "
                "It does not compute DockQ/LDDT/MolProbity or mutate external state."
            ),
        }
    return {
        "status": summary.get("status", ""),
        "artifact_path": str(EXTERNAL_METRIC_SCORECARD_ARTIFACT),
        "claim_scope": summary.get("claim_scope", ""),
        "claim_promotion_allowed": bool(summary.get("claim_promotion_allowed") is True),
        "row_count": int(summary.get("row_count") or len(rows)),
        "blocked_row_count": int(summary.get("blocked_row_count") or 0),
        "evaluated_row_count": int(summary.get("evaluated_row_count") or 0),
        "topology_fidelity_required": summary.get("topology_fidelity_required", ""),
        "rows": rows,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/public-benchmark")
async def get_product_public_benchmark() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_PUBLIC_BENCHMARK_WORK_ORDER_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_product_public_benchmark_work_order",
            "artifact_path": str(PRODUCT_PUBLIC_BENCHMARK_WORK_ORDER_ARTIFACT),
            "public_benchmark_validation_ready": False,
            "open_suite_count": 0,
            "materialization_required_suite_count": 0,
            "scorecard_required_suite_count": 0,
            "continuous_validation_command_count": 0,
            "continuous_validation_command": "",
            "suite_run_command_count": 0,
            "suite_materialization_run_command_count": 0,
            "suite_scorecard_command_count": 0,
            "suite_result_provenance_command_count": 0,
            "suite_result_provenance_present_count": 0,
            "suite_threshold_count": 0,
            "suite_blocker_count": 0,
            "suite_materialization_manifest_count": 0,
            "suite_scorecard_row_csv_count": 0,
            "suite_required_output_count": 0,
            "suite_no_external_dependency_count": 0,
            "local_artifact_preflight_ready_suite_count": 0,
            "local_artifact_preflight_blocked_suite_count": 0,
            "missing_local_input_artifact_count": 0,
            "missing_local_output_artifact_count": 0,
            "missing_local_input_artifacts": [],
            "missing_local_output_artifacts": [],
            "requires_24h_server": False,
            "requires_competition_season": False,
            "requires_paid_vps": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product public-benchmark endpoint only; the local public benchmark work-order artifact is missing or invalid. "
                "It does not download datasets, run docking, compute metrics, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_PUBLIC_BENCHMARK_WORK_ORDER_ARTIFACT),
        "source_public_benchmark_status": summary.get("source_public_benchmark_status", ""),
        "source_public_benchmark_json": summary.get("source_public_benchmark_json", ""),
        "public_benchmark_validation_ready": bool(summary.get("public_benchmark_validation_ready") is True),
        "suite_count": int(summary.get("suite_count") or 0),
        "open_suite_count": int(summary.get("open_suite_count") or 0),
        "materialization_required_suite_count": int(summary.get("materialization_required_suite_count") or 0),
        "scorecard_required_suite_count": int(summary.get("scorecard_required_suite_count") or 0),
        "continuous_validation_command_count": int(summary.get("continuous_validation_command_count") or 0),
        "continuous_validation_command": summary.get("continuous_validation_command", ""),
        "scorecard_intake_sync_command": summary.get("scorecard_intake_sync_command", ""),
        "scorecard_row_csvs": list(summary.get("scorecard_row_csvs") or []),
        "suite_run_command_count": int(summary.get("suite_run_command_count") or 0),
        "suite_materialization_run_command_count": int(summary.get("suite_materialization_run_command_count") or 0),
        "suite_scorecard_command_count": int(summary.get("suite_scorecard_command_count") or 0),
        "suite_result_provenance_command_count": int(summary.get("suite_result_provenance_command_count") or 0),
        "suite_result_provenance_present_count": int(summary.get("suite_result_provenance_present_count") or 0),
        "suite_threshold_count": int(summary.get("suite_threshold_count") or 0),
        "suite_blocker_count": int(summary.get("suite_blocker_count") or 0),
        "suite_materialization_manifest_count": int(summary.get("suite_materialization_manifest_count") or 0),
        "suite_scorecard_row_csv_count": int(summary.get("suite_scorecard_row_csv_count") or 0),
        "suite_required_output_count": int(summary.get("suite_required_output_count") or 0),
        "suite_no_external_dependency_count": int(summary.get("suite_no_external_dependency_count") or 0),
        "local_artifact_preflight_ready_suite_count": int(
            summary.get("local_artifact_preflight_ready_suite_count") or 0
        ),
        "local_artifact_preflight_blocked_suite_count": int(
            summary.get("local_artifact_preflight_blocked_suite_count") or 0
        ),
        "missing_local_input_artifact_count": int(summary.get("missing_local_input_artifact_count") or 0),
        "missing_local_output_artifact_count": int(summary.get("missing_local_output_artifact_count") or 0),
        "missing_local_input_artifacts": list(summary.get("missing_local_input_artifacts") or []),
        "missing_local_output_artifacts": list(summary.get("missing_local_output_artifacts") or []),
        "requires_24h_server": bool(summary.get("requires_24h_server") is True),
        "requires_competition_season": bool(summary.get("requires_competition_season") is True),
        "requires_paid_vps": bool(summary.get("requires_paid_vps") is True),
        "requires_institution_registration": bool(summary.get("requires_institution_registration") is True),
        "download_executed": bool(summary.get("download_executed") is True),
        "suites": rows,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/trajectory-sla-contract")
async def get_product_trajectory_sla_contract() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_TRAJECTORY_SLA_CONTRACT_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_product_trajectory_sla_contract",
            "artifact_path": str(PRODUCT_TRAJECTORY_SLA_CONTRACT_ARTIFACT),
            "production_trajectory_sla_ready": False,
            "sla_claim_tier": "",
            "restricted_family_sla_allowed": False,
            "broad_platform_sla_allowed": False,
            "candidate_artifact_count": 0,
            "ready_run_count": 0,
            "qualified_ready_run_count": 0,
            "required_families": [],
            "ready_families": [],
            "qualified_ready_families": [],
            "missing_families": [],
            "missing_qualified_families": [],
            "minimum_ready_run_count": 0,
            "minimum_ready_rows_per_family": 0,
            "family_sla_matrix": [],
            "current_rocm_baseline_artifact": "",
            "current_rocm_baseline_ready": False,
            "current_rocm_baseline_family": "",
            "current_rocm_baseline_target_id": "",
            "current_rocm_baseline_production_trajectory_profile_enabled": False,
            "current_rocm_baseline_warning_count": 0,
            "current_rocm_baseline_claim_scope": "",
            "current_rocm_baseline_supports_restricted_family_sla": False,
            "current_rocm_baseline_supports_broad_platform_sla": False,
            "allowed_sla_claims": [],
            "blocked_sla_claims": ["missing_product_trajectory_sla_contract"],
            "customer_sla_disclosure_card": {},
            "customer_sla_disclosure_ready": False,
            "general_platform_sla_allowed": False,
            "restricted_sla_backed_by_historical_profile_artifacts": False,
            "rocm_baseline_profile_gap_acknowledged": False,
            "single_baseline_only": False,
            "trajectory_sla_rows": [],
            "next_required_step": "Run python3 tools/build_product_trajectory_sla_contract.py.",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "benchmark_executed": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product trajectory-SLA-contract endpoint only; the local trajectory SLA artifact is missing. "
                "It does not launch docking, rerun trajectories, execute benchmarks, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status", ""),
        "artifact_path": str(PRODUCT_TRAJECTORY_SLA_CONTRACT_ARTIFACT),
        "production_trajectory_sla_ready": bool(summary.get("production_trajectory_sla_ready") is True),
        "sla_claim_tier": summary.get("sla_claim_tier", ""),
        "restricted_family_sla_allowed": bool(summary.get("restricted_family_sla_allowed") is True),
        "broad_platform_sla_allowed": bool(summary.get("broad_platform_sla_allowed") is True),
        "candidate_artifact_count": int(summary.get("candidate_artifact_count") or 0),
        "ready_run_count": int(summary.get("ready_run_count") or 0),
        "qualified_ready_run_count": int(summary.get("qualified_ready_run_count") or 0),
        "required_families": list(summary.get("required_families") or []),
        "ready_families": list(summary.get("ready_families") or []),
        "qualified_ready_families": list(summary.get("qualified_ready_families") or []),
        "missing_families": list(summary.get("missing_families") or []),
        "missing_qualified_families": list(summary.get("missing_qualified_families") or []),
        "minimum_ready_run_count": int(summary.get("minimum_ready_run_count") or 0),
        "minimum_ready_rows_per_family": int(summary.get("minimum_ready_rows_per_family") or 0),
        "family_sla_matrix": list(summary.get("family_sla_matrix") or []),
        "current_rocm_baseline_artifact": summary.get("current_rocm_baseline_artifact", ""),
        "current_rocm_baseline_ready": bool(summary.get("current_rocm_baseline_ready") is True),
        "current_rocm_baseline_family": summary.get("current_rocm_baseline_family", ""),
        "current_rocm_baseline_target_id": summary.get("current_rocm_baseline_target_id", ""),
        "current_rocm_baseline_production_trajectory_profile_enabled": bool(
            summary.get("current_rocm_baseline_production_trajectory_profile_enabled") is True
        ),
        "current_rocm_baseline_warning_count": int(summary.get("current_rocm_baseline_warning_count") or 0),
        "current_rocm_baseline_claim_scope": summary.get("current_rocm_baseline_claim_scope", ""),
        "current_rocm_baseline_supports_restricted_family_sla": bool(
            summary.get("current_rocm_baseline_supports_restricted_family_sla") is True
        ),
        "current_rocm_baseline_supports_broad_platform_sla": bool(
            summary.get("current_rocm_baseline_supports_broad_platform_sla") is True
        ),
        "allowed_sla_claims": list(summary.get("allowed_sla_claims") or []),
        "blocked_sla_claims": list(summary.get("blocked_sla_claims") or []),
        "customer_sla_disclosure_card": summary.get("customer_sla_disclosure_card")
        if isinstance(summary.get("customer_sla_disclosure_card"), dict)
        else {},
        "customer_sla_disclosure_ready": bool(summary.get("customer_sla_disclosure_ready") is True),
        "general_platform_sla_allowed": bool(summary.get("general_platform_sla_allowed") is True),
        "restricted_sla_backed_by_historical_profile_artifacts": bool(
            summary.get("restricted_sla_backed_by_historical_profile_artifacts") is True
        ),
        "rocm_baseline_profile_gap_acknowledged": bool(
            summary.get("rocm_baseline_profile_gap_acknowledged") is True
        ),
        "single_baseline_only": bool(summary.get("single_baseline_only") is True),
        "trajectory_sla_rows": rows,
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "benchmark_executed": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


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


@router.get("/cameo-live-validation")
async def get_product_cameo_live_validation() -> dict[str, Any]:
    packet = _read_json_object(CAMEO_VALIDATION_OPERATIONS_ARTIFACT)
    official_packet = _read_json_object(CAMEO_OFFICIAL_RESULTS_ARTIFACT)
    registration_packet = _read_json_object(CAMEO_PUBLIC_REGISTRATION_ARTIFACT)
    summary = _summary(packet)
    official = _summary(official_packet)
    registration = _summary(registration_packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_cameo_validation_operations_dossier",
            "artifact_path": str(CAMEO_VALIDATION_OPERATIONS_ARTIFACT),
            "validation_ready": False,
            "official_result_required": True,
            "official_results_intake_ready": False,
            "official_results_intake_status": "",
            "official_results_operator_template_csv": str(CAMEO_OFFICIAL_RESULTS_TEMPLATE),
            "official_results_operator_intake_csv": str(CAMEO_OFFICIAL_RESULTS_INTAKE),
            "official_results_blocker_codes": [],
            "public_registration_allowed": False,
            "registration_gate_status": "",
            "registration_operator_template_csv": str(CAMEO_PUBLIC_REGISTRATION_TEMPLATE),
            "registration_operator_approval_csv": str(CAMEO_PUBLIC_REGISTRATION_INTAKE),
            "approval_tokens_required": [],
            "next_required_step": "",
            "server_started": False,
            "outbound_email_enabled": False,
            "server_registration_mutated": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product CAMEO live-validation endpoint only; the local CAMEO validation operations dossier is missing "
                "or invalid. It does not start a server, register a CAMEO server, send email, fetch official results, "
                "submit predictions, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(CAMEO_VALIDATION_OPERATIONS_ARTIFACT),
        "validation_ready": bool(summary.get("validation_ready") is True),
        "validation_readiness_status": summary.get("validation_readiness_status", ""),
        "official_result_required": bool(summary.get("official_result_required") is True),
        "official_results_intake_ready": bool(summary.get("official_results_intake_ready") is True),
        "official_results_intake_status": summary.get("official_results_intake_status", ""),
        "official_results_intake_blocker_count": int(summary.get("official_results_intake_blocker_count") or 0),
        "official_results_gate_status": official.get("status", ""),
        "official_results_result_row_count": int(official.get("result_row_count") or 0),
        "official_results_accepted_count": int(official.get("accepted_official_result_count") or 0),
        "official_results_rejected_count": int(official.get("rejected_official_result_count") or 0),
        "official_results_blocker_codes": list(official.get("blocker_codes") or []),
        "official_results_operator_template_csv": official.get("operator_template_csv") or str(CAMEO_OFFICIAL_RESULTS_TEMPLATE),
        "official_results_operator_intake_csv": official.get("operator_intake_csv") or str(CAMEO_OFFICIAL_RESULTS_INTAKE),
        "official_results_required_columns": list(official.get("required_columns") or []),
        "official_results_missing_required_columns": list(official.get("missing_required_columns") or []),
        "official_results_metric_columns": list(official.get("official_metric_columns") or []),
        "official_model1_result_ready": bool(summary.get("official_model1_result_ready") is True),
        "official_cameo_results_used": bool(summary.get("official_cameo_results_used") is True),
        "official_results_pending_honest": bool(summary.get("official_results_pending_honest") is True),
        "receiver_smoke_status": summary.get("receiver_smoke_status", ""),
        "api_dependency_status": summary.get("api_dependency_status", ""),
        "evidence_integrity_ready": bool(summary.get("evidence_integrity_ready") is True),
        "evidence_integrity_status": summary.get("evidence_integrity_status", ""),
        "public_registration_allowed": bool(summary.get("public_registration_allowed") is True),
        "registration_gate_status": registration.get("status", ""),
        "registration_authorized_for_review": bool(registration.get("authorized_for_registration_review") is True),
        "registration_operator_template_csv": registration.get("operator_template_csv")
        or str(CAMEO_PUBLIC_REGISTRATION_TEMPLATE),
        "registration_operator_approval_csv": registration.get("operator_approval_csv")
        or str(CAMEO_PUBLIC_REGISTRATION_INTAKE),
        "registration_blocker_count": int(registration.get("blocker_count") or 0),
        "registration_blockers": list(registration.get("blockers") or []),
        "registration_approval_token_required": summary.get("registration_approval_token_required", ""),
        "outbound_email_approval_token_required": summary.get("outbound_email_approval_token_required", ""),
        "approval_token_count": int(summary.get("approval_token_count") or 0),
        "approval_tokens_required": list(summary.get("approval_tokens_required") or []),
        "next_required_step": summary.get("next_required_step", ""),
        "stages": rows,
        "server_started": bool(summary.get("server_started") is True),
        "outbound_email_enabled": bool(summary.get("outbound_email_enabled") is True),
        "server_registration_mutated": bool(summary.get("server_registration_mutated") is True),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": bool(summary.get("external_state_mutated") is True),
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/operations")
async def get_product_operations() -> dict[str, Any]:
    release_packet = _read_json_object(PRODUCT_RELEASE_OPERATIONS_ARTIFACT)
    approval_packet = _read_json_object(PRODUCT_EXECUTION_APPROVAL_ARTIFACT)
    operational_quality_packet = _read_json_object(PRODUCT_OPERATIONAL_QUALITY_ARTIFACT)
    license_packet = _read_json_object(PRODUCT_LICENSE_DECISION_ARTIFACT)
    license_options_packet = _read_json_object(PRODUCT_LICENSE_DECISION_PACKET_ARTIFACT)
    license_work_order_packet = _read_json_object(PRODUCT_LICENSE_FILE_WORK_ORDER_ARTIFACT)
    commercial_packet = _read_json_object(PRODUCT_COMMERCIAL_INDEPENDENCE_ARTIFACT)
    release = _summary(release_packet)
    release_rows = release_packet.get("rows") if isinstance(release_packet.get("rows"), list) else []
    approval = _summary(approval_packet)
    operational_quality = _summary(operational_quality_packet)
    license_decision = _summary(license_packet)
    license_options = _summary(license_options_packet)
    license_work_order = _summary(license_work_order_packet)
    commercial = _summary(commercial_packet)
    if not release:
        return {
            "status": "missing_product_release_operations_dossier",
            "artifact_path": str(PRODUCT_RELEASE_OPERATIONS_ARTIFACT),
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product operations endpoint only; the local product release operations artifact is missing or invalid. "
                "It does not run docking, approve execution, write license files, or mutate external state."
            ),
        }
    return {
        "status": release.get("status"),
        "artifact_path": str(PRODUCT_RELEASE_OPERATIONS_ARTIFACT),
        "target_id": release.get("target_id", ""),
        "family": release.get("family", ""),
        "capability_surface_ready": bool(release.get("capability_surface_ready") is True),
        "architecture_contract_ready": bool(release.get("architecture_contract_ready") is True),
        "architecture_local_surface_ready": bool(release.get("architecture_local_surface_ready") is True),
        "architecture_release_ready": bool(release.get("architecture_release_ready") is True),
        "architecture_blocked_lane_count": int(release.get("architecture_blocked_lane_count") or 0),
        "architecture_approval_required_lane_count": int(release.get("architecture_approval_required_lane_count") or 0),
        "operational_quality_ready": bool(
            release.get("operational_quality_ready") is True
            or operational_quality.get("operational_quality_ready") is True
        ),
        "source_operational_quality_status": release.get("source_operational_quality_status")
        or operational_quality.get("status", ""),
        "operational_quality_blocker_count": int(
            release.get("operational_quality_blocker_count")
            if release.get("operational_quality_blocker_count") is not None
            else operational_quality.get("blocker_count") or 0
        ),
        "product_service_boundary_ready": bool(release.get("product_service_boundary_ready") is True),
        "product_api_contract_ready": bool(release.get("product_api_contract_ready") is True),
        "public_benchmark_suite_materialization_manifest_count": int(
            release.get("public_benchmark_suite_materialization_manifest_count") or 0
        ),
        "public_benchmark_suite_scorecard_row_csv_count": int(
            release.get("public_benchmark_suite_scorecard_row_csv_count") or 0
        ),
        "public_benchmark_suite_threshold_count": int(release.get("public_benchmark_suite_threshold_count") or 0),
        "public_benchmark_suite_blocker_count": int(release.get("public_benchmark_suite_blocker_count") or 0),
        "public_benchmark_suite_run_command_count": int(release.get("public_benchmark_suite_run_command_count") or 0),
        "public_benchmark_suite_materialization_run_command_count": int(
            release.get("public_benchmark_suite_materialization_run_command_count") or 0
        ),
        "public_benchmark_suite_result_provenance_command_count": int(
            release.get("public_benchmark_suite_result_provenance_command_count") or 0
        ),
        "public_benchmark_suite_result_provenance_present_count": int(
            release.get("public_benchmark_suite_result_provenance_present_count") or 0
        ),
        "public_benchmark_suite_no_external_dependency_count": int(
            release.get("public_benchmark_suite_no_external_dependency_count") or 0
        ),
        "public_benchmark_work_order_status": release.get("public_benchmark_work_order_status", ""),
        "public_benchmark_work_order_artifact": release.get("public_benchmark_work_order_artifact", ""),
        "public_benchmark_work_order_open_suite_count": int(
            release.get("public_benchmark_work_order_open_suite_count") or 0
        ),
        "public_benchmark_work_order_materialization_required_suite_count": int(
            release.get("public_benchmark_work_order_materialization_required_suite_count") or 0
        ),
        "public_benchmark_work_order_scorecard_required_suite_count": int(
            release.get("public_benchmark_work_order_scorecard_required_suite_count") or 0
        ),
        "public_benchmark_work_order_continuous_validation_command_count": int(
            release.get("public_benchmark_work_order_continuous_validation_command_count") or 0
        ),
        "public_benchmark_work_order_continuous_validation_command": release.get(
            "public_benchmark_work_order_continuous_validation_command", ""
        ),
        "public_benchmark_work_order_suite_run_command_count": int(
            release.get("public_benchmark_work_order_suite_run_command_count") or 0
        ),
        "public_benchmark_work_order_suite_result_provenance_command_count": int(
            release.get("public_benchmark_work_order_suite_result_provenance_command_count") or 0
        ),
        "public_benchmark_work_order_suite_result_provenance_present_count": int(
            release.get("public_benchmark_work_order_suite_result_provenance_present_count") or 0
        ),
        "public_benchmark_work_order_suite_threshold_count": int(
            release.get("public_benchmark_work_order_suite_threshold_count") or 0
        ),
        "public_benchmark_work_order_suite_materialization_manifest_count": int(
            release.get("public_benchmark_work_order_suite_materialization_manifest_count") or 0
        ),
        "public_benchmark_work_order_suite_scorecard_row_csv_count": int(
            release.get("public_benchmark_work_order_suite_scorecard_row_csv_count") or 0
        ),
        "public_benchmark_work_order_suite_no_external_dependency_count": int(
            release.get("public_benchmark_work_order_suite_no_external_dependency_count") or 0
        ),
        "public_benchmark_work_order_local_artifact_preflight_ready_suite_count": int(
            release.get("public_benchmark_work_order_local_artifact_preflight_ready_suite_count") or 0
        ),
        "public_benchmark_work_order_local_artifact_preflight_blocked_suite_count": int(
            release.get("public_benchmark_work_order_local_artifact_preflight_blocked_suite_count") or 0
        ),
        "public_benchmark_work_order_missing_local_input_artifact_count": int(
            release.get("public_benchmark_work_order_missing_local_input_artifact_count") or 0
        ),
        "public_benchmark_work_order_missing_local_output_artifact_count": int(
            release.get("public_benchmark_work_order_missing_local_output_artifact_count") or 0
        ),
        "cameo_architecture_validation_ready": bool(release.get("cameo_architecture_validation_ready") is True),
        "cleanup_postcheck_contract_ready": bool(release.get("cleanup_postcheck_contract_ready") is True),
        "cleanup_postcheck_blocked_row_count": int(release.get("cleanup_postcheck_blocked_row_count") or 0),
        "structure_analysis_capability_ready": bool(release.get("structure_analysis_capability_ready") is True),
        "ligand_docking_capability_ready": bool(release.get("ligand_docking_capability_ready") is True),
        "authorized_for_execution": bool(release.get("authorized_for_execution") is True),
        "bundle_contract_ready": bool(release.get("bundle_contract_ready") is True),
        "bundle_assembled": bool(release.get("bundle_assembled") is True),
        "bundle_validation_passed": bool(release.get("bundle_validation_passed") is True),
        "delivery_ready_claim_allowed": bool(release.get("delivery_ready_claim_allowed") is True),
        "pilot_delivery_ready": bool(release.get("pilot_delivery_ready") is True),
        "blocked_stage_count": int(release.get("blocked_stage_count") or 0),
        "approval_required_stage_count": int(release.get("approval_required_stage_count") or 0),
        "approval_token_count": int(release.get("approval_token_count") or 0),
        "approval_tokens_required": list(release.get("approval_tokens_required") or []),
        "stages": release_rows,
        "execution_approval_status": approval.get("status", ""),
        "execution_approval_token_required": approval.get("approval_token_required", "APPROVE_PRODUCT_DOCKING_EXECUTION"),
        "execution_operator_approval_csv_present": bool(approval.get("operator_approval_csv_present") is True),
        "license_decision_status": license_decision.get("status", ""),
        "license_decision_packet_status": license_options.get("status", ""),
        "license_decision_option_count": int(license_options.get("option_count") or 0),
        "license_authorized_for_file_creation_review": bool(license_decision.get("authorized_for_license_file_creation_review") is True),
        "source_license_file_creation_work_order_status": release.get("source_license_file_creation_work_order_status", ""),
        "license_file_creation_work_order_status": release.get("source_license_file_creation_work_order_status")
        or license_work_order.get("status", ""),
        "license_file_creation_review_ready": bool(
            release.get("license_file_creation_review_ready") is True
            or license_work_order.get("license_file_creation_review_ready") is True
        ),
        "license_file_creation_work_order_blocker_count": int(
            release.get("license_file_creation_work_order_blocker_count")
            if release.get("license_file_creation_work_order_blocker_count") is not None
            else license_work_order.get("blocker_count") or 0
        ),
        "license_file_creation_work_order_artifact": release.get("license_file_creation_work_order_artifact")
        or str(PRODUCT_LICENSE_FILE_WORK_ORDER_ARTIFACT),
        "license_operator_template_csv": str(PRODUCT_LICENSE_DECISION_TEMPLATE),
        "license_operator_intake_csv": str(PRODUCT_LICENSE_DECISION_INTAKE),
        "license_required_fields": list(LICENSE_REQUIRED_FIELDS),
        "license_required_decision": DECISION_CREATE_LICENSE,
        "license_approval_token_required": LICENSE_APPROVAL_TOKEN,
        "license_missing_required_fields": license_decision.get("missing_required_fields", []),
        "commercial_independence_status": commercial.get("status", ""),
        "commercial_independent_product_claim_allowed": bool(commercial.get("commercial_independent_product_claim_allowed") is True),
        "license_file_written": False,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": release.get("claim_boundary", ""),
    }


@router.get("/license-decision")
async def get_product_license_decision() -> dict[str, Any]:
    license_packet = _read_json_object(PRODUCT_LICENSE_DECISION_ARTIFACT)
    summary = _summary(license_packet)
    rows = license_packet.get("rows") if isinstance(license_packet.get("rows"), list) else []
    blockers = license_packet.get("blockers") if isinstance(license_packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_product_license_decision_gate",
            "artifact_path": str(PRODUCT_LICENSE_DECISION_ARTIFACT),
            "operator_template_csv": str(PRODUCT_LICENSE_DECISION_TEMPLATE),
            "operator_intake_csv": str(PRODUCT_LICENSE_DECISION_INTAKE),
            "required_fields": list(LICENSE_REQUIRED_FIELDS),
            "required_decision": DECISION_CREATE_LICENSE,
            "approval_token_required": LICENSE_APPROVAL_TOKEN,
            "authorized_for_license_file_creation_review": False,
            "license_file_written": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product license-decision endpoint only; the local license decision artifact is missing or invalid. "
                "It does not choose a license, write a LICENSE file, run docking, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_LICENSE_DECISION_ARTIFACT),
        "operator_template_csv": str(PRODUCT_LICENSE_DECISION_TEMPLATE),
        "operator_intake_csv": str(PRODUCT_LICENSE_DECISION_INTAKE),
        "required_fields": list(LICENSE_REQUIRED_FIELDS),
        "required_decision": DECISION_CREATE_LICENSE,
        "approval_token_required": LICENSE_APPROVAL_TOKEN,
        "authorized_for_license_file_creation_review": bool(summary.get("authorized_for_license_file_creation_review") is True),
        "operator_intake_csv_present": bool(summary.get("operator_intake_csv_present") is True),
        "operator_decision": summary.get("operator_decision", ""),
        "approval_token_valid": bool(summary.get("approval_token_valid") is True),
        "spdx_license_id": summary.get("spdx_license_id", ""),
        "license_text_source": summary.get("license_text_source", ""),
        "copyright_holder": summary.get("copyright_holder", ""),
        "effective_year": summary.get("effective_year", ""),
        "missing_required_field_count": int(summary.get("missing_required_field_count") or 0),
        "missing_required_fields": summary.get("missing_required_fields", []),
        "license_present": bool(summary.get("license_present") is True),
        "commercial_gate_only_license_blocked": bool(summary.get("commercial_gate_only_license_blocked") is True),
        "blocker_count": int(summary.get("blocker_count") or 0),
        "check_count": int(summary.get("check_count") or 0),
        "checks": rows,
        "blockers": blockers,
        "license_file_written": False,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/license-file-work-order")
async def get_product_license_file_work_order() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_LICENSE_FILE_WORK_ORDER_ARTIFACT)
    summary = _summary(packet)
    license_decision_summary = _summary(_read_json_object(PRODUCT_LICENSE_DECISION_ARTIFACT))
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    work_items = packet.get("work_items") if isinstance(packet.get("work_items"), list) else []
    if not summary:
        return {
            "status": "missing_product_license_file_creation_work_order",
            "artifact_path": str(PRODUCT_LICENSE_FILE_WORK_ORDER_ARTIFACT),
            "license_file_creation_review_ready": False,
            "approval_token_required": LICENSE_APPROVAL_TOKEN,
            "target_license_path": "LICENSE",
            "license_review_manifest_ready": False,
            "license_review_manifest": {},
            "license_review_manifest_fingerprint_sha256": "",
            "license_file_written": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product license-file work-order endpoint only; the local LICENSE creation work-order artifact is missing or invalid. "
                "It does not choose a license, write a LICENSE file, run docking, or mutate external state."
            ),
        }
    license_text_source = str(summary.get("license_text_source", "") or "")
    license_present = bool(summary.get("license_present") is True or license_text_source)
    authorized_for_review = bool(
        summary.get("authorized_for_license_file_creation_review") is True
        or license_decision_summary.get("authorized_for_license_file_creation_review") is True
    )
    license_review_manifest = summary.get("license_review_manifest") if isinstance(summary.get("license_review_manifest"), dict) else {}
    fingerprint = str(summary.get("license_review_manifest_fingerprint_sha256", "") or "")
    if not fingerprint and bool(summary.get("license_review_manifest_ready") is True):
        fingerprint_payload = license_review_manifest or {
            "spdx_license_id": summary.get("spdx_license_id", ""),
            "license_text_source": license_text_source,
            "copyright_holder": summary.get("copyright_holder", ""),
            "effective_year": summary.get("effective_year", ""),
        }
        fingerprint = hashlib.sha256(
            json.dumps(fingerprint_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_LICENSE_FILE_WORK_ORDER_ARTIFACT),
        "license_file_creation_review_ready": bool(summary.get("license_file_creation_review_ready") is True),
        "approval_token_required": summary.get("approval_token_required") or LICENSE_APPROVAL_TOKEN,
        "target_license_path": summary.get("target_license_path") or "LICENSE",
        "spdx_license_id": summary.get("spdx_license_id", ""),
        "license_text_source": license_text_source,
        "copyright_holder": summary.get("copyright_holder", ""),
        "effective_year": summary.get("effective_year", ""),
        "license_review_manifest_ready": bool(summary.get("license_review_manifest_ready") is True),
        "license_review_manifest": license_review_manifest,
        "license_review_manifest_fingerprint_sha256": fingerprint,
        "license_decision_gate_status": summary.get("license_decision_gate_status", "")
        or license_decision_summary.get("status", ""),
        "authorized_for_license_file_creation_review": authorized_for_review,
        "commercial_gate_only_license_blocked": bool(summary.get("commercial_gate_only_license_blocked") is True),
        "license_present": license_present,
        "blocker_count": int(summary.get("blocker_count") or 0),
        "check_count": int(summary.get("check_count") or 0),
        "checks": rows,
        "blockers": blockers,
        "work_items": work_items,
        "license_file_written": False,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/license-options")
async def get_product_license_options() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_LICENSE_DECISION_PACKET_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_product_license_decision_packet",
            "artifact_path": str(PRODUCT_LICENSE_DECISION_PACKET_ARTIFACT),
            "option_count": 0,
            "operator_template_csv": str(PRODUCT_LICENSE_DECISION_TEMPLATE),
            "operator_intake_csv": str(PRODUCT_LICENSE_DECISION_INTAKE),
            "required_fields": list(LICENSE_REQUIRED_FIELDS),
            "required_decision": DECISION_CREATE_LICENSE,
            "approval_token_required": LICENSE_APPROVAL_TOKEN,
            "license_file_written": False,
            "legal_advice_provided": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product license-options endpoint only; the local license decision packet is missing or invalid. "
                "It does not choose a license, provide legal advice, write a LICENSE file, run docking, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_LICENSE_DECISION_PACKET_ARTIFACT),
        "option_count": int(summary.get("option_count") or 0),
        "blocker_count": int(summary.get("blocker_count") or 0),
        "commercial_gate_only_license_blocked": bool(summary.get("commercial_gate_only_license_blocked") is True),
        "license_decision_gate_status": summary.get("license_decision_gate_status", ""),
        "license_decision_authorized_for_file_creation_review": bool(
            summary.get("license_decision_authorized_for_file_creation_review") is True
        ),
        "operator_intake_csv_present": bool(summary.get("operator_intake_csv_present") is True),
        "operator_template_csv": summary.get("operator_template_csv") or str(PRODUCT_LICENSE_DECISION_TEMPLATE),
        "operator_intake_csv": summary.get("operator_intake_csv") or str(PRODUCT_LICENSE_DECISION_INTAKE),
        "required_fields": list(summary.get("required_fields") or LICENSE_REQUIRED_FIELDS),
        "required_decision": summary.get("required_decision") or DECISION_CREATE_LICENSE,
        "approval_token_required": summary.get("approval_token_required") or LICENSE_APPROVAL_TOKEN,
        "license_present": bool(summary.get("license_present") is True),
        "license_file_written": False,
        "legal_advice_provided": False,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "options": rows,
        "blockers": blockers,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/commercial-independence")
async def get_product_commercial_independence() -> dict[str, Any]:
    commercial_packet = _read_json_object(PRODUCT_COMMERCIAL_INDEPENDENCE_ARTIFACT)
    license_packet = _read_json_object(PRODUCT_LICENSE_DECISION_ARTIFACT)
    license_options_packet = _read_json_object(PRODUCT_LICENSE_DECISION_PACKET_ARTIFACT)
    license_work_order_packet = _read_json_object(PRODUCT_LICENSE_FILE_WORK_ORDER_ARTIFACT)
    commercial = _summary(commercial_packet)
    license_decision = _summary(license_packet)
    license_options = _summary(license_options_packet)
    license_work_order = _summary(license_work_order_packet)
    rows = commercial_packet.get("rows") if isinstance(commercial_packet.get("rows"), list) else []
    blockers = commercial_packet.get("blockers") if isinstance(commercial_packet.get("blockers"), list) else []
    if not commercial:
        return {
            "status": "missing_product_commercial_independence_gate",
            "artifact_path": str(PRODUCT_COMMERCIAL_INDEPENDENCE_ARTIFACT),
            "commercial_independent_product_claim_allowed": False,
            "restricted_commercial_scope_claim_ready": False,
            "commercial_claim_scope_tier": "missing_product_commercial_independence_gate",
            "commercial_claim_scope_detail": "",
            "allowed_scope_families": [],
            "blocked_claim_scopes": [],
            "general_platform_claim_allowed": False,
            "operator_template_csv": str(PRODUCT_LICENSE_DECISION_TEMPLATE),
            "operator_intake_csv": str(PRODUCT_LICENSE_DECISION_INTAKE),
            "required_fields": list(LICENSE_REQUIRED_FIELDS),
            "required_decision": DECISION_CREATE_LICENSE,
            "approval_token_required": LICENSE_APPROVAL_TOKEN,
            "license_file_written": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product commercial-independence endpoint only; the local commercial-independence artifact is missing or invalid. "
                "It does not choose a license, create license files, run docking, or mutate external state."
            ),
        }
    return {
        "status": commercial.get("status"),
        "artifact_path": str(PRODUCT_COMMERCIAL_INDEPENDENCE_ARTIFACT),
        "commercial_independent_product_claim_allowed": bool(commercial.get("commercial_independent_product_claim_allowed") is True),
        "restricted_commercial_scope_claim_ready": bool(
            commercial.get("restricted_commercial_scope_claim_ready") is True
        ),
        "commercial_claim_scope_tier": commercial.get("commercial_claim_scope_tier", ""),
        "commercial_claim_scope_detail": commercial.get("commercial_claim_scope_detail", ""),
        "allowed_scope_families": list(commercial.get("allowed_scope_families") or []),
        "blocked_claim_scopes": list(commercial.get("blocked_claim_scopes") or []),
        "general_platform_claim_allowed": bool(commercial.get("general_platform_claim_allowed") is True),
        "license_present": bool(commercial.get("license_present") is True),
        "license_decision_status": license_decision.get("status", ""),
        "license_authorized_for_file_creation_review": bool(license_decision.get("authorized_for_license_file_creation_review") is True),
        "license_decision_packet_status": license_options.get("status", ""),
        "license_decision_packet_ready": bool(license_options.get("status") == "product_license_decision_packet_ready"),
        "license_decision_option_count": int(license_options.get("option_count") or 0),
        "source_license_file_creation_work_order_status": license_work_order.get("status", ""),
        "license_file_creation_work_order_status": license_work_order.get("status", ""),
        "license_file_creation_review_ready": bool(license_work_order.get("license_file_creation_review_ready") is True),
        "license_file_creation_work_order_blocker_count": int(license_work_order.get("blocker_count") or 0),
        "license_file_creation_work_order_artifact": str(PRODUCT_LICENSE_FILE_WORK_ORDER_ARTIFACT),
        "commercial_gate_only_license_blocked": bool(license_options.get("commercial_gate_only_license_blocked") is True),
        "operator_template_csv": license_options.get("operator_template_csv") or str(PRODUCT_LICENSE_DECISION_TEMPLATE),
        "operator_intake_csv": license_options.get("operator_intake_csv") or str(PRODUCT_LICENSE_DECISION_INTAKE),
        "required_fields": list(license_options.get("required_fields") or LICENSE_REQUIRED_FIELDS),
        "required_decision": license_options.get("required_decision") or DECISION_CREATE_LICENSE,
        "approval_token_required": license_options.get("approval_token_required") or LICENSE_APPROVAL_TOKEN,
        "runtime_requirements_present": bool(commercial.get("runtime_requirements_present") is True),
        "runtime_dependency_count": int(commercial.get("runtime_dependency_count") or 0),
        "loose_runtime_dependency_count": int(commercial.get("loose_runtime_dependency_count") or 0),
        "external_api_runtime_dependency_count": int(commercial.get("external_api_runtime_dependency_count") or 0),
        "optional_profiles_separated": bool(commercial.get("optional_profiles_separated") is True),
        "deployment_manifest_present": bool(commercial.get("deployment_manifest_present") is True),
        "core_product_surface_present": bool(commercial.get("core_product_surface_present") is True),
        "public_benchmark_evidence_ready": bool(commercial.get("public_benchmark_evidence_ready") is True),
        "public_benchmark_status": commercial.get("public_benchmark_status", ""),
        "public_benchmark_required_suite_count": int(commercial.get("public_benchmark_required_suite_count") or 0),
        "public_benchmark_ready_required_suite_count": int(
            commercial.get("public_benchmark_ready_required_suite_count") or 0
        ),
        "public_benchmark_blocked_suite_count": int(commercial.get("public_benchmark_blocked_suite_count") or 0),
        "public_benchmark_suite_coverage_ready": bool(
            commercial.get("public_benchmark_suite_coverage_ready") is True
        ),
        "public_benchmark_suite_materialization_manifest_count": int(
            commercial.get("public_benchmark_suite_materialization_manifest_count") or 0
        ),
        "public_benchmark_suite_scorecard_row_csv_count": int(
            commercial.get("public_benchmark_suite_scorecard_row_csv_count") or 0
        ),
        "public_benchmark_suite_threshold_count": int(commercial.get("public_benchmark_suite_threshold_count") or 0),
        "public_benchmark_suite_blocker_count": int(commercial.get("public_benchmark_suite_blocker_count") or 0),
        "public_benchmark_suite_run_command_count": int(commercial.get("public_benchmark_suite_run_command_count") or 0),
        "public_benchmark_suite_materialization_run_command_count": int(
            commercial.get("public_benchmark_suite_materialization_run_command_count") or 0
        ),
        "public_benchmark_suite_result_provenance_command_count": int(
            commercial.get("public_benchmark_suite_result_provenance_command_count") or 0
        ),
        "public_benchmark_suite_result_provenance_present_count": int(
            commercial.get("public_benchmark_suite_result_provenance_present_count") or 0
        ),
        "public_benchmark_suite_no_external_dependency_count": int(
            commercial.get("public_benchmark_suite_no_external_dependency_count") or 0
        ),
        "public_benchmark_work_order_status": commercial.get("public_benchmark_work_order_status", ""),
        "public_benchmark_work_order_local_artifact_preflight_ready": bool(
            commercial.get("public_benchmark_work_order_local_artifact_preflight_ready") is True
        ),
        "public_benchmark_work_order_local_artifact_preflight_ready_suite_count": int(
            commercial.get("public_benchmark_work_order_local_artifact_preflight_ready_suite_count") or 0
        ),
        "public_benchmark_work_order_local_artifact_preflight_blocked_suite_count": int(
            commercial.get("public_benchmark_work_order_local_artifact_preflight_blocked_suite_count") or 0
        ),
        "public_benchmark_work_order_missing_local_input_artifact_count": int(
            commercial.get("public_benchmark_work_order_missing_local_input_artifact_count") or 0
        ),
        "public_benchmark_work_order_missing_local_output_artifact_count": int(
            commercial.get("public_benchmark_work_order_missing_local_output_artifact_count") or 0
        ),
        "blocker_count": int(commercial.get("blocker_count") or 0),
        "check_count": int(commercial.get("check_count") or 0),
        "checks": rows,
        "blockers": blockers,
        "license_file_written": False,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": commercial.get("claim_boundary", ""),
    }


@router.get("/release-readiness")
async def get_product_release_readiness() -> dict[str, Any]:
    release_packet = _read_json_object(PRODUCT_RELEASE_OPERATIONS_ARTIFACT)
    architecture_packet = _read_json_object(PRODUCT_ARCHITECTURE_ARTIFACT)
    commercial_packet = _read_json_object(PRODUCT_COMMERCIAL_INDEPENDENCE_ARTIFACT)
    operational_quality_packet = _read_json_object(PRODUCT_OPERATIONAL_QUALITY_ARTIFACT)
    license_packet = _read_json_object(PRODUCT_LICENSE_DECISION_ARTIFACT)
    license_options_packet = _read_json_object(PRODUCT_LICENSE_DECISION_PACKET_ARTIFACT)
    license_work_order_packet = _read_json_object(PRODUCT_LICENSE_FILE_WORK_ORDER_ARTIFACT)
    goal_packet = _read_json_object(GOAL_RELEASE_DECISION_ARTIFACT)
    release = _summary(release_packet)
    architecture = _summary(architecture_packet)
    commercial = _summary(commercial_packet)
    operational_quality = _summary(operational_quality_packet)
    license_decision = _summary(license_packet)
    license_options = _summary(license_options_packet)
    license_work_order = _summary(license_work_order_packet)
    goal = _summary(goal_packet)
    if not release:
        return {
            "status": "missing_product_release_operations_dossier",
            "artifact_path": str(PRODUCT_RELEASE_OPERATIONS_ARTIFACT),
            "release_allowed": False,
            "commercial_independent_product_ready": False,
            "restricted_commercial_scope_claim_ready": False,
            "commercial_claim_scope_tier": "missing_product_release_operations_dossier",
            "commercial_claim_scope_detail": "",
            "commercial_allowed_scope_families": [],
            "commercial_blocked_claim_scopes": [],
            "commercial_general_platform_claim_allowed": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product release-readiness endpoint only; the local release operations artifact is missing or invalid. "
                "It does not run docking, assemble bundles, claim release readiness, or mutate external state."
            ),
        }
    return {
        "status": release.get("status"),
        "artifact_path": str(PRODUCT_RELEASE_OPERATIONS_ARTIFACT),
        "target_id": release.get("target_id", ""),
        "family": release.get("family", ""),
        "product_api_surface_ready": bool(release.get("product_api_surface_ready") is True),
        "capability_surface_ready": bool(release.get("capability_surface_ready") is True),
        "authorized_for_execution": bool(release.get("authorized_for_execution") is True),
        "bundle_assembled": bool(release.get("bundle_assembled") is True),
        "bundle_validation_passed": bool(release.get("bundle_validation_passed") is True),
        "pilot_delivery_ready": bool(release.get("pilot_delivery_ready") is True),
        "delivery_ready_claim_allowed": bool(release.get("delivery_ready_claim_allowed") is True),
        "product_architecture_status": architecture.get("status", ""),
        "product_architecture_local_surface_ready": bool(architecture.get("local_architecture_surface_ready") is True),
        "product_architecture_release_ready": bool(architecture.get("architecture_release_ready") is True),
        "operational_quality_ready": bool(
            release.get("operational_quality_ready") is True
            or operational_quality.get("operational_quality_ready") is True
        ),
        "source_operational_quality_status": release.get("source_operational_quality_status")
        or operational_quality.get("status", ""),
        "operational_quality_blocker_count": int(
            release.get("operational_quality_blocker_count")
            if release.get("operational_quality_blocker_count") is not None
            else operational_quality.get("blocker_count") or 0
        ),
        "product_architecture_blocked_lane_count": int(architecture.get("blocked_lane_count") or 0),
        "product_architecture_approval_required_lane_count": int(architecture.get("approval_required_lane_count") or 0),
        "product_service_boundary_ready": bool(architecture.get("product_service_boundary_ready") is True),
        "product_api_contract_ready": bool(architecture.get("product_api_contract_ready") is True),
        "public_benchmark_suite_materialization_manifest_count": int(
            release.get("public_benchmark_suite_materialization_manifest_count") or 0
        ),
        "public_benchmark_suite_scorecard_row_csv_count": int(
            release.get("public_benchmark_suite_scorecard_row_csv_count") or 0
        ),
        "public_benchmark_suite_threshold_count": int(release.get("public_benchmark_suite_threshold_count") or 0),
        "public_benchmark_suite_blocker_count": int(release.get("public_benchmark_suite_blocker_count") or 0),
        "public_benchmark_suite_run_command_count": int(release.get("public_benchmark_suite_run_command_count") or 0),
        "public_benchmark_suite_materialization_run_command_count": int(
            release.get("public_benchmark_suite_materialization_run_command_count") or 0
        ),
        "public_benchmark_suite_result_provenance_command_count": int(
            release.get("public_benchmark_suite_result_provenance_command_count") or 0
        ),
        "public_benchmark_suite_result_provenance_present_count": int(
            release.get("public_benchmark_suite_result_provenance_present_count") or 0
        ),
        "public_benchmark_suite_no_external_dependency_count": int(
            release.get("public_benchmark_suite_no_external_dependency_count") or 0
        ),
        "public_benchmark_work_order_status": release.get("public_benchmark_work_order_status", ""),
        "public_benchmark_work_order_artifact": release.get("public_benchmark_work_order_artifact", ""),
        "public_benchmark_work_order_open_suite_count": int(
            release.get("public_benchmark_work_order_open_suite_count") or 0
        ),
        "public_benchmark_work_order_materialization_required_suite_count": int(
            release.get("public_benchmark_work_order_materialization_required_suite_count") or 0
        ),
        "public_benchmark_work_order_scorecard_required_suite_count": int(
            release.get("public_benchmark_work_order_scorecard_required_suite_count") or 0
        ),
        "public_benchmark_work_order_continuous_validation_command_count": int(
            release.get("public_benchmark_work_order_continuous_validation_command_count") or 0
        ),
        "public_benchmark_work_order_continuous_validation_command": release.get(
            "public_benchmark_work_order_continuous_validation_command", ""
        ),
        "public_benchmark_work_order_suite_run_command_count": int(
            release.get("public_benchmark_work_order_suite_run_command_count") or 0
        ),
        "public_benchmark_work_order_suite_result_provenance_command_count": int(
            release.get("public_benchmark_work_order_suite_result_provenance_command_count") or 0
        ),
        "public_benchmark_work_order_suite_result_provenance_present_count": int(
            release.get("public_benchmark_work_order_suite_result_provenance_present_count") or 0
        ),
        "public_benchmark_work_order_suite_threshold_count": int(
            release.get("public_benchmark_work_order_suite_threshold_count") or 0
        ),
        "public_benchmark_work_order_suite_materialization_manifest_count": int(
            release.get("public_benchmark_work_order_suite_materialization_manifest_count") or 0
        ),
        "public_benchmark_work_order_suite_scorecard_row_csv_count": int(
            release.get("public_benchmark_work_order_suite_scorecard_row_csv_count") or 0
        ),
        "public_benchmark_work_order_suite_no_external_dependency_count": int(
            release.get("public_benchmark_work_order_suite_no_external_dependency_count") or 0
        ),
        "public_benchmark_work_order_local_artifact_preflight_ready_suite_count": int(
            release.get("public_benchmark_work_order_local_artifact_preflight_ready_suite_count") or 0
        ),
        "public_benchmark_work_order_local_artifact_preflight_blocked_suite_count": int(
            release.get("public_benchmark_work_order_local_artifact_preflight_blocked_suite_count") or 0
        ),
        "public_benchmark_work_order_missing_local_input_artifact_count": int(
            release.get("public_benchmark_work_order_missing_local_input_artifact_count") or 0
        ),
        "public_benchmark_work_order_missing_local_output_artifact_count": int(
            release.get("public_benchmark_work_order_missing_local_output_artifact_count") or 0
        ),
        "product_architecture_cleanup_postcheck_ready": bool(architecture.get("cleanup_postcheck_contract_ready") is True),
        "product_architecture_cleanup_postcheck_row_count": int(architecture.get("cleanup_postcheck_row_count") or 0),
        "product_architecture_cleanup_postcheck_blocked_row_count": int(architecture.get("cleanup_postcheck_blocked_row_count") or 0),
        "commercial_independence_status": commercial.get("status", ""),
        "commercial_independent_product_ready": bool(commercial.get("commercial_independent_product_claim_allowed") is True),
        "restricted_commercial_scope_claim_ready": bool(release.get("restricted_commercial_scope_claim_ready") is True),
        "commercial_claim_scope_tier": release.get("commercial_claim_scope_tier", ""),
        "commercial_claim_scope_detail": release.get("commercial_claim_scope_detail", ""),
        "commercial_allowed_scope_families": list(release.get("commercial_allowed_scope_families") or []),
        "commercial_blocked_claim_scopes": list(release.get("commercial_blocked_claim_scopes") or []),
        "commercial_general_platform_claim_allowed": bool(
            release.get("commercial_general_platform_claim_allowed") is True
        ),
        "license_present": bool(commercial.get("license_present") is True),
        "license_decision_status": license_decision.get("status", ""),
        "license_authorized_for_file_creation_review": bool(license_decision.get("authorized_for_license_file_creation_review") is True),
        "license_decision_packet_status": license_options.get("status", ""),
        "license_decision_packet_ready": bool(license_options.get("status") == "product_license_decision_packet_ready"),
        "license_decision_option_count": int(license_options.get("option_count") or 0),
        "source_license_file_creation_work_order_status": release.get("source_license_file_creation_work_order_status", ""),
        "license_file_creation_work_order_status": release.get("source_license_file_creation_work_order_status")
        or license_work_order.get("status", ""),
        "license_file_creation_review_ready": bool(
            release.get("license_file_creation_review_ready") is True
            or license_work_order.get("license_file_creation_review_ready") is True
        ),
        "license_file_creation_work_order_blocker_count": int(
            release.get("license_file_creation_work_order_blocker_count")
            if release.get("license_file_creation_work_order_blocker_count") is not None
            else license_work_order.get("blocker_count") or 0
        ),
        "license_file_creation_work_order_artifact": release.get("license_file_creation_work_order_artifact")
        or str(PRODUCT_LICENSE_FILE_WORK_ORDER_ARTIFACT),
        "license_operator_template_csv": license_options.get("operator_template_csv") or str(PRODUCT_LICENSE_DECISION_TEMPLATE),
        "license_operator_intake_csv": license_options.get("operator_intake_csv") or str(PRODUCT_LICENSE_DECISION_INTAKE),
        "license_required_fields": list(license_options.get("required_fields") or LICENSE_REQUIRED_FIELDS),
        "license_required_decision": license_options.get("required_decision") or DECISION_CREATE_LICENSE,
        "license_approval_token_required": license_options.get("approval_token_required") or LICENSE_APPROVAL_TOKEN,
        "goal_release_status": goal.get("status", ""),
        "release_allowed": bool(goal.get("release_allowed") is True),
        "goal_release_blocker_count": int(goal.get("blocker_count") or 0),
        "cameo_architecture_validation_ready": bool(goal.get("cameo_architecture_validation_ready") is True),
        "cleanup_objective_ready": bool(goal.get("cleanup_objective_ready") is True),
        "blocked_stage_count": int(release.get("blocked_stage_count") or 0),
        "approval_required_stage_count": int(release.get("approval_required_stage_count") or 0),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "license_file_written": False,
        "external_state_mutated": False,
        "claim_boundary": (
            "Product release-readiness endpoint only; it reports local release, commercial-independence, CAMEO, and cleanup gate summaries. "
            "It does not run docking, assemble bundles, submit CAMEO predictions, delete data, or mutate external state."
        ),
    }


@router.get("/docking/jobs/{job_id}")
async def get_docking_job(job_id: str) -> dict[str, Any]:
    path = _jobs_dir() / f"{job_id}.json"
    if not path.exists():
        return {
            "job_id": job_id,
            "status": "missing",
            "execution_enabled": False,
            "docking_results_emitted": False,
        }
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/docking/jobs")
async def list_docking_jobs(
    limit: int = 50,
    source_host: str = "",
    root_job_id: str = "",
    customer_id: str = "",
    user_id: str = "",
) -> dict[str, Any]:
    return list_job_records(
        _jobs_dir(),
        limit=max(1, min(limit, 500)),
        source_host=source_host,
        root_job_id=root_job_id,
        customer_id=customer_id,
        user_id=user_id,
    )


@router.get("/docking/jobs/{job_id}/history")
async def get_docking_job_history(job_id: str) -> dict[str, Any]:
    return job_history(_jobs_dir(), job_id)


@router.post("/docking/jobs/{job_id}/cancel")
async def cancel_docking_job(job_id: str, payload: JobActionRequest | None = None) -> dict[str, Any]:
    action = payload or JobActionRequest()
    return cancel_job_record(_jobs_dir(), job_id, reason=action.reason or "", actor=action.actor or "")


@router.post("/docking/jobs/{job_id}/retry")
async def retry_docking_job(job_id: str, payload: JobActionRequest | None = None) -> dict[str, Any]:
    action = payload or JobActionRequest()
    return retry_job_record(_jobs_dir(), job_id, reason=action.reason or "", actor=action.actor or "")


@router.get("/job-orchestration-contract")
async def get_product_job_orchestration_contract() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_JOB_ORCHESTRATION_CONTRACT_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_product_job_orchestration_contract",
            "artifact_path": str(PRODUCT_JOB_ORCHESTRATION_CONTRACT_ARTIFACT),
            "product_job_orchestration_contract_ready": False,
            "check_count": 0,
            "ready_check_count": 0,
            "blocked_check_count": 1,
            "blocked_checks": ["missing_product_job_orchestration_contract"],
            "retry_child_attempt_created": False,
            "idempotency_preserved": False,
            "progress_fields_present": False,
            "listed_status_progress_contract_ready": False,
            "queue_lifecycle_progress_ready": False,
            "customer_run_history_lineage_ready": False,
            "status_snapshot_persistence_ready": False,
            "retention_policy_ready": False,
            "rerun_manifest_ready": False,
            "long_running_status_persistence_ready": False,
            "worker_backend_contract_ready": False,
            "worker_lease_heartbeat_ready": False,
            "retryable_failure_resume_ready": False,
            "running_cancel_ack_ready": False,
            "stale_worker_lease_recovery_ready": False,
            "stale_worker_lease_sweep_ready": False,
            "stale_worker_lease_detected_count": 0,
            "stale_worker_lease_updated_count": 0,
            "retryable_after_stale_count": 0,
            "stale_worker_lease_timeout_seconds": 0,
            "job_retention_days": 0,
            "source_host_filter_job_count": 0,
            "root_job_id_filter_job_count": 0,
            "customer_id_filter_job_count": 0,
            "user_id_filter_job_count": 0,
            "lineage_customer_id": "",
            "lineage_user_id": "",
            "root_attempt_count_after_retry": 0,
            "history_event_count": 0,
            "job_count_after_retry": 0,
            "job_count_after_stale_probe": 0,
            "checks": [],
            "next_required_step": "Regenerate runs/product_job_orchestration_contract_current.json before claiming durable product job orchestration.",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product job orchestration contract endpoint only; it reports the local fail-closed job ledger contract. "
                "It does not run docking, start workers, cancel external compute, emit scientific results, upload, email, "
                "delete, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status", ""),
        "artifact_path": str(PRODUCT_JOB_ORCHESTRATION_CONTRACT_ARTIFACT),
        "product_job_orchestration_contract_ready": bool(
            summary.get("product_job_orchestration_contract_ready") is True
        ),
        "check_count": int(summary.get("check_count") or 0),
        "ready_check_count": int(summary.get("ready_check_count") or 0),
        "blocked_check_count": int(summary.get("blocked_check_count") or 0),
        "blocked_checks": list(summary.get("blocked_checks") or []),
        "retry_child_attempt_created": bool(summary.get("retry_child_attempt_created") is True),
        "idempotency_preserved": bool(summary.get("idempotency_preserved") is True),
        "progress_fields_present": bool(summary.get("progress_fields_present") is True),
        "listed_status_progress_contract_ready": bool(summary.get("listed_status_progress_contract_ready") is True),
        "queue_lifecycle_progress_ready": bool(summary.get("queue_lifecycle_progress_ready") is True),
        "customer_run_history_lineage_ready": bool(summary.get("customer_run_history_lineage_ready") is True),
        "status_snapshot_persistence_ready": bool(summary.get("status_snapshot_persistence_ready") is True),
        "retention_policy_ready": bool(summary.get("retention_policy_ready") is True),
        "rerun_manifest_ready": bool(summary.get("rerun_manifest_ready") is True),
        "long_running_status_persistence_ready": bool(summary.get("long_running_status_persistence_ready") is True),
        "worker_backend_contract_ready": bool(summary.get("worker_backend_contract_ready") is True),
        "worker_lease_heartbeat_ready": bool(summary.get("worker_lease_heartbeat_ready") is True),
        "retryable_failure_resume_ready": bool(summary.get("retryable_failure_resume_ready") is True),
        "running_cancel_ack_ready": bool(summary.get("running_cancel_ack_ready") is True),
        "stale_worker_lease_recovery_ready": bool(summary.get("stale_worker_lease_recovery_ready") is True),
        "stale_worker_lease_sweep_ready": bool(summary.get("stale_worker_lease_sweep_ready") is True),
        "stale_worker_lease_detected_count": int(summary.get("stale_worker_lease_detected_count") or 0),
        "stale_worker_lease_updated_count": int(summary.get("stale_worker_lease_updated_count") or 0),
        "retryable_after_stale_count": int(summary.get("retryable_after_stale_count") or 0),
        "stale_worker_lease_timeout_seconds": int(summary.get("stale_worker_lease_timeout_seconds") or 0),
        "job_retention_days": int(summary.get("job_retention_days") or 0),
        "source_host_filter_job_count": int(summary.get("source_host_filter_job_count") or 0),
        "root_job_id_filter_job_count": int(summary.get("root_job_id_filter_job_count") or 0),
        "customer_id_filter_job_count": int(summary.get("customer_id_filter_job_count") or 0),
        "user_id_filter_job_count": int(summary.get("user_id_filter_job_count") or 0),
        "lineage_customer_id": summary.get("lineage_customer_id", ""),
        "lineage_user_id": summary.get("lineage_user_id", ""),
        "root_attempt_count_after_retry": int(summary.get("root_attempt_count_after_retry") or 0),
        "history_event_count": int(summary.get("history_event_count") or 0),
        "job_count_after_retry": int(summary.get("job_count_after_retry") or 0),
        "job_count_after_stale_probe": int(summary.get("job_count_after_stale_probe") or 0),
        "checks": rows,
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
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


@router.get("/production-ai-checkpoint-readiness")
async def get_product_production_ai_checkpoint_readiness() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_PRODUCTION_AI_CHECKPOINT_READINESS_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_product_production_ai_checkpoint_readiness_artifact",
            "artifact_path": str(PRODUCT_PRODUCTION_AI_CHECKPOINT_READINESS_ARTIFACT),
            "registry_artifact_path": str(RESIDUAL_MODEL_REGISTRY_ARTIFACT),
            "checkpoint_work_order_artifact_path": str(RESIDUAL_PRODUCTION_CHECKPOINT_WORK_ORDER_ARTIFACT),
            "training_data_artifact_path": str(RESIDUAL_PRODUCTION_TRAINING_DATA_CONTRACT_ARTIFACT),
            "force_gpu_worker_return_receipt_artifact_path": str(RESIDUAL_FORCE_GPU_WORKER_RETURN_RECEIPT_ARTIFACT),
            "force_gpu_worker_handoff_artifact_path": str(RESIDUAL_FORCE_GPU_WORKER_HANDOFF_ARTIFACT),
            "production_gpu_execution_environment_artifact_path": str(ROCM_ENVIRONMENT_MANIFEST_ARTIFACT),
            "check_count": 0,
            "pass_check_count": 0,
            "fail_check_count": 1,
            "failed_check_ids": ["missing_product_production_ai_checkpoint_readiness_artifact"],
            "first_failed_check_id": "missing_product_production_ai_checkpoint_readiness_artifact",
            "first_failed_source_artifact": str(PRODUCT_PRODUCTION_AI_CHECKPOINT_READINESS_ARTIFACT),
            "first_failed_observed": "missing",
            "first_failed_required": "product production AI checkpoint readiness artifact exists",
            "first_failed_next_action": "Run python3 tools/build_product_production_ai_checkpoint_readiness.py.",
            "production_ai_checkpoint_ready": False,
            "production_ai_inference_subject_active": False,
            "product_model_layer_ready": False,
            "default_residual_mode": "",
            "production_promotion_allowed": False,
            "registry_promotion_required_gate_ids": [],
            "registry_promotion_missing_gate_ids": [],
            "registry_promotion_missing_gate_count": 0,
            "registry_promotion_upstream_acceptance_ready": False,
            "registry_promotion_currently_satisfied": False,
            "customer_facing_auto_correction_allowed": False,
            "customer_facing_score_mutation_allowed": False,
            "customer_facing_ranking_mutation_allowed": False,
            "trained_model_checkpoint_count": 0,
            "candidate_checkpoint_count": 0,
            "ready_checkpoint_count": 0,
            "checkpoint_preflight_ready": False,
            "production_training_data_ready": False,
            "production_output_head_gap_contract_ready": False,
            "production_output_heads_complete": False,
            "production_output_head_required_field_count": 0,
            "production_output_head_ready_field_count": 0,
            "production_output_head_blocked_field_count": 0,
            "production_output_head_blocked_fields": [],
            "production_output_head_first_blocked_field": "",
            "production_output_head_first_blocked_field_blockers": [],
            "production_output_head_gap_contract_artifact_path": "",
            "force_gpu_worker_return_receipt_ready": False,
            "force_gpu_worker_handoff_ready": False,
            "production_gpu_execution_environment_ready": False,
            "production_gpu_execution_environment_status": "",
            "production_gpu_rocm_manifest_ready": False,
            "production_gpu_rocm_stack_detected": False,
            "production_gpu_rocm_torch_ready": False,
            "production_gpu_rocm_amd_gpu_detected": False,
            "production_gpu_rocm_visible_device_count": 0,
            "production_gpu_rocm_device_names": [],
            "production_gpu_rocm_torch_version": "",
            "production_gpu_rocm_torch_hip_version": "",
            "production_gpu_rocm_visibility_diagnostic_packet_ready": False,
            "production_gpu_rocm_visibility_diagnostic_command_count": 0,
            "production_gpu_rocm_visibility_diagnostic_commands": [],
            "production_gpu_rocm_visibility_diagnostic_required_fields": [],
            "production_gpu_rocm_visibility_diagnostic_required_field_count": 0,
            "production_gpu_rocm_visibility_diagnostic_completion_rule": "",
            "production_gpu_rocm_visibility_diagnostic_return_artifacts": [],
            "production_gpu_rocm_visibility_torch_probe_command": "",
            "production_gpu_rocm_next_required_step": "",
            "force_gpu_worker_handoff_required": False,
            "force_gpu_worker_operator_action_required": False,
            "force_gpu_worker_handoff_next_required_step": "",
            "force_gpu_worker_operator_transfer_manifest_ready": False,
            "force_gpu_worker_operator_transfer_outbound_artifact_count": 0,
            "force_gpu_worker_operator_transfer_outbound_artifacts": [],
            "force_gpu_worker_operator_transfer_inbound_artifact_count": 0,
            "force_gpu_worker_operator_transfer_inbound_artifacts": [],
            "force_gpu_worker_operator_transfer_first_return_artifact": "",
            "force_gpu_worker_operator_transfer_return_manifest_artifact": "",
            "force_gpu_worker_operator_transfer_acceptance_artifact": "",
            "force_gpu_worker_operator_transfer_acceptance_ready_key": "",
            "force_gpu_worker_operator_transfer_post_return_validation_command": "",
            "force_gpu_worker_return_summary_template_payload_json": "",
            "force_gpu_worker_full_regeneration_command": "",
            "force_gpu_worker_post_return_validation_command": "",
            "force_gpu_worker_post_return_output_contract_ready": False,
            "force_gpu_worker_post_return_required_production_output_fields": [],
            "force_gpu_worker_post_return_gpu_unlock_artifacts": [],
            "force_gpu_worker_post_return_unlock_output_fields": [],
            "force_gpu_worker_post_return_min_expected_label_rows": 0,
            "force_gpu_worker_post_return_promotion_ladder_ready": False,
            "force_gpu_worker_post_return_promotion_ladder_contract_ready": False,
            "force_gpu_worker_post_return_promotion_ladder_currently_satisfied": False,
            "force_gpu_worker_post_return_promotion_ladder_current_blocked_stage_count": 0,
            "force_gpu_worker_post_return_promotion_ladder_current_blocked_stage_ids": [],
            "force_gpu_worker_post_return_promotion_ladder_current_next_stage_id": "",
            "force_gpu_worker_post_return_promotion_ladder_current_next_stage_artifact": "",
            "force_gpu_worker_post_return_promotion_ladder_current_next_stage_validation_command": "",
            "force_gpu_worker_post_return_promotion_ladder_stage_count": 0,
            "force_gpu_worker_post_return_promotion_ladder_stage_ids": [],
            "force_gpu_worker_post_return_promotion_ladder": [],
            "force_gpu_worker_post_return_promotion_ladder_ready_keys": [],
            "force_gpu_worker_post_return_promotion_ladder_missing_stages": [],
            "force_gpu_worker_post_return_promotion_ladder_missing_ready_keys": [],
            "production_inference_acceptance_matrix_ready": False,
            "production_inference_acceptance_stage_count": 0,
            "production_inference_acceptance_ready_stage_count": 0,
            "production_inference_acceptance_blocked_stage_count": 0,
            "production_inference_acceptance_stage_ids": [],
            "production_inference_acceptance_ready_stage_ids": [],
            "production_inference_acceptance_blocked_stage_ids": [],
            "production_inference_acceptance_next_stage_id": "",
            "production_inference_acceptance_next_stage_artifact": "",
            "production_inference_acceptance_next_stage_validation_command": "",
            "production_inference_acceptance_next_stage_release_effect": "",
            "production_inference_acceptance_next_stage_unlock_fields": [],
            "production_inference_acceptance_next_stage_required_checks": [],
            "production_inference_acceptance_next_stage_next_action": "",
            "production_inference_actionable_blocker_stage_id": "",
            "production_inference_actionable_blocker_check_id": "",
            "production_inference_actionable_blocker_artifact": "",
            "production_inference_actionable_blocker_observed": "",
            "production_inference_actionable_blocker_required": "",
            "production_inference_actionable_blocker_next_action": "",
            "production_inference_actionable_blocker_validation_command": "",
            "production_inference_actionable_blocker_unlock_fields": [],
            "production_inference_actionable_blocker_downstream_blocked_stage_count": 0,
            "production_inference_next_after_actionable_blocker_stage_id": "",
            "production_inference_next_after_actionable_blocker_artifact": "",
            "production_inference_next_after_actionable_blocker_validation_command": "",
            "production_inference_next_after_actionable_blocker_required_checks": [],
            "production_inference_next_after_actionable_blocker_unlock_fields": [],
            "production_inference_next_after_actionable_blocker_next_action": "",
            "production_inference_actionable_blocker_blocks_registry_promotion": False,
            "production_inference_actionable_operator_completion_packet_ready": False,
            "production_inference_actionable_operator_completion_packet_artifact": "",
            "production_inference_actionable_operator_completion_artifact_id": "",
            "production_inference_actionable_operator_completion_artifact_path": "",
            "production_inference_actionable_operator_completion_expected_queue_rows": 0,
            "production_inference_actionable_operator_completion_required_fields_or_columns": [],
            "production_inference_actionable_operator_completion_diagnostic_commands": [],
            "production_inference_actionable_operator_completion_diagnostic_command_count": 0,
            "production_inference_actionable_operator_completion_diagnostic_required_fields": [],
            "production_inference_actionable_operator_completion_diagnostic_required_field_count": 0,
            "production_inference_actionable_operator_completion_diagnostic_completion_rule": "",
            "production_inference_actionable_operator_completion_diagnostic_return_artifacts": [],
            "production_inference_actionable_operator_completion_torch_visibility_probe_command": "",
            "production_inference_actionable_operator_completion_failed_check_ids": [],
            "production_inference_actionable_operator_completion_template_payload_json": "",
            "production_inference_actionable_operator_completion_actual_summary_return_path": "",
            "production_inference_actionable_operator_completion_actual_manifest_return_path": "",
            "production_inference_actionable_operator_completion_validation_command": "",
            "production_inference_actionable_operator_completion_full_regeneration_command": "",
            "production_inference_actionable_operator_completion_completion_rule": "",
            "production_inference_actionable_operator_completion_backend_provenance_completion_rule": "",
            "production_inference_actionable_operator_completion_next_action": "",
            "production_inference_actionable_operator_completion_packet": {},
            "production_inference_worker_runtime_receipt_contract_ready": False,
            "production_inference_worker_runtime_receipt_contract": {},
            "production_inference_worker_runtime_receipt_required_fields_or_columns": [],
            "production_inference_worker_runtime_receipt_required_field_count": 0,
            "production_inference_worker_runtime_receipt_completion_rule": "",
            "production_inference_worker_runtime_receipt_post_environment_next_stage_id": "",
            "production_inference_worker_runtime_receipt_post_environment_next_artifact": "",
            "production_inference_worker_runtime_receipt_post_environment_validation_command": "",
            "production_inference_worker_runtime_receipt_full_regeneration_command": "",
            "production_inference_worker_runtime_receipt_guardrails": [],
            "production_inference_acceptance_matrix": [],
            "force_gpu_worker_post_run_validation_chain_current": False,
            "force_gpu_worker_post_run_validation_command_count": 0,
            "force_gpu_worker_post_run_validation_commands": [],
            "checkpoint_closure_blockers": ["missing_registry_or_checkpoint_work_order"],
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
            "gpu_receipt_blockers": [],
            "gpu_receipt_summary_manifest_bound": False,
            "gpu_receipt_summary_out_manifest_csv_bound": False,
            "gpu_receipt_summary_out_summary_json_bound": False,
            "gpu_receipt_summary_manifest_row_counts_consistent": False,
            "gpu_receipt_summary_manifest_csv": "",
            "gpu_receipt_summary_out_manifest_csv": "",
            "gpu_receipt_summary_out_summary_json": "",
            "gpu_receipt_production_gpu_backend_provenance_ready": False,
            "gpu_receipt_production_gpu_backend_rows": 0,
            "gpu_receipt_production_gpu_backend_non_production_rows": 0,
            "gpu_receipt_production_gpu_backend_prod_mode": False,
            "gpu_receipt_production_gpu_backend_require_rust_hip": False,
            "gpu_receipt_expected_queue_rows": 0,
            "gpu_receipt_expected_npz_count": 0,
            "gpu_receipt_queue_id_count": 0,
            "gpu_receipt_queue_fingerprint_count": 0,
            "gpu_receipt_manifest_ok_row_count": 0,
            "gpu_receipt_manifest_row_count": 0,
            "gpu_receipt_manifest_identity_row_count": 0,
            "gpu_receipt_manifest_matched_queue_id_count": 0,
            "gpu_receipt_manifest_matched_expected_npz_count": 0,
            "gpu_receipt_manifest_matched_queue_fingerprint_count": 0,
            "gpu_receipt_manifest_operator_verified": False,
            "gpu_receipt_operator_verified_true_count": 0,
            "gpu_receipt_identity_coverage_ready": False,
            "training_data_failed_check_ids": [],
            "training_data_missing_output_labels": [],
            "next_required_step": "Run python3 tools/build_product_production_ai_checkpoint_readiness.py.",
            "requirements": [],
            "execution_enabled": False,
            "docking_results_emitted": False,
            "model_promoted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Production AI checkpoint-readiness endpoint only; local registry/work-order artifacts are missing. "
                "It does not run inference, train models, create checkpoints, promote production mode, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_PRODUCTION_AI_CHECKPOINT_READINESS_ARTIFACT),
        "registry_artifact_path": summary.get("registry_artifact_path", ""),
        "checkpoint_work_order_artifact_path": summary.get("checkpoint_work_order_artifact_path", ""),
        "training_data_artifact_path": summary.get("training_data_artifact_path", ""),
        "force_gpu_worker_return_receipt_artifact_path": summary.get("force_gpu_worker_return_receipt_artifact_path", ""),
        "force_gpu_worker_handoff_artifact_path": summary.get("force_gpu_worker_handoff_artifact_path", ""),
        "production_gpu_execution_environment_artifact_path": summary.get(
            "production_gpu_execution_environment_artifact_path", ""
        ),
        "check_count": int(summary.get("check_count") or 0),
        "pass_check_count": int(summary.get("pass_check_count") or 0),
        "fail_check_count": int(summary.get("fail_check_count") or 0),
        "failed_check_ids": list(summary.get("failed_check_ids") or []),
        "first_failed_check_id": summary.get("first_failed_check_id", ""),
        "first_failed_source_artifact": summary.get("first_failed_source_artifact", ""),
        "first_failed_observed": summary.get("first_failed_observed", ""),
        "first_failed_required": summary.get("first_failed_required", ""),
        "first_failed_next_action": summary.get("first_failed_next_action", ""),
        "production_ai_checkpoint_ready": bool(summary.get("production_ai_checkpoint_ready") is True),
        "production_ai_inference_subject_active": bool(
            summary.get("production_ai_inference_subject_active") is True
        ),
        "product_model_layer_ready": bool(summary.get("product_model_layer_ready") is True),
        "default_residual_mode": summary.get("default_residual_mode", ""),
        "production_promotion_allowed": bool(summary.get("production_promotion_allowed") is True),
        "registry_promotion_required_gate_ids": list(summary.get("registry_promotion_required_gate_ids") or []),
        "registry_promotion_missing_gate_ids": list(summary.get("registry_promotion_missing_gate_ids") or []),
        "registry_promotion_missing_gate_count": int(summary.get("registry_promotion_missing_gate_count") or 0),
        "registry_promotion_upstream_acceptance_ready": bool(
            summary.get("registry_promotion_upstream_acceptance_ready") is True
        ),
        "registry_promotion_currently_satisfied": bool(
            summary.get("registry_promotion_currently_satisfied") is True
        ),
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
        "ready_checkpoint_count": int(summary.get("ready_checkpoint_count") or 0),
        "checkpoint_preflight_ready": bool(summary.get("checkpoint_preflight_ready") is True),
        "production_training_data_ready": bool(summary.get("production_training_data_ready") is True),
        "production_output_head_gap_contract_ready": bool(
            summary.get("production_output_head_gap_contract_ready") is True
        ),
        "production_output_heads_complete": bool(summary.get("production_output_heads_complete") is True),
        "production_output_head_required_field_count": int(
            summary.get("production_output_head_required_field_count") or 0
        ),
        "production_output_head_ready_field_count": int(
            summary.get("production_output_head_ready_field_count") or 0
        ),
        "production_output_head_blocked_field_count": int(
            summary.get("production_output_head_blocked_field_count") or 0
        ),
        "production_output_head_blocked_fields": list(
            summary.get("production_output_head_blocked_fields") or []
        ),
        "production_output_head_first_blocked_field": summary.get(
            "production_output_head_first_blocked_field", ""
        ),
        "production_output_head_first_blocked_field_blockers": list(
            summary.get("production_output_head_first_blocked_field_blockers") or []
        ),
        "production_output_head_gap_contract_artifact_path": summary.get(
            "production_output_head_gap_contract_artifact_path", ""
        ),
        "force_gpu_worker_return_receipt_ready": bool(
            summary.get("force_gpu_worker_return_receipt_ready") is True
        ),
        "force_gpu_worker_handoff_ready": bool(summary.get("force_gpu_worker_handoff_ready") is True),
        "production_gpu_execution_environment_ready": bool(
            summary.get("production_gpu_execution_environment_ready") is True
        ),
        "production_gpu_execution_environment_status": summary.get("production_gpu_execution_environment_status", ""),
        "production_gpu_rocm_manifest_ready": bool(summary.get("production_gpu_rocm_manifest_ready") is True),
        "production_gpu_rocm_stack_detected": bool(summary.get("production_gpu_rocm_stack_detected") is True),
        "production_gpu_rocm_torch_ready": bool(summary.get("production_gpu_rocm_torch_ready") is True),
        "production_gpu_rocm_amd_gpu_detected": bool(summary.get("production_gpu_rocm_amd_gpu_detected") is True),
        "production_gpu_rocm_visible_device_count": int(
            summary.get("production_gpu_rocm_visible_device_count") or 0
        ),
        "production_gpu_rocm_device_names": list(summary.get("production_gpu_rocm_device_names") or []),
        "production_gpu_rocm_torch_version": summary.get("production_gpu_rocm_torch_version", ""),
        "production_gpu_rocm_torch_hip_version": summary.get("production_gpu_rocm_torch_hip_version", ""),
        "production_gpu_rocm_visibility_diagnostic_packet_ready": bool(
            summary.get("production_gpu_rocm_visibility_diagnostic_packet_ready") is True
        ),
        "production_gpu_rocm_visibility_diagnostic_command_count": int(
            summary.get("production_gpu_rocm_visibility_diagnostic_command_count") or 0
        ),
        "production_gpu_rocm_visibility_diagnostic_commands": list(
            summary.get("production_gpu_rocm_visibility_diagnostic_commands") or []
        ),
        "production_gpu_rocm_visibility_diagnostic_required_fields": list(
            summary.get("production_gpu_rocm_visibility_diagnostic_required_fields") or []
        ),
        "production_gpu_rocm_visibility_diagnostic_required_field_count": int(
            summary.get("production_gpu_rocm_visibility_diagnostic_required_field_count") or 0
        ),
        "production_gpu_rocm_visibility_diagnostic_completion_rule": summary.get(
            "production_gpu_rocm_visibility_diagnostic_completion_rule", ""
        ),
        "production_gpu_rocm_visibility_diagnostic_return_artifacts": list(
            summary.get("production_gpu_rocm_visibility_diagnostic_return_artifacts") or []
        ),
        "production_gpu_rocm_visibility_torch_probe_command": summary.get(
            "production_gpu_rocm_visibility_torch_probe_command", ""
        ),
        "production_gpu_rocm_next_required_step": summary.get("production_gpu_rocm_next_required_step", ""),
        "force_gpu_worker_handoff_required": bool(summary.get("force_gpu_worker_handoff_required") is True),
        "force_gpu_worker_operator_action_required": bool(
            summary.get("force_gpu_worker_operator_action_required") is True
        ),
        "force_gpu_worker_handoff_next_required_step": summary.get(
            "force_gpu_worker_handoff_next_required_step", ""
        ),
        "force_gpu_worker_operator_transfer_manifest_ready": bool(
            summary.get("force_gpu_worker_operator_transfer_manifest_ready") is True
        ),
        "force_gpu_worker_operator_transfer_outbound_artifact_count": int(
            summary.get("force_gpu_worker_operator_transfer_outbound_artifact_count") or 0
        ),
        "force_gpu_worker_operator_transfer_outbound_artifacts": list(
            summary.get("force_gpu_worker_operator_transfer_outbound_artifacts") or []
        ),
        "force_gpu_worker_operator_transfer_inbound_artifact_count": int(
            summary.get("force_gpu_worker_operator_transfer_inbound_artifact_count") or 0
        ),
        "force_gpu_worker_operator_transfer_inbound_artifacts": list(
            summary.get("force_gpu_worker_operator_transfer_inbound_artifacts") or []
        ),
        "force_gpu_worker_operator_transfer_first_return_artifact": summary.get(
            "force_gpu_worker_operator_transfer_first_return_artifact", ""
        ),
        "force_gpu_worker_operator_transfer_return_manifest_artifact": summary.get(
            "force_gpu_worker_operator_transfer_return_manifest_artifact", ""
        ),
        "force_gpu_worker_operator_transfer_acceptance_artifact": summary.get(
            "force_gpu_worker_operator_transfer_acceptance_artifact", ""
        ),
        "force_gpu_worker_operator_transfer_acceptance_ready_key": summary.get(
            "force_gpu_worker_operator_transfer_acceptance_ready_key", ""
        ),
        "force_gpu_worker_operator_transfer_post_return_validation_command": summary.get(
            "force_gpu_worker_operator_transfer_post_return_validation_command", ""
        ),
        "force_gpu_worker_return_summary_template_payload_json": summary.get(
            "force_gpu_worker_return_summary_template_payload_json", ""
        ),
        "force_gpu_worker_full_regeneration_command": summary.get("force_gpu_worker_full_regeneration_command", ""),
        "force_gpu_worker_post_return_validation_command": summary.get(
            "force_gpu_worker_post_return_validation_command", ""
        ),
        "force_gpu_worker_post_return_output_contract_ready": bool(
            summary.get("force_gpu_worker_post_return_output_contract_ready") is True
        ),
        "force_gpu_worker_post_return_required_production_output_fields": list(
            summary.get("force_gpu_worker_post_return_required_production_output_fields") or []
        ),
        "force_gpu_worker_post_return_gpu_unlock_artifacts": list(
            summary.get("force_gpu_worker_post_return_gpu_unlock_artifacts") or []
        ),
        "force_gpu_worker_post_return_unlock_output_fields": list(
            summary.get("force_gpu_worker_post_return_unlock_output_fields") or []
        ),
        "force_gpu_worker_post_return_min_expected_label_rows": int(
            summary.get("force_gpu_worker_post_return_min_expected_label_rows") or 0
        ),
        "force_gpu_worker_post_return_promotion_ladder_ready": bool(
            summary.get("force_gpu_worker_post_return_promotion_ladder_ready") is True
        ),
        "force_gpu_worker_post_return_promotion_ladder_contract_ready": bool(
            summary.get("force_gpu_worker_post_return_promotion_ladder_contract_ready") is True
        ),
        "force_gpu_worker_post_return_promotion_ladder_currently_satisfied": bool(
            summary.get("force_gpu_worker_post_return_promotion_ladder_currently_satisfied") is True
        ),
        "force_gpu_worker_post_return_promotion_ladder_current_blocked_stage_count": int(
            summary.get("force_gpu_worker_post_return_promotion_ladder_current_blocked_stage_count") or 0
        ),
        "force_gpu_worker_post_return_promotion_ladder_current_blocked_stage_ids": list(
            summary.get("force_gpu_worker_post_return_promotion_ladder_current_blocked_stage_ids") or []
        ),
        "force_gpu_worker_post_return_promotion_ladder_current_next_stage_id": summary.get(
            "force_gpu_worker_post_return_promotion_ladder_current_next_stage_id", ""
        ),
        "force_gpu_worker_post_return_promotion_ladder_current_next_stage_artifact": summary.get(
            "force_gpu_worker_post_return_promotion_ladder_current_next_stage_artifact", ""
        ),
        "force_gpu_worker_post_return_promotion_ladder_current_next_stage_validation_command": summary.get(
            "force_gpu_worker_post_return_promotion_ladder_current_next_stage_validation_command", ""
        ),
        "force_gpu_worker_post_return_promotion_ladder_stage_count": int(
            summary.get("force_gpu_worker_post_return_promotion_ladder_stage_count") or 0
        ),
        "force_gpu_worker_post_return_promotion_ladder_stage_ids": list(
            summary.get("force_gpu_worker_post_return_promotion_ladder_stage_ids") or []
        ),
        "force_gpu_worker_post_return_promotion_ladder": list(
            summary.get("force_gpu_worker_post_return_promotion_ladder") or []
        ),
        "force_gpu_worker_post_return_promotion_ladder_ready_keys": list(
            summary.get("force_gpu_worker_post_return_promotion_ladder_ready_keys") or []
        ),
        "force_gpu_worker_post_return_promotion_ladder_missing_stages": list(
            summary.get("force_gpu_worker_post_return_promotion_ladder_missing_stages") or []
        ),
        "force_gpu_worker_post_return_promotion_ladder_missing_ready_keys": list(
            summary.get("force_gpu_worker_post_return_promotion_ladder_missing_ready_keys") or []
        ),
        "production_inference_acceptance_matrix_ready": bool(
            summary.get("production_inference_acceptance_matrix_ready") is True
        ),
        "production_inference_acceptance_stage_count": int(
            summary.get("production_inference_acceptance_stage_count") or 0
        ),
        "production_inference_acceptance_ready_stage_count": int(
            summary.get("production_inference_acceptance_ready_stage_count") or 0
        ),
        "production_inference_acceptance_blocked_stage_count": int(
            summary.get("production_inference_acceptance_blocked_stage_count") or 0
        ),
        "production_inference_acceptance_stage_ids": list(
            summary.get("production_inference_acceptance_stage_ids") or []
        ),
        "production_inference_acceptance_ready_stage_ids": list(
            summary.get("production_inference_acceptance_ready_stage_ids") or []
        ),
        "production_inference_acceptance_blocked_stage_ids": list(
            summary.get("production_inference_acceptance_blocked_stage_ids") or []
        ),
        "production_inference_acceptance_next_stage_id": summary.get(
            "production_inference_acceptance_next_stage_id", ""
        ),
        "production_inference_acceptance_next_stage_artifact": summary.get(
            "production_inference_acceptance_next_stage_artifact", ""
        ),
        "production_inference_acceptance_next_stage_validation_command": summary.get(
            "production_inference_acceptance_next_stage_validation_command", ""
        ),
        "production_inference_acceptance_next_stage_release_effect": summary.get(
            "production_inference_acceptance_next_stage_release_effect", ""
        ),
        "production_inference_acceptance_next_stage_unlock_fields": list(
            summary.get("production_inference_acceptance_next_stage_unlock_fields") or []
        ),
        "production_inference_acceptance_next_stage_required_checks": list(
            summary.get("production_inference_acceptance_next_stage_required_checks") or []
        ),
        "production_inference_acceptance_next_stage_next_action": summary.get(
            "production_inference_acceptance_next_stage_next_action", ""
        ),
        "production_inference_actionable_blocker_stage_id": summary.get(
            "production_inference_actionable_blocker_stage_id", ""
        ),
        "production_inference_actionable_blocker_check_id": summary.get(
            "production_inference_actionable_blocker_check_id", ""
        ),
        "production_inference_actionable_blocker_artifact": summary.get(
            "production_inference_actionable_blocker_artifact", ""
        ),
        "production_inference_actionable_blocker_observed": summary.get(
            "production_inference_actionable_blocker_observed", ""
        ),
        "production_inference_actionable_blocker_required": summary.get(
            "production_inference_actionable_blocker_required", ""
        ),
        "production_inference_actionable_blocker_next_action": summary.get(
            "production_inference_actionable_blocker_next_action", ""
        ),
        "production_inference_actionable_blocker_validation_command": summary.get(
            "production_inference_actionable_blocker_validation_command", ""
        ),
        "production_inference_actionable_blocker_unlock_fields": list(
            summary.get("production_inference_actionable_blocker_unlock_fields") or []
        ),
        "production_inference_actionable_blocker_downstream_blocked_stage_count": int(
            summary.get("production_inference_actionable_blocker_downstream_blocked_stage_count") or 0
        ),
        "production_inference_next_after_actionable_blocker_stage_id": summary.get(
            "production_inference_next_after_actionable_blocker_stage_id", ""
        ),
        "production_inference_next_after_actionable_blocker_artifact": summary.get(
            "production_inference_next_after_actionable_blocker_artifact", ""
        ),
        "production_inference_next_after_actionable_blocker_validation_command": summary.get(
            "production_inference_next_after_actionable_blocker_validation_command", ""
        ),
        "production_inference_next_after_actionable_blocker_required_checks": list(
            summary.get("production_inference_next_after_actionable_blocker_required_checks") or []
        ),
        "production_inference_next_after_actionable_blocker_unlock_fields": list(
            summary.get("production_inference_next_after_actionable_blocker_unlock_fields") or []
        ),
        "production_inference_next_after_actionable_blocker_next_action": summary.get(
            "production_inference_next_after_actionable_blocker_next_action", ""
        ),
        "production_inference_actionable_blocker_blocks_registry_promotion": bool(
            summary.get("production_inference_actionable_blocker_blocks_registry_promotion") is True
        ),
        "production_inference_actionable_operator_completion_packet_ready": bool(
            summary.get("production_inference_actionable_operator_completion_packet_ready") is True
        ),
        "production_inference_actionable_operator_completion_packet_artifact": summary.get(
            "production_inference_actionable_operator_completion_packet_artifact", ""
        ),
        "production_inference_actionable_operator_completion_artifact_id": summary.get(
            "production_inference_actionable_operator_completion_artifact_id", ""
        ),
        "production_inference_actionable_operator_completion_artifact_path": summary.get(
            "production_inference_actionable_operator_completion_artifact_path", ""
        ),
        "production_inference_actionable_operator_completion_expected_queue_rows": int(
            summary.get("production_inference_actionable_operator_completion_expected_queue_rows") or 0
        ),
        "production_inference_actionable_operator_completion_required_fields_or_columns": list(
            summary.get("production_inference_actionable_operator_completion_required_fields_or_columns") or []
        ),
        "production_inference_actionable_operator_completion_diagnostic_commands": list(
            summary.get("production_inference_actionable_operator_completion_diagnostic_commands") or []
        ),
        "production_inference_actionable_operator_completion_diagnostic_command_count": int(
            summary.get("production_inference_actionable_operator_completion_diagnostic_command_count") or 0
        ),
        "production_inference_actionable_operator_completion_diagnostic_required_fields": list(
            summary.get("production_inference_actionable_operator_completion_diagnostic_required_fields") or []
        ),
        "production_inference_actionable_operator_completion_diagnostic_required_field_count": int(
            summary.get("production_inference_actionable_operator_completion_diagnostic_required_field_count") or 0
        ),
        "production_inference_actionable_operator_completion_diagnostic_completion_rule": summary.get(
            "production_inference_actionable_operator_completion_diagnostic_completion_rule", ""
        ),
        "production_inference_actionable_operator_completion_diagnostic_return_artifacts": list(
            summary.get("production_inference_actionable_operator_completion_diagnostic_return_artifacts") or []
        ),
        "production_inference_actionable_operator_completion_torch_visibility_probe_command": summary.get(
            "production_inference_actionable_operator_completion_torch_visibility_probe_command", ""
        ),
        "production_inference_actionable_operator_completion_failed_check_ids": list(
            summary.get("production_inference_actionable_operator_completion_failed_check_ids") or []
        ),
        "production_inference_actionable_operator_completion_template_payload_json": summary.get(
            "production_inference_actionable_operator_completion_template_payload_json", ""
        ),
        "production_inference_actionable_operator_completion_actual_summary_return_path": summary.get(
            "production_inference_actionable_operator_completion_actual_summary_return_path", ""
        ),
        "production_inference_actionable_operator_completion_actual_manifest_return_path": summary.get(
            "production_inference_actionable_operator_completion_actual_manifest_return_path", ""
        ),
        "production_inference_actionable_operator_completion_validation_command": summary.get(
            "production_inference_actionable_operator_completion_validation_command", ""
        ),
        "production_inference_actionable_operator_completion_full_regeneration_command": summary.get(
            "production_inference_actionable_operator_completion_full_regeneration_command", ""
        ),
        "production_inference_actionable_operator_completion_completion_rule": summary.get(
            "production_inference_actionable_operator_completion_completion_rule", ""
        ),
        "production_inference_actionable_operator_completion_backend_provenance_completion_rule": summary.get(
            "production_inference_actionable_operator_completion_backend_provenance_completion_rule", ""
        ),
        "production_inference_actionable_operator_completion_next_action": summary.get(
            "production_inference_actionable_operator_completion_next_action", ""
        ),
        "production_inference_actionable_operator_completion_packet": dict(
            summary.get("production_inference_actionable_operator_completion_packet") or {}
        ),
        "production_inference_worker_runtime_receipt_contract_ready": bool(
            summary.get("production_inference_worker_runtime_receipt_contract_ready") is True
        ),
        "production_inference_worker_runtime_receipt_contract": dict(
            summary.get("production_inference_worker_runtime_receipt_contract") or {}
        ),
        "production_inference_worker_runtime_receipt_required_fields_or_columns": list(
            summary.get("production_inference_worker_runtime_receipt_required_fields_or_columns") or []
        ),
        "production_inference_worker_runtime_receipt_required_field_count": int(
            summary.get("production_inference_worker_runtime_receipt_required_field_count") or 0
        ),
        "production_inference_worker_runtime_receipt_completion_rule": summary.get(
            "production_inference_worker_runtime_receipt_completion_rule", ""
        ),
        "production_inference_worker_runtime_receipt_post_environment_next_stage_id": summary.get(
            "production_inference_worker_runtime_receipt_post_environment_next_stage_id", ""
        ),
        "production_inference_worker_runtime_receipt_post_environment_next_artifact": summary.get(
            "production_inference_worker_runtime_receipt_post_environment_next_artifact", ""
        ),
        "production_inference_worker_runtime_receipt_post_environment_validation_command": summary.get(
            "production_inference_worker_runtime_receipt_post_environment_validation_command", ""
        ),
        "production_inference_worker_runtime_receipt_full_regeneration_command": summary.get(
            "production_inference_worker_runtime_receipt_full_regeneration_command", ""
        ),
        "production_inference_worker_runtime_receipt_guardrails": list(
            summary.get("production_inference_worker_runtime_receipt_guardrails") or []
        ),
        "production_inference_acceptance_matrix": list(
            packet.get("production_inference_acceptance_matrix") or []
        ),
        "force_gpu_worker_post_run_validation_chain_current": bool(
            summary.get("force_gpu_worker_post_run_validation_chain_current") is True
        ),
        "force_gpu_worker_post_run_validation_command_count": int(
            summary.get("force_gpu_worker_post_run_validation_command_count") or 0
        ),
        "force_gpu_worker_post_run_validation_commands": list(
            summary.get("force_gpu_worker_post_run_validation_commands") or []
        ),
        "checkpoint_closure_blockers": list(summary.get("checkpoint_closure_blockers") or []),
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
        "gpu_receipt_blockers": list(summary.get("gpu_receipt_blockers") or []),
        "gpu_receipt_summary_manifest_bound": bool(summary.get("gpu_receipt_summary_manifest_bound") is True),
        "gpu_receipt_summary_out_manifest_csv_bound": bool(
            summary.get("gpu_receipt_summary_out_manifest_csv_bound") is True
        ),
        "gpu_receipt_summary_out_summary_json_bound": bool(
            summary.get("gpu_receipt_summary_out_summary_json_bound") is True
        ),
        "gpu_receipt_summary_manifest_row_counts_consistent": bool(
            summary.get("gpu_receipt_summary_manifest_row_counts_consistent") is True
        ),
        "gpu_receipt_summary_manifest_csv": summary.get("gpu_receipt_summary_manifest_csv", ""),
        "gpu_receipt_summary_out_manifest_csv": summary.get("gpu_receipt_summary_out_manifest_csv", ""),
        "gpu_receipt_summary_out_summary_json": summary.get("gpu_receipt_summary_out_summary_json", ""),
        "gpu_receipt_production_gpu_backend_provenance_ready": bool(
            summary.get("gpu_receipt_production_gpu_backend_provenance_ready") is True
        ),
        "gpu_receipt_production_gpu_backend_rows": int(
            summary.get("gpu_receipt_production_gpu_backend_rows") or 0
        ),
        "gpu_receipt_production_gpu_backend_non_production_rows": int(
            summary.get("gpu_receipt_production_gpu_backend_non_production_rows") or 0
        ),
        "gpu_receipt_production_gpu_backend_prod_mode": bool(
            summary.get("gpu_receipt_production_gpu_backend_prod_mode") is True
        ),
        "gpu_receipt_production_gpu_backend_require_rust_hip": bool(
            summary.get("gpu_receipt_production_gpu_backend_require_rust_hip") is True
        ),
        "gpu_receipt_expected_queue_rows": int(summary.get("gpu_receipt_expected_queue_rows") or 0),
        "gpu_receipt_expected_npz_count": int(summary.get("gpu_receipt_expected_npz_count") or 0),
        "gpu_receipt_queue_id_count": int(summary.get("gpu_receipt_queue_id_count") or 0),
        "gpu_receipt_queue_fingerprint_count": int(summary.get("gpu_receipt_queue_fingerprint_count") or 0),
        "gpu_receipt_manifest_ok_row_count": int(summary.get("gpu_receipt_manifest_ok_row_count") or 0),
        "gpu_receipt_manifest_row_count": int(summary.get("gpu_receipt_manifest_row_count") or 0),
        "gpu_receipt_manifest_identity_row_count": int(summary.get("gpu_receipt_manifest_identity_row_count") or 0),
        "gpu_receipt_manifest_matched_queue_id_count": int(
            summary.get("gpu_receipt_manifest_matched_queue_id_count") or 0
        ),
        "gpu_receipt_manifest_matched_expected_npz_count": int(
            summary.get("gpu_receipt_manifest_matched_expected_npz_count") or 0
        ),
        "gpu_receipt_manifest_matched_queue_fingerprint_count": int(
            summary.get("gpu_receipt_manifest_matched_queue_fingerprint_count") or 0
        ),
        "gpu_receipt_manifest_operator_verified": bool(
            summary.get("gpu_receipt_manifest_operator_verified") is True
        ),
        "gpu_receipt_operator_verified_true_count": int(summary.get("gpu_receipt_operator_verified_true_count") or 0),
        "gpu_receipt_identity_coverage_ready": bool(summary.get("gpu_receipt_identity_coverage_ready") is True),
        "training_data_failed_check_ids": list(summary.get("training_data_failed_check_ids") or []),
        "training_data_missing_output_labels": list(summary.get("training_data_missing_output_labels") or []),
        "next_required_step": summary.get("next_required_step", ""),
        "requirements": rows,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/production-ai-gpu-worker-dispatch-manifest")
async def get_product_production_ai_gpu_worker_dispatch_manifest() -> dict[str, Any]:
    packet = _read_json_object(RESIDUAL_FORCE_GPU_WORKER_DISPATCH_MANIFEST_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_residual_force_gpu_worker_dispatch_manifest",
            "artifact_path": str(RESIDUAL_FORCE_GPU_WORKER_DISPATCH_MANIFEST_ARTIFACT),
            "dispatch_manifest_ready": False,
            "handoff_package_ready": False,
            "handoff_package_artifact": "",
            "queue_rows": 0,
            "queue_csv": "",
            "queue_csv_sha256": "",
            "outbound_artifact_count": 0,
            "inbound_artifact_count": 0,
            "local_artifact_reference_count": 0,
            "local_artifact_present_count": 0,
            "local_artifact_missing_count": 1,
            "local_artifact_missing": ["missing_residual_force_gpu_worker_dispatch_manifest"],
            "native_pdb_dependency_count": 0,
            "native_pdb_missing_count": 0,
            "native_pdb_missing": [],
            "tiny_pilot_command": "",
            "full_regeneration_command": "",
            "post_run_validation_commands": [],
            "post_run_validation_command_count": 0,
            "acceptance_contract": {},
            "return_summary_completion_rule": "",
            "return_manifest_required_identity_rule": "",
            "worker_rocm_manifest_completion_rule": "",
            "rows": [],
            "blockers": [{"code": "missing_residual_force_gpu_worker_dispatch_manifest"}],
            "next_required_step": "Run python3 tools/build_residual_force_gpu_worker_dispatch_manifest.py.",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "full_regeneration_executed": False,
            "force_labels_created": False,
            "training_executed": False,
            "checkpoint_created": False,
            "model_promoted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Residual force GPU worker dispatch manifest endpoint only; local manifest is missing. It does not "
                "run GPU jobs, regenerate trajectories, create force labels, train models, promote checkpoints, or "
                "mutate external state."
            ),
        }
    return {
        "status": summary.get("status", ""),
        "artifact_path": str(RESIDUAL_FORCE_GPU_WORKER_DISPATCH_MANIFEST_ARTIFACT),
        "dispatch_manifest_ready": bool(summary.get("dispatch_manifest_ready") is True),
        "handoff_package_ready": bool(summary.get("handoff_package_ready") is True),
        "handoff_package_artifact": summary.get("handoff_package_artifact", ""),
        "queue_rows": int(summary.get("queue_rows") or 0),
        "queue_csv": summary.get("queue_csv", ""),
        "queue_csv_sha256": summary.get("queue_csv_sha256", ""),
        "outbound_artifact_count": int(summary.get("outbound_artifact_count") or 0),
        "inbound_artifact_count": int(summary.get("inbound_artifact_count") or 0),
        "local_artifact_reference_count": int(summary.get("local_artifact_reference_count") or 0),
        "local_artifact_present_count": int(summary.get("local_artifact_present_count") or 0),
        "local_artifact_missing_count": int(summary.get("local_artifact_missing_count") or 0),
        "local_artifact_missing": list(summary.get("local_artifact_missing") or []),
        "native_pdb_dependency_count": int(summary.get("native_pdb_dependency_count") or 0),
        "native_pdb_missing_count": int(summary.get("native_pdb_missing_count") or 0),
        "native_pdb_missing": list(summary.get("native_pdb_missing") or []),
        "tiny_pilot_command": summary.get("tiny_pilot_command", ""),
        "full_regeneration_command": summary.get("full_regeneration_command", ""),
        "post_run_validation_commands": list(summary.get("post_run_validation_commands") or []),
        "post_run_validation_command_count": int(summary.get("post_run_validation_command_count") or 0),
        "acceptance_contract": dict(summary.get("acceptance_contract") or {}),
        "return_summary_completion_rule": summary.get("return_summary_completion_rule", ""),
        "return_manifest_required_identity_rule": summary.get("return_manifest_required_identity_rule", ""),
        "worker_rocm_manifest_completion_rule": summary.get("worker_rocm_manifest_completion_rule", ""),
        "rows": list(rows),
        "blockers": list(blockers),
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "full_regeneration_executed": False,
        "force_labels_created": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/production-ai-gpu-worker-dispatch-bundle")
async def get_product_production_ai_gpu_worker_dispatch_bundle() -> dict[str, Any]:
    packet = _read_json_object(RESIDUAL_FORCE_GPU_WORKER_DISPATCH_BUNDLE_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_residual_force_gpu_worker_dispatch_bundle",
            "artifact_path": str(RESIDUAL_FORCE_GPU_WORKER_DISPATCH_BUNDLE_ARTIFACT),
            "dispatch_bundle_ready": False,
            "dispatch_manifest_ready": False,
            "dispatch_manifest_artifact": "",
            "bundle_tar_path": "",
            "bundle_tar_exists": False,
            "bundle_tar_size_bytes": 0,
            "bundle_tar_sha256": "",
            "bundle_member_count": 0,
            "source_artifact_count": 0,
            "local_artifact_missing_count": 1,
            "native_pdb_dependency_count": 0,
            "native_pdb_missing_count": 0,
            "queue_rows": 0,
            "outbound_artifact_count": 0,
            "inbound_artifact_count": 0,
            "acceptance_contract": {},
            "tiny_pilot_command": "",
            "full_regeneration_command": "",
            "post_run_validation_commands": [],
            "post_run_validation_command_count": 0,
            "rows": [],
            "blockers": [{"code": "missing_residual_force_gpu_worker_dispatch_bundle"}],
            "next_required_step": "Run python3 tools/build_residual_force_gpu_worker_dispatch_bundle.py.",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "full_regeneration_executed": False,
            "force_labels_created": False,
            "training_executed": False,
            "checkpoint_created": False,
            "model_promoted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Residual force GPU worker dispatch bundle endpoint only; local bundle artifact is missing. It does "
                "not run GPU jobs, regenerate trajectories, upload, submit, email, delete files, train models, "
                "promote checkpoints, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status", ""),
        "artifact_path": str(RESIDUAL_FORCE_GPU_WORKER_DISPATCH_BUNDLE_ARTIFACT),
        "dispatch_bundle_ready": bool(summary.get("dispatch_bundle_ready") is True),
        "dispatch_manifest_ready": bool(summary.get("dispatch_manifest_ready") is True),
        "dispatch_manifest_artifact": summary.get("dispatch_manifest_artifact", ""),
        "bundle_tar_path": summary.get("bundle_tar_path", ""),
        "bundle_tar_exists": bool(summary.get("bundle_tar_exists") is True),
        "bundle_tar_size_bytes": int(summary.get("bundle_tar_size_bytes") or 0),
        "bundle_tar_sha256": summary.get("bundle_tar_sha256", ""),
        "bundle_member_count": int(summary.get("bundle_member_count") or 0),
        "source_artifact_count": int(summary.get("source_artifact_count") or 0),
        "local_artifact_missing_count": int(summary.get("local_artifact_missing_count") or 0),
        "native_pdb_dependency_count": int(summary.get("native_pdb_dependency_count") or 0),
        "native_pdb_missing_count": int(summary.get("native_pdb_missing_count") or 0),
        "queue_rows": int(summary.get("queue_rows") or 0),
        "outbound_artifact_count": int(summary.get("outbound_artifact_count") or 0),
        "inbound_artifact_count": int(summary.get("inbound_artifact_count") or 0),
        "acceptance_contract": dict(summary.get("acceptance_contract") or {}),
        "tiny_pilot_command": summary.get("tiny_pilot_command", ""),
        "full_regeneration_command": summary.get("full_regeneration_command", ""),
        "post_run_validation_commands": list(summary.get("post_run_validation_commands") or []),
        "post_run_validation_command_count": int(summary.get("post_run_validation_command_count") or 0),
        "rows": list(rows),
        "blockers": list(blockers),
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "full_regeneration_executed": False,
        "force_labels_created": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/production-ai-gpu-worker-execution-runbook")
async def get_product_production_ai_gpu_worker_execution_runbook() -> dict[str, Any]:
    packet = _read_json_object(RESIDUAL_FORCE_GPU_WORKER_EXECUTION_RUNBOOK_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_residual_force_gpu_worker_execution_runbook",
            "artifact_path": str(RESIDUAL_FORCE_GPU_WORKER_EXECUTION_RUNBOOK_ARTIFACT),
            "execution_runbook_ready": False,
            "dispatch_bundle_ready": False,
            "dispatch_bundle_artifact": "",
            "bundle_tar_path": "",
            "bundle_tar_exists": False,
            "bundle_tar_sha256": "",
            "queue_rows": 0,
            "worker_script_path": "",
            "worker_script_exists": False,
            "worker_script_executable": False,
            "return_packager_script_path": "",
            "return_packager_script_exists": False,
            "return_packager_script_executable": False,
            "return_bundle_tar_path": "",
            "return_bundle_sha256_path": "",
            "manifest_npz_path_columns": [],
            "required_return_core_files": [],
            "return_packager_command": "",
            "step_count": 0,
            "worker_executable_step_count": 0,
            "local_post_return_step_count": 0,
            "rocm_diagnostic_command_count": 0,
            "required_return_artifact_count": 0,
            "required_return_artifacts": [],
            "acceptance_contract": {},
            "tiny_pilot_command": "",
            "full_regeneration_command": "",
            "post_return_validation_command": "",
            "rows": [],
            "blockers": [{"code": "missing_residual_force_gpu_worker_execution_runbook"}],
            "next_required_step": "Run python3 tools/build_residual_force_gpu_worker_execution_runbook.py.",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "full_regeneration_executed": False,
            "force_labels_created": False,
            "training_executed": False,
            "checkpoint_created": False,
            "model_promoted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Residual force GPU worker execution runbook endpoint only; local runbook artifact is missing. "
                "It does not run GPU jobs, extract bundles, regenerate trajectories, upload, train models, promote "
                "checkpoints, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status", ""),
        "artifact_path": str(RESIDUAL_FORCE_GPU_WORKER_EXECUTION_RUNBOOK_ARTIFACT),
        "execution_runbook_ready": bool(summary.get("execution_runbook_ready") is True),
        "dispatch_bundle_ready": bool(summary.get("dispatch_bundle_ready") is True),
        "dispatch_bundle_artifact": summary.get("dispatch_bundle_artifact", ""),
        "bundle_tar_path": summary.get("bundle_tar_path", ""),
        "bundle_tar_exists": bool(summary.get("bundle_tar_exists") is True),
        "bundle_tar_sha256": summary.get("bundle_tar_sha256", ""),
        "queue_rows": int(summary.get("queue_rows") or 0),
        "worker_script_path": summary.get("worker_script_path", ""),
        "worker_script_exists": bool(summary.get("worker_script_exists") is True),
        "worker_script_executable": bool(summary.get("worker_script_executable") is True),
        "return_packager_script_path": summary.get("return_packager_script_path", ""),
        "return_packager_script_exists": bool(summary.get("return_packager_script_exists") is True),
        "return_packager_script_executable": bool(
            summary.get("return_packager_script_executable") is True
        ),
        "return_bundle_tar_path": summary.get("return_bundle_tar_path", ""),
        "return_bundle_sha256_path": summary.get("return_bundle_sha256_path", ""),
        "manifest_npz_path_columns": list(summary.get("manifest_npz_path_columns") or []),
        "required_return_core_files": list(summary.get("required_return_core_files") or []),
        "return_packager_command": summary.get("return_packager_command", ""),
        "step_count": int(summary.get("step_count") or 0),
        "worker_executable_step_count": int(summary.get("worker_executable_step_count") or 0),
        "local_post_return_step_count": int(summary.get("local_post_return_step_count") or 0),
        "rocm_diagnostic_command_count": int(summary.get("rocm_diagnostic_command_count") or 0),
        "required_return_artifact_count": int(summary.get("required_return_artifact_count") or 0),
        "required_return_artifacts": list(summary.get("required_return_artifacts") or []),
        "acceptance_contract": dict(summary.get("acceptance_contract") or {}),
        "tiny_pilot_command": summary.get("tiny_pilot_command", ""),
        "full_regeneration_command": summary.get("full_regeneration_command", ""),
        "post_return_validation_command": summary.get("post_return_validation_command", ""),
        "rows": list(rows),
        "blockers": list(blockers),
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "full_regeneration_executed": False,
        "force_labels_created": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/production-ai-gpu-return-intake")
async def get_product_production_ai_gpu_return_intake() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_PRODUCTION_AI_GPU_RETURN_INTAKE_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    operator_acceptance_matrix = (
        packet.get("operator_acceptance_matrix")
        if isinstance(packet.get("operator_acceptance_matrix"), list)
        else []
    )
    operator_return_artifact_completion_matrix = (
        packet.get("operator_return_artifact_completion_matrix")
        if isinstance(packet.get("operator_return_artifact_completion_matrix"), list)
        else []
    )
    operator_return_artifact_completion_blocker_matrix = (
        packet.get("operator_return_artifact_completion_blocker_matrix")
        if isinstance(packet.get("operator_return_artifact_completion_blocker_matrix"), list)
        else []
    )
    if not summary:
        return {
            "status": "missing_product_production_ai_gpu_return_intake_artifact",
            "artifact_path": str(PRODUCT_PRODUCTION_AI_GPU_RETURN_INTAKE_ARTIFACT),
            "gpu_return_intake_ready": False,
            "gpu_return_artifacts_ready": False,
            "check_count": 0,
            "pass_check_count": 0,
            "fail_check_count": 1,
            "failed_check_ids": ["missing_product_production_ai_gpu_return_intake_artifact"],
            "operator_return_blocker_count": 1,
            "first_failed_check_id": "missing_product_production_ai_gpu_return_intake_artifact",
            "first_failed_source_artifact": str(PRODUCT_PRODUCTION_AI_GPU_RETURN_INTAKE_ARTIFACT),
            "first_failed_required": "product production AI GPU return intake artifact exists",
            "first_failed_observed": "missing",
            "first_failed_next_action": "Run python3 tools/build_product_production_ai_gpu_return_intake.py.",
            "expected_queue_rows": 0,
            "operator_return_bundle_contract_ready": False,
            "operator_return_required_artifacts": [],
            "operator_return_required_artifact_count": 0,
            "operator_return_artifact_completion_matrix": [],
            "operator_return_artifact_completion_matrix_count": 0,
            "operator_return_artifact_completion_blocker_matrix": [],
            "operator_return_artifact_completion_blocker_count": 0,
            "operator_return_next_artifact_completion_packet_ready": False,
            "operator_return_next_artifact_completion_packet": {},
            "operator_return_next_artifact_id": "",
            "operator_return_next_artifact_path": "",
            "operator_return_next_artifact_failed_check_ids": [],
            "operator_return_manifest_required_columns": [],
            "operator_return_manifest_required_column_count": 0,
            "operator_return_validation_ladder_ready": False,
            "operator_return_handoff_binding_ready": False,
            "operator_return_handoff_queue_csv": "",
            "operator_return_handoff_queue_csv_sha256": "",
            "operator_return_handoff_full_regeneration_command": "",
            "operator_return_handoff_return_manifest_schema_contract_ready": False,
            "operator_return_handoff_return_manifest_required_identity_rule": "",
            "operator_return_handoff_return_manifest_fingerprint_columns": [],
            "operator_return_handoff_return_manifest_queue_id_columns": [],
            "operator_return_handoff_return_manifest_npz_columns": [],
            "operator_acceptance_matrix_ready": False,
            "operator_acceptance_stage_count": 0,
            "operator_acceptance_ready_stage_count": 0,
            "operator_acceptance_blocked_stage_count": 0,
            "operator_acceptance_stage_ids": [],
            "operator_acceptance_ready_stage_ids": [],
            "operator_acceptance_blocked_stage_ids": [],
            "operator_acceptance_next_stage_id": "",
            "operator_acceptance_next_stage_artifact": "",
            "operator_acceptance_next_stage_validation_command": "",
            "operator_acceptance_next_stage_release_effect": "",
            "operator_acceptance_next_stage_unlock_fields": [],
            "operator_acceptance_next_stage_required_checks": [],
            "operator_acceptance_next_stage_next_action": "",
            "operator_acceptance_matrix": [],
            "operator_acceptance_stage_check_matrix": [],
            "operator_acceptance_stage_check_matrix_count": 0,
            "operator_acceptance_current_blocked_stage_check_matrix": [],
            "operator_acceptance_current_blocked_stage_check_matrix_count": 0,
            "handoff_ready": False,
            "operator_action_required": True,
            "manifest_template_ready": False,
            "manifest_template_csv": "",
            "manifest_template_row_count": 0,
            "manifest_status_placeholder_count": 0,
            "manifest_operator_verification_placeholder_count": 0,
            "summary_template_ready": False,
            "summary_template_csv": "",
            "summary_template_payload_json": "",
            "summary_template_payload": {},
            "summary_template_field_count": 0,
            "summary_template_required_fields": [],
            "summary_template_completion_rule": "",
            "summary_template_backend_provenance_contract_ready": False,
            "summary_template_required_backend_provenance_fields": [],
            "summary_template_backend_provenance_completion_rule": "",
            "actual_summary_return_path": "",
            "actual_manifest_return_path": "",
            "receipt_status": "",
            "receipt_blockers": [],
            "summary_returned": False,
            "summary_complete": False,
            "summary_manifest_bound": False,
            "summary_manifest_csv": "",
            "summary_out_manifest_csv_present": False,
            "summary_out_manifest_csv": "",
            "summary_out_manifest_csv_bound": False,
            "summary_out_summary_json_bound": False,
            "summary_out_summary_json": "",
            "summary_manifest_row_counts_consistent": False,
            "production_gpu_backend_provenance_ready": False,
            "production_gpu_backend_rows": 0,
            "production_gpu_backend_non_production_rows": 0,
            "production_gpu_backend_prod_mode": False,
            "production_gpu_backend_require_rust_hip": False,
            "worker_rocm_manifest_artifact": "",
            "worker_rocm_manifest_ready": False,
            "worker_rocm_manifest_generation_command": "",
            "worker_rocm_manifest_completion_rule": "",
            "worker_rocm_stack_detected": False,
            "worker_rocm_torch_ready": False,
            "worker_rocm_amd_gpu_detected": False,
            "worker_rocm_visible_device_count": 0,
            "worker_rocm_device_names": [],
            "worker_rocm_next_required_step": "",
            "manifest_returned": False,
            "manifest_complete": False,
            "manifest_npz_paths_complete": False,
            "manifest_npz_files_exist": False,
            "manifest_npz_files_valid": False,
            "manifest_npz_schema_valid": False,
            "manifest_npz_identity_valid": False,
            "manifest_npz_path_column_present": False,
            "manifest_npz_path_present_count": 0,
            "manifest_npz_path_missing_count": 0,
            "manifest_ok_row_missing_npz_path_count": 0,
            "manifest_operator_verified_missing_npz_path_count": 0,
            "manifest_npz_file_existing_count": 0,
            "manifest_npz_file_missing_count": 0,
            "manifest_ok_row_missing_npz_file_count": 0,
            "manifest_operator_verified_missing_npz_file_count": 0,
            "manifest_npz_file_valid_count": 0,
            "manifest_npz_file_invalid_count": 0,
            "manifest_ok_row_invalid_npz_file_count": 0,
            "manifest_operator_verified_invalid_npz_file_count": 0,
            "manifest_npz_schema_valid_count": 0,
            "manifest_npz_schema_invalid_count": 0,
            "manifest_ok_row_invalid_npz_schema_count": 0,
            "manifest_operator_verified_invalid_npz_schema_count": 0,
            "manifest_npz_identity_valid_count": 0,
            "manifest_npz_identity_invalid_count": 0,
            "manifest_ok_row_invalid_npz_identity_count": 0,
            "manifest_operator_verified_invalid_npz_identity_count": 0,
            "manifest_operator_verified": False,
            "identity_coverage_ready": False,
            "post_run_derivation_validation_ready": False,
            "post_return_validation_command": "",
            "post_run_validation_command_count": 0,
            "post_run_validation_commands": [],
            "checks": [],
            "blockers": [],
            "next_required_step": "Run python3 tools/build_product_production_ai_gpu_return_intake.py.",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "full_regeneration_executed": False,
            "force_labels_created": False,
            "training_executed": False,
            "checkpoint_created": False,
            "model_promoted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Production AI GPU-return intake endpoint only; the local intake artifact is missing. "
                "It does not run GPU jobs, train models, promote production mode, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_PRODUCTION_AI_GPU_RETURN_INTAKE_ARTIFACT),
        "gpu_return_intake_ready": bool(summary.get("gpu_return_intake_ready") is True),
        "gpu_return_artifacts_ready": bool(summary.get("gpu_return_artifacts_ready") is True),
        "check_count": int(summary.get("check_count") or 0),
        "pass_check_count": int(summary.get("pass_check_count") or 0),
        "fail_check_count": int(summary.get("fail_check_count") or 0),
        "failed_check_ids": list(summary.get("failed_check_ids") or []),
        "operator_return_blocker_count": int(summary.get("operator_return_blocker_count") or 0),
        "first_failed_check_id": summary.get("first_failed_check_id", ""),
        "first_failed_source_artifact": summary.get("first_failed_source_artifact", ""),
        "first_failed_required": summary.get("first_failed_required", ""),
        "first_failed_observed": summary.get("first_failed_observed", ""),
        "first_failed_next_action": summary.get("first_failed_next_action", ""),
        "expected_queue_rows": int(summary.get("expected_queue_rows") or 0),
        "operator_return_bundle_contract_ready": bool(
            summary.get("operator_return_bundle_contract_ready") is True
        ),
        "operator_return_required_artifacts": list(summary.get("operator_return_required_artifacts") or []),
        "operator_return_required_artifact_count": int(
            summary.get("operator_return_required_artifact_count") or 0
        ),
        "operator_return_artifact_completion_matrix": operator_return_artifact_completion_matrix,
        "operator_return_artifact_completion_matrix_count": int(
            summary.get("operator_return_artifact_completion_matrix_count") or 0
        ),
        "operator_return_artifact_completion_blocker_matrix": (
            operator_return_artifact_completion_blocker_matrix
        ),
        "operator_return_artifact_completion_blocker_count": int(
            summary.get("operator_return_artifact_completion_blocker_count") or 0
        ),
        "operator_return_next_artifact_completion_packet_ready": bool(
            summary.get("operator_return_next_artifact_completion_packet_ready") is True
        ),
        "operator_return_next_artifact_completion_packet": dict(
            summary.get("operator_return_next_artifact_completion_packet") or {}
        ),
        "operator_return_next_artifact_id": summary.get("operator_return_next_artifact_id", ""),
        "operator_return_next_artifact_path": summary.get("operator_return_next_artifact_path", ""),
        "operator_return_next_artifact_failed_check_ids": list(
            summary.get("operator_return_next_artifact_failed_check_ids") or []
        ),
        "operator_return_manifest_required_columns": list(
            summary.get("operator_return_manifest_required_columns") or []
        ),
        "operator_return_manifest_required_column_count": int(
            summary.get("operator_return_manifest_required_column_count") or 0
        ),
        "operator_return_validation_ladder_ready": bool(
            summary.get("operator_return_validation_ladder_ready") is True
        ),
        "operator_return_handoff_binding_ready": bool(
            summary.get("operator_return_handoff_binding_ready") is True
        ),
        "operator_return_handoff_queue_csv": summary.get("operator_return_handoff_queue_csv", ""),
        "operator_return_handoff_queue_csv_sha256": summary.get("operator_return_handoff_queue_csv_sha256", ""),
        "operator_return_handoff_full_regeneration_command": summary.get(
            "operator_return_handoff_full_regeneration_command", ""
        ),
        "operator_return_handoff_return_manifest_schema_contract_ready": bool(
            summary.get("operator_return_handoff_return_manifest_schema_contract_ready") is True
        ),
        "operator_return_handoff_return_manifest_required_identity_rule": summary.get(
            "operator_return_handoff_return_manifest_required_identity_rule", ""
        ),
        "operator_return_handoff_return_manifest_fingerprint_columns": list(
            summary.get("operator_return_handoff_return_manifest_fingerprint_columns") or []
        ),
        "operator_return_handoff_return_manifest_queue_id_columns": list(
            summary.get("operator_return_handoff_return_manifest_queue_id_columns") or []
        ),
        "operator_return_handoff_return_manifest_npz_columns": list(
            summary.get("operator_return_handoff_return_manifest_npz_columns") or []
        ),
        "operator_acceptance_matrix_ready": bool(summary.get("operator_acceptance_matrix_ready") is True),
        "operator_acceptance_stage_count": int(summary.get("operator_acceptance_stage_count") or 0),
        "operator_acceptance_ready_stage_count": int(
            summary.get("operator_acceptance_ready_stage_count") or 0
        ),
        "operator_acceptance_blocked_stage_count": int(
            summary.get("operator_acceptance_blocked_stage_count") or 0
        ),
        "operator_acceptance_stage_ids": list(summary.get("operator_acceptance_stage_ids") or []),
        "operator_acceptance_ready_stage_ids": list(
            summary.get("operator_acceptance_ready_stage_ids") or []
        ),
        "operator_acceptance_blocked_stage_ids": list(
            summary.get("operator_acceptance_blocked_stage_ids") or []
        ),
        "operator_acceptance_next_stage_id": summary.get("operator_acceptance_next_stage_id", ""),
        "operator_acceptance_next_stage_artifact": summary.get(
            "operator_acceptance_next_stage_artifact", ""
        ),
        "operator_acceptance_next_stage_validation_command": summary.get(
            "operator_acceptance_next_stage_validation_command", ""
        ),
        "operator_acceptance_next_stage_release_effect": summary.get(
            "operator_acceptance_next_stage_release_effect", ""
        ),
        "operator_acceptance_next_stage_unlock_fields": list(
            summary.get("operator_acceptance_next_stage_unlock_fields") or []
        ),
        "operator_acceptance_next_stage_required_checks": list(
            summary.get("operator_acceptance_next_stage_required_checks") or []
        ),
        "operator_acceptance_next_stage_next_action": summary.get(
            "operator_acceptance_next_stage_next_action", ""
        ),
        "operator_acceptance_matrix": operator_acceptance_matrix,
        "operator_acceptance_stage_check_matrix": list(
            summary.get("operator_acceptance_stage_check_matrix") or []
        ),
        "operator_acceptance_stage_check_matrix_count": int(
            summary.get("operator_acceptance_stage_check_matrix_count") or 0
        ),
        "operator_acceptance_current_blocked_stage_check_matrix": list(
            summary.get("operator_acceptance_current_blocked_stage_check_matrix") or []
        ),
        "operator_acceptance_current_blocked_stage_check_matrix_count": int(
            summary.get("operator_acceptance_current_blocked_stage_check_matrix_count") or 0
        ),
        "handoff_ready": bool(summary.get("handoff_ready") is True),
        "operator_action_required": bool(summary.get("operator_action_required") is True),
        "manifest_template_ready": bool(summary.get("manifest_template_ready") is True),
        "manifest_template_csv": summary.get("manifest_template_csv", ""),
        "manifest_template_row_count": int(summary.get("manifest_template_row_count") or 0),
        "manifest_status_placeholder_count": int(summary.get("manifest_status_placeholder_count") or 0),
        "manifest_operator_verification_placeholder_count": int(
            summary.get("manifest_operator_verification_placeholder_count") or 0
        ),
        "summary_template_ready": bool(summary.get("summary_template_ready") is True),
        "summary_template_csv": summary.get("summary_template_csv", ""),
        "summary_template_payload_json": summary.get("summary_template_payload_json", ""),
        "summary_template_payload": (
            dict(summary.get("summary_template_payload"))
            if isinstance(summary.get("summary_template_payload"), dict)
            else {}
        ),
        "summary_template_field_count": int(summary.get("summary_template_field_count") or 0),
        "summary_template_required_fields": list(summary.get("summary_template_required_fields") or []),
        "summary_template_completion_rule": summary.get("summary_template_completion_rule", ""),
        "summary_template_backend_provenance_contract_ready": bool(
            summary.get("summary_template_backend_provenance_contract_ready") is True
        ),
        "summary_template_required_backend_provenance_fields": list(
            summary.get("summary_template_required_backend_provenance_fields") or []
        ),
        "summary_template_backend_provenance_completion_rule": summary.get(
            "summary_template_backend_provenance_completion_rule", ""
        ),
        "actual_summary_return_path": summary.get("actual_summary_return_path", ""),
        "actual_manifest_return_path": summary.get("actual_manifest_return_path", ""),
        "receipt_status": summary.get("receipt_status", ""),
        "receipt_blockers": list(summary.get("receipt_blockers") or []),
        "summary_returned": bool(summary.get("summary_returned") is True),
        "summary_complete": bool(summary.get("summary_complete") is True),
        "summary_manifest_bound": bool(summary.get("summary_manifest_bound") is True),
        "summary_manifest_csv": summary.get("summary_manifest_csv", ""),
        "summary_out_manifest_csv_present": bool(summary.get("summary_out_manifest_csv_present") is True),
        "summary_out_manifest_csv": summary.get("summary_out_manifest_csv", ""),
        "summary_out_manifest_csv_bound": bool(summary.get("summary_out_manifest_csv_bound") is True),
        "summary_out_summary_json_bound": bool(summary.get("summary_out_summary_json_bound") is True),
        "summary_out_summary_json": summary.get("summary_out_summary_json", ""),
        "summary_manifest_row_counts_consistent": bool(
            summary.get("summary_manifest_row_counts_consistent") is True
        ),
        "production_gpu_backend_provenance_ready": bool(
            summary.get("production_gpu_backend_provenance_ready") is True
        ),
        "production_gpu_backend_rows": int(summary.get("production_gpu_backend_rows") or 0),
        "production_gpu_backend_non_production_rows": int(
            summary.get("production_gpu_backend_non_production_rows") or 0
        ),
        "production_gpu_backend_prod_mode": bool(summary.get("production_gpu_backend_prod_mode") is True),
        "production_gpu_backend_require_rust_hip": bool(
            summary.get("production_gpu_backend_require_rust_hip") is True
        ),
        "worker_rocm_manifest_artifact": summary.get("worker_rocm_manifest_artifact", ""),
        "worker_rocm_manifest_ready": bool(summary.get("worker_rocm_manifest_ready") is True),
        "worker_rocm_manifest_generation_command": summary.get(
            "worker_rocm_manifest_generation_command", ""
        ),
        "worker_rocm_manifest_completion_rule": summary.get("worker_rocm_manifest_completion_rule", ""),
        "worker_rocm_stack_detected": bool(summary.get("worker_rocm_stack_detected") is True),
        "worker_rocm_torch_ready": bool(summary.get("worker_rocm_torch_ready") is True),
        "worker_rocm_amd_gpu_detected": bool(summary.get("worker_rocm_amd_gpu_detected") is True),
        "worker_rocm_visible_device_count": int(summary.get("worker_rocm_visible_device_count") or 0),
        "worker_rocm_device_names": list(summary.get("worker_rocm_device_names") or []),
        "worker_rocm_next_required_step": summary.get("worker_rocm_next_required_step", ""),
        "manifest_returned": bool(summary.get("manifest_returned") is True),
        "manifest_complete": bool(summary.get("manifest_complete") is True),
        "manifest_npz_paths_complete": bool(summary.get("manifest_npz_paths_complete") is True),
        "manifest_npz_files_exist": bool(summary.get("manifest_npz_files_exist") is True),
        "manifest_npz_files_valid": bool(summary.get("manifest_npz_files_valid") is True),
        "manifest_npz_schema_valid": bool(summary.get("manifest_npz_schema_valid") is True),
        "manifest_npz_identity_valid": bool(summary.get("manifest_npz_identity_valid") is True),
        "manifest_npz_path_column_present": bool(summary.get("manifest_npz_path_column_present") is True),
        "manifest_npz_path_present_count": int(summary.get("manifest_npz_path_present_count") or 0),
        "manifest_npz_path_missing_count": int(summary.get("manifest_npz_path_missing_count") or 0),
        "manifest_ok_row_missing_npz_path_count": int(summary.get("manifest_ok_row_missing_npz_path_count") or 0),
        "manifest_operator_verified_missing_npz_path_count": int(
            summary.get("manifest_operator_verified_missing_npz_path_count") or 0
        ),
        "manifest_npz_file_existing_count": int(summary.get("manifest_npz_file_existing_count") or 0),
        "manifest_npz_file_missing_count": int(summary.get("manifest_npz_file_missing_count") or 0),
        "manifest_ok_row_missing_npz_file_count": int(summary.get("manifest_ok_row_missing_npz_file_count") or 0),
        "manifest_operator_verified_missing_npz_file_count": int(
            summary.get("manifest_operator_verified_missing_npz_file_count") or 0
        ),
        "manifest_npz_file_valid_count": int(summary.get("manifest_npz_file_valid_count") or 0),
        "manifest_npz_file_invalid_count": int(summary.get("manifest_npz_file_invalid_count") or 0),
        "manifest_ok_row_invalid_npz_file_count": int(summary.get("manifest_ok_row_invalid_npz_file_count") or 0),
        "manifest_operator_verified_invalid_npz_file_count": int(
            summary.get("manifest_operator_verified_invalid_npz_file_count") or 0
        ),
        "manifest_npz_schema_valid_count": int(summary.get("manifest_npz_schema_valid_count") or 0),
        "manifest_npz_schema_invalid_count": int(summary.get("manifest_npz_schema_invalid_count") or 0),
        "manifest_ok_row_invalid_npz_schema_count": int(
            summary.get("manifest_ok_row_invalid_npz_schema_count") or 0
        ),
        "manifest_operator_verified_invalid_npz_schema_count": int(
            summary.get("manifest_operator_verified_invalid_npz_schema_count") or 0
        ),
        "manifest_npz_identity_valid_count": int(summary.get("manifest_npz_identity_valid_count") or 0),
        "manifest_npz_identity_invalid_count": int(summary.get("manifest_npz_identity_invalid_count") or 0),
        "manifest_ok_row_invalid_npz_identity_count": int(
            summary.get("manifest_ok_row_invalid_npz_identity_count") or 0
        ),
        "manifest_operator_verified_invalid_npz_identity_count": int(
            summary.get("manifest_operator_verified_invalid_npz_identity_count") or 0
        ),
        "manifest_operator_verified": bool(summary.get("manifest_operator_verified") is True),
        "identity_coverage_ready": bool(summary.get("identity_coverage_ready") is True),
        "post_run_derivation_validation_ready": bool(
            summary.get("post_run_derivation_validation_ready") is True
        ),
        "post_return_validation_command": summary.get("post_return_validation_command", ""),
        "post_run_validation_command_count": int(summary.get("post_run_validation_command_count") or 0),
        "post_run_validation_commands": list(summary.get("post_run_validation_commands") or []),
        "checks": rows,
        "blockers": blockers,
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "full_regeneration_executed": False,
        "force_labels_created": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/production-ai-promotion-workbench")
async def get_product_production_ai_promotion_workbench() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_PRODUCTION_AI_PROMOTION_WORKBENCH_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_product_production_ai_promotion_workbench_artifact",
            "artifact_path": str(PRODUCT_PRODUCTION_AI_PROMOTION_WORKBENCH_ARTIFACT),
            "checkpoint_readiness_artifact_path": str(PRODUCT_PRODUCTION_AI_CHECKPOINT_READINESS_ARTIFACT),
            "promotion_workbench_ready": False,
            "production_ai_promotion_ready": False,
            "production_ai_checkpoint_ready": False,
            "production_ai_inference_subject_active": False,
            "production_promotion_allowed": False,
            "registry_promotion_required_gate_ids": [],
            "registry_promotion_missing_gate_ids": [],
            "registry_promotion_missing_gate_count": 0,
            "registry_promotion_upstream_acceptance_ready": False,
            "registry_promotion_currently_satisfied": False,
            "default_residual_mode": "",
            "trained_model_checkpoint_count": 0,
            "candidate_checkpoint_count": 0,
            "ready_checkpoint_count": 0,
            "checkpoint_preflight_ready": False,
            "production_training_data_ready": False,
            "gpu_handoff_ready": False,
            "gpu_operator_action_required": False,
            "gpu_return_receipt_ready": False,
            "gpu_receipt_expected_queue_rows": 0,
            "gpu_receipt_expected_npz_count": 0,
            "gpu_receipt_manifest_row_count": 0,
            "gpu_receipt_manifest_ok_row_count": 0,
            "gpu_receipt_manifest_identity_row_count": 0,
            "gpu_receipt_manifest_matched_queue_id_count": 0,
            "gpu_receipt_manifest_matched_expected_npz_count": 0,
            "gpu_receipt_manifest_matched_queue_fingerprint_count": 0,
            "gpu_receipt_manifest_operator_verified": False,
            "gpu_receipt_operator_verified_true_count": 0,
            "gpu_receipt_identity_coverage_ready": False,
            "post_return_promotion_ladder_stage_count": 0,
            "post_return_promotion_ladder_ready_stage_count": 0,
            "post_return_promotion_ladder_blocked_stage_count": 1,
            "post_return_promotion_ladder_stage_ids": [],
            "ready_key_alias_used_count": 0,
            "ready_key_alias_used_stage_ids": [],
            "blocked_stage_ids": ["missing_product_production_ai_promotion_workbench_artifact"],
            "first_blocked_stage_id": "missing_product_production_ai_promotion_workbench_artifact",
            "first_blocked_stage_artifact": str(PRODUCT_PRODUCTION_AI_PROMOTION_WORKBENCH_ARTIFACT),
            "first_blocked_stage_ready_key": "promotion_workbench_ready",
            "first_blocked_stage_observed_value": None,
            "checkpoint_failed_check_ids": [],
            "checkpoint_closure_blockers": [],
            "checkpoint_missing_output_fields": [],
            "checkpoint_missing_adapter_output_policy_fields": [],
            "selected_sidecar_ready": False,
            "selected_sidecar_status": "",
            "selected_sidecar_blockers": [],
            "selected_sidecar_missing_output_fields": [],
            "training_data_failed_check_ids": [],
            "training_data_missing_output_labels": [],
            "force_gpu_worker_full_regeneration_command": "",
            "force_gpu_worker_post_return_validation_command": "",
            "force_gpu_worker_post_run_validation_command_count": 0,
            "force_gpu_worker_post_run_validation_commands": [],
            "promotion_stages": [],
            "blockers": [],
            "next_required_step": "Run python3 tools/build_product_production_ai_promotion_workbench.py.",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "model_promoted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Production AI promotion-workbench endpoint only; the local workbench artifact is missing. "
                "It does not run inference, train models, promote production mode, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_PRODUCTION_AI_PROMOTION_WORKBENCH_ARTIFACT),
        "checkpoint_readiness_artifact_path": summary.get("checkpoint_readiness_artifact_path", ""),
        "promotion_workbench_ready": bool(summary.get("promotion_workbench_ready") is True),
        "production_ai_promotion_ready": bool(summary.get("production_ai_promotion_ready") is True),
        "production_ai_checkpoint_ready": bool(summary.get("production_ai_checkpoint_ready") is True),
        "production_ai_inference_subject_active": bool(
            summary.get("production_ai_inference_subject_active") is True
        ),
        "production_promotion_allowed": bool(summary.get("production_promotion_allowed") is True),
        "registry_promotion_required_gate_ids": list(summary.get("registry_promotion_required_gate_ids") or []),
        "registry_promotion_missing_gate_ids": list(summary.get("registry_promotion_missing_gate_ids") or []),
        "registry_promotion_missing_gate_count": int(summary.get("registry_promotion_missing_gate_count") or 0),
        "registry_promotion_upstream_acceptance_ready": bool(
            summary.get("registry_promotion_upstream_acceptance_ready") is True
        ),
        "registry_promotion_currently_satisfied": bool(
            summary.get("registry_promotion_currently_satisfied") is True
        ),
        "default_residual_mode": summary.get("default_residual_mode", ""),
        "trained_model_checkpoint_count": int(summary.get("trained_model_checkpoint_count") or 0),
        "candidate_checkpoint_count": int(summary.get("candidate_checkpoint_count") or 0),
        "ready_checkpoint_count": int(summary.get("ready_checkpoint_count") or 0),
        "checkpoint_preflight_ready": bool(summary.get("checkpoint_preflight_ready") is True),
        "production_training_data_ready": bool(summary.get("production_training_data_ready") is True),
        "gpu_handoff_ready": bool(summary.get("gpu_handoff_ready") is True),
        "gpu_operator_action_required": bool(summary.get("gpu_operator_action_required") is True),
        "gpu_return_receipt_ready": bool(summary.get("gpu_return_receipt_ready") is True),
        "gpu_receipt_expected_queue_rows": int(summary.get("gpu_receipt_expected_queue_rows") or 0),
        "gpu_receipt_expected_npz_count": int(summary.get("gpu_receipt_expected_npz_count") or 0),
        "gpu_receipt_manifest_row_count": int(summary.get("gpu_receipt_manifest_row_count") or 0),
        "gpu_receipt_manifest_ok_row_count": int(summary.get("gpu_receipt_manifest_ok_row_count") or 0),
        "gpu_receipt_manifest_identity_row_count": int(summary.get("gpu_receipt_manifest_identity_row_count") or 0),
        "gpu_receipt_manifest_matched_queue_id_count": int(
            summary.get("gpu_receipt_manifest_matched_queue_id_count") or 0
        ),
        "gpu_receipt_manifest_matched_expected_npz_count": int(
            summary.get("gpu_receipt_manifest_matched_expected_npz_count") or 0
        ),
        "gpu_receipt_manifest_matched_queue_fingerprint_count": int(
            summary.get("gpu_receipt_manifest_matched_queue_fingerprint_count") or 0
        ),
        "gpu_receipt_manifest_operator_verified": bool(
            summary.get("gpu_receipt_manifest_operator_verified") is True
        ),
        "gpu_receipt_operator_verified_true_count": int(summary.get("gpu_receipt_operator_verified_true_count") or 0),
        "gpu_receipt_identity_coverage_ready": bool(summary.get("gpu_receipt_identity_coverage_ready") is True),
        "post_return_promotion_ladder_stage_count": int(
            summary.get("post_return_promotion_ladder_stage_count") or 0
        ),
        "post_return_promotion_ladder_ready_stage_count": int(
            summary.get("post_return_promotion_ladder_ready_stage_count") or 0
        ),
        "post_return_promotion_ladder_blocked_stage_count": int(
            summary.get("post_return_promotion_ladder_blocked_stage_count") or 0
        ),
        "post_return_promotion_ladder_stage_ids": list(
            summary.get("post_return_promotion_ladder_stage_ids") or []
        ),
        "ready_key_alias_used_count": int(summary.get("ready_key_alias_used_count") or 0),
        "ready_key_alias_used_stage_ids": list(summary.get("ready_key_alias_used_stage_ids") or []),
        "blocked_stage_ids": list(summary.get("blocked_stage_ids") or []),
        "first_blocked_stage_id": summary.get("first_blocked_stage_id", ""),
        "first_blocked_stage_artifact": summary.get("first_blocked_stage_artifact", ""),
        "first_blocked_stage_ready_key": summary.get("first_blocked_stage_ready_key", ""),
        "first_blocked_stage_observed_value": summary.get("first_blocked_stage_observed_value"),
        "checkpoint_failed_check_ids": list(summary.get("checkpoint_failed_check_ids") or []),
        "checkpoint_closure_blockers": list(summary.get("checkpoint_closure_blockers") or []),
        "checkpoint_missing_output_fields": list(summary.get("checkpoint_missing_output_fields") or []),
        "checkpoint_missing_adapter_output_policy_fields": list(
            summary.get("checkpoint_missing_adapter_output_policy_fields") or []
        ),
        "selected_sidecar_ready": bool(summary.get("selected_sidecar_ready") is True),
        "selected_sidecar_status": summary.get("selected_sidecar_status", ""),
        "selected_sidecar_blockers": list(summary.get("selected_sidecar_blockers") or []),
        "selected_sidecar_missing_output_fields": list(summary.get("selected_sidecar_missing_output_fields") or []),
        "training_data_failed_check_ids": list(summary.get("training_data_failed_check_ids") or []),
        "training_data_missing_output_labels": list(summary.get("training_data_missing_output_labels") or []),
        "force_gpu_worker_full_regeneration_command": summary.get("force_gpu_worker_full_regeneration_command", ""),
        "force_gpu_worker_post_return_validation_command": summary.get(
            "force_gpu_worker_post_return_validation_command", ""
        ),
        "force_gpu_worker_post_run_validation_command_count": int(
            summary.get("force_gpu_worker_post_run_validation_command_count") or 0
        ),
        "force_gpu_worker_post_run_validation_commands": list(
            summary.get("force_gpu_worker_post_run_validation_commands") or []
        ),
        "promotion_stages": rows,
        "blockers": blockers,
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/scope-breadth-contract")
async def get_product_scope_breadth_contract() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_SCOPE_BREADTH_CONTRACT_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    scope_acceptance_matrix = (
        packet.get("scope_acceptance_matrix") if isinstance(packet.get("scope_acceptance_matrix"), list) else []
    )
    scope_acceptance_stage_evidence_matrix = (
        packet.get("scope_acceptance_stage_evidence_matrix")
        if isinstance(packet.get("scope_acceptance_stage_evidence_matrix"), list)
        else []
    )
    scope_acceptance_current_blocked_stage_evidence_matrix = (
        packet.get("scope_acceptance_current_blocked_stage_evidence_matrix")
        if isinstance(packet.get("scope_acceptance_current_blocked_stage_evidence_matrix"), list)
        else []
    )
    if not summary:
        return {
            "status": "missing_product_scope_breadth_contract",
            "artifact_path": str(PRODUCT_SCOPE_BREADTH_CONTRACT_ARTIFACT),
            "scope_breadth_ready": False,
            "scope_widened": False,
            "scope_claim_posture_ready": False,
            "restricted_scope_claim_allowed": False,
            "allowed_scope_families": [],
            "domain_count": 0,
            "ready_domain_count": 0,
            "missing_domain_count": 0,
            "ready_domains": [],
            "missing_domains": [],
            "first_blocked_domain": "",
            "first_blocked_domain_artifact": "",
            "first_blocked_domain_observed": "",
            "first_blocked_domain_requirement": "",
            "first_blocked_domain_next_action": "",
            "transporter_p0_closure_packet_ready": False,
            "transporter_p0_closure_artifact": "",
            "transporter_p0_current_membrane_open_count": 0,
            "transporter_p0_closure_row_count": 0,
            "transporter_p0_count_matches_readiness": False,
            "transporter_p0_aqp1_core_open_count": 0,
            "transporter_p0_glut1_core_open_count": 0,
            "transporter_p0_glut1_reference_placeholder_rows_after_apply": 0,
            "transporter_p0_glut1_split_placeholder_rows_after_apply": 0,
            "transporter_p0_glut1_meta_placeholder_rows_after_apply": 0,
            "transporter_p0_next_required_step": "",
            "transporter_p0_readiness_matrix_ready": False,
            "transporter_p0_readiness_matrix_artifact": "",
            "transporter_p0_auto_close_ready_artifact_count": 0,
            "transporter_p0_manual_or_external_required_artifact_count": 0,
            "transporter_p0_unresolved_slot_count": 0,
            "transporter_p0_auto_close_ready_slot_count": 0,
            "transporter_p0_external_exact_evidence_required_slot_count": 0,
            "transporter_p0_first_manual_or_external_required_step_id": "",
            "transporter_p0_first_manual_or_external_required_slot_step": "",
            "transporter_p0_first_manual_or_external_required_action": "",
            "transporter_p0_evidence_acquisition_packet_ready": False,
            "transporter_p0_evidence_acquisition_artifact": "",
            "transporter_p0_evidence_acquisition_exact_request_slot_count": 0,
            "transporter_p0_evidence_acquisition_unresolved_slot_count": 0,
            "transporter_p0_evidence_acquisition_first_target_id": "",
            "transporter_p0_evidence_acquisition_first_packet_step": "",
            "transporter_p0_evidence_acquisition_first_replacement_ligand_id": "",
            "transporter_p0_evidence_acquisition_first_request_mode": "",
            "transporter_p0_evidence_acquisition_first_source_signal": "",
            "transporter_p0_evidence_acquisition_first_required_missing_fields": "",
            "transporter_p0_evidence_acquisition_first_next_required_action": "",
            "transporter_p0_evidence_acquisition_next_slot_completion_packet_ready": False,
            "transporter_p0_evidence_acquisition_next_slot_completion_packet": {},
            "transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifacts": [],
            "transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifact_count": 0,
            "transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix": [],
            "transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix_count": 0,
            "transporter_p0_evidence_acquisition_next_slot_return_bundle_blocker_count": 0,
            "transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_id": "",
            "transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_path": "",
            "transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_failed_check_ids": [],
            "transporter_p0_evidence_acquisition_next_slot_id": "",
            "transporter_p0_evidence_acquisition_next_slot_operator_review_artifact": "",
            "transporter_p0_evidence_acquisition_next_slot_source_modality_guard_ready": False,
            "transporter_p0_evidence_acquisition_next_slot_source_modality": "",
            "transporter_p0_evidence_acquisition_next_slot_source_modality_claim_safe": False,
            "transporter_p0_evidence_acquisition_next_slot_source_modality_direct_binding_claim_allowed": False,
            "transporter_p0_evidence_acquisition_next_slot_source_modality_decision": "",
            "transporter_p0_evidence_acquisition_next_slot_source_modality_guardrails": [],
            "transporter_p0_evidence_acquisition_next_slot_source_modality_observed_signal": "",
            "transporter_p0_evidence_acquisition_next_slot_source_modality_required_upgrade": "",
            "evidence_queue_next_operator_completion_aqp1_review_sidecar_ready": False,
            "evidence_queue_next_operator_completion_aqp1_review_candidate_name": "",
            "evidence_queue_next_operator_completion_aqp1_review_source_anchor": "",
            "evidence_queue_next_operator_completion_aqp1_review_target_uniprot": "",
            "evidence_queue_next_operator_completion_aqp1_review_functional_delta_g_surrogate_kcal_mol": "",
            "evidence_queue_next_operator_completion_aqp1_review_direct_binding_claim_allowed": "",
            "evidence_queue_next_operator_completion_aqp1_review_replacement_reference_binding_kcal_mol_must_remain_blank": "",
            "evidence_queue_pxr_exact_review_sidecar_row_count": 0,
            "evidence_queue_next_pxr_exact_review_sidecar_ready": False,
            "evidence_queue_next_pxr_exact_review_row_id": "",
            "evidence_queue_next_pxr_exact_review_candidate_name": "",
            "evidence_queue_next_pxr_exact_review_required_evidence_mode": "",
            "evidence_queue_next_pxr_exact_review_target_match_confirmed": "",
            "evidence_queue_next_pxr_exact_review_replacement_reference_binding_kcal_mol": "",
            "evidence_queue_next_pxr_exact_review_replacement_source_url_or_doi": "",
            "evidence_queue_next_pxr_exact_review_authoritative_apply_allowed": False,
            "evidence_queue_next_pxr_exact_review_scope_promotion_allowed": False,
            "transporter_target_ready_for_promotion_count": 0,
            "transporter_target_blocked_for_promotion_count": 0,
            "transporter_target_ready_for_promotion_ids": [],
            "transporter_target_blocked_for_promotion_ids": [],
            "transporter_primary_blocker_target_id": "",
            "transporter_primary_blocker_packet_step": "",
            "transporter_primary_blocker_candidate_name": "",
            "allowed_claim_scopes": [],
            "blocked_claim_scopes": ["product_scope_breadth_contract_missing"],
            "blocked_claim_scope_count": 1,
            "general_platform_claim_allowed": False,
            "general_platform_claim_blocked": True,
            "general_protein_ligand_platform_ready": False,
            "scope_claim_boundary_detail": "",
            "pxr_exact_review_intake_ready": False,
            "pxr_exact_review_template_row_count": 0,
            "pxr_exact_review_next_review_completion_packet_ready": False,
            "pxr_exact_review_next_review_completion_packet": {},
            "pxr_exact_review_next_review_return_bundle_required_artifacts": [],
            "pxr_exact_review_next_review_return_bundle_required_artifact_count": 0,
            "pxr_exact_review_next_review_return_bundle_completion_matrix": [],
            "pxr_exact_review_next_review_return_bundle_completion_matrix_count": 0,
            "pxr_exact_review_next_review_return_bundle_blocker_count": 0,
            "pxr_exact_review_next_review_return_bundle_next_artifact_id": "",
            "pxr_exact_review_next_review_return_bundle_next_artifact_path": "",
            "pxr_exact_review_next_review_return_bundle_next_artifact_failed_check_ids": [],
            "pxr_exact_review_next_review_row_id": "",
            "pxr_exact_review_next_review_candidate_name": "",
            "pxr_exact_review_next_review_operator_review_artifact": "",
            "pxr_source_modality_triage_ready": False,
            "pxr_source_modality_triage_status": "",
            "pxr_source_modality_triage_artifact": "",
            "pxr_source_modality_triage_decision": "",
            "pxr_source_modality_public_evidence_recheck_ready": False,
            "pxr_source_modality_public_recheck_artifact": "",
            "pxr_source_modality_public_recheck_candidate_count": 0,
            "pxr_source_modality_public_recheck_chembl_direct_binding_total_record_count": 0,
            "pxr_source_modality_public_recheck_chembl_functional_activity_total_record_count": 0,
            "pxr_source_modality_public_recheck_bindingdb_pxr_like_total_record_count": 0,
            "pxr_source_modality_public_recheck_direct_or_claim_safe_binding_kcal_ready_count": 0,
            "pxr_source_modality_public_recheck_all_candidates_remain_blocked": False,
            "pxr_source_modality_public_recheck_first_blocked_candidate_name": "",
            "pxr_source_modality_public_recheck_first_blocked_reason": "",
            "pxr_source_modality_direct_replacement_candidate_packet_ready": False,
            "pxr_source_modality_direct_replacement_artifact": "",
            "pxr_source_modality_direct_replacement_candidate_count": 0,
            "pxr_source_modality_direct_replacement_selected_candidate_count": 0,
            "pxr_source_modality_direct_replacement_selected_claim_safe_candidate_count": 0,
            "pxr_source_modality_direct_replacement_first_ligand_id": "",
            "pxr_source_modality_direct_replacement_first_molecule_chembl_id": "",
            "pxr_source_modality_direct_replacement_first_reference_binding_kcal_mol": "",
            "pxr_source_modality_direct_replacement_first_source": "",
            "pxr_source_modality_direct_replacement_apply_draft_ready": False,
            "pxr_source_modality_direct_replacement_apply_draft_status": "",
            "pxr_source_modality_direct_replacement_apply_draft_artifact": "",
            "pxr_source_modality_direct_replacement_apply_draft_workbook_row_count": 0,
            "pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_before_draft": 0,
            "pxr_source_modality_direct_replacement_apply_draft_overlay_row_count": 0,
            "pxr_source_modality_direct_replacement_apply_draft_ready_for_apply_row_count_after_draft": 0,
            "pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_after_draft": 0,
            "pxr_source_modality_direct_replacement_apply_draft_first_overlay_ligand_id": "",
            "pxr_source_modality_direct_replacement_apply_draft_authoritative_fields_touched": False,
            "pxr_source_modality_activity_proxy_or_conflict_surrogate_row_count": 0,
            "pxr_source_modality_direct_or_claim_safe_quantitative_ready_count": 0,
            "pxr_source_modality_accepted_for_scope_promotion_count": 0,
            "pxr_source_modality_next_review_row_id": "",
            "pxr_source_modality_next_review_candidate_name": "",
            "pxr_source_modality_next_review_source_modality": "",
            "pxr_source_modality_next_review_rejection_reason": "",
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_ready": False,
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_status": "",
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_artifact": "",
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_decision": "",
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_direct_experimental_binding_row_count": 0,
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_claim_safe_binding_kcal_ready_count": 0,
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_ready": False,
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_source_count": 0,
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_result": "",
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_database_recheck_row_count": 0,
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_ligand_identity_mismatch_row_count": 0,
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_pubchem_cid": "",
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_id": "",
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_chembl_target_id": "",
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_bindingdb_uniprot_affinity_row_count": 0,
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_aqp1_activity_row_count": 0,
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_functional_ic50_identity_mismatch_detail": "",
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_replacement_reference_binding_kcal_mol_action": "",
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_computational_binding_energy_row_count": 0,
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_best_computational_binding_energy_kcal_mol": "",
            "scope_acceptance_matrix_ready": False,
            "scope_acceptance_stage_count": 0,
            "scope_acceptance_ready_stage_count": 0,
            "scope_acceptance_blocked_stage_count": 0,
            "scope_acceptance_stage_ids": [],
            "scope_acceptance_ready_stage_ids": [],
            "scope_acceptance_blocked_stage_ids": [],
            "scope_acceptance_next_stage_id": "",
            "scope_acceptance_next_stage_artifact": "",
            "scope_acceptance_next_stage_validation_command": "",
            "scope_acceptance_next_stage_release_effect": "",
            "scope_acceptance_next_stage_unlock_claim_scopes": [],
            "scope_acceptance_next_stage_required_checks": [],
            "scope_acceptance_next_stage_next_action": "",
            "scope_acceptance_stage_evidence_matrix": [],
            "scope_acceptance_stage_evidence_matrix_count": 0,
            "scope_acceptance_current_blocked_stage_evidence_matrix": [],
            "scope_acceptance_current_blocked_stage_evidence_matrix_count": 0,
            "domain_rows": [],
            "scope_acceptance_matrix": [],
            "next_required_step": "Run python3 tools/build_product_scope_breadth_contract.py.",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "scope_widened_by_endpoint": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product scope-breadth-contract endpoint only; the local breadth contract artifact is missing. "
                "It does not acquire evidence, widen claims, run docking, promote scope, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status", ""),
        "artifact_path": str(PRODUCT_SCOPE_BREADTH_CONTRACT_ARTIFACT),
        "scope_breadth_ready": bool(summary.get("scope_breadth_ready") is True),
        "scope_widened": bool(summary.get("scope_widened") is True),
        "scope_claim_posture_ready": bool(summary.get("scope_claim_posture_ready") is True),
        "restricted_scope_claim_allowed": bool(summary.get("restricted_scope_claim_allowed") is True),
        "allowed_scope_families": list(summary.get("allowed_scope_families") or []),
        "domain_count": int(summary.get("domain_count") or 0),
        "ready_domain_count": int(summary.get("ready_domain_count") or 0),
        "missing_domain_count": int(summary.get("missing_domain_count") or 0),
        "ready_domains": list(summary.get("ready_domains") or []),
        "missing_domains": list(summary.get("missing_domains") or []),
        "first_blocked_domain": summary.get("first_blocked_domain", ""),
        "first_blocked_domain_artifact": summary.get("first_blocked_domain_artifact", ""),
        "first_blocked_domain_observed": summary.get("first_blocked_domain_observed", ""),
        "first_blocked_domain_requirement": summary.get("first_blocked_domain_requirement", ""),
        "first_blocked_domain_next_action": summary.get("first_blocked_domain_next_action", ""),
        "transporter_p0_closure_packet_ready": bool(summary.get("transporter_p0_closure_packet_ready") is True),
        "transporter_p0_closure_artifact": summary.get("transporter_p0_closure_artifact", ""),
        "transporter_p0_current_membrane_open_count": int(
            summary.get("transporter_p0_current_membrane_open_count") or 0
        ),
        "transporter_p0_closure_row_count": int(summary.get("transporter_p0_closure_row_count") or 0),
        "transporter_p0_count_matches_readiness": bool(
            summary.get("transporter_p0_count_matches_readiness") is True
        ),
        "transporter_p0_aqp1_core_open_count": int(summary.get("transporter_p0_aqp1_core_open_count") or 0),
        "transporter_p0_glut1_core_open_count": int(summary.get("transporter_p0_glut1_core_open_count") or 0),
        "transporter_p0_glut1_reference_placeholder_rows_after_apply": int(
            summary.get("transporter_p0_glut1_reference_placeholder_rows_after_apply") or 0
        ),
        "transporter_p0_glut1_split_placeholder_rows_after_apply": int(
            summary.get("transporter_p0_glut1_split_placeholder_rows_after_apply") or 0
        ),
        "transporter_p0_glut1_meta_placeholder_rows_after_apply": int(
            summary.get("transporter_p0_glut1_meta_placeholder_rows_after_apply") or 0
        ),
        "transporter_p0_next_required_step": summary.get("transporter_p0_next_required_step", ""),
        "transporter_p0_readiness_matrix_ready": bool(
            summary.get("transporter_p0_readiness_matrix_ready") is True
        ),
        "transporter_p0_readiness_matrix_artifact": summary.get(
            "transporter_p0_readiness_matrix_artifact", ""
        ),
        "transporter_p0_auto_close_ready_artifact_count": int(
            summary.get("transporter_p0_auto_close_ready_artifact_count") or 0
        ),
        "transporter_p0_manual_or_external_required_artifact_count": int(
            summary.get("transporter_p0_manual_or_external_required_artifact_count") or 0
        ),
        "transporter_p0_unresolved_slot_count": int(summary.get("transporter_p0_unresolved_slot_count") or 0),
        "transporter_p0_auto_close_ready_slot_count": int(
            summary.get("transporter_p0_auto_close_ready_slot_count") or 0
        ),
        "transporter_p0_external_exact_evidence_required_slot_count": int(
            summary.get("transporter_p0_external_exact_evidence_required_slot_count") or 0
        ),
        "transporter_p0_first_manual_or_external_required_step_id": summary.get(
            "transporter_p0_first_manual_or_external_required_step_id", ""
        ),
        "transporter_p0_first_manual_or_external_required_slot_step": summary.get(
            "transporter_p0_first_manual_or_external_required_slot_step", ""
        ),
        "transporter_p0_first_manual_or_external_required_action": summary.get(
            "transporter_p0_first_manual_or_external_required_action", ""
        ),
        "transporter_p0_evidence_acquisition_packet_ready": bool(
            summary.get("transporter_p0_evidence_acquisition_packet_ready") is True
        ),
        "transporter_p0_evidence_acquisition_artifact": summary.get(
            "transporter_p0_evidence_acquisition_artifact", ""
        ),
        "transporter_p0_evidence_acquisition_exact_request_slot_count": int(
            summary.get("transporter_p0_evidence_acquisition_exact_request_slot_count") or 0
        ),
        "transporter_p0_evidence_acquisition_unresolved_slot_count": int(
            summary.get("transporter_p0_evidence_acquisition_unresolved_slot_count") or 0
        ),
        "transporter_p0_evidence_acquisition_first_target_id": summary.get(
            "transporter_p0_evidence_acquisition_first_target_id", ""
        ),
        "transporter_p0_evidence_acquisition_first_packet_step": summary.get(
            "transporter_p0_evidence_acquisition_first_packet_step", ""
        ),
        "transporter_p0_evidence_acquisition_first_replacement_ligand_id": summary.get(
            "transporter_p0_evidence_acquisition_first_replacement_ligand_id", ""
        ),
        "transporter_p0_evidence_acquisition_first_request_mode": summary.get(
            "transporter_p0_evidence_acquisition_first_request_mode", ""
        ),
        "transporter_p0_evidence_acquisition_first_source_signal": summary.get(
            "transporter_p0_evidence_acquisition_first_source_signal", ""
        ),
        "transporter_p0_evidence_acquisition_first_required_missing_fields": summary.get(
            "transporter_p0_evidence_acquisition_first_required_missing_fields", ""
        ),
        "transporter_p0_evidence_acquisition_first_next_required_action": summary.get(
            "transporter_p0_evidence_acquisition_first_next_required_action", ""
        ),
        "transporter_p0_evidence_acquisition_next_slot_completion_packet_ready": bool(
            summary.get("transporter_p0_evidence_acquisition_next_slot_completion_packet_ready") is True
        ),
        "transporter_p0_evidence_acquisition_next_slot_completion_packet": dict(
            summary.get("transporter_p0_evidence_acquisition_next_slot_completion_packet") or {}
        ),
        "transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifacts": list(
            summary.get("transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifacts") or []
        ),
        "transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifact_count": int(
            summary.get("transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifact_count") or 0
        ),
        "transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix": list(
            summary.get("transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix") or []
        ),
        "transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix_count": int(
            summary.get("transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix_count") or 0
        ),
        "transporter_p0_evidence_acquisition_next_slot_return_bundle_blocker_count": int(
            summary.get("transporter_p0_evidence_acquisition_next_slot_return_bundle_blocker_count") or 0
        ),
        "transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_id": summary.get(
            "transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_id", ""
        ),
        "transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_path": summary.get(
            "transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_path", ""
        ),
        "transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_failed_check_ids": list(
            summary.get("transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_failed_check_ids")
            or []
        ),
        "transporter_p0_evidence_acquisition_next_slot_id": summary.get(
            "transporter_p0_evidence_acquisition_next_slot_id", ""
        ),
        "transporter_p0_evidence_acquisition_next_slot_operator_review_artifact": summary.get(
            "transporter_p0_evidence_acquisition_next_slot_operator_review_artifact", ""
        ),
        "transporter_p0_evidence_acquisition_next_slot_source_modality_guard_ready": bool(
            summary.get("transporter_p0_evidence_acquisition_next_slot_source_modality_guard_ready") is True
        ),
        "transporter_p0_evidence_acquisition_next_slot_source_modality": summary.get(
            "transporter_p0_evidence_acquisition_next_slot_source_modality", ""
        ),
        "transporter_p0_evidence_acquisition_next_slot_source_modality_claim_safe": bool(
            summary.get("transporter_p0_evidence_acquisition_next_slot_source_modality_claim_safe") is True
        ),
        "transporter_p0_evidence_acquisition_next_slot_source_modality_direct_binding_claim_allowed": bool(
            summary.get(
                "transporter_p0_evidence_acquisition_next_slot_source_modality_direct_binding_claim_allowed"
            )
            is True
        ),
        "transporter_p0_evidence_acquisition_next_slot_source_modality_decision": summary.get(
            "transporter_p0_evidence_acquisition_next_slot_source_modality_decision", ""
        ),
        "transporter_p0_evidence_acquisition_next_slot_source_modality_guardrails": list(
            summary.get("transporter_p0_evidence_acquisition_next_slot_source_modality_guardrails") or []
        ),
        "transporter_p0_evidence_acquisition_next_slot_source_modality_observed_signal": summary.get(
            "transporter_p0_evidence_acquisition_next_slot_source_modality_observed_signal", ""
        ),
        "transporter_p0_evidence_acquisition_next_slot_source_modality_required_upgrade": summary.get(
            "transporter_p0_evidence_acquisition_next_slot_source_modality_required_upgrade", ""
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_ready": bool(
            summary.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_ready"
            )
            is True
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_status": summary.get(
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_status", ""
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_artifact": summary.get(
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_artifact", ""
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_decision": summary.get(
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_triage_decision", ""
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_direct_experimental_binding_row_count": int(
            summary.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_direct_experimental_binding_row_count"
            )
            or 0
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_claim_safe_binding_kcal_ready_count": int(
            summary.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_claim_safe_binding_kcal_ready_count"
            )
            or 0
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_ready": bool(
            summary.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_ready"
            )
            is True
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_source_count": int(
            summary.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_source_count"
            )
            or 0
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_result": summary.get(
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_result",
            "",
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_database_recheck_row_count": int(
            summary.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_database_recheck_row_count"
            )
            or 0
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_ligand_identity_mismatch_row_count": int(
            summary.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_ligand_identity_mismatch_row_count"
            )
            or 0
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_pubchem_cid": summary.get(
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_pubchem_cid",
            "",
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_id": summary.get(
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_id",
            "",
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_chembl_target_id": summary.get(
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_chembl_target_id",
            "",
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_bindingdb_uniprot_affinity_row_count": int(
            summary.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_bindingdb_uniprot_affinity_row_count"
            )
            or 0
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_aqp1_activity_row_count": int(
            summary.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_aqp1_activity_row_count"
            )
            or 0
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_functional_ic50_identity_mismatch_detail": summary.get(
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_functional_ic50_identity_mismatch_detail",
            "",
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_replacement_reference_binding_kcal_mol_action": summary.get(
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_replacement_reference_binding_kcal_mol_action",
            "",
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_computational_binding_energy_row_count": int(
            summary.get(
                "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_computational_binding_energy_row_count"
            )
            or 0
        ),
        "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_best_computational_binding_energy_kcal_mol": summary.get(
            "transporter_p0_evidence_acquisition_aqp1_binding_source_modality_best_computational_binding_energy_kcal_mol",
            "",
        ),
        "evidence_queue_next_operator_completion_aqp1_review_sidecar_ready": bool(
            summary.get("evidence_queue_next_operator_completion_aqp1_review_sidecar_ready") is True
        ),
        "evidence_queue_next_operator_completion_aqp1_review_candidate_name": summary.get(
            "evidence_queue_next_operator_completion_aqp1_review_candidate_name", ""
        ),
        "evidence_queue_next_operator_completion_aqp1_review_source_anchor": summary.get(
            "evidence_queue_next_operator_completion_aqp1_review_source_anchor", ""
        ),
        "evidence_queue_next_operator_completion_aqp1_review_target_uniprot": summary.get(
            "evidence_queue_next_operator_completion_aqp1_review_target_uniprot", ""
        ),
        "evidence_queue_next_operator_completion_aqp1_review_functional_delta_g_surrogate_kcal_mol": summary.get(
            "evidence_queue_next_operator_completion_aqp1_review_functional_delta_g_surrogate_kcal_mol",
            "",
        ),
        "evidence_queue_next_operator_completion_aqp1_review_direct_binding_claim_allowed": summary.get(
            "evidence_queue_next_operator_completion_aqp1_review_direct_binding_claim_allowed",
            "",
        ),
        "evidence_queue_next_operator_completion_aqp1_review_replacement_reference_binding_kcal_mol_must_remain_blank": summary.get(
            "evidence_queue_next_operator_completion_aqp1_review_replacement_reference_binding_kcal_mol_must_remain_blank",
            "",
        ),
        "evidence_queue_pxr_exact_review_sidecar_row_count": int(
            summary.get("evidence_queue_pxr_exact_review_sidecar_row_count") or 0
        ),
        "evidence_queue_next_pxr_exact_review_sidecar_ready": bool(
            summary.get("evidence_queue_next_pxr_exact_review_sidecar_ready") is True
        ),
        "evidence_queue_next_pxr_exact_review_row_id": summary.get(
            "evidence_queue_next_pxr_exact_review_row_id", ""
        ),
        "evidence_queue_next_pxr_exact_review_candidate_name": summary.get(
            "evidence_queue_next_pxr_exact_review_candidate_name", ""
        ),
        "evidence_queue_next_pxr_exact_review_required_evidence_mode": summary.get(
            "evidence_queue_next_pxr_exact_review_required_evidence_mode", ""
        ),
        "evidence_queue_next_pxr_exact_review_target_match_confirmed": summary.get(
            "evidence_queue_next_pxr_exact_review_target_match_confirmed", ""
        ),
        "evidence_queue_next_pxr_exact_review_replacement_reference_binding_kcal_mol": summary.get(
            "evidence_queue_next_pxr_exact_review_replacement_reference_binding_kcal_mol", ""
        ),
        "evidence_queue_next_pxr_exact_review_replacement_source_url_or_doi": summary.get(
            "evidence_queue_next_pxr_exact_review_replacement_source_url_or_doi", ""
        ),
        "evidence_queue_next_pxr_exact_review_authoritative_apply_allowed": bool(
            summary.get("evidence_queue_next_pxr_exact_review_authoritative_apply_allowed") is True
        ),
        "evidence_queue_next_pxr_exact_review_scope_promotion_allowed": bool(
            summary.get("evidence_queue_next_pxr_exact_review_scope_promotion_allowed") is True
        ),
        "transporter_target_ready_for_promotion_count": int(
            summary.get("transporter_target_ready_for_promotion_count") or 0
        ),
        "transporter_target_blocked_for_promotion_count": int(
            summary.get("transporter_target_blocked_for_promotion_count") or 0
        ),
        "transporter_target_ready_for_promotion_ids": list(
            summary.get("transporter_target_ready_for_promotion_ids") or []
        ),
        "transporter_target_blocked_for_promotion_ids": list(
            summary.get("transporter_target_blocked_for_promotion_ids") or []
        ),
        "transporter_primary_blocker_target_id": summary.get("transporter_primary_blocker_target_id", ""),
        "transporter_primary_blocker_packet_step": summary.get("transporter_primary_blocker_packet_step", ""),
        "transporter_primary_blocker_candidate_name": summary.get(
            "transporter_primary_blocker_candidate_name", ""
        ),
        "allowed_claim_scopes": list(summary.get("allowed_claim_scopes") or []),
        "blocked_claim_scopes": list(summary.get("blocked_claim_scopes") or []),
        "blocked_claim_scope_count": int(summary.get("blocked_claim_scope_count") or 0),
        "general_platform_claim_allowed": bool(summary.get("general_platform_claim_allowed") is True),
        "general_platform_claim_blocked": bool(summary.get("general_platform_claim_blocked") is True),
        "general_protein_ligand_platform_ready": bool(
            summary.get("general_protein_ligand_platform_ready") is True
        ),
        "scope_claim_boundary_detail": summary.get("scope_claim_boundary_detail", ""),
        "pxr_exact_review_intake_ready": bool(summary.get("pxr_exact_review_intake_ready") is True),
        "pxr_exact_review_template_row_count": int(summary.get("pxr_exact_review_template_row_count") or 0),
        "pxr_exact_review_next_review_completion_packet_ready": bool(
            summary.get("pxr_exact_review_next_review_completion_packet_ready") is True
        ),
        "pxr_exact_review_next_review_completion_packet": dict(
            summary.get("pxr_exact_review_next_review_completion_packet") or {}
        ),
        "pxr_exact_review_next_review_return_bundle_required_artifacts": list(
            summary.get("pxr_exact_review_next_review_return_bundle_required_artifacts") or []
        ),
        "pxr_exact_review_next_review_return_bundle_required_artifact_count": int(
            summary.get("pxr_exact_review_next_review_return_bundle_required_artifact_count") or 0
        ),
        "pxr_exact_review_next_review_return_bundle_completion_matrix": list(
            summary.get("pxr_exact_review_next_review_return_bundle_completion_matrix") or []
        ),
        "pxr_exact_review_next_review_return_bundle_completion_matrix_count": int(
            summary.get("pxr_exact_review_next_review_return_bundle_completion_matrix_count") or 0
        ),
        "pxr_exact_review_next_review_return_bundle_blocker_count": int(
            summary.get("pxr_exact_review_next_review_return_bundle_blocker_count") or 0
        ),
        "pxr_exact_review_next_review_return_bundle_next_artifact_id": summary.get(
            "pxr_exact_review_next_review_return_bundle_next_artifact_id", ""
        ),
        "pxr_exact_review_next_review_return_bundle_next_artifact_path": summary.get(
            "pxr_exact_review_next_review_return_bundle_next_artifact_path", ""
        ),
        "pxr_exact_review_next_review_return_bundle_next_artifact_failed_check_ids": list(
            summary.get("pxr_exact_review_next_review_return_bundle_next_artifact_failed_check_ids") or []
        ),
        "pxr_exact_review_next_review_row_id": summary.get("pxr_exact_review_next_review_row_id", ""),
        "pxr_exact_review_next_review_candidate_name": summary.get(
            "pxr_exact_review_next_review_candidate_name", ""
        ),
        "pxr_exact_review_next_review_operator_review_artifact": summary.get(
            "pxr_exact_review_next_review_operator_review_artifact", ""
        ),
        "pxr_source_modality_triage_ready": bool(
            summary.get("pxr_source_modality_triage_ready") is True
        ),
        "pxr_source_modality_triage_status": summary.get("pxr_source_modality_triage_status", ""),
        "pxr_source_modality_triage_artifact": summary.get("pxr_source_modality_triage_artifact", ""),
        "pxr_source_modality_triage_decision": summary.get("pxr_source_modality_triage_decision", ""),
        "pxr_source_modality_public_evidence_recheck_ready": bool(
            summary.get("pxr_source_modality_public_evidence_recheck_ready") is True
        ),
        "pxr_source_modality_public_recheck_artifact": summary.get(
            "pxr_source_modality_public_recheck_artifact", ""
        ),
        "pxr_source_modality_public_recheck_candidate_count": int(
            summary.get("pxr_source_modality_public_recheck_candidate_count") or 0
        ),
        "pxr_source_modality_public_recheck_chembl_direct_binding_total_record_count": int(
            summary.get("pxr_source_modality_public_recheck_chembl_direct_binding_total_record_count") or 0
        ),
        "pxr_source_modality_public_recheck_chembl_functional_activity_total_record_count": int(
            summary.get("pxr_source_modality_public_recheck_chembl_functional_activity_total_record_count") or 0
        ),
        "pxr_source_modality_public_recheck_bindingdb_pxr_like_total_record_count": int(
            summary.get("pxr_source_modality_public_recheck_bindingdb_pxr_like_total_record_count") or 0
        ),
        "pxr_source_modality_public_recheck_direct_or_claim_safe_binding_kcal_ready_count": int(
            summary.get("pxr_source_modality_public_recheck_direct_or_claim_safe_binding_kcal_ready_count") or 0
        ),
        "pxr_source_modality_public_recheck_all_candidates_remain_blocked": bool(
            summary.get("pxr_source_modality_public_recheck_all_candidates_remain_blocked") is True
        ),
        "pxr_source_modality_public_recheck_first_blocked_candidate_name": summary.get(
            "pxr_source_modality_public_recheck_first_blocked_candidate_name", ""
        ),
        "pxr_source_modality_public_recheck_first_blocked_reason": summary.get(
            "pxr_source_modality_public_recheck_first_blocked_reason", ""
        ),
        "pxr_source_modality_direct_replacement_candidate_packet_ready": bool(
            summary.get("pxr_source_modality_direct_replacement_candidate_packet_ready") is True
        ),
        "pxr_source_modality_direct_replacement_artifact": summary.get(
            "pxr_source_modality_direct_replacement_artifact", ""
        ),
        "pxr_source_modality_direct_replacement_candidate_count": int(
            summary.get("pxr_source_modality_direct_replacement_candidate_count") or 0
        ),
        "pxr_source_modality_direct_replacement_selected_candidate_count": int(
            summary.get("pxr_source_modality_direct_replacement_selected_candidate_count") or 0
        ),
        "pxr_source_modality_direct_replacement_selected_claim_safe_candidate_count": int(
            summary.get("pxr_source_modality_direct_replacement_selected_claim_safe_candidate_count") or 0
        ),
        "pxr_source_modality_direct_replacement_first_ligand_id": summary.get(
            "pxr_source_modality_direct_replacement_first_ligand_id", ""
        ),
        "pxr_source_modality_direct_replacement_first_molecule_chembl_id": summary.get(
            "pxr_source_modality_direct_replacement_first_molecule_chembl_id", ""
        ),
        "pxr_source_modality_direct_replacement_first_reference_binding_kcal_mol": summary.get(
            "pxr_source_modality_direct_replacement_first_reference_binding_kcal_mol", ""
        ),
        "pxr_source_modality_direct_replacement_first_source": summary.get(
            "pxr_source_modality_direct_replacement_first_source", ""
        ),
        "pxr_source_modality_direct_replacement_apply_draft_ready": bool(
            summary.get("pxr_source_modality_direct_replacement_apply_draft_ready") is True
        ),
        "pxr_source_modality_direct_replacement_apply_draft_status": summary.get(
            "pxr_source_modality_direct_replacement_apply_draft_status", ""
        ),
        "pxr_source_modality_direct_replacement_apply_draft_artifact": summary.get(
            "pxr_source_modality_direct_replacement_apply_draft_artifact", ""
        ),
        "pxr_source_modality_direct_replacement_apply_draft_workbook_row_count": int(
            summary.get("pxr_source_modality_direct_replacement_apply_draft_workbook_row_count") or 0
        ),
        "pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_before_draft": int(
            summary.get("pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_before_draft")
            or 0
        ),
        "pxr_source_modality_direct_replacement_apply_draft_overlay_row_count": int(
            summary.get("pxr_source_modality_direct_replacement_apply_draft_overlay_row_count") or 0
        ),
        "pxr_source_modality_direct_replacement_apply_draft_ready_for_apply_row_count_after_draft": int(
            summary.get(
                "pxr_source_modality_direct_replacement_apply_draft_ready_for_apply_row_count_after_draft"
            )
            or 0
        ),
        "pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_after_draft": int(
            summary.get("pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_after_draft")
            or 0
        ),
        "pxr_source_modality_direct_replacement_apply_draft_first_overlay_ligand_id": summary.get(
            "pxr_source_modality_direct_replacement_apply_draft_first_overlay_ligand_id", ""
        ),
        "pxr_source_modality_direct_replacement_apply_draft_authoritative_fields_touched": bool(
            summary.get("pxr_source_modality_direct_replacement_apply_draft_authoritative_fields_touched")
            is True
        ),
        "pxr_source_modality_activity_proxy_or_conflict_surrogate_row_count": int(
            summary.get("pxr_source_modality_activity_proxy_or_conflict_surrogate_row_count") or 0
        ),
        "pxr_source_modality_direct_or_claim_safe_quantitative_ready_count": int(
            summary.get("pxr_source_modality_direct_or_claim_safe_quantitative_ready_count") or 0
        ),
        "pxr_source_modality_accepted_for_scope_promotion_count": int(
            summary.get("pxr_source_modality_accepted_for_scope_promotion_count") or 0
        ),
        "pxr_source_modality_next_review_row_id": summary.get(
            "pxr_source_modality_next_review_row_id", ""
        ),
        "pxr_source_modality_next_review_candidate_name": summary.get(
            "pxr_source_modality_next_review_candidate_name", ""
        ),
        "pxr_source_modality_next_review_source_modality": summary.get(
            "pxr_source_modality_next_review_source_modality", ""
        ),
        "pxr_source_modality_next_review_rejection_reason": summary.get(
            "pxr_source_modality_next_review_rejection_reason", ""
        ),
        "scope_acceptance_matrix_ready": bool(summary.get("scope_acceptance_matrix_ready") is True),
        "scope_acceptance_stage_count": int(summary.get("scope_acceptance_stage_count") or 0),
        "scope_acceptance_ready_stage_count": int(summary.get("scope_acceptance_ready_stage_count") or 0),
        "scope_acceptance_blocked_stage_count": int(summary.get("scope_acceptance_blocked_stage_count") or 0),
        "scope_acceptance_stage_ids": list(summary.get("scope_acceptance_stage_ids") or []),
        "scope_acceptance_ready_stage_ids": list(summary.get("scope_acceptance_ready_stage_ids") or []),
        "scope_acceptance_blocked_stage_ids": list(summary.get("scope_acceptance_blocked_stage_ids") or []),
        "scope_acceptance_next_stage_id": summary.get("scope_acceptance_next_stage_id", ""),
        "scope_acceptance_next_stage_artifact": summary.get("scope_acceptance_next_stage_artifact", ""),
        "scope_acceptance_next_stage_validation_command": summary.get(
            "scope_acceptance_next_stage_validation_command", ""
        ),
        "scope_acceptance_next_stage_release_effect": summary.get(
            "scope_acceptance_next_stage_release_effect", ""
        ),
        "scope_acceptance_next_stage_unlock_claim_scopes": list(
            summary.get("scope_acceptance_next_stage_unlock_claim_scopes") or []
        ),
        "scope_acceptance_next_stage_required_checks": list(
            summary.get("scope_acceptance_next_stage_required_checks") or []
        ),
        "scope_acceptance_next_stage_next_action": summary.get(
            "scope_acceptance_next_stage_next_action", ""
        ),
        "scope_acceptance_stage_evidence_matrix": scope_acceptance_stage_evidence_matrix,
        "scope_acceptance_stage_evidence_matrix_count": int(
            summary.get("scope_acceptance_stage_evidence_matrix_count") or 0
        ),
        "scope_acceptance_current_blocked_stage_evidence_matrix": (
            scope_acceptance_current_blocked_stage_evidence_matrix
        ),
        "scope_acceptance_current_blocked_stage_evidence_matrix_count": int(
            summary.get("scope_acceptance_current_blocked_stage_evidence_matrix_count") or 0
        ),
        "domain_rows": rows,
        "scope_acceptance_matrix": scope_acceptance_matrix,
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "scope_widened_by_endpoint": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/scope-claim-guard")
async def get_product_scope_claim_guard() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_SCOPE_CLAIM_GUARD_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_product_scope_claim_guard",
            "artifact_path": str(PRODUCT_SCOPE_CLAIM_GUARD_ARTIFACT),
            "scope_breadth_ready": False,
            "closure_checklist_ready": False,
            "scope_promotion_allowed": False,
            "authoritative_apply_allowed": False,
            "allowed_scope_families": [],
            "allowed_scope_family_count": 0,
            "blocked_claim_scopes": ["product_scope_claim_guard_artifact_missing"],
            "blocked_claim_scope_count": 1,
            "claim_blocked_domains": [],
            "general_platform_claim_allowed": False,
            "ready_for_apply_count": 0,
            "authoritative_apply_allowed_count": 0,
            "checklist_row_count": 0,
            "manual_review_blocked_row_count": 0,
            "manual_review_subcheck_count": 0,
            "field_missing_row_count": 0,
            "first_scientific_blocker": "",
            "blocker_class_counts": {},
            "blocker_classes": [],
            "transporter_manual_review_subcheck_count": 0,
            "transporter_identity_scaffold_confirmation_required_count": 0,
            "transporter_direct_binding_or_kcal_confirmation_required_count": 0,
            "transporter_negative_quantitative_confirmation_required_count": 0,
            "transporter_direct_binding_missing_count": 0,
            "transporter_negative_quantitative_missing_count": 0,
            "transporter_candidate_ready_for_apply_count": 0,
            "pxr_reconciled_blocked_row_count": 0,
            "pxr_conflict_resolution_count": 0,
            "pxr_quantitative_missing_count": 0,
            "general_claim_blocker_count": 0,
            "general_claim_gate_blocker_count": 0,
            "claim_boundary_detail": "",
            "claim_boundary_matrix": [],
            "source_artifacts": [],
            "closure_items": [],
            "next_required_step": "Run python3 tools/build_product_scope_breadth_closure_checklist.py.",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "scope_widened": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product scope-claim-guard endpoint only; the local scope closure checklist artifact is missing. "
                "It does not acquire evidence, widen claims, run docking, promote scope, or mutate external state."
            ),
        }
    return {
        "artifact_path": str(PRODUCT_SCOPE_CLAIM_GUARD_ARTIFACT),
        "status": summary.get("status")
        or (
            "product_scope_breadth_closure_checklist_ready"
            if summary.get("closure_checklist_ready") is True
            else "blocked_product_scope_breadth_closure_checklist"
        ),
        "scope_breadth_ready": bool(summary.get("scope_breadth_ready") is True),
        "closure_checklist_ready": bool(summary.get("closure_checklist_ready") is True),
        "scope_promotion_allowed": bool(summary.get("scope_promotion_allowed") is True),
        "authoritative_apply_allowed": bool(summary.get("authoritative_apply_allowed") is True),
        "allowed_scope_families": list(summary.get("allowed_scope_families") or []),
        "allowed_scope_family_count": int(summary.get("allowed_scope_family_count") or 0),
        "blocked_claim_scopes": list(summary.get("blocked_claim_scopes") or []),
        "blocked_claim_scope_count": int(summary.get("blocked_claim_scope_count") or 0),
        "claim_blocked_domains": list(summary.get("claim_blocked_domains") or []),
        "general_platform_claim_allowed": bool(summary.get("general_platform_claim_allowed") is True),
        "ready_for_apply_count": int(summary.get("ready_for_apply_count") or 0),
        "authoritative_apply_allowed_count": int(summary.get("authoritative_apply_allowed_count") or 0),
        "checklist_row_count": int(summary.get("checklist_row_count") or 0),
        "manual_review_blocked_row_count": int(summary.get("manual_review_blocked_row_count") or 0),
        "manual_review_subcheck_count": int(summary.get("manual_review_subcheck_count") or 0),
        "field_missing_row_count": int(summary.get("field_missing_row_count") or 0),
        "first_scientific_blocker": summary.get("first_scientific_blocker", ""),
        "blocker_class_counts": (
            summary.get("blocker_class_counts") if isinstance(summary.get("blocker_class_counts"), dict) else {}
        ),
        "blocker_classes": list(summary.get("blocker_classes") or []),
        "transporter_manual_review_subcheck_count": int(
            summary.get("transporter_manual_review_subcheck_count") or 0
        ),
        "transporter_identity_scaffold_confirmation_required_count": int(
            summary.get("transporter_identity_scaffold_confirmation_required_count") or 0
        ),
        "transporter_direct_binding_or_kcal_confirmation_required_count": int(
            summary.get("transporter_direct_binding_or_kcal_confirmation_required_count") or 0
        ),
        "transporter_negative_quantitative_confirmation_required_count": int(
            summary.get("transporter_negative_quantitative_confirmation_required_count") or 0
        ),
        "transporter_direct_binding_missing_count": int(
            summary.get("transporter_direct_binding_missing_count") or 0
        ),
        "transporter_negative_quantitative_missing_count": int(
            summary.get("transporter_negative_quantitative_missing_count") or 0
        ),
        "transporter_candidate_ready_for_apply_count": int(
            summary.get("transporter_candidate_ready_for_apply_count") or 0
        ),
        "pxr_reconciled_blocked_row_count": int(summary.get("pxr_reconciled_blocked_row_count") or 0),
        "pxr_conflict_resolution_count": int(summary.get("pxr_conflict_resolution_count") or 0),
        "pxr_quantitative_missing_count": int(summary.get("pxr_quantitative_missing_count") or 0),
        "general_claim_blocker_count": int(summary.get("general_claim_blocker_count") or 0),
        "general_claim_gate_blocker_count": int(summary.get("general_claim_gate_blocker_count") or 0),
        "claim_boundary_detail": summary.get("claim_boundary_detail", ""),
        "claim_boundary_matrix": list(summary.get("claim_boundary_matrix") or []),
        "source_artifacts": list(summary.get("source_artifacts") or []),
        "closure_items": rows,
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "scope_widened": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/scope-evidence-priority")
async def get_product_scope_evidence_priority() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_SCOPE_EVIDENCE_PRIORITY_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_product_scope_evidence_priority",
            "artifact_path": str(PRODUCT_SCOPE_EVIDENCE_PRIORITY_ARTIFACT),
            "priority_packet_ready": False,
            "scope_promotion_allowed": False,
            "authoritative_apply_allowed": False,
            "queue_item_count": 0,
            "source_queue_item_count": 0,
            "open_item_count": 0,
            "scientific_evidence_request_count": 0,
            "local_crosscheck_candidate_count": 0,
            "external_primary_exact_evidence_required_count": 0,
            "review_only_keep_blocked_count": 0,
            "claim_gate_prerequisite_count": 0,
            "operator_packet_binding_ready_count": 0,
            "operator_packet_binding_missing_count": 0,
            "all_operator_packet_bindings_ready": False,
            "top_item_id": "",
            "top_required_evidence_type": "",
            "top_review_template_artifact": "",
            "top_apply_gate_artifact": "",
            "authoritative_apply_allowed_count": 0,
            "source_artifacts": [],
            "top_priority_items": [],
            "priority_items": [],
            "next_required_step": "Run python3 tools/build_product_scope_breadth_evidence_priority_packet.py.",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "scope_widened": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product scope-evidence-priority endpoint only; the local priority artifact is missing. "
                "It does not acquire evidence, widen scope, run docking, promote claims, or mutate external state."
            ),
        }
    sorted_rows = sorted(
        [row for row in rows if isinstance(row, dict)],
        key=lambda row: int(row.get("priority") or 999999),
    )
    return {
        "status": summary.get("status") or "product_scope_breadth_evidence_priority_packet_ready",
        "artifact_path": str(PRODUCT_SCOPE_EVIDENCE_PRIORITY_ARTIFACT),
        "priority_packet_ready": bool(summary.get("priority_packet_ready") is True),
        "scope_promotion_allowed": bool(summary.get("scope_promotion_allowed") is True),
        "authoritative_apply_allowed": bool(summary.get("authoritative_apply_allowed") is True),
        "queue_item_count": int(summary.get("queue_item_count") or 0),
        "source_queue_item_count": int(summary.get("source_queue_item_count") or 0),
        "open_item_count": int(summary.get("open_item_count") or 0),
        "scientific_evidence_request_count": int(summary.get("scientific_evidence_request_count") or 0),
        "local_crosscheck_candidate_count": int(summary.get("local_crosscheck_candidate_count") or 0),
        "external_primary_exact_evidence_required_count": int(
            summary.get("external_primary_exact_evidence_required_count") or 0
        ),
        "review_only_keep_blocked_count": int(summary.get("review_only_keep_blocked_count") or 0),
        "claim_gate_prerequisite_count": int(summary.get("claim_gate_prerequisite_count") or 0),
        "operator_packet_binding_ready_count": int(summary.get("operator_packet_binding_ready_count") or 0),
        "operator_packet_binding_missing_count": int(summary.get("operator_packet_binding_missing_count") or 0),
        "all_operator_packet_bindings_ready": bool(summary.get("all_operator_packet_bindings_ready") is True),
        "top_item_id": summary.get("top_item_id", ""),
        "top_required_evidence_type": summary.get("top_required_evidence_type", ""),
        "top_review_template_artifact": summary.get("top_review_template_artifact", ""),
        "top_apply_gate_artifact": summary.get("top_apply_gate_artifact", ""),
        "authoritative_apply_allowed_count": int(summary.get("authoritative_apply_allowed_count") or 0),
        "source_artifacts": list(summary.get("source_artifacts") or []),
        "top_priority_items": sorted_rows[:5],
        "priority_items": sorted_rows,
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "scope_widened": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/scope-evidence-intake-readiness")
async def get_product_scope_evidence_intake_readiness() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_SCOPE_EVIDENCE_INTAKE_READINESS_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_product_scope_evidence_intake_readiness",
            "artifact_path": str(PRODUCT_SCOPE_EVIDENCE_INTAKE_READINESS_ARTIFACT),
            "intake_readiness_ready": False,
            "scope_promotion_allowed": False,
            "authoritative_apply_allowed": False,
            "row_count": 0,
            "local_crosscheck_triage_item_count": 0,
            "local_crosscheck_intake_ready_count": 0,
            "external_exact_evidence_required_count": 0,
            "guardrail_item_count": 0,
            "operator_packet_binding_ready_count": 0,
            "operator_packet_binding_missing_count": 0,
            "all_operator_packet_bindings_ready": False,
            "top_unbound_item_id": "",
            "top_unbound_required_evidence_type": "",
            "next_operator_completion_item_id": "",
            "next_operator_completion_domain": "",
            "next_operator_completion_candidate_or_check": "",
            "next_operator_completion_intake_mode": "",
            "next_operator_completion_required_evidence_type": "",
            "next_operator_completion_required_intake_columns": [],
            "next_operator_completion_required_intake_column_count": 0,
            "next_operator_completion_review_template_artifact": "",
            "next_operator_completion_apply_gate_artifact": "",
            "next_operator_completion_regeneration_commands": "",
            "next_operator_completion_operator_packet_binding_key": "",
            "next_operator_completion_operator_packet_binding_ready": False,
            "next_operator_completion_transporter_claim_safe_blocker": "",
            "next_operator_completion_transporter_operator_next_verdict": "",
            "next_operator_completion_transporter_best_evidence_source_file": "",
            "next_operator_completion_transporter_best_evidence_activity_type": "",
            "next_operator_completion_transporter_best_evidence_value": "",
            "next_operator_completion_transporter_best_evidence_units": "",
            "next_operator_completion_transporter_best_evidence_document_id": "",
            "transporter_triage_packet_ready": False,
            "transporter_operator_review_evidence_matrix_ready": False,
            "transporter_claim_safe_local_evidence_ready_count": 0,
            "transporter_claim_safe_local_evidence_blocked_count": 0,
            "transporter_direct_binding_claim_blocked_count": 0,
            "transporter_negative_value_claim_blocked_count": 0,
            "transporter_top_claim_safe_blocker": "",
            "transporter_top_operator_next_verdict": "",
            "transporter_candidate_row_count": 0,
            "transporter_candidate_ready_for_manual_review_count": 0,
            "transporter_candidate_ready_for_apply_count": 0,
            "transporter_candidate_assignment_required_count": 0,
            "transporter_functional_quantitative_only_direct_gap_open_count": 0,
            "transporter_review_only_direct_binding_gap_count": 0,
            "transporter_manual_review_intake_ready": False,
            "transporter_manual_review_template_row_count": 0,
            "transporter_manual_review_direct_binding_evidence_required_count": 0,
            "transporter_manual_review_negative_quantitative_value_required_count": 0,
            "transporter_manual_review_decision_placeholder_count": 0,
            "first_review_row_id": "",
            "first_review_item_id": "",
            "first_review_target_id": "",
            "first_review_candidate_ligand_id": "",
            "first_review_replacement_source": "",
            "first_review_replacement_reference_binding_kcal_mol": "",
            "first_review_direct_binding_evidence_required": False,
            "first_review_direct_binding_source_url_or_doi": "",
            "first_review_negative_quantitative_value_required": False,
            "first_review_negative_reference_binding_kcal_mol": "",
            "first_review_review_decision": "",
            "first_review_authoritative_apply_requested": "",
            "first_review_manual_review_blockers": "",
            "first_review_review_requirements": "",
            "first_review_p0_slot_overlay_required_missing_fields": "",
            "first_review_p0_slot_overlay_claim_safe_step_ready": False,
            "first_review_p0_slot_overlay_authoritative_apply_allowed": False,
            "first_review_p0_slot_overlay_scope_promotion_allowed": False,
            "scope_operator_transfer_manifest_ready": False,
            "scope_operator_transfer_outbound_artifact_count": 0,
            "scope_operator_transfer_outbound_artifacts": [],
            "scope_operator_transfer_inbound_artifact_count": 0,
            "scope_operator_transfer_inbound_artifacts": [],
            "scope_operator_transfer_first_return_artifact": "",
            "scope_operator_transfer_acceptance_artifact": "",
            "scope_operator_transfer_acceptance_ready_key": "",
            "scope_operator_transfer_next_acceptance_stage": "",
            "scope_operator_transfer_post_return_validation_command": "",
            "source_artifacts": [],
            "intake_items": [],
            "next_required_step": "Run python3 tools/build_product_scope_breadth_evidence_intake_readiness.py.",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "scope_widened": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product scope evidence intake-readiness endpoint only; local artifact is missing. It does not accept "
                "evidence, authoritatively apply rows, widen API scope, run docking, promote claims, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status") or "product_scope_breadth_evidence_intake_readiness_ready",
        "artifact_path": str(PRODUCT_SCOPE_EVIDENCE_INTAKE_READINESS_ARTIFACT),
        "intake_readiness_ready": bool(summary.get("intake_readiness_ready") is True),
        "scope_promotion_allowed": bool(summary.get("scope_promotion_allowed") is True),
        "authoritative_apply_allowed": bool(summary.get("authoritative_apply_allowed") is True),
        "row_count": int(summary.get("row_count") or 0),
        "local_crosscheck_triage_item_count": int(summary.get("local_crosscheck_triage_item_count") or 0),
        "local_crosscheck_intake_ready_count": int(summary.get("local_crosscheck_intake_ready_count") or 0),
        "external_exact_evidence_required_count": int(summary.get("external_exact_evidence_required_count") or 0),
        "guardrail_item_count": int(summary.get("guardrail_item_count") or 0),
        "operator_packet_binding_ready_count": int(summary.get("operator_packet_binding_ready_count") or 0),
        "operator_packet_binding_missing_count": int(summary.get("operator_packet_binding_missing_count") or 0),
        "all_operator_packet_bindings_ready": bool(summary.get("all_operator_packet_bindings_ready") is True),
        "top_unbound_item_id": summary.get("top_unbound_item_id", ""),
        "top_unbound_required_evidence_type": summary.get("top_unbound_required_evidence_type", ""),
        "next_operator_completion_item_id": summary.get("next_operator_completion_item_id", ""),
        "next_operator_completion_domain": summary.get("next_operator_completion_domain", ""),
        "next_operator_completion_candidate_or_check": summary.get(
            "next_operator_completion_candidate_or_check", ""
        ),
        "next_operator_completion_intake_mode": summary.get("next_operator_completion_intake_mode", ""),
        "next_operator_completion_required_evidence_type": summary.get(
            "next_operator_completion_required_evidence_type", ""
        ),
        "next_operator_completion_required_intake_columns": list(
            summary.get("next_operator_completion_required_intake_columns") or []
        ),
        "next_operator_completion_required_intake_column_count": int(
            summary.get("next_operator_completion_required_intake_column_count") or 0
        ),
        "next_operator_completion_review_template_artifact": summary.get(
            "next_operator_completion_review_template_artifact", ""
        ),
        "next_operator_completion_apply_gate_artifact": summary.get(
            "next_operator_completion_apply_gate_artifact", ""
        ),
        "next_operator_completion_regeneration_commands": summary.get(
            "next_operator_completion_regeneration_commands", ""
        ),
        "next_operator_completion_operator_packet_binding_key": summary.get(
            "next_operator_completion_operator_packet_binding_key", ""
        ),
        "next_operator_completion_operator_packet_binding_ready": bool(
            summary.get("next_operator_completion_operator_packet_binding_ready") is True
        ),
        "next_operator_completion_transporter_claim_safe_blocker": summary.get(
            "next_operator_completion_transporter_claim_safe_blocker", ""
        ),
        "next_operator_completion_transporter_operator_next_verdict": summary.get(
            "next_operator_completion_transporter_operator_next_verdict", ""
        ),
        "next_operator_completion_transporter_best_evidence_source_file": summary.get(
            "next_operator_completion_transporter_best_evidence_source_file", ""
        ),
        "next_operator_completion_transporter_best_evidence_activity_type": summary.get(
            "next_operator_completion_transporter_best_evidence_activity_type", ""
        ),
        "next_operator_completion_transporter_best_evidence_value": summary.get(
            "next_operator_completion_transporter_best_evidence_value", ""
        ),
        "next_operator_completion_transporter_best_evidence_units": summary.get(
            "next_operator_completion_transporter_best_evidence_units", ""
        ),
        "next_operator_completion_transporter_best_evidence_document_id": summary.get(
            "next_operator_completion_transporter_best_evidence_document_id", ""
        ),
        "transporter_triage_packet_ready": bool(summary.get("transporter_triage_packet_ready") is True),
        "transporter_operator_review_evidence_matrix_ready": bool(
            summary.get("transporter_operator_review_evidence_matrix_ready") is True
        ),
        "transporter_claim_safe_local_evidence_ready_count": int(
            summary.get("transporter_claim_safe_local_evidence_ready_count") or 0
        ),
        "transporter_claim_safe_local_evidence_blocked_count": int(
            summary.get("transporter_claim_safe_local_evidence_blocked_count") or 0
        ),
        "transporter_direct_binding_claim_blocked_count": int(
            summary.get("transporter_direct_binding_claim_blocked_count") or 0
        ),
        "transporter_negative_value_claim_blocked_count": int(
            summary.get("transporter_negative_value_claim_blocked_count") or 0
        ),
        "transporter_top_claim_safe_blocker": summary.get("transporter_top_claim_safe_blocker", ""),
        "transporter_top_operator_next_verdict": summary.get("transporter_top_operator_next_verdict", ""),
        "transporter_candidate_row_count": int(summary.get("transporter_candidate_row_count") or 0),
        "transporter_candidate_ready_for_manual_review_count": int(
            summary.get("transporter_candidate_ready_for_manual_review_count") or 0
        ),
        "transporter_candidate_ready_for_apply_count": int(
            summary.get("transporter_candidate_ready_for_apply_count") or 0
        ),
        "transporter_candidate_assignment_required_count": int(
            summary.get("transporter_candidate_assignment_required_count") or 0
        ),
        "transporter_functional_quantitative_only_direct_gap_open_count": int(
            summary.get("transporter_functional_quantitative_only_direct_gap_open_count") or 0
        ),
        "transporter_review_only_direct_binding_gap_count": int(
            summary.get("transporter_review_only_direct_binding_gap_count") or 0
        ),
        "transporter_manual_review_intake_ready": bool(
            summary.get("transporter_manual_review_intake_ready") is True
        ),
        "transporter_manual_review_template_row_count": int(
            summary.get("transporter_manual_review_template_row_count") or 0
        ),
        "transporter_manual_review_direct_binding_evidence_required_count": int(
            summary.get("transporter_manual_review_direct_binding_evidence_required_count") or 0
        ),
        "transporter_manual_review_negative_quantitative_value_required_count": int(
            summary.get("transporter_manual_review_negative_quantitative_value_required_count") or 0
        ),
        "transporter_manual_review_decision_placeholder_count": int(
            summary.get("transporter_manual_review_decision_placeholder_count") or 0
        ),
        "first_review_row_id": summary.get("first_review_row_id", ""),
        "first_review_item_id": summary.get("first_review_item_id", ""),
        "first_review_target_id": summary.get("first_review_target_id", ""),
        "first_review_candidate_ligand_id": summary.get("first_review_candidate_ligand_id", ""),
        "first_review_replacement_source": summary.get("first_review_replacement_source", ""),
        "first_review_replacement_reference_binding_kcal_mol": summary.get(
            "first_review_replacement_reference_binding_kcal_mol", ""
        ),
        "first_review_direct_binding_evidence_required": bool(
            summary.get("first_review_direct_binding_evidence_required") is True
        ),
        "first_review_direct_binding_source_url_or_doi": summary.get(
            "first_review_direct_binding_source_url_or_doi", ""
        ),
        "first_review_negative_quantitative_value_required": bool(
            summary.get("first_review_negative_quantitative_value_required") is True
        ),
        "first_review_negative_reference_binding_kcal_mol": summary.get(
            "first_review_negative_reference_binding_kcal_mol", ""
        ),
        "first_review_review_decision": summary.get("first_review_review_decision", ""),
        "first_review_authoritative_apply_requested": summary.get(
            "first_review_authoritative_apply_requested", ""
        ),
        "first_review_manual_review_blockers": summary.get("first_review_manual_review_blockers", ""),
        "first_review_review_requirements": summary.get("first_review_review_requirements", ""),
        "first_review_p0_slot_overlay_required_missing_fields": summary.get(
            "first_review_p0_slot_overlay_required_missing_fields", ""
        ),
        "first_review_p0_slot_overlay_claim_safe_step_ready": bool(
            summary.get("first_review_p0_slot_overlay_claim_safe_step_ready") is True
        ),
        "first_review_p0_slot_overlay_authoritative_apply_allowed": bool(
            summary.get("first_review_p0_slot_overlay_authoritative_apply_allowed") is True
        ),
        "first_review_p0_slot_overlay_scope_promotion_allowed": bool(
            summary.get("first_review_p0_slot_overlay_scope_promotion_allowed") is True
        ),
        "scope_operator_transfer_manifest_ready": bool(
            summary.get("scope_operator_transfer_manifest_ready") is True
        ),
        "scope_operator_transfer_outbound_artifact_count": int(
            summary.get("scope_operator_transfer_outbound_artifact_count") or 0
        ),
        "scope_operator_transfer_outbound_artifacts": list(
            summary.get("scope_operator_transfer_outbound_artifacts") or []
        ),
        "scope_operator_transfer_inbound_artifact_count": int(
            summary.get("scope_operator_transfer_inbound_artifact_count") or 0
        ),
        "scope_operator_transfer_inbound_artifacts": list(
            summary.get("scope_operator_transfer_inbound_artifacts") or []
        ),
        "scope_operator_transfer_first_return_artifact": summary.get(
            "scope_operator_transfer_first_return_artifact", ""
        ),
        "scope_operator_transfer_acceptance_artifact": summary.get(
            "scope_operator_transfer_acceptance_artifact", ""
        ),
        "scope_operator_transfer_acceptance_ready_key": summary.get(
            "scope_operator_transfer_acceptance_ready_key", ""
        ),
        "scope_operator_transfer_next_acceptance_stage": summary.get(
            "scope_operator_transfer_next_acceptance_stage", ""
        ),
        "scope_operator_transfer_post_return_validation_command": summary.get(
            "scope_operator_transfer_post_return_validation_command", ""
        ),
        "transporter_manual_review_p0_slot_overlay_row_count": int(
            summary.get("transporter_manual_review_p0_slot_overlay_row_count") or 0
        ),
        "transporter_manual_review_p0_slot_overlay_candidate_changed_count": int(
            summary.get("transporter_manual_review_p0_slot_overlay_candidate_changed_count") or 0
        ),
        "transporter_manual_review_p0_slot_overlay_first_item_id": summary.get(
            "transporter_manual_review_p0_slot_overlay_first_item_id",
            "",
        ),
        "transporter_manual_review_p0_slot_overlay_first_candidate_ligand_id": summary.get(
            "transporter_manual_review_p0_slot_overlay_first_candidate_ligand_id",
            "",
        ),
        "transporter_manual_review_p0_slot_overlay_first_source": summary.get(
            "transporter_manual_review_p0_slot_overlay_first_source",
            "",
        ),
        "source_artifacts": list(summary.get("source_artifacts") or []),
        "intake_items": rows,
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "scope_widened": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/transporter-manual-review-intake")
async def get_product_transporter_manual_review_intake() -> dict[str, Any]:
    packet = _read_json_object(TRANSPORTER_MANUAL_REVIEW_INTAKE_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_transporter_manual_review_intake_template",
            "artifact_path": str(TRANSPORTER_MANUAL_REVIEW_INTAKE_ARTIFACT),
            "manual_review_intake_ready": False,
            "scope_promotion_allowed": False,
            "authoritative_apply_allowed": False,
            "manual_review_template_row_count": 0,
            "expected_manual_review_row_count": 0,
            "manual_review_row_count_matches_workbook": False,
            "manual_confirmation_required_count": 0,
            "direct_binding_evidence_required_count": 0,
            "negative_quantitative_value_required_count": 0,
            "review_decision_placeholder_count": 0,
            "authoritative_apply_requested_placeholder_count": 0,
            "p0_slot_overlay_row_count": 0,
            "p0_slot_overlay_candidate_changed_count": 0,
            "p0_slot_overlay_first_item_id": "",
            "p0_slot_overlay_first_candidate_ligand_id": "",
            "p0_slot_overlay_first_source": "",
            "p0_slot_overlay_claim_safe_step_ready_count": 0,
            "first_review_row_id": "",
            "first_review_item_id": "",
            "first_review_target_id": "",
            "first_review_candidate_ligand_id": "",
            "first_review_replacement_source": "",
            "first_review_replacement_reference_binding_kcal_mol": "",
            "first_review_direct_binding_evidence_required": False,
            "first_review_direct_binding_source_url_or_doi": "",
            "first_review_negative_quantitative_value_required": False,
            "first_review_negative_reference_binding_kcal_mol": "",
            "first_review_review_decision": "",
            "first_review_authoritative_apply_requested": "",
            "first_review_manual_review_blockers": "",
            "first_review_review_requirements": "",
            "first_review_p0_slot_overlay_required_missing_fields": "",
            "first_review_p0_slot_overlay_claim_safe_step_ready": False,
            "first_review_p0_slot_overlay_authoritative_apply_allowed": False,
            "first_review_p0_slot_overlay_scope_promotion_allowed": False,
            "candidate_workbook_ready": False,
            "candidate_workbook_row_count": 0,
            "unique_review_row_ids_ready": False,
            "review_rows": [],
            "next_required_step": "Run python3 tools/build_transporter_manual_review_intake_template.py.",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "scope_widened": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Transporter manual review endpoint only; local template artifact is missing. It does not write config "
                "CSVs, authoritatively apply rows, run docking, widen product scope, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status") or "transporter_manual_review_intake_template_ready",
        "artifact_path": str(TRANSPORTER_MANUAL_REVIEW_INTAKE_ARTIFACT),
        "manual_review_intake_ready": bool(summary.get("manual_review_intake_ready") is True),
        "scope_promotion_allowed": bool(summary.get("scope_promotion_allowed") is True),
        "authoritative_apply_allowed": bool(summary.get("authoritative_apply_allowed") is True),
        "manual_review_template_row_count": int(summary.get("manual_review_template_row_count") or 0),
        "expected_manual_review_row_count": int(summary.get("expected_manual_review_row_count") or 0),
        "manual_review_row_count_matches_workbook": bool(
            summary.get("manual_review_row_count_matches_workbook") is True
        ),
        "manual_confirmation_required_count": int(summary.get("manual_confirmation_required_count") or 0),
        "direct_binding_evidence_required_count": int(summary.get("direct_binding_evidence_required_count") or 0),
        "negative_quantitative_value_required_count": int(
            summary.get("negative_quantitative_value_required_count") or 0
        ),
        "review_decision_placeholder_count": int(summary.get("review_decision_placeholder_count") or 0),
        "authoritative_apply_requested_placeholder_count": int(
            summary.get("authoritative_apply_requested_placeholder_count") or 0
        ),
        "p0_slot_overlay_row_count": int(summary.get("p0_slot_overlay_row_count") or 0),
        "p0_slot_overlay_candidate_changed_count": int(
            summary.get("p0_slot_overlay_candidate_changed_count") or 0
        ),
        "p0_slot_overlay_first_item_id": summary.get("p0_slot_overlay_first_item_id", ""),
        "p0_slot_overlay_first_candidate_ligand_id": summary.get(
            "p0_slot_overlay_first_candidate_ligand_id",
            "",
        ),
        "p0_slot_overlay_first_source": summary.get("p0_slot_overlay_first_source", ""),
        "p0_slot_overlay_claim_safe_step_ready_count": int(
            summary.get("p0_slot_overlay_claim_safe_step_ready_count") or 0
        ),
        "first_review_row_id": summary.get("first_review_row_id", ""),
        "first_review_item_id": summary.get("first_review_item_id", ""),
        "first_review_target_id": summary.get("first_review_target_id", ""),
        "first_review_candidate_ligand_id": summary.get("first_review_candidate_ligand_id", ""),
        "first_review_replacement_source": summary.get("first_review_replacement_source", ""),
        "first_review_replacement_reference_binding_kcal_mol": summary.get(
            "first_review_replacement_reference_binding_kcal_mol", ""
        ),
        "first_review_direct_binding_evidence_required": bool(
            summary.get("first_review_direct_binding_evidence_required") is True
        ),
        "first_review_direct_binding_source_url_or_doi": summary.get(
            "first_review_direct_binding_source_url_or_doi", ""
        ),
        "first_review_negative_quantitative_value_required": bool(
            summary.get("first_review_negative_quantitative_value_required") is True
        ),
        "first_review_negative_reference_binding_kcal_mol": summary.get(
            "first_review_negative_reference_binding_kcal_mol", ""
        ),
        "first_review_review_decision": summary.get("first_review_review_decision", ""),
        "first_review_authoritative_apply_requested": summary.get(
            "first_review_authoritative_apply_requested", ""
        ),
        "first_review_manual_review_blockers": summary.get("first_review_manual_review_blockers", ""),
        "first_review_review_requirements": summary.get("first_review_review_requirements", ""),
        "first_review_p0_slot_overlay_required_missing_fields": summary.get(
            "first_review_p0_slot_overlay_required_missing_fields", ""
        ),
        "first_review_p0_slot_overlay_claim_safe_step_ready": bool(
            summary.get("first_review_p0_slot_overlay_claim_safe_step_ready") is True
        ),
        "first_review_p0_slot_overlay_authoritative_apply_allowed": bool(
            summary.get("first_review_p0_slot_overlay_authoritative_apply_allowed") is True
        ),
        "first_review_p0_slot_overlay_scope_promotion_allowed": bool(
            summary.get("first_review_p0_slot_overlay_scope_promotion_allowed") is True
        ),
        "candidate_workbook_ready": bool(summary.get("candidate_workbook_ready") is True),
        "candidate_workbook_row_count": int(summary.get("candidate_workbook_row_count") or 0),
        "unique_review_row_ids_ready": bool(summary.get("unique_review_row_ids_ready") is True),
        "review_rows": rows,
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "scope_widened": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/pxr-exact-review-intake")
async def get_product_pxr_exact_review_intake() -> dict[str, Any]:
    packet = _read_json_object(PXR_EXACT_REVIEW_INTAKE_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_pxr_exact_evidence_review_intake_template",
            "artifact_path": str(PXR_EXACT_REVIEW_INTAKE_ARTIFACT),
            "pxr_exact_review_intake_ready": False,
            "scope_promotion_allowed": False,
            "authoritative_apply_allowed": False,
            "review_template_row_count": 0,
            "expected_blocked_row_count": 0,
            "review_row_count_matches_reconciliation": False,
            "binder_review_row_count": 0,
            "non_binder_review_row_count": 0,
            "conflict_resolution_required_count": 0,
            "kcal_placeholder_count": 0,
            "source_placeholder_count": 0,
            "target_match_placeholder_count": 0,
            "review_decision_placeholder_count": 0,
            "next_review_completion_packet_ready": False,
            "next_review_completion_packet": {},
            "next_review_return_bundle_required_artifacts": [],
            "next_review_return_bundle_required_artifact_count": 0,
            "next_review_return_bundle_completion_matrix": [],
            "next_review_return_bundle_completion_matrix_count": 0,
            "next_review_return_bundle_blocker_count": 0,
            "next_review_return_bundle_next_artifact_id": "",
            "next_review_return_bundle_next_artifact_path": "",
            "next_review_return_bundle_next_artifact_failed_check_ids": [],
            "next_review_row_id": "",
            "next_review_candidate_name": "",
            "next_review_packet_step": "",
            "next_review_required_evidence_mode": "",
            "next_review_operator_review_artifact": "",
            "reconciliation_packet_ready": False,
            "reconciliation_artifact": "",
            "unique_review_row_ids_ready": False,
            "review_rows": [],
            "next_required_step": "Run python3 tools/build_pxr_exact_evidence_review_intake_template.py.",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "scope_widened": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "PXR exact review endpoint only; local template artifact is missing. It does not authoritatively apply "
                "rows, promote PXR scope, run docking, upload, submit, email, delete, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status") or "pxr_exact_evidence_review_intake_template_ready",
        "artifact_path": str(PXR_EXACT_REVIEW_INTAKE_ARTIFACT),
        "pxr_exact_review_intake_ready": bool(summary.get("pxr_exact_review_intake_ready") is True),
        "scope_promotion_allowed": bool(summary.get("scope_promotion_allowed") is True),
        "authoritative_apply_allowed": bool(summary.get("authoritative_apply_allowed") is True),
        "review_template_row_count": int(summary.get("review_template_row_count") or 0),
        "expected_blocked_row_count": int(summary.get("expected_blocked_row_count") or 0),
        "review_row_count_matches_reconciliation": bool(
            summary.get("review_row_count_matches_reconciliation") is True
        ),
        "binder_review_row_count": int(summary.get("binder_review_row_count") or 0),
        "non_binder_review_row_count": int(summary.get("non_binder_review_row_count") or 0),
        "conflict_resolution_required_count": int(summary.get("conflict_resolution_required_count") or 0),
        "kcal_placeholder_count": int(summary.get("kcal_placeholder_count") or 0),
        "source_placeholder_count": int(summary.get("source_placeholder_count") or 0),
        "target_match_placeholder_count": int(summary.get("target_match_placeholder_count") or 0),
        "review_decision_placeholder_count": int(summary.get("review_decision_placeholder_count") or 0),
        "next_review_completion_packet_ready": bool(
            summary.get("next_review_completion_packet_ready") is True
        ),
        "next_review_completion_packet": dict(summary.get("next_review_completion_packet") or {}),
        "next_review_return_bundle_required_artifacts": list(
            summary.get("next_review_return_bundle_required_artifacts") or []
        ),
        "next_review_return_bundle_required_artifact_count": int(
            summary.get("next_review_return_bundle_required_artifact_count") or 0
        ),
        "next_review_return_bundle_completion_matrix": list(
            summary.get("next_review_return_bundle_completion_matrix") or []
        ),
        "next_review_return_bundle_completion_matrix_count": int(
            summary.get("next_review_return_bundle_completion_matrix_count") or 0
        ),
        "next_review_return_bundle_blocker_count": int(
            summary.get("next_review_return_bundle_blocker_count") or 0
        ),
        "next_review_return_bundle_next_artifact_id": summary.get(
            "next_review_return_bundle_next_artifact_id", ""
        ),
        "next_review_return_bundle_next_artifact_path": summary.get(
            "next_review_return_bundle_next_artifact_path", ""
        ),
        "next_review_return_bundle_next_artifact_failed_check_ids": list(
            summary.get("next_review_return_bundle_next_artifact_failed_check_ids") or []
        ),
        "next_review_row_id": summary.get("next_review_row_id", ""),
        "next_review_candidate_name": summary.get("next_review_candidate_name", ""),
        "next_review_packet_step": summary.get("next_review_packet_step", ""),
        "next_review_required_evidence_mode": summary.get("next_review_required_evidence_mode", ""),
        "next_review_operator_review_artifact": summary.get("next_review_operator_review_artifact", ""),
        "reconciliation_packet_ready": bool(summary.get("reconciliation_packet_ready") is True),
        "reconciliation_artifact": summary.get("reconciliation_artifact", ""),
        "unique_review_row_ids_ready": bool(summary.get("unique_review_row_ids_ready") is True),
        "review_rows": rows,
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "scope_widened": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/aqp1-operator-validation-candidate")
async def get_product_aqp1_operator_validation_candidate() -> dict[str, Any]:
    packet = _read_json_object(AQP1_OPERATOR_VALIDATION_CANDIDATE_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_aqp1_operator_validation_candidate_packet",
            "artifact_path": str(AQP1_OPERATOR_VALIDATION_CANDIDATE_ARTIFACT),
            "packet_ready": False,
            "candidate_ready": False,
            "candidate_count": 0,
            "candidate_claim_safe_ready_count": 0,
            "operator_validation_required_count": 0,
            "operator_placeholder_count": 0,
            "required_operator_decision_fields": [],
            "required_operator_decision_field_count": 0,
            "validation_blockers": ["missing_aqp1_operator_validation_candidate_packet"],
            "validation_blocker_count": 1,
            "first_candidate_id": "",
            "first_candidate_target_id": "",
            "first_candidate_target_uniprot": "",
            "first_candidate_ligand_external_identifier": "",
            "first_candidate_ligand_name": "",
            "first_candidate_activity_id": "",
            "first_candidate_standard_type": "",
            "first_candidate_standard_value_nM": "",
            "first_candidate_reference_binding_kcal_mol": "",
            "first_candidate_blocker": "",
            "first_candidate_claim_safe_ready": False,
            "first_candidate_source_locator": "",
            "return_bundle_required_artifacts": [],
            "return_bundle_required_artifact_count": 0,
            "post_return_validation_commands": [],
            "post_return_validation_command_count": 0,
            "rows": [],
            "blockers": [{"code": "missing_aqp1_operator_validation_candidate_packet"}],
            "next_required_step": "Run python3 tools/build_aqp1_operator_validation_candidate_packet.py.",
            "claim_promotion_allowed": False,
            "authoritative_apply_allowed": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "scope_widened": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "AQP1 operator-validation candidate endpoint only; local packet artifact is missing. It does not "
                "approve claim-safe binding kcal, promote transporter scope, run docking, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status") or "aqp1_operator_validation_candidate_packet_ready",
        "artifact_path": str(AQP1_OPERATOR_VALIDATION_CANDIDATE_ARTIFACT),
        "packet_ready": bool(summary.get("packet_ready") is True),
        "candidate_ready": bool(summary.get("candidate_ready") is True),
        "candidate_count": int(summary.get("candidate_count") or 0),
        "candidate_claim_safe_ready_count": int(summary.get("candidate_claim_safe_ready_count") or 0),
        "operator_validation_required_count": int(summary.get("operator_validation_required_count") or 0),
        "operator_placeholder_count": int(summary.get("operator_placeholder_count") or 0),
        "required_operator_decision_fields": list(summary.get("required_operator_decision_fields") or []),
        "required_operator_decision_field_count": int(
            summary.get("required_operator_decision_field_count") or 0
        ),
        "validation_blockers": list(summary.get("validation_blockers") or []),
        "validation_blocker_count": int(summary.get("validation_blocker_count") or 0),
        "first_candidate_id": summary.get("first_candidate_id", ""),
        "first_candidate_target_id": summary.get("first_candidate_target_id", ""),
        "first_candidate_target_uniprot": summary.get("first_candidate_target_uniprot", ""),
        "first_candidate_ligand_external_identifier": summary.get(
            "first_candidate_ligand_external_identifier", ""
        ),
        "first_candidate_ligand_name": summary.get("first_candidate_ligand_name", ""),
        "first_candidate_activity_id": summary.get("first_candidate_activity_id", ""),
        "first_candidate_standard_type": summary.get("first_candidate_standard_type", ""),
        "first_candidate_standard_value_nM": summary.get("first_candidate_standard_value_nM", ""),
        "first_candidate_reference_binding_kcal_mol": summary.get(
            "first_candidate_reference_binding_kcal_mol", ""
        ),
        "first_candidate_blocker": summary.get("first_candidate_blocker", ""),
        "first_candidate_claim_safe_ready": bool(summary.get("first_candidate_claim_safe_ready") is True),
        "first_candidate_source_locator": summary.get("first_candidate_source_locator", ""),
        "return_bundle_required_artifacts": list(summary.get("return_bundle_required_artifacts") or []),
        "return_bundle_required_artifact_count": int(
            summary.get("return_bundle_required_artifact_count") or 0
        ),
        "post_return_validation_commands": list(summary.get("post_return_validation_commands") or []),
        "post_return_validation_command_count": int(
            summary.get("post_return_validation_command_count") or 0
        ),
        "rows": list(rows),
        "blockers": list(blockers),
        "next_required_step": summary.get("next_required_step", ""),
        "claim_promotion_allowed": False,
        "authoritative_apply_allowed": False,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "scope_widened": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/aqp1-direct-binding-procurement-packet")
async def get_product_aqp1_direct_binding_procurement_packet() -> dict[str, Any]:
    packet = _read_json_object(AQP1_DIRECT_BINDING_PROCUREMENT_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_aqp1_direct_binding_procurement_packet",
            "artifact_path": str(AQP1_DIRECT_BINDING_PROCUREMENT_ARTIFACT),
            "procurement_packet_ready": False,
            "target_id": "",
            "target_uniprot": "",
            "current_direct_experimental_binding_row_count": 0,
            "current_claim_safe_binding_kcal_ready_count": 0,
            "direct_binding_gap_open": True,
            "public_direct_binding_recheck_ready": False,
            "public_direct_binding_recheck_result": "",
            "current_operator_candidate_id": "",
            "current_operator_candidate_ligand_external_identifier": "",
            "current_operator_candidate_reference_binding_kcal_mol": "",
            "current_operator_candidate_blocker": "",
            "current_operator_candidate_claim_safe_ready": False,
            "external_primary_evidence_required": True,
            "accepted_direct_binding_methods": [],
            "acceptance_fields": [],
            "acceptance_field_count": 0,
            "minimum_acceptance_rule": "",
            "first_required_external_action_id": "",
            "post_return_validation_commands": [],
            "post_return_validation_command_count": 0,
            "rows": [],
            "blockers": [{"code": "missing_aqp1_direct_binding_procurement_packet"}],
            "next_required_step": "Run python3 tools/build_aqp1_direct_binding_procurement_packet.py.",
            "claim_promotion_allowed": False,
            "authoritative_apply_allowed": False,
            "execution_enabled": False,
            "docking_results_emitted": False,
            "scope_widened": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "AQP1 direct-binding procurement endpoint only; local packet artifact is missing. It does not "
                "approve claim-safe binding kcal, promote transporter scope, run docking, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status") or "aqp1_direct_binding_procurement_packet_ready",
        "artifact_path": str(AQP1_DIRECT_BINDING_PROCUREMENT_ARTIFACT),
        "procurement_packet_ready": bool(summary.get("procurement_packet_ready") is True),
        "target_id": summary.get("target_id", ""),
        "target_uniprot": summary.get("target_uniprot", ""),
        "current_direct_experimental_binding_row_count": int(
            summary.get("current_direct_experimental_binding_row_count") or 0
        ),
        "current_claim_safe_binding_kcal_ready_count": int(
            summary.get("current_claim_safe_binding_kcal_ready_count") or 0
        ),
        "direct_binding_gap_open": bool(summary.get("direct_binding_gap_open") is True),
        "public_direct_binding_recheck_ready": bool(
            summary.get("public_direct_binding_recheck_ready") is True
        ),
        "public_direct_binding_recheck_result": summary.get("public_direct_binding_recheck_result", ""),
        "current_operator_candidate_id": summary.get("current_operator_candidate_id", ""),
        "current_operator_candidate_ligand_external_identifier": summary.get(
            "current_operator_candidate_ligand_external_identifier", ""
        ),
        "current_operator_candidate_reference_binding_kcal_mol": summary.get(
            "current_operator_candidate_reference_binding_kcal_mol", ""
        ),
        "current_operator_candidate_blocker": summary.get("current_operator_candidate_blocker", ""),
        "current_operator_candidate_claim_safe_ready": bool(
            summary.get("current_operator_candidate_claim_safe_ready") is True
        ),
        "external_primary_evidence_required": bool(
            summary.get("external_primary_evidence_required") is True
        ),
        "accepted_direct_binding_methods": list(summary.get("accepted_direct_binding_methods") or []),
        "acceptance_fields": list(summary.get("acceptance_fields") or []),
        "acceptance_field_count": int(summary.get("acceptance_field_count") or 0),
        "minimum_acceptance_rule": summary.get("minimum_acceptance_rule", ""),
        "first_required_external_action_id": summary.get("first_required_external_action_id", ""),
        "post_return_validation_commands": list(summary.get("post_return_validation_commands") or []),
        "post_return_validation_command_count": int(
            summary.get("post_return_validation_command_count") or 0
        ),
        "rows": list(rows),
        "blockers": list(blockers),
        "next_required_step": summary.get("next_required_step", ""),
        "claim_promotion_allowed": False,
        "authoritative_apply_allowed": False,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "scope_widened": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/commercial-readiness-operator-packet")
async def get_product_commercial_readiness_operator_packet() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_COMMERCIAL_READINESS_OPERATOR_PACKET_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    operator_packets = (
        packet.get("operator_completion_packets")
        if isinstance(packet.get("operator_completion_packets"), list)
        else []
    )
    if not summary:
        return {
            "status": "missing_product_commercial_readiness_operator_packet",
            "artifact_path": str(PRODUCT_COMMERCIAL_READINESS_OPERATOR_PACKET_ARTIFACT),
            "packet_ready": False,
            "goal_audit_artifact": "",
            "goal_audit_sha256": "",
            "commercial_readiness_matrix_sha256": "",
            "source_fingerprint_ready": False,
            "goal_complete": False,
            "open_gap_ids": [],
            "action_count": 0,
            "blocked_action_count": 0,
            "ready_action_count": 0,
            "parallelizable_action_count": 0,
            "parallelizable_action_ids": [],
            "first_parallelizable_action_id": "",
            "first_parallelizable_action_artifact": "",
            "first_parallelizable_action_next_action": "",
            "first_parallelizable_action_validation_command": "",
            "first_parallelizable_action_required_operator_inputs": "",
            "first_parallelizable_action_required_exact_evidence_fields": "",
            "first_parallelizable_action_required_claim_guardrails": "",
            "first_parallelizable_action_expected_evidence_type": "",
            "first_parallelizable_action_required_missing_fields": "",
            "first_parallelizable_action_operator_review_artifact": "",
            "first_parallelizable_action_post_intake_synchronization_targets": "",
            "first_parallelizable_action_acceptance_gate_commands": "",
            **_commercial_first_parallelizable_source_modality_fields(summary),
            "first_parallelizable_action_lane_id": "",
            "first_parallelizable_action_precondition": "",
            "first_action_id": "",
            "first_artifact": "",
            "first_execution_command": "",
            "first_validation_command": "",
            **_commercial_first_worker_runtime_receipt_fields(summary),
            **_commercial_production_ai_registry_promotion_fields(summary),
            **_commercial_production_ai_return_fields(summary),
            **_commercial_delta_force_closure_fields(summary),
            **_commercial_scope_closure_fields(summary),
            **_commercial_engine_refinement_claim_fields(summary),
            **_commercial_scope_breadth_evidence_receipt_fields(summary),
            "operator_input_total_count": 0,
            "operator_completion_packet_ready_count": 0,
            "release_blocker_action_ids": [],
            "actions": [],
            "operator_completion_packets": [],
            "next_required_step": "",
            "execution_enabled": False,
            "external_state_mutated": False,
            "docking_results_emitted": False,
            "scope_widened": False,
            "checkpoint_promoted": False,
            "claim_boundary": (
                "Product commercial-readiness operator-packet endpoint only; the local handoff packet artifact is "
                "missing or invalid. It does not run docking, run GPU jobs, fill evidence, promote checkpoints, "
                "widen claims, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_COMMERCIAL_READINESS_OPERATOR_PACKET_ARTIFACT),
        "packet_ready": bool(summary.get("packet_ready") is True),
        "goal_audit_artifact": summary.get("goal_audit_artifact", ""),
        "goal_audit_sha256": summary.get("goal_audit_sha256", ""),
        "commercial_readiness_matrix_sha256": summary.get("commercial_readiness_matrix_sha256", ""),
        "source_fingerprint_ready": bool(summary.get("source_fingerprint_ready") is True),
        "goal_complete": bool(summary.get("goal_complete") is True),
        "open_gap_ids": list(summary.get("open_gap_ids") or []),
        "action_count": int(summary.get("action_count") or 0),
        "blocked_action_count": int(summary.get("blocked_action_count") or 0),
        "ready_action_count": int(summary.get("ready_action_count") or 0),
        "parallelizable_action_count": int(summary.get("parallelizable_action_count") or 0),
        "parallelizable_action_ids": list(summary.get("parallelizable_action_ids") or []),
        "first_parallelizable_action_id": summary.get("first_parallelizable_action_id", ""),
        "first_parallelizable_action_artifact": summary.get("first_parallelizable_action_artifact", ""),
        "first_parallelizable_action_next_action": summary.get(
            "first_parallelizable_action_next_action", ""
        ),
        "first_parallelizable_action_validation_command": summary.get(
            "first_parallelizable_action_validation_command", ""
        ),
        "first_parallelizable_action_required_operator_inputs": summary.get(
            "first_parallelizable_action_required_operator_inputs", ""
        ),
        "first_parallelizable_action_required_exact_evidence_fields": summary.get(
            "first_parallelizable_action_required_exact_evidence_fields", ""
        ),
        "first_parallelizable_action_required_claim_guardrails": summary.get(
            "first_parallelizable_action_required_claim_guardrails", ""
        ),
        "first_parallelizable_action_expected_evidence_type": summary.get(
            "first_parallelizable_action_expected_evidence_type", ""
        ),
        "first_parallelizable_action_required_missing_fields": summary.get(
            "first_parallelizable_action_required_missing_fields", ""
        ),
        "first_parallelizable_action_operator_review_artifact": summary.get(
            "first_parallelizable_action_operator_review_artifact", ""
        ),
        "first_parallelizable_action_post_intake_synchronization_targets": summary.get(
            "first_parallelizable_action_post_intake_synchronization_targets", ""
        ),
        "first_parallelizable_action_acceptance_gate_commands": summary.get(
            "first_parallelizable_action_acceptance_gate_commands", ""
        ),
        **_commercial_first_parallelizable_source_modality_fields(summary),
        "first_parallelizable_action_lane_id": summary.get("first_parallelizable_action_lane_id", ""),
        "first_parallelizable_action_precondition": summary.get(
            "first_parallelizable_action_precondition", ""
        ),
        "first_action_id": summary.get("first_action_id", ""),
        "first_artifact": summary.get("first_artifact", ""),
        "first_execution_command": summary.get("first_execution_command", ""),
        "first_validation_command": summary.get("first_validation_command", ""),
        **_commercial_first_worker_runtime_receipt_fields(summary),
        **_commercial_production_ai_registry_promotion_fields(summary),
        **_commercial_production_ai_return_fields(summary),
        **_commercial_delta_force_closure_fields(summary),
        **_commercial_scope_closure_fields(summary),
        **_commercial_engine_refinement_claim_fields(summary),
        **_commercial_scope_breadth_evidence_receipt_fields(summary),
        "operator_input_total_count": int(summary.get("operator_input_total_count") or 0),
        "operator_completion_packet_ready_count": int(
            summary.get("operator_completion_packet_ready_count") or 0
        ),
        "release_blocker_action_ids": list(summary.get("release_blocker_action_ids") or []),
        "actions": list(rows),
        "operator_completion_packets": list(operator_packets),
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "external_state_mutated": False,
        "docking_results_emitted": False,
        "scope_widened": False,
        "checkpoint_promoted": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/commercial-readiness-operator-packet-freshness")
async def get_product_commercial_readiness_operator_packet_freshness() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_COMMERCIAL_READINESS_OPERATOR_PACKET_FRESHNESS_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_product_commercial_readiness_operator_packet_freshness",
            "artifact_path": str(PRODUCT_COMMERCIAL_READINESS_OPERATOR_PACKET_FRESHNESS_ARTIFACT),
            "freshness_ready": False,
            "goal_complete": False,
            "goal_audit_artifact": "",
            "operator_packet_artifact": "",
            "current_goal_audit_sha256": "",
            "operator_goal_audit_sha256": "",
            "current_commercial_readiness_matrix_sha256": "",
            "operator_commercial_readiness_matrix_sha256": "",
            "current_action_count": 0,
            "operator_action_count": 0,
            "current_blocked_action_count": 0,
            "operator_blocked_action_count": 0,
            "current_first_action_id": "",
            "operator_first_action_id": "",
            "command_references_ready": False,
            "operator_python_tool_reference_count": 0,
            "operator_missing_python_tool_reference_count": 0,
            "operator_python_tool_references": [],
            "operator_missing_python_tool_references": [],
            "check_count": 0,
            "pass_count": 0,
            "fail_count": 1,
            "failed_check_ids": ["missing_product_commercial_readiness_operator_packet_freshness"],
            "checks": [],
            "blockers": [],
            "next_required_step": "",
            "execution_enabled": False,
            "external_state_mutated": False,
            "docking_results_emitted": False,
            "scope_widened": False,
            "checkpoint_promoted": False,
            "claim_boundary": (
                "Product commercial-readiness operator-packet freshness endpoint only; the local freshness artifact "
                "is missing or invalid. It does not run docking, run GPU jobs, fill evidence, promote checkpoints, "
                "widen claims, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_COMMERCIAL_READINESS_OPERATOR_PACKET_FRESHNESS_ARTIFACT),
        "freshness_ready": bool(summary.get("freshness_ready") is True),
        "goal_complete": bool(summary.get("goal_complete") is True),
        "goal_audit_artifact": summary.get("goal_audit_artifact", ""),
        "operator_packet_artifact": summary.get("operator_packet_artifact", ""),
        "current_goal_audit_sha256": summary.get("current_goal_audit_sha256", ""),
        "operator_goal_audit_sha256": summary.get("operator_goal_audit_sha256", ""),
        "current_commercial_readiness_matrix_sha256": summary.get(
            "current_commercial_readiness_matrix_sha256", ""
        ),
        "operator_commercial_readiness_matrix_sha256": summary.get(
            "operator_commercial_readiness_matrix_sha256", ""
        ),
        "current_action_count": int(summary.get("current_action_count") or 0),
        "operator_action_count": int(summary.get("operator_action_count") or 0),
        "current_blocked_action_count": int(summary.get("current_blocked_action_count") or 0),
        "operator_blocked_action_count": int(summary.get("operator_blocked_action_count") or 0),
        "current_first_action_id": summary.get("current_first_action_id", ""),
        "operator_first_action_id": summary.get("operator_first_action_id", ""),
        "command_references_ready": bool(summary.get("command_references_ready") is True),
        "operator_python_tool_reference_count": int(
            summary.get("operator_python_tool_reference_count") or 0
        ),
        "operator_missing_python_tool_reference_count": int(
            summary.get("operator_missing_python_tool_reference_count") or 0
        ),
        "operator_python_tool_references": list(summary.get("operator_python_tool_references") or []),
        "operator_missing_python_tool_references": list(
            summary.get("operator_missing_python_tool_references") or []
        ),
        "check_count": int(summary.get("check_count") or 0),
        "pass_count": int(summary.get("pass_count") or 0),
        "fail_count": int(summary.get("fail_count") or 0),
        "failed_check_ids": list(summary.get("failed_check_ids") or []),
        "checks": list(rows),
        "blockers": list(blockers),
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "external_state_mutated": False,
        "docking_results_emitted": False,
        "scope_widened": False,
        "checkpoint_promoted": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/commercial-readiness-execution-ladder")
async def get_product_commercial_readiness_execution_ladder() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_COMMERCIAL_READINESS_EXECUTION_LADDER_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_product_commercial_readiness_execution_ladder",
            "artifact_path": str(PRODUCT_COMMERCIAL_READINESS_EXECUTION_LADDER_ARTIFACT),
            "ladder_ready": False,
            "operator_packet_artifact": "",
            "freshness_artifact": "",
            "operator_packet_ready": False,
            "freshness_ready": False,
            "goal_complete": False,
            "action_count": 0,
            "blocked_action_count": 0,
            "parallelizable_action_count": 0,
            "parallelizable_action_ids": [],
            "first_parallelizable_action_id": "",
            "first_parallelizable_action_order": 0,
            "first_parallelizable_action_artifact": "",
            "first_parallelizable_action_next_action": "",
            "first_parallelizable_action_validation_command": "",
            "first_parallelizable_action_required_operator_inputs": "",
            "first_parallelizable_action_required_exact_evidence_fields": "",
            "first_parallelizable_action_required_claim_guardrails": "",
            "first_parallelizable_action_expected_evidence_type": "",
            "first_parallelizable_action_required_missing_fields": "",
            "first_parallelizable_action_operator_review_artifact": "",
            "first_parallelizable_action_post_intake_synchronization_targets": "",
            "first_parallelizable_action_acceptance_gate_commands": "",
            **_commercial_first_parallelizable_source_modality_fields(summary),
            "first_parallelizable_action_lane_id": "",
            "first_parallelizable_action_precondition": "",
            "first_execution_order": 0,
            "first_action_id": "",
            "first_operator_input_artifact": "",
            "first_execution_command": "",
            "first_validation_command": "",
            **_commercial_first_worker_runtime_receipt_fields(summary),
            **_commercial_production_ai_registry_promotion_fields(summary),
            **_commercial_production_ai_return_fields(summary),
            "all_preconditions_satisfied": False,
            "ladder": [],
            "blockers": [],
            "next_required_step": "",
            "execution_enabled": False,
            "external_state_mutated": False,
            "docking_results_emitted": False,
            "scope_widened": False,
            "checkpoint_promoted": False,
            "claim_boundary": (
                "Product commercial-readiness execution-ladder endpoint only; the local ladder artifact is missing "
                "or invalid. It does not run commands, run docking, run GPU jobs, fill evidence, promote checkpoints, "
                "widen claims, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_COMMERCIAL_READINESS_EXECUTION_LADDER_ARTIFACT),
        "ladder_ready": bool(summary.get("ladder_ready") is True),
        "operator_packet_artifact": summary.get("operator_packet_artifact", ""),
        "freshness_artifact": summary.get("freshness_artifact", ""),
        "operator_packet_ready": bool(summary.get("operator_packet_ready") is True),
        "freshness_ready": bool(summary.get("freshness_ready") is True),
        "goal_complete": bool(summary.get("goal_complete") is True),
        "action_count": int(summary.get("action_count") or 0),
        "blocked_action_count": int(summary.get("blocked_action_count") or 0),
        "parallelizable_action_count": int(summary.get("parallelizable_action_count") or 0),
        "parallelizable_action_ids": list(summary.get("parallelizable_action_ids") or []),
        "first_parallelizable_action_id": summary.get("first_parallelizable_action_id", ""),
        "first_parallelizable_action_order": int(
            summary.get("first_parallelizable_action_order") or 0
        ),
        "first_parallelizable_action_artifact": summary.get("first_parallelizable_action_artifact", ""),
        "first_parallelizable_action_next_action": summary.get(
            "first_parallelizable_action_next_action", ""
        ),
        "first_parallelizable_action_validation_command": summary.get(
            "first_parallelizable_action_validation_command", ""
        ),
        "first_parallelizable_action_required_operator_inputs": summary.get(
            "first_parallelizable_action_required_operator_inputs", ""
        ),
        "first_parallelizable_action_required_exact_evidence_fields": summary.get(
            "first_parallelizable_action_required_exact_evidence_fields", ""
        ),
        "first_parallelizable_action_required_claim_guardrails": summary.get(
            "first_parallelizable_action_required_claim_guardrails", ""
        ),
        "first_parallelizable_action_expected_evidence_type": summary.get(
            "first_parallelizable_action_expected_evidence_type", ""
        ),
        "first_parallelizable_action_required_missing_fields": summary.get(
            "first_parallelizable_action_required_missing_fields", ""
        ),
        "first_parallelizable_action_operator_review_artifact": summary.get(
            "first_parallelizable_action_operator_review_artifact", ""
        ),
        "first_parallelizable_action_post_intake_synchronization_targets": summary.get(
            "first_parallelizable_action_post_intake_synchronization_targets", ""
        ),
        "first_parallelizable_action_acceptance_gate_commands": summary.get(
            "first_parallelizable_action_acceptance_gate_commands", ""
        ),
        **_commercial_first_parallelizable_source_modality_fields(summary),
        "first_parallelizable_action_lane_id": summary.get("first_parallelizable_action_lane_id", ""),
        "first_parallelizable_action_precondition": summary.get(
            "first_parallelizable_action_precondition", ""
        ),
        "first_execution_order": int(summary.get("first_execution_order") or 0),
        "first_action_id": summary.get("first_action_id", ""),
        "first_operator_input_artifact": summary.get("first_operator_input_artifact", ""),
        "first_execution_command": summary.get("first_execution_command", ""),
        "first_validation_command": summary.get("first_validation_command", ""),
        **_commercial_first_worker_runtime_receipt_fields(summary),
        **_commercial_production_ai_registry_promotion_fields(summary),
        **_commercial_production_ai_return_fields(summary),
        "all_preconditions_satisfied": bool(summary.get("all_preconditions_satisfied") is True),
        "ladder": list(rows),
        "blockers": list(blockers),
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "external_state_mutated": False,
        "docking_results_emitted": False,
        "scope_widened": False,
        "checkpoint_promoted": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/commercial-readiness-handoff-bundle")
async def get_product_commercial_readiness_handoff_bundle() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_COMMERCIAL_READINESS_HANDOFF_BUNDLE_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_product_commercial_readiness_handoff_bundle",
            "artifact_path": str(PRODUCT_COMMERCIAL_READINESS_HANDOFF_BUNDLE_ARTIFACT),
            "handoff_bundle_ready": False,
            "goal_complete": False,
            "artifact_count": 0,
            "ready_artifact_count": 0,
            "blocked_artifact_count": 1,
            "blocked_artifact_ids": ["missing_product_commercial_readiness_handoff_bundle"],
            "operator_packet_ready": False,
            "source_fingerprint_ready": False,
            "freshness_ready": False,
            "execution_ladder_ready": False,
            "operator_action_count": 0,
            "operator_blocked_action_count": 0,
            "ladder_action_count": 0,
            "operator_parallelizable_action_count": 0,
            "operator_parallelizable_action_ids": [],
            "ladder_parallelizable_action_count": 0,
            "ladder_parallelizable_action_ids": [],
            "first_parallelizable_action_id": "",
            "first_parallelizable_action_artifact": "",
            "first_parallelizable_action_next_action": "",
            "first_parallelizable_action_validation_command": "",
            "first_parallelizable_action_required_operator_inputs": "",
            "first_parallelizable_action_required_exact_evidence_fields": "",
            "first_parallelizable_action_required_claim_guardrails": "",
            "first_parallelizable_action_expected_evidence_type": "",
            "first_parallelizable_action_required_missing_fields": "",
            "first_parallelizable_action_operator_review_artifact": "",
            "first_parallelizable_action_post_intake_synchronization_targets": "",
            "first_parallelizable_action_acceptance_gate_commands": "",
            **_commercial_first_parallelizable_source_modality_fields(summary),
            "first_parallelizable_action_lane_id": "",
            "first_parallelizable_action_precondition": "",
            "first_action_id": "",
            "first_operator_input_artifact": "",
            "first_execution_command": "",
            "first_validation_command": "",
            **_commercial_first_worker_runtime_receipt_fields(summary),
            **_commercial_production_ai_registry_promotion_fields(summary),
            **_commercial_production_ai_return_fields(summary),
            **_commercial_handoff_closure_acceptance_fields(summary),
            **_commercial_engine_refinement_claim_fields(summary),
            **_commercial_scope_breadth_evidence_receipt_fields(summary),
            "artifact_reference_contract_ready": False,
            "artifact_reference_count": 0,
            "artifact_reference_manifest": [],
            "local_required_artifact_reference_count": 0,
            "local_missing_artifact_reference_count": 1,
            "local_missing_artifact_references": [
                "missing_product_commercial_readiness_handoff_bundle"
            ],
            "operator_return_artifact_reference_count": 0,
            "operator_return_pending_artifact_reference_count": 0,
            "abstract_artifact_reference_count": 0,
            "artifacts": [],
            "blockers": [],
            "next_required_step": "",
            "execution_enabled": False,
            "external_state_mutated": False,
            "docking_results_emitted": False,
            "scope_widened": False,
            "checkpoint_promoted": False,
            "claim_boundary": (
                "Product commercial-readiness handoff-bundle endpoint only; the local bundle artifact is missing "
                "or invalid. It does not run commands, run docking, run GPU jobs, fill evidence, promote checkpoints, "
                "widen claims, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_COMMERCIAL_READINESS_HANDOFF_BUNDLE_ARTIFACT),
        "handoff_bundle_ready": bool(summary.get("handoff_bundle_ready") is True),
        "goal_complete": bool(summary.get("goal_complete") is True),
        "artifact_count": int(summary.get("artifact_count") or 0),
        "ready_artifact_count": int(summary.get("ready_artifact_count") or 0),
        "blocked_artifact_count": int(summary.get("blocked_artifact_count") or 0),
        "blocked_artifact_ids": list(summary.get("blocked_artifact_ids") or []),
        "operator_packet_ready": bool(summary.get("operator_packet_ready") is True),
        "source_fingerprint_ready": bool(summary.get("source_fingerprint_ready") is True),
        "freshness_ready": bool(summary.get("freshness_ready") is True),
        "execution_ladder_ready": bool(summary.get("execution_ladder_ready") is True),
        "operator_action_count": int(summary.get("operator_action_count") or 0),
        "operator_blocked_action_count": int(summary.get("operator_blocked_action_count") or 0),
        "ladder_action_count": int(summary.get("ladder_action_count") or 0),
        "operator_parallelizable_action_count": int(
            summary.get("operator_parallelizable_action_count") or 0
        ),
        "operator_parallelizable_action_ids": list(
            summary.get("operator_parallelizable_action_ids") or []
        ),
        "ladder_parallelizable_action_count": int(
            summary.get("ladder_parallelizable_action_count") or 0
        ),
        "ladder_parallelizable_action_ids": list(
            summary.get("ladder_parallelizable_action_ids") or []
        ),
        "first_parallelizable_action_id": summary.get("first_parallelizable_action_id", ""),
        "first_parallelizable_action_artifact": summary.get("first_parallelizable_action_artifact", ""),
        "first_parallelizable_action_next_action": summary.get(
            "first_parallelizable_action_next_action", ""
        ),
        "first_parallelizable_action_validation_command": summary.get(
            "first_parallelizable_action_validation_command", ""
        ),
        "first_parallelizable_action_required_operator_inputs": summary.get(
            "first_parallelizable_action_required_operator_inputs", ""
        ),
        "first_parallelizable_action_required_exact_evidence_fields": summary.get(
            "first_parallelizable_action_required_exact_evidence_fields", ""
        ),
        "first_parallelizable_action_required_claim_guardrails": summary.get(
            "first_parallelizable_action_required_claim_guardrails", ""
        ),
        "first_parallelizable_action_expected_evidence_type": summary.get(
            "first_parallelizable_action_expected_evidence_type", ""
        ),
        "first_parallelizable_action_required_missing_fields": summary.get(
            "first_parallelizable_action_required_missing_fields", ""
        ),
        "first_parallelizable_action_operator_review_artifact": summary.get(
            "first_parallelizable_action_operator_review_artifact", ""
        ),
        "first_parallelizable_action_post_intake_synchronization_targets": summary.get(
            "first_parallelizable_action_post_intake_synchronization_targets", ""
        ),
        "first_parallelizable_action_acceptance_gate_commands": summary.get(
            "first_parallelizable_action_acceptance_gate_commands", ""
        ),
        **_commercial_first_parallelizable_source_modality_fields(summary),
        "first_parallelizable_action_lane_id": summary.get("first_parallelizable_action_lane_id", ""),
        "first_parallelizable_action_precondition": summary.get(
            "first_parallelizable_action_precondition", ""
        ),
        "first_action_id": summary.get("first_action_id", ""),
        "first_operator_input_artifact": summary.get("first_operator_input_artifact", ""),
        "first_execution_command": summary.get("first_execution_command", ""),
        "first_validation_command": summary.get("first_validation_command", ""),
        **_commercial_first_worker_runtime_receipt_fields(summary),
        **_commercial_production_ai_registry_promotion_fields(summary),
        **_commercial_production_ai_return_fields(summary),
        **_commercial_handoff_closure_acceptance_fields(summary),
        **_commercial_engine_refinement_claim_fields(summary),
        **_commercial_scope_breadth_evidence_receipt_fields(summary),
        "artifact_reference_contract_ready": bool(
            summary.get("artifact_reference_contract_ready") is True
        ),
        "artifact_reference_count": int(summary.get("artifact_reference_count") or 0),
        "artifact_reference_manifest": list(summary.get("artifact_reference_manifest") or []),
        "local_required_artifact_reference_count": int(
            summary.get("local_required_artifact_reference_count") or 0
        ),
        "local_missing_artifact_reference_count": int(
            summary.get("local_missing_artifact_reference_count") or 0
        ),
        "local_missing_artifact_references": list(
            summary.get("local_missing_artifact_references") or []
        ),
        "operator_return_artifact_reference_count": int(
            summary.get("operator_return_artifact_reference_count") or 0
        ),
        "operator_return_pending_artifact_reference_count": int(
            summary.get("operator_return_pending_artifact_reference_count") or 0
        ),
        "abstract_artifact_reference_count": int(
            summary.get("abstract_artifact_reference_count") or 0
        ),
        "artifacts": list(rows),
        "blockers": list(blockers),
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "external_state_mutated": False,
        "docking_results_emitted": False,
        "scope_widened": False,
        "checkpoint_promoted": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/full-commercial-blocker-evidence-matrix")
async def get_product_full_commercial_blocker_evidence_matrix() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_FULL_COMMERCIAL_BLOCKER_EVIDENCE_MATRIX_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    blockers = packet.get("blockers") if isinstance(packet.get("blockers"), list) else []
    if not summary:
        return {
            "status": "missing_product_full_commercial_blocker_evidence_matrix",
            "artifact_path": str(PRODUCT_FULL_COMMERCIAL_BLOCKER_EVIDENCE_MATRIX_ARTIFACT),
            "full_commercial_blocker_evidence_matrix_ready": False,
            "full_commercial_evidence_receipts_ready": False,
            "release_blocker_visibility_ready": False,
            "expected_release_blocker_ids": [],
            "expected_release_blocker_count": 0,
            "goal_audit_release_blocker_ids": [],
            "missing_goal_audit_release_blocker_ids": [],
            "bottleneck_release_blocker_ids": [],
            "missing_bottleneck_release_blocker_ids": [],
            "scope_receipt_json": "",
            "scope_receipt_status": "",
            "scope_receipt_ready": False,
            "scope_receipt_blocked_row_count": 0,
            "engine_receipt_json": "",
            "engine_receipt_status": "",
            "engine_receipt_ready": False,
            "engine_receipt_blocked_row_count": 0,
            "matrix_row_count": 0,
            "pass_matrix_row_count": 0,
            "blocked_matrix_row_count": 0,
            "ready_receipt_count": 0,
            "blocked_receipt_count": 0,
            "approval_token_count": 0,
            "approval_tokens_required": [],
            "first_blocked_release_blocker_id": "",
            "first_blocked_evidence_row_id": "",
            "first_blocked_evidence_artifact": "",
            "first_blocked_expected_evidence_status": "",
            "first_blocked_observed_evidence_status": "",
            "first_blocked_row_blockers": "",
            "first_blocked_receipt_json": "",
            "first_blocked_acceptance_artifact": "",
            "first_blocked_next_required_step": "",
            "scope_receipt_most_common_row_blocker": "",
            "engine_receipt_most_common_row_blocker": "",
            "evidence_matrix": [],
            "blockers": [],
            "next_required_step": "",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product full-commercial blocker evidence-matrix endpoint only; the local matrix artifact is "
                "missing or invalid. It does not fill evidence, approve tokens, run docking, promote claims, "
                "upload, email, delete, commit, push, or mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_FULL_COMMERCIAL_BLOCKER_EVIDENCE_MATRIX_ARTIFACT),
        "full_commercial_blocker_evidence_matrix_ready": bool(
            summary.get("full_commercial_blocker_evidence_matrix_ready") is True
        ),
        "full_commercial_evidence_receipts_ready": bool(
            summary.get("full_commercial_evidence_receipts_ready") is True
        ),
        "release_blocker_visibility_ready": bool(
            summary.get("release_blocker_visibility_ready") is True
        ),
        "expected_release_blocker_ids": list(summary.get("expected_release_blocker_ids") or []),
        "expected_release_blocker_count": int(summary.get("expected_release_blocker_count") or 0),
        "goal_audit_release_blocker_ids": list(summary.get("goal_audit_release_blocker_ids") or []),
        "missing_goal_audit_release_blocker_ids": list(
            summary.get("missing_goal_audit_release_blocker_ids") or []
        ),
        "bottleneck_release_blocker_ids": list(summary.get("bottleneck_release_blocker_ids") or []),
        "missing_bottleneck_release_blocker_ids": list(
            summary.get("missing_bottleneck_release_blocker_ids") or []
        ),
        "scope_receipt_json": summary.get("scope_receipt_json", ""),
        "scope_receipt_status": summary.get("scope_receipt_status", ""),
        "scope_receipt_ready": bool(summary.get("scope_receipt_ready") is True),
        "scope_receipt_blocked_row_count": int(summary.get("scope_receipt_blocked_row_count") or 0),
        "engine_receipt_json": summary.get("engine_receipt_json", ""),
        "engine_receipt_status": summary.get("engine_receipt_status", ""),
        "engine_receipt_ready": bool(summary.get("engine_receipt_ready") is True),
        "engine_receipt_blocked_row_count": int(
            summary.get("engine_receipt_blocked_row_count") or 0
        ),
        "matrix_row_count": int(summary.get("matrix_row_count") or 0),
        "pass_matrix_row_count": int(summary.get("pass_matrix_row_count") or 0),
        "blocked_matrix_row_count": int(summary.get("blocked_matrix_row_count") or 0),
        "ready_receipt_count": int(summary.get("ready_receipt_count") or 0),
        "blocked_receipt_count": int(summary.get("blocked_receipt_count") or 0),
        "approval_token_count": int(summary.get("approval_token_count") or 0),
        "approval_tokens_required": list(summary.get("approval_tokens_required") or []),
        "first_blocked_release_blocker_id": summary.get("first_blocked_release_blocker_id", ""),
        "first_blocked_evidence_row_id": summary.get("first_blocked_evidence_row_id", ""),
        "first_blocked_evidence_artifact": summary.get("first_blocked_evidence_artifact", ""),
        "first_blocked_expected_evidence_status": summary.get(
            "first_blocked_expected_evidence_status", ""
        ),
        "first_blocked_observed_evidence_status": summary.get(
            "first_blocked_observed_evidence_status", ""
        ),
        "first_blocked_row_blockers": summary.get("first_blocked_row_blockers", ""),
        "first_blocked_receipt_json": summary.get("first_blocked_receipt_json", ""),
        "first_blocked_acceptance_artifact": summary.get("first_blocked_acceptance_artifact", ""),
        "first_blocked_next_required_step": summary.get("first_blocked_next_required_step", ""),
        "scope_receipt_most_common_row_blocker": summary.get(
            "scope_receipt_most_common_row_blocker", ""
        ),
        "engine_receipt_most_common_row_blocker": summary.get(
            "engine_receipt_most_common_row_blocker", ""
        ),
        "evidence_matrix": list(rows),
        "blockers": list(blockers),
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }


@router.get("/goal-completion-audit")
async def get_product_goal_completion_audit() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_GOAL_COMPLETION_AUDIT_ARTIFACT)
    readiness = _summary(_read_json_object(GOAL_READINESS_ROLLUP_ARTIFACT))
    lane_surface = _goal_readiness_rollup_lane_surface(readiness)
    registry_packet = _read_json_object(RESIDUAL_MODEL_REGISTRY_ARTIFACT)
    summary = _summary(packet)
    registry = _summary(registry_packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_product_goal_completion_audit",
            "artifact_path": str(PRODUCT_GOAL_COMPLETION_AUDIT_ARTIFACT),
            "goal_complete": False,
            "requirement_count": 0,
            "pass_count": 0,
            "fail_count": 1,
            "primary_bottleneck_phase": "",
            "primary_bottleneck_kind": "",
            "approval_tokens_required": [],
            "next_command": "",
            "next_command_candidate_count": 0,
            "next_command_candidates": [],
            "product_ai_architecture_ready": False,
            "product_ai_architecture_gap_status": "",
            "product_ai_architecture_all_gaps_closed": False,
            "product_ai_architecture_gap_count": 0,
            "product_ai_architecture_closed_gap_count": 0,
            "product_ai_architecture_open_gap_count": 0,
            "product_ai_architecture_open_gap_ids": [],
            "product_ai_architecture_closed_gap_ids": [],
            "product_ai_architecture_gap_blocker_matrix_ready": False,
            "product_ai_architecture_gap_blocker_matrix_count": 0,
            "product_ai_architecture_gap_blocker_matrix": [],
            "product_ai_architecture_current_primary_blocker_gap_id": "",
            "product_ai_architecture_current_primary_blocker_id": "",
            "product_ai_architecture_current_primary_blocker_artifact": "",
            "product_ai_architecture_current_primary_blocker_validation_command": "",
            "product_ai_architecture_current_primary_blocker_next_action": "",
            "product_ai_architecture_current_primary_blocker_operator_input_fields": [],
            "product_ai_architecture_current_primary_blocker_unlock_claim": "",
            "product_ai_architecture_current_primary_blocker_next_after_stage_id": "",
            "product_ai_architecture_current_primary_blocker_next_after_artifact": "",
            "product_ai_architecture_current_primary_blocker_next_after_validation_command": "",
            "product_ai_architecture_current_primary_blocker_next_after_next_action": "",
            "product_ai_architecture_current_primary_blocker_next_after_required_checks": [],
            "product_ai_architecture_current_primary_blocker_next_after_unlock_fields": [],
            "product_ai_architecture_parallelizable_gap_blocker_count": 0,
            "product_ai_architecture_parallelizable_gap_blocker_ids": [],
            "product_ai_architecture_first_parallelizable_gap_id": "",
            "product_ai_architecture_first_parallelizable_blocker_id": "",
            "product_ai_architecture_first_parallelizable_blocker_artifact": "",
            "product_ai_architecture_first_parallelizable_blocker_next_action": "",
            "product_ai_architecture_first_parallelizable_blocker_validation_command": "",
            "product_ai_architecture_first_parallelizable_blocker_operator_input_fields": [],
            "product_ai_architecture_first_parallelizable_blocker_required_exact_evidence_fields": [],
            "product_ai_architecture_first_parallelizable_blocker_required_claim_guardrails": [],
            "product_ai_architecture_first_parallelizable_blocker_claim_safe_completion_rule": "",
            "product_ai_architecture_first_parallelizable_blocker_unlock_claim": "",
            "product_ai_architecture_first_parallelizable_blocker_source_modality_triage_artifact": "",
            "product_ai_architecture_first_parallelizable_blocker_source_modality_triage_decision": "",
            "product_ai_architecture_first_parallelizable_blocker_source_modality_direct_experimental_binding_row_count": 0,
            "product_ai_architecture_first_parallelizable_blocker_source_modality_claim_safe_binding_kcal_ready_count": 0,
            "product_ai_architecture_first_parallelizable_blocker_source_modality_computational_binding_energy_row_count": 0,
            "product_ai_architecture_first_parallelizable_blocker_source_modality_best_computational_binding_energy_kcal_mol": "",
            "commercial_readiness_next_action_matrix_ready": False,
            "commercial_readiness_next_action_matrix": [],
            "commercial_readiness_next_action_matrix_count": 0,
            "commercial_readiness_next_action_blocker_matrix": [],
            "commercial_readiness_next_action_blocker_count": 0,
            "commercial_readiness_first_next_action_id": "",
            "commercial_readiness_first_next_action_artifact": "",
            "commercial_readiness_first_next_action_validation_command": "",
            "commercial_readiness_handoff_bundle_status": "",
            "commercial_readiness_handoff_bundle_artifact_path": "",
            "commercial_readiness_handoff_bundle_ready": False,
            "commercial_readiness_handoff_bundle_artifact_count": 0,
            "commercial_readiness_handoff_bundle_blocked_artifact_count": 0,
            "commercial_readiness_handoff_bundle_blocked_artifact_ids": [],
            "commercial_readiness_handoff_bundle_artifact_reference_contract_ready": False,
            "commercial_readiness_handoff_bundle_artifact_reference_count": 0,
            "commercial_readiness_handoff_bundle_local_missing_artifact_reference_count": 0,
            "commercial_readiness_handoff_bundle_operator_return_pending_artifact_reference_count": 0,
            "commercial_readiness_handoff_bundle_first_action_id": "",
            "commercial_readiness_handoff_bundle_first_operator_input_artifact": "",
            "commercial_readiness_handoff_bundle_next_required_step": "",
            "product_ai_production_checkpoint_gap_ready": False,
            "product_ai_production_checkpoint_gap_observed": "",
            "product_ai_closed_loop_decision_graph_ready": False,
            "product_ai_closed_loop_decision_graph_observed": "",
            "product_ai_durable_job_orchestration_ready": False,
            "product_ai_durable_job_orchestration_observed": "",
            "product_ai_trajectory_sla_ready": False,
            "product_ai_trajectory_sla_observed": "",
            "product_ai_trajectory_sla_claim_tier": "",
            "product_ai_trajectory_sla_restricted_family_allowed": False,
            "product_ai_trajectory_sla_broad_platform_allowed": False,
            "product_ai_trajectory_sla_current_rocm_baseline_claim_scope": "",
            "product_ai_trajectory_sla_current_rocm_baseline_production_profile_enabled": False,
            "product_ai_trajectory_sla_rocm_baseline_profile_gap_acknowledged": False,
            "product_ai_scope_breadth_ready": False,
            "product_ai_scope_breadth_observed": "",
            "product_scope_evidence_queue_next_operator_completion_packet_ready": False,
            "product_scope_evidence_queue_next_operator_completion_slot_id": "",
            "product_scope_evidence_queue_next_operator_completion_expected_evidence_type": "",
            "product_scope_evidence_queue_next_operator_completion_required_exact_evidence_field_count": 0,
            "product_scope_evidence_queue_next_operator_completion_required_exact_evidence_fields": "",
            "product_scope_evidence_queue_next_operator_completion_required_operator_intake_columns": "",
            "product_scope_evidence_queue_next_operator_completion_required_claim_guardrails": "",
            "product_scope_evidence_queue_next_operator_completion_operator_review_artifact": "",
            "product_scope_evidence_queue_next_operator_completion_post_intake_synchronization_targets": "",
            "product_scope_evidence_queue_next_operator_completion_acceptance_gate_commands": "",
            "product_scope_evidence_queue_next_operator_completion_contract_artifact": "",
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_sidecar_ready": False,
            "product_scope_evidence_queue_next_operator_completion_aqp1_functional_surrogate_artifact": "",
            "product_scope_evidence_queue_next_operator_completion_aqp1_candidate_ledger_artifact": "",
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_candidate_name": "",
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_source_anchor": "",
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_source_url": "",
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_target_uniprot": "",
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_functional_measure": "",
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_functional_delta_g_surrogate_kcal_mol": "",
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_assay_type_honesty": "",
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_direct_binding_claim_allowed": "",
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_binding_kcal_claim_allowed": "",
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_replacement_reference_binding_kcal_mol_must_remain_blank": "",
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_claim_safe_functional_kcal_ready": "",
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_ledger_review_bucket": "",
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_ledger_promotion_policy": "",
            "product_scope_evidence_queue_pxr_exact_review_sidecar_row_count": 0,
            "product_scope_evidence_queue_next_pxr_exact_review_sidecar_ready": False,
            "product_scope_evidence_queue_next_pxr_exact_review_row_id": "",
            "product_scope_evidence_queue_next_pxr_exact_review_candidate_name": "",
            "product_scope_evidence_queue_next_pxr_exact_review_required_evidence_mode": "",
            "product_scope_evidence_queue_next_pxr_exact_review_target_match_confirmed": "",
            "product_scope_evidence_queue_next_pxr_exact_review_replacement_reference_binding_kcal_mol": "",
            "product_scope_evidence_queue_next_pxr_exact_review_replacement_source_url_or_doi": "",
            "product_scope_evidence_queue_next_pxr_exact_review_authoritative_apply_allowed": False,
            "product_scope_evidence_queue_next_pxr_exact_review_scope_promotion_allowed": False,
            "product_ai_report_ux_ready": False,
            "product_ai_report_ux_observed": "",
            "product_ai_report_ux_customer_report_delivery_contract_ready": False,
            "product_ai_report_ux_customer_report_evidence_binding_ready": False,
            "product_ai_report_ux_customer_report_viewer_binding_ready": False,
            "product_ai_report_ux_viewer_customer_report_binding_ready": False,
            "product_ai_report_ux_customer_report_ready_block_count": 0,
            "product_ai_report_ux_customer_report_required_block_count": 0,
            "product_ai_report_ux_customer_report_blocked_block_count": 0,
            "product_ai_security_deployment_ready": False,
            "product_ai_security_deployment_observed": "",
            "product_ai_security_hosted_deployment_contract_ready": False,
            "product_ai_security_hosted_deployment_currently_satisfied": False,
            "product_ai_security_hosted_deployment_next_stage_id": "",
            "product_ai_security_hosted_external_exposure_allowed": False,
            "product_ai_security_hosted_secret_injection_ready": False,
            "product_ai_security_tls_termination_operator_verified": False,
            "production_ai_inference_subject_active": False,
            "production_ai_default_residual_mode": "",
            "production_ai_promotion_allowed": False,
            "production_ai_customer_facing_auto_correction_allowed": False,
            "production_ai_customer_facing_score_mutation_allowed": False,
            "production_ai_customer_facing_ranking_mutation_allowed": False,
            "production_ai_trained_checkpoint_count": 0,
            "production_ai_selected_sidecar_ready": False,
            "production_ai_selected_sidecar_missing_output_fields": [],
            "production_ai_blocked_reason": "missing_product_goal_completion_audit",
            "production_ai_residual_model_registry_status": "",
            "production_ai_residual_model_registry_artifact_path": "",
            "production_ai_residual_model_registry_ready": False,
            "production_ai_product_model_layer_ready": False,
            "production_ai_registry_checkpoint_preflight_ready": False,
            "production_ai_registry_production_checkpoint_blocked": False,
            "production_ai_registry_checkpoint_primary_blocker": "",
            "production_ai_registry_checkpoint_missing_output_fields": [],
            "production_ai_registry_checkpoint_missing_adapter_output_policy_fields": [],
            "product_ai_primary_backlog_detail": "",
            "product_ai_primary_backlog_work_item_id": "",
            "product_ai_primary_backlog_acceptance_criteria": "",
            "product_ai_primary_backlog_next_action": "",
            "product_ai_primary_backlog_source_artifact": "",
            "product_ai_primary_backlog_verification_command": "",
            "production_ai_gpu_worker_return_receipt_ready": False,
            "production_ai_gpu_worker_return_receipt_blockers": [],
            "production_ai_gpu_expected_queue_rows": 0,
            "production_ai_gpu_manifest_ok_row_count": 0,
            "production_ai_gpu_manifest_status_placeholder_count": 0,
            "production_ai_gpu_manifest_status_invalid_count": 0,
            "production_ai_gpu_manifest_npz_paths_complete": False,
            "production_ai_gpu_manifest_npz_files_exist": False,
            "production_ai_gpu_manifest_npz_files_valid": False,
            "production_ai_gpu_manifest_npz_schema_valid": False,
            "production_ai_gpu_manifest_npz_identity_valid": False,
            "production_ai_gpu_manifest_npz_path_present_count": 0,
            "production_ai_gpu_manifest_npz_path_missing_count": 0,
            "production_ai_gpu_manifest_ok_row_missing_npz_path_count": 0,
            "production_ai_gpu_manifest_operator_verified_missing_npz_path_count": 0,
            "production_ai_gpu_manifest_npz_file_existing_count": 0,
            "production_ai_gpu_manifest_npz_file_missing_count": 0,
            "production_ai_gpu_manifest_ok_row_missing_npz_file_count": 0,
            "production_ai_gpu_manifest_operator_verified_missing_npz_file_count": 0,
            "production_ai_gpu_manifest_npz_file_valid_count": 0,
            "production_ai_gpu_manifest_npz_file_invalid_count": 0,
            "production_ai_gpu_manifest_ok_row_invalid_npz_file_count": 0,
            "production_ai_gpu_manifest_operator_verified_invalid_npz_file_count": 0,
            "production_ai_gpu_manifest_npz_schema_valid_count": 0,
            "production_ai_gpu_manifest_npz_schema_invalid_count": 0,
            "production_ai_gpu_manifest_ok_row_invalid_npz_schema_count": 0,
            "production_ai_gpu_manifest_operator_verified_invalid_npz_schema_count": 0,
            "production_ai_gpu_manifest_npz_identity_valid_count": 0,
            "production_ai_gpu_manifest_npz_identity_invalid_count": 0,
            "production_ai_gpu_manifest_ok_row_invalid_npz_identity_count": 0,
            "production_ai_gpu_manifest_operator_verified_invalid_npz_identity_count": 0,
            "production_ai_gpu_manifest_operator_verified": False,
            "production_ai_gpu_operator_verified_true_count": 0,
            "production_ai_gpu_operator_verification_column_present": False,
            "production_ai_gpu_identity_coverage_ready": False,
            "production_ai_gpu_matched_queue_fingerprints": 0,
            "production_ai_gpu_queue_fingerprints": 0,
            "production_ai_force_derivation_input_ready": False,
            "production_ai_delta_force_derivation_validation_ready": False,
            "production_ai_missing_output_labels": [],
            "production_ai_checkpoint_output_head_gap_contract_ready": False,
            "production_ai_checkpoint_output_heads_complete": False,
            "production_ai_checkpoint_output_head_required_field_count": 0,
            "production_ai_checkpoint_output_head_ready_field_count": 0,
            "production_ai_checkpoint_output_head_blocked_field_count": 0,
            "production_ai_checkpoint_output_head_blocked_fields": [],
            "production_ai_checkpoint_output_head_first_blocked_field": "",
            "production_ai_checkpoint_output_head_first_blocked_field_blockers": [],
            "production_ai_checkpoint_output_head_gap_contract_artifact_path": "",
            "production_ai_delta_force_closure_acceptance_artifact_path": "",
            "production_ai_delta_force_closure_acceptance_packet_ready": False,
            "production_ai_delta_force_closure_ready": False,
            "production_ai_delta_force_closure_first_blocked_output_field": "",
            "production_ai_delta_force_closure_failed_stage_count": 0,
            "production_ai_delta_force_closure_failed_stage_ids": [],
            "production_ai_delta_force_closure_next_stage_id": "",
            "production_ai_delta_force_closure_next_stage_artifact": "",
            "production_ai_delta_force_closure_next_stage_validation_command": "",
            "production_ai_delta_force_closure_next_required_step": "",
            "production_ai_checkpoint_readiness_status": "",
            "production_ai_checkpoint_ready": False,
            "production_ai_checkpoint_failed_check_ids": [],
            "production_ai_checkpoint_first_failed_check_id": "",
            "production_ai_checkpoint_first_failed_source_artifact": "",
            "production_ai_checkpoint_first_failed_observed": "",
            "production_ai_checkpoint_first_failed_required": "",
            "production_ai_checkpoint_first_failed_next_action": "",
            "production_ai_checkpoint_registry_promotion_required_gate_ids": [],
            "production_ai_checkpoint_registry_promotion_missing_gate_ids": [],
            "production_ai_checkpoint_registry_promotion_missing_gate_count": 0,
            "production_ai_checkpoint_registry_promotion_upstream_acceptance_ready": False,
            "production_ai_checkpoint_registry_promotion_currently_satisfied": False,
            "production_ai_checkpoint_actionable_blocker_stage_id": "",
            "production_ai_checkpoint_actionable_blocker_check_id": "",
            "production_ai_checkpoint_actionable_blocker_artifact": "",
            "production_ai_checkpoint_actionable_blocker_observed": "",
            "production_ai_checkpoint_actionable_blocker_required": "",
            "production_ai_checkpoint_actionable_blocker_next_action": "",
            "production_ai_checkpoint_actionable_blocker_validation_command": "",
            "production_ai_checkpoint_actionable_blocker_unlock_fields": [],
            "production_ai_checkpoint_actionable_blocker_downstream_blocked_stage_count": 0,
            "production_ai_checkpoint_next_after_actionable_blocker_stage_id": "",
            "production_ai_checkpoint_next_after_actionable_blocker_artifact": "",
            "production_ai_checkpoint_next_after_actionable_blocker_validation_command": "",
            "production_ai_checkpoint_next_after_actionable_blocker_required_checks": [],
            "production_ai_checkpoint_next_after_actionable_blocker_unlock_fields": [],
            "production_ai_checkpoint_next_after_actionable_blocker_next_action": "",
            "production_ai_checkpoint_actionable_blocker_blocks_registry_promotion": False,
            "production_ai_checkpoint_actionable_operator_completion_packet_ready": False,
            "production_ai_checkpoint_actionable_operator_completion_packet_artifact": "",
            "production_ai_checkpoint_actionable_operator_completion_artifact_id": "",
            "production_ai_checkpoint_actionable_operator_completion_artifact_path": "",
            "production_ai_checkpoint_actionable_operator_completion_expected_queue_rows": 0,
            "production_ai_checkpoint_actionable_operator_completion_required_fields_or_columns": [],
            "production_ai_checkpoint_actionable_operator_completion_diagnostic_commands": [],
            "production_ai_checkpoint_actionable_operator_completion_diagnostic_command_count": 0,
            "production_ai_checkpoint_actionable_operator_completion_diagnostic_required_fields": [],
            "production_ai_checkpoint_actionable_operator_completion_diagnostic_required_field_count": 0,
            "production_ai_checkpoint_actionable_operator_completion_diagnostic_completion_rule": "",
            "production_ai_checkpoint_actionable_operator_completion_diagnostic_return_artifacts": [],
            "production_ai_checkpoint_actionable_operator_completion_torch_visibility_probe_command": "",
            "production_ai_checkpoint_actionable_operator_completion_failed_check_ids": [],
            "production_ai_checkpoint_actionable_operator_completion_template_payload_json": "",
            "production_ai_checkpoint_actionable_operator_completion_validation_command": "",
            "production_ai_checkpoint_actionable_operator_completion_full_regeneration_command": "",
            "production_ai_checkpoint_actionable_operator_completion_completion_rule": "",
            "production_ai_checkpoint_actionable_operator_completion_backend_provenance_completion_rule": "",
            "production_ai_checkpoint_actionable_operator_completion_next_action": "",
            "production_ai_checkpoint_actionable_operator_completion_packet": {},
            "production_ai_checkpoint_worker_runtime_receipt_contract_ready": False,
            "production_ai_checkpoint_worker_runtime_receipt_contract": {},
            "production_ai_checkpoint_worker_runtime_receipt_required_fields_or_columns": [],
            "production_ai_checkpoint_worker_runtime_receipt_required_field_count": 0,
            "production_ai_checkpoint_worker_runtime_receipt_completion_rule": "",
            "production_ai_checkpoint_worker_runtime_receipt_post_environment_next_stage_id": "",
            "production_ai_checkpoint_worker_runtime_receipt_post_environment_next_artifact": "",
            "production_ai_checkpoint_worker_runtime_receipt_post_environment_validation_command": "",
            "production_ai_checkpoint_worker_runtime_receipt_full_regeneration_command": "",
            "production_ai_checkpoint_worker_runtime_receipt_guardrails": [],
            "production_ai_checkpoint_acceptance_matrix_ready": False,
            "production_ai_checkpoint_acceptance_stage_count": 0,
            "production_ai_checkpoint_acceptance_ready_stage_count": 0,
            "production_ai_checkpoint_acceptance_blocked_stage_count": 0,
            "production_ai_checkpoint_acceptance_stage_ids": [],
            "production_ai_checkpoint_acceptance_ready_stage_ids": [],
            "production_ai_checkpoint_acceptance_blocked_stage_ids": [],
            "production_ai_checkpoint_acceptance_matrix": [],
            "production_ai_checkpoint_acceptance_current_blocked_stage_matrix": [],
            "production_ai_checkpoint_acceptance_release_blocker_stage_count": 0,
            "production_ai_checkpoint_acceptance_release_blocker_stage_ids": [],
            "production_ai_checkpoint_acceptance_next_stage_id": "",
            "production_ai_checkpoint_acceptance_next_stage_artifact": "",
            "production_ai_checkpoint_acceptance_next_stage_validation_command": "",
            "production_ai_checkpoint_acceptance_next_stage_release_effect": "",
            "production_ai_checkpoint_acceptance_next_stage_unlock_fields": [],
            "production_ai_checkpoint_acceptance_next_stage_required_checks": [],
            "production_ai_checkpoint_acceptance_next_stage_next_action": "",
            "production_ai_gpu_return_intake_status": "",
            "production_ai_gpu_return_intake_artifact_path": "",
            "production_ai_gpu_return_intake_ready": False,
            "production_ai_gpu_return_artifacts_ready": False,
            "production_ai_gpu_return_check_count": 0,
            "production_ai_gpu_return_fail_check_count": 0,
            "production_ai_gpu_return_failed_check_ids": [],
            "production_ai_gpu_return_blocker_matrix": [],
            "production_ai_gpu_return_blocker_matrix_count": 0,
            "production_ai_gpu_return_first_failed_check_id": "",
            "production_ai_gpu_return_first_failed_source_artifact": "",
            "production_ai_gpu_return_first_failed_observed": "",
            "production_ai_gpu_return_first_failed_required": "",
            "production_ai_gpu_return_first_failed_next_action": "",
            "production_ai_gpu_return_operator_return_artifact_completion_matrix": [],
            "production_ai_gpu_return_operator_return_artifact_completion_matrix_count": 0,
            "production_ai_gpu_return_operator_return_artifact_completion_blocker_matrix": [],
            "production_ai_gpu_return_operator_return_artifact_completion_blocker_count": 0,
            "production_ai_gpu_return_operator_return_next_artifact_completion_packet_ready": False,
            "production_ai_gpu_return_operator_return_next_artifact_completion_packet": {},
            "production_ai_gpu_return_operator_return_next_artifact_id": "",
            "production_ai_gpu_return_operator_return_next_artifact_path": "",
            "production_ai_gpu_return_operator_return_next_artifact_failed_check_ids": [],
            "production_ai_gpu_return_expected_queue_rows": 0,
            "production_ai_gpu_return_handoff_binding_ready": False,
            "production_ai_gpu_return_handoff_queue_csv": "",
            "production_ai_gpu_return_handoff_queue_csv_sha256": "",
            "production_ai_gpu_return_handoff_full_regeneration_command": "",
            "production_ai_gpu_return_handoff_return_manifest_schema_contract_ready": False,
            "production_ai_gpu_return_handoff_return_manifest_required_identity_rule": "",
            "production_ai_gpu_return_handoff_return_manifest_fingerprint_columns": [],
            "production_ai_gpu_return_handoff_return_manifest_queue_id_columns": [],
            "production_ai_gpu_return_handoff_return_manifest_npz_columns": [],
            "production_ai_gpu_return_manifest_template_csv": "",
            "production_ai_gpu_return_summary_template_csv": "",
            "production_ai_gpu_return_summary_template_payload_json": "",
            "production_ai_gpu_return_summary_template_required_fields": [],
            "production_ai_gpu_return_summary_template_completion_rule": "",
            "production_ai_gpu_return_summary_template_backend_provenance_contract_ready": False,
            "production_ai_gpu_return_summary_template_required_backend_provenance_fields": [],
            "production_ai_gpu_return_summary_template_backend_provenance_completion_rule": "",
            "production_ai_gpu_return_manifest_template_row_count": 0,
            "production_ai_gpu_return_manifest_operator_verification_placeholder_count": 0,
            "production_ai_gpu_return_operator_acceptance_matrix_ready": False,
            "production_ai_gpu_return_operator_acceptance_matrix": [],
            "production_ai_gpu_return_operator_acceptance_current_blocked_stage_matrix": [],
            "production_ai_gpu_return_operator_acceptance_stage_check_matrix": [],
            "production_ai_gpu_return_operator_acceptance_stage_check_matrix_count": 0,
            "production_ai_gpu_return_operator_acceptance_current_blocked_stage_check_matrix": [],
            "production_ai_gpu_return_operator_acceptance_current_blocked_stage_check_matrix_count": 0,
            "production_ai_gpu_return_operator_acceptance_stage_count": 0,
            "production_ai_gpu_return_operator_acceptance_ready_stage_count": 0,
            "production_ai_gpu_return_operator_acceptance_blocked_stage_count": 0,
            "production_ai_gpu_return_operator_acceptance_stage_ids": [],
            "production_ai_gpu_return_operator_acceptance_ready_stage_ids": [],
            "production_ai_gpu_return_operator_acceptance_blocked_stage_ids": [],
            "production_ai_gpu_return_operator_acceptance_next_stage_id": "",
            "production_ai_gpu_return_operator_acceptance_next_stage_artifact": "",
            "production_ai_gpu_return_operator_acceptance_next_stage_validation_command": "",
            "production_ai_gpu_return_operator_acceptance_next_stage_release_effect": "",
            "production_ai_gpu_return_operator_acceptance_next_stage_unlock_fields": [],
            "production_ai_gpu_return_operator_acceptance_next_stage_required_checks": [],
            "production_ai_gpu_return_operator_acceptance_next_stage_next_action": "",
            "production_ai_gpu_return_actual_summary_return_path": "",
            "production_ai_gpu_return_actual_manifest_return_path": "",
            "production_ai_gpu_summary_manifest_bound": False,
            "production_ai_gpu_summary_manifest_csv": "",
            "production_ai_gpu_summary_out_manifest_csv_present": False,
            "production_ai_gpu_summary_out_manifest_csv": "",
            "production_ai_gpu_summary_out_manifest_csv_bound": False,
            "production_ai_gpu_summary_out_summary_json_bound": False,
            "production_ai_gpu_summary_out_summary_json": "",
            "production_ai_gpu_summary_manifest_row_counts_consistent": False,
            "production_ai_gpu_backend_provenance_ready": False,
            "production_ai_gpu_backend_rows": 0,
            "production_ai_gpu_backend_non_production_rows": 0,
            "production_ai_gpu_backend_prod_mode": False,
            "production_ai_gpu_backend_require_rust_hip": False,
            "production_ai_gpu_worker_rocm_manifest_artifact": "",
            "production_ai_gpu_worker_rocm_manifest_ready": False,
            "production_ai_gpu_worker_rocm_manifest_generation_command": "",
            "production_ai_gpu_worker_rocm_manifest_completion_rule": "",
            "production_ai_gpu_worker_rocm_stack_detected": False,
            "production_ai_gpu_worker_rocm_torch_ready": False,
            "production_ai_gpu_worker_rocm_amd_gpu_detected": False,
            "production_ai_gpu_worker_rocm_visible_device_count": 0,
            "production_ai_gpu_worker_rocm_device_names": [],
            "production_ai_gpu_worker_rocm_next_required_step": "",
            "production_ai_checkpoint_gpu_backend_provenance_ready": False,
            "production_ai_checkpoint_gpu_backend_rows": 0,
            "production_ai_checkpoint_gpu_backend_non_production_rows": 0,
            "production_ai_gpu_return_post_return_validation_command": "",
            "production_ai_gpu_return_next_required_step": "",
            "production_ai_promotion_workbench_status": "",
            "production_ai_promotion_workbench_ready": False,
            "production_ai_promotion_ready": False,
            "production_ai_promotion_first_blocked_stage_id": "",
            "production_ai_promotion_first_blocked_stage_artifact": "",
            "production_ai_promotion_first_blocked_stage_ready_key": "",
            "production_ai_promotion_blocked_stage_count": 0,
            "production_ai_promotion_blocked_stage_ids": [],
            "production_ai_force_gpu_worker_handoff_ready": False,
            "production_ai_force_gpu_worker_operator_action_required": False,
            "production_ai_force_gpu_operator_transfer_manifest_ready": False,
            "production_ai_force_gpu_operator_transfer_outbound_artifact_count": 0,
            "production_ai_force_gpu_operator_transfer_outbound_artifacts": [],
            "production_ai_force_gpu_operator_transfer_inbound_artifact_count": 0,
            "production_ai_force_gpu_operator_transfer_inbound_artifacts": [],
            "production_ai_force_gpu_operator_transfer_first_return_artifact": "",
            "production_ai_force_gpu_operator_transfer_return_manifest_artifact": "",
            "production_ai_force_gpu_operator_transfer_acceptance_artifact": "",
            "production_ai_force_gpu_operator_transfer_acceptance_ready_key": "",
            "production_ai_force_gpu_operator_transfer_post_return_validation_command": "",
            "production_ai_force_gpu_full_regeneration_command": "",
            "production_ai_force_gpu_post_return_validation_command": "",
            "production_ai_force_gpu_post_run_validation_commands": [],
            "production_ai_force_gpu_post_return_required_production_output_fields": [],
            "production_ai_force_gpu_post_return_gpu_unlock_artifacts": [],
            "production_ai_force_gpu_post_return_unlock_output_fields": [],
            "production_ai_force_gpu_post_return_min_expected_label_rows": 0,
            "production_ai_force_gpu_post_return_promotion_ladder_stage_count": 0,
            "production_ai_force_gpu_post_return_promotion_ladder_contract_ready": False,
            "production_ai_force_gpu_post_return_promotion_ladder_currently_satisfied": False,
            "production_ai_force_gpu_post_return_promotion_ladder_current_blocked_stage_count": 0,
            "production_ai_force_gpu_post_return_promotion_ladder_current_blocked_stage_ids": [],
            "production_ai_force_gpu_post_return_promotion_ladder_current_next_stage_id": "",
            "production_ai_force_gpu_post_return_promotion_ladder_current_next_stage_artifact": "",
            "production_ai_force_gpu_post_return_promotion_ladder_current_next_stage_validation_command": "",
            "production_ai_force_gpu_post_return_promotion_ladder_stage_ids": [],
            "production_ai_force_gpu_post_return_promotion_ladder_missing_ready_keys": [],
            "production_ai_force_gpu_receipt_manifest_identity_row_count": 0,
            "production_ai_force_gpu_receipt_matched_queue_id_count": 0,
            "production_ai_force_gpu_receipt_matched_expected_npz_count": 0,
            "production_ai_force_gpu_receipt_matched_queue_fingerprint_count": 0,
            "product_scope_closure_acceptance_artifact_path": "",
            "product_scope_closure_acceptance_packet_ready": False,
            "product_scope_closure_acceptance_ready": False,
            "product_scope_closure_acceptance_stage_count": 0,
            "product_scope_closure_acceptance_blocked_stage_count": 0,
            "product_scope_closure_acceptance_blocked_stage_ids": [],
            "product_scope_closure_acceptance_next_stage_id": "",
            "product_scope_closure_acceptance_first_blocked_evidence_row_id": "",
            "product_scope_closure_acceptance_first_blocked_target_id": "",
            "product_scope_closure_acceptance_first_blocked_required_missing_fields": "",
            "product_scope_closure_acceptance_transporter_unresolved_slot_count": 0,
            "product_scope_closure_acceptance_pxr_direct_or_claim_safe_quantitative_ready_count": 0,
            "product_scope_closure_acceptance_general_platform_claim_allowed": False,
            "product_scope_closure_acceptance_next_required_step": "",
            "product_ai_scope_backlog_detail": "",
            "product_scope_closure_blocker_class_counts": {},
            "product_scope_first_scientific_blocker": "",
            "product_scope_manual_review_subcheck_count": 0,
            "product_scope_transporter_manual_review_subcheck_count": 0,
            "product_scope_transporter_identity_scaffold_confirmation_required_count": 0,
            "product_scope_transporter_direct_binding_or_kcal_confirmation_required_count": 0,
            "product_scope_transporter_negative_quantitative_confirmation_required_count": 0,
            "product_scope_transporter_direct_binding_missing_count": 0,
            "product_scope_transporter_negative_quantitative_missing_count": 0,
            "product_scope_transporter_operator_review_evidence_matrix_ready": False,
            "product_scope_transporter_claim_safe_local_evidence_ready_count": 0,
            "product_scope_transporter_claim_safe_local_evidence_blocked_count": 0,
            "product_scope_transporter_direct_binding_claim_blocked_count": 0,
            "product_scope_transporter_negative_value_claim_blocked_count": 0,
            "product_scope_transporter_top_claim_safe_blocker": "",
            "product_scope_transporter_top_operator_next_verdict": "",
            "product_scope_transporter_target_ready_for_promotion_count": 0,
            "product_scope_transporter_target_blocked_for_promotion_count": 0,
            "product_scope_transporter_target_ready_for_promotion_ids": [],
            "product_scope_transporter_target_blocked_for_promotion_ids": [],
            "product_scope_transporter_primary_blocker_target_id": "",
            "product_scope_transporter_primary_blocker_packet_step": "",
            "product_scope_transporter_primary_blocker_candidate_name": "",
            "product_scope_pxr_reconciled_blocked_row_count": 0,
            "product_scope_pxr_conflict_resolution_count": 0,
            "product_scope_pxr_quantitative_missing_count": 0,
            "product_scope_breadth_contract_status": "",
            "product_scope_breadth_contract_artifact_path": "",
            "product_scope_operator_transfer_manifest_ready": False,
            "product_scope_operator_transfer_outbound_artifact_count": 0,
            "product_scope_operator_transfer_outbound_artifacts": [],
            "product_scope_operator_transfer_inbound_artifact_count": 0,
            "product_scope_operator_transfer_inbound_artifacts": [],
            "product_scope_operator_transfer_first_return_artifact": "",
            "product_scope_operator_transfer_acceptance_artifact": "",
            "product_scope_operator_transfer_acceptance_ready_key": "",
            "product_scope_operator_transfer_next_acceptance_stage": "",
            "product_scope_operator_transfer_post_return_validation_command": "",
            "product_scope_acceptance_matrix_ready": False,
            "product_scope_claim_expansion_contract_ready": False,
            "product_scope_claim_expansion_currently_satisfied": False,
            "product_scope_claim_expansion_current_blocked_stage_count": 0,
            "product_scope_claim_expansion_current_blocked_stage_ids": [],
            "product_scope_claim_expansion_current_next_stage_id": "",
            "product_scope_claim_expansion_current_next_stage_artifact": "",
            "product_scope_claim_expansion_current_next_stage_validation_command": "",
            "product_scope_claim_expansion_current_next_stage_unlock_claim_scopes": [],
            "product_scope_acceptance_stage_count": 0,
            "product_scope_acceptance_ready_stage_count": 0,
            "product_scope_acceptance_blocked_stage_count": 0,
            "product_scope_acceptance_stage_ids": [],
            "product_scope_acceptance_ready_stage_ids": [],
            "product_scope_acceptance_blocked_stage_ids": [],
            "product_scope_acceptance_matrix": [],
            "product_scope_acceptance_current_blocked_stage_matrix": [],
            "product_scope_acceptance_stage_evidence_matrix": [],
            "product_scope_acceptance_stage_evidence_matrix_count": 0,
            "product_scope_acceptance_current_blocked_stage_evidence_matrix": [],
            "product_scope_acceptance_current_blocked_stage_evidence_matrix_count": 0,
            "product_scope_acceptance_release_blocker_stage_count": 0,
            "product_scope_acceptance_release_blocker_stage_ids": [],
            "product_scope_acceptance_next_stage_id": "",
            "product_scope_acceptance_next_stage_artifact": "",
            "product_scope_acceptance_next_stage_validation_command": "",
            "product_scope_acceptance_next_stage_release_effect": "",
            "product_scope_acceptance_next_stage_unlock_claim_scopes": [],
            "product_scope_acceptance_next_stage_required_checks": [],
            "product_scope_acceptance_next_stage_next_action": "",
            "product_scope_general_claim_blocker_count": 0,
            "product_scope_ready_for_apply_count": 0,
            "product_scope_authoritative_apply_allowed": False,
            "product_scope_domain_count": 0,
            "product_scope_ready_domain_count": 0,
            "product_scope_missing_domain_count": 0,
            "product_scope_ready_domains": [],
            "product_scope_missing_domains": [],
            "product_scope_first_blocked_domain": "",
            "product_scope_first_blocked_domain_artifact": "",
            "product_scope_first_blocked_domain_observed": "",
            "product_scope_first_blocked_domain_requirement": "",
            "product_scope_first_blocked_domain_next_action": "",
            "product_scope_transporter_p0_readiness_matrix_ready": False,
            "product_scope_transporter_p0_readiness_matrix_artifact": "",
            "product_scope_transporter_p0_auto_close_ready_artifact_count": 0,
            "product_scope_transporter_p0_manual_or_external_required_artifact_count": 0,
            "product_scope_transporter_p0_unresolved_slot_count": 0,
            "product_scope_transporter_p0_auto_close_ready_slot_count": 0,
            "product_scope_transporter_p0_external_exact_evidence_required_slot_count": 0,
            "product_scope_transporter_p0_first_manual_or_external_required_step_id": "",
            "product_scope_transporter_p0_first_manual_or_external_required_slot_step": "",
            "product_scope_transporter_p0_first_manual_or_external_required_action": "",
            "product_scope_transporter_p0_evidence_acquisition_packet_ready": False,
            "product_scope_transporter_p0_evidence_acquisition_artifact": "",
            "product_scope_transporter_p0_evidence_acquisition_exact_request_slot_count": 0,
            "product_scope_transporter_p0_evidence_acquisition_unresolved_slot_count": 0,
            "product_scope_transporter_p0_evidence_acquisition_first_target_id": "",
            "product_scope_transporter_p0_evidence_acquisition_first_packet_step": "",
            "product_scope_transporter_p0_evidence_acquisition_first_replacement_ligand_id": "",
            "product_scope_transporter_p0_evidence_acquisition_first_request_mode": "",
            "product_scope_transporter_p0_evidence_acquisition_first_source_signal": "",
            "product_scope_transporter_p0_evidence_acquisition_first_required_missing_fields": "",
            "product_scope_transporter_p0_evidence_acquisition_first_next_required_action": "",
            "product_scope_transporter_p0_evidence_acquisition_next_slot_completion_packet_ready": False,
            "product_scope_transporter_p0_evidence_acquisition_next_slot_completion_packet": {},
            "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifacts": [],
            "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifact_count": 0,
            "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix": [],
            "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix_count": 0,
            "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_blocker_count": 0,
            "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_id": "",
            "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_path": "",
            "product_scope_transporter_p0_evidence_acquisition_next_slot_id": "",
            "product_scope_transporter_p0_evidence_acquisition_next_slot_operator_review_artifact": "",
            "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_guard_ready": False,
            "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality": "",
            "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_claim_safe": False,
            "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_direct_binding_claim_allowed": False,
            "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_decision": "",
            "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_guardrails": [],
            "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_observed_signal": "",
            "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_required_upgrade": "",
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_source_count": 0,
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_result": "",
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_database_recheck_row_count": 0,
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_ligand_identity_mismatch_row_count": 0,
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_direct_like_binding_candidate_row_count": 0,
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_direct_like_binding_candidate_claim_safe_ready_count": 0,
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_candidate_chembl_id": "",
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_candidate_delta_g_kcal_mol": "",
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_candidate_blocker": "",
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bindingdb_aqp1_expanded_cutoff_affinity_row_count": 0,
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bindingdb_aqp1_expanded_cutoff_direct_like_affinity_row_count": 0,
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_pubchem_cid": "",
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_id": "",
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_chembl_target_id": "",
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_bindingdb_uniprot_affinity_row_count": 0,
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_aqp1_activity_row_count": 0,
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_functional_ic50_identity_mismatch_detail": "",
            "product_scope_general_platform_domain_floor_ready": False,
            "product_scope_general_platform_domain_floor_missing_domain_count": 0,
            "product_scope_general_platform_domain_floor_missing_domains": [],
            "product_scope_allowed_families": [],
            "product_scope_blocked_claim_scopes": [],
            "product_scope_claim_blocked_domains": [],
            "product_scope_general_platform_claim_allowed": False,
            "product_scope_evidence_priority_ready": False,
            "product_scope_evidence_priority_queue_item_count": 0,
            "product_scope_evidence_priority_open_item_count": 0,
            "product_scope_evidence_priority_local_crosscheck_candidate_count": 0,
            "product_scope_evidence_priority_external_primary_exact_required_count": 0,
            "product_scope_evidence_priority_top_item_id": "",
            "product_scope_evidence_priority_top_domain": "",
            "product_scope_evidence_priority_top_bucket": "",
            "product_scope_evidence_priority_top_next_step": "",
            "product_scope_evidence_priority_next_required_step": "",
            "product_scope_evidence_intake_ready": False,
            "product_scope_evidence_intake_row_count": 0,
            "product_scope_local_crosscheck_triage_item_count": 0,
            "product_scope_local_crosscheck_intake_ready_count": 0,
            "product_scope_external_exact_evidence_required_count": 0,
            "product_scope_guardrail_item_count": 0,
            "product_scope_transporter_triage_packet_ready": False,
            "product_scope_transporter_candidate_assignment_required_count": 0,
            "product_scope_transporter_functional_quantitative_only_direct_gap_open_count": 0,
            "product_scope_transporter_review_only_direct_binding_gap_count": 0,
            "product_scope_transporter_candidate_ready_for_manual_review_count": 0,
            "product_scope_transporter_candidate_ready_for_apply_count": 0,
            "product_scope_transporter_manual_review_intake_ready": False,
            "product_scope_transporter_manual_review_template_row_count": 0,
            "product_scope_transporter_manual_review_direct_binding_evidence_required_count": 0,
            "product_scope_transporter_manual_review_negative_quantitative_value_required_count": 0,
            "product_scope_transporter_manual_review_decision_placeholder_count": 0,
            "product_scope_transporter_manual_review_p0_slot_overlay_row_count": 0,
            "product_scope_transporter_manual_review_p0_slot_overlay_candidate_changed_count": 0,
            "product_scope_transporter_manual_review_p0_slot_overlay_first_item_id": "",
            "product_scope_transporter_manual_review_p0_slot_overlay_first_candidate_ligand_id": "",
            "product_scope_transporter_manual_review_p0_slot_overlay_first_source": "",
            "product_scope_transporter_manual_review_first_review_row_id": "",
            "product_scope_transporter_manual_review_first_review_item_id": "",
            "product_scope_transporter_manual_review_first_review_target_id": "",
            "product_scope_transporter_manual_review_first_review_candidate_ligand_id": "",
            "product_scope_transporter_manual_review_first_review_replacement_source": "",
            "product_scope_transporter_manual_review_first_review_replacement_reference_binding_kcal_mol": "",
            "product_scope_transporter_manual_review_first_review_direct_binding_evidence_required": False,
            "product_scope_transporter_manual_review_first_review_direct_binding_source_url_or_doi": "",
            "product_scope_transporter_manual_review_first_review_negative_quantitative_value_required": False,
            "product_scope_transporter_manual_review_first_review_negative_reference_binding_kcal_mol": "",
            "product_scope_transporter_manual_review_first_review_review_decision": "",
            "product_scope_transporter_manual_review_first_review_authoritative_apply_requested": "",
            "product_scope_transporter_manual_review_first_review_manual_review_blockers": "",
            "product_scope_transporter_manual_review_first_review_review_requirements": "",
            "product_scope_transporter_manual_review_first_review_p0_slot_overlay_required_missing_fields": "",
            "product_scope_transporter_manual_review_first_review_p0_slot_overlay_claim_safe_step_ready": False,
            "product_scope_transporter_manual_review_first_review_p0_slot_overlay_authoritative_apply_allowed": False,
            "product_scope_transporter_manual_review_first_review_p0_slot_overlay_scope_promotion_allowed": False,
            "product_scope_evidence_intake_next_required_step": "",
            "product_scope_pxr_exact_review_intake_ready": False,
            "product_scope_pxr_exact_review_template_row_count": 0,
            "product_scope_pxr_exact_review_expected_blocked_row_count": 0,
            "product_scope_pxr_exact_review_conflict_resolution_required_count": 0,
            "product_scope_pxr_exact_review_kcal_placeholder_count": 0,
            "product_scope_pxr_exact_review_source_placeholder_count": 0,
            "product_scope_pxr_exact_review_target_match_placeholder_count": 0,
            "product_scope_pxr_exact_review_decision_placeholder_count": 0,
            "product_scope_pxr_exact_review_next_review_completion_packet_ready": False,
            "product_scope_pxr_exact_review_next_review_completion_packet": {},
            "product_scope_pxr_exact_review_next_review_return_bundle_required_artifacts": [],
            "product_scope_pxr_exact_review_next_review_return_bundle_required_artifact_count": 0,
            "product_scope_pxr_exact_review_next_review_return_bundle_completion_matrix": [],
            "product_scope_pxr_exact_review_next_review_return_bundle_completion_matrix_count": 0,
            "product_scope_pxr_exact_review_next_review_return_bundle_blocker_count": 0,
            "product_scope_pxr_exact_review_next_review_return_bundle_next_artifact_id": "",
            "product_scope_pxr_exact_review_next_review_return_bundle_next_artifact_path": "",
            "product_scope_pxr_exact_review_next_review_return_bundle_next_artifact_failed_check_ids": [],
            "product_scope_pxr_exact_review_next_review_row_id": "",
            "product_scope_pxr_exact_review_next_review_candidate_name": "",
            "product_scope_pxr_exact_review_next_review_operator_review_artifact": "",
            "product_scope_pxr_exact_review_next_required_step": "",
            "product_scope_pxr_source_modality_triage_ready": False,
            "product_scope_pxr_source_modality_triage_status": "",
            "product_scope_pxr_source_modality_triage_artifact": "",
            "product_scope_pxr_source_modality_triage_decision": "",
            "product_scope_pxr_source_modality_public_evidence_recheck_ready": False,
            "product_scope_pxr_source_modality_public_recheck_artifact": "",
            "product_scope_pxr_source_modality_public_recheck_candidate_count": 0,
            "product_scope_pxr_source_modality_public_recheck_chembl_direct_binding_total_record_count": 0,
            "product_scope_pxr_source_modality_public_recheck_chembl_functional_activity_total_record_count": 0,
            "product_scope_pxr_source_modality_public_recheck_bindingdb_pxr_like_total_record_count": 0,
            "product_scope_pxr_source_modality_public_recheck_direct_or_claim_safe_binding_kcal_ready_count": 0,
            "product_scope_pxr_source_modality_public_recheck_all_candidates_remain_blocked": False,
            "product_scope_pxr_source_modality_public_recheck_first_blocked_candidate_name": "",
            "product_scope_pxr_source_modality_public_recheck_first_blocked_reason": "",
            "product_scope_pxr_source_modality_direct_replacement_candidate_packet_ready": False,
            "product_scope_pxr_source_modality_direct_replacement_artifact": "",
            "product_scope_pxr_source_modality_direct_replacement_candidate_count": 0,
            "product_scope_pxr_source_modality_direct_replacement_selected_candidate_count": 0,
            "product_scope_pxr_source_modality_direct_replacement_selected_claim_safe_candidate_count": 0,
            "product_scope_pxr_source_modality_direct_replacement_first_ligand_id": "",
            "product_scope_pxr_source_modality_direct_replacement_first_molecule_chembl_id": "",
            "product_scope_pxr_source_modality_direct_replacement_first_reference_binding_kcal_mol": "",
            "product_scope_pxr_source_modality_direct_replacement_first_source": "",
            "product_scope_pxr_source_modality_direct_replacement_apply_draft_ready": False,
            "product_scope_pxr_source_modality_direct_replacement_apply_draft_status": "",
            "product_scope_pxr_source_modality_direct_replacement_apply_draft_artifact": "",
            "product_scope_pxr_source_modality_direct_replacement_apply_draft_workbook_row_count": 0,
            "product_scope_pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_before_draft": 0,
            "product_scope_pxr_source_modality_direct_replacement_apply_draft_overlay_row_count": 0,
            "product_scope_pxr_source_modality_direct_replacement_apply_draft_ready_for_apply_row_count_after_draft": 0,
            "product_scope_pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_after_draft": 0,
            "product_scope_pxr_source_modality_direct_replacement_apply_draft_first_overlay_ligand_id": "",
            "product_scope_pxr_source_modality_direct_replacement_apply_draft_authoritative_fields_touched": False,
            "product_scope_pxr_source_modality_activity_proxy_or_conflict_surrogate_row_count": 0,
            "product_scope_pxr_source_modality_direct_or_claim_safe_quantitative_ready_count": 0,
            "product_scope_pxr_source_modality_accepted_for_scope_promotion_count": 0,
            "product_scope_pxr_source_modality_next_review_row_id": "",
            "product_scope_pxr_source_modality_next_review_candidate_name": "",
            "product_scope_pxr_source_modality_next_review_source_modality": "",
            "product_scope_pxr_source_modality_next_review_rejection_reason": "",
            "requirements": [],
            "execution_enabled": False,
            "docking_results_emitted": False,
            "license_file_written": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product goal-completion-audit endpoint only; the local completion audit artifact is missing or invalid. "
                "It does not choose a license, run docking, create files, submit predictions, or mutate external state."
            ),
            "release_complete_vs_operator_pending_lane": lane_surface["release_complete_vs_operator_pending_lane"],
            "goal_completion_audit_goal_complete": lane_surface["goal_completion_audit_goal_complete"],
            "release_complete_lane_ready": lane_surface["release_complete_lane_ready"],
            "operator_pending_lane_ready": lane_surface["operator_pending_lane_ready"],
            "operator_or_external_pending_lane_count": lane_surface["operator_or_external_pending_lane_count"],
            "release_complete_vs_operator_pending_matrix": lane_surface["release_complete_vs_operator_pending_matrix"],
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_GOAL_COMPLETION_AUDIT_ARTIFACT),
        "goal_complete": bool(summary.get("goal_complete") is True),
        "requirement_count": int(summary.get("requirement_count") or 0),
        "pass_count": int(summary.get("pass_count") or 0),
        "fail_count": int(summary.get("fail_count") or 0),
        "primary_bottleneck_phase": summary.get("primary_bottleneck_phase", ""),
        "primary_bottleneck_kind": summary.get("primary_bottleneck_kind", ""),
        "approval_tokens_required": list(summary.get("approval_tokens_required") or []),
        "next_command": summary.get("next_command", ""),
        "next_command_candidate_count": int(summary.get("next_command_candidate_count") or 0),
        "next_command_candidates": list(summary.get("next_command_candidates") or []),
        "release_allowed": bool(summary.get("release_allowed") is True),
        "commercial_independence_ready": bool(summary.get("commercial_independence_ready") is True),
        "public_benchmark_validation_ready": bool(summary.get("public_benchmark_validation_ready") is True),
        "local_self_hosted_product_ready": bool(summary.get("local_self_hosted_product_ready") is True),
        "cameo_optional_live_validation_ready": bool(summary.get("cameo_optional_live_validation_ready") is True),
        "release_artifact_ready": bool(summary.get("release_artifact_ready") is True),
        "product_ai_architecture_ready": bool(summary.get("product_ai_architecture_ready") is True),
        "product_ai_architecture_gap_status": summary.get("product_ai_architecture_gap_status", ""),
        "product_ai_architecture_all_gaps_closed": bool(
            summary.get("product_ai_architecture_all_gaps_closed") is True
        ),
        "product_ai_architecture_gap_count": int(summary.get("product_ai_architecture_gap_count") or 0),
        "product_ai_architecture_closed_gap_count": int(
            summary.get("product_ai_architecture_closed_gap_count") or 0
        ),
        "product_ai_architecture_open_gap_count": int(summary.get("product_ai_architecture_open_gap_count") or 0),
        "product_ai_architecture_open_gap_ids": list(summary.get("product_ai_architecture_open_gap_ids") or []),
        "product_ai_architecture_closed_gap_ids": list(summary.get("product_ai_architecture_closed_gap_ids") or []),
        "product_ai_architecture_gap_blocker_matrix_ready": bool(
            summary.get("product_ai_architecture_gap_blocker_matrix_ready") is True
        ),
        "product_ai_architecture_gap_blocker_matrix_count": int(
            summary.get("product_ai_architecture_gap_blocker_matrix_count") or 0
        ),
        "product_ai_architecture_gap_blocker_matrix": list(
            summary.get("product_ai_architecture_gap_blocker_matrix") or []
        ),
        "product_ai_architecture_current_primary_blocker_gap_id": summary.get(
            "product_ai_architecture_current_primary_blocker_gap_id", ""
        ),
        "product_ai_architecture_current_primary_blocker_id": summary.get(
            "product_ai_architecture_current_primary_blocker_id", ""
        ),
        "product_ai_architecture_current_primary_blocker_artifact": summary.get(
            "product_ai_architecture_current_primary_blocker_artifact", ""
        ),
        "product_ai_architecture_current_primary_blocker_validation_command": summary.get(
            "product_ai_architecture_current_primary_blocker_validation_command", ""
        ),
        "product_ai_architecture_current_primary_blocker_next_action": summary.get(
            "product_ai_architecture_current_primary_blocker_next_action", ""
        ),
        "product_ai_architecture_current_primary_blocker_operator_input_fields": list(
            summary.get("product_ai_architecture_current_primary_blocker_operator_input_fields") or []
        ),
        "product_ai_architecture_current_primary_blocker_unlock_claim": summary.get(
            "product_ai_architecture_current_primary_blocker_unlock_claim", ""
        ),
        "product_ai_architecture_current_primary_blocker_next_after_stage_id": summary.get(
            "product_ai_architecture_current_primary_blocker_next_after_stage_id", ""
        ),
        "product_ai_architecture_current_primary_blocker_next_after_artifact": summary.get(
            "product_ai_architecture_current_primary_blocker_next_after_artifact", ""
        ),
        "product_ai_architecture_current_primary_blocker_next_after_validation_command": summary.get(
            "product_ai_architecture_current_primary_blocker_next_after_validation_command", ""
        ),
        "product_ai_architecture_current_primary_blocker_next_after_next_action": summary.get(
            "product_ai_architecture_current_primary_blocker_next_after_next_action", ""
        ),
        "product_ai_architecture_current_primary_blocker_next_after_required_checks": list(
            summary.get("product_ai_architecture_current_primary_blocker_next_after_required_checks")
            or []
        ),
        "product_ai_architecture_current_primary_blocker_next_after_unlock_fields": list(
            summary.get("product_ai_architecture_current_primary_blocker_next_after_unlock_fields")
            or []
        ),
        "product_ai_architecture_parallelizable_gap_blocker_count": int(
            summary.get("product_ai_architecture_parallelizable_gap_blocker_count") or 0
        ),
        "product_ai_architecture_parallelizable_gap_blocker_ids": list(
            summary.get("product_ai_architecture_parallelizable_gap_blocker_ids") or []
        ),
        "product_ai_architecture_first_parallelizable_gap_id": summary.get(
            "product_ai_architecture_first_parallelizable_gap_id", ""
        ),
        "product_ai_architecture_first_parallelizable_blocker_id": summary.get(
            "product_ai_architecture_first_parallelizable_blocker_id", ""
        ),
        "product_ai_architecture_first_parallelizable_blocker_artifact": summary.get(
            "product_ai_architecture_first_parallelizable_blocker_artifact", ""
        ),
        "product_ai_architecture_first_parallelizable_blocker_next_action": summary.get(
            "product_ai_architecture_first_parallelizable_blocker_next_action", ""
        ),
        "product_ai_architecture_first_parallelizable_blocker_validation_command": summary.get(
            "product_ai_architecture_first_parallelizable_blocker_validation_command", ""
        ),
        "product_ai_architecture_first_parallelizable_blocker_operator_input_fields": list(
            summary.get("product_ai_architecture_first_parallelizable_blocker_operator_input_fields")
            or []
        ),
        "product_ai_architecture_first_parallelizable_blocker_required_exact_evidence_fields": list(
            summary.get(
                "product_ai_architecture_first_parallelizable_blocker_required_exact_evidence_fields"
            )
            or []
        ),
        "product_ai_architecture_first_parallelizable_blocker_required_claim_guardrails": list(
            summary.get("product_ai_architecture_first_parallelizable_blocker_required_claim_guardrails")
            or []
        ),
        "product_ai_architecture_first_parallelizable_blocker_claim_safe_completion_rule": summary.get(
            "product_ai_architecture_first_parallelizable_blocker_claim_safe_completion_rule", ""
        ),
        "product_ai_architecture_first_parallelizable_blocker_unlock_claim": summary.get(
            "product_ai_architecture_first_parallelizable_blocker_unlock_claim", ""
        ),
        "product_ai_architecture_first_parallelizable_blocker_source_modality_triage_artifact": summary.get(
            "product_ai_architecture_first_parallelizable_blocker_source_modality_triage_artifact", ""
        ),
        "product_ai_architecture_first_parallelizable_blocker_source_modality_triage_decision": summary.get(
            "product_ai_architecture_first_parallelizable_blocker_source_modality_triage_decision", ""
        ),
        "product_ai_architecture_first_parallelizable_blocker_source_modality_direct_experimental_binding_row_count": int(
            summary.get(
                "product_ai_architecture_first_parallelizable_blocker_source_modality_direct_experimental_binding_row_count"
            )
            or 0
        ),
        "product_ai_architecture_first_parallelizable_blocker_source_modality_claim_safe_binding_kcal_ready_count": int(
            summary.get(
                "product_ai_architecture_first_parallelizable_blocker_source_modality_claim_safe_binding_kcal_ready_count"
            )
            or 0
        ),
        "product_ai_architecture_first_parallelizable_blocker_source_modality_computational_binding_energy_row_count": int(
            summary.get(
                "product_ai_architecture_first_parallelizable_blocker_source_modality_computational_binding_energy_row_count"
            )
            or 0
        ),
        "product_ai_architecture_first_parallelizable_blocker_source_modality_best_computational_binding_energy_kcal_mol": summary.get(
            "product_ai_architecture_first_parallelizable_blocker_source_modality_best_computational_binding_energy_kcal_mol",
            "",
        ),
        "commercial_readiness_next_action_matrix_ready": bool(
            summary.get("commercial_readiness_next_action_matrix_ready") is True
        ),
        "commercial_readiness_next_action_matrix": list(
            summary.get("commercial_readiness_next_action_matrix") or []
        ),
        "commercial_readiness_next_action_matrix_count": int(
            summary.get("commercial_readiness_next_action_matrix_count") or 0
        ),
        "commercial_readiness_next_action_blocker_matrix": list(
            summary.get("commercial_readiness_next_action_blocker_matrix") or []
        ),
        "commercial_readiness_next_action_blocker_count": int(
            summary.get("commercial_readiness_next_action_blocker_count") or 0
        ),
        "commercial_readiness_first_next_action_id": summary.get(
            "commercial_readiness_first_next_action_id", ""
        ),
        "commercial_readiness_first_next_action_artifact": summary.get(
            "commercial_readiness_first_next_action_artifact", ""
        ),
        "commercial_readiness_first_next_action_validation_command": summary.get(
            "commercial_readiness_first_next_action_validation_command", ""
        ),
        "commercial_readiness_handoff_bundle_status": summary.get(
            "commercial_readiness_handoff_bundle_status", ""
        ),
        "commercial_readiness_handoff_bundle_artifact_path": summary.get(
            "commercial_readiness_handoff_bundle_artifact_path", ""
        ),
        "commercial_readiness_handoff_bundle_ready": bool(
            summary.get("commercial_readiness_handoff_bundle_ready") is True
        ),
        "commercial_readiness_handoff_bundle_artifact_count": int(
            summary.get("commercial_readiness_handoff_bundle_artifact_count") or 0
        ),
        "commercial_readiness_handoff_bundle_blocked_artifact_count": int(
            summary.get("commercial_readiness_handoff_bundle_blocked_artifact_count") or 0
        ),
        "commercial_readiness_handoff_bundle_blocked_artifact_ids": list(
            summary.get("commercial_readiness_handoff_bundle_blocked_artifact_ids") or []
        ),
        "commercial_readiness_handoff_bundle_artifact_reference_contract_ready": bool(
            summary.get("commercial_readiness_handoff_bundle_artifact_reference_contract_ready")
            is True
        ),
        "commercial_readiness_handoff_bundle_artifact_reference_count": int(
            summary.get("commercial_readiness_handoff_bundle_artifact_reference_count") or 0
        ),
        "commercial_readiness_handoff_bundle_local_missing_artifact_reference_count": int(
            summary.get("commercial_readiness_handoff_bundle_local_missing_artifact_reference_count")
            or 0
        ),
        "commercial_readiness_handoff_bundle_operator_return_pending_artifact_reference_count": int(
            summary.get(
                "commercial_readiness_handoff_bundle_operator_return_pending_artifact_reference_count"
            )
            or 0
        ),
        "commercial_readiness_handoff_bundle_first_action_id": summary.get(
            "commercial_readiness_handoff_bundle_first_action_id", ""
        ),
        "commercial_readiness_handoff_bundle_first_operator_input_artifact": summary.get(
            "commercial_readiness_handoff_bundle_first_operator_input_artifact", ""
        ),
        "commercial_readiness_handoff_bundle_next_required_step": summary.get(
            "commercial_readiness_handoff_bundle_next_required_step", ""
        ),
        "product_ai_production_checkpoint_gap_ready": bool(
            summary.get("product_ai_production_checkpoint_gap_ready") is True
        ),
        "product_ai_production_checkpoint_gap_observed": summary.get(
            "product_ai_production_checkpoint_gap_observed", ""
        ),
        "product_ai_closed_loop_decision_graph_ready": bool(
            summary.get("product_ai_closed_loop_decision_graph_ready") is True
        ),
        "product_ai_closed_loop_decision_graph_observed": summary.get(
            "product_ai_closed_loop_decision_graph_observed", ""
        ),
        "product_ai_durable_job_orchestration_ready": bool(
            summary.get("product_ai_durable_job_orchestration_ready") is True
        ),
        "product_ai_durable_job_orchestration_observed": summary.get(
            "product_ai_durable_job_orchestration_observed", ""
        ),
        "product_ai_trajectory_sla_ready": bool(summary.get("product_ai_trajectory_sla_ready") is True),
        "product_ai_trajectory_sla_observed": summary.get("product_ai_trajectory_sla_observed", ""),
        "product_ai_trajectory_sla_claim_tier": summary.get("product_ai_trajectory_sla_claim_tier", ""),
        "product_ai_trajectory_sla_restricted_family_allowed": bool(
            summary.get("product_ai_trajectory_sla_restricted_family_allowed") is True
        ),
        "product_ai_trajectory_sla_broad_platform_allowed": bool(
            summary.get("product_ai_trajectory_sla_broad_platform_allowed") is True
        ),
        "product_ai_trajectory_sla_current_rocm_baseline_claim_scope": summary.get(
            "product_ai_trajectory_sla_current_rocm_baseline_claim_scope", ""
        ),
        "product_ai_trajectory_sla_current_rocm_baseline_production_profile_enabled": bool(
            summary.get("product_ai_trajectory_sla_current_rocm_baseline_production_profile_enabled") is True
        ),
        "product_ai_trajectory_sla_rocm_baseline_profile_gap_acknowledged": bool(
            summary.get("product_ai_trajectory_sla_rocm_baseline_profile_gap_acknowledged") is True
        ),
        "product_ai_scope_breadth_ready": bool(summary.get("product_ai_scope_breadth_ready") is True),
        "product_ai_scope_breadth_observed": summary.get("product_ai_scope_breadth_observed", ""),
        "product_scope_evidence_queue_next_operator_completion_packet_ready": bool(
            summary.get("product_scope_evidence_queue_next_operator_completion_packet_ready") is True
        ),
        "product_scope_evidence_queue_next_operator_completion_slot_id": summary.get(
            "product_scope_evidence_queue_next_operator_completion_slot_id", ""
        ),
        "product_scope_evidence_queue_next_operator_completion_expected_evidence_type": summary.get(
            "product_scope_evidence_queue_next_operator_completion_expected_evidence_type", ""
        ),
        "product_scope_evidence_queue_next_operator_completion_required_exact_evidence_field_count": int(
            summary.get(
                "product_scope_evidence_queue_next_operator_completion_required_exact_evidence_field_count",
                0,
            )
            or 0
        ),
        "product_scope_evidence_queue_next_operator_completion_required_exact_evidence_fields": summary.get(
            "product_scope_evidence_queue_next_operator_completion_required_exact_evidence_fields", ""
        ),
        "product_scope_evidence_queue_next_operator_completion_required_operator_intake_columns": summary.get(
            "product_scope_evidence_queue_next_operator_completion_required_operator_intake_columns", ""
        ),
        "product_scope_evidence_queue_next_operator_completion_required_claim_guardrails": summary.get(
            "product_scope_evidence_queue_next_operator_completion_required_claim_guardrails", ""
        ),
        "product_scope_evidence_queue_next_operator_completion_operator_review_artifact": summary.get(
            "product_scope_evidence_queue_next_operator_completion_operator_review_artifact", ""
        ),
        "product_scope_evidence_queue_next_operator_completion_post_intake_synchronization_targets": summary.get(
            "product_scope_evidence_queue_next_operator_completion_post_intake_synchronization_targets", ""
        ),
        "product_scope_evidence_queue_next_operator_completion_acceptance_gate_commands": summary.get(
            "product_scope_evidence_queue_next_operator_completion_acceptance_gate_commands", ""
        ),
        "product_scope_evidence_queue_next_operator_completion_contract_artifact": summary.get(
            "product_scope_evidence_queue_next_operator_completion_contract_artifact", ""
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_sidecar_ready": bool(
            summary.get(
                "product_scope_evidence_queue_next_operator_completion_aqp1_review_sidecar_ready"
            )
            is True
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_functional_surrogate_artifact": summary.get(
            "product_scope_evidence_queue_next_operator_completion_aqp1_functional_surrogate_artifact",
            "",
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_candidate_ledger_artifact": summary.get(
            "product_scope_evidence_queue_next_operator_completion_aqp1_candidate_ledger_artifact",
            "",
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_candidate_name": summary.get(
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_candidate_name", ""
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_source_anchor": summary.get(
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_source_anchor", ""
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_source_url": summary.get(
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_source_url", ""
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_target_uniprot": summary.get(
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_target_uniprot", ""
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_functional_measure": summary.get(
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_functional_measure",
            "",
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_functional_delta_g_surrogate_kcal_mol": summary.get(
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_functional_delta_g_surrogate_kcal_mol",
            "",
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_assay_type_honesty": summary.get(
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_assay_type_honesty",
            "",
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_direct_binding_claim_allowed": summary.get(
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_direct_binding_claim_allowed",
            "",
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_binding_kcal_claim_allowed": summary.get(
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_binding_kcal_claim_allowed",
            "",
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_replacement_reference_binding_kcal_mol_must_remain_blank": summary.get(
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_replacement_reference_binding_kcal_mol_must_remain_blank",
            "",
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_claim_safe_functional_kcal_ready": summary.get(
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_claim_safe_functional_kcal_ready",
            "",
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_ledger_review_bucket": summary.get(
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_ledger_review_bucket",
            "",
        ),
        "product_scope_evidence_queue_next_operator_completion_aqp1_review_ledger_promotion_policy": summary.get(
            "product_scope_evidence_queue_next_operator_completion_aqp1_review_ledger_promotion_policy",
            "",
        ),
        "product_scope_evidence_queue_pxr_exact_review_sidecar_row_count": int(
            summary.get("product_scope_evidence_queue_pxr_exact_review_sidecar_row_count") or 0
        ),
        "product_scope_evidence_queue_next_pxr_exact_review_sidecar_ready": bool(
            summary.get("product_scope_evidence_queue_next_pxr_exact_review_sidecar_ready") is True
        ),
        "product_scope_evidence_queue_next_pxr_exact_review_row_id": summary.get(
            "product_scope_evidence_queue_next_pxr_exact_review_row_id", ""
        ),
        "product_scope_evidence_queue_next_pxr_exact_review_candidate_name": summary.get(
            "product_scope_evidence_queue_next_pxr_exact_review_candidate_name", ""
        ),
        "product_scope_evidence_queue_next_pxr_exact_review_required_evidence_mode": summary.get(
            "product_scope_evidence_queue_next_pxr_exact_review_required_evidence_mode", ""
        ),
        "product_scope_evidence_queue_next_pxr_exact_review_target_match_confirmed": summary.get(
            "product_scope_evidence_queue_next_pxr_exact_review_target_match_confirmed", ""
        ),
        "product_scope_evidence_queue_next_pxr_exact_review_replacement_reference_binding_kcal_mol": summary.get(
            "product_scope_evidence_queue_next_pxr_exact_review_replacement_reference_binding_kcal_mol",
            "",
        ),
        "product_scope_evidence_queue_next_pxr_exact_review_replacement_source_url_or_doi": summary.get(
            "product_scope_evidence_queue_next_pxr_exact_review_replacement_source_url_or_doi",
            "",
        ),
        "product_scope_evidence_queue_next_pxr_exact_review_authoritative_apply_allowed": bool(
            summary.get("product_scope_evidence_queue_next_pxr_exact_review_authoritative_apply_allowed") is True
        ),
        "product_scope_evidence_queue_next_pxr_exact_review_scope_promotion_allowed": bool(
            summary.get("product_scope_evidence_queue_next_pxr_exact_review_scope_promotion_allowed") is True
        ),
        "product_ai_report_ux_ready": bool(summary.get("product_ai_report_ux_ready") is True),
        "product_ai_report_ux_observed": summary.get("product_ai_report_ux_observed", ""),
        "product_ai_report_ux_customer_report_delivery_contract_ready": bool(
            summary.get("product_ai_report_ux_customer_report_delivery_contract_ready") is True
        ),
        "product_ai_report_ux_customer_report_evidence_binding_ready": bool(
            summary.get("product_ai_report_ux_customer_report_evidence_binding_ready") is True
        ),
        "product_ai_report_ux_customer_report_viewer_binding_ready": bool(
            summary.get("product_ai_report_ux_customer_report_viewer_binding_ready") is True
        ),
        "product_ai_report_ux_viewer_customer_report_binding_ready": bool(
            summary.get("product_ai_report_ux_viewer_customer_report_binding_ready") is True
        ),
        "product_ai_report_ux_customer_report_ready_block_count": int(
            summary.get("product_ai_report_ux_customer_report_ready_block_count") or 0
        ),
        "product_ai_report_ux_customer_report_required_block_count": int(
            summary.get("product_ai_report_ux_customer_report_required_block_count") or 0
        ),
        "product_ai_report_ux_customer_report_blocked_block_count": int(
            summary.get("product_ai_report_ux_customer_report_blocked_block_count") or 0
        ),
        "product_ai_security_deployment_ready": bool(
            summary.get("product_ai_security_deployment_ready") is True
        ),
        "product_ai_security_deployment_observed": summary.get("product_ai_security_deployment_observed", ""),
        "product_ai_security_hosted_deployment_contract_ready": bool(
            summary.get("product_ai_security_hosted_deployment_contract_ready") is True
        ),
        "product_ai_security_hosted_deployment_currently_satisfied": bool(
            summary.get("product_ai_security_hosted_deployment_currently_satisfied") is True
        ),
        "product_ai_security_hosted_deployment_next_stage_id": summary.get(
            "product_ai_security_hosted_deployment_next_stage_id", ""
        ),
        "product_ai_security_hosted_external_exposure_allowed": bool(
            summary.get("product_ai_security_hosted_external_exposure_allowed") is True
        ),
        "product_ai_security_hosted_secret_injection_ready": bool(
            summary.get("product_ai_security_hosted_secret_injection_ready") is True
        ),
        "product_ai_security_tls_termination_operator_verified": bool(
            summary.get("product_ai_security_tls_termination_operator_verified") is True
        ),
        "production_ai_inference_subject_active": bool(
            registry.get("production_promotion_allowed") is True
            and registry.get("customer_facing_auto_correction_allowed") is True
            and registry.get("customer_facing_score_mutation_allowed") is True
            and registry.get("customer_facing_ranking_mutation_allowed") is True
            and registry.get("trained_model_checkpoint_count")
            and str(registry.get("default_residual_mode") or "") in {"assist", "production", "production_guarded"}
        ),
        "production_ai_default_residual_mode": registry.get("default_residual_mode", ""),
        "production_ai_promotion_allowed": bool(registry.get("production_promotion_allowed") is True),
        "production_ai_customer_facing_auto_correction_allowed": bool(
            registry.get("customer_facing_auto_correction_allowed") is True
        ),
        "production_ai_customer_facing_score_mutation_allowed": bool(
            registry.get("customer_facing_score_mutation_allowed") is True
        ),
        "production_ai_customer_facing_ranking_mutation_allowed": bool(
            registry.get("customer_facing_ranking_mutation_allowed") is True
        ),
        "production_ai_trained_checkpoint_count": int(registry.get("trained_model_checkpoint_count") or 0),
        "production_ai_selected_sidecar_ready": bool(registry.get("selected_sidecar_ready") is True),
        "production_ai_selected_sidecar_missing_output_fields": list(
            registry.get("selected_sidecar_missing_output_fields") or []
        ),
        "production_ai_blocked_reason": registry.get("production_promotion_blocked_reason", ""),
        "production_ai_residual_model_registry_status": summary.get(
            "production_ai_residual_model_registry_status", registry.get("status", "")
        ),
        "production_ai_residual_model_registry_artifact_path": summary.get(
            "production_ai_residual_model_registry_artifact_path", str(RESIDUAL_MODEL_REGISTRY_ARTIFACT)
        ),
        "production_ai_residual_model_registry_ready": bool(
            summary.get("production_ai_residual_model_registry_ready") is True
            or registry.get("registry_ready") is True
        ),
        "production_ai_product_model_layer_ready": bool(
            summary.get("production_ai_product_model_layer_ready") is True
            or registry.get("product_model_layer_ready") is True
        ),
        "production_ai_registry_checkpoint_preflight_ready": bool(
            summary.get("production_ai_registry_checkpoint_preflight_ready") is True
            or registry.get("checkpoint_preflight_ready") is True
        ),
        "production_ai_registry_production_checkpoint_blocked": bool(
            summary.get("production_ai_registry_production_checkpoint_blocked") is True
            or registry.get("production_checkpoint_blocked") is True
        ),
        "production_ai_registry_checkpoint_primary_blocker": summary.get(
            "production_ai_registry_checkpoint_primary_blocker", registry.get("checkpoint_primary_blocker", "")
        ),
        "production_ai_registry_checkpoint_missing_output_fields": list(
            summary.get("production_ai_registry_checkpoint_missing_output_fields")
            or registry.get("checkpoint_missing_output_fields")
            or []
        ),
        "production_ai_registry_checkpoint_missing_adapter_output_policy_fields": list(
            summary.get("production_ai_registry_checkpoint_missing_adapter_output_policy_fields")
            or registry.get("checkpoint_missing_adapter_output_policy_fields")
            or []
        ),
        "product_ai_primary_backlog_detail": summary.get("product_ai_primary_backlog_detail", ""),
        "product_ai_primary_backlog_work_item_id": summary.get("product_ai_primary_backlog_work_item_id", ""),
        "product_ai_primary_backlog_acceptance_criteria": summary.get(
            "product_ai_primary_backlog_acceptance_criteria", ""
        ),
        "product_ai_primary_backlog_next_action": summary.get("product_ai_primary_backlog_next_action", ""),
        "product_ai_primary_backlog_source_artifact": summary.get("product_ai_primary_backlog_source_artifact", ""),
        "product_ai_primary_backlog_verification_command": summary.get(
            "product_ai_primary_backlog_verification_command", ""
        ),
        "production_ai_gpu_worker_return_receipt_ready": bool(
            summary.get("production_ai_gpu_worker_return_receipt_ready") is True
        ),
        "production_ai_gpu_worker_return_receipt_blockers": list(
            summary.get("production_ai_gpu_worker_return_receipt_blockers") or []
        ),
        "production_ai_gpu_expected_queue_rows": int(summary.get("production_ai_gpu_expected_queue_rows") or 0),
        "production_ai_gpu_manifest_ok_row_count": int(
            summary.get("production_ai_gpu_manifest_ok_row_count") or 0
        ),
        "production_ai_gpu_manifest_status_placeholder_count": int(
            summary.get("production_ai_gpu_manifest_status_placeholder_count") or 0
        ),
        "production_ai_gpu_manifest_status_invalid_count": int(
            summary.get("production_ai_gpu_manifest_status_invalid_count") or 0
        ),
        "production_ai_gpu_manifest_npz_paths_complete": bool(
            summary.get("production_ai_gpu_manifest_npz_paths_complete") is True
        ),
        "production_ai_gpu_manifest_npz_files_exist": bool(
            summary.get("production_ai_gpu_manifest_npz_files_exist") is True
        ),
        "production_ai_gpu_manifest_npz_files_valid": bool(
            summary.get("production_ai_gpu_manifest_npz_files_valid") is True
        ),
        "production_ai_gpu_manifest_npz_schema_valid": bool(
            summary.get("production_ai_gpu_manifest_npz_schema_valid") is True
        ),
        "production_ai_gpu_manifest_npz_identity_valid": bool(
            summary.get("production_ai_gpu_manifest_npz_identity_valid") is True
        ),
        "production_ai_gpu_manifest_npz_path_present_count": int(
            summary.get("production_ai_gpu_manifest_npz_path_present_count") or 0
        ),
        "production_ai_gpu_manifest_npz_path_missing_count": int(
            summary.get("production_ai_gpu_manifest_npz_path_missing_count") or 0
        ),
        "production_ai_gpu_manifest_ok_row_missing_npz_path_count": int(
            summary.get("production_ai_gpu_manifest_ok_row_missing_npz_path_count") or 0
        ),
        "production_ai_gpu_manifest_operator_verified_missing_npz_path_count": int(
            summary.get("production_ai_gpu_manifest_operator_verified_missing_npz_path_count") or 0
        ),
        "production_ai_gpu_manifest_npz_file_existing_count": int(
            summary.get("production_ai_gpu_manifest_npz_file_existing_count") or 0
        ),
        "production_ai_gpu_manifest_npz_file_missing_count": int(
            summary.get("production_ai_gpu_manifest_npz_file_missing_count") or 0
        ),
        "production_ai_gpu_manifest_ok_row_missing_npz_file_count": int(
            summary.get("production_ai_gpu_manifest_ok_row_missing_npz_file_count") or 0
        ),
        "production_ai_gpu_manifest_operator_verified_missing_npz_file_count": int(
            summary.get("production_ai_gpu_manifest_operator_verified_missing_npz_file_count") or 0
        ),
        "production_ai_gpu_manifest_npz_file_valid_count": int(
            summary.get("production_ai_gpu_manifest_npz_file_valid_count") or 0
        ),
        "production_ai_gpu_manifest_npz_file_invalid_count": int(
            summary.get("production_ai_gpu_manifest_npz_file_invalid_count") or 0
        ),
        "production_ai_gpu_manifest_ok_row_invalid_npz_file_count": int(
            summary.get("production_ai_gpu_manifest_ok_row_invalid_npz_file_count") or 0
        ),
        "production_ai_gpu_manifest_operator_verified_invalid_npz_file_count": int(
            summary.get("production_ai_gpu_manifest_operator_verified_invalid_npz_file_count") or 0
        ),
        "production_ai_gpu_manifest_npz_schema_valid_count": int(
            summary.get("production_ai_gpu_manifest_npz_schema_valid_count") or 0
        ),
        "production_ai_gpu_manifest_npz_schema_invalid_count": int(
            summary.get("production_ai_gpu_manifest_npz_schema_invalid_count") or 0
        ),
        "production_ai_gpu_manifest_ok_row_invalid_npz_schema_count": int(
            summary.get("production_ai_gpu_manifest_ok_row_invalid_npz_schema_count") or 0
        ),
        "production_ai_gpu_manifest_operator_verified_invalid_npz_schema_count": int(
            summary.get("production_ai_gpu_manifest_operator_verified_invalid_npz_schema_count") or 0
        ),
        "production_ai_gpu_manifest_npz_identity_valid_count": int(
            summary.get("production_ai_gpu_manifest_npz_identity_valid_count") or 0
        ),
        "production_ai_gpu_manifest_npz_identity_invalid_count": int(
            summary.get("production_ai_gpu_manifest_npz_identity_invalid_count") or 0
        ),
        "production_ai_gpu_manifest_ok_row_invalid_npz_identity_count": int(
            summary.get("production_ai_gpu_manifest_ok_row_invalid_npz_identity_count") or 0
        ),
        "production_ai_gpu_manifest_operator_verified_invalid_npz_identity_count": int(
            summary.get("production_ai_gpu_manifest_operator_verified_invalid_npz_identity_count") or 0
        ),
        "production_ai_gpu_manifest_operator_verified": bool(
            summary.get("production_ai_gpu_manifest_operator_verified") is True
        ),
        "production_ai_gpu_operator_verified_true_count": int(
            summary.get("production_ai_gpu_operator_verified_true_count") or 0
        ),
        "production_ai_gpu_operator_verification_column_present": bool(
            summary.get("production_ai_gpu_operator_verification_column_present") is True
        ),
        "production_ai_gpu_identity_coverage_ready": bool(
            summary.get("production_ai_gpu_identity_coverage_ready") is True
        ),
        "production_ai_gpu_matched_queue_fingerprints": int(
            summary.get("production_ai_gpu_matched_queue_fingerprints") or 0
        ),
        "production_ai_gpu_queue_fingerprints": int(summary.get("production_ai_gpu_queue_fingerprints") or 0),
        "production_ai_force_derivation_input_ready": bool(
            summary.get("production_ai_force_derivation_input_ready") is True
        ),
        "production_ai_delta_force_derivation_validation_ready": bool(
            summary.get("production_ai_delta_force_derivation_validation_ready") is True
        ),
        "production_ai_missing_output_labels": list(summary.get("production_ai_missing_output_labels") or []),
        "production_ai_checkpoint_readiness_status": summary.get("production_ai_checkpoint_readiness_status", ""),
        "production_ai_checkpoint_ready": bool(summary.get("production_ai_checkpoint_ready") is True),
        "production_ai_checkpoint_output_head_gap_contract_ready": bool(
            summary.get("production_ai_checkpoint_output_head_gap_contract_ready") is True
        ),
        "production_ai_checkpoint_output_heads_complete": bool(
            summary.get("production_ai_checkpoint_output_heads_complete") is True
        ),
        "production_ai_checkpoint_output_head_required_field_count": int(
            summary.get("production_ai_checkpoint_output_head_required_field_count") or 0
        ),
        "production_ai_checkpoint_output_head_ready_field_count": int(
            summary.get("production_ai_checkpoint_output_head_ready_field_count") or 0
        ),
        "production_ai_checkpoint_output_head_blocked_field_count": int(
            summary.get("production_ai_checkpoint_output_head_blocked_field_count") or 0
        ),
        "production_ai_checkpoint_output_head_blocked_fields": list(
            summary.get("production_ai_checkpoint_output_head_blocked_fields") or []
        ),
        "production_ai_checkpoint_output_head_first_blocked_field": summary.get(
            "production_ai_checkpoint_output_head_first_blocked_field", ""
        ),
        "production_ai_checkpoint_output_head_first_blocked_field_blockers": list(
            summary.get("production_ai_checkpoint_output_head_first_blocked_field_blockers") or []
        ),
        "production_ai_checkpoint_output_head_gap_contract_artifact_path": summary.get(
            "production_ai_checkpoint_output_head_gap_contract_artifact_path", ""
        ),
        "production_ai_delta_force_closure_acceptance_artifact_path": summary.get(
            "production_ai_delta_force_closure_acceptance_artifact_path", ""
        ),
        "production_ai_delta_force_closure_acceptance_packet_ready": bool(
            summary.get("production_ai_delta_force_closure_acceptance_packet_ready") is True
        ),
        "production_ai_delta_force_closure_ready": bool(
            summary.get("production_ai_delta_force_closure_ready") is True
        ),
        "production_ai_delta_force_closure_first_blocked_output_field": summary.get(
            "production_ai_delta_force_closure_first_blocked_output_field", ""
        ),
        "production_ai_delta_force_closure_failed_stage_count": int(
            summary.get("production_ai_delta_force_closure_failed_stage_count") or 0
        ),
        "production_ai_delta_force_closure_failed_stage_ids": list(
            summary.get("production_ai_delta_force_closure_failed_stage_ids") or []
        ),
        "production_ai_delta_force_closure_next_stage_id": summary.get(
            "production_ai_delta_force_closure_next_stage_id", ""
        ),
        "production_ai_delta_force_closure_next_stage_artifact": summary.get(
            "production_ai_delta_force_closure_next_stage_artifact", ""
        ),
        "production_ai_delta_force_closure_next_stage_validation_command": summary.get(
            "production_ai_delta_force_closure_next_stage_validation_command", ""
        ),
        "production_ai_delta_force_closure_next_required_step": summary.get(
            "production_ai_delta_force_closure_next_required_step", ""
        ),
        "production_ai_checkpoint_failed_check_ids": list(
            summary.get("production_ai_checkpoint_failed_check_ids") or []
        ),
        "production_ai_checkpoint_first_failed_check_id": summary.get(
            "production_ai_checkpoint_first_failed_check_id", ""
        ),
        "production_ai_checkpoint_first_failed_source_artifact": summary.get(
            "production_ai_checkpoint_first_failed_source_artifact", ""
        ),
        "production_ai_checkpoint_first_failed_observed": summary.get(
            "production_ai_checkpoint_first_failed_observed", ""
        ),
        "production_ai_checkpoint_first_failed_required": summary.get(
            "production_ai_checkpoint_first_failed_required", ""
        ),
        "production_ai_checkpoint_first_failed_next_action": summary.get(
            "production_ai_checkpoint_first_failed_next_action", ""
        ),
        "production_ai_checkpoint_registry_promotion_required_gate_ids": list(
            summary.get("production_ai_checkpoint_registry_promotion_required_gate_ids") or []
        ),
        "production_ai_checkpoint_registry_promotion_missing_gate_ids": list(
            summary.get("production_ai_checkpoint_registry_promotion_missing_gate_ids") or []
        ),
        "production_ai_checkpoint_registry_promotion_missing_gate_count": int(
            summary.get("production_ai_checkpoint_registry_promotion_missing_gate_count") or 0
        ),
        "production_ai_checkpoint_registry_promotion_upstream_acceptance_ready": bool(
            summary.get("production_ai_checkpoint_registry_promotion_upstream_acceptance_ready") is True
        ),
        "production_ai_checkpoint_registry_promotion_currently_satisfied": bool(
            summary.get("production_ai_checkpoint_registry_promotion_currently_satisfied") is True
        ),
        "production_ai_checkpoint_actionable_blocker_stage_id": summary.get(
            "production_ai_checkpoint_actionable_blocker_stage_id", ""
        ),
        "production_ai_checkpoint_actionable_blocker_check_id": summary.get(
            "production_ai_checkpoint_actionable_blocker_check_id", ""
        ),
        "production_ai_checkpoint_actionable_blocker_artifact": summary.get(
            "production_ai_checkpoint_actionable_blocker_artifact", ""
        ),
        "production_ai_checkpoint_actionable_blocker_observed": summary.get(
            "production_ai_checkpoint_actionable_blocker_observed", ""
        ),
        "production_ai_checkpoint_actionable_blocker_required": summary.get(
            "production_ai_checkpoint_actionable_blocker_required", ""
        ),
        "production_ai_checkpoint_actionable_blocker_next_action": summary.get(
            "production_ai_checkpoint_actionable_blocker_next_action", ""
        ),
        "production_ai_checkpoint_actionable_blocker_validation_command": summary.get(
            "production_ai_checkpoint_actionable_blocker_validation_command", ""
        ),
        "production_ai_checkpoint_actionable_blocker_unlock_fields": list(
            summary.get("production_ai_checkpoint_actionable_blocker_unlock_fields") or []
        ),
        "production_ai_checkpoint_actionable_blocker_downstream_blocked_stage_count": int(
            summary.get("production_ai_checkpoint_actionable_blocker_downstream_blocked_stage_count") or 0
        ),
        "production_ai_checkpoint_next_after_actionable_blocker_stage_id": summary.get(
            "production_ai_checkpoint_next_after_actionable_blocker_stage_id", ""
        ),
        "production_ai_checkpoint_next_after_actionable_blocker_artifact": summary.get(
            "production_ai_checkpoint_next_after_actionable_blocker_artifact", ""
        ),
        "production_ai_checkpoint_next_after_actionable_blocker_validation_command": summary.get(
            "production_ai_checkpoint_next_after_actionable_blocker_validation_command", ""
        ),
        "production_ai_checkpoint_next_after_actionable_blocker_required_checks": list(
            summary.get("production_ai_checkpoint_next_after_actionable_blocker_required_checks") or []
        ),
        "production_ai_checkpoint_next_after_actionable_blocker_unlock_fields": list(
            summary.get("production_ai_checkpoint_next_after_actionable_blocker_unlock_fields") or []
        ),
        "production_ai_checkpoint_next_after_actionable_blocker_next_action": summary.get(
            "production_ai_checkpoint_next_after_actionable_blocker_next_action", ""
        ),
        "production_ai_checkpoint_actionable_blocker_blocks_registry_promotion": bool(
            summary.get("production_ai_checkpoint_actionable_blocker_blocks_registry_promotion") is True
        ),
        "production_ai_checkpoint_actionable_operator_completion_packet_ready": bool(
            summary.get("production_ai_checkpoint_actionable_operator_completion_packet_ready") is True
        ),
        "production_ai_checkpoint_actionable_operator_completion_packet_artifact": summary.get(
            "production_ai_checkpoint_actionable_operator_completion_packet_artifact", ""
        ),
        "production_ai_checkpoint_actionable_operator_completion_artifact_id": summary.get(
            "production_ai_checkpoint_actionable_operator_completion_artifact_id", ""
        ),
        "production_ai_checkpoint_actionable_operator_completion_artifact_path": summary.get(
            "production_ai_checkpoint_actionable_operator_completion_artifact_path", ""
        ),
        "production_ai_checkpoint_actionable_operator_completion_expected_queue_rows": int(
            summary.get("production_ai_checkpoint_actionable_operator_completion_expected_queue_rows") or 0
        ),
        "production_ai_checkpoint_actionable_operator_completion_required_fields_or_columns": list(
            summary.get("production_ai_checkpoint_actionable_operator_completion_required_fields_or_columns") or []
        ),
        "production_ai_checkpoint_actionable_operator_completion_diagnostic_commands": list(
            summary.get("production_ai_checkpoint_actionable_operator_completion_diagnostic_commands") or []
        ),
        "production_ai_checkpoint_actionable_operator_completion_diagnostic_command_count": int(
            summary.get("production_ai_checkpoint_actionable_operator_completion_diagnostic_command_count") or 0
        ),
        "production_ai_checkpoint_actionable_operator_completion_diagnostic_required_fields": list(
            summary.get("production_ai_checkpoint_actionable_operator_completion_diagnostic_required_fields") or []
        ),
        "production_ai_checkpoint_actionable_operator_completion_diagnostic_required_field_count": int(
            summary.get("production_ai_checkpoint_actionable_operator_completion_diagnostic_required_field_count")
            or 0
        ),
        "production_ai_checkpoint_actionable_operator_completion_diagnostic_completion_rule": summary.get(
            "production_ai_checkpoint_actionable_operator_completion_diagnostic_completion_rule", ""
        ),
        "production_ai_checkpoint_actionable_operator_completion_diagnostic_return_artifacts": list(
            summary.get("production_ai_checkpoint_actionable_operator_completion_diagnostic_return_artifacts") or []
        ),
        "production_ai_checkpoint_actionable_operator_completion_torch_visibility_probe_command": summary.get(
            "production_ai_checkpoint_actionable_operator_completion_torch_visibility_probe_command", ""
        ),
        "production_ai_checkpoint_actionable_operator_completion_failed_check_ids": list(
            summary.get("production_ai_checkpoint_actionable_operator_completion_failed_check_ids") or []
        ),
        "production_ai_checkpoint_actionable_operator_completion_template_payload_json": summary.get(
            "production_ai_checkpoint_actionable_operator_completion_template_payload_json", ""
        ),
        "production_ai_checkpoint_actionable_operator_completion_validation_command": summary.get(
            "production_ai_checkpoint_actionable_operator_completion_validation_command", ""
        ),
        "production_ai_checkpoint_actionable_operator_completion_full_regeneration_command": summary.get(
            "production_ai_checkpoint_actionable_operator_completion_full_regeneration_command", ""
        ),
        "production_ai_checkpoint_actionable_operator_completion_completion_rule": summary.get(
            "production_ai_checkpoint_actionable_operator_completion_completion_rule", ""
        ),
        "production_ai_checkpoint_actionable_operator_completion_backend_provenance_completion_rule": summary.get(
            "production_ai_checkpoint_actionable_operator_completion_backend_provenance_completion_rule", ""
        ),
        "production_ai_checkpoint_actionable_operator_completion_next_action": summary.get(
            "production_ai_checkpoint_actionable_operator_completion_next_action", ""
        ),
        "production_ai_checkpoint_actionable_operator_completion_packet": dict(
            summary.get("production_ai_checkpoint_actionable_operator_completion_packet") or {}
        ),
        "production_ai_checkpoint_worker_runtime_receipt_contract_ready": bool(
            summary.get("production_ai_checkpoint_worker_runtime_receipt_contract_ready") is True
        ),
        "production_ai_checkpoint_worker_runtime_receipt_contract": dict(
            summary.get("production_ai_checkpoint_worker_runtime_receipt_contract") or {}
        ),
        "production_ai_checkpoint_worker_runtime_receipt_required_fields_or_columns": list(
            summary.get("production_ai_checkpoint_worker_runtime_receipt_required_fields_or_columns") or []
        ),
        "production_ai_checkpoint_worker_runtime_receipt_required_field_count": int(
            summary.get("production_ai_checkpoint_worker_runtime_receipt_required_field_count") or 0
        ),
        "production_ai_checkpoint_worker_runtime_receipt_completion_rule": summary.get(
            "production_ai_checkpoint_worker_runtime_receipt_completion_rule", ""
        ),
        "production_ai_checkpoint_worker_runtime_receipt_post_environment_next_stage_id": summary.get(
            "production_ai_checkpoint_worker_runtime_receipt_post_environment_next_stage_id", ""
        ),
        "production_ai_checkpoint_worker_runtime_receipt_post_environment_next_artifact": summary.get(
            "production_ai_checkpoint_worker_runtime_receipt_post_environment_next_artifact", ""
        ),
        "production_ai_checkpoint_worker_runtime_receipt_post_environment_validation_command": summary.get(
            "production_ai_checkpoint_worker_runtime_receipt_post_environment_validation_command", ""
        ),
        "production_ai_checkpoint_worker_runtime_receipt_full_regeneration_command": summary.get(
            "production_ai_checkpoint_worker_runtime_receipt_full_regeneration_command", ""
        ),
        "production_ai_checkpoint_worker_runtime_receipt_guardrails": list(
            summary.get("production_ai_checkpoint_worker_runtime_receipt_guardrails") or []
        ),
        "production_ai_checkpoint_acceptance_matrix_ready": bool(
            summary.get("production_ai_checkpoint_acceptance_matrix_ready") is True
        ),
        "production_ai_checkpoint_acceptance_stage_count": int(
            summary.get("production_ai_checkpoint_acceptance_stage_count") or 0
        ),
        "production_ai_checkpoint_acceptance_ready_stage_count": int(
            summary.get("production_ai_checkpoint_acceptance_ready_stage_count") or 0
        ),
        "production_ai_checkpoint_acceptance_blocked_stage_count": int(
            summary.get("production_ai_checkpoint_acceptance_blocked_stage_count") or 0
        ),
        "production_ai_checkpoint_acceptance_stage_ids": list(
            summary.get("production_ai_checkpoint_acceptance_stage_ids") or []
        ),
        "production_ai_checkpoint_acceptance_ready_stage_ids": list(
            summary.get("production_ai_checkpoint_acceptance_ready_stage_ids") or []
        ),
        "production_ai_checkpoint_acceptance_blocked_stage_ids": list(
            summary.get("production_ai_checkpoint_acceptance_blocked_stage_ids") or []
        ),
        "production_ai_checkpoint_acceptance_matrix": list(
            summary.get("production_ai_checkpoint_acceptance_matrix") or []
        ),
        "production_ai_checkpoint_acceptance_current_blocked_stage_matrix": list(
            summary.get("production_ai_checkpoint_acceptance_current_blocked_stage_matrix") or []
        ),
        "production_ai_checkpoint_acceptance_release_blocker_stage_count": int(
            summary.get("production_ai_checkpoint_acceptance_release_blocker_stage_count") or 0
        ),
        "production_ai_checkpoint_acceptance_release_blocker_stage_ids": list(
            summary.get("production_ai_checkpoint_acceptance_release_blocker_stage_ids") or []
        ),
        "production_ai_checkpoint_acceptance_next_stage_id": summary.get(
            "production_ai_checkpoint_acceptance_next_stage_id", ""
        ),
        "production_ai_checkpoint_acceptance_next_stage_artifact": summary.get(
            "production_ai_checkpoint_acceptance_next_stage_artifact", ""
        ),
        "production_ai_checkpoint_acceptance_next_stage_validation_command": summary.get(
            "production_ai_checkpoint_acceptance_next_stage_validation_command", ""
        ),
        "production_ai_checkpoint_acceptance_next_stage_release_effect": summary.get(
            "production_ai_checkpoint_acceptance_next_stage_release_effect", ""
        ),
        "production_ai_checkpoint_acceptance_next_stage_unlock_fields": list(
            summary.get("production_ai_checkpoint_acceptance_next_stage_unlock_fields") or []
        ),
        "production_ai_checkpoint_acceptance_next_stage_required_checks": list(
            summary.get("production_ai_checkpoint_acceptance_next_stage_required_checks") or []
        ),
        "production_ai_checkpoint_acceptance_next_stage_next_action": summary.get(
            "production_ai_checkpoint_acceptance_next_stage_next_action", ""
        ),
        "production_ai_gpu_return_intake_status": summary.get("production_ai_gpu_return_intake_status", ""),
        "production_ai_gpu_return_intake_artifact_path": summary.get(
            "production_ai_gpu_return_intake_artifact_path", ""
        ),
        "production_ai_gpu_return_intake_ready": bool(
            summary.get("production_ai_gpu_return_intake_ready") is True
        ),
        "production_ai_gpu_return_artifacts_ready": bool(
            summary.get("production_ai_gpu_return_artifacts_ready") is True
        ),
        "production_ai_gpu_return_check_count": int(summary.get("production_ai_gpu_return_check_count") or 0),
        "production_ai_gpu_return_fail_check_count": int(
            summary.get("production_ai_gpu_return_fail_check_count") or 0
        ),
        "production_ai_gpu_return_failed_check_ids": list(
            summary.get("production_ai_gpu_return_failed_check_ids") or []
        ),
        "production_ai_gpu_return_blocker_matrix": list(
            summary.get("production_ai_gpu_return_blocker_matrix") or []
        ),
        "production_ai_gpu_return_blocker_matrix_count": int(
            summary.get("production_ai_gpu_return_blocker_matrix_count") or 0
        ),
        "production_ai_gpu_return_first_failed_check_id": summary.get(
            "production_ai_gpu_return_first_failed_check_id", ""
        ),
        "production_ai_gpu_return_first_failed_source_artifact": summary.get(
            "production_ai_gpu_return_first_failed_source_artifact", ""
        ),
        "production_ai_gpu_return_first_failed_observed": summary.get(
            "production_ai_gpu_return_first_failed_observed", ""
        ),
        "production_ai_gpu_return_first_failed_required": summary.get(
            "production_ai_gpu_return_first_failed_required", ""
        ),
        "production_ai_gpu_return_first_failed_next_action": summary.get(
            "production_ai_gpu_return_first_failed_next_action", ""
        ),
        "production_ai_gpu_return_operator_return_artifact_completion_matrix": list(
            summary.get("production_ai_gpu_return_operator_return_artifact_completion_matrix") or []
        ),
        "production_ai_gpu_return_operator_return_artifact_completion_matrix_count": int(
            summary.get("production_ai_gpu_return_operator_return_artifact_completion_matrix_count") or 0
        ),
        "production_ai_gpu_return_operator_return_artifact_completion_blocker_matrix": list(
            summary.get("production_ai_gpu_return_operator_return_artifact_completion_blocker_matrix") or []
        ),
        "production_ai_gpu_return_operator_return_artifact_completion_blocker_count": int(
            summary.get("production_ai_gpu_return_operator_return_artifact_completion_blocker_count") or 0
        ),
        "production_ai_gpu_return_operator_return_next_artifact_completion_packet_ready": bool(
            summary.get("production_ai_gpu_return_operator_return_next_artifact_completion_packet_ready") is True
        ),
        "production_ai_gpu_return_operator_return_next_artifact_completion_packet": dict(
            summary.get("production_ai_gpu_return_operator_return_next_artifact_completion_packet") or {}
        ),
        "production_ai_gpu_return_operator_return_next_artifact_id": summary.get(
            "production_ai_gpu_return_operator_return_next_artifact_id", ""
        ),
        "production_ai_gpu_return_operator_return_next_artifact_path": summary.get(
            "production_ai_gpu_return_operator_return_next_artifact_path", ""
        ),
        "production_ai_gpu_return_operator_return_next_artifact_failed_check_ids": list(
            summary.get("production_ai_gpu_return_operator_return_next_artifact_failed_check_ids") or []
        ),
        "production_ai_gpu_return_handoff_binding_ready": bool(
            summary.get("production_ai_gpu_return_handoff_binding_ready") is True
        ),
        "production_ai_gpu_return_handoff_queue_csv": summary.get(
            "production_ai_gpu_return_handoff_queue_csv", ""
        ),
        "production_ai_gpu_return_handoff_queue_csv_sha256": summary.get(
            "production_ai_gpu_return_handoff_queue_csv_sha256", ""
        ),
        "production_ai_gpu_return_handoff_full_regeneration_command": summary.get(
            "production_ai_gpu_return_handoff_full_regeneration_command", ""
        ),
        "production_ai_gpu_return_handoff_return_manifest_schema_contract_ready": bool(
            summary.get("production_ai_gpu_return_handoff_return_manifest_schema_contract_ready") is True
        ),
        "production_ai_gpu_return_handoff_return_manifest_required_identity_rule": summary.get(
            "production_ai_gpu_return_handoff_return_manifest_required_identity_rule", ""
        ),
        "production_ai_gpu_return_handoff_return_manifest_fingerprint_columns": list(
            summary.get("production_ai_gpu_return_handoff_return_manifest_fingerprint_columns") or []
        ),
        "production_ai_gpu_return_handoff_return_manifest_queue_id_columns": list(
            summary.get("production_ai_gpu_return_handoff_return_manifest_queue_id_columns") or []
        ),
        "production_ai_gpu_return_handoff_return_manifest_npz_columns": list(
            summary.get("production_ai_gpu_return_handoff_return_manifest_npz_columns") or []
        ),
        "production_ai_gpu_return_operator_acceptance_matrix_ready": bool(
            summary.get("production_ai_gpu_return_operator_acceptance_matrix_ready") is True
        ),
        "production_ai_gpu_return_operator_acceptance_matrix": list(
            summary.get("production_ai_gpu_return_operator_acceptance_matrix") or []
        ),
        "production_ai_gpu_return_operator_acceptance_current_blocked_stage_matrix": list(
            summary.get("production_ai_gpu_return_operator_acceptance_current_blocked_stage_matrix") or []
        ),
        "production_ai_gpu_return_operator_acceptance_stage_check_matrix": list(
            summary.get("production_ai_gpu_return_operator_acceptance_stage_check_matrix") or []
        ),
        "production_ai_gpu_return_operator_acceptance_stage_check_matrix_count": int(
            summary.get("production_ai_gpu_return_operator_acceptance_stage_check_matrix_count") or 0
        ),
        "production_ai_gpu_return_operator_acceptance_current_blocked_stage_check_matrix": list(
            summary.get("production_ai_gpu_return_operator_acceptance_current_blocked_stage_check_matrix") or []
        ),
        "production_ai_gpu_return_operator_acceptance_current_blocked_stage_check_matrix_count": int(
            summary.get("production_ai_gpu_return_operator_acceptance_current_blocked_stage_check_matrix_count")
            or 0
        ),
        "production_ai_gpu_return_operator_acceptance_stage_count": int(
            summary.get("production_ai_gpu_return_operator_acceptance_stage_count") or 0
        ),
        "production_ai_gpu_return_operator_acceptance_ready_stage_count": int(
            summary.get("production_ai_gpu_return_operator_acceptance_ready_stage_count") or 0
        ),
        "production_ai_gpu_return_operator_acceptance_blocked_stage_count": int(
            summary.get("production_ai_gpu_return_operator_acceptance_blocked_stage_count") or 0
        ),
        "production_ai_gpu_return_operator_acceptance_stage_ids": list(
            summary.get("production_ai_gpu_return_operator_acceptance_stage_ids") or []
        ),
        "production_ai_gpu_return_operator_acceptance_ready_stage_ids": list(
            summary.get("production_ai_gpu_return_operator_acceptance_ready_stage_ids") or []
        ),
        "production_ai_gpu_return_operator_acceptance_blocked_stage_ids": list(
            summary.get("production_ai_gpu_return_operator_acceptance_blocked_stage_ids") or []
        ),
        "production_ai_gpu_return_operator_acceptance_next_stage_id": summary.get(
            "production_ai_gpu_return_operator_acceptance_next_stage_id", ""
        ),
        "production_ai_gpu_return_operator_acceptance_next_stage_artifact": summary.get(
            "production_ai_gpu_return_operator_acceptance_next_stage_artifact", ""
        ),
        "production_ai_gpu_return_operator_acceptance_next_stage_validation_command": summary.get(
            "production_ai_gpu_return_operator_acceptance_next_stage_validation_command", ""
        ),
        "production_ai_gpu_return_operator_acceptance_next_stage_release_effect": summary.get(
            "production_ai_gpu_return_operator_acceptance_next_stage_release_effect", ""
        ),
        "production_ai_gpu_return_operator_acceptance_next_stage_unlock_fields": list(
            summary.get("production_ai_gpu_return_operator_acceptance_next_stage_unlock_fields") or []
        ),
        "production_ai_gpu_return_operator_acceptance_next_stage_required_checks": list(
            summary.get("production_ai_gpu_return_operator_acceptance_next_stage_required_checks") or []
        ),
        "production_ai_gpu_return_operator_acceptance_next_stage_next_action": summary.get(
            "production_ai_gpu_return_operator_acceptance_next_stage_next_action", ""
        ),
        "production_ai_gpu_return_expected_queue_rows": int(
            summary.get("production_ai_gpu_return_expected_queue_rows") or 0
        ),
        "production_ai_gpu_return_manifest_template_csv": summary.get(
            "production_ai_gpu_return_manifest_template_csv", ""
        ),
        "production_ai_gpu_return_summary_template_csv": summary.get(
            "production_ai_gpu_return_summary_template_csv", ""
        ),
        "production_ai_gpu_return_summary_template_payload_json": summary.get(
            "production_ai_gpu_return_summary_template_payload_json", ""
        ),
        "production_ai_gpu_return_summary_template_required_fields": list(
            summary.get("production_ai_gpu_return_summary_template_required_fields") or []
        ),
        "production_ai_gpu_return_summary_template_completion_rule": summary.get(
            "production_ai_gpu_return_summary_template_completion_rule", ""
        ),
        "production_ai_gpu_return_summary_template_backend_provenance_contract_ready": bool(
            summary.get("production_ai_gpu_return_summary_template_backend_provenance_contract_ready") is True
        ),
        "production_ai_gpu_return_summary_template_required_backend_provenance_fields": list(
            summary.get("production_ai_gpu_return_summary_template_required_backend_provenance_fields") or []
        ),
        "production_ai_gpu_return_summary_template_backend_provenance_completion_rule": summary.get(
            "production_ai_gpu_return_summary_template_backend_provenance_completion_rule", ""
        ),
        "production_ai_gpu_return_manifest_template_row_count": int(
            summary.get("production_ai_gpu_return_manifest_template_row_count") or 0
        ),
        "production_ai_gpu_return_manifest_operator_verification_placeholder_count": int(
            summary.get("production_ai_gpu_return_manifest_operator_verification_placeholder_count") or 0
        ),
        "production_ai_gpu_return_actual_summary_return_path": summary.get(
            "production_ai_gpu_return_actual_summary_return_path", ""
        ),
        "production_ai_gpu_return_actual_manifest_return_path": summary.get(
            "production_ai_gpu_return_actual_manifest_return_path", ""
        ),
        "production_ai_gpu_summary_manifest_bound": bool(
            summary.get("production_ai_gpu_summary_manifest_bound") is True
        ),
        "production_ai_gpu_summary_manifest_csv": summary.get(
            "production_ai_gpu_summary_manifest_csv", ""
        ),
        "production_ai_gpu_summary_out_manifest_csv_present": bool(
            summary.get("production_ai_gpu_summary_out_manifest_csv_present") is True
        ),
        "production_ai_gpu_summary_out_manifest_csv": summary.get(
            "production_ai_gpu_summary_out_manifest_csv", ""
        ),
        "production_ai_gpu_summary_out_manifest_csv_bound": bool(
            summary.get("production_ai_gpu_summary_out_manifest_csv_bound") is True
        ),
        "production_ai_gpu_summary_out_summary_json_bound": bool(
            summary.get("production_ai_gpu_summary_out_summary_json_bound") is True
        ),
        "production_ai_gpu_summary_out_summary_json": summary.get(
            "production_ai_gpu_summary_out_summary_json", ""
        ),
        "production_ai_gpu_summary_manifest_row_counts_consistent": bool(
            summary.get("production_ai_gpu_summary_manifest_row_counts_consistent") is True
        ),
        "production_ai_gpu_backend_provenance_ready": bool(
            summary.get("production_ai_gpu_backend_provenance_ready") is True
        ),
        "production_ai_gpu_backend_rows": int(summary.get("production_ai_gpu_backend_rows") or 0),
        "production_ai_gpu_backend_non_production_rows": int(
            summary.get("production_ai_gpu_backend_non_production_rows") or 0
        ),
        "production_ai_gpu_backend_prod_mode": bool(
            summary.get("production_ai_gpu_backend_prod_mode") is True
        ),
        "production_ai_gpu_backend_require_rust_hip": bool(
            summary.get("production_ai_gpu_backend_require_rust_hip") is True
        ),
        "production_ai_gpu_worker_rocm_manifest_artifact": summary.get(
            "production_ai_gpu_worker_rocm_manifest_artifact", ""
        ),
        "production_ai_gpu_worker_rocm_manifest_ready": bool(
            summary.get("production_ai_gpu_worker_rocm_manifest_ready") is True
        ),
        "production_ai_gpu_worker_rocm_manifest_generation_command": summary.get(
            "production_ai_gpu_worker_rocm_manifest_generation_command", ""
        ),
        "production_ai_gpu_worker_rocm_manifest_completion_rule": summary.get(
            "production_ai_gpu_worker_rocm_manifest_completion_rule", ""
        ),
        "production_ai_gpu_worker_rocm_stack_detected": bool(
            summary.get("production_ai_gpu_worker_rocm_stack_detected") is True
        ),
        "production_ai_gpu_worker_rocm_torch_ready": bool(
            summary.get("production_ai_gpu_worker_rocm_torch_ready") is True
        ),
        "production_ai_gpu_worker_rocm_amd_gpu_detected": bool(
            summary.get("production_ai_gpu_worker_rocm_amd_gpu_detected") is True
        ),
        "production_ai_gpu_worker_rocm_visible_device_count": int(
            summary.get("production_ai_gpu_worker_rocm_visible_device_count") or 0
        ),
        "production_ai_gpu_worker_rocm_device_names": list(
            summary.get("production_ai_gpu_worker_rocm_device_names") or []
        ),
        "production_ai_gpu_worker_rocm_next_required_step": summary.get(
            "production_ai_gpu_worker_rocm_next_required_step", ""
        ),
        "production_ai_checkpoint_gpu_backend_provenance_ready": bool(
            summary.get("production_ai_checkpoint_gpu_backend_provenance_ready") is True
        ),
        "production_ai_checkpoint_gpu_backend_rows": int(
            summary.get("production_ai_checkpoint_gpu_backend_rows") or 0
        ),
        "production_ai_checkpoint_gpu_backend_non_production_rows": int(
            summary.get("production_ai_checkpoint_gpu_backend_non_production_rows") or 0
        ),
        "production_ai_gpu_return_post_return_validation_command": summary.get(
            "production_ai_gpu_return_post_return_validation_command", ""
        ),
        "production_ai_gpu_return_next_required_step": summary.get(
            "production_ai_gpu_return_next_required_step", ""
        ),
        "production_ai_promotion_workbench_status": summary.get("production_ai_promotion_workbench_status", ""),
        "production_ai_promotion_workbench_ready": bool(
            summary.get("production_ai_promotion_workbench_ready") is True
        ),
        "production_ai_promotion_ready": bool(summary.get("production_ai_promotion_ready") is True),
        "production_ai_promotion_first_blocked_stage_id": summary.get(
            "production_ai_promotion_first_blocked_stage_id", ""
        ),
        "production_ai_promotion_first_blocked_stage_artifact": summary.get(
            "production_ai_promotion_first_blocked_stage_artifact", ""
        ),
        "production_ai_promotion_first_blocked_stage_ready_key": summary.get(
            "production_ai_promotion_first_blocked_stage_ready_key", ""
        ),
        "production_ai_promotion_blocked_stage_count": int(
            summary.get("production_ai_promotion_blocked_stage_count") or 0
        ),
        "production_ai_promotion_blocked_stage_ids": list(
            summary.get("production_ai_promotion_blocked_stage_ids") or []
        ),
        "production_ai_force_gpu_worker_handoff_ready": bool(
            summary.get("production_ai_force_gpu_worker_handoff_ready") is True
        ),
        "production_ai_force_gpu_worker_operator_action_required": bool(
            summary.get("production_ai_force_gpu_worker_operator_action_required") is True
        ),
        "production_ai_force_gpu_operator_transfer_manifest_ready": bool(
            summary.get("production_ai_force_gpu_operator_transfer_manifest_ready") is True
        ),
        "production_ai_force_gpu_operator_transfer_outbound_artifact_count": int(
            summary.get("production_ai_force_gpu_operator_transfer_outbound_artifact_count") or 0
        ),
        "production_ai_force_gpu_operator_transfer_outbound_artifacts": list(
            summary.get("production_ai_force_gpu_operator_transfer_outbound_artifacts") or []
        ),
        "production_ai_force_gpu_operator_transfer_inbound_artifact_count": int(
            summary.get("production_ai_force_gpu_operator_transfer_inbound_artifact_count") or 0
        ),
        "production_ai_force_gpu_operator_transfer_inbound_artifacts": list(
            summary.get("production_ai_force_gpu_operator_transfer_inbound_artifacts") or []
        ),
        "production_ai_force_gpu_operator_transfer_first_return_artifact": summary.get(
            "production_ai_force_gpu_operator_transfer_first_return_artifact", ""
        ),
        "production_ai_force_gpu_operator_transfer_return_manifest_artifact": summary.get(
            "production_ai_force_gpu_operator_transfer_return_manifest_artifact", ""
        ),
        "production_ai_force_gpu_operator_transfer_acceptance_artifact": summary.get(
            "production_ai_force_gpu_operator_transfer_acceptance_artifact", ""
        ),
        "production_ai_force_gpu_operator_transfer_acceptance_ready_key": summary.get(
            "production_ai_force_gpu_operator_transfer_acceptance_ready_key", ""
        ),
        "production_ai_force_gpu_operator_transfer_post_return_validation_command": summary.get(
            "production_ai_force_gpu_operator_transfer_post_return_validation_command", ""
        ),
        "production_ai_force_gpu_full_regeneration_command": summary.get(
            "production_ai_force_gpu_full_regeneration_command", ""
        ),
        "production_ai_force_gpu_post_return_validation_command": summary.get(
            "production_ai_force_gpu_post_return_validation_command", ""
        ),
        "production_ai_force_gpu_post_run_validation_commands": list(
            summary.get("production_ai_force_gpu_post_run_validation_commands") or []
        ),
        "production_ai_force_gpu_post_return_required_production_output_fields": list(
            summary.get("production_ai_force_gpu_post_return_required_production_output_fields") or []
        ),
        "production_ai_force_gpu_post_return_gpu_unlock_artifacts": list(
            summary.get("production_ai_force_gpu_post_return_gpu_unlock_artifacts") or []
        ),
        "production_ai_force_gpu_post_return_unlock_output_fields": list(
            summary.get("production_ai_force_gpu_post_return_unlock_output_fields") or []
        ),
        "production_ai_force_gpu_post_return_min_expected_label_rows": int(
            summary.get("production_ai_force_gpu_post_return_min_expected_label_rows") or 0
        ),
        "production_ai_force_gpu_post_return_promotion_ladder_stage_count": int(
            summary.get("production_ai_force_gpu_post_return_promotion_ladder_stage_count") or 0
        ),
        "production_ai_force_gpu_post_return_promotion_ladder_contract_ready": bool(
            summary.get("production_ai_force_gpu_post_return_promotion_ladder_contract_ready") is True
        ),
        "production_ai_force_gpu_post_return_promotion_ladder_currently_satisfied": bool(
            summary.get("production_ai_force_gpu_post_return_promotion_ladder_currently_satisfied") is True
        ),
        "production_ai_force_gpu_post_return_promotion_ladder_current_blocked_stage_count": int(
            summary.get("production_ai_force_gpu_post_return_promotion_ladder_current_blocked_stage_count") or 0
        ),
        "production_ai_force_gpu_post_return_promotion_ladder_current_blocked_stage_ids": list(
            summary.get("production_ai_force_gpu_post_return_promotion_ladder_current_blocked_stage_ids") or []
        ),
        "production_ai_force_gpu_post_return_promotion_ladder_current_next_stage_id": summary.get(
            "production_ai_force_gpu_post_return_promotion_ladder_current_next_stage_id", ""
        ),
        "production_ai_force_gpu_post_return_promotion_ladder_current_next_stage_artifact": summary.get(
            "production_ai_force_gpu_post_return_promotion_ladder_current_next_stage_artifact", ""
        ),
        "production_ai_force_gpu_post_return_promotion_ladder_current_next_stage_validation_command": summary.get(
            "production_ai_force_gpu_post_return_promotion_ladder_current_next_stage_validation_command", ""
        ),
        "production_ai_force_gpu_post_return_promotion_ladder_stage_ids": list(
            summary.get("production_ai_force_gpu_post_return_promotion_ladder_stage_ids") or []
        ),
        "production_ai_force_gpu_post_return_promotion_ladder_missing_ready_keys": list(
            summary.get("production_ai_force_gpu_post_return_promotion_ladder_missing_ready_keys") or []
        ),
        "production_ai_force_gpu_receipt_manifest_identity_row_count": int(
            summary.get("production_ai_force_gpu_receipt_manifest_identity_row_count") or 0
        ),
        "production_ai_force_gpu_receipt_matched_queue_id_count": int(
            summary.get("production_ai_force_gpu_receipt_matched_queue_id_count") or 0
        ),
        "production_ai_force_gpu_receipt_matched_expected_npz_count": int(
            summary.get("production_ai_force_gpu_receipt_matched_expected_npz_count") or 0
        ),
        "production_ai_force_gpu_receipt_matched_queue_fingerprint_count": int(
            summary.get("production_ai_force_gpu_receipt_matched_queue_fingerprint_count") or 0
        ),
        "product_scope_closure_acceptance_artifact_path": summary.get(
            "product_scope_closure_acceptance_artifact_path", ""
        ),
        "product_scope_closure_acceptance_packet_ready": bool(
            summary.get("product_scope_closure_acceptance_packet_ready") is True
        ),
        "product_scope_closure_acceptance_ready": bool(
            summary.get("product_scope_closure_acceptance_ready") is True
        ),
        "product_scope_closure_acceptance_stage_count": int(
            summary.get("product_scope_closure_acceptance_stage_count") or 0
        ),
        "product_scope_closure_acceptance_blocked_stage_count": int(
            summary.get("product_scope_closure_acceptance_blocked_stage_count") or 0
        ),
        "product_scope_closure_acceptance_blocked_stage_ids": list(
            summary.get("product_scope_closure_acceptance_blocked_stage_ids") or []
        ),
        "product_scope_closure_acceptance_next_stage_id": summary.get(
            "product_scope_closure_acceptance_next_stage_id", ""
        ),
        "product_scope_closure_acceptance_first_blocked_evidence_row_id": summary.get(
            "product_scope_closure_acceptance_first_blocked_evidence_row_id", ""
        ),
        "product_scope_closure_acceptance_first_blocked_target_id": summary.get(
            "product_scope_closure_acceptance_first_blocked_target_id", ""
        ),
        "product_scope_closure_acceptance_first_blocked_required_missing_fields": summary.get(
            "product_scope_closure_acceptance_first_blocked_required_missing_fields", ""
        ),
        "product_scope_closure_acceptance_transporter_unresolved_slot_count": int(
            summary.get("product_scope_closure_acceptance_transporter_unresolved_slot_count") or 0
        ),
        "product_scope_closure_acceptance_pxr_direct_or_claim_safe_quantitative_ready_count": int(
            summary.get("product_scope_closure_acceptance_pxr_direct_or_claim_safe_quantitative_ready_count") or 0
        ),
        "product_scope_closure_acceptance_general_platform_claim_allowed": bool(
            summary.get("product_scope_closure_acceptance_general_platform_claim_allowed") is True
        ),
        "product_scope_closure_acceptance_next_required_step": summary.get(
            "product_scope_closure_acceptance_next_required_step", ""
        ),
        "product_ai_scope_backlog_detail": summary.get("product_ai_scope_backlog_detail", ""),
        "product_scope_closure_blocker_class_counts": (
            summary.get("product_scope_closure_blocker_class_counts")
            if isinstance(summary.get("product_scope_closure_blocker_class_counts"), dict)
            else {}
        ),
        "product_scope_first_scientific_blocker": summary.get("product_scope_first_scientific_blocker", ""),
        "product_scope_manual_review_subcheck_count": int(
            summary.get("product_scope_manual_review_subcheck_count") or 0
        ),
        "product_scope_transporter_manual_review_subcheck_count": int(
            summary.get("product_scope_transporter_manual_review_subcheck_count") or 0
        ),
        "product_scope_transporter_identity_scaffold_confirmation_required_count": int(
            summary.get("product_scope_transporter_identity_scaffold_confirmation_required_count") or 0
        ),
        "product_scope_transporter_direct_binding_or_kcal_confirmation_required_count": int(
            summary.get("product_scope_transporter_direct_binding_or_kcal_confirmation_required_count") or 0
        ),
        "product_scope_transporter_negative_quantitative_confirmation_required_count": int(
            summary.get("product_scope_transporter_negative_quantitative_confirmation_required_count") or 0
        ),
        "product_scope_transporter_direct_binding_missing_count": int(
            summary.get("product_scope_transporter_direct_binding_missing_count") or 0
        ),
        "product_scope_transporter_negative_quantitative_missing_count": int(
            summary.get("product_scope_transporter_negative_quantitative_missing_count") or 0
        ),
        "product_scope_pxr_reconciled_blocked_row_count": int(
            summary.get("product_scope_pxr_reconciled_blocked_row_count") or 0
        ),
        "product_scope_pxr_conflict_resolution_count": int(
            summary.get("product_scope_pxr_conflict_resolution_count") or 0
        ),
        "product_scope_pxr_quantitative_missing_count": int(
            summary.get("product_scope_pxr_quantitative_missing_count") or 0
        ),
        "product_scope_breadth_contract_status": summary.get("product_scope_breadth_contract_status", ""),
        "product_scope_breadth_contract_artifact_path": summary.get(
            "product_scope_breadth_contract_artifact_path", ""
        ),
        "product_scope_operator_transfer_manifest_ready": bool(
            summary.get("product_scope_operator_transfer_manifest_ready") is True
        ),
        "product_scope_operator_transfer_outbound_artifact_count": int(
            summary.get("product_scope_operator_transfer_outbound_artifact_count") or 0
        ),
        "product_scope_operator_transfer_outbound_artifacts": list(
            summary.get("product_scope_operator_transfer_outbound_artifacts") or []
        ),
        "product_scope_operator_transfer_inbound_artifact_count": int(
            summary.get("product_scope_operator_transfer_inbound_artifact_count") or 0
        ),
        "product_scope_operator_transfer_inbound_artifacts": list(
            summary.get("product_scope_operator_transfer_inbound_artifacts") or []
        ),
        "product_scope_operator_transfer_first_return_artifact": summary.get(
            "product_scope_operator_transfer_first_return_artifact", ""
        ),
        "product_scope_operator_transfer_acceptance_artifact": summary.get(
            "product_scope_operator_transfer_acceptance_artifact", ""
        ),
        "product_scope_operator_transfer_acceptance_ready_key": summary.get(
            "product_scope_operator_transfer_acceptance_ready_key", ""
        ),
        "product_scope_operator_transfer_next_acceptance_stage": summary.get(
            "product_scope_operator_transfer_next_acceptance_stage", ""
        ),
        "product_scope_operator_transfer_post_return_validation_command": summary.get(
            "product_scope_operator_transfer_post_return_validation_command", ""
        ),
        "product_scope_acceptance_matrix_ready": bool(
            summary.get("product_scope_acceptance_matrix_ready") is True
        ),
        "product_scope_claim_expansion_contract_ready": bool(
            summary.get("product_scope_claim_expansion_contract_ready") is True
        ),
        "product_scope_claim_expansion_currently_satisfied": bool(
            summary.get("product_scope_claim_expansion_currently_satisfied") is True
        ),
        "product_scope_claim_expansion_current_blocked_stage_count": int(
            summary.get("product_scope_claim_expansion_current_blocked_stage_count") or 0
        ),
        "product_scope_claim_expansion_current_blocked_stage_ids": list(
            summary.get("product_scope_claim_expansion_current_blocked_stage_ids") or []
        ),
        "product_scope_claim_expansion_current_next_stage_id": summary.get(
            "product_scope_claim_expansion_current_next_stage_id", ""
        ),
        "product_scope_claim_expansion_current_next_stage_artifact": summary.get(
            "product_scope_claim_expansion_current_next_stage_artifact", ""
        ),
        "product_scope_claim_expansion_current_next_stage_validation_command": summary.get(
            "product_scope_claim_expansion_current_next_stage_validation_command", ""
        ),
        "product_scope_claim_expansion_current_next_stage_unlock_claim_scopes": list(
            summary.get("product_scope_claim_expansion_current_next_stage_unlock_claim_scopes") or []
        ),
        "product_scope_acceptance_stage_count": int(summary.get("product_scope_acceptance_stage_count") or 0),
        "product_scope_acceptance_ready_stage_count": int(
            summary.get("product_scope_acceptance_ready_stage_count") or 0
        ),
        "product_scope_acceptance_blocked_stage_count": int(
            summary.get("product_scope_acceptance_blocked_stage_count") or 0
        ),
        "product_scope_acceptance_stage_ids": list(summary.get("product_scope_acceptance_stage_ids") or []),
        "product_scope_acceptance_ready_stage_ids": list(
            summary.get("product_scope_acceptance_ready_stage_ids") or []
        ),
        "product_scope_acceptance_blocked_stage_ids": list(
            summary.get("product_scope_acceptance_blocked_stage_ids") or []
        ),
        "product_scope_acceptance_matrix": list(summary.get("product_scope_acceptance_matrix") or []),
        "product_scope_acceptance_current_blocked_stage_matrix": list(
            summary.get("product_scope_acceptance_current_blocked_stage_matrix") or []
        ),
        "product_scope_acceptance_stage_evidence_matrix": list(
            summary.get("product_scope_acceptance_stage_evidence_matrix") or []
        ),
        "product_scope_acceptance_stage_evidence_matrix_count": int(
            summary.get("product_scope_acceptance_stage_evidence_matrix_count") or 0
        ),
        "product_scope_acceptance_current_blocked_stage_evidence_matrix": list(
            summary.get("product_scope_acceptance_current_blocked_stage_evidence_matrix") or []
        ),
        "product_scope_acceptance_current_blocked_stage_evidence_matrix_count": int(
            summary.get("product_scope_acceptance_current_blocked_stage_evidence_matrix_count") or 0
        ),
        "product_scope_acceptance_release_blocker_stage_count": int(
            summary.get("product_scope_acceptance_release_blocker_stage_count") or 0
        ),
        "product_scope_acceptance_release_blocker_stage_ids": list(
            summary.get("product_scope_acceptance_release_blocker_stage_ids") or []
        ),
        "product_scope_acceptance_next_stage_id": summary.get(
            "product_scope_acceptance_next_stage_id", ""
        ),
        "product_scope_acceptance_next_stage_artifact": summary.get(
            "product_scope_acceptance_next_stage_artifact", ""
        ),
        "product_scope_acceptance_next_stage_validation_command": summary.get(
            "product_scope_acceptance_next_stage_validation_command", ""
        ),
        "product_scope_acceptance_next_stage_release_effect": summary.get(
            "product_scope_acceptance_next_stage_release_effect", ""
        ),
        "product_scope_acceptance_next_stage_unlock_claim_scopes": list(
            summary.get("product_scope_acceptance_next_stage_unlock_claim_scopes") or []
        ),
        "product_scope_acceptance_next_stage_required_checks": list(
            summary.get("product_scope_acceptance_next_stage_required_checks") or []
        ),
        "product_scope_acceptance_next_stage_next_action": summary.get(
            "product_scope_acceptance_next_stage_next_action", ""
        ),
        "product_scope_general_claim_blocker_count": int(
            summary.get("product_scope_general_claim_blocker_count") or 0
        ),
        "product_scope_ready_for_apply_count": int(summary.get("product_scope_ready_for_apply_count") or 0),
        "product_scope_authoritative_apply_allowed": bool(
            summary.get("product_scope_authoritative_apply_allowed") is True
        ),
        "product_scope_domain_count": int(summary.get("product_scope_domain_count") or 0),
        "product_scope_ready_domain_count": int(summary.get("product_scope_ready_domain_count") or 0),
        "product_scope_missing_domain_count": int(summary.get("product_scope_missing_domain_count") or 0),
        "product_scope_ready_domains": list(summary.get("product_scope_ready_domains") or []),
        "product_scope_missing_domains": list(summary.get("product_scope_missing_domains") or []),
        "product_scope_first_blocked_domain": summary.get("product_scope_first_blocked_domain", ""),
        "product_scope_first_blocked_domain_artifact": summary.get(
            "product_scope_first_blocked_domain_artifact", ""
        ),
        "product_scope_first_blocked_domain_observed": summary.get(
            "product_scope_first_blocked_domain_observed", ""
        ),
        "product_scope_first_blocked_domain_requirement": summary.get(
            "product_scope_first_blocked_domain_requirement", ""
        ),
        "product_scope_first_blocked_domain_next_action": summary.get(
            "product_scope_first_blocked_domain_next_action", ""
        ),
        "product_scope_transporter_p0_readiness_matrix_ready": bool(
            summary.get("product_scope_transporter_p0_readiness_matrix_ready") is True
        ),
        "product_scope_transporter_p0_readiness_matrix_artifact": summary.get(
            "product_scope_transporter_p0_readiness_matrix_artifact", ""
        ),
        "product_scope_transporter_p0_auto_close_ready_artifact_count": int(
            summary.get("product_scope_transporter_p0_auto_close_ready_artifact_count") or 0
        ),
        "product_scope_transporter_p0_manual_or_external_required_artifact_count": int(
            summary.get("product_scope_transporter_p0_manual_or_external_required_artifact_count") or 0
        ),
        "product_scope_transporter_p0_unresolved_slot_count": int(
            summary.get("product_scope_transporter_p0_unresolved_slot_count") or 0
        ),
        "product_scope_transporter_p0_auto_close_ready_slot_count": int(
            summary.get("product_scope_transporter_p0_auto_close_ready_slot_count") or 0
        ),
        "product_scope_transporter_p0_external_exact_evidence_required_slot_count": int(
            summary.get("product_scope_transporter_p0_external_exact_evidence_required_slot_count") or 0
        ),
        "product_scope_transporter_p0_first_manual_or_external_required_step_id": summary.get(
            "product_scope_transporter_p0_first_manual_or_external_required_step_id", ""
        ),
        "product_scope_transporter_p0_first_manual_or_external_required_slot_step": summary.get(
            "product_scope_transporter_p0_first_manual_or_external_required_slot_step", ""
        ),
        "product_scope_transporter_p0_first_manual_or_external_required_action": summary.get(
            "product_scope_transporter_p0_first_manual_or_external_required_action", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_packet_ready": bool(
            summary.get("product_scope_transporter_p0_evidence_acquisition_packet_ready") is True
        ),
        "product_scope_transporter_p0_evidence_acquisition_artifact": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_artifact", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_exact_request_slot_count": int(
            summary.get("product_scope_transporter_p0_evidence_acquisition_exact_request_slot_count") or 0
        ),
        "product_scope_transporter_p0_evidence_acquisition_unresolved_slot_count": int(
            summary.get("product_scope_transporter_p0_evidence_acquisition_unresolved_slot_count") or 0
        ),
        "product_scope_transporter_p0_evidence_acquisition_first_target_id": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_first_target_id", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_first_packet_step": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_first_packet_step", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_first_replacement_ligand_id": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_first_replacement_ligand_id", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_first_request_mode": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_first_request_mode", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_first_source_signal": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_first_source_signal", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_first_required_missing_fields": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_first_required_missing_fields", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_first_next_required_action": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_first_next_required_action", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_completion_packet_ready": bool(
            summary.get("product_scope_transporter_p0_evidence_acquisition_next_slot_completion_packet_ready")
            is True
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_completion_packet": dict(
            summary.get("product_scope_transporter_p0_evidence_acquisition_next_slot_completion_packet") or {}
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifacts": list(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifacts"
            )
            or []
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifact_count": int(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_required_artifact_count"
            )
            or 0
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix": list(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix"
            )
            or []
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix_count": int(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_completion_matrix_count"
            )
            or 0
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_blocker_count": int(
            summary.get("product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_blocker_count")
            or 0
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_id": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_id", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_path": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_next_slot_return_bundle_next_artifact_path", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_id": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_next_slot_id", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_operator_review_artifact": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_next_slot_operator_review_artifact", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_guard_ready": bool(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_guard_ready"
            )
            is True
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_claim_safe": bool(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_claim_safe"
            )
            is True
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_direct_binding_claim_allowed": bool(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_direct_binding_claim_allowed"
            )
            is True
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_decision": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_decision", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_guardrails": list(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_guardrails"
            )
            or []
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_observed_signal": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_observed_signal", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_required_upgrade": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_next_slot_source_modality_required_upgrade", ""
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_source_count": int(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_source_count"
            )
            or 0
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_result": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_direct_binding_recheck_result",
            "",
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_database_recheck_row_count": int(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_public_database_recheck_row_count"
            )
            or 0
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_ligand_identity_mismatch_row_count": int(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_ligand_identity_mismatch_row_count"
            )
            or 0
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_direct_like_binding_candidate_row_count": int(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_direct_like_binding_candidate_row_count"
            )
            or 0
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_direct_like_binding_candidate_claim_safe_ready_count": int(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_direct_like_binding_candidate_claim_safe_ready_count"
            )
            or 0
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_candidate_chembl_id": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_candidate_chembl_id",
            "",
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_candidate_delta_g_kcal_mol": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_candidate_delta_g_kcal_mol",
            "",
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_candidate_blocker": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_chembl_aqp1_direct_like_binding_candidate_blocker",
            "",
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bindingdb_aqp1_expanded_cutoff_affinity_row_count": int(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bindingdb_aqp1_expanded_cutoff_affinity_row_count"
            )
            or 0
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bindingdb_aqp1_expanded_cutoff_direct_like_affinity_row_count": int(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bindingdb_aqp1_expanded_cutoff_direct_like_affinity_row_count"
            )
            or 0
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_pubchem_cid": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_pubchem_cid",
            "",
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_id": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_id",
            "",
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_chembl_target_id": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_chembl_target_id",
            "",
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_bindingdb_uniprot_affinity_row_count": int(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_aqp1_bindingdb_uniprot_affinity_row_count"
            )
            or 0
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_aqp1_activity_row_count": int(
            summary.get(
                "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_bacopaside_ii_chembl_aqp1_activity_row_count"
            )
            or 0
        ),
        "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_functional_ic50_identity_mismatch_detail": summary.get(
            "product_scope_transporter_p0_evidence_acquisition_aqp1_binding_source_modality_functional_ic50_identity_mismatch_detail",
            "",
        ),
        "product_scope_general_platform_domain_floor_ready": bool(
            summary.get("product_scope_general_platform_domain_floor_ready") is True
        ),
        "product_scope_general_platform_domain_floor_missing_domain_count": int(
            summary.get("product_scope_general_platform_domain_floor_missing_domain_count") or 0
        ),
        "product_scope_general_platform_domain_floor_missing_domains": list(
            summary.get("product_scope_general_platform_domain_floor_missing_domains") or []
        ),
        "product_scope_allowed_families": list(summary.get("product_scope_allowed_families") or []),
        "product_scope_blocked_claim_scopes": list(summary.get("product_scope_blocked_claim_scopes") or []),
        "product_scope_claim_blocked_domains": list(summary.get("product_scope_claim_blocked_domains") or []),
        "product_scope_general_platform_claim_allowed": bool(
            summary.get("product_scope_general_platform_claim_allowed") is True
        ),
        "product_scope_evidence_priority_ready": bool(
            summary.get("product_scope_evidence_priority_ready") is True
        ),
        "product_scope_evidence_priority_queue_item_count": int(
            summary.get("product_scope_evidence_priority_queue_item_count") or 0
        ),
        "product_scope_evidence_priority_open_item_count": int(
            summary.get("product_scope_evidence_priority_open_item_count") or 0
        ),
        "product_scope_evidence_priority_local_crosscheck_candidate_count": int(
            summary.get("product_scope_evidence_priority_local_crosscheck_candidate_count") or 0
        ),
        "product_scope_evidence_priority_external_primary_exact_required_count": int(
            summary.get("product_scope_evidence_priority_external_primary_exact_required_count") or 0
        ),
        "product_scope_evidence_priority_top_item_id": summary.get(
            "product_scope_evidence_priority_top_item_id", ""
        ),
        "product_scope_evidence_priority_top_domain": summary.get(
            "product_scope_evidence_priority_top_domain", ""
        ),
        "product_scope_evidence_priority_top_bucket": summary.get(
            "product_scope_evidence_priority_top_bucket", ""
        ),
        "product_scope_evidence_priority_top_next_step": summary.get(
            "product_scope_evidence_priority_top_next_step", ""
        ),
        "product_scope_evidence_priority_next_required_step": summary.get(
            "product_scope_evidence_priority_next_required_step", ""
        ),
        "product_scope_evidence_intake_ready": bool(
            summary.get("product_scope_evidence_intake_ready") is True
        ),
        "product_scope_evidence_intake_row_count": int(summary.get("product_scope_evidence_intake_row_count") or 0),
        "product_scope_local_crosscheck_triage_item_count": int(
            summary.get("product_scope_local_crosscheck_triage_item_count") or 0
        ),
        "product_scope_local_crosscheck_intake_ready_count": int(
            summary.get("product_scope_local_crosscheck_intake_ready_count") or 0
        ),
        "product_scope_external_exact_evidence_required_count": int(
            summary.get("product_scope_external_exact_evidence_required_count") or 0
        ),
        "product_scope_guardrail_item_count": int(summary.get("product_scope_guardrail_item_count") or 0),
        "product_scope_transporter_triage_packet_ready": bool(
            summary.get("product_scope_transporter_triage_packet_ready") is True
        ),
        "product_scope_transporter_operator_review_evidence_matrix_ready": bool(
            summary.get("product_scope_transporter_operator_review_evidence_matrix_ready") is True
        ),
        "product_scope_transporter_claim_safe_local_evidence_ready_count": int(
            summary.get("product_scope_transporter_claim_safe_local_evidence_ready_count") or 0
        ),
        "product_scope_transporter_claim_safe_local_evidence_blocked_count": int(
            summary.get("product_scope_transporter_claim_safe_local_evidence_blocked_count") or 0
        ),
        "product_scope_transporter_direct_binding_claim_blocked_count": int(
            summary.get("product_scope_transporter_direct_binding_claim_blocked_count") or 0
        ),
        "product_scope_transporter_negative_value_claim_blocked_count": int(
            summary.get("product_scope_transporter_negative_value_claim_blocked_count") or 0
        ),
        "product_scope_transporter_top_claim_safe_blocker": summary.get(
            "product_scope_transporter_top_claim_safe_blocker", ""
        ),
        "product_scope_transporter_top_operator_next_verdict": summary.get(
            "product_scope_transporter_top_operator_next_verdict", ""
        ),
        "product_scope_transporter_target_ready_for_promotion_count": int(
            summary.get("product_scope_transporter_target_ready_for_promotion_count") or 0
        ),
        "product_scope_transporter_target_blocked_for_promotion_count": int(
            summary.get("product_scope_transporter_target_blocked_for_promotion_count") or 0
        ),
        "product_scope_transporter_target_ready_for_promotion_ids": list(
            summary.get("product_scope_transporter_target_ready_for_promotion_ids") or []
        ),
        "product_scope_transporter_target_blocked_for_promotion_ids": list(
            summary.get("product_scope_transporter_target_blocked_for_promotion_ids") or []
        ),
        "product_scope_transporter_primary_blocker_target_id": summary.get(
            "product_scope_transporter_primary_blocker_target_id", ""
        ),
        "product_scope_transporter_primary_blocker_packet_step": summary.get(
            "product_scope_transporter_primary_blocker_packet_step", ""
        ),
        "product_scope_transporter_primary_blocker_candidate_name": summary.get(
            "product_scope_transporter_primary_blocker_candidate_name", ""
        ),
        "product_scope_transporter_candidate_assignment_required_count": int(
            summary.get("product_scope_transporter_candidate_assignment_required_count") or 0
        ),
        "product_scope_transporter_functional_quantitative_only_direct_gap_open_count": int(
            summary.get("product_scope_transporter_functional_quantitative_only_direct_gap_open_count") or 0
        ),
        "product_scope_transporter_review_only_direct_binding_gap_count": int(
            summary.get("product_scope_transporter_review_only_direct_binding_gap_count") or 0
        ),
        "product_scope_transporter_candidate_ready_for_manual_review_count": int(
            summary.get("product_scope_transporter_candidate_ready_for_manual_review_count") or 0
        ),
        "product_scope_transporter_candidate_ready_for_apply_count": int(
            summary.get("product_scope_transporter_candidate_ready_for_apply_count") or 0
        ),
        "product_scope_transporter_manual_review_intake_ready": bool(
            summary.get("product_scope_transporter_manual_review_intake_ready") is True
        ),
        "product_scope_transporter_manual_review_template_row_count": int(
            summary.get("product_scope_transporter_manual_review_template_row_count") or 0
        ),
        "product_scope_transporter_manual_review_direct_binding_evidence_required_count": int(
            summary.get("product_scope_transporter_manual_review_direct_binding_evidence_required_count") or 0
        ),
        "product_scope_transporter_manual_review_negative_quantitative_value_required_count": int(
            summary.get("product_scope_transporter_manual_review_negative_quantitative_value_required_count") or 0
        ),
        "product_scope_transporter_manual_review_decision_placeholder_count": int(
            summary.get("product_scope_transporter_manual_review_decision_placeholder_count") or 0
        ),
        "product_scope_transporter_manual_review_p0_slot_overlay_row_count": int(
            summary.get("product_scope_transporter_manual_review_p0_slot_overlay_row_count") or 0
        ),
        "product_scope_transporter_manual_review_p0_slot_overlay_candidate_changed_count": int(
            summary.get("product_scope_transporter_manual_review_p0_slot_overlay_candidate_changed_count") or 0
        ),
        "product_scope_transporter_manual_review_p0_slot_overlay_first_item_id": summary.get(
            "product_scope_transporter_manual_review_p0_slot_overlay_first_item_id",
            "",
        ),
        "product_scope_transporter_manual_review_p0_slot_overlay_first_candidate_ligand_id": summary.get(
            "product_scope_transporter_manual_review_p0_slot_overlay_first_candidate_ligand_id",
            "",
        ),
        "product_scope_transporter_manual_review_p0_slot_overlay_first_source": summary.get(
            "product_scope_transporter_manual_review_p0_slot_overlay_first_source",
            "",
        ),
        "product_scope_transporter_manual_review_first_review_row_id": summary.get(
            "product_scope_transporter_manual_review_first_review_row_id",
            "",
        ),
        "product_scope_transporter_manual_review_first_review_item_id": summary.get(
            "product_scope_transporter_manual_review_first_review_item_id",
            "",
        ),
        "product_scope_transporter_manual_review_first_review_target_id": summary.get(
            "product_scope_transporter_manual_review_first_review_target_id",
            "",
        ),
        "product_scope_transporter_manual_review_first_review_candidate_ligand_id": summary.get(
            "product_scope_transporter_manual_review_first_review_candidate_ligand_id",
            "",
        ),
        "product_scope_transporter_manual_review_first_review_replacement_source": summary.get(
            "product_scope_transporter_manual_review_first_review_replacement_source",
            "",
        ),
        "product_scope_transporter_manual_review_first_review_replacement_reference_binding_kcal_mol": summary.get(
            "product_scope_transporter_manual_review_first_review_replacement_reference_binding_kcal_mol",
            "",
        ),
        "product_scope_transporter_manual_review_first_review_direct_binding_evidence_required": bool(
            summary.get("product_scope_transporter_manual_review_first_review_direct_binding_evidence_required")
            is True
        ),
        "product_scope_transporter_manual_review_first_review_direct_binding_source_url_or_doi": summary.get(
            "product_scope_transporter_manual_review_first_review_direct_binding_source_url_or_doi",
            "",
        ),
        "product_scope_transporter_manual_review_first_review_negative_quantitative_value_required": bool(
            summary.get(
                "product_scope_transporter_manual_review_first_review_negative_quantitative_value_required"
            )
            is True
        ),
        "product_scope_transporter_manual_review_first_review_negative_reference_binding_kcal_mol": summary.get(
            "product_scope_transporter_manual_review_first_review_negative_reference_binding_kcal_mol",
            "",
        ),
        "product_scope_transporter_manual_review_first_review_review_decision": summary.get(
            "product_scope_transporter_manual_review_first_review_review_decision",
            "",
        ),
        "product_scope_transporter_manual_review_first_review_authoritative_apply_requested": summary.get(
            "product_scope_transporter_manual_review_first_review_authoritative_apply_requested",
            "",
        ),
        "product_scope_transporter_manual_review_first_review_manual_review_blockers": summary.get(
            "product_scope_transporter_manual_review_first_review_manual_review_blockers",
            "",
        ),
        "product_scope_transporter_manual_review_first_review_review_requirements": summary.get(
            "product_scope_transporter_manual_review_first_review_review_requirements",
            "",
        ),
        "product_scope_transporter_manual_review_first_review_p0_slot_overlay_required_missing_fields": summary.get(
            "product_scope_transporter_manual_review_first_review_p0_slot_overlay_required_missing_fields",
            "",
        ),
        "product_scope_transporter_manual_review_first_review_p0_slot_overlay_claim_safe_step_ready": bool(
            summary.get(
                "product_scope_transporter_manual_review_first_review_p0_slot_overlay_claim_safe_step_ready"
            )
            is True
        ),
        "product_scope_transporter_manual_review_first_review_p0_slot_overlay_authoritative_apply_allowed": bool(
            summary.get(
                "product_scope_transporter_manual_review_first_review_p0_slot_overlay_authoritative_apply_allowed"
            )
            is True
        ),
        "product_scope_transporter_manual_review_first_review_p0_slot_overlay_scope_promotion_allowed": bool(
            summary.get(
                "product_scope_transporter_manual_review_first_review_p0_slot_overlay_scope_promotion_allowed"
            )
            is True
        ),
        "product_scope_evidence_intake_next_required_step": summary.get(
            "product_scope_evidence_intake_next_required_step", ""
        ),
        "product_scope_pxr_exact_review_intake_ready": bool(
            summary.get("product_scope_pxr_exact_review_intake_ready") is True
        ),
        "product_scope_pxr_exact_review_template_row_count": int(
            summary.get("product_scope_pxr_exact_review_template_row_count") or 0
        ),
        "product_scope_pxr_exact_review_expected_blocked_row_count": int(
            summary.get("product_scope_pxr_exact_review_expected_blocked_row_count") or 0
        ),
        "product_scope_pxr_exact_review_conflict_resolution_required_count": int(
            summary.get("product_scope_pxr_exact_review_conflict_resolution_required_count") or 0
        ),
        "product_scope_pxr_exact_review_kcal_placeholder_count": int(
            summary.get("product_scope_pxr_exact_review_kcal_placeholder_count") or 0
        ),
        "product_scope_pxr_exact_review_source_placeholder_count": int(
            summary.get("product_scope_pxr_exact_review_source_placeholder_count") or 0
        ),
        "product_scope_pxr_exact_review_target_match_placeholder_count": int(
            summary.get("product_scope_pxr_exact_review_target_match_placeholder_count") or 0
        ),
        "product_scope_pxr_exact_review_decision_placeholder_count": int(
            summary.get("product_scope_pxr_exact_review_decision_placeholder_count") or 0
        ),
        "product_scope_pxr_exact_review_next_review_completion_packet_ready": bool(
            summary.get("product_scope_pxr_exact_review_next_review_completion_packet_ready") is True
        ),
        "product_scope_pxr_exact_review_next_review_completion_packet": dict(
            summary.get("product_scope_pxr_exact_review_next_review_completion_packet") or {}
        ),
        "product_scope_pxr_exact_review_next_review_return_bundle_required_artifacts": list(
            summary.get("product_scope_pxr_exact_review_next_review_return_bundle_required_artifacts") or []
        ),
        "product_scope_pxr_exact_review_next_review_return_bundle_required_artifact_count": int(
            summary.get("product_scope_pxr_exact_review_next_review_return_bundle_required_artifact_count") or 0
        ),
        "product_scope_pxr_exact_review_next_review_return_bundle_completion_matrix": list(
            summary.get("product_scope_pxr_exact_review_next_review_return_bundle_completion_matrix") or []
        ),
        "product_scope_pxr_exact_review_next_review_return_bundle_completion_matrix_count": int(
            summary.get("product_scope_pxr_exact_review_next_review_return_bundle_completion_matrix_count") or 0
        ),
        "product_scope_pxr_exact_review_next_review_return_bundle_blocker_count": int(
            summary.get("product_scope_pxr_exact_review_next_review_return_bundle_blocker_count") or 0
        ),
        "product_scope_pxr_exact_review_next_review_return_bundle_next_artifact_id": summary.get(
            "product_scope_pxr_exact_review_next_review_return_bundle_next_artifact_id", ""
        ),
        "product_scope_pxr_exact_review_next_review_return_bundle_next_artifact_path": summary.get(
            "product_scope_pxr_exact_review_next_review_return_bundle_next_artifact_path", ""
        ),
        "product_scope_pxr_exact_review_next_review_return_bundle_next_artifact_failed_check_ids": list(
            summary.get(
                "product_scope_pxr_exact_review_next_review_return_bundle_next_artifact_failed_check_ids"
            )
            or []
        ),
        "product_scope_pxr_exact_review_next_review_row_id": summary.get(
            "product_scope_pxr_exact_review_next_review_row_id", ""
        ),
        "product_scope_pxr_exact_review_next_review_candidate_name": summary.get(
            "product_scope_pxr_exact_review_next_review_candidate_name", ""
        ),
        "product_scope_pxr_exact_review_next_review_operator_review_artifact": summary.get(
            "product_scope_pxr_exact_review_next_review_operator_review_artifact", ""
        ),
        "product_scope_pxr_exact_review_next_required_step": summary.get(
            "product_scope_pxr_exact_review_next_required_step", ""
        ),
        "product_scope_pxr_source_modality_triage_ready": bool(
            summary.get("product_scope_pxr_source_modality_triage_ready") is True
        ),
        "product_scope_pxr_source_modality_triage_status": summary.get(
            "product_scope_pxr_source_modality_triage_status", ""
        ),
        "product_scope_pxr_source_modality_triage_artifact": summary.get(
            "product_scope_pxr_source_modality_triage_artifact", ""
        ),
        "product_scope_pxr_source_modality_triage_decision": summary.get(
            "product_scope_pxr_source_modality_triage_decision", ""
        ),
        "product_scope_pxr_source_modality_public_evidence_recheck_ready": bool(
            summary.get("product_scope_pxr_source_modality_public_evidence_recheck_ready") is True
        ),
        "product_scope_pxr_source_modality_public_recheck_artifact": summary.get(
            "product_scope_pxr_source_modality_public_recheck_artifact", ""
        ),
        "product_scope_pxr_source_modality_public_recheck_candidate_count": int(
            summary.get("product_scope_pxr_source_modality_public_recheck_candidate_count") or 0
        ),
        "product_scope_pxr_source_modality_public_recheck_chembl_direct_binding_total_record_count": int(
            summary.get(
                "product_scope_pxr_source_modality_public_recheck_chembl_direct_binding_total_record_count"
            )
            or 0
        ),
        "product_scope_pxr_source_modality_public_recheck_chembl_functional_activity_total_record_count": int(
            summary.get(
                "product_scope_pxr_source_modality_public_recheck_chembl_functional_activity_total_record_count"
            )
            or 0
        ),
        "product_scope_pxr_source_modality_public_recheck_bindingdb_pxr_like_total_record_count": int(
            summary.get(
                "product_scope_pxr_source_modality_public_recheck_bindingdb_pxr_like_total_record_count"
            )
            or 0
        ),
        "product_scope_pxr_source_modality_public_recheck_direct_or_claim_safe_binding_kcal_ready_count": int(
            summary.get(
                "product_scope_pxr_source_modality_public_recheck_direct_or_claim_safe_binding_kcal_ready_count"
            )
            or 0
        ),
        "product_scope_pxr_source_modality_public_recheck_all_candidates_remain_blocked": bool(
            summary.get("product_scope_pxr_source_modality_public_recheck_all_candidates_remain_blocked")
            is True
        ),
        "product_scope_pxr_source_modality_public_recheck_first_blocked_candidate_name": summary.get(
            "product_scope_pxr_source_modality_public_recheck_first_blocked_candidate_name", ""
        ),
        "product_scope_pxr_source_modality_public_recheck_first_blocked_reason": summary.get(
            "product_scope_pxr_source_modality_public_recheck_first_blocked_reason", ""
        ),
        "product_scope_pxr_source_modality_direct_replacement_candidate_packet_ready": bool(
            summary.get("product_scope_pxr_source_modality_direct_replacement_candidate_packet_ready") is True
        ),
        "product_scope_pxr_source_modality_direct_replacement_artifact": summary.get(
            "product_scope_pxr_source_modality_direct_replacement_artifact", ""
        ),
        "product_scope_pxr_source_modality_direct_replacement_candidate_count": int(
            summary.get("product_scope_pxr_source_modality_direct_replacement_candidate_count") or 0
        ),
        "product_scope_pxr_source_modality_direct_replacement_selected_candidate_count": int(
            summary.get("product_scope_pxr_source_modality_direct_replacement_selected_candidate_count") or 0
        ),
        "product_scope_pxr_source_modality_direct_replacement_selected_claim_safe_candidate_count": int(
            summary.get(
                "product_scope_pxr_source_modality_direct_replacement_selected_claim_safe_candidate_count"
            )
            or 0
        ),
        "product_scope_pxr_source_modality_direct_replacement_first_ligand_id": summary.get(
            "product_scope_pxr_source_modality_direct_replacement_first_ligand_id", ""
        ),
        "product_scope_pxr_source_modality_direct_replacement_first_molecule_chembl_id": summary.get(
            "product_scope_pxr_source_modality_direct_replacement_first_molecule_chembl_id", ""
        ),
        "product_scope_pxr_source_modality_direct_replacement_first_reference_binding_kcal_mol": summary.get(
            "product_scope_pxr_source_modality_direct_replacement_first_reference_binding_kcal_mol", ""
        ),
        "product_scope_pxr_source_modality_direct_replacement_first_source": summary.get(
            "product_scope_pxr_source_modality_direct_replacement_first_source", ""
        ),
        "product_scope_pxr_source_modality_direct_replacement_apply_draft_ready": bool(
            summary.get("product_scope_pxr_source_modality_direct_replacement_apply_draft_ready") is True
        ),
        "product_scope_pxr_source_modality_direct_replacement_apply_draft_status": summary.get(
            "product_scope_pxr_source_modality_direct_replacement_apply_draft_status", ""
        ),
        "product_scope_pxr_source_modality_direct_replacement_apply_draft_artifact": summary.get(
            "product_scope_pxr_source_modality_direct_replacement_apply_draft_artifact", ""
        ),
        "product_scope_pxr_source_modality_direct_replacement_apply_draft_workbook_row_count": int(
            summary.get("product_scope_pxr_source_modality_direct_replacement_apply_draft_workbook_row_count")
            or 0
        ),
        "product_scope_pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_before_draft": int(
            summary.get(
                "product_scope_pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_before_draft"
            )
            or 0
        ),
        "product_scope_pxr_source_modality_direct_replacement_apply_draft_overlay_row_count": int(
            summary.get("product_scope_pxr_source_modality_direct_replacement_apply_draft_overlay_row_count")
            or 0
        ),
        "product_scope_pxr_source_modality_direct_replacement_apply_draft_ready_for_apply_row_count_after_draft": int(
            summary.get(
                "product_scope_pxr_source_modality_direct_replacement_apply_draft_ready_for_apply_row_count_after_draft"
            )
            or 0
        ),
        "product_scope_pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_after_draft": int(
            summary.get(
                "product_scope_pxr_source_modality_direct_replacement_apply_draft_blocked_row_count_after_draft"
            )
            or 0
        ),
        "product_scope_pxr_source_modality_direct_replacement_apply_draft_first_overlay_ligand_id": summary.get(
            "product_scope_pxr_source_modality_direct_replacement_apply_draft_first_overlay_ligand_id", ""
        ),
        "product_scope_pxr_source_modality_direct_replacement_apply_draft_authoritative_fields_touched": bool(
            summary.get(
                "product_scope_pxr_source_modality_direct_replacement_apply_draft_authoritative_fields_touched"
            )
            is True
        ),
        "product_scope_pxr_source_modality_activity_proxy_or_conflict_surrogate_row_count": int(
            summary.get("product_scope_pxr_source_modality_activity_proxy_or_conflict_surrogate_row_count") or 0
        ),
        "product_scope_pxr_source_modality_direct_or_claim_safe_quantitative_ready_count": int(
            summary.get("product_scope_pxr_source_modality_direct_or_claim_safe_quantitative_ready_count") or 0
        ),
        "product_scope_pxr_source_modality_accepted_for_scope_promotion_count": int(
            summary.get("product_scope_pxr_source_modality_accepted_for_scope_promotion_count") or 0
        ),
        "product_scope_pxr_source_modality_next_review_row_id": summary.get(
            "product_scope_pxr_source_modality_next_review_row_id", ""
        ),
        "product_scope_pxr_source_modality_next_review_candidate_name": summary.get(
            "product_scope_pxr_source_modality_next_review_candidate_name", ""
        ),
        "product_scope_pxr_source_modality_next_review_source_modality": summary.get(
            "product_scope_pxr_source_modality_next_review_source_modality", ""
        ),
        "product_scope_pxr_source_modality_next_review_rejection_reason": summary.get(
            "product_scope_pxr_source_modality_next_review_rejection_reason", ""
        ),
        "release_complete_vs_operator_pending_lane": lane_surface["release_complete_vs_operator_pending_lane"],
        "goal_completion_audit_goal_complete": lane_surface["goal_completion_audit_goal_complete"],
        "release_complete_lane_ready": lane_surface["release_complete_lane_ready"],
        "operator_pending_lane_ready": lane_surface["operator_pending_lane_ready"],
        "operator_or_external_pending_lane_count": lane_surface["operator_or_external_pending_lane_count"],
        "release_complete_vs_operator_pending_matrix": lane_surface["release_complete_vs_operator_pending_matrix"],
        "requirements": rows,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "license_file_written": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }
