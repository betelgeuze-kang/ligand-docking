"""Source-pinned, create-only supervisor for the frozen four-case SRO campaign.

No molecular code is imported here. Each case has one shared operational
ceiling for the native invocation, independent oracle, and case publication.
A stopped case is retained; subsequent cases remain unstarted with unknown work.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import time
import types
import zipfile

CASE_IDS = [f"perturbed_{index:02d}" for index in range(1, 5)]
CASE_WALL_NS = 7200 * 1_000_000_000
PROTOCOL_SHA = "5977f12ee7e35710e6a8eb09a19337ff579750f2573fa442d31b89fe3a94ca23"
MANIFEST_SHA = "4fa96ef4a8457fd20e8bce67dafa380c08b01e15765bcfbb0a1eb67634815dc3"
SHA = re.compile(r"[0-9a-f]{64}\Z")
PLACEHOLDERS = {"plan_path", "plan_sha256", "case_id", "child_result_path",
                "child_result_sha256", "oracle_output"}


class CampaignError(ValueError):
    """An operational integrity failure; no automatic retry is permitted."""


class CaseDeadline(CampaignError):
    """The shared case ceiling expired."""


def require(condition, reason):
    if not condition:
        raise CampaignError(reason)


def now():
    return datetime.now(timezone.utc).isoformat()


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "duplicate_json_key")
        value[key] = item
    return value


def loads(raw):
    return json.loads(raw, object_pairs_hook=_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(CampaignError("nonfinite_json")))


def _read(path):
    path = Path(path)
    require(path.is_absolute() and str(path.resolve(strict=True)) == str(path), "canonical_file_required")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_size <= 256 * 1024 * 1024, "regular_bounded_file_required")
        chunks = []
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(fd)
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), "file_changed_during_read")
        raw = b"".join(chunks)
        require(len(raw) == before.st_size, "file_size_changed")
        return raw
    finally:
        os.close(fd)


def file_ref(path):
    path = Path(path).absolute()
    raw = _read(path)
    return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def read_bound(ref, *, parse=True):
    require(type(ref) is dict and set(ref) == {"path", "sha256", "bytes"}, "file_pin_fields")
    require(type(ref["sha256"]) is str and SHA.fullmatch(ref["sha256"]) and
            type(ref["bytes"]) is int and 0 <= ref["bytes"] <= 256 * 1024 * 1024, "file_pin_shape")
    raw = _read(ref["path"])
    require(len(raw) == ref["bytes"] and hashlib.sha256(raw).hexdigest() == ref["sha256"], "bound_file_changed")
    return loads(raw) if parse else raw


def publish(path, value):
    path = Path(path)
    with path.open("xb") as stream:
        stream.write(encode(value))
        stream.flush()
        os.fsync(stream.fileno())
    return file_ref(path)


def inventory(directory):
    refs = []
    directory = Path(directory)
    if directory.exists():
        for path in sorted(directory.rglob("*")):
            require(not path.is_symlink(), "output_symlink")
            if path.is_file():
                refs.append(file_ref(path))
    return refs


def source_layout(plan_ref, review_ref, plan):
    """Authenticate local roles before opening or compiling supplied sources."""
    source = Path(__file__).absolute().parent
    require(plan_ref["path"] == str(source.parent / "plan.json") and
            review_ref["path"] == str(source.parent / "execution-review.json"), "plan_review_role_required")
    require(plan["driver_source_ref"]["path"] == str(source / "runtime_execution.py"), "driver_source_role_required")
    phase = plan.get("oracle_phase")
    require(type(phase) is dict, "separate_oracle_required")
    expected = {str(source / name) for name in ("endpoint_oracle_runner.py", "campaign_supervisor.py",
                                                "sro_recovery_endpoint_numerics_v1.py")}
    expected.add(str(source.parent / "oracle-input-spec.json"))
    refs = phase.get("source_refs")
    require(type(refs) is list and len(refs) == 4 and {ref["path"] for ref in refs} == expected,
            "oracle_source_roles_required")
    require(phase["argv_template"][:3] == ["-I", "-B", str(source / "endpoint_oracle_runner.py")],
            "exact_oracle_runner_required")
    return source


# Python -c consumes and hashes the entry source once, then executes those exact
# captured bytes. __file__ and sys.argv retain the reviewed script interface.
SOURCE_BOOTSTRAP = """import hashlib, os, pathlib, stat, sys
p, digest, size = sys.argv[1], sys.argv[2], int(sys.argv[3])
assert pathlib.Path(p).is_absolute() and str(pathlib.Path(p).resolve(strict=True)) == p
fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
try:
    before = os.fstat(fd)
    assert stat.S_ISREG(before.st_mode) and before.st_size == size
    chunks = []
    while True:
        chunk = os.read(fd, 65536)
        if not chunk: break
        chunks.append(chunk)
    raw = b''.join(chunks)
    after = os.fstat(fd)
    assert (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns) == (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)
    assert len(raw) == size and hashlib.sha256(raw).hexdigest() == digest
finally:
    os.close(fd)
