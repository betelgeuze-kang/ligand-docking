"""Synthetic explicit component assembly; no structures, training, or search.

The numerical oracle uses scalar Python math over supplied constants. Manual
complex construction supplies a separate index-remapping integration control.
"""

from __future__ import annotations

from dataclasses import replace
import json
import math

import pytest
import torch

from betelgeuze_engine_v2.docking.authority import DockingScope, PocketDefinition
from betelgeuze_engine_v2.docking.fixed_pose import FixedPoseError, evaluate_fixed_pose
from betelgeuze_engine_v2.docking.fixed_pose_assembly import (
    FixedPoseAssemblyError,
    assemble_fixed_pose_inputs,
    evaluate_fixed_components,
)
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem, Atom, Bond, Chain, Residue, StructureProvenance, UnitCell,
    all_atom_system_from_canonical_json, canonical_coordinates_sha256,
    canonical_system_json_bytes, canonical_system_sha256, canonical_topology_sha256,
)
from betelgeuze_engine_v2.physics import (
    AtomNonbondedParameter, HarmonicAngleParameter, HarmonicBondParameter,
    PairScalingParameter, PeriodicTorsionParameter, ReferenceApplicabilityDomain,
    ReferenceForceFieldParameters,
)


def _component(name, positions, charges, *, bonds=(), elements=None):
    elements = tuple(elements or ("C",) * len(positions))
    numbers = {"H": 1, "C": 6, "N": 7, "O": 8, "F": 9}
    return AllAtomSystem(
        system_id=f"synthetic-{name}",
        atoms=tuple(Atom(i, f"{name}{i}", element, numbers[element], 0,
                         partial_charge_e=charges[i], mass_da=12.0, serial=100 + i,
                         stereo="R" if i == 0 else "unspecified",
                         metadata={"source_atom": i, "zero": 0.0})
                    for i, element in enumerate(elements)),
        bonds=tuple(Bond(i, first, second, 1.0, source="synthetic-explicit",
                         metadata={"source_bond": i}) for i, (first, second) in enumerate(bonds)),
        residues=(Residue(0, "SYN", 0, 17, tuple(range(len(positions))), insertion_code="X",
                          entity_type="non_polymer", hetero=True, metadata={"origin": name}),),
        chains=(Chain(0, "A", (0,), entity_id="same-entity-label", metadata={"origin": name}),),
        coordinates=torch.tensor([positions], dtype=torch.float64),
        provenance=StructureProvenance(
            source_format="synthetic", source_id=name, parser_name="constant-fixture",
            parser_version="1", parent_sha256=("e" * 64,), operations=("explicit-fixture",),
            metadata={"origin": name, "nested": {"zero": 0.0, "label": "preserve"}},
        ),
        metadata={"coordinate_frame_id": "synthetic-frame", "origin": name, "zero": 0.0},
    )


def _parameters(system, **changes):
    base = ReferenceForceFieldParameters(
        parameter_set_id="synthetic-shared-family", parameter_set_version="1",
        topology_sha256=canonical_topology_sha256(system),
        atom_parameters=tuple(AtomNonbondedParameter(i, 1.1 + i * 0.1, 0.02 + i * 0.01,
                                                   atom.partial_charge_e or 0.0)
                              for i, atom in enumerate(system.atoms)),
        bonds=tuple(HarmonicBondParameter(bond.atom_i, bond.atom_j, 1.0, 7.0)
                    for bond in system.bonds),
        cutoff_angstrom=10.0, switch_start_angstrom=8.0, dielectric=3.0,
        screening_kappa_per_angstrom=0.12,
        applicability_domain=ReferenceApplicabilityDomain(max_atoms=256),
        metadata={"source": system.system_id, "zero": 0.0},
    )
    return replace(base, **changes)


