//! Minimal periodic Ala3 + TIP3P + NaCl composition fixture.
//!
//! This is structural development evidence for shared molecular-state
//! composition. It is not a bulk-solvent, PME, production, or scientific lane.

use crate::development_peptide::{
    development_ala3_v1_profile_sha256, require_development_ala3_cpu_backend,
};
use crate::development_peptide_constraints::{
    development_ala3_constraints_v1_profile_sha256, frozen_xh_constraints,
};
use crate::development_peptide_data as peptide;
use crate::development_water_box as water;
use crate::{
    development_ion_parameters_v1, development_water_box_v1_profile_sha256,
    development_water_ion_v1_profile_sha256, invalid,
    native_periodic_neighbor_list_v2_profile_sha256, AtomNonbonded, Backend, Context,
    DevelopmentIonIdentityV1, DistanceConstraint, DistanceConstraints, DynamicsReport, Evaluation,
    ForceField, ForceFieldInput, HarmonicAngle, HarmonicBond, Integrator, OrthorhombicCell,
    PairExclusion, PairScale, ParticleSnapshot, ParticleSoa, PeriodicTorsion, PositionSoa, Result,
    Simulation, SimulationOptions, System, VelocitySoa,
};
use sha2::{Digest, Sha256};

pub const DEVELOPMENT_ALA3_EXPLICIT_COMPOSITION_V1_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_ala3_explicit_composition_profile/1.0.0";
pub const DEVELOPMENT_ALA3_EXPLICIT_COMPOSITION_V1_PROFILE_ID: &str =
    "engine_v2_native_ala3_tip3p_nacl_composition_development_v1";
pub const DEVELOPMENT_ALA3_EXPLICIT_COMPOSITION_V1_ATOM_COUNT: usize = 41;
pub const DEVELOPMENT_ALA3_EXPLICIT_COMPOSITION_V1_CONSTRAINT_COUNT: usize = 23;

const PROFILE_BYTES: &[u8] =
    include_bytes!("../assets/engine_v2_native_ala3_explicit_composition_profile_v1.json");
const ALA3_TRANSLATION: [f64; 3] = [8.0, 15.0, 15.0];
const WATER_TRANSLATION: [f64; 3] = [25.0, 5.0, 10.0];
const CELL_ANGSTROM: f64 = 40.0;
const CUTOFF_ANGSTROM: f64 = 12.0;
const SWITCH_START_ANGSTROM: f64 = 10.0;
const TIMESTEP_FEMTOSECONDS: f64 = 0.02;
const NVE_STEPS: u64 = 128;
const CHECKPOINT_STEP: u64 = 53;
const MAXIMUM_NVE_DRIFT: f64 = 5.0e-4;

pub fn development_ala3_explicit_composition_v1_profile_sha256() -> [u8; 32] {
    Sha256::digest(PROFILE_BYTES).into()
}

#[derive(Clone, Debug, PartialEq)]
pub struct DevelopmentAla3ExplicitCompositionObservationV1 {
    pub backend: Backend,
    pub atom_count: u64,
    pub constraint_count: u64,
    pub static_total_kcal_per_mol: f64,
    pub static_evaluation_sha256: [u8; 32],
    pub nve_report: DynamicsReport,
    pub nve_post_projection_initial_total_kcal_per_mol: f64,
    pub nve_post_projection_total_energy_drift_kcal_per_mol: f64,
    pub maximum_position_residual_angstrom: f64,
    pub maximum_radial_velocity_residual_angstrom_per_femtosecond: f64,
    pub final_state_sha256: [u8; 32],
    pub observation_receipt_sha256: [u8; 32],
    pub backend_receipt_sha256: [u8; 32],
}

pub struct DevelopmentAla3ExplicitCompositionV1 {
    simulation: Simulation,
}

impl DevelopmentAla3ExplicitCompositionV1 {
    pub fn nve() -> Result<Self> {
        Ok(Self {
            simulation: Simulation::new(
                &composition_system(true)?,
                &composition_forcefield()?,
                &composition_constraints()?,
                SimulationOptions {
                    integrator: Integrator::VelocityVerlet,
                    timestep_femtoseconds: TIMESTEP_FEMTOSECONDS,
                    temperature_kelvin: 0.0,
                    friction_per_femtosecond: 0.0,
                    random_seed: 0,
                },
            )?,
        })
    }

