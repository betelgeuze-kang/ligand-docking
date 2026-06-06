#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_FAILURE_PACKET_JSON = "runs/idp_tau_k18_corrected_path_failure_packet_current.json"
DEFAULT_DECISION_JSON = "runs/idp_commercial_pretest_decision_current.json"
DEFAULT_PLAN_JSON = "runs/tau_k18_stabilization_plan_current.json"
DEFAULT_REFERENCE_SUMMARY_JSON = "runs/idp_tau_k18_stabilization_trial_seed77_r1_summary.json"
DEFAULT_OUT_JSON = "runs/tau_k18_stabilization_packet_current.json"
DEFAULT_OUT_CSV = "runs/tau_k18_stabilization_packet_current.csv"
DEFAULT_OUT_MD = "runs/tau_k18_stabilization_packet_current.md"


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


def _infer_reference_summary_path(
    plan_payload: dict[str, Any],
    fallback: str,
) -> str:
    summary = dict(plan_payload.get("summary", {}) or {})
    reference = dict(summary.get("completed_reference_trial", {}) or {})
    return str(reference.get("source_summary_json") or fallback)


def build_payload(
    failure_packet: dict[str, Any],
    decision_payload: dict[str, Any],
    plan_payload: dict[str, Any],
    reference_summary: dict[str, Any],
) -> dict[str, Any]:
    failure_s = dict(failure_packet.get("summary", {}) or {})
    decision_s = dict(decision_payload.get("summary", {}) or {})
    plan_s = dict(plan_payload.get("summary", {}) or {})
    reference_s = dict(reference_summary or {})
    next_trial = dict(plan_s.get("next_trial", {}) or {})
    reference_trial = dict(plan_s.get("completed_reference_trial", {}) or {})

    condition_rows: list[dict[str, Any]] = []
    for idx, row in enumerate(failure_packet.get("row_deltas", []) or [], start=1):
        true_state = str(row.get("true_state", "")).strip()
        corrected_pred_state = str(row.get("corrected_pred_state", "")).strip()
        condition_rows.append(
            {
                "packet_rank": idx,
                "condition_group": str(row.get("condition_group", "")).strip(),
                "true_state": true_state,
                "baseline_state": str(row.get("baseline_state", "")).strip(),
                "corrected_state": str(row.get("corrected_state", "")).strip(),
                "corrected_pred_state": corrected_pred_state,
                "prediction_matches_true_state": corrected_pred_state == true_state,
                "baseline_target_pass": int(row.get("baseline_target_pass", 0) or 0),
                "corrected_target_pass": int(row.get("corrected_target_pass", 0) or 0),
                "would_have_changed_state": int(row.get("would_have_changed_state", 0) or 0),
                "would_have_changed_gate": int(row.get("would_have_changed_gate", 0) or 0),
                "kf_shadow_state": str(row.get("kf_shadow_state", "")).strip(),
            }
        )

    summary = {
        "status": "operator_packet_ready",
        "packet_scope": "tau_k18_corrected_path_single_fold_stabilization_fallback",
        "operator_scope_now": str(
            decision_s.get("operator_scope_now") or failure_s.get("operator_scope_now") or ""
        ).strip(),
        "shadow_safe_retained": bool(
            decision_s.get("shadow_safe_retained", failure_s.get("shadow_safe_retained", False))
        ),
        "broader_promotion_blocked": bool(
            decision_s.get("broader_promotion_blocked", failure_s.get("broader_promotion_blocked", True))
        ),
        "blocking_target": str(
            decision_s.get("blocking_target") or failure_s.get("failure_anchor_target") or "tau_k18"
        ).strip(),
        "blocking_class": str(decision_s.get("blocking_class") or "corrected_path_fragility").strip(),
        "reference_fail_seed": int(reference_s.get("seed", reference_trial.get("seed", 77)) or 77),
        "reference_fail_pass": bool(reference_s.get("pass", False)),
        "reference_corrected_gate_pass": reference_s.get("corrected_gate_pass"),
        "reference_corrected_dominant_state_accuracy": reference_s.get(
            "corrected_dominant_state_accuracy"
        ),
        "next_trial_label": str(next_trial.get("label", "")).strip(),
        "next_trial_seed": int(next_trial.get("seed", 0) or 0),
        "next_trial_epochs": int(next_trial.get("epochs", 0) or 0),
        "next_trial_patience": int(next_trial.get("patience", 0) or 0),
        "next_trial_lr": float(next_trial.get("lr", 0.0) or 0.0),
        "next_trial_weight_decay": float(next_trial.get("weight_decay", 0.0) or 0.0),
        "next_trial_train_npz": str(next_trial.get("train_npz", "")).strip(),
        "next_trial_eval_config_json": str(next_trial.get("eval_config_json", "")).strip(),
        "next_trial_baseline_gate_json": str(next_trial.get("baseline_gate_json", "")).strip(),
        "next_trial_out_prefix": str(next_trial.get("out_prefix", "")).strip(),
        "next_trial_fixed_feature_mask": str(next_trial.get("fixed_feature_mask", "")).strip(),
        "next_trial_fixed_kalman_mode": str(next_trial.get("fixed_kalman_mode", "")).strip(),
        "exact_command": str(next_trial.get("exact_command", "")).strip(),
        "dominant_state_accuracy": failure_s.get("dominant_state_accuracy"),
        "dominant_state_threshold": failure_s.get("dominant_state_threshold"),
        "branch_macro_f1": failure_s.get("branch_macro_f1"),
        "kalman_state_change_count": int(failure_s.get("kalman_state_change_count", 0) or 0),
        "kalman_gate_change_count": int(failure_s.get("kalman_gate_change_count", 0) or 0),
        "condition_row_count": len(condition_rows),
        "blocker_reason": str(
            failure_s.get("blocker_reason") or decision_s.get("blocker_reason") or ""
        ).strip(),
        "decision_reason": str(decision_s.get("decision_reason", "")).strip(),
        "next_required_step": str(
            decision_s.get("next_required_step") or plan_s.get("failure_gate") or ""
        ).strip(),
    }
    return {
        "summary": summary,
        "conditions": condition_rows,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Tau K18 Stabilization Packet",
        "",
        f"- status: `{summary['status']}`",
        f"- packet_scope: `{summary['packet_scope']}`",
        f"- operator_scope_now: `{summary['operator_scope_now']}`",
        f"- shadow_safe_retained: `{summary['shadow_safe_retained']}`",
        f"- broader_promotion_blocked: `{summary['broader_promotion_blocked']}`",
        f"- blocking_target: `{summary['blocking_target']}`",
        f"- blocking_class: `{summary['blocking_class']}`",
        f"- reference_fail_seed: `{summary['reference_fail_seed']}`",
        f"- reference_fail_pass: `{summary['reference_fail_pass']}`",
        f"- reference_corrected_gate_pass: `{summary['reference_corrected_gate_pass']}`",
        f"- reference_corrected_dominant_state_accuracy: `{summary['reference_corrected_dominant_state_accuracy']}`",
        f"- next_trial_label: `{summary['next_trial_label']}`",
        f"- next_trial_seed: `{summary['next_trial_seed']}`",
        f"- next_trial_epochs: `{summary['next_trial_epochs']}`",
        f"- next_trial_patience: `{summary['next_trial_patience']}`",
        f"- next_trial_lr: `{summary['next_trial_lr']}`",
        f"- next_trial_weight_decay: `{summary['next_trial_weight_decay']}`",
        f"- next_trial_fixed_kalman_mode: `{summary['next_trial_fixed_kalman_mode']}`",
        f"- next_trial_fixed_feature_mask: `{summary['next_trial_fixed_feature_mask']}`",
        f"- dominant_state_accuracy: `{summary['dominant_state_accuracy']}`",
        f"- dominant_state_threshold: `{summary['dominant_state_threshold']}`",
        f"- branch_macro_f1: `{summary['branch_macro_f1']}`",
        f"- kalman_state_change_count: `{summary['kalman_state_change_count']}`",
        f"- kalman_gate_change_count: `{summary['kalman_gate_change_count']}`",
        f"- condition_row_count: `{summary['condition_row_count']}`",
        "",
        "## Why This Packet Exists",
        "",
        f"- {summary['decision_reason']}",
        f"- {summary['blocker_reason']}",
        "",
        "## Next Runnable Slice",
        "",
        f"- train_npz: `{summary['next_trial_train_npz']}`",
        f"- eval_config_json: `{summary['next_trial_eval_config_json']}`",
        f"- baseline_gate_json: `{summary['next_trial_baseline_gate_json']}`",
        f"- out_prefix: `{summary['next_trial_out_prefix']}`",
        "",
        "## Exact Command",
        "",
        "```bash",
        summary["exact_command"],
        "```",
        "",
        "## Guardrail",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Conditions",
        "",
        "| rank | condition | true_state | corrected_pred_state | pred_matches_true | baseline_pass | corrected_pass | kf_state_change | kf_gate_change |",
        "| ---: | --- | --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["conditions"]:
        lines.append(
            f"| {row['packet_rank']} | `{row['condition_group']}` | `{row['true_state']}` | "
            f"`{row['corrected_pred_state']}` | `{row['prediction_matches_true_state']}` | "
            f"{row['baseline_target_pass']} | {row['corrected_target_pass']} | "
            f"{row['would_have_changed_state']} | {row['would_have_changed_gate']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Build an operator-facing tau_k18 stabilization packet from the failure packet, decision, and stabilization plan."
    )
    ap.add_argument("--failure-packet-json", default=DEFAULT_FAILURE_PACKET_JSON)
    ap.add_argument("--decision-json", default=DEFAULT_DECISION_JSON)
    ap.add_argument("--plan-json", default=DEFAULT_PLAN_JSON)
    ap.add_argument("--reference-summary-json", default=DEFAULT_REFERENCE_SUMMARY_JSON)
    ap.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    ap.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    ap.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    plan_payload = _load_json(args.plan_json)
    reference_summary_path = args.reference_summary_json or _infer_reference_summary_path(
        plan_payload,
        DEFAULT_REFERENCE_SUMMARY_JSON,
    )
    payload = build_payload(
        _load_json(args.failure_packet_json),
        _load_json(args.decision_json),
        plan_payload,
        _load_json(reference_summary_path),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_cvs if hasattr(args, "out_cvs") else args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["conditions"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
