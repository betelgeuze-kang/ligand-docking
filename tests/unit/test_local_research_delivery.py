"""Actual local result verification and isolated-device-process failure controls.

All molecular data/model fixtures are newly generated synthetic data. Stub
children exercise process handling only and never count as AMD qualification.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import pytest

from betelgeuze_product import local_research_workflow as workflow
from betelgeuze_product import local_research_verify as verifier
from betelgeuze_product import rocm_diagnostic as rocm
from tests.unit.test_local_research_workflow import request, selector
from tests.unit.test_public_assay_selector_shadow import _row


def _write_json(path, data):
    path.write_text(json.dumps(data, allow_nan=False))


def _digests(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


def test_actual_shadow_physics_resume_and_offline_verification(tmp_path, monkeypatch):
    r = request(tmp_path)
    r["assay_shadow"] = selector(tmp_path, monkeypatch, [_row(), _row(smiles=""), _row()])
    run = tmp_path / "run"
    first = workflow.run_workflow(r, run_dir=run)
    assert first["exit_code"] == 2  # valid incomplete support, not overall success
    second = workflow.run_workflow(r, run_dir=run, resume=True)
    assert second["backend_executed"] is None
    before = _digests(run)
    for attempt in (None, 1, 2):
        observed = verifier.verify_run(run, attempt=attempt)
        assert observed["status"] == "intact", observed
        assert observed["workflow_status"] == "partial_or_failed"
        assert observed["workflow_exit_code"] == 2 and observed["exit_code"] == 0
        assert observed["html_verified"] is True
        assert sorted(observed["artifacts_verified"]) == ["assay-shadow.json", "physics.json", "report.html"]
        assert observed["source_authenticated"] is False
        assert observed["resume_authorized"] is False
        assert observed["execution_performed"] is False
    assert _digests(run) == before  # no journal or history mutation
    # Verification needs only saved receipts, not original molecular files.
    shutil.rmtree(tmp_path / "source")
    assert verifier.verify_run(run)["status"] == "intact"


@pytest.mark.parametrize("backend", ["cpu", "hip_safe", "hip_fast"])
def test_verify_preserves_blocked_or_successful_status(tmp_path, backend):
    r = request(tmp_path)
    r["backend"] = backend
    run = tmp_path / "run"
    result = workflow.run_workflow(r, run_dir=run)
    checked = verifier.verify_run(run)
    assert checked["status"] == "intact", checked
    assert checked["workflow_status"] == result["status"]
    assert checked["workflow_exit_code"] == result["exit_code"]
    assert checked["scientifically_validated"] is False


@pytest.mark.parametrize("filename", ["physics.json", "report.html", "report.json", "request.json"])
def test_mutated_artifacts_are_rejected_with_no_recalculation(tmp_path, monkeypatch, filename):
    r, run = request(tmp_path), tmp_path / "run"
    workflow.run_workflow(r, run_dir=run)
    path = (run if filename == "request.json" else run / "attempt-000001") / filename
    if filename == "report.json":
        payload = json.loads(path.read_text())
        payload["physics"]["denominator"]["evaluated"] += 1
        _write_json(path, payload)
    elif filename == "request.json":
        payload = json.loads(path.read_text())
        payload["request"]["backend"] = "hip_fast"
        _write_json(path, payload)
    else:
        raw = path.read_bytes()
        path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])  # same size, so hash is checked
    from tools.product import score_prepared_cross_interactions as consumer
    monkeypatch.setattr(consumer, "evaluate_request", lambda *a, **k: pytest.fail("verifier computed physics"))
    changed = _digests(run)
    result = verifier.verify_run(run)
    assert result["status"] == "invalid", result
    assert result["exit_code"] == 2
    assert _digests(run) == changed
    assert str(tmp_path) not in json.dumps(result)


@pytest.mark.parametrize("change", ["traversal", "absolute", "wrong_count", "boolean_bytes", "claim", "delete_receipt"])
def test_invalid_receipt_metadata_is_not_accepted(tmp_path, change):
    run = tmp_path / "run"
    workflow.run_workflow(request(tmp_path), run_dir=run)
    path = run / "attempt-000001/report.json"
    data = json.loads(path.read_text())
    if change == "traversal":
        data["artifacts"]["physics"]["name"] = "../../outside.json"
    elif change == "absolute":
        data["artifacts"]["physics"]["name"] = str(tmp_path / "private-input")
    elif change == "wrong_count":
        data["physics"]["poses"][0]["status"] = "failed"
    elif change == "boolean_bytes":
        data["artifacts"]["html"]["bytes"] = True
    elif change == "claim":
        data["scientifically_validated"] = True
    else:
        del data["artifacts"]["html"]
    _write_json(path, data)
    assert verifier.verify_run(run)["status"] == "invalid"


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo", "attempt_symlink", "lock_symlink"])
def test_nonregular_or_redirected_artifact_paths_are_rejected(tmp_path, kind):
    run = tmp_path / "run"
    workflow.run_workflow(request(tmp_path), run_dir=run)
    path = run / "attempt-000001/physics.json"
    outside = tmp_path / "outside"
    if kind == "attempt_symlink":
        attempt = run / "attempt-000001"
        attempt.rename(outside)
        attempt.symlink_to(outside, target_is_directory=True)
    elif kind == "lock_symlink":
        lock = run / ".workflow.lock"
        lock.rename(outside)
        lock.symlink_to(outside)
    else:
        path.rename(outside)
        if kind == "symlink":
            path.symlink_to(outside)
        elif kind == "hardlink":
            os.link(outside, path)
        else:
            os.mkfifo(path)
    assert verifier.verify_run(run)["status"] == "invalid"


def test_active_run_lock_is_respected(tmp_path):
    run = tmp_path / "run"
    workflow.run_workflow(request(tmp_path), run_dir=run)
    with (run / ".workflow.lock").open("r") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        observed = verifier.verify_run(run)
        assert observed["reason"] == "run_is_active"


def test_latest_interrupted_attempt_not_replaced_by_older_success(tmp_path, monkeypatch):
    run = tmp_path / "run"
    r = request(tmp_path)
    workflow.run_workflow(r, run_dir=run)
    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt
    monkeypatch.setattr(workflow, "_shadow_status", interrupt)
    # Same request binding is required; interrupt the evaluator on a resume.
    from tools.product import score_prepared_cross_interactions as consumer
    monkeypatch.setattr(consumer, "evaluate_request", interrupt)
    with pytest.raises(KeyboardInterrupt):
        workflow.run_workflow(r, run_dir=run, resume=True)
    latest = verifier.verify_run(run)
    assert latest["attempt"] == 2 and latest["status"] == "incomplete"
    assert verifier.verify_run(run, attempt=1)["status"] == "intact"


def test_backward_report_without_html_digest_is_explicitly_unverified(tmp_path):
    run = tmp_path / "run"
    workflow.run_workflow(request(tmp_path), run_dir=run)
    path = run / "attempt-000001/report.json"
    data = json.loads(path.read_text())
    del data["artifacts"]["html"]
    del data["artifact_integrity_policy"]
    del data["publication_policy"]
    (run / "attempt-000001/complete.json").unlink()
    _write_json(path, data)
    checked = verifier.verify_run(run)
    assert checked["status"] == "intact" and checked["html_verified"] is False
    assert checked["summary_receipt_verified"] is False


@pytest.mark.parametrize("attempt", [True, 0, -1, 10001, "1"])
def test_bad_attempt_selection_does_not_create_paths(tmp_path, attempt):
    run = tmp_path / "missing"
    assert verifier.verify_run(run, attempt=attempt)["exit_code"] == 2
    assert not run.exists()


def test_receipt_size_and_json_duplicate_limits(tmp_path, monkeypatch):
    run = tmp_path / "run"
    workflow.run_workflow(request(tmp_path), run_dir=run)
    with monkeypatch.context() as patch:
        patch.setattr(verifier, "MAX_REPORT_BYTES", 20)
        assert verifier.verify_run(run)["reason"] == "receipt_exceeds_capacity"
    path = run / "attempt-000001/report.json"
    path.write_text('{"attempt":1,"attempt":1}')
    assert verifier.verify_run(run)["status"] == "invalid"


def test_read_only_cli_is_lightweight_and_does_not_need_inputs(tmp_path):
    run = tmp_path / "run"
    workflow.run_workflow(request(tmp_path), run_dir=run)
    before = _digests(run)
    code = '''import sys
before=set(sys.modules)
from betelgeuze_product.local_research_workflow import main
assert main(["--verify-run","--run-dir",sys.argv[1]])==0
added=set(sys.modules)-before
assert not any(n.split(".")[0] in {"torch","numpy","rdkit","betelgeuze_engine","betelgeuze_engine_v2"} for n in added)
'''
    result = subprocess.run([sys.executable, "-c", code, str(run)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["status"] == "intact"
    assert _digests(run) == before


def _stub(monkeypatch, code):
    monkeypatch.setattr(rocm, "_probe_command", lambda fd: [sys.executable, "-S", "-c", code, str(fd)])


def test_probe_timeout_kills_child_and_does_not_import_parent_torch(tmp_path, monkeypatch):
    pidfile = tmp_path / "pid"
    _stub(monkeypatch, f"import os,sys,time;open({str(pidfile)!r},'w').write(str(os.getpid()));time.sleep(30)")
    monkeypatch.setattr(rocm.importlib, "import_module", lambda *a: pytest.fail("parent imported Torch"))
    started = time.monotonic()
    result = rocm.diagnose_rocm_isolated(probe=True, timeout_seconds=0.5)
    assert result["status"] == "probe_timeout"
    assert result["probe_cleanup"] == "child_reaped"
    assert time.monotonic() - started < 5
    pid = int(pidfile.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
    assert result["native_backend_qualified"] is False


def test_native_process_abort_is_recorded_not_propagated(monkeypatch):
    _stub(monkeypatch, "import os,resource;resource.setrlimit(resource.RLIMIT_CORE,(0,0));os.abort()")
    result = rocm.diagnose_rocm_isolated(probe=True, timeout_seconds=5)
    assert result["status"] == "probe_process_failed" and result["probe_returncode"] < 0
    assert result["probe_backend"] is None and result["probe_cleanup"] == "child_reaped"


@pytest.mark.parametrize("payload", [b"", b"not json", b'{"status":NaN}', b"x" * (rocm.MAX_PROBE_BYTES + 1)])
def test_probe_bad_receipt_is_bounded_and_sanitized(monkeypatch, payload):
    _stub(monkeypatch, f"import os,sys;os.write(int(sys.argv[1]),{payload!r})")
    result = rocm.diagnose_rocm_isolated(probe=True, timeout_seconds=5)
    assert result["status"] == "probe_failed"
    assert result["native_backend_qualified"] is False
    assert "not json" not in json.dumps(result)


def _packet():
    result = rocm.diagnose_rocm()
    result["status"] = "unavailable_not_torch_hip_build"
    return result


@pytest.mark.parametrize("change", ["native", "false_success", "nan", "duplicate", "private_error"])
def test_worker_receipt_cannot_promote_native_or_false_success(change):
    data = _packet()
    if change == "native":
        data["native_backend_qualified"] = True
    elif change == "false_success":
        data["status"] = "torch_hip_probe_passed"
    elif change == "nan":
        data["device_count"] = float("nan")
    elif change == "private_error":
        data["error_type"] = "/private/model"
    raw = json.dumps(data).encode()
    if change == "duplicate":
        raw = raw[:-1] + b',"status":"probe_failed"}'
    with pytest.raises(ValueError):
        rocm._probe_packet(raw)


def test_valid_child_receipt_and_real_cpu_process(monkeypatch):
    payload = json.dumps(_packet()).encode()
    with monkeypatch.context() as patch:
        _stub(patch, f"import os,sys;os.write(int(sys.argv[1]),{payload!r})")
        result = rocm.diagnose_rocm_isolated(probe=True)
        assert result["status"] == "unavailable_not_torch_hip_build"
    # Actual owned child process, not a simulated AMD execution.
    result = rocm.diagnose_rocm_isolated(probe=True)
    assert result["status"] in rocm._PROBE_STATUSES, result
    assert result["native_backend_qualified"] is False
    assert result["probe_cleanup"] == "child_reaped"


@pytest.mark.parametrize("timeout", [True, 0, -1, float("nan"), float("inf"), 121, "10"])
def test_probe_timeout_is_validated(timeout):
    with pytest.raises(ValueError):
        rocm.diagnose_rocm_isolated(probe=True, timeout_seconds=timeout)


def test_probe_failure_is_separate_from_successful_physics(tmp_path, monkeypatch):
    _stub(monkeypatch, "import os;os._exit(7)")
    result = workflow.run_workflow(request(tmp_path), run_dir=tmp_path / "run", probe_rocm=True)
    assert result["exit_code"] == 0
    assert result["physics"]["denominator"]["evaluated"] == 2
    assert result["rocm_observation"]["status"] == "probe_process_failed"
    assert result["backend_executed"] == "cpu"
    assert verifier.verify_run(tmp_path / "run")["status"] == "intact"


def test_verifier_holds_open_directory_across_path_replacement(tmp_path, monkeypatch):
    run = tmp_path / "run"
    workflow.run_workflow(request(tmp_path), run_dir=run)
    real = verifier._check_summary
    def swap(report, r):
        run.rename(tmp_path / "original")
        run.mkdir(mode=0o700)
        (run / "outside").write_text("must not be read or changed")
        return real(report, r)
    monkeypatch.setattr(verifier, "_check_summary", swap)
    assert verifier.verify_run(run)["status"] == "intact"
    assert list(run.iterdir()) == [run / "outside"]


def test_probe_kills_descendants_on_timeout(tmp_path, monkeypatch):
    child_pid = tmp_path / "child-pid"
    code = ("import subprocess,sys,time;"
            "p=subprocess.Popen([sys.executable,'-S','-c','import time;time.sleep(30)']);"
            f"open({str(child_pid)!r},'w').write(str(p.pid));time.sleep(30)")
    _stub(monkeypatch, code)
    result = rocm.diagnose_rocm_isolated(probe=True, timeout_seconds=0.5)
    assert result["status"] == "probe_timeout"
    pid = int(child_pid.read_text())
    for _ in range(100):
        path = Path(f"/proc/{pid}/stat")
        try:
            state = path.read_text().split(")", 1)[1].split()[0]
        except FileNotFoundError:
            break
        if state == "Z":  # exited child awaiting the container init's reap
            break
        time.sleep(0.01)
    else:
        pytest.fail("probe descendant remained alive")


def test_probe_does_not_publish_child_output(monkeypatch):
    _stub(monkeypatch, "import os,sys;os.write(1,b'/private/input');os.write(2,b'/private/model');sys.exit(3)")
    result = rocm.diagnose_rocm_isolated(probe=True)
    assert result["status"] == "probe_process_failed"
    assert "/private" not in json.dumps(result)


def test_probe_cancel_cleanup_does_not_swallow_cancellation(monkeypatch):
    class Child:
        pid = 2147480000
        calls = 0
        def wait(self, timeout):
            self.calls += 1
            if self.calls == 1:
                raise KeyboardInterrupt
            return 0
    child = Child()
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: child)
    calls = []
    monkeypatch.setattr(os, "killpg", lambda pid, sig: calls.append(pid))
    with pytest.raises(KeyboardInterrupt):
        rocm.diagnose_rocm_isolated(probe=True)
    assert calls == [child.pid] and child.calls == 2
