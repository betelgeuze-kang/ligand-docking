//! Frozen tri-alanine native CPU development slice.
//!
//! The topology and parameters are an offline projection of the packaged
//! OpenMM Amber14 ff14SB definition for one 33-atom Ala3 structure. This is
//! development evidence only: it carries no product, scientific, benchmark,
//! performance, Stage 0, Fresh-128, molecular-execution, or HIP authority.

use crate::development_peptide_data as data;
use crate::{
    invalid, Backend, Context, DistanceConstraints, DynamicsReport, Evaluation, ForceField,
    ForceFieldInput, Integrator, ParticleSnapshot, ParticleSoa, PositionSoa, Result, Simulation,
    SimulationOptions, System, VelocitySoa,
};
use sha2::{Digest, Sha256};

pub const DEVELOPMENT_ALA3_V1_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_ala3_peptide_profile/1.0.0";
pub const DEVELOPMENT_ALA3_V1_PROFILE_ID: &str = "engine_v2_native_ala3_ff14sb_development_v1";
pub const DEVELOPMENT_ALA3_V1_PARAMETER_SOURCE_DOI: &str = "10.1021/acs.jctc.5b00255";
pub const DEVELOPMENT_ALA3_V1_ATOM_COUNT: usize = data::ATOM_COUNT;

const DEVELOPMENT_ALA3_V1_PROFILE_BYTES: &[u8] =
    include_bytes!("../assets/engine_v2_native_ala3_peptide_profile_v1.json");
const CUTOFF_ANGSTROM: f64 = 20.0;
const SWITCH_START_ANGSTROM: f64 = 15.0;
const ZERO_VELOCITY: [f64; data::ATOM_COUNT] = [0.0; data::ATOM_COUNT];

/// SHA-256 of the exact Ala3 development profile embedded into this runtime.
pub fn development_ala3_v1_profile_sha256() -> [u8; 32] {
    Sha256::digest(DEVELOPMENT_ALA3_V1_PROFILE_BYTES).into()
}

/// Evaluate the frozen Ala3 coordinates through one selected CPU backend.
pub fn evaluate_development_ala3_v1(context: &Context) -> Result<Evaluation> {
    require_cpu_backend(context)?;
    context.evaluate(&system(false)?, &forcefield()?)
}

/// Native-owned deterministic Ala3 development simulation.
pub struct DevelopmentAla3V1 {
    simulation: Simulation,
}

