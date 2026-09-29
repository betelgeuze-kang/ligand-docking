"""One research-only, exact-feasible Armijo step on an unchanged objective.

This is neither a minimizer nor product admission. Every attempted point stays
in the report, including failed calls; no penalty energy or force is invented.
"""
from __future__ import annotations

import copy
import hashlib
import math
import time

import numpy as np
import torch


PROTOCOL = {
    "algorithm": "research_single_feasible_armijo_step_v1",
    "direction": "negative_original_total_gradient_maximum_atom_norm_one",
    "initial_alpha_angstrom": 0.05,
    "backtracking_factor": 0.5,
    "max_backtracking_trials": 16,
    "max_objective_point_attempts": 17,
    "armijo_c1": 1e-4,
    "internal_increase_limit_kcal_mol": 5.0,
    "original_bond_length_change_limit_angstrom": 0.15,
    "raw_maximum_atom_force_tolerance_kcal_mol_angstrom": 0.001,
    "selection": "first_exact_feasible_strict_energy_decrease_and_armijo_trial",
    "full_validity_scope": "every_normally_returned_objective_unless_source_integrity_failed",
    "failure_policy": "stop_and_retain_original_no_substitute_energy",
}


class IntegrityStop(RuntimeError):
    pass


class EvaluationStop(RuntimeError):
    def __init__(self, stage, error):
        self.stage = stage
        super().__init__(str(error))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def coordinate_key(xyz):
    return np.asarray(xyz, dtype=np.float64).tobytes(order="C")


def atom_norm(value):
    # hypot avoids overflow from squaring otherwise representable components.
    return float(np.hypot.reduce(np.asarray(value).reshape(-1, 3), axis=1).max())


def _coordinate_document(xyz):
    return {"coordinates_angstrom": xyz.tolist(),
            "coordinate_bytes_sha256": hashlib.sha256(coordinate_key(xyz)).hexdigest()}


