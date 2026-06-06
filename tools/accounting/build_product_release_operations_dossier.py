#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_READINESS_JSON = "runs/product_readiness_gate_current.json"
DEFAULT_CAPABILITY_SURFACE_JSON = "runs/product_capability_surface_contract_current.json"
DEFAULT_OPERATIONAL_QUALITY_JSON = "runs/product_operational_quality_contract_current.json"
DEFAULT_ARCHITECTURE_JSON = "runs/product_architecture_contract_current.json"
DEFAULT_PUBLIC_BENCHMARK_WORK_ORDER_JSON = "runs/product_public_benchmark_work_order_current.json"
DEFAULT_PREFLIGHT_JSON = "runs/product_execution_preflight_current.json"
DEFAULT_WORK_ORDER_JSON = "runs/product_execution_work_order_current.json"
DEFAULT_APPROVAL_GATE_JSON = "runs/product_execution_approval_gate_current.json"
DEFAULT_BUNDLE_CONTRACT_JSON = "runs/product_bundle_contract_current.json"
DEFAULT_DELIVERY_EVIDENCE_JSON = "runs/product_delivery_evidence_contract_current.json"
DEFAULT_PILOT_PACKET_JSON = "runs/product_pilot_packet_contract_current.json"
DEFAULT_COMMERCIAL_INDEPENDENCE_JSON = "runs/product_commercial_independence_gate_current.json"
DEFAULT_LICENSE_DECISION_JSON = "runs/product_license_decision_gate_current.json"
DEFAULT_LICENSE_DECISION_PACKET_JSON = "runs/product_license_decision_packet_current.json"
DEFAULT_LICENSE_FILE_WORK_ORDER_JSON = "runs/product_license_file_creation_work_order_current.json"
DEFAULT_OUT_JSON = "runs/product_release_operations_dossier_current.json"
DEFAULT_OUT_CSV = "runs/product_release_operations_dossier_current.csv"
DEFAULT_OUT_MD = "runs/product_release_operations_dossier_current.md"

APPROVAL_TOKEN = "APPROVE_PRODUCT_DOCKING_EXECUTION"
LICENSE_APPROVAL_TOKEN = "APPROVE_PRODUCT_LICENSE_FILE_CREATION"