def _pocket(**changes):
    return replace(PocketDefinition(
        scope=DockingScope.KNOWN_POCKET, method_id="synthetic", method_version="1",
        coordinate_frame_id="synthetic-frame", center=torch.zeros(3, dtype=torch.float64),
        radius_angstrom=100.0, source_artifact_sha256="a" * 64,
        implementation_source_sha256="b" * 64,
    ), **changes)


def _frame(receptor, ligand):
    return {"coordinate_frame_id": "synthetic-frame",
            "receptor_coordinates_sha256": canonical_coordinates_sha256(receptor),
            "ligand_coordinates_sha256": canonical_coordinates_sha256(ligand)}


def _declarations():
    return {"chemical_state_id": "synthetic-explicit-state",
            "hydrogen_state": "as-supplied-no-inference", "charge_source": "synthetic-constants",
            "parameter_source": "synthetic-shared-family/1"}


def _inputs():
    receptor = _component("R", ((0.0, 0.0, 0.0), (1.3, 0.2, 0.0)), (0.2, 0.0), bonds=((0, 1),))
    ligand = _component("L", ((4.1, 0.5, 0.3), (5.2, 1.0, 0.3)), (-0.3, 0.1), bonds=((0, 1),))
    rp = _parameters(receptor, excluded_pairs=((0, 1),))
    lp = _parameters(ligand, scaled_pairs=(PairScalingParameter(0, 1, 0.25, 0.5),))
    return receptor, rp, ligand, lp


def _assemble(inputs=None, **changes):
    inputs = inputs or _inputs()
    options = {"pocket": _pocket(), "frame_declaration": _frame(inputs[0], inputs[2])}
    options.update(changes)
    return assemble_fixed_pose_inputs(*inputs, **options)


def _evaluate(inputs=None, **changes):
    inputs = inputs or _inputs()
    options = {"pocket": _pocket(), "frame_declaration": _frame(inputs[0], inputs[2]),
               "state_declarations": _declarations()}
    options.update(changes)
    return evaluate_fixed_components(*inputs, **options)


def _pair_scalar(distance, first, second, lj_scale=1.0, coulomb_scale=1.0):
    if distance >= 10.0:
        return 0.0, 0.0
    sigma = (first.sigma_angstrom + second.sigma_angstrom) / 2.0
    epsilon = math.sqrt(first.epsilon_kcal_per_mol * second.epsilon_kcal_per_mol)
    sixth = (sigma / distance) ** 6
    lj = 4.0 * epsilon * (sixth * sixth - sixth) * lj_scale
    dlj = 24.0 * epsilon * (sixth - 2.0 * sixth * sixth) / distance * lj_scale
    q = 332.063713299 * first.charge_e * second.charge_e * math.exp(-0.12 * distance) / (3.0 * distance) * coulomb_scale
    dq = -q * (0.12 + 1.0 / distance)
    switch, derivative = 1.0, 0.0
    if distance > 8.0:
        x = (distance - 8.0) / 2.0
        switch = 1.0 - 10.0 * x**3 + 15.0 * x**4 - 6.0 * x**5
        derivative = (-30.0 * x**2 + 60.0 * x**3 - 30.0 * x**4) / 2.0
    return (lj + q) * switch, (dlj + dq) * switch + (lj + q) * derivative


def _independent_four_atom_oracle(inputs):
    receptor, rp, ligand, lp = inputs
    xyz = receptor.coordinates[0].tolist() + ligand.coordinates[0].tolist()
    parameters = list(rp.atom_parameters) + list(lp.atom_parameters)
    total, cross = 0.0, 0.0
    forces, cross_forces = [[0.0] * 3 for _ in xyz], [[0.0] * 3 for _ in xyz]
    for first in range(4):
        for second in range(first + 1, 4):
            displacement = [xyz[second][axis] - xyz[first][axis] for axis in range(3)]
            distance = math.sqrt(sum(value * value for value in displacement))
            scales = (0.0, 0.0) if (first, second) == (0, 1) else ((0.25, 0.5) if (first, second) == (2, 3) else (1.0, 1.0))
            energy, derivative = _pair_scalar(distance, parameters[first], parameters[second], *scales)
            is_cross = first < 2 <= second
            total += energy
            cross += energy if is_cross else 0.0
            if (first, second) in ((0, 1), (2, 3)):
                total += 0.5 * 7.0 * (distance - 1.0)**2
                derivative += 7.0 * (distance - 1.0)
            for axis in range(3):
                force = derivative * displacement[axis] / distance
                forces[first][axis] += force
                forces[second][axis] -= force
                if is_cross:
                    cross_forces[first][axis] += force
                    cross_forces[second][axis] -= force
    return total, cross, forces, cross_forces


