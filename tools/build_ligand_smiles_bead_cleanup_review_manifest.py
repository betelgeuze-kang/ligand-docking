#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.build_runs_cleanup_batch4_stage_review_manifest import _resolve
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNS_DIR = "runs"
DEFAULT_OUT_JSON = "runs/ligand_smiles_bead_cleanup_review_manifest_current.json"
DEFAULT_OUT_CSV = "runs/ligand_smiles_bead_cleanup_review_manifest_current.csv"
DEFAULT_OUT_MD = "runs/ligand_smiles_bead_cleanup_review_manifest_current.md"

KEEP_FILE = "ligand_smiles_bead_cache.json"


def _file_size(path: Path) -> int:
    return path.stat().st_size if path.is_file() else 0


def _has_repo_reference(project_root: Path, filename: str) -> bool:
    candidate_files = list((project_root / "config").glob("*.json"))
    candidate_files += list((project_root / "tools").glob("*.py"))
    candidate_files += list((project_root / "runs").glob("*_current.*"))
    for path in candidate_files:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if filename in text:
            return True
    return False


def build_payload(runs_dir: str) -> dict[str, Any]:
    runs_root = _resolve(runs_dir)
    project_root = runs_root.parent
    files = sorted(path for path in runs_root.glob("ligand_smiles_bead_cache*.json") if path.is_file())
    rows: list[dict[str, Any]] = []
    keep_size = 0
    archive_bytes = 0
    for path in files:
        if path.name == KEEP_FILE:
            recommended = "keep_in_active_root"
            classification = "shared_default_cache"
            reason = "Default HTVS pipeline cache path still points here, so keep one shared cache in active root."
        elif _has_repo_reference(project_root, path.name):
            recommended = "keep_in_active_root"
            classification = "active_config_cache"
            reason = "Current config or current artifacts still reference this target-specific cache path, so keep it until config routing is changed."
        else:
            recommended = "archive_first"
            classification = "target_specific_cache"
            reason = "Target-specific cache file is rebuildable and not referenced by current configs or current artifacts, so it can move to archive-first storage."
        if recommended == "keep_in_active_root":
            keep_size += _file_size(path)
        else:
            archive_bytes += _file_size(path)
        rows.append(
            {
                "filename": path.name,
                "classification": classification,
                "recommended_disposition": recommended,
                "size_mb": round(_file_size(path) / (1024 * 1024), 2),
                "reason": reason,
            }
        )

    summary = {
        "status": "ligand_smiles_bead_cleanup_review_manifest_ready",
        "runs_dir": str(runs_root),
        "file_count": len(files),
        "keep_in_active_root_count": len([row for row in rows if row["recommended_disposition"] == "keep_in_active_root"]),
        "archive_candidate_count": len([row for row in rows if row["recommended_disposition"] == "archive_first"]),
        "archive_candidate_size_gb": round(archive_bytes / (1024 * 1024 * 1024), 2),
        "next_required_step": "Archive the target-specific cache files, keep the shared default cache in active root, then rebuild the cleanup audit.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Ligand SMILES Bead Cleanup Review Manifest",
        "",
        f"- status: `{s['status']}`",
        f"- runs_dir: `{s['runs_dir']}`",
        f"- file_count: `{s['file_count']}`",
        f"- keep_in_active_root_count: `{s['keep_in_active_root_count']}`",
        f"- archive_candidate_count: `{s['archive_candidate_count']}`",
        f"- archive_candidate_size_gb: `{s['archive_candidate_size_gb']}`",
        "",
        "| filename | classification | size_mb | recommended_disposition |",
        "| --- | --- | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['filename']}` | `{row['classification']}` | `{row['size_mb']}` | `{row['recommended_disposition']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a cleanup review manifest for ligand_smiles_bead caches.")
    parser.add_argument("--runs-dir", default=DEFAULT_RUNS_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args.runs_dir)
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
