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
DEFAULT_OUT_JSON = "runs/tools_package_batch2_review_plan_current.json"
DEFAULT_OUT_CSV = "runs/tools_package_batch2_review_plan_current.csv"
DEFAULT_OUT_MD = "runs/tools_package_batch2_review_plan_current.md"

TARGET_PACKAGES = {"product", "cameo", "casp17", "wetlab", "cleanup", "gpcr_replay"}
TARGET_EXTENSIONS = {".py", ".md", ".yml", ".yaml"}
DEFAULT_LIMIT = 25
CLAIM_BOUNDARY = (
    "Tools package batch2 review plan only; it decomposes batch_2_review rows into smaller reference classes and "
    "selects a first reviewed slice with exact local reference locations. It does not move files, rewrite callers or "
    "tests, execute selected tools, delete, archive, commit, push, or mutate external state."
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


def _candidate_target_path(tool_path: str, package: str) -> str:
    return f"tools/{package}/{Path(tool_path).name}"


def _candidate_target_exists(tool_path: str, package: str) -> bool:
    return _resolve(_candidate_target_path(tool_path, package)).exists()


def _tokens_for_tool(tool_path: str) -> list[str]:
    path = Path(tool_path)
    module = path.stem
    return [
        tool_path,
        path.name,
        f"tools.{module}",
        f"import {module}",
        module,
    ]


def _line_has_token(line: str, token: str, bare_module: str) -> bool:
    if not token:
        return False
    if token not in line:
        return False
    if token == f"{bare_module}.py":
        return re.search(rf"(?<![A-Za-z0-9_]){re.escape(token)}(?![A-Za-z0-9_])", line) is not None
    if token in {bare_module, f"tools.{bare_module}", f"import {bare_module}"}:
        return re.search(rf"(?<![A-Za-z0-9_]){re.escape(token)}(?![A-Za-z0-9_])", line) is not None
    return True


def _iter_reference_files(root: Path) -> list[Path]:
    roots = [root / "tools", root / "tests", root / ".github", root / "deploy"]
    files: list[Path] = []
    for base in roots:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix.lower() in TARGET_EXTENSIONS:
                files.append(path)
    return sorted(files)


def _find_references(root: Path, tool_path: str, reference_files: list[Path]) -> list[dict[str, Any]]:
    tokens = _tokens_for_tool(tool_path)
    bare_module = Path(tool_path).stem
    source = (root / tool_path).resolve()
    refs: list[dict[str, Any]] = []
    for path in reference_files:
        resolved = path.resolve()
        if resolved == source:
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, start=1):
            matched = []
            for token in tokens:
                if not _line_has_token(line, token, bare_module):
                    continue
                if token == bare_module:
                    window = "\n".join(lines[max(0, line_number - 3) : min(len(lines), line_number + 2)])
                    if "import" not in window and "tools/" not in window:
                        continue
                matched.append(token)
            if not matched:
                continue
            refs.append(
                {
                    "reference_path": str(path.relative_to(root)),
                    "line_number": line_number,
                    "matched_token": matched[0],
                    "line_excerpt": line.strip()[:240],
                }
            )
    return refs


def _reference_class(row: dict[str, Any]) -> str:
    tool_refs = _int(row.get("tool_reference_count"))
    test_refs = _int(row.get("test_reference_count"))
    imports = _int(row.get("internal_tool_import_count"))
    active = sum(1 for value in (tool_refs, test_refs, imports) if value > 0)
    if active > 1:
        return "mixed_references"
    if test_refs > 0:
        return "test_only_reference"
    if tool_refs > 0:
        return "tool_string_reference"
    if imports > 0:
        return "internal_import_reference"
    return "risk_only_review"


def _recommended_action(reference_class: str) -> str:
    if reference_class == "test_only_reference":
        return "move_with_wrapper_then_update_tests_or_keep_wrapper_contract"
    if reference_class == "tool_string_reference":
        return "move_with_wrapper_then_rewrite_recorded_tool_callers"
    if reference_class == "internal_import_reference":
        return "move_with_wrapper_then_rewrite_internal_imports"
    if reference_class == "mixed_references":
        return "split_into_manual_subtasks_before_move"
    return "manual_review_before_move"


