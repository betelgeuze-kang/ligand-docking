from __future__ import annotations

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.docking import (  # noqa: E402
    INTERPRETABLE_POSE_SCORER_V0_BLOCKERS,
    DockingBudget,
    DockingProblemIdentity,
    InterpretablePoseScoreConfig,
    InterpretablePoseScorerV0,
    InterpretablePoseScoringError,
    TorsionSearchSpace,
    generate_bounded_docking_proposals,
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
    formal_charges: tuple[int, ...] | None = None,
    aromatic_atoms: frozenset[int] = frozenset(),
    include_ring_metadata: bool = True,
    entity_type: str,
    dtype=torch.float64,
) -> AllAtomSystem:
    charges = formal_charges or (0,) * len(elements)
    atoms = tuple(
        Atom(
            index=index,
            name=f"{element}{index + 1}",
            element=element,
            atomic_number=atomic_number_for_element(element),
            residue_index=0,
            formal_charge=charges[index],
            aromatic=index in aromatic_atoms,
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
            metadata={"is_in_ring": False} if include_ring_metadata else {},
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
        coordinates=torch.tensor((coordinates,), dtype=dtype),
        provenance=StructureProvenance(source_format="unit-test"),
    )


def _problem(
    receptor: AllAtomSystem,
    ligand: AllAtomSystem,
) -> DockingProblemIdentity:
    return DockingProblemIdentity(
        receptor_system_sha256=canonical_system_sha256(receptor),
        ligand_system_sha256=canonical_system_sha256(ligand),
        pocket_definition_sha256="a" * 64,
        coordinate_frame_id="pocket_centered_receptor_frame",
    )


def _proposal(
    ligand: AllAtomSystem,
    problem: DockingProblemIdentity,
):
    coordinates = ligand.coordinates[0]
    atom_count = ligand.atom_count
    space = TorsionSearchSpace(
        local_offsets=torch.zeros_like(coordinates),
        parent=torch.full((atom_count,), -1, dtype=torch.long),
        local_axes=torch.tensor(
            [[0.0, 0.0, 1.0]] * atom_count,
            dtype=torch.float64,
        ),
        rotatable_mask=torch.zeros(atom_count, dtype=torch.bool),
        root_positions=coordinates,
    )
    return generate_bounded_docking_proposals(
        space,
        DockingBudget(
            candidate_count=1,
            top_k=1,
            max_torsions=0,
            translation_radius_angstrom=0.0,
        ),
        problem=problem,
    )[0]


def _interaction_fixture():
    receptor = _system(
        "interaction-receptor",
        ("O", "C", "C"),
        (
            (0.0, 0.0, 0.0),
            (-1.2, 0.0, 0.0),
            (0.0, 6.0, 0.0),
        ),
        bonds=((0, 1, 2.0),),
        entity_type="polymer",
    )
    ligand = _system(
        "interaction-ligand",
        ("N", "H", "C"),
        (
            (3.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (3.4, 6.0, 0.0),
        ),
        bonds=((0, 1, 1.0), (0, 2, 1.0)),
        entity_type="non-polymer",
    )
    problem = _problem(receptor, ligand)
    return (
        receptor,
        ligand,
        problem,
        InterpretablePoseScorerV0(
            receptor,
            ligand,
            problem,
        ),
    )


def _term_map(breakdown):
    return {term.term_id: term for term in breakdown.terms}


def test_interpretable_scorer_emits_bound_nine_term_diagnostics() -> None:
    receptor, ligand, problem, scorer = _interaction_fixture()

    breakdown, diagnostics = scorer.score_with_diagnostics(_proposal(ligand, problem))
    terms = _term_map(breakdown)

    assert tuple(terms) == (
        "element_radius_contact_reward",
        "element_radius_overlap_penalty",
        "element_radius_deep_penetration_penalty",
        "pocket_centroid_restraint",
        "ligand_bond_length_strain",
        "ligand_angle_strain",
        "ligand_torsion_displacement",
        "directional_hydrogen_bond_reward",
        "hydrophobic_contact_reward",
    )
    assert breakdown.complete
    assert terms["ligand_bond_length_strain"].raw_value == pytest.approx(0.0)
    assert terms["ligand_angle_strain"].raw_value == pytest.approx(0.0)
    assert terms["ligand_torsion_displacement"].raw_value == pytest.approx(0.0)
    assert terms["directional_hydrogen_bond_reward"].raw_value < -0.9
    assert terms["hydrophobic_contact_reward"].raw_value < 0.0
    assert all(
        terms[term_id].parameter_source_sha256 == scorer.config_fingerprint_sha256
        for term_id in (
            "ligand_bond_length_strain",
            "ligand_angle_strain",
            "ligand_torsion_displacement",
            "directional_hydrogen_bond_reward",
            "hydrophobic_contact_reward",
        )
    )
    assert set(INTERPRETABLE_POSE_SCORER_V0_BLOCKERS) <= set(breakdown.blockers)
    assert scorer.validated_for_docking_ranking is False
    assert scorer.score_descriptor.calibrated is False
    assert scorer.chemistry_scope["partial_charge_used"] is False
    assert scorer.chemistry_scope["calibrated"] is False
    assert (
        diagnostics.coordinate_sha256
        == _proposal(
            ligand,
            problem,
        ).coordinate_fingerprint_sha256
    )
    assert diagnostics.scorer_fingerprint_sha256 == (scorer.config_fingerprint_sha256)
    assert diagnostics.feature_binding_sha256 == scorer.feature_binding_sha256
    assert diagnostics.hbond_candidate_count == 1
    assert diagnostics.hbond_active_count == 1
    assert diagnostics.hydrophobic_pair_count == 2
    assert diagnostics.hydrophobic_active_count >= 1
    assert diagnostics.strongest_hbond is not None
    assert diagnostics.strongest_hbond.direction == (
        "ligand_donor_to_receptor_acceptor"
    )
    assert diagnostics.to_dict()["claim_safe"] is False
    assert canonical_system_sha256(receptor) == problem.receptor_system_sha256


def test_directional_hbond_and_hydrophobic_terms_respond_to_geometry() -> None:
    _receptor, ligand, _problem_identity, scorer = _interaction_fixture()
    reference = ligand.coordinates[0]
    bent_hydrogen = reference.clone()
    bent_hydrogen[1] = torch.tensor([3.0, 1.0, 0.0], dtype=torch.float64)
    far_hydrophobe = reference.clone()
    far_hydrophobe[2] = torch.tensor([12.0, 12.0, 0.0], dtype=torch.float64)

    aligned_terms = _term_map(scorer.score_coordinates(reference))
    bent_terms = _term_map(scorer.score_coordinates(bent_hydrogen))
    far_terms = _term_map(scorer.score_coordinates(far_hydrophobe))

    assert aligned_terms["directional_hydrogen_bond_reward"].raw_value < (
        bent_terms["directional_hydrogen_bond_reward"].raw_value
    )
    assert bent_terms["directional_hydrogen_bond_reward"].raw_value == 0.0
    assert aligned_terms["hydrophobic_contact_reward"].raw_value < (
        far_terms["hydrophobic_contact_reward"].raw_value
    )


def test_reference_relative_bond_angle_and_torsion_terms_are_separable() -> None:
    receptor = _system(
        "strain-receptor",
        ("C",),
        ((0.0, 8.0, 0.0),),
        entity_type="polymer",
    )
    ligand = _system(
        "strain-ligand",
        ("C", "C", "C", "C"),
        (
            (2.0, 1.0, 0.0),
            (3.0, 0.0, 0.0),
            (4.0, 0.0, 0.0),
            (5.0, 1.0, 1.0),
        ),
        bonds=((0, 1, 1.0), (1, 2, 1.0), (2, 3, 1.0)),
        entity_type="non-polymer",
    )
    problem = _problem(receptor, ligand)
    scorer = InterpretablePoseScorerV0(receptor, ligand, problem)
    reference = ligand.coordinates[0]
    torsion_only = reference.clone()
    torsion_only[3] = torch.tensor([5.0, -1.0, 1.0], dtype=torch.float64)
    distorted = reference.clone()
    distorted[0] = torch.tensor([1.4, 1.4, 0.0], dtype=torch.float64)

    reference_terms = _term_map(scorer.score_coordinates(reference))
    torsion_terms = _term_map(scorer.score_coordinates(torsion_only))
    distorted_terms = _term_map(scorer.score_coordinates(distorted))

    assert scorer.rotatable_torsions == ((0, 1, 2, 3),)
    assert reference_terms["ligand_bond_length_strain"].raw_value == 0.0
    assert reference_terms["ligand_angle_strain"].raw_value == 0.0
    assert reference_terms["ligand_torsion_displacement"].raw_value == 0.0
    assert torsion_terms["ligand_bond_length_strain"].raw_value == pytest.approx(
        0.0,
        abs=1.0e-12,
    )
    assert torsion_terms["ligand_angle_strain"].raw_value == pytest.approx(
        0.0,
        abs=1.0e-12,
    )
    assert torsion_terms["ligand_torsion_displacement"].raw_value > 0.5
    assert distorted_terms["ligand_bond_length_strain"].raw_value > 0.0
    assert distorted_terms["ligand_angle_strain"].raw_value > 0.0


def test_interpretable_scorer_fails_closed_on_scope_identity_and_dtype() -> None:
    receptor, ligand, problem, scorer = _interaction_fixture()
    zinc = _system(
        "zinc-receptor",
        ("Zn",),
        ((0.0, 0.0, 0.0),),
        entity_type="non-polymer",
    )
    zinc_problem = _problem(zinc, ligand)
    with pytest.raises(InterpretablePoseScoringError, match="unsupported atomic"):
        InterpretablePoseScorerV0(zinc, ligand, zinc_problem)

    mismatched = DockingProblemIdentity(
        receptor_system_sha256=canonical_system_sha256(receptor),
        ligand_system_sha256="b" * 64,
    )
    with pytest.raises(InterpretablePoseScoringError, match="do not match"):
        InterpretablePoseScorerV0(receptor, ligand, mismatched)

    missing_ring_metadata = _system(
        "missing-ring-metadata",
        ("C", "C"),
        ((2.0, 0.0, 0.0), (3.4, 0.0, 0.0)),
        bonds=((0, 1, 1.0),),
        include_ring_metadata=False,
        entity_type="non-polymer",
    )
    with pytest.raises(InterpretablePoseScoringError, match="is_in_ring"):
        InterpretablePoseScorerV0(
            receptor,
            missing_ring_metadata,
            _problem(receptor, missing_ring_metadata),
        )

    with pytest.raises(InterpretablePoseScoringError, match="CPU float64"):
        scorer.score_coordinates(ligand.coordinates[0].to(dtype=torch.float32))

    other_problem = DockingProblemIdentity(
        receptor_system_sha256="c" * 64,
        ligand_system_sha256="d" * 64,
    )
    with pytest.raises(InterpretablePoseScoringError, match="does not match"):
        scorer.score(_proposal(ligand, other_problem))

    with pytest.raises(
        InterpretablePoseScoringError,
        match="active feature threshold",
    ):
        InterpretablePoseScoreConfig(active_feature_threshold=1.1)
    with pytest.raises(
        InterpretablePoseScoringError,
        match="admitted distance interval",
    ):
        InterpretablePoseScoreConfig(
            hbond_h_a_center_angstrom=1.0,
        )
    with pytest.raises(
        InterpretablePoseScoringError,
        match="hydrophobic pair capacity",
    ):
        InterpretablePoseScorerV0(
            receptor,
            ligand,
            problem,
            config=InterpretablePoseScoreConfig(max_hydrophobic_pairs=1),
        )

    assert problem.bound


def test_interpretable_scorer_symbols_are_reexported() -> None:
    from betelgeuze_engine_v2 import docking
    from betelgeuze_engine_v2.docking.interpretable_scoring import (
        __all__ as interpretable_exports,
    )

    assert set(interpretable_exports) <= set(docking.__all__)
