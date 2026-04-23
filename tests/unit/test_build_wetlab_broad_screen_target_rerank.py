from __future__ import annotations

from tools import build_wetlab_broad_screen_target_rerank as mod


def test_build_wetlab_broad_screen_target_rerank_marks_partial_actual_top3() -> None:
    payload = mod.build_payload(
        source_payload={'rows':[
            {'target_id':'CA IX','compound_name':'Acetazolamide','bulk_rank':1,'bulk_score':92.4,'seed_status':'broad_screen_actual_result_example'},
            {'target_id':'CA IX','compound_name':'Methazolamide','bulk_rank':2,'bulk_score':89.1,'seed_status':'broad_screen_actual_result_example'},
            {'target_id':'CA IX','compound_name':'Dichlorphenamide','bulk_rank':3,'bulk_score':97.0,'seed_status':'bootstrap_from_manual_fill_map'},
        ]},
        progress_payload={'rows':[
            {'target_id':'CA IX','queue_status':'result_ready'},
            {'target_id':'CA IX','queue_status':'result_ready'},
            {'target_id':'CA IX','queue_status':'result_ready'},
        ]},
    )
    summary = payload['summary']
    row = payload['rows'][0]
    assert summary['status'] == 'wetlab_broad_screen_target_rerank_ready'
    assert row['target_id'] == 'CA IX'
    assert row['actual_top3_count'] == 2
    assert row['rerank_status'] == 'partial_actual_top3_not_full_bulk_ready'
    assert row['calibration_readiness'] == 'calibration_candidate'
    assert row['calibration_registry_presence'] == 'absent'
    assert row['calibration_registry_state'] == 'default_only'
    assert row['threshold_posture'] == 'prepare_tighten'
    assert row['threshold_posture_source'] == 'default_from_policy'
    assert row['decision_class_update_hint'] == 'promote_threshold_review_class'
    assert row['decision_class_update_hint_source'] == 'default_from_policy'
    assert row['calibration_action_bucket'] == 'prepare_threshold_update'
    assert row['confidence_bucket'] == 'watchlist'
    assert row['confidence_bucket_rank'] == 1
    assert row['commercial_weight'] == 1.05
    assert row['commercial_weight_source'] == 'default_from_readiness'
    assert row['score_posture'] == 'prepare_tighten'
    assert row['score_posture_source'] == 'default_from_policy'
    assert row['selected_threshold_A'] is None
    assert row['selected_threshold_A_source'] == 'default_unset'


def test_build_wetlab_broad_screen_target_rerank_marks_full_bulk_top3_ready() -> None:
    payload = mod.build_payload(
        source_payload={'rows':[
            {'target_id':'CA IX','compound_name':'Acetazolamide','bulk_rank':1,'bulk_score':92.4,'seed_status':'broad_screen_actual_result_example'},
            {'target_id':'CA IX','compound_name':'Methazolamide','bulk_rank':2,'bulk_score':89.1,'seed_status':'broad_screen_actual_result_example'},
            {'target_id':'CA IX','compound_name':'Dichlorphenamide','bulk_rank':3,'bulk_score':97.0,'seed_status':'broad_screen_runtime_validation_result'},
        ]},
        progress_payload={'rows':[
            {'target_id':'CA IX','queue_status':'result_ready'},
            {'target_id':'CA IX','queue_status':'result_ready'},
            {'target_id':'CA IX','queue_status':'result_ready'},
            {'target_id':'CA IX','queue_status':'result_ready'},
        ]},
    )
    row = payload['rows'][0]
    assert row['actual_top3_count'] == 3
    assert row['rerank_status'] == 'full_bulk_top3_ready'
    assert row['calibration_readiness'] == 'calibration_ready'
    assert row['threshold_posture'] == 'tighten'
    assert row['decision_class_update_hint'] == 'promote_threshold_tighten_class'
    assert row['calibration_action_bucket'] == 'tighten_thresholds'
    assert row['confidence_bucket'] == 'moderate_confidence'
    assert row['confidence_bucket_rank'] == 2


