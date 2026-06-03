#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_KIT_JSON = "runs/cameo_operator_input_kit_current/manifest.json"
DEFAULT_INPUT_VALIDATION_JSON = "runs/cameo_operator_input_validation_current.json"
DEFAULT_REPAIR_PREFLIGHT_JSON = "runs/cameo_repair_execution_preflight_current.json"
DEFAULT_READINESS_JSON = "runs/cameo_validation_readiness_gate_current.json"
DEFAULT_OFFICIAL_RESULTS_INTAKE_JSON = "runs/cameo_official_results_intake_gate_current.json"
DEFAULT_EVIDENCE_INTEGRITY_JSON = "runs/cameo_evidence_integrity_contract_current.json"
DEFAULT_RUNTIME_REPAIR_JSON = "runs/cameo_runtime_repair_work_order_current.json"
DEFAULT_API_DEPENDENCY_JSON = "runs/cameo_api_dependency_readiness_current.json"
DEFAULT_RECEIVER_SMOKE_JSON = "runs/cameo_receiver_smoke_contract_current.json"
DEFAULT_CAPABILITY_PREFLIGHT_JSON = "runs/cameo_capability_preflight_current.json"
DEFAULT_OUT_JSON = "runs/cameo_validation_operations_dossier_current.json"
DEFAULT_OUT_CSV = "runs/cameo_validation_operations_dossier_current.csv"
DEFAULT_OUT_MD = "runs/cameo_validation_operations_dossier_current.md"

API_APPROVAL_TOKEN = "APPROVE_API_DEPENDENCY_INSTALL"
REGISTRATION_APPROVAL_TOKEN = "APPROVE_CAMEO_SERVER_REGISTRATION"
OUTBOUND_EMAIL_APPROVAL_TOKEN = "APPROVE_CAMEO_OUTBOUND_EMAIL"

CLAIM_BOUNDARY = (
    "CAMEO validation operations dossier only; it consolidates local CAMEO operator-input, validation, runtime, and "
    "registration-readiness artifacts. It does not install packages, start a server, register a CAMEO server, submit "
    "predictions, send email, run prediction generation, use local native accuracy, or mutate external state."
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


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in packet.get("rows", []) or [] if isinstance(row, dict)]


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


def _status_for_ready(actual_status: str, ready_statuses: set[str], *, missing: bool = False) -> str:
    if missing:
        return "blocked"
    if actual_status in ready_statuses:
        return "ready"
    if actual_status:
        return "blocked"
    return "blocked"


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
    official_result_required: bool = False,
) -> dict[str, Any]:
    return {
        "priority": priority,
        "stage": stage,
        "status": status,
        "source_status": source_status,
        "blocker_count": blocker_count,
        "required_input": required_input,
        "approval_token_required": approval_token_required,
        "official_result_required": official_result_required,
        "source_artifact": source_artifact,
        "recommended_action": recommended_action,
        "reason": reason,
        "package_install_executed": False,
        "server_started": False,
        "server_registration_mutated": False,
        "prediction_generation_enabled": False,
        "outbound_email_enabled": False,
        "external_state_mutated": False,
    }


