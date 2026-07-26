from __future__ import annotations

from dataclasses import replace

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.docking import (  # noqa: E402
    INTERPRETABLE_LOCAL_REFINEMENT_V0_BLOCKERS,
    DockingBudget,
    DockingProblemIdentity,
    InterpretableLocalPoseRefinerV0,
    InterpretableLocalRefinementConfig,
    InterpretableLocalRefinementError,
    InterpretableLocalRefinementReceipt,
    InterpretablePoseScorerV0,
    PoseValidityConfig,
    PoseValidityContext,
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
    atomic_number_for_element,
    canonical_system_sha256,
)


def _system(
    system_id: str,
    elements: tuple[str, ...],
    coordinates: tuple[tuple[float, float, float], ...],
    *,
    bonds: tuple[tuple[int, int, float], ...] = (),
    entity_type: str,
) -> AllAtomSystem:
    atoms = tuple(
        Atom(
            index=index,
            name=f"{element}{index + 1}",
            element=element,
            atomic_number=atomic_number_for_element(element),
            residue_index=0,
        )
        for index, element in enumerate(elements)
    )
    bond_rows = tuple(
        Bond(
            index=index,
            atom_i=first,
            atom_j=second,
            order=order,
            aromatic=False,
            metadata={"is_in_ring": False},
        )
        for index, (first, second, order) in enumerate(bonds)
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


def _fixture():
    receptor = _system(
        "local-refinement-receptor",
        ("C",),
        ((10.0, 10.0, 10.0),),
        entity_type="polymer",
    )
    ligand = _system(
        "local-refinement-ligand",
        ("C", "C", "C", "C"),
        (
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 0.0),
            (1.4, 0.0, 0.0),
            (1.8, 1.1, 0.7),
        ),
        bonds=((0, 1, 1.0), (1, 2, 1.0), (2, 3, 1.0)),
        entity_type="non-polymer",
    )
    problem = DockingProblemIdentity(
        receptor_system_sha256=canonical_system_sha256(receptor),
        ligand_system_sha256=canonical_system_sha256(ligand),
        pocket_definition_sha256="a" * 64,
    )
    scorer = InterpretablePoseScorerV0(receptor, ligand, problem)
    space, _torsion_receipt = build_molecular_torsion_search_space(ligand)
    proposals = generate_bounded_docking_proposals(
        space,
        DockingBudget(
            candidate_count=2,
            top_k=1,
            max_torsions=1,
            translation_radius_angstrom=0.0,
            seed=101,
        ),
        problem=problem,
    )
    return receptor, ligand, problem, scorer, space, proposals[1]


def _bond_lengths(system: AllAtomSystem, coordinates: torch.Tensor) -> torch.Tensor:
    return torch.tensor(
        [
            torch.linalg.vector_norm(
                coordinates[bond.atom_i] - coordinates[bond.atom_j]
            )
            for bond in system.bonds
        ],
        dtype=torch.float64,
    )


def test_rigid_torsion_refinement_is_deterministic_and_constraint_preserving() -> None:
    _receptor, ligand, _problem, scorer, _space, proposal = _fixture()
    refiner = InterpretableLocalPoseRefinerV0(
        scorer,
        config=InterpretableLocalRefinementConfig(maximum_steps=8),
    )

    refined, receipt = refiner.refine_with_receipt(proposal, max_steps=8)
    repeated, repeated_receipt = refiner.refine_with_receipt(
        proposal,
        max_steps=8,
    )

    assert refined.fingerprint_sha256 == repeated.fingerprint_sha256
    assert receipt.to_dict() == repeated_receipt.to_dict()
    assert receipt.final_score < receipt.initial_score
    assert receipt.accepted_step_count >= 1
    assert any(
        step.move_id.startswith("torsion_bond_")
        for step in receipt.steps
        if step.outcome == "accepted"
    )
    assert receipt.evaluated_move_count == sum(
        step.evaluated_move_count for step in receipt.steps
    )
    assert receipt.rejected_move_count == sum(
        step.rejected_move_count for step in receipt.steps
    )
    assert receipt.maximum_bond_length_residual_angstrom <= 1.0e-8
    assert receipt.maximum_angle_residual_radians <= 1.0e-8
    torch.testing.assert_close(
        _bond_lengths(ligand, refined.coordinates),
        _bond_lengths(ligand, ligand.coordinates[0]),
        atol=1.0e-10,
        rtol=0.0,
    )
    assert refined.parent_proposal_fingerprint_sha256 == proposal.fingerprint_sha256
    assert refined.refinement_receipt_sha256 == receipt.fingerprint_sha256
    assert receipt.torsion_search_receipt.rotatable_bond_count == 1
    assert receipt.blockers == INTERPRETABLE_LOCAL_REFINEMENT_V0_BLOCKERS
    assert receipt.to_dict()["objective_is_force_field_energy"] is False
    assert receipt.to_dict()["analytic_forces_available"] is False
    assert receipt.to_dict()["scientifically_validated"] is False
    assert receipt.to_dict()["claim_safe"] is False
    assert len(receipt.term_deltas) == 9


