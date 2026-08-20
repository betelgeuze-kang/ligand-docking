//! Deterministic, bounded docking-search primitives owned by Betelgeuze.
//!
//! The crate is deliberately independent of Python, benchmark oracles, external
//! solvers, and serialization frameworks. Public models use canonical angstrom,
//! radian, kcal/mol, and kcal/(mol·angstrom) units so a thin FFI bridge can
//! convert ordinary vectors without sharing an implementation with an oracle.

mod anchors;
mod cluster;
mod error;
mod fixed64;
mod fixed64_cluster;
mod fixed64_pipeline;
mod fixed64_placement;
mod fixed64_producer;
mod fixed64_ranking;
mod fixed64_single_anchor;
mod fixed64_validity;
mod geometric_admission;
mod geometry;
mod identity;
mod model;
mod native_hash;
mod prune;
mod receipt;
mod refine;
mod repository_d0;
mod rigid_refinement;
mod sampling_funnel;
mod sampling_funnel_batch;
#[cfg(test)]
mod sampling_funnel_tests;
mod scorer_v1;
mod search;
mod sha256;
mod short_range;
mod so3;
mod surface;
mod torsion_refinement;
mod validity;

pub use error::{EvaluationError, SearchError, SearchErrorCode};
pub use fixed64::{
    Fixed64Allocation, Fixed64AllocationError, Fixed64AnchorKind, Fixed64AtomicFeatureEvidence,
    Fixed64ConformerSourceEvidence, Fixed64ExactV11SourceEvidence, Fixed64FeatureInventory,
    Fixed64FeatureKind, Fixed64GenerationParent, Fixed64GenerationParentRole,
    Fixed64IndexedSourceEvidence, Fixed64Lane, Fixed64MissingFeature, Fixed64Requirement,
    Fixed64Slot, Fixed64SourceEvidence, FIXED64_CANDIDATE_COUNT, FIXED64_LANE_RANGES,
    FIXED64_PROFILE_ID, NATIVE_FIXED64_ALLOCATION_SCHEMA_ID, NATIVE_FIXED64_SLOT_SCHEMA_ID,
    RETAINED_SOURCE_INDICES, TRUE_CONFORMER_SLOT_RANKS,
};
pub use fixed64_cluster::{
    cluster_native_fixed64_direct_rmsd_kernel, NativeFixed64RmsdClusterError,
    NativeFixed64RmsdClusterErrorCode, NativeFixed64RmsdClusterInputRow,
    NativeFixed64RmsdClusterKernelOutcome, NativeFixed64RmsdClusterRow,
    NATIVE_FIXED64_DIRECT_RMSD_CLUSTER_ALGORITHM_ID,
};
pub use fixed64_pipeline::{
    run_native_fixed64_pipeline, NativeFixed64AuthorityBlocker, NativeFixed64Consumer,
    NativeFixed64ConsumerView, NativeFixed64PipelineError, NativeFixed64PipelineReceipt,
    NativeFixed64PipelineStage, NATIVE_FIXED64_AUTHORITY_BLOCKERS,
    NATIVE_FIXED64_CONSUMER_VIEW_SCHEMA_ID, NATIVE_FIXED64_PIPELINE_ID,
    NATIVE_FIXED64_PIPELINE_SCHEMA_ID,
};
pub use fixed64_placement::{
    generate_native_fixed64_indexed_so3, Fixed64FeatureGeometry, Fixed64FeatureGeometryInventory,
    Fixed64IndexedSo3Placement, Fixed64PlacementError, Fixed64PlacementErrorCode,
    Fixed64PlacementSource, NATIVE_FIXED64_FEATURE_GEOMETRY_SCHEMA_ID,
    NATIVE_FIXED64_INDEXED_SO3_PROFILE_ID, NATIVE_FIXED64_INDEXED_SO3_SCHEMA_ID,
    NATIVE_FIXED64_SINGLE_ANCHOR_PROFILE_ID, NATIVE_FIXED64_SINGLE_ANCHOR_SCHEMA_ID,
};
pub use fixed64_producer::{
    native_fixed64_producer_policy_sha256, produce_native_fixed64_proposals,
    Fixed64CoordinateSourceKind, Fixed64CoordinateSourcePayload, Fixed64PassthroughPlacement,
    Fixed64ProducerError, Fixed64ProducerErrorCode, Fixed64ProposalBatch,
    Fixed64ProposalFailureCode, Fixed64ProposalGenerationFailure, Fixed64ProposalPlacement,
    Fixed64ProposalRecord, Fixed64ProposalSourceBundle, Fixed64ProposalStatus,
    NATIVE_FIXED64_COORDINATE_SOURCE_SCHEMA_ID, NATIVE_FIXED64_GENERATION_FAILURE_SCHEMA_ID,
    NATIVE_FIXED64_PASSTHROUGH_SCHEMA_ID, NATIVE_FIXED64_PRODUCER_BATCH_SCHEMA_ID,
    NATIVE_FIXED64_PRODUCER_PROFILE_ID, NATIVE_FIXED64_PROPOSAL_RECORD_SCHEMA_ID,
    NATIVE_FIXED64_SOURCE_BUNDLE_SCHEMA_ID,
};
pub use fixed64_ranking::{
    rank_native_fixed64_stable_top_k_kernel, rank_native_fixed64_top_k, NativeFixed64RankingBatch,
    NativeFixed64RankingError, NativeFixed64RankingErrorCode, NativeFixed64RankingRecord,
    NativeFixed64StableTopKInputRow, NativeFixed64StableTopKKernelOutcome,
    NATIVE_FIXED64_PRIMARY_RANKING_SEMANTICS, NATIVE_FIXED64_RANKING_ALGORITHM_ID,
    NATIVE_FIXED64_RANKING_BATCH_SCHEMA_ID, NATIVE_FIXED64_RANKING_RECORD_SCHEMA_ID,
    NATIVE_FIXED64_TOP_K_LIMIT, NATIVE_FIXED64_VALID_RANKING_SEMANTICS,
};
pub use fixed64_single_anchor::{
    generate_native_fixed64_single_anchor, native_fixed64_single_anchor_kernel,
    Fixed64SingleAnchorPlacement, NativeFixed64SingleAnchorKernelOutcome,
    NativeFixed64SingleAnchorKernelPlacement,
};
pub use fixed64_validity::{
    evaluate_native_fixed64_pose_validity, NativeFixed64ValidityBackend,
    NativeFixed64ValidityBatch, NativeFixed64ValidityBlocker, NativeFixed64ValidityChecks,
    NativeFixed64ValidityConfig, NativeFixed64ValidityContext, NativeFixed64ValidityError,
    NativeFixed64ValidityErrorCode, NativeFixed64ValidityFailure, NativeFixed64ValidityFailureCode,
    NativeFixed64ValidityKernelFailure, NativeFixed64ValidityKernelOutcome,
    NativeFixed64ValidityMeasurements, NativeFixed64ValidityResult, NativeFixed64ValidityRow,
    NativeFixed64ValidityRowStatus, NativeFixed64ValidityRustCpuKernel,
    NATIVE_FIXED64_ELEMENT_RECEPTOR_TRAVERSAL_ID, NATIVE_FIXED64_VALIDITY_ALGORITHM_ID,
    NATIVE_FIXED64_VALIDITY_BATCH_SCHEMA_ID, NATIVE_FIXED64_VALIDITY_CONFIG_SCHEMA_ID,
    NATIVE_FIXED64_VALIDITY_CONTEXT_SCHEMA_ID, NATIVE_FIXED64_VALIDITY_FAILURE_SCHEMA_ID,
    NATIVE_FIXED64_VALIDITY_MAX_CHIRALITY_CENTERS, NATIVE_FIXED64_VALIDITY_MAX_CROSS_CHECKS,
    NATIVE_FIXED64_VALIDITY_MAX_PAIR_CHECKS, NATIVE_FIXED64_VALIDITY_RECEPTOR_TRAVERSAL_ID,
    NATIVE_FIXED64_VALIDITY_RESULT_SCHEMA_ID, NATIVE_FIXED64_VALIDITY_ROW_SCHEMA_ID,
};
pub use geometric_admission::{
    evaluate_fixed64_geometric_metrics, native_fixed64_coordinate_sha256,
    native_fixed64_heavy_atom_mask_sha256, native_fixed64_radii_sha256, Fixed64GeometricBatch,
    Fixed64GeometricDecision, Fixed64GeometricError, Fixed64GeometricErrorCode,
    Fixed64GeometricInput, Fixed64GeometricMetrics, Fixed64GeometricStatus,
    FIXED64_MAX_ABSOLUTE_COORDINATE_ANGSTROM, FIXED64_MAX_BATCH_EXACT_PAIR_EVALUATIONS,
    FIXED64_MAX_LIGAND_ATOMS, FIXED64_MAX_POCKET_RADIUS_ANGSTROM, FIXED64_MAX_RECEPTOR_ATOMS,
    FIXED64_MAX_VDW_RADIUS_ANGSTROM, FIXED64_MIN_VDW_RADIUS_ANGSTROM,
    HARD_REJECTION_MINIMUM_VDW_RATIO, NATIVE_FIXED64_GEOMETRIC_BATCH_SCHEMA_ID,
    NATIVE_FIXED64_GEOMETRIC_DECISION_SCHEMA_ID, NATIVE_FIXED64_GEOMETRIC_INPUT_SCHEMA_ID,
    NATIVE_FIXED64_GEOMETRIC_METRICS_SCHEMA_ID,
};
pub use geometry::{Quaternion, Vec3};
pub use model::{
    AnchorId, AnchorKind, CandidateKey, CandidateReason, CandidateRow, CandidateStatus,
    EnergyForceEvaluator, LigandAnchor, LigandAtom, PlacementMode, RankedPose, ReceptorAtom,
    SearchConfig, SearchInput, SearchResult, SurfaceId, SurfaceSample, MAX_ANCHOR_COMBINATIONS,
    MAX_CANDIDATE_COORDINATES, MAX_COMPATIBLE_SINGLE_ANCHOR_PAIRS, MAX_EVALUATION_DETAIL_BYTES,
    MAX_GENERATED_CANDIDATES, MAX_LEDGER_PAYLOAD_BYTES, MAX_LIGAND_ANCHORS, MAX_LIGAND_ATOMS,
    MAX_ORIENTATIONS, MAX_PAIR_EVALUATIONS, MAX_RECEPTOR_ATOMS, MAX_REFINEMENT_STEPS,
    MAX_SURFACE_SAMPLES, MAX_TOP_K,
};
pub use receipt::SearchReceipt;
pub use repository_d0::{
    materialize_repository_synthetic_d0_sources, RepositoryD0AtomicFeature,
    RepositoryD0ProposalSource, RepositoryD0SourceBundle, RepositoryD0SourceError,
    REPOSITORY_D0_CANDIDATE_DENOMINATOR, REPOSITORY_D0_CENTERED_CANDIDATE_COUNT,
    REPOSITORY_D0_EXPECTED_ALLOCATION_SHA256, REPOSITORY_D0_EXPECTED_BUNDLE_SHA256,
    REPOSITORY_D0_EXPECTED_FEATURE_INVENTORY_SHA256, REPOSITORY_D0_EXPECTED_PREPARED_INPUT_SHA256,
    REPOSITORY_D0_GUIDED_SOURCE_INDICES, REPOSITORY_D0_LIGAND_ATOM_COUNT,
    REPOSITORY_D0_POCKET_RADIUS_ANGSTROM, REPOSITORY_D0_PROFILE_ID,
    REPOSITORY_D0_RECEPTOR_ATOM_COUNT, REPOSITORY_D0_RETAINED_SOURCE_INDICES,
    REPOSITORY_D0_SCHEMA_ID, REPOSITORY_D0_SEED, REPOSITORY_D0_TOP_K,
    REPOSITORY_D0_TRANSLATION_RADIUS_ANGSTROM,
};
pub use rigid_refinement::{
    refine_interaction_aware_rigid_v2, refine_interaction_aware_rigid_v3,
    refine_interaction_aware_rigid_v6, NativeRigidRefinementContext, NativeRigidRefinementError,
    NativeRigidRefinementErrorCode, NativeRigidRefinementOutcome, NativeRigidRefinementProfile,
    NativeRigidV2Config, NativeRigidV3Config, NativeRigidV6Outcome,
    NATIVE_RIGID_REFINEMENT_MAX_LIGAND_ATOMS, NATIVE_RIGID_REFINEMENT_MAX_PAIR_EVALUATIONS,
    NATIVE_RIGID_REFINEMENT_MAX_RECEPTOR_ATOMS, NATIVE_RIGID_REFINEMENT_MAX_STEPS,
};
pub use sampling_funnel::{
    run_native_sampling_funnel, NativeSamplingFunnelCandidate, NativeSamplingFunnelCandidateState,
    NativeSamplingFunnelDecision, NativeSamplingFunnelError, NativeSamplingFunnelErrorCode,
    NativeSamplingFunnelGeneratedCandidate, NativeSamplingFunnelLane,
    NativeSamplingFunnelLaneSummary, NativeSamplingFunnelObservation, NativeSamplingFunnelReceipt,
    NativeSamplingFunnelSelectedRow, NativeSamplingFunnelSelectedState,
    NATIVE_SAMPLING_FUNNEL_DUPLICATE_POLICY, NATIVE_SAMPLING_FUNNEL_EMBEDDING_DIMENSION,
    NATIVE_SAMPLING_FUNNEL_HARD_MINIMUM_VDW_RATIO, NATIVE_SAMPLING_FUNNEL_INPUT_DENOMINATOR,
    NATIVE_SAMPLING_FUNNEL_INPUT_SCHEMA_ID, NATIVE_SAMPLING_FUNNEL_LANE_ORDER,
    NATIVE_SAMPLING_FUNNEL_MAXIMUM_POCKET_ESCAPE_ANGSTROM,
    NATIVE_SAMPLING_FUNNEL_OUTPUT_DENOMINATOR, NATIVE_SAMPLING_FUNNEL_PROFILE_CANONICAL_SHA256,
    NATIVE_SAMPLING_FUNNEL_PROFILE_ID, NATIVE_SAMPLING_FUNNEL_QUALITY_PREFILTER_MULTIPLIER,
    NATIVE_SAMPLING_FUNNEL_SCHEMA_ID,
};
pub use sampling_funnel_batch::{
    materialize_native_sampling_funnel_preselected_batch, NativeSamplingFunnelBatchError,
    NativeSamplingFunnelBatchErrorCode, NativeSamplingFunnelPayloadBatch,
    NativeSamplingFunnelPayloadRow, NativeSamplingFunnelPayloadRowState,
    NativeSamplingFunnelPreselectedBatch, NativeSamplingFunnelPreselectedRow,
    NATIVE_SAMPLING_FUNNEL_PAYLOAD_BATCH_SCHEMA_ID,
    NATIVE_SAMPLING_FUNNEL_PRESELECTED_BATCH_SCHEMA_ID,
};
pub use scorer_v1::{
    score_native_fixed64_scorer_v1, NativeScorerV1Atom, NativeScorerV1Backend, NativeScorerV1Batch,
    NativeScorerV1Config, NativeScorerV1Context, NativeScorerV1Donor, NativeScorerV1Error,
    NativeScorerV1ErrorCode, NativeScorerV1Failure, NativeScorerV1FailureCode,
    NativeScorerV1KernelFailure, NativeScorerV1KernelOutcome, NativeScorerV1KernelTerms,
    NativeScorerV1Row, NativeScorerV1RowStatus, NativeScorerV1RustCpuKernel, NativeScorerV1Terms,
    NATIVE_SCORER_V1_ALGORITHM_ID, NATIVE_SCORER_V1_BATCH_SCHEMA_ID,
    NATIVE_SCORER_V1_CONFIG_SCHEMA_ID, NATIVE_SCORER_V1_CONTEXT_SCHEMA_ID,
    NATIVE_SCORER_V1_FAILURE_SCHEMA_ID, NATIVE_SCORER_V1_MAX_LIGAND_PAIR_CHECKS,
    NATIVE_SCORER_V1_MAX_RECEPTOR_CANDIDATE_PAIRS, NATIVE_SCORER_V1_MAX_ROTORS,
    NATIVE_SCORER_V1_PAIR_TRAVERSAL_ID, NATIVE_SCORER_V1_ROW_SCHEMA_ID, NATIVE_SCORER_V1_SCORE_ID,
    NATIVE_SCORER_V1_TERMS_SCHEMA_ID,
};
pub use search::{search, search_default, search_short_range};
pub use short_range::{ShortRangeConfig, ShortRangeEvaluator};
pub use so3::{orientations, Orientation};
pub use torsion_refinement::{
    refine_interaction_aware_torsion_contact_v7,
    validate_interaction_aware_torsion_contact_v7_context, NativeTorsionV7Config,
    NativeTorsionV7Context, NativeTorsionV7Error, NativeTorsionV7ErrorCode, NativeTorsionV7Move,
    NativeTorsionV7Objective, NativeTorsionV7Outcome, NativeTorsionV7Request,
    NativeTorsionV7SelectionReason, NativeTorsionV7SkipReason, NATIVE_TORSION_V7_ALGORITHM_ID,
    NATIVE_TORSION_V7_CONFIG_SCHEMA_ID, NATIVE_TORSION_V7_MAX_CALLER_STEPS,
    NATIVE_TORSION_V7_MAX_LIGAND_ATOMS, NATIVE_TORSION_V7_MAX_RECEPTOR_ATOMS,
    NATIVE_TORSION_V7_MAX_TOTAL_PAIR_EVALUATIONS,
};

/// Frozen contract for deterministic search inputs, stage ordering, and receipts.
pub const SEARCH_SCHEMA_ID: &str = "betelgeuze.docking_search/2.0.0";

/// Frozen receipt schema for stage denominators and bounded allocations.
pub const SEARCH_RECEIPT_SCHEMA_ID: &str = "betelgeuze.docking_search_receipt/2.0.0";

/// Coulomb conversion factor in kcal·angstrom/(mol·e²).
pub const COULOMB_KCAL_ANGSTROM_PER_MOL_E2: f64 = 332.063_713_299;
