"""Symmetry-aware graph clustering tests (P1-7)."""

from __future__ import annotations

import numpy as np
import pytest

from betelgeuze_engine.chemistry.pose_clustering import (
    METHOD_GRAPH_ATOM_ORDER,
    METHOD_GRAPH_SYMMETRY,
    POSE_CLUSTERING_SCHEMA_VERSION,
    cluster_poses,
    pairwise_rmsd_matrix,
    symmetry_aware_rmsd,
)


def _pose(offset: float) -> np.ndarray:
    return np.asarray([[offset, 0.0, 0.0], [offset + 1.0, 0.0, 0.0]], dtype=np.float64)


def test_nearby_poses_share_a_cluster_and_far_pose_does_not() -> None:
    result = cluster_poses(
        [_pose(0.0), _pose(0.5), _pose(10.0)], scores=[1.0, 0.5, 2.0], threshold_a=1.0
    )

    assert result.cluster_count == 2
    assert result.assignments[0] == result.assignments[1]
    assert result.assignments[2] != result.assignments[0]


def test_clustering_is_independent_of_input_order() -> None:
    poses = [_pose(0.0), _pose(0.5), _pose(10.0)]
    scores = [1.0, 0.5, 2.0]
    permutation = [2, 0, 1]

    baseline = cluster_poses(poses, scores=scores, threshold_a=1.0)
    permuted = cluster_poses(
        [poses[i] for i in permutation],
        scores=[scores[i] for i in permutation],
        threshold_a=1.0,
    )

    def grouping(result, index_map):
        return sorted(
            sorted(index_map[i] for i in cluster.member_pose_indices)
            for cluster in result.clusters
        )

    assert grouping(baseline, {i: i for i in range(3)}) == grouping(
        permuted, {position: original for position, original in enumerate(permutation)}
    )


def test_representative_is_the_best_scoring_cluster_member() -> None:
    result = cluster_poses(
        [_pose(0.0), _pose(0.4), _pose(0.8)], scores=[5.0, -3.0, 1.0], threshold_a=2.0
    )

    assert result.cluster_count == 1
    assert result.clusters[0].representative_pose_index == 1
    assert result.clusters[0].best_score == -3.0


def test_clusters_are_ordered_best_score_first() -> None:
    result = cluster_poses(
        [_pose(0.0), _pose(20.0)], scores=[4.0, -1.0], threshold_a=1.0
    )

    assert result.representative_pose_indices() == [1, 0]
    assert result.clusters[0].best_score == -1.0


def test_diameter_cap_splits_a_chained_component() -> None:
    chain = [_pose(0.0), _pose(0.9), _pose(1.8), _pose(2.7)]
    scores = [0.0, 1.0, 2.0, 3.0]

    # Pure connected components merge the whole chain even though its ends are
    # 2.7 A apart, which is what a greedy pass also does.
    merged = cluster_poses(chain, scores=scores, threshold_a=1.0)
    split = cluster_poses(chain, scores=scores, threshold_a=1.0, max_cluster_diameter_a=1.5)

    assert merged.cluster_count == 1
    assert split.cluster_count > 1
    assert all(cluster.diameter_a <= 2.0 for cluster in split.clusters)


def test_symmetry_mapping_collapses_swapped_poses() -> None:
    pose_a = np.asarray([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]], dtype=np.float64)
    pose_b = np.asarray([[1.0, 0.0, 0.0], [0.0, 0.0, 0.0]], dtype=np.float64)
    mappings = [(1, 0)]

    assert symmetry_aware_rmsd(pose_a, pose_b) > 0.0
    assert symmetry_aware_rmsd(pose_a, pose_b, mappings) == 0.0

    without = cluster_poses([pose_a, pose_b], scores=[0.0, 1.0], threshold_a=0.1)
    with_symmetry = cluster_poses(
        [pose_a, pose_b], scores=[0.0, 1.0], threshold_a=0.1, symmetry_mappings=mappings
    )

    assert without.cluster_count == 2
    assert with_symmetry.cluster_count == 1
    assert with_symmetry.method == METHOD_GRAPH_SYMMETRY
    assert without.method == METHOD_GRAPH_ATOM_ORDER


def test_pairwise_matrix_is_symmetric_with_zero_diagonal() -> None:
    matrix = pairwise_rmsd_matrix([_pose(0.0), _pose(1.0), _pose(5.0)])

    assert matrix.shape == (3, 3)
    assert np.allclose(matrix, matrix.T)
    assert np.allclose(np.diag(matrix), 0.0)


def test_every_pose_is_assigned_exactly_once() -> None:
    poses = [_pose(float(index)) for index in range(6)]
    result = cluster_poses(poses, scores=list(range(6)), threshold_a=1.0)

    members = [idx for cluster in result.clusters for idx in cluster.member_pose_indices]
    assert sorted(members) == list(range(6))
    assert set(result.assignments) == set(range(6))


def test_top_k_representatives_are_distinct_binding_modes() -> None:
    poses = [_pose(0.0), _pose(0.2), _pose(8.0), _pose(8.2), _pose(16.0)]
    result = cluster_poses(poses, scores=[1.0, 0.9, 0.5, 0.6, 2.0], threshold_a=1.0)

    top = result.representative_pose_indices(limit=3)
    assert len(top) == 3
    assert len(set(result.assignments[index] for index in top)) == 3


def test_empty_pose_list_is_blocked() -> None:
    result = cluster_poses([], scores=[])

    assert result.status == "blocked_no_poses"
    assert result.cluster_count == 0


def test_score_count_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        cluster_poses([_pose(0.0), _pose(1.0)], scores=[0.0])


def test_payload_reports_schema_and_order_independence() -> None:
    payload = cluster_poses([_pose(0.0)], scores=[0.0]).to_dict()

    assert payload["schema_version"] == POSE_CLUSTERING_SCHEMA_VERSION
    assert payload["order_independent"] is True
    assert "not a benchmarked pose-accuracy claim" in payload["claim_boundary"]
