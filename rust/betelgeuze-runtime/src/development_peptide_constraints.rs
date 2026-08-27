//! Frozen X-H SHAKE/RATTLE successor for the Ala3 development fixture.
//!
//! This module is repository-local validation evidence only. It grants no
//! production, scientific, benchmark, molecular-execution, or HIP authority.

use crate::development_peptide::{
    development_ala3_forcefield, development_ala3_system, development_ala3_v1_profile_sha256,
    development_ala3_validation_v1_profile_sha256, require_development_ala3_cpu_backend,
};
use crate::development_peptide_data as data;
use crate::{
    invalid, Backend, Context, DistanceConstraint, DistanceConstraints, DynamicsReport, Integrator,
    ParticleSnapshot, Result, Simulation, SimulationOptions,
};
use sha2::{Digest, Sha256};

pub const DEVELOPMENT_ALA3_CONSTRAINTS_V1_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_ala3_constraints_profile/1.0.0";
pub const DEVELOPMENT_ALA3_CONSTRAINTS_V1_PROFILE_ID: &str =
    "engine_v2_native_ala3_xh_constraints_development_v1";
pub const DEVELOPMENT_ALA3_CONSTRAINTS_V1_ROW_COUNT: usize = 17;

const PROFILE_BYTES: &[u8] =
    include_bytes!("../assets/engine_v2_native_ala3_constraints_profile_v1.json");
const HYDROGEN_MASS_CUTOFF_DALTON: f64 = 2.0;
const POSITION_TOLERANCE_ANGSTROM: f64 = 1.0e-10;
const VELOCITY_TOLERANCE_ANGSTROM_PER_FEMTOSECOND: f64 = 1.0e-10;
const MAX_ITERATIONS: u32 = 100;
const TIMESTEP_FEMTOSECONDS: f64 = 0.05;
const NVE_STEPS: u64 = 512;
const CHECKPOINT_STEP: u64 = 211;
const BAOAB_STEPS: u64 = 256;
const TEMPERATURE_KELVIN: f64 = 300.0;
const FRICTION_PER_FEMTOSECOND: f64 = 0.001;
const BAOAB_SEED: u64 = 2_711_863_518;
const MAXIMUM_ABSOLUTE_POST_PROJECTION_NVE_DRIFT_KCAL_PER_MOL: f64 = 5.0e-3;
#[cfg(test)]
const CPU_BACKEND_MAXIMUM_ABSOLUTE_DIFFERENCE: f64 = 2.0e-10;

/// SHA-256 of the exact constrained-Ala3 profile embedded into this runtime.
pub fn development_ala3_constraints_v1_profile_sha256() -> [u8; 32] {
    Sha256::digest(PROFILE_BYTES).into()
}

/// One complete constrained-Ala3 development observation.
#[derive(Clone, Debug, PartialEq)]
pub struct DevelopmentAla3ConstraintsObservationV1 {
    pub backend: Backend,
    pub constraint_count: u64,
    pub nve_report: DynamicsReport,
    pub nve_post_projection_initial_total_kcal_per_mol: f64,
    pub nve_post_projection_total_energy_drift_kcal_per_mol: f64,
    pub nve_maximum_position_residual_angstrom: f64,
    pub nve_maximum_radial_velocity_residual_angstrom_per_femtosecond: f64,
    pub nve_final_state_sha256: [u8; 32],
    pub baoab_report: DynamicsReport,
    pub baoab_maximum_position_residual_angstrom: f64,
    pub baoab_maximum_radial_velocity_residual_angstrom_per_femtosecond: f64,
    pub baoab_final_state_sha256: [u8; 32],
    pub observation_receipt_sha256: [u8; 32],
    pub backend_receipt_sha256: [u8; 32],
}

/// Native-owned frozen Ala3 X-H constrained development simulation.
pub struct DevelopmentAla3ConstrainedV1 {
    simulation: Simulation,
}

impl DevelopmentAla3ConstrainedV1 {
    /// Construct the fixed zero-velocity constrained Velocity Verlet lane.
    pub fn nve() -> Result<Self> {
        Self::new(SimulationOptions {
            integrator: Integrator::VelocityVerlet,
            timestep_femtoseconds: TIMESTEP_FEMTOSECONDS,
            temperature_kelvin: 0.0,
            friction_per_femtosecond: 0.0,
            random_seed: 0,
        })
    }

