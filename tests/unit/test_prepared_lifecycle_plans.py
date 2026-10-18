"""Plan admission and dispatch authority; synthetic bytes, no force evaluation."""
from concurrent.futures import ThreadPoolExecutor
import json

import pytest

from betelgeuze_product import prepared_lifecycle as core
from tests.unit.test_prepared_lifecycle_store import make_service


@pytest.fixture
def service(tmp_path):
    return make_service(tmp_path)


def test_plan_is_retained_zero_dispatch_and_contains_no_private_paths(service):
    first = service.plan("fixture")
    assert first == service.plan("fixture") == service.get_plan(first["plan_id"])
    assert first["budget"]["force_call_ceiling"] == 19
    assert first["preflight"]["force_calls"] == first["preflight"]["numerical_dispatches"] == 0
    assert str(service.input_root) not in json.dumps(first)
    assert "source_evidence" in first["input_sha256"]
    assert service._claim() is None
    with service._connect() as connection:
        assert connection.execute("SELECT count(*) FROM prepared_jobs").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM prepared_invocations").fetchone()[0] == 0


def test_planned_and_legacy_submission_share_one_owner_and_key(service):
    plan = service.plan("fixture")
    legacy = service.submit("fixture", "same-key")
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(lambda _: service.execute(plan["plan_id"], plan["plan_sha256"], "same-key"), range(8)))
    assert {row["execution_id"] for row in rows} == {legacy["execution_id"]}
    with service._connect() as connection:
        assert connection.execute("SELECT count(*) FROM prepared_execution_plans").fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM prepared_jobs").fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM prepared_invocations").fetchone()[0] == 0
    claim = service._claim(legacy["execution_id"])
    assert claim["force_reserved"] == 19
    assert service._claim() is None


@pytest.mark.parametrize("kind", ["runtime", "source", "policy"])
def test_stale_plan_rejected_before_queue_or_reservation(service, monkeypatch, kind):
    plan = service.plan("fixture")
    if kind == "runtime":
        identity = core.runtime_identity()
        monkeypatch.setattr(core, "runtime_identity", lambda: {**identity, "python_executable_sha256": "0" * 64})
    elif kind == "source":
        sources = core.implementation_sources()
        monkeypatch.setattr(core, "implementation_sources", lambda: {**sources, "api/product_prepared.py": "0" * 64})
    else:
        monkeypatch.setitem(core.POLICY, "max_numerical_invocations", 3)
    with pytest.raises(core.LifecycleError) as error:
        service.execute(plan["plan_id"], plan["plan_sha256"], "stale")
    assert error.value.code == "STALE_PLAN"
    with service._connect() as connection:
        assert connection.execute("SELECT count(*) FROM prepared_jobs").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM prepared_invocations").fetchone()[0] == 0


def test_changed_input_cannot_be_dispatched_from_old_plan(service):
    plan = service.plan("fixture")
    (service.input_root / "fixture" / "ligand.json").write_text("changed")
    with pytest.raises(core.LifecycleError) as error:
        service.execute(plan["plan_id"], plan["plan_sha256"], "changed")
    assert error.value.code == "SOURCE_OR_MODEL_MISMATCH"
    assert service._claim() is None


def test_plan_digest_tamper_and_cross_tenant_are_refused(service):
    plan = service.plan("fixture")
    other = core.PreparedLifecycle(service.root, service.input_root, tenant_id="other")
    for operation in (lambda: other.get_plan(plan["plan_id"]),
                      lambda: other.execute(plan["plan_id"], plan["plan_sha256"], "other")):
        with pytest.raises(core.LifecycleError) as error:
            operation()
        assert error.value.http_status == 404
    with pytest.raises(core.LifecycleError) as error:
        service.execute(plan["plan_id"], "0" * 64, "tampered")
    assert error.value.code == "PLAN_INTEGRITY_FAILED"
    with service._transaction() as connection:
        connection.execute("UPDATE prepared_plans SET document_json='{}' WHERE plan_id=?", (plan["plan_id"],))
    with pytest.raises(core.LifecycleError) as error:
        service.get_plan(plan["plan_id"])
    assert error.value.code == "PLAN_INTEGRITY_FAILED"
    assert service._claim() is None


