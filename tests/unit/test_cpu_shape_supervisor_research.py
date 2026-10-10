"""Explicit research resource admission, using bounded non-molecular workers."""
from contextlib import contextmanager
import json
import os
from types import SimpleNamespace

import pytest

from betelgeuze_product.cpu_shape_comparison_supervisor_v1 import __main__ as cli
from betelgeuze_product.cpu_shape_comparison_supervisor_v1 import supervisor
from betelgeuze_product.cpu_shape_comparison_supervisor_v1.limits import Limits

MIB = 1024 ** 2
GIB = 1024 ** 3


def research_limits(**changes):
    return Limits(**{'resource_policy': 'research_161', 'file_bytes': 8 * MIB,
                     'write_reservations': 360, **changes})


def _forbidden(*args, **kwargs):
    pytest.fail('unexpected output creation or worker dispatch')


def _files(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob('*') if p.is_file()}


def test_default_and_policy_only_selection_do_not_implicitly_increase_limits():
    default = Limits()
    policy_only = Limits(resource_policy='research_161')
    for limits in (default, policy_only):
        assert limits.file_bytes == 2 * MIB
        assert limits.write_reservations == 120
        assert limits.directory_reservations == 16
        assert limits.cpu_seconds == limits.wall_seconds == 600
        assert supervisor.logical_comparison_bound(limits) == 768 * MIB
    assert default.resource_policy == 'default'
    assert policy_only.resource_policy == 'research_161'


@pytest.mark.parametrize('options', [
    {'file_bytes': 8 * MIB}, {'write_reservations': 360},
    {'file_bytes': 8 * MIB, 'write_reservations': 360},
    {'resource_policy': 'research'}, {'resource_policy': None},
])
def test_larger_limits_require_exact_explicit_policy(options):
    with pytest.raises(ValueError):
        Limits(**options)


@pytest.mark.parametrize('changes', [
    {'file_bytes': 8 * MIB + 1}, {'write_reservations': 361},
    {'file_bytes': True}, {'write_reservations': True}, {'write_reservations': 360.},
    {'directory_reservations': 17}, {'cpu_seconds': 601}, {'wall_seconds': 601},
])
def test_research_ceilings_and_exact_integer_controls_remain_bounded(changes):
    with pytest.raises(ValueError):
        research_limits(**changes)


def test_exact_research_admission_and_b0_parent_aggregate_math():
    limits = research_limits()
    assert limits.file_bytes == 8 * MIB and limits.write_reservations == 360
    assert limits.logical_payload_bound == 2880 * MIB
    baseline = Limits(**{**limits.to_dict(), 'write_reservations': 16})
    assert baseline.logical_payload_bound == 128 * MIB
    parent = supervisor.PARENT_FILES_MAXIMUM * supervisor.PARENT_FILE_BYTES
    assert parent == 16 * MIB
    bound = 3 * limits.logical_payload_bound + baseline.logical_payload_bound + parent
    assert supervisor.logical_comparison_bound(limits) == bound == 8784 * MIB
    assert bound + GIB == 9808 * MIB


@pytest.mark.parametrize('available_delta', [-1, 0, 1])
def test_research_preflight_exact_free_space_boundary(tmp_path, monkeypatch, available_delta):
    limits = research_limits()
    required = 8784 * MIB + GIB
    devices = []

    def observed(fd):
        devices.append(os.fstat(fd).st_dev)
        return SimpleNamespace(f_bavail=required + available_delta, f_frsize=1)

    monkeypatch.setattr(supervisor.os, 'fstatvfs', observed)
    target = tmp_path / 'not-created'
    if available_delta < 0:
        with pytest.raises(ValueError, match='one GiB'):
            supervisor.research_storage_preflight(target, limits)
    else:
        receipt = supervisor.research_storage_preflight(target, limits)
        assert receipt == {
            'status': 'admitted_observation_not_exclusive_reservation',
            'filesystem_device': devices[0], 'available_bytes': required + available_delta,
            'required_available_bytes': required, 'logical_payload_bound_bytes': 8784 * MIB,
            'headroom_bytes': GIB, 'physical_quota_or_preallocation': False}
    assert not target.exists()
    assert len(devices) == 1


@pytest.mark.parametrize('route', ['run_comparison', 'run_synthetic_comparison'])
def test_low_space_fails_before_output_creation_or_any_worker(tmp_path, monkeypatch, route):
    monkeypatch.setattr(supervisor.os, 'fstatvfs',
                        lambda fd: SimpleNamespace(f_bavail=1, f_frsize=4096))
    monkeypatch.setattr(supervisor, 'new_directory', _forbidden)
    monkeypatch.setattr(supervisor, 'run_arm', _forbidden)
    output = tmp_path / 'never-created'
    with pytest.raises(ValueError, match='storage admission'):
        getattr(supervisor, route)('unused-plan', 'a' * 64, output, limits=research_limits())
    assert not output.exists()
    assert list(tmp_path.iterdir()) == []


