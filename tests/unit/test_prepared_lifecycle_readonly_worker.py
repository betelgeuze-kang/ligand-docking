"""No force calls: native stdlib transport/caps plus explicit mocked read seams."""
from __future__ import annotations

import builtins
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import types

import pytest

from betelgeuze_product import prepared_lifecycle_readonly_worker as worker
from betelgeuze_product import prepared_lifecycle_results as results
from betelgeuze_product.prepared_lifecycle import LifecycleError, digest


def request(directory):
    return {"schema_version": worker.REQUEST_SCHEMA, "nonce": "a"*64, "protocol": {},
            "protocol_sha256": digest({}), "directory": str(directory),
            "implementation_sources": {}, "runtime_identity": {}, "with_report": False}


def synthetic_transport(monkeypatch, code):
    """Keep actual pipes/groups/timeouts; explicitly substitute child contents."""
    original = subprocess.Popen
    children = []

    def launch(command, **kwargs):
        assert command == [sys.executable, "-I", "-B", "-m", "betelgeuze_product.prepared_lifecycle_readonly_worker"]
        assert kwargs["start_new_session"] and kwargs["close_fds"]
        assert "preexec_fn" not in kwargs
        assert not ({"HOME", "PYTHONPATH", "LD_PRELOAD"} & set(kwargs["env"]))
        child = original([sys.executable, "-I", "-B", "-c", code], **kwargs)
        children.append((child, Path(kwargs["cwd"])))
        return child

    monkeypatch.setattr(results.subprocess, "Popen", launch)
    return children


def response_code(modification="", exitcode=0):
    # This is a transport fixture, not evidence that its reported caps applied.
    return f'''
import hashlib,json,os,sys
raw=sys.stdin.buffer.read();r=json.loads(raw)
cost={{"CPU_seconds":.01,"worker_module_wall_seconds":.02,"peak_RSS_bytes":12345,
"new_force_calls":0,"execution_budget_charged":False,
"applied_resources":{{"RLIMIT_CPU":[{worker.CPU_SECONDS}]*2,"RLIMIT_AS":[{worker.ADDRESS_SPACE_BYTES}]*2,
"RLIMIT_FSIZE":[{worker.FILE_BYTES}]*2,"cpu_affinity":[int(os.environ["BETELGEUZE_READONLY_CPU"])],
"self_wall_limit_seconds":{worker.WALL_SECONDS},"self_wall_timer_remaining_seconds_at_admission":{worker.WALL_SECONDS}}}}}
value={{"schema_version":{worker.RESPONSE_SCHEMA!r},"nonce":r["nonce"],"request_sha256":hashlib.sha256(raw).hexdigest(),
"implementation_sources":r["implementation_sources"],"runtime_identity":r["runtime_identity"],"read_only_child_cost":cost,
"result":{{"binding":"b"*64,"status":"complete","known_force_calls":0,"total_work_known":True,
"report":None,"evaluator":{{}},"read_only_environment":{{"torch_threads":1,"torch_interop_threads":1,"deterministic_algorithms":False}}}}}}
{modification}
print(json.dumps(value),flush=True)
sys.exit({exitcode})
'''


def test_bounded_fixed_transport_returns_request_source_and_child_cost_without_parent_torch(tmp_path, monkeypatch):
    before = sys.modules.get("torch")
    children = synthetic_transport(monkeypatch, response_code())
    value = results._owning_adapter({}, tmp_path, with_report=False)
    assert value["read_only_environment"]["torch_interop_threads"] == 1
    assert value["read_only_child_cost"]["CPU_seconds"] == .01
    assert value["read_only_child_cost"]["execution_budget_charged"] is False
    assert sys.modules.get("torch") is before
    assert children[0][0].returncode == 0 and not children[0][1].exists()


@pytest.mark.parametrize("change", [
    'value["nonce"]="f"*64', 'value["request_sha256"]="0"*64',
    'value["implementation_sources"]={}', 'value["runtime_identity"]={}',
    'value["result"]["read_only_environment"]["torch_interop_threads"]=12',
    'value["read_only_child_cost"]["applied_resources"]["RLIMIT_CPU"]=[999,999]',
])
def test_transport_rejects_source_runtime_nonce_and_resource_rebinding(tmp_path, monkeypatch, change):
    synthetic_transport(monkeypatch, response_code(change))
    with pytest.raises(LifecycleError) as error:
        results._owning_adapter({}, tmp_path, with_report=False)
    assert error.value.code == "READ_VERIFICATION_FAILED"


def test_complete_json_from_nonzero_exit_is_never_adopted(tmp_path, monkeypatch):
    children = synthetic_transport(monkeypatch, response_code(exitcode=2))
    with pytest.raises(LifecycleError) as error:
        results._owning_adapter({}, tmp_path, with_report=False)
    assert error.value.code == "READ_VERIFICATION_FAILED" and children[0][0].returncode == 2


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_pipe_capture_overflow_kills_waits_then_removes_private_cwd(tmp_path, monkeypatch, stream):
    monkeypatch.setattr(worker, "MAX_RESPONSE_BYTES" if stream == "stdout" else "MAX_STDERR_BYTES", 1024)
    children = synthetic_transport(monkeypatch, f'import sys,time;sys.{stream}.write("x"*2048);sys.{stream}.flush();time.sleep(10)')
    with pytest.raises(LifecycleError, match="capture exceeds"):
        results._capture_worker(request(tmp_path), {})
    child, cwd = children[0]
    assert child.returncode == -signal.SIGKILL and not cwd.exists()


