from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

ARTIFACTS = {
    "operator-inputs": "runs/cameo_operator_input_validation_current.json",
    "repair-preflight": "runs/cameo_repair_execution_preflight_current.json",
    "readiness": "runs/cameo_validation_readiness_gate_current.json",
    "official-results": "runs/cameo_official_results_intake_gate_current.json",
    "performance": "runs/cameo_performance_scorecard_current.json",
    "runtime": "runs/cameo_api_dependency_readiness_current.json",
    "receiver-smoke": "runs/cameo_receiver_smoke_contract_current.json",
    "capability": "runs/cameo_capability_preflight_current.json",
    "operations": "runs/cameo_validation_operations_dossier_current.json",
    "architecture": "runs/cameo_architecture_validation_contract_current.json",
    "api-contract": "runs/cameo_api_contract_current.json",
    "service-boundary": "runs/cameo_service_boundary_contract_current.json",
    "evidence-integrity": "runs/cameo_evidence_integrity_contract_current.json",
    "registration-approval": "runs/cameo_public_registration_approval_gate_current.json",
}

CLAIM_BOUNDARY = (
    "Betelgeuze CAMEO CLI only; it reads local CAMEO validation and operations artifacts and prints status JSON. "
    "It does not install packages, start a server, register a CAMEO server, submit predictions, send email, "
    "fetch official CAMEO pages, use local native accuracy, or mutate external state."
)


def _resolve(root: str | Path, path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else Path(root).resolve() / path


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


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in packet.get("rows", []) or [] if isinstance(row, dict)]


def _blockers(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in packet.get("blockers", []) or [] if isinstance(row, dict)]


def _approval_required(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in packet.get("approval_required", []) or [] if isinstance(row, dict)]


