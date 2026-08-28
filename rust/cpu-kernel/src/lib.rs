//! Pure-Rust deterministic CPU provider for the private native engine ABI.
//!
//! The public C ABI owns validation, handles, and transaction boundaries. This
//! crate supplies an independently implemented scalar kernel and a versioned,
//! hidden provider boundary used by the C++ dispatcher.

mod direct_ewald;
mod docking_fixed64_allocation;
mod docking_fixed64_indexed_so3;
mod docking_fixed64_single_anchor;
mod docking_fixed64_so3;
mod docking_rigid_refinement;
mod docking_torsion_v7;
mod kernel;
mod particle_mesh_reciprocal;

use core::mem::{align_of, size_of};
use core::ptr;
use std::ffi::c_void;
use std::panic::{catch_unwind, AssertUnwindSafe};

use betelgeuze_docking_search::{
    cluster_native_fixed64_direct_rmsd_kernel, evaluate_fixed64_geometric_metrics,
    rank_native_fixed64_stable_top_k_kernel, Fixed64GeometricErrorCode, Fixed64GeometricInput,
    NativeFixed64RmsdClusterErrorCode, NativeFixed64RmsdClusterInputRow,
    NativeFixed64StableTopKInputRow, NativeFixed64ValidityBackend, NativeFixed64ValidityChecks,
    NativeFixed64ValidityConfig, NativeFixed64ValidityContext, NativeFixed64ValidityFailureCode,
    NativeFixed64ValidityKernelOutcome, NativeFixed64ValidityMeasurements,
    NativeFixed64ValidityRowStatus, NativeScorerV1Atom, NativeScorerV1Backend,
    NativeScorerV1Config, NativeScorerV1Context, NativeScorerV1Donor, NativeScorerV1FailureCode,
    NativeScorerV1KernelOutcome, NativeScorerV1RowStatus, Quaternion, Vec3,
    FIXED64_CANDIDATE_COUNT, FIXED64_MAX_ABSOLUTE_COORDINATE_ANGSTROM,
    FIXED64_MAX_BATCH_EXACT_PAIR_EVALUATIONS, FIXED64_MAX_LIGAND_ATOMS, FIXED64_MAX_RECEPTOR_ATOMS,
    HARD_REJECTION_MINIMUM_VDW_RATIO, NATIVE_FIXED64_TOP_K_LIMIT,
};
use kernel::{AngleSoa, BondSoa, ForceField, Pair, PairScale, System, TorsionSoa};

const PROVIDER_ABI_VERSION: u32 = 1;
const STATUS_OK: i32 = 0;
const STATUS_INVALID_ARGUMENT: i32 = 1;
const STATUS_ABI_MISMATCH: i32 = 2;
const STATUS_CAPACITY_OVERFLOW: i32 = 6;
const STATUS_INTERNAL_ERROR: i32 = 9;
const STATUS_NUMERICAL_ERROR: i32 = 10;
const ERROR_CAPACITY: usize = 256;
const UNIT_SYSTEM_ANGSTROM_KCAL_MOL: i32 = 1;
const DOCKING_CANDIDATE_INACTIVE: i32 = 0;
const DOCKING_CANDIDATE_ACTIVE: i32 = 1;
const DOCKING_ROW_SCORED: i32 = 1;
const DOCKING_ROW_TYPED_FAILURE: i32 = 2;
const DOCKING_FAILURE_NONE: i32 = 0;
const DOCKING_FAILURE_UPSTREAM_NOT_ADMITTED: i32 = 1;
const DOCKING_FAILURE_INVALID_CANDIDATE_COORDINATES: i32 = 2;
const DOCKING_FAILURE_RECEPTOR_PAIR_CAPACITY: i32 = 3;
const DOCKING_FAILURE_LIGAND_PAIR_CAPACITY: i32 = 4;
const DOCKING_FAILURE_DEGENERATE_ROTOR: i32 = 5;
const DOCKING_FAILURE_NONFINITE_SCORE: i32 = 6;
const VALIDITY_CANDIDATE_UPSTREAM_FAILURE: i32 = 0;
const VALIDITY_CANDIDATE_EVALUATE: i32 = 1;
const VALIDITY_ROW_EVALUATED: i32 = 1;
const VALIDITY_ROW_UPSTREAM_SCORER_FAILURE: i32 = 2;
const VALIDITY_ROW_TYPED_FAILURE: i32 = 3;
const VALIDITY_FAILURE_NONE: i32 = 0;
const VALIDITY_FAILURE_UPSTREAM_SCORER: i32 = 1;
const VALIDITY_FAILURE_INVALID_CANDIDATE_COORDINATES: i32 = 2;
const VALIDITY_FAILURE_LIGAND_PAIR_CAPACITY: i32 = 3;
const VALIDITY_FAILURE_RECEPTOR_CROSS_CAPACITY: i32 = 4;
const VALIDITY_FAILURE_ELEMENT_LIGAND_PAIR_CAPACITY: i32 = 5;
const VALIDITY_FAILURE_ELEMENT_RECEPTOR_CANDIDATE_CAPACITY: i32 = 6;
const VALIDITY_FAILURE_NONFINITE_DERIVED_MEASUREMENT: i32 = 7;
const VALIDITY_CHECK_PROPER_ROTATION: u32 = 1 << 0;
const VALIDITY_CHECK_BOND_LENGTHS: u32 = 1 << 1;
const VALIDITY_CHECK_LIGAND_SELF_CLASH: u32 = 1 << 2;
const VALIDITY_CHECK_RECEPTOR_LIGAND_CLASH: u32 = 1 << 3;
const VALIDITY_CHECK_CHIRALITY: u32 = 1 << 4;
const VALIDITY_CHECK_DECLARED_POCKET: u32 = 1 << 5;
const VALIDITY_CHECK_ELEMENT_LIGAND_VDW: u32 = 1 << 6;
const VALIDITY_CHECK_ELEMENT_RECEPTOR_VDW: u32 = 1 << 7;
const VALIDITY_CHECK_ALL: u32 = 0xff;
const STABLE_TOP_K_LIMIT: u32 = NATIVE_FIXED64_TOP_K_LIMIT as u32;
const RMSD_CLUSTER_ROW_CLUSTERED: i32 = 1;
const RMSD_CLUSTER_ROW_UPSTREAM_NOT_VALID: i32 = 2;
const GEOMETRIC_CANDIDATE_UPSTREAM_FAILURE: i32 = 0;
const GEOMETRIC_CANDIDATE_EVALUATE: i32 = 1;
const GEOMETRIC_ROW_EVALUATED: i32 = 1;
const GEOMETRIC_ROW_UPSTREAM_FAILURE: i32 = 2;
const GEOMETRIC_ROW_TYPED_FAILURE: i32 = 3;
const GEOMETRIC_FAILURE_NONE: i32 = 0;
const GEOMETRIC_FAILURE_UPSTREAM_NOT_AVAILABLE: i32 = 1;
const GEOMETRIC_FAILURE_INVALID_CANDIDATE_COORDINATES: i32 = 2;
const GEOMETRIC_FAILURE_NONFINITE_DERIVED_MEASUREMENT: i32 = 3;
const GEOMETRIC_DECISION_NOT_EVALUATED: i32 = 0;
const GEOMETRIC_DECISION_ACCEPTED: i32 = 1;
const GEOMETRIC_DECISION_SEVERE_PENETRATION_REJECTED: i32 = 2;

#[repr(C)]
pub struct SystemV1 {
    struct_size: u32,
    abi_version: u32,
    atom_count: usize,
    position_x: *const f64,
    position_y: *const f64,
    position_z: *const f64,
    charge: *const f64,
    reserved: [u64; 4],
}

#[repr(C)]
pub struct BondSoaV1 {
    count: usize,
    atom_i: *const usize,
    atom_j: *const usize,
    equilibrium: *const f64,
    force_constant: *const f64,
}

#[repr(C)]
pub struct AngleSoaV1 {
    count: usize,
    atom_i: *const usize,
    atom_j: *const usize,
    atom_k: *const usize,
    equilibrium: *const f64,
    force_constant: *const f64,
}

#[repr(C)]
pub struct TorsionSoaV1 {
    count: usize,
    atom_i: *const usize,
    atom_j: *const usize,
    atom_k: *const usize,
    atom_l: *const usize,
    periodicity: *const u32,
    phase: *const f64,
    amplitude: *const f64,
}

#[repr(C)]
pub struct ForceFieldV1 {
    struct_size: u32,
    abi_version: u32,
    atom_count: usize,
    sigma: *const f64,
    epsilon: *const f64,
    bonds: BondSoaV1,
    angles: AngleSoaV1,
    torsions: TorsionSoaV1,
    exclusion_count: usize,
    exclusions: *const Pair,
    pair_scale_count: usize,
    pair_scales: *const PairScale,
    periodic_axes_mask: u32,
    reserved0: u32,
    cell_lengths: [f64; 3],
    cutoff: f64,
    switch_start: f64,
    dielectric: f64,
    screening_kappa: f64,
    minimum_pair_distance: f64,
    reserved: [u64; 4],
}

#[repr(C)]
pub struct EnergyV1 {
    struct_size: u32,
    abi_version: u32,
    harmonic_bond: f64,
    harmonic_angle: f64,
    periodic_torsion: f64,
    lennard_jones: f64,
    coulomb: f64,
    total: f64,
    reserved: [u64; 4],
}

#[repr(C)]
pub struct ForceOutputV1 {
    struct_size: u32,
    abi_version: u32,
    capacity: usize,
    x: *mut f64,
    y: *mut f64,
    z: *mut f64,
    reserved: [u64; 4],
}

#[repr(C)]
pub struct ErrorV1 {
    struct_size: u32,
    abi_version: u32,
    message: [u8; ERROR_CAPACITY],
    reserved: [u64; 4],
}

#[repr(C)]
pub struct DockingGeometricAdmissionContextSoaV1 {
    struct_size: u32,
    abi_version: u32,
    unit_system: i32,
    reserved0: u32,
    receptor_atom_count: u64,
    ligand_atom_count: u64,
    receptor_x_angstrom: *const f64,
    receptor_y_angstrom: *const f64,
    receptor_z_angstrom: *const f64,
    receptor_vdw_radius_angstrom: *const f64,
    ligand_vdw_radius_angstrom: *const f64,
    ligand_heavy_atom_mask: *const u8,
    pocket_center_angstrom: [f64; 3],
    pocket_radius_angstrom: f64,
    hard_rejection_minimum_vdw_ratio: f64,
    max_batch_exact_pair_evaluations: u64,
    authority_input_receipt_sha256: [u8; 32],
    receptor_system_sha256: [u8; 32],
    ligand_system_sha256: [u8; 32],
    backend_receipt_sha256: [u8; 32],
    reserved: [u64; 8],
}

#[repr(C)]
pub struct DockingGeometricAdmissionCandidateBatchSoaV1 {
    struct_size: u32,
    abi_version: u32,
    candidate_count: u64,
    ligand_atom_count: u64,
    unit_system: i32,
    reserved0: u32,
    candidate_state: *const i32,
    x_angstrom: *const f64,
    y_angstrom: *const f64,
    z_angstrom: *const f64,
    reserved: [u64; 4],
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct DockingGeometricAdmissionRowV1 {
    slot_index: u32,
    status: i32,
    failure_code: i32,
    decision: i32,
    rank_eligible: u8,
    reserved0: [u8; 3],
    reserved1: u32,
    ligand_atom_count: u64,
    receptor_atom_count: u64,
    exact_pair_count: u64,
    penetration_pair_count: u64,
    unique_ligand_penetration_atom_count: u64,
    unique_ligand_heavy_atom_penetration_count: u64,
    raw_minimum_distance_angstrom: f64,
    minimum_vdw_surface_gap_angstrom: f64,
    minimum_vdw_ratio: f64,
    sphere_overlap_proxy_angstrom3: f64,
    pocket_escape_angstrom: f64,
    row_receipt_sha256: [u8; 32],
}

struct GeometricAdmissionState {
    input: Fixed64GeometricInput,
    ligand_atom_count: usize,
    receptor_atom_count: usize,
    max_batch_exact_pair_evaluations: usize,
}

#[repr(C)]
pub struct DockingScorerContextSoaV1 {
    struct_size: u32,
    abi_version: u32,
    unit_system: i32,
    reserved0: u32,
    receptor_atom_count: u64,
    ligand_atom_count: u64,
    receptor_x_angstrom: *const f64,
    receptor_y_angstrom: *const f64,
    receptor_z_angstrom: *const f64,
    receptor_charge_elementary: *const f64,
    receptor_vdw_radius_angstrom: *const f64,
    receptor_epsilon_kcal_per_mol: *const f64,
    receptor_hydrophobic: *const u8,
    receptor_acceptor: *const u8,
    ligand_reference_x_angstrom: *const f64,
    ligand_reference_y_angstrom: *const f64,
    ligand_reference_z_angstrom: *const f64,
    ligand_charge_elementary: *const f64,
    ligand_vdw_radius_angstrom: *const f64,
    ligand_epsilon_kcal_per_mol: *const f64,
    ligand_hydrophobic: *const u8,
    ligand_acceptor: *const u8,
    receptor_donor_count: u64,
    receptor_donor_atom_index: *const u64,
    receptor_hydrogen_atom_index: *const u64,
    ligand_donor_count: u64,
    ligand_donor_atom_index: *const u64,
    ligand_hydrogen_atom_index: *const u64,
    ligand_exclusion_count: u64,
    ligand_exclusion_atom_i: *const u64,
    ligand_exclusion_atom_j: *const u64,
    rotor_count: u64,
    rotor_atom_i: *const u64,
    rotor_atom_j: *const u64,
    rotor_atom_k: *const u64,
    rotor_atom_l: *const u64,
    pocket_center_angstrom: [f64; 3],
    pocket_radius_angstrom: f64,
    weights: [f64; 8],
    electrostatic_dielectric: f64,
    pair_cutoff_angstrom: f64,
    hbond_distance_max_angstrom: f64,
    polar_burial_distance_angstrom: f64,
    max_receptor_candidate_pairs: u64,
    max_ligand_pair_checks: u64,
    authority_input_receipt_sha256: [u8; 32],
    receptor_system_sha256: [u8; 32],
    ligand_system_sha256: [u8; 32],
    backend_receipt_sha256: [u8; 32],
    reserved: [u64; 8],
}

#[repr(C)]
pub struct DockingScorerCandidateBatchSoaV1 {
    struct_size: u32,
    abi_version: u32,
    candidate_count: u64,
    ligand_atom_count: u64,
    unit_system: i32,
    reserved0: u32,
    candidate_state: *const i32,
    x_angstrom: *const f64,
    y_angstrom: *const f64,
    z_angstrom: *const f64,
    reserved: [u64; 4],
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct DockingScorerRowV1 {
    slot_index: u32,
    status: i32,
    failure_code: i32,
    reserved0: u32,
    weighted_terms: [f64; 8],
    total_score: f64,
    receptor_candidate_pair_count: u64,
    ligand_pair_count: u64,
    hbond_count: u64,
    hydrophobic_contact_count: u64,
    buried_polar_count: u64,
    reserved: [u64; 4],
}

#[repr(C)]
pub struct DockingPoseValidityContextSoaV1 {
    struct_size: u32,
    abi_version: u32,
    unit_system: i32,
    reserved0: u32,
    receptor_atom_count: u64,
    ligand_atom_count: u64,
    receptor_x_angstrom: *const f64,
    receptor_y_angstrom: *const f64,
    receptor_z_angstrom: *const f64,
    receptor_vdw_radius_angstrom: *const f64,
    ligand_reference_x_angstrom: *const f64,
    ligand_reference_y_angstrom: *const f64,
    ligand_reference_z_angstrom: *const f64,
    ligand_vdw_radius_angstrom: *const f64,
    bond_count: u64,
    bond_atom_i: *const u64,
    bond_atom_j: *const u64,
    ligand_exclusion_count: u64,
    ligand_exclusion_atom_i: *const u64,
    ligand_exclusion_atom_j: *const u64,
    chirality_center_count: u64,
    chirality_center_atom: *const u64,
    chirality_atom_i: *const u64,
    chirality_atom_j: *const u64,
    chirality_atom_k: *const u64,
    pocket_center_angstrom: [f64; 3],
    pocket_radius_angstrom: f64,
    bond_length_tolerance_angstrom: f64,
    ligand_self_clash_angstrom: f64,
    receptor_ligand_clash_angstrom: f64,
    rotation_tolerance: f64,
    chirality_volume_tolerance: f64,
    severe_overlap_scale: f64,
    contact_cell_size_angstrom: f64,
    max_pair_checks: u64,
    max_cross_checks: u64,
    max_element_ligand_pair_checks: u64,
    max_element_receptor_candidate_pairs: u64,
    authority_input_receipt_sha256: [u8; 32],
    receptor_system_sha256: [u8; 32],
    ligand_system_sha256: [u8; 32],
    scorer_context_receipt_sha256: [u8; 32],
    backend_receipt_sha256: [u8; 32],
    contact_policy_sha256: [u8; 32],
    reserved: [u64; 8],
}

#[repr(C)]
pub struct DockingPoseValidityCandidateBatchSoaV1 {
    struct_size: u32,
    abi_version: u32,
    candidate_count: u64,
    ligand_atom_count: u64,
    unit_system: i32,
    reserved0: u32,
    candidate_state: *const i32,
    upstream_scorer_failure_code: *const i32,
    quaternion_x: *const f64,
    quaternion_y: *const f64,
    quaternion_z: *const f64,
    quaternion_w: *const f64,
    x_angstrom: *const f64,
    y_angstrom: *const f64,
    z_angstrom: *const f64,
    reserved: [u64; 4],
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct DockingPoseValidityRowV1 {
    slot_index: u32,
    status: i32,
    failure_code: i32,
    upstream_scorer_failure_code: i32,
    passed_check_mask: u32,
    blocker_mask: u32,
    observed_count: u64,
    atom_count: u64,
    rotation_orthogonality_max_error: f64,
    rotation_determinant: f64,
    max_bond_length_delta_angstrom: f64,
    minimum_ligand_nonbonded_distance_angstrom: f64,
    evaluated_ligand_nonbonded_pair_count: u64,
    excluded_ligand_pair_count: u64,
    minimum_receptor_ligand_distance_angstrom: f64,
    evaluated_receptor_ligand_pair_count: u64,
    minimum_declared_chiral_volume: f64,
    declared_chirality_center_count: u64,
    maximum_pocket_center_distance_angstrom: f64,
    element_vdw_ligand_pair_count: u64,
    element_vdw_ligand_severe_overlap_count: u64,
    element_vdw_ligand_minimum_distance_angstrom: f64,
    element_vdw_ligand_minimum_ratio: f64,
    element_vdw_receptor_candidate_pair_count: u64,
    element_vdw_receptor_full_cartesian_pair_count: u64,
    element_vdw_receptor_cell_count: u64,
    element_vdw_receptor_severe_overlap_count: u64,
    element_vdw_receptor_minimum_distance_angstrom: f64,
    element_vdw_receptor_minimum_ratio: f64,
    reserved: [u64; 4],
}

#[repr(C)]
pub struct DockingStableTopKInputV1 {
    struct_size: u32,
    abi_version: u32,
    candidate_count: u64,
    top_k_limit: u32,
    unit_system: i32,
    scorer_rows: *const DockingScorerRowV1,
    validity_rows: *const DockingPoseValidityRowV1,
    coordinate_sha256: *const u8,
    reserved: [u64; 4],
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct DockingStableTopKRowV1 {
    slot_index: u32,
    rank_eligible: u8,
    valid_rank_eligible: u8,
    reserved0: u16,
    stable_rank: u32,
    stable_valid_rank: u32,
    total_score: f64,
    coordinate_sha256: [u8; 32],
    reserved: [u64; 4],
}

struct StableTopKState;

#[repr(C)]
pub struct DockingRmsdClusterInputV1 {
    struct_size: u32,
    abi_version: u32,
    candidate_count: u64,
    ligand_atom_count: u64,
    valid_index_count: u64,
    top_k_limit: u32,
    unit_system: i32,
    rmsd_threshold_angstrom: f64,
    ranking_rows: *const DockingStableTopKRowV1,
    valid_slot_indices: *const u32,
    x_angstrom: *const f64,
    y_angstrom: *const f64,
    z_angstrom: *const f64,
    reserved: [u64; 4],
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct DockingRmsdClusterRowV1 {
    slot_index: u32,
    status: i32,
    cluster_eligible: u8,
    representative: u8,
    top_k_representative: u8,
    reserved0: u8,
    stable_valid_rank: u32,
    cluster_id: u32,
    representative_slot_index: u32,
    cluster_rank: u32,
    top_k_rank: u32,
    cluster_size: u32,
    reserved1: u32,
    direct_rmsd_to_representative_angstrom: f64,
    coordinate_sha256: [u8; 32],
    reserved: [u64; 4],
}

#[derive(Clone, Copy)]
struct ProviderError {
    status: i32,
    message: &'static str,
}

type ForceChannels<'a> = (&'a mut [f64], &'a mut [f64], &'a mut [f64]);

impl ProviderError {
    const fn invalid(message: &'static str) -> Self {
        Self {
            status: STATUS_INVALID_ARGUMENT,
            message,
        }
    }

