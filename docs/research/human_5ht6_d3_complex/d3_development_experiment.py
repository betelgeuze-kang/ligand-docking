"""Frozen rigid preparation followed by native D3 on one development input.

This creates a new candidate lineage, separate from any same-candidate comparison.
No observed PR49 reference pose, activity labels or protected outcomes are inputs.
The expected native source hash is required; existing output packets survive.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import time

import torch

from betelgeuze_engine_v2.geometry import RadiusGraphConfig, build_compact_radius_graph
from betelgeuze_engine_v2.molecular import canonical_system_sha256, canonical_topology_sha256
from betelgeuze_engine_v2.molecular.serialization import canonical_system_json_bytes
from betelgeuze_product.reference_minimization_workflow import _bound
from betelgeuze_product.cpu_refinement_v1_2.evaluation import ExtendedEvaluator
from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import (
    CrossParameters, FixedReceptorEnvironment,
    ReferencePhysicsApplicabilityError,
)
from betelgeuze_product.cpu_refinement_v1_2.minimization import minimize_extended
from betelgeuze_product.cpu_refinement_v1_2.provenance import digest, source_manifest
from betelgeuze_product.cpu_refinement_v1_2.scoring_profile import FIXED_REQUEST_SCHEMAS
from betelgeuze_product.cpu_refinement_v1_2.workflow import load_request, REQUEST_SCHEMA


GEOMETRY_PROTOCOL_SHA256 = "01c1f5f2c0fa8e253a997565e64c4d319d2025a1f49a1221976bc9fde730af8b"
RIGID_PROTOCOL = {
    "algorithm": "unweighted_rigid_tangent_cross_descent_proper_rotation_v1",
    "translation": "sum_cross_force_divided_by_atom_count",
    "rotation": "solve_sum_r2I_minus_outer_r_r_times_omega_equals_sum_r_cross_force",
    "center": "arithmetic_centroid_of_all_ligand_atoms",
    "normalization": "one_global_scale_for_translation_and_rotation_using_translation_norm_plus_omega_norm_times_max_radius",
    "max_accepted_steps": 32,
    "max_backtracks": 12,
    "initial_step": 0.001,
    "backtrack_factor": 0.5,
    "armijo_constant": 0.0001,
    "maximum_atom_displacement_angstrom": 0.05,
    "rigid_projected_force_tolerance_kcal_mol_angstrom": 0.001,
    "maximum_internal_distance_drift_angstrom": 1e-10,
    "proper_rotation_tolerance": 1e-12,
    "maximum_internal_energy_drift_kcal_mol": 1e-8,
    "force_call_upper_bound": 417,
    "geometry_protocol_sha256": GEOMETRY_PROTOCOL_SHA256,
    "selection": "last_accepted_state_of_single_fixed_start_no_restart_or_best_of_search",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def reference(path):
    path = Path(path).resolve(strict=True)
    raw = path.read_bytes()
    return {"path": str(path), "sha256": sha(raw), "bytes": len(raw)}


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def verify_file_references(references):
    for ref in references.values():
        require(reference(ref["path"]) == ref, "source_file_changed_during_experiment")


def verify_numerical_receipt(report, oracle_sha256, native_sha256):
    protocol = report["protocol"]
    require(protocol["absolute_energy_tolerance_kcal_per_mol"] == 1e-8
            and protocol["absolute_force_component_tolerance_kcal_per_mol_angstrom"] == 1e-8,
            "numerical_audit_tolerance_changed")
    require(report["audit_source_sha256"] == oracle_sha256, "numerical_oracle_source_changed")
    require(report["native_source_manifest_sha256"] == native_sha256, "numerical_native_source_changed")


def proper_rotation(rotation_vector):
    """Rodrigues exponential; no reflection, scaling or approximate Euler step."""
    vector = torch.as_tensor(rotation_vector, dtype=torch.float64)
    require(vector.shape == (3,) and bool(torch.isfinite(vector).all()), "invalid_rotation_vector")
    x, y, z = vector.tolist()
    skew = torch.tensor([[0., -z, y], [z, 0., -x], [-y, x, 0.]], dtype=torch.float64)
    theta2 = float(torch.dot(vector, vector))
    if theta2 < 1e-12:
        a = 1. - theta2 / 6. + theta2 * theta2 / 120.
        b = .5 - theta2 / 24. + theta2 * theta2 / 720.
    else:
        theta = math.sqrt(theta2)
        a, b = math.sin(theta) / theta, (1. - math.cos(theta)) / theta2
    return torch.eye(3, dtype=torch.float64) + a * skew + b * (skew @ skew)


def rigid_tangent(coordinates, forces):
    """Euclidean projection onto translations and infinitesimal rotations."""
    require(coordinates.ndim == 2 and coordinates.shape[1] == 3 and coordinates.shape == forces.shape,
            "rigid_coordinates_force_shape_mismatch")
    require(bool(torch.isfinite(coordinates).all() and torch.isfinite(forces).all()), "nonfinite_rigid_input")
    relative = coordinates - coordinates.mean(dim=0)
    inertia = torch.eye(3, dtype=torch.float64) * (relative * relative).sum() - relative.T @ relative
    eigenvalues = torch.linalg.eigvalsh(inertia)
    require(float(eigenvalues[0]) > 1e-12 * max(1., float(eigenvalues[-1])), "singular_rigid_rotation_metric")
    translation = forces.mean(dim=0)
    torque = torch.linalg.cross(relative, forces, dim=-1).sum(dim=0)
    omega = torch.linalg.solve(inertia, torque)
    tangent = translation + torch.linalg.cross(omega.expand_as(relative), relative, dim=-1)
    return translation, omega, tangent


def bounded_direction(coordinates, translation, omega):
    radius = float(torch.linalg.vector_norm(coordinates - coordinates.mean(dim=0), dim=-1).max())
    speed_bound = float(torch.linalg.vector_norm(translation)) + float(torch.linalg.vector_norm(omega)) * radius
    scale = min(1., RIGID_PROTOCOL["maximum_atom_displacement_angstrom"] /
                max(RIGID_PROTOCOL["initial_step"] * speed_bound, 1e-300))
    return translation * scale, omega * scale


def transform_from_original(original, rotation, centroid_shift):
    identity = torch.eye(3, dtype=torch.float64)
    tolerance = RIGID_PROTOCOL["proper_rotation_tolerance"]
    require(bool(torch.isfinite(rotation).all() and torch.isfinite(centroid_shift).all())
            and float((rotation.T @ rotation - identity).abs().max()) <= tolerance
            and abs(float(torch.linalg.det(rotation)) - 1.) <= tolerance, "transform_not_proper_rigid")
    center = original.mean(dim=0)
    moved = (original - center) @ rotation.T + center + centroid_shift
    drift = float((torch.pdist(original) - torch.pdist(moved)).abs().max())
    require(drift <= RIGID_PROTOCOL["maximum_internal_distance_drift_angstrom"], "rigid_internal_distance_changed")
    return moved, drift


def geometry_observation(coordinates, ligand_elements, receptor_coordinates, receptor_elements, center, protocol):
    """All pairs, including hydrogens; retain the original overlap/pocket limits."""
    heavy_l = torch.tensor([element != "H" for element in ligand_elements])
    heavy_r = torch.tensor([element != "H" for element in receptor_elements])
    radii = protocol["radius_table_angstrom"]
    sums = (torch.tensor([radii[e] for e in ligand_elements], dtype=torch.float64)[:, None]
            + torch.tensor([radii[e] for e in receptor_elements], dtype=torch.float64)[None, :])
    distances = torch.linalg.vector_norm(coordinates[:, None] - receptor_coordinates[None, :], dim=-1)
    require(bool(torch.isfinite(distances).all()), "nonfinite_geometry")
    ratios = distances / sums
    row = {
        "minimum_all_atom_distance_angstrom": float(distances.min()),
        "minimum_heavy_atom_distance_angstrom": float(distances[heavy_l][:, heavy_r].min()),
        "minimum_all_atom_radius_sum_ratio": float(ratios.min()),
        "minimum_heavy_atom_radius_sum_ratio": float(ratios[heavy_l][:, heavy_r].min()),
        "maximum_ligand_heavy_radius_angstrom": float(torch.linalg.vector_norm(coordinates[heavy_l] - center, dim=-1).max()),
        "heavy_centroid_offset_angstrom": float(torch.linalg.vector_norm(coordinates[heavy_l].mean(dim=0) - center)),
    }
    checks = {
        "all_distance": row["minimum_all_atom_distance_angstrom"] >= protocol["all_atom_minimum_distance_angstrom"],
        "heavy_distance": row["minimum_heavy_atom_distance_angstrom"] >= protocol["heavy_atom_minimum_distance_angstrom"],
        "all_ratio": row["minimum_all_atom_radius_sum_ratio"] >= protocol["all_atom_minimum_radius_sum_ratio"],
        "heavy_ratio": row["minimum_heavy_atom_radius_sum_ratio"] >= protocol["heavy_atom_minimum_radius_sum_ratio"],
        "pocket": row["maximum_ligand_heavy_radius_angstrom"] <= protocol["pocket_all_heavy_maximum_radius_angstrom"],
        "centroid_offset": row["heavy_centroid_offset_angstrom"] <= protocol["offset_maximum_norm_angstrom"],
    }
    return {**row, "checks": checks, "passed": all(checks.values())}


def rigid_descent(original, cross_evaluate, geometry_check, record):
    """Bounded research optimizer with an append-only record of every trial."""
    start = time.perf_counter()
    rotation = torch.eye(3, dtype=torch.float64)
    shift = torch.zeros(3, dtype=torch.float64)
    xyz = original.clone()
    initial_geometry = geometry_check(xyz)
    require(initial_geometry["passed"], "initial_geometry_ineligible")
    calls, failed_calls, force_seconds, attempts, accepted = 0, 0, 0., 0, 0

    def evaluate(coordinates, row):
        nonlocal calls, failed_calls, force_seconds
        called = time.perf_counter()
        calls += 1
        try:
            components, forces, pair_count = cross_evaluate(coordinates)
            numeric = {key: float(value) for key, value in components.items()}
            energy = sum(numeric.values())
            if not (math.isfinite(energy) and bool(torch.isfinite(forces).all())):
                raise FloatingPointError("nonfinite_cross_evaluation")
        except Exception as exc:
            failed_calls += 1
            row.update(outcome="rejected_force_evaluation", error_type=type(exc).__name__, error=str(exc))
            raise
        finally:
            elapsed = time.perf_counter() - called
            force_seconds += elapsed
            row["cross_force_wall_seconds"] = elapsed
        row.update(cross_components=numeric, cross_energy_kcal_mol=energy,
                   cross_forces_kcal_mol_angstrom=forces.tolist(), active_cross_pairs=pair_count)
        return energy, forces

    row = {"index": 0, "iteration": 0, "trial": 0, "outcome": "initial", "step": 0.,
           "coordinates_angstrom": xyz.tolist(), "geometry": initial_geometry}
    try:
        energy, forces = evaluate(xyz, row)
    finally:
        record(row)
    initial_energy = energy
    status = "max_rigid_iterations_reached"
    while accepted < RIGID_PROTOCOL["max_accepted_steps"]:
        translation, omega, tangent = rigid_tangent(xyz, forces)
        projected_force = float(torch.linalg.vector_norm(tangent, dim=-1).max())
        if projected_force <= RIGID_PROTOCOL["rigid_projected_force_tolerance_kcal_mol_angstrom"]:
            status = "rigid_projected_stationary_not_full_convergence"
            break
        translation, omega = bounded_direction(xyz, translation, omega)
        moved = False
        for trial in range(RIGID_PROTOCOL["max_backtracks"] + 1):
            attempts += 1
            step = RIGID_PROTOCOL["initial_step"] * RIGID_PROTOCOL["backtrack_factor"] ** trial
            trial_rotation = proper_rotation(step * omega) @ rotation
            trial_shift = shift + step * translation
            trial_xyz, drift = transform_from_original(original, trial_rotation, trial_shift)
            geometry = geometry_check(trial_xyz)
            displacement = float(torch.linalg.vector_norm(trial_xyz - xyz, dim=-1).max())
            slope = -float((forces * (trial_xyz - xyz)).sum())
            row = {"index": attempts, "iteration": accepted + 1, "trial": trial, "step": step,
                   "coordinates_angstrom": trial_xyz.tolist(), "geometry": geometry,
                   "rotation_from_original": trial_rotation.tolist(), "all_atom_centroid_shift_angstrom": trial_shift.tolist(),
                   "maximum_step_displacement_angstrom": displacement,
                   "maximum_internal_distance_drift_angstrom": drift, "armijo_slope_kcal_mol": slope,
                   "cross_force_wall_seconds": 0., "outcome": "accepted"}
            if displacement > RIGID_PROTOCOL["maximum_atom_displacement_angstrom"] + 1e-12:
                row["outcome"] = "rejected_displacement"
            elif not geometry["passed"]:
                row["outcome"] = "rejected_geometry"
            elif slope >= 0:
                row["outcome"] = "rejected_non_descent"
            else:
                try:
                    trial_energy, trial_forces = evaluate(trial_xyz, row)
                except (ReferencePhysicsApplicabilityError, FloatingPointError):
                    pass
                except Exception:
                    # Global input/integrity failures are fatal, with the failed
                    # force attempt retained rather than retried as a pose miss.
                    row["outcome"] = "fatal_force_evaluation"
                    record(row)
                    raise
                else:
                    if trial_energy > energy + RIGID_PROTOCOL["armijo_constant"] * slope:
                        row["outcome"] = "rejected_armijo"
            record(row)
            if row["outcome"] == "accepted":
                xyz, rotation, shift = trial_xyz, trial_rotation, trial_shift
                energy, forces = trial_energy, trial_forces
                accepted += 1
                moved = True
                break
        if not moved:
            status = "rigid_line_search_failed_last_accepted_retained"
            break
    _, _, tangent = rigid_tangent(xyz, forces)
    return xyz, {
        "status": status, "accepted_steps": accepted, "trial_count": attempts,
        "cross_force_calls": calls, "failed_cross_force_calls": failed_calls,
        "initial_cross_energy_kcal_mol": initial_energy, "final_cross_energy_kcal_mol": energy,
        "final_projected_force_kcal_mol_angstrom": float(torch.linalg.vector_norm(tangent, dim=-1).max()),
        "rotation_from_original": rotation.tolist(), "all_atom_centroid_shift_angstrom": shift.tolist(),
        "maximum_internal_distance_drift_angstrom": float((torch.pdist(original) - torch.pdist(xyz)).abs().max()),
        "final_geometry": geometry_check(xyz), "wall_seconds": time.perf_counter() - start,
        "nested_cross_force_wall_seconds": force_seconds, "timings_are_inclusive": True,
        "full_coordinate_convergence_claimed": False,
    }


def run(request_path, geometry_path, ligand_xml, receptor_xml, output, expected_source_sha256):
    from tools.analysis import openmm_d3_numerical_audit as numerical_audit

    started = time.perf_counter()
    request_path, geometry_path, ligand_xml, receptor_xml, output = map(
        lambda p: Path(p).resolve(), (request_path, geometry_path, ligand_xml, receptor_xml, output))
    sources = source_manifest()
    require(digest(sources) == expected_source_sha256, "native_source_does_not_match_frozen_expected_hash")
    script = reference(__file__)
    source_refs = {name: reference(path) for name, path in (
        ("request", request_path), ("geometry_protocol", geometry_path), ("ligand_xml", ligand_xml),
        ("receptor_xml", receptor_xml), ("numerical_oracle", numerical_audit.__file__))}
    require(numerical_audit.ENERGY_ABSOLUTE_TOLERANCE == 1e-8
            and numerical_audit.FORCE_ABSOLUTE_TOLERANCE == 1e-8, "numerical_audit_tolerance_changed")
    require(source_refs["geometry_protocol"]["sha256"] == GEOMETRY_PROTOCOL_SHA256, "frozen_geometry_protocol_changed")
    geometry_protocol = json.loads(geometry_path.read_bytes())
    request = json.loads(request_path.read_bytes())
    require(request["schema_id"] in FIXED_REQUEST_SCHEMAS and request["solvation"] is None, "fixed_dry_request_required")
    internal_request = {k: v for k, v in request.items() if k != "cross_parameters"}
    internal_request["schema_id"] = REQUEST_SCHEMA
    _, receptor, ligand, parameters, _, solver, solvent, _, _ = load_request(internal_request, expected_source_sha256)
    fixed = FixedReceptorEnvironment(receptor, CrossParameters.from_dict(_bound(request["cross_parameters"])))
    fixed.validate_ligand(ligand, parameters.base_parameters)
    native_settings = {"max_iterations": 32, "max_backtracks": 12,
        "force_tolerance_kcal_per_mol_angstrom": .001,
        "initial_step_size_angstrom2_mol_per_kcal": .001,
        "maximum_atom_displacement_angstrom": .05, "armijo_constant": .0001, "backtrack_factor": .5}
    require(all(getattr(solver.minimization, key) == value for key, value in native_settings.items())
            and fixed.cross.max_internal_increase_kcal_per_mol == 5., "frozen_native_admission_or_budget_changed")
    require(not parameters.constraints and solvent is None, "unconstrained_dry_development_model_required")
    require(parameters.metadata.get("source_xml_sha256") == source_refs["ligand_xml"]["sha256"]
            and fixed.cross.parameter_source_sha256 == source_refs["receptor_xml"]["sha256"], "source_xml_not_bound")
    center = torch.tensor(request["pocket"]["center_angstrom"], dtype=torch.float64)
    require(request["pocket"]["radius_angstrom"] == geometry_protocol["pocket_all_heavy_maximum_radius_angstrom"], "pocket_radius_changed")
    def geometry(xyz):
        return geometry_observation(xyz, [a.element for a in ligand.atoms], receptor.coordinates[0],
                                    [a.element for a in receptor.atoms], center, geometry_protocol)
    require(geometry(ligand.coordinates[0])["passed"], "initial_geometry_ineligible")
    output.mkdir(parents=True, exist_ok=False)
    plan = {"schema_id": "pr49_rigid_then_native_d3_development_plan/1.0.0",
        "inputs": source_refs, "script": script, "native_source_sha256": expected_source_sha256,
        "native_source_manifest": sources, "rigid_protocol": RIGID_PROTOCOL, "native_solver": solver.to_dict(),
        "internal_strain_limit_kcal_mol": 5., "numerical_energy_and_force_absolute_tolerance": 1e-8,
        "numerical_states": ["original", "rigid", "native_final"],
        "numerical_audits": "two source-bound audits with zero perturbations; rigid state repeated, unique states deduplicated",
        "geometry_scope": "every rigid trial and final native state; native solver unchanged",
        "new_candidate_lineage": True, "same_candidates_comparison": False,
        "timing_scope": "local development observation; concurrent CPU work not controlled; no performance comparison",
        "observed_PR49_pose": False, "affinity_validated": False, "protected_outcomes_read": False,
        "scientifically_validated": False, "setup_wall_seconds": time.perf_counter() - started}
    write(output / "plan.json", plan)  # Frozen before the first force evaluation.
    phases = {}
    def intact():
        require(source_manifest() == sources and reference(__file__) == script, "implementation_changed_during_experiment")
        verify_file_references(source_refs)
        for name in ("ligand", "receptor", "parameters", "extensions", "cross_parameters"):
            _bound(request[name])
        fixed.assert_intact()
    def internal_energy(state):
        neighbors = build_compact_radius_graph(state.coordinates, RadiusGraphConfig(
            cutoff_angstrom=parameters.base_parameters.cutoff_angstrom,
            max_neighbors=solver.minimization.max_neighbors,
            max_atoms_per_cell=solver.minimization.max_atoms_per_cell))
        evaluation = ExtendedEvaluator(parameters).evaluate(state, neighbors)
        return {"energy_kcal_mol": float(evaluation.term.energy[0]),
                "components": {k: float(v[0]) for k, v in evaluation.component_energies.items()}}
    phase = "initial_internal"
    try:
        scope = time.perf_counter()
        before = internal_energy(ligand)
        phases[phase] = time.perf_counter() - scope
        write(output / "initial-internal.json", before)
        phase = "rigid_preparation"
        def cross(xyz):
            state = ligand.with_coordinates(xyz.unsqueeze(0), operation="rigid_cross_development_trial")
            components, force, count = fixed.evaluate_cross(state, parameters.base_parameters)
            return {k: float(v[0]) for k, v in components.items()}, force[0], count
        with (output / "rigid-trials.jsonl").open("x") as stream:
            def record(row):
                stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
                stream.flush()
            xyz, rigid_report = rigid_descent(ligand.coordinates[0], cross, geometry, record)
        phases[phase] = rigid_report["wall_seconds"]
        write(output / "rigid-report.json", rigid_report)
        rigid = ligand.with_coordinates(xyz.unsqueeze(0), operation=RIGID_PROTOCOL["algorithm"],
                                        operation_evidence_sha256=digest(rigid_report))
        require(canonical_topology_sha256(rigid) == canonical_topology_sha256(ligand), "rigid_topology_changed")
        phase = "rigid_internal_verification"
        scope = time.perf_counter()
        after = internal_energy(rigid)
        phases[phase] = time.perf_counter() - scope
        write(output / "rigid-internal.json", after)
        require(abs(after["energy_kcal_mol"] - before["energy_kcal_mol"]) <= 1e-8, "rigid_internal_energy_changed")
        with (output / "rigid-canonical.json").open("xb") as stream:
            stream.write(canonical_system_json_bytes(rigid))
        write(output / "rigid-coordinates.json", {"coordinates_angstrom": xyz.tolist()})
        derived = {**request, "ligand": {k: v for k, v in reference(output / "rigid-canonical.json").items() if k != "bytes"}}
        write(output / "rigid-request.json", derived)
        intact()
        phase = "initial_rigid_numerical_audit"
        scope = time.perf_counter()
        first_audit = numerical_audit.audit(request_path, ligand_xml, receptor_xml,
                                           final_coordinates_path=output / "rigid-coordinates.json", perturbations=0)
        phases[phase] = time.perf_counter() - scope
        write(output / "numerical-original-rigid.json", first_audit)
        verify_numerical_receipt(first_audit, source_refs["numerical_oracle"]["sha256"], expected_source_sha256)
        intact()
        require(first_audit["all_same_math_checks_passed"], "original_or_rigid_numerical_audit_failed")
        phase = "native_d3"
        scope = time.perf_counter()
        result = minimize_extended(rigid, parameters, solver, fixed_environment=fixed)
        phases[phase] = time.perf_counter() - scope
        checkpoint = result.checkpoint.to_dict()
        write(output / "native-checkpoint.json", checkpoint)
        write(output / "native-execution.json", dict(result.execution))
        with (output / "native-final-canonical.json").open("xb") as stream:
            stream.write(canonical_system_json_bytes(result.system))
        write(output / "native-final-coordinates.json", {"coordinates_angstrom": result.system.coordinates[0].tolist()})
        phase = "rigid_final_numerical_audit"
        scope = time.perf_counter()
        second_audit = numerical_audit.audit(output / "rigid-request.json", ligand_xml, receptor_xml,
                                            final_coordinates_path=output / "native-final-coordinates.json", perturbations=0)
        phases[phase] = time.perf_counter() - scope
        write(output / "numerical-rigid-final.json", second_audit)
        verify_numerical_receipt(second_audit, source_refs["numerical_oracle"]["sha256"], expected_source_sha256)
        intact()
        final_geometry = geometry(result.system.coordinates[0])
        strain = checkpoint["current_components"]["ligand_internal"] - before["energy_kcal_mol"]
        criteria = {"native_converged": result.converged, "internal_increase_within_5_kcal_mol": strain <= 5.,
            "native_total_not_increased": checkpoint["current_energy"] <= checkpoint["initial_energy"],
            "final_geometry_eligible": final_geometry["passed"],
            "numerical_audits_passed": first_audit["all_same_math_checks_passed"] and second_audit["all_same_math_checks_passed"]}
        unique = {row["coordinates_sha256"] for report in (first_audit, second_audit) for row in report["snapshots"]}
        report = {"schema_id": "pr49_rigid_then_native_d3_development_report/1.0.0",
            "status": "DEVELOPMENT_NUMERICAL_CRITERIA_MET" if all(criteria.values()) else "NOT_ADMITTED",
            "plan": reference(output / "plan.json"), "native_source_sha256": expected_source_sha256,
            "original_ligand_sha256": canonical_system_sha256(ligand), "rigid_ligand_sha256": canonical_system_sha256(rigid),
            "final_ligand_sha256": canonical_system_sha256(result.system),
            "rigid": rigid_report, "initial_internal": before, "rigid_internal": after,
            "native_status": result.status, "native_initial_components": checkpoint["initial_components"],
            "native_final_components": checkpoint["current_components"],
            "native_final_max_force_kcal_mol_angstrom": checkpoint["current_max_tangent_force"],
            "internal_increase_from_original_kcal_mol": strain, "criteria": criteria, "final_geometry": final_geometry,
            "numerical_unique_coordinate_states": len(unique),
            "numerical_invocation_denominators": [first_audit["denominator"], second_audit["denominator"]],
            "phase_wall_seconds": phases, "whole_wall_seconds_before_report_publication": time.perf_counter() - started,
            "timings_are_inclusive_do_not_sum_nested_scopes": True,
            "new_candidate_lineage": True, "same_candidates_comparison": False, "observed_PR49_pose": False,
            "affinity_validated": False, "scientifically_validated": False, "product_qualified": False,
            "performance_qualified": False, "timing_scope": plan["timing_scope"]}
        write(output / "report.json", report)
        return {key: report[key] for key in ("status", "criteria", "native_final_max_force_kcal_mol_angstrom", "internal_increase_from_original_kcal_mol")}
    except Exception as exc:
        write(output / "failure.json", {"status": "FAILED_DEVELOPMENT_EXECUTION", "phase": phase,
            "error_type": type(exc).__name__, "reason": str(exc), "completed_phase_wall_seconds": phases,
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
