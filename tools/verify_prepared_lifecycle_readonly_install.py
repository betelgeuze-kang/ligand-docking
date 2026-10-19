"""Exercise an installed read-only adapter against one genuine synthetic journal.

The checkout supplies only the existing one-atom protocol fixture. A separate
installed producer evaluates that toy once. An installed consumer then reads
its retained journal from a deliberately different Torch thread/determinism
context. This is synthetic software evidence, without namespace qualification
or lifecycle/public-service acceptance.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


PRODUCER = r"""
import hashlib, importlib.util, json, pathlib, sys
import torch
root = pathlib.Path(sys.argv[1]).resolve()
assert pathlib.Path.cwd().resolve() == root
assert sys.flags.isolated and sys.dont_write_bytecode
# This is the actual producer contract used by the installed numerical worker.
torch.set_num_threads(1)
torch.set_num_interop_threads(1)
torch.use_deterministic_algorithms(False)
from betelgeuze_product.cpu_refinement_fourier_v1 import workflow
prefix = pathlib.Path(sys.prefix).resolve()
assert pathlib.Path(workflow.__file__).resolve().is_relative_to(prefix)
assert importlib.util.find_spec('tools') is None
assert not any(name.split('.')[0] in {'tools', 'tests', 'pytest'} for name in sys.modules)
protocol = json.loads((root / 'inputs/protocol.json').read_bytes())
assert protocol['evidence_kind'] == 'synthetic_control'
result = workflow.run(protocol, root / 'numerical')
(root / 'producer-result.json').write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
rows = ([] if result['baseline'] is None else [result['baseline']]) + result['invocations']
count = sum(row['work']['force_evaluation_calls'] for row in rows)
failed = sum(row['work']['failed_force_evaluation_calls'] for row in rows)
frozen = json.loads((root / 'numerical/frozen.json').read_bytes())
environment = frozen['payload']['environment']
summary = {
    'status': result['status'], 'binding': result['binding'],
    'known_force_evaluation_calls': count, 'known_failed_force_evaluation_calls': failed,
    'unknown_stage': result['unknown_stage'], 'frozen_environment': environment,
    'protocol_sha256': hashlib.sha256((root / 'inputs/protocol.json').read_bytes()).hexdigest(),
    'installed_workflow': str(pathlib.Path(workflow.__file__).resolve()),
    'workflow_source_sha256': hashlib.sha256(pathlib.Path(workflow.__file__).read_bytes()).hexdigest(),
    'evidence_kind': 'synthetic_control', 'scientifically_qualified': False,
}
(root / 'producer-summary.json').write_text(json.dumps(summary, sort_keys=True, indent=2) + '\n')
assert result['status'] == 'complete' and result['unknown_stage'] is None
assert type(count) is int and count > 0 and failed == 0
assert environment['torch_threads'] == environment['torch_interop_threads'] == 1
assert environment['deterministic_algorithms'] is False
print(json.dumps(summary, sort_keys=True))
"""


CONSUMER = r"""
import hashlib, importlib.util, json, pathlib, sys
import torch
root = pathlib.Path(sys.argv[1]).resolve()
assert pathlib.Path.cwd().resolve() == root
assert sys.flags.isolated and sys.dont_write_bytecode
# The consumer must not borrow the producer's process-global Torch settings.
torch.set_num_threads(2)
torch.set_num_interop_threads(2)
torch.use_deterministic_algorithms(True)
from betelgeuze_product import prepared_lifecycle_results as results
from betelgeuze_product.cpu_refinement_fourier_v1 import workflow
prefix = pathlib.Path(sys.prefix).resolve()
origins = {module.__name__: str(pathlib.Path(module.__file__).resolve())
           for module in (results, workflow)}
assert all(pathlib.Path(path).is_relative_to(prefix) for path in origins.values())
assert importlib.util.find_spec('tools') is None
assert not any(name.split('.')[0] in {'tools', 'tests', 'pytest'} for name in sys.modules)
def state():
    return {'torch_threads': torch.get_num_threads(),
            'torch_interop_threads': torch.get_num_interop_threads(),
            'deterministic_algorithms': torch.are_deterministic_algorithms_enabled()}
