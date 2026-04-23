#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DECISION_JSON = "runs/idp_page4_anchor_backed_candidate_decision_current.json"
DEFAULT_CONFIRMATION_JSON = "runs/idp_page4_anchor_backed_candidate_confirmation_sheet_current.json"
DEFAULT_RECOMMENDATION_JSON = "runs/idp_page4_anchor_backed_confirmation_recommendation_current.json"
DEFAULT_OUT_JSON = "runs/idp_page4_anchor_backed_promotion_review_current.json"
DEFAULT_OUT_CSV = "runs/idp_page4_anchor_backed_promotion_review_current.csv"
DEFAULT_OUT_MD = "runs/idp_page4_anchor_backed_promotion_review_current.md"


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
    decision_payload: dict[str, Any],
    confirmation_payload: dict[str, Any],
    recommendation_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    decision_s = dict((decision_payload.get("summary") if isinstance(decision_payload.get("summary"), dict) else {}) or {})
    confirmation_s = dict((confirmation_payload.get("summary") if isinstance(confirmation_payload.get("summary"), dict) else {}) or {})
    recommendation_s = dict((((recommendation_payload or {}).get("summary", {}) if isinstance((recommendation_payload or {}).get("summary", {}), dict) else {}) or {}))
    recommendation_rows = [dict(row) for row in (recommendation_payload or {}).get("rows", []) or []]
    recommendation_by_item = {
        str(row.get("confirmation_item", "")).strip(): row
        for row in recommendation_rows
        if str(row.get("confirmation_item", "")).strip()
    }
    confirmation_rows = [dict(row) for row in confirmation_payload.get("rows", []) or []]
    confirmation_by_item = {
        str(row.get("confirmation_item", "")).strip(): row
        for row in confirmation_rows
        if str(row.get("confirmation_item", "")).strip()
    }
    ph_low_confirmed = str(confirmation_by_item.get("ph_low_freeze_confirmation", {}).get("manual_confirmation_decision", "")).strip() == "accept_with_guardrails"
    ph_high_confirmed = str(confirmation_by_item.get("ph_high_freeze_confirmation", {}).get("manual_confirmation_decision", "")).strip() == "accept_with_guardrails"
    candidate_ready_now = ph_low_confirmed and ph_high_confirmed

    rows = [
        {
            "promotion_item": "baseline_identity_anchor",
            "current_state": "frozen",
            "recommended_manual_confirmation": "",
            "promotion_effect_if_accepted": "keeps base PAGE4 identity stable while allowing state-specific follow-up notes.",
            "blocking_rule": "must_remain_frozen",
        },
        {
            "promotion_item": "ph_low_confirmation",
            "current_state": "accepted_with_guardrails" if ph_low_confirmed else "pending_manual_confirmation",
            "recommended_manual_confirmation": str(
                recommendation_by_item.get("ph_low_freeze_confirmation", {}).get("suggested_manual_confirmation_decision", "")
            ).strip(),
            "promotion_effect_if_accepted": "allows ph_low compact/low-phosphorylation-like follow-up note to support candidate review.",
            "blocking_rule": "manual_confirmation_required",
        },
        {
            "promotion_item": "ph_high_confirmation",
            "current_state": "accepted_with_guardrails" if ph_high_confirmed else "pending_manual_confirmation",
            "recommended_manual_confirmation": str(
                recommendation_by_item.get("ph_high_freeze_confirmation", {}).get("suggested_manual_confirmation_decision", "")
            ).strip(),
            "promotion_effect_if_accepted": "allows ph_high expanded/hyperphosphorylated follow-up note to support candidate review.",
            "blocking_rule": "manual_confirmation_required",
        },
    ]

    summary = {
        "status": "page4_anchor_backed_promotion_review_ready_for_candidate_promotion" if candidate_ready_now else "page4_anchor_backed_promotion_review_pending_manual_confirmation",
        "target_name": "page4",
        "decision_surface_ready": bool(decision_s),
        "confirmation_sheet_ready": bool(confirmation_s),
        "recommendation_ready": bool(recommendation_s),
        "recommendation_artifact": (
            "runs/idp_page4_anchor_backed_confirmation_recommendation_current.md" if recommendation_s else ""
        ),
        "recommended_accept_with_guardrails_count": int(
            recommendation_s.get("recommended_accept_with_guardrails_count", 0) or 0
        ),
        "pending_manual_confirmation_count": int(confirmation_s.get("pending_manual_confirmation_count", 0) or 0),
        "promotion_review_ready": True,
        "anchor_backed_candidate_ready_now": candidate_ready_now,
        "broader_rerun_ready": False,
        "next_required_step": (
            "Treat page4 as candidate-ready with guardrails for review surfaces, keep broader_full_idp_promotion blocked, and move the next improvement to quantitative anchor replacement before any true broader rerun."
            if candidate_ready_now
            else
            "Review the confirmation recommendation first, then use the confirmation sheet to resolve ph_low and ph_high together; only if both are manually accepted should page4 be reconsidered for anchor-backed candidate promotion."
            if recommendation_s
            else "Use the confirmation sheet to resolve ph_low and ph_high together; only if both are manually accepted should page4 be reconsidered for anchor-backed candidate promotion."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Page4 Anchor-Backed Promotion Review",
        "",
        f"- status: `{s['status']}`",
        f"- target_name: `{s['target_name']}`",
        f"- decision_surface_ready: `{s['decision_surface_ready']}`",
        f"- confirmation_sheet_ready: `{s['confirmation_sheet_ready']}`",
        f"- recommendation_ready: `{s['recommendation_ready']}`",
        f"- recommendation_artifact: `{s['recommendation_artifact']}`",
        f"- recommended_accept_with_guardrails_count: `{s['recommended_accept_with_guardrails_count']}`",
        f"- pending_manual_confirmation_count: `{s['pending_manual_confirmation_count']}`",
        f"- promotion_review_ready: `{s['promotion_review_ready']}`",
        f"- anchor_backed_candidate_ready_now: `{s['anchor_backed_candidate_ready_now']}`",
        f"- broader_rerun_ready: `{s['broader_rerun_ready']}`",
        "",
        "## Promotion Review Items",
        "",
        "| promotion_item | current_state | recommended_manual_confirmation | promotion_effect_if_accepted | blocking_rule |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['promotion_item']}` | `{row['current_state']}` | `{row.get('recommended_manual_confirmation', '')}` | {row['promotion_effect_if_accepted']} | `{row['blocking_rule']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the page4 anchor-backed promotion review surface.")
    parser.add_argument("--decision-json", default=DEFAULT_DECISION_JSON)
    parser.add_argument("--confirmation-json", default=DEFAULT_CONFIRMATION_JSON)
    parser.add_argument("--recommendation-json", default=DEFAULT_RECOMMENDATION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.decision_json),
        _load_json(args.confirmation_json),
        _load_json(args.recommendation_json),
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
