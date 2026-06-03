#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.build_ligand_heavy_cleanup_approval_packet import APPROVAL_TOKEN

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_APPROVAL_JSON = "runs/ligand_heavy_cleanup_approval_packet_current.json"
DEFAULT_OUT_JSON = "runs/ligand_heavy_cleanup_work_order_current.json"
DEFAULT_OUT_CSV = "runs/ligand_heavy_cleanup_work_order_current.csv"
DEFAULT_OUT_MD = "runs/ligand_heavy_cleanup_work_order_current.md"
CLAIM_BOUNDARY = (
    "Ligand-heavy cleanup work order only; it records the approval-gated cleanup command. "
    "It does not delete, move, archive, upload, commit, push, or change scientific claims."
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


def _quote_join(parts: list[str]) -> str:
    return " ".join(shlex.quote(str(part)) for part in parts)


def _unique_roots(rows: list[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    roots: list[str] = []
    for row in rows:
        root = str(row.get("root", "")).strip()
        if root and root not in seen:
            roots.append(root)
            seen.add(root)
    return roots


def build_work_order(
    approval_packet: dict[str, Any],
    *,
    approval_json: str = DEFAULT_APPROVAL_JSON,
    out_report_json: str = "runs/ligand_heavy_cleanup_execute_after_approval.json",
) -> dict[str, Any]:
    summary = approval_packet.get("summary") if isinstance(approval_packet.get("summary"), dict) else {}
    rows = approval_packet.get("rows") if isinstance(approval_packet.get("rows"), list) else []
    candidate_rows = [row for row in rows if isinstance(row, dict)]
    blockers: list[dict[str, str]] = []
    if summary.get("status") != "approval_packet_ready":
        blockers.append({"code": "approval_packet_not_ready", "severity": "hard", "reason": "Cleanup approval packet must be approval_packet_ready."})
    if summary.get("delete_executed") is not False:
        blockers.append({"code": "approval_packet_delete_flag_invalid", "severity": "hard", "reason": "Approval packet must report delete_executed=false."})
    if summary.get("external_state_mutated") is not False:
        blockers.append({"code": "approval_packet_external_state_invalid", "severity": "hard", "reason": "Approval packet must report external_state_mutated=false."})
    if summary.get("approval_token_required") != APPROVAL_TOKEN:
        blockers.append({"code": "approval_token_missing", "severity": "hard", "reason": f"Approval packet must require {APPROVAL_TOKEN}."})
    if not candidate_rows:
        blockers.append({"code": "cleanup_candidates_missing", "severity": "hard", "reason": "At least one cleanup candidate is required."})

    roots = _unique_roots(candidate_rows)
    command_parts = ["python3", "tools/cleanup_ligand_heavy_runs.py"]
    for root in roots:
        command_parts.extend(["--root", root])
    keep_recent = summary.get("keep_recent", 2)
    older_than_days = summary.get("older_than_days", 7)
    source_summary = {}
    source_json = str(summary.get("source_dry_run_json", "") or "")
    if source_json:
        try:
            source_summary = _read_json(source_json).get("summary", {})
        except (OSError, json.JSONDecodeError):
            source_summary = {}
    if isinstance(source_summary, dict):
        keep_recent = source_summary.get("keep_recent", keep_recent)
        older_than_days = source_summary.get("older_than_days", older_than_days)
    command_parts.extend(["--keep-recent", str(int(keep_recent or 0))])
    command_parts.extend(["--older-than-days", str(int(older_than_days or 0))])
    command_parts.extend(["--out-json", out_report_json])
    execute_command_parts = [*command_parts, "--execute"]
    dry_run_refresh_command_parts = [*command_parts]

    status = "cleanup_work_order_ready" if not blockers else "blocked_cleanup_work_order"
    work_summary = {
        "packet_type": "ligand_heavy_cleanup_work_order",
        "status": status,
        "source_approval_json": approval_json,
        "candidate_count": int(summary.get("candidate_count", len(candidate_rows)) or 0),
        "candidate_bytes": int(summary.get("candidate_bytes", 0) or 0),
        "candidate_size_gb": float(summary.get("candidate_size_gb", 0.0) or 0.0),
        "root_count": len(roots),
        "approval_token_required": APPROVAL_TOKEN,
        "delete_enabled": False,
        "delete_executed": False,
        "external_state_mutated": False,
        "parent_runs_preserved": True,
        "blocker_count": len(blockers),
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            f"Review this work order and provide `{APPROVAL_TOKEN}` before running the execute command."
            if status == "cleanup_work_order_ready"
            else "Repair approval packet blockers and regenerate this work order before deletion approval."
        ),
    }
    command_rows = [
        {
            "step": "refresh_dry_run",
            "command": _quote_join(dry_run_refresh_command_parts),
            "requires_approval_token": False,
            "delete_executed_by_this_packet": False,
        },
        {
            "step": "execute_after_approval",
            "command": _quote_join(execute_command_parts),
            "requires_approval_token": True,
            "approval_token_required": APPROVAL_TOKEN,
            "delete_executed_by_this_packet": False,
        },
    ]
    return {
        "summary": work_summary,
        "blockers": blockers,
        "roots": roots,
        "commands": {
            "refresh_dry_run_command": command_rows[0]["command"],
            "execute_after_approval_command": command_rows[1]["command"],
        },
        "rows": command_rows,
    }


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Ligand Heavy Cleanup Work Order",
        "",
        f"- status: `{s['status']}`",
        f"- candidate_count: `{s['candidate_count']}`",
        f"- candidate_size_gb: `{s['candidate_size_gb']}`",
        f"- root_count: `{s['root_count']}`",
        f"- approval_token_required: `{s['approval_token_required']}`",
        f"- delete_enabled: `{s['delete_enabled']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Commands",
        "",
        "| step | requires approval | command |",
        "| --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(f"| `{row['step']}` | `{row['requires_approval_token']}` | `{row['command']}` |")
    lines.extend(["", "## Blockers", ""])
    blockers = payload.get("blockers") or []
    if blockers:
        lines.extend(f"- `{blocker['code']}`: {blocker['reason']}" for blocker in blockers)
    else:
        lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an approval-gated ligand-heavy cleanup work order.")
    parser.add_argument("--approval-json", default=DEFAULT_APPROVAL_JSON)
    parser.add_argument("--out-report-json", default="runs/ligand_heavy_cleanup_execute_after_approval.json")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_work_order(_read_json(args.approval_json), approval_json=str(args.approval_json), out_report_json=str(args.out_report_json))
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
