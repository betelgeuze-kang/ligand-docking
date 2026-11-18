"""Queue, cancellation, planned source and public artifact regressions.

Only synthetic metadata and fixed test children are used; no force evaluation.
"""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from betelgeuze_product import prepared_lifecycle as core
from betelgeuze_product import prepared_lifecycle_owner as owner
from betelgeuze_product import prepared_lifecycle_results as results
from betelgeuze_product.prepared_lifecycle_worker import _bound_freeze
from tests.unit.test_prepared_lifecycle_owner import fake_known_runner
from tests.unit.test_prepared_lifecycle_results import retained, adapter, reseal_registered
from tests.unit.test_prepared_lifecycle_store import make_service, fake_admission


@pytest.fixture
def service(tmp_path):
    return make_service(tmp_path)


@pytest.mark.parametrize("damage,code", [
    ("changed_input", "SOURCE_OR_MODEL_MISMATCH"),
    ("missing_input", "NOT_FOUND_OR_FORBIDDEN"),
    ("plan_deleted", "PLAN_INTEGRITY_FAILED"),
    ("exhausted_budget", "BUDGET_EXHAUSTED"),
])
def test_bad_fifo_head_is_durably_rejected_without_blocking_healthy_next(service, monkeypatch, damage, code):
    plan = service.plan("fixture")
    bad = service.execute(plan["plan_id"], plan["plan_sha256"], "bad")["execution_id"]
    fake_admission(service.input_root, "healthy")
    healthy = service.submit("healthy", "good")["execution_id"]
    if damage == "changed_input":
        (service.input_root / "fixture/ligand.json").write_text("changed")
    elif damage == "missing_input":
        (service.input_root / "fixture/ligand.json").unlink()
    else:
        with service._transaction() as connection:
            if damage == "plan_deleted":
                connection.execute("DELETE FROM prepared_plans WHERE plan_id=?", (plan["plan_id"],))
            else:
                connection.execute("UPDATE prepared_jobs SET wall_spent=300 WHERE execution_id=?", (bad,))
    core.admission_document(service.input_root, "healthy")
    rejected = owner.run_one(service, process_runner=lambda *a, **k: pytest.fail("rejected work dispatched"))
    assert rejected["execution_id"] == bad
    assert rejected["status"] == "rejected_before_dispatch"
    assert rejected["error"]["code"] == code
    assert rejected["error"]["numerical_dispatches"] == 0
    assert rejected["budget"]["numerical_invocations"] == rejected["budget"]["known_force_calls"] == 0
    restarted = core.PreparedLifecycle(service.root, service.input_root)
    assert restarted.status(bad)["status"] == "rejected_before_dispatch"
    with restarted._connect() as connection:
        assert connection.execute("SELECT count(*) FROM prepared_invocations WHERE execution_id=?", (bad,)).fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM prepared_events WHERE execution_id=? AND kind='claim_rejected'", (bad,)).fetchone()[0] == 1
    monkeypatch.setattr(owner, "require_runtime", lambda: {"qualified": True, "scope": "synthetic_fixture_only"})
    next_result = owner.run_one(restarted, process_runner=fake_known_runner())
    assert next_result["execution_id"] == healthy and next_result["status"] == "paused"


def test_rejected_resume_keeps_prior_known_work_and_cumulative_budget(service):
    execution = service.submit("fixture", "resume")["execution_id"]
    claim = service._claim(execution)
    previous = service._finish(claim, status="paused", numerical_state="paused", known_force=3,
                               wall=9, cpu=7, spawned=True)
    service.resume(execution)
    (service.input_root / "fixture/ligand.json").write_text("changed")
    result = owner.run_one(service, process_runner=lambda *a, **k: pytest.fail("rejected resume dispatched"))
    assert result["status"] == "rejected_before_dispatch"
    assert result["numerical_state"] == "paused"
    assert result["budget"] == previous["budget"]
    with service._connect() as connection:
        assert service._row(connection, execution)["generation"] == 1
    with pytest.raises(core.LifecycleError, match="verified known paused"):
        service.resume(execution)


@pytest.mark.parametrize("status", ["paused", "failed", "complete"])
def test_cancel_after_runner_return_resolves_without_rewriting_manifest_outcome(service, monkeypatch, status):
    execution = service.submit("fixture", "late-cancel")["execution_id"]
    publish = owner.write_absent

    def cancel_after_watch_stopped(path, value):
        if path.name == "process.json":
            assert service.cancel(execution)["cancel_state"] == "requested"
        return publish(path, value)

    monkeypatch.setattr(owner, "write_absent", cancel_after_watch_stopped)
    monkeypatch.setattr(owner, "require_runtime", lambda: {"qualified": True, "scope": "synthetic_fixture_only"})
    result = owner.run_one(service, process_runner=fake_known_runner(status))
    expected = "completion_won_race" if status == "complete" else "confirmed_process_terminal"
    assert result["status"] == status and result["cancel_state"] == expected
    manifest = json.loads((service.root / "jobs" / execution / "attempts/000001/manifest.json").read_bytes())
    with service._connect() as connection:
        row = service._row(connection, execution)
        invocation = dict(connection.execute("SELECT * FROM prepared_invocations WHERE execution_id=?", (execution,)).fetchone())
    assert row["owner_pid"] is None and row["owner_token"] == ""
    assert manifest["status"] == invocation["status"] == row["status"] == status
    assert manifest["process_terminal_confirmed"] is True


