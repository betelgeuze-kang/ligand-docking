import json
import subprocess
import sys
import csv
from pathlib import Path

ROOT = Path('/home/betelgeuze/분자동역학')


def test_idp_3bead_holdout_pipeline(tmp_path):
    config_path = tmp_path / 'idp_holdout_cfg.json'
    anchor = {
        'source': 'test_anchor',
        'rg_mean_range': [10.0, 200.0],
        'sasa_proxy_mean_range': [0.0, 5000.0],
        'contact_persistence_range': [0.0, 1.0],
        'transient_helicity_range': [0.0, 1.0],
        'ensemble_diversity_range': [0.0, 50.0],
    }
    config_path.write_text(
        json.dumps(
            {
                'runtime': {
                    'device': 'cpu',
                    'rollout_steps': 12,
                    'sample_stride': 3,
                    'dt': 0.02,
                    'thermal_noise': 0.005,
                    'knn_k': 6,
                },
                'gate': {
                    'min_target_pass_fraction': 0.0,
                    'max_failed_targets': 10,
                    'min_mean_force': 0.0,
                    'max_virtual_hbond_mean_distance_A': 10.0,
                    'min_virtual_hbond_contacts_mean': 0.0,
                    'min_anti_collapse_force_mean': 0.0,
                    'max_overcollapse_rate': 1.0,
                    'min_abs_delta_contact_persistence': 0.0,
                    'min_abs_delta_transient_helicity': 0.0,
                    'min_abs_delta_ensemble_diversity': 0.0,
                    'max_anchor_rg_mean_error': 1000.0,
                    'max_anchor_sasa_proxy_mean_error': 1000.0,
                    'max_anchor_contact_persistence_error': 10.0,
                    'max_anchor_transient_helicity_error': 10.0,
                    'max_anchor_ensemble_diversity_error': 10.0,
                },
                'targets': [
                    {'name': 'g1_a', 'split_group': 'g1', 'condition_group': 'base', 'source': 'synthetic', 'n_res': 20, 'seed': 7, 'observable_anchor': anchor},
                    {'name': 'g1_b', 'split_group': 'g1', 'condition_group': 'salt', 'source': 'synthetic', 'n_res': 22, 'seed': 8, 'observable_anchor': anchor},
                    {'name': 'g2_a', 'split_group': 'g2', 'condition_group': 'base', 'source': 'synthetic', 'n_res': 24, 'seed': 9, 'observable_anchor': anchor},
                    {'name': 'g2_b', 'split_group': 'g2', 'condition_group': 'salt', 'source': 'synthetic', 'n_res': 26, 'seed': 10, 'observable_anchor': anchor},
                ],
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )
    prefix = tmp_path / 'holdout'
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / 'tools' / 'run_idp_3bead_holdout_pipeline.py'),
            '--config-json',
            str(config_path),
            '--device',
            'cpu',
            '--out-prefix',
            str(prefix),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode in (0, 2), proc.stderr
    summary = json.loads((tmp_path / 'holdout_summary.json').read_text(encoding='utf-8'))
    assert summary['fold_count'] == 2
    assert 'combined_gate' in summary
    assert 'branch_summary' in summary
    assert 'all_fold_pass' in summary
    assert 'combined_gate_pass' in summary
    assert summary['pass'] == summary['all_fold_pass']
    assert 'release_post' in summary
    assert 'manifest' in summary['release_post']
    assert 'manifest_json' in summary['release_post']


def test_append_kalman_shadow_args_includes_mode_and_delta_cap():
    from argparse import Namespace

    from tools.run_idp_3bead_holdout_pipeline import _append_kalman_shadow_args

    cmd = ["python3", "tools/run_idp_3bead_evaluator.py"]
    args = Namespace(
        kalman_shadow_enable=1,
        kalman_shadow_mode="feature_state_v1",
        kalman_shadow_family_token="idp",
        kalman_shadow_obs_noise_scale=0.15,
        kalman_shadow_process_noise_scale=0.03,
        kalman_shadow_delta_cap_frac=0.25,
    )
    out = _append_kalman_shadow_args(list(cmd), args)
    joined = " ".join(out)
    assert "--kalman-shadow-mode feature_state_v1" in joined
    assert "--kalman-shadow-delta-cap-frac 0.25" in joined


def test_build_idp_release_manifest(tmp_path):
    summary_path = tmp_path / 'release_summary.json'
    summary_path.write_text(
        json.dumps(
            {
                'pass': True,
                'all_fold_pass': True,
                'combined_gate_pass': False,
                'baseline_pass_folds': 2,
                'corrected_pass_folds': 2,
                'fold_count': 2,
                'config_json': 'config/idp_3bead_benchmark_v7.json',
                'device': 'cuda',
                'holdout_key': 'split_group',
                'folds': [
                    {'holdout': 'g1', 'pass': True, 'baseline_gate': {'pass': True}, 'corrected_gate': {'pass': True}},
                    {'holdout': 'g2', 'pass': True, 'baseline_gate': {'pass': True}, 'corrected_gate': {'pass': True}},
                ],
                'combined_gate': {
                    'payload': {
                        'classification_metrics': {
                            'branch_macro_f1': 1.0,
                            'dominant_state_accuracy': 0.9,
                            'llps_flag_pr_auc': 0.8,
                            'aggregation_flag_pr_auc': 0.7,
                        },
                        'ranking_metrics': {
                            'compactness_rank_auc': 0.9,
                            'helicity_rank_auc': 0.85,
                            'condensation_rank_auc': 0.88,
                        },
                        'physics_summary': {
                            'failed_row_count': 3,
                            'unique_hotspot_count': 2,
                        },
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )
    manifest_json = tmp_path / 'manifest.json'
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / 'tools' / 'build_idp_release_manifest.py'),
            '--summary-json',
            str(summary_path),
            '--out-json',
            str(manifest_json),
            '--release-label',
            'test_release',
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    manifest = json.loads(manifest_json.read_text(encoding='utf-8'))
    assert manifest['release_label'] == 'test_release'
    assert manifest['acceptance']['pass'] is True
    assert manifest['acceptance']['all_fold_pass'] is True
    assert len(manifest['fold_artifacts']) == 2
    assert manifest['combined_physics_summary']['failed_row_count'] == 3
    assert manifest['fold_artifacts'][0]['eval_corrected_csv'].endswith('_eval_corrected_targets.csv')


def test_check_idp_holdout_regression(tmp_path):
    baseline_manifest = tmp_path / 'baseline_manifest.json'
    baseline_manifest.write_text(
        json.dumps(
            {
                'release_label': 'baseline',
                'acceptance': {
                    'pass': True,
                    'all_fold_pass': True,
                    'combined_gate_pass': False,
                    'fold_count': 2,
                    'baseline_pass_folds': 2,
                    'corrected_pass_folds': 2,
                },
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )
    candidate_summary = tmp_path / 'candidate_summary.json'
    candidate_summary.write_text(
        json.dumps(
            {
                'pass': True,
                'all_fold_pass': True,
                'combined_gate_pass': False,
                'fold_count': 2,
                'corrected_pass_folds': 2,
                'combined_gate': {
                    'payload': {
                        'classification_metrics': {
                            'branch_macro_f1': 1.0,
                            'dominant_state_accuracy': 0.95,
                            'llps_flag_pr_auc': 0.9,
                            'aggregation_flag_pr_auc': 0.6,
                        },
                        'ranking_metrics': {
                            'compactness_rank_auc': 0.9,
                            'helicity_rank_auc': 0.91,
                            'condensation_rank_auc': 0.92,
                        },
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )
    out_json = tmp_path / 'regression.json'
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / 'tools' / 'check_idp_holdout_regression.py'),
            '--baseline-manifest-json',
            str(baseline_manifest),
            '--candidate-summary-json',
            str(candidate_summary),
            '--out-json',
            str(out_json),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out_json.read_text(encoding='utf-8'))
    assert payload['summary']['pass'] is True
    assert payload['candidate']['corrected_pass_folds'] == 2


def test_resolve_and_load_frozen_labels(tmp_path):
    from tools.run_idp_3bead_holdout_pipeline import _resolve_frozen_labels_csv
    from tools.run_idp_3bead_evaluator import _load_frozen_labels

    g1_csv = tmp_path / 'baseline_fold1_eval_corrected_targets.csv'
    g2_csv = tmp_path / 'baseline_fold2_eval_corrected_targets.csv'
    fieldnames = ['target', 'condition_group', 'true_dominant_state', 'true_aggregation_flag', 'true_llps_flag']
    for path, rows in (
        (g1_csv, [
            {'target': 'g1_a', 'condition_group': 'base', 'true_dominant_state': 'helix_enriched', 'true_aggregation_flag': '1', 'true_llps_flag': '0'},
            {'target': 'g1_b', 'condition_group': 'salt', 'true_dominant_state': 'compact_disordered', 'true_aggregation_flag': '0', 'true_llps_flag': '0'},
        ]),
        (g2_csv, [
            {'target': 'g2_a', 'condition_group': 'base', 'true_dominant_state': 'sticky_condensed', 'true_aggregation_flag': '0', 'true_llps_flag': '1'},
            {'target': 'g2_b', 'condition_group': 'salt', 'true_dominant_state': 'expanded_disordered', 'true_aggregation_flag': '0', 'true_llps_flag': '0'},
        ]),
    ):
        with path.open('w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    baseline_manifest = tmp_path / 'baseline_manifest.json'
    baseline_manifest.write_text(
        json.dumps(
            {
                'fold_artifacts': [
                    {'fold_index': 1, 'holdout': 'g1', 'eval_corrected_csv': str(g1_csv)},
                    {'fold_index': 2, 'holdout': 'g2', 'eval_corrected_csv': str(g2_csv)},
                ]
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )
    resolved = _resolve_frozen_labels_csv(str(baseline_manifest), fold_idx=1, holdout='g1')
    assert resolved == str(g1_csv)
    frozen = _load_frozen_labels(resolved)
    assert frozen['g1_a::base']['true_dominant_state'] == 'helix_enriched'
    assert frozen['g1_b::salt']['true_dominant_state'] == 'compact_disordered'


def test_resolve_frozen_labels_prefers_holdout_name_over_fold_index(tmp_path):
    from tools.run_idp_3bead_holdout_pipeline import _resolve_frozen_labels_csv

    wrong_idx_csv = tmp_path / 'wrong_fold4_eval_corrected_targets.csv'
    right_holdout_csv = tmp_path / 'tau_2n4r_eval_corrected_targets.csv'
    for path in (wrong_idx_csv, right_holdout_csv):
        path.write_text(
            "target,condition_group,true_dominant_state,true_aggregation_flag,true_llps_flag\n"
            "x,base,compact_disordered,1,0\n",
            encoding='utf-8',
        )

    baseline_manifest = tmp_path / 'baseline_manifest.json'
    baseline_manifest.write_text(
        json.dumps(
            {
                'fold_artifacts': [
                    {'fold_index': 4, 'holdout': 'tardbp_ctd', 'eval_corrected_csv': str(wrong_idx_csv)},
                    {'fold_index': 10, 'holdout': 'tau_2n4r_fragment', 'eval_corrected_csv': str(right_holdout_csv)},
                ]
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )

    resolved = _resolve_frozen_labels_csv(
        str(baseline_manifest),
        fold_idx=4,
        holdout='tau_2n4r_fragment',
    )
    assert resolved == str(right_holdout_csv)


def test_resolve_frozen_labels_falls_back_to_fold_index_for_legacy_manifest(tmp_path):
    from tools.run_idp_3bead_holdout_pipeline import _resolve_frozen_labels_csv

    legacy_csv = tmp_path / 'legacy_fold6_eval_corrected_targets.csv'
    legacy_csv.write_text(
        "target,condition_group,true_dominant_state,true_aggregation_flag,true_llps_flag\n"
        "x,base,compact_disordered,1,0\n",
        encoding='utf-8',
    )

    baseline_manifest = tmp_path / 'baseline_manifest_legacy.json'
    baseline_manifest.write_text(
        json.dumps(
            {
                'fold_artifacts': [
                    {'fold_index': 6, 'eval_corrected_csv': str(legacy_csv)},
                ]
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )

    resolved = _resolve_frozen_labels_csv(
        str(baseline_manifest),
        fold_idx=6,
        holdout='tau_k18',
    )
    assert resolved == str(legacy_csv)


def test_require_outputs_needs_summary_file_even_when_stage_progress_looks_done():
    from tools.run_idp_3bead_holdout_pipeline import _require_outputs

    status = {'rc': 0}
    ok = _require_outputs(
        status,
        ['/tmp/definitely_missing_eval_summary.json'],
        stage_name='eval_baseline',
    )
    assert ok is False
    assert status['stage_name'] == 'eval_baseline'
    assert status['missing_outputs'] == ['/tmp/definitely_missing_eval_summary.json']


def test_append_kalman_shadow_args_appends_passthrough_flags():
    from tools.run_idp_3bead_holdout_pipeline import _append_kalman_shadow_args, build_parser

    args = build_parser().parse_args(
        [
            '--config-json',
            'config/test.json',
            '--kalman-shadow-enable',
            '1',
            '--kalman-shadow-family-token',
            'idp',
            '--kalman-shadow-obs-noise-scale',
            '0.15',
            '--kalman-shadow-process-noise-scale',
            '0.03',
        ]
    )
    cmd = ['python3', 'tools/run_idp_3bead_evaluator.py']
    out = _append_kalman_shadow_args(cmd, args)
    assert '--kalman-shadow-enable' in out
    assert out[out.index('--kalman-shadow-enable') + 1] == '1'
    assert out[out.index('--kalman-shadow-family-token') + 1] == 'idp'
    assert out[out.index('--kalman-shadow-obs-noise-scale') + 1] == '0.15'
    assert out[out.index('--kalman-shadow-process-noise-scale') + 1] == '0.03'


def test_retryable_gpu_fault_detection():
    from tools.run_idp_3bead_holdout_pipeline import _is_retryable_gpu_fault

    assert _is_retryable_gpu_fault({'rc': -6, 'stderr_tail': 'Memory access fault by GPU node-1', 'stdout_tail': ''}) is True
    assert _is_retryable_gpu_fault({'rc': -6, 'stderr_tail': 'hipErrorIllegalAddress', 'stdout_tail': ''}) is True
    assert _is_retryable_gpu_fault({'rc': 1, 'stderr_tail': 'plain python error', 'stdout_tail': ''}) is False
    assert _is_retryable_gpu_fault({'rc': 0, 'stderr_tail': 'Memory access fault by GPU node-1', 'stdout_tail': ''}) is False


def test_build_idp_release_manifest_includes_diagnostic_artifacts_when_present(tmp_path):
    summary_path = tmp_path / 'release_summary.json'
    summary_path.write_text(
        json.dumps(
            {
                'pass': True,
                'all_fold_pass': True,
                'combined_gate_pass': True,
                'baseline_pass_folds': 1,
                'corrected_pass_folds': 1,
                'fold_count': 1,
                'folds': [
                    {'holdout': 'g1', 'pass': True, 'baseline_gate': {'pass': True}, 'corrected_gate': {'pass': True}},
                ],
                'combined_gate': {'payload': {'classification_metrics': {}, 'ranking_metrics': {}, 'physics_summary': {}}},
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )
    prefix = tmp_path / 'release'
    for rel in (
        prefix.with_name(prefix.name + '_global_aggregation_calibrator.json'),
        prefix.with_name(prefix.name + '_global_aggregation_calibrator.md'),
        prefix.with_name(prefix.name + '_global_aggregation_calibrator_predictions.csv'),
        prefix.with_name(prefix.name + '_global_aggregation_dashboard.html'),
        prefix.with_name(prefix.name + '_global_aggregation_dashboard.json'),
    ):
        rel.write_text('x', encoding='utf-8')

    manifest_json = tmp_path / 'manifest.json'
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / 'tools' / 'build_idp_release_manifest.py'),
            '--summary-json',
            str(summary_path),
            '--out-json',
            str(manifest_json),
            '--release-label',
            'diag_test_release',
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    manifest = json.loads(manifest_json.read_text(encoding='utf-8'))
    diag = manifest.get('diagnostic_artifacts', {})
    assert diag['global_aggregation_calibrator_json'].endswith('_global_aggregation_calibrator.json')
    assert diag['global_aggregation_calibrator_md'].endswith('_global_aggregation_calibrator.md')
    assert diag['global_aggregation_predictions_csv'].endswith('_global_aggregation_calibrator_predictions.csv')
    assert diag['global_aggregation_dashboard_html'].endswith('_global_aggregation_dashboard.html')
    assert diag['global_aggregation_dashboard_json'].endswith('_global_aggregation_dashboard.json')
