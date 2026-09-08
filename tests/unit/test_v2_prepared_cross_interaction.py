"""Fresh fixed-coordinate synthetic checks against independent scalar math.

No prepared molecular data, historical fixtures, solver, training or search is
used here. The oracle neither calls the V2 evaluator nor imports its formulas.
"""

from __future__ import annotations

from contextlib import nullcontext
import copy
from dataclasses import replace
import json
import math

import pytest
import torch

from betelgeuze_engine.product import v2_cross_interaction as adapter
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
    canonical_coordinates_sha256,
    canonical_system_document,
    canonical_system_sha256,
    MolecularIntegrityError,
)
from betelgeuze_engine_v2.physics.reference_forcefield import ReferencePhysicsApplicabilityError
from betelgeuze_engine_v2.molecular.serialization import canonical_json_value


def _system(positions, charges, *, elements=None, bonds=()):
    elements = elements or ["C"] * len(positions)
    numbers = {"H": 1, "C": 6, "N": 7, "O": 8, "F": 9, "P": 15,
               "S": 16, "Cl": 17, "Br": 35, "I": 53, "Si": 14}
    return AllAtomSystem(
        system_id="prepared-cross-synthetic-constants",
        atoms=tuple(Atom(i, f"{element}{i}", element, numbers[element], i,
                         partial_charge_e=charges[i]) for i, element in enumerate(elements)),
        bonds=tuple(Bond(i, a, b, 1.0, source="synthetic") for i, (a, b) in enumerate(bonds)),
        residues=tuple(Residue(i, "SYN", i, i + 1, (i,), entity_type="non_polymer", hetero=True)
                       for i in range(len(positions))),
        chains=tuple(Chain(i, str(i), (i,)) for i in range(len(positions))),
        coordinates=torch.tensor([positions], dtype=torch.float64, device="cpu"),
        provenance=StructureProvenance(source_format="synthetic", source_id="local-numerical-constants",
            source_sha256="d" * 64, parser_name="synthetic-test-constructor", parser_version="1"),
        metadata={"evidence_scope": "synthetic_numerical_test_only"},
    )


def _parameters(system, *, sigma=3.0, epsilon=0.2):
    return [{"atom_index": i, "charge_e": atom.partial_charge_e,
             "sigma_angstrom": sigma, "epsilon_kcal_per_mol": epsilon}
            for i, atom in enumerate(system.atoms)]


def _pair(distance=4.0, *, charges=(0.2, -0.3), sigma=(3.1, 2.9), epsilon=(0.16, 0.25)):
    receptor = _system([[0.0, 0.0, 0.0]], [charges[0]])
    ligand = _system([[distance, 0.0, 0.0]], [charges[1]])
    return (receptor, ligand, _parameters(receptor, sigma=sigma[0], epsilon=epsilon[0]),
            _parameters(ligand, sigma=sigma[1], epsilon=epsilon[1]))


def _evaluate(receptor, ligand, rp, lp, **changes):
    options = {"source_declarations": {
        "coordinate_frame_id": "synthetic-frame", "prepared_state_id": "synthetic-explicit-state",
        "parameter_source_id": "synthetic-constants", "charge_source_id": "synthetic-explicit-charges"},
        "pocket_center_angstrom": [0.0, 0.0, 0.0], "pocket_radius_angstrom": 100.0,
        "cutoff_angstrom": 10.0, "switch_start_angstrom": 8.0,
        "dielectric": 4.0, "screening_kappa_per_angstrom": 0.1}
    options.update(changes)
    return adapter.evaluate_prepared_cross_interaction(receptor, ligand, rp, lp, **options)