    const fn abi(message: &'static str) -> Self {
        Self {
            status: STATUS_ABI_MISMATCH,
            message,
        }
    }

    const fn capacity(message: &'static str) -> Self {
        Self {
            status: STATUS_CAPACITY_OVERFLOW,
            message,
        }
    }
}

fn reserved_is_zero(values: &[u64]) -> bool {
    values.iter().all(|value| *value == 0)
}

fn validate_header<T>(
    observed_size: u32,
    observed_version: u32,
    name: &'static str,
) -> Result<(), ProviderError> {
    if usize::try_from(observed_size).ok() != Some(size_of::<T>()) {
        return Err(ProviderError::abi(name));
    }
    if observed_version != PROVIDER_ABI_VERSION {
        return Err(ProviderError::abi(
            "provider descriptor ABI version mismatch",
        ));
    }
    Ok(())
}

unsafe fn checked_slice<'a, T>(
    pointer: *const T,
    length: usize,
    null_message: &'static str,
) -> Result<&'a [T], ProviderError> {
    if length == 0 {
        return Ok(&[]);
    }
    if pointer.is_null() {
        return Err(ProviderError::invalid(null_message));
    }
    if (pointer as usize) % align_of::<T>() != 0 {
        return Err(ProviderError::invalid(
            "provider input pointer is not naturally aligned",
        ));
    }
    if length > (isize::MAX as usize) / size_of::<T>() {
        return Err(ProviderError::capacity(
            "provider input slice exceeds the addressable range",
        ));
    }
    // SAFETY: The private C++ caller guarantees that every non-null channel
    // addresses `length` initialized elements for the duration of this call.
    Ok(unsafe { core::slice::from_raw_parts(pointer, length) })
}

fn checked_output_range(pointer: *mut f64, length: usize) -> Result<(usize, usize), ProviderError> {
    if length == 0 {
        return Ok((0, 0));
    }
    if pointer.is_null() || (pointer as usize) % align_of::<f64>() != 0 {
        return Err(ProviderError::invalid(
            "force output channel is null or misaligned",
        ));
    }
    if length > (isize::MAX as usize) / size_of::<f64>() {
        return Err(ProviderError::capacity(
            "force output slice exceeds the addressable range",
        ));
    }
    let bytes = length * size_of::<f64>();
    let begin = pointer as usize;
    let end = begin
        .checked_add(bytes)
        .ok_or_else(|| ProviderError::capacity("force output range overflows"))?;
    Ok((begin, end))
}

fn validate_finite(values: &[f64], message: &'static str) -> Result<(), ProviderError> {
    if values.iter().any(|value| !value.is_finite()) {
        return Err(ProviderError::invalid(message));
    }
    Ok(())
}

fn validate_pair_order(pairs: &[Pair], atom_count: usize) -> Result<(), ProviderError> {
    let mut previous = None;
    for pair in pairs {
        let key = (pair.atom_i, pair.atom_j);
        if pair.atom_i >= pair.atom_j || pair.atom_j >= atom_count || previous >= Some(key) {
            return Err(ProviderError::invalid(
                "exclusion pairs must be unique sorted in-range canonical pairs",
            ));
        }
        previous = Some(key);
    }
    Ok(())
}

fn validate_pair_scale_order(scales: &[PairScale], atom_count: usize) -> Result<(), ProviderError> {
    let mut previous = None;
    for scale in scales {
        let key = (scale.atom_i, scale.atom_j);
        if scale.atom_i >= scale.atom_j
            || scale.atom_j >= atom_count
            || previous >= Some(key)
            || !scale.lennard_jones.is_finite()
            || !scale.coulomb.is_finite()
        {
            return Err(ProviderError::invalid(
                "pair scales must be unique sorted finite in-range canonical rows",
            ));
        }
        previous = Some(key);
    }
    Ok(())
}

unsafe fn build_inputs_impl<'a>(
    system: &'a SystemV1,
    forcefield: &'a ForceFieldV1,
    validate_immutable_forcefield: bool,
) -> Result<(System<'a>, ForceField<'a>), ProviderError> {
    validate_header::<SystemV1>(
        system.struct_size,
        system.abi_version,
        "rust_cpu system descriptor size mismatch",
    )?;
    validate_header::<ForceFieldV1>(
        forcefield.struct_size,
        forcefield.abi_version,
        "rust_cpu force-field descriptor size mismatch",
    )?;
    if !reserved_is_zero(&system.reserved)
        || !reserved_is_zero(&forcefield.reserved)
        || forcefield.reserved0 != 0
    {
        return Err(ProviderError::invalid(
            "rust_cpu provider reserved fields must be zero",
        ));
    }
    if system.atom_count == 0 || system.atom_count != forcefield.atom_count {
        return Err(ProviderError::invalid(
            "rust_cpu system and force-field atom counts must match and be non-zero",
        ));
    }
    let atom_count = system.atom_count;
    // SAFETY: Descriptor identity and counts were checked above; each helper
    // validates pointer nullability, alignment, and addressable byte length.
    let position_x = unsafe { checked_slice(system.position_x, atom_count, "position_x is null")? };
    let position_y = unsafe { checked_slice(system.position_y, atom_count, "position_y is null")? };
    let position_z = unsafe { checked_slice(system.position_z, atom_count, "position_z is null")? };
    let charge = unsafe { checked_slice(system.charge, atom_count, "charge is null")? };
    let sigma = unsafe { checked_slice(forcefield.sigma, atom_count, "sigma is null")? };
    let epsilon = unsafe { checked_slice(forcefield.epsilon, atom_count, "epsilon is null")? };

    let bonds = BondSoa {
        atom_i: unsafe {
            checked_slice(
                forcefield.bonds.atom_i,
                forcefield.bonds.count,
                "bond atom_i is null",
            )?
        },
        atom_j: unsafe {
            checked_slice(
                forcefield.bonds.atom_j,
                forcefield.bonds.count,
                "bond atom_j is null",
            )?
        },
        equilibrium: unsafe {
            checked_slice(
                forcefield.bonds.equilibrium,
                forcefield.bonds.count,
                "bond equilibrium is null",
            )?
        },
        force_constant: unsafe {
            checked_slice(
                forcefield.bonds.force_constant,
                forcefield.bonds.count,
                "bond force constant is null",
            )?
        },
    };
    let angles = AngleSoa {
        atom_i: unsafe {
            checked_slice(
                forcefield.angles.atom_i,
                forcefield.angles.count,
                "angle atom_i is null",
            )?
        },
        atom_j: unsafe {
            checked_slice(
                forcefield.angles.atom_j,
                forcefield.angles.count,
                "angle atom_j is null",
            )?
        },
        atom_k: unsafe {
            checked_slice(
                forcefield.angles.atom_k,
                forcefield.angles.count,
                "angle atom_k is null",
            )?
        },
        equilibrium: unsafe {
            checked_slice(
                forcefield.angles.equilibrium,
                forcefield.angles.count,
                "angle equilibrium is null",
            )?
        },
        force_constant: unsafe {
            checked_slice(
                forcefield.angles.force_constant,
                forcefield.angles.count,
                "angle force constant is null",
            )?
        },
    };
    let torsions = TorsionSoa {
        atom_i: unsafe {
            checked_slice(
                forcefield.torsions.atom_i,
                forcefield.torsions.count,
                "torsion atom_i is null",
            )?
        },
        atom_j: unsafe {
            checked_slice(
                forcefield.torsions.atom_j,
                forcefield.torsions.count,
                "torsion atom_j is null",
            )?
        },
        atom_k: unsafe {
            checked_slice(
                forcefield.torsions.atom_k,
                forcefield.torsions.count,
                "torsion atom_k is null",
            )?
        },
        atom_l: unsafe {
            checked_slice(
                forcefield.torsions.atom_l,
                forcefield.torsions.count,
                "torsion atom_l is null",
            )?
        },
        periodicity: unsafe {
            checked_slice(
                forcefield.torsions.periodicity,
                forcefield.torsions.count,
                "torsion periodicity is null",
            )?
        },
        phase: unsafe {
            checked_slice(
                forcefield.torsions.phase,
                forcefield.torsions.count,
                "torsion phase is null",
            )?
        },
        amplitude: unsafe {
            checked_slice(
                forcefield.torsions.amplitude,
                forcefield.torsions.count,
                "torsion amplitude is null",
            )?
        },
    };
    let exclusions = unsafe {
        checked_slice(
            forcefield.exclusions,
            forcefield.exclusion_count,
            "exclusions are null",
        )?
    };
    let pair_scales = unsafe {
        checked_slice(
            forcefield.pair_scales,
            forcefield.pair_scale_count,
            "pair scales are null",
        )?
    };

    for values in [position_x, position_y, position_z, charge] {
        validate_finite(values, "rust_cpu atom channel contains a non-finite value")?;
    }
    if validate_immutable_forcefield {
        for values in [sigma, epsilon] {
            validate_finite(values, "rust_cpu atom channel contains a non-finite value")?;
        }
        if sigma.iter().any(|value| *value <= 0.0) || epsilon.iter().any(|value| *value < 0.0) {
            return Err(ProviderError::invalid(
                "rust_cpu sigma must be positive and epsilon non-negative",
            ));
        }
        for index in bonds
            .atom_i
            .iter()
            .chain(bonds.atom_j)
            .chain(angles.atom_i)
            .chain(angles.atom_j)
            .chain(angles.atom_k)
            .chain(torsions.atom_i)
            .chain(torsions.atom_j)
            .chain(torsions.atom_k)
            .chain(torsions.atom_l)
        {
            if *index >= atom_count {
                return Err(ProviderError::invalid(
                    "rust_cpu bonded atom index is out of range",
                ));
            }
        }
        for values in [
            bonds.equilibrium,
            bonds.force_constant,
            angles.equilibrium,
            angles.force_constant,
            torsions.phase,
            torsions.amplitude,
        ] {
            validate_finite(values, "rust_cpu bonded parameter is not finite")?;
        }
        for row in 0..bonds.atom_i.len() {
            if bonds.atom_i[row] == bonds.atom_j[row]
                || bonds.equilibrium[row] <= 0.0
                || bonds.force_constant[row] <= 0.0
            {
                return Err(ProviderError::invalid(
                    "rust_cpu bond indices and parameters are invalid",
                ));
            }
        }
        for row in 0..angles.atom_i.len() {
            let atom_i = angles.atom_i[row];
            let atom_j = angles.atom_j[row];
            let atom_k = angles.atom_k[row];
            if atom_i == atom_j
                || atom_i == atom_k
                || atom_j == atom_k
                || angles.equilibrium[row] <= 0.0
                || angles.equilibrium[row] >= core::f64::consts::PI
                || angles.force_constant[row] <= 0.0
            {
                return Err(ProviderError::invalid(
                    "rust_cpu angle indices and parameters are invalid",
                ));
            }
        }
        for row in 0..torsions.atom_i.len() {
            let indices = [
                torsions.atom_i[row],
                torsions.atom_j[row],
                torsions.atom_k[row],
                torsions.atom_l[row],
            ];
            let indices_are_distinct = (0..indices.len()).all(|left| {
                ((left + 1)..indices.len()).all(|right| indices[left] != indices[right])
            });
            if !indices_are_distinct
                || !(1..=12).contains(&torsions.periodicity[row])
                || torsions.amplitude[row] < 0.0
            {
                return Err(ProviderError::invalid(
                    "rust_cpu torsion indices and parameters are invalid",
                ));
            }
        }
        validate_pair_order(exclusions, atom_count)?;
        validate_pair_scale_order(pair_scales, atom_count)?;
        for scale in pair_scales {
            if !(0.0..=1.0).contains(&scale.lennard_jones)
                || !(0.0..=1.0).contains(&scale.coulomb)
                || exclusions
                    .binary_search_by_key(&(scale.atom_i, scale.atom_j), |pair| {
                        (pair.atom_i, pair.atom_j)
                    })
                    .is_ok()
            {
                return Err(ProviderError::invalid(
                    "rust_cpu pair scale is out of range or conflicts with an exclusion",
                ));
            }
        }
        if forcefield.periodic_axes_mask & !7_u32 != 0
            || !forcefield.cutoff.is_finite()
            || forcefield.cutoff <= 0.0
            || !forcefield.switch_start.is_finite()
            || forcefield.switch_start < 0.0
            || forcefield.switch_start >= forcefield.cutoff
            || !forcefield.dielectric.is_finite()
            || forcefield.dielectric <= 0.0
            || !forcefield.screening_kappa.is_finite()
            || forcefield.screening_kappa < 0.0
            || !forcefield.minimum_pair_distance.is_finite()
            || forcefield.minimum_pair_distance <= 0.0
        {
            return Err(ProviderError::invalid(
                "rust_cpu nonbonded settings are invalid",
            ));
        }
        let has_periodic_axis = forcefield.periodic_axes_mask != 0;
        let nonperiodic_lengths_are_all_zero =
            forcefield.cell_lengths.iter().all(|length| *length == 0.0);
        for axis in 0..3 {
            let length = forcefield.cell_lengths[axis];
            let length_must_be_positive = has_periodic_axis || !nonperiodic_lengths_are_all_zero;
            if !length.is_finite()
                || (length_must_be_positive && length <= 0.0)
                || (forcefield.periodic_axes_mask & (1_u32 << axis) != 0
                    && forcefield.cutoff >= 0.5 * length)
            {
                return Err(ProviderError::invalid("rust_cpu periodic cell is invalid"));
            }
        }
    }

    Ok((
        System {
            position_x,
            position_y,
            position_z,
            charge,
        },
        ForceField {
            atom_count,
            sigma,
            epsilon,
            bonds,
            angles,
            torsions,
            exclusions,
            pair_scales,
            periodic_axes_mask: forcefield.periodic_axes_mask,
            cell_lengths: forcefield.cell_lengths,
            cutoff: forcefield.cutoff,
            switch_start: forcefield.switch_start,
            dielectric: forcefield.dielectric,
            screening_kappa: forcefield.screening_kappa,
            minimum_pair_distance: forcefield.minimum_pair_distance,
        },
    ))
}

unsafe fn build_inputs<'a>(
    system: &'a SystemV1,
    forcefield: &'a ForceFieldV1,
) -> Result<(System<'a>, ForceField<'a>), ProviderError> {
    unsafe { build_inputs_impl(system, forcefield, true) }
}

unsafe fn validate_outputs<'a>(
    atom_count: usize,
    compute_forces: bool,
    out_energy: *mut EnergyV1,
    out_forces: *mut ForceOutputV1,
) -> Result<Option<ForceChannels<'a>>, ProviderError> {
    let energy = unsafe {
        out_energy
            .as_ref()
            .ok_or_else(|| ProviderError::invalid("energy output is null"))?
    };
    validate_header::<EnergyV1>(
        energy.struct_size,
        energy.abi_version,
        "rust_cpu energy output size mismatch",
    )?;
    if !reserved_is_zero(&energy.reserved) {
        return Err(ProviderError::invalid(
            "rust_cpu energy output reserved fields must be zero",
        ));
    }
    if !compute_forces {
        return Ok(None);
    }
    if atom_count == 0 {
        return Err(ProviderError::invalid(
            "rust_cpu force output requires a non-empty system",
        ));
    }
    let forces = unsafe {
        out_forces
            .as_ref()
            .ok_or_else(|| ProviderError::invalid("force output is null"))?
    };
    validate_header::<ForceOutputV1>(
        forces.struct_size,
        forces.abi_version,
        "rust_cpu force output size mismatch",
    )?;
    if !reserved_is_zero(&forces.reserved) || forces.capacity < atom_count {
        return Err(ProviderError::invalid(
            "rust_cpu force output is reserved or undersized",
        ));
    }
    let x_range = checked_output_range(forces.x, atom_count)?;
    let y_range = checked_output_range(forces.y, atom_count)?;
    let z_range = checked_output_range(forces.z, atom_count)?;
    let overlaps =
        |left: (usize, usize), right: (usize, usize)| left.0 < right.1 && right.0 < left.1;
    if overlaps(x_range, y_range) || overlaps(x_range, z_range) || overlaps(y_range, z_range) {
        return Err(ProviderError::invalid(
            "rust_cpu force output channels must not overlap",
        ));
    }
    // SAFETY: Raw ranges were validated for nullability, alignment, capacity,
    // overflow, and pairwise disjointness before mutable slices are formed.
    let x = unsafe { core::slice::from_raw_parts_mut(forces.x, atom_count) };
    let y = unsafe { core::slice::from_raw_parts_mut(forces.y, atom_count) };
    let z = unsafe { core::slice::from_raw_parts_mut(forces.z, atom_count) };
    Ok(Some((x, y, z)))
}

fn clear_error(error: &mut ErrorV1) {
    error.message.fill(0);
}

fn write_error(error: &mut ErrorV1, message: &str) {
    error.message.fill(0);
    let bytes = message.as_bytes();
    let count = bytes.len().min(ERROR_CAPACITY - 1);
    error.message[..count].copy_from_slice(&bytes[..count]);
}

fn checked_usize(value: u64, message: &'static str) -> Result<usize, ProviderError> {
    usize::try_from(value).map_err(|_| ProviderError::capacity(message))
}

fn digest_present(value: &[u8; 32]) -> bool {
    value.iter().any(|byte| *byte != 0)
}

unsafe fn build_geometric_admission_state(
    descriptor: &DockingGeometricAdmissionContextSoaV1,
) -> Result<GeometricAdmissionState, ProviderError> {
    validate_header::<DockingGeometricAdmissionContextSoaV1>(
        descriptor.struct_size,
        descriptor.abi_version,
        "rust_cpu geometric-admission context descriptor size mismatch",
    )?;
    if descriptor.unit_system != UNIT_SYSTEM_ANGSTROM_KCAL_MOL
        || descriptor.reserved0 != 0
        || !reserved_is_zero(&descriptor.reserved)
        || descriptor.hard_rejection_minimum_vdw_ratio != HARD_REJECTION_MINIMUM_VDW_RATIO
        || descriptor.max_batch_exact_pair_evaluations
            != FIXED64_MAX_BATCH_EXACT_PAIR_EVALUATIONS as u64
        || !digest_present(&descriptor.authority_input_receipt_sha256)
        || !digest_present(&descriptor.receptor_system_sha256)
        || !digest_present(&descriptor.ligand_system_sha256)
        || !digest_present(&descriptor.backend_receipt_sha256)
    {
        return Err(ProviderError::invalid(
            "rust_cpu geometric-admission policy, identity, units, or reserved fields are invalid",
        ));
    }
    let receptor_count = checked_usize(
        descriptor.receptor_atom_count,
        "rust_cpu geometric-admission receptor count exceeds the host address space",
    )?;
    let ligand_count = checked_usize(
        descriptor.ligand_atom_count,
        "rust_cpu geometric-admission ligand count exceeds the host address space",
    )?;
    if receptor_count == 0
        || receptor_count > FIXED64_MAX_RECEPTOR_ATOMS
        || ligand_count == 0
        || ligand_count > FIXED64_MAX_LIGAND_ATOMS
    {
        return Err(ProviderError::capacity(
            "rust_cpu geometric-admission atom denominator is outside fixed bounds",
        ));
    }
    // SAFETY: Counts are bounded and checked_slice validates pointer identity,
    // alignment, and addressable byte length before forming each shared slice.
    let receptor_x = unsafe {
        checked_slice(
            descriptor.receptor_x_angstrom,
            receptor_count,
            "rust_cpu geometric-admission receptor x channel is null",
        )?
    };
    let receptor_y = unsafe {
        checked_slice(
            descriptor.receptor_y_angstrom,
            receptor_count,
            "rust_cpu geometric-admission receptor y channel is null",
        )?
    };
    let receptor_z = unsafe {
        checked_slice(
            descriptor.receptor_z_angstrom,
            receptor_count,
            "rust_cpu geometric-admission receptor z channel is null",
        )?
    };
    let receptor_radii = unsafe {
        checked_slice(
            descriptor.receptor_vdw_radius_angstrom,
            receptor_count,
            "rust_cpu geometric-admission receptor radii are null",
        )?
    };
    let ligand_radii = unsafe {
        checked_slice(
            descriptor.ligand_vdw_radius_angstrom,
            ligand_count,
            "rust_cpu geometric-admission ligand radii are null",
        )?
    };
    let ligand_heavy = unsafe {
        checked_slice(
            descriptor.ligand_heavy_atom_mask,
            ligand_count,
            "rust_cpu geometric-admission heavy-atom mask is null",
        )?
    };
    if ligand_heavy.iter().any(|value| *value > 1) {
        return Err(ProviderError::invalid(
            "rust_cpu geometric-admission heavy-atom mask is not boolean",
        ));
    }
    let receptor_coordinates = receptor_x
        .iter()
        .zip(receptor_y)
        .zip(receptor_z)
        .map(|((x, y), z)| Vec3::new(*x, *y, *z))
        .collect();
    let input = Fixed64GeometricInput::new(
        ligand_radii.to_vec(),
        ligand_heavy.iter().map(|value| *value == 1).collect(),
        receptor_coordinates,
        receptor_radii.to_vec(),
        Vec3::new(
            descriptor.pocket_center_angstrom[0],
            descriptor.pocket_center_angstrom[1],
            descriptor.pocket_center_angstrom[2],
        ),
        descriptor.pocket_radius_angstrom,
    )
    .map_err(|error| match error.code() {
        Fixed64GeometricErrorCode::PairBudgetExceeded => {
            ProviderError::capacity("rust_cpu geometric-admission context exceeds the pair budget")
        }
        _ => ProviderError::invalid("rust_cpu geometric-admission context geometry is invalid"),
    })?;
    Ok(GeometricAdmissionState {
        input,
        ligand_atom_count: ligand_count,
        receptor_atom_count: receptor_count,
        max_batch_exact_pair_evaluations: FIXED64_MAX_BATCH_EXACT_PAIR_EVALUATIONS,
    })
}

