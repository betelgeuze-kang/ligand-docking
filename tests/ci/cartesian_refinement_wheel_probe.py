"""Exercise installed Cartesian CLI continuation on one tiny synthetic water.

Preparation uses checkout fixture builders without evaluating forces or scores.
Execution must run outside the checkout with -I -B and explicitly declared
installed product and shared dependency roots. Reusing dependencies is not a
fresh dependency installation or scientific validation.
"""
from __future__ import annotations

import argparse
import base64
import datetime
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import sysconfig
import time
import traceback


SCHEMA = 'cartesian_refinement_installed_wheel_probe/1.3.0'
PACKAGE_ROOTS = {'api', 'core', 'betelgeuze_engine', 'betelgeuze_engine_v2',
                 'betelgeuze_ai_md', 'betelgeuze_product', 'betelgeuze_cameo',
                 'betelgeuze_cleanup'}


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _read(path):
    return json.loads(path.read_bytes())


def _write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def _require(condition, message):
    if not condition:
        raise AssertionError(message)


def prepare(root):
    from betelgeuze_product.cpu_refinement_v1_3.contracts import SolverConfig, source_manifest
    from betelgeuze_product.cpu_refinement_v1_3.workflow import prepare_cartesian_request
    from tests.unit.test_cpu_registered_pose_workflow import request_fixture

    root.mkdir(parents=True, exist_ok=False)
    (root / 'synthetic-input').mkdir()
    old, _ = request_fixture(root / 'synthetic-input', strained=True)
    config = SolverConfig(max_objective_attempts=30, max_accepted_steps=20)
    request = prepare_cartesian_request(old, config)
    _write(root / 'original-registered-request.json', old)
    _write(root / 'request.json', request)
    script = Path(__file__).resolve()
    (root / script.name).write_bytes(script.read_bytes())
    _write(root / 'preparation.json', {
        'schema_id': SCHEMA, 'source_checkout': str(script.parents[2]),
        'request_sha256': _sha((root / 'request.json').read_bytes()),
        'original_request_sha256': _sha((root / 'original-registered-request.json').read_bytes()),
        'probe_sha256': _sha(script.read_bytes()), 'implementation_sources': source_manifest(),
        'input_files': {key: request[key] for key in ('receptor', 'ligand', 'parameters',
                                                   'extensions', 'cross_parameters')},
        'solver': config.to_dict(), 'pause_after_objective_attempts': 2,
        'fixture': 'translated_water_with_0.08_angstrom_single_bond_strain',
        'fixture_force_evaluations': 0, 'fixture_score_evaluations': 0,
        'synthetic_inputs_only': True, 'scientifically_validated': False})


def _pins(preparation):
    for name, ref in preparation['input_files'].items():
        _require(_sha(Path(ref['path']).read_bytes()) == ref['sha256'], 'input changed: ' + name)


