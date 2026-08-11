//! Pure-Rust deterministic CPU provider for the private native engine ABI.
//!
//! The public C ABI owns validation, handles, and transaction boundaries. This
//! crate supplies an independently implemented scalar kernel and a versioned,
//! hidden provider boundary used by the C++ dispatcher.

mod kernel;

use core::mem::{align_of, size_of};
use core::ptr;
use std::ffi::c_void;
use std::panic::{catch_unwind, AssertUnwindSafe};

use betelgeuze_docking_search::{
    NativeScorerV1Atom, NativeScorerV1Backend, NativeScorerV1Config, NativeScorerV1Context,
    NativeScorerV1Donor, NativeScorerV1FailureCode, NativeScorerV1KernelOutcome, Vec3,
    FIXED64_CANDIDATE_COUNT,
};
use kernel::{AngleSoa, BondSoa, ForceField, Pair, PairScale, System, TorsionSoa};

const PROVIDER_ABI_VERSION: u32 = 1;
const STATUS_OK: i32 = 0;
const STATUS_INVALID_ARGUMENT: i32 = 1;
const STATUS_ABI_MISMATCH: i32 = 2;
const STATUS_CAPACITY_OVERFLOW: i32 = 6;
const STATUS_INTERNAL_ERROR: i32 = 9;
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

unsafe fn build_inputs<'a>(
    system: &'a SystemV1,
    forcefield: &'a ForceFieldV1,
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

    for values in [position_x, position_y, position_z, charge, sigma, epsilon] {
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
        let indices_are_distinct = (0..indices.len())
            .all(|left| ((left + 1)..indices.len()).all(|right| indices[left] != indices[right]));
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

unsafe fn evaluate_impl(
    system: *const SystemV1,
    forcefield: *const ForceFieldV1,
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
    let evaluation =
        kernel::evaluate(&system, &forcefield, compute_forces).map_err(|error| ProviderError {
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
        evaluate_impl(system, forcefield, compute_forces, out_energy, out_forces)
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
