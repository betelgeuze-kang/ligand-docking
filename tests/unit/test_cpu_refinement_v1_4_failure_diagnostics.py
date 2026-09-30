"""Mock-only diagnostic runner/replay tests; no molecular or force implementation."""
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
import hashlib
import json
from types import SimpleNamespace

import pytest
import torch

from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError, coordinates_hex, digest, canonical
from betelgeuze_product.cpu_refinement_v1_3 import minimization as legacy
from betelgeuze_product.cpu_refinement_v1_3.contracts import SolverConfig
from betelgeuze_product.cpu_refinement_v1_4 import minimization as detailed
from betelgeuze_product.cpu_refinement_v1_4 import failure_diagnostics as diagnostics
from betelgeuze_product.cpu_refinement_v1_4.contracts import source_manifest
from betelgeuze_product.cpu_refinement_v1_4 import workflow
from betelgeuze_product.cpu_refinement_v1_4 import __main__ as cli


@dataclass
class SyntheticSystem:
    coordinates: object
    atom_count: int = 1
    model_count: int = 1
    cell: object = None

    def with_coordinates(self, xyz, *, operation):
        return SyntheticSystem(xyz.clone())


class SyntheticEnvironment:
    def __init__(self, receptor=None, cross=None):
        self.cross = cross or SimpleNamespace(max_internal_increase_kcal_per_mol=5.)

    def validate_ligand(self, system, parameters):
        pass


@pytest.fixture
def harness(monkeypatch):
    scenario = {'calls': 0, 'fault': None, 'vary_vectors': False}
    parameters = SimpleNamespace(constraints=(), base_parameters=SimpleNamespace(cutoff_angstrom=8.))
    system = SyntheticSystem(torch.zeros((1, 1, 3), dtype=torch.float64))
    fixed = SyntheticEnvironment()

    class SyntheticEvaluator:
        def __init__(self, internal, environment):
            self.parameters = internal.parameters

        def identity(self):
            return {'fixture': 'constant-vector mock; no force implementation'}

        def evaluate(self, state, neighbors):
            scenario['calls'] += 1
            if scenario['fault'] is not None:
                replacement = scenario['fault'](scenario['calls'], state)
                if replacement is not None:
                    return replacement
            # Predetermined toy observation, not a molecular force evaluation.
            value = -float(state.coordinates[0, 0, 0])
            amplitude = (1. if value == 0. else .5 if value >= -.001 else .25) if scenario['vary_vectors'] else 1.
            return SimpleNamespace(constraint_observations=(), term=SimpleNamespace(
                energy=torch.tensor([value], dtype=torch.float64),
                forces=torch.tensor([[[amplitude, 0., 0.]]], dtype=torch.float64)))

    for module in (legacy, detailed):
        monkeypatch.setattr(module, 'require_system', lambda *args: None)
        monkeypatch.setattr(module, 'ExtendedEvaluator', lambda p: SimpleNamespace(parameters=p))
        monkeypatch.setattr(module, 'FixedReceptorEnvironment', SyntheticEnvironment)
        monkeypatch.setattr(module, 'FixedReceptorEvaluator', SyntheticEvaluator)
        monkeypatch.setattr(module, 'build_compact_radius_graph', lambda *args: 'synthetic graph token')
        monkeypatch.setattr(module, 'canonical_system_sha256', lambda s: digest(coordinates_hex(s.coordinates)))
        monkeypatch.setattr(module, 'environment', lambda: {'fixture': 'mock-only'})
        monkeypatch.setattr(module, 'components_document', lambda e: {
            'total': float(e.term.energy[0]), 'ligand_internal': float(e.term.energy[0]),
            'cross_lennard_jones': 0., 'cross_screened_coulomb': 0.})
    config = SolverConfig(algorithm='sd', max_objective_attempts=3, max_accepted_steps=2,
                          max_restart_verifications=2, force_tolerance=1.e-12)
    binding = {'synthetic_fixture': 'no molecule, oracle, score or real force implementation'}
    holder = SimpleNamespace(system=system, parameters=parameters, fixed=fixed, config=config,
                             binding=binding, scenario=scenario)

    def run(module, path, **options):
        return module.minimize(holder.system, holder.parameters, holder.config, fixed_environment=holder.fixed,
                               run_dir=path, binding=holder.binding, **options)

    def inspect(path):
        return detailed.inspect_run(holder.system, holder.parameters, holder.config, fixed_environment=holder.fixed,
                                    run_dir=path, binding=holder.binding)

    holder.run, holder.inspect = run, inspect
    return holder


