//! Independent scalar reference dynamics for Betelgeuze validation.
//!
//! This crate intentionally has no FFI, accelerator, production-runtime, or
//! external-solver dependency. A [`ForceProvider`] supplies potential energy
//! and force in canonical units, while every integration and projection step is
//! evaluated in a documented scalar `f64` order.

mod checkpoint;
mod constraints;
mod dynamics;
mod model;
mod rng;

pub use checkpoint::{decode_checkpoint, encode_checkpoint};
pub use constraints::{project_positions, project_velocities};
pub use dynamics::{
    integrate_baoab, integrate_velocity_verlet, kinetic_energy_kcal_per_mol, minimize,
    temperature_kelvin,
};
pub use model::{
    ConstraintConfig, DistanceConstraint, DynamicsError, DynamicsErrorCode, ForceProvider,
    IntegrationReport, LangevinConfig, MinimizationConfig, MinimizationReport, OrthorhombicCell,
    State, System, VerletConfig,
};
pub use rng::{normal_triplet, philox4x32_10};

/// Convert `(kcal/mol)/angstrom/dalton` to `angstrom/fs^2`.
pub const ACCELERATION_ANGSTROM_PER_FS2_PER_FORCE_PER_DALTON: f64 = 4.184e-4;

/// Molar gas constant in `kcal/(mol K)`.
pub const GAS_CONSTANT_KCAL_PER_MOL_KELVIN: f64 = 0.001_987_204_258_640_831_6;

/// Frozen semantic identifier for equations, iteration order, RNG, and bytes.
pub const ORACLE_SCHEMA_ID: &str = "betelgeuze.reference_dynamics/1.0.0";
