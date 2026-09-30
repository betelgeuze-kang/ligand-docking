"""Source-bound strain/bond-constrained SLSQP research on the original PR49 pose.

The product optimizer and its raw-force convergence criterion remain unchanged.
Constrained stationarity is a separate research diagnostic, never product admission.
"""
from __future__ import annotations

import argparse
import json
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
    constrained_refinement_core as core, d3_development_experiment as common,
    lbfgs_development_experiment as previous, product_geometry_audit as product_geometry,
)


def runtime_identity():
    return {**previous.runtime_identity(), "scipy_distribution": scipy.__version__}


def verify_optimizer_derivatives(audit, observations):
    """Bind both total and strain derivatives to independent fixed-state checks."""
    result = []
    for snapshot in audit["snapshots"]:
        observed = observations[digest(snapshot["coordinates_angstrom"])]
        native = snapshot["native"]
        internal = torch.tensor(native["internal_forces"], dtype=torch.float64)
        cross = torch.tensor(native["cross_forces"], dtype=torch.float64)
        total_gradient = torch.tensor(observed["total_gradient"], dtype=torch.float64)
        internal_gradient = torch.tensor(observed["internal_gradient"], dtype=torch.float64)
        reference = snapshot["reference_same_math"]
        reference_internal = torch.tensor(reference["internal_forces"], dtype=torch.float64)
        reference_cross = torch.tensor(reference["cross_forces"], dtype=torch.float64)
        errors = {
            "total_energy": abs(observed["energy"] - native["internal_energy"] - sum(native["cross_components"].values())),
            "internal_energy": abs(observed["internal_energy"] - native["internal_energy"]),
            "total_gradient": float((total_gradient + internal + cross).abs().max()),
            "internal_gradient": float((internal_gradient + internal).abs().max()),
            "reference_total_energy": abs(observed["energy"] - reference["internal_energy"] - reference["cross_energy"]),
            "reference_internal_energy": abs(observed["internal_energy"] - reference["internal_energy"]),
            "reference_total_gradient": float((total_gradient + reference_internal + reference_cross).abs().max()),
            "reference_internal_gradient": float((internal_gradient + reference_internal).abs().max()),
        }
        common.require(all(value <= 1e-8 for value in errors.values()),
                       "optimizer_derivative_does_not_match_audited_native_state")
        result.append({"coordinates_sha256": digest(snapshot["coordinates_angstrom"]),
                       "absolute_errors": errors, "passed": True})
    return result


