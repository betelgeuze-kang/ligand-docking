"""Synthetic registry contracts; fixture JSON is never sent to a force evaluator."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path

import pytest

from betelgeuze_product.prepared_lifecycle import (
    LifecycleError, PreparedLifecycle, canonical, register_admission, write_absent,
)


def fake_admission(inputs, admission_id="fixture", pause=1):
    bundle = inputs / admission_id
    bundle.mkdir(mode=0o700)
    refs = {}
    for name in ("ligand", "receptor", "parameters", "cross", "source_evidence"):
        value = {"source_files": []} if name == "source_evidence" else {"synthetic_metadata": name}
        raw = canonical(value).encode()
        path = bundle / (name + ".json")
        path.write_bytes(raw)
        refs[name] = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}
    protocol = {"schema_version": "prepared_fourier_development_protocol/1.0.0",
                "evidence_kind": "synthetic_control", **refs,
                "solver": {"minimization": {"max_iterations": 4, "max_backtracks": 3}}}
    (bundle / "protocol.json").write_text(canonical(protocol))
    register_admission(inputs, admission_id, bundle / "protocol.json",
                       initial_pause_after_accepted_iterations=pause)
    return bundle


def make_service(tmp_path):
    inputs = tmp_path / "inputs"
    inputs.mkdir(mode=0o700)
    fake_admission(inputs)
    return PreparedLifecycle(tmp_path / "state", inputs)


@pytest.fixture
def service(tmp_path):
    return make_service(tmp_path)


def test_registry_is_full_durable_and_same_key_concurrent_submit_inserts_once(service):
    with service._connect() as connection:
        assert connection.execute("PRAGMA synchronous").fetchone()[0] == 2
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(lambda _: service.submit("fixture", "same-key"), range(8)))
    assert len({r["execution_id"] for r in rows}) == 1
    row = rows[0]
    assert row["status"] == "queued" and row["qualified"] is False
    assert row["budget"]["limits"]["force_call_ceiling"] == 19
    assert row["budget"]["total_force_calls"] == 0


def test_idempotency_does_not_change_when_execution_placement_changes(service, monkeypatch):
    monkeypatch.setattr("os.sched_getaffinity", lambda _: {0, 23})
    first = service.submit("fixture", "same")
    monkeypatch.setattr("os.sched_getaffinity", lambda _: {1, 23})
    replay = service.submit("fixture", "same")
    assert replay["execution_id"] == first["execution_id"]
    assert replay["budget"]["limits"]["cpu_affinity"] == [0]


def test_any_single_available_cpu_is_valid_product_placement(service, monkeypatch):
    monkeypatch.setattr("os.sched_getaffinity", lambda _: {23})
    assert service.submit("fixture", "singleton")["budget"]["limits"]["cpu_affinity"] == [23]


def test_concurrent_first_use_constructors_share_private_registry(tmp_path):
    inputs = tmp_path / "inputs"
    inputs.mkdir(mode=0o700)
    fake_admission(inputs)
    state = tmp_path / "state"
    with ThreadPoolExecutor(max_workers=4) as pool:
        services = list(pool.map(lambda _: PreparedLifecycle(state, inputs), range(8)))
    rows = [item.submit("fixture", "first-use") for item in services]
    assert len({item["execution_id"] for item in rows}) == 1


def test_same_key_changed_request_conflicts_and_colon_tenant_is_scoped(service):
    row = service.submit("fixture", "same")
    fake_admission(service.input_root, "other")
    with pytest.raises(LifecycleError, match="different request") as error:
        service.submit("other", "same")
    assert error.value.code == "IDEMPOTENCY_CONFLICT"
    other = PreparedLifecycle(service.root, service.input_root, tenant_id="other:tenant")
    with pytest.raises(LifecycleError) as hidden:
        other.status(row["execution_id"])
    assert hidden.value.http_status == 404


def test_known_pause_resume_keeps_cumulative_work_and_complete_is_noop(service):
    execution = service.submit("fixture", "resume")["execution_id"]
    first = service._claim(execution)
    assert service.status(execution)["budget"]["force_calls_reserved"] == 19
    service._finish(first, status="paused", numerical_state="paused", known_force=3,
                    wall=2., cpu=1., spawned=True)
    service.resume(execution)
    second = service._claim(execution)
    assert second["resume"] is True and second["force_reserved"] == 16
    assert second["reserved_wall"] == 298 and second["reserved_cpu"] == 299
    done = service._finish(second, status="complete", numerical_state="complete", known_force=8,
                           wall=3., cpu=2., spawned=True)
    assert done["budget"]["numerical_invocations"] == 2
    assert done["budget"]["wall_seconds_spent"] == 5.
    assert done["budget"]["cpu_seconds_charged"] == 3.
    assert service.resume(execution) == done


def test_unknown_retains_prefix_reservation_and_cannot_be_claimed_or_resumed(service):
    execution = service.submit("fixture", "unknown")["execution_id"]
    claim = service._claim(execution)
    result = service._finish(claim, status="interrupted_unknown", numerical_state="interrupted_unknown",
                             force_known=False, wall=300, cpu=300, spawned=True)
    assert result["budget"]["total_force_calls"] is None
    assert result["budget"]["force_calls_reserved"] == 19
    assert service._claim() is None
    with pytest.raises(LifecycleError) as error:
        service.resume(execution)
    assert error.value.code == "RESUME_NOT_ADMITTED"


def test_fenced_stale_owner_cannot_publish_and_cancel_is_not_lease_ack(service):
    execution = service.submit("fixture", "cancel")["execution_id"]
    claim = service._claim(execution)
    cancelled = service.cancel(execution)
    assert cancelled["status"] == "cancel_requested"
    assert cancelled["cancel_state"] == "requested"
    with pytest.raises(LifecycleError) as error:
        service._finish({**claim, "owner_token": "wrong"}, status="complete", numerical_state="complete")
    assert error.value.code == "OWNER_FENCE_LOST"
    assert service.status(execution)["status"] == "cancel_requested"


def test_cumulative_budget_is_not_reset_on_resume(service):
    execution = service.submit("fixture", "budget")["execution_id"]
    claim = service._claim(execution)
    service._finish(claim, status="paused", numerical_state="paused", known_force=3,
                    wall=300., cpu=1., spawned=True)
    with pytest.raises(LifecycleError) as error:
        service.resume(execution)
    assert error.value.code == "BUDGET_EXHAUSTED"


@pytest.mark.parametrize("active", [False, True])
def test_confirmed_cancel_with_known_paused_checkpoint_can_explicitly_resume(service, active):
    execution = service.submit("fixture", "cancel-known")["execution_id"]
    claim = service._claim(execution)
    if active:
        service.cancel(execution)
        service._finish(claim, status="cancelled", numerical_state="paused", known_force=3, spawned=True)
    else:
        service._finish(claim, status="paused", numerical_state="paused", known_force=3, spawned=True)
        service.cancel(execution)
    assert service.resume(execution)["status"] == "resume_queued"
    assert service._claim(execution)["force_reserved"] == 16


def test_aggregate_publication_budget_rolls_back_registration_transaction(service):
    execution = service.submit("fixture", "publication-budget")["execution_id"]
    claim = service._claim(execution)
    root = service.root / "jobs" / execution
    root.mkdir(mode=0o700)
    paths = [root / "first.json", root / "second.json"]
    for path in paths:
        write_absent(path, {"schema_version": "synthetic_report", "payload": "x" * 128})
    with service._transaction() as connection:
        row = service._row(connection, execution)
        policy = json.loads(row["policy_json"])
        policy["output_bytes"] = paths[0].stat().st_size + 1
        connection.execute("UPDATE prepared_jobs SET policy_json=? WHERE execution_id=?", (canonical(policy), execution))
    with pytest.raises(LifecycleError) as error:
        service._finish(claim, status="complete", numerical_state="complete", artifacts=[(p, "report") for p in paths])
    assert error.value.code == "PUBLICATION_BUDGET_EXHAUSTED"
    assert service.artifacts(execution)["artifacts"] == []
    assert service.status(execution)["status"] == "running"


def test_opaque_artifact_metadata_hides_path_and_modified_bytes_fail(service):
    execution = service.submit("fixture", "artifact")["execution_id"]
    claim = service._claim(execution)
    root = service.root / "jobs" / execution
    root.mkdir(mode=0o700)
    output = root / "report.json"
    write_absent(output, {"schema_version": "synthetic_report", "chemical_validity": None})
    result = service._finish(claim, status="complete", numerical_state="complete",
                             artifacts=[(output, "retained_report")])
    metadata = result["artifacts"][0]
    assert "path" not in metadata and str(root) not in json.dumps(metadata)
    path, fetched = service.artifact(execution, metadata["artifact_id"])
    assert path == output and fetched == metadata
    output.write_text("changed")
    with pytest.raises(LifecycleError) as error:
        service.artifact(execution, metadata["artifact_id"])
    assert error.value.code == "ARTIFACT_PUBLICATION_UNKNOWN"


def test_admission_symlink_and_source_drift_reject_before_dispatch(service):
    bundle = service.input_root / "fixture"
    original = bundle / "ligand.json"
    backup = bundle / "saved.json"
    original.rename(backup)
    original.symlink_to(backup)
    with pytest.raises(LifecycleError) as unsafe:
        service.submit("fixture", "symlink")
    assert unsafe.value.code == "INVALID_ADMISSION"
    original.unlink()
    backup.rename(original)
    original.write_text("changed")
    with pytest.raises(LifecycleError) as error:
        service.submit("fixture", "drift")
    assert error.value.code == "SOURCE_OR_MODEL_MISMATCH"


def test_known_admission_id_does_not_authorize_another_tenant(service):
    other = PreparedLifecycle(service.root, service.input_root, tenant_id="other:tenant")
    with pytest.raises(LifecycleError) as error:
        other.submit("fixture", "guessed-id")
    assert error.value.code == "NOT_FOUND_OR_FORBIDDEN"
    assert error.value.http_status == 404
    with service._connect() as connection:
        assert connection.execute("SELECT count(*) FROM prepared_jobs").fetchone()[0] == 0


def test_active_status_keeps_total_unknown_until_owned_completion(service):
    execution = service.submit("fixture", "live-status")["execution_id"]
    service._claim(execution)
    status = service.status(execution)
    assert status["numerical_state"] == "running_unresolved"
    assert status["budget"]["known_force_calls"] == 0
    assert status["budget"]["total_force_calls"] is None
    assert status["budget"]["total_work_known"] is False
    assert "api/runner_process.py" in status["implementation_sources"]


def test_helper_only_source_drift_blocks_known_resume_without_source_mutation(service, monkeypatch):
    execution = service.submit("fixture", "helper-drift")["execution_id"]
    claim = service._claim(execution)
    service._finish(claim, status="paused", numerical_state="paused", known_force=3, spawned=True)
    original = Path.read_bytes

    def helper_drift(path):
        data = original(path)
        return data + b"# synthetic drift" if path.name == "runner_process.py" else data

    monkeypatch.setattr(Path, "read_bytes", helper_drift)
    with pytest.raises(LifecycleError) as error:
        service.resume(execution)
    assert error.value.code == "SOURCE_OR_MODEL_MISMATCH"
    assert service.status(execution)["budget"]["known_force_calls"] == 3


def test_runtime_binary_identity_drift_blocks_known_resume(service, monkeypatch):
    import betelgeuze_product.prepared_lifecycle as core
    execution = service.submit("fixture", "runtime-drift")["execution_id"]
    claim = service._claim(execution)
    service._finish(claim, status="paused", numerical_state="paused", known_force=3, spawned=True)
    original = core.runtime_identity()
    monkeypatch.setattr(core, "runtime_identity", lambda: {**original, "python_executable_sha256": "0" * 64})
    with pytest.raises(LifecycleError) as error:
        service.resume(execution)
    assert error.value.code == "SOURCE_OR_MODEL_MISMATCH"