def test_execution_binds_plan_without_resetting_existing_cumulative_budget(service):
    plan = service.plan("fixture")
    initial = service.execute(plan["plan_id"], plan["plan_sha256"], "resume")
    claim = service._claim(initial["execution_id"])
    service._finish(claim, status="paused", numerical_state="paused", known_force=3,
                    wall=11, cpu=7, spawned=True)
    replay = service.execute(plan["plan_id"], plan["plan_sha256"], "resume")
    assert replay["status"] == "paused"
    assert replay["budget"]["known_force_calls"] == 3
    assert replay["budget"]["wall_seconds_spent"] == 11
    assert replay["budget"]["numerical_invocations"] == 1
    assert service._claim() is None
    service.resume(initial["execution_id"])
    second = service._claim(initial["execution_id"])
    assert second["force_reserved"] == 16
    assert second["reserved_wall"] == 289 and second["reserved_cpu"] == 293


@pytest.mark.parametrize("damage", ["plan_bytes", "plan_deleted", "binding_deleted", "binding_hash"])
def test_owner_rechecks_plan_custody_before_any_reservation(service, damage):
    plan = service.plan("fixture")
    execution = service.execute(plan["plan_id"], plan["plan_sha256"], "custody")["execution_id"]
    with service._transaction() as connection:
        if damage == "plan_bytes":
            connection.execute("UPDATE prepared_plans SET document_json='{}'")
        elif damage == "plan_deleted":
            connection.execute("DELETE FROM prepared_plans")
        elif damage == "binding_deleted":
            connection.execute("DELETE FROM prepared_execution_plans")
        else:
            connection.execute("UPDATE prepared_execution_plans SET checksum=?", ("0" * 64,))
    with pytest.raises(core.LifecycleError) as error:
        service._claim(execution)
    assert error.value.code == "PLAN_INTEGRITY_FAILED"
    with service._connect() as connection:
        assert connection.execute("SELECT count(*) FROM prepared_invocations").fetchone()[0] == 0
        assert service._row(connection, execution)["generation"] == 0


def test_owner_rechecks_current_policy_before_any_reservation(service, monkeypatch):
    plan = service.plan("fixture")
    execution = service.execute(plan["plan_id"], plan["plan_sha256"], "policy")["execution_id"]
    monkeypatch.setitem(core.POLICY, "max_numerical_invocations", 3)
    with pytest.raises(core.LifecycleError) as error:
        service._claim(execution)
    assert error.value.code == "STALE_PLAN"
    assert service.status(execution)["budget"]["numerical_invocations"] == 0


def test_public_plan_does_not_echo_arbitrary_admitted_solver_metadata(service):
    bundle = service.input_root / "fixture"
    path = bundle / "protocol.json"
    protocol = json.loads(path.read_text())
    protocol["solver"]["private_unused_field"] = "/private/path/credential"
    path.write_text(core.canonical(protocol))
    manifest_path = bundle / "admission.json"
    manifest = json.loads(manifest_path.read_text())
    import hashlib
    manifest["protocol_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path.write_text(core.canonical(manifest))
    plan = service.plan("fixture")
    assert "/private" not in json.dumps(plan)
    assert plan["solver"]["configuration_sha256"] == core.digest(protocol["solver"])


@pytest.mark.parametrize("terminal,known", [("complete", True), ("interrupted_unknown", False)])
def test_execute_replay_never_requeues_terminal_or_refreshes_unknown_work(service, terminal, known):
    plan = service.plan("fixture")
    execution = service.execute(plan["plan_id"], plan["plan_sha256"], "terminal")["execution_id"]
    claim = service._claim(execution)
    previous = service._finish(claim, status=terminal, numerical_state=terminal, known_force=3,
                               force_known=known, wall=9, cpu=8, spawned=True)
    replay = service.execute(plan["plan_id"], plan["plan_sha256"], "terminal")
    assert replay == previous
    assert replay["plan"] == {"plan_id": plan["plan_id"], "plan_sha256": plan["plan_sha256"]}
    assert replay["budget"]["total_force_calls"] == (3 if known else None)
    assert replay["budget"]["numerical_invocations"] == 1
    assert service._claim() is None
