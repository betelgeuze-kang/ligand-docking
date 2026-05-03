#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOTS = ("ligand_heavy_runs", "runs/local_heavy_runs")
DEFAULT_ALLOW_PREFIXES = ("external_validation_", "ligand_", "local_", "run_", "heavy_")
DEFAULT_PRESERVE_PATTERNS = (
    "*summary*",
    "*evidence*",
    "*manifest*",
    "*report*",
    "*current*",
)
PAYLOAD_DIR_NAMES = {
    "stage2_trajectory_frames",
    "stage2_traj_frames",
    "trajectory_frames",
    "frames",
    "trajectory",
    "trajectories",
    "checkpoints",
}
HEAVY_EXTENSIONS = {
    ".dcd",
    ".xtc",
    ".trr",
    ".nc",
    ".h5",
    ".hdf5",
    ".lammpstrj",
}
HEAVY_DIR_NAMES = PAYLOAD_DIR_NAMES
ACTIVE_MARKER_NAMES = {
    ".lock",
    ".running",
    "running",
    "running.lock",
    "run.lock",
    "progress",
    "progress.json",
    "progress.jsonl",
}


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path.resolve()
    return (ROOT / path).resolve()


def _default_roots() -> list[str]:
    roots: list[str] = []
    seen: set[Path] = set()
    for root_like in DEFAULT_ROOTS:
        root = _resolve(root_like)
        if root.exists() and root not in seen:
            roots.append(str(root))
            seen.add(root)
    mnt = Path("/mnt")
    if mnt.exists():
        for root in sorted(mnt.glob("*/ligand_heavy_runs")):
            resolved = root.resolve()
            if resolved.exists() and resolved not in seen:
                roots.append(str(resolved))
                seen.add(resolved)
    return roots or list(DEFAULT_ROOTS)


def _split_values(values: Iterable[str] | None) -> list[str]:
    if not values:
        return []
    out: list[str] = []
    for value in values:
        out.extend(part.strip() for part in value.split(",") if part.strip())
    return out


def _process_lines() -> list[str]:
    try:
        output = subprocess.check_output(["ps", "-eo", "pid=,args="], text=True)
    except (OSError, subprocess.SubprocessError):
        return []
    ignored_pids = {os.getpid(), os.getppid()}
    lines: list[str] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            pid = int(line.split(maxsplit=1)[0])
        except (ValueError, IndexError):
            pid = -1
        if pid in ignored_pids:
            continue
        lines.append(line)
    return lines


def _dir_size(path: Path) -> int:
    try:
        output = subprocess.check_output(["du", "-sb", str(path)], text=True)
        return int(output.split()[0])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        total = 0
        for item in path.rglob("*"):
            if item.is_file():
                try:
                    total += item.stat().st_size
                except OSError:
                    continue
        return total


def _latest_mtime(path: Path) -> float:
    latest = path.stat().st_mtime
    for item in path.rglob("*"):
        try:
            latest = max(latest, item.stat().st_mtime)
        except OSError:
            continue
    return latest


def _has_heavy_payload(path: Path) -> bool:
    if path.is_dir() and path.name.lower() in HEAVY_DIR_NAMES:
        return True
    for item in path.rglob("*"):
        if item.is_dir() and item.name.lower() in HEAVY_DIR_NAMES:
            return True
        if item.is_file() and item.suffix.lower() in HEAVY_EXTENSIONS:
            return True
    return False


def _has_active_marker(path: Path) -> bool:
    for item in path.rglob("*"):
        name = item.name.lower()
        if name in ACTIVE_MARKER_NAMES or name.endswith(".lock"):
            return True
    return False


def _running_process_mentions(path: Path, process_lines: Iterable[str]) -> bool:
    resolved = str(path.resolve())
    name = path.name
    return any(resolved in line or name in line for line in process_lines)


def _matches_any(name: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)


