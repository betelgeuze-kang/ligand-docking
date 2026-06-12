#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import py_compile
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BATCH3_PLAN_JSON = "runs/tools_package_batch3_review_plan_current.json"
DEFAULT_OUT_JSON = "runs/tools_package_batch3_migration_receipt_current.json"
DEFAULT_OUT_CSV = "runs/tools_package_batch3_migration_receipt_current.csv"
DEFAULT_OUT_MD = "runs/tools_package_batch3_migration_receipt_current.md"

CLAIM_BOUNDARY = (
    "Tools package batch3 migration receipt only; it verifies selected batch3 rows have been moved to "
    "their package target modules while top-level compatibility wrappers remain syntax-valid. It does not move "
    "additional files, delete, archive, commit, push, execute selected tools, or mutate external state."
)

READY_SOURCE_STATUSES = {
    "tools_package_batch3_review_plan_ready",
    "tools_package_batch3_lane_decomposition_plan_ready",
    "tools_package_batch3_package_classification_plan_ready",
    "tools_package_batch3_other_review_classification_plan_ready",
}


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


def _compile_ok(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        py_compile.compile(str(path), doraise=True)
    except py_compile.PyCompileError:
        return False
    return True


def _module_path(path_text: str) -> str:
    return path_text.removesuffix(".py").replace("/", ".")


def _wrapper_import_line(target_path: str) -> str:
    return f"from {_module_path(target_path)} import *"


def _wrapper_main_line(target_path: str) -> str:
    return f"from {_module_path(target_path)} import main as _main"


def _target_has_main(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        return "def main" in path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False


def _selected_rows(batch3_plan_packet: dict[str, Any]) -> list[dict[str, Any]]:
    source_status = _text(_summary(batch3_plan_packet).get("status"))
    if source_status in {
        "tools_package_batch3_package_classification_plan_ready",
        "tools_package_batch3_other_review_classification_plan_ready",
    }:
        return [
            row
            for row in _rows(batch3_plan_packet)
            if _text(row.get("target_path")) and _text(row.get("classification_status")) == "classified"
        ]
    return [
        row
        for row in _rows(batch3_plan_packet)
        if row.get("selected_for_first_slice") is True or row.get("selected_for_next_slice") is True
    ]


def build_tools_package_batch3_migration_receipt(
    *,
    batch3_plan_packet: dict[str, Any],
    batch3_plan_json: str = DEFAULT_BATCH3_PLAN_JSON,
) -> dict[str, Any]:
    plan_summary = _summary(batch3_plan_packet)
    plan_rows = _selected_rows(batch3_plan_packet)
    blockers: list[str] = []
    if _text(plan_summary.get("status")) not in READY_SOURCE_STATUSES:
        blockers.append("batch3_plan_not_ready")
    if not plan_rows:
        blockers.append("batch3_selected_rows_missing")

    receipt_rows: list[dict[str, Any]] = []
    for plan_row in plan_rows:
        source_path_text = _text(plan_row.get("tool_path"))
        target_path_text = _text(plan_row.get("target_path"))
        source_path = _resolve(source_path_text)
        target_path = _resolve(target_path_text)
        wrapper_text = source_path.read_text(encoding="utf-8", errors="ignore") if source_path.is_file() else ""
        row_blockers: list[str] = []
        if not source_path.is_file():
            row_blockers.append("source_wrapper_missing")
        if not target_path.is_file():
            row_blockers.append("target_module_missing")
        if not (target_path.parent / "__init__.py").is_file():
            row_blockers.append("package_init_missing")
        if target_path_text and _wrapper_import_line(target_path_text) not in wrapper_text:
            row_blockers.append("wrapper_import_missing")
        wrapper_main_required = _target_has_main(target_path)
        if wrapper_main_required and _wrapper_main_line(target_path_text) not in wrapper_text:
            row_blockers.append("wrapper_main_passthrough_missing")
        source_compile_ok = _compile_ok(source_path)
        target_compile_ok = _compile_ok(target_path)
        if not source_compile_ok:
            row_blockers.append("source_wrapper_py_compile_failed")
        if not target_compile_ok:
            row_blockers.append("target_module_py_compile_failed")
        blockers.extend(row_blockers)
        receipt_rows.append(
            {
                "source_path": source_path_text,
                "target_path": target_path_text,
                "proposed_package": _text(plan_row.get("proposed_package")),
                "review_lane": _text(plan_row.get("review_lane")),
                "source_wrapper_present": source_path.is_file(),
                "target_module_present": target_path.is_file(),
                "source_wrapper_py_compile_ok": source_compile_ok,
                "target_module_py_compile_ok": target_compile_ok,
                "wrapper_main_passthrough_required": wrapper_main_required,
                "migration_verified": not row_blockers,
                "blockers": ",".join(row_blockers),
                "move_executed": target_path.is_file(),
                "compatibility_wrapper_retained": source_path.is_file(),
                "caller_or_test_rewrite_executed": False,
                "external_state_mutated": False,
            }
        )

    verified_count = sum(1 for row in receipt_rows if row["migration_verified"])
    status = "tools_package_batch3_migration_receipt_ready" if receipt_rows and not blockers else "blocked_tools_package_batch3_migration_receipt"
    summary = {
        "packet_type": "tools_package_batch3_migration_receipt",
        "status": status,
        "source_batch3_plan_json": batch3_plan_json,
        "source_batch3_plan_status": _text(plan_summary.get("status")),
        "plan_selected_count": len(plan_rows),
        "verified_migration_count": verified_count,
        "blocked_migration_count": len(receipt_rows) - verified_count,
        "blocker_count": len(blockers),
        "blockers": sorted(set(blockers)),
        "move_executed": any(row["move_executed"] for row in receipt_rows),
        "compatibility_wrapper_retained": all(row["compatibility_wrapper_retained"] for row in receipt_rows) if receipt_rows else False,
        "caller_or_test_rewrite_executed": False,
        "delete_executed": False,
        "archive_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Regenerate the deep tools package separation work order and batch3 review plan to select the next batch3 slice."
            if status == "tools_package_batch3_migration_receipt_ready"
            else "Fix missing target modules or compatibility wrappers before recalculating batch3 progress."
        ),
    }
    return {"summary": summary, "rows": receipt_rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Tools Package Batch3 Migration Receipt",
        "",
        f"- status: `{s['status']}`",
        f"- plan_selected_count: `{s['plan_selected_count']}`",
        f"- verified_migration_count: `{s['verified_migration_count']}`",
        f"- blocked_migration_count: `{s['blocked_migration_count']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        "",
        "## Claim Boundary",
        "",
        s["claim_boundary"],
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build tools package batch3 migration receipt.")
    parser.add_argument("--batch3-plan-json", default=DEFAULT_BATCH3_PLAN_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    payload = build_tools_package_batch3_migration_receipt(
        batch3_plan_packet=_read_json_if_present(args.batch3_plan_json),
        batch3_plan_json=args.batch3_plan_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
