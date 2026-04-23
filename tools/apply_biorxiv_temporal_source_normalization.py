#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _source_family(source_label: str) -> str:
    if source_label.startswith("chembl_blind_adrb2_v1:"):
        return "chembl_blind_adrb2_v1"
    return source_label or "unknown"


def main() -> int:
    ap = argparse.ArgumentParser(description="Apply family-level source normalization defaults to the ligand temporal provenance CSV.")
    ap.add_argument("--ligand-csv", default="config/biorxiv_temporal_ligand_provenance_v1.csv")
    ap.add_argument("--normalization-csv", default="config/biorxiv_temporal_source_normalization_v1.csv")
    ap.add_argument("--out-csv", default="config/biorxiv_temporal_ligand_provenance_v1.csv")
    args = ap.parse_args()

    ligand_path = (ROOT / args.ligand_csv).resolve()
    normalization_path = (ROOT / args.normalization_csv).resolve()
    out_path = (ROOT / args.out_csv).resolve()

    rows = _read_csv(ligand_path)
    mappings = {
        row["source_family"]: row
        for row in _read_csv(normalization_path)
    }

    for row in rows:
        mapping = mappings.get(_source_family(row["source_label"]))
        if not mapping:
            continue
        if not row.get("source_release", "").strip():
            row["source_release"] = mapping.get("normalized_source_release", "")
        if not row.get("provenance_granularity", "").strip():
            row["provenance_granularity"] = mapping.get("provenance_granularity", "")
        if not row.get("provenance_url", "").strip():
            row["provenance_url"] = mapping.get("provenance_url", "")
        if row.get("curation_status", "").strip() in {"", "pending"}:
            row["curation_status"] = mapping.get("default_curation_status", row.get("curation_status", "pending"))
        note = mapping.get("notes", "").strip()
        if note and not row.get("notes", "").strip():
            row["notes"] = note

    fieldnames = list(rows[0].keys()) if rows else []
    _write_csv(out_path, rows, fieldnames)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
