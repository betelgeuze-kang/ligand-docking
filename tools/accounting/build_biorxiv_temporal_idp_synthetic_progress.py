#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _status(row: dict[str, str]) -> str:
    has_source = (row.get("provenance_source") or "").strip()
    has_date = any((row.get(key) or "").strip() for key in ("publication_year", "benchmark_inclusion_date", "corrected_label_freeze_date"))
    granularity = (row.get("provenance_granularity") or "").strip().lower()
    if has_source and has_date:
        if granularity.startswith("item"):
            return "item_ready"
        return "dataset_ready"
    if has_source or has_date or granularity:
        return "partial"
    return "missing"


def main() -> int:
    ap = argparse.ArgumentParser(description="Summarize progress on synthetic-IDP temporal provenance curation.")
    ap.add_argument("--idp-csv", default="config/biorxiv_temporal_idp_provenance_v1.csv")
    ap.add_argument("--out-json", default="runs/biorxiv_temporal_idp_synthetic_progress_current.json")
    ap.add_argument("--out-csv", default="runs/biorxiv_temporal_idp_synthetic_progress_current.csv")
    ap.add_argument("--out-md", default="runs/biorxiv_temporal_idp_synthetic_progress_current.md")
    args = ap.parse_args()

    rows = _read_csv((ROOT / args.idp_csv).resolve())
    synthetic_rows = [row for row in rows if (row.get("source_kind") or "").strip() == "synthetic"]
    item_rows = [row for row in synthetic_rows if _status(row) == "item_ready"]
    dataset_rows = [row for row in synthetic_rows if _status(row) == "dataset_ready"]

    curated_rows = [
        {
            "holdout_name": row.get("holdout_name", ""),
            "publication_year": row.get("publication_year", ""),
            "provenance_source": row.get("provenance_source", ""),
            "curation_status": row.get("curation_status", ""),
            "notes": row.get("notes", ""),
        }
        for row in sorted(item_rows, key=lambda row: row.get("holdout_name", ""))
    ]
    unresolved_rows = [
        {
            "holdout_name": row.get("holdout_name", ""),
            "benchmark_inclusion_date": row.get("benchmark_inclusion_date", ""),
            "corrected_label_freeze_date": row.get("corrected_label_freeze_date", ""),
            "provenance_source": row.get("provenance_source", ""),
            "curation_status": row.get("curation_status", ""),
            "notes": row.get("notes", ""),
        }
        for row in sorted(dataset_rows, key=lambda row: row.get("holdout_name", ""))
    ]

    summary = {
        "synthetic_row_count": len(synthetic_rows),
        "item_ready_count": len(item_rows),
        "dataset_ready_count": len(dataset_rows),
        "curated_item_rows": curated_rows,
        "remaining_dataset_rows": unresolved_rows,
    }
    _write_json((ROOT / args.out_json).resolve(), summary)

    csv_rows: list[dict[str, Any]] = []
    for row in curated_rows:
        csv_rows.append({"status": "item_ready", **row})
    for row in unresolved_rows:
        csv_rows.append({"status": "dataset_ready", **row})
    _write_csv(
        (ROOT / args.out_csv).resolve(),
        csv_rows,
        [
            "status",
            "holdout_name",
            "publication_year",
            "benchmark_inclusion_date",
            "corrected_label_freeze_date",
            "provenance_source",
            "curation_status",
            "notes",
        ],
    )

    lines = [
        "# IDP Synthetic Temporal Progress",
        "",
        f"- synthetic_row_count: `{len(synthetic_rows)}`",
        f"- item_ready_count: `{len(item_rows)}`",
        f"- dataset_ready_count: `{len(dataset_rows)}`",
        "",
        "## Item-Ready Synthetic Holdouts",
        "",
    ]
    if curated_rows:
        for row in curated_rows:
            lines.extend(
                [
                    f"### {row['holdout_name']}",
                    "",
                    f"- publication_year: `{row['publication_year']}`",
                    f"- provenance_source: `{row['provenance_source']}`",
                    f"- curation_status: `{row['curation_status']}`",
                    "",
                ]
            )
    else:
        lines.extend(["- none", ""])

    lines.extend(["## Remaining Dataset-Ready Synthetic Holdouts", ""])
    if unresolved_rows:
        for row in unresolved_rows:
            lines.extend(
                [
                    f"### {row['holdout_name']}",
                    "",
                    f"- benchmark_inclusion_date: `{row['benchmark_inclusion_date']}`",
                    f"- corrected_label_freeze_date: `{row['corrected_label_freeze_date']}`",
                    f"- provenance_source: `{row['provenance_source']}`",
                    f"- curation_status: `{row['curation_status']}`",
                    f"- notes: {row['notes']}",
                    "",
                ]
            )
    else:
        lines.extend(["- none", ""])
    _write_text((ROOT / args.out_md).resolve(), "\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
