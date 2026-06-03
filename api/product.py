from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from api.config import settings
from betelgeuze_product.docking_request import build_docking_job_record, persist_docking_job_record
from betelgeuze_product.license_decision import APPROVAL_TOKEN as LICENSE_APPROVAL_TOKEN
from betelgeuze_product.license_decision import DECISION_CREATE_LICENSE, REQUIRED_FIELDS as LICENSE_REQUIRED_FIELDS
from betelgeuze_product.structure_analysis import analyze_structure_source

router = APIRouter(prefix="/product", tags=["product"])
ROOT = Path(__file__).resolve().parents[1]
PRODUCT_CAPABILITY_ARTIFACT = ROOT / "runs" / "product_capability_surface_contract_current.json"
PRODUCT_ARCHITECTURE_ARTIFACT = ROOT / "runs" / "product_architecture_contract_current.json"
PRODUCT_SERVICE_BOUNDARY_ARTIFACT = ROOT / "runs" / "product_service_boundary_contract_current.json"
PRODUCT_API_CONTRACT_ARTIFACT = ROOT / "runs" / "product_api_contract_current.json"
PRODUCT_OPERATIONAL_QUALITY_ARTIFACT = ROOT / "runs" / "product_operational_quality_contract_current.json"
PRODUCT_RELEASE_OPERATIONS_ARTIFACT = ROOT / "runs" / "product_release_operations_dossier_current.json"
PRODUCT_EXECUTION_APPROVAL_ARTIFACT = ROOT / "runs" / "product_execution_approval_gate_current.json"
PRODUCT_LICENSE_DECISION_ARTIFACT = ROOT / "runs" / "product_license_decision_gate_current.json"
PRODUCT_LICENSE_DECISION_PACKET_ARTIFACT = ROOT / "runs" / "product_license_decision_packet_current.json"
PRODUCT_LICENSE_FILE_WORK_ORDER_ARTIFACT = ROOT / "runs" / "product_license_file_creation_work_order_current.json"
PRODUCT_LICENSE_DECISION_TEMPLATE = ROOT / "runs" / "product_license_decision_operator_template_current.csv"
PRODUCT_LICENSE_DECISION_INTAKE = ROOT / "runs" / "product_license_decision_operator_intake.csv"
PRODUCT_COMMERCIAL_INDEPENDENCE_ARTIFACT = ROOT / "runs" / "product_commercial_independence_gate_current.json"
GOAL_RELEASE_DECISION_ARTIFACT = ROOT / "runs" / "goal_release_decision_gate_current.json"


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


@router.post("/docking/jobs")
async def submit_docking_job(payload: DockingJobRequest, request: Request) -> dict[str, Any]:
    record = build_docking_job_record(_model_to_dict(payload), source_host=request.client.host if request.client else "")
    path = persist_docking_job_record(record, _jobs_dir())
    return {
        "job_id": record["job_id"],
        "status": record["status"],
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
        "ledger_path": str(path),
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
        "status": summary.get("status"),
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
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_LICENSE_FILE_WORK_ORDER_ARTIFACT),
        "license_file_creation_review_ready": bool(summary.get("license_file_creation_review_ready") is True),
        "approval_token_required": summary.get("approval_token_required") or LICENSE_APPROVAL_TOKEN,
        "target_license_path": summary.get("target_license_path") or "LICENSE",
        "spdx_license_id": summary.get("spdx_license_id", ""),
        "license_text_source": summary.get("license_text_source", ""),
        "copyright_holder": summary.get("copyright_holder", ""),
        "effective_year": summary.get("effective_year", ""),
        "license_review_manifest_ready": bool(summary.get("license_review_manifest_ready") is True),
        "license_review_manifest": summary.get("license_review_manifest") if isinstance(summary.get("license_review_manifest"), dict) else {},
        "license_review_manifest_fingerprint_sha256": summary.get("license_review_manifest_fingerprint_sha256", ""),
        "license_decision_gate_status": summary.get("license_decision_gate_status", ""),
        "authorized_for_license_file_creation_review": bool(
            summary.get("authorized_for_license_file_creation_review") is True
        ),
        "commercial_gate_only_license_blocked": bool(summary.get("commercial_gate_only_license_blocked") is True),
        "license_present": bool(summary.get("license_present") is True),
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
        "product_architecture_cleanup_postcheck_ready": bool(architecture.get("cleanup_postcheck_contract_ready") is True),
        "product_architecture_cleanup_postcheck_row_count": int(architecture.get("cleanup_postcheck_row_count") or 0),
        "product_architecture_cleanup_postcheck_blocked_row_count": int(architecture.get("cleanup_postcheck_blocked_row_count") or 0),
        "commercial_independence_status": commercial.get("status", ""),
        "commercial_independent_product_ready": bool(commercial.get("commercial_independent_product_claim_allowed") is True),
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