sys.argv = [p] + sys.argv[4:]
exec(compile(raw, p, 'exec'), {'__name__':'__main__','__file__':p,'__builtins__':__builtins__})
"""


def source_command(python_executable, source_ref, arguments):
    read_bound(source_ref, parse=False)
    return [python_executable, "-I", "-B", "-c", SOURCE_BOOTSTRAP, source_ref["path"],
            source_ref["sha256"], str(source_ref["bytes"]), *arguments]


def _load_driver(ref):
    raw = read_bound(ref, parse=False)
    module = types.ModuleType("sro_pinned_native_driver")
    module.__file__ = ref["path"]
    exec(compile(raw, ref["path"], "exec"), module.__dict__)
    read_bound(ref, parse=False)
    return module


def _validate(plan_ref, review_ref, driver):
    plan = read_bound(plan_ref)
    source_layout(plan_ref, review_ref, plan)
    driver.validate_plan(plan)
    driver.review_execution(plan_ref, review_ref)
    require(plan["execution_order"] == CASE_IDS and plan["protocol_sha256"] == PROTOCOL_SHA and
            plan["manifest_sha256"] == MANIFEST_SHA and plan["budget"]["wall_seconds"] == 7200, "frozen_campaign_required")
    phase = plan.get("oracle_phase")
    require(type(phase) is dict and set(phase) == {"python_executable", "python_binary_ref", "argv_template",
                                                "source_refs", "receipt_name"}, "separate_oracle_required")
    require(phase["receipt_name"] == "numerical-receipt.json" and type(phase["source_refs"]) is list and
            file_ref(Path(__file__).absolute()) in phase["source_refs"], "reviewed_supervisor_source_required")
    for ref in phase["source_refs"]:
        read_bound(ref, parse=False)
    require(Path(phase["python_executable"]).is_absolute() and
            file_ref(Path(phase["python_executable"]).resolve(strict=True)) == phase["python_binary_ref"], "oracle_python_changed")
    template = phase["argv_template"]
    require(type(template) is list and len(template) >= 3 and template[:2] == ["-I", "-B"] and
            any(ref["path"] == template[2] for ref in phase["source_refs"]), "source_pinned_isolated_oracle_required")
    require(all(type(arg) is str for arg in template), "oracle_argv_shape")
    for arg in template:
        for placeholder in re.findall(r"\{([^{}]+)\}", arg):
            require(placeholder in PLACEHOLDERS, "undeclared_oracle_placeholder")
    return plan


def _remaining(deadline_ns):
    remaining = (deadline_ns - time.monotonic_ns()) / 1_000_000_000
    if remaining <= 0:
        raise CaseDeadline("shared_case_deadline_expired")
    return remaining


def _terminate_group(process):
    """Always reap; TERM grace is bounded and followed by group KILL."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass
    # A terminated leader does not prove that all descendants exited.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=5)


def _launch(argv, directory, deadline_ns):
    directory = Path(directory)
    directory.mkdir(mode=0o700)
    start = time.monotonic_ns()
    _remaining(deadline_ns)
    environment = dict(os.environ)
    environment.update({"OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
                        "CUDA_VISIBLE_DEVICES": "", "HIP_VISIBLE_DEVICES": "", "ROCR_VISIBLE_DEVICES": ""})
    process = None
    error = None
    try:
        with (directory / "stdout.log").open("xb") as stdout, (directory / "stderr.log").open("xb") as stderr:
            process = subprocess.Popen(argv, stdout=stdout, stderr=stderr, env=environment, start_new_session=True)
            publish(directory / "process-start.json", {"schema_id": "sro_supervised_process_start/1",
                    "pid": process.pid, "argv": argv, "started_at": now(), "started_monotonic_ns": start,
                    "deadline_monotonic_ns": deadline_ns})
            while process.poll() is None:
                _remaining(deadline_ns)
                time.sleep(min(.2, _remaining(deadline_ns)))
            _remaining(deadline_ns)
    except BaseException as exc:
        error = {"type": type(exc).__name__, "reason": str(exc)}
        if process is not None:
            _terminate_group(process)
        raise
    finally:
        publish(directory / "process-end.json", {"schema_id": "sro_supervised_process_end/1",
                "pid": None if process is None else process.pid,
                "returncode": None if process is None else process.returncode, "error": error,
                "ended_at": now(), "inclusive_wall_ns": time.monotonic_ns() - start,
                "durations_are_inclusive_do_not_sum": True})
    require(process.returncode == 0, "child_process_nonzero_exit:" + str(process.returncode))


def _native_result(native_dir, case_id):
    ref = file_ref(Path(native_dir) / "child-result.json")
    value = read_bound(ref)
    require(value["schema_id"] == "sro_native_child_result/1" and value["case_id"] == case_id and
            value["status"] == "native_completed", "native_case_failed")
    expected = {name: str(Path(native_dir) / name) for name in
                ("native-start.json", "preflight.json", "native-end.json", "post-exit-source-check.json")}
    require(type(value["lifecycle_refs"]) is dict and set(value["lifecycle_refs"]) == set(expected), "native_lifecycle_missing")
    for name, lifecycle_ref in value["lifecycle_refs"].items():
        require(lifecycle_ref["path"] == expected[name], "native_lifecycle_path_changed")
        read_bound(lifecycle_ref)
    ending = read_bound(value["lifecycle_refs"]["native-end.json"])
    require(ending["error_type"] is None and ending["post_exit_error_type"] is None and
            ending["pending_dispatches"] == [], "native_pending_or_integrity_failure")
    require(value["verification_ref"]["path"] == str(Path(native_dir) / "semantic-verification.json") and
            value["endpoint_states_ref"]["path"] == str(Path(native_dir) / "endpoint-states.json"), "native_output_role_changed")
    require(value["native_artifact_refs"] == inventory(Path(native_dir) / "run"), "native_artifact_inventory_changed")
    verification = read_bound(value["verification_ref"])
    require(verification["structural_verification_passed"] is True and
            verification["scoring_reexecuted"] is False and verification["numerical_evaluation_reexecuted"] is False,
            "native_saved_semantics_unverified")
    read_bound(value["endpoint_states_ref"])
    for artifact in value["native_artifact_refs"]:
        read_bound(artifact, parse=False)
    return ref


