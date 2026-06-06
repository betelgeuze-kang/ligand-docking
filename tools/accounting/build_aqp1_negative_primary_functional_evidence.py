#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
RUNS = Path("runs")

DEFAULT_OUT_JSON = RUNS / "aqp1_negative_primary_functional_evidence_current.json"
DEFAULT_OUT_CSV = RUNS / "aqp1_negative_primary_functional_evidence_current.csv"
DEFAULT_OUT_MD = RUNS / "aqp1_negative_primary_functional_evidence_current.md"
DEFAULT_INTAKE_CSV = RUNS / "aqp1_negative_evidence_intake_current.csv"

TARGET_ID = "AQP1"
TARGET_ACCESSION = "P29972"
TARGET_CHEMBL_ID = "CHEMBL4523210"
SOURCE_PMID = "23123479"
SOURCE_DOI = "10.1248/bpb.b12-00581"
SOURCE_URL = "https://www.jstage.jst.go.jp/article/bpb/35/11/35_b12-00581/_article"
SOURCE_TITLE = (
    "Reinvestigation of drugs and chemicals as aquaporin-1 inhibitors using "
    "pressure-induced hemolysis in human erythrocytes."
)
SOURCE_CITATION = "Yamaguchi T, Iwata Y, Miura S, Kawada K. Biol Pharm Bull. 2012;35(11):2088-2091."
ASSAY_CONTEXT = "human erythrocyte pressure-induced hemolysis attributed to AQP1 water transport"
ENDPOINT = "pressure_induced_hemolysis_percent_at_200_mpa"
PRIMARY_SOURCE = (
    f"primary_journal_article:Biol Pharm Bull 2012; PMID:{SOURCE_PMID}; DOI:{SOURCE_DOI}; "
    "J-STAGE free access"
)
SOURCE_ID = f"PMID:{SOURCE_PMID}; DOI:{SOURCE_DOI}; J-STAGE:{SOURCE_URL}"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _evidence_rows() -> list[dict[str, Any]]:
    base = {
        "target_id": TARGET_ID,
        "target_accession": TARGET_ACCESSION,
        "target_chembl_id": TARGET_CHEMBL_ID,
        "target_organism": "Homo sapiens",
        "assay_context": ASSAY_CONTEXT,
        "endpoint": ENDPOINT,
        "standard_type": "Hemolysis",
        "standard_relation": "=",
        "standard_units": "percent",
        "primary_source": PRIMARY_SOURCE,
        "source_id": SOURCE_ID,
        "negative_semantics": "no_transport_effect",
        "curator_decision": "ready_for_authoritative_negative_review",
    }
    rows = [
        {
            **base,
            "slot_queue_id": "AQP1__core_non_binder_01",
            "request_rank": "1",
            "packet_step": "core_non_binder_01",
            "candidate_scope": "sodium nitroprusside primary functional no-effect row",
            "candidate_name": "sodium nitroprusside",
            "molecule_id": "CHEMBL136478|PubChem:6604165",
            "standard_value": "38.9",
            "concentration_or_curve_range": "0.1 mM; matched control 0 mM = 39.1 +/- 3.0% hemolysis",
            "replicate_or_error_model": "n=3; mean +/- SD = 38.9 +/- 2.8% hemolysis",
            "split_id": "aqp1_negative_primary_functional_v1_slot_01",
            "reference_meta_id": "aqp1_negative_reference_meta_primary_2012_slot_01",
            "curator_notes": (
                "Primary-source row: hemolysis at 200 MPa stayed near matched control, supporting no AQP1 "
                "inhibitor effect in human erythrocytes."
            ),
        },
        {
            **base,
            "slot_queue_id": "AQP1__core_non_binder_02",
            "request_rank": "2",
            "packet_step": "core_non_binder_02",
            "candidate_scope": "sodium nitroprusside primary functional no-effect row",
            "candidate_name": "sodium nitroprusside",
            "molecule_id": "CHEMBL136478|PubChem:6604165",
            "standard_value": "38.1",
            "concentration_or_curve_range": "0.5 mM; matched control 0 mM = 39.1 +/- 3.0% hemolysis",
            "replicate_or_error_model": "n=3; mean +/- SD = 38.1 +/- 1.8% hemolysis",
            "split_id": "aqp1_negative_primary_functional_v1_slot_02",
            "reference_meta_id": "aqp1_negative_reference_meta_primary_2012_slot_02",
            "curator_notes": (
                "Primary-source row: no hemolysis enhancement at 200 MPa; the paper interprets sodium "
                "nitroprusside as not an AQP1 inhibitor in human erythrocytes."
            ),
        },
        {
            **base,
            "slot_queue_id": "AQP1__core_non_binder_03",
            "request_rank": "3",
            "packet_step": "core_non_binder_03",
            "candidate_scope": "acetazolamide primary functional no-effect row",
            "candidate_name": "acetazolamide",
            "molecule_id": "CHEMBL20|PubChem:1986",
            "standard_value": "39.0",
            "concentration_or_curve_range": "1 mM; matched control 0 mM = 39.6 +/- 3.1% hemolysis",
            "replicate_or_error_model": "n=3; mean +/- SD = 39.0 +/- 2.5% hemolysis",
            "split_id": "aqp1_negative_primary_functional_v1_slot_03",
            "reference_meta_id": "aqp1_negative_reference_meta_primary_2012_slot_03",
            "curator_notes": (
                "Primary-source row: pressure-induced hemolysis was not affected by acetazolamide in human "
                "erythrocytes; this is accepted only as a primary functional no-effect row, not as a binding Kd/Ki."
            ),
        },
    ]
    return rows


