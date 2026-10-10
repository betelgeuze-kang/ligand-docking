"""Synthetic-only prepared comparison adapter contracts, no molecular dispatch."""
from dataclasses import replace
import json
import time

import pytest
import torch

from betelgeuze_engine_v2 import geometry
from betelgeuze_product.cpu_prepared_cartesian_budget_v3 import workflow as budget
from betelgeuze_product.cpu_prepared_shape_comparison_v1 import cartesian as shape
from betelgeuze_product.cpu_prepared_shape_comparison_v1.contracts import ComparisonConfig
from betelgeuze_product.cpu_refinement_fourier_v1.evaluation import (
    FourierFixedEvaluator, FourierInternalEvaluator, FourierEnvironment,
)
from betelgeuze_product.cpu_refinement_linear_angle_v1.evaluation import (
    LinearAngleFixedEvaluator, LinearAngleInternalEvaluator,
)
from betelgeuze_product.cpu_refinement_v1_2 import evaluation, fixed_receptor
from betelgeuze_product.cpu_refinement_v1_2.provenance import (
    ResearchError, coordinates_hex, decode_coordinates,
)
from betelgeuze_product.cpu_refinement_v1_3 import minimization as execution
from betelgeuze_product.cpu_refinement_v1_3.kernel import make_observation
from tests.unit.test_cpu_parent_shape_cartesian import inputs as fourier_inputs
from tests.unit.test_cpu_parent_shape_linear_base import _inputs as linear_inputs

_TOTAL_BASE_CALLS = 0
_STARTED = None


class ForbiddenMolecularEvaluation(BaseException):
    pass


def _forbidden(*args, **kwargs):
    raise ForbiddenMolecularEvaluation('molecular dispatch forbidden in synthetic suite')


@pytest.fixture(autouse=True)
def synthetic_only(monkeypatch):
    global _STARTED
    if _STARTED is None:
        _STARTED = time.monotonic()
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    class SyntheticCalls(list):
        objective = 'quadratic'

    calls = SyntheticCalls()
    for evaluator in (FourierFixedEvaluator, FourierInternalEvaluator,
                      LinearAngleFixedEvaluator, LinearAngleInternalEvaluator,
                      evaluation.ExtendedEvaluator, fixed_receptor.FixedReceptorEvaluator):
        monkeypatch.setattr(evaluator, 'evaluate', _forbidden)
    monkeypatch.setattr(FourierEnvironment, 'evaluate_cross', _forbidden)
    monkeypatch.setattr(geometry, 'build_compact_radius_graph', _forbidden)
    monkeypatch.setattr(execution, 'build_compact_radius_graph', _forbidden)

    def receipt(system, evaluator, config, intent):
        global _TOTAL_BASE_CALLS
        _TOTAL_BASE_CALLS += 1
        assert _TOTAL_BASE_CALLS <= 256, 'reserved half of global 512-call suite limit exceeded'
        assert time.monotonic() - _STARTED < 290, 'synthetic wall budget exceeded'
        xyz = decode_coordinates(intent['coordinates'], system.atom_count)
        calls.append(intent['coordinates'])
        if calls.objective == 'linear':
            gradient = torch.full_like(xyz, .1)
            energy = float((gradient * xyz).sum())
        else:
            target = system.coordinates + .1
            gradient = xyz - target
            energy = float(.5 * gradient.square().sum())
        observation = make_observation(intent['attempt'], xyz, energy, -gradient,
            {'total': energy, 'ligand_internal': energy,
             'cross_lennard_jones': 0., 'cross_screened_coulomb': 0.})
        return {'observation': observation, 'failure': None, 'error_type': None,
                'work': {'graph_calls': 1, 'force_calls': 1, 'failed_force_calls': 0},
                'timings_ns': {'graph': 2, 'force': 3, 'objective': 7}}

    monkeypatch.setattr(execution, '_invoke', receipt)
    try:
        yield calls
    finally:
        torch.set_num_threads(previous)


