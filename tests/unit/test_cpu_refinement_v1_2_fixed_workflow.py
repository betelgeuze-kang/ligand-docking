"""D3 integration: authentic candidates, explicit objective, preserved legacy behavior."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import pytest
from betelgeuze_engine_v2.physics.reference_parameters import AtomNonbondedParameter
from betelgeuze_engine_v2.physics.reference_forcefield_v2 import ReferenceForceFieldV2Parameters
from betelgeuze_engine_v2.molecular import canonical_system_sha256, canonical_topology_sha256
from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import CrossParameters, FIXED_REQUEST_SCHEMA, FIXED_REPORT_SCHEMA, FIXED_EVALUATOR_ID
from betelgeuze_product.cpu_refinement_v1_2 import workflow
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError, digest
from betelgeuze_product.cpu_refinement_v1_2.verification import verify_report
from betelgeuze_product.cpu_refinement_v1_2.selection import refinement_admissible
from betelgeuze_product.cpu_refinement_v1_2.comparison import choose_variant
from tests.unit.test_cpu_refinement_v1_2_workflow import request_fixture
from tests.unit.test_engine_v2_energy_local_refinement_stage6 import _authority, _parameters

def fixed_request_fixture(directory: Path, *, equal_budget=False):
    request = request_fixture(directory)
    _, receptor, ligand = _authority()
    base = replace(_parameters(ligand), atom_parameters=tuple((AtomNonbondedParameter(i, 1.0, 0.05, atom.partial_charge_e) for i, atom in enumerate(ligand.atoms))))
    extensions = ReferenceForceFieldV2Parameters(base)
    cross = CrossParameters('synthetic-cross-workflow', '1', 'e' * 64, canonical_system_sha256(receptor), canonical_topology_sha256(ligand), base.fingerprint_sha256, request['pocket']['coordinate_frame_id'], tuple((AtomNonbondedParameter(i, 1.5, 0.05, a.partial_charge_e) for i, a in enumerate(receptor.atoms))), (), 8.0, 6.0, 10.0, 0.1, 0.05)
    for name, content in (('parameters', base.to_dict()), ('extensions', extensions.to_dict()), ('cross_parameters', cross.to_dict())):
        raw = json.dumps(content).encode()
        path = directory / (name + '-fixed.json')
        path.write_bytes(raw)
        request[name] = {'path': str(path.absolute()), 'sha256': hashlib.sha256(raw).hexdigest()}
    request['schema_id'] = FIXED_REQUEST_SCHEMA
    request['max_internal_increase_kcal_per_mol'] = 5.0
    if equal_budget:
        request['budget']['candidate_count'] = 8
        request['budget']['max_refinement_steps'] = 2
        request['solver']['minimization']['max_backtracks'] = 0
        request['comparison']['mode'] = 'equal_work_budget'
        request['comparison']['work_units_per_arm'] = 8
    return request

@pytest.mark.parametrize('equal_budget', [False, True])
def test_fixed_receptor_actual_pipeline_and_portable_verifier(tmp_path, equal_budget):
    request = fixed_request_fixture(tmp_path, equal_budget=equal_budget)
    before = Path(request['receptor']['path']).read_bytes()
    output = tmp_path / 'run'
    r = workflow.run_request(request, output)['result']
    assert r['schema_id'] == FIXED_REPORT_SCHEMA
    assert r['receptor_ligand_interaction_energy_minimized'] is True
    assert r['arms']['refined']['failure_count'] == 0
    assert r['arms']['refined']['actual_force_evaluation_calls'] > 0
    assert Path(request['receptor']['path']).read_bytes() == before
    for attempt, row in zip(r['attempts'], r['arms']['refined']['rows'], strict=True):
        assert attempt['pre_coordinates_sha256'] != attempt['post_coordinates_sha256']
        assert attempt['energy_delta'] < 0
        assert row['coordinates_sha256'] == attempt['post_coordinates_sha256']
        assert abs(attempt['initial_objective_components']['cross_screened_coulomb']) > 0
    assert workflow.verify_output(output)['input_binding_evidence_present'] is True
    for name in ('receptor', 'ligand', 'parameters', 'extensions', 'cross_parameters'):
        Path(request[name]['path']).unlink()
    assert workflow.verify_output(output)['structural_verification_passed'] is True
    assert r['final_selection'] is None if equal_budget else r['final_selection'] is not None

def test_strain_policy_distinguishes_total_descent_from_internal_increase():
    row = {'succeeded': True, 'selection_eligible': True, 'score': -3.0}
    before = {**row, 'score': -2.0}
    attempt = {'status': 'success', 'converged': True, 'energy_delta': -2.0, 'evaluator': {'evaluator_id': FIXED_EVALUATOR_ID}, 'initial_objective_components': {'ligand_internal': 0.0}, 'final_objective_components': {'ligand_internal': 1.0}}
    assert not refinement_admissible(row, attempt, True, 0.5)
    assert refinement_admissible(row, attempt, True, 1.0)
    assert choose_variant(before, row, attempt, True, 0.5) == ('baseline', 'ligand_strain_limit_exceeded')
    assert choose_variant(before, row, attempt, True, 1.0) == ('refined', 'valid_refinement_selected')
    with pytest.raises(ResearchError, match='cap'):
        refinement_admissible(row, attempt, True)

@pytest.mark.parametrize('change', ['components', 'total', 'environment', 'cap', 'scope', 'policy', 'request_cross', 'request_cap'])
def test_fixed_result_crosswiring_rejected_after_outer_rehash(tmp_path, change):
    req = fixed_request_fixture(tmp_path)
    out = tmp_path / 'out'
    report = workflow.run_request(req, out)
    result = deepcopy(report['result'])
    if change == 'components':
        a = result['attempts'][0]
        a['final_objective_components']['cross_screened_coulomb'] += 1.0
        a['receipt_sha256'] = digest({k: v for k, v in a.items() if k != 'receipt_sha256'})
    elif change == 'total':
        a = result['attempts'][0]
        a['initial_objective_components']['total'] += 1.0
        a['receipt_sha256'] = digest({k: v for k, v in a.items() if k != 'receipt_sha256'})
    elif change == 'environment':
        a = result['attempts'][0]
        a['evaluator']['receptor_system_sha256'] = '0' * 64
        a['receipt_sha256'] = digest({k: v for k, v in a.items() if k != 'receipt_sha256'})
    elif change == 'cap':
        result['max_internal_increase_kcal_per_mol'] = -1.0
    elif change == 'scope':
        result['receptor_ligand_interaction_energy_minimized'] = False
    elif change == 'policy':
        result['selection_policy_id'] = 'changed-policy'
    elif change == 'request_cross':
        result['request_binding']['cross_parameters']['sha256'] = '0' * 64
    else:
        result['request_binding']['max_internal_increase_kcal_per_mol'] = 99.0
    result['report_sha256'] = digest({k: v for k, v in result.items() if k != 'report_sha256'})
    if change == 'request_cross':
        report['result'] = result
        report['verification']['report_sha256'] = result['report_sha256']
        data = json.dumps(report).encode()
        (out / 'report.json').write_bytes(data)
        completion = json.loads((out / 'complete.json').read_bytes())
        completion['report_sha256'] = hashlib.sha256(data).hexdigest()
        (out / 'complete.json').write_text(json.dumps(completion))
        with pytest.raises(ResearchError):
            workflow.verify_output(out)
    else:
        with pytest.raises(ResearchError):
            verify_report(result)

@pytest.mark.parametrize('change', ['digest', 'frame', 'receptor', 'ligand_parameters', 'absent_cap', 'negative_cap'])
def test_bad_fixed_request_is_not_silently_downgraded(tmp_path, change):
    req = fixed_request_fixture(tmp_path)
    if change == 'digest':
        req['cross_parameters']['sha256'] = '0' * 64
    elif change == 'absent_cap':
        del req['max_internal_increase_kcal_per_mol']
    elif change == 'negative_cap':
        req['max_internal_increase_kcal_per_mol'] = -1.0
    else:
        path = Path(req['cross_parameters']['path'])
        doc = json.loads(path.read_bytes())
        doc[{'frame': 'coordinate_frame_id', 'receptor': 'receptor_system_sha256', 'ligand_parameters': 'ligand_parameter_fingerprint_sha256'}[change]] = 'wrong' if change == 'frame' else '0' * 64
        raw = json.dumps(doc).encode()
        path.write_bytes(raw)
        req['cross_parameters']['sha256'] = hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError):
        workflow.run_request(req, tmp_path / 'out')
    assert not (tmp_path / 'out' / 'complete.json').exists()

def test_fixed_failure_preserves_original_and_actual_work(tmp_path, monkeypatch):
    from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import FixedReceptorEnvironment

    def fail(*args):
        raise FloatingPointError('synthetic cross evaluation failure')
    monkeypatch.setattr(FixedReceptorEnvironment, 'evaluate_cross', fail)
    result = workflow.run_request(fixed_request_fixture(tmp_path), tmp_path / 'out')['result']
    assert result['arms']['refined']['failure_count'] == 2
    assert result['arms']['refined']['failed_force_evaluation_calls'] == 2
    assert all((row['variant'] == 'baseline' for row in result['final_selection']['selected_candidates']))
    assert verify_report(result)['structural_verification_passed'] is True

def test_fixed_input_mutation_prevents_success_publication(tmp_path, monkeypatch):
    req = fixed_request_fixture(tmp_path)
    real = workflow.run_comparison

    def mutate(*args, **kwargs):
        result = real(*args, **kwargs)
        path = Path(req['cross_parameters']['path'])
        path.write_bytes(path.read_bytes() + b'\n')
        return result
    monkeypatch.setattr(workflow, 'run_comparison', mutate)
    with pytest.raises(ResearchError, match='sha256'):
        workflow.run_request(req, tmp_path / 'out')
    assert not (tmp_path / 'out' / 'report.json').exists()

def test_integer_zero_strain_cap_supported_without_silent_float_rewrite(tmp_path):
    req = fixed_request_fixture(tmp_path)
    req['max_internal_increase_kcal_per_mol'] = 0
    workflow.run_request(req, tmp_path / 'out')
    assert workflow.verify_output(tmp_path / 'out')['structural_verification_passed']

def test_fixed_charged_solvated_constrained_request(tmp_path):
    from betelgeuze_engine_v2.physics.reference_forcefield_v2 import DistanceConstraintParameter
    from betelgeuze_engine_v2.physics.reference_solvation import FixedBornPolarSolvationParameters, FixedBornAtomParameter
    req = fixed_request_fixture(tmp_path)
    _, _, ligand = _authority()
    from betelgeuze_product.reference_minimization_workflow import _parameters
    base = _parameters(workflow._bound(req['parameters']))
    parameters = ReferenceForceFieldV2Parameters(base, constraints=(DistanceConstraintParameter(0, 1, 2 ** 0.5, tolerance_angstrom=1e-10),))
    solvent = FixedBornPolarSolvationParameters(parameter_set_id='fixed-ligand-gb', parameter_set_version='1', parameter_source_sha256='d' * 64, topology_sha256=parameters.topology_sha256, charge_parameter_fingerprint_sha256=parameters.fingerprint_sha256, atom_parameters=tuple((FixedBornAtomParameter(i, 1.5) for i in range(ligand.atom_count))))
    for name, doc in (('extensions', parameters.to_dict()), ('solvation', solvent.to_dict())):
        path = tmp_path / (name + '-gb.json')
        raw = json.dumps(doc).encode()
        path.write_bytes(raw)
        req[name] = {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest()}
    req['solver']['force_projection_max_sweeps'] = 200
    report = workflow.run_request(req, tmp_path / 'out')['result']
    assert report['arms']['refined']['failure_count'] == 0
    for a in report['attempts']:
        assert a['max_constraint_residual'] <= 1e-10
        assert a['initial_objective_components']['ligand_polar_solvation'] != 0.0
        assert a['energy_delta'] < 0.0
    assert workflow.verify_output(tmp_path / 'out')['structural_verification_passed']

def test_cross_parameters_on_old_request_schema_rejected(tmp_path):
    req = fixed_request_fixture(tmp_path)
    req['schema_id'] = workflow.REQUEST_SCHEMA
    with pytest.raises(ResearchError):
        workflow.run_request(req, tmp_path / 'out')
