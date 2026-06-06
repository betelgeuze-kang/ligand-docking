#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import py_compile
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REFERENCE_REVIEW_JSON = "runs/tools_package_reference_review_current.json"
DEFAULT_OUT_JSON = "runs/tools_package_reference_migration_receipt_current.json"
DEFAULT_OUT_CSV = "runs/tools_package_reference_migration_receipt_current.csv"
DEFAULT_OUT_MD = "runs/tools_package_reference_migration_receipt_current.md"

CLAIM_BOUNDARY = (
    "Tools package reference migration receipt only; it verifies referenced batch_1 tools were moved to package "
    "targets, top-level wrappers remain, and recorded caller lines now point at package paths. It does not move "
    "additional files, execute referenced tools, delete, archive, commit, push, or mutate external state."
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


def _module_import_line(target_path: str) -> str:
    module = target_path.removesuffix(".py").replace("/", ".")
    return f"from {module} import *"


def _module_main_line(target_path: str) -> str:
    module = target_path.removesuffix(".py").replace("/", ".")
    return f"from {module} import main as _main"


def _line_at(path: Path, line_number: int) -> str:
    if not path.is_file() or line_number <= 0:
        return ""
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return ""
    return lines[line_number - 1] if line_number <= len(lines) else ""


def _target_tokens(target_path: str) -> list[str]:
    no_prefix = target_path.removeprefix("tools/")
    return [target_path, no_prefix]


def _parse_locations(value: str) -> list[tuple[str, int]]:
    locations: list[tuple[str, int]] = []
    for item in value.split(";"):
        item = item.strip()
        if not item or ":" not in item:
            continue
        path_text, line_text = item.rsplit(":", 1)
        try:
            line_number = int(line_text)
        except ValueError:
            continue
        locations.append((path_text, line_number))
    return locations


def build_tools_package_reference_migration_receipt(
    *,
    reference_review_packet: dict[str, Any],
    reference_review_json: str = DEFAULT_REFERENCE_REVIEW_JSON,
) -> dict[str, Any]:
    review_summary = _summary(reference_review_packet)
    review_rows = _rows(reference_review_packet)
    blockers: list[str] = []
    if _text(review_summary.get("status")) != "tools_package_reference_review_ready":
        blockers.append("reference_review_not_ready")
    if not review_rows:
        blockers.append("reference_review_rows_missing")

    rows: list[dict[str, Any]] = []
    for review_row in review_rows:
        source_path_text = _text(review_row.get("tool_path"))
        target_path_text = _text(review_row.get("target_path"))
        source_path = _resolve(source_path_text)
        target_path = _resolve(target_path_text)
        wrapper_text = source_path.read_text(encoding="utf-8", errors="ignore") if source_path.is_file() else ""
        source_compile_ok = _compile_ok(source_path)
        target_compile_ok = _compile_ok(target_path)
        row_blockers: list[str] = []
        if not source_path.is_file():
            row_blockers.append("source_wrapper_missing")
        if not target_path.is_file():
            row_blockers.append("target_module_missing")
        if not (target_path.parent / "__init__.py").is_file():
            row_blockers.append("package_init_missing")
        if _module_import_line(target_path_text) not in wrapper_text:
            row_blockers.append("wrapper_import_missing")
        if "monitor_wetlab_broad_screen.py" not in source_path_text and _module_main_line(target_path_text) not in wrapper_text:
            row_blockers.append("wrapper_main_passthrough_missing")
        if "monitor_wetlab_broad_screen.py" in source_path_text and "run_monitor" not in wrapper_text:
            row_blockers.append("wrapper_monitor_passthrough_missing")
        if not source_compile_ok:
            row_blockers.append("source_wrapper_py_compile_failed")
        if not target_compile_ok:
            row_blockers.append("target_module_py_compile_failed")

        caller_locations = _parse_locations(_text(review_row.get("reference_locations")))
        rewritten_locations: list[str] = []
        stale_locations: list[str] = []
        missing_locations: list[str] = []
        for caller_path_text, line_number in caller_locations:
            line = _line_at(_resolve(caller_path_text), line_number)
            location = f"{caller_path_text}:{line_number}"
            if not line:
                missing_locations.append(location)
                continue
            old_path_present = source_path_text in line
            target_present = any(token and token in line for token in _target_tokens(target_path_text))
            if target_present and not old_path_present:
                rewritten_locations.append(location)
            else:
                stale_locations.append(location)
        if missing_locations:
            row_blockers.append("caller_location_missing")
        if stale_locations:
            row_blockers.append("caller_line_not_rewritten")
        blockers.extend(row_blockers)
        rows.append(
            {
                "source_path": source_path_text,
                "target_path": target_path_text,
                "proposed_package": _text(review_row.get("proposed_package")),
                "source_wrapper_present": source_path.is_file(),
                "target_module_present": target_path.is_file(),
                "source_wrapper_py_compile_ok": source_compile_ok,
                "target_module_py_compile_ok": target_compile_ok,
                "caller_locations": ";".join(f"{path}:{line}" for path, line in caller_locations),
                "rewritten_caller_locations": ";".join(rewritten_locations),
                "stale_caller_locations": ";".join(stale_locations),
                "missing_caller_locations": ";".join(missing_locations),
                "caller_rewrite_verified": bool(caller_locations) and not stale_locations and not missing_locations,
                "migration_verified": not row_blockers,
                "blockers": ",".join(row_blockers),
                "move_executed": target_path.is_file(),
                "compatibility_wrapper_retained": source_path.is_file(),
                "caller_rewrite_executed": bool(caller_locations) and not stale_locations and not missing_locations,
                "external_state_mutated": False,
            }
        )

    verified_count = sum(1 for row in rows if row["migration_verified"])
    status = "tools_package_reference_migration_receipt_ready" if rows and not blockers else "blocked_tools_package_reference_migration_receipt"
    summary = {
        "packet_type": "tools_package_reference_migration_receipt",
        "status": status,
        "source_reference_review_json": reference_review_json,
        "source_reference_review_status": _text(review_summary.get("status")),
        "review_candidate_count": len(review_rows),
        "verified_migration_count": verified_count,
        "blocked_migration_count": len(rows) - verified_count,
        "caller_rewrite_verified_count": sum(1 for row in rows if row["caller_rewrite_verified"]),
        "blocker_count": len(blockers),
        "blockers": sorted(set(blockers)),
        "move_executed": any(row["move_executed"] for row in rows),
        "compatibility_wrapper_retained": all(row["compatibility_wrapper_retained"] for row in rows) if rows else False,
        "caller_rewrite_executed": all(row["caller_rewrite_executed"] for row in rows) if rows else False,
        "delete_executed": False,
        "archive_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Regenerate the deep tools package separation work order to recalculate the remaining package split backlog."
            if status == "tools_package_reference_migration_receipt_ready"
            else "Fix missing wrappers, package targets, or stale caller lines before recalculating the package split backlog."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Tools Package Reference Migration Receipt",
        "",
        f"- status: `{s['status']}`",
        f"- review_candidate_count: `{s['review_candidate_count']}`",
        f"- verified_migration_count: `{s['verified_migration_count']}`",
        f"- caller_rewrite_verified_count: `{s['caller_rewrite_verified_count']}`",
        f"- blocked_migration_count: `{s['blocked_migration_count']}`",
        f"- blocker_count: `{s['blocker_count']}`",
        f"- blockers: `{';'.join(s['blockers'])}`",
        f"- move_executed: `{s['move_executed']}`",
        f"- compatibility_wrapper_retained: `{s['compatibility_wrapper_retained']}`",
        f"- caller_rewrite_executed: `{s['caller_rewrite_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Verified Rows",
        "",
        "| source wrapper | target module | rewritten callers | verified | blockers |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['source_path']}` | `{row['target_path']}` | `{row['rewritten_caller_locations']}` | "
            f"`{row['migration_verified']}` | `{row['blockers']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a receipt for referenced tools package migration and caller rewrites.")
    parser.add_argument("--reference-review-json", default=DEFAULT_REFERENCE_REVIEW_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    review_packet = _read_json_if_present(args.reference_review_json)
    payload = build_tools_package_reference_migration_receipt(
        reference_review_packet=review_packet,
        reference_review_json=args.reference_review_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
