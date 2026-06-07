#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_EVIDENCE_SEED_JSON = "runs/idp_page4_anchor_evidence_seed_current.json"
DEFAULT_PROVENANCE_FILL_JSON = "runs/idp_page4_anchor_provenance_fill_draft_current.json"
DEFAULT_FOLLOWUP_PACKET_MD = "runs/idp_page4_phosphorylation_followup_packet_current.md"
DEFAULT_OUT_JSON = "runs/idp_page4_anchor_citation_confirmed_packet_current.json"
DEFAULT_OUT_CSV = "runs/idp_page4_anchor_citation_confirmed_packet_current.csv"
DEFAULT_OUT_MD = "runs/idp_page4_anchor_citation_confirmed_packet_current.md"


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
    provenance_fill_payload: dict[str, Any],
) -> dict[str, Any]:
    seed_s = dict((evidence_seed_payload.get("summary") if isinstance(evidence_seed_payload.get("summary"), dict) else {}) or {})
    draft_s = dict((provenance_fill_payload.get("summary") if isinstance(provenance_fill_payload.get("summary"), dict) else {}) or {})

    citation = str(draft_s.get("candidate_anchor_citation", "") or seed_s.get("first_open_source_anchor", "")).strip()
    citation_url = str(draft_s.get("candidate_anchor_url", "") or seed_s.get("first_open_source_url", "")).strip()
    construct_mapping = str(draft_s.get("construct_mapping", "")).strip() or str(seed_s.get("identity_hypothesis", "")).strip()
    wrong_conditions = list(draft_s.get("current_wrong_conditions", []) or [])

    rows = [
        {
            "packet_field": "confirmed_construct_anchor",
            "confirmed_value": citation,
            "source_url": citation_url,
            "freeze_status": "citation_confirmed",
            "next_action": "Use this as the frozen construct-level anchor while keeping PAGE4 identity wording cautious and full-length only.",
        },
        {
            "packet_field": "confirmed_construct_mapping",
            "confirmed_value": construct_mapping,
            "source_url": citation_url,
            "freeze_status": "citation_confirmed_hypothesis_only",
            "next_action": "Keep construct wording at the full-length PAGE4 candidate level and do not mix fragment evidence into the replacement anchor.",
        },
        {
            "packet_field": "phosphorylation_state_followup",
            "confirmed_value": "PMID 26242913 and PMID 28289210 remain required for ph_low/ph_high compactness and branch-state interpretation.",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/26242913/ ; https://pubmed.ncbi.nlm.nih.gov/28289210/",
            "freeze_status": "followup_required",
            "next_action": "Extract construct-matched state-specific compactness, helicity, and aggregation-negative support before any page4 anchor replacement.",
        },
        {
            "packet_field": "promotion_guardrail",
            "confirmed_value": "broader_full_idp_promotion remains blocked until phosphorylation-state follow-up is explicit",
            "source_url": "",
            "freeze_status": "guardrail_locked",
            "next_action": "Do not move page4 into a true broader roster or freeze a replacement anchor until the phosphorylation-state follow-up is complete.",
        },
    ]

    summary = {
        "status": "page4_anchor_citation_confirmed_packet_ready",
        "target_name": "page4",
        "confirmed_anchor_citation": citation,
        "confirmed_anchor_url": citation_url,
        "construct_mapping": construct_mapping,
        "construct_confirmation_status": "construct_citation_confirmed",
        "identity_status": "construct_citation_confirmed_state_followup_required",
        "identity_claim_allowed_now": False,
        "followup_packet_artifact": DEFAULT_FOLLOWUP_PACKET_MD,
        "fragment_evidence_policy": "fragment_not_sufficient",
        "state_mixing_allowed": False,
        "phosphorylation_state_followup_required": True,
        "followup_source_count": 2,
        "followup_source_anchors": "PMID 26242913 ; PMID 28289210",
        "current_wrong_conditions": wrong_conditions,
        "promotion_ready": False,
        "next_required_step": (
            "Keep the construct citation frozen, open the page4 phosphorylation-state follow-up packet next, then use the PAGE4 phosphorylation-state follow-up papers to separate ph_low/ph_high compactness and branch-state interpretation "
            "before any page4 anchor replacement or true broader rerun."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Page4 Anchor Citation-Confirmed Packet",
        "",
        f"- status: `{s['status']}`",
        f"- target_name: `{s['target_name']}`",
        f"- confirmed_anchor_citation: `{s['confirmed_anchor_citation']}`",
        f"- confirmed_anchor_url: `{s['confirmed_anchor_url']}`",
        f"- construct_mapping: `{s['construct_mapping']}`",
        f"- construct_confirmation_status: `{s['construct_confirmation_status']}`",
        f"- identity_status: `{s['identity_status']}`",
        f"- identity_claim_allowed_now: `{s['identity_claim_allowed_now']}`",
        f"- followup_packet_artifact: `{s['followup_packet_artifact']}`",
        f"- fragment_evidence_policy: `{s['fragment_evidence_policy']}`",
        f"- state_mixing_allowed: `{s['state_mixing_allowed']}`",
        f"- phosphorylation_state_followup_required: `{s['phosphorylation_state_followup_required']}`",
        f"- followup_source_count: `{s['followup_source_count']}`",
        f"- followup_source_anchors: `{s['followup_source_anchors']}`",
        f"- current_wrong_conditions: `{', '.join(s['current_wrong_conditions'])}`",
        f"- promotion_ready: `{s['promotion_ready']}`",
        "",
        "## Packet Rows",
        "",
        "| packet_field | confirmed_value | freeze_status | next_action |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['packet_field']}` | `{row['confirmed_value']}` | `{row['freeze_status']}` | {row['next_action']} |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a citation-confirmed page4 anchor packet before phosphorylation-state follow-up.")
    parser.add_argument("--evidence-seed-json", default=DEFAULT_EVIDENCE_SEED_JSON)
    parser.add_argument("--provenance-fill-json", default=DEFAULT_PROVENANCE_FILL_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.evidence_seed_json),
        _load_json(args.provenance_fill_json),
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