def test_assembled_energy_and_forces_match_independent_math():
    inputs = _inputs()
    expected = _independent_four_atom_oracle(inputs)
    result = _evaluate(inputs)
    for name, value in zip(("total_energy", "cross_energy", "total_forces", "cross_forces"), expected):
        assert torch.allclose(torch.tensor(result["quantities"][name]["value"], dtype=torch.float64),
                              torch.tensor(value, dtype=torch.float64), rtol=2e-11, atol=2e-11)
    assert result["assembly"]["cross_pair_policy"] == "full_unscaled_reference_nonbonded_no_cross_exceptions"
    assert not any(result["claim_policy"].values())


def test_manual_combined_input_matches_wrapper_with_explicit_index_offsets():
    receptor, rp, ligand, lp = _inputs()
    manual = AllAtomSystem(
        system_id="synthetic-manual-complex",
        atoms=receptor.atoms + tuple(replace(atom, index=atom.index + 2, residue_index=1) for atom in ligand.atoms),
        bonds=(receptor.bonds[0], replace(ligand.bonds[0], index=1, atom_i=2, atom_j=3)),
        residues=(receptor.residues[0], replace(ligand.residues[0], index=1, chain_index=1, atom_indices=(2, 3))),
        chains=(receptor.chains[0], replace(ligand.chains[0], index=1, chain_id="B", residue_indices=(1,))),
        coordinates=torch.tensor([[[0.0, 0.0, 0.0], [1.3, 0.2, 0.0], [4.1, 0.5, 0.3], [5.2, 1.0, 0.3]]], dtype=torch.float64),
        provenance=StructureProvenance(source_format="synthetic", source_id="manual"),
    )
    params = replace(rp, topology_sha256=canonical_topology_sha256(manual),
                     atom_parameters=rp.atom_parameters + tuple(replace(row, atom_index=row.atom_index + 2) for row in lp.atom_parameters),
                     bonds=rp.bonds + (replace(lp.bonds[0], atom_i=2, atom_j=3),),
                     scaled_pairs=(PairScalingParameter(2, 3, 0.25, 0.5),))
    expected = evaluate_fixed_pose(manual, params, receptor_atom_indices=(0, 1), ligand_atom_indices=(2, 3),
                                   pocket=_pocket(), state_declarations=_declarations())
    actual = _evaluate()
    assert actual["quantities"] == expected["quantities"]
    assert actual["component_energies"] == expected["component_energies"]


