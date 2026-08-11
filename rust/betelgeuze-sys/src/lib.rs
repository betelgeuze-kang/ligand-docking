//! Raw bindings for the Betelgeuze native compute ABI.
//!
//! This crate intentionally mirrors `include/betelgeuze/engine.h` without
//! adding ownership or lifetime semantics. Prefer `betelgeuze-runtime` for a
//! safe API.
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
pub const BG_ABI_VERSION_MINOR: u32 = 5;
pub const BG_ABI_VERSION: u32 = 1;

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

pub type bg_integrator = i32;
pub const BG_INTEGRATOR_VELOCITY_VERLET: bg_integrator = 1;
pub const BG_INTEGRATOR_LANGEVIN_BAOAB: bg_integrator = 2;

pub const BG_DOCKING_FIXED64_CANDIDATE_COUNT: u32 = 64;
pub const BG_DOCKING_SCORER_V1_TERM_COUNT: u32 = 8;

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

/// Opaque native simulation. Its representation is intentionally unavailable.
#[repr(C)]
pub struct bg_simulation {
    _private: [u8; 0],
}

/// Opaque persistent Engine V2 ScorerV1 context.
#[repr(C)]
pub struct bg_docking_scorer_v1 {
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

unsafe extern "C" {
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
