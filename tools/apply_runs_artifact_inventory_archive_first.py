#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import shutil
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from tools.lib.artifacts import read_csv, resolve, short_error, write_csv, write_json

DEFAULT_INVENTORY_CSV = "runs/runs_artifact_inventory_current.csv"
DEFAULT_RUNS_DIR = "runs"
DEFAULT_ARCHIVE_ROOT = "runs/archive/runs_artifact_inventory_archive_first_current"
DEFAULT_OUT_JSON = "runs/runs_artifact_inventory_archive_first_apply_report_current.json"
DEFAULT_OUT_CSV = "runs/runs_artifact_inventory_archive_first_apply_report_current.csv"
DEFAULT_OUT_MD = "runs/runs_artifact_inventory_archive_first_apply_report_current.md"
DEFAULT_INCLUDE_GROUPS = {
    "wetlab_broad_screen_throughput",
    "wetlab_broad_screen_antitarget_throughput",
}
DEFAULT_INCLUDE_GROUP_REGEXES = [
    r"^ligand_htvs_nightly_.*stage2_traj_frames$",
    r"^nightly_fix_probe_stage2_traj_frames$",
]
EXCLUDED_GROUPS = {"(root)", "_by_name", "archive"}
GROUP_DATE_RE = re.compile(r"20\d{2}-\d{2}-\d{2}")


def _size_gb(size_bytes: int) -> float:
    return round(size_bytes / (1024 * 1024 * 1024), 3)


def _size_mb(size_bytes: int) -> float:
    return round(size_bytes / (1024 * 1024), 3)


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _display(path: Path) -> str:
    try:
        return str(path.relative_to(resolve(".")))
    except ValueError:
        return str(path)


def _compile_patterns(patterns: list[str]) -> list[re.Pattern[str]]:
    return [re.compile(pattern) for pattern in patterns]


def _defaulted(values: list[str] | None, defaults: set[str] | list[str]) -> list[str]:
    return list(defaults) if values is None else list(values)


def should_archive_row(
    row: dict[str, str],
    *,
    include_groups: set[str],
    include_group_patterns: list[re.Pattern[str]],
    today_local: date | None = None,
) -> bool:
    path = str(row.get("path", "")).strip()
    group = str(row.get("top_level_group", "")).strip()
    if str(row.get("cleanup_action", "")).strip() != "archive_review":
        return False
    if str(row.get("file_kind", "file")).strip() == "symlink":
        return False
    if group in EXCLUDED_GROUPS:
        return False
    if "_current" in path:
        return False
    if today_local is not None:
        match = GROUP_DATE_RE.search(group)
        if match and date.fromisoformat(match.group(0)) >= today_local:
            return False
    if group in include_groups:
        return True
    return any(pattern.search(group) for pattern in include_group_patterns)


def select_rows(
    inventory_rows: list[dict[str, str]],
    *,
    include_groups: set[str] | None = None,
    include_group_regexes: list[str] | None = None,
    protect_same_day_dated: bool = True,
    today_local: date | None = None,
) -> list[dict[str, str]]:
    groups = set(DEFAULT_INCLUDE_GROUPS if include_groups is None else include_groups)
    patterns = _compile_patterns(_defaulted(include_group_regexes, DEFAULT_INCLUDE_GROUP_REGEXES))
    effective_today = today_local if protect_same_day_dated else None
    if protect_same_day_dated and effective_today is None:
        effective_today = datetime.now().astimezone().date()
    return [
        row
        for row in inventory_rows
        if should_archive_row(row, include_groups=groups, include_group_patterns=patterns, today_local=effective_today)
    ]


def _group_state(group: str) -> dict[str, Any]:
    return {
        "top_level_group": group,
        "planned_file_count": 0,
        "planned_size_mb": 0.0,
        "moved_file_count": 0,
        "moved_size_mb": 0.0,
        "already_archived_file_count": 0,
        "missing_file_count": 0,
        "destination_conflict_count": 0,
        "error_count": 0,
        "sample_artifacts": "",
        "status": "planned",
    }


def _archive_destination(archive_root: Path, path_text: str) -> Path:
    rel = Path(path_text)
    if rel.parts and rel.parts[0] == "runs":
        rel = Path(*rel.parts[1:])
    return archive_root / rel


