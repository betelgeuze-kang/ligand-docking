#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CURRENT_GATE_JSON = "runs/idp_3bead_holdout_v7_kfshadow_2026-03-26_r1_fold19_page4_gate_corrected_summary.json"
DEFAULT_BASELINE_GATE_JSON = "runs/idp_3bead_holdout_v7_sb_rust_2026-03-20_r3_speedopt3_fold19_page4_gate_corrected_summary.json"
DEFAULT_CURRENT_TARGETS_CSV = "runs/idp_3bead_holdout_v7_kfshadow_2026-03-26_r1_fold19_page4_eval_corrected_targets.csv"
DEFAULT_BASELINE_TARGETS_CSV = "runs/idp_3bead_holdout_v7_sb_rust_2026-03-20_r3_speedopt3_fold19_page4_eval_corrected_targets.csv"
DEFAULT_OUT_JSON = "runs/idp_fold19_page4_failure_analysis_current.json"
DEFAULT_OUT_CSV = "runs/idp_fold19_page4_failure_analysis_current.csv"
DEFAULT_OUT_MD = "runs/idp_fold19_page4_failure_analysis_current.md"


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


def _read_csv(path_like: str) -> list[dict[str, Any]]:
    with _resolve(path_like).open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _float(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key, default) or default)
    except (TypeError, ValueError):
        return float(default)


def _int(row: dict[str, Any], key: str, default: int = 0) -> int:
    try:
        return int(float(row.get(key, default) or default))
    except (TypeError, ValueError):
        return int(default)


def _boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    raw = str(value or "").strip().lower()
    return raw in {"1", "true", "yes", "y", "on"}


def _pred_state_from_row(row: dict[str, Any]) -> str:
    prob_pairs: list[tuple[str, float]] = []
    for prefix in ("pred_state_prob_", "kf_pred_state_prob_"):
        for key, value in row.items():
            if not key.startswith(prefix):
                continue
            state_name = key[len(prefix) :]
            prob_pairs.append((state_name, _float(row, key)))
        if prob_pairs:
            break
    if not prob_pairs:
        return ""
    prob_pairs.sort(key=lambda item: item[1], reverse=True)
    return str(prob_pairs[0][0])


