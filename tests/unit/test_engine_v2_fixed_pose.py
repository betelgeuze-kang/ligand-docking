"""Synthetic numerical and admission checks; no molecular source or search runs.

The scalar oracle uses Python math and explicit LJ/Coulomb derivatives. It does
not call the reference evaluator, its switching helper, or any old fixtures.
"""

from __future__ import annotations

from dataclasses import replace
import json
import math
import re

import pytest


import torch

from betelgeuze_engine_v2.docking.authority import DockingScope, PocketDefinition
from betelgeuze_engine_v2.docking.fixed_pose import FixedPoseError, evaluate_fixed_pose
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
    UnitCell,
    canonical_coordinates_sha256,
    canonical_system_sha256,
    canonical_topology_sha256,
)
from betelgeuze_engine_v2.physics import (
    AtomNonbondedParameter,
    HarmonicAngleParameter,
    HarmonicBondParameter,
    PairScalingParameter,
    PeriodicTorsionParameter,
    ReferenceApplicabilityDomain,
    ReferenceForceFieldParameters,
)


def _system(
    positions=None,
    *,
    charges=(0.2, -0.3),
    elements=None,
    residue_groups=None,
    bond_pairs=(),
) -> AllAtomSystem:
    if positions is None:
        positions = ((0.0, 0.0, 0.0), (4.0, 0.0, 0.0))
    count = len(positions)
    elements = ("C",) * count if elements is None else elements
    residue_groups = tuple((i,) for i in range(count)) if residue_groups is None else residue_groups
    residues_by_atom = {atom: residue for residue, group in enumerate(residue_groups) for atom in group}
    atomic_numbers = {"H": 1, "C": 6, "N": 7, "O": 8, "F": 9, "S": 16}
    return AllAtomSystem(
        system_id="fixed-pose-synthetic-numerical-test",
        atoms=tuple(
            Atom(i, f"{element}{i}", element, atomic_numbers[element], residues_by_atom[i], partial_charge_e=charges[i])
            for i, element in enumerate(elements)
        ),
        bonds=tuple(Bond(i, first, second, 1.0, source="synthetic") for i, (first, second) in enumerate(bond_pairs)),
        residues=tuple(
            Residue(i, f"S{i}", i, i + 1, tuple(group), entity_type="non_polymer", hetero=True)
            for i, group in enumerate(residue_groups)
        ),
        chains=tuple(Chain(i, f"S{i}", (i,)) for i in range(len(residue_groups))),
        coordinates=torch.tensor([positions], dtype=torch.float64),
        provenance=StructureProvenance(
            source_format="synthetic",
            source_id="local-numerical-constant-fixture",
            source_sha256="d" * 64,
            parser_name="synthetic-test-constructor",
            parser_version="1",
        ),
        metadata={"evidence_scope": "synthetic_numerical_test_only"},
    )


def _parameters(system, *, epsilon=0.2, sigma=3.0, charges=None, **changes):
    charges = tuple(atom.partial_charge_e for atom in system.atoms) if charges is None else charges
    parameters = ReferenceForceFieldParameters(
        parameter_set_id="synthetic-explicit-parameters",
        parameter_set_version="1",
        topology_sha256=canonical_topology_sha256(system),
        atom_parameters=tuple(AtomNonbondedParameter(i, sigma, epsilon, charge) for i, charge in enumerate(charges)),
        cutoff_angstrom=10.0,
        switch_start_angstrom=8.0,
        dielectric=4.0,
        screening_kappa_per_angstrom=0.1,
        applicability_domain=ReferenceApplicabilityDomain(max_atoms=300),
        metadata={"evidence_scope": "synthetic_numerical_test_only"},
    )
    return replace(parameters, **changes)


