#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.build_cleanup_execution_approval_dossier import DEFAULT_OUT_JSON as DEFAULT_DOSSIER_JSON
from tools.build_cleanup_execution_approval_gate import DEFAULT_OUT_JSON as DEFAULT_APPROVAL_GATE_JSON
from tools.build_cleanup_payload_manifest_lock import DEFAULT_OUT_JSON as DEFAULT_PAYLOAD_LOCK_JSON
from tools.build_protected_cleanup_policy_decision_gate import DEFAULT_OUT_JSON as DEFAULT_PROTECTED_POLICY_JSON

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/cleanup_postcheck_contract_current.json"
DEFAULT_OUT_CSV = "runs/cleanup_postcheck_contract_current.csv"
DEFAULT_OUT_MD = "runs/cleanup_postcheck_contract_current.md"

CLAIM_BOUNDARY = (
    "Cleanup postcheck contract only; it maps approval-ready cleanup rows to required post-execution evidence and "
    "refresh commands. It does not approve cleanup, delete, move, archive, externalize, upload, commit, push, or mutate "
    "external state."
)

GLOBAL_REFRESH_COMMANDS = [
    "python3 tools/build_cleanup_snapshot_preflight.py",
    "python3 tools/build_cleanup_snapshot_artifacts.py",
    "python3 tools/build_cleanup_execution_approval_dossier.py",
    "python3 tools/build_cleanup_payload_manifest_lock.py",
    "python3 tools/build_cleanup_execution_approval_gate.py",
    "python3 tools/build_cleanup_completion_gate.py",
    "python3 tools/build_goal_readiness_rollup.py",
    "python3 tools/build_goal_operator_action_board.py",
    "python3 tools/build_goal_release_decision_gate.py",
]


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
    rows = packet.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (_text(row.get("lane")), _text(row.get("recommended_action")), _text(row.get("path")))


def _postcheck_requirement(row: dict[str, Any]) -> tuple[str, str]:
    lane = _text(row.get("lane"))
    action = _text(row.get("recommended_action"))
    if lane == "ligand_heavy_cleanup":
        return (
            "rerun ligand-heavy dry-run, approval dossier, payload lock, completion gate, and release gates",
            "python3 tools/build_ligand_heavy_cleanup_execution_preflight.py",
        )
    if action == "externalize":
        return (
            "externalized payload listing/checksum manifest exists and source is no longer required by active local tests",
            "python3 tools/build_cleanup_snapshot_preflight.py",
        )
    if action == "archive":
        return (
            "archive manifest exists and current product/CAMEO/cleanup artifacts still resolve",
            "python3 tools/build_cleanup_snapshot_artifacts.py",
        )
    if action == "delete_candidate":
        return (
            "source tree compiles and focused product/CAMEO/cleanup gates still pass after approved deletion",
            "python3 -m py_compile api/main.py api/cleanup.py betelgeuze_cleanup/cli.py",
        )
    return (
        "row-specific postcheck evidence is recorded before cleanup completion is claimed",
        "python3 tools/build_cleanup_completion_gate.py",
    )


def _blocker(code: str, reason: str) -> dict[str, str]:
    return {"code": code, "severity": "hard", "reason": reason}


