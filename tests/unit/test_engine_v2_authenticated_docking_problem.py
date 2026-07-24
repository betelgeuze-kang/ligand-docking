from __future__ import annotations

from dataclasses import replace

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.docking import (  # noqa: E402
    DockingBudget,
    DockingProblemInput,
    DockingProblemInputError,
    DockingProposalError,
    MolecularTorsionSearchConfig,
    PocketDefinition,
    PoseValidityConfig,
    PoseValidityContext,
    bind_molecular_torsion_search_space,
    build_authenticated_rigid_search_space,
    build_molecular_torsion_search_space,
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
    canonical_system_sha256,
)


def _system(
    system_id: str,
    coordinates: tuple[tuple[float, float, float], ...],
    bonds: tuple[tuple[int, int], ...],
    *,
    dtype: torch.dtype = torch.float64,
) -> AllAtomSystem:
    atoms = tuple(
        Atom(
            index=index,
            name=f"C{index + 1}",
            element="C",
            atomic_number=6,
            residue_index=0,
        )
        for index in range(len(coordinates))
    )
    return AllAtomSystem(
        system_id=system_id,
        atoms=atoms,
        bonds=tuple(
            Bond(index=index, atom_i=first, atom_j=second)
            for index, (first, second) in enumerate(bonds)
        ),
        residues=(
            Residue(
                index=0,
                name="LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(len(atoms))),
                entity_type="non-polymer",
                hetero=True,
            ),
        ),
        chains=(Chain(index=0, chain_id="A", residue_indices=(0,)),),
        coordinates=torch.tensor((coordinates,), dtype=dtype),
        provenance=StructureProvenance(source_format="unit-test"),
    )


def _receptor() -> AllAtomSystem:
    return _system("receptor", ((50.0, 50.0, 50.0),), ())


def _ligand(*, dtype: torch.dtype = torch.float64) -> AllAtomSystem:
    return _system(
        "ligand",
        (
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 0.0),
            (1.4, 0.0, 0.0),
            (1.8, 1.1, 0.7),
        ),
        ((0, 1), (1, 2), (2, 3)),
        dtype=dtype,
    )


def _problem_input() -> DockingProblemInput:
    receptor = _receptor()
    ligand = _ligand()
    search_space, molecular_receipt = build_molecular_torsion_search_space(
        ligand,
        config=MolecularTorsionSearchConfig(max_rotatable_bonds=1),
    )
    derivation = bind_molecular_torsion_search_space(
        ligand,
        search_space,
        molecular_receipt,
    )
    pocket = PocketDefinition(
        receptor_system_sha256=canonical_system_sha256(receptor),
        center_angstrom=(0.5, 0.5, 0.0),
        radius_angstrom=20.0,
        coordinate_frame_id="receptor-input-frame-v1",
        derivation_policy_id="unit-test-explicit-pocket/1.0.0",
        source_receipt_sha256="a" * 64,
    )
    return DockingProblemInput(
        receptor=receptor,
        ligand=ligand,
        pocket=pocket,
        search_space=search_space,
        search_space_derivation=derivation,
        source_artifact_sha256_by_role={
            "receptor": "b" * 64,
            "ligand": "c" * 64,
        },
    )


class _Scorer:
    scorer_id = "authenticated-problem-test-scorer"
    scorer_version = "1.0.0"
    validated_for_docking_ranking = False
    implementation_source_sha256 = "d" * 64
    config_fingerprint_sha256 = "e" * 64

    def __init__(self, problem: DockingProblemInput) -> None:
        self.problem_fingerprint_sha256 = problem.identity.fingerprint_sha256

    def score(self, proposal):
        return proposal.coordinates.square().sum()


def _validity_context(problem: DockingProblemInput) -> PoseValidityContext:
    ligand = problem.ligand
    return PoseValidityContext(
        problem_fingerprint_sha256=problem.identity.fingerprint_sha256,
        reference_coordinates=ligand.coordinates[0],
        bond_pairs=tuple(
            (bond.atom_i, bond.atom_j) for bond in ligand.bonds
        ),
        excluded_nonbonded_pairs=tuple(
            (bond.atom_i, bond.atom_j) for bond in ligand.bonds
        ),
        receptor_coordinates=problem.receptor.coordinates[0],
        pocket_center=problem.pocket.center_tensor,
        chirality_centers=(),
        config=PoseValidityConfig(pocket_radius_angstrom=20.0),
    )


