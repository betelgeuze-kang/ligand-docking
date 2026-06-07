#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_OUT_JSON = "runs/aqp1_negative_exact_source_outcome_packet_current.json"
DEFAULT_OUT_CSV = "runs/aqp1_negative_exact_source_outcome_packet_current.csv"
DEFAULT_OUT_MD = "runs/aqp1_negative_exact_source_outcome_packet_current.md"

PMID = "23123479"
TITLE = "Reinvestigation of drugs and chemicals as aquaporin-1 inhibitors using pressure-induced hemolysis in human erythrocytes."
URL = "https://pubmed.ncbi.nlm.nih.gov/23123479/"
SOURCE_ASSAY_CONTEXT = "human_erythrocyte_pressure_induced_hemolysis"
SOURCE_ENDPOINT = "hemolysis_at_200_mpa"
PROMOTION_GATE_FAILED_REASON = "not_a_direct_transporter_specific_quantitative_negative_binding_or_flux_row"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_payload(*, as_of_date: str | None = None) -> dict[str, Any]:
    today = as_of_date or date.today().isoformat()
    rows = [
        {
            "outcome_rank": 1,
            "candidate_name": "sodium nitroprusside",
            "molecule_chembl_id": "CHEMBL136478",
            "exact_source_role": "primary_negative_probe_unaffected_outcome",
            "source_pmid": PMID,
            "source_title": TITLE,
            "source_url": URL,
            "source_assay_context": SOURCE_ASSAY_CONTEXT,
            "source_endpoint": SOURCE_ENDPOINT,
            "hemolysis_outcome": "almost_unaffected_at_200_mpa",
            "outcome_direction": "unchanged",
            "aqp1_interpretation": "exact_source_negative_probe_candidate_conflicts_with_older_permeability_reports_not_direct_quantitative_negative_row",
            "direct_transporter_specific_quantitative_negative_row_found": False,
            "promotion_gate_failed_reason": PROMOTION_GATE_FAILED_REASON,
            "authoritative_negative_apply_allowed": False,
        },
        {
            "outcome_rank": 2,
            "candidate_name": "acetazolamide",
            "molecule_chembl_id": "CHEMBL20",
            "exact_source_role": "positive_boundary_unaffected_outcome",
            "source_pmid": PMID,
            "source_title": TITLE,
            "source_url": URL,
            "source_assay_context": SOURCE_ASSAY_CONTEXT,
            "source_endpoint": SOURCE_ENDPOINT,
            "hemolysis_outcome": "almost_unaffected_at_200_mpa",
            "outcome_direction": "unchanged",
            "aqp1_interpretation": "boundary_only_not_authoritative_negative",
            "direct_transporter_specific_quantitative_negative_row_found": False,
            "promotion_gate_failed_reason": PROMOTION_GATE_FAILED_REASON,
            "authoritative_negative_apply_allowed": False,
        },
        {
            "outcome_rank": 3,
            "candidate_name": "tetraethylammonium",
            "molecule_chembl_id": "CHEMBL9324",
            "exact_source_role": "tool_reference_decreased_hemolysis_outcome",
            "source_pmid": PMID,
            "source_title": TITLE,
            "source_url": URL,
            "source_assay_context": SOURCE_ASSAY_CONTEXT,
            "source_endpoint": SOURCE_ENDPOINT,
            "hemolysis_outcome": "decreased_hemolysis_at_200_mpa",
            "outcome_direction": "decreased",
            "aqp1_interpretation": "tool_reference_context_not_authoritative_negative",
            "direct_transporter_specific_quantitative_negative_row_found": False,
            "promotion_gate_failed_reason": PROMOTION_GATE_FAILED_REASON,
            "authoritative_negative_apply_allowed": False,
        },
        {
            "outcome_rank": 4,
            "candidate_name": "dimethyl sulfoxide",
            "molecule_chembl_id": "CHEMBL504",
            "exact_source_role": "small_inhibitor_signal_solvent_context",
            "source_pmid": PMID,
            "source_title": TITLE,
            "source_url": URL,
            "source_assay_context": SOURCE_ASSAY_CONTEXT,
            "source_endpoint": SOURCE_ENDPOINT,
            "hemolysis_outcome": "increased_significantly_at_200_mpa",
            "outcome_direction": "increased",
            "aqp1_interpretation": "exact_source_small_inhibitor_signal_not_negative_candidate",
            "direct_transporter_specific_quantitative_negative_row_found": False,
            "promotion_gate_failed_reason": PROMOTION_GATE_FAILED_REASON,
            "authoritative_negative_apply_allowed": False,
        },
    ]

    almost_unaffected_candidate_count = sum(
        1 for row in rows if row["hemolysis_outcome"] == "almost_unaffected_at_200_mpa"
    )
    direct_negative_quantitative_row_found_count = sum(
        1
        for row in rows
        if row["direct_transporter_specific_quantitative_negative_row_found"]
    )
    authoritative_negative_apply_allowed_count = sum(
        1 for row in rows if row["authoritative_negative_apply_allowed"]
    )
    summary = {
        "family": "aqp1",
        "as_of_date": today,
        "row_count": len(rows),
        "source_assay_context": SOURCE_ASSAY_CONTEXT,
        "source_endpoint": SOURCE_ENDPOINT,
        "almost_unaffected_candidate_count": almost_unaffected_candidate_count,
        "primary_negative_probe_candidate": "sodium nitroprusside",
        "positive_boundary_candidate": "acetazolamide",
        "tool_reference_candidate": "tetraethylammonium",
        "small_inhibitor_signal_candidate": "dimethyl sulfoxide",
        "source_pmid": PMID,
        "direct_negative_quantitative_row_found_count": direct_negative_quantitative_row_found_count,
        "authoritative_negative_apply_allowed_count": authoritative_negative_apply_allowed_count,
        "promotion_gate_failed_reason": PROMOTION_GATE_FAILED_REASON,
        "packet_artifact": "runs/aqp1_negative_exact_source_outcome_packet_current.md",
        "next_required_step": (
            "Use PMID 23123479 as the exact-source outcome anchor: sodium nitroprusside and acetazolamide were almost unaffected at 200 MPa, tetraethylammonium decreased hemolysis, and dimethyl sulfoxide showed the only small inhibitor-like signal. Keep sodium nitroprusside as the first review-only negative probe candidate, explicitly note that this exact-source outcome conflicts with older permeability reports, and do not treat dimethyl sulfoxide as a negative fallback."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# AQP1 Negative Exact-Source Outcome Packet",
        "",
        f"- family: `{s['family']}`",
        f"- as_of_date: `{s['as_of_date']}`",
        f"- row_count: `{s['row_count']}`",
        f"- source_assay_context: `{s['source_assay_context']}`",
        f"- source_endpoint: `{s['source_endpoint']}`",
        f"- almost_unaffected_candidate_count: `{s['almost_unaffected_candidate_count']}`",
        f"- primary_negative_probe_candidate: `{s['primary_negative_probe_candidate']}`",
        f"- positive_boundary_candidate: `{s['positive_boundary_candidate']}`",
        f"- tool_reference_candidate: `{s['tool_reference_candidate']}`",
        f"- small_inhibitor_signal_candidate: `{s['small_inhibitor_signal_candidate']}`",
        f"- source_pmid: `{s['source_pmid']}`",
        f"- direct_negative_quantitative_row_found_count: `{s['direct_negative_quantitative_row_found_count']}`",
        f"- authoritative_negative_apply_allowed_count: `{s['authoritative_negative_apply_allowed_count']}`",
        f"- promotion_gate_failed_reason: `{s['promotion_gate_failed_reason']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Exact-Source Outcomes",
        "",
        "| outcome_rank | candidate_name | exact_source_role | hemolysis_outcome | outcome_direction | aqp1_interpretation |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['outcome_rank']} | `{row['candidate_name']}` | `{row['exact_source_role']}` | "
            f"`{row['hemolysis_outcome']}` | `{row['outcome_direction']}` | `{row['aqp1_interpretation']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the AQP1 negative exact-source outcome packet.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload()
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
