#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_PACKET_JSON = "runs/tau_k18_full_fold_corrected_calibration_packet_current.json"
DEFAULT_REFERENCE_GATE_JSON = "runs/idp_3bead_holdout_v7_anchor_commercial_pretest_r16validation_r1_fold6_tau_k18_gate_corrected_summary.json"
DEFAULT_CALIBRATION_SUMMARY_JSON = "runs/idp_tau_k18_stabilization_trial_commercial_pretest_seed123_phhelixrecover_r1_summary.json"
DEFAULT_CALIBRATION_GATE_JSON = "runs/idp_tau_k18_stabilization_trial_commercial_pretest_seed123_phhelixrecover_r1_gate_corrected_summary.json"
DEFAULT_CALIBRATION_EVAL_JSON = "runs/idp_tau_k18_stabilization_trial_commercial_pretest_seed123_phhelixrecover_r1_eval_corrected_summary.json"
DEFAULT_OUT_JSON = "runs/tau_k18_full_fold_corrected_calibration_result_current.json"
DEFAULT_OUT_CSV = "runs/tau_k18_full_fold_corrected_calibration_result_current.csv"
DEFAULT_OUT_MD = "runs/tau_k18_full_fold_corrected_calibration_result_current.md"


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


def _load_eval_rows(path_like: str) -> dict[str, dict[str, Any]]:
    payload = _load_json(path_like)
    return {
        str(row.get("condition_group", "")).strip(): dict(row)
        for row in payload.get("targets", []) or []
        if str(row.get("condition_group", "")).strip()
    }


