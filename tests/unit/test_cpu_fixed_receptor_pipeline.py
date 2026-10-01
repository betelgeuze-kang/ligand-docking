"""Actual authenticated D3 candidates, total/strain admission, files and failures."""
from __future__ import annotations
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from betelgeuze_engine_v2.docking import DockingBudget
from betelgeuze_engine_v2.physics.reference_parameters import AtomNonbondedParameter
from betelgeuze_engine_v2.physics.reference_forcefield_v2 import ReferenceForceFieldV2Parameters
from betelgeuze_engine_v2.molecular import canonical_system_sha256
from betelgeuze_engine_v2.molecular.serialization import canonical_system_json_bytes
from betelgeuze_product.cpu_refinement.reference_minimization_v1_1 import ReferenceMinimizationConfig
from betelgeuze_product.cpu_refinement.refinement_comparison import RefinementComparisonConfig
from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import FixedReceptorEnvironment, FIXED_REPORT_SCHEMA, FIXED_REQUEST_SCHEMA
from betelgeuze_product.cpu_refinement_v1_2.minimization import SolverConfig
from betelgeuze_product.cpu_refinement_v1_2.comparison import run_comparison, choose_variant
from betelgeuze_product.cpu_refinement_v1_2.selection import refinement_admissible
from betelgeuze_product.cpu_refinement_v1_2.verification import verify_report
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError, digest
from betelgeuze_product.cpu_refinement_v1_2.workflow import run_request, verify_output
from tests.unit.test_engine_v2_energy_local_refinement_stage6 import _authority, _parameters
from tests.unit.test_cpu_fixed_receptor import environment
from tests.unit.test_refinement_comparison_workflow import request_fixture as old_fixture

def fixture():
    authority, receptor, ligand = _authority()
    base = _parameters(ligand)
    base = replace(base, atom_parameters=tuple((AtomNonbondedParameter(i, 1.0, 0.01, float(a.partial_charge_e)) for i, a in enumerate(ligand.atoms))), excluded_pairs=tuple(((i, j) for i in range(ligand.atom_count) for j in range(i + 1, ligand.atom_count))))
    params = ReferenceForceFieldV2Parameters(base)
    env = environment(receptor, ligand, base, epsilon=0.01)
    env = FixedReceptorEnvironment(receptor, replace(env.cross, coordinate_frame_id=authority.pocket.coordinate_frame_id))
    solver = SolverConfig(ReferenceMinimizationConfig(max_iterations=3))
    budget = DockingBudget(candidate_count=4, top_k=2, max_torsions=1, max_refinement_steps=3, seed=1301)
    return (authority, receptor, ligand, params, env, solver, budget)

def real_run(equal=False):
    a, r, ligand, p, e, s, b = fixture()
    comp = RefinementComparisonConfig()
    if equal:
        s = replace(s, minimization=replace(s.minimization, max_backtracks=0))
        b = replace(b, candidate_count=12, max_refinement_steps=2)
        comp = RefinementComparisonConfig(mode='equal_work_budget', work_units_per_arm=8)
    result = run_comparison(a, b, receptor_system=r, ligand_system=ligand, parameters=p, solver=s, fixed_environment=e, comparison=comp)
    return result

@pytest.mark.parametrize('equal', [False, True])
def test_real_pipeline_uses_fixed_environment_and_verifies_totals(equal):
    report = real_run(equal)
    assert report['schema_id'] == FIXED_REPORT_SCHEMA
    assert report['receptor_ligand_interaction_energy_minimized'] is True
    assert report['arms']['refined']['failure_count'] == 0
    assert verify_report(report)['structural_verification_passed']
    attempts = report['attempts']
    assert any((a['pre_coordinates_sha256'] != a['post_coordinates_sha256'] for a in attempts))
    for a in attempts:
        assert a['final_energy'] <= a['initial_energy']
        assert a['energy_basis'] == 'ligand_internal_plus_cross_lj_plus_cross_screened_coulomb'
        for field in ['initial_components', 'final_components']:
            v = a[field]
            assert v['total'] == pytest.approx(v['ligand_internal'] + v['cross_lennard_jones'] + v['cross_screened_coulomb'], abs=1e-12)
    if equal:
        assert report['final_selection'] is None
        assert report['arms']['baseline']['candidate_count'] == 8
        assert report['arms']['refined']['candidate_count'] == 2
    else:
        assert len(report['final_selection']['selected_candidates']) <= 2

def test_total_improvement_and_internal_strain_are_separate():
    before = {'succeeded': True, 'selection_eligible': True, 'score': 2.0}
    after = {'succeeded': True, 'selection_eligible': True, 'score': 1.0}
    attempt = {'status': 'success', 'converged': True, 'energy_delta': -2.0, 'initial_components': {'ligand_internal': 0.0}, 'final_components': {'ligand_internal': 1.0}, 'max_internal_increase_kcal_per_mol': 2.0}
    assert choose_variant(before, after, attempt, True) == ('refined', 'valid_refinement_selected')
    attempt['max_internal_increase_kcal_per_mol'] = 0.5
    assert choose_variant(before, after, attempt, True) == ('baseline', 'ligand_internal_strain_limit_exceeded')
    assert not refinement_admissible(after, attempt, True)

