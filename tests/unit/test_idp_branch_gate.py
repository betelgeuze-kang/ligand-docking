import json
import subprocess
import sys
from pathlib import Path

ROOT = Path('/home/betelgeuze/분자동역학')


def test_branch_gate_ignores_anchor_as_hard_fail(tmp_path):
    cfg = tmp_path / 'cfg.json'
    cfg.write_text(json.dumps({'gate': {'min_branch_macro_f1': 0.5, 'min_dominant_state_accuracy': 0.5, 'min_llps_flag_pr_auc': 0.5, 'min_aggregation_flag_pr_auc': 0.5, 'min_compactness_rank_auc': 0.5, 'min_helicity_rank_auc': 0.5, 'min_condensation_rank_auc': 0.5, 'max_failed_targets': 10, 'min_virtual_hbond_contacts_mean': 0.0, 'min_anti_collapse_force_mean': 0.0, 'max_overcollapse_rate': 1.0}}, ensure_ascii=False), encoding='utf-8')
    eval_json = tmp_path / 'eval.json'
    rows = []
    for idx in range(4):
        rows.append({
            'target': f't{idx}',
            'split_group': 'g1' if idx < 2 else 'g2',
            'branch_label': 'llps_lcd' if idx < 2 else 'aggregation_prone',
            'true_dominant_state': 'sticky_condensed' if idx < 2 else 'compact_disordered',
            'true_llps_flag': 1 if idx < 2 else 0,
            'true_aggregation_flag': 0 if idx < 2 else 1,
            'branch_weight_llps_lcd': 0.9 if idx < 2 else 0.1,
            'branch_weight_aggregation_prone': 0.05 if idx < 2 else 0.85,
            'branch_weight_helix_tad': 0.05,
            'pred_state': 'sticky_condensed' if idx < 2 else 'compact_disordered',
            'pred_llps_prob': 0.9 if idx < 2 else 0.1,
            'pred_aggregation_prob': 0.1 if idx < 2 else 0.9,
            'compactness_score': float(idx),
            'helicity_score': float(idx),
            'condensation_score': float(idx),
            'pred_rank_compactness': float(idx),
            'pred_rank_helicity': float(idx),
            'pred_rank_condensation': float(idx),
            'on_virtual_hbond_contacts_mean': 0.2,
            'on_anti_collapse_force_mean': 0.2,
            'on_overcollapse_rate': 0.0,
            'baseline_anchor_rg_mean_lo': 1.0,
            'baseline_anchor_rg_mean_hi': 2.0,
            'baseline_anchor_rg_mean_error': 999.0,
        })
    eval_json.write_text(json.dumps({'targets': rows}, ensure_ascii=False), encoding='utf-8')
    out_json = tmp_path / 'gate.json'
    proc = subprocess.run([
        sys.executable, str(ROOT / 'tools' / 'run_idp_3bead_benchmark_gate.py'),
        '--config-json', str(cfg),
        '--eval-json', str(eval_json),
        '--out-json', str(out_json),
        '--out-md', str(tmp_path / 'gate.md'),
    ], cwd=str(ROOT), capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out_json.read_text(encoding='utf-8'))
    assert payload['mode'] == 'branch_moe_v1'
    assert payload['pass'] is True
    assert 'anchor_diagnostics' in payload


def test_branch_gate_uses_branch_conditioned_combined_metrics(tmp_path):
    cfg = tmp_path / 'cfg.json'
    cfg.write_text(
        json.dumps(
            {
                'gate': {
                    'min_branch_macro_f1': 0.5,
                    'min_dominant_state_accuracy': 0.5,
                    'min_llps_flag_pr_auc': 0.75,
                    'min_aggregation_flag_pr_auc': 0.75,
                    'min_compactness_rank_auc': 0.5,
                    'min_helicity_rank_auc': 0.5,
                    'min_condensation_rank_auc': 0.5,
                    'max_failed_targets': 10,
                    'min_virtual_hbond_contacts_mean': 0.0,
                    'min_anti_collapse_force_mean': 0.0,
                    'max_overcollapse_rate': 1.0,
                    'use_branch_conditioned_combined_metrics': True,
                }
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )
    eval_json = tmp_path / 'eval.json'
    rows = []
    for idx in range(4):
        rows.append(
            {
                'target': f'llps_{idx}',
                'split_group': 'llps',
                'branch_label': 'llps_lcd',
                'true_dominant_state': 'sticky_condensed',
                'true_llps_flag': 1,
                'true_aggregation_flag': 1 if idx < 2 else 0,
                'branch_weight_llps_lcd': 0.95,
                'branch_weight_aggregation_prone': 0.03,
                'branch_weight_helix_tad': 0.02,
                'pred_state': 'sticky_condensed',
                'pred_llps_prob': 0.98,
                # Deliberately poor on LLPS rows to keep global aggregation AP low.
                'pred_aggregation_prob': 0.02 if idx < 2 else 0.03,
                'compactness_score': float(idx),
                'helicity_score': float(idx),
                'condensation_score': float(idx),
                'pred_rank_compactness': float(idx),
                'pred_rank_helicity': float(idx),
                'pred_rank_condensation': float(idx),
                'on_virtual_hbond_contacts_mean': 0.2,
                'on_anti_collapse_force_mean': 0.2,
                'on_overcollapse_rate': 0.0,
            }
        )
    for idx in range(4):
        rows.append(
            {
                'target': f'agg_{idx}',
                'split_group': 'agg',
                'branch_label': 'aggregation_prone',
                'true_dominant_state': 'compact_disordered',
                'true_llps_flag': 0,
                'true_aggregation_flag': 1 if idx < 2 else 0,
                'branch_weight_llps_lcd': 0.02,
                'branch_weight_aggregation_prone': 0.95,
                'branch_weight_helix_tad': 0.03,
                'pred_state': 'compact_disordered',
                'pred_llps_prob': 0.02,
                'pred_aggregation_prob': 0.95 if idx < 2 else 0.05,
                'compactness_score': float(idx),
                'helicity_score': float(idx),
                'condensation_score': float(idx),
                'pred_rank_compactness': float(idx),
                'pred_rank_helicity': float(idx),
                'pred_rank_condensation': float(idx),
                'on_virtual_hbond_contacts_mean': 0.2,
                'on_anti_collapse_force_mean': 0.2,
                'on_overcollapse_rate': 0.0,
            }
        )
    eval_json.write_text(json.dumps({'targets': rows}, ensure_ascii=False), encoding='utf-8')
    out_json = tmp_path / 'gate.json'
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / 'tools' / 'run_idp_3bead_benchmark_gate.py'),
            '--config-json',
            str(cfg),
            '--eval-json',
            str(eval_json),
            '--out-json',
            str(out_json),
            '--out-md',
            str(tmp_path / 'gate.md'),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out_json.read_text(encoding='utf-8'))
    assert payload['pass'] is True
    cm = payload['classification_metrics']
    assert cm['aggregation_flag_pr_auc'] < 0.75
    assert cm['aggregation_relevant_pr_auc'] >= 0.75
    assert payload['gate_context']['effective_thresholds']['aggregation_metric'] == 'aggregation_relevant_pr_auc'
