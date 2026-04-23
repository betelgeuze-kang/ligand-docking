from __future__ import annotations

import json
from pathlib import Path

from tools import build_wetlab_broad_screen_actual_result_intake_packet as mod


def test_build_wetlab_broad_screen_actual_result_intake_packet_defaults_caix_shard_04() -> None:
    payload = mod.build_payload(target_id='CA IX', shard_id='04_of_20', schema_payload={'rows':[{'field_name':'target_id','required':True},{'field_name':'compound_name','required':True},{'field_name':'bulk_rank','required':True},{'field_name':'bulk_score','required':True},{'field_name':'shard_id','required':False}]}, source_payload={'rows':[{'target_id':'CA IX'}]}, example_payload={'rows':[]})
    summary = payload['summary']
    assert summary['status'] == 'wetlab_broad_screen_actual_result_intake_packet_ready'
    assert summary['target_id'] == 'CA IX'
    assert summary['shard_id'] == '04_of_20'
    assert summary['required_field_count'] == 4
    assert summary['source_calibration_registry_presence'] == 'absent'
    assert summary['source_calibration_registry_state'] == 'default_only'
    assert summary['source_calibration_readiness'] == 'calibration_candidate'
    assert summary['source_commercial_weight'] == 1.05
    assert summary['source_commercial_weight_source'] == 'default_from_readiness'
    assert summary['source_score_posture'] == summary['source_threshold_posture']


def test_build_wetlab_broad_screen_actual_result_intake_packet_tracks_richer_calibration_outputs() -> None:
    payload = mod.build_payload(
        target_id='CA IX',
        shard_id='07_of_20',
        schema_payload={
            'rows': [
                {'field_name': 'target_id', 'required': True},
                {'field_name': 'compound_name', 'required': True},
                {'field_name': 'bulk_rank', 'required': True},
                {'field_name': 'bulk_score', 'required': True},
                {'field_name': 'shard_id', 'required': False},
                {'field_name': 'first_contact_use_mode', 'required': False},
            ]
        },
        source_payload={
            'summary': {'source_tag': 'calibration_regression'},
            'calibration_registry': {
                'CA IX': {
                    'selected_threshold_A': 2.6,
                    'decision_class': 'promote_threshold_tighten_class',
                    'commercial_weight': 1.35,
                    'score_posture': 'tighten',
                    'reason': 'Actual rows support a tightened review posture.',
                }
            },
            'rows': [
                {
                    'target_id': 'CA IX',
                    'compound_name': 'Actual A',
                    'bulk_rank': 1,
                    'bulk_score': 95.0,
                    'seed_status': 'broad_screen_actual_result_example',
                    'first_contact_use_mode': 'manual_followup',
                },
                {
                    'target_id': 'CA IX',
                    'compound_name': 'Bootstrap B',
                    'bulk_rank': 2,
                    'bulk_score': 92.0,
                    'seed_status': 'bootstrap_from_manual_fill_map',
                    'first_contact_use_mode': 'bootstrap',
                },
                {
                    'target_id': 'CA IX',
                    'compound_name': 'Actual C',
                    'bulk_rank': 3,
                    'bulk_score': 89.0,
                    'seed_status': 'broad_screen_runtime_validation_result',
                    'first_contact_use_mode': 'manual_followup',
                },
                {
                    'target_id': 'CA IX',
                    'compound_name': 'Bootstrap D',
                    'bulk_rank': 4,
                    'bulk_score': 79.0,
                    'seed_status': 'bootstrap_from_manual_fill_map',
                    'first_contact_use_mode': 'bootstrap',
                },
                {
                    'target_id': 'Dengue NS2B-NS3 protease',
                    'compound_name': 'Other',
                    'bulk_rank': 1,
                    'bulk_score': 88.0,
                    'seed_status': 'broad_screen_actual_result_example',
                    'first_contact_use_mode': 'manual_followup',
                },
            ],
        },
        example_payload={
            'rows': [
                {'target_id': 'CA IX', 'shard_id': '07_of_20', 'compound_name': 'Example'},
                {'target_id': 'CA IX', 'shard_id': '99_of_20', 'compound_name': 'Ignored'},
            ]
        },
    )
    summary = payload['summary']
    calibration = payload['calibration']
    row = payload['rows'][0]

    assert summary['required_field_count'] == 4
    assert summary['optional_field_count'] == 2
    assert summary['existing_target_rows_in_source'] == 4
    assert summary['source_actual_row_count'] == 2
    assert summary['source_bootstrap_row_count'] == 2
    assert summary['source_actual_top3_count'] == 2
    assert summary['source_actual_row_fraction'] == 0.5
    assert summary['source_calibration_state'] == 'partial_actual_support'
    assert summary['source_calibration_readiness'] == 'calibration_candidate'
    assert summary['source_calibration_registry_presence'] == 'present'
    assert summary['source_calibration_registry_state'] == 'override_applied'
    assert summary['source_threshold_posture'] == 'tighten'
    assert summary['source_threshold_posture_default'] == 'prepare_tighten'
    assert summary['source_threshold_posture_source'] == 'registry_override'
    assert summary['source_decision_class_update_hint'] == 'promote_threshold_tighten_class'
    assert summary['source_decision_class_update_hint_source'] == 'registry_override'
    assert summary['source_calibration_action_bucket'] == 'prepare_threshold_update'
    assert summary['source_confidence_bucket'] == 'moderate_confidence'
    assert summary['source_commercial_weight'] == 1.35
    assert summary['source_commercial_weight_source'] == 'registry_override'
    assert summary['source_score_posture'] == 'tighten'
    assert summary['source_selected_threshold_A'] == 2.6
    assert summary['example_row_count_for_shard'] == 1
    assert summary['next_required_step'].startswith('Fill a real shard-result JSON')

    assert calibration['target_id'] == 'CA IX'
    assert calibration['source_actual_row_count'] == 2
    assert calibration['source_bootstrap_row_count'] == 2
    assert calibration['source_actual_top3_count'] == 2
    assert calibration['source_actual_row_fraction'] == 0.5
    assert calibration['source_bulk_rank_span'] == '1..4'
    assert calibration['source_bulk_score_span'] == '79.0..95.0'
    assert calibration['source_calibration_state'] == 'partial_actual_support'
    assert calibration['source_calibration_readiness'] == 'calibration_candidate'
    assert calibration['source_calibration_registry_presence'] == 'present'
    assert calibration['source_calibration_registry_state'] == 'override_applied'
    assert calibration['source_threshold_posture'] == 'tighten'
    assert calibration['source_threshold_posture_default'] == 'prepare_tighten'
    assert calibration['source_threshold_posture_source'] == 'registry_override'
    assert calibration['source_decision_class_update_hint'] == 'promote_threshold_tighten_class'
    assert calibration['source_decision_class_update_hint_source'] == 'registry_override'
    assert calibration['source_calibration_action_bucket'] == 'prepare_threshold_update'
    assert calibration['source_confidence_bucket'] == 'moderate_confidence'
    assert calibration['source_commercial_weight'] == 1.35
    assert calibration['source_score_posture'] == 'tighten'
    assert calibration['source_selected_threshold_A'] == 2.6
    structured = payload['structured']
    assert structured['calibration_fields'] == 'bulk_rank ; bulk_score ; seed_status ; first_contact_use_mode ; source_anchor ; source_url'
    assert structured['feedback_loop_note'].startswith('The merged source rows should keep actual-versus-bootstrap provenance')

    assert row['required_fields'] == 'target_id ; compound_name ; bulk_rank ; bulk_score'
    assert row['optional_fields'] == 'shard_id ; first_contact_use_mode'
    assert row['existing_target_rows_in_source'] == 4
    assert row['source_actual_row_count'] == 2
    assert row['source_bootstrap_row_count'] == 2
    assert row['source_actual_top3_count'] == 2
    assert row['source_actual_row_fraction'] == 0.5
    assert row['source_rank_span'] == '1..4'
    assert row['source_score_span'] == '79.0..95.0'
    assert row['calibration_hint'] == 'Capture the actual shard rows with stable bulk_rank and bulk_score provenance so target rerank can keep bootstrap-heavy targets conservative.'
    assert row['example_row_count_for_shard'] == 1
    assert row['merge_command'].startswith('python3 tools/build_wetlab_broad_screen_bulk_results_source_merge.py')
    assert row['source_calibration_readiness'] == 'calibration_candidate'
    assert row['source_calibration_registry_presence'] == 'present'
    assert row['source_calibration_registry_state'] == 'override_applied'
    assert row['source_threshold_posture'] == 'tighten'
    assert row['source_threshold_posture_default'] == 'prepare_tighten'
    assert row['source_threshold_posture_source'] == 'registry_override'
    assert row['source_decision_class_update_hint'] == 'promote_threshold_tighten_class'
    assert row['source_decision_class_update_hint_source'] == 'registry_override'
    assert row['source_calibration_action_bucket'] == 'prepare_threshold_update'
    assert row['source_confidence_bucket'] == 'moderate_confidence'
    assert row['source_commercial_weight'] == 1.35
    assert row['source_score_posture'] == 'tighten'
    assert row['source_selected_threshold_A'] == 2.6