def values(model='fourier'):
    ligand, parameters, _, fixed, old_binding = (
        fourier_inputs() if model == 'fourier' else linear_inputs())
    if model == 'fourier':
        from betelgeuze_engine_v2.physics.reference_parameters import HarmonicBondParameter
        parameters = replace(parameters, bonds=(HarmonicBondParameter(0, 1, 2., 10.),))
        fixed = FourierEnvironment(fixed.receptor, replace(fixed.cross,
            ligand_base_parameters_sha256=parameters.fingerprint_sha256))
    config = budget.budget_config('lbfgs', 40, restart_verifications=0)
    binding = {'profile_id': budget.PROFILE_ID, 'model': model,
               'accepted_step_budget': 40, 'restart_verifications': 0,
               'candidate_id': old_binding['candidate_id'],
               'prepared_protocol_sha256': old_binding['prepared_protocol_sha256'],
               'initial_coordinates_sha256': old_binding['initial_coordinates_sha256']}
    return ligand, parameters, config, fixed, binding


def run(parts, directory, strength, *, verify=False, reference=None, **options):
    ligand, parameters, config, fixed, binding = parts
    reference = shape.prepare_reference(ligand, binding) if reference is None else reference
    action = shape.verify_shape if verify else shape.minimize_shape
    return action(ligand, parameters, config, fixed_environment=fixed, binding=binding,
                  run_dir=directory, base_profile=binding['model'], reference=reference,
                  strength=strength, **options)


def files(directory):
    return {p.relative_to(directory).as_posix(): p.read_bytes()
            for p in directory.rglob('*') if p.is_file()}


@pytest.mark.parametrize('model', ['fourier', 'linear_angle'])
def test_zero_strength_preserves_prepared_base_trajectory(tmp_path, model, synthetic_only, monkeypatch):
    parts = values(model)
    ligand, parameters, config, fixed, binding = parts
    evaluator, identity = budget._context(ligand, parameters, config, fixed, binding)
    baseline = execution._minimize_profile(ligand, config, evaluator=evaluator, identity=identity,
        run_dir=tmp_path / 'base', implementation_sources=budget.implementation_sources,
        result_schema=budget.RESULT_SCHEMA, model_guard=fixed.assert_intact)
    base_calls = list(synthetic_only)
    synthetic_only.clear()
    result = run(parts, tmp_path / 'shape', 0.)
    assert synthetic_only == base_calls
    base_state = baseline['checkpoint']['state']
    shape_state = result['checkpoint']['state']
    assert shape_state['current']['base_observation'] == base_state['current']
    assert shape_state['accepted'] == base_state['accepted']
    assert result['work']['actual_force_calls'] == baseline['work']['actual_force_calls']
    assert result['work']['optimizer_shape_calls'] == 0
    assert result['converged'] == baseline['converged']
    assert result['scientifically_validated'] is False
    before = files(tmp_path / 'shape')
    monkeypatch.setattr(execution, '_invoke', _forbidden)
    assert run(parts, tmp_path / 'shape', 0., verify=True) == result
    assert run(parts, tmp_path / 'shape', 0., resume=True) == result
    assert files(tmp_path / 'shape') == before


@pytest.mark.parametrize('strength', [100., 1000.])
def test_nonzero_arm_binds_original_parent_and_counts_shape(tmp_path, strength, synthetic_only, monkeypatch):
    parts = values('linear_angle')
    reference = shape.prepare_reference(parts[0], parts[4])
    original = reference.to_document()
    result = run(parts, tmp_path / 'arm', strength, reference=reference,
                 pause_after_objective_attempts=3)
    assert result['work']['optimizer_shape_calls'] == len(synthetic_only)
    assert result['work']['optimizer_base_force_calls'] == len(synthetic_only)
    assert result['work']['restart_verification_attempts'] == 0
    assert result['pose_selection_admitted'] is False
    assert reference.to_document() == original
    metadata = json.loads((tmp_path / 'arm' / 'meta.json').read_text())['binding']
    assert metadata['shape_reference_sha256'] == reference.digest
    assert metadata['strength_kcal_per_mol_per_angstrom_squared'] == strength.hex()
    monkeypatch.setattr(execution, '_invoke', _forbidden)
    assert run(parts, tmp_path / 'arm', strength, verify=True, reference=reference) == result


def test_reference_and_source_drift_fail_without_new_work(tmp_path, synthetic_only, monkeypatch):
    parts = values()
    reference = shape.prepare_reference(parts[0], parts[4])
    run(parts, tmp_path / 'arm', 100., pause_after_objective_attempts=2)
    before = files(tmp_path / 'arm')
    monkeypatch.setattr(execution, '_invoke', _forbidden)
    with pytest.raises(ResearchError):
        run(parts, tmp_path / 'arm', 100., resume=True)
    with pytest.raises(ResearchError):
        run(parts, tmp_path / 'arm', 1000., verify=True)
    changed = replace(reference, source_digest='d' * 64)
    with pytest.raises(ResearchError):
        run(parts, tmp_path / 'arm', 100., reference=changed, verify=True)
    source = shape.implementation_sources
    monkeypatch.setattr(shape, 'implementation_sources',
                        lambda base: {**source(base), 'changed.py': 'd' * 64})
    with pytest.raises(ResearchError):
        run(parts, tmp_path / 'arm', 100., verify=True)
    assert files(tmp_path / 'arm') == before


