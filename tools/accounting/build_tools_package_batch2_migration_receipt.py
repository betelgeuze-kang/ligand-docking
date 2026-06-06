#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import py_compile
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BATCH2_PLAN_JSON = "runs/tools_package_batch2_review_plan_current.json"
DEFAULT_OUT_JSON = "runs/tools_package_batch2_migration_receipt_current.json"
DEFAULT_OUT_CSV = "runs/tools_package_batch2_migration_receipt_current.csv"
DEFAULT_OUT_MD = "runs/tools_package_batch2_migration_receipt_current.md"

CLAIM_BOUNDARY = (
    "Tools package batch2 migration receipt only; it verifies the selected batch2 slice has package target modules, "
    "top-level compatibility wrappers, syntax-valid source/target modules, and rewritten recorded test/tool/import "
    "references. It does not move additional files, execute selected tools, delete, archive, commit, push, or mutate "
    "external state."
)
READY_PLAN_STATUSES = {
    "tools_package_batch2_review_plan_ready",
    "tools_package_batch2_manual_review_plan_ready",
}
IMPORT_ONLY_WRAPPER = "import_only_compatibility_wrapper"
CLI_MAIN_WRAPPER = "cli_main_passthrough_wrapper"


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


def _module_name(path_text: str) -> str:
    return Path(path_text).stem


def _package_name(target_path: str) -> str:
    return Path(target_path).parent.name


def _module_path(target_path: str) -> str:
    return target_path.removesuffix(".py").replace("/", ".")


def _wrapper_import_line(target_path: str) -> str:
    return f"from {_module_path(target_path)} import *"


def _wrapper_main_line(target_path: str) -> str:
    return f"from {_module_path(target_path)} import main as _main"


def _wrapper_strategy(plan_row: dict[str, Any]) -> str:
    strategy = _text(plan_row.get("compatibility_wrapper_strategy"))
    if strategy:
        return strategy
    return CLI_MAIN_WRAPPER


def _parse_locations(value: str) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for item in value.split(";"):
        item = item.strip()
        if not item or ":" not in item:
            continue
        path_text, line_text = item.rsplit(":", 1)
        try:
            out.append((path_text, int(line_text)))
        except ValueError:
            continue
    return out


def _window(path: Path, line_number: int, radius: int = 2) -> str:
    if not path.is_file() or line_number <= 0:
        return ""
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return ""
    start = max(1, line_number - radius)
    end = min(len(lines), line_number + radius)
    return "\n".join(lines[start - 1 : end])


def _reference_rewritten(window_text: str, *, source_path: str, target_path: str) -> bool:
    module = _module_name(source_path)
    package = _package_name(target_path)
    package_import = f"from tools.{package} import"
    direct_module = _module_path(target_path)
    script_path = target_path
    script_path_without_tools = target_path.removeprefix("tools/")
    old_script_path = source_path
    stale_import = f"from tools import {module}"
    stale_script = old_script_path in window_text
    if stale_import in window_text or stale_script:
        return False
    return (
        direct_module in window_text
        or script_path in window_text
        or script_path_without_tools in window_text
        or (package_import in window_text and module in window_text)
    )


def _internal_import_reference_verified(window_text: str) -> bool:
    markers = ("from tools import ", "from tools.", "import tools.", "tools.")
    return any(marker in window_text for marker in markers)


