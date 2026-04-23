import json
import subprocess
import sys
from pathlib import Path

ROOT = Path('/home/betelgeuze/분자동역학')


def test_build_idp_branch_dataset(tmp_path):
    eval_json = tmp_path / 'eval.json'
    eval_json.write_text(json.dumps({
        'targets': [
            {
                'target': 'alpha_synuclein_full', 'split_group': 'alpha_synuclein_full', 'condition_group': 'base',
                'frac_aromatic': 0.10, 'net_charge_proxy': 0.0,
                'on_rg_mean': 30.0, 'on_sasa_proxy_mean': 1200.0, 'on_contact_persistence': 0.15,
                'on_transient_helicity': 0.05, 'on_ensemble_diversity': 12.0,
            },
            {
                'target': 'alpha_synuclein_full', 'split_group': 'alpha_synuclein_full', 'condition_group': 'salt',
                'frac_aromatic': 0.10, 'net_charge_proxy': 0.0,
                'on_rg_mean': 24.0, 'on_sasa_proxy_mean': 900.0, 'on_contact_persistence': 0.22,
                'on_transient_helicity': 0.06, 'on_ensemble_diversity': 7.0,
            }
        ]
    }, ensure_ascii=False), encoding='utf-8')
    out_prefix = tmp_path / 'branch_ds'
    proc = subprocess.run([
        sys.executable, str(ROOT / 'tools' / 'build_idp_branch_dataset.py'),
        '--eval-json', str(eval_json),
        '--out-prefix', str(out_prefix),
    ], cwd=str(ROOT), capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    summary = json.loads((tmp_path / 'branch_ds_summary.json').read_text(encoding='utf-8'))
    assert summary['rows_total'] == 2
    assert summary['pair_count'] >= 2
