#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BATCH3_PLAN_JSON = "runs/tools_package_batch3_review_plan_current.json"
DEFAULT_OUT_JSON = "runs/tools_package_batch3_lane_decomposition_plan_current.json"
DEFAULT_OUT_CSV = "runs/tools_package_batch3_lane_decomposition_plan_current.csv"
DEFAULT_OUT_MD = "runs/tools_package_batch3_lane_decomposition_plan_current.md"
DEFAULT_SELECTION_LIMIT = 10

BATCH3_REVIEW_LANES = {
    "lane_b_low_test_reference",
    "lane_c_internal_import_heavy",
    "lane_d_high_reference_manual",
}

CLAIM_BOUNDARY = (
    "Tools package batch3 lane decomposition plan only; it separates lane_b/c/d high-reference rows into "
    "candidate migration, existing-wrapper, canonical-owner, package-classification, and manual-review lanes. "
    "It does not move files, rewrite callers or tests, execute selected tools, delete, archive, commit, push, "
    "or mutate external state."
)


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


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _reference_total(row: dict[str, Any]) -> int:
    return (
        _int(row.get("test_reference_count"))
        + _int(row.get("tool_reference_count"))
        + _int(row.get("internal_tool_import_count"))
    )


def _decomposition_lane(row: dict[str, Any]) -> str:
    package = _text(row.get("proposed_package"))
    target_path = _text(row.get("target_path"))
    review_lane = _text(row.get("review_lane"))
    if row.get("has_non_target_canonical_module") is True:
        return "canonical_owner_review"
    if row.get("target_module_exists") is True or (
        row.get("canonical_module_exists") is True and _text(row.get("canonical_module_path"))
    ):
        return "existing_target_wrapper_verification"
    if package == "other_review" or not target_path:
        return "package_classification_required"
    if review_lane == "lane_b_low_test_reference":
        return "lane_b_target_move_candidate"
    if review_lane == "lane_c_internal_import_heavy":
        return "lane_c_reference_rewrite_review"
    return "lane_d_manual_migration_review"


def build_tools_package_batch3_lane_decomposition_plan(
    *,
    batch3_plan_packet: dict[str, Any] | None = None,
    selection_limit: int = DEFAULT_SELECTION_LIMIT,
    batch3_plan_json: str = DEFAULT_BATCH3_PLAN_JSON,
) -> dict[str, Any]:
    batch3_plan = batch3_plan_packet or _read_json_if_present(batch3_plan_json)
    batch3_summary = _summary(batch3_plan)
    source_rows = [
        row for row in _rows(batch3_plan) if _text(row.get("review_lane")) in BATCH3_REVIEW_LANES
    ]
    selected_remaining = max(int(selection_limit), 0)
    plan_rows: list[dict[str, Any]] = []
    for row in source_rows:
        lane = _decomposition_lane(row)
        selected = lane == "lane_b_target_move_candidate" and selected_remaining > 0
        if selected:
            selected_remaining -= 1
        plan_rows.append(
            {
                **row,
                "decomposition_lane": lane,
                "reference_total_count": _reference_total(row),
                "selected_for_next_slice": selected,
                "selection_limit": int(selection_limit),
                "move_executed": False,
                "caller_or_test_rewrite_executed": False,
                "external_state_mutated": False,
            }
        )

    decomposition_counts = Counter(row["decomposition_lane"] for row in plan_rows)
    review_counts = Counter(row["review_lane"] for row in plan_rows)
    package_counts = Counter(row.get("proposed_package") for row in plan_rows)
    selected_count = sum(1 for row in plan_rows if row["selected_for_next_slice"])
    source_ready = _text(batch3_summary.get("status")) == "tools_package_batch3_review_plan_ready"
    plan_ready = source_ready and bool(plan_rows)
    status = (
        "tools_package_batch3_lane_decomposition_plan_ready"
        if plan_ready
        else "blocked_tools_package_batch3_lane_decomposition_plan"
    )
    summary = {
        "packet_type": "tools_package_batch3_lane_decomposition_plan",
        "status": status,
        "source_batch3_plan_json": batch3_plan_json,
        "source_batch3_plan_status": _text(batch3_summary.get("status")),
        "candidate_count": len(plan_rows),
        "selected_for_next_slice_count": selected_count,
        "selection_limit": int(selection_limit),
        "review_lane_counts": dict(sorted(review_counts.items())),
        "decomposition_lane_counts": dict(sorted(decomposition_counts.items())),
        "package_counts": dict(sorted(package_counts.items())),
        "lane_b_target_move_candidate_count": decomposition_counts.get("lane_b_target_move_candidate", 0),
        "existing_target_wrapper_verification_count": decomposition_counts.get(
            "existing_target_wrapper_verification", 0
        ),
        "canonical_owner_review_count": decomposition_counts.get("canonical_owner_review", 0),
        "package_classification_required_count": decomposition_counts.get(
            "package_classification_required", 0
        ),
        "manual_or_reference_review_count": decomposition_counts.get("lane_c_reference_rewrite_review", 0)
        + decomposition_counts.get("lane_d_manual_migration_review", 0),
        "plan_ready": plan_ready,
        "move_executed": False,
        "caller_or_test_rewrite_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Migrate selected lane_b target-package candidates with compatibility wrappers, then regenerate this plan."
            if selected_count
            else "Resolve package-classification/canonical-owner/manual-reference lanes before selecting a move slice."
        ),
    }
    return {"summary": summary, "rows": plan_rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Tools Package Batch3 Lane Decomposition Plan",
        "",
        f"- status: `{s['status']}`",
        f"- candidate_count: `{s['candidate_count']}`",
        f"- selected_for_next_slice_count: `{s['selected_for_next_slice_count']}`",
        f"- decomposition_lane_counts: `{s['decomposition_lane_counts']}`",
        f"- next_required_step: `{s['next_required_step']}`",
        "",
        "## Claim Boundary",
        "",
        s["claim_boundary"],
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build tools package batch3 lane decomposition plan.")
    parser.add_argument("--batch3-plan-json", default=DEFAULT_BATCH3_PLAN_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--selection-limit", type=int, default=DEFAULT_SELECTION_LIMIT)
    args = parser.parse_args(argv)
    payload = build_tools_package_batch3_lane_decomposition_plan(
        batch3_plan_packet=_read_json_if_present(args.batch3_plan_json),
        selection_limit=int(args.selection_limit),
        batch3_plan_json=args.batch3_plan_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
