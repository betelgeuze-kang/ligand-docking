import json
import subprocess
import sys
from pathlib import Path
ROOT = Path('/home/betelgeuze/분자동역학')

def test_build_tau_k18_stabilization_plan(tmp_path: Path) -> None:
    out_json = tmp_path / 'plan.json'
    out_md = tmp_path / 'plan.md'
    proc = subprocess.run([sys.executable, str(ROOT / 'tools' / 'build_tau_k18_stabilization_plan.py'), '--out-json', str(out_json), '--out-md', str(out_md)], cwd=str(ROOT), capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out_json.read_text(encoding='utf-8'))
    assert payload['summary']['status'] == 'next_runnable_stabilization_slice_ready'
    assert payload['summary']['completed_reference_trial']['seed'] == 77
    assert payload['summary']['next_trial']['seed'] == 123
    assert 'anchor_commercial_pretest_r1_fold6_tau_k18_train_branch_dataset.npz' in payload['summary']['next_trial']['train_npz']
    assert 'run_idp_tau_k18_stabilization_trial.py' in payload['summary']['next_trial']['exact_command']
    assert '--kalman-shadow-feature-mask rg_sasa_only' in payload['summary']['next_trial']['exact_command']
