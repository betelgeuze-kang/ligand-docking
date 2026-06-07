#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
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


def _ligand_source_family(source_label: str) -> str:
    if source_label.startswith("chembl_blind_adrb2_v1:"):
        return "chembl_blind_adrb2_v1"
    return source_label or "unknown"


def _priority_from_rows(row_count: int, task_count: int, missing_targets: int = 0, sanity_flag: bool = False) -> str:
    score = row_count + task_count * 4 + missing_targets * 3 + (8 if sanity_flag else 0)
    if score >= 40:
        return "high"
    if score >= 12:
        return "medium"
    return "low"


def _build_ligand_groups(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row["domain"], _ligand_source_family(row["source_label"]))].append(row)

    output: list[dict[str, Any]] = []
    for (domain, family), group in sorted(grouped.items()):
        tasks = sorted({row["task_id"] for row in group})
        targets = sorted({row["target"] for row in group})
        missing_release = sum(1 for row in group if not row["source_release"].strip())
        missing_date = sum(
            1
            for row in group
            if not (
                row["provenance_date"].strip()
                or row["publication_year"].strip()
                or row["release_date"].strip()
            )
        )
        sanity_flag = len(targets) > 1
        output.append(
            {
                "category": "ligand",
                "domain": domain,
                "source_family": family,
                "row_count": len(group),
                "task_count": len(tasks),
                "tasks": ", ".join(tasks),
                "targets": ", ".join(targets),
                "missing_source_release": missing_release,
                "missing_item_dates": missing_date,
                "sanity_flag": sanity_flag,
                "priority": _priority_from_rows(len(group), len(tasks), len(targets), sanity_flag=sanity_flag),
                "recommended_fields": "source_release + one of provenance_date/publication_year/release_date",
                "notes": "Mixed target labels in one source family; verify intended reference pool before curation."
                if sanity_flag
                else "Curate one source family once, then propagate across all matching rows.",
            }
        )
    return output


def _build_idp_groups(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["source_kind"] or "unknown"].append(row)

    output: list[dict[str, Any]] = []
    for source_kind, group in sorted(grouped.items()):
        holdouts = sorted({row["holdout_name"] for row in group})
        missing_source = sum(1 for row in group if not row["provenance_source"].strip())
        missing_dates = sum(
            1
            for row in group
            if not (
                row["publication_year"].strip()
                or row["benchmark_inclusion_date"].strip()
                or row["corrected_label_freeze_date"].strip()
            )
        )
        output.append(
            {
                "category": "idp",
                "domain": "idp",
                "source_family": source_kind,
                "row_count": len(group),
                "task_count": 1,
                "tasks": "idp_release_current",
                "targets": ", ".join(holdouts[:6]) + (" ..." if len(holdouts) > 6 else ""),
                "missing_source_release": missing_source,
                "missing_item_dates": missing_dates,
                "sanity_flag": False,
                "priority": _priority_from_rows(len(group), 1),
                "recommended_fields": "provenance_source + one of publication_year/benchmark_inclusion_date/corrected_label_freeze_date",
                "notes": "Group by source kind to batch-curate PDB-derived versus synthetic holdouts.",
            }
        )
    return output


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a curation-priority summary for temporal provenance mapping files.")
    ap.add_argument("--ligand-csv", default="config/biorxiv_temporal_ligand_provenance_v1.csv")
    ap.add_argument("--idp-csv", default="config/biorxiv_temporal_idp_provenance_v1.csv")
    ap.add_argument("--out-json", default="runs/biorxiv_temporal_curation_priority_current.json")
    ap.add_argument("--out-csv", default="runs/biorxiv_temporal_curation_priority_current.csv")
    ap.add_argument("--out-md", default="runs/biorxiv_temporal_curation_priority_current.md")
    args = ap.parse_args()

    ligand_rows = _read_csv((ROOT / args.ligand_csv).resolve())
    idp_rows = _read_csv((ROOT / args.idp_csv).resolve())

    rows = _build_ligand_groups(ligand_rows) + _build_idp_groups(idp_rows)
    priority_counts = Counter(row["priority"] for row in rows)
    summary = {
        "group_count": len(rows),
        "priority_counts": dict(priority_counts),
        "high_priority_groups": [row["source_family"] for row in rows if row["priority"] == "high"],
    }
    payload = {"summary": summary, "rows": rows}
    _write_json((ROOT / args.out_json).resolve(), payload)
    _write_csv(
        (ROOT / args.out_csv).resolve(),
        rows,
        [
            "category",
            "domain",
            "source_family",
            "row_count",
            "task_count",
            "tasks",
            "targets",
            "missing_source_release",
            "missing_item_dates",
            "sanity_flag",
            "priority",
            "recommended_fields",
            "notes",
        ],
    )

    lines = [
        "# Temporal Provenance Curation Priority",
        "",
        f"- group_count: `{summary['group_count']}`",
        f"- priority_counts: `{summary['priority_counts']}`",
        "",
        "## Recommended Order",
        "",
        "1. Curate high-priority ligand source families first, because one source-level fill unlocks many rows at once.",
        "2. Sanity-check mixed-target ligand reference pools before filling provenance dates.",
        "3. Batch-curate IDP `pdb` holdouts separately from `synthetic` holdouts.",
        "",
        "## Groups",
        "",
        "| Category | Domain | Source Family | Priority | Rows | Tasks | Missing Release | Missing Dates | Notes |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in sorted(rows, key=lambda r: ({"high": 0, "medium": 1, "low": 2}[r["priority"]], r["category"], r["domain"], r["source_family"])):
        lines.append(
            f"| `{row['category']}` | `{row['domain']}` | `{row['source_family']}` | `{row['priority']}` | `{row['row_count']}` | `{row['tasks']}` | `{row['missing_source_release']}` | `{row['missing_item_dates']}` | {row['notes']} |"
        )
    _write_text((ROOT / args.out_md).resolve(), "\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
