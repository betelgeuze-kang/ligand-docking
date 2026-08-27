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
pub const DEVELOPMENT_ALA3_VALIDATION_V1_SCHEMA_ID: &str =
    "betelgeuze.engine_v2_native_ala3_validation_profile/1.0.0";
pub const DEVELOPMENT_ALA3_VALIDATION_V1_PROFILE_ID: &str =
    "engine_v2_native_ala3_cpu_validation_v1";

const DEVELOPMENT_ALA3_V1_PROFILE_BYTES: &[u8] =
    include_bytes!("../assets/engine_v2_native_ala3_peptide_profile_v1.json");
const DEVELOPMENT_ALA3_VALIDATION_V1_PROFILE_BYTES: &[u8] =
    include_bytes!("../assets/engine_v2_native_ala3_validation_profile_v1.json");
const CUTOFF_ANGSTROM: f64 = 20.0;
const SWITCH_START_ANGSTROM: f64 = 15.0;
const ZERO_VELOCITY: [f64; data::ATOM_COUNT] = [0.0; data::ATOM_COUNT];
const FINITE_DIFFERENCE_DISPLACEMENT_ANGSTROM: f64 = 1.0e-5;
const MAXIMUM_FINITE_DIFFERENCE_FORCE_ERROR: f64 = 1.0e-6;
const TRANSLATION_ANGSTROM: [f64; 3] = [8.0, -4.0, 2.0];
const MAXIMUM_INVARIANCE_ENERGY_ERROR: f64 = 1.0e-10;
const MAXIMUM_INVARIANCE_FORCE_ERROR: f64 = 1.0e-10;
const VALIDATION_NVE_STEPS: u64 = 256;
const MAXIMUM_NVE_TOTAL_ENERGY_DRIFT: f64 = 5.0e-4;

/// SHA-256 of the exact Ala3 development profile embedded into this runtime.
pub fn development_ala3_v1_profile_sha256() -> [u8; 32] {
    Sha256::digest(DEVELOPMENT_ALA3_V1_PROFILE_BYTES).into()
}

/// SHA-256 of the exact Ala3 validation profile embedded into this runtime.
pub fn development_ala3_validation_v1_profile_sha256() -> [u8; 32] {
    Sha256::digest(DEVELOPMENT_ALA3_VALIDATION_V1_PROFILE_BYTES).into()
}

/// Evaluate the frozen Ala3 coordinates through one selected CPU backend.
pub fn evaluate_development_ala3_v1(context: &Context) -> Result<Evaluation> {
    require_cpu_backend(context)?;
    context.evaluate(&system(false)?, &forcefield()?)
}

/// Complete repository-local Ala3 CPU validation observation.
#[derive(Clone, Debug, PartialEq)]
pub struct DevelopmentAla3ValidationObservationV1 {
    pub backend: Backend,
    pub finite_difference_component_count: u64,
    pub maximum_finite_difference_force_error_kcal_per_mol_angstrom: f64,
    pub translation_energy_error_kcal_per_mol: f64,
    pub maximum_translation_force_error_kcal_per_mol_angstrom: f64,
    pub permutation_energy_error_kcal_per_mol: f64,
    pub maximum_permutation_force_error_kcal_per_mol_angstrom: f64,
    pub nve_step_count: u64,
    pub nve_initial_total_kcal_per_mol: f64,
    pub nve_final_total_kcal_per_mol: f64,
    pub nve_total_energy_drift_kcal_per_mol: f64,
    pub nve_absolute_total_energy_drift_kcal_per_mol: f64,
    pub nve_final_state_sha256: [u8; 32],
    pub observation_receipt_sha256: [u8; 32],
    pub backend_receipt_sha256: [u8; 32],
}

