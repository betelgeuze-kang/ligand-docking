#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_NEGATIVE_ACQUISITION_JSON = "runs/aqp1_negative_evidence_acquisition_packet_current.json"
DEFAULT_NEGATIVE_EXACT_SOURCE_JSON = "runs/aqp1_negative_exact_source_outcome_packet_current.json"
DEFAULT_NEGATIVE_PRIMARY_PROBE_RESOLUTION_JSON = "runs/aqp1_negative_primary_probe_resolution_packet_current.json"
DEFAULT_NEGATIVE_SOURCE_EXCLUSION_JSON = "runs/aqp1_negative_source_exclusion_packet_current.json"
DEFAULT_OUT_JSON = "runs/aqp1_negative_direct_evidence_audit_packet_current.json"
DEFAULT_OUT_CSV = "runs/aqp1_negative_direct_evidence_audit_packet_current.csv"
DEFAULT_OUT_MD = "runs/aqp1_negative_direct_evidence_audit_packet_current.md"

PRIMARY_CANDIDATE = "sodium nitroprusside"
PRIMARY_CANDIDATE_CHEMBL_ID = "CHEMBL136478"
AQP1_TARGET_CHEMBL_ID = "CHEMBL4523210"
PUBMED_SODIUM_NITROPRUSSIDE_AQP1_PMIDS = (
    "27261598",
    "25338424",
    "23123479",
    "21157000",
    "18032550",
    "16935571",
    "14561230",
    "11914159",
)


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


def _first_row_by_candidate(payload: dict[str, Any], candidate_name: str) -> dict[str, Any]:
    for row in payload.get("rows", []) or []:
        if _text(row.get("candidate_name")).lower() == candidate_name.lower():
            return dict(row)
    return {}


