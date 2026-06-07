#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CITATION_CONFIRMED_JSON = "runs/idp_page4_anchor_citation_confirmed_packet_current.json"
DEFAULT_FILL_DRAFT_JSON = "runs/idp_page4_phosphorylation_fill_draft_current.json"
DEFAULT_CURATION_PACKET_JSON = "runs/idp_page4_anchor_curation_packet_current.json"
DEFAULT_PH_LOW_FILL_JSON = "runs/idp_page4_ph_low_fill_value_packet_current.json"
DEFAULT_PH_HIGH_FILL_JSON = "runs/idp_page4_ph_high_fill_value_packet_current.json"
DEFAULT_OUT_JSON = "runs/idp_page4_anchor_backed_candidate_readiness_current.json"
DEFAULT_OUT_CSV = "runs/idp_page4_anchor_backed_candidate_readiness_current.csv"
DEFAULT_OUT_MD = "runs/idp_page4_anchor_backed_candidate_readiness_current.md"


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
    citation_confirmed_payload: dict[str, Any],
    fill_draft_payload: dict[str, Any],
    curation_packet_payload: dict[str, Any],
    ph_low_fill_payload: dict[str, Any] | None = None,
    ph_high_fill_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    citation_s = dict((citation_confirmed_payload.get("summary") if isinstance(citation_confirmed_payload.get("summary"), dict) else {}) or {})
    fill_s = dict((fill_draft_payload.get("summary") if isinstance(fill_draft_payload.get("summary"), dict) else {}) or {})
    curation_s = dict((curation_packet_payload.get("summary") if isinstance(curation_packet_payload.get("summary"), dict) else {}) or {})
    ph_low_s = dict((((ph_low_fill_payload or {}).get("summary")) if isinstance((ph_low_fill_payload or {}).get("summary"), dict) else {}) or {})
    ph_high_s = dict((((ph_high_fill_payload or {}).get("summary")) if isinstance((ph_high_fill_payload or {}).get("summary"), dict) else {}) or {})
    fill_values_ready = bool(ph_low_s) and bool(ph_high_s)

    rows = [
        {
            "readiness_item": "construct_citation_confirmed",
            "current_status": "ready",
            "blocking_reason": "",
            "evidence_anchor": str(citation_s.get("confirmed_anchor_citation", "")).strip(),
            "next_action": "Keep the construct-level citation frozen as the baseline identity anchor.",
        },
        {
            "readiness_item": "ph_low_state_note_frozen",
            "current_status": "draft_ready" if ph_low_s else "pending",
            "blocking_reason": "" if ph_low_s else "draft_only_followup_note",
            "evidence_anchor": "PMID 26242913",
            "next_action": "Review the ph_low draft note and freeze it only if the state-specific mapping remains explicit and construct-matched.",
        },
        {
            "readiness_item": "ph_high_state_note_frozen",
            "current_status": "draft_ready" if ph_high_s else "pending",
            "blocking_reason": "" if ph_high_s else "draft_only_followup_note",
            "evidence_anchor": "PMID 28289210",
            "next_action": "Review the ph_high draft note and freeze it only if the state-specific mapping remains explicit and construct-matched.",
        },
        {
            "readiness_item": "baseline_state_separation",
            "current_status": "ready",
            "blocking_reason": "",
            "evidence_anchor": "PMC3077599 (2011)",
            "next_action": "Keep base identity separate from any phosphorylation-state interpretation.",
        },
        {
            "readiness_item": "nonfocus_wrong_conditions",
            "current_status": "defer",
            "blocking_reason": "hydro_high_and_salt_high_not_in_first_slice",
            "evidence_anchor": "defer_for_now",
            "next_action": "Do not require hydro_high or salt_high closure before the first anchor-backed candidate review.",
        },
    ]

    summary = {
        "status": "page4_anchor_backed_candidate_review_ready" if fill_values_ready else "page4_anchor_backed_candidate_readiness_pending_fill",
        "target_name": "page4",
        "construct_confirmation_status": str(citation_s.get("construct_confirmation_status", "")).strip(),
        "followup_fill_draft_ready": bool(fill_s),
        "fill_value_packets_ready": fill_values_ready,
        "required_followup_note_count": 2,
        "pending_followup_note_count": 0 if fill_values_ready else 2,
        "draft_followup_note_count": 2 if fill_values_ready else 0,
        "deferred_nonfocus_condition_count": len(str(fill_s.get("focus_conditions", "")).split(" ; ")) if fill_s else 0,
        "current_wrong_conditions": ", ".join(list(curation_s.get("current_wrong_conditions", []) or [])),
        "anchor_backed_candidate_ready_now": False,
        "next_required_step": (
            "Review the drafted ph_low and ph_high follow-up notes, keep baseline identity separation intact, and only then decide whether page4 is strong enough to become an anchor-backed candidate."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Page4 Anchor-Backed Candidate Readiness",
        "",
        f"- status: `{s['status']}`",
        f"- target_name: `{s['target_name']}`",
        f"- construct_confirmation_status: `{s['construct_confirmation_status']}`",
        f"- followup_fill_draft_ready: `{s['followup_fill_draft_ready']}`",
        f"- fill_value_packets_ready: `{s['fill_value_packets_ready']}`",
        f"- required_followup_note_count: `{s['required_followup_note_count']}`",
        f"- pending_followup_note_count: `{s['pending_followup_note_count']}`",
        f"- draft_followup_note_count: `{s['draft_followup_note_count']}`",
        f"- deferred_nonfocus_condition_count: `{s['deferred_nonfocus_condition_count']}`",
        f"- current_wrong_conditions: `{s['current_wrong_conditions']}`",
        f"- anchor_backed_candidate_ready_now: `{s['anchor_backed_candidate_ready_now']}`",
        "",
        "## Readiness Checklist",
        "",
        "| readiness_item | current_status | blocking_reason | evidence_anchor | next_action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['readiness_item']}` | `{row['current_status']}` | `{row['blocking_reason']}` | `{row['evidence_anchor']}` | {row['next_action']} |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a page4 anchor-backed candidate readiness review packet.")
    parser.add_argument("--citation-confirmed-json", default=DEFAULT_CITATION_CONFIRMED_JSON)
    parser.add_argument("--fill-draft-json", default=DEFAULT_FILL_DRAFT_JSON)
    parser.add_argument("--curation-packet-json", default=DEFAULT_CURATION_PACKET_JSON)
    parser.add_argument("--ph-low-fill-json", default=DEFAULT_PH_LOW_FILL_JSON)
    parser.add_argument("--ph-high-fill-json", default=DEFAULT_PH_HIGH_FILL_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.citation_confirmed_json),
        _load_json(args.fill_draft_json),
        _load_json(args.curation_packet_json),
        _load_json(args.ph_low_fill_json),
        _load_json(args.ph_high_fill_json),
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
