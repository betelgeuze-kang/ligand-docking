"""Bounded fixed-receptor Cartesian execution with durable trial-level restart.

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
from .contracts import RESULT_SCHEMA, SolverConfig, source_manifest
from .journal import TrialJournal
from .kernel import CartesianMachine, make_observation, validate_observation


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
    identity = {'schema_id': 'cpu_cartesian_run_binding/1.3.0',
                'source_system_sha256': canonical_system_sha256(system),
                'evaluator': evaluator.identity(), 'config': config.to_dict(),
                'implementation_sha256': digest(source_manifest()), 'environment': environment(),
                'external_binding': binding}
    # Canonical roundtrip prevents a caller from changing a nested binding later.
    import json
    return evaluator, json.loads(canonical(identity))


def _intact(system, evaluator, identity, implementation_sources=None, model_guard=None):
    if model_guard is not None:
        model_guard()
    implementation_sources = source_manifest if implementation_sources is None else implementation_sources
    _same(canonical_system_sha256(system), identity['source_system_sha256'], 'source ligand changed')
    _same(evaluator.identity(), identity['evaluator'], 'fixed evaluator changed')
    _same(digest(implementation_sources()), identity['implementation_sha256'], 'Cartesian implementation changed')
    _same(environment(), identity['environment'], 'Cartesian runtime changed')


def _work(config, profile=None):
    work = {'optimizer_objective_attempts': 0, 'optimizer_graph_calls': 0,
            'optimizer_force_calls': 0, 'failed_optimizer_force_calls': 0,
            'restart_verification_attempts': 0, 'restart_graph_calls': 0,
            'restart_force_calls': 0, 'failed_restart_force_calls': 0,
            'unknown_pending_attempts': 0,
            'max_objective_attempts': config.max_objective_attempts,
            'max_restart_verifications': config.max_restart_verifications,
            'max_total_force_calls': config.max_total_force_calls,
            'known_completed_force_calls': 0, 'actual_force_calls': 0}
    if profile is not None:
        extra = profile.work(config)
        if type(extra) is not dict or set(extra) & set(work):
            raise ResearchError('profile work must add separate counters')
        work.update(extra)
    return work


def _timings():
    return {'optimizer_graph_ns': 0, 'optimizer_force_ns': 0, 'optimizer_objective_ns': 0,
            'restart_graph_ns': 0, 'restart_force_ns': 0, 'restart_objective_ns': 0}


def _completed_work(payload, work, timings, prefix, profile=None):
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
    if profile is not None:
        profile.completed_work(payload, work, prefix)


def _checkpoint(machine, count, head, profile=None):
    value = {'journal_count': count, 'journal_sha256': head, 'state': machine.snapshot()}
    if profile is not None:
        value['schema_id'] = profile.checkpoint_schema
    return {**value, 'checkpoint_sha256': digest(value)}


def _restart_intent(machine, verification):
    current = machine.snapshot()['current']
    return {'verification': verification, 'current_attempt': current['attempt'],
            'coordinates': current['coordinates']}


def _replay(journal, system, config, profile=None):
    machine = CartesianMachine(system.coordinates, config, profile=profile)
    work, timings = _work(config, profile), _timings()
    checkpoints = journal.checkpoint_digests
    events = journal.events
    pending, restart_failed = None, False

    def verify_checkpoint(count, head):
        if count in checkpoints:
            _same(_checkpoint(machine, count, head, profile)['checkpoint_sha256'], checkpoints[count],
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
            common = {'observation', 'failure', 'error_type', 'work', 'timings_ns', 'state_sha256'}
            if profile is not None:
                common.add('shape_work')
            if kind == 'objective_finished':
                exact_fields(payload, common | {'attempt', 'decision'})
                _same(payload['attempt'], pending[1]['attempt'], 'objective finish attempt changed')
                decision = machine.commit(pending[1], payload['observation'], failure=payload['failure'])
                _same(payload['decision'], decision, 'replayed objective decision changed')
                _completed_work(payload, work, timings, 'optimizer', profile)
            else:
                exact_fields(payload, common | {'verification', 'matched'})
                _same(payload['verification'], pending[1]['verification'], 'restart finish index changed')
                observed = payload['observation']
                if observed is not None:
                    validator = validate_observation if profile is None else profile.validate_observation
                    observed = validator(observed, state['atom_count'])
                matched = observed is not None and canonical(observed) == canonical(state['current'])
                _same(payload['matched'], matched, 'restart full energy/force comparison changed')
                restart_failed = not matched
                _completed_work(payload, work, timings, 'restart', profile)
            _same(payload['state_sha256'], digest(machine.snapshot()), 'replayed solver state digest changed')
            pending = None
        verify_checkpoint(event['index'] + 1, event['event_sha256'])
    work['unknown_pending_attempts'] = int(pending is not None)
    if pending is not None:
        work['actual_force_calls'] = None
        raise PendingWorkError(work)
    if restart_failed:
        error = ResearchError('recorded restart energy/force verification failed; continuation forbidden')
        error.work = work
        raise error
    return machine, work, timings


def _invoke(system, evaluator, config, intent):
    started = time.perf_counter_ns()
    work = {'graph_calls': 0, 'force_calls': 0, 'failed_force_calls': 0}
    timings = {'graph': 0, 'force': 0, 'objective': 0}
    observation, failure, error = None, None, None
    try:
        xyz = decode_coordinates(intent['coordinates'], system.atom_count)
        state = system.with_coordinates(xyz, operation=config.algorithm_id)
        work['graph_calls'] = 1
        tick = time.perf_counter_ns()
        try:
            neighbors = build_compact_radius_graph(xyz, RadiusGraphConfig(
                cutoff_angstrom=evaluator.parameters.base_parameters.cutoff_angstrom,
                max_neighbors=config.max_neighbors, max_atoms_per_cell=config.max_atoms_per_cell))
        finally:
            timings['graph'] = time.perf_counter_ns() - tick
        work['force_calls'] = 1
        tick = time.perf_counter_ns()
        try:
            evaluated = evaluator.evaluate(state, neighbors)
        finally:
            timings['force'] = time.perf_counter_ns() - tick
        _same(coordinates_hex(state.coordinates), intent['coordinates'], 'evaluator changed trial coordinates')
        if evaluated.constraint_observations:
            raise ResearchError('Cartesian evaluator returned unsupported constraints')
        observation = make_observation(intent['attempt'], xyz, float(evaluated.term.energy[0]),
                                       evaluated.term.forces, components_document(evaluated))
    except Exception as exc:
        failure = 'retryable' if isinstance(exc, (*APPLICABILITY_ERRORS, FloatingPointError)) else 'fatal'
        error = type(exc).__name__[:128]
        work['failed_force_calls'] = work['force_calls']
    # BaseException intentionally leaves the durable reservation unfinished.
    timings['objective'] = time.perf_counter_ns() - started
    return {'observation': observation, 'failure': failure, 'error_type': error,
            'work': work, 'timings_ns': timings}


def _result(journal, machine, work, timings, binding, result_schema=RESULT_SCHEMA, profile=None):
    state = machine.snapshot()
    value = {'schema_id': result_schema,
             'status': 'checkpointed' if state['status'] == 'running' else state['status'],
             'converged': state['status'] == 'force_converged', 'binding_sha256': digest(binding),
             'checkpoint': _checkpoint(machine, journal.event_count, journal.head_sha256, profile),
             'work': dict(work), 'timings_ns': dict(timings),
             'durations_are_nested_do_not_sum': True,
             'scientifically_validated': False, 'claim_safe': False, 'customer_execution_allowed': False}
    if profile is not None:
        fields = profile.result_fields(state, machine.config)
        if type(fields) is not dict or type(fields.get('converged')) is not bool:
            raise ResearchError('profile must explicitly qualify result convergence')
        value.update(fields)
    return {**value, 'result_sha256': digest(value)}


def verify_run(system, parameters, config, *, fixed_environment, run_dir, binding):
    """Read/replay all evidence; never evaluate graph, force or score."""
    evaluator, identity = _context(system, parameters, config, fixed_environment, binding)
    return _verify_profile(system, config, evaluator=evaluator, identity=identity,
                           run_dir=run_dir, implementation_sources=source_manifest,
                           result_schema=RESULT_SCHEMA)


def _verify_profile(system, config, *, evaluator, identity, run_dir,
                    implementation_sources, result_schema, model_guard=None, profile=None):
    """Shared replay; public profiles own strict model admission and identity."""
    with TrialJournal(Path(run_dir), identity, create=False, profile=profile) as journal:
        machine, work, timings = _replay(journal, system, config, profile)
        result = _result(journal, machine, work, timings, identity, result_schema, profile)
        saved = journal.result()
        if saved is not None:
            if result['status'] == 'checkpointed':
                raise ResearchError('running state published as a terminal result')
            _same(saved, result, 'cached Cartesian result does not reproduce')
        _intact(system, evaluator, identity, implementation_sources, model_guard)
        return result


def minimize(system, parameters, config, *, fixed_environment, run_dir, binding,
             pause_after_objective_attempts=None, resume=False):
    if type(resume) is not bool:
        raise ResearchError('explicit resume flag required')
    pause = None if pause_after_objective_attempts is None else integer(
        pause_after_objective_attempts, 1, config.max_objective_attempts)
    evaluator, identity = _context(system, parameters, config, fixed_environment, binding)
    return _minimize_profile(system, config, evaluator=evaluator, identity=identity,
                             run_dir=run_dir, pause_after_objective_attempts=pause,
                             resume=resume, implementation_sources=source_manifest,
                             result_schema=RESULT_SCHEMA)


def _minimize_profile(system, config, *, evaluator, identity, run_dir,
                      implementation_sources, result_schema,
                      pause_after_objective_attempts=None, resume=False, model_guard=None,
                      profile=None):
    """One durable execution loop shared by strictly admitted model profiles."""
    if type(resume) is not bool:
        raise ResearchError('explicit resume flag required')
    pause = None if pause_after_objective_attempts is None else integer(
        pause_after_objective_attempts, 1, config.max_objective_attempts)
    with TrialJournal(Path(run_dir), identity, create=not resume, profile=profile) as journal:
        machine, work, timings = _replay(journal, system, config, profile)
        state = machine.snapshot()
        if pause is not None and pause < state['attempts']:
            raise ResearchError('pause precedes saved objective progress')
        saved = journal.result()
        if saved is not None:
            result = _result(journal, machine, work, timings, identity, result_schema, profile)
            if result['status'] == 'checkpointed':
                raise ResearchError('running state published as a terminal result')
            _same(saved, result, 'cached Cartesian result does not reproduce')
            _intact(system, evaluator, identity, implementation_sources, model_guard)
            return result
        advancing = state['status'] == 'running' and (pause is None or state['attempts'] < pause)
        if resume and advancing and state['current'] is not None:
            if work['restart_verification_attempts'] >= config.max_restart_verifications:
                raise ResearchError('cumulative restart verification allowance exhausted')
            verification = work['restart_verification_attempts'] + 1
            intent = _restart_intent(machine, verification)
            journal.append('restart_started', intent)
            work['restart_verification_attempts'] += 1
            invoke = _invoke if profile is None else profile.invoke
            receipt = invoke(system, evaluator, config, {'attempt': state['current']['attempt'],
                                                        'coordinates': intent['coordinates']})
            matched = canonical(receipt['observation']) == canonical(state['current'])
            receipt.update(verification=verification, matched=matched, state_sha256=digest(machine.snapshot()))
            journal.append('restart_finished', receipt)
            _completed_work(receipt, work, timings, 'restart', profile)
            journal.save_checkpoint(machine.snapshot())
            if not matched:
                error = ResearchError('restart full energy/force verification failed; continuation forbidden')
                error.work = work
                raise error
        while machine.snapshot()['status'] == 'running':
            if pause is not None and machine.snapshot()['attempts'] >= pause:
                break
            intent = machine.next_intent()
            journal.append('objective_started', intent)
            work['optimizer_objective_attempts'] += 1
            invoke = _invoke if profile is None else profile.invoke
            receipt = invoke(system, evaluator, config, intent)
            decision = machine.commit(intent, receipt['observation'], failure=receipt['failure'])
            receipt.update(attempt=intent['attempt'], decision=decision, state_sha256=digest(machine.snapshot()))
            journal.append('objective_finished', receipt)
            _completed_work(receipt, work, timings, 'optimizer', profile)
            journal.save_checkpoint(machine.snapshot())
        _intact(system, evaluator, identity, implementation_sources, model_guard)
        result = _result(journal, machine, work, timings, identity, result_schema, profile)
        if result['status'] != 'checkpointed':
            journal.publish_result(result)
        return result
