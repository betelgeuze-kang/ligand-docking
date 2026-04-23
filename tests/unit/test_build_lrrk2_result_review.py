from __future__ import annotations

from tools import build_lrrk2_result_review as mod

LAUNCH = {
    'summary': {
        'status': 'lrrk2_launch_packet_ready',
        'serialized_queue_rank': 5,
        'serialized_run_order': '5_of_5_in_wave2',
        'partner_track_id': 'MJFF_LRRK2',
        'blocking_rule': 'Do not start LRRK2 until T. cruzi KRS1 resolves.',
        'launch_readiness': 'ready_for_serialized_execution',
    }
}


def test_build_lrrk2_result_review_blocks_without_tcruzi_resolution() -> None:
    payload = mod.build_payload({}, LAUNCH)
    summary = payload['summary']

    assert summary['status'] == 'lrrk2_result_review_ready'
    assert summary['upstream_gate_open'] is False
    assert summary['content_ready'] is True
    assert summary['lrrk2_gate_open'] is False
    assert summary['lrrk2_review_state'] == 'blocked_on_tcruzi_krs1_result_review'
    assert summary['queue_status_now'] == 'blocked_on_previous_review'
    assert summary['successor_target'] == 'Wave 2 completion'


def test_build_lrrk2_result_review_opens_terminal_gate_when_run_record_is_result_ready() -> None:
    payload = mod.build_payload(
        {
            'summary': {
                'status': 'tcruzi_krs1_result_review_ready',
                'successor_gate_open': True,
                'successor_gate_state': 'open_for_lrrk2_execution',
            }
        },
        LAUNCH,
        {'summary': {'execution_state': 'result_ready', 'run_started': True, 'result_review_ready': True}},
    )
    summary = payload['summary']

    assert summary['upstream_gate_open'] is True
    assert summary['content_ready'] is True
    assert summary['lrrk2_gate_open'] is True
    assert summary['lrrk2_review_state'] == 'lrrk2_result_review_resolved'
    assert summary['queue_status_now'] == 'result_ready_for_terminal_review'
    assert summary['successor_target'] == 'Wave 2 completion'
    assert summary['successor_gate_open'] is True
    assert summary['successor_gate_state'] == 'wave2_terminal_review_open'
