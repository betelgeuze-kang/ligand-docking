//! Independent deterministic Rust CPU kernel for order-4 particle-mesh
//! reciprocal electrostatics.
//!
//! This module implements only the reciprocal-space mesh term. It has no
//! dependency on the standalone scalar oracle and is not a full PME
//! implementation.

mod fft {
    //! Deterministic scalar complex transforms used by the reciprocal oracle.

    #[derive(Clone, Copy, Debug, Default, PartialEq)]
    pub(crate) struct Complex {
        pub(crate) real: f64,
        pub(crate) imaginary: f64,
    }

    impl Complex {
        pub(crate) const fn new(real: f64, imaginary: f64) -> Self {
            Self { real, imaginary }
        }

        pub(crate) fn norm_squared(self) -> f64 {
            self.real * self.real + self.imaginary * self.imaginary
        }

        pub(crate) fn scale(self, factor: f64) -> Self {
            Self::new(self.real * factor, self.imaginary * factor)
        }

        fn add(self, other: Self) -> Self {
            Self::new(self.real + other.real, self.imaginary + other.imaginary)
        }

        fn subtract(self, other: Self) -> Self {
            Self::new(self.real - other.real, self.imaginary - other.imaginary)
        }

        fn multiply(self, other: Self) -> Self {
            Self::new(
                self.real * other.real - self.imaginary * other.imaginary,
                self.real * other.imaginary + self.imaginary * other.real,
            )
        }
    }

    /// Apply the frozen separable z, y, x transform order in place.
    pub(crate) fn fft_3d(
        values: &mut [Complex],
        dimensions: [usize; 3],
        inverse: bool,
    ) -> Result<(), super::AllocationFailure> {
        transform_3d_with(values, dimensions, inverse, fft_1d)
    }

    fn fft_1d(values: &mut [Complex], inverse: bool) {
        let count = values.len();
        debug_assert!(count.is_power_of_two());

        let mut target = 0_usize;
        for source in 1..count {
            let mut bit = count >> 1;
            while target & bit != 0 {
                target ^= bit;
                bit >>= 1;
            }
            target ^= bit;
            if source < target {
                values.swap(source, target);
            }
        }

        let mut span = 2_usize;
        while span <= count {
            let direction = if inverse { 1.0 } else { -1.0 };
            let angle = direction * core::f64::consts::TAU / bounded_usize_to_f64(span);
            let root = Complex::new(libm::cos(angle), libm::sin(angle));
            for start in (0..count).step_by(span) {
                let mut twiddle = Complex::new(1.0, 0.0);
                for offset in 0..span / 2 {
                    let even = values[start + offset];
                    let odd = values[start + offset + span / 2].multiply(twiddle);
                    values[start + offset] = even.add(odd);
                    values[start + offset + span / 2] = even.subtract(odd);
                    twiddle = twiddle.multiply(root);
                }
            }
            span *= 2;
        }

        if inverse {
            let normalization = 1.0 / bounded_usize_to_f64(count);
            for value in values {
                *value = value.scale(normalization);
            }
        }
    }

    fn bounded_usize_to_f64(value: usize) -> f64 {
        f64::from(u32::try_from(value).expect("validated FFT sizes fit u32"))
    }

    fn transform_3d_with(
        values: &mut [Complex],
        dimensions: [usize; 3],
        inverse: bool,
        transform_1d: fn(&mut [Complex], bool),
    ) -> Result<(), super::AllocationFailure> {
        let [x_count, y_count, z_count] = dimensions;
        debug_assert_eq!(values.len(), x_count * y_count * z_count);
        let line_count = x_count.max(y_count).max(z_count);
        let mut line = Vec::new();
        super::fallible_reserve_exact(
            &mut line,
            line_count,
            super::AllocationSite::FftLineScratch,
        )?;
        line.resize(line_count, Complex::default());

        for x in 0..x_count {
            for y in 0..y_count {
                for z in 0..z_count {
                    line[z] = values[index(x, y, z, dimensions)];
                }
                transform_1d(&mut line[..z_count], inverse);
                for z in 0..z_count {
                    values[index(x, y, z, dimensions)] = line[z];
                }
            }
        }
        for x in 0..x_count {
            for z in 0..z_count {
                for y in 0..y_count {
                    line[y] = values[index(x, y, z, dimensions)];
                }
                transform_1d(&mut line[..y_count], inverse);
                for y in 0..y_count {
                    values[index(x, y, z, dimensions)] = line[y];
                }
            }
        }
        for y in 0..y_count {
            for z in 0..z_count {
                for x in 0..x_count {
                    line[x] = values[index(x, y, z, dimensions)];
                }
                transform_1d(&mut line[..x_count], inverse);
                for x in 0..x_count {
                    values[index(x, y, z, dimensions)] = line[x];
                }
            }
        }
        Ok(())
    }

    pub(crate) const fn index(x: usize, y: usize, z: usize, dimensions: [usize; 3]) -> usize {
        (x * dimensions[1] + y) * dimensions[2] + z
    }
}

use std::cell::Cell;
use std::error::Error;
use std::fmt;
use std::mem::{align_of, size_of};
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::ptr;

use fft::Complex;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum AllocationSite {
    FftLineScratch,
    ParticleAssignments,
    Spectrum,
    ReciprocalAxisData,
    ForceOutput,
    NeutralitySort,
    ProviderChannelCopy,
    ProviderPositions,
}

impl AllocationSite {
    const fn detail(self) -> &'static str {
        match self {
            Self::FftLineScratch => "particle-mesh FFT line scratch allocation failed",
            Self::ParticleAssignments => "particle assignment allocation failed",
            Self::Spectrum => "particle-mesh spectrum allocation failed",
            Self::ReciprocalAxisData => "reciprocal axis-data allocation failed",
            Self::ForceOutput => "particle force-output allocation failed",
            Self::NeutralitySort => "neutrality summation scratch allocation failed",
            Self::ProviderChannelCopy => "provider input-channel copy allocation failed",
            Self::ProviderPositions => "provider position copy allocation failed",
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct AllocationFailure {
    site: AllocationSite,
}

fn fallible_reserve_exact<T>(
    values: &mut Vec<T>,
    additional: usize,
    site: AllocationSite,
) -> Result<(), AllocationFailure> {
    #[cfg(test)]
    if INJECTED_ALLOCATION_FAILURE.with(|injected| injected.get() == Some(site)) {
        return Err(AllocationFailure { site });
    }
    values
        .try_reserve_exact(additional)
        .map_err(|_| AllocationFailure { site })
}

#[cfg(test)]
thread_local! {
    static INJECTED_ALLOCATION_FAILURE: Cell<Option<AllocationSite>> = const { Cell::new(None) };
}

#[cfg(test)]
struct AllocationFailureGuard {
    previous: Option<AllocationSite>,
}

#[cfg(test)]
impl AllocationFailureGuard {
    fn inject(site: AllocationSite) -> Self {
        let previous = INJECTED_ALLOCATION_FAILURE.with(|injected| {
            let previous = injected.get();
            injected.set(Some(site));
            previous
        });
        Self { previous }
    }
}

#[cfg(test)]
impl Drop for AllocationFailureGuard {
    fn drop(&mut self) {
        INJECTED_ALLOCATION_FAILURE.with(|injected| injected.set(self.previous));
    }
}

/// Frozen semantic version for this particle-mesh reciprocal calculation.
#[cfg(test)]
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
    #[cfg(test)]
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
    code: Option<ParticleMeshReciprocalErrorCode>,
    detail: &'static str,
}

impl ParticleMeshReciprocalError {
    fn new(code: ParticleMeshReciprocalErrorCode, detail: &'static str) -> Self {
        Self {
            code: Some(code),
            detail,
        }
    }

    #[cfg(test)]
    #[must_use]
    pub fn code(&self) -> ParticleMeshReciprocalErrorCode {
        self.code.expect("typed particle-mesh failure has a code")
    }

    #[cfg(test)]
    #[must_use]
    pub fn detail(&self) -> &str {
        self.detail
    }
}

impl fmt::Display for ParticleMeshReciprocalError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        if let Some(code) = self.code {
            write!(formatter, "{code:?}: {}", self.detail)
        } else {
            write!(formatter, "OutOfMemory: {}", self.detail)
        }
    }
}

impl Error for ParticleMeshReciprocalError {}

impl From<AllocationFailure> for ParticleMeshReciprocalError {
    fn from(failure: AllocationFailure) -> Self {
        Self {
            code: None,
            detail: failure.site.detail(),
        }
    }
}

type Transform3d = fn(&mut [Complex], [usize; 3], bool) -> Result<(), AllocationFailure>;

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
#[cfg(test)]
pub fn evaluate(
    input: &ParticleMeshReciprocalInput,
) -> Result<ParticleMeshReciprocalEvaluation, ParticleMeshReciprocalError> {
    evaluate_with_force_option(input, true)
}

fn evaluate_with_force_option(
    input: &ParticleMeshReciprocalInput,
    compute_forces: bool,
) -> Result<ParticleMeshReciprocalEvaluation, ParticleMeshReciprocalError> {
    evaluate_with_transform(input, fft::fft_3d, compute_forces)
}

fn evaluate_with_transform(
    input: &ParticleMeshReciprocalInput,
    transform: Transform3d,
    compute_forces: bool,
) -> Result<ParticleMeshReciprocalEvaluation, ParticleMeshReciprocalError> {
    Ok(compute_with_transform(input, transform, compute_forces)?.evaluation)
}

struct InternalEvaluation {
    evaluation: ParticleMeshReciprocalEvaluation,
}

