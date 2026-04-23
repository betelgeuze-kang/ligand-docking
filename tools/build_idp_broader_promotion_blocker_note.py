#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.operator_surface_contracts import IDP_SAFE_SCOPE_CONTROLLED_PRETEST

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUBSET_DECISION_JSON = "runs/idp_feature_state_subset_decision_current.json"
DEFAULT_COMMERCIAL_PRETEST_DECISION_JSON = "runs/idp_commercial_pretest_decision_current.json"
DEFAULT_BROADER_SHADOW_RESULT_JSON = "runs/idp_broader_shadow_result_current.json"
DEFAULT_BROADER_SHADOW_DECISION_JSON = "runs/idp_broader_shadow_decision_current.json"
DEFAULT_BROADER_PROMOTION_RESOLUTION_JSON = "runs/idp_broader_promotion_resolution_current.json"
DEFAULT_FAILURE_PACKET_JSON = "runs/idp_tau_k18_corrected_path_failure_packet_current.json"
DEFAULT_RESULT_JSON = "runs/tau_k18_stabilization_result_current.json"
DEFAULT_TWEAK_PACKET_JSON = "runs/tau_k18_corrected_path_tweak_packet_current.json"
DEFAULT_CONFIG_TUNING_DECISION_JSON = "runs/tau_k18_config_only_tuning_decision_current.json"
DEFAULT_CALIBRATION_PACKET_JSON = "runs/tau_k18_full_fold_corrected_calibration_packet_current.json"
DEFAULT_CALIBRATION_RESULT_JSON = "runs/tau_k18_full_fold_corrected_calibration_result_current.json"
DEFAULT_DIAGNOSTIC_PACKET_JSON = "runs/tau_k18_corrected_path_diagnostic_packet_current.json"
DEFAULT_DIAGNOSTIC_RESULT_JSON = "runs/tau_k18_corrected_path_diagnostic_result_current.json"
DEFAULT_ACTIVATION_PACKET_JSON = "runs/tau_k18_corrected_path_activation_packet_current.json"
DEFAULT_ACTIVATION_RESULT_JSON = "runs/tau_k18_corrected_path_activation_result_current.json"
DEFAULT_VALIDATION_RESULT_JSON = "runs/idp_commercial_pretest_validation_result_current.json"
DEFAULT_OUT_JSON = "runs/idp_broader_promotion_blocker_note_current.json"
DEFAULT_OUT_MD = "runs/idp_broader_promotion_blocker_note_current.md"


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


