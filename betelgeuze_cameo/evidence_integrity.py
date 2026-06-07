from __future__ import annotations

from typing import Any

from betelgeuze_cameo.official_results import DISALLOWED_LOCAL_ACCURACY_COLUMNS, METRIC_COLUMNS, REQUIRED_COLUMNS

CLAIM_BOUNDARY = (
    "CAMEO evidence integrity contract only; it audits local CAMEO validation artifacts for honest official-result "
    "provenance, operator intake schema visibility, approval gating, and disabled external mutation flags. It does not "
    "fetch official CAMEO pages, submit predictions, register servers, send email, use local native accuracy, or mutate "
    "external state."
)


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


def _row(check: str, passed: bool, observed: str, required: str, artifact_path: str, reason: str) -> dict[str, Any]:
    return {
        "check": check,
        "status": "pass" if passed else "fail",
        "observed": observed,
        "required": required,
        "artifact_path": artifact_path,
        "reason": reason,
        "release_blocker": not passed,
        "server_started": False,
        "server_registration_mutated": False,
        "prediction_generation_enabled": False,
        "outbound_email_enabled": False,
        "official_results_fetched": False,
        "native_local_accuracy_used": False,
        "external_state_mutated": False,
    }


def _blocker(row: dict[str, Any]) -> dict[str, str]:
    return {
        "code": f"{row['check']}_not_ready",
        "severity": "hard",
        "check": _text(row["check"]),
        "reason": f"{row['reason']} Observed: {row['observed']}; required: {row['required']}.",
    }


def _flag(packet: dict[str, Any], key: str) -> bool:
    return _bool(_summary(packet).get(key))


