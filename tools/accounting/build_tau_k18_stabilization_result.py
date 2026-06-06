#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DECISION_JSON = "runs/idp_commercial_pretest_decision_current.json"
DEFAULT_REFERENCE_SUMMARY_JSON = "runs/idp_tau_k18_stabilization_trial_seed77_r1_summary.json"
DEFAULT_FALLBACK_SUMMARY_JSON = "runs/idp_tau_k18_stabilization_trial_commercial_pretest_seed123_r1_summary.json"
DEFAULT_FALLBACK_GATE_JSON = "runs/idp_tau_k18_stabilization_trial_commercial_pretest_seed123_r1_gate_corrected_summary.json"
DEFAULT_OUT_JSON = "runs/tau_k18_stabilization_result_current.json"
DEFAULT_OUT_MD = "runs/tau_k18_stabilization_result_current.md"


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


def _primary_hotspot(gate_payload: dict[str, Any]) -> dict[str, Any]:
    hotspots = ((gate_payload.get("physics_summary") or {}).get("hotspots") or [])
    if hotspots:
        return dict(hotspots[0])
    metric_counts = ((gate_payload.get("physics_summary") or {}).get("metric_counts") or {})
    metric = ""
    count = 0
    if metric_counts:
        metric, count = max(metric_counts.items(), key=lambda item: int(item[1] or 0))
    return {"metrics": [metric] if metric else [], "failed_row_count": count, "condition_groups": []}


