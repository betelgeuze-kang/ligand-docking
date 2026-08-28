//! Raw bindings for the Betelgeuze native compute ABI.
//!
//! This crate intentionally mirrors the native headers
//! `include/betelgeuze/engine.h`, `include/betelgeuze/direct_ewald.h`,
//! `include/betelgeuze/direct_ewald_composite.h`,
//! `include/betelgeuze/direct_ewald_composite_dynamics.h`,
//! `include/betelgeuze/particle_mesh_reciprocal.h`, and
//! `include/betelgeuze/particle_mesh_ewald.h`, and
//! `include/betelgeuze/particle_mesh_ewald_composite.h` without adding
//! ownership or lifetime semantics. Prefer `betelgeuze-runtime` for a safe
//! API.
//!
//! The optional `hip` feature requires `BG_HIP_ARCHITECTURE` and a ROCm
//! toolchain selected with `HIP_PATH` or `ROCM_PATH`. If device libraries are
//! not installed below that toolchain, set `ROCM_DEVICE_LIB_PATH`. Deployed
//! executables must also make that ROCm installation's `libamdhip64` visible
//! to the platform dynamic loader.

#![no_std]
#![allow(non_camel_case_types)]

use core::ffi::c_char;

#[used]
static BG_RUST_CPU_PROVIDER_LINK_ANCHOR: extern "C" fn() -> u32 =
    betelgeuze_cpu_kernel::bg_rust_cpu_provider_abi_version_v1;

pub const BG_ABI_VERSION_MAJOR: u32 = 1;
pub const BG_ABI_VERSION_MINOR: u32 = 21;
pub const BG_ABI_VERSION: u32 = 1;

pub const BG_DIRECT_EWALD_ABI_VERSION_MAJOR: u32 = 1;
pub const BG_DIRECT_EWALD_ABI_VERSION_MINOR: u32 = 0;
pub const BG_DIRECT_EWALD_ABI_VERSION: u32 = 1;
pub const BG_DIRECT_EWALD_ERROR_DETAIL_CAPACITY: u32 = 256;

pub const BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION_MAJOR: u32 = 1;
pub const BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION_MINOR: u32 = 0;
pub const BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION: u32 = 1;
pub const BG_PARTICLE_MESH_RECIPROCAL_ERROR_DETAIL_CAPACITY: u32 = 256;
pub const BG_PARTICLE_MESH_RECIPROCAL_CARDINAL_B_SPLINE_ORDER: u32 = 4;

pub const BG_PARTICLE_MESH_EWALD_ABI_VERSION_MAJOR: u32 = 1;
pub const BG_PARTICLE_MESH_EWALD_ABI_VERSION_MINOR: u32 = 0;
pub const BG_PARTICLE_MESH_EWALD_ABI_VERSION: u32 = 1;

pub const BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION_MAJOR: u32 = 1;
pub const BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION_MINOR: u32 = 0;
pub const BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION: u32 = 1;

pub const BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION_MAJOR: u32 = 1;
pub const BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION_MINOR: u32 = 0;
pub const BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION: u32 = 1;

pub const BG_DIRECT_EWALD_COMPOSITE_DYNAMICS_ABI_VERSION_MAJOR: u32 = 1;
pub const BG_DIRECT_EWALD_COMPOSITE_DYNAMICS_ABI_VERSION_MINOR: u32 = 0;
pub const BG_DIRECT_EWALD_COMPOSITE_DYNAMICS_ABI_VERSION: u32 = 1;

pub const BG_CANONICAL_LENGTH_UNIT: &[u8] = b"angstrom\0";
pub const BG_CANONICAL_ENERGY_UNIT: &[u8] = b"kcal/mol\0";
pub const BG_CANONICAL_FORCE_UNIT: &[u8] = b"kcal/(mol*angstrom)\0";
pub const BG_CANONICAL_CHARGE_UNIT: &[u8] = b"elementary_charge\0";
pub const BG_CANONICAL_MASS_UNIT: &[u8] = b"dalton\0";
pub const BG_CANONICAL_ANGLE_UNIT: &[u8] = b"radian\0";
pub const BG_CANONICAL_TIME_UNIT: &[u8] = b"femtosecond\0";
pub const BG_CANONICAL_VELOCITY_UNIT: &[u8] = b"angstrom/femtosecond\0";
pub const BG_CANONICAL_TEMPERATURE_UNIT: &[u8] = b"kelvin\0";

pub const BG_COULOMB_CONSTANT_KCAL_ANGSTROM_PER_MOL_E2: f64 = 332.063_713_299;

pub type bg_status = i32;
pub const BG_STATUS_OK: bg_status = 0;
pub const BG_STATUS_INVALID_ARGUMENT: bg_status = 1;
pub const BG_STATUS_ABI_MISMATCH: bg_status = 2;
pub const BG_STATUS_UNSUPPORTED_BACKEND: bg_status = 3;
pub const BG_STATUS_BACKEND_UNAVAILABLE: bg_status = 4;
pub const BG_STATUS_OUT_OF_MEMORY: bg_status = 5;
pub const BG_STATUS_CAPACITY_OVERFLOW: bg_status = 6;
pub const BG_STATUS_BUFFER_TOO_SMALL: bg_status = 7;
pub const BG_STATUS_BACKEND_ERROR: bg_status = 8;
pub const BG_STATUS_INTERNAL_ERROR: bg_status = 9;
pub const BG_STATUS_NUMERICAL_ERROR: bg_status = 10;

pub type bg_backend = i32;
pub const BG_BACKEND_AUTO: bg_backend = 0;
pub const BG_BACKEND_CPP_CPU_REFERENCE: bg_backend = 1;
pub const BG_BACKEND_HIP_FAST: bg_backend = 2;
pub const BG_BACKEND_RUST_CPU: bg_backend = 3;
pub const BG_BACKEND_HIP_SAFE: bg_backend = 4;
pub const BG_BACKEND_CPU: bg_backend = BG_BACKEND_CPP_CPU_REFERENCE;
pub const BG_BACKEND_HIP: bg_backend = BG_BACKEND_HIP_FAST;

pub type bg_unit_system = i32;
pub const BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL: bg_unit_system = 1;

pub type bg_direct_ewald_error_code = i32;
pub const BG_DIRECT_EWALD_ERROR_NONE: bg_direct_ewald_error_code = 0;
pub const BG_DIRECT_EWALD_ERROR_EMPTY_SYSTEM: bg_direct_ewald_error_code = 1;
pub const BG_DIRECT_EWALD_ERROR_CAPACITY_EXCEEDED: bg_direct_ewald_error_code = 2;
pub const BG_DIRECT_EWALD_ERROR_CHARGE_COUNT_MISMATCH: bg_direct_ewald_error_code = 3;
pub const BG_DIRECT_EWALD_ERROR_NONFINITE_COORDINATE: bg_direct_ewald_error_code = 4;
pub const BG_DIRECT_EWALD_ERROR_NONFINITE_CHARGE: bg_direct_ewald_error_code = 5;
pub const BG_DIRECT_EWALD_ERROR_NON_NEUTRAL_SYSTEM: bg_direct_ewald_error_code = 6;
pub const BG_DIRECT_EWALD_ERROR_INVALID_CELL: bg_direct_ewald_error_code = 7;
pub const BG_DIRECT_EWALD_ERROR_CUTOFF_VIOLATES_MINIMUM_IMAGE: bg_direct_ewald_error_code = 8;
pub const BG_DIRECT_EWALD_ERROR_INVALID_PARAMETER: bg_direct_ewald_error_code = 9;
pub const BG_DIRECT_EWALD_ERROR_ATOM_INDEX_OUT_OF_RANGE: bg_direct_ewald_error_code = 10;
pub const BG_DIRECT_EWALD_ERROR_REPEATED_ATOM_INDEX: bg_direct_ewald_error_code = 11;
pub const BG_DIRECT_EWALD_ERROR_DUPLICATE_PAIR_RULE: bg_direct_ewald_error_code = 12;
pub const BG_DIRECT_EWALD_ERROR_CONFLICTING_PAIR_RULE: bg_direct_ewald_error_code = 13;
pub const BG_DIRECT_EWALD_ERROR_AMBIGUOUS_PAIR_CORRECTION_IMAGE: bg_direct_ewald_error_code = 14;
pub const BG_DIRECT_EWALD_ERROR_AMBIGUOUS_REAL_SPACE_CUTOFF: bg_direct_ewald_error_code = 15;
pub const BG_DIRECT_EWALD_ERROR_AMBIGUOUS_MINIMUM_PAIR_DISTANCE: bg_direct_ewald_error_code = 16;
pub const BG_DIRECT_EWALD_ERROR_PAIR_BELOW_MINIMUM_DISTANCE: bg_direct_ewald_error_code = 17;
pub const BG_DIRECT_EWALD_ERROR_DAMPING_UNDERFLOW: bg_direct_ewald_error_code = 18;
pub const BG_DIRECT_EWALD_ERROR_PHASE_UNDERFLOW: bg_direct_ewald_error_code = 19;
pub const BG_DIRECT_EWALD_ERROR_NONFINITE_RESULT: bg_direct_ewald_error_code = 20;

pub type bg_particle_mesh_reciprocal_error_code = i32;
pub const BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONE: bg_particle_mesh_reciprocal_error_code = 0;
pub const BG_PARTICLE_MESH_RECIPROCAL_ERROR_EMPTY_SYSTEM: bg_particle_mesh_reciprocal_error_code =
    1;
pub const BG_PARTICLE_MESH_RECIPROCAL_ERROR_CAPACITY_EXCEEDED:
    bg_particle_mesh_reciprocal_error_code = 2;
pub const BG_PARTICLE_MESH_RECIPROCAL_ERROR_CHARGE_COUNT_MISMATCH:
    bg_particle_mesh_reciprocal_error_code = 3;
pub const BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONFINITE_COORDINATE:
    bg_particle_mesh_reciprocal_error_code = 4;
pub const BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONFINITE_CHARGE:
    bg_particle_mesh_reciprocal_error_code = 5;
pub const BG_PARTICLE_MESH_RECIPROCAL_ERROR_NON_NEUTRAL_SYSTEM:
    bg_particle_mesh_reciprocal_error_code = 6;
pub const BG_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_CELL: bg_particle_mesh_reciprocal_error_code =
    7;
pub const BG_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_PARAMETER:
    bg_particle_mesh_reciprocal_error_code = 8;
pub const BG_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_MESH: bg_particle_mesh_reciprocal_error_code =
    9;
pub const BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONFINITE_RESULT:
    bg_particle_mesh_reciprocal_error_code = 10;

pub type bg_integrator = i32;
pub const BG_INTEGRATOR_VELOCITY_VERLET: bg_integrator = 1;
pub const BG_INTEGRATOR_LANGEVIN_BAOAB: bg_integrator = 2;

pub const BG_DOCKING_FIXED64_CANDIDATE_COUNT: u32 = 64;
pub const BG_DOCKING_SCORER_V1_TERM_COUNT: u32 = 8;
pub const BG_DOCKING_STABLE_TOP_K_LIMIT: u32 = 5;
pub const BG_DOCKING_RMSD_CLUSTER_TOP_K_LIMIT: u32 = 5;
pub const BG_DOCKING_TORSION_V7_MAX_MOVES: u32 = 8;
pub const BG_DOCKING_FIXED64_FEATURE_KIND_COUNT: u32 = 12;
pub const BG_DOCKING_FIXED64_MAX_REQUIREMENTS: u32 = 2;
pub const BG_DOCKING_FIXED64_MAX_MISSING_FEATURES: u32 = 2;
pub const BG_DOCKING_FIXED64_MAX_SELECTED_SOURCE_RECEIPTS: u32 = 2;
pub const BG_DOCKING_FIXED64_SO3_ORIENTATION_COUNT: u32 = 64;

pub type bg_docking_fixed64_lane = i32;
pub const BG_DOCKING_FIXED64_LANE_POCKET_CENTERED_CONTROLS: bg_docking_fixed64_lane = 0;
pub const BG_DOCKING_FIXED64_LANE_UNIFORM_SOURCE_CONTROLS: bg_docking_fixed64_lane = 1;
pub const BG_DOCKING_FIXED64_LANE_DETERMINISTIC_INDEPENDENT_SO3: bg_docking_fixed64_lane = 2;
pub const BG_DOCKING_FIXED64_LANE_TRUE_CONFORMER_INDEPENDENT_SO3: bg_docking_fixed64_lane = 3;
pub const BG_DOCKING_FIXED64_LANE_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR: bg_docking_fixed64_lane = 4;
pub const BG_DOCKING_FIXED64_LANE_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR: bg_docking_fixed64_lane = 5;
pub const BG_DOCKING_FIXED64_LANE_COMPLEMENTARY_CHARGE: bg_docking_fixed64_lane = 6;
pub const BG_DOCKING_FIXED64_LANE_AROMATIC_PLANE: bg_docking_fixed64_lane = 7;
pub const BG_DOCKING_FIXED64_LANE_PRINCIPAL_AXIS_SHAPE: bg_docking_fixed64_lane = 8;
pub const BG_DOCKING_FIXED64_LANE_PAIRED_RETAINED_CONTROLS: bg_docking_fixed64_lane = 9;

pub type bg_docking_fixed64_feature_kind = i32;
pub const BG_DOCKING_FIXED64_FEATURE_LIGAND_DONOR: bg_docking_fixed64_feature_kind = 0;
pub const BG_DOCKING_FIXED64_FEATURE_LIGAND_ACCEPTOR: bg_docking_fixed64_feature_kind = 1;
pub const BG_DOCKING_FIXED64_FEATURE_RECEPTOR_DONOR: bg_docking_fixed64_feature_kind = 2;
pub const BG_DOCKING_FIXED64_FEATURE_RECEPTOR_ACCEPTOR: bg_docking_fixed64_feature_kind = 3;
pub const BG_DOCKING_FIXED64_FEATURE_LIGAND_POSITIVE_SITE: bg_docking_fixed64_feature_kind = 4;
pub const BG_DOCKING_FIXED64_FEATURE_LIGAND_NEGATIVE_SITE: bg_docking_fixed64_feature_kind = 5;
pub const BG_DOCKING_FIXED64_FEATURE_RECEPTOR_POSITIVE_SITE: bg_docking_fixed64_feature_kind = 6;
pub const BG_DOCKING_FIXED64_FEATURE_RECEPTOR_NEGATIVE_SITE: bg_docking_fixed64_feature_kind = 7;
pub const BG_DOCKING_FIXED64_FEATURE_LIGAND_AROMATIC_PLANE: bg_docking_fixed64_feature_kind = 8;
pub const BG_DOCKING_FIXED64_FEATURE_RECEPTOR_AROMATIC_PLANE: bg_docking_fixed64_feature_kind = 9;
pub const BG_DOCKING_FIXED64_FEATURE_LIGAND_SHAPE_AXIS: bg_docking_fixed64_feature_kind = 10;
pub const BG_DOCKING_FIXED64_FEATURE_POCKET_SHAPE_AXIS: bg_docking_fixed64_feature_kind = 11;

pub type bg_docking_fixed64_anchor_kind = i32;
pub const BG_DOCKING_FIXED64_ANCHOR_NONE: bg_docking_fixed64_anchor_kind = 0;
pub const BG_DOCKING_FIXED64_ANCHOR_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR:
    bg_docking_fixed64_anchor_kind = 1;
pub const BG_DOCKING_FIXED64_ANCHOR_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR:
    bg_docking_fixed64_anchor_kind = 2;
pub const BG_DOCKING_FIXED64_ANCHOR_COMPLEMENTARY_CHARGE: bg_docking_fixed64_anchor_kind = 3;
pub const BG_DOCKING_FIXED64_ANCHOR_AROMATIC_PLANE: bg_docking_fixed64_anchor_kind = 4;
pub const BG_DOCKING_FIXED64_ANCHOR_PRINCIPAL_AXIS_SHAPE: bg_docking_fixed64_anchor_kind = 5;

pub type bg_docking_fixed64_parent_role = i32;
pub const BG_DOCKING_FIXED64_PARENT_NONE: bg_docking_fixed64_parent_role = 0;
pub const BG_DOCKING_FIXED64_PARENT_EXACT_PASSTHROUGH: bg_docking_fixed64_parent_role = 1;
pub const BG_DOCKING_FIXED64_PARENT_GENERATOR_INPUT: bg_docking_fixed64_parent_role = 2;

pub type bg_docking_fixed64_requirement_kind = i32;
pub const BG_DOCKING_FIXED64_REQUIREMENT_V7_CONTROL_SOURCE: bg_docking_fixed64_requirement_kind = 0;
pub const BG_DOCKING_FIXED64_REQUIREMENT_TRUE_CONFORMER_RANK: bg_docking_fixed64_requirement_kind =
    1;
pub const BG_DOCKING_FIXED64_REQUIREMENT_FEATURE: bg_docking_fixed64_requirement_kind = 2;
pub const BG_DOCKING_FIXED64_REQUIREMENT_COMPLEMENTARY_CHARGE_ANCHOR:
    bg_docking_fixed64_requirement_kind = 3;
pub const BG_DOCKING_FIXED64_REQUIREMENT_RETAINED_SOURCE: bg_docking_fixed64_requirement_kind = 4;

