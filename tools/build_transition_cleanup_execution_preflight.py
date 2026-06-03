#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORK_ORDER_JSON = "runs/transition_cleanup_work_order_current.json"
DEFAULT_OUT_JSON = "runs/transition_cleanup_execution_preflight_current.json"
DEFAULT_OUT_CSV = "runs/transition_cleanup_execution_preflight_current.csv"
DEFAULT_OUT_MD = "runs/transition_cleanup_execution_preflight_current.md"
CLAIM_BOUNDARY = (
    "Transition cleanup execution preflight only; it validates approval-gated cleanup rows and review-only boundaries. "
    "It does not delete, move, archive, externalize, upload, commit, push, or mutate external state."
)
APPROVAL_TOKENS = {
    "externalize": "APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS",
    "archive": "APPROVE_ARCHIVE_LEGACY_RUNS",
    "delete_candidate": "APPROVE_DELETE_REGENERABLE_LOCAL_ARTIFACTS",
}
DELETE_ALLOWED_LANES = {"build_output", "local_environment"}
REVIEW_ONLY_ACTIONS = {"review_for_stage2_traj_frames", "review_for_ligand_heavy_payload_cleanup"}


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


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


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


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
    except ValueError:
        return False
    return True


def _python_inside(path: Path) -> bool:
    executable = Path(sys.executable).resolve()
    return _is_relative_to(executable, path)


def _row_path(row: dict[str, Any]) -> Path:
    return _resolve(_text(row.get("path")))