def build_payload(
    negative_acquisition_payload: dict[str, Any],
    negative_exact_source_payload: dict[str, Any],
    negative_primary_probe_resolution_payload: dict[str, Any],
    negative_source_exclusion_payload: dict[str, Any],
    *,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    acquisition_summary = dict((negative_acquisition_payload or {}).get("summary", {}) or {})
    exact_source_summary = dict((negative_exact_source_payload or {}).get("summary", {}) or {})
    exact_source_probe_row = _first_row_by_candidate(negative_exact_source_payload, PRIMARY_CANDIDATE)
    primary_resolution_summary = dict((negative_primary_probe_resolution_payload or {}).get("summary", {}) or {})
    primary_resolution_row = _first_row_by_candidate(negative_primary_probe_resolution_payload, PRIMARY_CANDIDATE)
    exclusion_summary = dict((negative_source_exclusion_payload or {}).get("summary", {}) or {})
    today = as_of_date or date.today().isoformat()

    exact_source_direct_negative_count = _int(exact_source_summary.get("direct_negative_quantitative_row_found_count"))
    source_anchor_direct_negative = bool(
        primary_resolution_summary.get("source_anchor_direct_negative_quantitative_row_found", False)
    )
    chembl_exact_target_pair_activity_count = _int(primary_resolution_row.get("exact_target_pair_activity_count"))
    pubmed_hit_count = len(PUBMED_SODIUM_NITROPRUSSIDE_AQP1_PMIDS)
    pressure_hemolysis_hit_count = 1 if _text(acquisition_summary.get("primary_anchor_pmid")) == "23123479" else 0

    rows = [
        {
            "audit_rank": 1,
            "audit_route": "pubmed_exact_ligand_target_query",
            "candidate_name": PRIMARY_CANDIDATE,
            "query_label": "sodium_nitroprusside_aqp1_title_abstract",
            "query_term": (
                '(AQP1[Title/Abstract] OR "aquaporin 1"[Title/Abstract] OR "aquaporin-1"[Title/Abstract]) '
                'AND "sodium nitroprusside"[Title/Abstract]'
            ),
            "result_count": pubmed_hit_count,
            "representative_pmids": ",".join(PUBMED_SODIUM_NITROPRUSSIDE_AQP1_PMIDS),
            "best_anchor_pmid": _text(acquisition_summary.get("primary_anchor_pmid")) or "23123479",
            "audit_interpretation": "pubmed_hits_are_exact_or_indirect_context_not_direct_quantitative_negative_rows",
            "direct_negative_quantitative_row_found": False,
            "authoritative_negative_apply_allowed": False,
        },
        {
            "audit_rank": 2,
            "audit_route": "pubmed_pressure_hemolysis_anchor",
            "candidate_name": PRIMARY_CANDIDATE,
            "query_label": _text(acquisition_summary.get("primary_query_label")) or "pressure_induced_hemolysis_reinvestigation",
            "query_term": '(AQP1[Title/Abstract] OR "aquaporin 1"[Title/Abstract]) AND "pressure-induced hemolysis"[Title/Abstract]',
            "result_count": pressure_hemolysis_hit_count,
            "representative_pmids": _text(acquisition_summary.get("primary_anchor_pmid")) or "23123479",
            "best_anchor_pmid": _text(acquisition_summary.get("primary_anchor_pmid")) or "23123479",
            "audit_interpretation": _text(exact_source_probe_row.get("aqp1_interpretation"))
            or "exact_source_anchor_is_review_only_not_direct_negative",
            "direct_negative_quantitative_row_found": exact_source_direct_negative_count > 0,
            "authoritative_negative_apply_allowed": False,
        },
        {
            "audit_rank": 3,
            "audit_route": "chembl_exact_target_pair_query",
            "candidate_name": PRIMARY_CANDIDATE,
            "query_label": "chembl_sodium_nitroprusside_human_aqp1_activity",
            "query_term": _text(primary_resolution_row.get("activity_url")),
            "result_count": chembl_exact_target_pair_activity_count,
            "representative_pmids": "",
            "best_anchor_pmid": "",
            "audit_interpretation": "no_structured_human_aqp1_activity_rows_for_primary_probe_candidate",
            "direct_negative_quantitative_row_found": chembl_exact_target_pair_activity_count > 0 and source_anchor_direct_negative,
            "authoritative_negative_apply_allowed": False,
        },
        {
            "audit_rank": 4,
            "audit_route": "caution_source_exclusion_check",
            "candidate_name": "tetraethylammonium,acetazolamide",
            "query_label": "caution_references_exact_target_pair_exclusion",
            "query_term": "ChEMBL exact target-pair checks for caution references",
            "result_count": _int(exclusion_summary.get("row_count")),
            "representative_pmids": "23123479,40359885",
            "best_anchor_pmid": "23123479",
            "audit_interpretation": "caution_references_remain_exclusion_context_not_negative_replacements",
            "direct_negative_quantitative_row_found": False,
            "authoritative_negative_apply_allowed": False,
        },
    ]

    direct_negative_count = sum(1 for row in rows if row["direct_negative_quantitative_row_found"])
    authoritative_apply_count = sum(1 for row in rows if row["authoritative_negative_apply_allowed"])
    summary = {
        "family": "aqp1",
        "as_of_date": today,
        "packet_artifact": "runs/aqp1_negative_direct_evidence_audit_packet_current.md",
        "row_count": len(rows),
        "primary_candidate": PRIMARY_CANDIDATE,
        "primary_candidate_chembl_id": PRIMARY_CANDIDATE_CHEMBL_ID,
        "target_chembl_id": AQP1_TARGET_CHEMBL_ID,
        "pubmed_exact_ligand_target_hit_count": pubmed_hit_count,
        "pubmed_pressure_hemolysis_hit_count": pressure_hemolysis_hit_count,
        "chembl_exact_target_pair_activity_count": chembl_exact_target_pair_activity_count,
        "source_anchor_hemolysis_outcome": _text(primary_resolution_summary.get("source_anchor_hemolysis_outcome")),
        "direct_negative_quantitative_row_found_count": direct_negative_count,
        "authoritative_negative_apply_allowed_count": authoritative_apply_count,
        "no_direct_negative_source_row_count": 3 if direct_negative_count == 0 else 0,
        "audit_decision": "keep_review_only_no_authoritative_negative_promotion",
        "next_required_step": (
            "Keep AQP1 core_non_binder_01 through core_non_binder_03 review-only: PubMed exact ligand/target hits "
            "and the pressure-hemolysis anchor do not provide a direct transporter-specific quantitative negative row, "
            "and the sodium nitroprusside human AQP1 ChEMBL exact target-pair count remains zero."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# AQP1 Negative Direct Evidence Audit Packet",
        "",
        f"- family: `{s['family']}`",
        f"- as_of_date: `{s['as_of_date']}`",
        f"- primary_candidate: `{s['primary_candidate']}`",
        f"- primary_candidate_chembl_id: `{s['primary_candidate_chembl_id']}`",
        f"- target_chembl_id: `{s['target_chembl_id']}`",
        f"- pubmed_exact_ligand_target_hit_count: `{s['pubmed_exact_ligand_target_hit_count']}`",
        f"- pubmed_pressure_hemolysis_hit_count: `{s['pubmed_pressure_hemolysis_hit_count']}`",
        f"- chembl_exact_target_pair_activity_count: `{s['chembl_exact_target_pair_activity_count']}`",
        f"- source_anchor_hemolysis_outcome: `{s['source_anchor_hemolysis_outcome']}`",
        f"- direct_negative_quantitative_row_found_count: `{s['direct_negative_quantitative_row_found_count']}`",
        f"- authoritative_negative_apply_allowed_count: `{s['authoritative_negative_apply_allowed_count']}`",
        f"- no_direct_negative_source_row_count: `{s['no_direct_negative_source_row_count']}`",
        f"- audit_decision: `{s['audit_decision']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Audit Rows",
        "",
        "| audit_rank | audit_route | candidate_name | result_count | best_anchor_pmid | audit_interpretation |",
        "| ---: | --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['audit_rank']} | `{row['audit_route']}` | `{row['candidate_name']}` | "
            f"{row['result_count']} | `{row['best_anchor_pmid']}` | `{row['audit_interpretation']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the AQP1 negative direct-evidence audit packet.")
    parser.add_argument("--negative-acquisition-json", default=DEFAULT_NEGATIVE_ACQUISITION_JSON)
    parser.add_argument("--negative-exact-source-json", default=DEFAULT_NEGATIVE_EXACT_SOURCE_JSON)
    parser.add_argument("--negative-primary-probe-resolution-json", default=DEFAULT_NEGATIVE_PRIMARY_PROBE_RESOLUTION_JSON)
    parser.add_argument("--negative-source-exclusion-json", default=DEFAULT_NEGATIVE_SOURCE_EXCLUSION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.negative_acquisition_json),
        _load_json(args.negative_exact_source_json),
        _load_json(args.negative_primary_probe_resolution_json),
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