class _Run:
    def __init__(self, original, objective, validity, record, intact):
        self.original = original
        self.xyz = original.detach().numpy().copy()
        self.key = coordinate_key(self.xyz)
        self.objective, self.validity, self.record, self.intact = objective, validity, record, intact
        self.integrity_error = None
        self.attempts = []
        self.counters = {"objective_point_attempts": 0, "backtracking_trials_attempted": 0,
                         "objective_calls": 0, "completed_objective_calls": 0,
                         "failed_objective_calls": 0, "invalid_objective_results": 0,
                         "validity_calls": 0, "failed_validity_calls": 0,
                         "record_calls": 0, "failed_record_calls": 0,
                         "integrity_checks": 0, "failed_integrity_checks": 0,
                         "objective_wall_seconds": 0.0, "validity_wall_seconds": 0.0,
                         "record_wall_seconds": 0.0, "integrity_wall_seconds": 0.0}

    def poison(self, reason):
        if self.integrity_error is None:
            self.integrity_error = str(reason)
        raise IntegrityStop(self.integrity_error)

    def guard(self):
        started = time.perf_counter()
        self.counters["integrity_checks"] += 1
        try:
            if self.integrity_error is not None:
                raise IntegrityStop(self.integrity_error)
            for after_callback in (False, True):
                if (self.original.shape != self.xyz.shape or self.original.dtype != torch.float64
                        or self.original.device.type != "cpu"
                        or coordinate_key(self.original.detach().numpy()) != self.key):
                    self.poison("original_input_coordinates_mutated")
                if not after_callback:
                    require(self.intact() is not False, "source_integrity_callback_returned_false")
        except Exception as exc:
            self.counters["failed_integrity_checks"] += 1
            self.poison(exc)
        finally:
            self.counters["integrity_wall_seconds"] += time.perf_counter() - started

    def call(self, stage, callback, argument, *, coordinate_argument=False):
        self.guard()
        self.counters[stage + "_calls"] += 1
        started = time.perf_counter()
        error, result = None, None
        key = coordinate_key(argument.numpy()) if coordinate_argument else None
        try:
            result = callback(argument)
            if stage == "objective":
                self.counters["completed_objective_calls"] += 1
        except Exception as exc:
            self.counters["failed_" + stage + "_calls"] += 1
            error = exc
        finally:
            self.counters[stage + "_wall_seconds"] += time.perf_counter() - started
            # The source check runs even when the callback failed. Once observed,
            # an integrity failure cannot be cleared by restoring source bytes.
            try:
                if coordinate_argument and (argument.shape != self.xyz.shape
                        or argument.dtype != torch.float64 or argument.device.type != "cpu"
                        or coordinate_key(argument.detach().numpy()) != key):
                    self.poison(stage + "_mutated_coordinate_argument")
            finally:
                self.guard()
        if error is not None:
            raise EvaluationStop(stage, error) from error
        return result

    def publish(self, row):
        # The callback receives an isolated copy, so it cannot rewrite a receipt.
        self.call("record", self.record, copy.deepcopy(row))

    def evaluate(self, xyz, trial_index, alpha, initial, direction_dot_gradient, bonds, lengths, protocol):
        self.guard()
        self.counters["objective_point_attempts"] += 1
        if trial_index is not None:
            self.counters["backtracking_trials_attempted"] += 1
        row = {"event": "objective_point", "origin": "initial" if trial_index is None else "backtracking_trial",
               "objective_point_attempt": self.counters["objective_point_attempts"],
               "trial_index": trial_index, "alpha_angstrom": alpha,
               "outcome": "evaluation_started", **_coordinate_document(xyz)}
        self.attempts.append(row)
        started = time.perf_counter()
        try:
            require(np.isfinite(xyz).all(), "finite_candidate_coordinates_required")
            raw = self.call("objective", self.objective, torch.from_numpy(xyz.copy()), coordinate_argument=True)
            numeric_error = None
            try:
                energy, gradient, internal, internal_gradient, components = raw
                energy, internal = float(energy), float(internal)
                for value in (gradient, internal_gradient):
                    require(isinstance(value, torch.Tensor) and value.shape == self.xyz.shape
                            and value.dtype == torch.float64 and value.device.type == "cpu"
                            and bool(torch.isfinite(value).all()), "finite_cpu_float64_gradient_required")
                gradient = gradient.detach().numpy().copy()
                internal_gradient = internal_gradient.detach().numpy().copy()
                components = {name: float(value) for name, value in components.items()}
                require(math.isfinite(energy) and math.isfinite(internal)
                        and math.isfinite(atom_norm(gradient)) and math.isfinite(atom_norm(internal_gradient))
                        and all(math.isfinite(value) for value in components.values()), "finite_objective_values_required")
                row.update(total_energy_kcal_mol=energy, total_gradient_kcal_mol_angstrom=gradient.tolist(),
                           internal_energy_kcal_mol=internal, internal_gradient_kcal_mol_angstrom=internal_gradient.tolist(),
                           components=components, raw_maximum_atom_force_kcal_mol_angstrom=atom_norm(gradient))
            except Exception as exc:
                self.counters["invalid_objective_results"] += 1
                numeric_error = exc
                row["objective_result_error"] = {"type": type(exc).__name__, "reason": str(exc)}
            # Geometry is deliberately not skipped for energy/strain rejection or
            # a normally returned objective whose numerical result is unusable.
            validity = self.call("validity", self.validity, torch.from_numpy(xyz.copy()), coordinate_argument=True)
            try:
                require(isinstance(validity, dict) and type(validity.get("complete")) is bool
                        and type(validity.get("valid")) is bool, "explicit_complete_and_valid_booleans_required")
                row["full_validity"] = copy.deepcopy(validity)
            except Exception as exc:
                raise EvaluationStop("validity_result", exc) from exc
            if numeric_error is not None:
                raise EvaluationStop("objective_result", numeric_error) from numeric_error
            changes = np.asarray([float(np.linalg.norm(xyz[i] - xyz[j])) - length
                                  for (i, j), length in zip(bonds, lengths, strict=True)])
            require(np.isfinite(changes).all(), "finite_original_bond_changes_required")
            strain = 0.0 if initial is None else internal - initial["internal_energy_kcal_mol"]
            require(math.isfinite(strain), "finite_internal_increase_required")
            strain_limit = protocol["internal_increase_limit_kcal_mol"]
            bond_limit = protocol["original_bond_length_change_limit_angstrom"]
            checks = {"strain_within_exact_limit": strain <= strain_limit,
                      "original_bonds_within_exact_limit": bool(np.all(np.abs(changes) <= bond_limit)),
                      "complete_full_validity": validity["complete"] and validity["valid"]}
            row.update(internal_increase_from_original_kcal_mol=strain,
                       original_bond_length_changes_angstrom=changes.tolist(),
                       maximum_original_bond_length_change_angstrom=float(np.max(np.abs(changes), initial=0.0)),
                       normalized_constraints=[(strain_limit - strain) / strain_limit]
                           + [slack for change in changes for slack in
                              ((bond_limit + float(change)) / bond_limit, (bond_limit - float(change)) / bond_limit)])
            if initial is not None:
                bound = initial["total_energy_kcal_mol"] + protocol["armijo_c1"] * alpha * direction_dot_gradient
                require(math.isfinite(bound), "finite_armijo_bound_required")
                row["armijo_upper_bound_kcal_mol"] = bound
                checks.update(strict_total_energy_decrease=energy < initial["total_energy_kcal_mol"],
                              armijo_sufficient_decrease=energy <= bound,
                              distinct_original_coordinates=coordinate_key(xyz) != self.key)
            row.update(checks=checks, eligible=all(checks.values()),
                       outcome=("initial_feasible" if initial is None else "accepted") if all(checks.values())
                       else ("initial_infeasible" if initial is None else "rejected"))
        except Exception as exc:
            row.update(outcome="source_integrity_failure" if isinstance(exc, IntegrityStop) else "evaluation_failure",
                       error={"type": type(exc).__name__, "reason": str(exc),
                              "stage": getattr(exc, "stage", None)})
            raise
        finally:
            row["point_evaluation_wall_seconds"] = time.perf_counter() - started
            # The in-memory ledger remains available even if the record callback
            # itself fails or integrity prevents further external publication.
            if self.integrity_error is None:
                try:
                    self.publish(row)
                except Exception as exc:
                    row.update(outcome="source_integrity_failure" if isinstance(exc, IntegrityStop) else "record_failure",
                               error={"type": type(exc).__name__, "reason": str(exc), "stage": "record"})
                    raise
        return row