pub type bg_docking_fixed64_missing_feature_kind = i32;
pub const BG_DOCKING_FIXED64_MISSING_V7_CONTROL_SOURCE: bg_docking_fixed64_missing_feature_kind = 0;
pub const BG_DOCKING_FIXED64_MISSING_TRUE_CONFORMER: bg_docking_fixed64_missing_feature_kind = 1;
pub const BG_DOCKING_FIXED64_MISSING_LIGAND_DONOR: bg_docking_fixed64_missing_feature_kind = 2;
pub const BG_DOCKING_FIXED64_MISSING_RECEPTOR_ACCEPTOR: bg_docking_fixed64_missing_feature_kind = 3;
pub const BG_DOCKING_FIXED64_MISSING_LIGAND_ACCEPTOR: bg_docking_fixed64_missing_feature_kind = 4;
pub const BG_DOCKING_FIXED64_MISSING_RECEPTOR_DONOR: bg_docking_fixed64_missing_feature_kind = 5;
pub const BG_DOCKING_FIXED64_MISSING_COMPLEMENTARY_CHARGE_ANCHOR:
    bg_docking_fixed64_missing_feature_kind = 6;
pub const BG_DOCKING_FIXED64_MISSING_LIGAND_AROMATIC_PLANE:
    bg_docking_fixed64_missing_feature_kind = 7;
pub const BG_DOCKING_FIXED64_MISSING_RECEPTOR_AROMATIC_PLANE:
    bg_docking_fixed64_missing_feature_kind = 8;
pub const BG_DOCKING_FIXED64_MISSING_LIGAND_SHAPE_AXIS: bg_docking_fixed64_missing_feature_kind = 9;
pub const BG_DOCKING_FIXED64_MISSING_POCKET_SHAPE_AXIS: bg_docking_fixed64_missing_feature_kind =
    10;
pub const BG_DOCKING_FIXED64_MISSING_RETAINED_SOURCE: bg_docking_fixed64_missing_feature_kind = 11;

pub type bg_docking_fixed64_allocation_row_status = i32;
pub const BG_DOCKING_FIXED64_ALLOCATION_ROW_READY: bg_docking_fixed64_allocation_row_status = 1;
pub const BG_DOCKING_FIXED64_ALLOCATION_ROW_TYPED_FAILURE:
    bg_docking_fixed64_allocation_row_status = 2;

pub type bg_docking_fixed64_so3_row_status = i32;
pub const BG_DOCKING_FIXED64_SO3_ROW_GENERATED: bg_docking_fixed64_so3_row_status = 1;
pub const BG_DOCKING_FIXED64_SO3_ROW_TYPED_FAILURE: bg_docking_fixed64_so3_row_status = 2;
pub type bg_docking_fixed64_so3_failure = i32;
pub const BG_DOCKING_FIXED64_SO3_FAILURE_NONE: bg_docking_fixed64_so3_failure = 0;
pub const BG_DOCKING_FIXED64_SO3_FAILURE_SEQUENCE_EXHAUSTED: bg_docking_fixed64_so3_failure = 1;
pub const BG_DOCKING_FIXED64_SO3_FAILURE_NONFINITE_QUATERNION: bg_docking_fixed64_so3_failure = 2;

pub type bg_docking_fixed64_indexed_so3_status = i32;
pub const BG_DOCKING_FIXED64_INDEXED_SO3_PLACED: bg_docking_fixed64_indexed_so3_status = 1;
pub const BG_DOCKING_FIXED64_INDEXED_SO3_TYPED_FAILURE: bg_docking_fixed64_indexed_so3_status = 2;
pub type bg_docking_fixed64_indexed_so3_failure = i32;
pub const BG_DOCKING_FIXED64_INDEXED_SO3_FAILURE_NONE: bg_docking_fixed64_indexed_so3_failure = 0;
pub const BG_DOCKING_FIXED64_INDEXED_SO3_FAILURE_DEGENERATE_SOURCE_GEOMETRY:
    bg_docking_fixed64_indexed_so3_failure = 1;
pub const BG_DOCKING_FIXED64_INDEXED_SO3_FAILURE_NONFINITE_OUTPUT:
    bg_docking_fixed64_indexed_so3_failure = 2;

pub type bg_docking_fixed64_single_anchor_status = i32;
pub const BG_DOCKING_FIXED64_SINGLE_ANCHOR_PLACED: bg_docking_fixed64_single_anchor_status = 1;
pub const BG_DOCKING_FIXED64_SINGLE_ANCHOR_TYPED_FAILURE: bg_docking_fixed64_single_anchor_status =
    2;
pub type bg_docking_fixed64_single_anchor_failure = i32;
pub const BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_NONE: bg_docking_fixed64_single_anchor_failure =
    0;
pub const BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_LIGAND_DIRECTION:
    bg_docking_fixed64_single_anchor_failure = 1;
pub const BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_RECEPTOR_DIRECTION:
    bg_docking_fixed64_single_anchor_failure = 2;
pub const BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_LOCAL_SURFACE_NORMAL:
    bg_docking_fixed64_single_anchor_failure = 3;
pub const BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_AROMATIC_PLANE:
    bg_docking_fixed64_single_anchor_failure = 4;
pub const BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_PRINCIPAL_AXIS:
    bg_docking_fixed64_single_anchor_failure = 5;
pub const BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_NONFINITE_OUTPUT:
    bg_docking_fixed64_single_anchor_failure = 6;

pub type bg_docking_fixed64_producer_row_status = i32;
pub const BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED: bg_docking_fixed64_producer_row_status = 1;
pub const BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE: bg_docking_fixed64_producer_row_status = 2;
pub type bg_docking_fixed64_producer_failure = i32;
pub const BG_DOCKING_FIXED64_PRODUCER_FAILURE_NONE: bg_docking_fixed64_producer_failure = 0;
pub const BG_DOCKING_FIXED64_PRODUCER_FAILURE_ALLOCATION_INELIGIBLE:
    bg_docking_fixed64_producer_failure = 1;
pub const BG_DOCKING_FIXED64_PRODUCER_FAILURE_SOURCE_NOT_AVAILABLE:
    bg_docking_fixed64_producer_failure = 2;
pub const BG_DOCKING_FIXED64_PRODUCER_FAILURE_LIGAND_DENOMINATOR_MISMATCH:
    bg_docking_fixed64_producer_failure = 3;
pub const BG_DOCKING_FIXED64_PRODUCER_FAILURE_FEATURE_GEOMETRY_NOT_AVAILABLE:
    bg_docking_fixed64_producer_failure = 4;
pub const BG_DOCKING_FIXED64_PRODUCER_FAILURE_INDEXED_SO3_TYPED_FAILURE:
    bg_docking_fixed64_producer_failure = 5;
pub const BG_DOCKING_FIXED64_PRODUCER_FAILURE_SINGLE_ANCHOR_TYPED_FAILURE:
    bg_docking_fixed64_producer_failure = 6;
pub type bg_docking_fixed64_producer_placement_kind = i32;
pub const BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_NONE: bg_docking_fixed64_producer_placement_kind =
    0;
pub const BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_EXACT_PASSTHROUGH:
    bg_docking_fixed64_producer_placement_kind = 1;
pub const BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_INDEXED_SO3:
    bg_docking_fixed64_producer_placement_kind = 2;
pub const BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_SINGLE_ANCHOR:
    bg_docking_fixed64_producer_placement_kind = 3;

pub type bg_docking_geometric_admission_candidate_state = i32;
pub const BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_UPSTREAM_FAILURE:
    bg_docking_geometric_admission_candidate_state = 0;
pub const BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_EVALUATE:
    bg_docking_geometric_admission_candidate_state = 1;
pub type bg_docking_geometric_admission_row_status = i32;
pub const BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED: bg_docking_geometric_admission_row_status =
    1;
pub const BG_DOCKING_GEOMETRIC_ADMISSION_ROW_UPSTREAM_FAILURE:
    bg_docking_geometric_admission_row_status = 2;
pub const BG_DOCKING_GEOMETRIC_ADMISSION_ROW_TYPED_FAILURE:
    bg_docking_geometric_admission_row_status = 3;
pub type bg_docking_geometric_admission_failure = i32;
pub const BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_NONE: bg_docking_geometric_admission_failure = 0;
pub const BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_UPSTREAM_NOT_AVAILABLE:
    bg_docking_geometric_admission_failure = 1;
pub const BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_INVALID_CANDIDATE_COORDINATES:
    bg_docking_geometric_admission_failure = 2;
pub const BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_NONFINITE_DERIVED_MEASUREMENT:
    bg_docking_geometric_admission_failure = 3;
pub type bg_docking_geometric_admission_decision = i32;
pub const BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_NOT_EVALUATED:
    bg_docking_geometric_admission_decision = 0;
pub const BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED:
    bg_docking_geometric_admission_decision = 1;
pub const BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_SEVERE_PENETRATION_REJECTED:
    bg_docking_geometric_admission_decision = 2;

pub type bg_docking_scorer_v1_candidate_state = i32;
pub const BG_DOCKING_SCORER_V1_CANDIDATE_INACTIVE: bg_docking_scorer_v1_candidate_state = 0;
pub const BG_DOCKING_SCORER_V1_CANDIDATE_ACTIVE: bg_docking_scorer_v1_candidate_state = 1;

pub type bg_docking_scorer_v1_row_status = i32;
pub const BG_DOCKING_SCORER_V1_ROW_SCORED: bg_docking_scorer_v1_row_status = 1;
pub const BG_DOCKING_SCORER_V1_ROW_TYPED_FAILURE: bg_docking_scorer_v1_row_status = 2;

pub type bg_docking_scorer_v1_failure = i32;
pub const BG_DOCKING_SCORER_V1_FAILURE_NONE: bg_docking_scorer_v1_failure = 0;
pub const BG_DOCKING_SCORER_V1_FAILURE_UPSTREAM_NOT_ADMITTED: bg_docking_scorer_v1_failure = 1;
pub const BG_DOCKING_SCORER_V1_FAILURE_INVALID_CANDIDATE_COORDINATES: bg_docking_scorer_v1_failure =
    2;
pub const BG_DOCKING_SCORER_V1_FAILURE_RECEPTOR_PAIR_CAPACITY: bg_docking_scorer_v1_failure = 3;
pub const BG_DOCKING_SCORER_V1_FAILURE_LIGAND_PAIR_CAPACITY: bg_docking_scorer_v1_failure = 4;
pub const BG_DOCKING_SCORER_V1_FAILURE_DEGENERATE_ROTOR: bg_docking_scorer_v1_failure = 5;
pub const BG_DOCKING_SCORER_V1_FAILURE_NONFINITE_SCORE: bg_docking_scorer_v1_failure = 6;

pub const BG_DOCKING_POSE_VALIDITY_CHECK_COUNT: u32 = 8;
pub type bg_docking_pose_validity_candidate_state = i32;
pub const BG_DOCKING_POSE_VALIDITY_CANDIDATE_UPSTREAM_FAILURE:
    bg_docking_pose_validity_candidate_state = 0;
pub const BG_DOCKING_POSE_VALIDITY_CANDIDATE_EVALUATE: bg_docking_pose_validity_candidate_state = 1;
pub type bg_docking_pose_validity_row_status = i32;
pub const BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED: bg_docking_pose_validity_row_status = 1;
pub const BG_DOCKING_POSE_VALIDITY_ROW_UPSTREAM_SCORER_FAILURE:
    bg_docking_pose_validity_row_status = 2;
pub const BG_DOCKING_POSE_VALIDITY_ROW_TYPED_FAILURE: bg_docking_pose_validity_row_status = 3;
pub type bg_docking_pose_validity_failure = i32;
pub const BG_DOCKING_POSE_VALIDITY_FAILURE_NONE: bg_docking_pose_validity_failure = 0;
pub const BG_DOCKING_POSE_VALIDITY_FAILURE_UPSTREAM_SCORER: bg_docking_pose_validity_failure = 1;
pub const BG_DOCKING_POSE_VALIDITY_FAILURE_INVALID_CANDIDATE_COORDINATES:
    bg_docking_pose_validity_failure = 2;
pub const BG_DOCKING_POSE_VALIDITY_FAILURE_LIGAND_PAIR_CAPACITY: bg_docking_pose_validity_failure =
    3;
pub const BG_DOCKING_POSE_VALIDITY_FAILURE_RECEPTOR_CROSS_CAPACITY:
    bg_docking_pose_validity_failure = 4;
pub const BG_DOCKING_POSE_VALIDITY_FAILURE_ELEMENT_LIGAND_PAIR_CAPACITY:
    bg_docking_pose_validity_failure = 5;
pub const BG_DOCKING_POSE_VALIDITY_FAILURE_ELEMENT_RECEPTOR_CANDIDATE_CAPACITY:
    bg_docking_pose_validity_failure = 6;
pub const BG_DOCKING_POSE_VALIDITY_FAILURE_NONFINITE_DERIVED_MEASUREMENT:
    bg_docking_pose_validity_failure = 7;
pub type bg_docking_pose_validity_check_mask = u32;
pub const BG_DOCKING_POSE_VALIDITY_CHECK_PROPER_ROTATION: bg_docking_pose_validity_check_mask =
    1 << 0;
pub const BG_DOCKING_POSE_VALIDITY_CHECK_BOND_LENGTHS: bg_docking_pose_validity_check_mask = 1 << 1;
pub const BG_DOCKING_POSE_VALIDITY_CHECK_LIGAND_SELF_CLASH: bg_docking_pose_validity_check_mask =
    1 << 2;
pub const BG_DOCKING_POSE_VALIDITY_CHECK_RECEPTOR_LIGAND_CLASH:
    bg_docking_pose_validity_check_mask = 1 << 3;
pub const BG_DOCKING_POSE_VALIDITY_CHECK_CHIRALITY: bg_docking_pose_validity_check_mask = 1 << 4;
pub const BG_DOCKING_POSE_VALIDITY_CHECK_DECLARED_POCKET: bg_docking_pose_validity_check_mask =
    1 << 5;
pub const BG_DOCKING_POSE_VALIDITY_CHECK_ELEMENT_LIGAND_VDW: bg_docking_pose_validity_check_mask =
    1 << 6;
pub const BG_DOCKING_POSE_VALIDITY_CHECK_ELEMENT_RECEPTOR_VDW: bg_docking_pose_validity_check_mask =
    1 << 7;
pub const BG_DOCKING_POSE_VALIDITY_CHECK_ALL: bg_docking_pose_validity_check_mask = 0xff;

pub type bg_docking_rmsd_cluster_row_status = i32;
pub const BG_DOCKING_RMSD_CLUSTER_ROW_CLUSTERED: bg_docking_rmsd_cluster_row_status = 1;
pub const BG_DOCKING_RMSD_CLUSTER_ROW_UPSTREAM_NOT_VALID: bg_docking_rmsd_cluster_row_status = 2;

pub type bg_docking_torsion_v7_candidate_state = i32;
pub const BG_DOCKING_TORSION_V7_CANDIDATE_INACTIVE: bg_docking_torsion_v7_candidate_state = 0;
pub const BG_DOCKING_TORSION_V7_CANDIDATE_REFINE: bg_docking_torsion_v7_candidate_state = 1;

pub type bg_docking_torsion_v7_row_status = i32;
pub const BG_DOCKING_TORSION_V7_ROW_REFINED: bg_docking_torsion_v7_row_status = 1;
pub const BG_DOCKING_TORSION_V7_ROW_TYPED_FAILURE: bg_docking_torsion_v7_row_status = 2;

pub type bg_docking_torsion_v7_failure = i32;
pub const BG_DOCKING_TORSION_V7_FAILURE_NONE: bg_docking_torsion_v7_failure = 0;
pub const BG_DOCKING_TORSION_V7_FAILURE_UPSTREAM_NOT_ELIGIBLE: bg_docking_torsion_v7_failure = 1;
pub const BG_DOCKING_TORSION_V7_FAILURE_INVALID_INPUT: bg_docking_torsion_v7_failure = 2;
pub const BG_DOCKING_TORSION_V7_FAILURE_PAIR_BUDGET: bg_docking_torsion_v7_failure = 3;
pub const BG_DOCKING_TORSION_V7_FAILURE_DEGENERATE_ROTOR: bg_docking_torsion_v7_failure = 4;
pub const BG_DOCKING_TORSION_V7_FAILURE_NONFINITE_DERIVED_VALUE: bg_docking_torsion_v7_failure = 5;

pub type bg_docking_torsion_v7_skip_reason = i32;
pub const BG_DOCKING_TORSION_V7_SKIP_NONE: bg_docking_torsion_v7_skip_reason = 0;
pub const BG_DOCKING_TORSION_V7_SKIP_NOT_ELIGIBLE: bg_docking_torsion_v7_skip_reason = 1;
pub const BG_DOCKING_TORSION_V7_SKIP_NO_AUTHORITY_ROTOR: bg_docking_torsion_v7_skip_reason = 2;
pub const BG_DOCKING_TORSION_V7_SKIP_NO_REMAINING_STEP_BUDGET: bg_docking_torsion_v7_skip_reason =
    3;
pub const BG_DOCKING_TORSION_V7_SKIP_OBJECTIVE_AT_OR_BELOW_TOLERANCE:
    bg_docking_torsion_v7_skip_reason = 4;
pub const BG_DOCKING_TORSION_V7_SKIP_SELECTION_WINDOW_UNREACHABLE:
    bg_docking_torsion_v7_skip_reason = 5;

