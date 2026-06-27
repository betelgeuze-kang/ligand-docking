#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
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


def _policy_label(row: dict[str, str]) -> str:
    status = (row.get("curation_status") or "").strip()
    if status == "dataset_control_policy_current":
        return "intentional_dataset_control"
    if status == "manual_item_curation_fragment_anchor_missing":
        return "fragment_anchor_missing"
    if status == "manual_item_curation_no_public_anchor_current":
        return "no_public_anchor_found"
    return status or "unspecified_dataset_ready"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Summarize policy reasons for remaining dataset-ready IDP temporal rows.")
    ap.add_argument("--idp-csv", default="config/biorxiv_temporal_idp_provenance_v1.csv")
    ap.add_argument("--out-json", default="runs/biorxiv_temporal_idp_remaining_policy_current.json")
    ap.add_argument("--out-csv", default="runs/biorxiv_temporal_idp_remaining_policy_current.csv")
    ap.add_argument("--out-md", default="runs/biorxiv_temporal_idp_remaining_policy_current.md")
    args = ap.parse_args(argv)

    rows = _read_csv((ROOT / args.idp_csv).resolve())
    remaining = []
    for row in rows:
        if _status(row) != "dataset_ready":
            continue
        remaining.append(
            {
                "holdout_name": row.get("holdout_name", ""),
                "source_kind": row.get("source_kind", ""),
                "policy_label": _policy_label(row),
                "curation_status": row.get("curation_status", ""),
                "benchmark_inclusion_date": row.get("benchmark_inclusion_date", ""),
                "corrected_label_freeze_date": row.get("corrected_label_freeze_date", ""),
                "provenance_source": row.get("provenance_source", ""),
                "notes": row.get("notes", ""),
            }
        )

    counts = Counter(row["policy_label"] for row in remaining)
    summary = {
        "remaining_count": len(remaining),
        "policy_counts": dict(sorted(counts.items())),
        "rows": remaining,
    }
    _write_json((ROOT / args.out_json).resolve(), summary)
    _write_csv(
        (ROOT / args.out_csv).resolve(),
        remaining,
        [
            "holdout_name",
            "source_kind",
            "policy_label",
            "curation_status",
            "benchmark_inclusion_date",
            "corrected_label_freeze_date",
            "provenance_source",
            "notes",
        ],
    )

    lines = [
        "# IDP Remaining Temporal Policy",
        "",
        f"- remaining_count: `{len(remaining)}`",
        "",
        "## Policy Counts",
        "",
    ]
    for label, count in sorted(counts.items()):
        lines.append(f"- `{label}`: `{count}`")
    lines.extend(["", "## Remaining Rows", ""])
    if remaining:
        for row in remaining:
            lines.extend(
                [
                    f"### {row['holdout_name']}",
                    "",
                    f"- policy_label: `{row['policy_label']}`",
                    f"- curation_status: `{row['curation_status']}`",
                    f"- benchmark_inclusion_date: `{row['benchmark_inclusion_date']}`",
                    f"- corrected_label_freeze_date: `{row['corrected_label_freeze_date']}`",
                    f"- provenance_source: `{row['provenance_source']}`",
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
