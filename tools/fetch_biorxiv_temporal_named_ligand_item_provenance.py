#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import time
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[1]
CHEMBL_API = "https://www.ebi.ac.uk/chembl/api/data"
SOURCE_RELEASES_DEFAULT = ["gpcr_blind_proxy_v1", "literature_proxy_v2", "disjoint_proxy_v2"]
SALT_TOKENS = (
    " HYDROCHLORIDE",
    " PHOSPHATE",
    " MALEATE",
    " SULFATE",
    " ETHANOLATE",
    " CITRATE",
    " MESYLATE",
    " LAURYLSULFATE",
    " SODIUM",
    " LYSINE",
    " GLUCURONIDE",
)
ALIASES = {
    "nicotinamide": "niacinamide",
}


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


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _base_name_from_ligand_id(ligand_id: str) -> str:
    name = ligand_id.lower()
    for prefix in ("egfr_", "hiv_"):
        if name.startswith(prefix):
            name = name[len(prefix) :]
    if name.startswith("decoy_"):
        name = name[len("decoy_") :]
    return ALIASES.get(name, name)


def _fetch_search_hits(session: requests.Session, query_name: str) -> list[dict[str, Any]]:
    response = session.get(
        f"{CHEMBL_API}/molecule/search.json",
        params={"q": query_name},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    return list(payload.get("molecules", []))


def _pick_best_hit(query_name: str, hits: list[dict[str, Any]]) -> dict[str, Any] | None:
    query_norm = _normalize_name(query_name)
    exact: list[dict[str, Any]] = []
    relaxed: list[dict[str, Any]] = []
    for hit in hits:
        pref_name = (hit.get("pref_name") or "").strip()
        if not pref_name:
            continue
        pref_norm = _normalize_name(pref_name)
        if pref_norm == query_norm:
            exact.append(hit)
            continue
        if any(token.strip().lower() in pref_name.lower() for token in SALT_TOKENS):
            continue
        if pref_norm.startswith(query_norm):
            relaxed.append(hit)
    if exact:
        return exact[0]
    if relaxed:
        return relaxed[0]
    for hit in hits:
        pref_name = (hit.get("pref_name") or "").strip()
        if not pref_name:
            continue
        if not any(token.strip().lower() in pref_name.lower() for token in SALT_TOKENS):
            return hit
    return hits[0] if hits else None


def _fetch_activity_years(session: requests.Session, chembl_id: str) -> tuple[int | None, str | None]:
    response = session.get(
        f"{CHEMBL_API}/activity.json",
        params={
            "molecule_chembl_id": chembl_id,
            "order_by": "document_year",
            "limit": 50,
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    for activity in payload.get("activities", []):
        year = activity.get("document_year")
        doc_id = activity.get("document_chembl_id")
        if year is None:
            continue
        try:
            year_int = int(year)
        except (TypeError, ValueError):
            continue
        return year_int, doc_id
    return None, None


def _document_url(document_chembl_id: str | None, chembl_id: str) -> str:
    if document_chembl_id:
        return f"https://www.ebi.ac.uk/chembl/document_report_card/{document_chembl_id}/"
    return f"https://www.ebi.ac.uk/chembl/compound_report_card/{chembl_id}/"


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch item-level ChEMBL provenance for named ligand source families.")
    ap.add_argument("--provenance-csv", default="config/biorxiv_temporal_ligand_provenance_v1.csv")
    ap.add_argument("--source-releases", default=",".join(SOURCE_RELEASES_DEFAULT))
    ap.add_argument("--out-csv", default="runs/biorxiv_temporal_named_ligand_item_provenance_current.csv")
    ap.add_argument("--out-json", default="runs/biorxiv_temporal_named_ligand_item_provenance_current.json")
    ap.add_argument("--out-md", default="runs/biorxiv_temporal_named_ligand_item_provenance_current.md")
    ap.add_argument("--sleep-sec", type=float, default=0.0)
    args = ap.parse_args()

    wanted_sources = {item.strip() for item in args.source_releases.split(",") if item.strip()}
    provenance_rows = _read_csv((ROOT / args.provenance_csv).resolve())
    targets: dict[tuple[str, str], str] = {}
    for row in provenance_rows:
        source_release = (row.get("source_release") or "").strip()
        ligand_id = (row.get("ligand_id") or "").strip()
        if source_release not in wanted_sources or not ligand_id:
            continue
        if ligand_id.lower().startswith("chembl"):
            continue
        targets[(source_release, ligand_id)] = _base_name_from_ligand_id(ligand_id)

    session = requests.Session()
    session.headers.update({"User-Agent": "biorxiv-temporal-provenance/1.0"})

    rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for (source_release, ligand_id), query_name in sorted(targets.items()):
        try:
            hits = _fetch_search_hits(session, query_name)
            best_hit = _pick_best_hit(query_name, hits)
            if not best_hit:
                failures.append({"source_release": source_release, "ligand_id": ligand_id, "error": "no_search_hit"})
                continue
            chembl_id = (best_hit.get("molecule_chembl_id") or "").strip()
            pref_name = (best_hit.get("pref_name") or "").strip()
            if not chembl_id:
                failures.append({"source_release": source_release, "ligand_id": ligand_id, "error": "missing_chembl_id"})
                continue
            earliest_year, earliest_doc = _fetch_activity_years(session, chembl_id)
            if earliest_year is None:
                failures.append({"source_release": source_release, "ligand_id": ligand_id, "error": f"no_activity_year:{chembl_id}"})
                continue
            rows.append(
                {
                    "source_release": source_release,
                    "ligand_id": ligand_id,
                    "query_name": query_name,
                    "resolved_chembl_id": chembl_id,
                    "resolved_pref_name": pref_name,
                    "publication_year": earliest_year,
                    "provenance_date": earliest_year,
                    "release_date": "",
                    "provenance_granularity": "item_publication",
                    "provenance_url": _document_url(earliest_doc, chembl_id),
                    "curation_status": "item_publication_chembl_api",
                    "notes": f"Earliest ChEMBL activity document year for {chembl_id}.",
                }
            )
            if args.sleep_sec > 0:
                time.sleep(args.sleep_sec)
        except Exception as exc:  # pragma: no cover - network failure path
            failures.append({"source_release": source_release, "ligand_id": ligand_id, "error": str(exc)})

    fieldnames = [
        "source_release",
        "ligand_id",
        "query_name",
        "resolved_chembl_id",
        "resolved_pref_name",
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
        "source_release_count": len(wanted_sources),
        "target_ligand_count": len(targets),
        "fetched_rows": len(rows),
        "failure_count": len(failures),
        "failures": failures,
    }
    _write_json((ROOT / args.out_json).resolve(), summary)
    lines = [
        "# Named Ligand Item-Level Provenance Fetch Summary",
        "",
        f"- source_release_count: `{len(wanted_sources)}`",
        f"- target_ligand_count: `{len(targets)}`",
        f"- fetched_rows: `{len(rows)}`",
        f"- failure_count: `{len(failures)}`",
        "",
        "## Failures",
        "",
    ]
    if failures:
        for item in failures:
            lines.append(f"- `{item['source_release']}/{item['ligand_id']}`: `{item['error']}`")
    else:
        lines.append("- none")
    _write_text((ROOT / args.out_md).resolve(), "\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