def test_build_wetlab_broad_screen_target_rerank_tracks_richer_calibration_outputs() -> None:
    payload = mod.build_payload(
        source_payload={
            'summary': {'source_tag': 'calibration_regression'},
            'rows': [
                {'target_id': 'CA IX', 'compound_name': 'Acetazolamide', 'bulk_rank': 1, 'bulk_score': 92.4, 'seed_status': 'broad_screen_actual_result_example', 'first_contact_use_mode': 'manual_followup'},
                {'target_id': 'CA IX', 'compound_name': 'Methazolamide', 'bulk_rank': 2, 'bulk_score': 89.1, 'seed_status': 'broad_screen_runtime_validation_result', 'first_contact_use_mode': 'manual_followup'},
                {'target_id': 'CA IX', 'compound_name': 'Dichlorphenamide', 'bulk_rank': 3, 'bulk_score': 97.0, 'seed_status': 'broad_screen_actual_result_example', 'first_contact_use_mode': 'manual_followup'},
                {'target_id': 'CA IX', 'compound_name': 'Topiramate', 'bulk_rank': 4, 'bulk_score': 80.0, 'seed_status': 'bootstrap_from_manual_fill_map', 'first_contact_use_mode': 'bootstrap'},
                {'target_id': 'Dengue NS2B-NS3 protease', 'compound_name': 'Eltrombopag', 'bulk_rank': 1, 'bulk_score': 88.0, 'seed_status': 'broad_screen_actual_result_example', 'first_contact_use_mode': 'manual_followup'},
                {'target_id': 'Dengue NS2B-NS3 protease', 'compound_name': 'Policresulen', 'bulk_rank': 2, 'bulk_score': 85.0, 'seed_status': 'bootstrap_from_manual_fill_map', 'first_contact_use_mode': 'bootstrap'},
            ],
        },
        progress_payload={'rows':[
            {'target_id':'CA IX','queue_status':'result_ready'},
            {'target_id':'CA IX','queue_status':'result_ready'},
            {'target_id':'Dengue NS2B-NS3 protease','queue_status':'result_ready'},
        ]},
    )

    summary = payload['summary']
    calibration = payload['calibration']
    caix_row = [row for row in payload['rows'] if row['target_id'] == 'CA IX'][0]
    dengue_row = [row for row in payload['rows'] if row['target_id'] == 'Dengue NS2B-NS3 protease'][0]

    assert summary['target_count'] == 2
    assert summary['full_bulk_ready_target_count'] == 1
    assert summary['partial_actual_target_count'] == 1
    assert summary['source_row_count'] == 6
    assert summary['source_actual_row_count'] == 4
    assert summary['source_bootstrap_row_count'] == 2
    assert summary['source_actual_target_count'] == 2
    assert summary['source_actual_top3_row_count'] == 4
    assert summary['source_actual_top3_target_count'] == 2
    assert summary['calibration_state'] == 'actual_supported'
    assert summary['source_calibration_readiness'] == 'calibration_ready'
    assert summary['source_threshold_posture'] == 'tighten'
    assert summary['source_decision_class_update_hint'] == 'promote_threshold_tighten_class'
    assert summary['source_calibration_action_bucket'] == 'tighten_thresholds'
    assert summary['source_confidence_bucket'] == 'high_confidence'
    assert summary['calibration_readiness_counts'] == {'calibration_candidate': 1, 'calibration_ready': 1}
    assert summary['decision_class_update_counts'] == {
        'promote_threshold_review_class': 1,
        'promote_threshold_tighten_class': 1,
    }
    assert summary['calibration_action_bucket_counts'] == {
        'prepare_threshold_update': 1,
        'tighten_thresholds': 1,
    }
    assert summary['next_required_step'].startswith('Keep merging real shard rows until targets reach full_bulk_top3_ready')

    assert calibration['source_row_count'] == 6
    assert calibration['actual_row_count'] == 4
    assert calibration['bootstrap_row_count'] == 2
    assert calibration['actual_target_count'] == 2
    assert calibration['actual_target_ids'] == ['CA IX', 'Dengue NS2B-NS3 protease']
    assert calibration['actual_top3_row_count'] == 4
    assert calibration['actual_top3_target_count'] == 2
    assert calibration['actual_rank1_row_count'] == 2
    assert calibration['actual_rank2_3_row_count'] == 2
    assert calibration['actual_rank_gt3_row_count'] == 0
    assert calibration['actual_seed_status_counts'] == {'broad_screen_actual_result_example': 3, 'broad_screen_runtime_validation_result': 1}
    assert calibration['actual_first_contact_use_mode_counts'] == {'manual_followup': 4}
    assert calibration['calibration_state'] == 'actual_supported'
    assert calibration['calibration_readiness'] == 'calibration_ready'
    assert calibration['threshold_posture'] == 'tighten'
    assert calibration['decision_class_update_hint'] == 'promote_threshold_tighten_class'
    assert calibration['calibration_action_bucket'] == 'tighten_thresholds'
    assert calibration['confidence_bucket'] == 'high_confidence'
    assert calibration['source_summary'] == {'source_tag': 'calibration_regression'}

    assert caix_row['completed_shard_count'] == 2
    assert caix_row['source_row_count'] == 4
    assert caix_row['actual_row_count'] == 3
    assert caix_row['bootstrap_row_count'] == 1
    assert caix_row['actual_row_fraction'] == 0.75
    assert caix_row['actual_top3_count'] == 3
    assert caix_row['rerank_status'] == 'full_bulk_top3_ready'
    assert caix_row['calibration_hint'] == 'full_actual_support'
    assert caix_row['calibration_advice'].startswith('Actual rows are strong enough to treat the target as higher-confidence')
    assert caix_row['calibration_readiness'] == 'calibration_ready'
    assert caix_row['threshold_posture'] == 'tighten'
    assert caix_row['decision_class_update_hint'] == 'promote_threshold_tighten_class'
    assert caix_row['calibration_action_bucket'] == 'tighten_thresholds'
    assert caix_row['top1_compound'] == 'Acetazolamide'
    assert caix_row['top2_compound'] == 'Methazolamide'
    assert caix_row['top3_compound'] == 'Dichlorphenamide'

    assert dengue_row['completed_shard_count'] == 1
    assert dengue_row['source_row_count'] == 2
    assert dengue_row['actual_row_count'] == 1
    assert dengue_row['bootstrap_row_count'] == 1
    assert dengue_row['actual_row_fraction'] == 0.5
    assert dengue_row['actual_top3_count'] == 1
    assert dengue_row['rerank_status'] == 'partial_actual_top3_not_full_bulk_ready'
    assert dengue_row['calibration_hint'] == 'partial_actual_support'
    assert dengue_row['calibration_advice'].startswith('Use the actual rows as advisory calibration only')
    assert dengue_row['calibration_readiness'] == 'calibration_candidate'
    assert dengue_row['threshold_posture'] == 'prepare_tighten'
    assert dengue_row['decision_class_update_hint'] == 'promote_threshold_review_class'
    assert dengue_row['calibration_action_bucket'] == 'prepare_threshold_update'