def test_search_preserves_refinement_receipts_for_every_refined_row() -> None:
    receptor, ligand, problem, scorer, space, _proposal = _fixture()
    refiner = InterpretableLocalPoseRefinerV0(
        scorer,
        config=InterpretableLocalRefinementConfig(maximum_steps=3),
    )
    budget = DockingBudget(
        candidate_count=3,
        top_k=2,
        max_torsions=1,
        max_refinement_steps=3,
        translation_radius_angstrom=0.0,
        seed=101,
    )
    bond_pairs = tuple((bond.atom_i, bond.atom_j) for bond in ligand.bonds)
    validity_context = PoseValidityContext(
        problem_fingerprint_sha256=problem.fingerprint_sha256,
        reference_coordinates=ligand.coordinates[0],
        bond_pairs=bond_pairs,
        excluded_nonbonded_pairs=bond_pairs,
        receptor_coordinates=receptor.coordinates[0],
        pocket_center=torch.zeros(3, dtype=torch.float64),
        chirality_centers=(),
        config=PoseValidityConfig(pocket_radius_angstrom=20.0),
    )

    result = run_bounded_docking_search(
        space,
        budget,
        scorer,
        refiner=refiner,
        validity_context=validity_context,
        problem=problem,
    )

    assert result.success_count == 3
    assert result.refiner_id == refiner.refiner_id
    assert "refinement_receipt_missing_rows" not in result.blockers
    assert all(row.refined for row in result.rows)
    assert all(
        isinstance(row.refinement_receipt, InterpretableLocalRefinementReceipt)
        for row in result.rows
    )
    for row in result.rows:
        payload = row.to_dict()
        assert row.proposal is not None
        assert row.refinement_receipt is not None
        assert payload["refinement_receipt_sha256"] == (
            row.proposal.refinement_receipt_sha256
        )
        assert payload["refinement_receipt"]["receipt_sha256"] == (
            row.proposal.refinement_receipt_sha256
        )


def test_refiner_fails_closed_on_bounds_identity_and_receipt_tampering() -> None:
    _receptor, _ligand, _problem, scorer, _space, proposal = _fixture()
    refiner = InterpretableLocalPoseRefinerV0(
        scorer,
        config=InterpretableLocalRefinementConfig(maximum_steps=2),
    )
    with pytest.raises(InterpretableLocalRefinementError, match="configured bound"):
        refiner.refine(proposal, max_steps=3)

    other_problem = DockingProblemIdentity(
        receptor_system_sha256="b" * 64,
        ligand_system_sha256="c" * 64,
        pocket_definition_sha256="d" * 64,
    )
    other_space, _receipt = build_molecular_torsion_search_space(scorer.ligand)
    other_problem_proposal = generate_bounded_docking_proposals(
        other_space,
        DockingBudget(
            candidate_count=1,
            top_k=1,
            max_torsions=1,
            translation_radius_angstrom=0.0,
        ),
        problem=other_problem,
    )[0]
    with pytest.raises(
        InterpretableLocalRefinementError,
        match="problem identity",
    ):
        refiner.refine(other_problem_proposal, max_steps=1)

    _refined, receipt = refiner.refine_with_receipt(proposal, max_steps=2)
    with pytest.raises(InterpretableLocalRefinementError, match="must not increase"):
        replace(receipt, final_score=receipt.initial_score + 1.0)
    with pytest.raises(InterpretableLocalRefinementError, match="cross-wired"):
        replace(receipt, torsion_search_space_sha256="c" * 64)


def test_interpretable_local_refinement_symbols_are_reexported() -> None:
    from betelgeuze_engine_v2 import docking
    from betelgeuze_engine_v2.docking.interpretable_refinement import (
        __all__ as refinement_exports,
    )

    assert set(refinement_exports) <= set(docking.__all__)
