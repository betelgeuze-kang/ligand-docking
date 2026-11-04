"""Qualify a recorded host, then run the unchanged frozen three-mode case CLI.

Eligibility is not a scientific result. Capability probes are sibling processes;
actual frozen workers are observed through procfs without code injection.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
import threading
import time

SCHEMA = "betelgeuze.posebusters_qualified_integration/1.0.0"
PROFILE_SCHEMA = "betelgeuze.posebusters_qualified_profile/1.0.0"
PROFILE_FILE_SHA256 = "14dba14517929759804dc83f30f7ef0f5cb293d8c65cbb52f54c940ddfe0cfc5"
HELPER_SHA256 = "89863acbb82e75ebe60448d7205b2a89aacc5ac1db4112efbdca23f9586c29a5"
EXECUTION_SOURCE = {"commit": "8f5fc53ab68b7e6d9801c6a5830e94dbdd914bb4",
    "tree": "1cdf7b179a046f25dc0d0690692efa54d0d632b9",
    "protocol_sha256": "bbb9fee321f435f2e2cdea14229b8e4f38265e754e42588bb33209c057b4e4d1"}
BUNDLE_SHA256 = "35276e0afe5101ca165439af012c6eeaed70a605950446310426b000743d298e"
CASE_ID = "6YSP_PAL"
MODES = ("reference", "prepared_receptor", "prepared_subset")
HOST_SLOTS = (1, 2, 3, 4)
LAUNCHER_WALL_SECONDS, CASE_WALL_SECONDS, WORKER_WALL_SECONDS, PROBE_WALL_SECONDS = 3000, 2400, 1800, 90
RSS_BYTES, LOG_BYTES = 6 * 1024 ** 3, 8 * 1024 ** 2
MAX_EVIDENCE_FILES, MAX_EVIDENCE_BYTES = 2000, 1024 ** 3
SELF_HASH = "result_sha256"
CPU_IDENTITY_KEYS = ("vendor_id", "cpu family", "model", "model name", "stepping", "microcode")
HOST_STABLE_KEYS = ("hostname", "uname", "machine", "affinity", "cpus", "common_flags", "boot_id")
LIMITS = {"launcher_wall_seconds": LAUNCHER_WALL_SECONDS, "case_controller_wall_seconds": CASE_WALL_SECONDS,
    "unchanged_worker_wall_seconds": WORKER_WALL_SECONDS, "probe_wall_seconds": PROBE_WALL_SECONDS,
    "rss_limit_bytes_each_supervisor": RSS_BYTES, "log_limit_bytes_per_stream": LOG_BYTES,
    "rss_sampling_seconds": .25, "original_historical_worker_wall_seconds": 900,
    "scope": "observed procfs descendants plus adopted orphans; no cgroup containment"}


class IntegrityError(RuntimeError):
    """Malformed or unauthentic evidence; never host ineligibility."""


class ProfileMismatch(RuntimeError):
    """Authentic observations outside the predeclared host contract."""


def require(condition, message):
    if not condition:
        raise IntegrityError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


def equal(left, right, message):
    require(canonical(left) == canonical(right), message)


def matches(left, right, message):
    if canonical(left) != canonical(right):
        raise ProfileMismatch(message)


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def digest_file(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def read_json(path):
    def object_hook(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate JSON key: " + key)
            result[key] = value
        return result
    def bad_constant(value):
        raise IntegrityError("nonfinite JSON constant: " + value)
    return json.loads(Path(path).read_bytes(), object_pairs_hook=object_hook, parse_constant=bad_constant)


def signed(value):
    require(SELF_HASH not in value, "self hash already present")
    return {**value, SELF_HASH: digest(value)}


def verify_signed(value):
    require(type(value) is dict and SELF_HASH in value, "missing signed result")
    equal(value[SELF_HASH], digest({k: v for k, v in value.items() if k != SELF_HASH}), "result self hash differs")


def atomic_json(path, value):
    path = Path(path)
    require(not path.is_symlink() and not path.parent.is_symlink(), "evidence symlink")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".pending", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(canonical(value) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def safe_path(root, relative):
    require(type(relative) is str and relative and "\\" not in relative, "invalid evidence path")
    parsed = PurePosixPath(relative)
    require(not parsed.is_absolute() and parsed.as_posix() == relative and ".." not in parsed.parts,
            "noncanonical evidence path")
    path = Path(root) / relative
    require(path.resolve().is_relative_to(Path(root).resolve()) and path == path.resolve(),
            "evidence path traverses a symlink or escapes root")
    return path


def descriptor(root, path):
    path = Path(path)
    relative = path.relative_to(root).as_posix()
    safe_path(root, relative)
    return {"relative_path": relative, "size_bytes": path.stat().st_size, "sha256": digest_file(path)}


def bound_file(root, item):
    require(type(item) is dict and set(item) == {"relative_path", "size_bytes", "sha256"}, "invalid file descriptor")
    require(type(item["size_bytes"]) is int and item["size_bytes"] >= 0, "invalid descriptor byte count")
    path = safe_path(root, item["relative_path"])
    equal(descriptor(root, path), item, "file bytes differ: " + item["relative_path"])
    return path


def inventory(root):
    files = sorted(path for path in Path(root).rglob("*") if path.is_file() or path.is_symlink())
    files = [path for path in files if path != Path(root) / "qualified-result.json"]
    require(len(files) <= MAX_EVIDENCE_FILES, "evidence file bound exceeded")
    result = [descriptor(root, path) for path in files]
    require(sum(row["size_bytes"] for row in result) <= MAX_EVIDENCE_BYTES, "evidence byte bound exceeded")
    return result


def load_helpers(launcher_root):
    path = Path(launcher_root) / "tools/run_posebusters_cpu_diagnostic.py"
    equal(digest_file(path), HELPER_SHA256, "frozen CPU helper source changed")
    spec = importlib.util.spec_from_file_location("_posebusters_qualified_frozen_cpu_helpers", path)
    require(spec is not None and spec.loader is not None, "CPU helper cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_profile(profile, helper):
    equal(profile["schema_id"], PROFILE_SCHEMA, "profile schema differs")
    equal(profile["profile_sha256"], digest({k: v for k, v in profile.items() if k != "profile_sha256"}),
          "profile self hash differs")
    equal(profile["execution_source"], EXECUTION_SOURCE, "profile execution source differs")
    equal(profile["input_bundle_sha256"], BUNDLE_SHA256, "profile input differs")
    equal([profile["case_id"], profile["stage"], profile["required_modes"]],
          [CASE_ID, "pipeline", list(MODES)], "profile experiment scope differs")
    equal(profile["provenance"]["launcher_python_sha256"], HELPER_SHA256, "profile helper differs")
    env = profile["numerical_environment"]
    equal(env["allowlisted_keys"], list(helper.NUMERICAL_ENVIRONMENT_KEYS), "environment allowlist differs")
    equal(env["absent_keys"], sorted(set(env["allowlisted_keys"]) - set(env["observed"])),
          "environment absent-key contract differs")
    require(set(env["observed"]) <= set(env["allowlisted_keys"])
            and all(type(value) is str for value in env["observed"].values()), "invalid environment profile")
    equal([profile["cpu"]["native_capability"], profile["cpu"]["requested_aten_cpu_capability"],
           profile["cpu"]["effective_capability"], env["observed"].get("ATEN_CPU_CAPABILITY")],
          ["AVX512", "avx2", "AVX2", "avx2"], "capability profile differs")
    require(profile["cpu"]["per_cpu_flags_equal_common"] is True, "per-CPU flag contract missing")
    equal(profile["libraries"]["path_policy"], "absolute_posix_exact", "library path policy differs")
    for kind, count in (("probe", 75), ("worker", 199)):
        section = profile["libraries"][kind]
        entries = section["entries"]
        equal(section["count"], count, "library count contract differs")
        require(len(entries) == count, "library inventory count differs")
        equal(section["canonical_sha256"], digest(entries), "library inventory hash differs")
        equal([row["path"] for row in entries], sorted({row["path"] for row in entries}),
              "library paths duplicate or unordered")
        for row in entries:
            require(set(row) == {"path", "size_bytes", "sha256"}
                    and type(row["size_bytes"]) is int and row["size_bytes"] > 0
                    and re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) is not None, "invalid library descriptor")
            require(row["path"].startswith("/") and str(PurePosixPath(row["path"])) == row["path"]
                    and ".." not in PurePosixPath(row["path"]).parts, "noncanonical library path")
    worker = profile["libraries"]["worker"]
    required, optional = worker["required_mapped_paths"], worker["optional_mapped_paths"]
    require(len(required) == 21 and len(optional) == 178 and not set(required) & set(optional),
            "core/optional mapping split differs")
    equal(sorted(required + optional), [row["path"] for row in worker["entries"]], "mapping coverage differs")
    equal(worker["transient_mapped_paths"], ["/etc/ld.so.cache"], "transient cache contract differs")
    equal(sorted(path for group in worker["core_groups"].values() for path in group), sorted(required),
          "core mapping groups differ")


def load_profile(path, expected_sha256, helper):
    equal(expected_sha256, PROFILE_FILE_SHA256, "requested profile is not the frozen profile")
    equal(digest_file(path), expected_sha256, "profile file bytes differ")
    profile = read_json(path)
    validate_profile(profile, helper)
    return profile


def validate_cpu(observed, profile):
    target = profile["cpu"]
    require(type(observed) is dict and type(observed.get("cpus")) is list
            and type(observed.get("affinity")) is list and len(observed["uname"]) == 6, "malformed CPU observation")
    require(len(observed["affinity"]) == len(set(observed["affinity"]))
            and all(type(value) is int and value >= 0 for value in observed["affinity"]), "invalid affinity observation")
    matches(len(observed["affinity"]), target["affinity_count"], "CPU affinity count differs")
    matches(len(observed["cpus"]), target["affinity_count"], "CPU metadata count differs")
    matches(observed["common_flags"], target["common_flags"], "common CPU flags differ")
    require(sorted(int(row["processor"]) for row in observed["cpus"]) == sorted(observed["affinity"]),
            "CPU metadata does not cover observed affinity")
    for row in observed["cpus"]:
        matches({key: row[key] for key in CPU_IDENTITY_KEYS}, target["identity"], "CPU model/metadata differs")
        matches(sorted(set(row["flags"].split())), target["common_flags"], "per-CPU flags differ")
    keys = ("system", "node", "release", "version", "machine", "processor")
    actual_platform = {key: value for key, value in zip(keys, observed["uname"]) if key != "node"}
    matches(actual_platform, profile["platform"], "platform descriptor differs")


def library_projection(rows):
    require(type(rows) is list, "library observation is not a list")
    projected = []
    for row in rows:
        require(type(row) is dict and all(key in row for key in ("path", "size_bytes", "sha256")),
                "library observation missing identity")
        require(type(row["size_bytes"]) is int and row["size_bytes"] > 0, "invalid library byte count")
        projected.append({key: row[key] for key in ("path", "size_bytes", "sha256")})
    require(len({row["path"] for row in projected}) == len(projected), "duplicate observed library path")
    return sorted(projected, key=lambda row: row["path"])


def validate_libraries(rows, profile, *, kind):
    section = profile["libraries"][kind]
    actual = library_projection(rows)
    if kind == "probe":
        matches(actual, section["entries"], "probe mapped library identities differ")
        return {"observed_count": len(actual), "unobserved_optional_paths": []}
    expected = {row["path"]: row for row in section["entries"]}
    paths = {row["path"] for row in actual}
    if not set(section["required_mapped_paths"]) <= paths:
        raise ProfileMismatch("required worker core mappings were not observed")
    if not paths <= set(expected):
        raise ProfileMismatch("worker exposes unpinned library mappings")
    for row in actual:
        matches(row, expected[row["path"]], "worker mapped library bytes differ: " + row["path"])
    return {"observed_count": len(actual), "required_count": len(section["required_mapped_paths"]),
            "unobserved_optional_paths": sorted(set(section["optional_mapped_paths"]) - paths),
            "observed_transient_paths": sorted(set(section["transient_mapped_paths"]) & paths)}


def observe_disk_libraries(profile):
    rows = []
    for item in profile["libraries"]["worker"]["entries"]:
        path = Path(item["path"])
        try:
            before = path.stat()
            sha = digest_file(path)
            after = path.stat()
        except FileNotFoundError:
            rows.append({"path": str(path), "missing": True})
            continue
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "library changed during hashing")
        rows.append({"path": str(path), "size_bytes": before.st_size, "sha256": sha,
                     "device": before.st_dev, "inode": before.st_ino, "mtime_ns": before.st_mtime_ns})
    return rows


def validate_disk_libraries(rows, profile):
    require(type(rows) is list and len(rows) == 199, "disk observation denominator differs")
    equal([row["path"] for row in rows], [row["path"] for row in profile["libraries"]["worker"]["entries"]],
          "disk observation paths differ")
    if any(row.get("missing") is True for row in rows):
        raise ProfileMismatch("a pinned on-disk library is absent")
    matches(library_projection(rows), profile["libraries"]["worker"]["entries"], "on-disk library bytes differ")


def expected_environment(profile, *, native=False):
    result = dict(profile["numerical_environment"]["observed"])
    if native:
        result.pop("ATEN_CPU_CAPABILITY")
    return result


def case_command(args, case_root):
    return [str(args.python), "-m", "tools.run_posebusters_integration", "run-case",
            "--input-root", str(args.input_root), "--bundle-sha256", BUNDLE_SHA256,
            "--runtime-root", str(args.runtime_root), "--output-root", str(case_root),
            "--stage", "pipeline", "--case-id", CASE_ID]


def worker_commands(controller, args, case_root):
    summary = {"case_id": CASE_ID, "stage": "pipeline", "bundle_sha256": BUNDLE_SHA256,
               "execution_context": {"python_executable": str(args.python), "input_root": str(args.input_root),
                   "runtime_root": str(args.runtime_root), "output_root": str(case_root),
                   "working_directory": str(args.execution_root)}}
    return {mode: controller.worker_command(summary, slot=slot, mode=mode)
            for slot, mode in enumerate(controller.mode_order(CASE_ID, "pipeline"))}


class NestedWorkerMonitor:
    """Observe the case controller and its exact worker argv via external procfs."""
    def __init__(self, helper, controller_command, commands, environment, execution_root):
        self.helper, self.controller_command, self.commands = helper, controller_command, commands
        self.environment, self.execution_root = environment, Path(execution_root)
        self.owner = int(os.readlink("/proc/self"))
        ids = self._namespace_ids(self.owner)
        require(ids and ids[-1] == os.getpid(), "monitor PID namespace cannot be bound")
        self.depth = len(ids) - 1
        self.stop_event = threading.Event()
        self.records, self.entries, self.errors = {}, {}, []
        self.thread = threading.Thread(target=self._run, daemon=True)

    @staticmethod
    def _namespace_ids(pid):
        status = Path(f"/proc/{pid}/status").read_text()
        return [int(value) for value in next(line for line in status.splitlines()
                if line.startswith("NSpid:")).split()[1:]]

    def start(self):
        self.thread.start()

    def _sample(self, role, pid, identity, argv):
        root = Path("/proc", str(pid))
        ids = self._namespace_ids(pid)
        require(len(ids) > self.depth, "observed process PID namespace differs")
        binding = {**identity, "local_pid": ids[self.depth], "namespace_pids": ids}
        actual_env = {}
        for entry in (root / "environ").read_bytes().split(b"\0"):
            key, separator, value = entry.partition(b"=")
            name = os.fsdecode(key)
            if separator and name in (*self.helper.NUMERICAL_ENVIRONMENT_KEYS, "GITHUB_SHA", "PYTHONPATH"):
                actual_env[name] = os.fsdecode(value)
        numeric = self.helper.numerical_environment(actual_env)
        equal(numeric, self.helper.numerical_environment(self.environment), "actual process numerical environment differs")
        equal(actual_env.get("GITHUB_SHA"), EXECUTION_SOURCE["commit"], "actual process execution SHA differs")
        equal(actual_env.get("PYTHONPATH"), str(self.execution_root), "actual process import path differs")
        cwd = os.readlink(root / "cwd")
        equal(cwd, str(self.execution_root), "actual process working directory differs")
        affinity = sorted(os.sched_getaffinity(binding["local_pid"]))
        maps, entries = self.helper.mapped_files(pid)
        equal(self.helper.proc_identity(pid), identity, "PID identity changed while observing")
        stamp = {"monotonic_ns": time.monotonic_ns(), "maps_sha256": hashlib.sha256(maps.encode()).hexdigest(), "maps": maps}
        if role not in self.records:
            binary = self.helper.descriptor(root / "exe")
            binary["resolved_path"] = os.readlink(root / "exe")
            self.records[role] = {"identity": binding, "argv": argv, "cwd": cwd,
                "numerical_environment": numeric, "execution_github_sha": actual_env["GITHUB_SHA"],
                "pythonpath": actual_env["PYTHONPATH"], "affinity": affinity, "python_binary": binary,
                "first": stamp, "samples": 0}
            self.entries[role] = {}
        record = self.records[role]
        equal(record["identity"], binding, "observed PID/start identity changed")
        equal(record["affinity"], affinity, "actual process affinity changed")
        record["last"] = stamp
        record["samples"] += 1
        self.entries[role].update(entries)

    def _run(self):
        while not self.stop_event.is_set():
            try:
                snapshot = []
                for path in Path("/proc").glob("[0-9]*/stat"):
                    try:
                        snapshot.append(self.helper.proc_identity(int(path.parent.name)))
                    except (FileNotFoundError, ProcessLookupError, PermissionError):
                        continue
                # Resolve the parent before admitting any grandchild.
                ordered = sorted(snapshot, key=lambda value: value["parent_pid"] != self.owner)
                for identity in ordered:
                    pid, parent = identity["pid"], identity["parent_pid"]
                    case = self.records.get("case_controller")
                    if parent != self.owner and (case is None or parent != case["identity"]["pid"]):
                        continue
                    try:
                        argv = [os.fsdecode(value) for value in Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0") if value]
                        role = "case_controller" if parent == self.owner and argv == self.controller_command else None
                        if case is not None and parent == case["identity"]["pid"]:
                            role = next((name for name, command in self.commands.items() if command == argv), None)
                        if role is not None:
                            self._sample(role, pid, identity, argv)
                    except (FileNotFoundError, ProcessLookupError):
                        continue
            except (FileNotFoundError, ProcessLookupError):
                pass
            except Exception as exc:
                if len(self.errors) < 10:
                    self.errors.append({"type": type(exc).__name__, "message": str(exc)[:2000]})
            self.stop_event.wait(.25)

    def finish(self):
        self.stop_event.set()
        self.thread.join(timeout=5)
        require(not self.thread.is_alive(), "external process monitor did not stop")
        for role, record in self.records.items():
            try:
                record["mapped_shared_libraries"] = self.helper.hash_mapped_files(self.entries[role])
            except Exception as exc:
                self.errors.append({"type": type(exc).__name__, "message": str(exc)[:2000], "role": role})
        return {"scope": "external procfs sampling; no worker injection", "sampling_seconds": .25,
                "worker_cpu_capability_directly_observed": False, "observer_pid": os.getpid(),
                "observer_procfs_pid": self.owner, "namespace_depth": self.depth,
                "records": self.records, "errors": self.errors}


def validate_observation(observed, *, profile, summary, commands, command, cpu, results):
    require(observed["errors"] == [] and observed["sampling_seconds"] == .25
            and observed["worker_cpu_capability_directly_observed"] is False, "process observation is incomplete")
    equal(sorted(observed["records"]), sorted(["case_controller", *MODES]), "missing or duplicate observed process")
    parent = observed["records"]["case_controller"]
    require(parent["identity"]["parent_pid"] == observed["observer_procfs_pid"]
            and parent["identity"]["local_pid"] == summary["controller_pid"], "case controller PID binding differs")
    coverages, identities = {}, []
    for role, row in observed["records"].items():
        require(type(row["samples"]) is int and row["samples"] >= 2, "insufficient actual process samples")
        equal(row["argv"], command if role == "case_controller" else commands[role], "actual process argv differs")
        equal(row["cwd"], summary["execution_context"]["working_directory"], "observed cwd differs")
        equal(row["pythonpath"], row["cwd"], "observed import path differs")
        equal(row["execution_github_sha"], EXECUTION_SOURCE["commit"], "observed execution SHA differs")
        equal(row["numerical_environment"], expected_environment(profile), "actual numerical environment differs")
        equal(row["affinity"], cpu["affinity"], "actual process affinity differs from qualification")
        equal({key: row["python_binary"][key] for key in ("size_bytes", "sha256")},
              {key: profile["runtime"]["python"][key] for key in ("size_bytes", "sha256")}, "actual Python binary differs")
        for stamp in (row["first"], row["last"]):
            equal(stamp["maps_sha256"], hashlib.sha256(stamp["maps"].encode()).hexdigest(), "raw maps hash differs")
        require(row["first"]["monotonic_ns"] < row["last"]["monotonic_ns"], "process sampling interval is empty")
        if role != "case_controller":
            actual = results[role]
            require(row["identity"]["parent_pid"] == parent["identity"]["pid"]
                    and row["identity"]["local_pid"] == actual["pid"]
                    and actual["parent_pid"] == parent["identity"]["local_pid"], "actual scientific worker PID binding differs")
            coverages[role] = validate_libraries(row["mapped_shared_libraries"], profile, kind="worker")
            identities.append((row["identity"]["pid"], row["identity"]["start_ticks"]))
    require(len(set(identities)) == 3, "scientific workers were not fresh distinct processes")
    return coverages


PATH_ARGUMENTS = ("launcher_root", "execution_root", "python", "profile", "input_root", "runtime_root", "output_root")
VALUE_ARGUMENTS = ("profile_sha256", "bundle_sha256", "launcher_workflow_sha", "host_slot")


def arguments(args):
    return {**{name: str(getattr(args, name)) for name in PATH_ARGUMENTS},
            **{name: getattr(args, name) for name in VALUE_ARGUMENTS}}


def recorded_arguments(value):
    equal(sorted(value), sorted((*PATH_ARGUMENTS, *VALUE_ARGUMENTS)), "argument fields differ")
    for name in PATH_ARGUMENTS:
        path = value[name]
        require(type(path) is str and path.startswith("/") and str(PurePosixPath(path)) == path
                and ".." not in PurePosixPath(path).parts and "\\" not in path, "noncanonical recorded argument")
    require(type(value["host_slot"]) is int and value["host_slot"] in HOST_SLOTS, "host slot differs")
    equal(value["bundle_sha256"], BUNDLE_SHA256, "argument bundle differs")
    equal(value["profile_sha256"], PROFILE_FILE_SHA256, "argument profile differs")
    require(re.fullmatch(r"[0-9a-f]{40}", value["launcher_workflow_sha"]) is not None, "invalid launcher SHA")
    return argparse.Namespace(**{name: Path(value[name]) for name in PATH_ARGUMENTS},
                              **{name: value[name] for name in VALUE_ARGUMENTS})


def qualification_command(args):
    values = arguments(args)
    values["output_root"] = str(args.output_root / "qualification")
    command = [str(args.python), str(args.launcher_root / "tools/run_posebusters_qualified_integration.py"), "_execute"]
    for name, value in values.items():
        command.extend(["--" + name.replace("_", "-"), str(value)])
    return command


def probe_command(args, directory):
    return [str(args.python), str(args.launcher_root / "tools/run_posebusters_cpu_diagnostic.py"), "probe",
        "--execution-root", str(args.execution_root), "--input-root", str(args.input_root),
        "--bundle-sha256", BUNDLE_SHA256, "--runtime-root", str(args.runtime_root),
        "--output-root", str(directory), "--launcher-workflow-sha", args.launcher_workflow_sha]


def verify_source_context(args, helper, controller):
    require(Path(__file__).resolve() == args.launcher_root / "tools/run_posebusters_qualified_integration.py",
            "launcher file does not belong to requested checkout")
    require(args.launcher_root != args.execution_root, "launcher and execution checkout must differ")
    launcher = helper.git_identity(args.launcher_root)
    equal(launcher["commit"], args.launcher_workflow_sha, "launcher Git HEAD differs from original workflow SHA")
    equal(os.environ.get("GITHUB_SHA"), args.launcher_workflow_sha, "parent workflow SHA was replaced")
    execution = helper.git_identity(args.execution_root)
    equal(execution, {key: EXECUTION_SOURCE[key] for key in ("commit", "tree")}, "actual execution Git source differs")
    equal(controller.digest(controller.PROTOCOL), EXECUTION_SOURCE["protocol_sha256"], "execution protocol differs")
    return {"launcher_source": launcher, "execution_source": EXECUTION_SOURCE,
            "launcher_workflow_sha": args.launcher_workflow_sha,
            "launcher_file": helper.descriptor(Path(__file__).resolve()),
            "helper_file": helper.descriptor(args.launcher_root / "tools/run_posebusters_cpu_diagnostic.py")}


def stable_cpu(before, after):
    equal({key: before[key] for key in HOST_STABLE_KEYS}, {key: after[key] for key in HOST_STABLE_KEYS},
          "host CPU identity changed during qualification")


def original_assessment(controller, directory, *, bundle, selected):
    summary = read_json(directory / "case-summary.json")
    controller.verify_signed(summary, "summary_sha256", "original case summary")
    require(summary["status"] == "success" and summary["cleanup_complete"] is True, "original case did not pass")
    assessment = controller.assess_case(directory, summary, selected=selected, bundle=bundle, bundle_sha256=BUNDLE_SHA256)
    equal(assessment, summary["assessment"], "original recorded assessment differs from raw revalidation")
    return summary, assessment


def validate_probe(directory, logical_directory, *, args, helper, controller, profile, bundle, launcher_source, native, observer_pid):
    process = read_json(directory / "process-execution.json")
    helper.validate_process(controller, directory, process, PROBE_WALL_SECONDS, probe_command(args, logical_directory))
    require(process["termination"] == "exited" and process["returncode"] == 0, "capability probe did not complete")
    value = read_json(directory / "probe.json")
    require(value["status"] == "success" and value["process_role"] == "same_environment_sibling_probe"
            and value["worker_cpu_capability_directly_observed"] is False, "invalid capability probe role")
    equal(value["parent_pid"], observer_pid, "probe parent differs")
    equal(value["source"], EXECUTION_SOURCE, "probe execution source differs")
    equal(value["launcher_source"], launcher_source, "probe launcher source differs")
    equal(value["launcher_workflow_sha"], args.launcher_workflow_sha, "probe workflow source differs")
    equal(value["execution_github_sha"], EXECUTION_SOURCE["commit"], "probe execution SHA differs")
    require(value["launcher_file"]["path"] == str(args.launcher_root / "tools/run_posebusters_cpu_diagnostic.py")
            and value["launcher_file"]["sha256"] == HELPER_SHA256, "probe helper source differs")
    environment_path = directory / "environment.json"
    equal(value["environment"], {"path": str(logical_directory / "environment.json"),
          "size_bytes": environment_path.stat().st_size, "sha256": digest_file(environment_path)}, "probe environment bytes differ")
    environment = read_json(environment_path)
    controller.validate_environment(environment, bundle=bundle)
    matches(environment["content_identity_sha256"], profile["runtime"]["environment_content_identity_sha256"],
            "runtime content identity differs")
    validate_cpu(value["cpu"], profile)
    for key in ("python", "python_version", "torch_version", "torch_intraop_threads", "torch_interop_threads"):
        matches(value[key], profile["runtime"][key], "probe runtime differs: " + key)
    matches(value["torch_cpu_capability"], profile["cpu"]["native_capability" if native else "effective_capability"],
            "observed CPU dispatch differs")
    matches(value["numerical_environment"], expected_environment(profile, native=native), "probe numerical environment differs")
    validate_libraries(value["mapped_shared_libraries"], profile, kind="probe")
    return value


def execute(args):
    helper = load_helpers(args.launcher_root)
    controller = helper.frozen_controller(args.execution_root)
    require(not args.output_root.exists(), "qualification output must be fresh")
    args.output_root.mkdir(parents=True)
    started = time.monotonic()
    report = {"schema_id": SCHEMA, "status": "incomplete", "eligible": False,
        "scientific_success": False, "case_started": False, "host_slot": args.host_slot,
        "case_id": CASE_ID, "stage": "pipeline", "required_modes": list(MODES), "limits": LIMITS,
        "arguments": arguments(args), "observer_pid": os.getpid(), "checks": [],
        "profile_file_sha256": PROFILE_FILE_SHA256, "input_bundle_sha256": BUNDLE_SHA256,
        "capability_scope": "sibling probes; actual workers observed externally, no injected capability call",
        "claim_scope": "conditional single-case validation; no unique historical-cause or general speedup claim"}
    def checkpoint():
        report["elapsed_seconds"] = time.monotonic() - started
        atomic_json(args.output_root / "qualification.json", signed(report))
    def check(name, value, validator):
        atomic_json(args.output_root / (name + ".json"), value)
        report["checks"].append(name)
        report["active_check"] = name
        checkpoint()
        validator(value)
        report.pop("active_check", None)
    checkpoint()
    try:
        profile = load_profile(args.profile, args.profile_sha256, helper)
        report.update(verify_source_context(args, helper, controller))
        bundle, manifest = controller.load_bundle(args.input_root, BUNDLE_SHA256)
        equal(bundle["source"], EXECUTION_SOURCE, "bundle execution source differs")
        selected = controller.selected_inputs(args.input_root, bundle, manifest, CASE_ID, "pipeline")
        cpu = helper.cpu_metadata()
        check("cpu-before", cpu, lambda value: validate_cpu(value, profile))
        check("disk-before", observe_disk_libraries(profile), lambda value: validate_disk_libraries(value, profile))
        native_env = helper.condition_environment(os.environ, args.execution_root, None)
        environment = helper.condition_environment(os.environ, args.execution_root, "avx2")
        check("requested-environment", helper.numerical_environment(environment),
              lambda value: matches(value, expected_environment(profile), "requested numerical environment differs"))
        probes = {}
        for name, native, env in (("probe-native", True, native_env), ("probe-before", False, environment)):
            directory = args.output_root / name
            helper.run_probe(args, controller, directory, env)
            report["checks"].append(name)
            report["active_check"] = name
            checkpoint()
            probes[name] = validate_probe(directory, directory, args=args, helper=helper, controller=controller,
                profile=profile, bundle=bundle, launcher_source=report["launcher_source"], native=native,
                observer_pid=os.getpid())
            stable_cpu(cpu, probes[name]["cpu"])
            report.pop("active_check", None)
        report["eligible"], report["case_started"] = True, True
        report.update(run_original_case(args, helper, controller, profile, bundle, selected, cpu,
                                       environment, probes["probe-before"], report, check, checkpoint))
        equal(verify_source_context(args, helper, controller), {key: report[key] for key in (
            "launcher_source", "execution_source", "launcher_workflow_sha", "launcher_file", "helper_file")},
            "source changed during qualification")
        controller.load_bundle(args.input_root, BUNDLE_SHA256)
    except ProfileMismatch as exc:
        report.update(status="incomplete" if report["case_started"] else "ineligible",
                      scientific_success=False, error_type=type(exc).__name__, error=str(exc))
        if not report["case_started"]:
            report["ineligible_check"] = report.get("active_check")
    except Exception as exc:
        report.update(status="incomplete", scientific_success=False, error_type=type(exc).__name__, error=str(exc))
    finally:
        checkpoint()
    print(json.dumps({key: report[key] for key in ("host_slot", "status", "eligible", "scientific_success")}))
    return 0 if report["status"] in ("success", "ineligible") else 1


def run_original_case(args, helper, controller, profile, bundle, selected, cpu, environment, before, report, check, checkpoint):
    case_root = args.output_root / "case"
    command = case_command(args, case_root)
    commands = worker_commands(controller, args, case_root)
    report["case_command"], report["worker_commands"] = command, commands
    checkpoint()
    monitor = NestedWorkerMonitor(helper, command, commands, environment, args.execution_root)
    monitor.start()
    def supervise_case():
        return controller.isolation.supervise(command, args.output_root / "case-controller-process",
            controller.isolation.Limits(CASE_WALL_SECONDS, rss_bytes=RSS_BYTES, log_bytes=LOG_BYTES),
            cwd=args.execution_root, env=environment)
    def finish_monitor():
        value = monitor.finish()
        atomic_json(args.output_root / "actual-process-observation.json", value)
        return value
    process, observed = helper.supervise_and_finalize(supervise_case, finish_monitor)
    helper.validate_process(controller, args.output_root / "case-controller-process", process, CASE_WALL_SECONDS, command)
    require(process["termination"] == "exited" and type(process["returncode"]) is int
            and process["returncode"] in (0, 1), "original case execution was incomplete")
    directory = args.output_root / "probe-after"
    helper.run_probe(args, controller, directory, environment)
    after = validate_probe(directory, directory, args=args, helper=helper, controller=controller,
        profile=profile, bundle=bundle, launcher_source=report["launcher_source"], native=False, observer_pid=os.getpid())
    report["checks"].append("probe-after")
    helper.before_after_identity(before, after)
    check("disk-after", observe_disk_libraries(profile), lambda value: validate_disk_libraries(value, profile))
    summary = read_json(case_root / "case-summary.json")
    controller.verify_signed(summary, "summary_sha256", "original case summary")
    results = {item["mode"]: controller.read_document(case_root, item["result"]) for item in summary["observations"]}
    coverage = validate_observation(observed, profile=profile, summary=summary, commands=commands,
        command=command, cpu=cpu, results=results)
    output = {"mapping_coverage": coverage, "original_case_status": summary["status"]}
    if process["returncode"] == 0:
        _, assessment = original_assessment(controller, case_root, bundle=bundle, selected=selected)
        output.update(status="success", scientific_success=True, assessment=assessment)
    else:
        require(summary["status"] == "failed", "original process and summary disagree")
        output.update(status="failed", scientific_success=False, failure_scope="unchanged original case gate",
                      original_error={key: summary.get(key) for key in ("error_type", "error")})
    return output


def normalize_run_arguments(args):
    for name in PATH_ARGUMENTS:
        value = getattr(args, name).absolute()
        if name != "python":
            require(value == value.resolve(), "noncanonical or symlink path: " + name)
        setattr(args, name, value)
    recorded_arguments(arguments(args))
    for name in ("launcher_root", "execution_root", "input_root", "runtime_root"):
        root = getattr(args, name)
        require(not args.output_root.is_relative_to(root) and not root.is_relative_to(args.output_root),
                "output overlaps a protected source/input root")


def run(args):
    normalize_run_arguments(args)
    require(not args.output_root.exists(), "qualified output must be fresh")
    args.output_root.mkdir(parents=True)
    report = {"schema_id": SCHEMA, "status": "incomplete", "eligible": False, "scientific_success": False,
        "host_slot": args.host_slot, "case_id": CASE_ID, "stage": "pipeline", "required_modes": list(MODES),
        "arguments": arguments(args), "limits": LIMITS, "profile_file_sha256": PROFILE_FILE_SHA256,
        "input_bundle_sha256": BUNDLE_SHA256, "actual_argv": [sys.executable, *sys.argv],
        "job": {key: os.environ.get(key) for key in ("GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_JOB")}}
    try:
        helper = load_helpers(args.launcher_root)
        controller = helper.frozen_controller(args.execution_root)
        load_profile(args.profile, args.profile_sha256, helper)
        report.update(verify_source_context(args, helper, controller))
        (args.output_root / "bound-profile.json").write_bytes(args.profile.read_bytes())
        command = qualification_command(args)
        report["qualification_command"] = command
        atomic_json(args.output_root / "qualified-request.json", signed(report))
        # The orchestrator retains the launcher SHA. Only frozen child probes and
        # the original case use GITHUB_SHA=8f, with real Git/source checks intact.
        environment = dict(os.environ)
        environment.update(PYTHONPATH=str(args.execution_root), PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1")
        process_root = args.output_root / "launcher-process"
        process = controller.isolation.supervise(command, process_root,
            controller.isolation.Limits(LAUNCHER_WALL_SECONDS, rss_bytes=RSS_BYTES, log_bytes=LOG_BYTES),
            cwd=args.execution_root, env=environment)
        helper.validate_process(controller, process_root, process, LAUNCHER_WALL_SECONDS, command)
        require(process["termination"] == "exited" and type(process["returncode"]) is int
                and process["returncode"] in (0, 1), "qualification orchestrator was incomplete")
        qualification = read_json(args.output_root / "qualification/qualification.json")
        verify_signed(qualification)
        require(qualification["status"] in ("success", "ineligible", "failed", "incomplete"), "unknown qualification status")
        equal(process["returncode"], 0 if qualification["status"] in ("success", "ineligible") else 1,
              "qualification process/status disagree")
        report.update({key: qualification[key] for key in ("status", "eligible", "scientific_success")})
        report["qualification"] = descriptor(args.output_root, args.output_root / "qualification/qualification.json")
        equal(verify_source_context(args, helper, controller), {key: report[key] for key in (
            "launcher_source", "execution_source", "launcher_workflow_sha", "launcher_file", "helper_file")},
            "launcher/execution source changed")
    except Exception as exc:
        report.update(status="incomplete", scientific_success=False, error_type=type(exc).__name__, error=str(exc))
    finally:
        report["files"] = inventory(args.output_root)
        atomic_json(args.output_root / "qualified-result.json", signed(report))
    print(json.dumps({key: report[key] for key in ("host_slot", "status", "eligible", "scientific_success")}))
    return 0 if report["status"] in ("success", "ineligible") else 1


def validate_qualification(root, value, *, helper, controller, profile, bundle, selected, launcher_source):
    verify_signed(value)
    args = recorded_arguments(value["arguments"])
    equal(value["schema_id"], SCHEMA, "qualification schema differs")
    equal(value["limits"], LIMITS, "qualification resource contract differs")
    equal(value["execution_source"], EXECUTION_SOURCE, "qualification source differs")
    equal(value["launcher_source"], launcher_source, "qualification launcher differs")
    equal(value["launcher_workflow_sha"], args.launcher_workflow_sha, "qualification workflow SHA differs")
    equal([value["case_id"], value["stage"], value["required_modes"], value["host_slot"]],
          [CASE_ID, "pipeline", list(MODES), args.host_slot], "qualification case/mode/slot differs")
    equal(value["profile_file_sha256"], PROFILE_FILE_SHA256, "qualification profile differs")
    equal(value["input_bundle_sha256"], BUNDLE_SHA256, "qualification bundle differs")
    for name, sha, actual_path in (("launcher_file", digest_file(Path(__file__).resolve()), Path(__file__).resolve()),
                                  ("helper_file", HELPER_SHA256, Path(helper.__file__))):
        row = value[name]
        equal(row, {"path": str(args.launcher_root / "tools" / actual_path.name),
                    "size_bytes": actual_path.stat().st_size, "sha256": sha}, "qualification launcher/helper bytes differ")
    preflight = ["cpu-before", "disk-before", "requested-environment", "probe-native", "probe-before"]
    all_checks = [*preflight, "probe-after", "disk-after"]
    checks = value["checks"]
    require(type(checks) is list and checks and checks == all_checks[:len(checks)], "check order/missing/duplicate differs")
    if value["status"] == "ineligible":
        require(value["eligible"] is False and value["scientific_success"] is False
                and value["case_started"] is False and not (root / "case").exists(), "ineligible host executed a case")
        require(value["error_type"] == "ProfileMismatch" and value["ineligible_check"] == checks[-1]
                and checks[-1] in preflight, "ineligibility reason is not a preflight mismatch")
    else:
        require(value["status"] == "success" and value["eligible"] is True and value["scientific_success"] is True
                and value["case_started"] is True, "qualification did not pass")
        equal(checks, all_checks, "successful host misses a qualification check")
    probes = {}
    cpu = read_json(root / "cpu-before.json")
    mismatch = None
    for name in checks:
        try:
            if name == "cpu-before":
                validate_cpu(cpu, profile)
            elif name in ("disk-before", "disk-after"):
                validate_disk_libraries(read_json(root / (name + ".json")), profile)
            elif name == "requested-environment":
                matches(read_json(root / (name + ".json")), expected_environment(profile), "requested numerical environment differs")
            else:
                probes[name] = validate_probe(root / name, args.output_root / name, args=args, helper=helper,
                    controller=controller, profile=profile, bundle=bundle, launcher_source=launcher_source,
                    native=name == "probe-native", observer_pid=value["observer_pid"])
                stable_cpu(cpu, probes[name]["cpu"])
        except ProfileMismatch as exc:
            require(value["status"] == "ineligible" and name == value["ineligible_check"]
                    and name == checks[-1], "profile changed after admission or before alleged mismatch")
            equal(str(exc), value["error"], "recorded profile mismatch differs")
            mismatch = name
            break
    if value["status"] == "ineligible":
        require(mismatch is not None, "claimed ineligibility was not reproduced")
        return {"status": "ineligible", "eligible": False, "scientific_success": False, "mismatch": mismatch}
    helper.before_after_identity(probes["probe-before"], probes["probe-after"])
    case_root = root / "case"
    command = case_command(args, args.output_root / "case")
    commands = worker_commands(controller, args, args.output_root / "case")
    equal(value["case_command"], command, "recorded case argv differs")
    equal(value["worker_commands"], commands, "recorded worker argv differs")
    process = read_json(root / "case-controller-process/process-execution.json")
    helper.validate_process(controller, root / "case-controller-process", process, CASE_WALL_SECONDS, command)
    require(process["termination"] == "exited" and type(process["returncode"]) is int and process["returncode"] == 0,
            "original case process did not pass")
    summary, assessment = original_assessment(controller, case_root, bundle=bundle, selected=selected)
    equal(value["assessment"], assessment, "qualification assessment differs from original raw revalidation")
    results = {item["mode"]: controller.read_document(case_root, item["result"]) for item in summary["observations"]}
    coverage = validate_observation(read_json(root / "actual-process-observation.json"), profile=profile, summary=summary,
                                   commands=commands, command=command, cpu=cpu, results=results)
    equal(value["mapping_coverage"], coverage, "mapping coverage differs")
    return {"status": "success", "eligible": True, "scientific_success": True,
            "original_assessment": assessment, "mapping_coverage": coverage}


def validate_actual_launcher_argv(argv, args):
    require(type(argv) is list and argv[:3] == [str(args.python),
        str(args.launcher_root / "tools/run_posebusters_qualified_integration.py"), "run"], "actual launcher argv differs")
    require(len(argv[3:]) % 2 == 0, "launcher argv is not explicit flag/value pairs")
    values = {}
    for key, value in zip(argv[3::2], argv[4::2]):
        require(key.startswith("--"), "unexpected positional launcher argument")
        name = key[2:].replace("-", "_")
        require(name not in values and name in (*PATH_ARGUMENTS, *VALUE_ARGUMENTS), "duplicate/unknown launcher argument")
        values[name] = int(value) if name == "host_slot" and value in ("1", "2", "3", "4") else value
    equal(values, arguments(args), "actual launcher arguments differ from recorded inputs")


def validate_run_binding(value, root, results_root, expected_job):
    for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
        expected = expected_job.get(key)
        require(type(expected) is str and re.fullmatch(r"[1-9][0-9]*", expected) is not None,
                "aggregate workflow run/attempt identity is missing")
        equal(value["job"].get(key), expected, "retained host belongs to a different run/attempt")
    equal(value["job"].get("GITHUB_JOB"), "qualified_case", "retained host workflow job differs")
    slot = value["host_slot"]
    require(type(slot) is int and slot in HOST_SLOTS, "invalid artifact host slot")
    name = f"pb-qualified-integration-{CASE_ID}-host-{slot}-{expected_job['GITHUB_RUN_ID']}-{expected_job['GITHUB_RUN_ATTEMPT']}"
    expected_path = f"{name}/pb-qualified-integration/host-{slot}"
    equal(Path(root).relative_to(results_root).as_posix(), expected_path,
          "retained result is outside the exact current-run artifact/host path")


def validate_host(root, *, helper, controller, profile, bundle, selected, launcher_source, results_root, expected_job):
    value = read_json(root / "qualified-result.json")
    verify_signed(value)
    args = recorded_arguments(value["arguments"])
    validate_run_binding(value, root, results_root, expected_job)
    equal(value["schema_id"], SCHEMA, "host schema differs")
    equal(value["host_slot"], args.host_slot, "host slot differs")
    equal(value["files"], inventory(root), "retained raw evidence inventory differs")
    equal(value["limits"], LIMITS, "host limits differ")
    equal(value["profile_file_sha256"], PROFILE_FILE_SHA256, "host profile differs")
    equal(value["input_bundle_sha256"], BUNDLE_SHA256, "host bundle differs")
    equal(value["execution_source"], EXECUTION_SOURCE, "host execution source differs")
    equal(value["launcher_source"], launcher_source, "host launcher source differs")
    equal(args.launcher_workflow_sha, launcher_source["commit"], "host workflow SHA differs")
    equal(value["job"]["GITHUB_SHA"], launcher_source["commit"], "original workflow SHA was not retained")
    validate_actual_launcher_argv(value["actual_argv"], args)
    equal(digest_file(root / "bound-profile.json"), PROFILE_FILE_SHA256, "retained profile differs")
    command = qualification_command(args)
    equal(value["qualification_command"], command, "qualification command differs")
    process = read_json(root / "launcher-process/process-execution.json")
    controller.verify_signed(process, "control_sha256", "launcher process")
    equal(process["command"], command, "actual qualification command differs")
    require(value["status"] in ("success", "ineligible", "failed", "incomplete"), "unknown host result status")
    if value["status"] in ("failed", "incomplete"):
        require(value["scientific_success"] is False, "failed evidence claimed scientific success")
        return {"host_slot": args.host_slot, "status": value["status"], "eligible": value["eligible"],
                "scientific_success": False, "failure_preserved": True, "error": value.get("error"),
                "evidence_scope": "raw inventory and signed outer receipt verified; no scientific admission"}
    helper.validate_process(controller, root / "launcher-process", process, LAUNCHER_WALL_SECONDS, command)
    require(process["termination"] == "exited" and type(process["returncode"]) is int and process["returncode"] == 0,
            "qualification process did not pass")
    qualification = read_json(bound_file(root, value["qualification"]))
    expected_args = arguments(args)
    expected_args["output_root"] = str(args.output_root / "qualification")
    equal(qualification["arguments"], expected_args, "qualification argument binding differs")
    result = validate_qualification(root / "qualification", qualification, helper=helper, controller=controller,
        profile=profile, bundle=bundle, selected=selected, launcher_source=launcher_source)
    for name in ("status", "eligible", "scientific_success"):
        equal(value[name], result[name], "host/original evidence status differs")
    return {"host_slot": args.host_slot, **result}


def aggregate_status(rows):
    slots = [row.get("host_slot") for row in rows]
    if any(type(slot) is not int for slot in slots) or sorted(slots) != list(HOST_SLOTS):
        return "failed"
    if any(row.get("status") not in ("success", "ineligible") for row in rows):
        return "failed"
    if any(row.get("status") == "success" and (row.get("eligible") is not True or row.get("scientific_success") is not True)
           or row.get("status") == "ineligible" and (row.get("eligible") is not False or row.get("scientific_success") is not False)
           for row in rows):
        return "failed"
    return "success" if any(row["status"] == "success" for row in rows) else "profile_unavailable"


def aggregate(args):
    args.launcher_root = Path(__file__).resolve().parent.parent
    for name in ("execution_root", "input_root", "profile", "results_root", "output"):
        value = getattr(args, name).absolute()
        require(value == value.resolve(), "noncanonical aggregate path")
        setattr(args, name, value)
    require(not args.output.exists() and not args.output.is_relative_to(args.results_root),
            "aggregate output must be fresh and outside retained evidence")
    report = {"schema_id": SCHEMA, "status": "failed", "scientific_success": False, "hosts": [],
        "expected_host_slots": list(HOST_SLOTS), "case_id": CASE_ID, "stage": "pipeline", "required_modes": list(MODES),
        "profile_file_sha256": PROFILE_FILE_SHA256, "input_bundle_sha256": BUNDLE_SHA256,
        "limits": LIMITS, "prior_failed_run_reclassified": False, "historical_cause_confirmed": False,
        "scope": "new qualified 6YSP three-mode case validation; no other case rerun or promotion",
        "actual_argv": [sys.executable, *sys.argv]}
    try:
        helper = load_helpers(args.launcher_root)
        profile = load_profile(args.profile, args.profile_sha256, helper)
        equal(args.bundle_sha256, BUNDLE_SHA256, "aggregate input bundle differs")
        controller = helper.frozen_controller(args.execution_root)
        launcher = helper.git_identity(args.launcher_root)
        equal(os.environ.get("GITHUB_SHA"), launcher["commit"], "aggregate original workflow SHA differs")
        equal(helper.git_identity(args.execution_root), {key: EXECUTION_SOURCE[key] for key in ("commit", "tree")},
              "aggregate actual execution checkout differs")
        bundle, manifest = controller.load_bundle(args.input_root, BUNDLE_SHA256)
        equal(bundle["source"], EXECUTION_SOURCE, "aggregate bundle source differs")
        selected = controller.selected_inputs(args.input_root, bundle, manifest, CASE_ID, "pipeline")
        report.update(launcher_source=launcher, execution_source=EXECUTION_SOURCE)
        collect_hosts(args, report, helper, controller, profile, bundle, selected, launcher)
        equal(helper.git_identity(args.launcher_root), launcher, "aggregate launcher changed")
    except Exception as exc:
        report.update(status="failed", scientific_success=False, error_type=type(exc).__name__, error=str(exc))
    atomic_json(args.output, signed(report))
    print(json.dumps({key: report[key] for key in ("status", "scientific_success", "case_id")}))
    return 0 if report["status"] == "success" else 1


def collect_hosts(args, report, helper, controller, profile, bundle, selected, launcher):
    paths = sorted(args.results_root.rglob("qualified-result.json"))
    report["raw_result_count"] = len(paths)
    report["infrastructure_receipts"] = [descriptor(args.results_root, path)
        for path in sorted(args.results_root.rglob("infrastructure-failure.json"))]
    for path in paths:
        item = {"host_slot": None, "status": "invalid_evidence", "eligible": None,
                "scientific_success": False, "raw_result": descriptor(args.results_root, path)}
        try:
            item["host_slot"] = read_json(path).get("host_slot")
            item.update(validate_host(path.parent, helper=helper, controller=controller, profile=profile,
                                      bundle=bundle, selected=selected, launcher_source=launcher,
                                      results_root=args.results_root, expected_job=os.environ))
        except Exception as exc:
            item.update(error_type=type(exc).__name__, error=str(exc))
        report["hosts"].append(item)
    observed_slots = [row["host_slot"] for row in report["hosts"]]
    for slot in HOST_SLOTS:
        if slot not in observed_slots:
            report["hosts"].append({"host_slot": slot, "status": "incomplete", "eligible": None,
                "scientific_success": False, "error": "missing retained qualified-result.json"})
    report["status"] = aggregate_status(report["hosts"])
    report["scientific_success"] = report["status"] == "success"
    report["counts"] = {status: sum(row["status"] == status for row in report["hosts"])
                        for status in ("success", "ineligible", "failed", "incomplete", "invalid_evidence")}
    report["admitted_workers"] = 3 * report["counts"]["success"]
    report["profile_available"] = any(row.get("eligible") is True for row in report["hosts"])
    report["performance_inference"] = controller.PROTOCOL["performance_inference"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    children = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "_execute"):
        child = children.add_parser(name)
        for field in PATH_ARGUMENTS:
            child.add_argument("--" + field.replace("_", "-"), type=Path, required=True)
        child.add_argument("--profile-sha256", required=True)
        child.add_argument("--bundle-sha256", required=True)
        child.add_argument("--launcher-workflow-sha", required=True)
        child.add_argument("--host-slot", type=int, choices=HOST_SLOTS, required=True)
    child = children.add_parser("aggregate")
    for field in ("execution_root", "input_root", "profile", "results_root", "output"):
        child.add_argument("--" + field.replace("_", "-"), type=Path, required=True)
    child.add_argument("--profile-sha256", required=True)
    child.add_argument("--bundle-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "aggregate":
            return aggregate(args)
        if args.command == "_execute":
            normalize_run_arguments(args)
            return execute(args)
        return run(args)
    except Exception as exc:
        print(json.dumps({"status": "incomplete", "scientific_success": False,
                          "error_type": type(exc).__name__, "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
