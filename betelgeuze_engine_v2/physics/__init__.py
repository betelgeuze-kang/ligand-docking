"""Independent Engine v2 physics and composition contracts."""

from betelgeuze_engine_v2.physics.composition import (
    EnergyCompositionResult,
    EnergyTermResult,
    IndependentPhysicsProvider,
    compose_energy_terms,
)
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
    "EnergyCompositionResult",
    "EnergyTermResult",
    "IndependentPhysicsProvider",
    "MAX_FIXED_PROJECTION_RANK",
    "ProjectionDiagnostics",
    "ProjectionRankError",
    "compose_energy_terms",
    "fixed_rank_orthogonal_complement",
    "fixed_rank_projection_adjoint",
    "local_normal_projection",
    "project_rigid_body_forces",
]
