"""Independent Engine v2 reference package.

This surface includes contracts, sparse geometry, mathematical AI/projection
primitives, and a fail-closed CPU orchestrator. It is not a calibrated docking,
MD, free-energy, GPU, or product engine.
"""

# Stack installers intentionally run before the public symbols they patch are
# rebound below.
# ruff: noqa: E402

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

from .stack_round3_molecular import (
    MolecularIntegrityError,
    install_stack_round3_molecular as _install_stack_round3_molecular,
)

STACK_ROUND3_MOLECULAR_SHA256 = _install_stack_round3_molecular()

from .stack_round3_integrity_compat import (
    install_stack_round3_integrity_compat as _install_stack_round3_integrity_compat,
)

STACK_ROUND3_INTEGRITY_COMPAT_SHA256 = (
    _install_stack_round3_integrity_compat()
)

from .stack_round3_list_compat import (
    install_stack_round3_list_compat as _install_stack_round3_list_compat,
)

STACK_ROUND3_LIST_COMPAT_SHA256 = _install_stack_round3_list_compat()

from .docking.search_fingerprint_material import (
    DOCKING_SEARCH_FINGERPRINT_SCHEMA_ID,
    DOCKING_SEARCH_RESULT_SCHEMA_ID,
    SearchFingerprintMaterialError,
    install_search_fingerprint_material as _install_search_fingerprint_material,
    recompute_search_fingerprint_sha256,
)

SEARCH_FINGERPRINT_MATERIAL_SHA256 = _install_search_fingerprint_material()

from .execution_parameter_attestation import (
    ATTESTED_INPUT_BOUND_VERIFICATION_SCHEMA_ID,
    CLI_EXECUTION_PARAMETERS_SCHEMA_ID,
    AttestedInputBoundVerificationReceipt,
    ExecutionParameterAttestationError,
    install_execution_parameter_attestation as _install_execution_parameter_attestation,
)

EXECUTION_PARAMETER_ATTESTATION_SHA256 = (
    _install_execution_parameter_attestation()
)

from .scorer_source_observation import (
    SCORER_SOURCE_OBSERVATION_MODE,
    SCORER_SOURCE_OBSERVATION_SCHEMA_ID,
    SOURCE_OBSERVED_INPUT_BOUND_VERIFICATION_SCHEMA_ID,
    ScorerSourceObservationError,
    ScorerSourceObservationReceipt,
    SourceObservedInputBoundVerificationReceipt,
    install_scorer_source_observation as _install_scorer_source_observation,
)

SCORER_SOURCE_OBSERVATION_SHA256 = _install_scorer_source_observation()

from .molecular import (
    chemical_graph_sha256,
    indexed_topology_sha256,
    source_bound_topology_sha256,
)
from .docking.pipeline import (
    CURRENT_V7_FIXED64_PROFILE_ID,
    EXTERNAL_AUTHORITY_BLOCKERS,
    PIPELINE_CLAIM_BLOCKERS,
    SEALED_CANONICAL_COMPONENT_BINDING,
    SYNTHETIC_D0_FIXTURE_ID,
    SYNTHETIC_D0_FIXTURE_MANIFEST_SHA256,
    SYNTHETIC_D0_FIXTURE_ONLY_BLOCKER,
    SYNTHETIC_D0_FIXTURE_REQUEST_SHA256,
    SYNTHETIC_ONLY_ACKNOWLEDGMENT,
    UNVERIFIED_COMPONENT_BINDING,
    UNVERIFIED_COMPONENT_BLOCKER,
    UNVERIFIED_SIDE_EFFECT_BLOCKER,
    CandidateEvidenceV1,
    DockingPipeline,
    DockingPipelineError,
    DockingPipelineProfileV1,
    DockingPipelineRequestV1,
    DockingPipelineResultV1,
    SyntheticD0FixtureAdmissionV1,
    repository_synthetic_d0_fixture_admission,
)

__version__ = ENGINE_API_VERSION

