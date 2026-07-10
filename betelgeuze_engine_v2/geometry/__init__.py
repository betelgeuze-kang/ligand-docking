"""Geometry primitives for sparse, bounded-degree engine v2 computations."""

from .neighbors import (
    MAX_COMPACT_ATOMS_PER_CELL,
    MAX_COMPACT_NEIGHBORS,
    NEIGHBOR_SCHEMA_VERSION,
    CompactNeighborList,
    NeighborBuildDiagnostics,
    NeighborOverflowError,
    RadiusGraphConfig,
    build_compact_radius_graph,
    build_radius_neighbors,
)

__all__ = [
    "MAX_COMPACT_ATOMS_PER_CELL",
    "MAX_COMPACT_NEIGHBORS",
    "NEIGHBOR_SCHEMA_VERSION",
    "CompactNeighborList",
    "NeighborBuildDiagnostics",
    "NeighborOverflowError",
    "RadiusGraphConfig",
    "build_compact_radius_graph",
    "build_radius_neighbors",
]
