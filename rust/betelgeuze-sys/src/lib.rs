//! Raw bindings for the Betelgeuze native compute ABI.
//!
//! This crate intentionally mirrors `include/betelgeuze/engine.h` without
//! adding ownership or lifetime semantics. Prefer `betelgeuze-runtime` for a
//! safe API.

#![no_std]
#![allow(non_camel_case_types)]

use core::ffi::c_char;

pub const BG_ABI_VERSION_MAJOR: u32 = 1;
pub const BG_ABI_VERSION_MINOR: u32 = 0;
pub const BG_ABI_VERSION: u32 = 1;

pub const BG_CANONICAL_LENGTH_UNIT: &[u8] = b"angstrom\0";
pub const BG_CANONICAL_ENERGY_UNIT: &[u8] = b"kcal/mol\0";
pub const BG_CANONICAL_FORCE_UNIT: &[u8] = b"kcal/(mol*angstrom)\0";
pub const BG_CANONICAL_CHARGE_UNIT: &[u8] = b"elementary_charge\0";
pub const BG_CANONICAL_MASS_UNIT: &[u8] = b"dalton\0";
pub const BG_CANONICAL_ANGLE_UNIT: &[u8] = b"radian\0";
pub const BG_CANONICAL_TIME_UNIT: &[u8] = b"femtosecond\0";
pub const BG_CANONICAL_VELOCITY_UNIT: &[u8] = b"angstrom/femtosecond\0";

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

pub type bg_backend = i32;
pub const BG_BACKEND_AUTO: bg_backend = 0;
pub const BG_BACKEND_CPU: bg_backend = 1;
pub const BG_BACKEND_HIP: bg_backend = 2;

pub type bg_unit_system = i32;
pub const BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL: bg_unit_system = 1;

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

    pub fn bg_context_options_init(options: *mut bg_context_options) -> bg_status;
    pub fn bg_particle_soa_init(particles: *mut bg_particle_soa) -> bg_status;
    pub fn bg_particle_soa_view_init(view: *mut bg_particle_soa_view) -> bg_status;
    pub fn bg_position_soa_init(positions: *mut bg_position_soa) -> bg_status;

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
}