def _ownership(installed_root, shared_root, prepared_sources):
    import betelgeuze_product
    from betelgeuze_product.cpu_refinement_v1_3 import workflow  # Load the public dependency closure.
    from betelgeuze_product.cpu_refinement_v1_3.contracts import source_manifest

    _require(workflow.REQUEST_SCHEMA.endswith('/1.3.0'), 'unexpected installed workflow schema')
    installed = Path(sysconfig.get_paths()['purelib']).resolve()
    _require(installed.is_relative_to(installed_root), 'purelib is outside installed product root')
    _require(Path(betelgeuze_product.__file__).resolve().is_relative_to(installed),
             'product imported outside new installation')
    _require(source_manifest() == prepared_sources, 'installed source closure differs from preparation')
    owners = [dist for dist in importlib.metadata.distributions(path=[str(installed)])
              if dist.metadata['Name'].lower().replace('_', '-') == 'betelgeuze-md-product']
    _require(len(owners) == 1, 'exactly one new product distribution required')
    owner = owners[0]
    records = {str(path): path for path in owner.files or ()}
    owned = {}
    for name, record in records.items():
        if Path(name).parts[0] not in PACKAGE_ROOTS or name.endswith('.pyc'):
            continue
        path = Path(owner.locate_file(record)).resolve()
        _require(path.is_relative_to(installed), 'product RECORD escapes installed site')
        raw = path.read_bytes()
        expected = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).decode().rstrip('=')
        _require(record.hash is not None and record.hash.mode == 'sha256'
                 and record.hash.value == expected and record.size == len(raw),
                 'product RECORD content mismatch: ' + name)
        owned[name] = _sha(raw)
    for name, sha in prepared_sources.items():
        _require(owned.get(name) == sha, 'bound source is not owned by new wheel: ' + name)
    modules, dependency_sites = {}, set()
    for name, module in list(sys.modules.items()):
        filename = getattr(module, '__file__', None)
        if not filename or str(filename).startswith('<'):
            continue
        path = Path(filename).resolve()
        if name.split('.')[0] in PACKAGE_ROOTS:
            _require(path.is_relative_to(installed), 'imported product module escapes installation: ' + name)
            relative = path.relative_to(installed).as_posix()
            _require(relative in owned, 'imported product module not in wheel RECORD: ' + name)
            modules[name] = {'path': str(path), 'sha256': owned[relative]}
        elif 'site-packages' in path.parts or 'dist-packages' in path.parts:
            _require(path.is_relative_to(installed_root) or path.is_relative_to(shared_root),
                     'undeclared third-party dependency root: ' + name)
            dependency_sites.add(str(path).split('/site-packages/')[0].split('/dist-packages/')[0])
    _require(modules, 'no product imports inspected')
    return {'installed_site': str(installed), 'product_distribution_version': owner.version,
            'owned_package_files': len(owned), 'bound_source_files': len(prepared_sources),
            'imported_product_modules': modules, 'observed_dependency_roots': sorted(dependency_sites),
            'fresh_dependency_install': False}


def _retained_bytes(directory):
    # Invocation receipts can grow; the numerical history and score receipts are immutable on reuse.
    paths = list((directory / 'numerical').rglob('*'))
    paths += [directory / name for name in ('baseline-score-intent.json', 'baseline-score.json',
              'refined-score-intent.json', 'refined-score.json', 'numerical-start-intent.json',
              'request.json', 'binding.json', 'result.json')]
    return {str(path.relative_to(directory)): _sha(path.read_bytes())
            for path in paths if path.is_file()}


def _decisions(directory):
    events = [json.loads(line) for line in (directory / 'numerical/events.jsonl').read_bytes().splitlines()]
    return [event['payload']['decision']['outcome'] for event in events
            if event['kind'] == 'objective_finished']


