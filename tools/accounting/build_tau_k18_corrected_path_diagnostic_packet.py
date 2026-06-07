#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DECISION_JSON = "runs/idp_commercial_pretest_decision_current.json"
DEFAULT_FAILURE_PACKET_JSON = "runs/tau_k18_corrected_condition_failure_packet_current.json"
DEFAULT_REFERENCE_EVAL_JSON = "runs/idp_tau_k18_stabilization_trial_commercial_pretest_seed123_r1_eval_corrected_summary.json"
DEFAULT_OUT_PREFIX = "runs/idp_tau_k18_stabilization_trial_commercial_pretest_seed123_basephlow_diag_r1"
DEFAULT_OUT_JSON = "runs/tau_k18_corrected_path_diagnostic_packet_current.json"
DEFAULT_OUT_CSV = "runs/tau_k18_corrected_path_diagnostic_packet_current.csv"
DEFAULT_OUT_MD = "runs/tau_k18_corrected_path_diagnostic_packet_current.md"

DIAGNOSTIC_RULE_NAME = "short_tau_base_phlow_gate_trace_v1"
DIAGNOSTIC_RULE_SCOPE = "corrected_path_observability_only"
DIAGNOSTIC_SLICE_ID = "fold6_tau_k18_seed123_base_phlow"


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


def _exact_command(out_prefix: str) -> str:
    return " ".join(
        [
            "python3",
            "tools/run_idp_tau_k18_stabilization_trial.py",
            "--eval-config-json",
            str(_resolve("runs/idp_3bead_holdout_v7_anchor_commercial_pretest_r1_fold_inputs/fold6_tau_k18_eval.json")),
            "--out-prefix",
            str(_resolve(out_prefix)),
            "--seed",
            "123",
            "--epochs",
            "120",
            "--patience",
            "24",
            "--lr",
            "0.00075",
            "--weight-decay",
            "1e-05",
            "--kalman-shadow-feature-mask",
            "rg_sasa_only",
        ]
    )


def _focus_rows(reference_eval: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in reference_eval.get("targets", []) or []:
        condition = str(row.get("condition_group", "")).strip()
        if condition not in {"base", "ph_low"}:
            continue
        rows.append(
            {
                "condition_group": condition,
                "true_state": str(row.get("true_dominant_state", "")).strip(),
                "reference_pred_state": str(row.get("pred_state", "")).strip(),
                "reference_dominant_state_label": str(row.get("dominant_state_label", "")).strip(),
                "expected_observation": (
                    "trace_why_base_remains_expanded"
                    if condition == "base"
                    else "trace_why_compact_gap_persists"
                ),
            }
        )
    order = {"base": 0, "ph_low": 1}
    rows.sort(key=lambda row: order.get(row["condition_group"], 99))
    return rows


def build_payload(
    decision_payload: dict[str, Any],
    failure_payload: dict[str, Any],
    reference_eval: dict[str, Any],
    *,
    out_prefix: str,
) -> dict[str, Any]:
    decision_s = dict(decision_payload.get("summary", {}) or {})
    failure_s = dict(failure_payload.get("summary", {}) or {})
    rows = _focus_rows(reference_eval)
    summary = {
        "status": "operator_diagnostic_packet_ready",
        "packet_scope": "tau_k18_corrected_path_single_slice_diagnostic",
        "operator_scope_now": str(decision_s.get("operator_scope_now") or "").strip(),
        "shadow_safe_retained": bool(decision_s.get("shadow_safe_retained", False)),
        "broader_promotion_blocked": bool(decision_s.get("broader_promotion_blocked", True)),
        "blocking_target": str(decision_s.get("blocking_target") or "tau_k18").strip(),
        "blocking_class": str(decision_s.get("blocking_class") or "corrected_path_fragility").strip(),
        "diagnostic_slice_id": DIAGNOSTIC_SLICE_ID,
        "diagnostic_rule_name": DIAGNOSTIC_RULE_NAME,
        "diagnostic_rule_scope": DIAGNOSTIC_RULE_SCOPE,
        "candidate_file": "tools/run_idp_3bead_evaluator.py",
        "candidate_anchor": "tau_k18_diag_* columns on short_tau_target path",
        "reference_corrected_gate_pass": failure_s.get("reference_corrected_gate_pass"),
        "reference_dominant_state_accuracy": failure_s.get("dominant_state_accuracy"),
        "focus_condition_count": len(rows),
        "exact_command": _exact_command(out_prefix),
        "out_prefix": str(_resolve(out_prefix)),
        "decision_reason": (
            "Emit tau_k18-only corrected-path debug columns for the remaining base/ph_low compact-state gap without changing gate or force-policy behavior."
        ),
        "guardrail": (
            "Keep broader_full_idp_promotion blocked and keep controlled_shadow_only_commercial_pretest as the only allowed IDP lane regardless of this slice outcome."
        ),
        "next_required_step": (
            "Run this single tau_k18 observability-only slice, inspect the new tau_k18_diag_* columns for base/ph_low, and only then choose the next corrected-path calibration rule."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Tau K18 Corrected-Path Diagnostic Packet",
        "",
        f"- status: `{s['status']}`",
        f"- packet_scope: `{s['packet_scope']}`",
        f"- operator_scope_now: `{s['operator_scope_now']}`",
        f"- shadow_safe_retained: `{s['shadow_safe_retained']}`",
        f"- broader_promotion_blocked: `{s['broader_promotion_blocked']}`",
        f"- blocking_target: `{s['blocking_target']}`",
        f"- blocking_class: `{s['blocking_class']}`",
        f"- diagnostic_slice_id: `{s['diagnostic_slice_id']}`",
        f"- diagnostic_rule_name: `{s['diagnostic_rule_name']}`",
        f"- diagnostic_rule_scope: `{s['diagnostic_rule_scope']}`",
        f"- candidate_file: `{s['candidate_file']}`",
        f"- candidate_anchor: `{s['candidate_anchor']}`",
        f"- focus_condition_count: `{s['focus_condition_count']}`",
        "",
        "## Why This Slice",
        "",
        f"- {s['decision_reason']}",
        f"- {s['guardrail']}",
        "",
        "## Exact Command",
        "",
        "```bash",
        s["exact_command"],
        "```",
        "",
        "## Focus Conditions",
        "",
        "| condition | true_state | reference_pred_state | expected_observation |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['condition_group']}` | `{row['true_state']}` | `{row['reference_pred_state']}` | `{row['expected_observation']}` |"
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
    parser = argparse.ArgumentParser(description="Build a tau_k18 corrected-path observability-only diagnostic packet.")
    parser.add_argument("--decision-json", default=DEFAULT_DECISION_JSON)
    parser.add_argument("--failure-json", default=DEFAULT_FAILURE_PACKET_JSON)
    parser.add_argument("--reference-eval-json", default=DEFAULT_REFERENCE_EVAL_JSON)
    parser.add_argument("--out-prefix", default=DEFAULT_OUT_PREFIX)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.decision_json),
        _load_json(args.failure_json),
        _load_json(args.reference_eval_json),
        out_prefix=args.out_prefix,
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