__all__ = [
    "ALL_ATOM_SCHEMA_ID",
    "ATOM_FEATURE_NAMES",
    "ATOM_FEATURE_SCHEMA_VERSION",
    "ATTESTED_INPUT_BOUND_VERIFICATION_SCHEMA_ID",
    "CHECKPOINT_SCHEMA_VERSION",
    "CURRENT_V7_FIXED64_PROFILE_ID",
    "CLI_EXECUTION_PARAMETERS_SCHEMA_ID",
    "DISTRIBUTION_NAME",
    "DISTRIBUTION_VERSION",
    "DOCKING_SEARCH_FINGERPRINT_SCHEMA_ID",
    "DOCKING_SEARCH_RESULT_SCHEMA_ID",
    "ENGINE_API_VERSION",
    "ENGINE_RESULT_SCHEMA_VERSION",
    "EXECUTION_PARAMETER_ATTESTATION_SHA256",
    "MAX_COMPACT_ATOMS_PER_CELL",
    "MAX_COMPACT_NEIGHBORS",
    "MAX_FIXED_PROJECTION_RANK",
    "NEIGHBOR_SCHEMA_VERSION",
    "REFERENCE_CLAIM_BLOCKERS",
    "REFERENCE_EXECUTION_MODE",
    "RIGID_PROJECTION_NOTE",
    "RUNTIME_INPUT_SCHEMA_VERSION",
    "SCORER_SOURCE_OBSERVATION_MODE",
    "SCORER_SOURCE_OBSERVATION_SCHEMA_ID",
    "SCORER_SOURCE_OBSERVATION_SHA256",
    "SEARCH_FINGERPRINT_MATERIAL_SHA256",
    "SOURCE_OBSERVED_INPUT_BOUND_VERIFICATION_SCHEMA_ID",
    "STACK_ROUND1_HARDENING_SHA256",
    "STACK_ROUND1_MINIMIZATION_COMPAT_SHA256",
    "STACK_ROUND2_EVALUATOR_SHA256",
    "STACK_ROUND3_INTEGRITY_COMPAT_SHA256",
    "STACK_ROUND3_LIST_COMPAT_SHA256",
    "STACK_ROUND3_MOLECULAR_SHA256",
    "VERIFIED_SOURCE_RUNTIME_HARDENING_SHA256",
    "VERSION_TAXONOMY",
    "AllAtomSystem",
    "Atom",
    "AtomFeatureBatch",
    "AttestedInputBoundVerificationReceipt",
    "Bond",
    "Chain",
    "ClaimBlocker",
    "ClaimStage",
    "CompactNeighborList",
    "EnergyCompositionResult",
    "EnergyForcePrediction",
    "EnergyTermResult",
    "EngineExecutionProvenance",
    "EXTERNAL_AUTHORITY_BLOCKERS",
    "PIPELINE_CLAIM_BLOCKERS",
    "ExecutionParameterAttestationError",
    "IndependentEngineV2",
    "IndependentEngineV2Config",
    "IndependentEngineV2Result",
    "DockingPipeline",
    "DockingPipelineError",
    "DockingPipelineProfileV1",
    "DockingPipelineRequestV1",
    "DockingPipelineResultV1",
    "CandidateEvidenceV1",
    "SEALED_CANONICAL_COMPONENT_BINDING",
    "SYNTHETIC_D0_FIXTURE_ID",
    "SYNTHETIC_D0_FIXTURE_MANIFEST_SHA256",
    "SYNTHETIC_D0_FIXTURE_ONLY_BLOCKER",
    "SYNTHETIC_D0_FIXTURE_REQUEST_SHA256",
    "SYNTHETIC_ONLY_ACKNOWLEDGMENT",
    "UNVERIFIED_COMPONENT_BINDING",
    "UNVERIFIED_COMPONENT_BLOCKER",
    "UNVERIFIED_SIDE_EFFECT_BLOCKER",
    "SyntheticD0FixtureAdmissionV1",
    "repository_synthetic_d0_fixture_admission",
    "IndependentPhysicsProvider",
    "KinematicResult",
    "LocalEnergyConfig",
    "LocalEnergyTerms",
    "MolecularIntegrityError",
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
    "ScorerSourceObservationError",
    "ScorerSourceObservationReceipt",
    "SearchFingerprintMaterialError",
    "SourceObservedInputBoundVerificationReceipt",
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
    "chemical_graph_sha256",
    "compose_energy_terms",
    "evaluate_physics_gates",
    "fixed_rank_orthogonal_complement",
    "fixed_rank_projection_adjoint",
    "indexed_topology_sha256",
    "physics_informed_objective",
    "project_rigid_body_forces",
    "recompute_search_fingerprint_sha256",
    "require_valid_all_atom_system",
    "run_internal_cpu_reference",
    "source_bound_topology_sha256",
    "torsion_tree_forward_kinematics",
    "validate_all_atom_system",
]