fn geometric_failure_row(
    slot_index: usize,
    status: i32,
    failure_code: i32,
) -> DockingGeometricAdmissionRowV1 {
    DockingGeometricAdmissionRowV1 {
        slot_index: slot_index as u32,
        status,
        failure_code,
        decision: GEOMETRIC_DECISION_NOT_EVALUATED,
        rank_eligible: 0,
        reserved0: [0; 3],
        reserved1: 0,
        ligand_atom_count: 0,
        receptor_atom_count: 0,
        exact_pair_count: 0,
        penetration_pair_count: 0,
        unique_ligand_penetration_atom_count: 0,
        unique_ligand_heavy_atom_penetration_count: 0,
        raw_minimum_distance_angstrom: 0.0,
        minimum_vdw_surface_gap_angstrom: 0.0,
        minimum_vdw_ratio: 0.0,
        sphere_overlap_proxy_angstrom3: 0.0,
        pocket_escape_angstrom: 0.0,
        row_receipt_sha256: [0; 32],
    }
}

unsafe fn evaluate_geometric_admission_fixed64(
    state: &GeometricAdmissionState,
    candidates: &DockingGeometricAdmissionCandidateBatchSoaV1,
) -> Result<[DockingGeometricAdmissionRowV1; FIXED64_CANDIDATE_COUNT], ProviderError> {
    validate_header::<DockingGeometricAdmissionCandidateBatchSoaV1>(
        candidates.struct_size,
        candidates.abi_version,
        "rust_cpu geometric-admission candidate descriptor size mismatch",
    )?;
    if candidates.candidate_count != FIXED64_CANDIDATE_COUNT as u64
        || checked_usize(
            candidates.ligand_atom_count,
            "rust_cpu geometric-admission candidate ligand count exceeds the host address space",
        )? != state.ligand_atom_count
        || candidates.unit_system != UNIT_SYSTEM_ANGSTROM_KCAL_MOL
        || candidates.reserved0 != 0
        || !reserved_is_zero(&candidates.reserved)
    {
        return Err(ProviderError::invalid(
            "rust_cpu geometric-admission candidate denominator, units, or reserved fields are invalid",
        ));
    }
    let coordinate_count = FIXED64_CANDIDATE_COUNT
        .checked_mul(state.ligand_atom_count)
        .ok_or_else(|| {
            ProviderError::capacity("rust_cpu geometric-admission coordinate count overflowed")
        })?;
    // SAFETY: The public dispatcher has validated disjoint fixed64 channels;
    // the provider independently checks all pointer identities and lengths.
    let candidate_state = unsafe {
        checked_slice(
            candidates.candidate_state,
            FIXED64_CANDIDATE_COUNT,
            "rust_cpu geometric-admission candidate-state channel is null",
        )?
    };
    let x = unsafe {
        checked_slice(
            candidates.x_angstrom,
            coordinate_count,
            "rust_cpu geometric-admission x channel is null",
        )?
    };
    let y = unsafe {
        checked_slice(
            candidates.y_angstrom,
            coordinate_count,
            "rust_cpu geometric-admission y channel is null",
        )?
    };
    let z = unsafe {
        checked_slice(
            candidates.z_angstrom,
            coordinate_count,
            "rust_cpu geometric-admission z channel is null",
        )?
    };
    if candidate_state.iter().any(|value| {
        *value != GEOMETRIC_CANDIDATE_UPSTREAM_FAILURE && *value != GEOMETRIC_CANDIDATE_EVALUATE
    }) {
        return Err(ProviderError::invalid(
            "rust_cpu geometric-admission candidate state is invalid",
        ));
    }
    let active_count = candidate_state
        .iter()
        .filter(|value| **value == GEOMETRIC_CANDIDATE_EVALUATE)
        .count();
    let batch_pairs = active_count
        .checked_mul(state.ligand_atom_count)
        .and_then(|value| value.checked_mul(state.receptor_atom_count))
        .ok_or_else(|| {
            ProviderError::capacity("rust_cpu geometric-admission batch pair count overflowed")
        })?;
    if batch_pairs > state.max_batch_exact_pair_evaluations {
        return Err(ProviderError::capacity(
            "rust_cpu geometric-admission batch pair work exceeds the frozen cap",
        ));
    }

    let mut rows = [geometric_failure_row(
        0,
        GEOMETRIC_ROW_UPSTREAM_FAILURE,
        GEOMETRIC_FAILURE_UPSTREAM_NOT_AVAILABLE,
    ); FIXED64_CANDIDATE_COUNT];
    for slot in 0..FIXED64_CANDIDATE_COUNT {
        if candidate_state[slot] == GEOMETRIC_CANDIDATE_UPSTREAM_FAILURE {
            rows[slot] = geometric_failure_row(
                slot,
                GEOMETRIC_ROW_UPSTREAM_FAILURE,
                GEOMETRIC_FAILURE_UPSTREAM_NOT_AVAILABLE,
            );
            continue;
        }
        let begin = slot * state.ligand_atom_count;
        let end = begin + state.ligand_atom_count;
        let coordinates: Vec<Vec3> = (begin..end)
            .map(|index| Vec3::new(x[index], y[index], z[index]))
            .collect();
        if coordinates.iter().any(|coordinate| {
            !coordinate.is_finite()
                || coordinate.x.abs() > FIXED64_MAX_ABSOLUTE_COORDINATE_ANGSTROM
                || coordinate.y.abs() > FIXED64_MAX_ABSOLUTE_COORDINATE_ANGSTROM
                || coordinate.z.abs() > FIXED64_MAX_ABSOLUTE_COORDINATE_ANGSTROM
        }) {
            rows[slot] = geometric_failure_row(
                slot,
                GEOMETRIC_ROW_TYPED_FAILURE,
                GEOMETRIC_FAILURE_INVALID_CANDIDATE_COORDINATES,
            );
            continue;
        }
        let metrics = match evaluate_fixed64_geometric_metrics(&coordinates, &state.input) {
            Ok(metrics) => metrics,
            Err(error) => {
                rows[slot] = geometric_failure_row(
                    slot,
                    GEOMETRIC_ROW_TYPED_FAILURE,
                    if error.code() == Fixed64GeometricErrorCode::InvalidInput {
                        GEOMETRIC_FAILURE_INVALID_CANDIDATE_COORDINATES
                    } else {
                        GEOMETRIC_FAILURE_NONFINITE_DERIVED_MEASUREMENT
                    },
                );
                continue;
            }
        };
        let rank_eligible = metrics.minimum_vdw_ratio() >= HARD_REJECTION_MINIMUM_VDW_RATIO;
        rows[slot] = DockingGeometricAdmissionRowV1 {
            slot_index: slot as u32,
            status: GEOMETRIC_ROW_EVALUATED,
            failure_code: GEOMETRIC_FAILURE_NONE,
            decision: if rank_eligible {
                GEOMETRIC_DECISION_ACCEPTED
            } else {
                GEOMETRIC_DECISION_SEVERE_PENETRATION_REJECTED
            },
            rank_eligible: u8::from(rank_eligible),
            reserved0: [0; 3],
            reserved1: 0,
            ligand_atom_count: metrics.ligand_atom_count() as u64,
            receptor_atom_count: metrics.receptor_atom_count() as u64,
            exact_pair_count: metrics.exact_pair_count() as u64,
            penetration_pair_count: metrics.penetration_pair_count() as u64,
            unique_ligand_penetration_atom_count: metrics.unique_ligand_penetration_atom_count()
                as u64,
            unique_ligand_heavy_atom_penetration_count: metrics
                .unique_ligand_heavy_atom_penetration_count()
                as u64,
            raw_minimum_distance_angstrom: metrics.raw_minimum_distance_angstrom(),
            minimum_vdw_surface_gap_angstrom: metrics.minimum_vdw_surface_gap_angstrom(),
            minimum_vdw_ratio: metrics.minimum_vdw_ratio(),
            sphere_overlap_proxy_angstrom3: metrics.sphere_overlap_proxy_angstrom3(),
            pocket_escape_angstrom: metrics.pocket_escape_angstrom(),
            row_receipt_sha256: [0; 32],
        };
    }
    Ok(rows)
}

fn docking_failure_code(code: NativeScorerV1FailureCode) -> i32 {
    match code {
        NativeScorerV1FailureCode::InvalidCandidateCoordinates => {
            DOCKING_FAILURE_INVALID_CANDIDATE_COORDINATES
        }
        NativeScorerV1FailureCode::ReceptorCandidatePairCapacityExceeded => {
            DOCKING_FAILURE_RECEPTOR_PAIR_CAPACITY
        }
        NativeScorerV1FailureCode::LigandPairCapacityExceeded => {
            DOCKING_FAILURE_LIGAND_PAIR_CAPACITY
        }
        NativeScorerV1FailureCode::DegenerateRotorGeometry => DOCKING_FAILURE_DEGENERATE_ROTOR,
        NativeScorerV1FailureCode::NonfiniteScore => DOCKING_FAILURE_NONFINITE_SCORE,
        NativeScorerV1FailureCode::ProposalGenerationFailure
        | NativeScorerV1FailureCode::SeverePenetrationRejected => {
            DOCKING_FAILURE_UPSTREAM_NOT_ADMITTED
        }
    }
}

fn docking_failure_row(
    slot_index: usize,
    failure_code: i32,
    receptor_pair_count: usize,
    ligand_pair_count: usize,
) -> DockingScorerRowV1 {
    DockingScorerRowV1 {
        slot_index: u32::try_from(slot_index).unwrap_or(0),
        status: DOCKING_ROW_TYPED_FAILURE,
        failure_code,
        reserved0: 0,
        weighted_terms: [0.0; 8],
        total_score: 0.0,
        receptor_candidate_pair_count: receptor_pair_count as u64,
        ligand_pair_count: ligand_pair_count as u64,
        hbond_count: 0,
        hydrophobic_contact_count: 0,
        buried_polar_count: 0,
        reserved: [0; 4],
    }
}

unsafe fn build_docking_context(
    descriptor: &DockingScorerContextSoaV1,
) -> Result<NativeScorerV1Context, ProviderError> {
    validate_header::<DockingScorerContextSoaV1>(
        descriptor.struct_size,
        descriptor.abi_version,
        "rust_cpu ScorerV1 context descriptor size mismatch",
    )?;
    if descriptor.unit_system != UNIT_SYSTEM_ANGSTROM_KCAL_MOL
        || descriptor.reserved0 != 0
        || !reserved_is_zero(&descriptor.reserved)
    {
        return Err(ProviderError::invalid(
            "rust_cpu ScorerV1 context units or reserved fields are invalid",
        ));
    }
    let receptor_count = checked_usize(
        descriptor.receptor_atom_count,
        "rust_cpu ScorerV1 receptor count exceeds the host address space",
    )?;
    let ligand_count = checked_usize(
        descriptor.ligand_atom_count,
        "rust_cpu ScorerV1 ligand count exceeds the host address space",
    )?;
    let receptor_donor_count = checked_usize(
        descriptor.receptor_donor_count,
        "rust_cpu ScorerV1 receptor donor count exceeds the host address space",
    )?;
    let ligand_donor_count = checked_usize(
        descriptor.ligand_donor_count,
        "rust_cpu ScorerV1 ligand donor count exceeds the host address space",
    )?;
    let exclusion_count = checked_usize(
        descriptor.ligand_exclusion_count,
        "rust_cpu ScorerV1 exclusion count exceeds the host address space",
    )?;
    let rotor_count = checked_usize(
        descriptor.rotor_count,
        "rust_cpu ScorerV1 rotor count exceeds the host address space",
    )?;
    if receptor_count == 0
        || receptor_count > 4_096
        || ligand_count == 0
        || ligand_count > 512
        || receptor_donor_count > receptor_count
        || ligand_donor_count > ligand_count
        || rotor_count > ligand_count
        || exclusion_count > ligand_count.saturating_mul(ligand_count.saturating_sub(1)) / 2
    {
        return Err(ProviderError::capacity(
            "rust_cpu ScorerV1 context denominator is outside fixed bounds",
        ));
    }

    macro_rules! checked {
        ($pointer:expr, $count:expr, $message:literal) => {{
            // SAFETY: Counts are bounded above and checked_slice validates the
            // pointer, alignment, and addressable byte range.
            unsafe { checked_slice($pointer, $count, $message)? }
        }};
    }
    let receptor_x = checked!(
        descriptor.receptor_x_angstrom,
        receptor_count,
        "rust_cpu ScorerV1 receptor x channel is null"
    );
    let receptor_y = checked!(
        descriptor.receptor_y_angstrom,
        receptor_count,
        "rust_cpu ScorerV1 receptor y channel is null"
    );
    let receptor_z = checked!(
        descriptor.receptor_z_angstrom,
        receptor_count,
        "rust_cpu ScorerV1 receptor z channel is null"
    );
    let receptor_charge = checked!(
        descriptor.receptor_charge_elementary,
        receptor_count,
        "rust_cpu ScorerV1 receptor charge channel is null"
    );
    let receptor_radius = checked!(
        descriptor.receptor_vdw_radius_angstrom,
        receptor_count,
        "rust_cpu ScorerV1 receptor radius channel is null"
    );
    let receptor_epsilon = checked!(
        descriptor.receptor_epsilon_kcal_per_mol,
        receptor_count,
        "rust_cpu ScorerV1 receptor epsilon channel is null"
    );
    let receptor_hydrophobic = checked!(
        descriptor.receptor_hydrophobic,
        receptor_count,
        "rust_cpu ScorerV1 receptor hydrophobic channel is null"
    );
    let receptor_acceptor = checked!(
        descriptor.receptor_acceptor,
        receptor_count,
        "rust_cpu ScorerV1 receptor acceptor channel is null"
    );
    let ligand_x = checked!(
        descriptor.ligand_reference_x_angstrom,
        ligand_count,
        "rust_cpu ScorerV1 ligand x channel is null"
    );
    let ligand_y = checked!(
        descriptor.ligand_reference_y_angstrom,
        ligand_count,
        "rust_cpu ScorerV1 ligand y channel is null"
    );
    let ligand_z = checked!(
        descriptor.ligand_reference_z_angstrom,
        ligand_count,
        "rust_cpu ScorerV1 ligand z channel is null"
    );
    let ligand_charge = checked!(
        descriptor.ligand_charge_elementary,
        ligand_count,
        "rust_cpu ScorerV1 ligand charge channel is null"
    );
    let ligand_radius = checked!(
        descriptor.ligand_vdw_radius_angstrom,
        ligand_count,
        "rust_cpu ScorerV1 ligand radius channel is null"
    );
    let ligand_epsilon = checked!(
        descriptor.ligand_epsilon_kcal_per_mol,
        ligand_count,
        "rust_cpu ScorerV1 ligand epsilon channel is null"
    );
    let ligand_hydrophobic = checked!(
        descriptor.ligand_hydrophobic,
        ligand_count,
        "rust_cpu ScorerV1 ligand hydrophobic channel is null"
    );
    let ligand_acceptor = checked!(
        descriptor.ligand_acceptor,
        ligand_count,
        "rust_cpu ScorerV1 ligand acceptor channel is null"
    );
    if receptor_hydrophobic
        .iter()
        .chain(receptor_acceptor)
        .chain(ligand_hydrophobic)
        .chain(ligand_acceptor)
        .any(|value| *value > 1)
    {
        return Err(ProviderError::invalid(
            "rust_cpu ScorerV1 boolean atom channels must contain zero or one",
        ));
    }

    let receptor_donor_atom = checked!(
        descriptor.receptor_donor_atom_index,
        receptor_donor_count,
        "rust_cpu ScorerV1 receptor donor index is null"
    );
    let receptor_hydrogen_atom = checked!(
        descriptor.receptor_hydrogen_atom_index,
        receptor_donor_count,
        "rust_cpu ScorerV1 receptor hydrogen index is null"
    );
    let ligand_donor_atom = checked!(
        descriptor.ligand_donor_atom_index,
        ligand_donor_count,
        "rust_cpu ScorerV1 ligand donor index is null"
    );
    let ligand_hydrogen_atom = checked!(
        descriptor.ligand_hydrogen_atom_index,
        ligand_donor_count,
        "rust_cpu ScorerV1 ligand hydrogen index is null"
    );
    let exclusion_i = checked!(
        descriptor.ligand_exclusion_atom_i,
        exclusion_count,
        "rust_cpu ScorerV1 exclusion i channel is null"
    );
    let exclusion_j = checked!(
        descriptor.ligand_exclusion_atom_j,
        exclusion_count,
        "rust_cpu ScorerV1 exclusion j channel is null"
    );
    let rotor_i = checked!(
        descriptor.rotor_atom_i,
        rotor_count,
        "rust_cpu ScorerV1 rotor i channel is null"
    );
    let rotor_j = checked!(
        descriptor.rotor_atom_j,
        rotor_count,
        "rust_cpu ScorerV1 rotor j channel is null"
    );
    let rotor_k = checked!(
        descriptor.rotor_atom_k,
        rotor_count,
        "rust_cpu ScorerV1 rotor k channel is null"
    );
    let rotor_l = checked!(
        descriptor.rotor_atom_l,
        rotor_count,
        "rust_cpu ScorerV1 rotor l channel is null"
    );

    let receptor_coordinates = (0..receptor_count)
        .map(|index| Vec3::new(receptor_x[index], receptor_y[index], receptor_z[index]))
        .collect();
    let receptor_atoms = (0..receptor_count)
        .map(|index| NativeScorerV1Atom {
            charge_elementary: receptor_charge[index],
            vdw_radius_angstrom: receptor_radius[index],
            epsilon_kcal_per_mol: receptor_epsilon[index],
            hydrophobic: receptor_hydrophobic[index] == 1,
            acceptor: receptor_acceptor[index] == 1,
        })
        .collect();
    let ligand_coordinates = (0..ligand_count)
        .map(|index| Vec3::new(ligand_x[index], ligand_y[index], ligand_z[index]))
        .collect();
    let ligand_atoms = (0..ligand_count)
        .map(|index| NativeScorerV1Atom {
            charge_elementary: ligand_charge[index],
            vdw_radius_angstrom: ligand_radius[index],
            epsilon_kcal_per_mol: ligand_epsilon[index],
            hydrophobic: ligand_hydrophobic[index] == 1,
            acceptor: ligand_acceptor[index] == 1,
        })
        .collect();
    let receptor_donors = (0..receptor_donor_count)
        .map(|index| {
            Ok(NativeScorerV1Donor {
                donor_atom_index: checked_usize(
                    receptor_donor_atom[index],
                    "rust_cpu ScorerV1 receptor donor index exceeds the host address space",
                )?,
                hydrogen_atom_index: checked_usize(
                    receptor_hydrogen_atom[index],
                    "rust_cpu ScorerV1 receptor hydrogen index exceeds the host address space",
                )?,
            })
        })
        .collect::<Result<Vec<_>, ProviderError>>()?;
    let ligand_donors = (0..ligand_donor_count)
        .map(|index| {
            Ok(NativeScorerV1Donor {
                donor_atom_index: checked_usize(
                    ligand_donor_atom[index],
                    "rust_cpu ScorerV1 ligand donor index exceeds the host address space",
                )?,
                hydrogen_atom_index: checked_usize(
                    ligand_hydrogen_atom[index],
                    "rust_cpu ScorerV1 ligand hydrogen index exceeds the host address space",
                )?,
            })
        })
        .collect::<Result<Vec<_>, ProviderError>>()?;
    let exclusions = (0..exclusion_count)
        .map(|index| {
            Ok([
                checked_usize(
                    exclusion_i[index],
                    "rust_cpu ScorerV1 exclusion index exceeds the host address space",
                )?,
                checked_usize(
                    exclusion_j[index],
                    "rust_cpu ScorerV1 exclusion index exceeds the host address space",
                )?,
            ])
        })
        .collect::<Result<Vec<_>, ProviderError>>()?;
    let rotors = (0..rotor_count)
        .map(|index| {
            Ok([
                checked_usize(
                    rotor_i[index],
                    "rust_cpu ScorerV1 rotor index exceeds the host address space",
                )?,
                checked_usize(
                    rotor_j[index],
                    "rust_cpu ScorerV1 rotor index exceeds the host address space",
                )?,
                checked_usize(
                    rotor_k[index],
                    "rust_cpu ScorerV1 rotor index exceeds the host address space",
                )?,
                checked_usize(
                    rotor_l[index],
                    "rust_cpu ScorerV1 rotor index exceeds the host address space",
                )?,
            ])
        })
        .collect::<Result<Vec<_>, ProviderError>>()?;
    let config = NativeScorerV1Config::new(
        descriptor.weights,
        descriptor.electrostatic_dielectric,
        descriptor.pair_cutoff_angstrom,
        descriptor.hbond_distance_max_angstrom,
        descriptor.polar_burial_distance_angstrom,
        checked_usize(
            descriptor.max_receptor_candidate_pairs,
            "rust_cpu ScorerV1 receptor pair capacity exceeds the host address space",
        )?,
        checked_usize(
            descriptor.max_ligand_pair_checks,
            "rust_cpu ScorerV1 ligand pair capacity exceeds the host address space",
        )?,
    )
    .map_err(|error| ProviderError::invalid(error.message()))?;
    NativeScorerV1Context::new(
        descriptor.authority_input_receipt_sha256,
        descriptor.receptor_system_sha256,
        descriptor.ligand_system_sha256,
        NativeScorerV1Backend::RustCpu,
        descriptor.backend_receipt_sha256,
        receptor_coordinates,
        receptor_atoms,
        ligand_coordinates,
        ligand_atoms,
        receptor_donors,
        ligand_donors,
        exclusions,
        rotors,
        Vec3::new(
            descriptor.pocket_center_angstrom[0],
            descriptor.pocket_center_angstrom[1],
            descriptor.pocket_center_angstrom[2],
        ),
        descriptor.pocket_radius_angstrom,
        config,
    )
    .map_err(|error| ProviderError::invalid(error.message()))
}