def build_payload(
    subset_decision: dict[str, Any],
    commercial_pretest_decision: dict[str, Any] | None = None,
    failure_packet: dict[str, Any] | None = None,
    result_packet: dict[str, Any] | None = None,
    tweak_packet: dict[str, Any] | None = None,
    config_tuning_decision: dict[str, Any] | None = None,
    calibration_packet: dict[str, Any] | None = None,
    calibration_result: dict[str, Any] | None = None,
    diagnostic_packet: dict[str, Any] | None = None,
    diagnostic_result: dict[str, Any] | None = None,
    activation_packet: dict[str, Any] | None = None,
    activation_result: dict[str, Any] | None = None,
    validation_result: dict[str, Any] | None = None,
    broader_shadow_result: dict[str, Any] | None = None,
    broader_shadow_decision: dict[str, Any] | None = None,
    broader_promotion_resolution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    s = dict(subset_decision.get("summary", {}) or {})
    d = dict((commercial_pretest_decision or {}).get("summary", {}) or {})
    br = dict((broader_shadow_result or {}).get("summary", {}) or {})
    bd = dict((broader_shadow_decision or {}).get("summary", {}) or {})
    pr = dict((broader_promotion_resolution or {}).get("summary", {}) or {})
    f = dict((failure_packet or {}).get("summary", {}) or {})
    r = dict((result_packet or {}).get("summary", {}) or {})
    t = dict((tweak_packet or {}).get("summary", {}) or {})
    c = dict((config_tuning_decision or {}).get("summary", {}) or {})
    cp = dict((calibration_packet or {}).get("summary", {}) or {})
    cr = dict((calibration_result or {}).get("summary", {}) or {})
    dp = dict((diagnostic_packet or {}).get("summary", {}) or {})
    dr = dict((diagnostic_result or {}).get("summary", {}) or {})
    ap = dict((activation_packet or {}).get("summary", {}) or {})
    ar = dict((activation_result or {}).get("summary", {}) or {})
    vr = dict((validation_result or {}).get("summary", {}) or {})
    has_active_calibration = bool(
        str(cp.get("candidate_rule_name", cr.get("candidate_rule_name", ""))).strip()
        or str(cr.get("status", cp.get("status", ""))).strip()
    )
    has_comparable_calibration = bool(cr.get("comparable_to_official_failure_slice", False))
    has_active_diagnostic = bool(
        str(dp.get("diagnostic_rule_name", dr.get("diagnostic_rule_name", ""))).strip()
        or str(dr.get("status", dp.get("status", ""))).strip()
    )
    has_active_activation = bool(
        str(ap.get("activation_rule_name", ar.get("activation_rule_name", ""))).strip()
        or str(ar.get("status", ap.get("status", ""))).strip()
    )

    blocker_reason = str(
        pr.get(
            "blocker_reason",
            bd.get(
            "blocker_reason",
            c.get(
            "blocker_reason",
            f.get(
                "blocker_reason",
                d.get(
                    "blocker_reason",
                    s.get(
                        "blocking_reason",
                        "Broader full-IDP promotion remains blocked until corrected-path and provisional-anchor risks are reduced.",
                    ),
                ),
            ),
        )))
    )
    if r and not c:
        blocker_reason = (
            f"{blocker_reason} The most recent corrected-path-only comparison left dominant-state accuracy at "
            f"{r.get('fallback_corrected_dominant_state_accuracy')} while only nudging aggregation_flag_pr_auc by "
            f"{r.get('aggregation_flag_pr_auc_delta_vs_reference')}."
        ).strip()
    if cr and not dr:
        blocker_reason = (
            f"{blocker_reason} The {cr.get('candidate_rule_name', 'latest calibration')} slice left dominant-state accuracy at "
            f"{cr.get('calibration_dominant_state_accuracy')} with aggregation_flag_pr_auc delta "
            f"{cr.get('aggregation_flag_pr_auc_delta')}."
        ).strip()
    if dr:
        blocker_reason = (
            f"{blocker_reason} The latest base/ph_low observability-only slice "
            f"({dr.get('diagnostic_rule_name', 'tau_k18 diagnostic')}) emitted tau_k18_diag_* columns on "
            f"{dr.get('debug_columns_present_count', 0)}/{dr.get('focus_condition_count', 0)} focus rows and observed "
            f"`{dr.get('primary_observation', '')}`."
        ).strip()
    if ar:
        blocker_reason = (
            f"{blocker_reason} A follow-up activation-check slice "
            f"({ar.get('activation_rule_name', 'short_tau activation')}) then activated the short-tau path on "
            f"{ar.get('focus_condition_active_count', 0)}/{ar.get('focus_condition_count', 0)} focus rows and "
            f"locally passed the corrected gate."
        ).strip()
    if vr:
        blocker_reason = (
            f"{blocker_reason} A bounded commercial-pretest rerun then finished with "
            f"corrected_pass_folds={vr.get('corrected_pass_folds')}/{vr.get('fold_count')} and "
            f"tau_k18_corrected_gate_pass={vr.get('tau_k18_corrected_gate_pass')}."
        ).strip()
    if has_comparable_calibration:
        blocker_reason = (
            f"{blocker_reason} A follow-up comparable full-fold calibration slice "
            f"({cr.get('candidate_rule_name', 'latest comparable calibration')}) then restored label parity, "
            f"improved dominant-state accuracy to {cr.get('calibration_dominant_state_accuracy')}, and left "
            f"remaining_aggregation_mismatch_count={cr.get('remaining_aggregation_mismatch_count')} with "
            f"calibration_corrected_gate_pass={cr.get('calibration_corrected_gate_pass')}."
        ).strip()

    summary = {
        "broader_promotion_blocked": bool(pr.get("broader_promotion_blocked", bd.get("broader_promotion_blocked", d.get("broader_promotion_blocked", True)))) if (pr or bd or d) else not bool(s.get("broader_full_idp_promotion", False)),
        "subset_safe_scope": "literature_anchor_subset_rg_sasa_only",
        "operator_scope_now": str(pr.get("operator_scope_now", bd.get("operator_scope_now", d.get("operator_scope_now", "")))) or IDP_SAFE_SCOPE_CONTROLLED_PRETEST,
        "shadow_safe_retained": bool(pr.get("shadow_safe_retained", bd.get("shadow_safe_retained", d.get("shadow_safe_retained", False)))) if (pr or bd or d) else False,
        "blocker_reason": blocker_reason,
        "broader_shadow_completed": bool(br.get("true_broader_shadow_completed", False)),
        "broader_shadow_passed": bool(br.get("true_broader_shadow_passed", False)),
        "wider_shadow_safe_lane_admitted": bool(pr.get("wider_shadow_safe_lane_admitted", False)),
        "page4_fold_pass": bool(br.get("page4_fold_pass", False)),
        "tau_k18_fold_pass": bool(br.get("tau_k18_fold_pass", False)),
        "current_diagnostic_rule": str(dp.get("diagnostic_rule_name", dr.get("diagnostic_rule_name", ""))).strip(),
        "current_diagnostic_status": str(dr.get("status", dp.get("status", ""))).strip(),
        "current_diagnostic_observation": str(dr.get("primary_observation", "")).strip(),
        "debug_columns_present_count": dr.get("debug_columns_present_count"),
        "inactive_short_tau_diag_count": dr.get("inactive_short_tau_diag_count"),
        "current_activation_rule": str(ap.get("activation_rule_name", ar.get("activation_rule_name", ""))).strip(),
        "current_activation_status": str(ar.get("status", ap.get("status", ""))).strip(),
        "current_activation_observation": str(ar.get("primary_observation", "")).strip(),
        "activation_focus_condition_active_count": ar.get("focus_condition_active_count"),
        "validation_status": str(vr.get("status", "")).strip(),
        "current_calibration_rule": (
            str(cp.get("candidate_rule_name", cr.get("candidate_rule_name", ""))).strip()
            if has_comparable_calibration or (not has_active_diagnostic and not has_active_activation)
            else ""
        ),
        "current_calibration_status": (
            str(cr.get("status", cp.get("status", ""))).strip()
            if has_comparable_calibration or (not has_active_diagnostic and not has_active_activation)
            else ""
        ),
        "last_calibration_dominant_state_accuracy_delta": (
            cr.get("dominant_state_accuracy_delta")
            if has_comparable_calibration or (not has_active_diagnostic and not has_active_activation)
            else None
        ),
        "last_calibration_aggregation_flag_pr_auc_delta": (
            cr.get("aggregation_flag_pr_auc_delta")
            if has_comparable_calibration or (not has_active_diagnostic and not has_active_activation)
            else None
        ),
        "current_tweak_field": "" if has_active_calibration or has_active_diagnostic or has_active_activation else str(t.get("tweak_field", "")).strip(),
        "current_tweak_status": "" if has_active_calibration or has_active_diagnostic or has_active_activation else str(t.get("status", "")).strip(),
        "last_attempt_dominant_state_accuracy_delta": r.get("dominant_state_accuracy_delta_vs_reference"),
        "last_attempt_aggregation_flag_pr_auc_delta": r.get("aggregation_flag_pr_auc_delta_vs_reference"),
        "config_only_force_policy_tuning_exhausted": bool(c.get("config_only_force_policy_tuning_exhausted", False)),
        "next_required_step": str(
            pr.get(
                "next_required_step",
                bd.get(
                "next_required_step",
                br.get(
                    "next_required_step",
                    vr.get(
                        "next_required_step",
                        cr.get(
                            "next_required_step",
                            ar.get(
                                "next_required_step",
                                dr.get(
                                    "next_required_step",
                                    c.get(
                                        "next_required_step",
                                        d.get(
                                            "next_required_step",
                                            s.get(
                                                "next_required_step",
                                                "Keep broader promotion blocked. Only expand to the next controlled shadow-only slice after maintaining zero state/gate changes and no corrected-pass regression.",
                                            ),
                                        ),
                                    ),
                                ),
                            ),
                        ),
                    ),
                )),
            )
        ),
    }
    return {"summary": summary}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Broader Promotion Blocker Note",
        "",
        f"- broader_promotion_blocked: `{s['broader_promotion_blocked']}`",
        f"- subset_safe_scope: `{s['subset_safe_scope']}`",
        f"- operator_scope_now: `{s['operator_scope_now']}`",
        f"- shadow_safe_retained: `{s['shadow_safe_retained']}`",
        f"- broader_shadow_completed: `{s['broader_shadow_completed']}`",
        f"- broader_shadow_passed: `{s['broader_shadow_passed']}`",
        f"- wider_shadow_safe_lane_admitted: `{s['wider_shadow_safe_lane_admitted']}`",
        f"- page4_fold_pass: `{s['page4_fold_pass']}`",
        f"- tau_k18_fold_pass: `{s['tau_k18_fold_pass']}`",
        f"- current_diagnostic_rule: `{s['current_diagnostic_rule']}`",
        f"- current_diagnostic_status: `{s['current_diagnostic_status']}`",
        f"- current_diagnostic_observation: `{s['current_diagnostic_observation']}`",
        f"- debug_columns_present_count: `{s['debug_columns_present_count']}`",
        f"- inactive_short_tau_diag_count: `{s['inactive_short_tau_diag_count']}`",
        f"- current_activation_rule: `{s['current_activation_rule']}`",
        f"- current_activation_status: `{s['current_activation_status']}`",
        f"- current_activation_observation: `{s['current_activation_observation']}`",
        f"- activation_focus_condition_active_count: `{s['activation_focus_condition_active_count']}`",
        f"- validation_status: `{s['validation_status']}`",
        f"- current_calibration_rule: `{s['current_calibration_rule']}`",
        f"- current_calibration_status: `{s['current_calibration_status']}`",
        f"- last_calibration_dominant_state_accuracy_delta: `{s['last_calibration_dominant_state_accuracy_delta']}`",
        f"- last_calibration_aggregation_flag_pr_auc_delta: `{s['last_calibration_aggregation_flag_pr_auc_delta']}`",
    ]
    if s["current_tweak_field"]:
        lines.append(f"- current_tweak_field: `{s['current_tweak_field']}`")
    if s["current_tweak_status"]:
        lines.append(f"- current_tweak_status: `{s['current_tweak_status']}`")
    lines.extend([
        f"- last_attempt_dominant_state_accuracy_delta: `{s['last_attempt_dominant_state_accuracy_delta']}`",
        f"- last_attempt_aggregation_flag_pr_auc_delta: `{s['last_attempt_aggregation_flag_pr_auc_delta']}`",
        f"- config_only_force_policy_tuning_exhausted: `{s['config_only_force_policy_tuning_exhausted']}`",
        "",
        s["blocker_reason"],
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an operator-facing blocker note for broader IDP promotion.")
    parser.add_argument("--subset-decision-json", default=DEFAULT_SUBSET_DECISION_JSON)
    parser.add_argument("--commercial-pretest-decision-json", default=DEFAULT_COMMERCIAL_PRETEST_DECISION_JSON)
    parser.add_argument("--broader-shadow-result-json", default=DEFAULT_BROADER_SHADOW_RESULT_JSON)
    parser.add_argument("--broader-shadow-decision-json", default=DEFAULT_BROADER_SHADOW_DECISION_JSON)
    parser.add_argument("--failure-packet-json", default=DEFAULT_FAILURE_PACKET_JSON)
    parser.add_argument("--result-json", default=DEFAULT_RESULT_JSON)
    parser.add_argument("--tweak-packet-json", default=DEFAULT_TWEAK_PACKET_JSON)
    parser.add_argument("--config-tuning-decision-json", default=DEFAULT_CONFIG_TUNING_DECISION_JSON)
    parser.add_argument("--calibration-packet-json", default=DEFAULT_CALIBRATION_PACKET_JSON)
    parser.add_argument("--calibration-result-json", default=DEFAULT_CALIBRATION_RESULT_JSON)
    parser.add_argument("--diagnostic-packet-json", default=DEFAULT_DIAGNOSTIC_PACKET_JSON)
    parser.add_argument("--diagnostic-result-json", default=DEFAULT_DIAGNOSTIC_RESULT_JSON)
    parser.add_argument("--activation-packet-json", default=DEFAULT_ACTIVATION_PACKET_JSON)
    parser.add_argument("--activation-result-json", default=DEFAULT_ACTIVATION_RESULT_JSON)
    parser.add_argument("--validation-result-json", default=DEFAULT_VALIDATION_RESULT_JSON)
    parser.add_argument("--broader-promotion-resolution-json", default=DEFAULT_BROADER_PROMOTION_RESOLUTION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.subset_decision_json),
        _maybe_load_json(args.commercial_pretest_decision_json),
        _maybe_load_json(args.failure_packet_json),
        _maybe_load_json(args.result_json),
        _maybe_load_json(args.tweak_packet_json),
        _maybe_load_json(args.config_tuning_decision_json),
        _maybe_load_json(args.calibration_packet_json),
        _maybe_load_json(args.calibration_result_json),
        _maybe_load_json(args.diagnostic_packet_json),
        _maybe_load_json(args.diagnostic_result_json),
        _maybe_load_json(args.activation_packet_json),
        _maybe_load_json(args.activation_result_json),
        _maybe_load_json(args.validation_result_json),
        _maybe_load_json(args.broader_shadow_result_json),
        _maybe_load_json(args.broader_shadow_decision_json),
        _maybe_load_json(args.broader_promotion_resolution_json),
    )
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
