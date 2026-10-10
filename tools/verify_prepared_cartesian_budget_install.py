"""Exercise the opt-in budget CLI and API from a separately installed wheel.

The parent builds a synthetic fixture using repository tests; the isolated child
imports only installed modules. This is execution evidence, not docking evidence.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

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
from betelgeuze_product.cpu_prepared_cartesian_budget_v3 import workflow as w
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
kw = dict(model='fourier', accepted_steps=40, restart_verifications=1)
protocol = root / 'prepared.json'
args = ['--model','fourier','--accepted-steps','40','--restart-verifications','1']
cli = [sys.executable, '-I', '-m', w.__name__]
command = cli + ['prepare', *args, '--candidate-id','synthetic-installed-budget',
    '--evidence-kind','synthetic_control','--algorithm','lbfgs','--output',str(protocol)]
for key, ref in refs.items():
    command += ['--'+key.replace('_','-'), ref['path']]
prepared = json.loads(subprocess.check_output(command, cwd=root, text=True))
sha = prepared['protocol_sha256']
assert sha == hashlib.sha256(protocol.read_bytes()).hexdigest()
common = [*args,'--protocol',str(protocol),'--expected-protocol-sha256',sha]
def command(action, directory, *extra):
    return json.loads(subprocess.check_output(cli+[action,*common,'--run-dir',str(directory),*extra],
                                            cwd=root,text=True))
def snapshot(directory):
    return {str(p.relative_to(directory)):p.read_bytes() for p in directory.rglob('*') if p.is_file()}
def forbidden(*a, **k):
    raise AssertionError('verification performed numerical work')
uninterrupted = command('run', root/'direct')
paused = command('run', root/'resumed','--pause-after-objective-attempts','2')
assert paused['status'] == 'checkpointed'
resumed = command('resume', root/'resumed')
assert resumed['checkpoint']['state'] == uninterrupted['checkpoint']['state']
assert resumed['checkpoint']['state']['accepted'] == 40
assert resumed['work']['restart_force_calls'] == 1
assert resumed['work']['actual_force_calls'] == uninterrupted['work']['actual_force_calls']+1
for directory, result in [(root/'direct',uninterrupted),(root/'resumed',resumed)]:
    before = snapshot(directory)
    with patch.object(execution,'build_compact_radius_graph',forbidden), patch.object(FourierFixedEvaluator,'evaluate',forbidden):
        assert w.verify(protocol,sha,directory,**kw) == result
        assert w.run(protocol,sha,directory,**kw,resume=True) == result
    assert snapshot(directory) == before
class Interrupted(BaseException): pass
def interrupt(*a,**k): raise Interrupted()
unknown = {}
for phase in ('objective','restart'):
    directory = root/('unknown-'+phase)
    if phase == 'restart': w.run(protocol,sha,directory,**kw,pause_after_objective_attempts=1)
    with patch.object(FourierFixedEvaluator,'evaluate',interrupt):
        try: w.run(protocol,sha,directory,**kw,resume=phase=='restart')
        except Interrupted: pass
        else: raise AssertionError('interruption did not occur')
    before = snapshot(directory)
    with patch.object(FourierFixedEvaluator,'evaluate',forbidden):
        for action in (lambda:w.verify(protocol,sha,directory,**kw),
                       lambda:w.run(protocol,sha,directory,**kw,resume=True)):
            try: action()
            except execution.PendingWorkError as error:
                assert error.work['actual_force_calls'] is None
                assert error.work['unknown_pending_attempts'] == 1
                unknown[phase] = error.work
            else: raise AssertionError('unknown reservation retried')
    assert snapshot(directory) == before
summary = dict(status='passed',profile_id=w.PROFILE_ID,installed_module=w.__file__,
    outside_checkout=True,isolated_python=True,evidence_kind='synthetic_control',
    accepted_steps=40,uninterrupted_work=uninterrupted['work'],resumed_work=resumed['work'],
    identical_terminal_state=True,verify_objective_calls=0,completed_resume_objective_calls=0,
    unknown_reservations=unknown,scientifically_validated=False,shape_penalty_enabled=False)
(root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary))
'''


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    checkout = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    if output.is_relative_to(checkout):
        parser.error('--output must be outside checkout')
    sys.path.insert(0, str(checkout))
    from tests.unit.test_cpu_refinement_fourier_v1_workflow import protocol
    from betelgeuze_product.cpu_refinement_fourier_v1.workflow import REFS
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    inputs = output / 'inputs'
    inputs.mkdir(mode=0o700)
    fixture = protocol(inputs)
    (output/'fixture.json').write_text(json.dumps({name: fixture[name] for name in REFS}))
    probe = output/'probe.py'
    probe.write_text(PROBE)
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    child = subprocess.Popen(
        [str(args.python.absolute()), '-I', str(probe), str(output), str(checkout)],
        cwd=output, env=env, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, start_new_session=True,
    )
    try:
        stdout, stderr = child.communicate(timeout=180)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid, signal.SIGKILL)
        stdout, stderr = child.communicate()
        (output/'stdout.log').write_text(stdout)
        (output/'stderr.log').write_text(stderr)
        (output/'timeout.txt').write_text('Installed budget probe exceeded 180 seconds\n')
        raise RuntimeError('installed budget probe timed out; evidence retained') from None
    (output/'stdout.log').write_text(stdout)
    (output/'stderr.log').write_text(stderr)
    if child.returncode:
        raise RuntimeError('installed budget probe failed; inspect retained logs')
    print(stdout, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
