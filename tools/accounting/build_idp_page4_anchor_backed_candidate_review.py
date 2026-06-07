#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_READINESS_JSON = "runs/idp_page4_anchor_backed_candidate_readiness_current.json"
DEFAULT_PH_LOW_FILL_JSON = "runs/idp_page4_ph_low_fill_value_packet_current.json"
DEFAULT_PH_HIGH_FILL_JSON = "runs/idp_page4_ph_high_fill_value_packet_current.json"
DEFAULT_OUT_JSON = "runs/idp_page4_anchor_backed_candidate_review_current.json"
DEFAULT_OUT_CSV = "runs/idp_page4_anchor_backed_candidate_review_current.csv"
DEFAULT_OUT_MD = "runs/idp_page4_anchor_backed_candidate_review_current.md"


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
    readiness_payload: dict[str, Any],
    ph_low_fill_payload: dict[str, Any],
    ph_high_fill_payload: dict[str, Any],
) -> dict[str, Any]:
    readiness_s = dict((readiness_payload.get("summary") if isinstance(readiness_payload.get("summary"), dict) else {}) or {})
    ph_low_s = dict((ph_low_fill_payload.get("summary") if isinstance(ph_low_fill_payload.get("summary"), dict) else {}) or {})
    ph_high_s = dict((ph_high_fill_payload.get("summary") if isinstance(ph_high_fill_payload.get("summary"), dict) else {}) or {})

    rows = [
        {
            "review_item": "baseline_identity_anchor",
            "source_anchor": "PMC3077599 (2011)",
            "current_status": "frozen",
            "decision_guardrail": "keep_base_identity_separate_from_phosphorylation_state_notes",
            "review_outcome_if_accepted": "base identity remains the construct-level anchor for page4.",
        },
        {
            "review_item": "ph_low_draft_note",
            "source_anchor": str(ph_low_s.get("source_anchor", "PMID 26242913")).strip() or "PMID 26242913",
            "current_status": "draft_ready",
            "decision_guardrail": "accept_only_if_construct_matched_and_state_explicit",
            "review_outcome_if_accepted": "ph_low can be treated as a compact, low-phosphorylation-like follow-up state without changing the base anchor.",
        },
        {
            "review_item": "ph_high_draft_note",
            "source_anchor": str(ph_high_s.get("source_anchor", "PMID 28289210")).strip() or "PMID 28289210",
            "current_status": "draft_ready",
            "decision_guardrail": "accept_only_if_expanded_signal_is_not_recast_as_true_aggregation_positive",
            "review_outcome_if_accepted": "ph_high can be treated as a hyperphosphorylated expanded follow-up state without mixing into base or ph_low.",
        },
    ]

    summary = {
        "status": "page4_anchor_backed_candidate_review_packet_ready",
        "target_name": "page4",
        "construct_confirmation_status": str(readiness_s.get("construct_confirmation_status", "")).strip(),
        "draft_note_count": int(readiness_s.get("draft_followup_note_count", 0) or 0),
        "review_item_count": len(rows),
        "review_decision_ready": True,
        "anchor_backed_candidate_ready_now": False,
        "baseline_state_separation_required": True,
        "next_required_step": (
            "Review the ph_low and ph_high drafted notes together, keep baseline identity separation frozen, "
            "and only then decide whether page4 is strong enough to enter the anchor-backed candidate pool."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Page4 Anchor-Backed Candidate Review",
        "",
        f"- status: `{s['status']}`",
        f"- target_name: `{s['target_name']}`",
        f"- construct_confirmation_status: `{s['construct_confirmation_status']}`",
        f"- draft_note_count: `{s['draft_note_count']}`",
        f"- review_item_count: `{s['review_item_count']}`",
        f"- review_decision_ready: `{s['review_decision_ready']}`",
        f"- anchor_backed_candidate_ready_now: `{s['anchor_backed_candidate_ready_now']}`",
        f"- baseline_state_separation_required: `{s['baseline_state_separation_required']}`",
        "",
        "## Review Checklist",
        "",
        "| review_item | source_anchor | current_status | decision_guardrail | review_outcome_if_accepted |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['review_item']}` | `{row['source_anchor']}` | `{row['current_status']}` | `{row['decision_guardrail']}` | {row['review_outcome_if_accepted']} |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a review packet for deciding whether page4 can enter the anchor-backed candidate pool.")
    parser.add_argument("--readiness-json", default=DEFAULT_READINESS_JSON)
    parser.add_argument("--ph-low-fill-json", default=DEFAULT_PH_LOW_FILL_JSON)
    parser.add_argument("--ph-high-fill-json", default=DEFAULT_PH_HIGH_FILL_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.readiness_json),
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
