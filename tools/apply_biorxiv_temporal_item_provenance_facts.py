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


def _apply_prefill(row: dict[str, str], fact: dict[str, str]) -> tuple[dict[str, str], bool]:
    updated = dict(row)
    touched = False
    overwriteable_statuses = {"", "pending", "release_prefilled_pending_date", "dataset_release_locally_anchored"}
    override_keys = {"provenance_granularity", "provenance_url"}
    for key in (
        "provenance_date",
        "publication_year",
        "release_date",
        "provenance_granularity",
        "provenance_url",
    ):
        fact_value = (fact.get(key) or "").strip()
        if not fact_value:
            continue
        current_value = (updated.get(key) or "").strip()
        current_status = (updated.get("curation_status") or "").strip()
        can_override = key in override_keys and current_status in overwriteable_statuses
        if current_value and current_value != fact_value and not can_override:
            continue
        if current_value != fact_value:
            updated[key] = fact_value
            touched = True

    fact_status = (fact.get("curation_status") or "").strip()
    current_status = (updated.get("curation_status") or "").strip()
    if fact_status and current_status in overwriteable_statuses and current_status != fact_status:
        updated["curation_status"] = fact_status
        touched = True

    fact_notes = (fact.get("notes") or "").strip()
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
    ap = argparse.ArgumentParser(description="Apply item-level ligand provenance facts to the temporal ligand provenance map.")
    ap.add_argument("--provenance-csv", default="config/biorxiv_temporal_ligand_provenance_v1.csv")
    ap.add_argument("--facts-csv", default="runs/biorxiv_temporal_chembl_item_provenance_current.csv")
    ap.add_argument("--out-json", default="runs/biorxiv_temporal_item_provenance_apply_current.json")
    ap.add_argument("--out-md", default="runs/biorxiv_temporal_item_provenance_apply_current.md")
    args = ap.parse_args()

    provenance_path = (ROOT / args.provenance_csv).resolve()
    facts_path = (ROOT / args.facts_csv).resolve()
    provenance_rows = _read_csv(provenance_path)
    fieldnames = list(provenance_rows[0].keys()) if provenance_rows else []
    facts_rows = _read_csv(facts_path)
    facts_by_key = {
        (
            (row.get("source_release") or "").strip(),
            (row.get("ligand_id") or "").strip().upper(),
        ): row
        for row in facts_rows
        if (row.get("source_release") or "").strip() and (row.get("ligand_id") or "").strip()
    }

    matched_rows = 0
    updated_rows = 0
    updated_provenance_rows: list[dict[str, str]] = []
    for row in provenance_rows:
        key = ((row.get("source_release") or "").strip(), (row.get("ligand_id") or "").strip().upper())
        fact = facts_by_key.get(key)
        if not fact:
            updated_provenance_rows.append(row)
            continue
        matched_rows += 1
        updated_row, touched = _apply_prefill(row, fact)
        if touched:
            updated_rows += 1
        updated_provenance_rows.append(updated_row)

    _write_csv(provenance_path, updated_provenance_rows, fieldnames)
    summary = {
        "provenance_csv": str(provenance_path),
        "facts_csv": str(facts_path),
        "fact_row_count": len(facts_rows),
        "matched_row_count": matched_rows,
        "updated_row_count": updated_rows,
    }
    _write_json((ROOT / args.out_json).resolve(), summary)
    lines = [
        "# Temporal Item-Level Provenance Apply Summary",
        "",
        f"- provenance_csv: `{provenance_path}`",
        f"- facts_csv: `{facts_path}`",
        f"- fact_row_count: `{len(facts_rows)}`",
        f"- matched_row_count: `{matched_rows}`",
        f"- updated_row_count: `{updated_rows}`",
    ]
    _write_text((ROOT / args.out_md).resolve(), "\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
