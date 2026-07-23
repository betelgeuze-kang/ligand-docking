from __future__ import annotations

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.docking import (  # noqa: E402
    DockingProblemIdentity,
    ReferenceDockingScoreConfig,
    admit_reference_docking_scorer,
    assess_reference_docking_applicability,
)
from betelgeuze_engine_v2.molecular import (  # noqa: E402
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
    atomic_number_for_element,
    canonical_system_sha256,
    canonical_topology_sha256,
)
from betelgeuze_engine_v2.physics import (  # noqa: E402
    AtomNonbondedParameter,
    HarmonicBondParameter,
    ReferenceForceFieldParameters,
)


def _system(
    system_id: str,
    elements: tuple[str, ...],
    partial_charges: tuple[float | None, ...],
    coordinates: tuple[tuple[float, float, float], ...],
    *,
    entity_type: str,
    formal_charges: tuple[int, ...] | None = None,
    aromatic_atoms: tuple[int, ...] = (),
    atom_stereo: tuple[str, ...] | None = None,
    bonds: tuple[tuple[int, int], ...] = (),
    aromatic_bonds: tuple[int, ...] = (),
) -> AllAtomSystem:
    charges = formal_charges or (0,) * len(elements)
    stereo = atom_stereo or ("unspecified",) * len(elements)
    atoms = tuple(
        Atom(
            index=index,
            name=f"{element}{index + 1}",
            element=element,
            atomic_number=atomic_number_for_element(element),
            residue_index=0,
            formal_charge=charges[index],
            partial_charge_e=partial_charges[index],
            aromatic=index in aromatic_atoms,
            stereo=stereo[index],
        )
        for index, element in enumerate(elements)
    )
    bond_rows = tuple(
        Bond(
            index=index,
            atom_i=atom_i,
            atom_j=atom_j,
            aromatic=index in aromatic_bonds,
        )
        for index, (atom_i, atom_j) in enumerate(bonds)
    )
    return AllAtomSystem(
        system_id=system_id,
        atoms=atoms,
        bonds=bond_rows,
        residues=(
            Residue(
                index=0,
                name="REC" if entity_type == "polymer" else "LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(len(atoms))),
                entity_type=entity_type,
                hetero=entity_type != "polymer",
            ),
        ),
        chains=(Chain(index=0, chain_id="A", residue_indices=(0,)),),
        coordinates=torch.tensor((coordinates,), dtype=torch.float64),
        provenance=StructureProvenance(source_format="unit-test"),
    )


def _parameters(
    system: AllAtomSystem,
    *,
    topology_sha256: str | None = None,
    parameter_indices: tuple[int, ...] | None = None,
    charge_overrides: dict[int, float] | None = None,
    include_bonds: bool = True,
) -> ReferenceForceFieldParameters:
    indices = (
        tuple(range(system.atom_count))
        if parameter_indices is None
        else parameter_indices
    )
    overrides = charge_overrides or {}
    atom_parameters = tuple(
        AtomNonbondedParameter(
            atom_index=index,
            sigma_angstrom=3.0,
            epsilon_kcal_per_mol=0.12,
            charge_e=overrides.get(
                index,
                0.0
                if system.atoms[index].partial_charge_e is None
                else float(system.atoms[index].partial_charge_e),
            ),
        )
        for index in indices
    )
    bond_parameters = (
        tuple(
            HarmonicBondParameter(
                atom_i=bond.atom_i,
                atom_j=bond.atom_j,
                equilibrium_angstrom=float(
                    torch.linalg.vector_norm(
                        system.coordinates[0, bond.atom_i]
                        - system.coordinates[0, bond.atom_j]
                    ).item()
                ),
                force_constant_kcal_per_mol_angstrom2=100.0,
            )
            for bond in system.bonds
        )
        if include_bonds
        else ()
    )
    return ReferenceForceFieldParameters(
        parameter_set_id=f"{system.system_id}-parameters",
        parameter_set_version="1.0.0",
        topology_sha256=topology_sha256 or canonical_topology_sha256(system),
        atom_parameters=atom_parameters,
        bonds=bond_parameters,
        excluded_pairs=(
            tuple((bond.atom_i, bond.atom_j) for bond in system.bonds)
            if include_bonds
            else ()
        ),
        cutoff_angstrom=10.0,
        switch_start_angstrom=8.0,
    )