def _int_value(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _bool_value(value: Any) -> bool:
    return bool(value is True)


def _approval_tokens_from_value(value: Any) -> list[str]:
    if isinstance(value, list):
        tokens: list[str] = []
        for token in value:
            tokens.extend(_approval_tokens_from_value(token))
        return tokens
    return [token.strip() for token in str(value or "").replace(",", ";").split(";") if token.strip()]


def _approval_tokens_from_status(payload: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    for key in (
        "approval_tokens_required",
        "approval_token_required",
        "registration_approval_token_required",
        "outbound_email_approval_token_required",
    ):
        tokens.update(_approval_tokens_from_value(payload.get(key)))
        tokens.update(_approval_tokens_from_value(summary.get(key)))
    for row_group in ("rows", "approval_required"):
        for row in payload.get(row_group, []) or []:
            if isinstance(row, dict):
                for key in (
                    "approval_token_required",
                    "registration_approval_token_required",
                    "outbound_email_approval_token_required",
                ):
                    tokens.update(_approval_tokens_from_value(row.get(key)))
    return tokens


def _blocker_count(summary: dict[str, Any], packet: dict[str, Any]) -> int:
    for key in ("blocker_count", "blocked_stage_count", "blocked_lane_count", "missing_or_unimportable_count"):
        value = _int_value(summary.get(key))
        if value:
            return value
    return len(_blockers(packet))


def _approval_required_count(summary: dict[str, Any], packet: dict[str, Any]) -> int:
    for key in ("approval_required_count", "approval_required_stage_count", "approval_required_lane_count"):
        value = _int_value(summary.get(key))
        if value:
            return value
    return len(_approval_required(packet))


def build_cli_status(command: str, *, root: str | Path = ROOT) -> dict[str, Any]:
    artifact_rel = ARTIFACTS[command]
    artifact = _resolve(root, artifact_rel)
    packet = _read_json_object(artifact)
    summary = _summary(packet)
    approval_tokens = sorted(_approval_tokens_from_status(packet))
    if not summary:
        return {
            "packet_type": "cameo_cli_status",
            "command": command,
            "status": f"missing_cameo_{command.replace('-', '_')}_artifact",
            "artifact_path": artifact_rel,
            "artifact_present": artifact.exists(),
            "row_count": 0,
            "blocker_count": 1,
            "approval_required_count": 0,
            "approval_token_count": 0,
            "approval_tokens_required": [],
            "summary": {},
            "package_install_executed": False,
            "server_started": False,
            "server_registration_mutated": False,
            "prediction_generation_enabled": False,
            "outbound_email_enabled": False,
            "official_results_fetched": False,
            "native_local_accuracy_used": False,
            "external_state_mutated": False,
            "claim_boundary": CLAIM_BOUNDARY,
        }
    return {
        "packet_type": "cameo_cli_status",
        "command": command,
        "status": str(summary.get("status") or "unknown"),
        "artifact_path": artifact_rel,
        "artifact_present": True,
        "row_count": len(_rows(packet)),
        "blocker_count": _blocker_count(summary, packet),
        "approval_required_count": _approval_required_count(summary, packet),
        "approval_token_count": len(approval_tokens),
        "approval_tokens_required": approval_tokens,
        "summary": summary,
        "package_install_executed": False,
        "server_started": False,
        "server_registration_mutated": False,
        "prediction_generation_enabled": False,
        "outbound_email_enabled": False,
        "official_results_fetched": False,
        "native_local_accuracy_used": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_all_status(*, root: str | Path = ROOT) -> dict[str, Any]:
    statuses = {command: build_cli_status(command, root=root) for command in ARTIFACTS}
    blocked_or_missing = [
        command
        for command, payload in statuses.items()
        if str(payload.get("status", "")).startswith(("blocked_", "missing_"))
    ]
    summaries = {command: _summary(payload) for command, payload in statuses.items()}
    approval_tokens = sorted({token for payload in statuses.values() for token in _approval_tokens_from_status(payload)})
    official = summaries.get("official-results", {})
    readiness = summaries.get("readiness", {})
    performance = summaries.get("performance", {})
    operations = summaries.get("operations", {})
    architecture = summaries.get("architecture", {})
    evidence_integrity = summaries.get("evidence-integrity", {})
    registration = summaries.get("registration-approval", {})
    capability = summaries.get("capability", {})
    runtime = summaries.get("runtime", {})
    receiver_smoke = summaries.get("receiver-smoke", {})
    official_result_required = (
        _bool_value(operations.get("official_result_required"))
        or str(readiness.get("status") or "") == "cameo_validation_pending_official_results"
        or str(performance.get("status") or "") == "cameo_performance_pending_official_results"
        or not _bool_value(official.get("model1_official_result_ready"))
    )
    api_install_approval_required = (
        str(runtime.get("status") or "") == "blocked_cameo_api_dependency_readiness"
        or _bool_value(operations.get("runtime_install_approval_required"))
    )
    return {
        "packet_type": "cameo_cli_status_set",
        "status": "blocked_cameo_cli_status_set" if blocked_or_missing else "cameo_cli_status_set_ready",
        "command_count": len(statuses),
        "blocked_or_missing_command_count": len(blocked_or_missing),
        "blocked_or_missing_commands": blocked_or_missing,
        "approval_token_count": len(approval_tokens),
        "approval_tokens_required": approval_tokens,
        "approval_required_command_count": sum(1 for payload in statuses.values() if int(payload.get("approval_required_count") or 0) > 0),
        "official_result_required": official_result_required,
        "official_results_intake_ready": _bool_value(official.get("model1_official_result_ready"))
        and str(official.get("status") or "") == "cameo_official_results_intake_ready",
        "official_results_result_row_count": _int_value(official.get("result_row_count")),
        "official_results_accepted_count": _int_value(official.get("accepted_official_result_count")),
        "official_model1_result_ready": _bool_value(official.get("model1_official_result_ready")),
        "official_cameo_results_used": any(
            _bool_value(summary.get("official_cameo_results_used"))
            for summary in (official, readiness, performance, operations, architecture)
        ),
        "validation_ready": _bool_value(operations.get("validation_ready")) or str(readiness.get("status") or "") == "cameo_validation_evidence_ready",
        "performance_scorecard_evidence_ready": str(performance.get("status") or "") == "cameo_performance_evidence_ready",
        "performance_threshold_policy_ready": _bool_value(performance.get("threshold_policy_ready"))
        or _bool_value(architecture.get("performance_threshold_policy_ready")),
        "evidence_integrity_ready": _bool_value(evidence_integrity.get("evidence_integrity_ready")),
        "official_results_pending_honest": _bool_value(evidence_integrity.get("official_results_pending_honest")),
        "no_local_native_accuracy_substitution": _bool_value(
            evidence_integrity.get("no_local_native_accuracy_substitution")
        ),
        "api_install_approval_required": api_install_approval_required,
        "api_dependency_status": str(runtime.get("status") or ""),
        "receiver_smoke_status": str(receiver_smoke.get("status") or ""),
        "public_registration_allowed": _bool_value(operations.get("public_registration_allowed"))
        or _bool_value(capability.get("public_registration_allowed")),
        "public_registration_authorized": _bool_value(registration.get("authorized_for_registration_review"))
        or _bool_value(architecture.get("public_registration_authorized")),
        "registration_awaiting_operator_approval_row_count": _int_value(registration.get("awaiting_operator_approval_row_count")),
        "registration_blocked_row_count": _int_value(registration.get("blocked_row_count")),
        "statuses": statuses,
        "package_install_executed": False,
        "server_started": False,
        "server_registration_mutated": False,
        "prediction_generation_enabled": False,
        "outbound_email_enabled": False,
        "official_results_fetched": False,
        "native_local_accuracy_used": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read local Betelgeuze CAMEO status artifacts as JSON.")
    parser.add_argument(
        "command",
        choices=[*ARTIFACTS.keys(), "all"],
        help="CAMEO status surface to read.",
    )
    parser.add_argument("--root", default=str(ROOT), help="Repository root containing the runs/ artifacts.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_all_status(root=args.root) if args.command == "all" else build_cli_status(args.command, root=args.root)
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
