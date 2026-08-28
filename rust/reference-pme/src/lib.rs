//! Independent scalar order-4 particle-mesh reciprocal electrostatics.
//!
//! This crate deliberately implements only the reciprocal-space mesh term. It
//! is a deterministic, binary64 development oracle and is not a full PME
//! implementation.

#[cfg(test)]
mod direct_dft;
mod fft;

use std::error::Error;
use std::fmt;

use fft::Complex;

/// Frozen semantic version for this particle-mesh reciprocal calculation.
pub const PARTICLE_MESH_RECIPROCAL_SCHEMA_ID: &str =
    "betelgeuze.reference_particle_mesh_reciprocal/1.0.0";
/// Cardinal B-spline assignment order used on every mesh axis.
pub const CARDINAL_B_SPLINE_ORDER: usize = 4;

const COULOMB_KCAL_ANGSTROM_PER_MOL_E2: f64 = 332.063_713_299;
const MIN_MESH_DIMENSION: u32 = 4;
const MAX_MESH_DIMENSION: u32 = 128;
const MAX_MESH_POINT_COUNT: usize = 1_048_576;
const MAX_PARTICLE_COUNT: usize = 4_096;
const MAX_EVALUATION_WORK_UNITS: usize = 16_000_000;
const MAX_ABSOLUTE_COORDINATE_ANGSTROM: f64 = 1.0e12;
const MIN_NONZERO_ABSOLUTE_CHARGE_ELEMENTARY: f64 = 1.0e-12;
const MAX_ABSOLUTE_CHARGE_ELEMENTARY: f64 = 16.0;
const MIN_CELL_LENGTH_ANGSTROM: f64 = 1.0e-6;
const MAX_CELL_LENGTH_ANGSTROM: f64 = 1.0e9;
const MIN_ALPHA_PER_ANGSTROM: f64 = 1.0e-12;
const MAX_ALPHA_PER_ANGSTROM: f64 = 1.0e6;
const MIN_DIELECTRIC: f64 = 1.0e-12;
const MAX_DIELECTRIC: f64 = 1.0e12;
const LN_HALF_MIN_POSITIVE_SUBNORMAL: f64 = -745.133_219_101_941_1;
const LOG_RESCUE_SCALE: f64 = core::f64::consts::LN_2 * 256.0;
const RESCUE_SCALE: f64 = f64::from_bits(0x4ff0_0000_0000_0000);

/// One Cartesian position in canonical angstrom units.
#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct Position {
    pub x_angstrom: f64,
    pub y_angstrom: f64,
    pub z_angstrom: f64,
}

impl Position {
    #[must_use]
    pub const fn new(x_angstrom: f64, y_angstrom: f64, z_angstrom: f64) -> Self {
        Self {
            x_angstrom,
            y_angstrom,
            z_angstrom,
        }
    }

    const fn components(self) -> [f64; 3] {
        [self.x_angstrom, self.y_angstrom, self.z_angstrom]
    }
}

/// Fully periodic orthorhombic cell in canonical angstrom units.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct OrthorhombicCell {
    pub lengths_angstrom: [f64; 3],
}

/// Frozen scalar particle-mesh reciprocal settings.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct ParticleMeshReciprocalSettings {
    pub alpha_per_angstrom: f64,
    pub mesh_dimensions: [u32; 3],
    pub dielectric: f64,
}

impl Default for ParticleMeshReciprocalSettings {
    fn default() -> Self {
        Self {
            alpha_per_angstrom: 0.3,
            mesh_dimensions: [16, 16, 16],
            dielectric: 1.0,
        }
    }
}

/// Complete owned input to the particle-mesh reciprocal evaluator.
#[derive(Clone, Debug, PartialEq)]
pub struct ParticleMeshReciprocalInput {
    pub positions: Vec<Position>,
    pub charges_elementary: Vec<f64>,
    pub cell: OrthorhombicCell,
    pub settings: ParticleMeshReciprocalSettings,
}

impl ParticleMeshReciprocalInput {
    #[must_use]
    pub fn new(
        positions: Vec<Position>,
        charges_elementary: Vec<f64>,
        cell: OrthorhombicCell,
    ) -> Self {
        Self {
            positions,
            charges_elementary,
            cell,
            settings: ParticleMeshReciprocalSettings::default(),
        }
    }
}

/// Reciprocal-space mesh energy and its analytic negative gradient.
#[derive(Clone, Debug, PartialEq)]
pub struct ParticleMeshReciprocalEvaluation {
    pub reciprocal_space_kcal_per_mol: f64,
    pub forces_kcal_per_mol_angstrom: Vec<[f64; 3]>,
}

/// Stable error categories for malformed or unsupported inputs.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum ParticleMeshReciprocalErrorCode {
    EmptySystem,
    CapacityExceeded,
    ChargeCountMismatch,
    NonFiniteCoordinate,
    NonFiniteCharge,
    NonNeutralSystem,
    InvalidCell,
    InvalidParameter,
    InvalidMesh,
    NonFiniteResult,
}

/// A validation or evaluation failure with a machine-readable category.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ParticleMeshReciprocalError {
    code: ParticleMeshReciprocalErrorCode,
    detail: String,
}