def _scalar_pair(distance, rp, lp, *, cutoff=10.0, switch_start=8.0, dielectric=4.0, kappa=0.1):
    """Return independent LJ, Coulomb, and d(total energy)/d(distance)."""
    if distance >= cutoff:
        return 0.0, 0.0, 0.0
    sigma = (rp["sigma_angstrom"] + lp["sigma_angstrom"]) / 2.0
    epsilon = math.sqrt(rp["epsilon_kcal_per_mol"] * lp["epsilon_kcal_per_mol"])
    a6 = (sigma / distance) ** 6
    lj = 4.0 * epsilon * (a6 * a6 - a6)
    d_lj = 24.0 * epsilon * (a6 - 2.0 * a6 * a6) / distance
    coefficient = 332.063713299 * rp["charge_e"] * lp["charge_e"] / dielectric
    coulomb = coefficient * math.exp(-kappa * distance) / distance
    d_coulomb = -coulomb * (kappa + 1.0 / distance)
    switch, derivative = 1.0, 0.0
    if distance > switch_start:
        x = (distance - switch_start) / (cutoff - switch_start)
        switch = 1.0 - 10.0 * x ** 3 + 15.0 * x ** 4 - 6.0 * x ** 5
        derivative = (-30.0 * x ** 2 + 60.0 * x ** 3 - 30.0 * x ** 4) / (cutoff - switch_start)
    return lj * switch, coulomb * switch, (d_lj + d_coulomb) * switch + (lj + coulomb) * derivative


def _oracle(receptor, ligand, rp, lp, **config):
    energies = [[], []]
    receptor_force = [[0.0] * 3 for _ in rp]
    ligand_force = [[0.0] * 3 for _ in lp]
    pairs = []
    for i, position in enumerate(receptor.coordinates[0].tolist()):
        for j, other in enumerate(ligand.coordinates[0].tolist()):
            delta = [other[k] - position[k] for k in range(3)]
            distance = math.sqrt(sum(value * value for value in delta))
            lj, coulomb, derivative = _scalar_pair(distance, rp[i], lp[j], **config)
            energies[0].append(lj)
            energies[1].append(coulomb)
            for axis in range(3):
                force = derivative * delta[axis] / distance
                receptor_force[i][axis] += force
                ligand_force[j][axis] -= force
            if distance <= config.get("cutoff", 10.0):
                pairs.append((i, j))
    return (math.fsum(energies[0]), math.fsum(energies[1]), receptor_force, ligand_force, pairs)


def _assert_oracle(result, state, **config):
    lj, coulomb, receptor_force, ligand_force, pairs = _oracle(*state, **config)
    quantities = result["quantities"]
    assert quantities["cross_lennard_jones_kcal_per_mol"] == pytest.approx(lj, rel=2e-12, abs=2e-12)
    assert quantities["cross_screened_coulomb_kcal_per_mol"] == pytest.approx(coulomb, rel=2e-12, abs=2e-12)
    assert quantities["cross_total_kcal_per_mol"] == pytest.approx(lj + coulomb, rel=2e-12, abs=2e-12)
    torch.testing.assert_close(torch.tensor(quantities["receptor_cross_forces_kcal_per_mol_angstrom"], dtype=torch.float64),
                               torch.tensor(receptor_force, dtype=torch.float64), rtol=2e-11, atol=2e-11)
    torch.testing.assert_close(torch.tensor(quantities["ligand_cross_forces_kcal_per_mol_angstrom"], dtype=torch.float64),
                               torch.tensor(ligand_force, dtype=torch.float64), rtol=2e-11, atol=2e-11)
    assert result["pair_accounting"]["requested_cross_pairs"] == len(state[2]) * len(state[3])
    assert result["pair_accounting"]["cross_pair_indices"] == pairs
    assert result["pair_accounting"]["within_declared_cutoff"] == len(pairs)


@pytest.mark.parametrize("context", [nullcontext, torch.no_grad, torch.inference_mode,
    lambda: torch.autocast(device_type="cpu", dtype=torch.bfloat16)])
def test_caller_gradient_inference_and_autocast_contexts_preserve_float64_math(context):
    state = _pair(6.1)
    with context():
        result = _evaluate(*state)
    _assert_oracle(result, state)


@pytest.mark.parametrize("distance", [2.6, 3.0, 4.1, 8.0, 8.7, 9.9, 10.0, 10.1])
@pytest.mark.parametrize("charges", [(0.0, 0.0), (0.2, -0.3), (0.2, 0.3)])
def test_pair_scalar_energy_and_analytic_force(distance, charges):
    state = _pair(distance, charges=charges)
    _assert_oracle(_evaluate(*state), state)


