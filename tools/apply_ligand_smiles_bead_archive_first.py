#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from tools.build_runs_cleanup_batch4_stage_review_manifest import _resolve
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_JSON = "runs/ligand_smiles_bead_cleanup_review_manifest_current.json"
DEFAULT_ARCHIVE_ROOT = "runs/archive/ligand_smiles_bead_archive_first_current"
DEFAULT_OUT_JSON = "runs/ligand_smiles_bead_archive_first_apply_report_current.json"
DEFAULT_OUT_CSV = "runs/ligand_smiles_bead_archive_first_apply_report_current.csv"
DEFAULT_OUT_MD = "runs/ligand_smiles_bead_archive_first_apply_report_current.md"


def _load_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _size_bytes(path: Path) -> int:
    return path.stat().st_size if path.is_file() else 0


def apply_manifest(manifest: dict[str, Any], *, archive_root: str = DEFAULT_ARCHIVE_ROOT) -> dict[str, Any]:
    runs_root = _resolve("runs")
    archive_root_path = _resolve(archive_root)
    archive_root_path.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    moved_file_count = 0
    moved_bytes = 0
    applied_row_count = 0

    for manifest_row in manifest.get("rows", []) or []:
        if manifest_row.get("recommended_disposition") != "archive_first":
            continue
        filename = str(manifest_row.get("filename", "")).strip()
        src = runs_root / filename
        dst = archive_root_path / filename
        out_row = {
            "filename": filename,
            "classification": str(manifest_row.get("classification", "")),
            "size_mb": float(manifest_row.get("size_mb", 0.0) or 0.0),
            "status": "",
        }
        if not src.exists():
            out_row["status"] = "no_match"
            rows.append(out_row)
            continue
        if dst.exists():
            out_row["status"] = "destination_exists_skipped"
            rows.append(out_row)
            continue
        moved_bytes += _size_bytes(src)
        shutil.move(str(src), str(dst))
        moved_file_count += 1
        applied_row_count += 1
        out_row["status"] = "archived"
        rows.append(out_row)

    summary = {
        "status": "ligand_smiles_bead_archive_first_apply_report_ready",
        "archive_root": str(archive_root_path),
        "manifest_row_count": len([row for row in manifest.get("rows", []) or [] if row.get("recommended_disposition") == "archive_first"]),
        "applied_row_count": applied_row_count,
        "moved_file_count": moved_file_count,
        "moved_size_gb": round(moved_bytes / (1024 * 1024 * 1024), 2),
        "next_required_step": "Compress the cache archive root if you want additional top-level declutter, then rebuild the cleanup audit.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Ligand SMILES Bead Archive-First Apply Report",
        "",
        f"- status: `{s['status']}`",
        f"- archive_root: `{s['archive_root']}`",
        f"- manifest_row_count: `{s['manifest_row_count']}`",
        f"- applied_row_count: `{s['applied_row_count']}`",
        f"- moved_file_count: `{s['moved_file_count']}`",
        f"- moved_size_gb: `{s['moved_size_gb']}`",
        "",
        "| filename | classification | size_mb | status |",
        "| --- | --- | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['filename']}` | `{row['classification']}` | `{row['size_mb']}` | `{row['status']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Archive-first apply for ligand_smiles_bead target-specific caches.")
    parser.add_argument("--manifest-json", default=DEFAULT_MANIFEST_JSON)
    parser.add_argument("--archive-root", default=DEFAULT_ARCHIVE_ROOT)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = apply_manifest(_load_json(args.manifest_json), archive_root=args.archive_root)
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