@pytest.mark.parametrize('changes', [
    {'accepted_steps': True}, {'accepted_steps': 4}, {'accepted_steps': 40.},
    {'restart_verifications': 1}, {'restart_verifications': False},
    {'diagnostic_stride': 1}, {'diagnostic_maximum_records': 18},
])
def test_comparison_controls_fail_closed(changes):
    with pytest.raises(ResearchError):
        ComparisonConfig(**changes)


@pytest.mark.parametrize('steps', [40, 80, 160])
def test_comparison_limits_are_equal_not_forced_equal_consumption(steps):
    config = ComparisonConfig(accepted_steps=steps).to_dict()
    assert config['optimizer_objective_attempt_limit_per_arm'] == 1 + 4 * steps
    assert config['optimizer_actual_base_call_limit_per_arm'] == 1 + 4 * steps
    assert config['baseline_evaluation_limit'] == 1
    assert config['limits_are_equal_consumption_may_differ'] is True


def baseline_arguments(tmp_path):
    ligand, parameters, config, fixed, binding = values()
    evaluator, identity = budget._context(ligand, parameters, config, fixed, binding)
    return ligand, config, evaluator, identity, {
        'output_dir': tmp_path / 'B0', 'plan_sha256': 'e' * 64}


def test_baseline_has_one_evaluation_zero_optimizer_calls_and_force_free_replay(
        tmp_path, monkeypatch, synthetic_only):
    from betelgeuze_product.cpu_prepared_shape_comparison_v1 import workflow
    ligand, config, evaluator, identity, options = baseline_arguments(tmp_path)
    monkeypatch.setattr(execution, '_minimize_profile', _forbidden)
    monkeypatch.setattr(execution, 'CartesianMachine', _forbidden)
    result = workflow.evaluate_baseline(ligand, config, evaluator, identity, **options)
    assert len(synthetic_only) == 1
    assert result['status'] == 'evaluated'
    assert result['evaluation_attempts'] == 1
    assert result['evaluation_work'] == {'graph_calls': 1, 'force_calls': 1, 'failed_force_calls': 0}
    assert result['optimizer_objective_attempts'] == result['optimizer_force_calls'] == 0
    assert result['receipt']['observation']['coordinates'] == coordinates_hex(ligand.coordinates)
    before = files(options['output_dir'])
    monkeypatch.setattr(execution, '_invoke', _forbidden)
    assert workflow.verify_baseline(ligand, config, identity, **options) == result
    assert files(options['output_dir']) == before
    with pytest.raises((ResearchError, FileExistsError)):
        workflow.evaluate_baseline(ligand, config, evaluator, identity, **options)
    assert files(options['output_dir']) == before


def test_failed_baseline_evaluation_is_counted_and_retained(tmp_path, monkeypatch, synthetic_only):
    from betelgeuze_product.cpu_prepared_shape_comparison_v1 import workflow
    ligand, config, evaluator, identity, options = baseline_arguments(tmp_path)
    invoke = execution._invoke

    def failed(*args, **kwargs):
        result = invoke(*args, **kwargs)
        result.update(observation=None, failure='fatal', error_type='SyntheticFailure')
        result['work']['failed_force_calls'] = 1
        return result

    monkeypatch.setattr(execution, '_invoke', failed)
    result = workflow.evaluate_baseline(ligand, config, evaluator, identity, **options)
    assert len(synthetic_only) == 1
    assert result['status'] == 'failed'
    assert result['evaluation_work']['failed_force_calls'] == 1
    assert result['optimizer_objective_attempts'] == result['optimizer_force_calls'] == 0
    monkeypatch.setattr(execution, '_invoke', _forbidden)
    assert workflow.verify_baseline(ligand, config, identity, **options) == result


