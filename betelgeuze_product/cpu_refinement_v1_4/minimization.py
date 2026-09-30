"""Opt-in 1.4 failure diagnostics over the unchanged Cartesian 1.3 kernel.

Every objective is reserved before graph/force work. A start without a finish
is unknown work and cannot be retried automatically. Resume verifies the full
accepted energy and force once, using a separate cumulative allowance.
"""
from __future__ import annotations

from pathlib import Path
import time

from betelgeuze_engine_v2.geometry import RadiusGraphConfig, build_compact_radius_graph
from betelgeuze_engine_v2.molecular import canonical_system_sha256
from ..cpu_refinement_v1_2.evaluation import ExtendedEvaluator
from ..cpu_refinement_v1_2.fixed_receptor import (
    FixedReceptorEnvironment, FixedReceptorEvaluator, components_document, require_system,
)
from ..cpu_refinement_v1_2.minimization import APPLICABILITY_ERRORS
from ..cpu_refinement_v1_2.provenance import (
    ResearchError, canonical, coordinates_hex, decode_coordinates, digest, environment,
    exact_fields, integer,
)
from .contracts import BINDING_SCHEMA, RESULT_SCHEMA, SolverConfig, source_manifest
from .failure_diagnostics import capture_failure, safe_error_type, validate_failure_detail
from ..cpu_refinement_v1_3.journal import TrialJournal
from ..cpu_refinement_v1_3.kernel import CartesianMachine, make_observation, validate_observation


class PendingWorkError(ResearchError):
    """The durable reservation has no outcome; its actual computation is unknown."""

    def __init__(self, work):
        super().__init__('unfinished Cartesian objective/restart intent; automatic retry is forbidden')
        self.work = dict(work)


def _same(left, right, reason):
    if canonical(left) != canonical(right):
        raise ResearchError(reason)


def _context(system, parameters, config, fixed_environment, binding):
    require_system(system, 256)
    if type(config) is not SolverConfig or type(fixed_environment) is not FixedReceptorEnvironment:
        raise ResearchError('explicit Cartesian config and fixed receptor required')
    internal = ExtendedEvaluator(parameters)
    if parameters.constraints:
        raise ResearchError('Cartesian solver does not support distance constraints')
    fixed_environment.validate_ligand(system, parameters.base_parameters)
    evaluator = FixedReceptorEvaluator(internal, fixed_environment)
    if type(binding) is not dict:
        raise ResearchError('explicit external request binding required')
    sources = source_manifest()
    identity = {'schema_id': BINDING_SCHEMA,
                'source_system_sha256': canonical_system_sha256(system),
                'evaluator': evaluator.identity(), 'config': config.to_dict(),
                'implementation_sha256': digest(sources), 'implementation_sources': sources,
                'environment': environment(),
                'external_binding': binding}
    # Canonical roundtrip prevents a caller from changing a nested binding later.
    import json
    return evaluator, json.loads(canonical(identity))


def _intact(system, evaluator, identity):
    _same(canonical_system_sha256(system), identity['source_system_sha256'], 'source ligand changed')
    _same(evaluator.identity(), identity['evaluator'], 'fixed evaluator changed')
    _same(digest(source_manifest()), identity['implementation_sha256'], 'Cartesian implementation changed')
    _same(environment(), identity['environment'], 'Cartesian runtime changed')


def _work(config):
    return {'optimizer_objective_attempts': 0, 'optimizer_graph_calls': 0,
            'optimizer_force_calls': 0, 'failed_optimizer_force_calls': 0,
            'restart_verification_attempts': 0, 'restart_graph_calls': 0,
            'restart_force_calls': 0, 'failed_restart_force_calls': 0,
            'unknown_pending_attempts': 0,
            'max_objective_attempts': config.max_objective_attempts,
            'max_restart_verifications': config.max_restart_verifications,
            'max_total_force_calls': config.max_total_force_calls,
            'known_completed_force_calls': 0, 'actual_force_calls': 0}


def _timings():
    return {'optimizer_graph_ns': 0, 'optimizer_force_ns': 0, 'optimizer_objective_ns': 0,
            'restart_graph_ns': 0, 'restart_force_ns': 0, 'restart_objective_ns': 0}


