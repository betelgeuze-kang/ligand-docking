"""Source-bound bounded repeated feasible descent on the original PR49 pose.

The product optimizer and its raw-force convergence criterion remain unchanged.
A feasible energy-lowering step is not force convergence or product admission.
"""
from __future__ import annotations

import argparse
import json
import hashlib
import math
from pathlib import Path
import time

import scipy
import torch

from betelgeuze_engine_v2.geometry import RadiusGraphConfig, build_compact_radius_graph
from betelgeuze_engine_v2.molecular import canonical_system_sha256, canonical_topology_sha256
from betelgeuze_engine_v2.molecular.serialization import canonical_system_json_bytes
from betelgeuze_product.reference_minimization_workflow import _bound
from betelgeuze_product.cpu_refinement_v1_2.evaluation import ExtendedEvaluator
from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import (
    CrossParameters, FixedReceptorEnvironment, FixedReceptorEvaluator, components_document,
)
from betelgeuze_product.cpu_refinement_v1_2.provenance import digest, source_manifest
from betelgeuze_product.cpu_refinement_v1_2.scoring_profile import REGISTERED_REQUEST_SCHEMA
from betelgeuze_product.cpu_refinement_v1_2.workflow import REQUEST_SCHEMA, load_request
from docs.research.human_5ht6_d3_complex import (
    feasible_trajectory_core as core, feasible_step_core as base_core,
    audit_feasible_trajectory as ledger_auditor, d3_development_experiment as common,
    constrained_development_experiment as derivative_helper,
    lbfgs_development_experiment as previous, product_geometry_audit as product_geometry,
)


def runtime_identity():
    return {**previous.runtime_identity(), "scipy_distribution": scipy.__version__}


