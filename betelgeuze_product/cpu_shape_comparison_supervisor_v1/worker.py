"""One requested arm, without retries or resource-limit policy.

The process supervisor owns isolation, limits, and return-receipt publication.
This worker preserves the frozen P3 source binding and separates diagnostic work.
"""
import hashlib
import os
from pathlib import Path

import torch

from betelgeuze_product.comparison_receipts import _regular_file

from betelgeuze_product.cpu_prepared_shape_comparison_v1 import cartesian, diagnostics
from betelgeuze_product.cpu_prepared_shape_comparison_v1 import workflow as comparison
from betelgeuze_product.cpu_prepared_shape_comparison_v1.contracts import ARMS, BOUNDARY, require
from betelgeuze_product.cpu_refinement_diagnostics_v1.contracts import DiagnosticConfig
from betelgeuze_product.cpu_refinement_v1_2.provenance import digest, exact_fields, require_digest
from betelgeuze_product.cpu_refinement_v1_3.minimization import PendingWorkError

SCHEMA = 'cpu_shape_comparison_supervised_arm/1.0.0'


def _worker_digest():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _load(plan_path, plan_sha256, arm):
    require(type(arm) is str and arm in ARMS, 'explicit supported comparison arm required')
    torch.set_num_threads(1)
    plan, settings, loaded, reference = comparison._load_plan(plan_path, plan_sha256)
    require(settings.accepted_steps == 40 and settings.restart_verifications == 0,
            'supervised worker requires frozen 40-step zero-restart tier')
    require(loaded[2].max_accepted_steps == 40 and loaded[2].max_restart_verifications == 0,
            'supervised solver limits differ from frozen tier')
    return plan, settings, loaded, reference


def _root(output_dir):
    root = comparison._path(output_dir)
    require(root.is_dir() and not root.is_symlink(), 'existing private worker directory required')
    for parent in root.parents:
        require(not parent.is_symlink(), 'symlink worker ancestor forbidden')
    return root


