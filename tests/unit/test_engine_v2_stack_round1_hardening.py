from __future__ import annotations

from dataclasses import replace

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2 import (
    STACK_ROUND1_HARDENING_SHA256,
    STACK_ROUND1_MINIMIZATION_COMPAT_SHA256,
)
from betelgeuze_engine_v2.docking import (
    DockingBudget,
    DockingProblemIdentity,
    DockingScoreDescriptor,
    PoseValidityConfig,
    PoseValidityContext,
    ScoreDirection,
    TorsionSearchSpace,
    generate_bounded_docking_proposals,
    run_bounded_docking_search,
)
from betelgeuze_engine_v2.docking import proposals as proposal_module
from betelgeuze_engine_v2.docking import search as search_module
from betelgeuze_engine_v2.geometry import (
    MAX_COMPACT_ATOMS_PER_CELL,
    MAX_COMPACT_NEIGHBORS,
    RadiusGraphConfig,
)
from betelgeuze_engine_v2.physics.reference_minimization import (
    ReferenceMinimizationConfig,
    ReferenceMinimizationError,
)
from betelgeuze_engine_v2.stack_round1_hardening import (
    MAX_POSE_VALIDITY_CROSS_CHECKS,
    MAX_POSE_VALIDITY_PAIR_CHECKS,
    PROPOSAL_NUMERIC_POLICY_ID,
    PUBLIC_BENCHMARK_POSE_VALIDITY_POLICY_ID,
    RESEARCH_POSE_VALIDITY_POLICY_ID,
)


def _problem() -> DockingProblemIdentity:
    return DockingProblemIdentity(
        receptor_system_sha256="a" * 64,
        ligand_system_sha256="b" * 64,
        pocket_definition_sha256="c" * 64,
    )


def _space(dtype: torch.dtype = torch.float64) -> TorsionSearchSpace:
    return TorsionSearchSpace(
        local_offsets=torch.tensor(
            [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 2.0, 0.0]],
            dtype=dtype,
        ),
        parent=torch.tensor([-1, -1, -1], dtype=torch.long),
        local_axes=torch.tensor([[0.0, 0.0, 1.0]] * 3, dtype=dtype),
        rotatable_mask=torch.zeros(3, dtype=torch.bool),
    )


def _validity_context(problem: DockingProblemIdentity) -> PoseValidityContext:
    reference = generate_bounded_docking_proposals(
        _space(),
        DockingBudget(candidate_count=1, top_k=1, max_torsions=0, seed=5),
        problem=problem,
    )[0].coordinates
    return PoseValidityContext(
        problem_fingerprint_sha256=problem.fingerprint_sha256,
        reference_coordinates=reference,
        bond_pairs=(),
        excluded_nonbonded_pairs=(),
        receptor_coordinates=torch.tensor(
            [[100.0, 100.0, 100.0]], dtype=torch.float64
        ),
        pocket_center=reference.mean(dim=0),
        chirality_centers=(),
        config=PoseValidityConfig(
            policy_id=RESEARCH_POSE_VALIDITY_POLICY_ID,
            pocket_radius_angstrom=100.0,
            ligand_self_clash_angstrom=0.0,
            receptor_ligand_clash_angstrom=0.0,
        ),
    )


class _Scorer:
    scorer_id = "round1-test-scorer"
    scorer_version = "1.0.0"
    validated_for_docking_ranking = False
    problem_fingerprint_sha256 = _problem().fingerprint_sha256
    implementation_source_sha256 = "d" * 64
    config_fingerprint_sha256 = "e" * 64
    score_descriptor = DockingScoreDescriptor(
        score_id="round1-test-score",
        direction=ScoreDirection.MINIMIZE,
        unit=None,
        semantics="unit_test_only",
        calibrated=False,
    )

    def score(self, proposal):
        return proposal.coordinates.square().sum()


def test_round1_hardening_receipt_is_installed() -> None:
    assert len(STACK_ROUND1_HARDENING_SHA256) == 64
    assert len(STACK_ROUND1_MINIMIZATION_COMPAT_SHA256) == 64
    assert proposal_module.PROPOSAL_NUMERIC_POLICY_ID == PROPOSAL_NUMERIC_POLICY_ID


def test_default_minimization_capacity_matches_neighbor_hard_caps() -> None:
    config = ReferenceMinimizationConfig()
    assert config.max_neighbors == MAX_COMPACT_NEIGHBORS
    assert config.max_atoms_per_cell == MAX_COMPACT_ATOMS_PER_CELL
    graph_config = RadiusGraphConfig(
        cutoff_angstrom=8.0,
        max_neighbors=config.max_neighbors,
        max_atoms_per_cell=config.max_atoms_per_cell,
    )
    assert graph_config.max_neighbors == MAX_COMPACT_NEIGHBORS
    assert graph_config.max_atoms_per_cell == MAX_COMPACT_ATOMS_PER_CELL

    with pytest.raises(ReferenceMinimizationError, match="max_neighbors"):
        ReferenceMinimizationConfig(
            max_neighbors=MAX_COMPACT_NEIGHBORS + 1
        )
    with pytest.raises(ReferenceMinimizationError, match="max_atoms_per_cell"):
        ReferenceMinimizationConfig(
            max_atoms_per_cell=MAX_COMPACT_ATOMS_PER_CELL + 1
        )