def build_payload(
    current_gate: dict[str, Any],
    baseline_gate: dict[str, Any],
    current_rows: list[dict[str, Any]],
    baseline_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    current_map = {str(row.get("condition_group", "")): row for row in current_rows}
    baseline_map = {str(row.get("condition_group", "")): row for row in baseline_rows}
    condition_groups = sorted(set(current_map) | set(baseline_map))
    row_deltas: list[dict[str, Any]] = []
    regressed_conditions: list[str] = []
    improved_conditions: list[str] = []
    current_wrong: list[str] = []
    baseline_wrong: list[str] = []

    for condition_group in condition_groups:
        current_row = current_map.get(condition_group, {})
        baseline_row = baseline_map.get(condition_group, {})
        true_state = str(current_row.get("true_dominant_state", baseline_row.get("true_dominant_state", "")))
        current_pred_state = _pred_state_from_row(current_row)
        baseline_pred_state = _pred_state_from_row(baseline_row)
        current_correct = bool(current_pred_state) and current_pred_state == true_state
        baseline_correct = bool(baseline_pred_state) and baseline_pred_state == true_state
        if not current_correct:
            current_wrong.append(condition_group)
        if not baseline_correct:
            baseline_wrong.append(condition_group)
        if baseline_correct and not current_correct:
            regressed_conditions.append(condition_group)
        if current_correct and not baseline_correct:
            improved_conditions.append(condition_group)
        row_deltas.append(
            {
                "condition_group": condition_group,
                "true_dominant_state": true_state,
                "baseline_pred_state": baseline_pred_state,
                "current_pred_state": current_pred_state,
                "baseline_correct": int(baseline_correct),
                "current_correct": int(current_correct),
                "baseline_true_aggregation_flag": _int(baseline_row, "true_aggregation_flag"),
                "current_true_aggregation_flag": _int(current_row, "true_aggregation_flag"),
                "baseline_on_rg_mean": _float(baseline_row, "on_rg_mean"),
                "current_on_rg_mean": _float(current_row, "on_rg_mean"),
                "baseline_on_contact_persistence": _float(baseline_row, "on_contact_persistence"),
                "current_on_contact_persistence": _float(current_row, "on_contact_persistence"),
                "baseline_on_ensemble_diversity": _float(baseline_row, "on_ensemble_diversity"),
                "current_on_ensemble_diversity": _float(current_row, "on_ensemble_diversity"),
                "baseline_on_transient_helicity": _float(baseline_row, "on_transient_helicity"),
                "current_on_transient_helicity": _float(current_row, "on_transient_helicity"),
                "kf_shadow_enabled": int(_boolish(current_row.get("kf_shadow_enabled", False))),
                "would_have_changed_state": int(_boolish(current_row.get("would_have_changed_state", False))),
                "would_have_changed_gate": int(_boolish(current_row.get("would_have_changed_gate", False))),
            }
        )

    current_cls = dict(current_gate.get("classification_metrics", {}) or {})
    baseline_cls = dict(baseline_gate.get("classification_metrics", {}) or {})
    current_anchor = dict(current_gate.get("anchor_diagnostics", {}) or {})
    baseline_anchor = dict(baseline_gate.get("anchor_diagnostics", {}) or {})
    thresholds = dict((current_gate.get("gate_context", {}) or {}).get("effective_thresholds", {}) or {})
    dominant_threshold = float(thresholds.get("min_dominant_state_accuracy", 0.0) or 0.0)

    summary = {
        "current_pass": bool(current_gate.get("pass", False)),
        "baseline_pass": bool(baseline_gate.get("pass", False)),
        "current_utility_gate_pass": bool(current_gate.get("utility_gate_pass", False)),
        "baseline_utility_gate_pass": bool(baseline_gate.get("utility_gate_pass", False)),
        "current_physics_gate_pass": bool(current_gate.get("physics_gate_pass", False)),
        "baseline_physics_gate_pass": bool(baseline_gate.get("physics_gate_pass", False)),
        "current_dominant_state_accuracy": float(current_cls.get("dominant_state_accuracy", 0.0) or 0.0),
        "baseline_dominant_state_accuracy": float(baseline_cls.get("dominant_state_accuracy", 0.0) or 0.0),
        "dominant_state_threshold": float(dominant_threshold),
        "current_aggregation_flag_pr_auc": float(current_cls.get("aggregation_flag_pr_auc", 0.0) or 0.0),
        "baseline_aggregation_flag_pr_auc": float(baseline_cls.get("aggregation_flag_pr_auc", 0.0) or 0.0),
        "current_aggregation_relevant_pr_auc": float(current_cls.get("aggregation_relevant_pr_auc", 0.0) or 0.0),
        "baseline_aggregation_relevant_pr_auc": float(baseline_cls.get("aggregation_relevant_pr_auc", 0.0) or 0.0),
        "current_branch_state_consistency": float(current_cls.get("branch_state_consistency", 0.0) or 0.0),
        "baseline_branch_state_consistency": float(baseline_cls.get("branch_state_consistency", 0.0) or 0.0),
        "current_rg_anchor_error": float(((current_anchor.get("rg_mean", {}) or {}).get("median_normalized_error", 0.0)) or 0.0),
        "baseline_rg_anchor_error": float(((baseline_anchor.get("rg_mean", {}) or {}).get("median_normalized_error", 0.0)) or 0.0),
        "current_diversity_anchor_error": float(((current_anchor.get("ensemble_diversity", {}) or {}).get("median_normalized_error", 0.0)) or 0.0),
        "baseline_diversity_anchor_error": float(((baseline_anchor.get("ensemble_diversity", {}) or {}).get("median_normalized_error", 0.0)) or 0.0),
        "regressed_conditions": regressed_conditions,
        "improved_conditions": improved_conditions,
        "current_wrong_conditions": current_wrong,
        "baseline_wrong_conditions": baseline_wrong,
        "likely_failure_mechanism": (
            "Borderline page4 slice with chronically weak aggregation discrimination and bad rg_mean anchor fit crossed the "
            "dominant_state_accuracy gate after one additional state miss."
        ),
        "kalman_shadow_regression_signal": bool(
            any(bool(int(row.get("would_have_changed_state", 0) or 0)) or bool(int(row.get("would_have_changed_gate", 0) or 0)) for row in row_deltas)
        ),
    }
    return {"summary": summary, "row_deltas": row_deltas}


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# IDP Fold19 Page4 Failure Analysis",
        "",
        f"- current_pass: `{summary['current_pass']}`",
        f"- baseline_pass: `{summary['baseline_pass']}`",
        f"- current_utility_gate_pass: `{summary['current_utility_gate_pass']}`",
        f"- current_physics_gate_pass: `{summary['current_physics_gate_pass']}`",
        f"- dominant_state_threshold: `{summary['dominant_state_threshold']}`",
        f"- current_dominant_state_accuracy: `{summary['current_dominant_state_accuracy']}`",
        f"- baseline_dominant_state_accuracy: `{summary['baseline_dominant_state_accuracy']}`",
        f"- current_aggregation_flag_pr_auc: `{summary['current_aggregation_flag_pr_auc']}`",
        f"- baseline_aggregation_flag_pr_auc: `{summary['baseline_aggregation_flag_pr_auc']}`",
        f"- current_aggregation_relevant_pr_auc: `{summary['current_aggregation_relevant_pr_auc']}`",
        f"- baseline_aggregation_relevant_pr_auc: `{summary['baseline_aggregation_relevant_pr_auc']}`",
        f"- current_rg_anchor_error: `{summary['current_rg_anchor_error']}`",
        f"- baseline_rg_anchor_error: `{summary['baseline_rg_anchor_error']}`",
        f"- current_diversity_anchor_error: `{summary['current_diversity_anchor_error']}`",
        f"- baseline_diversity_anchor_error: `{summary['baseline_diversity_anchor_error']}`",
        f"- regressed_conditions: `{','.join(summary['regressed_conditions'])}`",
        f"- improved_conditions: `{','.join(summary['improved_conditions'])}`",
        f"- current_wrong_conditions: `{','.join(summary['current_wrong_conditions'])}`",
        f"- baseline_wrong_conditions: `{','.join(summary['baseline_wrong_conditions'])}`",
        f"- kalman_shadow_regression_signal: `{summary['kalman_shadow_regression_signal']}`",
        "",
        "## Interpretation",
        "",
        f"- {summary['likely_failure_mechanism']}",
        "",
        "## Row Deltas",
        "",
        "| condition | true_state | baseline_pred | current_pred | baseline_ok | current_ok | kf_state | kf_gate |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["row_deltas"]:
        lines.append(
            f"| {row['condition_group']} | {row['true_dominant_state']} | {row['baseline_pred_state']} | {row['current_pred_state']} | "
            f"{row['baseline_correct']} | {row['current_correct']} | {row['would_have_changed_state']} | {row['would_have_changed_gate']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a failure analysis artifact for IDP fold19/page4.")
    parser.add_argument("--current-gate-json", default=DEFAULT_CURRENT_GATE_JSON)
    parser.add_argument("--baseline-gate-json", default=DEFAULT_BASELINE_GATE_JSON)
    parser.add_argument("--current-targets-csv", default=DEFAULT_CURRENT_TARGETS_CSV)
    parser.add_argument("--baseline-targets-csv", default=DEFAULT_BASELINE_TARGETS_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        current_gate=_read_json(args.current_gate_json),
        baseline_gate=_read_json(args.baseline_gate_json),
        current_rows=_read_csv(args.current_targets_csv),
        baseline_rows=_read_csv(args.baseline_targets_csv),
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