def _oracle_result(oracle_dir, case_id, *, plan_ref, plan, native_ref):
    ref = file_ref(Path(oracle_dir) / "numerical-receipt.json")
    value = read_bound(ref)
    require(value["schema_id"] == "sro_recovery_endpoint_numerics/1" and value["case_id"] == case_id,
            "oracle_receipt_identity")
    require(value["failure"] is None and value["denominator"]["requested"] == 2 and
            value["denominator"]["evaluated"] == 2 and value["denominator"]["unknown"] == 0 and
            [state["label"] for state in value["states"]] == ["initial", "last_accepted"] and
            all(state["status"] == "evaluated" for state in value["states"]), "oracle_operational_failure")
    require(value["new_native_force_calls"] == value["new_native_score_calls"] == 0, "oracle_new_native_work")
    lifecycle = read_bound(file_ref(Path(oracle_dir) / "lifecycle.json"))
    require(lifecycle["failure"] is None and lifecycle["plan_ref"] == plan_ref and
            lifecycle["native_child_ref"] == native_ref and lifecycle["numerical_receipt_ref"] == ref,
            "oracle_lifecycle_integrity_failure")
    child = read_bound(native_ref)
    case = next(case for case in plan["cases"] if case["case_id"] == case_id)
    source = Path(__file__).absolute().parent
    oracle_source_ref = next(ref for ref in plan["oracle_phase"]["source_refs"]
                             if ref["path"] == str(source / "sro_recovery_endpoint_numerics_v1.py"))
    require(value["openmm_observations_performed"] is True and value["source_sha256"] == oracle_source_ref["sha256"] and
            value["executing_source_ref"] == oracle_source_ref and value["environment"]["platform"] == "Reference" and
            value["environment"]["isolated"] == 1, "real_isolated_reference_oracle_required")
    require(value["request_ref"] == case["request_file_ref"] and
            value["binding_ref"] == child["lifecycle_refs"]["preflight.json"] and
            value["endpoint_states_ref"] == child["endpoint_states_ref"] and
            value["protocol_sha256"] == PROTOCOL_SHA and value["manifest_sha256"] == MANIFEST_SHA and
            value["wheel_ref"] == plan["wheel_ref"], "oracle_native_binding_changed")
    require(value["receipt_sha256"] == hashlib.sha256(json.dumps(
            {key: item for key, item in value.items() if key != "receipt_sha256"}, sort_keys=True,
            separators=(",", ":"), allow_nan=False).encode()).hexdigest(), "oracle_receipt_seal_changed")
    return ref, value["all_same_math_checks_passed"]


def failure_integrity(plan_ref, review_ref, driver):
    """Read-only closure verification cannot recover a killed process's origins."""
    result = {"input_source_wheel_verified": False, "installed_file_closure_verified": False,
              "installed_python_members": None, "loaded_child_origins_verified": False,
              "loaded_child_origins_status": "unavailable_after_incomplete_child", "error": None,
              "new_native_force_calls": 0, "new_native_score_calls": 0}
    try:
        plan = _validate(plan_ref, review_ref, driver)
        result["input_source_wheel_verified"] = True
        raw = read_bound(plan["wheel_ref"], parse=False)
        site = Path(plan["installed_site"])
        count = 0
        with zipfile.ZipFile(io.BytesIO(raw)) as wheel:
            names = wheel.namelist()
            require(len(names) == len(set(names)), "duplicate_wheel_members")
            for name in names:
                if not name.endswith(".py"):
                    continue
                relative = Path(name)
                require(not relative.is_absolute() and ".." not in relative.parts, "wheel_path_escape")
                path = site / relative
                require(path.resolve(strict=True).is_relative_to(site.resolve(strict=True)), "installed_path_escape")
                require(_read(path) == wheel.read(name), "installed_wheel_member_changed")
                count += 1
        expected_members = {name for name in names if name.endswith(".py")}
        namespaces = {Path(name).parts[0] for name in expected_members}
        actual_members = set()
        for namespace in namespaces:
            for path in (site / namespace).rglob("*.py"):
                require(not path.is_symlink() and path.is_file(), "installed_python_symlink")
                actual_members.add(str(path.relative_to(site)))
        require(actual_members == expected_members, "installed_python_membership_changed")
        require(count > 0, "empty_python_wheel")
        result.update(installed_file_closure_verified=True, installed_python_members=count)
    except BaseException as exc:
        result["error"] = {"type": type(exc).__name__, "reason": str(exc)}
    return result


