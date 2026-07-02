from __future__ import annotations

from fastapi import APIRouter

from api.product_architecture import (
    get_product_architecture,
    get_product_architecture_validation,
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
    get_product_public_benchmark_external_receipts_audit,
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
from api.product_operator_cockpit import get_product_operator_cockpit
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

router = APIRouter(prefix="/product", tags=["product"])
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
    "get_product_operator_cockpit",
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
    "get_product_public_benchmark_external_receipts_audit",
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
