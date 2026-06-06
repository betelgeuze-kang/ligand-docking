#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DECISION_JSON = "runs/idp_commercial_pretest_decision_current.json"
DEFAULT_GATE_JSON = "runs/idp_tau_k18_stabilization_trial_commercial_pretest_seed123_r1_gate_corrected_summary.json"
DEFAULT_EVAL_JSON = "runs/idp_tau_k18_stabilization_trial_commercial_pretest_seed123_r1_eval_corrected_summary.json"
DEFAULT_OUT_JSON = "runs/tau_k18_corrected_condition_failure_packet_current.json"
DEFAULT_OUT_CSV = "runs/tau_k18_corrected_condition_failure_packet_current.csv"
DEFAULT_OUT_MD = "runs/tau_k18_corrected_condition_failure_packet_current.md"


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


def build_payload(
    decision_payload: dict[str, Any],
    gate_payload: dict[str, Any],
    eval_payload: dict[str, Any],
) -> dict[str, Any]:
    decision_s = dict(decision_payload.get("summary", {}) or {})
    gate_metrics = dict((gate_payload.get("classification_metrics") or {}) or {})
    eval_targets = {
        str(row.get("condition_group", "")).strip(): dict(row)
        for row in eval_payload.get("targets", []) or []
        if str(row.get("condition_group", "")).strip()
    }

    hotspot = (((gate_payload.get("physics_summary") or {}).get("hotspots") or []) or [{}])[0]
    hotspot_metric = str(((hotspot.get("metrics") or [""])[0])).strip()

    rows: list[dict[str, Any]] = []
    for idx, failed in enumerate(gate_payload.get("failed_targets", []) or [], start=1):
        condition_group = str(failed.get("condition_group", "")).strip()
        eval_row = eval_targets.get(condition_group, {})
        rows.append(
            {
                "packet_rank": idx,
                "condition_group": condition_group,
                "true_dominant_state": str(eval_row.get("true_dominant_state", "")).strip(),
                "pred_state": str(eval_row.get("pred_state", "")).strip(),
                "dominant_state_label": str(eval_row.get("dominant_state_label", "")).strip(),
                "pred_llps_prob": eval_row.get("pred_llps_prob"),
                "pred_aggregation_prob": eval_row.get("pred_aggregation_prob"),
                "pred_rank_compactness": eval_row.get("pred_rank_compactness"),
                "pred_rank_helicity": eval_row.get("pred_rank_helicity"),
                "pred_rank_condensation": eval_row.get("pred_rank_condensation"),
                "on_anti_collapse_force_mean": eval_row.get("on_anti_collapse_force_mean"),
                "on_anti_collapse_rg_target_A": eval_row.get("on_anti_collapse_rg_target_A"),
                "conditional_anti_collapse_scale": eval_row.get("conditional_anti_collapse_scale"),
                "target_pass": bool(eval_row.get("target_pass", False)),
                "residual_target_pass": bool(eval_row.get("residual_target_pass", False)),
                "would_have_changed_state": bool(eval_row.get("would_have_changed_state", False)),
                "would_have_changed_gate": bool(eval_row.get("would_have_changed_gate", False)),
                "primary_hotspot_metric": hotspot_metric,
            }
        )

    summary = {
        "status": "diagnostic_packet_ready",
        "packet_scope": "tau_k18_corrected_path_condition_failure_diagnostic",
        "operator_scope_now": str(decision_s.get("operator_scope_now", "")).strip(),
        "shadow_safe_retained": bool(decision_s.get("shadow_safe_retained", False)),
        "broader_promotion_blocked": bool(decision_s.get("broader_promotion_blocked", True)),
        "blocking_target": str(decision_s.get("blocking_target") or "tau_k18").strip(),
        "failed_condition_count": len(rows),
        "primary_hotspot_metric": hotspot_metric,
        "branch_macro_f1": gate_metrics.get("branch_macro_f1"),
        "dominant_state_accuracy": gate_metrics.get("dominant_state_accuracy"),
        "aggregation_flag_pr_auc": gate_metrics.get("aggregation_flag_pr_auc"),
        "llps_flag_pr_auc": gate_metrics.get("llps_flag_pr_auc"),
        "next_required_step": (
            "Audit these failed corrected-path conditions, keep broader_full_idp_promotion blocked, and route follow-up work through exactly one minimal corrected-path diagnostic or calibration slice before any broader IDP rerun."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Tau K18 Corrected-Path Condition Failure Packet",
        "",
        f"- status: `{s['status']}`",
        f"- packet_scope: `{s['packet_scope']}`",
        f"- operator_scope_now: `{s['operator_scope_now']}`",
        f"- shadow_safe_retained: `{s['shadow_safe_retained']}`",
        f"- broader_promotion_blocked: `{s['broader_promotion_blocked']}`",
        f"- blocking_target: `{s['blocking_target']}`",
        f"- failed_condition_count: `{s['failed_condition_count']}`",
        f"- primary_hotspot_metric: `{s['primary_hotspot_metric']}`",
        f"- branch_macro_f1: `{s['branch_macro_f1']}`",
        f"- dominant_state_accuracy: `{s['dominant_state_accuracy']}`",
        f"- aggregation_flag_pr_auc: `{s['aggregation_flag_pr_auc']}`",
        f"- llps_flag_pr_auc: `{s['llps_flag_pr_auc']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Failed Conditions",
        "",
        "| rank | condition | true_state | pred_state | pred_aggregation_prob | anti_collapse_force | residual_pass | state_change | gate_change |",
        "| ---: | --- | --- | --- | ---: | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['packet_rank']} | `{row['condition_group']}` | `{row['true_dominant_state']}` | "
            f"`{row['pred_state']}` | {row['pred_aggregation_prob']} | {row['on_anti_collapse_force_mean']} | "
            f"`{row['residual_target_pass']}` | `{row['would_have_changed_state']}` | `{row['would_have_changed_gate']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Build a condition-level failure packet for tau_k18 corrected-path diagnostics.")
    ap.add_argument("--decision-json", default=DEFAULT_DECISION_JSON)
    ap.add_argument("--gate-json", default=DEFAULT_GATE_JSON)
    ap.add_argument("--eval-json", default=DEFAULT_EVAL_JSON)
    ap.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    ap.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    ap.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.decision_json),
        _load_json(args.gate_json),
        _load_json(args.eval_json),
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
