"""Portable supervisor tests use fake boundaries, never molecular evaluations."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import signal
import sys
import time

import pytest

SOURCE = Path(__file__).resolve().parents[2] / "docs/research/human_5ht6_sro_pose_recovery/campaign_supervisor.py"
spec = importlib.util.spec_from_file_location("tested_sro_campaign_supervisor", SOURCE)
supervisor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(supervisor)


class FakeDriver:
    def __init__(self):
        self.validations = 0

    def validate_plan(self, plan):
        self.validations += 1
        assert plan["execution_order"] == supervisor.CASE_IDS

    def review_execution(self, plan_ref, review_ref):
        return supervisor.read_bound(review_ref)


@pytest.fixture
def campaign(tmp_path, monkeypatch):
    fake_driver = FakeDriver()
    source = tmp_path / "source"
    source.mkdir()
    parent_source = source / "campaign_supervisor.py"
    parent_source.write_bytes(SOURCE.read_bytes())
    monkeypatch.setattr(supervisor, "__file__", str(parent_source))
    driver_path = source / "runtime_execution.py"
    driver_path.write_text("# explicitly fake test driver\n")
    runner_path = source / "endpoint_oracle_runner.py"
    runner_path.write_text("# explicitly fake test oracle\n")
    oracle_source = source / "sro_recovery_endpoint_numerics_v1.py"
    oracle_source.write_text("# explicitly fake test oracle module\n")
    spec_ref = supervisor.publish(tmp_path / "oracle-input-spec.json", {"explicit_fake_boundary": True})
    plan = {"driver_source_ref": supervisor.file_ref(driver_path),
            "execution_order": supervisor.CASE_IDS, "protocol_sha256": supervisor.PROTOCOL_SHA,
            "manifest_sha256": supervisor.MANIFEST_SHA, "budget": {"wall_seconds": 7200},
            "python_executable": sys.executable,
            "oracle_phase": {"python_executable": sys.executable,
                "python_binary_ref": supervisor.file_ref(Path(sys.executable).resolve()),
                "argv_template": ["-I", "-B", str(runner_path), "{case_id}", "{oracle_output}"],
                "source_refs": [supervisor.file_ref(parent_source), supervisor.file_ref(runner_path),
                                supervisor.file_ref(oracle_source), spec_ref],
                "receipt_name": "numerical-receipt.json"}}
    plan_ref = supervisor.publish(tmp_path / "plan.json", plan)
    review_ref = supervisor.publish(tmp_path / "execution-review.json", {"test_review": True})
    monkeypatch.setattr(supervisor, "_load_driver", lambda _: fake_driver)
    observed = []

    def launch(argv, directory, deadline):
        observed.append((deepcopy(argv), str(directory), deadline))
        directory.mkdir()
        supervisor.publish(directory / "fake-process-receipt.json", {"fake_boundary": True})

    monkeypatch.setattr(supervisor, "_launch", launch)
    monkeypatch.setattr(supervisor, "_native_result", lambda directory, case_id:
                        supervisor.publish(directory / "fake-child.json", {"case_id": case_id})
                        if directory.exists() else _child(directory, case_id))
    monkeypatch.setattr(supervisor, "_oracle_result", lambda directory, case_id, **kwargs:
                        (supervisor.publish(directory / "fake-oracle.json", {"case_id": case_id}), False)
                        if directory.exists() else _oracle(directory, case_id))
    return tmp_path, plan_ref, review_ref, observed, fake_driver


def _child(directory, case_id):
    directory.mkdir()
    return supervisor.publish(directory / "fake-child.json", {"case_id": case_id})


def _oracle(directory, case_id):
    directory.mkdir()
    return supervisor.publish(directory / "fake-oracle.json", {"case_id": case_id}), False


def run_fixture(campaign):
    path, plan_ref, review_ref, _, _ = campaign
    return supervisor.read_bound(supervisor.run_campaign(plan_ref, review_ref, path / "campaign"))


def test_same_math_gate_failure_is_completed_and_does_not_stop(campaign):
    result = run_fixture(campaign)
    observed = campaign[3]
    assert result["status"] == "completed"
    assert result["denominator"] == result["completed_count"] == 4
    assert len(observed) == 8
    for index, case_id in enumerate(supervisor.CASE_IDS):
        native, oracle = observed[index * 2:index * 2 + 2]
        assert native[0][:3] == [sys.executable, "-I", "-B"]
        assert native[0][native[0].index("--case") + 1] == case_id
        assert native[2] == oracle[2]
        assert result["case_results"][index]["all_same_math_checks_passed"] is False
        assert result["case_results"][index]["work"] is None
    assert campaign[4].validations == 13


def test_native_fatal_stops_without_oracle_or_remaining_cases(campaign, monkeypatch):
    def failed_native(directory, case_id):
        raise supervisor.CampaignError("retained native pending dispatch")
    monkeypatch.setattr(supervisor, "_native_result", failed_native)
    result = run_fixture(campaign)
    assert [row["status"] for row in result["case_results"]] == ["failed", "unstarted", "unstarted", "unstarted"]
    assert result["unstarted_count"] == 3
    assert len(campaign[3]) == 1
    assert all(row["work"] is None for row in result["case_results"])
    assert all(row["started_at"] is None for row in result["case_results"][1:])
    assert all(row["terminal_case_ref"] is None for row in result["case_results"][1:])


def test_oracle_exception_stops_after_native_once(campaign, monkeypatch):
    def failed_oracle(directory, case_id, **kwargs):
        raise supervisor.CampaignError("oracle incomplete state")
    monkeypatch.setattr(supervisor, "_oracle_result", failed_oracle)
    result = run_fixture(campaign)
    assert result["case_results"][0]["native_child_ref"] is not None
    assert result["case_results"][0]["numerical_receipt_ref"] is None
    assert result["case_results"][0]["status"] == "failed"
    assert len(campaign[3]) == 2
    assert result["unstarted_count"] == 3


def test_watchdog_stops_once_and_retains_unknown_work(campaign, monkeypatch):
    def timeout(argv, directory, deadline):
        campaign[3].append((argv, str(directory), deadline))
        raise supervisor.CaseDeadline("test watchdog")
    monkeypatch.setattr(supervisor, "_launch", timeout)
    result = run_fixture(campaign)
    assert result["case_results"][0]["status"] == "watchdog"
    assert result["denominator"] == 4
    assert result["unstarted_count"] == 3
    assert len(campaign[3]) == 1
    assert result["case_results"][0]["work"] is None


def test_actual_parent_pid_and_exact_shared_deadline_recorded(campaign):
    run_fixture(campaign)
    path = campaign[0] / "campaign" / "perturbed_01" / "supervisor.json"
    record = json.loads(path.read_bytes())
    assert set(record) == {"schema_id", "case_id", "plan_ref", "execution_review_ref", "controller_pid",
                           "started_at", "started_monotonic_ns", "deadline_monotonic_ns", "native_output"}
    assert record["controller_pid"] == supervisor.os.getpid()
    assert record["deadline_monotonic_ns"] - record["started_monotonic_ns"] == 7200 * 10**9
    assert record["native_output"] == str(path.parent / "native")


def test_output_is_create_only(campaign):
    run_fixture(campaign)
    with pytest.raises(FileExistsError):
        run_fixture(campaign)
    assert len(campaign[3]) == 8


def test_review_binds_supervisor_source(campaign):
    path, plan_ref, review_ref, observed, _ = campaign
    plan = supervisor.read_bound(plan_ref)
    plan["oracle_phase"]["source_refs"] = plan["oracle_phase"]["source_refs"][1:]
    with pytest.raises(supervisor.CampaignError, match="oracle_source_roles_required"):
        supervisor.source_layout(plan_ref, review_ref, plan)
    assert observed == []


def test_bound_json_rejects_duplicate_keys_and_changed_bytes(tmp_path):
    path = tmp_path / "test.json"
    path.write_bytes(b'{"one":1,"one":2}')
    with pytest.raises(supervisor.CampaignError, match="duplicate_json_key"):
        supervisor.read_bound(supervisor.file_ref(path))
    path.write_bytes(b'{"one":1}')
    ref = supervisor.file_ref(path)
    path.write_bytes(b'{"one":2}')
    with pytest.raises(supervisor.CampaignError, match="bound_file_changed"):
        supervisor.read_bound(ref)


def test_real_subprocess_deadline_is_reaped_and_receipted(tmp_path):
    directory = tmp_path / "process"
    with pytest.raises(supervisor.CaseDeadline):
        supervisor._launch([sys.executable, "-I", "-B", "-c", "import time; time.sleep(10)"],
                           directory, time.monotonic_ns() + 200_000_000)
    end = json.loads((directory / "process-end.json").read_bytes())
    assert end["returncode"] is not None
    assert end["error"]["type"] == "CaseDeadline"
    assert end["inclusive_wall_ns"] < 8 * 10**9


def test_oracle_numerical_mismatch_distinct_from_operational_failure(tmp_path):
    # Fabricated metadata checks parser semantics; it is not molecular evidence.
    dummy = {"path": str(tmp_path / "unused.json"), "sha256": "a" * 64, "bytes": 0}
    child_ref = supervisor.publish(tmp_path / "child.json", {"lifecycle_refs": {"preflight.json": dummy},
                                                            "endpoint_states_ref": dummy})
    oracle_ref = {"path": str(Path(supervisor.__file__).absolute().parent / "sro_recovery_endpoint_numerics_v1.py"),
                  "sha256": "b" * 64, "bytes": 0}
    plan_ref = {"path": str(tmp_path / "plan.json"), "sha256": "c" * 64, "bytes": 0}
    plan = {"cases": [{"case_id": "perturbed_01", "request_file_ref": dummy}], "wheel_ref": dummy,
            "oracle_phase": {"source_refs": [oracle_ref]}}
    receipt = {"schema_id": "sro_recovery_endpoint_numerics/1", "case_id": "perturbed_01",
               "failure": None, "denominator": {"requested": 2, "evaluated": 2, "unknown": 0},
               "states": [{"label": label, "status": "evaluated"} for label in ("initial", "last_accepted")],
               "new_native_force_calls": 0, "new_native_score_calls": 0, "all_same_math_checks_passed": False,
               "openmm_observations_performed": True, "source_sha256": oracle_ref["sha256"],
               "executing_source_ref": oracle_ref, "environment": {"platform": "Reference", "isolated": 1},
               "request_ref": dummy, "binding_ref": dummy, "endpoint_states_ref": dummy, "wheel_ref": dummy,
               "protocol_sha256": supervisor.PROTOCOL_SHA, "manifest_sha256": supervisor.MANIFEST_SHA}
    receipt["receipt_sha256"] = supervisor.hashlib.sha256(json.dumps(
        receipt, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    numeric_ref = supervisor.publish(tmp_path / "numerical-receipt.json", receipt)
    supervisor.publish(tmp_path / "lifecycle.json", {"failure": None, "plan_ref": plan_ref,
                       "native_child_ref": child_ref, "numerical_receipt_ref": numeric_ref})
    assert supervisor._oracle_result(tmp_path, "perturbed_01", plan_ref=plan_ref, plan=plan, native_ref=child_ref)[1] is False
    other = tmp_path / "incomplete"
    other.mkdir()
    receipt["failure"] = {"type": "RuntimeError", "reason": "test"}
    supervisor.publish(other / "numerical-receipt.json", receipt)
    with pytest.raises(supervisor.CampaignError, match="oracle_operational_failure"):
        supervisor._oracle_result(other, "perturbed_01", plan_ref=plan_ref, plan=plan, native_ref=child_ref)


def test_captured_source_bootstrap_rejects_source_replacement(tmp_path):
    source = tmp_path / "entry.py"
    source.write_text("raise SystemExit(0)\n")
    argv = supervisor.source_command(sys.executable, supervisor.file_ref(source), [])
    source.write_text("raise SystemExit(7)\n")
    with pytest.raises(supervisor.CampaignError, match="child_process_nonzero_exit"):
        supervisor._launch(argv, tmp_path / "process", time.monotonic_ns() + 10**10)
    assert json.loads((tmp_path / "process" / "process-end.json").read_bytes())["returncode"] == 1


def test_exact_oracle_entry_role_rejects_recursive_parent(campaign):
    path, plan_ref, review_ref, observed, _ = campaign
    plan = supervisor.read_bound(plan_ref)
    plan["oracle_phase"]["argv_template"][2] = str(path / "source" / "campaign_supervisor.py")
    supervisor.publish(path / "other-plan.json", plan)
    # Authenticate the plan role first, then exercise source layout directly.
    with pytest.raises(supervisor.CampaignError, match="exact_oracle_runner_required"):
        supervisor.source_layout(plan_ref, review_ref, plan)
    assert observed == []


def test_terminate_always_kills_remaining_process_group(monkeypatch):
    observed = []
    monkeypatch.setattr(supervisor.os, "killpg", lambda pid, sig: observed.append((pid, sig)))
    class Process:
        pid = 123
        returncode = -signal.SIGTERM
        def wait(self, timeout):
            return self.returncode
    supervisor._terminate_group(Process())
    assert observed == [(123, signal.SIGTERM), (123, signal.SIGKILL)]


def test_outside_archive_output_rejected_before_any_native_call(campaign):
    path, plan_ref, review_ref, observed, _ = campaign
    with pytest.raises(supervisor.CampaignError, match="canonical_output_scope_required"):
        supervisor.run_campaign(plan_ref, review_ref, path.parent / "outside-campaign")
    assert observed == []


def test_wheel_membership_rejects_extra_python_files(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    site = tmp_path / "site"
    package = site / "betelgeuze_product"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("# known\n")
    wheel = tmp_path / "wheel.zip"
    with supervisor.zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("betelgeuze_product/__init__.py", "# known\n")
    plan = {"wheel_ref": supervisor.file_ref(wheel), "installed_site": str(site)}
    monkeypatch.setattr(supervisor, "_validate", lambda *args: plan)
    check = supervisor.failure_integrity({}, {}, None)
    assert check["installed_file_closure_verified"] is True
    assert check["loaded_child_origins_verified"] is False
    (package / "injected.py").write_text("# undeclared module\n")
    check = supervisor.failure_integrity({}, {}, None)
    assert check["installed_file_closure_verified"] is False
    assert check["error"]["reason"] == "installed_python_membership_changed"


def test_seal_deadline_overrun_stops_and_retains_integrity(campaign, monkeypatch):
    original_publish = supervisor.publish
    actual_clock = supervisor.time.monotonic_ns
    expired = False
    def publishing(path, value):
        nonlocal expired
        ref = original_publish(path, value)
        if Path(path).name == "terminal-case.json":
            expired = True
        return ref
    monkeypatch.setattr(supervisor, "publish", publishing)
    monkeypatch.setattr(supervisor.time, "monotonic_ns", lambda: actual_clock() + (7200 * 10**9 if expired else 0))
    result = run_fixture(campaign)
    first = result["case_results"][0]
    assert first["status"] == "watchdog"
    assert first["error"]["reason"] == "case_seal_exceeded_shared_deadline"
    assert first["postfailure_integrity_ref"] is not None
    assert Path(first["terminal_case_ref"]["path"]).name == "terminal-seal-watchdog.json"
    assert result["unstarted_count"] == 3
    assert len(campaign[3]) == 2


def test_bootstrap_preserves_lexical_virtual_environment_python(tmp_path):
    import venv
    environment = tmp_path / "environment"
    venv.EnvBuilder(with_pip=False, symlinks=True).create(environment)
    executable = str(environment / "bin" / "python")
    observation = tmp_path / "observation.json"
    source = tmp_path / "entry.py"
    source.write_text("import json,sys\nfrom pathlib import Path\nPath(sys.argv[1]).write_text(json.dumps({'executable':sys.executable,'prefix':sys.prefix,'isolated':sys.flags.isolated}))\n")
    argv = supervisor.source_command(executable, supervisor.file_ref(source), [str(observation)])
    assert argv[0] == executable
    supervisor._launch(argv, tmp_path / "process", time.monotonic_ns() + 10**10)
    observed = json.loads(observation.read_bytes())
    assert observed["executable"] == executable
    assert observed["prefix"] == str(environment)
    assert observed["isolated"] == 1


def test_native_external_output_ref_rejected_before_body_read(tmp_path, monkeypatch):
    native = tmp_path / "native"
    native.mkdir()
    (native / "run").mkdir()
    refs = {}
    for name in ("native-start.json", "preflight.json", "native-end.json", "post-exit-source-check.json"):
        content = {"explicit_fake_boundary": True}
        if name == "native-end.json":
            content.update(error_type=None, post_exit_error_type=None, pending_dispatches=[])
        refs[name] = supervisor.publish(native / name, content)
    external = supervisor.publish(tmp_path / "external-reference.json", {"must_not_be_opened": True})
    endpoints = supervisor.publish(native / "endpoint-states.json", {"explicit_fake_boundary": True})
    supervisor.publish(native / "child-result.json", {"schema_id": "sro_native_child_result/1", "case_id": "perturbed_01",
        "status": "native_completed", "lifecycle_refs": refs, "verification_ref": external,
        "endpoint_states_ref": endpoints, "native_artifact_refs": []})
    reads = []
    original = supervisor.read_bound
    def reading(ref, **kwargs):
        reads.append(ref["path"])
        return original(ref, **kwargs)
    monkeypatch.setattr(supervisor, "read_bound", reading)
    with pytest.raises(supervisor.CampaignError, match="native_output_role_changed"):
        supervisor._native_result(native, "perturbed_01")
    assert external["path"] not in reads


# The saved-data fixtures below are synthetic assertions, never actual physics.
def trial_fixture(native, outcomes, *, pending=None, force_override=None, scores=2, score_reuses=0, score_pending=0):
    run = native / "run"
    numerical = run / "numerical"
    numerical.mkdir(parents=True)
    binding = {"explicit_fake_boundary": True}
    head = supervisor.compact_hash(binding)
    supervisor.publish(numerical / "meta.json", {"binding": binding, "binding_sha256": head})
    events = []
    def append(kind, payload):
        nonlocal head
        event = {"index": len(events), "kind": kind, "payload": payload, "previous_sha256": head}
        event["event_sha256"] = supervisor.compact_hash(event)
        events.append(event)
        head = event["event_sha256"]
    for index, outcome in enumerate(outcomes, 1):
        append("objective_started", {"attempt": index})
        append("objective_finished", {"attempt": index, "decision": {"outcome": outcome},
                                     "work": {"force_calls": 1}, "failure": "fatal" if outcome == "rejected_evaluation" else None})
    if pending == "objective":
        append("objective_started", {"attempt": len(outcomes) + 1})
    if pending == "restart":
        append("restart_started", {"verification": 1})
    (numerical / "events.jsonl").write_bytes(b"".join(
        json.dumps(event, sort_keys=True, separators=(",", ":")).encode() + b"\n" for event in events))
    force = len(outcomes) + int(pending is not None) if force_override is None else force_override
    starts = {"force": force, "graph": force, "score": scores}
    ledger = []
    pending_dispatches = []
    for kind, count in starts.items():
        for index in range(count):
            ledger.append({"event": "begin", "kind": kind, "index": index})
            if pending is not None and kind == "force" and index == count - 1:
                pending_dispatches.append([kind, index])
            else:
                error = "AdapterError" if kind == "force" and index < len(outcomes) and outcomes[index] == "rejected_evaluation" else None
                ledger.append({"event": "end", "kind": kind, "index": index, "error_type": error})
    (native / "dispatch.jsonl").write_bytes(b"".join(
        json.dumps(event, sort_keys=True, separators=(",", ":")).encode() + b"\n" for event in ledger))
    supervisor.publish(native / "native-end.json", {"dispatch_starts": starts, "pending_dispatches": pending_dispatches,
        "error_type": None, "post_exit_error_type": None})
    supervisor.publish(run / "invocation-000000.end.json", {"score_work": {
        "new_score_calls": scores, "reused_score_receipts": score_reuses, "unknown_pending_score_attempts": score_pending},
        "new_force_calls": None if pending is not None else force})
    return events


def test_objective_evaluation_failure_is_not_also_rejected(tmp_path):
    native = tmp_path / "native"
    trial_fixture(native, ["initial", "accepted", "rejected_armijo", "rejected_evaluation"], scores=1)
    accounting = supervisor._journal_work(native)
    work = accounting["work"]
    assert accounting["error"] is None
    assert work["objective_attempts"] == 4
    assert work["initial_successful_objectives"] == 1
    assert work["accepted_steps"] == 1
    assert work["rejected_attempts"] == 1
    assert work["failed_attempts"] == 1
    assert work["unknown_pending_attempts"] == 0
    assert accounting["completed_force_dispatches"] == 4
    assert work["score_calls"] == 1


def test_pending_restart_does_not_become_pending_objective(tmp_path):
    native = tmp_path / "native"
    trial_fixture(native, ["initial"], pending="restart", scores=1)
    accounting = supervisor._journal_work(native)
    assert accounting["error"] is None
    assert accounting["restart_pending"] == 1
    assert accounting["objective_pending"] == 0
    assert accounting["work"]["objective_attempts"] == 1
    assert accounting["work"]["unknown_pending_attempts"] == 0
    assert accounting["work"]["restart_force_calls"] is None
    assert accounting["raw_pending_dispatches"] == [("force", 1)]


def test_pending_objective_keeps_exact_partition_and_known_restart_count(tmp_path):
    native = tmp_path / "native"
    trial_fixture(native, ["initial"], pending="objective", scores=1)
    accounting = supervisor._journal_work(native)
    work = accounting["work"]
    assert work["objective_attempts"] == 2
    assert work["initial_successful_objectives"] == 1
    assert work["unknown_pending_attempts"] == 1
    assert work["restart_force_calls"] == 0
    assert accounting["restart_pending"] == 0


def test_dispatch_force_disagreement_blocks_legacy_accounting(tmp_path):
    native = tmp_path / "native"
    trial_fixture(native, ["initial"], force_override=2)
    accounting = supervisor._journal_work(native)
    assert accounting["dispatch_error"]["reason"] == "raw_journal_force_mismatch"
    assert accounting["raw_dispatch_starts"]["force"] == 2
    assert accounting["objective_force_calls_completed"] == 1


def test_invocation_score_disagreement_is_preserved(tmp_path):
    native = tmp_path / "native"
    trial_fixture(native, ["initial"], scores=1)
    path = native / "run" / "invocation-000000.end.json"
    invocation = json.loads(path.read_bytes())
    invocation["score_work"]["new_score_calls"] = 2
    path.write_bytes(supervisor.encode(invocation))
    accounting = supervisor._journal_work(native)
    assert accounting["dispatch_error"]["reason"] == "raw_invocation_score_mismatch"


def make_saved_campaign(tmp_path, *, native_pending=None, no_native=False):
    """Fabricated source and receipt seals test saved-data export only."""
    archive = tmp_path / "archive"
    source = archive / "source"
    source.mkdir(parents=True)
    driver_ref = None
    phase_refs = []
    for name in ("runtime_execution.py", "endpoint_oracle_runner.py", "campaign_supervisor.py",
                 "sro_recovery_endpoint_numerics_v1.py"):
        path = source / name
        path.write_text("# synthetic saved-data fixture; never executed\n")
        ref = supervisor.file_ref(path)
        if name == "runtime_execution.py":
            driver_ref = ref
        else:
            phase_refs.append(ref)
    phase_refs.append(supervisor.publish(archive / "oracle-input-spec.json", {"explicit_fake_boundary": True}))
    coordinates = [[float(index), .25, -.5] for index in range(26)]
    coordinate_sha = supervisor.hashlib.sha256(supervisor.encode(supervisor._exact_saved(coordinates))).hexdigest()
    plan = {"protocol_sha256": supervisor.PROTOCOL_SHA, "manifest_sha256": supervisor.MANIFEST_SHA,
            "driver_source_ref": driver_ref, "oracle_phase": {"source_refs": phase_refs},
            "cases": [{"case_id": case_id, "source_candidate_coordinates_sha256": coordinate_sha}
                      for case_id in supervisor.CASE_IDS]}
    plan_ref = supervisor.publish(archive / "plan.json", plan)
    review_ref = supervisor.publish(archive / "execution-review.json", {"schema_id": "sro_native_execution_review/1",
        "execution_authorized": True, "plan_sha256": plan_ref["sha256"],
        "driver_source_sha256": driver_ref["sha256"], "reviewed_at": "2026-01-01T00:00:00+00:00"})
    campaign = archive / "campaign"
    campaign.mkdir()
    case_root = campaign / "perturbed_01"
    native = case_root / "native"
    native.mkdir(parents=True)
    status = "watchdog" if native_pending is not None else "failed" if no_native else "completed"
    child_ref = numeric_ref = None
    if not no_native:
        trial_fixture(native, ["initial", "accepted"], pending=native_pending)
        if native_pending is None:
            current_coords = [[x + .125, y, z] for x, y, z in coordinates]
            def observation(coords, internal, total, force):
                return {"coordinates": [[value.hex() for value in row] for row in coords], "energy": float(total).hex(),
                        "forces": [[float(force).hex(), float(0).hex(), float(0).hex()] for _ in range(26)],
                        "components": {"ligand_internal": float(internal).hex(), "total": float(total).hex(),
                                       "cross_lennard_jones": float(total - internal).hex(), "cross_screened_coulomb": float(0).hex()}}
            initial = observation(coordinates, 10, 100, 1)
            current = observation(current_coords, 13, -100, .5)
            result = {"numerical_result": {"checkpoint": {"state": {"initial": initial, "current": current,
                       "best": observation(coordinates, 1, -200, .00001)}}},
                      "rows": {"baseline": {"score": 5}, "refined": {"score": 4,
                       "coordinates_binary64_hex": current["coordinates"], "pose_validity": {
                           "checks": {name: True for name in supervisor.EXPORT_CHECKS}, "complete": True}}},
                      "paired_decision": {"variant": "baseline"}}
            result["result_sha256"] = supervisor.compact_hash(result)
            supervisor.publish(native / "run" / "result.json", result)
            native_refs = supervisor.inventory(native / "run")
            lifecycle_refs = {"native-end.json": supervisor.file_ref(native / "native-end.json")}
            for name in ("native-start.json", "preflight.json", "post-exit-source-check.json"):
                lifecycle_refs[name] = supervisor.publish(native / name, {"explicit_fake_boundary": True})
            verification_ref = supervisor.publish(native / "semantic-verification.json", {
                "structural_verification_passed": True, "scoring_reexecuted": False,
                "numerical_evaluation_reexecuted": False, "explicit_fake_boundary": True})
            endpoints_ref = supervisor.publish(native / "endpoint-states.json", {"states": [
                {"label": label, **observed} for label, observed in (("initial", initial), ("last_accepted", current))]})
            child_ref = supervisor.publish(native / "child-result.json", {
                "schema_id": "sro_native_child_result/1", "case_id": "perturbed_01", "status": "native_completed",
                "lifecycle_refs": lifecycle_refs, "native_artifact_refs": native_refs,
                "verification_ref": verification_ref, "endpoint_states_ref": endpoints_ref})
            oracle = case_root / "oracle"
            oracle.mkdir()
            numeric = {"denominator": {"evaluated": 2}, "failure": None,
                "states": [{"energy_absolute_error_kcal_per_mol": 1e-9,
                    "component_absolute_errors_kcal_per_mol": {"ligand_internal": 2e-8, "total": 0},
                    "force_component_absolute_error_kcal_per_mol_angstrom": 3e-9} for _ in range(2)]}
            numeric["receipt_sha256"] = supervisor.compact_hash(numeric)
            numeric_ref = supervisor.publish(oracle / "numerical-receipt.json", numeric)
    else:
        trial_fixture(native, ["rejected_evaluation"], scores=1, score_reuses=1)
    actual_refs = supervisor.inventory(case_root)
    terminal_ref = supervisor.publish(case_root / "terminal-case.json", {"explicit_fake_boundary": True})
    row = {"case_id": "perturbed_01", "status": status, "started_at": "2026-01-01T00:01:00+00:00",
           "terminal_case_ref": terminal_ref, "native_child_ref": child_ref, "numerical_receipt_ref": numeric_ref,
           "actual_receipt_refs": actual_refs}
    rows = [row]
    for case_id in supervisor.CASE_IDS[1:]:
        rows.append({"case_id": case_id, "status": "unstarted", "started_at": None, "work": None})
    document = {"schema_id": "sro_four_case_campaign/1", "execution_order": supervisor.CASE_IDS,
                "denominator": 4, "case_results": rows, "plan_ref": plan_ref, "review_ref": review_ref}
    campaign_ref = supervisor.publish(campaign / "campaign-result.json", document)
    return archive, campaign_ref, coordinates


def test_export_uses_last_current_even_when_baseline_was_selected(tmp_path, monkeypatch):
    archive, campaign_ref, initial = make_saved_campaign(tmp_path)
    import builtins
    original_import = builtins.__import__
    def import_guard(name, *args, **kwargs):
        assert not name.startswith(("betelgeuze_product", "betelgeuze_engine_v2", "torch", "openmm"))
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", import_guard)
    exported = supervisor.read_bound(supervisor.export_results(campaign_ref, archive / "export"))
    saved = supervisor.read_bound(exported["saved_results_ref"])
    row = saved["case_results"][0]
    assert row["coordinates_angstrom"] == [[x + .125, y, z] for x, y, z in initial]
    assert row["forces_kcal_per_mol_angstrom"][0] == [.5, 0, 0]
    assert row["initial_internal_energy_kcal_per_mol"] == 10
    assert row["final_internal_energy_kcal_per_mol"] == 13
    assert row["baseline_dimensionless_score"] == 5
    assert row["final_dimensionless_score"] == 4
    assert row["numerical_audit"]["maximum_energy_error_kcal_per_mol"] == 2e-8
    assert row["input_coordinates_sha256"] == supervisor.hashlib.sha256(supervisor.encode(initial)).hexdigest()
    assert exported["denominator"] == len(exported["case_results"]) == 4
    assert exported["new_native_force_calls"] == exported["new_native_score_calls"] == exported["new_openmm_observations"] == 0
    assert saved["authority"]["scientifically_validated"] is False


def test_export_omits_unrepresentable_restart_and_preserves_four_denominator(tmp_path):
    archive, campaign_ref, _ = make_saved_campaign(tmp_path, native_pending="restart")
    exported = supervisor.read_bound(supervisor.export_results(campaign_ref, archive / "export"))
    saved = supervisor.read_bound(exported["saved_results_ref"])
    assert saved["case_results"] == []
    rich = exported["case_results"][0]
    assert rich["status"] == "watchdog"
    assert rich["work"]["restart_force_calls"] is None
    assert rich["work"]["unknown_pending_attempts"] == 0
    assert rich["accounting"]["restart_pending"] == 1
    assert rich["legacy_exported"] is False
    assert rich["omission_reason"] == "legacy_reader_cannot_represent_unknown_or_unverified_work"
    assert len(exported["case_results"]) == exported["denominator"] == 4
    assert all(row["work"] is None for row in exported["case_results"][1:])


def test_export_no_endpoint_failure_retains_failed_call_partition(tmp_path):
    archive, campaign_ref, _ = make_saved_campaign(tmp_path, no_native=True)
    exported = supervisor.read_bound(supervisor.export_results(campaign_ref, archive / "export"))
    saved = supervisor.read_bound(exported["saved_results_ref"])
    assert saved["case_results"] == []
    rich = exported["case_results"][0]
    assert rich["work"]["objective_attempts"] == rich["work"]["failed_attempts"] == 1
    assert rich["work"]["initial_successful_objectives"] == rich["work"]["accepted_steps"] == rich["work"]["rejected_attempts"] == 0
    assert rich["work"]["score_calls"] == 1
    assert rich["accounting"]["reused_score_receipts"] == 1
    assert rich["accounting"]["returned_dispatches"]["force"] == 0
    assert rich["accounting"]["error_dispatches"]["force"] == 1
    assert rich["accounting"].get("dispatch_error") is None
    assert rich["work"]["oracle_states"] is None
    assert rich["omission_reason"] == "legacy_start_coordinates_not_authenticated"
    assert exported["denominator"] == 4


def test_export_is_create_only_and_cannot_write_into_frozen_campaign(tmp_path):
    archive, campaign_ref, _ = make_saved_campaign(tmp_path)
    with pytest.raises(supervisor.CampaignError, match="export_cannot_change_frozen_campaign"):
        supervisor.export_results(campaign_ref, archive / "campaign" / "new-output")
    supervisor.export_results(campaign_ref, archive / "export")
    with pytest.raises(FileExistsError):
        supervisor.export_results(campaign_ref, archive / "export")


def test_export_rejects_modified_raw_native_evidence(tmp_path):
    archive, campaign_ref, _ = make_saved_campaign(tmp_path)
    path = archive / "campaign" / "perturbed_01" / "native" / "dispatch.jsonl"
    path.write_bytes(path.read_bytes() + b"{}\n")
    with pytest.raises(supervisor.CampaignError, match="bound_file_changed"):
        supervisor.export_results(campaign_ref, archive / "export")


def test_reused_score_receipt_is_separate_from_new_score_dispatch(tmp_path):
    native = tmp_path / "native"
    trial_fixture(native, ["rejected_evaluation"], scores=1, score_reuses=1)
    accounting = supervisor._journal_work(native)
    assert accounting.get("dispatch_error") is None
    assert accounting["work"]["score_calls"] == 1
    assert accounting["reused_score_receipts"] == 1
    assert accounting["raw_dispatch_starts"]["score"] == 1
    assert accounting["completed_force_dispatches"] == 1
    assert accounting["returned_dispatches"]["force"] == 0
    assert accounting["error_dispatches"]["force"] == 1
    assert accounting["dispatch_return_is_not_numerical_validation"] is True


def test_unknown_pending_score_remains_separate_from_receipt_reuse(tmp_path):
    native = tmp_path / "native"
    trial_fixture(native, ["initial"], scores=1, score_reuses=1, score_pending=1)
    accounting = supervisor._journal_work(native)
    assert accounting.get("dispatch_error") is None
    assert accounting["work"]["score_calls"] is None
    assert accounting["unknown_pending_score_attempts"] == 1
    assert accounting["reused_score_receipts"] == 1
    assert accounting["raw_dispatch_starts"]["score"] == 1