def tree():
    values = {}
    for path in sorted((root / 'numerical').rglob('*')):
        assert not path.is_symlink()
        if path.is_file():
            values[str(path.relative_to(root / 'numerical'))] = {
                'bytes': path.stat().st_size,
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    return values
protocol = json.loads((root / 'inputs/protocol.json').read_bytes())
produced = json.loads((root / 'producer-summary.json').read_bytes())
frozen = json.loads((root / 'numerical/frozen.json').read_bytes())
expected_environment = frozen['payload']['environment']
assert expected_environment == produced['frozen_environment']
assert expected_environment['torch_threads'] == expected_environment['torch_interop_threads'] == 1
assert expected_environment['deterministic_algorithms'] is False
parent_before, journal_before = state(), tree()
assert parent_before == {'torch_threads': 2, 'torch_interop_threads': 2, 'deterministic_algorithms': True}
observed, error = [], None
try:
    for with_report in (False, True):
        value = results._owning_adapter(protocol, root / 'numerical', with_report=with_report)
        observed.append(value)
        assert value['status'] == 'complete' and value['total_work_known'] is True
        assert value['binding'] == produced['binding'] == frozen['binding']
        assert value['known_force_calls'] == produced['known_force_evaluation_calls']
        assert value['evaluator'] == frozen['payload']['evaluator']
        assert value['read_only_environment'] == expected_environment
        assert state() == parent_before and tree() == journal_before
        if with_report:
            report = value['report']
            assert report['execution_status'] == 'complete'
            assert report['work']['known_force_evaluation_calls'] == produced['known_force_evaluation_calls']
            assert report['work']['total_force_evaluation_calls'] == produced['known_force_evaluation_calls']
            assert report['work']['known_failed_force_evaluation_calls'] == produced['known_failed_force_evaluation_calls']
            assert report['work']['report_force_evaluation_calls'] == 0
            assert report['chemical_validity'] is None and report['pose_accuracy'] is None
            assert report['pose_selection_admitted'] is False
        else:
            assert value['report'] is None
except BaseException as exception:
    error = {'class': type(exception).__name__, 'message': str(exception)}
parent_after, journal_after = state(), tree()
summary = {
    'status': 'passed' if error is None else 'failed', 'error': error,
    'adapter_calls': len(observed), 'observed_results': observed,
    'parent_before': parent_before, 'parent_after': parent_after,
    'parent_preserved': parent_after == parent_before,
    'journal_before': journal_before, 'journal_after': journal_after,
    'journal_preserved': journal_after == journal_before,
    'producer_known_force_evaluation_calls': produced['known_force_evaluation_calls'],
    'reader_additional_force_evaluation_calls': 0,
    'read_zero_EF_scope': 'Fixed production verify/report-only worker; returned report work and complete retained journal are unchanged.',
    'installed_origins': origins, 'tests_tools_pytest_leaked': False,
    'evidence_kind': 'synthetic_installed_readonly_regression',
    'scientifically_qualified': False, 'native_qualification_established': False,
    'lifecycle_acceptance_established': False,
}
(root / 'consumer-summary.json').write_text(json.dumps(summary, sort_keys=True, indent=2) + '\n')
assert parent_after == parent_before and journal_after == journal_before
assert not any(name.split('.')[0] in {'tools', 'tests', 'pytest'} for name in sys.modules)
print(json.dumps(summary, sort_keys=True))
raise SystemExit(0 if error is None else 1)
"""


def _write(path, value):
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    return hashlib.sha256(raw).hexdigest()


def _journal(directory):
    values = {}
    if not directory.exists():
        return values
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise RuntimeError("synthetic journal contains a symlink")
        if path.is_file():
            values[str(path.relative_to(directory))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return values


def _phase(python, output, name, source, environment, deadline, maximum):
    script = output / (name + ".py")
    with script.open("x") as handle:
        handle.write(source)
    timeout = min(maximum, deadline - time.monotonic())
    if timeout <= 0:
        raise RuntimeError("installed read-only regression deadline exhausted")
    command = [str(python), "-I", "-B", str(script), str(output)]
    _write(output / (name + "-intent.json"), {
        "argv": command, "timeout_seconds": timeout,
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
    })
    with (output / (name + "-stdout.log")).open("xb") as stdout, \
            (output / (name + "-stderr.log")).open("xb") as stderr:
        child = subprocess.Popen(command, cwd=output, env=environment, stdout=stdout,
                                 stderr=stderr, start_new_session=True)
        try:
            returncode = child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=5)
            _write(output / (name + "-result.json"), {
                "returncode": child.returncode, "deadline_exceeded": True,
                "automatic_reissue_allowed": False,
            })
            raise RuntimeError("installed read-only regression phase exceeded deadline") from None
    _write(output / (name + "-result.json"), {
        "returncode": returncode, "deadline_exceeded": False,
        "stdout_sha256": hashlib.sha256((output / (name + "-stdout.log")).read_bytes()).hexdigest(),
        "stderr_sha256": hashlib.sha256((output / (name + "-stderr.log")).read_bytes()).hexdigest(),
    })
    if returncode:
        raise RuntimeError("installed read-only regression failed; inspect retained " + name + " logs")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    checkout = Path(__file__).resolve().parents[1]
    output, python = args.output.resolve(), args.python.absolute()
    if output.is_relative_to(checkout) or python.is_relative_to(checkout):
        parser.error("installed Python and output must be outside the checkout")
    if not python.is_file():
        parser.error("installed Python does not exist")
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    deadline = time.monotonic() + 180
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(checkout))
    from tests.unit.test_cpu_refinement_fourier_v1_workflow import protocol

    inputs = output / "inputs"
    inputs.mkdir(mode=0o700)
    document = protocol(inputs)
    protocol_sha = _write(inputs / "protocol.json", document)
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment.update({"OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
                        "OPENBLAS_NUM_THREADS": "1", "PYTHONDONTWRITEBYTECODE": "1"})
    _write(output / "plan.json", {
        "schema_version": "installed_readonly_regression_plan/1.0.0",
        "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "fixture_sha256": hashlib.sha256((checkout / "tests/unit/test_cpu_refinement_fourier_v1_workflow.py").read_bytes()).hexdigest(),
        "protocol_sha256": protocol_sha, "python": str(python),
        "host_fixture_preparation_only": True, "total_deadline_seconds": 180,
        "synthetic_producer_runs_admitted": 1, "reader_adapter_calls_admitted": 2,
        "real_molecular_force_calls_admitted": False, "native_probes_admitted": False,
        "lifecycle_acceptance_claim_admitted": False, "automatic_reissue_allowed": False,
    })
    error, before, after = None, None, None
    try:
        _phase(python, output, "producer", PRODUCER, environment, deadline, 60)
        before = _journal(output / "numerical")
        _write(output / "journal-before-consumer.json", before)
        _phase(python, output, "consumer", CONSUMER, environment, deadline, 90)
        after = _journal(output / "numerical")
        if before != after:
            raise RuntimeError("installed read-only consumer changed the genuine journal")
    except BaseException as exception:
        error = {"class": type(exception).__name__, "message": str(exception)}
    finally:
        after = _journal(output / "numerical")
        _write(output / "journal-after-consumer.json", after)
    producer_path, consumer_path = output / "producer-summary.json", output / "consumer-summary.json"
    producer = json.loads(producer_path.read_bytes()) if producer_path.exists() else None
    consumer = json.loads(consumer_path.read_bytes()) if consumer_path.exists() else None
    summary = {
        "schema_version": "installed_readonly_regression/1.0.0",
        "status": "passed" if error is None else "failed", "error": error,
        "evidence_kind": "synthetic_installed_readonly_regression",
        "outside_checkout": True, "isolated_python": True,
        "synthetic_producer_force_evaluation_calls": producer["known_force_evaluation_calls"] if producer else None,
        "reader_additional_force_evaluation_calls": 0 if consumer and consumer["status"] == "passed" else None,
        "parent_context_preserved": consumer["parent_preserved"] if consumer else None,
        "full_journal_byte_hashes_preserved": before == after if before is not None else None,
        "producer_summary_sha256": hashlib.sha256(producer_path.read_bytes()).hexdigest() if producer else None,
        "consumer_summary_sha256": hashlib.sha256(consumer_path.read_bytes()).hexdigest() if consumer else None,
        "scientifically_qualified": False, "native_qualification_established": False,
        "lifecycle_acceptance_established": False, "automatic_reissue_allowed": False,
    }
    _write(output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    if error is not None:
        raise RuntimeError("installed read-only regression failed; retained output: " + str(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
