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
