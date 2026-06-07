#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_HOLDOUT_SUMMARY_JSON = "runs/idp_3bead_holdout_v7_anchor_commercial_pretest_processcheck_r1_summary.json"
DEFAULT_COMBINED_GATE_JSON = "runs/idp_3bead_holdout_v7_anchor_commercial_pretest_processcheck_r1_combined_gate_summary.json"
DEFAULT_CORRECTED_EVAL_JSON = "runs/idp_3bead_holdout_v7_anchor_commercial_pretest_processcheck_r1_corrected_eval_summary.json"
DEFAULT_PAGE4_PROMOTION_REVIEW_JSON = "runs/idp_page4_anchor_backed_promotion_review_current.json"
DEFAULT_ROSTER_VIABILITY_JSON = "runs/idp_broader_anchor_roster_viability_packet_current.json"
DEFAULT_OUT_JSON = "runs/idp_same_scope_processcheck_result_current.json"
DEFAULT_OUT_MD = "runs/idp_same_scope_processcheck_result_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _maybe_read_json(path_like: str) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def build_payload(
    holdout_summary: dict[str, Any] | None = None,
    combined_gate_summary: dict[str, Any] | None = None,
    corrected_eval_summary: dict[str, Any] | None = None,
    page4_promotion_review: dict[str, Any] | None = None,
    roster_viability: dict[str, Any] | None = None,
) -> dict[str, Any]:
    holdout_s = dict(holdout_summary or {})
    combined_s = dict(combined_gate_summary or {})
    corrected_s = dict(corrected_eval_summary or {})
    page4_promotion_review_s = dict(((page4_promotion_review or {}).get("summary", {}) if isinstance((page4_promotion_review or {}).get("summary", {}), dict) else {}) or {})
    roster_s = dict(((roster_viability or {}).get("summary", {}) if isinstance((roster_viability or {}).get("summary", {}), dict) else {}) or {})
    kalman_s = dict((corrected_s.get("kalman_shadow", {}) if isinstance(corrected_s.get("kalman_shadow", {}), dict) else {}) or {})
    additional_anchor_backed_target_count = int(roster_s.get("additional_anchor_backed_target_count", 0) or 0)

    summary_exists = bool(holdout_s)
    corrected_exists = bool(corrected_s)
    fold_count = int(holdout_s.get("fold_count", 0) or 0)
    corrected_pass_folds = int(holdout_s.get("corrected_pass_folds", 0) or 0)
    would_change_state_count = int(kalman_s.get("would_change_state_count", 0) or 0)
    would_change_gate_count = int(kalman_s.get("would_change_gate_count", 0) or 0)
    would_change_llps_flag_count = int(kalman_s.get("would_change_llps_flag_count", 0) or 0)
    would_change_aggregation_flag_count = int(kalman_s.get("would_change_aggregation_flag_count", 0) or 0)
    shadow_safe_retained = (
        corrected_exists
        and would_change_state_count == 0
        and would_change_gate_count == 0
        and would_change_llps_flag_count == 0
        and would_change_aggregation_flag_count == 0
    )

    if not summary_exists:
        status = "same_scope_processcheck_running_or_not_yet_summarized"
        next_required_step = (
            "Wait for the same-scope process check to finish. Keep broader_full_idp_promotion blocked meanwhile, "
            "and do not change the current controlled commercial-pretest lane."
        )
    elif shadow_safe_retained and corrected_pass_folds == fold_count and fold_count > 0:
        status = "same_scope_processcheck_completed_reproducibility_confirmed"
        next_required_step = (
            "Treat same-scope reproducibility as confirmed, keep broader_full_idp_promotion blocked, and reopen broader shadow review with page4 now counted as the first additional anchor-backed target."
            if additional_anchor_backed_target_count > 0
            else
            "Treat same-scope reproducibility as confirmed, keep broader_full_idp_promotion blocked, and move the next improvement to page4 quantitative anchor replacement."
            if bool(page4_promotion_review_s.get("anchor_backed_candidate_ready_now", False))
            else "Treat same-scope reproducibility as confirmed, keep broader_full_idp_promotion blocked, and move the next improvement to the page4 manual-confirmation console."
        )
    else:
        status = "same_scope_processcheck_completed_follow_up_required"
        next_required_step = (
            "Do not broaden yet. Inspect the process-check regression details, keep broader_full_idp_promotion blocked, "
            "and restore same-scope reproducibility before any anchor-expansion step."
        )

    summary = {
        "status": status,
        "operator_scope_now": "controlled_shadow_only_commercial_pretest",
        "summary_exists": summary_exists,
        "corrected_eval_exists": corrected_exists,
        "fold_count": fold_count,
        "corrected_pass_folds": corrected_pass_folds,
        "combined_gate_pass": bool(holdout_s.get("combined_gate_pass", combined_s.get("pass", False))),
        "shadow_safe_retained": shadow_safe_retained,
        "additional_anchor_backed_target_count": additional_anchor_backed_target_count,
        "page4_candidate_ready_now": bool(page4_promotion_review_s.get("anchor_backed_candidate_ready_now", False)),
        "next_anchor_curation_target": (
            "true_broader_rerun_review"
            if status == "same_scope_processcheck_completed_reproducibility_confirmed"
            and additional_anchor_backed_target_count > 0
            else
            "page4_quantitative_anchor_replacement"
            if status == "same_scope_processcheck_completed_reproducibility_confirmed"
            and bool(page4_promotion_review_s.get("anchor_backed_candidate_ready_now", False))
            else "page4"
            if status == "same_scope_processcheck_completed_reproducibility_confirmed"
            else ""
        ),
        "would_change_state_count": would_change_state_count,
        "would_change_gate_count": would_change_gate_count,
        "would_change_llps_flag_count": would_change_llps_flag_count,
        "would_change_aggregation_flag_count": would_change_aggregation_flag_count,
        "default_feature_mask": str(kalman_s.get("feature_mask_name", "rg_sasa_only")).strip() or "rg_sasa_only",
        "next_required_step": next_required_step,
    }
    return {"summary": summary}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Same-Scope Process Check Result",
        "",
        f"- status: `{s['status']}`",
        f"- operator_scope_now: `{s['operator_scope_now']}`",
        f"- summary_exists: `{s['summary_exists']}`",
        f"- corrected_eval_exists: `{s['corrected_eval_exists']}`",
        f"- fold_count: `{s['fold_count']}`",
        f"- corrected_pass_folds: `{s['corrected_pass_folds']}`",
        f"- combined_gate_pass: `{s['combined_gate_pass']}`",
        f"- shadow_safe_retained: `{s['shadow_safe_retained']}`",
        f"- additional_anchor_backed_target_count: `{s['additional_anchor_backed_target_count']}`",
        f"- page4_candidate_ready_now: `{s['page4_candidate_ready_now']}`",
        f"- next_anchor_curation_target: `{s['next_anchor_curation_target']}`",
        f"- would_change_state_count: `{s['would_change_state_count']}`",
        f"- would_change_gate_count: `{s['would_change_gate_count']}`",
        f"- would_change_llps_flag_count: `{s['would_change_llps_flag_count']}`",
        f"- would_change_aggregation_flag_count: `{s['would_change_aggregation_flag_count']}`",
        f"- default_feature_mask: `{s['default_feature_mask']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the current result surface for the bounded same-scope IDP process check.")
    parser.add_argument("--holdout-summary-json", default=DEFAULT_HOLDOUT_SUMMARY_JSON)
    parser.add_argument("--combined-gate-json", default=DEFAULT_COMBINED_GATE_JSON)
    parser.add_argument("--corrected-eval-json", default=DEFAULT_CORRECTED_EVAL_JSON)
    parser.add_argument("--page4-promotion-review-json", default=DEFAULT_PAGE4_PROMOTION_REVIEW_JSON)
    parser.add_argument("--roster-viability-json", default=DEFAULT_ROSTER_VIABILITY_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _maybe_read_json(args.holdout_summary_json),
        _maybe_read_json(args.combined_gate_json),
        _maybe_read_json(args.corrected_eval_json),
        _maybe_read_json(args.page4_promotion_review_json),
        _maybe_read_json(args.roster_viability_json),
    )
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
