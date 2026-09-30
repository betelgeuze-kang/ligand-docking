"""Portable native dispatch boundaries; fixtures perform no molecular work."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import time

import pytest

SOURCE = Path(__file__).resolve().parents[2] / "docs/research/human_5ht6_sro_pose_recovery/runtime_execution.py"
spec = importlib.util.spec_from_file_location("sro_native_execution_test", SOURCE)
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


def saved(tmp_path, name, value):
    path = tmp_path / name
    path.write_bytes(runtime.encode(value))
    return runtime.pin(path)


@pytest.fixture
def observed():
    xyz = [[float(i).hex(), "0x0.0p+0", "0x0.0p+0"] for i in range(26)]
    pose = {"valid": False, "checks": {k: False for k in runtime.GEOMETRY_CHECKS},
            "evaluated_checks": {k: True for k in runtime.GEOMETRY_CHECKS}, "complete": True,
            "valid_within_evaluated_scope": False, "measurements": {}, "blockers": [],
            "not_evaluated_reasons": [], "claim_safe": False}
    return {"execution_complete": True, "score_calls": 2,
            "attempt": {"status": "success", "post_coordinates_binary64_hex": xyz},
            "rows": {arm: {"succeeded": True, "status": "success", "score": 1.0, "terms": {},
                           "pose_validity": deepcopy(pose), "validity_complete": True,
                           "coordinates_binary64_hex": deepcopy(xyz)} for arm in ("baseline", "refined")},
            "numerical_result": {"checkpoint": {"state": {"current": {"coordinates": xyz}}}}}


def test_complete_invalid_geometry_is_completed_without_admission(observed):
    assert runtime.completed_observations(observed) is observed
    assert not any(observed["rows"]["refined"]["pose_validity"]["checks"].values())


@pytest.mark.parametrize("arm", ["baseline", "refined"])
@pytest.mark.parametrize("field,value", [("succeeded", False), ("status", "failure"),
                                        ("score", float("nan")), ("terms", None)])
def test_score_failure_blocks_native_completion(observed, arm, field, value):
    observed["rows"][arm][field] = value
    with pytest.raises(runtime.ExecutionError, match="successful_finite_score_required"):
        runtime.completed_observations(observed)


def test_incomplete_geometry_blocks_native_completion(observed):
    observed["rows"]["refined"]["pose_validity"]["complete"] = False
    with pytest.raises(runtime.ExecutionError, match="complete_authenticated_geometry_required"):
        runtime.completed_observations(observed)


def test_final_row_cannot_substitute_another_trajectory_state(observed):
    observed["rows"]["refined"]["coordinates_binary64_hex"][0][0] = float(999).hex()
    with pytest.raises(runtime.ExecutionError, match="last_accepted_geometry_binding"):
        runtime.completed_observations(observed)


def test_captured_adapter_source_executes_without_bytecode_cache(tmp_path):
    path = tmp_path / "adapter.py"
    path.write_text("VALUE = 47\n")
    module = runtime.load_adapter(runtime.pin(path))
    assert module.VALUE == 47
    assert not (tmp_path / "__pycache__").exists()


def test_bound_rejects_mutated_or_duplicate_json(tmp_path):
    ref = saved(tmp_path, "sealed.json", {"value": 1})
    Path(ref["path"]).write_bytes(b'{"value": 2}')
    with pytest.raises(runtime.ExecutionError, match="immutable_input_changed"):
        runtime.bound(ref)
    path = tmp_path / "duplicate.json"
    path.write_bytes(b'{"a":1,"a":2}')
    with pytest.raises(runtime.ExecutionError, match="duplicate_json_key"):
        runtime.bound(runtime.pin(path))


@pytest.fixture
def supervisor(tmp_path, monkeypatch):
    # Shell-less test runners may be reparented to PID 1; use a controlled parent.
    monkeypatch.setattr(runtime.os, "getppid", lambda: 12345)
    plan = {"path": "/reviewed/plan.json", "sha256": "a" * 64, "bytes": 1}
    review = {"path": "/reviewed/review.json", "sha256": "b" * 64, "bytes": 1}
    start = time.monotonic_ns() - 1_000_000
    value = {"schema_id": "sro_native_case_supervisor/1", "case_id": "perturbed_01",
             "plan_ref": plan, "execution_review_ref": review, "controller_pid": os.getppid(),
             "started_at": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
             "started_monotonic_ns": start, "deadline_monotonic_ns": start + 7200 * 1_000_000_000,
             "native_output": str(tmp_path / "native")}
    return value, plan, review


def verify_supervisor(tmp_path, supervisor):
    value, plan, review = supervisor
    return runtime.supervisor_contract(saved(tmp_path, "supervisor.json", value), plan, review,
                                       "perturbed_01", tmp_path / "native")


def test_same_parent_and_exact_shared_deadline_required(tmp_path, supervisor):
    assert verify_supervisor(tmp_path, supervisor)["controller_pid"] == os.getppid()
    supervisor[0]["controller_pid"] += 10000
    with pytest.raises(runtime.ExecutionError, match="supervisor_parent_required"):
        verify_supervisor(tmp_path, supervisor)


def test_supervisor_cannot_extend_the_frozen_ceiling(tmp_path, supervisor):
    supervisor[0]["deadline_monotonic_ns"] += 1
    with pytest.raises(runtime.ExecutionError, match="case_deadline_required"):
        verify_supervisor(tmp_path, supervisor)


def test_supervisor_case_mismatch_rejected(tmp_path, supervisor):
    supervisor[0]["case_id"] = "perturbed_02"
    with pytest.raises(runtime.ExecutionError, match="supervisor_association"):
        verify_supervisor(tmp_path, supervisor)


def test_deadline_rejects_dispatch_before_count_or_call(tmp_path):
    ledger = runtime.DispatchLedger(tmp_path / "dispatch.jsonl", deadline_monotonic_ns=time.monotonic_ns() - 1)
    calls = []
    with pytest.raises(runtime.ExecutionError, match="case_deadline_exhausted"):
        ledger.wrap(lambda: calls.append(True), "force")()
    assert calls == [] and ledger.counts["force"] == 0 and not ledger.path.exists()


def test_failed_dispatch_keeps_attempt_and_error_receipts(tmp_path):
    ledger = runtime.DispatchLedger(tmp_path / "dispatch.jsonl", deadline_monotonic_ns=time.monotonic_ns() + 10**9)
    def failed():
        raise RuntimeError("fixture failure")
    with pytest.raises(RuntimeError):
        ledger.wrap(failed, "force")()
    events = [json.loads(line) for line in ledger.path.read_text().splitlines()]
    assert [event["event"] for event in events] == ["begin", "end"]
    assert events[-1]["error_type"] == "RuntimeError" and ledger.counts["force"] == 1
    assert ledger.active == []


def test_arbitrary_oracle_source_role_rejected_before_body_read(monkeypatch):
    phase = {"python_executable": "/usr/bin/python3", "python_binary_ref": {}, "argv_template": [],
             "source_refs": [{"path": "/forbidden/ligand-canonical.json"}], "receipt_name": "numerical-receipt.json"}
    monkeypatch.setattr(runtime, "bound", lambda *_args, **_kwargs: pytest.fail("unreviewed body read"))
    with pytest.raises(runtime.ExecutionError, match="oracle_source_roles_required"):
        runtime.oracle_phase_contract(phase)


@pytest.fixture
def saved_verifier():
    from contextlib import contextmanager
    from types import SimpleNamespace

    state = {"guarded": False, "calls": 0, "geometry_allowed": False}
    result = {"structural_verification_passed": True, "scoring_reexecuted": False,
              "numerical_evaluation_reexecuted": False}

    @contextmanager
    def guard(*, allow_saved_geometry=False):
        assert allow_saved_geometry is True
        state["guarded"] = True
        state["geometry_allowed"] = allow_saved_geometry
        try:
            yield
        finally:
            state["guarded"] = False

    def verify(request, output):
        assert state["guarded"] and state["geometry_allowed"]
        assert request == {"saved": True} and output == Path("saved-run")
        state["calls"] += 1
        return result

    return SimpleNamespace(forbid_physics=guard), SimpleNamespace(verify_output=verify), state, result


def test_saved_verification_uses_only_geometry_guard(saved_verifier):
    adapter, workflow, state, result = saved_verifier
    assert runtime.verify_saved_output(adapter, workflow, {"saved": True}, Path("saved-run")) is result
    assert state["calls"] == 1 and state["guarded"] is False


@pytest.mark.parametrize("field,value", [("structural_verification_passed", False),
                                         ("scoring_reexecuted", True),
                                         ("numerical_evaluation_reexecuted", True)])
def test_saved_verification_requires_semantics_and_no_new_calculation(saved_verifier, field, value):
    adapter, workflow, state, result = saved_verifier
    result[field] = value
    with pytest.raises(runtime.ExecutionError, match="read_only_semantic_verification_required"):
        runtime.verify_saved_output(adapter, workflow, {"saved": True}, Path("saved-run"))
    assert state["calls"] == 1 and state["guarded"] is False


def test_older_guard_rejected_before_native_work():
    from types import SimpleNamespace

    calls = []
    def old_guard():
        calls.append("guard invoked")
    with pytest.raises(runtime.ExecutionError, match="saved_geometry_guard_capability_required"):
        runtime.require_saved_geometry_guard(SimpleNamespace(forbid_physics=old_guard))
    assert calls == []


def test_saved_geometry_guard_default_must_stay_strict():
    from types import SimpleNamespace

    def permissive_guard(*, allow_saved_geometry=True):
        pytest.fail("capability review must not invoke guard")
    with pytest.raises(runtime.ExecutionError, match="saved_geometry_guard_capability_required"):
        runtime.require_saved_geometry_guard(SimpleNamespace(forbid_physics=permissive_guard))


def test_saved_geometry_guard_support_is_inspected_without_invocation(saved_verifier):
    adapter, _workflow, state, _result = saved_verifier
    runtime.require_saved_geometry_guard(adapter)
    assert state["calls"] == 0 and state["guarded"] is False
