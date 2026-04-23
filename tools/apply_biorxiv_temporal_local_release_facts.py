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
    overwriteable_statuses = {"", "pending", "release_prefilled_pending_date"}
    for key in (
        "provenance_date",
        "publication_year",
        "release_date",
        "provenance_granularity",
        "provenance_url",
    ):
        fact_value = facts.get(key, "").strip()
        if not fact_value:
            continue
        if updated.get(key, "").strip():
            continue
        updated[key] = fact_value
        touched = True

    fact_status = facts.get("curation_status", "").strip()
    current_status = updated.get("curation_status", "").strip()
    if fact_status and current_status in overwriteable_statuses and current_status != fact_status:
        updated["curation_status"] = fact_status
        touched = True

    fact_notes = facts.get("notes", "").strip()
    if fact_notes:
        current_notes = updated.get("notes", "").strip()
        if not current_notes:
            updated["notes"] = fact_notes
            touched = True
        elif fact_notes not in current_notes:
            updated["notes"] = f"{current_notes} | {fact_notes}"
            touched = True
    return updated, touched


def main() -> int:
    ap = argparse.ArgumentParser(description="Apply dataset-level local release facts to the ligand temporal provenance map.")
    ap.add_argument("--provenance-csv", default="config/biorxiv_temporal_ligand_provenance_v1.csv")
    ap.add_argument("--facts-csv", default="config/biorxiv_temporal_local_release_facts_v1.csv")
    ap.add_argument("--out-json", default="runs/biorxiv_temporal_local_release_facts_apply_current.json")
    ap.add_argument("--out-md", default="runs/biorxiv_temporal_local_release_facts_apply_current.md")
    args = ap.parse_args()

    provenance_path = (ROOT / args.provenance_csv).resolve()
    facts_path = (ROOT / args.facts_csv).resolve()

    provenance_rows = _read_csv(provenance_path)
    fieldnames = list(provenance_rows[0].keys()) if provenance_rows else []
    facts_rows = _read_csv(facts_path)
    facts_by_release = {row.get("source_release", "").strip(): row for row in facts_rows if row.get("source_release", "").strip()}

    matched_rows = 0
    updated_rows = 0
    matched_sources: set[str] = set()

    updated_provenance_rows: list[dict[str, str]] = []
    for row in provenance_rows:
        source_release = row.get("source_release", "").strip()
        facts = facts_by_release.get(source_release)
        if not facts:
            updated_provenance_rows.append(row)
            continue
        matched_rows += 1
        matched_sources.add(source_release)
        updated_row, touched = _apply_prefill(row, facts)
        if touched:
            updated_rows += 1
        updated_provenance_rows.append(updated_row)

    _write_csv(provenance_path, updated_provenance_rows, fieldnames)

    summary = {
        "provenance_csv": str(provenance_path),
        "facts_csv": str(facts_path),
        "fact_source_count": len(facts_by_release),
        "matched_source_count": len(matched_sources),
        "matched_sources": sorted(matched_sources),
        "unmatched_fact_sources": sorted(set(facts_by_release) - matched_sources),
        "matched_row_count": matched_rows,
        "updated_row_count": updated_rows,
    }
    _write_json((ROOT / args.out_json).resolve(), summary)

    lines = [
        "# Temporal Local Release Facts Apply Summary",
        "",
        f"- provenance_csv: `{provenance_path}`",
        f"- facts_csv: `{facts_path}`",
        f"- fact_source_count: `{summary['fact_source_count']}`",
        f"- matched_source_count: `{summary['matched_source_count']}`",
        f"- matched_row_count: `{matched_rows}`",
        f"- updated_row_count: `{updated_rows}`",
        "",
        "## Matched Sources",
        "",
    ]
    for source in summary["matched_sources"]:
        lines.append(f"- `{source}`")
    if not summary["matched_sources"]:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Unmatched Fact Sources",
            "",
        ]
    )
    for source in summary["unmatched_fact_sources"]:
        lines.append(f"- `{source}`")
    if not summary["unmatched_fact_sources"]:
        lines.append("- none")
    _write_text((ROOT / args.out_md).resolve(), "\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