unsafe fn score_docking_fixed64(
    context: &NativeScorerV1Context,
    candidates: &DockingScorerCandidateBatchSoaV1,
) -> Result<[DockingScorerRowV1; FIXED64_CANDIDATE_COUNT], ProviderError> {
    validate_header::<DockingScorerCandidateBatchSoaV1>(
        candidates.struct_size,
        candidates.abi_version,
        "rust_cpu ScorerV1 candidate batch size mismatch",
    )?;
    if candidates.unit_system != UNIT_SYSTEM_ANGSTROM_KCAL_MOL
        || candidates.reserved0 != 0
        || !reserved_is_zero(&candidates.reserved)
        || candidates.candidate_count != FIXED64_CANDIDATE_COUNT as u64
        || candidates.ligand_atom_count != context.ligand_atoms().len() as u64
    {
        return Err(ProviderError::invalid(
            "rust_cpu ScorerV1 candidate batch identity is invalid",
        ));
    }
    let ligand_count = context.ligand_atoms().len();
    let coordinate_count = FIXED64_CANDIDATE_COUNT
        .checked_mul(ligand_count)
        .ok_or_else(|| ProviderError::capacity("rust_cpu ScorerV1 coordinate count overflows"))?;
    let states = unsafe {
        checked_slice(
            candidates.candidate_state,
            FIXED64_CANDIDATE_COUNT,
            "rust_cpu ScorerV1 candidate state channel is null",
        )?
    };
    let x = unsafe {
        checked_slice(
            candidates.x_angstrom,
            coordinate_count,
            "rust_cpu ScorerV1 candidate x channel is null",
        )?
    };
    let y = unsafe {
        checked_slice(
            candidates.y_angstrom,
            coordinate_count,
            "rust_cpu ScorerV1 candidate y channel is null",
        )?
    };
    let z = unsafe {
        checked_slice(
            candidates.z_angstrom,
            coordinate_count,
            "rust_cpu ScorerV1 candidate z channel is null",
        )?
    };
    if states
        .iter()
        .any(|state| *state != DOCKING_CANDIDATE_INACTIVE && *state != DOCKING_CANDIDATE_ACTIVE)
    {
        return Err(ProviderError::invalid(
            "rust_cpu ScorerV1 candidate state is invalid",
        ));
    }
    let kernel = context
        .prepare_rust_cpu_kernel()
        .map_err(|error| ProviderError::invalid(error.message()))?;
    let mut rows = Vec::with_capacity(FIXED64_CANDIDATE_COUNT);
    for (slot, state) in states.iter().copied().enumerate() {
        if state == DOCKING_CANDIDATE_INACTIVE {
            rows.push(docking_failure_row(
                slot,
                DOCKING_FAILURE_UPSTREAM_NOT_ADMITTED,
                0,
                0,
            ));
            continue;
        }
        let offset = slot * ligand_count;
        let pose = (0..ligand_count)
            .map(|atom| Vec3::new(x[offset + atom], y[offset + atom], z[offset + atom]))
            .collect::<Vec<_>>();
        match kernel.score_coordinates(&pose) {
            NativeScorerV1KernelOutcome::Scored(terms) => rows.push(DockingScorerRowV1 {
                slot_index: slot as u32,
                status: DOCKING_ROW_SCORED,
                failure_code: DOCKING_FAILURE_NONE,
                reserved0: 0,
                weighted_terms: terms.weighted_terms(),
                total_score: terms.total_score(),
                receptor_candidate_pair_count: terms.receptor_candidate_pair_count() as u64,
                ligand_pair_count: terms.ligand_pair_count() as u64,
                hbond_count: terms.hbond_count() as u64,
                hydrophobic_contact_count: terms.hydrophobic_contact_count() as u64,
                buried_polar_count: terms.buried_polar_count() as u64,
                reserved: [0; 4],
            }),
            NativeScorerV1KernelOutcome::TypedFailure(failure) => {
                rows.push(docking_failure_row(
                    slot,
                    docking_failure_code(failure.failure_code()),
                    failure.receptor_candidate_pair_count(),
                    failure.ligand_pair_count(),
                ));
            }
        }
    }
    rows.try_into().map_err(|_| ProviderError {
        status: STATUS_INTERNAL_ERROR,
        message: "rust_cpu ScorerV1 fixed64 denominator changed internally",
    })
}

fn validity_failure_code(code: NativeFixed64ValidityFailureCode) -> i32 {
    match code {
        NativeFixed64ValidityFailureCode::UpstreamScorerFailure => VALIDITY_FAILURE_UPSTREAM_SCORER,
        NativeFixed64ValidityFailureCode::InvalidCandidateCoordinates => {
            VALIDITY_FAILURE_INVALID_CANDIDATE_COORDINATES
        }
        NativeFixed64ValidityFailureCode::LigandPairCapacityExceeded => {
            VALIDITY_FAILURE_LIGAND_PAIR_CAPACITY
        }
        NativeFixed64ValidityFailureCode::ReceptorCrossCapacityExceeded => {
            VALIDITY_FAILURE_RECEPTOR_CROSS_CAPACITY
        }
        NativeFixed64ValidityFailureCode::ElementLigandPairCapacityExceeded => {
            VALIDITY_FAILURE_ELEMENT_LIGAND_PAIR_CAPACITY
        }
        NativeFixed64ValidityFailureCode::ElementReceptorCandidateCapacityExceeded => {
            VALIDITY_FAILURE_ELEMENT_RECEPTOR_CANDIDATE_CAPACITY
        }
        NativeFixed64ValidityFailureCode::NonfiniteDerivedMeasurement => {
            VALIDITY_FAILURE_NONFINITE_DERIVED_MEASUREMENT
        }
    }
}

fn validity_passed_mask(checks: NativeFixed64ValidityChecks) -> u32 {
    let mut mask = 0;
    if checks.proper_rotation() {
        mask |= VALIDITY_CHECK_PROPER_ROTATION;
    }
    if checks.bond_lengths_preserved() {
        mask |= VALIDITY_CHECK_BOND_LENGTHS;
    }
    if checks.ligand_self_clash_free() {
        mask |= VALIDITY_CHECK_LIGAND_SELF_CLASH;
    }
    if checks.receptor_ligand_clash_free() {
        mask |= VALIDITY_CHECK_RECEPTOR_LIGAND_CLASH;
    }
    if checks.declared_chirality_preserved() {
        mask |= VALIDITY_CHECK_CHIRALITY;
    }
    if checks.inside_declared_pocket() {
        mask |= VALIDITY_CHECK_DECLARED_POCKET;
    }
    if checks.element_vdw_ligand_overlap_free() {
        mask |= VALIDITY_CHECK_ELEMENT_LIGAND_VDW;
    }
    if checks.element_vdw_receptor_overlap_free() {
        mask |= VALIDITY_CHECK_ELEMENT_RECEPTOR_VDW;
    }
    mask
}

fn validity_failure_row(
    slot_index: usize,
    status: i32,
    failure_code: i32,
    upstream_scorer_failure_code: i32,
    observed_count: usize,
) -> DockingPoseValidityRowV1 {
    DockingPoseValidityRowV1 {
        slot_index: u32::try_from(slot_index).unwrap_or(0),
        status,
        failure_code,
        upstream_scorer_failure_code,
        passed_check_mask: 0,
        blocker_mask: 0,
        observed_count: observed_count as u64,
        atom_count: 0,
        rotation_orthogonality_max_error: 0.0,
        rotation_determinant: 0.0,
        max_bond_length_delta_angstrom: 0.0,
        minimum_ligand_nonbonded_distance_angstrom: 0.0,
        evaluated_ligand_nonbonded_pair_count: 0,
        excluded_ligand_pair_count: 0,
        minimum_receptor_ligand_distance_angstrom: 0.0,
        evaluated_receptor_ligand_pair_count: 0,
        minimum_declared_chiral_volume: 0.0,
        declared_chirality_center_count: 0,
        maximum_pocket_center_distance_angstrom: 0.0,
        element_vdw_ligand_pair_count: 0,
        element_vdw_ligand_severe_overlap_count: 0,
        element_vdw_ligand_minimum_distance_angstrom: 0.0,
        element_vdw_ligand_minimum_ratio: 0.0,
        element_vdw_receptor_candidate_pair_count: 0,
        element_vdw_receptor_full_cartesian_pair_count: 0,
        element_vdw_receptor_cell_count: 0,
        element_vdw_receptor_severe_overlap_count: 0,
        element_vdw_receptor_minimum_distance_angstrom: 0.0,
        element_vdw_receptor_minimum_ratio: 0.0,
        reserved: [0; 4],
    }
}

fn validity_evaluated_row(
    slot_index: usize,
    checks: NativeFixed64ValidityChecks,
    measurements: NativeFixed64ValidityMeasurements,
) -> DockingPoseValidityRowV1 {
    let passed_check_mask = validity_passed_mask(checks);
    DockingPoseValidityRowV1 {
        slot_index: u32::try_from(slot_index).unwrap_or(0),
        status: VALIDITY_ROW_EVALUATED,
        failure_code: VALIDITY_FAILURE_NONE,
        upstream_scorer_failure_code: DOCKING_FAILURE_NONE,
        passed_check_mask,
        blocker_mask: VALIDITY_CHECK_ALL ^ passed_check_mask,
        observed_count: 0,
        atom_count: measurements.atom_count() as u64,
        rotation_orthogonality_max_error: measurements.rotation_orthogonality_max_error(),
        rotation_determinant: measurements.rotation_determinant(),
        max_bond_length_delta_angstrom: measurements.max_bond_length_delta_angstrom(),
        minimum_ligand_nonbonded_distance_angstrom: measurements
            .minimum_ligand_nonbonded_distance_angstrom(),
        evaluated_ligand_nonbonded_pair_count: measurements.evaluated_ligand_nonbonded_pair_count()
            as u64,
        excluded_ligand_pair_count: measurements.excluded_ligand_pair_count() as u64,
        minimum_receptor_ligand_distance_angstrom: measurements
            .minimum_receptor_ligand_distance_angstrom(),
        evaluated_receptor_ligand_pair_count: measurements.evaluated_receptor_ligand_pair_count()
            as u64,
        minimum_declared_chiral_volume: measurements.minimum_declared_chiral_volume(),
        declared_chirality_center_count: measurements.declared_chirality_center_count() as u64,
        maximum_pocket_center_distance_angstrom: measurements
            .maximum_pocket_center_distance_angstrom(),
        element_vdw_ligand_pair_count: measurements.element_vdw_ligand_pair_count() as u64,
        element_vdw_ligand_severe_overlap_count: measurements
            .element_vdw_ligand_severe_overlap_count()
            as u64,
        element_vdw_ligand_minimum_distance_angstrom: measurements
            .element_vdw_ligand_minimum_distance_angstrom(),
        element_vdw_ligand_minimum_ratio: measurements.element_vdw_ligand_minimum_ratio(),
        element_vdw_receptor_candidate_pair_count: measurements
            .element_vdw_receptor_candidate_pair_count()
            as u64,
        element_vdw_receptor_full_cartesian_pair_count: measurements
            .element_vdw_receptor_full_cartesian_pair_count()
            as u64,
        element_vdw_receptor_cell_count: measurements.element_vdw_receptor_cell_count() as u64,
        element_vdw_receptor_severe_overlap_count: measurements
            .element_vdw_receptor_severe_overlap_count()
            as u64,
        element_vdw_receptor_minimum_distance_angstrom: measurements
            .element_vdw_receptor_minimum_distance_angstrom(),
        element_vdw_receptor_minimum_ratio: measurements.element_vdw_receptor_minimum_ratio(),
        reserved: [0; 4],
    }
}

unsafe fn build_pose_validity_context(
    descriptor: &DockingPoseValidityContextSoaV1,
) -> Result<NativeFixed64ValidityContext, ProviderError> {
    validate_header::<DockingPoseValidityContextSoaV1>(
        descriptor.struct_size,
        descriptor.abi_version,
        "rust_cpu pose-validity context descriptor size mismatch",
    )?;
    if descriptor.unit_system != UNIT_SYSTEM_ANGSTROM_KCAL_MOL
        || descriptor.reserved0 != 0
        || !reserved_is_zero(&descriptor.reserved)
    {
        return Err(ProviderError::invalid(
            "rust_cpu pose-validity context units or reserved fields are invalid",
        ));
    }
    let receptor_count = checked_usize(
        descriptor.receptor_atom_count,
        "rust_cpu pose-validity receptor count exceeds host address space",
    )?;
    let ligand_count = checked_usize(
        descriptor.ligand_atom_count,
        "rust_cpu pose-validity ligand count exceeds host address space",
    )?;
    let bond_count = checked_usize(
        descriptor.bond_count,
        "rust_cpu pose-validity bond count exceeds host address space",
    )?;
    let exclusion_count = checked_usize(
        descriptor.ligand_exclusion_count,
        "rust_cpu pose-validity exclusion count exceeds host address space",
    )?;
    let chirality_count = checked_usize(
        descriptor.chirality_center_count,
        "rust_cpu pose-validity chirality count exceeds host address space",
    )?;
    let maximum_pairs = ligand_count.saturating_mul(ligand_count.saturating_sub(1)) / 2;
    if receptor_count == 0
        || receptor_count > 4_096
        || ligand_count == 0
        || ligand_count > 512
        || bond_count > maximum_pairs
        || exclusion_count > maximum_pairs
        || chirality_count > ligand_count
    {
        return Err(ProviderError::capacity(
            "rust_cpu pose-validity context denominator is outside fixed bounds",
        ));
    }

    macro_rules! checked {
        ($pointer:expr, $count:expr, $message:literal) => {{
            // SAFETY: Counts are bounded above and checked_slice validates the
            // pointer, alignment, and addressable byte range.
            unsafe { checked_slice($pointer, $count, $message)? }
        }};
    }
    let receptor_x = checked!(
        descriptor.receptor_x_angstrom,
        receptor_count,
        "rust_cpu pose-validity receptor x channel is null"
    );
    let receptor_y = checked!(
        descriptor.receptor_y_angstrom,
        receptor_count,
        "rust_cpu pose-validity receptor y channel is null"
    );
    let receptor_z = checked!(
        descriptor.receptor_z_angstrom,
        receptor_count,
        "rust_cpu pose-validity receptor z channel is null"
    );
    let receptor_radius = checked!(
        descriptor.receptor_vdw_radius_angstrom,
        receptor_count,
        "rust_cpu pose-validity receptor radius channel is null"
    );
    let ligand_x = checked!(
        descriptor.ligand_reference_x_angstrom,
        ligand_count,
        "rust_cpu pose-validity ligand x channel is null"
    );
    let ligand_y = checked!(
        descriptor.ligand_reference_y_angstrom,
        ligand_count,
        "rust_cpu pose-validity ligand y channel is null"
    );
    let ligand_z = checked!(
        descriptor.ligand_reference_z_angstrom,
        ligand_count,
        "rust_cpu pose-validity ligand z channel is null"
    );
    let ligand_radius = checked!(
        descriptor.ligand_vdw_radius_angstrom,
        ligand_count,
        "rust_cpu pose-validity ligand radius channel is null"
    );
    let bond_i = checked!(
        descriptor.bond_atom_i,
        bond_count,
        "rust_cpu pose-validity bond i channel is null"
    );
    let bond_j = checked!(
        descriptor.bond_atom_j,
        bond_count,
        "rust_cpu pose-validity bond j channel is null"
    );
    let exclusion_i = checked!(
        descriptor.ligand_exclusion_atom_i,
        exclusion_count,
        "rust_cpu pose-validity exclusion i channel is null"
    );
    let exclusion_j = checked!(
        descriptor.ligand_exclusion_atom_j,
        exclusion_count,
        "rust_cpu pose-validity exclusion j channel is null"
    );
    let chirality_center = checked!(
        descriptor.chirality_center_atom,
        chirality_count,
        "rust_cpu pose-validity chirality center channel is null"
    );
    let chirality_i = checked!(
        descriptor.chirality_atom_i,
        chirality_count,
        "rust_cpu pose-validity chirality i channel is null"
    );
    let chirality_j = checked!(
        descriptor.chirality_atom_j,
        chirality_count,
        "rust_cpu pose-validity chirality j channel is null"
    );
    let chirality_k = checked!(
        descriptor.chirality_atom_k,
        chirality_count,
        "rust_cpu pose-validity chirality k channel is null"
    );

    let receptor_coordinates = (0..receptor_count)
        .map(|index| Vec3::new(receptor_x[index], receptor_y[index], receptor_z[index]))
        .collect::<Vec<_>>();
    let ligand_coordinates = (0..ligand_count)
        .map(|index| Vec3::new(ligand_x[index], ligand_y[index], ligand_z[index]))
        .collect::<Vec<_>>();
    let pairs = |first: &[u64], second: &[u64], message| {
        first
            .iter()
            .zip(second)
            .map(|(left, right)| {
                Ok([
                    checked_usize(*left, message)?,
                    checked_usize(*right, message)?,
                ])
            })
            .collect::<Result<Vec<_>, ProviderError>>()
    };
    let bond_pairs = pairs(
        bond_i,
        bond_j,
        "rust_cpu pose-validity bond index overflows",
    )?;
    let exclusions = pairs(
        exclusion_i,
        exclusion_j,
        "rust_cpu pose-validity exclusion index overflows",
    )?;
    let chirality_centers = (0..chirality_count)
        .map(|index| {
            Ok([
                checked_usize(
                    chirality_center[index],
                    "rust_cpu pose-validity chirality index overflows",
                )?,
                checked_usize(
                    chirality_i[index],
                    "rust_cpu pose-validity chirality index overflows",
                )?,
                checked_usize(
                    chirality_j[index],
                    "rust_cpu pose-validity chirality index overflows",
                )?,
                checked_usize(
                    chirality_k[index],
                    "rust_cpu pose-validity chirality index overflows",
                )?,
            ])
        })
        .collect::<Result<Vec<_>, ProviderError>>()?;
    let config = NativeFixed64ValidityConfig::new(
        descriptor.bond_length_tolerance_angstrom,
        descriptor.ligand_self_clash_angstrom,
        descriptor.receptor_ligand_clash_angstrom,
        descriptor.rotation_tolerance,
        descriptor.chirality_volume_tolerance,
        descriptor.severe_overlap_scale,
        descriptor.contact_cell_size_angstrom,
        checked_usize(
            descriptor.max_pair_checks,
            "rust_cpu pose-validity pair capacity overflows",
        )?,
        checked_usize(
            descriptor.max_cross_checks,
            "rust_cpu pose-validity cross capacity overflows",
        )?,
        checked_usize(
            descriptor.max_element_ligand_pair_checks,
            "rust_cpu pose-validity element-ligand capacity overflows",
        )?,
        checked_usize(
            descriptor.max_element_receptor_candidate_pairs,
            "rust_cpu pose-validity element-receptor capacity overflows",
        )?,
    )
    .map_err(|error| ProviderError::invalid(error.message()))?;

    NativeFixed64ValidityContext::new(
        descriptor.authority_input_receipt_sha256,
        descriptor.receptor_system_sha256,
        descriptor.ligand_system_sha256,
        descriptor.scorer_context_receipt_sha256,
        NativeFixed64ValidityBackend::RustCpu,
        descriptor.backend_receipt_sha256,
        descriptor.contact_policy_sha256,
        ligand_coordinates,
        receptor_coordinates,
        ligand_radius.to_vec(),
        receptor_radius.to_vec(),
        bond_pairs,
        exclusions,
        chirality_centers,
        Vec3::new(
            descriptor.pocket_center_angstrom[0],
            descriptor.pocket_center_angstrom[1],
            descriptor.pocket_center_angstrom[2],
        ),
        descriptor.pocket_radius_angstrom,
        config,
    )
    .map_err(|error| ProviderError::invalid(error.message()))
}