def _pocket(**changes):
    return replace(
        PocketDefinition(
            scope=DockingScope.KNOWN_POCKET,
            method_id="synthetic",
            method_version="1",
            coordinate_frame_id="synthetic-frame",
            center=torch.zeros(3, dtype=torch.float64),
            radius_angstrom=100.0,
            source_artifact_sha256="a" * 64,
            implementation_source_sha256="b" * 64,
        ),
        **changes,
    )


def _declarations():
    return {
        "chemical_state_id": "synthetic-explicit-state",
        "hydrogen_state": "synthetic-atoms-as-supplied",
        "charge_source": "synthetic-explicit-partial-charges",
        "parameter_source": "synthetic-explicit-parameters/1",
    }


def _evaluate(system=None, parameters=None, **changes):
    system = _system() if system is None else system
    parameters = _parameters(system) if parameters is None else parameters
    arguments = {
        "receptor_atom_indices": (0,),
        "ligand_atom_indices": tuple(range(1, system.atom_count)),
        "state_declarations": _declarations(),
        "pocket": _pocket(),
    }
    arguments.update(changes)
    return evaluate_fixed_pose(system, parameters, **arguments)


def _pair_oracle(distance, first, second, *, cutoff=10.0, start=8.0, dielectric=4.0, kappa=0.1, lj_scale=1.0, coulomb_scale=1.0):
    """Return LJ/Coulomb energy and dE/dr, including the switch derivative."""
    if distance >= cutoff:
        return {"lennard_jones": (0.0, 0.0), "screened_coulomb": (0.0, 0.0)}
    sigma = (first.sigma_angstrom + second.sigma_angstrom) / 2.0
    epsilon = math.sqrt(first.epsilon_kcal_per_mol * second.epsilon_kcal_per_mol)
    sixth = (sigma / distance) ** 6
    lj = 4.0 * epsilon * (sixth * sixth - sixth) * lj_scale
    lj_derivative = 24.0 * epsilon * (sixth - 2.0 * sixth * sixth) / distance * lj_scale
    coulomb = 332.063713299 * first.charge_e * second.charge_e * math.exp(-kappa * distance) / (dielectric * distance) * coulomb_scale
    coulomb_derivative = -coulomb * (kappa + 1.0 / distance)
    switch, switch_derivative = 1.0, 0.0
    if distance > start:
        t = (distance - start) / (cutoff - start)
        switch = 1.0 - t**3 * (10.0 - t * (15.0 - 6.0 * t))
        switch_derivative = -30.0 * t**2 * (1.0 - t)**2 / (cutoff - start)
    return {
        "lennard_jones": (lj * switch, lj_derivative * switch + lj * switch_derivative),
        "screened_coulomb": (coulomb * switch, coulomb_derivative * switch + coulomb * switch_derivative),
    }


def _value(result, name):
    return result["quantities"][name]["value"]


@pytest.mark.parametrize("distance", [2.4, 4.0, 8.0, 8.5, 9.5, 9.999, 10.0, 10.001])
def test_pair_energy_and_analytic_force_match_independent_math(distance):
    system = _system(((0.0, 0.0, 0.0), (distance, 0.0, 0.0)))
    parameters = _parameters(system)
    # Unequal atom parameters exercise arithmetic sigma and geometric epsilon mixing.
    parameters = replace(parameters, atom_parameters=(AtomNonbondedParameter(0, 2.8, 0.12, 0.2), AtomNonbondedParameter(1, 3.2, 0.27, -0.3)))
    expected = _pair_oracle(distance, *parameters.atom_parameters)
    energy = sum(value[0] for value in expected.values())
    derivative = sum(value[1] for value in expected.values())
    result = _evaluate(system, parameters)
    for name in ("total_energy", "cross_energy"):
        assert _value(result, name) == pytest.approx(energy, rel=2e-11, abs=2e-12)
    for name in ("total_forces", "cross_forces"):
        assert _value(result, name)[0] == pytest.approx([derivative, 0.0, 0.0], rel=2e-10, abs=2e-11)
        assert _value(result, name)[1] == pytest.approx([-derivative, 0.0, 0.0], rel=2e-10, abs=2e-11)
    for name, (component, _) in expected.items():
        assert result["component_energies"][name]["total"] == pytest.approx(component, rel=2e-11, abs=2e-12)
        assert result["component_energies"][name]["cross"] == pytest.approx(component, rel=2e-11, abs=2e-12)
        assert result["component_energies"][name]["internal"] == pytest.approx(0.0, abs=1e-12)


