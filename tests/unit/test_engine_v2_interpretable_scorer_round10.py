from __future__ import annotations

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2 import (
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
)
from betelgeuze_engine_v2.docking import (
    DockingBudget,
    DockingScope,
    InterpretablePoseScoreConfig,
    InterpretablePoseScorerError,
    InterpretablePoseScorerV0,
    PocketDefinition,
    build_element_aware_authenticated_known_pocket_docking_problem,
    generate_pocket_centered_docking_proposals,
    run_authenticated_pocket_placement_search,
)


def _provenance(name: str, digest: str) -> StructureProvenance:
    return StructureProvenance(
        source_format="unit",
        source_id=name,
        source_sha256=digest,
        parser_name="interpretable-scorer-fixture",
        parser_version="1.0.0",
    )


def _ligand() -> AllAtomSystem:
    elements = ("C", "N", "C", "O")
    return AllAtomSystem(
        system_id="interpretable-ligand",
        atoms=tuple(
            Atom(
                index=index,
                name=f"L{index}",
                element=element,
                atomic_number={"C": 6, "N": 7, "O": 8}[element],
                residue_index=0,
            )
            for index, element in enumerate(elements)
        ),
        bonds=(
            Bond(index=0, atom_i=0, atom_j=1, order=1.0),
            Bond(index=1, atom_i=1, atom_j=2, order=1.0),
            Bond(index=2, atom_i=2, atom_j=3, order=1.0),
        ),
        residues=(
            Residue(
                index=0,
                name="LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=(0, 1, 2, 3),
            ),
        ),
        chains=(Chain(index=0, chain_id="L", residue_indices=(0,)),),
        coordinates=torch.tensor(
            [
                [
                    [0.0, 0.0, 0.0],
                    [1.4, 0.0, 0.0],
                    [2.8, 0.3, 0.0],
                    [4.1, 1.0, 0.2],
                ]
            ],
            dtype=torch.float64,
        ),
        provenance=_provenance("interpretable-ligand-source", "a" * 64),
    )


def _receptor() -> AllAtomSystem:
    coordinates = (
        [0.0, 0.0, 0.0],
        [5.0, 0.0, 0.0],
        [8.0, 7.0, 4.0],
        [-8.0, -7.0, -4.0],
    )
    return AllAtomSystem(
        system_id="interpretable-receptor",
        atoms=tuple(
            Atom(
                index=index,
                name=f"R{index}",
                element="C",
                atomic_number=6,
                residue_index=0,
            )
            for index in range(len(coordinates))
        ),
        bonds=(),
        residues=(
            Residue(
                index=0,
                name="REC",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(len(coordinates))),
            ),
        ),
        chains=(Chain(index=0, chain_id="A", residue_indices=(0,)),),
        coordinates=torch.tensor([coordinates], dtype=torch.float64),
        provenance=_provenance("interpretable-receptor-source", "b" * 64),
    )


def _authority(
    center: tuple[float, float, float] = (2.5, 2.0, 0.0),
):
    pocket = PocketDefinition(
        scope=DockingScope.KNOWN_POCKET,
        method_id="interpretable-test-sphere",
        method_version="1.0.0",
        coordinate_frame_id="prepared-receptor-frame-v1",
        center=torch.tensor(center, dtype=torch.float64),
        radius_angstrom=12.0,
        source_artifact_sha256="c" * 64,
        implementation_source_sha256="d" * 64,
    )
    return build_element_aware_authenticated_known_pocket_docking_problem(
        _receptor(),
        _ligand(),
        pocket,
        receptor_margin_angstrom=4.0,
    )


def _budget(seed: int = 101) -> DockingBudget:
    return DockingBudget(
        candidate_count=6,
        top_k=3,
        max_torsions=1,
        translation_radius_angstrom=2.0,
        seed=seed,
    )


def _scorer(authority, config=None):
    return InterpretablePoseScorerV0(
        authority,
        implementation_source_sha256="e" * 64,
        config=config,
    )