impl ParticleMeshReciprocalError {
    fn new(code: ParticleMeshReciprocalErrorCode, detail: impl Into<String>) -> Self {
        Self {
            code,
            detail: detail.into(),
        }
    }

    #[must_use]
    pub const fn code(&self) -> ParticleMeshReciprocalErrorCode {
        self.code
    }

    #[must_use]
    pub fn detail(&self) -> &str {
        &self.detail
    }
}

impl fmt::Display for ParticleMeshReciprocalError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "{:?}: {}", self.code, self.detail)
    }
}

impl Error for ParticleMeshReciprocalError {}

type Transform3d = fn(&mut [Complex], [usize; 3], bool);

/// Evaluate the frozen scalar order-4 particle-mesh reciprocal term.
///
/// Positions are reduced into the periodic cell, charges are assigned to the
/// four points `floor(u)-1..=floor(u)+2` on each axis, and a deterministic
/// radix-2 transform evaluates the deconvolved reciprocal sum. The returned
/// forces analytically differentiate those same assignment weights.
///
/// # Errors
///
/// Returns a typed [`ParticleMeshReciprocalError`] when the input violates a
/// structural, numeric-envelope, exact-neutrality, cell, or mesh invariant, or
/// when a completed result is not finite.
pub fn evaluate(
    input: &ParticleMeshReciprocalInput,
) -> Result<ParticleMeshReciprocalEvaluation, ParticleMeshReciprocalError> {
    evaluate_with_transform(input, fft::fft_3d)
}

fn evaluate_with_transform(
    input: &ParticleMeshReciprocalInput,
    transform: Transform3d,
) -> Result<ParticleMeshReciprocalEvaluation, ParticleMeshReciprocalError> {
    Ok(compute_with_transform(input, transform)?.evaluation)
}

struct InternalEvaluation {
    evaluation: ParticleMeshReciprocalEvaluation,
    #[cfg(test)]
    charge_grid: Vec<Complex>,
    #[cfg(test)]
    grid_derivative: Vec<Complex>,
}

fn compute_with_transform(
    input: &ParticleMeshReciprocalInput,
    transform: Transform3d,
) -> Result<InternalEvaluation, ParticleMeshReciprocalError> {
    let validated = validate(input)?;
    let assignments = input
        .positions
        .iter()
        .copied()
        .map(|position| assignment(position, input.cell, validated.dimensions))
        .collect::<Vec<_>>();
    let mut spectrum = vec![Complex::default(); validated.mesh_point_count];
    spread_charges(
        &mut spectrum,
        validated.dimensions,
        &assignments,
        &input.charges_elementary,
    );
    #[cfg(test)]
    let charge_grid = spectrum.clone();
    transform(&mut spectrum, validated.dimensions, false);

    let reciprocal = apply_reciprocal_operator(input, &validated, &mut spectrum);
    let reciprocal_space_kcal_per_mol = reciprocal.energy;

    transform(&mut spectrum, validated.dimensions, true);
    let scaled_grid_multiplier = reciprocal.grid_derivative_scale / RESCUE_SCALE;
    let forces_kcal_per_mol_angstrom = gather_forces(
        &spectrum,
        validated.dimensions,
        &assignments,
        &input.charges_elementary,
        input.cell,
        scaled_grid_multiplier,
    );
    for value in &mut spectrum {
        *value = value.scale(scaled_grid_multiplier);
    }

    if !reciprocal_space_kcal_per_mol.is_finite()
        || spectrum
            .iter()
            .any(|value| !value.real.is_finite() || !value.imaginary.is_finite())
        || forces_kcal_per_mol_angstrom
            .iter()
            .flatten()
            .any(|value| !value.is_finite())
    {
        return Err(ParticleMeshReciprocalError::new(
            ParticleMeshReciprocalErrorCode::NonFiniteResult,
            "reciprocal energy, grid derivative, or force is not finite",
        ));
    }

    Ok(InternalEvaluation {
        evaluation: ParticleMeshReciprocalEvaluation {
            reciprocal_space_kcal_per_mol,
            forces_kcal_per_mol_angstrom,
        },
        #[cfg(test)]
        charge_grid,
        #[cfg(test)]
        grid_derivative: spectrum,
    })
}

struct ReciprocalOperator {
    energy: f64,
    grid_derivative_scale: f64,
}