def test_wall_timeout_kills_unreaped_owned_group_before_cwd_removal(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, "WALL_SECONDS", .15)
    children = synthetic_transport(monkeypatch, 'import time;time.sleep(10)')
    original = results._kill_owned_group

    def ordered_cleanup(child):
        assert children[0][1].exists() and child.returncode is None
        original(child)

    monkeypatch.setattr(results, "_kill_owned_group", ordered_cleanup)
    with pytest.raises(LifecycleError, match="wall limit"):
        results._capture_worker(request(tmp_path), {})
    assert children[0][0].returncode == -signal.SIGKILL and not children[0][1].exists()


def test_request_bound_and_duplicate_nonfinite_unknown_fields_rejected(tmp_path, monkeypatch):
    value = request(tmp_path)
    assert worker._request(json.dumps(value).encode()) == value
    for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{}', b'x'*(worker.MAX_REQUEST_BYTES+1)):
        with pytest.raises(ValueError):
            worker._request(raw)
    value["callback"] = "public module input prohibited"
    with pytest.raises(ValueError):
        worker._request(json.dumps(value).encode())
    monkeypatch.setattr(results.subprocess, "Popen", lambda *a, **k: pytest.fail("oversize request spawned"))
    with pytest.raises(LifecycleError, match="request exceeds"):
        results._capture_worker({"oversize": "x"*worker.MAX_REQUEST_BYTES}, {})


def test_native_stdlib_resource_envelope_applies_before_any_torch_import():
    candidates = sorted(set(os.sched_getaffinity(0)) - {23})
    assert candidates
    path = str(Path(worker.__file__).resolve())
    code = f'''import importlib.util,json,sys
spec=importlib.util.spec_from_file_location("bounded_read_worker",{path!r})
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
assert "torch" not in sys.modules
print(json.dumps(m._apply_resources({candidates[0]})))
assert "torch" not in sys.modules
'''
    run = subprocess.run([sys.executable, "-I", "-B", "-c", code], capture_output=True, check=True, timeout=10)
    value = json.loads(run.stdout)
    assert value["RLIMIT_CPU"] == [worker.CPU_SECONDS]*2
    assert value["RLIMIT_AS"] == [worker.ADDRESS_SPACE_BYTES]*2
    assert value["RLIMIT_FSIZE"] == [worker.FILE_BYTES]*2
    assert value["cpu_affinity"] == [candidates[0]]
    assert 0 < value["self_wall_timer_remaining_seconds_at_admission"] <= worker.WALL_SECONDS


def test_native_child_self_wall_timer_survives_absent_controller():
    path = str(Path(worker.__file__).resolve())
    code = f'''import importlib.util,time
spec=importlib.util.spec_from_file_location("bounded_read_worker",{path!r})
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.WALL_SECONDS=.1;m._arm_wall_timer();time.sleep(10)
'''
    run = subprocess.run([sys.executable, "-I", "-B", "-c", code], capture_output=True, timeout=5)
    assert run.returncode == -signal.SIGALRM


def test_bootstrap_validates_source_bytes_before_reading_json(tmp_path, monkeypatch):
    monkeypatch.delitem(sys.modules, "torch", raising=False)
    package = tmp_path / "betelgeuze_product"
    package.mkdir()
    own, core = package / "prepared_lifecycle_readonly_worker.py", package / "prepared_lifecycle.py"
    own.write_bytes(b"owned fixed worker")
    core.write_bytes(b"owned fixed core")
    monkeypatch.setattr(worker, "__file__", str(own))
    monkeypatch.setattr(worker.sys, "prefix", str(tmp_path))
    monkeypatch.setattr(worker.sys, "flags", types.SimpleNamespace(isolated=1))
    monkeypatch.setattr(worker.sys, "dont_write_bytecode", True)
    monkeypatch.setenv("BETELGEUZE_READONLY_INSTALLED_ROOT", str(tmp_path))
    monkeypatch.setenv("BETELGEUZE_READONLY_WORKER_SHA256", hashlib.sha256(own.read_bytes()).hexdigest())
    monkeypatch.setenv("BETELGEUZE_READONLY_CORE_SHA256", hashlib.sha256(core.read_bytes()).hexdigest())
    assert worker._bootstrap() == tmp_path
    core.write_bytes(b"drifted core")
    with pytest.raises(ValueError):
        worker._bootstrap()
    monkeypatch.setitem(sys.modules, "torch", types.ModuleType("torch"))
    with pytest.raises(ValueError):
        worker._bootstrap()


def test_initializer_sets_both_thread_pools_only_in_child_function(monkeypatch):
    monkeypatch.delitem(sys.modules, "torch", raising=False)
    calls, state = [], {"intra": 12, "inter": 12}
    fake = types.SimpleNamespace(__file__=str(Path(sys.prefix)/"torch/__init__.py"),
        set_num_threads=lambda n: (calls.append(("intra", n)), state.update(intra=n)),
        set_num_interop_threads=lambda n: (calls.append(("inter", n)), state.update(inter=n)),
        get_num_threads=lambda: state["intra"], get_num_interop_threads=lambda: state["inter"])
    original = builtins.__import__

    def import_fixed(name, *args, **kwargs):
        return fake if name == "torch" else original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_fixed)
    assert "torch" not in sys.modules
    worker._initialize_torch()
    assert calls == [("intra", 1), ("inter", 1)] and state == {"intra": 1, "inter": 1}
