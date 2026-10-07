"""Prepare synthetic inputs, then exercise the installed CLI outside checkout."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

PROBE = r"""
import hashlib, importlib.metadata, importlib.util, json, os, pathlib, subprocess, sys
root=pathlib.Path(sys.argv[1]).resolve();protocol=root/'inputs/protocol.json'
sha=hashlib.sha256(protocol.read_bytes()).hexdigest()
entries=importlib.metadata.distribution('betelgeuze-md-product').entry_points
assert any(e.name=='betelgeuze-prepared-fourier' and e.value=='betelgeuze_product.cpu_refinement_fourier_v1.workflow:main' for e in entries)
import betelgeuze_product.cpu_refinement_fourier_v1.workflow as workflow
assert pathlib.Path(workflow.__file__).resolve().is_relative_to(pathlib.Path(sys.prefix).resolve())
assert importlib.util.find_spec('tools') is None
assert not any(n=='tools' or n.startswith('tools.') or n=='tests' or n.startswith('tests.') for n in sys.modules)
entry=pathlib.Path(sys.executable).parent/'betelgeuze-prepared-fourier';assert entry.is_file()
env=dict(os.environ);env.pop('PYTHONPATH',None)
def call(action,directory=None,pause=None,expected=0):
    cmd=[sys.executable,'-I',str(entry),action,'--protocol',str(protocol),'--expected-protocol-sha256',sha]
    if directory is not None:cmd+=['--run-dir',str(directory)]
    if pause is not None:cmd+=['--pause-after-accepted-iterations',str(pause)]
    result=subprocess.run(cmd,cwd=root,env=env,capture_output=True,text=True,timeout=120)
    assert result.returncode==expected,(action,result.returncode,result.stderr)
    return json.loads(result.stdout) if result.stdout else None

def files(directory):return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.iterdir() if p.is_file()}
assert call('preflight')['force_calls']==0
run=root/'run';paused=call('run',run,1);assert paused['status']=='paused'
before=files(run);assert call('verify',run)==paused;assert files(run)==before
complete=call('resume',run);assert complete['status']=='complete'
assert complete['baseline']['work']['force_evaluation_calls']==1
assert complete['invocations'][0]['work']['force_evaluation_calls']==2
assert complete['invocations'][1]['work']['restart_verification_calls']==1
assert complete['pose_score'] is None and complete['pose_selection_admitted'] is False
before=files(run);assert call('verify',run)==complete;assert call('resume',run)==complete;assert files(run)==before
unknown=root/'unknown';partial=call('run',unknown,1)
intent={'binding':partial['binding'],'index':1,'previous_checkpoint_sha256':partial['final_checkpoint_sha256'],'pause_after_accepted_iterations':None}
(unknown/'invocation-001-intent.json').write_text(json.dumps(intent,sort_keys=True,separators=(',',':'))+'\n')
before=files(unknown);interrupted=call('resume',unknown,expected=2)
assert interrupted['status']=='interrupted_unknown' and files(unknown)==before
assert call('verify',unknown,expected=2)==interrupted
parameter=pathlib.Path(json.loads(protocol.read_bytes())['parameters']['path']);parameter.write_text('{}')
failed=subprocess.run([sys.executable,'-I',str(entry),'verify','--protocol',str(protocol),'--expected-protocol-sha256',sha,'--run-dir',str(run)],cwd=root,env=env,capture_output=True,text=True,timeout=120)
assert failed.returncode!=0
summary={'status':'passed','evidence_kind':'synthetic_installed_control','entrypoint_verified':True,
         'outside_checkout':True,'isolated_python':True,'known_checkpoint_resume':True,
         'verify_and_completed_resume_no_file_changes':True,'unknown_invocation_not_reissued':True,
         'source_tampering_rejected':True,'scientifically_validated':False,
         'installed_module':str(pathlib.Path(workflow.__file__).resolve())}
(root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
"""


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from tests.unit.test_cpu_refinement_fourier_v1_workflow import protocol

    output = args.output.resolve()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    inputs = output / "inputs"
    inputs.mkdir(mode=0o700)
    document = protocol(inputs)
    raw = (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode()
    (inputs / "protocol.json").write_bytes(raw)
    (output / "protocol.sha256").write_text(hashlib.sha256(raw).hexdigest() + "\n")
    script = output / "installed-probe.py"
    script.write_text(PROBE)
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    child = subprocess.Popen(
        [str(args.python.absolute()), "-I", str(script), str(output)],
        cwd=output,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout, stderr = child.communicate(timeout=180)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid, signal.SIGKILL)
        stdout, stderr = child.communicate()
        (output / "stdout.log").write_text(stdout)
        (output / "stderr.log").write_text(stderr)
        raise RuntimeError("installed Fourier probe exceeded 180 seconds") from None
    (output / "stdout.log").write_text(stdout)
    (output / "stderr.log").write_text(stderr)
    if child.returncode:
        raise RuntimeError("installed Fourier probe failed; inspect retained logs")
    print(stdout, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