impl DevelopmentAla3V1 {
    /// Construct the frozen unconstrained Velocity Verlet lane.
    pub fn nve() -> Result<Self> {
        let system = system(true)?;
        let forcefield = forcefield()?;
        let simulation = Simulation::new(
            &system,
            &forcefield,
            &DistanceConstraints::default(),
            SimulationOptions {
                integrator: Integrator::VelocityVerlet,
                timestep_femtoseconds: data::TIMESTEP_FEMTOSECONDS,
                temperature_kelvin: 0.0,
                friction_per_femtosecond: 0.0,
                random_seed: 0,
            },
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

fn system(with_velocities: bool) -> Result<System> {
    let particles = ParticleSoa::new(
        PositionSoa::new(&data::POSITION_X, &data::POSITION_Y, &data::POSITION_Z),
        &data::MASS_DALTON,
        &data::CHARGE_ELEMENTARY,
    );
    if with_velocities {
        System::new(particles.with_velocities(VelocitySoa::new(
            &ZERO_VELOCITY,
            &ZERO_VELOCITY,
            &ZERO_VELOCITY,
        )))
    } else {
        System::new(particles)
    }
}

fn forcefield() -> Result<ForceField> {
    let mut input = ForceFieldInput::new(&data::ATOM_NONBONDED);
    input.bonds = &data::BONDS;
    input.angles = &data::ANGLES;
    input.torsions = &data::TORSIONS;
    input.exclusions = &data::EXCLUSIONS;
    input.pair_scales = &data::PAIR_SCALES;
    input.nonbonded.cutoff_angstrom = CUTOFF_ANGSTROM;
    input.nonbonded.switch_start_angstrom = SWITCH_START_ANGSTROM;
    input.nonbonded.dielectric = 1.0;
    input.nonbonded.screening_kappa_per_angstrom = 0.0;
    input.nonbonded.minimum_pair_distance_angstrom = 1.0e-6;
    ForceField::new(input)
}

fn require_cpu_backend(context: &Context) -> Result<()> {
    match context.backend()? {
        Backend::CppCpuReference | Backend::RustCpu => Ok(()),
        backend => Err(invalid(format!(
            "{DEVELOPMENT_ALA3_V1_PROFILE_ID} is a CPU-only development profile; resolved backend {backend:?} is not admitted"
        ))),
    }
}

#[cfg(test)]
mod tests {
    use super::{data, DEVELOPMENT_ALA3_V1_PROFILE_ID, DEVELOPMENT_ALA3_V1_SCHEMA_ID};
    use crate as runtime;
    use sha2::{Digest, Sha256};

    const DATA_SOURCE_BYTES: &[u8] = include_bytes!("development_peptide_data.rs");

    #[test]
    fn frozen_profile_identity_hash_and_term_counts_are_exact() {
        assert_eq!(
            DEVELOPMENT_ALA3_V1_SCHEMA_ID,
            "betelgeuze.engine_v2_native_ala3_peptide_profile/1.0.0"
        );
        assert_eq!(
            DEVELOPMENT_ALA3_V1_PROFILE_ID,
            "engine_v2_native_ala3_ff14sb_development_v1"
        );
        assert_eq!(runtime::DEVELOPMENT_ALA3_V1_ATOM_COUNT, 33);
        assert_eq!(data::BONDS.len(), 32);
        assert_eq!(data::ANGLES.len(), 57);
        assert_eq!(data::TORSIONS.len(), 72);
        assert_eq!(data::EXCLUSIONS.len(), 89);
        assert_eq!(data::PAIR_SCALES.len(), 74);
        assert!(data::PAIR_SCALES.iter().all(|row| {
            row.lennard_jones_scale.to_bits() == 0.5f64.to_bits()
                && row.coulomb_scale.to_bits() == (5.0f64 / 6.0).to_bits()
        }));
        assert_eq!(
            runtime::development_ala3_v1_profile_sha256(),
            [
                0xa7, 0xa4, 0x22, 0x9c, 0xc3, 0x0b, 0xb2, 0x43, 0x93, 0xb0, 0x6d, 0x4b, 0x19, 0xe2,
                0x5b, 0x91, 0x70, 0x60, 0x21, 0x3c, 0xa4, 0x32, 0xb1, 0x26, 0x33, 0x29, 0xbd, 0xa6,
                0xc0, 0xb4, 0x9a, 0xdf,
            ]
        );
        assert_eq!(
            <[u8; 32]>::from(Sha256::digest(DATA_SOURCE_BYTES)),
            [
                0x7a, 0x75, 0xf9, 0xcc, 0xd2, 0xd0, 0xce, 0xe9, 0x93, 0x87, 0xec, 0x2a, 0xe2, 0x5c,
                0x47, 0xb1, 0x45, 0xa1, 0xa3, 0x25, 0xbf, 0x04, 0x98, 0xb1, 0x75, 0x23, 0x40, 0xc3,
                0xa0, 0x4b, 0x88, 0xa0,
            ]
        );
    }

    #[test]
    fn frozen_openmm_reference_matches_both_cpu_backends() {
        let cpp = runtime::Context::new(runtime::ContextOptions::cpu_reference()).unwrap();
        let rust = runtime::Context::new(runtime::ContextOptions::rust_cpu()).unwrap();
        let cpp_evaluation = runtime::evaluate_development_ala3_v1(&cpp).unwrap();
        let rust_evaluation = runtime::evaluate_development_ala3_v1(&rust).unwrap();

        assert_eq!(cpp_evaluation, rust_evaluation);
        assert!(
            (cpp_evaluation.energy.total_kcal_per_mol - data::REFERENCE_ENERGY_KCAL_PER_MOL).abs()
                <= data::ENERGY_ABSOLUTE_TOLERANCE_KCAL_PER_MOL
        );
        assert_force_reference(
            &cpp_evaluation.forces.x_kcal_per_mol_angstrom,
            &data::REFERENCE_FORCE_X,
        );
        assert_force_reference(
            &cpp_evaluation.forces.y_kcal_per_mol_angstrom,
            &data::REFERENCE_FORCE_Y,
        );
        assert_force_reference(
            &cpp_evaluation.forces.z_kcal_per_mol_angstrom,
            &data::REFERENCE_FORCE_Z,
        );
    }

    #[test]
    fn frozen_nve_is_cpu_parity_complete_and_checkpoint_exact() {
        let cpp = runtime::Context::new(runtime::ContextOptions::cpu_reference()).unwrap();
        let rust = runtime::Context::new(runtime::ContextOptions::rust_cpu()).unwrap();
        let cpp_result = run_nve(&cpp);
        let rust_result = run_nve(&rust);

        assert_eq!(cpp_result.0, rust_result.0);
        assert_snapshot_bits_equal(&cpp_result.1, &rust_result.1);
        assert_eq!(cpp_result.2, rust_result.2);
        assert_eq!(
            rust_result.0.steps_completed,
            data::NVE_STEPS - data::CHECKPOINT_STEP
        );
        assert_eq!(rust_result.0.absolute_step, data::NVE_STEPS);
        assert_eq!(
            rust_result.0.degrees_of_freedom,
            3 * data::ATOM_COUNT as u64
        );
        assert!(rust_result.0.total_kcal_per_mol.is_finite());
    }

    fn run_nve(
        context: &runtime::Context,
    ) -> (runtime::DynamicsReport, runtime::ParticleSnapshot, Vec<u8>) {
        let mut continuous = runtime::DevelopmentAla3V1::nve().unwrap();
        let continuous_report = continuous.integrate(context, data::NVE_STEPS).unwrap();

        let mut direct = runtime::DevelopmentAla3V1::nve().unwrap();
        let initial = direct.snapshot().unwrap();
        assert!(initial
            .velocities
            .x_angstrom_per_femtosecond
            .iter()
            .chain(&initial.velocities.y_angstrom_per_femtosecond)
            .chain(&initial.velocities.z_angstrom_per_femtosecond)
            .all(|value| value.to_bits() == 0.0f64.to_bits()));
        direct.integrate(context, data::CHECKPOINT_STEP).unwrap();
        let checkpoint = direct.checkpoint().unwrap();
        assert_eq!(checkpoint, direct.checkpoint().unwrap());

        let mut restarted = runtime::DevelopmentAla3V1::nve().unwrap();
        restarted.load_checkpoint(&checkpoint).unwrap();
        assert_eq!(restarted.absolute_step().unwrap(), data::CHECKPOINT_STEP);
        assert_snapshot_bits_equal(&direct.snapshot().unwrap(), &restarted.snapshot().unwrap());

        let remaining = data::NVE_STEPS - data::CHECKPOINT_STEP;
        let direct_report = direct.integrate(context, remaining).unwrap();
        let restarted_report = restarted.integrate(context, remaining).unwrap();
        assert_eq!(direct_report, restarted_report);
        let final_snapshot = direct.snapshot().unwrap();
        assert_snapshot_bits_equal(&final_snapshot, &restarted.snapshot().unwrap());
        assert_snapshot_bits_equal(&continuous.snapshot().unwrap(), &final_snapshot);
        assert_eq!(continuous_report.absolute_step, direct_report.absolute_step);
        assert_eq!(
            continuous_report.degrees_of_freedom,
            direct_report.degrees_of_freedom
        );
        assert_eq!(
            continuous_report.potential_kcal_per_mol.to_bits(),
            direct_report.potential_kcal_per_mol.to_bits()
        );
        assert_eq!(
            continuous_report.kinetic_kcal_per_mol.to_bits(),
            direct_report.kinetic_kcal_per_mol.to_bits()
        );
        assert_eq!(
            continuous_report.total_kcal_per_mol.to_bits(),
            direct_report.total_kcal_per_mol.to_bits()
        );
        assert!(final_snapshot
            .positions
            .x_angstrom
            .iter()
            .chain(&final_snapshot.positions.y_angstrom)
            .chain(&final_snapshot.positions.z_angstrom)
            .chain(&final_snapshot.velocities.x_angstrom_per_femtosecond)
            .chain(&final_snapshot.velocities.y_angstrom_per_femtosecond)
            .chain(&final_snapshot.velocities.z_angstrom_per_femtosecond)
            .chain(&final_snapshot.mass_dalton)
            .chain(&final_snapshot.charge_elementary)
            .all(|value| value.is_finite()));
        (direct_report, final_snapshot, checkpoint)
    }

    fn assert_force_reference(actual: &[f64], reference: &[f64]) {
        assert_eq!(actual.len(), reference.len());
        let maximum_error = actual
            .iter()
            .zip(reference)
            .map(|(actual, reference)| (actual - reference).abs())
            .fold(0.0_f64, f64::max);
        assert!(
            maximum_error <= data::FORCE_ABSOLUTE_TOLERANCE_KCAL_PER_MOL_ANGSTROM,
            "maximum force error {maximum_error:e} exceeds tolerance {}",
            data::FORCE_ABSOLUTE_TOLERANCE_KCAL_PER_MOL_ANGSTROM
        );
    }

    fn assert_snapshot_bits_equal(
        left: &runtime::ParticleSnapshot,
        right: &runtime::ParticleSnapshot,
    ) {
        assert_eq!(left.len(), right.len());
        for (left, right) in [
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
            (&left.mass_dalton, &right.mass_dalton),
            (&left.charge_elementary, &right.charge_elementary),
        ] {
            assert_eq!(
                left.iter().map(|value| value.to_bits()).collect::<Vec<_>>(),
                right
                    .iter()
                    .map(|value| value.to_bits())
                    .collect::<Vec<_>>()
            );
        }
    }
}
