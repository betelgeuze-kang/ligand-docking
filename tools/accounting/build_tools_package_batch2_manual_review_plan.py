#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from tools import build_tools_package_batch2_review_plan as base
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORK_ORDER_JSON = "runs/tools_package_separation_work_order_current.json"
DEFAULT_OUT_JSON = "runs/tools_package_batch2_manual_review_plan_current.json"
DEFAULT_OUT_CSV = "runs/tools_package_batch2_manual_review_plan_current.csv"
DEFAULT_OUT_MD = "runs/tools_package_batch2_manual_review_plan_current.md"
DEFAULT_LIMIT = 25

CLAIM_BOUNDARY = (
    "Tools package batch2 manual review plan only; it selects the next reference-bearing batch_2_review rows for "
    "human-reviewed package migration. It records exact local reference locations and manual rewrite lanes, but does "
    "not move files, rewrite callers or tests, execute selected tools, delete, archive, commit, push, or mutate "
    "external state."
)

CLASS_ORDER = {
    "internal_import_reference": 0,
    "tool_string_reference": 1,
    "test_only_reference": 2,
    "mixed_references": 3,
    "risk_only_review": 4,
}
SKIP_REFERENCE_PREFIXES = {("tools", "bin")}


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


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _reference_total(row: dict[str, Any]) -> int:
    return (
        _int(row.get("tool_reference_count"))
        + _int(row.get("test_reference_count"))
        + _int(row.get("internal_tool_import_count"))
    )


def _candidate_target_exists(tool_path: str, package: str) -> bool:
    return _resolve(base._candidate_target_path(tool_path, package)).exists()


def _source_has_main(tool_path: str) -> bool:
    path = _resolve(tool_path)
    if not path.is_file():
        return False
    try:
        return "def main" in path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False


def _wrapper_strategy(source_has_main: bool) -> str:
    return "cli_main_passthrough_wrapper" if source_has_main else "import_only_compatibility_wrapper"


def _iter_reference_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in base._iter_reference_files(root):
        try:
            parts = path.relative_to(root).parts
        except ValueError:
            parts = path.parts
        if any(parts[: len(prefix)] == prefix for prefix in SKIP_REFERENCE_PREFIXES):
            continue
        if "__pycache__" in parts:
            continue
        files.append(path)
    return files


def _find_internal_import_references(root: Path, tool_path: str) -> list[dict[str, Any]]:
    path = root / tool_path
    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return []
    markers = ("from tools import ", "from tools.", "import tools.", "tools.")
    refs: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not any(marker in line for marker in markers):
            continue
        refs.append(
            {
                "reference_path": tool_path,
                "line_number": line_number,
                "matched_token": "internal_tools_import",
                "line_excerpt": line.strip()[:240],
            }
        )
    return refs


def _manual_lane(row: dict[str, Any], reference_class: str) -> str:
    package = _text(row.get("proposed_package"))
    if package not in base.TARGET_PACKAGES:
        return "package_classification_review"
    if reference_class == "mixed_references":
        return "mixed_reference_rewrite_review"
    if _int(row.get("risk_score")) >= 3:
        return "high_risk_reference_rewrite_review"
    return "single_reference_class_rewrite_review"


def _recommended_action(reference_class: str, manual_lane: str) -> str:
    if manual_lane == "mixed_reference_rewrite_review":
        return "inspect_each_reference_kind_then_move_with_wrapper_and_rewrite_all_recorded_locations"
    if manual_lane == "high_risk_reference_rewrite_review":
        return "confirm_runtime_contract_then_move_with_wrapper_and_rewrite_recorded_locations"
    return base._recommended_action(reference_class)