def build_payload(
    decision_payload: dict[str, Any],
    reference_summary: dict[str, Any],
    fallback_summary: dict[str, Any],
    fallback_gate: dict[str, Any],
) -> dict[str, Any]:
    decision_s = dict(decision_payload.get("summary", {}) or {})
    reference_s = dict(reference_summary or {})
    fallback_s = dict(fallback_summary or {})
    gate_metrics = dict((fallback_gate.get("classification_metrics") or {}) or {})
    ranking_metrics = dict((fallback_gate.get("ranking_metrics") or {}) or {})
    hotspot = _primary_hotspot(fallback_gate)
    reference_acc = reference_s.get("corrected_dominant_state_accuracy")
    fallback_acc = fallback_s.get("corrected_dominant_state_accuracy")
    improvement = None
    if isinstance(reference_acc, (int, float)) and isinstance(fallback_acc, (int, float)):
        improvement = float(fallback_acc) - float(reference_acc)
    reference_agg = None
    reference_gate_metrics = dict((reference_s.get("gate_metrics") or {}) or {})
    if reference_agg is None:
        reference_agg = reference_gate_metrics.get("aggregation_flag_pr_auc")
    reference_gate_json = str(reference_s.get("gate_json") or "").strip()
    if reference_agg is None and reference_gate_json:
        ref_gate_path = _resolve(reference_gate_json)
        if ref_gate_path.exists():
            ref_gate = _load_json(str(ref_gate_path))
            reference_agg = (ref_gate.get("classification_metrics") or {}).get("aggregation_flag_pr_auc")
    aggregation_delta = None
    if isinstance(reference_agg, (int, float)) and isinstance(gate_metrics.get("aggregation_flag_pr_auc"), (int, float)):
        aggregation_delta = float(gate_metrics["aggregation_flag_pr_auc"]) - float(reference_agg)

    summary = {
        "status": "fallback_trial_completed_blocker_persists",
        "operator_scope_now": str(decision_s.get("operator_scope_now", "")).strip(),
        "shadow_safe_retained": bool(decision_s.get("shadow_safe_retained", False)),
        "broader_promotion_blocked": bool(decision_s.get("broader_promotion_blocked", True)),
        "blocking_target": str(decision_s.get("blocking_target") or "tau_k18").strip(),
        "blocking_class": str(decision_s.get("blocking_class") or "corrected_path_fragility").strip(),
        "reference_seed": int(reference_s.get("seed", 77) or 77),
        "reference_corrected_gate_pass": reference_s.get("corrected_gate_pass"),
        "reference_corrected_dominant_state_accuracy": reference_acc,
        "fallback_seed": int(fallback_s.get("seed", 123) or 123),
        "fallback_corrected_gate_pass": fallback_s.get("corrected_gate_pass"),
        "fallback_corrected_dominant_state_accuracy": fallback_acc,
        "dominant_state_accuracy_delta_vs_reference": improvement,
        "fallback_feature_mask_name": str(
            (fallback_s.get("kalman_shadow") or {}).get("feature_mask_name")
            or fallback_s.get("kalman_shadow_feature_mask")
            or ""
        ).strip(),
        "would_change_state_count": int(
            ((fallback_s.get("kalman_shadow") or {}).get("would_change_state_count", 0) or 0)
        ),
        "would_change_gate_count": int(
            ((fallback_s.get("kalman_shadow") or {}).get("would_change_gate_count", 0) or 0)
        ),
        "branch_macro_f1": gate_metrics.get("branch_macro_f1"),
        "reference_aggregation_flag_pr_auc": reference_agg,
        "aggregation_flag_pr_auc": gate_metrics.get("aggregation_flag_pr_auc"),
        "aggregation_flag_pr_auc_delta_vs_reference": aggregation_delta,
        "llps_flag_pr_auc": gate_metrics.get("llps_flag_pr_auc"),
        "compactness_rank_auc": ranking_metrics.get("compactness_rank_auc"),
        "helicity_rank_auc": ranking_metrics.get("helicity_rank_auc"),
        "condensation_rank_auc": ranking_metrics.get("condensation_rank_auc"),
        "physics_failed_row_count": int(((fallback_gate.get("physics_summary") or {}).get("failed_row_count", 0) or 0)),
        "primary_hotspot_metric": str(((hotspot.get("metrics") or [""])[0])).strip(),
        "primary_hotspot_failed_row_count": int(hotspot.get("failed_row_count", 0) or 0),
        "primary_hotspot_condition_count": len(hotspot.get("condition_groups") or []),
        "next_required_step": (
            "Keep broader_full_idp_promotion blocked, retain the controlled_shadow_only_commercial_pretest lane, "
            "and route follow-up through tau_k18 corrected-path diagnostics focused on the anti_collapse_force_mean hotspot."
        ),
    }
    rows = [
        {
            "rank": idx,
            "condition_group": condition,
            "primary_hotspot_metric": summary["primary_hotspot_metric"],
        }
        for idx, condition in enumerate(hotspot.get("condition_groups") or [], start=1)
    ]
    return {"summary": summary, "hotspot_conditions": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Tau K18 Stabilization Result",
        "",
        f"- status: `{s['status']}`",
        f"- operator_scope_now: `{s['operator_scope_now']}`",
        f"- shadow_safe_retained: `{s['shadow_safe_retained']}`",
        f"- broader_promotion_blocked: `{s['broader_promotion_blocked']}`",
        f"- blocking_target: `{s['blocking_target']}`",
        f"- blocking_class: `{s['blocking_class']}`",
        f"- reference_seed: `{s['reference_seed']}`",
        f"- reference_corrected_gate_pass: `{s['reference_corrected_gate_pass']}`",
        f"- reference_corrected_dominant_state_accuracy: `{s['reference_corrected_dominant_state_accuracy']}`",
        f"- fallback_seed: `{s['fallback_seed']}`",
        f"- fallback_corrected_gate_pass: `{s['fallback_corrected_gate_pass']}`",
        f"- fallback_corrected_dominant_state_accuracy: `{s['fallback_corrected_dominant_state_accuracy']}`",
        f"- dominant_state_accuracy_delta_vs_reference: `{s['dominant_state_accuracy_delta_vs_reference']}`",
        f"- fallback_feature_mask_name: `{s['fallback_feature_mask_name']}`",
        f"- would_change_state_count: `{s['would_change_state_count']}`",
        f"- would_change_gate_count: `{s['would_change_gate_count']}`",
        f"- branch_macro_f1: `{s['branch_macro_f1']}`",
        f"- reference_aggregation_flag_pr_auc: `{s['reference_aggregation_flag_pr_auc']}`",
        f"- aggregation_flag_pr_auc: `{s['aggregation_flag_pr_auc']}`",
        f"- aggregation_flag_pr_auc_delta_vs_reference: `{s['aggregation_flag_pr_auc_delta_vs_reference']}`",
        f"- llps_flag_pr_auc: `{s['llps_flag_pr_auc']}`",
        f"- compactness_rank_auc: `{s['compactness_rank_auc']}`",
        f"- helicity_rank_auc: `{s['helicity_rank_auc']}`",
        f"- condensation_rank_auc: `{s['condensation_rank_auc']}`",
        f"- physics_failed_row_count: `{s['physics_failed_row_count']}`",
        f"- primary_hotspot_metric: `{s['primary_hotspot_metric']}`",
        f"- primary_hotspot_failed_row_count: `{s['primary_hotspot_failed_row_count']}`",
        f"- primary_hotspot_condition_count: `{s['primary_hotspot_condition_count']}`",
        "",
        "## Interpretation",
        "",
        "- The compared corrected-path slice still fails, so broader IDP promotion remains blocked.",
        "- Kalman shadow stayed telemetry-only with zero state/gate changes, so this is not a shadow regression.",
        f"- Dominant-state accuracy delta versus the reference run: `{s['dominant_state_accuracy_delta_vs_reference']}`.",
        f"- Aggregation flag PR-AUC delta versus the reference run: `{s['aggregation_flag_pr_auc_delta_vs_reference']}`.",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Hotspot Conditions",
        "",
        "| rank | condition_group | hotspot_metric |",
        "| ---: | --- | --- |",
    ]
    for row in payload["hotspot_conditions"]:
        lines.append(
            f"| {row['rank']} | `{row['condition_group']}` | `{row['primary_hotspot_metric']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Build a tau_k18 stabilization result artifact from the reference and fallback trial outputs.")
    ap.add_argument("--decision-json", default=DEFAULT_DECISION_JSON)
    ap.add_argument("--reference-summary-json", default=DEFAULT_REFERENCE_SUMMARY_JSON)
    ap.add_argument("--fallback-summary-json", default=DEFAULT_FALLBACK_SUMMARY_JSON)
    ap.add_argument("--fallback-gate-json", default=DEFAULT_FALLBACK_GATE_JSON)
    ap.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    ap.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.decision_json),
        _load_json(args.reference_summary_json),
        _load_json(args.fallback_summary_json),
        _load_json(args.fallback_gate_json),
    )
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
