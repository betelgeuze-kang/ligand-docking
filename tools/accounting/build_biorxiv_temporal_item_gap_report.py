#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
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


def _status(row: dict[str, str], source_key: str, date_keys: list[str], granularity_key: str) -> str:
    has_source = (row.get(source_key) or "").strip()
    has_date = any((row.get(key) or "").strip() for key in date_keys)
    granularity = (row.get(granularity_key) or "").strip().lower()
    if has_source and has_date:
        if granularity.startswith("item"):
            return "item_ready"
        return "dataset_ready"
    if has_source or has_date or granularity:
        return "partial"
    return "missing"


def _build_ligand_groups(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if _status(row, "source_release", ["provenance_date", "publication_year", "release_date"], "provenance_granularity") != "dataset_ready":
            continue
        groups[row.get("source_release", "")].append(row)
    out: list[dict[str, Any]] = []
    for source_release, group_rows in sorted(groups.items()):
        ligands = sorted({row.get("ligand_id", "") for row in group_rows if row.get("ligand_id", "")})
        tasks = sorted({row.get("task_id", "") for row in group_rows if row.get("task_id", "")})
        targets = sorted({row.get("target", "") for row in group_rows if row.get("target", "")})
        out.append(
            {
                "kind": "ligand",
                "group_key": source_release,
                "row_count": len(group_rows),
                "unique_item_count": len(ligands),
                "tasks": ", ".join(tasks),
                "targets": ", ".join(targets),
                "example_items": ", ".join(ligands[:10]),
            }
        )
    return out


def _build_idp_groups(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if _status(
            row,
            "provenance_source",
            ["publication_year", "benchmark_inclusion_date", "corrected_label_freeze_date"],
            "provenance_granularity",
        ) != "dataset_ready":
            continue
        groups[row.get("source_kind", "")].append(row)
    out: list[dict[str, Any]] = []
    for source_kind, group_rows in sorted(groups.items()):
        holdouts = sorted({row.get("holdout_name", "") for row in group_rows if row.get("holdout_name", "")})
        out.append(
            {
                "kind": "idp",
                "group_key": source_kind,
                "row_count": len(group_rows),
                "unique_item_count": len(holdouts),
                "tasks": ", ".join(sorted({row.get("task_id", "") for row in group_rows if row.get("task_id", "")})),
                "targets": "",
                "example_items": ", ".join(holdouts[:10]),
            }
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Summarize the remaining dataset-ready but not item-ready temporal provenance gaps.")
    ap.add_argument("--ligand-csv", default="config/biorxiv_temporal_ligand_provenance_v1.csv")
    ap.add_argument("--idp-csv", default="config/biorxiv_temporal_idp_provenance_v1.csv")
    ap.add_argument("--out-json", default="runs/biorxiv_temporal_item_gap_report_current.json")
    ap.add_argument("--out-csv", default="runs/biorxiv_temporal_item_gap_report_current.csv")
    ap.add_argument("--out-md", default="runs/biorxiv_temporal_item_gap_report_current.md")
    args = ap.parse_args()

    ligand_rows = _read_csv((ROOT / args.ligand_csv).resolve())
    idp_rows = _read_csv((ROOT / args.idp_csv).resolve())

    rows = _build_ligand_groups(ligand_rows) + _build_idp_groups(idp_rows)
    summary = {
        "group_count": len(rows),
        "ligand_group_count": sum(1 for row in rows if row["kind"] == "ligand"),
        "idp_group_count": sum(1 for row in rows if row["kind"] == "idp"),
        "rows": rows,
    }
    _write_json((ROOT / args.out_json).resolve(), summary)
    _write_csv(
        (ROOT / args.out_csv).resolve(),
        rows,
        ["kind", "group_key", "row_count", "unique_item_count", "tasks", "targets", "example_items"],
    )

    lines = [
        "# Temporal Item-Level Gap Report",
        "",
        f"- group_count: `{summary['group_count']}`",
        f"- ligand_group_count: `{summary['ligand_group_count']}`",
        f"- idp_group_count: `{summary['idp_group_count']}`",
        "",
        "## Remaining Dataset-Ready Groups",
        "",
    ]
    for row in rows:
        detail_lines = [
            f"- row_count: `{row['row_count']}`",
            f"- unique_item_count: `{row['unique_item_count']}`",
            f"- tasks: `{row['tasks']}`",
        ]
        if row["targets"]:
            detail_lines.append(f"- targets: `{row['targets']}`")
        detail_lines.append(f"- example_items: `{row['example_items']}`")
        lines.extend(
            [
                f"### {row['kind']} / {row['group_key']}",
                "",
                *detail_lines,
                "",
            ]
        )
    if not rows:
        lines.append("- none")
    _write_text((ROOT / args.out_md).resolve(), "\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
