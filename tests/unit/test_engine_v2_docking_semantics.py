from __future__ import annotations

import math

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.docking import (  # noqa: E402
    DockingBudget,
    DockingProblemIdentity,
    DockingScoreDescriptor,
    PoseMetricError,
    PoseValidityConfig,
    ScoreDirection,
    TorsionSearchSpace,
    evaluate_pose_validity,
    generate_bounded_docking_proposals,
    kabsch_aligned_rmsd,
    run_bounded_docking_search,
    symmetry_aware_rmsd,
)


def _space() -> TorsionSearchSpace:
    return TorsionSearchSpace(
        local_offsets=torch.tensor(
            [[0.0, 0.0, 0.0], [1.2, 0.0, 0.0], [1.0, 0.5, 0.0], [0.8, 0.5, 0.4]],
            dtype=torch.float64,
        ),
        parent=torch.tensor([-1, 0, 1, 2], dtype=torch.long),
        local_axes=torch.tensor([[0.0, 0.0, 1.0]] * 4, dtype=torch.float64),
        rotatable_mask=torch.tensor([False, False, True, True]),
    )


def _problem() -> DockingProblemIdentity:
    return DockingProblemIdentity(
        receptor_system_sha256="a" * 64,
        ligand_system_sha256="b" * 64,
        pocket_definition_sha256="c" * 64,
    )


class _MaximizeScorer:
    scorer_id = "maximize-coordinate-sum"
    scorer_version = "1.0.0"
    validated_for_docking_ranking = False
    config_fingerprint_sha256 = "d" * 64
    score_descriptor = DockingScoreDescriptor(
        score_id="coordinate_sum_proxy",
        direction=ScoreDirection.MAXIMIZE,
        unit=None,
        semantics="unit_test_internal_coordinate_sum",
        calibrated=False,
    )

    def score(self, proposal):
        return proposal.coordinates.sum()


class _SecretFailingScorer(_MaximizeScorer):
    scorer_id = "secret-failing"

    def score(self, proposal):
        del proposal
        raise RuntimeError("/home/customer/private/ligand.sdf API_TOKEN=secret-value")


class _CountingScorer(_MaximizeScorer):
    scorer_id = "counting-coordinate-sum"

    def __init__(self) -> None:
        self.call_count = 0

    def score(self, proposal):
        self.call_count += 1
        return super().score(proposal)


class _CountingRefiner:
    refiner_id = "counting-refiner"
    refiner_version = "1.0.0"

    def __init__(self) -> None:
        self.call_count = 0

    def refine(self, proposal, *, max_steps):
        del max_steps
        self.call_count += 1
        return proposal.with_refined_coordinates(
            proposal.coordinates,
            refiner_id=self.refiner_id,
            refiner_version=self.refiner_version,
        )


def test_score_direction_controls_ranking_and_component_fingerprints_are_emitted() -> None:
    budget = DockingBudget(candidate_count=6, top_k=2, max_torsions=2, seed=29)
    result = run_bounded_docking_search(
        _space(),
        budget,
        _MaximizeScorer(),
        problem=_problem(),
        diversity_rmsd_angstrom=0.0,
    )
    successful = [row for row in result.rows if row.succeeded]
    expected = sorted(successful, key=lambda row: (-float(row.score), row.proposal_index))[:2]
    assert [row.candidate_id for row in result.top_rows] == [row.candidate_id for row in expected]
    assert result.score_descriptor.direction is ScoreDirection.MAXIMIZE
    assert len(result.scorer_contract_fingerprint_sha256) == 64
    assert result.refiner_contract_fingerprint_sha256 == ""
    assert "docking_score_uncalibrated" in result.blockers


def test_failure_rows_redact_private_exception_text() -> None:
    result = run_bounded_docking_search(
        _space(),
        DockingBudget(candidate_count=2, top_k=1, max_torsions=2),
        _SecretFailingScorer(),
        problem=_problem(),
    )
    assert result.failure_count == 2
    for row in result.rows:
        assert row.error_code == "RuntimeError"
        assert row.error_message == "docking candidate execution failed"
        assert "private" not in row.error_message
        assert "secret-value" not in row.error_message
        assert len(row.private_error_sha256) == 64
        assert row.private_error_byte_length > 0