def build_execution_preflight(work_order: dict[str, Any]) -> dict[str, Any]:
    summary_in = _summary(work_order)
    rows_in = [row for row in work_order.get("rows", []) or [] if isinstance(row, dict)]
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    if summary_in.get("status") != "transition_cleanup_work_order_ready":
        blockers.append(_blocker("work_order_not_ready", "Transition cleanup work order must be transition_cleanup_work_order_ready."))
    if summary_in.get("delete_enabled") is not False:
        blockers.append(_blocker("work_order_delete_enabled_invalid", "Work order must keep delete_enabled=false before explicit approval."))
    if summary_in.get("action_executed") is not False:
        blockers.append(_blocker("work_order_action_flag_invalid", "Work order must keep action_executed=false."))
    if summary_in.get("external_state_mutated") is not False:
        blockers.append(_blocker("work_order_external_state_invalid", "Work order must keep external_state_mutated=false."))
    if not rows_in:
        blockers.append(_blocker("work_order_rows_missing", "Transition cleanup work order must include rows."))

    approval_rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []
    missing_rows: list[dict[str, Any]] = []
    row_checks: list[dict[str, Any]] = []
    for row in rows_in:
        path_text = _text(row.get("path"))
        path = _row_path(row)
        action = _text(row.get("recommended_action"))
        lane = _text(row.get("lane"))
        status = _text(row.get("work_order_status"))
        token = _text(row.get("approval_token"))
        row_blockers: list[str] = []
        row_warnings: list[str] = []
        exists_now = path.exists()

        if row.get("delete_enabled") is not False:
            row_blockers.append("row_delete_enabled_invalid")
        if row.get("action_executed") is not False:
            row_blockers.append("row_action_executed_invalid")
        if row.get("external_state_mutated") is not False:
            row_blockers.append("row_external_state_invalid")

        if status == "approval_gated":
            approval_rows.append(row)
            expected_token = APPROVAL_TOKENS.get(action)
            if not expected_token:
                row_blockers.append("approval_action_unknown")
            elif token != expected_token:
                row_blockers.append("approval_token_mismatch")
            if row.get("operator_approval_required") is not True:
                row_blockers.append("approval_required_flag_missing")
            if not exists_now:
                row_blockers.append("approval_candidate_missing_refresh_required")
            if path.is_symlink():
                row_blockers.append("approval_candidate_is_symlink")
            if action == "delete_candidate" and lane not in DELETE_ALLOWED_LANES:
                row_blockers.append("delete_candidate_lane_not_allowed")
            if action in {"externalize", "archive"} and path_text.startswith("/mnt/"):
                row_warnings.append("approval_candidate_external_mount")
            if lane == "local_environment" and exists_now and _python_inside(path):
                row_blockers.append("current_python_inside_delete_candidate")
            if action == "delete_candidate" and path_text in {"runs", "casp17", "config", "tools", "tests"}:
                row_blockers.append("delete_candidate_too_broad")
        elif status == "review_only":
            review_rows.append(row)
            if action not in REVIEW_ONLY_ACTIONS:
                row_blockers.append("review_only_action_unexpected")
            if token:
                row_blockers.append("review_only_token_should_be_empty")
            if row.get("operator_approval_required") is not False:
                row_blockers.append("review_only_approval_required_invalid")
        elif status == "missing_noop":
            missing_rows.append(row)
            if exists_now:
                row_blockers.append("missing_noop_path_now_exists_refresh_required")
            if token:
                row_blockers.append("missing_noop_token_should_be_empty")
        else:
            row_blockers.append("work_order_status_unknown")

        for code in row_blockers:
            blockers.append(_blocker("transition_cleanup_row_blocked", f"Row failed preflight: {code}", path=path_text))
        for code in row_warnings:
            warnings.append(_warning(code, "Approval-gated candidate is on an external mount; verify mount stability before action.", path=path_text))
        row_checks.append(
            {
                "path": path_text,
                "resolved_path": str(path),
                "lane": lane,
                "recommended_action": action,
                "work_order_status": status,
                "exists_now": exists_now,
                "is_dir": path.is_dir(),
                "is_symlink": path.is_symlink(),
                "size_bytes": _int(row.get("size_bytes")),
                "size_gb": _float(row.get("size_gb")),
                "approval_token": token,
                "preflight_status": "fail" if row_blockers else "pass",
                "blockers": ",".join(row_blockers),
                "warnings": ",".join(row_warnings),
            }
        )

    expected_approval_count = _int(summary_in.get("approval_gated_count"))
    if expected_approval_count != len(approval_rows):
        blockers.append(_blocker("approval_gated_count_mismatch", f"Summary approval_gated_count={expected_approval_count} but rows={len(approval_rows)}."))
    expected_review_count = _int(summary_in.get("review_only_count"))
    if expected_review_count != len(review_rows):
        blockers.append(_blocker("review_only_count_mismatch", f"Summary review_only_count={expected_review_count} but rows={len(review_rows)}."))

    approval_size_gb = round(sum(_float(row.get("size_bytes")) for row in approval_rows) / (1024**3), 3)
    status = "transition_cleanup_execution_preflight_ready" if not blockers else "blocked_transition_cleanup_execution_preflight"
    summary = {
        "packet_type": "transition_cleanup_execution_preflight",
        "status": status,
        "row_count": len(rows_in),
        "approval_gated_count": len(approval_rows),
        "review_only_count": len(review_rows),
        "missing_noop_count": len(missing_rows),
        "approval_gated_reclaim_size_gb": approval_size_gb,
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "delete_enabled": False,
        "action_executed": False,
        "delete_executed": False,
        "external_state_mutated": False,
        "validated_without_execution": True,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Review this preflight and provide the row-specific approval tokens only for the intended archive/externalize/delete actions."
            if status == "transition_cleanup_execution_preflight_ready"
            else "Refresh the transition cleanup manifest/work order or repair blocked rows before approval."
        ),
    }
    return {"summary": summary, "blockers": blockers, "warnings": warnings, "rows": row_checks}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Transition Cleanup Execution Preflight",
        "",
        f"- status: `{s['status']}`",
        f"- row_count: `{s['row_count']}`",
        f"- approval_gated_count: `{s['approval_gated_count']}`",
        f"- review_only_count: `{s['review_only_count']}`",
        f"- missing_noop_count: `{s['missing_noop_count']}`",
        f"- approval_gated_reclaim_size_gb: `{s['approval_gated_reclaim_size_gb']}`",
        f"- delete_enabled: `{s['delete_enabled']}`",
        f"- action_executed: `{s['action_executed']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        f"- validated_without_execution: `{s['validated_without_execution']}`",
        "",
        "## Rows",
        "",
        "| status | work_order_status | action | exists | size_gb | path | blockers |",
        "| --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['preflight_status']}` | `{row['work_order_status']}` | `{row['recommended_action']}` | "
            f"`{row['exists_now']}` | `{row['size_gb']}` | `{row['path']}` | `{row['blockers']}` |"
        )
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
    parser = argparse.ArgumentParser(description="Preflight transition cleanup work order rows without mutating files.")
    parser.add_argument("--work-order-json", default=DEFAULT_WORK_ORDER_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_execution_preflight(_read_json(args.work_order_json))
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
