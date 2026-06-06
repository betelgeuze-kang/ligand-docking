#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORK_ORDER_JSON = "runs/tools_package_separation_work_order_current.json"
DEFAULT_OUT_JSON = "runs/tools_package_reference_review_current.json"
DEFAULT_OUT_CSV = "runs/tools_package_reference_review_current.csv"
DEFAULT_OUT_MD = "runs/tools_package_reference_review_current.md"

TARGET_EXTENSIONS = {".py", ".md", ".yml", ".yaml"}
CLAIM_BOUNDARY = (
    "Tools package reference review only; it resolves nonzero-reference batch_1 tool rows into exact local reference "
    "locations and proposes wrapper-preserving or caller-rewrite actions for a later refactor. It does not move files, "
    "rewrite callers, delete, archive, execute referenced tools, commit, push, or mutate external state."
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


def _tokens_for_tool(tool_path: str) -> list[str]:
    path = Path(tool_path)
    module = path.stem
    return [
        tool_path,
        path.name,
        f"tools.{module}",
        f"import {module}",
    ]


def _iter_reference_files(root: Path) -> list[Path]:
    roots = [root / "tools", root / "tests", root / "docs", root / ".github", root / "deploy"]
    files: list[Path] = []
    for base in roots:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix.lower() in TARGET_EXTENSIONS:
                files.append(path)
    return sorted(files)


def _find_references(root: Path, tool_path: str) -> list[dict[str, Any]]:
    tokens = _tokens_for_tool(tool_path)
    source = (root / tool_path).resolve()
    refs: list[dict[str, Any]] = []
    for path in _iter_reference_files(root):
        resolved = path.resolve()
        if resolved == source:
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, start=1):
            matched = [token for token in tokens if token and token in line]
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


def build_tools_package_reference_review(
    *,
    work_order_packet: dict[str, Any],
    work_order_json: str = DEFAULT_WORK_ORDER_JSON,
) -> dict[str, Any]:
    summary = _summary(work_order_packet)
    work_order_ready = _text(summary.get("status")) == "tools_package_separation_work_order_ready"
    reference_counts_included = summary.get("reference_counts_included") is True
    blockers: list[str] = []
    if not work_order_ready:
        blockers.append("tools_package_separation_work_order_not_ready")
    if not reference_counts_included:
        blockers.append("reference_counts_not_included")

    candidate_rows = [
        row
        for row in _rows(work_order_packet)
        if _text(row.get("migration_batch")) == "batch_1_low_reference"
        and (
            _int(row.get("tool_reference_count")) > 0
            or _int(row.get("test_reference_count")) > 0
            or _int(row.get("internal_tool_import_count")) > 0
        )
    ]
    review_rows: list[dict[str, Any]] = []
    missing_reference_count = 0
    for row in sorted(candidate_rows, key=lambda item: (_text(item.get("proposed_package")), _text(item.get("tool_path")))):
        tool_path = _text(row.get("tool_path"))
        package = _text(row.get("proposed_package"))
        target_path = _candidate_target_path(tool_path, package)
        refs = _find_references(ROOT, tool_path)
        if not refs:
            missing_reference_count += 1
        action = (
            "move_with_wrapper_then_rewrite_recorded_callers"
            if refs
            else "rerun_reference_counter_or_review_generated_string_reference"
        )
        review_rows.append(
            {
                "tool_path": tool_path,
                "proposed_package": package,
                "target_path": target_path,
                "risk_score": _int(row.get("risk_score")),
                "tool_reference_count": _int(row.get("tool_reference_count")),
                "test_reference_count": _int(row.get("test_reference_count")),
                "internal_tool_import_count": _int(row.get("internal_tool_import_count")),
                "exact_reference_count": len(refs),
                "reference_locations": ";".join(f"{ref['reference_path']}:{ref['line_number']}" for ref in refs),
                "first_reference_excerpt": refs[0]["line_excerpt"] if refs else "",
                "recommended_action": action,
                "move_executed": False,
                "caller_rewrite_executed": False,
                "external_state_mutated": False,
            }
        )

    if work_order_ready and reference_counts_included and not candidate_rows:
        blockers.append("no_referenced_batch_1_rows")
    if missing_reference_count:
        blockers.append("exact_reference_location_missing")

    status = "tools_package_reference_review_ready" if review_rows and not blockers else "blocked_tools_package_reference_review"
    review_summary = {
        "packet_type": "tools_package_reference_review",
        "status": status,
        "source_work_order_json": work_order_json,
        "source_work_order_status": _text(summary.get("status")),
        "source_reference_counts_included": reference_counts_included,
        "review_candidate_count": len(candidate_rows),
        "exact_reference_resolved_count": sum(1 for row in review_rows if row["exact_reference_count"] > 0),
        "missing_reference_location_count": missing_reference_count,
        "blocker_count": len(blockers),
        "blockers": sorted(set(blockers)),
        "move_executed": False,
        "caller_rewrite_executed": False,
        "delete_executed": False,
        "archive_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Move these referenced batch_1 tools with top-level wrappers, then rewrite the recorded caller lines in a separate tested refactor."
            if status == "tools_package_reference_review_ready"
            else "Regenerate the deep work order or inspect unresolved reference counts before moving referenced batch_1 tools."
        ),
    }
    return {"summary": review_summary, "rows": review_rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Tools Package Reference Review",
        "",
        f"- status: `{s['status']}`",
        f"- review_candidate_count: `{s['review_candidate_count']}`",
        f"- exact_reference_resolved_count: `{s['exact_reference_resolved_count']}`",
        f"- missing_reference_location_count: `{s['missing_reference_location_count']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- blockers: `{';'.join(s['blockers'])}`",
        f"- move_executed: `{s['move_executed']}`",
        f"- caller_rewrite_executed: `{s['caller_rewrite_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Referenced Batch 1 Rows",
        "",
        "| tool | package | target | exact refs | locations | action |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['tool_path']}` | `{row['proposed_package']}` | `{row['target_path']}` | "
            f"`{row['exact_reference_count']}` | `{row['reference_locations']}` | `{row['recommended_action']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve referenced batch_1 tools into exact caller locations.")
    parser.add_argument("--work-order-json", default=DEFAULT_WORK_ORDER_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    work_order = _read_json_if_present(args.work_order_json)
    payload = build_tools_package_reference_review(work_order_packet=work_order, work_order_json=args.work_order_json)
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
