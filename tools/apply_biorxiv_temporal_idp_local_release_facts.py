#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _ensure_fieldnames(rows: list[dict[str, str]], desired: list[str]) -> tuple[list[dict[str, str]], list[str]]:
    existing: list[str] = []
    if rows:
        existing = list(rows[0].keys())
    fieldnames = list(existing)
    for name in desired:
        if name not in fieldnames:
            fieldnames.append(name)
    normalized_rows: list[dict[str, str]] = []
    for row in rows:
        normalized = dict(row)
        for name in fieldnames:
            normalized.setdefault(name, "")
        normalized_rows.append(normalized)
    return normalized_rows, fieldnames


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


def _apply_prefill(row: dict[str, str], facts: dict[str, str]) -> tuple[dict[str, str], bool]:
    updated = dict(row)
    touched = False
    overwriteable_statuses = {"", "pending"}
    for key in (
        "publication_year",
        "benchmark_inclusion_date",
        "corrected_label_freeze_date",
        "provenance_granularity",
        "provenance_source",
    ):
        fact_value = (facts.get(key) or "").strip()
        if not fact_value:
            continue
        if (updated.get(key) or "").strip():
            continue
        updated[key] = fact_value
        touched = True

    fact_status = (facts.get("curation_status") or "").strip()
    current_status = (updated.get("curation_status") or "").strip()
    if fact_status and current_status in overwriteable_statuses and current_status != fact_status:
        updated["curation_status"] = fact_status
        touched = True

    fact_notes = (facts.get("notes") or "").strip()
    if fact_notes:
        current_notes = (updated.get("notes") or "").strip()
        if not current_notes:
            updated["notes"] = fact_notes
            touched = True
        elif fact_notes not in current_notes:
            updated["notes"] = f"{current_notes} | {fact_notes}"
            touched = True
    return updated, touched


def main() -> int:
    ap = argparse.ArgumentParser(description="Apply dataset-level local release facts to the IDP temporal provenance map.")
    ap.add_argument("--provenance-csv", default="config/biorxiv_temporal_idp_provenance_v1.csv")
    ap.add_argument("--facts-csv", default="config/biorxiv_temporal_idp_local_release_facts_v1.csv")
    ap.add_argument("--match-column", default="source_kind")
    ap.add_argument("--out-json", default="runs/biorxiv_temporal_idp_local_release_facts_apply_current.json")
    ap.add_argument("--out-md", default="runs/biorxiv_temporal_idp_local_release_facts_apply_current.md")
    args = ap.parse_args()

    provenance_path = (ROOT / args.provenance_csv).resolve()
    facts_path = (ROOT / args.facts_csv).resolve()

    provenance_rows = _read_csv(provenance_path)
    provenance_rows, fieldnames = _ensure_fieldnames(
        provenance_rows,
        [
            "publication_year",
            "benchmark_inclusion_date",
            "corrected_label_freeze_date",
            "provenance_granularity",
            "provenance_source",
            "curation_status",
            "notes",
        ],
    )

    facts_rows = _read_csv(facts_path)
    facts_by_key = {
        row.get(args.match_column, "").strip(): row
        for row in facts_rows
        if row.get(args.match_column, "").strip()
    }

    matched_rows = 0
    updated_rows = 0
    matched_keys: set[str] = set()
    updated_provenance_rows: list[dict[str, str]] = []
    for row in provenance_rows:
        match_value = row.get(args.match_column, "").strip()
        facts = facts_by_key.get(match_value)
        if not facts:
            updated_provenance_rows.append(row)
            continue
        matched_rows += 1
        matched_keys.add(match_value)
        updated_row, touched = _apply_prefill(row, facts)
        if touched:
            updated_rows += 1
        updated_provenance_rows.append(updated_row)

    _write_csv(provenance_path, updated_provenance_rows, fieldnames)

    summary = {
        "provenance_csv": str(provenance_path),
        "facts_csv": str(facts_path),
        "match_column": args.match_column,
        "fact_key_count": len(facts_by_key),
        "matched_key_count": len(matched_keys),
        "matched_keys": sorted(matched_keys),
        "unmatched_fact_keys": sorted(set(facts_by_key) - matched_keys),
        "matched_row_count": matched_rows,
        "updated_row_count": updated_rows,
    }
    _write_json((ROOT / args.out_json).resolve(), summary)

    lines = [
        "# Temporal IDP Local Release Facts Apply Summary",
        "",
        f"- provenance_csv: `{provenance_path}`",
        f"- facts_csv: `{facts_path}`",
        f"- match_column: `{args.match_column}`",
        f"- fact_key_count: `{summary['fact_key_count']}`",
        f"- matched_key_count: `{summary['matched_key_count']}`",
        f"- matched_row_count: `{matched_rows}`",
        f"- updated_row_count: `{updated_rows}`",
        "",
        "## Matched Keys",
        "",
    ]
    for key in summary["matched_keys"]:
        lines.append(f"- `{key}`")
    if not summary["matched_keys"]:
        lines.append("- none")
    lines.extend(["", "## Unmatched Fact Keys", ""])
    for key in summary["unmatched_fact_keys"]:
        lines.append(f"- `{key}`")
    if not summary["unmatched_fact_keys"]:
        lines.append("- none")
    _write_text((ROOT / args.out_md).resolve(), "\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
