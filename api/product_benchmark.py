from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/product", tags=["product-benchmark"])

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_ROLLOUT_EXECUTION_SMOKE_RECEIPT_ARTIFACT = (
    ROOT / "runs" / "product_rollout_execution_smoke_receipt_current.json"
)
PRODUCT_PUBLIC_BENCHMARK_WORK_ORDER_ARTIFACT = ROOT / "runs" / "product_public_benchmark_work_order_current.json"
PUBLIC_BENCHMARK_EXTERNAL_RECEIPTS_AUDIT_ARTIFACT = (
    ROOT / "runs" / "public_benchmark_external_receipts_audit_current.json"
)
EXTERNAL_METRIC_SCORECARD_ARTIFACT = ROOT / "runs" / "external_metric_scorecard_current.json"
PRODUCT_TRAJECTORY_SLA_CONTRACT_ARTIFACT = ROOT / "runs" / "product_trajectory_sla_contract_current.json"


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


@router.get("/public-benchmark-external-receipts-audit")
async def get_product_public_benchmark_external_receipts_audit() -> dict[str, Any]:
    packet = _read_json_object(PUBLIC_BENCHMARK_EXTERNAL_RECEIPTS_AUDIT_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_public_benchmark_external_receipts_audit",
            "artifact_path": str(PUBLIC_BENCHMARK_EXTERNAL_RECEIPTS_AUDIT_ARTIFACT),
            "external_benchmark_receipts_ready": False,
            "claim_promotion_allowed": False,
            "step_count": 7,
            "ready_step_count": 0,
            "blocked_step_count": 7,
            "blocker_count": 1,
            "blockers": ["public_benchmark_external_receipts_audit_missing"],
            "primary_blocker_id": "public_benchmark_external_receipts_audit_missing",
            "primary_blocker": "public_benchmark_external_receipts_audit_missing",
            "receipt_blocked_row_count": 0,
            "vina_gnina_comparison_adapter_score_evidence_ready": False,
            "steps": [],
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product public benchmark external receipts audit endpoint only; the local audit artifact "
                "is missing. It does not download data, run docking, run Vina/GNINA, approve receipts, "
                "or mutate external state."
            ),
        }
    return {
        "status": summary.get("status", ""),
        "artifact_path": str(PUBLIC_BENCHMARK_EXTERNAL_RECEIPTS_AUDIT_ARTIFACT),
        "external_benchmark_receipts_ready": bool(summary.get("external_benchmark_receipts_ready") is True),
        "claim_promotion_allowed": bool(summary.get("claim_promotion_allowed") is True),
        "step_count": int(summary.get("step_count") or 0),
        "ready_step_count": int(summary.get("ready_step_count") or 0),
        "blocked_step_count": int(summary.get("blocked_step_count") or 0),
        "blocker_count": int(summary.get("blocker_count") or 0),
        "blockers": list(summary.get("blockers") or []),
        "primary_blocker_id": summary.get("primary_blocker_id", ""),
        "primary_blocker": summary.get("primary_blocker", ""),
        "primary_blocker_next_required_step": summary.get("primary_blocker_next_required_step", ""),
        "pose_count": int(summary.get("pose_count") or 0),
        "pose_success_rate": summary.get("pose_success_rate"),
        "posebusters_valid_rate": summary.get("posebusters_valid_rate"),
        "receipt_row_count": int(summary.get("receipt_row_count") or 0),
        "receipt_blocked_row_count": int(summary.get("receipt_blocked_row_count") or 0),
        "receipt_manual_field_pending_count": int(summary.get("receipt_manual_field_pending_count") or 0),
        "receipt_approval_token_pending_count": int(summary.get("receipt_approval_token_pending_count") or 0),
        "vina_gnina_comparison_adapter_contract_ready": bool(
            summary.get("vina_gnina_comparison_adapter_contract_ready") is True
        ),
        "vina_gnina_comparison_adapter_score_evidence_ready": bool(
            summary.get("vina_gnina_comparison_adapter_score_evidence_ready") is True
        ),
        "comparison_adapter_same_input_row_count_match": bool(
            summary.get("comparison_adapter_same_input_row_count_match") is True
        ),
        "steps": rows,
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


@router.get("/rollout-execution-smoke-receipt")
async def get_product_rollout_execution_smoke_receipt() -> dict[str, Any]:
    packet = _read_json_object(PRODUCT_ROLLOUT_EXECUTION_SMOKE_RECEIPT_ARTIFACT)
    summary = _summary(packet)
    rows = packet.get("rows") if isinstance(packet.get("rows"), list) else []
    if not summary:
        return {
            "status": "missing_product_rollout_execution_smoke_receipt",
            "artifact_path": str(PRODUCT_ROLLOUT_EXECUTION_SMOKE_RECEIPT_ARTIFACT),
            "rollout_execution_smoke_receipt_ready": False,
            "source_rollout_execution_readiness_status": "",
            "source_authorized_for_separate_operator_execution": False,
            "source_rollout_executed": False,
            "receipt_csv": "",
            "receipt_csv_present": False,
            "operator_template_csv": "",
            "receipt_row_count": 0,
            "ready_receipt_row_count": 0,
            "blocker_count": 1,
            "blockers": [],
            "target_environment": "",
            "rollout_executed": False,
            "image_pushed": False,
            "service_restarted": False,
            "pager_provider_contacted": False,
            "ingress_certificate_verified_live": False,
            "receipt_external_state_mutated": False,
            "rollout_receipt_rows": [],
            "next_required_step": "",
            "execution_enabled": False,
            "docking_results_emitted": False,
            "external_state_mutated": False,
            "claim_boundary": (
                "Product rollout execution smoke receipt endpoint only; the local receipt artifact is missing "
                "or invalid. It does not build images, push containers, apply manifests, restart services, "
                "contact providers, verify certificates, roll back services, upload, delete, commit, push, or "
                "mutate external state."
            ),
        }
    return {
        "status": summary.get("status"),
        "artifact_path": str(PRODUCT_ROLLOUT_EXECUTION_SMOKE_RECEIPT_ARTIFACT),
        "rollout_execution_smoke_receipt_ready": bool(
            summary.get("rollout_execution_smoke_receipt_ready") is True
        ),
        "source_rollout_execution_readiness_status": summary.get(
            "source_rollout_execution_readiness_status", ""
        ),
        "source_authorized_for_separate_operator_execution": bool(
            summary.get("source_authorized_for_separate_operator_execution") is True
        ),
        "source_rollout_executed": bool(summary.get("source_rollout_executed") is True),
        "receipt_csv": summary.get("receipt_csv", ""),
        "receipt_csv_present": bool(summary.get("receipt_csv_present") is True),
        "operator_template_csv": summary.get("operator_template_csv", ""),
        "receipt_row_count": int(summary.get("receipt_row_count") or 0),
        "ready_receipt_row_count": int(summary.get("ready_receipt_row_count") or 0),
        "blocker_count": int(summary.get("blocker_count") or 0),
        "blockers": list(summary.get("blockers") or []),
        "target_environment": summary.get("target_environment", ""),
        "rollout_executed": bool(summary.get("rollout_executed") is True),
        "image_pushed": bool(summary.get("image_pushed") is True),
        "service_restarted": bool(summary.get("service_restarted") is True),
        "pager_provider_contacted": bool(summary.get("pager_provider_contacted") is True),
        "ingress_certificate_verified_live": bool(
            summary.get("ingress_certificate_verified_live") is True
        ),
        "receipt_external_state_mutated": bool(summary.get("external_state_mutated") is True),
        "rollout_receipt_rows": rows,
        "next_required_step": summary.get("next_required_step", ""),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": summary.get("claim_boundary", ""),
    }
