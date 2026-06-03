from __future__ import annotations

import argparse
import csv
import json
import shlex
from pathlib import Path
from typing import Any

from betelgeuze_product.work_order import EXECUTION_APPROVAL_TOKEN

CLAIM_BOUNDARY = (
    "Product execution preflight only; it validates an operator work order and command contract without "
    "running docking, assembling delivery bundles, emitting results, or mutating external state."
)
KNOWN_ENTRYPOINTS = {"tools/run_ligand_htvs_pipeline.py"}
KNOWN_APPROVAL_GATE_ENTRYPOINTS = {"tools/build_product_execution_approval_gate.py"}
REQUIRED_CONFIG_INPUTS = ("ligand_csv", "target_native_csv")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _blocker(code: str, reason: str) -> dict[str, str]:
    return {"code": code, "severity": "hard", "reason": reason}


def _warning(code: str, reason: str) -> dict[str, str]:
    return {"code": code, "severity": "warning", "reason": reason}


def _as_command_parts(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_text(part) for part in value if _text(part)]
    text = _text(value)
    return shlex.split(text) if text else []


def _extract_repeated_flag(parts: list[str], flag: str) -> list[str]:
    out: list[str] = []
    index = 0
    while index < len(parts):
        if parts[index] == flag and index + 1 < len(parts):
            out.append(parts[index + 1])
            index += 2
            continue
        index += 1
    return out


def _parse_csv_list(value: Any) -> list[str]:
    return [part.strip() for part in _text(value).split(",") if part.strip()]


def _resolve(root: Path, path_like: str) -> Path:
    path = Path(path_like).expanduser()
    return path if path.is_absolute() else root / path


def _read_json_object(path: Path) -> tuple[dict[str, Any], str]:
    if not path.exists():
        return {}, "missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, "invalid"
    return (payload, "present") if isinstance(payload, dict) else ({}, "invalid")


def _read_csv_dicts(path: Path) -> tuple[list[dict[str, str]], str]:
    if not path.exists():
        return [], "missing"
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)], "present"
    except OSError:
        return [], "invalid"


def _pipeline_parser() -> argparse.ArgumentParser:
    from tools.run_ligand_htvs_pipeline import build_parser

    parser = build_parser()
    parser.exit = lambda status=0, message=None: (_ for _ in ()).throw(
        ValueError(_text(message) or f"argparse exit {status}")
    )
    parser.error = lambda message: (_ for _ in ()).throw(ValueError(_text(message)))
    return parser


def _validate_execution_command(command: str) -> tuple[dict[str, Any], list[dict[str, str]]]:
    blockers: list[dict[str, str]] = []
    parts = _as_command_parts(command)
    check: dict[str, Any] = {
        "command": command,
        "parts": parts,
        "entrypoint": "",
        "argv": [],
        "parser_status": "not_checked",
        "unknown_args": [],
        "dry_run_flag_seen": "--dry-run" in parts,
        "no_dry_run_flag_seen": "--no-dry-run" in parts,
    }
    if not parts:
        blockers.append(_blocker("execution_command_missing", "Execution command is required for preflight."))
        return check, blockers

    script_index = -1
    for index, part in enumerate(parts):
        normalized = part.replace("\\", "/")
        if normalized in KNOWN_ENTRYPOINTS or normalized.endswith("/tools/run_ligand_htvs_pipeline.py"):
            script_index = index
            break
    if script_index < 0:
        blockers.append(
            _blocker(
                "execution_entrypoint_unrecognized",
                "Execution command must call tools/run_ligand_htvs_pipeline.py for this product preflight.",
            )
        )
        return check, blockers

    entrypoint = parts[script_index]
    argv = parts[script_index + 1 :]
    check["entrypoint"] = entrypoint
    check["argv"] = argv
    try:
        parsed_args, unknown = _pipeline_parser().parse_known_args(argv)
    except ValueError as exc:
        check["parser_status"] = "invalid"
        blockers.append(_blocker("execution_command_parse_error", f"Pipeline parser rejected command: {exc}"))
        return check, blockers

    check["parser_status"] = "parsed"
    check["unknown_args"] = unknown
    check["parsed_options"] = {
        "enforce_operational_gate": bool(parsed_args.enforce_operational_gate),
        "eval_split_csv": _text(parsed_args.eval_split_csv),
        "gate_ef1_min": float(parsed_args.gate_ef1_min),
        "gate_min_eval_unique_keys": int(parsed_args.gate_min_eval_unique_keys),
        "ranking_binder_col": _text(parsed_args.ranking_binder_col),
        "ranking_eval_roles": _text(parsed_args.ranking_eval_roles),
        "ranking_labels_csv": _text(parsed_args.ranking_labels_csv),
        "targets": _text(parsed_args.targets),
    }
    if unknown:
        blockers.append(
            _blocker(
                "execution_command_unknown_args",
                "Execution command contains arguments not accepted by tools/run_ligand_htvs_pipeline.py: "
                + " ".join(unknown),
            )
        )
    return check, blockers


