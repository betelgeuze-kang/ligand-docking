#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_NEGATIVE_SLOT_CLOSURE_JSON = "runs/aqp1_negative_slot_closure_packet_current.json"
DEFAULT_NEGATIVE_SOURCE_EXCLUSION_JSON = "runs/aqp1_negative_source_exclusion_packet_current.json"
DEFAULT_OUT_JSON = "runs/aqp1_negative_evidence_acquisition_packet_current.json"
DEFAULT_OUT_CSV = "runs/aqp1_negative_evidence_acquisition_packet_current.csv"
DEFAULT_OUT_MD = "runs/aqp1_negative_evidence_acquisition_packet_current.md"

SEARCH_ROWS = [
    {
        "query_rank": 1,
        "query_label": "pressure_induced_hemolysis_reinvestigation",
        "query_term": '(AQP1[Title/Abstract] OR "aquaporin 1"[Title/Abstract]) AND "pressure-induced hemolysis"[Title/Abstract]',
        "resolution_role": "primary_exact_source_reinvestigation",
        "anchor_pmid": "23123479",
        "anchor_title": "Reinvestigation of drugs and chemicals as aquaporin-1 inhibitors using pressure-induced hemolysis in human erythrocytes.",
        "query_caveat": "start_here_exact_source",
    },
    {
        "query_rank": 2,
        "query_label": "acetazolamide_boundary_review",
        "query_term": '(AQP1[Title/Abstract] OR "aquaporin 1"[Title/Abstract]) AND acetazolamide[Title/Abstract]',
        "resolution_role": "boundary_query_positive_heavy_do_not_promote_to_negative_directly",
        "anchor_pmid": "40359885",
        "anchor_title": "Acetazolamide as an aquaporin 1 inhibitor mitigates rheumatoid arthritis by reducing angiogenesis via the modulation of the FAK-PI3K/Akt signaling pathway.",
        "query_caveat": "positive_recent_literature_can_dominate",
    },
    {
        "query_rank": 3,
        "query_label": "tetraethylammonium_boundary_review",
        "query_term": '(AQP1[Title/Abstract] OR "aquaporin 1"[Title/Abstract]) AND tetraethylammonium[Title/Abstract]',
        "resolution_role": "boundary_query_refer_back_to_primary_reinvestigation_anchor",
        "anchor_pmid": "23123479",
        "anchor_title": "Reinvestigation of drugs and chemicals as aquaporin-1 inhibitors using pressure-induced hemolysis in human erythrocytes.",
        "query_caveat": "query_order_can_be_noisy_use_primary_anchor_first",
    },
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str | Path) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def build_payload(
    negative_slot_closure_payload: dict[str, Any],
    negative_source_exclusion_payload: dict[str, Any],
    *,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    slot_summary = dict((negative_slot_closure_payload or {}).get("summary", {}) or {})
    exclusion_summary = dict((negative_source_exclusion_payload or {}).get("summary", {}) or {})
    today = as_of_date or date.today().isoformat()

    rows: list[dict[str, Any]] = []
    for row in SEARCH_ROWS:
        rows.append(
            {
                "query_rank": row["query_rank"],
                "query_label": row["query_label"],
                "query_term": row["query_term"],
                "resolution_role": row["resolution_role"],
                "anchor_pmid": row["anchor_pmid"],
                "anchor_title": row["anchor_title"],
                "anchor_url": f"https://pubmed.ncbi.nlm.nih.gov/{row['anchor_pmid']}/",
                "query_caveat": row["query_caveat"],
                "slot_scope": "core_non_binder_01..03",
                "slot_row_count": _int(slot_summary.get("row_count")),
                "slot_top_packet_step": _text(slot_summary.get("top_packet_step")),
                "exclusion_primary_focus_ligand": _text(exclusion_summary.get("primary_focus_ligand")),
                "exclusion_reference_row_count": _int(exclusion_summary.get("row_count")),
                "authoritative_apply_allowed": False,
            }
        )

    summary = {
        "family": "aqp1",
        "as_of_date": today,
        "row_count": len(rows),
        "slot_row_count": _int(slot_summary.get("row_count")),
        "primary_query_label": rows[0]["query_label"] if rows else "",
        "primary_anchor_pmid": rows[0]["anchor_pmid"] if rows else "",
        "primary_anchor_url": rows[0]["anchor_url"] if rows else "",
        "exclusion_primary_focus_ligand": _text(exclusion_summary.get("primary_focus_ligand")),
        "packet_artifact": "runs/aqp1_negative_evidence_acquisition_packet_current.md",
        "next_required_step": (
            "Start AQP1 negative evidence follow-up from PMID 23123479, then use the acetazolamide and tetraethylammonium boundary queries only as context. "
            "Keep all three core_non_binder slots review-only until a direct transporter-specific quantitative negative row is curated."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# AQP1 Negative Evidence Acquisition Packet",
        "",
        f"- family: `{s['family']}`",
        f"- as_of_date: `{s['as_of_date']}`",
        f"- row_count: `{s['row_count']}`",
        f"- slot_row_count: `{s['slot_row_count']}`",
        f"- primary_query_label: `{s['primary_query_label']}`",
        f"- primary_anchor_pmid: `{s['primary_anchor_pmid']}`",
        f"- exclusion_primary_focus_ligand: `{s['exclusion_primary_focus_ligand']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Query Rows",
        "",
        "| query_rank | query_label | anchor_pmid | resolution_role | query_caveat |",
        "| ---: | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['query_rank']} | `{row['query_label']}` | `{row['anchor_pmid']}` | "
            f"`{row['resolution_role']}` | `{row['query_caveat']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the AQP1 negative evidence acquisition packet.")
    parser.add_argument("--negative-slot-closure-json", default=DEFAULT_NEGATIVE_SLOT_CLOSURE_JSON)
    parser.add_argument("--negative-source-exclusion-json", default=DEFAULT_NEGATIVE_SOURCE_EXCLUSION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.negative_slot_closure_json),
        _load_json(args.negative_source_exclusion_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