/// Evaluate every frozen Ala3 validation dimension on one admitted CPU backend.
pub fn observe_development_ala3_validation_v1(
    context: &Context,
) -> Result<DevelopmentAla3ValidationObservationV1> {
    let backend = require_cpu_backend(context)?;
    let forcefield = forcefield()?;
    let base = context.evaluate(&system(false)?, &forcefield)?;

    let maximum_finite_difference_force_error =
        maximum_finite_difference_force_error(context, &forcefield, &base)?;

    let translated_x = translated_channel(&data::POSITION_X, TRANSLATION_ANGSTROM[0]);
    let translated_y = translated_channel(&data::POSITION_Y, TRANSLATION_ANGSTROM[1]);
    let translated_z = translated_channel(&data::POSITION_Z, TRANSLATION_ANGSTROM[2]);
    let translated = context.evaluate(
        &system_from_positions(&translated_x, &translated_y, &translated_z, false)?,
        &forcefield,
    )?;
    let translation_energy_error =
        (translated.energy.total_kcal_per_mol - base.energy.total_kcal_per_mol).abs();
    let maximum_translation_force_error = maximum_force_error_same_order(&base, &translated);

    let (permuted_system, permuted_forcefield, new_to_old) = reversed_system_and_forcefield()?;
    let permuted = context.evaluate(&permuted_system, &permuted_forcefield)?;
    let permutation_energy_error =
        (permuted.energy.total_kcal_per_mol - base.energy.total_kcal_per_mol).abs();
    let maximum_permutation_force_error =
        maximum_force_error_permuted(&base, &permuted, &new_to_old);

    let mut dynamics = DevelopmentAla3V1::nve()?;
    let nve_initial_total = base.energy.total_kcal_per_mol;
    let nve_report = dynamics.integrate(context, VALIDATION_NVE_STEPS)?;
    let nve_total_energy_drift = nve_report.total_kcal_per_mol - nve_initial_total;
    let nve_absolute_total_energy_drift = nve_total_energy_drift.abs();
    let nve_final_state_sha256 = snapshot_sha256(&dynamics.snapshot()?);

    let finite_values = [
        maximum_finite_difference_force_error,
        translation_energy_error,
        maximum_translation_force_error,
        permutation_energy_error,
        maximum_permutation_force_error,
        nve_initial_total,
        nve_report.total_kcal_per_mol,
        nve_total_energy_drift,
        nve_absolute_total_energy_drift,
    ];
    if finite_values.iter().any(|value| !value.is_finite()) {
        return Err(invalid("Ala3 validation produced a nonfinite observation"));
    }
    require_validation_bound(
        maximum_finite_difference_force_error,
        MAXIMUM_FINITE_DIFFERENCE_FORCE_ERROR,
        "finite-difference force error",
    )?;
    require_validation_bound(
        translation_energy_error,
        MAXIMUM_INVARIANCE_ENERGY_ERROR,
        "translation energy error",
    )?;
    require_validation_bound(
        maximum_translation_force_error,
        MAXIMUM_INVARIANCE_FORCE_ERROR,
        "translation force error",
    )?;
    require_validation_bound(
        permutation_energy_error,
        MAXIMUM_INVARIANCE_ENERGY_ERROR,
        "permutation energy error",
    )?;
    require_validation_bound(
        maximum_permutation_force_error,
        MAXIMUM_INVARIANCE_FORCE_ERROR,
        "permutation force error",
    )?;
    require_validation_bound(
        nve_absolute_total_energy_drift,
        MAXIMUM_NVE_TOTAL_ENERGY_DRIFT,
        "NVE total-energy drift",
    )?;

    let mut observation = DevelopmentAla3ValidationObservationV1 {
        backend,
        finite_difference_component_count: (3 * data::ATOM_COUNT) as u64,
        maximum_finite_difference_force_error_kcal_per_mol_angstrom:
            maximum_finite_difference_force_error,
        translation_energy_error_kcal_per_mol: translation_energy_error,
        maximum_translation_force_error_kcal_per_mol_angstrom: maximum_translation_force_error,
        permutation_energy_error_kcal_per_mol: permutation_energy_error,
        maximum_permutation_force_error_kcal_per_mol_angstrom: maximum_permutation_force_error,
        nve_step_count: VALIDATION_NVE_STEPS,
        nve_initial_total_kcal_per_mol: nve_initial_total,
        nve_final_total_kcal_per_mol: nve_report.total_kcal_per_mol,
        nve_total_energy_drift_kcal_per_mol: nve_total_energy_drift,
        nve_absolute_total_energy_drift_kcal_per_mol: nve_absolute_total_energy_drift,
        nve_final_state_sha256,
        observation_receipt_sha256: [0; 32],
        backend_receipt_sha256: [0; 32],
    };
    observation.observation_receipt_sha256 = validation_observation_receipt(&observation);
    observation.backend_receipt_sha256 =
        validation_backend_receipt(observation.observation_receipt_sha256, backend);
    Ok(observation)
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
    system_from_positions(
        &data::POSITION_X,
        &data::POSITION_Y,
        &data::POSITION_Z,
        with_velocities,
    )
}