def events(path):
    return [json.loads(line) for line in (path / 'events.jsonl').read_bytes().splitlines()]


def files(path):
    return {p.relative_to(path).as_posix(): p.read_bytes() for p in path.rglob('*') if p.is_file()}


def forbidden(*args, **kwargs):
    pytest.fail('read-only diagnostic consumer invoked the numerical double')


@pytest.mark.parametrize('algorithm', ['sd', 'lbfgs'])
def test_opt_in_source_closure_and_normal_state_work_match_legacy(harness, tmp_path, monkeypatch, algorithm):
    harness.config = replace(harness.config, algorithm=algorithm)
    harness.scenario['vary_vectors'] = True
    before = source_manifest()
    old = harness.run(legacy, tmp_path / 'legacy')
    harness.scenario['calls'] = 0
    new = harness.run(detailed, tmp_path / 'detailed')
    assert new['schema_id'].endswith('/1.4.0')
    assert new['checkpoint']['state'] == old['checkpoint']['state']
    if algorithm == 'lbfgs':
        assert len(new['checkpoint']['state']['history']) == 2
    assert new['work'] == old['work']
    assert new['converged'] == old['converged'] and new['status'] == old['status']
    assert new['failure_diagnostics']['failures'] == []
    counts = new['failure_diagnostics']['dispatch_counts']
    assert counts['normal_force_returns'] == counts['known_force_attempts'] == 3
    assert counts['failed_objectives'] == counts['unknown_pending_attempts'] == 0
    assert all(new[key] is False for key in ('scientifically_validated', 'claim_safe', 'customer_execution_allowed'))
    closure = {name for name in before if name.startswith('betelgeuze_product/cpu_refinement_v1_4/')}
    assert closure == {'betelgeuze_product/cpu_refinement_v1_4/' + name for name in (
        '__init__.py', '__main__.py', 'contracts.py', 'failure_diagnostics.py', 'minimization.py', 'workflow.py')}
    assert before == source_manifest()
    stored = files(tmp_path / 'detailed')
    monkeypatch.setattr(detailed, 'build_compact_radius_graph', forbidden)
    monkeypatch.setattr(detailed.FixedReceptorEvaluator, 'evaluate', forbidden)
    assert harness.inspect(tmp_path / 'detailed')['numerical_result'] == new
    assert harness.run(detailed, tmp_path / 'detailed', resume=True) == new
    assert files(tmp_path / 'detailed') == stored and before == source_manifest()