def test_unfinished_baseline_reservation_cannot_be_retried(tmp_path, monkeypatch, synthetic_only):
    from betelgeuze_product.cpu_prepared_shape_comparison_v1 import workflow
    ligand, config, evaluator, identity, options = baseline_arguments(tmp_path)
    invoke = execution._invoke

    class Interrupted(BaseException):
        pass

    def interrupted(*args, **kwargs):
        invoke(*args, **kwargs)
        raise Interrupted()

    monkeypatch.setattr(execution, '_invoke', interrupted)
    with pytest.raises(Interrupted):
        workflow.evaluate_baseline(ligand, config, evaluator, identity, **options)
    assert len(synthetic_only) == 1
    before = files(options['output_dir'])
    assert set(before) == {'binding.json', 'evaluation-started.json'}
    monkeypatch.setattr(execution, '_invoke', _forbidden)
    with pytest.raises(ResearchError):
        workflow.verify_baseline(ligand, config, identity, **options)
    with pytest.raises((ResearchError, FileExistsError)):
        workflow.evaluate_baseline(ligand, config, evaluator, identity, **options)
    assert files(options['output_dir']) == before


def test_baseline_replay_rejects_receipt_and_binding_tampering(tmp_path, monkeypatch):
    from betelgeuze_product.cpu_prepared_shape_comparison_v1 import workflow
    ligand, config, evaluator, identity, options = baseline_arguments(tmp_path)
    workflow.evaluate_baseline(ligand, config, evaluator, identity, **options)
    monkeypatch.setattr(execution, '_invoke', _forbidden)
    with pytest.raises(ResearchError):
        workflow.verify_baseline(ligand, config, identity, **{**options, 'plan_sha256': 'f' * 64})
    path = options['output_dir'] / 'evaluation-finished.json'
    value = json.loads(path.read_text())
    value['optimizer_force_calls'] = 1
    path.write_text(json.dumps(value))
    with pytest.raises(ResearchError):
        workflow.verify_baseline(ligand, config, identity, **options)


def test_whole_runner_keeps_failed_arm_and_diagnostics_denominator(tmp_path, monkeypatch):
    from betelgeuze_product.cpu_prepared_shape_comparison_v1 import workflow
    parts = values()
    ligand, parameters, config, fixed, binding = parts
    evaluator, identity = budget._context(ligand, parameters, config, fixed, binding)
    reference = shape.prepare_reference(ligand, binding)
    loaded = ligand, parameters, config, fixed, evaluator, identity
    monkeypatch.setattr(workflow, '_load_plan', lambda *args:
        ({'model': 'fourier', 'preparation_phase_costs': []}, ComparisonConfig(), loaded, reference))

    def diagnostic_failure(*args, **kwargs):
        raise ResearchError('synthetic diagnostic unavailable')

    monkeypatch.setattr(workflow.diagnostics, 'diagnose_shape_run', diagnostic_failure)
    monkeypatch.setattr(workflow.diagnostics, 'diagnose_baseline', diagnostic_failure)
    minimize = shape.minimize_shape

    def fail_one(*args, **kwargs):
        if kwargs['strength'] == 100.:
            raise ResearchError('synthetic arm failure')
        return minimize(*args, **kwargs)

    monkeypatch.setattr(shape, 'minimize_shape', fail_one)
    result = workflow.run(tmp_path / 'unused-plan', 'e' * 64, tmp_path / 'comparison')
    report = result['report']
    assert [r['arm'] for r in report['arms']] == ['B0', 'B1', 'B2', 'B3']
    assert report['denominator'] == {'planned': 4, 'attempted': 4,
        'with_verified_result': 3, 'without_verified_result': 1}
    rows = {r['arm']: r for r in report['arms']}
    assert rows['B2']['status'] == 'failed_or_unknown'
    assert rows['B2']['result_sha256'] is None
    for arm in ('B0', 'B1', 'B3'):
        assert rows[arm]['diagnostic_status'] == 'failed_or_unknown'
        assert rows[arm]['result_sha256'] is not None
    assert not any(report['boundary'].values())
    before = files(tmp_path / 'comparison')
    monkeypatch.setattr(execution, '_invoke', _forbidden)
    monkeypatch.setattr(workflow.diagnostics, 'diagnose_shape_run', _forbidden)
    monkeypatch.setattr(workflow.diagnostics, 'diagnose_baseline', _forbidden)
    assert workflow.verify(tmp_path / 'unused-plan', 'e' * 64, tmp_path / 'comparison',
        expected_completion_sha256=result['completion']['completion_sha256']) == report
    with pytest.raises((ResearchError, FileExistsError)):
        workflow.run(tmp_path / 'unused-plan', 'e' * 64, tmp_path / 'comparison')
    assert files(tmp_path / 'comparison') == before
    (tmp_path / 'comparison' / 'B2-finished.json').write_text('{}')
    with pytest.raises(ResearchError):
        workflow.verify(tmp_path / 'unused-plan', 'e' * 64, tmp_path / 'comparison',
            expected_completion_sha256=result['completion']['completion_sha256'])


