"""Execute only the predeclared four-state SRO arithmetic comparison."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from docs.research.human_5ht6_sro_numerical_preparation.bind_numerical_request import (
    AUDIT_PROTOCOL, checked, publish, read_expected, reference, require, request_reference,
)


def verify_result(report, plan, oracle_ref):
    require(report['audit_source_sha256'] == oracle_ref['sha256'], 'oracle_source_changed')
    require(report['native_source_manifest_sha256'] == plan['native_source_sha256'], 'native_source_changed')
    for key, expected in AUDIT_PROTOCOL.items():
        require(report['protocol'][key] == expected, 'numerical_protocol_changed')
    for key, expected in (
        ('request', plan['request']), ('ligand_XML', plan['inputs']['ligand_xml']),
        ('receptor_XML', plan['inputs']['receptor_xml']),
    ):
        require(report['inputs'][key] == request_reference(expected), 'numerical_input_binding_changed')
    require(report['denominator'] == {'requested': 4, 'evaluated': 4, 'rejected': 0, 'passed': 4},
            'four_state_numerical_audit_failed')
    require([row['snapshot'] for row in report['snapshots']]
            == ['initial', 'perturbation_1', 'perturbation_2', 'perturbation_3'], 'snapshot_coverage_changed')
    require(report['all_same_math_checks_passed'] is True
            and all(row['passed'] is True for row in report['snapshots']), 'same_math_check_failed')
    require(report['ligand_atom_count'] == 26 and report['receptor_atom_count'] == 4376,
            'audit_atom_count_changed')
    require(report['reference_platform'] == 'Reference' and report['intrareceptor_energy_evaluated'] is False,
            'audit_model_changed')


def run(plan_path, output):
    from tools.analysis import openmm_d3_numerical_audit as oracle
    from betelgeuze_product.cpu_refinement_v1_2.provenance import digest, source_manifest
    started = time.perf_counter()
    plan_ref = reference(plan_path)
    raw, _ = read_expected(plan_path, plan_ref)
    plan = json.loads(raw)
    require(plan['schema_id'] == 'sro_same_math_numerical_plan/1.0.0'
            and plan['audit_protocol'] == AUDIT_PROTOCOL, 'frozen_SRO_plan_required')
    sources = source_manifest()
    require(digest(sources) == plan['native_source_sha256'], 'native_source_not_frozen')
    require(oracle.ENERGY_ABSOLUTE_TOLERANCE == 1e-8 and oracle.FORCE_ABSOLUTE_TOLERANCE == 1e-8,
            'oracle_tolerance_changed')
    oracle_ref = reference(oracle.__file__)
    bound = [plan_ref, oracle_ref, reference(__file__), reference(
        Path(__file__).with_name('bind_numerical_request.py')), plan['request'],
        plan['predeclaration'], plan['independent_preparation_verification'],
        plan['initial_product_geometry'], *plan['inputs'].values()]
    request_raw, _ = read_expected(plan['request']['path'], plan['request'])
    request = json.loads(request_raw)
    for key in ('ligand', 'receptor', 'parameters', 'extensions', 'cross_parameters'):
        raw_input, actual = read_expected(request[key]['path'], request[key])
        bound.append(actual)
    for ref in bound:
        checked(ref)
    output = Path(output).absolute()
    output.mkdir(parents=True, exist_ok=False)
    execution_plan = publish(output / 'execution-plan.json', {
        'plan': plan_ref, 'inputs_and_implementation': bound, 'audit_protocol': AUDIT_PROTOCOL,
        'native_source_sha256': plan['native_source_sha256'], 'optimization_or_pose_search': False,
        'source_roles_admitted': False, 'scientifically_validated': False, 'product_qualified': False})
    stage = 'independent_numerical_audit'
    try:
        report = oracle.audit(plan['request']['path'], plan['inputs']['ligand_xml']['path'],
            plan['inputs']['receptor_xml']['path'], perturbations=AUDIT_PROTOCOL['perturbations'],
            seed=AUDIT_PROTOCOL['seed'], perturbation_angstrom=AUDIT_PROTOCOL['perturbation_angstrom'])
        report_ref = publish(output / 'numerical-four-states.json', report)
        stage = 'verify_scope_and_boundaries'
        verify_result(report, plan, oracle_ref)
        for ref in [*bound, report_ref, execution_plan]:
            checked(ref)
        require(source_manifest() == sources, 'native_source_changed')
        summary = {'schema_id': 'sro_numerical_execution/1.0.0', 'execution_plan': execution_plan,
            'audit': report_ref, 'denominator': report['denominator'], 'all_same_math_checks_passed': True,
            'whole_wall_seconds_before_summary_publication': time.perf_counter() - started,
            'cost_excludes': ['upstream_preparation', 'human_work', 'summary_publication'],
            'nested_timings_do_not_sum': True, 'pose_recovery_or_affinity': False,
            'source_roles_admitted': False, 'scientifically_validated': False, 'product_qualified': False}
        publish(output / 'summary.json', summary)
        return summary
    except Exception as exc:
        publish(output / 'failure.json', {'stage': stage, 'type': type(exc).__name__, 'reason': str(exc),
            'elapsed_wall_seconds': time.perf_counter() - started, 'product_qualified': False})
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.plan, args.output), sort_keys=True))
