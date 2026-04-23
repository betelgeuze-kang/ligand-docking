#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from typing import Any, Dict, Optional, Sequence

from tools.run_live_unseen_protein_learning_loop import _cleanup_old_cycle_artifacts


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(
        description=(
            "One-shot maintenance for live_unseen per-cycle artifacts: keep recent cycles and "
            "archive older files."
        )
    )
    p.add_argument("--out-prefix", type=str, default="runs/live_unseen_learning_hip")
    p.add_argument("--date-tag-prefix", type=str, default="live_unseen_hip")
    p.add_argument("--keep-recent-cycles", type=int, default=20)
    p.add_argument("--archive-dir", type=str, default="archives/live_unseen_runs")
    p.add_argument("--compress-to-archive", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--delete-after-archive", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--out-json", type=str, default=f"runs/live_unseen_archive_maintenance_{stamp}.json")
    return p


def run_maintenance(args: argparse.Namespace) -> Dict[str, Any]:
    payload = _cleanup_old_cycle_artifacts(
        out_prefix=str(args.out_prefix),
        date_tag_prefix=str(args.date_tag_prefix),
        keep_recent_cycles=int(args.keep_recent_cycles),
        dry_run=bool(args.dry_run),
        compress_to_archive=bool(args.compress_to_archive),
        archive_dir=str(args.archive_dir),
        delete_after_archive=bool(args.delete_after_archive),
    )
    out = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "out_prefix": str(args.out_prefix),
        "date_tag_prefix": str(args.date_tag_prefix),
        "keep_recent_cycles": int(args.keep_recent_cycles),
        "archive_dir": str(args.archive_dir),
        "dry_run": bool(args.dry_run),
        "result": payload,
    }
    out_json = str(args.out_json).strip()
    if out_json:
        os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
    return out


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_maintenance(args)
    result = payload.get("result", {}) if isinstance(payload.get("result"), dict) else {}
    bundle_count = int(result.get("archive_count", len(result.get("archived", []) or [])) or 0)
    print(
        json.dumps(
            {
                "out_json": str(args.out_json),
                "dry_run": bool(args.dry_run),
                "removed_files": int(result.get("removed_files", 0) or 0),
                "archived_files": int(result.get("archived_files", 0) or 0),
                "archived_bundles": bundle_count,
                "kept_cycles": result.get("kept_cycles", []),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
