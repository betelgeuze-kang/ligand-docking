"""Bounded research trajectory reusing the exact-feasible single-point pipeline.

Original strain and bond references are immutable. A successfully published step
is the only commit point; this module never grants product admission.
"""
from __future__ import annotations

import copy
import math
import time

import numpy as np
import torch

from .feasible_step_core import (
    PROTOCOL as STEP_PROTOCOL, IntegrityStop, _Run, _coordinate_document, require,
)


PROTOCOL = {
    **STEP_PROTOCOL,
    "algorithm": "research_repeated_feasible_armijo_trajectory_v1",
    "direction": "negative_current_total_gradient_maximum_atom_norm_one",
    "max_accepted_steps": 32,
    "max_objective_point_attempts": 129,
    "selection": "first_exact_feasible_strict_energy_decrease_and_current_armijo_trial",
    "failure_policy": "stop_and_retain_last_published_incumbent_integrity_revokes_to_original",
}


def _delta(after, before):
    return {key: after[key] - before[key] for key in after}


def _error(exc):
    return {"type": type(exc).__name__, "reason": str(exc), "stage": getattr(exc, "stage", None)}


class _TrajectoryRun(_Run):
    """Add chronology and counter evidence without duplicating evaluation rules."""

    def __init__(self, *args):
        super().__init__(*args)
        self.counters["accepted_steps"] = 0
        self.publications = []
        self.step_index = None

    def publish(self, row):
        if row["event"] == "objective_point":
            row["step_index"] = self.step_index
        before = dict(self.counters)
        publication = {"publication_index": len(self.publications) + 1,
                       "event": copy.deepcopy(row), "succeeded": False, "error": None}
        self.publications.append(publication)
        try:
            super().publish(row)
            publication["succeeded"] = True
        except Exception as exc:
            publication["error"] = _error(exc)
            raise
        finally:
            publication["counter_delta"] = _delta(self.counters, before)

    def evaluate(self, *args, **kwargs):
        before, count = dict(self.counters), len(self.attempts)
        try:
            return super().evaluate(*args, **kwargs)
        finally:
            for row in self.attempts[count:]:
                row["step_index"] = self.step_index
                row["counter_delta"] = _delta(self.counters, before)


