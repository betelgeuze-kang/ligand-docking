"""Bounded CPU-dispatch evidence collection around an untouched frozen worker.

This standalone launcher lives outside the execution checkout. A completed
diagnostic is not a passed historical-science gate or a performance claim.
CPU capability probes are separate processes, explicitly not worker hooks.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import threading
import time

SCHEMA = "betelgeuze.cpu_dispatch_diagnostic/1.0.0"
EXECUTION_COMMIT = "8f5fc53ab68b7e6d9801c6a5830e94dbdd914bb4"
EXECUTION_TREE = "1cdf7b179a046f25dc0d0690692efa54d0d632b9"
BUNDLE_SHA256 = "35276e0afe5101ca165439af012c6eeaed70a605950446310426b000743d298e"
ISOLATION_SHA256 = "a21561ada518cd035e99fb7ee19b8b878c135fee0ac884517a9b5a4001c5ff4e"
WORKER_WALL_SECONDS = 600
TOTAL_WALL_SECONDS = 2100
PROBE_WALL_SECONDS = 90
RSS_BYTES = 6 * 1024 ** 3
LOG_BYTES = 8 * 1024 ** 2
CASES = ("6YSP_PAL", "6T88_MWQ")
STAGES = ("proposal_generated", "post_v6", "post_v7_optimization", "refinement_selected")
AVX2_FLAGS = {"avx2", "fma"}
AVX512_FLAGS = AVX2_FLAGS | {"avx512f", "avx512dq", "avx512bw", "avx512vl"}
STRICT_FAILURES = {
    "exact mismatch: fresh pipeline historical scientific row",
    "fresh pipeline Top5 output bytes differ from original",
}
NUMERICAL_ENVIRONMENT_KEYS = (
    "ATEN_CPU_CAPABILITY", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS", "OMP_DYNAMIC",
    "MKL_DYNAMIC", "MKL_CBWR", "MKL_DEBUG_CPU_TYPE", "OPENBLAS_CORETYPE",
    "NPY_DISABLE_CPU_FEATURES", "ONEDNN_MAX_CPU_ISA", "DNNL_MAX_CPU_ISA",
    "KMP_DETERMINISTIC_REDUCTION", "CUDA_VISIBLE_DEVICES", "HIP_VISIBLE_DEVICES",
    "ROCR_VISIBLE_DEVICES", "PYTHONHASHSEED", "PYTHONNOUSERSITE", "PYTHONDONTWRITEBYTECODE",
    "LANG", "LC_ALL", "LD_LIBRARY_PATH", "LD_PRELOAD",
)


class DiagnosticError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise DiagnosticError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def digest_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def descriptor(path):
    path = Path(path)
    return {"path": str(path), "size_bytes": path.stat().st_size, "sha256": digest_file(path)}


def atomic_json(path, value):
    path = Path(path)
    require(not path.is_symlink() and not path.parent.is_symlink(), "evidence symlink")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".pending", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(canonical(value) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def numerical_environment(environment):
    """Never serialize the full inherited environment (it can contain secrets)."""
    return {key: environment[key] for key in NUMERICAL_ENVIRONMENT_KEYS if key in environment}


def condition_environment(parent, execution_root, capability):
    require(capability in (None, "default", "avx2", "avx512"), "unsupported CPU capability request")
    result = dict(parent)
    result.pop("ATEN_CPU_CAPABILITY", None)
    if capability is not None:
        result["ATEN_CPU_CAPABILITY"] = capability
    result["PYTHONPATH"] = str(execution_root)
    # Child code executes this actual frozen revision, distinct from the
    # diagnostic workflow revision retained in the parent/request receipts.
    result["GITHUB_SHA"] = EXECUTION_COMMIT
    result["PYTHONDONTWRITEBYTECODE"] = "1"
    result["PYTHONNOUSERSITE"] = "1"
    return result


def supported_conditions(native_capability, flags):
    flags = set(flags)
    avx2 = native_capability in {"AVX2", "AVX512"} and AVX2_FLAGS <= flags
    avx512 = native_capability == "AVX512" and AVX512_FLAGS <= flags
    return [
        {"name": "native", "request": None, "eligible": True, "reason": None},
        {"name": "default", "request": "default", "eligible": True, "reason": None},
        {"name": "avx2", "request": "avx2", "eligible": avx2,
         "reason": None if avx2 else "native capability and CPU flags do not jointly admit AVX2"},
        {"name": "avx512", "request": "avx512", "eligible": avx512,
         "reason": None if avx512 else "native capability and CPU flags do not jointly admit AVX512"},
        {"name": "native_repeat", "request": None, "eligible": True, "reason": None},
    ]


def classify_worker_exit(process, result):
    if (not isinstance(process, dict) or not isinstance(result, dict)
            or process.get("termination") != "exited" or process.get("cleanup_complete") is not True
            or "error" not in process or process["error"] is not None
            or type(process.get("returncode")) is not int):
        return "incomplete"
    if process["returncode"] == 0 and result.get("status") == "success":
        return "success"
    if (process["returncode"] == 1 and result.get("status") == "failed"
            and result.get("error_type") == "ReplayProtocolError"
            and result.get("error") in STRICT_FAILURES):
        return "strict_gate_failure"
    return "incomplete"


def supervise_and_finalize(supervision_call, finalization_call):
    """Never mask fatal cleanup uncertainty with an observation-write failure."""
    try:
        process = supervision_call()
    except BaseException as primary:
        try:
            finalization_call()
        except BaseException as secondary:
            raise primary from secondary
        raise
    return process, finalization_call()


def git_identity(root):
    def git(*arguments):
        return subprocess.check_output(["git", *arguments], cwd=root, timeout=20).decode().strip()
    require(not git("status", "--porcelain", "--untracked-files=all"), "checkout is not clean: " + str(root))
    return {"commit": git("rev-parse", "HEAD"), "tree": git("rev-parse", "HEAD^{tree}")}


def frozen_controller(execution_root):
    require(digest_file(execution_root / "tools/redocking_isolation.py") == ISOLATION_SHA256,
            "frozen supervisor source changed")
    sys.path.insert(0, str(execution_root))
    controller = importlib.import_module("tools.run_posebusters_integration")
    require(Path(controller.__file__).resolve().parent.parent == execution_root, "wrong controller imported")
    require(Path(controller.isolation.__file__).resolve() == execution_root / "tools/redocking_isolation.py",
            "wrong supervisor imported")
    return controller


def cpu_metadata():
    text = Path("/proc/cpuinfo").read_text()
    affinity = sorted(os.sched_getaffinity(0))
    cpus = []
    for section in text.strip().split("\n\n"):
        values = dict(line.split(":", 1) for line in section.splitlines() if ":" in line)
        values = {key.strip(): value.strip() for key, value in values.items()}
        if int(values.get("processor", "-1")) in affinity:
            cpus.append({key: values.get(key) for key in (
                "processor", "vendor_id", "cpu family", "model", "model name", "stepping", "microcode", "flags")})
    require(len(cpus) == len(affinity) and cpus, "CPU metadata does not cover affinity")
    flags = sorted(set.intersection(*(set(row["flags"].split()) for row in cpus)))
    return {"hostname": platform.node(), "uname": list(platform.uname()), "machine": platform.machine(),
            "affinity": affinity, "cpus": cpus, "common_flags": flags,
            "cpuinfo_sha256": hashlib.sha256(text.encode()).hexdigest(), "cpuinfo": text,
            "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip()}


def proc_identity(pid):
    raw = Path("/proc", str(pid), "stat").read_text()
    fields = raw[raw.rfind(")") + 2:].split()
    return {"pid": pid, "parent_pid": int(fields[1]), "start_ticks": int(fields[19])}


def mapped_files(pid):
    raw = Path("/proc", str(pid), "maps").read_text()
    entries = {}
    for line in raw.splitlines():
        parts = line.split(maxsplit=5)
        if len(parts) != 6 or not parts[5].startswith("/"):
            continue
        path = re.sub(r"\\([0-7]{3})", lambda match: chr(int(match[1], 8)), parts[5])
        if ".so" not in Path(path).name:
            continue
        require(not path.endswith(" (deleted)"), "deleted shared library mapping")
        entries[path] = {"path": path, "mapped_device": parts[3], "mapped_inode": int(parts[4])}
    return raw, entries


def hash_mapped_files(entries):
    output = []
    for path, entry in sorted(entries.items()):
        before = Path(path).stat()
        require(before.st_ino == entry["mapped_inode"], "mapped library inode changed: " + path)
        require(f"{os.major(before.st_dev):02x}:{os.minor(before.st_dev):02x}" == entry["mapped_device"],
                "mapped library device changed: " + path)
        sha = digest_file(path)
        after = Path(path).stat()
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "library changed while hashing")
        output.append({**entry, "sha256": sha, "size_bytes": before.st_size, "mtime_ns": before.st_mtime_ns})
    return output


class WorkerMonitor:
    """Read-only procfs sampling; no probe subprocess overlaps the worker."""
    def __init__(self, command, environment, execution_root):
        self.command, self.environment, self.execution_root = command, environment, execution_root
        self.proc_owner = int(os.readlink("/proc/self"))
        owner_ids = next(line for line in Path(f"/proc/{self.proc_owner}/status").read_text().splitlines()
                         if line.startswith("NSpid:")).split()[1:]
        require(owner_ids and int(owner_ids[-1]) == os.getpid(), "cannot bind monitor PID namespace")
        self.namespace_depth = len(owner_ids) - 1
        self.stop_event = threading.Event()
        self.record = {"scope": "externally sampled actual worker; no injected code",
                       "launcher_workflow_sha": os.environ.get("GITHUB_SHA"),
                       "worker_cpu_capability_directly_observed": False, "samples": 0, "errors": []}
        self.entries = {}
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start()

    def _run(self):
        while not self.stop_event.is_set():
            try:
                if "identity" in self.record:
                    pids = [self.record["identity"]["pid"]]
                else:
                    # /proc/PID/task/TID/children is absent on some kernels.
                    # Use the same parent/start namespace model as the frozen
                    # supervisor without depending on that optional interface.
                    pids = []
                    for path in Path("/proc").glob("[0-9]*/stat"):
                        try:
                            candidate = proc_identity(int(path.parent.name))
                            if candidate["parent_pid"] == self.proc_owner:
                                pids.append(candidate["pid"])
                        except (FileNotFoundError, ProcessLookupError, PermissionError):
                            continue
                for pid in pids:
                    root = Path("/proc", str(pid))
                    identity = proc_identity(pid)
                    argv = [os.fsdecode(value) for value in (root / "cmdline").read_bytes().split(b"\0") if value]
                    if identity["parent_pid"] != self.proc_owner or argv != self.command:
                        continue
                    status = (root / "status").read_text()
                    ids = [int(value) for value in next(line for line in status.splitlines()
                           if line.startswith("NSpid:")).split()[1:]]
                    require(len(ids) > self.namespace_depth, "worker namespace differs from controller")
                    binding = {**identity, "local_pid": ids[self.namespace_depth],
                               "local_parent_pid": os.getpid(), "namespace_pids": ids}
                    require(self.record.get("identity", binding) == binding, "worker PID/start identity changed")
                    actual_env = {}
                    execution_sha = None
                    for item in (root / "environ").read_bytes().split(b"\0"):
                        key, separator, value = item.partition(b"=")
                        name = os.fsdecode(key)
                        if separator and name in NUMERICAL_ENVIRONMENT_KEYS:
                            actual_env[name] = os.fsdecode(value)
                        elif separator and name == "GITHUB_SHA":
                            execution_sha = os.fsdecode(value)
                    require(actual_env == numerical_environment(self.environment), "worker numerical environment differs")
                    require(execution_sha == EXECUTION_COMMIT, "worker requested execution SHA differs")
                    cwd = os.readlink(root / "cwd")
                    require(cwd == str(self.execution_root), "worker cwd differs")
                    maps, entries = mapped_files(pid)
                    require(proc_identity(pid) == identity, "worker identity changed while observing")
                    stamp = {"monotonic_ns": time.monotonic_ns(), "maps_sha256": hashlib.sha256(maps.encode()).hexdigest(),
                             "maps": maps}
                    if "first" not in self.record:
                        self.record.update(identity=binding, argv=argv, cwd=cwd, numerical_environment=actual_env,
                                           execution_github_sha=execution_sha,
                                           affinity=sorted(os.sched_getaffinity(binding["local_pid"])), first=stamp,
                                           nspid=next((line for line in status.splitlines()
                                                      if line.startswith("NSpid:")), None))
                    self.record["last"] = stamp
                    self.record["samples"] += 1
                    self.entries.update(entries)
            except (FileNotFoundError, ProcessLookupError):
                pass  # ordinary spawn/exit sampling race
            except Exception as exc:
                if len(self.record["errors"]) < 10:
                    self.record["errors"].append({"type": type(exc).__name__, "message": str(exc)})
            self.stop_event.wait(0.25)

    def finish(self):
        self.stop_event.set()
        self.thread.join(timeout=5)
        require(not self.thread.is_alive(), "worker monitor did not stop")
        self.record["mapped_shared_libraries"] = hash_mapped_files(self.entries)
        return self.record


def probe(args):
    """Fresh sibling process; imports metadata only and performs no docking."""
    execution = args.execution_root.resolve()
    controller = frozen_controller(execution)
    launcher_source = git_identity(Path(__file__).resolve().parent.parent)
    require(launcher_source["commit"] == args.launcher_workflow_sha, "probe launcher provenance differs")
    bundle, _ = controller.load_bundle(args.input_root, args.bundle_sha256)
    require(controller.source_identity() == bundle["source"], "probe execution source differs")
    environment = controller.capture_environment(args.runtime_root)
    controller.validate_environment(environment, bundle=bundle)
    atomic_json(args.output_root / "environment.json", environment)
    import torch
    require(str(torch.__version__) == "2.6.0+cpu", "probe Torch build differs")
    maps, entries = mapped_files(int(os.readlink("/proc/self")))
    report = {"schema_id": SCHEMA, "status": "success", "process_role": "same_environment_sibling_probe",
              "worker_cpu_capability_directly_observed": False, "pid": os.getpid(), "parent_pid": os.getppid(),
              "source": bundle["source"], "launcher_file": descriptor(Path(__file__).resolve()),
              "launcher_source": launcher_source, "launcher_workflow_sha": args.launcher_workflow_sha,
              "execution_github_sha": os.environ.get("GITHUB_SHA"),
              "python": descriptor(Path(sys.executable)), "python_version": platform.python_version(),
              "torch_version": str(torch.__version__), "torch_cpu_capability": torch.backends.cpu.get_cpu_capability(),
              "torch_config": torch.__config__.show(), "torch_parallel_info": torch.__config__.parallel_info(),
              "torch_intraop_threads": torch.get_num_threads(), "torch_interop_threads": torch.get_num_interop_threads(),
              "numerical_environment": numerical_environment(os.environ), "cpu": cpu_metadata(),
              "mapped_shared_libraries": hash_mapped_files(entries), "maps": maps,
              "environment": descriptor(args.output_root / "environment.json")}
    atomic_json(args.output_root / "probe.json", report)
    print(json.dumps({key: report[key] for key in ("status", "pid", "torch_cpu_capability", "process_role")}))
    return 0


def validate_process(controller, directory, record, wall_seconds, command):
    controller.verify_signed(record, "control_sha256", "diagnostic process receipt")
    require(record["command"] == command, "supervised argv changed")
    require(record["wall_limit_seconds"] == wall_seconds and record["rss_limit_bytes"] == RSS_BYTES
            and record["rss_sampling_seconds"] == .25, "diagnostic supervision limits changed")
    require(record["cleanup_complete"] is True and record["error"] is None, "supervisor/cleanup failed")
    for name in ("wall_seconds", "child_cpu_seconds"):
        value = record.get(name)
        require(type(value) in (int, float) and math.isfinite(value) and value >= 0,
                "invalid measured process duration: " + name)
    peak = record.get("sampled_peak_process_tree_rss_bytes")
    require(type(peak) is int and 0 <= peak <= RSS_BYTES, "observed sampled RSS exceeded diagnostic limit")
    if record["termination"] == "exited":
        # Includes supervisor finalization: boundary finishes are conservatively
        # retained as incomplete instead of overclaiming the time bound.
        require(0 < record["wall_seconds"] <= wall_seconds, "exited process wall interval exceeded diagnostic limit")
    for name in ("stdout", "stderr"):
        stream = record["streams"][name]
        require(stream["path"] == name + ".log" and stream["eof_observed"] is True, "stream not finalized")
        payload = directory / stream["path"]
        require(payload.stat().st_size == stream["bytes_retained"] and
                digest_file(payload) == stream["retained_sha256"], "stream bytes differ")
        require(stream["bytes_retained"] == min(stream["bytes_seen"], LOG_BYTES)
                and stream["bytes_discarded"] == stream["bytes_seen"] - stream["bytes_retained"],
                "stream resource accounting differs")
        require(stream["truncated"] is (stream["bytes_discarded"] > 0), "stream truncation flag differs")


def run_probe(args, controller, directory, environment):
    command = [str(args.python), str(Path(__file__).resolve()), "probe", "--execution-root", str(args.execution_root),
               "--input-root", str(args.input_root), "--bundle-sha256", args.bundle_sha256,
               "--runtime-root", str(args.runtime_root), "--output-root", str(directory),
               "--launcher-workflow-sha", args.launcher_workflow_sha]
    record = controller.isolation.supervise(command, directory,
        controller.isolation.Limits(PROBE_WALL_SECONDS, rss_bytes=RSS_BYTES, log_bytes=LOG_BYTES),
        cwd=args.execution_root, env=environment)
    validate_process(controller, directory, record, PROBE_WALL_SECONDS, command)
    require(record["termination"] == "exited" and record["returncode"] == 0, "capability probe failed")
    value = json.loads((directory / "probe.json").read_bytes())
    require(value["status"] == "success" and value["numerical_environment"] == numerical_environment(environment),
            "probe status/environment differs")
    return value


def capability_matches(request, capability, native):
    if request is None:
        return capability == native
    if request == "default":
        return capability in {"DEFAULT", "NO AVX"}
    return capability == request.upper()


def validate_worker_evidence(controller, directory, result, process, monitor, selected, bundle, command):
    outcome = classify_worker_exit(process, result)
    require(outcome != "incomplete", "worker did not finish success or an admitted strict scientific gate failure")
    controller.verify_signed(result, "result_sha256", "raw worker result")
    require(result["actual_argv"] == command and result["source"] == bundle["source"]
            and result["case_id"] == selected["case"]["case_id"] and result["stage"] == "pipeline"
            and result["mode"] == "prepared_subset" and result["bundle_sha256"] == BUNDLE_SHA256,
            "worker scientific execution identity differs")
    require(not monitor["errors"] and monitor["samples"] >= 2 and
            monitor["identity"]["local_pid"] == result["pid"] and result["parent_pid"] == os.getpid(),
            "actual worker process observation missing or mismatched")
    require(any("libtorch_cpu" in row["path"] for row in monitor["mapped_shared_libraries"]),
            "worker's actual Torch library mapping was not observed")
    for item in result["files"].values():
        controller.read_document(directory, item) if item["relative_path"].endswith(".json") else controller.bound_file(directory, item)
    controller.validate_environment(controller.read_document(directory, result["files"]["environment_before"]), bundle=bundle)
    identity = controller.journal_identity(source=bundle["source"], bundle_sha256=BUNDLE_SHA256,
        case_id=selected["case"]["case_id"], stage="pipeline", mode="prepared_subset",
        evaluator_identity=bundle["evaluator_identities"]["prepared_subset"],
        seed=selected["case"]["frozen_case_seed"], actual_argv=command)
    events, journal = controller.verify_journal(directory / "journal", expected_identity=identity)
    row = json.loads((directory / "scientific-row.json").read_bytes())
    lineage = controller.lineage.validate_observation_events(events, case_id=selected["case"]["case_id"], canonical_row=row)
    report = controller.read_document(directory, result["files"]["full_report"])
    require(report["record_count"] == 64 and len(report["fullReport"]["rows"]) == 64
            and len(report["fullReport"]["columns"]) == 126, "raw fullReport denominator differs")
    counts = {stage: sum(event.get("stage") == stage for event in events) for stage in STAGES}
    require(all(value == 64 for value in counts.values()), "four-stage candidate denominator differs")
    coordinates = {stage: sorted(
        [{"proposal_index": event["details"]["proposal_index"],
          "coordinates_binary64": event["details"]["coordinates_binary64"]}
         for event in events if event.get("stage") == stage], key=lambda value: value["proposal_index"])
        for stage in STAGES}
    stage_hashes = {stage: controller.digest(values) for stage, values in coordinates.items()}
    historical_selected = sorted([
        {"proposal_index": candidate["proposal_index"], "coordinates_binary64":
         controller.read_json(controller.relative_file(selected["root"], candidate["coordinates_relative_path"]))}
        for candidate in selected["case"]["candidates_sorted"]], key=lambda value: value["proposal_index"])
    # Preserve the complete frozen report gate, including typed cells, input
    # binding and immutability. An arm whose report itself differs is retained
    # as incomplete, never promoted by swallowing an unrelated validator error.
    controller.validate_report(report, selected=selected, bundle=bundle, mode="prepared_subset")
    report_validation = {"status": "passed"}
    if outcome == "success":
        controller.validate_worker(directory, result, selected=selected, bundle=bundle,
            bundle_sha256=BUNDLE_SHA256, stage="pipeline", mode="prepared_subset", actual_argv=command)
    else:
        require(events[-1].get("stage") == "worker_failure" and
                events[-1].get("details", {}).get("message") == result["error"], "strict failure is not durable")
    return {"scientific_gate": outcome, "historical_gate_passed": outcome == "success",
            "journal": journal, "stage_counts": counts, "lineage": lineage,
            "stage_coordinate_sha256s": stage_hashes,
            "historical_selected_coordinates_equal": controller.digest(coordinates["refinement_selected"]) == controller.digest(historical_selected),
            "historical_report_validation": report_validation,
            "scientific_row": descriptor(directory / "scientific-row.json"),
            "full_report": descriptor(directory / "full-report.json"),
            "top5": descriptor(directory / "poses" / (selected["case"]["case_id"] + ".sdf")),
            "historical_top5_bytes_equal": (directory / "poses" / (selected["case"]["case_id"] + ".sdf")).read_bytes()
                == controller.bound_file(selected["root"], selected["case"]["top5"]),
            "scientific_projection_sha256": controller.digest(controller.scientific_projection(row)),
            "historical_scientific_projection_equal": controller.digest(controller.scientific_projection(row)) == controller.digest(controller.scientific_projection(selected["source_row"]))}


def before_after_identity(before, after):
    fields = ("hostname", "uname", "machine", "affinity", "cpus", "common_flags", "boot_id")
    require({key: before["cpu"][key] for key in fields} == {key: after["cpu"][key] for key in fields},
            "CPU host identity changed within condition")
    for key in ("source", "launcher_source", "launcher_workflow_sha", "execution_github_sha",
                "python", "python_version", "torch_version", "torch_cpu_capability", "numerical_environment"):
        require(before[key] == after[key], "probe before/after differs: " + key)
    left = {row["path"]: (row["size_bytes"], row["sha256"]) for row in before["mapped_shared_libraries"]}
    right = {row["path"]: (row["size_bytes"], row["sha256"]) for row in after["mapped_shared_libraries"]}
    require(left == right, "probe shared library identities changed")


def run(args):
    for name in ("launcher_root", "execution_root", "input_root", "runtime_root", "output_root"):
        value = getattr(args, name).absolute()
        require(value == value.resolve(), "noncanonical or symlink root: " + name)
        setattr(args, name, value)
    args.python = args.python.absolute()  # the original venv executable is legitimately a symlink
    require(args.bundle_sha256 == BUNDLE_SHA256, "diagnostic input bundle is not the frozen final bundle")
    require(Path(__file__).resolve() == args.launcher_root / "tools/run_posebusters_cpu_diagnostic.py", "launcher checkout mismatch")
    for name in ("launcher_root", "execution_root", "input_root", "runtime_root"):
        root = getattr(args, name)
        require(not args.output_root.is_relative_to(root) and not root.is_relative_to(args.output_root),
                "output overlaps a protected source/input root")
    require(not args.output_root.exists(), "diagnostic output must be fresh")
    args.output_root.mkdir(parents=True)
    started = time.monotonic()
    report = {"schema_id": SCHEMA, "status": "in_progress", "case_id": args.case_id,
        "diagnostic_success_meaning": "all supported conditions produced complete controlled evidence, irrespective of preserved strict historical gate failure",
        "historical_all_passed": False, "performance_claim": False, "conditions": [],
        "worker_scientific_protocol_wall_seconds": 1800, "diagnostic_supervisor_wall_seconds": WORKER_WALL_SECONDS,
        "total_launcher_wall_budget_seconds": TOTAL_WALL_SECONDS, "rss_bytes": RSS_BYTES, "stream_bytes": LOG_BYTES,
        "capability_scope": "sibling probes before/after; actual worker observed externally through PID/start/argv/env/library maps; no injected worker capability call",
        "dispatch_scope": "ATEN_CPU_CAPABILITY does not control all BLAS/MKL/OpenBLAS/libm implementations; absence of an arm effect does not exclude those factors or establish the historical cause",
        "report_gate_scope": "the complete original fullReport validation remains mandatory; additional report differences are retained as incomplete evidence, never relaxed into an admitted historical-row failure",
        "input_bundle_sha256": BUNDLE_SHA256}
    def checkpoint():
        report["elapsed_seconds"] = time.monotonic() - started
        atomic_json(args.output_root / "diagnostic.json", report)
    checkpoint()
    try:
        report["launcher_source"] = git_identity(args.launcher_root)
        report["launcher_workflow_sha"] = os.environ.get("GITHUB_SHA")
        require(report["launcher_workflow_sha"] == report["launcher_source"]["commit"], "launcher workflow SHA missing or differs")
        args.launcher_workflow_sha = report["launcher_workflow_sha"]
        report["launcher_file"] = descriptor(Path(__file__).resolve())
        report["execution_source"] = git_identity(args.execution_root)
        require(report["execution_source"] == {"commit": EXECUTION_COMMIT, "tree": EXECUTION_TREE}, "execution checkout differs")
        require(args.launcher_root != args.execution_root, "launcher and execution checkout must differ")
        controller = frozen_controller(args.execution_root)
        bundle, manifest = controller.load_bundle(args.input_root, BUNDLE_SHA256)
        require({**report["execution_source"], "protocol_sha256": controller.digest(controller.PROTOCOL)} == bundle["source"],
                "actual execution checkout does not match immutable inputs")
        selected = controller.selected_inputs(args.input_root, bundle, manifest, args.case_id, "pipeline")
        report["execution_protocol_sha256"] = bundle["source"]["protocol_sha256"]
        native_env = condition_environment(os.environ, args.execution_root, None)
        baseline = run_probe(args, controller, args.output_root / "initial-native-probe", native_env)
        native = baseline["torch_cpu_capability"]
        report["native_capability_probe"] = descriptor(args.output_root / "initial-native-probe/probe.json")
        plan = supported_conditions(native, baseline["cpu"]["common_flags"])
        report["condition_plan"] = plan
        checkpoint()
        for condition in plan:
            item = {**condition, "status": "not_started", "historical_gate_passed": False}
            report["conditions"].append(item)
            if not condition["eligible"]:
                item["status"] = "skipped_unsupported_isa"
                checkpoint()
                continue
            if TOTAL_WALL_SECONDS - (time.monotonic() - started) < WORKER_WALL_SECONDS + 2 * PROBE_WALL_SECONDS + 60:
                item["reason"] = "budget_exhausted; insufficient full-arm and finalization allowance"
                checkpoint()
                continue
            directory = args.output_root / condition["name"]
            directory.mkdir()
            environment = condition_environment(os.environ, args.execution_root, condition["request"])
            command = [str(args.python), "-m", "tools.run_posebusters_integration", "worker",
                "--input-root", str(args.input_root), "--bundle-sha256", BUNDLE_SHA256,
                "--runtime-root", str(args.runtime_root), "--stage", "pipeline", "--case-id", args.case_id,
                "--mode", "prepared_subset", "--output-root", str(directory / "worker")]
            request = {"condition": condition, "command": command, "cwd": str(args.execution_root),
                       "numerical_environment": numerical_environment(environment), "source": bundle["source"],
                       "launcher_source": report["launcher_source"], "input_bundle_sha256": BUNDLE_SHA256,
                       "launcher_workflow_sha": report["launcher_workflow_sha"], "execution_github_sha": EXECUTION_COMMIT,
                       "supervisor_wall_seconds": WORKER_WALL_SECONDS, "rss_bytes": RSS_BYTES, "stream_bytes": LOG_BYTES}
            atomic_json(directory / "request.json", request)
            item["status"] = "running"
            checkpoint()
            try:
                before = baseline if condition["name"] == "native" else run_probe(args, controller, directory / "probe-before", environment)
                host_fields = ("hostname", "uname", "machine", "affinity", "cpus", "common_flags", "boot_id")
                require({key: before["cpu"][key] for key in host_fields} ==
                        {key: baseline["cpu"][key] for key in host_fields}, "host CPU changed between conditions")
                require(capability_matches(condition["request"], before["torch_cpu_capability"], native), "requested dispatch did not take effect in probe")
                monitor = WorkerMonitor(command, environment, args.execution_root)
                monitor.start()
                def supervise_worker():
                    return controller.isolation.supervise(command, directory / "worker",
                        controller.isolation.Limits(WORKER_WALL_SECONDS, rss_bytes=RSS_BYTES, log_bytes=LOG_BYTES),
                        cwd=args.execution_root, env=environment)
                def finalize_observation():
                    observed = monitor.finish()
                    atomic_json(directory / "worker-process-observation.json", observed)
                    return observed
                process, observed = supervise_and_finalize(supervise_worker, finalize_observation)
                validate_process(controller, directory / "worker", process, WORKER_WALL_SECONDS, command)
                after = run_probe(args, controller, directory / "probe-after", environment)
                before_after_identity(before, after)
                result_path = directory / "worker/result.json"
                result = json.loads(result_path.read_bytes()) if result_path.exists() else None
                assessment = validate_worker_evidence(controller, directory / "worker", result, process, observed,
                                                       selected, bundle, command)
                item.update(status="evidence_collected", **assessment,
                            raw_result=descriptor(result_path), process=descriptor(directory / "worker/process-execution.json"),
                            observation=descriptor(directory / "worker-process-observation.json"),
                            capability_before=before["torch_cpu_capability"], capability_after=after["torch_cpu_capability"])
            except controller.isolation.CleanupError:
                raise  # never launch another arm if live descendants may remain
            except Exception as exc:
                item.update(status="incomplete", error_type=type(exc).__name__, error=str(exc))
            checkpoint()
        require(git_identity(args.execution_root) == report["execution_source"], "execution checkout changed")
        require(git_identity(args.launcher_root) == report["launcher_source"] and
                descriptor(Path(__file__).resolve()) == report["launcher_file"], "launcher changed")
        controller.load_bundle(args.input_root, BUNDLE_SHA256)
        actual = [item for item in report["conditions"] if item["eligible"]]
        complete = len(report["conditions"]) == len(plan) and all(item["status"] == "evidence_collected" for item in actual)
        report["historical_all_passed"] = complete and all(item["historical_gate_passed"] for item in actual)
        report["status"] = "evidence_collection_completed" if complete else "incomplete"
        if complete:
            repeated = {item["name"]: item for item in actual}
            report["native_repeat_scientific_projection_equal"] = repeated["native"]["scientific_projection_sha256"] == repeated["native_repeat"]["scientific_projection_sha256"]
            report["native_repeat_stage_coordinates_equal"] = repeated["native"]["stage_coordinate_sha256s"] == repeated["native_repeat"]["stage_coordinate_sha256s"]
            for item in actual:
                item["stage_coordinates_equal_to_native"] = {
                    stage: item["stage_coordinate_sha256s"][stage] == repeated["native"]["stage_coordinate_sha256s"][stage]
                    for stage in STAGES}
                item["full_report_bytes_equal_to_native"] = item["full_report"]["sha256"] == repeated["native"]["full_report"]["sha256"]
    except Exception as exc:
        report.update(status="incomplete", error_type=type(exc).__name__, error=str(exc))
    finally:
        checkpoint()
    print(json.dumps({key: report[key] for key in ("case_id", "status", "historical_all_passed", "performance_claim")}))
    return 0 if report["status"] == "evidence_collection_completed" else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("run", "probe"):
        child = subparsers.add_parser(command)
        child.add_argument("--execution-root", type=Path, required=True)
        child.add_argument("--input-root", type=Path, required=True)
        child.add_argument("--bundle-sha256", required=True)
        child.add_argument("--runtime-root", type=Path, required=True)
        child.add_argument("--output-root", type=Path, required=True)
        if command == "run":
            child.add_argument("--launcher-root", type=Path, required=True)
            child.add_argument("--case-id", choices=CASES, required=True)
            child.add_argument("--python", type=Path, required=True)
        else:
            child.add_argument("--launcher-workflow-sha", required=True)
    args = parser.parse_args(argv)
    try:
        return run(args) if args.command == "run" else probe(args)
    except Exception as exc:
        print(json.dumps({"status": "incomplete", "error_type": type(exc).__name__, "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
