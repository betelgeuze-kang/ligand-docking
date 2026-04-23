import importlib.util
import json
import subprocess
import sys
from pathlib import Path
ROOT = Path('/home/betelgeuze/분자동역학')

def test_run_idp_tau_k18_stabilization_trial_argparse_help() -> None:
    proc = subprocess.run([sys.executable, str(ROOT / 'tools' / 'run_idp_tau_k18_stabilization_trial.py'), '--help'], cwd=str(ROOT), capture_output=True, text=True)
    assert proc.returncode == 0
    assert '--epochs' in proc.stdout
    assert '--patience' in proc.stdout


def test_run_idp_tau_k18_stabilization_trial_defaults_track_commercial_pretest_slice() -> None:
    spec = importlib.util.spec_from_file_location('run_idp_tau_k18_stabilization_trial', ROOT / 'tools' / 'run_idp_tau_k18_stabilization_trial.py')
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    args = module.build_parser().parse_args([])
    assert 'anchor_commercial_pretest_r1_fold6_tau_k18_train_branch_dataset.npz' in args.train_npz
    assert 'anchor_commercial_pretest_r1_fold_inputs/fold6_tau_k18_eval.json' in args.eval_config_json
    assert 'anchor_commercial_pretest_r1_fold6_tau_k18_gate_baseline_summary.json' in args.baseline_gate_json
    assert args.seed == 123
    assert args.lr == 7.5e-4
    assert args.kalman_shadow_feature_mask == 'rg_sasa_only'
    assert args.idp_r16_ml_patch == 0
