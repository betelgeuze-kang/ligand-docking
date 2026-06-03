#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_JSON = "runs/transition_cleanup_manifest_current.json"
DEFAULT_OUT_JSON = "runs/transition_cleanup_work_order_current.json"
DEFAULT_OUT_CSV = "runs/transition_cleanup_work_order_current.csv"
DEFAULT_OUT_MD = "runs/transition_cleanup_work_order_current.md"
CLAIM_BOUNDARY = (
    "Transition cleanup work order only; it records approval-gated archive, externalize, delete, and review actions. "
    "It does not delete, move, archive, upload, commit, push, or mutate external state."
)
ACTION_VERBS = {
    "externalize": "Create checksum/listing snapshot, move or externalize only after operator approval, then verify active tests do not depend on the source path.",
    "archive": "Create cold-storage/archive snapshot only after operator approval, then verify current artifacts still resolve.",
    "delete_candidate": "Delete only regenerable local artifacts after operator approval, then rerun compile and focused tests.",
    "review_for_stage2_traj_frames": "Review trajectory frames as evidence vs stale payload; do not delete from this work order.",
    "review_for_ligand_heavy_payload_cleanup": "Use ligand-heavy cleanup dry-run/work-order path; do not delete from this transition work order.",
}


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


def _bool(value: Any) -> bool:
    return bool(value is True)


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


def _blocker(code: str, reason: str) -> dict[str, str]:
    return {"code": code, "severity": "hard", "reason": reason}


def build_work_order(manifest: dict[str, Any], *, manifest_json: str = DEFAULT_MANIFEST_JSON) -> dict[str, Any]:
    summary = manifest.get("summary") if isinstance(manifest.get("summary"), dict) else {}
    rows = manifest.get("rows") if isinstance(manifest.get("rows"), list) else []
    blockers: list[dict[str, str]] = []
    if summary.get("status") != "transition_cleanup_manifest_dry_run_ready":
        blockers.append(_blocker("manifest_not_ready", "Transition cleanup manifest must be transition_cleanup_manifest_dry_run_ready."))
    if summary.get("delete_executed") is not False:
        blockers.append(_blocker("manifest_delete_flag_invalid", "Transition manifest must report delete_executed=false."))
    if summary.get("external_state_mutated") is not False:
        blockers.append(_blocker("manifest_external_state_invalid", "Transition manifest must report external_state_mutated=false."))
    if not rows:
        blockers.append(_blocker("manifest_rows_missing", "Transition manifest must include artifact rows."))

    work_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        exists = _bool(row.get("exists"))
        action = _text(row.get("recommended_action"))
        approval_required = _bool(row.get("operator_approval_required"))
        phase = _text(row.get("execution_phase"))
        token = _text(row.get("approval_token"))
        status = "approval_gated" if approval_required else "review_only"
        if not exists:
            status = "missing_noop"
        elif approval_required and not token:
            status = "blocked_missing_approval_token"
            blockers.append(_blocker("approval_token_missing", f"Approval token missing for `{row.get('path')}`."))
        work_rows.append(
            {
                "path": _text(row.get("path")),
                "lane": _text(row.get("lane")),
                "recommended_action": action,
                "execution_phase": phase,
                "exists": exists,
                "size_bytes": _int(row.get("size_bytes")),
                "size_gb": _float(row.get("size_gb")),
                "operator_approval_required": approval_required,
                "approval_token": token,
                "work_order_status": status,
                "delete_enabled": False,
                "action_executed": False,
                "external_state_mutated": False,
                "operator_action": ACTION_VERBS.get(action, "Review manually before any action."),
                "postcheck": _text(row.get("postcheck")),
            }
        )

    approval_rows = [row for row in work_rows if row["work_order_status"] == "approval_gated"]
    review_rows = [row for row in work_rows if row["work_order_status"] == "review_only"]
    missing_rows = [row for row in work_rows if row["work_order_status"] == "missing_noop"]
    status = "transition_cleanup_work_order_ready" if not blockers else "blocked_transition_cleanup_work_order"
    work_summary = {
        "packet_type": "transition_cleanup_work_order",
        "status": status,
        "source_manifest_json": manifest_json,
        "row_count": len(work_rows),
        "approval_gated_count": len(approval_rows),
        "review_only_count": len(review_rows),
        "missing_noop_count": len(missing_rows),
        "approval_gated_reclaim_size_bytes": sum(_int(row.get("size_bytes")) for row in approval_rows),
        "approval_gated_reclaim_size_gb": round(sum(_float(row.get("size_bytes")) for row in approval_rows) / (1024**3), 3),
        "review_only_size_gb": round(sum(_float(row.get("size_bytes")) for row in review_rows) / (1024**3), 3),
        "blocker_count": len(blockers),
        "delete_enabled": False,
        "action_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Review approval-gated rows and provide the row-specific approval tokens before any archive/externalize/delete action."
            if status == "transition_cleanup_work_order_ready"
            else "Repair manifest blockers and regenerate the transition cleanup work order."
        ),
    }
    return {"summary": work_summary, "blockers": blockers, "rows": work_rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Transition Cleanup Work Order",
        "",
        f"- status: `{s['status']}`",
        f"- row_count: `{s['row_count']}`",
        f"- approval_gated_count: `{s['approval_gated_count']}`",
        f"- review_only_count: `{s['review_only_count']}`",
        f"- missing_noop_count: `{s['missing_noop_count']}`",
        f"- approval_gated_reclaim_size_gb: `{s['approval_gated_reclaim_size_gb']}`",
        f"- review_only_size_gb: `{s['review_only_size_gb']}`",
        f"- delete_enabled: `{s['delete_enabled']}`",
        f"- action_executed: `{s['action_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Rows",
        "",
        "| status | path | action | size_gb | token |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['work_order_status']}` | `{row['path']}` | `{row['recommended_action']}` | "
            f"`{row['size_gb']}` | `{row['approval_token']}` |"
        )
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
    parser = argparse.ArgumentParser(description="Build an approval-gated transition cleanup work order.")
    parser.add_argument("--manifest-json", default=DEFAULT_MANIFEST_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_work_order(_read_json(args.manifest_json), manifest_json=str(args.manifest_json))
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