def _validate_operational_gate_feasibility(
    root: Path,
    parsed_options: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[dict[str, str]]]:
    if not parsed_options:
        return [], [], []
    if not bool(parsed_options.get("enforce_operational_gate")):
        return [
            {
                "check": "operational_gate_feasibility",
                "status": "skipped",
                "detail": "operational gate enforcement disabled",
            }
        ], [], []

    min_eval_unique = int(parsed_options.get("gate_min_eval_unique_keys") or 0)
    ef1_min = float(parsed_options.get("gate_ef1_min") or 0.0)
    if min_eval_unique <= 0 and ef1_min <= 0.0:
        return [
            {
                "check": "operational_gate_feasibility",
                "status": "skipped",
                "detail": "no eval-size or EF1 threshold configured",
            }
        ], [], []

    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    split_ref = _text(parsed_options.get("eval_split_csv"))
    labels_ref = _text(parsed_options.get("ranking_labels_csv"))
    binder_col = _text(parsed_options.get("ranking_binder_col")) or "is_binder"
    eval_roles = set(_parse_csv_list(parsed_options.get("ranking_eval_roles")) or ["eval"])
    row: dict[str, Any] = {
        "check": "operational_gate_feasibility",
        "status": "pass",
        "detail": "",
        "eval_split_csv": split_ref,
        "ranking_labels_csv": labels_ref,
        "ranking_eval_roles": ",".join(sorted(eval_roles)),
        "gate_min_eval_unique_keys": min_eval_unique,
        "gate_ef1_min": ef1_min,
        "eval_unique_keys": 0,
        "eval_positive_keys": 0,
        "ef1_max_possible": None,
    }
    if not split_ref:
        blockers.append(_blocker("operational_gate_split_csv_missing", "Operational gate feasibility requires --eval-split-csv."))
        row["status"] = "fail"
        row["detail"] = "missing eval split"
        return [row], blockers, warnings

    split_rows, split_status = _read_csv_dicts(_resolve(root, split_ref))
    if split_status != "present":
        blockers.append(_blocker("operational_gate_split_csv_unreadable", f"Eval split CSV is {split_status}: {split_ref}"))
        row["status"] = "fail"
        row["detail"] = f"split {split_status}"
        return [row], blockers, warnings

    eval_keys: set[tuple[str, str]] = set()
    for split_row in split_rows:
        role = _text(split_row.get("role"))
        if role not in eval_roles:
            continue
        target = _text(split_row.get("target"))
        ligand_id = _text(split_row.get("ligand_id"))
        if target and ligand_id:
            eval_keys.add((target, ligand_id))
    row["eval_unique_keys"] = len(eval_keys)

    label_rows, label_status = _read_csv_dicts(_resolve(root, labels_ref)) if labels_ref else ([], "missing")
    positive_keys: set[tuple[str, str]] = set()
    if label_status == "present":
        for label_row in label_rows:
            target = _text(label_row.get("target"))
            ligand_id = _text(label_row.get("ligand_id"))
            if not target or not ligand_id:
                continue
            try:
                is_positive = float(_text(label_row.get(binder_col)) or "0") > 0
            except ValueError:
                is_positive = False
            if is_positive:
                positive_keys.add((target, ligand_id))
    else:
        warnings.append(_warning("operational_gate_labels_csv_unreadable", f"Ranking labels CSV is {label_status}: {labels_ref}"))

    eval_positive = len(eval_keys & positive_keys)
    row["eval_positive_keys"] = eval_positive
    if eval_positive > 0:
        row["ef1_max_possible"] = float(len(eval_keys) / eval_positive)

    if min_eval_unique > 0 and len(eval_keys) < min_eval_unique:
        blockers.append(
            _blocker(
                "operational_gate_eval_unique_keys_impossible",
                f"Operational gate requires at least {min_eval_unique} eval unique keys, but the configured split has {len(eval_keys)}.",
            )
        )
    if ef1_min > 0.0 and eval_positive > 0:
        ef1_max = float(len(eval_keys) / eval_positive)
        if ef1_max + 1e-12 < ef1_min:
            blockers.append(
                _blocker(
                    "operational_gate_ef1_threshold_impossible",
                    f"Operational gate requires EF1 >= {ef1_min}, but eval prevalence caps max possible EF1 at {ef1_max:.6g}.",
                )
            )

    if blockers:
        row["status"] = "fail"
        row["detail"] = "configured operational gate cannot be satisfied by this eval split"
    else:
        row["detail"] = "configured operational gate is feasible for eval split cardinality"
    return [row], blockers, warnings