@pytest.mark.parametrize("distance,sign", [(2.4, -1), (4.0, 1)])
def test_repulsive_and_attractive_forces_have_the_expected_direction(distance, sign):
    system = _system(((0.0, 0.0, 0.0), (distance, 0.0, 0.0)), charges=(0.0, 0.0))
    result = _evaluate(system)
    assert _value(result, "cross_forces")[0][0] * sign > 0.0
    assert _value(result, "cross_forces")[1][0] * sign < 0.0


@pytest.mark.parametrize("excluded", [False, True])
def test_explicit_cross_pair_scaling_and_exclusion_are_preserved(excluded):
    system = _system()
    parameters = _parameters(system, excluded_pairs=((0, 1),) if excluded else (), scaled_pairs=() if excluded else (PairScalingParameter(0, 1, 0.25, 0.75),))
    oracle = _pair_oracle(4.0, *parameters.atom_parameters, lj_scale=0.0 if excluded else 0.25, coulomb_scale=0.0 if excluded else 0.75)
    result = _evaluate(system, parameters)
    assert _value(result, "cross_energy") == pytest.approx(sum(row[0] for row in oracle.values()), abs=1e-12)
    assert _value(result, "cross_forces")[0][0] == pytest.approx(sum(row[1] for row in oracle.values()), abs=1e-12)


def test_rigid_transform_preserves_energy_and_rotates_force_and_pocket():
    system = _system(((0.2, -0.7, 0.4), (3.6, 0.8, -0.6)))
    pocket = _pocket()
    original = _evaluate(system, pocket=pocket)
    rotation = torch.tensor([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]], dtype=torch.float64)
    shift = torch.tensor([4.0, -3.0, 2.0], dtype=torch.float64)
    transformed_system = replace(system, coordinates=system.coordinates @ rotation.T + shift)
    transformed_pocket = replace(pocket, center=pocket.center @ rotation.T + shift)
    transformed = _evaluate(transformed_system, pocket=transformed_pocket)
    for quantity in ("total_energy", "cross_energy"):
        assert _value(transformed, quantity) == pytest.approx(_value(original, quantity), abs=2e-12)
    for quantity in ("total_forces", "cross_forces"):
        before = torch.tensor(_value(original, quantity), dtype=torch.float64)
        after = torch.tensor(_value(transformed, quantity), dtype=torch.float64)
        assert torch.allclose(after, before @ rotation.T, rtol=2e-11, atol=2e-11)
        assert torch.allclose(after.sum(dim=0), torch.zeros(3, dtype=torch.float64), atol=2e-11, rtol=0.0)
    assert transformed["input_identity"]["coordinates_sha256"] != original["input_identity"]["coordinates_sha256"]
    assert transformed["input_identity"]["pocket_definition_sha256"] != original["input_identity"]["pocket_definition_sha256"]


@pytest.mark.parametrize("context", [torch.no_grad, torch.inference_mode])
def test_force_evaluation_is_valid_inside_inference_callers(context):
    system = _system()
    parameters = _parameters(system)
    oracle = _pair_oracle(4.0, *parameters.atom_parameters)
    with context():
        result = _evaluate(system, parameters)
    assert _value(result, "cross_energy") == pytest.approx(sum(row[0] for row in oracle.values()), abs=1e-12)
    assert _value(result, "cross_forces")[0][0] == pytest.approx(sum(row[1] for row in oracle.values()), abs=1e-12)