def _problem(
    receptor: AllAtomSystem,
    ligand: AllAtomSystem,
    *,
    receptor_sha256: str | None = None,
) -> DockingProblemIdentity:
    return DockingProblemIdentity(
        receptor_system_sha256=(receptor_sha256 or canonical_system_sha256(receptor)),
        ligand_system_sha256=canonical_system_sha256(ligand),
        pocket_definition_sha256="a" * 64,
    )


def _supported_fixture():
    receptor = _system(
        "receptor",
        ("C",),
        (0.2,),
        ((0.0, 0.0, 0.0),),
        entity_type="polymer",
    )
    ligand = _system(
        "ligand",
        ("C", "O"),
        (0.3, -0.3),
        ((3.0, 0.0, 0.0), (4.2, 0.0, 0.0)),
        entity_type="non-polymer",
        bonds=((0, 1),),
    )
    return (
        receptor,
        ligand,
        _parameters(receptor),
        _parameters(ligand),
        _problem(receptor, ligand),
    )


def test_supported_inputs_return_identity_bound_scorer_admission() -> None:
    receptor, ligand, receptor_parameters, ligand_parameters, problem = (
        _supported_fixture()
    )
    admission = admit_reference_docking_scorer(
        receptor,
        ligand,
        receptor_parameters,
        ligand_parameters,
        problem,
    )

    assert admission.admitted
    assert admission.scorer is not None
    assessment = admission.assessment
    assert assessment.disposition == "admitted_diagnostic"
    assert assessment.diagnostic_scorer_admitted
    assert assessment.interaction_coverage_complete
    assert not assessment.ood_detected
    assert assessment.admission_blockers == ()
    assert assessment.receptor.system_sha256 == canonical_system_sha256(receptor)
    assert assessment.ligand.system_sha256 == canonical_system_sha256(ligand)
    assert (
        assessment.parameter_source_sha256 == admission.scorer.parameter_source_sha256
    )
    assert not assessment.scientifically_validated
    assert not assessment.claim_safe
    assert len(assessment.fingerprint_sha256) == 64
    assert (
        assess_reference_docking_applicability(
            receptor,
            ligand,
            receptor_parameters,
            ligand_parameters,
            problem,
        )
        == assessment
    )


def test_combined_chemistry_charge_and_parameter_failures_are_all_retained() -> None:
    receptor = _system(
        "zinc-cofactor",
        ("Zn",),
        (None,),
        ((0.0, 0.0, 0.0),),
        entity_type="non-polymer",
        formal_charges=(5,),
    )
    ligand = _system(
        "charged-ligand",
        ("C",),
        (0.25,),
        ((3.0, 0.0, 0.0),),
        entity_type="non-polymer",
    )
    ligand_parameters = _parameters(
        ligand,
        topology_sha256="f" * 64,
        charge_overrides={0: -0.25},
    )
    admission = admit_reference_docking_scorer(
        receptor,
        ligand,
        None,
        ligand_parameters,
        _problem(receptor, ligand),
    )

    assert not admission.admitted
    assessment = admission.assessment
    assert assessment.disposition == "abstain_chemistry_scope"
    assert not assessment.interaction_coverage_complete
    assert assessment.ood_detected
    assert assessment.receptor.metal_atom_indices == (0,)
    assert assessment.receptor.metal_atomic_numbers == (30,)
    assert assessment.receptor.formal_charge_outlier_atom_indices == (0,)
    assert assessment.receptor.missing_partial_charge_atom_indices == (0,)
    assert len(assessment.receptor.receptor_nonpolymer_residues) == 1
    assert {
        "receptor_metal_coordination_unsupported",
        "receptor_unsupported_atomic_numbers",
        "receptor_formal_charge_outside_scope",
        "receptor_nonpolymer_cofactor_outside_scope",
    } <= set(assessment.chemistry_scope_blockers)
    assert {
        "receptor_parameters_missing",
        "receptor_partial_charge_missing",
        "ligand_parameter_topology_identity_mismatch",
        "ligand_partial_charge_parameter_mismatch",
    } <= set(assessment.parameter_scope_blockers)


