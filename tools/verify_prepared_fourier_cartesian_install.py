"""Prepare synthetic inputs, then smoke-test installed Fourier Cartesian APIs.

Run this repository-only helper with a source/test-capable Python and supply a
separate installed-wheel Python via --python. No test or tools imports occur in
the isolated child, and --output must be a new directory outside the checkout.
This is synthetic execution evidence, not scientific or docking validation.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys


PROBE = r"""
from contextlib import ExitStack, contextmanager
from dataclasses import replace
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

root, checkout = (Path(value).resolve() for value in sys.argv[1:3])
assert sys.flags.isolated == 1 and 'PYTHONPATH' not in os.environ
assert Path.cwd().resolve() == root and not root.is_relative_to(checkout)
assert not any(Path(value).resolve().is_relative_to(checkout) for value in sys.path)

import torch
torch.set_num_threads(1)
from betelgeuze_product.cpu_refinement_fourier_v1 import cartesian, workflow
from betelgeuze_product.cpu_refinement_fourier_v1.evaluation import FourierFixedEvaluator
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError, coordinates_hex, digest
from betelgeuze_product.cpu_refinement_v1_3 import contracts, minimization as execution

def installed_only():
    prefix = Path(sys.prefix).resolve()
    for name in ('tools', 'tests'):
        assert importlib.util.find_spec(name) is None, name + ' leaked into the install'
        assert not any(key == name or key.startswith(name + '.') for key in sys.modules)
    origins = {}
    for name, module in tuple(sys.modules.items()):
        if name.startswith(('betelgeuze_product', 'betelgeuze_engine')):
            path = getattr(module, '__file__', None)
            if path is not None:
                path = Path(path).resolve()
                assert path.is_relative_to(prefix), (name, str(path), str(prefix))
                assert not path.is_relative_to(checkout), (name, str(path))
                origins[name] = str(path)
    for module in (cartesian, contracts, execution, workflow):
        assert module.__name__ in origins
    return origins

origins = installed_only()
protocol_path = root / 'inputs/protocol.json'
raw = protocol_path.read_bytes()
protocol_sha256 = hashlib.sha256(raw).hexdigest()
assert protocol_sha256 == sys.argv[3]
protocol = json.loads(raw)
assert protocol['evidence_kind'] == 'synthetic_control'
frozen, loaded = workflow.freeze(protocol)
ligand, parameters, _, fixed = loaded
assert frozen['payload']['protocol'] == protocol
binding = {
    'schema_id': cartesian.INPUT_SCHEMA,
    'candidate_id': protocol['candidate_id'],
    'prepared_protocol_sha256': protocol_sha256,
    'initial_coordinates_sha256': digest(coordinates_hex(ligand.coordinates)),
}
assert binding['initial_coordinates_sha256'] == protocol['initial_coordinates_sha256']

def inputs(algorithm):
    config = contracts.SolverConfig(
        algorithm=algorithm, max_objective_attempts=17, max_accepted_steps=4,
        max_restart_verifications=2, max_backtracks=3,
        initial_step_size=0.03, maximum_atom_displacement=0.05,
        force_tolerance=0.001,
    )
    return ligand, parameters, config, fixed, binding

def run(values, directory, **kwargs):
    system, model, config, environment, identity = values
    return cartesian.minimize_cartesian(
        system, model, config, fixed_environment=environment,
        run_dir=directory, binding=identity, **kwargs,
    )

def verify(values, directory):
    system, model, config, environment, identity = values
    return cartesian.verify_cartesian(
        system, model, config, fixed_environment=environment,
        run_dir=directory, binding=identity,
    )

def tree_bytes(directory):
    return {str(path.relative_to(directory)): path.read_bytes()
            for path in directory.rglob('*') if path.is_file()}

class ForbiddenNumericalWork(BaseException):
    pass

class SimulatedInterruption(BaseException):
    pass

def forbidden(*args, **kwargs):
    raise ForbiddenNumericalWork('new graph/force/component work forbidden')

