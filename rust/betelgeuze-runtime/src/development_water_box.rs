//! Frozen two-water native CPU development slice.
//!
//! This module constructs one exact synthetic two-water system using the shared
//! native `System`, `ForceField`, and `Simulation` owners. It is development
//! evidence only: it carries no product, scientific, free-energy, performance,
//! benchmark, Stage 0, Fresh-128, or molecular-execution authority.

use crate::{
    invalid, AtomNonbonded, Backend, Context, DistanceConstraint, DistanceConstraints,
    DynamicsReport, Evaluation, ForceField, ForceFieldInput, HarmonicAngle, HarmonicBond,
    Integrator, OrthorhombicCell, PairExclusion, ParticleSnapshot, ParticleSoa, PositionSoa,
    Result, Simulation, SimulationOptions, System, VelocitySoa,
};
use sha2::{Digest, Sha256};
use std::fmt;

pub const DEVELOPMENT_WATER_BOX_V1_SCHEMA_ID: &str = "betelgeuze.engine_v2_native_water_box/1.0.0";
pub const DEVELOPMENT_WATER_BOX_V1_PROFILE_ID: &str = "engine_v2_native_two_water_development_v1";
pub const DEVELOPMENT_WATER_BOX_CONSTRAINTS_V1_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_water_box_constraints_profile/1.0.0";
pub const DEVELOPMENT_WATER_BOX_CONSTRAINTS_V1_PROFILE_ID: &str =
    "engine_v2_native_two_water_constraints_development_v1";
pub const DEVELOPMENT_WATER_BOX_V1_ATOM_COUNT: usize = 6;
pub const DEVELOPMENT_WATER_ION_V1_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_water_ion_profile/1.0.0";
pub const DEVELOPMENT_WATER_ION_V1_PROFILE_ID: &str = "engine_v2_native_tip3p_nacl_development_v1";
pub const DEVELOPMENT_WATER_ION_V1_PARAMETER_SOURCE_DOI: &str = "10.1021/jp8001614";
pub const DEVELOPMENT_WATER_ION_V1_ATOM_COUNT: usize = 8;
const DEVELOPMENT_WATER_BOX_V1_PROFILE_BYTES: &[u8] =
    include_bytes!("../assets/engine_v2_native_water_box_profile_v1.json");
const DEVELOPMENT_WATER_BOX_CONSTRAINTS_V1_PROFILE_BYTES: &[u8] =
    include_bytes!("../assets/engine_v2_native_water_box_constraints_profile_v1.json");
const DEVELOPMENT_WATER_ION_V1_PROFILE_BYTES: &[u8] =
    include_bytes!("../assets/engine_v2_native_water_ion_profile_v1.json");

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
    System::new(ParticleSoa::new(
        PositionSoa::new(&position_x, &position_y, &position_z),
        &mass,
        &charge,
    ))
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

/// SHA-256 of the exact bounded NaCl development profile embedded into this runtime.
pub fn development_water_ion_v1_profile_sha256() -> [u8; 32] {
    Sha256::digest(DEVELOPMENT_WATER_ION_V1_PROFILE_BYTES).into()
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

#[cfg(test)]
mod tests {
    use super::{CHARGE_ELEMENTARY, HH_DISTANCE_ANGSTROM, OH_DISTANCE_ANGSTROM};
    use crate as runtime;

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
