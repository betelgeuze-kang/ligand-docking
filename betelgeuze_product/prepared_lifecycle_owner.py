"""One fenced prepared owner; fixed installed child and conservative recovery."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys
import threading
import time

from .prepared_lifecycle import (admission_document, digest, implementation_sources, json_bytes,
    private_root, process_identity, regular_bytes, require, write_absent)

_OWNER_LOCK = threading.Lock()


def public_resource_receipt(value):
    if isinstance(value, dict):
        return {key: public_resource_receipt(item) for key, item in value.items()
                if key not in ("tree_root", "cwd", "command", "environment", "stdout", "stderr")}
    if isinstance(value, list):
        return [public_resource_receipt(item) for item in value]
    return value


def require_runtime():
    from api.validated_runner_runtime_qualification import require_validated_runner_namespace_runtime
    qualified = require_validated_runner_namespace_runtime()
    return {"receipt_sha256": qualified.receipt_sha256,
            "schema_version": qualified.schema_version, "qualified": qualified.qualified}


def reconcile_lost_owners(service):
    """Owner disappearance is unknown, never a retry queue transition."""
    with service._connect() as connection:
        rows = [dict(row) for row in connection.execute(
            "SELECT * FROM prepared_jobs WHERE tenant=? AND status IN ('running','cancel_requested')",
            (service.tenant_id,)).fetchall()]
    results = []
    for row in rows:
        if row["owner_pid"] and row["owner_start"] and process_identity(row["owner_pid"]) == row["owner_start"]:
            continue
        policy = json.loads(row["policy_json"])
        results.append(service._finish(row, status="interrupted_unknown", numerical_state="interrupted_unknown",
            error={"code": "OWNER_LOST", "stage": "owner_reconciliation", "retry_allowed": False},
            receipt={"process_terminal_confirmed": False, "owner_identity_missing": True},
            force_known=False, wall=max(0., policy["wall_seconds"] - row["wall_spent"]),
            cpu=max(0., policy["cpu_seconds"] - row["cpu_spent"]), spawned=True))
    return results


def run_one(service, *, execution_id=None, process_runner=None):
    """Only explicitly queued work may start; return None when this tenant is idle.

    ``process_runner`` is a trusted Python dependency seam for unit tests, never
    a request field. Normal calls always use the installed namespace controller.
    """
    require(_OWNER_LOCK.acquire(blocking=False), "BUSY", "This owner already has active work", 409)
    try:
        return _run_one(service, execution_id=execution_id, process_runner=process_runner)
    finally:
        _OWNER_LOCK.release()


def _run_one(service, *, execution_id, process_runner):
    reconcile_lost_owners(service)
    claim = service._claim(execution_id)
    if claim is None:
        return None
    job = service.root / "jobs" / claim["execution_id"]
    attempts = job / "attempts"
    attempt = attempts / str(claim["generation"]).zfill(6)
    policy = json.loads(claim["policy_json"])
    limits = {"wall_seconds": math.floor(claim["reserved_wall"]),
              "cpu_seconds": math.floor(claim["reserved_cpu"]),
              "address_space_bytes": policy["address_space_bytes"],
              "file_bytes": policy["file_bytes"], "cpu_affinity": policy["cpu_affinity"],
              "capture_bytes": policy["capture_bytes"], "tree_bytes": policy["output_bytes"],
              "tree_root": str(job),
              "poll_seconds": .02}
    spawned = False
    t0 = time.monotonic()
    stop, cancelled = threading.Event(), threading.Event()
    artifacts = []
    try:
        private_root(job, create=True)
        private_root(attempts, create=True)
        attempt.mkdir(mode=0o700)
        require(limits["wall_seconds"] >= 1 and limits["cpu_seconds"] >= 1,
                "BUDGET_EXHAUSTED", "Less than one second remains in the cumulative budget", 409)
        qualification = require_runtime()
        require(qualification.get("qualified") is True, "RUNTIME_UNQUALIFIED", "Namespace runtime is not qualified", 503)
        admission = json.loads(claim["admission_json"])
        require(admission_document(service.input_root, admission["admission_id"], tenant_id=service.tenant_id) == admission,
                "SOURCE_OR_MODEL_MISMATCH", "Registered source bytes changed", 409)
        binding = {"schema_version": "prepared_lifecycle_invocation/1.0.0",
            "execution_id": claim["execution_id"], "tenant": service.tenant_id,
            "state_root": str(service.root), "input_root": str(service.input_root),
            "job_root": str(job), "attempt_root": str(attempt),
            "owner_token_sha256": hashlib.sha256(claim["owner_token"].encode()).hexdigest(),
            "generation": claim["generation"], "resume": claim["resume"],
            "admission": admission, "limits": limits, "policy": policy,
            "implementation_sources": implementation_sources(), "qualification": qualification}
        binding_path = attempt / "binding.json"
        write_absent(binding_path, binding)
        # The binding contains private local source paths and is not a public artifact.
        command = [sys.executable, "-I", "-B", "-m", "betelgeuze_product.prepared_lifecycle_worker",
                   "--binding", str(binding_path), "--owner-token", claim["owner_token"]]
        environment = {"PATH": str(Path(sys.executable).parent) + ":/usr/bin:/bin",
            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1",
            "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
            "CUDA_VISIBLE_DEVICES": "", "HIP_VISIBLE_DEVICES": "", "ROCR_VISIBLE_DEVICES": ""}

        def watch():
            while not stop.wait(.02):
                try:
                    with service._connect() as connection:
                        current = service._row(connection, claim["execution_id"])
                    if current["owner_token"] != claim["owner_token"] or current["cancel_requested"]:
                        cancelled.set()
                except BaseException:
                    cancelled.set()  # Failure to observe ownership cannot admit more work.

        watcher = threading.Thread(target=watch, daemon=True)
        watcher.start()
        try:
            if process_runner is None:
                from api.linux_runner_supervisor import require_linux_runner_supervisor_support
                from api.runner_process import run_contained
                require_linux_runner_supervisor_support()
                process_runner = run_contained
            # The controller may reject resources before spawning. Its explicit
            # resource error is reconciled below as zero-dispatch unqualified.
            spawned = True
            process_started = time.monotonic()
            outcome = process_runner(command, cwd=job, environment=environment,
                timeout_seconds=limits["wall_seconds"], cancellation_event=cancelled, limits=limits)
            process_returned = time.monotonic()
        finally:
            stop.set()
            watcher.join(timeout=1.)
        process_path = attempt / "process.json"
        # Retain a bounded capture, never public credential-bearing command/env.
        outcome = dict(outcome)
        for name in ("stdout", "stderr"):
            if isinstance(outcome.get(name), str):
                outcome[name] = outcome[name][:policy["capture_bytes"]]
        write_absent(process_path, {"schema_version": "prepared_lifecycle_process/1.0.0", **outcome})
        # Raw process capture is retained privately; public errors are typed.
        result_path = attempt / "result.json"
        result = json_bytes(regular_bytes(result_path, job)) if result_path.exists() else None
        contained = (not outcome.get("containment_error")
                     and outcome.get("containment_evidence", {}).get("namespace_exit_verified") is True)
        if outcome.get("runner_start_admitted") is False and contained:
            # This field is parent-owned, emitted only by the explicit-envelope
            # controller after checking its nonce-bound start gate.
            return service._finish(claim, status="unqualified", numerical_state=claim["numerical_state"],
                error={"code": "RUNTIME_UNQUALIFIED", "stage": "runner_start_gate", "retry_allowed": False},
                receipt={"process_terminal_confirmed": True, "runner_start_admitted": False,
                         "process": outcome}, force_known=True, wall=time.monotonic()-t0,
                cpu=claim["reserved_cpu"], spawned=False)
        if result is not None:
            require(isinstance(result, dict) and result.get("execution_id") == claim["execution_id"]
                    and result.get("generation") == claim["generation"]
                    and result.get("schema_version") == "prepared_lifecycle_numerical_result/1.0.0"
                    and type(result.get("total_work_known")) is bool
                    and result.get("status") in ("complete", "paused", "failed", "interrupted_unknown"),
                    "ARTIFACT_PUBLICATION_UNKNOWN", "Numerical result binding differs", 409)
        require(implementation_sources() == binding["implementation_sources"]
                and admission_document(service.input_root, admission["admission_id"], tenant_id=service.tenant_id) == admission,
                "SOURCE_OR_MODEL_MISMATCH", "Source identity changed during execution", 409)
        known = bool(contained and outcome.get("returncode") == 0 and result
                     and result.get("total_work_known") is True)
        status = result.get("status") if known else "interrupted_unknown"
        if outcome.get("cancelled") and contained and not (known and status == "complete"):
            status = "cancelled"
        elif outcome.get("returncode") != 0 and known:
            status = "failed"
        if result_path.exists():
            artifacts.append((result_path, "numerical_invocation_result"))
        report_path = attempt / "report.json"
        if report_path.exists():
            report_document = json_bytes(regular_bytes(report_path, job))
            require(result is not None and result.get("report_sha256") == digest(report_document),
                    "ARTIFACT_PUBLICATION_UNKNOWN", "Retained report binding differs", 409)
            artifacts.append((report_path, "retained_refinement_report"))
        else:
            require(not known, "ARTIFACT_PUBLICATION_UNKNOWN", "Retained report is missing", 409)
        force = result.get("known_force_calls") if result else None
        require(not known or type(force) is int, "ARTIFACT_PUBLICATION_UNKNOWN", "Missing known force census", 409)
        numerical = result.get("numerical_state", result.get("status")) if known else "interrupted_unknown"
        error = None if known and status in ("complete", "paused") else {
            "code": "CANCEL_CONFIRMED" if status == "cancelled" else
                    "INTERRUPTED_UNKNOWN" if not known else "KNOWN_NUMERICAL_FAILURE",
            "stage": "contained_execution", "retry_allowed": False}
        usage = outcome.get("resource_usage", {})
        measured_cpu = usage.get("child_cpu_seconds")
        if (usage.get("measurement_complete") is not True
                or type(measured_cpu) not in (int, float)
                or not math.isfinite(measured_cpu) or measured_cpu < 0):
            measured_cpu = claim["reserved_cpu"]
            usage = {**usage, "CPU_measurement_available": False,
                     "CPU_charged_conservative_reserved_cap": True}
        manifest = {"schema_version": "prepared_lifecycle_artifact_manifest/1.0.0",
            "execution_id": claim["execution_id"], "generation": claim["generation"],
            "status": status, "numerical_state": numerical, "total_work_known": known,
            "known_force_calls": force, "process_terminal_confirmed": contained,
            "implementation_sources": binding["implementation_sources"],
            "runtime_identity": admission["runtime_identity"],
            "protocol_sha256": admission["manifest"]["protocol_sha256"],
            "artifact_content_sha256": {path.name: hashlib.sha256(regular_bytes(path, job)).hexdigest()
                                       for path, _role in artifacts},
            "resources": {"requested": {k: v for k, v in limits.items() if k != "tree_root"},
                          "applied": public_resource_receipt(outcome.get("applied_resources")),
                          "usage": usage},
            "timings": {"owner_prelaunch_wall_seconds": process_started-t0,
                        "controller_call_wall_seconds": process_returned-process_started,
                        "runner_execution_timeout_seconds": limits["wall_seconds"],
                        "controller_call_scope": "includes bootstrap, execution and separately bounded cleanup",
                        "execution_active_wall_seconds": None, "cleanup_wall_seconds": None,
                        "unavailable_scope": "controller does not separately measure active execution and cleanup"},
            "error": error, "research_only": True, "qualified": False}
        manifest_path = attempt / "manifest.json"
        write_absent(manifest_path, manifest)
        artifacts.append((manifest_path, "execution_artifact_manifest"))
        return service._finish(claim, status=status, numerical_state=numerical,
            receipt={"process_terminal_confirmed": contained, "process": outcome,
                     "owner_elapsed_wall_seconds": time.monotonic()-t0,
                     "wall_accounting_scope": "owner elapsed including setup, controller cleanup and publication; cleanup may exceed the runner timeout",
                     "CPU_accounting_scope": "namespace-reaped subtree measurement when present; full reserved cap when unavailable"},
            error=error, known_force=force, force_known=known,
            wall=time.monotonic()-t0, cpu=measured_cpu, spawned=True, artifacts=artifacts)
    except BaseException as exc:
        stop.set()
        # Only resource/qualification rejection known to happen before spawn is
        # zero work. Other failures after requesting a process remain unknown.
        pre_spawn = not spawned or getattr(exc, "runner_start_admitted", None) is False
        code = (getattr(exc, "code", None) or "RUNTIME_UNQUALIFIED") if pre_spawn else "INTERRUPTED_UNKNOWN"
        status = "unqualified" if pre_spawn else "interrupted_unknown"
        return service._finish(claim, status=status,
            numerical_state=claim["numerical_state"] if pre_spawn else "interrupted_unknown",
            error={"code": code, "stage": "runtime_admission" if pre_spawn else "owner_publication", "retry_allowed": False},
            receipt={"process_terminal_confirmed": False, "dispatch_admitted": not pre_spawn,
                     "exception_class": type(exc).__name__},
            force_known=pre_spawn, wall=0. if pre_spawn else claim["reserved_wall"],
            cpu=0. if pre_spawn else claim["reserved_cpu"], spawned=not pre_spawn, artifacts=())
