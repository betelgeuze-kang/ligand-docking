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
DEFAULT_ARCHIVE_ROOT = "runs/archive/runs_artifact_inventory_root_archive_current"
DEFAULT_OUT_JSON = "runs/runs_artifact_inventory_root_archive_apply_report_current.json"
DEFAULT_OUT_CSV = "runs/runs_artifact_inventory_root_archive_apply_report_current.csv"
DEFAULT_OUT_MD = "runs/runs_artifact_inventory_root_archive_apply_report_current.md"
DEFAULT_INCLUDE_PREFIXES = ("external_validation_", "ligand_stress_validation_")
ROOT_GROUP = "(root)"
GROUP_DATE_RE = re.compile(r"20\d{2}-\d{2}-\d{2}")


def _size_mb(size_bytes: int) -> float:
    return round(size_bytes / (1024 * 1024), 3)


def _size_gb(size_bytes: int) -> float:
    return round(size_bytes / (1024 * 1024 * 1024), 3)


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


def _relative_runs_path(path: Path, runs_root: Path) -> str:
    return str(Path(runs_root.name) / path.relative_to(runs_root))


def _source_path(runs_root: Path, path_text: str) -> Path:
    rel = Path(path_text)
    if rel.parts and rel.parts[0] == "runs":
        return runs_root / Path(*rel.parts[1:])
    return resolve(path_text)


def _archive_destination(archive_root: Path, path_text: str) -> Path:
    rel = Path(path_text)
    if rel.parts and rel.parts[0] == "runs":
        rel = Path(*rel.parts[1:])
    return archive_root / rel


def _basename(path_text: str) -> str:
    return Path(path_text).name


def _family_for_name(name: str, prefixes: tuple[str, ...]) -> str:
    for prefix in prefixes:
        if name.startswith(prefix):
            return prefix.rstrip("_")
    return "unknown"


def _is_same_day_or_newer(path_text: str, today_local: date | None) -> bool:
    if today_local is None:
        return False
    match = GROUP_DATE_RE.search(path_text)
    return bool(match and date.fromisoformat(match.group(0)) >= today_local)


def should_archive_root_row(
    row: dict[str, str],
    *,
    include_prefixes: tuple[str, ...],
    today_local: date | None = None,
) -> bool:
    path_text = str(row.get("path", "")).strip()
    name = _basename(path_text)
    if str(row.get("cleanup_action", "")).strip() != "archive_review":
        return False
    if str(row.get("top_level_group", "")).strip() != ROOT_GROUP:
        return False
    if str(row.get("file_kind", "file")).strip() == "symlink":
        return False
    if "_current" in path_text:
        return False
    if not name.startswith(include_prefixes):
        return False
    return not _is_same_day_or_newer(path_text, today_local)


def select_root_rows(
    inventory_rows: list[dict[str, str]],
    *,
    include_prefixes: tuple[str, ...] = DEFAULT_INCLUDE_PREFIXES,
    protect_same_day_dated: bool = True,
    today_local: date | None = None,
) -> list[dict[str, str]]:
    effective_today = today_local
    if protect_same_day_dated and effective_today is None:
        effective_today = datetime.now().astimezone().date()
    if not protect_same_day_dated:
        effective_today = None
    return [
        row
        for row in inventory_rows
        if should_archive_root_row(row, include_prefixes=include_prefixes, today_local=effective_today)
    ]


def collect_by_name_symlink_companions(
    *,
    runs_root: Path,
    selected_root_names: set[str],
) -> list[dict[str, Any]]:
    by_name_root = runs_root / "_by_name"
    if not by_name_root.exists():
        return []
    companions: list[dict[str, Any]] = []
    for link in sorted(by_name_root.rglob("*")):
        if not link.is_symlink():
            continue
        try:
            target = (link.parent / link.readlink()).resolve()
            target_rel = target.relative_to(runs_root.resolve())
        except (OSError, ValueError):
            continue
        if len(target_rel.parts) != 1 or target_rel.name not in selected_root_names:
            continue
        companions.append(
            {
                "path": _relative_runs_path(link, runs_root),
                "target_name": target_rel.name,
                "size_bytes": link.lstat().st_size,
            }
        )
    return companions


def _entry_move_status(source: Path, destination: Path) -> str:
    destination_exists = destination.exists() or destination.is_symlink()
    source_exists = source.exists() or source.is_symlink()
    if destination_exists and not source_exists:
        return "already_archived"
    if destination_exists:
        return "destination_conflict"
    if not source_exists:
        return "missing_source"
    return "ready"


def _move_entry(source: Path, destination: Path, *, execute: bool) -> tuple[str, int, str]:
    status = _entry_move_status(source, destination)
    if status != "ready":
        return status, 0, ""
    if not execute:
        return "dry_run_planned", source.lstat().st_size, ""
    try:
        size = source.lstat().st_size
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        return "archived", size, ""
    except OSError as exc:
        return "error", 0, short_error(exc)