@pytest.mark.parametrize("status", ["paused", "failed", "complete"])
def test_late_cancel_retained_lineage_and_report_stay_verified(service, monkeypatch, status):
    finish = service._finish

    def finish_after_cancel(claim, **kwargs):
        service.cancel(claim["execution_id"])
        return finish(claim, **kwargs)

    monkeypatch.setattr(service, "_finish", finish_after_cancel)
    identity, value, _, _ = retained(service, status=status)
    adapter(monkeypatch, value)
    document = results.report_execution(service, identity)
    assert document["fully_verified"] and document["total_work_known"]
    assert document["execution_status"] == document["numerical_state"] == status
    assert document["cancel_state"] == ("completion_won_race" if status == "complete" else "confirmed_process_terminal")


def test_metadata_plan_hashes_numerical_sources_without_importing_torch(tmp_path):
    root = str(Path(__file__).resolve().parents[2])
    code = f"""import sys
from pathlib import Path
sys.path.insert(0, {root!r})
from tests.unit.test_prepared_lifecycle_store import make_service
service = make_service(Path({str(tmp_path)!r}))
plan = service.plan('fixture')
assert 'betelgeuze_product/cpu_refinement_fourier_v1/workflow.py' in plan['numerical_implementation_sources']
assert 'betelgeuze_product/cpu_refinement_v1_2/minimization.py' in plan['numerical_implementation_sources']
assert not any(name.split('.')[0] in {{'torch','numpy','fastapi'}} for name in sys.modules)
"""
    subprocess.run([sys.executable, "-I", "-B", "-c", code], check=True, timeout=20)


def test_metadata_numerical_manifest_matches_owning_freeze_inventory():
    if importlib.util.find_spec("torch") is None:
        pytest.skip("owning manifest equivalence requires optional CPU Torch; metadata tests remain independent")
    root = str(Path(__file__).resolve().parents[2])
    code = f"""import sys
sys.path.insert(0, {root!r})
from betelgeuze_product.prepared_lifecycle import numerical_implementation_sources
expected = numerical_implementation_sources()
assert 'torch' not in sys.modules
from betelgeuze_product.cpu_refinement_fourier_v1.minimization import implementation_sources
assert implementation_sources() == expected
"""
    subprocess.run([sys.executable, "-I", "-B", "-c", code], check=True, timeout=30)


@pytest.mark.parametrize("stage", ["execute", "claim", "resume"])
def test_numerical_only_source_drift_is_rejected_before_new_dispatch(service, monkeypatch, stage):
    plan = service.plan("fixture")
    if stage != "execute":
        execution = service.execute(plan["plan_id"], plan["plan_sha256"], "frozen")["execution_id"]
        if stage == "resume":
            claim = service._claim(execution)
            service._finish(claim, status="paused", numerical_state="paused", known_force=3, wall=3, cpu=2, spawned=True)
    original_read = core.regular_bytes

    def numerical_drift(path, *args, **kwargs):
        data = original_read(path, *args, **kwargs)
        return data + b"# simulated numerical-only update" if str(path).endswith("cpu_refinement_fourier_v1/workflow.py") else data

    monkeypatch.setattr(core, "regular_bytes", numerical_drift)
    operation = (lambda: service.execute(plan["plan_id"], plan["plan_sha256"], "frozen")) if stage == "execute" else (
        (lambda: service._claim(execution)) if stage == "claim" else (lambda: service.resume(execution)))
    with pytest.raises(core.LifecycleError) as error:
        operation()
    assert error.value.code == ("STALE_PLAN" if stage == "execute" else "SOURCE_OR_MODEL_MISMATCH")
    with service._connect() as connection:
        assert connection.execute("SELECT count(*) FROM prepared_invocations").fetchone()[0] == (1 if stage == "resume" else 0)


def test_first_owning_freeze_must_match_plan_before_force_work():
    expected = {"numerical.py": "a" * 64}
    frozen = {"payload": {"implementation_sources": expected}}
    loaded = object()
    assert _bound_freeze(lambda _: (frozen, loaded), expected)({}) == (frozen, loaded)
    with pytest.raises(core.LifecycleError, match="Planned numerical implementation changed"):
        _bound_freeze(lambda _: ({"payload": {"implementation_sources": {"numerical.py": "b" * 64}}}, loaded), expected)({})