    pub fn integrate(&mut self, context: &Context, steps: u64) -> Result<DynamicsReport> {
        require_development_ala3_cpu_backend(context)?;
        context.integrate(&mut self.simulation, steps)
    }

    pub fn snapshot(&self) -> Result<ParticleSnapshot> {
        self.simulation.snapshot()
    }

    pub fn checkpoint(&self) -> Result<Vec<u8>> {
        self.simulation.checkpoint()
    }

    pub fn load_checkpoint(&mut self, bytes: &[u8]) -> Result<()> {
        self.simulation.load_checkpoint(bytes)
    }
}

pub fn evaluate_development_ala3_explicit_composition_v1(context: &Context) -> Result<Evaluation> {
    require_development_ala3_cpu_backend(context)?;
    context.evaluate(&composition_system(false)?, &composition_forcefield()?)
}

pub fn observe_development_ala3_explicit_composition_v1(
    context: &Context,
) -> Result<DevelopmentAla3ExplicitCompositionObservationV1> {
    let backend = require_development_ala3_cpu_backend(context)?;
    let evaluation = evaluate_development_ala3_explicit_composition_v1(context)?;
    let mut projection = DevelopmentAla3ExplicitCompositionV1::nve()?;
    let initial = projection.integrate(context, 1)?;
    let mut continuous = DevelopmentAla3ExplicitCompositionV1::nve()?;
    let nve_report = continuous.integrate(context, NVE_STEPS)?;
    let final_snapshot = continuous.snapshot()?;

    let mut split = DevelopmentAla3ExplicitCompositionV1::nve()?;
    split.integrate(context, CHECKPOINT_STEP)?;
    let checkpoint = split.checkpoint()?;
    let mut restarted = DevelopmentAla3ExplicitCompositionV1::nve()?;
    restarted.load_checkpoint(&checkpoint)?;
    if state_sha256(&split.snapshot()?) != state_sha256(&restarted.snapshot()?) {
        return Err(invalid(
            "explicit composition checkpoint load did not preserve the state bitwise",
        ));
    }
    let remaining = NVE_STEPS - CHECKPOINT_STEP;
    let split_report = split.integrate(context, remaining)?;
    let restarted_report = restarted.integrate(context, remaining)?;
    if split_report != restarted_report
        || state_sha256(&split.snapshot()?) != state_sha256(&restarted.snapshot()?)
        || state_sha256(&split.snapshot()?) != state_sha256(&final_snapshot)
    {
        return Err(invalid(
            "explicit composition checkpoint or integration partition is not bitwise exact",
        ));
    }
    require_same_terminal_report(nve_report, split_report)?;

    let drift = nve_report.total_kcal_per_mol - initial.total_kcal_per_mol;
    let (position_residual, velocity_residual) = constraint_residuals(&final_snapshot)?;
    if !drift.is_finite()
        || drift.abs() > MAXIMUM_NVE_DRIFT
        || position_residual > water::CONSTRAINT_TOLERANCE_ANGSTROM
        || velocity_residual > water::CONSTRAINT_VELOCITY_TOLERANCE_ANGSTROM_PER_FEMTOSECOND
    {
        return Err(invalid(
            "explicit composition observation exceeded a frozen finite bound",
        ));
    }

    let mut observation = DevelopmentAla3ExplicitCompositionObservationV1 {
        backend,
        atom_count: DEVELOPMENT_ALA3_EXPLICIT_COMPOSITION_V1_ATOM_COUNT as u64,
        constraint_count: DEVELOPMENT_ALA3_EXPLICIT_COMPOSITION_V1_CONSTRAINT_COUNT as u64,
        static_total_kcal_per_mol: evaluation.energy.total_kcal_per_mol,
        static_evaluation_sha256: evaluation_sha256(&evaluation),
        nve_report,
        nve_post_projection_initial_total_kcal_per_mol: initial.total_kcal_per_mol,
        nve_post_projection_total_energy_drift_kcal_per_mol: drift,
        maximum_position_residual_angstrom: position_residual,
        maximum_radial_velocity_residual_angstrom_per_femtosecond: velocity_residual,
        final_state_sha256: state_sha256(&final_snapshot),
        observation_receipt_sha256: [0; 32],
        backend_receipt_sha256: [0; 32],
    };
    observation.observation_receipt_sha256 = observation_receipt(&observation);
    observation.backend_receipt_sha256 = backend_receipt(&observation);
    Ok(observation)
}

