#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_FOLLOWUP_JSON = "runs/idp_page4_phosphorylation_followup_packet_current.json"
DEFAULT_READINESS_MD = "runs/idp_page4_anchor_backed_candidate_readiness_current.md"
DEFAULT_OUT_JSON = "runs/idp_page4_phosphorylation_fill_draft_current.json"
DEFAULT_OUT_CSV = "runs/idp_page4_phosphorylation_fill_draft_current.csv"
DEFAULT_OUT_MD = "runs/idp_page4_phosphorylation_fill_draft_current.md"


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


def build_payload(followup_payload: dict[str, Any]) -> dict[str, Any]:
    followup_s = dict((followup_payload.get("summary") if isinstance(followup_payload.get("summary"), dict) else {}) or {})

    rows = [
        {
            "fill_target": "ph_low_candidate_state_note",
            "draft_value": "Treat ph_low as a low-phosphorylation-like PAGE4 state only if construct-matched evidence stays explicit; compactness/helicity support may be allowed from HIPK1-like phosphorylation context.",
            "source_anchor": str(followup_s.get("low_state_source_anchor", "")).strip(),
            "confidence": "cautious_medium",
            "guardrail": "do_not_import_hyperphosphorylated_expansion_signal",
            "next_action": "Copy only as a draft state note and keep base identity separate from phospho-state interpretation.",
        },
        {
            "fill_target": "ph_low_candidate_compactness_note",
            "draft_value": "Use compactness or transient-helicity support only when the source clearly maps to a low-phosphorylation-like full-length PAGE4 state.",
            "source_anchor": str(followup_s.get("low_state_source_anchor", "")).strip(),
            "confidence": "cautious_medium",
            "guardrail": "full_length_and_state_explicit_only",
            "next_action": "Record compactness/helicity support as state-specific follow-up, not as a global page4 anchor replacement.",
        },
        {
            "fill_target": "ph_high_candidate_state_note",
            "draft_value": "Treat ph_high as a high-phosphorylation-like PAGE4 state only if construct-matched evidence stays explicit; expanded/random-coil-like interpretation is preferred over compact-state carryover.",
            "source_anchor": str(followup_s.get("high_state_source_anchor", "")).strip(),
            "confidence": "cautious_medium",
            "guardrail": "do_not_mix_with_base_or_ph_low",
            "next_action": "Copy only as a draft state note and keep baseline disorder identity out of the high-phosphorylation branch interpretation.",
        },
        {
            "fill_target": "ph_high_candidate_aggregation_note",
            "draft_value": "Use expanded or aggregation-negative support only when the source clearly maps to a high-phosphorylation-like full-length PAGE4 state.",
            "source_anchor": str(followup_s.get("high_state_source_anchor", "")).strip(),
            "confidence": "cautious_medium",
            "guardrail": "do_not_infer_true_aggregation_positive_from_expansion_source",
            "next_action": "Record expansion or aggregation-negative follow-up separately from provisional branch-family sticky/condensed priors.",
        },
    ]

    summary = {
        "status": "page4_phosphorylation_fill_draft_ready",
        "target_name": "page4",
        "focus_condition_count": 2,
        "focus_conditions": str(followup_s.get("focus_conditions", "")).strip(),
        "draft_fill_row_count": len(rows),
        "readiness_review_artifact": DEFAULT_READINESS_MD,
        "state_mixing_allowed": False,
        "promotion_ready": False,
        "next_required_step": (
            "Copy these ph_low/ph_high notes only as draft follow-up fields, keep baseline identity separate, and then open the page4 anchor-backed candidate readiness review."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Page4 Phosphorylation-State Fill Draft",
        "",
        f"- status: `{s['status']}`",
        f"- target_name: `{s['target_name']}`",
        f"- focus_condition_count: `{s['focus_condition_count']}`",
        f"- focus_conditions: `{s['focus_conditions']}`",
        f"- draft_fill_row_count: `{s['draft_fill_row_count']}`",
        f"- readiness_review_artifact: `{s['readiness_review_artifact']}`",
        f"- state_mixing_allowed: `{s['state_mixing_allowed']}`",
        f"- promotion_ready: `{s['promotion_ready']}`",
        "",
        "## Fill Rows",
        "",
        "| fill_target | source_anchor | confidence | guardrail | next_action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['fill_target']}` | `{row['source_anchor']}` | `{row['confidence']}` | `{row['guardrail']}` | {row['next_action']} |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a draft ph_low/ph_high follow-up fill surface for page4.")
    parser.add_argument("--followup-json", default=DEFAULT_FOLLOWUP_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(_load_json(args.followup_json))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
