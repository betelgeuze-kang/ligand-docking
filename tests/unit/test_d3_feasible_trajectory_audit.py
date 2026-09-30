"""Independent manual ledgers, targeted corruption, and synthetic-core compatibility."""
import copy
import hashlib

import numpy as np
import pytest

from docs.research.human_5ht6_d3_complex.audit_feasible_trajectory import FROZEN_PROTOCOL, audit_trajectory


COUNTERS = (
    "objective_point_attempts", "backtracking_trials_attempted", "objective_calls",
    "completed_objective_calls", "failed_objective_calls", "invalid_objective_results",
    "validity_calls", "failed_validity_calls", "record_calls", "failed_record_calls",
    "integrity_checks", "failed_integrity_checks", "accepted_steps",
)


def counts(**values):
    return {key: values.get(key, 0) for key in COUNTERS}


def coordinate_document(xyz):
    return {"coordinates_angstrom": xyz.tolist(),
            "coordinate_bytes_sha256": hashlib.sha256(xyz.tobytes(order="C")).hexdigest()}


def manual_packet(mode="accepted", *, bond=False):
    """Explicitly evaluate preselected linear-function points; never run an optimizer.

    One atom uses E=-x, I=60*x.  The accepted states are x=.05 and
    x=.05+.025, with x=.10 rejected by accumulated strain. A two-atom
    variant uses E=x0-x1, I=0, so original bond drift is decisive instead.
    """
    repeated = mode == "repeated"
    original = np.array([[0., 0., 0.], [1., 0., 0.]]) if bond else np.array([[1e16 if repeated else 0., 0., 0.]])
    bonds = ((0, 1),) if bond else ()
    gradient = np.array([[1., 0., 0.], [-1., 0., 0.]]) if bond else np.array([[-1., 0., 0.]])
    direction = -gradient
    slope = float(np.sum(gradient * direction))
    lengths = [float(np.linalg.norm(original[i] - original[j])) for i, j in bonds]
    protocol = dict(FROZEN_PROTOCOL, max_accepted_steps=2)
    if mode == "blocked":
        protocol["max_backtracking_trials"] = 1
    if repeated:
        protocol["max_backtracking_trials"] = 2
    attempts, steps, publications, native = [], [], [], []

    def publish(event):
        publication = {"publication_index": len(publications) + 1,
                       "event": copy.deepcopy(event), "succeeded": True, "error": None,
                       "counter_delta": counts(record_calls=1, integrity_checks=2)}
        publications.append(publication)
        return publication["publication_index"]

    def point(xyz, step_index=None, trial_index=None, base=None):
        index = len(attempts) + 1
        total = float(np.sum(gradient * xyz))
        internal = 0. if bond or repeated else float(60 * xyz[0, 0])
        internal_gradient = np.zeros_like(xyz)
        if not bond and not repeated:
            internal_gradient[0, 0] = 60.
        changes = np.array([float(np.linalg.norm(xyz[i] - xyz[j])) - length
                            for (i, j), length in zip(bonds, lengths, strict=True)])
        alpha = None if trial_index is None else .05 * .5 ** trial_index
        checks = {"strain_within_exact_limit": internal <= 5.,
                  "original_bonds_within_exact_limit": bool(np.all(np.abs(changes) <= .15)),
                  "complete_full_validity": True}
        row = {"event": "objective_point", "origin": "initial" if base is None else "backtracking_trial",
               "objective_point_attempt": index, "step_index": step_index, "trial_index": trial_index,
               "alpha_angstrom": alpha, **coordinate_document(xyz),
               "total_energy_kcal_mol": total, "internal_energy_kcal_mol": internal,
               "total_gradient_kcal_mol_angstrom": gradient.tolist(),
               "internal_gradient_kcal_mol_angstrom": internal_gradient.tolist(), "components": {},
               "raw_maximum_atom_force_kcal_mol_angstrom": 1.,
               "full_validity": {"complete": True, "valid": True},
               "internal_increase_from_original_kcal_mol": internal,
               "original_bond_length_changes_angstrom": changes.tolist(),
               "maximum_original_bond_length_change_angstrom": float(np.max(np.abs(changes), initial=0.)),
               "normalized_constraints": [(5. - internal) / 5.] + [slack for change in changes for slack in
                                           ((.15 + float(change)) / .15, (.15 - float(change)) / .15)]}
        if base is not None:
            bound = base["total_energy_kcal_mol"] + 1e-4 * alpha * slope
            row.update(armijo_upper_bound_kcal_mol=bound, armijo_base_objective_point_attempt=base["objective_point_attempt"])
            checks.update(strict_total_energy_decrease=total < base["total_energy_kcal_mol"],
                          armijo_sufficient_decrease=total <= bound,
                          distinct_original_coordinates=not np.array_equal(xyz, original),
                          distinct_current_coordinates=not np.array_equal(xyz, base["coordinates_angstrom"]))
        row.update(checks=checks, eligible=all(checks.values()),
                   outcome="initial_feasible" if base is None else "accepted" if all(checks.values()) else "rejected")
        publish(row)
        row["counter_delta"] = counts(objective_point_attempts=1, backtracking_trials_attempted=int(base is not None),
            objective_calls=1, completed_objective_calls=1, validity_calls=1, record_calls=1, integrity_checks=7)
        attempts.append(row)
        native.append({"status": "completed", "stage": "completed", "objective_point_attempt": index,
                       **{key: copy.deepcopy(row[key]) for key in (
                           "coordinates_angstrom", "coordinate_bytes_sha256", "total_energy_kcal_mol",
                           "internal_energy_kcal_mol", "total_gradient_kcal_mol_angstrom",
                           "internal_gradient_kcal_mol_angstrom", "components")}})
        return row

    initial = point(original)
    incumbent = initial
    sequences = ((0, 1),) if repeated else ((0,), (0,) if mode == "blocked" else (0, 1))
    for step_index, sequence in enumerate(sequences, 1):
        base = incumbent
        trials = [point(np.asarray(base["coordinates_angstrom"]) + .05 * .5 ** j * direction,
                        step_index, j, base) for j in sequence]
        selected = trials[-1]["objective_point_attempt"] if trials[-1]["eligible"] else None
        publication_id = None
        if selected is not None:
            publication_id = publish({"event": "trajectory_step_selection", "step_index": step_index,
                "base_objective_point_attempt": base["objective_point_attempt"], "selected_objective_point_attempt": selected,
                "step_accepted": True, "product_status": "NOT_ADMITTED"})
            incumbent = trials[-1]
        delta = {key: sum(row["counter_delta"][key] for row in trials) for key in COUNTERS}
        if selected is not None:
            delta["record_calls"] += 1
            delta["integrity_checks"] += 2
            delta["accepted_steps"] = 1
        steps.append({"step_index": step_index, "base_objective_point_attempt": base["objective_point_attempt"],
                      "direction": direction.tolist(), "base_gradient_dot_direction": slope,
                      "trial_objective_point_attempts": [row["objective_point_attempt"] for row in trials],
                      "proposed_accepted_objective_point_attempt": selected, "accepted_objective_point_attempt": selected,
                      "publication_index": publication_id, "published": selected is not None,
                      "outcome": "accepted" if selected is not None else "backtracking_blocked", "counter_delta": delta})
    accepted = [step["accepted_objective_point_attempt"] for step in steps if step["published"]]
    termination = "accepted_step_budget_exhausted" if len(accepted) == 2 else "backtracking_blocked"
    publish({"event": "trajectory_selection", "termination": termination, "accepted_steps": len(accepted),
             "selected_objective_point_attempt": incumbent["objective_point_attempt"], "product_status": "NOT_ADMITTED"})
    totals = {key: sum(row["counter_delta"][key] for row in attempts) for key in COUNTERS}
    for key in ("record_calls", "failed_record_calls"):
        totals[key] = sum(publication["counter_delta"][key] for publication in publications)
    totals["accepted_steps"] = len(accepted)
    totals["integrity_checks"] += 2 * (len(accepted) + 1)
    report = {"schema_id": "feasible_armijo_trajectory_research_report/1.0.0", "protocol": protocol,
              "status": "PUBLISHED_FEASIBLE_INCUMBENT_RETAINED" if accepted else "ORIGINAL_RETAINED",
              "initial": copy.deepcopy(initial), "final": copy.deepcopy(incumbent), "attempts": attempts,
              "steps": steps, "publications": publications, "counters": totals, "accepted_steps": len(accepted),
              "accepted_objective_point_attempts": accepted, "trusted_accepted_steps": len(accepted),
              "retained_objective_point_attempt": incumbent["objective_point_attempt"],
              "retained_coordinates": coordinate_document(np.asarray(incumbent["coordinates_angstrom"])),
              "original_bond_lengths_angstrom": lengths, "termination": termination, "error": None,
              "source_integrity_valid": True, "integrity_error": None, "selection_revoked": False,
              "raw_force_converged": False, "product_status": "NOT_ADMITTED", "product_qualified": False,
              "product_solver_changed": False, "convergence_claimed": False, "performance_comparison": False}
    return report, original, bonds, native


