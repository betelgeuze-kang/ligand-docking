#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_RECOMMENDATION_JSON = "runs/idp_page4_anchor_backed_confirmation_recommendation_current.json"
DEFAULT_WORKBENCH_JSON = "runs/idp_page4_manual_confirmation_workbench_current.json"
DEFAULT_NOTE_TEMPLATES_JSON = "runs/idp_page4_manual_confirmation_note_templates_current.json"
DEFAULT_CONFIRMATION_JSON = "runs/idp_page4_anchor_backed_candidate_confirmation_sheet_current.json"
DEFAULT_PROMOTION_REVIEW_JSON = "runs/idp_page4_anchor_backed_promotion_review_current.json"
DEFAULT_OUT_JSON = "runs/idp_page4_manual_confirmation_launch_packet_current.json"
DEFAULT_OUT_CSV = "runs/idp_page4_manual_confirmation_launch_packet_current.csv"
DEFAULT_OUT_MD = "runs/idp_page4_manual_confirmation_launch_packet_current.md"


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
    recommendation_payload: dict[str, Any],
    workbench_payload: dict[str, Any],
    note_templates_payload: dict[str, Any],
    confirmation_payload: dict[str, Any],
    promotion_review_payload: dict[str, Any],
) -> dict[str, Any]:
    recommendation_s = dict((recommendation_payload.get("summary") if isinstance(recommendation_payload.get("summary"), dict) else {}) or {})
    workbench_s = dict((workbench_payload.get("summary") if isinstance(workbench_payload.get("summary"), dict) else {}) or {})
    note_templates_s = dict((note_templates_payload.get("summary") if isinstance(note_templates_payload.get("summary"), dict) else {}) or {})
    confirmation_s = dict((confirmation_payload.get("summary") if isinstance(confirmation_payload.get("summary"), dict) else {}) or {})
    promotion_review_s = dict((promotion_review_payload.get("summary") if isinstance(promotion_review_payload.get("summary"), dict) else {}) or {})

    rows = [
        {
            "step_rank": 1,
            "step_id": "open_manual_confirmation_workbench",
            "artifact": "runs/idp_page4_manual_confirmation_workbench_current.md",
            "status": "ready_now" if workbench_s else "missing",
            "why_this_step_exists": "Use one reviewer-facing workbench that combines recommendation, staged confirmation, and promotion effect before writing anything manual.",
        },
        {
            "step_rank": 2,
            "step_id": "review_confirmation_recommendation",
            "artifact": "runs/idp_page4_anchor_backed_confirmation_recommendation_current.md",
            "status": "ready_now" if recommendation_s else "missing",
            "why_this_step_exists": "See the suggested accept-with-guardrails outcome and the exact freeze-field guardrails before writing any manual confirmation.",
        },
        {
            "step_rank": 3,
            "step_id": "review_note_templates",
            "artifact": "runs/idp_page4_manual_confirmation_note_templates_current.md",
            "status": "ready_now" if note_templates_s else "missing",
            "why_this_step_exists": "Use reviewer-facing note templates as a starting point without auto-filling the actual manual confirmation fields.",
        },
        {
            "step_rank": 4,
            "step_id": "fill_manual_confirmation_sheet",
            "artifact": "runs/idp_page4_anchor_backed_candidate_confirmation_sheet_current.md",
            "status": "ready_now" if confirmation_s else "missing",
            "why_this_step_exists": "Record the actual ph_low and ph_high manual confirmation decisions explicitly without auto-promoting anything.",
        },
        {
            "step_rank": 5,
            "step_id": "reopen_promotion_review",
            "artifact": "runs/idp_page4_anchor_backed_promotion_review_current.md",
            "status": (
                "ready_now"
                if bool(promotion_review_s) and bool(promotion_review_s.get("anchor_backed_candidate_ready_now", False))
                else "ready_after_manual_confirmation"
                if promotion_review_s
                else "missing"
            ),
            "why_this_step_exists": "Re-check whether page4 can be reconsidered for anchor-backed candidate promotion only after both manual confirmations are explicit.",
        },
    ]

    pending_count = int(confirmation_s.get("pending_manual_confirmation_count", 0) or 0)
    candidate_ready_now = bool(promotion_review_s.get("anchor_backed_candidate_ready_now", False))

    summary = {
        "status": (
            "page4_manual_confirmation_launch_packet_resolved"
            if pending_count == 0 and candidate_ready_now
            else "page4_manual_confirmation_launch_packet_ready"
        ),
        "target_name": "page4",
        "recommendation_ready": bool(recommendation_s),
        "workbench_ready": bool(workbench_s),
        "note_templates_ready": bool(note_templates_s),
        "confirmation_sheet_ready": bool(confirmation_s),
        "promotion_review_ready": bool(promotion_review_s),
        "step_count": len(rows),
        "pending_manual_confirmation_count": pending_count,
        "confirmed_accept_with_guardrails_count": int(confirmation_s.get("confirmed_accept_with_guardrails_count", 0) or 0),
        "anchor_backed_candidate_ready_now": candidate_ready_now,
        "broader_rerun_ready": False,
        "next_required_step": (
            "The ph_low and ph_high confirmations are explicit. Reopen the promotion review only to confirm the guardrailed candidate state, then move directly to page4 quantitative anchor replacement while keeping broader promotion blocked."
            if pending_count == 0 and candidate_ready_now
            else "Open the workbench first, use the recommendation and note templates as support, fill the two manual confirmation fields explicitly, and only then reopen the promotion review."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Page4 Manual Confirmation Launch Packet",
        "",
        f"- status: `{s['status']}`",
        f"- target_name: `{s['target_name']}`",
        f"- recommendation_ready: `{s['recommendation_ready']}`",
        f"- workbench_ready: `{s['workbench_ready']}`",
        f"- note_templates_ready: `{s['note_templates_ready']}`",
        f"- confirmation_sheet_ready: `{s['confirmation_sheet_ready']}`",
        f"- promotion_review_ready: `{s['promotion_review_ready']}`",
        f"- step_count: `{s['step_count']}`",
        f"- pending_manual_confirmation_count: `{s['pending_manual_confirmation_count']}`",
        f"- confirmed_accept_with_guardrails_count: `{s['confirmed_accept_with_guardrails_count']}`",
        f"- anchor_backed_candidate_ready_now: `{s['anchor_backed_candidate_ready_now']}`",
        f"- broader_rerun_ready: `{s['broader_rerun_ready']}`",
        "",
        "## Ordered Steps",
        "",
        "| step_rank | step_id | artifact | status |",
        "| ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['step_rank']} | `{row['step_id']}` | `{row['artifact']}` | `{row['status']}` |"
        )
        lines.append("")
        lines.append(f"- Why: {row['why_this_step_exists']}")
        lines.append("")
    lines.extend(["## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the page4 manual-confirmation launch packet.")
    parser.add_argument("--recommendation-json", default=DEFAULT_RECOMMENDATION_JSON)
    parser.add_argument("--workbench-json", default=DEFAULT_WORKBENCH_JSON)
    parser.add_argument("--note-templates-json", default=DEFAULT_NOTE_TEMPLATES_JSON)
    parser.add_argument("--confirmation-json", default=DEFAULT_CONFIRMATION_JSON)
    parser.add_argument("--promotion-review-json", default=DEFAULT_PROMOTION_REVIEW_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.recommendation_json),
        _load_json(args.workbench_json),
        _load_json(args.note_templates_json),
        _load_json(args.confirmation_json),
        _load_json(args.promotion_review_json),
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
