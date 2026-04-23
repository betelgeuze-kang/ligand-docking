#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[1]
CHEMBL_API = "https://www.ebi.ac.uk/chembl/api/data"


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


def _fetch_activity_years(session: requests.Session, chembl_id: str, page_limit: int = 1000) -> tuple[int | None, str | None]:
    offset = 0
    earliest_year: int | None = None
    earliest_doc: str | None = None
    while True:
        response = session.get(
            f"{CHEMBL_API}/activity.json",
            params={
                "molecule_chembl_id": chembl_id,
                "limit": page_limit,
                "offset": offset,
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        activities = payload.get("activities", [])
        if not activities:
            break
        for activity in activities:
            year = activity.get("document_year")
            doc_id = activity.get("document_chembl_id")
            if year is None:
                continue
            try:
                year_int = int(year)
            except (TypeError, ValueError):
                continue
            if earliest_year is None or year_int < earliest_year:
                earliest_year = year_int
                earliest_doc = doc_id
        page_meta = payload.get("page_meta", {})
        total_count = int(page_meta.get("total_count", 0) or 0)
        offset += len(activities)
        if offset >= total_count:
            break
    return earliest_year, earliest_doc


def _molecule_url(chembl_id: str) -> str:
    return f"https://www.ebi.ac.uk/chembl/compound_report_card/{chembl_id}/"


def _document_url(document_chembl_id: str) -> str:
    return f"https://www.ebi.ac.uk/chembl/document_report_card/{document_chembl_id}/"


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch item-level provenance facts for ChEMBL ligand families used in temporal validation.")
    ap.add_argument("--provenance-csv", default="config/biorxiv_temporal_ligand_provenance_v1.csv")
    ap.add_argument("--source-release", default="chembl_blind_adrb2_v1")
    ap.add_argument("--out-csv", default="runs/biorxiv_temporal_chembl_item_provenance_current.csv")
    ap.add_argument("--out-json", default="runs/biorxiv_temporal_chembl_item_provenance_current.json")
    ap.add_argument("--out-md", default="runs/biorxiv_temporal_chembl_item_provenance_current.md")
    ap.add_argument("--sleep-sec", type=float, default=0.0)
    args = ap.parse_args()

    provenance_rows = _read_csv((ROOT / args.provenance_csv).resolve())
    chembl_ids = sorted(
        {
            row.get("ligand_id", "").upper()
            for row in provenance_rows
            if row.get("source_release", "").strip() == args.source_release and row.get("ligand_id", "").lower().startswith("chembl")
        }
    )

    rows: list[dict[str, Any]] = []
    fetch_failures: list[dict[str, str]] = []
    session = requests.Session()
    session.headers.update({"User-Agent": "biorxiv-temporal-provenance/1.0"})

    for chembl_id in chembl_ids:
        try:
            earliest_year, earliest_doc = _fetch_activity_years(session, chembl_id)
        except Exception as exc:  # pragma: no cover - network failure path
            fetch_failures.append({"ligand_id": chembl_id, "error": str(exc)})
            continue
        provenance_url = _document_url(earliest_doc) if earliest_doc else _molecule_url(chembl_id)
        notes = "Earliest ChEMBL activity document year pulled from activity endpoint."
        if earliest_doc:
            notes += f" Earliest document: {earliest_doc}."
        rows.append(
            {
                "source_release": args.source_release,
                "ligand_id": chembl_id,
                "publication_year": earliest_year or "",
                "provenance_date": earliest_year or "",
                "release_date": "",
                "provenance_granularity": "item_publication",
                "provenance_url": provenance_url,
                "curation_status": "item_publication_chembl_api",
                "notes": notes,
            }
        )
        if args.sleep_sec > 0:
            time.sleep(args.sleep_sec)

    fieldnames = [
        "source_release",
        "ligand_id",
        "publication_year",
        "provenance_date",
        "release_date",
        "provenance_granularity",
        "provenance_url",
        "curation_status",
        "notes",
    ]
    _write_csv((ROOT / args.out_csv).resolve(), rows, fieldnames)
    summary = {
        "source_release": args.source_release,
        "unique_chembl_ids": len(chembl_ids),
        "fetched_rows": len(rows),
        "failure_count": len(fetch_failures),
        "failures": fetch_failures,
        "out_csv": str((ROOT / args.out_csv).resolve()),
    }
    _write_json((ROOT / args.out_json).resolve(), summary)
    lines = [
        "# ChEMBL Item-Level Provenance Fetch Summary",
        "",
        f"- source_release: `{args.source_release}`",
        f"- unique_chembl_ids: `{len(chembl_ids)}`",
        f"- fetched_rows: `{len(rows)}`",
        f"- failure_count: `{len(fetch_failures)}`",
        "",
        "## Failures",
        "",
    ]
    if fetch_failures:
        for item in fetch_failures:
            lines.append(f"- `{item['ligand_id']}`: `{item['error']}`")
    else:
        lines.append("- none")
    _write_text((ROOT / args.out_md).resolve(), "\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
