#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNS_DIR = "runs"
DEFAULT_OUT_JSON = "runs/runs_cleanup_batch2_manifest_current.json"
DEFAULT_OUT_CSV = "runs/runs_cleanup_batch2_manifest_current.csv"
DEFAULT_OUT_MD = "runs/runs_cleanup_batch2_manifest_current.md"

SAFE_GLOB_PATTERNS = [
    ("archive_compress", "archive_2026-03-29_external_validation_batch1"),
    ("archive_move", "idp_virtual_hbond*"),
    ("archive_move", "idp_3bead_vhbond*"),
    ("archive_move", "ligand_blind_gpcr*.lock"),
    ("archive_move", "ligand_blind_gpcr*_live.log"),
    ("archive_move", "ligand_blind_trpv1*.lock"),
    ("archive_move", "ligand_blind_trpv1*_live.log"),
    ("archive_move", "ligand_stress_commercial*.lock"),
    ("archive_move", "ligand_stress_commercial*_live.log"),
]
REVIEW_ONLY_PREFIXES = [
    "ligand_blind_gpcr*",
    "ligand_blind_trpv1*",
    "ligand_stress_commercial*",
]


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _match_size_bytes(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    if path.is_dir():
        return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return 0


def build_payload(runs_dir: str, archive_stamp: str) -> dict[str, Any]:
    root = _resolve(runs_dir)
    archive_root = root / f"archive_{archive_stamp}_safe_batch2"
    compressed_archive_path = root / "archive_2026-03-29_external_validation_batch1.tar.gz"

    rows: list[dict[str, Any]] = []
    safe_item_count = 0
    safe_size_bytes = 0
    for action, pattern in SAFE_GLOB_PATTERNS:
        matches = sorted(root.glob(pattern))
        size_bytes = sum(_match_size_bytes(path) for path in matches)
        rows.append(
            {
                "action": action,
                "match_pattern": pattern,
                "match_count": len(matches),
                "size_mb": round(size_bytes / (1024 * 1024), 2),
                "archive_subdir": str(Path(archive_root.name) / pattern.replace("*", "_glob")),
                "apply_now": bool(matches),
                "reason": (
                    "Compress the existing batch1 archive to a tarball, then remove the original directory if the tarball is written successfully."
                    if action == "archive_compress"
                    else "Safe-now archive target or stale top-level lock/log pattern that can be removed from the active runs root."
                ),
            }
        )
        if matches:
            safe_item_count += 1
            safe_size_bytes += size_bytes

    for pattern in REVIEW_ONLY_PREFIXES:
        rows.append(
            {
                "action": "review_only",
                "match_pattern": pattern,
                "match_count": 0,
                "size_mb": 0.0,
                "archive_subdir": "",
                "apply_now": False,
                "reason": "Large pipeline family: keep for manual review instead of sweeping it in this pass.",
            }
        )

    rows.extend(
        [
            {
                "action": "protect_hold",
                "match_pattern": "idp_3bead_holdout*",
                "match_count": 0,
                "size_mb": 0.0,
                "archive_subdir": "",
                "apply_now": False,
                "reason": "Protected because current IDP decision and repeatability surfaces still depend on these outputs.",
            },
            {
                "action": "protect_hold",
                "match_pattern": "*_current.*",
                "match_count": 0,
                "size_mb": 0.0,
                "archive_subdir": "",
                "apply_now": False,
                "reason": "Always protect current artifacts and outbound wet-lab packets.",
            },
        ]
    )

    summary = {
        "status": "runs_cleanup_batch2_manifest_ready",
        "runs_dir": str(root),
        "archive_root": str(archive_root),
        "compressed_archive_output": str(compressed_archive_path),
        "safe_apply_pattern_count": safe_item_count,
        "safe_apply_size_gb": round(safe_size_bytes / (1024 * 1024 * 1024), 2),
        "review_only_pattern_count": len(REVIEW_ONLY_PREFIXES),
        "next_required_step": "Compress the existing external-validation archive, move safe vhbond and stale lock/log files into the batch2 archive, then rebuild the cleanup audit.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Runs Cleanup Batch2 Manifest",
        "",
        f"- status: `{s['status']}`",
        f"- runs_dir: `{s['runs_dir']}`",
        f"- archive_root: `{s['archive_root']}`",
        f"- compressed_archive_output: `{s['compressed_archive_output']}`",
        f"- safe_apply_pattern_count: `{s['safe_apply_pattern_count']}`",
        f"- safe_apply_size_gb: `{s['safe_apply_size_gb']}`",
        f"- review_only_pattern_count: `{s['review_only_pattern_count']}`",
        "",
        "| action | match_pattern | match_count | size_mb | apply_now | archive_subdir |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['action']}` | `{row['match_pattern']}` | `{row['match_count']}` | `{row['size_mb']}` | `{row['apply_now']}` | `{row['archive_subdir']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a safe batch2 cleanup manifest with real disk-reclaim steps.")
    parser.add_argument("--runs-dir", default=DEFAULT_RUNS_DIR)
    parser.add_argument("--archive-stamp", default="2026-03-29")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(args.runs_dir, args.archive_stamp)
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