@pytest.mark.parametrize("axis", [0, 1, 2])
def test_switch_force_is_coordinate_derivative_of_independent_scalar_energy(axis):
    receptor, ligand, rp, lp = _pair()
    ligand = replace(ligand, coordinates=torch.tensor([[[8.2, 1.5, -2.0]]], dtype=torch.float64))
    result = _evaluate(receptor, ligand, rp, lp)
    step = 1e-5
    values = []
    for sign in (-1, 1):
        coordinates = ligand.coordinates.clone()
        coordinates[0, 0, axis] += sign * step
        shifted = replace(ligand, coordinates=coordinates)
        lj, coulomb, *_ = _oracle(receptor, shifted, rp, lp)
        values.append(lj + coulomb)
    negative_gradient = -(values[1] - values[0]) / (2 * step)
    assert result["quantities"]["ligand_cross_forces_kcal_per_mol_angstrom"][0][axis] == pytest.approx(
        negative_gradient, rel=2e-8, abs=2e-10)
    # This case is inside the switch. Omitting U * dS/dr is observably wrong.
    distance = float(torch.linalg.vector_norm(ligand.coordinates[0, 0]))
    _, _, full_derivative = _scalar_pair(distance, rp[0], lp[0])
    _, _, unswitched_derivative = _scalar_pair(distance, rp[0], lp[0], switch_start=9.5)
    x = (distance - 8.0) / 2.0
    switch = 1 - 10 * x ** 3 + 15 * x ** 4 - 6 * x ** 5
    assert abs(full_derivative - unswitched_derivative * switch) > 0.01


@pytest.mark.parametrize("zero_side", [0, 1])
def test_explicit_zero_sigma_epsilon_preserves_source_and_coulomb(zero_side, monkeypatch):
    state = list(_pair())
    state[2 + zero_side][0]["sigma_angstrom"] = 0.0
    state[2 + zero_side][0]["epsilon_kcal_per_mol"] = 0.0
    seen = []
    original = adapter.evaluate_reference_force_field

    def observe(system, graph, parameters):
        seen.append(parameters.atom_parameters)
        return original(system, graph, parameters)

    monkeypatch.setattr(adapter, "evaluate_reference_force_field", observe)
    result = _evaluate(*state)
    _assert_oracle(result, state)
    assert result["quantities"]["cross_lennard_jones_kcal_per_mol"] == 0.0
    assert result["quantities"]["cross_screened_coulomb_kcal_per_mol"] != 0.0
    assert len(seen) == 1
    assert seen[0][zero_side].sigma_angstrom == 1.0
    assert seen[0][zero_side].epsilon_kcal_per_mol == 0.0
    side = ("receptor", "ligand")[zero_side]
    assert result["sources"][side]["nonbonded_parameters"] == state[2 + zero_side]
    assert result["source_zero_sigma_projection"] == [{"side": side, "atom_index": 0,
        "source_sigma_angstrom": 0.0, "source_epsilon_kcal_per_mol": 0.0,
        "unused_kernel_sigma_angstrom": 1.0}]


def test_zero_evaluated_terms_remain_distinct_from_unevaluated_nulls():
    state = _pair(charges=(0.0, 0.0), epsilon=(0.0, 0.0), sigma=(0.0, 0.0))
    result = _evaluate(*state)
    _assert_oracle(result, state)
    for key in ("cross_lennard_jones_kcal_per_mol", "cross_screened_coulomb_kcal_per_mol", "cross_total_kcal_per_mol"):
        assert type(result["quantities"][key]) is float
        assert result["quantities"][key] == 0.0
    for key in ("internal_energy", "strain", "solvation", "residual", "affinity"):
        assert result["quantities"][key] is None
    for key in ("scientifically_validated", "customer_execution", "external_solver_called", "uncertainty_calibrated"):
        assert result[key] is False
    assert result["uncertainty"] is None
    assert result["pair_accounting"]["within_declared_cutoff"] == 1


