#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _source_family(source_label: str) -> str:
    if source_label.startswith("chembl_blind_adrb2_v1:"):
        return "chembl_blind_adrb2_v1"
    return source_label or "unknown"


def _prefill_release(source_family: str) -> str:
    return source_family if source_family != "unknown" else ""


def _prefill_granularity(source_family: str) -> str:
    if source_family.startswith("chembl_"):
        return "source_family"
    if source_family.endswith("_proxy_v2") or source_family.endswith("_proxy_v1"):
        return "dataset_release"
    return "dataset_release"


def _prefill_notes(targets: set[str]) -> str:
    if len(targets) > 1:
        return "Mixed target labels detected; verify intended reference/calibration pool before filling item-level dates."
    return "Auto-prefilled source release can be reused across all matching rows; item-level dates still required."


def main() -> int:
    ap = argparse.ArgumentParser(description="Build family-level source normalization tables for temporal ligand provenance curation.")
    ap.add_argument("--ligand-csv", default="config/biorxiv_temporal_ligand_provenance_v1.csv")
    ap.add_argument("--out-csv", default="config/biorxiv_temporal_source_normalization_v1.csv")
    ap.add_argument("--out-json", default="runs/biorxiv_temporal_source_normalization_current.json")
    ap.add_argument("--out-md", default="runs/biorxiv_temporal_source_normalization_current.md")
    ap.add_argument("--sanity-md", default="runs/biorxiv_temporal_source_pool_sanity_check_current.md")
    args = ap.parse_args()

    rows = _read_csv((ROOT / args.ligand_csv).resolve())
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[_source_family(row["source_label"])].append(row)

    out_rows: list[dict[str, Any]] = []
    sanity_rows: list[dict[str, Any]] = []
    for family, group in sorted(grouped.items()):
        source_labels = sorted({row["source_label"] for row in group})
        tasks = sorted({row["task_id"] for row in group})
        domains = sorted({row["domain"] for row in group})
        targets = sorted({row["target"] for row in group})
        example = source_labels[0] if source_labels else ""
        row = {
            "source_family": family,
            "example_source_label": example,
            "row_count": len(group),
            "task_count": len(tasks),
            "tasks": ", ".join(tasks),
            "domains": ", ".join(domains),
            "targets": ", ".join(targets),
            "normalized_source_release": _prefill_release(family),
            "provenance_granularity": _prefill_granularity(family),
            "provenance_url": "",
            "default_curation_status": "release_prefilled_pending_date",
            "notes": _prefill_notes(set(targets)),
        }
        out_rows.append(row)
        sanity_rows.append(
            {
                "source_family": family,
                "target_count": len(targets),
                "targets": ", ".join(targets),
                "tasks": ", ".join(tasks),
                "notes": row["notes"],
            }
        )

    _write_csv(
        (ROOT / args.out_csv).resolve(),
        out_rows,
        [
            "source_family",
            "example_source_label",
            "row_count",
            "task_count",
            "tasks",
            "domains",
            "targets",
            "normalized_source_release",
            "provenance_granularity",
            "provenance_url",
            "default_curation_status",
            "notes",
        ],
    )
    payload = {"group_count": len(out_rows), "rows": out_rows}
    _write_json((ROOT / args.out_json).resolve(), payload)

    md_lines = [
        "# Temporal Source Normalization",
        "",
        f"- group_count: `{len(out_rows)}`",
        "",
        "| Source Family | Rows | Tasks | Targets | Suggested Release | Notes |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in out_rows:
        md_lines.append(
            f"| `{row['source_family']}` | `{row['row_count']}` | `{row['tasks']}` | `{row['targets']}` | `{row['normalized_source_release']}` | {row['notes']} |"
        )
    _write_text((ROOT / args.out_md).resolve(), "\n".join(md_lines) + "\n")

    sanity_lines = [
        "# Temporal Source Pool Sanity Check",
        "",
        "Review source families with more than one target label before filling item-level provenance dates.",
        "",
        "| Source Family | Target Count | Targets | Tasks | Notes |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in sanity_rows:
        sanity_lines.append(
            f"| `{row['source_family']}` | `{row['target_count']}` | `{row['targets']}` | `{row['tasks']}` | {row['notes']} |"
        )
    _write_text((ROOT / args.sanity_md).resolve(), "\n".join(sanity_lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