def execute(root, installed_root, shared_root):
    started = time.perf_counter()
    receipt = {'schema_id': SCHEMA, 'status': 'running', 'stages': [],
               'synthetic_inputs_only': True, 'real_molecular_evaluations': 0,
               'evaluation_labels_read': 0, 'fresh_dependency_install': False,
               'scientifically_validated': False, 'timings_are_nested_do_not_sum': True}
    try:
        _require(sys.flags.isolated == 1 and sys.flags.dont_write_bytecode == 1
                 and sys.flags.optimize == 0, 'probe requires isolated -I -B without optimization')
        _require(Path(sys.prefix).resolve() == installed_root, 'sys.prefix differs from installed root')
        _require(importlib.util.find_spec('tools') is None, 'checkout tools are importable')
        preparation = _read(root / 'preparation.json')
        _require(not Path.cwd().resolve().is_relative_to(Path(preparation['source_checkout'])),
                 'installed execution must be outside checkout')
        _require(_sha(Path(__file__).read_bytes()) == preparation['probe_sha256'], 'probe bytes changed')
        _require(_sha((root / 'request.json').read_bytes()) == preparation['request_sha256'],
                 'prepared request bytes changed')
        _pins(preparation)
        receipt['runtime'] = {'python': sys.version, 'executable': sys.executable,
                              'prefix': sys.prefix, 'base_prefix': sys.base_prefix,
                              'sys_path': sys.path, 'shared_dependency_root': str(shared_root)}
        receipt['ownership_before'] = _ownership(installed_root, shared_root,
                                                  preparation['implementation_sources'])
        env = {key: value for key, value in os.environ.items()
               if key not in {'PYTHONPATH', 'PYTHONUSERBASE', 'PYTHONOPTIMIZE'}}
        env.update(PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1',
                   OPENBLAS_NUM_THREADS='1', CUDA_VISIBLE_DEVICES='')

        def invoke(name, command, directory, pause=None):
            args = [sys.executable, '-I', '-B', '-m', 'betelgeuze_product.cpu_refinement_v1_3',
                    command, '--request', str(root / 'request.json'), '--run-dir', str(directory)]
            if pause is not None:
                args += ['--pause-after-objective-attempts', str(pause)]
            stage = {'name': name, 'command': args, 'cwd': str(root),
                     'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                     'exit_code': None}
            tick = time.perf_counter()
            try:
                with (root / (name + '.stdout.json')).open('xb') as out, (root / (name + '.stderr.log')).open('xb') as err:
                    completed = subprocess.run(args, cwd=root, env=env, stdout=out, stderr=err, timeout=180)
                stage['exit_code'] = completed.returncode
                _require(completed.returncode == 0, name + ' CLI failed; logs retained')
                value = _read(root / (name + '.stdout.json'))
            except BaseException as exc:
                stage['error_type'] = type(exc).__name__
                raise
            finally:
                stage['whole_wall_seconds'] = time.perf_counter() - tick
                receipt['stages'].append(stage)
                _write(root / (name + '.execution.json'), stage)
            return value

        full_dir, split_dir = root / 'continuous', root / 'split'
        full = invoke('continuous-run', 'run', full_dir)
        pause = invoke('split-pause', 'run', split_dir, preparation['pause_after_objective_attempts'])
        _require(pause['result']['status'] == 'checkpointed', 'pause must retain a nonterminal state')
        _require(pause['result']['numerical_result']['checkpoint']['state']['attempts'] == 2,
                 'pause did not occur at declared objective count')
        _require(pause['invocation']['score_work']['new_score_calls'] == 1,
                 'paused run must score baseline only')
        baseline = (split_dir / 'baseline-score.json').read_bytes()
        split = invoke('split-resume', 'resume', split_dir)
        _require((split_dir / 'baseline-score.json').read_bytes() == baseline, 'resume changed baseline receipt')
        left, right = full['result'], split['result']
        a, b = left['numerical_result'], right['numerical_result']
        _require(a['status'] == b['status'] == 'force_converged', 'tiny fixture must converge')
        _require(a['checkpoint']['state'] == b['checkpoint']['state'],
                 'continuous and resumed complete binary64 solver states differ')
        outcomes = _decisions(full_dir)
        _require(outcomes == _decisions(split_dir), 'objective decisions differ after resume')
        accepted = outcomes.count('accepted')
        rejected = sum(item.startswith('rejected') for item in outcomes)
        _require(accepted > 0 and rejected > 0, 'fixture must cover accepted and rejected trials')
        for field in ('binding', 'attempt', 'rows', 'paired_decision', 'final_selection',
                      'raw_per_arm_selection', 'per_arm_selection', 'score_calls', 'score_quantity'):
            _require(left[field] == right[field], 'continuous/resumed result semantic mismatch: ' + field)
        _require(left['score_calls'] == right['score_calls'] == 2, 'one baseline and final score required')
        _require(full['invocation']['score_work']['new_score_calls'] == 2
                 and split['invocation']['score_work']['new_score_calls'] == 1, 'score invocation denominator differs')
        _require(a['work']['restart_force_calls'] == 0
                 and b['work']['restart_force_calls'] == b['work']['restart_verification_attempts'] == 1,
                 'resume must perform one separately counted full force verification')
        _require(a['work']['optimizer_force_calls'] == b['work']['optimizer_force_calls']
                 and b['work']['actual_force_calls'] == a['work']['actual_force_calls'] + 1,
                 'resume force denominator differs from optimizer plus one verification')
        _require(pause['invocation']['new_force_calls'] + split['invocation']['new_force_calls']
                 == b['work']['actual_force_calls'], 'invocation force calls do not sum to cumulative count')
        for numerical in (a, b):
            _require(numerical['work']['failed_optimizer_force_calls'] == 0
                     and numerical['work']['failed_restart_force_calls'] == 0
                     and numerical['work']['unknown_pending_attempts'] == 0,
                     'unexpected failed or unknown synthetic work')
        retained = _retained_bytes(split_dir)
        reuse = invoke('completed-reuse', 'resume', split_dir)
        _require(reuse['result'] == right, 'completed reuse changed result')
        _require(reuse['invocation']['new_force_calls'] == 0
                 and reuse['invocation']['score_work']['new_score_calls'] == 0,
                 'completed reuse performed new force or score work')
        _require(_retained_bytes(split_dir) == retained, 'completed reuse changed numerical or score evidence')
        for name, directory, result in (('verify-continuous', full_dir, left), ('verify-split', split_dir, right)):
            verified = invoke(name, 'verify', directory)
            _require(verified['structural_verification_passed']
                     and verified['result_sha256'] == result['result_sha256']
                     and verified['scoring_reexecuted'] is False
                     and verified['numerical_evaluation_reexecuted'] is False, 'verification receipt invalid')
        _require(_retained_bytes(split_dir) == retained, 'verification changed retained evidence')
        _pins(preparation)
        receipt['ownership_after'] = _ownership(installed_root, shared_root, preparation['implementation_sources'])
        _require(receipt['ownership_after'] == receipt['ownership_before'], 'loaded installed ownership changed')
        receipt.update(status='passed', accepted_trials=accepted, rejected_trials=rejected,
                       numerical_state_exact=True, raw_scores_exact=True, selections_exact=True,
                       continuous_work=a['work'], resumed_work=b['work'],
                       continuous_invocation=full['invocation'], paused_invocation=pause['invocation'],
                       resumed_invocation=split['invocation'], completed_reuse_invocation=reuse['invocation'],
                       numerical_and_score_bytes_unchanged_on_reuse=True,
                       qualification='installation_and_synthetic_continuation_only')
    except BaseException as exc:
        receipt.update(status='failed', error_type=type(exc).__name__, error=str(exc),
                       traceback=traceback.format_exc(),
                       unreturned_work='inspect retained CLI journals; no automatic retry or zero-work assumption')
        raise
    finally:
        receipt['whole_wall_seconds'] = time.perf_counter() - started
        _write(root / 'installed-probe.json', receipt)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prep = commands.add_parser('prepare')
    prep.add_argument('directory', type=Path)
    run = commands.add_parser('execute')
    run.add_argument('directory', type=Path)
    run.add_argument('--installed-root', type=Path, required=True)
    run.add_argument('--shared-dependency-root', type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.directory.resolve()
    if args.command == 'prepare':
        try:
            prepare(root)
        except BaseException as exc:
            if root.is_dir() and not (root / 'preparation-failure.json').exists():
                _write(root / 'preparation-failure.json', {'status': 'failed',
                    'error_type': type(exc).__name__, 'error': str(exc),
                    'force_evaluations': 0, 'score_evaluations': 0,
                    'traceback': traceback.format_exc()})
            raise
    else:
        result = execute(root, args.installed_root.resolve(), args.shared_dependency_root.resolve())
        print(json.dumps({'status': result['status'], 'receipt': str(root / 'installed-probe.json')}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
