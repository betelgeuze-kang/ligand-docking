#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORK_ORDER_JSON = "runs/tools_package_separation_work_order_current.json"
DEFAULT_OUT_JSON = "runs/tools_package_batch3_review_plan_current.json"
DEFAULT_OUT_CSV = "runs/tools_package_batch3_review_plan_current.csv"
DEFAULT_OUT_MD = "runs/tools_package_batch3_review_plan_current.md"

RISK_LANES = (
    ("lane_a_zero_test_low_internal", lambda row: row["risk_score"] <= 6 and row["test_reference_count"] == 0),
    ("lane_b_low_test_reference", lambda row: row["risk_score"] <= 10 and row["test_reference_count"] <= 2),
    ("lane_c_internal_import_heavy", lambda row: row["internal_tool_import_count"] >= 3),
    ("lane_d_high_reference_manual", lambda row: True),
)

CLAIM_BOUNDARY = (
    "Tools package batch3 review plan only; it decomposes batch_3_high_reference rows into review lanes without "
    "moving files or rewriting imports. move_executed remains false."
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


def _assign_lane(row: dict[str, Any]) -> str:
    normalized = {
        "risk_score": _int(row.get("risk_score")),
        "test_reference_count": _int(row.get("test_reference_count")),
        "internal_tool_import_count": _int(row.get("internal_tool_import_count")),
    }
    for lane_id, predicate in RISK_LANES:
        if predicate(normalized):
            return lane_id
    return "lane_d_high_reference_manual"


def _target_path_for(row: dict[str, Any]) -> str:
    package = _text(row.get("proposed_package"))
    tool_path = _text(row.get("tool_path"))
    if not package or package == "other_review" or not tool_path:
        return ""
    return str(Path("tools") / package / Path(tool_path).name)


def _file_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _canonical_module_path(source_path_text: str) -> str:
    text = _file_text(_resolve(source_path_text))
    if not text:
        return ""
    match = re.search(r"canonical module:\s*([A-Za-z0-9_.]+)", text)
    if match:
        module_name = match.group(1).strip().rstrip(".")
    else:
        wrapper_match = re.search(
            r"from\s+(tools\.(?:accounting|cameo|casp17|cleanup|gpcr_replay|product|wetlab)\.[A-Za-z0-9_]+)"
            r"\s+import\s+(?:\*|main\s+as\s+_main)(?:\s|#|$)",
            text,
        )
        if not wrapper_match:
            return ""
        module_name = wrapper_match.group(1).strip().rstrip(".")
    if not module_name.startswith("tools."):
        return ""
    return module_name.replace(".", "/") + ".py"


def build_tools_package_batch3_review_plan(
    *,
    work_order_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    work_order = work_order_packet or _read_json_if_present(DEFAULT_WORK_ORDER_JSON)
    source_rows = _rows(work_order)
    candidates = [row for row in source_rows if _text(row.get("migration_batch")) == "batch_3_high_reference"]
    plan_rows: list[dict[str, Any]] = []
    for row in candidates:
        lane_id = _assign_lane(row)
        raw_target_path = _target_path_for(row)
        canonical_module_path = _canonical_module_path(_text(row.get("tool_path")))
        canonical_module_exists = bool(canonical_module_path and _resolve(canonical_module_path).is_file())
        target_path = raw_target_path or canonical_module_path
        target_module_exists = bool(target_path and _resolve(target_path).is_file())
        has_non_target_canonical = bool(
            canonical_module_exists and raw_target_path and canonical_module_path != raw_target_path
        )
        migration_candidate = bool(
            lane_id == "lane_a_zero_test_low_internal"
            and target_path
            and not target_module_exists
            and not has_non_target_canonical
        )
        plan_rows.append(
            {
                **row,
                "target_path": target_path,
                "target_module_exists": target_module_exists,
                "canonical_module_path": canonical_module_path,
                "canonical_module_exists": canonical_module_exists,
                "has_non_target_canonical_module": has_non_target_canonical,
                "review_lane": lane_id,
                "selected_for_first_slice": migration_candidate,
                "move_executed": False,
                "caller_or_test_rewrite_executed": False,
                "external_state_mutated": False,
            }
        )
    lane_counts = Counter(row["review_lane"] for row in plan_rows)
    raw_first_slice_count = sum(1 for row in plan_rows if row["review_lane"] == "lane_a_zero_test_low_internal")
    first_slice_count = sum(1 for row in plan_rows if row["selected_for_first_slice"])
    skipped_existing_target_count = sum(
        1
        for row in plan_rows
        if row["review_lane"] == "lane_a_zero_test_low_internal" and row["target_module_exists"]
    )
    skipped_existing_canonical_count = sum(
        1
        for row in plan_rows
        if row["review_lane"] == "lane_a_zero_test_low_internal" and row["has_non_target_canonical_module"]
    )
    skipped_unclassified_count = sum(
        1
        for row in plan_rows
        if row["review_lane"] == "lane_a_zero_test_low_internal" and not _text(row.get("target_path"))
    )
    plan_ready = bool(plan_rows)
    status = "tools_package_batch3_review_plan_ready" if plan_ready else "blocked_tools_package_batch3_review_plan"
    summary = {
        "packet_type": "tools_package_batch3_review_plan",
        "status": status,
        "batch3_total_count": len(plan_rows),
        "first_slice_raw_candidate_count": raw_first_slice_count,
        "first_slice_candidate_count": first_slice_count,
        "skipped_existing_target_candidate_count": skipped_existing_target_count,
        "skipped_existing_canonical_candidate_count": skipped_existing_canonical_count,
        "skipped_unclassified_candidate_count": skipped_unclassified_count,
        "review_lane_counts": dict(sorted(lane_counts.items())),
        "plan_ready": plan_ready,
        "move_executed": False,
        "caller_or_test_rewrite_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Move selected lane_a_zero_test_low_internal target-package rows first, then regenerate batch3 plan."
            if plan_ready
            else "Regenerate tools package separation work order before batch3 decomposition."
        ),
    }
    return {"summary": summary, "rows": plan_rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Tools Package Batch3 Review Plan",
        "",
        f"- status: `{s['status']}`",
        f"- batch3_total_count: `{s['batch3_total_count']}`",
        f"- first_slice_raw_candidate_count: `{s['first_slice_raw_candidate_count']}`",
        f"- first_slice_candidate_count: `{s['first_slice_candidate_count']}`",
        f"- skipped_existing_target_candidate_count: `{s['skipped_existing_target_candidate_count']}`",
        f"- skipped_existing_canonical_candidate_count: `{s['skipped_existing_canonical_candidate_count']}`",
        f"- skipped_unclassified_candidate_count: `{s['skipped_unclassified_candidate_count']}`",
        "",
        "## Claim Boundary",
        "",
        s["claim_boundary"],
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build tools package batch3 review plan.")
    parser.add_argument("--work-order-json", default=DEFAULT_WORK_ORDER_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    payload = build_tools_package_batch3_review_plan(
        work_order_packet=_read_json_if_present(args.work_order_json),
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