fn system_from_positions(
    position_x: &[f64],
    position_y: &[f64],
    position_z: &[f64],
    with_velocities: bool,
) -> Result<System> {
    system_from_channels(
        position_x,
        position_y,
        position_z,
        &data::MASS_DALTON,
        &data::CHARGE_ELEMENTARY,
        with_velocities,
    )
}

fn system_from_channels(
    position_x: &[f64],
    position_y: &[f64],
    position_z: &[f64],
    mass_dalton: &[f64],
    charge_elementary: &[f64],
    with_velocities: bool,
) -> Result<System> {
    let particles = ParticleSoa::new(
        PositionSoa::new(position_x, position_y, position_z),
        mass_dalton,
        charge_elementary,
    );
    if with_velocities {
        if position_x.len() != data::ATOM_COUNT {
            return Err(invalid(
                "Ala3 zero-velocity construction requires exactly 33 atoms",
            ));
        }
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

fn maximum_finite_difference_force_error(
    context: &Context,
    forcefield: &ForceField,
    analytic: &Evaluation,
) -> Result<f64> {
    let analytic_channels = [
        &analytic.forces.x_kcal_per_mol_angstrom,
        &analytic.forces.y_kcal_per_mol_angstrom,
        &analytic.forces.z_kcal_per_mol_angstrom,
    ];
    let mut maximum_error = 0.0_f64;
    for (axis, channel) in analytic_channels.iter().enumerate() {
        for (atom, analytic_force) in channel.iter().copied().enumerate() {
            let plus = perturbed_total_energy(
                context,
                forcefield,
                atom,
                axis,
                FINITE_DIFFERENCE_DISPLACEMENT_ANGSTROM,
            )?;
            let minus = perturbed_total_energy(
                context,
                forcefield,
                atom,
                axis,
                -FINITE_DIFFERENCE_DISPLACEMENT_ANGSTROM,
            )?;
            let finite_difference_force =
                -(plus - minus) / (2.0 * FINITE_DIFFERENCE_DISPLACEMENT_ANGSTROM);
            maximum_error = maximum_error.max((finite_difference_force - analytic_force).abs());
        }
    }
    Ok(maximum_error)
}

fn perturbed_total_energy(
    context: &Context,
    forcefield: &ForceField,
    atom: usize,
    axis: usize,
    displacement: f64,
) -> Result<f64> {
    let mut position_x = data::POSITION_X;
    let mut position_y = data::POSITION_Y;
    let mut position_z = data::POSITION_Z;
    match axis {
        0 => position_x[atom] += displacement,
        1 => position_y[atom] += displacement,
        2 => position_z[atom] += displacement,
        _ => return Err(invalid("Ala3 finite-difference axis is out of range")),
    }
    Ok(context
        .evaluate_energy(
            &system_from_positions(&position_x, &position_y, &position_z, false)?,
            forcefield,
        )?
        .total_kcal_per_mol)
}

fn translated_channel(source: &[f64], translation: f64) -> Vec<f64> {
    source.iter().map(|value| value + translation).collect()
}

fn reversed_system_and_forcefield() -> Result<(System, ForceField, Vec<usize>)> {
    let new_to_old: Vec<_> = (0..data::ATOM_COUNT).rev().collect();
    let old_to_new = |index: usize| data::ATOM_COUNT - 1 - index;
    let permute_values = |values: &[f64]| {
        new_to_old
            .iter()
            .map(|index| values[*index])
            .collect::<Vec<_>>()
    };

    let position_x = permute_values(&data::POSITION_X);
    let position_y = permute_values(&data::POSITION_Y);
    let position_z = permute_values(&data::POSITION_Z);
    let mass_dalton = permute_values(&data::MASS_DALTON);
    let charge_elementary = permute_values(&data::CHARGE_ELEMENTARY);
    let atom_nonbonded = new_to_old
        .iter()
        .map(|index| data::ATOM_NONBONDED[*index])
        .collect::<Vec<_>>();

    let bonds = data::BONDS
        .iter()
        .copied()
        .map(|mut row| {
            row.atom_i = old_to_new(row.atom_i);
            row.atom_j = old_to_new(row.atom_j);
            row
        })
        .collect::<Vec<_>>();
    let angles = data::ANGLES
        .iter()
        .copied()
        .map(|mut row| {
            row.atom_i = old_to_new(row.atom_i);
            row.atom_j = old_to_new(row.atom_j);
            row.atom_k = old_to_new(row.atom_k);
            row
        })
        .collect::<Vec<_>>();
    let torsions = data::TORSIONS
        .iter()
        .copied()
        .map(|mut row| {
            row.atom_i = old_to_new(row.atom_i);
            row.atom_j = old_to_new(row.atom_j);
            row.atom_k = old_to_new(row.atom_k);
            row.atom_l = old_to_new(row.atom_l);
            row
        })
        .collect::<Vec<_>>();
    let mut exclusions = data::EXCLUSIONS
        .iter()
        .copied()
        .map(|mut row| {
            let atom_i = old_to_new(row.atom_i);
            let atom_j = old_to_new(row.atom_j);
            row.atom_i = atom_i.min(atom_j);
            row.atom_j = atom_i.max(atom_j);
            row
        })
        .collect::<Vec<_>>();
    exclusions.sort_by_key(|row| (row.atom_i, row.atom_j));
    let mut pair_scales = data::PAIR_SCALES
        .iter()
        .copied()
        .map(|mut row| {
            let atom_i = old_to_new(row.atom_i);
            let atom_j = old_to_new(row.atom_j);
            row.atom_i = atom_i.min(atom_j);
            row.atom_j = atom_i.max(atom_j);
            row
        })
        .collect::<Vec<_>>();
    pair_scales.sort_by_key(|row| (row.atom_i, row.atom_j));

    let system = system_from_channels(
        &position_x,
        &position_y,
        &position_z,
        &mass_dalton,
        &charge_elementary,
        false,
    )?;
    let mut input = ForceFieldInput::new(&atom_nonbonded);
    input.bonds = &bonds;
    input.angles = &angles;
    input.torsions = &torsions;
    input.exclusions = &exclusions;
    input.pair_scales = &pair_scales;
    input.nonbonded.cutoff_angstrom = CUTOFF_ANGSTROM;
    input.nonbonded.switch_start_angstrom = SWITCH_START_ANGSTROM;
    input.nonbonded.dielectric = 1.0;
    input.nonbonded.screening_kappa_per_angstrom = 0.0;
    input.nonbonded.minimum_pair_distance_angstrom = 1.0e-6;
    Ok((system, ForceField::new(input)?, new_to_old))
}

fn maximum_force_error_same_order(left: &Evaluation, right: &Evaluation) -> f64 {
    let left_channels = [
        &left.forces.x_kcal_per_mol_angstrom,
        &left.forces.y_kcal_per_mol_angstrom,
        &left.forces.z_kcal_per_mol_angstrom,
    ];
    let right_channels = [
        &right.forces.x_kcal_per_mol_angstrom,
        &right.forces.y_kcal_per_mol_angstrom,
        &right.forces.z_kcal_per_mol_angstrom,
    ];
    left_channels
        .iter()
        .zip(right_channels)
        .flat_map(|(left_channel, right_channel)| left_channel.iter().zip(right_channel))
        .map(|(left_value, right_value)| (left_value - right_value).abs())
        .fold(0.0, f64::max)
}

fn maximum_force_error_permuted(
    reference: &Evaluation,
    permuted: &Evaluation,
    new_to_old: &[usize],
) -> f64 {
    let reference_channels = [
        &reference.forces.x_kcal_per_mol_angstrom,
        &reference.forces.y_kcal_per_mol_angstrom,
        &reference.forces.z_kcal_per_mol_angstrom,
    ];
    let permuted_channels = [
        &permuted.forces.x_kcal_per_mol_angstrom,
        &permuted.forces.y_kcal_per_mol_angstrom,
        &permuted.forces.z_kcal_per_mol_angstrom,
    ];
    reference_channels
        .iter()
        .zip(permuted_channels)
        .flat_map(|(reference_channel, permuted_channel)| {
            new_to_old
                .iter()
                .copied()
                .enumerate()
                .map(move |(new_index, old_index)| {
                    (reference_channel[old_index] - permuted_channel[new_index]).abs()
                })
        })
        .fold(0.0, f64::max)
}

fn snapshot_sha256(snapshot: &ParticleSnapshot) -> [u8; 32] {
    let mut hash = Sha256::new();
    hash.update(b"betelgeuze.engine_v2_native_ala3_validation_state/1.0.0");
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

fn validation_observation_receipt(
    observation: &DevelopmentAla3ValidationObservationV1,
) -> [u8; 32] {
    let mut hash = Sha256::new();
    hash.update(b"betelgeuze.engine_v2_native_ala3_validation_observation/1.0.0");
    hash.update(development_ala3_v1_profile_sha256());
    hash.update(development_ala3_validation_v1_profile_sha256());
    hash.update(observation.finite_difference_component_count.to_le_bytes());
    for value in [
        observation.maximum_finite_difference_force_error_kcal_per_mol_angstrom,
        observation.translation_energy_error_kcal_per_mol,
        observation.maximum_translation_force_error_kcal_per_mol_angstrom,
        observation.permutation_energy_error_kcal_per_mol,
        observation.maximum_permutation_force_error_kcal_per_mol_angstrom,
        observation.nve_initial_total_kcal_per_mol,
        observation.nve_final_total_kcal_per_mol,
        observation.nve_total_energy_drift_kcal_per_mol,
        observation.nve_absolute_total_energy_drift_kcal_per_mol,
    ] {
        hash.update(value.to_bits().to_le_bytes());
    }
    hash.update(observation.nve_step_count.to_le_bytes());
    hash.update(observation.nve_final_state_sha256);
    hash.finalize().into()
}

fn validation_backend_receipt(observation_receipt: [u8; 32], backend: Backend) -> [u8; 32] {
    let backend_tag = match backend {
        Backend::CppCpuReference => b"cpp_cpu_reference".as_slice(),
        Backend::RustCpu => b"rust_cpu".as_slice(),
        _ => b"unadmitted".as_slice(),
    };
    let mut hash = Sha256::new();
    hash.update(b"betelgeuze.engine_v2_native_ala3_validation_backend/1.0.0");
    hash.update(observation_receipt);
    hash.update((backend_tag.len() as u64).to_le_bytes());
    hash.update(backend_tag);
    hash.finalize().into()
}

fn require_validation_bound(observed: f64, maximum: f64, name: &str) -> Result<()> {
    if observed <= maximum {
        Ok(())
    } else {
        Err(invalid(format!(
            "Ala3 validation {name} {observed:e} exceeds frozen maximum {maximum:e}"
        )))
    }
}

fn require_cpu_backend(context: &Context) -> Result<Backend> {
    let backend = context.backend()?;
    match backend {
        Backend::CppCpuReference | Backend::RustCpu => Ok(backend),
        backend => Err(invalid(format!(
            "{DEVELOPMENT_ALA3_V1_PROFILE_ID} is a CPU-only development profile; resolved backend {backend:?} is not admitted"
        ))),
    }
}

#[cfg(test)]
mod tests {
    use super::{
        data, DEVELOPMENT_ALA3_V1_PROFILE_ID, DEVELOPMENT_ALA3_V1_SCHEMA_ID,
        DEVELOPMENT_ALA3_VALIDATION_V1_PROFILE_ID, DEVELOPMENT_ALA3_VALIDATION_V1_SCHEMA_ID,
    };
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
            runtime::development_ala3_validation_v1_profile_sha256(),
            [
                0xf8, 0x6f, 0x0e, 0x25, 0x6c, 0x66, 0xe9, 0x90, 0x8b, 0xd0, 0xf4, 0xf2, 0x5d, 0x2e,
                0x4d, 0x10, 0x01, 0xc9, 0x3a, 0xa1, 0x15, 0xcf, 0x1f, 0x42, 0xe0, 0xdc, 0x24, 0x4f,
                0xdf, 0x88, 0x02, 0xf4,
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

    #[test]
    fn frozen_validation_is_complete_bounded_and_cpu_parity_exact() {
        assert_eq!(
            DEVELOPMENT_ALA3_VALIDATION_V1_SCHEMA_ID,
            "betelgeuze.engine_v2_native_ala3_validation_profile/1.0.0"
        );
        assert_eq!(
            DEVELOPMENT_ALA3_VALIDATION_V1_PROFILE_ID,
            "engine_v2_native_ala3_cpu_validation_v1"
        );
        let cpp = runtime::Context::new(runtime::ContextOptions::cpu_reference()).unwrap();
        let rust = runtime::Context::new(runtime::ContextOptions::rust_cpu()).unwrap();
        let cpp_observation = runtime::observe_development_ala3_validation_v1(&cpp).unwrap();
        let rust_observation = runtime::observe_development_ala3_validation_v1(&rust).unwrap();

        assert_eq!(cpp_observation.finite_difference_component_count, 99);
        assert_eq!(cpp_observation.nve_step_count, 256);
        assert_eq!(
            cpp_observation.observation_receipt_sha256,
            rederive_validation_observation_receipt(&cpp_observation)
        );
        assert_eq!(
            rust_observation.observation_receipt_sha256,
            rederive_validation_observation_receipt(&rust_observation)
        );
        assert_eq!(
            cpp_observation.backend_receipt_sha256,
            rederive_validation_backend_receipt(
                cpp_observation.observation_receipt_sha256,
                runtime::Backend::CppCpuReference,
            )
        );
        assert_eq!(
            rust_observation.backend_receipt_sha256,
            rederive_validation_backend_receipt(
                rust_observation.observation_receipt_sha256,
                runtime::Backend::RustCpu,
            )
        );
        assert_ne!(
            cpp_observation.backend_receipt_sha256,
            rust_observation.backend_receipt_sha256
        );
        assert_eq!(
            cpp_observation.nve_final_state_sha256,
            rust_observation.nve_final_state_sha256
        );
        assert_eq!(
            cpp_observation.observation_receipt_sha256,
            rust_observation.observation_receipt_sha256
        );
        for (cpp_value, rust_value) in [
            (
                cpp_observation.maximum_finite_difference_force_error_kcal_per_mol_angstrom,
                rust_observation.maximum_finite_difference_force_error_kcal_per_mol_angstrom,
            ),
            (
                cpp_observation.translation_energy_error_kcal_per_mol,
                rust_observation.translation_energy_error_kcal_per_mol,
            ),
            (
                cpp_observation.maximum_translation_force_error_kcal_per_mol_angstrom,
                rust_observation.maximum_translation_force_error_kcal_per_mol_angstrom,
            ),
            (
                cpp_observation.permutation_energy_error_kcal_per_mol,
                rust_observation.permutation_energy_error_kcal_per_mol,
            ),
            (
                cpp_observation.maximum_permutation_force_error_kcal_per_mol_angstrom,
                rust_observation.maximum_permutation_force_error_kcal_per_mol_angstrom,
            ),
            (
                cpp_observation.nve_initial_total_kcal_per_mol,
                rust_observation.nve_initial_total_kcal_per_mol,
            ),
            (
                cpp_observation.nve_final_total_kcal_per_mol,
                rust_observation.nve_final_total_kcal_per_mol,
            ),
            (
                cpp_observation.nve_total_energy_drift_kcal_per_mol,
                rust_observation.nve_total_energy_drift_kcal_per_mol,
            ),
            (
                cpp_observation.nve_absolute_total_energy_drift_kcal_per_mol,
                rust_observation.nve_absolute_total_energy_drift_kcal_per_mol,
            ),
        ] {
            assert_eq!(cpp_value.to_bits(), rust_value.to_bits());
        }
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

    fn rederive_validation_observation_receipt(
        observation: &runtime::DevelopmentAla3ValidationObservationV1,
    ) -> [u8; 32] {
        let mut hash = Sha256::new();
        hash.update(b"betelgeuze.engine_v2_native_ala3_validation_observation/1.0.0");
        hash.update(runtime::development_ala3_v1_profile_sha256());
        hash.update(runtime::development_ala3_validation_v1_profile_sha256());
        hash.update(observation.finite_difference_component_count.to_le_bytes());
        for value in [
            observation.maximum_finite_difference_force_error_kcal_per_mol_angstrom,
            observation.translation_energy_error_kcal_per_mol,
            observation.maximum_translation_force_error_kcal_per_mol_angstrom,
            observation.permutation_energy_error_kcal_per_mol,
            observation.maximum_permutation_force_error_kcal_per_mol_angstrom,
            observation.nve_initial_total_kcal_per_mol,
            observation.nve_final_total_kcal_per_mol,
            observation.nve_total_energy_drift_kcal_per_mol,
            observation.nve_absolute_total_energy_drift_kcal_per_mol,
        ] {
            hash.update(value.to_bits().to_le_bytes());
        }
        hash.update(observation.nve_step_count.to_le_bytes());
        hash.update(observation.nve_final_state_sha256);
        hash.finalize().into()
    }

    fn rederive_validation_backend_receipt(
        observation_receipt: [u8; 32],
        backend: runtime::Backend,
    ) -> [u8; 32] {
        let backend_tag = match backend {
            runtime::Backend::CppCpuReference => b"cpp_cpu_reference".as_slice(),
            runtime::Backend::RustCpu => b"rust_cpu".as_slice(),
            _ => b"unadmitted".as_slice(),
        };
        let mut hash = Sha256::new();
        hash.update(b"betelgeuze.engine_v2_native_ala3_validation_backend/1.0.0");
        hash.update(observation_receipt);
        hash.update((backend_tag.len() as u64).to_le_bytes());
        hash.update(backend_tag);
        hash.finalize().into()
    }
}
