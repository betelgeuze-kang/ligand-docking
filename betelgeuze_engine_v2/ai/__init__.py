"""Sparse non-Transformer AI references for the independent molecular engine."""

from betelgeuze_engine_v2.ai.energy import (
    EnergyForcePrediction,
    LocalEnergyConfig,
    LocalEnergyTerms,
    ParityAwareLocalEnergyModel,
)
from betelgeuze_engine_v2.ai.physics_informed import (
    PhysicsGateResult,
    PhysicsGateThresholds,
    PhysicsLossWeights,
    PhysicsObjectiveResult,
    evaluate_physics_gates,
    physics_informed_objective,
)
from betelgeuze_engine_v2.ai.sparse_graph import (
    ComplexityMetadata,
    SparseNeighborGraph,
    coerce_sparse_graph,
)
from betelgeuze_engine_v2.ai.temporal import TemporalRollout, TemporalStateGNN
from betelgeuze_engine_v2.ai.torsion import (
    KinematicResult,
    TorsionTopologyGNN,
    axis_angle_matrix,
    torsion_tree_forward_kinematics,
)

__all__ = [
    "ComplexityMetadata",
    "EnergyForcePrediction",
    "KinematicResult",
    "LocalEnergyConfig",
    "LocalEnergyTerms",
    "ParityAwareLocalEnergyModel",
    "PhysicsGateResult",
    "PhysicsGateThresholds",
    "PhysicsLossWeights",
    "PhysicsObjectiveResult",
    "SparseNeighborGraph",
    "TemporalRollout",
    "TemporalStateGNN",
    "TorsionTopologyGNN",
    "axis_angle_matrix",
    "coerce_sparse_graph",
    "evaluate_physics_gates",
    "physics_informed_objective",
    "torsion_tree_forward_kinematics",
]