def build_cleanup_postcheck_contract(
    *,
    dossier_packet: dict[str, Any],
    payload_lock_packet: dict[str, Any],
    approval_gate_packet: dict[str, Any],
    protected_policy_packet: dict[str, Any],
    dossier_json: str = DEFAULT_DOSSIER_JSON,
    payload_lock_json: str = DEFAULT_PAYLOAD_LOCK_JSON,
    approval_gate_json: str = DEFAULT_APPROVAL_GATE_JSON,
    protected_policy_json: str = DEFAULT_PROTECTED_POLICY_JSON,
) -> dict[str, Any]:
    dossier = _summary(dossier_packet)
    payload_lock = _summary(payload_lock_packet)
    approval_gate = _summary(approval_gate_packet)
    protected_policy = _summary(protected_policy_packet)
    dossier_rows = _rows(dossier_packet)
    lock_by_key = {_key(row): row for row in _rows(payload_lock_packet)}
    blockers: list[dict[str, str]] = []
    if _text(dossier.get("status")) != "cleanup_execution_approval_dossier_ready":
        blockers.append(_blocker("cleanup_execution_approval_dossier_not_ready", "Cleanup postchecks require a ready approval dossier."))
    if _text(payload_lock.get("status")) != "cleanup_payload_manifest_lock_ready":
        blockers.append(_blocker("cleanup_payload_manifest_lock_not_ready", "Cleanup postchecks require a ready payload manifest lock."))

    rows: list[dict[str, Any]] = []
    for row in dossier_rows:
        approval_status = _text(row.get("approval_status"))
        if approval_status not in {"approval_required", "policy_blocked_not_promoted"}:
            continue
        requirement, command = _postcheck_requirement(row)
        lock_row = lock_by_key.get(_key(row), {})
        payload_fingerprint = _text(lock_row.get("payload_fingerprint_sha256"))
        row_blockers: list[str] = []
        if approval_status == "approval_required" and not payload_fingerprint:
            row_blockers.append("payload_fingerprint_missing")
        if approval_status == "policy_blocked_not_promoted" and _text(protected_policy.get("status")) == "":
            row_blockers.append("protected_policy_gate_missing")
        if row_blockers:
            blockers.append(
                _blocker(
                    f"{_text(row.get('lane'))}_postcheck_not_ready",
                    f"Postcheck row is incomplete for {_text(row.get('path'))}: {','.join(row_blockers)}.",
                )
            )
        rows.append(
            {
                "lane": _text(row.get("lane")),
                "operation_class": _text(row.get("operation_class")),
                "recommended_action": _text(row.get("recommended_action")),
                "path": _text(row.get("path")),
                "approval_status": approval_status,
                "approval_token_required": _text(row.get("approval_token_required")),
                "size_gb": round(_float(row.get("size_gb")), 3),
                "candidate_count": _int(row.get("candidate_count")),
                "payload_fingerprint_sha256": payload_fingerprint,
                "snapshot_fingerprint_sha256": _text(row.get("snapshot_fingerprint_sha256")),
                "required_postcheck": requirement,
                "postcheck_refresh_command": command,
                "global_refresh_required": True,
                "postcheck_status": "ready" if not row_blockers else "blocked",
                "blockers": ",".join(row_blockers),
                "execution_enabled": False,
                "delete_executed": False,
                "archive_executed": False,
                "externalize_executed": False,
                "external_state_mutated": False,
            }
        )

    approval_rows = [row for row in rows if row["approval_status"] == "approval_required"]
    protected_rows = [row for row in rows if row["approval_status"] == "policy_blocked_not_promoted"]
    blocked_rows = [row for row in rows if row["postcheck_status"] != "ready"]
    postcheck_ready = bool(rows) and not blockers and not blocked_rows
    summary = {
        "packet_type": "cleanup_postcheck_contract",
        "status": "cleanup_postcheck_contract_ready" if postcheck_ready else "blocked_cleanup_postcheck_contract",
        "postcheck_contract_ready": postcheck_ready,
        "row_count": len(rows),
        "approval_row_count": len(approval_rows),
        "protected_policy_row_count": len(protected_rows),
        "blocked_row_count": len(blocked_rows),
        "blocker_count": len(blockers),
        "blockers": [blocker["code"] for blocker in blockers],
        "source_dossier_json": dossier_json,
        "source_dossier_status": _text(dossier.get("status")),
        "source_payload_lock_json": payload_lock_json,
        "source_payload_lock_status": _text(payload_lock.get("status")),
        "source_approval_gate_json": approval_gate_json,
        "source_approval_gate_status": _text(approval_gate.get("status")),
        "source_protected_policy_json": protected_policy_json,
        "source_protected_policy_status": _text(protected_policy.get("status")),
        "approval_reclaim_size_gb": round(_float(dossier.get("approval_reclaim_size_gb")), 3),
        "protected_payload_size_gb": round(_float(dossier.get("protected_payload_size_gb") or protected_policy.get("protected_payload_size_gb")), 3),
        "payload_manifest_fingerprint_sha256": _text(payload_lock.get("payload_manifest_fingerprint_sha256")),
        "global_refresh_command_count": len(GLOBAL_REFRESH_COMMANDS),
        "global_refresh_commands": list(GLOBAL_REFRESH_COMMANDS),
        "execution_enabled": False,
        "delete_executed": False,
        "archive_executed": False,
        "externalize_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "After operator-approved cleanup execution, run the row-specific postchecks and global refresh sequence before marking cleanup complete."
            if postcheck_ready
            else "Repair blocked postcheck rows before relying on cleanup completion evidence."
        ),
    }
    return {"summary": summary, "rows": rows, "blockers": blockers}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Cleanup Postcheck Contract",
        "",
        f"- status: `{s['status']}`",
        f"- postcheck_contract_ready: `{s['postcheck_contract_ready']}`",
        f"- row_count: `{s['row_count']}`",
        f"- approval_row_count: `{s['approval_row_count']}`",
        f"- protected_policy_row_count: `{s['protected_policy_row_count']}`",
        f"- blocked_row_count: `{s['blocked_row_count']}`",
        f"- approval_reclaim_size_gb: `{s['approval_reclaim_size_gb']}`",
        f"- protected_payload_size_gb: `{s['protected_payload_size_gb']}`",
        f"- payload_manifest_fingerprint_sha256: `{s['payload_manifest_fingerprint_sha256']}`",
        f"- global_refresh_command_count: `{s['global_refresh_command_count']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        f"- archive_executed: `{s['archive_executed']}`",
        f"- externalize_executed: `{s['externalize_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Rows",
        "",
        "| lane | action | status | size_gb | required_postcheck | command | path |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['lane']}` | `{row['recommended_action']}` | `{row['postcheck_status']}` | "
            f"`{row['size_gb']}` | `{row['required_postcheck']}` | `{row['postcheck_refresh_command']}` | `{row['path']}` |"
        )
    lines.extend(["", "## Global Refresh Commands", ""])
    lines.extend(f"- `{command}`" for command in s["global_refresh_commands"])
    lines.extend(["", "## Blockers", ""])
    if payload["blockers"]:
        lines.extend(f"- `{blocker['code']}`: {blocker['reason']}" for blocker in payload["blockers"])
    else:
        lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a cleanup postcheck contract without executing cleanup.")
    parser.add_argument("--dossier-json", default=DEFAULT_DOSSIER_JSON)
    parser.add_argument("--payload-lock-json", default=DEFAULT_PAYLOAD_LOCK_JSON)
    parser.add_argument("--approval-gate-json", default=DEFAULT_APPROVAL_GATE_JSON)
    parser.add_argument("--protected-policy-json", default=DEFAULT_PROTECTED_POLICY_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_cleanup_postcheck_contract(
        dossier_packet=_read_json_if_present(args.dossier_json),
        payload_lock_packet=_read_json_if_present(args.payload_lock_json),
        approval_gate_packet=_read_json_if_present(args.approval_gate_json),
        protected_policy_packet=_read_json_if_present(args.protected_policy_json),
        dossier_json=args.dossier_json,
        payload_lock_json=args.payload_lock_json,
        approval_gate_json=args.approval_gate_json,
        protected_policy_json=args.protected_policy_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
