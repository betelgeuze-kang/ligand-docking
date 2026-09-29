"""One bounded L-BFGS diagnostic on the original registered D3 development pose.

The product minimizer is unchanged. This is one algorithm and one frozen budget,
not a matched cost comparison, affinity validation or an observed PR49 pose.
Run with PYTHONPATH=. and an externally supplied frozen native source digest.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
from pathlib import Path
import sys
import time

import torch

from betelgeuze_engine_v2.geometry import RadiusGraphConfig, build_compact_radius_graph
from betelgeuze_engine_v2.molecular import canonical_system_sha256, canonical_topology_sha256
from betelgeuze_engine_v2.molecular.serialization import canonical_system_json_bytes
from betelgeuze_product.reference_minimization_workflow import _bound
from betelgeuze_product.cpu_refinement_v1_2.evaluation import ExtendedEvaluator
from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import (
    CrossParameters, FixedReceptorEnvironment, FixedReceptorEvaluator,
    ReferencePhysicsApplicabilityError, components_document,
)
from betelgeuze_product.cpu_refinement_v1_2.provenance import digest, environment, source_manifest
from betelgeuze_product.cpu_refinement_v1_2.scoring_profile import FIXED_REQUEST_SCHEMAS
from betelgeuze_product.cpu_refinement_v1_2.workflow import REQUEST_SCHEMA, load_request
from docs.research.human_5ht6_d3_complex import d3_development_experiment as common


ORIGINAL_LIGAND_FILE_SHA256 = "bc71d19603c3db4940af455939ddbcb4ebf5d8d88cd98c32c266f84d37fb3185"
PROTOCOL = {
    "algorithm": "bounded_cartesian_lbfgs_armijo_development_v1",
    "max_accepted_steps": 128,
    "max_force_evaluation_attempts": 192,
    "history_size": 10,
    "initial_inverse_hessian_scale_angstrom2_mol_per_kcal": 0.001,
    "inverse_hessian_scaling": "latest_valid_s_dot_y_over_y_dot_y_else_initial_scale",
    "initial_line_scalar": 1.0,
    "max_backtracks": 12,
    "backtrack_factor": 0.5,
    "armijo_constant": 1e-4,
    "maximum_atom_displacement_angstrom": 0.05,
    "force_tolerance_kcal_mol_angstrom": 0.001,
    "convergence_metric": "maximum_euclidean_force_norm_over_ligand_atoms",
    "curvature_relative_threshold": 1e-12,
    "curvature_rule": "s_dot_y_strictly_greater_than_threshold_times_norm_s_times_norm_y",
    "restart_rule": "clear_history_if_nonfinite_or_not_strict_descent_then_initial_scaled_negative_gradient",
    "internal_increase_limit_kcal_mol": 5.0,
    "maximum_numerical_energy_and_force_absolute_error": 1e-8,
    "selection": "last_accepted_state_of_one_original_start_no_rigid_prestep",
    "geometry_scope": "initial_and_final_admission_only_as_in_product_native_refinement",
    "strain_scope": "final_admission_only_no_strain_term_added_to_objective",
}


def maximum_atom_norm(value):
    return float(torch.linalg.vector_norm(value, dim=-1).max())


def inverse_hessian_product(gradient, history, initial_scale):
    """L-BFGS two-loop recursion, oldest-to-newest (s, y) history."""
    q = gradient.clone()
    coefficients = []
    for s, y in reversed(history):
        rho = 1.0 / float(torch.sum(s * y))
        alpha = rho * float(torch.sum(s * q))
        coefficients.append((rho, alpha))
        q = q - alpha * y
    scale = initial_scale
    if history:
        s, y = history[-1]
        scale = float(torch.sum(s * y)) / float(torch.sum(y * y))
    result = scale * q
    for (s, y), (rho, alpha) in zip(history, reversed(coefficients), strict=True):
        beta = rho * float(torch.sum(y * result))
        result = result + (alpha - beta) * s
    return result


def search_direction(gradient, history, protocol):
    """Return a globally capped direction; any restart explicitly clears history."""
    scale = protocol["initial_inverse_hessian_scale_angstrom2_mol_per_kcal"]
    reason = None
    try:
        direction = -inverse_hessian_product(gradient, history, scale)
        slope = float(torch.sum(gradient * direction))
        if not bool(torch.isfinite(direction).all()) or not math.isfinite(slope):
            reason = "nonfinite_lbfgs_direction"
        elif slope >= 0.0:
            reason = "lbfgs_direction_not_strict_descent"
    except (ZeroDivisionError, OverflowError):
        reason = "invalid_lbfgs_curvature_arithmetic"
    if reason is not None:
        history.clear()
        direction = -scale * gradient
    common.require(bool(torch.isfinite(direction).all()), "nonfinite_restart_direction")
    largest = maximum_atom_norm(direction)
    factor = min(1.0, protocol["maximum_atom_displacement_angstrom"] / max(largest, 1e-300))
    direction = direction * factor
    common.require(float(torch.sum(gradient * direction)) < 0.0, "no_representable_descent_direction")
    return direction, reason, factor


def curvature_update(history, s, y, protocol):
    sy = float(torch.sum(s * y))
    norm_product = float(torch.linalg.vector_norm(s)) * float(torch.linalg.vector_norm(y))
    threshold = protocol["curvature_relative_threshold"] * norm_product
    valid = (math.isfinite(sy) and math.isfinite(norm_product) and norm_product > 0.0
             and sy > threshold)
    row = {"s_dot_y": sy if math.isfinite(sy) else None,
           "norm_s_times_norm_y": norm_product if math.isfinite(norm_product) else None,
           "threshold": threshold if math.isfinite(threshold) else None,
           "accepted": valid, "discarded_oldest_pair": False}
    if valid:
        history.append((s.clone(), y.clone()))
        if len(history) > protocol["history_size"]:
            history.pop(0)
            row["discarded_oldest_pair"] = True
    else:
        row["reason"] = "nonfinite_zero_or_insufficient_positive_curvature"
    return row


def bounded_lbfgs(original, objective, record, *, intact=lambda: None, protocol=None):
    """Minimize an energy/gradient/components callable with a hard call budget.

    Each callable attempt consumes budget before invocation, including numerical
    failures. Fatal integrity errors are recorded and propagated without retry.
    The native runner also counts actual evaluator invocations independently.
    """
    protocol = dict(PROTOCOL if protocol is None else protocol)
    common.require(original.ndim == 2 and original.shape[1] == 3 and original.numel() > 0
                   and original.dtype == torch.float64 and original.device.type == "cpu"
                   and bool(torch.isfinite(original).all()), "finite_cpu_float64_coordinates_required")
    for name in ("max_force_evaluation_attempts", "max_accepted_steps", "history_size"):
        common.require(type(protocol[name]) is int and protocol[name] > 0, "positive_integer_budget_required")
    started = time.perf_counter()
    xyz = original.detach().clone()
    history = []
    calls = failed = accepted = trials = restarts = skipped = 0
    objective_seconds = 0.0
    outcomes = {}
    first_accepted = None

    def emit(row):
        outcomes[row["outcome"]] = outcomes.get(row["outcome"], 0) + 1
        record(row)

    def evaluate(at, row):
        nonlocal calls, failed, objective_seconds
        intact()
        common.require(calls < protocol["max_force_evaluation_attempts"], "force_budget_exhausted")
        calls += 1
        row["force_evaluation_attempt"] = calls
        scope = time.perf_counter()
        try:
            energy, gradient, components = objective(at.clone())
            energy = float(energy)
            components = {key: float(value) for key, value in components.items()}
            if (not math.isfinite(energy) or not isinstance(gradient, torch.Tensor)
                    or gradient.shape != at.shape or gradient.dtype != torch.float64
                    or gradient.device.type != "cpu" or not bool(torch.isfinite(gradient).all())
                    or not all(math.isfinite(value) for value in components.values())):
                raise FloatingPointError("nonfinite_or_invalid_objective_result")
            intact()
        except Exception as exc:
            failed += 1
            row.update(error_type=type(exc).__name__, error=str(exc))
            # A numerical exception must not hide a concurrent input mutation.
            intact()
            raise
        finally:
            elapsed = time.perf_counter() - scope
            row["objective_wall_seconds"] = elapsed
            objective_seconds += elapsed
        row.update(energy_kcal_mol=energy, components=components,
                   gradient_kcal_mol_angstrom=gradient.tolist(), maximum_atom_force=maximum_atom_norm(gradient))
        return energy, gradient.detach().clone(), components

    row = {"index": 0, "iteration": 0, "trial": 0, "outcome": "initial",
           "coordinates_angstrom": xyz.tolist()}
    try:
        energy, gradient, components = evaluate(xyz, row)
    except Exception:
        row["outcome"] = "fatal_initial_evaluation"
        raise
    finally:
        emit(row)
    initial = {"energy_kcal_mol": energy, "components": dict(components),
               "maximum_atom_force": maximum_atom_norm(gradient)}
    status = "max_accepted_steps_reached"
    while accepted < protocol["max_accepted_steps"]:
        if maximum_atom_norm(gradient) <= protocol["force_tolerance_kcal_mol_angstrom"]:
            status = "force_converged"
            break
        if calls >= protocol["max_force_evaluation_attempts"]:
            status = "force_budget_exhausted_last_accepted_retained"
            break
        intact()
        direction, restart, cap_scale = search_direction(gradient, history, protocol)
        restarts += int(restart is not None)
        moved = False
        for trial in range(protocol["max_backtracks"] + 1):
            if calls >= protocol["max_force_evaluation_attempts"]:
                status = "force_budget_exhausted_last_accepted_retained"
                break
            trials += 1
            scalar = protocol["initial_line_scalar"] * protocol["backtrack_factor"] ** trial
            trial_xyz = xyz + scalar * direction
            displacement = trial_xyz - xyz
            slope = float(torch.sum(gradient * displacement))
            row = {"index": trials, "iteration": accepted + 1, "trial": trial,
                   "line_scalar": scalar, "direction_cap_scale": cap_scale,
                   "direction_restart": restart, "history_pairs_before_trial": len(history),
                   "coordinates_angstrom": trial_xyz.tolist(),
                   "maximum_atom_displacement_angstrom": maximum_atom_norm(displacement),
                   "armijo_slope_kcal_mol": slope, "outcome": "accepted"}
            try:
                common.require(maximum_atom_norm(displacement) <= protocol["maximum_atom_displacement_angstrom"] + 1e-12,
                               "displacement_cap_exceeded")
                if slope >= 0.0:
                    row["outcome"] = "rejected_unrepresentable_descent"
                    continue
                trial_energy, trial_gradient, trial_components = evaluate(trial_xyz, row)
                limit = energy + protocol["armijo_constant"] * slope
                row["armijo_energy_limit_kcal_mol"] = limit
                if trial_energy > limit:
                    row["outcome"] = "rejected_armijo"
                    continue
                update = curvature_update(history, displacement, trial_gradient - gradient, protocol)
                row["curvature_update"] = update
                skipped += int(not update["accepted"])
                xyz, energy, gradient, components = trial_xyz, trial_energy, trial_gradient, trial_components
                accepted += 1
                if first_accepted is None:
                    first_accepted = xyz.clone()
                moved = True
                break
            except (FloatingPointError, ReferencePhysicsApplicabilityError):
                # Geometry-dependent numerical failure may backtrack; integrity
                # failures have a different type and must stop the experiment.
                row["outcome"] = "rejected_force_evaluation"
            except Exception:
                row["outcome"] = "fatal_evaluation_or_integrity"
                raise
            finally:
                emit(row)
        if not moved:
            if calls < protocol["max_force_evaluation_attempts"]:
                status = "line_search_failed_last_accepted_retained"
            break
    if maximum_atom_norm(gradient) <= protocol["force_tolerance_kcal_mol_angstrom"]:
        status = "force_converged"
    intact()
    return xyz, {"status": status, "converged": status == "force_converged",
        "accepted_steps": accepted, "trial_count": trials, "force_evaluation_attempts": calls,
        "failed_force_evaluation_attempts": failed, "direction_restarts": restarts,
        "skipped_curvature_updates": skipped, "retained_history_pairs": len(history),
        "outcomes": outcomes, "initial": initial,
        "final": {"energy_kcal_mol": energy, "components": dict(components),
                  "maximum_atom_force": maximum_atom_norm(gradient),
                  "gradient_kcal_mol_angstrom": gradient.tolist()},
        "objective_wall_seconds": objective_seconds, "wall_seconds": time.perf_counter() - started,
        "timings_are_inclusive_do_not_sum_nested_scopes": True}, first_accepted


def runtime_identity():
    return {**environment(), "python_executable": str(Path(sys.executable).resolve()),
            "openmm_distribution": importlib.metadata.version("OpenMM"),
            "numpy_distribution": importlib.metadata.version("numpy"),
            "native_device": "cpu", "native_dtype": "float64", "oracle_platform": "Reference"}


def verify_freeze(sources, runtime, references, protocol):
    common.require(source_manifest() == sources, "native_source_changed_during_experiment")
    common.require(runtime_identity() == runtime, "runtime_changed_during_experiment")
    common.require(PROTOCOL == protocol, "protocol_changed_during_experiment")
    common.verify_file_references(references)


def measured_audit(module, cost, *args, **kwargs):
    """Scope counters around unchanged oracle callables, restoring on failure.

    One native snapshot contains one internal evaluation and one cross force
    evaluation. OpenMM observations include grouped terms and the independent
    Coulomb constant measurement; these are not optimizer force calls.
    """
    originals = {name: getattr(module, name) for name in ("_native_components", "_observe")}
    def counted(name, original):
        key = "native_combined_snapshots" if name == "_native_components" else "openmm_energy_force_observations"
        cost[key] = {"calls": 0, "failed_calls": 0, "wall_seconds": 0.0}
        def wrapped(*args, **kwargs):
            counter = cost[key]
            counter["calls"] += 1
            started = time.perf_counter()
            try:
                return original(*args, **kwargs)
            except Exception:
                counter["failed_calls"] += 1
                raise
            finally:
                counter["wall_seconds"] += time.perf_counter() - started
        return wrapped
    started = time.perf_counter()
    try:
        for name, original in originals.items():
            setattr(module, name, counted(name, original))
        return module.audit(*args, **kwargs)
    finally:
        for name, original in originals.items():
            setattr(module, name, original)
        cost["whole_audit_wall_seconds"] = time.perf_counter() - started
        cost["timings_are_inclusive_do_not_sum_nested_scopes"] = True


def verify_audit_coverage(audit, original, supplied, source_refs, coordinate_ref):
    expected = [original.tolist(), supplied.tolist()]
    common.require(audit["denominator"] == {"requested": 2, "evaluated": 2, "rejected": 0, "passed": 2},
                   "numerical_audit_incomplete_state_coverage")
    common.require(len(audit["snapshots"]) == 2, "numerical_audit_incomplete_state_coverage")
    for row, xyz in zip(audit["snapshots"], expected, strict=True):
        common.require(row["coordinates_angstrom"] == xyz and row["coordinates_sha256"] == digest(xyz)
                       and row["passed"], "numerical_audit_coordinate_state_mismatch")
    for returned, bound in (("request", "request"), ("ligand_XML", "ligand_xml"), ("receptor_XML", "receptor_xml")):
        common.require(audit["inputs"][returned]["sha256"] == source_refs[bound]["sha256"],
                       "numerical_audit_input_binding_mismatch")
    common.require(audit["final_coordinates"]["sha256"] == coordinate_ref["sha256"],
                   "numerical_audit_final_coordinate_binding_mismatch")


def run(request_path, geometry_path, ligand_xml, receptor_xml, output, expected_source_sha256):
    started = time.perf_counter()
    sources = source_manifest()
    common.require(digest(sources) == expected_source_sha256, "native_source_not_frozen_expected_hash")
    from tools.analysis import openmm_d3_numerical_audit as numerical_audit
    source_refs = {name: common.reference(path) for name, path in (
        ("request", request_path), ("geometry_protocol", geometry_path), ("ligand_xml", ligand_xml),
        ("receptor_xml", receptor_xml), ("numerical_oracle", numerical_audit.__file__),
        ("script", __file__), ("shared_research_helpers", common.__file__))}
    common.require(numerical_audit.ENERGY_ABSOLUTE_TOLERANCE == 1e-8
                   and numerical_audit.FORCE_ABSOLUTE_TOLERANCE == 1e-8, "numerical_audit_tolerance_changed")
    common.require(source_refs["geometry_protocol"]["sha256"] == common.GEOMETRY_PROTOCOL_SHA256,
                   "frozen_geometry_protocol_changed")
    request = json.loads(Path(request_path).read_bytes())
    common.require(request["schema_id"] in FIXED_REQUEST_SCHEMAS and request["solvation"] is None,
                   "fixed_dry_request_required")
    for name in ("ligand", "receptor", "parameters", "extensions", "cross_parameters"):
        _bound(request[name])
        source_refs[name] = common.reference(request[name]["path"])
        common.require(source_refs[name]["sha256"] == request[name]["sha256"], "input_reference_mismatch")
    common.require(source_refs["ligand"]["sha256"] == ORIGINAL_LIGAND_FILE_SHA256,
                   "original_registered_ligand_required_no_repositioning")
    prepared = {k: v for k, v in request.items() if k != "cross_parameters"}
    prepared["schema_id"] = REQUEST_SCHEMA
    _, receptor, ligand, parameters, _, solver, solvent, _, _ = load_request(prepared, expected_source_sha256)
    fixed = FixedReceptorEnvironment(receptor, CrossParameters.from_dict(_bound(request["cross_parameters"])))
    fixed.validate_ligand(ligand, parameters.base_parameters)
    common.require(not parameters.constraints and solvent is None, "unconstrained_dry_development_model_required")
    common.require(fixed.cross.max_internal_increase_kcal_per_mol == 5.0
                   and solver.minimization.force_tolerance_kcal_per_mol_angstrom == 0.001
                   and solver.minimization.maximum_atom_displacement_angstrom == 0.05,
                   "original_admission_thresholds_changed")
    common.require(parameters.metadata.get("source_xml_sha256") == source_refs["ligand_xml"]["sha256"]
                   and fixed.cross.parameter_source_sha256 == source_refs["receptor_xml"]["sha256"], "source_xml_not_bound")
    geometry_protocol = json.loads(Path(geometry_path).read_bytes())
    common.require(request["pocket"]["radius_angstrom"] == geometry_protocol["pocket_all_heavy_maximum_radius_angstrom"],
                   "pocket_radius_changed")
    center = torch.tensor(request["pocket"]["center_angstrom"], dtype=torch.float64)
    def geometry(xyz):
        return common.geometry_observation(xyz, [a.element for a in ligand.atoms], receptor.coordinates[0],
                                           [a.element for a in receptor.atoms], center, geometry_protocol)
    initial_geometry = geometry(ligand.coordinates[0])
    common.require(initial_geometry["passed"], "initial_geometry_ineligible")
    runtime = runtime_identity()
    protocol = dict(PROTOCOL)
    original_identity = canonical_system_sha256(ligand)
    plan_reference = None
    def intact():
        verify_freeze(sources, runtime, source_refs, protocol)
        if plan_reference is not None:
            common.require(common.reference(plan_reference["path"]) == plan_reference,
                           "published_plan_changed_during_experiment")
        common.require(canonical_system_sha256(ligand) == original_identity, "original_ligand_mutated")
        fixed.assert_intact()
    intact()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    plan = {"schema_id": "pr49_original_pose_lbfgs_development_plan/1.0.0",
        "inputs_and_source_files": source_refs, "native_source_sha256": expected_source_sha256,
        "native_source_manifest": sources, "runtime": runtime, "protocol": protocol,
        "original_ligand_sha256": original_identity, "input_product_solver": solver.to_dict(),
        "original_coordinates_sha256": digest(ligand.coordinates[0].tolist()),
        "initial_geometry": initial_geometry,
        "numerical_states": ["original", "first_accepted_if_any", "final_last_accepted"],
        "numerical_audits": "two zero-perturbation source-driven audits; original repeated; if no accepted step, one audit",
        "native_optimizer_force_attempt_limit": 192,
        "oracle_native_combined_snapshots_separate_maximum": 4,
        "oracle_native_snapshot_definition": "one internal and one cross force evaluation assembled at fixed coordinates",
        "oracle_OpenMM_energy_force_observations_separately_counted": True,
        "oracle_instrumentation": "scoped call and failure counters wrap unchanged _native_components and _observe; wrappers restored after each audit",
        "budget_scope": "all optimizer objective attempts including initial, rejected and failed; graph failures also consume attempts",
        "same_candidates_comparison": False, "single_algorithm_budget_diagnostic": True,
        "input_placement_applied": False, "rigid_prestep_applied": False,
        "observed_PR49_pose": False, "protected_outcomes_read": False,
        "timing_scope": "local development observation; concurrent CPU work not controlled; no performance comparison",
        "setup_wall_seconds": time.perf_counter() - started}
    common.write(output / "plan.json", plan)  # Must precede every native or oracle force call.
    plan_reference = common.reference(output / "plan.json")
    evaluator = FixedReceptorEvaluator(ExtendedEvaluator(parameters, solvent), fixed)
    native_cost = {"graph_calls": 0, "failed_graph_calls": 0, "graph_wall_seconds": 0.0,
                   "force_calls": 0, "failed_force_calls": 0, "force_wall_seconds": 0.0}
    phase = "bounded_lbfgs"
    phase_times = {}
    ledger_outcomes = {}
    oracle_costs = []
    def objective(xyz):
        state = ligand.with_coordinates(xyz.unsqueeze(0), operation=PROTOCOL["algorithm"])
        native_cost["graph_calls"] += 1
        scope = time.perf_counter()
        try:
            graph = build_compact_radius_graph(state.coordinates, RadiusGraphConfig(
                cutoff_angstrom=parameters.base_parameters.cutoff_angstrom,
                max_neighbors=solver.minimization.max_neighbors,
                max_atoms_per_cell=solver.minimization.max_atoms_per_cell))
        except Exception:
            native_cost["failed_graph_calls"] += 1
            raise
        finally:
            native_cost["graph_wall_seconds"] += time.perf_counter() - scope
        native_cost["force_calls"] += 1
        scope = time.perf_counter()
        try:
            result = evaluator.evaluate(state, graph)
        except Exception:
            native_cost["failed_force_calls"] += 1
            raise
        finally:
            native_cost["force_wall_seconds"] += time.perf_counter() - scope
        return float(result.term.energy[0]), -result.term.forces[0], components_document(result)
    try:
        with (output / "trials.jsonl").open("x") as stream:
            def record(row):
                row["native_cost_cumulative"] = dict(native_cost)
                ledger_outcomes[row["outcome"]] = ledger_outcomes.get(row["outcome"], 0) + 1
                stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
                stream.flush()
            xyz, optimization, first = bounded_lbfgs(ligand.coordinates[0], objective, record,
                                                     intact=intact, protocol=protocol)
        phase_times[phase] = optimization["wall_seconds"]
        common.write(output / "optimization.json", optimization)
        common.write(output / "native-cost.json", native_cost)
        final = ligand.with_coordinates(xyz.unsqueeze(0), operation=PROTOCOL["algorithm"],
                                        operation_evidence_sha256=digest(optimization))
        common.require(canonical_topology_sha256(final) == canonical_topology_sha256(ligand), "topology_changed")
        with (output / "final-canonical.json").open("xb") as stream:
            stream.write(canonical_system_json_bytes(final))
        common.write(output / "final-coordinates.json", {"coordinates_angstrom": xyz.tolist()})
        audits = []
        audit_paths = []
        if first is not None:
            common.write(output / "first-accepted-coordinates.json", {"coordinates_angstrom": first.tolist()})
            audit_paths.append(("numerical-original-first-accepted", output / "first-accepted-coordinates.json", first))
        audit_paths.append(("numerical-original-final", output / "final-coordinates.json", xyz))
        for phase, coordinates_path, supplied in audit_paths:
            intact()
            coordinates_ref = common.reference(coordinates_path)
            cost = {"phase": phase}
            oracle_costs.append(cost)
            audit = measured_audit(numerical_audit, cost, Path(request_path), Path(ligand_xml), Path(receptor_xml),
                                   final_coordinates_path=coordinates_path, perturbations=0)
            phase_times[phase] = cost["whole_audit_wall_seconds"]
            common.write(output / (phase + ".json"), audit)
            common.write(output / (phase + "-cost.json"), cost)
            common.require(common.reference(coordinates_path) == coordinates_ref, "oracle_coordinates_changed")
            common.verify_numerical_receipt(audit, source_refs["numerical_oracle"]["sha256"], expected_source_sha256)
            verify_audit_coverage(audit, ligand.coordinates[0], supplied, source_refs, coordinates_ref)
            common.require(audit["all_same_math_checks_passed"], "source_driven_numerical_audit_failed")
            intact()
            audits.append(audit)
        phase = "final_admission"
        final_geometry = geometry(xyz)
        strain = optimization["final"]["components"]["ligand_internal"] - optimization["initial"]["components"]["ligand_internal"]
        criteria = {"force_converged": optimization["converged"],
                    "internal_increase_within_5_kcal_mol": strain <= 5.0,
                    "total_energy_not_increased": optimization["final"]["energy_kcal_mol"] <= optimization["initial"]["energy_kcal_mol"],
                    "final_geometry_eligible": final_geometry["passed"],
                    "numerical_audits_passed": all(a["all_same_math_checks_passed"] for a in audits)}
        unique = {row["coordinates_sha256"] for audit in audits for row in audit["snapshots"]}
        intact()
        report = {"schema_id": "pr49_original_pose_lbfgs_development_report/1.0.0",
            "status": "DEVELOPMENT_NUMERICAL_CRITERIA_MET" if all(criteria.values()) else "NOT_ADMITTED",
            "plan": plan_reference, "criteria": criteria,
            "native_source_sha256": expected_source_sha256, "runtime": runtime,
            "original_ligand_sha256": original_identity, "final_ligand_sha256": canonical_system_sha256(final),
            "optimization": optimization, "native_optimizer_cost": native_cost,
            "internal_increase_from_original_kcal_mol": strain, "final_geometry": final_geometry,
            "numerical_unique_coordinate_states": len(unique),
            "numerical_invocation_denominators": [a["denominator"] for a in audits],
            "oracle_cost": oracle_costs,
            "phase_wall_seconds": phase_times,
            "whole_wall_seconds_before_report_publication": time.perf_counter() - started,
            "timings_are_inclusive_do_not_sum_nested_scopes": True,
            "same_candidates_comparison": False, "single_algorithm_budget_diagnostic": True,
            "observed_PR49_pose": False, "affinity_validated": False,
            "scientifically_validated": False, "product_qualified": False, "performance_qualified": False,
            "timing_scope": plan["timing_scope"]}
        common.write(output / "report.json", report)
        return {"status": report["status"], "criteria": criteria,
                "maximum_atom_force": optimization["final"]["maximum_atom_force"],
                "internal_increase_from_original_kcal_mol": strain,
                "native_optimizer_force_calls": native_cost["force_calls"]}
    except Exception as exc:
        common.write(output / "failure.json", {"status": "FAILED_DEVELOPMENT_EXECUTION", "phase": phase,
            "error_type": type(exc).__name__, "reason": str(exc), "completed_phase_wall_seconds": phase_times,
            "native_optimizer_cost": native_cost, "recorded_trial_outcomes": ledger_outcomes,
            "oracle_cost": oracle_costs,
            "whole_wall_seconds_before_failure_publication": time.perf_counter() - started,
            "earlier_trials_preserved": True, "scientifically_validated": False})
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