def test_atom_permutation_reindexes_partition_parameters_and_forces():
    system = _system(((0.0, 0.0, 0.0), (3.8, 0.6, 0.0), (5.0, -1.2, 0.4)), charges=(0.2, -0.3, 0.1), elements=("C", "N", "O"))
    original = _evaluate(system)
    order = (2, 0, 1)
    permuted = _system(tuple(tuple(system.coordinates[0, i].tolist()) for i in order), charges=tuple(system.atoms[i].partial_charge_e for i in order), elements=tuple(system.atoms[i].element for i in order))
    changed = _evaluate(permuted, receptor_atom_indices=(1,), ligand_atom_indices=(0, 2))
    for name in ("total_energy", "cross_energy"):
        assert _value(changed, name) == pytest.approx(_value(original, name), rel=2e-11, abs=2e-11)
    for name in ("total_forces", "cross_forces"):
        for new_index, old_index in enumerate(order):
            assert _value(changed, name)[new_index] == pytest.approx(_value(original, name)[old_index], rel=2e-11, abs=2e-11)


def test_weak_cross_term_survives_large_internal_bond_energy():
    system = _system(((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (9.0, 0.0, 0.0)), charges=(0.0, 0.0, 0.0), residue_groups=((0, 1), (2,)), bond_pairs=((0, 1),))
    spring = 2.0e16
    parameters = _parameters(system, bonds=(HarmonicBondParameter(0, 1, 1.0, spring),), excluded_pairs=((0, 1),))
    result = _evaluate(system, parameters, receptor_atom_indices=(0, 1), ligand_atom_indices=(2,))
    first = _pair_oracle(9.0, parameters.atom_parameters[0], parameters.atom_parameters[2])
    second = _pair_oracle(7.0, parameters.atom_parameters[1], parameters.atom_parameters[2])
    cross = sum(row[0] for pair in (first, second) for row in pair.values())
    assert cross != 0.0 and abs(cross) < 0.01
    assert _value(result, "cross_energy") == pytest.approx(cross, rel=2e-11, abs=1e-14)
    assert result["component_energies"]["harmonic_bond"]["total"] == pytest.approx(0.5 * spring)
    assert result["component_energies"]["harmonic_bond"]["cross"] == 0.0
    assert result["component_energies"]["harmonic_bond"]["internal"] == pytest.approx(0.5 * spring)
    assert _value(result, "cross_forces")[0][0] == pytest.approx(sum(row[1] for row in first.values()), abs=1e-14)
    assert _value(result, "cross_forces")[1][0] == pytest.approx(sum(row[1] for row in second.values()), abs=1e-14)
    assert _value(result, "cross_forces")[2][0] == pytest.approx(-sum(row[1] for pair in (first, second) for row in pair.values()), abs=1e-14)


def _synthetic_angle_case(bend, near_zero):
    outer_x = -1.0 if near_zero else 2.0
    arm_length = abs(outer_x - 1.0)
    system = _system(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (outer_x, bend, 0.0), (6.0, 0.0, 0.0)),
        charges=(0.0,) * 4,
        residue_groups=((0, 1, 2), (3,)),
        bond_pairs=((0, 1), (1, 2)),
    )
    parameters = _parameters(
        system,
        epsilon=0.0,
        bonds=(
            HarmonicBondParameter(0, 1, 1.0, 200.0),
            HarmonicBondParameter(1, 2, math.hypot(arm_length, bend), 200.0),
        ),
        angles=(HarmonicAngleParameter(0, 1, 2, 2.0, 40.0),),
        excluded_pairs=((0, 1), (0, 2), (1, 2)),
    )
    return system, parameters, arm_length


@pytest.mark.parametrize("near_zero", [False, True], ids=["near_pi", "near_zero"])
@pytest.mark.parametrize("bend", [0.0, 1e-7], ids=["collinear", "clamped"])
def test_harmonic_angle_clamp_region_is_rejected(bend, near_zero):
    system, parameters, _ = _synthetic_angle_case(bend, near_zero)
    with pytest.raises(FixedPoseError, match="angle.*clamp"):
        _evaluate(system, parameters, receptor_atom_indices=(0, 1, 2), ligand_atom_indices=(3,))


