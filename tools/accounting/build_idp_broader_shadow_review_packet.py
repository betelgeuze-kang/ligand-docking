#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DECISION_JSON = "runs/idp_commercial_pretest_decision_current.json"
DEFAULT_VALIDATION_RESULT_JSON = "runs/idp_commercial_pretest_validation_result_current.json"
DEFAULT_SCAFFOLD_JSON = "runs/idp_broader_anchor_shadow_scaffold_current.json"
DEFAULT_ROSTER_VIABILITY_JSON = "runs/idp_broader_anchor_roster_viability_packet_current.json"
DEFAULT_OUT_JSON = "runs/idp_broader_shadow_review_packet_current.json"
DEFAULT_OUT_CSV = "runs/idp_broader_shadow_review_packet_current.csv"
DEFAULT_OUT_MD = "runs/idp_broader_shadow_review_packet_current.md"


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
    validation_result: dict[str, Any],
    scaffold_payload: dict[str, Any],
    roster_viability: dict[str, Any] | None = None,
) -> dict[str, Any]:
    decision_s = dict(decision_payload.get("summary", {}) or {})
    validation_s = dict(validation_result.get("summary", {}) or {})
    scaffold_s = dict(scaffold_payload.get("summary", {}) or {})
    roster_s = dict((roster_viability or {}).get("summary", {}) or {})
    additional_anchor_backed_target_count = int(roster_s.get("additional_anchor_backed_target_count", 0) or 0)
    provisional_only_target_count = int(roster_s.get("provisional_only_target_count", 0) or 0)
    no_true_broader_roster = additional_anchor_backed_target_count == 0
    same_scope_reproducibility_confirmed = bool(decision_s.get("same_scope_reproducibility_confirmed", False))
    page4_candidate_ready_now = bool(decision_s.get("page4_candidate_ready_now", False))

    rows = [
        {
            "review_item": "promotion_policy",
            "status": "review_now",
            "question": "Should broader_full_idp_promotion remain blocked after a clean bounded commercial-pretest rerun?",
            "current_signal": str(decision_s.get("decision", "")).strip(),
            "review_rule": "Do not auto-promote from bounded validation alone.",
        },
        {
            "review_item": "target_roster",
            "status": "review_now",
            "question": "What broader anchor-backed roster should be used beyond the current controlled 7-target scaffold?",
            "current_signal": (
                f"controlled_target_count={scaffold_s.get('controlled_target_count', 0)}; "
                f"additional_anchor_backed_target_count={roster_s.get('additional_anchor_backed_target_count', 0)}; "
                f"provisional_only_target_count={roster_s.get('provisional_only_target_count', 0)}"
            ),
            "review_rule": "Only expand with anchor-backed targets and preserve no-override guardrails.",
        },
        {
            "review_item": "guardrail_freeze",
            "status": "keep_frozen",
            "question": "What must remain frozen in the first broader full-IDP shadow rerun?",
            "current_signal": "feature_state_smoothing_only; no_coordinate_correction; no_ranking_override; no_gate_override",
            "review_rule": "Carry the exact same guardrails into the first broader rerun.",
        },
        {
            "review_item": "success_criteria",
            "status": "review_now",
            "question": "What is the minimum acceptable result for the first broader full-IDP shadow rerun?",
            "current_signal": (
                f"bounded_validation_status={validation_s.get('status', '')}; "
                f"corrected_pass_folds={validation_s.get('corrected_pass_folds', '')}/{validation_s.get('fold_count', '')}; "
                f"tau_k18_corrected_gate_pass={validation_s.get('tau_k18_corrected_gate_pass', '')}"
            ),
            "review_rule": "Require zero state/gate drift and no corrected-pass regression against the clean bounded commercial-pretest run.",
        },
    ]

    summary = {
        "status": (
            "broader_shadow_review_packet_ready_no_true_broader_roster"
            if no_true_broader_roster
            else "broader_shadow_review_packet_ready_true_broader_roster_available"
        ),
        "operator_scope_now": str(decision_s.get("operator_scope_now", "")).strip(),
        "broader_promotion_blocked": bool(decision_s.get("broader_promotion_blocked", True)),
        "shadow_safe_retained": bool(decision_s.get("shadow_safe_retained", False)),
        "bounded_validation_status": str(validation_s.get("status", "")).strip(),
        "bounded_validation_pass_folds": (
            f"{validation_s.get('corrected_pass_folds', '')}/{validation_s.get('fold_count', '')}"
        ),
        "controlled_target_count": int(scaffold_s.get("controlled_target_count", 0) or 0),
        "additional_anchor_backed_target_count": additional_anchor_backed_target_count,
        "provisional_only_target_count": provisional_only_target_count,
        "true_broader_rerun_ready": not no_true_broader_roster,
        "same_scope_process_check_ready": no_true_broader_roster and not same_scope_reproducibility_confirmed,
        "same_scope_reproducibility_confirmed": same_scope_reproducibility_confirmed,
        "page4_candidate_ready_now": page4_candidate_ready_now,
        "next_anchor_curation_target": (
            "page4_quantitative_anchor_replacement"
            if no_true_broader_roster and same_scope_reproducibility_confirmed and page4_candidate_ready_now
            else "page4"
            if no_true_broader_roster and same_scope_reproducibility_confirmed
            else "same_scope_process_check_or_new_anchor"
            if no_true_broader_roster
            else "true_broader_rerun"
        ),
        "review_item_count": len(rows),
        "next_required_step": (
            "Keep broader_full_idp_promotion blocked, treat same-scope reproducibility as confirmed, and use this review packet to move the next improvement to page4 quantitative anchor replacement before any true broader rerun."
            if no_true_broader_roster and same_scope_reproducibility_confirmed and page4_candidate_ready_now
            else
            "Keep broader_full_idp_promotion blocked, treat same-scope reproducibility as confirmed, and use this review packet to move the next improvement to page4 phosphorylation-state follow-up or another additional anchor-backed target before any true broader rerun."
            if no_true_broader_roster and same_scope_reproducibility_confirmed
            else
            "Keep broader_full_idp_promotion blocked, do not call the next run a true broader rerun yet, and use this review packet to choose either one same-scope process check or the curation of at least one additional anchor-backed target first."
            if no_true_broader_roster
            else "Review broader-promotion policy and the next broader anchor-backed roster, keep broader_full_idp_promotion blocked meanwhile, then define one broader full-IDP shadow-only rerun under the same no-override guardrails."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Broader Shadow Review Packet",
        "",
        f"- status: `{s['status']}`",
        f"- operator_scope_now: `{s['operator_scope_now']}`",
        f"- broader_promotion_blocked: `{s['broader_promotion_blocked']}`",
        f"- shadow_safe_retained: `{s['shadow_safe_retained']}`",
        f"- bounded_validation_status: `{s['bounded_validation_status']}`",
        f"- bounded_validation_pass_folds: `{s['bounded_validation_pass_folds']}`",
        f"- controlled_target_count: `{s['controlled_target_count']}`",
        f"- additional_anchor_backed_target_count: `{s['additional_anchor_backed_target_count']}`",
        f"- provisional_only_target_count: `{s['provisional_only_target_count']}`",
        f"- true_broader_rerun_ready: `{s['true_broader_rerun_ready']}`",
        f"- same_scope_process_check_ready: `{s['same_scope_process_check_ready']}`",
        f"- same_scope_reproducibility_confirmed: `{s['same_scope_reproducibility_confirmed']}`",
        f"- page4_candidate_ready_now: `{s['page4_candidate_ready_now']}`",
        f"- next_anchor_curation_target: `{s['next_anchor_curation_target']}`",
        f"- review_item_count: `{s['review_item_count']}`",
        "",
        "## Review Items",
        "",
        "| item | status | question | current_signal | review_rule |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['review_item']}` | `{row['status']}` | {row['question']} | `{row['current_signal']}` | {row['review_rule']} |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build the next-step review packet for broader IDP shadow promotion.")
    p.add_argument("--decision-json", default=DEFAULT_DECISION_JSON)
    p.add_argument("--validation-result-json", default=DEFAULT_VALIDATION_RESULT_JSON)
    p.add_argument("--scaffold-json", default=DEFAULT_SCAFFOLD_JSON)
    p.add_argument("--roster-viability-json", default=DEFAULT_ROSTER_VIABILITY_JSON)
    p.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    p.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    p.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.decision_json),
        _load_json(args.validation_result_json),
        _load_json(args.scaffold_json),
        _load_json(args.roster_viability_json),
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
