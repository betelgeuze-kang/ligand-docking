from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from betelgeuze_product.license_decision import APPROVAL_TOKEN as LICENSE_APPROVAL_TOKEN
from betelgeuze_product.license_decision import DECISION_CREATE_LICENSE, REQUIRED_FIELDS as LICENSE_REQUIRED_FIELDS

router = APIRouter(prefix="/product", tags=["product-release-ops"])

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ARCHITECTURE_ARTIFACT = ROOT / "runs" / "product_architecture_contract_current.json"
PRODUCT_OPERATIONAL_QUALITY_ARTIFACT = ROOT / "runs" / "product_operational_quality_contract_current.json"
PRODUCT_RELEASE_OPERATIONS_ARTIFACT = ROOT / "runs" / "product_release_operations_dossier_current.json"
PRODUCT_EXECUTION_APPROVAL_ARTIFACT = ROOT / "runs" / "product_execution_approval_gate_current.json"
PRODUCT_JOB_ORCHESTRATION_CONTRACT_ARTIFACT = ROOT / "runs" / "product_job_orchestration_contract_current.json"
PRODUCT_LICENSE_DECISION_ARTIFACT = ROOT / "runs" / "product_license_decision_gate_current.json"
PRODUCT_LICENSE_DECISION_PACKET_ARTIFACT = ROOT / "runs" / "product_license_decision_packet_current.json"
PRODUCT_LICENSE_FILE_WORK_ORDER_ARTIFACT = ROOT / "runs" / "product_license_file_creation_work_order_current.json"
PRODUCT_LICENSE_DECISION_TEMPLATE = ROOT / "runs" / "product_license_decision_operator_template_current.csv"
PRODUCT_LICENSE_DECISION_INTAKE = ROOT / "runs" / "product_license_decision_operator_intake.csv"
PRODUCT_COMMERCIAL_INDEPENDENCE_ARTIFACT = ROOT / "runs" / "product_commercial_independence_gate_current.json"
GOAL_RELEASE_DECISION_ARTIFACT = ROOT / "runs" / "goal_release_decision_gate_current.json"


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
