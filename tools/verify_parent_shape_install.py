"""Isolated installed parent-shape contracts; synthetic objectives only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

PROBE = r'''
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from betelgeuze_product.cpu_refinement_shape_v1 import reference, profile, cartesian
from betelgeuze_product.cpu_refinement_linear_angle_v1 import cartesian as linear_cartesian
from betelgeuze_product.cpu_refinement_v1_3 import kernel, journal, minimization
root, checkout = (Path(x).resolve() for x in sys.argv[1:3])
assert sys.flags.isolated == 1 and 'PYTHONPATH' not in os.environ
assert Path.cwd().resolve() == root and not root.is_relative_to(checkout)
assert not any(Path(x).resolve().is_relative_to(checkout) for x in sys.path)
for name in ('tests', 'tools'):
    assert importlib.util.find_spec(name) is None
origins = {}
for module in (reference, profile, cartesian, linear_cartesian, kernel, journal, minimization):
    path = Path(module.__file__).resolve()
    assert path.is_relative_to(Path(sys.prefix).resolve())
    assert not path.is_relative_to(checkout)
    origins[module.__name__] = {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
for name, module in tuple(sys.modules.items()):
    if name.startswith(('betelgeuze_product', 'betelgeuze_engine')) and getattr(module, '__file__', None):
        path = Path(module.__file__).resolve()
        assert path.is_relative_to(Path(sys.prefix).resolve()), (name,str(path))
        assert not path.is_relative_to(checkout)
identity = reference.MoleculeIdentity(('C0','H1'),('C','H'),((0,1,'synthetic_single'),),'synthetic-installed-two-atom')
parent = reference.ShapeReference(identity,((0.,0.,0.),(1.,0.,0.)), 'synthetic-control', 'synthetic', 'a'*64)
energies = {}
for strength in (0.,100.,1000.):
    contract = reference.ShapeContract(parent,strength)
    restored = reference.ShapeContract.from_json(contract.to_json(),expected_digest=contract.digest)
    result = restored.evaluate(((0.,0.,0.),(1.05,0.,0.)),identity=identity)
    assert abs(result.energy-strength*.05**2/2) < 1.e-12
    assert abs(result.forces[0][0]-strength*.05) < 1.e-10
    energies[str(strength)] = result.energy
summary = {'status':'passed','evidence_kind':'synthetic_installed_parent_shape_control',
 'outside_checkout':True,'isolated_python':True,'installed_modules':origins,
 'strengths':list(energies),'penalty_checks':energies,'molecular_evaluator_calls':0,
 'molecular_shape_arms_executed':False,'scientifically_validated':False}
(root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary))
'''

MEMBERS = (
    'tests/unit/test_cpu_parent_shape_reference.py',
    'tests/unit/test_cpu_parent_shape_profile.py',
    'tests/unit/test_cpu_parent_shape_cartesian.py',
    'tests/unit/test_cpu_parent_shape_linear_base.py',
    'tests/unit/test_cartesian_shape_profile_seam.py',
)


def _run(command, output, env, label):
    try:
        result = subprocess.run(command, cwd=output, env=env, capture_output=True,
                                text=True, timeout=180)
    except subprocess.TimeoutExpired as exc:
        (output/(label+'.stdout.log')).write_bytes(exc.stdout or b'')
        (output/(label+'.stderr.log')).write_bytes(exc.stderr or b'')
        raise RuntimeError('installed shape '+label+' exceeded 180 seconds') from exc
    (output/(label+'.stdout.log')).write_text(result.stdout)
    (output/(label+'.stderr.log')).write_text(result.stderr)
    if result.returncode:
        raise RuntimeError('installed shape '+label+' failed; inspect retained logs')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    checkout = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    if output.is_relative_to(checkout):
        parser.error('output must be outside checkout')
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    script = output/'probe.py'
    script.write_text(PROBE)
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    env.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
    python = str(args.python.absolute())
    _run([python, '-I', str(script), str(output), str(checkout)], output, env, 'probe')
    # Copy only standalone synthetic tests. No source implementation or pytest
    # path injection is permitted; isolated Python uses installed wheel modules.
    copied = {}
    for name in MEMBERS:
        target = output/name
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = (checkout/name).read_bytes()
        target.write_bytes(raw)
        copied[name] = hashlib.sha256(raw).hexdigest()
    _run([python, '-I', '-m', 'pytest', '--rootdir='+str(output), '-c', '/dev/null',
          '--noconftest', '-p', 'no:cacheprovider', '-W', 'error', '-q',
          '--junitxml='+str(output/'contracts.xml'),
          *(str(output/name) for name in MEMBERS)], output, env, 'contracts')
    summary = json.loads((output/'summary.json').read_text())
    summary.update(isolated_installed_synthetic_contracts='passed', copied_test_sha256=copied)
    (output/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary))
    return 0


if __name__ == '__main__':
    sys.exit(main())
