#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORK_ORDER_JSON = "runs/tools_package_separation_work_order_current.json"
DEFAULT_OUT_JSON = "runs/tools_package_migration_plan_current.json"
DEFAULT_OUT_CSV = "runs/tools_package_migration_plan_current.csv"
DEFAULT_OUT_MD = "runs/tools_package_migration_plan_current.md"

TARGET_PACKAGES = {"product", "cameo", "casp17", "wetlab", "cleanup", "gpcr_replay"}
DEFAULT_LIMIT = 50
CLAIM_BOUNDARY = (
    "Tools package migration plan only; it selects low-reference candidate tools from the package separation work "
    "order and proposes destination paths before an approved refactor. It does not create directories, move files, "
    "rewrite imports, delete, archive, commit, push, or mutate external state."
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


def _import_rewrite_hint(tool_path: str, target_path: str) -> str:
    source_module = Path(tool_path).stem
    package = Path(target_path).parent.name
    target_module = Path(target_path).stem
    return f"tools.{source_module} -> tools.{package}.{target_module}"


def build_tools_package_migration_plan(
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

    candidate_pool = [
        row
        for row in rows
        if _text(row.get("migration_batch")) == "batch_1_low_reference"
        and _text(row.get("proposed_package")) in TARGET_PACKAGES
        and _int(row.get("risk_score")) == 0
        and _int(row.get("test_reference_count")) == 0
        and _int(row.get("tool_reference_count")) == 0
        and _int(row.get("internal_tool_import_count")) == 0
    ]
    candidate_pool = sorted(candidate_pool, key=lambda row: (_text(row.get("proposed_package")), _text(row.get("tool_path"))))
    selected_source_rows = candidate_pool[: max(limit, 0)]
    if work_order_ready and reference_counts_included and not selected_source_rows:
        blockers.append("no_low_reference_candidates")

    plan_rows: list[dict[str, Any]] = []
    for index, row in enumerate(selected_source_rows, start=1):
        source_path = _text(row.get("tool_path"))
        package = _text(row.get("proposed_package"))
        target_path = _candidate_target_path(source_path, package)
        plan_rows.append(
            {
                "sequence": index,
                "source_path": source_path,
                "proposed_package": package,
                "target_path": target_path,
                "matched_keyword": _text(row.get("matched_keyword")),
                "risk_score": _int(row.get("risk_score")),
                "test_reference_count": _int(row.get("test_reference_count")),
                "tool_reference_count": _int(row.get("tool_reference_count")),
                "internal_tool_import_count": _int(row.get("internal_tool_import_count")),
                "has_argparse_cli": row.get("has_argparse_cli") is True,
                "import_rewrite_hint": _import_rewrite_hint(source_path, target_path),
                "recommended_verification": "python3 -m pytest -q tests/unit/test_build_tools_package_migration_plan.py",
                "directory_created": False,
                "move_executed": False,
                "import_rewrite_executed": False,
                "external_state_mutated": False,
            }
        )

    package_counts = Counter(row["proposed_package"] for row in plan_rows)
    ready = not blockers and bool(plan_rows)
    plan_status = "tools_package_migration_plan_ready" if ready else "blocked_tools_package_migration_plan"
    plan_summary = {
        "packet_type": "tools_package_migration_plan",
        "status": plan_status,
        "source_work_order_json": work_order_json,
        "source_work_order_status": _text(summary.get("status")),
        "source_reference_counts_included": reference_counts_included,
        "source_tool_file_count": _int(summary.get("tool_file_count")),
        "candidate_pool_count": len(candidate_pool),
        "selection_limit": limit,
        "selected_count": len(plan_rows),
        "selected_package_counts": dict(sorted(package_counts.items())),
        "blocker_count": len(blockers),
        "blockers": sorted(set(blockers)),
        "directory_created": False,
        "move_executed": False,
        "import_rewrite_executed": False,
        "delete_executed": False,
        "archive_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Run an approved refactor against this selected batch, creating package directories and rewriting imports with tests."
            if ready
            else (
                "Review remaining batch_1 rows with nonzero tool references or batch_2 rows manually; no zero-reference target-package batch remains."
                if reference_counts_included and work_order_ready
                else "Regenerate the tools package separation work order with --include-reference-counts before selecting a migration batch."
            )
        ),
    }
    return {"summary": plan_summary, "rows": plan_rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Tools Package Migration Plan",
        "",
        f"- status: `{s['status']}`",
        f"- source_reference_counts_included: `{s['source_reference_counts_included']}`",
        f"- candidate_pool_count: `{s['candidate_pool_count']}`",
        f"- selection_limit: `{s['selection_limit']}`",
        f"- selected_count: `{s['selected_count']}`",
        f"- selected_package_counts: `{s['selected_package_counts']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- blockers: `{';'.join(s['blockers'])}`",
        f"- move_executed: `{s['move_executed']}`",
        f"- import_rewrite_executed: `{s['import_rewrite_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Selected Batch",
        "",
        "| seq | source | target | package | risk | import rewrite hint |",
        "| ---: | --- | --- | --- | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['sequence']}` | `{row['source_path']}` | `{row['target_path']}` | "
            f"`{row['proposed_package']}` | `{row['risk_score']}` | `{row['import_rewrite_hint']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a read-only tools package migration plan.")
    parser.add_argument("--work-order-json", default=DEFAULT_WORK_ORDER_JSON)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    work_order = _read_json_if_present(args.work_order_json)
    payload = build_tools_package_migration_plan(
        work_order_packet=work_order,
        work_order_json=args.work_order_json,
        limit=args.limit,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