fn apply_reciprocal_operator(
    input: &ParticleMeshReciprocalInput,
    validated: &ValidatedInput,
    spectrum: &mut [Complex],
) -> ReciprocalOperator {
    let alpha = input.settings.alpha_per_angstrom;
    let energy_prefactor = COULOMB_KCAL_ANGSTROM_PER_MOL_E2 / input.settings.dielectric
        * core::f64::consts::TAU
        / validated.volume_angstrom_cubed;
    let grid_derivative_scale =
        2.0 * energy_prefactor * bounded_usize_to_f64(validated.mesh_point_count);
    let mut dimension_data = [Vec::new(), Vec::new(), Vec::new()];
    for (axis, data) in dimension_data.iter_mut().enumerate() {
        *data = reciprocal_axis_data(
            validated.dimensions[axis],
            input.cell.lengths_angstrom[axis],
        );
    }
    let mut reciprocal_sum = CompensatedSum::default();
    let mut rescued_energy_scaled = CompensatedSum::default();
    let mut has_rescued_energy = false;
    for x in 0..validated.dimensions[0] {
        for y in 0..validated.dimensions[1] {
            for z in 0..validated.dimensions[2] {
                let grid_index = fft::index(x, y, z, validated.dimensions);
                if x == 0 && y == 0 && z == 0 {
                    spectrum[grid_index] = Complex::default();
                    continue;
                }
                let wave_squared = dimension_data[0][x].wave_squared
                    + dimension_data[1][y].wave_squared
                    + dimension_data[2][z].wave_squared;
                let assignment_modulus = dimension_data[0][x].assignment_modulus
                    * dimension_data[1][y].assignment_modulus
                    * dimension_data[2][z].assignment_modulus;
                let damping_exponent = -wave_squared / (4.0 * alpha * alpha);
                let damping = libm::exp(damping_exponent);
                let influence = damping / wave_squared / (assignment_modulus * assignment_modulus);
                let charge_mode = spectrum[grid_index];
                let regular_grid_mode = charge_mode.scale(influence);
                let regular_energy_mode = influence * charge_mode.norm_squared();
                if mode_requires_log_rescue(
                    charge_mode,
                    damping,
                    influence,
                    regular_grid_mode,
                    regular_energy_mode,
                ) {
                    has_rescued_energy = true;
                    let denominator_log =
                        libm::log(wave_squared) + 2.0 * libm::log(assignment_modulus);
                    let energy_log_scale =
                        libm::log(energy_prefactor) - denominator_log + damping_exponent;
                    rescued_energy_scaled.add(completed_squared_component(
                        charge_mode.real,
                        energy_log_scale + LOG_RESCUE_SCALE,
                    ));
                    rescued_energy_scaled.add(completed_squared_component(
                        charge_mode.imaginary,
                        energy_log_scale + LOG_RESCUE_SCALE,
                    ));
                    let influence_log_scale =
                        -denominator_log + damping_exponent + LOG_RESCUE_SCALE;
                    spectrum[grid_index] = Complex::new(
                        completed_scaled_component(charge_mode.real, influence_log_scale),
                        completed_scaled_component(charge_mode.imaginary, influence_log_scale),
                    );
                } else {
                    reciprocal_sum.add(regular_energy_mode);
                    spectrum[grid_index] = regular_grid_mode.scale(RESCUE_SCALE);
                }
            }
        }
    }
    ReciprocalOperator {
        energy: complete_energy(
            energy_prefactor,
            reciprocal_sum.total(),
            rescued_energy_scaled.total(),
            has_rescued_energy,
        ),
        grid_derivative_scale,
    }
}

fn complete_energy(
    energy_prefactor: f64,
    regular_reciprocal_sum: f64,
    rescued_energy_scaled: f64,
    has_rescued_energy: bool,
) -> f64 {
    if !has_rescued_energy {
        return energy_prefactor * regular_reciprocal_sum;
    }

    let mut combined_scaled = CompensatedSum::default();
    combined_scaled.add((energy_prefactor * RESCUE_SCALE) * regular_reciprocal_sum);
    combined_scaled.add(rescued_energy_scaled);
    combined_scaled.total() / RESCUE_SCALE
}

fn mode_requires_log_rescue(
    charge_mode: Complex,
    damping: f64,
    influence: f64,
    regular_grid_mode: Complex,
    regular_energy_mode: f64,
) -> bool {
    let has_charge = charge_mode.real != 0.0 || charge_mode.imaginary != 0.0;
    has_charge
        && (!damping.is_normal()
            || !influence.is_normal()
            || (charge_mode.real != 0.0 && !regular_grid_mode.real.is_normal())
            || (charge_mode.imaginary != 0.0 && !regular_grid_mode.imaginary.is_normal())
            || !regular_energy_mode.is_normal())
}

fn completed_squared_component(component: f64, log_scale: f64) -> f64 {
    if component == 0.0 {
        return 0.0;
    }
    completed_positive_from_log(log_scale + 2.0 * libm::log(component.abs()))
}

fn completed_scaled_component(component: f64, log_scale: f64) -> f64 {
    if component == 0.0 {
        return 0.0;
    }
    let magnitude = completed_positive_from_log(log_scale + libm::log(component.abs()));
    if component.is_sign_negative() {
        -magnitude
    } else {
        magnitude
    }
}

fn completed_positive_from_log(log_magnitude: f64) -> f64 {
    if log_magnitude <= LN_HALF_MIN_POSITIVE_SUBNORMAL {
        0.0
    } else {
        libm::exp(log_magnitude)
    }
}

struct ValidatedInput {
    dimensions: [usize; 3],
    mesh_point_count: usize,
    volume_angstrom_cubed: f64,
}