@pytest.mark.parametrize('model', ['fourier', 'linear_angle'])
def test_prepared_plan_round_trip_and_byte_drift_are_force_free(tmp_path, monkeypatch, model, synthetic_only):
    from betelgeuze_engine_v2.molecular.serialization import canonical_system_json_bytes
    from betelgeuze_product.cpu_prepared_shape_comparison_v1 import workflow
    from betelgeuze_product.cpu_refinement_v1_2.provenance import canonical
    ligand, parameters, config, fixed, binding = values(model)
    raw = {'ligand': canonical_system_json_bytes(ligand),
           'receptor': canonical_system_json_bytes(fixed.receptor),
           'parameters': canonical(parameters.to_dict()).encode(),
           'cross': canonical(fixed.cross.to_dict()).encode(),
           'source_evidence': canonical({
               'schema_version': 'declared_prepared_source_evidence/1.0.0',
               'evidence_kind': 'synthetic_control', 'source_files': [],
               'source_authenticated': False,
               'original_simulation_hamiltonian_reproduced': False}).encode()}
    paths = {}
    for name, content in raw.items():
        paths[name] = tmp_path / (name + '.json')
        paths[name].write_bytes(content)
    monkeypatch.setattr(execution, '_invoke', _forbidden)
    prepared = budget.prepare(model=model, accepted_steps=40, restart_verifications=0,
        candidate_id=binding['candidate_id'], evidence_kind='synthetic_control',
        solver=config, output=tmp_path / 'prepared.json', **paths)
    sealed = workflow.prepare(prepared['protocol_path'], prepared['protocol_sha256'],
                              tmp_path / 'plan', model=model)
    preflight = workflow.preflight(sealed['plan_path'], sealed['plan_sha256'])
    assert preflight['status'] == 'admitted_for_bounded_development_execution'
    assert not any(preflight['boundary'].values())
    assert synthetic_only == []
    path = tmp_path / 'plan' / 'plan.json'
    path.write_bytes(path.read_bytes() + b' ')
    with pytest.raises(ResearchError):
        workflow.preflight(sealed['plan_path'], sealed['plan_sha256'])


@pytest.fixture
def analytic_diagnostics(monkeypatch):
    """Mock P2 arithmetic with retained analytic components, preserving its schema."""
    from dataclasses import asdict
    from betelgeuze_engine_v2.molecular import canonical_topology_sha256
    from betelgeuze_product.cpu_refinement_diagnostics_v1 import evaluation as diagnostic_evaluation
    from betelgeuze_product.cpu_refinement_diagnostics_v1 import workflow as diagnostic_workflow
    from betelgeuze_product.cpu_refinement_diagnostics_v1.contracts import RECORD_SCHEMA, empty_work
    from betelgeuze_product.cpu_refinement_diagnostics_v1.geometry import geometry_changes
    from betelgeuze_product.cpu_refinement_v1_2.provenance import digest
    calls = []

    def analytic(original, evaluator, config, observation, *, observation_ref,
                 diagnostic_config=None, shape_profile=None):
        calls.append(observation_ref)
        assert len(calls) <= 64
        observed = (execution.validate_observation(observation, original.atom_count)
                    if shape_profile is None else
                    shape_profile.validate_observation(observation, original.atom_count))
        base = observed if shape_profile is None else observed['base_observation']
        force = decode_coordinates(base['forces'], original.atom_count)
        xyz = decode_coordinates(observed['coordinates'], original.atom_count)
        atoms = [{'source_index': atom.index, 'element': atom.element,
                  'atom_metadata_sha256': digest(asdict(atom))} for atom in original.atoms]
        component = diagnostic_evaluation._component
        zero = torch.zeros_like(force)
        work = empty_work()
        work.update(graph_calls=1, internal_evaluator_calls=1, cross_passes=1,
                    cross_blocks_visited=1, cross_blocks_active=1,
                    cross_component_gradient_calls=2,
                    retained_shape_reuses=int(shape_profile is not None))
        record = {'schema_id': RECORD_SCHEMA, 'observation_ref': observation_ref,
            'observation_sha256': digest(observed), 'coordinates_sha256': digest(observed['coordinates']),
            'topology_sha256': canonical_topology_sha256(original), 'atoms': atoms,
            'evaluator': evaluator.identity(), 'source_evidence_verified': False,
            'status': 'evaluated', 'components': {
                'ligand_internal': component(float.fromhex(base['energy']), force, atoms),
                'cross_lennard_jones': component(0., zero, atoms),
                'cross_screened_coulomb': component(0., zero, atoms)},
            'internal_component_energies': {'analytic_quadratic': base['energy']},
            'internal_component_energy_semantics': 'subdivision_of_ligand_internal_not_additional_terms',
            'internal_component_forces_available': False,
            'unpenalized_total': component(float.fromhex(base['energy']), force, atoms),
            'parity': {'unpenalized_forces': diagnostic_evaluation._parity(force, force)},
            'geometry': geometry_changes(original,
                original.with_coordinates(xyz, operation='synthetic_retained_diagnostic'), evaluator.parameters),
            'failure_code': None, 'work': work, 'wall_ns': 7}
        if shape_profile is not None:
            shape_force = decode_coordinates(observed['restraint_forces'], original.atom_count)
            record['components']['parent_shape_restraint'] = component(
                float.fromhex(observed['components']['parent_shape_restraint']), shape_force, atoms)
            record['augmented_total'] = component(float.fromhex(observed['energy']),
                decode_coordinates(observed['forces'], original.atom_count), atoms)
        return {**record, 'record_sha256': digest(record)}

    monkeypatch.setattr(diagnostic_evaluation, 'diagnose_observation', analytic)
    monkeypatch.setattr(diagnostic_workflow, 'diagnose_observation', analytic)
    return calls


