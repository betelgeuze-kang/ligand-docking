#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import shutil
import subprocess
import tarfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


TOP_SUMMARY_RE = re.compile(r"(.+)_summary\.json$")
PER_RUN_RE = re.compile(r".+(?:_p\d+)?_n\d+_r\d+$")
STAGE_RE = re.compile(r".+_stage\d+.*$")


def _detect_ubuntu1_mount() -> str:
    candidates = [
        "/mnt/ubuntu-1",
        "/media/betelgeuze/ubuntu-1",
        "/home/betelgeuze/ubuntu-1",
    ]
    for c in candidates:
        if os.path.isdir(c):
            return c
    try:
        out = subprocess.check_output(
            ["lsblk", "-o", "LABEL,MOUNTPOINT", "-n"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        for line in out.splitlines():
            cols = [x for x in line.strip().split() if x]
            if len(cols) >= 2 and cols[0] == "ubuntu-1":
                mp = cols[1]
                if os.path.isdir(mp):
                    return mp
    except Exception:
        pass
    return ""


def _default_archive_dir() -> str:
    mp = _detect_ubuntu1_mount()
    if mp:
        return os.path.join(mp, "ligand_stress_archives")
    return "archives/ligand_stress_runs"


def _is_top_level_summary(path: str) -> bool:
    base = os.path.basename(path)
    if (
        "_stage" in base
        or "_post_" in base
        or "_smoke_" in base
        or "_hard_decoy" in base
        or "_sla" in base
        or "_failure_" in base
        or "_debug_" in base
    ):
        return False
    if not base.endswith("_summary.json"):
        return False
    prefix = base[: -len("_summary.json")]
    if PER_RUN_RE.match(prefix):
        return False
    if STAGE_RE.match(prefix):
        return False
    return True


def _collect_prefixes(prefix_glob: str) -> List[str]:
    found: List[str] = []
    for path in glob.glob(prefix_glob):
        if not _is_top_level_summary(path):
            continue
        found.append(path[: -len("_summary.json")])
    return sorted(set(found))


def _mtime(path: str) -> float:
    try:
        return float(os.path.getmtime(path))
    except Exception:
        return 0.0


def _bundle_files(prefix: str) -> List[str]:
    files = sorted(glob.glob(f"{prefix}*"))
    return [p for p in files if os.path.isfile(p)]


def _read_json(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def run_archive(args: argparse.Namespace) -> Dict[str, Any]:
    policy = _read_json(str(args.policy_json)) if str(getattr(args, "policy_json", "")).strip() else {}
    prefix_glob = str(args.prefix_glob)
    if isinstance(policy.get("prefix_glob"), str) and policy.get("prefix_glob"):
        prefix_glob = str(policy.get("prefix_glob"))
    prefixes = _collect_prefixes(prefix_glob)
    excludes = {str(x).strip() for x in (args.exclude_prefix or []) if str(x).strip()}
    if isinstance(policy.get("exclude_prefixes"), list):
        excludes.update(str(x).strip() for x in policy.get("exclude_prefixes", []) if str(x).strip())
    prefixes = [p for p in prefixes if p not in excludes]
    prefixes.sort(key=lambda p: _mtime(f"{p}_summary.json"), reverse=True)
    keep_latest = int(max(args.keep_latest, 0))
    if policy.get("keep_latest") is not None:
        try:
            keep_latest = int(max(int(policy.get("keep_latest")), 0))
        except Exception:
            pass
    keep = set(prefixes[:keep_latest])
    archive_targets = [p for p in prefixes if p not in keep]

    archive_dir_str = str(args.archive_dir).strip()
    if isinstance(policy.get("archive_dir"), str) and policy.get("archive_dir"):
        archive_dir_str = str(policy.get("archive_dir"))
    archive_dir = Path(archive_dir_str or _default_archive_dir())
    archive_dir.mkdir(parents=True, exist_ok=True)

    archived: List[Dict[str, Any]] = []
    removed_files = 0
    archived_files = 0
    for prefix in archive_targets:
        files = _bundle_files(prefix)
        if not files:
            continue
        stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        tar_path = archive_dir / f"{os.path.basename(prefix)}_{stamp}.tar.gz"
        if not bool(args.dry_run):
            with tarfile.open(tar_path, "w:gz") as tf:
                for path in files:
                    tf.add(path, arcname=os.path.basename(path))
        if bool(args.delete_after_archive) and (not bool(args.dry_run)):
            for path in files:
                try:
                    os.remove(path)
                    removed_files += 1
                except Exception:
                    pass
        archived_files += len(files)
        archived.append(
            {
                "prefix": prefix,
                "file_count": len(files),
                "archive_path": str(tar_path),
            }
        )

    out = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "prefix_glob": str(prefix_glob),
        "archive_dir": str(archive_dir),
        "keep_latest": int(keep_latest),
        "dry_run": bool(args.dry_run),
        "delete_after_archive": bool(args.delete_after_archive),
        "policy_json": str(getattr(args, "policy_json", "") or ""),
        "policy": policy,
        "discovered_prefixes": prefixes,
        "kept_prefixes": sorted(keep),
        "archived_count": len(archived),
        "archived_files": archived_files,
        "removed_files": removed_files,
        "archived": archived,
    }
    out_json = str(args.out_json).strip()
    if out_json:
        os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
            f.write("\n")
    return out


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(description="Archive old top-level ligand stress run bundles.")
    p.add_argument("--policy-json", type=str, default="")
    p.add_argument("--prefix-glob", type=str, default="runs/ligand_stress*_summary.json")
    p.add_argument("--exclude-prefix", action="append", default=[])
    p.add_argument("--keep-latest", type=int, default=8)
    p.add_argument("--archive-dir", type=str, default="")
    p.add_argument("--delete-after-archive", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--out-json", type=str, default=f"runs/ligand_stress_archive_{stamp}.json")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_archive(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