unsafe fn evaluate_pose_validity_fixed64(
    context: &NativeFixed64ValidityContext,
    candidates: &DockingPoseValidityCandidateBatchSoaV1,
) -> Result<[DockingPoseValidityRowV1; FIXED64_CANDIDATE_COUNT], ProviderError> {
    validate_header::<DockingPoseValidityCandidateBatchSoaV1>(
        candidates.struct_size,
        candidates.abi_version,
        "rust_cpu pose-validity candidate batch size mismatch",
    )?;
    if candidates.unit_system != UNIT_SYSTEM_ANGSTROM_KCAL_MOL
        || candidates.reserved0 != 0
        || !reserved_is_zero(&candidates.reserved)
        || candidates.candidate_count != FIXED64_CANDIDATE_COUNT as u64
        || candidates.ligand_atom_count != context.reference_coordinates_angstrom().len() as u64
    {
        return Err(ProviderError::invalid(
            "rust_cpu pose-validity candidate batch identity is invalid",
        ));
    }
    let ligand_count = context.reference_coordinates_angstrom().len();
    let coordinate_count = FIXED64_CANDIDATE_COUNT
        .checked_mul(ligand_count)
        .ok_or_else(|| {
            ProviderError::capacity("rust_cpu pose-validity coordinate count overflows")
        })?;
    let states = unsafe {
        checked_slice(
            candidates.candidate_state,
            FIXED64_CANDIDATE_COUNT,
            "rust_cpu pose-validity candidate state channel is null",
        )?
    };
    let upstream_failures = unsafe {
        checked_slice(
            candidates.upstream_scorer_failure_code,
            FIXED64_CANDIDATE_COUNT,
            "rust_cpu pose-validity upstream failure channel is null",
        )?
    };
    let quaternion_x = unsafe {
        checked_slice(
            candidates.quaternion_x,
            FIXED64_CANDIDATE_COUNT,
            "rust_cpu pose-validity quaternion x channel is null",
        )?
    };
    let quaternion_y = unsafe {
        checked_slice(
            candidates.quaternion_y,
            FIXED64_CANDIDATE_COUNT,
            "rust_cpu pose-validity quaternion y channel is null",
        )?
    };
    let quaternion_z = unsafe {
        checked_slice(
            candidates.quaternion_z,
            FIXED64_CANDIDATE_COUNT,
            "rust_cpu pose-validity quaternion z channel is null",
        )?
    };
    let quaternion_w = unsafe {
        checked_slice(
            candidates.quaternion_w,
            FIXED64_CANDIDATE_COUNT,
            "rust_cpu pose-validity quaternion w channel is null",
        )?
    };
    let x = unsafe {
        checked_slice(
            candidates.x_angstrom,
            coordinate_count,
            "rust_cpu pose-validity candidate x channel is null",
        )?
    };
    let y = unsafe {
        checked_slice(
            candidates.y_angstrom,
            coordinate_count,
            "rust_cpu pose-validity candidate y channel is null",
        )?
    };
    let z = unsafe {
        checked_slice(
            candidates.z_angstrom,
            coordinate_count,
            "rust_cpu pose-validity candidate z channel is null",
        )?
    };
    for (&state, &upstream) in states.iter().zip(upstream_failures) {
        if (state == VALIDITY_CANDIDATE_UPSTREAM_FAILURE
            && !(DOCKING_FAILURE_UPSTREAM_NOT_ADMITTED..=DOCKING_FAILURE_NONFINITE_SCORE)
                .contains(&upstream))
            || (state == VALIDITY_CANDIDATE_EVALUATE && upstream != DOCKING_FAILURE_NONE)
            || (state != VALIDITY_CANDIDATE_UPSTREAM_FAILURE
                && state != VALIDITY_CANDIDATE_EVALUATE)
        {
            return Err(ProviderError::invalid(
                "rust_cpu pose-validity candidate state/failure binding is invalid",
            ));
        }
    }
    let kernel = context
        .prepare_rust_cpu_kernel()
        .map_err(|error| ProviderError::invalid(error.message()))?;
    let mut rows = Vec::with_capacity(FIXED64_CANDIDATE_COUNT);
    for slot in 0..FIXED64_CANDIDATE_COUNT {
        if states[slot] == VALIDITY_CANDIDATE_UPSTREAM_FAILURE {
            rows.push(validity_failure_row(
                slot,
                VALIDITY_ROW_UPSTREAM_SCORER_FAILURE,
                VALIDITY_FAILURE_UPSTREAM_SCORER,
                upstream_failures[slot],
                0,
            ));
            continue;
        }
        let offset = slot * ligand_count;
        let pose = (0..ligand_count)
            .map(|atom| Vec3::new(x[offset + atom], y[offset + atom], z[offset + atom]))
            .collect::<Vec<_>>();
        let quaternion = Quaternion::new(
            quaternion_x[slot],
            quaternion_y[slot],
            quaternion_z[slot],
            quaternion_w[slot],
        );
        match kernel.evaluate_coordinates(&pose, quaternion) {
            NativeFixed64ValidityKernelOutcome::Evaluated {
                checks,
                measurements,
            } => rows.push(validity_evaluated_row(slot, checks, measurements)),
            NativeFixed64ValidityKernelOutcome::TypedFailure(failure) => {
                rows.push(validity_failure_row(
                    slot,
                    VALIDITY_ROW_TYPED_FAILURE,
                    validity_failure_code(failure.failure_code()),
                    DOCKING_FAILURE_NONE,
                    failure.observed_count(),
                ));
            }
        }
    }
    rows.try_into().map_err(|_| ProviderError {
        status: STATUS_INTERNAL_ERROR,
        message: "rust_cpu pose-validity fixed64 denominator changed internally",
    })
}

struct StableTopKProviderOutput {
    rows: [DockingStableTopKRowV1; FIXED64_CANDIDATE_COUNT],
    primary_slot_indices: [u32; FIXED64_CANDIDATE_COUNT],
    primary_count: u64,
    valid_slot_indices: [u32; FIXED64_CANDIDATE_COUNT],
    valid_count: u64,
}

fn digest_is_zero(digest: &[u8; 32]) -> bool {
    digest.iter().all(|value| *value == 0)
}

fn scorer_failure_rank_evidence_is_zero(row: &DockingScorerRowV1) -> bool {
    row.weighted_terms.iter().all(|value| *value == 0.0)
        && row.total_score == 0.0
        && row.hbond_count == 0
        && row.hydrophobic_contact_count == 0
        && row.buried_polar_count == 0
}

fn scorer_failure_pair_evidence_is_valid(row: &DockingScorerRowV1) -> bool {
    match row.failure_code {
        DOCKING_FAILURE_UPSTREAM_NOT_ADMITTED | DOCKING_FAILURE_INVALID_CANDIDATE_COORDINATES => {
            row.receptor_candidate_pair_count == 0 && row.ligand_pair_count == 0
        }
        DOCKING_FAILURE_RECEPTOR_PAIR_CAPACITY => {
            row.receptor_candidate_pair_count > 0 && row.ligand_pair_count == 0
        }
        DOCKING_FAILURE_LIGAND_PAIR_CAPACITY => row.ligand_pair_count > 0,
        DOCKING_FAILURE_DEGENERATE_ROTOR | DOCKING_FAILURE_NONFINITE_SCORE => true,
        _ => false,
    }
}

unsafe fn rank_stable_top_k_fixed64(
    input: &DockingStableTopKInputV1,
) -> Result<StableTopKProviderOutput, ProviderError> {
    validate_header::<DockingStableTopKInputV1>(
        input.struct_size,
        input.abi_version,
        "rust_cpu stable Top-K input size mismatch",
    )?;
    if input.candidate_count != FIXED64_CANDIDATE_COUNT as u64
        || input.top_k_limit != STABLE_TOP_K_LIMIT
        || input.unit_system != UNIT_SYSTEM_ANGSTROM_KCAL_MOL
        || !reserved_is_zero(&input.reserved)
    {
        return Err(ProviderError::invalid(
            "rust_cpu stable Top-K input identity is invalid",
        ));
    }
    let scorer_rows = unsafe {
        checked_slice(
            input.scorer_rows,
            FIXED64_CANDIDATE_COUNT,
            "rust_cpu stable Top-K scorer rows are null",
        )?
    };
    let validity_rows = unsafe {
        checked_slice(
            input.validity_rows,
            FIXED64_CANDIDATE_COUNT,
            "rust_cpu stable Top-K validity rows are null",
        )?
    };
    let coordinate_digests = unsafe {
        checked_slice(
            input.coordinate_sha256,
            FIXED64_CANDIDATE_COUNT * 32,
            "rust_cpu stable Top-K coordinate identities are null",
        )?
    };
    let mut kernel_rows = Vec::with_capacity(FIXED64_CANDIDATE_COUNT);
    for slot in 0..FIXED64_CANDIDATE_COUNT {
        let scorer = scorer_rows[slot];
        let validity = validity_rows[slot];
        if scorer.slot_index != slot as u32
            || validity.slot_index != slot as u32
            || scorer.reserved0 != 0
            || !reserved_is_zero(&scorer.reserved)
            || !reserved_is_zero(&validity.reserved)
        {
            return Err(ProviderError::invalid(
                "rust_cpu stable Top-K input slots are cross-wired",
            ));
        }
        let digest_slice = &coordinate_digests[slot * 32..(slot + 1) * 32];
        let mut digest = [0u8; 32];
        digest.copy_from_slice(digest_slice);
        let (scorer_status, total_score, coordinate_sha256) = match scorer.status {
            DOCKING_ROW_SCORED => {
                let score_term_sum = scorer.weighted_terms.iter().sum::<f64>();
                if scorer.failure_code != DOCKING_FAILURE_NONE
                    || !scorer.total_score.is_finite()
                    || scorer.weighted_terms.iter().any(|value| !value.is_finite())
                    || (score_term_sum - scorer.total_score).abs() > 1.0e-12
                    || digest_is_zero(&digest)
                {
                    return Err(ProviderError::invalid(
                        "rust_cpu stable Top-K scored evidence is invalid",
                    ));
                }
                (
                    NativeScorerV1RowStatus::Scored,
                    Some(scorer.total_score),
                    Some(digest),
                )
            }
            DOCKING_ROW_TYPED_FAILURE => {
                if !(DOCKING_FAILURE_UPSTREAM_NOT_ADMITTED..=DOCKING_FAILURE_NONFINITE_SCORE)
                    .contains(&scorer.failure_code)
                    || !digest_is_zero(&digest)
                    || !scorer_failure_rank_evidence_is_zero(&scorer)
                    || !scorer_failure_pair_evidence_is_valid(&scorer)
                {
                    return Err(ProviderError::invalid(
                        "rust_cpu stable Top-K scorer failure is invalid",
                    ));
                }
                (NativeScorerV1RowStatus::TypedFailure, None, None)
            }
            _ => {
                return Err(ProviderError::invalid(
                    "rust_cpu stable Top-K scorer status is invalid",
                ));
            }
        };
        let (validity_status, valid) = match validity.status {
            VALIDITY_ROW_EVALUATED => {
                if validity.failure_code != VALIDITY_FAILURE_NONE
                    || validity.upstream_scorer_failure_code != DOCKING_FAILURE_NONE
                    || validity.passed_check_mask & !VALIDITY_CHECK_ALL != 0
                    || validity.blocker_mask != (VALIDITY_CHECK_ALL ^ validity.passed_check_mask)
                {
                    return Err(ProviderError::invalid(
                        "rust_cpu stable Top-K evaluated validity row is invalid",
                    ));
                }
                (
                    NativeFixed64ValidityRowStatus::Evaluated,
                    validity.passed_check_mask == VALIDITY_CHECK_ALL,
                )
            }
            VALIDITY_ROW_UPSTREAM_SCORER_FAILURE => {
                if validity.failure_code != VALIDITY_FAILURE_UPSTREAM_SCORER
                    || validity.upstream_scorer_failure_code != scorer.failure_code
                {
                    return Err(ProviderError::invalid(
                        "rust_cpu stable Top-K upstream failure is cross-wired",
                    ));
                }
                (NativeFixed64ValidityRowStatus::UpstreamScorerFailure, false)
            }
            VALIDITY_ROW_TYPED_FAILURE => {
                if !(VALIDITY_FAILURE_INVALID_CANDIDATE_COORDINATES
                    ..=VALIDITY_FAILURE_NONFINITE_DERIVED_MEASUREMENT)
                    .contains(&validity.failure_code)
                    || validity.upstream_scorer_failure_code != DOCKING_FAILURE_NONE
                {
                    return Err(ProviderError::invalid(
                        "rust_cpu stable Top-K typed validity failure is invalid",
                    ));
                }
                (NativeFixed64ValidityRowStatus::TypedFailure, false)
            }
            _ => {
                return Err(ProviderError::invalid(
                    "rust_cpu stable Top-K validity status is invalid",
                ));
            }
        };
        kernel_rows.push(
            NativeFixed64StableTopKInputRow::new(
                slot,
                scorer_status,
                validity_status,
                total_score,
                coordinate_sha256,
                valid,
            )
            .map_err(|_| {
                ProviderError::invalid("rust_cpu stable Top-K scorer/validity binding is invalid")
            })?,
        );
    }
    let kernel_rows: [NativeFixed64StableTopKInputRow; FIXED64_CANDIDATE_COUNT] =
        kernel_rows.try_into().map_err(|_| ProviderError {
            status: STATUS_INTERNAL_ERROR,
            message: "rust_cpu stable Top-K denominator changed internally",
        })?;
    let ranking = rank_native_fixed64_stable_top_k_kernel(&kernel_rows).map_err(|_| {
        ProviderError::invalid("rust_cpu stable Top-K kernel rejected input binding")
    })?;
    let rows = core::array::from_fn(|slot| {
        let input_row = kernel_rows[slot];
        let rank_eligible = input_row.scorer_status() == NativeScorerV1RowStatus::Scored;
        let valid_rank_eligible = ranking.stable_valid_rank(slot).is_some();
        DockingStableTopKRowV1 {
            slot_index: slot as u32,
            rank_eligible: u8::from(rank_eligible),
            valid_rank_eligible: u8::from(valid_rank_eligible),
            reserved0: 0,
            stable_rank: ranking.stable_rank(slot).unwrap_or(0) as u32,
            stable_valid_rank: ranking.stable_valid_rank(slot).unwrap_or(0) as u32,
            total_score: input_row.total_score().unwrap_or(0.0),
            coordinate_sha256: input_row.coordinate_sha256().unwrap_or([0; 32]),
            reserved: [0; 4],
        }
    });
    let mut primary_slot_indices = [0u32; FIXED64_CANDIDATE_COUNT];
    for (destination, source) in primary_slot_indices
        .iter_mut()
        .zip(ranking.primary_slot_indices())
    {
        *destination = *source as u32;
    }
    let mut valid_slot_indices = [0u32; FIXED64_CANDIDATE_COUNT];
    for (destination, source) in valid_slot_indices
        .iter_mut()
        .zip(ranking.valid_slot_indices())
    {
        *destination = *source as u32;
    }
    Ok(StableTopKProviderOutput {
        rows,
        primary_slot_indices,
        primary_count: ranking.primary_slot_indices().len() as u64,
        valid_slot_indices,
        valid_count: ranking.valid_slot_indices().len() as u64,
    })
}

struct RmsdClusterProviderOutput {
    rows: [DockingRmsdClusterRowV1; FIXED64_CANDIDATE_COUNT],
    representative_slot_indices: [u32; FIXED64_CANDIDATE_COUNT],
    cluster_count: u64,
    top_k_slot_indices: [u32; NATIVE_FIXED64_TOP_K_LIMIT],
    top_k_count: u64,
}

unsafe fn cluster_direct_rmsd_fixed64(
    input: &DockingRmsdClusterInputV1,
) -> Result<RmsdClusterProviderOutput, ProviderError> {
    validate_header::<DockingRmsdClusterInputV1>(
        input.struct_size,
        input.abi_version,
        "rust_cpu RMSD cluster input size mismatch",
    )?;
    if input.candidate_count != FIXED64_CANDIDATE_COUNT as u64
        || input.ligand_atom_count == 0
        || input.ligand_atom_count > 512
        || input.valid_index_count > FIXED64_CANDIDATE_COUNT as u64
        || input.top_k_limit != STABLE_TOP_K_LIMIT
        || input.unit_system != UNIT_SYSTEM_ANGSTROM_KCAL_MOL
        || !input.rmsd_threshold_angstrom.is_finite()
        || input.rmsd_threshold_angstrom <= 0.0
        || !reserved_is_zero(&input.reserved)
    {
        return Err(ProviderError::invalid(
            "rust_cpu RMSD cluster input identity is invalid",
        ));
    }
    let atom_count = usize::try_from(input.ligand_atom_count).map_err(|_| {
        ProviderError::invalid("rust_cpu RMSD cluster atom count does not fit usize")
    })?;
    let coordinate_count = FIXED64_CANDIDATE_COUNT
        .checked_mul(atom_count)
        .ok_or_else(|| ProviderError::invalid("rust_cpu RMSD coordinate count overflowed"))?;
    let ranking_rows = unsafe {
        checked_slice(
            input.ranking_rows,
            FIXED64_CANDIDATE_COUNT,
            "rust_cpu RMSD ranking rows are null",
        )?
    };
    let valid_count = usize::try_from(input.valid_index_count)
        .map_err(|_| ProviderError::invalid("rust_cpu RMSD valid count does not fit usize"))?;
    let valid_indices = unsafe {
        checked_slice(
            input.valid_slot_indices,
            valid_count,
            "rust_cpu RMSD valid index list is null",
        )?
    };
    let x = unsafe {
        checked_slice(
            input.x_angstrom,
            coordinate_count,
            "rust_cpu RMSD x coordinates are null",
        )?
    };
    let y = unsafe {
        checked_slice(
            input.y_angstrom,
            coordinate_count,
            "rust_cpu RMSD y coordinates are null",
        )?
    };
    let z = unsafe {
        checked_slice(
            input.z_angstrom,
            coordinate_count,
            "rust_cpu RMSD z coordinates are null",
        )?
    };

    let mut kernel_rows = Vec::with_capacity(FIXED64_CANDIDATE_COUNT);
    let mut seen_valid = [false; FIXED64_CANDIDATE_COUNT];
    for (offset, slot) in valid_indices.iter().copied().enumerate() {
        let slot = usize::try_from(slot)
            .map_err(|_| ProviderError::invalid("rust_cpu RMSD valid slot is invalid"))?;
        if slot >= FIXED64_CANDIDATE_COUNT || seen_valid[slot] {
            return Err(ProviderError::invalid(
                "rust_cpu RMSD valid slot list is duplicated or out of range",
            ));
        }
        seen_valid[slot] = true;
        if ranking_rows[slot].stable_valid_rank != (offset + 1) as u32
            || ranking_rows[slot].valid_rank_eligible != 1
        {
            return Err(ProviderError::invalid(
                "rust_cpu RMSD valid slot list is cross-wired",
            ));
        }
    }
    for (slot, row) in ranking_rows.iter().copied().enumerate() {
        if row.slot_index != slot as u32
            || row.reserved0 != 0
            || !reserved_is_zero(&row.reserved)
            || row.rank_eligible > 1
            || row.valid_rank_eligible > 1
        {
            return Err(ProviderError::invalid(
                "rust_cpu RMSD ranking row identity is invalid",
            ));
        }
        let eligible = seen_valid[slot];
        if eligible {
            if row.valid_rank_eligible != 1
                || row.stable_valid_rank == 0
                || digest_is_zero(&row.coordinate_sha256)
            {
                return Err(ProviderError::invalid(
                    "rust_cpu RMSD eligible ranking evidence is invalid",
                ));
            }
        } else if row.valid_rank_eligible != 0 || row.stable_valid_rank != 0 {
            return Err(ProviderError::invalid(
                "rust_cpu RMSD ineligible ranking evidence is invalid",
            ));
        }
        kernel_rows.push(
            NativeFixed64RmsdClusterInputRow::new(
                slot,
                eligible,
                if eligible {
                    row.stable_valid_rank as usize
                } else {
                    0
                },
                eligible.then_some(row.coordinate_sha256),
            )
            .map_err(|_| ProviderError::invalid("rust_cpu RMSD row binding is invalid"))?,
        );
    }
    let kernel_rows: [NativeFixed64RmsdClusterInputRow; FIXED64_CANDIDATE_COUNT] =
        kernel_rows.try_into().map_err(|_| ProviderError {
            status: STATUS_INTERNAL_ERROR,
            message: "rust_cpu RMSD denominator changed internally",
        })?;
    let coordinates = (0..coordinate_count)
        .map(|index| Vec3::new(x[index], y[index], z[index]))
        .collect::<Vec<_>>();
    let clustered = cluster_native_fixed64_direct_rmsd_kernel(
        &kernel_rows,
        &coordinates,
        atom_count,
        input.rmsd_threshold_angstrom,
    )
    .map_err(|error| {
        if error.code() == NativeFixed64RmsdClusterErrorCode::NonFiniteDerivedValue {
            ProviderError {
                status: STATUS_NUMERICAL_ERROR,
                message: "rust_cpu RMSD cluster derived a non-finite distance",
            }
        } else {
            ProviderError::invalid("rust_cpu RMSD kernel rejected input")
        }
    })?;
    let rows = core::array::from_fn(|slot| {
        let row = clustered.rows()[slot];
        DockingRmsdClusterRowV1 {
            slot_index: slot as u32,
            status: if row.eligible() {
                RMSD_CLUSTER_ROW_CLUSTERED
            } else {
                RMSD_CLUSTER_ROW_UPSTREAM_NOT_VALID
            },
            cluster_eligible: u8::from(row.eligible()),
            representative: u8::from(row.representative()),
            top_k_representative: u8::from(row.top_k_representative()),
            reserved0: 0,
            stable_valid_rank: row.stable_valid_rank() as u32,
            cluster_id: row.cluster_id() as u32,
            representative_slot_index: row.representative_slot_index() as u32,
            cluster_rank: row.cluster_rank() as u32,
            top_k_rank: row.top_k_rank() as u32,
            cluster_size: row.cluster_size() as u32,
            reserved1: 0,
            direct_rmsd_to_representative_angstrom: row.direct_rmsd_to_representative_angstrom(),
            coordinate_sha256: row.coordinate_sha256().unwrap_or([0; 32]),
            reserved: [0; 4],
        }
    });
    let mut representative_slot_indices = [0u32; FIXED64_CANDIDATE_COUNT];
    for (destination, source) in representative_slot_indices
        .iter_mut()
        .zip(clustered.representative_slot_indices())
    {
        *destination = *source as u32;
    }
    let mut top_k_slot_indices = [0u32; NATIVE_FIXED64_TOP_K_LIMIT];
    for (destination, source) in top_k_slot_indices
        .iter_mut()
        .zip(clustered.top_k_slot_indices())
    {
        *destination = *source as u32;
    }
    Ok(RmsdClusterProviderOutput {
        rows,
        representative_slot_indices,
        cluster_count: clustered.cluster_count() as u64,
        top_k_slot_indices,
        top_k_count: clustered.top_k_slot_indices().len() as u64,
    })
}