def run_campaign(plan_ref, review_ref, output):
    """Run the fixed roster once; inputs and output documents are never replaced."""
    source = Path(__file__).absolute().parent
    require(plan_ref["path"] == str(source.parent / "plan.json") and
            review_ref["path"] == str(source.parent / "execution-review.json"), "plan_review_role_required")
    plan = read_bound(plan_ref)
    source_layout(plan_ref, review_ref, plan)
    driver = _load_driver(plan["driver_source_ref"])
    plan = _validate(plan_ref, review_ref, driver)
    output = Path(output).absolute()
    require(str(output.resolve()) == str(output) and output.is_relative_to(source.parent), "canonical_output_scope_required")
    output.mkdir(mode=0o700)
    start = time.monotonic_ns()
    rows = [{"case_id": case_id, "status": "unstarted", "started_at": None, "work": None,
             "terminal_case_ref": None, "error": None} for case_id in CASE_IDS]
    publish(output / "campaign-start.json", {"schema_id": "sro_four_case_campaign_start/1",
            "plan_ref": plan_ref, "review_ref": review_ref, "supervisor_source_ref": file_ref(Path(__file__).absolute()),
            "started_at": now(), "case_order": CASE_IDS, "denominator": 4})
    for row in rows:
        case_id = row["case_id"]
        case_root = output / case_id
        case_root.mkdir(mode=0o700)
        case_start = time.monotonic_ns()
        deadline = case_start + CASE_WALL_NS
        row["started_at"] = now()
        row["status"] = "failed"
        native_dir, oracle_dir = case_root / "native", case_root / "oracle"
        supervisor_ref = publish(case_root / "supervisor.json", {"schema_id": "sro_native_case_supervisor/1",
            "case_id": case_id, "plan_ref": plan_ref, "execution_review_ref": review_ref,
            "controller_pid": os.getpid(), "started_at": row["started_at"],
            "started_monotonic_ns": case_start, "deadline_monotonic_ns": deadline, "native_output": str(native_dir)})
        native_ref = oracle_ref = None
        same_math = None
        try:
            plan = _validate(plan_ref, review_ref, driver)
            _remaining(deadline)
            argv = source_command(plan["python_executable"], plan["driver_source_ref"], ["child",
                    "--plan", plan_ref["path"], "--case", case_id, "--output", str(native_dir),
                    "--review", review_ref["path"], "--supervisor", supervisor_ref["path"]])
            _launch(argv, case_root / "native-process", deadline)
            native_ref = _native_result(native_dir, case_id)
            plan = _validate(plan_ref, review_ref, driver)
            _remaining(deadline)
            values = {"plan_path": plan_ref["path"], "plan_sha256": plan_ref["sha256"], "case_id": case_id,
                      "child_result_path": native_ref["path"], "child_result_sha256": native_ref["sha256"],
                      "oracle_output": str(oracle_dir)}
            phase = plan["oracle_phase"]
            runner_ref = next(ref for ref in phase["source_refs"] if ref["path"] == phase["argv_template"][2])
            oracle_argv = source_command(phase["python_executable"], runner_ref,
                                        [arg.format_map(values) for arg in phase["argv_template"][3:]])
            _launch(oracle_argv, case_root / "oracle-process", deadline)
            oracle_ref, same_math = _oracle_result(oracle_dir, case_id, plan_ref=plan_ref, plan=plan, native_ref=native_ref)
            _validate(plan_ref, review_ref, driver)
            _remaining(deadline)
            row["status"] = "completed"
        except BaseException as exc:
            row["status"] = "watchdog" if isinstance(exc, CaseDeadline) else "failed"
            row["error"] = {"type": type(exc).__name__, "reason": str(exc)}
        if row["status"] != "completed":
            row["postfailure_integrity_ref"] = publish(case_root / "postfailure-integrity.json",
                failure_integrity(plan_ref, review_ref, driver))
        row["native_child_ref"] = native_ref
        row["numerical_receipt_ref"] = oracle_ref
        row["all_same_math_checks_passed"] = same_math
        row["work"] = None  # Raw retained evidence is authoritative; missing quantities remain unknown.
        row["actual_receipt_refs"] = inventory(case_root)
        terminal = {"schema_id": "sro_four_case_terminal_case/1", **row,
                    "supervisor_ref": supervisor_ref, "ended_at": now(),
                    "inclusive_wall_ns": time.monotonic_ns() - case_start,
                    "deadline_monotonic_ns": deadline, "durations_are_inclusive_do_not_sum": True,
                    "scientifically_validated": False, "product_qualified": False}
        row["terminal_case_ref"] = publish(case_root / "terminal-case.json", terminal)
        if row["status"] == "completed" and time.monotonic_ns() >= deadline:
            row["status"] = "watchdog"
            row["error"] = {"type": "CaseDeadline", "reason": "case_seal_exceeded_shared_deadline"}
            row["postfailure_integrity_ref"] = publish(case_root / "postfailure-integrity.json",
                failure_integrity(plan_ref, review_ref, driver))
            row["terminal_case_ref"] = publish(case_root / "terminal-seal-watchdog.json", {
                "schema_id": "sro_four_case_terminal_case/1", **row, "prior_terminal_case_ref": row["terminal_case_ref"]})
        if row["status"] != "completed":
            break
    receipt = {"schema_id": "sro_four_case_campaign/1", "plan_ref": plan_ref, "review_ref": review_ref,
               "execution_order": CASE_IDS, "case_results": rows, "denominator": 4,
               "completed_count": sum(row["status"] == "completed" for row in rows),
               "unstarted_count": sum(row["status"] == "unstarted" for row in rows),
               "status": "completed" if all(row["status"] == "completed" for row in rows) else "stopped",
               "ended_at": now(), "inclusive_wall_ns": time.monotonic_ns() - start,
               "durations_are_inclusive_do_not_sum": True, "scientifically_validated": False,
               "product_qualified": False, "HIP_qualified": False,
               "work_policy": "raw_receipts_retained; no_zero_inference_for_incomplete_or_unstarted_work"}
    return publish(output / "campaign-result.json", receipt)