def feasible_armijo_step(original, bonds, objective, validity, record, *, intact=lambda: None, protocol=None):
    """Return an independent retained CPU float64 snapshot and complete report.

Objective returns ``(F, g, I, gI, components)`` as in constrained_refinement_core.
Validity returns explicit ``complete`` and ``valid`` booleans plus details.
Only reduced budgets may override the frozen protocol. Failures stop the run,
and an observed integrity violation permanently revokes candidate selection.
"""
    started = time.perf_counter()
    configured = dict(PROTOCOL)
    if protocol is not None:
        require(isinstance(protocol, dict) and set(protocol) <= set(PROTOCOL), "unknown_protocol_field")
        configured.update(protocol)
    for key, value in PROTOCOL.items():
        if key in ("max_backtracking_trials", "max_objective_point_attempts"):
            require(type(configured[key]) is int and 1 <= configured[key] <= value, "bounded_positive_integer_budget_required:" + key)
        else:
            require(type(configured[key]) is type(value) and configured[key] == value, "frozen_protocol_field_changed:" + key)
    protocol = configured
    require(isinstance(original, torch.Tensor) and original.ndim == 2 and original.shape[1] == 3
            and original.numel() > 0 and original.dtype == torch.float64 and original.device.type == "cpu"
            and bool(torch.isfinite(original).all()), "finite_cpu_float64_original_coordinates_required")
    require(type(bonds) is tuple and all(type(pair) is tuple and len(pair) == 2
            and all(type(i) is int and 0 <= i < len(original) for i in pair) and pair[0] != pair[1]
            for pair in bonds), "explicit_original_bond_index_pairs_required")
    require(len({tuple(sorted(pair)) for pair in bonds}) == len(bonds), "duplicate_original_bond_pairs")
    require(all(callable(callback) for callback in (objective, validity, record, intact)), "callable_callbacks_required")
    run = _Run(original, objective, validity, record, intact)
    lengths = tuple(float(np.linalg.norm(run.xyz[i] - run.xyz[j])) for i, j in bonds)
    require(all(math.isfinite(length) and length > 0 for length in lengths), "positive_original_bond_lengths_required")
    initial, selected, direction, slope = None, None, None, None
    termination, error = "backtracking_exhausted", None
    try:
        initial = run.evaluate(run.xyz, None, None, None, None, bonds, lengths, protocol)
        if not initial["eligible"]:
            termination = "initial_not_fully_feasible"
        elif initial["raw_maximum_atom_force_kcal_mol_angstrom"] == 0.0:
            termination = "zero_original_gradient"
        else:
            gradient = np.asarray(initial["total_gradient_kcal_mol_angstrom"])
            direction = -gradient / initial["raw_maximum_atom_force_kcal_mol_angstrom"]
            slope = float(np.sum(gradient * direction))
            require(math.isfinite(slope) and slope < 0, "finite_strict_descent_direction_required")
            for trial_index in range(protocol["max_backtracking_trials"]):
                if run.counters["objective_point_attempts"] >= protocol["max_objective_point_attempts"]:
                    termination = "objective_point_budget_exhausted"
                    break
                alpha = protocol["initial_alpha_angstrom"] * protocol["backtracking_factor"] ** trial_index
                point = run.evaluate(run.xyz + alpha * direction, trial_index, alpha, initial,
                                     slope, bonds, lengths, protocol)
                if point["eligible"]:
                    selected, termination = point, "first_feasible_armijo_step"
                    break
        run.guard()
        run.publish({"event": "single_step_selection", "termination": termination,
                     "selected_objective_point_attempt": None if selected is None else selected["objective_point_attempt"],
                     "step_accepted": selected is not None, "product_status": "NOT_ADMITTED"})
        run.guard()
    except Exception as exc:
        termination = "source_integrity_failure" if isinstance(exc, IntegrityStop) else "evaluation_or_callback_failure"
        error = {"type": type(exc).__name__, "reason": str(exc), "stage": getattr(exc, "stage", None)}
        selected = None
    integrity_valid = run.integrity_error is None
    final = selected if selected is not None else initial
    # If initial evaluation failed, expose its genuine partial observation;
    # missing energies or gradients remain absent rather than fabricated.
    if final is None and run.attempts:
        final = run.attempts[0]
    retained = run.xyz.copy() if selected is None else np.asarray(selected["coordinates_angstrom"]).copy()
    raw_norm = None if final is None else final.get("raw_maximum_atom_force_kcal_mol_angstrom")
    report = {"schema_id": "feasible_armijo_single_step_research_report/1.0.0",
              "status": "INVALID_SOURCE_INTEGRITY" if not integrity_valid else
                        "FEASIBLE_ENERGY_LOWERING_STEP" if selected is not None else "ORIGINAL_RETAINED",
              "termination": termination, "error": error, "protocol": protocol,
              "source_integrity_valid": integrity_valid, "integrity_error": run.integrity_error,
              "step_accepted": selected is not None, "initial": copy.deepcopy(initial), "final": copy.deepcopy(final),
              "retained_coordinates": _coordinate_document(retained),
              "original_bond_lengths_angstrom": list(lengths),
              "direction": None if direction is None else direction.tolist(),
              "original_gradient_dot_direction": slope,
              "accepted_trial_index": None if selected is None else selected["trial_index"],
              "accepted_alpha_angstrom": None if selected is None else selected["alpha_angstrom"],
              "raw_force_converged": integrity_valid and raw_norm is not None
                    and raw_norm <= protocol["raw_maximum_atom_force_tolerance_kcal_mol_angstrom"],
              "product_status": "NOT_ADMITTED", "product_qualified": False, "product_solver_changed": False,
              "convergence_claimed": False, "performance_comparison": False,
              "attempts": copy.deepcopy(run.attempts), "counters": dict(run.counters),
              "whole_wall_seconds": time.perf_counter() - started,
              "timings_are_inclusive_do_not_sum_nested_scopes": True}
    return torch.from_numpy(retained), report
