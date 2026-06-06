#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PACKET_JSON = "runs/tau_k18_corrected_path_diagnostic_packet_current.json"
DEFAULT_REFERENCE_SUMMARY_JSON = "runs/idp_tau_k18_stabilization_trial_commercial_pretest_seed123_r1_summary.json"
DEFAULT_REFERENCE_GATE_JSON = "runs/idp_tau_k18_stabilization_trial_commercial_pretest_seed123_r1_gate_corrected_summary.json"
DEFAULT_DIAGNOSTIC_SUMMARY_JSON = "runs/idp_tau_k18_stabilization_trial_commercial_pretest_seed123_basephlow_diag_r1_summary.json"
DEFAULT_DIAGNOSTIC_GATE_JSON = "runs/idp_tau_k18_stabilization_trial_commercial_pretest_seed123_basephlow_diag_r1_gate_corrected_summary.json"
DEFAULT_DIAGNOSTIC_EVAL_JSON = "runs/idp_tau_k18_stabilization_trial_commercial_pretest_seed123_basephlow_diag_r1_eval_corrected_summary.json"
DEFAULT_OUT_JSON = "runs/tau_k18_corrected_path_diagnostic_result_current.json"
DEFAULT_OUT_CSV = "runs/tau_k18_corrected_path_diagnostic_result_current.csv"
DEFAULT_OUT_MD = "runs/tau_k18_corrected_path_diagnostic_result_current.md"


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
    reference_summary: dict[str, Any],
    reference_gate: dict[str, Any],
    diagnostic_summary: dict[str, Any],
    diagnostic_gate: dict[str, Any],
    diagnostic_eval: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    packet_s = dict(packet_payload.get("summary", {}) or {})
    ref_cls = dict(reference_gate.get("classification_metrics", {}) or {})
    diag_cls = dict(diagnostic_gate.get("classification_metrics", {}) or {})
    kalman_s = dict((diagnostic_summary.get("kalman_shadow", {}) if isinstance(diagnostic_summary.get("kalman_shadow", {}), dict) else {}) or {})

    rows: list[dict[str, Any]] = []
    expanded_gate_count = 0
    debug_columns_present_count = 0
    inactive_short_tau_diag_count = 0
    for row in packet_payload.get("rows", []) or []:
        condition = str(row.get("condition_group", "")).strip()
        diag_row = diagnostic_eval.get(condition, {})
        debug_present = bool(
            "tau_k18_diag_gate_mode" in diag_row
            or "tau_k18_diag_state_assignment" in diag_row
        )
        expanded_gate = bool(diag_row.get("tau_k18_diag_expanded_gate", False))
        inactive_diag = (
            debug_present
            and not bool(diag_row.get("tau_k18_diag_enabled", False))
            and not bool(diag_row.get("tau_k18_diag_focus_condition", False))
            and not bool(diag_row.get("tau_k18_diag_tau_helix_gate", False))
            and not expanded_gate
            and not bool(diag_row.get("tau_k18_diag_sticky_gate", False))
            and not str(
                diag_row.get(
                    "tau_k18_diag_state_assignment",
                    diag_row.get("tau_k18_diag_gate_mode", ""),
                )
            ).strip()
        )
        expanded_gate_count += int(expanded_gate)
        debug_columns_present_count += int(debug_present)
        inactive_short_tau_diag_count += int(inactive_diag)
        rows.append(
            {
                "condition_group": condition,
                "true_state": str(row.get("true_state", "")).strip(),
                "reference_pred_state": str(row.get("reference_pred_state", "")).strip(),
                "diagnostic_pred_state": str(diag_row.get("pred_state", "")).strip(),
                "gate_mode": str(diag_row.get("tau_k18_diag_state_assignment", diag_row.get("tau_k18_diag_gate_mode", ""))).strip(),
                "tau_helix_gate": bool(diag_row.get("tau_k18_diag_tau_helix_gate", False)),
                "expanded_gate": expanded_gate,
                "sticky_gate": bool(diag_row.get("tau_k18_diag_sticky_gate", False)),
                "agg_cal_pre_gate": diag_row.get("tau_k18_diag_agg_cal_pre_gate"),
                "agg_cal_post_gate": diag_row.get("tau_k18_diag_agg_cal_post_gate"),
                "short_tau_expand_meta": diag_row.get("tau_k18_diag_short_tau_expand_meta"),
                "short_tau_helix_meta": diag_row.get("tau_k18_diag_short_tau_helix_meta"),
                "short_tau_compact_meta": diag_row.get("tau_k18_diag_short_tau_compact_meta"),
                "debug_columns_present": debug_present,
            }
        )

    ref_dsa = float(reference_summary.get("corrected_dominant_state_accuracy", ref_cls.get("dominant_state_accuracy", 0.0)) or 0.0)
    diag_dsa = float(diagnostic_summary.get("corrected_dominant_state_accuracy", diag_cls.get("dominant_state_accuracy", 0.0)) or 0.0)
    ref_agg = float(ref_cls.get("aggregation_flag_pr_auc", 0.0) or 0.0)
    diag_agg = float(diag_cls.get("aggregation_flag_pr_auc", 0.0) or 0.0)
    behavior_change_detected = bool(
        bool(reference_summary.get("corrected_gate_pass", False)) != bool(diagnostic_summary.get("corrected_gate_pass", False))
        or diag_dsa != ref_dsa
        or diag_agg != ref_agg
    )
    diagnostic_path_inactive = bool(rows) and inactive_short_tau_diag_count == len(rows)
    primary_observation = (
        "short_tau_diagnostic_path_inactive_on_current_corrected_slice"
        if diagnostic_path_inactive
        else "expanded_gate_dominates_remaining_base_phlow_gap"
        if expanded_gate_count == len(rows) and rows
        else "diagnostic_columns_present_behavior_unchanged"
    )
    next_required_step = (
        "Keep broader_full_idp_promotion blocked, keep controlled_shadow_only_commercial_pretest unchanged, and inspect why the short-tau diagnostic path stayed inactive on base/ph_low before choosing another corrected-path calibration rule."
        if diagnostic_path_inactive
        else "Keep broader_full_idp_promotion blocked, keep controlled_shadow_only_commercial_pretest unchanged, and use these tau_k18_diag_* rows to choose exactly one next corrected-path calibration rule for the remaining base/ph_low compact-state gap."
    )

    summary = {
        "status": "single_slice_diagnostic_completed_blocker_persists",
        "operator_scope_now": str(packet_s.get("operator_scope_now") or "").strip(),
        "shadow_safe_retained": (
            int(kalman_s.get("would_change_state_count", 0) or 0) == 0
            and int(kalman_s.get("would_change_gate_count", 0) or 0) == 0
        ),
        "broader_promotion_blocked": True,
        "blocking_target": str(packet_s.get("blocking_target") or "tau_k18").strip(),
        "blocking_class": str(packet_s.get("blocking_class") or "corrected_path_fragility").strip(),
        "diagnostic_rule_name": str(packet_s.get("diagnostic_rule_name") or "").strip(),
        "diagnostic_rule_scope": str(packet_s.get("diagnostic_rule_scope") or "").strip(),
        "reference_corrected_gate_pass": bool(reference_summary.get("corrected_gate_pass", False)),
        "diagnostic_corrected_gate_pass": bool(diagnostic_summary.get("corrected_gate_pass", False)),
        "reference_dominant_state_accuracy": ref_dsa,
        "diagnostic_dominant_state_accuracy": diag_dsa,
        "dominant_state_accuracy_delta": diag_dsa - ref_dsa,
        "reference_aggregation_flag_pr_auc": ref_agg,
        "diagnostic_aggregation_flag_pr_auc": diag_agg,
        "aggregation_flag_pr_auc_delta": diag_agg - ref_agg,
        "behavior_change_detected": behavior_change_detected,
        "debug_columns_present_count": debug_columns_present_count,
        "inactive_short_tau_diag_count": inactive_short_tau_diag_count,
        "focus_condition_count": len(rows),
        "expanded_gate_count": expanded_gate_count,
        "primary_observation": primary_observation,
        "next_required_step": next_required_step,
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Tau K18 Corrected-Path Diagnostic Result",
        "",
        f"- status: `{s['status']}`",
        f"- operator_scope_now: `{s['operator_scope_now']}`",
        f"- shadow_safe_retained: `{s['shadow_safe_retained']}`",
        f"- broader_promotion_blocked: `{s['broader_promotion_blocked']}`",
        f"- blocking_target: `{s['blocking_target']}`",
        f"- blocking_class: `{s['blocking_class']}`",
        f"- diagnostic_rule_name: `{s['diagnostic_rule_name']}`",
        f"- diagnostic_rule_scope: `{s['diagnostic_rule_scope']}`",
        f"- reference_corrected_gate_pass: `{s['reference_corrected_gate_pass']}`",
        f"- diagnostic_corrected_gate_pass: `{s['diagnostic_corrected_gate_pass']}`",
        f"- reference_dominant_state_accuracy: `{s['reference_dominant_state_accuracy']}`",
        f"- diagnostic_dominant_state_accuracy: `{s['diagnostic_dominant_state_accuracy']}`",
        f"- dominant_state_accuracy_delta: `{s['dominant_state_accuracy_delta']}`",
        f"- reference_aggregation_flag_pr_auc: `{s['reference_aggregation_flag_pr_auc']}`",
        f"- diagnostic_aggregation_flag_pr_auc: `{s['diagnostic_aggregation_flag_pr_auc']}`",
        f"- aggregation_flag_pr_auc_delta: `{s['aggregation_flag_pr_auc_delta']}`",
        f"- behavior_change_detected: `{s['behavior_change_detected']}`",
        f"- debug_columns_present_count: `{s['debug_columns_present_count']}`",
        f"- inactive_short_tau_diag_count: `{s['inactive_short_tau_diag_count']}`",
        f"- expanded_gate_count: `{s['expanded_gate_count']}`",
        f"- primary_observation: `{s['primary_observation']}`",
        "",
        "## Focus Conditions",
        "",
        "| condition | true_state | diagnostic_pred_state | gate_mode | tau_helix_gate | expanded_gate | sticky_gate | agg_cal_pre | agg_cal_post |",
        "| --- | --- | --- | --- | --- | --- | --- | ---: | ---: |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['condition_group']}` | `{row['true_state']}` | `{row['diagnostic_pred_state']}` | `{row['gate_mode']}` | "
            f"`{row['tau_helix_gate']}` | `{row['expanded_gate']}` | `{row['sticky_gate']}` | {row['agg_cal_pre_gate']} | {row['agg_cal_post_gate']} |"
        )
    lines.extend(
        [
            "",
            "## Next Step",
            "",
            f"- {s['next_required_step']}",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the result artifact for a tau_k18 corrected-path observability-only diagnostic slice.")
    parser.add_argument("--packet-json", default=DEFAULT_PACKET_JSON)
    parser.add_argument("--reference-summary-json", default=DEFAULT_REFERENCE_SUMMARY_JSON)
    parser.add_argument("--reference-gate-json", default=DEFAULT_REFERENCE_GATE_JSON)
    parser.add_argument("--diagnostic-summary-json", default=DEFAULT_DIAGNOSTIC_SUMMARY_JSON)
    parser.add_argument("--diagnostic-gate-json", default=DEFAULT_DIAGNOSTIC_GATE_JSON)
    parser.add_argument("--diagnostic-eval-json", default=DEFAULT_DIAGNOSTIC_EVAL_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.packet_json),
        _load_json(args.reference_summary_json),
        _load_json(args.reference_gate_json),
        _load_json(args.diagnostic_summary_json),
        _load_json(args.diagnostic_gate_json),
        _load_eval_rows(args.diagnostic_eval_json),
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