@pytest.mark.parametrize('phase', ['initial', 'trial', 'resume'])
@pytest.mark.parametrize('kind', ['applicability', 'nonfinite', 'unexpected'])
def test_failure_reasons_phases_cause_hash_and_denominators(harness, tmp_path, phase, kind):
    target_call = 1 if phase == 'initial' else 2
    error_class = {'applicability': legacy.APPLICABILITY_ERRORS[0],
                   'nonfinite': FloatingPointError, 'unexpected': RuntimeError}[kind]
    private_message = 'private /arbitrary/location token=do-not-publish 원문\n'
    cause_message = 'private cause secret=also-not-public'

    def fail(call, state):
        if call == target_call:
            raise error_class(private_message) from ValueError(cause_message)

    harness.scenario['fault'] = fail
    path = tmp_path / 'detailed'
    if phase == 'resume':
        harness.run(detailed, path, pause_after_objective_attempts=1)
        with pytest.raises(ResearchError, match='restart full energy/force') as caught:
            harness.run(detailed, path, resume=True)
        assert caught.value.work['restart_force_calls'] == 1
        report = harness.inspect(path)
        assert report['status'] == 'restart_verification_failed'
    else:
        result = harness.run(detailed, path)
        report = harness.inspect(path)
        assert report['numerical_result'] == result
        if phase == 'initial' or kind == 'unexpected':
            assert result['status'] == 'evaluation_failed'
    summary = report['failure_diagnostics']
    detail = summary['failures'][0]['detail']
    assert detail['phase'] == phase and detail['stage'] == 'force_evaluation'
    assert detail['reason_code'] == {'applicability': 'applicability_rejected',
                                   'nonfinite': 'nonfinite_failure', 'unexpected': 'unexpected_exception'}[kind]
    assert detail['failure'] == ('fatal' if kind == 'unexpected' else 'retryable')
    assert detail['message']['sha256'] == hashlib.sha256(private_message.encode('utf-8')).hexdigest()
    assert detail['message']['bytes'] == len(private_message.encode('utf-8'))
    assert detail['cause_chain'][0]['message']['sha256'] == hashlib.sha256(cause_message.encode('utf-8')).hexdigest()
    position = detail['source_position']
    assert position['path'] == 'betelgeuze_product/cpu_refinement_v1_4/minimization.py'
    assert position['source_sha256'] == source_manifest()[position['path']]
    counts = summary['dispatch_counts']
    assert counts['failed_objectives'] == counts['force_dispatch_errors'] == 1
    assert counts['normal_force_returns'] == counts['known_force_attempts'] - 1
    assert counts['unknown_pending_attempts'] == 0
    assert counts['actual_force_attempts'] == report['work']['actual_force_calls']
    serialized = b''.join(files(path).values()).decode('ascii')
    assert 'do-not-publish' not in serialized and '/arbitrary/location' not in serialized
    assert 'also-not-public' not in serialized


def test_retryable_trial_preserves_legacy_history_and_work(harness, tmp_path):
    def fault(call, state):
        if call == 2:
            raise legacy.APPLICABILITY_ERRORS[0]('nonbonded pair is below minimum_pair_distance_angstrom')
    harness.scenario['fault'] = fault
    old = harness.run(legacy, tmp_path / 'old')
    harness.scenario['calls'] = 0
    new = harness.run(detailed, tmp_path / 'new')
    assert new['checkpoint']['state'] == old['checkpoint']['state']
    assert new['work'] == old['work']
    assert new['failure_diagnostics']['failures'][0]['detail']['reason_code'] == 'pair_below_minimum_distance'


@pytest.mark.parametrize('algorithm', ['sd', 'lbfgs'])
def test_normal_resume_preserves_accepted_history_and_restart_work(harness, tmp_path, algorithm):
    harness.config = replace(harness.config, algorithm=algorithm)
    harness.scenario['vary_vectors'] = True
    results = []
    for module, name in ((legacy, 'old'), (detailed, 'new')):
        harness.scenario['calls'] = 0
        path = tmp_path / name
        harness.run(module, path, pause_after_objective_attempts=1)
        results.append(harness.run(module, path, resume=True))
    assert results[0]['checkpoint']['state'] == results[1]['checkpoint']['state']
    assert results[0]['work'] == results[1]['work']
    assert results[1]['work']['restart_force_calls'] == 1
    assert harness.inspect(tmp_path / 'new')['numerical_result'] == results[1]


def test_restart_normal_return_mismatch_is_verification_failure(harness, tmp_path):
    path = tmp_path / 'run'
    harness.run(detailed, path, pause_after_objective_attempts=1)
    def changed(call, state):
        return SimpleNamespace(constraint_observations=(), term=SimpleNamespace(
            energy=torch.tensor([0.], dtype=torch.float64),
            forces=torch.tensor([[[-1., 0., 0.]]], dtype=torch.float64)))
    harness.scenario['fault'] = changed
    with pytest.raises(ResearchError):
        harness.run(detailed, path, resume=True)
    report = harness.inspect(path)
    counts = report['failure_diagnostics']['dispatch_counts']
    assert report['status'] == 'restart_verification_failed'
    assert counts['normal_force_returns'] == counts['valid_observations'] == 2
    assert counts['failed_objectives'] == counts['restart_mismatches'] == 1
    assert counts['force_dispatch_errors'] == report['work']['failed_restart_force_calls'] == 0
    reason = report['failure_diagnostics']['failures'][0]['verification_failure']
    assert reason['reason_code'] == 'restart_full_observation_mismatch' and reason['message'] is None