def test_private_original_and_sanitized_download_have_separate_identities(service, monkeypatch):
    candidate = "/private/research/identifier"
    identity, value, _, attempt = retained(service, candidate=candidate)
    adapter(monkeypatch, value)
    original = (attempt / "report.json").read_bytes()
    document = results.report_execution(service, identity)
    assert candidate not in json.dumps(document)
    listed = service.artifacts(identity)["artifacts"]
    assert "retained_refinement_report" not in {item["role"] for item in listed}
    public = next(item for item in listed if item["role"] == core.PUBLIC_REPORT_ROLE)
    path, metadata = service.artifact(identity, public["artifact_id"])
    raw = path.read_bytes()
    assert candidate.encode() not in raw
    assert hashlib.sha256(raw).hexdigest() == metadata["sha256"]
    assert metadata["sha256"] != hashlib.sha256(original).hexdigest()
    assert json.loads(raw)["source_report_sha256"] == core.digest(json.loads(original))
    assert json.loads(raw)["backend_candidate_sha256"] == core.digest(candidate)
    with service._connect() as connection:
        private_id = connection.execute("SELECT artifact_id FROM prepared_artifacts WHERE execution_id=? AND role='retained_refinement_report'", (identity,)).fetchone()[0]
    with pytest.raises(core.LifecycleError) as denied:
        service.artifact(identity, private_id)
    assert denied.value.http_status == 404
    assert (attempt / "report.json").read_bytes() == original


def test_forged_public_projection_is_rejected_even_with_resealed_artifact_hashes(service, monkeypatch):
    identity, value, _, attempt = retained(service)
    adapter(monkeypatch, value)
    path = attempt / "public-report.json"
    public = json.loads(path.read_bytes())
    public["backend_candidate_sha256"] = "f" * 64
    reseal_registered(service, identity, path, public, core.PUBLIC_REPORT_ROLE)
    manifest = json.loads((attempt / "manifest.json").read_bytes())
    manifest["artifact_content_sha256"]["public-report.json"] = hashlib.sha256(path.read_bytes()).hexdigest()
    reseal_registered(service, identity, attempt / "manifest.json", manifest, "execution_artifact_manifest")
    with pytest.raises(core.LifecycleError, match="Public report differs"):
        results.report_execution(service, identity)


def test_public_artifact_preserves_unknown_owner_work(service, monkeypatch):
    identity, value, _, attempt = retained(service, known=False)
    adapter(monkeypatch, value)
    assert results.report_execution(service, identity)["total_force_calls"] is None
    public = next(item for item in service.artifacts(identity)["artifacts"] if item["role"] == core.PUBLIC_REPORT_ROLE)
    path, _ = service.artifact(identity, public["artifact_id"])
    document = json.loads(path.read_bytes())
    assert document["state_metrics_provisional"] and document["total_work_known"] is False
    assert document["work"]["total_work_known"] is False
    assert document["work"]["total_force_evaluation_calls"] is document["numerical_convergence"] is None
    assert json.loads((attempt / "report.json").read_bytes())["work"]["total_work_known"] is True


def test_http_artifact_surface_cannot_download_private_original(service, monkeypatch):
    pytest.importorskip("fastapi")
    from api.request_identity import ProductRequestIdentity
    from tests.unit.test_api_product_prepared import client_for

    candidate = "/private/research/identifier"
    identity, value, _, _ = retained(service, candidate=candidate)
    monkeypatch.setattr(results, "_owning_adapter", lambda *a, **k: deepcopy(value))
    monkeypatch.setattr(core, "configured_service", lambda *, tenant_id: core.PreparedLifecycle(
        service.root, service.input_root, tenant_id=tenant_id))
    prefix = f"/product/prepared/jobs/{identity}"
    with service._connect() as connection:
        private_id = connection.execute("SELECT artifact_id FROM prepared_artifacts WHERE execution_id=? AND role='retained_refinement_report'", (identity,)).fetchone()[0]
    with client_for(ProductRequestIdentity("local", "token:local", True)) as client:
        report_response = client.get(prefix + "/report")
        assert report_response.status_code == 200 and report_response.json()["fully_verified"]
        assert candidate not in report_response.text
        listed = client.get(prefix + "/artifacts").json()["artifacts"]
        assert core.PUBLIC_REPORT_ROLE in {item["role"] for item in listed}
        for item in listed:
            response = client.get(prefix + "/artifacts/" + item["artifact_id"])
            assert response.status_code == 200 and candidate not in response.text
            assert hashlib.sha256(response.content).hexdigest() == item["sha256"]
        assert client.get(prefix + "/artifacts/" + private_id).status_code == 404
    with client_for(ProductRequestIdentity("other", "token:other", True)) as client:
        assert client.get(prefix + "/artifacts/" + listed[0]["artifact_id"]).status_code == 404
