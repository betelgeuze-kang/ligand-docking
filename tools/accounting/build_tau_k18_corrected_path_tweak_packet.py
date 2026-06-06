#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DECISION_JSON = "runs/idp_commercial_pretest_decision_current.json"
DEFAULT_RESULT_JSON = "runs/tau_k18_stabilization_result_current.json"
DEFAULT_FAILURE_PACKET_JSON = "runs/tau_k18_corrected_condition_failure_packet_current.json"
DEFAULT_BASE_FORCE_POLICY_JSON = "config/idp_branch_force_policy_v1.json"
DEFAULT_BASE_EVAL_CONFIG_JSON = "runs/idp_3bead_holdout_v7_anchor_commercial_pretest_r1_fold_inputs/fold6_tau_k18_eval.json"
DEFAULT_OUT_FORCE_POLICY_JSON = "runs/idp_branch_force_policy_tau_k18_antispread195_current.json"
DEFAULT_OUT_EVAL_CONFIG_JSON = "runs/tau_k18_corrected_path_antispread195_eval_current.json"
DEFAULT_OUT_PREFIX = "runs/idp_tau_k18_stabilization_trial_commercial_pretest_seed123_antispread195_r1"
DEFAULT_OUT_JSON = "runs/tau_k18_corrected_path_tweak_packet_current.json"
DEFAULT_OUT_CSV = "runs/tau_k18_corrected_path_tweak_packet_current.csv"
DEFAULT_OUT_MD = "runs/tau_k18_corrected_path_tweak_packet_current.md"


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


def _clone_force_policy(base_policy: dict[str, Any], *, tweak_field_name: str, new_value: float) -> dict[str, Any]:
    cloned = json.loads(json.dumps(base_policy))
    overrides = dict(cloned.get("target_overrides", {}) or {})
    tau = dict(overrides.get("tau_k18", {}) or {})
    tau[str(tweak_field_name)] = float(new_value)
    overrides["tau_k18"] = tau
    cloned["target_overrides"] = overrides
    return cloned


def _clone_eval_config(base_eval_config: dict[str, Any], *, out_force_policy_json: str) -> dict[str, Any]:
    cloned = json.loads(json.dumps(base_eval_config))
    runtime = dict(cloned.get("runtime", {}) or {})
    runtime["idp_branch_force_policy_json"] = str(_resolve(out_force_policy_json))
    cloned["runtime"] = runtime
    return cloned