def _validate_approval_gate_command(command: str) -> tuple[dict[str, Any], list[dict[str, str]]]:
    blockers: list[dict[str, str]] = []
    parts = _as_command_parts(command)
    check: dict[str, Any] = {
        "command": command,
        "parts": parts,
        "entrypoint": "",
        "present": bool(parts),
    }
    if not parts:
        blockers.append(
            _blocker(
                "approval_gate_command_missing",
                "Work order must record tools/build_product_execution_approval_gate.py before execution.",
            )
        )
        return check, blockers

    script_index = -1
    for index, part in enumerate(parts):
        normalized = part.replace("\\", "/")
        if normalized in KNOWN_APPROVAL_GATE_ENTRYPOINTS or normalized.endswith("/tools/build_product_execution_approval_gate.py"):
            script_index = index
            break
    if script_index < 0:
        blockers.append(
            _blocker(
                "approval_gate_entrypoint_unrecognized",
                "Approval gate command must call tools/build_product_execution_approval_gate.py before execution.",
            )
        )
        return check, blockers

    check["entrypoint"] = parts[script_index]
    return check, blockers


def _validate_config_paths(root: Path, paths: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[dict[str, str]]]:
    rows: list[dict[str, Any]] = []
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    if not paths:
        blockers.append(_blocker("config_paths_missing", "At least one config/profile path is required."))
        return rows, blockers, warnings

    for path_text in paths:
        path = _resolve(root, path_text)
        payload, status = _read_json_object(path)
        row: dict[str, Any] = {
            "path": path_text,
            "resolved_path": str(path),
            "status": status,
            "required_input_missing": [],
            "required_input_present_count": 0,
            "version": _text(payload.get("version")) if payload else "",
            "targets": _text(payload.get("targets")) if payload else "",
        }
        if status == "missing":
            blockers.append(_blocker("config_path_missing", f"Config path is missing: {path_text}"))
            rows.append(row)
            continue
        if status == "invalid":
            blockers.append(_blocker("config_json_invalid", f"Config path is not a JSON object: {path_text}"))
            rows.append(row)
            continue
        missing_inputs: list[str] = []
        present_count = 0
        for key in REQUIRED_CONFIG_INPUTS:
            ref = _text(payload.get(key))
            if not ref:
                missing_inputs.append(f"{key}=<empty>")
                continue
            ref_path = _resolve(root, ref)
            if ref_path.exists():
                present_count += 1
            else:
                missing_inputs.append(f"{key}={ref}")
        row["required_input_missing"] = missing_inputs
        row["required_input_present_count"] = present_count
        if missing_inputs:
            blockers.append(
                _blocker(
                    "config_required_input_missing",
                    f"Config {path_text} references missing required input(s): {', '.join(missing_inputs)}",
                )
            )
        if payload.get("dry_run") is False:
            warnings.append(
                _warning(
                    "config_requests_non_dry_run",
                    f"Config {path_text} requests dry_run=false; this is acceptable only after execution approval.",
                )
            )
        rows.append(row)
    return rows, blockers, warnings