def _base_row(path: Path, root: Path, now: float, run_path: Path | None = None) -> dict[str, object]:
    mtime = _latest_mtime(path)
    age_days = max(0.0, (now - mtime) / 86_400)
    row: dict[str, object] = {
        "root": str(root),
        "path": str(path),
        "name": path.name,
        "age_days": round(age_days, 2),
        "mtime": mtime,
        "size_bytes": _dir_size(path),
    }
    if run_path is not None:
        row["run_path"] = str(run_path)
        row["run_name"] = run_path.name
    return row


def _payload_dirs_for(run_path: Path) -> list[Path]:
    if run_path.name.lower() in PAYLOAD_DIR_NAMES:
        return [run_path]
    return [
        child
        for child in sorted(run_path.iterdir())
        if child.is_dir() and child.name.lower() in PAYLOAD_DIR_NAMES
    ]


def cleanup_heavy_runs(
    *,
    roots: Iterable[str | Path],
    execute: bool = False,
    allow_prefixes: Iterable[str] | None = None,
    preserve_patterns: Iterable[str] | None = None,
    keep_recent: int = 2,
    older_than_days: int = 7,
    now: float | None = None,
    process_lines: Iterable[str] | None = None,
) -> dict[str, object]:
    """Plan or execute cleanup of generated heavy trajectory payload directories.

    Only known heavy payload directories, such as ``stage2_trajectory_frames``,
    are deletion candidates. Parent run directories and JSON/MD/CSV summaries
    are preserved so the evidence record remains intact.
    """
    root_list = list(roots)
    now = time.time() if now is None else now
    allow_prefixes = list(DEFAULT_ALLOW_PREFIXES if allow_prefixes is None else allow_prefixes)
    preserve_patterns = list(DEFAULT_PRESERVE_PATTERNS if preserve_patterns is None else preserve_patterns)
    process_lines = _process_lines() if process_lines is None else list(process_lines)

    rows: list[dict[str, object]] = []
    candidates: list[dict[str, object]] = []
    for root_like in root_list:
        root = _resolve(root_like)
        if not root.exists():
            rows.append(
                {
                    "root": str(root),
                    "path": str(root),
                    "name": root.name,
                    "status": "kept_missing_root",
                    "reason": "root does not exist",
                }
            )
            continue
        if root.name.lower() in PAYLOAD_DIR_NAMES:
            run_path = root.parent
            row = _base_row(root, run_path.parent, now, run_path=run_path)
            if allow_prefixes and not any(run_path.name.startswith(prefix) for prefix in allow_prefixes):
                row.update(status="kept_disallowed_prefix", reason="run name does not match allowed prefixes")
            elif _matches_any(run_path.name, preserve_patterns) or _matches_any(root.name, preserve_patterns):
                row.update(status="kept_preserve_pattern", reason="run or payload name matches preserve pattern")
            elif not _has_heavy_payload(root):
                row.update(status="kept_not_heavy", reason="no heavy trajectory payload marker found")
            elif _has_active_marker(run_path):
                row.update(status="kept_active_marker", reason="lock, progress, or running marker present")
            elif _running_process_mentions(run_path, process_lines) or _running_process_mentions(root, process_lines):
                row.update(status="kept_running_process", reason="current process list mentions run directory")
            elif float(row["age_days"]) < older_than_days:
                row.update(status="kept_too_recent", reason="payload mtime is newer than older-than-days")
            else:
                row.update(status="pending", reason="eligible heavy payload for deletion")
                candidates.append(row)
            rows.append(row)
            continue
        for run_path in sorted(root.iterdir()):
            if not run_path.is_dir():
                continue
            run_name = run_path.name
            payload_dirs = _payload_dirs_for(run_path)
            if not payload_dirs:
                row = _base_row(run_path, root, now)
                row.update(status="kept_no_payload_dir", reason="no known heavy payload directory found")
                rows.append(row)
                continue
            for path in payload_dirs:
                row = _base_row(path, root, now, run_path=run_path)
                if allow_prefixes and not any(run_name.startswith(prefix) for prefix in allow_prefixes):
                    row.update(status="kept_disallowed_prefix", reason="run name does not match allowed prefixes")
                elif _matches_any(run_name, preserve_patterns) or _matches_any(path.name, preserve_patterns):
                    row.update(status="kept_preserve_pattern", reason="run or payload name matches preserve pattern")
                elif not _has_heavy_payload(path):
                    row.update(status="kept_not_heavy", reason="no heavy trajectory payload marker found")
                elif _has_active_marker(run_path):
                    row.update(status="kept_active_marker", reason="lock, progress, or running marker present")
                elif _running_process_mentions(run_path, process_lines) or _running_process_mentions(path, process_lines):
                    row.update(status="kept_running_process", reason="current process list mentions run directory")
                elif float(row["age_days"]) < older_than_days:
                    row.update(status="kept_too_recent", reason="payload mtime is newer than older-than-days")
                else:
                    row.update(status="pending", reason="eligible heavy payload for deletion")
                    candidates.append(row)
                rows.append(row)

    keep_recent = max(0, keep_recent)
    candidates_by_newest = sorted(candidates, key=lambda row: float(row["mtime"]), reverse=True)
    recent_slots = {str(row["path"]) for row in candidates_by_newest[:keep_recent]}
    deleted_count = 0
    deleted_bytes = 0
    planned_count = 0
    planned_bytes = 0
    for row in candidates:
        if str(row["path"]) in recent_slots:
            row.update(status="kept_recent_slot", reason="protected by keep-recent")
            continue
        path = Path(str(row["path"]))
        planned_count += 1
        planned_bytes += int(row["size_bytes"])
        if execute:
            shutil.rmtree(path)
            row.update(status="deleted", reason="removed by execute mode")
            deleted_count += 1
            deleted_bytes += int(row["size_bytes"])
        else:
            row.update(status="dry_run_delete", reason="would be removed; pass --execute to delete")

    return {
        "summary": {
            "status": "cleanup_executed" if execute else "dry_run",
            "execute": execute,
            "root_count": len(root_list),
            "planned_delete_count": planned_count,
            "planned_delete_bytes": planned_bytes,
            "deleted_count": deleted_count,
            "deleted_bytes": deleted_bytes,
            "keep_recent": keep_recent,
            "older_than_days": older_than_days,
            "allow_prefixes": allow_prefixes,
            "preserve_patterns": preserve_patterns,
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Safely clean generated heavy trajectory payload directories; dry-run by default."
    )
    parser.add_argument(
        "--root",
        action="append",
        dest="roots",
        help=(
            "Heavy trajectory root or payload dir to scan. May be repeated. "
            "Defaults to existing local roots plus /mnt/*/ligand_heavy_runs."
        ),
    )
    parser.add_argument("--execute", action="store_true", help="Actually delete planned directories.")
    parser.add_argument(
        "--allow-prefix",
        action="append",
        dest="allow_prefixes",
        help="Allowed generated run directory prefix. May be repeated or comma-separated.",
    )
    parser.add_argument(
        "--preserve-pattern",
        action="append",
        dest="preserve_patterns",
        help="fnmatch pattern for directory names to preserve. May be repeated or comma-separated.",
    )
    parser.add_argument("--keep-recent", type=int, default=2, help="Keep this many newest eligible runs.")
    parser.add_argument("--older-than-days", type=int, default=7, help="Only delete runs at least this old.")
    parser.add_argument("--out-json", help="Optional path for the cleanup report JSON.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    roots = args.roots or _default_roots()
    allow_prefixes = _split_values(args.allow_prefixes) or list(DEFAULT_ALLOW_PREFIXES)
    preserve_patterns = _split_values(args.preserve_patterns) or list(DEFAULT_PRESERVE_PATTERNS)
    report = cleanup_heavy_runs(
        roots=roots,
        execute=args.execute,
        allow_prefixes=allow_prefixes,
        preserve_patterns=preserve_patterns,
        keep_recent=args.keep_recent,
        older_than_days=args.older_than_days,
    )
    text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.out_json:
        out_json = _resolve(args.out_json)
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
