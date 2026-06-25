from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from api.product_architecture import (
    COMPETITION_EXTERNAL_OPERATOR_TRACK_ARTIFACT as _DEFAULT_COMPETITION_EXTERNAL_OPERATOR_TRACK_ARTIFACT,
    ARCHITECTURE_VALIDATION_REPORT_ARTIFACT as _DEFAULT_ARCHITECTURE_VALIDATION_REPORT_ARTIFACT,
    ROOT as _DEFAULT_ROOT,
    get_product_architecture,
)
from api.product_capabilities import get_product_capabilities
from api.product_docking import (
    DockingJobRequest,
    JobActionRequest,
    LigandInput,
    StructureAnalysisRequest,
    analyze_product_structure,
    cancel_docking_job,
    get_docking_job,
    get_docking_job_history,
    list_docking_jobs,
    retry_docking_job,
    submit_docking_job,
)
from api.product_benchmark import (
    get_product_external_metrics,
    get_product_public_benchmark,
    get_product_rollout_execution_smoke_receipt,
    get_product_trajectory_sla_contract,
)
from api.product_ai_surface import (
    get_product_ai_decision_graph,
    get_product_ai_report_ux,
    get_product_pose_sampling_readiness,
    get_product_residual_model_registry,
)
from api.product_operational import (
    get_product_operational_quality,
    get_product_security_deployment_contract,
)
from api.product_release_ops import (
    get_product_commercial_independence,
    get_product_job_orchestration_contract,
    get_product_operations,
    get_product_release_readiness,
)
from api.product_cameo_runner import (
    get_product_api_runner_profile_promotion_operator_receipt,
    get_product_api_runner_profile_promotion_operator_staging_apply,
    get_product_cameo_live_validation,
    get_product_cameo_official_result_fetch_preflight,
)
from api.product_license import (
    get_product_license_decision,
    get_product_license_file_work_order,
    get_product_license_options,
    get_product_self_hosted_license_distribution_audit,
)
from api.product_production_ai import (
    get_product_production_ai_checkpoint_readiness,
    get_product_production_ai_gpu_worker_dispatch_bundle,
    get_product_production_ai_gpu_worker_dispatch_manifest,
    get_product_production_ai_gpu_worker_execution_runbook,
    get_product_production_ai_gpu_return_intake,
    get_product_production_ai_promotion_workbench,
    get_product_production_ai_registry_promotion_operator_receipt,
    get_product_production_ai_registry_promotion_priority,
)
from api.product_service_contracts import get_product_api_contract, get_product_service_boundary
from api.product_commercial_readiness import (
    get_product_commercial_readiness_execution_ladder,
    get_product_commercial_readiness_handoff_bundle,
    get_product_commercial_readiness_operator_packet,
    get_product_commercial_readiness_operator_packet_freshness,
)
from api.product_scope import (
    get_product_aqp1_direct_binding_procurement_packet,
    get_product_aqp1_operator_validation_candidate,
    get_product_pxr_exact_review_intake,
    get_product_scope_breadth_contract,
    get_product_scope_claim_guard,
    get_product_scope_evidence_intake_readiness,
    get_product_scope_evidence_priority,
    get_product_transporter_manual_review_intake,
)
from api.product_evidence_goal import (
    get_product_engine_refinement_claim_evidence_priority,
    get_product_engine_refinement_claim_evidence_receipt,
    get_product_full_commercial_blocker_evidence_matrix,
    get_product_goal_completion_audit,
    get_product_scope_breadth_evidence_receipt,
)

ROOT = _DEFAULT_ROOT
ARCHITECTURE_VALIDATION_REPORT_ARTIFACT = _DEFAULT_ARCHITECTURE_VALIDATION_REPORT_ARTIFACT
COMPETITION_EXTERNAL_OPERATOR_TRACK_ARTIFACT = _DEFAULT_COMPETITION_EXTERNAL_OPERATOR_TRACK_ARTIFACT

router = APIRouter(prefix="/product", tags=["product"])


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


__all__ = [
    "DockingJobRequest",
    "JobActionRequest",
    "LigandInput",
    "StructureAnalysisRequest",
    "analyze_product_structure",
    "cancel_docking_job",
    "get_docking_job",
    "get_docking_job_history",
    "get_product_capabilities",
    "get_product_commercial_independence",
    "get_product_commercial_readiness_execution_ladder",
    "get_product_commercial_readiness_handoff_bundle",
    "get_product_commercial_readiness_operator_packet",
    "get_product_commercial_readiness_operator_packet_freshness",
    "get_product_ai_decision_graph",
    "get_product_ai_report_ux",
    "get_product_architecture",
    "get_product_architecture_validation",
    "get_product_api_contract",
    "get_product_api_runner_profile_promotion_operator_receipt",
    "get_product_api_runner_profile_promotion_operator_staging_apply",
    "get_product_cameo_live_validation",
    "get_product_cameo_official_result_fetch_preflight",
    "get_product_external_metrics",
    "get_product_job_orchestration_contract",
    "get_product_license_decision",
    "get_product_license_file_work_order",
    "get_product_license_options",
    "get_product_operational_quality",
    "get_product_operations",
    "get_product_pose_sampling_readiness",
    "get_product_production_ai_checkpoint_readiness",
    "get_product_production_ai_gpu_worker_dispatch_bundle",
    "get_product_production_ai_gpu_worker_dispatch_manifest",
    "get_product_production_ai_gpu_worker_execution_runbook",
    "get_product_production_ai_gpu_return_intake",
    "get_product_production_ai_promotion_workbench",
    "get_product_production_ai_registry_promotion_operator_receipt",
    "get_product_production_ai_registry_promotion_priority",
    "get_product_public_benchmark",
    "get_product_aqp1_direct_binding_procurement_packet",
    "get_product_aqp1_operator_validation_candidate",
    "get_product_pxr_exact_review_intake",
    "get_product_scope_breadth_contract",
    "get_product_scope_claim_guard",
    "get_product_scope_evidence_intake_readiness",
    "get_product_scope_evidence_priority",
    "get_product_transporter_manual_review_intake",
    "get_product_release_readiness",
    "get_product_residual_model_registry",
    "get_product_self_hosted_license_distribution_audit",
    "get_product_rollout_execution_smoke_receipt",
    "get_product_security_deployment_contract",
    "get_product_trajectory_sla_contract",
    "list_docking_jobs",
    "retry_docking_job",
    "submit_docking_job",
    "get_product_engine_refinement_claim_evidence_priority",
    "get_product_engine_refinement_claim_evidence_receipt",
    "get_product_full_commercial_blocker_evidence_matrix",
    "get_product_goal_completion_audit",
    "get_product_scope_breadth_evidence_receipt",
    "get_product_service_boundary",
    "router",
]