def build_cameo_validation_operations_dossier(
    *,
    input_kit_packet: dict[str, Any],
    input_validation_packet: dict[str, Any],
    repair_preflight_packet: dict[str, Any],
    readiness_packet: dict[str, Any],
    runtime_repair_packet: dict[str, Any],
    api_dependency_packet: dict[str, Any],
    receiver_smoke_packet: dict[str, Any],
    capability_preflight_packet: dict[str, Any],
    official_results_intake_packet: dict[str, Any] | None = None,
    evidence_integrity_packet: dict[str, Any] | None = None,
    input_kit_path: str = DEFAULT_INPUT_KIT_JSON,
    input_validation_path: str = DEFAULT_INPUT_VALIDATION_JSON,
    repair_preflight_path: str = DEFAULT_REPAIR_PREFLIGHT_JSON,
    readiness_path: str = DEFAULT_READINESS_JSON,
    official_results_intake_path: str = DEFAULT_OFFICIAL_RESULTS_INTAKE_JSON,
    evidence_integrity_path: str = DEFAULT_EVIDENCE_INTEGRITY_JSON,
    runtime_repair_path: str = DEFAULT_RUNTIME_REPAIR_JSON,
    api_dependency_path: str = DEFAULT_API_DEPENDENCY_JSON,
    receiver_smoke_path: str = DEFAULT_RECEIVER_SMOKE_JSON,
    capability_preflight_path: str = DEFAULT_CAPABILITY_PREFLIGHT_JSON,
) -> dict[str, Any]:
    input_kit = _summary(input_kit_packet)
    input_validation = _summary(input_validation_packet)
    repair_preflight = _summary(repair_preflight_packet)
    readiness = _summary(readiness_packet)
    official_results = _summary(official_results_intake_packet or {})
    evidence_integrity = _summary(evidence_integrity_packet or {})
    runtime_repair = _summary(runtime_repair_packet)
    api_dependency = _summary(api_dependency_packet)
    receiver_smoke = _summary(receiver_smoke_packet)
    capability = _summary(capability_preflight_packet)

    input_status = _text(input_validation.get("status"))
    input_blockers = _int(input_validation.get("blocker_count"))
    required_template_count = _int(input_kit.get("required_template_count"))
    if required_template_count == 0:
        required_template_count = sum(1 for row in _rows(input_kit_packet) if row.get("required_now") is True)
    input_row_status = _status_for_ready(
        input_status,
        {
            "cameo_operator_inputs_ready",
            "cameo_operator_inputs_ready_pending_official_results",
            "cameo_operator_inputs_ready_with_official_results",
        },
        missing=not input_validation_packet,
    )

    readiness_status = _text(readiness.get("status"))
    validation_row_status = _status_for_ready(
        readiness_status,
        {"cameo_validation_evidence_ready", "cameo_validation_pending_official_results"},
        missing=not readiness_packet,
    )
    official_results_ready = bool(readiness_status == "cameo_validation_evidence_ready" and readiness.get("official_cameo_results_used") is True)
    official_results_intake_status = _text(official_results.get("status"))
    official_results_intake_ready = (
        official_results_intake_status == "cameo_official_results_intake_ready"
        and _bool(official_results.get("model1_official_result_ready"))
    )
    official_result_required = not (official_results_ready and official_results_intake_ready)
    evidence_integrity_ready = (
        _text(evidence_integrity.get("status")) == "cameo_evidence_integrity_contract_ready"
        and _bool(evidence_integrity.get("evidence_integrity_ready"))
    )

    repair_status = _text(repair_preflight.get("status"))
    repair_row_status = _status_for_ready(
        repair_status,
        {"cameo_repair_execution_preflight_ready", "cameo_repair_execution_not_required"},
        missing=not repair_preflight_packet,
    )

    api_status = _text(api_dependency.get("status"))
    smoke_status = _text(receiver_smoke.get("status"))
    runtime_status = _text(runtime_repair.get("status"))
    runtime_blockers = _int(api_dependency.get("blocker_count")) + _int(receiver_smoke.get("blocker_count"))
    runtime_receiver_smoke_ready = api_status == "cameo_api_dependency_ready" and smoke_status == "cameo_receiver_smoke_ready"
    runtime_install_approval_required = (
        False
        if runtime_receiver_smoke_ready
        else _bool(runtime_repair.get("install_approval_required")) or api_status == "blocked_cameo_api_dependency_readiness"
    )
    runtime_row_status = "ready" if runtime_receiver_smoke_ready else ("approval_required" if runtime_install_approval_required else "blocked")
    if not api_dependency_packet or not receiver_smoke_packet:
        runtime_row_status = "blocked"
    runtime_recommended_action = (
        "Runtime dependency readiness and local POST /cameo/targets smoke are complete."
        if runtime_row_status == "ready"
        else "After explicit approval, activate API dependencies, then rerun API dependency readiness, receiver smoke, and capability preflight."
    )

    capability_status = _text(capability.get("status"))
    public_registration_allowed = _bool(capability.get("public_registration_allowed"))
    registration_row_status = "approval_required" if public_registration_allowed else "blocked"
    registration_tokens = ";".join(
        token
        for token in [
            _text(capability.get("registration_approval_token_required")) or REGISTRATION_APPROVAL_TOKEN,
            _text(capability.get("outbound_email_approval_token_required")) or OUTBOUND_EMAIL_APPROVAL_TOKEN,
        ]
        if token
    )

    rows = [
        _row(
            priority=1,
            stage="operator_inputs",
            status=input_row_status,
            source_status=input_status,
            blocker_count=input_blockers,
            required_input="filled CAMEO candidates, models, and official-results CSV rows",
            source_artifact=input_validation_path,
            recommended_action="Fill or repair operator CSV rows, then rerun build_cameo_operator_input_validation.py.",
            reason=(
                f"input_kit_status={_text(input_kit.get('status')) or 'missing'}, "
                f"required_template_count={required_template_count}, blocker_count={input_blockers}."
            ),
            official_result_required=official_result_required,
        ),
        _row(
            priority=2,
            stage="repair_execution_preflight",
            status=repair_row_status,
            source_status=repair_status,
            blocker_count=_int(repair_preflight.get("blocker_count")),
            required_input="repair command preflight with checked operator inputs",
            source_artifact=repair_preflight_path,
            recommended_action="Regenerate repair preflight after operator input validation is clear.",
            reason=f"source_operator_input_validation_status={_text(repair_preflight.get('source_operator_input_validation_status')) or input_status or 'missing'}.",
            official_result_required=official_result_required,
        ),
        _row(
            priority=3,
            stage="official_results_intake",
            status=_status_for_ready(
                official_results_intake_status,
                {"cameo_official_results_intake_ready"},
                missing=not official_results_intake_packet,
            ),
            source_status=official_results_intake_status,
            blocker_count=_int(official_results.get("blocker_count")),
            required_input="official CAMEO result CSV rows with CAMEO URL, record id, retrieval timestamp, assessment date, model1 rank, and official metrics",
            source_artifact=official_results_intake_path,
            recommended_action="Fill runs/cameo_official_results_operator_intake.csv from official CAMEO assessment output, then rerun build_cameo_official_results_intake_gate.py.",
            reason=(
                f"result_row_count={_int(official_results.get('result_row_count'))}, "
                f"accepted_official_result_count={_int(official_results.get('accepted_official_result_count'))}, "
                f"model1_official_result_ready={_bool(official_results.get('model1_official_result_ready'))}."
            ),
            official_result_required=not official_results_intake_ready,
        ),
        _row(
            priority=4,
            stage="evidence_integrity_contract",
            status="ready" if evidence_integrity_ready else "blocked",
            source_status=_text(evidence_integrity.get("status")) or "missing",
            blocker_count=_int(evidence_integrity.get("blocker_count")),
            required_input="honest official-result provenance, visible operator schema, no local native substitution, clear external mutation flags, and gated registration/email",
            source_artifact=evidence_integrity_path,
            recommended_action="Repair evidence-integrity blockers before claiming CAMEO-based architecture validation.",
            reason=(
                f"official_results_pending_honest={_bool(evidence_integrity.get('official_results_pending_honest'))}, "
                f"official_result_schema_visible={_bool(evidence_integrity.get('official_result_schema_visible'))}, "
                f"no_local_native_accuracy_substitution={_bool(evidence_integrity.get('no_local_native_accuracy_substitution'))}, "
                f"external_mutation_flags_clear={_bool(evidence_integrity.get('external_mutation_flags_clear'))}, "
                f"registration_and_email_gated={_bool(evidence_integrity.get('registration_and_email_gated'))}."
            ),
            official_result_required=official_result_required,
        ),
        _row(
            priority=5,
            stage="validation_evidence",
            status=validation_row_status,
            source_status=readiness_status,
            blocker_count=_int(readiness.get("blocker_count")),
            required_input="selection, format, handoff, and official CAMEO performance artifacts",
            source_artifact=readiness_path,
            recommended_action="Generate or repair the missing validation chain artifacts; use official CAMEO result metrics for performance evidence.",
            reason=(
                f"ready_stage_count={_int(readiness.get('ready_stage_count'))}/{_int(readiness.get('stage_count'))}, "
                f"missing_stage_count={_int(readiness.get('missing_stage_count'))}, "
                f"official_cameo_results_used={_bool(readiness.get('official_cameo_results_used'))}."
            ),
            official_result_required=official_result_required,
        ),
        _row(
            priority=6,
            stage="runtime_receiver_smoke",
            status=runtime_row_status,
            source_status=f"{api_status or 'missing'};{smoke_status or 'missing'};{runtime_status or 'missing'}",
            blocker_count=runtime_blockers,
            required_input="requirements-api.txt runtime dependency profile and local POST /cameo/targets smoke evidence",
            approval_token_required=API_APPROVAL_TOKEN if runtime_install_approval_required else "",
            source_artifact=f"{api_dependency_path};{receiver_smoke_path};{runtime_repair_path}",
            recommended_action=runtime_recommended_action,
            reason=(
                f"api_dependency_status={api_status or 'missing'}, receiver_smoke_status={smoke_status or 'missing'}, "
                f"runtime_repair_status={runtime_status or 'missing'}."
            ),
        ),
        _row(
            priority=7,
            stage="public_registration_and_email",
            status=registration_row_status,
            source_status=capability_status,
            blocker_count=_int(capability.get("public_registration_blocker_count")),
            required_input="validation evidence, receiver smoke, registration approval, and outbound-email approval",
            approval_token_required=registration_tokens,
            source_artifact=capability_preflight_path,
            recommended_action="Request registration/email approval only after validation evidence and receiver smoke are ready.",
            reason=(
                f"public_registration_allowed={public_registration_allowed}, "
                f"receiver_smoke_post_200_ok={_bool(capability.get('receiver_smoke_post_200_ok'))}, "
                f"public_registration_requested={_bool(capability.get('public_registration_requested'))}."
            ),
            official_result_required=official_result_required,
        ),
    ]

    blocked_stage_count = sum(1 for row in rows if row["status"] == "blocked")
    approval_required_stage_count = sum(1 for row in rows if row["status"] == "approval_required")
    approval_tokens = sorted({token for row in rows for token in _approval_tokens(row["approval_token_required"])})
    operator_input_required_count = max(input_blockers, required_template_count) if input_row_status == "blocked" else 0
    native_local_accuracy_used = any(
        _bool(_summary(packet).get("native_local_accuracy_used"))
        for packet in [
            input_validation_packet,
            readiness_packet,
            official_results_intake_packet or {},
            evidence_integrity_packet or {},
            capability_preflight_packet,
        ]
    )
    external_state_mutated = any(
        _bool(_summary(packet).get("external_state_mutated"))
        for packet in [
            input_kit_packet,
            input_validation_packet,
            repair_preflight_packet,
            readiness_packet,
            official_results_intake_packet or {},
            evidence_integrity_packet or {},
            runtime_repair_packet,
            api_dependency_packet,
            receiver_smoke_packet,
            capability_preflight_packet,
        ]
    )
    outbound_email_enabled = any(
        _bool(_summary(packet).get("outbound_email_enabled"))
        for packet in [
            input_kit_packet,
            input_validation_packet,
            repair_preflight_packet,
            readiness_packet,
            official_results_intake_packet or {},
            evidence_integrity_packet or {},
            runtime_repair_packet,
            api_dependency_packet,
            receiver_smoke_packet,
            capability_preflight_packet,
        ]
    )

    status = (
        "cameo_validation_operations_dossier_ready"
        if blocked_stage_count == 0 and approval_required_stage_count == 0 and public_registration_allowed and not official_result_required
        else "blocked_cameo_validation_operations_dossier"
    )
    summary = {
        "packet_type": "cameo_validation_operations_dossier",
        "status": status,
        "stage_count": len(rows),
        "blocked_stage_count": blocked_stage_count,
        "approval_required_stage_count": approval_required_stage_count,
        "approval_token_count": len(approval_tokens),
        "approval_tokens_required": approval_tokens,
        "operator_input_required_count": operator_input_required_count,
        "operator_input_blocker_count": input_blockers,
        "validation_readiness_status": readiness_status,
        "validation_ready": readiness_status == "cameo_validation_evidence_ready",
        "official_results_intake_status": official_results_intake_status,
        "official_results_intake_ready": official_results_intake_ready,
        "official_results_intake_blocker_count": _int(official_results.get("blocker_count")),
        "official_model1_result_ready": _bool(official_results.get("model1_official_result_ready")),
        "official_result_required": official_result_required,
        "official_cameo_results_used": _bool(readiness.get("official_cameo_results_used")),
        "evidence_integrity_ready": evidence_integrity_ready,
        "evidence_integrity_status": _text(evidence_integrity.get("status")),
        "evidence_integrity_blocker_count": _int(evidence_integrity.get("blocker_count")),
        "official_results_pending_honest": _bool(evidence_integrity.get("official_results_pending_honest")),
        "no_local_native_accuracy_substitution": _bool(evidence_integrity.get("no_local_native_accuracy_substitution")),
        "external_mutation_flags_clear": _bool(evidence_integrity.get("external_mutation_flags_clear")),
        "api_dependency_status": api_status,
        "receiver_smoke_status": smoke_status,
        "runtime_install_approval_required": runtime_install_approval_required,
        "public_registration_allowed": public_registration_allowed,
        "registration_approval_token_required": REGISTRATION_APPROVAL_TOKEN,
        "outbound_email_approval_token_required": OUTBOUND_EMAIL_APPROVAL_TOKEN,
        "package_install_executed": False,
        "server_started": False,
        "server_registration_mutated": False,
        "prediction_generation_enabled": False,
        "outbound_email_enabled": outbound_email_enabled,
        "native_local_accuracy_used": native_local_accuracy_used,
        "external_state_mutated": external_state_mutated,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            (
                "Fill official CAMEO result intake rows from official assessment output; registration/email remain gated."
                if runtime_row_status == "ready"
                else "Fill official CAMEO result intake rows from official assessment output; runtime receiver smoke and registration/email remain gated."
            )
            if official_result_required and input_row_status == "ready"
            else (
                "Clear operator inputs first, then repair CAMEO validation artifacts and runtime receiver smoke before any registration/email approval."
                if blocked_stage_count
                else (
                    "Review approval-gated runtime and registration/email rows."
                    if approval_required_stage_count
                    else "CAMEO validation operations dossier is clear."
                )
            )
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# CAMEO Validation Operations Dossier",
        "",
        f"- status: `{s['status']}`",
        f"- blocked_stage_count: `{s['blocked_stage_count']}`",
        f"- approval_required_stage_count: `{s['approval_required_stage_count']}`",
        f"- approval_tokens_required: `{';'.join(s['approval_tokens_required'])}`",
        f"- operator_input_required_count: `{s['operator_input_required_count']}`",
        f"- official_result_required: `{s['official_result_required']}`",
        f"- official_results_intake_status: `{s['official_results_intake_status']}`",
        f"- official_results_intake_ready: `{s['official_results_intake_ready']}`",
        f"- official_results_intake_blocker_count: `{s['official_results_intake_blocker_count']}`",
        f"- official_model1_result_ready: `{s['official_model1_result_ready']}`",
        f"- evidence_integrity_ready: `{s['evidence_integrity_ready']}`",
        f"- evidence_integrity_status: `{s['evidence_integrity_status']}`",
        f"- evidence_integrity_blocker_count: `{s['evidence_integrity_blocker_count']}`",
        f"- official_results_pending_honest: `{s['official_results_pending_honest']}`",
        f"- no_local_native_accuracy_substitution: `{s['no_local_native_accuracy_substitution']}`",
        f"- external_mutation_flags_clear: `{s['external_mutation_flags_clear']}`",
        f"- public_registration_allowed: `{s['public_registration_allowed']}`",
        f"- package_install_executed: `{s['package_install_executed']}`",
        f"- server_started: `{s['server_started']}`",
        f"- server_registration_mutated: `{s['server_registration_mutated']}`",
        f"- outbound_email_enabled: `{s['outbound_email_enabled']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Stages",
        "",
        "| priority | stage | status | source_status | blockers | token | official_result_required | source | reason |",
        "| ---: | --- | --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['priority']}` | `{row['stage']}` | `{row['status']}` | `{row['source_status']}` | "
            f"`{row['blocker_count']}` | `{row['approval_token_required']}` | `{row['official_result_required']}` | "
            f"`{row['source_artifact']}` | {row['reason']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a fail-closed CAMEO validation operations dossier from local artifacts.")
    parser.add_argument("--input-kit-json", default=DEFAULT_INPUT_KIT_JSON)
    parser.add_argument("--input-validation-json", default=DEFAULT_INPUT_VALIDATION_JSON)
    parser.add_argument("--repair-preflight-json", default=DEFAULT_REPAIR_PREFLIGHT_JSON)
    parser.add_argument("--readiness-json", default=DEFAULT_READINESS_JSON)
    parser.add_argument("--official-results-intake-json", default=DEFAULT_OFFICIAL_RESULTS_INTAKE_JSON)
    parser.add_argument("--evidence-integrity-json", default=DEFAULT_EVIDENCE_INTEGRITY_JSON)
    parser.add_argument("--runtime-repair-json", default=DEFAULT_RUNTIME_REPAIR_JSON)
    parser.add_argument("--api-dependency-json", default=DEFAULT_API_DEPENDENCY_JSON)
    parser.add_argument("--receiver-smoke-json", default=DEFAULT_RECEIVER_SMOKE_JSON)
    parser.add_argument("--capability-preflight-json", default=DEFAULT_CAPABILITY_PREFLIGHT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_cameo_validation_operations_dossier(
        input_kit_packet=_read_json_if_present(args.input_kit_json),
        input_validation_packet=_read_json_if_present(args.input_validation_json),
        repair_preflight_packet=_read_json_if_present(args.repair_preflight_json),
        readiness_packet=_read_json_if_present(args.readiness_json),
        official_results_intake_packet=_read_json_if_present(args.official_results_intake_json),
        evidence_integrity_packet=_read_json_if_present(args.evidence_integrity_json),
        runtime_repair_packet=_read_json_if_present(args.runtime_repair_json),
        api_dependency_packet=_read_json_if_present(args.api_dependency_json),
        receiver_smoke_packet=_read_json_if_present(args.receiver_smoke_json),
        capability_preflight_packet=_read_json_if_present(args.capability_preflight_json),
        input_kit_path=args.input_kit_json,
        input_validation_path=args.input_validation_json,
        repair_preflight_path=args.repair_preflight_json,
        readiness_path=args.readiness_json,
        official_results_intake_path=args.official_results_intake_json,
        evidence_integrity_path=args.evidence_integrity_json,
        runtime_repair_path=args.runtime_repair_json,
        api_dependency_path=args.api_dependency_json,
        receiver_smoke_path=args.receiver_smoke_json,
        capability_preflight_path=args.capability_preflight_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