def _completed_work(payload, work, timings, prefix):
    recorded = payload['work']
    exact_fields(recorded, {'graph_calls', 'force_calls', 'failed_force_calls'})
    graph, force, failed = [integer(recorded[key], 0, 1)
                            for key in ('graph_calls', 'force_calls', 'failed_force_calls')]
    if failed > force or force > graph:
        raise ResearchError('graph/force attempt denominator is inconsistent')
    observation, failure, error = payload['observation'], payload['failure'], payload['error_type']
    if observation is not None:
        if failure is not None or error is not None or (graph, force, failed) != (1, 1, 0):
            raise ResearchError('successful observation work denominator is inconsistent')
    elif (failure not in {'fatal', 'retryable'} or type(error) is not str or not 1 <= len(error) <= 128
          or failed != force):
        raise ResearchError('failed objective work denominator is inconsistent')
    recorded_times = payload['timings_ns']
    exact_fields(recorded_times, {'graph', 'force', 'objective'})
    for key, value in recorded_times.items():
        integer(value, 0, 10 ** 20)
        timings[prefix + '_' + key + '_ns'] += value
    if (recorded_times['graph'] + recorded_times['force'] > recorded_times['objective']
            or (not graph and recorded_times['graph']) or (not force and recorded_times['force'])):
        raise ResearchError('nested objective durations are inconsistent')
    work[prefix + '_graph_calls'] += graph
    work[prefix + '_force_calls'] += force
    work['failed_' + prefix + '_force_calls'] += failed
    work['actual_force_calls'] += force
    work['known_completed_force_calls'] += force


def _validate_diagnostics(payload, intent, phase, source_pins):
    returned = exact_fields(payload['dispatch_outcome'], {'graph_returned', 'force_returned'})
    if any(type(value) is not bool for value in returned.values()):
        raise ResearchError('exact Boolean dispatch return facts required')
    graph, force = payload['work']['graph_calls'], payload['work']['force_calls']
    if ((returned['graph_returned'] and not graph) or (returned['force_returned'] and not force)
            or (force and not returned['graph_returned'])):
        raise ResearchError('dispatch returns disagree with graph/force attempts')
    detail = payload['failure_detail']
    if payload['observation'] is not None:
        if detail is not None or not all(returned.values()):
            raise ResearchError('successful observation has contradictory failure details')
        return
    attempt = intent['current_attempt'] if phase == 'resume' else intent['attempt']
    verification = intent['verification'] if phase == 'resume' else None
    detail = validate_failure_detail(detail, phase=phase, attempt=attempt, verification=verification,
                                     failure=payload['failure'], error_type=payload['error_type'],
                                     source_pins=source_pins)
    stages = {
        'coordinate_decode': (0, 0, False, False),
        'state_construction': (0, 0, False, False),
        'neighbor_graph': (1, 0, False, False),
        'force_evaluation': (1, 1, True, False),
        'post_evaluation_integrity': (1, 1, True, True),
        'observation_validation': (1, 1, True, True),
    }
    if (graph, force, returned['graph_returned'], returned['force_returned']) != stages[detail['stage']]:
        raise ResearchError('diagnostic stage disagrees with completed dispatch facts')


def _diagnostics(journal):
    """Derived counts; a finish means accounted work, not a normal force return."""
    counts = {'objective_attempts': 0, 'finished_objectives': 0, 'successful_objectives': 0,
              'failed_objectives': 0, 'unknown_pending_attempts': 0,
              'valid_observations': 0,
              'known_graph_attempts': 0, 'normal_graph_returns': 0,
              'known_force_attempts': 0, 'normal_force_returns': 0,
              'force_dispatch_errors': 0, 'restart_mismatches': 0}
    details, pending = [], None
    for event in journal.events:
        payload = event['payload']
        if event['kind'].endswith('_started'):
            counts['objective_attempts'] += 1
            pending = {'kind': event['kind'], 'intent_sha256': digest(payload),
                       'attempt': payload.get('attempt', payload.get('current_attempt')),
                       'restart_verification': payload.get('verification'),
                       'event_index': event['index'], 'event_sha256': event['event_sha256']}
            continue
        counts['finished_objectives'] += 1
        valid = payload['observation'] is not None
        succeeded = valid and (event['kind'] != 'restart_finished' or payload['matched'])
        counts['valid_observations'] += int(valid)
        counts['successful_objectives' if succeeded else 'failed_objectives'] += 1
        counts['known_graph_attempts'] += payload['work']['graph_calls']
        counts['known_force_attempts'] += payload['work']['force_calls']
        counts['normal_graph_returns'] += int(payload['dispatch_outcome']['graph_returned'])
        counts['normal_force_returns'] += int(payload['dispatch_outcome']['force_returned'])
        counts['force_dispatch_errors'] += int(payload['work']['force_calls']
                                               and not payload['dispatch_outcome']['force_returned'])
        counts['restart_mismatches'] += int(event['kind'] == 'restart_finished' and not payload['matched'])
        if payload['failure_detail'] is not None:
            details.append({'event_index': event['index'], 'event_sha256': event['event_sha256'],
                            'detail': payload['failure_detail']})
        elif event['kind'] == 'restart_finished' and not payload['matched']:
            details.append({'event_index': event['index'], 'event_sha256': event['event_sha256'],
                            'verification_failure': {'phase': 'resume', 'stage': 'restart_comparison',
                                'reason_code': 'restart_full_observation_mismatch',
                                'attempt': payload['observation']['attempt'],
                                'restart_verification': payload['verification'],
                                'evaluator_returned': payload['dispatch_outcome']['force_returned'],
                                'message': None}})
        pending = None
    counts['unknown_pending_attempts'] = int(pending is not None)
    counts['actual_force_attempts'] = None if pending is not None else counts['known_force_attempts']
    return {'schema_id': 'cpu_cartesian_failure_summary/1.4.0', 'dispatch_counts': counts,
            'failures': details, 'pending': pending,
            'message_hashes_do_not_recover_messages': True,
            'scientifically_validated': False, 'claim_safe': False}