def audit(packet, **kwargs):
    report, original, bonds, native = packet
    defaults = {"events": [copy.deepcopy(p["event"]) for p in report["publications"]],
                "native_observations": native, "expected_protocol": dict(report["protocol"])}
    defaults.update(kwargs)
    return audit_trajectory(report, original, bonds, **defaults)


def synchronize_point_copies(report):
    """Allow tampering to reach arithmetic checks rather than duplicate-copy checks."""
    for publication in report["publications"]:
        event = publication["event"]
        if event["event"] == "objective_point":
            row = copy.deepcopy(report["attempts"][event["objective_point_attempt"] - 1])
            row.pop("counter_delta")
            publication["event"] = row
    report["initial"] = copy.deepcopy(report["attempts"][0])
    report["final"] = copy.deepcopy(report["attempts"][report["retained_objective_point_attempt"] - 1])


@pytest.mark.parametrize("mode,bond", [("accepted", False), ("blocked", False), ("repeated", False), ("accepted", True)])
def test_manual_analytic_packets_replay_with_exact_denominators(mode, bond):
    packet = manual_packet(mode, bond=bond)
    receipt = audit(packet)
    assert receipt["passed"], receipt["errors"]
    assert receipt["molecular_force_calls"] == receipt["optimizer_calls"] == 0
    if mode == "blocked":
        assert receipt["retained_objective_point_attempt"] == 2 and receipt["objective_point_attempts"] == 3
    if mode == "repeated":
        assert receipt["native_observations"]["attempt_order"] == [1, 2, 3]
        assert receipt["native_observations"]["unique_coordinates"] == 1


