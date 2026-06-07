#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PACKET_JSON = "runs/tau_k18_corrected_path_activation_packet_current.json"
DEFAULT_REFERENCE_RESULT_JSON = "runs/tau_k18_corrected_path_diagnostic_result_current.json"
DEFAULT_ACTIVATION_SUMMARY_JSON = "runs/idp_tau_k18_activation_trial_commercial_pretest_seed123_r16patch_r1_summary.json"
DEFAULT_ACTIVATION_GATE_JSON = "runs/idp_tau_k18_activation_trial_commercial_pretest_seed123_r16patch_r1_gate_corrected_summary.json"
DEFAULT_ACTIVATION_EVAL_JSON = "runs/idp_tau_k18_activation_trial_commercial_pretest_seed123_r16patch_r1_eval_corrected_summary.json"
DEFAULT_OUT_JSON = "runs/tau_k18_corrected_path_activation_result_current.json"
DEFAULT_OUT_CSV = "runs/tau_k18_corrected_path_activation_result_current.csv"
DEFAULT_OUT_MD = "runs/tau_k18_corrected_path_activation_result_current.md"


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
    reference_result: dict[str, Any],
    activation_summary: dict[str, Any],
    activation_gate: dict[str, Any],
    activation_eval: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    packet_s = dict(packet_payload.get("summary", {}) or {})
    ref_s = dict(reference_result.get("summary", {}) or {})
    act_cls = dict(activation_gate.get("classification_metrics", {}) or {})
    kalman_s = dict((activation_summary.get("kalman_shadow", {}) if isinstance(activation_summary.get("kalman_shadow", {}), dict) else {}) or {})

    rows: list[dict[str, Any]] = []
    focus_condition_enabled_count = 0
    focus_condition_active_count = 0
    for row in packet_payload.get("rows", []) or []:
        condition = str(row.get("condition_group", "")).strip()
        act_row = activation_eval.get(condition, {})
        diag_enabled = bool(act_row.get("tau_k18_diag_enabled", False))
        diag_focus = bool(act_row.get("tau_k18_diag_focus_condition", False))
        focus_condition_enabled_count += int(diag_enabled)
        focus_condition_active_count += int(diag_enabled and diag_focus)
        rows.append(
            {
                "condition_group": condition,
                "true_state": str(row.get("true_state", "")).strip(),
                "pred_state": str(act_row.get("pred_state", "")).strip(),
                "diag_enabled": diag_enabled,
                "diag_focus_condition": diag_focus,
                "gate_mode": str(act_row.get("tau_k18_diag_state_assignment", act_row.get("tau_k18_diag_gate_mode", ""))).strip(),
                "tau_helix_gate": bool(act_row.get("tau_k18_diag_tau_helix_gate", False)),
                "expanded_gate": bool(act_row.get("tau_k18_diag_expanded_gate", False)),
                "sticky_gate": bool(act_row.get("tau_k18_diag_sticky_gate", False)),
                "short_tau_expand_meta": act_row.get("tau_k18_diag_short_tau_expand_meta"),
                "short_tau_helix_meta": act_row.get("tau_k18_diag_short_tau_helix_meta"),
                "short_tau_compact_meta": act_row.get("tau_k18_diag_short_tau_compact_meta"),
            }
        )

    focus_count = len(rows)
    path_activated = bool(rows) and focus_condition_enabled_count == focus_count and focus_condition_active_count == focus_count
    shadow_safe_retained = (
        int(kalman_s.get("would_change_state_count", 0) or 0) == 0
        and int(kalman_s.get("would_change_gate_count", 0) or 0) == 0
    )
    primary_observation = (
        "short_tau_diagnostic_path_activated_on_focus_rows"
        if path_activated
        else "short_tau_diagnostic_path_still_inactive_on_focus_rows"
    )
    next_required_step = (
        "Keep broader_full_idp_promotion blocked, keep controlled_shadow_only_commercial_pretest unchanged, and validate the same now-active short-tau path on a bounded commercial-pretest rerun before any broader rerun."
        if path_activated
        else "Keep broader_full_idp_promotion blocked, keep controlled_shadow_only_commercial_pretest unchanged, and inspect runner/env wiring more deeply because the short-tau diagnostic path still did not activate on base/ph_low."
    )

    summary = {
        "status": "activation_slice_completed_path_active" if path_activated else "activation_slice_completed_path_still_inactive",
        "operator_scope_now": str(packet_s.get("operator_scope_now") or "").strip(),
        "shadow_safe_retained": shadow_safe_retained,
        "broader_promotion_blocked": True,
        "blocking_target": str(packet_s.get("blocking_target") or "tau_k18").strip(),
        "blocking_class": str(packet_s.get("blocking_class") or "corrected_path_fragility").strip(),
        "activation_rule_name": str(packet_s.get("activation_rule_name") or "").strip(),
        "activation_rule_scope": str(packet_s.get("activation_rule_scope") or "").strip(),
        "reference_primary_observation": str(ref_s.get("primary_observation", "")).strip(),
        "activation_corrected_gate_pass": bool(activation_summary.get("corrected_gate_pass", False)),
        "activation_dominant_state_accuracy": float(activation_summary.get("corrected_dominant_state_accuracy", act_cls.get("dominant_state_accuracy", 0.0)) or 0.0),
        "activation_aggregation_flag_pr_auc": float(act_cls.get("aggregation_flag_pr_auc", 0.0) or 0.0),
        "focus_condition_count": focus_count,
        "focus_condition_enabled_count": focus_condition_enabled_count,
        "focus_condition_active_count": focus_condition_active_count,
        "primary_observation": primary_observation,
        "next_required_step": next_required_step,
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Tau K18 Corrected-Path Activation Result",
        "",
        f"- status: `{s['status']}`",
        f"- operator_scope_now: `{s['operator_scope_now']}`",
        f"- shadow_safe_retained: `{s['shadow_safe_retained']}`",
        f"- broader_promotion_blocked: `{s['broader_promotion_blocked']}`",
        f"- blocking_target: `{s['blocking_target']}`",
        f"- blocking_class: `{s['blocking_class']}`",
        f"- activation_rule_name: `{s['activation_rule_name']}`",
        f"- activation_rule_scope: `{s['activation_rule_scope']}`",
        f"- reference_primary_observation: `{s['reference_primary_observation']}`",
        f"- activation_corrected_gate_pass: `{s['activation_corrected_gate_pass']}`",
        f"- activation_dominant_state_accuracy: `{s['activation_dominant_state_accuracy']}`",
        f"- activation_aggregation_flag_pr_auc: `{s['activation_aggregation_flag_pr_auc']}`",
        f"- focus_condition_count: `{s['focus_condition_count']}`",
        f"- focus_condition_enabled_count: `{s['focus_condition_enabled_count']}`",
        f"- focus_condition_active_count: `{s['focus_condition_active_count']}`",
        f"- primary_observation: `{s['primary_observation']}`",
        "",
        "## Focus Conditions",
        "",
        "| condition | true_state | pred_state | diag_enabled | diag_focus_condition | gate_mode | tau_helix_gate | expanded_gate | sticky_gate |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['condition_group']}` | `{row['true_state']}` | `{row['pred_state']}` | `{row['diag_enabled']}` | `{row['diag_focus_condition']}` | `{row['gate_mode']}` | `{row['tau_helix_gate']}` | `{row['expanded_gate']}` | `{row['sticky_gate']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the result artifact for a tau_k18 corrected-path activation-check slice.")
    parser.add_argument("--packet-json", default=DEFAULT_PACKET_JSON)
    parser.add_argument("--reference-result-json", default=DEFAULT_REFERENCE_RESULT_JSON)
    parser.add_argument("--activation-summary-json", default=DEFAULT_ACTIVATION_SUMMARY_JSON)
    parser.add_argument("--activation-gate-json", default=DEFAULT_ACTIVATION_GATE_JSON)
    parser.add_argument("--activation-eval-json", default=DEFAULT_ACTIVATION_EVAL_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.packet_json),
        _load_json(args.reference_result_json),
        _load_json(args.activation_summary_json),
        _load_json(args.activation_gate_json),
        _load_eval_rows(args.activation_eval_json),
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
