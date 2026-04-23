#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_RECOMMENDATION_JSON = "runs/idp_page4_anchor_backed_confirmation_recommendation_current.json"
DEFAULT_CONFIRMATION_JSON = "runs/idp_page4_anchor_backed_candidate_confirmation_sheet_current.json"
DEFAULT_PROMOTION_REVIEW_JSON = "runs/idp_page4_anchor_backed_promotion_review_current.json"
DEFAULT_OUT_JSON = "runs/idp_page4_manual_confirmation_workbench_current.json"
DEFAULT_OUT_CSV = "runs/idp_page4_manual_confirmation_workbench_current.csv"
DEFAULT_OUT_MD = "runs/idp_page4_manual_confirmation_workbench_current.md"


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


def _row_by_item(rows: list[dict[str, Any]], key: str, field: str) -> dict[str, Any]:
    for row in rows:
        if str(row.get(field, "")).strip() == key:
            return dict(row)
    return {}


def build_payload(
    recommendation_payload: dict[str, Any],
    confirmation_payload: dict[str, Any],
    promotion_review_payload: dict[str, Any],
) -> dict[str, Any]:
    recommendation_s = dict((recommendation_payload.get("summary") if isinstance(recommendation_payload.get("summary"), dict) else {}) or {})
    recommendation_rows = [dict(row) for row in recommendation_payload.get("rows", []) or []]
    confirmation_s = dict((confirmation_payload.get("summary") if isinstance(confirmation_payload.get("summary"), dict) else {}) or {})
    confirmation_rows = [dict(row) for row in confirmation_payload.get("rows", []) or []]
    promotion_s = dict((promotion_review_payload.get("summary") if isinstance(promotion_review_payload.get("summary"), dict) else {}) or {})
    promotion_rows = [dict(row) for row in promotion_review_payload.get("rows", []) or []]

    low_reco = _row_by_item(recommendation_rows, "ph_low_freeze_confirmation", "confirmation_item")
    high_reco = _row_by_item(recommendation_rows, "ph_high_freeze_confirmation", "confirmation_item")
    low_confirm = _row_by_item(confirmation_rows, "ph_low_freeze_confirmation", "confirmation_item")
    high_confirm = _row_by_item(confirmation_rows, "ph_high_freeze_confirmation", "confirmation_item")
    low_promo = _row_by_item(promotion_rows, "ph_low_confirmation", "promotion_item")
    high_promo = _row_by_item(promotion_rows, "ph_high_confirmation", "promotion_item")

    rows = [
        {
            "review_rank": 1,
            "confirmation_item": "ph_low_freeze_confirmation",
            "source_anchor": str(low_reco.get("source_anchor", low_confirm.get("source_anchor", "PMID 26242913"))).strip() or "PMID 26242913",
            "suggested_manual_confirmation_decision": str(low_reco.get("suggested_manual_confirmation_decision", low_confirm.get("staged_confirmation_decision", "accept_with_guardrails"))).strip() or "accept_with_guardrails",
            "guardrail_focus": str(low_reco.get("guardrail_focus", "")).strip(),
            "supporting_guardrails": str(low_reco.get("supporting_guardrails", "")).strip(),
            "staged_confirmation_note": str(low_confirm.get("staged_confirmation_note", "")).strip(),
            "manual_confirmation_decision": str(low_confirm.get("manual_confirmation_decision", "")).strip(),
            "manual_confirmation_note": str(low_confirm.get("manual_confirmation_note", "")).strip(),
            "reopen_effect_if_accepted": str(low_promo.get("promotion_effect_if_accepted", "")).strip(),
            "review_status": str(low_confirm.get("confirmation_status", "ready_for_manual_confirmation")).strip() or "ready_for_manual_confirmation",
        },
        {
            "review_rank": 2,
            "confirmation_item": "ph_high_freeze_confirmation",
            "source_anchor": str(high_reco.get("source_anchor", high_confirm.get("source_anchor", "PMID 28289210"))).strip() or "PMID 28289210",
            "suggested_manual_confirmation_decision": str(high_reco.get("suggested_manual_confirmation_decision", high_confirm.get("staged_confirmation_decision", "accept_with_guardrails"))).strip() or "accept_with_guardrails",
            "guardrail_focus": str(high_reco.get("guardrail_focus", "")).strip(),
            "supporting_guardrails": str(high_reco.get("supporting_guardrails", "")).strip(),
            "staged_confirmation_note": str(high_confirm.get("staged_confirmation_note", "")).strip(),
            "manual_confirmation_decision": str(high_confirm.get("manual_confirmation_decision", "")).strip(),
            "manual_confirmation_note": str(high_confirm.get("manual_confirmation_note", "")).strip(),
            "reopen_effect_if_accepted": str(high_promo.get("promotion_effect_if_accepted", "")).strip(),
            "review_status": str(high_confirm.get("confirmation_status", "ready_for_manual_confirmation")).strip() or "ready_for_manual_confirmation",
        },
    ]

    pending_count = sum(1 for row in rows if not row["manual_confirmation_decision"])
    confirmed_count = sum(1 for row in rows if row["manual_confirmation_decision"] == "accept_with_guardrails")
    candidate_ready_now = bool(promotion_s.get("anchor_backed_candidate_ready_now", False)) or (
        pending_count == 0 and confirmed_count == 2
    )

    summary = {
        "status": (
            "page4_manual_confirmation_workbench_resolved"
            if candidate_ready_now
            else "page4_manual_confirmation_workbench_ready"
        ),
        "target_name": "page4",
        "recommendation_ready": bool(recommendation_s),
        "confirmation_sheet_ready": bool(confirmation_s),
        "promotion_review_ready": bool(promotion_s),
        "review_row_count": len(rows),
        "pending_manual_confirmation_count": pending_count,
        "ready_for_manual_confirmation_count": sum(1 for row in rows if row["review_status"] == "ready_for_manual_confirmation"),
        "confirmed_accept_with_guardrails_count": confirmed_count,
        "anchor_backed_candidate_ready_now": candidate_ready_now,
        "next_required_step": (
            "The ph_low and ph_high confirmations are explicit. Use the page4 quantitative anchor replacement packet next, keep broader promotion blocked, and do not count page4 as an additional anchor-backed target until the provisional anchor ranges are replaced."
            if candidate_ready_now
            else "Use this workbench as the single page4 reviewer surface: compare the recommendation, enter the two manual confirmations explicitly, then reopen promotion review."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Page4 Manual Confirmation Workbench",
        "",
        f"- status: `{s['status']}`",
        f"- target_name: `{s['target_name']}`",
        f"- recommendation_ready: `{s['recommendation_ready']}`",
        f"- confirmation_sheet_ready: `{s['confirmation_sheet_ready']}`",
        f"- promotion_review_ready: `{s['promotion_review_ready']}`",
        f"- review_row_count: `{s['review_row_count']}`",
        f"- pending_manual_confirmation_count: `{s['pending_manual_confirmation_count']}`",
        f"- ready_for_manual_confirmation_count: `{s['ready_for_manual_confirmation_count']}`",
        f"- confirmed_accept_with_guardrails_count: `{s['confirmed_accept_with_guardrails_count']}`",
        f"- anchor_backed_candidate_ready_now: `{s['anchor_backed_candidate_ready_now']}`",
        "",
        "## Review Rows",
        "",
        "| review_rank | confirmation_item | source_anchor | suggested_manual_confirmation_decision | review_status |",
        "| ---: | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['review_rank']} | `{row['confirmation_item']}` | `{row['source_anchor']}` | `{row['suggested_manual_confirmation_decision']}` | `{row['review_status']}` |"
        )
        lines.append("")
        lines.append(f"- Guardrail focus: {row['guardrail_focus']}")
        lines.append(f"- Supporting guardrails: `{row['supporting_guardrails']}`")
        lines.append(f"- Staged confirmation note: {row['staged_confirmation_note']}")
        lines.append(f"- Reopen effect if accepted: {row['reopen_effect_if_accepted']}")
        lines.append("")
    lines.extend(["## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the page4 manual confirmation workbench.")
    parser.add_argument("--recommendation-json", default=DEFAULT_RECOMMENDATION_JSON)
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
