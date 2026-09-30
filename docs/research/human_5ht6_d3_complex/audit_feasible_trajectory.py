"""Offline reconstruction of a bounded feasible-trajectory decision ledger.

Only recorded observations and NumPy arithmetic are used.  This module does not
import the optimizer or a molecular evaluator.  Passing this audit establishes
recorded decision consistency, not independent physical or energy/force accuracy.
"""
from __future__ import annotations

import copy
import hashlib
import math
from numbers import Real

import numpy as np


FROZEN_PROTOCOL = {
    "algorithm": "research_repeated_feasible_armijo_trajectory_v1",
    "direction": "negative_current_total_gradient_maximum_atom_norm_one",
    "initial_alpha_angstrom": 0.05, "backtracking_factor": 0.5,
    "max_backtracking_trials": 16, "max_objective_point_attempts": 129,
    "max_accepted_steps": 32, "armijo_c1": 1e-4,
    "internal_increase_limit_kcal_mol": 5.0,
    "original_bond_length_change_limit_angstrom": 0.15,
    "raw_maximum_atom_force_tolerance_kcal_mol_angstrom": 0.001,
    "selection": "first_exact_feasible_strict_energy_decrease_and_current_armijo_trial",
    "full_validity_scope": "every_normally_returned_objective_unless_source_integrity_failed",
    "failure_policy": "stop_and_retain_last_published_incumbent_integrity_revokes_to_original",
}
_BUDGETS = {"max_backtracking_trials", "max_objective_point_attempts", "max_accepted_steps"}
_POINT_COUNTERS = ("objective_point_attempts", "backtracking_trials_attempted", "objective_calls",
                   "completed_objective_calls", "failed_objective_calls", "invalid_objective_results",
                   "validity_calls", "failed_validity_calls")
_FAILURES = {"evaluation_or_callback_failure", "source_integrity_failure"}
_POINT_FAILURES = {"evaluation_failure", "source_integrity_failure", "record_failure"}
_NUMERIC_FIELDS = ("total_energy_kcal_mol", "internal_energy_kcal_mol",
                   "total_gradient_kcal_mol_angstrom", "internal_gradient_kcal_mol_angstrom")


class TrajectoryAuditError(ValueError):
    """A recorded trajectory cannot be reconstructed under its frozen rules."""


def _require(condition, message):
    if not condition:
        raise TrajectoryAuditError(message)


def _number(value, label):
    _require(isinstance(value, Real) and not isinstance(value, (bool, np.bool_)),
             label + ":numeric_value_required")
    value = float(value)
    _require(math.isfinite(value), label + ":finite_value_required")
    return value


def _integer(value, label, minimum=0):
    _require(type(value) is int and value >= minimum, label + ":integer_required")
    return value


def _boolean(value, label):
    _require(type(value) is bool, label + ":explicit_boolean_required")
    return value


def _matrix(value, label, shape=None):
    try:
        array = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TrajectoryAuditError(label + ":invalid_matrix") from exc
    _require(array.ndim == 2 and array.shape[0] > 0 and array.shape[1] == 3,
             label + ":nonempty_n_by_three_required")
    _require(bool(np.isfinite(array).all()), label + ":finite_matrix_required")
    _require(shape is None or array.shape == shape, label + ":shape_mismatch")
    return array


def _coordinate_hash(array):
    return hashlib.sha256(np.asarray(array, dtype=np.float64).tobytes(order="C")).hexdigest()


def _coordinates(document, label, shape=None):
    _require(isinstance(document, dict), label + ":coordinate_document_required")
    array = _matrix(document.get("coordinates_angstrom"), label, shape)
    _require(document.get("coordinate_bytes_sha256") == _coordinate_hash(array),
             label + ":coordinate_hash_mismatch")
    return array


def _equal_number(recorded, expected, label):
    # These are replayed float64 operations, not a tolerance around admission.
    # The independently recomputed inequalities below never receive a cushion.
    _require(_number(recorded, label) == expected, label + ":arithmetic_mismatch")