@pytest.mark.parametrize('phase', ['initial', 'trial', 'resume'])
def test_graph_failure_is_not_a_force_dispatch(harness, tmp_path, monkeypatch, phase):
    path = tmp_path / 'run'
    if phase == 'resume':
        harness.run(detailed, path, pause_after_objective_attempts=1)
    graph_calls = []
    def fail_graph(*args):
        graph_calls.append(1)
        if phase != 'trial' or len(graph_calls) == 2:
            raise RuntimeError('private graph failure')
        return 'synthetic graph token'
    monkeypatch.setattr(detailed, 'build_compact_radius_graph', fail_graph)
    if phase == 'resume':
        with pytest.raises(ResearchError):
            harness.run(detailed, path, resume=True)
    else:
        harness.run(detailed, path)
    report = harness.inspect(path)
    detail = report['failure_diagnostics']['failures'][0]['detail']
    assert detail['stage'] == 'neighbor_graph' and detail['phase'] == phase
    payload = events(path)[-1]['payload']
    assert payload['work'] == {'graph_calls': 1, 'force_calls': 0, 'failed_force_calls': 0}
    assert payload['dispatch_outcome'] == {'graph_returned': False, 'force_returned': False}


def test_nonfinite_after_normal_return_is_a_failed_objective_not_dispatch_error(harness, tmp_path):
    def invalid(call, state):
        return SimpleNamespace(constraint_observations=(), term=SimpleNamespace(
            energy=torch.tensor([float('nan')]), forces=torch.zeros((1, 1, 3), dtype=torch.float64)))
    harness.scenario['fault'] = invalid
    new = harness.run(detailed, tmp_path / 'run')
    detail = new['failure_diagnostics']['failures'][0]['detail']
    assert detail['reason_code'] == 'nonfinite_failure' and detail['stage'] == 'observation_validation'
    counts = new['failure_diagnostics']['dispatch_counts']
    assert counts['normal_force_returns'] == counts['known_force_attempts'] == 1
    assert counts['failed_objectives'] == 1 and counts['force_dispatch_errors'] == 0
    assert new['work']['failed_optimizer_force_calls'] == 1


@pytest.mark.parametrize('secondary', [RuntimeError, KeyboardInterrupt, SystemExit])
def test_exception_str_failure_does_not_change_primary_failure_work(harness, tmp_path, secondary):
    class BadString(RuntimeError):
        def __str__(self):
            raise secondary('private secondary failure')
    def fail(*args):
        raise BadString()
    harness.scenario['fault'] = fail
    result = harness.run(detailed, tmp_path / 'run')
    detail = result['failure_diagnostics']['failures'][0]['detail']
    assert result['status'] == 'evaluation_failed' and result['work']['failed_optimizer_force_calls'] == 1
    assert detail['message'] == {'status': 'string_conversion_unavailable', 'capture_error_code': 'exception_str_failed',
                                 'encoding': 'utf-8/strict', 'sha256': None, 'bytes': None}
    assert harness.inspect(tmp_path / 'run')['numerical_result'] == result


