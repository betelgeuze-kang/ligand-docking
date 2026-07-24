"""Independent Engine v2 reference package.

This surface includes contracts, sparse geometry, mathematical AI/projection
primitives, and a fail-closed CPU orchestrator. It is not a calibrated docking,
MD, free-energy, GPU, or product engine.
"""

import sys as _sys

from .ai import (
    EnergyForcePrediction,
    KinematicResult,
    LocalEnergyConfig,
    LocalEnergyTerms,
    ParityAwareLocalEnergyModel,
    PhysicsGateResult,
    PhysicsGateThresholds,
    PhysicsLossWeights,
    PhysicsObjectiveResult,
    SparseNeighborGraph,
    TemporalRollout,
    TemporalStateGNN,
    TorsionTopologyGNN,
    axis_angle_matrix,
    evaluate_physics_gates,
    physics_informed_objective,
    torsion_tree_forward_kinematics,
)
from .contracts import (
    ALL_ATOM_SCHEMA_ID,
    CHECKPOINT_SCHEMA_VERSION,
    DISTRIBUTION_NAME,
    DISTRIBUTION_VERSION,
    ENGINE_API_VERSION,
    ENGINE_RESULT_SCHEMA_VERSION,
    RUNTIME_INPUT_SCHEMA_VERSION,
    VERSION_TAXONOMY,
    ClaimStage,
    QuantityDescriptor,
    UNCALIBRATED_ENERGY,
    UNCALIBRATED_FORCE,
)
from .engine import (
    REFERENCE_CLAIM_BLOCKERS,
    REFERENCE_EXECUTION_MODE,
    RIGID_PROJECTION_NOTE,
    ClaimBlocker,
    EngineExecutionProvenance,
    IndependentEngineV2,
    IndependentEngineV2Config,
    IndependentEngineV2Result,
    run_internal_cpu_reference,
)
from .features import (
    ATOM_FEATURE_NAMES,
    ATOM_FEATURE_SCHEMA_VERSION,
    AtomFeatureBatch,
    build_deterministic_atom_features,
)
from .geometry import (
    MAX_COMPACT_ATOMS_PER_CELL,
    MAX_COMPACT_NEIGHBORS,
    NEIGHBOR_SCHEMA_VERSION,
    CompactNeighborList,
    NeighborBuildDiagnostics,
    NeighborOverflowError,
    RadiusGraphConfig,
    build_compact_radius_graph,
)
from .molecular import (
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    MolecularValidationError,
    Residue,
    StructureProvenance,
    UnitCell,
    ValidationReport,
    canonical_coordinates_sha256,
    canonical_system_sha256,
    canonical_topology_sha256,
    require_valid_all_atom_system,
    validate_all_atom_system,
)
from .physics import (
    EnergyCompositionResult,
    EnergyTermResult,
    IndependentPhysicsProvider,
    MAX_FIXED_PROJECTION_RANK,
    ProjectionDiagnostics,
    ProjectionRankError,
    compose_energy_terms,
    fixed_rank_orthogonal_complement,
    fixed_rank_projection_adjoint,
    project_rigid_body_forces,
)

_VERIFIED_SOURCE_FINDER_ATTRIBUTE = (
    "_betelgeuze_reference_minimization_validation_source_finder"
)
if hasattr(_sys, _VERIFIED_SOURCE_FINDER_ATTRIBUTE):
    from .runtime_snapshot_hardening import (
        install_verified_source_runtime_hardening as _install_verified_source_runtime_hardening,
    )

    VERIFIED_SOURCE_RUNTIME_HARDENING_SHA256 = (
        _install_verified_source_runtime_hardening()
    )
else:
    VERIFIED_SOURCE_RUNTIME_HARDENING_SHA256 = ""

from .stack_round1_hardening import (
    install_stack_round1_hardening as _install_stack_round1_hardening,
)

STACK_ROUND1_HARDENING_SHA256 = _install_stack_round1_hardening()

from .stack_round1_minimization_compat import (
    install_stack_round1_minimization_compat as _install_stack_round1_minimization_compat,
)

STACK_ROUND1_MINIMIZATION_COMPAT_SHA256 = (
    _install_stack_round1_minimization_compat()
)

from .stack_round2_evaluator import (
    install_stack_round2_evaluator as _install_stack_round2_evaluator,
)

STACK_ROUND2_EVALUATOR_SHA256 = _install_stack_round2_evaluator()

__version__ = ENGINE_API_VERSION

__all__ = [
    "ALL_ATOM_SCHEMA_ID",
    "ATOM_FEATURE_NAMES",
    "ATOM_FEATURE_SCHEMA_VERSION",
    "CHECKPOINT_SCHEMA_VERSION",
    "DISTRIBUTION_NAME",
    "DISTRIBUTION_VERSION",
    "ENGINE_API_VERSION",
    "ENGINE_RESULT_SCHEMA_VERSION",
    "MAX_COMPACT_ATOMS_PER_CELL",
    "MAX_COMPACT_NEIGHBORS",
    "MAX_FIXED_PROJECTION_RANK",
    "NEIGHBOR_SCHEMA_VERSION",
    "REFERENCE_CLAIM_BLOCKERS",
    "REFERENCE_EXECUTION_MODE",
    "RIGID_PROJECTION_NOTE",
    "RUNTIME_INPUT_SCHEMA_VERSION",
    "STACK_ROUND1_HARDENING_SHA256",
    "STACK_ROUND1_MINIMIZATION_COMPAT_SHA256",
    "STACK_ROUND2_EVALUATOR_SHA256",
    "VERIFIED_SOURCE_RUNTIME_HARDENING_SHA256",
    "VERSION_TAXONOMY",
    "AllAtomSystem",
    "Atom",
    "AtomFeatureBatch",
    "Bond",
    "Chain",
    "ClaimBlocker",
    "ClaimStage",
    "CompactNeighborList",
    "EnergyCompositionResult",
    "EnergyForcePrediction",
    "EnergyTermResult",
    "EngineExecutionProvenance",
    "IndependentEngineV2",
    "IndependentEngineV2Config",
    "IndependentEngineV2Result",
    "IndependentPhysicsProvider",
    "KinematicResult",
    "LocalEnergyConfig",
    "LocalEnergyTerms",
    "MolecularValidationError",
    "NeighborBuildDiagnostics",
    "NeighborOverflowError",
    "ParityAwareLocalEnergyModel",
    "PhysicsGateResult",
    "PhysicsGateThresholds",
    "PhysicsLossWeights",
    "PhysicsObjectiveResult",
    "ProjectionDiagnostics",
    "ProjectionRankError",
    "QuantityDescriptor",
    "RadiusGraphConfig",
    "Residue",
    "SparseNeighborGraph",
    "StructureProvenance",
    "TemporalRollout",
    "TemporalStateGNN",
    "TorsionTopologyGNN",
    "UNCALIBRATED_ENERGY",
    "UNCALIBRATED_FORCE",
    "UnitCell",
    "ValidationReport",
    "axis_angle_matrix",
    "build_compact_radius_graph",
    "build_deterministic_atom_features",
    "canonical_coordinates_sha256",
    "canonical_system_sha256",
    "canonical_topology_sha256",
    "compose_energy_terms",
    "evaluate_physics_gates",
    "fixed_rank_orthogonal_complement",
    "fixed_rank_projection_adjoint",
    "physics_informed_objective",
    "project_rigid_body_forces",
    "require_valid_all_atom_system",
    "run_internal_cpu_reference",
    "torsion_tree_forward_kinematics",
    "validate_all_atom_system",
]