def test_aromatic_and_declared_stereo_remain_admitted_but_incomplete() -> None:
    receptor, ligand, receptor_parameters, _ligand_parameters, problem = (
        _supported_fixture()
    )
    ligand = _system(
        "aromatic-stereo-ligand",
        ("C", "O"),
        (0.3, -0.3),
        ((3.0, 0.0, 0.0), (4.2, 0.0, 0.0)),
        entity_type="non-polymer",
        aromatic_atoms=(0,),
        atom_stereo=("R", "unspecified"),
        bonds=((0, 1),),
        aromatic_bonds=(0,),
    )
    problem = _problem(receptor, ligand)
    admission = admit_reference_docking_scorer(
        receptor,
        ligand,
        receptor_parameters,
        _parameters(ligand),
        problem,
    )

    assert admission.admitted
    assert admission.assessment.disposition == "admitted_diagnostic"
    assert not admission.assessment.interaction_coverage_complete
    assert admission.assessment.ood_detected
    assert {
        "ligand_aromatic_specific_interactions_missing",
        "ligand_stereochemistry_geometry_not_verified",
    } == set(admission.assessment.interaction_coverage_blockers)
    assert admission.assessment.admission_blockers == ()


def test_identity_and_capacity_failures_preserve_both_categories() -> None:
    receptor = _system(
        "two-atom-receptor",
        ("C", "O"),
        (0.1, -0.1),
        ((0.0, 0.0, 0.0), (1.5, 0.0, 0.0)),
        entity_type="polymer",
    )
    ligand = _system(
        "two-atom-ligand",
        ("C", "O"),
        (0.2, -0.2),
        ((3.0, 0.0, 0.0), (4.2, 0.0, 0.0)),
        entity_type="non-polymer",
        bonds=((0, 1),),
    )
    assessment = assess_reference_docking_applicability(
        receptor,
        ligand,
        _parameters(receptor),
        _parameters(ligand),
        _problem(receptor, ligand, receptor_sha256="f" * 64),
        config=ReferenceDockingScoreConfig(max_cross_pairs=1),
    )

    assert assessment.disposition == "invalid_input"
    assert "docking_problem_receptor_identity_mismatch" in (
        assessment.invalid_input_blockers
    )
    assert "receptor_ligand_cross_pair_capacity_exceeded" in (
        assessment.execution_scope_blockers
    )


def test_ligand_bond_parameter_coverage_abstains_before_construction() -> None:
    receptor, ligand, receptor_parameters, _ligand_parameters, problem = (
        _supported_fixture()
    )
    admission = admit_reference_docking_scorer(
        receptor,
        ligand,
        receptor_parameters,
        _parameters(ligand, include_bonds=False),
        problem,
    )

    assert not admission.admitted
    assert admission.assessment.disposition == "abstain_parameter_scope"
    assert "ligand_bond_parameter_coverage_mismatch" in (
        admission.assessment.parameter_scope_blockers
    )


def test_dynamic_reference_energy_failure_becomes_structured_abstention() -> None:
    receptor, _ligand, receptor_parameters, _ligand_parameters, _problem_row = (
        _supported_fixture()
    )
    ligand = _system(
        "overlapping-ligand",
        ("C", "O"),
        (0.3, -0.3),
        ((3.0, 0.0, 0.0), (3.1, 0.0, 0.0)),
        entity_type="non-polymer",
    )
    admission = admit_reference_docking_scorer(
        receptor,
        ligand,
        receptor_parameters,
        _parameters(ligand),
        _problem(receptor, ligand),
    )

    assert not admission.admitted
    assert admission.assessment.disposition == "abstain_execution_scope"
    assert admission.assessment.execution_scope_blockers == (
        "reference_scorer_construction_failed",
    )