def run(request_path, geometry_path, ligand_xml, receptor_xml, output, expected_source_sha256):
    started = time.perf_counter()
    sources = source_manifest()
    common.require(digest(sources) == expected_source_sha256, "native_source_not_frozen")
    from tools.analysis import openmm_d3_numerical_audit as oracle
    refs = {name: common.reference(path) for name, path in (
        ("request", request_path), ("geometry_protocol", geometry_path), ("ligand_xml", ligand_xml),
        ("receptor_xml", receptor_xml), ("numerical_oracle", oracle.__file__), ("script", __file__),
        ("core", core.__file__), ("product_geometry_adapter", product_geometry.__file__),
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
    def intact():
        common.require(source_manifest() == sources, "native_source_changed")
        common.require(runtime_identity() == runtime and core.PROTOCOL == protocol, "runtime_or_protocol_changed")
        common.verify_file_references(refs)
        if plan_ref is not None:
            common.require(common.reference(plan_ref["path"]) == plan_ref, "published_plan_changed")
        common.require(canonical_system_sha256(ligand) == original_identity, "original_ligand_mutated")
        fixed.assert_intact()
    intact()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    plan = {
        "schema_id": "pr49_strain_bond_slsqp_development_plan/1.0.0", "protocol": protocol,
        "inputs_and_source_files": refs, "native_source_sha256": expected_source_sha256,
        "native_source_manifest": sources, "runtime": runtime, "input_product_solver": solver.to_dict(),
        "original_ligand_sha256": original_identity, "initial_product_geometry": baseline,
        "initial_placement_geometry": initial_geometry,
        "objective": "unchanged_internal_plus_cross_energy; optimizer-only_positive_scale_1_over_1000",
        "constraints": "normalized_internal_increase_at_most_5_and_each_original_bond_change_at_most_0.15",
        "step_policy": "SLSQP_trials; prior_0.05_angstrom_LBFGS_step_cap_not_applied; no_artificial_coordinate_box",
        "geometry_scope": "full_product_and_six_placement_checks_on_every_completed_native_trial_and_retained_state",
        "selection": "last_fully_feasible_callback_observed_or_independently_validated_terminal_state; no_callback_acceptance_claim",
        "stationarity_scope": "strain_and_original_bond_constraints_only; geometry_is_separate_eligibility",
        "budget": {"native_point_attempts": 192, "combined_evaluator_calls": 192,
                   "additional_internal_evaluator_calls": 192, "oracle_combined_snapshots_separate_maximum": 4},
        "cost_accounting": "combined evaluator contains one internal and one cross call; extra internal call recovers strain derivative; nested calls are not independent total cost",
        "numerical_states": ["original", "first_incumbent_if_any", "final_retained"],
        "original_product_raw_force_threshold_remains": .001,
        "same_budget_algorithm_comparison": False, "new_training_or_protected_outcomes_used": False,
        "scientifically_validated": False, "product_qualified": False,
        "timing_scope": "enclosing development run excludes upstream preparation and human work; CPU contention uncontrolled",
        "setup_wall_seconds": time.perf_counter() - started,
    }
    common.write(output / "plan.json", plan)
    plan_ref = common.reference(output / "plan.json")
    evaluator = FixedReceptorEvaluator(ExtendedEvaluator(parameters, solvent), fixed)
    costs = {name: {"calls": 0, "failed_calls": 0, "wall_seconds": 0.0}
             for name in ("graph", "combined_force", "additional_internal_force", "geometry")}
    observations, oracle_costs, phase_times = {}, [], {}
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
        state = ligand.with_coordinates(xyz.unsqueeze(0), operation="research_strain_bond_slsqp_v1")
        graph = measured("graph", lambda: build_compact_radius_graph(state.coordinates, RadiusGraphConfig(
            cutoff_angstrom=parameters.base_parameters.cutoff_angstrom,
            max_neighbors=solver.minimization.max_neighbors,
            max_atoms_per_cell=solver.minimization.max_atoms_per_cell)))
        value = measured("combined_force", lambda: evaluator.evaluate(state, graph))
        internal = measured("additional_internal_force", lambda: evaluator.internal.evaluate(state, graph))
        energy, internal_energy = float(value.term.energy[0]), float(internal.term.energy[0])
        common.require(internal_energy == float(value.component_energies["ligand_internal"][0]),
                       "internal_energy_evaluations_disagree")
        gradient, internal_gradient = -value.term.forces[0], -internal.term.forces[0]
        observations[digest(xyz.tolist())] = {"coordinates": xyz.tolist(), "energy": energy,
            "total_gradient": gradient.tolist(), "internal_energy": internal_energy,
            "internal_gradient": internal_gradient.tolist()}
        return energy, gradient, internal_energy, internal_gradient, components_document(value)
    def validity(xyz):
        def evaluate():
            binding = {"plan_sha256": plan_ref["sha256"], "coordinates_sha256": digest(xyz.tolist()),
                       "role": "actual_research_geometry_observation", "native_source_sha256": expected_source_sha256}
            product = adapter.evaluate_coordinates(xyz, refiner_id="research.strain_bond_slsqp",
                refiner_version="1.0.0", refinement_receipt_sha256=digest(binding))
            geometry = placement_geometry(xyz)
            return {"valid": product["passed"] and geometry["passed"], "complete": product["complete"],
                    "product": product, "placement": geometry, "research_binding": binding}
        return measured("geometry", evaluate)
    phase = "bounded_constrained_optimization"
    try:
        with (output / "trials.jsonl").open("x") as stream:
            def record(row):
                stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
                stream.flush()
            scope = time.perf_counter()
            xyz, optimization, first = core.bounded_slsqp(ligand.coordinates[0],
                tuple((b.atom_i, b.atom_j) for b in ligand.bonds), objective, validity, record, intact=intact)
            phase_times[phase] = time.perf_counter() - scope
        intact()
        common.require(optimization["source_integrity_valid"], "recorded_integrity_failure_is_fatal")
        common.write(output / "optimization.json", optimization)
        common.write(output / "objective-observations.json", observations)
        common.write(output / "final-coordinates.json", {"coordinates_angstrom": xyz.tolist()})
        final = ligand.with_coordinates(xyz.unsqueeze(0), operation="research_strain_bond_slsqp_v1")
        common.require(canonical_topology_sha256(final) == canonical_topology_sha256(ligand), "topology_changed")
        with (output / "final-canonical.json").open("xb") as stream:
            stream.write(canonical_system_json_bytes(final))
        audit_paths = []
        if first is not None:
            common.write(output / "first-incumbent-coordinates.json", {"coordinates_angstrom": first.tolist()})
            audit_paths.append(("numerical-original-first", output / "first-incumbent-coordinates.json", first))
        audit_paths.append(("numerical-original-final", output / "final-coordinates.json", xyz))
        audits, derivative_checks = [], []
        for phase, path, supplied in audit_paths:
            intact()
            coordinate_ref = common.reference(path)
            cost = {"phase": phase}
            oracle_costs.append(cost)
            audit = previous.measured_audit(oracle, cost, Path(request_path), Path(ligand_xml), Path(receptor_xml),
                                           final_coordinates_path=path, perturbations=0)
            phase_times[phase] = cost["whole_audit_wall_seconds"]
            common.write(output / (phase + ".json"), audit)
            common.write(output / (phase + "-cost.json"), cost)
            common.verify_numerical_receipt(audit, refs["numerical_oracle"]["sha256"], expected_source_sha256)
            previous.verify_audit_coverage(audit, ligand.coordinates[0], supplied, refs, coordinate_ref)
            common.require(common.reference(path) == coordinate_ref and audit["all_same_math_checks_passed"],
                           "independent_audit_failed")
            derivative_checks.extend(verify_optimizer_derivatives(audit, observations))
            audits.append(audit)
        final_geometry = validity(xyz)
        intact()
        report = {
            "schema_id": "pr49_strain_bond_slsqp_development_report/1.0.0", "plan": plan_ref,
            "native_source_sha256": expected_source_sha256, "runtime": runtime, "optimization": optimization,
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
        common.write(output / "report.json", report)
        return {"report": str(output / "report.json"), "product_admission": report["product_admission"],
                "termination": optimization["termination"], "constrained_stationary": optimization["constrained_stationary"],
                "raw_force_converged": optimization["raw_force_converged"]}
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
