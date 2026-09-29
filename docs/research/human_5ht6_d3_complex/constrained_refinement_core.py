"""Bounded research SLSQP with explicit feasibility and independent KKT audit.

SciPy callbacks are major-iteration observations, not accepted-step receipts.
The product minimizer, force model and original raw-force gate are unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
import copy
import hashlib
import math
import time

import numpy as np
import scipy
from scipy.optimize import minimize, nnls
import torch


PROTOCOL = {
    "algorithm": "research_bounded_slsqp_explicit_strain_and_original_bonds_v1",
    "required_scipy_version": "1.12.0",
    "max_iterations": 128,
    "max_objective_point_attempts": 192,
    "ftol": 1e-10,
    "objective_divisor": 1000.0,
    "internal_increase_limit_kcal_mol": 5.0,
    "original_bond_length_change_limit_angstrom": 0.15,
    "active_normalized_constraint_maximum": 1e-6,
    "kkt_maximum_atom_residual_kcal_mol_angstrom": 0.001,
    "complementarity_tolerance_kcal_mol": 1e-6,
    "raw_maximum_atom_force_tolerance_kcal_mol_angstrom": 0.001,
    "nnls_max_iterations_per_active_constraint": 3,
    "selection": "last_fully_feasible_callback_observed_state_or_fully_validated_terminal_state",
    "full_validity_scope": "every_completed_native_trial_and_all_admitted_states_exact_coordinate_cache_reused",
    "coordinate_bounds": None,
    "cache": "exact_cpu_float64_coordinate_bytes_with_integrity_guard_on_every_access",
}


class IntegrityStop(RuntimeError):
    pass


class PointBudgetStop(RuntimeError):
    pass


class NumericalStop(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise ValueError(message)


def atom_norm(value):
    return float(np.linalg.norm(np.asarray(value).reshape(-1, 3), axis=1).max())


def coordinate_key(xyz):
    return np.asarray(xyz, dtype=np.float64).reshape(-1).tobytes(order="C")


def normalized_constraints(xyz, internal_energy, internal_gradient, initial_internal, bonds, original_lengths, protocol):
    """c >= 0; rows are strain, then lower/upper distance for each bond."""
    xyz = np.asarray(xyz, dtype=np.float64).reshape(-1, 3)
    strain_limit = protocol["internal_increase_limit_kcal_mol"]
    distance_limit = protocol["original_bond_length_change_limit_angstrom"]
    values = [(strain_limit - (internal_energy - initial_internal)) / strain_limit]
    jacobian = [-np.asarray(internal_gradient).reshape(-1) / strain_limit]
    deltas = []
    for (i, j), original in zip(bonds, original_lengths, strict=True):
        delta = xyz[i] - xyz[j]
        distance = float(np.linalg.norm(delta))
        require(math.isfinite(distance) and distance > 0.0, "zero_or_nonfinite_bond_distance_has_no_distance_jacobian")
        change = distance - original
        deltas.append(change)
        derivative = np.zeros_like(xyz)
        derivative[i] = delta / (distance * distance_limit)
        derivative[j] = -derivative[i]
        values.extend(((distance_limit + change) / distance_limit,
                       (distance_limit - change) / distance_limit))
        jacobian.extend((derivative.reshape(-1), -derivative.reshape(-1)))
    values, jacobian = np.asarray(values), np.asarray(jacobian)
    require(np.isfinite(values).all() and np.isfinite(jacobian).all(), "nonfinite_constraint_values_or_jacobian")
    return values, jacobian, np.asarray(deltas)


@dataclass(frozen=True)
class Point:
    key: bytes
    xyz: np.ndarray
    energy: float
    gradient: np.ndarray
    internal_energy: float
    internal_gradient: np.ndarray
    components: dict
    values: np.ndarray
    jacobian: np.ndarray
    bond_changes: np.ndarray
    attempt: int
    validity: dict | None = None

    def document(self):
        return {"coordinates_angstrom": self.xyz.tolist(), "total_energy_kcal_mol": self.energy,
                "total_gradient_kcal_mol_angstrom": self.gradient.tolist(),
                "internal_energy_kcal_mol": self.internal_energy,
                "internal_gradient_kcal_mol_angstrom": self.internal_gradient.tolist(),
                "components": dict(self.components), "normalized_constraints": self.values.tolist(),
                "original_bond_length_changes_angstrom": self.bond_changes.tolist(),
                "raw_maximum_atom_force_kcal_mol_angstrom": atom_norm(self.gradient),
                "full_validity": copy.deepcopy(self.validity),
                "objective_point_attempt": self.attempt,
                "coordinate_bytes_sha256": hashlib.sha256(self.key).hexdigest()}


class PointCache:
    """One fixed-source run; new points, failed attempts and hits remain distinct."""
    def __init__(self, original, bonds, objective, record, intact, protocol, validity=None):
        self.original = original.detach().clone().numpy()
        self.bonds = bonds
        self.lengths = tuple(float(np.linalg.norm(self.original[i] - self.original[j])) for i, j in bonds)
        require(all(math.isfinite(d) and d > 0 for d in self.lengths), "positive_original_bond_lengths_required")
        self.objective, self.record, self.intact = objective, record, intact
        self.validity = validity
        self.protocol = dict(protocol)
        self.initial_internal = None
        self.points = {}
        self.counts = {"objective_point_attempts": 0, "failed_objective_point_attempts": 0,
                       "cache_requests": 0, "cache_hits": 0, "integrity_checks": 0,
                       "objective_wall_seconds": 0.0, "integrity_wall_seconds": 0.0,
                       "validity_calls": 0, "failed_validity_calls": 0, "validity_wall_seconds": 0.0}

    def evaluate_validity(self, xyz, key):
        if self.validity is None:
            return None
        self.guard()
        started = time.perf_counter()
        self.counts["validity_calls"] += 1
        try:
            argument = torch.from_numpy(xyz.copy())
            result = self.validity(argument)
            require(coordinate_key(argument.numpy()) == key, "validity_mutated_coordinate_argument")
            require(isinstance(result, dict) and type(result.get("complete")) is bool
                    and type(result.get("valid")) is bool, "explicit_complete_and_valid_booleans_required")
            self.guard()
            return copy.deepcopy(result)
        except Exception:
            self.counts["failed_validity_calls"] += 1
            self.guard()
            raise
        finally:
            self.counts["validity_wall_seconds"] += time.perf_counter() - started

    def guard(self):
        started = time.perf_counter()
        self.counts["integrity_checks"] += 1
        try:
            self.intact()
        except Exception as exc:
            raise IntegrityStop(str(exc)) from exc
        finally:
            self.counts["integrity_wall_seconds"] += time.perf_counter() - started

    def get(self, flat, origin):
        self.guard()
        self.counts["cache_requests"] += 1
        xyz = np.asarray(flat, dtype=np.float64).reshape(self.original.shape).copy()
        key = coordinate_key(xyz)
        if key in self.points:
            self.counts["cache_hits"] += 1
            self.guard()
            self.record({"event": "coordinate_cache_reuse", "origin": origin,
                         "objective_point_attempt": self.points[key].attempt,
                         "coordinate_bytes_sha256": hashlib.sha256(key).hexdigest()})
            return self.points[key]
        if self.counts["objective_point_attempts"] >= self.protocol["max_objective_point_attempts"]:
            self.record({"event": "objective_point_budget_stop", "origin": origin,
                         "coordinate_bytes_sha256": hashlib.sha256(key).hexdigest(),
                         "objective_point_attempts": self.counts["objective_point_attempts"]})
            raise PointBudgetStop("maximum_objective_point_attempts_reached")
        self.counts["objective_point_attempts"] += 1
        attempt = self.counts["objective_point_attempts"]
        row = {"event": "objective_point", "origin": origin, "objective_point_attempt": attempt,
               "coordinate_bytes_sha256": hashlib.sha256(key).hexdigest(), "outcome": "evaluated"}
        if np.isfinite(xyz).all():
            row["coordinates_angstrom"] = xyz.tolist()
        started = time.perf_counter()
        try:
            require(np.isfinite(xyz).all(), "nonfinite_objective_coordinates")
            argument = torch.from_numpy(xyz.copy())
            energy, gradient, internal, internal_gradient, components = self.objective(argument)
            require(coordinate_key(argument.numpy()) == key, "objective_mutated_coordinate_argument")
            energy, internal = float(energy), float(internal)
            for value in (gradient, internal_gradient):
                require(isinstance(value, torch.Tensor) and value.shape == argument.shape
                        and value.dtype == torch.float64 and value.device.type == "cpu"
                        and bool(torch.isfinite(value).all()), "finite_cpu_float64_gradient_required")
            gradient = gradient.detach().numpy().copy()
            internal_gradient = internal_gradient.detach().numpy().copy()
            components = {name: float(value) for name, value in components.items()}
            require(math.isfinite(energy) and math.isfinite(internal)
                    and math.isfinite(atom_norm(gradient)) and math.isfinite(atom_norm(internal_gradient))
                    and all(math.isfinite(value) for value in components.values()), "finite_objective_values_required")
            self.guard()
            validity_report = self.evaluate_validity(xyz, key)
            row["full_validity"] = validity_report
            if self.initial_internal is None:
                require(key == coordinate_key(self.original), "original_point_must_be_evaluated_first")
                self.initial_internal = internal
            values, jacobian, changes = normalized_constraints(
                xyz, internal, internal_gradient, self.initial_internal, self.bonds, self.lengths, self.protocol)
            point = Point(key, xyz, energy, gradient, internal, internal_gradient, components,
                          values, jacobian, changes, attempt, validity_report)
            self.points[key] = point
            row.update(point.document())
            return point
        except Exception as exc:
            self.counts["failed_objective_point_attempts"] += 1
            row.update(outcome="fatal_evaluation_failure", error_type=type(exc).__name__, error=str(exc))
            self.guard()  # Numerical failures cannot mask source mutation.
            if isinstance(exc, IntegrityStop):
                raise
            raise NumericalStop(str(exc)) from exc
        finally:
            elapsed = time.perf_counter() - started
            self.counts["objective_wall_seconds"] += elapsed
            row["objective_point_wall_seconds"] = elapsed
            self.record(row)


def kkt_audit(point, protocol, *, nnls_solver=nnls):
    """Unscaled g - J.T @ mu for normalized c >= 0 and nonnegative mu."""
    started = time.perf_counter()
    values, jacobian, gradient = point.values, point.jacobian, point.gradient.reshape(-1)
    active = np.flatnonzero(values <= protocol["active_normalized_constraint_maximum"])
    result = {"constraint_scope": "strain_and_original_bond_constraints_only",
              "active_constraint_indices": active.tolist(), "normalized_constraints": values.tolist(),
              "maximum_normalized_primal_violation": float(np.max(np.maximum(-values, 0.0), initial=0.0)),
              "primal_feasible_exact": bool(np.all(values >= 0.0)), "objective_gradient_scaled": False,
              "raw_maximum_atom_force_kcal_mol_angstrom": atom_norm(gradient),
              "nnls_called": bool(len(active)), "nnls_succeeded": False, "stationary": False}
    try:
        multipliers = np.zeros(len(values), dtype=np.float64)
        if len(active):
            fitted, _ = nnls_solver(jacobian[active].T, gradient,
                maxiter=protocol["nnls_max_iterations_per_active_constraint"] * len(active))
            fitted = np.asarray(fitted, dtype=np.float64)
            require(fitted.shape == (len(active),) and np.isfinite(fitted).all(), "invalid_nnls_multipliers")
            multipliers[active] = fitted
        residual = gradient - jacobian.T @ multipliers
        complementarity = float(np.max(np.abs(multipliers * values), initial=0.0))
        residual_norm = atom_norm(residual)
        dual = bool(np.all(multipliers >= 0.0))
        result.update(nnls_succeeded=True, dual_feasible_exact=dual,
            multipliers_kcal_mol=multipliers.tolist(), residual_kcal_mol_angstrom=residual.reshape(-1, 3).tolist(),
            maximum_atom_residual_kcal_mol_angstrom=residual_norm,
            maximum_complementarity_kcal_mol=complementarity,
            stationary=bool(result["primal_feasible_exact"] and dual
                and math.isfinite(residual_norm) and math.isfinite(complementarity)
                and residual_norm <= protocol["kkt_maximum_atom_residual_kcal_mol_angstrom"]
                and complementarity <= protocol["complementarity_tolerance_kcal_mol"]))
    except Exception as exc:
        result.update(error_type=type(exc).__name__, error=str(exc), dual_feasible_exact=False)
    result["wall_seconds"] = time.perf_counter() - started
    return result


def bounded_slsqp(original, bonds, objective, validity, record, *, intact=lambda: None, protocol=None):
    """Return (retained coordinates, JSON report, first distinct incumbent or None).

    Objective returns total energy/gradient, internal energy/gradient, components.
    Validity must return explicit booleans ``complete`` and ``valid``. Every
    optimizer observation remains separate from independent research admission.
    A fatal evaluation ends optimization; no penalty objective is substituted.
    """
    started = time.perf_counter()
    protocol = dict(PROTOCOL if protocol is None else protocol)
    require(scipy.__version__ == protocol["required_scipy_version"], "frozen_scipy_version_required")
    require(isinstance(original, torch.Tensor) and original.ndim == 2 and original.shape[1] == 3
            and original.numel() > 0 and original.dtype == torch.float64 and original.device.type == "cpu"
            and bool(torch.isfinite(original).all()), "finite_cpu_float64_original_coordinates_required")
    require(type(bonds) is tuple and all(type(b) is tuple and len(b) == 2
            and all(type(i) is int and 0 <= i < len(original) for i in b) and b[0] != b[1] for b in bonds),
            "explicit_original_bond_index_pairs_required")
    require(len({tuple(sorted(b)) for b in bonds}) == len(bonds), "duplicate_original_bond_pairs")
    require(all(type(protocol[k]) is int and protocol[k] > 0 for k in
            ("max_iterations", "max_objective_point_attempts", "nnls_max_iterations_per_active_constraint")),
            "positive_integer_budgets_required")
    for key in ("ftol", "objective_divisor", "internal_increase_limit_kcal_mol",
                "original_bond_length_change_limit_angstrom", "active_normalized_constraint_maximum",
                "kkt_maximum_atom_residual_kcal_mol_angstrom", "complementarity_tolerance_kcal_mol",
                "raw_maximum_atom_force_tolerance_kcal_mol_angstrom"):
        require(type(protocol[key]) in (float, int) and math.isfinite(protocol[key]) and protocol[key] > 0,
                "finite_positive_numerical_protocol_required:" + key)
    original_key = coordinate_key(original.detach().numpy())
    def checked_intact():
        require(coordinate_key(original.detach().numpy()) == original_key, "original_input_coordinates_mutated")
        intact()
    cache = PointCache(original, bonds, objective, record, checked_intact, protocol, validity=validity)
    initial = cache.get(original.numpy().reshape(-1), "initial")
    counters = {"major_iteration_observations": 0, "incumbent_updates": 0}
    observations = []
    first_incumbent = None
    incumbent = initial
    incumbent_origin = "initial"

    def admission(point, origin):
        cache.guard()
        validity_report = copy.deepcopy(point.validity)
        require(validity_report is not None, "full_validity_missing_from_evaluated_point")
        checks = {"strain_within_exact_limit": point.internal_energy - initial.internal_energy <= protocol["internal_increase_limit_kcal_mol"],
            "original_bonds_within_exact_limit": bool(np.all(np.abs(point.bond_changes) <= protocol["original_bond_length_change_limit_angstrom"])),
            "normalized_primal_feasible_exact": bool(np.all(point.values >= 0.0)),
            "complete_full_validity": validity_report["complete"] and validity_report["valid"],
            "total_energy_not_above_initial": point.energy <= initial.energy}
        return {"origin": origin, "checks": checks, "eligible": all(checks.values()), "validity": validity_report}

    initial_admission = admission(initial, "initial")
    record({"event": "initial_admission", **initial_admission})
    require(initial_admission["eligible"], "initial_full_feasibility_required")
    incumbent_admission = initial_admission

    def observe(flat, origin):
        nonlocal incumbent, incumbent_origin, incumbent_admission, first_incumbent
        point = cache.get(flat, origin)
        assessment = admission(point, origin)
        updated = assessment["eligible"] and point.key != incumbent.key
        if assessment["eligible"]:
            incumbent, incumbent_origin, incumbent_admission = point, origin, assessment
            if updated:
                counters["incumbent_updates"] += 1
                if first_incumbent is None and point.key != initial.key:
                    first_incumbent = torch.from_numpy(point.xyz.copy())
        observation = {"event": origin, "objective_point_attempt": point.attempt,
            "coordinate_bytes_sha256": hashlib.sha256(point.key).hexdigest(),
            "total_energy_kcal_mol": point.energy, "internal_energy_kcal_mol": point.internal_energy,
            "incumbent_updated": updated, "admission": assessment,
            "is_slsqp_accepted_step_receipt": False}
        if origin == "major_iteration_observation":
            observation["major_iteration_observation_index"] = counters["major_iteration_observations"]
        observations.append(observation)
        record(observation)

    def callback(flat):
        counters["major_iteration_observations"] += 1
        observe(flat, "major_iteration_observation")

    def fun(flat):
        return cache.get(flat, "objective_fun").energy / protocol["objective_divisor"]

    def jac(flat):
        return cache.get(flat, "objective_jac").gradient.reshape(-1).copy() / protocol["objective_divisor"]

    def constraint_fun(flat):
        return cache.get(flat, "constraint_fun").values.copy()

    def constraint_jac(flat):
        return cache.get(flat, "constraint_jac").jacobian.copy()

    scipy_result = None
    termination, error = "scipy_returned", None
    integrity_valid = True
    optimization_started = time.perf_counter()
    try:
        result = minimize(fun, original.detach().numpy().reshape(-1).copy(), method="SLSQP", jac=jac,
            constraints={"type": "ineq", "fun": constraint_fun, "jac": constraint_jac}, callback=callback,
            options={"maxiter": protocol["max_iterations"], "ftol": protocol["ftol"], "disp": False})
        scipy_result = {"success": bool(result.success), "status": int(result.status), "message": str(result.message),
                        "reported_iterations": int(result.nit), "reported_function_calls": int(result.nfev),
                        "reported_gradient_calls": int(result.njev)}
        # Even a successful terminal point needs a charged/cache-guarded objective
        # and complete independent admission; SciPy's status grants no authority.
        observe(result.x, "terminal_state_observation")
    except PointBudgetStop as exc:
        termination, error = "objective_point_budget_exhausted", {"type": type(exc).__name__, "reason": str(exc)}
    except IntegrityStop as exc:
        termination, error, integrity_valid = "source_integrity_failure", {"type": type(exc).__name__, "reason": str(exc)}, False
    except Exception as exc:
        termination, error = "fatal_numerical_applicability_or_optimizer_failure", {"type": type(exc).__name__, "reason": str(exc)}
    optimizer_seconds = time.perf_counter() - optimization_started
    # Recheck the retained state, without selecting any unobserved trial from cache.
    final_admission = incumbent_admission
    if integrity_valid:
        try:
            final_admission = admission(cache.get(incumbent.xyz.reshape(-1), "retained_final"), "retained_final")
        except IntegrityStop as exc:
            termination, error, integrity_valid = "source_integrity_failure", {"type": type(exc).__name__, "reason": str(exc)}, False
        except Exception as exc:
            termination, error = "retained_final_validation_failure", {"type": type(exc).__name__, "reason": str(exc)}
            final_admission = {"eligible": False, "error": str(exc)}
    kkt = kkt_audit(incumbent, protocol) if integrity_valid else {"stationary": False, "reason": "source_integrity_invalid"}
    raw = atom_norm(incumbent.gradient) <= protocol["raw_maximum_atom_force_tolerance_kcal_mol_angstrom"]
    stationary = integrity_valid and final_admission["eligible"] and kkt["stationary"]
    original_gates = integrity_valid and final_admission["eligible"] and raw
    status = ("INVALID_SOURCE_INTEGRITY" if not integrity_valid else
              "RAW_AND_CONSTRAINED_STATIONARY" if stationary and raw else
              "CONSTRAINED_STATIONARY_ONLY" if stationary else "NOT_STATIONARY")
    report = {"schema_id": "bounded_slsqp_research_core_report/1.0.0", "status": status,
        "termination": termination, "error": error, "scipy_result": scipy_result, "protocol": protocol,
        "scipy_version": scipy.__version__, "source_integrity_valid": integrity_valid,
        "initial": initial.document(), "final": incumbent.document(), "initial_admission": initial_admission,
        "final_admission": final_admission, "retained_incumbent_origin": incumbent_origin,
        "internal_increase_from_original_kcal_mol": incumbent.internal_energy - initial.internal_energy,
        "maximum_original_bond_length_change_angstrom": float(np.max(np.abs(incumbent.bond_changes), initial=0.0)),
        "kkt": kkt, "constrained_stationary": stationary, "raw_force_converged": raw,
        "original_force_and_research_admission_gates_passed": original_gates,
        "product_status": "NOT_ADMITTED" if not original_gates else "NOT_QUALIFIED_BY_RESEARCH_CORE",
        "counters": {**cache.counts, **counters, "cached_successful_points": len(cache.points)},
        "major_and_terminal_observations": observations,
        "optimizer_and_terminal_validation_wall_seconds": optimizer_seconds,
        "whole_wall_seconds": time.perf_counter() - started,
        "timings_are_inclusive_do_not_sum_nested_scopes": True,
        "product_solver_changed": False, "product_qualified": False, "performance_comparison": False,
        "selection_is_independent_research_admission_not_slsqp_step_acceptance": True}
    record({"event": "retained_final_assessment", "status": status, "termination": termination,
            "source_integrity_valid": integrity_valid, "admission": final_admission, "kkt": kkt})
    return torch.from_numpy(incumbent.xyz.copy()), report, first_incumbent