def test_baseline_diagnostic_roundtrip_and_tamper_are_force_free(
        tmp_path, monkeypatch, synthetic_only, analytic_diagnostics):
    from betelgeuze_product.cpu_prepared_shape_comparison_v1 import workflow, diagnostics
    from betelgeuze_product.cpu_refinement_diagnostics_v1 import evaluation as diagnostic_evaluation
    ligand, config, evaluator, identity, options = baseline_arguments(tmp_path)
    baseline = workflow.evaluate_baseline(ligand, config, evaluator, identity, **options)
    source_before = files(options['output_dir'])
    sidecar_options = {'baseline_dir': options['output_dir'], 'plan_sha256': options['plan_sha256'],
                       'output_dir': tmp_path / 'B0-diagnostics'}
    record = diagnostics.diagnose_baseline(ligand, evaluator, config, identity, **sidecar_options)
    assert len(synthetic_only) == len(analytic_diagnostics) == 1
    assert record['status'] == 'evaluated'
    assert record['source_evidence_verified'] is True
    assert record['observation_ref']['result_sha256'] == baseline['result_sha256']
    assert record['work']['internal_evaluator_calls'] == 1
    assert record['work']['retained_shape_reuses'] == 0
    assert files(options['output_dir']) == source_before
    before = files(sidecar_options['output_dir'])
    monkeypatch.setattr(execution, '_invoke', _forbidden)
    monkeypatch.setattr(diagnostic_evaluation, 'diagnose_observation', _forbidden)
    assert diagnostics.verify_baseline_sidecar(ligand, config, identity, **sidecar_options,
        expected_record_sha256=record['record_sha256']) == record
    assert files(sidecar_options['output_dir']) == before
    with pytest.raises(ResearchError):
        diagnostics.verify_baseline_sidecar(ligand, config, identity, **sidecar_options,
            expected_record_sha256='f' * 64)
    path = sidecar_options['output_dir'] / 'diagnostic-finished.json'
    altered = json.loads(path.read_text())
    altered['work']['internal_evaluator_calls'] += 1
    path.write_text(json.dumps(altered))
    with pytest.raises(ResearchError):
        diagnostics.verify_baseline_sidecar(ligand, config, identity, **sidecar_options,
            expected_record_sha256=record['record_sha256'])


