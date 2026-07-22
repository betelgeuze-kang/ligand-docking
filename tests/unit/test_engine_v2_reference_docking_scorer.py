from __future__ import annotations

from dataclasses import replace

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.docking import (  # noqa: E402
    DEFAULT_SUPPORTED_DOCKING_ATOMIC_NUMBERS,
    DockingBudget,
    DockingProblemIdentity,
    ReferenceDockingScoringError,
    TorsionSearchSpace,
    UncalibratedReferenceDockingScorer,
    generate_bounded_docking_proposals,
    run_bounded_docking_search,
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
    charges: tuple[float, ...],
    coordinates: tuple[tuple[float, float, float], ...],
    *,
    bonds: tuple[tuple[int, int], ...] = (),
    entity_type: str,
) -> AllAtomSystem:
    atoms = tuple(
        Atom(
            index=index,
            name=f"{element}{index + 1}",
            element=element,
            atomic_number=atomic_number_for_element(element),
            residue_index=0,
            formal_charge=0,
            partial_charge_e=charges[index],
        )
        for index, element in enumerate(elements)
    )
    bond_rows = tuple(
        Bond(index=index, atom_i=first, atom_j=second)
        for index, (first, second) in enumerate(bonds)
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


def _parameters(system: AllAtomSystem) -> ReferenceForceFieldParameters:
    sigma_by_element = {"C": 3.4, "O": 3.0, "Zn": 2.5}
    atom_parameters = tuple(
        AtomNonbondedParameter(
            atom_index=atom.index,
            sigma_angstrom=sigma_by_element[atom.element],
            epsilon_kcal_per_mol=0.12 if atom.element == "C" else 0.18,
            charge_e=float(atom.partial_charge_e),
        )
        for atom in system.atoms
    )
    harmonic_bonds = tuple(
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
    return ReferenceForceFieldParameters(
        parameter_set_id=f"{system.system_id}-unit-parameters",
        parameter_set_version="1.0.0",
        topology_sha256=canonical_topology_sha256(system),
        atom_parameters=atom_parameters,
        bonds=harmonic_bonds,
        excluded_pairs=tuple((bond.atom_i, bond.atom_j) for bond in system.bonds),
        cutoff_angstrom=10.0,
        switch_start_angstrom=8.0,
    )


def _fixture(receptor_charge: float = 0.25):
    receptor = _system(
        "receptor",
        ("C",),
        (receptor_charge,),
        ((0.0, 0.0, 0.0),),
        entity_type="polymer",
    )
    ligand = _system(
        "ligand",
        ("C", "O"),
        (0.30, -0.30),
        ((3.0, 0.0, 0.0), (4.2, 0.0, 0.0)),
        bonds=((0, 1),),
        entity_type="non-polymer",
    )
    problem = DockingProblemIdentity(
        receptor_system_sha256=canonical_system_sha256(receptor),
        ligand_system_sha256=canonical_system_sha256(ligand),
        pocket_definition_sha256="a" * 64,
    )
    space = TorsionSearchSpace(
        local_offsets=torch.tensor(
            [[0.0, 0.0, 0.0], [1.2, 0.0, 0.0]],
            dtype=torch.float64,
        ),
        parent=torch.tensor([-1, 0], dtype=torch.long),
        local_axes=torch.tensor([[0.0, 0.0, 1.0]] * 2, dtype=torch.float64),
        rotatable_mask=torch.tensor([False, False]),
        root_positions=torch.tensor([[3.0, 0.0, 0.0]], dtype=torch.float64),
    )
    scorer = UncalibratedReferenceDockingScorer(
        receptor,
        ligand,
        _parameters(receptor),
        _parameters(ligand),
        problem,
    )
    return receptor, ligand, problem, space, scorer


def _term_map(breakdown):
    return {term.term_id: term for term in breakdown.terms}


def test_reference_scorer_emits_four_parameter_bound_terms_in_search_rows() -> None:
    _receptor, _ligand, problem, space, scorer = _fixture()
    result = run_bounded_docking_search(
        space,
        DockingBudget(
            candidate_count=4,
            top_k=2,
            max_torsions=0,
            translation_radius_angstrom=1.0,
            seed=41,
        ),
        scorer,
        problem=problem,
        diversity_rmsd_angstrom=0.0,
    )

    assert result.success_count == 4
    assert "score_term_decomposition_missing" not in result.blockers
    assert "docking_score_uncalibrated" in result.blockers
    assert not scorer.validated_for_docking_ranking
    assert scorer.score_descriptor.unit == "kcal/mol"
    assert tuple(scorer.chemistry_scope["supported_atomic_numbers"]) == (
        DEFAULT_SUPPORTED_DOCKING_ATOMIC_NUMBERS
    )
    expected_terms = {
        "receptor_ligand_lennard_jones",
        "receptor_ligand_screened_coulomb",
        "ligand_internal_strain_delta",
        "vdw_overlap_penalty",
    }
    for row in result.rows:
        assert row.score_breakdown is not None
        assert set(_term_map(row.score_breakdown)) == expected_terms
        assert all(
            len(term.parameter_source_sha256) == 64
            for term in row.score_breakdown.terms
        )
        assert row.score == pytest.approx(row.score_breakdown.total_score)


def test_ligand_strain_delta_uses_bound_reference_force_field() -> None:
    _receptor, _ligand, problem, space, scorer = _fixture()
    baseline = generate_bounded_docking_proposals(
        space,
        DockingBudget(
            candidate_count=1,
            top_k=1,
            max_torsions=0,
            translation_radius_angstrom=0.0,
        ),
        problem=problem,
    )[0]
    baseline_terms = _term_map(scorer.score(baseline))
    assert baseline_terms["ligand_internal_strain_delta"].raw_value == pytest.approx(
        0.0,
        abs=1.0e-12,
    )

    distorted_coordinates = baseline.coordinates.clone()
    distorted_coordinates[1, 0] += 0.4
    distorted = baseline.with_refined_coordinates(
        distorted_coordinates,
        refiner_id="unit-test-distortion",
        refiner_version="1.0.0",
    )
    distorted_terms = _term_map(scorer.score(distorted))
    assert distorted_terms["ligand_internal_strain_delta"].raw_value == pytest.approx(
        8.0,
        rel=1.0e-10,
    )


def test_explicit_charge_changes_only_charge_dependent_interaction_direction() -> None:
    _receptor, _ligand, problem, space, positive_scorer = _fixture(0.25)
    positive_pose = generate_bounded_docking_proposals(
        space,
        DockingBudget(candidate_count=1, top_k=1, max_torsions=0),
        problem=problem,
    )[0]
    positive = _term_map(positive_scorer.score(positive_pose))

    _negative_receptor, _negative_ligand, negative_problem, negative_space, negative_scorer = (
        _fixture(-0.25)
    )
    negative_pose = generate_bounded_docking_proposals(
        negative_space,
        DockingBudget(candidate_count=1, top_k=1, max_torsions=0),
        problem=negative_problem,
    )[0]
    negative = _term_map(negative_scorer.score(negative_pose))

    assert positive["receptor_ligand_screened_coulomb"].raw_value == pytest.approx(
        -negative["receptor_ligand_screened_coulomb"].raw_value,
    )
    assert positive["receptor_ligand_lennard_jones"].raw_value == pytest.approx(
        negative["receptor_ligand_lennard_jones"].raw_value,
    )
    assert positive["vdw_overlap_penalty"].raw_value == pytest.approx(
        negative["vdw_overlap_penalty"].raw_value,
    )


def test_unsupported_metal_mismatched_charge_and_receptor_cofactor_fail_closed() -> None:
    receptor, ligand, _problem, _space, _scorer = _fixture()
    zinc_receptor = _system(
        "zinc-receptor",
        ("Zn",),
        (2.0,),
        ((0.0, 0.0, 0.0),),
        entity_type="polymer",
    )
    zinc_problem = DockingProblemIdentity(
        receptor_system_sha256=canonical_system_sha256(zinc_receptor),
        ligand_system_sha256=canonical_system_sha256(ligand),
        pocket_definition_sha256="a" * 64,
    )
    with pytest.raises(ReferenceDockingScoringError, match="outside the supported scope"):
        UncalibratedReferenceDockingScorer(
            zinc_receptor,
            ligand,
            _parameters(zinc_receptor),
            _parameters(ligand),
            zinc_problem,
        )

    mismatched_parameters = replace(
        _parameters(receptor),
        parameter_set_id="mismatched-charge",
        atom_parameters=(
            replace(_parameters(receptor).atom_parameters[0], charge_e=-0.25),
        ),
    )
    problem = DockingProblemIdentity(
        receptor_system_sha256=canonical_system_sha256(receptor),
        ligand_system_sha256=canonical_system_sha256(ligand),
        pocket_definition_sha256="a" * 64,
    )
    with pytest.raises(ReferenceDockingScoringError, match="partial charge"):
        UncalibratedReferenceDockingScorer(
            receptor,
            ligand,
            mismatched_parameters,
            _parameters(ligand),
            problem,
        )

    cofactor_receptor = replace(
        receptor,
        residues=(replace(receptor.residues[0], entity_type="non-polymer"),),
    )
    cofactor_problem = DockingProblemIdentity(
        receptor_system_sha256=canonical_system_sha256(cofactor_receptor),
        ligand_system_sha256=canonical_system_sha256(ligand),
        pocket_definition_sha256="a" * 64,
    )
    with pytest.raises(ReferenceDockingScoringError, match="cofactor-abstention"):
        UncalibratedReferenceDockingScorer(
            cofactor_receptor,
            ligand,
            _parameters(cofactor_receptor),
            _parameters(ligand),
            cofactor_problem,
        )