def _checkpoint(machine, count, head):
    value = {'journal_count': count, 'journal_sha256': head, 'state': machine.snapshot()}
    return {**value, 'checkpoint_sha256': digest(value)}


def _restart_intent(machine, verification):
    current = machine.snapshot()['current']
    return {'verification': verification, 'current_attempt': current['attempt'],
            'coordinates': current['coordinates']}


def _replay(journal, system, config, source_pins):
    machine = CartesianMachine(system.coordinates, config)
    work, timings = _work(config), _timings()
    checkpoints = journal.checkpoint_digests
    events = journal.events
    pending, restart_failed = None, False

    def verify_checkpoint(count, head):
        if count in checkpoints:
            _same(_checkpoint(machine, count, head)['checkpoint_sha256'], checkpoints[count],
                  'checkpoint differs from replayed coordinate/force/history transitions')

    verify_checkpoint(0, events[0]['previous_sha256'] if events else journal.head_sha256)
    for event in events:
        kind, payload = event['kind'], event['payload']
        state = machine.snapshot()
        if kind.endswith('_started'):
            if pending is not None or restart_failed or state['status'] != 'running':
                raise ResearchError('work started after pending, failed or terminal execution')
            if kind == 'objective_started':
                _same(payload, machine.next_intent(), 'replayed objective intent changed')
                work['optimizer_objective_attempts'] += 1
            else:
                if state['current'] is None or work['restart_verification_attempts'] >= config.max_restart_verifications:
                    raise ResearchError('restart verification has no state or exhausted its allowance')
                work['restart_verification_attempts'] += 1
                _same(payload, _restart_intent(machine, work['restart_verification_attempts']),
                      'replayed restart intent changed')
            pending = (kind, payload)
        else:
            if pending is None or kind != pending[0].replace('_started', '_finished'):
                raise ResearchError('finished objective/restart has no matching intent')
            common = {'observation', 'failure', 'error_type', 'work', 'timings_ns', 'state_sha256',
                      'failure_detail', 'dispatch_outcome'}
            phase = ('resume' if kind == 'restart_finished' else
                     'initial' if pending[1]['trial'] == 0 and pending[1]['iteration'] == 0 else 'trial')
            _validate_diagnostics(payload, pending[1], phase, source_pins)
            if kind == 'objective_finished':
                exact_fields(payload, common | {'attempt', 'decision'})
                _same(payload['attempt'], pending[1]['attempt'], 'objective finish attempt changed')
                decision = machine.commit(pending[1], payload['observation'], failure=payload['failure'])
                _same(payload['decision'], decision, 'replayed objective decision changed')
                _completed_work(payload, work, timings, 'optimizer')
            else:
                exact_fields(payload, common | {'verification', 'matched'})
                _same(payload['verification'], pending[1]['verification'], 'restart finish index changed')
                observed = payload['observation']
                if observed is not None:
                    observed = validate_observation(observed, state['atom_count'])
                matched = observed is not None and canonical(observed) == canonical(state['current'])
                _same(payload['matched'], matched, 'restart full energy/force comparison changed')
                restart_failed = not matched
                _completed_work(payload, work, timings, 'restart')
            _same(payload['state_sha256'], digest(machine.snapshot()), 'replayed solver state digest changed')
            pending = None
        verify_checkpoint(event['index'] + 1, event['event_sha256'])
    work['unknown_pending_attempts'] = int(pending is not None)
    if pending is not None:
        work['actual_force_calls'] = None
        error = PendingWorkError(work)
        error.failure_diagnostics = _diagnostics(journal)
        raise error
    if restart_failed:
        error = ResearchError('recorded restart energy/force verification failed; continuation forbidden')
        error.work = work
        error.failure_diagnostics = _diagnostics(journal)
        raise error
    return machine, work, timings