def test_preserves_coordinates_records_zero_values_and_complete_source_identity():
    inputs = _inputs()
    before = [canonical_system_sha256(inputs[i]) for i in (0, 2)]
    assembly = _assemble(inputs)
    assert torch.equal(assembly.system.coordinates, torch.cat((inputs[0].coordinates, inputs[2].coordinates), dim=1))
    assert assembly.receptor_atom_indices == (0, 1)
    assert assembly.ligand_atom_indices == (2, 3)
    assert [chain.chain_id for chain in assembly.system.chains] == ["R:A", "L:A"]
    assert assembly.system.atoms[1].partial_charge_e == 0.0
    assert assembly.parameters.atom_parameter_map[1].charge_e == 0.0
    for side, offset, system, parameters in (("receptor", 0, inputs[0], inputs[1]), ("ligand", 2, inputs[2], inputs[3])):
        assert assembly.system.metadata["component_metadata"][side] == system.metadata
        assert assembly.system.provenance.metadata["component_provenance"][side] == system.provenance
        assert assembly.parameters.metadata["component_metadata"][side] == parameters.metadata
        for atom in system.atoms:
            actual = assembly.system.atoms[atom.index + offset]
            assert replace(actual, index=atom.index, residue_index=0) == atom
            assert actual.metadata == atom.metadata
        assert assembly.source_identity[side]["system_sha256"] == canonical_system_sha256(system)
        assert assembly.source_identity[side]["parameter_document"] == parameters.to_dict()
    assert [canonical_system_sha256(inputs[i]) for i in (0, 2)] == before
    assert assembly.system.provenance.parent_sha256 == tuple(before)
    assert assembly.index_maps["ligand"]["atoms"] == {"0": 2, "1": 3}
    assert assembly.index_maps["ligand"]["chain_ids"] == {"0": {"source": "A", "combined": "L:A"}}
    document = json.loads(json.dumps(assembly.to_dict(), allow_nan=False))
    assert document["same_frame_status"] == "caller_assertion_not_verified_no_registration"
    roundtrip = all_atom_system_from_canonical_json(canonical_system_json_bytes(assembly.system), device="cpu")
    assert canonical_system_sha256(roundtrip) == canonical_system_sha256(assembly.system)


def test_assembly_takes_a_detached_snapshot_of_mutable_source_state():
    inputs = _inputs()
    assembly = _assemble(inputs)
    old_sha = canonical_system_sha256(assembly.system)
    inputs[0].coordinates[0, 0, 0] = 20.0
    with pytest.raises(TypeError):
        inputs[0].atoms[0].metadata["source_atom"] = "changed"
    with pytest.raises(TypeError):
        inputs[0].provenance.metadata["nested"]["label"] = "changed"
    assert canonical_system_sha256(assembly.system) == old_sha


def test_angle_torsion_and_all_pair_rule_indices_are_remapped_without_value_changes():
    receptor = _component("R", ((0.0, 0.0, 0.0),), (0.0,))
    ligand = _component("L", ((3.0, 0.0, 0.0), (4.0, 0.1, 0.0), (4.4, 1.0, 0.0), (5.2, 1.2, 0.8)),
                        (0.1, -0.1, 0.0, 0.0), bonds=((0, 1), (1, 2), (2, 3)))
    angles = (HarmonicAngleParameter(0, 1, 2, 1.3, 4.0), HarmonicAngleParameter(1, 2, 3, 1.4, 5.0))
    torsions = (PeriodicTorsionParameter(0, 1, 2, 3, 1, 0.3, 0.0), PeriodicTorsionParameter(0, 1, 2, 3, 2, 0.5, 1.7))
    lp = _parameters(ligand, angles=angles, torsions=torsions, excluded_pairs=((0, 1),),
                     scaled_pairs=(PairScalingParameter(0, 3, 0.5, 0.25),))
    assembly = _assemble((receptor, _parameters(receptor), ligand, lp))
    assert assembly.parameters.angles == tuple(replace(row, atom_i=row.atom_i + 1, atom_j=row.atom_j + 1, atom_k=row.atom_k + 1) for row in angles)
    assert assembly.parameters.torsions == tuple(replace(row, atom_i=1, atom_j=2, atom_k=3, atom_l=4) for row in torsions)
    assert assembly.parameters.excluded_pairs == ((1, 2),)
    assert assembly.parameters.scaled_pairs == (PairScalingParameter(1, 4, 0.5, 0.25),)
    assert assembly.parameters.topology_sha256 == canonical_topology_sha256(assembly.system)