#[allow(clippy::too_many_lines)]
fn validate(
    input: &ParticleMeshReciprocalInput,
) -> Result<ValidatedInput, ParticleMeshReciprocalError> {
    if input.positions.is_empty() {
        return Err(ParticleMeshReciprocalError::new(
            ParticleMeshReciprocalErrorCode::EmptySystem,
            "at least one particle is required",
        ));
    }
    if input.positions.len() > MAX_PARTICLE_COUNT {
        return Err(ParticleMeshReciprocalError::new(
            ParticleMeshReciprocalErrorCode::CapacityExceeded,
            format!("particle count exceeds {MAX_PARTICLE_COUNT}"),
        ));
    }
    if input.positions.len() != input.charges_elementary.len() {
        return Err(ParticleMeshReciprocalError::new(
            ParticleMeshReciprocalErrorCode::ChargeCountMismatch,
            format!(
                "{} positions do not match {} charges",
                input.positions.len(),
                input.charges_elementary.len()
            ),
        ));
    }
    for (particle, position) in input.positions.iter().copied().enumerate() {
        for (axis, coordinate) in position.components().into_iter().enumerate() {
            if !coordinate.is_finite() {
                return Err(ParticleMeshReciprocalError::new(
                    ParticleMeshReciprocalErrorCode::NonFiniteCoordinate,
                    format!("position {particle} axis {axis} is not finite"),
                ));
            }
            if coordinate.abs() > MAX_ABSOLUTE_COORDINATE_ANGSTROM {
                return Err(invalid_parameter(format!(
                    "position {particle} axis {axis} exceeds absolute coordinate bound {MAX_ABSOLUTE_COORDINATE_ANGSTROM} angstrom"
                )));
            }
        }
    }
    for (particle, charge) in input.charges_elementary.iter().copied().enumerate() {
        if !charge.is_finite() {
            return Err(ParticleMeshReciprocalError::new(
                ParticleMeshReciprocalErrorCode::NonFiniteCharge,
                format!("charge {particle} is not finite"),
            ));
        }
        if charge.abs() > MAX_ABSOLUTE_CHARGE_ELEMENTARY
            || (charge != 0.0 && charge.abs() < MIN_NONZERO_ABSOLUTE_CHARGE_ELEMENTARY)
        {
            return Err(invalid_parameter(format!(
                "nonzero charge {particle} must have magnitude in [{MIN_NONZERO_ABSOLUTE_CHARGE_ELEMENTARY},{MAX_ABSOLUTE_CHARGE_ELEMENTARY}] elementary charge"
            )));
        }
    }
    let total_charge = accurate_order_independent_sum(&input.charges_elementary);
    if total_charge != 0.0 {
        return Err(ParticleMeshReciprocalError::new(
            ParticleMeshReciprocalErrorCode::NonNeutralSystem,
            format!("total charge {total_charge} is not exactly zero"),
        ));
    }

    for (axis, length) in input.cell.lengths_angstrom.iter().copied().enumerate() {
        if !length.is_finite()
            || !(MIN_CELL_LENGTH_ANGSTROM..=MAX_CELL_LENGTH_ANGSTROM).contains(&length)
        {
            return Err(ParticleMeshReciprocalError::new(
                ParticleMeshReciprocalErrorCode::InvalidCell,
                format!(
                    "cell length axis {axis} must lie in [{MIN_CELL_LENGTH_ANGSTROM},{MAX_CELL_LENGTH_ANGSTROM}] angstrom"
                ),
            ));
        }
    }
    let volume_angstrom_cubed = cell_volume(input.cell);
    if !volume_angstrom_cubed.is_finite() || volume_angstrom_cubed <= 0.0 {
        return Err(ParticleMeshReciprocalError::new(
            ParticleMeshReciprocalErrorCode::InvalidCell,
            "cell volume must be finite and positive",
        ));
    }
    require_parameter_range(
        input.settings.alpha_per_angstrom,
        MIN_ALPHA_PER_ANGSTROM,
        MAX_ALPHA_PER_ANGSTROM,
        "alpha_per_angstrom",
    )?;
    require_parameter_range(
        input.settings.dielectric,
        MIN_DIELECTRIC,
        MAX_DIELECTRIC,
        "dielectric",
    )?;

    let mut dimensions = [0_usize; 3];
    for (axis, dimension) in input.settings.mesh_dimensions.iter().copied().enumerate() {
        if !dimension.is_power_of_two()
            || !(MIN_MESH_DIMENSION..=MAX_MESH_DIMENSION).contains(&dimension)
        {
            return Err(ParticleMeshReciprocalError::new(
                ParticleMeshReciprocalErrorCode::InvalidMesh,
                format!(
                    "mesh axis {axis} must be a power of two in [{MIN_MESH_DIMENSION},{MAX_MESH_DIMENSION}]"
                ),
            ));
        }
        dimensions[axis] = dimension as usize;
    }
    let mesh_point_count = dimensions
        .into_iter()
        .try_fold(1_usize, usize::checked_mul)
        .ok_or_else(|| {
            ParticleMeshReciprocalError::new(
                ParticleMeshReciprocalErrorCode::CapacityExceeded,
                "mesh point count exceeds addressable capacity",
            )
        })?;
    if mesh_point_count > MAX_MESH_POINT_COUNT {
        return Err(ParticleMeshReciprocalError::new(
            ParticleMeshReciprocalErrorCode::CapacityExceeded,
            format!("mesh point count exceeds {MAX_MESH_POINT_COUNT}"),
        ));
    }
    validate_work_limit(dimensions, mesh_point_count, input.positions.len())?;
    Ok(ValidatedInput {
        dimensions,
        mesh_point_count,
        volume_angstrom_cubed,
    })
}