def build_cameo_evidence_integrity_contract(
    *,
    official_results_packet: dict[str, Any],
    architecture_validation_packet: dict[str, Any],
    operations_packet: dict[str, Any],
    registration_packet: dict[str, Any],
    official_results_path: str = "runs/cameo_official_results_intake_gate_current.json",
    architecture_validation_path: str = "runs/cameo_architecture_validation_contract_current.json",
    operations_path: str = "runs/cameo_validation_operations_dossier_current.json",
    registration_path: str = "runs/cameo_public_registration_approval_gate_current.json",
) -> dict[str, Any]:
    official = _summary(official_results_packet)
    architecture = _summary(architecture_validation_packet)
    operations = _summary(operations_packet)
    registration = _summary(registration_packet)

    official_ready = (
        _text(official.get("status")) == "cameo_official_results_intake_ready"
        and _bool(official.get("model1_official_result_ready"))
        and _int(official.get("accepted_official_result_count")) > 0
    )
    official_pending_honest = (
        _text(official.get("status")) == "blocked_cameo_official_results_intake"
        and _int(official.get("accepted_official_result_count")) == 0
        and "official_result_rows_missing" in set(official.get("blocker_codes") or [])
    )
    schema_visible = (
        bool(official.get("operator_template_csv"))
        and bool(official.get("operator_intake_csv"))
        and set(REQUIRED_COLUMNS).issubset(set(official.get("required_columns") or []))
        and set(METRIC_COLUMNS).issubset(set(official.get("official_metric_columns") or []))
        and set(DISALLOWED_LOCAL_ACCURACY_COLUMNS).issubset(
            set(official.get("disallowed_local_accuracy_columns") or [])
        )
    )
    no_local_substitution = (
        not _bool(official.get("native_local_accuracy_used"))
        and not _bool(architecture.get("native_local_accuracy_used"))
        and not _bool(operations.get("native_local_accuracy_used"))
        and (_bool(architecture.get("official_cameo_results_used")) is official_ready or not _bool(architecture.get("official_cameo_results_used")))
    )
    external_flags_clear = not any(
        _flag(packet, key)
        for packet in [official_results_packet, architecture_validation_packet, operations_packet, registration_packet]
        for key in (
            "server_registration_mutated",
            "prediction_generation_enabled",
            "outbound_email_enabled",
            "official_results_fetched",
            "external_state_mutated",
        )
    )
    registration_gated = (
        _text(registration.get("status")) in {
            "blocked_cameo_public_registration_approval_gate",
            "cameo_public_registration_approval_gate_ready",
            "cameo_public_registration_pending_operator_approval",
        }
        and _text(operations.get("registration_approval_token_required")) == "APPROVE_CAMEO_SERVER_REGISTRATION"
        and _text(operations.get("outbound_email_approval_token_required")) == "APPROVE_CAMEO_OUTBOUND_EMAIL"
        and not _bool(registration.get("server_registration_mutated"))
    )
    local_protocol_connected = (
        _bool(architecture.get("local_validation_protocol_ready"))
        and _bool(architecture.get("cameo_service_boundary_ready"))
        and _bool(architecture.get("cameo_api_contract_ready"))
    )

    rows = [
        _row(
            "official_result_provenance_honesty",
            official_ready or official_pending_honest,
            (
                f"status={_text(official.get('status')) or 'missing'};"
                f"accepted={_int(official.get('accepted_official_result_count'))};"
                f"model1={_bool(official.get('model1_official_result_ready'))};"
                f"blockers={';'.join(official.get('blocker_codes') or [])}"
            ),
            "official model1 result ready or explicitly blocked as official_result_rows_missing",
            official_results_path,
            "CAMEO validation must not claim official evidence before official rows are present.",
        ),
        _row(
            "official_result_schema_visible",
            schema_visible,
            (
                f"template={_text(official.get('operator_template_csv')) or 'missing'};"
                f"intake={_text(official.get('operator_intake_csv')) or 'missing'};"
                f"required={len(official.get('required_columns') or [])};metrics={len(official.get('official_metric_columns') or [])}"
            ),
            "operator template/intake paths, required columns, official metric columns, and disallowed local-accuracy columns are visible",
            official_results_path,
            "Operators need a stable schema boundary for official CAMEO assessment rows.",
        ),
        _row(
            "no_local_native_accuracy_substitution",
            no_local_substitution,
            (
                f"official_used={_bool(architecture.get('official_cameo_results_used'))};"
                f"official_ready={official_ready};native_local_accuracy_used="
                f"{_bool(official.get('native_local_accuracy_used')) or _bool(architecture.get('native_local_accuracy_used')) or _bool(operations.get('native_local_accuracy_used'))}"
            ),
            "no local native-accuracy substitution, and official-results-used only when official evidence is ready",
            f"{official_results_path};{architecture_validation_path};{operations_path}",
            "CAMEO performance validation must be based on official evidence, not local native answers or fabricated score rows.",
        ),
        _row(
            "external_mutation_flags_clear",
            external_flags_clear,
            (
                f"registration_mutated={_bool(registration.get('server_registration_mutated'))};"
                f"prediction_generation_enabled={_bool(operations.get('prediction_generation_enabled'))};"
                f"outbound_email_enabled={_bool(operations.get('outbound_email_enabled'))};"
                f"external_state_mutated={_bool(operations.get('external_state_mutated'))}"
            ),
            "registration, prediction generation, outbound email, official result fetch, and external mutation flags all false",
            f"{operations_path};{registration_path}",
            "The local validation evidence packet must stay read-only until explicit operator approval.",
        ),
        _row(
            "registration_and_email_gated",
            registration_gated,
            (
                f"registration_status={_text(registration.get('status')) or 'missing'};"
                f"registration_token={_text(operations.get('registration_approval_token_required')) or 'missing'};"
                f"email_token={_text(operations.get('outbound_email_approval_token_required')) or 'missing'}"
            ),
            "registration/email approval status is explicit and guarded by exact approval tokens",
            f"{operations_path};{registration_path}",
            "CAMEO public participation remains an operator-gated external-state change.",
        ),
        _row(
            "local_protocol_connected",
            local_protocol_connected,
            (
                f"local_protocol={_bool(architecture.get('local_validation_protocol_ready'))};"
                f"service_boundary={_bool(architecture.get('cameo_service_boundary_ready'))};"
                f"api_contract={_bool(architecture.get('cameo_api_contract_ready'))}"
            ),
            "local validation protocol, CAMEO service boundary, and CAMEO API contract ready",
            architecture_validation_path,
            "Official evidence can only be trusted if the local CAMEO validation protocol and surfaces are connected.",
        ),
    ]
    blockers = [_blocker(row) for row in rows if row["status"] != "pass"]
    ready = not blockers
    summary = {
        "packet_type": "cameo_evidence_integrity_contract",
        "status": "cameo_evidence_integrity_contract_ready" if ready else "blocked_cameo_evidence_integrity_contract",
        "evidence_integrity_ready": ready,
        "check_count": len(rows),
        "pass_count": sum(1 for row in rows if row["status"] == "pass"),
        "blocker_count": len(blockers),
        "official_result_provenance_honest": official_ready or official_pending_honest,
        "official_result_schema_visible": schema_visible,
        "official_results_ready": official_ready,
        "official_results_pending_honest": official_pending_honest,
        "no_local_native_accuracy_substitution": no_local_substitution,
        "external_mutation_flags_clear": external_flags_clear,
        "registration_and_email_gated": registration_gated,
        "local_protocol_connected": local_protocol_connected,
        "operator_intake_csv": _text(official.get("operator_intake_csv")),
        "missing_required_columns": list(official.get("missing_required_columns") or []),
        "server_started": False,
        "server_registration_mutated": False,
        "prediction_generation_enabled": False,
        "outbound_email_enabled": False,
        "official_results_fetched": False,
        "native_local_accuracy_used": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Evidence integrity is ready; official CAMEO result rows and registration/email approvals remain separate release blockers."
            if ready
            else "Repair failed CAMEO evidence-integrity checks before claiming CAMEO-based architecture validation."
        ),
    }
    return {"summary": summary, "rows": rows, "blockers": blockers}
