#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_TRAIN_NPZ = "runs/idp_3bead_holdout_v7_anchor_commercial_pretest_r1_fold6_tau_k18_train_branch_dataset.npz"
DEFAULT_EVAL_CONFIG_JSON = "runs/idp_3bead_holdout_v7_anchor_commercial_pretest_r1_fold_inputs/fold6_tau_k18_eval.json"
DEFAULT_BASELINE_GATE_JSON = "runs/idp_3bead_holdout_v7_anchor_commercial_pretest_r1_fold6_tau_k18_gate_baseline_summary.json"
DEFAULT_OUT_PREFIX = "runs/idp_tau_k18_stabilization_trial_commercial_pretest_current"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _run(cmd: list[str], *, extra_env: dict[str, str] | None = None) -> dict[str, Any]:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, env=env)
    return {
        "cmd": cmd,
        "rc": int(p.returncode),
        "stdout_tail": "\n".join((p.stdout or "").splitlines()[-20:]),
        "stderr_tail": "\n".join((p.stderr or "").splitlines()[-20:]),
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Run a small tau_k18 corrected-path stabilization trial on the current commercial-pretest fold6 slice."
    )
    p.add_argument("--train-npz", default=DEFAULT_TRAIN_NPZ)
    p.add_argument("--eval-config-json", default=DEFAULT_EVAL_CONFIG_JSON)
    p.add_argument("--baseline-gate-json", default=DEFAULT_BASELINE_GATE_JSON)
    p.add_argument("--out-prefix", default=DEFAULT_OUT_PREFIX)
    p.add_argument("--device", default="cuda")
    p.add_argument("--seed", type=int, default=123)
    p.add_argument("--epochs", type=int, default=120)
    p.add_argument("--patience", type=int, default=24)
    p.add_argument("--lr", type=float, default=7.5e-4)
    p.add_argument("--weight-decay", type=float, default=1e-5)
    p.add_argument("--kalman-shadow-enable", type=int, default=1)
    p.add_argument("--kalman-shadow-mode", default="feature_state_v1")
    p.add_argument("--kalman-shadow-family-token", default="idp")
    p.add_argument("--kalman-shadow-obs-noise-scale", type=float, default=0.15)
    p.add_argument("--kalman-shadow-process-noise-scale", type=float, default=0.03)
    p.add_argument("--kalman-shadow-delta-cap-frac", type=float, default=0.25)
    p.add_argument("--kalman-shadow-feature-mask", default="rg_sasa_only")
    p.add_argument("--frozen-labels-csv", default="")
    p.add_argument("--idp-r16-ml-patch", type=int, default=0)
    p.add_argument("--idp-r17-tau-ph-split-patch", type=int, default=0)
    p.add_argument("--idp-r18-tau-ph-helix-recovery-patch", type=int, default=0)
    return p