def _multi_state(count_receptor=4, count_ligand=3):
    receptor = _system([[1.1 * (i % 9), 1.1 * (i // 9), 0.0] for i in range(count_receptor)],
                       [0.02 * (i % 7 - 3) for i in range(count_receptor)])
    ligand = _system([[0.2 + 1.1 * (i % 9), 0.3 + 1.1 * (i // 9), 4.0] for i in range(count_ligand)],
                     [0.03 * (i % 5 - 2) for i in range(count_ligand)])
    rp, lp = _parameters(receptor), _parameters(ligand)
    for rows in (rp, lp):
        for i, row in enumerate(rows):
            row["sigma_angstrom"] = 2.3 + (i % 4) * 0.2
            row["epsilon_kcal_per_mol"] = 0.08 + (i % 3) * 0.02
    return receptor, ligand, rp, lp


def test_rigid_transform_preserves_energy_and_rotates_forces_and_pocket():
    state = _multi_state()
    result = _evaluate(*state)
    rotation = torch.tensor([[0.0, -0.6, 0.8], [1.0, 0.0, 0.0], [0.0, 0.8, 0.6]], dtype=torch.float64)
    translation = torch.tensor([1.25, -12.5, 7.75], dtype=torch.float64)
    transformed = [replace(system, coordinates=system.coordinates @ rotation.T + translation) for system in state[:2]]
    shifted = _evaluate(*transformed, *state[2:], pocket_center_angstrom=translation.tolist())
    _assert_oracle(shifted, (*transformed, *state[2:]))
    assert shifted["quantities"]["cross_total_kcal_per_mol"] == pytest.approx(
        result["quantities"]["cross_total_kcal_per_mol"], rel=2e-12)
    for side in ("receptor", "ligand"):
        name = side + "_cross_forces_kcal_per_mol_angstrom"
        expected = torch.tensor(result["quantities"][name], dtype=torch.float64) @ rotation.T
        torch.testing.assert_close(torch.tensor(shifted["quantities"][name], dtype=torch.float64),
                                   expected, rtol=2e-11, atol=2e-11)


def _permuted(system, rows, order):
    coordinates = system.coordinates[0, order].tolist()
    remapped = _system(coordinates, [system.atoms[i].partial_charge_e for i in order],
                       elements=[system.atoms[i].element for i in order])
    return remapped, [{**rows[old], "atom_index": new} for new, old in enumerate(order)]


def test_source_atom_permutation_preserves_energy_and_force_source_order():
    receptor, ligand, rp, lp = state = _multi_state(65, 3)
    original = _evaluate(*state)
    receptor_order, ligand_order = list(reversed(range(65))), [2, 0, 1]
    reordered_r, reordered_rp = _permuted(receptor, rp, receptor_order)
    reordered_l, reordered_lp = _permuted(ligand, lp, ligand_order)
    changed = _evaluate(reordered_r, reordered_l, reordered_rp, reordered_lp)
    _assert_oracle(changed, (reordered_r, reordered_l, reordered_rp, reordered_lp))
    assert changed["quantities"]["cross_total_kcal_per_mol"] == pytest.approx(
        original["quantities"]["cross_total_kcal_per_mol"], rel=2e-12)
    for side, order in (("receptor", receptor_order), ("ligand", ligand_order)):
        name = side + "_cross_forces_kcal_per_mol_angstrom"
        torch.testing.assert_close(torch.tensor(changed["quantities"][name], dtype=torch.float64),
            torch.tensor(original["quantities"][name], dtype=torch.float64)[order], rtol=2e-11, atol=2e-11)


def test_tiles_call_real_v2_with_bondless_cross_projection_and_source_unchanged(monkeypatch):
    receptor, ligand, rp, lp = _multi_state(65, 65)
    receptor = replace(receptor, bonds=(Bond(0, 0, 1, 1.0, source="synthetic"),))
    state = receptor, ligand, rp, lp
    before = [canonical_system_document(system) for system in state[:2]]
    calls = []
    original = adapter.evaluate_reference_force_field

    def observe(system, graph, parameters):
        assert 2 <= system.atom_count <= 128
        assert system.bonds == ()
        assert parameters.bonds == parameters.angles == parameters.torsions == ()
        sides = [atom.metadata["projection_source_side"] for atom in system.atoms]
        expected_exclusions = {(i, j) for i in range(system.atom_count) for j in range(i + 1, system.atom_count)
                               if sides[i] == sides[j]}
        assert set(parameters.excluded_pairs) == expected_exclusions
        for index, atom in enumerate(system.atoms):
            side = 0 if atom.metadata["projection_source_side"] == "receptor" else 1
            source_index = atom.metadata["projection_source_atom"]
            torch.testing.assert_close(system.coordinates[0, index], state[side].coordinates[0, source_index],
                                       rtol=0, atol=0)
        evaluation = original(system, graph, parameters)
        calls.append((system.atom_count, float(evaluation.term.energy[0])))
        return evaluation

    monkeypatch.setattr(adapter, "evaluate_reference_force_field", observe)
    result = _evaluate(*state)
    _assert_oracle(result, state)
    assert sorted(count for count, _ in calls) == [2, 65, 65, 128]
    assert result["pair_accounting"]["kernel_tiles"] == 4
    assert result["quantities"]["cross_total_kcal_per_mol"] == pytest.approx(math.fsum(value for _, value in calls))
    for i, side in enumerate(("receptor", "ligand")):
        assert canonical_system_document(state[i]) == before[i]
        assert canonical_json_value(result["sources"][side]["system"]) == canonical_json_value(before[i])
        assert result["sources"][side]["system_sha256"] == canonical_system_sha256(state[i])
        assert result["sources"][side]["coordinates_sha256"] == canonical_coordinates_sha256(state[i])
        assert result["sources"][side]["nonbonded_parameters"] == state[i + 2]


def test_exact_outside_cutoff_cull_preserves_denominator_without_kernel_call(monkeypatch):
    state = _pair(10.1)

    def unexpected(*args, **kwargs):
        raise AssertionError("outside-cutoff tile must not call the physics kernel")

    monkeypatch.setattr(adapter, "evaluate_reference_force_field", unexpected)
    result = _evaluate(*state)
    _assert_oracle(result, state)
    assert result["pair_accounting"]["kernel_tiles"] == 0
    assert result["pair_accounting"]["exact_outside_cutoff_tiles"] == 1


@pytest.mark.parametrize("field", ["charge_e", "sigma_angstrom", "epsilon_kcal_per_mol"])
@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), float("-inf"), True, "0"])
def test_missing_nonfinite_or_non_numeric_parameters_are_rejected(field, bad):
    state = list(_pair())
    state[2][0][field] = bad
    with pytest.raises(adapter.PreparedInteractionError):
        _evaluate(*state)


@pytest.mark.parametrize("field", ["charge_e", "sigma_angstrom", "epsilon_kcal_per_mol", "atom_index"])
def test_absent_parameter_fields_are_rejected(field):
    state = list(_pair())
    del state[2][0][field]
    with pytest.raises(adapter.PreparedInteractionError):
        _evaluate(*state)


@pytest.mark.parametrize("change", [
    {"sigma_angstrom": -0.1}, {"epsilon_kcal_per_mol": -0.1},
    {"sigma_angstrom": 0.0, "epsilon_kcal_per_mol": 0.1},
    {"charge_e": 0.0}, {"atom_index": True}, {"atom_index": 1}, {"extra": 1},
])
def test_invalid_parameters_or_charge_mismatch_are_rejected(change):
    state = list(_pair())
    state[2][0].update(change)
    with pytest.raises(adapter.PreparedInteractionError):
        _evaluate(*state)


@pytest.mark.parametrize("change", [
    {"cutoff_angstrom": 0.0}, {"cutoff_angstrom": 20.1}, {"cutoff_angstrom": float("nan")},
    {"switch_start_angstrom": 0.0}, {"switch_start_angstrom": 10.0},
    {"dielectric": 0.0}, {"dielectric": float("inf")}, {"screening_kappa_per_angstrom": -0.1},
    {"pocket_center_angstrom": [0.0, float("nan"), 0.0]}, {"pocket_center_angstrom": [0.0, 0.0]},
    {"pocket_radius_angstrom": 0.0}, {"pocket_radius_angstrom": 3.9},
    {"source_declarations": {}}, {"source_declarations": None},
])
def test_invalid_model_pocket_or_declarations_are_rejected(change):
    with pytest.raises(adapter.PreparedInteractionError):
        _evaluate(*_pair(), **change)


@pytest.mark.parametrize("dtype", [torch.float16, torch.float32])
def test_non_float64_canonical_coordinates_are_rejected(dtype):
    receptor, ligand, rp, lp = _pair()
    with pytest.raises(adapter.PreparedInteractionError):
        _evaluate(replace(receptor, coordinates=receptor.coordinates.to(dtype=dtype)), ligand, rp, lp)


def test_nonfinite_coordinates_are_rejected_before_any_output():
    receptor, ligand, rp, lp = _pair()
    coordinates = receptor.coordinates.clone()
    coordinates[0, 0, 0] = float("nan")
    receptor = replace(receptor, coordinates=coordinates)
    with pytest.raises(ValueError):
        _evaluate(receptor, ligand, rp, lp)


def test_missing_canonical_charge_cannot_be_filled_from_parameters():
    receptor, ligand, rp, lp = _pair()
    receptor = replace(receptor, atoms=(replace(receptor.atoms[0], partial_charge_e=None),))
    with pytest.raises(adapter.PreparedInteractionError):
        _evaluate(receptor, ligand, rp, lp)


def test_cutoff_cannot_bypass_frozen_minimum_pair_distance_domain():
    with pytest.raises(adapter.PreparedInteractionError):
        _evaluate(*_pair(0.2), cutoff_angstrom=0.1, switch_start_angstrom=0.05)


@pytest.mark.parametrize("side", [0, 1])
@pytest.mark.parametrize("distance", [0.0, 0.2, math.nextafter(0.35, 0.0)])
def test_internal_excluded_close_pair_does_not_change_cross_admission_across_tiles(side, distance):
    # The declared all-source minimum must reject even when a same-side pair is
    # separated by the arbitrary 64-atom tile boundary. No cross distance is small.
    positions = [[0.0, 0.0, 0.0]] + [[30.0 + i, 0.0, 0.0] for i in range(63)] + [[distance, 0.0, 0.0]]
    component = _system(positions, [0.1] * 65)
    other = _system([[0.0, 0.0, 4.0]], [-0.1])
    rows, other_rows = _parameters(component), _parameters(other)
    order = [0, 64, *range(1, 64)]
    changed, changed_rows = _permuted(component, rows, order)
    for selected, selected_rows in ((component, rows), (changed, changed_rows)):
        state = ((selected, other, selected_rows, other_rows) if side == 0
                 else (other, selected, other_rows, selected_rows))
        with pytest.raises(adapter.PreparedInteractionError, match="minimum_pair_distance"):
            _evaluate(*state)


@pytest.mark.parametrize("side", [0, 1])
@pytest.mark.parametrize("distance", [0.35, math.nextafter(0.35, 1.0)])
def test_internal_minimum_boundary_is_admitted_without_evaluating_internal_energy(side, distance):
    component = _system([[0.0, 0.0, 0.0], [distance, 0.0, 0.0]], [0.1, 0.2])
    other = _system([[0.0, 0.0, 4.0]], [-0.1])
    rows, other_rows = _parameters(component), _parameters(other)
    state = ((component, other, rows, other_rows) if side == 0 else (other, component, other_rows, rows))
    result = _evaluate(*state)
    _assert_oracle(result, state)
    assert result["model"]["minimum_pair_distance_angstrom"] == 0.35
    assert result["model"]["minimum_distance_scope"] == "all source atoms; admission independent of tile order"
    assert result["quantities"]["internal_energy"] is None


def test_internal_minimum_is_checked_even_when_whole_tile_is_outside_cutoff():
    receptor = _system([[0.0, 0.0, 0.0], [0.2, 0.0, 0.0]], [0.1, 0.2])
    ligand = _system([[0.0, 0.0, 15.0]], [-0.1])
    with pytest.raises(adapter.PreparedInteractionError, match="minimum_pair_distance"):
        _evaluate(receptor, ligand, _parameters(receptor), _parameters(ligand))


def test_input_constructed_in_inference_mode_and_caller_context_is_restored():
    with torch.inference_mode():
        state = _pair(6.1)
        assert state[0].coordinates.is_inference()
        result = _evaluate(*state)
        assert torch.is_inference_mode_enabled()
    _assert_oracle(result, state)


def test_source_coordinate_mutation_is_rejected_by_canonical_integrity():
    receptor, ligand, rp, lp = _pair()
    receptor.coordinates[0, 0, 0] = 0.1
    with pytest.raises(MolecularIntegrityError):
        _evaluate(receptor, ligand, rp, lp)


@pytest.mark.parametrize("side", [0, 1])
@pytest.mark.parametrize("mode", ["missing", "duplicate", "reversed"])
def test_full_ordered_parameter_coverage_is_required(side, mode):
    state = list(_multi_state())
    rows = state[2 + side]
    if mode == "missing":
        state[2 + side] = rows[:-1]
    elif mode == "duplicate":
        rows[1] = dict(rows[0])
    else:
        state[2 + side] = list(reversed(rows))
    with pytest.raises(adapter.PreparedInteractionError):
        _evaluate(*state)


@pytest.mark.parametrize("element", ["H", "C", "N", "O", "F", "P", "S", "Cl", "Br", "I"])
def test_declared_elements_use_explicit_parameters_without_element_based_assignment(element):
    receptor, ligand, rp, lp = _pair()
    receptor = _system(receptor.coordinates[0].tolist(), [0.2], elements=[element])
    _assert_oracle(_evaluate(receptor, ligand, rp, lp), (receptor, ligand, rp, lp))


def test_element_outside_declared_domain_is_rejected():
    receptor, ligand, rp, lp = _pair()
    receptor = _system(receptor.coordinates[0].tolist(), [0.2], elements=["Si"])
    with pytest.raises(adapter.PreparedInteractionError):
        _evaluate(receptor, ligand, rp, lp)


@pytest.mark.parametrize("bad_value", [None, "", " ", True])
def test_nonblank_state_declarations_are_required(bad_value):
    fields = {"coordinate_frame_id": "synthetic", "prepared_state_id": "synthetic",
              "parameter_source_id": "synthetic", "charge_source_id": bad_value}
    with pytest.raises(adapter.PreparedInteractionError):
        _evaluate(*_pair(), source_declarations=fields)


def test_unknown_state_declaration_cannot_silently_enter_identity():
    fields = {"coordinate_frame_id": "synthetic", "prepared_state_id": "synthetic",
              "parameter_source_id": "synthetic", "charge_source_id": "synthetic", "other": "uninterpreted"}
    with pytest.raises(adapter.PreparedInteractionError):
        _evaluate(*_pair(), source_declarations=fields)


@pytest.mark.parametrize("distance", [0.0, 0.2, 0.349])
def test_cross_pair_below_frozen_distance_domain_is_rejected(distance):
    with pytest.raises((adapter.PreparedInteractionError, ReferencePhysicsApplicabilityError)):
        _evaluate(*_pair(distance))


def test_minimum_cross_distance_boundary_remains_evaluated():
    state = _pair(0.35)
    _assert_oracle(_evaluate(*state), state)


def test_result_serializes_with_finite_quantities_and_observational_cost():
    result = _evaluate(*_pair())
    document = json.loads(json.dumps(result, allow_nan=False))
    assert document["schema_id"] == "betelgeuze.prepared_v2_cross_interaction/1.0.0"
    assert document["status"] == "evaluated"
    assert document["model"]["source_full_simulation_hamiltonian_reproduced"] is False
    assert document["model"]["cross_pair_scaling"] == 1.0
    for field in ("wall_seconds", "cpu_seconds"):
        assert math.isfinite(document["cost"][field])
        assert document["cost"][field] >= 0.0


@pytest.mark.parametrize("dielectric,kappa", [(1.0, 0.0), (2.5, 0.4), (80.0, 1.0)])
def test_explicit_dielectric_and_screening_are_used_by_scalar_oracle(dielectric, kappa):
    state = _pair(8.5)
    result = _evaluate(*state, dielectric=dielectric, screening_kappa_per_angstrom=kappa)
    _assert_oracle(result, state, dielectric=dielectric, kappa=kappa)


def _large_finite_tile_state(ligand_sigma):
    # Each 64-atom receptor tile has one active point. The others are distant
    # synthetic constants, outside cutoff. Small receptor sigma keeps excluded
    # internal pairs finite. No molecular interpretation is attached to sigma.
    positions = []
    for row in range(4):
        for column in range(4):
            positions.append([4.0, -0.55 + row * 0.4, -0.55 + column * 0.4])
            for _ in range(63):
                positions.append([200.0 + len(positions) * 2.0, 0.0, 0.0])
    receptor = _system(positions, [0.0] * len(positions))
    ligand = _system([[0.0, 0.0, 0.0]], [0.0])
    return receptor, ligand, _parameters(receptor, sigma=1.0), _parameters(ligand, sigma=ligand_sigma)


def test_finite_kernel_tile_force_accumulation_overflow_is_rejected(monkeypatch):
    state = _large_finite_tile_state(3.0e26)
    original = adapter.evaluate_reference_force_field
    tile_force_magnitudes = []

    def observe(system, graph, parameters):
        evaluation = original(system, graph, parameters)
        assert bool(torch.isfinite(evaluation.term.forces).all())
        assert all(bool(torch.isfinite(value).all()) for value in evaluation.component_energies.values())
        tile_force_magnitudes.append(abs(float(evaluation.term.forces[0, -1, 0])))
        return evaluation

    monkeypatch.setattr(adapter, "evaluate_reference_force_field", observe)
    with pytest.raises(adapter.PreparedInteractionError, match="cross-force accumulation"):
        _evaluate(*state)
    assert len(tile_force_magnitudes) == 16
    assert math.isinf(sum(tile_force_magnitudes))


def test_large_finite_tile_accumulation_positive_control_matches_scalar_math():
    state = _large_finite_tile_state(2.0e26)
    result = _evaluate(*state)
    _assert_oracle(result, state)
    assert result["pair_accounting"]["kernel_tiles"] == 16
    assert result["pair_accounting"]["within_declared_cutoff"] == 16
    json.dumps(result, allow_nan=False)


def _state_with_nested_tensor_metadata():
    systems = []
    for system in _pair()[:2]:
        nested = {"nested": {"tensor": torch.tensor([1.25], dtype=torch.float64)}}
        systems.append(replace(system, metadata=nested,
            atoms=(replace(system.atoms[0], metadata=nested),),
            provenance=replace(system.provenance, metadata=nested)))
    return (*systems, _parameters(systems[0]), _parameters(systems[1]))


def _mutate_without_parent_tensor_version(system, kind):
    if kind in ("numpy", "data"):
        tensor = system.coordinates
    elif kind == "system_metadata":
        tensor = system.metadata["nested"]["tensor"]
    elif kind == "atom_metadata":
        tensor = system.atoms[0].metadata["nested"]["tensor"]
    else:
        tensor = system.provenance.metadata["nested"]["tensor"]
    before_version = tensor._version
    if kind == "data":
        tensor.data.reshape(-1)[0] += 0.125
    else:
        tensor.numpy().reshape(-1)[0] += 0.125
    assert tensor._version == before_version


@pytest.mark.parametrize("side", [0, 1])
@pytest.mark.parametrize("stage", ["before_physics", "after_physics", "output"])
@pytest.mark.parametrize("kind", ["numpy", "data", "system_metadata", "atom_metadata", "provenance_metadata"])
def test_full_integrity_guards_reject_mutation_at_existing_boundaries(monkeypatch, side, stage, kind):
    state = _state_with_nested_tensor_metadata()
    target = state[side]
    mutated = []

    def mutate():
        assert not mutated
        _mutate_without_parent_tensor_version(target, kind)
        mutated.append(True)

    if stage == "before_physics":
        original = adapter._validate_component_minimum_distance

        def checked(system, label):
            original(system, label)
            if label == "ligand":
                mutate()

        def unexpected_physics(*args, **kwargs):
            raise AssertionError("the original pre-physics integrity boundary was skipped")

        monkeypatch.setattr(adapter, "_validate_component_minimum_distance", checked)
        monkeypatch.setattr(adapter, "_tile", unexpected_physics)
    elif stage == "after_physics":
        original = adapter._tile

        def evaluated(*args, **kwargs):
            result = original(*args, **kwargs)
            mutate()
            return result

        monkeypatch.setattr(adapter, "_tile", evaluated)
    else:
        original = adapter.canonical_coordinates_sha256

        def exporting(system):
            if system is target:
                mutate()
            return original(system)

        # Only this adapter's alias is wrapped; the frozen canonical function
        # and object integrity method are unchanged and actually execute.
        monkeypatch.setattr(adapter, "canonical_coordinates_sha256", exporting)
    with pytest.raises(MolecularIntegrityError, match="changed after construction"):
        _evaluate(*state)
    assert mutated == [True]


@pytest.mark.parametrize("kind", ["numpy", "data"])
def test_successful_call_does_not_cache_admission_across_later_source_mutation(kind):
    state = _state_with_nested_tensor_metadata()
    _assert_oracle(_evaluate(*state), state)
    _mutate_without_parent_tensor_version(state[0], kind)
    with pytest.raises(MolecularIntegrityError):
        _evaluate(*state)


def test_returned_document_mutation_does_not_affect_a_later_call_or_sources():
    state = _state_with_nested_tensor_metadata()
    first = _evaluate(*state)
    expected = copy.deepcopy(first)
    first["sources"]["receptor"]["system"]["system_sha256"] = "0" * 64
    first["quantities"]["ligand_cross_forces_kcal_per_mol_angstrom"][0][0] = 999.0
    second = _evaluate(*state)
    for value in (expected, second):
        value.pop("cost")
    assert second == expected