# Saved-data arithmetic after terminal campaign receipts; no molecular calls.
EXPORT_CHEMISTRY_SHA = "1d960edf1ee7c450af7594b0fad6c6f605439e045da8292bfa48a74d4f95a3dc"
EXPORT_INPUT_HASHES = {
    "ligand": "aee0cdee35491fc44998a14c69c5e888b2de5e6c0c85b35bfedfb0562832445c",
    "parameters": "16d3b25e6492ae8500771d60d6fe5b5db12089b8c7fa64d3f25a6f1230fad217",
    "extensions": "871c1a252c87c0b4f134c8b572f009f99658fea88f1076c9ee3fe1461a0871f6",
    "cross_parameters": "226cb9f4be87b40d312e4b3bdb0dbc785bd6d6e87daa68e2f6abec76dde22d52",
    "receptor": "2c0970bcaf9e994f382e0f0c0fdacbfd1359bef60a10b879f757b31628658c4c",
}
EXPORT_AUTHORITY = {"known_reserved_source_development_only": True, "existing_source_role_unchanged": True,
    "new_source_rights_admitted": False, "training_admitted": False, "calibration_admitted": False,
    "independent_evaluation_admitted": False, "independent_recovery_claim_allowed": False,
    "experimental_labels_used": False, "protected_evaluation_used": False,
    "scientifically_validated": False, "product_qualified": False, "HIP_qualified": False}
EXPORT_CHECKS = {"bond_lengths_preserved", "declared_chirality_preserved", "element_vdw_ligand_overlap_free",
    "element_vdw_receptor_overlap_free", "inside_declared_pocket", "ligand_self_clash_free", "proper_rotation",
    "receptor_ligand_clash_free"}