def _row_state(key: str, entry_type: str) -> dict[str, Any]:
    return {
        "group": key,
        "entry_type": entry_type,
        "planned_count": 0,
        "planned_size_mb": 0.0,
        "moved_count": 0,
        "moved_size_mb": 0.0,
        "already_archived_count": 0,
        "missing_count": 0,
        "destination_conflict_count": 0,
        "error_count": 0,
        "sample_artifacts": "",
        "status": "planned",
    }


def _bump_planned(state: dict[str, Any], size_bytes: int, sample: str, samples: dict[tuple[str, str], list[str]]) -> None:
    state["planned_count"] += 1
    state["planned_size_mb"] = round(float(state["planned_size_mb"]) + _size_mb(size_bytes), 3)
    key = (str(state["group"]), str(state["entry_type"]))
    if len(samples[key]) < 3:
        samples[key].append(sample)


def _bump_status(state: dict[str, Any], status: str, moved_size: int) -> None:
    if status == "archived":
        state["moved_count"] += 1
        state["moved_size_mb"] = round(float(state["moved_size_mb"]) + _size_mb(moved_size), 3)
    elif status == "already_archived":
        state["already_archived_count"] += 1
    elif status == "missing_source":
        state["missing_count"] += 1
    elif status == "destination_conflict":
        state["destination_conflict_count"] += 1
    elif status == "error":
        state["error_count"] += 1


def _final_status(state: dict[str, Any], *, execute: bool) -> str:
    if not execute:
        return "dry_run_planned"
    if state["error_count"]:
        return "completed_with_errors"
    if state["destination_conflict_count"] or state["missing_count"]:
        return "completed_with_skips"
    if state["moved_count"] or state["already_archived_count"]:
        return "archived"
    return "no_op"


