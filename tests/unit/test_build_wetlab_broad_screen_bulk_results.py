from __future__ import annotations

from tools import build_wetlab_broad_screen_bulk_results as mod


def test_build_wetlab_broad_screen_bulk_results_tracks_calibration_readiness_and_actions() -> None:
    payload = mod.build_payload(
        source_payload={
            'rows': [
                {'target_id': 'CA IX', 'compound_name': 'Acetazolamide', 'bulk_rank': 1, 'bulk_score': 92.4, 'seed_status': 'broad_screen_actual_result_example'},
                {'target_id': 'CA IX', 'compound_name': 'Methazolamide', 'bulk_rank': 2, 'bulk_score': 89.1, 'seed_status': 'broad_screen_actual_result_example'},
                {'target_id': 'CA IX', 'compound_name': 'Dichlorphenamide', 'bulk_rank': 3, 'bulk_score': 97.0, 'seed_status': 'broad_screen_runtime_validation_result'},
                {'target_id': 'CA IX', 'compound_name': 'Topiramate', 'bulk_rank': 4, 'bulk_score': 80.0, 'seed_status': 'bootstrap_from_manual_fill_map'},
            ]
        }
    )

    summary = payload['summary']
    calibration = payload['calibration']

    assert summary['status'] == 'wetlab_broad_screen_bulk_results_ready'
    assert summary['calibration_readiness'] == 'calibration_ready'
    assert summary['threshold_posture'] == 'tighten'
    assert summary['decision_class_update_hint'] == 'promote_threshold_tighten_class'
    assert summary['calibration_action_bucket'] == 'tighten_thresholds'
    assert summary['confidence_bucket'] == 'high_confidence'
    assert summary['calibration_registry_presence'] == 'absent'
    assert summary['commercial_weight'] == 1.2
    assert summary['commercial_weight_source'] == 'default_from_readiness'
    assert summary['score_posture'] == 'tighten'
    assert summary['next_required_step'].startswith('Use these bulk rows to regenerate the broad-screen repurposing autofill')

    assert calibration['calibration_readiness'] == 'calibration_ready'
    assert calibration['threshold_posture'] == 'tighten'
    assert calibration['decision_class_update_hint'] == 'promote_threshold_tighten_class'
    assert calibration['calibration_action_bucket'] == 'tighten_thresholds'
    assert calibration['confidence_bucket'] == 'high_confidence'
    assert calibration['calibration_registry_presence'] == 'absent'
    assert calibration['commercial_weight'] == 1.2
    assert calibration['score_posture'] == 'tighten'


def test_build_wetlab_broad_screen_bulk_results_tracks_registry_overrides() -> None:
    payload = mod.build_payload(
        source_payload={
            'calibration_registry': {
                'CA IX': {
                    'decision_class': 'promote_threshold_tighten_class',
                    'commercial_weight': 1.35,
                    'score_posture': 'tighten',
                    'reason': 'Actual rows justify a tightened commercial posture.',
                }
            },
            'rows': [
                {'target_id': 'CA IX', 'compound_name': 'Acetazolamide', 'bulk_rank': 1, 'bulk_score': 92.4, 'seed_status': 'broad_screen_actual_result_example'},
                {'target_id': 'CA IX', 'compound_name': 'Methazolamide', 'bulk_rank': 2, 'bulk_score': 89.1, 'seed_status': 'broad_screen_actual_result_example'},
                {'target_id': 'CA IX', 'compound_name': 'Dichlorphenamide', 'bulk_rank': 3, 'bulk_score': 97.0, 'seed_status': 'broad_screen_runtime_validation_result'},
                {'target_id': 'CA IX', 'compound_name': 'Topiramate', 'bulk_rank': 4, 'bulk_score': 80.0, 'seed_status': 'bootstrap_from_manual_fill_map'},
            ]
        }
    )

    summary = payload['summary']
    calibration = payload['calibration']
    assert summary['calibration_registry_presence'] == 'present'
    assert summary['calibration_registry_entry_count'] == 1
    assert summary['calibration_registry_target_count'] == 1
    assert summary['calibration_registry_override_target_count'] == 1
    assert summary['calibration_registry_default_target_count'] == 0
    assert calibration['calibration_registry_presence'] == 'present'
    assert calibration['calibration_registry_override_target_count'] == 1