def _equal_array(recorded, expected, label):
    try:
        array = np.asarray(recorded, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TrajectoryAuditError(label + ":invalid_array") from exc
    _require(array.shape == np.asarray(expected).shape and np.array_equal(array, expected),
             label + ":arithmetic_mismatch")


def _maximum_atom_norm(gradient):
    return float(np.hypot.reduce(gradient, axis=1).max())


def _point_math(row, original, bonds, lengths, original_internal, base, slope, alpha):
    """Recompute each admission predicate rather than trusting recorded flags."""
    xyz = _coordinates(row, "point", original.shape)
    total = _number(row.get("total_energy_kcal_mol"), "point.total_energy")
    internal = _number(row.get("internal_energy_kcal_mol"), "point.internal_energy")
    gradient = _matrix(row.get("total_gradient_kcal_mol_angstrom"), "point.gradient", original.shape)
    _matrix(row.get("internal_gradient_kcal_mol_angstrom"), "point.internal_gradient", original.shape)
    components = row.get("components")
    _require(isinstance(components, dict), "point.components_required")
    for name, value in components.items():
        _number(value, "point.component." + str(name))
    _equal_number(row.get("raw_maximum_atom_force_kcal_mol_angstrom"),
                  _maximum_atom_norm(gradient), "point.raw_force")
    changes = np.asarray([float(np.linalg.norm(xyz[i] - xyz[j])) - length
                          for (i, j), length in zip(bonds, lengths, strict=True)])
    strain = 0.0 if base is None else internal - original_internal
    _equal_number(row.get("internal_increase_from_original_kcal_mol"), strain, "point.original_strain")
    _equal_array(row.get("original_bond_length_changes_angstrom"), changes, "point.original_bonds")
    _equal_number(row.get("maximum_original_bond_length_change_angstrom"),
                  float(np.max(np.abs(changes), initial=0.0)), "point.maximum_original_bond_change")
    slacks = [(5.0 - strain) / 5.0] + [slack for change in changes for slack in
              ((0.15 + float(change)) / 0.15, (0.15 - float(change)) / 0.15)]
    _equal_array(row.get("normalized_constraints"), slacks, "point.normalized_constraints")
    validity = row.get("full_validity")
    _require(isinstance(validity, dict), "point.full_validity_required")
    complete = _boolean(validity.get("complete"), "point.validity.complete")
    valid = _boolean(validity.get("valid"), "point.validity.valid")
    checks = {"strain_within_exact_limit": strain <= 5.0,
              "original_bonds_within_exact_limit": bool(np.all(np.abs(changes) <= 0.15)),
              "complete_full_validity": complete and valid}
    if base is not None:
        bound = base["total_energy_kcal_mol"] + 1e-4 * alpha * slope
        _equal_number(row.get("armijo_upper_bound_kcal_mol"), bound, "point.armijo_bound")
        checks.update(strict_total_energy_decrease=total < base["total_energy_kcal_mol"],
                      armijo_sufficient_decrease=total <= bound,
                      distinct_original_coordinates=_coordinate_hash(xyz) != _coordinate_hash(original),
                      distinct_current_coordinates=_coordinate_hash(xyz) != base["coordinate_bytes_sha256"])
        _require(row.get("armijo_base_objective_point_attempt") == base["objective_point_attempt"],
                 "point.armijo_base_identity_mismatch")
    _require(row.get("checks") == checks, "point.admission_checks_mismatch")
    for name, value in row["checks"].items():
        _boolean(value, "point.check." + name)
    eligible = all(checks.values())
    _require(_boolean(row.get("eligible"), "point.eligible") == eligible, "point.eligibility_mismatch")
    return eligible


def _counter_values(values, label, keys=None):
    _require(isinstance(values, dict), label + ":counter_document_required")
    if keys is not None:
        _require(set(values) == set(keys), label + ":counter_keys_mismatch")
    for key, value in values.items():
        if key.endswith("_wall_seconds"):
            _require(_number(value, label + "." + key) >= 0, label + ":negative_time")
        else:
            _integer(value, label + "." + key)
    return values


def _protocol(document, expected):
    _require(isinstance(document, dict) and set(document) == set(FROZEN_PROTOCOL), "protocol_fields_mismatch")
    for key, value in FROZEN_PROTOCOL.items():
        if key in _BUDGETS:
            _require(1 <= _integer(document[key], key) <= value, "protocol_budget_out_of_bounds:" + key)
        else:
            _require(type(document[key]) is type(value) and document[key] == value,
                     "frozen_protocol_changed:" + key)
    if expected is not None:
        _require(document == expected, "published_plan_protocol_mismatch")


def _publication_audit(report, events, counters):
    publications = report["publications"]
    _require(isinstance(publications, list), "publication_array_required")
    by_point, by_step, final = {}, {}, []
    last_point, last_step = 0, 0
    for index, publication in enumerate(publications, 1):
        _require(publication["publication_index"] == index, "publication_order_mismatch")
        succeeded = _boolean(publication["succeeded"], "publication.succeeded")
        _require((publication["error"] is None) == succeeded, "publication_error_status_mismatch")
        delta = _counter_values(publication["counter_delta"], "publication.delta", counters)
        _require(delta["record_calls"] <= 1 and delta["failed_record_calls"] <= delta["record_calls"],
                 "publication_record_count_mismatch")
        _require(all(delta[key] == 0 for key in (*_POINT_COUNTERS, "accepted_steps")),
                 "publication_changed_nonpublication_counter")
        if succeeded:
            _require(delta["record_calls"] == 1 and delta["failed_record_calls"] == 0,
                     "successful_publication_counter_mismatch")
        else:
            _require(index == len(publications) and report["termination"] in _FAILURES,
                     "execution_continued_after_failed_publication")
        event = publication["event"]
        kind = event["event"]
        _require(not final, "publication_after_final_selection")
        if kind == "objective_point":
            point_id = _integer(event["objective_point_attempt"], "publication.point_id", 1)
            _require(point_id == last_point + 1 and point_id not in by_point, "point_publication_order_mismatch")
            by_point[point_id], last_point = publication, point_id
        elif kind == "trajectory_step_selection":
            step_id = _integer(event["step_index"], "publication.step_id", 1)
            _require(step_id == last_step + 1 and event["selected_objective_point_attempt"] == last_point,
                     "step_publication_order_mismatch")
            _require(event["step_accepted"] is True and event["product_status"] == "NOT_ADMITTED",
                     "step_publication_claim_mismatch")
            by_step[step_id], last_step = publication, step_id
        elif kind == "trajectory_selection":
            _require(event["product_status"] == "NOT_ADMITTED", "final_publication_claim_mismatch")
            final.append(publication)
        else:
            raise TrajectoryAuditError("unknown_publication_event")
    for key in ("record_calls", "failed_record_calls"):
        _require(counters[key] == sum(p["counter_delta"][key] for p in publications), "counter_mismatch:" + key)
    if events is not None:
        _require(isinstance(events, list), "external_event_array_required")
        position = 0
        for publication in publications:
            if position < len(events) and events[position] == publication["event"]:
                position += 1
            else:
                _require(not publication["succeeded"], "successful_publication_missing_from_external_ledger")
        _require(position == len(events), "unknown_or_reordered_external_publication")
    return by_point, by_step, final


def _native_audit(observations, attempts, counters):
    if observations is None:
        return None
    _require(isinstance(observations, list), "native_observation_array_required")
    ids, completed, failed, invalid, bound = [], 0, 0, 0, 0
    for observation in observations:
        point_id = _integer(observation["objective_point_attempt"], "native.point_id", 1)
        _require(point_id not in ids and (not ids or point_id > ids[-1]), "native_attempt_order_mismatch")
        _require(point_id <= len(attempts), "native_unknown_attempt")
        row = attempts[point_id - 1]
        _require(row["counter_delta"]["objective_calls"] == 1, "native_call_without_counter")
        xyz = _coordinates(observation, "native", np.asarray(row["coordinates_angstrom"]).shape)
        _require(_coordinate_hash(xyz) == row["coordinate_bytes_sha256"], "native_coordinate_binding_mismatch")
        ids.append(point_id)
        if observation["status"] == "completed":
            completed += 1
            _require(row["counter_delta"]["completed_objective_calls"] == 1, "native_completion_mismatch")
            for field in _NUMERIC_FIELDS:
                if "gradient" in field:
                    _matrix(observation[field], "native." + field, xyz.shape)
                else:
                    _number(observation[field], "native." + field)
                if field in row:
                    _require(observation[field] == row[field], "native_numeric_binding_mismatch:" + field)
            bound += all(field in row for field in _NUMERIC_FIELDS)
        elif observation["status"] == "invalid_result":
            _require(isinstance(observation.get("error"), dict) and "raw_result" in observation,
                     "native_invalid_result_evidence_required")
            _require(row["counter_delta"]["completed_objective_calls"] == 1
                     and row["counter_delta"]["invalid_objective_results"] == 1,
                     "native_invalid_result_counter_mismatch")
            invalid += 1
        else:
            _require(observation["status"] == "failed" and isinstance(observation.get("error"), dict),
                     "native_failure_record_required")
            _require(row["counter_delta"]["failed_objective_calls"] == 1, "native_failure_counter_mismatch")
            failed += 1
    _require(ids == [row["objective_point_attempt"] for row in attempts if row["counter_delta"]["objective_calls"]],
             "native_call_denominator_mismatch")
    _require((completed + invalid, failed, invalid) == (counters["completed_objective_calls"],
             counters["failed_objective_calls"], counters["invalid_objective_results"]),
             "native_status_denominator_mismatch")
    return {"attempt_order": ids, "completed": completed, "failed": failed, "invalid_result": invalid, "fully_bound": bound,
            "unique_coordinates": len({row["coordinate_bytes_sha256"] for row in observations})}


def _audit(report, original_coordinates, bonds, events, native_observations, expected_protocol):
    _require(report["schema_id"] == "feasible_armijo_trajectory_research_report/1.0.0", "report_schema_mismatch")
    protocol = report["protocol"]
    _protocol(protocol, expected_protocol)
    original = _matrix(original_coordinates, "original")
    _require(isinstance(bonds, (tuple, list)), "bond_array_required")
    for pair in bonds:
        _require(isinstance(pair, (tuple, list)) and len(pair) == 2
                 and all(type(i) is int and 0 <= i < len(original) for i in pair) and pair[0] != pair[1],
                 "invalid_original_bond")
    _require(len({tuple(sorted(pair)) for pair in bonds}) == len(bonds), "duplicate_original_bond")
    lengths = [float(np.linalg.norm(original[i] - original[j])) for i, j in bonds]
    _require(all(math.isfinite(value) and value > 0 for value in lengths), "invalid_original_bond_length")
    _equal_array(report["original_bond_lengths_angstrom"], lengths, "original_bond_reference")
    attempts, steps = report["attempts"], report["steps"]
    _require(isinstance(attempts, list) and isinstance(steps, list), "chronological_arrays_required")
    counters = _counter_values(report["counters"], "counters")
    required_counts = {*_POINT_COUNTERS, "accepted_steps", "record_calls", "failed_record_calls",
                       "integrity_checks", "failed_integrity_checks"}
    _require(required_counts <= set(counters), "required_counters_missing")
    _require(len(attempts) <= protocol["max_objective_point_attempts"], "objective_budget_exceeded")
    intact = _boolean(report["source_integrity_valid"], "source_integrity_valid")
    _require((report["integrity_error"] is None) == intact, "sticky_integrity_error_mismatch")
    _require(_boolean(report["selection_revoked"], "selection_revoked") == (not intact), "selection_revocation_mismatch")
    termination = report["termination"]
    _require(termination in _FAILURES or termination in {
        "raw_force_tolerance_met", "accepted_step_budget_exhausted", "objective_point_budget_exhausted",
        "backtracking_blocked", "initial_not_fully_feasible"}, "unknown_termination")
    _require((report["error"] is not None) == (termination in _FAILURES), "termination_error_mismatch")
    _require(intact == (termination != "source_integrity_failure"), "integrity_termination_mismatch")
    point_publications, step_publications, final_publications = _publication_audit(report, events, counters)
    _require(set(point_publications) <= set(range(1, len(attempts) + 1)), "publication_without_attempt")
    for index, row in enumerate(attempts, 1):
        _require(row["event"] == "objective_point" and row["objective_point_attempt"] == index, "attempt_order_mismatch")
        delta = _counter_values(row["counter_delta"], "point.delta", counters)
        _require(delta["objective_point_attempts"] == 1 and delta["backtracking_trials_attempted"] == (index > 1),
                 "point_attempt_counter_mismatch")
        _require(delta["objective_calls"] <= 1 and delta["validity_calls"] <= 1 and delta["accepted_steps"] == 0,
                 "point_call_counter_mismatch")
        _require(delta["completed_objective_calls"] + delta["failed_objective_calls"] == delta["objective_calls"],
                 "point_objective_status_counter_mismatch")
        _require(delta["invalid_objective_results"] <= delta["completed_objective_calls"]
                 and delta["failed_validity_calls"] <= delta["validity_calls"], "point_failure_counter_mismatch")
        if delta["completed_objective_calls"] and row["outcome"] != "source_integrity_failure":
            _require(delta["validity_calls"] == 1, "completed_objective_missing_geometry_call")
        publication = point_publications.get(index)
        if publication is None:
            _require(not intact and index == len(attempts) and row["outcome"] == "source_integrity_failure",
                     "point_publication_missing")
        else:
            payload = copy.deepcopy(row)
            payload.pop("counter_delta")
            if payload != publication["event"]:
                # A failed publication changes the in-memory outcome afterwards.
                _require(not publication["succeeded"] and row["outcome"] in _POINT_FAILURES,
                         "point_publication_payload_mismatch")
                for key in set(payload) | set(publication["event"]):
                    if key not in {"outcome", "error"}:
                        _require(payload.get(key) == publication["event"].get(key), "failed_publication_payload_mismatch")
        _coordinates(row, "point", original.shape)
    for key in _POINT_COUNTERS:
        _require(counters[key] == sum(row["counter_delta"][key] for row in attempts), "counter_mismatch:" + key)
    _require(counters["objective_point_attempts"] == len(attempts), "attempt_denominator_mismatch")
    for key in ("integrity_checks", "failed_integrity_checks"):
        _require(counters[key] >= sum(row["counter_delta"][key] for row in attempts), "integrity_counter_lower_bound:" + key)
    if not intact:
        _require(counters["failed_integrity_checks"] > 0, "integrity_failure_without_counter")
    initial = attempts[0] if attempts else None
    initial_math = False
    if initial is not None:
        _require(_coordinate_hash(original) == initial["coordinate_bytes_sha256"], "initial_not_original")
        _require(initial["step_index"] is None and initial["trial_index"] is None and initial["alpha_angstrom"] is None
                 and initial["origin"] == "initial", "initial_identity_mismatch")
        if "checks" in initial:
            initial_math = _point_math(initial, original, bonds, lengths, None, None, None, None)
            expected_outcome = "initial_feasible" if initial_math else "initial_infeasible"
            _require(initial["outcome"] == expected_outcome or initial["outcome"] in _POINT_FAILURES,
                     "initial_outcome_mismatch")
        else:
            _require(initial["outcome"] in _POINT_FAILURES and termination in _FAILURES, "missing_initial_decision")
    if report["initial"] is not None:
        _require(report["initial"] == initial, "initial_snapshot_mismatch")
    else:
        _require(not attempts or initial["outcome"] in _POINT_FAILURES, "missing_initial_snapshot")
    incumbent = initial if initial_math and initial["outcome"] == "initial_feasible" else None
    original_internal = None if initial is None else initial.get("internal_energy_kcal_mol")
    accepted, assigned, stopped = [], [], False
    for number, step in enumerate(steps, 1):
        _require(not stopped and incumbent is not None, "step_after_failure_or_infeasible_initial")
        _require(number == step["step_index"] == len(accepted) + 1, "step_order_mismatch")
        _require(len(accepted) < protocol["max_accepted_steps"], "accepted_step_budget_exceeded")
        _require(incumbent["raw_maximum_atom_force_kcal_mol_angstrom"] > 0.001, "step_after_force_convergence")
        _require(step["base_objective_point_attempt"] == incumbent["objective_point_attempt"], "step_base_mismatch")
        gradient = np.asarray(incumbent["total_gradient_kcal_mol_angstrom"], dtype=np.float64)
        direction = -gradient / _maximum_atom_norm(gradient)
        slope = float(np.sum(gradient * direction))
        _require(math.isfinite(slope) and slope < 0, "non_descent_step")
        _equal_array(step["direction"], direction, "current_gradient_direction")
        _equal_number(step["base_gradient_dot_direction"], slope, "current_gradient_slope")
        trial_ids = step["trial_objective_point_attempts"]
        _require(isinstance(trial_ids, list) and len(trial_ids) <= protocol["max_backtracking_trials"], "trial_budget_exceeded")
        _require(trial_ids == list(range(len(assigned) + 2, len(assigned) + 2 + len(trial_ids))), "trial_span_mismatch")
        proposed, failed = None, False
        for trial_index, point_id in enumerate(trial_ids):
            _require(proposed is None and not failed, "trial_after_first_eligible_or_failure")
            row = attempts[point_id - 1]
            alpha = 0.05 * 0.5 ** trial_index
            _require(row["step_index"] == number and row["trial_index"] == trial_index
                     and row["origin"] == "backtracking_trial", "trial_identity_mismatch")
            _equal_number(row["alpha_angstrom"], alpha, "trial.alpha")
            expected_xyz = np.asarray(incumbent["coordinates_angstrom"]) + alpha * direction
            _require(row["coordinate_bytes_sha256"] == _coordinate_hash(expected_xyz), "trial_not_on_current_gradient_ray")
            if "checks" in row:
                eligible = _point_math(row, original, bonds, lengths, original_internal, incumbent, slope, alpha)
                _require(row["outcome"] == ("accepted" if eligible else "rejected") or row["outcome"] in _POINT_FAILURES,
                         "trial_outcome_mismatch")
                if eligible and row["outcome"] == "accepted":
                    proposed = point_id
            else:
                _require(row["outcome"] in _POINT_FAILURES, "missing_trial_decision")
            failed = row["outcome"] in _POINT_FAILURES
        assigned.extend(trial_ids)
        _require(step["proposed_accepted_objective_point_attempt"] == proposed, "first_eligible_selection_mismatch")
        published = _boolean(step["published"], "step.published")
        publication = step_publications.get(number)
        if proposed is None:
            _require(publication is None and step["publication_index"] is None and not published, "selection_without_eligible_trial")
        else:
            _require(publication is not None and step["publication_index"] == publication["publication_index"],
                     "step_publication_binding_mismatch")
            event = publication["event"]
            _require(event["base_objective_point_attempt"] == incumbent["objective_point_attempt"]
                     and event["selected_objective_point_attempt"] == proposed, "published_selection_mismatch")
            _require(published == publication["succeeded"], "uncommitted_step_promoted")
        delta = _counter_values(step["counter_delta"], "step.delta", counters)
        for key in _POINT_COUNTERS:
            _require(delta[key] == sum(attempts[i - 1]["counter_delta"][key] for i in trial_ids), "step_counter_mismatch:" + key)
        _require(delta["accepted_steps"] == int(published), "step_accepted_counter_mismatch")
        if published:
            _require(step["accepted_objective_point_attempt"] == proposed and step["outcome"] == "accepted", "published_step_outcome_mismatch")
            incumbent = attempts[proposed - 1]
            accepted.append(proposed)
        else:
            stopped = True
            _require(step["accepted_objective_point_attempt"] is None, "unpublished_accepted_point")
            expected = ("objective_point_budget_exhausted" if len(attempts) >= protocol["max_objective_point_attempts"]
                        else "backtracking_blocked")
            if step["outcome"] not in _FAILURES:
                _require(not failed and proposed is None and step["outcome"] == expected, "blocked_step_outcome_mismatch")
                _require(expected == "objective_point_budget_exhausted" or len(trial_ids) == protocol["max_backtracking_trials"],
                         "backtracking_stopped_early")
            else:
                _require(termination in _FAILURES, "step_failure_missing_run_failure")
    _require(assigned == list(range(2, len(attempts) + 1)), "unassigned_or_missing_trial")
    _require(set(step_publications) == {step["step_index"] for step in steps if step["publication_index"] is not None},
             "extra_step_publication")
    _require(report["accepted_objective_point_attempts"] == accepted and report["accepted_steps"] == len(accepted)
             and counters["accepted_steps"] == len(accepted), "accepted_chain_mismatch")
    _require(report["trusted_accepted_steps"] == (len(accepted) if intact else 0), "trusted_acceptance_mismatch")
    expected_status = ("INVALID_SOURCE_INTEGRITY" if not intact else
                       "PUBLISHED_FEASIBLE_INCUMBENT_RETAINED" if accepted else "ORIGINAL_RETAINED")
    _require(report["status"] == expected_status, "report_status_mismatch")
    selected = incumbent if intact else initial
    if selected is None:
        selected = initial
    retained_id = None if selected is None else selected["objective_point_attempt"]
    _require(report["retained_objective_point_attempt"] == retained_id and report["final"] == selected, "retained_incumbent_mismatch")
    retained = _coordinates(report["retained_coordinates"], "retained", original.shape)
    expected_retained = original if not intact or incumbent is None else np.asarray(incumbent["coordinates_angstrom"])
    _require(_coordinate_hash(retained) == _coordinate_hash(expected_retained), "retained_coordinate_mismatch")
    if termination not in _FAILURES:
        if incumbent is None:
            expected_termination = "initial_not_fully_feasible"
        elif stopped:
            expected_termination = steps[-1]["outcome"]
        elif incumbent["raw_maximum_atom_force_kcal_mol_angstrom"] <= 0.001:
            expected_termination = "raw_force_tolerance_met"
        elif len(accepted) >= protocol["max_accepted_steps"]:
            expected_termination = "accepted_step_budget_exhausted"
        elif len(attempts) >= protocol["max_objective_point_attempts"]:
            expected_termination = "objective_point_budget_exhausted"
        else:
            raise TrajectoryAuditError("premature_trajectory_termination")
        _require(termination == expected_termination, "termination_precedence_mismatch")
        _require(len(final_publications) == 1 and final_publications[0]["succeeded"], "final_publication_missing")
    if final_publications:
        event = final_publications[0]["event"]
        _require(event["accepted_steps"] == len(accepted)
                 and event["selected_objective_point_attempt"] == (None if incumbent is None else incumbent["objective_point_attempt"]),
                 "final_publication_selection_mismatch")
        if termination not in _FAILURES:
            _require(event["termination"] == termination, "final_publication_termination_mismatch")
    _require(report["raw_force_converged"] is (intact and termination == "raw_force_tolerance_met"), "force_convergence_mismatch")
    for key in ("product_qualified", "product_solver_changed", "convergence_claimed", "performance_comparison"):
        _require(report[key] is False, "unsupported_claim:" + key)
    _require(report["product_status"] == "NOT_ADMITTED", "unsupported_product_admission")
    native = _native_audit(native_observations, attempts, counters)
    return {"passed": True, "errors": [], "objective_point_attempts": len(attempts),
            "accepted_steps": len(accepted), "trusted_accepted_steps": len(accepted) if intact else 0,
            "retained_objective_point_attempt": retained_id, "termination": termination,
            "source_integrity_valid": intact, "external_events_checked": events is not None,
            "published_plan_protocol_checked": expected_protocol is not None, "native_observations": native,
            "exact_counter_scope": [*_POINT_COUNTERS, "record_calls", "failed_record_calls", "accepted_steps"],
            "integrity_counters_checked_as_lower_bounds": True,
            "molecular_force_calls": 0, "optimizer_calls": 0, "scientifically_validated": False}


def audit_trajectory(report, original_coordinates, bonds, *, events=None,
                     native_observations=None, expected_protocol=None):
    """Return a pass/fail receipt for recorded decisions, without evaluating forces.

    ``events`` binds external JSONL publications; ``native_observations`` binds
    one chronological event per objective call, including failures and repeated
    coordinates. Omitting either is reported explicitly, not treated as proof of
    an external artifact. Native values are bound, not independently recalculated.
    """
    try:
        return _audit(report, original_coordinates, bonds, events, native_observations, expected_protocol)
    except (ValueError, TypeError, KeyError, IndexError, OverflowError) as exc:
        return {"passed": False, "errors": [type(exc).__name__ + ": " + str(exc)],
                "molecular_force_calls": 0, "optimizer_calls": 0, "scientifically_validated": False}