fn validate_work_limit(
    dimensions: [usize; 3],
    mesh_point_count: usize,
    particle_count: usize,
) -> Result<(), ParticleMeshReciprocalError> {
    let fft_stage_count = dimensions.into_iter().try_fold(0_usize, |sum, dimension| {
        sum.checked_add(
            usize::try_from(dimension.ilog2()).expect("validated mesh logarithm fits usize"),
        )
    });
    let mesh_work = fft_stage_count
        .and_then(|stages| stages.checked_add(1))
        .and_then(|stages_and_influence| mesh_point_count.checked_mul(stages_and_influence));
    let assignment_support_count = CARDINAL_B_SPLINE_ORDER
        .checked_mul(CARDINAL_B_SPLINE_ORDER)
        .and_then(|count| count.checked_mul(CARDINAL_B_SPLINE_ORDER))
        .expect("fixed assignment order has a representable support count");
    let particle_work = particle_count
        .checked_mul(assignment_support_count)
        .and_then(|work| work.checked_mul(4));
    let total_work = mesh_work
        .zip(particle_work)
        .and_then(|(mesh, particles)| mesh.checked_add(particles))
        .ok_or_else(|| {
            ParticleMeshReciprocalError::new(
                ParticleMeshReciprocalErrorCode::CapacityExceeded,
                "particle-mesh evaluation work exceeds addressable capacity",
            )
        })?;
    if total_work > MAX_EVALUATION_WORK_UNITS {
        return Err(ParticleMeshReciprocalError::new(
            ParticleMeshReciprocalErrorCode::CapacityExceeded,
            format!(
                "particle-mesh evaluation requires {total_work} work units, above {MAX_EVALUATION_WORK_UNITS}"
            ),
        ));
    }
    Ok(())
}

fn invalid_parameter(detail: impl Into<String>) -> ParticleMeshReciprocalError {
    ParticleMeshReciprocalError::new(ParticleMeshReciprocalErrorCode::InvalidParameter, detail)
}

fn require_parameter_range(
    value: f64,
    minimum: f64,
    maximum: f64,
    name: &str,
) -> Result<(), ParticleMeshReciprocalError> {
    if !value.is_finite() || !(minimum..=maximum).contains(&value) {
        return Err(invalid_parameter(format!(
            "{name} must lie in [{minimum},{maximum}]"
        )));
    }
    Ok(())
}

#[derive(Clone, Copy)]
struct AxisAssignment {
    indices: [usize; CARDINAL_B_SPLINE_ORDER],
    weights: [f64; CARDINAL_B_SPLINE_ORDER],
    derivatives: [f64; CARDINAL_B_SPLINE_ORDER],
}

#[derive(Clone, Copy)]
struct ParticleAssignment {
    axes: [AxisAssignment; 3],
}

fn assignment(
    position: Position,
    cell: OrthorhombicCell,
    dimensions: [usize; 3],
) -> ParticleAssignment {
    let coordinates = position.components();
    let axes = core::array::from_fn(|axis| {
        let length = cell.lengths_angstrom[axis];
        let reduced = reduce_periodically(coordinates[axis], length);
        let dimension = dimensions[axis];
        let dimension_f64 = bounded_usize_to_f64(dimension);
        let scaled = reduced / length * dimension_f64;
        let scaled = if scaled >= dimension_f64 { 0.0 } else { scaled };
        axis_assignment(scaled, dimension)
    });
    ParticleAssignment { axes }
}

fn reduce_periodically(coordinate: f64, length: f64) -> f64 {
    let reduced = coordinate.rem_euclid(length);
    if matches!(reduced.to_bits(), 0 | 0x8000_0000_0000_0000)
        || reduced.to_bits() == length.to_bits()
    {
        0.0
    } else if reduced < 0.0 {
        reduced + length
    } else if reduced > length {
        reduced - length
    } else {
        reduced
    }
}

#[allow(clippy::cast_possible_truncation, clippy::cast_sign_loss)]
fn axis_assignment(scaled: f64, dimension: usize) -> AxisAssignment {
    debug_assert!(scaled >= 0.0 && scaled < bounded_usize_to_f64(dimension));
    let base = libm::floor(scaled) as usize;
    let fraction = scaled - bounded_usize_to_f64(base);
    let fraction_squared = fraction * fraction;
    let fraction_cubed = fraction_squared * fraction;
    let one_minus_fraction = 1.0 - fraction;
    let weights = [
        one_minus_fraction * one_minus_fraction * one_minus_fraction / 6.0,
        (3.0 * fraction_cubed - 6.0 * fraction_squared + 4.0) / 6.0,
        (-3.0 * fraction_cubed + 3.0 * fraction_squared + 3.0 * fraction + 1.0) / 6.0,
        fraction_cubed / 6.0,
    ];
    let derivatives = [
        -0.5 * one_minus_fraction * one_minus_fraction,
        1.5 * fraction_squared - 2.0 * fraction,
        -1.5 * fraction_squared + fraction + 0.5,
        0.5 * fraction_squared,
    ];
    let indices = [
        (base + dimension - 1) % dimension,
        base % dimension,
        (base + 1) % dimension,
        (base + 2) % dimension,
    ];
    AxisAssignment {
        indices,
        weights,
        derivatives,
    }
}

