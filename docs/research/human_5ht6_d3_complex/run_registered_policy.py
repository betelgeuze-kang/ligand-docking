"""Execute the frozen PR49 registered-pose policy and retain its actual evidence.

This consumes existing preparations. Its measured scopes do not include their
historical preparation or human work, and it never admits scientific claims.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time

from betelgeuze_product.reference_minimization_workflow import _bound
from betelgeuze_product.cpu_refinement_v1_2.provenance import digest, source_manifest
from betelgeuze_product.cpu_refinement_v1_2.scoring_profile import EXPLICIT_REQUEST_SCHEMA, REGISTERED_REQUEST_SCHEMA
from betelgeuze_product.cpu_refinement_v1_2.workflow import run_request, verify_output
from tools.analysis import openmm_d3_numerical_audit as oracle


def reference(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return {'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def write(path, document):
    with path.open('x') as stream:
        json.dump(document, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')


def run(source_request, ligand_xml, receptor_xml, output, expected_source_sha256):
    start = time.perf_counter()
    paths = [Path(p).resolve() for p in (source_request, ligand_xml, receptor_xml, output)]
    source_request, ligand_xml, receptor_xml, output = paths
    sources = source_manifest()
    if digest(sources) != expected_source_sha256:
        raise ValueError('frozen implementation mismatch')
    source_refs = {name: reference(path) for name, path in (
        ('source_request', source_request), ('ligand_xml', ligand_xml), ('receptor_xml', receptor_xml),
        ('runner', __file__), ('oracle', oracle.__file__))}
    request = json.loads(source_request.read_bytes())
    if request['schema_id'] != EXPLICIT_REQUEST_SCHEMA:
        raise ValueError('original explicit-chemistry development request required')
    for name in ('receptor', 'ligand', 'parameters', 'extensions', 'cross_parameters'):
        _bound(request[name])
    if (request['budget']['max_refinement_steps'] != 32
            or request['solver']['minimization']['max_iterations'] != 32
            or request['solver']['minimization']['force_tolerance_kcal_per_mol_angstrom'] != .001
            or _bound(request['cross_parameters'])['max_internal_increase_kcal_per_mol'] != 5.):
        raise ValueError('frozen D3 limits changed')
    original = deepcopy(request)
    request['schema_id'] = REGISTERED_REQUEST_SCHEMA
    request['budget'].update(candidate_count=1, top_k=1, max_torsions=0, translation_radius_angstrom=0.)
    request['selection']['top_k'] = 1
    if request['comparison']['mode'] != 'same_candidates':
        raise ValueError('same-candidate comparison required')
    output.mkdir(parents=True, exist_ok=False)
    write(output / 'request.json', request)
    plan = {'schema_id': 'pr49_registered_pose_policy_execution_plan/1.0.0',
        'sources': source_refs, 'implementation_source_sha256': expected_source_sha256,
        'request': reference(output / 'request.json'),
        'changed_fields': ['schema_id', 'budget.candidate_count', 'budget.top_k',
                           'budget.max_torsions', 'budget.translation_radius_angstrom', 'selection.top_k'],
        'old_budget': original['budget'], 'new_budget': request['budget'],
        'parameter_state_coordinates_solver_admission_criteria_unchanged': True,
        'numerical_audit_absolute_energy_and_force_tolerance': 1e-8,
        'timing_scope': 'existing prepared inputs through continuous product publication and separate audit',
        'upstream_preparation_and_human_time_included': False,
        'observed_PR49_pose': False, 'scientifically_validated': False}
    write(output / 'plan.json', plan)
    phases = {'request_preparation': time.perf_counter() - start}

    def intact():
        if source_manifest() != sources:
            raise ValueError('implementation changed during execution')
        for ref in source_refs.values():
            if reference(ref['path']) != ref:
                raise ValueError('research source/input changed during execution')
        for name in ('receptor', 'ligand', 'parameters', 'extensions', 'cross_parameters'):
            _bound(request[name])

    stage = 'continuous_product'
    try:
        begun = time.perf_counter()
        product = run_request(request, output / 'continuous')
        phases[stage] = time.perf_counter() - begun
        stage = 'portable_verification'
        begun = time.perf_counter()
        verification = verify_output(output / 'continuous')
        phases[stage] = time.perf_counter() - begun
        result = product['result']
        initial = result['proposal_policy']['initial_coordinates_binary64_hex']
        baseline, refined = (result['arms'][name]['rows'][0] for name in ('baseline', 'refined'))
        attempt = result['attempts'][0]
        if baseline['coordinates_binary64_hex'] != initial or attempt['pre_coordinates_binary64_hex'] != initial:
            raise ValueError('registered coordinates changed before scoring/refinement')
        write(output / 'final-coordinates.json', {'coordinates_angstrom':
            [[float.fromhex(value) for value in row] for row in attempt['post_coordinates_binary64_hex']]})
        stage = 'independent_numerical_audit'
        begun = time.perf_counter()
        audit = oracle.audit(output / 'request.json', ligand_xml, receptor_xml,
                             final_coordinates_path=output / 'final-coordinates.json', perturbations=0)
        phases[stage] = time.perf_counter() - begun
        write(output / 'numerical-initial-final.json', audit)
        if (audit['audit_source_sha256'] != source_refs['oracle']['sha256']
                or audit['native_source_manifest_sha256'] != expected_source_sha256
                or audit['protocol']['absolute_energy_tolerance_kcal_per_mol'] != 1e-8
                or audit['protocol']['absolute_force_component_tolerance_kcal_per_mol_angstrom'] != 1e-8
                or not audit['all_same_math_checks_passed']):
            raise ValueError('frozen independent numerical criteria failed')
        intact()
        report = {'schema_id': 'pr49_registered_pose_policy_execution/1.0.0',
            'plan': reference(output / 'plan.json'), 'implementation_source_sha256': expected_source_sha256,
            'continuous_product_report': reference(output / 'continuous/report.json'),
            'verification': verification, 'initial_coordinates_preserved': True,
            'requested_candidates': 1, 'score_rows': 2,
            'score_success_count': int(baseline['succeeded']) + int(refined['succeeded']),
            'baseline_valid': baseline['selection_eligible'], 'refined_valid': refined['selection_eligible'],
            'paired_decisions': result['paired_decisions'], 'final_selection': result['final_selection'],
            'native_converged': attempt['converged'],
            'internal_increase_kcal_mol': attempt['final_components']['ligand_internal'] - attempt['initial_components']['ligand_internal'],
            'force_calls': result['arms']['refined']['actual_force_evaluation_calls'],
            'numerical_denominator': audit['denominator'], 'phase_wall_seconds': phases,
            'whole_wall_seconds_before_report_publication': time.perf_counter() - start,
            'phase_timings_are_inclusive_do_not_sum_with_whole': True,
            'upstream_preparation_and_human_time_included': False,
            'observed_PR49_pose': False, 'scientifically_validated': False, 'product_qualified': False}
        write(output / 'report.json', report)
        return {k: report[k] for k in ('initial_coordinates_preserved', 'baseline_valid', 'refined_valid',
                                      'native_converged', 'internal_increase_kcal_mol', 'force_calls', 'paired_decisions')}
    except Exception as exc:
        write(output / 'failure.json', {'stage': stage, 'reason': str(exc), 'type': type(exc).__name__,
            'completed_phase_wall_seconds': phases, 'elapsed_wall_seconds': time.perf_counter() - start,
            'scientifically_validated': False})
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('source-request', 'ligand-xml', 'receptor-xml', 'output'):
        parser.add_argument('--' + key, required=True, type=Path)
    parser.add_argument('--expected-source-sha256', required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.source_request, args.ligand_xml, args.receptor_xml, args.output,
                         args.expected_source_sha256), sort_keys=True))