def build_tools_package_batch2_manual_review_plan(
    *,
    work_order_packet: dict[str, Any],
    work_order_json: str = DEFAULT_WORK_ORDER_JSON,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    summary = base._summary(work_order_packet)
    rows = base._rows(work_order_packet)
    blockers: list[str] = []
    work_order_ready = _text(summary.get("status")) == "tools_package_separation_work_order_ready"
    reference_counts_included = summary.get("reference_counts_included") is True
    if not work_order_ready:
        blockers.append("tools_package_separation_work_order_not_ready")
    if not reference_counts_included:
        blockers.append("reference_counts_not_included")
    if limit <= 0:
        blockers.append("selection_limit_not_positive")

    batch2_rows = [row for row in rows if _text(row.get("migration_batch")) == "batch_2_review"]
    target_batch2_rows = [row for row in batch2_rows if _text(row.get("proposed_package")) in base.TARGET_PACKAGES]
    reference_bearing_rows = [row for row in target_batch2_rows if _reference_total(row) > 0]
    unmigrated_reference_bearing_rows = [
        row
        for row in reference_bearing_rows
        if not _candidate_target_exists(_text(row.get("tool_path")), _text(row.get("proposed_package")))
    ]
    skipped_existing_target_count = len(reference_bearing_rows) - len(unmigrated_reference_bearing_rows)
    class_counts = Counter(base._reference_class(row) for row in batch2_rows)
    target_class_counts = Counter(base._reference_class(row) for row in target_batch2_rows)
    package_counts = Counter(_text(row.get("proposed_package")) for row in batch2_rows)
    risk_counts = Counter(str(_int(row.get("risk_score"))) for row in batch2_rows)
    lane_counts = Counter(_manual_lane(row, base._reference_class(row)) for row in batch2_rows)

    candidate_rows = sorted(
        unmigrated_reference_bearing_rows,
        key=lambda row: (
            CLASS_ORDER.get(base._reference_class(row), 99),
            _int(row.get("risk_score")),
            _text(row.get("proposed_package")),
            _reference_total(row),
            _text(row.get("tool_path")),
        ),
    )

    reference_files = _iter_reference_files(ROOT)
    plan_rows: list[dict[str, Any]] = []
    skipped_missing_reference_count = 0
    scanned_candidate_count = 0
    for row in candidate_rows:
        if len(plan_rows) >= max(limit, 0):
            break
        scanned_candidate_count += 1
        tool_path = _text(row.get("tool_path"))
        package = _text(row.get("proposed_package"))
        reference_class = base._reference_class(row)
        target_path = base._candidate_target_path(tool_path, package)
        refs = base._find_references(ROOT, tool_path, reference_files)
        if not refs and reference_class == "internal_import_reference":
            refs = _find_internal_import_references(ROOT, tool_path)
        if not refs:
            skipped_missing_reference_count += 1
            continue
        manual_lane = _manual_lane(row, reference_class)
        source_has_main = _source_has_main(tool_path)
        plan_rows.append(
            {
                "sequence": len(plan_rows) + 1,
                "tool_path": tool_path,
                "proposed_package": package,
                "target_path": target_path,
                "risk_score": _int(row.get("risk_score")),
                "reference_class": reference_class,
                "manual_lane": manual_lane,
                "tool_reference_count": _int(row.get("tool_reference_count")),
                "test_reference_count": _int(row.get("test_reference_count")),
                "internal_tool_import_count": _int(row.get("internal_tool_import_count")),
                "exact_reference_count": len(refs),
                "reference_locations": ";".join(f"{ref['reference_path']}:{ref['line_number']}" for ref in refs),
                "first_reference_excerpt": refs[0]["line_excerpt"] if refs else "",
                "recommended_action": _recommended_action(reference_class, manual_lane),
                "source_has_main": source_has_main,
                "compatibility_wrapper_strategy": _wrapper_strategy(source_has_main),
                "manual_review_required": True,
                "move_executed": False,
                "caller_or_test_rewrite_executed": False,
                "external_state_mutated": False,
            }
        )
    if work_order_ready and reference_counts_included and not plan_rows:
        blockers.append("no_batch2_manual_review_candidates_with_exact_references")

    ready = bool(plan_rows) and not blockers
    status = "tools_package_batch2_manual_review_plan_ready" if ready else "blocked_tools_package_batch2_manual_review_plan"
    plan_summary = {
        "packet_type": "tools_package_batch2_manual_review_plan",
        "status": status,
        "source_work_order_json": work_order_json,
        "source_work_order_status": _text(summary.get("status")),
        "source_reference_counts_included": reference_counts_included,
        "source_tool_file_count": _int(summary.get("tool_file_count")),
        "batch2_total_count": len(batch2_rows),
        "batch2_target_package_count": len(target_batch2_rows),
        "batch2_reference_bearing_target_count": len(reference_bearing_rows),
        "batch2_unmigrated_reference_bearing_target_count": len(unmigrated_reference_bearing_rows),
        "batch2_package_counts": dict(sorted(package_counts.items())),
        "batch2_risk_counts": dict(sorted(risk_counts.items())),
        "batch2_reference_class_counts": dict(sorted(class_counts.items())),
        "batch2_target_reference_class_counts": dict(sorted(target_class_counts.items())),
        "batch2_manual_lane_counts": dict(sorted(lane_counts.items())),
        "candidate_pool_count": len(candidate_rows),
        "scanned_candidate_count": scanned_candidate_count,
        "selection_limit": limit,
        "selected_count": len(plan_rows),
        "selected_reference_class_counts": dict(sorted(Counter(row["reference_class"] for row in plan_rows).items())),
        "selected_manual_lane_counts": dict(sorted(Counter(row["manual_lane"] for row in plan_rows).items())),
        "selected_source_has_main_count": sum(1 for row in plan_rows if row["source_has_main"]),
        "selected_import_only_wrapper_count": sum(
            1 for row in plan_rows if row["compatibility_wrapper_strategy"] == "import_only_compatibility_wrapper"
        ),
        "skipped_existing_target_candidate_count": skipped_existing_target_count,
        "skipped_missing_reference_candidate_count": skipped_missing_reference_count,
        "blocker_count": len(blockers),
        "blockers": sorted(set(blockers)),
        "manual_review_required": bool(plan_rows),
        "move_executed": False,
        "caller_or_test_rewrite_executed": False,
        "delete_executed": False,
        "archive_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Manually inspect selected reference locations, then create a wrapper-preserving migration slice and rewrite every recorded location."
            if ready
            else "Regenerate the deep work order or inspect package-classification rows before attempting another batch2 migration slice."
        ),
    }
    return {"summary": plan_summary, "rows": plan_rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Tools Package Batch2 Manual Review Plan",
        "",
        f"- status: `{s['status']}`",
        f"- batch2_total_count: `{s['batch2_total_count']}`",
        f"- batch2_target_package_count: `{s['batch2_target_package_count']}`",
        f"- batch2_reference_bearing_target_count: `{s['batch2_reference_bearing_target_count']}`",
        f"- batch2_unmigrated_reference_bearing_target_count: `{s['batch2_unmigrated_reference_bearing_target_count']}`",
        f"- batch2_risk_counts: `{s['batch2_risk_counts']}`",
        f"- batch2_reference_class_counts: `{s['batch2_reference_class_counts']}`",
        f"- batch2_manual_lane_counts: `{s['batch2_manual_lane_counts']}`",
        f"- candidate_pool_count: `{s['candidate_pool_count']}`",
        f"- scanned_candidate_count: `{s['scanned_candidate_count']}`",
        f"- selected_count: `{s['selected_count']}`",
        f"- selected_reference_class_counts: `{s['selected_reference_class_counts']}`",
        f"- selected_manual_lane_counts: `{s['selected_manual_lane_counts']}`",
        f"- selected_source_has_main_count: `{s['selected_source_has_main_count']}`",
        f"- selected_import_only_wrapper_count: `{s['selected_import_only_wrapper_count']}`",
        f"- skipped_existing_target_candidate_count: `{s['skipped_existing_target_candidate_count']}`",
        f"- skipped_missing_reference_candidate_count: `{s['skipped_missing_reference_candidate_count']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- blockers: `{';'.join(s['blockers'])}`",
        f"- move_executed: `{s['move_executed']}`",
        f"- caller_or_test_rewrite_executed: `{s['caller_or_test_rewrite_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Selected Manual Slice",
        "",
        "| seq | tool | package | class | lane | wrapper | refs | target | action |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['sequence']}` | `{row['tool_path']}` | `{row['proposed_package']}` | "
            f"`{row['reference_class']}` | `{row['manual_lane']}` | `{row['compatibility_wrapper_strategy']}` | "
            f"`{row['reference_locations']}` | "
            f"`{row['target_path']}` | `{row['recommended_action']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Select the next manual review slice from tools package batch_2_review rows.")
    parser.add_argument("--work-order-json", default=DEFAULT_WORK_ORDER_JSON)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    work_order = _read_json_if_present(args.work_order_json)
    payload = build_tools_package_batch2_manual_review_plan(
        work_order_packet=work_order,
        work_order_json=args.work_order_json,
        limit=args.limit,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
