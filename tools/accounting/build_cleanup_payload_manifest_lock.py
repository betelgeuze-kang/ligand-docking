#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.build_cleanup_execution_approval_dossier import DEFAULT_OUT_JSON as DEFAULT_DOSSIER_JSON

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_JSON = "runs/cleanup_payload_manifest_lock_current.json"
DEFAULT_OUT_CSV = "runs/cleanup_payload_manifest_lock_current.csv"
DEFAULT_OUT_MD = "runs/cleanup_payload_manifest_lock_current.md"

CLAIM_BOUNDARY = (
    "Cleanup payload manifest lock only; it computes stable per-row and manifest fingerprints for the current cleanup "
    "approval dossier and operator approval template. It does not execute cleanup, delete, move, archive, externalize, "
    "upload, commit, push, or mutate external state."
)

CANONICAL_FIELDS = [
    "lane",
    "operation_class",
    "recommended_action",
    "path",
    "approval_status",
    "approval_token_required",
    "size_gb",
    "candidate_count",
    "preflight_status",
    "snapshot_required",
    "snapshot_present",
    "snapshot_artifact",
    "snapshot_fingerprint_sha256",
    "postcheck",
    "protected_policy_change_required",
    "approval_promoted",
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
    return [row for row in packet.get("rows", []) or [] if isinstance(row, dict)]


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


def _canonical_row(row: dict[str, Any]) -> dict[str, Any]:
    canonical: dict[str, Any] = {}
    for field in CANONICAL_FIELDS:
        value = row.get(field)
        if field == "size_gb":
            canonical[field] = round(_float(value), 3)
        elif field == "candidate_count":
            canonical[field] = _int(value)
        elif field in {"snapshot_required", "snapshot_present", "protected_policy_change_required", "approval_promoted"}:
            canonical[field] = bool(value is True)
        else:
            canonical[field] = _text(value)
    return canonical


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _key(row: dict[str, Any]) -> str:
    return "|".join([_text(row.get("lane")), _text(row.get("recommended_action")), _text(row.get("path"))])


def _row_blockers(canonical: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    approval_status = _text(canonical.get("approval_status"))
    if not _text(canonical.get("lane")):
        blockers.append("lane_missing")
    if not _text(canonical.get("recommended_action")):
        blockers.append("recommended_action_missing")
    if not _text(canonical.get("path")):
        blockers.append("path_missing")
    if approval_status == "approval_required":
        if not _text(canonical.get("approval_token_required")):
            blockers.append("approval_token_required_missing")
        if _int(canonical.get("candidate_count")) <= 0:
            blockers.append("candidate_count_missing")
        if _float(canonical.get("size_gb")) < 0:
            blockers.append("size_gb_invalid")
        if canonical.get("snapshot_required") is True and not _text(canonical.get("snapshot_fingerprint_sha256")):
            blockers.append("required_snapshot_fingerprint_missing")
    elif approval_status == "policy_blocked_not_promoted":
        if canonical.get("approval_promoted") is True:
            blockers.append("protected_row_promoted_in_lock")
    else:
        blockers.append("approval_status_not_lockable")
    return blockers


def build_cleanup_payload_manifest_lock(
    *,
    dossier_packet: dict[str, Any],
    dossier_json: str = DEFAULT_DOSSIER_JSON,
) -> dict[str, Any]:
    dossier = _summary(dossier_packet)
    source_blockers: list[str] = []
    if dossier.get("status") != "cleanup_execution_approval_dossier_ready":
        source_blockers.append("cleanup_execution_approval_dossier_not_ready")

    lock_rows: list[dict[str, Any]] = []
    for source_row in sorted(_rows(dossier_packet), key=_key):
        canonical = _canonical_row(source_row)
        row_digest = _digest(canonical)
        blockers = _row_blockers(canonical)
        lock_rows.append(
            {
                "lane": canonical["lane"],
                "operation_class": canonical["operation_class"],
                "recommended_action": canonical["recommended_action"],
                "path": canonical["path"],
                "approval_status": canonical["approval_status"],
                "approval_token_required": canonical["approval_token_required"],
                "size_gb": canonical["size_gb"],
                "candidate_count": canonical["candidate_count"],
                "snapshot_required": canonical["snapshot_required"],
                "snapshot_present": canonical["snapshot_present"],
                "snapshot_artifact": canonical["snapshot_artifact"],
                "snapshot_fingerprint_sha256": canonical["snapshot_fingerprint_sha256"],
                "payload_fingerprint_sha256": row_digest,
                "lock_status": "locked" if not blockers else "blocked",
                "blockers": ",".join(blockers),
                "execution_enabled": False,
                "delete_executed": False,
                "external_state_mutated": False,
            }
        )

    duplicate_key_count = len(lock_rows) - len({_key(row) for row in lock_rows})
    if duplicate_key_count:
        source_blockers.append("duplicate_dossier_lock_keys")
    row_blocker_count = sum(1 for row in lock_rows if row["lock_status"] == "blocked")
    manifest_rows = [
        {
            "lane": row["lane"],
            "recommended_action": row["recommended_action"],
            "path": row["path"],
            "payload_fingerprint_sha256": row["payload_fingerprint_sha256"],
        }
        for row in lock_rows
    ]
    manifest_fingerprint = _digest(manifest_rows)
    approval_rows = [row for row in lock_rows if row["approval_status"] == "approval_required"]
    protected_rows = [row for row in lock_rows if row["approval_status"] == "policy_blocked_not_promoted"]
    blocker_count = len(source_blockers) + row_blocker_count
    status = "cleanup_payload_manifest_lock_ready" if lock_rows and blocker_count == 0 else "blocked_cleanup_payload_manifest_lock"
    summary = {
        "packet_type": "cleanup_payload_manifest_lock",
        "status": status,
        "source_dossier_json": dossier_json,
        "source_dossier_status": _text(dossier.get("status")),
        "row_count": len(lock_rows),
        "approval_row_count": len(approval_rows),
        "protected_not_promoted_row_count": len(protected_rows),
        "locked_row_count": sum(1 for row in lock_rows if row["lock_status"] == "locked"),
        "blocked_row_count": row_blocker_count,
        "duplicate_key_count": duplicate_key_count,
        "approval_payload_fingerprint_count": len({row["payload_fingerprint_sha256"] for row in approval_rows}),
        "payload_manifest_fingerprint_sha256": manifest_fingerprint if lock_rows else "",
        "blocker_count": blocker_count,
        "blockers": sorted(set(source_blockers + [b for row in lock_rows for b in row["blockers"].split(",") if b])),
        "execution_enabled": False,
        "delete_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Use the generated payload fingerprints in cleanup_execution_operator_approval_intake.csv before approval gate review."
            if status == "cleanup_payload_manifest_lock_ready"
            else "Repair the cleanup approval dossier before collecting operator cleanup execution approvals."
        ),
    }
    return {"summary": summary, "rows": lock_rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Cleanup Payload Manifest Lock",
        "",
        f"- status: `{s['status']}`",
        f"- row_count: `{s['row_count']}`",
        f"- approval_row_count: `{s['approval_row_count']}`",
        f"- protected_not_promoted_row_count: `{s['protected_not_promoted_row_count']}`",
        f"- locked_row_count: `{s['locked_row_count']}`",
        f"- blocked_row_count: `{s['blocked_row_count']}`",
        f"- approval_payload_fingerprint_count: `{s['approval_payload_fingerprint_count']}`",
        f"- payload_manifest_fingerprint_sha256: `{s['payload_manifest_fingerprint_sha256']}`",
        f"- execution_enabled: `{s['execution_enabled']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Rows",
        "",
        "| lock_status | lane | action | size_gb | candidates | fingerprint | path | blockers |",
        "| --- | --- | --- | ---: | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['lock_status']}` | `{row['lane']}` | `{row['recommended_action']}` | "
            f"`{row['size_gb']}` | `{row['candidate_count']}` | "
            f"`{row['payload_fingerprint_sha256'][:12]}` | `{row['path']}` | `{row['blockers']}` |"
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
    parser = argparse.ArgumentParser(description="Build a cleanup payload manifest lock without executing cleanup.")
    parser.add_argument("--dossier-json", default=DEFAULT_DOSSIER_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_cleanup_payload_manifest_lock(
        dossier_packet=_read_json_if_present(args.dossier_json),
        dossier_json=args.dossier_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