def _build_exact_command(out_eval_config_json: str, out_prefix: str) -> str:
    return " ".join(
        [
            "python3",
            "tools/run_idp_tau_k18_stabilization_trial.py",
            "--eval-config-json",
            str(_resolve(out_eval_config_json)),
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


def _build_tweak_rationale(tweak_field_name: str, original_value: Any, new_value: float) -> str:
    field = str(tweak_field_name).strip()
    if field == "anti_spread_scale":
        return (
            "The rg_target_multiplier trial moved tau_k18 target geometry but left anti_collapse_force_mean unchanged, "
            "so the next narrow config-only probe is the inward overspread correction amplitude. "
            f"Raise tau_k18 {field} from {original_value} to {new_value} to test whether the unchanged hotspot is really "
            "coming from the anti-spread branch without broadening the lane or changing Kalman behavior."
        )
    if field == "rg_target_multiplier":
        return (
            "Raise tau_k18 rg_target_multiplier from 0.96 to 1.00 before touching force amplitude. "
            "This is the narrowest config-only move for the anti_collapse_force_mean hotspot because it relaxes the "
            "tau_k18-specific suppressed target geometry without broadening the lane or changing Kalman behavior."
        )
    return (
        f"Change tau_k18 {field} from {original_value} to {new_value} as a single corrected-path-only config tweak. "
        "Keep the same fold, seed, Kalman mask, and operator lane so the effect stays attributable."
    )


def build_payload(
    decision_payload: dict[str, Any],
    result_payload: dict[str, Any],
    failure_payload: dict[str, Any],
    base_force_policy: dict[str, Any],
    *,
    out_force_policy_json: str,
    out_eval_config_json: str,
    out_prefix: str,
    tweak_field_name: str = "anti_spread_scale",
    new_value: float = 1.95,
) -> dict[str, Any]:
    decision_s = dict(decision_payload.get("summary", {}) or {})
    result_s = dict(result_payload.get("summary", {}) or {})
    failure_s = dict(failure_payload.get("summary", {}) or {})
    original_value = (
        (base_force_policy.get("target_overrides", {}) or {})
        .get("tau_k18", {})
        .get(str(tweak_field_name))
    )
    exact_command = _build_exact_command(out_eval_config_json, out_prefix)

    rows: list[dict[str, Any]] = []
    for row in failure_payload.get("rows", []) or []:
        rows.append(
            {
                "condition_group": str(row.get("condition_group", "")).strip(),
                "true_dominant_state": str(row.get("true_dominant_state", "")).strip(),
                "pred_state": str(row.get("pred_state", "")).strip(),
                "pred_aggregation_prob": row.get("pred_aggregation_prob"),
                "on_anti_collapse_force_mean": row.get("on_anti_collapse_force_mean"),
                "on_anti_collapse_rg_target_A": row.get("on_anti_collapse_rg_target_A"),
                "conditional_anti_collapse_scale": row.get("conditional_anti_collapse_scale"),
                "residual_target_pass": bool(row.get("residual_target_pass", False)),
                "would_have_changed_state": bool(row.get("would_have_changed_state", False)),
                "would_have_changed_gate": bool(row.get("would_have_changed_gate", False)),
            }
        )

    summary = {
        "status": "operator_tweak_packet_ready",
        "packet_scope": "tau_k18_corrected_path_single_tweak_force_policy_override",
        "operator_scope_now": str(decision_s.get("operator_scope_now") or "").strip(),
        "shadow_safe_retained": bool(decision_s.get("shadow_safe_retained", False)),
        "broader_promotion_blocked": bool(decision_s.get("broader_promotion_blocked", True)),
        "blocking_target": str(decision_s.get("blocking_target") or "tau_k18").strip(),
        "blocking_class": str(decision_s.get("blocking_class") or "corrected_path_fragility").strip(),
        "hotspot_metric": str(result_s.get("primary_hotspot_metric") or failure_s.get("primary_hotspot_metric") or "").strip(),
        "tweak_field": f"target_overrides.tau_k18.{tweak_field_name}",
        "original_value": original_value,
        "tweaked_value": float(new_value),
        "tweak_rationale": _build_tweak_rationale(tweak_field_name, original_value, float(new_value)),
        "result_reference_status": str(result_s.get("status") or "").strip(),
        "result_reference_dominant_state_accuracy": result_s.get("fallback_corrected_dominant_state_accuracy"),
        "result_reference_branch_macro_f1": result_s.get("branch_macro_f1"),
        "result_reference_llps_flag_pr_auc": result_s.get("llps_flag_pr_auc"),
        "exact_command": exact_command,
        "out_force_policy_json": str(_resolve(out_force_policy_json)),
        "out_eval_config_json": str(_resolve(out_eval_config_json)),
        "out_prefix": str(_resolve(out_prefix)),
        "next_required_step": (
            "Run this one corrected-path-only tau_k18 slice, compare it against the no-tweak seed123 trial, "
            "and keep broader_full_idp_promotion blocked unless corrected_gate_pass flips to true."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Tau K18 Corrected-Path Tweak Packet",
        "",
        f"- status: `{s['status']}`",
        f"- packet_scope: `{s['packet_scope']}`",
        f"- operator_scope_now: `{s['operator_scope_now']}`",
        f"- shadow_safe_retained: `{s['shadow_safe_retained']}`",
        f"- broader_promotion_blocked: `{s['broader_promotion_blocked']}`",
        f"- blocking_target: `{s['blocking_target']}`",
        f"- blocking_class: `{s['blocking_class']}`",
        f"- hotspot_metric: `{s['hotspot_metric']}`",
        f"- tweak_field: `{s['tweak_field']}`",
        f"- original_value: `{s['original_value']}`",
        f"- tweaked_value: `{s['tweaked_value']}`",
        "",
        "## Rationale",
        "",
        f"- {s['tweak_rationale']}",
        "",
        "## Reference Failure",
        "",
        f"- result_reference_status: `{s['result_reference_status']}`",
        f"- result_reference_dominant_state_accuracy: `{s['result_reference_dominant_state_accuracy']}`",
        f"- result_reference_branch_macro_f1: `{s['result_reference_branch_macro_f1']}`",
        f"- result_reference_llps_flag_pr_auc: `{s['result_reference_llps_flag_pr_auc']}`",
        "",
        "## Outputs",
        "",
        f"- out_force_policy_json: `{s['out_force_policy_json']}`",
        f"- out_eval_config_json: `{s['out_eval_config_json']}`",
        f"- out_prefix: `{s['out_prefix']}`",
        "",
        "## Exact Command",
        "",
        "```bash",
        s["exact_command"],
        "```",
        "",
        "## Guardrail",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Failed Conditions To Recheck",
        "",
        "| condition | true_state | pred_state | pred_aggregation_prob | anti_collapse_force | anti_collapse_rg_target | residual_pass | state_change | gate_change |",
        "| --- | --- | --- | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['condition_group']}` | `{row['true_dominant_state']}` | `{row['pred_state']}` | "
            f"{row['pred_aggregation_prob']} | {row['on_anti_collapse_force_mean']} | {row['on_anti_collapse_rg_target_A']} | "
            f"`{row['residual_target_pass']}` | `{row['would_have_changed_state']}` | `{row['would_have_changed_gate']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Build a tau_k18 corrected-path single-tweak packet and its cloned config inputs.")
    ap.add_argument("--decision-json", default=DEFAULT_DECISION_JSON)
    ap.add_argument("--result-json", default=DEFAULT_RESULT_JSON)
    ap.add_argument("--failure-packet-json", default=DEFAULT_FAILURE_PACKET_JSON)
    ap.add_argument("--base-force-policy-json", default=DEFAULT_BASE_FORCE_POLICY_JSON)
    ap.add_argument("--base-eval-config-json", default=DEFAULT_BASE_EVAL_CONFIG_JSON)
    ap.add_argument("--out-force-policy-json", default=DEFAULT_OUT_FORCE_POLICY_JSON)
    ap.add_argument("--out-eval-config-json", default=DEFAULT_OUT_EVAL_CONFIG_JSON)
    ap.add_argument("--out-prefix", default=DEFAULT_OUT_PREFIX)
    ap.add_argument("--tweak-field-name", default="anti_spread_scale")
    ap.add_argument("--new-value", type=float, default=1.95)
    ap.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    ap.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    ap.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    base_force_policy = _load_json(args.base_force_policy_json)
    base_eval_config = _load_json(args.base_eval_config_json)
    tweaked_force_policy = _clone_force_policy(
        base_force_policy,
        tweak_field_name=args.tweak_field_name,
        new_value=args.new_value,
    )
    tweaked_eval_config = _clone_eval_config(
        base_eval_config,
        out_force_policy_json=args.out_force_policy_json,
    )

    out_force_policy = _resolve(args.out_force_policy_json)
    out_eval_config = _resolve(args.out_eval_config_json)
    out_force_policy.parent.mkdir(parents=True, exist_ok=True)
    out_eval_config.parent.mkdir(parents=True, exist_ok=True)
    out_force_policy.write_text(json.dumps(tweaked_force_policy, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    out_eval_config.write_text(json.dumps(tweaked_eval_config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    payload = build_payload(
        _load_json(args.decision_json),
        _load_json(args.result_json),
        _load_json(args.failure_packet_json),
        base_force_policy,
        out_force_policy_json=args.out_force_policy_json,
        out_eval_config_json=args.out_eval_config_json,
        out_prefix=args.out_prefix,
        tweak_field_name=args.tweak_field_name,
        new_value=args.new_value,
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
