"""Actual bounded V2 minimization and process restart; synthetic parameters only."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
import torch
from betelgeuze_product import reference_minimization_workflow as workflow
from betelgeuze_engine_v2.molecular.serialization import canonical_system_json_bytes
from betelgeuze_engine_v2.physics.reference_minimization import minimize_reference_force_field
from tests.unit.test_engine_v2_reference_minimization import _system, _parameters, _config

def make_request(path, *, distance=1.5, iterations=100, interval=10):
    path.mkdir(parents=True, exist_ok=True)
    system = _system(distance=distance)
    parameters = _parameters(system)
    config = _config(max_iterations=iterations)

    def save(name, raw):
        p = path / name
        p.write_bytes(raw)
        return {'path': str(p.resolve()), 'sha256': hashlib.sha256(raw).hexdigest()}
    req = {'schema_version': workflow.SCHEMA, 'backend': 'cpu', 'system': save('system.json', canonical_system_json_bytes(system)), 'parameters': save('parameters.json', json.dumps(parameters.to_dict()).encode()), 'config': config.to_dict(), 'checkpoint_every': interval}
    return (req, system, parameters, config)

def test_actual_minimization_roundtrip_and_independent_harmonic_energy(tmp_path):
    request, system, parameters, config = make_request(tmp_path / 'input')
    before = copy.deepcopy(request)
    result = workflow.run_minimization(request, tmp_path / 'run')
    direct = minimize_reference_force_field(system, parameters, config)
    assert result['result'] == direct.to_dict()
    assert result['result']['status'] == 'converged'
    assert result['result']['final_energy_kcal_per_mol'] < result['result']['initial_energy_kcal_per_mol']
    from betelgeuze_engine_v2.molecular.serialization import all_atom_system_from_canonical_json
    loaded = all_atom_system_from_canonical_json((tmp_path / 'run/final-system.json').read_bytes())
    assert torch.equal(loaded.coordinates.view(torch.int64), direct.system.coordinates.view(torch.int64))
    distance = float(torch.linalg.vector_norm(loaded.coordinates[0, 1] - loaded.coordinates[0, 0]))
    assert result['evaluation']['energy_kcal_per_mol'] == pytest.approx(50 * (distance - 1) ** 2, abs=1e-15)
    assert result['evaluation']['forces_kcal_per_mol_angstrom'][0][0][0] == pytest.approx(100 * (distance - 1), abs=1e-12)
    assert request == before
    assert workflow.verify_minimization_run(tmp_path / 'run')['verification'] == 'passed'
    assert not result['md_performed'] and (not result['gpu_performed']) and (not result['scientifically_validated'])

def test_initially_converged_uses_unchanged_parent(tmp_path):
    request, _, _, _ = make_request(tmp_path / 'input', distance=1.0)
    result = workflow.run_minimization(request, tmp_path / 'run')
    assert result['result']['converged']
    assert result['result']['accepted_iterations'] == 0
    assert result['changed_atom_indices'] == [] and result['coordinate_status'] == 'unchanged_parent'

def test_iteration_budget_and_terminal_failure_not_retried(tmp_path, monkeypatch):
    request, _, _, _ = make_request(tmp_path / 'input', iterations=1)
    result = workflow.run_minimization(request, tmp_path / 'run')
    assert result['result']['status'] == 'max_iterations_reached'
    assert result['result']['energy_decreased'] and (not result['result']['converged'])
    import betelgeuze_engine_v2.physics.reference_minimization as owner
    monkeypatch.setattr(owner, 'minimize_reference_force_field', lambda *a, **k: pytest.fail('terminal state recomputed'))
    restored = workflow.run_minimization(request, tmp_path / 'run', resume=True)
    assert restored['result'] == result['result']
    assert restored['invocation']['solver_calls'] == 0 and restored['invocation']['restored_terminal']

def test_pause_and_new_process_resume_match_continuous(tmp_path):
    request, _, _, _ = make_request(tmp_path / 'input')
    path = tmp_path / 'request.json'
    path.write_text(json.dumps(request))
    root = Path(workflow.__file__).resolve().parents[1]
    env = {**os.environ, 'PYTHONPATH': str(root), 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1'}
    command = [sys.executable, '-m', workflow.__name__, '--request', str(path), '--run-dir', str(tmp_path / 'run')]
    paused = subprocess.run(command + ['--stop-after', '3'], env=env, cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert paused.returncode == 2, paused.stderr + paused.stdout
    assert json.loads(paused.stdout)['status'] == 'checkpointed'
    resumed = subprocess.run(command + ['--resume'], env=env, cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert resumed.returncode == 0, resumed.stderr + resumed.stdout
    stored = json.loads((tmp_path / 'run/report.json').read_text())
    continuous = workflow.run_minimization(request, tmp_path / 'continuous')
    assert stored['result'] == continuous['result']
    assert stored['system'] == continuous['system']
    checked = subprocess.run([sys.executable, '-m', workflow.__name__, '--verify-run', '--run-dir', str(tmp_path / 'run')], env=env, cwd=tmp_path, capture_output=True, text=True, timeout=20)
    assert checked.returncode == 0, checked.stderr

def test_process_death_after_durable_checkpoint(tmp_path):
    request, _, _, _ = make_request(tmp_path / 'input', interval=3)
    path = tmp_path / 'request.json'
    path.write_text(json.dumps(request))
    root = Path(workflow.__file__).resolve().parents[1]
    code = 'import json,os,sys\nfrom pathlib import Path\nfrom betelgeuze_product import reference_minimization_workflow as w\nsave=w._save_checkpoint\ndef die(*a,**k):\n    save(*a,**k)\n    os._exit(73)\nw._save_checkpoint=die\nw.run_minimization(json.loads(Path(sys.argv[1]).read_text()),Path(sys.argv[2]))\n'
    env = {**os.environ, 'PYTHONPATH': str(root), 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1'}
    child = subprocess.run([sys.executable, '-c', code, str(path), str(tmp_path / 'run')], env=env, cwd=tmp_path, capture_output=True, timeout=30)
    assert child.returncode == 73, child.stderr
    assert (tmp_path / 'run/checkpoint.json').exists()
    assert not (tmp_path / 'run/complete.json').exists()
    resumed = workflow.run_minimization(request, tmp_path / 'run', resume=True)
    continuous = workflow.run_minimization(request, tmp_path / 'continuous')
    assert resumed['result'] == continuous['result'] and resumed['system'] == continuous['system']

@pytest.mark.parametrize('change', ['system', 'parameters', 'config', 'runtime', 'corrupt', 'missing'])
def test_stale_or_damaged_resume_rejected(tmp_path, monkeypatch, change):
    request, _, _, _ = make_request(tmp_path / 'input')
    workflow.run_minimization(request, tmp_path / 'run', stop_after=3)
    if change in {'system', 'parameters'}:
        p = Path(request[change]['path'])
        p.write_bytes(p.read_bytes() + b'\n')
    elif change == 'config':
        request['config']['max_iterations'] += 1
    elif change == 'runtime':
        from betelgeuze_engine.product import prepared_pose_journal as journal
        old = journal._runtime_binding
        monkeypatch.setattr(journal, '_runtime_binding', lambda: {**old(), 'changed': True})
    elif change == 'corrupt':
        p = tmp_path / 'run/checkpoint.json'
        p.write_text(p.read_text().replace('checkpointed', 'converged'))
    else:
        (tmp_path / 'run/checkpoint.json').unlink()
    with pytest.raises((ValueError, OSError)):
        workflow.run_minimization(request, tmp_path / 'run', resume=True)

@pytest.mark.parametrize('change', ['backend', 'dtype', 'periodic', 'missing_parameter', 'claim', 'nan', 'bool_interval', 'huge_neighbors'])
def test_invalid_inputs_never_start_run(tmp_path, change):
    request, _, _, _ = make_request(tmp_path / 'input')
    if change == 'backend':
        request['backend'] = 'hip_safe'
    elif change == 'bool_interval':
        request['checkpoint_every'] = True
    elif change == 'huge_neighbors':
        request['config']['max_neighbors'] = 10000
    elif change in {'dtype', 'periodic'}:
        from dataclasses import replace
        from betelgeuze_engine_v2.molecular import UnitCell
        bad = _system(dtype=torch.float32) if change == 'dtype' else replace(_system(), cell=UnitCell.orthorhombic((10.0, 10.0, 10.0), dtype=torch.float64))
        raw = canonical_system_json_bytes(bad)
        Path(request['system']['path']).write_bytes(raw)
        request['system']['sha256'] = hashlib.sha256(raw).hexdigest()
    else:
        p = Path(request['parameters']['path'])
        value = json.loads(p.read_text())
        if change == 'missing_parameter':
            value.pop('bonds')
        elif change == 'claim':
            value['scientifically_validated'] = True
        elif change == 'nan':
            value['dielectric'] = float('nan')
        p.write_text(json.dumps(value))
        request['parameters']['sha256'] = hashlib.sha256(p.read_bytes()).hexdigest()
    with pytest.raises((ValueError, OSError, TypeError)):
        workflow.run_minimization(request, tmp_path / 'run')
    assert not (tmp_path / 'run').exists()

def test_result_corruption_and_readonly_verify(tmp_path):
    request, _, _, _ = make_request(tmp_path / 'input', distance=1.0)
    workflow.run_minimization(request, tmp_path / 'run')
    p = tmp_path / 'run/report.json'
    p.write_text(p.read_text() + ' ')
    before = {f.name: f.read_bytes() for f in (tmp_path / 'run').iterdir() if f.is_file()}
    with pytest.raises(ValueError, match='artifact_changed'):
        workflow.verify_minimization_run(tmp_path / 'run')
    assert before == {f.name: f.read_bytes() for f in (tmp_path / 'run').iterdir() if f.is_file()}

def test_existing_directory_and_symlink_rejected(tmp_path):
    request, _, _, _ = make_request(tmp_path / 'input')
    out = tmp_path / 'run'
    out.mkdir(mode=448)
    with pytest.raises(FileExistsError):
        workflow.run_minimization(request, out)
    link = tmp_path / 'link'
    link.symlink_to(out)
    with pytest.raises(OSError):
        workflow.run_minimization(request, link, resume=True)

def test_line_search_failure_is_terminal_not_convergence(tmp_path):
    request, _, _, _ = make_request(tmp_path / 'input')
    request['config'] = _config(max_iterations=2, max_backtracks=0, initial_step_size_angstrom2_mol_per_kcal=100.0, maximum_atom_displacement_angstrom=1000.0).to_dict()
    result = workflow.run_minimization(request, tmp_path / 'run')
    assert result['result']['status'] == 'line_search_failed'
    assert not result['result']['converged']
    assert result['result']['rejected_evaluations'] == 1
    assert result['changed_atom_indices'] == []
    original = (tmp_path / 'run/report.json').read_bytes()
    again = workflow.run_minimization(request, tmp_path / 'run', resume=True)
    assert again['invocation']['solver_calls'] == 0
    history = tmp_path / 'run' / again['invocation']['previous_attempt_archive']
    assert (history / 'report.json').read_bytes() == original
    assert workflow.verify_minimization_run(history)['status'] == 'line_search_failed'

def test_concurrent_run_lock_is_not_ignored(tmp_path):
    request, _, _, _ = make_request(tmp_path / 'input', distance=1.0)
    workflow.run_minimization(request, tmp_path / 'run')
    with workflow._directory(tmp_path / 'run', resume=True):
        with pytest.raises(BlockingIOError):
            workflow.run_minimization(request, tmp_path / 'run', resume=True)

def test_source_mutation_during_actual_calculation_never_finalizes(tmp_path, monkeypatch):
    request, _, _, _ = make_request(tmp_path / 'input')
    original = workflow._evaluate

    def mutate(*args):
        result = original(*args)
        path = Path(request['system']['path'])
        path.write_bytes(path.read_bytes() + b' ')
        return result
    monkeypatch.setattr(workflow, '_evaluate', mutate)
    with pytest.raises(ValueError, match='sha256'):
        workflow.run_minimization(request, tmp_path / 'run')
    assert not (tmp_path / 'run/complete.json').exists()
    assert not (tmp_path / 'run/checkpoint.json').exists()

def test_process_death_during_publication_preserves_partial_history(tmp_path):
    request, _, _, _ = make_request(tmp_path / 'input', distance=1.0)
    path = tmp_path / 'request.json'
    path.write_text(json.dumps(request))
    code = "import json,os,sys\nfrom pathlib import Path\nfrom betelgeuze_product import reference_minimization_workflow as w\npublish=w._publish\ndef die(path, value):\n    if path.name=='report.json':\n        path.with_name('report.json.partial').write_text('interrupted')\n        os._exit(74)\n    publish(path,value)\nw._publish=die\nw.run_minimization(json.loads(Path(sys.argv[1]).read_text()),Path(sys.argv[2]))\n"
    root = Path(workflow.__file__).resolve().parents[1]
    env = {**os.environ, 'PYTHONPATH': str(root), 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1'}
    child = subprocess.run([sys.executable, '-c', code, str(path), str(tmp_path / 'run')], env=env, cwd=tmp_path, capture_output=True, timeout=30)
    assert child.returncode == 74, child.stderr
    assert not (tmp_path / 'run/complete.json').exists()
    result = workflow.run_minimization(request, tmp_path / 'run', resume=True)
    history = tmp_path / 'run' / result['invocation']['previous_attempt_archive']
    assert (history / 'report.json.partial').read_text() == 'interrupted'
    assert result['invocation']['solver_calls'] == 0
    assert workflow.verify_minimization_run(tmp_path / 'run')['verification'] == 'passed'

# Request admission remains semantic; repeated checks bind the exact same bytes.
@pytest.mark.parametrize('source', ['system', 'parameters'])
def test_rechecks_read_all_source_bytes_without_redecoding(tmp_path, monkeypatch, source):
    request, _, _, _ = make_request(tmp_path / 'input', iterations=3, interval=1)
    raw = Path(request[source]['path']).read_bytes()
    original_decode, original_read = workflow._decode, workflow._read
    reads, decodes = [], []

    def read(path):
        value = original_read(path)
        if Path(path) == Path(request[source]['path']):
            reads.append(value)
        return value

    def decode(value):
        if any(value is item for item in reads):
            decodes.append(value)
        return original_decode(value)

    monkeypatch.setattr(workflow, '_read', read)
    monkeypatch.setattr(workflow, '_decode', decode)
    result = workflow.run_minimization(request, tmp_path / 'run')
    calls = result['invocation']['solver_calls']
    assert len(reads) == 2 * calls + 2
    assert all(value == raw for value in reads)
    assert len(decodes) == 1


@pytest.mark.parametrize('source', ['system', 'parameters'])
@pytest.mark.parametrize('replacement', [b'{"duplicate":1,"duplicate":2}', b'{truncated'])
def test_initial_semantic_admission_remains_required(tmp_path, source, replacement):
    request, _, _, _ = make_request(tmp_path / 'input')
    Path(request[source]['path']).write_bytes(replacement)
    request[source]['sha256'] = hashlib.sha256(replacement).hexdigest()
    with pytest.raises((ValueError, TypeError, KeyError)):
        workflow.run_minimization(request, tmp_path / 'run')
    assert not (tmp_path / 'run').exists()


@pytest.mark.parametrize('source', ['system', 'parameters'])
def test_rechecks_detect_changed_bytes_with_restored_size_and_mtime(tmp_path, monkeypatch, source):
    request, _, _, _ = make_request(tmp_path / 'input', interval=1)
    path = Path(request[source]['path'])
    raw, info = path.read_bytes(), path.stat()
    original = workflow._evaluate

    def mutate(*args):
        value = original(*args)
        altered = bytearray(raw)
        altered[len(altered) // 2] ^= 1
        path.write_bytes(altered)
        os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))
        return value

    monkeypatch.setattr(workflow, '_evaluate', mutate)
    with pytest.raises(ValueError, match='input_sha256_mismatch'):
        workflow.run_minimization(request, tmp_path / 'run')
    assert not (tmp_path / 'run/checkpoint.json').exists()
    assert not (tmp_path / 'run/complete.json').exists()


@pytest.mark.parametrize('interval', [1, 3, 100])
def test_observed_phase_costs_preserve_solver_and_checkpoint_schedule(tmp_path, interval):
    request, system, parameters, config = make_request(tmp_path / 'input', iterations=5, interval=interval)
    observed = workflow.run_minimization(request, tmp_path / 'run')
    direct = minimize_reference_force_field(system, parameters, config)
    assert observed['result'] == direct.to_dict()
    invocation = observed['invocation']
    costs = invocation['phase_costs']
    assert costs['schema_version'] == 'reference_minimization_phase_costs_v1'
    assert costs['scope'] == 'this_invocation_instrumented_substeps_only'
    assert costs['force_evaluation_count_observed'] is False
    phases = costs['phases']
    calls = invocation['solver_calls']
    assert phases['input_load']['calls'] == 1
    assert phases['source_recheck']['calls'] == 2 * calls + 1
    assert phases['solver']['calls'] == calls
    assert phases['result_recheck']['calls'] == calls
    assert phases['checkpoint_write']['calls'] == calls
    assert set(phases) == {'input_load', 'source_recheck', 'solver', 'result_recheck', 'checkpoint_write'}
    import math
    for phase in phases.values():
        assert type(phase['calls']) is int and phase['calls'] >= 0
        for name in ('wall_seconds', 'cpu_seconds'):
            assert type(phase[name]) is float and math.isfinite(phase[name]) and phase[name] >= 0
    assert sum(p['wall_seconds'] for p in phases.values()) <= invocation['wall_seconds']
    assert workflow.verify_minimization_run(tmp_path / 'run')['verification'] == 'passed'


def test_terminal_restore_has_no_new_solver_or_checkpoint_cost(tmp_path, monkeypatch):
    request, _, _, _ = make_request(tmp_path / 'input', distance=1.0)
    first = workflow.run_minimization(request, tmp_path / 'run')
    import betelgeuze_engine_v2.physics.reference_minimization as owner
    monkeypatch.setattr(owner, 'minimize_reference_force_field', lambda *a, **k: pytest.fail('recomputed'))
    monkeypatch.setattr(workflow, '_evaluate', lambda *a, **k: pytest.fail('rechecked terminal physics'))
    restored = workflow.run_minimization(request, tmp_path / 'run', resume=True)
    assert first['result'] == restored['result']
    costs = restored['invocation']['phase_costs']['phases']
    for phase in ('solver', 'result_recheck', 'checkpoint_write'):
        assert costs[phase] == {'calls': 0, 'wall_seconds': 0.0, 'cpu_seconds': 0.0}
    assert costs['source_recheck']['calls'] == 1
    assert workflow.verify_minimization_run(tmp_path / 'run')['verification'] == 'passed'
    old = tmp_path / 'run' / restored['invocation']['previous_attempt_archive']
    assert workflow.verify_minimization_run(old)['verification'] == 'passed'


def _reseal_minimization_report_for_corruption_test(directory, report):
    """Only fresh synthetic local copies; never rewrite historical evidence."""
    path = directory / 'report.json'
    path.write_text(json.dumps(report))
    completion_path = directory / 'complete.json'
    completion = json.loads(completion_path.read_text())
    completion['artifacts']['report.json'] = hashlib.sha256(path.read_bytes()).hexdigest()
    completion_path.write_text(json.dumps(completion))


@pytest.mark.parametrize('mutation', [
    'negative_wall', 'bool_time', 'string_time', 'negative_calls', 'bool_calls',
    'wrong_solver_calls', 'wrong_source_calls', 'wrong_write_calls', 'missing_phase',
    'extra_phase', 'wrong_scope', 'claims_force_count', 'nonzero_unexecuted', 'overflow_time',
])
def test_readonly_verifier_rejects_inconsistent_phase_costs(tmp_path, mutation):
    request, _, _, _ = make_request(tmp_path / 'input', distance=1.0)
    report = workflow.run_minimization(request, tmp_path / 'run')
    if mutation == 'nonzero_unexecuted':
        report = workflow.run_minimization(request, tmp_path / 'run', resume=True)
    costs = report['invocation']['phase_costs']
    phases = costs['phases']
    if mutation == 'negative_wall':
        phases['solver']['wall_seconds'] = -1.0
    elif mutation == 'bool_time':
        phases['solver']['cpu_seconds'] = True
    elif mutation == 'string_time':
        phases['solver']['wall_seconds'] = '0.1'
    elif mutation == 'negative_calls':
        phases['solver']['calls'] = -1
    elif mutation == 'bool_calls':
        phases['solver']['calls'] = True
    elif mutation == 'wrong_solver_calls':
        phases['solver']['calls'] += 1
    elif mutation == 'wrong_source_calls':
        phases['source_recheck']['calls'] += 1
    elif mutation == 'wrong_write_calls':
        phases['checkpoint_write']['calls'] += 1
    elif mutation == 'missing_phase':
        phases.pop('input_load')
    elif mutation == 'extra_phase':
        phases['gpu'] = {'calls': 0, 'wall_seconds': 0.0, 'cpu_seconds': 0.0}
    elif mutation == 'wrong_scope':
        costs['scope'] = 'entire_docking_gpu_run'
    elif mutation == 'claims_force_count':
        costs['force_evaluation_count_observed'] = True
    elif mutation == 'overflow_time':
        phases['solver']['cpu_seconds'] = 10 ** 400
    else:
        phases['solver']['wall_seconds'] = 0.1
    _reseal_minimization_report_for_corruption_test(tmp_path / 'run', report)
    before = {p.name: p.read_bytes() for p in (tmp_path / 'run').iterdir() if p.is_file()}
    with pytest.raises(ValueError, match='minimization_phase_costs'):
        workflow.verify_minimization_run(tmp_path / 'run')
    assert before == {p.name: p.read_bytes() for p in (tmp_path / 'run').iterdir() if p.is_file()}


def test_legacy_report_without_phase_costs_remains_readable(tmp_path):
    request, _, _, _ = make_request(tmp_path / 'input', distance=1.0)
    report = workflow.run_minimization(request, tmp_path / 'run')
    report['invocation'].pop('phase_costs', None)
    _reseal_minimization_report_for_corruption_test(tmp_path / 'run', report)
    assert workflow.verify_minimization_run(tmp_path / 'run')['verification'] == 'passed'


def test_phase_costs_do_not_reject_parallel_cpu_time(tmp_path):
    request, _, _, _ = make_request(tmp_path / 'input', distance=1.0)
    report = workflow.run_minimization(request, tmp_path / 'run')
    phase = report['invocation']['phase_costs']['phases']['solver']
    phase.update(wall_seconds=0.25, cpu_seconds=0.75)
    _reseal_minimization_report_for_corruption_test(tmp_path / 'run', report)
    assert workflow.verify_minimization_run(tmp_path / 'run')['verification'] == 'passed'