def test_permutation_within_each_source_preserves_energy_and_reorders_forces():
    inputs = _inputs()
    original = _evaluate(inputs)
    changed = []
    for system, params in ((inputs[0], inputs[1]), (inputs[2], inputs[3])):
        permuted = replace(system, atoms=tuple(replace(system.atoms[1 - i], index=i) for i in range(2)),
                           coordinates=system.coordinates[:, [1, 0], :])
        remapped = replace(params, topology_sha256=canonical_topology_sha256(permuted),
                           atom_parameters=tuple(replace(params.atom_parameter_map[1 - i], atom_index=i) for i in range(2)))
        changed.extend((permuted, remapped))
    result = _evaluate(tuple(changed))
    for name in ("total_energy", "cross_energy"):
        assert result["quantities"][name]["value"] == pytest.approx(original["quantities"][name]["value"], abs=2e-12)
    for name in ("total_forces", "cross_forces"):
        for i, old in enumerate((1, 0, 3, 2)):
            assert result["quantities"][name]["value"][i] == pytest.approx(original["quantities"][name]["value"][old], abs=2e-11)


@pytest.mark.parametrize("field", ["parameter_set_id", "parameter_set_version", "cutoff_angstrom",
                                    "switch_start_angstrom", "dielectric", "screening_kappa_per_angstrom",
                                    "applicability_domain"])
def test_rejects_mixing_global_parameter_contracts(field):
    receptor, rp, ligand, lp = _inputs()
    values = {"parameter_set_id": "other", "parameter_set_version": "2", "cutoff_angstrom": 11.0,
              "switch_start_angstrom": 7.0, "dielectric": 4.0, "screening_kappa_per_angstrom": 0.0,
              "applicability_domain": ReferenceApplicabilityDomain(max_atoms=255)}
    with pytest.raises(FixedPoseAssemblyError, match=field):
        _assemble((receptor, rp, ligand, replace(lp, **{field: values[field]})))


@pytest.mark.parametrize("side", [0, 2])
@pytest.mark.parametrize("parameter", ["atom_parameters", "bonds", "angles", "torsions", "excluded_pairs", "scaled_pairs"])
def test_rejects_parent_out_of_range_indices_before_they_can_become_combined_indices(side, parameter):
    inputs = list(_inputs())
    values = {
        "atom_parameters": inputs[side + 1].atom_parameters + (AtomNonbondedParameter(2, 1.0, 0.0, 0.0),),
        "bonds": (HarmonicBondParameter(0, 2, 1.0, 1.0),),
        "angles": (HarmonicAngleParameter(0, 1, 2, 1.0, 1.0),),
        "torsions": (PeriodicTorsionParameter(0, 1, 2, 3, 1, 0.0, 0.0),),
        "excluded_pairs": ((0, 2),), "scaled_pairs": (PairScalingParameter(0, 2, 1.0, 1.0),),
    }
    inputs[side + 1] = replace(inputs[side + 1], **{parameter: values[parameter]})
    with pytest.raises(FixedPoseAssemblyError, match="source parameters"):
        _assemble(tuple(inputs))


@pytest.mark.parametrize("side", [0, 2])
@pytest.mark.parametrize("problem", ["stale_hash", "missing_atom", "missing_bond", "extra_bond", "missing_charge", "nonfinite_charge", "charge_mismatch"])
def test_rejects_source_identity_coverage_and_charge_errors(side, problem):
    inputs = list(_inputs())
    system, params = inputs[side:side + 2]
    if problem == "stale_hash":
        params = replace(params, topology_sha256="0" * 64)
    elif problem == "missing_atom":
        params = replace(params, atom_parameters=params.atom_parameters[:1])
    elif problem == "missing_bond":
        params = replace(params, bonds=())
    elif problem == "extra_bond":
        system = replace(system, bonds=())
        params = replace(params, topology_sha256=canonical_topology_sha256(system))
    else:
        charge = None if problem == "missing_charge" else (math.nan if problem == "nonfinite_charge" else 0.7)
        system = replace(system, atoms=(replace(system.atoms[0], partial_charge_e=charge),) + system.atoms[1:])
        # Nonfinite source values cannot even be canonicalized; retaining the
        # original binding must still fail canonical validation before rebinding.
        if problem != "nonfinite_charge":
            params = replace(params, topology_sha256=canonical_topology_sha256(system))
    inputs[side:side + 2] = [system, params]
    with pytest.raises(FixedPoseAssemblyError):
        _assemble(tuple(inputs))


