"""Verify the explicit 600-step facade using the shared isolated wheel probe runner."""
from verify_prepared_cartesian_budget_install import main

PROBE = r'''
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
import torch
from betelgeuze_product import cpu_prepared_cartesian_long_budget as w
from betelgeuze_product.cpu_refinement_fourier_v1.evaluation import FourierFixedEvaluator
from betelgeuze_product.cpu_refinement_v1_3 import minimization as execution
root, checkout = map(Path, sys.argv[1:3])
assert sys.flags.isolated and 'PYTHONPATH' not in os.environ
assert Path.cwd() == root and not root.is_relative_to(checkout)
assert Path(w.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
assert importlib.util.find_spec('tests') is None
assert importlib.util.find_spec('tools') is None
torch.set_num_threads(1)
refs = json.loads((root / 'fixture.json').read_text())
kw = dict(profile='accepted600_attempts641/1.0.0', model='fourier', restart_verifications=1)
assert w.PROFILE_ID == kw['profile']
solver = w.budget_config('sd', profile=kw['profile'], restart_verifications=1)
assert solver.max_accepted_steps == 600 and solver.max_objective_attempts == 641
assert solver.max_restart_verifications == 1
protocol = root / 'prepared.json'
args = ['--model', 'fourier', '--profile', kw['profile'], '--restart-verifications', '1']
cli = [sys.executable, '-I', '-m', w.__name__]
prepare = cli + ['prepare', *args, '--candidate-id', 'synthetic-installed-long-budget',
    '--evidence-kind', 'synthetic_control', '--algorithm', 'sd', '--output', str(protocol)]
for key, ref in refs.items():
    prepare += ['--' + key.replace('_', '-'), ref['path']]
prepared = json.loads(subprocess.check_output(prepare, cwd=root, text=True))
sha = prepared['protocol_sha256']
assert sha == hashlib.sha256(protocol.read_bytes()).hexdigest()
common = [*args, '--protocol', str(protocol), '--expected-protocol-sha256', sha]
def command(action, directory, *extra):
    return json.loads(subprocess.check_output(cli + [action, *common, '--run-dir', str(directory), *extra],
                                            cwd=root, text=True))
def snapshot(directory):
    return {str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob('*') if p.is_file()}
def forbidden(*a, **k):
    raise AssertionError('verification performed numerical work')
uninterrupted = command('run', root / 'direct')
paused = command('run', root / 'resumed', '--pause-after-objective-attempts', '2')
assert paused['status'] == 'checkpointed'
assert paused['work']['optimizer_objective_attempts'] == 2
resumed = command('resume', root / 'resumed')
assert resumed['checkpoint']['state'] == uninterrupted['checkpoint']['state']
for result in (uninterrupted, resumed):
    assert result['checkpoint']['state']['accepted'] == 600
    assert result['status'] == 'max_accepted_steps_reached' and result['converged'] is False
    assert result['work']['optimizer_objective_attempts'] == 601
    for key in ('scientifically_validated', 'claim_safe', 'customer_execution_allowed'):
        assert result[key] is False
assert uninterrupted['work']['restart_verification_attempts'] == 0
assert uninterrupted['work']['actual_force_calls'] == 601
assert resumed['work']['restart_verification_attempts'] == 1
assert resumed['work']['actual_force_calls'] == 602
for directory, result in [(root / 'direct', uninterrupted), (root / 'resumed', resumed)]:
    before = snapshot(directory)
    assert command('verify', directory) == result
    with patch.object(execution, 'build_compact_radius_graph', forbidden), patch.object(FourierFixedEvaluator, 'evaluate', forbidden):
        assert w.verify(protocol, sha, directory, **kw) == result
        assert w.run(protocol, sha, directory, **kw, resume=True) == result
    assert snapshot(directory) == before
summary = dict(status='passed', profile_id=w.PROFILE_ID, installed_module=w.__file__,
    outside_checkout=True, isolated_python=True, evidence_kind='synthetic_control',
    accepted_steps=600, max_objective_attempts=641,
    uninterrupted_work=uninterrupted['work'], resumed_work=resumed['work'],
    identical_terminal_state=True, verify_objective_calls=0, completed_resume_objective_calls=0,
    scientifically_validated=False, shape_penalty_enabled=False)
(root / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary))
'''


if __name__ == '__main__':
    raise SystemExit(main(probe_source=PROBE))