fn compute_with_transform(
    input: &ParticleMeshReciprocalInput,
    transform: Transform3d,
    compute_forces: bool,
) -> Result<InternalEvaluation, ParticleMeshReciprocalError> {
    let validated = validate(input)?;
    let mut assignments = Vec::new();
    fallible_reserve_exact(
        &mut assignments,
        input.positions.len(),
        AllocationSite::ParticleAssignments,
    )
    .map_err(ParticleMeshReciprocalError::from)?;
    assignments.extend(
        input
            .positions
            .iter()
            .copied()
            .map(|position| assignment(position, input.cell, validated.dimensions)),
    );
    let mut spectrum = Vec::new();
    fallible_reserve_exact(
        &mut spectrum,
        validated.mesh_point_count,
        AllocationSite::Spectrum,
    )
    .map_err(ParticleMeshReciprocalError::from)?;
    spectrum.resize(validated.mesh_point_count, Complex::default());
    spread_charges(
        &mut spectrum,
        validated.dimensions,
        &assignments,
        &input.charges_elementary,
    );
    transform(&mut spectrum, validated.dimensions, false)
        .map_err(ParticleMeshReciprocalError::from)?;

    let reciprocal = apply_reciprocal_operator(input, &validated, &mut spectrum)?;
    let reciprocal_space_kcal_per_mol = reciprocal.energy;

    let forces_kcal_per_mol_angstrom = if compute_forces {
        transform(&mut spectrum, validated.dimensions, true)
            .map_err(ParticleMeshReciprocalError::from)?;
        let scaled_grid_multiplier = reciprocal.grid_derivative_scale / RESCUE_SCALE;
        let forces = gather_forces(
            &spectrum,
            validated.dimensions,
            &assignments,
            &input.charges_elementary,
            input.cell,
            scaled_grid_multiplier,
        )
        .map_err(ParticleMeshReciprocalError::from)?;
        for value in &mut spectrum {
            *value = value.scale(scaled_grid_multiplier);
        }
        forces
    } else {
        Vec::new()
    };

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
) -> Result<ReciprocalOperator, ParticleMeshReciprocalError> {
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
        )
        .map_err(ParticleMeshReciprocalError::from)?;
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
    Ok(ReciprocalOperator {
        energy: complete_energy(
            energy_prefactor,
            reciprocal_sum.total(),
            rescued_energy_scaled.total(),
            has_rescued_energy,
        ),
        grid_derivative_scale,
    })
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
            "particle count exceeds the frozen maximum",
        ));
    }
    if input.positions.len() != input.charges_elementary.len() {
        return Err(ParticleMeshReciprocalError::new(
            ParticleMeshReciprocalErrorCode::ChargeCountMismatch,
            "position count does not match charge count",
        ));
    }
    for position in input.positions.iter().copied() {
        for coordinate in position.components() {
            if !coordinate.is_finite() {
                return Err(ParticleMeshReciprocalError::new(
                    ParticleMeshReciprocalErrorCode::NonFiniteCoordinate,
                    "a particle coordinate is not finite",
                ));
            }
            if coordinate.abs() > MAX_ABSOLUTE_COORDINATE_ANGSTROM {
                return Err(invalid_parameter(
                    "a particle coordinate exceeds the frozen absolute bound",
                ));
            }
        }
    }
    for charge in input.charges_elementary.iter().copied() {
        if !charge.is_finite() {
            return Err(ParticleMeshReciprocalError::new(
                ParticleMeshReciprocalErrorCode::NonFiniteCharge,
                "a particle charge is not finite",
            ));
        }
        if charge.abs() > MAX_ABSOLUTE_CHARGE_ELEMENTARY
            || (charge != 0.0 && charge.abs() < MIN_NONZERO_ABSOLUTE_CHARGE_ELEMENTARY)
        {
            return Err(invalid_parameter(
                "a nonzero charge is outside the frozen magnitude range",
            ));
        }
    }
    let total_charge = accurate_order_independent_sum(&input.charges_elementary)
        .map_err(ParticleMeshReciprocalError::from)?;
    if total_charge != 0.0 {
        return Err(ParticleMeshReciprocalError::new(
            ParticleMeshReciprocalErrorCode::NonNeutralSystem,
            "compensated total charge is not exactly zero",
        ));
    }

    for length in input.cell.lengths_angstrom {
        if !length.is_finite()
            || !(MIN_CELL_LENGTH_ANGSTROM..=MAX_CELL_LENGTH_ANGSTROM).contains(&length)
        {
            return Err(ParticleMeshReciprocalError::new(
                ParticleMeshReciprocalErrorCode::InvalidCell,
                "a cell length is outside the frozen finite positive range",
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
        "alpha_per_angstrom is outside the frozen finite positive range",
    )?;
    require_parameter_range(
        input.settings.dielectric,
        MIN_DIELECTRIC,
        MAX_DIELECTRIC,
        "dielectric is outside the frozen finite positive range",
    )?;

    let mut dimensions = [0_usize; 3];
    for (axis, dimension) in input.settings.mesh_dimensions.iter().copied().enumerate() {
        if !dimension.is_power_of_two()
            || !(MIN_MESH_DIMENSION..=MAX_MESH_DIMENSION).contains(&dimension)
        {
            return Err(ParticleMeshReciprocalError::new(
                ParticleMeshReciprocalErrorCode::InvalidMesh,
                "a mesh dimension is not a supported power of two",
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
            "mesh point count exceeds the frozen maximum",
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
            "particle-mesh evaluation exceeds the frozen work limit",
        ));
    }
    Ok(())
}

fn invalid_parameter(detail: &'static str) -> ParticleMeshReciprocalError {
    ParticleMeshReciprocalError::new(ParticleMeshReciprocalErrorCode::InvalidParameter, detail)
}

fn require_parameter_range(
    value: f64,
    minimum: f64,
    maximum: f64,
    detail: &'static str,
) -> Result<(), ParticleMeshReciprocalError> {
    if !value.is_finite() || !(minimum..=maximum).contains(&value) {
        return Err(invalid_parameter(detail));
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

fn reciprocal_axis_data(
    dimension: usize,
    cell_length: f64,
) -> Result<Vec<ReciprocalAxisData>, AllocationFailure> {
    let mut data = Vec::new();
    fallible_reserve_exact(&mut data, dimension, AllocationSite::ReciprocalAxisData)?;
    for index in 0..dimension {
        let signed_index = signed_mesh_index(index, dimension);
        let wave = core::f64::consts::TAU * f64::from(signed_index) / cell_length;
        let angle =
            core::f64::consts::TAU * f64::from(signed_index) / bounded_usize_to_f64(dimension);
        data.push(ReciprocalAxisData {
            wave_squared: wave * wave,
            assignment_modulus: (2.0 + libm::cos(angle)) / 3.0,
        });
    }
    Ok(data)
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
) -> Result<Vec<[f64; 3]>, AllocationFailure> {
    let mut forces = Vec::new();
    fallible_reserve_exact(&mut forces, assignments.len(), AllocationSite::ForceOutput)?;
    for (assignment, charge) in assignments.iter().zip(charges.iter().copied()) {
        forces.push(core::array::from_fn(|derivative_axis| {
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
        }));
    }
    Ok(forces)
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

fn accurate_order_independent_sum(values: &[f64]) -> Result<f64, AllocationFailure> {
    let mut ordered = Vec::new();
    fallible_reserve_exact(&mut ordered, values.len(), AllocationSite::NeutralitySort)?;
    ordered.extend_from_slice(values);
    ordered.sort_unstable_by(|left, right| {
        left.abs()
            .total_cmp(&right.abs())
            .then_with(|| left.total_cmp(right))
    });
    let mut sum = CompensatedSum::default();
    for value in ordered {
        sum.add(value);
    }
    Ok(sum.total())
}

fn cell_volume(cell: OrthorhombicCell) -> f64 {
    let mut lengths = cell.lengths_angstrom;
    lengths.sort_unstable_by(f64::total_cmp);
    (lengths[0] * lengths[2]) * lengths[1]
}

fn bounded_usize_to_f64(value: usize) -> f64 {
    f64::from(u32::try_from(value).expect("validated particle-mesh sizes fit u32"))
}

const PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION: u32 = 1;
const PARTICLE_MESH_RECIPROCAL_ERROR_CAPACITY: usize = 256;
const STATUS_OK: i32 = 0;
const STATUS_INVALID_ARGUMENT: i32 = 1;
const STATUS_ABI_MISMATCH: i32 = 2;
const STATUS_OUT_OF_MEMORY: i32 = 5;
const STATUS_CAPACITY_OVERFLOW: i32 = 6;
const STATUS_INTERNAL_ERROR: i32 = 9;
const STATUS_NUMERICAL_ERROR: i32 = 10;

#[repr(i32)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum ParticleMeshReciprocalErrorCodeV1 {
    None = 0,
    EmptySystem = 1,
    CapacityExceeded = 2,
    ChargeCountMismatch = 3,
    NonFiniteCoordinate = 4,
    NonFiniteCharge = 5,
    NonNeutralSystem = 6,
    InvalidCell = 7,
    InvalidParameter = 8,
    InvalidMesh = 9,
    NonFiniteResult = 10,
}

impl From<ParticleMeshReciprocalErrorCode> for ParticleMeshReciprocalErrorCodeV1 {
    fn from(value: ParticleMeshReciprocalErrorCode) -> Self {
        match value {
            ParticleMeshReciprocalErrorCode::EmptySystem => Self::EmptySystem,
            ParticleMeshReciprocalErrorCode::CapacityExceeded => Self::CapacityExceeded,
            ParticleMeshReciprocalErrorCode::ChargeCountMismatch => Self::ChargeCountMismatch,
            ParticleMeshReciprocalErrorCode::NonFiniteCoordinate => Self::NonFiniteCoordinate,
            ParticleMeshReciprocalErrorCode::NonFiniteCharge => Self::NonFiniteCharge,
            ParticleMeshReciprocalErrorCode::NonNeutralSystem => Self::NonNeutralSystem,
            ParticleMeshReciprocalErrorCode::InvalidCell => Self::InvalidCell,
            ParticleMeshReciprocalErrorCode::InvalidParameter => Self::InvalidParameter,
            ParticleMeshReciprocalErrorCode::InvalidMesh => Self::InvalidMesh,
            ParticleMeshReciprocalErrorCode::NonFiniteResult => Self::NonFiniteResult,
        }
    }
}

#[repr(C)]
#[derive(Clone, Copy)]
pub(crate) struct ParticleMeshReciprocalSystemV1 {
    struct_size: u32,
    abi_version: u32,
    atom_count: usize,
    position_x: *const f64,
    position_y: *const f64,
    position_z: *const f64,
    charge: *const f64,
    reserved: [u64; 4],
}

#[repr(C)]
#[derive(Clone, Copy)]
pub(crate) struct ParticleMeshReciprocalModelV1 {
    struct_size: u32,
    abi_version: u32,
    cell_lengths_angstrom: [f64; 3],
    alpha_per_angstrom: f64,
    mesh_dimensions: [u32; 3],
    reserved0: u32,
    dielectric: f64,
    reserved: [u64; 4],
}

#[repr(C)]
#[derive(Clone, Copy)]
pub(crate) struct ParticleMeshReciprocalEnergyV1 {
    struct_size: u32,
    abi_version: u32,
    reciprocal_space_kcal_per_mol: f64,
    reserved: [u64; 4],
}

#[repr(C)]
#[derive(Clone, Copy)]
pub(crate) struct ParticleMeshReciprocalForceOutputV1 {
    struct_size: u32,
    abi_version: u32,
    capacity: usize,
    x: *mut f64,
    y: *mut f64,
    z: *mut f64,
    reserved: [u64; 4],
}

#[repr(C)]
#[derive(Clone, Copy)]
pub(crate) struct ParticleMeshReciprocalErrorV1 {
    struct_size: u32,
    abi_version: u32,
    typed_code: i32,
    reserved0: u32,
    detail: [u8; PARTICLE_MESH_RECIPROCAL_ERROR_CAPACITY],
    reserved: [u64; 4],
}

#[derive(Clone, Copy, Debug)]
struct MemoryRange {
    begin: usize,
    end: usize,
}

#[derive(Debug)]
struct ProviderFailure {
    status: i32,
    code: ParticleMeshReciprocalErrorCodeV1,
    detail: &'static str,
    may_write_error: bool,
}

impl ProviderFailure {
    fn new(status: i32, code: ParticleMeshReciprocalErrorCodeV1, detail: &'static str) -> Self {
        Self {
            status,
            code,
            detail,
            may_write_error: true,
        }
    }

    fn invalid(detail: &'static str) -> Self {
        Self::new(
            STATUS_INVALID_ARGUMENT,
            ParticleMeshReciprocalErrorCodeV1::None,
            detail,
        )
    }

    fn abi(detail: &'static str) -> Self {
        Self::new(
            STATUS_ABI_MISMATCH,
            ParticleMeshReciprocalErrorCodeV1::None,
            detail,
        )
    }

    fn capacity(detail: &'static str) -> Self {
        Self::new(
            STATUS_CAPACITY_OVERFLOW,
            ParticleMeshReciprocalErrorCodeV1::CapacityExceeded,
            detail,
        )
    }

    fn out_of_memory(detail: &'static str) -> Self {
        Self::new(
            STATUS_OUT_OF_MEMORY,
            ParticleMeshReciprocalErrorCodeV1::None,
            detail,
        )
    }

    fn without_error_write(mut self) -> Self {
        self.may_write_error = false;
        self
    }
}

impl From<ParticleMeshReciprocalError> for ProviderFailure {
    fn from(error: ParticleMeshReciprocalError) -> Self {
        let Some(code) = error.code else {
            return Self::new(
                STATUS_OUT_OF_MEMORY,
                ParticleMeshReciprocalErrorCodeV1::None,
                error.detail,
            );
        };
        let status = match code {
            ParticleMeshReciprocalErrorCode::CapacityExceeded => STATUS_CAPACITY_OVERFLOW,
            ParticleMeshReciprocalErrorCode::NonNeutralSystem
            | ParticleMeshReciprocalErrorCode::NonFiniteResult => STATUS_NUMERICAL_ERROR,
            _ => STATUS_INVALID_ARGUMENT,
        };
        Self::new(status, code.into(), error.detail)
    }
}

impl From<AllocationFailure> for ProviderFailure {
    fn from(failure: AllocationFailure) -> Self {
        Self::out_of_memory(failure.site.detail())
    }
}

struct ProviderCandidate {
    energy: ParticleMeshReciprocalEnergyV1,
    forces: Vec<[f64; 3]>,
    force_output: Option<ParticleMeshReciprocalForceOutputV1>,
}

fn reserved_is_zero(values: &[u64]) -> bool {
    values.iter().all(|value| *value == 0)
}

fn validate_header<T>(
    struct_size: u32,
    abi_version: u32,
    reserved: &[u64],
    _label: &'static str,
) -> Result<(), ProviderFailure> {
    if usize::try_from(struct_size).ok() != Some(size_of::<T>()) {
        return Err(ProviderFailure::abi(
            "provider descriptor struct size does not match the ABI",
        ));
    }
    if abi_version != PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION {
        return Err(ProviderFailure::abi(
            "provider descriptor ABI version does not match",
        ));
    }
    if !reserved_is_zero(reserved) {
        return Err(ProviderFailure::abi(
            "provider descriptor reserved fields must be zero",
        ));
    }
    Ok(())
}

fn checked_range<T>(
    pointer: *const T,
    length: usize,
    detail: &'static str,
) -> Result<Option<MemoryRange>, ProviderFailure> {
    if length == 0 {
        return Ok(None);
    }
    if pointer.is_null() {
        return Err(ProviderFailure::invalid(detail));
    }
    if (pointer as usize) % align_of::<T>() != 0 {
        return Err(ProviderFailure::invalid(
            "provider pointer is not naturally aligned",
        ));
    }
    if length > (isize::MAX as usize) / size_of::<T>() {
        return Err(ProviderFailure::capacity(
            "provider range exceeds addressable capacity",
        ));
    }
    let byte_count = length * size_of::<T>();
    let begin = pointer as usize;
    let end = begin.checked_add(byte_count).ok_or_else(|| {
        ProviderFailure::capacity("provider pointer range overflows addressable capacity")
    })?;
    Ok(Some(MemoryRange { begin, end }))
}

fn ranges_overlap(first: MemoryRange, second: MemoryRange) -> bool {
    first.begin < second.end && second.begin < first.end
}

fn require_disjoint_outputs(mutable_ranges: &[Option<MemoryRange>]) -> Result<(), ProviderFailure> {
    for first_index in 0..mutable_ranges.len() {
        let Some(first) = mutable_ranges[first_index] else {
            continue;
        };
        for &second in &mutable_ranges[(first_index + 1)..] {
            if second.is_some_and(|second| ranges_overlap(first, second)) {
                return Err(ProviderFailure::invalid(
                    "particle-mesh reciprocal mutable output regions must not overlap",
                ));
            }
        }
    }
    Ok(())
}

fn overlaps_any(range: MemoryRange, candidates: &[Option<MemoryRange>]) -> bool {
    candidates
        .iter()
        .flatten()
        .copied()
        .any(|candidate| ranges_overlap(range, candidate))
}

unsafe fn copy_validated_slice<T: Copy>(
    pointer: *const T,
    length: usize,
    site: AllocationSite,
) -> Result<Vec<T>, ProviderFailure> {
    if length == 0 {
        return Ok(Vec::new());
    }
    let mut values = Vec::new();
    fallible_reserve_exact(&mut values, length, site).map_err(ProviderFailure::from)?;
    // SAFETY: The caller supplies `length` initialized elements and the range
    // and alignment were preflighted. Copying removes all input borrows before
    // any output is committed.
    values.extend_from_slice(unsafe { core::slice::from_raw_parts(pointer, length) });
    Ok(values)
}

fn provider_input(
    system: ParticleMeshReciprocalSystemV1,
    model: ParticleMeshReciprocalModelV1,
) -> Result<ParticleMeshReciprocalInput, ProviderFailure> {
    // SAFETY: Private-ABI channels were fully preflighted for range, alignment,
    // and aliasing and remain initialized for the call.
    let position_x = unsafe {
        copy_validated_slice(
            system.position_x,
            system.atom_count,
            AllocationSite::ProviderChannelCopy,
        )?
    };
    // SAFETY: Same channel contract as position_x.
    let position_y = unsafe {
        copy_validated_slice(
            system.position_y,
            system.atom_count,
            AllocationSite::ProviderChannelCopy,
        )?
    };
    // SAFETY: Same channel contract as position_x.
    let position_z = unsafe {
        copy_validated_slice(
            system.position_z,
            system.atom_count,
            AllocationSite::ProviderChannelCopy,
        )?
    };
    // SAFETY: Same channel contract as position_x.
    let charges = unsafe {
        copy_validated_slice(
            system.charge,
            system.atom_count,
            AllocationSite::ProviderChannelCopy,
        )?
    };

    let mut positions = Vec::new();
    fallible_reserve_exact(
        &mut positions,
        system.atom_count,
        AllocationSite::ProviderPositions,
    )
    .map_err(ProviderFailure::from)?;
    positions.extend(
        position_x
            .into_iter()
            .zip(position_y)
            .zip(position_z)
            .map(|((x, y), z)| Position::new(x, y, z)),
    );
    Ok(ParticleMeshReciprocalInput {
        positions,
        charges_elementary: charges,
        cell: OrthorhombicCell {
            lengths_angstrom: model.cell_lengths_angstrom,
        },
        settings: ParticleMeshReciprocalSettings {
            alpha_per_angstrom: model.alpha_per_angstrom,
            mesh_dimensions: model.mesh_dimensions,
            dielectric: model.dielectric,
        },
    })
}

unsafe fn evaluate_provider_impl(
    system_pointer: *const ParticleMeshReciprocalSystemV1,
    model_pointer: *const ParticleMeshReciprocalModelV1,
    compute_forces: u8,
    energy_pointer: *mut ParticleMeshReciprocalEnergyV1,
    force_pointer: *mut ParticleMeshReciprocalForceOutputV1,
    error_range: MemoryRange,
    alias_safety: &Cell<bool>,
) -> Result<ProviderCandidate, ProviderFailure> {
    let system_range = checked_range(system_pointer, 1, "system descriptor is null")
        .map_err(ProviderFailure::without_error_write)?
        .expect("one-element system descriptor has a range");
    let model_range = checked_range(model_pointer, 1, "model descriptor is null")
        .map_err(ProviderFailure::without_error_write)?
        .expect("one-element model descriptor has a range");
    let energy_range = checked_range(energy_pointer.cast_const(), 1, "energy descriptor is null")
        .map_err(ProviderFailure::without_error_write)?
        .expect("one-element energy descriptor has a range");
    let force_descriptor_range = if force_pointer.is_null() {
        None
    } else {
        checked_range(force_pointer.cast_const(), 1, "force descriptor is null")
            .map_err(ProviderFailure::without_error_write)?
    };
    let descriptor_ranges = [
        Some(system_range),
        Some(model_range),
        Some(energy_range),
        force_descriptor_range,
    ];
    if overlaps_any(error_range, &descriptor_ranges) {
        return Err(ProviderFailure::invalid(
            "error output must not overlap a provider descriptor",
        )
        .without_error_write());
    }

    // SAFETY: Every fixed-size descriptor range was checked for non-nullness
    // and natural alignment, and none overlaps writable error storage.
    let system = unsafe { ptr::read(system_pointer) };
    // SAFETY: Same preflight contract as system.
    let model = unsafe { ptr::read(model_pointer) };
    // SAFETY: Same preflight contract as system.
    let energy_output = unsafe { ptr::read(energy_pointer) };
    let preflight_force_output = if force_pointer.is_null() {
        None
    } else {
        // SAFETY: The non-null force descriptor passed the fixed-range
        // preflight and does not overlap error storage.
        Some(unsafe { ptr::read(force_pointer) })
    };

    let input_channel_ranges = [
        checked_range(
            system.position_x,
            system.atom_count,
            "position_x channel is null",
        )
        .map_err(ProviderFailure::without_error_write)?,
        checked_range(
            system.position_y,
            system.atom_count,
            "position_y channel is null",
        )
        .map_err(ProviderFailure::without_error_write)?,
        checked_range(
            system.position_z,
            system.atom_count,
            "position_z channel is null",
        )
        .map_err(ProviderFailure::without_error_write)?,
        checked_range(system.charge, system.atom_count, "charge channel is null")
            .map_err(ProviderFailure::without_error_write)?,
    ];
    let force_channel_ranges = if let Some(output) = preflight_force_output {
        [
            checked_range(
                output.x.cast_const(),
                system.atom_count,
                "force x output is null",
            )
            .map_err(ProviderFailure::without_error_write)?,
            checked_range(
                output.y.cast_const(),
                system.atom_count,
                "force y output is null",
            )
            .map_err(ProviderFailure::without_error_write)?,
            checked_range(
                output.z.cast_const(),
                system.atom_count,
                "force z output is null",
            )
            .map_err(ProviderFailure::without_error_write)?,
        ]
    } else {
        [None; 3]
    };
    if overlaps_any(error_range, &input_channel_ranges)
        || overlaps_any(error_range, &force_channel_ranges)
    {
        return Err(ProviderFailure::invalid(
            "error output must not overlap an input or force channel",
        )
        .without_error_write());
    }
    alias_safety.set(true);

    if !matches!(compute_forces, 0 | 1) {
        return Err(ProviderFailure::invalid(
            "compute_forces must be exactly zero or one",
        ));
    }
    validate_header::<ParticleMeshReciprocalSystemV1>(
        system.struct_size,
        system.abi_version,
        &system.reserved,
        "system",
    )?;
    validate_header::<ParticleMeshReciprocalModelV1>(
        model.struct_size,
        model.abi_version,
        &model.reserved,
        "model",
    )?;
    if model.reserved0 != 0 {
        return Err(ProviderFailure::abi("model reserved0 must be zero"));
    }
    validate_header::<ParticleMeshReciprocalEnergyV1>(
        energy_output.struct_size,
        energy_output.abi_version,
        &energy_output.reserved,
        "energy output",
    )?;
    if system.atom_count > MAX_PARTICLE_COUNT {
        return Err(ProviderFailure::new(
            STATUS_CAPACITY_OVERFLOW,
            ParticleMeshReciprocalErrorCodeV1::CapacityExceeded,
            "particle count exceeds the frozen provider maximum",
        ));
    }

    let force_output = if compute_forces == 1 {
        let output = preflight_force_output.ok_or_else(|| {
            ProviderFailure::invalid("force output is null when compute_forces is one")
        })?;
        validate_header::<ParticleMeshReciprocalForceOutputV1>(
            output.struct_size,
            output.abi_version,
            &output.reserved,
            "force output",
        )?;
        if output.capacity < system.atom_count {
            return Err(ProviderFailure::capacity(
                "force capacity is below particle count",
            ));
        }
        Some(output)
    } else {
        if preflight_force_output.is_some() {
            return Err(ProviderFailure::invalid(
                "force output must be null when compute_forces is zero",
            ));
        }
        None
    };

    let mutable_ranges = [
        Some(error_range),
        Some(energy_range),
        if compute_forces == 1 {
            force_channel_ranges[0]
        } else {
            None
        },
        if compute_forces == 1 {
            force_channel_ranges[1]
        } else {
            None
        },
        if compute_forces == 1 {
            force_channel_ranges[2]
        } else {
            None
        },
    ];
    require_disjoint_outputs(&mutable_ranges)?;
    let input_ranges = [
        Some(system_range),
        Some(model_range),
        force_descriptor_range,
        input_channel_ranges[0],
        input_channel_ranges[1],
        input_channel_ranges[2],
        input_channel_ranges[3],
    ];
    for input_range in input_ranges.into_iter().flatten() {
        if overlaps_any(input_range, &mutable_ranges) {
            return Err(ProviderFailure::invalid(
                "particle-mesh reciprocal output storage must not overlap input storage",
            ));
        }
    }

    let input = provider_input(system, model)?;
    let result =
        evaluate_with_force_option(&input, compute_forces == 1).map_err(ProviderFailure::from)?;
    Ok(ProviderCandidate {
        energy: ParticleMeshReciprocalEnergyV1 {
            struct_size: u32::try_from(size_of::<ParticleMeshReciprocalEnergyV1>()).unwrap_or(0),
            abi_version: PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION,
            reciprocal_space_kcal_per_mol: result.reciprocal_space_kcal_per_mol,
            reserved: [0; 4],
        },
        forces: result.forces_kcal_per_mol_angstrom,
        force_output,
    })
}

unsafe fn validate_error_output(
    pointer: *mut ParticleMeshReciprocalErrorV1,
) -> Result<(ParticleMeshReciprocalErrorV1, MemoryRange), i32> {
    let Some(range) = checked_range(pointer.cast_const(), 1, "error output is null")
        .map_err(|failure| failure.status)?
    else {
        return Err(STATUS_INVALID_ARGUMENT);
    };
    // SAFETY: Pointer non-nullness and alignment were checked above and the
    // private caller guarantees initialized descriptor storage.
    let output = unsafe { ptr::read(pointer) };
    if validate_header::<ParticleMeshReciprocalErrorV1>(
        output.struct_size,
        output.abi_version,
        &output.reserved,
        "error output",
    )
    .is_err()
        || output.reserved0 != 0
    {
        return Err(STATUS_ABI_MISMATCH);
    }
    Ok((output, range))
}

unsafe fn write_provider_error(
    pointer: *mut ParticleMeshReciprocalErrorV1,
    code: ParticleMeshReciprocalErrorCodeV1,
    detail: &str,
) {
    let mut output = ParticleMeshReciprocalErrorV1 {
        struct_size: u32::try_from(size_of::<ParticleMeshReciprocalErrorV1>()).unwrap_or(0),
        abi_version: PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION,
        typed_code: code as i32,
        reserved0: 0,
        detail: [0; PARTICLE_MESH_RECIPROCAL_ERROR_CAPACITY],
        reserved: [0; 4],
    };
    let bytes = detail.as_bytes();
    let copy_length = bytes.len().min(PARTICLE_MESH_RECIPROCAL_ERROR_CAPACITY - 1);
    output.detail[..copy_length].copy_from_slice(&bytes[..copy_length]);
    // SAFETY: The entry point validated aligned writable storage and the
    // complete descriptor is committed at once.
    unsafe { ptr::write(pointer, output) };
}

unsafe fn commit_candidate(
    candidate: ProviderCandidate,
    energy_pointer: *mut ParticleMeshReciprocalEnergyV1,
) {
    if let Some(output) = candidate.force_output {
        for (particle, force) in candidate.forces.into_iter().enumerate() {
            // SAFETY: The three disjoint channels were validated for the
            // particle count and no fallible work remains.
            unsafe {
                output.x.add(particle).write(force[0]);
                output.y.add(particle).write(force[1]);
                output.z.add(particle).write(force[2]);
            }
        }
    }
    // SAFETY: Energy storage is valid and disjoint from all other output.
    unsafe { ptr::write(energy_pointer, candidate.energy) };
}

#[no_mangle]
pub extern "C" fn bg_rust_particle_mesh_reciprocal_provider_abi_version_v1() -> u32 {
    PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION
}

/// Evaluate reciprocal-only order-4 particle-mesh electrostatics through the
/// hidden Rust CPU provider ABI.
///
/// # Safety
/// Every descriptor and non-null channel must remain initialized and valid for
/// its declared extent for the call. Mutable outputs must not overlap one
/// another or any input region.
#[no_mangle]
pub unsafe extern "C" fn bg_rust_particle_mesh_reciprocal_evaluate_v1(
    system: *const ParticleMeshReciprocalSystemV1,
    model: *const ParticleMeshReciprocalModelV1,
    compute_forces: u8,
    out_energy: *mut ParticleMeshReciprocalEnergyV1,
    out_forces: *mut ParticleMeshReciprocalForceOutputV1,
    out_error: *mut ParticleMeshReciprocalErrorV1,
) -> i32 {
    // SAFETY: Validation occurs before reading the initialized error descriptor.
    let (_error_output, error_range) = match unsafe { validate_error_output(out_error) } {
        Ok(validated) => validated,
        Err(status) => return status,
    };
    let alias_safety = Cell::new(false);
    let outcome = catch_unwind(AssertUnwindSafe(|| {
        // SAFETY: All raw pointer validation and input copying is contained in
        // the implementation before references or output writes are formed.
        unsafe {
            evaluate_provider_impl(
                system,
                model,
                compute_forces,
                out_energy,
                out_forces,
                error_range,
                &alias_safety,
            )
        }
    }));
    match outcome {
        Ok(Ok(candidate)) => {
            // SAFETY: Candidate construction validated all output regions and
            // no fallible operation remains.
            unsafe { commit_candidate(candidate, out_energy) };
            // SAFETY: Error storage was validated before evaluation.
            unsafe { write_provider_error(out_error, ParticleMeshReciprocalErrorCodeV1::None, "") };
            STATUS_OK
        }
        Ok(Err(failure)) => {
            if failure.may_write_error {
                // SAFETY: Error storage was validated before evaluation.
                unsafe { write_provider_error(out_error, failure.code, failure.detail) };
            }
            failure.status
        }
        Err(_) => {
            if alias_safety.get() {
                // SAFETY: Error storage was validated and fully proven
                // disjoint from all caller descriptors and channels.
                unsafe {
                    write_provider_error(
                        out_error,
                        ParticleMeshReciprocalErrorCodeV1::None,
                        "rust particle-mesh reciprocal provider panicked",
                    )
                };
            }
            STATUS_INTERNAL_ERROR
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture(mesh_dimensions: [u32; 3]) -> ParticleMeshReciprocalInput {
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
            mesh_dimensions,
            dielectric: 1.0,
        };
        input
    }

    fn initialized_energy(value: f64) -> ParticleMeshReciprocalEnergyV1 {
        ParticleMeshReciprocalEnergyV1 {
            struct_size: u32::try_from(size_of::<ParticleMeshReciprocalEnergyV1>()).unwrap(),
            abi_version: PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION,
            reciprocal_space_kcal_per_mol: value,
            reserved: [0; 4],
        }
    }

    fn initialized_error() -> ParticleMeshReciprocalErrorV1 {
        ParticleMeshReciprocalErrorV1 {
            struct_size: u32::try_from(size_of::<ParticleMeshReciprocalErrorV1>()).unwrap(),
            abi_version: PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION,
            typed_code: -1,
            reserved0: 0,
            detail: [0xff; PARTICLE_MESH_RECIPROCAL_ERROR_CAPACITY],
            reserved: [0; 4],
        }
    }

    fn frozen_provider_evaluation() -> (ParticleMeshReciprocalEnergyV1, Vec<[f64; 3]>) {
        let position_x = [1.25, 5.1, 10.2, 15.4];
        let position_y = [2.5, 3.2, 12.3, 17.1];
        let position_z = [3.75, 8.4, 7.7, 19.3];
        let charges = [0.7, -0.4, -0.6, 0.300_000_000_000_000_04];
        let system = ParticleMeshReciprocalSystemV1 {
            struct_size: u32::try_from(size_of::<ParticleMeshReciprocalSystemV1>()).unwrap(),
            abi_version: PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION,
            atom_count: charges.len(),
            position_x: position_x.as_ptr(),
            position_y: position_y.as_ptr(),
            position_z: position_z.as_ptr(),
            charge: charges.as_ptr(),
            reserved: [0; 4],
        };
        let model = ParticleMeshReciprocalModelV1 {
            struct_size: u32::try_from(size_of::<ParticleMeshReciprocalModelV1>()).unwrap(),
            abi_version: PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION,
            cell_lengths_angstrom: [18.0, 20.0, 22.0],
            alpha_per_angstrom: 0.31,
            mesh_dimensions: [16; 3],
            reserved0: 0,
            dielectric: 1.0,
            reserved: [0; 4],
        };
        let mut energy = initialized_energy(f64::NAN);
        let mut force_x = vec![f64::NAN; charges.len()];
        let mut force_y = vec![f64::NAN; charges.len()];
        let mut force_z = vec![f64::NAN; charges.len()];
        let mut force_output = ParticleMeshReciprocalForceOutputV1 {
            struct_size: u32::try_from(size_of::<ParticleMeshReciprocalForceOutputV1>()).unwrap(),
            abi_version: PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION,
            capacity: charges.len(),
            x: force_x.as_mut_ptr(),
            y: force_y.as_mut_ptr(),
            z: force_z.as_mut_ptr(),
            reserved: [0; 4],
        };
        let mut error = initialized_error();
        // SAFETY: Descriptors and channels remain initialized and live, and
        // mutable output storage is pairwise disjoint.
        let status = unsafe {
            super::bg_rust_particle_mesh_reciprocal_evaluate_v1(
                &system,
                &model,
                1,
                &mut energy,
                &mut force_output,
                &mut error,
            )
        };
        assert_eq!(status, STATUS_OK);
        assert_eq!(
            error.typed_code,
            ParticleMeshReciprocalErrorCodeV1::None as i32
        );
        assert!(error.detail.iter().all(|byte| *byte == 0));
        let forces = force_x
            .into_iter()
            .zip(force_y)
            .zip(force_z)
            .map(|((x, y), z)| [x, y, z])
            .collect();
        (energy, forces)
    }

    #[test]
    fn production_failure_diagnostics_are_statically_allocated() {
        const SOURCE: &str = include_str!("particle_mesh_reciprocal.rs");
        let production = SOURCE
            .split_once("\n#[cfg(test)]\nmod tests {")
            .expect("test module boundary must remain explicit")
            .0;
        for forbidden in ["format!(", ".to_owned(", "Cow", "String", ".sort_by("] {
            assert!(
                !production.contains(forbidden),
                "production diagnostics must not contain {forbidden}"
            );
        }
        assert!(
            production.matches("detail: &'static str").count() >= 2,
            "kernel and provider failure details must both remain static"
        );
        assert_eq!(
            production.matches(".sort_unstable_by(").count(),
            2,
            "production ordering must use the allocation-free unstable primitive"
        );
    }

    #[test]
    fn provider_abi_layout_and_typed_codes_are_frozen() {
        assert_eq!(
            PARTICLE_MESH_RECIPROCAL_SCHEMA_ID,
            "betelgeuze.reference_particle_mesh_reciprocal/1.0.0"
        );
        assert_eq!(
            super::bg_rust_particle_mesh_reciprocal_provider_abi_version_v1(),
            1
        );
        assert_eq!(size_of::<ParticleMeshReciprocalSystemV1>(), 80);
        assert_eq!(size_of::<ParticleMeshReciprocalModelV1>(), 96);
        assert_eq!(size_of::<ParticleMeshReciprocalEnergyV1>(), 48);
        assert_eq!(size_of::<ParticleMeshReciprocalForceOutputV1>(), 72);
        assert_eq!(size_of::<ParticleMeshReciprocalErrorV1>(), 304);
        assert_eq!(align_of::<ParticleMeshReciprocalSystemV1>(), 8);
        assert_eq!(align_of::<ParticleMeshReciprocalModelV1>(), 8);
        assert_eq!(align_of::<ParticleMeshReciprocalEnergyV1>(), 8);
        assert_eq!(align_of::<ParticleMeshReciprocalForceOutputV1>(), 8);
        assert_eq!(align_of::<ParticleMeshReciprocalErrorV1>(), 8);
        assert_eq!(
            [
                ParticleMeshReciprocalErrorCodeV1::None,
                ParticleMeshReciprocalErrorCodeV1::EmptySystem,
                ParticleMeshReciprocalErrorCodeV1::CapacityExceeded,
                ParticleMeshReciprocalErrorCodeV1::ChargeCountMismatch,
                ParticleMeshReciprocalErrorCodeV1::NonFiniteCoordinate,
                ParticleMeshReciprocalErrorCodeV1::NonFiniteCharge,
                ParticleMeshReciprocalErrorCodeV1::NonNeutralSystem,
                ParticleMeshReciprocalErrorCodeV1::InvalidCell,
                ParticleMeshReciprocalErrorCodeV1::InvalidParameter,
                ParticleMeshReciprocalErrorCodeV1::InvalidMesh,
                ParticleMeshReciprocalErrorCodeV1::NonFiniteResult,
            ]
            .map(|code| code as i32),
            [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        );
    }

    #[test]
    fn frozen_provider_energy_and_twelve_force_bits_match() {
        let (energy, forces) = frozen_provider_evaluation();
        assert_eq!(
            energy.reciprocal_space_kcal_per_mol.to_bits(),
            0x4044_1de7_1e7a_685d
        );
        let expected = [
            [
                0x3ff7_abf2_33ca_e3fe,
                0x3fe3_f50c_6800_dce2,
                0x4003_a5fe_6291_2de6,
            ],
            [
                0xbff8_2153_b58f_e4a2,
                0xbfdf_03fd_220e_aedd,
                0xbff9_9603_2fc4_0900,
            ],
            [
                0x3fd5_c06e_1da1_0cd7,
                0x3fcf_508c_e37d_6938,
                0xbfdf_6cb8_61fd_f624,
            ],
            [
                0xbfd2_c722_83b8_727e,
                0xbfda_223b_fc46_95cd,
                0xbfd9_e069_9f28_2115,
            ],
        ];
        for (actual, expected) in forces.iter().zip(expected) {
            assert_eq!(actual.map(f64::to_bits), expected);
        }
        let repeated = frozen_provider_evaluation();
        assert_eq!(
            repeated.0.reciprocal_space_kcal_per_mol.to_bits(),
            energy.reciprocal_space_kcal_per_mol.to_bits()
        );
        assert_eq!(
            repeated
                .1
                .iter()
                .flat_map(|force| force.map(f64::to_bits))
                .collect::<Vec<_>>(),
            forces
                .iter()
                .flat_map(|force| force.map(f64::to_bits))
                .collect::<Vec<_>>()
        );
    }

    #[test]
    fn energy_only_skips_inverse_and_gather_without_changing_energy_bits() {
        let input = fixture([16; 3]);
        let with_forces =
            evaluate_with_force_option(&input, true).expect("fixture must evaluate with forces");
        let energy_only =
            evaluate_with_force_option(&input, false).expect("energy-only fixture must evaluate");
        assert_eq!(
            with_forces.reciprocal_space_kcal_per_mol.to_bits(),
            energy_only.reciprocal_space_kcal_per_mol.to_bits()
        );
        assert_eq!(with_forces.forces_kcal_per_mol_angstrom.len(), 4);
        assert!(energy_only.forces_kcal_per_mol_angstrom.is_empty());

        let position_x = [0.0, 1.0];
        let position_y = [0.0; 2];
        let position_z = [0.0; 2];
        let charges = [1.0, -1.0];
        let system = ParticleMeshReciprocalSystemV1 {
            struct_size: 80,
            abi_version: 1,
            atom_count: 2,
            position_x: position_x.as_ptr(),
            position_y: position_y.as_ptr(),
            position_z: position_z.as_ptr(),
            charge: charges.as_ptr(),
            reserved: [0; 4],
        };
        let model = ParticleMeshReciprocalModelV1 {
            struct_size: 96,
            abi_version: 1,
            cell_lengths_angstrom: [10.0, 12.0, 14.0],
            alpha_per_angstrom: 0.3,
            mesh_dimensions: [8; 3],
            reserved0: 0,
            dielectric: 1.0,
            reserved: [0; 4],
        };
        let mut energy = initialized_energy(123.0);
        let mut error = initialized_error();
        // SAFETY: Input and output descriptors remain initialized and live;
        // energy-only requires a null force descriptor.
        let status = unsafe {
            super::bg_rust_particle_mesh_reciprocal_evaluate_v1(
                &system,
                &model,
                0,
                &mut energy,
                ptr::null_mut(),
                &mut error,
            )
        };
        assert_eq!(status, STATUS_OK);
        assert!(energy.reciprocal_space_kcal_per_mol.is_finite());
    }

    fn assert_error_code(
        input: &ParticleMeshReciprocalInput,
        expected: ParticleMeshReciprocalErrorCode,
    ) {
        let error = evaluate(input).expect_err("malformed input must fail");
        assert_eq!(error.code(), expected, "{error}");
        assert!(!error.detail().is_empty());
    }

    #[test]
    fn ten_typed_failure_categories_and_status_mapping_are_stable() {
        let base = fixture([4; 3]);

        let mut malformed = base.clone();
        malformed.positions.clear();
        malformed.charges_elementary.clear();
        assert_error_code(&malformed, ParticleMeshReciprocalErrorCode::EmptySystem);

        let mut malformed = base.clone();
        malformed.positions = vec![Position::default(); MAX_PARTICLE_COUNT + 1];
        malformed.charges_elementary = vec![0.0; MAX_PARTICLE_COUNT + 1];
        assert_error_code(
            &malformed,
            ParticleMeshReciprocalErrorCode::CapacityExceeded,
        );

        let mut malformed = base.clone();
        malformed.charges_elementary.pop();
        assert_error_code(
            &malformed,
            ParticleMeshReciprocalErrorCode::ChargeCountMismatch,
        );

        let mut malformed = base.clone();
        malformed.positions[0].x_angstrom = f64::NAN;
        assert_error_code(
            &malformed,
            ParticleMeshReciprocalErrorCode::NonFiniteCoordinate,
        );

        let mut malformed = base.clone();
        malformed.charges_elementary[0] = f64::INFINITY;
        assert_error_code(&malformed, ParticleMeshReciprocalErrorCode::NonFiniteCharge);

        let mut malformed = base.clone();
        malformed.charges_elementary[0] += 0.25;
        assert_error_code(
            &malformed,
            ParticleMeshReciprocalErrorCode::NonNeutralSystem,
        );

        let mut malformed = base.clone();
        malformed.cell.lengths_angstrom[1] = 0.0;
        assert_error_code(&malformed, ParticleMeshReciprocalErrorCode::InvalidCell);

        let mut malformed = base.clone();
        malformed.settings.alpha_per_angstrom = 0.0;
        assert_error_code(
            &malformed,
            ParticleMeshReciprocalErrorCode::InvalidParameter,
        );

        let mut malformed = base;
        malformed.settings.mesh_dimensions = [4, 6, 4];
        assert_error_code(&malformed, ParticleMeshReciprocalErrorCode::InvalidMesh);

        fn poisoned_inverse(
            values: &mut [Complex],
            dimensions: [usize; 3],
            inverse: bool,
        ) -> Result<(), AllocationFailure> {
            fft::fft_3d(values, dimensions, inverse)?;
            if inverse {
                values[0].real = f64::INFINITY;
            }
            Ok(())
        }
        let error = evaluate_with_transform(&fixture([4; 3]), poisoned_inverse, true)
            .expect_err("test-only poisoned inverse must fail closed");
        assert_eq!(
            error.code(),
            ParticleMeshReciprocalErrorCode::NonFiniteResult
        );
        assert!(!error.detail().is_empty());

        let mappings = [
            (
                ParticleMeshReciprocalErrorCode::EmptySystem,
                STATUS_INVALID_ARGUMENT,
            ),
            (
                ParticleMeshReciprocalErrorCode::CapacityExceeded,
                STATUS_CAPACITY_OVERFLOW,
            ),
            (
                ParticleMeshReciprocalErrorCode::ChargeCountMismatch,
                STATUS_INVALID_ARGUMENT,
            ),
            (
                ParticleMeshReciprocalErrorCode::NonFiniteCoordinate,
                STATUS_INVALID_ARGUMENT,
            ),
            (
                ParticleMeshReciprocalErrorCode::NonFiniteCharge,
                STATUS_INVALID_ARGUMENT,
            ),
            (
                ParticleMeshReciprocalErrorCode::NonNeutralSystem,
                STATUS_NUMERICAL_ERROR,
            ),
            (
                ParticleMeshReciprocalErrorCode::InvalidCell,
                STATUS_INVALID_ARGUMENT,
            ),
            (
                ParticleMeshReciprocalErrorCode::InvalidParameter,
                STATUS_INVALID_ARGUMENT,
            ),
            (
                ParticleMeshReciprocalErrorCode::InvalidMesh,
                STATUS_INVALID_ARGUMENT,
            ),
            (
                ParticleMeshReciprocalErrorCode::NonFiniteResult,
                STATUS_NUMERICAL_ERROR,
            ),
        ];
        for (code, expected_status) in mappings {
            let failure = ProviderFailure::from(ParticleMeshReciprocalError::new(code, "injected"));
            assert_eq!(failure.status, expected_status);
            assert_eq!(
                failure.code as i32,
                ParticleMeshReciprocalErrorCodeV1::from(code) as i32
            );
            assert!(!failure.detail.is_empty());
        }
    }

    #[test]
    fn work_envelope_accepts_the_largest_reachable_mesh_and_rejects_the_next() {
        let accepted = fixture([128, 64, 64]);
        let validated = validate(&accepted).expect("524288-point mesh must fit frozen work cap");
        assert_eq!(validated.mesh_point_count, 524_288);

        let rejected = fixture([64, 128, 128]);
        assert_error_code(&rejected, ParticleMeshReciprocalErrorCode::CapacityExceeded);
    }

    #[test]
    fn log_rescue_preserves_normal_and_subnormal_force_domains() {
        let mut normal = ParticleMeshReciprocalInput::new(
            vec![Position::new(0.0, 0.0, 0.0), Position::new(4.0e8, 0.0, 0.0)],
            vec![16.0, -16.0],
            OrthorhombicCell {
                lengths_angstrom: [1.0e9, 1.0e-6, 1.0e-6],
            },
        );
        normal.settings = ParticleMeshReciprocalSettings {
            alpha_per_angstrom: 1.15e-10,
            mesh_dimensions: [4; 3],
            dielectric: 1.0e-12,
        };
        let first_wave = core::f64::consts::TAU / normal.cell.lengths_angstrom[0];
        assert_eq!(
            libm::exp(
                -(first_wave * first_wave)
                    / (4.0
                        * normal.settings.alpha_per_angstrom
                        * normal.settings.alpha_per_angstrom)
            )
            .to_bits(),
            0
        );
        let normal_result = evaluate(&normal).expect("normal rescue fixture must evaluate");
        assert!(normal_result.reciprocal_space_kcal_per_mol.is_normal());
        assert!(normal_result.forces_kcal_per_mol_angstrom[1][0].is_normal());

        let mut subnormal = ParticleMeshReciprocalInput::new(
            vec![
                Position::new(0.0, 0.0, 0.0),
                Position::new(4.0e-7, 0.0, 0.0),
            ],
            vec![16.0, -16.0],
            OrthorhombicCell {
                lengths_angstrom: [1.0e-6; 3],
            },
        );
        subnormal.settings = ParticleMeshReciprocalSettings {
            alpha_per_angstrom: 1.15e5,
            mesh_dimensions: [4; 3],
            dielectric: 1.0e12,
        };
        let evaluated = evaluate(&subnormal).expect("subnormal rescue fixture must evaluate");
        assert_eq!(evaluated.reciprocal_space_kcal_per_mol.to_bits(), 0);
        assert!(evaluated.forces_kcal_per_mol_angstrom[1][0].is_subnormal());

        subnormal.settings.dielectric = 2.5e10;
        let aggregate = evaluate(&subnormal).expect("aggregate rescue fixture must evaluate");
        assert_eq!(aggregate.reciprocal_space_kcal_per_mol.to_bits(), 1);
    }

    #[test]
    fn rescue_only_and_mixed_energy_lanes_round_once() {
        let minimum_subnormal = f64::from_bits(1);
        let individual_log = libm::log(minimum_subnormal) - libm::log(8.0);
        assert_eq!(completed_positive_from_log(individual_log).to_bits(), 0);
        let mut rescue_only = CompensatedSum::default();
        for _ in 0..8 {
            rescue_only.add(completed_positive_from_log(
                individual_log + LOG_RESCUE_SCALE,
            ));
        }
        assert_eq!(
            (rescue_only.total() / RESCUE_SCALE).to_bits(),
            minimum_subnormal.to_bits()
        );

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
    fn fft_is_z_fast_negative_nyquist_conjugate_symmetric_and_reversible() {
        assert_eq!(fft::index(0, 0, 1, [4, 8, 4]), 1);
        assert_eq!(fft::index(0, 1, 0, [4, 8, 4]), 4);
        assert_eq!(fft::index(1, 0, 0, [4, 8, 4]), 32);
        assert_eq!(
            (0..8)
                .map(|index| signed_mesh_index(index, 8))
                .collect::<Vec<_>>(),
            [0, 1, 2, 3, -4, -3, -2, -1]
        );

        let dimensions = [4, 8, 4];
        let original = (0..dimensions.iter().product())
            .map(|index| Complex::new(libm::sin(0.37 * bounded_usize_to_f64(index)), 0.0))
            .collect::<Vec<_>>();
        let mut transformed = original.clone();
        fft::fft_3d(&mut transformed, dimensions, false).expect("forward FFT must allocate");
        for x in 0..dimensions[0] {
            for y in 0..dimensions[1] {
                for z in 0..dimensions[2] {
                    let paired = [
                        (dimensions[0] - x) % dimensions[0],
                        (dimensions[1] - y) % dimensions[1],
                        (dimensions[2] - z) % dimensions[2],
                    ];
                    let value = transformed[fft::index(x, y, z, dimensions)];
                    let conjugate =
                        transformed[fft::index(paired[0], paired[1], paired[2], dimensions)];
                    assert!((value.real - conjugate.real).abs() <= 2.0e-12);
                    assert!((value.imaginary + conjugate.imaginary).abs() <= 2.0e-12);
                }
            }
        }
        fft::fft_3d(&mut transformed, dimensions, true).expect("inverse FFT must allocate");
        for (actual, expected) in transformed.iter().zip(original) {
            assert!((actual.real - expected.real).abs() <= 2.0e-12);
            assert!(actual.imaginary.abs() <= 2.0e-12);
        }
    }

    #[test]
    fn abi_validation_is_fail_closed_and_transactional() {
        let position_x = [0.0, 1.0];
        let position_y = [0.0; 2];
        let position_z = [0.0; 2];
        let charges = [1.0, 1.0];
        let system = ParticleMeshReciprocalSystemV1 {
            struct_size: 80,
            abi_version: 1,
            atom_count: 2,
            position_x: position_x.as_ptr(),
            position_y: position_y.as_ptr(),
            position_z: position_z.as_ptr(),
            charge: charges.as_ptr(),
            reserved: [0; 4],
        };
        let model = ParticleMeshReciprocalModelV1 {
            struct_size: 96,
            abi_version: 1,
            cell_lengths_angstrom: [10.0; 3],
            alpha_per_angstrom: 0.3,
            mesh_dimensions: [4; 3],
            reserved0: 0,
            dielectric: 1.0,
            reserved: [0; 4],
        };
        let mut energy = initialized_energy(101.0);
        let mut force_x = [201.0; 2];
        let mut force_y = [202.0; 2];
        let mut force_z = [203.0; 2];
        let mut force_output = ParticleMeshReciprocalForceOutputV1 {
            struct_size: 72,
            abi_version: 1,
            capacity: 2,
            x: force_x.as_mut_ptr(),
            y: force_y.as_mut_ptr(),
            z: force_z.as_mut_ptr(),
            reserved: [0; 4],
        };
        let mut error = initialized_error();
        // SAFETY: Every descriptor/channel is initialized and disjoint; the
        // deliberately non-neutral input must fail before output commit.
        let status = unsafe {
            super::bg_rust_particle_mesh_reciprocal_evaluate_v1(
                &system,
                &model,
                1,
                &mut energy,
                &mut force_output,
                &mut error,
            )
        };
        assert_eq!(status, STATUS_NUMERICAL_ERROR);
        assert_eq!(
            error.typed_code,
            ParticleMeshReciprocalErrorCodeV1::NonNeutralSystem as i32
        );
        assert_ne!(error.detail[0], 0);
        assert_eq!(
            energy.reciprocal_space_kcal_per_mol.to_bits(),
            101.0_f64.to_bits()
        );
        assert_eq!(force_x, [201.0; 2]);
        assert_eq!(force_y, [202.0; 2]);
        assert_eq!(force_z, [203.0; 2]);

        let mut error = initialized_error();
        // SAFETY: Same live descriptors; compute_forces=2 is intentionally invalid.
        let status = unsafe {
            super::bg_rust_particle_mesh_reciprocal_evaluate_v1(
                &system,
                &model,
                2,
                &mut energy,
                ptr::null_mut(),
                &mut error,
            )
        };
        assert_eq!(status, STATUS_INVALID_ARGUMENT);
        assert_eq!(
            error.typed_code,
            ParticleMeshReciprocalErrorCodeV1::None as i32
        );
        assert_ne!(error.detail[0], 0);
        assert_eq!(
            energy.reciprocal_space_kcal_per_mol.to_bits(),
            101.0_f64.to_bits()
        );

        let mut overlapping = [301.0; 2];
        force_output.x = overlapping.as_mut_ptr();
        force_output.y = overlapping.as_mut_ptr();
        force_output.z = force_z.as_mut_ptr();
        let mut error = initialized_error();
        // SAFETY: Channels are initialized but two mutable spans deliberately overlap.
        let status = unsafe {
            super::bg_rust_particle_mesh_reciprocal_evaluate_v1(
                &system,
                &model,
                1,
                &mut energy,
                &mut force_output,
                &mut error,
            )
        };
        assert_eq!(status, STATUS_INVALID_ARGUMENT);
        assert_eq!(overlapping, [301.0; 2]);

        let oversized_length = (isize::MAX as usize) / size_of::<f64>() + 1;
        let range_error = checked_range(ptr::dangling::<f64>(), oversized_length, "span")
            .expect_err("oversized span must fail");
        assert_eq!(range_error.status, STATUS_CAPACITY_OVERFLOW);
    }

    #[test]
    fn injected_allocation_failures_map_to_out_of_memory_without_output_commit() {
        let position_x = [1.25, 5.1, 10.2, 15.4];
        let position_y = [2.5, 3.2, 12.3, 17.1];
        let position_z = [3.75, 8.4, 7.7, 19.3];
        let charges = [0.7, -0.4, -0.6, 0.300_000_000_000_000_04];
        let system = ParticleMeshReciprocalSystemV1 {
            struct_size: 80,
            abi_version: 1,
            atom_count: charges.len(),
            position_x: position_x.as_ptr(),
            position_y: position_y.as_ptr(),
            position_z: position_z.as_ptr(),
            charge: charges.as_ptr(),
            reserved: [0; 4],
        };
        let mut model = ParticleMeshReciprocalModelV1 {
            struct_size: 96,
            abi_version: 1,
            cell_lengths_angstrom: [18.0, 20.0, 22.0],
            alpha_per_angstrom: 0.31,
            mesh_dimensions: [16; 3],
            reserved0: 0,
            dielectric: 1.0,
            reserved: [0; 4],
        };
        for site in [
            AllocationSite::ProviderChannelCopy,
            AllocationSite::ProviderPositions,
            AllocationSite::NeutralitySort,
            AllocationSite::ParticleAssignments,
            AllocationSite::Spectrum,
            AllocationSite::FftLineScratch,
            AllocationSite::ReciprocalAxisData,
            AllocationSite::ForceOutput,
        ] {
            let mut energy = initialized_energy(101.0);
            let mut force_x = [201.0; 4];
            let mut force_y = [202.0; 4];
            let mut force_z = [203.0; 4];
            let mut force_output = ParticleMeshReciprocalForceOutputV1 {
                struct_size: 72,
                abi_version: 1,
                capacity: 4,
                x: force_x.as_mut_ptr(),
                y: force_y.as_mut_ptr(),
                z: force_z.as_mut_ptr(),
                reserved: [0; 4],
            };
            let mut error = initialized_error();
            let _injection = AllocationFailureGuard::inject(site);
            // SAFETY: All descriptors and channels are initialized, live, and
            // disjoint. The test hook fails one reserve without requesting OOM.
            let status = unsafe {
                super::bg_rust_particle_mesh_reciprocal_evaluate_v1(
                    &system,
                    &model,
                    1,
                    &mut energy,
                    &mut force_output,
                    &mut error,
                )
            };
            assert_eq!(status, STATUS_OUT_OF_MEMORY, "allocation site {site:?}");
            assert_eq!(
                error.typed_code,
                ParticleMeshReciprocalErrorCodeV1::None as i32,
                "allocation site {site:?}"
            );
            assert_ne!(error.detail[0], 0, "allocation site {site:?}");
            assert_eq!(
                energy.reciprocal_space_kcal_per_mol.to_bits(),
                101.0_f64.to_bits()
            );
            assert_eq!(force_x, [201.0; 4]);
            assert_eq!(force_y, [202.0; 4]);
            assert_eq!(force_z, [203.0; 4]);
        }

        model.mesh_dimensions = [128; 3];
        let mut energy = initialized_energy(101.0);
        let mut error = initialized_error();
        // SAFETY: Valid disjoint descriptors exercise a work-capacity failure,
        // which must remain distinct from allocation failure.
        let status = unsafe {
            super::bg_rust_particle_mesh_reciprocal_evaluate_v1(
                &system,
                &model,
                0,
                &mut energy,
                ptr::null_mut(),
                &mut error,
            )
        };
        assert_eq!(status, STATUS_CAPACITY_OVERFLOW);
        assert_eq!(
            error.typed_code,
            ParticleMeshReciprocalErrorCodeV1::CapacityExceeded as i32
        );
        assert_eq!(
            energy.reciprocal_space_kcal_per_mol.to_bits(),
            101.0_f64.to_bits()
        );
    }

    fn descriptor_bytes<T>(value: *const T) -> Vec<u8> {
        // SAFETY: Tests pass a live initialized descriptor and copy exactly its
        // statically known byte size without retaining a borrow.
        unsafe { core::slice::from_raw_parts(value.cast::<u8>(), size_of::<T>()).to_vec() }
    }

    #[test]
    fn early_failures_never_write_an_error_that_aliases_caller_storage() {
        let position_x = [0.0, 1.0];
        let position_y = [0.0; 2];
        let position_z = [0.0; 2];
        let charges = [1.0, -1.0];
        let base_system = ParticleMeshReciprocalSystemV1 {
            struct_size: 80,
            abi_version: 1,
            atom_count: 2,
            position_x: position_x.as_ptr(),
            position_y: position_y.as_ptr(),
            position_z: position_z.as_ptr(),
            charge: charges.as_ptr(),
            reserved: [0; 4],
        };
        let model = ParticleMeshReciprocalModelV1 {
            struct_size: 96,
            abi_version: 1,
            cell_lengths_angstrom: [10.0, 12.0, 14.0],
            alpha_per_angstrom: 0.3,
            mesh_dimensions: [8; 3],
            reserved0: 0,
            dielectric: 1.0,
            reserved: [0; 4],
        };

        let call_with_alias =
            |system: *const ParticleMeshReciprocalSystemV1,
             model_pointer: *const ParticleMeshReciprocalModelV1,
             energy: *mut ParticleMeshReciprocalEnergyV1,
             force: *mut ParticleMeshReciprocalForceOutputV1,
             compute_forces: u8,
             error: *mut ParticleMeshReciprocalErrorV1| {
                let before = descriptor_bytes(error);
                // SAFETY: Each case deliberately aliases one raw ABI region. All
                // referenced storage is initialized and live so the provider can
                // reject by arithmetic range preflight without writing.
                let status = unsafe {
                    super::bg_rust_particle_mesh_reciprocal_evaluate_v1(
                        system,
                        model_pointer,
                        compute_forces,
                        energy,
                        force,
                        error,
                    )
                };
                assert_eq!(status, STATUS_INVALID_ARGUMENT);
                assert_eq!(descriptor_bytes(error), before);
            };

        let mut energy = initialized_energy(101.0);
        let mut error = initialized_error();
        let error_pointer = &mut error as *mut ParticleMeshReciprocalErrorV1;
        call_with_alias(
            error_pointer.cast(),
            &model,
            &mut energy,
            ptr::null_mut(),
            0,
            error_pointer,
        );

        let mut error = initialized_error();
        let error_pointer = &mut error as *mut ParticleMeshReciprocalErrorV1;
        call_with_alias(
            &base_system,
            error_pointer.cast(),
            &mut energy,
            ptr::null_mut(),
            0,
            error_pointer,
        );

        let mut error = initialized_error();
        let error_pointer = &mut error as *mut ParticleMeshReciprocalErrorV1;
        call_with_alias(
            &base_system,
            &model,
            error_pointer.cast(),
            ptr::null_mut(),
            0,
            error_pointer,
        );

        let mut error = initialized_error();
        let error_pointer = &mut error as *mut ParticleMeshReciprocalErrorV1;
        call_with_alias(
            &base_system,
            &model,
            &mut energy,
            error_pointer.cast(),
            1,
            error_pointer,
        );

        let mut error = initialized_error();
        let error_pointer = &mut error as *mut ParticleMeshReciprocalErrorV1;
        let input_alias_system = ParticleMeshReciprocalSystemV1 {
            position_x: error_pointer.cast(),
            ..base_system
        };
        call_with_alias(
            &input_alias_system,
            &model,
            &mut energy,
            ptr::null_mut(),
            2,
            error_pointer,
        );

        let mut error = initialized_error();
        let error_pointer = &mut error as *mut ParticleMeshReciprocalErrorV1;
        let mut force_y = [0.0; 2];
        let mut force_z = [0.0; 2];
        let mut force_output = ParticleMeshReciprocalForceOutputV1 {
            struct_size: 72,
            abi_version: 1,
            capacity: 2,
            x: error_pointer.cast(),
            y: force_y.as_mut_ptr(),
            z: force_z.as_mut_ptr(),
            reserved: [0; 4],
        };
        call_with_alias(
            &base_system,
            &model,
            &mut energy,
            &mut force_output,
            1,
            error_pointer,
        );
    }

    #[test]
    fn misaligned_descriptor_is_rejected_without_reading() {
        let model = ParticleMeshReciprocalModelV1 {
            struct_size: 96,
            abi_version: 1,
            cell_lengths_angstrom: [10.0; 3],
            alpha_per_angstrom: 0.3,
            mesh_dimensions: [4; 3],
            reserved0: 0,
            dielectric: 1.0,
            reserved: [0; 4],
        };
        let mut energy = initialized_energy(101.0);
        let mut error = initialized_error();
        let mut storage = vec![
            0_u8;
            size_of::<ParticleMeshReciprocalSystemV1>()
                + align_of::<ParticleMeshReciprocalSystemV1>()
        ];
        let offset = (0..align_of::<ParticleMeshReciprocalSystemV1>())
            .find(|offset| {
                (storage.as_ptr() as usize + offset) % align_of::<ParticleMeshReciprocalSystemV1>()
                    != 0
            })
            .expect("alignment greater than one has a misaligned offset");
        let misaligned = storage.as_mut_ptr().wrapping_add(offset).cast();
        // SAFETY: The system pointer is intentionally misaligned. The provider
        // must reject its address without dereferencing it.
        let status = unsafe {
            super::bg_rust_particle_mesh_reciprocal_evaluate_v1(
                misaligned,
                &model,
                0,
                &mut energy,
                ptr::null_mut(),
                &mut error,
            )
        };
        assert_eq!(status, STATUS_INVALID_ARGUMENT);
        assert_eq!(
            energy.reciprocal_space_kcal_per_mol.to_bits(),
            101.0_f64.to_bits()
        );
    }
}
