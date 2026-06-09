#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST_CSV = "runs/residual_force_trajectory_regeneration_current_manifest.csv"
DEFAULT_OUT_JSON = "runs/residual_force_gpu_worker_return_manifest_finalize_current.json"

OK_STATUSES = {"ok", "ok_npz_bundle", "ok_regenerated_npz", "ok_full_regeneration", "ok_cached"}


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def finalize_manifest(manifest_csv: str) -> dict[str, Any]:
    path = _resolve(manifest_csv)
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]

    if "operator_verified_npz_exists" not in fieldnames:
        fieldnames.append("operator_verified_npz_exists")
    if "generated_npz" not in fieldnames:
        fieldnames.append("generated_npz")

    verified_true = 0
    missing_npz = 0
    for row in rows:
        status = str(row.get("status", "")).strip().lower()
        npz_path = str(row.get("trajectory_npz") or row.get("generated_npz") or "").strip()
        row["generated_npz"] = npz_path
        if status in OK_STATUSES and npz_path and _resolve(npz_path).exists():
            row["operator_verified_npz_exists"] = "true"
            verified_true += 1
        else:
            row["operator_verified_npz_exists"] = "false"
            if status in OK_STATUSES:
                missing_npz += 1

    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    ready = verified_true == len(rows) and len(rows) > 0 and missing_npz == 0
    return {
        "packet_type": "residual_force_gpu_worker_return_manifest_finalize",
        "status": "residual_force_gpu_worker_return_manifest_finalize_ready" if ready else "blocked_residual_force_gpu_worker_return_manifest_finalize",
        "manifest_csv": manifest_csv,
        "manifest_row_count": len(rows),
        "operator_verified_true_count": verified_true,
        "missing_npz_count": missing_npz,
        "next_required_step": (
            "Rerun tools/build_residual_force_gpu_worker_return_receipt.py."
            if ready
            else "Repair missing NPZ paths before finalizing operator verification."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Finalize GPU return manifest with operator NPZ verification.")
    parser.add_argument("--manifest-csv", default=DEFAULT_MANIFEST_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = finalize_manifest(args.manifest_csv)
    out = _resolve(args.out_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