fn composition_system(with_velocities: bool) -> Result<System> {
    let sodium = development_ion_parameters_v1(DevelopmentIonIdentityV1::SODIUM)
        .map_err(|error| invalid(error.to_string()))?;
    let chloride = development_ion_parameters_v1(DevelopmentIonIdentityV1::CHLORIDE)
        .map_err(|error| invalid(error.to_string()))?;
    let mut x = Vec::with_capacity(41);
    let mut y = Vec::with_capacity(41);
    let mut z = Vec::with_capacity(41);
    let mut mass = Vec::with_capacity(41);
    let mut charge = Vec::with_capacity(41);
    for atom in 0..peptide::ATOM_COUNT {
        x.push(peptide::POSITION_X[atom] + ALA3_TRANSLATION[0]);
        y.push(peptide::POSITION_Y[atom] + ALA3_TRANSLATION[1]);
        z.push(peptide::POSITION_Z[atom] + ALA3_TRANSLATION[2]);
        mass.push(peptide::MASS_DALTON[atom]);
        charge.push(peptide::CHARGE_ELEMENTARY[atom]);
    }
    for atom in 0..water::DEVELOPMENT_WATER_BOX_V1_ATOM_COUNT {
        x.push(water::POSITION_X[atom] + WATER_TRANSLATION[0]);
        y.push(water::POSITION_Y[atom] + WATER_TRANSLATION[1]);
        z.push(water::POSITION_Z[atom] + WATER_TRANSLATION[2]);
        mass.push(water::MASS_DALTON[atom]);
        charge.push(water::CHARGE_ELEMENTARY[atom]);
    }
    x.extend([32.0, 34.5]);
    y.extend([10.0, 10.0]);
    z.extend([25.0, 25.0]);
    mass.extend([sodium.mass_dalton, chloride.mass_dalton]);
    charge.extend([sodium.charge_elementary, chloride.charge_elementary]);
    let particles = ParticleSoa::new(PositionSoa::new(&x, &y, &z), &mass, &charge);
    if with_velocities {
        let zero = vec![0.0; x.len()];
        System::new(particles.with_velocities(VelocitySoa::new(&zero, &zero, &zero)))
    } else {
        System::new(particles)
    }
}

fn offset_bond(mut row: HarmonicBond, offset: usize) -> HarmonicBond {
    row.atom_i += offset;
    row.atom_j += offset;
    row
}

fn offset_angle(mut row: HarmonicAngle, offset: usize) -> HarmonicAngle {
    row.atom_i += offset;
    row.atom_j += offset;
    row.atom_k += offset;
    row
}

fn offset_exclusion(mut row: PairExclusion, offset: usize) -> PairExclusion {
    row.atom_i += offset;
    row.atom_j += offset;
    row
}

fn composition_forcefield() -> Result<ForceField> {
    let sodium = development_ion_parameters_v1(DevelopmentIonIdentityV1::SODIUM)
        .map_err(|error| invalid(error.to_string()))?;
    let chloride = development_ion_parameters_v1(DevelopmentIonIdentityV1::CHLORIDE)
        .map_err(|error| invalid(error.to_string()))?;
    let mut atom_nonbonded = peptide::ATOM_NONBONDED.to_vec();
    atom_nonbonded.extend(water::ATOM_NONBONDED);
    atom_nonbonded.extend([
        AtomNonbonded {
            sigma_angstrom: sodium.sigma_angstrom,
            epsilon_kcal_per_mol: sodium.epsilon_kcal_per_mol,
        },
        AtomNonbonded {
            sigma_angstrom: chloride.sigma_angstrom,
            epsilon_kcal_per_mol: chloride.epsilon_kcal_per_mol,
        },
    ]);
    let mut bonds: Vec<HarmonicBond> = peptide::BONDS.to_vec();
    bonds.extend(water::BONDS.map(|row| offset_bond(row, peptide::ATOM_COUNT)));
    let mut angles: Vec<HarmonicAngle> = peptide::ANGLES.to_vec();
    angles.extend(water::ANGLES.map(|row| offset_angle(row, peptide::ATOM_COUNT)));
    let torsions: Vec<PeriodicTorsion> = peptide::TORSIONS.to_vec();
    let mut exclusions: Vec<PairExclusion> = peptide::EXCLUSIONS.to_vec();
    exclusions.extend(water::EXCLUSIONS.map(|row| offset_exclusion(row, peptide::ATOM_COUNT)));
    let pair_scales: Vec<PairScale> = peptide::PAIR_SCALES.to_vec();
    let mut input = ForceFieldInput::new(&atom_nonbonded);
    input.bonds = &bonds;
    input.angles = &angles;
    input.torsions = &torsions;
    input.exclusions = &exclusions;
    input.pair_scales = &pair_scales;
    input.cell = Some(OrthorhombicCell {
        lengths_angstrom: [CELL_ANGSTROM; 3],
        periodic_axes: [true; 3],
    });
    input.nonbonded.cutoff_angstrom = CUTOFF_ANGSTROM;
    input.nonbonded.switch_start_angstrom = SWITCH_START_ANGSTROM;
    input.nonbonded.minimum_pair_distance_angstrom = 1.0e-6;
    ForceField::new(input)
}