@pytest.mark.parametrize("near_zero", [False, True], ids=["near_pi", "near_zero"])
@pytest.mark.parametrize("bend", [1e-5, 0.3], ids=["outside_clamp", "regular_angle"])
def test_unclamped_harmonic_angle_force_matches_independent_math(bend, near_zero):
    system, parameters, arm_length = _synthetic_angle_case(bend, near_zero)
    result = _evaluate(system, parameters, receptor_atom_indices=(0, 1, 2), ligand_atom_indices=(3,))
    acute = math.atan(bend / arm_length)
    theta = acute if near_zero else math.pi - acute
    theta_derivative = (1.0 if near_zero else -1.0) * arm_length / (arm_length**2 + bend**2)
    expected_force_y = -40.0 * (theta - 2.0) * theta_derivative
    assert result["status"] == "evaluated"
    assert result["component_energies"]["harmonic_angle"]["total"] == pytest.approx(
        20.0 * (theta - 2.0)**2, rel=2e-6, abs=1e-10,
    )
    assert _value(result, "total_forces")[2][1] == pytest.approx(expected_force_y, rel=2e-6, abs=1e-9)
    assert abs(expected_force_y) > 1.0
    assert _value(result, "cross_energy") == 0.0
    assert _value(result, "cross_forces") == [[0.0, 0.0, 0.0]] * 4


def test_collinear_atoms_without_harmonic_angles_remain_supported():
    system, _, _ = _synthetic_angle_case(0.0, False)
    system = replace(system, bonds=())
    result = _evaluate(
        system, _parameters(system, epsilon=0.0),
        receptor_atom_indices=(0, 1, 2), ligand_atom_indices=(3,),
    )
    assert result["status"] == "evaluated"
    assert _value(result, "total_energy") == 0.0
    assert result["applicability_domain"]["harmonic_angle_cosine_open_interval"] == [
        -1.0 + 1e-12, 1.0 - 1e-12,
    ]


@pytest.mark.parametrize("indices", [(4, 1, 2), (0, 4, 2), (0, 1, 4)])
def test_angle_domain_gate_preserves_out_of_range_parameter_error(indices):
    system, parameters, _ = _synthetic_angle_case(0.3, False)
    parameters = replace(parameters, angles=(HarmonicAngleParameter(*indices, 2.0, 40.0),))
    with pytest.raises(FixedPoseError, match="angle.*index"):
        _evaluate(system, parameters, receptor_atom_indices=(0, 1, 2), ligand_atom_indices=(3,))


def test_regular_torsion_keeps_independent_energy_and_force():
    phi = 0.7
    system = _system(
        ((0.0, 1.0, 0.0), (0.0, 0.0, 0.0), (1.0, 0.0, 0.0),
         (1.0, math.cos(phi), math.sin(phi)), (6.0, 0.0, 0.0)),
        charges=(0.0,) * 5,
        residue_groups=((0, 1, 2, 3), (4,)),
        bond_pairs=((0, 1), (1, 2), (2, 3)),
    )
    parameters = _parameters(
        system, epsilon=0.0,
        bonds=tuple(HarmonicBondParameter(i, i + 1, 1.0, 200.0) for i in range(3)),
        angles=(
            HarmonicAngleParameter(0, 1, 2, math.pi / 2.0, 40.0),
            HarmonicAngleParameter(1, 2, 3, math.pi / 2.0, 40.0),
        ),
        torsions=(PeriodicTorsionParameter(0, 1, 2, 3, 3, 0.2, 0.5),),
        excluded_pairs=tuple((i, j) for i in range(4) for j in range(i + 1, 4)),
    )
    result = _evaluate(system, parameters, receptor_atom_indices=(0, 1, 2, 3), ligand_atom_indices=(4,))
    expected_energy = 0.5 * (1.0 + math.cos(3.0 * phi - 0.2))
    expected_torque = 1.5 * math.sin(3.0 * phi - 0.2)
    assert _value(result, "total_energy") == pytest.approx(expected_energy, abs=1e-12)
    assert _value(result, "total_forces")[3] == pytest.approx(
        [0.0, -expected_torque * math.sin(phi), expected_torque * math.cos(phi)], abs=1e-11,
    )
    assert _value(result, "cross_energy") == 0.0
    assert _value(result, "cross_forces") == [[0.0, 0.0, 0.0]] * 5