def test_candidate_id_is_derived_from_stable_identity_and_survives_refinement() -> None:
    proposal = generate_bounded_docking_proposals(
        _space(),
        DockingBudget(candidate_count=1, top_k=1, max_torsions=0, seed=11),
        problem=_problem(),
    )[0]
    expected = proposal.candidate_id
    assert expected.startswith("pose-00000-")
    assert expected != f"pose-00000-{proposal.fingerprint_sha256[:12]}"

    refined = proposal.with_refined_coordinates(
        proposal.coordinates,
        refiner_id="round1-refiner",
        refiner_version="1.0.0",
    )
    assert refined.candidate_id == expected
    assert refined.fingerprint_sha256 != proposal.fingerprint_sha256

    with pytest.raises(
        proposal_module.DockingProposalError,
        match="candidate_id is not derived",
    ):
        replace(proposal, candidate_id="arbitrary-user-label")


def test_proposal_fingerprint_records_dtype_and_binary64_hex_policy() -> None:
    fp64 = generate_bounded_docking_proposals(
        _space(torch.float64),
        DockingBudget(candidate_count=1, top_k=1, max_torsions=0, seed=13),
        problem=_problem(),
    )[0].fingerprint_sha256
    fp32 = generate_bounded_docking_proposals(
        _space(torch.float32),
        DockingBudget(candidate_count=1, top_k=1, max_torsions=0, seed=13),
        problem=_problem(),
    )[0].fingerprint_sha256
    assert fp64 != fp32


def test_symmetry_aware_direct_diversity_preserves_receptor_frame() -> None:
    first = generate_bounded_docking_proposals(
        _space(),
        DockingBudget(candidate_count=1, top_k=1, max_torsions=0, seed=17),
        problem=_problem(),
    )[0]
    translated_and_swapped = first.with_refined_coordinates(
        first.coordinates[[0, 2, 1]] + torch.tensor(
            [4.0, 0.0, 0.0], dtype=torch.float64
        ),
        refiner_id="round1-symmetry-refiner",
        refiner_version="1.0.0",
    )
    direct = search_module._pose_distance(
        first,
        translated_and_swapped,
        metric="symmetry_aware_direct_rmsd",
        symmetry_permutations=((0, 1, 2), (0, 2, 1)),
    )
    aligned = search_module._pose_distance(
        first,
        translated_and_swapped,
        metric="symmetry_aware_kabsch_rmsd",
        symmetry_permutations=((0, 1, 2), (0, 2, 1)),
    )
    assert direct == pytest.approx(4.0, abs=1.0e-12)
    assert aligned == pytest.approx(0.0, abs=1.0e-12)

    problem = _problem()
    result = run_bounded_docking_search(
        _space(),
        DockingBudget(candidate_count=2, top_k=1, max_torsions=0, seed=19),
        _Scorer(),
        problem=problem,
        validity_context=_validity_context(problem),
        diversity_metric="symmetry_aware_direct_rmsd",
        symmetry_permutations=((0, 1, 2), (0, 2, 1)),
        diversity_rmsd_angstrom=0.0,
    )
    assert result.diversity_metric == "symmetry_aware_direct_rmsd"
    assert len(result.search_fingerprint_sha256) == 64


def test_pose_validity_policies_are_bounded_and_public_policy_is_immutable() -> None:
    research = PoseValidityConfig(
        policy_id=RESEARCH_POSE_VALIDITY_POLICY_ID,
        ligand_self_clash_angstrom=0.0,
        receptor_ligand_clash_angstrom=0.0,
    )
    assert research.policy_id == RESEARCH_POSE_VALIDITY_POLICY_ID

    public = PoseValidityConfig(
        policy_id=PUBLIC_BENCHMARK_POSE_VALIDITY_POLICY_ID,
        pocket_radius_angstrom=10.0,
    )
    assert public.policy_id == PUBLIC_BENCHMARK_POSE_VALIDITY_POLICY_ID

    with pytest.raises(Exception, match="immutable"):
        PoseValidityConfig(
            policy_id=PUBLIC_BENCHMARK_POSE_VALIDITY_POLICY_ID,
            ligand_self_clash_angstrom=0.0,
            pocket_radius_angstrom=10.0,
        )
    with pytest.raises(Exception, match="max_pair_checks"):
        PoseValidityConfig(max_pair_checks=MAX_POSE_VALIDITY_PAIR_CHECKS + 1)
    with pytest.raises(Exception, match="max_cross_checks"):
        PoseValidityConfig(max_cross_checks=MAX_POSE_VALIDITY_CROSS_CHECKS + 1)
