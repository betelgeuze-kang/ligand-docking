#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DECISION_JSON = "runs/idp_commercial_pretest_decision_current.json"
DEFAULT_VALIDATION_RESULT_JSON = "runs/idp_commercial_pretest_validation_result_current.json"
DEFAULT_EVAL_JSON = "runs/idp_3bead_holdout_v7_anchor_commercial_pretest_r16validation_r1_fold6_tau_k18_eval_corrected_summary.json"
DEFAULT_GATE_JSON = "runs/idp_3bead_holdout_v7_anchor_commercial_pretest_r16validation_r1_fold6_tau_k18_gate_corrected_summary.json"
DEFAULT_OUT_JSON = "runs/tau_k18_full_fold_corrected_failure_slice_packet_current.json"
DEFAULT_OUT_CSV = "runs/tau_k18_full_fold_corrected_failure_slice_packet_current.csv"
DEFAULT_OUT_MD = "runs/tau_k18_full_fold_corrected_failure_slice_packet_current.md"


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


def _bool_pred(prob: Any, threshold: float = 0.5) -> int:
    try:
        return 1 if float(prob or 0.0) >= threshold else 0
    except Exception:
        return 0


def build_payload(
    decision_payload: dict[str, Any],
    validation_result: dict[str, Any],
    eval_payload: dict[str, Any],
    gate_payload: dict[str, Any],
) -> dict[str, Any]:
    decision_s = dict((decision_payload.get("summary", {}) if isinstance(decision_payload.get("summary", {}), dict) else {}) or {})
    validation_s = dict((validation_result.get("summary", {}) if isinstance(validation_result.get("summary", {}), dict) else {}) or {})
    gate_cls = dict((gate_payload.get("classification_metrics") or {}) or {})
    rows: list[dict[str, Any]] = []

    for row in eval_payload.get("targets", []) or []:
        condition = str(row.get("condition_group", "")).strip()
        true_state = str(row.get("true_dominant_state", row.get("dominant_state_label", ""))).strip()
        pred_state = str(row.get("pred_state", "")).strip()
        true_agg = int(row.get("true_aggregation_flag", 0) or 0)
        pred_agg = _bool_pred(row.get("pred_aggregation_prob"))
        true_llps = int(row.get("true_llps_flag", 0) or 0)
        pred_llps = _bool_pred(row.get("pred_llps_prob"))
        state_mismatch = true_state != pred_state
        aggregation_mismatch = true_agg != pred_agg
        llps_mismatch = true_llps != pred_llps
        if not (state_mismatch or aggregation_mismatch or llps_mismatch):
            continue
        rows.append(
            {
                "condition_group": condition,
                "true_state": true_state,
                "pred_state": pred_state,
                "state_mismatch": state_mismatch,
                "true_aggregation_flag": true_agg,
                "pred_aggregation_flag": pred_agg,
                "aggregation_mismatch": aggregation_mismatch,
                "true_llps_flag": true_llps,
                "pred_llps_flag": pred_llps,
                "llps_mismatch": llps_mismatch,
                "pred_aggregation_prob": row.get("pred_aggregation_prob"),
                "pred_llps_prob": row.get("pred_llps_prob"),
                "diag_enabled": bool(row.get("tau_k18_diag_enabled", False)),
                "diag_focus_condition": bool(row.get("tau_k18_diag_focus_condition", False)),
                "diag_state_assignment": str(row.get("tau_k18_diag_state_assignment", "")).strip(),
                "tau_helix_gate": bool(row.get("tau_k18_diag_tau_helix_gate", False)),
                "expanded_gate": bool(row.get("tau_k18_diag_expanded_gate", False)),
                "sticky_gate": bool(row.get("tau_k18_diag_sticky_gate", False)),
                "anti_collapse_force_mean": row.get("on_anti_collapse_force_mean"),
                "compactness_score": row.get("compactness_score"),
                "helicity_score": row.get("helicity_score"),
                "condensation_score": row.get("condensation_score"),
            }
        )

    order = {"base": 0, "ph_low": 1, "salt_high": 2, "ph_high": 3, "hydro_high": 4, "cooling": 5}
    rows.sort(key=lambda r: (0 if r["diag_focus_condition"] else 1, order.get(r["condition_group"], 99), r["condition_group"]))

    summary = {
        "status": "full_fold_failure_slice_packet_ready",
        "packet_scope": "tau_k18_full_fold_corrected_failure_slice",
        "operator_scope_now": str(validation_s.get("operator_scope_now", decision_s.get("operator_scope_now", ""))).strip(),
        "shadow_safe_retained": bool(validation_s.get("shadow_safe_retained", decision_s.get("shadow_safe_retained", False))),
        "broader_promotion_blocked": bool(validation_s.get("broader_promotion_blocked", decision_s.get("broader_promotion_blocked", True))),
        "blocking_target": str(validation_s.get("blocking_target", decision_s.get("blocking_target", "tau_k18"))).strip(),
        "blocking_class": str(validation_s.get("blocking_class", decision_s.get("blocking_class", "corrected_path_fragility"))).strip(),
        "activation_observation": str(validation_s.get("activation_observation", decision_s.get("latest_activation_observation", ""))).strip(),
        "tau_k18_corrected_gate_pass": bool(validation_s.get("tau_k18_corrected_gate_pass", gate_payload.get("pass", False))),
        "dominant_state_accuracy": gate_cls.get("dominant_state_accuracy"),
        "aggregation_flag_pr_auc": gate_cls.get("aggregation_flag_pr_auc"),
        "mismatch_row_count": len(rows),
        "focus_row_count": sum(1 for row in rows if row["diag_focus_condition"]),
        "state_mismatch_count": sum(1 for row in rows if row["state_mismatch"]),
        "aggregation_mismatch_count": sum(1 for row in rows if row["aggregation_mismatch"]),
        "llps_mismatch_count": sum(1 for row in rows if row["llps_mismatch"]),
        "next_required_step": (
            "Use this full-fold failure slice to choose exactly one next corrected-path interpretation or calibration rule, preserve the now-active base/ph_low short-tau path, and keep broader_full_idp_promotion blocked until the bounded rerun turns fold-clean."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Tau K18 Full-Fold Corrected Failure Slice Packet",
        "",
        f"- status: `{s['status']}`",
        f"- packet_scope: `{s['packet_scope']}`",
        f"- operator_scope_now: `{s['operator_scope_now']}`",
        f"- shadow_safe_retained: `{s['shadow_safe_retained']}`",
        f"- broader_promotion_blocked: `{s['broader_promotion_blocked']}`",
        f"- blocking_target: `{s['blocking_target']}`",
        f"- blocking_class: `{s['blocking_class']}`",
        f"- activation_observation: `{s['activation_observation']}`",
        f"- tau_k18_corrected_gate_pass: `{s['tau_k18_corrected_gate_pass']}`",
        f"- dominant_state_accuracy: `{s['dominant_state_accuracy']}`",
        f"- aggregation_flag_pr_auc: `{s['aggregation_flag_pr_auc']}`",
        f"- mismatch_row_count: `{s['mismatch_row_count']}`",
        f"- focus_row_count: `{s['focus_row_count']}`",
        f"- state_mismatch_count: `{s['state_mismatch_count']}`",
        f"- aggregation_mismatch_count: `{s['aggregation_mismatch_count']}`",
        f"- llps_mismatch_count: `{s['llps_mismatch_count']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Failure Slice",
        "",
        "| condition | true_state | pred_state | state_mismatch | agg_true | agg_pred | agg_prob | focus | diag_state_assignment | anti_collapse_force_mean |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | --- | --- | ---: |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['condition_group']}` | `{row['true_state']}` | `{row['pred_state']}` | `{row['state_mismatch']}` | "
            f"{row['true_aggregation_flag']} | {row['pred_aggregation_flag']} | {row['pred_aggregation_prob']} | "
            f"`{row['diag_focus_condition']}` | `{row['diag_state_assignment']}` | {row['anti_collapse_force_mean']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a tau_k18 full-fold corrected failure slice packet.")
    parser.add_argument("--decision-json", default=DEFAULT_DECISION_JSON)
    parser.add_argument("--validation-result-json", default=DEFAULT_VALIDATION_RESULT_JSON)
    parser.add_argument("--eval-json", default=DEFAULT_EVAL_JSON)
    parser.add_argument("--gate-json", default=DEFAULT_GATE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.decision_json),
        _load_json(args.validation_result_json),
        _load_json(args.eval_json),
        _load_json(args.gate_json),
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