pub type bg_docking_torsion_v7_selection_reason = i32;
pub const BG_DOCKING_TORSION_V7_SELECTION_FINAL_PENALTY_WINDOW:
    bg_docking_torsion_v7_selection_reason = 1;
pub const BG_DOCKING_TORSION_V7_SELECTION_V6_RETAINED_OUTSIDE_WINDOW:
    bg_docking_torsion_v7_selection_reason = 2;
pub const BG_DOCKING_TORSION_V7_SELECTION_V6_RETAINED_NO_REDUCTION:
    bg_docking_torsion_v7_selection_reason = 3;

pub type bg_docking_rigid_refinement_candidate_mode = i32;
pub const BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_INACTIVE:
    bg_docking_rigid_refinement_candidate_mode = 0;
pub const BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION:
    bg_docking_rigid_refinement_candidate_mode = 1;
pub const BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V3_TRANSLATION_ROTATION:
    bg_docking_rigid_refinement_candidate_mode = 2;
pub const BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V2_LANE:
    bg_docking_rigid_refinement_candidate_mode = 3;
pub const BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V3_LANE:
    bg_docking_rigid_refinement_candidate_mode = 4;

pub type bg_docking_rigid_refinement_row_status = i32;
pub const BG_DOCKING_RIGID_REFINEMENT_ROW_REFINED: bg_docking_rigid_refinement_row_status = 1;
pub const BG_DOCKING_RIGID_REFINEMENT_ROW_TYPED_FAILURE: bg_docking_rigid_refinement_row_status = 2;

pub type bg_docking_rigid_refinement_failure = i32;
pub const BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE: bg_docking_rigid_refinement_failure = 0;
pub const BG_DOCKING_RIGID_REFINEMENT_FAILURE_UPSTREAM_NOT_ELIGIBLE:
    bg_docking_rigid_refinement_failure = 1;
pub const BG_DOCKING_RIGID_REFINEMENT_FAILURE_INVALID_INPUT: bg_docking_rigid_refinement_failure =
    2;
pub const BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONFINITE_INPUT: bg_docking_rigid_refinement_failure =
    3;
pub const BG_DOCKING_RIGID_REFINEMENT_FAILURE_PAIR_BUDGET: bg_docking_rigid_refinement_failure = 4;
pub const BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONFINITE_DERIVED_VALUE:
    bg_docking_rigid_refinement_failure = 5;

pub type bg_docking_rigid_refinement_profile = i32;
pub const BG_DOCKING_RIGID_REFINEMENT_PROFILE_NONE: bg_docking_rigid_refinement_profile = 0;
pub const BG_DOCKING_RIGID_REFINEMENT_PROFILE_V2_TRANSLATION: bg_docking_rigid_refinement_profile =
    1;
pub const BG_DOCKING_RIGID_REFINEMENT_PROFILE_V3_TRANSLATION_ROTATION:
    bg_docking_rigid_refinement_profile = 2;
pub const BG_DOCKING_RIGID_REFINEMENT_PROFILE_V6_BASELINE_V2: bg_docking_rigid_refinement_profile =
    3;
pub const BG_DOCKING_RIGID_REFINEMENT_PROFILE_V6_BASELINE_V3: bg_docking_rigid_refinement_profile =
    4;
pub const BG_DOCKING_RIGID_REFINEMENT_PROFILE_V6_CLEARANCE_V4: bg_docking_rigid_refinement_profile =
    5;

pub type bg_docking_fixed64_refinement_row_status = i32;
pub const BG_DOCKING_FIXED64_REFINEMENT_ROW_COORDINATE_READY:
    bg_docking_fixed64_refinement_row_status = 1;
pub const BG_DOCKING_FIXED64_REFINEMENT_ROW_TYPED_FAILURE:
    bg_docking_fixed64_refinement_row_status = 2;

pub type bg_docking_fixed64_refinement_failure_stage = i32;
pub const BG_DOCKING_FIXED64_REFINEMENT_FAILURE_STAGE_NONE:
    bg_docking_fixed64_refinement_failure_stage = 0;
pub const BG_DOCKING_FIXED64_REFINEMENT_FAILURE_STAGE_RIGID:
    bg_docking_fixed64_refinement_failure_stage = 1;
pub const BG_DOCKING_FIXED64_REFINEMENT_FAILURE_STAGE_TORSION_V7:
    bg_docking_fixed64_refinement_failure_stage = 2;

pub type bg_docking_fixed64_refinement_coordinate_origin = i32;
pub const BG_DOCKING_FIXED64_REFINEMENT_COORDINATE_NONE:
    bg_docking_fixed64_refinement_coordinate_origin = 0;
pub const BG_DOCKING_FIXED64_REFINEMENT_COORDINATE_RIGID_SELECTED:
    bg_docking_fixed64_refinement_coordinate_origin = 1;
pub const BG_DOCKING_FIXED64_REFINEMENT_COORDINATE_TORSION_V7_FINAL:
    bg_docking_fixed64_refinement_coordinate_origin = 2;

/// Opaque native context. Its representation is intentionally unavailable.
#[repr(C)]
pub struct bg_context {
    _private: [u8; 0],
}

/// Opaque native particle system. Its representation is intentionally unavailable.
#[repr(C)]
pub struct bg_system {
    _private: [u8; 0],
}

/// Opaque native force field. Its representation is intentionally unavailable.
#[repr(C)]
pub struct bg_forcefield {
    _private: [u8; 0],
}

/// Opaque immutable direct-Ewald model.
#[repr(C)]
pub struct bg_direct_ewald_model_v1 {
    _private: [u8; 0],
}

/// Opaque immutable particle-mesh reciprocal model.
#[repr(C)]
pub struct bg_particle_mesh_reciprocal_model_v1 {
    _private: [u8; 0],
}

/// Opaque deep-owned short-range + direct-Ewald dynamics simulation.
#[repr(C)]
pub struct bg_direct_ewald_composite_simulation_v1 {
    _private: [u8; 0],
}

/// Opaque native simulation. Its representation is intentionally unavailable.
#[repr(C)]
pub struct bg_simulation {
    _private: [u8; 0],
}

/// Opaque persistent fixed64 geometric-admission provider.
#[repr(C)]
pub struct bg_docking_geometric_admission_v1 {
    _private: [u8; 0],
}

/// Opaque persistent Engine V2 ScorerV1 context.
#[repr(C)]
pub struct bg_docking_scorer_v1 {
    _private: [u8; 0],
}

/// Opaque persistent Engine V2 pose-validity context.
#[repr(C)]
pub struct bg_docking_pose_validity_v1 {
    _private: [u8; 0],
}

/// Opaque persistent Engine V2 stable Top-K provider.
#[repr(C)]
pub struct bg_docking_stable_top_k_v1 {
    _private: [u8; 0],
}

/// Opaque persistent fixed64 score-validity-ranking pipeline.
#[repr(C)]
pub struct bg_docking_fixed64_downstream_v1 {
    _private: [u8; 0],
}

/// Opaque persistent fixed64 refinement-to-ranking pipeline.
#[repr(C)]
pub struct bg_docking_fixed64_refinement_pipeline_v1 {
    _private: [u8; 0],
}

/// Opaque persistent fixed64 proposal-to-clustering pipeline.
#[repr(C)]
pub struct bg_docking_fixed64_pipeline_v1 {
    _private: [u8; 0],
}

/// Opaque persistent fixed64 proposal-to-post-admission pipeline.
#[repr(C)]
pub struct bg_docking_fixed64_pipeline_v2 {
    _private: [u8; 0],
}

/// Opaque persistent interaction-aware V2/V3/V6 rigid-refinement provider.
#[repr(C)]
pub struct bg_docking_rigid_refinement {
    _private: [u8; 0],
}

