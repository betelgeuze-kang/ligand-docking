"""Registry and retained-evidence controls; no force evaluator is executed."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types

import pytest

from betelgeuze_product import prepared_lifecycle_results as results
from betelgeuze_product.prepared_lifecycle import (
    LifecycleError, PreparedLifecycle, digest, write_absent,
)
from tests.unit.test_prepared_lifecycle_store import make_service


def backend_report(energy=8., candidate="candidate"):
    document = {
        "schema_version": "prepared_refinement_report/1.0.0", "binding": "b"*64,
        "candidate_id": candidate, "execution_status": "complete", "refinement_status": "max_iterations_reached",
        "verification_scope": results.OWNING_SCOPE, "numerical_convergence": False,
        "chemical_validity": None, "pose_accuracy": None, "pose_selection_admitted": False,
        "force_semantics": results.FORCE_SEMANTICS, "units": dict(results.UNITS),
        "states": {"baseline": {"state_role": "baseline", "energy_kcal_per_mol": 10.,
                                "max_force_kcal_per_mol_angstrom": 2.},
                   "last_observed_refinement": {"state_role": "last_observed_refinement",
                       "energy_kcal_per_mol": energy, "max_force_kcal_per_mol_angstrom": 1.}},
        "comparison": {"energy_delta_kcal_per_mol": energy-10.,
                       "scope": "baseline_vs_last_observed_refinement_same_declared_model"},
        "work": {"known_force_evaluation_calls": 3, "total_force_evaluation_calls": 3,
                 "known_failed_force_evaluation_calls": 0, "restart_verification_calls": 0,
                 "total_work_known": True, "report_force_evaluation_calls": 0},
        "boundary": {"scientifically_validated": False},
        "report_sources": results._report_source_identity(),
    }
    document["report_source_sha256"] = digest(document["report_sources"])
    return {**document, "report_sha256": digest(document)}


def retained(service, key="one", *, known=True, energy=8., candidate="candidate",
             resume_from=None, status="complete", force=3):
    execution = service.submit("fixture", key)["execution_id"] if resume_from is None else resume_from
    if resume_from is not None:
        service.resume(execution)
    claim = service._claim(execution)
    admission = json.loads(claim["admission_json"])
    job = service.root / "jobs" / execution
    generation = claim["generation"]
    attempt = job / "attempts" / f"{generation:06d}"
    attempt.mkdir(parents=True, mode=0o700)
    numerical = job / "numerical"
    numerical.mkdir(mode=0o700, exist_ok=True)
    if not (numerical / "frozen.json").exists():
        write_absent(numerical / "frozen.json", {"test_receipt_only": True})
    report = backend_report(energy, candidate)
    report["execution_status"] = status
    report["work"]["known_force_evaluation_calls"] = force
    report["work"]["total_force_evaluation_calls"] = force
    report["report_sha256"] = digest({k: v for k, v in report.items() if k != "report_sha256"})
    result = {"schema_version": "prepared_lifecycle_numerical_result/1.0.0",
              "execution_id": execution, "generation": generation, "status": status, "numerical_state": status,
              "known_force_calls": force, "total_work_known": True, "backend_binding": "b"*64,
              "report_sha256": digest(report)}
    write_absent(attempt / "result.json", result)
    write_absent(attempt / "report.json", report)
    manifest = {"schema_version": "prepared_lifecycle_artifact_manifest/1.0.0",
                "execution_id": execution, "generation": generation,
                "status": status if known else "interrupted_unknown",
                "numerical_state": status if known else "interrupted_unknown",
                "total_work_known": known, "known_force_calls": force,
                "process_terminal_confirmed": True,
                "implementation_sources": admission["lifecycle_sources"],
                "runtime_identity": admission["runtime_identity"],
                "protocol_sha256": admission["manifest"]["protocol_sha256"],
                "artifact_content_sha256": {name: hashlib.sha256((attempt/name).read_bytes()).hexdigest()
                                            for name in ("result.json", "report.json")}}
    write_absent(attempt / "manifest.json", manifest)
    process = {"returncode": 0 if known else 125, "containment_error": "",
               "containment_evidence": {"namespace_exit_verified": True}}
    service._finish(claim, status=manifest["status"], numerical_state=manifest["numerical_state"],
                    receipt={"process_terminal_confirmed": True, "process": process},
                    known_force=force, force_known=known, spawned=True,
                    artifacts=[(attempt/name, role) for role, name in results.ROLES.items()])
    owning = {"binding": "b"*64, "status": status, "known_force_calls": force,
              "total_work_known": True, "report": report,
              "evaluator": {"evaluator_id": "test-fourier-fixed", "parameter_fingerprint_sha256": "c"*64,
                            "cross_parameters_sha256": "d"*64}}
    return execution, owning, numerical, attempt


@pytest.fixture
def service(tmp_path):
    return make_service(tmp_path)


def adapter(monkeypatch, value):
    calls = []
    def read_only(protocol, directory, *, with_report):
        calls.append(with_report)
        return deepcopy(value)
    monkeypatch.setattr(results, "_owning_adapter", read_only)
    return calls


def test_module_import_is_light_in_isolated_interpreter():
    root = str(Path(__file__).resolve().parents[2])
    code = "import sys;sys.path.insert(0,"+repr(root)+");import betelgeuze_product.prepared_lifecycle_results;assert not any(n.split('.')[0] in {'torch','numpy','fastapi'} for n in sys.modules)"
    subprocess.run([sys.executable, "-I", "-B", "-c", code], check=True, timeout=10)


def test_queued_and_inflight_never_import_owning_runtime(service, monkeypatch):
    identity = service.submit("fixture", "one")["execution_id"]
    monkeypatch.setattr(results, "_owning_adapter", lambda *a, **k: pytest.fail("owning runtime reached"))
    queued = results.report_execution(service, identity)
    assert queued["verification_status"] == "not_ready" and queued["report"] is None
    service._claim(identity)
    running = results.verify_execution(service, identity)
    assert running["verification_status"] == "inflight_unresolved"
    assert running["total_force_calls"] is None and running["fully_verified"] is False


def test_known_report_binds_registry_artifacts_and_preserves_nonconvergence(service, monkeypatch):
    identity, value, numerical, _ = retained(service)
    before = {p.name: p.read_bytes() for p in numerical.iterdir()}
    calls = adapter(monkeypatch, value)
    verified = results.verify_execution(service, identity)
    reported = results.report_execution(service, identity)
    assert calls == [False, True]
    assert verified["verification_status"] == "verified_known" and verified["total_force_calls"] == 3
    assert reported["report_status"] == "available"
    assert reported["report"]["numerical_convergence"] is False
    assert reported["report"]["refinement_status"] == "max_iterations_reached"
    assert reported["read_only_cost"]["new_force_calls"] == 0
    assert {p.name: p.read_bytes() for p in numerical.iterdir()} == before
    assert service.status(identity)["budget"]["known_force_calls"] == 3
    assert service.status(identity)["budget"]["numerical_invocations"] == 1


def test_visible_complete_backend_does_not_promote_unknown_owner_work(service, monkeypatch):
    identity, value, _, _ = retained(service, known=False)
    adapter(monkeypatch, value)
    document = results.report_execution(service, identity)
    assert document["verification_status"] == "verified_with_unknown_work"
    assert document["report_status"] == "provisional_unknown_work"
    assert document["fully_verified"] is False and document["known_force_calls"] == 3
    assert document["total_force_calls"] is None
    assert document["report"]["work"]["total_force_evaluation_calls"] is None
    assert document["report"]["numerical_convergence"] is None
    assert document["report"]["state_metrics_provisional"] is True


def test_cancelled_before_numerical_files_keeps_unknown_none_manifest_prefix(service, monkeypatch):
    identity = service.submit("fixture", "cancelled")["execution_id"]
    claim = service._claim(identity)
    admission = json.loads(claim["admission_json"])
    attempt = service.root / "jobs" / identity / "attempts" / "000001"
    attempt.mkdir(parents=True, mode=0o700)
    manifest = {"schema_version": "prepared_lifecycle_artifact_manifest/1.0.0",
                "execution_id": identity, "generation": 1, "status": "cancelled",
                "numerical_state": "interrupted_unknown", "total_work_known": False,
                "known_force_calls": None, "process_terminal_confirmed": True,
                "implementation_sources": admission["lifecycle_sources"],
                "runtime_identity": admission["runtime_identity"],
                "protocol_sha256": admission["manifest"]["protocol_sha256"],
                "artifact_content_sha256": {}}
    write_absent(attempt / "manifest.json", manifest)
    service._finish(claim, status="cancelled", numerical_state="interrupted_unknown",
                    known_force=None, force_known=False, spawned=True,
                    artifacts=[(attempt / "manifest.json", "execution_artifact_manifest")])
    monkeypatch.setattr(results, "_owning_adapter", lambda *a, **k: pytest.fail("missing numerical runtime reached"))
    document = results.report_execution(service, identity)
    assert document["verification_status"] == "not_ready" and document["report"] is None
    assert document["total_work_known"] is False and document["total_force_calls"] is None
    assert document["known_force_calls"] == 0 and document["fully_verified"] is False


def reseal_registered(service, identity, path, value, role):
    raw = (json.dumps(value, sort_keys=True)+"\n").encode()
    path.write_bytes(raw)
    with service._transaction() as connection:
        connection.execute("UPDATE prepared_artifacts SET checksum=?,bytes=? WHERE execution_id=? AND relative_path=? AND role=?",
                           (hashlib.sha256(raw).hexdigest(), len(raw), identity,
                            str(path.relative_to(service.root / "jobs" / identity)), role))


def test_prior_generation_report_census_checked_even_if_current_generation_is_valid(service, monkeypatch):
    identity, _, _, first = retained(service, status="paused")
    _, current, _, _ = retained(service, resume_from=identity, force=5)
    adapter(monkeypatch, current)
    assert results.verify_execution(service, identity)["total_force_calls"] == 5
    report = json.loads((first / "report.json").read_bytes())
    report["work"]["known_force_evaluation_calls"] = 2
    report["work"]["total_force_evaluation_calls"] = 2
    report["report_sha256"] = digest({k: v for k, v in report.items() if k != "report_sha256"})
    reseal_registered(service, identity, first / "report.json", report, "retained_refinement_report")
    result = json.loads((first / "result.json").read_bytes())
    result["report_sha256"] = digest(report)
    reseal_registered(service, identity, first / "result.json", result, "numerical_invocation_result")
    manifest = json.loads((first / "manifest.json").read_bytes())
    manifest["artifact_content_sha256"] = {name: hashlib.sha256((first/name).read_bytes()).hexdigest()
                                           for name in ("report.json", "result.json")}
    reseal_registered(service, identity, first / "manifest.json", manifest, "execution_artifact_manifest")
    with pytest.raises(LifecycleError, match="Result and report binding"):
        results.verify_execution(service, identity)


def test_prior_reserved_generation_cannot_be_hidden_by_valid_latest_completion(service, monkeypatch):
    identity, _, _, _ = retained(service, status="paused")
    _, current, _, _ = retained(service, resume_from=identity, force=5)
    adapter(monkeypatch, current)
    with service._transaction() as connection:
        connection.execute("UPDATE prepared_invocations SET status='reserved' WHERE execution_id=? AND generation=1", (identity,))
    with pytest.raises(LifecycleError, match="unresolved owner reservation"):
        results.verify_execution(service, identity)


def test_tree_and_registry_read_totals_are_bounded_before_large_reads(service, monkeypatch):
    directory = service.root / "bounded-test"
    directory.mkdir()
    (directory / "one").write_bytes(b"1234")
    (directory / "two").write_bytes(b"1234")
    with pytest.raises(LifecycleError) as overflow:
        results._tree(directory, 7)
    assert overflow.value.code == "READ_VERIFICATION_FAILED"
    identity, value, _, _ = retained(service)
    adapter(monkeypatch, value)
    with service._transaction() as connection:
        connection.execute("UPDATE prepared_artifacts SET bytes=? WHERE execution_id=?",
                           (209715201, identity))
    with pytest.raises(LifecycleError, match="Cumulative artifact bytes"):
        results.verify_execution(service, identity)


def test_candidate_path_is_hashed_instead_of_echoed(service, monkeypatch):
    identity, value, _, _ = retained(service, candidate="/private/research/identifier")
    adapter(monkeypatch, value)
    document = results.report_execution(service, identity)
    assert document["report"]["candidate_id"] is None
    assert document["report"]["backend_candidate_sha256"] == digest("/private/research/identifier")
    assert "/private/research" not in json.dumps(document)


def test_artifact_tamper_rejected_before_backend_call(service, monkeypatch):
    identity, _, _, attempt = retained(service)
    (attempt / "report.json").write_text("{}")
    monkeypatch.setattr(results, "_owning_adapter", lambda *a, **k: pytest.fail("tamper reached backend"))
    with pytest.raises(LifecycleError) as error:
        results.verify_execution(service, identity)
    assert error.value.code == "ARTIFACT_PUBLICATION_UNKNOWN"


def test_registry_generation_and_prior_reservations_are_checked(service, monkeypatch):
    identity, value, _, _ = retained(service)
    adapter(monkeypatch, value)
    with service._transaction() as connection:
        connection.execute("UPDATE prepared_jobs SET generation=2 WHERE execution_id=?", (identity,))
    with pytest.raises(LifecycleError, match="generation sequence"):
        results.verify_execution(service, identity)


def test_prior_generation_runtime_source_cannot_drift(service, monkeypatch):
    identity, value, _, attempt = retained(service)
    adapter(monkeypatch, value)
    path = attempt / "manifest.json"
    manifest = json.loads(path.read_bytes())
    manifest["runtime_identity"] = {"changed": True}
    raw = (json.dumps(manifest, sort_keys=True)+"\n").encode()
    path.write_bytes(raw)
    with service._transaction() as connection:
        connection.execute("UPDATE prepared_artifacts SET checksum=?,bytes=? WHERE execution_id=? AND role='execution_artifact_manifest'",
                           (hashlib.sha256(raw).hexdigest(), len(raw), identity))
    with pytest.raises(LifecycleError, match="source identity"):
        results.verify_execution(service, identity)


def test_numerical_or_registry_mutation_during_read_fails(service, monkeypatch):
    identity, value, numerical, _ = retained(service)
    def mutating(*args, **kwargs):
        (numerical / "unexpected.json").write_text("{}")
        return value
    monkeypatch.setattr(results, "_owning_adapter", mutating)
    with pytest.raises(LifecycleError) as error:
        results.verify_execution(service, identity)
    assert error.value.code == "CONCURRENT_STATE_CHANGE"


def test_thread_contract_failure_is_typed_without_changing_threads(service, monkeypatch):
    identity, _, _, _ = retained(service)
    def wrong_threads(*args, **kwargs):
        raise ValueError("one CPU thread required")
    monkeypatch.setattr(results, "_owning_adapter", wrong_threads)
    with pytest.raises(LifecycleError) as error:
        results.verify_execution(service, identity)
    assert error.value.code == "READ_VERIFICATION_UNAVAILABLE"


def test_fixed_lazy_adapter_calls_only_owning_read_functions(monkeypatch, tmp_path):
    calls = []
    fake_workflow = types.ModuleType("betelgeuze_product.cpu_refinement_fourier_v1.workflow")
    fake_workflow.__file__ = str(Path(results.__file__).parent / "cpu_refinement_fourier_v1/workflow.py")
    fake_workflow.verify = lambda *a: calls.append("verify") or {
        "verification_scope": results.OWNING_SCOPE, "binding": "b"*64, "status": "complete",
        "baseline": None, "invocations": [], "unknown_stage": None}
    fake_workflow._committed = lambda *a: {"payload": {"evaluator": {"declared": True}}}
    package = types.ModuleType("betelgeuze_product.cpu_refinement_fourier_v1")
    package.workflow = fake_workflow
    fake_report = types.ModuleType("betelgeuze_product.prepared_refinement_cli")
    fake_report.__file__ = str(Path(results.__file__).parent / "prepared_refinement_cli.py")
    fake_report.report = lambda *a: calls.append("report") or backend_report()
    fake_provenance = types.ModuleType("betelgeuze_product.cpu_refinement_v1_2.provenance")
    fake_provenance.__file__ = str(Path(results.__file__).parent / "cpu_refinement_v1_2/provenance.py")
    fake_provenance.environment = lambda: {"torch_threads": 1, "torch_interop_threads": 1}
    old_package = types.ModuleType("betelgeuze_product.cpu_refinement_v1_2")
    old_package.provenance = fake_provenance
    monkeypatch.setitem(sys.modules, "betelgeuze_product.cpu_refinement_fourier_v1", package)
    monkeypatch.setitem(sys.modules, "betelgeuze_product.cpu_refinement_fourier_v1.workflow", fake_workflow)
    monkeypatch.setitem(sys.modules, "betelgeuze_product.prepared_refinement_cli", fake_report)
    monkeypatch.setitem(sys.modules, "betelgeuze_product.cpu_refinement_v1_2", old_package)
    monkeypatch.setitem(sys.modules, "betelgeuze_product.cpu_refinement_v1_2.provenance", fake_provenance)
    results.read_worker._read_owning({}, tmp_path, with_report=False)
    results.read_worker._read_owning({}, tmp_path, with_report=True)
    assert calls == ["verify", "report"]


def test_compare_retains_all_requested_rows_and_rejects_other_hamiltonian(service, monkeypatch):
    first, a, _, _ = retained(service, "a", energy=8.)
    second, b, _, _ = retained(service, "b", energy=7.)
    values = {first: a, second: b}
    monkeypatch.setattr(results, "_owning_adapter", lambda p, directory, **k: deepcopy(values[directory.parent.name]))
    document = results.compare_executions(service, [first, second, "f"*32])
    assert document["requested_execution_count"] == 3 and len(document["rows"]) == 3
    assert document["pairs"][0]["differences"]["right_minus_left_energy_kcal_per_mol"] == -1.
    assert document["rows"][2]["result"]["error"]["code"] == "NOT_FOUND_OR_FORBIDDEN"
    assert document["winner"] is None and document["automatic_ranking_performed"] is False
    b["evaluator"]["cross_parameters_sha256"] = "e"*64
    incompatible = results.compare_executions(service, [first, second])
    assert incompatible["pairs"][0]["comparable"] is False
    assert incompatible["pairs"][0]["differences"] is None


def test_compare_checks_global_snapshot_and_tenant_isolation(service, monkeypatch):
    first, a, _, _ = retained(service, "a")
    second, b, _, _ = retained(service, "b")
    def racing(protocol, directory, **kwargs):
        if directory.parent.name == second:
            with service._transaction() as connection:
                connection.execute("UPDATE prepared_jobs SET updated=updated+1 WHERE execution_id=?", (first,))
        return deepcopy(a if directory.parent.name == first else b)
    monkeypatch.setattr(results, "_owning_adapter", racing)
    with pytest.raises(LifecycleError) as error:
        results.compare_executions(service, [first, second])
    assert error.value.code == "CONCURRENT_STATE_CHANGE"
    other = PreparedLifecycle(service.root, service.input_root, tenant_id="other")
    with pytest.raises(LifecycleError) as forbidden:
        results.verify_execution(other, first)
    assert forbidden.value.code == "NOT_FOUND_OR_FORBIDDEN"
    rows = results.compare_executions(other, [first, "f"*32])["rows"]
    assert rows[0]["result"]["error"] == rows[1]["result"]["error"]


def test_duplicate_references_preserve_denominator_without_repeating_verification(service, monkeypatch):
    identity, value, _, _ = retained(service)
    calls = adapter(monkeypatch, value)
    document = results.compare_executions(service, [identity, identity])
    assert calls == [True]
    assert document["requested_execution_count"] == 2 and document["unique_execution_count"] == 1
    assert document["rows"][1]["repeated_execution_reference"] is True