def main() -> int:
    args = build_parser().parse_args()
    out_prefix = str(_resolve(args.out_prefix))
    ckpt = f"{out_prefix}.pt"
    train_json = f"{out_prefix}_train_summary.json"
    train_md = f"{out_prefix}_train_summary.md"
    eval_prefix = f"{out_prefix}_eval_corrected"
    eval_json = f"{eval_prefix}_summary.json"
    gate_json = f"{out_prefix}_gate_corrected_summary.json"
    gate_md = f"{out_prefix}_gate_corrected_summary.md"
    summary_json = f"{out_prefix}_summary.json"
    summary_md = f"{out_prefix}_summary.md"

    train_cmd = [
        sys.executable, str(ROOT / 'tools' / 'train_idp_branch_model.py'),
        '--input-npz', str(_resolve(args.train_npz)),
        '--device', str(args.device),
        '--seed', str(args.seed),
        '--epochs', str(args.epochs),
        '--patience', str(args.patience),
        '--lr', str(args.lr),
        '--weight-decay', str(args.weight_decay),
        '--out-checkpoint', ckpt,
        '--out-json', train_json,
        '--out-md', train_md,
    ]
    train_status = _run(train_cmd)
    if train_status['rc'] != 0:
        Path(summary_json).write_text(json.dumps({'pass': False, 'stage': 'train', 'status': train_status}, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        return train_status['rc']

    eval_cmd = [
        sys.executable, str(ROOT / 'tools' / 'run_idp_3bead_evaluator.py'),
        '--config-json', str(_resolve(args.eval_config_json)),
        '--device', str(args.device),
        '--residual-checkpoint', ckpt,
        '--residual-device', str(args.device),
        '--date-tag', 'tau-k18-stabilization-trial',
        '--out-prefix', eval_prefix,
        '--kalman-shadow-enable', str(args.kalman_shadow_enable),
        '--kalman-shadow-mode', str(args.kalman_shadow_mode),
        '--kalman-shadow-family-token', str(args.kalman_shadow_family_token),
        '--kalman-shadow-obs-noise-scale', str(args.kalman_shadow_obs_noise_scale),
        '--kalman-shadow-process-noise-scale', str(args.kalman_shadow_process_noise_scale),
        '--kalman-shadow-delta-cap-frac', str(args.kalman_shadow_delta_cap_frac),
        '--kalman-shadow-feature-mask', str(args.kalman_shadow_feature_mask),
    ]
    if str(args.frozen_labels_csv).strip():
        eval_cmd.extend(['--frozen-labels-csv', str(_resolve(args.frozen_labels_csv))])
    extra_env: dict[str, str] = {}
    if int(args.idp_r16_ml_patch or 0) == 1:
        extra_env["IDP_R16_ML_PATCH"] = "1"
    if int(args.idp_r17_tau_ph_split_patch or 0) == 1:
        extra_env["IDP_R17_TAU_PH_SPLIT_PATCH"] = "1"
    if int(args.idp_r18_tau_ph_helix_recovery_patch or 0) == 1:
        extra_env["IDP_R18_TAU_PH_HELIX_RECOVERY_PATCH"] = "1"
    eval_status = _run(
        eval_cmd,
        extra_env=extra_env or None,
    )
    if eval_status['rc'] != 0:
        Path(summary_json).write_text(json.dumps({'pass': False, 'stage': 'eval', 'train_status': train_status, 'status': eval_status}, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        return eval_status['rc']

    gate_cmd = [
        sys.executable, str(ROOT / 'tools' / 'run_idp_3bead_benchmark_gate.py'),
        '--config-json', str(_resolve(args.eval_config_json)),
        '--eval-json', eval_json,
        '--out-json', gate_json,
        '--out-md', gate_md,
    ]
    gate_status = _run(gate_cmd)

    baseline_gate = _read_json(_resolve(args.baseline_gate_json))
    corrected_gate = _read_json(Path(gate_json))
    train_payload = _read_json(Path(train_json))
    eval_payload = _read_json(Path(eval_json))

    summary = {
        'pass': bool(corrected_gate.get('pass', False)),
        'seed': int(args.seed),
        'epochs': int(args.epochs),
        'patience': int(args.patience),
        'lr': float(args.lr),
        'weight_decay': float(args.weight_decay),
        'train_status': train_status,
        'eval_status': eval_status,
        'gate_status': gate_status,
        'train_best': train_payload.get('best', {}),
        'baseline_gate_pass': baseline_gate.get('pass'),
        'corrected_gate_pass': corrected_gate.get('pass'),
        'baseline_dominant_state_accuracy': (baseline_gate.get('classification_metrics', {}) or {}).get('dominant_state_accuracy'),
        'corrected_dominant_state_accuracy': (corrected_gate.get('classification_metrics', {}) or {}).get('dominant_state_accuracy'),
        'kalman_shadow': eval_payload.get('kalman_shadow', {}),
        'kalman_shadow_feature_mask': str(args.kalman_shadow_feature_mask),
        'frozen_labels_csv': str(_resolve(args.frozen_labels_csv)) if str(args.frozen_labels_csv).strip() else "",
        'idp_r16_ml_patch': int(args.idp_r16_ml_patch),
        'idp_r17_tau_ph_split_patch': int(args.idp_r17_tau_ph_split_patch),
        'idp_r18_tau_ph_helix_recovery_patch': int(args.idp_r18_tau_ph_helix_recovery_patch),
        'checkpoint': ckpt,
        'eval_json': eval_json,
        'gate_json': gate_json,
    }
    Path(summary_json).write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    Path(summary_md).write_text(
        '\n'.join([
            '# Tau K18 Stabilization Trial',
            '',
            f"- pass: `{summary['pass']}`",
            f"- seed: `{summary['seed']}`",
            f"- epochs: `{summary['epochs']}`",
            f"- patience: `{summary['patience']}`",
            f"- kalman_shadow_feature_mask: `{summary['kalman_shadow_feature_mask']}`",
            f"- frozen_labels_csv: `{summary['frozen_labels_csv']}`",
            f"- idp_r16_ml_patch: `{summary['idp_r16_ml_patch']}`",
            f"- idp_r17_tau_ph_split_patch: `{summary['idp_r17_tau_ph_split_patch']}`",
            f"- idp_r18_tau_ph_helix_recovery_patch: `{summary['idp_r18_tau_ph_helix_recovery_patch']}`",
            f"- baseline_gate_pass: `{summary['baseline_gate_pass']}`",
            f"- corrected_gate_pass: `{summary['corrected_gate_pass']}`",
            f"- baseline_dominant_state_accuracy: `{summary['baseline_dominant_state_accuracy']}`",
            f"- corrected_dominant_state_accuracy: `{summary['corrected_dominant_state_accuracy']}`",
            f"- checkpoint: `{summary['checkpoint']}`",
            f"- gate_json: `{summary['gate_json']}`",
        ]) + '\n', encoding='utf-8'
    )
    return int(gate_status['rc'])


if __name__ == '__main__':
    raise SystemExit(main())