@pytest.mark.parametrize("problem", ["missing", "extra", "blank", "wrong_frame", "stale_receptor", "stale_ligand", "swapped_hashes"])
def test_requires_exact_current_frame_binding(problem):
    inputs = _inputs()
    frame = _frame(inputs[0], inputs[2])
    if problem == "missing":
        frame.pop("receptor_coordinates_sha256")
    elif problem == "extra":
        frame["verified"] = "true"
    elif problem == "blank":
        frame["coordinate_frame_id"] = " "
    elif problem == "wrong_frame":
        frame["coordinate_frame_id"] = "other"
    elif problem == "swapped_hashes":
        frame["receptor_coordinates_sha256"], frame["ligand_coordinates_sha256"] = frame["ligand_coordinates_sha256"], frame["receptor_coordinates_sha256"]
    else:
        frame[f"{problem.removeprefix('stale_')}_coordinates_sha256"] = "f" * 64
    with pytest.raises(FixedPoseAssemblyError, match="frame|SHA"):
        _assemble(inputs, frame_declaration=frame)


def test_rejects_source_metadata_frame_conflict_and_pocket_exclusion():
    receptor, rp, ligand, lp = _inputs()
    changed = replace(receptor, metadata={"coordinate_frame_id": "other"})
    rebound = replace(rp, topology_sha256=canonical_topology_sha256(changed))
    with pytest.raises(FixedPoseAssemblyError, match="different coordinate frame"):
        _assemble((changed, rebound, ligand, lp))
    with pytest.raises(FixedPoseAssemblyError, match="outside"):
        _assemble(pocket=_pocket(radius_angstrom=1.0))


@pytest.mark.parametrize("problem", ["float32", "multimodel", "periodic", "unsupported_element", "capacity"])
def test_rejects_unsupported_component_domain(problem):
    receptor, rp, ligand, lp = _inputs()
    if problem == "float32":
        receptor = replace(receptor, coordinates=receptor.coordinates.float())
    elif problem == "multimodel":
        receptor = replace(receptor, coordinates=receptor.coordinates.repeat(2, 1, 1))
    elif problem == "periodic":
        receptor = replace(receptor, cell=UnitCell.orthorhombic((20.0, 20.0, 20.0)))
    elif problem == "unsupported_element":
        receptor = replace(receptor, atoms=(replace(receptor.atoms[0], element="F", atomic_number=9), receptor.atoms[1]))
    else:
        domain = ReferenceApplicabilityDomain(max_atoms=3)
        rp, lp = replace(rp, applicability_domain=domain), replace(lp, applicability_domain=domain)
    rp = replace(rp, topology_sha256=canonical_topology_sha256(receptor))
    with pytest.raises(FixedPoseAssemblyError):
        _assemble((receptor, rp, ligand, lp))


