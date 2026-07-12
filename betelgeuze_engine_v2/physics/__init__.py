"""Independent Engine v2 physics, registry, and composition contracts."""

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
from betelgeuze_engine_v2.physics.registry import (
    MAX_REGISTERED_PHYSICS_TERMS,
    IndependentPhysicsTerm,
    PhysicsRegistryEvaluation,
    PhysicsTermRegistry,
    PhysicsTermRegistryError,
    PhysicsTermRow,
    sum_validated_physics_terms,
)

__all__ = [
    "EnergyCompositionResult",
    "EnergyTermResult",
    "IndependentPhysicsProvider",
    "IndependentPhysicsTerm",
    "MAX_FIXED_PROJECTION_RANK",
    "MAX_REGISTERED_PHYSICS_TERMS",
    "PhysicsRegistryEvaluation",
    "PhysicsTermRegistry",
    "PhysicsTermRegistryError",
    "PhysicsTermRow",
    "ProjectionDiagnostics",
    "ProjectionRankError",
    "compose_energy_terms",
    "fixed_rank_orthogonal_complement",
    "fixed_rank_projection_adjoint",
    "local_normal_projection",
    "project_rigid_body_forces",
    "sum_validated_physics_terms",
]