def test_unpaired_surrogate_and_secondary_capture_failure_stay_explicit_unknown(harness, tmp_path, monkeypatch):
    def fail(*args):
        raise RuntimeError('private\ud800message')
    harness.scenario['fault'] = fail
    result = harness.run(detailed, tmp_path / 'surrogate')
    message = result['failure_diagnostics']['failures'][0]['detail']['message']
    assert message['status'] == 'utf8_unavailable' and message['sha256'] is None and message['bytes'] is None
    def broken_capture(*args, **kwargs):
        raise MemoryError('private capture failure')
    monkeypatch.setattr(diagnostics, '_capture_failure', broken_capture)
    result = harness.run(detailed, tmp_path / 'capture')
    detail = result['failure_diagnostics']['failures'][0]['detail']
    assert result['work']['failed_optimizer_force_calls'] == 1
    assert detail['message']['status'] == 'diagnostic_capture_unavailable'
    assert detail['type_identity_sha256'] is None
    assert harness.inspect(tmp_path / 'capture')['numerical_result'] == result


@pytest.mark.parametrize('phase', ['initial', 'trial', 'resume'])
def test_base_exception_stays_unknown_and_forbids_retry(harness, tmp_path, phase, monkeypatch):
    path = tmp_path / 'run'
    if phase == 'resume':
        harness.run(detailed, path, pause_after_objective_attempts=1)
    target = 1 if phase == 'initial' else 2
    def interrupt(call, state):
        if call == target:
            raise KeyboardInterrupt('private interruption')
    harness.scenario['fault'] = interrupt
    with pytest.raises(KeyboardInterrupt):
        harness.run(detailed, path, resume=phase == 'resume')
    original = files(path)
    monkeypatch.setattr(detailed.FixedReceptorEvaluator, 'evaluate', forbidden)
    report = harness.inspect(path)
    assert report['status'] == 'unknown_pending' and report['work']['actual_force_calls'] is None
    counts = report['failure_diagnostics']['dispatch_counts']
    assert counts['unknown_pending_attempts'] == 1 and counts['actual_force_attempts'] is None
    assert counts['objective_attempts'] == counts['finished_objectives'] + 1
    assert report['failure_diagnostics']['failures'] == []
    assert 'intent_sha256' in report['failure_diagnostics']['pending']
    assert 'coordinates' not in canonical(report['failure_diagnostics']['pending'])
    with pytest.raises(detailed.PendingWorkError):
        harness.run(detailed, path, resume=True)
    assert files(path) == original


@pytest.mark.parametrize('mutation', ['binding', 'coordinates'])
def test_input_binding_and_legacy_journal_cannot_be_reinterpreted(harness, tmp_path, monkeypatch, mutation):
    harness.run(detailed, tmp_path / 'new', pause_after_objective_attempts=1)
    harness.run(legacy, tmp_path / 'old', pause_after_objective_attempts=1)
    monkeypatch.setattr(detailed.FixedReceptorEvaluator, 'evaluate', forbidden)
    with pytest.raises(ResearchError, match='journal binding changed'):
        harness.inspect(tmp_path / 'old')
    if mutation == 'binding':
        harness.binding['synthetic_fixture'] = 'changed input binding'
    else:
        harness.system.coordinates[0, 0, 0] = 1.
    with pytest.raises(ResearchError, match='journal binding changed'):
        harness.inspect(tmp_path / 'new')


@pytest.mark.parametrize('mutation', ['message', 'phase', 'stage', 'reason', 'source_line', 'raw_field'])
def test_retained_detail_mutations_are_rejected_even_if_detail_resealed(harness, tmp_path, mutation):
    def fail(*args):
        raise legacy.APPLICABILITY_ERRORS[0]('angle contains a zero-length vector')
    harness.scenario['fault'] = fail
    path = tmp_path / 'run'
    result = harness.run(detailed, path)
    payload = events(path)[-1]['payload']
    detail = deepcopy(payload['failure_detail'])
    if mutation == 'message':
        detail['message']['sha256'] = '0' * 64
    elif mutation == 'phase':
        detail['phase'] = 'resume'
    elif mutation == 'stage':
        detail['stage'] = 'neighbor_graph'
    elif mutation == 'reason':
        detail['reason_code'] = 'pair_below_minimum_distance'
    elif mutation == 'source_line':
        detail['source_position']['line'] = 999999
    else:
        detail['raw_message'] = '/private/source token=secret'
    detail['detail_sha256'] = digest({k: v for k, v in detail.items() if k != 'detail_sha256'})
    payload['failure_detail'] = detail
    with pytest.raises(ResearchError):
        detailed._validate_diagnostics(payload, events(path)[0]['payload'], 'initial', source_manifest())
    assert harness.inspect(path)['numerical_result'] == result


