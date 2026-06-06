#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.operator_surface_contracts import IDP_SAFE_SCOPE_CONTROLLED_PRETEST

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_HOLDOUT_SUMMARY_JSON = "runs/idp_3bead_holdout_v7_anchor_commercial_pretest_r18validation_r1_summary.json"
DEFAULT_COMBINED_GATE_JSON = "runs/idp_3bead_holdout_v7_anchor_commercial_pretest_r18validation_r1_combined_gate_summary.json"
DEFAULT_CORRECTED_EVAL_JSON = "runs/idp_3bead_holdout_v7_anchor_commercial_pretest_r18validation_r1_corrected_eval_summary.json"
DEFAULT_FAILURE_PACKET_JSON = "runs/idp_tau_k18_corrected_path_failure_packet_current.json"
DEFAULT_PRETEST_PACKET_JSON = "runs/idp_commercial_pretest_packet_current.json"
DEFAULT_DIAGNOSTIC_RESULT_JSON = "runs/tau_k18_corrected_path_diagnostic_result_current.json"
DEFAULT_ACTIVATION_RESULT_JSON = "runs/tau_k18_corrected_path_activation_result_current.json"
DEFAULT_VALIDATION_RESULT_JSON = "runs/idp_commercial_pretest_validation_result_current.json"
DEFAULT_ROSTER_VIABILITY_JSON = "runs/idp_broader_anchor_roster_viability_packet_current.json"
DEFAULT_SAME_SCOPE_PROCESSCHECK_RESULT_JSON = "runs/idp_same_scope_processcheck_result_current.json"
DEFAULT_PAGE4_PROMOTION_REVIEW_JSON = "runs/idp_page4_anchor_backed_promotion_review_current.json"
DEFAULT_OUT_JSON = "runs/idp_commercial_pretest_decision_current.json"
DEFAULT_OUT_MD = "runs/idp_commercial_pretest_decision_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _read_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _maybe_read_json(path_like: str) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def build_payload(
    holdout_summary: dict[str, Any],
    combined_gate_summary: dict[str, Any],
    corrected_eval_summary: dict[str, Any],
    failure_packet: dict[str, Any],
    pretest_packet: dict[str, Any],
    diagnostic_result: dict[str, Any] | None = None,
    activation_result: dict[str, Any] | None = None,
    validation_result: dict[str, Any] | None = None,
    roster_viability: dict[str, Any] | None = None,
    same_scope_processcheck_result: dict[str, Any] | None = None,
    page4_promotion_review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    holdout_s = dict(holdout_summary or {})
    combined_s = dict(combined_gate_summary or {})
    corrected_s = dict(corrected_eval_summary or {})
    failure_s = dict((failure_packet.get("summary", {}) if isinstance(failure_packet.get("summary", {}), dict) else {}) or {})
    packet_s = dict((pretest_packet.get("summary", {}) if isinstance(pretest_packet.get("summary", {}), dict) else {}) or {})
    diagnostic_s = dict(((diagnostic_result or {}).get("summary", {}) if isinstance((diagnostic_result or {}).get("summary", {}), dict) else {}) or {})
    activation_s = dict(((activation_result or {}).get("summary", {}) if isinstance((activation_result or {}).get("summary", {}), dict) else {}) or {})
    validation_s = dict(((validation_result or {}).get("summary", {}) if isinstance((validation_result or {}).get("summary", {}), dict) else {}) or {})
    roster_s = dict(((roster_viability or {}).get("summary", {}) if isinstance((roster_viability or {}).get("summary", {}), dict) else {}) or {})
    same_scope_s = dict(((same_scope_processcheck_result or {}).get("summary", {}) if isinstance((same_scope_processcheck_result or {}).get("summary", {}), dict) else {}) or {})
    page4_promotion_review_s = dict(((page4_promotion_review or {}).get("summary", {}) if isinstance((page4_promotion_review or {}).get("summary", {}), dict) else {}) or {})
    kalman_s = dict((corrected_s.get("kalman_shadow", {}) if isinstance(corrected_s.get("kalman_shadow", {}), dict) else {}) or {})
    additional_anchor_backed_target_count = int(roster_s.get("additional_anchor_backed_target_count", 0) or 0)
    provisional_only_target_count = int(roster_s.get("provisional_only_target_count", 0) or 0)
    same_scope_reproducibility_confirmed = (
        str(same_scope_s.get("status", "")).strip() == "same_scope_processcheck_completed_reproducibility_confirmed"
    )
    page4_candidate_ready_now = bool(page4_promotion_review_s.get("anchor_backed_candidate_ready_now", False))

    would_change_state_count = int(kalman_s.get("would_change_state_count", 0) or 0)
    would_change_gate_count = int(kalman_s.get("would_change_gate_count", 0) or 0)
    would_change_llps_flag_count = int(kalman_s.get("would_change_llps_flag_count", 0) or 0)
    would_change_aggregation_flag_count = int(kalman_s.get("would_change_aggregation_flag_count", 0) or 0)
    shadow_safe_retained = (
        would_change_state_count == 0
        and would_change_gate_count == 0
        and would_change_llps_flag_count == 0
        and would_change_aggregation_flag_count == 0
    )
    fold_count = int(holdout_s.get("fold_count", 0) or 0)
    corrected_pass_folds = int(holdout_s.get("corrected_pass_folds", 0) or 0)
    baseline_pass_folds = int(holdout_s.get("baseline_pass_folds", 0) or 0)
    combined_gate_pass = bool(holdout_s.get("combined_gate_pass", combined_s.get("pass", False)))

    blocker_reason = str(
        failure_s.get(
            "blocker_reason",
            "tau_k18 corrected-path fragility remains the blocker for broader IDP promotion; Kalman shadow stayed telemetry-only and did not cause the failure.",
        )
    )
    diagnostic_observation = str(diagnostic_s.get("primary_observation", "")).strip()
    activation_observation = str(activation_s.get("primary_observation", "")).strip()
    if diagnostic_observation == "short_tau_diagnostic_path_inactive_on_current_corrected_slice":
        blocker_reason = (
            f"{blocker_reason} The latest base/ph_low observability-only slice emitted tau_k18_diag_* columns on "
            f"{diagnostic_s.get('debug_columns_present_count', 0)}/{diagnostic_s.get('focus_condition_count', 0)} focus rows "
            f"but kept the short-tau diagnostic path inactive on {diagnostic_s.get('inactive_short_tau_diag_count', 0)}/"
            f"{diagnostic_s.get('focus_condition_count', 0)} rows."
        ).strip()
    if activation_observation == "short_tau_diagnostic_path_activated_on_focus_rows":
        blocker_reason = (
            f"{blocker_reason} A bounded activation-check slice with IDP_R16_ML_PATCH=1 activated the short-tau path on "
            f"{activation_s.get('focus_condition_active_count', 0)}/{activation_s.get('focus_condition_count', 0)} focus rows "
            f"and locally passed the corrected gate with dominant_state_accuracy={activation_s.get('activation_dominant_state_accuracy')}."
        ).strip()
    if str(validation_s.get("status", "")).strip() == "bounded_commercial_pretest_completed_blocker_persists_activation_retained":
        blocker_reason = (
            f"{blocker_reason} A bounded commercial-pretest rerun kept the activated path but still finished at "
            f"{validation_s.get('corrected_pass_folds', 0)}/{validation_s.get('fold_count', 0)} corrected pass folds, with "
            f"tau_k18_corrected_gate_pass={validation_s.get('tau_k18_corrected_gate_pass')}."
        ).strip()
    elif str(validation_s.get("status", "")).strip() == "bounded_commercial_pretest_completed_activation_retained":
        blocker_reason = (
            "The bounded commercial-pretest rerun stayed shadow-safe and fold-clean, including tau_k18 corrected gate recovery. "
            "Broader promotion remains blocked only because a wider full-IDP shadow step still needs explicit review rather than automatic promotion."
        )
    non_cause_note = str(
        failure_s.get(
            "do_not_infer",
            "Do not treat this as a Kalman-shadow regression or as evidence against the current controlled shadow-only commercial-pretest lane.",
        )
    )
    if shadow_safe_retained and corrected_pass_folds < fold_count:
        decision = "shadow_safe_retained_broader_promotion_blocked"
        status = "controlled_shadow_only_commercial_pretest_completed_shadow_safe"
        decision_reason = (
            "The current controlled shadow-only commercial-pretest lane remains shadow-safe, "
            "but broader promotion stays blocked because tau_k18 still shows corrected-path fragility."
        )
        if str(validation_s.get("status", "")).strip() == "bounded_commercial_pretest_completed_blocker_persists_activation_retained":
            next_required_step = str(validation_s.get("next_required_step", "")).strip() or (
                "Keep broader_full_idp_promotion blocked, keep controlled_shadow_only_commercial_pretest unchanged, "
                "and use the tau_k18 full-fold corrected failure slice to choose exactly one next corrected-path interpretation or calibration rule."
            )
        elif activation_observation == "short_tau_diagnostic_path_activated_on_focus_rows":
            next_required_step = (
                "Keep broader_full_idp_promotion blocked, keep controlled_shadow_only_commercial_pretest unchanged, "
                "and validate the same now-active short-tau path on a bounded commercial-pretest rerun before any broader rerun."
            )
        elif diagnostic_observation == "short_tau_diagnostic_path_inactive_on_current_corrected_slice":
            next_required_step = (
                "Keep broader_full_idp_promotion blocked, keep controlled_shadow_only_commercial_pretest unchanged, "
                "and inspect why the short-tau diagnostic path stayed inactive on base/ph_low before choosing another corrected-path calibration rule."
            )
        else:
            next_required_step = (
                "Keep broader_full_idp_promotion blocked, keep controlled_shadow_only_commercial_pretest unchanged, "
                "and move the next tau_k18 slice to the remaining base/ph_low compact-state gap."
            )
    elif shadow_safe_retained:
        decision = "shadow_safe_retained_promotion_review_required"
        status = "controlled_shadow_only_commercial_pretest_completed_shadow_safe"
        decision_reason = (
            "The current controlled shadow-only commercial-pretest lane remained shadow-safe and fold-clean, "
            "but broader promotion still requires an explicit review step."
        )
        if additional_anchor_backed_target_count == 0:
            blocker_reason = (
                f"{blocker_reason} Local roster viability adds no additional anchor-backed targets beyond the currently validated 7-target scaffold; "
                f"the remaining {provisional_only_target_count} local targets are provisional-only and cannot justify a true broader rerun yet."
            ).strip()
            if same_scope_reproducibility_confirmed:
                blocker_reason = (
                    f"{blocker_reason} The bounded same-scope process check then confirmed reproducibility at "
                    f"{same_scope_s.get('corrected_pass_folds', 0)}/{same_scope_s.get('fold_count', 0)} corrected pass folds "
                    f"with would_change_state_count={same_scope_s.get('would_change_state_count', 0)} and "
                    f"would_change_gate_count={same_scope_s.get('would_change_gate_count', 0)}."
                ).strip()
                if page4_candidate_ready_now:
                    blocker_reason = (
                        f"{blocker_reason} Page4 is now candidate-ready with guardrails, but it still remains provisional until quantitative anchor replacement replaces the current branch-family prior ranges."
                    ).strip()
                    next_required_step = (
                        "Keep the current controlled commercial-pretest lane bounded, keep broader_full_idp_promotion blocked, "
                        "treat same-scope reproducibility as confirmed, and move the next improvement to page4 quantitative anchor replacement "
                        "before any true broader rerun."
                    )
                else:
                    next_required_step = (
                        "Keep the current controlled commercial-pretest lane bounded, keep broader_full_idp_promotion blocked, "
                        "treat same-scope reproducibility as confirmed, and move the next improvement to the page4 manual-confirmation console "
                        "before any true broader rerun."
                    )
            else:
                next_required_step = (
                    "Keep the current controlled commercial-pretest lane bounded, keep broader_full_idp_promotion blocked, and do not call the next run a true broader rerun yet. "
                    "Either approve one same-scope process check on the 7-target literature-anchor subset or curate at least one additional anchor-backed target before defining a broader shadow rerun."
                )
        else:
            next_required_step = (
                "Keep the current controlled commercial-pretest lane bounded, use the broader-shadow review packet to freeze promotion policy, target roster, and guardrails, "
                "and only then consider one broader full-IDP shadow rerun with the same no-override guardrails."
            )
    else:
        decision = "shadow_safety_regressed_broader_promotion_blocked"
        status = "controlled_shadow_only_commercial_pretest_regressed_shadow_safety"
        decision_reason = (
            "The controlled shadow-only commercial-pretest lane no longer looks shadow-safe, "
            "so broader promotion must stay blocked until shadow regressions are removed."
        )
        next_required_step = (
            "Stop broader promotion work, restore shadow-safe behavior first, and only then revisit commercial-pretest conclusions."
        )

    summary = {
        "decision": decision,
        "status": status,
        "operator_scope_now": IDP_SAFE_SCOPE_CONTROLLED_PRETEST,
        "shadow_safe_retained": shadow_safe_retained,
        "broader_promotion_blocked": True,
        "fold_count": fold_count,
        "baseline_pass_folds": baseline_pass_folds,
        "corrected_pass_folds": corrected_pass_folds,
        "combined_gate_pass": combined_gate_pass,
        "blocking_target": (
            "broader_shadow_review"
            if decision == "shadow_safe_retained_promotion_review_required" and additional_anchor_backed_target_count > 0
            else "page4_quantitative_anchor_replacement"
            if decision == "shadow_safe_retained_promotion_review_required" and same_scope_reproducibility_confirmed and additional_anchor_backed_target_count == 0 and page4_candidate_ready_now
            else "anchor_roster"
            if decision == "shadow_safe_retained_promotion_review_required" and additional_anchor_backed_target_count == 0
            else str(failure_s.get("failure_anchor_target", "tau_k18"))
        ),
        "blocking_class": (
            "page4_quantitative_anchor_replacement_required"
            if decision == "shadow_safe_retained_promotion_review_required" and same_scope_reproducibility_confirmed and additional_anchor_backed_target_count == 0 and page4_candidate_ready_now
            else "anchor_roster_not_broader_ready"
            if decision == "shadow_safe_retained_promotion_review_required" and same_scope_reproducibility_confirmed and additional_anchor_backed_target_count == 0
            else "bounded_review_required"
            if decision == "shadow_safe_retained_promotion_review_required"
            else "corrected_path_fragility"
        ),
        "default_feature_mask": str(kalman_s.get("feature_mask_name", packet_s.get("default_feature_mask", ""))),
        "core_target_count": int(packet_s.get("core_target_count", 0) or 0),
        "watchlist_target_count": int(packet_s.get("watchlist_target_count", 0) or 0),
        "additional_anchor_backed_target_count": additional_anchor_backed_target_count,
        "provisional_only_target_count": provisional_only_target_count,
        "same_scope_reproducibility_confirmed": same_scope_reproducibility_confirmed,
        "same_scope_processcheck_status": str(same_scope_s.get("status", "")).strip(),
        "page4_candidate_ready_now": page4_candidate_ready_now,
        "next_anchor_curation_target": (
            "page4_quantitative_anchor_replacement"
            if same_scope_reproducibility_confirmed and additional_anchor_backed_target_count == 0 and page4_candidate_ready_now
            else "broader_shadow_review"
            if additional_anchor_backed_target_count > 0
            else "page4"
            if same_scope_reproducibility_confirmed and additional_anchor_backed_target_count == 0
            else ""
        ),
        "would_change_state_count": would_change_state_count,
        "would_change_gate_count": would_change_gate_count,
        "would_change_llps_flag_count": would_change_llps_flag_count,
        "would_change_aggregation_flag_count": would_change_aggregation_flag_count,
        "blocker_reason": blocker_reason,
        "latest_diagnostic_rule_name": str(diagnostic_s.get("diagnostic_rule_name", "")).strip(),
        "latest_diagnostic_observation": diagnostic_observation,
        "latest_activation_rule_name": str(activation_s.get("activation_rule_name", "")).strip(),
        "latest_activation_observation": activation_observation,
        "latest_activation_status": str(activation_s.get("status", "")).strip(),
        "latest_activation_focus_condition_active_count": int(activation_s.get("focus_condition_active_count", 0) or 0),
        "latest_validation_status": str(validation_s.get("status", "")).strip(),
        "decision_reason": decision_reason,
        "non_cause_note": non_cause_note,
        "next_required_step": next_required_step,
    }
    return {"summary": summary}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# IDP Commercial Pretest Decision",
        "",
        f"- decision: `{summary['decision']}`",
        f"- status: `{summary['status']}`",
        f"- operator_scope_now: `{summary['operator_scope_now']}`",
        f"- shadow_safe_retained: `{summary['shadow_safe_retained']}`",
        f"- broader_promotion_blocked: `{summary['broader_promotion_blocked']}`",
        f"- fold_count: `{summary['fold_count']}`",
        f"- baseline_pass_folds: `{summary['baseline_pass_folds']}`",
        f"- corrected_pass_folds: `{summary['corrected_pass_folds']}`",
        f"- combined_gate_pass: `{summary['combined_gate_pass']}`",
        f"- blocking_target: `{summary['blocking_target']}`",
        f"- blocking_class: `{summary['blocking_class']}`",
        f"- default_feature_mask: `{summary['default_feature_mask']}`",
        f"- core_target_count: `{summary['core_target_count']}`",
        f"- watchlist_target_count: `{summary['watchlist_target_count']}`",
        f"- additional_anchor_backed_target_count: `{summary['additional_anchor_backed_target_count']}`",
        f"- provisional_only_target_count: `{summary['provisional_only_target_count']}`",
        f"- same_scope_reproducibility_confirmed: `{summary['same_scope_reproducibility_confirmed']}`",
        f"- same_scope_processcheck_status: `{summary['same_scope_processcheck_status']}`",
        f"- page4_candidate_ready_now: `{summary['page4_candidate_ready_now']}`",
        f"- next_anchor_curation_target: `{summary['next_anchor_curation_target']}`",
        f"- would_change_state_count: `{summary['would_change_state_count']}`",
        f"- would_change_gate_count: `{summary['would_change_gate_count']}`",
        f"- would_change_llps_flag_count: `{summary['would_change_llps_flag_count']}`",
        f"- would_change_aggregation_flag_count: `{summary['would_change_aggregation_flag_count']}`",
        f"- latest_diagnostic_rule_name: `{summary['latest_diagnostic_rule_name']}`",
        f"- latest_diagnostic_observation: `{summary['latest_diagnostic_observation']}`",
        f"- latest_activation_rule_name: `{summary['latest_activation_rule_name']}`",
        f"- latest_activation_observation: `{summary['latest_activation_observation']}`",
        f"- latest_activation_status: `{summary['latest_activation_status']}`",
        f"- latest_activation_focus_condition_active_count: `{summary['latest_activation_focus_condition_active_count']}`",
        f"- latest_validation_status: `{summary['latest_validation_status']}`",
        "",
        "## Decision",
        "",
        f"- {summary['decision_reason']}",
        f"- {summary['blocker_reason']}",
        f"- {summary['non_cause_note']}",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a decision artifact from the completed IDP commercial-pretest run.")
    parser.add_argument("--holdout-summary-json", default=DEFAULT_HOLDOUT_SUMMARY_JSON)
    parser.add_argument("--combined-gate-json", default=DEFAULT_COMBINED_GATE_JSON)
    parser.add_argument("--corrected-eval-json", default=DEFAULT_CORRECTED_EVAL_JSON)
    parser.add_argument("--failure-packet-json", default=DEFAULT_FAILURE_PACKET_JSON)
    parser.add_argument("--pretest-packet-json", default=DEFAULT_PRETEST_PACKET_JSON)
    parser.add_argument("--diagnostic-result-json", default=DEFAULT_DIAGNOSTIC_RESULT_JSON)
    parser.add_argument("--activation-result-json", default=DEFAULT_ACTIVATION_RESULT_JSON)
    parser.add_argument("--validation-result-json", default=DEFAULT_VALIDATION_RESULT_JSON)
    parser.add_argument("--roster-viability-json", default=DEFAULT_ROSTER_VIABILITY_JSON)
    parser.add_argument("--same-scope-processcheck-result-json", default=DEFAULT_SAME_SCOPE_PROCESSCHECK_RESULT_JSON)
    parser.add_argument("--page4-promotion-review-json", default=DEFAULT_PAGE4_PROMOTION_REVIEW_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _read_json(args.holdout_summary_json),
        _read_json(args.combined_gate_json),
        _read_json(args.corrected_eval_json),
        _read_json(args.failure_packet_json),
        _read_json(args.pretest_packet_json),
        _read_json(args.diagnostic_result_json),
        _read_json(args.activation_result_json),
        _maybe_read_json(args.validation_result_json),
        _maybe_read_json(args.roster_viability_json),
        _maybe_read_json(args.same_scope_processcheck_result_json),
        _maybe_read_json(args.page4_promotion_review_json),
    )
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
