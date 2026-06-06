#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.build_cleanup_execution_approval_dossier import DEFAULT_OUT_JSON as DEFAULT_DOSSIER_JSON
from tools.build_cleanup_payload_manifest_lock import DEFAULT_OUT_JSON as DEFAULT_PAYLOAD_LOCK_JSON

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OPERATOR_APPROVAL_CSV = "runs/cleanup_execution_operator_approval_intake.csv"
DEFAULT_TEMPLATE_CSV = "runs/cleanup_execution_operator_approval_template_current.csv"
DEFAULT_OUT_JSON = "runs/cleanup_execution_approval_gate_current.json"
DEFAULT_OUT_CSV = "runs/cleanup_execution_approval_gate_current.csv"
DEFAULT_OUT_MD = "runs/cleanup_execution_approval_gate_current.md"

CLAIM_BOUNDARY = (
    "Cleanup execution approval gate only; it validates operator approval-token intake against the cleanup dossier "
    "and builds a local execution authorization view. It does not execute cleanup, delete, move, archive, externalize, "
    "upload, commit, push, or mutate external state."
)

APPROVE_DECISION = "approve"
SKIP_DECISION = "skip"
VALID_DECISIONS = {APPROVE_DECISION, SKIP_DECISION}


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


def _read_csv_rows(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_template(path_like: str | Path, dossier_rows: list[dict[str, Any]], payload_lock_rows: list[dict[str, Any]] | None = None) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_by_key = {_key(row): row for row in payload_lock_rows or []}
    fieldnames = [
        "lane",
        "recommended_action",
        "path",
        "payload_fingerprint_sha256",
        "approval_status",
        "approval_token_required",
        "operator_decision",
        "operator_approval_token",
        "operator_note",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in dossier_rows:
            if _text(row.get("approval_status")) != "approval_required":
                continue
            writer.writerow(
                {
                    "lane": _text(row.get("lane")),
                    "recommended_action": _text(row.get("recommended_action")),
                    "path": _text(row.get("path")),
                    "payload_fingerprint_sha256": _text(lock_by_key.get(_key(row), {}).get("payload_fingerprint_sha256")),
                    "approval_status": _text(row.get("approval_status")),
                    "approval_token_required": _text(row.get("approval_token_required")),
                    "operator_decision": "",
                    "operator_approval_token": "",
                    "operator_note": "",
                }
            )


def build_cleanup_execution_approval_gate(
    *,
    dossier_packet: dict[str, Any],
    payload_lock_packet: dict[str, Any] | None = None,
    operator_approval_rows: list[dict[str, Any]],
    dossier_json: str = DEFAULT_DOSSIER_JSON,
    payload_lock_json: str = DEFAULT_PAYLOAD_LOCK_JSON,
    operator_approval_csv: str = DEFAULT_OPERATOR_APPROVAL_CSV,
    template_csv: str = DEFAULT_TEMPLATE_CSV,
    operator_approval_csv_present: bool = True,
    payload_lock_required: bool = False,
) -> dict[str, Any]:
    dossier = _summary(dossier_packet)
    dossier_rows = _rows(dossier_packet)
    payload_lock_packet = payload_lock_packet or {}
    payload_lock = _summary(payload_lock_packet)
    payload_lock_rows = _rows(payload_lock_packet)
    blockers: list[str] = []
    if dossier.get("status") != "cleanup_execution_approval_dossier_ready":
        blockers.append("cleanup_execution_approval_dossier_not_ready")
    if payload_lock_required and payload_lock.get("status") != "cleanup_payload_manifest_lock_ready":
        blockers.append("cleanup_payload_manifest_lock_not_ready")

    approvals_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    duplicate_approval_count = 0
    for row in operator_approval_rows:
        key = _key(row)
        if key in approvals_by_key:
            duplicate_approval_count += 1
        approvals_by_key[key] = row
    if duplicate_approval_count:
        blockers.append("duplicate_operator_approval_rows")
    if not operator_approval_csv_present:
        blockers.append("operator_approval_csv_missing")

    dossier_keys = {_key(row) for row in dossier_rows}
    unknown_approval_count = 0
    for key in approvals_by_key:
        if key not in dossier_keys:
            unknown_approval_count += 1
    if unknown_approval_count:
        blockers.append("operator_approval_row_not_in_dossier")

    lock_by_key = {_key(row): row for row in payload_lock_rows}
    if payload_lock_required:
        dossier_approval_keys = {_key(row) for row in dossier_rows if _text(row.get("approval_status")) == "approval_required"}
        missing_lock_row_count = sum(1 for key in dossier_approval_keys if key not in lock_by_key)
        if missing_lock_row_count:
            blockers.append("cleanup_payload_lock_row_missing")

    rows: list[dict[str, Any]] = []
    for dossier_row in dossier_rows:
        approval_status = _text(dossier_row.get("approval_status"))
        approval_row = approvals_by_key.get(_key(dossier_row), {})
        decision = _text(approval_row.get("operator_decision")).lower()
        operator_token = _text(approval_row.get("operator_approval_token") or approval_row.get("approval_token"))
        operator_payload_fingerprint = _text(
            approval_row.get("payload_fingerprint_sha256") or approval_row.get("cleanup_payload_fingerprint_sha256")
        )
        required_token = _text(dossier_row.get("approval_token_required"))
        lock_row = lock_by_key.get(_key(dossier_row), {})
        expected_payload_fingerprint = _text(lock_row.get("payload_fingerprint_sha256"))
        row_blockers: list[str] = []
        gate_status = "not_eligible_for_execution"

        if approval_status == "approval_required":
            if payload_lock_required:
                if not lock_row:
                    row_blockers.append("cleanup_payload_lock_row_missing")
                elif _text(lock_row.get("lock_status")) != "locked":
                    row_blockers.append("cleanup_payload_lock_row_not_locked")
            if not approval_row:
                row_blockers.append("operator_decision_missing")
                gate_status = "awaiting_operator_approval"
            elif decision not in VALID_DECISIONS:
                row_blockers.append("operator_decision_invalid")
                gate_status = "blocked_before_execution"
            elif payload_lock_required and not operator_payload_fingerprint:
                row_blockers.append("operator_payload_fingerprint_missing")
                gate_status = "blocked_before_execution"
            elif payload_lock_required and operator_payload_fingerprint != expected_payload_fingerprint:
                row_blockers.append("operator_payload_fingerprint_mismatch")
                gate_status = "blocked_before_execution"
            elif decision == SKIP_DECISION:
                gate_status = "skipped_by_operator"
            elif operator_token != required_token:
                row_blockers.append("operator_approval_token_mismatch")
                gate_status = "blocked_before_execution"
            else:
                gate_status = "authorized_for_operator_execution"
        elif approval_status == "policy_blocked_not_promoted":
            if decision == APPROVE_DECISION or operator_token:
                row_blockers.append("protected_row_approval_attempted")
                gate_status = "blocked_protected_row_attempted"
            else:
                gate_status = "policy_blocked_not_promoted"
        else:
            gate_status = "blocked_before_execution"
            row_blockers.append("dossier_row_not_approval_ready")

        if row_blockers:
            blockers.extend(row_blockers)
        rows.append(
            {
                "lane": _text(dossier_row.get("lane")),
                "recommended_action": _text(dossier_row.get("recommended_action")),
                "path": _text(dossier_row.get("path")),
                "dossier_approval_status": approval_status,
                "approval_gate_status": gate_status,
                "operator_decision": decision,
                "approval_token_required": required_token,
                "operator_approval_token_present": bool(operator_token),
                "expected_payload_fingerprint_sha256": expected_payload_fingerprint,
                "operator_payload_fingerprint_sha256": operator_payload_fingerprint,
                "size_gb": round(_float(dossier_row.get("size_gb")), 3),
                "candidate_count": _int(dossier_row.get("candidate_count")),
                "snapshot_fingerprint_sha256": _text(dossier_row.get("snapshot_fingerprint_sha256")),
                "blockers": ",".join(row_blockers),
                "execution_enabled": False,
                "delete_executed": False,
                "external_state_mutated": False,
            }
        )

    authorized_rows = [row for row in rows if row["approval_gate_status"] == "authorized_for_operator_execution"]
    skipped_rows = [row for row in rows if row["approval_gate_status"] == "skipped_by_operator"]
    protected_rows = [row for row in rows if row["approval_gate_status"] == "policy_blocked_not_promoted"]
    awaiting_rows = [row for row in rows if row["approval_gate_status"] == "awaiting_operator_approval"]
    blocked_rows = [row for row in rows if row["blockers"]]
    status = "cleanup_execution_operator_approval_gate_ready" if authorized_rows and not blockers else "blocked_cleanup_execution_operator_approval_gate"
    summary = {
        "packet_type": "cleanup_execution_operator_approval_gate",
        "status": status,
        "source_dossier_json": dossier_json,
        "source_dossier_status": _text(dossier.get("status")),
        "source_payload_lock_json": payload_lock_json,
        "source_payload_lock_status": _text(payload_lock.get("status")),
        "payload_lock_required": bool(payload_lock_required),
        "payload_manifest_fingerprint_sha256": _text(payload_lock.get("payload_manifest_fingerprint_sha256")),
        "payload_lock_row_count": _int(payload_lock.get("row_count")),
        "payload_lock_blocked_row_count": _int(payload_lock.get("blocked_row_count")),
        "operator_approval_csv": operator_approval_csv,
        "operator_approval_csv_present": bool(operator_approval_csv_present),
        "operator_template_csv": template_csv,
        "approval_row_count": sum(1 for row in dossier_rows if _text(row.get("approval_status")) == "approval_required"),
        "authorized_row_count": len(authorized_rows),
        "skipped_row_count": len(skipped_rows),
        "awaiting_operator_approval_row_count": len(awaiting_rows),
        "blocked_row_count": len(blocked_rows),
        "protected_not_promoted_row_count": len(protected_rows),
        "unknown_operator_approval_row_count": unknown_approval_count,
        "duplicate_operator_approval_row_count": duplicate_approval_count,
        "authorized_reclaim_size_gb": round(sum(_float(row.get("size_gb")) for row in authorized_rows), 3),
        "total_reclaim_size_gb": round(_float(dossier.get("approval_reclaim_size_gb")), 3),
        "protected_payload_size_gb": round(_float(dossier.get("protected_payload_size_gb")), 3),
        "blocker_count": len(blockers),
        "blockers": sorted(set(blockers)),
        "execution_enabled": False,
        "delete_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Run only the authorized rows through the separate operator-approved cleanup executor."
            if status == "cleanup_execution_operator_approval_gate_ready"
            else f"Fill `{template_csv}` into `{operator_approval_csv}` with exact per-row decisions and approval tokens."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Cleanup Execution Operator Approval Gate",
        "",
        f"- status: `{s['status']}`",
        f"- source_payload_lock_status: `{s['source_payload_lock_status']}`",
        f"- payload_lock_required: `{s['payload_lock_required']}`",
        f"- payload_manifest_fingerprint_sha256: `{s['payload_manifest_fingerprint_sha256']}`",
        f"- operator_approval_csv_present: `{s['operator_approval_csv_present']}`",
        f"- approval_row_count: `{s['approval_row_count']}`",
        f"- authorized_row_count: `{s['authorized_row_count']}`",
        f"- awaiting_operator_approval_row_count: `{s['awaiting_operator_approval_row_count']}`",
        f"- blocked_row_count: `{s['blocked_row_count']}`",
        f"- protected_not_promoted_row_count: `{s['protected_not_promoted_row_count']}`",
        f"- authorized_reclaim_size_gb: `{s['authorized_reclaim_size_gb']}`",
        f"- total_reclaim_size_gb: `{s['total_reclaim_size_gb']}`",
        f"- protected_payload_size_gb: `{s['protected_payload_size_gb']}`",
        f"- execution_enabled: `{s['execution_enabled']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Rows",
        "",
        "| gate_status | lane | action | decision | payload | size_gb | candidates | path | blockers |",
        "| --- | --- | --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        payload_fingerprint = row["expected_payload_fingerprint_sha256"][:12] if row["expected_payload_fingerprint_sha256"] else ""
        lines.append(
            f"| `{row['approval_gate_status']}` | `{row['lane']}` | `{row['recommended_action']}` | "
            f"`{row['operator_decision']}` | `{payload_fingerprint}` | `{row['size_gb']}` | `{row['candidate_count']}` | "
            f"`{row['path']}` | `{row['blockers']}` |"
        )
    lines.extend(["", "## Blockers", ""])
    if s["blockers"]:
        lines.extend(f"- `{blocker}`" for blocker in s["blockers"])
    else:
        lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate cleanup operator approval tokens without executing cleanup.")
    parser.add_argument("--dossier-json", default=DEFAULT_DOSSIER_JSON)
    parser.add_argument("--payload-lock-json", default=DEFAULT_PAYLOAD_LOCK_JSON)
    parser.add_argument("--operator-approval-csv", default=DEFAULT_OPERATOR_APPROVAL_CSV)
    parser.add_argument("--template-csv", default=DEFAULT_TEMPLATE_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    dossier_packet = _read_json_if_present(args.dossier_json)
    payload_lock_packet = _read_json_if_present(args.payload_lock_json)
    dossier_rows = _rows(dossier_packet)
    _write_template(args.template_csv, dossier_rows, _rows(payload_lock_packet))
    operator_path = _resolve(args.operator_approval_csv)
    payload = build_cleanup_execution_approval_gate(
        dossier_packet=dossier_packet,
        payload_lock_packet=payload_lock_packet,
        operator_approval_rows=_read_csv_rows(args.operator_approval_csv),
        dossier_json=args.dossier_json,
        payload_lock_json=args.payload_lock_json,
        operator_approval_csv=args.operator_approval_csv,
        template_csv=args.template_csv,
        operator_approval_csv_present=operator_path.exists(),
        payload_lock_required=True,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