def test_terms_are_deterministic_finite_and_sum_to_total() -> None:
    authority = _authority()
    proposal = generate_pocket_centered_docking_proposals(
        authority,
        _budget(),
    )[0][0]
    scorer = _scorer(authority)
    first = scorer.score_terms(proposal)
    second = scorer.score_terms(proposal)
    assert first.receipt_sha256 == second.receipt_sha256
    expected = (
        first.ligand_overlap_penalty
        + first.receptor_overlap_penalty
        - first.contact_reward
        + first.pocket_center_penalty
        + first.torsion_penalty
    )
    assert first.total_score == pytest.approx(expected, abs=1.0e-12)
    assert scorer.score(proposal) == pytest.approx(first.total_score, abs=1.0e-12)
    assert scorer.score_descriptor.calibrated is False
    assert scorer.score_descriptor.unit is None
    assert scorer.validated_for_docking_ranking is False
    assert len(scorer.contract_fingerprint_sha256) == 64
    status = scorer.qualification_document()
    assert status["affinity_estimate"] is False
    assert status["free_energy_estimate"] is False
    assert status["claim_safe"] is False


def test_receptor_overlap_has_a_positive_interpretable_penalty() -> None:
    authority = _authority()
    proposal = generate_pocket_centered_docking_proposals(
        authority,
        _budget(103),
    )[0][0]
    scorer = _scorer(authority)
    receptor_atom = authority.validity_context.receptor_coordinates[0]
    overlapping = proposal.with_refined_coordinates(
        proposal.coordinates - proposal.coordinates[0] + receptor_atom,
        refiner_id="interpretable-overlap-fixture",
        refiner_version="1.0.0",
    )
    clear = proposal.with_refined_coordinates(
        proposal.coordinates + torch.tensor(
            [0.0, 8.0, 0.0],
            dtype=torch.float64,
        ),
        refiner_id="interpretable-clear-fixture",
        refiner_version="1.0.0",
    )
    overlapping_terms = scorer.score_terms(overlapping)
    clear_terms = scorer.score_terms(clear)
    assert overlapping_terms.receptor_overlap_penalty > 0.0
    assert overlapping_terms.receptor_overlap_penalty > (
        clear_terms.receptor_overlap_penalty
    )
    assert overlapping_terms.minimum_receptor_vdw_ratio < 1.0


def test_config_changes_component_identity_and_term_weights() -> None:
    authority = _authority()
    proposals = generate_pocket_centered_docking_proposals(
        authority,
        _budget(107),
    )[0]
    proposal = proposals[1]
    assert float(
        torch.linalg.vector_norm(
            proposal.coordinates.mean(dim=0) - authority.pocket.center
        ).item()
    ) > 0.0
    first = _scorer(
        authority,
        InterpretablePoseScoreConfig(pocket_center_weight=0.25),
    )
    second = _scorer(
        authority,
        InterpretablePoseScoreConfig(pocket_center_weight=2.0),
    )
    assert first.config_fingerprint_sha256 != second.config_fingerprint_sha256
    assert first.contract_fingerprint_sha256 != second.contract_fingerprint_sha256
    assert first.score_terms(proposal).pocket_center_penalty != (
        second.score_terms(proposal).pocket_center_penalty
    )


def test_crosswired_proposal_is_rejected() -> None:
    authority = _authority()
    other_authority = _authority(center=(3.5, 2.0, 0.0))
    crosswired = generate_pocket_centered_docking_proposals(
        other_authority,
        _budget(109),
    )[0][0]
    assert crosswired.problem_fingerprint_sha256 != (
        authority.problem.fingerprint_sha256
    )
    scorer = _scorer(authority)
    with pytest.raises(
        InterpretablePoseScorerError,
        match="cross-wired",
    ):
        scorer.score(crosswired)


def test_failure_complete_search_uses_explicit_uncalibrated_descriptor() -> None:
    authority = _authority()
    scorer = _scorer(authority)
    result = run_authenticated_pocket_placement_search(
        authority,
        _budget(113),
        scorer,
        diversity_rmsd_angstrom=0.0,
        diversity_metric="symmetry_aware_direct_rmsd",
        symmetry_permutations=((0, 1, 2, 3),),
    )
    search = result.authenticated_search_result.search_result
    assert search.scorer_id == scorer.scorer_id
    assert search.score_descriptor.score_id == scorer.score_descriptor.score_id
    assert search.score_descriptor.calibrated is False
    assert "docking_score_uncalibrated" in search.blockers
    assert "scorer_not_validated_for_docking_ranking" in search.blockers
    assert len(search.rows) == _budget(113).candidate_count
