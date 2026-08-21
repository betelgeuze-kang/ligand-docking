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

#[cfg(test)]
mod tests {
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
