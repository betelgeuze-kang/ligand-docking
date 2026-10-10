"""Fixed mock-arm workers exercise actual launch, limits, receipts and death."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

from betelgeuze_product.cpu_shape_comparison_supervisor_v1.limits import Limits
from betelgeuze_product.cpu_shape_comparison_supervisor_v1 import supervisor


def descriptor(behavior, arm='B1'):
    return {'mode': 'synthetic_control', 'behavior': behavior, 'arm': arm}


def test_finished_worker_collection_replay_and_no_retry(tmp_path):
    root = tmp_path / 'arm'
    receipt = supervisor.run_arm(descriptor('finished'), root,
        limits=Limits(wall_seconds=3., cpu_seconds=2, file_bytes=65536, write_reservations=8))
    assert receipt['status'] == 'finished'
    assert receipt['worker_result']['row']['base_calls'] == 1
    assert not receipt['unknown_work_is_not_zero']
    assert receipt['worker_result']['storage']['write_reservations_used'] <= 8
    assert supervisor.verify_supervised_arm(root, receipt['receipt_sha256']) == receipt
    with pytest.raises(FileExistsError):
        supervisor.run_arm(descriptor('finished'), root)
    (root / 'work' / 'objective-finished.json').write_text('{}')
    with pytest.raises(ValueError):
        supervisor.verify_supervised_arm(root, receipt['receipt_sha256'])


@pytest.mark.parametrize('behavior', ['sleep', 'cpu', 'grow_file', 'many_files', 'spawn_child'])
def test_failed_worker_preserves_reservation_and_unknown_work(tmp_path, behavior):
    root = tmp_path / behavior
    limit = Limits(wall_seconds=.3 if behavior == 'sleep' else 4., cpu_seconds=1,
                   file_bytes=65536, write_reservations=8)
    receipt = supervisor.run_arm(descriptor(behavior), root, limits=limit)
    assert receipt['status'] == 'failed_or_unknown'
    assert receipt['worker_result'] is None
    assert receipt['unknown_work_is_not_zero']
    assert not receipt['automatic_retry_performed']
    assert (root / 'work' / 'objective-started.json').exists()
    assert not (root / 'work' / 'objective-finished.json').exists()
    assert all(row['bytes'] <= max(supervisor.PARENT_FILE_BYTES, limit.file_bytes)
               for row in receipt['files'].values())
    assert receipt['logical_bytes_before_finished_receipt'] <= limit.logical_payload_bound + 2 * supervisor.PARENT_FILE_BYTES
    assert supervisor.verify_supervised_arm(root, receipt['receipt_sha256']) == receipt
    if behavior == 'sleep':
        assert receipt['wall_watchdog_killed'] and receipt['returncode'] == -signal.SIGKILL
    elif behavior == 'cpu':
        assert receipt['returncode'] == -signal.SIGKILL


def _live(pid):
    try:
        value = Path(f'/proc/{pid}/stat').read_text()
    except FileNotFoundError:
        return False
    return value.split(') ', 1)[1][0] != 'Z'


def test_parent_death_kills_worker_and_leaves_unknown_reservation(tmp_path):
    root = tmp_path / 'orphan'
    code = ('from betelgeuze_product.cpu_shape_comparison_supervisor_v1.supervisor import run_arm; '
            'from betelgeuze_product.cpu_shape_comparison_supervisor_v1.limits import Limits; '
            f'run_arm({descriptor("sleep")!r}, {str(root)!r}, limits=Limits(wall_seconds=30., cpu_seconds=30))')
    env = dict(os.environ, PYTHONPATH=str(Path(supervisor.__file__).resolve().parents[2]),
               PYTHONDONTWRITEBYTECODE='1')
    parent = subprocess.Popen([sys.executable, '-c', code], env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    marker = root / 'work' / 'objective-started.json'
    deadline = time.monotonic() + 5
    pid = None
    try:
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(.02)
        assert marker.exists(), 'worker never reserved objective'
        pid = json.loads(marker.read_text())['pid']
        assert _live(pid)
        parent.kill()
        parent.wait(timeout=3)
        while _live(pid) and time.monotonic() < deadline:
            time.sleep(.02)
        assert not _live(pid), 'worker survived supervising parent death'
        assert marker.exists()
        assert not (root / 'finished.json').exists()
        assert not (root / 'worker-result.json').exists()
        with pytest.raises(FileExistsError):
            supervisor.run_arm(descriptor('finished'), root)
    finally:
        if parent.poll() is None:
            parent.kill()
            parent.wait()
        if pid is not None and _live(pid):
            os.kill(pid, signal.SIGKILL)


def test_source_bound_logical_cap_is_below_one_gib():
    limits = Limits()
    cap = (3 * limits.write_reservations + 16) * limits.file_bytes
    cap += supervisor.PARENT_FILES_MAXIMUM * supervisor.PARENT_FILE_BYTES
    assert cap == 768 * 1024 * 1024
    assert cap < 1024 * 1024 * 1024


def test_whole_wall_watchdog_covers_parent_only_work():
    started = time.monotonic()
    with pytest.raises(supervisor.WholeComparisonTimeout):
        with supervisor.wall_deadline(.05):
            time.sleep(5)
    assert time.monotonic() - started < 1
    assert signal.getitimer(signal.ITIMER_REAL) == (0., 0.)


def test_whole_wall_watchdog_kills_active_group_and_preserves_unknown(tmp_path):
    root = tmp_path / 'whole-timeout'
    with pytest.raises(supervisor.WholeComparisonTimeout):
        with supervisor.wall_deadline(.5):
            supervisor.run_arm(descriptor('sleep'), root,
                limits=Limits(wall_seconds=10., cpu_seconds=10))
    marker = root / 'work' / 'objective-started.json'
    assert marker.exists()
    assert not _live(json.loads(marker.read_text())['pid'])
    assert not (root / 'finished.json').exists()
    assert not (root / 'work' / 'objective-finished.json').exists()
    with pytest.raises(FileExistsError):
        supervisor.run_arm(descriptor('finished'), root)


def test_cli_parent_cpu_ceiling_can_be_inherited_by_larger_worker_limit(tmp_path):
    root = tmp_path / 'inherited-limits'
    code = (
        'from betelgeuze_product.cpu_shape_comparison_supervisor_v1.__main__ import configure_parent_cpu; '
        'from betelgeuze_product.cpu_shape_comparison_supervisor_v1.supervisor import run_arm; '
        'from betelgeuze_product.cpu_shape_comparison_supervisor_v1.limits import Limits; '
        'configure_parent_cpu(1, 2); '
        f'r = run_arm({descriptor("finished")!r}, {str(root)!r}, '
        'limits=Limits(wall_seconds=3., cpu_seconds=2)); '
        'assert r["status"] == "finished", r')
    env = dict(os.environ, PYTHONPATH=str(Path(supervisor.__file__).resolve().parents[2]),
               PYTHONDONTWRITEBYTECODE='1')
    completed = subprocess.run([sys.executable, '-c', code], env=env,
                               capture_output=True, timeout=5)
    assert completed.returncode == 0, completed.stderr.decode()
    receipt = json.loads((root / 'finished.json').read_text())
    assert receipt['limits']['cpu_seconds'] == 2
    assert receipt['status'] == 'finished'


def test_finished_process_retains_unknown_base_work_flag(tmp_path):
    root = tmp_path / 'retained-unknown'
    receipt = supervisor.run_arm(descriptor('retained_unknown'), root,
        limits=Limits(wall_seconds=3., cpu_seconds=2, file_bytes=65536, write_reservations=8))
    assert receipt['status'] == 'finished'
    assert receipt['returncode'] == 0
    assert not receipt['process_result_unknown']
    assert receipt['base_work_unknown']
    assert receipt['unknown_work_is_not_zero']
    assert receipt['worker_result']['row']['work'] is None
    assert (root / 'work' / 'objective-started.json').exists()
    assert not (root / 'work' / 'objective-finished.json').exists()
    assert supervisor.verify_supervised_arm(root, receipt['receipt_sha256']) == receipt


def test_diagnostic_uncertainty_is_independent_of_known_base_work():
    flags = supervisor.uncertainty({'row': {'status': 'max_accepted_steps_reached',
        'work': {'actual_force_calls': 41}, 'diagnostic_status': 'failed_or_unknown'}})
    assert flags == {'process_result_unknown': False, 'base_work_unknown': False,
                     'diagnostic_work_unknown': True, 'unknown_work_is_not_zero': True}


def test_parent_soft_cpu_default_disposition_terminates_before_hard():
    code = ('from betelgeuze_product.cpu_shape_comparison_supervisor_v1.__main__ import configure_parent_cpu\n'
            'configure_parent_cpu(1, 2)\nwhile True: pass\n')
    env = dict(os.environ, PYTHONPATH=str(Path(supervisor.__file__).resolve().parents[2]),
               PYTHONDONTWRITEBYTECODE='1')
    result = subprocess.run([sys.executable, '-c', code], env=env, timeout=5, capture_output=True)
    assert result.returncode == -signal.SIGXCPU, result.stderr


def test_write_and_link_reservations_are_never_refunded():
    from betelgeuze_product.cpu_shape_comparison_supervisor_v1.limits import (
        ResourceBoundExceeded, WriteBudget,
    )
    budget = WriteBudget(Limits(write_reservations=3))
    budget('open', ('/nonexistent', 'w', os.O_WRONLY | os.O_CREAT))
    budget('os.link', ('/nonexistent', '/nonexistent2', -1, -1))
    with pytest.raises(ResourceBoundExceeded):
        budget('open', ('/nonexistent', 'w', os.O_WRONLY))
    assert budget.writes == 3
    for event in ('os.symlink', 'os.rename', 'os.truncate', 'os.fork', 'os.exec', 'subprocess.Popen'):
        with pytest.raises(ResourceBoundExceeded):
            budget(event, ())


def test_unadmitted_executable_descriptor_cannot_dispatch(tmp_path):
    root = tmp_path / 'bad-descriptor'
    receipt = supervisor.run_arm({**descriptor('finished'), 'command': 'true'}, root,
        limits=Limits(wall_seconds=3., cpu_seconds=2, file_bytes=65536, write_reservations=8))
    assert receipt['status'] == 'failed_or_unknown'
    assert not list((root / 'work').iterdir())
    with pytest.raises(FileExistsError):
        supervisor.run_arm(descriptor('finished'), root)


def test_symlink_output_ancestor_rejected_without_mutation(tmp_path):
    real = tmp_path / 'real'
    real.mkdir()
    alias = tmp_path / 'alias'
    alias.symlink_to(real, target_is_directory=True)
    with pytest.raises(OSError):
        supervisor.run_arm(descriptor('finished'), alias / 'arm')
    assert list(real.iterdir()) == []
