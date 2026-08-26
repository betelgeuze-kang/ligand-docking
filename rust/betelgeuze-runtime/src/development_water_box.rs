//! Frozen two-water native CPU development slice.
//!
//! This module constructs one exact synthetic two-water system using the shared
//! native `System`, `ForceField`, and `Simulation` owners. It is development
//! evidence only: it carries no product, scientific, free-energy, performance,
//! benchmark, Stage 0, Fresh-128, or molecular-execution authority.

use crate::{
    invalid, AtomNonbonded, Backend, Context, DistanceConstraint, DistanceConstraints,
    DynamicsReport, Error, ErrorCode, Evaluation, ForceField, ForceFieldInput, HarmonicAngle,
    HarmonicBond, Integrator, OrthorhombicCell, PairExclusion, ParticleSnapshot, ParticleSoa,
    PositionSoa, Result, Simulation, SimulationOptions, System, VelocitySoa,
};
use betelgeuze_sys as sys;
use sha2::{Digest, Sha256};
use std::fmt;

pub const DEVELOPMENT_WATER_BOX_V1_SCHEMA_ID: &str = "betelgeuze.engine_v2_native_water_box/1.0.0";
pub const DEVELOPMENT_WATER_BOX_V1_PROFILE_ID: &str = "engine_v2_native_two_water_development_v1";
pub const DEVELOPMENT_WATER_BOX_CONSTRAINTS_V1_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_water_box_constraints_profile/1.0.0";
pub const DEVELOPMENT_WATER_BOX_CONSTRAINTS_V1_PROFILE_ID: &str =
    "engine_v2_native_two_water_constraints_development_v1";
pub const DEVELOPMENT_WATER_BOX_NVT_ENSEMBLE_V1_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_water_box_nvt_ensemble_profile/1.0.0";
pub const DEVELOPMENT_WATER_BOX_NVT_ENSEMBLE_V1_PROFILE_ID: &str =
    "engine_v2_native_two_water_nvt_ensemble_development_v1";
pub const DEVELOPMENT_WATER_BOX_NVT_CONSTRAINT_RESIDUAL_V1_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_water_box_nvt_constraint_residual_profile/1.0.0";
pub const DEVELOPMENT_WATER_BOX_NVT_CONSTRAINT_RESIDUAL_V1_PROFILE_ID: &str =
    "engine_v2_native_two_water_nvt_constraint_residual_development_v1";
pub const DEVELOPMENT_WATER_BOX_V1_ATOM_COUNT: usize = 6;
pub const DEVELOPMENT_WATER_ION_V1_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_water_ion_profile/1.0.0";
pub const DEVELOPMENT_WATER_ION_V1_PROFILE_ID: &str = "engine_v2_native_tip3p_nacl_development_v1";
pub const DEVELOPMENT_WATER_ION_DYNAMICS_V1_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_water_ion_dynamics_profile/1.0.0";
pub const DEVELOPMENT_WATER_ION_DYNAMICS_V1_PROFILE_ID: &str =
    "engine_v2_native_tip3p_nacl_constrained_dynamics_development_v1";
pub const DEVELOPMENT_WATER_BOX_DYNAMICS_FAILURE_V1_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_water_box_dynamics_failure_profile/1.0.0";
pub const DEVELOPMENT_WATER_BOX_DYNAMICS_FAILURE_V1_PROFILE_ID: &str =
    "engine_v2_native_water_box_dynamics_failure_matrix_development_v1";
pub const DEVELOPMENT_WATER_BOX_DYNAMICS_FAILURE_V2_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_water_box_dynamics_failure_profile/2.0.0";
pub const DEVELOPMENT_WATER_BOX_DYNAMICS_FAILURE_V2_PROFILE_ID: &str =
    "engine_v2_native_water_box_dynamics_failure_boundary_development_v2";
pub const DEVELOPMENT_WATER_BOX_DYNAMICS_FAILURE_V3_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_water_box_dynamics_failure_profile/3.0.0";
pub const DEVELOPMENT_WATER_BOX_DYNAMICS_FAILURE_V3_PROFILE_ID: &str =
    "engine_v2_native_exception_boundary_matrix_development_v3";
pub const DEVELOPMENT_WATER_ION_V1_PARAMETER_SOURCE_DOI: &str = "10.1021/jp8001614";
pub const DEVELOPMENT_WATER_ION_V1_ATOM_COUNT: usize = 8;
const DEVELOPMENT_WATER_BOX_V1_PROFILE_BYTES: &[u8] =
    include_bytes!("../assets/engine_v2_native_water_box_profile_v1.json");
const DEVELOPMENT_WATER_BOX_CONSTRAINTS_V1_PROFILE_BYTES: &[u8] =
    include_bytes!("../assets/engine_v2_native_water_box_constraints_profile_v1.json");
const DEVELOPMENT_WATER_BOX_NVT_ENSEMBLE_V1_PROFILE_BYTES: &[u8] =
    include_bytes!("../assets/engine_v2_native_water_box_nvt_ensemble_profile_v1.json");
const DEVELOPMENT_WATER_BOX_NVT_CONSTRAINT_RESIDUAL_V1_PROFILE_BYTES: &[u8] =
    include_bytes!("../assets/engine_v2_native_water_box_nvt_constraint_residual_profile_v1.json");
const DEVELOPMENT_WATER_ION_V1_PROFILE_BYTES: &[u8] =
    include_bytes!("../assets/engine_v2_native_water_ion_profile_v1.json");
const DEVELOPMENT_WATER_ION_DYNAMICS_V1_PROFILE_BYTES: &[u8] =
    include_bytes!("../assets/engine_v2_native_water_ion_dynamics_profile_v1.json");
const DEVELOPMENT_WATER_BOX_DYNAMICS_FAILURE_V1_PROFILE_BYTES: &[u8] =
    include_bytes!("../assets/engine_v2_native_water_box_dynamics_failure_profile_v1.json");
const DEVELOPMENT_WATER_BOX_DYNAMICS_FAILURE_V2_PROFILE_BYTES: &[u8] =
    include_bytes!("../assets/engine_v2_native_water_box_dynamics_failure_profile_v2.json");
const DEVELOPMENT_WATER_BOX_DYNAMICS_FAILURE_V3_PROFILE_BYTES: &[u8] =
    include_bytes!("../assets/engine_v2_native_water_box_dynamics_failure_profile_v3.json");

const OH_DISTANCE_ANGSTROM: f64 = f64::from_bits(0x3feea161e4f765fe);
const HOH_ANGLE_RADIANS: f64 = f64::from_bits(0x3ffd2fff5ab17aaf);
const BOND_FORCE_KCAL_PER_MOL_ANGSTROM2: f64 = 450.0;
const ANGLE_FORCE_KCAL_PER_MOL_RADIAN2: f64 = 55.0;
const OXYGEN_SIGMA_ANGSTROM: f64 = f64::from_bits(0x4009347304039abf);
const OXYGEN_EPSILON_KCAL_PER_MOL: f64 = f64::from_bits(0x3fc3780346dc5d64);
// The native ABI requires every sigma to be positive. Hydrogen epsilon is
// exactly zero, so this positive representation preserves its exact zero LJ
// contribution while replacing the Python profile's zero-sigma sentinel.
const HYDROGEN_NATIVE_SIGMA_SENTINEL_ANGSTROM: f64 = 1.0;
const BOX_ANGSTROM: f64 = 14.0;
const CUTOFF_ANGSTROM: f64 = 6.99;
const SWITCH_START_ANGSTROM: f64 = 6.5;
const TIMESTEP_FEMTOSECONDS: f64 = 0.02;
const TEMPERATURE_KELVIN: f64 = 300.0;
const FRICTION_PER_FEMTOSECOND: f64 = 0.001;
const HH_DISTANCE_ANGSTROM: f64 = 2.0 * f64::from_bits(0x3fe838efe48967cf);
const CONSTRAINT_TOLERANCE_ANGSTROM: f64 = 1.0e-10;
const CONSTRAINT_VELOCITY_TOLERANCE_ANGSTROM_PER_FEMTOSECOND: f64 = 1.0e-10;
const CONSTRAINT_MAX_ITERATIONS: u32 = 100;
const NVT_ENSEMBLE_TIMESTEP_FEMTOSECONDS: f64 = 0.5;
const NVT_ENSEMBLE_FRICTION_PER_FEMTOSECOND: f64 = 0.01;
const NVT_ENSEMBLE_SEEDS: [u64; 8] = [101, 211, 307, 401, 503, 601, 701, 809];
const NVT_ENSEMBLE_BURN_IN_STEPS: u64 = 2_000;
const NVT_ENSEMBLE_SAMPLE_COUNT: usize = 32;
const NVT_ENSEMBLE_SAMPLE_STRIDE_STEPS: u64 = 100;

const SODIUM_SIGMA_ANGSTROM: f64 = f64::from_bits(0x4003_83a5_9833_bb42);
const SODIUM_EPSILON_KCAL_PER_MOL: f64 = f64::from_bits(0x3fb6_626c_05e2_9810);
const CHLORIDE_SIGMA_ANGSTROM: f64 = f64::from_bits(0x4011_e91e_e7ca_8064);
const CHLORIDE_EPSILON_KCAL_PER_MOL: f64 = f64::from_bits(0x3fa2_38fb_ca10_59ea);

const POSITION_X: [f64; DEVELOPMENT_WATER_BOX_V1_ATOM_COUNT] = [
    0.0,
    f64::from_bits(0x3fe2bf8c302c3616),
    f64::from_bits(0x3fe2bf8c302c3616),
    4.0,
    f64::from_bits(0x401257f1860586c3),
    f64::from_bits(0x401257f1860586c3),
];
const POSITION_Y: [f64; DEVELOPMENT_WATER_BOX_V1_ATOM_COUNT] = [
    0.0,
    f64::from_bits(0x3fe838efe48967cf),
    f64::from_bits(0xbfe838efe48967cf),
    0.0,
    f64::from_bits(0x3fe838efe48967cf),
    f64::from_bits(0xbfe838efe48967cf),
];
const POSITION_Z: [f64; DEVELOPMENT_WATER_BOX_V1_ATOM_COUNT] = [0.0; 6];
const VELOCITY_X: [f64; DEVELOPMENT_WATER_BOX_V1_ATOM_COUNT] = [0.0; 6];
const VELOCITY_Y: [f64; DEVELOPMENT_WATER_BOX_V1_ATOM_COUNT] = [0.0; 6];
const VELOCITY_Z: [f64; DEVELOPMENT_WATER_BOX_V1_ATOM_COUNT] =
    [0.0, 0.0001, -0.0001, 0.0, 0.0, 0.0];
const MASS_DALTON: [f64; DEVELOPMENT_WATER_BOX_V1_ATOM_COUNT] = [
    f64::from_bits(0x402fffb15b573eab),
    f64::from_bits(0x3ff020c49ba5e354),
    f64::from_bits(0x3ff020c49ba5e354),
    f64::from_bits(0x402fffb15b573eab),
    f64::from_bits(0x3ff020c49ba5e354),
    f64::from_bits(0x3ff020c49ba5e354),
];
const CHARGE_ELEMENTARY: [f64; DEVELOPMENT_WATER_BOX_V1_ATOM_COUNT] = [
    f64::from_bits(0xbfeab020c49ba5e3),
    f64::from_bits(0x3fdab020c49ba5e3),
    f64::from_bits(0x3fdab020c49ba5e3),
    f64::from_bits(0xbfeab020c49ba5e3),
    f64::from_bits(0x3fdab020c49ba5e3),
    f64::from_bits(0x3fdab020c49ba5e3),
];

const ATOM_NONBONDED: [AtomNonbonded; DEVELOPMENT_WATER_BOX_V1_ATOM_COUNT] = [
    oxygen_nonbonded(),
    hydrogen_nonbonded(),
    hydrogen_nonbonded(),
    oxygen_nonbonded(),
    hydrogen_nonbonded(),
    hydrogen_nonbonded(),
];
const BONDS: [HarmonicBond; 4] = [bond(0, 1), bond(0, 2), bond(3, 4), bond(3, 5)];
const ANGLES: [HarmonicAngle; 2] = [angle(1, 0, 2), angle(4, 3, 5)];
const EXCLUSIONS: [PairExclusion; 6] = [
    exclusion(0, 1),
    exclusion(0, 2),
    exclusion(1, 2),
    exclusion(3, 4),
    exclusion(3, 5),
    exclusion(4, 5),
];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct DevelopmentIonIdentityV1 {
    pub atomic_number: u8,
    pub formal_charge: i8,
}

impl DevelopmentIonIdentityV1 {
    pub const SODIUM: Self = Self {
        atomic_number: 11,
        formal_charge: 1,
    };
    pub const CHLORIDE: Self = Self {
        atomic_number: 17,
        formal_charge: -1,
    };

