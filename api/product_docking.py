from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from api.config import settings
from api.docking_dispatch import dispatch_docking_job_if_eligible
from api.job_store import get_configured_job_store
from betelgeuze_product.docking_private_payload import configured_store, store_docking_request
from betelgeuze_product.docking_request import build_docking_job_record, persist_docking_job_record
from betelgeuze_product.job_orchestration import (
    cancel_job_record,
    job_history,
    list_job_records,
    retry_job_record,
)
from betelgeuze_product.structure_analysis import analyze_structure_source

router = APIRouter(prefix="/product", tags=["product-docking"])
ROOT = Path(__file__).resolve().parents[1]
RESIDUAL_MODEL_REGISTRY_ARTIFACT = ROOT / "runs" / "residual_model_registry_current.json"
PRODUCT_SCOPE_CLAIM_GUARD_ARTIFACT = ROOT / "runs" / "product_scope_breadth_closure_checklist_current.json"


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


@router.post("/docking/jobs")
async def submit_docking_job(payload: DockingJobRequest, request: Request) -> dict[str, Any]:
    record = build_docking_job_record(
        _model_to_dict(payload),
        source_host=request.client.host if request.client else "",
        residual_registry_packet=_read_json_object(RESIDUAL_MODEL_REGISTRY_ARTIFACT),
        scope_claim_guard_packet=_read_json_object(PRODUCT_SCOPE_CLAIM_GUARD_ARTIFACT),
    )
    path = persist_docking_job_record(record, _jobs_dir())
    # Persist the ORIGINAL request encrypted at rest, bound to job_id and the
    # ledger request_sha256. The public ledger keeps only the redacted form;
    # materialization recovers the raw inputs from this store. Fail-closed:
    # no-op when the store is not configured.
    store_docking_request(
        configured_store(),
        job_id=record["job_id"],
        request_sha256=record["request_sha256"],
        request=_model_to_dict(payload),
    )
    dispatch_outcome = dispatch_docking_job_if_eligible(
        record,
        jobs_dir=_jobs_dir(),
        store=get_configured_job_store(),
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
