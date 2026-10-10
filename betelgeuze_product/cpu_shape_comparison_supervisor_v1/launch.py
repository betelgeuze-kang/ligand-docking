"""Fixed worker entry point, with no arbitrary command or executable dispatch."""
import argparse
import os
from pathlib import Path
import time

from .limits import Limits, install
from .supervisor import SCHEMA, digest, read_json, sources, write_json, open_directory


def synthetic(request, output):
    """Explicit non-molecular protocol controls used only by supervision tests."""
    behavior = request.get('behavior')
    allowed = {'finished', 'sleep', 'cpu', 'grow_file', 'many_files', 'spawn_child', 'retained_unknown'}
    if behavior not in allowed:
        raise ValueError('unknown synthetic behavior')
    fd = open_directory(output)
    try:
        write_json(fd, 'objective-started.json', {'kind': 'synthetic_objective_reserved',
                    'arm': request['arm'], 'pid': os.getpid()})
        if behavior == 'retained_unknown':
            return {'arm': request['arm'], 'status': 'failed_or_unknown', 'work': None,
                    'diagnostic_status': 'not_started', 'evidence_kind': 'synthetic_control',
                    'scientifically_validated': False}
        if behavior == 'sleep':
            time.sleep(60)
        elif behavior == 'cpu':
            while True:
                pass
        elif behavior == 'grow_file':
            child = os.open('growth.bin', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=fd)
            try:
                while True:
                    os.write(child, b'x' * 65536)
            finally:
                os.close(child)
        elif behavior == 'many_files':
            for index in range(1000):
                child = os.open(f'growth-{index:04d}.bin', os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                                0o600, dir_fd=fd)
                os.close(child)
        elif behavior == 'spawn_child':
            import subprocess
            subprocess.run(['true'], check=True)
        write_json(fd, 'objective-finished.json', {'kind': 'synthetic_objective_completed',
                   'base_calls': 1, 'optimizer_calls': 0 if request['arm'] == 'B0' else 1})
        return {'arm': request['arm'], 'status': 'synthetic_completed', 'base_calls': 1,
                'evidence_kind': 'synthetic_control', 'scientifically_validated': False}
    finally:
        os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', required=True)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--parent-pid', required=True, type=int)
    args = parser.parse_args(argv)
    request = read_json(args.request)
    if (request.get('schema_id') != SCHEMA or digest(request) != args.expected_sha256
            or request.get('supervisor_sources') != sources()):
        raise ValueError('worker request/source identity mismatch')
    mode = request.get('mode')
    expected = {'schema_id', 'mode', 'arm', 'limits', 'supervisor_sources'}
    expected |= {'behavior'} if mode == 'synthetic_control' else {'plan_path', 'plan_sha256'}
    if mode == 'synthetic_control' and request.get('behavior') == 'prepared_analytic':
        expected |= {'plan_path', 'plan_sha256'}
    if set(request) != expected or mode not in ('prepared', 'synthetic_control'):
        raise ValueError('exact worker descriptor required')
    limits = Limits(**request['limits'])
    budget = install(limits, args.parent_pid)
    root = Path(args.request).absolute().parent
    output = root / 'work'
    started, cpu = time.perf_counter_ns(), time.process_time_ns()
    if mode == 'synthetic_control' and request.get('behavior') == 'prepared_analytic':
        from .synthetic import execute_analytic
        row = execute_analytic(request['plan_path'], request['plan_sha256'], request['arm'], output)
    elif mode == 'synthetic_control':
        row = synthetic(request, output)
    else:
        from .worker import execute_arm
        row = execute_arm(request['plan_path'], request['plan_sha256'], request['arm'], output)
    if request['supervisor_sources'] != sources():
        raise ValueError('worker source changed')
    result = {'schema_id': SCHEMA, 'request_sha256': digest(request),
        'supervisor_sources': sources(), 'row': row,
        'worker_wall_ns': time.perf_counter_ns() - started,
        'worker_cpu_ns': time.process_time_ns() - cpu,
        'storage': budget.snapshot(), 'scientifically_validated': False}
    fd = open_directory(root)
    try:
        write_json(fd, 'worker-result.json', result, limits.file_bytes)
    finally:
        os.close(fd)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
