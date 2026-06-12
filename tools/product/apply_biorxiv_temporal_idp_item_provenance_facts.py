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
    overwriteable_statuses = {
        "",
        "pending",
        "dataset_release_locally_anchored",
        "manual_item_curation_pending",
    }
    for key in ("publication_year", "provenance_granularity", "provenance_source"):
        fact_value = (fact.get(key) or "").strip()
        if not fact_value:
            continue
        current_value = (updated.get(key) or "").strip()
        current_status = (updated.get("curation_status") or "").strip()
        can_override = key in {"provenance_granularity", "provenance_source"} and current_status in overwriteable_statuses
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
    ap = argparse.ArgumentParser(description="Apply item-level IDP provenance facts to the temporal IDP provenance map.")
    ap.add_argument("--provenance-csv", default="config/biorxiv_temporal_idp_provenance_v1.csv")
    ap.add_argument("--facts-csv", default="runs/biorxiv_temporal_idp_item_provenance_facts_current.csv")
    ap.add_argument("--out-json", default="runs/biorxiv_temporal_idp_item_provenance_apply_current.json")
    ap.add_argument("--out-md", default="runs/biorxiv_temporal_idp_item_provenance_apply_current.md")
    args = ap.parse_args()

    provenance_path = (ROOT / args.provenance_csv).resolve()
    facts_path = (ROOT / args.facts_csv).resolve()
    provenance_rows = _read_csv(provenance_path)
    facts_rows = _read_csv(facts_path)
    fieldnames = list(provenance_rows[0].keys()) if provenance_rows else []
    facts_by_holdout = {
        (row.get("holdout_name") or "").strip(): row
        for row in facts_rows
        if (row.get("holdout_name") or "").strip()
    }

    matched_rows = 0
    updated_rows = 0
    updated_provenance_rows: list[dict[str, str]] = []
    for row in provenance_rows:
        holdout = (row.get("holdout_name") or "").strip()
        fact = facts_by_holdout.get(holdout)
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
        "# IDP Temporal Item-Level Provenance Apply Summary",
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
