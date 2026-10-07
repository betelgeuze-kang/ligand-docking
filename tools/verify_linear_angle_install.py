"""Synthetic installed linear-angle contracts, outside checkout and isolated."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

PROBE = r'''
import json
import math
from pathlib import Path
import sys
import torch
from betelgeuze_product.cpu_refinement_linear_angle_v1 import geometry, parameters, evaluation, cartesian
from betelgeuze_engine_v2.physics.reference_parameters import HarmonicAngleParameter, ReferenceParameterError
root = Path(sys.argv[1])
checkout = Path(sys.argv[2])
origins = {}
for module in (geometry, parameters, evaluation, cartesian):
    path = Path(module.__file__).resolve()
    assert not path.is_relative_to(checkout)
    assert "site-packages" in path.parts
    origins[module.__name__] = str(path)
a = torch.tensor([[1.,0.,0.], [1.,0.,0.]], dtype=torch.float64, requires_grad=True)
b = torch.tensor([[-2.,0.,0.],[-2.,1.e-8,0.]], dtype=torch.float64, requires_grad=True)
energy = geometry.harmonic_linear_angle_energy(a,b,100.)
assert energy[0] == 0 and energy[1] > 0
forces = torch.autograd.grad(energy.sum(), (a,b), create_graph=True)
assert all(torch.isfinite(f).all() for f in forces)
assert all(torch.count_nonzero(f[0]) == 0 for f in forces)
hessian = torch.autograd.functional.hessian(lambda x: geometry.harmonic_linear_angle_energy(x,b,100.).sum(),a)
assert torch.isfinite(hessian).all()
assert abs(hessian[0,1,0,1].item()-100.) < 1.e-12
try:
    HarmonicAngleParameter(0,1,2,math.pi,100.)
except ReferenceParameterError:
    pass
else:
    raise AssertionError("old domain was widened")
row = parameters.LinearHarmonicAngleParameter(0,1,2,math.pi,100.)
assert row.to_dict()["equilibrium_radians"] == math.pi
assert "cpu_prepared_linear_harmonic" in cartesian.RESULT_SCHEMA
summary = {"status":"passed", "evidence_kind":"synthetic_installed_linear_angle_control",
           "outside_checkout":True, "isolated_python":True, "installed_modules":origins,
           "endpoint_and_mixed_batch_gradients":True, "endpoint_hessian":True,
           "legacy_parameter_gate_unchanged":True, "scientifically_validated":False}
(root/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
print(json.dumps(summary))
'''


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    checkout = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    if output.is_relative_to(checkout):
        parser.error("output must be outside checkout")
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    script = output/"probe.py"
    script.write_text(PROBE)
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env["OMP_NUM_THREADS"] = "1"
    env["MKL_NUM_THREADS"] = "1"
    result = subprocess.run([str(args.python.absolute()), "-I", str(script), str(output), str(checkout)],
                            cwd=output, env=env, capture_output=True, text=True, timeout=120)
    (output/"stdout.log").write_text(result.stdout)
    (output/"stderr.log").write_text(result.stderr)
    if result.returncode:
        raise RuntimeError("installed linear angle smoke failed; inspect retained logs")
    # Copy only synthetic tests/fixture outside checkout. Isolated Python must
    # resolve every implementation module from the installed wheel, not source.
    members = ("tests/unit/test_cpu_linear_angle_v1.py",
               "tests/unit/test_cpu_linear_angle_independent.py",
               "tests/fixtures/linear_angle_independent_oracle.json")
    for member in members:
        target = output/member
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((checkout/member).read_bytes())
    contracts = subprocess.run(
        [str(args.python.absolute()), "-I", "-m", "pytest", "--rootdir="+str(output),
         "-c", "/dev/null", "--noconftest", "-p", "no:cacheprovider", "-W", "error", "-q",
         str(output/members[0]), str(output/members[1])],
        cwd=output, env=env, capture_output=True, text=True, timeout=120,
    )
    (output/"contracts.stdout.log").write_text(contracts.stdout)
    (output/"contracts.stderr.log").write_text(contracts.stderr)
    if contracts.returncode:
        raise RuntimeError("installed synthetic contracts failed; inspect retained logs")
    summary = json.loads((output/"summary.json").read_text())
    summary["isolated_installed_synthetic_contracts"] = "passed"
    (output/"summary.json").write_text(json.dumps(summary, indent=2)+"\n")
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
