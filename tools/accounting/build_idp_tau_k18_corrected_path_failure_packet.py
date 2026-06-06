#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.operator_surface_contracts import IDP_SAFE_SCOPE_CONTROLLED_PRETEST

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BASELINE_GATE_JSON = "runs/idp_3bead_holdout_v7_anchor_commercial_pretest_r1_fold6_tau_k18_gate_baseline_summary.json"
DEFAULT_CORRECTED_GATE_JSON = "runs/idp_3bead_holdout_v7_anchor_commercial_pretest_r1_fold6_tau_k18_gate_corrected_summary.json"
DEFAULT_BASELINE_EVAL_JSON = "runs/idp_3bead_holdout_v7_anchor_commercial_pretest_r1_fold6_tau_k18_eval_baseline_summary.json"
DEFAULT_CORRECTED_EVAL_JSON = "runs/idp_3bead_holdout_v7_anchor_commercial_pretest_r1_fold6_tau_k18_eval_corrected_summary.json"
DEFAULT_OUT_JSON = "runs/idp_tau_k18_corrected_path_failure_packet_current.json"
DEFAULT_OUT_CSV = "runs/idp_tau_k18_corrected_path_failure_packet_current.csv"
DEFAULT_OUT_MD = "runs/idp_tau_k18_corrected_path_failure_packet_current.md"


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
    baseline_gate: dict[str, Any],
    corrected_gate: dict[str, Any],
    baseline_eval: dict[str, Any],
    corrected_eval: dict[str, Any],
) -> dict[str, Any]:
    baseline_rows = {str(r.get("condition_group", "")): r for r in baseline_eval.get("targets", []) or []}
    corrected_rows = {str(r.get("condition_group", "")): r for r in corrected_eval.get("targets", []) or []}
    conditions = sorted(set(baseline_rows) | set(corrected_rows))
    row_deltas: list[dict[str, Any]] = []
    for condition in conditions:
        baseline_row = baseline_rows.get(condition, {})
        corrected_row = corrected_rows.get(condition, {})
        row_deltas.append(
            {
                "condition_group": condition,
                "true_state": str(corrected_row.get("true_dominant_state", baseline_row.get("true_dominant_state", ""))),
                "baseline_state": str(baseline_row.get("dominant_state_label", "")),
                "corrected_state": str(corrected_row.get("dominant_state_label", "")),
                "baseline_pred_state": str(baseline_row.get("pred_state", "")),
                "corrected_pred_state": str(corrected_row.get("pred_state", "")),
                "baseline_target_pass": int(bool(baseline_row.get("target_pass", False))),
                "corrected_target_pass": int(bool(corrected_row.get("target_pass", False))),
                "would_have_changed_state": int(bool(corrected_row.get("would_have_changed_state", False))),
                "would_have_changed_gate": int(bool(corrected_row.get("would_have_changed_gate", False))),
                "kf_shadow_state": str(corrected_row.get("kf_shadow_dominant_state_label", "")),
            }
        )

    corrected_gate_context = dict((corrected_gate.get("gate_context", {}) or {}).get("effective_thresholds", {}) or {})
    corrected_cls = dict(corrected_gate.get("classification_metrics", {}) or {})
    corrected_rank = dict(corrected_gate.get("ranking_metrics", {}) or {})
    corrected_anchor = dict(corrected_gate.get("anchor_diagnostics", {}) or {})
    kalman_state_change_count = int(sum(row["would_have_changed_state"] for row in row_deltas))
    kalman_gate_change_count = int(sum(row["would_have_changed_gate"] for row in row_deltas))
    shadow_safe_retained = kalman_state_change_count == 0 and kalman_gate_change_count == 0

    blocker_reason = (
        "tau_k18 corrected-path fragility remains the blocker for broader IDP promotion; "
        "Kalman shadow stayed telemetry-only and did not cause the failure."
    )
    do_not_infer = (
        "Do not treat this as a Kalman-shadow regression or as evidence against the current "
        "controlled shadow-only commercial-pretest lane."
    )
    next_required_step = (
        "Keep the current controlled commercial-pretest lane active, retain shadow-safe status, "
        "and block broader full-IDP promotion until tau_k18 corrected-path fragility is resolved."
    )

    summary = {
        "status": "corrected_path_failure_packet_ready",
        "packet_scope": "tau_k18_corrected_path_failure_within_controlled_shadow_only_commercial_pretest",
        "operator_scope_now": IDP_SAFE_SCOPE_CONTROLLED_PRETEST,
        "broader_promotion_blocked": True,
        "shadow_safe_retained": shadow_safe_retained,
        "failure_anchor_target": "tau_k18",
        "baseline_pass": bool(baseline_gate.get("pass", False)),
        "corrected_pass": bool(corrected_gate.get("pass", False)),
        "corrected_utility_gate_pass": bool(corrected_gate.get("utility_gate_pass", False)),
        "corrected_physics_gate_pass": bool(corrected_gate.get("physics_gate_pass", False)),
        "dominant_state_accuracy": float(corrected_cls.get("dominant_state_accuracy", 0.0) or 0.0),
        "dominant_state_threshold": float(corrected_gate_context.get("min_dominant_state_accuracy", 0.0) or 0.0),
        "branch_macro_f1": float(corrected_cls.get("branch_macro_f1", 0.0) or 0.0),
        "llps_flag_pr_auc": float(corrected_cls.get("llps_flag_pr_auc", 0.0) or 0.0),
        "aggregation_flag_pr_auc": float(corrected_cls.get("aggregation_flag_pr_auc", 0.0) or 0.0),
        "compactness_rank_auc": float(corrected_rank.get("compactness_rank_auc", 0.0) or 0.0),
        "helicity_rank_auc": float(corrected_rank.get("helicity_rank_auc", 0.0) or 0.0),
        "condensation_rank_auc": float(corrected_rank.get("condensation_rank_auc", 0.0) or 0.0),
        "rg_anchor_error": float(((corrected_anchor.get("rg_mean", {}) or {}).get("median_normalized_error", 0.0)) or 0.0),
        "sasa_anchor_error": float(((corrected_anchor.get("sasa_proxy_mean", {}) or {}).get("median_normalized_error", 0.0)) or 0.0),
        "kalman_state_change_count": kalman_state_change_count,
        "kalman_gate_change_count": kalman_gate_change_count,
        "blocker_reason": blocker_reason,
        "do_not_infer": do_not_infer,
        "next_required_step": next_required_step,
    }
    return {"summary": summary, "row_deltas": row_deltas}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# IDP Tau K18 Corrected-Path Failure Packet",
        "",
        f"- status: `{summary['status']}`",
        f"- packet_scope: `{summary['packet_scope']}`",
        f"- operator_scope_now: `{summary['operator_scope_now']}`",
        f"- broader_promotion_blocked: `{summary['broader_promotion_blocked']}`",
        f"- shadow_safe_retained: `{summary['shadow_safe_retained']}`",
        f"- failure_anchor_target: `{summary['failure_anchor_target']}`",
        f"- baseline_pass: `{summary['baseline_pass']}`",
        f"- corrected_pass: `{summary['corrected_pass']}`",
        f"- corrected_utility_gate_pass: `{summary['corrected_utility_gate_pass']}`",
        f"- corrected_physics_gate_pass: `{summary['corrected_physics_gate_pass']}`",
        f"- dominant_state_accuracy: `{summary['dominant_state_accuracy']}`",
        f"- dominant_state_threshold: `{summary['dominant_state_threshold']}`",
        f"- branch_macro_f1: `{summary['branch_macro_f1']}`",
        f"- llps_flag_pr_auc: `{summary['llps_flag_pr_auc']}`",
        f"- aggregation_flag_pr_auc: `{summary['aggregation_flag_pr_auc']}`",
        f"- compactness_rank_auc: `{summary['compactness_rank_auc']}`",
        f"- helicity_rank_auc: `{summary['helicity_rank_auc']}`",
        f"- condensation_rank_auc: `{summary['condensation_rank_auc']}`",
        f"- kalman_state_change_count: `{summary['kalman_state_change_count']}`",
        f"- kalman_gate_change_count: `{summary['kalman_gate_change_count']}`",
        "",
        "## Blocker",
        "",
        f"- {summary['blocker_reason']}",
        f"- {summary['do_not_infer']}",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Conditions",
        "",
        "| condition | true | baseline_state | corrected_state | baseline_pred | corrected_pred | corrected_pass | kf_state_change | kf_gate_change |",
        "| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: |",
    ]
    for row in payload["row_deltas"]:
        lines.append(
            f"| {row['condition_group']} | {row['true_state']} | {row['baseline_state']} | {row['corrected_state']} | "
            f"{row['baseline_pred_state']} | {row['corrected_pred_state']} | {row['corrected_target_pass']} | "
            f"{row['would_have_changed_state']} | {row['would_have_changed_gate']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the tau_k18 corrected-path failure packet for the IDP commercial-pretest lane.")
    parser.add_argument("--baseline-gate-json", default=DEFAULT_BASELINE_GATE_JSON)
    parser.add_argument("--corrected-gate-json", default=DEFAULT_CORRECTED_GATE_JSON)
    parser.add_argument("--baseline-eval-json", default=DEFAULT_BASELINE_EVAL_JSON)
    parser.add_argument("--corrected-eval-json", default=DEFAULT_CORRECTED_EVAL_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _read_json(args.baseline_gate_json),
        _read_json(args.corrected_gate_json),
        _read_json(args.baseline_eval_json),
        _read_json(args.corrected_eval_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["row_deltas"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
