#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DECISION_JSON = "runs/idp_page4_anchor_backed_candidate_decision_current.json"
DEFAULT_CONFIRMATION_JSON = "runs/idp_page4_anchor_backed_candidate_confirmation_sheet_current.json"
DEFAULT_PH_LOW_FREEZE_JSON = "runs/idp_page4_ph_low_freeze_packet_current.json"
DEFAULT_PH_HIGH_FREEZE_JSON = "runs/idp_page4_ph_high_freeze_packet_current.json"
DEFAULT_OUT_JSON = "runs/idp_page4_anchor_backed_confirmation_recommendation_current.json"
DEFAULT_OUT_CSV = "runs/idp_page4_anchor_backed_confirmation_recommendation_current.csv"
DEFAULT_OUT_MD = "runs/idp_page4_anchor_backed_confirmation_recommendation_current.md"


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
    decision_payload: dict[str, Any],
    confirmation_payload: dict[str, Any],
    ph_low_freeze_payload: dict[str, Any],
    ph_high_freeze_payload: dict[str, Any],
) -> dict[str, Any]:
    decision_s = dict((decision_payload.get("summary") if isinstance(decision_payload.get("summary"), dict) else {}) or {})
    confirmation_s = dict((confirmation_payload.get("summary") if isinstance(confirmation_payload.get("summary"), dict) else {}) or {})
    confirmation_rows = [dict(row) for row in confirmation_payload.get("rows", []) or []]
    low_s = dict((ph_low_freeze_payload.get("summary") if isinstance(ph_low_freeze_payload.get("summary"), dict) else {}) or {})
    low_rows = [dict(row) for row in ph_low_freeze_payload.get("rows", []) or []]
    high_s = dict((ph_high_freeze_payload.get("summary") if isinstance(ph_high_freeze_payload.get("summary"), dict) else {}) or {})
    high_rows = [dict(row) for row in ph_high_freeze_payload.get("rows", []) or []]

    low_confirmation = _row_by_item(confirmation_rows, "ph_low_freeze_confirmation", "confirmation_item")
    high_confirmation = _row_by_item(confirmation_rows, "ph_high_freeze_confirmation", "confirmation_item")
    low_state_row = _row_by_item(low_rows, "ph_low_candidate_state_note", "fill_field")
    low_compact_row = _row_by_item(low_rows, "ph_low_candidate_compactness_note", "fill_field")
    high_state_row = _row_by_item(high_rows, "ph_high_candidate_state_note", "fill_field")
    high_agg_row = _row_by_item(high_rows, "ph_high_candidate_aggregation_note", "fill_field")

    rows = [
        {
            "confirmation_item": "ph_low_freeze_confirmation",
            "source_anchor": str(low_s.get("source_anchor", "PMID 26242913")).strip() or "PMID 26242913",
            "suggested_manual_confirmation_decision": str(low_confirmation.get("staged_confirmation_decision", "accept_with_guardrails")).strip() or "accept_with_guardrails",
            "guardrail_focus": "keep construct match explicit and keep the low-phosphorylation note separate from base and hyperphosphorylated interpretations",
            "supporting_freeze_fields": "ph_low_candidate_state_note ; ph_low_candidate_compactness_note",
            "supporting_guardrails": " ; ".join(
                part
                for part in [
                    str(low_state_row.get("freeze_guardrail", "")).strip(),
                    str(low_compact_row.get("freeze_guardrail", "")).strip(),
                ]
                if part
            ),
            "suggested_manual_confirmation_note": (
                "Suggested accept-with-guardrails: the low-phosphorylation follow-up is review-ready if we keep the construct match explicit "
                "and do not fold this signal back into baseline or hyperphosphorylated PAGE4 interpretations."
            ),
            "recommendation_status": "ready_for_manual_confirmation_review",
        },
        {
            "confirmation_item": "ph_high_freeze_confirmation",
            "source_anchor": str(high_s.get("source_anchor", "PMID 28289210")).strip() or "PMID 28289210",
            "suggested_manual_confirmation_decision": str(high_confirmation.get("staged_confirmation_decision", "accept_with_guardrails")).strip() or "accept_with_guardrails",
            "guardrail_focus": "keep the expanded hyperphosphorylated note explicit and do not convert it into a true aggregation-positive claim",
            "supporting_freeze_fields": "ph_high_candidate_state_note ; ph_high_candidate_aggregation_note",
            "supporting_guardrails": " ; ".join(
                part
                for part in [
                    str(high_state_row.get("freeze_guardrail", "")).strip(),
                    str(high_agg_row.get("freeze_guardrail", "")).strip(),
                ]
                if part
            ),
            "suggested_manual_confirmation_note": (
                "Suggested accept-with-guardrails: the hyperphosphorylated follow-up is review-ready if we keep the expanded-state mapping explicit "
                "and avoid recasting an expanded signal as true aggregation-positive evidence."
            ),
            "recommendation_status": "ready_for_manual_confirmation_review",
        },
    ]

    summary = {
        "status": "page4_anchor_backed_confirmation_recommendation_ready",
        "target_name": "page4",
        "decision_surface_ready": bool(decision_s),
        "confirmation_sheet_ready": bool(confirmation_s),
        "recommendation_row_count": len(rows),
        "recommended_accept_with_guardrails_count": sum(
            1 for row in rows if row["suggested_manual_confirmation_decision"] == "accept_with_guardrails"
        ),
        "manual_confirmation_required_count": int(confirmation_s.get("pending_manual_confirmation_count", len(rows)) or len(rows)),
        "anchor_backed_candidate_ready_now": False,
        "next_required_step": "Review these two suggested confirmation outcomes first, then record explicit manual confirmation in the confirmation sheet before reopening the promotion review.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Page4 Anchor-Backed Confirmation Recommendation",
        "",
        f"- status: `{s['status']}`",
        f"- target_name: `{s['target_name']}`",
        f"- decision_surface_ready: `{s['decision_surface_ready']}`",
        f"- confirmation_sheet_ready: `{s['confirmation_sheet_ready']}`",
        f"- recommendation_row_count: `{s['recommendation_row_count']}`",
        f"- recommended_accept_with_guardrails_count: `{s['recommended_accept_with_guardrails_count']}`",
        f"- manual_confirmation_required_count: `{s['manual_confirmation_required_count']}`",
        f"- anchor_backed_candidate_ready_now: `{s['anchor_backed_candidate_ready_now']}`",
        "",
        "## Recommendation Rows",
        "",
        "| confirmation_item | source_anchor | suggested_manual_confirmation_decision | recommendation_status |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['confirmation_item']}` | `{row['source_anchor']}` | `{row['suggested_manual_confirmation_decision']}` | `{row['recommendation_status']}` |"
        )
        lines.append("")
        lines.append(f"- Guardrail focus: {row['guardrail_focus']}")
        lines.append(f"- Supporting freeze fields: `{row['supporting_freeze_fields']}`")
        lines.append(f"- Supporting guardrails: `{row['supporting_guardrails']}`")
        lines.append(f"- Suggested note: {row['suggested_manual_confirmation_note']}")
        lines.append("")
    lines.extend(["## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the page4 anchor-backed confirmation recommendation surface.")
    parser.add_argument("--decision-json", default=DEFAULT_DECISION_JSON)
    parser.add_argument("--confirmation-json", default=DEFAULT_CONFIRMATION_JSON)
    parser.add_argument("--ph-low-freeze-json", default=DEFAULT_PH_LOW_FREEZE_JSON)
    parser.add_argument("--ph-high-freeze-json", default=DEFAULT_PH_HIGH_FREEZE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.decision_json),
        _load_json(args.confirmation_json),
        _load_json(args.ph_low_freeze_json),
        _load_json(args.ph_high_freeze_json),
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
