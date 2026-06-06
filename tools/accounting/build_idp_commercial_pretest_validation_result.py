#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_HOLDOUT_SUMMARY_JSON = "runs/idp_3bead_holdout_v7_anchor_commercial_pretest_r18validation_r1_summary.json"
DEFAULT_COMBINED_GATE_JSON = "runs/idp_3bead_holdout_v7_anchor_commercial_pretest_r18validation_r1_combined_gate_summary.json"
DEFAULT_CORRECTED_EVAL_JSON = "runs/idp_3bead_holdout_v7_anchor_commercial_pretest_r18validation_r1_corrected_eval_summary.json"
DEFAULT_TAU_GATE_JSON = "runs/idp_3bead_holdout_v7_anchor_commercial_pretest_r18validation_r1_fold6_tau_k18_gate_corrected_summary.json"
DEFAULT_ACTIVATION_RESULT_JSON = "runs/tau_k18_full_fold_corrected_calibration_result_current.json"
DEFAULT_OUT_JSON = "runs/idp_commercial_pretest_validation_result_current.json"
DEFAULT_OUT_MD = "runs/idp_commercial_pretest_validation_result_current.md"


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


def build_payload(
    holdout_summary: dict[str, Any],
    combined_gate_summary: dict[str, Any],
    corrected_eval_summary: dict[str, Any],
    tau_gate_summary: dict[str, Any],
    activation_result: dict[str, Any],
) -> dict[str, Any]:
    holdout_s = dict(holdout_summary or {})
    combined_s = dict(combined_gate_summary or {})
    corrected_s = dict(corrected_eval_summary or {})
    tau_gate_s = dict(tau_gate_summary or {})
    activation_s = dict((activation_result.get("summary", {}) if isinstance(activation_result.get("summary", {}), dict) else {}) or {})
    kalman_s = dict((corrected_s.get("kalman_shadow", {}) if isinstance(corrected_s.get("kalman_shadow", {}), dict) else {}) or {})
    tau_cls = dict((tau_gate_s.get("classification_metrics") or {}) or {})

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
    activation_active = bool(
        activation_s.get("calibration_corrected_gate_pass", False)
        or str(activation_s.get("primary_observation", "")).strip() == "short_tau_diagnostic_path_activated_on_focus_rows"
    )
    tau_gate_pass = bool(tau_gate_s.get("pass", False))

    if shadow_safe_retained and activation_active and not tau_gate_pass:
        status = "bounded_commercial_pretest_completed_blocker_persists_activation_retained"
        next_required_step = (
            "Keep broader_full_idp_promotion blocked, keep controlled_shadow_only_commercial_pretest unchanged, "
            "and use the tau_k18 full-fold corrected failure slice to choose exactly one next corrected-path interpretation or calibration rule."
        )
    elif shadow_safe_retained and activation_active:
        status = "bounded_commercial_pretest_completed_activation_retained"
        next_required_step = (
            "Keep broader_full_idp_promotion blocked for now, do not call the next IDP run a true broader rerun yet, "
            "and either approve one same-scope process check on the validated 7-target literature-anchor subset or curate at least one additional anchor-backed target first."
        )
    else:
        status = "bounded_commercial_pretest_completed_activation_not_confirmed"
        next_required_step = (
            "Keep broader_full_idp_promotion blocked, keep controlled_shadow_only_commercial_pretest unchanged, and inspect why the expected activation did not persist on the bounded rerun."
        )

    summary = {
        "status": status,
        "operator_scope_now": "controlled_shadow_only_commercial_pretest",
        "shadow_safe_retained": shadow_safe_retained,
        "broader_promotion_blocked": True,
        "fold_count": fold_count,
        "corrected_pass_folds": corrected_pass_folds,
        "combined_gate_pass": bool(holdout_s.get("combined_gate_pass", combined_s.get("pass", False))),
        "blocking_target": "tau_k18",
        "blocking_class": "corrected_path_fragility",
        "default_feature_mask": str(kalman_s.get("feature_mask_name", "rg_sasa_only")).strip(),
        "activation_rule_name": str(activation_s.get("activation_rule_name", "")).strip(),
        "calibration_rule_name": str(activation_s.get("candidate_rule_name", "")).strip(),
        "activation_status": str(activation_s.get("status", "")).strip(),
        "activation_observation": str(activation_s.get("primary_observation", "")).strip(),
        "tau_k18_corrected_gate_pass": tau_gate_pass,
        "tau_k18_dominant_state_accuracy": tau_cls.get("dominant_state_accuracy"),
        "tau_k18_aggregation_flag_pr_auc": tau_cls.get("aggregation_flag_pr_auc"),
        "would_change_state_count": would_change_state_count,
        "would_change_gate_count": would_change_gate_count,
        "would_change_llps_flag_count": would_change_llps_flag_count,
        "would_change_aggregation_flag_count": would_change_aggregation_flag_count,
        "next_required_step": next_required_step,
    }
    return {"summary": summary}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Commercial Pretest Validation Result",
        "",
        f"- status: `{s['status']}`",
        f"- operator_scope_now: `{s['operator_scope_now']}`",
        f"- shadow_safe_retained: `{s['shadow_safe_retained']}`",
        f"- broader_promotion_blocked: `{s['broader_promotion_blocked']}`",
        f"- fold_count: `{s['fold_count']}`",
        f"- corrected_pass_folds: `{s['corrected_pass_folds']}`",
        f"- combined_gate_pass: `{s['combined_gate_pass']}`",
        f"- blocking_target: `{s['blocking_target']}`",
        f"- blocking_class: `{s['blocking_class']}`",
        f"- default_feature_mask: `{s['default_feature_mask']}`",
        f"- activation_rule_name: `{s['activation_rule_name']}`",
        f"- calibration_rule_name: `{s['calibration_rule_name']}`",
        f"- activation_status: `{s['activation_status']}`",
        f"- activation_observation: `{s['activation_observation']}`",
        f"- tau_k18_corrected_gate_pass: `{s['tau_k18_corrected_gate_pass']}`",
        f"- tau_k18_dominant_state_accuracy: `{s['tau_k18_dominant_state_accuracy']}`",
        f"- tau_k18_aggregation_flag_pr_auc: `{s['tau_k18_aggregation_flag_pr_auc']}`",
        f"- would_change_state_count: `{s['would_change_state_count']}`",
        f"- would_change_gate_count: `{s['would_change_gate_count']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the bounded IDP commercial-pretest validation result.")
    parser.add_argument("--holdout-summary-json", default=DEFAULT_HOLDOUT_SUMMARY_JSON)
    parser.add_argument("--combined-gate-json", default=DEFAULT_COMBINED_GATE_JSON)
    parser.add_argument("--corrected-eval-json", default=DEFAULT_CORRECTED_EVAL_JSON)
    parser.add_argument("--tau-gate-json", default=DEFAULT_TAU_GATE_JSON)
    parser.add_argument("--activation-result-json", default=DEFAULT_ACTIVATION_RESULT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _read_json(args.holdout_summary_json),
        _read_json(args.combined_gate_json),
        _read_json(args.corrected_eval_json),
        _read_json(args.tau_gate_json),
        _read_json(args.activation_result_json),
    )
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