def build_payload(
    packet_payload: dict[str, Any],
    reference_gate: dict[str, Any],
    calibration_summary: dict[str, Any],
    calibration_gate: dict[str, Any],
    calibration_eval: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    packet_s = dict(packet_payload.get("summary", {}) or {})
    ref_cls = dict(reference_gate.get("classification_metrics", {}) or {})
    cal_cls = dict(calibration_gate.get("classification_metrics", {}) or {})
    kalman_s = dict((calibration_summary.get("kalman_shadow", {}) if isinstance(calibration_summary.get("kalman_shadow", {}), dict) else {}) or {})

    rows: list[dict[str, Any]] = []
    recovered_condition_count = 0
    aggregation_mismatch_count = 0
    label_basis_drift_count = 0
    for row in packet_payload.get("rows", []) or []:
        condition = str(row.get("condition_group", "")).strip()
        cal_row = calibration_eval.get(condition, {})
        calibrated_pred_state = str(cal_row.get("pred_state", "")).strip()
        true_state = str(row.get("true_state", "")).strip()
        eval_true_state = str(cal_row.get("true_dominant_state", "")).strip()
        recovered = bool(calibrated_pred_state == true_state)
        pred_agg = int(float(cal_row.get("pred_aggregation_positive", cal_row.get("dynamic_aggregation_flag", 0)) or 0))
        true_agg = int(cal_row.get("true_aggregation_flag", 0) or 0)
        recovered_condition_count += int(recovered)
        aggregation_mismatch_count += int(pred_agg != true_agg)
        label_basis_drift_count += int(bool(eval_true_state) and eval_true_state != true_state)
        rows.append(
            {
                "condition_group": condition,
                "true_state": true_state,
                "eval_true_state": eval_true_state,
                "reference_pred_state": str(row.get("reference_pred_state", "")).strip(),
                "calibrated_pred_state": calibrated_pred_state,
                "recovered_true_state": recovered,
                "true_aggregation_flag": true_agg,
                "calibrated_aggregation_flag": pred_agg,
                "aggregation_mismatch": bool(pred_agg != true_agg),
                "tau_helix_gate": bool(cal_row.get("tau_k18_diag_tau_helix_gate", False)),
                "diag_state_assignment": str(cal_row.get("tau_k18_diag_state_assignment", "")).strip(),
            }
        )

    ref_dsa = float(ref_cls.get("dominant_state_accuracy", 0.0) or 0.0)
    cal_dsa = float(cal_cls.get("dominant_state_accuracy", 0.0) or 0.0)
    ref_agg = float(ref_cls.get("aggregation_flag_pr_auc", 0.0) or 0.0)
    cal_agg = float(cal_cls.get("aggregation_flag_pr_auc", 0.0) or 0.0)
    gate_pass = bool(calibration_gate.get("pass", False))
    comparable_to_official_failure_slice = label_basis_drift_count == 0
    if not comparable_to_official_failure_slice:
        status = "full_fold_calibration_completed_label_basis_drift"
        next_required_step = (
            "Do not use this local tau_k18 slice as official corrected-path evidence yet. First restore frozen-label parity so the local calibration trial and the bounded commercial-pretest failure slice use the same truth basis."
        )
    elif gate_pass:
        status = "full_fold_calibration_completed_local_pass_broader_blocked"
        next_required_step = (
            "This tau_k18 full-fold slice improved the local corrected-path gate. Keep broader_full_idp_promotion blocked, then validate the same rule in a bounded commercial-pretest rerun before changing any official IDP lane."
        )
    else:
        status = "full_fold_calibration_completed_blocker_persists"
        next_required_step = (
            "Keep broader_full_idp_promotion blocked, keep controlled_shadow_only_commercial_pretest unchanged, and use the remaining mismatch rows to choose one narrower branch/state calibration rule."
        )

    summary = {
        "status": status,
        "operator_scope_now": str(packet_s.get("operator_scope_now") or "").strip(),
        "shadow_safe_retained": (
            int(kalman_s.get("would_change_state_count", 0) or 0) == 0
            and int(kalman_s.get("would_change_gate_count", 0) or 0) == 0
            and int(kalman_s.get("would_change_llps_flag_count", 0) or 0) == 0
            and int(kalman_s.get("would_change_aggregation_flag_count", 0) or 0) == 0
        ),
        "broader_promotion_blocked": True,
        "blocking_target": str(packet_s.get("blocking_target") or "tau_k18").strip(),
        "blocking_class": str(packet_s.get("blocking_class") or "corrected_path_fragility").strip(),
        "candidate_rule_name": str(packet_s.get("candidate_rule_name") or "").strip(),
        "candidate_rule_scope": str(packet_s.get("candidate_rule_scope") or "").strip(),
        "reference_corrected_gate_pass": bool(reference_gate.get("pass", False)),
        "calibration_corrected_gate_pass": gate_pass,
        "reference_dominant_state_accuracy": ref_dsa,
        "calibration_dominant_state_accuracy": cal_dsa,
        "dominant_state_accuracy_delta": cal_dsa - ref_dsa,
        "reference_aggregation_flag_pr_auc": ref_agg,
        "calibration_aggregation_flag_pr_auc": cal_agg,
        "aggregation_flag_pr_auc_delta": cal_agg - ref_agg,
        "recovered_condition_count": recovered_condition_count,
        "focus_condition_count": len(rows),
        "comparable_to_official_failure_slice": comparable_to_official_failure_slice,
        "label_basis_drift_count": label_basis_drift_count,
        "remaining_aggregation_mismatch_count": aggregation_mismatch_count,
        "kalman_feature_mask": str(calibration_summary.get("kalman_shadow_feature_mask", "")).strip(),
        "idp_r16_ml_patch": int(calibration_summary.get("idp_r16_ml_patch", 0) or 0),
        "idp_r17_tau_ph_split_patch": int(calibration_summary.get("idp_r17_tau_ph_split_patch", 0) or 0),
        "idp_r18_tau_ph_helix_recovery_patch": int(calibration_summary.get("idp_r18_tau_ph_helix_recovery_patch", 0) or 0),
        "would_change_state_count": int(kalman_s.get("would_change_state_count", 0) or 0),
        "would_change_gate_count": int(kalman_s.get("would_change_gate_count", 0) or 0),
        "next_required_step": next_required_step,
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Tau K18 Full-Fold Corrected Calibration Result",
        "",
        f"- status: `{s['status']}`",
        f"- operator_scope_now: `{s['operator_scope_now']}`",
        f"- shadow_safe_retained: `{s['shadow_safe_retained']}`",
        f"- broader_promotion_blocked: `{s['broader_promotion_blocked']}`",
        f"- candidate_rule_name: `{s['candidate_rule_name']}`",
        f"- reference_corrected_gate_pass: `{s['reference_corrected_gate_pass']}`",
        f"- calibration_corrected_gate_pass: `{s['calibration_corrected_gate_pass']}`",
        f"- reference_dominant_state_accuracy: `{s['reference_dominant_state_accuracy']}`",
        f"- calibration_dominant_state_accuracy: `{s['calibration_dominant_state_accuracy']}`",
        f"- dominant_state_accuracy_delta: `{s['dominant_state_accuracy_delta']}`",
        f"- recovered_condition_count: `{s['recovered_condition_count']}`",
        f"- focus_condition_count: `{s['focus_condition_count']}`",
        f"- comparable_to_official_failure_slice: `{s['comparable_to_official_failure_slice']}`",
        f"- label_basis_drift_count: `{s['label_basis_drift_count']}`",
        f"- remaining_aggregation_mismatch_count: `{s['remaining_aggregation_mismatch_count']}`",
        f"- idp_r18_tau_ph_helix_recovery_patch: `{s['idp_r18_tau_ph_helix_recovery_patch']}`",
        "",
        "## Focus Conditions",
        "",
        "| condition | packet_true_state | eval_true_state | calibrated_pred_state | recovered_true_state | agg_mismatch | tau_helix_gate | diag_state_assignment |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['condition_group']}` | `{row['true_state']}` | `{row['eval_true_state']}` | `{row['calibrated_pred_state']}` | `{row['recovered_true_state']}` | `{row['aggregation_mismatch']}` | `{row['tau_helix_gate']}` | `{row['diag_state_assignment']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the result artifact for a tau_k18 full-fold corrected calibration slice.")
    parser.add_argument("--packet-json", default=DEFAULT_PACKET_JSON)
    parser.add_argument("--reference-gate-json", default=DEFAULT_REFERENCE_GATE_JSON)
    parser.add_argument("--calibration-summary-json", default=DEFAULT_CALIBRATION_SUMMARY_JSON)
    parser.add_argument("--calibration-gate-json", default=DEFAULT_CALIBRATION_GATE_JSON)
    parser.add_argument("--calibration-eval-json", default=DEFAULT_CALIBRATION_EVAL_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.packet_json),
        _load_json(args.reference_gate_json),
        _load_json(args.calibration_summary_json),
        _load_json(args.calibration_gate_json),
        _load_eval_rows(args.calibration_eval_json),
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