def apply_root_archive(
    inventory_rows: list[dict[str, str]],
    *,
    runs_dir: str | Path = DEFAULT_RUNS_DIR,
    archive_root: str | Path = DEFAULT_ARCHIVE_ROOT,
    include_prefixes: tuple[str, ...] = DEFAULT_INCLUDE_PREFIXES,
    protect_same_day_dated: bool = True,
    today_local: date | None = None,
    execute: bool = False,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    runs_root = resolve(runs_dir)
    archive_root_path = resolve(archive_root)
    archive_root_path.mkdir(parents=True, exist_ok=True)
    selected_rows = select_root_rows(
        inventory_rows,
        include_prefixes=include_prefixes,
        protect_same_day_dated=protect_same_day_dated,
        today_local=today_local,
    )
    selected_names = {_basename(row["path"]) for row in selected_rows}
    companions = collect_by_name_symlink_companions(runs_root=runs_root, selected_root_names=selected_names)

    states: dict[tuple[str, str], dict[str, Any]] = {}
    samples: dict[tuple[str, str], list[str]] = defaultdict(list)
    errors: list[dict[str, str]] = []

    for row in selected_rows:
        path_text = str(row["path"])
        name = _basename(path_text)
        family = _family_for_name(name, include_prefixes)
        state = states.setdefault((family, "root_file"), _row_state(family, "root_file"))
        size = _as_int(row.get("size_bytes"))
        _bump_planned(state, size, path_text, samples)
        status, moved_size, error = _move_entry(
            _source_path(runs_root, path_text),
            _archive_destination(archive_root_path, path_text),
            execute=execute,
        )
        _bump_status(state, status, moved_size)
        if error and len(errors) < 100:
            errors.append({"path": path_text, "error": error})

    for companion in companions:
        path_text = str(companion["path"])
        target_name = str(companion["target_name"])
        family = _family_for_name(target_name, include_prefixes)
        state = states.setdefault((family, "by_name_symlink"), _row_state(family, "by_name_symlink"))
        size = _as_int(companion.get("size_bytes"))
        _bump_planned(state, size, path_text, samples)
        status, moved_size, error = _move_entry(
            _source_path(runs_root, path_text),
            _archive_destination(archive_root_path, path_text),
            execute=execute,
        )
        _bump_status(state, status, moved_size)
        if error and len(errors) < 100:
            errors.append({"path": path_text, "error": error})

    rows: list[dict[str, Any]] = []
    for key, state in sorted(states.items()):
        state["sample_artifacts"] = "; ".join(samples[key])
        state["status"] = _final_status(state, execute=execute)
        rows.append(state)

    planned_root_bytes = sum(_as_int(row.get("size_bytes")) for row in selected_rows)
    planned_symlink_bytes = sum(_as_int(row.get("size_bytes")) for row in companions)
    moved_bytes = int(sum(float(row["moved_size_mb"]) for row in rows) * 1024 * 1024)
    summary = {
        "status": "runs_artifact_inventory_root_archive_dry_run_ready"
        if not execute
        else "runs_artifact_inventory_root_archive_apply_report_ready",
        "execution_mode": "execute" if execute else "dry_run",
        "generated_at_local": generated_at_local or datetime.now().astimezone().isoformat(timespec="seconds"),
        "archive_root": _display(archive_root_path),
        "include_prefixes": list(include_prefixes),
        "protect_same_day_dated": protect_same_day_dated,
        "selected_root_file_count": len(selected_rows),
        "selected_root_size_gb": _size_gb(planned_root_bytes),
        "companion_symlink_count": len(companions),
        "companion_symlink_size_mb": _size_mb(planned_symlink_bytes),
        "planned_entry_count": len(selected_rows) + len(companions),
        "planned_size_gb": _size_gb(planned_root_bytes + planned_symlink_bytes),
        "moved_entry_count": sum(_as_int(row["moved_count"]) for row in rows),
        "moved_size_gb": _size_gb(moved_bytes),
        "already_archived_count": sum(_as_int(row["already_archived_count"]) for row in rows),
        "missing_count": sum(_as_int(row["missing_count"]) for row in rows),
        "destination_conflict_count": sum(_as_int(row["destination_conflict_count"]) for row in rows),
        "error_count": sum(_as_int(row["error_count"]) for row in rows),
        "delete_performed": False,
        "selection_rule": "archive_review root files only; excludes _current and same-day dated paths; includes prefixes "
        + ",".join(include_prefixes)
        + " plus matching _by_name symlinks",
        "next_required_step": "Rebuild runs_artifact_inventory_current after execution and confirm root-level archive_review is reduced without broken _by_name symlink residue.",
    }
    return {"summary": summary, "rows": rows, "errors": errors}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Runs Artifact Inventory Root Archive Apply Report",
        "",
        f"- status: `{summary['status']}`",
        f"- execution_mode: `{summary['execution_mode']}`",
        f"- archive_root: `{summary['archive_root']}`",
        f"- selected_root_file_count: `{summary['selected_root_file_count']}`",
        f"- selected_root_size_gb: `{summary['selected_root_size_gb']}`",
        f"- companion_symlink_count: `{summary['companion_symlink_count']}`",
        f"- planned_entry_count: `{summary['planned_entry_count']}`",
        f"- planned_size_gb: `{summary['planned_size_gb']}`",
        f"- moved_entry_count: `{summary['moved_entry_count']}`",
        f"- moved_size_gb: `{summary['moved_size_gb']}`",
        f"- already_archived_count: `{summary['already_archived_count']}`",
        f"- missing_count: `{summary['missing_count']}`",
        f"- destination_conflict_count: `{summary['destination_conflict_count']}`",
        f"- error_count: `{summary['error_count']}`",
        f"- delete_performed: `{summary['delete_performed']}`",
        "",
        "## Groups",
        "",
        "| group | entry_type | planned_count | planned_size_mb | moved_count | moved_size_mb | already_archived | missing | conflicts | errors | status |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['group']}` | `{row['entry_type']}` | `{row['planned_count']}` | `{row['planned_size_mb']}` | `{row['moved_count']}` | `{row['moved_size_mb']}` | `{row['already_archived_count']}` | `{row['missing_count']}` | `{row['destination_conflict_count']}` | `{row['error_count']}` | `{row['status']}` |"
        )
    lines.extend(["", "## Selection Rule", "", f"- {summary['selection_rule']}", "", "## Next Step", "", f"- {summary['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Archive selected root-level external validation artifacts and matching _by_name symlinks.")
    parser.add_argument("--inventory-csv", default=DEFAULT_INVENTORY_CSV)
    parser.add_argument("--runs-dir", default=DEFAULT_RUNS_DIR)
    parser.add_argument("--archive-root", default=DEFAULT_ARCHIVE_ROOT)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--include-prefix", action="append", dest="include_prefixes")
    parser.add_argument("--allow-same-day-dated", action="store_true")
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    include_prefixes = tuple(args.include_prefixes) if args.include_prefixes else DEFAULT_INCLUDE_PREFIXES
    payload = apply_root_archive(
        read_csv(args.inventory_csv),
        runs_dir=args.runs_dir,
        archive_root=args.archive_root,
        include_prefixes=include_prefixes,
        protect_same_day_dated=not args.allow_same_day_dated,
        execute=args.execute,
    )
    write_json(args.out_json, payload)
    write_csv(args.out_csv, payload["rows"])
    _write_markdown(resolve(args.out_md), payload)


if __name__ == "__main__":
    main()
