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
mod fixed64_placement;
mod fixed64_producer;
mod fixed64_single_anchor;
mod geometric_admission;
mod geometry;
mod identity;
mod model;
mod native_hash;
mod prune;
mod receipt;
mod refine;
mod search;
mod sha256;
mod short_range;
mod so3;
mod surface;
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
pub use fixed64_single_anchor::{
    generate_native_fixed64_single_anchor, Fixed64SingleAnchorPlacement,
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
pub use search::{search, search_default, search_short_range};
pub use short_range::{ShortRangeConfig, ShortRangeEvaluator};
pub use so3::{orientations, Orientation};

/// Frozen contract for deterministic search inputs, stage ordering, and receipts.
pub const SEARCH_SCHEMA_ID: &str = "betelgeuze.docking_search/2.0.0";

/// Frozen receipt schema for stage denominators and bounded allocations.
pub const SEARCH_RECEIPT_SCHEMA_ID: &str = "betelgeuze.docking_search_receipt/2.0.0";

/// Coulomb conversion factor in kcal·angstrom/(mol·e²).
pub const COULOMB_KCAL_ANGSTROM_PER_MOL_E2: f64 = 332.063_713_299;
