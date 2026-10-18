"""Synthetic control records only; no recovered numerical modules are imported."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import types

import pytest

from tools.pfk_paired_water_eight_dof import journal, protocol, supervisor as s


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n")
    return {"path": str(path), "sha256": protocol.hash_file(path)}


@pytest.fixture
def campaign(tmp_path, monkeypatch):
    monkeypatch.delitem(sys.modules, "common", raising=False)
    root = tmp_path / "campaign"
    root.mkdir()
    own = tmp_path / "own/worker.py"
    source = put(own, {"synthetic_source": True})
    plan = {"phase_order": list(protocol.PHASE_ORDER),
            "stage_caps_by_phase": {p: protocol.stage_caps(p) for p in protocol.PHASE_ORDER},
            "limits_by_phase": {p: protocol.phase_limits(p) for p in protocol.PHASE_ORDER},
            "runtime": {"python_executable": sys.executable},
            "own_source": {"root": str(own.parent), "files": {source["path"]: source["sha256"]}},
            "source_roots": {"dry": str(tmp_path / "archive/dry"), "water": str(tmp_path / "archive/water")}}
    plan_binding = put(root / "plan.json", {"synthetic_plan": True})
    checksum = plan_binding["sha256"]
    support = put(tmp_path / "independent-review-evidence.json", {"synthetic_source_review": True})
    review = {"plan_sha256": checksum, "verdict": "admitted", "root_review": True,
              "independent_review": True, "source_files": plan["own_source"]["files"],
              "real_objective_calls": 0, "supporting_receipts": [support]}
    source_review = put(tmp_path / "source-review.json", review)
    verified = []

    def verify(path, expected):
        assert Path(path) == root / "plan.json" and expected == checksum
        verified.append((path, expected))
        return plan

    monkeypatch.setattr(protocol, "verify_plan", verify)
    return types.SimpleNamespace(root=root, plan=plan, checksum=checksum,
                                 plan_path=root / "plan.json", source_review=Path(source_review["path"]),
                                 review=review, support=support, verified=verified)


def physical_counts(phase):
    diagnostic = phase.startswith("diagnostic-")
    n = 17 if diagnostic else 1
    counts = {k: 0 for k in protocol.stage_caps(phase)}
    for key in ("objective", "source_base_full_EF", "cross_correction_EF", "internal_correction_EF",
                "backward_cross", "backward_internal", "external_graph", "source_admission_graph"):
        counts[key] = n
    counts["backward_base"] = 2 * n
    if phase.endswith("-wet"):
        counts["WL_EF"], counts["backward_WL"] = n, 9 * n
    if not diagnostic:
        counts.update(terminal_water_global=1, terminal_water_screen=1,
                      terminal_water_kernel=3, terminal_water_backward=9)
    return counts


def ledger_bytes(counts, failed_kind=None):
    # Simulated worker publication, not dispatch. Construct actual chain hashes
    # so corruption/partial records are tested by the production inspector.
    chain, serial, lines = "0" * 64, 0, []
    for kind, count in counts.items():
        for index in range(count):
            serial += 1
            for event, success in (("started", None), ("finished", not (kind == failed_kind and index == 0))):
                row = {"schema": journal.SCHEMA, "previous_sha256": chain, "elapsed_seconds": 0.0,
                       "id": serial, "kind": kind, "event": event, "success": success}
                checksum = journal.digest(row)
                lines.append((journal.canonical({**row, "record_sha256": checksum}) + "\n").encode())
                chain = checksum
    return b"".join(lines)


def write_phase(campaign, phase, *, mode="complete", count_changes=None, summary_changes=None, state_changes=None):
    work = campaign.root / "runs" / phase / "work"
    work.mkdir(parents=True)
    counts = physical_counts(phase)
    counts.update(count_changes or {})
    path = work / "dispatch-events.jsonl"
    path.write_bytes(ledger_bytes(counts, "source_base_full_EF" if mode == "failed_stage" else None))
    known_ledger = journal.inspect(path, campaign.plan["stage_caps_by_phase"][phase])
    summary = {"phase": phase, "plan_sha256": campaign.checksum,
               "status": "diagnostic_passed" if phase.startswith("diagnostic-") else "completed",
               "ledger": copy.deepcopy(known_ledger),
               "journal_runtime": {"poisoned": False, "pending": {}, "publication_uncertain": False},
               "frozen_sources_and_inputs_unchanged": True,
               "module_origins": {"tools.pfk_paired_water_eight_dof.worker": next(iter(campaign.plan["own_source"]["files"]))},
               "automatic_retry_admitted": False, "new_objectives": 17,
               "all_gradient_components_passed": True,
               "result": [{"index": i, "passed": True, "step": 1e-5} for i in range(8)],
               "attempts": counts["objective"], "extra_final_or_replay_ligand_EF": 0}
    if phase.endswith("-wet"):
        summary["WL_work"] = {"total_work_known": True, "poisoned": False,
                              "unknown_work_reissued": False, "total_kernel_calls": counts["WL_EF"],
                              "total_backward_calls": counts["backward_WL"], "stages": {}}
    else:
        summary["WL_work"] = None
    summary.update(summary_changes or {})
    put(work / "summary.json", summary)
    state = {"reason": "completed", "returncode": 0, "cleanup_remaining_pids": [],
             "cleanup_error": None, "plan_sha256": campaign.checksum}
    state.update(state_changes or {})
    put(work.parent / "supervisor-exit.json", state)
    if mode == "missing":
        path.unlink()
    elif mode == "torn":
        path.write_bytes(path.read_bytes() + b'{"unfinished":')
    elif mode == "pending":
        path.write_bytes(b"\n".join(path.read_bytes().split(b"\n")[:-2]) + b"\n")
    elif mode == "empty":
        path.write_bytes(b"")
    elif mode == "modified":
        path.write_bytes(path.read_bytes().replace(b'"elapsed_seconds":0.0', b'"elapsed_seconds":1.0', 1))
    return work


@pytest.mark.parametrize("phase", protocol.PHASE_ORDER)
def test_complete_synthetic_physical_census_reconciles(campaign, phase):
    write_phase(campaign, phase)
    item = s.reconcile_phase(campaign.root, campaign.plan, phase)
    assert item["admitted"] and item["ledger"]["total_work_known"]
    assert item["physical_census_admitted"]


@pytest.mark.parametrize("mode", ["missing", "torn", "pending", "modified"])
def test_successful_exit_and_complete_claim_cannot_hide_unknown_journal(campaign, mode):
    write_phase(campaign, "P0-wet", mode=mode)
    item = s.reconcile_phase(campaign.root, campaign.plan, "P0-wet")
    assert not item["admitted"] and item["status"] == "failed"
    assert item["ledger"]["total_work_known"] is False
    assert item["ledger"]["total_started_calls"] is None
    assert item["automatic_retry_admitted"] is False


@pytest.mark.parametrize("phase", ["diagnostic-dry", "P0-wet"])
def test_empty_journal_is_not_a_completed_experiment(campaign, phase):
    write_phase(campaign, phase, mode="empty")
    item = s.reconcile_phase(campaign.root, campaign.plan, phase)
    assert not item["admitted"] and not item["physical_census_admitted"]


@pytest.mark.parametrize("change", [
    {"source_base_full_EF": 0}, {"cross_correction_EF": 0}, {"internal_correction_EF": 0},
    {"source_admission_graph": 0}, {"external_graph": 0}, {"backward_base": 1},
    {"WL_EF": 0}, {"terminal_water_global": 0},
    {"terminal_water_screen": 0}, {"terminal_water_kernel": 0}, {"terminal_water_backward": 0},
])
def test_incomplete_physical_census_is_rejected(campaign, change):
    write_phase(campaign, "P0-wet", count_changes=change)
    assert not s.reconcile_phase(campaign.root, campaign.plan, "P0-wet")["admitted"]


def test_zero_active_pair_wet_kernel_can_complete_without_backward_dispatch(campaign):
    # The original pair kernel skips differentiation for blocks without any
    # active pairs. Kernel dispatch still has to be present and acknowledged.
    write_phase(campaign, "P0-wet", count_changes={"backward_WL": 0})
    item = s.reconcile_phase(campaign.root, campaign.plan, "P0-wet")
    assert item["admitted"] and item["ledger"]["counts"]["WL_EF"]["succeeded"] == 1
    assert item["ledger"]["counts"]["backward_WL"]["succeeded"] == 0


def test_wet_backward_overcap_cannot_be_hidden_by_successful_worker_exit(campaign):
    write_phase(campaign, "P0-wet", count_changes={"backward_WL": 10})
    item = s.reconcile_phase(campaign.root, campaign.plan, "P0-wet")
    # Ten fits the absolute 641-objective campaign ceiling, but exceeds the
    # original nine-block bound for this one completed objective.
    assert not item["admitted"] and not item["physical_census_admitted"]
    assert item["ledger"]["total_work_known"]


def test_worker_claimed_counts_must_equal_independent_durable_counts(campaign):
    work = write_phase(campaign, "P0-dry")
    summary = json.loads((work / "summary.json").read_text())
    summary["ledger"]["counts"]["objective"]["succeeded"] += 1
    put(work / "summary.json", summary)
    item = s.reconcile_phase(campaign.root, campaign.plan, "P0-dry")
    assert item["physical_census_admitted"] and not item["admitted"]


@pytest.mark.parametrize("runtime", [
    {"poisoned": True, "pending": {}, "publication_uncertain": False},
    {"poisoned": False, "pending": {"WL_EF": 1}, "publication_uncertain": False},
    {"poisoned": False, "pending": {}, "publication_uncertain": True},
    {"poisoned": False}, {},
])
def test_runtime_uncertainty_is_never_erased_by_a_complete_log(campaign, runtime):
    write_phase(campaign, "P0-wet", summary_changes={"journal_runtime": runtime})
    assert not s.reconcile_phase(campaign.root, campaign.plan, "P0-wet")["admitted"]


@pytest.mark.parametrize("state", [{"reason": "timeout"}, {"returncode": 1},
                                     {"cleanup_remaining_pids": [123456]}, {"cleanup_error": "synthetic cleanup failure"}])
def test_cleanup_and_process_failures_block_admission(campaign, state):
    write_phase(campaign, "P0-dry", state_changes=state)
    assert not s.reconcile_phase(campaign.root, campaign.plan, "P0-dry")["admitted"]


def test_failed_dispatch_source_drift_or_worker_unknown_ledger_cannot_pass(campaign):
    for phase, kwargs in [("P0-dry", {"mode": "failed_stage"}),
                          ("P0-wet", {"summary_changes": {"frozen_sources_and_inputs_unchanged": False}}),
                          ("Qplus-dry", {"summary_changes": {"ledger": {"total_work_known": False}}})]:
        write_phase(campaign, phase, **kwargs)
        assert not s.reconcile_phase(campaign.root, campaign.plan, phase)["admitted"]


@pytest.mark.parametrize("mutation", [
    lambda review: review.update(plan_sha256="a" * 64),
    lambda review: review.update(independent_review=False),
    lambda review: review.update(root_review=False),
    lambda review: review.update(source_files={}),
    lambda review: review.update(real_objective_calls=1),
    lambda review: review.update(supporting_receipts=[]),
])
def test_source_review_must_bind_exact_plan_bytes_and_zero_call_review(campaign, mutation):
    review = copy.deepcopy(campaign.review)
    mutation(review)
    put(campaign.source_review, review)
    with pytest.raises(s.CampaignError):
        s._source_review(campaign.source_review, campaign.plan, campaign.checksum)


def test_changed_independent_review_receipt_is_rejected(campaign):
    Path(campaign.support["path"]).write_text('{"changed_after_review":true}')
    with pytest.raises(s.CampaignError, match="receipt changed"):
        s._source_review(campaign.source_review, campaign.plan, campaign.checksum)


def diagnostic_review(campaign):
    bindings = {}
    for phase in ("diagnostic-dry", "diagnostic-wet"):
        write_phase(campaign, phase)
        bindings[phase] = s.reconcile_phase(campaign.root, campaign.plan, phase)["summary_binding"]
    path = campaign.root.parent / "diagnostic-review.json"
    review = {"plan_sha256": campaign.checksum, "verdict": "admitted", "root_review": True,
              "independent_review": True, "diagnostics": bindings,
              "supporting_receipts": [campaign.support]}
    put(path, review)
    return path, review


def test_fd_review_requires_both_fresh_exact_summary_bytes(campaign):
    path, _ = diagnostic_review(campaign)
    assert s._diagnostic_review(path, campaign.root, campaign.plan, campaign.checksum)["sha256"] == protocol.hash_file(path)
    summary_path = campaign.root / "runs/diagnostic-wet/work/summary.json"
    document = json.loads(summary_path.read_text())
    document["after_review_change"] = True
    put(summary_path, document)
    with pytest.raises(s.CampaignError, match="diagnostic bytes differ"):
        s._diagnostic_review(path, campaign.root, campaign.plan, campaign.checksum)


def test_fd_review_rejects_missing_arm_or_sixteen_point_diagnostic(campaign):
    path, review = diagnostic_review(campaign)
    del review["diagnostics"]["diagnostic-wet"]
    put(path, review)
    with pytest.raises(s.CampaignError, match="both fresh"):
        s._diagnostic_review(path, campaign.root, campaign.plan, campaign.checksum)
    review["diagnostics"]["diagnostic-wet"] = {"path": "irrelevant", "sha256": "0" * 64}
    put(path, review)
    ledger_path = campaign.root / "runs/diagnostic-wet/work/dispatch-events.jsonl"
    counts = physical_counts("diagnostic-wet")
    counts["objective"] = 16
    ledger_path.write_bytes(ledger_bytes(counts))
    with pytest.raises(s.CampaignError, match="did not complete"):
        s._diagnostic_review(path, campaign.root, campaign.plan, campaign.checksum)


def test_environment_and_common_metadata_seam_restore_after_base_exception(campaign, monkeypatch):
    monkeypatch.setenv("PFK_UNRELATED_SYNTHETIC_SECRET", "must stay in parent only")
    before = dict(os.environ)
    with pytest.raises(KeyboardInterrupt):
        with s._paired_metadata_environment(campaign.plan, "P0-dry"):
            assert "PFK_UNRELATED_SYNTHETIC_SECRET" not in os.environ
            assert "HOME" not in os.environ and not any(k.startswith("LD_") for k in os.environ)
            assert os.environ["OMP_NUM_THREADS"] == "1"
            assert callable(sys.modules["common"].route_ledger)
            raise KeyboardInterrupt("synthetic interrupted watchdog")
    assert dict(os.environ) == before and "common" not in sys.modules


def test_preexisting_common_module_is_preserved_when_metadata_seam_refuses_entry(campaign, monkeypatch):
    original = types.ModuleType("common")
    monkeypatch.setitem(sys.modules, "common", original)
    before = dict(os.environ)
    with pytest.raises(s.CampaignError, match="already imported"):
        with s._paired_metadata_environment(campaign.plan, "P0-dry"):
            pytest.fail("unexpected metadata seam entry")
    assert sys.modules["common"] is original and dict(os.environ) == before


@pytest.mark.parametrize("mode", ["pending", "torn", "failed_stage", "interrupt"])
def test_first_failed_or_unknown_phase_stops_group_and_marker_forbids_retry(campaign, monkeypatch, mode):
    calls, before = [], dict(os.environ)
    def supervise(root, phase, limits, command, **kwargs):
        calls.append(phase)
        assert "-I" in command and "-B" in command and sys.modules["common"].route_ledger
        kwargs["prelaunch"]()
        kwargs["sample_hook"]({})
        write_phase(campaign, phase, mode="pending" if mode == "interrupt" else mode)
        if mode == "interrupt":
            raise KeyboardInterrupt("synthetic cleanup completed after interrupted dispatch")
    monkeypatch.setattr(s, "_load_watchdog", lambda plan: types.SimpleNamespace(supervise_run=supervise))
    result = s.execute(plan_path=campaign.plan_path, expected_plan_sha256=campaign.checksum,
                       operation="diagnostics", review_path=campaign.source_review)
    assert result["status"] == "failed" and calls == ["diagnostic-dry"]
    assert [p["phase"] for p in result["phases"]] == ["diagnostic-dry", "diagnostic-wet"]
    assert result["phases"][1]["status"] == "not_run" and not result["automatic_retry_admitted"]
    assert (campaign.root / "diagnostics-started.json").exists()
    assert (campaign.root / "diagnostics-finished.json").exists()
    assert dict(os.environ) == before and "common" not in sys.modules
    with pytest.raises(s.CampaignError, match="replay forbidden"):
        s.execute(plan_path=campaign.plan_path, expected_plan_sha256=campaign.checksum,
                  operation="diagnostics", review_path=campaign.source_review)
    assert calls == ["diagnostic-dry"]


def test_source_verifier_failure_after_phase_stops_before_next_launch(campaign, monkeypatch):
    calls = []
    def supervise(root, phase, limits, command, **kwargs):
        calls.append(phase)
        write_phase(campaign, phase)
    def fail_after_first(path, expected):
        if calls:
            raise protocol.PlanError("synthetic source drift")
        return campaign.plan
    monkeypatch.setattr(s, "_load_watchdog", lambda plan: types.SimpleNamespace(supervise_run=supervise))
    monkeypatch.setattr(protocol, "verify_plan", fail_after_first)
    result = s.execute(plan_path=campaign.plan_path, expected_plan_sha256=campaign.checksum,
                       operation="diagnostics", review_path=campaign.source_review)
    assert result["status"] == "failed" and calls == ["diagnostic-dry"]
    assert "source drift" in result["source_verification_error"]
    assert result["phases"][1]["status"] == "not_run"


def test_watchdog_bootstrap_failure_preserves_attempt_marker_and_forbids_retry(campaign, monkeypatch):
    calls = []
    def fail(plan):
        calls.append(True)
        raise s.CampaignError("synthetic watchdog byte admission failed")
    monkeypatch.setattr(s, "_load_watchdog", fail)
    with pytest.raises(s.CampaignError, match="byte admission failed"):
        s.execute(plan_path=campaign.plan_path, expected_plan_sha256=campaign.checksum,
                  operation="diagnostics", review_path=campaign.source_review)
    assert (campaign.root / "diagnostics-started.json").exists()
    assert not (campaign.root / "diagnostics-finished.json").exists()
    with pytest.raises(s.CampaignError, match="replay forbidden"):
        s.execute(plan_path=campaign.plan_path, expected_plan_sha256=campaign.checksum,
                  operation="diagnostics", review_path=campaign.source_review)
    assert calls == [True]


def test_operation_lock_refuses_overlapping_parent_but_releases_after_exception(campaign):
    with pytest.raises(KeyboardInterrupt):
        with s._operation_lock(campaign.root):
            with pytest.raises(s.CampaignError, match="another paired operation"):
                with s._operation_lock(campaign.root):
                    pytest.fail("overlapping campaign lock was acquired")
            raise KeyboardInterrupt("synthetic parent interruption")
    with s._operation_lock(campaign.root):
        pass


@pytest.fixture
def driver():
    path = Path(__file__).resolve().parents[2] / "tools/run_pfk_paired_water_eight_dof.py"
    old_path, old_bytecode = list(sys.path), sys.dont_write_bytecode
    try:
        spec = importlib.util.spec_from_file_location("_synthetic_paired_driver", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.path[:] = old_path
        sys.dont_write_bytecode = old_bytecode


def test_driver_report_passes_only_three_agreed_arguments(driver, campaign, monkeypatch, capsys):
    received = []
    fake = types.ModuleType("tools.pfk_paired_water_eight_dof.report")
    fake.build_report = lambda **kwargs: (received.append(kwargs) or {"status": "synthetic_report"})
    monkeypatch.setitem(sys.modules, fake.__name__, fake)
    output = campaign.root / "report.json"
    assert driver.main(["report", "--plan", str(campaign.plan_path), "--expected-plan-sha256", campaign.checksum,
                        "--output", str(output)]) == 0
    assert received == [{"plan_path": campaign.plan_path, "expected_plan_sha256": campaign.checksum, "output_path": output}]
    assert json.loads(capsys.readouterr().out)["status"] == "synthetic_report"


def test_driver_diagnostics_failure_returns_nonzero_without_reissuing(driver, campaign, monkeypatch, capsys):
    received = []
    def execute(**kwargs):
        received.append(kwargs)
        return {"status": "failed", "failure": "unknown dispatch", "phases": [{"phase": "diagnostic-dry", "status": "failed"}]}
    monkeypatch.setattr(s, "execute", execute)
    assert driver.main(["diagnostics", "--plan", str(campaign.plan_path), "--expected-plan-sha256", campaign.checksum,
                        "--review", str(campaign.source_review)]) == 1
    assert len(received) == 1 and received[0]["operation"] == "diagnostics"
    assert json.loads(capsys.readouterr().out)["failure"] == "unknown dispatch"


def test_driver_status_retains_full_phase_denominator_and_unknown_totals(driver, campaign, monkeypatch, capsys):
    def reconcile(root, plan, phase):
        return {"phase": phase, "status": "failed" if phase == "P0-wet" else "not_run",
                "ledger": {"total_work_known": False, "total_started_calls": None}}
    monkeypatch.setattr(s, "reconcile_phase", reconcile)
    assert driver.main(["status", "--plan", str(campaign.plan_path), "--expected-plan-sha256", campaign.checksum]) == 0
    result = json.loads(capsys.readouterr().out)
    assert [r["phase"] for r in result["phases"]] == list(protocol.PHASE_ORDER)
    assert all(r["total_work_known"] is False for r in result["phases"])


def test_driver_worker_forwards_control_arguments_without_importing_real_worker(driver, campaign, monkeypatch):
    received = []
    fake = types.ModuleType("tools.pfk_paired_water_eight_dof.worker")
    fake.main = lambda arguments: (received.append(arguments) or 7)
    monkeypatch.setitem(sys.modules, fake.__name__, fake)
    output = campaign.root / "work"
    assert driver.main(["worker", "--plan", str(campaign.plan_path), "--expected-plan-sha256", campaign.checksum,
                        "--phase", "P0-dry", "--output-dir", str(output)]) == 7
    assert received == [["--plan", str(campaign.plan_path), "--expected-plan-sha256", campaign.checksum,
                         "--phase", "P0-dry", "--output-dir", str(output)]]


def test_driver_plan_dispatch_does_not_print_whole_frozen_source_manifest(driver, campaign, monkeypatch, capsys):
    received = []
    spec_path = campaign.root / "synthetic-spec.json"
    put(spec_path, {"synthetic": True})
    def build(**kwargs):
        received.append(kwargs)
        return {"plan_path": str(campaign.plan_path), "plan_sha256": campaign.checksum,
                "plan": {"source_files": {"should_not_print": "full manifest"}}}
    monkeypatch.setattr(protocol, "build_plan", build)
    assert driver.main(["plan", "--spec", str(spec_path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert received == [{"synthetic": True}]
    assert set(result) == {"plan_path", "plan_sha256"}