/// Opaque persistent interaction-aware torsion/contact V7 provider.
#[repr(C)]
pub struct bg_docking_torsion_v7 {
    _private: [u8; 0],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_context_options {
    pub struct_size: u32,
    pub abi_version: u32,
    pub backend: bg_backend,
    pub unit_system: bg_unit_system,
    pub device_ordinal: i32,
    pub reserved0: u32,
    pub flags: u64,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_particle_soa {
    pub struct_size: u32,
    pub abi_version: u32,
    pub particle_count: u64,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub position_x_angstrom: *const f64,
    pub position_y_angstrom: *const f64,
    pub position_z_angstrom: *const f64,
    pub velocity_x_angstrom_per_femtosecond: *const f64,
    pub velocity_y_angstrom_per_femtosecond: *const f64,
    pub velocity_z_angstrom_per_femtosecond: *const f64,
    pub mass_dalton: *const f64,
    pub charge_elementary: *const f64,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_particle_soa_view {
    pub struct_size: u32,
    pub abi_version: u32,
    pub particle_count: u64,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub position_x_angstrom: *const f64,
    pub position_y_angstrom: *const f64,
    pub position_z_angstrom: *const f64,
    pub velocity_x_angstrom_per_femtosecond: *const f64,
    pub velocity_y_angstrom_per_femtosecond: *const f64,
    pub velocity_z_angstrom_per_femtosecond: *const f64,
    pub mass_dalton: *const f64,
    pub charge_elementary: *const f64,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_position_soa {
    pub struct_size: u32,
    pub abi_version: u32,
    pub particle_count: u64,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub x_angstrom: *const f64,
    pub y_angstrom: *const f64,
    pub z_angstrom: *const f64,
    pub reserved: [u64; 4],
}

pub const BG_PERIODIC_AXIS_X: u32 = 1 << 0;
pub const BG_PERIODIC_AXIS_Y: u32 = 1 << 1;
pub const BG_PERIODIC_AXIS_Z: u32 = 1 << 2;
pub const BG_PERIODIC_AXES_ALL: u32 = BG_PERIODIC_AXIS_X | BG_PERIODIC_AXIS_Y | BG_PERIODIC_AXIS_Z;

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_forcefield_soa_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub atom_count: u64,
    pub unit_system: bg_unit_system,
    pub periodic_axes_mask: u32,
    pub sigma_angstrom: *const f64,
    pub epsilon_kcal_per_mol: *const f64,
    pub bond_count: u64,
    pub bond_atom_i: *const u64,
    pub bond_atom_j: *const u64,
    pub bond_equilibrium_angstrom: *const f64,
    pub bond_force_constant_kcal_per_mol_angstrom2: *const f64,
    pub angle_count: u64,
    pub angle_atom_i: *const u64,
    pub angle_atom_j: *const u64,
    pub angle_atom_k: *const u64,
    pub angle_equilibrium_radians: *const f64,
    pub angle_force_constant_kcal_per_mol_radian2: *const f64,
    pub torsion_count: u64,
    pub torsion_atom_i: *const u64,
    pub torsion_atom_j: *const u64,
    pub torsion_atom_k: *const u64,
    pub torsion_atom_l: *const u64,
    pub torsion_periodicity: *const u32,
    pub torsion_phase_radians: *const f64,
    pub torsion_amplitude_kcal_per_mol: *const f64,
    pub exclusion_count: u64,
    pub exclusion_atom_i: *const u64,
    pub exclusion_atom_j: *const u64,
    pub pair_scale_count: u64,
    pub pair_scale_atom_i: *const u64,
    pub pair_scale_atom_j: *const u64,
    pub pair_scale_lennard_jones: *const f64,
    pub pair_scale_coulomb: *const f64,
    pub cell_lengths_angstrom: [f64; 3],
    pub cutoff_angstrom: f64,
    pub switch_start_angstrom: f64,
    pub dielectric: f64,
    pub screening_kappa_per_angstrom: f64,
    pub minimum_pair_distance_angstrom: f64,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_force_soa_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub particle_capacity: u64,
    pub particle_count: u64,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub x_kcal_per_mol_angstrom: *mut f64,
    pub y_kcal_per_mol_angstrom: *mut f64,
    pub z_kcal_per_mol_angstrom: *mut f64,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_energy_components_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub harmonic_bond_kcal_per_mol: f64,
    pub harmonic_angle_kcal_per_mol: f64,
    pub periodic_torsion_kcal_per_mol: f64,
    pub lennard_jones_kcal_per_mol: f64,
    pub coulomb_kcal_per_mol: f64,
    pub total_kcal_per_mol: f64,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_direct_ewald_parameters_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub atom_count: u64,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub cell_lengths_angstrom: [f64; 3],
    pub alpha_per_angstrom: f64,
    pub real_space_cutoff_angstrom: f64,
    pub reciprocal_max_indices: [i32; 3],
    pub reserved1: u32,
    pub dielectric: f64,
    pub minimum_pair_distance_angstrom: f64,
    pub exclusion_count: u64,
    pub exclusion_atom_i: *const u64,
    pub exclusion_atom_j: *const u64,
    pub pair_scale_count: u64,
    pub pair_scale_atom_i: *const u64,
    pub pair_scale_atom_j: *const u64,
    pub pair_scale_coulomb: *const f64,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_particle_mesh_reciprocal_parameters_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub atom_count: u64,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub cell_lengths_angstrom: [f64; 3],
    pub alpha_per_angstrom: f64,
    pub mesh_dimensions: [u32; 3],
    pub reserved1: u32,
    pub dielectric: f64,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_particle_mesh_reciprocal_energy_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub reciprocal_space_kcal_per_mol: f64,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_particle_mesh_reciprocal_force_soa_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub atom_capacity: u64,
    pub atom_count: u64,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub x_kcal_per_mol_angstrom: *mut f64,
    pub y_kcal_per_mol_angstrom: *mut f64,
    pub z_kcal_per_mol_angstrom: *mut f64,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_particle_mesh_reciprocal_error_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub code: bg_particle_mesh_reciprocal_error_code,
    pub reserved0: u32,
    pub detail: [c_char; BG_PARTICLE_MESH_RECIPROCAL_ERROR_DETAIL_CAPACITY as usize],
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_direct_ewald_energy_components_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub real_space_kcal_per_mol: f64,
    pub reciprocal_space_kcal_per_mol: f64,
    pub self_kcal_per_mol: f64,
    pub pair_correction_kcal_per_mol: f64,
    pub total_kcal_per_mol: f64,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_direct_ewald_force_soa_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub atom_capacity: u64,
    pub atom_count: u64,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub x_kcal_per_mol_angstrom: *mut f64,
    pub y_kcal_per_mol_angstrom: *mut f64,
    pub z_kcal_per_mol_angstrom: *mut f64,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_particle_mesh_ewald_energy_components_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub real_space_kcal_per_mol: f64,
    pub reciprocal_space_kcal_per_mol: f64,
    pub self_kcal_per_mol: f64,
    pub pair_correction_kcal_per_mol: f64,
    pub total_kcal_per_mol: f64,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_particle_mesh_ewald_force_soa_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub atom_capacity: u64,
    pub atom_count: u64,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub x_kcal_per_mol_angstrom: *mut f64,
    pub y_kcal_per_mol_angstrom: *mut f64,
    pub z_kcal_per_mol_angstrom: *mut f64,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_particle_mesh_ewald_composite_energy_components_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub short_harmonic_bond_kcal_per_mol: f64,
    pub short_harmonic_angle_kcal_per_mol: f64,
    pub short_periodic_torsion_kcal_per_mol: f64,
    pub short_lennard_jones_kcal_per_mol: f64,
    pub short_coulomb_kcal_per_mol: f64,
    pub short_total_kcal_per_mol: f64,
    pub pme_real_space_kcal_per_mol: f64,
    pub pme_reciprocal_space_kcal_per_mol: f64,
    pub pme_self_kcal_per_mol: f64,
    pub pme_pair_correction_kcal_per_mol: f64,
    pub pme_total_kcal_per_mol: f64,
    pub total_kcal_per_mol: f64,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_particle_mesh_ewald_composite_force_soa_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub atom_capacity: u64,
    pub atom_count: u64,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub x_kcal_per_mol_angstrom: *mut f64,
    pub y_kcal_per_mol_angstrom: *mut f64,
    pub z_kcal_per_mol_angstrom: *mut f64,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_direct_ewald_error_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub code: bg_direct_ewald_error_code,
    pub reserved0: u32,
    pub detail: [c_char; BG_DIRECT_EWALD_ERROR_DETAIL_CAPACITY as usize],
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_direct_ewald_composite_energy_components_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub short_harmonic_bond_kcal_per_mol: f64,
    pub short_harmonic_angle_kcal_per_mol: f64,
    pub short_periodic_torsion_kcal_per_mol: f64,
    pub short_lennard_jones_kcal_per_mol: f64,
    pub short_coulomb_kcal_per_mol: f64,
    pub short_total_kcal_per_mol: f64,
    pub ewald_real_space_kcal_per_mol: f64,
    pub ewald_reciprocal_space_kcal_per_mol: f64,
    pub ewald_self_kcal_per_mol: f64,
    pub ewald_pair_correction_kcal_per_mol: f64,
    pub ewald_total_kcal_per_mol: f64,
    pub total_kcal_per_mol: f64,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_direct_ewald_composite_force_soa_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub atom_capacity: u64,
    pub atom_count: u64,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub x_kcal_per_mol_angstrom: *mut f64,
    pub y_kcal_per_mol_angstrom: *mut f64,
    pub z_kcal_per_mol_angstrom: *mut f64,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_distance_constraints_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub constraint_count: u64,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub atom_i: *const u64,
    pub atom_j: *const u64,
    pub distance_angstrom: *const f64,
    pub tolerance_angstrom: f64,
    pub velocity_tolerance_angstrom_per_femtosecond: f64,
    pub max_iterations: u32,
    pub reserved1: u32,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_simulation_options_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub unit_system: bg_unit_system,
    pub integrator: bg_integrator,
    pub timestep_femtoseconds: f64,
    pub temperature_kelvin: f64,
    pub friction_per_femtosecond: f64,
    pub random_seed: u64,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_minimizer_options_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub max_iterations: u64,
    pub max_line_search_steps: u32,
    pub reserved1: u32,
    pub initial_step_angstrom2_mol_per_kcal: f64,
    pub minimum_step_angstrom2_mol_per_kcal: f64,
    pub energy_tolerance_kcal_per_mol: f64,
    pub force_tolerance_kcal_per_mol_angstrom: f64,
    pub armijo_coefficient: f64,
    pub backtrack_factor: f64,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_minimization_report_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub iterations: u64,
    pub converged: u32,
    pub reserved1: u32,
    pub initial_potential_kcal_per_mol: f64,
    pub final_potential_kcal_per_mol: f64,
    pub maximum_force_kcal_per_mol_angstrom: f64,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_dynamics_report_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub steps_completed: u64,
    pub absolute_step: u64,
    pub degrees_of_freedom: u64,
    pub potential_kcal_per_mol: f64,
    pub kinetic_kcal_per_mol: f64,
    pub total_kcal_per_mol: f64,
    pub temperature_kelvin: f64,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_fixed64_source_evidence_v1 {
    pub receipt_sha256: [u8; 32],
    pub proposal_sha256: [u8; 32],
    pub coordinate_sha256: [u8; 32],
    pub reserved: [u64; 2],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_fixed64_exact_source_evidence_v1 {
    pub source_receipt_sha256: [u8; 32],
    pub proposal_sha256: [u8; 32],
    pub ligand_coordinate_sha256: [u8; 32],
    pub receptor_coordinate_sha256: [u8; 32],
    pub prepared_ligand_topology_sha256: [u8; 32],
    pub prepared_receptor_topology_sha256: [u8; 32],
    pub ligand_vdw_radii_sha256: [u8; 32],
    pub ligand_heavy_atom_mask_sha256: [u8; 32],
    pub receptor_vdw_radii_sha256: [u8; 32],
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_fixed64_atomic_feature_evidence_v1 {
    pub kind: bg_docking_fixed64_feature_kind,
    pub reserved0: u32,
    pub receipt_sha256: [u8; 32],
    pub reserved: [u64; 2],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_fixed64_indexed_source_evidence_v1 {
    pub source_index: u32,
    pub reserved0: u32,
    pub source: bg_docking_fixed64_source_evidence_v1,
    pub reserved: [u64; 2],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_fixed64_conformer_source_evidence_v1 {
    pub rank: u8,
    pub reserved0: [u8; 7],
    pub source: bg_docking_fixed64_source_evidence_v1,
    pub reserved: [u64; 2],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_fixed64_allocation_input_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub exact_v11_source: bg_docking_fixed64_exact_source_evidence_v1,
    pub atomic_feature_count: u64,
    pub atomic_features: *const bg_docking_fixed64_atomic_feature_evidence_v1,
    pub v7_control_source_count: u64,
    pub v7_control_sources: *const bg_docking_fixed64_indexed_source_evidence_v1,
    pub conformer_source_count: u64,
    pub conformer_sources: *const bg_docking_fixed64_conformer_source_evidence_v1,
    pub retained_source_count: u64,
    pub retained_sources: *const bg_docking_fixed64_indexed_source_evidence_v1,
    pub reserved: [u64; 8],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_fixed64_requirement_v1 {
    pub kind: bg_docking_fixed64_requirement_kind,
    pub value: u32,
    pub reserved: [u64; 2],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_fixed64_missing_feature_v1 {
    pub kind: bg_docking_fixed64_missing_feature_kind,
    pub value: u32,
    pub reserved: [u64; 2],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_fixed64_allocation_row_v1 {
    pub slot_index: u32,
    pub lane: bg_docking_fixed64_lane,
    pub lane_offset: u32,
    pub status: bg_docking_fixed64_allocation_row_status,
    pub declared_anchor_kind: bg_docking_fixed64_anchor_kind,
    pub generation_parent_role: bg_docking_fixed64_parent_role,
    pub requirement_count: u32,
    pub missing_feature_count: u32,
    pub v7_control_source_index: i32,
    pub so3_sequence_index: i32,
    pub true_conformer_rank: i32,
    pub retained_source_index: i32,
    pub requirements:
        [bg_docking_fixed64_requirement_v1; BG_DOCKING_FIXED64_MAX_REQUIREMENTS as usize],
    pub missing_features:
        [bg_docking_fixed64_missing_feature_v1; BG_DOCKING_FIXED64_MAX_MISSING_FEATURES as usize],
    pub selected_source_receipt_count: u32,
    pub reserved0: u32,
    pub selected_source_receipt_sha256:
        [[u8; 32]; BG_DOCKING_FIXED64_MAX_SELECTED_SOURCE_RECEIPTS as usize],
    pub generation_parent_receipt_sha256: [u8; 32],
    pub generation_parent_proposal_sha256: [u8; 32],
    pub generation_parent_coordinate_sha256: [u8; 32],
    pub slot_receipt_sha256: [u8; 32],
    pub generation_eligible: u8,
    pub fallback_allowed: u8,
    pub multi_anchor_allowed: u8,
    pub result_dependent_allocation: u8,
    pub denominator_preserved: u8,
    pub molecular_execution_authorized: u8,
    pub reservation_authorized: u8,
    pub benchmark_execution_authorized: u8,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_fixed64_allocation_output_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub row_capacity: u64,
    pub row_count: u64,
    pub rows: *mut bg_docking_fixed64_allocation_row_v1,
    pub ready_count: u64,
    pub typed_failure_count: u64,
    pub inventory_sha256: [u8; 32],
    pub allocation_receipt_sha256: [u8; 32],
    pub result_dependent_allocation: u8,
    pub molecular_execution_authorized: u8,
    pub reservation_authorized: u8,
    pub benchmark_execution_authorized: u8,
    pub existing_rank_auto_change_authorized: u8,
    pub customer_pose_emission_authorized: u8,
    pub production_claim_authorized: u8,
    pub reserved0: u8,
    pub reserved: [u64; 8],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_fixed64_so3_input_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub source_seed_sha256: [u8; 32],
    pub reserved: [u64; 8],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_fixed64_so3_row_v1 {
    pub orientation_index: u32,
    pub status: bg_docking_fixed64_so3_row_status,
    pub failure_code: bg_docking_fixed64_so3_failure,
    pub reserved0: u32,
    pub raw_sequence_index: u64,
    pub quaternion_x: f64,
    pub quaternion_y: f64,
    pub quaternion_z: f64,
    pub quaternion_w: f64,
    pub norm_error: f64,
    pub row_receipt_sha256: [u8; 32],
    pub result_dependent_input_consumed: u8,
    pub duplicate_orientation_emitted: u8,
    pub denominator_preserved: u8,
    pub molecular_execution_authorized: u8,
    pub reservation_authorized: u8,
    pub benchmark_execution_authorized: u8,
    pub production_claim_authorized: u8,
    pub reserved1: u8,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_fixed64_so3_output_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub row_capacity: u64,
    pub row_count: u64,
    pub rows: *mut bg_docking_fixed64_so3_row_v1,
    pub backend: bg_backend,
    pub reserved0: u32,
    pub batch_receipt_sha256: [u8; 32],
    pub result_dependent_input_consumed: u8,
    pub denominator_preserved: u8,
    pub molecular_execution_authorized: u8,
    pub reservation_authorized: u8,
    pub benchmark_execution_authorized: u8,
    pub production_claim_authorized: u8,
    pub reserved1: [u8; 2],
    pub reserved: [u64; 8],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_fixed64_indexed_so3_input_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub allocation_inventory_sha256: [u8; 32],
    pub allocation_receipt_sha256: [u8; 32],
    pub allocation_row_count: u64,
    pub allocation_rows: *const bg_docking_fixed64_allocation_row_v1,
    pub slot_index: u32,
    pub reserved0: u32,
    pub source: bg_docking_fixed64_source_evidence_v1,
    pub ligand_atom_count: u64,
    pub source_x_angstrom: *const f64,
    pub source_y_angstrom: *const f64,
    pub source_z_angstrom: *const f64,
    pub pocket_center_angstrom: [f64; 3],
    pub pocket_normal: [f64; 3],
    pub reserved: [u64; 8],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_fixed64_indexed_so3_output_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub coordinate_capacity: u64,
    pub x_angstrom: *mut f64,
    pub y_angstrom: *mut f64,
    pub z_angstrom: *mut f64,
    pub slot_index: u32,
    pub lane: bg_docking_fixed64_lane,
    pub status: bg_docking_fixed64_indexed_so3_status,
    pub failure_code: bg_docking_fixed64_indexed_so3_failure,
    pub backend: bg_backend,
    pub accepted_sequence_index: u32,
    pub ligand_atom_count: u64,
    pub raw_sequence_index: u64,
    pub quaternion_x: f64,
    pub quaternion_y: f64,
    pub quaternion_z: f64,
    pub quaternion_w: f64,
    pub translation_angstrom: [f64; 3],
    pub source_centroid_angstrom: [f64; 3],
    pub source_seed_sha256: [u8; 32],
    pub output_coordinate_sha256: [u8; 32],
    pub placement_receipt_sha256: [u8; 32],
    pub coordinates_written: u8,
    pub source_identity_verified: u8,
    pub allocation_identity_verified: u8,
    pub result_dependent_input_consumed: u8,
    pub denominator_preserved: u8,
    pub molecular_execution_authorized: u8,
    pub reservation_authorized: u8,
    pub benchmark_execution_authorized: u8,
    pub production_claim_authorized: u8,
    pub reserved0: [u8; 7],
    pub reserved: [u64; 8],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_fixed64_feature_geometry_row_v1 {
    pub kind: bg_docking_fixed64_feature_kind,
    pub reserved0: u32,
    pub allocation_feature_receipt_sha256: [u8; 32],
    pub atom_index_offset: u64,
    pub atom_index_count: u64,
    pub feature_geometry_receipt_sha256: [u8; 32],
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_fixed64_single_anchor_input_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub allocation_input: *const bg_docking_fixed64_allocation_input_v1,
    pub slot_index: u32,
    pub reserved0: u32,
    pub source: bg_docking_fixed64_source_evidence_v1,
    pub ligand_atom_count: u64,
    pub source_x_angstrom: *const f64,
    pub source_y_angstrom: *const f64,
    pub source_z_angstrom: *const f64,
    pub feature_geometry_count: u64,
    pub feature_geometry_rows: *const bg_docking_fixed64_feature_geometry_row_v1,
    pub feature_atom_index_count: u64,
    pub feature_atom_indices: *const u64,
    pub feature_geometry_inventory_sha256: [u8; 32],
    pub reserved: [u64; 8],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_geometric_admission_context_soa_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub receptor_atom_count: u64,
    pub ligand_atom_count: u64,
    pub receptor_x_angstrom: *const f64,
    pub receptor_y_angstrom: *const f64,
    pub receptor_z_angstrom: *const f64,
    pub receptor_vdw_radius_angstrom: *const f64,
    pub ligand_vdw_radius_angstrom: *const f64,
    pub ligand_heavy_atom_mask: *const u8,
    pub pocket_center_angstrom: [f64; 3],
    pub pocket_radius_angstrom: f64,
    pub hard_rejection_minimum_vdw_ratio: f64,
    pub max_batch_exact_pair_evaluations: u64,
    pub authority_input_receipt_sha256: [u8; 32],
    pub receptor_system_sha256: [u8; 32],
    pub ligand_system_sha256: [u8; 32],
    pub backend_receipt_sha256: [u8; 32],
    pub reserved: [u64; 8],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_geometric_admission_candidate_batch_soa_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub candidate_count: u64,
    pub ligand_atom_count: u64,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub candidate_state: *const bg_docking_geometric_admission_candidate_state,
    pub x_angstrom: *const f64,
    pub y_angstrom: *const f64,
    pub z_angstrom: *const f64,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_geometric_admission_row_v1 {
    pub slot_index: u32,
    pub status: bg_docking_geometric_admission_row_status,
    pub failure_code: bg_docking_geometric_admission_failure,
    pub decision: bg_docking_geometric_admission_decision,
    pub rank_eligible: u8,
    pub reserved0: [u8; 3],
    pub reserved1: u32,
    pub ligand_atom_count: u64,
    pub receptor_atom_count: u64,
    pub exact_pair_count: u64,
    pub penetration_pair_count: u64,
    pub unique_ligand_penetration_atom_count: u64,
    pub unique_ligand_heavy_atom_penetration_count: u64,
    pub raw_minimum_distance_angstrom: f64,
    pub minimum_vdw_surface_gap_angstrom: f64,
    pub minimum_vdw_ratio: f64,
    pub sphere_overlap_proxy_angstrom3: f64,
    pub pocket_escape_angstrom: f64,
    pub row_receipt_sha256: [u8; 32],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_geometric_admission_output_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub row_capacity: u64,
    pub row_count: u64,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub rows: *mut bg_docking_geometric_admission_row_v1,
    pub molecular_execution_authorized: u8,
    pub reservation_authorized: u8,
    pub benchmark_execution_authorized: u8,
    pub existing_rank_auto_change_authorized: u8,
    pub customer_pose_emission_authorized: u8,
    pub production_claim_authorized: u8,
    pub scientific_claim_authorized: u8,
    pub reserved1: u8,
    pub batch_receipt_sha256: [u8; 32],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_fixed64_single_anchor_output_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub coordinate_capacity: u64,
    pub x_angstrom: *mut f64,
    pub y_angstrom: *mut f64,
    pub z_angstrom: *mut f64,
    pub slot_index: u32,
    pub lane: bg_docking_fixed64_lane,
    pub lane_offset: u32,
    pub anchor_kind: bg_docking_fixed64_anchor_kind,
    pub status: bg_docking_fixed64_single_anchor_status,
    pub failure_code: bg_docking_fixed64_single_anchor_failure,
    pub backend: bg_backend,
    pub reserved0: u32,
    pub ligand_atom_count: u64,
    pub ligand_anchor_point_angstrom: [f64; 3],
    pub receptor_anchor_point_angstrom: [f64; 3],
    pub target_anchor_point_angstrom: [f64; 3],
    pub local_surface_normal: [f64; 3],
    pub approach_vector: [f64; 3],
    pub ligand_direction: [f64; 3],
    pub alignment_target_direction: [f64; 3],
    pub target_distance_angstrom: f64,
    pub twist_angle_radians: f64,
    pub quaternion_x: f64,
    pub quaternion_y: f64,
    pub quaternion_z: f64,
    pub quaternion_w: f64,
    pub translation_angstrom: [f64; 3],
    pub allocation_inventory_sha256: [u8; 32],
    pub allocation_receipt_sha256: [u8; 32],
    pub allocation_slot_receipt_sha256: [u8; 32],
    pub source_receipt_sha256: [u8; 32],
    pub feature_geometry_inventory_sha256: [u8; 32],
    pub selected_ligand_feature_geometry_sha256: [u8; 32],
    pub selected_receptor_feature_geometry_sha256: [u8; 32],
    pub output_coordinate_sha256: [u8; 32],
    pub geometric_admission: bg_docking_geometric_admission_row_v1,
    pub geometric_admission_batch_receipt_sha256: [u8; 32],
    pub placement_receipt_sha256: [u8; 32],
    pub coordinates_written: u8,
    pub steric_precheck_passed: u8,
    pub source_identity_verified: u8,
    pub allocation_identity_verified: u8,
    pub feature_identity_verified: u8,
    pub geometric_identity_verified: u8,
    pub result_dependent_input_consumed: u8,
    pub fallback_allowed: u8,
    pub multi_anchor_consumed: u8,
    pub denominator_preserved: u8,
    pub molecular_execution_authorized: u8,
    pub reservation_authorized: u8,
    pub benchmark_execution_authorized: u8,
    pub existing_rank_auto_change_authorized: u8,
    pub customer_pose_emission_authorized: u8,
    pub production_claim_authorized: u8,
    pub scientific_claim_authorized: u8,
    pub reserved: [u64; 8],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_fixed64_coordinate_source_v1 {
    pub source: bg_docking_fixed64_source_evidence_v1,
    pub ligand_atom_count: u64,
    pub x_angstrom: *const f64,
    pub y_angstrom: *const f64,
    pub z_angstrom: *const f64,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_fixed64_indexed_coordinate_source_v1 {
    pub source_index: u32,
    pub reserved0: u32,
    pub payload: bg_docking_fixed64_coordinate_source_v1,
    pub reserved: [u64; 2],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_fixed64_conformer_coordinate_source_v1 {
    pub rank: u8,
    pub reserved0: [u8; 7],
    pub payload: bg_docking_fixed64_coordinate_source_v1,
    pub reserved: [u64; 2],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_fixed64_producer_input_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub allocation_input: *const bg_docking_fixed64_allocation_input_v1,
    pub exact_v11_source: *const bg_docking_fixed64_coordinate_source_v1,
    pub v7_control_source_count: u64,
    pub v7_control_sources: *const bg_docking_fixed64_indexed_coordinate_source_v1,
    pub conformer_source_count: u64,
    pub conformer_sources: *const bg_docking_fixed64_conformer_coordinate_source_v1,
    pub retained_source_count: u64,
    pub retained_sources: *const bg_docking_fixed64_indexed_coordinate_source_v1,
    pub feature_geometry_count: u64,
    pub feature_geometry_rows: *const bg_docking_fixed64_feature_geometry_row_v1,
    pub feature_atom_index_count: u64,
    pub feature_atom_indices: *const u64,
    pub feature_geometry_inventory_sha256: [u8; 32],
    pub pocket_normal: [f64; 3],
    pub reserved: [u64; 8],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_fixed64_producer_row_v1 {
    pub slot_index: u32,
    pub lane: bg_docking_fixed64_lane,
    pub status: bg_docking_fixed64_producer_row_status,
    pub failure_code: bg_docking_fixed64_producer_failure,
    pub placement_kind: bg_docking_fixed64_producer_placement_kind,
    pub component_failure_code: i32,
    pub backend: bg_backend,
    pub reserved0: u32,
    pub ligand_atom_count: u64,
    pub coordinate_offset: u64,
    pub allocation_slot_receipt_sha256: [u8; 32],
    pub source_payload_receipt_sha256: [u8; 32],
    pub source_proposal_sha256: [u8; 32],
    pub source_coordinate_sha256: [u8; 32],
    pub placement_receipt_sha256: [u8; 32],
    pub output_proposal_sha256: [u8; 32],
    pub output_coordinate_sha256: [u8; 32],
    pub geometric_admission: bg_docking_geometric_admission_row_v1,
    pub row_receipt_sha256: [u8; 32],
    pub coordinates_available: u8,
    pub steric_precheck_passed: u8,
    pub source_identity_verified: u8,
    pub allocation_identity_verified: u8,
    pub geometric_identity_verified: u8,
    pub result_dependent_input_consumed: u8,
    pub fallback_allowed: u8,
    pub multi_anchor_consumed: u8,
    pub denominator_preserved: u8,
    pub molecular_execution_authorized: u8,
    pub reservation_authorized: u8,
    pub benchmark_execution_authorized: u8,
    pub existing_rank_auto_change_authorized: u8,
    pub customer_pose_emission_authorized: u8,
    pub production_claim_authorized: u8,
    pub scientific_claim_authorized: u8,
    pub placement_quaternion_x: f64,
    pub placement_quaternion_y: f64,
    pub placement_quaternion_z: f64,
    pub placement_quaternion_w: f64,
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_fixed64_producer_output_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub row_capacity: u64,
    pub row_count: u64,
    pub coordinate_capacity: u64,
    pub coordinate_count: u64,
    pub unit_system: bg_unit_system,
    pub backend: bg_backend,
    pub rows: *mut bg_docking_fixed64_producer_row_v1,
    pub x_angstrom: *mut f64,
    pub y_angstrom: *mut f64,
    pub z_angstrom: *mut f64,
    pub generated_count: u64,
    pub typed_failure_count: u64,
    pub allocation_inventory_sha256: [u8; 32],
    pub allocation_receipt_sha256: [u8; 32],
    pub source_bundle_receipt_sha256: [u8; 32],
    pub geometric_admission_batch_receipt_sha256: [u8; 32],
    pub producer_batch_receipt_sha256: [u8; 32],
    pub result_dependent_input_consumed: u8,
    pub fallback_allowed: u8,
    pub multi_anchor_consumed: u8,
    pub denominator_preserved: u8,
    pub molecular_execution_authorized: u8,
    pub reservation_authorized: u8,
    pub benchmark_execution_authorized: u8,
    pub existing_rank_auto_change_authorized: u8,
    pub customer_pose_emission_authorized: u8,
    pub production_claim_authorized: u8,
    pub scientific_claim_authorized: u8,
    pub reserved0: [u8; 5],
    pub reserved: [u64; 8],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_fixed64_pipeline_input_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub producer_input: *const bg_docking_fixed64_producer_input_v1,
    pub rmsd_threshold_angstrom: f64,
    pub candidate_mode: *const bg_docking_rigid_refinement_candidate_mode,
    pub rigid_max_steps: *const u64,
    pub proposal_is_torsion_eligible: *const u8,
    pub torsion_max_steps: *const u64,
    pub baseline_torsion_angles_radians: *const f64,
    pub predeclared_refinement_policy_sha256: [u8; 32],
    pub reserved: [u64; 8],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_fixed64_pipeline_row_v1 {
    pub slot_index: u32,
    pub producer_status: bg_docking_fixed64_producer_row_status,
    pub producer_failure_code: bg_docking_fixed64_producer_failure,
    pub initial_admission_decision: bg_docking_geometric_admission_decision,
    pub requested_refinement_mode: bg_docking_rigid_refinement_candidate_mode,
    pub effective_refinement_mode: bg_docking_rigid_refinement_candidate_mode,
    pub refinement_status: bg_docking_fixed64_refinement_row_status,
    pub refinement_failure_stage: bg_docking_fixed64_refinement_failure_stage,
    pub scorer_status: bg_docking_scorer_v1_row_status,
    pub scorer_failure_code: bg_docking_scorer_v1_failure,
    pub validity_status: bg_docking_pose_validity_row_status,
    pub validity_failure_code: bg_docking_pose_validity_failure,
    pub stable_rank: u32,
    pub stable_valid_rank: u32,
    pub cluster_status: bg_docking_rmsd_cluster_row_status,
    pub cluster_id: u32,
    pub cluster_rank: u32,
    pub top_k_rank: u32,
    pub producer_row_receipt_sha256: [u8; 32],
    pub final_coordinate_sha256: [u8; 32],
    pub refinement_evidence_sha256: [u8; 32],
    pub scorer_evidence_sha256: [u8; 32],
    pub validity_evidence_sha256: [u8; 32],
    pub ranking_evidence_sha256: [u8; 32],
    pub cluster_evidence_sha256: [u8; 32],
    pub row_receipt_sha256: [u8; 32],
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_fixed64_pipeline_output_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub row_capacity: u64,
    pub row_count: u64,
    pub unit_system: bg_unit_system,
    pub backend: bg_backend,
    pub rows: *mut bg_docking_fixed64_pipeline_row_v1,
    pub generated_count: u64,
    pub initial_admitted_count: u64,
    pub refined_count: u64,
    pub scored_count: u64,
    pub valid_count: u64,
    pub cluster_count: u64,
    pub allocation_receipt_sha256: [u8; 32],
    pub source_bundle_receipt_sha256: [u8; 32],
    pub admission_context_receipt_sha256: [u8; 32],
    pub refinement_context_receipt_sha256: [u8; 32],
    pub scorer_context_receipt_sha256: [u8; 32],
    pub validity_context_receipt_sha256: [u8; 32],
    pub component_binding_receipt_sha256: [u8; 32],
    pub producer_batch_receipt_sha256: [u8; 32],
    pub refinement_policy_receipt_sha256: [u8; 32],
    pub refinement_batch_receipt_sha256: [u8; 32],
    pub scorer_batch_receipt_sha256: [u8; 32],
    pub validity_batch_receipt_sha256: [u8; 32],
    pub ranking_batch_receipt_sha256: [u8; 32],
    pub cluster_batch_receipt_sha256: [u8; 32],
    pub pipeline_batch_receipt_sha256: [u8; 32],
    pub result_dependent_input_consumed: u8,
    pub fallback_allowed: u8,
    pub denominator_preserved: u8,
    pub molecular_execution_authorized: u8,
    pub reservation_authorized: u8,
    pub benchmark_execution_authorized: u8,
    pub existing_rank_auto_change_authorized: u8,
    pub customer_pose_emission_authorized: u8,
    pub production_claim_authorized: u8,
    pub scientific_claim_authorized: u8,
    pub reserved0: [u8; 6],
    pub reserved: [u64; 8],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_fixed64_pipeline_input_v2 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub producer_input: *const bg_docking_fixed64_producer_input_v1,
    pub rmsd_threshold_angstrom: f64,
    pub candidate_mode: *const bg_docking_rigid_refinement_candidate_mode,
    pub rigid_max_steps: *const u64,
    pub proposal_is_torsion_eligible: *const u8,
    pub torsion_max_steps: *const u64,
    pub baseline_torsion_angles_radians: *const f64,
    pub predeclared_refinement_policy_sha256: [u8; 32],
    pub predeclared_post_refinement_admission_policy_sha256: [u8; 32],
    pub reserved: [u64; 8],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_fixed64_pipeline_row_v2 {
    pub slot_index: u32,
    pub producer_status: bg_docking_fixed64_producer_row_status,
    pub producer_failure_code: bg_docking_fixed64_producer_failure,
    pub initial_admission_decision: bg_docking_geometric_admission_decision,
    pub requested_refinement_mode: bg_docking_rigid_refinement_candidate_mode,
    pub effective_refinement_mode: bg_docking_rigid_refinement_candidate_mode,
    pub refinement_status: bg_docking_fixed64_refinement_row_status,
    pub refinement_failure_stage: bg_docking_fixed64_refinement_failure_stage,
    pub post_admission_status: bg_docking_geometric_admission_row_status,
    pub post_admission_failure_code: bg_docking_geometric_admission_failure,
    pub post_admission_decision: bg_docking_geometric_admission_decision,
    pub post_admission_rank_eligible: u8,
    pub reserved0: [u8; 3],
    pub scorer_status: bg_docking_scorer_v1_row_status,
    pub scorer_failure_code: bg_docking_scorer_v1_failure,
    pub validity_status: bg_docking_pose_validity_row_status,
    pub validity_failure_code: bg_docking_pose_validity_failure,
    pub stable_rank: u32,
    pub stable_valid_rank: u32,
    pub cluster_status: bg_docking_rmsd_cluster_row_status,
    pub cluster_id: u32,
    pub cluster_rank: u32,
    pub top_k_rank: u32,
    pub producer_row_receipt_sha256: [u8; 32],
    pub final_coordinate_sha256: [u8; 32],
    pub refinement_evidence_sha256: [u8; 32],
    pub post_admission_row_receipt_sha256: [u8; 32],
    pub scorer_evidence_sha256: [u8; 32],
    pub validity_evidence_sha256: [u8; 32],
    pub ranking_evidence_sha256: [u8; 32],
    pub cluster_evidence_sha256: [u8; 32],
    pub row_receipt_sha256: [u8; 32],
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_fixed64_pipeline_output_v2 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub row_capacity: u64,
    pub row_count: u64,
    pub unit_system: bg_unit_system,
    pub backend: bg_backend,
    pub rows: *mut bg_docking_fixed64_pipeline_row_v2,
    pub generated_count: u64,
    pub initial_admitted_count: u64,
    pub refined_count: u64,
    pub post_admitted_count: u64,
    pub post_rejected_count: u64,
    pub scored_count: u64,
    pub valid_count: u64,
    pub cluster_count: u64,
    pub allocation_receipt_sha256: [u8; 32],
    pub source_bundle_receipt_sha256: [u8; 32],
    pub admission_context_receipt_sha256: [u8; 32],
    pub refinement_context_receipt_sha256: [u8; 32],
    pub scorer_context_receipt_sha256: [u8; 32],
    pub validity_context_receipt_sha256: [u8; 32],
    pub component_binding_receipt_sha256: [u8; 32],
    pub producer_batch_receipt_sha256: [u8; 32],
    pub refinement_policy_receipt_sha256: [u8; 32],
    pub refinement_batch_receipt_sha256: [u8; 32],
    pub post_admission_policy_receipt_sha256: [u8; 32],
    pub post_admission_batch_receipt_sha256: [u8; 32],
    pub scorer_batch_receipt_sha256: [u8; 32],
    pub validity_batch_receipt_sha256: [u8; 32],
    pub ranking_batch_receipt_sha256: [u8; 32],
    pub cluster_batch_receipt_sha256: [u8; 32],
    pub pipeline_batch_receipt_sha256: [u8; 32],
    pub result_dependent_input_consumed: u8,
    pub fallback_allowed: u8,
    pub denominator_preserved: u8,
    pub molecular_execution_authorized: u8,
    pub reservation_authorized: u8,
    pub benchmark_execution_authorized: u8,
    pub existing_rank_auto_change_authorized: u8,
    pub customer_pose_emission_authorized: u8,
    pub production_claim_authorized: u8,
    pub scientific_claim_authorized: u8,
    pub reserved1: [u8; 6],
    pub reserved: [u64; 8],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_scorer_v1_context_soa_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub receptor_atom_count: u64,
    pub ligand_atom_count: u64,
    pub receptor_x_angstrom: *const f64,
    pub receptor_y_angstrom: *const f64,
    pub receptor_z_angstrom: *const f64,
    pub receptor_charge_elementary: *const f64,
    pub receptor_vdw_radius_angstrom: *const f64,
    pub receptor_epsilon_kcal_per_mol: *const f64,
    pub receptor_hydrophobic: *const u8,
    pub receptor_acceptor: *const u8,
    pub ligand_reference_x_angstrom: *const f64,
    pub ligand_reference_y_angstrom: *const f64,
    pub ligand_reference_z_angstrom: *const f64,
    pub ligand_charge_elementary: *const f64,
    pub ligand_vdw_radius_angstrom: *const f64,
    pub ligand_epsilon_kcal_per_mol: *const f64,
    pub ligand_hydrophobic: *const u8,
    pub ligand_acceptor: *const u8,
    pub receptor_donor_count: u64,
    pub receptor_donor_atom_index: *const u64,
    pub receptor_hydrogen_atom_index: *const u64,
    pub ligand_donor_count: u64,
    pub ligand_donor_atom_index: *const u64,
    pub ligand_hydrogen_atom_index: *const u64,
    pub ligand_exclusion_count: u64,
    pub ligand_exclusion_atom_i: *const u64,
    pub ligand_exclusion_atom_j: *const u64,
    pub rotor_count: u64,
    pub rotor_atom_i: *const u64,
    pub rotor_atom_j: *const u64,
    pub rotor_atom_k: *const u64,
    pub rotor_atom_l: *const u64,
    pub pocket_center_angstrom: [f64; 3],
    pub pocket_radius_angstrom: f64,
    pub weights: [f64; BG_DOCKING_SCORER_V1_TERM_COUNT as usize],
    pub electrostatic_dielectric: f64,
    pub pair_cutoff_angstrom: f64,
    pub hbond_distance_max_angstrom: f64,
    pub polar_burial_distance_angstrom: f64,
    pub max_receptor_candidate_pairs: u64,
    pub max_ligand_pair_checks: u64,
    pub authority_input_receipt_sha256: [u8; 32],
    pub receptor_system_sha256: [u8; 32],
    pub ligand_system_sha256: [u8; 32],
    pub backend_receipt_sha256: [u8; 32],
    pub reserved: [u64; 8],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_scorer_v1_candidate_batch_soa_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub candidate_count: u64,
    pub ligand_atom_count: u64,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub candidate_state: *const bg_docking_scorer_v1_candidate_state,
    pub x_angstrom: *const f64,
    pub y_angstrom: *const f64,
    pub z_angstrom: *const f64,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_scorer_v1_row_v1 {
    pub slot_index: u32,
    pub status: bg_docking_scorer_v1_row_status,
    pub failure_code: bg_docking_scorer_v1_failure,
    pub reserved0: u32,
    pub weighted_terms: [f64; BG_DOCKING_SCORER_V1_TERM_COUNT as usize],
    pub total_score: f64,
    pub receptor_candidate_pair_count: u64,
    pub ligand_pair_count: u64,
    pub hbond_count: u64,
    pub hydrophobic_contact_count: u64,
    pub buried_polar_count: u64,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_scorer_v1_output_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub row_capacity: u64,
    pub row_count: u64,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub rows: *mut bg_docking_scorer_v1_row_v1,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_pose_validity_context_soa_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub receptor_atom_count: u64,
    pub ligand_atom_count: u64,
    pub receptor_x_angstrom: *const f64,
    pub receptor_y_angstrom: *const f64,
    pub receptor_z_angstrom: *const f64,
    pub receptor_vdw_radius_angstrom: *const f64,
    pub ligand_reference_x_angstrom: *const f64,
    pub ligand_reference_y_angstrom: *const f64,
    pub ligand_reference_z_angstrom: *const f64,
    pub ligand_vdw_radius_angstrom: *const f64,
    pub bond_count: u64,
    pub bond_atom_i: *const u64,
    pub bond_atom_j: *const u64,
    pub ligand_exclusion_count: u64,
    pub ligand_exclusion_atom_i: *const u64,
    pub ligand_exclusion_atom_j: *const u64,
    pub chirality_center_count: u64,
    pub chirality_center_atom: *const u64,
    pub chirality_atom_i: *const u64,
    pub chirality_atom_j: *const u64,
    pub chirality_atom_k: *const u64,
    pub pocket_center_angstrom: [f64; 3],
    pub pocket_radius_angstrom: f64,
    pub bond_length_tolerance_angstrom: f64,
    pub ligand_self_clash_angstrom: f64,
    pub receptor_ligand_clash_angstrom: f64,
    pub rotation_tolerance: f64,
    pub chirality_volume_tolerance: f64,
    pub severe_overlap_scale: f64,
    pub contact_cell_size_angstrom: f64,
    pub max_pair_checks: u64,
    pub max_cross_checks: u64,
    pub max_element_ligand_pair_checks: u64,
    pub max_element_receptor_candidate_pairs: u64,
    pub authority_input_receipt_sha256: [u8; 32],
    pub receptor_system_sha256: [u8; 32],
    pub ligand_system_sha256: [u8; 32],
    pub scorer_context_receipt_sha256: [u8; 32],
    pub backend_receipt_sha256: [u8; 32],
    pub contact_policy_sha256: [u8; 32],
    pub reserved: [u64; 8],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_pose_validity_candidate_batch_soa_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub candidate_count: u64,
    pub ligand_atom_count: u64,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub candidate_state: *const bg_docking_pose_validity_candidate_state,
    pub upstream_scorer_failure_code: *const bg_docking_scorer_v1_failure,
    pub quaternion_x: *const f64,
    pub quaternion_y: *const f64,
    pub quaternion_z: *const f64,
    pub quaternion_w: *const f64,
    pub x_angstrom: *const f64,
    pub y_angstrom: *const f64,
    pub z_angstrom: *const f64,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_pose_validity_row_v1 {
    pub slot_index: u32,
    pub status: bg_docking_pose_validity_row_status,
    pub failure_code: bg_docking_pose_validity_failure,
    pub upstream_scorer_failure_code: bg_docking_scorer_v1_failure,
    pub passed_check_mask: bg_docking_pose_validity_check_mask,
    pub blocker_mask: bg_docking_pose_validity_check_mask,
    pub observed_count: u64,
    pub atom_count: u64,
    pub rotation_orthogonality_max_error: f64,
    pub rotation_determinant: f64,
    pub max_bond_length_delta_angstrom: f64,
    pub minimum_ligand_nonbonded_distance_angstrom: f64,
    pub evaluated_ligand_nonbonded_pair_count: u64,
    pub excluded_ligand_pair_count: u64,
    pub minimum_receptor_ligand_distance_angstrom: f64,
    pub evaluated_receptor_ligand_pair_count: u64,
    pub minimum_declared_chiral_volume: f64,
    pub declared_chirality_center_count: u64,
    pub maximum_pocket_center_distance_angstrom: f64,
    pub element_vdw_ligand_pair_count: u64,
    pub element_vdw_ligand_severe_overlap_count: u64,
    pub element_vdw_ligand_minimum_distance_angstrom: f64,
    pub element_vdw_ligand_minimum_ratio: f64,
    pub element_vdw_receptor_candidate_pair_count: u64,
    pub element_vdw_receptor_full_cartesian_pair_count: u64,
    pub element_vdw_receptor_cell_count: u64,
    pub element_vdw_receptor_severe_overlap_count: u64,
    pub element_vdw_receptor_minimum_distance_angstrom: f64,
    pub element_vdw_receptor_minimum_ratio: f64,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_pose_validity_output_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub row_capacity: u64,
    pub row_count: u64,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub rows: *mut bg_docking_pose_validity_row_v1,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_stable_top_k_input_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub candidate_count: u64,
    pub top_k_limit: u32,
    pub unit_system: bg_unit_system,
    pub scorer_rows: *const bg_docking_scorer_v1_row_v1,
    pub validity_rows: *const bg_docking_pose_validity_row_v1,
    pub coordinate_sha256: *const u8,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_stable_top_k_row_v1 {
    pub slot_index: u32,
    pub rank_eligible: u8,
    pub valid_rank_eligible: u8,
    pub reserved0: u16,
    pub stable_rank: u32,
    pub stable_valid_rank: u32,
    pub total_score: f64,
    pub coordinate_sha256: [u8; 32],
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_stable_top_k_output_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub row_capacity: u64,
    pub row_count: u64,
    pub primary_index_capacity: u64,
    pub primary_index_count: u64,
    pub valid_index_capacity: u64,
    pub valid_index_count: u64,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub rows: *mut bg_docking_stable_top_k_row_v1,
    pub primary_slot_indices: *mut u32,
    pub valid_slot_indices: *mut u32,
    pub existing_rank_auto_change_authorized: u8,
    pub customer_pose_emission_authorized: u8,
    pub production_claim_authorized: u8,
    pub reserved1: u8,
    pub reserved2: u32,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_rmsd_cluster_input_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub candidate_count: u64,
    pub ligand_atom_count: u64,
    pub valid_index_count: u64,
    pub top_k_limit: u32,
    pub unit_system: bg_unit_system,
    pub rmsd_threshold_angstrom: f64,
    pub ranking_rows: *const bg_docking_stable_top_k_row_v1,
    pub valid_slot_indices: *const u32,
    pub x_angstrom: *const f64,
    pub y_angstrom: *const f64,
    pub z_angstrom: *const f64,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_rmsd_cluster_row_v1 {
    pub slot_index: u32,
    pub status: bg_docking_rmsd_cluster_row_status,
    pub cluster_eligible: u8,
    pub representative: u8,
    pub top_k_representative: u8,
    pub reserved0: u8,
    pub stable_valid_rank: u32,
    pub cluster_id: u32,
    pub representative_slot_index: u32,
    pub cluster_rank: u32,
    pub top_k_rank: u32,
    pub cluster_size: u32,
    pub reserved1: u32,
    pub direct_rmsd_to_representative_angstrom: f64,
    pub coordinate_sha256: [u8; 32],
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_rmsd_cluster_output_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub row_capacity: u64,
    pub row_count: u64,
    pub representative_index_capacity: u64,
    pub representative_index_count: u64,
    pub top_k_index_capacity: u64,
    pub top_k_index_count: u64,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub rows: *mut bg_docking_rmsd_cluster_row_v1,
    pub representative_slot_indices: *mut u32,
    pub top_k_slot_indices: *mut u32,
    pub existing_rank_auto_change_authorized: u8,
    pub customer_pose_emission_authorized: u8,
    pub production_claim_authorized: u8,
    pub reserved1: u8,
    pub reserved2: u32,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_rigid_v2_config_v1 {
    pub overlap_scale: f64,
    pub maximum_step_angstrom: f64,
    pub minimum_step_angstrom: f64,
    pub maximum_total_translation_angstrom: f64,
    pub maximum_backtracking_evaluations: u64,
    pub penalty_tolerance: f64,
    pub epsilon_angstrom: f64,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_rigid_v3_config_v1 {
    pub v2: bg_docking_rigid_v2_config_v1,
    pub maximum_rotation_step_radians: f64,
    pub minimum_rotation_step_radians: f64,
    pub maximum_total_rotation_radians: f64,
    pub maximum_rotation_steps: u64,
    pub minimum_rotation_relative_penalty_reduction: f64,
    pub maximum_centroid_offset_angstrom: f64,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_rigid_refinement_context_soa_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub receptor_atom_count: u64,
    pub ligand_atom_count: u64,
    pub receptor_x_angstrom: *const f64,
    pub receptor_y_angstrom: *const f64,
    pub receptor_z_angstrom: *const f64,
    pub receptor_vdw_radius_angstrom: *const f64,
    pub ligand_vdw_radius_angstrom: *const f64,
    pub pocket_center_angstrom: [f64; 3],
    pub pocket_radius_angstrom: f64,
    pub v2: bg_docking_rigid_v2_config_v1,
    pub v3: bg_docking_rigid_v3_config_v1,
    pub clearance_v4: bg_docking_rigid_v3_config_v1,
    pub reserved: [u64; 8],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_rigid_refinement_candidate_batch_soa_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub candidate_count: u64,
    pub ligand_atom_count: u64,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub candidate_mode: *const bg_docking_rigid_refinement_candidate_mode,
    pub max_steps: *const u64,
    pub x_angstrom: *const f64,
    pub y_angstrom: *const f64,
    pub z_angstrom: *const f64,
    pub reserved: [u64; 8],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_rigid_refinement_evidence_v1 {
    pub profile: bg_docking_rigid_refinement_profile,
    pub available: u8,
    pub reserved0: [u8; 3],
    pub accepted_steps: u64,
    pub accepted_translation_steps: u64,
    pub accepted_rotation_steps: u64,
    pub line_search_evaluation_count: u64,
    pub fallback_direction_step_count: u64,
    pub initial_penalty: f64,
    pub final_penalty: f64,
    pub total_translation_angstrom: [f64; 3],
    pub total_rotation_vector_radians: [f64; 3],
    pub total_rotation_path_radians: f64,
    pub initial_centroid_offset_angstrom: f64,
    pub final_centroid_offset_angstrom: f64,
    pub maximum_centroid_offset_angstrom: f64,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_rigid_refinement_row_v1 {
    pub slot_index: u32,
    pub status: bg_docking_rigid_refinement_row_status,
    pub failure_code: bg_docking_rigid_refinement_failure,
    pub candidate_mode: bg_docking_rigid_refinement_candidate_mode,
    pub selected_profile: bg_docking_rigid_refinement_profile,
    pub baseline_duplicate_of_v2: u8,
    pub clearance_evaluated: u8,
    pub clearance_selected: u8,
    pub reserved0: u8,
    pub selected: bg_docking_rigid_refinement_evidence_v1,
    pub comparison_v2: bg_docking_rigid_refinement_evidence_v1,
    pub baseline_v3: bg_docking_rigid_refinement_evidence_v1,
    pub clearance_v4: bg_docking_rigid_refinement_evidence_v1,
    pub reserved: [u64; 8],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_rigid_refinement_output_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub row_capacity: u64,
    pub row_count: u64,
    pub coordinate_capacity: u64,
    pub coordinate_count: u64,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub rows: *mut bg_docking_rigid_refinement_row_v1,
    pub selected_x_angstrom: *mut f64,
    pub selected_y_angstrom: *mut f64,
    pub selected_z_angstrom: *mut f64,
    pub comparison_v2_x_angstrom: *mut f64,
    pub comparison_v2_y_angstrom: *mut f64,
    pub comparison_v2_z_angstrom: *mut f64,
    pub baseline_v3_x_angstrom: *mut f64,
    pub baseline_v3_y_angstrom: *mut f64,
    pub baseline_v3_z_angstrom: *mut f64,
    pub clearance_v4_x_angstrom: *mut f64,
    pub clearance_v4_y_angstrom: *mut f64,
    pub clearance_v4_z_angstrom: *mut f64,
    pub molecular_execution_authorized: u8,
    pub existing_rank_auto_change_authorized: u8,
    pub customer_pose_emission_authorized: u8,
    pub production_claim_authorized: u8,
    pub reserved1: u32,
    pub reserved: [u64; 8],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_torsion_v7_context_soa_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub receptor_atom_count: u64,
    pub ligand_atom_count: u64,
    pub rotor_count: u64,
    pub internal_pair_count: u64,
    pub receptor_x_angstrom: *const f64,
    pub receptor_y_angstrom: *const f64,
    pub receptor_z_angstrom: *const f64,
    pub receptor_vdw_radius_angstrom: *const f64,
    pub ligand_vdw_radius_angstrom: *const f64,
    pub pocket_center_angstrom: [f64; 3],
    pub parent_atom_index: *const i32,
    pub rotatable_child_atom_index: *const u64,
    pub internal_pair_atom_i: *const u64,
    pub internal_pair_atom_j: *const u64,
    pub receptor_overlap_scale: f64,
    pub internal_overlap_scale: f64,
    pub internal_overlap_weight: f64,
    pub maximum_baseline_v6_steps: u64,
    pub maximum_torsions_evaluated: u64,
    pub maximum_torsion_steps: u64,
    pub maximum_backtracking_evaluations: u64,
    pub maximum_torsion_step_radians: f64,
    pub minimum_torsion_step_radians: f64,
    pub maximum_total_torsion_path_radians: f64,
    pub maximum_centroid_offset_angstrom: f64,
    pub minimum_selected_final_receptor_penalty: f64,
    pub maximum_selected_final_receptor_penalty: f64,
    pub penalty_tolerance: f64,
    pub epsilon_angstrom: f64,
    pub reserved: [u64; 8],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_torsion_v7_candidate_batch_soa_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub candidate_count: u64,
    pub ligand_atom_count: u64,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub candidate_state: *const bg_docking_torsion_v7_candidate_state,
    pub proposal_is_torsion_eligible: *const u8,
    pub max_steps: *const u64,
    pub baseline_v6_accepted_steps: *const u64,
    pub source_x_angstrom: *const f64,
    pub source_y_angstrom: *const f64,
    pub source_z_angstrom: *const f64,
    pub baseline_v6_x_angstrom: *const f64,
    pub baseline_v6_y_angstrom: *const f64,
    pub baseline_v6_z_angstrom: *const f64,
    pub baseline_v6_torsion_angles_radians: *const f64,
    pub reserved: [u64; 8],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_torsion_v7_row_v1 {
    pub slot_index: u32,
    pub status: bg_docking_torsion_v7_row_status,
    pub failure_code: bg_docking_torsion_v7_failure,
    pub skip_reason: bg_docking_torsion_v7_skip_reason,
    pub selection_reason: bg_docking_torsion_v7_selection_reason,
    pub selection_window_reachable: u8,
    pub evaluation_stopped_after_selection_window_became_unreachable: u8,
    pub torsion_evaluated: u8,
    pub torsion_variant_available: u8,
    pub torsion_selected: u8,
    pub reserved0: [u8; 3],
    pub torsion_step_budget: u64,
    pub fixed_objective_evaluation_count: u64,
    pub torsion_trial_objective_evaluation_count: u64,
    pub evaluated_torsion_steps: u64,
    pub accepted_torsion_steps: u64,
    pub baseline_v6_accepted_steps: u64,
    pub source_receptor_penalty: f64,
    pub source_internal_penalty: f64,
    pub source_combined_penalty: f64,
    pub baseline_receptor_penalty: f64,
    pub baseline_internal_penalty: f64,
    pub baseline_combined_penalty: f64,
    pub optimized_receptor_penalty: f64,
    pub optimized_internal_penalty: f64,
    pub optimized_combined_penalty: f64,
    pub final_receptor_penalty: f64,
    pub final_internal_penalty: f64,
    pub final_combined_penalty: f64,
    pub evaluated_total_torsion_path_radians: f64,
    pub accepted_total_torsion_path_radians: f64,
    pub reserved: [u64; 8],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_torsion_v7_move_v1 {
    pub slot_index: u32,
    pub move_index: u32,
    pub evaluated: u8,
    pub selected: u8,
    pub reserved0: u16,
    pub rotatable_child_atom_index: u64,
    pub delta_radians: f64,
    pub receptor_penalty: f64,
    pub internal_penalty: f64,
    pub combined_penalty: f64,
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_torsion_v7_output_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub row_capacity: u64,
    pub row_count: u64,
    pub move_capacity: u64,
    pub move_count: u64,
    pub coordinate_capacity: u64,
    pub coordinate_count: u64,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub rows: *mut bg_docking_torsion_v7_row_v1,
    pub moves: *mut bg_docking_torsion_v7_move_v1,
    pub optimized_x_angstrom: *mut f64,
    pub optimized_y_angstrom: *mut f64,
    pub optimized_z_angstrom: *mut f64,
    pub optimized_torsion_angles_radians: *mut f64,
    pub final_x_angstrom: *mut f64,
    pub final_y_angstrom: *mut f64,
    pub final_z_angstrom: *mut f64,
    pub final_torsion_angles_radians: *mut f64,
    pub molecular_execution_authorized: u8,
    pub existing_rank_auto_change_authorized: u8,
    pub customer_pose_emission_authorized: u8,
    pub production_claim_authorized: u8,
    pub reserved1: u32,
    pub reserved: [u64; 8],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_fixed64_refinement_input_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub candidate_count: u64,
    pub ligand_atom_count: u64,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub rmsd_threshold_angstrom: f64,
    pub candidate_mode: *const bg_docking_rigid_refinement_candidate_mode,
    pub rigid_max_steps: *const u64,
    pub proposal_is_torsion_eligible: *const u8,
    pub torsion_max_steps: *const u64,
    pub source_x_angstrom: *const f64,
    pub source_y_angstrom: *const f64,
    pub source_z_angstrom: *const f64,
    pub baseline_torsion_angles_radians: *const f64,
    pub source_quaternion_x: *const f64,
    pub source_quaternion_y: *const f64,
    pub source_quaternion_z: *const f64,
    pub source_quaternion_w: *const f64,
    pub reserved: [u64; 8],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_fixed64_refinement_row_v1 {
    pub slot_index: u32,
    pub status: bg_docking_fixed64_refinement_row_status,
    pub failure_stage: bg_docking_fixed64_refinement_failure_stage,
    pub coordinate_origin: bg_docking_fixed64_refinement_coordinate_origin,
    pub rigid_failure_code: bg_docking_rigid_refinement_failure,
    pub torsion_v7_failure_code: bg_docking_torsion_v7_failure,
    pub selected_rigid_profile: bg_docking_rigid_refinement_profile,
    pub downstream_candidate_state: bg_docking_scorer_v1_candidate_state,
    pub torsion_v7_applicable: u8,
    pub torsion_v7_selected: u8,
    pub coordinate_available: u8,
    pub reserved0: u8,
    pub coordinate_sha256: [u8; 32],
    pub reserved: [u64; 4],
}

#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct bg_docking_fixed64_refinement_output_v1 {
    pub struct_size: u32,
    pub abi_version: u32,
    pub row_capacity: u64,
    pub row_count: u64,
    pub coordinate_capacity: u64,
    pub coordinate_count: u64,
    pub quaternion_capacity: u64,
    pub quaternion_count: u64,
    pub unit_system: bg_unit_system,
    pub reserved0: u32,
    pub rows: *mut bg_docking_fixed64_refinement_row_v1,
    pub final_x_angstrom: *mut f64,
    pub final_y_angstrom: *mut f64,
    pub final_z_angstrom: *mut f64,
    pub final_quaternion_x: *mut f64,
    pub final_quaternion_y: *mut f64,
    pub final_quaternion_z: *mut f64,
    pub final_quaternion_w: *mut f64,
    pub molecular_execution_authorized: u8,
    pub reservation_authorized: u8,
    pub benchmark_execution_authorized: u8,
    pub existing_rank_auto_change_authorized: u8,
    pub customer_pose_emission_authorized: u8,
    pub production_claim_authorized: u8,
    pub reserved1: [u8; 2],
    pub reserved: [u64; 8],
}

unsafe extern "C" {
    pub fn bg_particle_mesh_reciprocal_abi_version() -> u32;
    pub fn bg_particle_mesh_reciprocal_abi_version_major() -> u32;
    pub fn bg_particle_mesh_reciprocal_abi_version_minor() -> u32;
    pub fn bg_particle_mesh_reciprocal_abi_version_string() -> *const c_char;
    pub fn bg_particle_mesh_reciprocal_parameters_v1_init(
        parameters: *mut bg_particle_mesh_reciprocal_parameters_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_particle_mesh_reciprocal_energy_v1_init(
        energy: *mut bg_particle_mesh_reciprocal_energy_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_particle_mesh_reciprocal_force_soa_v1_init(
        forces: *mut bg_particle_mesh_reciprocal_force_soa_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_particle_mesh_reciprocal_error_v1_init(
        error: *mut bg_particle_mesh_reciprocal_error_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_particle_mesh_reciprocal_model_v1_create(
        parameters: *const bg_particle_mesh_reciprocal_parameters_v1,
        out_model: *mut *mut bg_particle_mesh_reciprocal_model_v1,
        out_error: *mut bg_particle_mesh_reciprocal_error_v1,
    ) -> bg_status;
    pub fn bg_particle_mesh_reciprocal_model_v1_destroy(
        model: *mut bg_particle_mesh_reciprocal_model_v1,
    );
    pub fn bg_particle_mesh_reciprocal_model_v1_get_atom_count(
        model: *const bg_particle_mesh_reciprocal_model_v1,
        atom_count: *mut u64,
    ) -> bg_status;
    pub fn bg_particle_mesh_reciprocal_model_v1_profile_id() -> *const c_char;
    pub fn bg_context_evaluate_particle_mesh_reciprocal_v1(
        context: *const bg_context,
        system: *const bg_system,
        model: *const bg_particle_mesh_reciprocal_model_v1,
        out_energy: *mut bg_particle_mesh_reciprocal_energy_v1,
        out_forces: *mut bg_particle_mesh_reciprocal_force_soa_v1,
        out_error: *mut bg_particle_mesh_reciprocal_error_v1,
    ) -> bg_status;

    pub fn bg_particle_mesh_ewald_abi_version() -> u32;
    pub fn bg_particle_mesh_ewald_abi_version_major() -> u32;
    pub fn bg_particle_mesh_ewald_abi_version_minor() -> u32;
    pub fn bg_particle_mesh_ewald_abi_version_string() -> *const c_char;
    pub fn bg_particle_mesh_ewald_energy_components_v1_init(
        energy: *mut bg_particle_mesh_ewald_energy_components_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_particle_mesh_ewald_force_soa_v1_init(
        forces: *mut bg_particle_mesh_ewald_force_soa_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_particle_mesh_ewald_v1_profile_id() -> *const c_char;
    pub fn bg_context_evaluate_particle_mesh_ewald_v1(
        context: *const bg_context,
        system: *const bg_system,
        direct_model: *const bg_direct_ewald_model_v1,
        particle_mesh_reciprocal_model: *const bg_particle_mesh_reciprocal_model_v1,
        out_energy: *mut bg_particle_mesh_ewald_energy_components_v1,
        out_forces: *mut bg_particle_mesh_ewald_force_soa_v1,
        out_error: *mut bg_direct_ewald_error_v1,
    ) -> bg_status;

    pub fn bg_particle_mesh_ewald_composite_abi_version() -> u32;
    pub fn bg_particle_mesh_ewald_composite_abi_version_major() -> u32;
    pub fn bg_particle_mesh_ewald_composite_abi_version_minor() -> u32;
    pub fn bg_particle_mesh_ewald_composite_abi_version_string() -> *const c_char;
    pub fn bg_particle_mesh_ewald_composite_energy_components_v1_init(
        energy: *mut bg_particle_mesh_ewald_composite_energy_components_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_particle_mesh_ewald_composite_force_soa_v1_init(
        forces: *mut bg_particle_mesh_ewald_composite_force_soa_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_particle_mesh_ewald_composite_v1_profile_id() -> *const c_char;
    pub fn bg_context_evaluate_particle_mesh_ewald_composite_v1(
        context: *const bg_context,
        system: *const bg_system,
        forcefield: *const bg_forcefield,
        direct_model: *const bg_direct_ewald_model_v1,
        particle_mesh_reciprocal_model: *const bg_particle_mesh_reciprocal_model_v1,
        out_energy: *mut bg_particle_mesh_ewald_composite_energy_components_v1,
        out_forces: *mut bg_particle_mesh_ewald_composite_force_soa_v1,
        out_error: *mut bg_direct_ewald_error_v1,
    ) -> bg_status;

    pub fn bg_direct_ewald_abi_version() -> u32;
    pub fn bg_direct_ewald_abi_version_major() -> u32;
    pub fn bg_direct_ewald_abi_version_minor() -> u32;
    pub fn bg_direct_ewald_abi_version_string() -> *const c_char;
    pub fn bg_direct_ewald_parameters_v1_init(
        parameters: *mut bg_direct_ewald_parameters_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_direct_ewald_energy_components_v1_init(
        energy: *mut bg_direct_ewald_energy_components_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_direct_ewald_force_soa_v1_init(
        forces: *mut bg_direct_ewald_force_soa_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_direct_ewald_error_v1_init(
        error: *mut bg_direct_ewald_error_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_direct_ewald_model_v1_create(
        parameters: *const bg_direct_ewald_parameters_v1,
        out_model: *mut *mut bg_direct_ewald_model_v1,
        out_error: *mut bg_direct_ewald_error_v1,
    ) -> bg_status;
    pub fn bg_direct_ewald_model_v1_destroy(model: *mut bg_direct_ewald_model_v1);
    pub fn bg_direct_ewald_model_v1_get_atom_count(
        model: *const bg_direct_ewald_model_v1,
        atom_count: *mut u64,
    ) -> bg_status;
    pub fn bg_direct_ewald_model_v1_profile_id() -> *const c_char;
    pub fn bg_context_evaluate_direct_ewald_v1(
        context: *const bg_context,
        system: *const bg_system,
        model: *const bg_direct_ewald_model_v1,
        out_energy: *mut bg_direct_ewald_energy_components_v1,
        out_forces: *mut bg_direct_ewald_force_soa_v1,
        out_error: *mut bg_direct_ewald_error_v1,
    ) -> bg_status;
    pub fn bg_direct_ewald_composite_abi_version() -> u32;
    pub fn bg_direct_ewald_composite_abi_version_major() -> u32;
    pub fn bg_direct_ewald_composite_abi_version_minor() -> u32;
    pub fn bg_direct_ewald_composite_abi_version_string() -> *const c_char;
    pub fn bg_direct_ewald_composite_energy_components_v1_init(
        energy: *mut bg_direct_ewald_composite_energy_components_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_direct_ewald_composite_force_soa_v1_init(
        forces: *mut bg_direct_ewald_composite_force_soa_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_direct_ewald_composite_v1_profile_id() -> *const c_char;
    pub fn bg_context_evaluate_direct_ewald_composite_v1(
        context: *const bg_context,
        system: *const bg_system,
        forcefield: *const bg_forcefield,
        model: *const bg_direct_ewald_model_v1,
        out_energy: *mut bg_direct_ewald_composite_energy_components_v1,
        out_forces: *mut bg_direct_ewald_composite_force_soa_v1,
        out_error: *mut bg_direct_ewald_error_v1,
    ) -> bg_status;
    pub fn bg_direct_ewald_composite_dynamics_abi_version() -> u32;
    pub fn bg_direct_ewald_composite_dynamics_abi_version_major() -> u32;
    pub fn bg_direct_ewald_composite_dynamics_abi_version_minor() -> u32;
    pub fn bg_direct_ewald_composite_dynamics_abi_version_string() -> *const c_char;
    pub fn bg_direct_ewald_composite_dynamics_v1_profile_id() -> *const c_char;
    pub fn bg_direct_ewald_composite_simulation_v1_create(
        system: *const bg_system,
        forcefield: *const bg_forcefield,
        model: *const bg_direct_ewald_model_v1,
        constraints: *const bg_distance_constraints_v1,
        options: *const bg_simulation_options_v1,
        out_simulation: *mut *mut bg_direct_ewald_composite_simulation_v1,
        out_error: *mut bg_direct_ewald_error_v1,
    ) -> bg_status;
    pub fn bg_direct_ewald_composite_simulation_v1_destroy(
        simulation: *mut bg_direct_ewald_composite_simulation_v1,
    );
    pub fn bg_direct_ewald_composite_simulation_v1_get_particles(
        simulation: *const bg_direct_ewald_composite_simulation_v1,
        out_view: *mut bg_particle_soa_view,
    ) -> bg_status;
    pub fn bg_direct_ewald_composite_simulation_v1_get_absolute_step(
        simulation: *const bg_direct_ewald_composite_simulation_v1,
        absolute_step: *mut u64,
    ) -> bg_status;
    pub fn bg_context_integrate_direct_ewald_composite_v1(
        context: *const bg_context,
        simulation: *mut bg_direct_ewald_composite_simulation_v1,
        step_count: u64,
        out_report: *mut bg_dynamics_report_v1,
        out_error: *mut bg_direct_ewald_error_v1,
    ) -> bg_status;
    pub fn bg_direct_ewald_composite_simulation_v1_checkpoint_size(
        simulation: *const bg_direct_ewald_composite_simulation_v1,
        required_size: *mut u64,
    ) -> bg_status;
    pub fn bg_direct_ewald_composite_simulation_v1_checkpoint_write(
        simulation: *const bg_direct_ewald_composite_simulation_v1,
        buffer: *mut core::ffi::c_void,
        buffer_capacity: u64,
        written_size: *mut u64,
    ) -> bg_status;
    pub fn bg_direct_ewald_composite_simulation_v1_checkpoint_load(
        simulation: *mut bg_direct_ewald_composite_simulation_v1,
        buffer: *const core::ffi::c_void,
        buffer_size: u64,
    ) -> bg_status;

    pub fn bg_abi_version() -> u32;
    pub fn bg_abi_version_major() -> u32;
    pub fn bg_abi_version_minor() -> u32;
    pub fn bg_abi_version_string() -> *const c_char;
    pub fn bg_status_string(status: bg_status) -> *const c_char;
    pub fn bg_backend_string(backend: bg_backend) -> *const c_char;
    pub fn bg_unit_system_string(units: bg_unit_system) -> *const c_char;

    pub fn bg_last_error_message() -> *const c_char;
    pub fn bg_last_error_message_copy(
        buffer: *mut c_char,
        buffer_capacity: u64,
        required_size: *mut u64,
    ) -> bg_status;

    pub fn bg_context_options_init(
        options: *mut bg_context_options,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_particle_soa_init(
        particles: *mut bg_particle_soa,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_particle_soa_view_init(
        view: *mut bg_particle_soa_view,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_position_soa_init(
        positions: *mut bg_position_soa,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_forcefield_soa_v1_init(
        forcefield: *mut bg_forcefield_soa_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_force_soa_v1_init(
        forces: *mut bg_force_soa_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_energy_components_v1_init(
        energy: *mut bg_energy_components_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_distance_constraints_v1_init(
        constraints: *mut bg_distance_constraints_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_simulation_options_v1_init(
        options: *mut bg_simulation_options_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_minimizer_options_v1_init(
        options: *mut bg_minimizer_options_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_minimization_report_v1_init(
        report: *mut bg_minimization_report_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_dynamics_report_v1_init(
        report: *mut bg_dynamics_report_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_docking_fixed64_allocation_input_v1_init(
        input: *mut bg_docking_fixed64_allocation_input_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_docking_fixed64_allocation_output_v1_init(
        output: *mut bg_docking_fixed64_allocation_output_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_docking_fixed64_so3_input_v1_init(
        input: *mut bg_docking_fixed64_so3_input_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_docking_fixed64_so3_output_v1_init(
        output: *mut bg_docking_fixed64_so3_output_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_docking_fixed64_indexed_so3_input_v1_init(
        input: *mut bg_docking_fixed64_indexed_so3_input_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_docking_fixed64_indexed_so3_output_v1_init(
        output: *mut bg_docking_fixed64_indexed_so3_output_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_docking_fixed64_single_anchor_input_v1_init(
        input: *mut bg_docking_fixed64_single_anchor_input_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_docking_fixed64_single_anchor_output_v1_init(
        output: *mut bg_docking_fixed64_single_anchor_output_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_docking_fixed64_producer_input_v1_init(
        input: *mut bg_docking_fixed64_producer_input_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_docking_fixed64_producer_output_v1_init(
        output: *mut bg_docking_fixed64_producer_output_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_docking_fixed64_pipeline_input_v1_init(
        input: *mut bg_docking_fixed64_pipeline_input_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_docking_fixed64_pipeline_output_v1_init(
        output: *mut bg_docking_fixed64_pipeline_output_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_docking_fixed64_pipeline_input_v2_init(
        input: *mut bg_docking_fixed64_pipeline_input_v2,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_docking_fixed64_pipeline_output_v2_init(
        output: *mut bg_docking_fixed64_pipeline_output_v2,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_docking_geometric_admission_context_soa_v1_init(
        descriptor: *mut bg_docking_geometric_admission_context_soa_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_docking_geometric_admission_candidate_batch_soa_v1_init(
        batch: *mut bg_docking_geometric_admission_candidate_batch_soa_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_docking_geometric_admission_output_v1_init(
        output: *mut bg_docking_geometric_admission_output_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_docking_scorer_v1_context_soa_v1_init(
        descriptor: *mut bg_docking_scorer_v1_context_soa_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_docking_scorer_v1_candidate_batch_soa_v1_init(
        batch: *mut bg_docking_scorer_v1_candidate_batch_soa_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_docking_scorer_v1_output_v1_init(
        output: *mut bg_docking_scorer_v1_output_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_docking_pose_validity_context_soa_v1_init(
        descriptor: *mut bg_docking_pose_validity_context_soa_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_docking_pose_validity_candidate_batch_soa_v1_init(
        batch: *mut bg_docking_pose_validity_candidate_batch_soa_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_docking_pose_validity_output_v1_init(
        output: *mut bg_docking_pose_validity_output_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_docking_stable_top_k_input_v1_init(
        input: *mut bg_docking_stable_top_k_input_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_docking_stable_top_k_output_v1_init(
        output: *mut bg_docking_stable_top_k_output_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_docking_rmsd_cluster_input_v1_init(
        input: *mut bg_docking_rmsd_cluster_input_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_docking_rmsd_cluster_output_v1_init(
        output: *mut bg_docking_rmsd_cluster_output_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_docking_rigid_refinement_context_soa_v1_init(
        descriptor: *mut bg_docking_rigid_refinement_context_soa_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_docking_rigid_refinement_candidate_batch_soa_v1_init(
        batch: *mut bg_docking_rigid_refinement_candidate_batch_soa_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_docking_rigid_refinement_output_v1_init(
        output: *mut bg_docking_rigid_refinement_output_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_docking_torsion_v7_context_soa_v1_init(
        descriptor: *mut bg_docking_torsion_v7_context_soa_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_docking_torsion_v7_candidate_batch_soa_v1_init(
        batch: *mut bg_docking_torsion_v7_candidate_batch_soa_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_docking_torsion_v7_output_v1_init(
        output: *mut bg_docking_torsion_v7_output_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_docking_fixed64_refinement_input_v1_init(
        input: *mut bg_docking_fixed64_refinement_input_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;
    pub fn bg_docking_fixed64_refinement_output_v1_init(
        output: *mut bg_docking_fixed64_refinement_output_v1,
        caller_struct_size: usize,
        caller_abi_version: u32,
    ) -> bg_status;

    pub fn bg_backend_is_available(
        backend: bg_backend,
        device_ordinal: i32,
        available: *mut u8,
    ) -> bg_status;
    pub fn bg_context_create(
        options: *const bg_context_options,
        out_context: *mut *mut bg_context,
    ) -> bg_status;
    pub fn bg_context_destroy(context: *mut bg_context);
    pub fn bg_context_get_backend(
        context: *const bg_context,
        backend: *mut bg_backend,
    ) -> bg_status;
    pub fn bg_context_get_device_ordinal(
        context: *const bg_context,
        device_ordinal: *mut i32,
    ) -> bg_status;
    pub fn bg_context_get_unit_system(
        context: *const bg_context,
        unit_system: *mut bg_unit_system,
    ) -> bg_status;

    pub fn bg_docking_fixed64_allocation_v1_build(
        input: *const bg_docking_fixed64_allocation_input_v1,
        output: *mut bg_docking_fixed64_allocation_output_v1,
    ) -> bg_status;
    pub fn bg_docking_fixed64_so3_v1_generate(
        context: *const bg_context,
        input: *const bg_docking_fixed64_so3_input_v1,
        output: *mut bg_docking_fixed64_so3_output_v1,
    ) -> bg_status;
    pub fn bg_docking_fixed64_indexed_so3_v1_place(
        context: *const bg_context,
        input: *const bg_docking_fixed64_indexed_so3_input_v1,
        output: *mut bg_docking_fixed64_indexed_so3_output_v1,
    ) -> bg_status;
    pub fn bg_docking_fixed64_single_anchor_v1_place(
        context: *const bg_context,
        admission: *const bg_docking_geometric_admission_v1,
        input: *const bg_docking_fixed64_single_anchor_input_v1,
        output: *mut bg_docking_fixed64_single_anchor_output_v1,
    ) -> bg_status;
    pub fn bg_docking_fixed64_producer_v1_run(
        context: *const bg_context,
        admission: *const bg_docking_geometric_admission_v1,
        input: *const bg_docking_fixed64_producer_input_v1,
        output: *mut bg_docking_fixed64_producer_output_v1,
    ) -> bg_status;
    pub fn bg_docking_fixed64_producer_v1_profile_id() -> *const c_char;
    pub fn bg_docking_fixed64_pipeline_v1_create(
        context: *const bg_context,
        admission_descriptor: *const bg_docking_geometric_admission_context_soa_v1,
        rigid_descriptor: *const bg_docking_rigid_refinement_context_soa_v1,
        torsion_descriptor: *const bg_docking_torsion_v7_context_soa_v1,
        scorer_descriptor: *const bg_docking_scorer_v1_context_soa_v1,
        validity_descriptor: *const bg_docking_pose_validity_context_soa_v1,
        out_pipeline: *mut *mut bg_docking_fixed64_pipeline_v1,
    ) -> bg_status;
    pub fn bg_docking_fixed64_pipeline_v1_destroy(pipeline: *mut bg_docking_fixed64_pipeline_v1);
    pub fn bg_docking_fixed64_pipeline_v1_get_backend(
        pipeline: *const bg_docking_fixed64_pipeline_v1,
        backend: *mut bg_backend,
    ) -> bg_status;
    pub fn bg_docking_fixed64_pipeline_v1_profile_id() -> *const c_char;
    pub fn bg_docking_fixed64_pipeline_v1_run(
        context: *const bg_context,
        pipeline: *const bg_docking_fixed64_pipeline_v1,
        input: *const bg_docking_fixed64_pipeline_input_v1,
        producer_output: *mut bg_docking_fixed64_producer_output_v1,
        rigid_output: *mut bg_docking_rigid_refinement_output_v1,
        torsion_output: *mut bg_docking_torsion_v7_output_v1,
        scorer_output: *mut bg_docking_scorer_v1_output_v1,
        validity_output: *mut bg_docking_pose_validity_output_v1,
        ranking_output: *mut bg_docking_stable_top_k_output_v1,
        cluster_output: *mut bg_docking_rmsd_cluster_output_v1,
        refinement_output: *mut bg_docking_fixed64_refinement_output_v1,
        pipeline_output: *mut bg_docking_fixed64_pipeline_output_v1,
    ) -> bg_status;
    pub fn bg_docking_fixed64_pipeline_v2_create(
        context: *const bg_context,
        admission_descriptor: *const bg_docking_geometric_admission_context_soa_v1,
        rigid_descriptor: *const bg_docking_rigid_refinement_context_soa_v1,
        torsion_descriptor: *const bg_docking_torsion_v7_context_soa_v1,
        scorer_descriptor: *const bg_docking_scorer_v1_context_soa_v1,
        validity_descriptor: *const bg_docking_pose_validity_context_soa_v1,
        out_pipeline: *mut *mut bg_docking_fixed64_pipeline_v2,
    ) -> bg_status;
    pub fn bg_docking_fixed64_pipeline_v2_destroy(pipeline: *mut bg_docking_fixed64_pipeline_v2);
    pub fn bg_docking_fixed64_pipeline_v2_get_backend(
        pipeline: *const bg_docking_fixed64_pipeline_v2,
        backend: *mut bg_backend,
    ) -> bg_status;
    pub fn bg_docking_fixed64_pipeline_v2_profile_id() -> *const c_char;
    pub fn bg_docking_fixed64_pipeline_v2_run(
        context: *const bg_context,
        pipeline: *const bg_docking_fixed64_pipeline_v2,
        input: *const bg_docking_fixed64_pipeline_input_v2,
        producer_output: *mut bg_docking_fixed64_producer_output_v1,
        rigid_output: *mut bg_docking_rigid_refinement_output_v1,
        torsion_output: *mut bg_docking_torsion_v7_output_v1,
        refinement_output: *mut bg_docking_fixed64_refinement_output_v1,
        post_admission_output: *mut bg_docking_geometric_admission_output_v1,
        scorer_output: *mut bg_docking_scorer_v1_output_v1,
        validity_output: *mut bg_docking_pose_validity_output_v1,
        ranking_output: *mut bg_docking_stable_top_k_output_v1,
        cluster_output: *mut bg_docking_rmsd_cluster_output_v1,
        pipeline_output: *mut bg_docking_fixed64_pipeline_output_v2,
    ) -> bg_status;

    pub fn bg_docking_geometric_admission_v1_create(
        context: *const bg_context,
        descriptor: *const bg_docking_geometric_admission_context_soa_v1,
        out_admission: *mut *mut bg_docking_geometric_admission_v1,
    ) -> bg_status;
    pub fn bg_docking_geometric_admission_v1_destroy(
        admission: *mut bg_docking_geometric_admission_v1,
    );
    pub fn bg_docking_geometric_admission_v1_get_backend(
        admission: *const bg_docking_geometric_admission_v1,
        backend: *mut bg_backend,
    ) -> bg_status;
    pub fn bg_docking_geometric_admission_v1_evaluate_fixed64(
        context: *const bg_context,
        admission: *const bg_docking_geometric_admission_v1,
        candidates: *const bg_docking_geometric_admission_candidate_batch_soa_v1,
        output: *mut bg_docking_geometric_admission_output_v1,
    ) -> bg_status;

    pub fn bg_docking_scorer_v1_create(
        context: *const bg_context,
        descriptor: *const bg_docking_scorer_v1_context_soa_v1,
        out_scorer: *mut *mut bg_docking_scorer_v1,
    ) -> bg_status;
    pub fn bg_docking_scorer_v1_destroy(scorer: *mut bg_docking_scorer_v1);
    pub fn bg_docking_scorer_v1_get_backend(
        scorer: *const bg_docking_scorer_v1,
        backend: *mut bg_backend,
    ) -> bg_status;
    pub fn bg_docking_scorer_v1_score_fixed64(
        context: *const bg_context,
        scorer: *const bg_docking_scorer_v1,
        candidates: *const bg_docking_scorer_v1_candidate_batch_soa_v1,
        out_rows: *mut bg_docking_scorer_v1_output_v1,
    ) -> bg_status;
    pub fn bg_docking_pose_validity_v1_create(
        context: *const bg_context,
        descriptor: *const bg_docking_pose_validity_context_soa_v1,
        out_validity: *mut *mut bg_docking_pose_validity_v1,
    ) -> bg_status;
    pub fn bg_docking_pose_validity_v1_destroy(validity: *mut bg_docking_pose_validity_v1);
    pub fn bg_docking_pose_validity_v1_get_backend(
        validity: *const bg_docking_pose_validity_v1,
        backend: *mut bg_backend,
    ) -> bg_status;
    pub fn bg_docking_pose_validity_v1_evaluate_fixed64(
        context: *const bg_context,
        validity: *const bg_docking_pose_validity_v1,
        candidates: *const bg_docking_pose_validity_candidate_batch_soa_v1,
        out_rows: *mut bg_docking_pose_validity_output_v1,
    ) -> bg_status;
    pub fn bg_docking_stable_top_k_v1_create(
        context: *const bg_context,
        out_ranker: *mut *mut bg_docking_stable_top_k_v1,
    ) -> bg_status;
    pub fn bg_docking_stable_top_k_v1_destroy(ranker: *mut bg_docking_stable_top_k_v1);
    pub fn bg_docking_stable_top_k_v1_get_backend(
        ranker: *const bg_docking_stable_top_k_v1,
        backend: *mut bg_backend,
    ) -> bg_status;
    pub fn bg_docking_stable_top_k_v1_rank_fixed64(
        context: *const bg_context,
        ranker: *const bg_docking_stable_top_k_v1,
        input: *const bg_docking_stable_top_k_input_v1,
        output: *mut bg_docking_stable_top_k_output_v1,
    ) -> bg_status;
    pub fn bg_docking_fixed64_downstream_v1_create(
        context: *const bg_context,
        scorer_descriptor: *const bg_docking_scorer_v1_context_soa_v1,
        validity_descriptor: *const bg_docking_pose_validity_context_soa_v1,
        out_pipeline: *mut *mut bg_docking_fixed64_downstream_v1,
    ) -> bg_status;
    pub fn bg_docking_fixed64_downstream_v1_destroy(
        pipeline: *mut bg_docking_fixed64_downstream_v1,
    );
    pub fn bg_docking_fixed64_downstream_v1_get_backend(
        pipeline: *const bg_docking_fixed64_downstream_v1,
        backend: *mut bg_backend,
    ) -> bg_status;
    pub fn bg_docking_fixed64_downstream_v1_run(
        context: *const bg_context,
        pipeline: *const bg_docking_fixed64_downstream_v1,
        candidates: *const bg_docking_scorer_v1_candidate_batch_soa_v1,
        quaternion_x: *const f64,
        quaternion_y: *const f64,
        quaternion_z: *const f64,
        quaternion_w: *const f64,
        scorer_output: *mut bg_docking_scorer_v1_output_v1,
        validity_output: *mut bg_docking_pose_validity_output_v1,
        ranking_output: *mut bg_docking_stable_top_k_output_v1,
    ) -> bg_status;
    pub fn bg_docking_stable_top_k_v1_cluster_direct_rmsd_fixed64(
        context: *const bg_context,
        ranker: *const bg_docking_stable_top_k_v1,
        input: *const bg_docking_rmsd_cluster_input_v1,
        output: *mut bg_docking_rmsd_cluster_output_v1,
    ) -> bg_status;
    pub fn bg_docking_rigid_refinement_create(
        context: *const bg_context,
        descriptor: *const bg_docking_rigid_refinement_context_soa_v1,
        out_refiner: *mut *mut bg_docking_rigid_refinement,
    ) -> bg_status;
    pub fn bg_docking_rigid_refinement_destroy(refiner: *mut bg_docking_rigid_refinement);
    pub fn bg_docking_rigid_refinement_get_backend(
        refiner: *const bg_docking_rigid_refinement,
        backend: *mut bg_backend,
    ) -> bg_status;
    pub fn bg_docking_rigid_refinement_fixed64(
        context: *const bg_context,
        refiner: *const bg_docking_rigid_refinement,
        candidates: *const bg_docking_rigid_refinement_candidate_batch_soa_v1,
        output: *mut bg_docking_rigid_refinement_output_v1,
    ) -> bg_status;
    pub fn bg_docking_torsion_v7_create(
        context: *const bg_context,
        descriptor: *const bg_docking_torsion_v7_context_soa_v1,
        out_refiner: *mut *mut bg_docking_torsion_v7,
    ) -> bg_status;
    pub fn bg_docking_torsion_v7_destroy(refiner: *mut bg_docking_torsion_v7);
    pub fn bg_docking_torsion_v7_get_backend(
        refiner: *const bg_docking_torsion_v7,
        backend: *mut bg_backend,
    ) -> bg_status;
    pub fn bg_docking_torsion_v7_refine_fixed64(
        context: *const bg_context,
        refiner: *const bg_docking_torsion_v7,
        candidates: *const bg_docking_torsion_v7_candidate_batch_soa_v1,
        output: *mut bg_docking_torsion_v7_output_v1,
    ) -> bg_status;
    pub fn bg_docking_fixed64_refinement_pipeline_v1_create(
        context: *const bg_context,
        rigid_descriptor: *const bg_docking_rigid_refinement_context_soa_v1,
        torsion_descriptor: *const bg_docking_torsion_v7_context_soa_v1,
        scorer_descriptor: *const bg_docking_scorer_v1_context_soa_v1,
        validity_descriptor: *const bg_docking_pose_validity_context_soa_v1,
        out_pipeline: *mut *mut bg_docking_fixed64_refinement_pipeline_v1,
    ) -> bg_status;
    pub fn bg_docking_fixed64_refinement_pipeline_v1_destroy(
        pipeline: *mut bg_docking_fixed64_refinement_pipeline_v1,
    );
    pub fn bg_docking_fixed64_refinement_pipeline_v1_get_backend(
        pipeline: *const bg_docking_fixed64_refinement_pipeline_v1,
        backend: *mut bg_backend,
    ) -> bg_status;
    pub fn bg_docking_fixed64_refinement_pipeline_v1_run(
        context: *const bg_context,
        pipeline: *const bg_docking_fixed64_refinement_pipeline_v1,
        input: *const bg_docking_fixed64_refinement_input_v1,
        rigid_output: *mut bg_docking_rigid_refinement_output_v1,
        torsion_output: *mut bg_docking_torsion_v7_output_v1,
        scorer_output: *mut bg_docking_scorer_v1_output_v1,
        validity_output: *mut bg_docking_pose_validity_output_v1,
        ranking_output: *mut bg_docking_stable_top_k_output_v1,
        cluster_output: *mut bg_docking_rmsd_cluster_output_v1,
        pipeline_output: *mut bg_docking_fixed64_refinement_output_v1,
    ) -> bg_status;

    pub fn bg_system_create(
        particles: *const bg_particle_soa,
        out_system: *mut *mut bg_system,
    ) -> bg_status;
    pub fn bg_system_destroy(system: *mut bg_system);
    pub fn bg_system_get_particle_count(
        system: *const bg_system,
        particle_count: *mut u64,
    ) -> bg_status;
    pub fn bg_system_get_unit_system(
        system: *const bg_system,
        unit_system: *mut bg_unit_system,
    ) -> bg_status;
    pub fn bg_system_get_particles(
        system: *const bg_system,
        out_view: *mut bg_particle_soa_view,
    ) -> bg_status;
    pub fn bg_system_set_positions(
        system: *mut bg_system,
        positions: *const bg_position_soa,
    ) -> bg_status;

    pub fn bg_forcefield_create(
        parameters: *const bg_forcefield_soa_v1,
        out_forcefield: *mut *mut bg_forcefield,
    ) -> bg_status;
    pub fn bg_forcefield_destroy(forcefield: *mut bg_forcefield);
    pub fn bg_forcefield_get_atom_count(
        forcefield: *const bg_forcefield,
        atom_count: *mut u64,
    ) -> bg_status;

    pub fn bg_context_evaluate(
        context: *const bg_context,
        system: *const bg_system,
        forcefield: *const bg_forcefield,
        out_energy: *mut bg_energy_components_v1,
        out_forces: *mut bg_force_soa_v1,
    ) -> bg_status;

    pub fn bg_simulation_create(
        system: *const bg_system,
        forcefield: *const bg_forcefield,
        constraints: *const bg_distance_constraints_v1,
        options: *const bg_simulation_options_v1,
        out_simulation: *mut *mut bg_simulation,
    ) -> bg_status;
    pub fn bg_simulation_destroy(simulation: *mut bg_simulation);
    pub fn bg_simulation_get_particles(
        simulation: *const bg_simulation,
        out_view: *mut bg_particle_soa_view,
    ) -> bg_status;
    pub fn bg_simulation_get_absolute_step(
        simulation: *const bg_simulation,
        absolute_step: *mut u64,
    ) -> bg_status;
    pub fn bg_context_minimize(
        context: *const bg_context,
        simulation: *mut bg_simulation,
        options: *const bg_minimizer_options_v1,
        out_report: *mut bg_minimization_report_v1,
    ) -> bg_status;
    pub fn bg_context_integrate(
        context: *const bg_context,
        simulation: *mut bg_simulation,
        step_count: u64,
        out_report: *mut bg_dynamics_report_v1,
    ) -> bg_status;
    pub fn bg_simulation_checkpoint_size(
        simulation: *const bg_simulation,
        required_size: *mut u64,
    ) -> bg_status;
    pub fn bg_simulation_checkpoint_write(
        simulation: *const bg_simulation,
        buffer: *mut core::ffi::c_void,
        buffer_capacity: u64,
        written_size: *mut u64,
    ) -> bg_status;
    pub fn bg_simulation_checkpoint_load(
        simulation: *mut bg_simulation,
        buffer: *const core::ffi::c_void,
        buffer_size: u64,
    ) -> bg_status;
}
