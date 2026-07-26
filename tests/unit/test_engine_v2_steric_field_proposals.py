from __future__ import annotations

from dataclasses import replace
import hashlib
import json

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.docking import (  # noqa: E402
    DOCKING_STERIC_FIELD_SAMPLING_POLICY_ID,
    DOCKING_STERIC_FIELD_TRANSLATION_PLACEMENT_POLICY_ID,
    DockingBudget,
    DockingNumericPolicy,
    DockingProblemInput,
    DockingProposalError,
    PocketDefinition,
    StericFieldPlacementConfig,
    StericFieldPlacementError,
    build_authenticated_rigid_search_space,
    build_steric_field_placement_plan,
    generate_bounded_docking_proposals,
)
from betelgeuze_engine_v2.molecular import (  # noqa: E402
    AllAtomSystem,
    Atom,
    Chain,
    Residue,
    StructureProvenance,
    canonical_system_sha256,
)


def _system(system_id: str, coordinates: tuple[tuple[float, float, float], ...]) -> AllAtomSystem:
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
        bonds=(),
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
        coordinates=torch.tensor((coordinates,), dtype=torch.float64),
        provenance=StructureProvenance(source_format="unit-test"),
    )


def _problem() -> DockingProblemInput:
    receptor = _system("receptor", ((0.0, 0.0, 0.0),))
    ligand = _system("ligand", ((0.0, 0.0, 0.0),))
    search_space, derivation = build_authenticated_rigid_search_space(ligand)
    pocket = PocketDefinition(
        receptor_system_sha256=canonical_system_sha256(receptor),
        center_angstrom=(0.0, 0.0, 0.0),
        radius_angstrom=6.0,
        coordinate_frame_id="unit-test-pocket-frame",
        derivation_policy_id="explicit-unit-test-pocket/1.0.0",
    )
    return DockingProblemInput(
        receptor=receptor,
        ligand=ligand,
        pocket=pocket,
        search_space=search_space,
        search_space_derivation=derivation,
    )


def _plan():
    problem = _problem()
    config = StericFieldPlacementConfig(
        translation_radius_angstrom=4.0,
        grid_spacing_angstrom=2.0,
        maximum_site_count=64,
        site_cycle_depth=8,
    )
    return problem, build_steric_field_placement_plan(problem, config=config)