fn composition_constraints() -> Result<DistanceConstraints> {
    let mut rows = frozen_xh_constraints()?.rows;
    for offset in [peptide::ATOM_COUNT, peptide::ATOM_COUNT + 3] {
        rows.extend([
            DistanceConstraint {
                atom_i: offset,
                atom_j: offset + 1,
                distance_angstrom: water::OH_DISTANCE_ANGSTROM,
            },
            DistanceConstraint {
                atom_i: offset,
                atom_j: offset + 2,
                distance_angstrom: water::OH_DISTANCE_ANGSTROM,
            },
            DistanceConstraint {
                atom_i: offset + 1,
                atom_j: offset + 2,
                distance_angstrom: water::HH_DISTANCE_ANGSTROM,
            },
        ]);
    }
    if rows.len() != DEVELOPMENT_ALA3_EXPLICIT_COMPOSITION_V1_CONSTRAINT_COUNT {
        return Err(invalid("explicit composition constraint count drifted"));
    }
    Ok(DistanceConstraints {
        rows,
        tolerance_angstrom: water::CONSTRAINT_TOLERANCE_ANGSTROM,
        velocity_tolerance_angstrom_per_femtosecond:
            water::CONSTRAINT_VELOCITY_TOLERANCE_ANGSTROM_PER_FEMTOSECOND,
        max_iterations: water::CONSTRAINT_MAX_ITERATIONS,
    })
}

fn constraint_residuals(snapshot: &ParticleSnapshot) -> Result<(f64, f64)> {
    let mut maximum_position = 0.0_f64;
    let mut maximum_velocity = 0.0_f64;
    for row in composition_constraints()?.rows {
        let delta = [
            snapshot.positions.x_angstrom[row.atom_j] - snapshot.positions.x_angstrom[row.atom_i],
            snapshot.positions.y_angstrom[row.atom_j] - snapshot.positions.y_angstrom[row.atom_i],
            snapshot.positions.z_angstrom[row.atom_j] - snapshot.positions.z_angstrom[row.atom_i],
        ];
        let distance = delta.iter().map(|value| value * value).sum::<f64>().sqrt();
        let velocity = [
            snapshot.velocities.x_angstrom_per_femtosecond[row.atom_j]
                - snapshot.velocities.x_angstrom_per_femtosecond[row.atom_i],
            snapshot.velocities.y_angstrom_per_femtosecond[row.atom_j]
                - snapshot.velocities.y_angstrom_per_femtosecond[row.atom_i],
            snapshot.velocities.z_angstrom_per_femtosecond[row.atom_j]
                - snapshot.velocities.z_angstrom_per_femtosecond[row.atom_i],
        ];
        if !distance.is_finite() || distance <= 0.0 {
            return Err(invalid(
                "explicit composition constrained distance is invalid",
            ));
        }
        maximum_position = maximum_position.max((distance - row.distance_angstrom).abs());
        maximum_velocity = maximum_velocity.max(
            delta
                .iter()
                .zip(velocity)
                .map(|(a, b)| a * b)
                .sum::<f64>()
                .abs()
                / distance,
        );
    }
    Ok((maximum_position, maximum_velocity))
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
            "explicit composition partition changed terminal report",
        ))
    }
}