def test_default_policy_does_not_consume_research_free_space_preflight(tmp_path, monkeypatch):
    monkeypatch.setattr(supervisor.os, 'fstatvfs', _forbidden)
    assert supervisor.research_storage_preflight(tmp_path / 'unused', Limits()) == {
        'status': 'not_required_default_policy'}


def test_research_output_parent_symlink_is_never_followed(tmp_path, monkeypatch):
    real = tmp_path / 'real'
    real.mkdir()
    alias = tmp_path / 'alias'
    alias.symlink_to(real, target_is_directory=True)
    monkeypatch.setattr(supervisor.os, 'fstatvfs', _forbidden)
    monkeypatch.setattr(supervisor, 'run_arm', _forbidden)
    with pytest.raises(OSError):
        supervisor.run_synthetic_comparison('unused-plan', 'a' * 64, alias / 'output',
                                             limits=research_limits())
    assert list(real.iterdir()) == []


@pytest.mark.parametrize('policy', [None, 'default', 'research_161'])
def test_cli_policy_selection_passes_only_explicit_resource_limits(monkeypatch, capsys, policy):
    observed = []
    cpu = []
    deadlines = []

    @contextmanager
    def deadline(seconds):
        deadlines.append(seconds)
        yield

    def run(*args, **kwargs):
        observed.append((args, kwargs))
        return {'report_sha256': 'a' * 64, 'denominator': {'planned': 4}}

    args = ['supervisor', '--plan', 'plan.json', '--expected-plan-sha256', 'b' * 64,
            '--output-dir', 'new-output']
    if policy is not None:
        args += ['--resource-policy', policy]
    monkeypatch.setattr(cli, 'run_comparison', run)
    monkeypatch.setattr(cli, 'configure_parent_cpu', lambda: cpu.append(True))
    monkeypatch.setattr(cli, 'wall_deadline', deadline)
    monkeypatch.setattr('sys.argv', args)
    cli.main()
    assert len(observed) == 1 and cpu == [True] and deadlines == [2700.]
    arguments, options = observed[0]
    assert arguments == ('plan.json', 'b' * 64, 'new-output')
    limits = options['limits']
    assert limits.resource_policy == ('research_161' if policy == 'research_161' else 'default')
    assert limits.file_bytes == (8 if policy == 'research_161' else 2) * MIB
    assert limits.write_reservations == (360 if policy == 'research_161' else 120)
    assert json.loads(capsys.readouterr().out)['report_sha256'] == 'a' * 64


def test_research_comparison_collects_actual_mock_workers_failure_and_no_retry(tmp_path, monkeypatch):
    """Run real supervised primitive controls, never prepared molecular workers."""
    limits = research_limits(wall_seconds=5, cpu_seconds=3)
    available = 9808 * MIB
    monkeypatch.setattr(supervisor.os, 'fstatvfs',
                        lambda fd: SimpleNamespace(f_bavail=available, f_frsize=1))
    execute = supervisor.run_arm
    dispatched = []

    def mock_arm(request, output_dir, **options):
        dispatched.append((request, options['limits']))
        # Only this fixture substitutes a fixed primitive descriptor; the real
        # process launcher, kernel/audit limits, collection and replay run unchanged.
        descriptor = {'mode': 'synthetic_control', 'arm': request['arm'],
                      'behavior': 'spawn_child' if request['arm'] == 'B2' else 'finished'}
        return execute(descriptor, output_dir, **options)

    monkeypatch.setattr(supervisor, 'run_arm', mock_arm)
    output = tmp_path / 'research-comparison'
    report = supervisor.run_synthetic_comparison('unused-synthetic-plan', 'c' * 64, output,
        limits=limits, total_wall_seconds=30)
    assert report['denominator'] == {'planned': 4, 'finished': 3,
                                     'failed_or_unknown': 1, 'not_started': 0}
    assert [row['arm'] for row in report['rows']] == list(supervisor.ARMS)
    assert report['plan_sha256'] == 'c' * 64
    assert report['limits'] == limits.to_dict()
    assert report['logical_payload_bound_bytes'] == 8784 * MIB
    assert report['storage_admission']['required_available_bytes'] == available
    assert report['storage_admission']['physical_quota_or_preallocation'] is False
    assert report['supervisor_sources'] == supervisor.sources()
    assert report['evidence_kind'] == 'synthetic_control'
    assert report['scientifically_validated'] is False
    assert report['report_sha256'] == supervisor.digest({
        k: v for k, v in report.items() if k != 'report_sha256'})
    assert json.loads((output / 'report.json').read_text()) == report
    binding = json.loads((output / 'binding.json').read_text())
    assert binding['limits'] == report['limits']
    assert binding['storage_admission'] == report['storage_admission']
    before = _files(output)
    for request, selected in dispatched:
        assert selected.resource_policy == 'research_161'
        assert selected.file_bytes == 8 * MIB
        assert selected.write_reservations == (16 if request['arm'] == 'B0' else 360)
    for receipt in report['rows']:
        root = output / receipt['arm']
        assert receipt['limits']['resource_policy'] == 'research_161'
        assert receipt['automatic_retry_performed'] is False
        assert supervisor.verify_supervised_arm(root, receipt['receipt_sha256']) == receipt
        if receipt['arm'] == 'B2':
            assert receipt['worker_result'] is None and receipt['unknown_work_is_not_zero']
            assert (root / 'work' / 'objective-started.json').exists()
            assert not (root / 'work' / 'objective-finished.json').exists()
        else:
            assert receipt['worker_result']['row']['base_calls'] == 1
        with pytest.raises(FileExistsError):
            execute({'mode': 'synthetic_control', 'arm': receipt['arm'], 'behavior': 'finished'},
                    root, limits=limits)
    with pytest.raises(FileExistsError):
        supervisor.run_synthetic_comparison('unused-synthetic-plan', 'c' * 64, output,
            limits=limits, total_wall_seconds=30)
    assert len(dispatched) == 4
    assert _files(output) == before