def _invoke(system, evaluator, config, intent, *, phase, source_pins, verification=None):
    started = time.perf_counter_ns()
    work = {'graph_calls': 0, 'force_calls': 0, 'failed_force_calls': 0}
    timings = {'graph': 0, 'force': 0, 'objective': 0}
    observation, failure, error, detail = None, None, None, None
    returned = {'graph_returned': False, 'force_returned': False}
    stage = 'coordinate_decode'
    try:
        xyz = decode_coordinates(intent['coordinates'], system.atom_count)
        stage = 'state_construction'
        state = system.with_coordinates(xyz, operation=config.algorithm_id)
        stage = 'neighbor_graph'
        work['graph_calls'] = 1
        tick = time.perf_counter_ns()
        try:
            neighbors = build_compact_radius_graph(xyz, RadiusGraphConfig(
                cutoff_angstrom=evaluator.parameters.base_parameters.cutoff_angstrom,
                max_neighbors=config.max_neighbors, max_atoms_per_cell=config.max_atoms_per_cell))
            returned['graph_returned'] = True
        finally:
            timings['graph'] = time.perf_counter_ns() - tick
        stage = 'force_evaluation'
        work['force_calls'] = 1
        tick = time.perf_counter_ns()
        try:
            evaluated = evaluator.evaluate(state, neighbors)
            returned['force_returned'] = True
        finally:
            timings['force'] = time.perf_counter_ns() - tick
        stage = 'post_evaluation_integrity'
        _same(coordinates_hex(state.coordinates), intent['coordinates'], 'evaluator changed trial coordinates')
        if evaluated.constraint_observations:
            raise ResearchError('Cartesian evaluator returned unsupported constraints')
        stage = 'observation_validation'
        observation = make_observation(intent['attempt'], xyz, float(evaluated.term.energy[0]),
                                       evaluated.term.forces, components_document(evaluated))
    except Exception as exc:
        failure = 'retryable' if isinstance(exc, (*APPLICABILITY_ERRORS, FloatingPointError)) else 'fatal'
        error = safe_error_type(exc)
        detail = capture_failure(exc, phase=phase, stage=stage, attempt=intent['attempt'],
                                 verification=verification, failure=failure, source_pins=source_pins)
        work['failed_force_calls'] = work['force_calls']
    # BaseException intentionally leaves the durable reservation unfinished.
    timings['objective'] = time.perf_counter_ns() - started
    return {'observation': observation, 'failure': failure, 'error_type': error,
            'work': work, 'timings_ns': timings, 'failure_detail': detail, 'dispatch_outcome': returned}


def _result(journal, machine, work, timings, binding):
    state = machine.snapshot()
    value = {'schema_id': RESULT_SCHEMA,
             'status': 'checkpointed' if state['status'] == 'running' else state['status'],
             'converged': state['status'] == 'force_converged', 'binding_sha256': digest(binding),
             'checkpoint': _checkpoint(machine, journal.event_count, journal.head_sha256),
             'work': dict(work), 'timings_ns': dict(timings),
             'failure_diagnostics': _diagnostics(journal),
             'durations_are_nested_do_not_sum': True,
             'scientifically_validated': False, 'claim_safe': False, 'customer_execution_allowed': False}
    return {**value, 'result_sha256': digest(value)}


def verify_run(system, parameters, config, *, fixed_environment, run_dir, binding):
    """Read/replay all evidence; never evaluate graph, force or score."""
    evaluator, identity = _context(system, parameters, config, fixed_environment, binding)
    with TrialJournal(Path(run_dir), identity, create=False) as journal:
        try:
            machine, work, timings = _replay(journal, system, config, identity['implementation_sources'])
        except ResearchError:
            _intact(system, evaluator, identity)
            raise
        result = _result(journal, machine, work, timings, identity)
        saved = journal.result()
        if saved is not None:
            if result['status'] == 'checkpointed':
                raise ResearchError('running state published as a terminal result')
            _same(saved, result, 'cached Cartesian result does not reproduce')
        _intact(system, evaluator, identity)
        return result