    pub const fn new(atomic_number: u8, formal_charge: i8) -> Self {
        Self {
            atomic_number,
            formal_charge,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum DevelopmentIonSpeciesV1 {
    Sodium,
    Chloride,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct DevelopmentIonParametersV1 {
    pub species: DevelopmentIonSpeciesV1,
    pub identity: DevelopmentIonIdentityV1,
    pub charge_elementary: f64,
    pub mass_dalton: f64,
    pub rmin_over_2_angstrom: f64,
    pub sigma_angstrom: f64,
    pub epsilon_kcal_per_mol: f64,
    pub parameter_source_doi: &'static str,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum DevelopmentIonParameterErrorV1 {
    UnsupportedIdentity(DevelopmentIonIdentityV1),
}

impl fmt::Display for DevelopmentIonParameterErrorV1 {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::UnsupportedIdentity(identity) => write!(
                formatter,
                "unsupported development ion identity: atomic_number={}, formal_charge={}",
                identity.atomic_number, identity.formal_charge
            ),
        }
    }
}

impl std::error::Error for DevelopmentIonParameterErrorV1 {}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum DevelopmentDynamicsFailureCodeV1 {
    InvalidArgument,
    CapacityOverflow,
    OutOfMemory,
    UnsupportedIonIdentity,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum DevelopmentDynamicsFailureEvidenceV1 {
    SafeWrapperRejection,
    NativeRuntimeRejection,
    SafeWrapperCapacityPreflight,
    StatusMappingOnly,
    DomainCatalogRejection,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct DevelopmentDynamicsFailureRowV1 {
    pub case_id: &'static str,
    pub failure_code: DevelopmentDynamicsFailureCodeV1,
    pub evidence_kind: DevelopmentDynamicsFailureEvidenceV1,
    pub failure_attempted: bool,
    pub state_preserved: Option<bool>,
    pub message: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct DevelopmentDynamicsFailureReportV1 {
    pub backend: Backend,
    pub rows: Vec<DevelopmentDynamicsFailureRowV1>,
    pub all_required_failure_classes_typed: bool,
    pub all_required_failure_classes_runtime_exercised: bool,
    pub oom_allocation_attempted: bool,
    pub observation_receipt_sha256: [u8; 32],
}

pub fn development_ion_parameters_v1(
    identity: DevelopmentIonIdentityV1,
) -> std::result::Result<DevelopmentIonParametersV1, DevelopmentIonParameterErrorV1> {
    let parameters = match identity {
        DevelopmentIonIdentityV1::SODIUM => DevelopmentIonParametersV1 {
            species: DevelopmentIonSpeciesV1::Sodium,
            identity,
            charge_elementary: 1.0,
            mass_dalton: 22.99,
            rmin_over_2_angstrom: 1.369,
            sigma_angstrom: SODIUM_SIGMA_ANGSTROM,
            epsilon_kcal_per_mol: SODIUM_EPSILON_KCAL_PER_MOL,
            parameter_source_doi: DEVELOPMENT_WATER_ION_V1_PARAMETER_SOURCE_DOI,
        },
        DevelopmentIonIdentityV1::CHLORIDE => DevelopmentIonParametersV1 {
            species: DevelopmentIonSpeciesV1::Chloride,
            identity,
            charge_elementary: -1.0,
            mass_dalton: 35.45,
            rmin_over_2_angstrom: 2.513,
            sigma_angstrom: CHLORIDE_SIGMA_ANGSTROM,
            epsilon_kcal_per_mol: CHLORIDE_EPSILON_KCAL_PER_MOL,
            parameter_source_doi: DEVELOPMENT_WATER_ION_V1_PARAMETER_SOURCE_DOI,
        },
        unsupported => {
            return Err(DevelopmentIonParameterErrorV1::UnsupportedIdentity(
                unsupported,
            ));
        }
    };
    Ok(parameters)
}

const fn oxygen_nonbonded() -> AtomNonbonded {
    AtomNonbonded {
        sigma_angstrom: OXYGEN_SIGMA_ANGSTROM,
        epsilon_kcal_per_mol: OXYGEN_EPSILON_KCAL_PER_MOL,
    }
}

const fn hydrogen_nonbonded() -> AtomNonbonded {
    AtomNonbonded {
        sigma_angstrom: HYDROGEN_NATIVE_SIGMA_SENTINEL_ANGSTROM,
        epsilon_kcal_per_mol: 0.0,
    }
}

const fn bond(atom_i: usize, atom_j: usize) -> HarmonicBond {
    HarmonicBond {
        atom_i,
        atom_j,
        equilibrium_angstrom: OH_DISTANCE_ANGSTROM,
        force_constant_kcal_per_mol_angstrom2: BOND_FORCE_KCAL_PER_MOL_ANGSTROM2,
    }
}

const fn angle(atom_i: usize, atom_j: usize, atom_k: usize) -> HarmonicAngle {
    HarmonicAngle {
        atom_i,
        atom_j,
        atom_k,
        equilibrium_radians: HOH_ANGLE_RADIANS,
        force_constant_kcal_per_mol_radian2: ANGLE_FORCE_KCAL_PER_MOL_RADIAN2,
    }
}

const fn exclusion(atom_i: usize, atom_j: usize) -> PairExclusion {
    PairExclusion { atom_i, atom_j }
}

fn system() -> Result<System> {
    System::new(
        ParticleSoa::new(
            PositionSoa::new(&POSITION_X, &POSITION_Y, &POSITION_Z),
            &MASS_DALTON,
            &CHARGE_ELEMENTARY,
        )
        .with_velocities(VelocitySoa::new(&VELOCITY_X, &VELOCITY_Y, &VELOCITY_Z)),
    )
}

fn single_water_system() -> Result<System> {
    System::new(ParticleSoa::new(
        PositionSoa::new(&POSITION_X[..3], &POSITION_Y[..3], &POSITION_Z[..3]),
        &MASS_DALTON[..3],
        &CHARGE_ELEMENTARY[..3],
    ))
}

fn water_ion_system() -> Result<System> {
    water_ion_system_with_velocities(false)
}

fn water_ion_dynamics_system() -> Result<System> {
    water_ion_system_with_velocities(true)
}

fn water_ion_system_with_velocities(include_velocities: bool) -> Result<System> {
    let sodium = development_ion_parameters_v1(DevelopmentIonIdentityV1::SODIUM)
        .map_err(|error| invalid(error.to_string()))?;
    let chloride = development_ion_parameters_v1(DevelopmentIonIdentityV1::CHLORIDE)
        .map_err(|error| invalid(error.to_string()))?;
    let position_x = [
        POSITION_X[0],
        POSITION_X[1],
        POSITION_X[2],
        POSITION_X[3],
        POSITION_X[4],
        POSITION_X[5],
        8.0,
        10.5,
    ];
    let position_y = [
        POSITION_Y[0],
        POSITION_Y[1],
        POSITION_Y[2],
        POSITION_Y[3],
        POSITION_Y[4],
        POSITION_Y[5],
        2.0,
        2.0,
    ];
    let position_z = [0.0; DEVELOPMENT_WATER_ION_V1_ATOM_COUNT];
    let mass = [
        MASS_DALTON[0],
        MASS_DALTON[1],
        MASS_DALTON[2],
        MASS_DALTON[3],
        MASS_DALTON[4],
        MASS_DALTON[5],
        sodium.mass_dalton,
        chloride.mass_dalton,
    ];
    let charge = [
        CHARGE_ELEMENTARY[0],
        CHARGE_ELEMENTARY[1],
        CHARGE_ELEMENTARY[2],
        CHARGE_ELEMENTARY[3],
        CHARGE_ELEMENTARY[4],
        CHARGE_ELEMENTARY[5],
        sodium.charge_elementary,
        chloride.charge_elementary,
    ];
    let particles = ParticleSoa::new(
        PositionSoa::new(&position_x, &position_y, &position_z),
        &mass,
        &charge,
    );
    if include_velocities {
        let velocity_x = [
            VELOCITY_X[0],
            VELOCITY_X[1],
            VELOCITY_X[2],
            VELOCITY_X[3],
            VELOCITY_X[4],
            VELOCITY_X[5],
            0.0,
            0.0,
        ];
        let velocity_y = [
            VELOCITY_Y[0],
            VELOCITY_Y[1],
            VELOCITY_Y[2],
            VELOCITY_Y[3],
            VELOCITY_Y[4],
            VELOCITY_Y[5],
            0.0,
            0.0,
        ];
        let velocity_z = [
            VELOCITY_Z[0],
            VELOCITY_Z[1],
            VELOCITY_Z[2],
            VELOCITY_Z[3],
            VELOCITY_Z[4],
            VELOCITY_Z[5],
            0.0,
            0.0,
        ];
        System::new(particles.with_velocities(VelocitySoa::new(
            &velocity_x,
            &velocity_y,
            &velocity_z,
        )))
    } else {
        System::new(particles)
    }
}

fn forcefield() -> Result<ForceField> {
    let mut input = ForceFieldInput::new(&ATOM_NONBONDED);
    input.bonds = &BONDS;
    input.angles = &ANGLES;
    input.exclusions = &EXCLUSIONS;
    input.cell = Some(OrthorhombicCell {
        lengths_angstrom: [BOX_ANGSTROM; 3],
        periodic_axes: [true; 3],
    });
    input.nonbonded.cutoff_angstrom = CUTOFF_ANGSTROM;
    input.nonbonded.switch_start_angstrom = SWITCH_START_ANGSTROM;
    input.nonbonded.dielectric = 1.0;
    input.nonbonded.screening_kappa_per_angstrom = 0.0;
    input.nonbonded.minimum_pair_distance_angstrom = 1.0e-10;
    ForceField::new(input)
}

fn single_water_forcefield() -> Result<ForceField> {
    let mut input = ForceFieldInput::new(&ATOM_NONBONDED[..3]);
    input.bonds = &BONDS[..2];
    input.angles = &ANGLES[..1];
    input.exclusions = &EXCLUSIONS[..3];
    ForceField::new(input)
}

fn water_ion_forcefield() -> Result<ForceField> {
    let sodium = development_ion_parameters_v1(DevelopmentIonIdentityV1::SODIUM)
        .map_err(|error| invalid(error.to_string()))?;
    let chloride = development_ion_parameters_v1(DevelopmentIonIdentityV1::CHLORIDE)
        .map_err(|error| invalid(error.to_string()))?;
    let atom_nonbonded = [
        ATOM_NONBONDED[0],
        ATOM_NONBONDED[1],
        ATOM_NONBONDED[2],
        ATOM_NONBONDED[3],
        ATOM_NONBONDED[4],
        ATOM_NONBONDED[5],
        AtomNonbonded {
            sigma_angstrom: sodium.sigma_angstrom,
            epsilon_kcal_per_mol: sodium.epsilon_kcal_per_mol,
        },
        AtomNonbonded {
            sigma_angstrom: chloride.sigma_angstrom,
            epsilon_kcal_per_mol: chloride.epsilon_kcal_per_mol,
        },
    ];
    let mut input = ForceFieldInput::new(&atom_nonbonded);
    input.bonds = &BONDS;
    input.angles = &ANGLES;
    input.exclusions = &EXCLUSIONS;
    input.cell = Some(OrthorhombicCell {
        lengths_angstrom: [BOX_ANGSTROM; 3],
        periodic_axes: [true; 3],
    });
    input.nonbonded.cutoff_angstrom = CUTOFF_ANGSTROM;
    input.nonbonded.switch_start_angstrom = SWITCH_START_ANGSTROM;
    input.nonbonded.dielectric = 1.0;
    input.nonbonded.screening_kappa_per_angstrom = 0.0;
    input.nonbonded.minimum_pair_distance_angstrom = 1.0e-10;
    ForceField::new(input)
}

fn require_cpu_backend(context: &Context, profile_id: &str) -> Result<()> {
    match context.backend()? {
        Backend::CppCpuReference | Backend::RustCpu => Ok(()),
        backend => Err(invalid(format!(
            "{profile_id} is a CPU-only development profile; resolved backend {backend:?} is not admitted"
        ))),
    }
}

/// SHA-256 of the exact profile embedded into this compiled runtime.
pub fn development_water_box_v1_profile_sha256() -> [u8; 32] {
    Sha256::digest(DEVELOPMENT_WATER_BOX_V1_PROFILE_BYTES).into()
}

/// SHA-256 of the exact rigid-water successor profile embedded into this runtime.
pub fn development_water_box_constraints_v1_profile_sha256() -> [u8; 32] {
    Sha256::digest(DEVELOPMENT_WATER_BOX_CONSTRAINTS_V1_PROFILE_BYTES).into()
}

/// SHA-256 of the exact repeated-seed NVT observation profile.
pub fn development_water_box_nvt_ensemble_v1_profile_sha256() -> [u8; 32] {
    Sha256::digest(DEVELOPMENT_WATER_BOX_NVT_ENSEMBLE_V1_PROFILE_BYTES).into()
}

/// SHA-256 of the exact repeated-seed constraint-residual observation profile.
pub fn development_water_box_nvt_constraint_residual_v1_profile_sha256() -> [u8; 32] {
    Sha256::digest(DEVELOPMENT_WATER_BOX_NVT_CONSTRAINT_RESIDUAL_V1_PROFILE_BYTES).into()
}

/// SHA-256 of the exact bounded NaCl development profile embedded into this runtime.
pub fn development_water_ion_v1_profile_sha256() -> [u8; 32] {
    Sha256::digest(DEVELOPMENT_WATER_ION_V1_PROFILE_BYTES).into()
}

/// SHA-256 of the exact constrained water-ion dynamics profile.
pub fn development_water_ion_dynamics_v1_profile_sha256() -> [u8; 32] {
    Sha256::digest(DEVELOPMENT_WATER_ION_DYNAMICS_V1_PROFILE_BYTES).into()
}

/// SHA-256 of the exact typed-failure matrix profile.
pub fn development_water_box_dynamics_failure_v1_profile_sha256() -> [u8; 32] {
    Sha256::digest(DEVELOPMENT_WATER_BOX_DYNAMICS_FAILURE_V1_PROFILE_BYTES).into()
}

/// SHA-256 of the native exception-boundary successor profile.
pub fn development_water_box_dynamics_failure_v2_profile_sha256() -> [u8; 32] {
    Sha256::digest(DEVELOPMENT_WATER_BOX_DYNAMICS_FAILURE_V2_PROFILE_BYTES).into()
}

/// SHA-256 of the complete native exception-boundary matrix profile.
pub fn development_water_box_dynamics_failure_v3_profile_sha256() -> [u8; 32] {
    Sha256::digest(DEVELOPMENT_WATER_BOX_DYNAMICS_FAILURE_V3_PROFILE_BYTES).into()
}

/// Observe the bounded CPU dynamics typed-failure contract.
///
/// Four rows execute deterministic rejection paths. The OOM row intentionally
/// verifies only the public native-status to safe-Rust error mapping; it does
/// not allocate, inject a production failure, or claim OOM resilience.
pub fn observe_development_water_box_dynamics_failures_v1(
    context: &Context,
) -> Result<DevelopmentDynamicsFailureReportV1> {
    require_cpu_backend(
        context,
        DEVELOPMENT_WATER_BOX_DYNAMICS_FAILURE_V1_PROFILE_ID,
    )?;
    let backend = context.backend()?;
    let mut rows = Vec::with_capacity(5);

    let nonfinite_x = [f64::NAN];
    let zero = [0.0];
    let mass = [1.0];
    let nonfinite_error = expected_error(
        System::new(ParticleSoa::new(
            PositionSoa::new(&nonfinite_x, &zero, &zero),
            &mass,
            &zero,
        )),
        "nonfinite particle position unexpectedly created a system",
    )?;
    rows.push(native_failure_row(
        "nonfinite_particle_position",
        DevelopmentDynamicsFailureCodeV1::InvalidArgument,
        DevelopmentDynamicsFailureEvidenceV1::SafeWrapperRejection,
        nonfinite_error,
        None,
    )?);

    let singular_x = [0.0, 1.0, 2.0];
    let singular_zero = [0.0; 3];
    let singular_mass = [1.0; 3];
    let singular_system = System::new(ParticleSoa::new(
        PositionSoa::new(&singular_x, &singular_zero, &singular_zero),
        &singular_mass,
        &singular_zero,
    ))?;
    let singular_nonbonded = [AtomNonbonded {
        sigma_angstrom: 1.0,
        epsilon_kcal_per_mol: 0.0,
    }; 3];
    let singular_forcefield = ForceField::new(ForceFieldInput::new(&singular_nonbonded))?;
    let singular_constraints = DistanceConstraints {
        rows: vec![
            DistanceConstraint {
                atom_i: 0,
                atom_j: 1,
                distance_angstrom: 1.0,
            },
            DistanceConstraint {
                atom_i: 1,
                atom_j: 2,
                distance_angstrom: 1.0,
            },
            DistanceConstraint {
                atom_i: 0,
                atom_j: 2,
                distance_angstrom: 2.0,
            },
        ],
        ..DistanceConstraints::default()
    };
    let singular_error = expected_error(
        Simulation::new(
            &singular_system,
            &singular_forcefield,
            &singular_constraints,
            SimulationOptions::default(),
        ),
        "linearly dependent constraints unexpectedly created a simulation",
    )?;
    rows.push(native_failure_row(
        "linearly_dependent_constraint_jacobian",
        DevelopmentDynamicsFailureCodeV1::InvalidArgument,
        DevelopmentDynamicsFailureEvidenceV1::NativeRuntimeRejection,
        singular_error,
        None,
    )?);

    let mut capacity_fixture = DevelopmentWaterIonDynamicsV1::constrained_nve()?;
    let mut maximum_step_checkpoint = capacity_fixture.checkpoint()?;
    if maximum_step_checkpoint.len() < 104 {
        return Err(invalid(
            "capacity fixture checkpoint is shorter than its canonical header",
        ));
    }
    maximum_step_checkpoint[32..40].copy_from_slice(&u64::MAX.to_le_bytes());
    maximum_step_checkpoint[72..104].fill(0);
    let digest = Sha256::digest(&maximum_step_checkpoint);
    maximum_step_checkpoint[72..104].copy_from_slice(&digest);
    capacity_fixture.load_checkpoint(&maximum_step_checkpoint)?;
    if capacity_fixture.absolute_step()? != u64::MAX {
        return Err(invalid(
            "capacity fixture did not restore the maximum uint64 absolute step",
        ));
    }
    let capacity_snapshot = capacity_fixture.snapshot()?;
    let capacity_checkpoint = capacity_fixture.checkpoint()?;
    let capacity_error = expected_error(
        capacity_fixture.integrate(context, 1),
        "maximum absolute step unexpectedly accepted another dynamics step",
    )?;
    let capacity_state_preserved = capacity_fixture.absolute_step()? == u64::MAX
        && capacity_fixture.snapshot()? == capacity_snapshot
        && capacity_fixture.checkpoint()? == capacity_checkpoint;
    if !capacity_state_preserved {
        return Err(invalid(
            "capacity failure modified the frozen dynamics state or checkpoint",
        ));
    }
    rows.push(native_failure_row(
        "absolute_step_uint64_overflow",
        DevelopmentDynamicsFailureCodeV1::CapacityOverflow,
        DevelopmentDynamicsFailureEvidenceV1::SafeWrapperCapacityPreflight,
        capacity_error,
        Some(true),
    )?);

    if ErrorCode::from_raw(sys::BG_STATUS_OUT_OF_MEMORY) != Some(ErrorCode::OutOfMemory) {
        return Err(invalid(
            "native out-of-memory status did not map to the safe Rust error code",
        ));
    }
    rows.push(DevelopmentDynamicsFailureRowV1 {
        case_id: "out_of_memory_status_mapping",
        failure_code: DevelopmentDynamicsFailureCodeV1::OutOfMemory,
        evidence_kind: DevelopmentDynamicsFailureEvidenceV1::StatusMappingOnly,
        failure_attempted: false,
        state_preserved: None,
        message: "BG_STATUS_OUT_OF_MEMORY maps to ErrorCode::OutOfMemory; allocation not attempted"
            .to_owned(),
    });

    let unsupported = DevelopmentIonIdentityV1::new(19, 1);
    let unsupported_error = development_ion_parameters_v1(unsupported)
        .expect_err("unsupported development ion identity unexpectedly resolved parameters");
    if unsupported_error != DevelopmentIonParameterErrorV1::UnsupportedIdentity(unsupported) {
        return Err(invalid(
            "unsupported ion identity returned the wrong domain error",
        ));
    }
    rows.push(DevelopmentDynamicsFailureRowV1 {
        case_id: "unsupported_ion_identity",
        failure_code: DevelopmentDynamicsFailureCodeV1::UnsupportedIonIdentity,
        evidence_kind: DevelopmentDynamicsFailureEvidenceV1::DomainCatalogRejection,
        failure_attempted: true,
        state_preserved: None,
        message: unsupported_error.to_string(),
    });

    let expected_case_ids = [
        "nonfinite_particle_position",
        "linearly_dependent_constraint_jacobian",
        "absolute_step_uint64_overflow",
        "out_of_memory_status_mapping",
        "unsupported_ion_identity",
    ];
    if rows.iter().map(|row| row.case_id).ne(expected_case_ids) {
        return Err(invalid("typed-failure rows are not in canonical order"));
    }
    let mut receipt = Sha256::new();
    receipt.update(b"betelgeuze.engine_v2_native_water_box_dynamics_failure_observation/1.0.0\0");
    receipt.update(development_water_box_dynamics_failure_v1_profile_sha256());
    receipt.update([failure_backend_tag(backend)?]);
    receipt.update(
        u64::try_from(rows.len())
            .map_err(|_| invalid("typed-failure row count exceeds u64"))?
            .to_le_bytes(),
    );
    for row in &rows {
        receipt.update(row.case_id.as_bytes());
        receipt.update([0]);
        receipt.update([failure_code_tag(row.failure_code)]);
        receipt.update([failure_evidence_tag(row.evidence_kind)]);
        receipt.update([u8::from(row.failure_attempted)]);
        receipt.update([match row.state_preserved {
            None => 0,
            Some(false) => 1,
            Some(true) => 2,
        }]);
        receipt.update(row.message.as_bytes());
        receipt.update([0]);
    }
    receipt.update([1, 0, 0]);

    Ok(DevelopmentDynamicsFailureReportV1 {
        backend,
        rows,
        all_required_failure_classes_typed: true,
        all_required_failure_classes_runtime_exercised: false,
        oom_allocation_attempted: false,
        observation_receipt_sha256: receipt.finalize().into(),
    })
}

fn expected_error<T>(result: Result<T>, success_message: &'static str) -> Result<Error> {
    match result {
        Ok(_) => Err(invalid(success_message)),
        Err(error) => Ok(error),
    }
}

fn native_failure_row(
    case_id: &'static str,
    failure_code: DevelopmentDynamicsFailureCodeV1,
    evidence_kind: DevelopmentDynamicsFailureEvidenceV1,
    error: Error,
    state_preserved: Option<bool>,
) -> Result<DevelopmentDynamicsFailureRowV1> {
    let expected_error_code = match failure_code {
        DevelopmentDynamicsFailureCodeV1::InvalidArgument => ErrorCode::InvalidArgument,
        DevelopmentDynamicsFailureCodeV1::CapacityOverflow => ErrorCode::CapacityOverflow,
        DevelopmentDynamicsFailureCodeV1::OutOfMemory => ErrorCode::OutOfMemory,
        DevelopmentDynamicsFailureCodeV1::UnsupportedIonIdentity => {
            return Err(invalid(
                "unsupported-ion domain error cannot be built from a native error",
            ));
        }
    };
    if error.code != expected_error_code {
        return Err(invalid(format!(
            "{case_id} returned {:?} instead of {expected_error_code:?}",
            error.code
        )));
    }
    Ok(DevelopmentDynamicsFailureRowV1 {
        case_id,
        failure_code,
        evidence_kind,
        failure_attempted: true,
        state_preserved,
        message: error.message,
    })
}

const fn failure_code_tag(code: DevelopmentDynamicsFailureCodeV1) -> u8 {
    match code {
        DevelopmentDynamicsFailureCodeV1::InvalidArgument => 1,
        DevelopmentDynamicsFailureCodeV1::CapacityOverflow => 2,
        DevelopmentDynamicsFailureCodeV1::OutOfMemory => 3,
        DevelopmentDynamicsFailureCodeV1::UnsupportedIonIdentity => 4,
    }
}

const fn failure_evidence_tag(evidence: DevelopmentDynamicsFailureEvidenceV1) -> u8 {
    match evidence {
        DevelopmentDynamicsFailureEvidenceV1::SafeWrapperRejection => 1,
        DevelopmentDynamicsFailureEvidenceV1::NativeRuntimeRejection => 2,
        DevelopmentDynamicsFailureEvidenceV1::SafeWrapperCapacityPreflight => 3,
        DevelopmentDynamicsFailureEvidenceV1::StatusMappingOnly => 4,
        DevelopmentDynamicsFailureEvidenceV1::DomainCatalogRejection => 5,
    }
}

fn failure_backend_tag(backend: Backend) -> Result<u8> {
    match backend {
        Backend::CppCpuReference => Ok(1),
        Backend::RustCpu => Ok(2),
        Backend::Auto | Backend::HipFast | Backend::HipSafe => Err(invalid(
            "typed-failure CPU guard admitted an unsupported backend",
        )),
    }
}

/// Evaluate one frozen unconstrained water through a selected CPU backend.
pub fn evaluate_development_single_water_v1(context: &Context) -> Result<Evaluation> {
    require_cpu_backend(context, DEVELOPMENT_WATER_BOX_V1_PROFILE_ID)?;
    context.evaluate(&single_water_system()?, &single_water_forcefield()?)
}

/// Evaluate the frozen initial coordinates through the selected native backend.
pub fn evaluate_development_water_box_v1(context: &Context) -> Result<Evaluation> {
    require_cpu_backend(context, DEVELOPMENT_WATER_BOX_V1_PROFILE_ID)?;
    context.evaluate(&system()?, &forcefield()?)
}

/// Evaluate the frozen neutral two-water plus Na+/Cl- static CPU fixture.
pub fn evaluate_development_water_ion_v1(context: &Context) -> Result<Evaluation> {
    require_cpu_backend(context, DEVELOPMENT_WATER_ION_V1_PROFILE_ID)?;
    context.evaluate(&water_ion_system()?, &water_ion_forcefield()?)
}

/// Native-owned frozen two-water development simulation.
pub struct DevelopmentWaterBoxV1 {
    simulation: Simulation,
}

/// Native-owned constrained neutral two-water plus Na+/Cl- development simulation.
pub struct DevelopmentWaterIonDynamicsV1 {
    simulation: Simulation,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct DevelopmentWaterBoxNvtObservationV1 {
    pub random_seed: u64,
    pub sample_index: u32,
    pub absolute_step: u64,
    pub degrees_of_freedom: u64,
    pub kinetic_kcal_per_mol: f64,
    pub temperature_kelvin: f64,
}

#[derive(Clone, Debug, PartialEq)]
pub struct DevelopmentWaterBoxNvtEnsembleReportV1 {
    pub backend: Backend,
    pub observations: Vec<DevelopmentWaterBoxNvtObservationV1>,
    pub mean_kinetic_kcal_per_mol: f64,
    pub mean_temperature_kelvin: f64,
    pub temperature_variance_kelvin2: f64,
    pub observation_receipt_sha256: [u8; 32],
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct DevelopmentWaterBoxNvtConstraintObservationV1 {
    pub random_seed: u64,
    pub sample_index: u32,
    pub absolute_step: u64,
    pub degrees_of_freedom: u64,
    pub kinetic_kcal_per_mol: f64,
    pub temperature_kelvin: f64,
    pub maximum_position_constraint_residual_angstrom: f64,
    pub maximum_radial_velocity_constraint_residual_angstrom_per_femtosecond: f64,
}

#[derive(Clone, Debug, PartialEq)]
pub struct DevelopmentWaterBoxNvtConstraintEnsembleReportV1 {
    pub backend: Backend,
    pub observations: Vec<DevelopmentWaterBoxNvtConstraintObservationV1>,
    pub mean_kinetic_kcal_per_mol: f64,
    pub mean_temperature_kelvin: f64,
    pub temperature_variance_kelvin2: f64,
    pub mean_position_constraint_residual_angstrom: f64,
    pub maximum_position_constraint_residual_angstrom: f64,
    pub mean_radial_velocity_constraint_residual_angstrom_per_femtosecond: f64,
    pub maximum_radial_velocity_constraint_residual_angstrom_per_femtosecond: f64,
    pub observation_receipt_sha256: [u8; 32],
}

#[derive(Clone, Copy)]
struct DevelopmentWaterBoxNvtSummary {
    observation_count: u32,
    mean_kinetic_kcal_per_mol: f64,
    mean_temperature_kelvin: f64,
    temperature_variance_kelvin2: f64,
}

#[derive(Clone, Copy)]
struct DevelopmentWaterBoxConstraintResidualSummary {
    mean_position_constraint_residual_angstrom: f64,
    maximum_position_constraint_residual_angstrom: f64,
    mean_radial_velocity_constraint_residual_angstrom_per_femtosecond: f64,
    maximum_radial_velocity_constraint_residual_angstrom_per_femtosecond: f64,
}

impl DevelopmentWaterBoxV1 {
    /// Construct the frozen deterministic NVE lane.
    pub fn nve() -> Result<Self> {
        Self::new(
            SimulationOptions {
                integrator: Integrator::VelocityVerlet,
                timestep_femtoseconds: TIMESTEP_FEMTOSECONDS,
                temperature_kelvin: TEMPERATURE_KELVIN,
                friction_per_femtosecond: 0.0,
                random_seed: 0,
            },
            false,
        )
    }

    /// Construct the frozen rigid-water SHAKE/RATTLE NVE lane.
    pub fn constrained_nve() -> Result<Self> {
        Self::new(
            SimulationOptions {
                integrator: Integrator::VelocityVerlet,
                timestep_femtoseconds: TIMESTEP_FEMTOSECONDS,
                temperature_kelvin: TEMPERATURE_KELVIN,
                friction_per_femtosecond: 0.0,
                random_seed: 0,
            },
            true,
        )
    }

    /// Construct the frozen deterministic BAOAB lane with an explicit seed.
    pub fn baoab(random_seed: u64) -> Result<Self> {
        Self::new(
            SimulationOptions {
                integrator: Integrator::LangevinBaoab,
                timestep_femtoseconds: TIMESTEP_FEMTOSECONDS,
                temperature_kelvin: TEMPERATURE_KELVIN,
                friction_per_femtosecond: FRICTION_PER_FEMTOSECOND,
                random_seed,
            },
            false,
        )
    }

    /// Construct the frozen rigid-water SHAKE/RATTLE BAOAB lane.
    pub fn constrained_baoab(random_seed: u64) -> Result<Self> {
        Self::new(
            SimulationOptions {
                integrator: Integrator::LangevinBaoab,
                timestep_femtoseconds: TIMESTEP_FEMTOSECONDS,
                temperature_kelvin: TEMPERATURE_KELVIN,
                friction_per_femtosecond: FRICTION_PER_FEMTOSECOND,
                random_seed,
            },
            true,
        )
    }

    fn new(options: SimulationOptions, constrained: bool) -> Result<Self> {
        let system = system()?;
        let forcefield = forcefield()?;
        let constraints = if constrained {
            frozen_water_constraints()
        } else {
            DistanceConstraints::default()
        };
        let simulation = Simulation::new(&system, &forcefield, &constraints, options)?;
        Ok(Self { simulation })
    }

    pub fn integrate(&mut self, context: &Context, step_count: u64) -> Result<DynamicsReport> {
        require_cpu_backend(context, DEVELOPMENT_WATER_BOX_V1_PROFILE_ID)?;
        context.integrate(&mut self.simulation, step_count)
    }

    pub fn snapshot(&self) -> Result<ParticleSnapshot> {
        self.simulation.snapshot()
    }

    pub fn absolute_step(&self) -> Result<u64> {
        self.simulation.absolute_step()
    }

    pub fn checkpoint(&self) -> Result<Vec<u8>> {
        self.simulation.checkpoint()
    }

    pub fn load_checkpoint(&mut self, checkpoint: &[u8]) -> Result<()> {
        self.simulation.load_checkpoint(checkpoint)
    }
}

impl DevelopmentWaterIonDynamicsV1 {
    /// Construct the frozen constrained Velocity Verlet water-ion lane.
    pub fn constrained_nve() -> Result<Self> {
        let system = water_ion_dynamics_system()?;
        let forcefield = water_ion_forcefield()?;
        let constraints = frozen_water_constraints();
        let simulation = Simulation::new(
            &system,
            &forcefield,
            &constraints,
            SimulationOptions {
                integrator: Integrator::VelocityVerlet,
                timestep_femtoseconds: TIMESTEP_FEMTOSECONDS,
                temperature_kelvin: TEMPERATURE_KELVIN,
                friction_per_femtosecond: 0.0,
                random_seed: 0,
            },
        )?;
        Ok(Self { simulation })
    }

    pub fn integrate(&mut self, context: &Context, step_count: u64) -> Result<DynamicsReport> {
        require_cpu_backend(context, DEVELOPMENT_WATER_ION_DYNAMICS_V1_PROFILE_ID)?;
        context.integrate(&mut self.simulation, step_count)
    }

    pub fn snapshot(&self) -> Result<ParticleSnapshot> {
        self.simulation.snapshot()
    }

    pub fn absolute_step(&self) -> Result<u64> {
        self.simulation.absolute_step()
    }

    pub fn checkpoint(&self) -> Result<Vec<u8>> {
        self.simulation.checkpoint()
    }

    pub fn load_checkpoint(&mut self, checkpoint: &[u8]) -> Result<()> {
        self.simulation.load_checkpoint(checkpoint)
    }
}

fn frozen_water_constraints() -> DistanceConstraints {
    DistanceConstraints {
        rows: vec![
            DistanceConstraint {
                atom_i: 0,
                atom_j: 1,
                distance_angstrom: OH_DISTANCE_ANGSTROM,
            },
            DistanceConstraint {
                atom_i: 0,
                atom_j: 2,
                distance_angstrom: OH_DISTANCE_ANGSTROM,
            },
            DistanceConstraint {
                atom_i: 1,
                atom_j: 2,
                distance_angstrom: HH_DISTANCE_ANGSTROM,
            },
            DistanceConstraint {
                atom_i: 3,
                atom_j: 4,
                distance_angstrom: OH_DISTANCE_ANGSTROM,
            },
            DistanceConstraint {
                atom_i: 3,
                atom_j: 5,
                distance_angstrom: OH_DISTANCE_ANGSTROM,
            },
            DistanceConstraint {
                atom_i: 4,
                atom_j: 5,
                distance_angstrom: HH_DISTANCE_ANGSTROM,
            },
        ],
        tolerance_angstrom: CONSTRAINT_TOLERANCE_ANGSTROM,
        velocity_tolerance_angstrom_per_femtosecond:
            CONSTRAINT_VELOCITY_TOLERANCE_ANGSTROM_PER_FEMTOSECOND,
        max_iterations: CONSTRAINT_MAX_ITERATIONS,
    }
}

/// Run the frozen repeated-seed constrained BAOAB development observation.
///
/// This is a tiny synthetic CPU validation lane. It does not authorize general
/// molecular execution, performance claims, or scientifically validated NVT.
pub fn observe_development_water_box_nvt_ensemble_v1(
    context: &Context,
) -> Result<DevelopmentWaterBoxNvtEnsembleReportV1> {
    require_cpu_backend(context, DEVELOPMENT_WATER_BOX_NVT_ENSEMBLE_V1_PROFILE_ID)?;
    let (backend, observations) = collect_development_water_box_nvt_observations(
        context,
        |_water_box, random_seed, sample_index, report| {
            Ok(DevelopmentWaterBoxNvtObservationV1 {
                random_seed,
                sample_index,
                absolute_step: report.absolute_step,
                degrees_of_freedom: report.degrees_of_freedom,
                kinetic_kcal_per_mol: report.kinetic_kcal_per_mol,
                temperature_kelvin: report.temperature_kelvin,
            })
        },
    )?;
    let summary = summarize_development_water_box_nvt(&observations, |row| {
        (row.kinetic_kcal_per_mol, row.temperature_kelvin)
    })?;
    let mut receipt = Sha256::new();
    receipt.update(b"betelgeuze.engine_v2_native_water_box_nvt_ensemble_observation/1.0.0\0");
    receipt.update(development_water_box_nvt_ensemble_v1_profile_sha256());
    receipt.update([nvt_backend_tag(backend)?]);
    receipt.update(u64::from(summary.observation_count).to_le_bytes());
    for row in &observations {
        receipt.update(row.random_seed.to_le_bytes());
        receipt.update(row.sample_index.to_le_bytes());
        receipt.update(row.absolute_step.to_le_bytes());
        receipt.update(row.degrees_of_freedom.to_le_bytes());
        receipt.update(row.kinetic_kcal_per_mol.to_bits().to_le_bytes());
        receipt.update(row.temperature_kelvin.to_bits().to_le_bytes());
    }
    receipt.update(summary.mean_kinetic_kcal_per_mol.to_bits().to_le_bytes());
    receipt.update(summary.mean_temperature_kelvin.to_bits().to_le_bytes());
    receipt.update(summary.temperature_variance_kelvin2.to_bits().to_le_bytes());

    Ok(DevelopmentWaterBoxNvtEnsembleReportV1 {
        backend,
        observations,
        mean_kinetic_kcal_per_mol: summary.mean_kinetic_kcal_per_mol,
        mean_temperature_kelvin: summary.mean_temperature_kelvin,
        temperature_variance_kelvin2: summary.temperature_variance_kelvin2,
        observation_receipt_sha256: receipt.finalize().into(),
    })
}

/// Run the immutable constraint-residual successor to the repeated-seed NVT lane.
///
/// This retains the ordered residual distribution for a tiny synthetic CPU
/// fixture. It grants no production, scientific, molecular, performance, or
/// HIP-device authority.
pub fn observe_development_water_box_nvt_constraint_ensemble_v1(
    context: &Context,
) -> Result<DevelopmentWaterBoxNvtConstraintEnsembleReportV1> {
    require_cpu_backend(
        context,
        DEVELOPMENT_WATER_BOX_NVT_CONSTRAINT_RESIDUAL_V1_PROFILE_ID,
    )?;
    let (backend, observations) = collect_development_water_box_nvt_observations(
        context,
        |water_box, random_seed, sample_index, report| {
            let snapshot = water_box.snapshot()?;
            let (maximum_position_residual, maximum_radial_velocity_residual) =
                frozen_water_box_constraint_residuals(&snapshot)?;
            Ok(DevelopmentWaterBoxNvtConstraintObservationV1 {
                random_seed,
                sample_index,
                absolute_step: report.absolute_step,
                degrees_of_freedom: report.degrees_of_freedom,
                kinetic_kcal_per_mol: report.kinetic_kcal_per_mol,
                temperature_kelvin: report.temperature_kelvin,
                maximum_position_constraint_residual_angstrom: maximum_position_residual,
                maximum_radial_velocity_constraint_residual_angstrom_per_femtosecond:
                    maximum_radial_velocity_residual,
            })
        },
    )?;
    let summary = summarize_development_water_box_nvt(&observations, |row| {
        (row.kinetic_kcal_per_mol, row.temperature_kelvin)
    })?;
    let residual_summary = summarize_development_water_box_constraint_residuals(&observations)?;
    let mut receipt = Sha256::new();
    receipt.update(
        b"betelgeuze.engine_v2_native_water_box_nvt_constraint_residual_observation/1.0.0\0",
    );
    receipt.update(development_water_box_nvt_constraint_residual_v1_profile_sha256());
    receipt.update([nvt_backend_tag(backend)?]);
    receipt.update(u64::from(summary.observation_count).to_le_bytes());
    for row in &observations {
        receipt.update(row.random_seed.to_le_bytes());
        receipt.update(row.sample_index.to_le_bytes());
        receipt.update(row.absolute_step.to_le_bytes());
        receipt.update(row.degrees_of_freedom.to_le_bytes());
        receipt.update(row.kinetic_kcal_per_mol.to_bits().to_le_bytes());
        receipt.update(row.temperature_kelvin.to_bits().to_le_bytes());
        receipt.update(
            row.maximum_position_constraint_residual_angstrom
                .to_bits()
                .to_le_bytes(),
        );
        receipt.update(
            row.maximum_radial_velocity_constraint_residual_angstrom_per_femtosecond
                .to_bits()
                .to_le_bytes(),
        );
    }
    receipt.update(summary.mean_kinetic_kcal_per_mol.to_bits().to_le_bytes());
    receipt.update(summary.mean_temperature_kelvin.to_bits().to_le_bytes());
    receipt.update(summary.temperature_variance_kelvin2.to_bits().to_le_bytes());
    receipt.update(
        residual_summary
            .mean_position_constraint_residual_angstrom
            .to_bits()
            .to_le_bytes(),
    );
    receipt.update(
        residual_summary
            .maximum_position_constraint_residual_angstrom
            .to_bits()
            .to_le_bytes(),
    );
    receipt.update(
        residual_summary
            .mean_radial_velocity_constraint_residual_angstrom_per_femtosecond
            .to_bits()
            .to_le_bytes(),
    );
    receipt.update(
        residual_summary
            .maximum_radial_velocity_constraint_residual_angstrom_per_femtosecond
            .to_bits()
            .to_le_bytes(),
    );

    Ok(DevelopmentWaterBoxNvtConstraintEnsembleReportV1 {
        backend,
        observations,
        mean_kinetic_kcal_per_mol: summary.mean_kinetic_kcal_per_mol,
        mean_temperature_kelvin: summary.mean_temperature_kelvin,
        temperature_variance_kelvin2: summary.temperature_variance_kelvin2,
        mean_position_constraint_residual_angstrom: residual_summary
            .mean_position_constraint_residual_angstrom,
        maximum_position_constraint_residual_angstrom: residual_summary
            .maximum_position_constraint_residual_angstrom,
        mean_radial_velocity_constraint_residual_angstrom_per_femtosecond: residual_summary
            .mean_radial_velocity_constraint_residual_angstrom_per_femtosecond,
        maximum_radial_velocity_constraint_residual_angstrom_per_femtosecond: residual_summary
            .maximum_radial_velocity_constraint_residual_angstrom_per_femtosecond,
        observation_receipt_sha256: receipt.finalize().into(),
    })
}

fn collect_development_water_box_nvt_observations<T>(
    context: &Context,
    mut capture: impl FnMut(&DevelopmentWaterBoxV1, u64, u32, DynamicsReport) -> Result<T>,
) -> Result<(Backend, Vec<T>)> {
    let backend = context.backend()?;
    let mut observations = Vec::with_capacity(NVT_ENSEMBLE_SEEDS.len() * NVT_ENSEMBLE_SAMPLE_COUNT);
    for random_seed in NVT_ENSEMBLE_SEEDS {
        let mut water_box = DevelopmentWaterBoxV1::new(
            SimulationOptions {
                integrator: Integrator::LangevinBaoab,
                timestep_femtoseconds: NVT_ENSEMBLE_TIMESTEP_FEMTOSECONDS,
                temperature_kelvin: TEMPERATURE_KELVIN,
                friction_per_femtosecond: NVT_ENSEMBLE_FRICTION_PER_FEMTOSECOND,
                random_seed,
            },
            true,
        )?;
        let burn_in = water_box.integrate(context, NVT_ENSEMBLE_BURN_IN_STEPS)?;
        if burn_in.absolute_step != NVT_ENSEMBLE_BURN_IN_STEPS || burn_in.degrees_of_freedom != 12 {
            return Err(invalid(
                "NVT ensemble burn-in returned an invalid step or degree-of-freedom count",
            ));
        }
        for sample_index in 0..NVT_ENSEMBLE_SAMPLE_COUNT {
            let report = water_box.integrate(context, NVT_ENSEMBLE_SAMPLE_STRIDE_STEPS)?;
            let sample_index_u64 = u64::try_from(sample_index)
                .map_err(|_| invalid("NVT ensemble sample index exceeds u64"))?;
            let sample_index_u32 = u32::try_from(sample_index)
                .map_err(|_| invalid("NVT ensemble sample index exceeds u32"))?;
            let expected_step = NVT_ENSEMBLE_BURN_IN_STEPS
                + (sample_index_u64 + 1) * NVT_ENSEMBLE_SAMPLE_STRIDE_STEPS;
            if report.absolute_step != expected_step
                || report.degrees_of_freedom != 12
                || !report.kinetic_kcal_per_mol.is_finite()
                || report.kinetic_kcal_per_mol <= 0.0
                || !report.temperature_kelvin.is_finite()
                || report.temperature_kelvin <= 0.0
            {
                return Err(invalid("NVT ensemble sample is incomplete or non-finite"));
            }
            observations.push(capture(&water_box, random_seed, sample_index_u32, report)?);
        }
    }
    Ok((backend, observations))
}

fn summarize_development_water_box_nvt<T>(
    observations: &[T],
    values: impl Fn(&T) -> (f64, f64),
) -> Result<DevelopmentWaterBoxNvtSummary> {
    let observation_count = u32::try_from(observations.len())
        .map_err(|_| invalid("NVT ensemble observation count exceeds u32"))?;
    if observation_count == 0 {
        return Err(invalid("NVT ensemble returned no observations"));
    }
    let count = f64::from(observation_count);
    let mean_kinetic_kcal_per_mol =
        observations.iter().map(|row| values(row).0).sum::<f64>() / count;
    let mean_temperature_kelvin = observations.iter().map(|row| values(row).1).sum::<f64>() / count;
    let temperature_variance_kelvin2 = observations
        .iter()
        .map(|row| {
            let delta = values(row).1 - mean_temperature_kelvin;
            delta * delta
        })
        .sum::<f64>()
        / count;
    if !(240.0..=360.0).contains(&mean_temperature_kelvin)
        || !mean_kinetic_kcal_per_mol.is_finite()
        || mean_kinetic_kcal_per_mol <= 0.0
        || !temperature_variance_kelvin2.is_finite()
        || temperature_variance_kelvin2 <= 0.0
    {
        return Err(invalid(
            "NVT ensemble development distribution is outside the frozen bounds",
        ));
    }

    Ok(DevelopmentWaterBoxNvtSummary {
        observation_count,
        mean_kinetic_kcal_per_mol,
        mean_temperature_kelvin,
        temperature_variance_kelvin2,
    })
}

fn summarize_development_water_box_constraint_residuals(
    observations: &[DevelopmentWaterBoxNvtConstraintObservationV1],
) -> Result<DevelopmentWaterBoxConstraintResidualSummary> {
    let observation_count = u32::try_from(observations.len())
        .map_err(|_| invalid("NVT constraint observation count exceeds u32"))?;
    if observation_count == 0 {
        return Err(invalid("NVT constraint ensemble returned no observations"));
    }
    if observations.iter().any(|row| {
        !row.maximum_position_constraint_residual_angstrom
            .is_finite()
            || row.maximum_position_constraint_residual_angstrom < 0.0
            || !row
                .maximum_radial_velocity_constraint_residual_angstrom_per_femtosecond
                .is_finite()
            || row.maximum_radial_velocity_constraint_residual_angstrom_per_femtosecond < 0.0
    }) {
        return Err(invalid(
            "NVT constraint distribution contains an invalid residual",
        ));
    }
    let count = f64::from(observation_count);
    let mean_position_constraint_residual_angstrom = observations
        .iter()
        .map(|row| row.maximum_position_constraint_residual_angstrom)
        .sum::<f64>()
        / count;
    let maximum_position_constraint_residual_angstrom = observations
        .iter()
        .map(|row| row.maximum_position_constraint_residual_angstrom)
        .fold(0.0, f64::max);
    let mean_radial_velocity_constraint_residual_angstrom_per_femtosecond = observations
        .iter()
        .map(|row| row.maximum_radial_velocity_constraint_residual_angstrom_per_femtosecond)
        .sum::<f64>()
        / count;
    let maximum_radial_velocity_constraint_residual_angstrom_per_femtosecond = observations
        .iter()
        .map(|row| row.maximum_radial_velocity_constraint_residual_angstrom_per_femtosecond)
        .fold(0.0, f64::max);
    if maximum_position_constraint_residual_angstrom > CONSTRAINT_TOLERANCE_ANGSTROM
        || maximum_radial_velocity_constraint_residual_angstrom_per_femtosecond
            > CONSTRAINT_VELOCITY_TOLERANCE_ANGSTROM_PER_FEMTOSECOND
    {
        return Err(invalid(
            "NVT constraint distribution is outside the frozen residual bounds",
        ));
    }
    Ok(DevelopmentWaterBoxConstraintResidualSummary {
        mean_position_constraint_residual_angstrom,
        maximum_position_constraint_residual_angstrom,
        mean_radial_velocity_constraint_residual_angstrom_per_femtosecond,
        maximum_radial_velocity_constraint_residual_angstrom_per_femtosecond,
    })
}

fn nvt_backend_tag(backend: Backend) -> Result<u8> {
    match backend {
        Backend::CppCpuReference => Ok(1_u8),
        Backend::RustCpu => Ok(2_u8),
        Backend::Auto | Backend::HipFast | Backend::HipSafe => Err(invalid(
            "NVT ensemble CPU guard admitted an unsupported backend",
        )),
    }
}

fn frozen_water_box_constraint_residuals(snapshot: &ParticleSnapshot) -> Result<(f64, f64)> {
    let expected_count = DEVELOPMENT_WATER_BOX_V1_ATOM_COUNT;
    let channel_lengths = [
        snapshot.len(),
        snapshot.positions.x_angstrom.len(),
        snapshot.positions.y_angstrom.len(),
        snapshot.positions.z_angstrom.len(),
        snapshot.velocities.x_angstrom_per_femtosecond.len(),
        snapshot.velocities.y_angstrom_per_femtosecond.len(),
        snapshot.velocities.z_angstrom_per_femtosecond.len(),
    ];
    if channel_lengths
        .iter()
        .any(|length| *length != expected_count)
    {
        return Err(invalid(
            "NVT constraint observation snapshot has an invalid channel shape",
        ));
    }
    let mut maximum_position_residual = 0.0_f64;
    let mut maximum_radial_velocity_residual = 0.0_f64;
    for (atom_i, atom_j, target_distance) in [
        (0, 1, OH_DISTANCE_ANGSTROM),
        (0, 2, OH_DISTANCE_ANGSTROM),
        (1, 2, HH_DISTANCE_ANGSTROM),
        (3, 4, OH_DISTANCE_ANGSTROM),
        (3, 5, OH_DISTANCE_ANGSTROM),
        (4, 5, HH_DISTANCE_ANGSTROM),
    ] {
        let displacement = [
            snapshot.positions.x_angstrom[atom_j] - snapshot.positions.x_angstrom[atom_i],
            snapshot.positions.y_angstrom[atom_j] - snapshot.positions.y_angstrom[atom_i],
            snapshot.positions.z_angstrom[atom_j] - snapshot.positions.z_angstrom[atom_i],
        ];
        let relative_velocity = [
            snapshot.velocities.x_angstrom_per_femtosecond[atom_j]
                - snapshot.velocities.x_angstrom_per_femtosecond[atom_i],
            snapshot.velocities.y_angstrom_per_femtosecond[atom_j]
                - snapshot.velocities.y_angstrom_per_femtosecond[atom_i],
            snapshot.velocities.z_angstrom_per_femtosecond[atom_j]
                - snapshot.velocities.z_angstrom_per_femtosecond[atom_i],
        ];
        let distance = displacement
            .iter()
            .map(|value| value * value)
            .sum::<f64>()
            .sqrt();
        if !distance.is_finite() || distance <= 0.0 {
            return Err(invalid(
                "NVT constraint observation contains a degenerate distance",
            ));
        }
        let position_residual = (distance - target_distance).abs();
        let radial_velocity_residual = displacement
            .iter()
            .zip(relative_velocity)
            .map(|(left, right)| left * right)
            .sum::<f64>()
            .abs()
            / distance;
        if !position_residual.is_finite() || !radial_velocity_residual.is_finite() {
            return Err(invalid(
                "NVT constraint observation contains a non-finite residual",
            ));
        }
        maximum_position_residual = maximum_position_residual.max(position_residual);
        maximum_radial_velocity_residual =
            maximum_radial_velocity_residual.max(radial_velocity_residual);
    }
    Ok((maximum_position_residual, maximum_radial_velocity_residual))
}

#[cfg(test)]
mod tests {
    use super::{CHARGE_ELEMENTARY, HH_DISTANCE_ANGSTROM, OH_DISTANCE_ANGSTROM};
    use crate as runtime;
    use sha2::{Digest, Sha256};

    const TOLERANCE: f64 = 2.0e-11;
    const BAOAB_SEED: u64 = 0x42d0_3301_a5a5_0101;

    #[test]
    fn frozen_single_water_matches_across_cpu_backends() {
        let cpp = runtime::Context::new(runtime::ContextOptions::cpu_reference()).unwrap();
        let rust = runtime::Context::new(runtime::ContextOptions::rust_cpu()).unwrap();
        let cpp_evaluation = runtime::evaluate_development_single_water_v1(&cpp).unwrap();
        let rust_evaluation = runtime::evaluate_development_single_water_v1(&rust).unwrap();

        assert!(cpp_evaluation.energy.total_kcal_per_mol.abs() < 1.0e-24);
        assert_evaluation_close(&cpp_evaluation, &rust_evaluation, TOLERANCE);
    }

    #[test]
    fn frozen_water_ion_catalog_is_exact_and_rejects_unsupported_identities() {
        assert_eq!(
            runtime::DEVELOPMENT_WATER_ION_V1_SCHEMA_ID,
            "betelgeuze.engine_v2_native_water_ion_profile/1.0.0"
        );
        assert_eq!(
            runtime::DEVELOPMENT_WATER_ION_V1_PROFILE_ID,
            "engine_v2_native_tip3p_nacl_development_v1"
        );
        assert_eq!(
            runtime::DEVELOPMENT_WATER_ION_V1_PARAMETER_SOURCE_DOI,
            "10.1021/jp8001614"
        );
        assert_eq!(
            runtime::development_water_ion_v1_profile_sha256(),
            [
                0x40, 0x99, 0x02, 0xe5, 0xf6, 0x77, 0x6b, 0xd5, 0x8c, 0x76, 0xf8, 0x0a, 0x57, 0x2c,
                0x9c, 0xf9, 0x78, 0xf7, 0xe2, 0xf4, 0x93, 0x80, 0x03, 0xe5, 0x60, 0x90, 0x36, 0xbf,
                0xe9, 0x1c, 0x63, 0x1f,
            ]
        );

        let sodium =
            runtime::development_ion_parameters_v1(runtime::DevelopmentIonIdentityV1::SODIUM)
                .unwrap();
        assert_eq!(sodium.species, runtime::DevelopmentIonSpeciesV1::Sodium);
        assert_eq!(sodium.charge_elementary.to_bits(), 1.0f64.to_bits());
        assert_eq!(sodium.mass_dalton.to_bits(), 22.99f64.to_bits());
        assert_eq!(sodium.rmin_over_2_angstrom.to_bits(), 1.369f64.to_bits());
        assert_eq!(sodium.sigma_angstrom.to_bits(), 0x4003_83a5_9833_bb42);
        assert_eq!(sodium.epsilon_kcal_per_mol.to_bits(), 0x3fb6_626c_05e2_9810);
        let converted_sodium_sigma = 2.0 * sodium.rmin_over_2_angstrom / 2.0f64.powf(1.0 / 6.0);
        assert!((converted_sodium_sigma - sodium.sigma_angstrom).abs() <= 1.0e-15);

        let chloride =
            runtime::development_ion_parameters_v1(runtime::DevelopmentIonIdentityV1::CHLORIDE)
                .unwrap();
        assert_eq!(chloride.species, runtime::DevelopmentIonSpeciesV1::Chloride);
        assert_eq!(chloride.charge_elementary.to_bits(), (-1.0f64).to_bits());
        assert_eq!(chloride.mass_dalton.to_bits(), 35.45f64.to_bits());
        assert_eq!(chloride.rmin_over_2_angstrom.to_bits(), 2.513f64.to_bits());
        assert_eq!(chloride.sigma_angstrom.to_bits(), 0x4011_e91e_e7ca_8064);
        assert_eq!(
            chloride.epsilon_kcal_per_mol.to_bits(),
            0x3fa2_38fb_ca10_59ea
        );
        let converted_chloride_sigma = 2.0 * chloride.rmin_over_2_angstrom / 2.0f64.powf(1.0 / 6.0);
        assert!((converted_chloride_sigma - chloride.sigma_angstrom).abs() <= 1.0e-15);
        assert_eq!(
            CHARGE_ELEMENTARY.iter().sum::<f64>()
                + sodium.charge_elementary
                + chloride.charge_elementary,
            0.0
        );

        for identity in [
            runtime::DevelopmentIonIdentityV1::new(11, 0),
            runtime::DevelopmentIonIdentityV1::new(19, 1),
        ] {
            assert_eq!(
                runtime::development_ion_parameters_v1(identity),
                Err(runtime::DevelopmentIonParameterErrorV1::UnsupportedIdentity(identity))
            );
        }
    }

    #[test]
    fn frozen_neutral_water_ion_fixture_matches_across_cpu_backends() {
        let cpp = runtime::Context::new(runtime::ContextOptions::cpu_reference()).unwrap();
        let rust = runtime::Context::new(runtime::ContextOptions::rust_cpu()).unwrap();
        let cpp_result = runtime::evaluate_development_water_ion_v1(&cpp).unwrap();
        let rust_result = runtime::evaluate_development_water_ion_v1(&rust).unwrap();
        assert_eq!(cpp_result.energy, rust_result.energy);
        assert_eq!(cpp_result.forces, rust_result.forces);
        assert_eq!(
            cpp_result.forces.x_kcal_per_mol_angstrom.len(),
            runtime::DEVELOPMENT_WATER_ION_V1_ATOM_COUNT
        );
        assert!(cpp_result.energy.total_kcal_per_mol.is_finite());
        assert!(cpp_result
            .forces
            .x_kcal_per_mol_angstrom
            .iter()
            .chain(&cpp_result.forces.y_kcal_per_mol_angstrom)
            .chain(&cpp_result.forces.z_kcal_per_mol_angstrom)
            .all(|value| value.is_finite()));
    }

    #[test]
    fn constrained_water_ion_dynamics_is_cpu_parity_complete_and_checkpoint_exact() {
        assert_eq!(
            runtime::DEVELOPMENT_WATER_ION_DYNAMICS_V1_SCHEMA_ID,
            "betelgeuze.engine_v2_native_water_ion_dynamics_profile/1.0.0"
        );
        assert_eq!(
            runtime::DEVELOPMENT_WATER_ION_DYNAMICS_V1_PROFILE_ID,
            "engine_v2_native_tip3p_nacl_constrained_dynamics_development_v1"
        );
        assert_eq!(
            runtime::development_water_ion_dynamics_v1_profile_sha256(),
            [
                0xad, 0x00, 0x9e, 0x5a, 0x60, 0xc0, 0x7d, 0xcc, 0xf2, 0xd6, 0xc5, 0x0e, 0x76, 0xd7,
                0x3a, 0xa9, 0xc8, 0x20, 0x62, 0x01, 0xae, 0x1b, 0xab, 0x7c, 0x58, 0x5b, 0x63, 0x64,
                0x1d, 0xf0, 0x98, 0xe3,
            ]
        );

        let cpp = runtime::Context::new(runtime::ContextOptions::cpu_reference()).unwrap();
        let rust = runtime::Context::new(runtime::ContextOptions::rust_cpu()).unwrap();
        let mut cpp_system = runtime::DevelopmentWaterIonDynamicsV1::constrained_nve().unwrap();
        let mut rust_system = runtime::DevelopmentWaterIonDynamicsV1::constrained_nve().unwrap();
        let initial = rust_system.snapshot().unwrap();
        for ion_index in [6, 7] {
            assert_eq!(
                initial.velocities.x_angstrom_per_femtosecond[ion_index].to_bits(),
                0.0f64.to_bits()
            );
            assert_eq!(
                initial.velocities.y_angstrom_per_femtosecond[ion_index].to_bits(),
                0.0f64.to_bits()
            );
            assert_eq!(
                initial.velocities.z_angstrom_per_femtosecond[ion_index].to_bits(),
                0.0f64.to_bits()
            );
        }

        let cpp_report = cpp_system.integrate(&cpp, 100).unwrap();
        let rust_report = rust_system.integrate(&rust, 100).unwrap();
        assert_eq!(cpp_report, rust_report);
        assert_eq!(rust_report.steps_completed, 100);
        assert_eq!(rust_report.absolute_step, 100);
        assert_eq!(rust_report.degrees_of_freedom, 18);
        assert!(rust_report.total_kcal_per_mol.is_finite());
        assert!(rust_report.kinetic_kcal_per_mol.is_finite());
        assert!(rust_report.potential_kcal_per_mol.is_finite());
        let cpp_snapshot = cpp_system.snapshot().unwrap();
        let rust_snapshot = rust_system.snapshot().unwrap();
        assert_snapshot_bits_equal(&cpp_snapshot, &rust_snapshot);
        assert!(rust_snapshot
            .positions
            .x_angstrom
            .iter()
            .chain(&rust_snapshot.positions.y_angstrom)
            .chain(&rust_snapshot.positions.z_angstrom)
            .chain(&rust_snapshot.velocities.x_angstrom_per_femtosecond)
            .chain(&rust_snapshot.velocities.y_angstrom_per_femtosecond)
            .chain(&rust_snapshot.velocities.z_angstrom_per_femtosecond)
            .chain(&rust_snapshot.mass_dalton)
            .chain(&rust_snapshot.charge_elementary)
            .all(|value| value.is_finite()));
        assert_constraint_residuals(&rust_snapshot, 1.0e-10);
        for ion_index in [6, 7] {
            assert!(
                initial.positions.x_angstrom[ion_index].to_bits()
                    != rust_snapshot.positions.x_angstrom[ion_index].to_bits()
                    || initial.positions.y_angstrom[ion_index].to_bits()
                        != rust_snapshot.positions.y_angstrom[ion_index].to_bits()
                    || initial.positions.z_angstrom[ion_index].to_bits()
                        != rust_snapshot.positions.z_angstrom[ion_index].to_bits()
            );
        }

        let checkpoint = rust_system.checkpoint().unwrap();
        assert_eq!(checkpoint, rust_system.checkpoint().unwrap());
        let mut restarted = runtime::DevelopmentWaterIonDynamicsV1::constrained_nve().unwrap();
        restarted.load_checkpoint(&checkpoint).unwrap();
        assert_eq!(restarted.absolute_step().unwrap(), 100);
        assert_snapshot_bits_equal(&rust_snapshot, &restarted.snapshot().unwrap());
        let continued = rust_system.integrate(&rust, 32).unwrap();
        let restarted_report = restarted.integrate(&rust, 32).unwrap();
        assert_eq!(continued, restarted_report);
        assert_eq!(continued.absolute_step, 132);
        assert_snapshot_bits_equal(
            &rust_system.snapshot().unwrap(),
            &restarted.snapshot().unwrap(),
        );
        assert_constraint_residuals(&restarted.snapshot().unwrap(), 1.0e-10);
    }

    #[test]
    fn dynamics_failure_matrix_is_ordered_typed_and_honest_about_oom() {
        assert_eq!(
            runtime::DEVELOPMENT_WATER_BOX_DYNAMICS_FAILURE_V1_SCHEMA_ID,
            "betelgeuze.engine_v2_native_water_box_dynamics_failure_profile/1.0.0"
        );
        assert_eq!(
            runtime::DEVELOPMENT_WATER_BOX_DYNAMICS_FAILURE_V1_PROFILE_ID,
            "engine_v2_native_water_box_dynamics_failure_matrix_development_v1"
        );
        assert_eq!(
            runtime::development_water_box_dynamics_failure_v1_profile_sha256(),
            [
                0xe6, 0xfe, 0xf1, 0x89, 0x52, 0xef, 0x81, 0x3b, 0x3f, 0x2e, 0x96, 0xb1, 0x61, 0x4e,
                0x7b, 0x92, 0x15, 0xf6, 0x2f, 0x03, 0x2b, 0x1a, 0xbd, 0xa9, 0x2b, 0x4a, 0x2d, 0x13,
                0xd4, 0x53, 0xe6, 0xd0,
            ]
        );

        let cpp = runtime::Context::new(runtime::ContextOptions::cpu_reference()).unwrap();
        let rust = runtime::Context::new(runtime::ContextOptions::rust_cpu()).unwrap();
        let cpp_report = runtime::observe_development_water_box_dynamics_failures_v1(&cpp).unwrap();
        let repeated = runtime::observe_development_water_box_dynamics_failures_v1(&cpp).unwrap();
        let rust_report =
            runtime::observe_development_water_box_dynamics_failures_v1(&rust).unwrap();
        assert_eq!(cpp_report, repeated);
        assert_eq!(cpp_report.rows, rust_report.rows);
        assert_ne!(
            cpp_report.observation_receipt_sha256,
            rust_report.observation_receipt_sha256
        );
        assert!(cpp_report.all_required_failure_classes_typed);
        assert!(!cpp_report.all_required_failure_classes_runtime_exercised);
        assert!(!cpp_report.oom_allocation_attempted);
        assert_eq!(
            cpp_report
                .rows
                .iter()
                .map(|row| row.case_id)
                .collect::<Vec<_>>(),
            vec![
                "nonfinite_particle_position",
                "linearly_dependent_constraint_jacobian",
                "absolute_step_uint64_overflow",
                "out_of_memory_status_mapping",
                "unsupported_ion_identity",
            ]
        );
        assert_eq!(
            cpp_report
                .rows
                .iter()
                .map(|row| row.failure_code)
                .collect::<Vec<_>>(),
            vec![
                runtime::DevelopmentDynamicsFailureCodeV1::InvalidArgument,
                runtime::DevelopmentDynamicsFailureCodeV1::InvalidArgument,
                runtime::DevelopmentDynamicsFailureCodeV1::CapacityOverflow,
                runtime::DevelopmentDynamicsFailureCodeV1::OutOfMemory,
                runtime::DevelopmentDynamicsFailureCodeV1::UnsupportedIonIdentity,
            ]
        );
        assert_eq!(
            cpp_report
                .rows
                .iter()
                .map(|row| row.evidence_kind)
                .collect::<Vec<_>>(),
            vec![
                runtime::DevelopmentDynamicsFailureEvidenceV1::SafeWrapperRejection,
                runtime::DevelopmentDynamicsFailureEvidenceV1::NativeRuntimeRejection,
                runtime::DevelopmentDynamicsFailureEvidenceV1::SafeWrapperCapacityPreflight,
                runtime::DevelopmentDynamicsFailureEvidenceV1::StatusMappingOnly,
                runtime::DevelopmentDynamicsFailureEvidenceV1::DomainCatalogRejection,
            ]
        );
        assert_eq!(
            cpp_report
                .rows
                .iter()
                .map(|row| row.failure_attempted)
                .collect::<Vec<_>>(),
            vec![true, true, true, false, true]
        );
        assert_eq!(
            cpp_report
                .rows
                .iter()
                .map(|row| row.state_preserved)
                .collect::<Vec<_>>(),
            vec![None, None, Some(true), None, None]
        );
        assert_eq!(
            cpp_report.rows[0].message,
            "position SoA channels must contain only finite values"
        );
        assert_eq!(
            cpp_report.rows[1].message,
            "constraint Jacobian rows are linearly dependent"
        );
        assert_eq!(
            cpp_report.rows[2].message,
            "absolute dynamics step would overflow uint64"
        );
        assert!(cpp_report.rows[3]
            .message
            .contains("allocation not attempted"));
        assert_eq!(
            cpp_report.rows[4].message,
            "unsupported development ion identity: atomic_number=19, formal_charge=1"
        );
        assert_eq!(
            cpp_report.observation_receipt_sha256,
            independently_hash_failure_report(&cpp_report)
        );
        assert_eq!(
            rust_report.observation_receipt_sha256,
            independently_hash_failure_report(&rust_report)
        );
    }

    #[test]
    fn dynamics_failure_boundary_successor_is_frozen_without_allocator_authority() {
        assert_eq!(
            runtime::DEVELOPMENT_WATER_BOX_DYNAMICS_FAILURE_V2_SCHEMA_ID,
            "betelgeuze.engine_v2_native_water_box_dynamics_failure_profile/2.0.0"
        );
        assert_eq!(
            runtime::DEVELOPMENT_WATER_BOX_DYNAMICS_FAILURE_V2_PROFILE_ID,
            "engine_v2_native_water_box_dynamics_failure_boundary_development_v2"
        );
        assert_eq!(
            runtime::development_water_box_dynamics_failure_v2_profile_sha256(),
            [
                0x0b, 0xf2, 0x09, 0xeb, 0x62, 0x28, 0x7f, 0x82, 0x08, 0x0a, 0x12, 0x3d, 0x7f, 0x48,
                0xe8, 0xc6, 0x32, 0x61, 0xd7, 0xa3, 0x70, 0x28, 0x31, 0x12, 0xe1, 0xaf, 0x95, 0xca,
                0x5e, 0x47, 0x57, 0xbe,
            ]
        );
        assert_eq!(
            runtime::ErrorCode::from_raw(betelgeuze_sys::BG_STATUS_OUT_OF_MEMORY),
            Some(runtime::ErrorCode::OutOfMemory)
        );
    }

    #[test]
    fn native_exception_boundary_matrix_is_frozen_without_product_hook() {
        assert_eq!(
            runtime::DEVELOPMENT_WATER_BOX_DYNAMICS_FAILURE_V3_SCHEMA_ID,
            "betelgeuze.engine_v2_native_water_box_dynamics_failure_profile/3.0.0"
        );
        assert_eq!(
            runtime::DEVELOPMENT_WATER_BOX_DYNAMICS_FAILURE_V3_PROFILE_ID,
            "engine_v2_native_exception_boundary_matrix_development_v3"
        );
        assert_eq!(
            runtime::development_water_box_dynamics_failure_v3_profile_sha256(),
            [
                0xb0, 0xf7, 0x3f, 0x13, 0x64, 0x89, 0xcb, 0xdc, 0x17, 0xc5, 0x5b, 0xe0, 0xf8, 0x2d,
                0x16, 0xb4, 0xcf, 0xd5, 0xdd, 0x32, 0x18, 0x37, 0x3a, 0x0d, 0x2c, 0x4a, 0x31, 0x0c,
                0x98, 0x84, 0xf3, 0x2c,
            ]
        );
        assert_eq!(
            runtime::ErrorCode::from_raw(betelgeuze_sys::BG_STATUS_CAPACITY_OVERFLOW),
            Some(runtime::ErrorCode::CapacityOverflow)
        );
        assert_eq!(
            runtime::ErrorCode::from_raw(betelgeuze_sys::BG_STATUS_OUT_OF_MEMORY),
            Some(runtime::ErrorCode::OutOfMemory)
        );
        assert_eq!(
            runtime::ErrorCode::from_raw(betelgeuze_sys::BG_STATUS_INTERNAL_ERROR),
            Some(runtime::ErrorCode::InternalError)
        );
    }

    #[test]
    fn frozen_initial_water_box_matches_across_cpu_backends() {
        assert_eq!(runtime::DEVELOPMENT_WATER_BOX_V1_ATOM_COUNT, 6);
        assert_eq!(
            runtime::DEVELOPMENT_WATER_BOX_V1_SCHEMA_ID,
            "betelgeuze.engine_v2_native_water_box/1.0.0"
        );
        assert_eq!(
            runtime::DEVELOPMENT_WATER_BOX_V1_PROFILE_ID,
            "engine_v2_native_two_water_development_v1"
        );
        assert_eq!(
            runtime::development_water_box_v1_profile_sha256(),
            [
                0x2b, 0x0b, 0xe8, 0x3b, 0x57, 0x08, 0x5c, 0x65, 0x50, 0x92, 0xab, 0x02, 0x72, 0xae,
                0xa5, 0xa9, 0x1b, 0x9c, 0x3f, 0x90, 0xc3, 0x44, 0xfa, 0x06, 0x2d, 0x49, 0x4a, 0xd3,
                0x24, 0xf0, 0x01, 0x9e,
            ]
        );
        assert_eq!(
            runtime::NATIVE_PERIODIC_NEIGHBOR_LIST_V1_SCHEMA_ID,
            "betelgeuze.engine_v2_native_periodic_neighbor_list_profile/1.0.0"
        );
        assert_eq!(
            runtime::NATIVE_PERIODIC_NEIGHBOR_LIST_V1_PROFILE_ID,
            "engine_v2_native_periodic_cpu_cell_list_development_v1"
        );
        assert_eq!(
            runtime::native_periodic_neighbor_list_v1_profile_sha256(),
            [
                0xee, 0x2c, 0x64, 0xb3, 0xe4, 0x0e, 0xc1, 0x90, 0x5a, 0x97, 0xb0, 0xc2, 0x64, 0x6e,
                0x36, 0xc5, 0x9f, 0xe3, 0x0f, 0x67, 0x4a, 0xdf, 0xd0, 0x19, 0xdd, 0xe0, 0x16, 0xe2,
                0x63, 0x7e, 0x36, 0x28,
            ]
        );
        assert_eq!(
            runtime::NATIVE_PERIODIC_NEIGHBOR_LIST_V2_SCHEMA_ID,
            "betelgeuze.engine_v2_native_periodic_neighbor_list_profile/2.0.0"
        );
        assert_eq!(
            runtime::NATIVE_PERIODIC_NEIGHBOR_LIST_V2_PROFILE_ID,
            "engine_v2_native_periodic_cpu_neighbor_cache_development_v2"
        );
        assert_eq!(
            runtime::native_periodic_neighbor_list_v2_profile_sha256(),
            [
                0xc9, 0xe6, 0x71, 0xb9, 0x25, 0xb8, 0xf5, 0xda, 0x48, 0xa4, 0x3d, 0xec, 0x2a, 0xbe,
                0x26, 0x4e, 0x69, 0x58, 0x40, 0xb2, 0x77, 0xcc, 0x3c, 0xf4, 0xa8, 0x4a, 0xa7, 0x25,
                0x5b, 0x59, 0x15, 0x0d,
            ]
        );

        let cpp = runtime::Context::new(runtime::ContextOptions::cpu_reference()).unwrap();
        let rust = runtime::Context::new(runtime::ContextOptions::rust_cpu()).unwrap();
        let cpp_evaluation = runtime::evaluate_development_water_box_v1(&cpp).unwrap();
        let rust_evaluation = runtime::evaluate_development_water_box_v1(&rust).unwrap();

        assert_close(
            cpp_evaluation.energy.total_kcal_per_mol,
            -2.235452238349433,
            TOLERANCE,
        );
        assert_evaluation_close(&cpp_evaluation, &rust_evaluation, TOLERANCE);
    }

    #[test]
    fn frozen_nve_is_cpu_parity_complete_and_checkpoint_exact() {
        let cpp = runtime::Context::new(runtime::ContextOptions::cpu_reference()).unwrap();
        let rust = runtime::Context::new(runtime::ContextOptions::rust_cpu()).unwrap();
        let mut cpp_box = runtime::DevelopmentWaterBoxV1::nve().unwrap();
        let mut rust_box = runtime::DevelopmentWaterBoxV1::nve().unwrap();

        let cpp_report = cpp_box.integrate(&cpp, 100).unwrap();
        let rust_report = rust_box.integrate(&rust, 100).unwrap();
        assert_eq!(cpp_report.steps_completed, 100);
        assert_eq!(cpp_report.absolute_step, 100);
        assert_eq!(cpp_report.degrees_of_freedom, 18);
        assert_close(cpp_report.total_kcal_per_mol, -2.235428271468032, TOLERANCE);
        assert_report_close(cpp_report, rust_report, TOLERANCE);
        assert_snapshot_close(
            &cpp_box.snapshot().unwrap(),
            &rust_box.snapshot().unwrap(),
            TOLERANCE,
        );

        let checkpoint = rust_box.checkpoint().unwrap();
        assert_eq!(checkpoint, rust_box.checkpoint().unwrap());
        let mut restarted = runtime::DevelopmentWaterBoxV1::nve().unwrap();
        restarted.load_checkpoint(&checkpoint).unwrap();
        assert_snapshot_bits_equal(
            &rust_box.snapshot().unwrap(),
            &restarted.snapshot().unwrap(),
        );
        let continued = rust_box.integrate(&rust, 32).unwrap();
        let restarted_report = restarted.integrate(&rust, 32).unwrap();
        assert_eq!(continued, restarted_report);
        assert_snapshot_bits_equal(
            &rust_box.snapshot().unwrap(),
            &restarted.snapshot().unwrap(),
        );
    }

    #[test]
    fn frozen_baoab_is_seed_repeatable_and_cpu_parity_complete() {
        let cpp = runtime::Context::new(runtime::ContextOptions::cpu_reference()).unwrap();
        let rust = runtime::Context::new(runtime::ContextOptions::rust_cpu()).unwrap();
        let mut cpp_box = runtime::DevelopmentWaterBoxV1::baoab(BAOAB_SEED).unwrap();
        let mut rust_box = runtime::DevelopmentWaterBoxV1::baoab(BAOAB_SEED).unwrap();
        let mut repeated = runtime::DevelopmentWaterBoxV1::baoab(BAOAB_SEED).unwrap();

        let cpp_report = cpp_box.integrate(&cpp, 128).unwrap();
        let rust_report = rust_box.integrate(&rust, 128).unwrap();
        let repeated_report = repeated.integrate(&rust, 128).unwrap();
        assert_eq!(rust_report, repeated_report);
        assert!(rust_report.temperature_kelvin.is_finite());
        assert!(rust_report.temperature_kelvin >= 0.0);
        assert_report_close(cpp_report, rust_report, TOLERANCE);
        assert_snapshot_close(
            &cpp_box.snapshot().unwrap(),
            &rust_box.snapshot().unwrap(),
            TOLERANCE,
        );
        assert_snapshot_bits_equal(&rust_box.snapshot().unwrap(), &repeated.snapshot().unwrap());
    }

    #[test]
    fn repeated_seed_nvt_distribution_is_frozen_repeatable_and_cpu_bounded() {
        assert_eq!(
            runtime::DEVELOPMENT_WATER_BOX_NVT_ENSEMBLE_V1_SCHEMA_ID,
            "betelgeuze.engine_v2_native_water_box_nvt_ensemble_profile/1.0.0"
        );
        assert_eq!(
            runtime::DEVELOPMENT_WATER_BOX_NVT_ENSEMBLE_V1_PROFILE_ID,
            "engine_v2_native_two_water_nvt_ensemble_development_v1"
        );
        assert_eq!(
            runtime::development_water_box_nvt_ensemble_v1_profile_sha256(),
            [
                0xbb, 0x25, 0x77, 0xc0, 0xe2, 0x27, 0x15, 0x1b, 0x8a, 0xa9, 0x5b, 0x5c, 0x28, 0x82,
                0x49, 0x82, 0x32, 0x06, 0x02, 0x05, 0x58, 0xa1, 0x86, 0xec, 0xcc, 0x8b, 0x5d, 0xdc,
                0xbc, 0xa8, 0x02, 0xde,
            ]
        );
        let cpp = runtime::Context::new(runtime::ContextOptions::cpu_reference()).unwrap();
        let rust = runtime::Context::new(runtime::ContextOptions::rust_cpu()).unwrap();
        let cpp_report = runtime::observe_development_water_box_nvt_ensemble_v1(&cpp).unwrap();
        let rust_report = runtime::observe_development_water_box_nvt_ensemble_v1(&rust).unwrap();
        let repeated = runtime::observe_development_water_box_nvt_ensemble_v1(&rust).unwrap();
        assert_eq!(rust_report, repeated);
        assert_eq!(cpp_report.observations, rust_report.observations);
        assert_eq!(
            cpp_report.mean_temperature_kelvin.to_bits(),
            rust_report.mean_temperature_kelvin.to_bits()
        );
        assert_eq!(
            cpp_report.temperature_variance_kelvin2.to_bits(),
            rust_report.temperature_variance_kelvin2.to_bits()
        );
        assert_eq!(
            cpp_report.mean_kinetic_kcal_per_mol.to_bits(),
            rust_report.mean_kinetic_kcal_per_mol.to_bits()
        );
        assert_eq!(cpp_report.observations.len(), 8 * 32);
        assert_eq!(rust_report.observations.len(), 8 * 32);
        for (backend, report) in [
            (runtime::Backend::CppCpuReference, &cpp_report),
            (runtime::Backend::RustCpu, &rust_report),
        ] {
            assert_eq!(report.backend, backend);
            assert!((240.0..=360.0).contains(&report.mean_temperature_kelvin));
            assert!(report.mean_kinetic_kcal_per_mol > 0.0);
            assert!(report.temperature_variance_kelvin2 > 0.0);
            for (index, row) in report.observations.iter().enumerate() {
                let seed_index = index / 32;
                let sample_index = index % 32;
                assert_eq!(
                    row.random_seed,
                    [101, 211, 307, 401, 503, 601, 701, 809][seed_index]
                );
                assert_eq!(row.sample_index, sample_index as u32);
                assert_eq!(row.absolute_step, 2_000 + (sample_index as u64 + 1) * 100);
                assert_eq!(row.degrees_of_freedom, 12);
                assert!(row.kinetic_kcal_per_mol > 0.0);
                assert!(row.temperature_kelvin > 0.0);
            }
            assert_eq!(
                report.observation_receipt_sha256,
                independently_recompute_nvt_observation_receipt(report)
            );
        }
        assert_ne!(
            cpp_report.observation_receipt_sha256,
            rust_report.observation_receipt_sha256
        );
    }

    #[test]
    fn repeated_seed_nvt_constraint_residual_distribution_is_retained_and_cpu_parity_complete() {
        assert_eq!(
            runtime::DEVELOPMENT_WATER_BOX_NVT_CONSTRAINT_RESIDUAL_V1_SCHEMA_ID,
            "betelgeuze.engine_v2_native_water_box_nvt_constraint_residual_profile/1.0.0"
        );
        assert_eq!(
            runtime::DEVELOPMENT_WATER_BOX_NVT_CONSTRAINT_RESIDUAL_V1_PROFILE_ID,
            "engine_v2_native_two_water_nvt_constraint_residual_development_v1"
        );
        assert_eq!(
            runtime::development_water_box_nvt_constraint_residual_v1_profile_sha256(),
            [
                0xa9, 0x20, 0x70, 0xad, 0xe1, 0xd2, 0x14, 0xe9, 0x52, 0x6a, 0x10, 0x16, 0x66, 0xb4,
                0x9e, 0x8a, 0x7d, 0x5b, 0x90, 0x98, 0x88, 0x29, 0x3b, 0x79, 0x43, 0x7c, 0xa8, 0x59,
                0xef, 0x4e, 0x7c, 0x35,
            ]
        );
        let cpp = runtime::Context::new(runtime::ContextOptions::cpu_reference()).unwrap();
        let rust = runtime::Context::new(runtime::ContextOptions::rust_cpu()).unwrap();
        let cpp_report =
            runtime::observe_development_water_box_nvt_constraint_ensemble_v1(&cpp).unwrap();
        let rust_report =
            runtime::observe_development_water_box_nvt_constraint_ensemble_v1(&rust).unwrap();
        let repeated =
            runtime::observe_development_water_box_nvt_constraint_ensemble_v1(&rust).unwrap();
        assert_eq!(rust_report, repeated);
        assert_eq!(cpp_report.observations, rust_report.observations);
        for (left, right) in [
            (
                cpp_report.mean_kinetic_kcal_per_mol,
                rust_report.mean_kinetic_kcal_per_mol,
            ),
            (
                cpp_report.mean_temperature_kelvin,
                rust_report.mean_temperature_kelvin,
            ),
            (
                cpp_report.temperature_variance_kelvin2,
                rust_report.temperature_variance_kelvin2,
            ),
            (
                cpp_report.mean_position_constraint_residual_angstrom,
                rust_report.mean_position_constraint_residual_angstrom,
            ),
            (
                cpp_report.maximum_position_constraint_residual_angstrom,
                rust_report.maximum_position_constraint_residual_angstrom,
            ),
            (
                cpp_report.mean_radial_velocity_constraint_residual_angstrom_per_femtosecond,
                rust_report.mean_radial_velocity_constraint_residual_angstrom_per_femtosecond,
            ),
            (
                cpp_report.maximum_radial_velocity_constraint_residual_angstrom_per_femtosecond,
                rust_report.maximum_radial_velocity_constraint_residual_angstrom_per_femtosecond,
            ),
        ] {
            assert_eq!(left.to_bits(), right.to_bits());
        }
        for (backend, report) in [
            (runtime::Backend::CppCpuReference, &cpp_report),
            (runtime::Backend::RustCpu, &rust_report),
        ] {
            assert_eq!(report.backend, backend);
            assert_eq!(report.observations.len(), 8 * 32);
            assert!(report.mean_position_constraint_residual_angstrom >= 0.0);
            assert!(report.maximum_position_constraint_residual_angstrom <= 1.0e-10);
            assert!(
                report.mean_radial_velocity_constraint_residual_angstrom_per_femtosecond >= 0.0
            );
            assert!(
                report.maximum_radial_velocity_constraint_residual_angstrom_per_femtosecond
                    <= 1.0e-10
            );
            for (index, row) in report.observations.iter().enumerate() {
                let seed_index = index / 32;
                let sample_index = index % 32;
                assert_eq!(
                    row.random_seed,
                    [101, 211, 307, 401, 503, 601, 701, 809][seed_index]
                );
                assert_eq!(row.sample_index, sample_index as u32);
                assert_eq!(row.absolute_step, 2_000 + (sample_index as u64 + 1) * 100);
                assert_eq!(row.degrees_of_freedom, 12);
                assert!(row
                    .maximum_position_constraint_residual_angstrom
                    .is_finite());
                assert!(row.maximum_position_constraint_residual_angstrom >= 0.0);
                assert!(row.maximum_position_constraint_residual_angstrom <= 1.0e-10);
                assert!(row
                    .maximum_radial_velocity_constraint_residual_angstrom_per_femtosecond
                    .is_finite());
                assert!(
                    row.maximum_radial_velocity_constraint_residual_angstrom_per_femtosecond >= 0.0
                );
                assert!(
                    row.maximum_radial_velocity_constraint_residual_angstrom_per_femtosecond
                        <= 1.0e-10
                );
            }
            assert_constraint_summary_rederived(report);
            assert_eq!(
                report.observation_receipt_sha256,
                independently_recompute_nvt_constraint_observation_receipt(report)
            );
        }
        assert_ne!(
            cpp_report.observation_receipt_sha256,
            rust_report.observation_receipt_sha256
        );
    }

    fn assert_constraint_summary_rederived(
        report: &runtime::DevelopmentWaterBoxNvtConstraintEnsembleReportV1,
    ) {
        let count = report.observations.len() as f64;
        let mean_kinetic = report
            .observations
            .iter()
            .map(|row| row.kinetic_kcal_per_mol)
            .sum::<f64>()
            / count;
        let mean_temperature = report
            .observations
            .iter()
            .map(|row| row.temperature_kelvin)
            .sum::<f64>()
            / count;
        let temperature_variance = report
            .observations
            .iter()
            .map(|row| {
                let delta = row.temperature_kelvin - mean_temperature;
                delta * delta
            })
            .sum::<f64>()
            / count;
        let mean_position = report
            .observations
            .iter()
            .map(|row| row.maximum_position_constraint_residual_angstrom)
            .sum::<f64>()
            / count;
        let maximum_position = report
            .observations
            .iter()
            .map(|row| row.maximum_position_constraint_residual_angstrom)
            .fold(0.0, f64::max);
        let mean_velocity = report
            .observations
            .iter()
            .map(|row| row.maximum_radial_velocity_constraint_residual_angstrom_per_femtosecond)
            .sum::<f64>()
            / count;
        let maximum_velocity = report
            .observations
            .iter()
            .map(|row| row.maximum_radial_velocity_constraint_residual_angstrom_per_femtosecond)
            .fold(0.0, f64::max);
        assert_eq!(
            mean_kinetic.to_bits(),
            report.mean_kinetic_kcal_per_mol.to_bits()
        );
        assert_eq!(
            mean_temperature.to_bits(),
            report.mean_temperature_kelvin.to_bits()
        );
        assert_eq!(
            temperature_variance.to_bits(),
            report.temperature_variance_kelvin2.to_bits()
        );
        assert_eq!(
            mean_position.to_bits(),
            report.mean_position_constraint_residual_angstrom.to_bits()
        );
        assert_eq!(
            maximum_position.to_bits(),
            report
                .maximum_position_constraint_residual_angstrom
                .to_bits()
        );
        assert_eq!(
            mean_velocity.to_bits(),
            report
                .mean_radial_velocity_constraint_residual_angstrom_per_femtosecond
                .to_bits()
        );
        assert_eq!(
            maximum_velocity.to_bits(),
            report
                .maximum_radial_velocity_constraint_residual_angstrom_per_femtosecond
                .to_bits()
        );
    }

    fn independently_recompute_nvt_constraint_observation_receipt(
        report: &runtime::DevelopmentWaterBoxNvtConstraintEnsembleReportV1,
    ) -> [u8; 32] {
        let backend_tag = match report.backend {
            runtime::Backend::CppCpuReference => 1_u8,
            runtime::Backend::RustCpu => 2_u8,
            other => panic!("unexpected NVT constraint observation backend: {other:?}"),
        };
        let mut receipt = Sha256::new();
        receipt.update(
            b"betelgeuze.engine_v2_native_water_box_nvt_constraint_residual_observation/1.0.0\0",
        );
        receipt.update(runtime::development_water_box_nvt_constraint_residual_v1_profile_sha256());
        receipt.update([backend_tag]);
        receipt.update(
            u64::try_from(report.observations.len())
                .unwrap()
                .to_le_bytes(),
        );
        for row in &report.observations {
            receipt.update(row.random_seed.to_le_bytes());
            receipt.update(row.sample_index.to_le_bytes());
            receipt.update(row.absolute_step.to_le_bytes());
            receipt.update(row.degrees_of_freedom.to_le_bytes());
            receipt.update(row.kinetic_kcal_per_mol.to_bits().to_le_bytes());
            receipt.update(row.temperature_kelvin.to_bits().to_le_bytes());
            receipt.update(
                row.maximum_position_constraint_residual_angstrom
                    .to_bits()
                    .to_le_bytes(),
            );
            receipt.update(
                row.maximum_radial_velocity_constraint_residual_angstrom_per_femtosecond
                    .to_bits()
                    .to_le_bytes(),
            );
        }
        receipt.update(report.mean_kinetic_kcal_per_mol.to_bits().to_le_bytes());
        receipt.update(report.mean_temperature_kelvin.to_bits().to_le_bytes());
        receipt.update(report.temperature_variance_kelvin2.to_bits().to_le_bytes());
        receipt.update(
            report
                .mean_position_constraint_residual_angstrom
                .to_bits()
                .to_le_bytes(),
        );
        receipt.update(
            report
                .maximum_position_constraint_residual_angstrom
                .to_bits()
                .to_le_bytes(),
        );
        receipt.update(
            report
                .mean_radial_velocity_constraint_residual_angstrom_per_femtosecond
                .to_bits()
                .to_le_bytes(),
        );
        receipt.update(
            report
                .maximum_radial_velocity_constraint_residual_angstrom_per_femtosecond
                .to_bits()
                .to_le_bytes(),
        );
        receipt.finalize().into()
    }

    fn independently_recompute_nvt_observation_receipt(
        report: &runtime::DevelopmentWaterBoxNvtEnsembleReportV1,
    ) -> [u8; 32] {
        let backend_tag = match report.backend {
            runtime::Backend::CppCpuReference => 1_u8,
            runtime::Backend::RustCpu => 2_u8,
            other => panic!("unexpected NVT observation backend: {other:?}"),
        };
        let mut receipt = Sha256::new();
        receipt.update(b"betelgeuze.engine_v2_native_water_box_nvt_ensemble_observation/1.0.0\0");
        receipt.update(runtime::development_water_box_nvt_ensemble_v1_profile_sha256());
        receipt.update([backend_tag]);
        receipt.update(
            u64::try_from(report.observations.len())
                .unwrap()
                .to_le_bytes(),
        );
        for row in &report.observations {
            receipt.update(row.random_seed.to_le_bytes());
            receipt.update(row.sample_index.to_le_bytes());
            receipt.update(row.absolute_step.to_le_bytes());
            receipt.update(row.degrees_of_freedom.to_le_bytes());
            receipt.update(row.kinetic_kcal_per_mol.to_bits().to_le_bytes());
            receipt.update(row.temperature_kelvin.to_bits().to_le_bytes());
        }
        receipt.update(report.mean_kinetic_kcal_per_mol.to_bits().to_le_bytes());
        receipt.update(report.mean_temperature_kelvin.to_bits().to_le_bytes());
        receipt.update(report.temperature_variance_kelvin2.to_bits().to_le_bytes());
        receipt.finalize().into()
    }

    fn independently_hash_failure_report(
        report: &runtime::DevelopmentDynamicsFailureReportV1,
    ) -> [u8; 32] {
        let backend_tag = match report.backend {
            runtime::Backend::CppCpuReference => 1_u8,
            runtime::Backend::RustCpu => 2_u8,
            other => panic!("unexpected failure-report backend: {other:?}"),
        };
        let mut receipt = Sha256::new();
        receipt
            .update(b"betelgeuze.engine_v2_native_water_box_dynamics_failure_observation/1.0.0\0");
        receipt.update(runtime::development_water_box_dynamics_failure_v1_profile_sha256());
        receipt.update([backend_tag]);
        receipt.update(u64::try_from(report.rows.len()).unwrap().to_le_bytes());
        for row in &report.rows {
            let failure_code_tag = match row.failure_code {
                runtime::DevelopmentDynamicsFailureCodeV1::InvalidArgument => 1,
                runtime::DevelopmentDynamicsFailureCodeV1::CapacityOverflow => 2,
                runtime::DevelopmentDynamicsFailureCodeV1::OutOfMemory => 3,
                runtime::DevelopmentDynamicsFailureCodeV1::UnsupportedIonIdentity => 4,
            };
            let evidence_tag = match row.evidence_kind {
                runtime::DevelopmentDynamicsFailureEvidenceV1::SafeWrapperRejection => 1,
                runtime::DevelopmentDynamicsFailureEvidenceV1::NativeRuntimeRejection => 2,
                runtime::DevelopmentDynamicsFailureEvidenceV1::SafeWrapperCapacityPreflight => 3,
                runtime::DevelopmentDynamicsFailureEvidenceV1::StatusMappingOnly => 4,
                runtime::DevelopmentDynamicsFailureEvidenceV1::DomainCatalogRejection => 5,
            };
            receipt.update(row.case_id.as_bytes());
            receipt.update([0]);
            receipt.update([failure_code_tag, evidence_tag]);
            receipt.update([u8::from(row.failure_attempted)]);
            receipt.update([match row.state_preserved {
                None => 0,
                Some(false) => 1,
                Some(true) => 2,
            }]);
            receipt.update(row.message.as_bytes());
            receipt.update([0]);
        }
        receipt.update([
            u8::from(report.all_required_failure_classes_typed),
            u8::from(report.all_required_failure_classes_runtime_exercised),
            u8::from(report.oom_allocation_attempted),
        ]);
        receipt.finalize().into()
    }

    #[test]
    fn constrained_nve_preserves_cpu_parity_residuals_and_checkpoint() {
        assert_eq!(
            runtime::DEVELOPMENT_WATER_BOX_CONSTRAINTS_V1_SCHEMA_ID,
            "betelgeuze.engine_v2_native_water_box_constraints_profile/1.0.0"
        );
        assert_eq!(
            runtime::DEVELOPMENT_WATER_BOX_CONSTRAINTS_V1_PROFILE_ID,
            "engine_v2_native_two_water_constraints_development_v1"
        );
        assert_eq!(
            runtime::development_water_box_constraints_v1_profile_sha256(),
            [
                0x8d, 0xca, 0xd0, 0xb5, 0x00, 0x5b, 0x7a, 0x76, 0x8c, 0xe0, 0xa8, 0x8b, 0x18, 0x04,
                0xb5, 0x5e, 0xcd, 0xdb, 0x9b, 0x34, 0x90, 0xe2, 0xdd, 0x59, 0x17, 0x9d, 0xfa, 0x23,
                0x93, 0x43, 0x35, 0x07,
            ]
        );
        let cpp = runtime::Context::new(runtime::ContextOptions::cpu_reference()).unwrap();
        let rust = runtime::Context::new(runtime::ContextOptions::rust_cpu()).unwrap();
        let mut cpp_box = runtime::DevelopmentWaterBoxV1::constrained_nve().unwrap();
        let mut rust_box = runtime::DevelopmentWaterBoxV1::constrained_nve().unwrap();
        let cpp_report = cpp_box.integrate(&cpp, 100).unwrap();
        let rust_report = rust_box.integrate(&rust, 100).unwrap();
        assert_eq!(rust_report.degrees_of_freedom, 12);
        assert_report_close(cpp_report, rust_report, TOLERANCE);
        assert_snapshot_close(
            &cpp_box.snapshot().unwrap(),
            &rust_box.snapshot().unwrap(),
            TOLERANCE,
        );
        assert_constraint_residuals(&rust_box.snapshot().unwrap(), 1.0e-10);
        let checkpoint = rust_box.checkpoint().unwrap();
        let mut restarted = runtime::DevelopmentWaterBoxV1::constrained_nve().unwrap();
        restarted.load_checkpoint(&checkpoint).unwrap();
        assert_eq!(
            rust_box.integrate(&rust, 32).unwrap(),
            restarted.integrate(&rust, 32).unwrap()
        );
        assert_snapshot_bits_equal(
            &rust_box.snapshot().unwrap(),
            &restarted.snapshot().unwrap(),
        );
    }

    #[test]
    fn constrained_baoab_is_seed_repeatable_and_cpu_parity_complete() {
        let cpp = runtime::Context::new(runtime::ContextOptions::cpu_reference()).unwrap();
        let rust = runtime::Context::new(runtime::ContextOptions::rust_cpu()).unwrap();
        let mut cpp_box = runtime::DevelopmentWaterBoxV1::constrained_baoab(BAOAB_SEED).unwrap();
        let mut rust_box = runtime::DevelopmentWaterBoxV1::constrained_baoab(BAOAB_SEED).unwrap();
        let mut repeated = runtime::DevelopmentWaterBoxV1::constrained_baoab(BAOAB_SEED).unwrap();
        let cpp_report = cpp_box.integrate(&cpp, 128).unwrap();
        let rust_report = rust_box.integrate(&rust, 128).unwrap();
        let repeated_report = repeated.integrate(&rust, 128).unwrap();
        assert_eq!(rust_report.degrees_of_freedom, 12);
        assert_eq!(rust_report, repeated_report);
        assert_report_close(cpp_report, rust_report, TOLERANCE);
        assert_snapshot_close(
            &cpp_box.snapshot().unwrap(),
            &rust_box.snapshot().unwrap(),
            TOLERANCE,
        );
        assert_constraint_residuals(&rust_box.snapshot().unwrap(), 1.0e-10);
        assert_snapshot_bits_equal(&rust_box.snapshot().unwrap(), &repeated.snapshot().unwrap());
    }

    fn assert_constraint_residuals(snapshot: &runtime::ParticleSnapshot, tolerance: f64) {
        for (i, j, target) in [
            (0, 1, OH_DISTANCE_ANGSTROM),
            (0, 2, OH_DISTANCE_ANGSTROM),
            (1, 2, HH_DISTANCE_ANGSTROM),
            (3, 4, OH_DISTANCE_ANGSTROM),
            (3, 5, OH_DISTANCE_ANGSTROM),
            (4, 5, HH_DISTANCE_ANGSTROM),
        ] {
            let delta = [
                snapshot.positions.x_angstrom[j] - snapshot.positions.x_angstrom[i],
                snapshot.positions.y_angstrom[j] - snapshot.positions.y_angstrom[i],
                snapshot.positions.z_angstrom[j] - snapshot.positions.z_angstrom[i],
            ];
            let distance = delta.iter().map(|v| v * v).sum::<f64>().sqrt();
            assert!((distance - target).abs() <= tolerance);
            let dv = [
                snapshot.velocities.x_angstrom_per_femtosecond[j]
                    - snapshot.velocities.x_angstrom_per_femtosecond[i],
                snapshot.velocities.y_angstrom_per_femtosecond[j]
                    - snapshot.velocities.y_angstrom_per_femtosecond[i],
                snapshot.velocities.z_angstrom_per_femtosecond[j]
                    - snapshot.velocities.z_angstrom_per_femtosecond[i],
            ];
            let residual = delta.iter().zip(dv).map(|(a, b)| a * b).sum::<f64>().abs() / distance;
            assert!(residual <= tolerance);
        }
    }

    fn assert_evaluation_close(
        left: &runtime::Evaluation,
        right: &runtime::Evaluation,
        tolerance: f64,
    ) {
        for (left, right) in [
            (
                left.energy.harmonic_bond_kcal_per_mol,
                right.energy.harmonic_bond_kcal_per_mol,
            ),
            (
                left.energy.harmonic_angle_kcal_per_mol,
                right.energy.harmonic_angle_kcal_per_mol,
            ),
            (
                left.energy.lennard_jones_kcal_per_mol,
                right.energy.lennard_jones_kcal_per_mol,
            ),
            (
                left.energy.coulomb_kcal_per_mol,
                right.energy.coulomb_kcal_per_mol,
            ),
            (
                left.energy.total_kcal_per_mol,
                right.energy.total_kcal_per_mol,
            ),
        ] {
            assert_close(left, right, tolerance);
        }
        for (left, right) in [
            (
                &left.forces.x_kcal_per_mol_angstrom,
                &right.forces.x_kcal_per_mol_angstrom,
            ),
            (
                &left.forces.y_kcal_per_mol_angstrom,
                &right.forces.y_kcal_per_mol_angstrom,
            ),
            (
                &left.forces.z_kcal_per_mol_angstrom,
                &right.forces.z_kcal_per_mol_angstrom,
            ),
        ] {
            assert_eq!(left.len(), right.len());
            for (&left, &right) in left.iter().zip(right) {
                assert_close(left, right, tolerance);
            }
        }
    }

    fn assert_report_close(
        left: runtime::DynamicsReport,
        right: runtime::DynamicsReport,
        tolerance: f64,
    ) {
        assert_eq!(left.steps_completed, right.steps_completed);
        assert_eq!(left.absolute_step, right.absolute_step);
        assert_eq!(left.degrees_of_freedom, right.degrees_of_freedom);
        for (left, right) in [
            (left.potential_kcal_per_mol, right.potential_kcal_per_mol),
            (left.kinetic_kcal_per_mol, right.kinetic_kcal_per_mol),
            (left.total_kcal_per_mol, right.total_kcal_per_mol),
            (left.temperature_kelvin, right.temperature_kelvin),
        ] {
            assert_close(left, right, tolerance);
        }
    }

    fn assert_snapshot_close(
        left: &runtime::ParticleSnapshot,
        right: &runtime::ParticleSnapshot,
        tolerance: f64,
    ) {
        assert_eq!(left.mass_dalton, right.mass_dalton);
        assert_eq!(left.charge_elementary, right.charge_elementary);
        for (left, right) in snapshot_channels(left, right) {
            assert_eq!(left.len(), right.len());
            for (&left, &right) in left.iter().zip(right) {
                assert_close(left, right, tolerance);
            }
        }
    }

    fn assert_snapshot_bits_equal(
        left: &runtime::ParticleSnapshot,
        right: &runtime::ParticleSnapshot,
    ) {
        assert_eq!(left.mass_dalton, right.mass_dalton);
        assert_eq!(left.charge_elementary, right.charge_elementary);
        for (left, right) in snapshot_channels(left, right) {
            assert_eq!(left.len(), right.len());
            for (&left, &right) in left.iter().zip(right) {
                assert_eq!(left.to_bits(), right.to_bits());
            }
        }
    }

    fn snapshot_channels<'a>(
        left: &'a runtime::ParticleSnapshot,
        right: &'a runtime::ParticleSnapshot,
    ) -> [(&'a [f64], &'a [f64]); 6] {
        [
            (&left.positions.x_angstrom, &right.positions.x_angstrom),
            (&left.positions.y_angstrom, &right.positions.y_angstrom),
            (&left.positions.z_angstrom, &right.positions.z_angstrom),
            (
                &left.velocities.x_angstrom_per_femtosecond,
                &right.velocities.x_angstrom_per_femtosecond,
            ),
            (
                &left.velocities.y_angstrom_per_femtosecond,
                &right.velocities.y_angstrom_per_femtosecond,
            ),
            (
                &left.velocities.z_angstrom_per_femtosecond,
                &right.velocities.z_angstrom_per_femtosecond,
            ),
        ]
    }

    fn assert_close(actual: f64, expected: f64, tolerance: f64) {
        let error = (actual - expected).abs();
        assert!(
            error <= tolerance * (1.0 + expected.abs()),
            "actual={actual:.17e}, expected={expected:.17e}, error={error:.3e}, tolerance={tolerance:.3e}"
        );
    }
}
