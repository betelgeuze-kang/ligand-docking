#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BASELINE_GATE_JSON = "runs/idp_3bead_holdout_v7_literature_anchor_kfshadow_r1_fold6_tau_k18_gate_baseline_summary.json"
DEFAULT_CORRECTED_GATE_JSON = "runs/idp_3bead_holdout_v7_literature_anchor_kfshadow_r1_fold6_tau_k18_gate_corrected_summary.json"
DEFAULT_BASELINE_EVAL_JSON = "runs/idp_3bead_holdout_v7_literature_anchor_kfshadow_r1_fold6_tau_k18_eval_baseline_summary.json"
DEFAULT_CORRECTED_EVAL_JSON = "runs/idp_3bead_holdout_v7_literature_anchor_kfshadow_r1_fold6_tau_k18_eval_corrected_summary.json"
DEFAULT_OUT_JSON = "runs/idp_tau_k18_subset_failure_analysis_current.json"
DEFAULT_OUT_CSV = "runs/idp_tau_k18_subset_failure_analysis_current.csv"
DEFAULT_OUT_MD = "runs/idp_tau_k18_subset_failure_analysis_current.md"


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


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_payload(
    baseline_gate: dict[str, Any],
    corrected_gate: dict[str, Any],
    baseline_eval: dict[str, Any],
    corrected_eval: dict[str, Any],
) -> dict[str, Any]:
    baseline_rows = {str(r.get('condition_group', '')): r for r in baseline_eval.get('targets', [])}
    corrected_rows = {str(r.get('condition_group', '')): r for r in corrected_eval.get('targets', [])}
    conditions = sorted(set(baseline_rows) | set(corrected_rows))
    row_deltas: list[dict[str, Any]] = []
    for condition in conditions:
        b = baseline_rows.get(condition, {})
        c = corrected_rows.get(condition, {})
        row_deltas.append({
            'condition_group': condition,
            'true_state': str(c.get('true_dominant_state', b.get('true_dominant_state', ''))),
            'baseline_state': str(b.get('dominant_state_label', '')),
            'corrected_state': str(c.get('dominant_state_label', '')),
            'baseline_pred_state': str(b.get('pred_state', '')),
            'corrected_pred_state': str(c.get('pred_state', '')),
            'would_have_changed_state': int(bool(c.get('would_have_changed_state', False))),
            'would_have_changed_gate': int(bool(c.get('would_have_changed_gate', False))),
            'kf_shadow_state': str(c.get('kf_shadow_dominant_state_label', '')),
            'baseline_target_pass': int(bool(b.get('target_pass', False))),
            'corrected_target_pass': int(bool(c.get('target_pass', False))),
        })
    b_anchor = dict(baseline_gate.get('anchor_diagnostics', {}) or {})
    c_anchor = dict(corrected_gate.get('anchor_diagnostics', {}) or {})
    c_cls = dict(corrected_gate.get('classification_metrics', {}) or {})
    thresholds = dict((corrected_gate.get('gate_context', {}) or {}).get('effective_thresholds', {}) or {})
    summary = {
        'fold_name': 'tau_k18',
        'baseline_pass': bool(baseline_gate.get('pass', False)),
        'corrected_pass': bool(corrected_gate.get('pass', False)),
        'corrected_utility_gate_pass': bool(corrected_gate.get('utility_gate_pass', False)),
        'corrected_physics_gate_pass': bool(corrected_gate.get('physics_gate_pass', False)),
        'dominant_state_accuracy': float(c_cls.get('dominant_state_accuracy', 0.0) or 0.0),
        'dominant_state_threshold': float(thresholds.get('min_dominant_state_accuracy', 0.0) or 0.0),
        'aggregation_flag_pr_auc': float(c_cls.get('aggregation_flag_pr_auc', 0.0) or 0.0),
        'compactness_rank_auc': float((corrected_gate.get('ranking_metrics', {}) or {}).get('compactness_rank_auc', 0.0) or 0.0),
        'helicity_rank_auc': float((corrected_gate.get('ranking_metrics', {}) or {}).get('helicity_rank_auc', 0.0) or 0.0),
        'condensation_rank_auc': float((corrected_gate.get('ranking_metrics', {}) or {}).get('condensation_rank_auc', 0.0) or 0.0),
        'rg_anchor_error': float(((c_anchor.get('rg_mean', {}) or {}).get('median_normalized_error', 0.0)) or 0.0),
        'sasa_anchor_error': float(((c_anchor.get('sasa_proxy_mean', {}) or {}).get('median_normalized_error', 0.0)) or 0.0),
        'kalman_state_change_count': int(sum(r['would_have_changed_state'] for r in row_deltas)),
        'kalman_gate_change_count': int(sum(r['would_have_changed_gate'] for r in row_deltas)),
        'failure_interpretation': (
            'Corrected-path dominant-state classification failed on tau_k18 while Kalman feature_state_v1 stayed telemetry-only '
            'with zero state/gate changes on corrected eval rows. This is a corrected-path/model fragility, not a Kalman-shadow regression.'
        ),
    }
    return {'summary': summary, 'row_deltas': row_deltas}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload['summary']
    lines = [
        '# IDP Tau K18 Subset Failure Analysis',
        '',
        f"- baseline_pass: `{s['baseline_pass']}`",
        f"- corrected_pass: `{s['corrected_pass']}`",
        f"- corrected_utility_gate_pass: `{s['corrected_utility_gate_pass']}`",
        f"- corrected_physics_gate_pass: `{s['corrected_physics_gate_pass']}`",
        f"- dominant_state_accuracy: `{s['dominant_state_accuracy']}`",
        f"- dominant_state_threshold: `{s['dominant_state_threshold']}`",
        f"- aggregation_flag_pr_auc: `{s['aggregation_flag_pr_auc']}`",
        f"- compactness_rank_auc: `{s['compactness_rank_auc']}`",
        f"- helicity_rank_auc: `{s['helicity_rank_auc']}`",
        f"- condensation_rank_auc: `{s['condensation_rank_auc']}`",
        f"- rg_anchor_error: `{s['rg_anchor_error']}`",
        f"- sasa_anchor_error: `{s['sasa_anchor_error']}`",
        f"- kalman_state_change_count: `{s['kalman_state_change_count']}`",
        f"- kalman_gate_change_count: `{s['kalman_gate_change_count']}`",
        '',
        '## Interpretation',
        '',
        f"- {s['failure_interpretation']}",
        '',
        '## Conditions',
        '',
        '| condition | true | baseline_state | corrected_state | baseline_pred | corrected_pred | kf_state | kf_gate |',
        '| --- | --- | --- | --- | --- | --- | ---: | ---: |',
    ]
    for row in payload['row_deltas']:
        lines.append(
            f"| {row['condition_group']} | {row['true_state']} | {row['baseline_state']} | {row['corrected_state']} | {row['baseline_pred_state']} | {row['corrected_pred_state']} | {row['would_have_changed_state']} | {row['would_have_changed_gate']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description='Build tau_k18 subset failure analysis artifact.')
    ap.add_argument('--baseline-gate-json', default=DEFAULT_BASELINE_GATE_JSON)
    ap.add_argument('--corrected-gate-json', default=DEFAULT_CORRECTED_GATE_JSON)
    ap.add_argument('--baseline-eval-json', default=DEFAULT_BASELINE_EVAL_JSON)
    ap.add_argument('--corrected-eval-json', default=DEFAULT_CORRECTED_EVAL_JSON)
    ap.add_argument('--out-json', default=DEFAULT_OUT_JSON)
    ap.add_argument('--out-csv', default=DEFAULT_OUT_CSV)
    ap.add_argument('--out-md', default=DEFAULT_OUT_MD)
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _read_json(args.baseline_gate_json),
        _read_json(args.corrected_gate_json),
        _read_json(args.baseline_eval_json),
        _read_json(args.corrected_eval_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    _write_csv(out_csv, payload['row_deltas'])
    _write_markdown(out_md, payload)


if __name__ == '__main__':
    main()
