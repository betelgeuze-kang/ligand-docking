#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _has_any_value(row: dict[str, str], columns: set[str]) -> bool:
    return any(row.get(col, "").strip() for col in columns)


def _status_from_required(
    row: dict[str, str],
    required_any: list[list[str]],
    required_all: list[str],
    *,
    granularity_field: str | None = None,
) -> str:
    all_ok = all((row.get(col, "").strip() for col in required_all))
    any_groups_ok = all(any(row.get(col, "").strip() for col in group) for group in required_any)
    if all_ok and any_groups_ok:
        if granularity_field:
            granularity = row.get(granularity_field, "").strip().lower()
            if granularity.startswith("item"):
                return "item_ready"
            return "dataset_ready"
        return "item_ready"
    relevant_columns = set(required_all)
    for group in required_any:
        relevant_columns.update(group)
    if granularity_field:
        relevant_columns.add(granularity_field)
    if _has_any_value(row, relevant_columns):
        return "partial"
    return "missing"


def _summarize(
    rows: list[dict[str, str]],
    required_any: list[list[str]],
    required_all: list[str],
    label: str,
    *,
    granularity_field: str | None = None,
) -> dict[str, Any]:
    statuses = [
        _status_from_required(
            row,
            required_any,
            required_all,
            granularity_field=granularity_field,
        )
        for row in rows
    ]
    counts = Counter(statuses)
    return {
        "label": label,
        "row_count": len(rows),
        "ready_count": counts.get("item_ready", 0) + counts.get("dataset_ready", 0),
        "item_ready_count": counts.get("item_ready", 0),
        "dataset_ready_count": counts.get("dataset_ready", 0),
        "partial_count": counts.get("partial", 0),
        "missing_count": counts.get("missing", 0),
        "required_all": required_all,
        "required_any": required_any,
        "granularity_field": granularity_field,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Summarize coverage of editable temporal provenance mapping CSVs.")
    ap.add_argument("--ligand-csv", default="config/biorxiv_temporal_ligand_provenance_v1.csv")
    ap.add_argument("--idp-csv", default="config/biorxiv_temporal_idp_provenance_v1.csv")
    ap.add_argument("--out-json", default="runs/biorxiv_temporal_provenance_mapping_coverage_current.json")
    ap.add_argument("--out-md", default="runs/biorxiv_temporal_provenance_mapping_coverage_current.md")
    args = ap.parse_args()

    ligand_rows = _read_csv((ROOT / args.ligand_csv).resolve())
    idp_rows = _read_csv((ROOT / args.idp_csv).resolve())

    ligand_summary = _summarize(
        ligand_rows,
        required_any=[["provenance_date", "publication_year", "release_date"]],
        required_all=["source_release"],
        label="ligand",
        granularity_field="provenance_granularity",
    )
    idp_summary = _summarize(
        idp_rows,
        required_any=[["publication_year", "benchmark_inclusion_date", "corrected_label_freeze_date"]],
        required_all=["provenance_source"],
        label="idp",
        granularity_field="provenance_granularity",
    )

    summary = {
        "ligand": ligand_summary,
        "idp": idp_summary,
        "overall_ready_count": ligand_summary["ready_count"] + idp_summary["ready_count"],
        "overall_item_ready_count": ligand_summary["item_ready_count"] + idp_summary["item_ready_count"],
        "overall_dataset_ready_count": ligand_summary["dataset_ready_count"] + idp_summary["dataset_ready_count"],
        "overall_row_count": ligand_summary["row_count"] + idp_summary["row_count"],
    }
    _write_json((ROOT / args.out_json).resolve(), summary)

    lines = [
        "# Temporal Provenance Mapping Coverage",
        "",
        "## Ligand",
        "",
        f"- row_count: `{ligand_summary['row_count']}`",
        f"- ready_count: `{ligand_summary['ready_count']}`",
        f"- item_ready_count: `{ligand_summary['item_ready_count']}`",
        f"- dataset_ready_count: `{ligand_summary['dataset_ready_count']}`",
        f"- partial_count: `{ligand_summary['partial_count']}`",
        f"- missing_count: `{ligand_summary['missing_count']}`",
        f"- required_all: `{', '.join(ligand_summary['required_all'])}`",
        f"- required_any: `{', '.join('/'.join(group) for group in ligand_summary['required_any'])}`",
        f"- granularity_field: `{ligand_summary['granularity_field']}`",
        "",
        "## IDP",
        "",
        f"- row_count: `{idp_summary['row_count']}`",
        f"- ready_count: `{idp_summary['ready_count']}`",
        f"- item_ready_count: `{idp_summary['item_ready_count']}`",
        f"- dataset_ready_count: `{idp_summary['dataset_ready_count']}`",
        f"- partial_count: `{idp_summary['partial_count']}`",
        f"- missing_count: `{idp_summary['missing_count']}`",
        f"- required_all: `{', '.join(idp_summary['required_all'])}`",
        f"- required_any: `{', '.join('/'.join(group) for group in idp_summary['required_any'])}`",
        f"- granularity_field: `{idp_summary['granularity_field']}`",
        "",
        "## Overall",
        "",
        f"- overall_row_count: `{summary['overall_row_count']}`",
        f"- overall_ready_count: `{summary['overall_ready_count']}`",
        f"- overall_item_ready_count: `{summary['overall_item_ready_count']}`",
        f"- overall_dataset_ready_count: `{summary['overall_dataset_ready_count']}`",
        "",
        "## Interpretation",
        "",
        "- A ligand row is marked `item_ready` when `source_release` is filled, one of `provenance_date`, `publication_year`, or `release_date` is present, and `provenance_granularity` begins with `item`.",
        "- A ligand row is marked `dataset_ready` when the same required fields are present but `provenance_granularity` indicates dataset-level rather than item-level provenance.",
        "- An IDP row is marked `item_ready` when `provenance_source` is filled, at least one of `publication_year`, `benchmark_inclusion_date`, or `corrected_label_freeze_date` is present, and `provenance_granularity` begins with `item`.",
        "- An IDP row is marked `dataset_ready` when the same required fields are present but `provenance_granularity` indicates dataset-level rather than item-level provenance.",
        "- Current files are intended as editable curation maps; rerun this checker after provenance fields are populated.",
    ]
    _write_text((ROOT / args.out_md).resolve(), "\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
