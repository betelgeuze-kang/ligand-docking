#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_RECOMMENDATION_JSON = "runs/idp_page4_anchor_backed_confirmation_recommendation_current.json"
DEFAULT_OUT_JSON = "runs/idp_page4_manual_confirmation_resolution_current.json"
DEFAULT_OUT_CSV = "runs/idp_page4_manual_confirmation_resolution_current.csv"
DEFAULT_OUT_MD = "runs/idp_page4_manual_confirmation_resolution_current.md"


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


def build_payload(recommendation_payload: dict[str, Any]) -> dict[str, Any]:
    recommendation_s = dict((recommendation_payload.get("summary") if isinstance(recommendation_payload.get("summary"), dict) else {}) or {})
    rows = [
        {
            "confirmation_item": "ph_low_freeze_confirmation",
            "source_anchor": "PMID 26242913",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/26242913/",
            "manual_confirmation_decision": "accept_with_guardrails",
            "manual_confirmation_actor": "assistant_curated_from_literature",
            "manual_confirmation_note": (
                "Accept with guardrails: use PMID 26242913 only as a construct-matched low-phosphorylation-like follow-up state, "
                "keeping the compact/helicity interpretation explicit and separate from both baseline PAGE4 and hyperphosphorylated PAGE4."
            ),
            "guardrail_rationale": "compact_followup_state_only_not_base_or_hyperphosphorylated",
        },
        {
            "confirmation_item": "ph_high_freeze_confirmation",
            "source_anchor": "PMID 28289210",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/28289210/",
            "manual_confirmation_decision": "accept_with_guardrails",
            "manual_confirmation_actor": "assistant_curated_from_literature",
            "manual_confirmation_note": (
                "Accept with guardrails: use PMID 28289210 only as a hyperphosphorylated expanded/random-coil-like follow-up state "
                "with reduced AP-1 affinity, and do not recast the expanded signal as true aggregation-positive evidence."
            ),
            "guardrail_rationale": "expanded_hyperphosphorylated_followup_not_true_aggregation_positive",
        },
    ]
    summary = {
        "status": "page4_manual_confirmation_resolution_ready",
        "target_name": "page4",
        "recommendation_ready": bool(recommendation_s),
        "resolution_row_count": len(rows),
        "accept_with_guardrails_count": 2,
        "pending_manual_confirmation_count": 0,
        "confirmation_actor": "assistant_curated_from_literature",
        "next_required_step": "Merge these assistant-confirmed decisions into the confirmation sheet, reopen promotion review, and keep broader promotion blocked until quantitative anchor replacement is ready.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Page4 Manual Confirmation Resolution",
        "",
        f"- status: `{s['status']}`",
        f"- target_name: `{s['target_name']}`",
        f"- recommendation_ready: `{s['recommendation_ready']}`",
        f"- resolution_row_count: `{s['resolution_row_count']}`",
        f"- accept_with_guardrails_count: `{s['accept_with_guardrails_count']}`",
        f"- pending_manual_confirmation_count: `{s['pending_manual_confirmation_count']}`",
        f"- confirmation_actor: `{s['confirmation_actor']}`",
        "",
        "## Resolution Rows",
        "",
        "| confirmation_item | source_anchor | manual_confirmation_decision | manual_confirmation_actor |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['confirmation_item']}` | `{row['source_anchor']}` | `{row['manual_confirmation_decision']}` | `{row['manual_confirmation_actor']}` |"
        )
        lines.append("")
        lines.append(f"- Source URL: `{row['source_url']}`")
        lines.append(f"- Note: {row['manual_confirmation_note']}")
        lines.append(f"- Guardrail rationale: `{row['guardrail_rationale']}`")
        lines.append("")
    lines.extend(["## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an assistant-curated page4 manual confirmation resolution.")
    parser.add_argument("--recommendation-json", default=DEFAULT_RECOMMENDATION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(_load_json(args.recommendation_json))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
