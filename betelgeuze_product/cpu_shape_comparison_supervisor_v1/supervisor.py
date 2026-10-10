"""One-shot arm process groups with reservations, bounded writes and receipts."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import time
import threading

from .limits import Limits

SCHEMA = 'cpu_shape_arm_supervision/1.0.0'
PARENT_FILE_BYTES = 256 * 1024
PARENT_FILES_MAXIMUM = 64
ARMS = ('B0', 'B1', 'B2', 'B3')


class WholeComparisonTimeout(BaseException):
    """Whole-parent wall deadline, including inventory and publication."""


@contextmanager
def wall_deadline(seconds):
    if (type(seconds) not in (int, float) or not 0 < seconds <= 2700
            or threading.current_thread() is not threading.main_thread()
            or signal.getitimer(signal.ITIMER_REAL) != (0., 0.)):
        raise ValueError('fresh main-thread bounded wall watchdog required')
    previous = signal.getsignal(signal.SIGALRM)

    def expired(signum, frame):
        raise WholeComparisonTimeout('whole comparison wall deadline reached')

    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.)
        signal.signal(signal.SIGALRM, previous)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def sources():
    folder = Path(__file__).resolve().parent
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.glob('*.py'))}


def open_directory(path):
    path = Path(path).absolute()
    if '..' in path.parts:
        raise ValueError('directory traversal forbidden')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        result, fd = fd, None
        return result
    finally:
        if fd is not None:
            os.close(fd)


def new_directory(path):
    path = Path(path).absolute()
    if '..' in path.parts or len(path.parts) < 2:
        raise ValueError('confined absolute output required')
    fds = []
    try:
        parent = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        fds.append(parent)
        for part in path.parts[1:-1]:
            parent = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            fds.append(parent)
        os.mkdir(path.name, mode=0o700, dir_fd=parent)
        fd = os.open(path.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        os.fsync(parent)
        return path, fd
    finally:
        for fd in reversed(fds):
            os.close(fd)


def write_json(fd, name, value, limit=PARENT_FILE_BYTES):
    if '/' in name or name in ('.', '..'):
        raise ValueError('confined filename required')
    raw = (canonical(value) + '\n').encode()
    if len(raw) > limit:
        raise ValueError('supervisor receipt size bound exceeded')
    child = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
    try:
        with os.fdopen(child, 'wb', closefd=False) as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(child)
    finally:
        os.close(child)
    os.fsync(fd)


def read_json(path, limit=PARENT_FILE_BYTES):
    path = Path(path).absolute()
    directory = open_directory(path.parent)
    try:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
    finally:
        os.close(directory)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError('bounded regular JSON required')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise ValueError('JSON capacity exceeded')
        return json.loads(raw)
    finally:
        os.close(fd)


def inventory(directory, *, file_limit, maximum_files=256):
    guard = open_directory(directory)
    os.close(guard)
    rows = {}
    for root, directories, files in os.walk(directory, followlinks=False):
        if any((Path(root) / name).is_symlink() for name in directories):
            raise ValueError('supervision evidence symlink forbidden')
        for name in files:
            path = Path(root) / name
            if path.is_symlink() or len(rows) >= maximum_files:
                raise ValueError('supervision evidence capacity or symlink violation')
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_size > file_limit:
                    raise ValueError('supervision evidence file limit violation')
                hasher = hashlib.sha256()
                with os.fdopen(fd, 'rb', closefd=False) as stream:
                    while chunk := stream.read(65536):
                        hasher.update(chunk)
                after = os.fstat(fd)
                current = os.stat(path, follow_symlinks=False)
                fields = ('st_dev', 'st_ino', 'st_mode', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_nlink')
                before_identity = tuple(getattr(info, key) for key in fields)
                if (tuple(getattr(after, key) for key in fields) != before_identity
                        or tuple(getattr(current, key) for key in fields) != before_identity):
                    raise ValueError('supervisor artifact changed during inventory')
                rows[str(path.relative_to(directory))] = {'bytes': info.st_size, 'sha256': hasher.hexdigest()}
            finally:
                os.close(fd)
    return rows


def _wait_worker(child, timeout):
    deadline = time.monotonic() + timeout
    timed_out = False
    try:
        while True:
            pid, status, usage = os.wait4(child.pid, os.WNOHANG)
            if pid:
                child.returncode = os.waitstatus_to_exitcode(status)
                return usage, timed_out
            if time.monotonic() >= deadline:
                timed_out = True
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                _, status, usage = os.wait4(child.pid, 0)
                child.returncode = os.waitstatus_to_exitcode(status)
                return usage, timed_out
            time.sleep(min(.01, max(0., deadline - time.monotonic())))
    except BaseException:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        _, status, _ = os.wait4(child.pid, 0)
        child.returncode = os.waitstatus_to_exitcode(status)
        raise


def uncertainty(worker_result):
    process_unknown = worker_result is None
    row = {} if process_unknown else worker_result['row']
    simple_control = (row.get('status') == 'synthetic_completed'
                      and row.get('evidence_kind') == 'synthetic_control'
                      and type(row.get('base_calls')) is int)
    work = row.get('work')
    base_unknown = process_unknown or (not simple_control and (
        row.get('status') == 'failed_or_unknown' or work is None
        or work.get('actual_force_calls', 0) is None))
    diagnostic_unknown = process_unknown or row.get('diagnostic_status') == 'failed_or_unknown'
    return {'process_result_unknown': process_unknown,
            'base_work_unknown': base_unknown, 'diagnostic_work_unknown': diagnostic_unknown,
            'unknown_work_is_not_zero': process_unknown or base_unknown or diagnostic_unknown}


def run_arm(request, output_dir, *, limits=Limits(), remaining_wall_seconds=None):
    """Never accept an executable or retry an existing reservation directory."""
    if type(limits) is not Limits or request.get('arm') not in ARMS:
        raise ValueError('explicit bounded arm request required')
    if request.get('mode') not in ('prepared', 'synthetic_control'):
        raise ValueError('explicit source-bound worker mode required')
    source_manifest = sources()
    request = {'schema_id': SCHEMA, **request, 'limits': limits.to_dict(),
               'supervisor_sources': source_manifest}
    if request['schema_id'] != SCHEMA:
        raise ValueError('supervision request schema mismatch')
    path, fd = new_directory(output_dir)
    started = time.perf_counter_ns()
    try:
        write_json(fd, 'request.json', request)
        write_json(fd, 'started.json', {'schema_id': SCHEMA, 'request_sha256': digest(request),
            'retry_policy': 'never_retry_unknown_work', 'planned_arm': request['arm']})
        work_path, work_fd = new_directory(path / 'work')
        os.close(work_fd)
        environment = dict(os.environ)
        for key in ('PYTHONHOME', 'PYTHONSTARTUP'):
            environment.pop(key, None)
        environment.update(PYTHONPATH=str(Path(__file__).resolve().parents[2]),
            PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1',
            OPENBLAS_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1', PATH='/usr/bin:/bin')
        stderr_fd = os.open('worker-stderr.txt', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                            0o600, dir_fd=fd)
        try:
            child = subprocess.Popen([sys.executable, '-m',
                'betelgeuze_product.cpu_shape_comparison_supervisor_v1.launch',
                '--request', str(path / 'request.json'), '--expected-sha256', digest(request),
                '--parent-pid', str(os.getpid())], cwd=work_path, env=environment,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=stderr_fd,
                start_new_session=True)
        finally:
            os.close(stderr_fd)
        timeout = limits.wall_seconds if remaining_wall_seconds is None else min(
            limits.wall_seconds, remaining_wall_seconds)
        usage, timed_out = _wait_worker(child, max(.001, timeout))
        if source_manifest != sources():
            raise ValueError('supervisor implementation changed')
        files = inventory(path, file_limit=max(PARENT_FILE_BYTES, limits.file_bytes),
                          maximum_files=limits.write_reservations + 8)
        result_path = path / 'worker-result.json'
        worker_result = None
        if child.returncode == 0 and result_path.exists():
            worker_result = read_json(result_path, limits.file_bytes)
            if (worker_result.get('request_sha256') != digest(request)
                    or worker_result.get('supervisor_sources') != source_manifest):
                raise ValueError('worker result source/request binding mismatch')
        result = {'schema_id': SCHEMA, 'arm': request['arm'], 'request_sha256': digest(request),
            'supervisor_sources': source_manifest, 'limits': limits.to_dict(),
            'status': 'finished' if worker_result is not None else 'failed_or_unknown',
            'returncode': child.returncode, 'wall_watchdog_killed': timed_out,
            'wall_ns': time.perf_counter_ns() - started,
            'child_user_cpu_seconds': usage.ru_utime,
            'child_system_cpu_seconds': usage.ru_stime,
            'child_peak_rss_kib': usage.ru_maxrss,
            'worker_result': worker_result, 'files': files,
            'logical_bytes_before_finished_receipt': sum(r['bytes'] for r in files.values()),
            **uncertainty(worker_result),
            'automatic_retry_performed': False,
            'cpu_measurement': 'per_pid_wait4_user_system_and_peak_rss'}
        result['receipt_sha256'] = digest(result)
        write_json(fd, 'finished.json', result)
        return result
    finally:
        os.close(fd)


def logical_comparison_bound(limits):
    return ((3 * limits.write_reservations + min(limits.write_reservations, 16))
            * limits.file_bytes + PARENT_FILES_MAXIMUM * PARENT_FILE_BYTES)


def research_storage_preflight(output_dir, limits):
    """Observe available space on output filesystem; never claim reservation/quota.

    The one GiB margin covers metadata/other activity conservatively at admission,
    but concurrent consumers can still exhaust space. Such failure retains evidence
    and never authorizes retry or a resource increase.
    """
    if limits.resource_policy != 'research_161':
        return {'status': 'not_required_default_policy'}
    parent = open_directory(Path(output_dir).absolute().parent)
    try:
        info = os.fstatvfs(parent)
        filesystem_device = os.fstat(parent).st_dev
    finally:
        os.close(parent)
    available = info.f_bavail * info.f_frsize
    bound = logical_comparison_bound(limits)
    required = bound + 1024 ** 3
    if available < required:
        raise ValueError('research storage admission requires logical bound plus one GiB free')
    return {'status': 'admitted_observation_not_exclusive_reservation',
            'filesystem_device': filesystem_device, 'available_bytes': available,
            'required_available_bytes': required, 'logical_payload_bound_bytes': bound,
            'headroom_bytes': 1024 ** 3, 'physical_quota_or_preallocation': False}


def _run_comparison(plan_path, plan_sha256, output_dir, *, limits=Limits(),
                    total_wall_seconds=2700., synthetic=False):
    """Fixed four-arm orchestration with a distinct explicit synthetic lane."""
    if type(limits) is not Limits:
        raise ValueError('explicit bounded comparison limits required')
    if not 0 < total_wall_seconds <= 2700:
        raise ValueError('bounded comparison wall allowance required')
    storage_admission = research_storage_preflight(output_dir, limits)
    path, fd = new_directory(output_dir)
    started = time.monotonic()
    manifest = sources()
    try:
        if (limits.resource_policy == 'research_161'
                and os.fstat(fd).st_dev != storage_admission['filesystem_device']):
            raise ValueError('output filesystem differs from research storage admission')
        declared = {'schema_id': SCHEMA, 'plan_path': str(Path(plan_path).absolute()),
            'plan_sha256': plan_sha256, 'arms': list(ARMS), 'limits': limits.to_dict(),
            'total_wall_seconds': total_wall_seconds, 'supervisor_sources': manifest,
            'evidence_kind': 'synthetic_control' if synthetic else 'prepared_development',
            'logical_payload_bound_bytes': logical_comparison_bound(limits),
            'storage_admission': storage_admission,
            'bound_scope': 'trusted_audited_python_payload_bytes_excludes_filesystem_metadata',
            'scientifically_validated': False}
        write_json(fd, 'binding.json', declared)
        rows = []
        for arm in ARMS:
            remaining = total_wall_seconds - (time.monotonic() - started)
            if remaining <= 0:
                rows.append({'arm': arm, 'status': 'not_started_total_wall_exhausted'})
                continue
            selected = Limits(**{**limits.to_dict(), 'write_reservations':
                min(limits.write_reservations, 16) if arm == 'B0' else limits.write_reservations})
            request = {'mode': 'synthetic_control' if synthetic else 'prepared', 'arm': arm,
                       'plan_path': declared['plan_path'], 'plan_sha256': plan_sha256}
            if synthetic:
                request['behavior'] = 'prepared_analytic'
            rows.append(run_arm(request, path / arm, limits=selected, remaining_wall_seconds=remaining))
        if sources() != manifest:
            raise ValueError('supervisor source changed before publication')
        report = {**declared, 'rows': rows, 'denominator': {'planned': 4,
            'finished': sum(r['status'] == 'finished' for r in rows),
            'failed_or_unknown': sum(r['status'] == 'failed_or_unknown' for r in rows),
            'not_started': sum(r['status'].startswith('not_started') for r in rows)},
            'wall_seconds': time.monotonic() - started,
            'self_publication_cost_requires_outer_process_measurement': True}
        report['report_sha256'] = digest(report)
        write_json(fd, 'report.json', report)
        return report
    finally:
        os.close(fd)


def run_comparison(plan_path, plan_sha256, output_dir, *, limits=Limits(), total_wall_seconds=2700.):
    """Production arm route; explicit real-run approval is separately required."""
    return _run_comparison(plan_path, plan_sha256, output_dir, limits=limits,
                           total_wall_seconds=total_wall_seconds)


def run_synthetic_comparison(plan_path, plan_sha256, output_dir, *, limits=Limits(),
                             total_wall_seconds=2700.):
    """Same process orchestration, admitting only explicit synthetic input plans."""
    return _run_comparison(plan_path, plan_sha256, output_dir, limits=limits,
                           total_wall_seconds=total_wall_seconds, synthetic=True)


def verify_supervised_arm(output_dir, expected_receipt_sha256):
    """Force-free available-result verification; failed/unknown stays unknown."""
    root = Path(output_dir)
    request = read_json(root / 'request.json')
    receipt = read_json(root / 'finished.json')
    if receipt['receipt_sha256'] != expected_receipt_sha256 or digest(
            {k: v for k, v in receipt.items() if k != 'receipt_sha256'}) != expected_receipt_sha256:
        raise ValueError('supervisor receipt digest mismatch')
    if receipt['request_sha256'] != digest(request) or receipt['supervisor_sources'] != sources():
        raise ValueError('supervisor source/request mismatch')
    limits = Limits(**request['limits'])
    current = inventory(root, file_limit=max(PARENT_FILE_BYTES, limits.file_bytes),
                        maximum_files=limits.write_reservations + 8)
    current.pop('finished.json')
    if current != receipt['files']:
        raise ValueError('supervisor retained artifacts changed')
    if any(receipt.get(key) != value for key, value in uncertainty(receipt['worker_result']).items()):
        raise ValueError('supervised work uncertainty mismatch')
    if receipt['status'] == 'finished':
        worker_result = read_json(root / 'worker-result.json', limits.file_bytes)
        if worker_result != receipt['worker_result']:
            raise ValueError('retained worker result differs')
        if request['mode'] == 'prepared' or request.get('behavior') == 'prepared_analytic':
            from .worker import verify_arm
            verify_arm(request['plan_path'], request['plan_sha256'], request['arm'],
                       root / 'work', worker_result['row'])
    elif receipt['status'] != 'failed_or_unknown' or receipt['worker_result'] is not None:
        raise ValueError('invalid unknown-work result')
    return receipt
