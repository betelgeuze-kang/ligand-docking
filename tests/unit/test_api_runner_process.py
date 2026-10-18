"""Process-only controls; native probes execute fixed stdlib fixture children."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import pytest

from api import runner_process as process
from api.linux_runner_supervisor import validate_resource_limits


MIB = 1024 ** 2


def environment():
    return {"PATH": os.defpath, "LANG": "C.UTF-8", "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "PYTHONDONTWRITEBYTECODE": "1"}


def limits(root, **changes):
    # CPU23 belongs to an unrelated frozen P2 campaign; never change its affinity.
    available = sorted(set(os.sched_getaffinity(0)) - {23})
    if not available:
        pytest.skip("no separate CPU is available for a P4 native probe")
    result = {"wall_seconds": 3, "cpu_seconds": 2, "address_space_bytes": 256 * MIB,
              "file_bytes": 64 * 1024, "capture_bytes": 32 * 1024, "tree_bytes": 256 * 1024,
              "tree_root": str(root), "poll_seconds": .02, "cpu_affinity": [available[0]]}
    result.update(changes)
    return result


def native(root, code, *, resources=None, cancellation=None):
    return process.run_contained([sys.executable, "-I", "-B", "-c", code],
                                 cwd=root, environment=environment(), timeout_seconds=6,
                                 cancellation_event=cancellation,
                                 limits=resources if resources is not None else limits(root))


def test_shared_import_is_stdlib_only_in_a_fresh_isolated_interpreter():
    root = str(Path(__file__).resolve().parents[2])
    code = "\n".join([
        "import sys, importlib.abc, json",
        "class RejectApplicationImports(importlib.abc.MetaPathFinder):",
        " def find_spec(self,fullname,path=None,target=None):",
        "  if fullname.split('.')[0] in {'fastapi','pydantic','torch','numpy','betelgeuze_product'}:",
        "   raise RuntimeError('application dependency imported: '+fullname)",
        "sys.meta_path.insert(0,RejectApplicationImports())",
        "sys.path.insert(0," + repr(root) + ")",
        "from api.runner_process import resource_capabilities",
        "print(json.dumps(resource_capabilities()))",
    ])
    result = subprocess.run([sys.executable, "-I", "-B", "-c", code], check=True,
                            capture_output=True, text=True, timeout=10)
    capabilities = json.loads(result.stdout)
    assert capabilities["address_space_bytes"] is True
    assert capabilities["memory_bytes"] is False and capabilities["output_bytes"] is False


@pytest.mark.parametrize("unsupported", [{"memory_bytes": 6 * 1024 ** 3},
                                          {"output_bytes": 512 * MIB},
                                          {"aggregate_cpu_seconds": 300}, {"cpu_threads": 1}])
def test_unsupported_guarantees_fail_before_namespace_probe_or_spawn(tmp_path, monkeypatch, unsupported):
    monkeypatch.setattr(process, "require_linux_runner_supervisor_support",
                        lambda: pytest.fail("unsupported limits reached native probe"))
    monkeypatch.setattr(process.subprocess, "Popen", lambda *a, **k: pytest.fail("unsupported limits spawned"))
    with pytest.raises(process.ResourceContainmentUnavailable, match="RESOURCE_CONTAINMENT_UNAVAILABLE") as error:
        process.run_contained([sys.executable, "-c", "pass"], cwd=tmp_path,
                              environment=environment(), timeout_seconds=1, limits=unsupported)
    assert error.value.code == "RESOURCE_CONTAINMENT_UNAVAILABLE"
    assert error.value.runner_start_admitted is False


@pytest.mark.parametrize("invalid", [{"cpu_seconds": True}, {"file_bytes": 0},
                                      {"address_space_bytes": -1}, {"capture_bytes": 1.5},
                                      {"tree_bytes": 0}, {"poll_seconds": float("nan")},
                                      {"poll_seconds": 0}, {"cpu_affinity": [False]},
                                      {"cpu_affinity": [10 ** 6]}])
def test_resource_envelope_rejects_ambiguous_or_unenforceable_values(invalid):
    with pytest.raises(ValueError):
        validate_resource_limits(invalid)


def test_internal_tree_root_must_be_canonical_and_explicitly_budgeted(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(actual, target_is_directory=True)
    with pytest.raises(ValueError):
        validate_resource_limits({"tree_bytes": 1024, "tree_root": str(alias)})
    with pytest.raises(ValueError):
        validate_resource_limits({"tree_root": str(actual)})


def test_no_envelope_preserves_legacy_result_and_explicit_cwd_environment(tmp_path, monkeypatch):
    legacy = {"returncode": 0, "stdout": "ok", "stderr": "", "timed_out": False,
              "cancelled": False, "containment_error": "", "supervisor": "linux_pid_namespace_v1"}
    seen = []
    def fixed(command, **kwargs):
        seen.append((command, kwargs))
        return dict(legacy)
    monkeypatch.setattr(process, "_run_pid_namespace_command", fixed)
    child_env = environment()
    result = process.run_contained(["fixed-child"], cwd=tmp_path, environment=child_env,
                                   timeout_seconds=7)
    assert result == legacy and "resource_capabilities" not in result
    assert seen == [(["fixed-child"], {"cwd": tmp_path, "environment": child_env,
                                     "timeout_seconds": 7, "cancellation_event": None, "limits": None})]


def test_untrusted_containment_record_cannot_refund_reserved_cpu_with_claimed_zero(tmp_path, monkeypatch):
    def untrusted(*args, **kwargs):
        kwargs["_on_start_admitted"]()
        return {"returncode": 125, "containment_error": "supervisor nonce mismatch",
                "resource_usage": {"child_cpu_seconds": 0., "measurement_complete": True},
                "applied_resources": {"cpu_seconds": {"hard": 2}}}
    monkeypatch.setattr(process, "_run_pid_namespace_command", untrusted)
    outcome = native(tmp_path, "pass")
    assert outcome["resource_usage"]["child_cpu_seconds"] is None
    assert outcome["resource_usage"]["measurement_complete"] is False
    assert outcome["applied_resources"] is None
    assert outcome["containment_evidence"]["namespace_exit_verified"] is False
    assert outcome["runner_start_admitted"] is True


def test_pre_start_bootstrap_failure_reports_zero_worker_admission_only_before_start_gate(tmp_path, monkeypatch):
    def before_start(*args, **kwargs):
        return {"returncode": 125, "containment_error": "namespace initialization failed"}
    monkeypatch.setattr(process, "_run_pid_namespace_command", before_start)
    outcome = native(tmp_path, "must not execute")
    assert outcome["runner_start_admitted"] is False
    assert outcome["resource_usage"]["child_cpu_seconds"] is None
    assert outcome["containment_evidence"]["namespace_exit_verified"] is False


@pytest.mark.skipif(sys.platform != "linux", reason="actual Linux namespace/resource probe")
def test_native_child_inherits_exact_hard_limits_and_admitted_affinity(tmp_path):
    resources = limits(tmp_path)
    code = "import json,resource,os; print(json.dumps({'cpu':resource.getrlimit(resource.RLIMIT_CPU),'as':resource.getrlimit(resource.RLIMIT_AS),'file':resource.getrlimit(resource.RLIMIT_FSIZE),'affinity':sorted(os.sched_getaffinity(0))}))"
    result = native(tmp_path, code, resources=resources)
    assert result["returncode"] == 0, result
    assert result["runner_start_admitted"] is True
    assert not result["containment_error"] and result["containment_evidence"]["namespace_exit_verified"]
    child = json.loads(result["stdout"])
    assert child == {"cpu": [2, 2], "as": [256 * MIB] * 2, "file": [64 * 1024] * 2,
                     "affinity": resources["cpu_affinity"]}
    applied = result["applied_resources"]
    assert applied["cpu_seconds"]["soft"] == applied["cpu_seconds"]["hard"] == 2
    assert applied["cpu_affinity_admission"]["requested"] == resources["cpu_affinity"]
    assert applied["cpu_affinity_admission"]["observed_after"] == resources["cpu_affinity"]
    assert "not a resident-memory cap" in applied["scope"]["address_space_bytes"]
    assert result["resource_usage"]["measurement_complete"]
    assert result["resource_usage"]["child_cpu_seconds"] > 0
    assert result["resource_usage"]["child_peak_rss_bytes"] > 0


@pytest.mark.skipif(sys.platform != "linux", reason="actual Linux CPU-limit probe")
def test_native_cpu_limit_stops_fixed_busy_child_without_wall_timeout(tmp_path):
    result = native(tmp_path, "while True: pass", resources=limits(tmp_path, cpu_seconds=1, wall_seconds=5))
    assert result["returncode"] != 0 and result["timed_out"] is False, result
    assert result["containment_evidence"]["namespace_exit_verified"]
    assert result["applied_resources"]["cpu_seconds"]["hard"] == 1
    assert .5 <= result["resource_usage"]["child_cpu_seconds"] <= 2.5


@pytest.mark.skipif(sys.platform != "linux", reason="actual Linux address-space probe")
def test_native_address_space_cap_is_enforced_without_claiming_ram_cap(tmp_path):
    code = "\n".join(["import json,sys", "try:", " block=bytearray(512*1024*1024)",
                       "except MemoryError:", " print(json.dumps({'address_space_allocation_refused':True}))",
                       " sys.exit(7)", "sys.exit(0)"])
    result = native(tmp_path, code)
    assert result["returncode"] == 7, result
    assert json.loads(result["stdout"])["address_space_allocation_refused"]
    assert result["applied_resources"]["address_space_bytes"]["hard"] == 256 * MIB
    assert result["resource_capabilities"]["memory_bytes"] is False


@pytest.mark.skipif(sys.platform != "linux", reason="actual Linux file-size probe")
def test_native_per_file_size_cap_is_enforced_without_claiming_total_quota(tmp_path):
    target = tmp_path / "large.bin"
    code = "\n".join(["import errno,sys,json", "try:",
                       " with open('large.bin','wb') as handle: handle.write(b'x'*(128*1024))",
                       "except OSError as error:", " print(json.dumps({'errno':error.errno}))", " sys.exit(7)"])
    result = native(tmp_path, code)
    assert result["returncode"] == 7, result
    assert json.loads(result["stdout"])["errno"] != 0
    assert target.stat().st_size <= 64 * 1024
    assert result["resource_capabilities"]["output_bytes"] is False


@pytest.mark.skipif(sys.platform != "linux", reason="actual Linux bounded-capture probe")
def test_native_capture_is_read_bounded_and_truncation_is_failure(tmp_path):
    result = native(tmp_path, "import os; os.write(1,b'x'*(128*1024))",
                    resources=limits(tmp_path, capture_bytes=1024))
    assert result["returncode"] != 0 and result["resource_error"], result
    assert len(result["stdout"].encode()) == 1024
    assert result["captured_streams"]["stdout_truncated"]
    assert result["containment_evidence"]["namespace_exit_verified"]
    assert "sampled" in result["applied_resources"]["scope"]["capture_bytes"]


@pytest.mark.skipif(sys.platform != "linux", reason="actual Linux sampled-tree probe")
def test_native_tree_sampling_reports_overshoot_instead_of_claiming_hard_quota(tmp_path):
    result = native(tmp_path, "open('tree.bin','wb').write(b'x'*(32*1024))",
                    resources=limits(tmp_path, tree_bytes=1024))
    assert result["returncode"] != 0 and "tree" in result["resource_error"], result
    assert (tmp_path / "tree.bin").stat().st_size > 1024
    assert result["resource_usage"]["sampled_tree_peak_bytes"] >= 32 * 1024
    assert "possible overshoot" in result["resource_usage"]["sampled_tree_scope"]


@pytest.mark.skipif(sys.platform != "linux", reason="actual Linux resource-envelope cancellation probe")
def test_native_cancellation_still_waits_for_detached_descendant_cleanup(tmp_path):
    ready, late = tmp_path / "ready", tmp_path / "late"
    code = "\n".join([
        "import os,time", "first=os.fork()", "if first==0:", " os.setsid()", " second=os.fork()",
        " if second==0:", "  open('ready','w').write('ready')", "  time.sleep(1)",
        "  open('late','w').write('survived')", " os._exit(0)", "os.waitpid(first,0)",
        "while True: time.sleep(.05)",
    ])
    cancellation = threading.Event()
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(native, tmp_path, code, cancellation=cancellation)
        deadline = time.monotonic() + 4
        while not ready.exists() and not future.done() and time.monotonic() < deadline:
            time.sleep(.01)
        assert ready.exists(), future.result() if future.done() else "child did not reach ready gate"
        cancellation.set()
        result = future.result(timeout=8)
    assert result["cancelled"] and result["returncode"] != 0, result
    assert result["containment_evidence"]["namespace_exit_verified"]
    assert result["containment_error"] == ""
    time.sleep(1.05)
    assert not late.exists()