@pytest.mark.parametrize("tamper,expected", [
    ("strain_reset", "original_strain"), ("bond_reset", "original_bond_reference"),
    ("armijo_original", "armijo_bound"), ("gradient_direction", "current_gradient_direction"),
    ("base_identity", "step_base_mismatch"), ("skip_first_eligible", "trial_after_first_eligible"),
    ("counter", "counter_mismatch"), ("force_claim", "force_convergence_mismatch"),
    ("budget", "objective_budget_exceeded"), ("retained_rejection", "retained_incumbent_mismatch"),
    ("truncated", "publication_without_attempt"), ("attempt_order", "attempt_order_mismatch"),
])
def test_coherent_tampering_cannot_change_exact_decisions(tamper, expected):
    packet = manual_packet(bond=tamper == "bond_reset")
    report, _, _, _ = packet
    if tamper == "strain_reset":
        row = report["attempts"][2]
        row["internal_increase_from_original_kcal_mol"] -= report["attempts"][1]["internal_energy_kcal_mol"]
        synchronize_point_copies(report)
    elif tamper == "bond_reset":
        report["original_bond_lengths_angstrom"][0] += .1
    elif tamper == "armijo_original":
        row = report["attempts"][2]
        row["armijo_upper_bound_kcal_mol"] = report["initial"]["total_energy_kcal_mol"] - .000005
        synchronize_point_copies(report)
    elif tamper == "gradient_direction":
        report["steps"][1]["direction"][0][1] = .1
    elif tamper == "base_identity":
        report["steps"][1]["base_objective_point_attempt"] = 1
    elif tamper == "skip_first_eligible":
        report["steps"][0]["trial_objective_point_attempts"] = [2, 3]
    elif tamper == "counter":
        report["counters"]["objective_calls"] += 1
    elif tamper == "force_claim":
        report["raw_force_converged"] = True
    elif tamper == "budget":
        report["protocol"]["max_objective_point_attempts"] = 3
    elif tamper == "retained_rejection":
        report["retained_objective_point_attempt"] = 3
        report["final"] = copy.deepcopy(report["attempts"][2])
    elif tamper == "truncated":
        report["attempts"].pop()
    else:
        report["attempts"][1], report["attempts"][2] = report["attempts"][2], report["attempts"][1]
    receipt = audit(packet)
    assert not receipt["passed"] and expected in receipt["errors"][0], receipt


