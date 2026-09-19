"""Run the installed fixed-receptor CLI outside checkout, including restart."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from tests.unit.test_cpu_fixed_receptor_workflow import request_fixture


def verify(python: Path, output: Path):
    root = Path(__file__).resolve().parents[1]
    output.mkdir(parents=True, exist_ok=False)
    environment = {k: v for k, v in os.environ.items() if k != 'PYTHONPATH'}
    executable = str(python.absolute())
    records = []
    with tempfile.TemporaryDirectory(prefix='installed-fixed-receptor-') as directory:
        outside = Path(directory)
        request = request_fixture(outside)
        path = outside / 'request.json'
        path.write_text(json.dumps(request))
        module = 'betelgeuze_product.cpu_refinement_v1_2.fixed_receptor_workflow'
        commands = [
            [executable, '-I', '-c', 'from pathlib import Path; import sys; '
             'import betelgeuze_product.cpu_refinement_v1_2.fixed_receptor_workflow as w; '
             'p=Path(w.__file__).resolve(); '
             f'assert not p.is_relative_to(Path({str(root)!r})); '
             'assert p.is_relative_to(Path(sys.prefix)); print(p)'],
            [executable, '-I', '-m', module, 'preflight', str(path)],
            [executable, '-I', '-m', module, 'run', str(path), '--output', str(outside / 'run'), '--stop-after', '1'],
            [executable, '-I', '-m', module, 'run', str(path), '--output', str(outside / 'run'), '--resume'],
            [executable, '-I', '-m', module, 'verify', str(outside / 'run')],
        ]
        for command in commands:
            result = subprocess.run(command, cwd=outside, env=environment, text=True, capture_output=True, timeout=180)
            records.append({'command': command, 'returncode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
            (output / 'commands.json').write_text(json.dumps(records, indent=2))
            if result.returncode:
                raise RuntimeError('installed fixed-receptor CLI failed; retained output contains details')
        for name in ('request.json', 'plan.json', 'candidate-00000.json', 'candidate-00001.json', 'report.json', 'complete.json'):
            (output / name).write_bytes((outside / 'run' / name).read_bytes())
        plan = json.loads((outside / 'run' / 'plan.json').read_bytes())['payload']
        for name, expected in plan['implementation_sources'].items():
            if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
                raise RuntimeError('installed source differs from tested checkout')
        report = json.loads((outside / 'run' / 'report.json').read_bytes())
        if report['candidate_count'] != 2 or report['refinement_failure_count'] != 0 or report['interrupted_attempts_unknown_cost'] != 0:
            raise RuntimeError('installed run did not complete the synthetic refinements')
        verified = {'installed_cli_verified': True, 'outside_checkout': True, 'pythonpath_removed': True,
                    'isolated_python': True, 'source_files_verified': len(plan['implementation_sources']),
                    'resume_verified': True, 'scientifically_validated': False}
        (output / 'verification.json').write_text(json.dumps(verified, indent=2))
        return verified


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.python, args.output)))


if __name__ == '__main__':
    main()