    /// Construct the fixed-seed constrained BAOAB repeatability lane.
    pub fn baoab() -> Result<Self> {
        Self::new(SimulationOptions {
            integrator: Integrator::LangevinBaoab,
            timestep_femtoseconds: TIMESTEP_FEMTOSECONDS,
            temperature_kelvin: TEMPERATURE_KELVIN,
            friction_per_femtosecond: FRICTION_PER_FEMTOSECOND,
            random_seed: BAOAB_SEED,
        })
    }

    fn new(options: SimulationOptions) -> Result<Self> {
        let simulation = Simulation::new(
            &development_ala3_system(true)?,
            &development_ala3_forcefield()?,
            &frozen_xh_constraints()?,
            options,
        )?;
        Ok(Self { simulation })
    }

    pub fn integrate(&mut self, context: &Context, step_count: u64) -> Result<DynamicsReport> {
        require_development_ala3_cpu_backend(context)?;
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

/// Run checkpoint, residual, fixed-seed repeatability, and receipt evidence.
pub fn observe_development_ala3_constraints_v1(
    context: &Context,
) -> Result<DevelopmentAla3ConstraintsObservationV1> {
    let backend = require_development_ala3_cpu_backend(context)?;
    let mut projection_probe = DevelopmentAla3ConstrainedV1::nve()?;
    let post_projection_initial_report = projection_probe.integrate(context, 1)?;

    let mut continuous = DevelopmentAla3ConstrainedV1::nve()?;
    let continuous_report = continuous.integrate(context, NVE_STEPS)?;
    let continuous_snapshot = continuous.snapshot()?;

    let mut split = DevelopmentAla3ConstrainedV1::nve()?;
    split.integrate(context, CHECKPOINT_STEP)?;
    let checkpoint = split.checkpoint()?;
    let mut restarted = DevelopmentAla3ConstrainedV1::nve()?;
    restarted.load_checkpoint(&checkpoint)?;
    require_same_snapshot(
        &split.snapshot()?,
        &restarted.snapshot()?,
        "checkpoint load",
    )?;
    let remaining = NVE_STEPS - CHECKPOINT_STEP;
    let split_report = split.integrate(context, remaining)?;
    let restarted_report = restarted.integrate(context, remaining)?;
    if split_report != restarted_report {
        return Err(invalid(
            "constrained Ala3 NVE reports differ across checkpoint continuation",
        ));
    }
    require_same_terminal_report(continuous_report, split_report)?;
    require_same_snapshot(
        &split.snapshot()?,
        &restarted.snapshot()?,
        "checkpoint continuation",
    )?;
    require_same_snapshot(
        &continuous_snapshot,
        &split.snapshot()?,
        "integration partition",
    )?;

    let (nve_position_residual, nve_velocity_residual) =
        maximum_constraint_residuals(&continuous_snapshot)?;

    let mut baoab = DevelopmentAla3ConstrainedV1::baoab()?;
    let mut repeated = DevelopmentAla3ConstrainedV1::baoab()?;
    let baoab_report = baoab.integrate(context, BAOAB_STEPS)?;
    let repeated_report = repeated.integrate(context, BAOAB_STEPS)?;
    if baoab_report != repeated_report {
        return Err(invalid(
            "constrained Ala3 fixed-seed BAOAB reports are not repeatable",
        ));
    }
    let baoab_snapshot = baoab.snapshot()?;
    require_same_snapshot(&baoab_snapshot, &repeated.snapshot()?, "fixed-seed BAOAB")?;
    let (baoab_position_residual, baoab_velocity_residual) =
        maximum_constraint_residuals(&baoab_snapshot)?;

    let nve_total_energy_drift =
        continuous_report.total_kcal_per_mol - post_projection_initial_report.total_kcal_per_mol;
    for value in [
        nve_total_energy_drift,
        nve_position_residual,
        nve_velocity_residual,
        baoab_position_residual,
        baoab_velocity_residual,
    ] {
        if !value.is_finite() {
            return Err(invalid(
                "constrained Ala3 observation produced a nonfinite value",
            ));
        }
    }
    require_residual_bound(
        nve_position_residual,
        POSITION_TOLERANCE_ANGSTROM,
        "NVE position",
    )?;
    require_residual_bound(
        nve_velocity_residual,
        VELOCITY_TOLERANCE_ANGSTROM_PER_FEMTOSECOND,
        "NVE radial velocity",
    )?;
    require_residual_bound(
        baoab_position_residual,
        POSITION_TOLERANCE_ANGSTROM,
        "BAOAB position",
    )?;
    require_residual_bound(
        baoab_velocity_residual,
        VELOCITY_TOLERANCE_ANGSTROM_PER_FEMTOSECOND,
        "BAOAB radial velocity",
    )?;
    require_residual_bound(
        nve_total_energy_drift.abs(),
        MAXIMUM_ABSOLUTE_POST_PROJECTION_NVE_DRIFT_KCAL_PER_MOL,
        "post-projection NVE total-energy drift",
    )?;

    let mut observation = DevelopmentAla3ConstraintsObservationV1 {
        backend,
        constraint_count: DEVELOPMENT_ALA3_CONSTRAINTS_V1_ROW_COUNT as u64,
        nve_report: continuous_report,
        nve_post_projection_initial_total_kcal_per_mol: post_projection_initial_report
            .total_kcal_per_mol,
        nve_post_projection_total_energy_drift_kcal_per_mol: nve_total_energy_drift,
        nve_maximum_position_residual_angstrom: nve_position_residual,
        nve_maximum_radial_velocity_residual_angstrom_per_femtosecond: nve_velocity_residual,
        nve_final_state_sha256: snapshot_sha256(&continuous_snapshot),
        baoab_report,
        baoab_maximum_position_residual_angstrom: baoab_position_residual,
        baoab_maximum_radial_velocity_residual_angstrom_per_femtosecond: baoab_velocity_residual,
        baoab_final_state_sha256: snapshot_sha256(&baoab_snapshot),
        observation_receipt_sha256: [0; 32],
        backend_receipt_sha256: [0; 32],
    };
    observation.observation_receipt_sha256 = observation_receipt(&observation);
    observation.backend_receipt_sha256 =
        backend_receipt(observation.observation_receipt_sha256, backend);
    Ok(observation)
}

fn frozen_xh_constraints() -> Result<DistanceConstraints> {
    let rows = data::BONDS
        .iter()
        .filter(|bond| {
            (data::MASS_DALTON[bond.atom_i] < HYDROGEN_MASS_CUTOFF_DALTON)
                ^ (data::MASS_DALTON[bond.atom_j] < HYDROGEN_MASS_CUTOFF_DALTON)
        })
        .map(|bond| DistanceConstraint {
            atom_i: bond.atom_i,
            atom_j: bond.atom_j,
            distance_angstrom: bond.equilibrium_angstrom,
        })
        .collect::<Vec<_>>();
    if rows.len() != DEVELOPMENT_ALA3_CONSTRAINTS_V1_ROW_COUNT {
        return Err(invalid(format!(
            "Ala3 X-H selection produced {} rows instead of {}",
            rows.len(),
            DEVELOPMENT_ALA3_CONSTRAINTS_V1_ROW_COUNT
        )));
    }
    Ok(DistanceConstraints {
        rows,
        tolerance_angstrom: POSITION_TOLERANCE_ANGSTROM,
        velocity_tolerance_angstrom_per_femtosecond: VELOCITY_TOLERANCE_ANGSTROM_PER_FEMTOSECOND,
        max_iterations: MAX_ITERATIONS,
    })
}

fn maximum_constraint_residuals(snapshot: &ParticleSnapshot) -> Result<(f64, f64)> {
    let mut maximum_position = 0.0_f64;
    let mut maximum_velocity = 0.0_f64;
    for row in frozen_xh_constraints()?.rows {
        let delta = [
            snapshot.positions.x_angstrom[row.atom_j] - snapshot.positions.x_angstrom[row.atom_i],
            snapshot.positions.y_angstrom[row.atom_j] - snapshot.positions.y_angstrom[row.atom_i],
            snapshot.positions.z_angstrom[row.atom_j] - snapshot.positions.z_angstrom[row.atom_i],
        ];
        let distance = delta.iter().map(|value| value * value).sum::<f64>().sqrt();
        if !distance.is_finite() || distance <= 0.0 {
            return Err(invalid(
                "constrained Ala3 observation contains an invalid constrained distance",
            ));
        }
        let delta_velocity = [
            snapshot.velocities.x_angstrom_per_femtosecond[row.atom_j]
                - snapshot.velocities.x_angstrom_per_femtosecond[row.atom_i],
            snapshot.velocities.y_angstrom_per_femtosecond[row.atom_j]
                - snapshot.velocities.y_angstrom_per_femtosecond[row.atom_i],
            snapshot.velocities.z_angstrom_per_femtosecond[row.atom_j]
                - snapshot.velocities.z_angstrom_per_femtosecond[row.atom_i],
        ];
        let radial_velocity = delta
            .iter()
            .zip(delta_velocity)
            .map(|(position, velocity)| position * velocity)
            .sum::<f64>()
            .abs()
            / distance;
        maximum_position = maximum_position.max((distance - row.distance_angstrom).abs());
        maximum_velocity = maximum_velocity.max(radial_velocity);
    }
    Ok((maximum_position, maximum_velocity))
}

fn require_same_snapshot(
    left: &ParticleSnapshot,
    right: &ParticleSnapshot,
    dimension: &str,
) -> Result<()> {
    if snapshot_sha256(left) == snapshot_sha256(right) {
        Ok(())
    } else {
        Err(invalid(format!(
            "constrained Ala3 {dimension} did not preserve the complete state bitwise"
        )))
    }
}

fn require_same_terminal_report(left: DynamicsReport, right: DynamicsReport) -> Result<()> {
    if left.absolute_step == right.absolute_step
        && left.degrees_of_freedom == right.degrees_of_freedom
        && left.potential_kcal_per_mol.to_bits() == right.potential_kcal_per_mol.to_bits()
        && left.kinetic_kcal_per_mol.to_bits() == right.kinetic_kcal_per_mol.to_bits()
        && left.total_kcal_per_mol.to_bits() == right.total_kcal_per_mol.to_bits()
        && left.temperature_kelvin.to_bits() == right.temperature_kelvin.to_bits()
    {
        Ok(())
    } else {
        Err(invalid(
            "constrained Ala3 NVE terminal report depends on integration partition",
        ))
    }
}

fn require_residual_bound(observed: f64, maximum: f64, name: &str) -> Result<()> {
    if observed <= maximum {
        Ok(())
    } else {
        Err(invalid(format!(
            "constrained Ala3 {name} residual {observed:e} exceeds {maximum:e}"
        )))
    }
}

fn snapshot_sha256(snapshot: &ParticleSnapshot) -> [u8; 32] {
    let mut hash = Sha256::new();
    hash.update(b"betelgeuze.engine_v2_native_ala3_constraints_state/1.0.0");
    hash.update((snapshot.len() as u64).to_le_bytes());
    for channel in [
        snapshot.positions.x_angstrom.as_slice(),
        snapshot.positions.y_angstrom.as_slice(),
        snapshot.positions.z_angstrom.as_slice(),
        snapshot.velocities.x_angstrom_per_femtosecond.as_slice(),
        snapshot.velocities.y_angstrom_per_femtosecond.as_slice(),
        snapshot.velocities.z_angstrom_per_femtosecond.as_slice(),
        snapshot.mass_dalton.as_slice(),
        snapshot.charge_elementary.as_slice(),
    ] {
        hash.update((channel.len() as u64).to_le_bytes());
        for value in channel {
            hash.update(value.to_bits().to_le_bytes());
        }
    }
    hash.finalize().into()
}

fn update_report(hash: &mut Sha256, report: DynamicsReport) {
    hash.update(report.steps_completed.to_le_bytes());
    hash.update(report.absolute_step.to_le_bytes());
    hash.update(report.degrees_of_freedom.to_le_bytes());
    for value in [
        report.potential_kcal_per_mol,
        report.kinetic_kcal_per_mol,
        report.total_kcal_per_mol,
        report.temperature_kelvin,
    ] {
        hash.update(value.to_bits().to_le_bytes());
    }
}

fn observation_receipt(observation: &DevelopmentAla3ConstraintsObservationV1) -> [u8; 32] {
    let mut hash = Sha256::new();
    hash.update(b"betelgeuze.engine_v2_native_ala3_constraints_observation/1.0.0");
    hash.update(development_ala3_v1_profile_sha256());
    hash.update(development_ala3_validation_v1_profile_sha256());
    hash.update(development_ala3_constraints_v1_profile_sha256());
    hash.update(observation.constraint_count.to_le_bytes());
    update_report(&mut hash, observation.nve_report);
    for value in [
        observation.nve_post_projection_initial_total_kcal_per_mol,
        observation.nve_post_projection_total_energy_drift_kcal_per_mol,
        observation.nve_maximum_position_residual_angstrom,
        observation.nve_maximum_radial_velocity_residual_angstrom_per_femtosecond,
    ] {
        hash.update(value.to_bits().to_le_bytes());
    }
    hash.update(observation.nve_final_state_sha256);
    update_report(&mut hash, observation.baoab_report);
    for value in [
        observation.baoab_maximum_position_residual_angstrom,
        observation.baoab_maximum_radial_velocity_residual_angstrom_per_femtosecond,
    ] {
        hash.update(value.to_bits().to_le_bytes());
    }
    hash.update(observation.baoab_final_state_sha256);
    hash.finalize().into()
}

fn backend_receipt(observation_receipt: [u8; 32], backend: Backend) -> [u8; 32] {
    let backend_tag = match backend {
        Backend::CppCpuReference => b"cpp_cpu_reference".as_slice(),
        Backend::RustCpu => b"rust_cpu".as_slice(),
        _ => b"unadmitted".as_slice(),
    };
    let mut hash = Sha256::new();
    hash.update(b"betelgeuze.engine_v2_native_ala3_constraints_backend/1.0.0");
    hash.update(observation_receipt);
    hash.update((backend_tag.len() as u64).to_le_bytes());
    hash.update(backend_tag);
    hash.finalize().into()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate as runtime;

    #[test]
    fn frozen_profile_and_xh_selection_are_exact() {
        assert_eq!(
            DEVELOPMENT_ALA3_CONSTRAINTS_V1_SCHEMA_ID,
            "betelgeuze.engine_v2_native_ala3_constraints_profile/1.0.0"
        );
        assert_eq!(
            DEVELOPMENT_ALA3_CONSTRAINTS_V1_PROFILE_ID,
            "engine_v2_native_ala3_xh_constraints_development_v1"
        );
        assert_eq!(
            development_ala3_constraints_v1_profile_sha256(),
            [
                0x81, 0x5c, 0x9a, 0xb4, 0x62, 0xae, 0xc7, 0xda, 0xa5, 0x7b, 0x6c, 0xf6, 0xe4, 0x2d,
                0x8b, 0xba, 0x56, 0x9d, 0x58, 0x91, 0xec, 0x1e, 0x00, 0x2d, 0xef, 0xf6, 0xad, 0x9e,
                0x97, 0x4c, 0xb6, 0x92,
            ]
        );
        let rows = frozen_xh_constraints().unwrap().rows;
        assert_eq!(rows.len(), 17);
        assert_eq!(
            rows.iter()
                .map(|row| (row.atom_i, row.atom_j))
                .collect::<Vec<_>>(),
            vec![
                (4, 5),
                (6, 7),
                (6, 8),
                (6, 9),
                (1, 0),
                (2, 0),
                (3, 0),
                (14, 15),
                (16, 17),
                (16, 18),
                (16, 19),
                (13, 12),
                (24, 25),
                (26, 27),
                (26, 28),
                (26, 29),
                (23, 22),
            ]
        );
    }

    #[test]
    fn observation_is_bounded_repeatable_checkpoint_exact_and_cpu_parity_bounded() {
        let cpp = runtime::Context::new(runtime::ContextOptions::cpu_reference()).unwrap();
        let rust = runtime::Context::new(runtime::ContextOptions::rust_cpu()).unwrap();
        let cpp_observation = runtime::observe_development_ala3_constraints_v1(&cpp).unwrap();
        let rust_observation = runtime::observe_development_ala3_constraints_v1(&rust).unwrap();

        assert_eq!(cpp_observation.constraint_count, 17);
        assert_eq!(cpp_observation.nve_report.absolute_step, NVE_STEPS);
        assert_eq!(cpp_observation.baoab_report.absolute_step, BAOAB_STEPS);
        assert_eq!(cpp_observation.nve_report.degrees_of_freedom, 82);
        assert_eq!(cpp_observation.baoab_report.degrees_of_freedom, 82);
        assert_eq!(
            cpp_observation.observation_receipt_sha256,
            rederive_observation_receipt(&cpp_observation)
        );
        assert_eq!(
            rust_observation.observation_receipt_sha256,
            rederive_observation_receipt(&rust_observation)
        );
        assert_eq!(
            cpp_observation.backend_receipt_sha256,
            rederive_backend_receipt(
                cpp_observation.observation_receipt_sha256,
                Backend::CppCpuReference
            )
        );
        assert_eq!(
            rust_observation.backend_receipt_sha256,
            rederive_backend_receipt(
                rust_observation.observation_receipt_sha256,
                Backend::RustCpu
            )
        );
        assert_ne!(
            cpp_observation.backend_receipt_sha256,
            rust_observation.backend_receipt_sha256
        );
        assert_report_close(cpp_observation.nve_report, rust_observation.nve_report);
        assert_report_close(cpp_observation.baoab_report, rust_observation.baoab_report);
        for (cpp_value, rust_value) in [
            (
                cpp_observation.nve_post_projection_initial_total_kcal_per_mol,
                rust_observation.nve_post_projection_initial_total_kcal_per_mol,
            ),
            (
                cpp_observation.nve_post_projection_total_energy_drift_kcal_per_mol,
                rust_observation.nve_post_projection_total_energy_drift_kcal_per_mol,
            ),
            (
                cpp_observation.nve_maximum_position_residual_angstrom,
                rust_observation.nve_maximum_position_residual_angstrom,
            ),
            (
                cpp_observation.nve_maximum_radial_velocity_residual_angstrom_per_femtosecond,
                rust_observation.nve_maximum_radial_velocity_residual_angstrom_per_femtosecond,
            ),
            (
                cpp_observation.baoab_maximum_position_residual_angstrom,
                rust_observation.baoab_maximum_position_residual_angstrom,
            ),
            (
                cpp_observation.baoab_maximum_radial_velocity_residual_angstrom_per_femtosecond,
                rust_observation.baoab_maximum_radial_velocity_residual_angstrom_per_femtosecond,
            ),
        ] {
            assert!((cpp_value - rust_value).abs() <= CPU_BACKEND_MAXIMUM_ABSOLUTE_DIFFERENCE);
        }

        assert_lane_parity_and_observation_digest(
            &cpp,
            &rust,
            DevelopmentAla3ConstrainedV1::nve,
            NVE_STEPS,
            cpp_observation.nve_final_state_sha256,
            rust_observation.nve_final_state_sha256,
        );
        assert_lane_parity_and_observation_digest(
            &cpp,
            &rust,
            DevelopmentAla3ConstrainedV1::baoab,
            BAOAB_STEPS,
            cpp_observation.baoab_final_state_sha256,
            rust_observation.baoab_final_state_sha256,
        );
    }

    fn rederive_observation_receipt(
        observation: &runtime::DevelopmentAla3ConstraintsObservationV1,
    ) -> [u8; 32] {
        let mut hash = Sha256::new();
        hash.update(b"betelgeuze.engine_v2_native_ala3_constraints_observation/1.0.0");
        hash.update(runtime::development_ala3_v1_profile_sha256());
        hash.update(runtime::development_ala3_validation_v1_profile_sha256());
        hash.update(runtime::development_ala3_constraints_v1_profile_sha256());
        hash.update(observation.constraint_count.to_le_bytes());
        rederive_report(&mut hash, observation.nve_report);
        for value in [
            observation.nve_post_projection_initial_total_kcal_per_mol,
            observation.nve_post_projection_total_energy_drift_kcal_per_mol,
            observation.nve_maximum_position_residual_angstrom,
            observation.nve_maximum_radial_velocity_residual_angstrom_per_femtosecond,
        ] {
            hash.update(value.to_bits().to_le_bytes());
        }
        hash.update(observation.nve_final_state_sha256);
        rederive_report(&mut hash, observation.baoab_report);
        for value in [
            observation.baoab_maximum_position_residual_angstrom,
            observation.baoab_maximum_radial_velocity_residual_angstrom_per_femtosecond,
        ] {
            hash.update(value.to_bits().to_le_bytes());
        }
        hash.update(observation.baoab_final_state_sha256);
        hash.finalize().into()
    }

    fn maximum_snapshot_difference(left: &ParticleSnapshot, right: &ParticleSnapshot) -> f64 {
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
        .into_iter()
        .flat_map(|(a, b)| a.iter().zip(b))
        .map(|(a, b)| (a - b).abs())
        .fold(0.0_f64, f64::max)
    }

    fn assert_lane_parity_and_observation_digest(
        cpp: &Context,
        rust: &Context,
        constructor: fn() -> Result<DevelopmentAla3ConstrainedV1>,
        steps: u64,
        expected_cpp_digest: [u8; 32],
        expected_rust_digest: [u8; 32],
    ) {
        let mut cpp_lane = constructor().unwrap();
        let mut rust_lane = constructor().unwrap();
        cpp_lane.integrate(cpp, steps).unwrap();
        rust_lane.integrate(rust, steps).unwrap();
        let cpp_snapshot = cpp_lane.snapshot().unwrap();
        let rust_snapshot = rust_lane.snapshot().unwrap();
        assert!(
            maximum_snapshot_difference(&cpp_snapshot, &rust_snapshot)
                <= CPU_BACKEND_MAXIMUM_ABSOLUTE_DIFFERENCE
        );
        assert_eq!(rederive_snapshot_sha256(&cpp_snapshot), expected_cpp_digest);
        assert_eq!(
            rederive_snapshot_sha256(&rust_snapshot),
            expected_rust_digest
        );
    }

    fn assert_report_close(left: DynamicsReport, right: DynamicsReport) {
        assert_eq!(left.steps_completed, right.steps_completed);
        assert_eq!(left.absolute_step, right.absolute_step);
        assert_eq!(left.degrees_of_freedom, right.degrees_of_freedom);
        for (left, right) in [
            (left.potential_kcal_per_mol, right.potential_kcal_per_mol),
            (left.kinetic_kcal_per_mol, right.kinetic_kcal_per_mol),
            (left.total_kcal_per_mol, right.total_kcal_per_mol),
            (left.temperature_kelvin, right.temperature_kelvin),
        ] {
            assert!(
                (left - right).abs() <= CPU_BACKEND_MAXIMUM_ABSOLUTE_DIFFERENCE,
                "report difference {:e} exceeds bound for {left:e} versus {right:e}",
                (left - right).abs(),
            );
        }
    }

    fn rederive_snapshot_sha256(snapshot: &ParticleSnapshot) -> [u8; 32] {
        let mut hash = Sha256::new();
        hash.update(b"betelgeuze.engine_v2_native_ala3_constraints_state/1.0.0");
        hash.update((snapshot.len() as u64).to_le_bytes());
        for channel in [
            snapshot.positions.x_angstrom.as_slice(),
            snapshot.positions.y_angstrom.as_slice(),
            snapshot.positions.z_angstrom.as_slice(),
            snapshot.velocities.x_angstrom_per_femtosecond.as_slice(),
            snapshot.velocities.y_angstrom_per_femtosecond.as_slice(),
            snapshot.velocities.z_angstrom_per_femtosecond.as_slice(),
            snapshot.mass_dalton.as_slice(),
            snapshot.charge_elementary.as_slice(),
        ] {
            hash.update((channel.len() as u64).to_le_bytes());
            for value in channel {
                hash.update(value.to_bits().to_le_bytes());
            }
        }
        hash.finalize().into()
    }

    fn rederive_report(hash: &mut Sha256, report: DynamicsReport) {
        hash.update(report.steps_completed.to_le_bytes());
        hash.update(report.absolute_step.to_le_bytes());
        hash.update(report.degrees_of_freedom.to_le_bytes());
        for value in [
            report.potential_kcal_per_mol,
            report.kinetic_kcal_per_mol,
            report.total_kcal_per_mol,
            report.temperature_kelvin,
        ] {
            hash.update(value.to_bits().to_le_bytes());
        }
    }

    fn rederive_backend_receipt(observation_receipt: [u8; 32], backend: Backend) -> [u8; 32] {
        let backend_tag = match backend {
            Backend::CppCpuReference => b"cpp_cpu_reference".as_slice(),
            Backend::RustCpu => b"rust_cpu".as_slice(),
            _ => b"unadmitted".as_slice(),
        };
        let mut hash = Sha256::new();
        hash.update(b"betelgeuze.engine_v2_native_ala3_constraints_backend/1.0.0");
        hash.update(observation_receipt);
        hash.update((backend_tag.len() as u64).to_le_bytes());
        hash.update(backend_tag);
        hash.finalize().into()
    }
}
