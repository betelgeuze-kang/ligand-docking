"""Finite campaign control around the byte-identical recovered watchdog.

The archived watchdog owns process-group cleanup and sampled limits. Two new
metadata seams replace its historical route layout: the paired dispatch ledger
and the separately reviewed finite-difference gate. Numerical kernels and the
watchdog file itself are never changed.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import importlib.util
import os
from pathlib import Path
import sys
import time
import types

from . import journal, protocol


WATCHDOG_SHA256 = "1312da3ea4f1b22e59e8fb80a951aced39875e06f3320c24c6788a9e042eb7b9"


class CampaignError(RuntimeError):
    pass


def _read(path):
    return protocol._json_file(path)


def _require(condition, message):
    if not condition:
        raise CampaignError(message)


@contextmanager
def _operation_lock(root):
    fd = os.open(root / "paired-operation.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise CampaignError("another paired operation is active") from exc
        yield
    finally:
        os.close(fd)


@contextmanager
def _paired_metadata_environment(plan, phase):
    """Single parent main thread only; restore both seams even after failure."""
    _require("common" not in sys.modules, "unexpected archived common already imported")
    original = dict(os.environ)
    shim = types.ModuleType("common")
    shim.route_ledger = lambda route: journal.inspect(
        route / "work/dispatch-events.jsonl", plan["stage_caps_by_phase"][phase])
    clean = {"PATH": str(Path(plan["runtime"]["python_executable"]).parent) + ":/usr/bin:/bin",
             "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "CUDA_VISIBLE_DEVICES": "",
             "HIP_VISIBLE_DEVICES": "", "ROCR_VISIBLE_DEVICES": "",
             "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
             "PYTHONDONTWRITEBYTECODE": "1", "PFK_PAIRED_SUPERVISOR_PID": str(os.getpid())}
    try:
        os.environ.clear()
        os.environ.update(clean)
        sys.modules["common"] = shim
        yield
    finally:
        sys.modules.pop("common", None)
        os.environ.clear()
        os.environ.update(original)


def _load_watchdog(plan):
    source = Path(plan["source_roots"]["dry"]) / "vendor/audited_supervisor.py"
    _require(plan["source_files"].get(str(source)) == WATCHDOG_SHA256,
             "watchdog absent from admitted byte closure")
    _require(protocol.hash_file(source) == WATCHDOG_SHA256, "watchdog bytes changed")
    spec = importlib.util.spec_from_file_location("_paired_original_watchdog", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Historical direct/shape/release parity metadata does not describe this
    # fresh experiment. Both new 17-point FD tests are required before any arm.
    module._check_initial_parity = lambda _route, _checked: (None, [])
    return module


def _source_review(path, plan, checksum):
    review = _read(path)
    _require(review.get("plan_sha256") == checksum and review.get("verdict") == "admitted",
             "source review is not bound to this admitted plan")
    _require(review.get("root_review") is True and review.get("independent_review") is True,
             "root and independent source review required")
    _require(review.get("source_files") == plan["own_source"]["files"], "review source bytes differ")
    _require(review.get("real_objective_calls") == 0, "source review must precede numerical work")
    for binding in review.get("supporting_receipts", []):
        _require(protocol.hash_file(binding["path"]) == binding["sha256"], "review receipt changed")
    _require(bool(review.get("supporting_receipts")), "independent review evidence missing")
    return {"path": str(Path(path)), "sha256": protocol.hash_file(path)}


def reconcile_phase(root, plan, phase):
    """Do not equate a successful process exit with known, successful work."""
    route = root / "runs" / phase
    result = {"phase": phase, "status": "not_run", "admitted": False,
              "automatic_retry_admitted": False}
    if not route.exists():
        return result
    result["status"] = "failed"
    try:
        state = _read(route / "supervisor-exit.json")
        summary = _read(route / "work/summary.json")
        ledger = journal.inspect(route / "work/dispatch-events.jsonl", plan["stage_caps_by_phase"][phase])
        runtime = summary.get("journal_runtime", {})
        if (runtime.get("publication_uncertain") or runtime.get("pending")
                or summary.get("ledger", {}).get("total_work_known") is not True):
            ledger["total_work_known"] = False
            ledger["total_started_calls"] = None
            ledger["runtime_uncertainty_preserved"] = True
        result.update({"supervisor": state, "summary": summary, "ledger": ledger})
        failed = sum(row["failed"] for row in ledger["counts"].values())
        counts = {kind: row["succeeded"] for kind, row in ledger["counts"].items()}
        objectives = counts["objective"]
        diagnostic = phase.startswith("diagnostic-")
        census_ok = (objectives == 17 if diagnostic else 0 < objectives <= 641)
        census_ok = census_ok and all(counts[k] == objectives for k in (
            "source_base_full_EF", "cross_correction_EF", "internal_correction_EF",
            "backward_cross", "backward_internal", "external_graph", "source_admission_graph"))
        census_ok = census_ok and 2 * objectives <= counts["backward_base"] <= 55 * objectives
        census_ok = census_ok and counts["WL_EF"] == (objectives if phase.endswith("-wet") else 0)
        census_ok = census_ok and (0 <= counts["backward_WL"] <= 9 * objectives
                                  if phase.endswith("-wet") else counts["backward_WL"] == 0)
        terminal = ("terminal_water_global", "terminal_water_kernel", "terminal_water_backward", "terminal_water_screen")
        census_ok = census_ok and (all(counts[k] == 0 for k in terminal) if diagnostic else
            counts["terminal_water_global"] == counts["terminal_water_screen"] == 1
            and 1 <= counts["terminal_water_kernel"] <= 102
            and 1 <= counts["terminal_water_backward"] <= 726)
        valid_status = "diagnostic_passed" if phase.startswith("diagnostic-") else "completed"
        result["admitted"] = (state["reason"] == "completed" and state["returncode"] == 0
                              and not state.get("cleanup_remaining_pids")
                              and not state.get("cleanup_error") and ledger["total_work_known"]
                              and failed == 0 and summary["status"] == valid_status
                              and census_ok and summary.get("phase") == phase
                              and summary.get("frozen_sources_and_inputs_unchanged") is True
                              and runtime.get("poisoned") is False
                              and runtime.get("publication_uncertain") is False
                              and type(runtime.get("pending")) is dict and runtime["pending"] == {}
                              and summary.get("ledger") == ledger)
        result["physical_census_admitted"] = census_ok
        if result["admitted"]:
            result["status"] = valid_status
        result["summary_binding"] = {"path": str(route / "work/summary.json"),
                                      "sha256": protocol.hash_file(route / "work/summary.json")}
        result["supervisor_binding"] = {"path": str(route / "supervisor-exit.json"),
                                         "sha256": protocol.hash_file(route / "supervisor-exit.json")}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result["reconciliation_error"] = f"{type(exc).__name__}: {exc}"
        # Missing or torn journals are unknown, not zero calls.
        result.setdefault("ledger", {"total_work_known": False, "total_started_calls": None})
    return result


def _diagnostic_review(path, root, plan, checksum):
    review = _read(path)
    _require(review.get("plan_sha256") == checksum and review.get("verdict") == "admitted",
             "diagnostic review is not bound to this admitted plan")
    _require(review.get("root_review") is True and review.get("independent_review") is True,
             "root and independent numerical review required")
    _require(set(review.get("diagnostics", {})) == {"diagnostic-dry", "diagnostic-wet"},
             "both fresh diagnostic reviews required")
    for phase in ("diagnostic-dry", "diagnostic-wet"):
        item = reconcile_phase(root, plan, phase)
        _require(item["admitted"], "fresh diagnostic did not complete successfully: " + phase)
        _require(item["ledger"]["counts"]["objective"]["succeeded"] == 17,
                 "all 17 planned objective points required")
        _require(review["diagnostics"][phase] == item["summary_binding"], "diagnostic bytes differ")
    for binding in review.get("supporting_receipts", []):
        _require(protocol.hash_file(binding["path"]) == binding["sha256"], "diagnostic review receipt changed")
    _require(bool(review.get("supporting_receipts")), "independent diagnostic review evidence missing")
    return {"path": str(Path(path)), "sha256": protocol.hash_file(path)}


def execute(*, plan_path, expected_plan_sha256, operation, review_path):
    """Run one absent-only finite group; any failed phase stops this campaign."""
    started = time.monotonic()
    plan = protocol.verify_plan(plan_path, expected_plan_sha256)
    root = Path(plan_path).parent
    _require(operation in ("diagnostics", "optimize"), "unknown campaign operation")
    phases = [p for p in plan["phase_order"] if p.startswith("diagnostic-") == (operation == "diagnostics")]
    command_cap = sum(plan["limits_by_phase"][p]["wall_seconds"] for p in phases)
    marker = root / (operation + "-started.json")
    output = root / (operation + "-finished.json")
    with _operation_lock(root):
        # A marker or an existing phase is never reinterpreted as resumable.
        _require(not marker.exists() and not output.exists(), "operation already attempted; replay forbidden")
        _require(not any((root / "runs" / p).exists() for p in phases), "phase already attempted")
        if operation == "diagnostics":
            binding = _source_review(review_path, plan, expected_plan_sha256)
        else:
            binding = _diagnostic_review(review_path, root, plan, expected_plan_sha256)
        protocol.write_json_absent(marker, {"operation": operation, "plan_sha256": expected_plan_sha256,
                                           "review": binding, "command_wall_cap_seconds": command_cap,
                                           "automatic_retry_admitted": False})
        watchdog = _load_watchdog(plan)
        outcomes, failure = [], None
        try:
            for phase in phases:
                _require(time.monotonic() - started < command_cap, "aggregate active operation budget exhausted")
                command = [plan["runtime"]["python_executable"], "-I", "-B",
                           str(Path(plan["own_source"]["root"]) / "tools/run_pfk_paired_water_eight_dof.py"),
                           "worker", "--plan", str(plan_path), "--expected-plan-sha256", expected_plan_sha256,
                           "--phase", phase, "--output-dir", str(root / "runs" / phase / "work")]

                def sample(_state):
                    _require(time.monotonic() - started < command_cap, "aggregate active operation budget exhausted")

                with _paired_metadata_environment(plan, phase):
                    watchdog.supervise_run(root, phase, plan["limits_by_phase"][phase], command,
                                           plan_sha256=expected_plan_sha256,
                                           prelaunch=lambda: protocol.verify_plan(plan_path, expected_plan_sha256),
                                           sample_hook=sample)
                protocol.verify_plan(plan_path, expected_plan_sha256)
                item = reconcile_phase(root, plan, phase)
                outcomes.append(item)
                if not item["admitted"]:
                    failure = "phase did not reconcile: " + phase
                    break
        except BaseException as exc:
            failure = f"{type(exc).__name__}: {exc}"
        finally:
            # Preserve the declared denominator after an early stop.
            present = {item["phase"] for item in outcomes}
            outcomes.extend(reconcile_phase(root, plan, p) for p in phases if p not in present)
            source_error = None
            try:
                protocol.verify_plan(plan_path, expected_plan_sha256)
            except BaseException as exc:
                source_error = f"{type(exc).__name__}: {exc}"
            status = "completed" if failure is None and source_error is None and all(i["admitted"] for i in outcomes) else "failed"
            result = {"operation": operation, "status": status, "plan_sha256": expected_plan_sha256,
                      "review": binding, "phases": outcomes, "failure": failure,
                      "source_verification_error": source_error,
                      "active_parent_wall_seconds": time.monotonic() - started,
                      "command_wall_cap_seconds": command_cap, "automatic_retry_admitted": False,
                      "accounting_note": "parent verification/control included; review idle time and environment preparation separate"}
            protocol.write_json_absent(output, result)
        return result