fn spread_charges(
    grid: &mut [Complex],
    dimensions: [usize; 3],
    assignments: &[ParticleAssignment],
    charges: &[f64],
) {
    for (assignment, charge) in assignments.iter().zip(charges.iter().copied()) {
        for x_support in 0..CARDINAL_B_SPLINE_ORDER {
            for y_support in 0..CARDINAL_B_SPLINE_ORDER {
                for z_support in 0..CARDINAL_B_SPLINE_ORDER {
                    let x_axis = assignment.axes[0];
                    let y_axis = assignment.axes[1];
                    let z_axis = assignment.axes[2];
                    let grid_index = fft::index(
                        x_axis.indices[x_support],
                        y_axis.indices[y_support],
                        z_axis.indices[z_support],
                        dimensions,
                    );
                    grid[grid_index].real += charge
                        * x_axis.weights[x_support]
                        * y_axis.weights[y_support]
                        * z_axis.weights[z_support];
                }
            }
        }
    }
}

#[derive(Clone, Copy)]
struct ReciprocalAxisData {
    wave_squared: f64,
    assignment_modulus: f64,
}

fn reciprocal_axis_data(dimension: usize, cell_length: f64) -> Vec<ReciprocalAxisData> {
    (0..dimension)
        .map(|index| {
            let signed_index = signed_mesh_index(index, dimension);
            let wave = core::f64::consts::TAU * f64::from(signed_index) / cell_length;
            let angle =
                core::f64::consts::TAU * f64::from(signed_index) / bounded_usize_to_f64(dimension);
            ReciprocalAxisData {
                wave_squared: wave * wave,
                assignment_modulus: (2.0 + libm::cos(angle)) / 3.0,
            }
        })
        .collect()
}

fn signed_mesh_index(index: usize, dimension: usize) -> i32 {
    let index = i32::try_from(index).expect("validated mesh index fits i32");
    let dimension = i32::try_from(dimension).expect("validated mesh dimension fits i32");
    if index < dimension / 2 {
        index
    } else {
        index - dimension
    }
}

fn gather_forces(
    grid_derivative: &[Complex],
    dimensions: [usize; 3],
    assignments: &[ParticleAssignment],
    charges: &[f64],
    cell: OrthorhombicCell,
    grid_derivative_multiplier: f64,
) -> Vec<[f64; 3]> {
    assignments
        .iter()
        .zip(charges.iter().copied())
        .map(|(assignment, charge)| {
            core::array::from_fn(|derivative_axis| {
                let mut derivative = CompensatedSum::default();
                for x_support in 0..CARDINAL_B_SPLINE_ORDER {
                    for y_support in 0..CARDINAL_B_SPLINE_ORDER {
                        for z_support in 0..CARDINAL_B_SPLINE_ORDER {
                            let supports = [x_support, y_support, z_support];
                            let grid_index = fft::index(
                                assignment.axes[0].indices[x_support],
                                assignment.axes[1].indices[y_support],
                                assignment.axes[2].indices[z_support],
                                dimensions,
                            );
                            let mut weight_derivative = 1.0;
                            for (axis, support) in supports.iter().copied().enumerate() {
                                weight_derivative *= if axis == derivative_axis {
                                    assignment.axes[axis].derivatives[support]
                                } else {
                                    assignment.axes[axis].weights[support]
                                };
                            }
                            derivative.add(grid_derivative[grid_index].real * weight_derivative);
                        }
                    }
                }
                let force_scale = (-charge * bounded_usize_to_f64(dimensions[derivative_axis])
                    / cell.lengths_angstrom[derivative_axis])
                    * grid_derivative_multiplier;
                force_scale * derivative.total()
            })
        })
        .collect()
}

#[derive(Default)]
struct CompensatedSum {
    sum: f64,
    correction: f64,
}

impl CompensatedSum {
    fn add(&mut self, value: f64) {
        let updated = self.sum + value;
        self.correction += if self.sum.abs() >= value.abs() {
            (self.sum - updated) + value
        } else {
            (value - updated) + self.sum
        };
        self.sum = updated;
    }

    fn total(self) -> f64 {
        self.sum + self.correction
    }
}

fn accurate_order_independent_sum(values: &[f64]) -> f64 {
    let mut ordered = values.to_vec();
    ordered.sort_by(|left, right| {
        left.abs()
            .total_cmp(&right.abs())
            .then_with(|| left.total_cmp(right))
    });
    let mut sum = CompensatedSum::default();
    for value in ordered {
        sum.add(value);
    }
    sum.total()
}

fn cell_volume(cell: OrthorhombicCell) -> f64 {
    let mut lengths = cell.lengths_angstrom;
    lengths.sort_by(f64::total_cmp);
    (lengths[0] * lengths[2]) * lengths[1]
}

