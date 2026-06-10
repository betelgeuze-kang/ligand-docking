from __future__ import annotations

from typing import Any

CLAIM_BOUNDARY = (
    "CAMEO capability preflight only; it audits receiver/capability policy before any public server registration or outbound email. "
    "It does not register a CAMEO server, submit predictions, send email, run predictions, use local native accuracy, or mutate external state."
)
REGISTRATION_APPROVAL_TOKEN = "APPROVE_CAMEO_SERVER_REGISTRATION"
OUTBOUND_EMAIL_APPROVAL_TOKEN = "APPROVE_CAMEO_OUTBOUND_EMAIL"
ALLOWED_DEVELOPMENT_CAPABILITY_LANES = {"polymer_complex_receiver_dry_run"}


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


def _check(name: str, passed: bool, observed: str, required: str) -> dict[str, Any]:
    return {
        "check": name,
        "status": "pass" if passed else "fail",
        "observed": observed,
        "required": required,
        "action_executed": False,
        "outbound_email_enabled": False,
        "external_state_mutated": False,
    }


def _blocker(code: str, reason: str, *, check: str = "") -> dict[str, str]:
    payload = {"code": code, "severity": "hard", "reason": reason}
    if check:
        payload["check"] = check
    return payload


def _warning(code: str, reason: str, *, check: str = "") -> dict[str, str]:
    payload = {"code": code, "severity": "warning", "reason": reason}
    if check:
        payload["check"] = check
    return payload


