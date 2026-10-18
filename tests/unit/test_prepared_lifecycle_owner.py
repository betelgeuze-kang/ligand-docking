"""Trusted process dependency fixtures; no molecular evaluation or qualification."""
import json
from pathlib import Path
import threading

import pytest

from betelgeuze_product import prepared_lifecycle_owner as owner
from betelgeuze_product.prepared_lifecycle import LifecycleError, digest, write_absent
from tests.unit.test_prepared_lifecycle_store import make_service


@pytest.fixture
def service(tmp_path):
    return make_service(tmp_path)


@pytest.fixture(autouse=True)
def synthetic_runtime(monkeypatch):
    monkeypatch.setattr(owner, "require_runtime", lambda: {
        "qualified": True, "receipt_sha256": "synthetic-unit-only", "scope": "mocked_test"})


def fake_known_runner(status="paused", forces=3):
    def run(command, **kwargs):
        assert command[1:5] == ["-I", "-B", "-m", "betelgeuze_product.prepared_lifecycle_worker"]
        binding_path = Path(command[command.index("--binding") + 1])
        binding = json.loads(binding_path.read_text())
        attempt = Path(binding["attempt_root"])
        document = {"schema_version": "synthetic_test_only", "qualified": False}
        result = {"schema_version": "prepared_lifecycle_numerical_result/1.0.0",
                  "execution_id": binding["execution_id"], "generation": binding["generation"],
                  "status": status, "numerical_state": status,
                  "known_force_calls": forces, "total_work_known": True,
                  "report_sha256": digest(document)}
        write_absent(attempt / "result.json", result)
        write_absent(attempt / "report.json", document)
        return {"returncode": 0, "timed_out": False, "cancelled": False,
                "containment_error": "", "containment_evidence": {"namespace_exit_verified": True},
                "resource_usage": {"child_cpu_seconds": .25, "measurement_complete": True}, "applied_resources": {"synthetic": True}}
    return run


def test_owner_known_pause_then_resume_uses_same_fixed_child_and_cumulative_budget(service):
    execution = service.submit("fixture", "known")["execution_id"]
    paused = owner.run_one(service, execution_id=execution, process_runner=fake_known_runner())
    assert paused["status"] == "paused"
    assert paused["budget"]["known_force_calls"] == 3
    assert paused["budget"]["cpu_seconds_charged"] == .25
    service.resume(execution)
    done = owner.run_one(service, execution_id=execution,
                         process_runner=fake_known_runner("complete", 8))
    assert done["status"] == "complete" and done["budget"]["total_force_calls"] == 8
    assert done["budget"]["cpu_seconds_charged"] == .5
    assert done["budget"]["numerical_invocations"] == 2
    assert service.resume(execution) == done
    assert owner.run_one(service, process_runner=fake_known_runner()) is None


def test_cancel_requires_process_terminal_and_missing_result_stays_unknown(service):
    execution = service.submit("fixture", "cancel")["execution_id"]
    started = threading.Event()

    def controlled_runner(command, **kwargs):
        started.set()
        assert kwargs["cancellation_event"].wait(2.)
        return {"returncode": -9, "cancelled": True, "timed_out": False,
                "containment_error": "", "containment_evidence": {"namespace_exit_verified": True}}

    result = []
    thread = threading.Thread(target=lambda: result.append(owner.run_one(
        service, execution_id=execution, process_runner=controlled_runner)))
    thread.start()
    assert started.wait(2.)
    requested = service.cancel(execution)
    assert requested["cancel_state"] == "requested"
    thread.join(timeout=3.)
    assert not thread.is_alive()
    assert result[0]["status"] == "cancelled"
    assert result[0]["cancel_state"] == "confirmed_process_terminal"
    assert result[0]["numerical_state"] == "interrupted_unknown"
    assert result[0]["budget"]["total_force_calls"] is None
    with pytest.raises(LifecycleError):
        service.resume(execution)


def test_no_verified_namespace_exit_means_unknown_even_if_result_looks_complete(service):
    execution = service.submit("fixture", "uncontained")["execution_id"]

    def run(command, **kwargs):
        outcome = fake_known_runner("complete", 8)(command, **kwargs)
        outcome["containment_evidence"] = {"namespace_exit_verified": False}
        return outcome

    result = owner.run_one(service, execution_id=execution, process_runner=run)
    assert result["status"] == "interrupted_unknown"
    assert result["budget"]["total_force_calls"] is None


def test_unsupported_resource_gate_is_unqualified_zero_dispatch_without_fallback(service):
    class Unsupported(RuntimeError):
        code = "RESOURCE_CONTAINMENT_UNAVAILABLE"
        runner_start_admitted = False

    def unavailable(*args, **kwargs):
        raise Unsupported("synthetic unsupported platform")

    execution = service.submit("fixture", "resource")["execution_id"]
    result = owner.run_one(service, execution_id=execution, process_runner=unavailable)
    assert result["status"] == "unqualified"
    assert result["error"]["code"] == "RESOURCE_CONTAINMENT_UNAVAILABLE"
    assert result["budget"]["total_force_calls"] == 0
    assert result["budget"]["numerical_invocations"] == 0
    assert result["budget"]["cpu_seconds_charged"] == 0.
    assert result["qualified"] is False