def build_tools_package_batch2_review_plan(
    *,
    work_order_packet: dict[str, Any],
    work_order_json: str = DEFAULT_WORK_ORDER_JSON,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    summary = _summary(work_order_packet)
    rows = _rows(work_order_packet)
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
    target_batch2_rows = [row for row in batch2_rows if _text(row.get("proposed_package")) in TARGET_PACKAGES]
    class_counts = Counter(_reference_class(row) for row in batch2_rows)
    package_counts = Counter(_text(row.get("proposed_package")) for row in batch2_rows)
    risk_counts = Counter(str(_int(row.get("risk_score"))) for row in batch2_rows)
    first_slice_raw_pool = [
        row
        for row in target_batch2_rows
        if _int(row.get("risk_score")) == 1 and _reference_class(row) in {"test_only_reference", "tool_string_reference", "internal_import_reference"}
    ]
    skipped_existing_target_count = sum(
        1 for row in first_slice_raw_pool if _candidate_target_exists(_text(row.get("tool_path")), _text(row.get("proposed_package")))
    )
    first_slice_pool = [
        row
        for row in first_slice_raw_pool
        if not _candidate_target_exists(_text(row.get("tool_path")), _text(row.get("proposed_package")))
    ]
    first_slice_pool = sorted(
        first_slice_pool,
        key=lambda row: (
            _reference_class(row),
            _text(row.get("proposed_package")),
            _text(row.get("tool_path")),
        ),
    )
    reference_files = _iter_reference_files(ROOT)
    plan_rows: list[dict[str, Any]] = []
    missing_reference_count = 0
    for row in first_slice_pool:
        if len(plan_rows) >= max(limit, 0):
            break
        tool_path = _text(row.get("tool_path"))
        package = _text(row.get("proposed_package"))
        target_path = _candidate_target_path(tool_path, package)
        reference_class = _reference_class(row)
        refs = _find_references(ROOT, tool_path, reference_files)
        if not refs:
            missing_reference_count += 1
            continue
        plan_rows.append(
            {
                "sequence": len(plan_rows) + 1,
                "tool_path": tool_path,
                "proposed_package": package,
                "target_path": target_path,
                "risk_score": _int(row.get("risk_score")),
                "reference_class": reference_class,
                "tool_reference_count": _int(row.get("tool_reference_count")),
                "test_reference_count": _int(row.get("test_reference_count")),
                "internal_tool_import_count": _int(row.get("internal_tool_import_count")),
                "exact_reference_count": len(refs),
                "reference_locations": ";".join(f"{ref['reference_path']}:{ref['line_number']}" for ref in refs),
                "first_reference_excerpt": refs[0]["line_excerpt"] if refs else "",
                "recommended_action": _recommended_action(reference_class),
                "move_executed": False,
                "caller_or_test_rewrite_executed": False,
                "external_state_mutated": False,
            }
        )
    if work_order_ready and reference_counts_included and not plan_rows:
        blockers.append("no_batch2_first_slice_candidates_with_exact_references")

    ready = bool(plan_rows) and not blockers
    status = "tools_package_batch2_review_plan_ready" if ready else "blocked_tools_package_batch2_review_plan"
    plan_summary = {
        "packet_type": "tools_package_batch2_review_plan",
        "status": status,
        "source_work_order_json": work_order_json,
        "source_work_order_status": _text(summary.get("status")),
        "source_reference_counts_included": reference_counts_included,
        "source_tool_file_count": _int(summary.get("tool_file_count")),
        "batch2_total_count": len(batch2_rows),
        "batch2_target_package_count": len(target_batch2_rows),
        "batch2_package_counts": dict(sorted(package_counts.items())),
        "batch2_risk_counts": dict(sorted(risk_counts.items())),
        "batch2_reference_class_counts": dict(sorted(class_counts.items())),
        "first_slice_raw_candidate_count": len(first_slice_raw_pool),
        "first_slice_candidate_count": len(first_slice_pool),
        "selection_limit": limit,
        "selected_count": len(plan_rows),
        "missing_reference_location_count": 0,
        "skipped_missing_reference_candidate_count": missing_reference_count,
        "skipped_existing_target_candidate_count": skipped_existing_target_count,
        "blocker_count": len(blockers),
        "blockers": sorted(set(blockers)),
        "move_executed": False,
        "caller_or_test_rewrite_executed": False,
        "delete_executed": False,
        "archive_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Move the selected batch2 slice with wrappers, then rewrite the exact recorded caller/test/import references in a tested refactor."
            if ready
            else "Review batch2 rows manually or regenerate the deep work order before selecting a batch2 slice."
        ),
    }
    return {"summary": plan_summary, "rows": plan_rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Tools Package Batch2 Review Plan",
        "",
        f"- status: `{s['status']}`",
        f"- batch2_total_count: `{s['batch2_total_count']}`",
        f"- batch2_target_package_count: `{s['batch2_target_package_count']}`",
        f"- batch2_risk_counts: `{s['batch2_risk_counts']}`",
        f"- batch2_reference_class_counts: `{s['batch2_reference_class_counts']}`",
        f"- first_slice_raw_candidate_count: `{s['first_slice_raw_candidate_count']}`",
        f"- first_slice_candidate_count: `{s['first_slice_candidate_count']}`",
        f"- selected_count: `{s['selected_count']}`",
        f"- missing_reference_location_count: `{s['missing_reference_location_count']}`",
        f"- skipped_existing_target_candidate_count: `{s['skipped_existing_target_candidate_count']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- blockers: `{';'.join(s['blockers'])}`",
        f"- move_executed: `{s['move_executed']}`",
        f"- caller_or_test_rewrite_executed: `{s['caller_or_test_rewrite_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Selected Slice",
        "",
        "| seq | tool | package | class | refs | target | action |",
        "| ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['sequence']}` | `{row['tool_path']}` | `{row['proposed_package']}` | "
            f"`{row['reference_class']}` | `{row['reference_locations']}` | `{row['target_path']}` | "
            f"`{row['recommended_action']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Decompose tools package batch_2_review rows into a first reviewed slice.")
    parser.add_argument("--work-order-json", default=DEFAULT_WORK_ORDER_JSON)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    work_order = _read_json_if_present(args.work_order_json)
    payload = build_tools_package_batch2_review_plan(
        work_order_packet=work_order,
        work_order_json=args.work_order_json,
        limit=args.limit,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