def build_cameo_capability_preflight(
    *,
    validation_readiness_packet: dict[str, Any],
    repair_execution_preflight_packet: dict[str, Any],
    receiver_smoke_packet: dict[str, Any] | None = None,
    receiver_scaffold_present: bool,
    api_route_registered: bool,
    api_operations_route_registered: bool = False,
    local_status_cli_present: bool = False,
    capability_lane: str = "polymer_complex_receiver_dry_run",
    public_registration_requested: bool = False,
    registration_approval_token: str = "",
    outbound_email_requested: bool = False,
    outbound_email_approval_token: str = "",
    prediction_generation_requested: bool = False,
) -> dict[str, Any]:
    validation = _summary(validation_readiness_packet)
    repair = _summary(repair_execution_preflight_packet)
    receiver_smoke_packet = receiver_smoke_packet or {}
    receiver_smoke = _summary(receiver_smoke_packet)
    validation_status = _text(validation.get("status"))
    repair_status = _text(repair.get("status"))
    receiver_smoke_status = _text(receiver_smoke.get("status"))
    capability_lane = _text(capability_lane)

    rows: list[dict[str, Any]] = []
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    registration_blockers: list[dict[str, str]] = []

    checks = [
        (
            "receiver_scaffold_present",
            receiver_scaffold_present,
            str(receiver_scaffold_present),
            "api/cameo.py and betelgeuze_cameo/intake.py present",
        ),
        (
            "api_route_registered",
            api_route_registered,
            str(api_route_registered),
            "CAMEO /cameo/targets route registered or import-smoke covered",
        ),
        (
            "api_operations_route_registered",
            api_operations_route_registered,
            str(api_operations_route_registered),
            "CAMEO /cameo/operations, /cameo/architecture-validation, /cameo/official-results, /cameo/registration-approval, /cameo/api-contract, and /cameo/service-boundary read-only routes registered or import-smoke covered",
        ),
        (
            "local_status_cli_present",
            local_status_cli_present,
            str(local_status_cli_present),
            "betelgeuze_cameo/cli.py read-only local status surface present",
        ),
        (
            "capability_lane_conservative",
            capability_lane in ALLOWED_DEVELOPMENT_CAPABILITY_LANES,
            capability_lane,
            "polymer_complex_receiver_dry_run",
        ),
        (
            "outbound_email_disabled",
            not outbound_email_requested,
            str(outbound_email_requested),
            "False until dry-run handoff, validation evidence, and explicit email approval are ready",
        ),
        (
            "prediction_generation_disabled",
            not prediction_generation_requested,
            str(prediction_generation_requested),
            "False until production prediction pipeline is explicitly wired and approved",
        ),
    ]
    for name, passed, observed, required in checks:
        rows.append(_check(name, passed, observed, required))
        if not passed:
            blockers.append(_blocker(f"{name}_failed", f"{name} must satisfy: {required}; observed: {observed}", check=name))

    receiver_smoke_ready = not receiver_smoke_packet or receiver_smoke_status == "cameo_receiver_smoke_ready"
    if receiver_smoke_packet:
        rows.append(
            _check(
                "receiver_runtime_smoke_ready",
                receiver_smoke_ready,
                receiver_smoke_status,
                "cameo_receiver_smoke_ready with POST /cameo/targets HTTP 200 and fail-closed ledger evidence",
            )
        )
        if not receiver_smoke_ready:
            blockers.append(
                _blocker(
                    "receiver_runtime_smoke_not_ready",
                    f"CAMEO receiver runtime smoke must pass before development server readiness; observed: {receiver_smoke_status or 'missing'}.",
                    check="receiver_runtime_smoke_ready",
                )
            )

    validation_evidence_ready = validation_status == "cameo_validation_evidence_ready"
    repair_ready = repair_status in {
        "cameo_repair_execution_preflight_ready",
        "cameo_repair_execution_not_required",
    }
    registration_token_ok = _text(registration_approval_token) == REGISTRATION_APPROVAL_TOKEN
    email_token_ok = _text(outbound_email_approval_token) == OUTBOUND_EMAIL_APPROVAL_TOKEN

    registration_checks = [
        ("validation_evidence_ready", validation_evidence_ready, validation_status, "cameo_validation_evidence_ready"),
        ("repair_execution_preflight_ready", repair_ready, repair_status, "cameo_repair_execution_preflight_ready"),
        (
            "registration_approval_token_present",
            registration_token_ok,
            "present" if registration_approval_token else "missing",
            REGISTRATION_APPROVAL_TOKEN,
        ),
        (
            "outbound_email_approval_token_present",
            email_token_ok,
            "present" if outbound_email_approval_token else "missing",
            OUTBOUND_EMAIL_APPROVAL_TOKEN,
        ),
    ]
    for name, passed, observed, required in registration_checks:
        rows.append(_check(f"public_registration_{name}", passed, observed, required))
        if not passed:
            registration_blockers.append(
                _blocker(
                    f"public_registration_{name}_blocked",
                    f"Public CAMEO registration requires {required}; observed: {observed or 'missing'}.",
                    check=f"public_registration_{name}",
                )
            )

    public_registration_allowed = (
        public_registration_requested
        and not blockers
        and not registration_blockers
        and not outbound_email_requested
        and not prediction_generation_requested
    )
    if public_registration_requested and not public_registration_allowed:
        blockers.extend(registration_blockers)
    elif not public_registration_requested:
        warnings.append(
            _warning(
                "public_registration_not_requested",
                "Development receiver capability can be inspected locally, but public CAMEO server registration remains disabled.",
                check="public_registration",
            )
        )

    status = (
        "cameo_public_registration_preflight_ready"
        if public_registration_allowed
        else ("blocked_cameo_capability_preflight" if blockers else "cameo_development_capability_preflight_ready")
    )
    summary = {
        "packet_type": "cameo_capability_preflight",
        "status": status,
        "capability_lane": capability_lane,
        "receiver_scaffold_present": receiver_scaffold_present,
        "api_route_registered": api_route_registered,
        "api_operations_route_registered": api_operations_route_registered,
        "local_status_cli_present": local_status_cli_present,
        "source_validation_status": validation_status,
        "source_repair_execution_preflight_status": repair_status,
        "source_receiver_smoke_status": receiver_smoke_status,
        "source_api_dependency_status": _text(receiver_smoke.get("source_api_dependency_status")),
        "api_dependency_ready": bool(receiver_smoke.get("api_dependency_ready") is True),
        "api_dependency_blocker_count": _int(receiver_smoke.get("api_dependency_blocker_count")),
        "receiver_smoke_post_200_ok": bool(receiver_smoke.get("post_200_ok") is True),
        "receiver_smoke_blocker_count": _int(receiver_smoke.get("blocker_count")),
        "public_registration_requested": public_registration_requested,
        "public_registration_allowed": public_registration_allowed,
        "public_registration_blocker_count": len(registration_blockers),
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "outbound_email_enabled": False,
        "prediction_generation_enabled": False,
        "action_executed": False,
        "server_registration_mutated": False,
        "external_state_mutated": False,
        "native_local_accuracy_used": False,
        "registration_approval_token_required": REGISTRATION_APPROVAL_TOKEN,
        "outbound_email_approval_token_required": OUTBOUND_EMAIL_APPROVAL_TOKEN,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Keep local development receiver only; fill CAMEO operator inputs and reach validation evidence-ready before requesting public registration."
            if status == "cameo_development_capability_preflight_ready"
            else (
                "Operator may proceed with separate public CAMEO registration review; this packet still performs no registration or email action."
                if status == "cameo_public_registration_preflight_ready"
                else "Repair failed CAMEO capability checks before requesting registration or outbound email."
            )
        ),
    }
    return {"summary": summary, "blockers": blockers, "registration_blockers": registration_blockers, "warnings": warnings, "rows": rows}
