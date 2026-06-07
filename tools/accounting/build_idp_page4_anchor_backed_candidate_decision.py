#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_REVIEW_JSON = "runs/idp_page4_anchor_backed_candidate_review_current.json"
DEFAULT_PH_LOW_FREEZE_JSON = "runs/idp_page4_ph_low_freeze_packet_current.json"
DEFAULT_PH_HIGH_FREEZE_JSON = "runs/idp_page4_ph_high_freeze_packet_current.json"
DEFAULT_CONFIRMATION_JSON = "runs/idp_page4_anchor_backed_candidate_confirmation_sheet_current.json"
DEFAULT_OUT_JSON = "runs/idp_page4_anchor_backed_candidate_decision_current.json"
DEFAULT_OUT_CSV = "runs/idp_page4_anchor_backed_candidate_decision_current.csv"
DEFAULT_OUT_MD = "runs/idp_page4_anchor_backed_candidate_decision_current.md"


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
    review_payload: dict[str, Any],
    ph_low_freeze_payload: dict[str, Any],
    ph_high_freeze_payload: dict[str, Any],
    confirmation_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    review_s = dict((review_payload.get("summary") if isinstance(review_payload.get("summary"), dict) else {}) or {})
    low_s = dict((ph_low_freeze_payload.get("summary") if isinstance(ph_low_freeze_payload.get("summary"), dict) else {}) or {})
    high_s = dict((ph_high_freeze_payload.get("summary") if isinstance(ph_high_freeze_payload.get("summary"), dict) else {}) or {})
    confirmation_s = dict((((confirmation_payload or {}).get("summary")) if isinstance((confirmation_payload or {}).get("summary"), dict) else {}) or {})
    confirmed_accept_count = int(confirmation_s.get("confirmed_accept_with_guardrails_count", 0) or 0)
    pending_count = int(confirmation_s.get("pending_manual_confirmation_count", 2) or 0)

    rows = [
        {
            "decision_item": "baseline_identity_anchor",
            "current_status": "frozen",
            "decision_state": "keep_frozen",
            "source_anchor": "PMC3077599 (2011)",
            "next_action": "Do not relax the base identity anchor while deciding the phosphorylation-state notes.",
        },
        {
            "decision_item": "ph_low_freeze_packet",
            "current_status": "review_ready",
            "decision_state": "pending_manual_confirmation",
            "source_anchor": str(low_s.get("source_anchor", "PMID 26242913")).strip() or "PMID 26242913",
            "next_action": "Manually confirm or reject the ph_low freeze packet under its construct-match and state-explicit guardrails.",
        },
        {
            "decision_item": "ph_high_freeze_packet",
            "current_status": "review_ready",
            "decision_state": "pending_manual_confirmation",
            "source_anchor": str(high_s.get("source_anchor", "PMID 28289210")).strip() or "PMID 28289210",
            "next_action": "Manually confirm or reject the ph_high freeze packet under its expanded-state and non-aggregation-overcall guardrails.",
        },
    ]

    summary = {
        "status": (
            "page4_anchor_backed_candidate_decision_confirmed_accept_with_guardrails"
            if pending_count == 0 and confirmed_accept_count == 2
            else "page4_anchor_backed_candidate_decision_pending_manual_confirmation"
        ),
        "target_name": "page4",
        "review_packet_ready": bool(review_s),
        "ph_low_freeze_ready": bool(low_s),
        "ph_high_freeze_ready": bool(high_s),
        "confirmation_sheet_ready": bool(confirmation_s),
        "decision_item_count": len(rows),
        "manual_confirmation_required_count": pending_count,
        "confirmed_accept_with_guardrails_count": confirmed_accept_count,
        "anchor_backed_candidate_ready_now": pending_count == 0 and confirmed_accept_count == 2,
        "promotion_ready": pending_count == 0 and confirmed_accept_count == 2,
        "next_required_step": (
            "The ph_low and ph_high confirmations are now explicit. Reopen promotion review and treat page4 as candidate-ready with guardrails, but do not count it as a broader anchor-backed target until quantitative anchor replacement is defined."
            if pending_count == 0 and confirmed_accept_count == 2
            else "Manually confirm the ph_low and ph_high freeze decisions together; only if both are accepted should page4 be reconsidered for the anchor-backed candidate pool."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Page4 Anchor-Backed Candidate Decision",
        "",
        f"- status: `{s['status']}`",
        f"- target_name: `{s['target_name']}`",
        f"- review_packet_ready: `{s['review_packet_ready']}`",
        f"- ph_low_freeze_ready: `{s['ph_low_freeze_ready']}`",
        f"- ph_high_freeze_ready: `{s['ph_high_freeze_ready']}`",
        f"- confirmation_sheet_ready: `{s['confirmation_sheet_ready']}`",
        f"- decision_item_count: `{s['decision_item_count']}`",
        f"- manual_confirmation_required_count: `{s['manual_confirmation_required_count']}`",
        f"- confirmed_accept_with_guardrails_count: `{s['confirmed_accept_with_guardrails_count']}`",
        f"- anchor_backed_candidate_ready_now: `{s['anchor_backed_candidate_ready_now']}`",
        f"- promotion_ready: `{s['promotion_ready']}`",
        "",
        "## Decision Checklist",
        "",
        "| decision_item | current_status | decision_state | source_anchor | next_action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['decision_item']}` | `{row['current_status']}` | `{row['decision_state']}` | `{row['source_anchor']}` | {row['next_action']} |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the page4 anchor-backed candidate decision surface.")
    parser.add_argument("--review-json", default=DEFAULT_REVIEW_JSON)
    parser.add_argument("--ph-low-freeze-json", default=DEFAULT_PH_LOW_FREEZE_JSON)
    parser.add_argument("--ph-high-freeze-json", default=DEFAULT_PH_HIGH_FREEZE_JSON)
    parser.add_argument("--confirmation-json", default=DEFAULT_CONFIRMATION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.review_json),
        _load_json(args.ph_low_freeze_json),
        _load_json(args.ph_high_freeze_json),
        _load_json(args.confirmation_json),
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
