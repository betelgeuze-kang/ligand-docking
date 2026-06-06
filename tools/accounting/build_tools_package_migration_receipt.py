#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import py_compile
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN_JSON = "runs/tools_package_migration_plan_current.json"
DEFAULT_OUT_JSON = "runs/tools_package_migration_receipt_current.json"
DEFAULT_OUT_CSV = "runs/tools_package_migration_receipt_current.csv"
DEFAULT_OUT_MD = "runs/tools_package_migration_receipt_current.md"

CLAIM_BOUNDARY = (
    "Tools package migration receipt only; it verifies that selected migration-plan files now have package targets, "
    "top-level compatibility wrappers, package __init__.py files, and syntax-valid source/target modules. It does not "
    "move additional files, rewrite imports beyond existing wrappers, delete, archive, commit, push, or mutate external state."
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


def _compile_ok(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        py_compile.compile(str(path), doraise=True)
    except py_compile.PyCompileError:
        return False
    return True


def _wrapper_import_expected(target_path: str) -> str:
    module = target_path.removesuffix(".py").replace("/", ".")
    return f"from {module} import *"


def _wrapper_main_expected(target_path: str) -> str:
    module = target_path.removesuffix(".py").replace("/", ".")
    return f"from {module} import main as _main"


def build_tools_package_migration_receipt(
    *,
    plan_packet: dict[str, Any],
    plan_json: str = DEFAULT_PLAN_JSON,
) -> dict[str, Any]:
    plan_summary = _summary(plan_packet)
    plan_rows = _rows(plan_packet)
    blockers: list[str] = []
    if _text(plan_summary.get("status")) != "tools_package_migration_plan_ready":
        blockers.append("migration_plan_not_ready")
    if not plan_rows:
        blockers.append("migration_plan_rows_missing")

    rows: list[dict[str, Any]] = []
    for plan_row in plan_rows:
        source_path_text = _text(plan_row.get("source_path"))
        target_path_text = _text(plan_row.get("target_path"))
        package = _text(plan_row.get("proposed_package"))
        source_path = _resolve(source_path_text)
        target_path = _resolve(target_path_text)
        package_init = target_path.parent / "__init__.py"
        wrapper_text = source_path.read_text(encoding="utf-8", errors="ignore") if source_path.is_file() else ""
        row_blockers: list[str] = []
        if not source_path.is_file():
            row_blockers.append("source_wrapper_missing")
        if not target_path.is_file():
            row_blockers.append("target_module_missing")
        if not package_init.is_file():
            row_blockers.append("package_init_missing")
        if source_path.is_file() and _wrapper_import_expected(target_path_text) not in wrapper_text:
            row_blockers.append("wrapper_import_missing")
        if source_path.is_file() and _wrapper_main_expected(target_path_text) not in wrapper_text:
            row_blockers.append("wrapper_main_passthrough_missing")
        source_compile_ok = _compile_ok(source_path)
        target_compile_ok = _compile_ok(target_path)
        if not source_compile_ok:
            row_blockers.append("source_wrapper_py_compile_failed")
        if not target_compile_ok:
            row_blockers.append("target_module_py_compile_failed")
        blockers.extend(row_blockers)
        rows.append(
            {
                "source_path": source_path_text,
                "target_path": target_path_text,
                "proposed_package": package,
                "source_wrapper_present": source_path.is_file(),
                "target_module_present": target_path.is_file(),
                "package_init_present": package_init.is_file(),
                "wrapper_imports_target": _wrapper_import_expected(target_path_text) in wrapper_text,
                "wrapper_main_passthrough": _wrapper_main_expected(target_path_text) in wrapper_text,
                "source_wrapper_py_compile_ok": source_compile_ok,
                "target_module_py_compile_ok": target_compile_ok,
                "migration_verified": not row_blockers,
                "blockers": ",".join(row_blockers),
                "directory_created": target_path.parent.is_dir(),
                "move_executed": target_path.is_file(),
                "compatibility_wrapper_retained": source_path.is_file(),
                "import_rewrite_executed": False,
                "external_state_mutated": False,
            }
        )

    verified_count = sum(1 for row in rows if row["migration_verified"])
    status = "tools_package_migration_receipt_ready" if rows and not blockers else "blocked_tools_package_migration_receipt"
    summary = {
        "packet_type": "tools_package_migration_receipt",
        "status": status,
        "source_plan_json": plan_json,
        "source_plan_status": _text(plan_summary.get("status")),
        "plan_selected_count": len(plan_rows),
        "verified_migration_count": verified_count,
        "blocked_migration_count": len(rows) - verified_count,
        "blocker_count": len(blockers),
        "blockers": sorted(set(blockers)),
        "directory_created": any(row["directory_created"] for row in rows),
        "move_executed": any(row["move_executed"] for row in rows),
        "compatibility_wrapper_retained": all(row["compatibility_wrapper_retained"] for row in rows) if rows else False,
        "import_rewrite_executed": False,
        "delete_executed": False,
        "archive_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Regenerate the tools package separation work order and migration plan to select the next low-risk batch."
            if status == "tools_package_migration_receipt_ready"
            else "Fix missing wrappers, package targets, or syntax failures before selecting the next migration batch."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Tools Package Migration Receipt",
        "",
        f"- status: `{s['status']}`",
        f"- plan_selected_count: `{s['plan_selected_count']}`",
        f"- verified_migration_count: `{s['verified_migration_count']}`",
        f"- blocked_migration_count: `{s['blocked_migration_count']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- blockers: `{';'.join(s['blockers'])}`",
        f"- directory_created: `{s['directory_created']}`",
        f"- move_executed: `{s['move_executed']}`",
        f"- compatibility_wrapper_retained: `{s['compatibility_wrapper_retained']}`",
        f"- import_rewrite_executed: `{s['import_rewrite_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Verified Rows",
        "",
        "| source wrapper | target module | package | verified | blockers |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['source_path']}` | `{row['target_path']}` | `{row['proposed_package']}` | "
            f"`{row['migration_verified']}` | `{row['blockers']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a read-only receipt for an executed tools package migration batch.")
    parser.add_argument("--plan-json", default=DEFAULT_PLAN_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    plan_packet = _read_json_if_present(args.plan_json)
    payload = build_tools_package_migration_receipt(plan_packet=plan_packet, plan_json=args.plan_json)
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
