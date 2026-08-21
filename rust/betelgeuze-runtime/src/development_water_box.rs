//! Frozen two-water native CPU development slice.
//!
//! This module constructs one exact synthetic two-water system using the shared
//! native `System`, `ForceField`, and `Simulation` owners. It is development
//! evidence only: it carries no product, scientific, free-energy, performance,
//! benchmark, Stage 0, Fresh-128, or molecular-execution authority.

use crate::{
    invalid, AtomNonbonded, Backend, Context, DistanceConstraints, DynamicsReport, Evaluation,
    ForceField, ForceFieldInput, HarmonicAngle, HarmonicBond, Integrator, OrthorhombicCell,
    PairExclusion, ParticleSnapshot, ParticleSoa, PositionSoa, Result, Simulation,
    SimulationOptions, System, VelocitySoa,
};
use sha2::{Digest, Sha256};

pub const DEVELOPMENT_WATER_BOX_V1_SCHEMA_ID: &str = "betelgeuze.engine_v2_native_water_box/1.0.0";
pub const DEVELOPMENT_WATER_BOX_V1_PROFILE_ID: &str = "engine_v2_native_two_water_development_v1";
pub const DEVELOPMENT_WATER_BOX_V1_ATOM_COUNT: usize = 6;
const DEVELOPMENT_WATER_BOX_V1_PROFILE_BYTES: &[u8] =
    include_bytes!("../assets/engine_v2_native_water_box_profile_v1.json");

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

fn require_cpu_backend(context: &Context) -> Result<()> {
    match context.backend()? {
        Backend::CppCpuReference | Backend::RustCpu => Ok(()),
        backend => Err(invalid(format!(
            "{DEVELOPMENT_WATER_BOX_V1_PROFILE_ID} is a CPU-only development profile; resolved backend {backend:?} is not admitted"
        ))),
    }
}

/// SHA-256 of the exact profile embedded into this compiled runtime.
pub fn development_water_box_v1_profile_sha256() -> [u8; 32] {
    Sha256::digest(DEVELOPMENT_WATER_BOX_V1_PROFILE_BYTES).into()
}

/// Evaluate one frozen unconstrained water through a selected CPU backend.
pub fn evaluate_development_single_water_v1(context: &Context) -> Result<Evaluation> {
    require_cpu_backend(context)?;
    context.evaluate(&single_water_system()?, &single_water_forcefield()?)
}

/// Evaluate the frozen initial coordinates through the selected native backend.
pub fn evaluate_development_water_box_v1(context: &Context) -> Result<Evaluation> {
    require_cpu_backend(context)?;
    context.evaluate(&system()?, &forcefield()?)
}

/// Native-owned frozen two-water development simulation.
pub struct DevelopmentWaterBoxV1 {
    simulation: Simulation,
}

impl DevelopmentWaterBoxV1 {
    /// Construct the frozen deterministic NVE lane.
    pub fn nve() -> Result<Self> {
        Self::new(SimulationOptions {
            integrator: Integrator::VelocityVerlet,
            timestep_femtoseconds: TIMESTEP_FEMTOSECONDS,
            temperature_kelvin: TEMPERATURE_KELVIN,
            friction_per_femtosecond: 0.0,
            random_seed: 0,
        })
    }

    /// Construct the frozen deterministic BAOAB lane with an explicit seed.
    pub fn baoab(random_seed: u64) -> Result<Self> {
        Self::new(SimulationOptions {
            integrator: Integrator::LangevinBaoab,
            timestep_femtoseconds: TIMESTEP_FEMTOSECONDS,
            temperature_kelvin: TEMPERATURE_KELVIN,
            friction_per_femtosecond: FRICTION_PER_FEMTOSECOND,
            random_seed,
        })
    }

    fn new(options: SimulationOptions) -> Result<Self> {
        let system = system()?;
        let forcefield = forcefield()?;
        let simulation = Simulation::new(
            &system,
            &forcefield,
            &DistanceConstraints::default(),
            options,
        )?;
        Ok(Self { simulation })
    }

    pub fn integrate(&mut self, context: &Context, step_count: u64) -> Result<DynamicsReport> {
        require_cpu_backend(context)?;
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