def test_kabsch_and_symmetry_aware_rmsd_are_explicit_and_bounded() -> None:
    reference = torch.tensor(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 2.0, 0.0]],
        dtype=torch.float64,
    )
    rotation = torch.tensor(
        [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
        dtype=torch.float64,
    )
    transformed = reference @ rotation.T + torch.tensor([4.0, -2.0, 1.0], dtype=torch.float64)
    assert kabsch_aligned_rmsd(reference, transformed) == pytest.approx(0.0, abs=1.0e-10)

    swapped = transformed[[0, 2, 1]]
    result = symmetry_aware_rmsd(
        reference,
        swapped,
        permutations=((0, 1, 2), (0, 2, 1)),
        align=True,
    )
    assert result.rmsd_angstrom == pytest.approx(0.0, abs=1.0e-10)
    assert result.symmetry_permutation_index == 1


def test_pose_validity_checks_rotation_bonds_clashes_pocket_and_chirality() -> None:
    proposal = generate_bounded_docking_proposals(
        _space(),
        DockingBudget(candidate_count=1, top_k=1, max_torsions=2),
        problem=_problem(),
    )[0]
    reference = proposal.coordinates.clone()
    valid = evaluate_pose_validity(
        proposal,
        reference,
        bond_pairs=((0, 1), (1, 2), (2, 3)),
        receptor_coordinates=torch.tensor([[20.0, 20.0, 20.0]], dtype=torch.float64),
        pocket_center=reference.mean(dim=0),
        chirality_centers=((1, 0, 2, 3),),
        config=PoseValidityConfig(pocket_radius_angstrom=10.0),
    )
    assert valid.valid
    assert valid.complete
    assert valid.valid_within_evaluated_scope
    assert all(valid.evaluated_checks.values())
    assert valid.checks["proper_rotation"]
    assert valid.checks["bond_lengths_preserved"]

    mirrored_coordinates = reference.clone()
    mirrored_coordinates[:, 2] *= -1.0
    mirrored = proposal.with_refined_coordinates(
        mirrored_coordinates,
        refiner_id="mirror-test",
        refiner_version="1.0.0",
    )
    invalid = evaluate_pose_validity(
        mirrored,
        reference,
        bond_pairs=((0, 1), (1, 2), (2, 3)),
        chirality_centers=((1, 0, 2, 3),),
    )
    assert not invalid.valid
    assert "declared_chirality_not_preserved" in invalid.blockers


def test_missing_receptor_is_not_evaluated_and_prevents_complete_validity() -> None:
    proposal = generate_bounded_docking_proposals(
        _space(),
        DockingBudget(candidate_count=1, top_k=1, max_torsions=2),
        problem=_problem(),
    )[0]
    reference = proposal.coordinates.clone()
    result = evaluate_pose_validity(
        proposal,
        reference,
        bond_pairs=((0, 1), (1, 2), (2, 3)),
        pocket_center=reference.mean(dim=0),
        chirality_centers=((1, 0, 2, 3),),
        config=PoseValidityConfig(pocket_radius_angstrom=10.0),
    )

    assert result.checks["receptor_ligand_clash_free"] is False
    assert result.evaluated_checks["receptor_ligand_clash_free"] is False
    assert result.not_evaluated_reasons["receptor_ligand_clash_free"] == (
        "receptor_coordinates_not_supplied"
    )
    assert "minimum_receptor_ligand_distance_angstrom" not in result.measurements
    assert result.valid_within_evaluated_scope
    assert not result.complete
    assert not result.valid
    assert result.to_dict()["complete"] is False


def test_missing_pocket_is_not_evaluated_and_prevents_complete_validity() -> None:
    proposal = generate_bounded_docking_proposals(
        _space(),
        DockingBudget(candidate_count=1, top_k=1, max_torsions=2),
        problem=_problem(),
    )[0]
    reference = proposal.coordinates.clone()
    result = evaluate_pose_validity(
        proposal,
        reference,
        bond_pairs=((0, 1), (1, 2), (2, 3)),
        receptor_coordinates=torch.tensor([[20.0, 20.0, 20.0]], dtype=torch.float64),
        chirality_centers=((1, 0, 2, 3),),
    )

    assert result.checks["inside_declared_pocket"] is False
    assert result.evaluated_checks["inside_declared_pocket"] is False
    assert result.not_evaluated_reasons["inside_declared_pocket"] == (
        "pocket_center_not_supplied"
    )
    assert "maximum_pocket_center_distance_angstrom" not in result.measurements
    assert result.valid_within_evaluated_scope
    assert not result.complete
    assert not result.valid


def test_supplied_receptor_and_pocket_failures_are_explicit_and_complete() -> None:
    proposal = generate_bounded_docking_proposals(
        _space(),
        DockingBudget(candidate_count=1, top_k=1, max_torsions=2),
        problem=_problem(),
    )[0]
    reference = proposal.coordinates.clone()
    result = evaluate_pose_validity(
        proposal,
        reference,
        bond_pairs=((0, 1), (1, 2), (2, 3)),
        receptor_coordinates=reference[:1],
        pocket_center=torch.tensor([50.0, 50.0, 50.0], dtype=torch.float64),
        chirality_centers=((1, 0, 2, 3),),
        config=PoseValidityConfig(pocket_radius_angstrom=0.5),
    )

    assert result.evaluated_checks["receptor_ligand_clash_free"] is True
    assert result.evaluated_checks["inside_declared_pocket"] is True
    assert result.checks["receptor_ligand_clash_free"] is False
    assert result.checks["inside_declared_pocket"] is False
    assert result.complete
    assert not result.valid_within_evaluated_scope
    assert not result.valid
    assert result.not_evaluated_reasons == {}


def test_missing_topology_is_not_evaluated_but_explicit_empty_declarations_are() -> None:
    proposal = generate_bounded_docking_proposals(
        _space(),
        DockingBudget(candidate_count=1, top_k=1, max_torsions=2),
        problem=_problem(),
    )[0]
    reference = proposal.coordinates.clone()
    common = {
        "receptor_coordinates": torch.tensor([[20.0, 20.0, 20.0]], dtype=torch.float64),
        "pocket_center": reference.mean(dim=0),
        "config": PoseValidityConfig(pocket_radius_angstrom=10.0),
    }

    missing = evaluate_pose_validity(proposal, reference, **common)
    declared_empty = evaluate_pose_validity(
        proposal,
        reference,
        bond_pairs=(),
        chirality_centers=(),
        **common,
    )

    assert missing.evaluated_checks["bond_lengths_preserved"] is False
    assert missing.evaluated_checks["ligand_self_clash_free"] is False
    assert missing.evaluated_checks["declared_chirality_preserved"] is False
    assert not missing.complete
    assert declared_empty.evaluated_checks["bond_lengths_preserved"] is True
    assert declared_empty.evaluated_checks["ligand_self_clash_free"] is True
    assert declared_empty.evaluated_checks["declared_chirality_preserved"] is True
    assert declared_empty.complete


def test_symmetry_aware_search_records_metric_contract() -> None:
    budget = DockingBudget(candidate_count=4, top_k=2, max_torsions=2, seed=13)
    result = run_bounded_docking_search(
        _space(),
        budget,
        _MaximizeScorer(),
        problem=_problem(),
        diversity_rmsd_angstrom=0.0,
        diversity_metric="symmetry_aware_kabsch_rmsd",
        symmetry_permutations=((0, 1, 2, 3), (0, 1, 3, 2)),
    )
    assert result.diversity_metric == "symmetry_aware_kabsch_rmsd"
    assert math.isfinite(float(result.top_rows[0].score))
    assert len(result.search_fingerprint_sha256) == 64


def test_search_fingerprint_distinguishes_same_count_symmetry_mappings() -> None:
    budget = DockingBudget(candidate_count=4, top_k=2, max_torsions=2, seed=13)
    first = run_bounded_docking_search(
        _space(),
        budget,
        _MaximizeScorer(),
        problem=_problem(),
        diversity_metric="symmetry_aware_kabsch_rmsd",
        symmetry_permutations=((0, 1, 2, 3), (0, 1, 3, 2)),
    )
    second = run_bounded_docking_search(
        _space(),
        budget,
        _MaximizeScorer(),
        problem=_problem(),
        diversity_metric="symmetry_aware_kabsch_rmsd",
        symmetry_permutations=((0, 1, 2, 3), (1, 0, 2, 3)),
    )

    assert first.search_fingerprint_sha256 != second.search_fingerprint_sha256


def test_search_fingerprint_canonicalizes_list_and_tensor_symmetry_mappings() -> None:
    budget = DockingBudget(candidate_count=4, top_k=2, max_torsions=2, seed=13)
    from_lists = run_bounded_docking_search(
        _space(),
        budget,
        _MaximizeScorer(),
        problem=_problem(),
        diversity_metric="symmetry_aware_kabsch_rmsd",
        symmetry_permutations=[[0, 1, 2, 3], [0, 1, 3, 2]],
    )
    from_tensors = run_bounded_docking_search(
        _space(),
        budget,
        _MaximizeScorer(),
        problem=_problem(),
        diversity_metric="symmetry_aware_kabsch_rmsd",
        symmetry_permutations=(
            torch.tensor([0, 1, 2, 3], dtype=torch.long),
            torch.tensor([0, 1, 3, 2], dtype=torch.long),
        ),
    )

    assert from_lists.search_fingerprint_sha256 == from_tensors.search_fingerprint_sha256


def test_search_fingerprint_preserves_symmetry_mapping_order() -> None:
    budget = DockingBudget(candidate_count=4, top_k=2, max_torsions=2, seed=13)
    first = run_bounded_docking_search(
        _space(),
        budget,
        _MaximizeScorer(),
        problem=_problem(),
        diversity_metric="symmetry_aware_kabsch_rmsd",
        symmetry_permutations=((0, 1, 2, 3), (0, 1, 3, 2)),
    )
    reordered = run_bounded_docking_search(
        _space(),
        budget,
        _MaximizeScorer(),
        problem=_problem(),
        diversity_metric="symmetry_aware_kabsch_rmsd",
        symmetry_permutations=((0, 1, 3, 2), (0, 1, 2, 3)),
    )

    assert first.search_fingerprint_sha256 != reordered.search_fingerprint_sha256


def test_invalid_symmetry_mapping_fails_before_proposal_scoring() -> None:
    scorer = _CountingScorer()
    refiner = _CountingRefiner()

    with pytest.raises(PoseMetricError, match="bijection"):
        run_bounded_docking_search(
            _space(),
            DockingBudget(
                candidate_count=4,
                top_k=2,
                max_torsions=2,
                max_refinement_steps=1,
            ),
            scorer,
            refiner=refiner,
            problem=_problem(),
            diversity_metric="symmetry_aware_kabsch_rmsd",
            symmetry_permutations=((0, 1, 1, 3),),
        )

    assert scorer.call_count == 0
    assert refiner.call_count == 0


@pytest.mark.parametrize(
    "permutations",
    (
        ([0.0, 1.0, 2.0, 3.0],),
        ([0, 1, [2], 3],),
    ),
)
def test_malformed_symmetry_mapping_has_stable_fail_closed_error(permutations) -> None:
    scorer = _CountingScorer()

    with pytest.raises(PoseMetricError, match="symmetry permutation"):
        run_bounded_docking_search(
            _space(),
            DockingBudget(candidate_count=4, top_k=2, max_torsions=2),
            scorer,
            problem=_problem(),
            diversity_metric="symmetry_aware_kabsch_rmsd",
            symmetry_permutations=permutations,
        )

    assert scorer.call_count == 0
