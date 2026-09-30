"""Profile the existing trajectory integrity guard without evaluating an objective.

One warm-up and nine measured guards are fixed before object reconstruction.
This is an integrity microprofile, not an optimizer run or a speedup comparison.
"""
from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path
import resource
import statistics
import sys
import time

import torch

from docs.research.human_5ht6_d3_complex import feasible_trajectory_development_experiment as runner


PROTOCOL = {
    "schema_id": "pr49_trajectory_integrity_profile_protocol/1.0.0",
    "warmup_guard_calls": 1,
    "measured_guard_calls": 9,
    "stage_order": ["native_source_manifest", "runtime_and_protocol", "input_source_references",
                    "published_result_references", "published_plan_explicit",
                    "original_ligand_canonical", "fixed_receptor_intact"],
    "full_guard": "existing feasible_step_core._Run.guard with existing integrity operations",
    "result_reference_scope": "plan.json only, matching the completed trajectory phase",
    "file_validation": "fresh full source enumeration and content hashing every call; no stat cache",
    "warmup_policy": "one explicit warm-up; OS page-cache state uncontrolled; no cold-cache claim",
    "timing_policy": "disjoint integrity stages nested inside full guard; never add enclosing and nested scopes",
    "reconstruction_and_final_verification": "separate setup/postcheck, excluded from nine guard measurements",
    "optimizer_calls": 0,
    "objective_calls": 0,
    "molecular_force_calls": 0,
    "geometry_evaluations": 0,
    "solvation_calls": 0,
    "openmm_audit_calls": 0,
    "optimization_implemented": False,
    "speedup_claimed": False,
}


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _memory():
    # ru_maxrss is process-lifetime high water on Linux, not a per-stage allocation.
    result = {"peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            result["current_rss_bytes"] = int(line.split()[1]) * 1024
            break
    return result


def _stats(values):
    return {"count": len(values), "minimum": min(values), "median": statistics.median(values),
            "mean": statistics.mean(values), "maximum": max(values), "sum": sum(values)}


def profile(plan_path: Path, output: Path):
    common = runner.common
    plan_path = plan_path.resolve(strict=True)
    plan_ref = common.reference(plan_path)
    plan = json.loads(plan_path.read_bytes())
    common.require(plan["schema_id"] == "pr49_feasible_trajectory_development_plan/1.0.0",
                   "completed_trajectory_plan_required")
    protocol_ref = common.reference(__file__)
    historical_path = plan_path.parent / "trajectory.json"
    historical_ref = common.reference(historical_path)
    historical = json.loads(historical_path.read_bytes())
    common.require(historical["source_integrity_valid"] and historical["error"] is None,
                   "intact_completed_trajectory_required")
    refs = plan["inputs_and_source_files"]
    output.mkdir(parents=True, exist_ok=False)
    declaration = {"declared_at_utc": _now(), "protocol": PROTOCOL,
                   "command": [sys.executable, "-B", *sys.argv],
                   "profile_script": protocol_ref, "historical_plan": plan_ref,
                   "historical_trajectory": historical_ref,
                   "input_and_source_references": refs,
                   "native_source_sha256": plan["native_source_sha256"],
                   "scientifically_validated": False, "product_qualified": False}
    common.write(output / "protocol.json", declaration)
    declaration_ref = common.reference(output / "protocol.json")
    phase = "same_object_reconstruction"
    samples = []
    guard = None
    try:
        setup_wall, setup_cpu = time.perf_counter(), time.process_time()
        memory_before_setup = _memory()
        common.verify_file_references(refs)
        sources = runner.source_manifest()
        common.require(sources == plan["native_source_manifest"]
                       and runner.digest(sources) == plan["native_source_sha256"], "native_source_not_identical")
        runtime = runner.runtime_identity()
        common.require(runtime == plan["runtime"], "runtime_not_identical_to_historical_run")
        common.require(runner.core.PROTOCOL == plan["protocol"], "trajectory_protocol_changed")
        request = json.loads(Path(refs["request"]["path"]).read_bytes())
        common.require(request["schema_id"] == runner.REGISTERED_REQUEST_SCHEMA
                       and request["solvation"] is None, "same_registered_dry_request_required")
        prepared = {key: value for key, value in request.items() if key != "cross_parameters"}
        prepared["schema_id"] = runner.REQUEST_SCHEMA
        _, receptor, ligand, parameters, _, solver, solvent, _, _ = runner.load_request(
            prepared, plan["native_source_sha256"])
        common.require(not parameters.constraints and solvent is None, "unconstrained_dry_inputs_required")
        common.require(solver.to_dict() == plan["input_product_solver"], "product_solver_configuration_changed")
        fixed = runner.FixedReceptorEnvironment(receptor, runner.CrossParameters.from_dict(
            runner._bound(request["cross_parameters"])))
        fixed.validate_ligand(ligand, parameters.base_parameters)
        original_identity = runner.canonical_system_sha256(ligand)
        common.require(original_identity == plan["original_ligand_sha256"], "original_ligand_identity_changed")
        common.require(ligand.coordinates[0].tolist() == historical["initial"]["coordinates_angstrom"],
                       "original_coordinates_not_identical")
        common.require(runner.canonical_system_sha256(receptor) == fixed.cross.receptor_system_sha256,
                       "original_receptor_identity_changed")
        result_refs = {"plan.json": plan_ref}
        baseline_identity = {"ligand_system_sha256": original_identity,
                             "receptor_system_sha256": fixed.cross.receptor_system_sha256,
                             "ligand_atoms": ligand.atom_count, "receptor_atoms": receptor.atom_count,
                             "same_runtime": True, "same_source_bytes": True, "same_input_bytes": True,
                             "same_original_coordinates": True, "same_product_solver": True,
                             "same_protocol": True}
        setup = {"wall_seconds": time.perf_counter() - setup_wall,
                 "cpu_seconds": time.process_time() - setup_cpu,
                 "memory_before": memory_before_setup, "memory_after": _memory()}
        active_stages = []

        def stage(name, action):
            wall, cpu = time.perf_counter(), time.process_time()
            succeeded = False
            try:
                value = action()
                succeeded = True
                return value
            finally:
                cpu_elapsed = time.process_time() - cpu
                wall_elapsed = time.perf_counter() - wall
                active_stages.append({"stage": name, "succeeded": succeeded,
                                      "wall_seconds": wall_elapsed, "cpu_seconds": cpu_elapsed})

        def intact():
            # Preserve the operations and order of runner.intact(), including both plan reads.
            stage("native_source_manifest", lambda: common.require(
                runner.source_manifest() == sources, "native_source_changed"))
            stage("runtime_and_protocol", lambda: common.require(
                runner.runtime_identity() == runtime and runner.core.PROTOCOL == plan["protocol"],
                "runtime_or_protocol_changed"))
            stage("input_source_references", lambda: common.verify_file_references(refs))
            stage("published_result_references", lambda: common.verify_file_references(result_refs))
            stage("published_plan_explicit", lambda: common.require(
                common.reference(plan_ref["path"]) == plan_ref, "published_plan_changed"))
            stage("original_ligand_canonical", lambda: common.require(
                runner.canonical_system_sha256(ligand) == original_identity, "original_ligand_mutated"))
            stage("fixed_receptor_intact", fixed.assert_intact)

        def prohibited_callback(_):
            raise AssertionError("profiling_must_not_invoke_objective_geometry_or_publication_callbacks")

        guard = runner.base_core._Run(ligand.coordinates[0], prohibited_callback,
                                     prohibited_callback, prohibited_callback, intact)
        total = PROTOCOL["warmup_guard_calls"] + PROTOCOL["measured_guard_calls"]
        for index in range(total):
            phase = "warmup_guard" if index < PROTOCOL["warmup_guard_calls"] else "measured_guard"
            active_stages.clear()
            before = _memory()
            wall, cpu = time.perf_counter(), time.process_time()
            guard.guard()
            cpu_elapsed, wall_elapsed = time.process_time() - cpu, time.perf_counter() - wall
            common.require([s["stage"] for s in active_stages] == PROTOCOL["stage_order"]
                           and all(s["succeeded"] for s in active_stages), "integrity_stage_coverage_mismatch")
            sample = {"index": index, "scope": phase, "full_guard_wall_seconds": wall_elapsed,
                      "full_guard_cpu_seconds": cpu_elapsed, "stages": list(active_stages),
                      "memory_before": before, "memory_after": _memory()}
            for metric in ("wall", "cpu"):
                subtotal = sum(row[metric + "_seconds"] for row in active_stages)
                sample["stage_" + metric + "_seconds_sum"] = subtotal
                sample["unattributed_wrapper_" + metric + "_seconds"] = sample[
                    "full_guard_" + metric + "_seconds"] - subtotal
            samples.append(sample)
        phase = "post_profile_source_and_input_verification"
        post_wall, post_cpu = time.perf_counter(), time.process_time()
        common.verify_file_references({"profile_script": protocol_ref, "declaration": declaration_ref,
                                       "historical_plan": plan_ref, "historical_trajectory": historical_ref})
        common.verify_file_references(refs)
        common.require(runner.source_manifest() == sources and runner.runtime_identity() == runtime,
                       "post_profile_source_or_runtime_changed")
        common.require(guard.integrity_error is None and guard.counters["integrity_checks"] == total
                       and guard.counters["failed_integrity_checks"] == 0, "integrity_guard_count_mismatch")
        common.require(all(guard.counters[key] == 0 for key in (
            "objective_point_attempts", "objective_calls", "completed_objective_calls", "validity_calls", "record_calls")),
            "prohibited_execution_detected")
        postcheck = {"wall_seconds": time.perf_counter() - post_wall,
                     "cpu_seconds": time.process_time() - post_cpu}
        measured = [row for row in samples if row["scope"] == "measured_guard"]
        stage_stats = {name: {metric: _stats([next(s for s in row["stages"] if s["stage"] == name)[metric]
                                             for row in measured])
                              for metric in ("wall_seconds", "cpu_seconds")}
                       for name in PROTOCOL["stage_order"]}
        full_stats = {key: _stats([row[key] for row in measured]) for key in (
            "full_guard_wall_seconds", "full_guard_cpu_seconds", "stage_wall_seconds_sum",
            "stage_cpu_seconds_sum", "unattributed_wrapper_wall_seconds", "unattributed_wrapper_cpu_seconds")}
        report = {"schema_id": "pr49_trajectory_integrity_profile/1.0.0", "passed": True,
                  "finished_at_utc": _now(), "protocol": declaration_ref,
                  "baseline_identity": baseline_identity, "runtime": runtime, "setup": setup,
                  "postcheck": postcheck, "samples": samples, "measured_full_guard": full_stats,
                  "measured_stages": stage_stats, "guard_counters": dict(guard.counters),
                  "historical_observation": {"reference": historical_ref,
                      "integrity_checks": historical["counters"]["integrity_checks"],
                      "integrity_wall_seconds": historical["counters"]["integrity_wall_seconds"],
                      "enclosing_trajectory_wall_seconds": historical["whole_wall_seconds"],
                      "current_microprofile_is_not_historical_stage_attribution": True},
                  "execution": {"integrity_guard_calls": total, "optimizer_calls": 0,
                      "objective_calls": 0, "molecular_force_calls": 0, "geometry_evaluations": 0,
                      "solvation_calls": 0, "openmm_audit_calls": 0},
                  "timing_scopes_are_nested_do_not_sum": True, "optimization_implemented": False,
                  "speedup_claimed": False, "scientifically_validated": False, "product_qualified": False,
                  "limits": ["One process, one host, nine post-warmup observations; contention and OS page cache uncontrolled.",
                      "RSS is sampled outside timed stages; peak RSS is the Linux process-lifetime high water.",
                      "The receptor stage includes require_system, canonical serialization/hash and charge validation; it is not split internally.",
                      "Guard wrapper residual includes timers/bookkeeping/original-coordinate checks and is not molecular work.",
                      "Reconstructed same canonical objects do not prove the historical process had identical allocator/cache/scheduler state.",
                      "Only existing plan inputs are referenced; no protected outcome, new molecular experiment or full repository copy."]}
        common.write(output / "profile.json", report)
        return {"passed": True, "output": str(output), "measured_guard_calls": len(measured),
                "median_full_guard_wall_seconds": full_stats["full_guard_wall_seconds"]["median"],
                "median_stage_wall_seconds": {name: value["wall_seconds"]["median"]
                                              for name, value in stage_stats.items()}}
    except Exception as exc:
        common.write(output / "failure.json", {"passed": False, "phase": phase,
            "error_type": type(exc).__name__, "error": str(exc), "completed_samples": samples,
            "guard_counters": None if guard is None else guard.counters,
            "optimizer_calls": 0, "molecular_force_calls": 0, "speedup_claimed": False})
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    torch.set_num_threads(1)
    print(json.dumps(profile(arguments.plan, arguments.output), sort_keys=True))
