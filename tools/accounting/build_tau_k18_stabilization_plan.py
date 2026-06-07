#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = 'runs/tau_k18_stabilization_plan_current.json'
DEFAULT_OUT_MD = 'runs/tau_k18_stabilization_plan_current.md'
DEFAULT_FAILURE_PACKET_MD = 'runs/idp_tau_k18_corrected_path_failure_packet_current.md'
DEFAULT_DECISION_MD = 'runs/idp_commercial_pretest_decision_current.md'
DEFAULT_REFERENCE_SUMMARY_JSON = 'runs/idp_tau_k18_stabilization_trial_seed77_r1_summary.json'
DEFAULT_TRAIN_NPZ = 'runs/idp_3bead_holdout_v7_anchor_commercial_pretest_r1_fold6_tau_k18_train_branch_dataset.npz'
DEFAULT_EVAL_CONFIG_JSON = 'runs/idp_3bead_holdout_v7_anchor_commercial_pretest_r1_fold_inputs/fold6_tau_k18_eval.json'
DEFAULT_BASELINE_GATE_JSON = 'runs/idp_3bead_holdout_v7_anchor_commercial_pretest_r1_fold6_tau_k18_gate_baseline_summary.json'
DEFAULT_OUT_PREFIX = 'runs/idp_tau_k18_stabilization_trial_commercial_pretest_seed123_r1'


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _command(next_trial: dict[str, Any]) -> str:
    return shlex.join([
        'python3',
        'tools/run_idp_tau_k18_stabilization_trial.py',
        '--train-npz', next_trial['train_npz'],
        '--eval-config-json', next_trial['eval_config_json'],
        '--baseline-gate-json', next_trial['baseline_gate_json'],
        '--out-prefix', next_trial['out_prefix'],
        '--seed', str(next_trial['seed']),
        '--epochs', str(next_trial['epochs']),
        '--patience', str(next_trial['patience']),
        '--lr', str(next_trial['lr']),
        '--weight-decay', str(next_trial['weight_decay']),
        '--kalman-shadow-enable', '1',
        '--kalman-shadow-mode', 'feature_state_v1',
        '--kalman-shadow-family-token', 'idp',
        '--kalman-shadow-obs-noise-scale', '0.15',
        '--kalman-shadow-process-noise-scale', '0.03',
        '--kalman-shadow-delta-cap-frac', '0.25',
        '--kalman-shadow-feature-mask', 'rg_sasa_only',
    ])


def build_payload() -> dict[str, Any]:
    completed_reference_trial = {
        'label': 'seed77_reference_fail',
        'source_summary_json': DEFAULT_REFERENCE_SUMMARY_JSON,
        'seed': 77,
        'epochs': 120,
        'patience': 24,
        'lr': 1e-3,
        'weight_decay': 1e-5,
        'known_result': 'corrected_gate_fail',
    }
    next_trial = {
        'label': 'commercial_pretest_fold6_seed123_fallback',
        'seed': 123,
        'epochs': 120,
        'patience': 24,
        'lr': 7.5e-4,
        'weight_decay': 1e-5,
        'train_npz': DEFAULT_TRAIN_NPZ,
        'eval_config_json': DEFAULT_EVAL_CONFIG_JSON,
        'baseline_gate_json': DEFAULT_BASELINE_GATE_JSON,
        'out_prefix': DEFAULT_OUT_PREFIX,
        'fixed_kalman_mode': 'feature_state_v1',
        'fixed_feature_mask': 'rg_sasa_only',
        'fixed_obs_noise_scale': 0.15,
        'fixed_process_noise_scale': 0.03,
        'fixed_delta_cap_frac': 0.25,
    }
    next_trial['exact_command'] = _command(next_trial)
    return {
        'summary': {
            'status': 'next_runnable_stabilization_slice_ready',
            'target': 'tau_k18',
            'goal': 'stabilize corrected-path dominant_state_accuracy without conflating Kalman shadow effects',
            'slice_basis': 'anchor_commercial_pretest_fold6_tau_k18_corrected_gate_failure',
            'failure_packet_md': DEFAULT_FAILURE_PACKET_MD,
            'decision_md': DEFAULT_DECISION_MD,
            'completed_reference_trial': completed_reference_trial,
            'next_trial': next_trial,
            'why_this_is_smallest_slice': (
                'This isolates only fold6 tau_k18 on the current commercial-pretest inputs, keeps the model architecture '
                'and Kalman settings fixed, and perturbs only branch-trainer optimization stability.'
            ),
            'success_criterion': (
                'tau_k18 corrected gate passes on the commercial-pretest fold6 slice while Kalman state/gate change counts stay zero.'
            ),
            'failure_gate': (
                'If corrected gate still fails with zero Kalman state/gate changes, treat that as persistent corrected-path fragility '
                'and do not widen IDP commercialization scope.'
            ),
        }
    }


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    s = payload['summary']
    r = s['completed_reference_trial']
    n = s['next_trial']
    lines = [
        '# Tau K18 Stabilization Plan',
        '',
        f"- status: `{s['status']}`",
        f"- target: `{s['target']}`",
        f"- goal: {s['goal']}",
        f"- slice_basis: `{s['slice_basis']}`",
        f"- failure_packet_md: `{s['failure_packet_md']}`",
        f"- decision_md: `{s['decision_md']}`",
        f"- why_this_is_smallest_slice: {s['why_this_is_smallest_slice']}",
        f"- success_criterion: {s['success_criterion']}",
        f"- failure_gate: {s['failure_gate']}",
        '',
        '## Completed Reference Trial',
        '',
        f"- label: `{r['label']}`",
        f"- seed: `{r['seed']}`",
        f"- epochs: `{r['epochs']}`",
        f"- patience: `{r['patience']}`",
        f"- lr: `{r['lr']}`",
        f"- weight_decay: `{r['weight_decay']}`",
        f"- known_result: `{r['known_result']}`",
        f"- source_summary_json: `{r['source_summary_json']}`",
        '',
        '## Next Runnable Slice',
        '',
        f"- label: `{n['label']}`",
        f"- seed: `{n['seed']}`",
        f"- epochs: `{n['epochs']}`",
        f"- patience: `{n['patience']}`",
        f"- lr: `{n['lr']}`",
        f"- weight_decay: `{n['weight_decay']}`",
        f"- train_npz: `{n['train_npz']}`",
        f"- eval_config_json: `{n['eval_config_json']}`",
        f"- baseline_gate_json: `{n['baseline_gate_json']}`",
        f"- out_prefix: `{n['out_prefix']}`",
        f"- fixed_kalman_mode: `{n['fixed_kalman_mode']}`",
        f"- fixed_feature_mask: `{n['fixed_feature_mask']}`",
        f"- fixed_obs_noise_scale: `{n['fixed_obs_noise_scale']}`",
        f"- fixed_process_noise_scale: `{n['fixed_process_noise_scale']}`",
        f"- fixed_delta_cap_frac: `{n['fixed_delta_cap_frac']}`",
        '',
        '## Exact Next Command',
        '',
        '```bash',
        n['exact_command'],
        '```',
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main() -> None:
    ap = argparse.ArgumentParser(description='Build tau_k18 stabilization plan artifact.')
    ap.add_argument('--out-json', default=DEFAULT_OUT_JSON)
    ap.add_argument('--out-md', default=DEFAULT_OUT_MD)
    args = ap.parse_args()
    payload = build_payload()
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    _write_md(out_md, payload)


if __name__ == '__main__':
    main()
