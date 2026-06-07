#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, wetlab_run_record_state, write_artifact

DEFAULT_UPSTREAM_REVIEW_JSON = 'runs/tcruzi_krs1_result_review_current.json'
DEFAULT_LAUNCH_JSON = 'runs/lrrk2_launch_packet_current.json'
DEFAULT_RUN_RECORD_JSON = 'runs/lrrk2_run_record_current.json'
DEFAULT_OUT_MD = 'runs/lrrk2_result_review_current.md'


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get('summary', {}) or {})


def build_payload(upstream_review: dict[str, Any] | None, launch_payload: dict[str, Any], run_record: dict[str, Any] | None = None) -> dict:
    upstream_s = _summary(upstream_review)
    launch_s = _summary(launch_payload)
    run_state = wetlab_run_record_state(run_record)

    upstream_gate_state = str(upstream_s.get('successor_gate_state', '')).strip() or 'blocked_on_tcruzi_krs1_result_review'
    upstream_gate_open = bool(upstream_s.get('successor_gate_open', False))
    content_ready = str(launch_s.get('launch_readiness', '')).strip() == 'ready_for_serialized_execution'
    execution_gate_open = upstream_gate_open and content_ready

    if not upstream_gate_open:
        review_state = 'blocked_on_tcruzi_krs1_result_review'
        queue_status_now = 'blocked_on_previous_review'
        terminal_gate_state = 'blocked_on_lrrk2_result_review'
        terminal_gate_open = False
    elif not content_ready:
        review_state = 'blocked_on_target_content'
        queue_status_now = 'blocked_on_target_content'
        terminal_gate_state = 'blocked_on_lrrk2_result_review'
        terminal_gate_open = False
    elif run_state['explicit_hold']:
        review_state = 'lrrk2_result_review_resolved'
        queue_status_now = 'explicit_hold_ready_for_terminal_review'
        terminal_gate_state = 'wave2_terminal_review_open'
        terminal_gate_open = True
    elif run_state['result_review_ready']:
        review_state = 'lrrk2_result_review_resolved'
        queue_status_now = 'result_ready_for_terminal_review'
        terminal_gate_state = 'wave2_terminal_review_open'
        terminal_gate_open = True
    elif run_state['run_started']:
        review_state = 'lrrk2_result_review_in_progress'
        queue_status_now = 'running_after_previous_review'
        terminal_gate_state = 'blocked_on_lrrk2_result_review'
        terminal_gate_open = False
    else:
        review_state = 'ready_to_capture_lrrk2_result_review'
        queue_status_now = 'ready_after_previous_review'
        terminal_gate_state = 'blocked_on_lrrk2_result_review'
        terminal_gate_open = False

    rows = [
        {'review_item': 'tcruzi_krs1_release_gate', 'source_artifact': 'runs/tcruzi_krs1_result_review_current.md', 'queue_phrase': 'T. cruzi KRS1 must resolve before LRRK2 may leave blocked_on_previous_review.', 'gate_status': upstream_gate_state},
        {'review_item': 'lrrk2_content_gate', 'source_artifact': 'runs/lrrk2_launch_packet_current.md', 'queue_phrase': 'LRRK2 launch packet is fill-ready; only the T. cruzi KRS1 predecessor gate still blocks execution.' if content_ready else 'keep LRRK2 blocked until the repurposing and novelty lanes are actually filled', 'gate_status': str(launch_s.get('launch_readiness', '')).strip() or 'missing_launch_packet'},
        {'review_item': 'lrrk2_run_record', 'source_artifact': 'runs/lrrk2_run_record_current.md', 'queue_phrase': 'Live LRRK2 run records advance this review from ready to running to resolved.', 'gate_status': run_state['status']},
        {'review_item': 'wave2_terminal_gate', 'source_artifact': 'runs/wetlab_wave2_protein_run_queue_current.md', 'queue_phrase': 'Wave 2 closes only after LRRK2 resolves.', 'gate_status': terminal_gate_state},
    ]

    return {'summary': {
        'status': 'lrrk2_result_review_ready',
        'target_id': 'LRRK2',
        'serialized_queue_rank': int(launch_s.get('serialized_queue_rank', 5) or 5),
        'serialized_run_order': str(launch_s.get('serialized_run_order', '5_of_5_in_wave2')).strip() or '5_of_5_in_wave2',
        'partner_track_id': str(launch_s.get('partner_track_id', 'MJFF_LRRK2')).strip() or 'MJFF_LRRK2',
        'upstream_gate_state': upstream_gate_state,
        'upstream_gate_open': upstream_gate_open,
        'content_ready': content_ready,
        'lrrk2_gate_open': execution_gate_open,
        'lrrk2_review_state': review_state,
        'lrrk2_run_record_detected': run_state['detected'],
        'lrrk2_run_record_status': run_state['status'],
        'lrrk2_execution_state': run_state['execution_state'],
        'lrrk2_result_review_ready': run_state['result_review_ready'],
        'lrrk2_explicit_hold': run_state['explicit_hold'],
        'queue_status_now': queue_status_now,
        'successor_target': 'Wave 2 completion',
        'successor_gate_state': terminal_gate_state,
        'successor_gate_open': terminal_gate_open,
        'wave2_terminal_state': 'complete' if terminal_gate_open else 'pending',
        'launch_packet_status': str(launch_s.get('status', '')).strip(),
        'next_required_step': 'LRRK2 is resolved; Wave 2 may now move into terminal review.' if terminal_gate_open else 'LRRK2 is running; keep Wave 2 terminal review blocked until the live run record reaches result-ready or explicit hold.' if run_state['run_started'] else 'Wait for T. cruzi KRS1 to resolve before opening LRRK2.' if not upstream_gate_open else 'LRRK2 may move into ready_after_previous_review now; keep terminal Wave 2 review blocked until the live run record resolves.',
    }, 'structured': {
        'gate_policy': 'open_lrrk2_only_after_tcruzi_krs1_resolution_and_real_compound_fill',
        'downstream_policy': 'wave2_terminal_review_stays_blocked_until_lrrk2_run_record_reaches_result_ready_or_explicit_hold',
    }, 'rows': rows}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Build the LRRK2 result-review surface as the fifth Wave 2 gate.')
    parser.add_argument('--upstream-review-json', default=DEFAULT_UPSTREAM_REVIEW_JSON)
    parser.add_argument('--launch-json', default=DEFAULT_LAUNCH_JSON)
    parser.add_argument('--run-record-json', default=DEFAULT_RUN_RECORD_JSON)
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    write_artifact(DEFAULT_OUT_MD, 'LRRK2 Result Review', build_payload(maybe_load_json(args.upstream_review_json), load_json(args.launch_json), maybe_load_json(args.run_record_json)))
