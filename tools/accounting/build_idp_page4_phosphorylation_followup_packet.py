#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CITATION_CONFIRMED_JSON = "runs/idp_page4_anchor_citation_confirmed_packet_current.json"
DEFAULT_EVIDENCE_SEED_JSON = "runs/idp_page4_anchor_evidence_seed_current.json"
DEFAULT_FAILURE_JSON = "runs/idp_fold19_page4_failure_analysis_current.json"
DEFAULT_FILL_DRAFT_MD = "runs/idp_page4_phosphorylation_fill_draft_current.md"
DEFAULT_OUT_JSON = "runs/idp_page4_phosphorylation_followup_packet_current.json"
DEFAULT_OUT_CSV = "runs/idp_page4_phosphorylation_followup_packet_current.csv"
DEFAULT_OUT_MD = "runs/idp_page4_phosphorylation_followup_packet_current.md"


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
    evidence_seed_payload: dict[str, Any],
    failure_payload: dict[str, Any],
) -> dict[str, Any]:
    citation_s = dict((citation_confirmed_payload.get("summary") if isinstance(citation_confirmed_payload.get("summary"), dict) else {}) or {})
    failure_s = dict((failure_payload.get("summary") if isinstance(failure_payload.get("summary"), dict) else {}) or {})
    wrong_conditions = list(failure_s.get("current_wrong_conditions", []) or [])

    rows = [
        {
            "followup_condition": "ph_low",
            "state_axis": "compactness_or_helix_shift",
            "source_anchor": "PMID 26242913",
            "expected_signal": "HIPK1-like phosphorylation context may support compactness/helicity shifts only when the state mapping is explicit and construct-matched.",
            "guardrail": "do_not_mix_with_base_or_hyperphosphorylated_rows",
            "next_action": "Extract any full-length PAGE4 compactness or helicity signal that explicitly maps to the low-phosphorylation-like state.",
        },
        {
            "followup_condition": "ph_high",
            "state_axis": "expanded_or_aggregation_negative",
            "source_anchor": "PMID 28289210",
            "expected_signal": "Hyperphosphorylated PAGE4 may favor expansion and aggregation-negative interpretation when the state mapping is explicit.",
            "guardrail": "do_not_import_expansion_signal_into_ph_low_or_base",
            "next_action": "Extract any full-length PAGE4 expanded or aggregation-negative evidence that explicitly maps to the high-phosphorylation-like state.",
        },
        {
            "followup_condition": "base",
            "state_axis": "baseline_disorder_reference",
            "source_anchor": str(citation_s.get("confirmed_anchor_citation", "")).strip(),
            "expected_signal": "Keep baseline disorder identity anchored to the construct citation and separate from phosphorylation-state interpretation.",
            "guardrail": "baseline_reference_only_no_state_mixing",
            "next_action": "Use the construct citation only as a baseline identity reference while keeping phospho-state interpretation isolated to ph_low/ph_high rows.",
        },
        {
            "followup_condition": "hydro_high,salt_high",
            "state_axis": "non_focus_wrong_conditions",
            "source_anchor": "defer_for_now",
            "expected_signal": "Do not overfit the phosphorylation-state follow-up packet to unrelated wrong-condition rows.",
            "guardrail": "keep_nonfocus_conditions_out_of_first_followup_slice",
            "next_action": "Leave non-focus wrong conditions for later anchor refinement after ph_low/ph_high state interpretation is explicit.",
        },
    ]

    summary = {
        "status": "page4_phosphorylation_followup_packet_ready",
        "target_name": "page4",
        "construct_confirmation_status": str(citation_s.get("construct_confirmation_status", "")).strip(),
        "construct_anchor_citation": str(citation_s.get("confirmed_anchor_citation", "")).strip(),
        "focus_condition_count": 2,
        "focus_conditions": "ph_low ; ph_high",
        "non_focus_wrong_condition_count": len(wrong_conditions),
        "non_focus_wrong_conditions": ", ".join(wrong_conditions),
        "low_state_source_anchor": "PMID 26242913",
        "high_state_source_anchor": "PMID 28289210",
        "fill_draft_artifact": DEFAULT_FILL_DRAFT_MD,
        "state_mixing_allowed": False,
        "promotion_ready": False,
        "next_required_step": (
            "Open the page4 phosphorylation fill draft next, fill the ph_low and ph_high state-specific notes first, keep baseline identity separate from phospho-state interpretation, "
            "and only then reconsider whether page4 can move from provisional-only to an anchor-backed candidate."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Page4 Phosphorylation-State Follow-up Packet",
        "",
        f"- status: `{s['status']}`",
        f"- target_name: `{s['target_name']}`",
        f"- construct_confirmation_status: `{s['construct_confirmation_status']}`",
        f"- construct_anchor_citation: `{s['construct_anchor_citation']}`",
        f"- focus_condition_count: `{s['focus_condition_count']}`",
        f"- focus_conditions: `{s['focus_conditions']}`",
        f"- non_focus_wrong_condition_count: `{s['non_focus_wrong_condition_count']}`",
        f"- non_focus_wrong_conditions: `{s['non_focus_wrong_conditions']}`",
        f"- low_state_source_anchor: `{s['low_state_source_anchor']}`",
        f"- high_state_source_anchor: `{s['high_state_source_anchor']}`",
        f"- fill_draft_artifact: `{s['fill_draft_artifact']}`",
        f"- state_mixing_allowed: `{s['state_mixing_allowed']}`",
        f"- promotion_ready: `{s['promotion_ready']}`",
        "",
        "## Follow-up Rows",
        "",
        "| followup_condition | state_axis | source_anchor | guardrail | next_action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['followup_condition']}` | `{row['state_axis']}` | `{row['source_anchor']}` | `{row['guardrail']}` | {row['next_action']} |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a page4 ph_low/ph_high phosphorylation-state follow-up packet.")
    parser.add_argument("--citation-confirmed-json", default=DEFAULT_CITATION_CONFIRMED_JSON)
    parser.add_argument("--evidence-seed-json", default=DEFAULT_EVIDENCE_SEED_JSON)
    parser.add_argument("--failure-json", default=DEFAULT_FAILURE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.citation_confirmed_json),
        _load_json(args.evidence_seed_json),
        _load_json(args.failure_json),
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