def test_build_wetlab_broad_screen_actual_result_intake_packet_builds_comparison_when_actual_table_is_provided(tmp_path: Path) -> None:
    actual_csv = tmp_path / "actual.csv"
    actual_csv.write_text(
        "\n".join(
            [
                "target_id,compound_name,percent_inhibition,replicate_count",
                "CA IX,Actual A,92,3",
                "CA IX,Actual C,71,3",
                "CA IX,Bootstrap B,15,3",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    payload = mod.build_payload(
        target_id="CA IX",
        shard_id="07_of_20",
        schema_payload={"rows": [{"field_name": "target_id", "required": True}, {"field_name": "compound_name", "required": True}]},
        source_payload={
            "rows": [
                {"target_id": "CA IX", "compound_name": "Actual A", "bulk_rank": 1, "bulk_score": 95.0},
                {"target_id": "CA IX", "compound_name": "Bootstrap B", "bulk_rank": 2, "bulk_score": 89.0},
                {"target_id": "CA IX", "compound_name": "Actual C", "bulk_rank": 3, "bulk_score": 84.0},
            ]
        },
        example_payload={"rows": []},
        actual_results_table=str(actual_csv),
        intake_out_md=str(tmp_path / "caix_intake_packet_current.md"),
    )

    summary = payload["summary"]
    row = payload["rows"][0]

    assert summary["comparison_summary_status"] == "wetlab_prediction_result_comparison_ready"
    assert summary["comparison_actual_value_kind"] == "percent_inhibition"
    assert summary["comparison_merged_row_count"] == 3
    assert summary["comparison_spearman_prediction_vs_activity"] == 0.5
    assert row["comparison_top3_hit_count"] == 2
    assert Path(summary["comparison_artifact_json"]).exists()
    assert Path(summary["comparison_artifact_md"]).exists()
    comparison_payload = json.loads(Path(summary["comparison_artifact_json"]).read_text(encoding="utf-8"))
    assert comparison_payload["summary"]["status"] == "wetlab_prediction_result_comparison_ready"
