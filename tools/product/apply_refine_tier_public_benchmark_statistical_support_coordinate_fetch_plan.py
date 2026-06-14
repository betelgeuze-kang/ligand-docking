#!/usr/bin/env python3
"""Apply or preview approved R9 statistical-support coordinate fetch rows."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.build_refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan import (
    DEFAULT_OUT_JSON as DEFAULT_FETCH_PLAN_JSON,
)
from tools.product.fetch_public_benchmark_native_structure import (
    APPROVAL_TOKEN,
    _download,
    _sha256,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = (
    "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_apply_current.json"
)
DEFAULT_OUT_CSV = "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_apply_current.csv"
DEFAULT_OUT_MD = "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_apply_current.md"

CLAIM_BOUNDARY = (
    "Refine-tier public-benchmark statistical-support coordinate fetch apply only; preview mode validates "
    "local fetch-plan rows, and execute mode can download public RCSB coordinate files into local staging "
    "paths only when the operator approval token is present. It does not run docking or MD, compute metrics, "
    "write canonical intake, approve receipts, promote claims, upload, email, delete, commit, push, or mutate "
    "external services."
)


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _display(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = _resolve(path_like, root=root)
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> tuple[dict[str, Any], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return {}, False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, True
    return (payload if isinstance(payload, dict) else {}), True


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else payload


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _approval_token_accepted(token: str) -> bool:
    return _text(token) == APPROVAL_TOKEN


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _row_preflight(row: dict[str, Any], *, root: Path) -> tuple[list[str], Path]:
    blockers: list[str] = []
    source_url = _text(row.get("source_url_primary"))
    destination = _resolve(row.get("staging_destination_path") or "", root=root)
    if not _text(row.get("target_id")):
        blockers.append("target_id_missing")
    if not source_url:
        blockers.append("source_url_primary_missing")
    if not _text(row.get("staging_destination_path")):
        blockers.append("staging_destination_path_missing")
    if destination.exists() and not destination.is_file():
        blockers.append("staging_destination_not_file")
    if _bool(row.get("external_state_mutated")):
        blockers.append("source_row_external_state_mutated")
    if _bool(row.get("canonical_intake_promotion_allowed")):
        blockers.append("source_row_canonical_intake_promotion_allowed")
    return blockers, destination


def _apply_row(
    row: dict[str, Any],
    *,
    mode: str,
    root: Path,
    approval_token: str,
    timeout_seconds: int,
    overwrite: bool,
) -> dict[str, Any]:
    preflight_blockers, destination = _row_preflight(row, root=root)
    token_accepted = _approval_token_accepted(approval_token)
    execution_requested = mode == "execute"
    blockers = list(preflight_blockers)
    if execution_requested and not token_accepted:
        blockers.append("approval_token_missing_or_invalid")
    before_present = destination.is_file()
    download_executed = False
    fetch_status = "preview_ready"
    error = ""
    if blockers:
        fetch_status = "blocked"
    elif execution_requested:
        try:
            download_executed, fetch_status = _download(
                _text(row.get("source_url_primary")),
                destination,
                timeout_seconds=timeout_seconds,
                overwrite=overwrite,
            )
        except Exception as exc:  # pragma: no cover - network/runtime dependent
            blockers.append("download_failed")
            fetch_status = "failed"
            error = str(exc)
    after_present = destination.is_file()
    status = "fetch_apply_ready"
    if blockers:
        status = "blocked_fetch_apply"
    elif execution_requested and download_executed:
        status = "downloaded"
    elif execution_requested and after_present:
        status = "already_present"
    return {
        "candidate_queue_id": _text(row.get("candidate_queue_id")),
        "expansion_slot_id": _text(row.get("expansion_slot_id")),
        "suggested_work_order_id": _text(row.get("suggested_work_order_id")),
        "target_id": _text(row.get("target_id")).lower(),
        "pose_id": _text(row.get("pose_id")),
        "required_split": _text(row.get("required_split")),
        "suggested_split": _text(row.get("suggested_split")),
        "source_url_primary": _text(row.get("source_url_primary")),
        "staging_destination_path": _display(destination, root=root),
        "destination_present_before": before_present,
        "destination_present_after": after_present,
        "destination_size_bytes": destination.stat().st_size if after_present else 0,
        "destination_sha256": _sha256(destination) if after_present else "",
        "mode": mode,
        "execution_requested": execution_requested,
        "approval_token_required": APPROVAL_TOKEN,
        "approval_token_present": bool(_text(approval_token)),
        "approval_token_accepted": token_accepted,
        "preflight_pass": not preflight_blockers,
        "download_executed": download_executed,
        "fetch_status": fetch_status,
        "row_status": status,
        "row_blockers": ";".join(blockers),
        "download_error": error,
        "post_fetch_validation_command": _text(row.get("post_fetch_validation_command")),
        "canonical_intake_promotion_allowed": False,
        "external_state_mutated": False,
    }


def apply_refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan(
    *,
    fetch_plan_json: str | Path = DEFAULT_FETCH_PLAN_JSON,
    mode: str = "preview",
    approval_token: str = "",
    timeout_seconds: int = 30,
    overwrite: bool = False,
    root: Path = ROOT,
) -> dict[str, Any]:
    plan_payload, plan_present = _read_json(fetch_plan_json, root=root)
    plan_summary = _summary(plan_payload)
    plan_rows = _rows(plan_payload)
    rows = [
        _apply_row(
            row,
            mode=mode,
            root=root,
            approval_token=approval_token,
            timeout_seconds=timeout_seconds,
            overwrite=overwrite,
        )
        for row in plan_rows
    ]
    blockers: list[str] = []
    if not plan_present:
        blockers.append("coordinate_fetch_plan_missing")
    if plan_summary.get("status") != "refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan_ready":
        blockers.append("coordinate_fetch_plan_not_ready")
    if mode not in {"preview", "execute"}:
        blockers.append("invalid_mode")
    execution_requested = mode == "execute"
    token_accepted = _approval_token_accepted(approval_token)
    blocked_row_count = sum(1 for row in rows if _text(row.get("row_status")).startswith("blocked"))
    preflight_pass_count = sum(1 for row in rows if row["preflight_pass"] is True)
    downloaded_count = sum(1 for row in rows if row["download_executed"] is True)
    present_after_count = sum(1 for row in rows if row["destination_present_after"] is True)
    preview_ready_count = sum(1 for row in rows if row["row_status"] == "fetch_apply_ready")
    live_apply_ready = bool(plan_present and not blockers and execution_requested and token_accepted)
    status = (
        "refine_tier_public_benchmark_statistical_support_coordinate_fetch_apply_ready"
        if live_apply_ready and blocked_row_count == 0
        else "blocked_refine_tier_public_benchmark_statistical_support_coordinate_fetch_apply"
    )
    summary = {
        "packet_type": "refine_tier_public_benchmark_statistical_support_coordinate_fetch_apply",
        "status": status,
        "coordinate_fetch_apply_preview_ready": bool(
            plan_present and not blockers and mode == "preview" and preflight_pass_count == len(rows) and rows
        ),
        "coordinate_fetch_apply_live_ready": live_apply_ready,
        "coordinate_fetch_plan": _display(fetch_plan_json, root=root),
        "coordinate_fetch_plan_present": plan_present,
        "coordinate_fetch_plan_ready": bool(
            plan_summary.get("status")
            == "refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan_ready"
        ),
        "mode": mode,
        "execution_requested": execution_requested,
        "approval_token_required": APPROVAL_TOKEN,
        "approval_token_present": bool(_text(approval_token)),
        "approval_token_accepted": token_accepted,
        "coordinate_fetch_apply_row_count": len(rows),
        "coordinate_fetch_apply_preflight_pass_row_count": preflight_pass_count,
        "coordinate_fetch_apply_preview_ready_row_count": preview_ready_count,
        "coordinate_fetch_apply_blocked_row_count": blocked_row_count,
        "coordinate_fetch_apply_downloaded_row_count": downloaded_count,
        "coordinate_fetch_apply_destination_present_after_row_count": present_after_count,
        "coordinate_fetch_apply_ready_for_validation_row_count": present_after_count,
        "download_executed": downloaded_count > 0,
        "canonical_intake_promotion_allowed": False,
        "external_state_mutated": False,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Set APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD as the approval token and rerun "
            "with --mode execute, then rebuild coordinate intake validation."
            if mode == "preview"
            else "Rebuild coordinate intake validation and then metric source materialization."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    summary = payload["summary"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "# R9 Statistical Support Coordinate Fetch Apply",
                "",
                f"- status: `{summary['status']}`",
                f"- mode: `{summary['mode']}`",
                f"- coordinate_fetch_apply_row_count: `{summary['coordinate_fetch_apply_row_count']}`",
                f"- coordinate_fetch_apply_preflight_pass_row_count: "
                f"`{summary['coordinate_fetch_apply_preflight_pass_row_count']}`",
                f"- coordinate_fetch_apply_blocked_row_count: "
                f"`{summary['coordinate_fetch_apply_blocked_row_count']}`",
                f"- coordinate_fetch_apply_downloaded_row_count: "
                f"`{summary['coordinate_fetch_apply_downloaded_row_count']}`",
                f"- approval_token_accepted: `{summary['approval_token_accepted']}`",
                "",
                "## Claim Boundary",
                "",
                summary["claim_boundary"],
                "",
                "## Next Required Step",
                "",
                summary["next_required_step"],
                "",
            ]
        ),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(
        description="Preview or execute approved R9 statistical-support public coordinate fetch rows."
    )
    parser.add_argument("--fetch-plan-json", default=DEFAULT_FETCH_PLAN_JSON)
    parser.add_argument("--mode", choices=["preview", "execute"], default="preview")
    parser.add_argument("--approval-token", default="")
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--overwrite", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    payload = apply_refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan(
        fetch_plan_json=args.fetch_plan_json,
        mode=args.mode,
        approval_token=args.approval_token,
        timeout_seconds=args.timeout_seconds,
        overwrite=args.overwrite,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_md(args.out_md, payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