def test_cause_chain_cycles_are_bounded_and_non_ascii_hash_is_exact():
    first, second = RuntimeError('α\r\nβ'), ValueError('different')
    first.__cause__, second.__cause__ = second, first
    detail = diagnostics.capture_failure(first, phase='initial', stage='force_evaluation', attempt=1,
                                         verification=None, failure='fatal', source_pins={})
    assert detail['cause_chain_truncated'] is True and len(detail['cause_chain']) == 1
    assert detail['message']['sha256'] == hashlib.sha256('α\r\nβ'.encode('utf-8')).hexdigest()
    assert detail['message']['bytes'] == len('α\r\nβ'.encode('utf-8'))


@pytest.fixture
def prepared_request(harness, tmp_path, monkeypatch):
    parent = workflow.parent
    refs = {}
    for role in parent.FILE_FIELDS:
        path = tmp_path / (role + '.json')
        raw = (canonical({'synthetic_role': role}) + '\n').encode('ascii')
        path.write_bytes(raw)
        refs[role] = {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest()}
    request = {**refs, 'schema_id': parent.REQUEST_SCHEMA, 'backend': 'python_cpu_reference',
               'pocket': {'center_angstrom': [0., 0., 0.], 'radius_angstrom': 8.,
                          'coordinate_frame_id': 'synthetic', 'source_artifact_sha256': 'c' * 64,
                          'method_id': 'synthetic', 'method_version': '1'},
               'receptor_margin_angstrom': 1., 'budget': {'candidate_count': 1, 'top_k': 1,
                   'max_torsions': 0, 'translation_radius_angstrom': 0., 'seed': 0},
               'solver': harness.config.to_dict(), 'solvation': None,
               'comparison': asdict(parent.RefinementComparisonConfig(mode='same_candidates',
                   require_convergence_for_selection=True)), 'selection': parent.SelectionConfig(1).to_dict()}
    monkeypatch.setattr(parent, 'all_atom_system_from_canonical_json', lambda raw: harness.system)
    monkeypatch.setattr(parent, '_parameters', lambda raw: harness.parameters.base_parameters)
    monkeypatch.setattr(parent, '_extension', lambda raw, base: harness.parameters)
    monkeypatch.setattr(parent, 'FixedReceptorEnvironment', SyntheticEnvironment)
    monkeypatch.setattr(parent, 'CrossParameters', SimpleNamespace(from_dict=lambda raw:
        SimpleNamespace(max_internal_increase_kcal_per_mol=5., coordinate_frame_id='synthetic')))
    monkeypatch.setattr(parent, 'scorer_class', forbidden)
    monkeypatch.setattr(parent, 'generate_registered_pose', forbidden)
    return request


def test_prepared_api_authenticates_inputs_and_reaches_actual_runner_and_consumer(
        prepared_request, harness, tmp_path, monkeypatch):
    before = source_manifest()
    audit = workflow.audit_request(prepared_request)
    assert len(audit['prepared_files']) == 5
    assert {r['role'] for r in audit['prepared_files']} == set(workflow.parent.FILE_FIELDS)
    assert audit['force_dispatches'] == audit['graph_dispatches'] == audit['score_dispatches'] == 0
    assert audit['implementation_sources'] == before
    result = workflow.run_minimization(prepared_request, tmp_path / 'run')
    assert result['numerical_result']['work']['optimizer_force_calls'] == 3
    assert result['selection_performed'] is False and result['source_role_admission_verified'] is False
    stored = files(tmp_path / 'run')
    monkeypatch.setattr(detailed, 'build_compact_radius_graph', forbidden)
    monkeypatch.setattr(detailed.FixedReceptorEvaluator, 'evaluate', forbidden)
    verified = workflow.verify_run(prepared_request, tmp_path / 'run')
    assert verified['inspection']['numerical_result'] == result['numerical_result']
    assert verified['force_dispatches'] == verified['score_dispatches'] == verified['graph_dispatches'] == 0
    assert verified['continuation_authorized'] is False
    assert before == source_manifest() and stored == files(tmp_path / 'run')