def published_json(path, value, references):
    """Bind the intended publication before any dependent verification."""
    raw = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    expected = {"path": str(Path(path).resolve()), "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw)}
    with Path(path).open("xb") as stream:
        stream.write(raw)
    common.require(common.reference(path) == expected, "published_result_bytes_changed")
    references[Path(path).name] = expected


def capture_numerical_observation(row, energy, gradient, internal, internal_gradient, components):
    """Preserve malformed native values without bypassing the core geometry call."""
    values = {"total_energy_kcal_mol": energy, "total_gradient_kcal_mol_angstrom": gradient.tolist(),
              "internal_energy_kcal_mol": internal, "internal_gradient_kcal_mol_angstrom": internal_gradient.tolist(),
              "components": components}
    def safe(value):
        if isinstance(value, float) and not math.isfinite(value):
            return {"non_finite_float": repr(value)}
        if isinstance(value, dict):
            return {key: safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [safe(item) for item in value]
        return value
    normal = all(math.isfinite(v) for v in (energy, internal, *components.values()))
    normal = normal and all(t.dtype == torch.float64 and t.device.type == "cpu"
                            and list(t.shape) == [len(row["coordinates_angstrom"]), 3]
                            and bool(torch.isfinite(t).all()) for t in (gradient, internal_gradient))
    if normal:
        row.update(status="completed", stage="completed", **values)
    else:
        row.update(status="invalid_result", stage="objective_result", raw_result=safe(values),
                   error={"type": "InvalidNativeResult", "reason": "nonfinite_or_malformed_native_values"})


def observation_index(observations):
    """Keep chronological calls authoritative; reject inconsistent repeated states."""
    common.require(bool(observations), "native_observations_required")
    indexed, compatibility = {}, {}
    for expected, row in enumerate(observations, 1):
        common.require(type(row.get("objective_point_attempt")) is int
                       and row["objective_point_attempt"] == expected, "native_observation_order_mismatch")
        xyz = torch.tensor(row["coordinates_angstrom"], dtype=torch.float64)
        common.require(xyz.ndim == 2 and xyz.shape[1] == 3 and xyz.numel() > 0
                       and bool(torch.isfinite(xyz).all()), "native_coordinates_invalid")
        common.require(row["coordinate_bytes_sha256"]
                       == hashlib.sha256(base_core.coordinate_key(xyz.numpy())).hexdigest(),
                       "native_coordinate_binding_mismatch")
        common.require(row.get("status") in ("completed", "failed", "invalid_result"), "native_status_invalid")
        if row["status"] != "completed":
            common.require(bool(row.get("error")) and bool(row.get("stage")), "failed_native_stage_required")
            continue
        for key in ("total_gradient_kcal_mol_angstrom", "internal_gradient_kcal_mol_angstrom"):
            value = torch.tensor(row[key], dtype=torch.float64)
            common.require(value.shape == xyz.shape and bool(torch.isfinite(value).all()), "native_gradient_invalid")
        common.require(all(math.isfinite(row[k]) for k in
                           ("total_energy_kcal_mol", "internal_energy_kcal_mol")), "native_energy_invalid")
        indexed[expected] = row
        value = {"coordinates": row["coordinates_angstrom"], "energy": row["total_energy_kcal_mol"],
                 "total_gradient": row["total_gradient_kcal_mol_angstrom"],
                 "internal_energy": row["internal_energy_kcal_mol"],
                 "internal_gradient": row["internal_gradient_kcal_mol_angstrom"]}
        key = digest(value["coordinates"])
        common.require(key not in compatibility or compatibility[key] == value,
                       "repeated_native_state_disagrees")
        compatibility[key] = value
    return indexed, compatibility


def select_audit_attempts(original, retained, report, observations):
    """Include every committed accepted endpoint and a rejected/failed-geometry tail.

    The oracle separately evaluates the original for every supplied endpoint.
    Selection uses call IDs, so repeated coordinates never erase call history.
    """
    indexed, compatibility = observation_index(observations)
    common.require(1 in indexed and indexed[1]["coordinates_angstrom"] == original.tolist(),
                   "first_native_observation_not_original")
    accepted = report["accepted_objective_point_attempts"]
    common.require(type(accepted) is list and all(type(i) is int and i > 1 for i in accepted)
                   and accepted == sorted(set(accepted)), "accepted_attempt_order_invalid")
    common.require(all(i in indexed for i in accepted), "accepted_native_observation_missing")
    expected_retained = indexed[accepted[-1] if accepted else 1]["coordinates_angstrom"]
    common.require(report["source_integrity_valid"] and expected_retained == retained.tolist(),
                   "retained_not_last_published_incumbent")
    selected = list(accepted)
    last = max(indexed)
    if last not in selected:
        selected.append(last)
    return [(i, torch.tensor(indexed[i]["coordinates_angstrom"], dtype=torch.float64))
            for i in selected], compatibility


def run(request_path, geometry_path, ligand_xml, receptor_xml, output, expected_source_sha256):
    started = time.perf_counter()
    sources = source_manifest()
    common.require(digest(sources) == expected_source_sha256, "native_source_not_frozen")
    from tools.analysis import openmm_d3_numerical_audit as oracle
    refs = {name: common.reference(path) for name, path in (
        ("request", request_path), ("geometry_protocol", geometry_path), ("ligand_xml", ligand_xml),
        ("receptor_xml", receptor_xml), ("numerical_oracle", oracle.__file__), ("script", __file__),
        ("core", core.__file__), ("base_core", base_core.__file__),
        ("independent_ledger_auditor", ledger_auditor.__file__), ("derivative_helper", derivative_helper.__file__),
        ("product_geometry_adapter", product_geometry.__file__),
        ("shared_helpers", common.__file__), ("audit_helpers", previous.__file__))}
    common.require(refs["geometry_protocol"]["sha256"] == common.GEOMETRY_PROTOCOL_SHA256,
                   "geometry_protocol_changed")
    common.require(oracle.ENERGY_ABSOLUTE_TOLERANCE == 1e-8
                   and oracle.FORCE_ABSOLUTE_TOLERANCE == 1e-8, "oracle_tolerance_changed")
    request = json.loads(Path(request_path).read_bytes())
    common.require(request["schema_id"] == REGISTERED_REQUEST_SCHEMA and request["solvation"] is None,
                   "original_registered_dry_request_required")
    for name in ("ligand", "receptor", "parameters", "extensions", "cross_parameters"):
        _bound(request[name])
        refs[name] = common.reference(request[name]["path"])
        common.require(refs[name]["sha256"] == request[name]["sha256"], "input_binding_mismatch")
    common.require(refs["ligand"]["sha256"] == previous.ORIGINAL_LIGAND_FILE_SHA256,
                   "original_registered_ligand_required")
    prepared = {k: v for k, v in request.items() if k != "cross_parameters"}
    prepared["schema_id"] = REQUEST_SCHEMA
    authority, receptor, ligand, parameters, budget, solver, solvent, _, _ = load_request(
        prepared, expected_source_sha256)
    fixed = FixedReceptorEnvironment(receptor, CrossParameters.from_dict(_bound(request["cross_parameters"])))
    fixed.validate_ligand(ligand, parameters.base_parameters)
    common.require(not parameters.constraints and solvent is None, "unconstrained_dry_force_model_required")
    common.require(fixed.cross.max_internal_increase_kcal_per_mol == 5.0
                   and solver.minimization.force_tolerance_kcal_per_mol_angstrom == .001,
                   "original_product_admission_thresholds_changed")
    common.require(parameters.metadata.get("source_xml_sha256") == refs["ligand_xml"]["sha256"]
                   and fixed.cross.parameter_source_sha256 == refs["receptor_xml"]["sha256"],
                   "source_xml_binding_mismatch")
    adapter = product_geometry.ProductGeometryAudit(authority, budget, ligand)
    common.require(adapter.criteria()["pose_validity_config"]["bond_length_tolerance_angstrom"] == .15,
                   "product_bond_tolerance_changed")
    geometry_protocol = json.loads(Path(geometry_path).read_bytes())
    center = torch.tensor(request["pocket"]["center_angstrom"], dtype=torch.float64)
    common.require(request["pocket"]["radius_angstrom"]
                   == geometry_protocol["pocket_all_heavy_maximum_radius_angstrom"], "pocket_radius_changed")
    def placement_geometry(xyz):
        return common.geometry_observation(xyz, [a.element for a in ligand.atoms], receptor.coordinates[0],
                                           [a.element for a in receptor.atoms], center, geometry_protocol)
    baseline = adapter.baseline_report()
    initial_geometry = placement_geometry(ligand.coordinates[0])
    common.require(baseline["passed"] and initial_geometry["passed"], "initial_geometry_ineligible")
    runtime, protocol = runtime_identity(), dict(core.PROTOCOL)
    original_identity = canonical_system_sha256(ligand)
    plan_ref = None
    result_refs = {}
    def intact():
        common.require(source_manifest() == sources, "native_source_changed")
        common.require(runtime_identity() == runtime and core.PROTOCOL == protocol, "runtime_or_protocol_changed")
        common.verify_file_references(refs)
        common.verify_file_references(result_refs)
        if plan_ref is not None:
            common.require(common.reference(plan_ref["path"]) == plan_ref, "published_plan_changed")
        common.require(canonical_system_sha256(ligand) == original_identity, "original_ligand_mutated")
        fixed.assert_intact()
    intact()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    plan = {
        "schema_id": "pr49_feasible_trajectory_development_plan/1.0.0", "protocol": protocol,
        "inputs_and_source_files": refs, "native_source_sha256": expected_source_sha256,
        "native_source_manifest": sources, "runtime": runtime, "input_product_solver": solver.to_dict(),
        "original_ligand_sha256": original_identity, "initial_product_geometry": baseline,
        "initial_placement_geometry": initial_geometry,
        "objective": "unchanged_unscaled_internal_plus_cross_energy",
        "constraints": "exact_internal_increase_at_most_5_and_each_original_bond_change_at_most_0.15",
        "step_policy": "current_incumbent_negative_gradient_ray_each_step; alpha=0.05*2^-j_A_j0..15; current_Armijo_c1=1e-4; immutable_original_strain_and_bonds",
        "geometry_scope": "full_product_and_six_placement_checks_on_every_completed_native_trial_and_retained_state",
        "selection": "first_eligible_per_step; publish_before_committing_incumbent; ordinary_failure_retains_last_committed_state; integrity_failure_revokes_selection",
        "stationarity_scope": "raw_atom_force_at_most_0.001_reported_separately; no_KKT_or_small_step_convergence_claim",
        "budget": {"native_point_attempts": 129, "maximum_accepted_steps": 32, "backtracking_trials_per_step": 16,
                   "combined_evaluator_calls": 129, "additional_internal_evaluator_calls": 129,
                   "oracle_combined_snapshots_separate_maximum": 66},
        "cost_accounting": "combined evaluator contains one internal and one cross call; extra internal call recovers strain derivative; nested calls are not independent total cost",
        "numerical_states": ["original_paired_with_each_selected_call", "all_successfully_published_accepted_endpoints",
                             "last_completed_native_objective_even_if_later_geometry_fails"],
        "original_product_raw_force_threshold_remains": .001,
        "same_budget_algorithm_comparison": False, "new_training_or_protected_outcomes_used": False,
        "scientifically_validated": False, "product_qualified": False,
        "timing_scope": "enclosing development run excludes upstream preparation and human work; CPU contention uncontrolled",
        "setup_wall_seconds": time.perf_counter() - started,
    }
    published_json(output / "plan.json", plan, result_refs)
    plan_ref = common.reference(output / "plan.json")
    evaluator = FixedReceptorEvaluator(ExtendedEvaluator(parameters, solvent), fixed)
    costs = {name: {"calls": 0, "failed_calls": 0, "wall_seconds": 0.0}
             for name in ("graph", "combined_force", "additional_internal_force", "geometry")}
    observations, oracle_costs, phase_times = [], [], {}
    def measured(name, call):
        counter = costs[name]
        counter["calls"] += 1
        scope = time.perf_counter()
        try:
            return call()
        except Exception:
            counter["failed_calls"] += 1
            raise
        finally:
            counter["wall_seconds"] += time.perf_counter() - scope
    def objective(xyz):
        observation = {"objective_point_attempt": len(observations) + 1,
                       "coordinates_angstrom": xyz.tolist(),
                       "coordinate_bytes_sha256": hashlib.sha256(base_core.coordinate_key(xyz.numpy())).hexdigest(),
                       "status": "started", "stage": "state"}
        observations.append(observation)
        try:
            state = ligand.with_coordinates(xyz.unsqueeze(0), operation="research_feasible_trajectory_v1")
            observation["stage"] = "graph"
            graph = measured("graph", lambda: build_compact_radius_graph(state.coordinates, RadiusGraphConfig(
                cutoff_angstrom=parameters.base_parameters.cutoff_angstrom,
                max_neighbors=solver.minimization.max_neighbors,
                max_atoms_per_cell=solver.minimization.max_atoms_per_cell)))
            observation["stage"] = "combined_force"
            value = measured("combined_force", lambda: evaluator.evaluate(state, graph))
            observation["stage"] = "additional_internal_force"
            internal = measured("additional_internal_force", lambda: evaluator.internal.evaluate(state, graph))
            energy, internal_energy = float(value.term.energy[0]), float(internal.term.energy[0])
            common.require(internal_energy == float(value.component_energies["ligand_internal"][0]),
                           "internal_energy_evaluations_disagree")
            gradient, internal_gradient = -value.term.forces[0], -internal.term.forces[0]
            components = components_document(value)
            capture_numerical_observation(observation, energy, gradient, internal_energy, internal_gradient, components)
            return energy, gradient, internal_energy, internal_gradient, components
        except Exception as exc:
            observation.update(status="failed", error={"type": type(exc).__name__, "reason": str(exc)})
            raise
    def validity(xyz):
        def evaluate():
            binding = {"plan_sha256": plan_ref["sha256"], "coordinates_sha256": digest(xyz.tolist()),
                       "role": "actual_research_geometry_observation", "native_source_sha256": expected_source_sha256}
            product = adapter.evaluate_coordinates(xyz, refiner_id="research.feasible_trajectory",
                refiner_version="1.0.0", refinement_receipt_sha256=digest(binding))
            geometry = placement_geometry(xyz)
            return {"valid": product["passed"] and geometry["passed"], "complete": product["complete"],
                    "product": product, "placement": geometry, "research_binding": binding}
        return measured("geometry", evaluate)
    phase = "bounded_feasible_trajectory"
    try:
        with (output / "trials.jsonl").open("x") as stream:
            def record(row):
                stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
                stream.flush()
            scope = time.perf_counter()
            xyz, step = core.feasible_armijo_trajectory(ligand.coordinates[0],
                tuple((b.atom_i, b.atom_j) for b in ligand.bonds), objective, validity, record, intact=intact)
            phase_times[phase] = time.perf_counter() - scope
        result_refs["trials.jsonl"] = common.reference(output / "trials.jsonl")
        published_json(output / "trajectory.json", step, result_refs)
        published_json(output / "objective-observations.json", observations, result_refs)
        intact()
        common.require(step["source_integrity_valid"], "recorded_integrity_failure_is_fatal")
        published_json(output / "final-coordinates.json", {"coordinates_angstrom": xyz.tolist()}, result_refs)
        final = ligand.with_coordinates(xyz.unsqueeze(0), operation="research_feasible_trajectory_v1")
        common.require(canonical_topology_sha256(final) == canonical_topology_sha256(ligand), "topology_changed")
        final_bytes = canonical_system_json_bytes(final)
        with (output / "final-canonical.json").open("xb") as stream:
            stream.write(final_bytes)
        result_refs["final-canonical.json"] = {"path": str((output / "final-canonical.json").resolve()),
            "sha256": hashlib.sha256(final_bytes).hexdigest(), "bytes": len(final_bytes)}
        intact()
        selected_calls, observation_map = select_audit_attempts(ligand.coordinates[0], xyz, step, observations)
        phase = "independent_trajectory_ledger_audit"
        scope = time.perf_counter()
        ledger = ledger_auditor.audit_trajectory(step, ligand.coordinates[0].tolist(),
            tuple((b.atom_i, b.atom_j) for b in ligand.bonds),
            events=[json.loads(line) for line in (output / "trials.jsonl").read_text().splitlines()],
            native_observations=observations, expected_protocol=protocol)
        phase_times[phase] = time.perf_counter() - scope
        published_json(output / "trajectory-audit.json", ledger, result_refs)
        common.require(ledger["passed"], "independent_trajectory_ledger_audit_failed")
        intact()
        audit_paths = []
        for attempt, audit_xyz in selected_calls:
            name = "native-attempt-" + str(attempt) + "-coordinates.json"
            published_json(output / name, {"coordinates_angstrom": audit_xyz.tolist()}, result_refs)
            audit_paths.append(("numerical-original-attempt-" + str(attempt), output / name, audit_xyz))
        audits, derivative_checks = [], []
        for phase, path, supplied in audit_paths:
            intact()
            coordinate_ref = common.reference(path)
            cost = {"phase": phase}
            oracle_costs.append(cost)
            audit = previous.measured_audit(oracle, cost, Path(request_path), Path(ligand_xml), Path(receptor_xml),
                                           final_coordinates_path=path, perturbations=0)
            phase_times[phase] = cost["whole_audit_wall_seconds"]
            published_json(output / (phase + ".json"), audit, result_refs)
            published_json(output / (phase + "-cost.json"), cost, result_refs)
            intact()
            common.verify_numerical_receipt(audit, refs["numerical_oracle"]["sha256"], expected_source_sha256)
            previous.verify_audit_coverage(audit, ligand.coordinates[0], supplied, refs, coordinate_ref)
            common.require(common.reference(path) == coordinate_ref and audit["all_same_math_checks_passed"],
                           "independent_audit_failed")
            derivative_checks.extend(derivative_helper.verify_optimizer_derivatives(audit, observation_map))
            audits.append(audit)
        phase = "final_retained_geometry"
        final_geometry = validity(xyz)
        intact()
        common.require(final_geometry.get("complete") is True and final_geometry.get("valid") is True,
                       "final_retained_geometry_invalid_or_incomplete")
        phase = "report_publication"
        report = {
            "schema_id": "pr49_feasible_trajectory_development_report/1.0.0", "plan": plan_ref,
            "native_source_sha256": expected_source_sha256, "runtime": runtime, "trajectory": step, "bound_execution_results": result_refs,
            "independent_trajectory_ledger_audit": ledger,
            "audited_native_attempt_ids": [i for i, _ in selected_calls],
            "completed_native_attempts": sum(r["status"] == "completed" for r in observations),
            "failed_native_attempts": sum(r["status"] == "failed" for r in observations),
            "invalid_native_results": sum(r["status"] == "invalid_result" for r in observations),
            "native_attempts_not_independently_numerically_audited": [r["objective_point_attempt"] for r in observations
                if r["status"] == "completed" and r["objective_point_attempt"] not in {1, *(i for i, _ in selected_calls)}],
            "final_geometry": final_geometry, "native_and_geometry_cost": costs, "oracle_cost": oracle_costs,
            "numerical_denominators": [a["denominator"] for a in audits],
            "numerical_unique_states": len({s["coordinates_sha256"] for a in audits for s in a["snapshots"]}),
            "optimizer_derivatives_match_audited_states": derivative_checks,
            "phase_wall_seconds": phase_times,
            "whole_wall_seconds_before_report_publication": time.perf_counter() - started,
            "timings_are_inclusive_do_not_sum_nested_scopes": True,
            "product_admission": "NOT_ADMITTED_BY_RESEARCH_EXPERIMENT",
            "product_solver_changed": False, "product_qualified": False, "scientifically_validated": False,
            "observed_PR49_pose": False, "affinity_validated": False, "performance_qualified": False,
            "timing_scope": plan["timing_scope"],
        }
        published_json(output / "report.json", report, {})
        return {"report": str(output / "report.json"), "product_admission": report["product_admission"],
                "termination": step["termination"], "accepted_steps": len(step["accepted_objective_point_attempts"]),
                "raw_force_converged": step["raw_force_converged"]}
    except Exception as exc:
        common.write(output / "failure.json", {"phase": phase, "error_type": type(exc).__name__, "error": str(exc),
            "native_and_geometry_cost": costs, "oracle_cost": oracle_costs, "completed_phases": phase_times,
            "wall_seconds": time.perf_counter() - started, "trials_preserved": True, "product_qualified": False})
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("request", "geometry-protocol", "ligand-xml", "receptor-xml", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--expected-source-sha256", required=True)
    args = parser.parse_args()
    torch.set_num_threads(1)
    print(json.dumps(run(args.request, args.geometry_protocol, args.ligand_xml, args.receptor_xml,
                         args.output, args.expected_source_sha256), sort_keys=True))