def test_build_wetlab_broad_screen_target_rerank_applies_calibration_registry_overrides() -> None:
    payload = mod.build_payload(
        source_payload={
            'calibration_registry': {
                'CA IX': {
                    'selected_threshold_A': 2.75,
                    'decision_class': 'promote_threshold_tighten_class',
                    'commercial_weight': 1.4,
                    'score_posture': 'tighten',
                    'reason': 'Actual rows support a tighter commercial gate.',
                }
            },
            'rows': [
                {'target_id': 'CA IX', 'compound_name': 'Acetazolamide', 'bulk_rank': 1, 'bulk_score': 92.4, 'seed_status': 'broad_screen_actual_result_example'},
                {'target_id': 'CA IX', 'compound_name': 'Methazolamide', 'bulk_rank': 2, 'bulk_score': 89.1, 'seed_status': 'broad_screen_actual_result_example'},
                {'target_id': 'CA IX', 'compound_name': 'Dichlorphenamide', 'bulk_rank': 3, 'bulk_score': 97.0, 'seed_status': 'bootstrap_from_manual_fill_map'},
            ],
        },
        progress_payload={'rows':[
            {'target_id':'CA IX','queue_status':'result_ready'},
            {'target_id':'CA IX','queue_status':'result_ready'},
            {'target_id':'CA IX','queue_status':'result_ready'},
        ]},
    )
    row = payload['rows'][0]
    summary = payload['summary']
    assert row['calibration_registry_presence'] == 'present'
    assert row['calibration_registry_match'] is True
    assert row['calibration_registry_state'] == 'override_applied'
    assert row['calibration_registry_source'] == 'source_payload.calibration_registry'
    assert row['calibration_registry_reason'] == 'Actual rows support a tighter commercial gate.'
    assert row['selected_threshold_A'] == 2.75
    assert row['selected_threshold_A_source'] == 'registry_override'
    assert row['threshold_posture'] == 'tighten'
    assert row['threshold_posture_default'] == 'prepare_tighten'
    assert row['threshold_posture_source'] == 'registry_override'
    assert row['decision_class_update_hint'] == 'promote_threshold_tighten_class'
    assert row['decision_class_update_hint_source'] == 'registry_override'
    assert row['commercial_weight'] == 1.4
    assert row['commercial_weight_source'] == 'registry_override'
    assert row['score_posture'] == 'tighten'
    assert row['score_posture_source'] == 'registry_override'
    assert summary['calibration_registry_presence'] == 'present'
    assert summary['calibration_registry_override_target_count'] == 1