def build_tools_package_batch2_migration_receipt(
    *,
    batch2_plan_packet: dict[str, Any],
    batch2_plan_json: str = DEFAULT_BATCH2_PLAN_JSON,
) -> dict[str, Any]:
    plan_summary = _summary(batch2_plan_packet)
    plan_rows = _rows(batch2_plan_packet)
    blockers: list[str] = []
    if _text(plan_summary.get("status")) not in READY_PLAN_STATUSES:
        blockers.append("batch2_review_plan_not_ready")
    if not plan_rows:
        blockers.append("batch2_review_plan_rows_missing")

    migrated_reference_paths = {
        _text(plan_row.get("tool_path")): _text(plan_row.get("target_path"))
        for plan_row in plan_rows
        if _text(plan_row.get("tool_path")) and _text(plan_row.get("target_path"))
    }
    rows: list[dict[str, Any]] = []
    for plan_row in plan_rows:
        source_path_text = _text(plan_row.get("tool_path"))
        target_path_text = _text(plan_row.get("target_path"))
        source_path = _resolve(source_path_text)
        target_path = _resolve(target_path_text)
        wrapper_text = source_path.read_text(encoding="utf-8", errors="ignore") if source_path.is_file() else ""
        wrapper_strategy = _wrapper_strategy(plan_row)
        row_blockers: list[str] = []
        if not source_path.is_file():
            row_blockers.append("source_wrapper_missing")
        if not target_path.is_file():
            row_blockers.append("target_module_missing")
        if not (target_path.parent / "__init__.py").is_file():
            row_blockers.append("package_init_missing")
        if _wrapper_import_line(target_path_text) not in wrapper_text:
            row_blockers.append("wrapper_import_missing")
        if wrapper_strategy != IMPORT_ONLY_WRAPPER and _wrapper_main_line(target_path_text) not in wrapper_text:
            row_blockers.append("wrapper_main_passthrough_missing")
        source_compile_ok = _compile_ok(source_path)
        target_compile_ok = _compile_ok(target_path)
        if not source_compile_ok:
            row_blockers.append("source_wrapper_py_compile_failed")
        if not target_compile_ok:
            row_blockers.append("target_module_py_compile_failed")

        rewritten_locations: list[str] = []
        stale_locations: list[str] = []
        missing_locations: list[str] = []
        reference_class = _text(plan_row.get("reference_class"))
        for ref_path_text, line_number in _parse_locations(_text(plan_row.get("reference_locations"))):
            text = _window(_resolve(ref_path_text), line_number)
            location = f"{ref_path_text}:{line_number}"
            resolved_ref_path_text = ref_path_text
            if reference_class == "internal_import_reference" and ref_path_text == source_path_text and ref_path_text in migrated_reference_paths:
                resolved_ref_path_text = migrated_reference_paths[ref_path_text]
                text = _window(_resolve(resolved_ref_path_text), line_number)
            if not text and ref_path_text in migrated_reference_paths:
                resolved_ref_path_text = migrated_reference_paths[ref_path_text]
                text = _window(_resolve(resolved_ref_path_text), line_number)
            if not text:
                missing_locations.append(location)
            elif reference_class == "internal_import_reference" and _internal_import_reference_verified(text):
                rewritten_locations.append(location)
            elif _reference_rewritten(text, source_path=source_path_text, target_path=target_path_text):
                rewritten_locations.append(location)
            elif ref_path_text in migrated_reference_paths:
                resolved_ref_path_text = migrated_reference_paths[ref_path_text]
                moved_text = _window(_resolve(resolved_ref_path_text), line_number)
                if moved_text and _reference_rewritten(moved_text, source_path=source_path_text, target_path=target_path_text):
                    rewritten_locations.append(location)
                else:
                    stale_locations.append(location)
            else:
                stale_locations.append(location)
        if missing_locations:
            row_blockers.append("reference_location_missing")
        if stale_locations:
            row_blockers.append("reference_not_rewritten")
        blockers.extend(row_blockers)
        rows.append(
            {
                "source_path": source_path_text,
                "target_path": target_path_text,
                "proposed_package": _text(plan_row.get("proposed_package")),
                "reference_class": _text(plan_row.get("reference_class")),
                "compatibility_wrapper_strategy": wrapper_strategy,
                "wrapper_main_passthrough_required": wrapper_strategy != IMPORT_ONLY_WRAPPER,
                "source_wrapper_present": source_path.is_file(),
                "target_module_present": target_path.is_file(),
                "source_wrapper_py_compile_ok": source_compile_ok,
                "target_module_py_compile_ok": target_compile_ok,
                "reference_locations": _text(plan_row.get("reference_locations")),
                "rewritten_reference_locations": ";".join(rewritten_locations),
                "stale_reference_locations": ";".join(stale_locations),
                "missing_reference_locations": ";".join(missing_locations),
                "reference_rewrite_verified": bool(rewritten_locations) and not stale_locations and not missing_locations,
                "migration_verified": not row_blockers,
                "blockers": ",".join(row_blockers),
                "move_executed": target_path.is_file(),
                "compatibility_wrapper_retained": source_path.is_file(),
                "caller_or_test_rewrite_executed": bool(rewritten_locations) and not stale_locations and not missing_locations,
                "external_state_mutated": False,
            }
        )

    verified_count = sum(1 for row in rows if row["migration_verified"])
    status = "tools_package_batch2_migration_receipt_ready" if rows and not blockers else "blocked_tools_package_batch2_migration_receipt"
    summary = {
        "packet_type": "tools_package_batch2_migration_receipt",
        "status": status,
        "source_batch2_plan_json": batch2_plan_json,
        "source_batch2_plan_status": _text(plan_summary.get("status")),
        "plan_selected_count": len(plan_rows),
        "verified_migration_count": verified_count,
        "blocked_migration_count": len(rows) - verified_count,
        "reference_rewrite_verified_count": sum(1 for row in rows if row["reference_rewrite_verified"]),
        "cli_main_wrapper_count": sum(1 for row in rows if row["compatibility_wrapper_strategy"] == CLI_MAIN_WRAPPER),
        "import_only_wrapper_count": sum(1 for row in rows if row["compatibility_wrapper_strategy"] == IMPORT_ONLY_WRAPPER),
        "blocker_count": len(blockers),
        "blockers": sorted(set(blockers)),
        "move_executed": any(row["move_executed"] for row in rows),
        "compatibility_wrapper_retained": all(row["compatibility_wrapper_retained"] for row in rows) if rows else False,
        "caller_or_test_rewrite_executed": all(row["caller_or_test_rewrite_executed"] for row in rows) if rows else False,
        "delete_executed": False,
        "archive_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Regenerate the deep tools package separation work order and batch2 review plan to select the next batch2 slice."
            if status == "tools_package_batch2_migration_receipt_ready"
            else "Fix missing wrappers, target modules, or stale recorded references before recalculating batch2 progress."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Tools Package Batch2 Migration Receipt",
        "",
        f"- status: `{s['status']}`",
        f"- plan_selected_count: `{s['plan_selected_count']}`",
        f"- verified_migration_count: `{s['verified_migration_count']}`",
        f"- reference_rewrite_verified_count: `{s['reference_rewrite_verified_count']}`",
        f"- cli_main_wrapper_count: `{s['cli_main_wrapper_count']}`",
        f"- import_only_wrapper_count: `{s['import_only_wrapper_count']}`",
        f"- blocked_migration_count: `{s['blocked_migration_count']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- blockers: `{';'.join(s['blockers'])}`",
        f"- move_executed: `{s['move_executed']}`",
        f"- compatibility_wrapper_retained: `{s['compatibility_wrapper_retained']}`",
        f"- caller_or_test_rewrite_executed: `{s['caller_or_test_rewrite_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Rows",
        "",
        "| source | target | class | wrapper | rewritten refs | verified | blockers |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['source_path']}` | `{row['target_path']}` | `{row['reference_class']}` | "
            f"`{row['compatibility_wrapper_strategy']}` | `{row['rewritten_reference_locations']}` | "
            f"`{row['migration_verified']}` | `{row['blockers']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a receipt for selected batch2 tools package migration.")
    parser.add_argument("--batch2-plan-json", default=DEFAULT_BATCH2_PLAN_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    plan_packet = _read_json_if_present(args.batch2_plan_json)
    payload = build_tools_package_batch2_migration_receipt(
        batch2_plan_packet=plan_packet,
        batch2_plan_json=args.batch2_plan_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
