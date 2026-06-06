#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def _first_row(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8", newline="") as handle:
        return next(csv.DictReader(handle))


def _parse_anchor(raw: str) -> dict[str, Any]:
    if not raw.strip():
        return {}
    try:
        value = ast.literal_eval(raw)
    except (SyntaxError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _extract_year(citation: str) -> str:
    years = YEAR_RE.findall(citation or "")
    return years[0] if years else ""


def _extract_pdb_header_date(path_str: str) -> str:
    path = Path(path_str)
    if not path.exists():
        return ""
    try:
        header = path.read_text(encoding="utf-8", errors="ignore").splitlines()[0]
    except IndexError:
        return ""
    if not header.startswith("HEADER"):
        return ""
    raw = header[50:59].strip()
    if not raw:
        return ""
    try:
        return datetime.strptime(raw.title(), "%d-%b-%y").date().isoformat()
    except ValueError:
        return raw


def main() -> int:
    ap = argparse.ArgumentParser(description="Build IDP item-level temporal provenance helpers from release artifacts.")
    ap.add_argument("--provenance-csv", default="config/biorxiv_temporal_idp_provenance_v1.csv")
    ap.add_argument("--release-manifest-json", default="runs/idp_3bead_holdout_v7_sb_rust_2026-03-20_r3_speedopt3_release_manifest.json")
    ap.add_argument("--out-helper-csv", default="runs/biorxiv_temporal_idp_item_helpers_current.csv")
    ap.add_argument("--out-helper-json", default="runs/biorxiv_temporal_idp_item_helpers_current.json")
    ap.add_argument("--out-helper-md", default="runs/biorxiv_temporal_idp_item_helpers_current.md")
    ap.add_argument("--out-facts-csv", default="runs/biorxiv_temporal_idp_item_provenance_facts_current.csv")
    ap.add_argument("--out-facts-json", default="runs/biorxiv_temporal_idp_item_provenance_facts_current.json")
    ap.add_argument("--out-facts-md", default="runs/biorxiv_temporal_idp_item_provenance_facts_current.md")
    args = ap.parse_args()

    provenance_rows = _read_csv((ROOT / args.provenance_csv).resolve())
    manifest = _read_json((ROOT / args.release_manifest_json).resolve())
    provenance_by_holdout = {row["holdout_name"]: row for row in provenance_rows}

    helper_rows: list[dict[str, str]] = []
    fact_rows: list[dict[str, str]] = []
    for fold in manifest.get("fold_artifacts", []):
        holdout = str(fold.get("holdout", "")).strip()
        if not holdout:
            continue
        prov_row = provenance_by_holdout.get(holdout, {})
        eval_csv = (ROOT / str(fold.get("eval_corrected_csv", ""))).resolve()
        first_row = _first_row(eval_csv)
        anchor = _parse_anchor(first_row.get("observable_anchor", ""))
        provenance = anchor.get("provenance", {}) if isinstance(anchor.get("provenance"), dict) else {}
        citation = str(provenance.get("citation", "") or "").strip()
        notes = str(provenance.get("notes", "") or "").strip()
        item_year = _extract_year(citation)
        source_kind = str(prov_row.get("source_kind", first_row.get("source", "")) or "").strip()
        pdb_path = str(prov_row.get("pdb_path", "") or "").strip()
        pdb_header_date = _extract_pdb_header_date(pdb_path) if pdb_path else ""
        auto_candidate = "yes" if item_year else "no"
        helper_rows.append(
            {
                "holdout_name": holdout,
                "source_kind": source_kind,
                "pdb_path": pdb_path,
                "eval_corrected_csv": str(eval_csv),
                "anchor_source": str(anchor.get("source", "") or "").strip(),
                "citation_publication_year": item_year,
                "pdb_header_date": pdb_header_date,
                "auto_item_ready_candidate": auto_candidate,
                "citation": citation,
                "notes": notes,
            }
        )
        if not item_year:
            continue
        fact_rows.append(
            {
                "holdout_name": holdout,
                "publication_year": item_year,
                "provenance_granularity": "item_publication",
                "provenance_source": str(eval_csv),
                "curation_status": "item_publication_prefilled",
                "notes": "Auto-prefilled from explicit year found in observable_anchor citation extracted from the accepted IDP eval_corrected targets artifact.",
            }
        )

    helper_summary = {
        "release_manifest_json": str((ROOT / args.release_manifest_json).resolve()),
        "holdout_count": len(helper_rows),
        "auto_item_ready_candidate_count": sum(1 for row in helper_rows if row["auto_item_ready_candidate"] == "yes"),
        "citation_year_count": sum(1 for row in helper_rows if row["citation_publication_year"]),
        "pdb_header_date_count": sum(1 for row in helper_rows if row["pdb_header_date"]),
    }
    facts_summary = {
        "release_manifest_json": str((ROOT / args.release_manifest_json).resolve()),
        "fact_row_count": len(fact_rows),
        "holdouts": [row["holdout_name"] for row in fact_rows],
    }

    _write_csv(
        (ROOT / args.out_helper_csv).resolve(),
        helper_rows,
        [
            "holdout_name",
            "source_kind",
            "pdb_path",
            "eval_corrected_csv",
            "anchor_source",
            "citation_publication_year",
            "pdb_header_date",
            "auto_item_ready_candidate",
            "citation",
            "notes",
        ],
    )
    _write_json((ROOT / args.out_helper_json).resolve(), helper_summary | {"rows": helper_rows})
    helper_lines = [
        "# IDP Temporal Item-Level Helper",
        "",
        f"- holdout_count: `{helper_summary['holdout_count']}`",
        f"- auto_item_ready_candidate_count: `{helper_summary['auto_item_ready_candidate_count']}`",
        f"- citation_year_count: `{helper_summary['citation_year_count']}`",
        f"- pdb_header_date_count: `{helper_summary['pdb_header_date_count']}`",
        "",
        "## Auto-Candidate Holdouts",
        "",
    ]
    auto_rows = [row for row in helper_rows if row["auto_item_ready_candidate"] == "yes"]
    if auto_rows:
        for row in auto_rows:
            helper_lines.extend(
                [
                    f"### {row['holdout_name']}",
                    "",
                    f"- source_kind: `{row['source_kind']}`",
                    f"- citation_publication_year: `{row['citation_publication_year']}`",
                    f"- eval_corrected_csv: `{row['eval_corrected_csv']}`",
                    f"- citation: `{row['citation']}`",
                    "",
                ]
            )
    else:
        helper_lines.append("- none")
        helper_lines.append("")
    _write_text((ROOT / args.out_helper_md).resolve(), "\n".join(helper_lines))

    _write_csv(
        (ROOT / args.out_facts_csv).resolve(),
        fact_rows,
        [
            "holdout_name",
            "publication_year",
            "provenance_granularity",
            "provenance_source",
            "curation_status",
            "notes",
        ],
    )
    _write_json((ROOT / args.out_facts_json).resolve(), facts_summary)
    fact_lines = [
        "# IDP Temporal Item-Level Facts",
        "",
        f"- fact_row_count: `{facts_summary['fact_row_count']}`",
        f"- holdouts: `{', '.join(facts_summary['holdouts']) if facts_summary['holdouts'] else 'none'}`",
        "",
    ]
    _write_text((ROOT / args.out_facts_md).resolve(), "\n".join(fact_lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