@pytest.mark.parametrize('behavior', ['grow_file', 'many_files'])
def test_research_full_storage_ceilings_fail_closed_in_actual_worker(tmp_path, behavior):
    limits = research_limits(wall_seconds=5, cpu_seconds=3)
    output = tmp_path / behavior
    receipt = supervisor.run_arm({'mode': 'synthetic_control', 'arm': 'B1',
                                 'behavior': behavior}, output, limits=limits)
    assert receipt['status'] == 'failed_or_unknown'
    assert receipt['unknown_work_is_not_zero']
    assert (output / 'work' / 'objective-started.json').exists()
    assert not (output / 'work' / 'objective-finished.json').exists()
    if behavior == 'grow_file':
        assert (output / 'work' / 'growth.bin').stat().st_size == 8 * MIB
    else:
        # One stderr token and two opens for objective JSON leave 357.
        assert len(list((output / 'work').glob('growth-*.bin'))) == 357
    assert supervisor.verify_supervised_arm(output, receipt['receipt_sha256']) == receipt
    with pytest.raises(FileExistsError):
        supervisor.run_arm({'mode': 'synthetic_control', 'arm': 'B1',
                            'behavior': 'finished'}, output, limits=limits)


def test_research_retained_artifact_above_default_cap_inventory_and_replay(tmp_path, monkeypatch):
    from betelgeuze_product.cpu_shape_comparison_supervisor_v1 import worker
    from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError

    run = tmp_path / 'run'
    run.mkdir()
    retained = run / 'events.jsonl'
    retained.write_bytes(b'x' * (3 * MIB))
    plan = {'prepared_protocol_sha256': 'b' * 64, 'implementation_sha256': 'c' * 64}
    monkeypatch.setattr(worker, '_load', lambda *args: (plan, None, None, None))
    # A retained failed row deliberately has no completed objective or diagnostic
    # claims. This test exercises inventory/replay only, with no molecular dispatch.
    row = {'schema_id': worker.SCHEMA, 'arm': 'B1', 'strength': worker.ARMS['B1'],
           'plan_sha256': 'a' * 64, **plan,
           'source_implementation_sha256': plan['implementation_sha256'],
           'worker_sha256': worker._worker_digest(), 'boundary': dict(worker.BOUNDARY),
           'status': 'failed_or_unknown', 'result_sha256': None, 'work': None,
           'error_type': 'SyntheticInterruption', 'diagnostic_status': 'not_started',
           'diagnostic_error_type': None, 'phase_costs': [], 'artifacts': worker._artifacts(tmp_path)}
    row.pop('implementation_sha256')
    row['row_sha256'] = worker.digest(row)
    assert row['artifacts']['run/events.jsonl']['bytes'] == 3 * MIB
    assert worker.verify_arm('unused', 'a' * 64, 'B1', tmp_path, row) == row
    with pytest.raises(ValueError, match='file limit'):
        supervisor.inventory(tmp_path, file_limit=2 * MIB)
    assert supervisor.inventory(tmp_path, file_limit=8 * MIB)
    retained.write_bytes(b'x' * (8 * MIB + 1))
    with pytest.raises((ResearchError, ValueError)):
        worker._artifacts(tmp_path)


def test_changed_output_filesystem_fails_before_receipts_and_workers(tmp_path, monkeypatch):
    monkeypatch.setattr(supervisor, 'research_storage_preflight',
                        lambda *args: {'filesystem_device': -1})
    monkeypatch.setattr(supervisor, 'write_json', _forbidden)
    monkeypatch.setattr(supervisor, 'run_arm', _forbidden)
    output = tmp_path / 'changed-filesystem'
    with pytest.raises(ValueError, match='filesystem differs'):
        supervisor.run_synthetic_comparison('unused', 'a' * 64, output,
                                             limits=research_limits())
    assert output.is_dir()
    assert list(output.iterdir()) == []