def compact_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _journal_work(native_dir):
    """Classify durable objective outcomes and keep pending restarts separate."""
    numerical = Path(native_dir) / "run" / "numerical"
    work = {key: None for key in ("objective_attempts", "initial_successful_objectives", "accepted_steps",
            "rejected_attempts", "failed_attempts", "unknown_pending_attempts", "restart_force_calls", "score_calls", "oracle_states")}
    work.update(AI_inference_calls=0, proposal_calls=0)
    accounting = {"work": work, "journal_prefix_complete": False, "objective_pending": None,
                  "restart_pending": None, "raw_dispatch_starts": None, "raw_pending_dispatches": None,
                  "completed_force_dispatches": None, "completed_score_dispatches": None,
                  "returned_dispatches": None, "error_dispatches": None,
                  "reused_score_receipts": None, "unknown_pending_score_attempts": None, "error": None}
    try:
        metadata = read_bound(file_ref(numerical / "meta.json"))
        require(metadata["binding_sha256"] == compact_hash(metadata["binding"]), "journal_metadata_seal")
        raw = read_bound(file_ref(numerical / "events.jsonl"), parse=False)
        require(not raw or raw.endswith(b"\n"), "torn_trial_journal")
        events = [loads(line) for line in raw.splitlines()]
        head = metadata["binding_sha256"]
        pending = None
        objective = initial = accepted = rejected = failed = restart_force = objective_force = 0
        for index, event in enumerate(events):
            require(event["index"] == index and event["previous_sha256"] == head and
                    event["event_sha256"] == compact_hash({key: item for key, item in event.items() if key != "event_sha256"}),
                    "journal_chain_changed")
            head = event["event_sha256"]
            kind, payload = event["kind"], event["payload"]
            if kind in ("objective_started", "restart_started"):
                require(pending is None, "overlapping_journal_intents")
                pending = (kind, payload)
                objective += int(kind == "objective_started")
            else:
                require(pending is not None and kind == pending[0].replace("_started", "_finished"), "unmatched_journal_finish")
                if kind == "objective_finished":
                    require(payload["attempt"] == pending[1]["attempt"], "journal_attempt_mismatch")
                    outcome = payload["decision"]["outcome"]
                    require(outcome in {"initial", "accepted", "rejected_displacement", "rejected_non_descent",
                            "rejected_armijo", "rejected_evaluation"}, "unknown_objective_outcome")
                    initial += int(outcome == "initial")
                    accepted += int(outcome == "accepted")
                    failed += int(outcome == "rejected_evaluation")
                    rejected += int(outcome in {"rejected_displacement", "rejected_non_descent", "rejected_armijo"})
                    objective_force += payload["work"]["force_calls"]
                else:
                    restart_force += payload["work"]["force_calls"]
                pending = None
        objective_pending = int(pending is not None and pending[0] == "objective_started")
        restart_pending = int(pending is not None and pending[0] == "restart_started")
        work.update(objective_attempts=objective, initial_successful_objectives=initial, accepted_steps=accepted,
            rejected_attempts=rejected, failed_attempts=failed, unknown_pending_attempts=objective_pending,
            restart_force_calls=None if restart_pending else restart_force)
        require(objective == initial + accepted + rejected + failed + objective_pending, "objective_partition")
        accounting.update(journal_prefix_complete=True, objective_pending=objective_pending, restart_pending=restart_pending,
                          objective_force_calls_completed=objective_force, restart_force_calls_completed=restart_force)
    except Exception as exc:
        accounting["error"] = {"type": type(exc).__name__, "reason": str(exc)}
    try:
        native_end = read_bound(file_ref(Path(native_dir) / "native-end.json"))
        starts = native_end["dispatch_starts"]
        pending_dispatches = native_end["pending_dispatches"]
        require(set(starts) == {"force", "score", "graph"}, "dispatch_count_fields")
        raw = _read(Path(native_dir) / "dispatch.jsonl") if (Path(native_dir) / "dispatch.jsonl").exists() else b""
        require(not raw or raw.endswith(b"\n"), "torn_dispatch_ledger")
        observed = {"force": 0, "score": 0, "graph": 0}
        active = set()
        completed = {"force": 0, "score": 0, "graph": 0}
        returned = {"force": 0, "score": 0, "graph": 0}
        errored = {"force": 0, "score": 0, "graph": 0}
        for event in [loads(line) for line in raw.splitlines()]:
            key = (event["kind"], event["index"])
            require(event["kind"] in observed, "unknown_dispatch_kind")
            if event["event"] == "begin":
                require(event["index"] == observed[event["kind"]] and key not in active, "dispatch_index")
                observed[event["kind"]] += 1
                active.add(key)
            else:
                require(event["event"] == "end" and key in active, "dispatch_finish")
                completed[event["kind"]] += 1
                require(event["error_type"] is None or type(event["error_type"]) is str, "dispatch_error_shape")
                returned[event["kind"]] += int(event["error_type"] is None)
                errored[event["kind"]] += int(event["error_type"] is not None)
                active.remove(key)
        require(observed == starts and sorted(active) == sorted(tuple(item) for item in pending_dispatches), "native_dispatch_end_mismatch")
        accounting.update(raw_dispatch_starts=observed, raw_pending_dispatches=sorted(active),
                          completed_force_dispatches=completed["force"], completed_score_dispatches=completed["score"],
                          returned_dispatches=returned, error_dispatches=errored,
                          dispatch_return_is_not_numerical_validation=True)
        work["score_calls"] = None if any(kind == "score" for kind, _ in active) else observed["score"]
        invocation_path = Path(native_dir) / "run" / "invocation-000000.end.json"
        if invocation_path.exists():
            invocation = read_bound(file_ref(invocation_path))
            score_work = invocation["score_work"]
            require(score_work["new_score_calls"] == observed["score"], "raw_invocation_score_mismatch")
            require(type(score_work["reused_score_receipts"]) is int and score_work["reused_score_receipts"] >= 0 and
                    type(score_work["unknown_pending_score_attempts"]) is int and
                    score_work["unknown_pending_score_attempts"] >= 0, "score_reuse_or_pending_shape")
            accounting["reused_score_receipts"] = score_work["reused_score_receipts"]
            accounting["unknown_pending_score_attempts"] = score_work["unknown_pending_score_attempts"]
            if score_work["unknown_pending_score_attempts"]:
                work["score_calls"] = None
            if invocation["new_force_calls"] is not None:
                require(invocation["new_force_calls"] == observed["force"], "raw_invocation_force_mismatch")
        if accounting["journal_prefix_complete"] and not active and not accounting["objective_pending"] and not accounting["restart_pending"]:
            require(observed["force"] == accounting["objective_force_calls_completed"] + accounting["restart_force_calls_completed"],
                    "raw_journal_force_mismatch")
    except Exception as exc:
        accounting["dispatch_error"] = {"type": type(exc).__name__, "reason": str(exc)}
    return accounting


def _exact_saved(value):
    if type(value) is float:
        require(math.isfinite(value), "nonfinite_saved_value")
        return ["float", value.hex()]
    if type(value) is list:
        return ["list", [_exact_saved(item) for item in value]]
    if type(value) is dict:
        return ["dict", [[key, _exact_saved(value[key])] for key in sorted(value)]]
    return [type(value).__name__, value]


def _saved_number(value):
    require(type(value) is str, "canonical_saved_number_required")
    number = float.fromhex(value)
    require(math.isfinite(number) and number.hex() == value, "noncanonical_or_nonfinite_saved_number")
    return number


def _saved_matrix(rows):
    require(type(rows) is list and len(rows) == 26 and all(type(row) is list and len(row) == 3 for row in rows),
            "saved_endpoint_shape")
    return [[_saved_number(value) for value in row] for row in rows]


