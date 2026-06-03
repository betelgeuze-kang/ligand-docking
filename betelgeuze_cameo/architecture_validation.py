from __future__ import annotations

from typing import Any

CLAIM_BOUNDARY = (
    "CAMEO architecture validation contract only; it links the local product architecture to the official CAMEO "
    "validation lane. It does not register a server, submit predictions, send email, fetch assessment pages, use local "
    "native accuracy, run docking, or mutate external state."
)


def _summary(packet: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(packet, dict):
        return {}
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


def _row(
    *,
    lane_id: str,
    status: str,
    observed: str,
    required: str,
    artifact_path: str,
    reason: str,
    approval_token_required: str = "",
) -> dict[str, Any]:
    return {
        "lane_id": lane_id,
        "status": status,
        "observed": observed,
        "required": required,
        "approval_token_required": approval_token_required,
        "artifact_path": artifact_path,
        "reason": reason,
        "server_registration_mutated": False,
        "prediction_generation_enabled": False,
        "outbound_email_enabled": False,
        "native_local_accuracy_used": False,
        "external_state_mutated": False,
    }


def _blocker(row: dict[str, Any]) -> dict[str, str]:
    return {
        "code": f"{row['lane_id']}_not_ready",
        "severity": "hard",
        "lane_id": _text(row["lane_id"]),
        "reason": f"{row['reason']} Observed: {row['observed']}; required: {row['required']}.",
    }


def build_cameo_architecture_validation_contract(
    *,
    product_architecture_packet: dict[str, Any],
    validation_operations_packet: dict[str, Any],
    validation_readiness_packet: dict[str, Any],
    performance_threshold_policy_packet: dict[str, Any],
    performance_scorecard_packet: dict[str, Any],
    official_results_packet: dict[str, Any],
    public_registration_packet: dict[str, Any],
    service_boundary_packet: dict[str, Any] | None = None,
    api_contract_packet: dict[str, Any] | None = None,
    product_architecture_path: str = "runs/product_architecture_contract_current.json",
    validation_operations_path: str = "runs/cameo_validation_operations_dossier_current.json",
    validation_readiness_path: str = "runs/cameo_validation_readiness_gate_current.json",
    performance_threshold_policy_path: str = "runs/cameo_performance_threshold_policy_current.json",
    performance_scorecard_path: str = "runs/cameo_performance_scorecard_current.json",
    official_results_path: str = "runs/cameo_official_results_intake_gate_current.json",
    public_registration_path: str = "runs/cameo_public_registration_approval_gate_current.json",
    service_boundary_path: str = "runs/cameo_service_boundary_contract_current.json",
    api_contract_path: str = "runs/cameo_api_contract_current.json",
) -> dict[str, Any]:
    architecture = _summary(product_architecture_packet)
    operations = _summary(validation_operations_packet)
    readiness = _summary(validation_readiness_packet)
    threshold_policy = _summary(performance_threshold_policy_packet)
    performance = _summary(performance_scorecard_packet)
    official = _summary(official_results_packet)
    registration = _summary(public_registration_packet)
    service_boundary = _summary(service_boundary_packet or {})
    api_contract = _summary(api_contract_packet or {})

    product_local_ready = _bool(architecture.get("local_architecture_surface_ready"))
    service_boundary_status = _text(service_boundary.get("status"))
    service_boundary_ready = (
        service_boundary_status == "cameo_service_boundary_contract_ready"
        and _bool(service_boundary.get("service_boundary_ready"))
        and _int(service_boundary.get("missing_api_route_count")) == 0
        and _int(service_boundary.get("missing_cli_command_count")) == 0
        and _int(service_boundary.get("artifact_registry_mismatch_count")) == 0
    )
    api_contract_status = _text(api_contract.get("status"))
    api_contract_ready = (
        api_contract_status == "cameo_api_contract_ready"
        and _bool(api_contract.get("api_contract_ready"))
        and _int(api_contract.get("missing_route_count")) == 0
        and _int(api_contract.get("status_response_missing_key_count")) == 0
    )
    operations_present = bool(operations)
    operations_surface_ready = operations_present and _int(operations.get("stage_count")) > 0
    readiness_present = bool(readiness)
    readiness_status = _text(readiness.get("status"))
    validation_evidence_ready = (
        readiness_status == "cameo_validation_evidence_ready"
        and _bool(readiness.get("official_cameo_results_used"))
    )
    threshold_policy_status = _text(threshold_policy.get("status"))
    threshold_policy_ready = (
        threshold_policy_status == "cameo_performance_threshold_policy_ready"
        and _bool(threshold_policy.get("threshold_policy_ready"))
    )
    performance_present = bool(performance)
    performance_status = _text(performance.get("status"))
    performance_evidence_ready = (
        performance_status == "cameo_performance_evidence_ready"
        and _bool(performance.get("official_cameo_results_used"))
        and _int(performance.get("model1_official_result_count")) >= 1
    )
    official_status = _text(official.get("status"))
    official_results_ready = (
        official_status == "cameo_official_results_intake_ready"
        and _bool(official.get("model1_official_result_ready"))
        and _int(official.get("accepted_official_result_count")) >= 1
    )
    registration_status = _text(registration.get("status"))
    registration_authorized = _bool(registration.get("authorized_for_registration_review"))
    registration_prepared = bool(registration)

    local_validation_protocol_ready = (
        product_local_ready
        and service_boundary_ready
        and api_contract_ready
        and operations_surface_ready
        and readiness_present
        and threshold_policy_ready
    )
    cameo_architecture_validation_ready = (
        local_validation_protocol_ready
        and validation_evidence_ready
        and performance_evidence_ready
        and official_results_ready
        and registration_authorized
    )

    rows = [
        _row(
            lane_id="product_architecture_local_surface",
            status="ready" if product_local_ready else "blocked",
            observed=(
                f"architecture_status={_text(architecture.get('status')) or 'missing'};"
                f"local_architecture_surface_ready={product_local_ready}"
            ),
            required="local product architecture surface ready before CAMEO validation can support product claims",
            artifact_path=product_architecture_path,
            reason="CAMEO validation must be tied to the current product architecture, not a detached benchmark note.",
        ),
        _row(
            lane_id="cameo_validation_operations_surface",
            status="ready" if operations_surface_ready else "blocked",
            observed=(
                f"operations_status={_text(operations.get('status')) or 'missing'};"
                f"stage_count={_int(operations.get('stage_count'))}"
            ),
            required="CAMEO validation operations dossier with staged operator/runtime/registration gates",
            artifact_path=validation_operations_path,
            reason="The architecture needs a visible CAMEO operations lane before external validation is attempted.",
        ),
        _row(
            lane_id="cameo_service_boundary_contract",
            status="ready" if service_boundary_ready else "blocked",
            observed=(
                f"service_boundary_status={service_boundary_status or 'missing'};"
                f"service_boundary_ready={_bool(service_boundary.get('service_boundary_ready'))};"
                f"api_route_count={_int(service_boundary.get('api_route_count'))};"
                f"expected_api_route_count={_int(service_boundary.get('expected_api_route_count'))};"
                f"cli_command_count={_int(service_boundary.get('cli_command_count'))};"
                f"expected_cli_command_count={_int(service_boundary.get('expected_cli_command_count'))};"
                f"artifact_registry_mismatch_count={_int(service_boundary.get('artifact_registry_mismatch_count'))}"
            ),
            required="CAMEO service-boundary contract ready with complete API route, CLI command, console script, and artifact registry coverage",
            artifact_path=service_boundary_path,
            reason="The CAMEO validation lane should expose a coherent service boundary before it supports product architecture claims.",
        ),
        _row(
            lane_id="cameo_api_contract",
            status="ready" if api_contract_ready else "blocked",
            observed=(
                f"api_contract_status={api_contract_status or 'missing'};"
                f"api_contract_ready={_bool(api_contract.get('api_contract_ready'))};"
                f"expected_route_count={_int(api_contract.get('expected_route_count'))};"
                f"missing_route_count={_int(api_contract.get('missing_route_count'))};"
                f"status_response_missing_key_count={_int(api_contract.get('status_response_missing_key_count'))}"
            ),
            required="CAMEO API contract ready with complete route coverage and status response safety/domain keys",
            artifact_path=api_contract_path,
            reason="The CAMEO validation API needs a static contract before it can serve as architecture validation evidence.",
        ),
        _row(
            lane_id="cameo_validation_readiness_evidence",
            status=(
                "ready"
                if validation_evidence_ready
                else ("approval_required" if readiness_status == "cameo_validation_pending_official_results" else "blocked")
            ),
            observed=(
                f"readiness_status={readiness_status or 'missing'};"
                f"official_cameo_results_used={_bool(readiness.get('official_cameo_results_used'))}"
            ),
            required="CAMEO validation readiness with official CAMEO result evidence",
            artifact_path=validation_readiness_path,
            reason="The architecture performance claim must be based on official CAMEO evidence, not local native accuracy.",
        ),
        _row(
            lane_id="cameo_performance_threshold_policy",
            status="ready" if threshold_policy_ready else "blocked",
            observed=(
                f"threshold_policy_status={threshold_policy_status or 'missing'};"
                f"threshold_policy_ready={threshold_policy_ready};"
                f"profile_name={_text(threshold_policy.get('profile_name')) or 'missing'};"
                f"min_model1_lddt={threshold_policy.get('min_model1_lddt', 'missing')};"
                f"min_model1_tm_score={threshold_policy.get('min_model1_tm_score', 'missing')};"
                f"max_model1_rmsd_A={threshold_policy.get('max_model1_rmsd_A', 'missing')}"
            ),
            required="product-grade model1 threshold policy with non-placeholder lDDT, TM-score, QS-score, and finite RMSD thresholds",
            artifact_path=performance_threshold_policy_path,
            reason="The CAMEO scorecard must be judged against explicit product thresholds rather than permissive placeholders.",
        ),
        _row(
            lane_id="cameo_performance_scorecard",
            status=(
                "ready"
                if performance_evidence_ready
                else ("approval_required" if performance_status == "cameo_performance_pending_official_results" else "blocked")
            ),
            observed=(
                f"performance_status={performance_status or 'missing'};"
                f"model1_official_result_count={_int(performance.get('model1_official_result_count'))};"
                f"official_cameo_results_used={_bool(performance.get('official_cameo_results_used'))}"
            ),
            required="model1-centered CAMEO performance scorecard using accepted official result rows",
            artifact_path=performance_scorecard_path,
            reason="The CAMEO validation lane needs a scorecard that can be compared against product thresholds.",
        ),
        _row(
            lane_id="cameo_official_results_intake",
            status="ready" if official_results_ready else ("approval_required" if official else "blocked"),
            observed=(
                f"official_results_status={official_status or 'missing'};"
                f"accepted_official_result_count={_int(official.get('accepted_official_result_count'))};"
                f"model1_official_result_ready={_bool(official.get('model1_official_result_ready'))}"
            ),
            required="operator-provided official CAMEO result rows with model1 official metric evidence",
            artifact_path=official_results_path,
            reason="Official result intake is the provenance boundary for CAMEO-based performance validation.",
        ),
        _row(
            lane_id="cameo_public_registration_approval",
            status=(
                "ready"
                if registration_authorized
                else ("approval_required" if registration_status == "cameo_public_registration_pending_operator_approval" else "blocked")
            ),
            observed=(
                f"registration_status={registration_status or 'missing'};"
                f"authorized_for_registration_review={registration_authorized}"
            ),
            required="explicit operator authorization for CAMEO server registration and outbound email review",
            approval_token_required="APPROVE_CAMEO_SERVER_REGISTRATION;APPROVE_CAMEO_OUTBOUND_EMAIL",
            artifact_path=public_registration_path,
            reason="External CAMEO participation remains operator-gated even after local surfaces are ready.",
        ),
        _row(
            lane_id="fail_closed_claim_boundary",
            status="ready",
            observed="server_registration_mutated=False;prediction_generation_enabled=False;outbound_email_enabled=False;native_local_accuracy_used=False;external_state_mutated=False",
            required="contract reports evidence only and performs no external registration, prediction submission, email, or native-accuracy substitution",
            artifact_path="betelgeuze_cameo/architecture_validation.py",
            reason="The validation contract must not imply scientific or external actions that did not happen.",
        ),
    ]
    blockers = [_blocker(row) for row in rows if row["status"] == "blocked"]
    approval_required = [row for row in rows if row["status"] == "approval_required"]
    ready_count = sum(1 for row in rows if row["status"] == "ready")
    status = (
        "cameo_architecture_validation_contract_ready"
        if cameo_architecture_validation_ready
        else "blocked_cameo_architecture_validation_contract"
    )
    summary = {
        "packet_type": "cameo_architecture_validation_contract",
        "status": status,
        "lane_count": len(rows),
        "ready_lane_count": ready_count,
        "blocked_lane_count": len(blockers),
        "approval_required_lane_count": len(approval_required),
        "local_validation_protocol_ready": local_validation_protocol_ready,
        "cameo_architecture_validation_ready": cameo_architecture_validation_ready,
        "product_architecture_local_surface_ready": product_local_ready,
        "cameo_service_boundary_ready": service_boundary_ready,
        "cameo_service_boundary_status": service_boundary_status,
        "cameo_service_boundary_api_route_count": _int(service_boundary.get("api_route_count")),
        "cameo_service_boundary_cli_command_count": _int(service_boundary.get("cli_command_count")),
        "cameo_api_contract_ready": api_contract_ready,
        "cameo_api_contract_status": api_contract_status,
        "cameo_api_contract_expected_route_count": _int(api_contract.get("expected_route_count")),
        "cameo_api_contract_missing_route_count": _int(api_contract.get("missing_route_count")),
        "cameo_api_contract_status_response_missing_key_count": _int(api_contract.get("status_response_missing_key_count")),
        "validation_operations_surface_ready": operations_surface_ready,
        "validation_evidence_ready": validation_evidence_ready,
        "performance_threshold_policy_ready": threshold_policy_ready,
        "performance_threshold_profile_name": _text(threshold_policy.get("profile_name")),
        "performance_scorecard_evidence_ready": performance_evidence_ready,
        "official_results_ready": official_results_ready,
        "public_registration_authorized": registration_authorized,
        "official_cameo_results_used": validation_evidence_ready or performance_evidence_ready or official_results_ready,
        "server_registration_mutated": False,
        "prediction_generation_enabled": False,
        "outbound_email_enabled": False,
        "native_local_accuracy_used": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "CAMEO architecture validation evidence is ready for product release review."
            if cameo_architecture_validation_ready
            else (
                "Local CAMEO validation protocol is connected; obtain official CAMEO model1 results and explicit registration/email approval before release claims."
                if local_validation_protocol_ready
                else "Repair local product architecture and CAMEO validation operations surfaces before CAMEO-based architecture validation."
            )
        ),
    }
    return {"summary": summary, "blockers": blockers, "approval_required": approval_required, "rows": rows}
