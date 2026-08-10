//! Independent scalar reference equations for Betelgeuze force-field validation.
//!
//! This crate deliberately has no dependency on the native compute ABI, production
//! evaluators, accelerator code, or external molecular-dynamics engines. All public
//! fields name their canonical units: angstrom, radians, elementary charge, and
//! kcal/mol. Evaluation uses scalar `f64` operations in a frozen order.

mod geometry;
mod model;
mod oracle;

pub use model::{
    AtomNonbonded, EnergyComponents, HarmonicAngle, HarmonicBond, NonbondedSettings, OracleError,
    OracleErrorCode, OracleInput, OrthorhombicCell, PairExclusion, PairScale, PeriodicTorsion,
    Position,
};
pub use oracle::evaluate;

/// Coulomb conversion factor in kcal·angstrom/(mol·e²).
pub const COULOMB_KCAL_ANGSTROM_PER_MOL_E2: f64 = 332.063_713_299;

/// Frozen semantic version for the equations and evaluation order in this crate.
pub const ORACLE_SCHEMA_ID: &str = "betelgeuze.reference_physics/1.0.0";