def build_payload(*, as_of_date: str | None = None) -> dict[str, Any]:
    rows = _evidence_rows()
    summary = {
        "curation_ready": True,
        "packet_artifact": str(DEFAULT_OUT_MD),
        "intake_csv_artifact": str(DEFAULT_INTAKE_CSV),
        "as_of_date": as_of_date or date.today().isoformat(),
        "target_id": TARGET_ID,
        "target_uniprot_accession": TARGET_ACCESSION,
        "target_chembl_id": TARGET_CHEMBL_ID,
        "source_pmid": SOURCE_PMID,
        "source_doi": SOURCE_DOI,
        "source_url": SOURCE_URL,
        "source_title": SOURCE_TITLE,
        "source_citation": SOURCE_CITATION,
        "source_article_type": "primary_journal_article",
        "assay_context": ASSAY_CONTEXT,
        "endpoint": ENDPOINT,
        "curated_row_count": len(rows),
        "direct_negative_quantitative_row_found_count": len(rows),
        "slot_cover_ready_count": len({row["slot_queue_id"] for row in rows}),
        "required_slot_count": 3,
        "split_reference_meta_ready": True,
        "authoritative_negative_apply_allowed_count": len(rows),
        "negative_evidence_closure_allowed": True,
        "claim_promotion_allowed": False,
        "curation_status": "primary_functional_no_effect_rows_ready_for_authoritative_negative_apply",
        "next_required_step": (
            "Run the AQP1 intake gate and transporter negative authoritative apply gate; keep the evidence label "
            "as functional no-effect, not direct binding affinity."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# AQP1 Negative Primary Functional Evidence",
        "",
        f"- curation_ready: `{s['curation_ready']}`",
        f"- target_id: `{s['target_id']}`",
        f"- target_uniprot_accession: `{s['target_uniprot_accession']}`",
        f"- target_chembl_id: `{s['target_chembl_id']}`",
        f"- source_pmid: `{s['source_pmid']}`",
        f"- source_doi: `{s['source_doi']}`",
        f"- source_url: `{s['source_url']}`",
        f"- source_article_type: `{s['source_article_type']}`",
        f"- assay_context: `{s['assay_context']}`",
        f"- endpoint: `{s['endpoint']}`",
        f"- direct_negative_quantitative_row_found_count: `{s['direct_negative_quantitative_row_found_count']}`",
        f"- slot_cover_ready_count: `{s['slot_cover_ready_count']}/{s['required_slot_count']}`",
        f"- split_reference_meta_ready: `{s['split_reference_meta_ready']}`",
        f"- authoritative_negative_apply_allowed_count: `{s['authoritative_negative_apply_allowed_count']}`",
        f"- negative_evidence_closure_allowed: `{s['negative_evidence_closure_allowed']}`",
        f"- claim_promotion_allowed: `{s['claim_promotion_allowed']}`",
        f"- curation_status: `{s['curation_status']}`",
        "",
        "## Evidence Rows",
        "",
        "| slot | candidate | concentration | value | replicate | semantics |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['slot_queue_id']}` | `{row['candidate_name']}` | "
            f"`{row['concentration_or_curve_range']}` | `{row['standard_value']} {row['standard_units']}` | "
            f"`{row['replicate_or_error_model']}` | `{row['negative_semantics']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build curated primary functional AQP1 negative evidence rows.")
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    parser.add_argument("--intake-csv", default=str(DEFAULT_INTAKE_CSV))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload()
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    intake_csv = _resolve(args.intake_csv)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    write_csv_rows(intake_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
