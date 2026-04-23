#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.operator_surface_contracts import (
    IDP_BLOCKED_SCOPE_BROADER_FULL_PROMOTION,
    IDP_SAFE_SCOPE_CONTROLLED_PRETEST,
    IDP_SAFE_SCOPE_LEGACY_SUBSET_ONLY,
)

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SUBSET_DECISION_JSON = "runs/idp_feature_state_subset_decision_current.json"
DEFAULT_PRETEST_SCOPE_JSON = "runs/idp_pretest_scope_note_current.json"
DEFAULT_BROADER_BLOCKER_JSON = "runs/idp_broader_promotion_blocker_note_current.json"
DEFAULT_KALMAN_PLAN_JSON = "runs/idp_kalman_feature_state_smoothing_plan_current.json"
DEFAULT_COMMERCIALIZATION_JSON = "runs/commercialization_readiness_current.json"
DEFAULT_BROADER_SCAFFOLD_JSON = "runs/idp_broader_anchor_shadow_scaffold_current.json"
DEFAULT_COMMERCIAL_PRETEST_PACKET_JSON = "runs/idp_commercial_pretest_packet_current.json"
DEFAULT_COMMERCIAL_PRETEST_DECISION_JSON = "runs/idp_commercial_pretest_decision_current.json"
DEFAULT_BROADER_SHADOW_RESULT_JSON = "runs/idp_broader_shadow_result_current.json"
DEFAULT_BROADER_SHADOW_DECISION_JSON = "runs/idp_broader_shadow_decision_current.json"
DEFAULT_BROADER_PROMOTION_RESOLUTION_JSON = "runs/idp_broader_promotion_resolution_current.json"
DEFAULT_ONE_WIDER_REPEATABILITY_PACKET_JSON = "runs/idp_one_wider_shadow_repeatability_packet_current.json"
DEFAULT_ONE_WIDER_REPEATABILITY_RESULT_JSON = "runs/idp_one_wider_shadow_repeatability_result_current.json"
DEFAULT_VALIDATION_RESULT_JSON = "runs/idp_commercial_pretest_validation_result_current.json"
DEFAULT_BROADER_REVIEW_PACKET_JSON = "runs/idp_broader_shadow_review_packet_current.json"
DEFAULT_BROADER_ROSTER_VIABILITY_JSON = "runs/idp_broader_anchor_roster_viability_packet_current.json"
DEFAULT_FAILURE_PACKET_JSON = "runs/idp_tau_k18_corrected_path_failure_packet_current.json"
DEFAULT_RESULT_JSON = "runs/tau_k18_stabilization_result_current.json"
DEFAULT_TWEAK_PACKET_JSON = "runs/tau_k18_corrected_path_tweak_packet_current.json"
DEFAULT_CONFIG_TUNING_DECISION_JSON = "runs/tau_k18_config_only_tuning_decision_current.json"
DEFAULT_ACTIVATION_PACKET_JSON = "runs/tau_k18_corrected_path_activation_packet_current.json"
DEFAULT_ACTIVATION_RESULT_JSON = "runs/tau_k18_corrected_path_activation_result_current.json"
DEFAULT_OUT_JSON = "runs/idp_commercialization_upgrade_plan_current.json"
DEFAULT_OUT_CSV = "runs/idp_commercialization_upgrade_plan_current.csv"
DEFAULT_OUT_MD = "runs/idp_commercialization_upgrade_plan_current.md"


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