CLAIM_BOUNDARY = (
    "Product release operations dossier only; it consolidates local product readiness, architecture, execution approval, "
    "bundle, delivery-evidence, and pilot-packet artifacts. It does not run docking, assemble bundles, validate completed "
    "bundles, emit scientific results, submit predictions, delete data, upload, commit, push, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    return bool(value is True)


def _approval_tokens(value: str) -> list[str]:
    return [token.strip() for token in value.split(";") if token.strip()]


def _row(
    *,
    priority: int,
    stage: str,
    status: str,
    source_status: str,
    source_artifact: str,
    blocker_count: int = 0,
    required_input: str = "",
    approval_token_required: str = "",
    recommended_action: str = "",
    reason: str = "",
) -> dict[str, Any]:
    return {
        "priority": priority,
        "stage": stage,
        "status": status,
        "source_status": source_status,
        "blocker_count": blocker_count,
        "required_input": required_input,
        "approval_token_required": approval_token_required,
        "source_artifact": source_artifact,
        "recommended_action": recommended_action,
        "reason": reason,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "bundle_assembled": False,
        "delivery_ready_claim_allowed": False,
        "external_state_mutated": False,
    }


def build_product_release_operations_dossier(
    *,
    readiness_packet: dict[str, Any],
    preflight_packet: dict[str, Any],
    work_order_packet: dict[str, Any],
    approval_gate_packet: dict[str, Any],
    bundle_contract_packet: dict[str, Any],
    delivery_evidence_packet: dict[str, Any],
    pilot_packet: dict[str, Any],
    capability_surface_packet: dict[str, Any] | None = None,
    operational_quality_packet: dict[str, Any] | None = None,
    architecture_packet: dict[str, Any] | None = None,
    public_benchmark_work_order_packet: dict[str, Any] | None = None,
    commercial_independence_packet: dict[str, Any] | None = None,
    license_decision_packet: dict[str, Any] | None = None,
    license_decision_options_packet: dict[str, Any] | None = None,
    license_file_work_order_packet: dict[str, Any] | None = None,
    readiness_path: str = DEFAULT_READINESS_JSON,
    capability_surface_path: str = DEFAULT_CAPABILITY_SURFACE_JSON,
    operational_quality_path: str = DEFAULT_OPERATIONAL_QUALITY_JSON,
    architecture_path: str = DEFAULT_ARCHITECTURE_JSON,
    public_benchmark_work_order_path: str = DEFAULT_PUBLIC_BENCHMARK_WORK_ORDER_JSON,
    preflight_path: str = DEFAULT_PREFLIGHT_JSON,
    work_order_path: str = DEFAULT_WORK_ORDER_JSON,
    approval_gate_path: str = DEFAULT_APPROVAL_GATE_JSON,
    bundle_contract_path: str = DEFAULT_BUNDLE_CONTRACT_JSON,
    delivery_evidence_path: str = DEFAULT_DELIVERY_EVIDENCE_JSON,
    pilot_packet_path: str = DEFAULT_PILOT_PACKET_JSON,
    commercial_independence_path: str = DEFAULT_COMMERCIAL_INDEPENDENCE_JSON,
    license_decision_path: str = DEFAULT_LICENSE_DECISION_JSON,
    license_decision_options_path: str = DEFAULT_LICENSE_DECISION_PACKET_JSON,
    license_file_work_order_path: str = DEFAULT_LICENSE_FILE_WORK_ORDER_JSON,
) -> dict[str, Any]:
    readiness = _summary(readiness_packet)
    capability_surface = _summary(capability_surface_packet or {})
    operational_quality = _summary(operational_quality_packet or {})
    architecture = _summary(architecture_packet or {})
    public_benchmark_work_order = _summary(public_benchmark_work_order_packet or {})
    preflight = _summary(preflight_packet)
    work_order = _summary(work_order_packet)
    approval_gate = _summary(approval_gate_packet)
    bundle_contract = _summary(bundle_contract_packet)
    delivery = _summary(delivery_evidence_packet)
    pilot = _summary(pilot_packet)
    commercial = _summary(commercial_independence_packet or {})
    license_decision = _summary(license_decision_packet or {})
    license_options = _summary(license_decision_options_packet or {})
    license_file_work_order = _summary(license_file_work_order_packet or {})

    target_id = _text(readiness.get("target_id") or preflight.get("target_id") or work_order.get("target_id") or pilot.get("target_id"))
    family = _text(readiness.get("family") or preflight.get("family") or work_order.get("family") or pilot.get("family"))
    bundle_tag = _text(work_order.get("bundle_tag") or approval_gate.get("bundle_tag") or bundle_contract.get("bundle_tag"))

    capability_surface_ready = _text(capability_surface.get("status")) == "product_capability_surface_contract_ready"
    operational_quality_ready = (
        _text(operational_quality.get("status")) == "product_operational_quality_contract_ready"
        and _bool(operational_quality.get("operational_quality_ready"))
    )
    architecture_release_ready = _text(architecture.get("status")) == "product_architecture_contract_ready" and _bool(
        architecture.get("architecture_release_ready")
    )
    architecture_local_surface_ready = _bool(architecture.get("local_architecture_surface_ready"))
    public_benchmark_validation_ready = _bool(architecture.get("public_benchmark_validation_ready"))
    public_benchmark_status = _text(architecture.get("public_benchmark_status"))
    public_benchmark_blocked_suite_count = _int(architecture.get("public_benchmark_blocked_suite_count"))
    public_benchmark_ready_required_suite_count = _int(architecture.get("public_benchmark_ready_required_suite_count"))
    public_benchmark_required_suite_count = _int(architecture.get("public_benchmark_required_suite_count"))
    public_benchmark_suite_materialization_manifest_count = _int(
        architecture.get("public_benchmark_suite_materialization_manifest_count")
    )
    public_benchmark_suite_scorecard_row_csv_count = _int(
        architecture.get("public_benchmark_suite_scorecard_row_csv_count")
    )
    public_benchmark_suite_threshold_count = _int(architecture.get("public_benchmark_suite_threshold_count"))
    public_benchmark_suite_blocker_count = _int(architecture.get("public_benchmark_suite_blocker_count"))
    public_benchmark_suite_run_command_count = _int(architecture.get("public_benchmark_suite_run_command_count"))
    public_benchmark_suite_materialization_run_command_count = _int(
        architecture.get("public_benchmark_suite_materialization_run_command_count")
    )
    public_benchmark_suite_result_provenance_command_count = _int(
        public_benchmark_work_order.get("suite_result_provenance_command_count")
        or architecture.get("public_benchmark_suite_result_provenance_command_count")
    )
    public_benchmark_suite_result_provenance_present_count = _int(
        public_benchmark_work_order.get("suite_result_provenance_present_count")
        or architecture.get("public_benchmark_suite_result_provenance_present_count")
    )
    public_benchmark_suite_no_external_dependency_count = _int(
        architecture.get("public_benchmark_suite_no_external_dependency_count")
    )
    public_benchmark_work_order_status = _text(public_benchmark_work_order.get("status"))
    public_benchmark_work_order_open_suite_count = _int(public_benchmark_work_order.get("open_suite_count"))
    public_benchmark_work_order_materialization_required_suite_count = _int(
        public_benchmark_work_order.get("materialization_required_suite_count")
    )
    public_benchmark_work_order_scorecard_required_suite_count = _int(
        public_benchmark_work_order.get("scorecard_required_suite_count")
    )
    public_benchmark_work_order_continuous_validation_command_count = _int(
        public_benchmark_work_order.get("continuous_validation_command_count")
    )
    public_benchmark_work_order_suite_run_command_count = _int(public_benchmark_work_order.get("suite_run_command_count"))
    public_benchmark_work_order_suite_result_provenance_command_count = _int(
        public_benchmark_work_order.get("suite_result_provenance_command_count")
    )
    public_benchmark_work_order_suite_result_provenance_present_count = _int(
        public_benchmark_work_order.get("suite_result_provenance_present_count")
    )
    public_benchmark_work_order_suite_threshold_count = _int(public_benchmark_work_order.get("suite_threshold_count"))
    public_benchmark_work_order_suite_materialization_manifest_count = _int(
        public_benchmark_work_order.get("suite_materialization_manifest_count")
    )
    public_benchmark_work_order_suite_scorecard_row_csv_count = _int(
        public_benchmark_work_order.get("suite_scorecard_row_csv_count")
    )
    public_benchmark_work_order_suite_no_external_dependency_count = _int(
        public_benchmark_work_order.get("suite_no_external_dependency_count")
    )
    public_benchmark_work_order_local_artifact_preflight_ready_suite_count = _int(
        public_benchmark_work_order.get("local_artifact_preflight_ready_suite_count")
        or architecture.get("public_benchmark_work_order_local_artifact_preflight_ready_suite_count")
    )
    public_benchmark_work_order_local_artifact_preflight_blocked_suite_count = _int(
        public_benchmark_work_order.get("local_artifact_preflight_blocked_suite_count")
        or architecture.get("public_benchmark_work_order_local_artifact_preflight_blocked_suite_count")
    )
    public_benchmark_work_order_missing_local_input_artifact_count = _int(
        public_benchmark_work_order.get("missing_local_input_artifact_count")
        or architecture.get("public_benchmark_work_order_missing_local_input_artifact_count")
    )
    public_benchmark_work_order_missing_local_output_artifact_count = _int(
        public_benchmark_work_order.get("missing_local_output_artifact_count")
        or architecture.get("public_benchmark_work_order_missing_local_output_artifact_count")
    )
    public_benchmark_work_order_continuous_validation_command = _text(
        public_benchmark_work_order.get("continuous_validation_command")
    )
    preflight_ready = preflight.get("status") == "product_execution_preflight_ready"
    work_order_ready = work_order.get("status") == "product_execution_work_order_ready"
    approval_authorized = approval_gate.get("authorized_for_execution") is True
    bundle_contract_ready = bundle_contract.get("status") == "product_bundle_contract_ready"
    bundle_assembled = _bool(pilot.get("bundle_assembled") or bundle_contract.get("bundle_assembled") or delivery.get("bundle_assembled"))
    bundle_validation_passed = _bool(pilot.get("bundle_validation_passed") or delivery.get("bundle_validation_passed"))
    delivery_ready_claim_allowed = _bool(pilot.get("delivery_ready_claim_allowed") or delivery.get("delivery_ready_claim_allowed"))
    pilot_delivery_ready = _bool(pilot.get("pilot_delivery_ready"))
    commercial_independence_ready = _text(commercial.get("status")) == "product_commercial_independence_gate_ready"
    commercial_claim_scope_tier = _text(commercial.get("commercial_claim_scope_tier")) or "unknown"
    commercial_claim_scope_detail = _text(commercial.get("commercial_claim_scope_detail"))
    restricted_commercial_scope_claim_ready = _bool(commercial.get("restricted_commercial_scope_claim_ready"))
    commercial_allowed_scope_families = [str(item) for item in commercial.get("allowed_scope_families") or []]
    commercial_blocked_claim_scopes = [str(item) for item in commercial.get("blocked_claim_scopes") or []]
    commercial_general_platform_claim_allowed = _bool(commercial.get("general_platform_claim_allowed"))
    license_present = _bool(commercial.get("license_present")) or _bool(license_decision.get("license_present"))
    license_decision_authorized = _bool(license_decision.get("authorized_for_license_file_creation_review"))
    license_options_ready = _text(license_options.get("status")) == "product_license_decision_packet_ready"
    license_file_creation_review_ready = _bool(license_file_work_order.get("license_file_creation_review_ready"))
    license_stage_ready = license_present or license_file_creation_review_ready
    preflight_blockers = preflight_packet.get("blockers") if isinstance(preflight_packet.get("blockers"), list) else []
    preflight_blocker_codes = [
        _text(blocker.get("code"))
        for blocker in preflight_blockers
        if isinstance(blocker, dict) and _text(blocker.get("code"))
    ]
    gate_checks = (
        preflight_packet.get("operational_gate_feasibility_checks")
        if isinstance(preflight_packet.get("operational_gate_feasibility_checks"), list)
        else []
    )
    gate_check = gate_checks[0] if gate_checks and isinstance(gate_checks[0], dict) else {}

    rows = [
        _row(
            priority=1,
            stage="capability_surface_contract",
            status="ready" if capability_surface_ready else "blocked",
            source_status=_text(capability_surface.get("status")) or "missing",
            blocker_count=_int(capability_surface.get("blocked_capability_count")),
            required_input="ready molecular-structure analysis and ligand-docking product capability surface",
            source_artifact=capability_surface_path,
            recommended_action="Repair blocked capability rows before treating the product surface as complete.",
            reason=(
                f"structure_analysis_capability_ready={_bool(capability_surface.get('structure_analysis_capability_ready'))}, "
                f"ligand_docking_capability_ready={_bool(capability_surface.get('ligand_docking_capability_ready'))}, "
                f"api_surface_ready={_bool(capability_surface.get('api_surface_ready'))}."
            ),
        ),
        _row(
            priority=2,
            stage="operational_quality_contract",
            status="ready" if operational_quality_ready else "blocked",
            source_status=_text(operational_quality.get("status")) or "missing",
            blocker_count=_int(operational_quality.get("blocker_count")),
            required_input="fail-closed docking intake, private ledger record, traceability, scope-limit, and heavy-artifact policy checks",
            source_artifact=operational_quality_path,
            recommended_action="Repair operational-quality blockers before treating the product API as commercial-grade.",
            reason=(
                f"fail_closed_docking_intake_ready={_bool(operational_quality.get('fail_closed_docking_intake_ready'))}, "
                f"ledger_payload_privacy_ready={_bool(operational_quality.get('ledger_payload_privacy_ready'))}, "
                f"request_traceability_ready={_bool(operational_quality.get('request_traceability_ready'))}, "
                f"scope_limit_enforcement_ready={_bool(operational_quality.get('scope_limit_enforcement_ready'))}, "
                f"heavy_artifact_policy_ready={_bool(operational_quality.get('heavy_artifact_policy_ready'))}."
            ),
        ),
        _row(
            priority=3,
            stage="architecture_contract",
            status="ready" if architecture_release_ready else "blocked",
            source_status=_text(architecture.get("status")) or "missing",
            blocker_count=_int(architecture.get("blocked_lane_count")) + _int(architecture.get("approval_required_lane_count")),
            required_input="product architecture contract release-ready across product, public benchmark, optional CAMEO, CASP17 transition, and cleanup lanes",
            source_artifact=architecture_path,
            recommended_action="Clear product architecture blockers before treating release operations as complete.",
            reason=(
                f"local_architecture_surface_ready={architecture_local_surface_ready}, "
                f"architecture_release_ready={architecture_release_ready}, "
                f"product_api_contract_ready={_bool(architecture.get('product_api_contract_ready'))}, "
                f"product_service_boundary_ready={_bool(architecture.get('product_service_boundary_ready'))}, "
                f"public_benchmark_validation_ready={public_benchmark_validation_ready}, "
                f"public_benchmark_status={public_benchmark_status or 'missing'}, "
                f"public_benchmark_ready_required_suite_count={public_benchmark_ready_required_suite_count}, "
                f"public_benchmark_required_suite_count={public_benchmark_required_suite_count}, "
                f"public_benchmark_blocked_suite_count={public_benchmark_blocked_suite_count}, "
                f"public_benchmark_suite_materialization_manifest_count={public_benchmark_suite_materialization_manifest_count}, "
                f"public_benchmark_suite_scorecard_row_csv_count={public_benchmark_suite_scorecard_row_csv_count}, "
                f"public_benchmark_suite_threshold_count={public_benchmark_suite_threshold_count}, "
                f"public_benchmark_suite_blocker_count={public_benchmark_suite_blocker_count}, "
                f"public_benchmark_suite_run_command_count={public_benchmark_suite_run_command_count}, "
                f"public_benchmark_suite_materialization_run_command_count={public_benchmark_suite_materialization_run_command_count}, "
                f"public_benchmark_suite_no_external_dependency_count={public_benchmark_suite_no_external_dependency_count}, "
                f"public_benchmark_work_order_status={public_benchmark_work_order_status or 'missing'}, "
                f"public_benchmark_work_order_open_suite_count={public_benchmark_work_order_open_suite_count}, "
                f"public_benchmark_work_order_continuous_validation_command_count={public_benchmark_work_order_continuous_validation_command_count}, "
                f"public_benchmark_work_order_local_artifact_preflight_blocked_suite_count={public_benchmark_work_order_local_artifact_preflight_blocked_suite_count}, "
                f"public_benchmark_work_order_missing_local_input_artifact_count={public_benchmark_work_order_missing_local_input_artifact_count}, "
                f"public_benchmark_work_order_missing_local_output_artifact_count={public_benchmark_work_order_missing_local_output_artifact_count}, "
                f"cameo_architecture_validation_ready={_bool(architecture.get('cameo_architecture_validation_ready'))}, "
                f"cameo_official_validation_evidence_ready={_bool(architecture.get('cameo_official_validation_evidence_ready'))}, "
                f"cameo_receiver_smoke_status={_text(architecture.get('cameo_receiver_smoke_status')) or 'missing'}, "
                f"cameo_api_dependency_status={_text(architecture.get('cameo_api_dependency_status')) or 'missing'}, "
                f"cameo_public_registration_allowed={_bool(architecture.get('cameo_public_registration_allowed'))}, "
                f"cleanup_postcheck_contract_ready={_bool(architecture.get('cleanup_postcheck_contract_ready'))}."
            ),
        ),
        _row(
            priority=4,
            stage="commercial_independence_packaging",
            status="ready" if commercial_independence_ready else "blocked",
            source_status=_text(commercial.get("status")) or "missing",
            blocker_count=_int(commercial.get("blocker_count")),
            required_input="commercial-independence gate ready with explicit local license evidence",
            source_artifact=commercial_independence_path,
            recommended_action="Clear packaging/license blockers before treating the product as commercially independent.",
            reason=(
                f"commercial_independent_product_claim_allowed={_bool(commercial.get('commercial_independent_product_claim_allowed'))}, "
                f"restricted_commercial_scope_claim_ready={restricted_commercial_scope_claim_ready}, "
                f"commercial_claim_scope_tier={commercial_claim_scope_tier}, "
                f"general_platform_claim_allowed={commercial_general_platform_claim_allowed}, "
                f"license_present={license_present}, runtime_requirements_present={_bool(commercial.get('runtime_requirements_present'))}, "
                f"optional_profiles_separated={_bool(commercial.get('optional_profiles_separated'))}."
            ),
        ),
        _row(
            priority=5,
            stage="license_decision_review",
            status="ready" if license_stage_ready else "approval_required",
            source_status=_text(license_decision.get("status")) or "missing",
            blocker_count=_int(license_decision.get("blocker_count")),
            required_input="existing LICENSE or exact operator-approved license file creation metadata",
            approval_token_required="" if license_present else _text(license_decision.get("approval_token_required")) or LICENSE_APPROVAL_TOKEN,
            source_artifact=f"{license_decision_path};{license_decision_options_path};{license_file_work_order_path}",
            recommended_action="Fill product license decision intake only if the operator wants a LICENSE file creation review.",
            reason=(
                f"license_present={license_present}, "
                f"authorized_for_license_file_creation_review={license_decision_authorized}, "
                f"license_decision_packet_ready={license_options_ready}, "
                f"license_file_creation_work_order_status={_text(license_file_work_order.get('status')) or 'missing'}, "
                f"license_file_creation_review_ready={license_file_creation_review_ready}, "
                f"license_file_creation_work_order_blocker_count={_int(license_file_work_order.get('blocker_count'))}, "
                f"license_option_count={_int(license_options.get('option_count'))}, "
                f"operator_intake_csv_present={_bool(license_decision.get('operator_intake_csv_present'))}, "
                f"missing_required_field_count={_int(license_decision.get('missing_required_field_count'))}."
            ),
        ),
        _row(
            priority=6,
            stage="execution_preflight_and_work_order",
            status="ready" if preflight_ready and work_order_ready else "blocked",
            source_status=f"{_text(preflight.get('status')) or 'missing'};{_text(work_order.get('status')) or 'missing'}",
            blocker_count=_int(preflight.get("blocker_count")) + _int(work_order.get("blocker_count")),
            required_input="product execution preflight and work order with parsed command contract",
            source_artifact=f"{preflight_path};{work_order_path}",
            recommended_action=(
                "Repair product execution preflight blockers before any approval: align operational gate thresholds with the eval split or switch to a validation dataset that can satisfy them."
                if not preflight_ready
                else "Keep execution disabled until operator approval; repair command contract blockers if any appear."
            ),
            reason=(
                f"target_id={target_id or 'missing'}, family={family or 'missing'}, bundle_tag={bundle_tag or 'missing'}, "
                f"preflight_ready={preflight_ready}, work_order_ready={work_order_ready}, "
                f"operational_gate_feasibility_status={_text(preflight.get('operational_gate_feasibility_status')) or 'not_checked'}, "
                f"preflight_blockers={';'.join(preflight_blocker_codes) or 'none'}, "
                f"eval_unique_keys={_int(gate_check.get('eval_unique_keys'))}, "
                f"gate_min_eval_unique_keys={_int(gate_check.get('gate_min_eval_unique_keys'))}, "
                f"eval_positive_keys={_int(gate_check.get('eval_positive_keys'))}, "
                f"ef1_max_possible={gate_check.get('ef1_max_possible') if gate_check.get('ef1_max_possible') is not None else 'unknown'}, "
                f"gate_ef1_min={gate_check.get('gate_ef1_min') if gate_check.get('gate_ef1_min') is not None else 'unknown'}."
            ),
        ),
        _row(
            priority=7,
            stage="operator_execution_approval",
            status="ready" if approval_authorized else "approval_required",
            source_status=_text(approval_gate.get("status")) or "missing",
            blocker_count=_int(approval_gate.get("blocker_count")),
            required_input="exact operator approval CSV decision and product execution token",
            approval_token_required=_text(approval_gate.get("approval_token_required")) or APPROVAL_TOKEN,
            source_artifact=approval_gate_path,
            recommended_action="Fill the product execution approval intake CSV only when the operator wants the docking run executed.",
            reason=(
                f"authorized_for_execution={approval_authorized}, "
                f"awaiting_operator_approval_row_count={_int(approval_gate.get('awaiting_operator_approval_row_count'))}, "
                f"operator_approval_csv_present={_bool(approval_gate.get('operator_approval_csv_present'))}."
            ),
        ),
        _row(
            priority=8,
            stage="bundle_contract",
            status="ready" if bundle_contract_ready else "blocked",
            source_status=_text(bundle_contract.get("status")) or "missing",
            blocker_count=_int(bundle_contract.get("blocker_count")),
            required_input="local-delivery bundle command contract",
            source_artifact=bundle_contract_path,
            recommended_action="After approved execution creates planned artifacts, run the recorded bundle command and final validator.",
            reason=f"expected_bundle_dir={_text(bundle_contract.get('expected_bundle_dir') or pilot.get('expected_bundle_dir')) or 'missing'}.",
        ),
        _row(
            priority=9,
            stage="bundle_assembly_and_validation",
            status="ready" if bundle_assembled and bundle_validation_passed else "blocked",
            source_status=_text(pilot.get("status")) or "missing",
            blocker_count=int(not bundle_assembled) + int(not bundle_validation_passed),
            required_input="assembled expected bundle directory and passing final bundle validation JSON",
            source_artifact=pilot_packet_path,
            recommended_action="Assemble the expected local-delivery bundle and run the final bundle validator after approved execution.",
            reason=(
                f"bundle_assembled={bundle_assembled}, bundle_validation_passed={bundle_validation_passed}, "
                f"bundle_dir_exists={_bool(pilot.get('bundle_dir_exists'))}."
            ),
        ),
        _row(
            priority=10,
            stage="delivery_ready_claim",
            status="ready" if delivery_ready_claim_allowed and pilot_delivery_ready else "blocked",
            source_status=f"{_text(delivery.get('status')) or 'missing'};{_text(pilot.get('status')) or 'missing'}",
            blocker_count=int(not delivery_ready_claim_allowed) + int(not pilot_delivery_ready),
            required_input="delivery evidence contract and pilot packet with delivery-ready claim allowed",
            source_artifact=f"{delivery_evidence_path};{pilot_packet_path}",
            recommended_action="Refresh delivery evidence and pilot packet after bundle validation passes.",
            reason=(
                f"delivery_ready_claim_allowed={delivery_ready_claim_allowed}, pilot_delivery_ready={pilot_delivery_ready}, "
                f"delivery_warning_count={_int(delivery.get('warning_count'))}, pilot_warning_count={_int(pilot.get('warning_count'))}."
            ),
        ),
    ]

    blocked_stage_count = sum(1 for row in rows if row["status"] == "blocked")
    approval_required_stage_count = sum(1 for row in rows if row["status"] == "approval_required")
    approval_tokens = sorted(
        {
            token
            for row in rows
            if row["status"] != "ready"
            for token in _approval_tokens(row["approval_token_required"])
        }
    )
    source_packets = [
        readiness_packet,
        capability_surface_packet or {},
        operational_quality_packet or {},
        architecture_packet or {},
        commercial_independence_packet or {},
        license_decision_packet or {},
        license_decision_options_packet or {},
        license_file_work_order_packet or {},
        preflight_packet,
        work_order_packet,
        public_benchmark_work_order_packet or {},
        approval_gate_packet,
        bundle_contract_packet,
        delivery_evidence_packet,
        pilot_packet,
    ]
    external_state_mutated = any(_bool(_summary(packet).get("external_state_mutated")) for packet in source_packets)
    execution_enabled = any(_bool(_summary(packet).get("execution_enabled")) for packet in source_packets)
    docking_results_emitted = any(_bool(_summary(packet).get("docking_results_emitted")) for packet in source_packets)
    status = (
        "product_release_operations_dossier_ready"
        if blocked_stage_count == 0 and approval_required_stage_count == 0 and pilot_delivery_ready
        else "blocked_product_release_operations_dossier"
    )
    summary = {
        "packet_type": "product_release_operations_dossier",
        "status": status,
        "target_id": target_id,
        "family": family,
        "bundle_tag": bundle_tag,
        "stage_count": len(rows),
        "blocked_stage_count": blocked_stage_count,
        "approval_required_stage_count": approval_required_stage_count,
        "capability_surface_ready": capability_surface_ready,
        "source_capability_surface_status": _text(capability_surface.get("status")),
        "operational_quality_ready": operational_quality_ready,
        "source_operational_quality_status": _text(operational_quality.get("status")),
        "operational_quality_blocker_count": _int(operational_quality.get("blocker_count")),
        "architecture_contract_ready": architecture_release_ready,
        "source_architecture_status": _text(architecture.get("status")),
        "architecture_local_surface_ready": architecture_local_surface_ready,
        "architecture_release_ready": _bool(architecture.get("architecture_release_ready")),
        "architecture_blocked_lane_count": _int(architecture.get("blocked_lane_count")),
        "architecture_approval_required_lane_count": _int(architecture.get("approval_required_lane_count")),
        "product_service_boundary_ready": _bool(architecture.get("product_service_boundary_ready")),
        "product_api_contract_ready": _bool(architecture.get("product_api_contract_ready")),
        "public_benchmark_validation_ready": public_benchmark_validation_ready,
        "public_benchmark_status": public_benchmark_status,
        "public_benchmark_required_suite_count": public_benchmark_required_suite_count,
        "public_benchmark_ready_required_suite_count": public_benchmark_ready_required_suite_count,
        "public_benchmark_blocked_suite_count": public_benchmark_blocked_suite_count,
        "public_benchmark_suite_materialization_manifest_count": public_benchmark_suite_materialization_manifest_count,
        "public_benchmark_suite_scorecard_row_csv_count": public_benchmark_suite_scorecard_row_csv_count,
        "public_benchmark_suite_threshold_count": public_benchmark_suite_threshold_count,
        "public_benchmark_suite_blocker_count": public_benchmark_suite_blocker_count,
        "public_benchmark_suite_run_command_count": public_benchmark_suite_run_command_count,
        "public_benchmark_suite_materialization_run_command_count": public_benchmark_suite_materialization_run_command_count,
        "public_benchmark_suite_result_provenance_command_count": public_benchmark_suite_result_provenance_command_count,
        "public_benchmark_suite_result_provenance_present_count": public_benchmark_suite_result_provenance_present_count,
        "public_benchmark_suite_no_external_dependency_count": public_benchmark_suite_no_external_dependency_count,
        "public_benchmark_requires_24h_server": _bool(architecture.get("public_benchmark_requires_24h_server")),
        "public_benchmark_requires_competition_season": _bool(architecture.get("public_benchmark_requires_competition_season")),
        "public_benchmark_requires_paid_vps": _bool(architecture.get("public_benchmark_requires_paid_vps")),
        "public_benchmark_work_order_status": public_benchmark_work_order_status,
        "public_benchmark_work_order_artifact": public_benchmark_work_order_path,
        "public_benchmark_work_order_open_suite_count": public_benchmark_work_order_open_suite_count,
        "public_benchmark_work_order_materialization_required_suite_count": public_benchmark_work_order_materialization_required_suite_count,
        "public_benchmark_work_order_scorecard_required_suite_count": public_benchmark_work_order_scorecard_required_suite_count,
        "public_benchmark_work_order_continuous_validation_command_count": public_benchmark_work_order_continuous_validation_command_count,
        "public_benchmark_work_order_suite_run_command_count": public_benchmark_work_order_suite_run_command_count,
        "public_benchmark_work_order_suite_result_provenance_command_count": public_benchmark_work_order_suite_result_provenance_command_count,
        "public_benchmark_work_order_suite_result_provenance_present_count": public_benchmark_work_order_suite_result_provenance_present_count,
        "public_benchmark_work_order_suite_threshold_count": public_benchmark_work_order_suite_threshold_count,
        "public_benchmark_work_order_suite_materialization_manifest_count": public_benchmark_work_order_suite_materialization_manifest_count,
        "public_benchmark_work_order_suite_scorecard_row_csv_count": public_benchmark_work_order_suite_scorecard_row_csv_count,
        "public_benchmark_work_order_suite_no_external_dependency_count": public_benchmark_work_order_suite_no_external_dependency_count,
        "public_benchmark_work_order_local_artifact_preflight_ready_suite_count": public_benchmark_work_order_local_artifact_preflight_ready_suite_count,
        "public_benchmark_work_order_local_artifact_preflight_blocked_suite_count": public_benchmark_work_order_local_artifact_preflight_blocked_suite_count,
        "public_benchmark_work_order_missing_local_input_artifact_count": public_benchmark_work_order_missing_local_input_artifact_count,
        "public_benchmark_work_order_missing_local_output_artifact_count": public_benchmark_work_order_missing_local_output_artifact_count,
        "public_benchmark_work_order_continuous_validation_command": public_benchmark_work_order_continuous_validation_command,
        "cameo_architecture_validation_ready": _bool(architecture.get("cameo_architecture_validation_ready")),
        "cameo_official_validation_evidence_ready": _bool(architecture.get("cameo_official_validation_evidence_ready")),
        "cameo_receiver_smoke_ready": _bool(architecture.get("cameo_receiver_smoke_ready")),
        "cameo_receiver_smoke_status": _text(architecture.get("cameo_receiver_smoke_status")),
        "cameo_api_dependency_ready": _bool(architecture.get("cameo_api_dependency_ready")),
        "cameo_api_dependency_status": _text(architecture.get("cameo_api_dependency_status")),
        "cameo_public_registration_allowed": _bool(architecture.get("cameo_public_registration_allowed")),
        "cameo_public_registration_blocker_count": _int(architecture.get("cameo_public_registration_blocker_count")),
        "cameo_registration_approval_token_count": _int(architecture.get("cameo_registration_approval_token_count")),
        "cameo_registration_approval_tokens_required": list(architecture.get("cameo_registration_approval_tokens_required") or []),
        "cleanup_postcheck_contract_ready": _bool(architecture.get("cleanup_postcheck_contract_ready")),
        "cleanup_postcheck_blocked_row_count": _int(architecture.get("cleanup_postcheck_blocked_row_count")),
        "structure_analysis_capability_ready": _bool(capability_surface.get("structure_analysis_capability_ready")),
        "ligand_docking_capability_ready": _bool(capability_surface.get("ligand_docking_capability_ready")),
        "product_api_surface_ready": _bool(capability_surface.get("api_surface_ready")),
        "commercial_independence_ready": commercial_independence_ready,
        "source_commercial_independence_status": _text(commercial.get("status")),
        "commercial_independent_product_claim_allowed": _bool(commercial.get("commercial_independent_product_claim_allowed")),
        "restricted_commercial_scope_claim_ready": restricted_commercial_scope_claim_ready,
        "commercial_claim_scope_tier": commercial_claim_scope_tier,
        "commercial_claim_scope_detail": commercial_claim_scope_detail,
        "commercial_allowed_scope_families": commercial_allowed_scope_families,
        "commercial_blocked_claim_scopes": commercial_blocked_claim_scopes,
        "commercial_general_platform_claim_allowed": commercial_general_platform_claim_allowed,
        "license_present": license_present,
        "source_license_decision_status": _text(license_decision.get("status")),
        "source_license_decision_packet_status": _text(license_options.get("status")),
        "source_license_file_creation_work_order_status": _text(license_file_work_order.get("status")),
        "license_decision_option_count": _int(license_options.get("option_count")),
        "license_decision_packet_ready": license_options_ready,
        "license_authorized_for_file_creation_review": license_decision_authorized,
        "license_file_creation_review_ready": license_file_creation_review_ready,
        "license_file_creation_work_order_blocker_count": _int(license_file_work_order.get("blocker_count")),
        "license_file_creation_work_order_artifact": license_file_work_order_path,
        "approval_token_count": len(approval_tokens),
        "approval_tokens_required": approval_tokens,
        "authorized_for_execution": approval_authorized,
        "bundle_contract_ready": bundle_contract_ready,
        "bundle_assembled": bundle_assembled,
        "bundle_validation_passed": bundle_validation_passed,
        "delivery_ready_claim_allowed": delivery_ready_claim_allowed,
        "pilot_delivery_ready": pilot_delivery_ready,
        "execution_enabled": execution_enabled,
        "docking_results_emitted": docking_results_emitted,
        "external_state_mutated": external_state_mutated,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Clear commercial-independence/license evidence, obtain exact product execution approval, run the approved execution path, assemble and validate the bundle, then refresh pilot evidence."
            if blocked_stage_count or approval_required_stage_count
            else "Product release operations dossier is clear."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product Release Operations Dossier",
        "",
        f"- status: `{s['status']}`",
        f"- target_id: `{s['target_id']}`",
        f"- family: `{s['family']}`",
        f"- bundle_tag: `{s['bundle_tag']}`",
        f"- blocked_stage_count: `{s['blocked_stage_count']}`",
        f"- approval_required_stage_count: `{s['approval_required_stage_count']}`",
        f"- capability_surface_ready: `{s['capability_surface_ready']}`",
        f"- source_capability_surface_status: `{s['source_capability_surface_status']}`",
        f"- operational_quality_ready: `{s['operational_quality_ready']}`",
        f"- source_operational_quality_status: `{s['source_operational_quality_status']}`",
        f"- operational_quality_blocker_count: `{s['operational_quality_blocker_count']}`",
        f"- architecture_contract_ready: `{s['architecture_contract_ready']}`",
        f"- source_architecture_status: `{s['source_architecture_status']}`",
        f"- architecture_local_surface_ready: `{s['architecture_local_surface_ready']}`",
        f"- architecture_release_ready: `{s['architecture_release_ready']}`",
        f"- architecture_blocked_lane_count: `{s['architecture_blocked_lane_count']}`",
        f"- architecture_approval_required_lane_count: `{s['architecture_approval_required_lane_count']}`",
        f"- product_service_boundary_ready: `{s['product_service_boundary_ready']}`",
        f"- product_api_contract_ready: `{s['product_api_contract_ready']}`",
        f"- public_benchmark_validation_ready: `{s['public_benchmark_validation_ready']}`",
        f"- public_benchmark_status: `{s['public_benchmark_status']}`",
        f"- public_benchmark_required_suite_count: `{s['public_benchmark_required_suite_count']}`",
        f"- public_benchmark_ready_required_suite_count: `{s['public_benchmark_ready_required_suite_count']}`",
        f"- public_benchmark_blocked_suite_count: `{s['public_benchmark_blocked_suite_count']}`",
        f"- public_benchmark_suite_materialization_manifest_count: `{s['public_benchmark_suite_materialization_manifest_count']}`",
        f"- public_benchmark_suite_scorecard_row_csv_count: `{s['public_benchmark_suite_scorecard_row_csv_count']}`",
        f"- public_benchmark_suite_threshold_count: `{s['public_benchmark_suite_threshold_count']}`",
        f"- public_benchmark_suite_blocker_count: `{s['public_benchmark_suite_blocker_count']}`",
        f"- public_benchmark_suite_run_command_count: `{s['public_benchmark_suite_run_command_count']}`",
        f"- public_benchmark_suite_materialization_run_command_count: `{s['public_benchmark_suite_materialization_run_command_count']}`",
        f"- public_benchmark_suite_no_external_dependency_count: `{s['public_benchmark_suite_no_external_dependency_count']}`",
        f"- public_benchmark_requires_24h_server: `{s['public_benchmark_requires_24h_server']}`",
        f"- public_benchmark_requires_competition_season: `{s['public_benchmark_requires_competition_season']}`",
        f"- public_benchmark_requires_paid_vps: `{s['public_benchmark_requires_paid_vps']}`",
        f"- public_benchmark_work_order_status: `{s['public_benchmark_work_order_status']}`",
        f"- public_benchmark_work_order_artifact: `{s['public_benchmark_work_order_artifact']}`",
        f"- public_benchmark_work_order_open_suite_count: `{s['public_benchmark_work_order_open_suite_count']}`",
        f"- public_benchmark_work_order_materialization_required_suite_count: `{s['public_benchmark_work_order_materialization_required_suite_count']}`",
        f"- public_benchmark_work_order_scorecard_required_suite_count: `{s['public_benchmark_work_order_scorecard_required_suite_count']}`",
        f"- public_benchmark_work_order_continuous_validation_command_count: `{s['public_benchmark_work_order_continuous_validation_command_count']}`",
        f"- public_benchmark_work_order_suite_run_command_count: `{s['public_benchmark_work_order_suite_run_command_count']}`",
        f"- public_benchmark_work_order_suite_threshold_count: `{s['public_benchmark_work_order_suite_threshold_count']}`",
        f"- public_benchmark_work_order_suite_materialization_manifest_count: `{s['public_benchmark_work_order_suite_materialization_manifest_count']}`",
        f"- public_benchmark_work_order_suite_scorecard_row_csv_count: `{s['public_benchmark_work_order_suite_scorecard_row_csv_count']}`",
        f"- public_benchmark_work_order_suite_no_external_dependency_count: `{s['public_benchmark_work_order_suite_no_external_dependency_count']}`",
        f"- public_benchmark_work_order_local_artifact_preflight_ready_suite_count: `{s['public_benchmark_work_order_local_artifact_preflight_ready_suite_count']}`",
        f"- public_benchmark_work_order_local_artifact_preflight_blocked_suite_count: `{s['public_benchmark_work_order_local_artifact_preflight_blocked_suite_count']}`",
        f"- public_benchmark_work_order_missing_local_input_artifact_count: `{s['public_benchmark_work_order_missing_local_input_artifact_count']}`",
        f"- public_benchmark_work_order_missing_local_output_artifact_count: `{s['public_benchmark_work_order_missing_local_output_artifact_count']}`",
        f"- public_benchmark_work_order_continuous_validation_command: `{s['public_benchmark_work_order_continuous_validation_command']}`",
        f"- cameo_architecture_validation_ready: `{s['cameo_architecture_validation_ready']}`",
        f"- cameo_official_validation_evidence_ready: `{s['cameo_official_validation_evidence_ready']}`",
        f"- cameo_receiver_smoke_ready: `{s['cameo_receiver_smoke_ready']}`",
        f"- cameo_receiver_smoke_status: `{s['cameo_receiver_smoke_status']}`",
        f"- cameo_api_dependency_ready: `{s['cameo_api_dependency_ready']}`",
        f"- cameo_api_dependency_status: `{s['cameo_api_dependency_status']}`",
        f"- cameo_public_registration_allowed: `{s['cameo_public_registration_allowed']}`",
        f"- cameo_public_registration_blocker_count: `{s['cameo_public_registration_blocker_count']}`",
        f"- cameo_registration_approval_token_count: `{s['cameo_registration_approval_token_count']}`",
        f"- cameo_registration_approval_tokens_required: `{';'.join(s['cameo_registration_approval_tokens_required'])}`",
        f"- cleanup_postcheck_contract_ready: `{s['cleanup_postcheck_contract_ready']}`",
        f"- cleanup_postcheck_blocked_row_count: `{s['cleanup_postcheck_blocked_row_count']}`",
        f"- structure_analysis_capability_ready: `{s['structure_analysis_capability_ready']}`",
        f"- ligand_docking_capability_ready: `{s['ligand_docking_capability_ready']}`",
        f"- product_api_surface_ready: `{s['product_api_surface_ready']}`",
        f"- commercial_independence_ready: `{s['commercial_independence_ready']}`",
        f"- source_commercial_independence_status: `{s['source_commercial_independence_status']}`",
        f"- commercial_independent_product_claim_allowed: `{s['commercial_independent_product_claim_allowed']}`",
        f"- restricted_commercial_scope_claim_ready: `{s['restricted_commercial_scope_claim_ready']}`",
        f"- commercial_claim_scope_tier: `{s['commercial_claim_scope_tier']}`",
        f"- commercial_claim_scope_detail: `{s['commercial_claim_scope_detail']}`",
        f"- commercial_allowed_scope_families: `{','.join(s['commercial_allowed_scope_families'])}`",
        f"- commercial_blocked_claim_scopes: `{','.join(s['commercial_blocked_claim_scopes'])}`",
        f"- commercial_general_platform_claim_allowed: `{s['commercial_general_platform_claim_allowed']}`",
        f"- license_present: `{s['license_present']}`",
        f"- source_license_decision_status: `{s['source_license_decision_status']}`",
        f"- source_license_decision_packet_status: `{s['source_license_decision_packet_status']}`",
        f"- source_license_file_creation_work_order_status: `{s['source_license_file_creation_work_order_status']}`",
        f"- license_decision_option_count: `{s['license_decision_option_count']}`",
        f"- license_decision_packet_ready: `{s['license_decision_packet_ready']}`",
        f"- license_authorized_for_file_creation_review: `{s['license_authorized_for_file_creation_review']}`",
        f"- license_file_creation_review_ready: `{s['license_file_creation_review_ready']}`",
        f"- license_file_creation_work_order_blocker_count: `{s['license_file_creation_work_order_blocker_count']}`",
        f"- license_file_creation_work_order_artifact: `{s['license_file_creation_work_order_artifact']}`",
        f"- approval_tokens_required: `{';'.join(s['approval_tokens_required'])}`",
        f"- authorized_for_execution: `{s['authorized_for_execution']}`",
        f"- bundle_assembled: `{s['bundle_assembled']}`",
        f"- bundle_validation_passed: `{s['bundle_validation_passed']}`",
        f"- delivery_ready_claim_allowed: `{s['delivery_ready_claim_allowed']}`",
        f"- pilot_delivery_ready: `{s['pilot_delivery_ready']}`",
        f"- execution_enabled: `{s['execution_enabled']}`",
        f"- docking_results_emitted: `{s['docking_results_emitted']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Stages",
        "",
        "| priority | stage | status | source_status | blockers | token | source | reason |",
        "| ---: | --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['priority']}` | `{row['stage']}` | `{row['status']}` | `{row['source_status']}` | "
            f"`{row['blocker_count']}` | `{row['approval_token_required']}` | `{row['source_artifact']}` | {row['reason']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a product release operations dossier from local artifacts.")
    parser.add_argument("--readiness-json", default=DEFAULT_READINESS_JSON)
    parser.add_argument("--capability-surface-json", default=DEFAULT_CAPABILITY_SURFACE_JSON)
    parser.add_argument("--operational-quality-json", default=DEFAULT_OPERATIONAL_QUALITY_JSON)
    parser.add_argument("--architecture-json", default=DEFAULT_ARCHITECTURE_JSON)
    parser.add_argument("--public-benchmark-work-order-json", default=DEFAULT_PUBLIC_BENCHMARK_WORK_ORDER_JSON)
    parser.add_argument("--preflight-json", default=DEFAULT_PREFLIGHT_JSON)
    parser.add_argument("--work-order-json", default=DEFAULT_WORK_ORDER_JSON)
    parser.add_argument("--approval-gate-json", default=DEFAULT_APPROVAL_GATE_JSON)
    parser.add_argument("--bundle-contract-json", default=DEFAULT_BUNDLE_CONTRACT_JSON)
    parser.add_argument("--delivery-evidence-json", default=DEFAULT_DELIVERY_EVIDENCE_JSON)
    parser.add_argument("--pilot-packet-json", default=DEFAULT_PILOT_PACKET_JSON)
    parser.add_argument("--commercial-independence-json", default=DEFAULT_COMMERCIAL_INDEPENDENCE_JSON)
    parser.add_argument("--license-decision-json", default=DEFAULT_LICENSE_DECISION_JSON)
    parser.add_argument("--license-decision-options-json", default=DEFAULT_LICENSE_DECISION_PACKET_JSON)
    parser.add_argument("--license-file-work-order-json", default=DEFAULT_LICENSE_FILE_WORK_ORDER_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_release_operations_dossier(
        readiness_packet=_read_json_if_present(args.readiness_json),
        capability_surface_packet=_read_json_if_present(args.capability_surface_json),
        operational_quality_packet=_read_json_if_present(args.operational_quality_json),
        preflight_packet=_read_json_if_present(args.preflight_json),
        work_order_packet=_read_json_if_present(args.work_order_json),
        approval_gate_packet=_read_json_if_present(args.approval_gate_json),
        bundle_contract_packet=_read_json_if_present(args.bundle_contract_json),
        delivery_evidence_packet=_read_json_if_present(args.delivery_evidence_json),
        pilot_packet=_read_json_if_present(args.pilot_packet_json),
        commercial_independence_packet=_read_json_if_present(args.commercial_independence_json),
        architecture_packet=_read_json_if_present(args.architecture_json),
        public_benchmark_work_order_packet=_read_json_if_present(args.public_benchmark_work_order_json),
        license_decision_packet=_read_json_if_present(args.license_decision_json),
        license_decision_options_packet=_read_json_if_present(args.license_decision_options_json),
        license_file_work_order_packet=_read_json_if_present(args.license_file_work_order_json),
        readiness_path=args.readiness_json,
        capability_surface_path=args.capability_surface_json,
        operational_quality_path=args.operational_quality_json,
        architecture_path=args.architecture_json,
        preflight_path=args.preflight_json,
        work_order_path=args.work_order_json,
        approval_gate_path=args.approval_gate_json,
        bundle_contract_path=args.bundle_contract_json,
        delivery_evidence_path=args.delivery_evidence_json,
        pilot_packet_path=args.pilot_packet_json,
        commercial_independence_path=args.commercial_independence_json,
        public_benchmark_work_order_path=args.public_benchmark_work_order_json,
        license_decision_path=args.license_decision_json,
        license_decision_options_path=args.license_decision_options_json,
        license_file_work_order_path=args.license_file_work_order_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
