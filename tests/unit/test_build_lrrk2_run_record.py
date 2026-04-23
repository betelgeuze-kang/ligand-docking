from __future__ import annotations

import pytest

from tools import build_lrrk2_run_record as mod

LAUNCH = {
    'summary': {
        'status': 'lrrk2_launch_packet_ready',
        'serialized_queue_rank': 5,
        'serialized_run_order': '5_of_5_in_wave2',
        'partner_track_id': 'MJFF_LRRK2',
    }
}
GO_NO_GO = {'summary': {'status': 'lrrk2_go_no_go_card_ready'}}


def test_build_lrrk2_run_record_defaults_to_blocked_when_tcruzi_gate_is_closed() -> None:
    payload = mod.build_payload(
        LAUNCH,
        {'summary': {'status': 'lrrk2_result_review_ready', 'lrrk2_gate_open': False}},
        GO_NO_GO,
    )
    summary = payload['summary']

    assert summary['status'] == 'lrrk2_run_record_ready'
    assert summary['execution_state'] == 'blocked_on_previous_review'
    assert summary['queue_status_now'] == 'blocked_on_previous_review'
    assert summary['successor_target'] == 'Wave 2 completion'
    assert summary['successor_gate_open'] is False
    assert summary['successor_gate_state'] == 'blocked_until_lrrk2_result_ready_or_explicit_hold'


def test_build_lrrk2_run_record_opens_terminal_review_after_result_ready() -> None:
    payload = mod.build_payload(
        LAUNCH,
        {
            'summary': {
                'status': 'lrrk2_result_review_ready',
                'lrrk2_gate_open': True,
                'lrrk2_review_state': 'ready_to_capture_lrrk2_result_review',
            }
        },
        GO_NO_GO,
        result_summary={'summary': {'status': 'completed', 'result_review_ready': True}},
    )
    summary = payload['summary']

    assert summary['result_summary_detected'] is True
    assert summary['execution_state'] == 'result_ready'
    assert summary['queue_status_now'] == 'result_ready_for_terminal_review'
    assert summary['successor_target'] == 'Wave 2 completion'
    assert summary['successor_gate_open'] is True
    assert summary['successor_gate_state'] == 'wave2_terminal_review_open'
    assert summary['successor_next_queue_state'] == 'terminal_review_ready'


def test_build_lrrk2_run_record_rejects_advanced_state_when_gate_is_closed() -> None:
    with pytest.raises(ValueError):
        mod.build_payload(
            LAUNCH,
            {'summary': {'status': 'lrrk2_result_review_ready', 'lrrk2_gate_open': False}},
            GO_NO_GO,
            run_state='running',
        )


def test_build_lrrk2_run_record_accepts_execution_gate_open_fallback() -> None:
    payload = mod.build_payload(
        LAUNCH,
        {
            'summary': {
                'status': 'lrrk2_result_review_ready',
                'execution_gate_open': True,
                'lrrk2_review_state': 'ready_to_capture_lrrk2_result_review',
            }
        },
        GO_NO_GO,
        live_progress={'summary': {'status': 'running', 'active_stage_label': 'kinase_primary_assay'}},
    )
    summary = payload['summary']

    assert summary['upstream_gate_open'] is True
    assert summary['execution_state'] == 'running'
    assert summary['queue_status_now'] == 'running_after_previous_review'