def test_authenticated_problem_binds_concrete_systems_pocket_and_derivation() -> None:
    problem = _problem_input()

    assert problem.identity.bound is True
    assert problem.identity.pocket_definition_sha256 == (
        problem.pocket.fingerprint_sha256
    )
    assert problem.search_space_derivation.search_space_sha256 == (
        problem.search_space.fingerprint_sha256
    )
    assert problem.to_dict()["authenticated_to_concrete_molecular_state"] is True

    result = run_bounded_docking_search(
        problem.search_space,
        DockingBudget(
            candidate_count=2,
            top_k=1,
            max_torsions=1,
            translation_radius_angstrom=0.0,
            seed=17,
        ),
        _Scorer(problem),
        validity_context=_validity_context(problem),
        problem=problem,
        diversity_rmsd_angstrom=0.0,
    )

    assert result.problem_input_fingerprint_sha256 == (
        problem.input_fingerprint_sha256
    )
    assert "docking_problem_input_not_authenticated" not in result.blockers
    assert len(result.numeric_policy_sha256) == 64
    assert len(result.rng_stream_initial_state_sha256) == 64
    assert len(result.rng_stream_final_state_sha256) == 64
    assert all(
        row.numeric_policy_sha256 == result.numeric_policy_sha256
        for row in result.rows
    )


def test_cross_wired_pocket_or_search_derivation_fails_closed() -> None:
    problem = _problem_input()
    wrong_pocket = replace(
        problem.pocket,
        receptor_system_sha256="f" * 64,
    )
    with pytest.raises(DockingProblemInputError, match="another receptor"):
        replace(problem, pocket=wrong_pocket)

    wrong_derivation = replace(
        problem.search_space_derivation,
        ligand_system_sha256="f" * 64,
    )
    with pytest.raises(DockingProblemInputError, match="another ligand"):
        replace(problem, search_space_derivation=wrong_derivation)


def test_rigid_search_space_receipt_is_bound_to_ligand_state() -> None:
    ligand = _ligand()
    space, receipt = build_authenticated_rigid_search_space(
        ligand,
        source_receipt_sha256="9" * 64,
    )

    assert space.torsion_count == 0
    assert receipt.ligand_system_sha256 == canonical_system_sha256(ligand)
    assert receipt.search_space_sha256 == space.fingerprint_sha256
    assert receipt.parent_derivation_receipt_sha256 == "9" * 64


def test_candidate_id_numeric_policy_and_rng_stream_are_canonical() -> None:
    problem = _problem_input()
    budget = DockingBudget(
        candidate_count=2,
        top_k=1,
        max_torsions=1,
        seed=23,
    )
    first = generate_bounded_docking_proposals(
        problem.search_space,
        budget,
        problem=problem,
    )
    repeated = generate_bounded_docking_proposals(
        problem.search_space,
        budget,
        problem=problem,
    )
    changed_seed = generate_bounded_docking_proposals(
        problem.search_space,
        replace(budget, seed=24),
        problem=problem,
    )

    assert [row.candidate_id for row in first] == [
        row.candidate_id for row in repeated
    ]
    assert [row.fingerprint_sha256 for row in first] == [
        row.fingerprint_sha256 for row in repeated
    ]
    assert first[0].numeric_policy_sha256 == repeated[0].numeric_policy_sha256
    assert first[0].rng_state_before_sha256 != (
        changed_seed[0].rng_state_before_sha256
    )
    assert first[0].candidate_id != changed_seed[0].candidate_id

    refined = first[0].with_refined_coordinates(
        first[0].coordinates + 0.01,
        refiner_id="unit-test-refiner",
        refiner_version="1.0.0",
    )
    assert refined.candidate_id == first[0].candidate_id
    assert refined.fingerprint_sha256 != first[0].fingerprint_sha256
    with pytest.raises(DockingProposalError, match="candidate_id"):
        replace(first[0], candidate_id="forged-candidate")


def test_symmetry_aware_direct_diversity_is_available_and_identity_bound() -> None:
    problem = _problem_input()
    result = run_bounded_docking_search(
        problem.search_space,
        DockingBudget(
            candidate_count=3,
            top_k=2,
            max_torsions=1,
            seed=31,
        ),
        _Scorer(problem),
        validity_context=_validity_context(problem),
        problem=problem,
        diversity_metric="symmetry_aware_direct_rmsd",
        symmetry_permutations=(
            (0, 1, 2, 3),
            (3, 2, 1, 0),
        ),
        diversity_rmsd_angstrom=0.0,
    )

    assert result.diversity_metric == "symmetry_aware_direct_rmsd"
    assert result.success_count == 3
    assert len(result.search_fingerprint_sha256) == 64
