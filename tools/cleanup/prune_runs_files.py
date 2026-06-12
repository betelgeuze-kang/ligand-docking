#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from tools.classify_runs_files import _classify, _role_for_latest


def _iter_target_files(runs_dir: Path, exts: Sequence[str]) -> List[Path]:
    ext_set = {e.lower().strip() for e in exts if str(e).strip()}
    files: List[Path] = []
    for p in runs_dir.iterdir():
        if not p.is_file():
            continue
        if p.name.startswith("."):
            continue
        if p.name.startswith("INDEX") or p.name.startswith("LATEST"):
            continue
        if p.suffix.lower() not in ext_set:
            continue
        files.append(p)
    return files


def _build_groups(files: Sequence[Path]) -> Dict[Tuple[str, str], List[Path]]:
    groups: Dict[Tuple[str, str], List[Path]] = {}
    for fp in files:
        cat = _classify(fp.name)
        role = _role_for_latest(fp.name)
        key = (cat, role)
        groups.setdefault(key, []).append(fp)
    for key, vals in groups.items():
        vals.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        groups[key] = vals
    return groups


def _should_protect(name: str, protect_prefixes: Sequence[str]) -> bool:
    for pref in protect_prefixes:
        p = str(pref).strip()
        if p and name.startswith(p):
            return True
    return False


def prune_runs_files(
    runs_dir: str = "runs",
    keep_per_role: int = 2,
    exts: Optional[Sequence[str]] = None,
    protect_prefixes: Optional[Sequence[str]] = None,
    dry_run: bool = False,
    archive_root: str = "_archive_pruned",
) -> Dict[str, object]:
    root = Path(runs_dir)
    if not root.exists():
        raise FileNotFoundError(f"runs directory not found: {runs_dir}")

    keep = max(1, int(keep_per_role))
    extensions = list(exts or [".csv", ".json"])
    protected = list(protect_prefixes or [])
    files = _iter_target_files(root, extensions)
    groups = _build_groups(files)

    date_tag = dt.date.today().isoformat()
    archive_dir = root / archive_root / date_tag
    moved: List[Dict[str, str]] = []
    scanned = 0

    for (cat, role), paths in sorted(groups.items()):
        scanned += len(paths)
        keep_count = 0
        for fp in paths:
            if keep_count < keep:
                keep_count += 1
                continue
            if _should_protect(fp.name, protected):
                continue
            dst_dir = archive_dir / cat
            dst_dir.mkdir(parents=True, exist_ok=True)
            dst = dst_dir / fp.name
            if dst.exists():
                stem = dst.stem
                suf = dst.suffix
                idx = 2
                while dst.exists():
                    dst = dst_dir / f"{stem}__{idx}{suf}"
                    idx += 1
            moved.append(
                {
                    "file": str(fp),
                    "category": cat,
                    "role": role,
                    "dest": str(dst),
                }
            )
            if not dry_run:
                shutil.move(str(fp), str(dst))

    return {
        "runs_dir": str(root),
        "keep_per_role": keep,
        "extensions": extensions,
        "dry_run": bool(dry_run),
        "protected_prefixes": protected,
        "scanned_files": scanned,
        "moved_files": len(moved),
        "archive_dir": str(archive_dir),
        "moved": moved,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Archive old runs/*.csv and runs/*.json files by category+role retention."
    )
    p.add_argument("--runs-dir", type=str, default="runs")
    p.add_argument("--keep-per-role", type=int, default=2)
    p.add_argument("--ext", action="append", default=[".csv", ".json"])
    p.add_argument("--protect-prefix", action="append", default=[])
    p.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--archive-root", type=str, default="_archive_pruned")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    payload = prune_runs_files(
        runs_dir=str(args.runs_dir),
        keep_per_role=int(args.keep_per_role),
        exts=list(args.ext),
        protect_prefixes=list(args.protect_prefix),
        dry_run=bool(args.dry_run),
        archive_root=str(args.archive_root),
    )
    print(f"Scanned: {payload['scanned_files']} files")
    print(f"Moved: {payload['moved_files']} files")
    print(f"Archive: {payload['archive_dir']}")


if __name__ == "__main__":
    main()
