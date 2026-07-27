from __future__ import annotations

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2 import (  # noqa: E402
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
)
from betelgeuze_engine_v2.docking import (  # noqa: E402
    HAAR_ROTATION_SAMPLER_ID,
    POCKET_PROPOSAL_OVERRIDE_SHA256,
    DockingAuthorityError,
    DockingBudget,
    DockingScoreDescriptor,
    DockingScope,
    PocketDefinition,
    PocketPlacementPolicy,
    ScoreDirection,
    build_authenticated_known_pocket_docking_problem,
    generate_bounded_docking_proposals,
    generate_pocket_centered_docking_proposals,
    run_authenticated_pocket_placement_search,
)


def _provenance(name: str, digest: str) -> StructureProvenance:
    return StructureProvenance(
        source_format="unit",
        source_id=name,
        source_sha256=digest,
        parser_name="placement-fixture",
        parser_version="1.0.0",
    )


def _ligand() -> AllAtomSystem:
    elements = ("C", "N", "C", "O")
    return AllAtomSystem(
        system_id="placement-ligand",
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
            [[[0.0, 0.0, 0.0], [1.4, 0.0, 0.0], [2.8, 0.3, 0.0], [4.1, 1.0, 0.2]]],
            dtype=torch.float64,
        ),
        provenance=_provenance("placement-ligand-source", "a" * 64),
    )


def _receptor() -> AllAtomSystem:
    return AllAtomSystem(
        system_id="placement-receptor",
        atoms=tuple(
            Atom(
                index=index,
                name=f"R{index}",
                element="C",
                atomic_number=6,
                residue_index=0,
            )
            for index in range(4)
        ),
        bonds=(),
        residues=(
            Residue(
                index=0,
                name="REC",
                chain_index=0,
                sequence_number=1,
                atom_indices=(0, 1, 2, 3),
            ),
        ),
        chains=(Chain(index=0, chain_id="A", residue_indices=(0,)),),
        coordinates=torch.tensor(
            [[[1.0, 4.0, 0.0], [4.0, 4.0, 0.0], [7.0, 0.0, 0.0], [60.0, 60.0, 60.0]]],
            dtype=torch.float64,
        ),
        provenance=_provenance("placement-receptor-source", "b" * 64),
    )


def _authority():
    pocket = PocketDefinition(
        scope=DockingScope.KNOWN_POCKET,
        method_id="manual-reviewed-sphere",
        method_version="1.0.0",
        coordinate_frame_id="prepared-receptor-frame-v1",
        center=torch.tensor([5.0, 2.0, -1.0], dtype=torch.float64),
        radius_angstrom=8.0,
        source_artifact_sha256="c" * 64,
        implementation_source_sha256="d" * 64,
    )
    return build_authenticated_known_pocket_docking_problem(
        _receptor(),
        _ligand(),
        pocket,
        receptor_margin_angstrom=8.0,
    )


class _Scorer:
    scorer_id = "placement-test-scorer"
    scorer_version = "1.0.0"
    validated_for_docking_ranking = False
    implementation_source_sha256 = "e" * 64
    config_fingerprint_sha256 = "f" * 64
    score_descriptor = DockingScoreDescriptor(
        score_id="placement-test-score",
        direction=ScoreDirection.MINIMIZE,
        unit=None,
        semantics="unit_test_only",
        calibrated=False,
    )

    def __init__(self, problem_fingerprint: str) -> None:
        self.problem_fingerprint_sha256 = problem_fingerprint

    def score(self, proposal):
        return proposal.coordinates.square().sum()


def _budget(seed: int = 71) -> DockingBudget:
    return DockingBudget(
        candidate_count=8,
        top_k=3,
        max_torsions=1,
        translation_radius_angstrom=2.0,
        seed=seed,
    )


def test_haar_placement_is_deterministic_proper_and_pocket_centered() -> None:
    assert len(POCKET_PROPOSAL_OVERRIDE_SHA256) == 64
    authority = _authority()
    policy = PocketPlacementPolicy()
    assert policy.rotation_sampler_id == HAAR_ROTATION_SAMPLER_ID
    first, receipt = generate_pocket_centered_docking_proposals(
        authority,
        _budget(),
        policy=policy,
    )
    second, second_receipt = generate_pocket_centered_docking_proposals(
        authority,
        _budget(),
        policy=policy,
    )
    assert tuple(row.fingerprint_sha256 for row in first) == tuple(
        row.fingerprint_sha256 for row in second
    )
    assert receipt.receipt_sha256 == second_receipt.receipt_sha256
    assert torch.allclose(
        first[0].coordinates.mean(dim=0),
        authority.pocket.center,
        atol=1.0e-12,
        rtol=0.0,
    )
    for proposal, offset in zip(first, receipt.centroid_offset_angstroms):
        identity = torch.eye(3, dtype=proposal.rotation.dtype)
        assert torch.allclose(
            proposal.rotation.T @ proposal.rotation,
            identity,
            atol=1.0e-10,
            rtol=0.0,
        )
        assert float(torch.linalg.det(proposal.rotation).item()) == pytest.approx(
            1.0,
            abs=1.0e-10,
        )
        observed = float(
            torch.linalg.vector_norm(
                proposal.coordinates.mean(dim=0) - authority.pocket.center
            ).item()
        )
        assert observed == pytest.approx(offset, abs=1.0e-10)
        assert observed <= _budget().translation_radius_angstrom + 1.0e-10


def test_seed_changes_placement_identity_and_radius_is_authority_bounded() -> None:
    authority = _authority()
    first, _ = generate_pocket_centered_docking_proposals(authority, _budget(73))
    second, _ = generate_pocket_centered_docking_proposals(authority, _budget(79))
    assert tuple(row.fingerprint_sha256 for row in first) != tuple(
        row.fingerprint_sha256 for row in second
    )
    with pytest.raises(DockingAuthorityError, match="translation radius"):
        generate_pocket_centered_docking_proposals(
            authority,
            DockingBudget(
                candidate_count=2,
                top_k=1,
                max_torsions=1,
                translation_radius_angstrom=9.0,
                seed=83,
            ),
        )


def test_placement_reuses_failure_complete_search_and_context_resets() -> None:
    authority = _authority()
    result = run_authenticated_pocket_placement_search(
        authority,
        _budget(89),
        _Scorer(authority.problem.fingerprint_sha256),
        diversity_rmsd_angstrom=0.0,
        diversity_metric="symmetry_aware_direct_rmsd",
        symmetry_permutations=((0, 1, 2, 3),),
    )
    assert result.placement_receipt.authenticated_input_receipt_sha256 == (
        authority.input_receipt_sha256
    )
    assert result.authenticated_search_result.search_result.diversity_metric == (
        "symmetry_aware_direct_rmsd"
    )
    assert len(result.receipt_sha256) == 64
    assert result.to_dict()["claim_safe"] is False

    generic = generate_bounded_docking_proposals(
        authority.search_space,
        _budget(89),
        problem=authority.problem,
    )
    assert not torch.allclose(
        generic[0].coordinates.mean(dim=0),
        authority.pocket.center,
        atol=1.0e-12,
        rtol=0.0,
    )
