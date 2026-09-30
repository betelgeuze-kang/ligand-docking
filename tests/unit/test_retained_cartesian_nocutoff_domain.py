from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[2] / 'tools/analysis/retained_cartesian_nocutoff_domain.py'
spec = importlib.util.spec_from_file_location('retained_domain', SOURCE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def xyz(distance):
    return [[float(x).hex() for x in [0., 0., 0.]], [float(x).hex() for x in [distance, 0., 0.]]]


def sequence(include_outside=False, pending=False):
    events = []
    def add(kind, payload):
        value = {'index': len(events), 'kind': kind, 'payload': payload,
                 'previous_sha256': events[-1]['event_sha256'] if events else 'a' * 64}
        events.append({**value, 'event_sha256': audit.digest(value)})
    first = {'attempt': 1, 'coordinates': xyz(1.)}
    add('objective_started', first)
    observation = {'attempt': 1, 'coordinates': xyz(1.), 'energy': '0x0.0p+0', 'forces': xyz(0.)}
    add('objective_finished', {'attempt': 1, 'observation': observation, 'failure': None, 'error_type': None,
        'work': {'graph_calls': 1, 'force_calls': 1, 'failed_force_calls': 0}, 'decision': {'outcome': 'initial'}})
    add('objective_started', {'attempt': 2, 'coordinates': xyz(2.)})
    add('objective_finished', {'attempt': 2, 'observation': {**observation, 'attempt': 2, 'coordinates': xyz(2.)},
        'failure': None, 'error_type': None, 'work': {'graph_calls': 1, 'force_calls': 1, 'failed_force_calls': 0},
        'decision': {'outcome': 'rejected_armijo'}})
    add('restart_started', {'verification': 1, 'current_attempt': 1, 'coordinates': xyz(1.)})
    add('restart_finished', {'verification': 1, 'observation': observation, 'failure': None, 'error_type': None,
        'work': {'graph_calls': 1, 'force_calls': 1, 'failed_force_calls': 0}, 'matched': True})
    if include_outside:
        add('objective_started', {'attempt': 3, 'coordinates': xyz(91.)})
        add('objective_finished', {'attempt': 3, 'observation': None, 'failure': 'retryable', 'error_type': 'DomainError',
            'work': {'graph_calls': 1, 'force_calls': 1, 'failed_force_calls': 1}, 'decision': {'outcome': 'rejected_evaluation'}})
    if pending:
        add('objective_started', {'attempt': 4 if include_outside else 3, 'coordinates': xyz(3.)})
    return events


def reseal(events):
    for index, event in enumerate(events):
        event['index'] = index
        event['previous_sha256'] = events[index - 1]['event_sha256'] if index else 'a' * 64
        event['event_sha256'] = audit.digest({k: v for k, v in event.items() if k != 'event_sha256'})


def inspect(events):
    return audit.inventory_events(events, 'a' * 64, 2)


def test_rejected_armijo_coordinates_and_restart_call_are_in_denominator():
    report = inspect(sequence())
    assert report['complete'] and report['all_reserved_coordinates_inside_domain']
    assert len(report['rows']) == 3
    assert report['counts']['optimizer_objective_attempts'] == 2
    assert report['counts']['restart_verification_attempts'] == 1
    assert report['counts']['known_completed_force_calls'] == 3
    assert report['outcomes']['rejected_armijo'] == 1


def test_outside_domain_rejected_force_attempt_prevents_full_trace_domain_claim():
    report = inspect(sequence(include_outside=True))
    assert report['complete']
    assert not report['all_reserved_coordinates_inside_domain']
    assert report['counts']['failed_optimizer_force_calls'] == 1
    assert report['counts']['known_completed_force_calls'] == 4
    assert report['rows'][-1]['domain']['maximum_pair_distance_angstrom'] == 91.


def test_pending_attempt_preserves_known_completed_floor_and_unknown_total():
    report = inspect(sequence(include_outside=True, pending=True))
    assert not report['complete']
    assert report['counts']['known_completed_force_calls'] == 4
    assert report['counts']['unknown_pending_attempts'] == 1
    assert report['counts']['actual_force_calls'] is None
    assert report['rows'][-1]['force_calls'] is None


@pytest.mark.parametrize('distance,expected', [(89.999999999, True), (90., False), (90.000000001, False)])
def test_domain_boundary_is_strict_without_tolerance_relaxation(distance, expected):
    assert audit.domain(xyz(distance), 2)['passed'] is expected


def test_failed_graph_attempt_coordinate_is_retained_with_zero_known_force_calls():
    events = sequence()
    payload = events[3]['payload']
    payload.update(observation=None, failure='fatal', error_type='GraphError',
        work={'graph_calls': 1, 'force_calls': 0, 'failed_force_calls': 0}, decision={'outcome': 'rejected_evaluation'})
    events = events[:4]
    reseal(events)
    report = inspect(events)
    assert len(report['rows']) == 2
    assert report['counts']['optimizer_objective_attempts'] == 2
    assert report['counts']['known_completed_force_calls'] == 1
    assert report['rows'][-1]['force_calls'] == 0


@pytest.mark.parametrize('mutation', ['missing_start', 'index', 'chain', 'sequence', 'different_observation', 'wrong_work', 'changed_restart'])
def test_dropped_or_resealed_inconsistent_trace_is_rejected(mutation):
    events = sequence()
    if mutation == 'missing_start':
        events.pop(2)
    elif mutation == 'index':
        events[2]['index'] = 99
    elif mutation == 'chain':
        events[2]['previous_sha256'] = 'b' * 64
    elif mutation == 'sequence':
        events[2]['payload']['attempt'] = 4
    elif mutation == 'different_observation':
        events[3]['payload']['observation']['coordinates'] = xyz(4.)
    elif mutation == 'wrong_work':
        events[3]['payload']['work']['force_calls'] = 0
    else:
        events[4]['payload']['coordinates'] = xyz(4.)
    if mutation not in {'index', 'chain'}:
        reseal(events)
    with pytest.raises(audit.TraceDomainError):
        inspect(events)


def outer(trace):
    zeros = {k: 0 for k in trace['counts'] if k != 'unknown_pending_attempts'}
    return {(0, 'start'): {'request_sha256': 'c' * 64}, (0, 'end'): {'index': 0,
        'numerical_entrypoint_invoked': True, 'new_force_calls': 3,
        'numerical_work_before': zeros, 'numerical_work_after': trace['counts'],
        'prior_unresolved_numerical_invocations': []}}


def test_outer_calls_cover_exact_full_force_inventory():
    trace = inspect(sequence())
    result = audit.invocation_inventory(outer(trace), 'c' * 64, trace['counts'])
    assert result['complete']
    assert result['known_new_force_calls_in_outer_receipts'] == 3


@pytest.mark.parametrize('mutation', ['missing_end', 'missing_start', 'unknown_calls', 'unknown_after', 'missing_force_delta'])
def test_unknown_outer_work_is_not_repaired_by_complete_inner_prefix(mutation):
    trace = inspect(sequence())
    receipts = copy.deepcopy(outer(trace))
    if mutation == 'missing_end':
        receipts.pop((0, 'end'))
    elif mutation == 'missing_start':
        receipts.pop((0, 'start'))
    elif mutation == 'unknown_calls':
        receipts[(0, 'end')]['new_force_calls'] = None
    elif mutation == 'unknown_after':
        receipts[(0, 'end')]['numerical_work_after']['actual_force_calls'] = None
    else:
        receipts[(0, 'end')]['new_force_calls'] = 2
    result = audit.invocation_inventory(receipts, 'c' * 64, trace['counts'])
    assert not result['complete']


def test_truncated_inner_prefix_cannot_hide_higher_retained_outer_work():
    trace = inspect(sequence())
    receipts = outer(trace)
    receipts[(0, 'end')]['numerical_work_after'] = {**trace['counts'], 'optimizer_force_calls': 99}
    with pytest.raises(audit.TraceDomainError, match='journal_behind_retained_outer_work'):
        audit.invocation_inventory(receipts, 'c' * 64, trace['counts'])


@pytest.mark.parametrize('token', ['nan', 'inf', '0x1p+0'])
def test_nonfinite_or_noncanonical_hex_coordinates_are_rejected(token):
    values = xyz(1.)
    values[0][0] = token
    with pytest.raises(audit.TraceDomainError):
        audit.domain(values, 2)


def recovery_fixture(tmp_path):
    system = {'coordinates': {'coordinates': {'$tensor': {'shape': [1, 2, 3], 'dtype': 'float64',
        'values': [{'$float_hex': item} for row in xyz(1.) for item in row]}}}}
    source = {'system': system, 'system_sha256': audit.digest(system)}
    ligand = tmp_path / 'ligand.json'
    raw = audit.canonical(source).encode('ascii')
    ligand.write_bytes(raw)
    (tmp_path / 'request.json').write_text(audit.canonical({'ligand': {'path': str(ligand), 'sha256': audit.hashlib.sha256(raw).hexdigest()}}))
    numerical = tmp_path / 'numerical'
    numerical.mkdir()
    binding = {'source_system_sha256': source['system_sha256']}
    head = audit.digest(binding)
    (numerical / 'meta.json').write_text(audit.canonical({'binding': binding, 'binding_sha256': head}))
    events = sequence()
    for index, event in enumerate(events):
        event['previous_sha256'] = events[index - 1]['event_sha256'] if index else head
        event['event_sha256'] = audit.digest({k: v for k, v in event.items() if k != 'event_sha256'})
    path = numerical / 'events.jsonl'
    path.write_text(''.join(audit.canonical(event) + '\n' for event in events))
    return path, events


def test_truncated_tail_preserves_valid_sealed_prefix_work_and_coordinate_rows(tmp_path):
    path, _ = recovery_fixture(tmp_path)
    with path.open('ab') as stream:
        stream.write(b'{"index":')
    report = audit.recover_prefix_for_blocked_report(tmp_path)
    assert report['work']['known_completed_force_calls'] == 3
    assert report['work']['actual_force_calls'] is None
    assert report['work']['unknown_pending_attempts'] is None
    assert report['event_count'] == 6 and len(report['coordinate_rows']) == 3
    assert report['unparsed_journal_bytes'] == 9
    assert report['unparsed_journal_reason'].startswith('invalid_JSON:')


def test_bad_sealed_finish_preserves_pending_reserved_coordinate_and_known_floor(tmp_path):
    path, events = recovery_fixture(tmp_path)
    events[3]['payload']['work']['force_calls'] = 0
    for index, event in enumerate(events):
        if index:
            event['previous_sha256'] = events[index - 1]['event_sha256']
        event['event_sha256'] = audit.digest({k: v for k, v in event.items() if k != 'event_sha256'})
    path.write_text(''.join(audit.canonical(event) + '\n' for event in events))
    report = audit.recover_prefix_for_blocked_report(tmp_path)
    assert report['work']['known_completed_force_calls'] == 1
    assert report['work']['known_pending_reserved_attempts'] == 1
    assert report['work']['actual_force_calls'] is None
    assert report['event_count'] == 3
    assert len(report['coordinate_rows']) == 2 and not report['coordinate_rows'][-1]['completed']
    assert report['unparsed_journal_reason'] == 'successful_work_denominator_invalid'