@contextmanager
def no_numerical_work():
    with ExitStack() as stack:
        stack.enter_context(patch.object(execution, 'build_compact_radius_graph', forbidden))
        stack.enter_context(patch.object(FourierFixedEvaluator, 'evaluate', forbidden))
        stack.enter_context(patch.object(execution, 'components_document', forbidden))
        yield

def rejected(action):
    try:
        action()
    except ResearchError as error:
        return str(error)
    raise AssertionError('drift was not rejected')

results = {}
unknown_results = {}
drift_results = {}
initial_ligand = coordinates_hex(ligand.coordinates)
initial_receptor = coordinates_hex(fixed.receptor.coordinates)
for algorithm in ('sd', 'lbfgs'):
    values = inputs(algorithm)
    directory = root / algorithm
    paused = run(values, directory, pause_after_objective_attempts=1)
    assert paused['status'] == 'checkpointed'
    assert paused['checkpoint']['state']['attempts'] == 1
    assert paused['checkpoint']['state']['accepted'] == 0
    assert paused['work']['optimizer_objective_attempts'] == 1
    assert paused['work']['optimizer_graph_calls'] == paused['work']['optimizer_force_calls'] == 1
    assert paused['work']['actual_force_calls'] == 1
    assert paused['work']['restart_verification_attempts'] == 0
    before = tree_bytes(directory)
    with no_numerical_work():
        assert verify(values, directory) == paused
    assert tree_bytes(directory) == before

    complete = run(values, directory, resume=True)
    state, work = complete['checkpoint']['state'], complete['work']
    assert complete['schema_id'] == cartesian.RESULT_SCHEMA
    assert complete['status'] == 'max_accepted_steps_reached'
    assert complete['converged'] is False
    assert state['config'] == values[2].to_dict()
    assert state['accepted'] == 4 and state['attempts'] == 5
    assert state['original_coordinates'] == state['initial']['coordinates'] == initial_ligand
    assert work['optimizer_objective_attempts'] == work['optimizer_graph_calls'] == 5
    assert work['optimizer_force_calls'] == 5
    assert work['restart_verification_attempts'] == work['restart_graph_calls'] == work['restart_force_calls'] == 1
    assert work['actual_force_calls'] == work['known_completed_force_calls'] == 6
    assert work['failed_optimizer_force_calls'] == work['failed_restart_force_calls'] == work['unknown_pending_attempts'] == 0
    assert work['actual_force_calls'] <= work['max_total_force_calls'] == 19
    for key in ('scientifically_validated', 'claim_safe', 'customer_execution_allowed'):
        assert complete[key] is False
    assert coordinates_hex(ligand.coordinates) == initial_ligand
    assert coordinates_hex(fixed.receptor.coordinates) == initial_receptor
    before = tree_bytes(directory)
    with no_numerical_work():
        assert verify(values, directory) == complete
        assert run(values, directory, resume=True) == complete
    assert tree_bytes(directory) == before
    results[algorithm] = {'status': complete['status'], 'work': work,
                          'result_sha256': complete['result_sha256']}

    # Leave actual durable reservations unfinished, including restart work.
    for phase in ('initial', 'restart'):
        unknown = root / (algorithm + '-unknown-' + phase)
        if phase == 'restart':
            run(values, unknown, pause_after_objective_attempts=1)
        calls = []

        def interrupt(*args, **kwargs):
            calls.append(True)
            raise SimulatedInterruption('interrupted after durable reservation')

        with patch.object(FourierFixedEvaluator, 'evaluate', interrupt):
            try:
                run(values, unknown, resume=phase == 'restart')
            except SimulatedInterruption:
                pass
            else:
                raise AssertionError('synthetic interruption did not escape')
        events = [json.loads(line) for line in (unknown / 'events.jsonl').read_text().splitlines()]
        assert events[-1]['kind'] == ('objective_started' if phase == 'initial' else 'restart_started')
        before_unknown = tree_bytes(unknown)
        with no_numerical_work():
            for action in (lambda: run(values, unknown, resume=True), lambda: verify(values, unknown)):
                try:
                    action()
                except execution.PendingWorkError as error:
                    pending = error.work
                    assert pending['unknown_pending_attempts'] == 1
                    assert pending['actual_force_calls'] is None
                    assert pending['known_completed_force_calls'] == (0 if phase == 'initial' else 1)
                else:
                    raise AssertionError('unknown reservation was not blocked')
        assert calls == [True] and tree_bytes(unknown) == before_unknown
        unknown_results[algorithm + '-' + phase] = pending

    # A internally consistent changed model still cannot reuse an old journal.
    changed_model = replace(parameters, parameter_set_version='installed-smoke-drift')
    changed_fixed = replace(fixed, cross=replace(
        fixed.cross, ligand_base_parameters_sha256=changed_model.fingerprint_sha256,
    ))
    changed_values = ligand, changed_model, values[2], changed_fixed, binding
    before = tree_bytes(directory)
    with no_numerical_work():
        model_errors = [rejected(lambda: run(changed_values, directory, resume=True)),
                        rejected(lambda: verify(changed_values, directory))]
        sources = cartesian.implementation_sources()
        key = sorted(sources)[0]
        sources[key] = ('0' if sources[key][0] != '0' else '1') + sources[key][1:]
        with patch.object(cartesian, 'implementation_sources', lambda: sources):
            source_errors = [rejected(lambda: run(values, directory, resume=True)),
                             rejected(lambda: verify(values, directory))]
    assert tree_bytes(directory) == before
    drift_results[algorithm] = {'model': model_errors, 'implementation_identity': source_errors}