def _export_binding(campaign_path, campaign):
    archive_root = campaign_path.parent.parent
    require(campaign["plan_ref"]["path"] == str(archive_root / "plan.json") and
            campaign["review_ref"]["path"] == str(archive_root / "execution-review.json"), "campaign_plan_role")
    plan = read_bound(campaign["plan_ref"])
    require(plan["protocol_sha256"] == PROTOCOL_SHA and plan["manifest_sha256"] == MANIFEST_SHA,
            "frozen_export_protocol_required")
    source = archive_root / "source"
    require(plan["driver_source_ref"]["path"] == str(source / "runtime_execution.py"), "export_driver_role")
    expected = {str(source / name) for name in ("endpoint_oracle_runner.py", "campaign_supervisor.py",
                                                "sro_recovery_endpoint_numerics_v1.py")}
    expected.add(str(archive_root / "oracle-input-spec.json"))
    source_refs = plan["oracle_phase"]["source_refs"]
    require(len(source_refs) == 4 and {ref["path"] for ref in source_refs} == expected, "export_source_roles")
    for ref in [plan["driver_source_ref"], *source_refs]:
        read_bound(ref, parse=False)
    review = read_bound(campaign["review_ref"])
    require(review["schema_id"] == "sro_native_execution_review/1" and review["execution_authorized"] is True and
            review["plan_sha256"] == campaign["plan_ref"]["sha256"] and
            review["driver_source_sha256"] == plan["driver_source_ref"]["sha256"], "export_review_binding")
    reviewed = datetime.fromisoformat(review["reviewed_at"])
    require(reviewed.utcoffset() is not None, "export_review_timezone")
    for row in campaign["case_results"]:
        if row["status"] != "unstarted":
            started = datetime.fromisoformat(row["started_at"])
            require(started.utcoffset() is not None and started > reviewed, "export_result_precedes_review")
    return plan


