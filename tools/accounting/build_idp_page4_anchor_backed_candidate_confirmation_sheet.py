#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DECISION_JSON = "runs/idp_page4_anchor_backed_candidate_decision_current.json"
DEFAULT_PH_LOW_FREEZE_JSON = "runs/idp_page4_ph_low_freeze_packet_current.json"
DEFAULT_PH_HIGH_FREEZE_JSON = "runs/idp_page4_ph_high_freeze_packet_current.json"
DEFAULT_RESOLUTION_JSON = "runs/idp_page4_manual_confirmation_resolution_current.json"
DEFAULT_OUT_JSON = "runs/idp_page4_anchor_backed_candidate_confirmation_sheet_current.json"
DEFAULT_OUT_CSV = "runs/idp_page4_anchor_backed_candidate_confirmation_sheet_current.csv"
DEFAULT_OUT_MD = "runs/idp_page4_anchor_backed_candidate_confirmation_sheet_current.md"


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
    ph_low_freeze_payload: dict[str, Any],
    ph_high_freeze_payload: dict[str, Any],
    resolution_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    decision_s = dict((decision_payload.get("summary") if isinstance(decision_payload.get("summary"), dict) else {}) or {})
    low_s = dict((ph_low_freeze_payload.get("summary") if isinstance(ph_low_freeze_payload.get("summary"), dict) else {}) or {})
    high_s = dict((ph_high_freeze_payload.get("summary") if isinstance(ph_high_freeze_payload.get("summary"), dict) else {}) or {})
    resolution_s = dict((((resolution_payload or {}).get("summary")) if isinstance((resolution_payload or {}).get("summary"), dict) else {}) or {})
    resolution_rows = {
        str(row.get("confirmation_item", "")).strip(): dict(row)
        for row in (resolution_payload or {}).get("rows", []) or []
        if str(row.get("confirmation_item", "")).strip()
    }

    rows = [
        {
            "confirmation_item": "ph_low_freeze_confirmation",
            "source_anchor": str(low_s.get("source_anchor", "PMID 26242913")).strip() or "PMID 26242913",
            "staged_confirmation_decision": "accept_with_guardrails",
            "staged_confirmation_note": "Accept only if the construct match stays explicit and the low-phosphorylation state is not mixed into base or hyperphosphorylated interpretations.",
            "manual_confirmation_decision": str(resolution_rows.get("ph_low_freeze_confirmation", {}).get("manual_confirmation_decision", "")).strip(),
            "manual_confirmation_note": str(resolution_rows.get("ph_low_freeze_confirmation", {}).get("manual_confirmation_note", "")).strip(),
            "manual_confirmation_actor": str(resolution_rows.get("ph_low_freeze_confirmation", {}).get("manual_confirmation_actor", "")).strip(),
            "confirmation_status": (
                "assistant_confirmed_with_guardrails"
                if str(resolution_rows.get("ph_low_freeze_confirmation", {}).get("manual_confirmation_decision", "")).strip()
                else "ready_for_manual_confirmation"
            ),
        },
        {
            "confirmation_item": "ph_high_freeze_confirmation",
            "source_anchor": str(high_s.get("source_anchor", "PMID 28289210")).strip() or "PMID 28289210",
            "staged_confirmation_decision": "accept_with_guardrails",
            "staged_confirmation_note": "Accept only if the expanded hyperphosphorylated signal is not turned into a true aggregation-positive claim and remains separate from base/ph_low.",
            "manual_confirmation_decision": str(resolution_rows.get("ph_high_freeze_confirmation", {}).get("manual_confirmation_decision", "")).strip(),
            "manual_confirmation_note": str(resolution_rows.get("ph_high_freeze_confirmation", {}).get("manual_confirmation_note", "")).strip(),
            "manual_confirmation_actor": str(resolution_rows.get("ph_high_freeze_confirmation", {}).get("manual_confirmation_actor", "")).strip(),
            "confirmation_status": (
                "assistant_confirmed_with_guardrails"
                if str(resolution_rows.get("ph_high_freeze_confirmation", {}).get("manual_confirmation_decision", "")).strip()
                else "ready_for_manual_confirmation"
            ),
        },
    ]
    pending_count = sum(1 for row in rows if not row["manual_confirmation_decision"])
    confirmed_count = sum(1 for row in rows if row["manual_confirmation_decision"] == "accept_with_guardrails")

    summary = {
        "status": "page4_anchor_backed_candidate_confirmation_sheet_resolved" if pending_count == 0 and bool(resolution_s) else "page4_anchor_backed_candidate_confirmation_sheet_ready",
        "target_name": "page4",
        "decision_surface_ready": bool(decision_s),
        "resolution_ready": bool(resolution_s),
        "confirmation_row_count": len(rows),
        "pending_manual_confirmation_count": pending_count,
        "ready_for_manual_confirmation_count": sum(1 for row in rows if row["confirmation_status"] == "ready_for_manual_confirmation"),
        "confirmed_accept_with_guardrails_count": confirmed_count,
        "anchor_backed_candidate_ready_now": pending_count == 0 and confirmed_count == 2,
        "next_required_step": (
            "The two confirmations are now explicit. Reopen promotion review and keep broader promotion blocked until quantitative anchor replacement is ready."
            if pending_count == 0 and bool(resolution_s)
            else "Fill the two manual confirmation fields here first; only then move to the anchor-backed promotion review surface."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Page4 Anchor-Backed Candidate Confirmation Sheet",
        "",
        f"- status: `{s['status']}`",
        f"- target_name: `{s['target_name']}`",
        f"- decision_surface_ready: `{s['decision_surface_ready']}`",
        f"- resolution_ready: `{s['resolution_ready']}`",
        f"- confirmation_row_count: `{s['confirmation_row_count']}`",
        f"- pending_manual_confirmation_count: `{s['pending_manual_confirmation_count']}`",
        f"- ready_for_manual_confirmation_count: `{s['ready_for_manual_confirmation_count']}`",
        f"- confirmed_accept_with_guardrails_count: `{s['confirmed_accept_with_guardrails_count']}`",
        f"- anchor_backed_candidate_ready_now: `{s['anchor_backed_candidate_ready_now']}`",
        "",
        "## Confirmation Rows",
        "",
        "| confirmation_item | source_anchor | staged_confirmation_decision | confirmation_status |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['confirmation_item']}` | `{row['source_anchor']}` | `{row['staged_confirmation_decision']}` | `{row['confirmation_status']}` |"
        )
        lines.append("")
        lines.append(f"- Staged note: {row['staged_confirmation_note']}")
        if row["manual_confirmation_decision"]:
            lines.append(f"- Manual confirmation decision: `{row['manual_confirmation_decision']}`")
            lines.append(f"- Manual confirmation actor: `{row['manual_confirmation_actor']}`")
            lines.append(f"- Manual confirmation note: {row['manual_confirmation_note']}")
        lines.append("")
    lines.extend(["## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the page4 anchor-backed candidate manual confirmation sheet.")
    parser.add_argument("--decision-json", default=DEFAULT_DECISION_JSON)
    parser.add_argument("--ph-low-freeze-json", default=DEFAULT_PH_LOW_FREEZE_JSON)
    parser.add_argument("--ph-high-freeze-json", default=DEFAULT_PH_HIGH_FREEZE_JSON)
    parser.add_argument("--resolution-json", default=DEFAULT_RESOLUTION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.decision_json),
        _load_json(args.ph_low_freeze_json),
        _load_json(args.ph_high_freeze_json),
        _load_json(args.resolution_json),
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