# Re-loading the prepared protocol must reject altered bound input bytes.
parameter_path = Path(protocol['parameters']['path'])
parameter_bytes = parameter_path.read_bytes()
try:
    parameter_path.write_text('{}')
    with no_numerical_work():
        input_error = rejected(lambda: workflow.freeze(protocol))
    assert 'bytes changed' in input_error
finally:
    parameter_path.write_bytes(parameter_bytes)
assert installed_only() == origins
summary = {
    'status': 'passed', 'evidence_kind': 'synthetic_installed_cartesian_control',
    'outside_checkout': True, 'isolated_python': True,
    'installed_modules': {module.__name__: origins[module.__name__]
                          for module in (cartesian, contracts, execution, workflow)},
    'prepared_protocol_sha256': protocol_sha256,
    'known_checkpoint_resume': True,
    'terminal_verify_and_resume_zero_graph_force_calls': True,
    'verify_and_completed_resume_no_file_changes': True,
    'unknown_reservations_not_reissued': True,
    'model_and_implementation_identity_drift_rejected': True,
    'bound_input_bytes_drift_rejected': input_error,
    'algorithms': results, 'unknown_reservations': unknown_results,
    'identity_drift_errors': drift_results,
    'scientifically_validated': False, 'claim_safe': False,
    'customer_execution_allowed': False,
}
(root / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary))
"""


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    checkout = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    if output.is_relative_to(checkout):
        parser.error("--output must be outside the source checkout")
    sys.path.insert(0, str(checkout))
    from tests.unit.test_cpu_refinement_fourier_v1_workflow import protocol

    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    inputs = output / "inputs"
    inputs.mkdir(mode=0o700)
    document = protocol(inputs)
    raw = (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode()
    (inputs / "protocol.json").write_bytes(raw)
    protocol_sha256 = hashlib.sha256(raw).hexdigest()
    (output / "protocol.sha256").write_text(protocol_sha256 + "\n")
    script = output / "installed-probe.py"
    script.write_text(PROBE)
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    child = subprocess.Popen(
        [str(args.python.absolute()), "-I", str(script), str(output),
         str(checkout), protocol_sha256],
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
        raise RuntimeError("installed Fourier Cartesian probe exceeded 180 seconds") from None
    (output / "stdout.log").write_text(stdout)
    (output / "stderr.log").write_text(stderr)
    if child.returncode:
        raise RuntimeError("installed Fourier Cartesian probe failed; inspect retained logs")
    print(stdout, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