@pytest.mark.parametrize('mutation', ['hash', 'body', 'backend', 'threshold', 'strain', 'coordinate_frame'])
def test_prepared_api_rejects_tampering_and_does_not_promote_native(
        prepared_request, harness, tmp_path, monkeypatch, mutation):
    request = deepcopy(prepared_request)
    monkeypatch.setattr(detailed.FixedReceptorEvaluator, 'evaluate', forbidden)
    if mutation == 'hash':
        request['ligand']['sha256'] = '0' * 64
    elif mutation == 'body':
        from pathlib import Path
        Path(request['ligand']['path']).write_text('{"changed":true}\n')
    elif mutation == 'backend':
        request['backend'] = 'native'
    elif mutation == 'threshold':
        request['solver']['force_tolerance'] = .002
    elif mutation == 'strain':
        monkeypatch.setattr(workflow.parent, 'CrossParameters', SimpleNamespace(from_dict=lambda raw:
            SimpleNamespace(max_internal_increase_kcal_per_mol=6., coordinate_frame_id='synthetic')))
    else:
        request['pocket']['coordinate_frame_id'] = 'wrong-frame'
    with pytest.raises((ResearchError, ValueError)):
        workflow.run_minimization(request, tmp_path / 'uncreated')
    assert not (tmp_path / 'uncreated').exists()


def test_cli_audit_run_verify_and_private_error_envelope(prepared_request, harness, tmp_path, capsys, monkeypatch):
    request_path = tmp_path / 'request.json'
    request_path.write_text(canonical(prepared_request) + '\n')
    assert cli.main(['audit', '--request', str(request_path)]) == 0
    assert json.loads(capsys.readouterr().out)['scope'] == 'request_structure_and_raw_prepared_file_identity_only'
    assert cli.main(['run', '--request', str(request_path), '--run-dir', str(tmp_path / 'run')]) == 0
    result = json.loads(capsys.readouterr().out)
    monkeypatch.setattr(detailed.FixedReceptorEvaluator, 'evaluate', forbidden)
    assert cli.main(['verify', '--request', str(request_path), '--run-dir', str(tmp_path / 'run')]) == 0
    assert json.loads(capsys.readouterr().out)['inspection']['numerical_result'] == result['numerical_result']
    assert cli.main(['audit', '--request', str(tmp_path / 'PRIVATE-do-not-print.json')]) == 2
    captured = capsys.readouterr()
    error = json.loads(captured.out)
    assert error['status'] == 'blocked' and error['private_message']['status'] == 'captured'
    assert 'PRIVATE-do-not-print' not in captured.out and captured.err == ''


@pytest.mark.parametrize('error,exit_code', [(KeyboardInterrupt('PRIVATE interrupt'), 130),
                                           (SystemExit(7), 7)])
def test_cli_interrupt_retains_pending_without_traceback_or_message(
        prepared_request, harness, tmp_path, capsys, error, exit_code):
    request_path = tmp_path / 'request.json'
    request_path.write_text(canonical(prepared_request) + '\n')
    def interrupt(*args):
        raise error
    harness.scenario['fault'] = interrupt
    path = tmp_path / 'run'
    assert cli.main(['run', '--request', str(request_path), '--run-dir', str(path)]) == exit_code
    output = capsys.readouterr()
    report = json.loads(output.out)
    assert report['status'] == 'interrupted' and report['numerical_work'] == 'unknown_if_reserved'
    assert 'PRIVATE interrupt' not in output.out and output.err == ''
    assert events(path)[-1]['kind'] == 'objective_started'
    assert workflow.verify_run(prepared_request, path)['inspection']['status'] == 'unknown_pending'