def test_parent_start_gate_denial_is_zero_numerical_dispatch_and_never_resumed(service):
    execution = service.submit("fixture", "start-denied")["execution_id"]

    def denied(*args, **kwargs):
        return {"returncode": 125, "runner_start_admitted": False,
                "containment_evidence": {"namespace_exit_verified": True}}

    result = owner.run_one(service, execution_id=execution, process_runner=denied)
    assert result["status"] == "unqualified"
    assert result["budget"]["total_force_calls"] == 0
    assert result["budget"]["numerical_invocations"] == 0
    assert result["budget"]["cpu_seconds_charged"] == 300  # Namespace bootstrap usage was not measured.
    with pytest.raises(LifecycleError):
        service.resume(execution)


def test_prelaunch_storage_failure_does_not_leave_live_owner_or_dispatch(service, monkeypatch):
    execution = service.submit("fixture", "storage-denied")["execution_id"]
    monkeypatch.setattr(owner, "private_root", lambda *a, **k: (_ for _ in ()).throw(OSError("synthetic storage failure")))
    result = owner.run_one(service, execution_id=execution, process_runner=lambda *a, **k: pytest.fail("must not start"))
    assert result["status"] == "unqualified"
    assert result["budget"]["total_force_calls"] == 0
    assert result["budget"]["numerical_invocations"] == 0


def test_lost_owner_is_unknown_and_never_reacquired(service, monkeypatch):
    execution = service.submit("fixture", "lost")["execution_id"]
    service._claim(execution)
    monkeypatch.setattr(owner, "process_identity", lambda _pid: None)
    rows = owner.reconcile_lost_owners(service)
    assert rows[0]["status"] == "interrupted_unknown"
    assert rows[0]["budget"]["total_force_calls"] is None
    assert service._claim() is None


def test_result_publication_failure_poisoned_without_retry(service):
    execution = service.submit("fixture", "publication")["execution_id"]

    def fail_after_requested_launch(*args, **kwargs):
        raise OSError("synthetic publication uncertainty")

    result = owner.run_one(service, execution_id=execution, process_runner=fail_after_requested_launch)
    assert result["status"] == "interrupted_unknown"
    assert result["budget"]["wall_seconds_spent"] == 300.
    assert result["budget"]["cpu_seconds_charged"] == 300.
    assert result["budget"]["total_force_calls"] is None
    assert service._claim() is None


def test_readable_result_after_nonzero_exit_cannot_erase_publication_uncertainty(service):
    execution = service.submit("fixture", "fsync")["execution_id"]

    def nonzero_after_visible_result(command, **kwargs):
        outcome = fake_known_runner("complete", 8)(command, **kwargs)
        outcome["returncode"] = 1  # Complete bytes visible, publication failed.
        return outcome

    result = owner.run_one(service, execution_id=execution, process_runner=nonzero_after_visible_result)
    assert result["status"] == "interrupted_unknown"
    assert result["budget"]["known_force_calls"] == 8
    assert result["budget"]["total_force_calls"] is None
    assert result["budget"]["force_calls_reserved"] == 19
    with pytest.raises(LifecycleError):
        service.resume(execution)


def test_known_numerical_failure_is_distinct_from_transport_failure(service):
    execution = service.submit("fixture", "known-failed")["execution_id"]
    result = owner.run_one(service, execution_id=execution,
                           process_runner=fake_known_runner("failed", 1))
    assert result["status"] == "failed"
    assert result["numerical_state"] == "failed"
    assert result["budget"]["total_force_calls"] == 1
    assert result["error"]["code"] == "KNOWN_NUMERICAL_FAILURE"


def test_verified_completion_wins_cancel_race(service):
    execution = service.submit("fixture", "completion-race")["execution_id"]

    def completed(command, **kwargs):
        service.cancel(execution)
        outcome = fake_known_runner("complete", 8)(command, **kwargs)
        return {**outcome, "cancelled": True}

    result = owner.run_one(service, execution_id=execution, process_runner=completed)
    assert result["status"] == "complete"
    assert result["cancel_state"] == "completion_won_race"
    assert result["budget"]["total_force_calls"] == 8
    assert service.resume(execution) == result


def test_incomplete_cpu_measurement_charges_full_reservation(service):
    execution = service.submit("fixture", "cpu-unknown")["execution_id"]

    def incomplete(command, **kwargs):
        outcome = fake_known_runner()(command, **kwargs)
        outcome["resource_usage"] = {"child_cpu_seconds": .01, "measurement_complete": False}
        return outcome

    result = owner.run_one(service, execution_id=execution, process_runner=incomplete)
    assert result["budget"]["cpu_seconds_charged"] == 300
    with pytest.raises(LifecycleError) as error:
        service.resume(execution)
    assert error.value.code == "BUDGET_EXHAUSTED"


def test_public_resource_receipt_removes_nested_internal_paths():
    value = {"requested_limits": {"tree_root": "/private/job", "cpu_seconds": 300},
             "observed_affinity": [0], "cwd": "/private"}
    public = owner.public_resource_receipt(value)
    assert public == {"requested_limits": {"cpu_seconds": 300}, "observed_affinity": [0]}
    assert "/private" not in json.dumps(public)
