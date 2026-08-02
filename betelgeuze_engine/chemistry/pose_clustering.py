"""Symmetry-aware graph clustering for pose selection (P1-7).

The previous selection was greedy: walk the poses in score order and attach each
one to the first representative within the RMSD threshold. That makes the
clustering depend on input order, and it lets a chain of near-threshold poses
collapse into one cluster even when its ends are far apart, so "top-3 distinct
poses" could silently be three views of the same binding mode.

This module replaces that with connected-component clustering over a symmetry-
aware RMSD graph:

- build the full pairwise symmetry-aware RMSD matrix;
- add an edge whenever the RMSD is within the threshold;
- take connected components as clusters (order-independent);
- optionally require cluster diameter to stay within a cap, which splits the
  chained case a pure component pass would merge.

The representative of each cluster is its best-scoring member, so downstream
top-k selection reports genuinely distinct binding modes.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Sequence

import numpy as np

POSE_CLUSTERING_SCHEMA_VERSION = "symmetry_aware_pose_graph_clustering_v1"

METHOD_GRAPH_SYMMETRY = "connected_component_symmetry_aware_rmsd_graph"
METHOD_GRAPH_ATOM_ORDER = "connected_component_atom_order_rmsd_graph"

DEFAULT_THRESHOLD_A = 2.0

CLAIM_BOUNDARY = (
    "Order-independent symmetry-aware pose clustering only. It reports distinct sampled binding modes for "
    "top-k selection; it is not a benchmarked pose-accuracy claim and does not assert that any cluster is "
    "the experimental binding mode."
)


@dataclass(frozen=True)
class PoseCluster:
    """One cluster of poses that represent the same binding mode."""

    cluster_id: int
    representative_pose_index: int
    member_pose_indices: tuple[int, ...]
    best_score: float
    diameter_a: float

    @property
    def member_count(self) -> int:
        return len(self.member_pose_indices)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["member_pose_indices"] = list(self.member_pose_indices)
        payload["member_count"] = self.member_count
        return payload


@dataclass(frozen=True)
class PoseClusteringResult:
    """Clustering outcome plus the parameters that produced it."""

    status: str
    method: str
    threshold_a: float
    max_cluster_diameter_a: float | None
    symmetry_mapping_count: int
    clusters: tuple[PoseCluster, ...] = ()
    assignments: dict[int, int] = field(default_factory=dict)

    @property
    def cluster_count(self) -> int:
        return len(self.clusters)

    def representative_pose_indices(self, *, limit: int | None = None) -> list[int]:
        """Best-scoring representative per cluster, best cluster first."""

        ordered = sorted(self.clusters, key=lambda cluster: (cluster.best_score, cluster.cluster_id))
        indices = [cluster.representative_pose_index for cluster in ordered]
        return indices if limit is None else indices[: max(int(limit), 0)]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": POSE_CLUSTERING_SCHEMA_VERSION,
            "status": self.status,
            "method": self.method,
            "order_independent": True,
            "threshold_a": float(self.threshold_a),
            "max_cluster_diameter_a": self.max_cluster_diameter_a,
            "symmetry_mapping_count": int(self.symmetry_mapping_count),
            "cluster_count": self.cluster_count,
            "clusters": [cluster.to_dict() for cluster in self.clusters],
            "assignments": {int(key): int(value) for key, value in self.assignments.items()},
            "representative_pose_indices": self.representative_pose_indices(),
            "claim_boundary": CLAIM_BOUNDARY,
        }


def _plain_rmsd(left: np.ndarray, right: np.ndarray) -> float:
    n = min(int(left.shape[0]), int(right.shape[0]))
    if n <= 0:
        return float("inf")
    return float(np.sqrt(np.mean(np.sum((left[:n] - right[:n]) ** 2, axis=1))))


def symmetry_aware_rmsd(
    a: np.ndarray,
    b: np.ndarray,
    symmetry_mappings: Sequence[Sequence[int]] | None = None,
) -> float:
    """Minimum RMSD over the ligand's automorphism mappings.

    Without mappings this is plain atom-order RMSD, which overstates the
    difference between two poses that are identical up to a symmetry swap.
    """

    left = np.asarray(a, dtype=np.float64)
    right = np.asarray(b, dtype=np.float64)
    n = min(int(left.shape[0]), int(right.shape[0]))
    if n <= 0:
        return float("inf")
    best = _plain_rmsd(left, right)
    for mapping in symmetry_mappings or ():
        indices = [int(idx) for idx in list(mapping)[:n]]
        if len(indices) < n:
            continue
        if any(idx < 0 or idx >= int(right.shape[0]) for idx in indices):
            continue
        candidate = _plain_rmsd(left[:n], right[indices])
        if candidate < best:
            best = candidate
    return float(best)


def pairwise_rmsd_matrix(
    pose_coords: Sequence[np.ndarray],
    symmetry_mappings: Sequence[Sequence[int]] | None = None,
) -> np.ndarray:
    """Full symmetric RMSD matrix; the graph pass needs every pair."""

    count = len(pose_coords)
    matrix = np.zeros((count, count), dtype=np.float64)
    for i in range(count):
        for j in range(i + 1, count):
            value = symmetry_aware_rmsd(pose_coords[i], pose_coords[j], symmetry_mappings)
            matrix[i, j] = value
            matrix[j, i] = value
    return matrix


def _connected_components(adjacency: list[set[int]]) -> list[list[int]]:
    seen: set[int] = set()
    components: list[list[int]] = []
    for start in range(len(adjacency)):
        if start in seen:
            continue
        stack = [start]
        component: list[int] = []
        seen.add(start)
        while stack:
            node = stack.pop()
            component.append(node)
            for neighbour in sorted(adjacency[node]):
                if neighbour not in seen:
                    seen.add(neighbour)
                    stack.append(neighbour)
        components.append(sorted(component))
    return components


def _split_by_diameter(
    component: list[int],
    matrix: np.ndarray,
    *,
    max_diameter_a: float,
) -> list[list[int]]:
    """Split a chained component whose ends exceed the diameter cap.

    Seeds are chosen deterministically (lowest index first) and each member joins
    the seed it is closest to, so the split does not depend on input order.
    """

    seeds: list[int] = []
    for node in component:
        if all(matrix[node, seed] > float(max_diameter_a) for seed in seeds):
            seeds.append(node)
    if len(seeds) <= 1:
        return [component]
    groups: dict[int, list[int]] = {seed: [] for seed in seeds}
    for node in component:
        best_seed = min(seeds, key=lambda seed: (matrix[node, seed], seed))
        groups[best_seed].append(node)
    return [sorted(members) for _, members in sorted(groups.items()) if members]


def cluster_poses(
    pose_coords: Sequence[np.ndarray],
    *,
    scores: Sequence[float] | None = None,
    symmetry_mappings: Sequence[Sequence[int]] | None = None,
    threshold_a: float = DEFAULT_THRESHOLD_A,
    max_cluster_diameter_a: float | None = None,
) -> PoseClusteringResult:
    """Cluster poses into distinct binding modes, independent of input order."""

    coords = [np.asarray(pose, dtype=np.float64) for pose in pose_coords]
    mapping_count = 1 + len(list(symmetry_mappings or ()))
    method = METHOD_GRAPH_SYMMETRY if symmetry_mappings else METHOD_GRAPH_ATOM_ORDER
    if not coords:
        return PoseClusteringResult(
            status="blocked_no_poses",
            method=method,
            threshold_a=float(threshold_a),
            max_cluster_diameter_a=max_cluster_diameter_a,
            symmetry_mapping_count=mapping_count,
        )

    score_values = [
        float(value) if value is not None and math.isfinite(float(value)) else float("inf")
        for value in (scores if scores is not None else [0.0] * len(coords))
    ]
    if len(score_values) != len(coords):
        raise ValueError("pose_score_count_mismatch")

    matrix = pairwise_rmsd_matrix(coords, symmetry_mappings)
    adjacency: list[set[int]] = [set() for _ in coords]
    for i in range(len(coords)):
        for j in range(i + 1, len(coords)):
            if matrix[i, j] <= float(threshold_a):
                adjacency[i].add(j)
                adjacency[j].add(i)

    groups: list[list[int]] = []
    for component in _connected_components(adjacency):
        if max_cluster_diameter_a is None or len(component) <= 1:
            groups.append(component)
            continue
        groups.extend(
            _split_by_diameter(component, matrix, max_diameter_a=float(max_cluster_diameter_a))
        )

    # Order clusters by best score so cluster ids are stable and meaningful.
    groups.sort(key=lambda members: (min(score_values[idx] for idx in members), members[0]))

    clusters: list[PoseCluster] = []
    assignments: dict[int, int] = {}
    for cluster_id, members in enumerate(groups):
        representative = min(members, key=lambda idx: (score_values[idx], idx))
        diameter = 0.0
        for i in members:
            for j in members:
                if i < j:
                    diameter = max(diameter, float(matrix[i, j]))
        clusters.append(
            PoseCluster(
                cluster_id=cluster_id,
                representative_pose_index=int(representative),
                member_pose_indices=tuple(int(idx) for idx in members),
                best_score=float(score_values[representative]),
                diameter_a=float(diameter),
            )
        )
        for member in members:
            assignments[int(member)] = cluster_id

    return PoseClusteringResult(
        status="pose_graph_clustered",
        method=method,
        threshold_a=float(threshold_a),
        max_cluster_diameter_a=max_cluster_diameter_a,
        symmetry_mapping_count=mapping_count,
        clusters=tuple(clusters),
        assignments=assignments,
    )


__all__ = [
    "CLAIM_BOUNDARY",
    "DEFAULT_THRESHOLD_A",
    "METHOD_GRAPH_ATOM_ORDER",
    "METHOD_GRAPH_SYMMETRY",
    "POSE_CLUSTERING_SCHEMA_VERSION",
    "PoseCluster",
    "PoseClusteringResult",
    "cluster_poses",
    "pairwise_rmsd_matrix",
    "symmetry_aware_rmsd",
]