def export_results(campaign_ref, output):
    """Export retained last-accepted endpoints, never a better historical state.

    This verifies saved data seals and source-pinned parent assertions. It makes
    no new numerical observations and cannot qualify science or service use.
    """
    campaign_path = Path(campaign_ref["path"])
    require(campaign_path.name == "campaign-result.json" and campaign_path.parent.name == "campaign", "campaign_role_required")
    campaign = read_bound(campaign_ref)
    require(campaign["schema_id"] == "sro_four_case_campaign/1" and campaign["execution_order"] == CASE_IDS and
            campaign["denominator"] == 4 and [row["case_id"] for row in campaign["case_results"]] == CASE_IDS,
            "four_case_campaign_required")
    plan = _export_binding(campaign_path, campaign)
    output = Path(output).absolute()
    require(not output.is_relative_to(campaign_path.parent), "export_cannot_change_frozen_campaign")
    output.mkdir(mode=0o700)
    rich_rows, legacy_rows = [], []
    fatal = False
    for row in campaign["case_results"]:
        case_id, status = row["case_id"], row["status"]
        require(status in {"completed", "failed", "watchdog", "unstarted"}, "unknown_case_status")
        require(not fatal or status == "unstarted", "execution_after_fatal")
        fatal = fatal or status in {"failed", "watchdog"}
        if status == "unstarted":
            rich_rows.append({"case_id": case_id, "status": status, "work": None,
                              "legacy_exported": False, "omission_reason": "unstarted_work_unknown"})
            continue
        case_root = campaign_path.parent / case_id
        terminal_ref = row["terminal_case_ref"]
        require(terminal_ref["path"] in {str(case_root / "terminal-case.json"), str(case_root / "terminal-seal-watchdog.json")},
                "terminal_case_role")
        read_bound(terminal_ref)
        for ref in row["actual_receipt_refs"]:
            require(Path(ref["path"]).is_relative_to(case_root), "case_receipt_role")
            read_bound(ref, parse=False)
        accounting = _journal_work(case_root / "native")
        work = accounting["work"]
        native_ref = row.get("native_child_ref")
        numerical_ref = row.get("numerical_receipt_ref")
        if numerical_ref is None:
            numerical_ref = next((ref for ref in row["actual_receipt_refs"]
                                  if ref["path"] == str(case_root / "oracle" / "numerical-receipt.json")), None)
        if numerical_ref is not None:
            require(numerical_ref["path"] == str(case_root / "oracle" / "numerical-receipt.json"), "numeric_export_role")
            numeric = read_bound(numerical_ref)
            require(numeric["receipt_sha256"] == compact_hash({key: item for key, item in numeric.items() if key != "receipt_sha256"}),
                    "saved_numeric_seal")
            work["oracle_states"] = numeric["denominator"]["evaluated"]
        rich = {"case_id": case_id, "status": status, "accounting": accounting, "work": work,
                "legacy_exported": False, "omission_reason": None}
        rich_rows.append(rich)
        known = all(work[name] is not None for name in ("objective_attempts", "initial_successful_objectives", "accepted_steps",
                    "rejected_attempts", "failed_attempts", "restart_force_calls", "score_calls"))
        if not known or accounting["error"] is not None or accounting.get("dispatch_error") is not None:
            rich["omission_reason"] = "legacy_reader_cannot_represent_unknown_or_unverified_work"
            continue
        if native_ref is None:
            rich["omission_reason"] = "legacy_start_coordinates_not_authenticated"
            continue
        require(native_ref["path"] == str(case_root / "native" / "child-result.json") and
                _native_result(case_root / "native", case_id) == native_ref, "saved_native_result_changed")
        child = read_bound(native_ref)
        endpoints = read_bound(child["endpoint_states_ref"])
        initial_coordinates = _saved_matrix(endpoints["states"][0]["coordinates"])
        declared_case = next(case for case in plan["cases"] if case["case_id"] == case_id)
        require(hashlib.sha256(encode(_exact_saved(initial_coordinates))).hexdigest() ==
                declared_case["source_candidate_coordinates_sha256"], "export_start_coordinate_binding")
        saved = {"case_id": case_id, "status": status, "started_at": row["started_at"],
            "input_coordinates_sha256": hashlib.sha256(encode(initial_coordinates)).hexdigest(),
            "chemistry_sha256": EXPORT_CHEMISTRY_SHA, "original_input_hashes": EXPORT_INPUT_HASHES,
            "endpoint_policy": "last_accepted_state", "coordinates_angstrom": None, "forces_kcal_per_mol_angstrom": None,
            "initial_internal_energy_kcal_per_mol": None, "final_internal_energy_kcal_per_mol": None,
            "baseline_dimensionless_score": None, "final_dimensionless_score": None, "geometry_complete": False,
            "geometry_checks": {}, "numerical_audit": None, "work": work,
            "actual_receipt_refs": [terminal_ref, *row["actual_receipt_refs"]]}
        if status == "completed":
            require(native_ref is not None and numerical_ref is not None and
                    native_ref["path"] == str(case_root / "native" / "child-result.json"), "completed_export_receipts_required")
            refs = {ref["path"]: ref for ref in child["native_artifact_refs"]}
            result = read_bound(refs[str(case_root / "native" / "run" / "result.json")])
            require(result["result_sha256"] == compact_hash({key: item for key, item in result.items() if key != "result_sha256"}),
                    "saved_native_result_seal")
            state = result["numerical_result"]["checkpoint"]["state"]
            initial, current = state["initial"], state["current"]
            endpoints = read_bound(child["endpoint_states_ref"])
            require(endpoints["states"] == [{"label": label, **{name: observed[name] for name in ("coordinates", "energy", "forces", "components")}}
                    for label, observed in (("initial", initial), ("last_accepted", current))], "last_current_export_binding")
            refined = result["rows"]["refined"]
            require(refined["coordinates_binary64_hex"] == current["coordinates"], "scored_last_current_mismatch")
            geometry = refined["pose_validity"]
            require(set(geometry["checks"]) == EXPORT_CHECKS and all(type(value) is bool for value in geometry["checks"].values()),
                    "saved_geometry_checks")
            require(work["unknown_pending_attempts"] == 0 and work["initial_successful_objectives"] == 1 and
                    work["score_calls"] == work["oracle_states"] == 2 and numeric["failure"] is None, "completed_export_work")
            coordinates = _saved_matrix(current["coordinates"])
            require(_saved_matrix(initial["coordinates"]) == initial_coordinates, "initial_export_state_changed")
            saved.update(coordinates_angstrom=coordinates, forces_kcal_per_mol_angstrom=_saved_matrix(current["forces"]),
                initial_internal_energy_kcal_per_mol=_saved_number(initial["components"]["ligand_internal"]),
                final_internal_energy_kcal_per_mol=_saved_number(current["components"]["ligand_internal"]),
                baseline_dimensionless_score=result["rows"]["baseline"]["score"], final_dimensionless_score=refined["score"],
                geometry_complete=geometry["complete"], geometry_checks=geometry["checks"],
                numerical_audit={"endpoint_count": 2,
                    "maximum_energy_error_kcal_per_mol": max(max(observation["energy_absolute_error_kcal_per_mol"],
                        *observation["component_absolute_errors_kcal_per_mol"].values()) for observation in numeric["states"]),
                    "maximum_force_component_error_kcal_per_mol_angstrom": max(observation["force_component_absolute_error_kcal_per_mol_angstrom"]
                                                                               for observation in numeric["states"])})
        legacy_rows.append(saved)
        rich["legacy_exported"] = True
    legacy_ref = publish(output / "saved-recovery-results.json", {"schema_id": "sro_saved_recovery_results/1",
        "protocol_sha256": PROTOCOL_SHA, "authority": EXPORT_AUTHORITY, "case_results": legacy_rows})
    return publish(output / "export-receipt.json", {"schema_id": "sro_saved_recovery_export/1", "campaign_ref": campaign_ref,
        "saved_results_ref": legacy_ref, "case_results": rich_rows, "denominator": 4,
        "export_source_ref": file_ref(Path(__file__).absolute()),
        "new_native_force_calls": 0, "new_native_score_calls": 0, "new_openmm_observations": 0,
        "authority": EXPORT_AUTHORITY, "evidence_scope": "saved_data_arithmetic_and_existing_source_pinned_execution_receipts"})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--review", required=True)
    parser.add_argument("--review-sha256", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    source = Path(__file__).absolute().parent
    require(Path(args.plan).absolute() == source.parent / "plan.json" and
            Path(args.review).absolute() == source.parent / "execution-review.json", "plan_review_role_required")
    plan_ref, review_ref = file_ref(args.plan), file_ref(args.review)
    require(plan_ref["sha256"] == args.plan_sha256 and review_ref["sha256"] == args.review_sha256,
            "command_input_pin_mismatch")
    print(json.dumps(run_campaign(plan_ref, review_ref, args.output), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
