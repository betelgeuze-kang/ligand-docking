"""Observe predeclared hosts around the unchanged 8f three-mode case CLI.

CPU identity is evidence, never an eligibility filter. Collection completion
does not turn an original scientific failure into success. No frozen controller
or worker source is edited, replaced or instrumented by this launcher.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = "betelgeuze.posebusters_observed_integration/1.0.0"
PROTOCOL_SCHEMA = "betelgeuze.posebusters_observed_protocol/1.0.0"
PROTOCOL_SHA256 = "1cea1d24c3e02b675cadf73c1a998775f6dfdee76b328d3116683d9e12ebf08d"
MONITOR_HELPER_SHA256 = "3056a63fb7f6f173694025ee8a79516fbb4161667b0c21edbb790fee6bba0e6f"


def _load_shared():
    path = ROOT / "tools/run_posebusters_qualified_integration.py"
    if hashlib.sha256(path.read_bytes()).hexdigest() != MONITOR_HELPER_SHA256:
        raise RuntimeError("frozen observation helper source changed")
    spec = importlib.util.spec_from_file_location("_posebusters_observed_shared", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("observation helper cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = _load_shared()
helper = core.load_helpers(ROOT)
require, equal = core.require, core.equal
EXECUTION_SOURCE = core.EXECUTION_SOURCE
BUNDLE_SHA256, CASE_ID, MODES = core.BUNDLE_SHA256, core.CASE_ID, core.MODES
HOST_SLOTS = (1, 2)
LIMITS = {"case_controller_wall_seconds": 2400, "probe_wall_seconds": 90,
          "rss_bytes": 6 * 1024**3, "log_bytes": 8 * 1024**2, "rss_sampling_seconds": .25}
PATH_ARGUMENTS = ("launcher_root", "execution_root", "python", "protocol", "input_root", "runtime_root", "output_root")
VALUE_ARGUMENTS = ("protocol_sha256", "bundle_sha256", "launcher_workflow_sha", "host_slot")


def validate_protocol(value):
    equal(value["schema_id"], PROTOCOL_SCHEMA, "observed protocol schema differs")
    equal(value["execution_source"], EXECUTION_SOURCE, "observed protocol source differs")
    equal(value["input_bundle_sha256"], BUNDLE_SHA256, "observed protocol input differs")
    equal([value["case_id"], value["stage"], value["required_modes"], value["host_slots"]],
          [CASE_ID, "pipeline", list(MODES), list(HOST_SLOTS)], "observed protocol scope differs")
    require(value["capability_request"] is None, "only prospective native capability is allowed")
    equal(value["limits"], LIMITS, "observed protocol limits differ")
    selection = value["host_selection"]
    equal({key: selection[key] for key in ("batches", "slots_per_batch", "cpu_model_eligibility_filter",
          "outcome_dependent_selection", "retry_on_scientific_failure")},
          {"batches": 1, "slots_per_batch": 2, "cpu_model_eligibility_filter": False,
           "outcome_dependent_selection": False, "retry_on_scientific_failure": False}, "host selection differs")
    environment = value["numerical_environment"]
    require(type(environment) is dict and "ATEN_CPU_CAPABILITY" not in environment
            and all(type(key) is str and type(item) is str for key, item in environment.items()),
            "invalid prospective native environment")
    equal(helper.numerical_environment(environment), environment, "unknown numerical environment key")
    pilot = value["pilot_evidence"]
    equal([pilot["run_id"], pilot["scope"], pilot["status"], pilot["source"],
           pilot["expected_case_stage_count"], pilot["observed_case_stage_count"], pilot["expected_worker_count"]],
          ["41798394302", "pilot", "success", EXECUTION_SOURCE, 2, 2, 6], "retained pilot evidence differs")
    for key in ("changes_to_frozen_scientific_gates", "changes_to_old_qualified_profile", "scientific_promotion",
                "performance_promotion", "product_promotion", "commercial_promotion", "cpu_cause_proven",
                "docking_accuracy_improved", "full_31_case_stage_integration_rerun"):
        require(value["claim_scope"][key] is False, "unsupported promotion: " + key)
    require(value["claim_scope"]["single_case_observed_host_diagnostic"] is True, "single-case scope missing")


def load_protocol(path, expected_sha256):
    equal(expected_sha256, PROTOCOL_SHA256, "requested protocol is not the prospective frozen protocol")
    equal(core.digest_file(path), expected_sha256, "prospective protocol file bytes differ")
    value = core.read_json(path)
    validate_protocol(value)
    return value


def source_context(args, controller):
    require(Path(__file__).resolve() == args.launcher_root / "tools/run_posebusters_observed_integration.py",
            "observed launcher does not belong to requested checkout")
    require(args.launcher_root != args.execution_root, "launcher and execution checkout must differ")
    launcher = helper.git_identity(args.launcher_root)
    equal(launcher["commit"], args.launcher_workflow_sha, "actual launcher Git HEAD differs from workflow SHA")
    equal(os.environ.get("GITHUB_SHA"), args.launcher_workflow_sha, "parent workflow SHA was replaced")
    equal(helper.git_identity(args.execution_root), {key: EXECUTION_SOURCE[key] for key in ("commit", "tree")},
          "actual execution Git source differs")
    equal(controller.digest(controller.PROTOCOL), EXECUTION_SOURCE["protocol_sha256"], "original protocol differs")
    monitor_path = args.launcher_root / "tools/run_posebusters_qualified_integration.py"
    cpu_path = args.launcher_root / "tools/run_posebusters_cpu_diagnostic.py"
    equal(core.digest_file(monitor_path), MONITOR_HELPER_SHA256, "frozen monitor source changed")
    equal(core.digest_file(cpu_path), core.HELPER_SHA256, "frozen CPU utility source changed")
    return {"launcher_source": launcher, "execution_source": EXECUTION_SOURCE,
            "launcher_workflow_sha": args.launcher_workflow_sha,
            "launcher_file": helper.descriptor(Path(__file__).resolve()),
            "monitor_helper_file": helper.descriptor(monitor_path), "cpu_helper_file": helper.descriptor(cpu_path)}


def validate_native_probe(value, directory, *, args, controller, bundle, source, environment):
    equal(core.read_json(directory / "probe.json"), value, "probe raw document differs")
    equal(value["source"], bundle["source"], "probe frozen source differs")
    equal(value["launcher_source"], source["launcher_source"], "probe launcher source differs")
    equal(value["launcher_workflow_sha"], args.launcher_workflow_sha, "probe workflow binding differs")
    equal(value["execution_github_sha"], EXECUTION_SOURCE["commit"], "probe actual child source differs")
    equal(value["launcher_file"], source["cpu_helper_file"], "probe utility source differs")
    require(value["status"] == "success" and value["process_role"] == "same_environment_sibling_probe"
            and value["worker_cpu_capability_directly_observed"] is False, "probe scope differs")
    require(value["parent_pid"] == os.getpid() and type(value["pid"]) is int and value["pid"] > 0,
            "probe parent/PID differs")
    equal(value["numerical_environment"], environment, "probe native numerical environment differs")
    equal(value["python"], helper.descriptor(args.python), "probe Python executable differs")
    equal([value["python_version"], value["torch_version"]], ["3.10.22", "2.6.0+cpu"], "probe runtime differs")
    require(type(value["torch_cpu_capability"]) is str and value["torch_cpu_capability"], "missing native capability observation")
    equal(value["environment"], helper.descriptor(directory / "environment.json"), "probe environment file differs")
    controller.validate_environment(core.read_json(directory / "environment.json"), bundle=bundle)
    require(core.library_projection(value["mapped_shared_libraries"]), "probe library observations missing")


def record_original_assessment(controller, directory, summary, *, bundle, selected):
    """Call the real strict assessor even for a failed original case summary."""
    try:
        assessment = controller.assess_case(directory, summary, selected=selected, bundle=bundle,
                                            bundle_sha256=BUNDLE_SHA256)
    except Exception as exc:
        return {"passed": False, "error_type": type(exc).__name__, "error": str(exc)}
    equal(assessment, summary.get("assessment"), "original recorded assessment differs from raw revalidation")
    return {"passed": True, "assessment": assessment}


def decide_status(*, original_returncode, original_status, assessment_passed, collection_complete):
    require(type(original_returncode) is int and original_returncode in (0, 1), "original case exit is incomplete")
    require(type(assessment_passed) is bool and type(collection_complete) is bool, "invalid completion decision")
    equal(original_status, "success" if original_returncode == 0 else "failed", "original process/status disagree")
    if not collection_complete:
        return "incomplete"
    if original_returncode == 0:
        require(assessment_passed, "original success did not pass raw strict reassessment")
        return "success"
    require(not assessment_passed, "failed original case unexpectedly passed strict reassessment")
    return "failed"


def validate_original_processes(controller, directory, summary, *, args, commands):
    controller.verify_signed(summary, "summary_sha256", "observed original case summary")
    equal({key: summary[key] for key in ("schema_id", "case_id", "stage", "source", "bundle_sha256", "protocol_sha256")},
          {"schema_id": controller.SCHEMA, "case_id": CASE_ID, "stage": "pipeline", "source": EXECUTION_SOURCE,
           "bundle_sha256": BUNDLE_SHA256, "protocol_sha256": EXECUTION_SOURCE["protocol_sha256"]}, "original case identity differs")
    require(summary["cleanup_complete"] is True, "original descendant cleanup is incomplete")
    observations, order = summary["observations"], controller.mode_order(CASE_ID, "pipeline")
    require(type(observations) is list and len(observations) == 3, "missing/duplicate original mode observation")
    expected_context = {"python_executable": str(args.python), "input_root": str(args.input_root),
                        "runtime_root": str(args.runtime_root), "output_root": str(directory),
                        "working_directory": str(args.execution_root)}
    equal(summary["execution_context"], expected_context, "original execution context differs")
    results, receipts, identities = {}, {}, []
    for slot, (item, mode) in enumerate(zip(observations, order, strict=True)):
        relative = f"worker-{slot}-{mode}"
        equal([item["slot"], item["mode"], item["worker_directory"]], [slot, mode, relative], "original mode order differs")
        equal(item["execution"]["relative_path"], relative + "/process-execution.json", "original receipt path differs")
        require(type(item["result"]) is dict, "original worker result is missing")
        equal(item["result"]["relative_path"], relative + "/result.json", "original result path differs")
        receipt = controller.read_document(directory, item["execution"])
        result = controller.read_document(directory, item["result"])
        worker_root = core.safe_path(directory, relative)
        helper.validate_process(controller, worker_root, receipt, controller.PROTOCOL["wall_limit_seconds"]["pipeline"], commands[mode])
        require(receipt["termination"] == "exited" and type(receipt["returncode"]) is int
                and receipt["returncode"] in (0, 1), "original worker did not finish")
        equal(item["process_gate_passed"], controller.common.execution_ok(receipt), "original process gate receipt differs")
        controller.verify_signed(result, "result_sha256", "observed original worker result")
        equal({key: result[key] for key in ("schema_id", "case_id", "stage", "mode", "source", "bundle_sha256", "protocol_sha256")},
              {"schema_id": controller.SCHEMA, "case_id": CASE_ID, "stage": "pipeline", "mode": mode,
               "source": EXECUTION_SOURCE, "bundle_sha256": BUNDLE_SHA256,
               "protocol_sha256": EXECUTION_SOURCE["protocol_sha256"]}, "original worker identity differs")
        equal(result["status"], "success" if receipt["returncode"] == 0 else "failed", "original worker process/status disagree")
        equal(result["actual_argv"], commands[mode], "original worker argv differs")
        equal(result["parent_pid"], summary["controller_pid"], "original worker parent differs")
        equal(result["node"], summary["node"], "original worker node differs")
        equal(result["working_directory"], str(args.execution_root), "original worker cwd differs")
        require(type(result["pid"]) is int and result["pid"] > 0, "invalid original worker PID")
        identities.append(result["pid"])
        results[mode], receipts[mode] = result, receipt
    require(len(set(identities)) == 3, "original workers did not use distinct fresh PIDs")
    return results, receipts


def validate_raw_collection(controller, directory, summary, results, *, bundle, selected):
    """Bind completed raw pipelines without admitting their failed science gates."""
    output = {}
    for item in summary["observations"]:
        mode, result = item["mode"], results[item["mode"]]
        worker = core.safe_path(directory, item["worker_directory"])
        equal(result["source_snapshot_sha256"], bundle["source_snapshot_sha256"], "worker source snapshot differs")
        equal(result["evaluator_identity"], bundle["evaluator_identities"][mode], "worker evaluator differs")
        if result["status"] == "failed":
            require(result.get("error_type") == "ReplayProtocolError" and result.get("error") in helper.STRICT_FAILURES,
                    "worker failure is not a completed known strict scientific failure")
            require("runner_call_ns" not in result, "failed runner timer must not be invented")
        else:
            # A different mode may have failed before assess_case reached this
            # worker. Revalidate every claimed success with the original gate.
            controller.validate_worker(worker, result, selected=selected, bundle=bundle,
                bundle_sha256=BUNDLE_SHA256, stage="pipeline", mode=mode, actual_argv=result["actual_argv"])
        for item_descriptor in result["files"].values():
            controller.bound_file(worker, item_descriptor)
        equal(result["files"]["full_report"]["relative_path"], "full-report.json", "raw report path differs")
        report = controller.read_document(worker, result["files"]["full_report"])
        controller.validate_report(report, selected=selected, bundle=bundle, mode=mode)
        equal(report["record_count"], 64, "completed pipeline does not retain all 64 evaluations")
        row = core.read_json(worker / "scientific-row.json")
        equal([row["case_id"], row["status"]], [CASE_ID, "success"], "fresh scientific row was not completed")
        controller.scientific_projection(row)  # Validate the original projection shape; no historical relabeling.
        poses = core.safe_path(worker, "poses/" + CASE_ID + ".sdf")
        pose_records = controller.inputs.frozen.split_sdf_records(poses.read_bytes())
        require(len(pose_records) == 5, "completed Top5 raw output is missing")
        equal([hashlib.sha256(record).hexdigest() for record in pose_records], row["pose_artifact_sha256s"],
              "retained Top5 records differ from the actual scientific row")
        context = result["final_context"]
        equal({key: context[key] for key in ("case_id", "mode", "evaluator_identity", "closed", "bust_calls",
              "record_evaluations", "full_reports_observed", "input_immutability_verified_batches")},
              {"case_id": CASE_ID, "mode": mode, "evaluator_identity": bundle["evaluator_identities"][mode],
               "closed": True, "bust_calls": 1, "record_evaluations": 64, "full_reports_observed": 1,
               "input_immutability_verified_batches": 1}, "completed evaluator context differs")
        observation = result["final_observation"]
        equal(observation["evaluation_cache"], {"cached_records": 64, "evaluation_calls": 1, "reused_records": 5},
              "completed original P1 cache observations differ")
        require(observation["healthy"] is True and observation["incomplete_stages"] == [], "pipeline observation is incomplete")
        identity = controller.journal_identity(source=bundle["source"], bundle_sha256=BUNDLE_SHA256,
            case_id=CASE_ID, stage="pipeline", mode=mode, evaluator_identity=result["evaluator_identity"],
            seed=selected["case"]["frozen_case_seed"], actual_argv=result["actual_argv"])
        events, journal = controller.verify_journal(worker / "journal", expected_identity=identity)
        lineage = controller.lineage.validate_observation_events(events, case_id=CASE_ID, canonical_row=row)
        equal(lineage["evaluator_identity"], result["evaluator_identity"], "raw lineage evaluator differs")
        snapshots = [event["details"]["proposal_index"] for event in events if event.get("stage") == "refinement_selected"]
        equal(snapshots, list(range(64)), "pipeline lacks all 64 final coordinate snapshots")
        raw_events = [event for event in events if event.get("stage") == "raw_full_report"]
        equal(raw_events, [{"stage": "raw_full_report", "phase": "snapshot",
                          "details": {"file": result["files"]["full_report"]}}], "raw report journal binding differs")
        if result["status"] == "failed":
            equal(events[-1], {"stage": "worker_failure", "phase": "error",
                  "details": {"exception_type": result["error_type"], "message": result["error"]}}, "strict failure journal differs")
        output[mode] = {"full_report": core.descriptor(worker, worker / "full-report.json"),
            "scientific_row": core.descriptor(worker, worker / "scientific-row.json"),
            "top5": core.descriptor(worker, poses), "journal": journal, "lineage": lineage, "evaluated_records": 64,
            "strict_scientific_admission": result["status"] == "success"}
    return output


def validate_observed_processes(observed, *, summary, results, commands, command, before, environment):
    require(observed["errors"] == [] and observed["sampling_seconds"] == .25
            and observed["worker_cpu_capability_directly_observed"] is False, "external process observation is incomplete")
    equal(sorted(observed["records"]), sorted(["case_controller", *MODES]), "missing/duplicate observed process")
    parent = observed["records"]["case_controller"]
    require(parent["identity"]["parent_pid"] == observed["observer_procfs_pid"]
            and parent["identity"]["local_pid"] == summary["controller_pid"], "observed controller PID binding differs")
    identities, libraries = [], {}
    for role, row in observed["records"].items():
        require(type(row["samples"]) is int and row["samples"] >= 2, "insufficient actual process samples")
        equal(row["argv"], command if role == "case_controller" else commands[role], "observed process argv differs")
        equal(row["cwd"], summary["execution_context"]["working_directory"], "observed process cwd differs")
        equal(row["pythonpath"], row["cwd"], "observed process import path differs")
        equal(row["execution_github_sha"], EXECUTION_SOURCE["commit"], "observed process source differs")
        equal(row["numerical_environment"], environment, "observed native numerical environment differs")
        equal(row["affinity"], before["cpu"]["affinity"], "observed process affinity differs within host")
        equal({key: row["python_binary"][key] for key in ("size_bytes", "sha256")},
              {key: before["python"][key] for key in ("size_bytes", "sha256")}, "observed Python binary differs")
        for stamp in (row["first"], row["last"]):
            equal(stamp["maps_sha256"], hashlib.sha256(stamp["maps"].encode()).hexdigest(), "raw process maps hash differs")
        require(row["first"]["monotonic_ns"] < row["last"]["monotonic_ns"], "empty process observation interval")
        rows = core.library_projection(row["mapped_shared_libraries"])
        require(rows, "mapped library observations missing")
        libraries[role] = rows
        if role != "case_controller":
            result = results[role]
            require(row["identity"]["parent_pid"] == parent["identity"]["pid"]
                    and row["identity"]["local_pid"] == result["pid"]
                    and result["parent_pid"] == parent["identity"]["local_pid"], "observed worker PID binding differs")
            identities.append((row["identity"]["pid"], row["identity"]["start_ticks"]))
    require(len(set(identities)) == 3, "observed workers are not distinct processes")
    # Sampling may expose different transient subsets. Compare shared observed
    # paths; do not invent coverage for a mapping that was never observed.
    known = {}
    for rows in libraries.values():
        for row in rows:
            identity = {key: row[key] for key in ("size_bytes", "sha256")}
            if row["path"] in known:
                equal(identity, known[row["path"]], "mapped library bytes changed within host")
            known[row["path"]] = identity
    return {"observed_paths_per_process": {role: len(rows) for role, rows in libraries.items()},
            "union_observed_paths": len(known), "shared_observed_bytes_stable": True,
            "scope": "sampled mappings only; absence is not proof that a library was unused"}


def inventory(directory):
    files = sorted(path for path in directory.rglob("*") if path.is_file() or path.is_symlink())
    files = [path for path in files if path != directory / "observed-result.json"]
    require(len(files) <= core.MAX_EVIDENCE_FILES, "evidence file bound exceeded")
    rows = [core.descriptor(directory, path) for path in files]
    require(sum(row["size_bytes"] for row in rows) <= core.MAX_EVIDENCE_BYTES, "evidence byte bound exceeded")
    return rows


def normalize_arguments(args):
    for field in PATH_ARGUMENTS:
        path = Path(getattr(args, field)).expanduser().absolute()
        if field != "python":
            require(path == path.resolve(), "argument path traverses a symlink: " + field)
        setattr(args, field, path)
    equal(args.bundle_sha256, BUNDLE_SHA256, "requested input bundle differs")
    require(type(args.host_slot) is int and args.host_slot in HOST_SLOTS, "undeclared host slot")
    require(not args.launcher_root.is_relative_to(args.execution_root)
            and not args.execution_root.is_relative_to(args.launcher_root), "source checkouts must not overlap")
    for root in (args.launcher_root, args.execution_root, args.input_root, args.runtime_root):
        require(not args.output_root.is_relative_to(root) and not root.is_relative_to(args.output_root),
                "outputs must not overlap source, input or runtime roots")


def run(args):
    normalize_arguments(args)
    require(not args.output_root.exists(), "observed output directory must be fresh")
    args.output_root.mkdir(parents=True)
    started = time.monotonic()
    report = {"schema_id": SCHEMA, "status": "incomplete", "diagnostic_collection_complete": False,
        "scientific_success": False, "case_started": False, "host_slot": args.host_slot,
        "case_id": CASE_ID, "stage": "pipeline", "required_modes": list(MODES), "limits": LIMITS,
        "protocol_file_sha256": PROTOCOL_SHA256, "input_bundle_sha256": BUNDLE_SHA256,
        "actual_argv": list(sys.orig_argv), "arguments": {key: str(getattr(args, key)) for key in PATH_ARGUMENTS},
        "job": {key: os.environ.get(key) for key in ("GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_JOB")},
        "checks": [], "worker_cpu_capability_directly_observed": False}
    report["arguments"].update({key: getattr(args, key) for key in VALUE_ARGUMENTS})
    primary_error = None

    def checkpoint():
        report["elapsed_seconds"] = time.monotonic() - started
        core.atomic_json(args.output_root / "progress.json", core.signed(report))

    try:
        protocol = load_protocol(args.protocol, args.protocol_sha256)
        controller = helper.frozen_controller(args.execution_root)
        source = source_context(args, controller)
        report.update(source)
        report.update(experiment_id=protocol["experiment_id"], pilot_evidence=protocol["pilot_evidence"],
                      old_runs_preserved=protocol["old_runs_preserved"], claim_scope=protocol["claim_scope"])
        (args.output_root / "bound-protocol.json").write_bytes(args.protocol.read_bytes())
        bundle, manifest = controller.load_bundle(args.input_root, BUNDLE_SHA256)
        equal(bundle["source"], EXECUTION_SOURCE, "input source differs")
        selected = controller.selected_inputs(args.input_root, bundle, manifest, CASE_ID, "pipeline")
        environment = helper.condition_environment(os.environ, args.execution_root, None)
        numeric = helper.numerical_environment(environment)
        equal(numeric, protocol["numerical_environment"], "prospective native environment differs")
        core.atomic_json(args.output_root / "observed-request.json", core.signed(report))
        core.atomic_json(args.output_root / "requested-environment.json", numeric)
        before_root = args.output_root / "probe-before"
        before = helper.run_probe(args, controller, before_root, environment)
        validate_native_probe(before, before_root, args=args, controller=controller, bundle=bundle, source=source, environment=numeric)
        report["checks"].append("native-probe-before")
        report["cpu_observation"] = {"boot_id": before["cpu"]["boot_id"], "native_capability": before["torch_cpu_capability"],
                                    "affinity": before["cpu"]["affinity"], "cpus": before["cpu"]["cpus"]}
        case_root = args.output_root / "case"
        command, commands = core.case_command(args, case_root), core.worker_commands(controller, args, case_root)
        report.update(case_command=command, worker_commands=commands, case_started=True)
        checkpoint()
        monitor = core.NestedWorkerMonitor(helper, command, commands, environment, args.execution_root)
        monitor.start()

        def supervise_case():
            return controller.isolation.supervise(command, args.output_root / "case-controller-process",
                controller.isolation.Limits(LIMITS["case_controller_wall_seconds"], rss_bytes=LIMITS["rss_bytes"],
                                            log_bytes=LIMITS["log_bytes"]), cwd=args.execution_root, env=environment)

        def finish_monitor():
            value = monitor.finish()
            core.atomic_json(args.output_root / "actual-process-observation.json", value)
            return value

        process, observed = helper.supervise_and_finalize(supervise_case, finish_monitor)
        helper.validate_process(controller, args.output_root / "case-controller-process", process,
                                LIMITS["case_controller_wall_seconds"], command)
        require(process["termination"] == "exited" and type(process["returncode"]) is int
                and process["returncode"] in (0, 1), "original case did not finish")
        summary = core.read_json(case_root / "case-summary.json")
        controller.verify_signed(summary, "summary_sha256", "original case summary")
        report["original_case_status"] = summary["status"]
        report["original_returncode"] = process["returncode"]
        report["original_error"] = {key: summary.get(key) for key in ("error_type", "error")}
        assessment = record_original_assessment(controller, case_root, summary, bundle=bundle, selected=selected)
        core.atomic_json(args.output_root / "original-assessment.json", assessment)
        report["original_assessment"] = assessment
        if process["returncode"] == 1:
            require(summary.get("error_type") == "ReplayProtocolError"
                    and assessment.get("error_type") == "ReplayProtocolError",
                    "original case failure is not an authentic strict scientific rejection")
            equal({key: summary.get(key) for key in ("error_type", "error")},
                  {key: assessment.get(key) for key in ("error_type", "error")},
                  "original case failure differs from raw strict reassessment")
        checkpoint()
        results, receipts = validate_original_processes(controller, case_root, summary, args=args, commands=commands)
        report["workers"] = {mode: {"status": result["status"], "error_type": result.get("error_type"),
            "error": result.get("error"), "returncode": receipts[mode]["returncode"],
            "cleanup_complete": receipts[mode]["cleanup_complete"]} for mode, result in results.items()}
        report["mapping_coverage"] = validate_observed_processes(observed, summary=summary, results=results,
            commands=commands, command=command, before=before, environment=numeric)
        report["raw_collection"] = validate_raw_collection(controller, case_root, summary, results, bundle=bundle, selected=selected)
        report["checks"].append("original-three-mode-processes")
        checkpoint()
        after_root = args.output_root / "probe-after"
        after = helper.run_probe(args, controller, after_root, environment)
        validate_native_probe(after, after_root, args=args, controller=controller, bundle=bundle, source=source, environment=numeric)
        helper.before_after_identity(before, after)
        equal(source_context(args, controller), source, "source changed during observed execution")
        controller.load_bundle(args.input_root, BUNDLE_SHA256)
        load_protocol(args.protocol, args.protocol_sha256)
        report["checks"].append("native-probe-after-and-stability")
        status = decide_status(original_returncode=process["returncode"], original_status=summary["status"],
                               assessment_passed=assessment["passed"], collection_complete=True)
        report.update(status=status, diagnostic_collection_complete=True, scientific_success=status == "success")
    except Exception as exc:
        primary_error = exc
        report.update(status="incomplete", diagnostic_collection_complete=False, scientific_success=False,
                      error_type=type(exc).__name__, error=str(exc))
    finally:
        try:
            checkpoint()
            report["files"] = inventory(args.output_root)
            core.atomic_json(args.output_root / "observed-result.json", core.signed(report))
        except Exception as finalization_error:
            if primary_error is not None:
                raise primary_error from finalization_error
            raise
    print(json.dumps({key: report[key] for key in ("host_slot", "status", "diagnostic_collection_complete", "scientific_success")}))
    return 0 if report["status"] == "success" else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    child = parser.add_subparsers(dest="command", required=True).add_parser("run")
    for field in PATH_ARGUMENTS:
        child.add_argument("--" + field.replace("_", "-"), type=Path, required=True)
    for field in VALUE_ARGUMENTS[:-1]:
        child.add_argument("--" + field.replace("_", "-"), required=True)
    child.add_argument("--host-slot", type=int, choices=HOST_SLOTS, required=True)
    args = parser.parse_args(argv)
    try:
        return run(args)
    except Exception as exc:
        print(json.dumps({"status": "incomplete", "diagnostic_collection_complete": False, "scientific_success": False,
                          "error_type": type(exc).__name__, "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
