"""Read-only lifecycle evidence over the owning prepared Fourier verifier.

Importing this module is dependency-light. Actual verification/reporting lazily
loads the installed owning modules, never run/evaluate/graph/minimizer entry
points. Registry uncertainty remains authoritative even when a complete backend
document survived an uncertain worker/publication outcome.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import time

from .prepared_lifecycle import (
    LifecycleError, _HEX32, _identifier, admission_document, digest, json_bytes,
    regular_bytes, require, implementation_sources, runtime_identity,
)
from . import prepared_lifecycle_readonly_worker as read_worker

VERIFY_SCHEMA = "prepared_lifecycle_verification/1.0.0"
REPORT_SCHEMA = "prepared_lifecycle_report/1.0.0"
COMPARE_SCHEMA = "prepared_lifecycle_comparison/1.0.0"
UNITS = {"coordinates": "angstrom", "energy": "kcal/mol", "force": "kcal/mol/angstrom"}
PUBLIC_UNITS = {"coordinates": "angstrom", "energy": "kcal/mol", "raw_force": "kcal/mol/angstrom"}
FORCE_SEMANTICS = "unconstrained_raw_negative_coordinate_gradient_no_restraint_or_augmentation"
OWNING_SCOPE = "bound_bytes_structural_receipts_no_force_reexecution"
INFLIGHT = {"running", "cancel_requested"}
ROLES = {
    "numerical_invocation_result": "result.json",
    "retained_refinement_report": "report.json",
    "execution_artifact_manifest": "manifest.json",
}
REPORT_SOURCES = ("betelgeuze_product/prepared_refinement_cli.py",
                  "betelgeuze_product/docking_cli.py", "betelgeuze_engine_v2/standalone_cli.py")


def _report_source_identity():
    root = Path(__file__).resolve().parent.parent
    return {name: hashlib.sha256(regular_bytes(root / name, root)).hexdigest() for name in REPORT_SOURCES}


def _snapshot(service, execution_id):
    _identifier(execution_id, _HEX32)
    with closing(service._connect()) as connection:
        connection.execute("BEGIN")
        row = service._row(connection, execution_id)
        invocations = [dict(r) for r in connection.execute(
            "SELECT * FROM prepared_invocations WHERE execution_id=? ORDER BY generation", (execution_id,))]
        artifacts = [dict(r) for r in connection.execute(
            "SELECT * FROM prepared_artifacts WHERE execution_id=? ORDER BY artifact_id", (execution_id,))]
        plan = service._bound_plan(connection, row, json.loads(row["admission_json"]), json.loads(row["policy_json"]))
    value = {"row": row, "invocations": invocations, "artifacts": artifacts, "plan": plan}
    return value, digest(value)


def _stable(service, execution_id, checksum):
    require(_snapshot(service, execution_id)[1] == checksum,
            "CONCURRENT_STATE_CHANGE", "Execution changed during read-only verification", 409)


def _artifacts(service, snapshot):
    row = snapshot["row"]
    root = service.root / "jobs" / row["execution_id"]
    limit = json.loads(row["policy_json"])["output_bytes"]
    documents, descriptors, total_bytes = {}, [], 0
    require(len(snapshot["artifacts"]) <= 1024, "READ_VERIFICATION_FAILED", "Artifact count exceeds bounds", 409)
    for item in snapshot["artifacts"]:
        require(type(item["bytes"]) is int and 0 <= item["bytes"] <= limit-total_bytes,
                "READ_VERIFICATION_FAILED", "Cumulative artifact bytes exceed the frozen output budget", 409)
        data = regular_bytes(root / item["relative_path"], root, maximum=limit-total_bytes)
        total_bytes += len(data)
        require(len(data) == item["bytes"] and hashlib.sha256(data).hexdigest() == item["checksum"],
                "ARTIFACT_PUBLICATION_UNKNOWN", "Retained artifact differs from its registered bytes", 409)
        descriptors.append(service._artifact_metadata(item))
        if item["role"] in ROLES:
            parts = Path(item["relative_path"]).parts
            require(len(parts) == 3 and parts[0] == "attempts" and parts[1].isdigit()
                    and len(parts[1]) == 6 and parts[2] == ROLES[item["role"]],
                    "ARTIFACT_PUBLICATION_UNKNOWN", "Artifact generation binding is invalid", 409)
            key = (int(parts[1]), item["role"])
            require(key not in documents, "ARTIFACT_PUBLICATION_UNKNOWN", "Duplicate generation artifact", 409)
            document = json_bytes(data)
            require(isinstance(document, dict), "ARTIFACT_PUBLICATION_UNKNOWN", "Retained artifact must be an object", 409)
            if item["role"] == "numerical_invocation_result":
                require(document.get("schema_version") == "prepared_lifecycle_numerical_result/1.0.0"
                        and document.get("execution_id") == row["execution_id"]
                        and document.get("generation") == key[0]
                        and type(document.get("total_work_known")) is bool,
                        "ARTIFACT_PUBLICATION_UNKNOWN", "Numerical artifact identity differs", 409)
                _count(document.get("known_force_calls"))
            elif item["role"] == "retained_refinement_report":
                require(document.get("schema_version") == "prepared_refinement_report/1.0.0"
                        and document.get("report_sha256") == digest({k: v for k, v in document.items() if k != "report_sha256"})
                        and document.get("report_sources") == _report_source_identity()
                        and document.get("report_source_sha256") == digest(document.get("report_sources")),
                        "ARTIFACT_PUBLICATION_UNKNOWN", "Retained report digest differs", 409)
            documents[key] = (document, item["checksum"])
    for (generation, role), (manifest, _) in documents.items():
        if role != "execution_artifact_manifest":
            continue
        require(manifest.get("schema_version") == "prepared_lifecycle_artifact_manifest/1.0.0"
                and manifest.get("execution_id") == row["execution_id"]
                and manifest.get("generation") == generation
                and type(manifest.get("total_work_known")) is bool,
                "ARTIFACT_PUBLICATION_UNKNOWN", "Artifact manifest identity differs", 409)
        admission = json.loads(row["admission_json"])
        require(manifest.get("protocol_sha256") == admission["manifest"]["protocol_sha256"]
                and manifest.get("runtime_identity") == admission["runtime_identity"]
                and manifest.get("implementation_sources") == admission["lifecycle_sources"],
                "ARTIFACT_PUBLICATION_UNKNOWN", "Generation source identity differs", 409)
        contents = manifest.get("artifact_content_sha256")
        expected_contents = {ROLES[r]: value[1] for (g, r), value in documents.items()
                             if g == generation and r != "execution_artifact_manifest"}
        require(contents == expected_contents, "ARTIFACT_PUBLICATION_UNKNOWN", "Manifest artifact census differs", 409)
        for basename, checksum in contents.items():
            matching = [value[1] for (g, r), value in documents.items()
                        if g == generation and ROLES[r] == basename]
            require(matching == [checksum], "ARTIFACT_PUBLICATION_UNKNOWN", "Manifest artifact census differs", 409)
        result = documents.get((generation, "numerical_invocation_result"))
        report = documents.get((generation, "retained_refinement_report"))
        if result and report:
            work = report[0].get("work", {})
            force = _count(work.get("known_force_evaluation_calls"))
            failed = _count(work.get("known_failed_force_evaluation_calls"))
            restarts = _count(work.get("restart_verification_calls"))
            require(result[0].get("report_sha256") == digest(report[0])
                    and result[0].get("backend_binding") == report[0].get("binding")
                    and force == result[0].get("known_force_calls")
                    and failed <= force and restarts <= force
                    and work.get("report_force_evaluation_calls") == 0
                    and type(work.get("total_work_known")) is bool
                    and work["total_work_known"] == result[0].get("total_work_known")
                    and work.get("total_force_evaluation_calls") == (force if work["total_work_known"] else None)
                    and report[0].get("execution_status") == result[0].get("numerical_state")
                    and result[0].get("known_force_calls") == manifest.get("known_force_calls")
                    and (manifest.get("total_work_known") is False or
                         result[0].get("numerical_state") == manifest.get("numerical_state")
                         and result[0].get("total_work_known") is True),
                    "ARTIFACT_PUBLICATION_UNKNOWN", "Result and report binding differs", 409)
    return documents, descriptors


def _lineage(snapshot, documents):
    row, invocations = snapshot["row"], snapshot["invocations"]
    require(type(row["generation"]) is int and row["generation"] >= 0
            and [r["generation"] for r in invocations] == list(range(1, row["generation"]+1))
            and all(1 <= generation <= row["generation"] for generation, _ in documents),
            "ARTIFACT_PUBLICATION_UNKNOWN", "Owner generation sequence is incomplete", 409)
    known = bool(row["force_known"])
    previous = 0
    spawned_known = 0
    for invocation in invocations:
        status, generation = invocation["status"], invocation["generation"]
        require(status in {"complete", "paused", "failed", "cancelled", "interrupted_unknown", "unqualified"},
                "ARTIFACT_PUBLICATION_UNKNOWN", "An unresolved owner reservation remains", 409)
        manifest = documents.get((generation, "execution_artifact_manifest"))
        if manifest:
            value = manifest[0]
            force = value.get("known_force_calls")
            if force is None:
                require(value.get("total_work_known") is False
                        and (generation, "numerical_invocation_result") not in documents,
                        "ARTIFACT_PUBLICATION_UNKNOWN", "Unknown generation has an inconsistent force prefix", 409)
                force = previous
            else:
                force = _count(force)
            require(force >= previous and value.get("status") == status,
                    "ARTIFACT_PUBLICATION_UNKNOWN", "Generation force prefix or state regressed", 409)
            previous = force
        if known and status != "unqualified":
            require(manifest is not None and manifest[0].get("total_work_known") is True
                    and all((generation, role) in documents for role in ROLES),
                    "ARTIFACT_PUBLICATION_UNKNOWN", "Known owner generation lacks complete evidence", 409)
            receipt = json.loads(invocation["receipt_json"] or "{}")
            process = receipt.get("process", {})
            require(receipt.get("process_terminal_confirmed") is True
                    and process.get("returncode") == 0 and not process.get("containment_error")
                    and process.get("containment_evidence", {}).get("namespace_exit_verified") is True,
                    "ARTIFACT_PUBLICATION_UNKNOWN", "Prior owner process evidence is unresolved", 409)
            spawned_known += 1
    require(0 <= row["invocation_count"] <= len(invocations)
            and (not known or row["invocation_count"] == spawned_known and row["force_reserved"] == 0),
            "ARTIFACT_PUBLICATION_UNKNOWN", "Cumulative invocation accounting differs", 409)


def _tree(directory, maximum):
    """Bind numerical receipt bytes before/after the owning read-only verifier."""
    require(not directory.is_symlink(), "READ_VERIFICATION_FAILED", "Numerical directory is aliased", 409)
    if not directory.exists():
        return None
    result, total_bytes = {}, 0
    for root, dirs, files in os.walk(directory, followlinks=False):
        parent = Path(root)
        require(all(not (parent / name).is_symlink() for name in dirs),
                "READ_VERIFICATION_FAILED", "Numerical receipt directory is aliased", 409)
        for name in files:
            path = parent / name
            require(len(result) < 1024, "READ_VERIFICATION_FAILED", "Numerical receipt count exceeds bounds", 409)
            remaining = maximum-total_bytes
            require(remaining >= 0, "READ_VERIFICATION_FAILED", "Numerical receipt bytes exceed the frozen output budget", 409)
            try:
                data = regular_bytes(path, directory, maximum=min(64*1024*1024, remaining))
            except LifecycleError as exc:
                raise LifecycleError("READ_VERIFICATION_FAILED", "Numerical receipt exceeds read bounds or is not a regular unaliased file", 409) from exc
            total_bytes += len(data)
            result[str(path.relative_to(directory))] = hashlib.sha256(data).hexdigest()
    return result


def _count(value):
    require(type(value) is int and value >= 0, "READ_VERIFICATION_FAILED", "Invalid retained force census", 409)
    return value


def _kill_owned_group(process):
    # No poll/wait has reaped this private Popen child yet. Its PID still pins
    # the session/process-group identity; never signal a group after reaping.
    if process.returncode is None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired as exc:
        raise LifecycleError("READ_VERIFICATION_UNAVAILABLE", "Read worker cleanup did not confirm exit", 503) from exc


def _capture_worker(request, environment):
    """Bound both directions without preexec_fn or unbounded communicate()."""
    raw = (json.dumps(request, sort_keys=True, separators=(",", ":"), allow_nan=False)+"\n").encode()
    require(len(raw) <= read_worker.MAX_REQUEST_BYTES, "READ_VERIFICATION_FAILED", "Read request exceeds bounds", 409)
    command = [sys.executable, "-I", "-B", "-m", "betelgeuze_product.prepared_lifecycle_readonly_worker"]
    started, process, reaped = time.monotonic(), None, False
    output = {"stdout": bytearray(), "stderr": bytearray()}
    selector = selectors.DefaultSelector()
    directory = None
    try:
        directory = tempfile.mkdtemp(prefix="betelgeuze-readonly-")
        process = subprocess.Popen(command, cwd=directory, env=environment,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   start_new_session=True, close_fds=True)
        for stream, kind, event in ((process.stdin, "stdin", selectors.EVENT_WRITE),
                                     (process.stdout, "stdout", selectors.EVENT_READ),
                                     (process.stderr, "stderr", selectors.EVENT_READ)):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, event, kind)
        offset = 0
        deadline = started + read_worker.WALL_SECONDS
        while selector.get_map():
            remaining = deadline-time.monotonic()
            require(remaining > 0, "READ_VERIFICATION_UNAVAILABLE", "Read worker exceeded its wall limit", 503)
            for key, _ in selector.select(min(.05, remaining)):
                stream, kind = key.fileobj, key.data
                if kind == "stdin":
                    try:
                        offset += os.write(stream.fileno(), raw[offset:offset+65536])
                    except BrokenPipeError:
                        offset = len(raw)
                    except BlockingIOError:
                        continue
                    if offset == len(raw):
                        selector.unregister(stream)
                        stream.close()
                else:
                    limit = read_worker.MAX_RESPONSE_BYTES if kind == "stdout" else read_worker.MAX_STDERR_BYTES
                    try:
                        chunk = os.read(stream.fileno(), min(65536, limit-len(output[kind])+1))
                    except BlockingIOError:
                        continue
                    require(len(output[kind])+len(chunk) <= limit,
                            "READ_VERIFICATION_UNAVAILABLE", "Read worker capture exceeds bounds", 503)
                    if chunk:
                        output[kind].extend(chunk)
                    else:
                        selector.unregister(stream)
                        stream.close()
        try:
            returncode = process.wait(timeout=max(.001, deadline-time.monotonic()))
            reaped = True
        except subprocess.TimeoutExpired as exc:
            raise LifecycleError("READ_VERIFICATION_UNAVAILABLE", "Read worker exceeded its wall limit", 503) from exc
        require(returncode == 0, "READ_VERIFICATION_FAILED", "Isolated owning read did not complete successfully", 409)
        return bytes(output["stdout"]), hashlib.sha256(raw).hexdigest(), time.monotonic()-started
    except BaseException:
        if process is not None and not reaped:
            _kill_owned_group(process)
        raise
    finally:
        selector.close()
        if process is not None:
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None and not stream.closed:
                    stream.close()
        # Never remove a working directory until our direct child was reaped.
        # An unconfirmed cleanup leaves this new private directory for diagnosis.
        if directory is not None and (process is None or process.returncode is not None):
            shutil.rmtree(directory)


def _owning_adapter(protocol, directory, *, with_report):
    """Fixed installed isolated child; parent Torch state is never touched."""
    sources, runtime = implementation_sources(), runtime_identity()
    root = Path(__file__).resolve().parent.parent
    available = sorted(os.sched_getaffinity(0))
    require(bool(available), "READ_VERIFICATION_UNAVAILABLE", "Read worker CPU placement is unavailable", 503)
    cpu = available[0]
    request = {"schema_version": read_worker.REQUEST_SCHEMA, "nonce": secrets.token_hex(32),
               "protocol": protocol, "protocol_sha256": digest(protocol), "directory": str(directory),
               "implementation_sources": sources, "runtime_identity": runtime, "with_report": with_report}
    environment = {"PATH": str(Path(sys.executable).parent)+":/usr/bin:/bin",
                   "PYTHONDONTWRITEBYTECODE": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
                   "OPENBLAS_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1", "LANG": "C.UTF-8",
                   "BETELGEUZE_READONLY_INSTALLED_ROOT": str(root),
                   "BETELGEUZE_READONLY_WORKER_SHA256": sources["betelgeuze_product/prepared_lifecycle_readonly_worker.py"],
                   "BETELGEUZE_READONLY_CORE_SHA256": sources["betelgeuze_product/prepared_lifecycle.py"],
                   "BETELGEUZE_READONLY_CPU": str(cpu)}
    try:
        raw, request_sha, elapsed = _capture_worker(request, environment)
        response = json.loads(raw, object_pairs_hook=read_worker._pairs, parse_constant=read_worker._reject_constant)
        require(type(response) is dict and set(response) == {
            "schema_version", "nonce", "request_sha256", "implementation_sources", "runtime_identity", "result", "read_only_child_cost"}
                and response["schema_version"] == read_worker.RESPONSE_SCHEMA
                and response["nonce"] == request["nonce"] and response["request_sha256"] == request_sha
                and response["implementation_sources"] == sources and response["runtime_identity"] == runtime
                and implementation_sources() == sources and runtime_identity() == runtime,
                "READ_VERIFICATION_FAILED", "Read worker source or request binding differs", 409)
        result, cost = response["result"], response["read_only_child_cost"]
        require(type(result) is dict and set(result) == {
            "binding", "status", "known_force_calls", "total_work_known", "report", "evaluator", "read_only_environment"}
                and type(result["total_work_known"]) is bool and result["read_only_environment"]["torch_threads"] == 1
                and result["read_only_environment"]["torch_interop_threads"] == 1,
                "READ_VERIFICATION_FAILED", "Read worker result contract differs", 409)
        _count(result["known_force_calls"])
        applied = cost["applied_resources"]
        require({k: v for k, v in applied.items() if not k.startswith("self_wall_")} == {
            "RLIMIT_CPU": [read_worker.CPU_SECONDS]*2, "RLIMIT_AS": [read_worker.ADDRESS_SPACE_BYTES]*2,
            "RLIMIT_FSIZE": [read_worker.FILE_BYTES]*2, "cpu_affinity": [cpu]}
                and applied["self_wall_limit_seconds"] == read_worker.WALL_SECONDS
                and type(applied["self_wall_timer_remaining_seconds_at_admission"]) in (int, float)
                and 0 < applied["self_wall_timer_remaining_seconds_at_admission"] <= read_worker.WALL_SECONDS
                and cost["new_force_calls"] == 0 and cost["execution_budget_charged"] is False
                and all(type(cost[key]) in (int, float) and math.isfinite(cost[key]) and cost[key] >= 0
                        for key in ("CPU_seconds", "worker_module_wall_seconds", "peak_RSS_bytes")),
                "READ_VERIFICATION_FAILED", "Read worker resource receipt differs", 409)
        result["read_only_child_cost"] = {**cost, "parent_observed_wall_seconds": elapsed,
            "wall_limit_seconds": read_worker.WALL_SECONDS, "stdout_limit_bytes": read_worker.MAX_RESPONSE_BYTES,
            "stderr_limit_bytes": read_worker.MAX_STDERR_BYTES, "request_limit_bytes": read_worker.MAX_REQUEST_BYTES,
            "cleanup_scope": "waited fixed trusted child; owned session/process-group kill on failure; no namespace or escaped-descendant containment claim"}
        return result
    except LifecycleError:
        raise
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise LifecycleError("READ_VERIFICATION_FAILED", "Read worker evidence is invalid or unavailable", 409) from exc


def _model(admission, evaluator):
    require(set(evaluator) == {"evaluator_id", "parameter_fingerprint_sha256", "cross_parameters_sha256"},
            "READ_VERIFICATION_FAILED", "Owning evaluator identity is incomplete", 409)
    value = {"model_id": admission["model_id"], "evaluator": evaluator,
             "physical_input_sha256": {name: admission["protocol"][name]["sha256"]
                                       for name in ("ligand", "receptor", "parameters", "cross")},
             "source_evidence_sha256": admission["protocol"]["source_evidence"]["sha256"],
             "implementation_sha256": digest(admission["lifecycle_sources"]),
             "evidence_kind": admission["protocol"]["evidence_kind"],
             "force_semantics": FORCE_SEMANTICS, "units": dict(PUBLIC_UNITS)}
    return {**value, "comparability_sha256": digest(value),
            "comparability_scope": "exact prepared physical input bytes and declared model; conservative matched-input scope"}


def _terminal(snapshot, documents, owning):
    row = snapshot["row"]
    known = bool(row["force_known"]) and owning["total_work_known"] is True
    if not known:
        return False
    generation = row["generation"]
    values = {role: documents.get((generation, role)) for role in ROLES}
    require(all(values.values()), "ARTIFACT_PUBLICATION_UNKNOWN", "Terminal generation artifacts are incomplete", 409)
    result = values["numerical_invocation_result"][0]
    report = values["retained_refinement_report"][0]
    manifest = values["execution_artifact_manifest"][0]
    invocations = [item for item in snapshot["invocations"] if item["generation"] == generation]
    require(len(invocations) == 1, "ARTIFACT_PUBLICATION_UNKNOWN", "Terminal owner generation is missing", 409)
    receipt = json.loads(invocations[0]["receipt_json"] or "{}")
    process = receipt.get("process", {})
    require(receipt.get("process_terminal_confirmed") is True
            and process.get("returncode") == 0 and not process.get("containment_error")
            and process.get("containment_evidence", {}).get("namespace_exit_verified") is True,
            "ARTIFACT_PUBLICATION_UNKNOWN", "Terminal process evidence does not admit known work", 409)
    require(result.get("schema_version") == "prepared_lifecycle_numerical_result/1.0.0"
            and result.get("execution_id") == row["execution_id"]
            and result.get("generation") == generation
            and result.get("backend_binding") == owning["binding"]
            and result.get("numerical_state") == row["numerical_state"] == owning["status"]
            and result.get("total_work_known") is True
            and manifest.get("total_work_known") is True
            and manifest.get("process_terminal_confirmed") is True
            and result.get("known_force_calls") == manifest.get("known_force_calls")
            == row["known_force"] == owning["known_force_calls"],
            "ARTIFACT_PUBLICATION_UNKNOWN", "Terminal numerical ledger bindings differ", 409)
    admission = json.loads(row["admission_json"])
    require(manifest.get("protocol_sha256") == admission["manifest"]["protocol_sha256"]
            and manifest.get("runtime_identity") == admission["runtime_identity"]
            and manifest.get("implementation_sources") == admission["lifecycle_sources"],
            "ARTIFACT_PUBLICATION_UNKNOWN", "Terminal source identity differs", 409)
    require(report.get("binding") == owning["binding"], "ARTIFACT_PUBLICATION_UNKNOWN", "Retained report backend differs", 409)
    return True


def _base(snapshot, checksum):
    row = snapshot["row"]
    policy = json.loads(row["policy_json"])
    prefix = _count(row["known_force"])
    require(prefix <= policy["force_call_ceiling"], "READ_VERIFICATION_FAILED", "Registry force budget is inconsistent", 409)
    return {"schema_version": VERIFY_SCHEMA, "execution_id": row["execution_id"],
            "generation": row["generation"], "execution_status": row["status"],
            "numerical_state": row["numerical_state"], "registry_snapshot_sha256": checksum,
            "plan": snapshot["plan"],
            "fully_verified": False, "total_work_known": False, "known_force_calls": prefix,
            "total_force_calls": None, "report": None, "model": None,
            "research_only": True, "qualified": False, "chemical_validity": None,
            "pose_accuracy": None, "pose_selection_admitted": False,
            "units": dict(PUBLIC_UNITS), "force_semantics": FORCE_SEMANTICS,
            "budget": {"limits": policy, "wall_seconds_spent": row["wall_spent"],
                       "cpu_seconds_charged": row["cpu_spent"], "numerical_invocations": row["invocation_count"]}}


def _read_cost(wall, cpu, child=None, environment=None):
    return {"wall_seconds": time.monotonic()-wall,
            "CPU_seconds": child.get("CPU_seconds") if child else None,
            "CPU_scope": "isolated read worker own CPU only; parent request CPU is not separately attributable",
            "parent_process_CPU_delta_seconds": time.process_time()-cpu,
            "parent_process_CPU_delta_scope": "whole service process; may include concurrent requests; not this request's CPU cost",
            "child": child, "read_only_environment": environment, "new_force_calls": 0,
            "scope": "read-only registry/artifact/owning verification; separate from numerical execution budgets"}


def _inspect(service, execution_id, *, with_report):
    wall, cpu = time.monotonic(), time.process_time()
    snapshot, checksum = _snapshot(service, execution_id)
    row = snapshot["row"]
    result = _base(snapshot, checksum)
    if row["status"] in INFLIGHT:
        _stable(service, execution_id, checksum)
        return {**result, "verification_status": "inflight_unresolved", "verification_scope": "registry_snapshot_only",
                "read_only_cost": _read_cost(wall, cpu)}
    try:
        saved = json.loads(row["admission_json"])
        current = admission_document(service.input_root, saved["admission_id"], tenant_id=service.tenant_id)
        require(saved == current, "SOURCE_OR_MODEL_MISMATCH", "Registered source or runtime identity changed", 409)
        documents, descriptors = _artifacts(service, snapshot)
        _lineage(snapshot, documents)
        directory = service.root / "jobs" / execution_id / "numerical"
        maximum = json.loads(row["policy_json"])["output_bytes"]
        before = _tree(directory, maximum)
        if before is None:
            require(row["status"] not in {"complete", "paused"}, "ARTIFACT_PUBLICATION_UNKNOWN", "Numerical receipts are missing", 409)
            _stable(service, execution_id, checksum)
            return {**result, "verification_status": "not_ready", "verification_scope": "registered_bytes_and_artifacts",
                    "artifacts": descriptors,
                    "read_only_cost": _read_cost(wall, cpu)}
        try:
            owning = _owning_adapter(saved["protocol"], directory, with_report=with_report)
        except LifecycleError:
            raise
        except ImportError as exc:
            raise LifecycleError("READ_VERIFICATION_UNAVAILABLE", "Owning read-only runtime is unavailable", 503) from exc
        except Exception as exc:
            if str(exc) == "one CPU thread required":
                raise LifecycleError("READ_VERIFICATION_UNAVAILABLE", "Configured one-thread verifier contract is not met", 409) from exc
            raise LifecycleError("READ_VERIFICATION_FAILED", "Owning read-only receipt validation failed", 409) from exc
        finally:
            require(_tree(directory, maximum) == before, "CONCURRENT_STATE_CHANGE", "Numerical receipts changed during verification", 409)
        prefix = _count(owning["known_force_calls"])
        require(type(owning["total_work_known"]) is bool and row["known_force"] <= prefix
                <= json.loads(row["policy_json"])["force_call_ceiling"],
                "READ_VERIFICATION_FAILED", "Owning and registry force prefixes disagree", 409)
        known = _terminal(snapshot, documents, owning)
        result.update(verification_status="verified_known" if known else "verified_with_unknown_work",
                      verification_scope=OWNING_SCOPE, fully_verified=known, total_work_known=known,
                      known_force_calls=prefix, total_force_calls=prefix if known else None,
                      owning_numerical_state=owning["status"], backend_binding=owning["binding"],
                      model=_model(saved, owning["evaluator"]), artifacts=descriptors,
                      registry_known_force_calls=row["known_force"], result_provisional=not known)
        if with_report:
            document = owning["report"]
            require(document.get("schema_version") == "prepared_refinement_report/1.0.0"
                    and document.get("force_semantics") == FORCE_SEMANTICS and document.get("units") == UNITS
                    and document.get("chemical_validity") is None and document.get("pose_accuracy") is None
                    and document.get("pose_selection_admitted") is False
                    and document.get("report_sha256") == digest({k: v for k, v in document.items() if k != "report_sha256"}),
                    "READ_VERIFICATION_FAILED", "Owning report contract differs", 409)
            published = documents.get((row["generation"], "retained_refinement_report"))
            require(published is None or published[0] == document,
                    "READ_VERIFICATION_FAILED", "Current retained report differs from owning verification", 409)
            result["report"] = {
                "backend_schema_version": document["schema_version"], "backend_report_sha256": digest(document),
                "candidate_id": None, "backend_candidate_sha256": digest(document["candidate_id"]),
                "states": document["states"],
                "comparison": document["comparison"], "refinement_status": document["refinement_status"],
                "last_observed_numerical_convergence": document["numerical_convergence"],
                "numerical_convergence": document["numerical_convergence"] if known else None,
                "work": {**document["work"], "total_work_known": known,
                         "total_force_evaluation_calls": prefix if known else None},
                "boundary": document["boundary"], "state_metrics_provisional": not known,
            }
            _no_private_paths(result["report"])
        require(admission_document(service.input_root, saved["admission_id"], tenant_id=service.tenant_id) == saved,
                "CONCURRENT_STATE_CHANGE", "Registered inputs changed during verification", 409)
        _artifacts(service, snapshot)  # Recheck exact retained bytes after owning reads.
        _stable(service, execution_id, checksum)
        result["read_only_cost"] = _read_cost(wall, cpu, owning.get("read_only_child_cost"), owning.get("read_only_environment"))
        return result
    except LifecycleError:
        _stable(service, execution_id, checksum)
        raise
    except (OSError, KeyError, TypeError, ValueError) as exc:
        _stable(service, execution_id, checksum)
        raise LifecycleError("READ_VERIFICATION_FAILED", "Retained lifecycle evidence is invalid or unavailable", 409) from exc


def verify_execution(service, execution_id):
    return _inspect(service, execution_id, with_report=False)


def report_execution(service, execution_id):
    result = _inspect(service, execution_id, with_report=True)
    return {**result, "schema_version": REPORT_SCHEMA,
            "report_status": "available" if result["fully_verified"] and result["report"] is not None else
            "provisional_unknown_work" if result["report"] is not None else "unavailable"}


def _no_private_paths(value):
    if isinstance(value, dict):
        for item in value.values():
            _no_private_paths(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _no_private_paths(item)
    elif isinstance(value, str):
        require(not value.startswith(("/", "file://")),
                "READ_VERIFICATION_FAILED", "Owning report contains a private filesystem reference", 409)


def compare_executions(service, execution_ids):
    require(type(execution_ids) is list and 2 <= len(execution_ids) <= 32,
            "INVALID_ARGUMENT", "Between two and 32 execution references are required")
    for identity in execution_ids:
        _identifier(identity, _HEX32)
    rows, cached = [], {}
    for position, identity in enumerate(execution_ids):
        if identity not in cached:
            try:
                cached[identity] = report_execution(service, identity)
            except LifecycleError as exc:
                cached[identity] = {"execution_id": identity, "report": None,
                                    "error": {"code": exc.code, "retry_allowed": False},
                                    "total_work_known": False, "total_force_calls": None}
        rows.append({"request_position": position, "execution_id": identity,
                     "repeated_execution_reference": identity in execution_ids[:position], "result": cached[identity]})
    for identity, value in cached.items():
        if "registry_snapshot_sha256" in value:
            _stable(service, identity, value["registry_snapshot_sha256"])
    pairs = []
    for i, left in enumerate(rows):
        for right in rows[i+1:]:
            a, b = left["result"], right["result"]
            reasons = []
            if not a.get("report") or not b.get("report"):
                reasons.append("retained_report_unavailable")
            if not a.get("fully_verified") or not b.get("fully_verified"):
                reasons.append("unknown_or_unverified_work")
            if not a.get("model") or not b.get("model") or a["model"]["comparability_sha256"] != b["model"]["comparability_sha256"]:
                reasons.append("exact_model_or_physical_input_identity_mismatch")
            differences = None
            if not reasons:
                x = a["report"]["states"]["last_observed_refinement"]
                y = b["report"]["states"]["last_observed_refinement"]
                if x is None or y is None:
                    reasons.append("last_observed_state_unavailable")
                else:
                    differences = {"right_minus_left_energy_kcal_per_mol": y["energy_kcal_per_mol"]-x["energy_kcal_per_mol"],
                                   "right_minus_left_raw_force_kcal_per_mol_angstrom": y["max_force_kcal_per_mol_angstrom"]-x["max_force_kcal_per_mol_angstrom"]}
                    require(all(type(v) in (int, float) and math.isfinite(v) for v in differences.values()),
                            "READ_VERIFICATION_FAILED", "Comparison arithmetic is nonfinite", 409)
            pairs.append({"left_request_position": left["request_position"], "right_request_position": right["request_position"],
                          "comparable": not reasons, "incompatibility_reasons": reasons, "differences": differences})
    for identity, value in cached.items():
        if "registry_snapshot_sha256" in value:
            _stable(service, identity, value["registry_snapshot_sha256"])
    return {"schema_version": COMPARE_SCHEMA, "requested_execution_count": len(execution_ids),
            "unique_execution_count": len(cached), "rows": rows, "pairs": pairs,
            "status": "available" if all(p["comparable"] for p in pairs) else "partial_or_incompatible",
            "comparison_scope": "verified retained states of exactly the same declared prepared physical inputs/model",
            "winner": None, "automatic_ranking_performed": False, "cross_Hamiltonian_energy_comparison_admitted": False,
            "new_force_calls": 0, "research_only": True, "qualified": False, "chemical_validity": None}