def test_zero_results_remain_evaluated_while_uncomputed_quantities_are_null():
    system = _system(charges=(0.0, 0.0))
    result = _evaluate(system, _parameters(system, epsilon=0.0))
    assert result["schema_id"] == "betelgeuze.engine_v2_fixed_pose_evaluation/1.0.0"
    assert result["status"] == "evaluated"
    for name in ("total_energy", "cross_energy"):
        assert result["quantities"][name]["status"] == "evaluated"
        assert result["quantities"][name]["unit"] == "kcal/mol"
        assert _value(result, name) == 0.0
    for name in ("total_forces", "cross_forces"):
        assert result["quantities"][name]["status"] == "evaluated"
        assert result["quantities"][name]["unit"] == "kcal/mol/angstrom"
        assert _value(result, name) == [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
    for name in ("strain", "solvation", "ai_correction", "uncertainty", "pose_retention", "improper", "entropy"):
        assert name in result["not_evaluated"]
        assert result["not_evaluated"][name] is None
    assert result["component_forces"] is None
    assert set(result["claim_policy"]) == {"scientifically_validated", "validated_for_composition", "production_claim_allowed", "product_qualified"}
    assert result["claim_policy"] and all(value is False for value in result["claim_policy"].values())
    assert json.loads(json.dumps(result, allow_nan=False)) == result


def test_result_binds_inputs_without_mutating_coordinates_parameters_or_pocket():
    system = _system()
    parameters = _parameters(system)
    pocket = _pocket()
    coordinates = system.coordinates.clone()
    center = pocket.center.clone()
    declarations = _declarations()
    original_declarations = declarations.copy()
    identities = {"system_sha256": canonical_system_sha256(system), "topology_sha256": canonical_topology_sha256(system), "coordinates_sha256": canonical_coordinates_sha256(system), "parameter_fingerprint_sha256": parameters.fingerprint_sha256, "pocket_definition_sha256": pocket.fingerprint_sha256}
    result = _evaluate(system, parameters, pocket=pocket, state_declarations=declarations)
    assert torch.equal(system.coordinates, coordinates)
    assert torch.equal(pocket.center, center)
    assert system.coordinates.grad is None and not system.coordinates.requires_grad
    assert declarations == original_declarations
    assert result["coordinates"] == coordinates.tolist()
    assert result["coordinate_frame_id"] == pocket.coordinate_frame_id
    assert result["coordinate_frame_status"] == "caller_declared_no_registration_performed"
    assert result["state_declarations"] == declarations
    assert result["state_declarations_verified"] is False
    for name, expected in identities.items():
        assert result["input_identity"][name] == expected
    for name in ("partition_sha256", "state_declarations_sha256"):
        assert re.fullmatch(r"[0-9a-f]{64}", result["input_identity"][name])
    assert result["atom_mapping"]["receptor_atom_indices"] == [0]
    assert result["atom_mapping"]["ligand_atom_indices"] == [1]
    assert result["cost"]["evaluation_count"] == 2
    assert result["cost"]["timing_evidence"] == "single_call_observation"
    assert result["cost"]["speedup"] is None
    for name in ("wall_seconds", "cpu_seconds"):
        assert math.isfinite(result["cost"][name]) and result["cost"][name] >= 0.0


def test_caller_metadata_claims_cannot_remove_scientific_blockers():
    system = _system()
    parameters = _parameters(system, metadata={"scientifically_validated": True, "production_claim_allowed": True})
    result = _evaluate(system, parameters)
    assert all(value is False for value in result["claim_policy"].values())
    assert "public_force_energy_validation_missing" in result["scientific_blockers"]
    assert "verified_validation_receipt_not_implemented" in result["scientific_blockers"]


@pytest.mark.parametrize("receptor,ligand", [((), (0, 1)), ((0, 1), ()), ((0,), (0, 1)), ((0,), ()), ((0, 0), (1,)), ((0,), (1, 1)), ((-1,), (1,)), ((0,), (2,)), ((False,), (1,)), ((0.0,), (1,)), (("0",), (1,)), ((0,), (True,))])
def test_invalid_partition_is_rejected(receptor, ligand):
    with pytest.raises(FixedPoseError):
        _evaluate(receptor_atom_indices=receptor, ligand_atom_indices=ligand)


def test_cross_covalent_bond_is_rejected_with_complete_parameters():
    system = _system(bond_pairs=((0, 1),))
    parameters = _parameters(system, bonds=(HarmonicBondParameter(0, 1, 1.5, 200.0),), excluded_pairs=((0, 1),))
    with pytest.raises(FixedPoseError):
        _evaluate(system, parameters)


def test_residue_cannot_straddle_partition():
    system = _system(residue_groups=((0, 1),))
    with pytest.raises(FixedPoseError):
        _evaluate(system)


@pytest.mark.parametrize("field", tuple(_declarations()))
@pytest.mark.parametrize("bad", [None, "", "   ", 1, False])
def test_required_state_declarations_are_nonblank_strings(field, bad):
    declarations = _declarations()
    declarations[field] = bad
    with pytest.raises(FixedPoseError):
        _evaluate(state_declarations=declarations)


def test_missing_or_extra_state_declarations_are_rejected():
    declarations = _declarations()
    del declarations["hydrogen_state"]
    with pytest.raises(FixedPoseError):
        _evaluate(state_declarations=declarations)
    with pytest.raises(FixedPoseError):
        _evaluate(state_declarations={**_declarations(), "scientifically_validated": "true"})


@pytest.mark.parametrize("bad_charge", [None, math.nan, math.inf, -math.inf])
def test_absent_or_nonfinite_canonical_partial_charge_is_rejected(bad_charge):
    system = _system(charges=(bad_charge, -0.3))
    # Finite parameter charges isolate admission of the canonical atom record.
    parameters = _parameters(_system())
    if bad_charge is None:
        parameters = replace(parameters, topology_sha256=canonical_topology_sha256(system))
    with pytest.raises(FixedPoseError):
        _evaluate(system, parameters)


def test_parameter_charge_must_match_explicit_canonical_charge():
    system = _system()
    with pytest.raises(FixedPoseError):
        _evaluate(system, _parameters(system, charges=(0.21, -0.3)))


@pytest.mark.parametrize("bad_hash", ["0" * 64, "f" * 64])
def test_stale_parameter_topology_identity_is_rejected(bad_hash):
    system = _system()
    with pytest.raises(FixedPoseError):
        _evaluate(system, _parameters(system, topology_sha256=bad_hash))


def test_missing_nonbonded_and_bond_parameter_coverage_are_rejected():
    system = _system()
    parameters = _parameters(system)
    with pytest.raises(FixedPoseError):
        _evaluate(system, replace(parameters, atom_parameters=parameters.atom_parameters[:1]))
    bonded = _system(((0.0, 0.0, 0.0), (1.5, 0.0, 0.0), (5.0, 0.0, 0.0)), charges=(0.0, 0.0, 0.0), residue_groups=((0, 1), (2,)), bond_pairs=((0, 1),))
    with pytest.raises(FixedPoseError):
        _evaluate(bonded, receptor_atom_indices=(0, 1), ligand_atom_indices=(2,))


@pytest.mark.parametrize("missing_term", ["angle", "torsion"])
def test_internal_parameter_coverage_cannot_be_bypassed_by_cross_projection(missing_term):
    positions = ((0.0, 0.0, 0.0), (1.5, 0.0, 0.0), (2.0, 1.4, 0.0), (3.2, 1.7, 0.8), (7.0, 0.0, 0.0))
    system = _system(positions, charges=(0.0,) * 5, residue_groups=((0, 1, 2, 3), (4,)), bond_pairs=((0, 1), (1, 2), (2, 3)))
    parameters = _parameters(
        system,
        bonds=tuple(HarmonicBondParameter(i, i + 1, 1.5, 200.0) for i in range(3)),
        angles=() if missing_term == "angle" else (HarmonicAngleParameter(0, 1, 2, 2.0, 40.0), HarmonicAngleParameter(1, 2, 3, 2.0, 40.0)),
        torsions=(PeriodicTorsionParameter(0, 1, 2, 3, 3, 0.0, 0.5),) if missing_term == "angle" else (),
    )
    with pytest.raises(FixedPoseError, match=f"{missing_term}_parameters_do_not_exactly_cover_system_topology"):
        _evaluate(system, parameters, receptor_atom_indices=(0, 1, 2, 3), ligand_atom_indices=(4,))


@pytest.mark.parametrize("element", ["F", "S"])
def test_out_of_domain_element_is_rejected(element):
    system = _system(elements=("C", element))
    with pytest.raises(FixedPoseError):
        _evaluate(system)


@pytest.mark.parametrize("bad", ["float32", "ensemble", "nonfinite", "periodic", "unit", "atom_shape"])
def test_unsupported_coordinate_domain_is_rejected(bad):
    system = _system()
    parameters = _parameters(system)
    if bad == "float32":
        system = replace(system, coordinates=system.coordinates.float())
    elif bad == "ensemble":
        system = replace(system, coordinates=system.coordinates.repeat(2, 1, 1))
    elif bad == "nonfinite":
        system.coordinates[0, 1, 0] = math.nan
    elif bad == "periodic":
        system = replace(system, cell=UnitCell.orthorhombic((20.0, 20.0, 20.0), dtype=torch.float64))
    elif bad == "unit":
        system = replace(system, coordinate_unit="nm")
    else:
        system = replace(system, coordinates=system.coordinates[:, :1])
    with pytest.raises(FixedPoseError):
        _evaluate(system, parameters)


@pytest.mark.parametrize("count", [1, 257])
def test_atom_count_bounds_are_enforced_before_evaluation(count):
    system = _system(tuple((float(i), 0.0, 0.0) for i in range(count)), charges=(0.0,) * count)
    with pytest.raises(FixedPoseError):
        _evaluate(system)


def test_coincident_atoms_are_rejected():
    system = _system(((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)))
    with pytest.raises(FixedPoseError):
        _evaluate(system)


def test_cutoff_cannot_hide_pairs_below_minimum_admissible_distance():
    system = _system(((0.0, 0.0, 0.0), (0.2, 0.0, 0.0)))
    parameters = _parameters(system, cutoff_angstrom=0.1, switch_start_angstrom=0.05)
    with pytest.raises(FixedPoseError, match="cutoff"):
        _evaluate(system, parameters)


def test_known_pocket_scope_and_ligand_containment_are_required():
    with pytest.raises(FixedPoseError):
        _evaluate(pocket=_pocket(scope=DockingScope.REDOCKING))
    with pytest.raises(FixedPoseError):
        _evaluate(pocket=_pocket(radius_angstrom=3.0))


def test_mutated_pocket_definition_fails_identity_check():
    pocket = _pocket()
    pocket.center[0] = 1.0
    with pytest.raises(FixedPoseError):
        _evaluate(pocket=pocket)