def test_steric_field_plan_guides_and_authenticates_translation() -> None:
    problem, plan = _plan()
    budget = DockingBudget(
        candidate_count=4,
        top_k=2,
        max_torsions=0,
        translation_radius_angstrom=4.0,
        seed=91,
    )

    proposals = generate_bounded_docking_proposals(
        problem.search_space,
        budget,
        problem=problem,
        translation_placement_plan=plan,
    )

    assert len(proposals) == 4
    assert torch.equal(proposals[0].translation, torch.zeros(3, dtype=torch.float64))
    assert proposals[0].translation_placement_receipt.overlap_pair_count == 1
    assert proposals[1].translation_placement_receipt.overlap_pair_count == 0
    assert 0.0 < torch.linalg.vector_norm(proposals[1].translation).item() <= 4.0
    assert all(
        proposal.translation_placement_receipt.placement_plan_sha256
        == plan.fingerprint_sha256
        for proposal in proposals
    )
    assert all(
        proposal.translation_placement_receipt.placement_policy_id
        == DOCKING_STERIC_FIELD_TRANSLATION_PLACEMENT_POLICY_ID
        for proposal in proposals
    )
    assert len({proposal.numeric_policy_sha256 for proposal in proposals}) == 1
    assert plan.to_dict()["retained_site_count"] > 1
    unsigned = plan.to_dict()
    receipt_sha256 = unsigned.pop("receipt_sha256")
    assert receipt_sha256 == hashlib.sha256(
        json.dumps(
            unsigned,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    ).hexdigest()


def test_steric_field_guided_prefix_is_budget_stable() -> None:
    problem, plan = _plan()

    short = generate_bounded_docking_proposals(
        problem.search_space,
        DockingBudget(
            candidate_count=3,
            top_k=2,
            max_torsions=0,
            translation_radius_angstrom=4.0,
            seed=7,
        ),
        problem=problem,
        translation_placement_plan=plan,
    )
    long = generate_bounded_docking_proposals(
        problem.search_space,
        DockingBudget(
            candidate_count=8,
            top_k=2,
            max_torsions=0,
            translation_radius_angstrom=4.0,
            seed=7,
        ),
        problem=problem,
        translation_placement_plan=plan,
    )

    assert [proposal.fingerprint_sha256 for proposal in short] == [
        proposal.fingerprint_sha256 for proposal in long[:3]
    ]
    assert all(
        proposal.translation_placement_receipt.placement_plan_sha256
        == plan.fingerprint_sha256
        for proposal in long
    )


def test_steric_field_and_uniform_sampling_have_distinct_authenticated_policy() -> None:
    problem, plan = _plan()
    budget = DockingBudget(
        candidate_count=2,
        top_k=1,
        max_torsions=0,
        translation_radius_angstrom=4.0,
        seed=19,
    )

    guided = generate_bounded_docking_proposals(
        problem.search_space,
        budget,
        problem=problem,
        translation_placement_plan=plan,
    )
    uniform = generate_bounded_docking_proposals(
        problem.search_space,
        budget,
        problem=problem,
    )

    assert guided[0].numeric_policy_sha256 != uniform[0].numeric_policy_sha256
    assert guided[0].candidate_id != uniform[0].candidate_id
    assert guided[0].translation_placement_receipt.placement_plan_sha256
    assert uniform[0].translation_placement_receipt.placement_plan_sha256 == ""
    assert (
        guided[0].translation_placement_receipt.placement_policy_id
        == DOCKING_STERIC_FIELD_TRANSLATION_PLACEMENT_POLICY_ID
    )
    guided_policy = DockingNumericPolicy(
        coordinate_dtype="float64",
        sampling_policy_id=DOCKING_STERIC_FIELD_SAMPLING_POLICY_ID,
        translation_placement_policy_id=(
            DOCKING_STERIC_FIELD_TRANSLATION_PLACEMENT_POLICY_ID
        ),
        translation_placement_plan_sha256=plan.fingerprint_sha256,
    )
    assert guided_policy.fingerprint_sha256 == guided[0].numeric_policy_sha256


def test_steric_field_plan_and_receipt_tampering_fail_closed() -> None:
    problem, plan = _plan()
    proposal = generate_bounded_docking_proposals(
        problem.search_space,
        DockingBudget(
            candidate_count=1,
            top_k=1,
            max_torsions=0,
            translation_radius_angstrom=4.0,
            seed=1,
        ),
        problem=problem,
        translation_placement_plan=plan,
    )[0]
    tampered_receipt = replace(
        proposal.translation_placement_receipt,
        site_id="tampered-site",
    )

    with pytest.raises(DockingProposalError, match="complete proposal state"):
        replace(
            proposal,
            translation_placement_receipt=tampered_receipt,
        )

    plan.site_translations[0, 0] = 0.125
    with pytest.raises(StericFieldPlacementError, match="changed after construction"):
        plan.assert_integrity()


def test_steric_field_hard_bounds_and_cross_wiring_fail_closed() -> None:
    problem, plan = _plan()
    with pytest.raises(StericFieldPlacementError, match="grid exceeds"):
        build_steric_field_placement_plan(
            problem,
            config=StericFieldPlacementConfig(
                translation_radius_angstrom=4.0,
                grid_spacing_angstrom=1.0,
                max_grid_point_count=1,
            ),
        )

    other_problem = _problem()
    other_problem = replace(
        other_problem,
        pocket=PocketDefinition(
            receptor_system_sha256=canonical_system_sha256(other_problem.receptor),
            center_angstrom=(0.0, 0.0, 0.0),
            radius_angstrom=7.0,
            coordinate_frame_id="unit-test-pocket-frame",
            derivation_policy_id="explicit-unit-test-pocket/1.0.0",
        ),
    )
    with pytest.raises(DockingProposalError, match="cross-wired"):
        generate_bounded_docking_proposals(
            other_problem.search_space,
            DockingBudget(
                candidate_count=1,
                top_k=1,
                max_torsions=0,
                translation_radius_angstrom=4.0,
                seed=1,
            ),
            problem=other_problem,
            translation_placement_plan=plan,
        )