@pytest.mark.parametrize('field', ['components', 'cross_parameters', 'receptor_identity', 'strain', 'policy', 'semantics'])
def test_rehashed_fixed_record_inconsistencies_reject(field):
    report = real_run()
    if field == 'components':
        report['attempts'][0]['final_components']['cross_lennard_jones'] += 1
    elif field == 'cross_parameters':
        report['cross_parameters']['dielectric'] += 1
    elif field == 'receptor_identity':
        report['evaluator']['receptor_system_sha256'] = '0' * 64
    elif field == 'strain':
        report['attempts'][0]['max_internal_increase_kcal_per_mol'] = 100.0
    elif field == 'policy':
        report['selection_policy_id'] = 'legacy'
    else:
        report['attempts'][0]['energy_basis'] = 'binding_free_energy'
    for a in report['attempts']:
        a['receipt_sha256'] = digest({k: v for k, v in a.items() if k != 'receipt_sha256'})
    report['report_sha256'] = digest({k: v for k, v in report.items() if k != 'report_sha256'})
    with pytest.raises(ResearchError):
        verify_report(report)

def test_cross_failure_retains_baseline_and_failure_counts(monkeypatch):
    from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import ReferencePhysicsApplicabilityError

    def fail(*args):
        raise ReferencePhysicsApplicabilityError('private synthetic cross failure')
    monkeypatch.setattr(FixedReceptorEnvironment, 'evaluate_cross', fail)
    report = real_run()
    assert report['arms']['refined']['failure_count'] == 4
    assert report['arms']['refined']['failed_force_evaluation_calls'] == 4
    assert all((a['status'] == 'failure' for a in report['attempts']))
    assert verify_report(report)['structural_verification_passed']
    assert 'private synthetic' not in str(report)

def test_receptor_mismatch_rejected_before_execution():
    a, r, ligand, p, e, s, b = fixture()
    rr = r.with_coordinates(r.coordinates + 0.1, operation='another-receptor')
    wrong = FixedReceptorEnvironment(rr, replace(e.cross, receptor_system_sha256=canonical_system_sha256(rr)))
    with pytest.raises(ResearchError, match='docking receptor'):
        run_comparison(a, b, receptor_system=r, ligand_system=ligand, parameters=p, solver=s, fixed_environment=wrong)
    wrong = FixedReceptorEnvironment(r, replace(e.cross, coordinate_frame_id='different'))
    with pytest.raises(ResearchError, match='coordinate frame'):
        run_comparison(a, b, receptor_system=r, ligand_system=ligand, parameters=p, solver=s, fixed_environment=wrong)

def request_fixture(path):
    a, r, ligand, p, e, s, b = fixture()
    old = old_fixture(path)
    doc = {k: v for k, v in old.items() if k not in {'minimization', 'schema_id'}}
    e = FixedReceptorEnvironment(r, replace(e.cross, coordinate_frame_id=doc['pocket']['coordinate_frame_id']))
    doc.update(schema_id=FIXED_REQUEST_SCHEMA, solver=s.to_dict(), solvation=None, selection={'top_k': b.top_k, 'diversity_rmsd_angstrom': 0.5, 'metric': 'direct_rmsd_in_receptor_frame', 'exact_coordinate_deduplication': True}, budget=b.to_dict())
    contents = {'receptor': canonical_system_json_bytes(r), 'ligand': canonical_system_json_bytes(ligand), 'parameters': json.dumps(p.base_parameters.to_dict()).encode(), 'extensions': json.dumps(p.to_dict()).encode(), 'cross_parameters': json.dumps(e.cross.to_dict()).encode()}
    for name, data in contents.items():
        file = path / (name + '-fixed.json')
        file.write_bytes(data)
        doc[name] = {'path': str(file.absolute()), 'sha256': hashlib.sha256(data).hexdigest()}
    return doc

def test_actual_cli_and_readonly_fixed_result(tmp_path):
    request = request_fixture(tmp_path)
    path = tmp_path / 'input.json'
    path.write_text(json.dumps(request))
    out = tmp_path / 'run'
    result = subprocess.run([sys.executable, '-m', 'betelgeuze_product.cpu_refinement_v1_2', 'run', str(path), '--output', str(out)], cwd=tmp_path, env={**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[2])}, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    report = json.loads((out / 'report.json').read_bytes())
    assert report['result']['arms']['refined']['failure_count'] == 0
    original = {p.name: p.read_bytes() for p in out.iterdir() if p.is_file()}
    assert verify_output(out)['structural_verification_passed']
    assert original == {p.name: p.read_bytes() for p in out.iterdir() if p.is_file()}
    with pytest.raises(FileExistsError):
        run_request(request, out)

def test_changed_cross_file_cannot_publish_success(tmp_path, monkeypatch):
    from betelgeuze_product.cpu_refinement_v1_2 import workflow
    request = request_fixture(tmp_path)
    old = workflow.run_comparison

    def mutate(*args, **kwargs):
        result = old(*args, **kwargs)
        with Path(request['cross_parameters']['path']).open('ab') as stream:
            stream.write(b'\n')
        return result
    monkeypatch.setattr(workflow, 'run_comparison', mutate)
    with pytest.raises(ResearchError, match='sha256'):
        run_request(request, tmp_path / 'run')
    assert not (tmp_path / 'run' / 'complete.json').exists()

def test_request_cross_binding_mismatch_rejected_after_rehash(tmp_path):
    request = request_fixture(tmp_path)
    out = tmp_path / 'run'
    run_request(request, out)
    request['cross_parameters']['sha256'] = '0' * 64
    (out / 'request.json').write_text(json.dumps(request))
    report = json.loads((out / 'report.json').read_bytes())
    report['request_sha256'] = digest(request)
    data = json.dumps(report).encode()
    (out / 'report.json').write_bytes(data)
    done = json.loads((out / 'complete.json').read_bytes())
    done['report_sha256'] = hashlib.sha256(data).hexdigest()
    (out / 'complete.json').write_text(json.dumps(done))
    with pytest.raises(ResearchError, match='binding'):
        verify_output(out)