fn state_sha256(snapshot: &ParticleSnapshot) -> [u8; 32] {
    let mut hash = Sha256::new();
    hash.update(b"betelgeuze.engine_v2_native_ala3_explicit_composition_state/1.0.0");
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

fn evaluation_sha256(evaluation: &Evaluation) -> [u8; 32] {
    let mut hash = Sha256::new();
    hash.update(b"betelgeuze.engine_v2_native_ala3_explicit_composition_evaluation/1.0.0");
    hash.update(evaluation.energy.total_kcal_per_mol.to_bits().to_le_bytes());
    for channel in [
        evaluation.forces.x_kcal_per_mol_angstrom.as_slice(),
        evaluation.forces.y_kcal_per_mol_angstrom.as_slice(),
        evaluation.forces.z_kcal_per_mol_angstrom.as_slice(),
    ] {
        for value in channel {
            hash.update(value.to_bits().to_le_bytes());
        }
    }
    hash.finalize().into()
}

fn update_report(hash: &mut Sha256, report: DynamicsReport) {
    for value in [
        report.steps_completed,
        report.absolute_step,
        report.degrees_of_freedom,
    ] {
        hash.update(value.to_le_bytes());
    }
    for value in [
        report.potential_kcal_per_mol,
        report.kinetic_kcal_per_mol,
        report.total_kcal_per_mol,
        report.temperature_kelvin,
    ] {
        hash.update(value.to_bits().to_le_bytes());
    }
}

fn observation_receipt(row: &DevelopmentAla3ExplicitCompositionObservationV1) -> [u8; 32] {
    let mut hash = Sha256::new();
    hash.update(b"betelgeuze.engine_v2_native_ala3_explicit_composition_observation/1.0.0");
    for parent in [
        development_ala3_v1_profile_sha256(),
        development_ala3_constraints_v1_profile_sha256(),
        development_water_box_v1_profile_sha256(),
        development_water_ion_v1_profile_sha256(),
        native_periodic_neighbor_list_v2_profile_sha256(),
        development_ala3_explicit_composition_v1_profile_sha256(),
    ] {
        hash.update(parent);
    }
    hash.update(row.atom_count.to_le_bytes());
    hash.update(row.constraint_count.to_le_bytes());
    hash.update(row.static_total_kcal_per_mol.to_bits().to_le_bytes());
    hash.update(row.static_evaluation_sha256);
    update_report(&mut hash, row.nve_report);
    for value in [
        row.nve_post_projection_initial_total_kcal_per_mol,
        row.nve_post_projection_total_energy_drift_kcal_per_mol,
        row.maximum_position_residual_angstrom,
        row.maximum_radial_velocity_residual_angstrom_per_femtosecond,
    ] {
        hash.update(value.to_bits().to_le_bytes());
    }
    hash.update(row.final_state_sha256);
    hash.finalize().into()
}

fn backend_receipt(row: &DevelopmentAla3ExplicitCompositionObservationV1) -> [u8; 32] {
    let tag = match row.backend {
        Backend::CppCpuReference => b"cpp_cpu_reference".as_slice(),
        Backend::RustCpu => b"rust_cpu".as_slice(),
        _ => b"unadmitted".as_slice(),
    };
    let mut hash = Sha256::new();
    hash.update(b"betelgeuze.engine_v2_native_ala3_explicit_composition_backend/1.0.0");
    hash.update(row.observation_receipt_sha256);
    hash.update((tag.len() as u64).to_le_bytes());
    hash.update(tag);
    hash.finalize().into()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate as runtime;

    #[test]
    fn composition_is_complete_bounded_checkpoint_exact_and_cpu_bounded() {
        assert_eq!(
            development_ala3_explicit_composition_v1_profile_sha256(),
            [
                0xa9, 0xfa, 0xd3, 0x85, 0xe3, 0xea, 0xf8, 0x4c, 0x67, 0x35, 0x07, 0xee, 0x51, 0x37,
                0x78, 0xad, 0x05, 0x84, 0x2d, 0xa1, 0x39, 0xc2, 0x82, 0xce, 0x9d, 0xef, 0x1c, 0x71,
                0x2e, 0xb1, 0x30, 0x79,
            ]
        );
        let cpp = Context::new(runtime::ContextOptions::cpu_reference()).unwrap();
        let rust = Context::new(runtime::ContextOptions::rust_cpu()).unwrap();
        let cpp_row = observe_development_ala3_explicit_composition_v1(&cpp).unwrap();
        let rust_row = observe_development_ala3_explicit_composition_v1(&rust).unwrap();
        let snapshot = composition_system(false).unwrap().snapshot().unwrap();
        assert_eq!(snapshot.positions.x_angstrom.len(), 41);
        assert!(snapshot.charge_elementary.iter().sum::<f64>().abs() <= 1.0e-12);
        for channel in [
            &snapshot.positions.x_angstrom,
            &snapshot.positions.y_angstrom,
            &snapshot.positions.z_angstrom,
        ] {
            assert!(channel
                .iter()
                .all(|value| (0.0..CELL_ANGSTROM).contains(value)));
        }
        assert_eq!(
            snapshot.positions.x_angstrom[0],
            peptide::POSITION_X[0] + 8.0
        );
        assert_eq!(
            snapshot.positions.x_angstrom[33],
            water::POSITION_X[0] + 25.0
        );
        assert_eq!(snapshot.positions.x_angstrom[39], 32.0);
        assert_eq!(snapshot.positions.x_angstrom[40], 34.5);
        assert_eq!(cpp_row.atom_count, 41);
        assert_eq!(cpp_row.constraint_count, 23);
        assert_eq!(cpp_row.static_total_kcal_per_mol, -104.92872401231725);
        assert_eq!(
            cpp_row.static_evaluation_sha256,
            [
                0x0b, 0x44, 0x8b, 0xc3, 0x37, 0xd4, 0x6d, 0xd4, 0xf5, 0x59, 0x0f, 0x95, 0xf7, 0xe1,
                0xe2, 0xf9, 0xe2, 0x87, 0xe2, 0x2b, 0x30, 0xda, 0x78, 0x1e, 0x1a, 0xd6, 0xc5, 0xd8,
                0xcb, 0x0b, 0x2e, 0x24,
            ]
        );
        assert_eq!(
            cpp_row.nve_report,
            DynamicsReport {
                steps_completed: 128,
                absolute_step: 128,
                degrees_of_freedom: 100,
                potential_kcal_per_mol: -109.30341055126496,
                kinetic_kcal_per_mol: 1.7915224420080298,
                total_kcal_per_mol: -107.51188810925693,
                temperature_kelvin: 18.03058175039701,
            }
        );
        assert_eq!(
            cpp_row.nve_post_projection_initial_total_kcal_per_mol,
            -107.5118169601866
        );
        assert_eq!(
            cpp_row.nve_post_projection_total_energy_drift_kcal_per_mol,
            -7.11490703366735e-5
        );
        assert_eq!(
            cpp_row.maximum_position_residual_angstrom,
            9.00888252886034e-11
        );
        assert_eq!(
            cpp_row.maximum_radial_velocity_residual_angstrom_per_femtosecond,
            8.599890623379582e-11
        );
        assert_eq!(
            cpp_row.final_state_sha256,
            [
                0x00, 0x57, 0x73, 0x2e, 0x8c, 0xde, 0xe9, 0x62, 0x88, 0xbb, 0x36, 0x59, 0x37, 0x6a,
                0x05, 0x70, 0x4e, 0x9c, 0x74, 0x3f, 0xbe, 0xa3, 0x07, 0x0c, 0xe6, 0x18, 0x51, 0xab,
                0xff, 0x06, 0x23, 0x25,
            ]
        );
        assert_eq!(
            cpp_row.observation_receipt_sha256,
            [
                0x4b, 0xc8, 0xa9, 0xd4, 0x96, 0x44, 0x9b, 0x2c, 0xc3, 0x60, 0x1f, 0x6c, 0x2c, 0x13,
                0xff, 0x1b, 0x03, 0xff, 0x0a, 0x84, 0xc6, 0x70, 0x4d, 0xc7, 0x63, 0xd0, 0x22, 0x80,
                0x8a, 0x4d, 0x3a, 0xf4,
            ]
        );
        assert_eq!(
            cpp_row.backend_receipt_sha256,
            [
                0x2e, 0x9d, 0x08, 0x07, 0xa0, 0xcd, 0xe9, 0x0a, 0x83, 0xb2, 0x10, 0xdd, 0x2b, 0x85,
                0xa0, 0xe6, 0x4e, 0x06, 0xcb, 0xde, 0x70, 0x1d, 0x3d, 0x70, 0x75, 0x8b, 0xda, 0x9d,
                0x99, 0xb2, 0x2a, 0x40,
            ]
        );
        assert_eq!(
            rust_row.backend_receipt_sha256,
            [
                0x05, 0xfb, 0xc9, 0x5f, 0xef, 0x07, 0x7b, 0x92, 0xde, 0xce, 0x57, 0x6c, 0xbc, 0xe1,
                0x66, 0xc3, 0x00, 0xd0, 0x6f, 0xa9, 0xbd, 0xff, 0xb8, 0xf1, 0x01, 0x4e, 0xd3, 0x09,
                0x35, 0x0e, 0xe7, 0x03,
            ]
        );
        assert_eq!(
            cpp_row.static_evaluation_sha256,
            rust_row.static_evaluation_sha256
        );
        assert_eq!(cpp_row.nve_report, rust_row.nve_report);
        assert_eq!(cpp_row.final_state_sha256, rust_row.final_state_sha256);
        assert_eq!(
            cpp_row.observation_receipt_sha256,
            rust_row.observation_receipt_sha256
        );
        assert_eq!(
            cpp_row.observation_receipt_sha256,
            rederive_observation_receipt(&cpp_row)
        );
        assert_eq!(
            rust_row.observation_receipt_sha256,
            rederive_observation_receipt(&rust_row)
        );
        assert_eq!(
            cpp_row.backend_receipt_sha256,
            rederive_backend_receipt(&cpp_row)
        );
        assert_eq!(
            rust_row.backend_receipt_sha256,
            rederive_backend_receipt(&rust_row)
        );
    }

    fn rederive_observation_receipt(
        row: &DevelopmentAla3ExplicitCompositionObservationV1,
    ) -> [u8; 32] {
        let mut hash = Sha256::new();
        hash.update(b"betelgeuze.engine_v2_native_ala3_explicit_composition_observation/1.0.0");
        for parent in [
            runtime::development_ala3_v1_profile_sha256(),
            runtime::development_ala3_constraints_v1_profile_sha256(),
            runtime::development_water_box_v1_profile_sha256(),
            runtime::development_water_ion_v1_profile_sha256(),
            runtime::native_periodic_neighbor_list_v2_profile_sha256(),
            runtime::development_ala3_explicit_composition_v1_profile_sha256(),
        ] {
            hash.update(parent);
        }
        hash.update(row.atom_count.to_le_bytes());
        hash.update(row.constraint_count.to_le_bytes());
        hash.update(row.static_total_kcal_per_mol.to_bits().to_le_bytes());
        hash.update(row.static_evaluation_sha256);
        rederive_report(&mut hash, row.nve_report);
        for value in [
            row.nve_post_projection_initial_total_kcal_per_mol,
            row.nve_post_projection_total_energy_drift_kcal_per_mol,
            row.maximum_position_residual_angstrom,
            row.maximum_radial_velocity_residual_angstrom_per_femtosecond,
        ] {
            hash.update(value.to_bits().to_le_bytes());
        }
        hash.update(row.final_state_sha256);
        hash.finalize().into()
    }

    fn rederive_report(hash: &mut Sha256, report: DynamicsReport) {
        for value in [
            report.steps_completed,
            report.absolute_step,
            report.degrees_of_freedom,
        ] {
            hash.update(value.to_le_bytes());
        }
        for value in [
            report.potential_kcal_per_mol,
            report.kinetic_kcal_per_mol,
            report.total_kcal_per_mol,
            report.temperature_kelvin,
        ] {
            hash.update(value.to_bits().to_le_bytes());
        }
    }

    fn rederive_backend_receipt(row: &DevelopmentAla3ExplicitCompositionObservationV1) -> [u8; 32] {
        let tag = match row.backend {
            Backend::CppCpuReference => b"cpp_cpu_reference".as_slice(),
            Backend::RustCpu => b"rust_cpu".as_slice(),
            _ => b"unadmitted".as_slice(),
        };
        let mut hash = Sha256::new();
        hash.update(b"betelgeuze.engine_v2_native_ala3_explicit_composition_backend/1.0.0");
        hash.update(row.observation_receipt_sha256);
        hash.update((tag.len() as u64).to_le_bytes());
        hash.update(tag);
        hash.finalize().into()
    }
}