def _source_path(runs_root: Path, path_text: str) -> Path:
    rel = Path(path_text)
    if rel.parts and rel.parts[0] == "runs":
        return runs_root / Path(*rel.parts[1:])
    return resolve(path_text)


def _prune_empty_parents(source_parent: Path, runs_root: Path, stop_at: Path) -> int:
    pruned = 0
    current = source_parent
    while current != runs_root and current != stop_at and runs_root in current.parents:
        try:
            current.rmdir()
        except OSError:
            break
        pruned += 1
        current = current.parent
    return pruned


def apply_archive_first(
    inventory_rows: list[dict[str, str]],
    *,
    archive_root: str | Path = DEFAULT_ARCHIVE_ROOT,
    runs_dir: str | Path = DEFAULT_RUNS_DIR,
    include_groups: set[str] | None = None,
    include_group_regexes: list[str] | None = None,
    protect_same_day_dated: bool = True,
    today_local: date | None = None,
    execute: bool = False,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    selected = select_rows(
        inventory_rows,
        include_groups=include_groups,
        include_group_regexes=include_group_regexes,
        protect_same_day_dated=protect_same_day_dated,
        today_local=today_local,
    )
    effective_include_groups = sorted(DEFAULT_INCLUDE_GROUPS if include_groups is None else include_groups)
    effective_include_group_regexes = _defaulted(include_group_regexes, DEFAULT_INCLUDE_GROUP_REGEXES)
    archive_root_path = resolve(archive_root)
    runs_root = resolve(runs_dir)
    rows_by_group: dict[str, dict[str, Any]] = {}
    samples: dict[str, list[str]] = defaultdict(list)
    errors: list[dict[str, str]] = []
    pruned_empty_dir_count = 0
    archive_root_path.mkdir(parents=True, exist_ok=True)

    for row in selected:
        group = str(row.get("top_level_group", "")).strip()
        state = rows_by_group.setdefault(group, _group_state(group))
        planned_size = _as_int(row.get("size_bytes"))
        state["planned_file_count"] += 1
        state["planned_size_mb"] = round(float(state["planned_size_mb"]) + _size_mb(planned_size), 3)
        path_text = str(row.get("path", "")).strip()
        if len(samples[group]) < 3:
            samples[group].append(path_text)

        source = _source_path(runs_root, path_text)
        destination = _archive_destination(archive_root_path, path_text)
        if destination.exists() and not source.exists():
            state["already_archived_file_count"] += 1
            continue
        if destination.exists():
            state["destination_conflict_count"] += 1
            continue
        if not source.exists() and not source.is_symlink():
            state["missing_file_count"] += 1
            continue
        if not execute:
            continue

        try:
            source_size = source.lstat().st_size
            destination.parent.mkdir(parents=True, exist_ok=True)
            source_parent = source.parent
            shutil.move(str(source), str(destination))
            state["moved_file_count"] += 1
            state["moved_size_mb"] = round(float(state["moved_size_mb"]) + _size_mb(source_size), 3)
            stop_at = runs_root / group
            pruned_empty_dir_count += _prune_empty_parents(source_parent, runs_root, stop_at)
        except OSError as exc:
            state["error_count"] += 1
            if len(errors) < 100:
                errors.append({"path": path_text, "error": short_error(exc)})

    total_planned_bytes = sum(_as_int(row.get("size_bytes")) for row in selected)
    total_moved_bytes = 0
    group_rows = []
    for group, state in sorted(rows_by_group.items()):
        total_moved_bytes += int(round(float(state["moved_size_mb"]) * 1024 * 1024))
        state["sample_artifacts"] = "; ".join(samples[group])
        if not execute:
            state["status"] = "dry_run_planned"
        elif state["error_count"]:
            state["status"] = "completed_with_errors"
        elif state["destination_conflict_count"] or state["missing_file_count"]:
            state["status"] = "completed_with_skips"
        else:
            state["status"] = "archived"
        group_rows.append(state)

    summary = {
        "status": "runs_artifact_inventory_archive_first_dry_run_ready"
        if not execute
        else "runs_artifact_inventory_archive_first_apply_report_ready",
        "execution_mode": "execute" if execute else "dry_run",
        "generated_at_local": generated_at_local or datetime.now().astimezone().isoformat(timespec="seconds"),
        "archive_root": _display(archive_root_path),
        "selected_group_count": len(group_rows),
        "planned_file_count": len(selected),
        "planned_size_gb": _size_gb(total_planned_bytes),
        "moved_file_count": sum(_as_int(row["moved_file_count"]) for row in group_rows),
        "moved_size_gb": _size_gb(total_moved_bytes),
        "already_archived_file_count": sum(_as_int(row["already_archived_file_count"]) for row in group_rows),
        "missing_file_count": sum(_as_int(row["missing_file_count"]) for row in group_rows),
        "destination_conflict_count": sum(_as_int(row["destination_conflict_count"]) for row in group_rows),
        "error_count": sum(_as_int(row["error_count"]) for row in group_rows),
        "pruned_empty_dir_count": pruned_empty_dir_count,
        "delete_performed": False,
        "protect_same_day_dated": protect_same_day_dated,
        "selection_rule": "archive_review rows only; excludes root, _by_name, archive, symlinks, and _current paths; includes groups "
        + ",".join(effective_include_groups)
        + " and regexes "
        + ",".join(effective_include_group_regexes),
        "next_required_step": "Rebuild runs_artifact_inventory_current after execution and verify keep/current referenced evidence remains intact.",
    }
    return {"summary": summary, "rows": group_rows, "errors": errors}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Runs Artifact Inventory Archive-First Apply Report",
        "",
        f"- status: `{summary['status']}`",
        f"- execution_mode: `{summary['execution_mode']}`",
        f"- archive_root: `{summary['archive_root']}`",
        f"- selected_group_count: `{summary['selected_group_count']}`",
        f"- planned_file_count: `{summary['planned_file_count']}`",
        f"- planned_size_gb: `{summary['planned_size_gb']}`",
        f"- moved_file_count: `{summary['moved_file_count']}`",
        f"- moved_size_gb: `{summary['moved_size_gb']}`",
        f"- already_archived_file_count: `{summary['already_archived_file_count']}`",
        f"- missing_file_count: `{summary['missing_file_count']}`",
        f"- destination_conflict_count: `{summary['destination_conflict_count']}`",
        f"- error_count: `{summary['error_count']}`",
        f"- pruned_empty_dir_count: `{summary['pruned_empty_dir_count']}`",
        f"- delete_performed: `{summary['delete_performed']}`",
        "",
        "## Groups",
        "",
        "| top_level_group | planned_file_count | planned_size_mb | moved_file_count | moved_size_mb | already_archived | missing | conflicts | errors | status |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['top_level_group']}` | `{row['planned_file_count']}` | `{row['planned_size_mb']}` | `{row['moved_file_count']}` | `{row['moved_size_mb']}` | `{row['already_archived_file_count']}` | `{row['missing_file_count']}` | `{row['destination_conflict_count']}` | `{row['error_count']}` | `{row['status']}` |"
        )
    lines.extend(["", "## Selection Rule", "", f"- {summary['selection_rule']}", "", "## Next Step", "", f"- {summary['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Archive the highest-confidence rows from runs_artifact_inventory_current.csv.")
    parser.add_argument("--inventory-csv", default=DEFAULT_INVENTORY_CSV)
    parser.add_argument("--runs-dir", default=DEFAULT_RUNS_DIR)
    parser.add_argument("--archive-root", default=DEFAULT_ARCHIVE_ROOT)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--include-group", action="append", dest="include_groups")
    parser.add_argument("--include-group-regex", action="append", dest="include_group_regexes")
    parser.add_argument("--allow-same-day-dated", action="store_true")
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    include_groups = None if args.include_groups is None else set(args.include_groups)
    payload = apply_archive_first(
        read_csv(args.inventory_csv),
        archive_root=args.archive_root,
        runs_dir=args.runs_dir,
        include_groups=include_groups,
        include_group_regexes=args.include_group_regexes,
        protect_same_day_dated=not args.allow_same_day_dated,
        execute=args.execute,
    )
    write_json(args.out_json, payload)
    write_csv(args.out_csv, payload["rows"])
    _write_markdown(resolve(args.out_md), payload)


if __name__ == "__main__":
    main()
