"""Independent-engine physics primitives that are honest CPU references."""

from betelgeuze_engine_v2.physics.projection import (
    MAX_FIXED_PROJECTION_RANK,
    ProjectionDiagnostics,
    ProjectionRankError,
    fixed_rank_orthogonal_complement,
    fixed_rank_projection_adjoint,
    local_normal_projection,
    project_rigid_body_forces,
)

__all__ = [
    "MAX_FIXED_PROJECTION_RANK",
    "ProjectionDiagnostics",
    "ProjectionRankError",
    "fixed_rank_orthogonal_complement",
    "fixed_rank_projection_adjoint",
    "local_normal_projection",
    "project_rigid_body_forces",
]
