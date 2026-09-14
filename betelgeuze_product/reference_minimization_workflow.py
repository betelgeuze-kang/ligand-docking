"""Local CPU reference minimization using the existing V2 solver and checkpoint.

Explicit canonical systems and complete reference parameters only. This is not
molecular preparation, receptor/ligand cross-only optimization, MD or approval.
One private local directory holds atomic iteration checkpoints and final output.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from dataclasses import fields
import fcntl
import hashlib
import html
import json
import os
from pathlib import Path
import stat
import time
from betelgeuze_product.local_research_workflow import _atomic, _decode, _json
SCHEMA = 'local_reference_minimization_request_v1'
MAX_BYTES = 32 * 1024 * 1024
MAX_ATOMS = 256

def _digest(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()

def _read(path):
    """Bound a regular input, including replacement during reading."""
    path = Path(path)
    if not path.is_absolute():
        raise ValueError('absolute_input_path_required')
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_BYTES:
            raise ValueError('bounded_regular_input_required')
        raw = stream.read(MAX_BYTES + 1)
        after = os.fstat(stream.fileno())
        current = path.stat()

        def identity(s):
            return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if len(raw) > MAX_BYTES or identity(before) != identity(after) or identity(after) != identity(current):
            raise ValueError('input_changed_or_exceeds_capacity')
    return raw

def _bound(ref):
    if type(ref) is not dict or set(ref) != {'path', 'sha256'}:
        raise ValueError('exact_bound_file_required')
    raw = _read(ref['path'])
    if hashlib.sha256(raw).hexdigest() != ref['sha256']:
        raise ValueError('input_sha256_mismatch')
    return _decode(raw)

def _parameters(document):
    from betelgeuze_engine_v2.physics import reference_parameters as p
    if type(document) is not dict or set(document) != {f.name for f in fields(p.ReferenceForceFieldParameters)}:
        raise ValueError('complete_reference_parameters_required')
    value = dict(document)
    for name, cls in (('atom_parameters', p.AtomNonbondedParameter), ('bonds', p.HarmonicBondParameter), ('angles', p.HarmonicAngleParameter), ('torsions', p.PeriodicTorsionParameter), ('scaled_pairs', p.PairScalingParameter)):
        if type(value[name]) is not list or len(value[name]) > 20000:
            raise ValueError('parameter_array_capacity_or_type')
        rows = []
        for row in value[name]:
            if type(row) is not dict or set(row) != {f.name for f in fields(cls)}:
                raise ValueError('complete_parameter_row_required')
            rows.append(cls(**row))
        value[name] = tuple(rows)
    domain = value['applicability_domain']
    if type(domain) is not dict or set(domain) != {f.name for f in fields(p.ReferenceApplicabilityDomain)}:
        raise ValueError('explicit_applicability_domain_required')
    value['applicability_domain'] = p.ReferenceApplicabilityDomain(**domain)
    result = p.ReferenceForceFieldParameters(**value)
    if result.to_dict() != document:
        raise ValueError('parameter_normalization_is_not_admission')
    return result

def _load(request):
    import torch
    from betelgeuze_engine_v2.molecular.serialization import all_atom_system_from_canonical_json
    from betelgeuze_engine_v2.physics.reference_minimization import _config_from_document
    if type(request) is not dict or set(request) != {'schema_version', 'backend', 'system', 'parameters', 'config', 'checkpoint_every'} or request['schema_version'] != SCHEMA or (request['backend'] != 'cpu'):
        raise ValueError('explicit_reference_cpu_request_required')
    if type(request['checkpoint_every']) is not int or not 1 <= request['checkpoint_every'] <= 100:
        raise ValueError('checkpoint_every_must_be_1_to_100')
    system = all_atom_system_from_canonical_json(_json(_bound(request['system'])))
    if not 1 <= system.atom_count <= MAX_ATOMS or system.model_count != 1 or system.coordinates.dtype != torch.float64 or (system.cell is not None):
        raise ValueError('bounded_nonperiodic_binary64_system_required')
    config = _config_from_document(request['config'])
    if config.to_dict() != request['config']:
        raise ValueError('noncanonical_minimization_config')
    if config.max_neighbors > MAX_ATOMS or config.max_atoms_per_cell > MAX_ATOMS:
        raise ValueError('local_neighbor_capacity_exceeded')
    return (system, _parameters(_bound(request['parameters'])), config)

def _check_inputs(request):
    for key in ('system', 'parameters'):
        _bound(request[key])

@contextmanager
def _directory(path, *, resume):
    path = Path(path).absolute()
    if not resume:
        path.mkdir(mode=448)
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    lock = None
    try:
        info = os.fstat(fd)
        if info.st_uid != os.geteuid() or info.st_mode & 63:
            raise ValueError('private_owned_run_directory_required')
        lock = os.open('.minimization.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 384, dir_fd=fd)
        info = os.fstat(lock)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError('invalid_minimization_lock')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield Path(f'/proc/self/fd/{fd}')
    finally:
        if lock is not None:
            os.close(lock)
        os.close(fd)

def _publish(path, value):
    raw = _json(value) + '\n'
    if len(raw.encode()) > MAX_BYTES:
        raise ValueError('minimization_output_capacity_exceeded')
    _atomic(path, raw)

def _envelope(payload):
    return {'payload': payload, 'sha256': _digest(payload)}

def _verified(path):
    result = _decode(_read(path))
    if type(result) is not dict or set(result) != {'payload', 'sha256'} or _digest(result['payload']) != result['sha256']:
        raise ValueError('minimization_record_corrupt')
    return result['payload']

def _archive_previous_attempt(directory):
    """Keep old summaries and interrupted publication bytes before a resumed write."""
    history = directory / 'history'
    history.mkdir(mode=448, exist_ok=True)
    if history.is_symlink() or not history.is_dir():
        raise ValueError('unsafe_history_directory')
    for index in range(1, 10001):
        dest = history / f'attempt-{index:05d}'
        try:
            dest.mkdir(mode=448)
            break
        except FileExistsError:
            continue
    else:
        raise ValueError('attempt_history_capacity_exceeded')
    names = ('binding.json', 'checkpoint.json', 'final-system.json', 'report.json', 'report.html', 'complete.json')
    for name in names:
        for suffix in ('', '.partial'):
            original = directory / (name + suffix)
            if original.exists() or original.is_symlink():
                raw = _read(original)
                with (dest / (name + suffix)).open('xb') as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
    fd = os.open(dest, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    for name in names:
        (directory / (name + '.partial')).unlink(missing_ok=True)
    return str(dest.relative_to(directory))

def _save_checkpoint(directory, payload):
    _publish(directory / 'checkpoint.json', _envelope(payload))

def _evaluate(system, parameters, config):
    from betelgeuze_engine_v2.geometry import RadiusGraphConfig, build_compact_radius_graph
    from betelgeuze_engine_v2.physics.reference_forcefield import evaluate_reference_force_field
    neighbors = build_compact_radius_graph(system.coordinates, RadiusGraphConfig(cutoff_angstrom=parameters.cutoff_angstrom, max_neighbors=config.max_neighbors, max_atoms_per_cell=config.max_atoms_per_cell))
    value = evaluate_reference_force_field(system, neighbors, parameters)
    return {'energy_kcal_per_mol': value.term.energy[0].item(), 'forces_kcal_per_mol_angstrom': value.term.forces.tolist()}

def run_minimization(request, run_dir, *, resume=False, stop_after=None):
    """Resume original solver budgets; checkpointed does not mean converged.

    `stop_after` is an absolute accepted-iteration pause, not a new iteration
    budget. Uncommitted work after process death may repeat; its historical cost
    is unknown, not represented as a measured speedup. Terminal results restore.
    """
    started, cpu = (time.perf_counter(), time.process_time())
    import torch
    from betelgeuze_engine.product.prepared_pose_journal import _runtime_binding
    from betelgeuze_engine_v2.molecular.serialization import canonical_system_json_bytes, all_atom_system_from_canonical_json
    from betelgeuze_engine_v2.physics.reference_minimization import minimize_reference_force_field
    if type(resume) is not bool:
        raise ValueError('resume_must_be_boolean')
    request = _decode(_json(request))
    if len((_json(request) + '\n').encode()) > MAX_BYTES:
        raise ValueError('request_capacity_exceeded')
    system, parameters, config = _load(request)
    if stop_after is not None and (type(stop_after) is not int or not 0 <= stop_after <= config.max_iterations):
        raise ValueError('invalid_absolute_pause_iteration')
    physical_source = _decode(canonical_system_json_bytes(system))
    binding = {'request': request, 'runtime': _runtime_binding()}
    for key in ('system', 'parameters'):
        if Path(request[key]['path']).resolve().is_relative_to(Path(run_dir).resolve()):
            raise ValueError('output_directory_contains_source')
    with _directory(run_dir, resume=resume) as directory:
        if resume:
            if _verified(directory / 'binding.json') != binding:
                raise ValueError('minimization_request_source_or_environment_changed')
            saved = _verified(directory / 'checkpoint.json')
            if saved.get('binding_sha256') != _digest(binding):
                raise ValueError('minimization_checkpoint_binding_changed')
            prior = saved['result']
            checkpoint = saved['checkpoint']
            from betelgeuze_engine_v2.physics.reference_minimization import require_reference_minimization_checkpoint_document
            checked = require_reference_minimization_checkpoint_document(checkpoint)
            if checked.checkpoint_sha256 != prior['checkpoint_sha256'] or checked.source_system_sha256 != physical_source['system_sha256'] or checked.parameter_fingerprint_sha256 != parameters.fingerprint_sha256 or (checked.config_fingerprint_sha256 != config.fingerprint_sha256) or (prior['status'] not in {'converged', 'checkpointed', 'max_iterations_reached', 'line_search_failed'}) or (prior['scientifically_validated'] is not False):
                raise ValueError('result_checkpoint_mismatch')
            restored_system = all_atom_system_from_canonical_json(_json(saved['system']))
            if not torch.equal(restored_system.coordinates.view(torch.int64), checked.coordinates().view(torch.int64)):
                raise ValueError('checkpoint_coordinate_mismatch')
            terminal = prior['status'] != 'checkpointed'
            if stop_after is not None and stop_after < checked.accepted_iterations:
                raise ValueError('pause_precedes_committed_progress')
            previous_attempt = _archive_previous_attempt(directory)
        else:
            _publish(directory / 'binding.json', _envelope(binding))
            saved, checkpoint, terminal = (None, None, False)
            previous_attempt = None
        (directory / 'complete.json').unlink(missing_ok=True)
        calls = 0
        if not terminal:
            while True:
                accepted = 0 if checkpoint is None else checkpoint['accepted_iterations']
                target = min(config.max_iterations, accepted + request['checkpoint_every'])
                if stop_after is not None:
                    target = min(target, stop_after)
                _check_inputs(request)
                value = minimize_reference_force_field(system, parameters, config, checkpoint=checkpoint, pause_after_accepted_iterations=target)
                calls += 1
                document = _decode(canonical_system_json_bytes(value.system))
                reloaded = all_atom_system_from_canonical_json(_json(document))
                if not torch.equal(value.system.coordinates.view(torch.int64), reloaded.coordinates.view(torch.int64)):
                    raise ValueError('minimized_coordinate_roundtrip_failed')
                evaluation = _evaluate(reloaded, parameters, config)
                if evaluation['energy_kcal_per_mol'] != value.final_energy_kcal_per_mol:
                    raise ValueError('minimized_energy_recheck_failed')
                if not torch.isfinite(torch.tensor(evaluation['forces_kcal_per_mol_angstrom'], dtype=torch.float64)).all() or torch.linalg.vector_norm(torch.tensor(evaluation['forces_kcal_per_mol_angstrom'], dtype=torch.float64), dim=-1).max().item() != value.final_max_force_kcal_per_mol_angstrom:
                    raise ValueError('minimized_force_recheck_failed')
                changed = [i for i, (a, b) in enumerate(zip(system.coordinates[0].tolist(), value.system.coordinates[0].tolist())) if a != b]
                _check_inputs(request)
                if _decode(canonical_system_json_bytes(system)) != physical_source:
                    raise ValueError('source_system_mutated')
                saved = {'binding_sha256': _digest(binding), 'result': value.to_dict(), 'checkpoint': value.checkpoint.to_dict(), 'system': document, 'evaluation': evaluation, 'changed_atom_indices': changed, 'coordinate_status': 'derived' if changed else 'unchanged_parent', 'source_system_sha256': physical_source['system_sha256'], 'scientifically_validated': False, 'md_performed': False, 'gpu_performed': False, 'external_solver_called': False}
                _save_checkpoint(directory, saved)
                checkpoint = saved['checkpoint']
                if value.status != 'checkpointed' or (stop_after is not None and value.accepted_iterations >= stop_after):
                    break
        _check_inputs(request)
        _publish(directory / 'final-system.json', saved['system'])
        report = {**saved, 'invocation': {'solver_calls': calls, 'restored_terminal': terminal, 'previous_attempt_archive': previous_attempt, 'wall_seconds': time.perf_counter() - started, 'cpu_seconds': time.process_time() - cpu, 'past_interrupted_cost_known': False, 'cost_scope': 'this_invocation_excluding_final_publication'}}
        _publish(directory / 'report.json', report)
        _atomic(directory / 'report.html', '<!doctype html><meta charset="utf-8"><h1>Reference minimization</h1><pre>' + html.escape(json.dumps(report['result'], indent=2)) + '</pre><p>CPU reference model; not validated MD or affinity.</p>')
        hashes = {name: hashlib.sha256(_read(directory / name)).hexdigest() for name in ('report.json', 'final-system.json', 'report.html')}
        _publish(directory / 'complete.json', {'status': saved['result']['status'], 'binding_sha256': _digest(binding), 'artifacts': hashes, 'scientifically_validated': False})
        return report

def verify_minimization_run(directory):
    """Read-only local corruption check; neither executes nor approves a run."""
    directory = Path(directory).absolute()
    final = _decode(_read(directory / 'complete.json'))
    if set(final) != {'status', 'binding_sha256', 'artifacts', 'scientifically_validated'} or final['scientifically_validated'] is not False:
        raise ValueError('invalid_minimization_completion')
    names = {'report.json', 'final-system.json', 'report.html'}
    if type(final['artifacts']) is not dict or set(final['artifacts']) != names:
        raise ValueError('invalid_minimization_artifacts')
    for name, digest in final['artifacts'].items():
        if hashlib.sha256(_read(directory / name)).hexdigest() != digest:
            raise ValueError('minimization_artifact_changed')
    binding = _verified(directory / 'binding.json')
    saved = _verified(directory / 'checkpoint.json')
    report = _decode(_read(directory / 'report.json'))
    if final['binding_sha256'] != _digest(binding) or saved['binding_sha256'] != _digest(binding) or final['status'] != report['result']['status'] or any((report.get(key) != value for key, value in saved.items())) or (_decode(_read(directory / 'final-system.json')) != saved['system']):
        raise ValueError('minimization_publication_mismatch')
    return {'verification': 'passed', 'status': final['status'], 'scientifically_validated': False}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path)
    parser.add_argument('--verify-run', action='store_true')
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--stop-after', type=int)
    args = parser.parse_args(argv)
    try:
        if args.verify_run:
            if args.request or args.resume or args.stop_after is not None:
                raise ValueError('verify_run_has_no_execution_options')
            print(_json(verify_minimization_run(args.run_dir)))
            return 0
        if args.request is None:
            raise ValueError('request_required')
        result = run_minimization(_decode(_read(args.request)), args.run_dir, resume=args.resume, stop_after=args.stop_after)
        status = result['result']['status']
        print(_json({'status': status, 'converged': result['result']['converged'], 'scientifically_validated': False}))
        return 0 if status == 'converged' else 2
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(_json({'status': 'failed', 'error_type': type(exc).__name__, 'scientifically_validated': False}))
        return 2
if __name__ == '__main__':
    raise SystemExit(main())