def test_wrapper_keeps_zero_evaluated_values_distinct_from_missing_terms():
    receptor = _component("R", ((0.0, 0.0, 0.0),), (0.0,))
    ligand = _component("L", ((4.0, 0.0, 0.0),), (0.0,))
    rp = _parameters(receptor, atom_parameters=(AtomNonbondedParameter(0, 1.0, 0.0, 0.0),))
    lp = _parameters(ligand, atom_parameters=(AtomNonbondedParameter(0, 1.0, 0.0, 0.0),))
    result = _evaluate((receptor, rp, ligand, lp))
    for name in ("total_energy", "cross_energy"):
        assert result["quantities"][name]["value"] == 0.0
        assert result["quantities"][name]["status"] == "evaluated"
    for name in ("total_forces", "cross_forces"):
        assert result["quantities"][name]["value"] == [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
    assert result["not_evaluated"] == {name: None for name in (
        "strain", "solvation", "ai_correction", "uncertainty", "pose_retention", "improper", "entropy",
    )}


def test_wrapper_retains_existing_minimum_distance_admission():
    receptor = _component("R", ((0.0, 0.0, 0.0),), (0.0,))
    ligand = _component("L", ((0.1, 0.0, 0.0),), (0.0,))
    with pytest.raises(FixedPoseError, match="minimum|distance"):
        _evaluate((receptor, _parameters(receptor), ligand, _parameters(ligand)))


@pytest.mark.parametrize("missing", ["angles", "torsions"])
def test_rejects_missing_source_graph_paths_before_rebinding(missing):
    receptor = _component("R", ((0.0, 0.0, 0.0),), (0.0,))
    ligand = _component("L", ((3.0, 0.0, 0.0), (4.0, 0.1, 0.0), (4.4, 1.0, 0.0), (5.2, 1.2, 0.8)),
                        (0.1, -0.1, 0.0, 0.0), bonds=((0, 1), (1, 2), (2, 3)))
    parameters = _parameters(ligand,
                             angles=(HarmonicAngleParameter(0, 1, 2, 1.3, 4.0), HarmonicAngleParameter(1, 2, 3, 1.4, 5.0)),
                             torsions=(PeriodicTorsionParameter(0, 1, 2, 3, 1, 0.3, 0.0),))
    with pytest.raises(FixedPoseAssemblyError, match="exactly cover"):
        _assemble((receptor, _parameters(receptor), ligand, replace(parameters, **{missing: ()})))


def test_same_rigid_transform_of_components_and_pocket_rotates_forces():
    inputs = _inputs()
    original = _evaluate(inputs)
    rotation = torch.tensor([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]], dtype=torch.float64)
    shift = torch.tensor([1.0, -2.0, 0.5], dtype=torch.float64)
    moved = tuple(replace(value, coordinates=value.coordinates @ rotation.T + shift) if i in (0, 2) else value
                  for i, value in enumerate(inputs))
    pocket = _pocket(center=shift)
    result = _evaluate(moved, pocket=pocket)
    for name in ("total_energy", "cross_energy"):
        assert result["quantities"][name]["value"] == pytest.approx(original["quantities"][name]["value"], abs=2e-11)
    for name in ("total_forces", "cross_forces"):
        before = torch.tensor(original["quantities"][name]["value"], dtype=torch.float64)
        after = torch.tensor(result["quantities"][name]["value"], dtype=torch.float64)
        assert torch.allclose(after, before @ rotation.T, atol=2e-11, rtol=2e-11)


def test_wrapper_returns_replayable_actual_combined_system_and_parameters():
    inputs = _inputs()
    result = _evaluate(inputs)
    reconstructed = all_atom_system_from_canonical_json(json.dumps(result["evaluated_system"]), device="cpu")
    assembly = _assemble(inputs)
    assert canonical_system_sha256(reconstructed) == canonical_system_sha256(assembly.system)
    assert result["evaluated_parameters"] == assembly.parameters.to_dict()
    assert result["evaluated_system"]["system_sha256"] == result["assembly"]["system_sha256"]


def test_combined_atom_limit_does_not_expand_either_parent_domain():
    receptor = _component("R", tuple((float(i), 0.0, 0.0) for i in range(129)), (0.0,) * 129)
    ligand = _component("L", tuple((float(i), 1.0, 0.0) for i in range(128)), (0.0,) * 128)
    with pytest.raises(FixedPoseAssemblyError, match="exceeds 256"):
        _assemble((receptor, _parameters(receptor), ligand, _parameters(ligand)))