unsafe fn evaluate_impl(
    system: *const SystemV1,
    forcefield: *const ForceFieldV1,
    neighbor_pairs: Option<&[Pair]>,
    compute_forces: u8,
    out_energy: *mut EnergyV1,
    out_forces: *mut ForceOutputV1,
) -> Result<(), ProviderError> {
    if compute_forces > 1 {
        return Err(ProviderError::invalid(
            "compute_forces must be exactly zero or one",
        ));
    }
    let system = unsafe {
        system
            .as_ref()
            .ok_or_else(|| ProviderError::invalid("system descriptor is null"))?
    };
    let forcefield = unsafe {
        forcefield
            .as_ref()
            .ok_or_else(|| ProviderError::invalid("force-field descriptor is null"))?
    };
    let compute_forces = compute_forces == 1;
    // Validate output capacity and aliasing before any potentially expensive
    // calculation, but retain transactional writes until evaluation succeeds.
    let output_channels =
        unsafe { validate_outputs(system.atom_count, compute_forces, out_energy, out_forces)? };
    let (system, forcefield) = unsafe { build_inputs(system, forcefield)? };
    let evaluation = match neighbor_pairs {
        Some(pairs) => {
            kernel::evaluate_with_neighbor_pairs(&system, &forcefield, pairs, compute_forces)
        }
        None => kernel::evaluate(&system, &forcefield, compute_forces),
    }
    .map_err(|error| ProviderError {
        status: error.status,
        message: error.message,
    })?;

    let energy = EnergyV1 {
        struct_size: u32::try_from(size_of::<EnergyV1>()).unwrap_or(0),
        abi_version: PROVIDER_ABI_VERSION,
        harmonic_bond: evaluation.energy.harmonic_bond,
        harmonic_angle: evaluation.energy.harmonic_angle,
        periodic_torsion: evaluation.energy.periodic_torsion,
        lennard_jones: evaluation.energy.lennard_jones,
        coulomb: evaluation.energy.coulomb,
        total: evaluation.energy.total,
        reserved: [0; 4],
    };
    if let Some((x, y, z)) = output_channels {
        x.copy_from_slice(&evaluation.force_x);
        y.copy_from_slice(&evaluation.force_y);
        z.copy_from_slice(&evaluation.force_z);
    }
    // SAFETY: Output identity was validated and no write occurs before success.
    unsafe { ptr::write(out_energy, energy) };
    Ok(())
}

unsafe fn evaluate_reusing_force_output_impl(
    system: *const SystemV1,
    forcefield: *const ForceFieldV1,
    neighbor_pairs: Option<&[Pair]>,
    prevalidated_neighbor_pairs: bool,
    inout_forcefield_validated: *mut u8,
    out_energy: *mut EnergyV1,
    out_forces: *mut ForceOutputV1,
) -> Result<(), ProviderError> {
    let system = unsafe {
        system
            .as_ref()
            .ok_or_else(|| ProviderError::invalid("system descriptor is null"))?
    };
    let forcefield = unsafe {
        forcefield
            .as_ref()
            .ok_or_else(|| ProviderError::invalid("force-field descriptor is null"))?
    };
    let forcefield_validated = unsafe {
        inout_forcefield_validated
            .as_mut()
            .ok_or_else(|| ProviderError::invalid("force-field validation state is null"))?
    };
    if *forcefield_validated > 1 {
        return Err(ProviderError::invalid(
            "force-field validation state must be exactly zero or one",
        ));
    }
    // This internal dynamics route deliberately writes directly into disposable
    // caller-owned force storage. Descriptor, capacity, and alias validation
    // still complete before the first force write; energy remains transactional.
    let output_channels =
        unsafe { validate_outputs(system.atom_count, true, out_energy, out_forces)? }.ok_or(
            ProviderError {
                status: STATUS_INTERNAL_ERROR,
                message: "rust_cpu force output validation changed internally",
            },
        )?;
    let validate_immutable_forcefield = *forcefield_validated == 0;
    let (system, forcefield) =
        unsafe { build_inputs_impl(system, forcefield, validate_immutable_forcefield)? };
    let energy = match neighbor_pairs {
        Some(pairs) if prevalidated_neighbor_pairs => {
            kernel::evaluate_with_prevalidated_neighbor_pairs_into(
                &system,
                &forcefield,
                pairs,
                output_channels,
            )
        }
        Some(pairs) => {
            kernel::evaluate_with_neighbor_pairs_into(&system, &forcefield, pairs, output_channels)
        }
        None => kernel::evaluate_into(&system, &forcefield, output_channels),
    }
    .map_err(|error| ProviderError {
        status: error.status,
        message: error.message,
    })?;

    let energy = EnergyV1 {
        struct_size: u32::try_from(size_of::<EnergyV1>()).unwrap_or(0),
        abi_version: PROVIDER_ABI_VERSION,
        harmonic_bond: energy.harmonic_bond,
        harmonic_angle: energy.harmonic_angle,
        periodic_torsion: energy.periodic_torsion,
        lennard_jones: energy.lennard_jones,
        coulomb: energy.coulomb,
        total: energy.total,
        reserved: [0; 4],
    };
    // The C++ simulation owns an immutable force field. Once a successful
    // dynamics evaluation has validated it, later evaluations only need to
    // validate the dynamic system channels and structural descriptor shape.
    *forcefield_validated = 1;
    // SAFETY: Output identity was validated and energy is committed only after
    // the direct force evaluation succeeds.
    unsafe { ptr::write(out_energy, energy) };
    Ok(())
}

#[no_mangle]
pub extern "C" fn bg_rust_cpu_provider_abi_version_v1() -> u32 {
    PROVIDER_ABI_VERSION
}

/// Evaluate through the hidden provider ABI.
///
/// # Safety
/// Every non-null descriptor and channel must point to initialized storage of
/// the declared size and alignment for the duration of this call. Energy,
/// force, and error output storage must be writable and must not overlap any
/// input descriptor or input channel. Energy and error storage must not overlap
/// each other or a force channel. Pairwise force-channel overlap is accepted as
/// a raw input condition only so it can be detected and rejected before mutable
/// Rust slices are formed.
#[no_mangle]
pub unsafe extern "C" fn bg_rust_cpu_evaluate_v1(
    system: *const SystemV1,
    forcefield: *const ForceFieldV1,
    compute_forces: u8,
    out_energy: *mut EnergyV1,
    out_forces: *mut ForceOutputV1,
    out_error: *mut ErrorV1,
) -> i32 {
    let error = unsafe {
        match out_error.as_mut() {
            Some(error) => error,
            None => return STATUS_INVALID_ARGUMENT,
        }
    };
    if validate_header::<ErrorV1>(
        error.struct_size,
        error.abi_version,
        "rust_cpu error output size mismatch",
    )
    .is_err()
        || !reserved_is_zero(&error.reserved)
    {
        return STATUS_ABI_MISMATCH;
    }
    clear_error(error);
    let result = catch_unwind(AssertUnwindSafe(|| unsafe {
        evaluate_impl(
            system,
            forcefield,
            None,
            compute_forces,
            out_energy,
            out_forces,
        )
    }));
    match result {
        Ok(Ok(())) => STATUS_OK,
        Ok(Err(provider_error)) => {
            write_error(error, provider_error.message);
            provider_error.status
        }
        Err(_) => {
            write_error(error, "rust_cpu provider panicked");
            STATUS_INTERNAL_ERROR
        }
    }
}

/// Evaluate through a caller-owned canonical neighbor-pair slice.
///
/// # Safety
/// The base evaluator safety contract applies. `neighbor_pairs` must point to
/// `neighbor_pair_count` readable canonical pair rows for the duration of this
/// call; a zero count permits a null pointer.
#[no_mangle]
pub unsafe extern "C" fn bg_rust_cpu_evaluate_with_neighbor_pairs_v1(
    system: *const SystemV1,
    forcefield: *const ForceFieldV1,
    neighbor_pair_count: usize,
    neighbor_pairs: *const Pair,
    compute_forces: u8,
    out_energy: *mut EnergyV1,
    out_forces: *mut ForceOutputV1,
    out_error: *mut ErrorV1,
) -> i32 {
    let error = unsafe {
        match out_error.as_mut() {
            Some(error) => error,
            None => return STATUS_INVALID_ARGUMENT,
        }
    };
    if validate_header::<ErrorV1>(
        error.struct_size,
        error.abi_version,
        "rust_cpu error output size mismatch",
    )
    .is_err()
        || !reserved_is_zero(&error.reserved)
    {
        return STATUS_ABI_MISMATCH;
    }
    clear_error(error);
    let pairs = unsafe {
        match checked_slice(
            neighbor_pairs,
            neighbor_pair_count,
            "neighbor pairs are null",
        ) {
            Ok(pairs) => pairs,
            Err(provider_error) => {
                write_error(error, provider_error.message);
                return provider_error.status;
            }
        }
    };
    let result = catch_unwind(AssertUnwindSafe(|| unsafe {
        evaluate_impl(
            system,
            forcefield,
            Some(pairs),
            compute_forces,
            out_energy,
            out_forces,
        )
    }));
    match result {
        Ok(Ok(())) => STATUS_OK,
        Ok(Err(provider_error)) => {
            write_error(error, provider_error.message);
            provider_error.status
        }
        Err(_) => {
            write_error(error, "rust_cpu provider panicked");
            STATUS_INTERNAL_ERROR
        }
    }
}

/// Evaluate directly into reusable force storage.
///
/// This hidden dynamics-only entry point may modify force channels when the
/// scientific evaluation fails. Energy is committed only on success.
///
/// # Safety
/// The base evaluator safety contract applies. `inout_forcefield_validated`
/// must point to a live byte initialized to zero. Once this function writes
/// one, the force-field descriptor and every channel it references must remain
/// immutable and live for every call using that byte.
#[no_mangle]
pub unsafe extern "C" fn bg_rust_cpu_evaluate_reusing_force_output_v1(
    system: *const SystemV1,
    forcefield: *const ForceFieldV1,
    inout_forcefield_validated: *mut u8,
    out_energy: *mut EnergyV1,
    out_forces: *mut ForceOutputV1,
    out_error: *mut ErrorV1,
) -> i32 {
    let error = unsafe {
        match out_error.as_mut() {
            Some(error) => error,
            None => return STATUS_INVALID_ARGUMENT,
        }
    };
    if validate_header::<ErrorV1>(
        error.struct_size,
        error.abi_version,
        "rust_cpu error output size mismatch",
    )
    .is_err()
        || !reserved_is_zero(&error.reserved)
    {
        return STATUS_ABI_MISMATCH;
    }
    clear_error(error);
    let result = catch_unwind(AssertUnwindSafe(|| unsafe {
        evaluate_reusing_force_output_impl(
            system,
            forcefield,
            None,
            false,
            inout_forcefield_validated,
            out_energy,
            out_forces,
        )
    }));
    match result {
        Ok(Ok(())) => STATUS_OK,
        Ok(Err(provider_error)) => {
            write_error(error, provider_error.message);
            provider_error.status
        }
        Err(_) => {
            write_error(error, "rust_cpu provider panicked");
            STATUS_INTERNAL_ERROR
        }
    }
}

/// Evaluate canonical neighbor pairs directly into reusable force storage.
///
/// This hidden dynamics-only entry point may modify force channels when the
/// scientific evaluation fails. Energy is committed only on success.
///
/// # Safety
/// The base evaluator and caller-owned neighbor-pair safety contracts apply.
/// `inout_forcefield_validated` must point to a live byte initialized to zero.
/// Once this function writes one, the force-field descriptor and every channel
/// it references must remain immutable and live for every call using that byte.
#[no_mangle]
pub unsafe extern "C" fn bg_rust_cpu_evaluate_with_neighbor_pairs_reusing_force_output_v1(
    system: *const SystemV1,
    forcefield: *const ForceFieldV1,
    neighbor_pair_count: usize,
    neighbor_pairs: *const Pair,
    inout_forcefield_validated: *mut u8,
    out_energy: *mut EnergyV1,
    out_forces: *mut ForceOutputV1,
    out_error: *mut ErrorV1,
) -> i32 {
    unsafe {
        evaluate_with_neighbor_pairs_reusing_force_output_entry(
            system,
            forcefield,
            neighbor_pair_count,
            neighbor_pairs,
            false,
            inout_forcefield_validated,
            out_energy,
            out_forces,
            out_error,
        )
    }
}

/// Evaluate a dynamics-owned prevalidated canonical neighbor-pair slice
/// directly into reusable force storage.
///
/// This hidden entry point is restricted to the native dynamics owner that
/// built the pair slice with the canonical CPU neighbor-list implementation.
/// Public and general supplied-pair entry points retain full row validation.
///
/// # Safety
/// The reusable-force-output contract applies. The supplied pair rows must
/// already be unique, strictly sorted, in range, and canonical.
#[no_mangle]
pub unsafe extern "C" fn bg_rust_cpu_evaluate_with_prevalidated_neighbor_pairs_reusing_force_output_v1(
    system: *const SystemV1,
    forcefield: *const ForceFieldV1,
    neighbor_pair_count: usize,
    neighbor_pairs: *const Pair,
    inout_forcefield_validated: *mut u8,
    out_energy: *mut EnergyV1,
    out_forces: *mut ForceOutputV1,
    out_error: *mut ErrorV1,
) -> i32 {
    unsafe {
        evaluate_with_neighbor_pairs_reusing_force_output_entry(
            system,
            forcefield,
            neighbor_pair_count,
            neighbor_pairs,
            true,
            inout_forcefield_validated,
            out_energy,
            out_forces,
            out_error,
        )
    }
}

#[allow(clippy::too_many_arguments)]
unsafe fn evaluate_with_neighbor_pairs_reusing_force_output_entry(
    system: *const SystemV1,
    forcefield: *const ForceFieldV1,
    neighbor_pair_count: usize,
    neighbor_pairs: *const Pair,
    prevalidated_neighbor_pairs: bool,
    inout_forcefield_validated: *mut u8,
    out_energy: *mut EnergyV1,
    out_forces: *mut ForceOutputV1,
    out_error: *mut ErrorV1,
) -> i32 {
    let error = unsafe {
        match out_error.as_mut() {
            Some(error) => error,
            None => return STATUS_INVALID_ARGUMENT,
        }
    };
    if validate_header::<ErrorV1>(
        error.struct_size,
        error.abi_version,
        "rust_cpu error output size mismatch",
    )
    .is_err()
        || !reserved_is_zero(&error.reserved)
    {
        return STATUS_ABI_MISMATCH;
    }
    clear_error(error);
    let pairs = unsafe {
        match checked_slice(
            neighbor_pairs,
            neighbor_pair_count,
            "neighbor pairs are null",
        ) {
            Ok(pairs) => pairs,
            Err(provider_error) => {
                write_error(error, provider_error.message);
                return provider_error.status;
            }
        }
    };
    let result = catch_unwind(AssertUnwindSafe(|| unsafe {
        evaluate_reusing_force_output_impl(
            system,
            forcefield,
            Some(pairs),
            prevalidated_neighbor_pairs,
            inout_forcefield_validated,
            out_energy,
            out_forces,
        )
    }));
    match result {
        Ok(Ok(())) => STATUS_OK,
        Ok(Err(provider_error)) => {
            write_error(error, provider_error.message);
            provider_error.status
        }
        Err(_) => {
            write_error(error, "rust_cpu provider panicked");
            STATUS_INTERNAL_ERROR
        }
    }
}

/// Construct a persistent Rust geometric-admission context.
///
/// # Safety
/// The descriptor and all declared channels must remain readable for this
/// call. `out_state` and `out_error` must be writable and correctly aligned.
#[no_mangle]
pub unsafe extern "C" fn bg_rust_cpu_docking_geometric_admission_v1_create(
    descriptor: *const DockingGeometricAdmissionContextSoaV1,
    out_state: *mut *mut c_void,
    out_error: *mut ErrorV1,
) -> i32 {
    let error = unsafe {
        match out_error.as_mut() {
            Some(error) => error,
            None => return STATUS_INVALID_ARGUMENT,
        }
    };
    if validate_header::<ErrorV1>(
        error.struct_size,
        error.abi_version,
        "rust_cpu error output size mismatch",
    )
    .is_err()
        || !reserved_is_zero(&error.reserved)
    {
        return STATUS_ABI_MISMATCH;
    }
    clear_error(error);
    let state_output = unsafe {
        match out_state.as_mut() {
            Some(output) => output,
            None => {
                write_error(error, "rust_cpu geometric-admission state output is null");
                return STATUS_INVALID_ARGUMENT;
            }
        }
    };
    *state_output = ptr::null_mut();
    let descriptor = unsafe {
        match descriptor.as_ref() {
            Some(descriptor) => descriptor,
            None => {
                write_error(
                    error,
                    "rust_cpu geometric-admission context descriptor is null",
                );
                return STATUS_INVALID_ARGUMENT;
            }
        }
    };
    let result = catch_unwind(AssertUnwindSafe(|| unsafe {
        build_geometric_admission_state(descriptor)
    }));
    match result {
        Ok(Ok(state)) => {
            *state_output = Box::into_raw(Box::new(state)).cast::<c_void>();
            STATUS_OK
        }
        Ok(Err(provider_error)) => {
            write_error(error, provider_error.message);
            provider_error.status
        }
        Err(_) => {
            write_error(
                error,
                "rust_cpu geometric-admission context creation panicked",
            );
            STATUS_INTERNAL_ERROR
        }
    }
}

/// Destroy a Rust geometric-admission context.
///
/// # Safety
/// A non-null pointer must be the unique state returned by the matching create
/// function and must not be used after this call.
#[no_mangle]
pub unsafe extern "C" fn bg_rust_cpu_docking_geometric_admission_v1_destroy(state: *mut c_void) {
    if !state.is_null() {
        // SAFETY: The private dispatcher passes the unique Box pointer once.
        drop(unsafe { Box::from_raw(state.cast::<GeometricAdmissionState>()) });
    }
}

/// Evaluate all 64 fixed slots through the Rust geometric-admission kernel.
///
/// # Safety
/// `state` must be live, candidate channels must be readable for their fixed
/// denominators, and `out_rows` must address 64 writable aligned rows.
#[no_mangle]
pub unsafe extern "C" fn bg_rust_cpu_docking_geometric_admission_v1_evaluate_fixed64(
    state: *const c_void,
    candidates: *const DockingGeometricAdmissionCandidateBatchSoaV1,
    out_rows: *mut DockingGeometricAdmissionRowV1,
    out_error: *mut ErrorV1,
) -> i32 {
    let error = unsafe {
        match out_error.as_mut() {
            Some(error) => error,
            None => return STATUS_INVALID_ARGUMENT,
        }
    };
    if validate_header::<ErrorV1>(
        error.struct_size,
        error.abi_version,
        "rust_cpu error output size mismatch",
    )
    .is_err()
        || !reserved_is_zero(&error.reserved)
    {
        return STATUS_ABI_MISMATCH;
    }
    clear_error(error);
    if state.is_null() || candidates.is_null() || out_rows.is_null() {
        write_error(error, "rust_cpu geometric-admission batch pointer is null");
        return STATUS_INVALID_ARGUMENT;
    }
    if (out_rows as usize) % align_of::<DockingGeometricAdmissionRowV1>() != 0 {
        write_error(
            error,
            "rust_cpu geometric-admission row output is misaligned",
        );
        return STATUS_INVALID_ARGUMENT;
    }
    let state = unsafe { &*state.cast::<GeometricAdmissionState>() };
    let candidates = unsafe { &*candidates };
    let result = catch_unwind(AssertUnwindSafe(|| unsafe {
        evaluate_geometric_admission_fixed64(state, candidates)
    }));
    match result {
        Ok(Ok(rows)) => {
            // SAFETY: The dispatcher supplies a disjoint private fixed64 array.
            unsafe {
                ptr::copy_nonoverlapping(rows.as_ptr(), out_rows, FIXED64_CANDIDATE_COUNT);
            }
            STATUS_OK
        }
        Ok(Err(provider_error)) => {
            write_error(error, provider_error.message);
            provider_error.status
        }
        Err(_) => {
            write_error(error, "rust_cpu geometric-admission batch panicked");
            STATUS_INTERNAL_ERROR
        }
    }
}