fn bounded_usize_to_f64(value: usize) -> f64 {
    f64::from(u32::try_from(value).expect("validated particle-mesh sizes fit u32"))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn small_input() -> ParticleMeshReciprocalInput {
        let mut input = ParticleMeshReciprocalInput::new(
            vec![
                Position::new(1.25, 2.5, 3.75),
                Position::new(5.1, 3.2, 8.4),
                Position::new(10.2, 12.3, 7.7),
                Position::new(15.4, 17.1, 19.3),
            ],
            vec![0.7, -0.4, -0.6, 0.300_000_000_000_000_04],
            OrthorhombicCell {
                lengths_angstrom: [18.0, 20.0, 22.0],
            },
        );
        input.settings = ParticleMeshReciprocalSettings {
            alpha_per_angstrom: 0.31,
            mesh_dimensions: [4, 8, 4],
            dielectric: 1.0,
        };
        input
    }

    #[test]
    fn assignment_weights_partition_unity_and_derivatives_sum_to_zero() {
        for scaled in [0.0, 0.125, 1.5, 3.999_999] {
            let assignment = axis_assignment(scaled, 4);
            assert!((assignment.weights.iter().sum::<f64>() - 1.0).abs() < 2.0e-16);
            assert!(assignment.derivatives.iter().sum::<f64>().abs() < 2.0e-16);
        }
    }

    #[test]
    fn cardinal_spline_knots_and_periodic_support_are_frozen() {
        let knot = axis_assignment(0.0, 4);
        assert_eq!(knot.indices, [3, 0, 1, 2]);
        assert_eq!(
            knot.weights.map(f64::to_bits),
            [1.0 / 6.0, 4.0 / 6.0, 1.0 / 6.0, 0.0].map(f64::to_bits)
        );
        assert_eq!(
            knot.derivatives.map(f64::to_bits),
            [-0.5, 0.0, 0.5, 0.0].map(f64::to_bits)
        );

        let half = axis_assignment(2.5, 4);
        assert_eq!(half.indices, [1, 2, 3, 0]);
        assert_eq!(
            half.weights.map(f64::to_bits),
            [1.0 / 48.0, 23.0 / 48.0, 23.0 / 48.0, 1.0 / 48.0].map(f64::to_bits)
        );
        assert_eq!(
            half.derivatives.map(f64::to_bits),
            [-1.0 / 8.0, -5.0 / 8.0, 5.0 / 8.0, 1.0 / 8.0].map(f64::to_bits)
        );
    }

    #[test]
    fn deposited_grid_charge_is_conserved() {
        let dimensions = [4, 8, 4];
        let positions = [
            Position::new(-0.125, 2.5, 3.75),
            Position::new(18.0, 19.999, 22.0),
        ];
        let cell = OrthorhombicCell {
            lengths_angstrom: [18.0, 20.0, 22.0],
        };
        let assignments = positions
            .iter()
            .copied()
            .map(|position| assignment(position, cell, dimensions))
            .collect::<Vec<_>>();
        let charges = [0.7, -0.2];
        let mut grid = vec![Complex::default(); dimensions.iter().product()];
        spread_charges(&mut grid, dimensions, &assignments, &charges);
        let mut deposited = CompensatedSum::default();
        for value in grid {
            deposited.add(value.real);
            assert_eq!(value.imaginary.to_bits(), 0);
        }
        assert_close(deposited.total(), 0.5, 3.0e-16);
    }

    #[test]
    fn radix_two_evaluation_matches_the_direct_dft_oracle() {
        let input = small_input();
        let fast = evaluate_with_transform(&input, fft::fft_3d).expect("FFT must evaluate");
        let direct = evaluate_with_transform(&input, direct_dft::direct_dft_3d)
            .expect("direct DFT must evaluate");
        assert_close(
            fast.reciprocal_space_kcal_per_mol,
            direct.reciprocal_space_kcal_per_mol,
            2.0e-12,
        );
        for (fast, direct) in fast
            .forces_kcal_per_mol_angstrom
            .iter()
            .flatten()
            .zip(direct.forces_kcal_per_mol_angstrom.iter().flatten())
        {
            assert_close(*fast, *direct, 7.0e-12);
        }
    }

    #[test]
    fn signed_frequency_mapping_uses_the_negative_even_grid_nyquist() {
        assert_eq!(
            (0..4)
                .map(|index| signed_mesh_index(index, 4))
                .collect::<Vec<_>>(),
            [0, 1, -2, -1]
        );
        assert_eq!(
            (0..8)
                .map(|index| signed_mesh_index(index, 8))
                .collect::<Vec<_>>(),
            [0, 1, 2, 3, -4, -3, -2, -1]
        );
    }

    #[test]
    fn reciprocal_energy_equals_half_grid_charge_potential_sum() {
        let input = small_input();
        let internal = compute_with_transform(&input, fft::fft_3d).expect("fixture must evaluate");
        let grid_identity = half_grid_charge_potential_sum(&internal);
        assert_close(
            internal.evaluation.reciprocal_space_kcal_per_mol,
            grid_identity,
            2.0e-13,
        );

        let mut rescue = ParticleMeshReciprocalInput::new(
            vec![Position::new(0.0, 0.0, 0.0), Position::new(4.0e8, 0.0, 0.0)],
            vec![16.0, -16.0],
            OrthorhombicCell {
                lengths_angstrom: [1.0e9, 1.0e-6, 1.0e-6],
            },
        );
        rescue.settings = ParticleMeshReciprocalSettings {
            alpha_per_angstrom: 1.15e-10,
            mesh_dimensions: [4; 3],
            dielectric: 1.0e-12,
        };
        let rescued =
            compute_with_transform(&rescue, fft::fft_3d).expect("rescue fixture must evaluate");
        let energy = rescued.evaluation.reciprocal_space_kcal_per_mol;
        let identity = half_grid_charge_potential_sum(&rescued);
        assert!(energy.is_normal() && identity.is_normal());
        let scale = energy.abs().max(identity.abs());
        assert!((energy - identity).abs() <= 2.0e-13 * scale);

        let rescued_direct = compute_with_transform(&rescue, direct_dft::direct_dft_3d)
            .expect("direct-DFT rescue fixture must evaluate");
        assert_relative_without_unit_floor(
            energy,
            rescued_direct.evaluation.reciprocal_space_kcal_per_mol,
            2.0e-12,
        );
        for (fast, direct) in rescued
            .evaluation
            .forces_kcal_per_mol_angstrom
            .iter()
            .flatten()
            .zip(
                rescued_direct
                    .evaluation
                    .forces_kcal_per_mol_angstrom
                    .iter()
                    .flatten(),
            )
        {
            if *fast != 0.0 || *direct != 0.0 {
                assert_relative_without_unit_floor(*fast, *direct, 2.0e-12);
            }
        }
    }

    fn half_grid_charge_potential_sum(internal: &InternalEvaluation) -> f64 {
        let mut grid_identity = CompensatedSum::default();
        for (charge, potential) in internal.charge_grid.iter().zip(&internal.grid_derivative) {
            grid_identity.add(charge.real * potential.real);
        }
        0.5 * grid_identity.total()
    }

    #[test]
    fn non_finite_transform_result_is_reported_transactionally() {
        fn poisoned_transform(values: &mut [Complex], dimensions: [usize; 3], inverse: bool) {
            fft::fft_3d(values, dimensions, inverse);
            if inverse {
                values[0].real = f64::INFINITY;
            }
        }

        let error = evaluate_with_transform(&small_input(), poisoned_transform)
            .expect_err("non-finite grid derivative must fail");
        assert_eq!(
            error.code(),
            ParticleMeshReciprocalErrorCode::NonFiniteResult
        );
    }

    #[test]
    fn scaled_rescue_accumulation_preserves_a_representable_positive_sum() {
        let minimum_subnormal = f64::from_bits(1);
        let individual_log = libm::log(minimum_subnormal) - libm::log(8.0);
        assert_eq!(completed_positive_from_log(individual_log).to_bits(), 0);

        let mut scaled = CompensatedSum::default();
        for _ in 0..8 {
            scaled.add(completed_positive_from_log(
                individual_log + LOG_RESCUE_SCALE,
            ));
        }
        let restored = scaled.total() / RESCUE_SCALE;
        assert_eq!(restored.to_bits(), minimum_subnormal.to_bits());
    }

    #[test]
    fn regular_and_rescue_energy_lanes_round_only_after_combination() {
        let minimum_subnormal = f64::from_bits(1);
        let regular_sum = f64::MIN_POSITIVE;
        let energy_prefactor = f64::from_bits(971_u64 << 52) * 0.375;
        let rescued_scaled = minimum_subnormal * RESCUE_SCALE * 0.375;

        assert_eq!((energy_prefactor * regular_sum).to_bits(), 0);
        assert_eq!((rescued_scaled / RESCUE_SCALE).to_bits(), 0);
        assert_eq!(
            complete_energy(energy_prefactor, regular_sum, rescued_scaled, true).to_bits(),
            minimum_subnormal.to_bits()
        );
    }

    #[test]
    fn analytic_assignment_force_matches_energy_finite_difference() {
        let input = small_input();
        let result = evaluate(&input).expect("fixture must evaluate");
        let step = 1.0e-6;
        for atom in 0..input.positions.len() {
            for axis in 0..3 {
                let mut minus = input.clone();
                let mut plus = input.clone();
                *coordinate_mut(&mut minus.positions[atom], axis) -= step;
                *coordinate_mut(&mut plus.positions[atom], axis) += step;
                let minus_energy = evaluate(&minus)
                    .expect("minus displacement must evaluate")
                    .reciprocal_space_kcal_per_mol;
                let plus_energy = evaluate(&plus)
                    .expect("plus displacement must evaluate")
                    .reciprocal_space_kcal_per_mol;
                let finite_difference_force = -(plus_energy - minus_energy) / (2.0 * step);
                assert_close(
                    result.forces_kcal_per_mol_angstrom[atom][axis],
                    finite_difference_force,
                    3.0e-7,
                );
            }
        }
    }

    fn coordinate_mut(position: &mut Position, axis: usize) -> &mut f64 {
        match axis {
            0 => &mut position.x_angstrom,
            1 => &mut position.y_angstrom,
            2 => &mut position.z_angstrom,
            _ => unreachable!(),
        }
    }

    fn assert_close(left: f64, right: f64, relative_tolerance: f64) {
        let scale = 1.0 + left.abs().max(right.abs());
        assert!(
            (left - right).abs() <= relative_tolerance * scale,
            "{left:.17e} differs from {right:.17e}"
        );
    }

    fn assert_relative_without_unit_floor(left: f64, right: f64, relative_tolerance: f64) {
        let scale = left.abs().max(right.abs());
        assert!(scale > 0.0);
        assert!(
            (left - right).abs() <= relative_tolerance * scale,
            "{left:.17e} differs from {right:.17e}"
        );
    }
}
