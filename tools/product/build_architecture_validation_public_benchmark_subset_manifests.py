#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/architecture_validation_public_benchmark_subset_manifests_current.json"

CLAIM_BOUNDARY = (
    "Public benchmark subset manifest builder only; documents held-out subset selection policy "
    "for Package B pose/complex validation. It does not rerun docking or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_csv_rows(path: Path, limit: int) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return rows[:limit]


def build_public_benchmark_subset_manifests(*, subset_size: int = 100) -> dict[str, Any]:
    pdbbind_full = _resolve("runs/pdbbind_casf_pose_affinity_benchmark_results_current.csv")
    bm5_full = _resolve("runs/protein_protein_docking_benchmark_v5_benchmark_results_current.csv")
    pdbbind_rows = _read_csv_rows(pdbbind_full, subset_size)
    bm5_rows = _read_csv_rows(bm5_full, subset_size)

    pdbbind_out = _resolve("runs/pdbbind_casf_pose_affinity_benchmark_subset_current.csv")
    bm5_out = _resolve("runs/protein_protein_docking_benchmark_v5_benchmark_subset_current.csv")
    pdbbind_out.parent.mkdir(parents=True, exist_ok=True)
    if pdbbind_rows:
        with pdbbind_out.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(pdbbind_rows[0].keys()))
            writer.writeheader()
            writer.writerows(pdbbind_rows)
    if bm5_rows:
        with bm5_out.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(bm5_rows[0].keys()))
            writer.writeheader()
            writer.writerows(bm5_rows)

    bm5_provenance = _resolve("runs/protein_protein_docking_benchmark_v5_result_provenance_current.json")
    proxy_disclaimer_present = False
    if bm5_provenance.exists():
        prov = json.loads(bm5_provenance.read_text(encoding="utf-8"))
        text_blob = json.dumps(prov, ensure_ascii=False).lower()
        proxy_disclaimer_present = "proxy" in text_blob or "rigid" in text_blob

    summary = {
        "packet_type": "architecture_validation_public_benchmark_subset_manifests",
        "status": "architecture_validation_public_benchmark_subset_manifests_ready"
        if pdbbind_rows and bm5_rows
        else "blocked_architecture_validation_public_benchmark_subset_manifests",
        "subset_size": subset_size,
        "selection_policy": "deterministic_prefix_of_existing_full_benchmark_results_csv",
        "pdbbind_casf_subset_ready": bool(pdbbind_rows),
        "pdbbind_casf_subset_row_count": len(pdbbind_rows),
        "pdbbind_casf_subset_csv": str(pdbbind_out.relative_to(ROOT)),
        "pdbbind_casf_full_csv": str(pdbbind_full.relative_to(ROOT)),
        "bm5_subset_ready": bool(bm5_rows),
        "bm5_subset_row_count": len(bm5_rows),
        "bm5_subset_csv": str(bm5_out.relative_to(ROOT)),
        "bm5_full_csv": str(bm5_full.relative_to(ROOT)),
        "bm5_proxy_disclaimer_present": proxy_disclaimer_present,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build public benchmark subset manifests for Package B.")
    parser.add_argument("--subset-size", type=int, default=100)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    args = parser.parse_args(argv)
    payload = build_public_benchmark_subset_manifests(subset_size=args.subset_size)
    _resolve(args.out_json).write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
