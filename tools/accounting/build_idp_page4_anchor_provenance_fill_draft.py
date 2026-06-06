#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_EVIDENCE_SEED_JSON = "runs/idp_page4_anchor_evidence_seed_current.json"
DEFAULT_CURATION_PACKET_JSON = "runs/idp_page4_anchor_curation_packet_current.json"
DEFAULT_OUT_JSON = "runs/idp_page4_anchor_provenance_fill_draft_current.json"
DEFAULT_OUT_CSV = "runs/idp_page4_anchor_provenance_fill_draft_current.csv"
DEFAULT_OUT_MD = "runs/idp_page4_anchor_provenance_fill_draft_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def build_payload(
    evidence_seed_payload: dict[str, Any],
    curation_packet_payload: dict[str, Any],
) -> dict[str, Any]:
    seed_s = dict((evidence_seed_payload.get("summary") if isinstance(evidence_seed_payload.get("summary"), dict) else {}) or {})
    packet_s = dict((curation_packet_payload.get("summary") if isinstance(curation_packet_payload.get("summary"), dict) else {}) or {})

    residue_count = int(seed_s.get("residue_count", 0) or 0)
    citation = str(seed_s.get("first_open_source_anchor", "")).strip()
    citation_url = str(seed_s.get("first_open_source_url", "")).strip()
    construct_mapping = (
        f"synthetic page4 target likely maps to PAGE4 full-length {residue_count}-aa construct candidate"
        if residue_count
        else "synthetic page4 target likely maps to PAGE4 full-length construct candidate"
    )
    condition_mapping = (
        "baseline_disorder_identity primary; phosphorylation-state follow-up required for ph_low/ph_high and compactness/branch-state interpretation"
    )

    rows = [
        {
            "fill_field": "candidate_anchor_citation",
            "draft_value": citation,
            "source_url": citation_url,
            "why_now": "Best local construct-level provenance anchor already exists in repo metadata and seed sheet.",
            "freeze_status": "draft_not_frozen",
            "next_action": "confirm construct alias against the disorder anchor paper before freezing",
        },
        {
            "fill_field": "construct_mapping",
            "draft_value": construct_mapping,
            "source_url": citation_url,
            "why_now": "Benchmark target length and local provenance support the PAGE4 full-length identity hypothesis.",
            "freeze_status": "draft_not_frozen",
            "next_action": "keep as hypothesis wording until construct details are confirmed from the anchor paper",
        },
        {
            "fill_field": "condition_mapping",
            "draft_value": condition_mapping,
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/26242913/ ; https://pubmed.ncbi.nlm.nih.gov/28289210/",
            "why_now": "Current page4 errors are condition-sensitive, so the draft should already separate baseline identity from phosphorylation-state follow-up.",
            "freeze_status": "draft_not_frozen",
            "next_action": "use PAGE4 phosphorylation papers to keep state-specific follow-up explicit before anchor replacement",
        },
        {
            "fill_field": "followup_state_specific_sources",
            "draft_value": "PMID 26242913 ; PMID 28289210",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/26242913/ ; https://pubmed.ncbi.nlm.nih.gov/28289210/",
            "why_now": "These are the immediate state-specific follow-ups after the construct-level disorder anchor.",
            "freeze_status": "supporting_context_only",
            "next_action": "extract only construct-matched compactness, helicity, or aggregation-negative support",
        },
    ]

    summary = {
        "status": "page4_anchor_provenance_fill_draft_ready",
        "target_name": "page4",
        "candidate_anchor_citation": citation,
        "candidate_anchor_url": citation_url,
        "citation_confirmed_packet_artifact": "runs/idp_page4_anchor_citation_confirmed_packet_current.md",
        "identity_status": "hypothesis_only",
        "identity_claim_allowed_now": False,
        "construct_mapping": construct_mapping,
        "fragment_evidence_policy": "fragment_not_sufficient",
        "condition_mapping": condition_mapping,
        "state_mixing_allowed": False,
        "followup_source_count": 2,
        "current_wrong_conditions": list(packet_s.get("current_wrong_conditions", []) or []),
        "promotion_ready": False,
        "next_required_step": (
            "Freeze these draft values into the page4 citation-confirmed packet, then use the phosphorylation-state follow-up papers before any page4 anchor replacement decision."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Page4 Anchor Provenance Fill Draft",
        "",
        f"- status: `{s['status']}`",
        f"- target_name: `{s['target_name']}`",
        f"- candidate_anchor_citation: `{s['candidate_anchor_citation']}`",
        f"- candidate_anchor_url: `{s['candidate_anchor_url']}`",
        f"- citation_confirmed_packet_artifact: `{s['citation_confirmed_packet_artifact']}`",
        f"- identity_status: `{s['identity_status']}`",
        f"- identity_claim_allowed_now: `{s['identity_claim_allowed_now']}`",
        f"- construct_mapping: `{s['construct_mapping']}`",
        f"- fragment_evidence_policy: `{s['fragment_evidence_policy']}`",
        f"- condition_mapping: `{s['condition_mapping']}`",
        f"- state_mixing_allowed: `{s['state_mixing_allowed']}`",
        f"- followup_source_count: `{s['followup_source_count']}`",
        f"- current_wrong_conditions: `{', '.join(s['current_wrong_conditions'])}`",
        f"- promotion_ready: `{s['promotion_ready']}`",
        "",
        "## Fill Rows",
        "",
        "| fill_field | draft_value | freeze_status | next_action |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['fill_field']}` | `{row['draft_value']}` | `{row['freeze_status']}` | {row['next_action']} |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a draft provenance-fill packet for the first page4 anchor replacement fields.")
    parser.add_argument("--evidence-seed-json", default=DEFAULT_EVIDENCE_SEED_JSON)
    parser.add_argument("--curation-packet-json", default=DEFAULT_CURATION_PACKET_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.evidence_seed_json),
        _load_json(args.curation_packet_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