def _maybe_load_json(path_like: str) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_payload(
    subset_decision: dict[str, Any],
    pretest_scope: dict[str, Any],
    broader_blocker: dict[str, Any],
    kalman_plan: dict[str, Any],
    commercialization: dict[str, Any],
    broader_scaffold: dict[str, Any] | None = None,
    commercial_pretest_packet: dict[str, Any] | None = None,
    commercial_pretest_decision: dict[str, Any] | None = None,
    validation_result: dict[str, Any] | None = None,
    failure_packet: dict[str, Any] | None = None,
    result_packet: dict[str, Any] | None = None,
    tweak_packet: dict[str, Any] | None = None,
    config_tuning_decision: dict[str, Any] | None = None,
    activation_packet: dict[str, Any] | None = None,
    activation_result: dict[str, Any] | None = None,
    broader_review_packet: dict[str, Any] | None = None,
    broader_roster_viability_packet: dict[str, Any] | None = None,
    broader_shadow_result: dict[str, Any] | None = None,
    broader_shadow_decision: dict[str, Any] | None = None,
    broader_promotion_resolution: dict[str, Any] | None = None,
    one_wider_repeatability_packet: dict[str, Any] | None = None,
    one_wider_repeatability_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    subset_s = dict(subset_decision.get("summary", {}) or {})
    pretest_s = dict(pretest_scope.get("summary", {}) or {})
    blocker_s = dict(broader_blocker.get("summary", {}) or {})
    kalman_s = dict(kalman_plan.get("summary", {}) or {})
    scaffold_s = dict((broader_scaffold or {}).get("summary", {}) or {})
    pretest_packet_s = dict((commercial_pretest_packet or {}).get("summary", {}) or {})
    pretest_decision_s = dict((commercial_pretest_decision or {}).get("summary", {}) or {})
    broader_result_s = dict((broader_shadow_result or {}).get("summary", {}) or {})
    broader_decision_s = dict((broader_shadow_decision or {}).get("summary", {}) or {})
    broader_promotion_resolution_s = dict((broader_promotion_resolution or {}).get("summary", {}) or {})
    one_wider_repeatability_packet_s = dict((one_wider_repeatability_packet or {}).get("summary", {}) or {})
    one_wider_repeatability_result_s = dict((one_wider_repeatability_result or {}).get("summary", {}) or {})
    one_wider_repeatability_s = one_wider_repeatability_result_s or one_wider_repeatability_packet_s
    validation_s = dict((validation_result or {}).get("summary", {}) or {})
    broader_review_s = dict((broader_review_packet or {}).get("summary", {}) or {})
    broader_roster_s = dict((broader_roster_viability_packet or {}).get("summary", {}) or {})
    additional_anchor_backed_target_count = int(broader_roster_s.get("additional_anchor_backed_target_count", 0) or 0)
    same_scope_reproducibility_confirmed = bool(pretest_decision_s.get("same_scope_reproducibility_confirmed", False))
    page4_candidate_ready_now = bool(pretest_decision_s.get("page4_candidate_ready_now", False))
    failure_packet_s = dict((failure_packet or {}).get("summary", {}) or {})
    result_s = dict((result_packet or {}).get("summary", {}) or {})
    tweak_s = dict((tweak_packet or {}).get("summary", {}) or {})
    config_tuning_s = dict((config_tuning_decision or {}).get("summary", {}) or {})
    activation_packet_s = dict((activation_packet or {}).get("summary", {}) or {})
    activation_result_s = dict((activation_result or {}).get("summary", {}) or {})
    commercial_rows = {str(row.get("family", "")).strip(): dict(row) for row in commercialization.get("rows", []) or []}
    idp_row = commercial_rows.get("idp", {})

    blocker_signal_bits = [
        str(pretest_decision_s.get("blocker_reason", "")).strip() or blocker_s.get("blocker_reason", ""),
        f"config_tuning_exhausted={config_tuning_s.get('config_only_force_policy_tuning_exhausted')}" if config_tuning_s else "",
        f"diagnostic_rule={blocker_s.get('current_diagnostic_rule', '')}" if blocker_s.get("current_diagnostic_rule") else "",
        f"diagnostic_status={blocker_s.get('current_diagnostic_status', '')}" if blocker_s.get("current_diagnostic_status") else "",
        f"diagnostic_observation={blocker_s.get('current_diagnostic_observation', '')}" if blocker_s.get("current_diagnostic_observation") else "",
        f"diagnostic_inactive_count={blocker_s.get('inactive_short_tau_diag_count')}" if blocker_s.get("inactive_short_tau_diag_count") is not None else "",
        f"debug_columns_present_count={blocker_s.get('debug_columns_present_count')}" if blocker_s.get("debug_columns_present_count") is not None else "",
        f"activation_rule={blocker_s.get('current_activation_rule', '')}" if blocker_s.get("current_activation_rule") else "",
        f"activation_status={blocker_s.get('current_activation_status', '')}" if blocker_s.get("current_activation_status") else "",
        f"activation_observation={blocker_s.get('current_activation_observation', '')}" if blocker_s.get("current_activation_observation") else "",
        f"activation_active_count={blocker_s.get('activation_focus_condition_active_count')}" if blocker_s.get("activation_focus_condition_active_count") is not None else "",
        f"validation_status={validation_s.get('status', '')}" if validation_s.get("status") else "",
        f"validation_tau_gate_pass={validation_s.get('tau_k18_corrected_gate_pass')}" if validation_s else "",
        f"current_calibration_rule={blocker_s.get('current_calibration_rule', '')}" if blocker_s.get("current_calibration_rule") else "",
        f"current_calibration_status={blocker_s.get('current_calibration_status', '')}" if blocker_s.get("current_calibration_status") else "",
        f"current_tweak_field={tweak_s.get('tweak_field', '')}" if tweak_s and not blocker_s.get("current_calibration_rule") and not blocker_s.get("current_diagnostic_rule") else "",
        (
            f"last_attempt_d_state_delta={blocker_s.get('last_calibration_dominant_state_accuracy_delta')}"
            if blocker_s.get("current_calibration_rule")
            else f"last_attempt_d_state_delta={result_s.get('dominant_state_accuracy_delta_vs_reference')}"
        ) if (blocker_s.get("current_calibration_rule") or result_s) else "",
        (
            f"last_attempt_d_agg_pr={blocker_s.get('last_calibration_aggregation_flag_pr_auc_delta')}"
            if blocker_s.get("current_calibration_rule")
            else f"last_attempt_d_agg_pr={result_s.get('aggregation_flag_pr_auc_delta_vs_reference')}"
        ) if (blocker_s.get("current_calibration_rule") or result_s) else "",
    ]

    rows = [
        {
            "milestone_rank": 1,
            "milestone_id": "preserve_subset_safe_baseline",
            "status": "done",
            "why_it_matters": "We already have a validated literature-anchor subset basis that should not regress while the current controlled commercial-pretest lane widens carefully.",
            "current_signal": f"corrected_pass_folds={subset_s.get('corrected_pass_folds', '')}/{subset_s.get('fold_count', '')}; mask={subset_s.get('default_feature_mask', '')}",
            "next_evidence_needed": "Maintain zero state/gate changes on any new anchor-backed shadow slice.",
        },
        {
            "milestone_rank": 2,
            "milestone_id": "expand_anchor_backed_shadow_coverage",
            "status": "open",
            "why_it_matters": "Commercialization needs broader representative IDP coverage than the validated subset basis, but that expansion still has to stay inside the current controlled commercial-pretest lane.",
            "current_signal": (
                f"legacy_note_scope={pretest_s.get('allowed_now', '') or IDP_SAFE_SCOPE_LEGACY_SUBSET_ONLY}; "
                f"operator_scope={IDP_SAFE_SCOPE_CONTROLLED_PRETEST}; "
                f"blocked_now={pretest_s.get('blocked_now', '') or IDP_BLOCKED_SCOPE_BROADER_FULL_PROMOTION}; "
                f"controlled_targets={scaffold_s.get('controlled_target_count', 0)}"
            ),
            "next_evidence_needed": "More controlled anchor-backed shadow slices with zero gate changes and no corrected-pass regression.",
        },
        {
            "milestone_rank": 3,
            "milestone_id": "complete_broader_shadow_review",
            "status": "done" if broader_result_s else "review_now" if broader_review_s else "blocked",
            "why_it_matters": "The bounded commercial-pretest lane is now clean, and the first broader shadow-only pass needs to be carried into an explicit promotion review instead of being treated as automatic widening.",
            "current_signal": " ; ".join(part for part in blocker_signal_bits if part),
            "next_evidence_needed": (
                "Use the completed broader-shadow result to reopen explicit promotion review while keeping broader_full_idp_promotion blocked."
                if broader_result_s else
                "Same-scope reproducibility is confirmed. Keep broader promotion blocked and move the next improvement to page4 quantitative anchor replacement before any true broader rerun."
                if broader_review_s and same_scope_reproducibility_confirmed and additional_anchor_backed_target_count == 0 and page4_candidate_ready_now
                else
                "Same-scope reproducibility is confirmed. Keep broader promotion blocked and move the next improvement to the page4 manual-confirmation console or another additional anchor-backed target before any true broader rerun."
                if broader_review_s and same_scope_reproducibility_confirmed and additional_anchor_backed_target_count == 0
                else
                "Freeze promotion policy, confirm that no additional anchor-backed targets exist yet, and choose explicitly between a same-scope process check or new anchor curation before any true broader rerun."
                if broader_review_s and additional_anchor_backed_target_count == 0
                else "Freeze promotion policy, broader anchor-backed target roster, guardrails, and success criteria in the broader-shadow review packet before any wider rerun."
            ),
        },
        {
            "milestone_rank": 4,
            "milestone_id": "promote_broader_full_idp_shadow",
            "status": "done" if broader_promotion_resolution_s else "review_now" if broader_result_s else "blocked" if additional_anchor_backed_target_count == 0 else "open" if broader_review_s else "blocked",
            "why_it_matters": "Commercial lane needs more than the validated subset basis and current controlled commercial-pretest lane.",
            "current_signal": (
                f"broader_full_idp_promotion={subset_s.get('broader_full_idp_promotion', '')}; "
                f"commercial_decision={broader_promotion_resolution_s.get('decision', broader_decision_s.get('decision', pretest_decision_s.get('decision', '')))}; "
                f"blocking_target={broader_promotion_resolution_s.get('blocking_target', broader_decision_s.get('blocking_target', pretest_decision_s.get('blocking_target', failure_packet_s.get('failure_anchor_target', ''))))}; "
                f"review_packet_status={broader_review_s.get('status', '')}; "
                f"broader_shadow_passed={broader_result_s.get('true_broader_shadow_passed', False)}; "
                f"additional_anchor_backed_target_count={additional_anchor_backed_target_count}"
            ),
            "next_evidence_needed": (
                "Run or monitor the admitted one-wider shadow-safe repeatability slice on the frozen 8-target roster before considering any further commercialization step."
                if broader_promotion_resolution_s and one_wider_repeatability_s else
                "Keep the admitted one-wider shadow-safe lane frozen to the validated 7-target scaffold plus PAGE4, and gather bounded operator evidence before considering any further commercialization step."
                if broader_promotion_resolution_s else
                "Run the explicit promotion review over the completed broader-shadow pass and decide whether one wider shadow-safe lane should be admitted without changing the no-override guardrails."
                if broader_result_s else
                "Complete page4 quantitative anchor replacement so page4 can count as the first additional anchor-backed target, then run one true broader full-IDP shadow rerun with the same no-override guardrails."
                if additional_anchor_backed_target_count == 0 and page4_candidate_ready_now
                else
                "At least one additional anchor-backed target beyond the current validated 7-target scaffold, then one true broader full-IDP shadow rerun with the same no-override guardrails."
                if additional_anchor_backed_target_count == 0
                else "One broader full-IDP shadow rerun with the same no-override guardrails, zero state/gate changes, and no corrected-pass regression against the clean bounded commercial-pretest run."
            ),
        },
        {
            "milestone_rank": 5,
            "milestone_id": "package_idp_as_commercial_endpoint",
            "status": "blocked",
            "why_it_matters": "To reach commercial-lane status, IDP needs a repeatable bounded offering rather than a one-off validated subset basis plus controlled pretest lane.",
            "current_signal": (
                f"current_stage={idp_row.get('stage', '')}; "
                f"current_status={broader_promotion_resolution_s.get('status', idp_row.get('status', ''))}; "
                f"repeatability_status={one_wider_repeatability_s.get('status', '')}"
            ),
            "next_evidence_needed": (
                "Confirm bounded repeatability on the admitted one-wider shadow-safe lane before reopening any larger commercialization boundary."
                if one_wider_repeatability_s and str(one_wider_repeatability_s.get("status", "")).strip() != "one_wider_shadow_repeatability_confirmed"
                else "A broader, repeatable shadow-safe endpoint definition with operator guardrails and preserved non-regression behavior."
            ),
        },
    ]

    summary = {
        "current_score": idp_row.get("score", ""),
        "current_stage": idp_row.get("stage", ""),
        "current_status": broader_promotion_resolution_s.get("status", idp_row.get("status", "")),
        "current_safe_scope": (
            "one wider shadow-safe lane admitted on the frozen validated-7-plus-PAGE4 roster under the same no-override guardrails"
            if broader_promotion_resolution_s
            else idp_row.get("claim_safe_scope", "")
        ),
        "commercialization_target": "broader_idp_commercial_lane",
        "done_count": sum(1 for row in rows if row["status"] == "done"),
        "open_count": sum(1 for row in rows if row["status"] == "open"),
        "blocked_count": sum(1 for row in rows if row["status"] == "blocked"),
        "default_feature_mask": kalman_s.get("default_feature_mask", subset_s.get("default_feature_mask", "")),
        "broader_anchor_scaffold_ready": bool(scaffold_s),
        "broader_anchor_scaffold_target_count": scaffold_s.get("controlled_target_count", 0),
        "broader_anchor_scaffold_core_count": scaffold_s.get("commercial_pretest_core_count", 0),
        "broader_anchor_scaffold_watchlist_count": scaffold_s.get("commercial_pretest_watchlist_count", 0),
        "commercial_pretest_packet_ready": bool(pretest_packet_s),
        "commercial_pretest_packet_target_count": pretest_packet_s.get("row_count", 0),
        "commercial_pretest_decision_ready": bool(pretest_decision_s),
        "broader_shadow_result_ready": bool(broader_result_s),
        "broader_shadow_decision_ready": bool(broader_decision_s),
        "broader_promotion_resolution_ready": bool(broader_promotion_resolution_s),
        "one_wider_repeatability_packet_ready": bool(one_wider_repeatability_packet_s),
        "one_wider_repeatability_result_ready": bool(one_wider_repeatability_result_s),
        "validation_result_ready": bool(validation_s),
        "broader_shadow_review_packet_ready": bool(broader_review_s),
        "broader_shadow_review_item_count": broader_review_s.get("review_item_count", 0),
        "broader_roster_viability_ready": bool(broader_roster_s),
        "additional_anchor_backed_target_count": additional_anchor_backed_target_count,
        "activation_packet_ready": bool(activation_packet_s),
        "activation_result_ready": bool(activation_result_s),
        "next_required_step": (
            str(one_wider_repeatability_s.get("next_required_step", "")).strip()
            or
            str(broader_promotion_resolution_s.get("next_required_step", "")).strip()
            or
            str(broader_decision_s.get("next_required_step", "")).strip()
            or
            str(broader_review_s.get("next_required_step", "")).strip()
            or
            str(blocker_s.get("next_required_step", "")).strip()
            or
            str(config_tuning_s.get("next_required_step", "")).strip()
            or
            str(pretest_decision_s.get("next_required_step", "")).strip()
            or "Keep rg_sasa_only as the safe default, preserve the validated literature-anchor subset basis, keep the current operator lane bounded to controlled commercial-pretest, use the commercial-pretest packet and broader-anchor scaffold to widen coverage, fix corrected-path fragility, then retry broader full-IDP shadow promotion before talking about an IDP commercial lane."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Commercialization Upgrade Plan",
        "",
        f"- current_score: `{s['current_score']}`",
        f"- current_stage: `{s['current_stage']}`",
        f"- current_status: `{s['current_status']}`",
        f"- current_safe_scope: `{s['current_safe_scope']}`",
        f"- commercialization_target: `{s['commercialization_target']}`",
        f"- done_count: `{s['done_count']}`",
        f"- open_count: `{s['open_count']}`",
        f"- blocked_count: `{s['blocked_count']}`",
        f"- default_feature_mask: `{s['default_feature_mask']}`",
        f"- broader_anchor_scaffold_ready: `{s['broader_anchor_scaffold_ready']}`",
        f"- broader_anchor_scaffold_target_count: `{s['broader_anchor_scaffold_target_count']}`",
        f"- broader_anchor_scaffold_core_count: `{s['broader_anchor_scaffold_core_count']}`",
        f"- broader_anchor_scaffold_watchlist_count: `{s['broader_anchor_scaffold_watchlist_count']}`",
        f"- commercial_pretest_packet_ready: `{s['commercial_pretest_packet_ready']}`",
        f"- commercial_pretest_packet_target_count: `{s['commercial_pretest_packet_target_count']}`",
        f"- commercial_pretest_decision_ready: `{s['commercial_pretest_decision_ready']}`",
        f"- broader_shadow_result_ready: `{s['broader_shadow_result_ready']}`",
        f"- broader_shadow_decision_ready: `{s['broader_shadow_decision_ready']}`",
        f"- broader_promotion_resolution_ready: `{s['broader_promotion_resolution_ready']}`",
        f"- one_wider_repeatability_packet_ready: `{s['one_wider_repeatability_packet_ready']}`",
        f"- one_wider_repeatability_result_ready: `{s['one_wider_repeatability_result_ready']}`",
        f"- validation_result_ready: `{s['validation_result_ready']}`",
        f"- broader_shadow_review_packet_ready: `{s['broader_shadow_review_packet_ready']}`",
        f"- broader_shadow_review_item_count: `{s['broader_shadow_review_item_count']}`",
        f"- broader_roster_viability_ready: `{s['broader_roster_viability_ready']}`",
        f"- additional_anchor_backed_target_count: `{s['additional_anchor_backed_target_count']}`",
        f"- activation_packet_ready: `{s['activation_packet_ready']}`",
        f"- activation_result_ready: `{s['activation_result_ready']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Milestones",
        "",
        "| milestone_rank | milestone_id | status | why_it_matters | current_signal | next_evidence_needed |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['milestone_rank']} | `{row['milestone_id']}` | `{row['status']}` | {row['why_it_matters']} | `{row['current_signal']}` | {row['next_evidence_needed']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a concrete commercialization-upgrade roadmap for IDP.")
    parser.add_argument("--subset-decision-json", default=DEFAULT_SUBSET_DECISION_JSON)
    parser.add_argument("--pretest-scope-json", default=DEFAULT_PRETEST_SCOPE_JSON)
    parser.add_argument("--broader-blocker-json", default=DEFAULT_BROADER_BLOCKER_JSON)
    parser.add_argument("--kalman-plan-json", default=DEFAULT_KALMAN_PLAN_JSON)
    parser.add_argument("--commercialization-json", default=DEFAULT_COMMERCIALIZATION_JSON)
    parser.add_argument("--broader-scaffold-json", default=DEFAULT_BROADER_SCAFFOLD_JSON)
    parser.add_argument("--commercial-pretest-packet-json", default=DEFAULT_COMMERCIAL_PRETEST_PACKET_JSON)
    parser.add_argument("--commercial-pretest-decision-json", default=DEFAULT_COMMERCIAL_PRETEST_DECISION_JSON)
    parser.add_argument("--broader-shadow-result-json", default=DEFAULT_BROADER_SHADOW_RESULT_JSON)
    parser.add_argument("--broader-shadow-decision-json", default=DEFAULT_BROADER_SHADOW_DECISION_JSON)
    parser.add_argument("--broader-promotion-resolution-json", default=DEFAULT_BROADER_PROMOTION_RESOLUTION_JSON)
    parser.add_argument("--one-wider-repeatability-packet-json", default=DEFAULT_ONE_WIDER_REPEATABILITY_PACKET_JSON)
    parser.add_argument("--one-wider-repeatability-result-json", default=DEFAULT_ONE_WIDER_REPEATABILITY_RESULT_JSON)
    parser.add_argument("--validation-result-json", default=DEFAULT_VALIDATION_RESULT_JSON)
    parser.add_argument("--broader-review-packet-json", default=DEFAULT_BROADER_REVIEW_PACKET_JSON)
    parser.add_argument("--broader-roster-viability-json", default=DEFAULT_BROADER_ROSTER_VIABILITY_JSON)
    parser.add_argument("--failure-packet-json", default=DEFAULT_FAILURE_PACKET_JSON)
    parser.add_argument("--result-json", default=DEFAULT_RESULT_JSON)
    parser.add_argument("--tweak-packet-json", default=DEFAULT_TWEAK_PACKET_JSON)
    parser.add_argument("--config-tuning-decision-json", default=DEFAULT_CONFIG_TUNING_DECISION_JSON)
    parser.add_argument("--activation-packet-json", default=DEFAULT_ACTIVATION_PACKET_JSON)
    parser.add_argument("--activation-result-json", default=DEFAULT_ACTIVATION_RESULT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.subset_decision_json),
        _load_json(args.pretest_scope_json),
        _load_json(args.broader_blocker_json),
        _load_json(args.kalman_plan_json),
        _load_json(args.commercialization_json),
        _load_json(args.broader_scaffold_json),
        _load_json(args.commercial_pretest_packet_json),
        _maybe_load_json(args.commercial_pretest_decision_json),
        _maybe_load_json(args.validation_result_json),
        _maybe_load_json(args.failure_packet_json),
        _maybe_load_json(args.result_json),
        _maybe_load_json(args.tweak_packet_json),
        _maybe_load_json(args.config_tuning_decision_json),
        _maybe_load_json(args.activation_packet_json),
        _maybe_load_json(args.activation_result_json),
        _maybe_load_json(args.broader_review_packet_json),
        _maybe_load_json(args.broader_roster_viability_json),
        _maybe_load_json(args.broader_shadow_result_json),
        _maybe_load_json(args.broader_shadow_decision_json),
        _maybe_load_json(args.broader_promotion_resolution_json),
        _maybe_load_json(args.one_wider_repeatability_packet_json),
        _maybe_load_json(args.one_wider_repeatability_result_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