/// Construct the persistent Rust ScorerV1 context used by the public native
/// docking ABI.
///
/// # Safety
/// The descriptor and every declared channel must remain readable for the
/// duration of the call. `out_state` and `out_error` must be writable,
/// correctly aligned, and disjoint from all inputs.
#[no_mangle]
pub unsafe extern "C" fn bg_rust_cpu_docking_scorer_v1_create(
    descriptor: *const DockingScorerContextSoaV1,
    out_state: *mut *mut c_void,
    out_error: *mut ErrorV1,
) -> i32 {
    let error = unsafe {
        match out_error.as_mut() {
            Some(error) => error,
            None => return STATUS_INVALID_ARGUMENT,
        }
    };
    if validate_header::<ErrorV1>(
        error.struct_size,
        error.abi_version,
        "rust_cpu error output size mismatch",
    )
    .is_err()
        || !reserved_is_zero(&error.reserved)
    {
        return STATUS_ABI_MISMATCH;
    }
    clear_error(error);
    let state_output = unsafe {
        match out_state.as_mut() {
            Some(output) => output,
            None => {
                write_error(error, "rust_cpu ScorerV1 state output is null");
                return STATUS_INVALID_ARGUMENT;
            }
        }
    };
    *state_output = ptr::null_mut();
    let descriptor = unsafe {
        match descriptor.as_ref() {
            Some(descriptor) => descriptor,
            None => {
                write_error(error, "rust_cpu ScorerV1 context descriptor is null");
                return STATUS_INVALID_ARGUMENT;
            }
        }
    };
    let result = catch_unwind(AssertUnwindSafe(|| unsafe {
        build_docking_context(descriptor)
    }));
    match result {
        Ok(Ok(context)) => {
            *state_output = Box::into_raw(Box::new(context)).cast::<c_void>();
            STATUS_OK
        }
        Ok(Err(provider_error)) => {
            write_error(error, provider_error.message);
            provider_error.status
        }
        Err(_) => {
            write_error(error, "rust_cpu ScorerV1 context creation panicked");
            STATUS_INTERNAL_ERROR
        }
    }
}

/// Destroy a ScorerV1 context returned by
/// `bg_rust_cpu_docking_scorer_v1_create`.
///
/// # Safety
/// A non-null pointer must be the unique live state returned by the matching
/// create function and must not be used after this call.
#[no_mangle]
pub unsafe extern "C" fn bg_rust_cpu_docking_scorer_v1_destroy(state: *mut c_void) {
    if !state.is_null() {
        // SAFETY: The private C++ dispatcher passes the unique pointer returned
        // by Box::into_raw above exactly once.
        drop(unsafe { Box::from_raw(state.cast::<NativeScorerV1Context>()) });
    }
}

/// Score all 64 slots through the persistent Rust ScorerV1 context.
///
/// # Safety
/// `state` must be a live state created by the matching create function. The
/// candidate descriptor and channels must remain readable throughout the
/// call. `out_rows` must address 64 writable, aligned, non-overlapping rows,
/// and `out_error` must be a writable private-provider error descriptor.
#[no_mangle]
pub unsafe extern "C" fn bg_rust_cpu_docking_scorer_v1_score_fixed64(
    state: *const c_void,
    candidates: *const DockingScorerCandidateBatchSoaV1,
    out_rows: *mut DockingScorerRowV1,
    out_error: *mut ErrorV1,
) -> i32 {
    let error = unsafe {
        match out_error.as_mut() {
            Some(error) => error,
            None => return STATUS_INVALID_ARGUMENT,
        }
    };
    if validate_header::<ErrorV1>(
        error.struct_size,
        error.abi_version,
        "rust_cpu error output size mismatch",
    )
    .is_err()
        || !reserved_is_zero(&error.reserved)
    {
        return STATUS_ABI_MISMATCH;
    }
    clear_error(error);
    if state.is_null() || candidates.is_null() || out_rows.is_null() {
        write_error(error, "rust_cpu ScorerV1 score pointer is null");
        return STATUS_INVALID_ARGUMENT;
    }
    if (out_rows as usize) % align_of::<DockingScorerRowV1>() != 0 {
        write_error(error, "rust_cpu ScorerV1 row output is misaligned");
        return STATUS_INVALID_ARGUMENT;
    }
    let context = unsafe { &*state.cast::<NativeScorerV1Context>() };
    let candidates = unsafe { &*candidates };
    let result = catch_unwind(AssertUnwindSafe(|| unsafe {
        score_docking_fixed64(context, candidates)
    }));
    match result {
        Ok(Ok(rows)) => {
            // SAFETY: The private dispatcher supplies a disjoint temporary
            // fixed64 row array and no write occurs before complete success.
            unsafe {
                ptr::copy_nonoverlapping(rows.as_ptr(), out_rows, FIXED64_CANDIDATE_COUNT);
            }
            STATUS_OK
        }
        Ok(Err(provider_error)) => {
            write_error(error, provider_error.message);
            provider_error.status
        }
        Err(_) => {
            write_error(error, "rust_cpu ScorerV1 batch panicked");
            STATUS_INTERNAL_ERROR
        }
    }
}

/// Construct the persistent Rust pose-validity context used by the public
/// native docking ABI.
///
/// # Safety
/// The descriptor and every declared channel must remain readable for the
/// duration of the call. `out_state` and `out_error` must be writable,
/// correctly aligned, and disjoint from all inputs.
#[no_mangle]
pub unsafe extern "C" fn bg_rust_cpu_docking_pose_validity_v1_create(
    descriptor: *const DockingPoseValidityContextSoaV1,
    out_state: *mut *mut c_void,
    out_error: *mut ErrorV1,
) -> i32 {
    let error = unsafe {
        match out_error.as_mut() {
            Some(error) => error,
            None => return STATUS_INVALID_ARGUMENT,
        }
    };
    if validate_header::<ErrorV1>(
        error.struct_size,
        error.abi_version,
        "rust_cpu error output size mismatch",
    )
    .is_err()
        || !reserved_is_zero(&error.reserved)
    {
        return STATUS_ABI_MISMATCH;
    }
    clear_error(error);
    let state_output = unsafe {
        match out_state.as_mut() {
            Some(output) => output,
            None => {
                write_error(error, "rust_cpu pose-validity state output is null");
                return STATUS_INVALID_ARGUMENT;
            }
        }
    };
    *state_output = ptr::null_mut();
    let descriptor = unsafe {
        match descriptor.as_ref() {
            Some(descriptor) => descriptor,
            None => {
                write_error(error, "rust_cpu pose-validity context descriptor is null");
                return STATUS_INVALID_ARGUMENT;
            }
        }
    };
    let result = catch_unwind(AssertUnwindSafe(|| unsafe {
        build_pose_validity_context(descriptor)
    }));
    match result {
        Ok(Ok(context)) => {
            *state_output = Box::into_raw(Box::new(context)).cast::<c_void>();
            STATUS_OK
        }
        Ok(Err(provider_error)) => {
            write_error(error, provider_error.message);
            provider_error.status
        }
        Err(_) => {
            write_error(error, "rust_cpu pose-validity context creation panicked");
            STATUS_INTERNAL_ERROR
        }
    }
}

/// Destroy a pose-validity context returned by
/// `bg_rust_cpu_docking_pose_validity_v1_create`.
///
/// # Safety
/// A non-null pointer must be the unique live state returned by the matching
/// create function and must not be used after this call.
#[no_mangle]
pub unsafe extern "C" fn bg_rust_cpu_docking_pose_validity_v1_destroy(state: *mut c_void) {
    if !state.is_null() {
        // SAFETY: The private C++ dispatcher passes the unique pointer returned
        // by Box::into_raw above exactly once.
        drop(unsafe { Box::from_raw(state.cast::<NativeFixed64ValidityContext>()) });
    }
}

/// Evaluate all 64 slots through the persistent Rust pose-validity context.
///
/// # Safety
/// `state` must be a live state created by the matching create function. The
/// candidate descriptor and channels must remain readable throughout the
/// call. `out_rows` must address 64 writable, aligned, non-overlapping rows,
/// and `out_error` must be a writable private-provider error descriptor.
#[no_mangle]
pub unsafe extern "C" fn bg_rust_cpu_docking_pose_validity_v1_evaluate_fixed64(
    state: *const c_void,
    candidates: *const DockingPoseValidityCandidateBatchSoaV1,
    out_rows: *mut DockingPoseValidityRowV1,
    out_error: *mut ErrorV1,
) -> i32 {
    let error = unsafe {
        match out_error.as_mut() {
            Some(error) => error,
            None => return STATUS_INVALID_ARGUMENT,
        }
    };
    if validate_header::<ErrorV1>(
        error.struct_size,
        error.abi_version,
        "rust_cpu error output size mismatch",
    )
    .is_err()
        || !reserved_is_zero(&error.reserved)
    {
        return STATUS_ABI_MISMATCH;
    }
    clear_error(error);
    if state.is_null() || candidates.is_null() || out_rows.is_null() {
        write_error(error, "rust_cpu pose-validity evaluation pointer is null");
        return STATUS_INVALID_ARGUMENT;
    }
    if (out_rows as usize) % align_of::<DockingPoseValidityRowV1>() != 0 {
        write_error(error, "rust_cpu pose-validity row output is misaligned");
        return STATUS_INVALID_ARGUMENT;
    }
    let context = unsafe { &*state.cast::<NativeFixed64ValidityContext>() };
    let candidates = unsafe { &*candidates };
    let result = catch_unwind(AssertUnwindSafe(|| unsafe {
        evaluate_pose_validity_fixed64(context, candidates)
    }));
    match result {
        Ok(Ok(rows)) => {
            // SAFETY: The private dispatcher supplies a disjoint temporary
            // fixed64 row array and no write occurs before complete success.
            unsafe {
                ptr::copy_nonoverlapping(rows.as_ptr(), out_rows, FIXED64_CANDIDATE_COUNT);
            }
            STATUS_OK
        }
        Ok(Err(provider_error)) => {
            write_error(error, provider_error.message);
            provider_error.status
        }
        Err(_) => {
            write_error(error, "rust_cpu pose-validity batch panicked");
            STATUS_INTERNAL_ERROR
        }
    }
}

/// Construct the stateless Rust stable Top-K provider marker.
///
/// # Safety
/// `out_state` and `out_error` must be writable, correctly aligned, and
/// disjoint.
#[no_mangle]
pub unsafe extern "C" fn bg_rust_cpu_docking_stable_top_k_v1_create(
    out_state: *mut *mut c_void,
    out_error: *mut ErrorV1,
) -> i32 {
    let error = unsafe {
        match out_error.as_mut() {
            Some(error) => error,
            None => return STATUS_INVALID_ARGUMENT,
        }
    };
    if validate_header::<ErrorV1>(
        error.struct_size,
        error.abi_version,
        "rust_cpu error output size mismatch",
    )
    .is_err()
        || !reserved_is_zero(&error.reserved)
    {
        return STATUS_ABI_MISMATCH;
    }
    clear_error(error);
    let state_output = unsafe {
        match out_state.as_mut() {
            Some(output) => output,
            None => {
                write_error(error, "rust_cpu stable Top-K state output is null");
                return STATUS_INVALID_ARGUMENT;
            }
        }
    };
    *state_output = Box::into_raw(Box::new(StableTopKState)).cast::<c_void>();
    STATUS_OK
}

/// Destroy a stable Top-K provider marker.
///
/// # Safety
/// A non-null pointer must be the unique live marker returned by the matching
/// create function and must not be reused.
#[no_mangle]
pub unsafe extern "C" fn bg_rust_cpu_docking_stable_top_k_v1_destroy(state: *mut c_void) {
    if !state.is_null() {
        drop(unsafe { Box::from_raw(state.cast::<StableTopKState>()) });
    }
}

/// Derive primary and valid-only fixed64 stable rankings.
///
/// # Safety
/// The input and all three fixed64 output arrays must remain readable or
/// writable for the call, be correctly aligned, and not overlap. Count and
/// error outputs must also be writable and disjoint.
#[no_mangle]
pub unsafe extern "C" fn bg_rust_cpu_docking_stable_top_k_v1_rank_fixed64(
    state: *const c_void,
    input: *const DockingStableTopKInputV1,
    out_rows: *mut DockingStableTopKRowV1,
    out_primary_slot_indices: *mut u32,
    out_primary_count: *mut u64,
    out_valid_slot_indices: *mut u32,
    out_valid_count: *mut u64,
    out_error: *mut ErrorV1,
) -> i32 {
    let error = unsafe {
        match out_error.as_mut() {
            Some(error) => error,
            None => return STATUS_INVALID_ARGUMENT,
        }
    };
    if validate_header::<ErrorV1>(
        error.struct_size,
        error.abi_version,
        "rust_cpu error output size mismatch",
    )
    .is_err()
        || !reserved_is_zero(&error.reserved)
    {
        return STATUS_ABI_MISMATCH;
    }
    clear_error(error);
    if state.is_null()
        || input.is_null()
        || out_rows.is_null()
        || out_primary_slot_indices.is_null()
        || out_primary_count.is_null()
        || out_valid_slot_indices.is_null()
        || out_valid_count.is_null()
        || (out_rows as usize) % align_of::<DockingStableTopKRowV1>() != 0
        || (out_primary_slot_indices as usize) % align_of::<u32>() != 0
        || (out_primary_count as usize) % align_of::<u64>() != 0
        || (out_valid_slot_indices as usize) % align_of::<u32>() != 0
        || (out_valid_count as usize) % align_of::<u64>() != 0
    {
        write_error(error, "rust_cpu stable Top-K pointer is null or misaligned");
        return STATUS_INVALID_ARGUMENT;
    }
    let input = unsafe { &*input };
    let result = catch_unwind(AssertUnwindSafe(|| unsafe {
        rank_stable_top_k_fixed64(input)
    }));
    match result {
        Ok(Ok(output)) => {
            unsafe {
                ptr::copy_nonoverlapping(output.rows.as_ptr(), out_rows, FIXED64_CANDIDATE_COUNT);
                ptr::copy_nonoverlapping(
                    output.primary_slot_indices.as_ptr(),
                    out_primary_slot_indices,
                    FIXED64_CANDIDATE_COUNT,
                );
                ptr::copy_nonoverlapping(
                    output.valid_slot_indices.as_ptr(),
                    out_valid_slot_indices,
                    FIXED64_CANDIDATE_COUNT,
                );
                ptr::write(out_primary_count, output.primary_count);
                ptr::write(out_valid_count, output.valid_count);
            }
            STATUS_OK
        }
        Ok(Err(provider_error)) => {
            write_error(error, provider_error.message);
            provider_error.status
        }
        Err(_) => {
            write_error(error, "rust_cpu stable Top-K batch panicked");
            STATUS_INTERNAL_ERROR
        }
    }
}