def build_product_execution_preflight(
    work_order_packet: dict[str, Any],
    *,
    root: str | Path = ".",
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    summary_in = work_order_packet.get("summary") if isinstance(work_order_packet.get("summary"), dict) else {}
    commands = work_order_packet.get("commands") if isinstance(work_order_packet.get("commands"), dict) else {}
    bundle_parts = _as_command_parts(commands.get("bundle_command"))
    config_paths = _extract_repeated_flag(bundle_parts, "--config-path")
    planned_artifact_paths = _extract_repeated_flag(bundle_parts, "--artifact-path")

    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    if summary_in.get("status") != "product_execution_work_order_ready":
        blockers.append(_blocker("work_order_not_ready", "Work order must be product_execution_work_order_ready."))
    if summary_in.get("execution_enabled") is not False:
        blockers.append(_blocker("work_order_execution_flag_invalid", "Work order must keep execution_enabled=false."))
    if summary_in.get("docking_results_emitted") is not False:
        blockers.append(_blocker("work_order_results_flag_invalid", "Work order must keep docking_results_emitted=false."))
    if summary_in.get("external_state_mutated") is not False:
        blockers.append(_blocker("work_order_external_state_flag_invalid", "Work order must keep external_state_mutated=false."))
    if summary_in.get("approval_token_required") != EXECUTION_APPROVAL_TOKEN:
        blockers.append(_blocker("approval_token_missing", f"Work order must require {EXECUTION_APPROVAL_TOKEN}."))

    approval_gate_check, approval_gate_blockers = _validate_approval_gate_command(_text(commands.get("approval_gate_command")))
    execution_check, command_blockers = _validate_execution_command(_text(commands.get("execution_command")))
    config_rows, config_blockers, config_warnings = _validate_config_paths(root_path, config_paths)
    gate_rows, gate_blockers, gate_warnings = _validate_operational_gate_feasibility(
        root_path,
        execution_check.get("parsed_options") if isinstance(execution_check.get("parsed_options"), dict) else {},
    )
    blockers.extend(approval_gate_blockers)
    blockers.extend(command_blockers)
    blockers.extend(config_blockers)
    blockers.extend(gate_blockers)
    warnings.extend(config_warnings)
    warnings.extend(gate_warnings)

    artifact_rows: list[dict[str, Any]] = []
    for path_text in planned_artifact_paths:
        path = _resolve(root_path, path_text)
        exists = path.exists()
        artifact_rows.append({"path": path_text, "resolved_path": str(path), "present_before_execution": exists})
        if exists:
            blockers.append(
                _blocker(
                    "planned_artifact_already_present",
                    f"Planned post-execution artifact already exists and could be stale: {path_text}",
                )
            )
    if not planned_artifact_paths:
        warnings.append(_warning("planned_artifact_paths_missing", "No planned post-execution artifact path was recorded."))

    status = "product_execution_preflight_ready" if not blockers else "blocked_product_execution_preflight"
    summary = {
        "packet_type": "product_execution_preflight",
        "status": status,
        "target_id": _text(summary_in.get("target_id")),
        "family": _text(summary_in.get("family")),
        "ligand_count": int(summary_in.get("ligand_count") or 0),
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "approval_gate_command_present": bool(approval_gate_check.get("present")),
        "approval_gate_entrypoint": _text(approval_gate_check.get("entrypoint")),
        "command_parser_status": execution_check.get("parser_status"),
        "unknown_arg_count": len(execution_check.get("unknown_args") or []),
        "config_count": len(config_rows),
        "operational_gate_feasibility_status": gate_rows[0]["status"] if gate_rows else "not_checked",
        "planned_artifact_count": len(artifact_rows),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "bundle_assembled": False,
        "external_state_mutated": False,
        "validated_without_execution": True,
        "approval_token_required": EXECUTION_APPROVAL_TOKEN,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            f"Review blockers/warnings, then provide `{EXECUTION_APPROVAL_TOKEN}` only if execution should run."
            if status == "product_execution_preflight_ready"
            else "Repair the blocked command/config contract and rerun this preflight before execution approval."
        ),
    }
    rows = [
        {
            "check": "approval_gate_command",
            "status": "pass" if not approval_gate_blockers else "fail",
            "detail": _text(approval_gate_check.get("entrypoint")) or "missing",
        },
        {
            "check": "execution_command",
            "status": "pass" if not command_blockers else "fail",
            "detail": " ".join(execution_check.get("unknown_args") or []) or _text(execution_check.get("parser_status")),
        },
        {
            "check": "config_paths",
            "status": "pass" if not config_blockers else "fail",
            "detail": ",".join(config_paths),
        },
        {
            "check": "operational_gate_feasibility",
            "status": gate_rows[0]["status"] if gate_rows else "not_checked",
            "detail": gate_rows[0]["detail"] if gate_rows else "",
        },
        {
            "check": "planned_artifacts",
            "status": "pass" if not any(row["present_before_execution"] for row in artifact_rows) else "fail",
            "detail": ",".join(planned_artifact_paths),
        },
    ]
    return {
        "summary": summary,
        "blockers": blockers,
        "warnings": warnings,
        "approval_gate_command_check": approval_gate_check,
        "execution_command_check": execution_check,
        "config_checks": config_rows,
        "operational_gate_feasibility_checks": gate_rows,
        "planned_artifact_checks": artifact_rows,
        "rows": rows,
    }
