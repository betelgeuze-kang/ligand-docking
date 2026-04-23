#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DECISION_JSON = "runs/idp_commercial_pretest_decision_current.json"
DEFAULT_DIAGNOSTIC_RESULT_JSON = "runs/tau_k18_corrected_path_diagnostic_result_current.json"
DEFAULT_REFERENCE_EVAL_JSON = "runs/idp_tau_k18_stabilization_trial_commercial_pretest_seed123_basephlow_diag_r1_eval_corrected_summary.json"
DEFAULT_OUT_PREFIX = "runs/idp_tau_k18_activation_trial_commercial_pretest_seed123_r16patch_r1"
DEFAULT_OUT_JSON = "runs/tau_k18_corrected_path_activation_packet_current.json"
DEFAULT_OUT_CSV = "runs/tau_k18_corrected_path_activation_packet_current.csv"
DEFAULT_OUT_MD = "runs/tau_k18_corrected_path_activation_packet_current.md"

ACTIVATION_RULE_NAME = "short_tau_diag_r16_activation_v1"
ACTIVATION_RULE_SCOPE = "corrected_path_observability_only_env_gate"
ACTIVATION_SLICE_ID = "fold6_tau_k18_seed123_base_phlow_r16patch"


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
            "--idp-r16-ml-patch",
            "1",
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
                "true_state": str(row.get("dominant_state_label", row.get("true_state", ""))).strip(),
                "reference_pred_state": str(row.get("pred_state", "")).strip(),
                "reference_diag_enabled": bool(row.get("tau_k18_diag_enabled", False)),
                "expected_observation": (
                    "confirm_short_tau_diag_activation_for_base"
                    if condition == "base"
                    else "confirm_short_tau_diag_activation_for_ph_low"
                ),
            }
        )
    order = {"base": 0, "ph_low": 1}
    rows.sort(key=lambda row: order.get(row["condition_group"], 99))
    return rows


def build_payload(
    decision_payload: dict[str, Any],
    diagnostic_result_payload: dict[str, Any],
    reference_eval_payload: dict[str, Any],
    *,
    out_prefix: str,
) -> dict[str, Any]:
    decision_s = dict(decision_payload.get("summary", {}) or {})
    diagnostic_s = dict(diagnostic_result_payload.get("summary", {}) or {})
    rows = _focus_rows(reference_eval_payload)
    summary = {
        "status": "operator_activation_packet_ready",
        "packet_scope": "tau_k18_corrected_path_single_slice_activation_check",
        "operator_scope_now": str(decision_s.get("operator_scope_now") or "").strip(),
        "shadow_safe_retained": bool(decision_s.get("shadow_safe_retained", False)),
        "broader_promotion_blocked": bool(decision_s.get("broader_promotion_blocked", True)),
        "blocking_target": str(decision_s.get("blocking_target") or "tau_k18").strip(),
        "blocking_class": str(decision_s.get("blocking_class") or "corrected_path_fragility").strip(),
        "activation_slice_id": ACTIVATION_SLICE_ID,
        "activation_rule_name": ACTIVATION_RULE_NAME,
        "activation_rule_scope": ACTIVATION_RULE_SCOPE,
        "candidate_file": "tools/run_idp_tau_k18_stabilization_trial.py",
        "candidate_anchor": "IDP_R16_ML_PATCH env passthrough into run_idp_3bead_evaluator.py",
        "reference_primary_observation": str(diagnostic_s.get("primary_observation", "")).strip(),
        "reference_inactive_short_tau_diag_count": diagnostic_s.get("inactive_short_tau_diag_count"),
        "focus_condition_count": len(rows),
        "exact_command": _exact_command(out_prefix),
        "out_prefix": str(_resolve(out_prefix)),
        "decision_reason": (
            "Re-run the exact same tau_k18 base/ph_low observability slice, but force IDP_R16_ML_PATCH=1 so we can tell whether the short-tau diagnostic path was simply never activated by the runner."
        ),
        "guardrail": (
            "Keep broader_full_idp_promotion blocked and keep controlled_shadow_only_commercial_pretest as the only allowed IDP lane regardless of this slice outcome."
        ),
        "next_required_step": (
            "Run this single activation-check slice, verify tau_k18_diag_enabled becomes true on base/ph_low, and only then decide whether the next smallest follow-up should be a calibration rule or a deeper gating/path diagnostic."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Tau K18 Corrected-Path Activation Packet",
        "",
        f"- status: `{s['status']}`",
        f"- packet_scope: `{s['packet_scope']}`",
        f"- operator_scope_now: `{s['operator_scope_now']}`",
        f"- shadow_safe_retained: `{s['shadow_safe_retained']}`",
        f"- broader_promotion_blocked: `{s['broader_promotion_blocked']}`",
        f"- blocking_target: `{s['blocking_target']}`",
        f"- blocking_class: `{s['blocking_class']}`",
        f"- activation_slice_id: `{s['activation_slice_id']}`",
        f"- activation_rule_name: `{s['activation_rule_name']}`",
        f"- activation_rule_scope: `{s['activation_rule_scope']}`",
        f"- reference_primary_observation: `{s['reference_primary_observation']}`",
        f"- reference_inactive_short_tau_diag_count: `{s['reference_inactive_short_tau_diag_count']}`",
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
        "| condition | true_state | reference_pred_state | reference_diag_enabled | expected_observation |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['condition_group']}` | `{row['true_state']}` | `{row['reference_pred_state']}` | `{row['reference_diag_enabled']}` | `{row['expected_observation']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a tau_k18 corrected-path activation-check packet.")
    parser.add_argument("--decision-json", default=DEFAULT_DECISION_JSON)
    parser.add_argument("--diagnostic-result-json", default=DEFAULT_DIAGNOSTIC_RESULT_JSON)
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
        _load_json(args.diagnostic_result_json),
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
