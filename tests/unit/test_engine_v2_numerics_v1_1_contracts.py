"""Run unchanged 1.0 contract assertions against the explicit 1.1 API.

Only symbols in the *test modules* are rebound by pytest and restored after
an assertion. Production module globals and numerical thresholds are untouched.
This avoids duplicating hundreds of lines of checkpoint/applicability tests.
"""
from __future__ import annotations

import pytest

from betelgeuze_engine_v2.physics import reference_forcefield_v1_1 as physics
from betelgeuze_engine_v2.physics import reference_minimization_v1_1 as minimizer
from tests.unit import test_engine_v2_reference_physics as physics_contracts
from tests.unit import test_engine_v2_reference_minimization as minimizer_contracts


@pytest.mark.parametrize("name", [
    "test_reference_terms_are_finite_conservative_and_not_composable_by_default",
    "test_reference_force_matches_finite_difference",
    "test_translation_rotation_invariance_and_newton_third_law",
    "test_switch_makes_nonbonded_energy_and_force_continuous_at_cutoff",
    "test_periodic_nonbonded_terms_use_neighbor_minimum_image_shift",
    "test_applicability_fails_closed_for_missing_parameters_and_short_neighbor_cutoff",
    "test_parameter_topology_binding_and_bond_coverage_fail_closed",
    "test_stale_neighbor_graph_is_rejected_against_current_coordinates",
    "test_non_angstrom_coordinate_unit_is_rejected",
    "test_periodic_cutoff_must_stay_strictly_below_half_smallest_box_length",
])
def test_v1_1_forcefield_contract(monkeypatch, name):
    for symbol in ("evaluate_reference_force_field", "ReferenceForceFieldProvider"):
        monkeypatch.setattr(physics_contracts, symbol, getattr(physics, symbol))
    getattr(physics_contracts, name)()


@pytest.mark.parametrize("name", [
    "test_minimization_is_deterministic_decreases_energy_and_preserves_claim_blockers",
    "test_checkpoint_restart_is_bit_exact_with_uninterrupted_execution",
    "test_iteration_exhaustion_is_failure_inclusive_and_keeps_decreased_state",
    "test_convergence_on_final_budgeted_iteration_is_not_reported_as_exhaustion",
    "test_bounded_line_search_retains_rejected_failure_row_and_original_state",
    "test_checkpoint_tampering_identity_drift_and_recomputed_value_drift_fail_closed",
    "test_minimization_rejects_non_float64_and_multimodel_sources",
])
def test_v1_1_minimization_contract(monkeypatch, name):
    for symbol in ("ReferenceMinimizationConfig", "minimize_reference_force_field",
                   "require_reference_minimization_checkpoint_document"):
        monkeypatch.setattr(minimizer_contracts, symbol, getattr(minimizer, symbol))
    getattr(minimizer_contracts, name)()


@pytest.mark.parametrize("kwargs,message", [
    ({"max_iterations": 0}, "max_iterations"),
    ({"max_backtracks": 65}, "max_backtracks"),
    ({"backtrack_factor": 1.0}, "backtrack_factor"),
    ({"armijo_constant": 1.0}, "armijo_constant"),
    ({"maximum_atom_displacement_angstrom": 0.0}, "maximum_atom_displacement"),
    ({"max_neighbors": 0}, "max_neighbors"),
])
def test_v1_1_bad_config_rejected(kwargs, message):
    with pytest.raises(minimizer.ReferenceMinimizationError, match=message):
        minimizer.ReferenceMinimizationConfig(**kwargs)