def test_whole_runner_successful_diagnostic_bridge_and_force_free_replay(
        tmp_path, monkeypatch, synthetic_only, analytic_diagnostics):
    from betelgeuze_product.cpu_prepared_shape_comparison_v1 import workflow
    from betelgeuze_product.cpu_refinement_diagnostics_v1 import evaluation as diagnostic_evaluation
    from betelgeuze_product.cpu_refinement_diagnostics_v1 import workflow as diagnostic_workflow
    ligand, parameters, config, fixed, binding = values()
    evaluator, identity = budget._context(ligand, parameters, config, fixed, binding)
    reference = shape.prepare_reference(ligand, binding)
    loaded = ligand, parameters, config, fixed, evaluator, identity
    monkeypatch.setattr(workflow, '_load_plan', lambda *args:
        ({'model': 'fourier', 'preparation_phase_costs': []}, ComparisonConfig(), loaded, reference))
    result = workflow.run(tmp_path / 'unused-plan', 'e' * 64, tmp_path / 'comparison')
    report = result['report']
    rows = report['arms']
    assert report['denominator']['with_verified_result'] == 4
    assert report['denominator']['without_verified_result'] == 0
    assert rows[0]['diagnostic_status'] == 'evaluated'
    assert all(r['diagnostic_status'] == 'complete' for r in rows[1:])
    assert all(r['diagnostic_work']['failed_evaluations'] == 0 for r in rows)
    totals = report['work_totals']
    assert totals['all_actual_base_calls_excluding_diagnostics'] == len(synthetic_only)
    assert totals['baseline_evaluation_base_calls'] == 1
    assert totals['diagnostic_known_completed_work']['internal_evaluator_calls'] == len(analytic_diagnostics)
    assert totals['diagnostic_known_completed_work']['retained_shape_reuses'] == len(analytic_diagnostics) - 1
    assert totals['diagnostic_arms_with_unavailable_or_unknown_work'] == 0
    for arm in ('B1', 'B2', 'B3'):
        sidecar = json.loads((tmp_path / 'comparison' / (arm + '-diagnostics') / 'report.json').read_text())
        row = next(r for r in rows if r['arm'] == arm)
        assert sidecar['original_solver_work'] == row['work']
        assert sidecar['report_sha256'] == row['diagnostic_report_sha256']
    before = files(tmp_path / 'comparison')
    monkeypatch.setattr(execution, '_invoke', _forbidden)
    monkeypatch.setattr(diagnostic_evaluation, 'diagnose_observation', _forbidden)
    monkeypatch.setattr(diagnostic_workflow, 'diagnose_observation', _forbidden)
    assert workflow.verify(tmp_path / 'unused-plan', 'e' * 64, tmp_path / 'comparison',
        expected_completion_sha256=result['completion']['completion_sha256']) == report
    assert files(tmp_path / 'comparison') == before
    path = tmp_path / 'comparison' / 'B1-diagnostics' / 'record-00000.json'
    path.write_bytes(path.read_bytes() + b' ')
    with pytest.raises(ResearchError):
        workflow.verify(tmp_path / 'unused-plan', 'e' * 64, tmp_path / 'comparison',
            expected_completion_sha256=result['completion']['completion_sha256'])


def test_aggregate_unknown_work_is_null_and_known_partial_is_retained():
    from betelgeuze_product.cpu_prepared_shape_comparison_v1 import workflow
    rows = [
        {'arm': 'B0', 'work': {'evaluation_work': {'force_calls': 1}},
         'diagnostic_work': {'internal_evaluator_calls': 1}},
        {'arm': 'B1', 'work': {'optimizer_base_force_calls': 4, 'actual_force_calls': 4,
                             'optimizer_shape_calls': 0}},
        {'arm': 'B2', 'work': {'optimizer_base_force_calls': 3, 'actual_force_calls': None,
                             'optimizer_shape_calls': 2, 'optimizer_failed_base_force_calls': 1}},
        {'arm': 'B3', 'work': None},
    ]
    result = workflow._aggregate(rows)
    assert result['optimizer_known_completed_base_calls'] == 7
    assert result['optimizer_actual_base_calls'] is None
    assert result['all_actual_base_calls_excluding_diagnostics'] is None
    assert result['optimizer_arms_with_unknown_work'] == 2
    assert result['optimizer_failed_base_calls'] == 1
    assert result['optimizer_known_shape_calls'] == 2
    assert result['baseline_evaluation_base_calls'] == 1
    assert result['diagnostic_known_completed_work'] == {'internal_evaluator_calls': 1}
    assert result['diagnostic_arms_with_unavailable_or_unknown_work'] == 3
    assert result['unknown_work_is_not_zero_and_is_not_retried'] is True


