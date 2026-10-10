"""Explicit same-input comparison with exclusive, failure-inclusive evidence.

No retries, chemical preparation variants, selection, or scientific promotion.
This in-process API requires an external supervisor for hard wall/CPU/disk limits.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

import torch

from betelgeuze_product.comparison_receipts import MAX_JSON_BYTES, _json, _regular_file
from betelgeuze_product.cpu_prepared_cartesian_budget_v3 import workflow as budget
from betelgeuze_product.cpu_refinement_diagnostics_v1 import workflow as retained
from betelgeuze_product.cpu_refinement_diagnostics_v1.contracts import DiagnosticConfig
from betelgeuze_product.cpu_refinement_v1_2.provenance import (
    coordinates_hex, digest, exact_fields, require_digest,
)
from betelgeuze_product.cpu_refinement_v1_3 import minimization as execution
from betelgeuze_product.cpu_refinement_v1_3.kernel import validate_observation
from . import cartesian, diagnostics
from .contracts import ARMS, BASELINE_SCHEMA, BOUNDARY, ComparisonConfig, PLAN_SCHEMA, SCHEMA, require


def _path(value):
    path = Path(value).absolute()
    require('..' not in path.parts, 'comparison path traversal forbidden')
    return path


def _read(path):
    return _json(_regular_file(_path(path), MAX_JSON_BYTES))


def _phase(rows, name, function):
    wall, cpu = time.perf_counter_ns(), time.process_time_ns()
    try:
        value = function()
    except BaseException:
        rows.append({'phase': name, 'status': 'failed', 'wall_ns': time.perf_counter_ns() - wall,
                     'cpu_ns': time.process_time_ns() - cpu})
        raise
    rows.append({'phase': name, 'status': 'completed', 'wall_ns': time.perf_counter_ns() - wall,
                 'cpu_ns': time.process_time_ns() - cpu})
    return value


def _options(config, model):
    return dict(model=model, accepted_steps=config.accepted_steps, restart_verifications=0)


def _loaded(protocol_path, protocol_sha256, model, config):
    protocol, loaded = budget._read(protocol_path, protocol_sha256, **_options(config, model))
    ligand, parameters, solver, fixed, evaluator, identity = loaded
    require(solver.algorithm == 'lbfgs', 'comparison requires explicit L-BFGS prepared protocol')
    reference = cartesian.prepare_reference(ligand, identity['external_binding'])
    return protocol, loaded, reference


def prepare(protocol_path, expected_protocol_sha256, output_dir, *, model, config=ComparisonConfig()):
    """Seal one exact existing P1 preparation; no graph/energy/force work."""
    require(type(config) is ComparisonConfig, 'explicit comparison configuration required')
    phases = []
    protocol, loaded, reference = _phase(phases, 'prepared_input_validation', lambda:
        _loaded(protocol_path, expected_protocol_sha256, model, config))
    receipt = _phase(phases, 'prepared_geometry_validation', lambda:
        budget._preflight(protocol, expected_protocol_sha256, loaded))
    plan = {'schema_id': PLAN_SCHEMA, 'prepared_protocol_path': str(_path(protocol_path)),
            'prepared_protocol_sha256': expected_protocol_sha256, 'model': model,
            'config': config.to_dict(), 'arms': ARMS, 'shape_reference': reference.to_document(),
            'shape_reference_sha256': reference.digest,
            'implementation_sha256': digest(cartesian.implementation_sources(model)),
            'preflight': receipt, 'boundary': BOUNDARY, 'preparation_phase_costs': list(phases),
            'prior_chemical_preparation_cost': {'status': 'unavailable',
                'reason': 'consumes_preexisting_preparation_no_historical_cost_inferred'}}
    with retained._OutputDirectory(_path(output_dir)) as destination:
        _phase(phases, 'plan_storage', lambda: destination.write('plan.json', plan))
        destination.write('preparation-cost.json', {'phases': phases,
            'cost_receipt_write_cost': 'unmeasured_self_publication'})
    path = _path(output_dir) / 'plan.json'
    return {'plan_path': str(path), 'plan_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'preparation_phases': phases}


def _load_plan(path, expected_sha256):
    require_digest(expected_sha256)
    raw = _regular_file(_path(path), MAX_JSON_BYTES)
    require(hashlib.sha256(raw).hexdigest() == expected_sha256, 'comparison plan bytes changed')
    plan = _json(raw)
    exact_fields(plan, {'schema_id', 'prepared_protocol_path', 'prepared_protocol_sha256', 'model',
        'config', 'arms', 'shape_reference', 'shape_reference_sha256', 'implementation_sha256',
        'preflight', 'boundary', 'prior_chemical_preparation_cost', 'preparation_phase_costs'})
    config = ComparisonConfig(accepted_steps=plan['config']['accepted_steps'])
    require(plan['schema_id'] == PLAN_SCHEMA and plan['config'] == config.to_dict()
            and plan['arms'] == ARMS and plan['boundary'] == BOUNDARY, 'comparison controls changed')
    require(plan['implementation_sha256'] == digest(cartesian.implementation_sources(plan['model'])),
            'comparison implementation changed')
    protocol, loaded, reference = _loaded(plan['prepared_protocol_path'],
        plan['prepared_protocol_sha256'], plan['model'], config)
    require(reference.digest == plan['shape_reference_sha256']
            and reference.to_document() == plan['shape_reference'], 'original parent changed')
    require(budget._preflight(protocol, plan['prepared_protocol_sha256'], loaded) == plan['preflight'],
            'prepared preflight changed')
    return plan, config, loaded, reference


def preflight(plan_path, expected_sha256):
    plan, config, _, _ = _load_plan(plan_path, expected_sha256)
    return {'schema_id': SCHEMA, 'status': 'admitted_for_bounded_development_execution',
            'plan_sha256': expected_sha256, 'config': config.to_dict(), 'boundary': plan['boundary']}


def _baseline_binding(plan_sha256, identity):
    return {'schema_id': BASELINE_SCHEMA, 'plan_sha256': plan_sha256,
            'base_binding': identity, 'optimizer_calls': 0}


def evaluate_baseline(ligand, config, evaluator, identity, *, output_dir, plan_sha256):
    """One durable reserved evaluation; never creates a minimizer or optimizer run."""
    binding = _baseline_binding(plan_sha256, identity)
    intent = {'attempt': 1, 'coordinates': coordinates_hex(ligand.coordinates)}
    with retained._OutputDirectory(_path(output_dir)) as destination:
        destination.write('binding.json', binding)
        destination.write('evaluation-started.json', {'binding_sha256': digest(binding), 'intent': intent})
        execution._intact(ligand, evaluator, identity, budget.implementation_sources, evaluator.fixed.assert_intact)
        result = execution._invoke(ligand, evaluator, config, intent)
        execution._intact(ligand, evaluator, identity, budget.implementation_sources, evaluator.fixed.assert_intact)
        # Same work invariants as solver calls, without labeling this optimizer work.
        work, timings = execution._work(config), execution._timings()
        execution._completed_work(result, work, timings, 'optimizer')
        require(result['observation'] is None
                or result['observation']['coordinates'] == intent['coordinates'], 'baseline coordinates changed')
        receipt = {'schema_id': BASELINE_SCHEMA, 'binding_sha256': digest(binding),
                   'status': 'evaluated' if result['observation'] is not None else 'failed',
                   'optimizer_objective_attempts': 0, 'optimizer_force_calls': 0,
                   'evaluation_attempts': 1, 'evaluation_work': result['work'],
                   'evaluation_timings_ns': result['timings_ns'], 'receipt': result}
        receipt['result_sha256'] = digest(receipt)
        destination.write('evaluation-finished.json', receipt)
        return receipt


def verify_baseline(ligand, config, identity, *, output_dir, plan_sha256):
    """Validate retained baseline without computing graph, energies or forces."""
    path = _path(output_dir)
    require(path.is_dir() and not path.is_symlink(), 'regular baseline directory required')
    require({p.name for p in path.iterdir()} == {'binding.json', 'evaluation-started.json',
            'evaluation-finished.json'}, 'unfinished or unexpected baseline work; retry forbidden')
    binding = _baseline_binding(plan_sha256, identity)
    require(_read(path / 'binding.json') == binding, 'baseline binding mismatch')
    require(_read(path / 'evaluation-started.json') == {'binding_sha256': digest(binding),
        'intent': {'attempt': 1, 'coordinates': coordinates_hex(ligand.coordinates)}},
        'baseline reservation mismatch')
    result = _read(path / 'evaluation-finished.json')
    require(result['result_sha256'] == digest({k: v for k, v in result.items() if k != 'result_sha256'}),
            'baseline receipt digest mismatch')
    require(result['schema_id'] == BASELINE_SCHEMA and result['binding_sha256'] == digest(binding)
            and result['optimizer_objective_attempts'] == result['optimizer_force_calls'] == 0
            and result['evaluation_attempts'] == 1, 'baseline accounting mismatch')
    receipt = result['receipt']
    work, timings = execution._work(config), execution._timings()
    execution._completed_work(receipt, work, timings, 'optimizer')
    require(result['evaluation_work'] == receipt['work']
            and result['evaluation_timings_ns'] == receipt['timings_ns']
            and result['status'] == ('evaluated' if receipt['observation'] is not None else 'failed'),
            'baseline evaluation accounting mismatch')
    if receipt['observation'] is not None:
        observation = validate_observation(receipt['observation'], ligand.atom_count)
        require(observation['coordinates'] == coordinates_hex(ligand.coordinates)
                and observation['attempt'] == 1, 'baseline observation changed')
    return result


def _inventory(path):
    rows = {}
    for item in sorted(path.rglob('*')):
        require(not item.is_symlink(), 'symlink in comparison evidence')
        if item.is_file():
            raw = _regular_file(item, 256 * 1024 * 1024)
            rows[str(item.relative_to(path))] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    return rows


def _aggregate(rows):
    optimized = [r for r in rows if r['arm'] != 'B0']
    known = sum((r['work'] or {}).get('optimizer_base_force_calls', 0) for r in optimized)
    known_restart = sum((r['work'] or {}).get('restart_base_force_calls', 0) for r in optimized)
    unknown = sum(r['work'] is None or r['work'].get('actual_force_calls') is None
                  for r in optimized)
    baseline = rows[0]['work']
    baseline_calls = None if baseline is None else baseline['evaluation_work']['force_calls']
    diagnostics_known = {}
    for row in rows:
        for key, value in row.get('diagnostic_work', {}).items():
            diagnostics_known[key] = diagnostics_known.get(key, 0) + value
    return {
        'optimizer_known_completed_base_calls': known,
        'optimizer_actual_base_calls': None if unknown else known,
        'optimizer_arms_with_unknown_work': unknown,
        'restart_known_completed_base_calls': known_restart,
        'baseline_evaluation_base_calls': baseline_calls,
        'all_actual_base_calls_excluding_diagnostics': None if unknown or baseline_calls is None
            else known + known_restart + baseline_calls,
        'optimizer_failed_base_calls': sum((r['work'] or {}).get('optimizer_failed_base_force_calls', 0)
                                           for r in optimized),
        'optimizer_known_shape_calls': sum((r['work'] or {}).get('optimizer_shape_calls', 0)
                                          for r in optimized),
        'optimizer_known_failed_shape_calls': sum((r['work'] or {}).get('optimizer_failed_shape_calls', 0)
                                                 for r in optimized),
        'diagnostic_known_completed_work': diagnostics_known,
        'diagnostic_arms_with_unavailable_or_unknown_work': sum('diagnostic_work' not in r for r in rows),
        'diagnostic_internal_gradient_count': 'not_instrumented',
        'unknown_work_is_not_zero_and_is_not_retried': True,
    }


def run(plan_path, expected_sha256, output_dir):
    """Execute each predeclared arm once; existing output is never retried/resumed.

    Hard resource limits belong to an external process supervisor. Unknown work
    remains unknown even if later arms complete. No failed row is dropped.
    """
    phases = []
    plan, settings, loaded, reference = _phase(phases, 'plan_validation', lambda:
        _load_plan(plan_path, expected_sha256))
    ligand, parameters, config, fixed, evaluator, identity = loaded
    root = _path(output_dir)
    rows = []
    with retained._OutputDirectory(root) as destination:
        destination.write('binding.json', {'schema_id': SCHEMA, 'plan_sha256': expected_sha256,
                                          'arms': ARMS, 'boundary': BOUNDARY})
        for arm, strength in ARMS.items():
            row = {'arm': arm, 'strength': strength, 'status': 'not_started', 'result_sha256': None,
                   'diagnostic_status': 'not_requested', 'work': None, 'error_type': None}
            rows.append(row)
            destination.guard()
            destination.write(arm + '-started.json', {'arm': arm, 'plan_sha256': expected_sha256})
            try:
                _phase(phases, arm + '_input_validation', lambda: _load_plan(plan_path, expected_sha256))
                if arm == 'B0':
                    result = _phase(phases, arm + '_evaluation', lambda: evaluate_baseline(ligand, config,
                        evaluator, identity, output_dir=root / arm, plan_sha256=expected_sha256))
                    _phase(phases, arm + '_verification', lambda: verify_baseline(ligand, config, identity,
                        output_dir=root / arm, plan_sha256=expected_sha256))
                    row['work'] = {k: result[k] for k in ('optimizer_objective_attempts',
                        'optimizer_force_calls', 'evaluation_attempts', 'evaluation_work')}
                    row['diagnostic_status'] = 'not_started'
                else:
                    options = dict(fixed_environment=fixed, run_dir=root / arm,
                        binding=identity['external_binding'], base_profile=plan['model'],
                        reference=reference, strength=strength)
                    result = _phase(phases, arm + '_execution', lambda: cartesian.minimize_shape(
                        ligand, parameters, config, **options))
                    _phase(phases, arm + '_verification', lambda: cartesian.verify_shape(
                        ligand, parameters, config, **options))
                    row['work'] = result['work']
                row.update(status=result['status'], result_sha256=result['result_sha256'])
                if arm == 'B0':
                    try:
                        record = _phase(phases, arm + '_diagnostics', lambda: diagnostics.diagnose_baseline(
                            ligand, evaluator, config, identity, baseline_dir=root / arm,
                            plan_sha256=expected_sha256, output_dir=root / (arm + '-diagnostics')))
                        _phase(phases, arm + '_diagnostic_verification', lambda:
                            diagnostics.verify_baseline_sidecar(ligand, config, identity,
                                baseline_dir=root / arm, plan_sha256=expected_sha256,
                                output_dir=root / (arm + '-diagnostics'),
                                expected_record_sha256=record['record_sha256']))
                        row.update(diagnostic_status=record['status'],
                                   diagnostic_record_sha256=record['record_sha256'],
                                   diagnostic_work=record['work'])
                    except Exception as exc:
                        row.update(diagnostic_status='failed_or_unknown', diagnostic_error_type=type(exc).__name__[:128])
                else:
                    try:
                        sidecar = _phase(phases, arm + '_diagnostics', lambda:
                            diagnostics.diagnose_shape_run(ligand, parameters, config, **options,
                                output_dir=root / (arm + '-diagnostics'), diagnostic_config=DiagnosticConfig(
                                    accepted_stride=settings.diagnostic_stride,
                                    maximum_records=settings.diagnostic_maximum_records)))
                        _phase(phases, arm + '_diagnostic_verification', lambda:
                            diagnostics.verify_shape_sidecar(ligand, parameters, config, **options,
                                output_dir=root / (arm + '-diagnostics'),
                                expected_report_sha256=sidecar['report_sha256']))
                        row.update(diagnostic_status=sidecar['status'],
                                   diagnostic_report_sha256=sidecar['report_sha256'],
                                   diagnostic_work=sidecar['diagnostic_work'])
                    except Exception as exc:
                        row.update(diagnostic_status='failed_or_unknown', diagnostic_error_type=type(exc).__name__[:128])
            except Exception as exc:
                row.update(status='failed_or_unknown', error_type=type(exc).__name__[:128])
                if hasattr(exc, 'work'):
                    row['work'] = dict(exc.work)
            destination.guard()
            destination.write(arm + '-finished.json', row)
        # A changed source invalidates publication even when some arm receipts exist.
        _phase(phases, 'final_input_validation', lambda: _load_plan(plan_path, expected_sha256))
        files = _phase(phases, 'storage_inventory', lambda: _inventory(root))
        report = {'schema_id': SCHEMA, 'plan_sha256': expected_sha256, 'arms': rows,
            'denominator': {'planned': 4, 'attempted': 4,
                            'with_verified_result': sum(r['result_sha256'] is not None for r in rows),
                            'without_verified_result': sum(r['result_sha256'] is None for r in rows)},
            'phase_costs': list(phases), 'preparation_phase_costs': plan['preparation_phase_costs'],
            'files': files, 'work_totals': _aggregate(rows),
            'logical_artifact_bytes_before_report': sum(r['bytes'] for r in files.values()),
            'boundary': BOUNDARY, 'cost_limits': {
                'hard_wall_cpu_disk_limits': 'requires_external_supervisor',
                'process_cpu_excludes_children': True, 'nested_solver_times_do_not_sum': True,
                'historical_preparation': 'unavailable', 'storage_io_bytes': 'not_instrumented',
                'interrupted_phase_costs': 'may_be_unknown',
                'final_completion_receipt_publication': 'unmeasured_self_publication'}}
        report['report_sha256'] = digest(report)
        publication = []
        _phase(publication, 'report_publication', lambda: destination.write('report.json', report))
        completion = {'schema_id': SCHEMA, 'report_sha256': report['report_sha256'],
                      'publication_costs': publication}
        completion['completion_sha256'] = digest(completion)
        destination.write('completion.json', completion)
        return {'report': report, 'completion': completion}


def verify(plan_path, expected_sha256, output_dir, *, expected_completion_sha256):
    """Force-free integrity replay; failed/unknown rows remain explicitly incomplete."""
    plan, _, loaded, reference = _load_plan(plan_path, expected_sha256)
    ligand, parameters, config, fixed, _, identity = loaded
    root = _path(output_dir)
    completion, report = _read(root / 'completion.json'), _read(root / 'report.json')
    require_digest(expected_completion_sha256)
    require(completion['completion_sha256'] == expected_completion_sha256 == digest(
        {k: v for k, v in completion.items() if k != 'completion_sha256'}), 'completion digest mismatch')
    require(report['report_sha256'] == completion['report_sha256'] == digest(
        {k: v for k, v in report.items() if k != 'report_sha256'}), 'report digest mismatch')
    require(report['plan_sha256'] == expected_sha256 and report['schema_id'] == SCHEMA
            and report['boundary'] == BOUNDARY, 'comparison identity mismatch')
    inventory = _inventory(root)
    for name in ('report.json', 'completion.json'):
        inventory.pop(name)
    require(inventory == report['files'], 'comparison artifact inventory mismatch')
    require([row['arm'] for row in report['arms']] == list(ARMS), 'comparison arm denominator changed')
    verified = 0
    for row in report['arms']:
        arm = row['arm']
        require(row['strength'] == ARMS[arm] and _read(root / (arm + '-finished.json')) == row,
                'comparison arm binding changed')
        if row['result_sha256'] is None:
            require(row['status'] == 'failed_or_unknown', 'missing arm result misclassified')
            continue
        if arm == 'B0':
            result = verify_baseline(ligand, config, identity, output_dir=root / arm,
                                     plan_sha256=expected_sha256)
            work = {k: result[k] for k in ('optimizer_objective_attempts', 'optimizer_force_calls',
                                         'evaluation_attempts', 'evaluation_work')}
            if 'diagnostic_record_sha256' in row:
                record = diagnostics.verify_baseline_sidecar(ligand, config, identity,
                    baseline_dir=root / arm, plan_sha256=expected_sha256,
                    output_dir=root / (arm + '-diagnostics'),
                    expected_record_sha256=row['diagnostic_record_sha256'])
                require(record['work'] == row['diagnostic_work']
                        and record['status'] == row['diagnostic_status'], 'baseline diagnostic accounting mismatch')
        else:
            options = dict(fixed_environment=fixed, run_dir=root / arm,
                binding=identity['external_binding'], base_profile=plan['model'],
                reference=reference, strength=ARMS[arm])
            result = cartesian.verify_shape(ligand, parameters, config, **options)
            work = result['work']
            if 'diagnostic_report_sha256' in row:
                sidecar = diagnostics.verify_shape_sidecar(ligand, parameters, config, **options,
                    output_dir=root / (arm + '-diagnostics'),
                    expected_report_sha256=row['diagnostic_report_sha256'])
                require(sidecar['diagnostic_work'] == row['diagnostic_work']
                        and sidecar['status'] == row['diagnostic_status'], 'diagnostic accounting mismatch')
        require(result['result_sha256'] == row['result_sha256'] and result['status'] == row['status']
                and work == row['work'], 'comparison result mismatch')
        verified += 1
    require(report['denominator'] == {'planned': 4, 'attempted': 4,
        'with_verified_result': verified, 'without_verified_result': 4 - verified}, 'denominator mismatch')
    require(report['work_totals'] == _aggregate(report['arms']), 'aggregate work mismatch')
    _load_plan(plan_path, expected_sha256)
    final_inventory = _inventory(root)
    for name in ('report.json', 'completion.json'):
        final_inventory.pop(name)
    require(final_inventory == report['files'], 'comparison artifacts changed during verification')
    require(_read(root / 'completion.json') == completion and _read(root / 'report.json') == report,
            'comparison report changed during verification')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    prepare_parser = commands.add_parser('prepare')
    prepare_parser.add_argument('--protocol', required=True)
    prepare_parser.add_argument('--expected-protocol-sha256', required=True)
    prepare_parser.add_argument('--model', choices=('fourier', 'linear_angle'), required=True)
    prepare_parser.add_argument('--accepted-steps', type=int, choices=(40, 80, 160), required=True)
    prepare_parser.add_argument('--output-dir', required=True)
    for name in ('preflight', 'run', 'verify'):
        command = commands.add_parser(name)
        command.add_argument('--plan', required=True)
        command.add_argument('--expected-plan-sha256', required=True)
        if name != 'preflight':
            command.add_argument('--output-dir', required=True)
        if name == 'verify':
            command.add_argument('--expected-completion-sha256', required=True)
    args = parser.parse_args(argv)
    torch.set_num_threads(1)
    if args.action == 'prepare':
        result = prepare(args.protocol, args.expected_protocol_sha256, args.output_dir,
                         model=args.model, config=ComparisonConfig(args.accepted_steps))
    elif args.action == 'preflight':
        result = preflight(args.plan, args.expected_plan_sha256)
    elif args.action == 'run':
        result = run(args.plan, args.expected_plan_sha256, args.output_dir)
    else:
        result = verify(args.plan, args.expected_plan_sha256, args.output_dir,
                        expected_completion_sha256=args.expected_completion_sha256)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
