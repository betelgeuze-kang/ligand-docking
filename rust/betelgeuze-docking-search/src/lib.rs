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
mod geometry;
mod identity;
mod model;
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
    Fixed64ConformerSourceEvidence, Fixed64FeatureInventory, Fixed64FeatureKind,
    Fixed64GenerationParent, Fixed64GenerationParentRole, Fixed64IndexedSourceEvidence,
    Fixed64Lane, Fixed64MissingFeature, Fixed64Requirement, Fixed64Slot, Fixed64SourceEvidence,
    FIXED64_CANDIDATE_COUNT, FIXED64_LANE_RANGES, FIXED64_PROFILE_ID,
    NATIVE_FIXED64_ALLOCATION_SCHEMA_ID, NATIVE_FIXED64_SLOT_SCHEMA_ID, RETAINED_SOURCE_INDICES,
    TRUE_CONFORMER_SLOT_RANKS,
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
