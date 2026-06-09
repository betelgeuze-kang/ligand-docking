from __future__ import annotations

import shlex
import json
from pathlib import Path
from typing import Any

CLAIM_BOUNDARY = (
    "Product bundle contract only; it validates the local-delivery bundle command recorded in the product work order "
    "and reconciles any existing local bundle validation evidence. It does not run docking, assemble bundles, run bundle "
    "validation, emit scientific results, or mutate external state."
)
BUNDLE_ENTRYPOINT = "tools/build_local_delivery_bundle.py"
VALIDATION_ENTRYPOINT = "tools/validate_local_delivery_bundle.py"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    return bool(value is True)


def _blocker(code: str, reason: str) -> dict[str, str]:
    return {"code": code, "severity": "hard", "reason": reason}


def _warning(code: str, reason: str) -> dict[str, str]:
    return {"code": code, "severity": "warning", "reason": reason}


def _as_command_parts(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_text(part) for part in value if _text(part)]
    text = _text(value)
    return shlex.split(text) if text else []


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _resolve(root: Path, path_like: str) -> Path:
    path = Path(path_like).expanduser()
    return path if path.is_absolute() else root / path


def _read_json_if_present(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _script_index(parts: list[str], entrypoint: str) -> int:
    for index, part in enumerate(parts):
        normalized = part.replace("\\", "/")
        if normalized == entrypoint or normalized.endswith(f"/{entrypoint}"):
            return index
    return -1


def _bundle_parser() -> Any:
    from tools.build_local_delivery_bundle import build_parser

    parser = build_parser()
    parser.exit = lambda status=0, message=None: (_ for _ in ()).throw(
        ValueError(_text(message) or f"argparse exit {status}")
    )
    parser.error = lambda message: (_ for _ in ()).throw(ValueError(_text(message)))
    return parser


def _claims_delivery_ready(verdict: str) -> bool:
    lowered = " ".join(verdict.lower().split())
    if any(hint in lowered for hint in ("not delivery-ready", "not delivery ready", "internal-review", "internal review", "review-only", "review only", "blocked")):
        return False
    return any(hint in lowered for hint in ("delivery-ready", "delivery ready", "ready for delivery", "ready for guarded"))


def _parse_bundle_command(command: Any) -> tuple[dict[str, Any], list[dict[str, str]]]:
    blockers: list[dict[str, str]] = []
    parts = _as_command_parts(command)
    check: dict[str, Any] = {
        "command": command if isinstance(command, str) else " ".join(parts),
        "parts": parts,
        "entrypoint": "",
        "parser_status": "not_checked",
        "unknown_args": [],
        "parsed_args": {},
    }
    if not parts:
        blockers.append(_blocker("bundle_command_missing", "Bundle command is required."))
        return check, blockers
    script_index = _script_index(parts, BUNDLE_ENTRYPOINT)
    if script_index < 0:
        blockers.append(_blocker("bundle_entrypoint_unrecognized", f"Bundle command must call {BUNDLE_ENTRYPOINT}."))
        return check, blockers
    check["entrypoint"] = parts[script_index]
    argv = parts[script_index + 1 :]
    try:
        parsed, unknown = _bundle_parser().parse_known_args(argv)
    except ValueError as exc:
        check["parser_status"] = "invalid"
        blockers.append(_blocker("bundle_command_parse_error", f"Bundle parser rejected command: {exc}"))
        return check, blockers
    parsed_args = vars(parsed)
    check["parser_status"] = "parsed"
    check["unknown_args"] = unknown
    check["parsed_args"] = {
        "bundle_tag": _text(parsed_args.get("bundle_tag")),
        "out_dir": _text(parsed_args.get("out_dir")),
        "request_summary": _text(parsed_args.get("request_summary")),
        "delivery_scope": _text(parsed_args.get("delivery_scope")),
        "claim_scope": _text(parsed_args.get("claim_scope")),
        "verdict": _text(parsed_args.get("verdict")),
        "rerun_command": _text(parsed_args.get("rerun_command")),
        "config_paths": [_text(path) for path in parsed_args.get("config_paths", []) or [] if _text(path)],
        "artifact_paths": [_text(path) for path in parsed_args.get("artifact_paths", []) or [] if _text(path)],
    }
    if unknown:
        blockers.append(_blocker("bundle_command_unknown_args", "Bundle command contains unsupported args: " + " ".join(unknown)))
    return check, blockers


def _validation_command_status(command: Any, expected_bundle_dir: str) -> dict[str, Any]:
    parts = _as_command_parts(command)
    status = {
        "command": command if isinstance(command, str) else " ".join(parts),
        "entrypoint_seen": False,
        "bundle_dir_arg": "",
        "expected_bundle_dir": expected_bundle_dir,
        "matches_expected_bundle_dir": False,
    }
    if _script_index(parts, VALIDATION_ENTRYPOINT) >= 0:
        status["entrypoint_seen"] = True
    for index, part in enumerate(parts):
        if part == "--bundle-dir" and index + 1 < len(parts):
            status["bundle_dir_arg"] = parts[index + 1]
            status["matches_expected_bundle_dir"] = parts[index + 1].rstrip("/") == expected_bundle_dir.rstrip("/")
            break
    return status


def build_product_bundle_contract(
    work_order_packet: dict[str, Any],
    preflight_packet: dict[str, Any],
    *,
    root: str | Path = ".",
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    work_summary = _summary(work_order_packet)
    preflight_summary = _summary(preflight_packet)
    commands = work_order_packet.get("commands") if isinstance(work_order_packet.get("commands"), dict) else {}
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    if work_summary.get("status") != "product_execution_work_order_ready":
        blockers.append(_blocker("work_order_not_ready", "Product execution work order must be ready."))
    if preflight_summary.get("status") != "product_execution_preflight_ready":
        blockers.append(_blocker("execution_preflight_not_ready", "Product execution preflight must be ready."))
    for label, summary in (("work_order", work_summary), ("preflight", preflight_summary)):
        if summary.get("execution_enabled") is not False:
            blockers.append(_blocker(f"{label}_execution_flag_invalid", f"{label} must keep execution_enabled=false."))
        if summary.get("docking_results_emitted") is not False:
            blockers.append(_blocker(f"{label}_results_flag_invalid", f"{label} must keep docking_results_emitted=false."))
        post_execution_bundle_validated = (
            label == "preflight" and summary.get("post_execution_bundle_validated") is True
        )
        if summary.get("bundle_assembled") is not False and not post_execution_bundle_validated:
            blockers.append(_blocker(f"{label}_bundle_flag_invalid", f"{label} must keep bundle_assembled=false."))
        if summary.get("external_state_mutated") is not False:
            blockers.append(_blocker(f"{label}_external_state_flag_invalid", f"{label} must keep external_state_mutated=false."))

    bundle_check, command_blockers = _parse_bundle_command(commands.get("bundle_command"))
    blockers.extend(command_blockers)
    parsed = bundle_check.get("parsed_args") if isinstance(bundle_check.get("parsed_args"), dict) else {}
    bundle_tag = _text(parsed.get("bundle_tag"))
    out_dir = _text(parsed.get("out_dir"))
    expected_bundle_dir = str((Path(out_dir) / f"bundle_{bundle_tag}").as_posix()) if out_dir and bundle_tag else ""
    validation_status = _validation_command_status(commands.get("bundle_validation_command"), expected_bundle_dir)
    bundle_assembled = False
    bundle_validation_present = False
    bundle_validation_passed = False
    bundle_validation_path = ""

    if bundle_tag and bundle_tag != _text(work_summary.get("bundle_tag")):
        blockers.append(_blocker("bundle_tag_mismatch", "Bundle command tag must match work order summary.bundle_tag."))
    if parsed and not _text(parsed.get("request_summary")):
        blockers.append(_blocker("bundle_request_summary_missing", "Bundle command must include --request-summary."))
    if parsed and not _text(parsed.get("rerun_command")):
        blockers.append(_blocker("bundle_rerun_command_missing", "Bundle command must include --rerun-command."))
    if parsed and _claims_delivery_ready(_text(parsed.get("verdict"))):
        blockers.append(_blocker("bundle_verdict_claims_delivery_ready_before_execution", "Pre-execution bundle contract must use an internal-review verdict, not a delivery-ready claim."))
    if expected_bundle_dir:
        expected_path = _resolve(root_path, expected_bundle_dir)
        if expected_path.exists():
            bundle_assembled = expected_path.is_dir()
            validation_path = expected_path / "validation.json"
            bundle_validation_path = str(validation_path)
            validation_payload = _read_json_if_present(validation_path)
            bundle_validation_present = bool(validation_payload)
            bundle_validation_passed = bool(
                validation_payload.get("overall_ok") is True and _int(validation_payload.get("blocker_count")) == 0
            )
            if not bundle_validation_passed:
                blockers.append(
                    _blocker(
                        "bundle_dir_already_present",
                        f"Expected bundle directory already exists without passing validation evidence: {expected_bundle_dir}",
                    )
                )
    if not validation_status["entrypoint_seen"]:
        blockers.append(_blocker("bundle_validation_entrypoint_missing", f"Validation command must call {VALIDATION_ENTRYPOINT}."))
    if expected_bundle_dir and not validation_status["matches_expected_bundle_dir"]:
        blockers.append(_blocker("bundle_validation_dir_mismatch", "Validation command must point at the expected bundle output directory."))

    config_rows: list[dict[str, Any]] = []
    for path_text in parsed.get("config_paths", []) or []:
        path = _resolve(root_path, _text(path_text))
        config_rows.append({"path": _text(path_text), "resolved_path": str(path), "present": path.exists()})
        if not path.exists():
            blockers.append(_blocker("bundle_config_path_missing", f"Bundle config path is missing: {path_text}"))
    artifact_rows: list[dict[str, Any]] = []
    for path_text in parsed.get("artifact_paths", []) or []:
        path = _resolve(root_path, _text(path_text))
        present = path.exists()
        artifact_rows.append({"path": _text(path_text), "resolved_path": str(path), "present_before_execution": present})
        if present:
            warnings.append(_warning("planned_artifact_present_before_execution", f"Planned artifact is already present before approved execution: {path_text}"))

    status = "product_bundle_contract_ready" if not blockers else "blocked_product_bundle_contract"
    summary = {
        "packet_type": "product_bundle_contract",
        "status": status,
        "target_id": _text(work_summary.get("target_id")),
        "family": _text(work_summary.get("family")),
        "ligand_count": _int(work_summary.get("ligand_count")),
        "bundle_tag": bundle_tag,
        "expected_bundle_dir": expected_bundle_dir,
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "bundle_parser_status": _text(bundle_check.get("parser_status")),
        "bundle_unknown_arg_count": len(bundle_check.get("unknown_args") or []),
        "config_count": len(config_rows),
        "artifact_count": len(artifact_rows),
        "bundle_validation_command_matches": _bool(validation_status.get("matches_expected_bundle_dir")),
        "bundle_validation_present": bundle_validation_present,
        "bundle_validation_passed": bundle_validation_passed,
        "bundle_validation_json": bundle_validation_path,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "bundle_assembled": bundle_assembled,
        "external_state_mutated": False,
        "validated_without_execution": True,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Bundle assembly and validation evidence are present; refresh product delivery evidence and pilot packet."
            if status == "product_bundle_contract_ready" and bundle_validation_passed
            else "After approved execution creates planned artifacts, run the recorded bundle command and then bundle validation."
            if status == "product_bundle_contract_ready"
            else "Repair bundle command, validation command, or stale bundle artifacts before approved execution handoff."
        ),
    }
    rows = [
        {"check": "bundle_command", "status": "pass" if not command_blockers else "fail", "detail": _text(bundle_check.get("parser_status"))},
        {"check": "bundle_validation_command", "status": "pass" if validation_status["matches_expected_bundle_dir"] else "fail", "detail": validation_status["bundle_dir_arg"]},
        {"check": "bundle_config_paths", "status": "pass" if all(row["present"] for row in config_rows) else "fail", "detail": ",".join(row["path"] for row in config_rows)},
        {"check": "planned_artifacts", "status": "pass", "detail": ",".join(row["path"] for row in artifact_rows)},
        {"check": "bundle_validation_evidence", "status": "pass" if bundle_validation_passed else "not_present", "detail": bundle_validation_path},
    ]
    return {
        "summary": summary,
        "blockers": blockers,
        "warnings": warnings,
        "bundle_command_check": bundle_check,
        "bundle_validation_command_check": validation_status,
        "config_checks": config_rows,
        "planned_artifact_checks": artifact_rows,
        "rows": rows,
    }