def _artifacts(root):
    """Bounded inventory of worker-owned files, excluding supervisor control files."""
    artifacts, pending, entries = {}, [], 0
    for name in ('run', 'diagnostics'):
        directory = root / name
        require(not directory.is_symlink(), 'symlink worker artifact forbidden')
        if directory.exists():
            require(directory.is_dir(), 'worker artifact directory required')
            pending.append(directory)
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as iterator:
            for item in iterator:
                entries += 1
                require(entries <= 256, 'worker artifact inventory capacity exceeded')
                require(not item.is_symlink(), 'symlink worker artifact forbidden')
                path = Path(item.path)
                if item.is_dir(follow_symlinks=False):
                    pending.append(path)
                else:
                    require(item.is_file(follow_symlinks=False), 'nonregular worker artifact')
                    # Read ceiling supports the largest explicit supervisor policy.
                    # The source-bound outer inventory/kernel still enforce the
                    # selected per-worker cap, including the unchanged 2 MiB default.
                    raw = _regular_file(path, 8 * 1024 * 1024)
                    artifacts[path.relative_to(root).as_posix()] = {
                        'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    return dict(sorted(artifacts.items()))


def _options(plan, loaded, reference, root, arm):
    return dict(fixed_environment=loaded[3], run_dir=root / 'run',
                binding=loaded[5]['external_binding'], base_profile=plan['model'],
                reference=reference, strength=ARMS[arm])


def _verify_result(plan, loaded, reference, root, arm, plan_sha256):
    ligand, parameters, config, _, _, identity = loaded
    if arm == 'B0':
        return comparison.verify_baseline(ligand, config, identity,
            output_dir=root / 'run', plan_sha256=plan_sha256)
    return cartesian.verify_shape(ligand, parameters, config,
                                 **_options(plan, loaded, reference, root, arm))


def _work(result, arm):
    if arm == 'B0':
        return {key: result[key] for key in ('optimizer_objective_attempts',
                'optimizer_force_calls', 'evaluation_attempts', 'evaluation_work')}
    return result['work']


def _verify_diagnostic(plan, loaded, reference, root, arm, plan_sha256, row):
    ligand, parameters, config, _, _, identity = loaded
    if arm == 'B0':
        record = diagnostics.verify_baseline_sidecar(ligand, config, identity,
            baseline_dir=root / 'run', plan_sha256=plan_sha256,
            output_dir=root / 'diagnostics',
            expected_record_sha256=row['diagnostic_record_sha256'])
        return record['status'], record['work']
    report = diagnostics.verify_shape_sidecar(ligand, parameters, config,
        **_options(plan, loaded, reference, root, arm), output_dir=root / 'diagnostics',
        expected_report_sha256=row['diagnostic_report_sha256'])
    return report['status'], report['diagnostic_work']


def execute_arm(plan_path, plan_sha256, arm, output_dir):
    """Execute one new arm; interrupted processes are classified by the supervisor.

    An ordinary exception yields explicit failed/unknown state. BaseException
    interruptions propagate, preserving the durable reservations for inspection.
    """
    phases = []
    plan, settings, loaded, reference = comparison._phase(phases, 'plan_validation',
        lambda: _load(plan_path, plan_sha256, arm))
    root = _root(output_dir)
    require(not (root / 'run').exists() and not (root / 'run').is_symlink()
            and not (root / 'diagnostics').exists() and not (root / 'diagnostics').is_symlink(),
            'existing arm output cannot be retried')
    ligand, parameters, config, _, evaluator, identity = loaded
    row = {'schema_id': SCHEMA, 'arm': arm, 'strength': ARMS[arm],
           'plan_sha256': plan_sha256,
           'prepared_protocol_sha256': plan['prepared_protocol_sha256'],
           'source_implementation_sha256': plan['implementation_sha256'],
           'worker_sha256': _worker_digest(), 'boundary': dict(BOUNDARY),
           'status': 'failed_or_unknown', 'result_sha256': None,
           'work': None, 'error_type': None, 'diagnostic_status': 'not_started',
           'diagnostic_error_type': None, 'phase_costs': phases}
    try:
        if arm == 'B0':
            result = comparison._phase(phases, 'baseline_evaluation', lambda:
                comparison.evaluate_baseline(ligand, config, evaluator, identity,
                    output_dir=root / 'run', plan_sha256=plan_sha256))
        else:
            result = comparison._phase(phases, 'optimization', lambda:
                cartesian.minimize_shape(ligand, parameters, config,
                    **_options(plan, loaded, reference, root, arm)))
        checked = comparison._phase(phases, 'result_verification', lambda:
            _verify_result(plan, loaded, reference, root, arm, plan_sha256))
        require(checked == result, 'worker result changed during verification')
        row.update(status=result['status'], result_sha256=result['result_sha256'],
                   work=_work(result, arm))
    except Exception as exc:
        row['error_type'] = type(exc).__name__[:128]
        if hasattr(exc, 'work'):
            row['work'] = dict(exc.work)
        if arm != 'B0' and (root / 'run').is_dir():
            # Read-only recovery of an interrupted reservation's known lower bound.
            try:
                comparison._phase(phases, 'failed_result_inspection', lambda:
                    _verify_result(plan, loaded, reference, root, arm, plan_sha256))
            except PendingWorkError as pending:
                row['work'] = dict(pending.work)
            except Exception:
                pass
    if row['result_sha256'] is not None:
        try:
            if arm == 'B0':
                sidecar = comparison._phase(phases, 'diagnostics', lambda:
                    diagnostics.diagnose_baseline(ligand, evaluator, config, identity,
                        baseline_dir=root / 'run', plan_sha256=plan_sha256,
                        output_dir=root / 'diagnostics'))
                key, sha256, work = 'diagnostic_record_sha256', sidecar['record_sha256'], sidecar['work']
            else:
                sidecar = comparison._phase(phases, 'diagnostics', lambda:
                    diagnostics.diagnose_shape_run(ligand, parameters, config,
                        **_options(plan, loaded, reference, root, arm),
                        output_dir=root / 'diagnostics', diagnostic_config=DiagnosticConfig(
                            accepted_stride=settings.diagnostic_stride,
                            maximum_records=settings.diagnostic_maximum_records)))
                key, sha256, work = ('diagnostic_report_sha256', sidecar['report_sha256'],
                                    sidecar['diagnostic_work'])
            status, verified_work = comparison._phase(phases, 'diagnostic_verification', lambda:
                _verify_diagnostic(plan, loaded, reference, root, arm, plan_sha256, {key: sha256}))
            require(status == sidecar['status'] and verified_work == work,
                    'worker diagnostic changed during verification')
            row.update({key: sha256, 'diagnostic_status': status, 'diagnostic_work': work})
        except Exception as exc:
            row.update(diagnostic_status='failed_or_unknown',
                       diagnostic_error_type=type(exc).__name__[:128])
    comparison._phase(phases, 'final_source_validation', lambda: _load(plan_path, plan_sha256, arm))
    require(_worker_digest() == row['worker_sha256'], 'worker implementation changed')
    row['artifacts'] = comparison._phase(phases, 'artifact_inventory', lambda: _artifacts(root))
    row['row_sha256'] = digest(row)
    return row


def verify_arm(plan_path, plan_sha256, arm, output_dir, row):
    """Read-only validation; a retained failed/unknown row stays incomplete."""
    plan, _, loaded, reference = _load(plan_path, plan_sha256, arm)
    root = _root(output_dir)
    required = {'schema_id', 'arm', 'strength', 'plan_sha256', 'prepared_protocol_sha256',
                'source_implementation_sha256', 'worker_sha256', 'boundary', 'status',
                'result_sha256', 'work', 'error_type', 'diagnostic_status', 'diagnostic_error_type',
                'phase_costs', 'artifacts', 'row_sha256'}
    optional = {'diagnostic_work', 'diagnostic_record_sha256', 'diagnostic_report_sha256'}
    exact_fields(row, required | (set(row) & optional))
    require_digest(row['row_sha256'])
    require(row['row_sha256'] == digest({k: v for k, v in row.items() if k != 'row_sha256'}),
            'worker row digest mismatch')
    require(row['schema_id'] == SCHEMA and row['arm'] == arm and row['strength'] == ARMS[arm]
            and row['plan_sha256'] == plan_sha256
            and row['prepared_protocol_sha256'] == plan['prepared_protocol_sha256']
            and row['source_implementation_sha256'] == plan['implementation_sha256']
            and row['worker_sha256'] == _worker_digest() and row['boundary'] == BOUNDARY,
            'worker source or arm identity mismatch')
    require(row['artifacts'] == _artifacts(root), 'worker artifact inventory changed')
    if row['result_sha256'] is None:
        require(row['status'] == 'failed_or_unknown' and row['error_type'] is not None
                and row['diagnostic_status'] == 'not_started'
                and not (set(row) & optional), 'unknown worker result misclassified')
        if row['work'] is not None:
            try:
                _verify_result(plan, loaded, reference, root, arm, plan_sha256)
            except PendingWorkError as pending:
                require(row['work'] == pending.work, 'unknown worker lower bound changed')
            else:
                require(False, 'unknown worker work lacks pending reservation')
    else:
        result = _verify_result(plan, loaded, reference, root, arm, plan_sha256)
        require(row['result_sha256'] == result['result_sha256'] and row['status'] == result['status']
                and row['work'] == _work(result, arm) and row['error_type'] is None,
                'worker result accounting changed')
        diagnostic_key = 'diagnostic_record_sha256' if arm == 'B0' else 'diagnostic_report_sha256'
        if diagnostic_key in row:
            require(set(row) & optional == {diagnostic_key, 'diagnostic_work'}
                    and row['diagnostic_error_type'] is None, 'worker diagnostic fields changed')
            status, work = _verify_diagnostic(plan, loaded, reference, root, arm, plan_sha256, row)
            require(row['diagnostic_status'] == status and row['diagnostic_work'] == work,
                    'worker diagnostic accounting changed')
        else:
            require(row['diagnostic_status'] == 'failed_or_unknown'
                    and row['diagnostic_error_type'] is not None and not (set(row) & optional),
                    'missing worker diagnostics misclassified')
    _load(plan_path, plan_sha256, arm)
    require(row['artifacts'] == _artifacts(root), 'worker artifacts changed during verification')
    return row