def feasible_armijo_trajectory(original, bonds, objective, validity, record, *,
                              intact=lambda: None, protocol=None):
    """Return retained CPU float64 coordinates and a complete chronological report.

Callbacks match ``feasible_armijo_step``. Only reductions to the three frozen
budgets are permitted. Ordinary failures retain the last step whose selection
publication succeeded; sticky source failures revoke all trusted selection.
"""
    started = time.perf_counter()
    configured = dict(PROTOCOL)
    if protocol is not None:
        require(isinstance(protocol, dict) and set(protocol) <= set(PROTOCOL), "unknown_protocol_field")
        configured.update(protocol)
    budgets = {"max_accepted_steps", "max_backtracking_trials", "max_objective_point_attempts"}
    for key, value in PROTOCOL.items():
        if key in budgets:
            require(type(configured[key]) is int and 1 <= configured[key] <= value,
                    "bounded_positive_integer_budget_required:" + key)
        else:
            require(type(configured[key]) is type(value) and configured[key] == value,
                    "frozen_protocol_field_changed:" + key)
    protocol = configured
    require(isinstance(original, torch.Tensor) and original.ndim == 2 and original.shape[1] == 3
            and original.numel() > 0 and original.dtype == torch.float64 and original.device.type == "cpu"
            and bool(torch.isfinite(original).all()), "finite_cpu_float64_original_coordinates_required")
    require(type(bonds) is tuple and all(type(pair) is tuple and len(pair) == 2
            and all(type(i) is int and 0 <= i < len(original) for i in pair) and pair[0] != pair[1]
            for pair in bonds), "explicit_original_bond_index_pairs_required")
    require(len({tuple(sorted(pair)) for pair in bonds}) == len(bonds), "duplicate_original_bond_pairs")
    require(all(callable(callback) for callback in (objective, validity, record, intact)), "callable_callbacks_required")
    run = _TrajectoryRun(original, objective, validity, record, intact)
    lengths = tuple(float(np.linalg.norm(run.xyz[i] - run.xyz[j])) for i, j in bonds)
    require(all(math.isfinite(length) and length > 0 for length in lengths), "positive_original_bond_lengths_required")
    initial, incumbent, error = None, None, None
    steps = []
    termination = "initial_not_fully_feasible"
    try:
        initial = run.evaluate(run.xyz, None, None, None, None, bonds, lengths, protocol)
        if initial["eligible"]:
            incumbent = initial
            while True:
                run.guard()
                if incumbent["raw_maximum_atom_force_kcal_mol_angstrom"] <= protocol["raw_maximum_atom_force_tolerance_kcal_mol_angstrom"]:
                    termination = "raw_force_tolerance_met"
                    break
                if run.counters["accepted_steps"] >= protocol["max_accepted_steps"]:
                    termination = "accepted_step_budget_exhausted"
                    break
                if run.counters["objective_point_attempts"] >= protocol["max_objective_point_attempts"]:
                    termination = "objective_point_budget_exhausted"
                    break
                gradient = np.asarray(incumbent["total_gradient_kcal_mol_angstrom"])
                direction = -gradient / incumbent["raw_maximum_atom_force_kcal_mol_angstrom"]
                slope = float(np.sum(gradient * direction))
                require(np.isfinite(direction).all() and math.isfinite(slope) and slope < 0,
                        "finite_strict_descent_direction_required")
                run.step_index = run.counters["accepted_steps"] + 1
                step = {"step_index": run.step_index,
                        "base_objective_point_attempt": incumbent["objective_point_attempt"],
                        "direction": direction.tolist(), "base_gradient_dot_direction": slope,
                        "trial_objective_point_attempts": [], "proposed_accepted_objective_point_attempt": None,
                        "accepted_objective_point_attempt": None, "publication_index": None,
                        "published": False, "outcome": "in_progress"}
                steps.append(step)
                before = dict(run.counters)
                try:
                    base_xyz = np.asarray(incumbent["coordinates_angstrom"])
                    for trial_index in range(protocol["max_backtracking_trials"]):
                        if run.counters["objective_point_attempts"] >= protocol["max_objective_point_attempts"]:
                            break
                        alpha = protocol["initial_alpha_angstrom"] * protocol["backtracking_factor"] ** trial_index
                        count = len(run.attempts)
                        try:
                            point = run.evaluate(base_xyz + alpha * direction, trial_index, alpha, initial,
                                                 slope, bonds, lengths, protocol, armijo_base=incumbent)
                        finally:
                            step["trial_objective_point_attempts"].extend(
                                row["objective_point_attempt"] for row in run.attempts[count:])
                        if point["eligible"]:
                            step["proposed_accepted_objective_point_attempt"] = point["objective_point_attempt"]
                            step["publication_index"] = len(run.publications) + 1
                            run.publish({"event": "trajectory_step_selection", "step_index": run.step_index,
                                         "base_objective_point_attempt": incumbent["objective_point_attempt"],
                                         "selected_objective_point_attempt": point["objective_point_attempt"],
                                         "step_accepted": True, "product_status": "NOT_ADMITTED"})
                            # No callback can fail between successful publication and this commit.
                            incumbent = point
                            run.counters["accepted_steps"] += 1
                            step.update(published=True, outcome="accepted",
                                        accepted_objective_point_attempt=point["objective_point_attempt"])
                            break
                    if not step["published"]:
                        termination = ("objective_point_budget_exhausted"
                                       if run.counters["objective_point_attempts"] >= protocol["max_objective_point_attempts"]
                                       else "backtracking_blocked")
                        step["outcome"] = termination
                        break
                except Exception as exc:
                    step["outcome"] = "source_integrity_failure" if isinstance(exc, IntegrityStop) else "evaluation_or_callback_failure"
                    raise
                finally:
                    step["counter_delta"] = _delta(run.counters, before)
        run.guard()
        run.publish({"event": "trajectory_selection", "termination": termination,
                     "accepted_steps": run.counters["accepted_steps"],
                     "selected_objective_point_attempt": None if incumbent is None else incumbent["objective_point_attempt"],
                     "product_status": "NOT_ADMITTED"})
        run.guard()
    except Exception as exc:
        termination = "source_integrity_failure" if isinstance(exc, IntegrityStop) else "evaluation_or_callback_failure"
        error = _error(exc)
    integrity_valid = run.integrity_error is None
    trusted = incumbent if integrity_valid else initial
    final = trusted if trusted is not None else initial
    if final is None and run.attempts:
        final = run.attempts[0]
    retained = (np.asarray(incumbent["coordinates_angstrom"]).copy()
                if integrity_valid and incumbent is not None else run.xyz.copy())
    accepted = run.counters["accepted_steps"]
    report = {"schema_id": "feasible_armijo_trajectory_research_report/1.0.0",
              "status": "INVALID_SOURCE_INTEGRITY" if not integrity_valid else
                        "PUBLISHED_FEASIBLE_INCUMBENT_RETAINED" if accepted else "ORIGINAL_RETAINED",
              "termination": termination, "error": error, "protocol": protocol,
              "source_integrity_valid": integrity_valid, "integrity_error": run.integrity_error,
              "accepted_steps": accepted, "trusted_accepted_steps": accepted if integrity_valid else 0,
              "accepted_objective_point_attempts": [step["accepted_objective_point_attempt"]
                                                     for step in steps if step["published"]],
              "selection_revoked": not integrity_valid, "initial": copy.deepcopy(initial),
              "final": copy.deepcopy(final), "retained_coordinates": _coordinate_document(retained),
              "retained_objective_point_attempt": None if final is None else final["objective_point_attempt"],
              "original_bond_lengths_angstrom": list(lengths),
              "raw_force_converged": integrity_valid and error is None and termination == "raw_force_tolerance_met",
              "product_status": "NOT_ADMITTED", "product_qualified": False, "product_solver_changed": False,
              "convergence_claimed": False, "performance_comparison": False,
              "attempts": copy.deepcopy(run.attempts), "steps": copy.deepcopy(steps),
              "publications": copy.deepcopy(run.publications), "counters": dict(run.counters),
              "whole_wall_seconds": time.perf_counter() - started,
              "timings_are_inclusive_do_not_sum_nested_scopes": True}
    return torch.from_numpy(retained), report
