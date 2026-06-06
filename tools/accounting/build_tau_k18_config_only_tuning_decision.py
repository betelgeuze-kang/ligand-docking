#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_COMMERCIAL_PRETEST_DECISION_JSON = "runs/idp_commercial_pretest_decision_current.json"
DEFAULT_NO_TWEAK_GATE_JSON = "runs/idp_tau_k18_stabilization_trial_commercial_pretest_seed123_r1_gate_corrected_summary.json"
DEFAULT_RG_TARGET_GATE_JSON = "runs/idp_tau_k18_stabilization_trial_commercial_pretest_seed123_rgtarget100_r1_gate_corrected_summary.json"
DEFAULT_ANTI_SPREAD_GATE_JSON = "runs/idp_tau_k18_stabilization_trial_commercial_pretest_seed123_antispread195_r1_gate_corrected_summary.json"
DEFAULT_OUT_JSON = "runs/tau_k18_config_only_tuning_decision_current.json"
DEFAULT_OUT_MD = "runs/tau_k18_config_only_tuning_decision_current.md"


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


def _metrics(gate_payload: dict[str, Any]) -> dict[str, Any]:
    cls = dict((gate_payload.get("classification_metrics") or {}) or {})
    hot = (((gate_payload.get("physics_summary") or {}).get("hotspots") or [{}]) or [{}])[0]
    return {
        "pass": bool(gate_payload.get("pass", False)),
        "branch_macro_f1": cls.get("branch_macro_f1"),
        "dominant_state_accuracy": cls.get("dominant_state_accuracy"),
        "llps_flag_pr_auc": cls.get("llps_flag_pr_auc"),
        "aggregation_flag_pr_auc": cls.get("aggregation_flag_pr_auc"),
        "primary_hotspot_metric": str(((hot.get("metrics") or [""])[0])).strip(),
        "primary_hotspot_failed_row_count": int(hot.get("failed_row_count", 0) or 0),
    }


def build_payload(
    commercial_pretest_decision: dict[str, Any],
    no_tweak_gate: dict[str, Any],
    rg_target_gate: dict[str, Any],
    anti_spread_gate: dict[str, Any],
) -> dict[str, Any]:
    decision_s = dict((commercial_pretest_decision.get("summary") or {}) or {})
    no_tweak = _metrics(no_tweak_gate)
    rg_target = _metrics(rg_target_gate)
    anti_spread = _metrics(anti_spread_gate)
    best_agg = max(
        (
            ("no_tweak", no_tweak.get("aggregation_flag_pr_auc")),
            ("rg_target_multiplier", rg_target.get("aggregation_flag_pr_auc")),
            ("anti_spread_scale", anti_spread.get("aggregation_flag_pr_auc")),
        ),
        key=lambda item: float(item[1] or float("-inf")),
    )
    summary = {
        "status": "config_only_force_policy_tuning_exhausted",
        "operator_scope_now": str(decision_s.get("operator_scope_now") or "").strip(),
        "shadow_safe_retained": bool(decision_s.get("shadow_safe_retained", False)),
        "broader_promotion_blocked": bool(decision_s.get("broader_promotion_blocked", True)),
        "blocking_target": str(decision_s.get("blocking_target") or "tau_k18").strip(),
        "attempted_tweak_count": 2,
        "attempted_tweak_fields": [
            "target_overrides.tau_k18.rg_target_multiplier",
            "target_overrides.tau_k18.anti_spread_scale",
        ],
        "no_tweak_dominant_state_accuracy": no_tweak.get("dominant_state_accuracy"),
        "rg_target_dominant_state_accuracy": rg_target.get("dominant_state_accuracy"),
        "anti_spread_dominant_state_accuracy": anti_spread.get("dominant_state_accuracy"),
        "no_tweak_aggregation_flag_pr_auc": no_tweak.get("aggregation_flag_pr_auc"),
        "rg_target_aggregation_flag_pr_auc": rg_target.get("aggregation_flag_pr_auc"),
        "anti_spread_aggregation_flag_pr_auc": anti_spread.get("aggregation_flag_pr_auc"),
        "hotspot_metric_consensus": no_tweak.get("primary_hotspot_metric"),
        "config_only_force_policy_tuning_exhausted": True,
        "best_aggregation_variant": str(best_agg[0]),
        "best_aggregation_flag_pr_auc": best_agg[1],
        "blocker_reason": (
            "tau_k18 corrected-path fragility remains the blocker. Two single config-only force-policy tweaks "
            "did not change corrected_gate_pass or dominant_state_accuracy, and the hotspot stayed anti_collapse_force_mean."
        ),
        "next_required_step": (
            "Stop config-only force-policy tuning for tau_k18, keep broader_full_idp_promotion blocked, "
            "and move follow-up work to a corrected-path diagnostic or calibration slice."
        ),
    }
    rows = [
        {"trial": "no_tweak", **no_tweak},
        {"trial": "rg_target_multiplier", **rg_target},
        {"trial": "anti_spread_scale", **anti_spread},
    ]
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Tau K18 Config-Only Tuning Decision",
        "",
        f"- status: `{s['status']}`",
        f"- operator_scope_now: `{s['operator_scope_now']}`",
        f"- shadow_safe_retained: `{s['shadow_safe_retained']}`",
        f"- broader_promotion_blocked: `{s['broader_promotion_blocked']}`",
        f"- blocking_target: `{s['blocking_target']}`",
        f"- attempted_tweak_count: `{s['attempted_tweak_count']}`",
        f"- hotspot_metric_consensus: `{s['hotspot_metric_consensus']}`",
        f"- best_aggregation_variant: `{s['best_aggregation_variant']}`",
        f"- best_aggregation_flag_pr_auc: `{s['best_aggregation_flag_pr_auc']}`",
        f"- config_only_force_policy_tuning_exhausted: `{s['config_only_force_policy_tuning_exhausted']}`",
        "",
        s["blocker_reason"],
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Trials",
        "",
        "| trial | pass | dominant_state_accuracy | aggregation_flag_pr_auc | llps_flag_pr_auc | hotspot |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['trial']}` | `{row['pass']}` | {row['dominant_state_accuracy']} | "
            f"{row['aggregation_flag_pr_auc']} | {row['llps_flag_pr_auc']} | `{row['primary_hotspot_metric']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Build a stop/go decision for tau_k18 config-only force-policy tuning.")
    ap.add_argument("--commercial-pretest-decision-json", default=DEFAULT_COMMERCIAL_PRETEST_DECISION_JSON)
    ap.add_argument("--no-tweak-gate-json", default=DEFAULT_NO_TWEAK_GATE_JSON)
    ap.add_argument("--rg-target-gate-json", default=DEFAULT_RG_TARGET_GATE_JSON)
    ap.add_argument("--anti-spread-gate-json", default=DEFAULT_ANTI_SPREAD_GATE_JSON)
    ap.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    ap.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.commercial_pretest_decision_json),
        _load_json(args.no_tweak_gate_json),
        _load_json(args.rg_target_gate_json),
        _load_json(args.anti_spread_gate_json),
    )
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