def test_native_identity_preserves_repeated_coordinate_call_order():
    packet = manual_packet("repeated")
    observations = packet[3]
    observations[1], observations[2] = observations[2], observations[1]
    receipt = audit(packet)
    assert not receipt["passed"] and "native_attempt_order_mismatch" in receipt["errors"][0]


@pytest.mark.parametrize("tamper", ["missing_event", "native_energy", "native_missing", "plan_change", "original_change"])
def test_external_bindings_reject_missing_or_changed_evidence(tamper):
    packet = manual_packet()
    report, original, _, native = packet
    kwargs = {}
    if tamper == "missing_event":
        kwargs["events"] = [p["event"] for p in report["publications"]][1:]
    elif tamper == "native_energy":
        native[2]["total_energy_kcal_mol"] += .01
    elif tamper == "native_missing":
        native.pop(2)
    elif tamper == "plan_change":
        kwargs["expected_protocol"] = dict(report["protocol"], max_accepted_steps=3)
    else:
        original[0, 0] += .01
    assert not audit(packet, **kwargs)["passed"]


def test_omitted_external_inputs_are_disclosed_without_claiming_binding():
    report, original, bonds, _ = manual_packet()
    receipt = audit_trajectory(report, original, bonds)
    assert receipt["passed"]
    assert receipt["native_observations"] is None
    assert not receipt["external_events_checked"] and not receipt["published_plan_protocol_checked"]


@pytest.mark.parametrize("failure", [None, "objective", "geometry", "publication", "integrity"])
def test_actual_core_synthetic_reports_preserve_published_incumbent(failure):
    # The auditor never imports this producer. Integration is confined to tests.
    import torch
    from docs.research.human_5ht6_d3_complex.feasible_trajectory_core import feasible_armijo_trajectory

    events, source = [], [True]
    original = torch.zeros(1, 3, dtype=torch.float64)

    def objective(xyz):
        if float(xyz[0, 0]) > .05 and failure == "objective":
            raise ValueError("synthetic objective failure")
        return float(-xyz[0, 0]), torch.tensor([[-1., 0., 0.]], dtype=torch.float64), float(60 * xyz[0, 0]), torch.tensor([[60., 0., 0.]], dtype=torch.float64), {}

    def validity(xyz):
        if float(xyz[0, 0]) > .05:
            if failure == "geometry":
                raise ValueError("synthetic geometry failure")
            if failure == "integrity":
                source[0] = False
        return {"complete": True, "valid": True}

    def record(row):
        events.append(copy.deepcopy(row))
        if row["event"] == "trajectory_step_selection" and row["step_index"] == 2 and failure == "publication":
            raise OSError("synthetic publication failure")

    _, report = feasible_armijo_trajectory(original, (), objective, validity, record,
        intact=lambda: source[0], protocol={"max_accepted_steps": 2})
    receipt = audit_trajectory(report, original.numpy(), (), events=events)
    assert receipt["passed"], receipt["errors"]
    if failure:
        assert receipt["accepted_steps"] == 1
        assert receipt["retained_objective_point_attempt"] == (1 if failure == "integrity" else 2)