def test_zero_strength_long_budget_crosses_four_step_seam_exactly(
        tmp_path, monkeypatch, synthetic_only):
    synthetic_only.objective = 'linear'
    parts = values()
    ligand, parameters, config, fixed, binding = parts
    evaluator, identity = budget._context(ligand, parameters, config, fixed, binding)
    baseline = execution._minimize_profile(ligand, config, evaluator=evaluator, identity=identity,
        run_dir=tmp_path / 'base-long', implementation_sources=budget.implementation_sources,
        result_schema=budget.RESULT_SCHEMA, model_guard=fixed.assert_intact)
    base_calls = list(synthetic_only)
    assert len(base_calls) == 41
    synthetic_only.clear()
    result = run(parts, tmp_path / 'shape-long', 0.)
    assert synthetic_only == base_calls
    assert len(synthetic_only) == 41
    for item in (baseline, result):
        assert item['status'] == 'max_accepted_steps_reached'
        assert item['checkpoint']['state']['accepted'] == 40
        assert item['work']['optimizer_objective_attempts'] == 41
        assert item['work']['actual_force_calls'] == 41
        assert item['work']['restart_verification_attempts'] == 0
        assert item['converged'] is False
    assert result['work']['optimizer_shape_calls'] == 0
    assert (result['checkpoint']['state']['current']['base_observation']
            == baseline['checkpoint']['state']['current'])
    energies = []
    for line in (tmp_path / 'shape-long' / 'events.jsonl').read_text().splitlines():
        event = json.loads(line)
        if event['kind'] == 'objective_finished':
            energies.append(float.fromhex(event['payload']['observation']['energy']))
    assert len(energies) == 41
    assert all(next_energy < energy for energy, next_energy in zip(energies, energies[1:]))
    before = files(tmp_path / 'shape-long')
    monkeypatch.setattr(execution, '_invoke', _forbidden)
    assert run(parts, tmp_path / 'shape-long', 0., verify=True) == result
    assert run(parts, tmp_path / 'shape-long', 0., resume=True) == result
    assert files(tmp_path / 'shape-long') == before


def test_shape_failure_after_successful_base_is_fully_counted(tmp_path, monkeypatch, synthetic_only):
    parts = values()

    def broken(*args, **kwargs):
        raise ResearchError('synthetic shape failure after base')

    monkeypatch.setattr(shape, '_calculate', broken)
    result = run(parts, tmp_path / 'arm', 100.)
    work = result['work']
    assert len(synthetic_only) == 1
    assert work['optimizer_base_force_calls'] == 1
    assert work['optimizer_failed_base_force_calls'] == 0
    assert work['optimizer_shape_calls'] == work['optimizer_failed_shape_calls'] == 1
    assert work['actual_force_calls'] == 1
    monkeypatch.setattr(execution, '_invoke', _forbidden)
    assert run(parts, tmp_path / 'arm', 100., verify=True) == result


def test_baseline_symlink_parent_rejected_before_work(tmp_path, synthetic_only):
    from betelgeuze_product.cpu_prepared_shape_comparison_v1 import workflow
    original = tmp_path / 'real'
    original.mkdir()
    link = tmp_path / 'alias'
    link.symlink_to(original, target_is_directory=True)
    ligand, config, evaluator, identity, options = baseline_arguments(tmp_path)
    options['output_dir'] = link / 'B0'
    with pytest.raises((OSError, ResearchError)):
        workflow.evaluate_baseline(ligand, config, evaluator, identity, **options)
    assert not list(original.iterdir())
    assert len(synthetic_only) == 0


def test_baseline_diagnostic_output_cannot_modify_source(tmp_path, monkeypatch):
    from betelgeuze_product.cpu_prepared_shape_comparison_v1 import workflow, diagnostics
    from betelgeuze_product.cpu_refinement_diagnostics_v1 import evaluation as diagnostic_evaluation
    ligand, config, evaluator, identity, options = baseline_arguments(tmp_path)
    workflow.evaluate_baseline(ligand, config, evaluator, identity, **options)
    before = files(options['output_dir'])
    monkeypatch.setattr(diagnostic_evaluation, 'diagnose_observation', _forbidden)
    with pytest.raises(ResearchError, match='outside original evidence'):
        diagnostics.diagnose_baseline(ligand, evaluator, config, identity,
            baseline_dir=options['output_dir'], plan_sha256=options['plan_sha256'],
            output_dir=options['output_dir'] / 'sidecar')
    assert files(options['output_dir']) == before