def inspect_run(system, parameters, config, *, fixed_environment, run_dir, binding):
    """Read-only consumer, including failed restarts and unfinished reservations.

    It does not suppress malformed/binding-drift errors or authorize continuation.
    This diagnostic envelope is separate from the numerical result authority.
    """
    try:
        result = verify_run(system, parameters, config, fixed_environment=fixed_environment,
                            run_dir=run_dir, binding=binding)
        value = {'schema_id': 'cpu_cartesian_diagnostic_inspection/1.4.0',
                 'status': result['status'], 'numerical_result': result,
                 'work': result['work'], 'failure_diagnostics': result['failure_diagnostics']}
    except ResearchError as exc:
        if not hasattr(exc, 'failure_diagnostics') or not hasattr(exc, 'work'):
            raise
        value = {'schema_id': 'cpu_cartesian_diagnostic_inspection/1.4.0',
                 'status': 'unknown_pending' if isinstance(exc, PendingWorkError) else 'restart_verification_failed',
                 'numerical_result': None, 'work': dict(exc.work),
                 'failure_diagnostics': exc.failure_diagnostics}
    value.update(scientifically_validated=False, claim_safe=False, continuation_authorized=False)
    return {**value, 'inspection_sha256': digest(value)}


def minimize(system, parameters, config, *, fixed_environment, run_dir, binding,
             pause_after_objective_attempts=None, resume=False):
    if type(resume) is not bool:
        raise ResearchError('explicit resume flag required')
    pause = None if pause_after_objective_attempts is None else integer(
        pause_after_objective_attempts, 1, config.max_objective_attempts)
    evaluator, identity = _context(system, parameters, config, fixed_environment, binding)
    with TrialJournal(Path(run_dir), identity, create=not resume) as journal:
        machine, work, timings = _replay(journal, system, config, identity['implementation_sources'])
        state = machine.snapshot()
        if pause is not None and pause < state['attempts']:
            raise ResearchError('pause precedes saved objective progress')
        saved = journal.result()
        if saved is not None:
            result = _result(journal, machine, work, timings, identity)
            if result['status'] == 'checkpointed':
                raise ResearchError('running state published as a terminal result')
            _same(saved, result, 'cached Cartesian result does not reproduce')
            _intact(system, evaluator, identity)
            return result
        advancing = state['status'] == 'running' and (pause is None or state['attempts'] < pause)
        if resume and advancing and state['current'] is not None:
            if work['restart_verification_attempts'] >= config.max_restart_verifications:
                raise ResearchError('cumulative restart verification allowance exhausted')
            verification = work['restart_verification_attempts'] + 1
            intent = _restart_intent(machine, verification)
            journal.append('restart_started', intent)
            work['restart_verification_attempts'] += 1
            receipt = _invoke(system, evaluator, config, {'attempt': state['current']['attempt'],
                                                         'coordinates': intent['coordinates']}, phase='resume',
                              source_pins=identity['implementation_sources'], verification=verification)
            _validate_diagnostics(receipt, intent, 'resume', identity['implementation_sources'])
            matched = canonical(receipt['observation']) == canonical(state['current'])
            receipt.update(verification=verification, matched=matched, state_sha256=digest(machine.snapshot()))
            journal.append('restart_finished', receipt)
            _completed_work(receipt, work, timings, 'restart')
            journal.save_checkpoint(machine.snapshot())
            if not matched:
                error = ResearchError('restart full energy/force verification failed; continuation forbidden')
                error.work = work
                error.failure_diagnostics = _diagnostics(journal)
                raise error
        while machine.snapshot()['status'] == 'running':
            if pause is not None and machine.snapshot()['attempts'] >= pause:
                break
            intent = machine.next_intent()
            journal.append('objective_started', intent)
            work['optimizer_objective_attempts'] += 1
            phase = 'initial' if intent['trial'] == 0 and intent['iteration'] == 0 else 'trial'
            receipt = _invoke(system, evaluator, config, intent, phase=phase,
                              source_pins=identity['implementation_sources'])
            _validate_diagnostics(receipt, intent, phase, identity['implementation_sources'])
            decision = machine.commit(intent, receipt['observation'], failure=receipt['failure'])
            receipt.update(attempt=intent['attempt'], decision=decision, state_sha256=digest(machine.snapshot()))
            journal.append('objective_finished', receipt)
            _completed_work(receipt, work, timings, 'optimizer')
            journal.save_checkpoint(machine.snapshot())
        _intact(system, evaluator, identity)
        result = _result(journal, machine, work, timings, identity)
        if result['status'] != 'checkpointed':
            journal.publish_result(result)
        return result
