#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.build_ligand_heavy_cleanup_approval_packet import APPROVAL_TOKEN
from tools.cleanup_ligand_heavy_runs import PAYLOAD_DIR_NAMES

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_APPROVAL_JSON = "runs/ligand_heavy_cleanup_approval_packet_current.json"
DEFAULT_WORK_ORDER_JSON = "runs/ligand_heavy_cleanup_work_order_current.json"
DEFAULT_OUT_JSON = "runs/ligand_heavy_cleanup_execution_preflight_current.json"
DEFAULT_OUT_CSV = "runs/ligand_heavy_cleanup_execution_preflight_current.csv"
DEFAULT_OUT_MD = "runs/ligand_heavy_cleanup_execution_preflight_current.md"
CLAIM_BOUNDARY = (
    "Ligand-heavy cleanup execution preflight only; it validates approval-gated cleanup candidates and commands. "
    "It does not delete, move, archive, upload, commit, push, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _blocker(code: str, reason: str, *, path: str = "") -> dict[str, str]:
    payload = {"code": code, "severity": "hard", "reason": reason}
    if path:
        payload["path"] = path
    return payload


def _warning(code: str, reason: str, *, path: str = "") -> dict[str, str]:
    payload = {"code": code, "severity": "warning", "reason": reason}
    if path:
        payload["path"] = path
    return payload


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
    except ValueError:
        return False
    return True


def _command_parts(command: Any) -> list[str]:
    if isinstance(command, list):
        return [_text(part) for part in command if _text(part)]
    text = _text(command)
    return shlex.split(text) if text else []


def _command_roots(parts: list[str]) -> list[str]:
    roots: list[str] = []
    index = 0
    while index < len(parts):
        if parts[index] == "--root" and index + 1 < len(parts):
            roots.append(parts[index + 1])
            index += 2
            continue
        index += 1
    return roots


def _command_has_entrypoint(parts: list[str]) -> bool:
    return any(part.replace("\\", "/") == "tools/cleanup_ligand_heavy_runs.py" or part.replace("\\", "/").endswith("/tools/cleanup_ligand_heavy_runs.py") for part in parts)


def build_execution_preflight(
    approval_packet: dict[str, Any],
    work_order_packet: dict[str, Any],
) -> dict[str, Any]:
    approval_summary = _summary(approval_packet)
    work_summary = _summary(work_order_packet)
    approval_rows = [row for row in approval_packet.get("rows", []) or [] if isinstance(row, dict)]
    commands = work_order_packet.get("commands") if isinstance(work_order_packet.get("commands"), dict) else {}
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    if approval_summary.get("status") != "approval_packet_ready":
        blockers.append(_blocker("approval_packet_not_ready", "Approval packet must be approval_packet_ready."))
    if work_summary.get("status") != "cleanup_work_order_ready":
        blockers.append(_blocker("cleanup_work_order_not_ready", "Cleanup work order must be cleanup_work_order_ready."))
    for label, summary in (("approval_packet", approval_summary), ("work_order", work_summary)):
        if summary.get("approval_token_required") != APPROVAL_TOKEN:
            blockers.append(_blocker(f"{label}_approval_token_invalid", f"{label} must require {APPROVAL_TOKEN}."))
        if summary.get("delete_executed") is not False:
            blockers.append(_blocker(f"{label}_delete_flag_invalid", f"{label} must keep delete_executed=false."))
        if summary.get("external_state_mutated") is not False:
            blockers.append(_blocker(f"{label}_external_state_invalid", f"{label} must keep external_state_mutated=false."))
    if work_summary.get("delete_enabled") is not False:
        blockers.append(_blocker("work_order_delete_enabled_invalid", "Work order must keep delete_enabled=false before explicit approval."))
    if not approval_rows:
        blockers.append(_blocker("cleanup_candidates_missing", "Approval packet must include cleanup candidate rows."))

    refresh_parts = _command_parts(commands.get("refresh_dry_run_command"))
    execute_parts = _command_parts(commands.get("execute_after_approval_command"))
    if not _command_has_entrypoint(refresh_parts):
        blockers.append(_blocker("refresh_command_entrypoint_missing", "Refresh command must call tools/cleanup_ligand_heavy_runs.py."))
    if "--execute" in refresh_parts:
        blockers.append(_blocker("refresh_command_contains_execute", "Refresh dry-run command must not include --execute."))
    if not _command_has_entrypoint(execute_parts):
        blockers.append(_blocker("execute_command_entrypoint_missing", "Execute command must call tools/cleanup_ligand_heavy_runs.py."))
    if "--execute" not in execute_parts:
        blockers.append(_blocker("execute_command_missing_execute_flag", "Execute-after-approval command must include --execute."))

    row_roots = sorted({_text(row.get("root")) for row in approval_rows if _text(row.get("root"))})
    command_roots = sorted(_command_roots(execute_parts))
    if row_roots != command_roots:
        blockers.append(_blocker("execute_command_roots_mismatch", f"Execute command roots {command_roots} do not match approval rows {row_roots}."))

    row_checks: list[dict[str, Any]] = []
    existing_candidate_count = 0
    candidate_bytes = 0
    for row in approval_rows:
        root_text = _text(row.get("root"))
        path_text = _text(row.get("path"))
        run_path_text = _text(row.get("run_path"))
        size_bytes = _int(row.get("size_bytes"))
        candidate_bytes += size_bytes
        path = Path(path_text)
        root = Path(root_text) if root_text else Path()
        run_path = Path(run_path_text) if run_path_text else path.parent
        row_blockers: list[str] = []
        if not root_text:
            row_blockers.append("root_missing")
        if not path_text:
            row_blockers.append("path_missing")
        if path_text and root_text and not _is_relative_to(path, root):
            row_blockers.append("candidate_path_outside_root")
        if path_text and run_path_text and not _is_relative_to(path, run_path):
            row_blockers.append("candidate_path_outside_run_path")
        if path.name.lower() not in PAYLOAD_DIR_NAMES:
            row_blockers.append("candidate_not_known_payload_dir")
        if path.exists():
            existing_candidate_count += 1
            if not path.is_dir():
                row_blockers.append("candidate_path_not_directory")
            if path.is_symlink():
                row_blockers.append("candidate_path_is_symlink")
        else:
            row_blockers.append("candidate_path_missing_refresh_required")
        if row.get("parent_run_preserved") is not True:
            row_blockers.append("parent_run_preservation_not_asserted")
        if _text(row.get("deletion_scope")) != "payload_directory_only":
            row_blockers.append("deletion_scope_not_payload_only")
        if row_blockers:
            blockers.append(_blocker("cleanup_candidate_blocked", "Cleanup candidate failed preflight: " + ",".join(row_blockers), path=path_text))
        row_checks.append(
            {
                "path": path_text,
                "root": root_text,
                "run_path": run_path_text,
                "size_bytes": size_bytes,
                "present": path.exists(),
                "is_dir": path.is_dir(),
                "is_symlink": path.is_symlink(),
                "preflight_status": "fail" if row_blockers else "pass",
                "blockers": ",".join(row_blockers),
            }
        )

    expected_count = _int(approval_summary.get("candidate_count"))
    if expected_count != len(approval_rows):
        blockers.append(_blocker("candidate_count_mismatch", f"Approval summary candidate_count={expected_count} but rows={len(approval_rows)}."))
    expected_bytes = _int(approval_summary.get("candidate_bytes"))
    if expected_bytes and expected_bytes != candidate_bytes:
        warnings.append(_warning("candidate_bytes_mismatch", f"Approval summary candidate_bytes={expected_bytes} but rows sum to {candidate_bytes}."))

    status = "ligand_heavy_cleanup_execution_preflight_ready" if not blockers else "blocked_ligand_heavy_cleanup_execution_preflight"
    summary = {
        "packet_type": "ligand_heavy_cleanup_execution_preflight",
        "status": status,
        "candidate_count": len(approval_rows),
        "existing_candidate_count": existing_candidate_count,
        "candidate_bytes": candidate_bytes,
        "candidate_size_gb": round(candidate_bytes / (1024**3), 3),
        "root_count": len(row_roots),
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "approval_token_required": APPROVAL_TOKEN,
        "delete_enabled": False,
        "delete_executed": False,
        "external_state_mutated": False,
        "validated_without_execution": True,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            f"Review this preflight and provide `{APPROVAL_TOKEN}` only if the execute command should be run."
            if status == "ligand_heavy_cleanup_execution_preflight_ready"
            else "Refresh the dry-run report or repair cleanup candidate/command blockers before deletion approval."
        ),
    }
    return {
        "summary": summary,
        "blockers": blockers,
        "warnings": warnings,
        "command_checks": [
            {
                "command": "refresh_dry_run",
                "entrypoint_seen": _command_has_entrypoint(refresh_parts),
                "execute_flag_seen": "--execute" in refresh_parts,
                "root_count": len(_command_roots(refresh_parts)),
            },
            {
                "command": "execute_after_approval",
                "entrypoint_seen": _command_has_entrypoint(execute_parts),
                "execute_flag_seen": "--execute" in execute_parts,
                "root_count": len(command_roots),
            },
        ],
        "rows": row_checks,
    }


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Ligand Heavy Cleanup Execution Preflight",
        "",
        f"- status: `{s['status']}`",
        f"- candidate_count: `{s['candidate_count']}`",
        f"- existing_candidate_count: `{s['existing_candidate_count']}`",
        f"- candidate_size_gb: `{s['candidate_size_gb']}`",
        f"- approval_token_required: `{s['approval_token_required']}`",
        f"- delete_enabled: `{s['delete_enabled']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        f"- validated_without_execution: `{s['validated_without_execution']}`",
        "",
        "## Candidate Checks",
        "",
        "| status | present | size_gb | path | blockers |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        size_gb = round(_float(row.get("size_bytes")) / (1024**3), 3)
        lines.append(f"| `{row['preflight_status']}` | `{row['present']}` | `{size_gb}` | `{row['path']}` | `{row['blockers']}` |")
    lines.extend(["", "## Blockers", ""])
    blockers = payload.get("blockers") or []
    if blockers:
        lines.extend(f"- `{blocker['code']}`: {blocker['reason']}" for blocker in blockers)
    else:
        lines.append("- none")
    lines.extend(["", "## Warnings", ""])
    warnings = payload.get("warnings") or []
    if warnings:
        lines.extend(f"- `{warning['code']}`: {warning['reason']}" for warning in warnings)
    else:
        lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preflight approval-gated ligand-heavy cleanup execution without deleting files.")
    parser.add_argument("--approval-json", default=DEFAULT_APPROVAL_JSON)
    parser.add_argument("--work-order-json", default=DEFAULT_WORK_ORDER_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_execution_preflight(_read_json(args.approval_json), _read_json(args.work_order_json))
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