/// Cluster the stable valid-only fixed64 ranking with direct binary64 RMSD.
///
/// # Safety
/// The input graph and all output arrays/counts must be readable or writable,
/// correctly aligned, and pairwise disjoint for the duration of this call.
#[no_mangle]
pub unsafe extern "C" fn bg_rust_cpu_docking_stable_top_k_v1_cluster_direct_rmsd_fixed64(
    state: *const c_void,
    input: *const DockingRmsdClusterInputV1,
    out_rows: *mut DockingRmsdClusterRowV1,
    out_representative_slot_indices: *mut u32,
    out_cluster_count: *mut u64,
    out_top_k_slot_indices: *mut u32,
    out_top_k_count: *mut u64,
    out_error: *mut ErrorV1,
) -> i32 {
    let error = unsafe {
        match out_error.as_mut() {
            Some(error) => error,
            None => return STATUS_INVALID_ARGUMENT,
        }
    };
    if validate_header::<ErrorV1>(
        error.struct_size,
        error.abi_version,
        "rust_cpu error output size mismatch",
    )
    .is_err()
        || !reserved_is_zero(&error.reserved)
    {
        return STATUS_ABI_MISMATCH;
    }
    clear_error(error);
    if state.is_null()
        || input.is_null()
        || out_rows.is_null()
        || out_representative_slot_indices.is_null()
        || out_cluster_count.is_null()
        || out_top_k_slot_indices.is_null()
        || out_top_k_count.is_null()
        || (out_rows as usize) % align_of::<DockingRmsdClusterRowV1>() != 0
        || (out_representative_slot_indices as usize) % align_of::<u32>() != 0
        || (out_cluster_count as usize) % align_of::<u64>() != 0
        || (out_top_k_slot_indices as usize) % align_of::<u32>() != 0
        || (out_top_k_count as usize) % align_of::<u64>() != 0
    {
        write_error(error, "rust_cpu RMSD cluster pointer is null or misaligned");
        return STATUS_INVALID_ARGUMENT;
    }
    let input = unsafe { &*input };
    let result = catch_unwind(AssertUnwindSafe(|| unsafe {
        cluster_direct_rmsd_fixed64(input)
    }));
    match result {
        Ok(Ok(output)) => {
            unsafe {
                ptr::copy_nonoverlapping(output.rows.as_ptr(), out_rows, FIXED64_CANDIDATE_COUNT);
                ptr::copy_nonoverlapping(
                    output.representative_slot_indices.as_ptr(),
                    out_representative_slot_indices,
                    FIXED64_CANDIDATE_COUNT,
                );
                ptr::copy_nonoverlapping(
                    output.top_k_slot_indices.as_ptr(),
                    out_top_k_slot_indices,
                    NATIVE_FIXED64_TOP_K_LIMIT,
                );
                ptr::write(out_cluster_count, output.cluster_count);
                ptr::write(out_top_k_count, output.top_k_count);
            }
            STATUS_OK
        }
        Ok(Err(provider_error)) => {
            write_error(error, provider_error.message);
            provider_error.status
        }
        Err(_) => {
            write_error(error, "rust_cpu RMSD cluster batch panicked");
            STATUS_INTERNAL_ERROR
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn one_atom_system(
        position_x: &[f64; 1],
        position_y: &[f64; 1],
        position_z: &[f64; 1],
        charge: &[f64; 1],
    ) -> SystemV1 {
        SystemV1 {
            struct_size: u32::try_from(size_of::<SystemV1>()).unwrap(),
            abi_version: PROVIDER_ABI_VERSION,
            atom_count: 1,
            position_x: position_x.as_ptr(),
            position_y: position_y.as_ptr(),
            position_z: position_z.as_ptr(),
            charge: charge.as_ptr(),
            reserved: [0; 4],
        }
    }

    fn one_atom_forcefield(sigma: &[f64; 1], epsilon: &[f64; 1]) -> ForceFieldV1 {
        ForceFieldV1 {
            struct_size: u32::try_from(size_of::<ForceFieldV1>()).unwrap(),
            abi_version: PROVIDER_ABI_VERSION,
            atom_count: 1,
            sigma: sigma.as_ptr(),
            epsilon: epsilon.as_ptr(),
            bonds: BondSoaV1 {
                count: 0,
                atom_i: ptr::null(),
                atom_j: ptr::null(),
                equilibrium: ptr::null(),
                force_constant: ptr::null(),
            },
            angles: AngleSoaV1 {
                count: 0,
                atom_i: ptr::null(),
                atom_j: ptr::null(),
                atom_k: ptr::null(),
                equilibrium: ptr::null(),
                force_constant: ptr::null(),
            },
            torsions: TorsionSoaV1 {
                count: 0,
                atom_i: ptr::null(),
                atom_j: ptr::null(),
                atom_k: ptr::null(),
                atom_l: ptr::null(),
                periodicity: ptr::null(),
                phase: ptr::null(),
                amplitude: ptr::null(),
            },
            exclusion_count: 0,
            exclusions: ptr::null(),
            pair_scale_count: 0,
            pair_scales: ptr::null(),
            periodic_axes_mask: 0,
            reserved0: 0,
            cell_lengths: [0.0; 3],
            cutoff: 8.0,
            switch_start: 6.0,
            dielectric: 1.0,
            screening_kappa: 0.0,
            minimum_pair_distance: 0.25,
            reserved: [0; 4],
        }
    }

    fn energy_with_sentinel(sentinel: f64) -> EnergyV1 {
        EnergyV1 {
            struct_size: u32::try_from(size_of::<EnergyV1>()).unwrap(),
            abi_version: PROVIDER_ABI_VERSION,
            harmonic_bond: sentinel,
            harmonic_angle: sentinel,
            periodic_torsion: sentinel,
            lennard_jones: sentinel,
            coulomb: sentinel,
            total: sentinel,
            reserved: [0; 4],
        }
    }

    fn error_output() -> ErrorV1 {
        ErrorV1 {
            struct_size: u32::try_from(size_of::<ErrorV1>()).unwrap(),
            abi_version: PROVIDER_ABI_VERSION,
            message: [0; ERROR_CAPACITY],
            reserved: [0; 4],
        }
    }

    fn error_message(error: &ErrorV1) -> &str {
        let length = error
            .message
            .iter()
            .position(|value| *value == 0)
            .unwrap_or(error.message.len());
        core::str::from_utf8(&error.message[..length]).unwrap()
    }

    #[test]
    fn provider_layouts_are_versioned_and_stable_on_the_host() {
        assert_eq!(size_of::<Pair>(), 2 * size_of::<usize>());
        assert_eq!(size_of::<PairScale>(), 2 * size_of::<usize>() + 16);
        assert_eq!(bg_rust_cpu_provider_abi_version_v1(), 1);
        assert_eq!(size_of::<ErrorV1>(), 296);
        assert_eq!(size_of::<DockingScorerContextSoaV1>(), 608);
        assert_eq!(size_of::<DockingScorerCandidateBatchSoaV1>(), 96);
        assert_eq!(size_of::<DockingScorerRowV1>(), 160);
        assert_eq!(size_of::<DockingPoseValidityContextSoaV1>(), 560);
        assert_eq!(size_of::<DockingPoseValidityCandidateBatchSoaV1>(), 136);
        assert_eq!(size_of::<DockingPoseValidityRowV1>(), 240);
        assert_eq!(size_of::<DockingStableTopKInputV1>(), 80);
        assert_eq!(size_of::<DockingStableTopKRowV1>(), 88);
        assert_eq!(size_of::<DockingRmsdClusterInputV1>(), 120);
        assert_eq!(size_of::<DockingRmsdClusterRowV1>(), 112);
    }

    #[test]
    fn provider_evaluates_a_valid_request_and_clears_outputs() {
        let position_x = [1.0];
        let position_y = [2.0];
        let position_z = [3.0];
        let charge = [0.0];
        let sigma = [1.5];
        let epsilon = [0.2];
        let system = one_atom_system(&position_x, &position_y, &position_z, &charge);
        let forcefield = one_atom_forcefield(&sigma, &epsilon);
        let mut energy = energy_with_sentinel(17.0);
        let mut force_x = [19.0];
        let mut force_y = [23.0];
        let mut force_z = [29.0];
        let mut forces = ForceOutputV1 {
            struct_size: u32::try_from(size_of::<ForceOutputV1>()).unwrap(),
            abi_version: PROVIDER_ABI_VERSION,
            capacity: 1,
            x: force_x.as_mut_ptr(),
            y: force_y.as_mut_ptr(),
            z: force_z.as_mut_ptr(),
            reserved: [0; 4],
        };
        let mut error = error_output();
        error.message[0] = b'x';

        // SAFETY: All descriptors point to live, correctly sized, disjoint storage.
        let status = unsafe {
            bg_rust_cpu_evaluate_v1(
                &system,
                &forcefield,
                1,
                &mut energy,
                &mut forces,
                &mut error,
            )
        };

        assert_eq!(status, STATUS_OK);
        assert_eq!(energy.harmonic_bond, 0.0);
        assert_eq!(energy.harmonic_angle, 0.0);
        assert_eq!(energy.periodic_torsion, 0.0);
        assert_eq!(energy.lennard_jones, 0.0);
        assert_eq!(energy.coulomb, 0.0);
        assert_eq!(energy.total, 0.0);
        assert_eq!(force_x, [0.0]);
        assert_eq!(force_y, [0.0]);
        assert_eq!(force_z, [0.0]);
        assert_eq!(error_message(&error), "");

        energy = energy_with_sentinel(31.0);
        force_x = [37.0];
        force_y = [41.0];
        force_z = [43.0];
        let mut forcefield_validated = 0_u8;
        // SAFETY: The reusable output channels and derived validation state
        // are live, correctly sized, aligned, and disjoint.
        let direct_status = unsafe {
            bg_rust_cpu_evaluate_reusing_force_output_v1(
                &system,
                &forcefield,
                &mut forcefield_validated,
                &mut energy,
                &mut forces,
                &mut error,
            )
        };
        assert_eq!(direct_status, STATUS_OK);
        assert_eq!(forcefield_validated, 1);
        assert_eq!(energy.total, 0.0);
        assert_eq!(force_x, [0.0]);
        assert_eq!(force_y, [0.0]);
        assert_eq!(force_z, [0.0]);
        assert_eq!(error_message(&error), "");
    }

    #[test]
    fn provider_supplied_neighbor_pairs_match_automatic_and_fail_transactionally() {
        let position_x = [0.2, 9.8];
        let position_y = [0.0; 2];
        let position_z = [0.0; 2];
        let charge = [0.3, -0.4];
        let mut sigma = [1.0; 2];
        let epsilon = [0.05; 2];
        let system = SystemV1 {
            struct_size: u32::try_from(size_of::<SystemV1>()).unwrap(),
            abi_version: PROVIDER_ABI_VERSION,
            atom_count: 2,
            position_x: position_x.as_ptr(),
            position_y: position_y.as_ptr(),
            position_z: position_z.as_ptr(),
            charge: charge.as_ptr(),
            reserved: [0; 4],
        };
        let forcefield = ForceFieldV1 {
            struct_size: u32::try_from(size_of::<ForceFieldV1>()).unwrap(),
            abi_version: PROVIDER_ABI_VERSION,
            atom_count: 2,
            sigma: sigma.as_ptr(),
            epsilon: epsilon.as_ptr(),
            bonds: BondSoaV1 {
                count: 0,
                atom_i: ptr::null(),
                atom_j: ptr::null(),
                equilibrium: ptr::null(),
                force_constant: ptr::null(),
            },
            angles: AngleSoaV1 {
                count: 0,
                atom_i: ptr::null(),
                atom_j: ptr::null(),
                atom_k: ptr::null(),
                equilibrium: ptr::null(),
                force_constant: ptr::null(),
            },
            torsions: TorsionSoaV1 {
                count: 0,
                atom_i: ptr::null(),
                atom_j: ptr::null(),
                atom_k: ptr::null(),
                atom_l: ptr::null(),
                periodicity: ptr::null(),
                phase: ptr::null(),
                amplitude: ptr::null(),
            },
            exclusion_count: 0,
            exclusions: ptr::null(),
            pair_scale_count: 0,
            pair_scales: ptr::null(),
            periodic_axes_mask: 7,
            reserved0: 0,
            cell_lengths: [10.0; 3],
            cutoff: 3.0,
            switch_start: 2.5,
            dielectric: 1.0,
            screening_kappa: 0.0,
            minimum_pair_distance: 1.0e-10,
            reserved: [0; 4],
        };
        let mut automatic_energy = energy_with_sentinel(17.0);
        let mut automatic_x = [19.0; 2];
        let mut automatic_y = [23.0; 2];
        let mut automatic_z = [29.0; 2];
        let mut automatic_forces = ForceOutputV1 {
            struct_size: u32::try_from(size_of::<ForceOutputV1>()).unwrap(),
            abi_version: PROVIDER_ABI_VERSION,
            capacity: 2,
            x: automatic_x.as_mut_ptr(),
            y: automatic_y.as_mut_ptr(),
            z: automatic_z.as_mut_ptr(),
            reserved: [0; 4],
        };
        let mut error = error_output();
        // SAFETY: All descriptors point to live, correctly sized, disjoint storage.
        assert_eq!(
            unsafe {
                bg_rust_cpu_evaluate_v1(
                    &system,
                    &forcefield,
                    1,
                    &mut automatic_energy,
                    &mut automatic_forces,
                    &mut error,
                )
            },
            STATUS_OK
        );

        let mut automatic_direct_energy = energy_with_sentinel(31.0);
        let mut automatic_direct_x = [37.0; 2];
        let mut automatic_direct_y = [41.0; 2];
        let mut automatic_direct_z = [43.0; 2];
        let mut automatic_direct_forces = ForceOutputV1 {
            struct_size: u32::try_from(size_of::<ForceOutputV1>()).unwrap(),
            abi_version: PROVIDER_ABI_VERSION,
            capacity: 2,
            x: automatic_direct_x.as_mut_ptr(),
            y: automatic_direct_y.as_mut_ptr(),
            z: automatic_direct_z.as_mut_ptr(),
            reserved: [0; 4],
        };
        let mut automatic_forcefield_validated = 0_u8;
        // SAFETY: The reusable output channels and derived validation state
        // are live, correctly sized, aligned, and disjoint.
        assert_eq!(
            unsafe {
                bg_rust_cpu_evaluate_reusing_force_output_v1(
                    &system,
                    &forcefield,
                    &mut automatic_forcefield_validated,
                    &mut automatic_direct_energy,
                    &mut automatic_direct_forces,
                    &mut error,
                )
            },
            STATUS_OK
        );
        assert_eq!(automatic_forcefield_validated, 1);
        for (left, right) in [
            (
                automatic_energy.harmonic_bond,
                automatic_direct_energy.harmonic_bond,
            ),
            (
                automatic_energy.harmonic_angle,
                automatic_direct_energy.harmonic_angle,
            ),
            (
                automatic_energy.periodic_torsion,
                automatic_direct_energy.periodic_torsion,
            ),
            (
                automatic_energy.lennard_jones,
                automatic_direct_energy.lennard_jones,
            ),
            (automatic_energy.coulomb, automatic_direct_energy.coulomb),
            (automatic_energy.total, automatic_direct_energy.total),
        ] {
            assert_eq!(left.to_bits(), right.to_bits());
        }
        assert_eq!(
            automatic_x.map(f64::to_bits),
            automatic_direct_x.map(f64::to_bits)
        );
        assert_eq!(
            automatic_y.map(f64::to_bits),
            automatic_direct_y.map(f64::to_bits)
        );
        assert_eq!(
            automatic_z.map(f64::to_bits),
            automatic_direct_z.map(f64::to_bits)
        );

        let pairs = [Pair {
            atom_i: 0,
            atom_j: 1,
        }];
        let mut supplied_energy = energy_with_sentinel(31.0);
        let mut supplied_x = [37.0; 2];
        let mut supplied_y = [41.0; 2];
        let mut supplied_z = [43.0; 2];
        let mut supplied_forces = ForceOutputV1 {
            struct_size: u32::try_from(size_of::<ForceOutputV1>()).unwrap(),
            abi_version: PROVIDER_ABI_VERSION,
            capacity: 2,
            x: supplied_x.as_mut_ptr(),
            y: supplied_y.as_mut_ptr(),
            z: supplied_z.as_mut_ptr(),
            reserved: [0; 4],
        };
        // SAFETY: The canonical pair and all descriptors point to live,
        // correctly sized, disjoint storage.
        assert_eq!(
            unsafe {
                bg_rust_cpu_evaluate_with_neighbor_pairs_v1(
                    &system,
                    &forcefield,
                    pairs.len(),
                    pairs.as_ptr(),
                    1,
                    &mut supplied_energy,
                    &mut supplied_forces,
                    &mut error,
                )
            },
            STATUS_OK
        );
        for (left, right) in [
            (
                automatic_energy.harmonic_bond,
                supplied_energy.harmonic_bond,
            ),
            (
                automatic_energy.harmonic_angle,
                supplied_energy.harmonic_angle,
            ),
            (
                automatic_energy.periodic_torsion,
                supplied_energy.periodic_torsion,
            ),
            (
                automatic_energy.lennard_jones,
                supplied_energy.lennard_jones,
            ),
            (automatic_energy.coulomb, supplied_energy.coulomb),
            (automatic_energy.total, supplied_energy.total),
        ] {
            assert_eq!(left.to_bits(), right.to_bits());
        }
        assert_eq!(automatic_x.map(f64::to_bits), supplied_x.map(f64::to_bits));
        assert_eq!(automatic_y.map(f64::to_bits), supplied_y.map(f64::to_bits));
        assert_eq!(automatic_z.map(f64::to_bits), supplied_z.map(f64::to_bits));

        let mut direct_energy = energy_with_sentinel(47.0);
        let mut direct_x = [53.0; 2];
        let mut direct_y = [59.0; 2];
        let mut direct_z = [61.0; 2];
        let mut direct_forces = ForceOutputV1 {
            struct_size: u32::try_from(size_of::<ForceOutputV1>()).unwrap(),
            abi_version: PROVIDER_ABI_VERSION,
            capacity: 2,
            x: direct_x.as_mut_ptr(),
            y: direct_y.as_mut_ptr(),
            z: direct_z.as_mut_ptr(),
            reserved: [0; 4],
        };
        let mut forcefield_validated = 0_u8;
        sigma[0] = f64::NAN;
        // SAFETY: All pointer ranges are valid. The first use of a zero state
        // must fully validate the immutable force field before output mutation.
        assert_eq!(
            unsafe {
                bg_rust_cpu_evaluate_with_neighbor_pairs_reusing_force_output_v1(
                    &system,
                    &forcefield,
                    pairs.len(),
                    pairs.as_ptr(),
                    &mut forcefield_validated,
                    &mut direct_energy,
                    &mut direct_forces,
                    &mut error,
                )
            },
            STATUS_INVALID_ARGUMENT
        );
        assert_eq!(forcefield_validated, 0);
        assert_eq!(direct_energy.total, 47.0);
        assert_eq!(direct_x, [53.0; 2]);
        assert_eq!(direct_y, [59.0; 2]);
        assert_eq!(direct_z, [61.0; 2]);
        sigma[0] = 1.0;
        assert_eq!(sigma[0], 1.0);
        // SAFETY: The reusable output channels and canonical pair are live,
        // correctly sized, and disjoint.
        assert_eq!(
            unsafe {
                bg_rust_cpu_evaluate_with_neighbor_pairs_reusing_force_output_v1(
                    &system,
                    &forcefield,
                    pairs.len(),
                    pairs.as_ptr(),
                    &mut forcefield_validated,
                    &mut direct_energy,
                    &mut direct_forces,
                    &mut error,
                )
            },
            STATUS_OK
        );
        assert_eq!(forcefield_validated, 1);
        for (left, right) in [
            (supplied_energy.harmonic_bond, direct_energy.harmonic_bond),
            (supplied_energy.harmonic_angle, direct_energy.harmonic_angle),
            (
                supplied_energy.periodic_torsion,
                direct_energy.periodic_torsion,
            ),
            (supplied_energy.lennard_jones, direct_energy.lennard_jones),
            (supplied_energy.coulomb, direct_energy.coulomb),
            (supplied_energy.total, direct_energy.total),
        ] {
            assert_eq!(left.to_bits(), right.to_bits());
        }
        assert_eq!(supplied_x.map(f64::to_bits), direct_x.map(f64::to_bits));
        assert_eq!(supplied_y.map(f64::to_bits), direct_y.map(f64::to_bits));
        assert_eq!(supplied_z.map(f64::to_bits), direct_z.map(f64::to_bits));

        // SAFETY: The canonical pair was produced by the same trusted owner
        // contract used by native dynamics, and all outputs remain live and
        // disjoint. This exercises the prevalidated provider symbol directly.
        assert_eq!(
            unsafe {
                bg_rust_cpu_evaluate_with_prevalidated_neighbor_pairs_reusing_force_output_v1(
                    &system,
                    &forcefield,
                    pairs.len(),
                    pairs.as_ptr(),
                    &mut forcefield_validated,
                    &mut direct_energy,
                    &mut direct_forces,
                    &mut error,
                )
            },
            STATUS_OK
        );
        assert_eq!(forcefield_validated, 1);
        assert_eq!(
            supplied_energy.total.to_bits(),
            direct_energy.total.to_bits()
        );
        assert_eq!(supplied_x.map(f64::to_bits), direct_x.map(f64::to_bits));
        assert_eq!(supplied_y.map(f64::to_bits), direct_y.map(f64::to_bits));
        assert_eq!(supplied_z.map(f64::to_bits), direct_z.map(f64::to_bits));

        let duplicate = [pairs[0], pairs[0]];
        let energy_before = supplied_energy.total.to_bits();
        let x_before = supplied_x.map(f64::to_bits);
        // SAFETY: The duplicate rows are readable and the provider must reject
        // their semantics before committing any output.
        assert_eq!(
            unsafe {
                bg_rust_cpu_evaluate_with_neighbor_pairs_v1(
                    &system,
                    &forcefield,
                    duplicate.len(),
                    duplicate.as_ptr(),
                    1,
                    &mut supplied_energy,
                    &mut supplied_forces,
                    &mut error,
                )
            },
            STATUS_INVALID_ARGUMENT
        );
        assert_eq!(
            error_message(&error),
            "neighbor pairs must be unique sorted in-range canonical pairs"
        );
        assert_eq!(supplied_energy.total.to_bits(), energy_before);
        assert_eq!(supplied_x.map(f64::to_bits), x_before);

        let direct_energy_before = direct_energy.total.to_bits();
        // SAFETY: The duplicate rows are readable. This dynamics-only route is
        // explicitly allowed to clear reusable force channels before failure.
        assert_eq!(
            unsafe {
                bg_rust_cpu_evaluate_with_neighbor_pairs_reusing_force_output_v1(
                    &system,
                    &forcefield,
                    duplicate.len(),
                    duplicate.as_ptr(),
                    &mut forcefield_validated,
                    &mut direct_energy,
                    &mut direct_forces,
                    &mut error,
                )
            },
            STATUS_INVALID_ARGUMENT
        );
        assert_eq!(direct_energy.total.to_bits(), direct_energy_before);
        assert_eq!(direct_x, [0.0; 2]);
        assert_eq!(direct_y, [0.0; 2]);
        assert_eq!(direct_z, [0.0; 2]);
        assert_eq!(forcefield_validated, 1);

        forcefield_validated = 2;
        // SAFETY: All pointer ranges remain valid; the deliberately malformed
        // derived validation state must be rejected before output mutation.
        assert_eq!(
            unsafe {
                bg_rust_cpu_evaluate_with_neighbor_pairs_reusing_force_output_v1(
                    &system,
                    &forcefield,
                    pairs.len(),
                    pairs.as_ptr(),
                    &mut forcefield_validated,
                    &mut direct_energy,
                    &mut direct_forces,
                    &mut error,
                )
            },
            STATUS_INVALID_ARGUMENT
        );
        assert_eq!(
            error_message(&error),
            "force-field validation state must be exactly zero or one"
        );
    }

    #[test]
    fn provider_failure_is_transactional_for_energy_and_forces() {
        let position_x = [f64::NAN];
        let position_y = [2.0];
        let position_z = [3.0];
        let charge = [0.0];
        let sigma = [1.5];
        let epsilon = [0.2];
        let system = one_atom_system(&position_x, &position_y, &position_z, &charge);
        let forcefield = one_atom_forcefield(&sigma, &epsilon);
        let mut energy = energy_with_sentinel(17.0);
        let mut force_x = [19.0];
        let mut force_y = [23.0];
        let mut force_z = [29.0];
        let mut forces = ForceOutputV1 {
            struct_size: u32::try_from(size_of::<ForceOutputV1>()).unwrap(),
            abi_version: PROVIDER_ABI_VERSION,
            capacity: 1,
            x: force_x.as_mut_ptr(),
            y: force_y.as_mut_ptr(),
            z: force_z.as_mut_ptr(),
            reserved: [0; 4],
        };
        let mut error = error_output();

        // SAFETY: The descriptors are structurally valid. The deliberately
        // non-finite coordinate is rejected before any scientific output write.
        let status = unsafe {
            bg_rust_cpu_evaluate_v1(
                &system,
                &forcefield,
                1,
                &mut energy,
                &mut forces,
                &mut error,
            )
        };

        assert_eq!(status, STATUS_INVALID_ARGUMENT);
        assert_eq!(energy.total, 17.0);
        assert_eq!(force_x, [19.0]);
        assert_eq!(force_y, [23.0]);
        assert_eq!(force_z, [29.0]);
        assert!(error_message(&error).contains("non-finite"));
    }

    #[test]
    fn provider_rejects_overlapping_force_channels_without_writing() {
        let position_x = [1.0];
        let position_y = [2.0];
        let position_z = [3.0];
        let charge = [0.0];
        let sigma = [1.5];
        let epsilon = [0.2];
        let system = one_atom_system(&position_x, &position_y, &position_z, &charge);
        let forcefield = one_atom_forcefield(&sigma, &epsilon);
        let mut energy = energy_with_sentinel(17.0);
        let mut shared_force = [19.0];
        let mut force_z = [29.0];
        let mut forces = ForceOutputV1 {
            struct_size: u32::try_from(size_of::<ForceOutputV1>()).unwrap(),
            abi_version: PROVIDER_ABI_VERSION,
            capacity: 1,
            x: shared_force.as_mut_ptr(),
            y: shared_force.as_mut_ptr(),
            z: force_z.as_mut_ptr(),
            reserved: [0; 4],
        };
        let mut error = error_output();

        // SAFETY: No Rust references are created for the deliberately aliased
        // raw channels because range validation rejects them first.
        let status = unsafe {
            bg_rust_cpu_evaluate_v1(
                &system,
                &forcefield,
                1,
                &mut energy,
                &mut forces,
                &mut error,
            )
        };

        assert_eq!(status, STATUS_INVALID_ARGUMENT);
        assert_eq!(energy.total, 17.0);
        assert_eq!(shared_force, [19.0]);
        assert_eq!(force_z, [29.0]);
        assert!(error_message(&error).contains("must not overlap"));
    }
}
