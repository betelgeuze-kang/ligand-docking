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
        line: &mut [Complex],
    ) {
        transform_3d_with(values, dimensions, inverse, line, fft_1d);
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
        line: &mut [Complex],
        transform_1d: fn(&mut [Complex], bool),
    ) {
        let [x_count, y_count, z_count] = dimensions;
        debug_assert_eq!(values.len(), x_count * y_count * z_count);
        let line_count = x_count.max(y_count).max(z_count);
        debug_assert!(line.len() >= line_count);

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
    ParticleAssignments,
    SpectrumAndFftLineScratch,
    ReciprocalAxisData,
    ForceOutput,
    NeutralitySort,
}

impl AllocationSite {
    const fn detail(self) -> &'static str {
        match self {
            Self::ParticleAssignments => "particle assignment allocation failed",
            Self::SpectrumAndFftLineScratch => {
                "particle-mesh spectrum and FFT line-scratch allocation failed"
            }
            Self::ReciprocalAxisData => "reciprocal axis-data allocation failed",
            Self::ForceOutput => "particle force-output allocation failed",
            Self::NeutralitySort => "neutrality summation scratch allocation failed",
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
    if INJECTED_ALLOCATION_FAILURE.with(|injected| {
        let Some(mut request) = injected.get() else {
            return false;
        };
        if request.site != site {
            return false;
        }
        if request.matching_allocations_before_failure == 0 {
            return true;
        }
        request.matching_allocations_before_failure -= 1;
        injected.set(Some(request));
        false
    }) {
        return Err(AllocationFailure { site });
    }
    values
        .try_reserve_exact(additional)
        .map_err(|_| AllocationFailure { site })
}

#[cfg(test)]
#[derive(Clone, Copy)]
struct InjectedAllocationFailure {
    site: AllocationSite,
    matching_allocations_before_failure: usize,
}

#[cfg(test)]
thread_local! {
    static INJECTED_ALLOCATION_FAILURE: Cell<Option<InjectedAllocationFailure>> =
        const { Cell::new(None) };
}

#[cfg(test)]
struct AllocationFailureGuard {
    previous: Option<InjectedAllocationFailure>,
}

#[cfg(test)]
impl AllocationFailureGuard {
    fn inject(site: AllocationSite) -> Self {
        Self::inject_at(site, 1)
    }

    fn inject_at(site: AllocationSite, occurrence: usize) -> Self {
        assert!(occurrence > 0, "allocation occurrence is one-based");
        let previous = INJECTED_ALLOCATION_FAILURE.with(|injected| {
            let previous = injected.get();
            injected.set(Some(InjectedAllocationFailure {
                site,
                matching_allocations_before_failure: occurrence - 1,
            }));
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

#[cfg(test)]
thread_local! {
    static INJECTED_LATE_NONFINITE_RESULT: Cell<bool> = const { Cell::new(false) };
}

#[cfg(test)]
struct LateNonFiniteResultGuard {
    previous: bool,
}

#[cfg(test)]
impl LateNonFiniteResultGuard {
    fn inject() -> Self {
        let previous = INJECTED_LATE_NONFINITE_RESULT.with(|injected| {
            let previous = injected.get();
            injected.set(true);
            previous
        });
        Self { previous }
    }
}

#[cfg(test)]
impl Drop for LateNonFiniteResultGuard {
    fn drop(&mut self) {
        INJECTED_LATE_NONFINITE_RESULT.with(|injected| injected.set(self.previous));
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
#[cfg_attr(not(test), allow(dead_code))]
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

trait ReciprocalInput {
    fn particle_count(&self) -> usize;
    fn position(&self, particle: usize) -> Position;
    fn charges_elementary(&self) -> &[f64];
    fn cell(&self) -> OrthorhombicCell;
    fn settings(&self) -> ParticleMeshReciprocalSettings;
}

impl ReciprocalInput for ParticleMeshReciprocalInput {
    fn particle_count(&self) -> usize {
        self.positions.len()
    }

    fn position(&self, particle: usize) -> Position {
        self.positions[particle]
    }

    fn charges_elementary(&self) -> &[f64] {
        &self.charges_elementary
    }

    fn cell(&self) -> OrthorhombicCell {
        self.cell
    }

    fn settings(&self) -> ParticleMeshReciprocalSettings {
        self.settings
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

type Transform3d = fn(&mut [Complex], [usize; 3], bool, &mut [Complex]);

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

fn evaluate_with_force_option<I: ReciprocalInput + ?Sized>(
    input: &I,
    compute_forces: bool,
) -> Result<ParticleMeshReciprocalEvaluation, ParticleMeshReciprocalError> {
    evaluate_with_transform(input, fft::fft_3d, compute_forces)
}

fn evaluate_with_transform<I: ReciprocalInput + ?Sized>(
    input: &I,
    transform: Transform3d,
    compute_forces: bool,
) -> Result<ParticleMeshReciprocalEvaluation, ParticleMeshReciprocalError> {
    let force_mode = if compute_forces {
        ForceStorageMode::Transactional
    } else {
        ForceStorageMode::Disabled
    };
    Ok(compute_with_transform(input, transform, force_mode)?.evaluation)
}

struct InternalEvaluation {
    evaluation: ParticleMeshReciprocalEvaluation,
}

fn spectrum_and_fft_line_scratch(
    validated: &ValidatedInput,
) -> Result<Vec<Complex>, AllocationFailure> {
    let line_count = validated.dimensions.into_iter().max().unwrap_or(0);
    let storage_count = validated
        .mesh_point_count
        .checked_add(line_count)
        .expect("validated spectrum and FFT line-scratch count fits usize");
    let mut storage = Vec::new();
    fallible_reserve_exact(
        &mut storage,
        storage_count,
        AllocationSite::SpectrumAndFftLineScratch,
    )?;
    storage.resize(storage_count, Complex::default());
    Ok(storage)
}

#[derive(Clone, Copy)]
enum ForceStorageMode {
    Disabled,
    Transactional,
    Direct(ParticleMeshReciprocalForceOutputV1),
}

fn compute_with_transform<I: ReciprocalInput + ?Sized>(
    input: &I,
    transform: Transform3d,
    force_mode: ForceStorageMode,
) -> Result<InternalEvaluation, ParticleMeshReciprocalError> {
    let validated = validate(input)?;
    let particle_count = input.particle_count();
    let charges = input.charges_elementary();
    let cell = input.cell();
    let mut assignments = Vec::new();
    fallible_reserve_exact(
        &mut assignments,
        particle_count,
        AllocationSite::ParticleAssignments,
    )
    .map_err(ParticleMeshReciprocalError::from)?;
    assignments.extend(
        (0..particle_count)
            .map(|particle| assignment(input.position(particle), cell, validated.dimensions)),
    );
    let mut spectrum_and_fft_line_storage =
        spectrum_and_fft_line_scratch(&validated).map_err(ParticleMeshReciprocalError::from)?;
    let (spectrum, fft_line_scratch) =
        spectrum_and_fft_line_storage.split_at_mut(validated.mesh_point_count);
    debug_assert_eq!(
        fft_line_scratch.len(),
        validated.dimensions.into_iter().max().unwrap_or(0)
    );
    spread_charges(spectrum, validated.dimensions, &assignments, charges);
    transform(spectrum, validated.dimensions, false, fft_line_scratch);

    let reciprocal = apply_reciprocal_operator(input, &validated, spectrum)?;
    let reciprocal_space_kcal_per_mol = reciprocal.energy;

    let (forces_kcal_per_mol_angstrom, all_forces_are_finite) = if matches!(
        force_mode,
        ForceStorageMode::Transactional | ForceStorageMode::Direct(_)
    ) {
        transform(spectrum, validated.dimensions, true, fft_line_scratch);
        let scaled_grid_multiplier = reciprocal.grid_derivative_scale / RESCUE_SCALE;
        let (forces, all_forces_are_finite) = match force_mode {
            ForceStorageMode::Transactional => {
                let forces = gather_forces(
                    spectrum,
                    validated.dimensions,
                    &assignments,
                    charges,
                    cell,
                    scaled_grid_multiplier,
                )
                .map_err(ParticleMeshReciprocalError::from)?;
                let all_forces_are_finite = forces.iter().flatten().all(|value| value.is_finite());
                (forces, all_forces_are_finite)
            }
            ForceStorageMode::Direct(output) => {
                // SAFETY: The direct provider preflight validates descriptor,
                // capacity, and aliases before calling this shared pipeline.
                let all_forces_are_finite = unsafe {
                    gather_forces_into_provider_output(
                        spectrum,
                        validated.dimensions,
                        &assignments,
                        charges,
                        cell,
                        scaled_grid_multiplier,
                        output,
                    )
                };
                (Vec::new(), all_forces_are_finite)
            }
            ForceStorageMode::Disabled => unreachable!("force mode was checked above"),
        };
        for value in spectrum.iter_mut() {
            *value = value.scale(scaled_grid_multiplier);
        }
        #[cfg(test)]
        INJECTED_LATE_NONFINITE_RESULT.with(|injected| {
            if injected.get() {
                spectrum[0].real = f64::INFINITY;
            }
        });
        (forces, all_forces_are_finite)
    } else {
        (Vec::new(), true)
    };

    if !reciprocal_space_kcal_per_mol.is_finite()
        || spectrum
            .iter()
            .any(|value| !value.real.is_finite() || !value.imaginary.is_finite())
        || !all_forces_are_finite
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

fn apply_reciprocal_operator<I: ReciprocalInput + ?Sized>(
    input: &I,
    validated: &ValidatedInput,
    spectrum: &mut [Complex],
) -> Result<ReciprocalOperator, ParticleMeshReciprocalError> {
    let settings = input.settings();
    let cell = input.cell();
    let alpha = settings.alpha_per_angstrom;
    let energy_prefactor = COULOMB_KCAL_ANGSTROM_PER_MOL_E2 / settings.dielectric
        * core::f64::consts::TAU
        / validated.volume_angstrom_cubed;
    let grid_derivative_scale =
        2.0 * energy_prefactor * bounded_usize_to_f64(validated.mesh_point_count);
    let dimension_data_storage = reciprocal_axis_data(validated.dimensions, cell.lengths_angstrom)
        .map_err(ParticleMeshReciprocalError::from)?;
    let [x_count, y_count, z_count] = validated.dimensions;
    let (x_axis_data, yz_axis_data) = dimension_data_storage.split_at(x_count);
    let (y_axis_data, z_axis_data) = yz_axis_data.split_at(y_count);
    debug_assert_eq!(z_axis_data.len(), z_count);
    let dimension_data = [x_axis_data, y_axis_data, z_axis_data];
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
fn validate<I: ReciprocalInput + ?Sized>(
    input: &I,
) -> Result<ValidatedInput, ParticleMeshReciprocalError> {
    let particle_count = input.particle_count();
    let charges = input.charges_elementary();
    let cell = input.cell();
    let settings = input.settings();
    if particle_count == 0 {
        return Err(ParticleMeshReciprocalError::new(
            ParticleMeshReciprocalErrorCode::EmptySystem,
            "at least one particle is required",
        ));
    }
    if particle_count > MAX_PARTICLE_COUNT {
        return Err(ParticleMeshReciprocalError::new(
            ParticleMeshReciprocalErrorCode::CapacityExceeded,
            "particle count exceeds the frozen maximum",
        ));
    }
    if particle_count != charges.len() {
        return Err(ParticleMeshReciprocalError::new(
            ParticleMeshReciprocalErrorCode::ChargeCountMismatch,
            "position count does not match charge count",
        ));
    }
    for particle in 0..particle_count {
        let position = input.position(particle);
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
    for charge in charges.iter().copied() {
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
    let total_charge =
        accurate_order_independent_sum(charges).map_err(ParticleMeshReciprocalError::from)?;
    if total_charge != 0.0 {
        return Err(ParticleMeshReciprocalError::new(
            ParticleMeshReciprocalErrorCode::NonNeutralSystem,
            "compensated total charge is not exactly zero",
        ));
    }

    for length in cell.lengths_angstrom {
        if !length.is_finite()
            || !(MIN_CELL_LENGTH_ANGSTROM..=MAX_CELL_LENGTH_ANGSTROM).contains(&length)
        {
            return Err(ParticleMeshReciprocalError::new(
                ParticleMeshReciprocalErrorCode::InvalidCell,
                "a cell length is outside the frozen finite positive range",
            ));
        }
    }
    let volume_angstrom_cubed = cell_volume(cell);
    if !volume_angstrom_cubed.is_finite() || volume_angstrom_cubed <= 0.0 {
        return Err(ParticleMeshReciprocalError::new(
            ParticleMeshReciprocalErrorCode::InvalidCell,
            "cell volume must be finite and positive",
        ));
    }
    require_parameter_range(
        settings.alpha_per_angstrom,
        MIN_ALPHA_PER_ANGSTROM,
        MAX_ALPHA_PER_ANGSTROM,
        "alpha_per_angstrom is outside the frozen finite positive range",
    )?;
    require_parameter_range(
        settings.dielectric,
        MIN_DIELECTRIC,
        MAX_DIELECTRIC,
        "dielectric is outside the frozen finite positive range",
    )?;

    let mut dimensions = [0_usize; 3];
    for (axis, dimension) in settings.mesh_dimensions.iter().copied().enumerate() {
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
    validate_work_limit(dimensions, mesh_point_count, particle_count)?;
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
    dimensions: [usize; 3],
    cell_lengths: [f64; 3],
) -> Result<Vec<ReciprocalAxisData>, AllocationFailure> {
    let data_count = dimensions
        .into_iter()
        .try_fold(0_usize, usize::checked_add)
        .expect("validated reciprocal axis-data count fits usize");
    let mut data = Vec::new();
    fallible_reserve_exact(&mut data, data_count, AllocationSite::ReciprocalAxisData)?;
    for axis in 0..3 {
        let dimension = dimensions[axis];
        let cell_length = cell_lengths[axis];
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
    }
    debug_assert_eq!(data.len(), data_count);
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
        forces.push(gather_force(
            grid_derivative,
            dimensions,
            assignment,
            charge,
            cell,
            grid_derivative_multiplier,
        ));
    }
    Ok(forces)
}

fn gather_force(
    grid_derivative: &[Complex],
    dimensions: [usize; 3],
    assignment: &ParticleAssignment,
    charge: f64,
    cell: OrthorhombicCell,
    grid_derivative_multiplier: f64,
) -> [f64; 3] {
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

#[derive(Clone, Copy)]
enum ProviderForceMode {
    Transactional(u8),
    Direct,
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

struct BorrowedProviderInput<'a> {
    position_x: &'a [f64],
    position_y: &'a [f64],
    position_z: &'a [f64],
    charges_elementary: &'a [f64],
    cell: OrthorhombicCell,
    settings: ParticleMeshReciprocalSettings,
}

impl ReciprocalInput for BorrowedProviderInput<'_> {
    fn particle_count(&self) -> usize {
        self.position_x.len()
    }

    fn position(&self, particle: usize) -> Position {
        Position::new(
            self.position_x[particle],
            self.position_y[particle],
            self.position_z[particle],
        )
    }

    fn charges_elementary(&self) -> &[f64] {
        self.charges_elementary
    }

    fn cell(&self) -> OrthorhombicCell {
        self.cell
    }

    fn settings(&self) -> ParticleMeshReciprocalSettings {
        self.settings
    }
}

unsafe fn borrowed_provider_channel(
    system: &ParticleMeshReciprocalSystemV1,
    pointer: *const f64,
) -> &[f64] {
    if system.atom_count == 0 {
        return &[];
    }
    // SAFETY: The provider preflight validated this channel's non-null,
    // aligned, addressable range. The private FFI contract keeps every input
    // element initialized and immutable for the duration of this call.
    unsafe { core::slice::from_raw_parts(pointer, system.atom_count) }
}

unsafe fn provider_input<'a>(
    system: &'a ParticleMeshReciprocalSystemV1,
    model: ParticleMeshReciprocalModelV1,
) -> BorrowedProviderInput<'a> {
    // SAFETY: The caller completed descriptor, capacity, mutable-output
    // disjointness, and input/output alias preflight before borrowing any raw
    // channel. Each borrow is bounded by the local system descriptor lifetime.
    BorrowedProviderInput {
        position_x: unsafe { borrowed_provider_channel(system, system.position_x) },
        position_y: unsafe { borrowed_provider_channel(system, system.position_y) },
        position_z: unsafe { borrowed_provider_channel(system, system.position_z) },
        charges_elementary: unsafe { borrowed_provider_channel(system, system.charge) },
        cell: OrthorhombicCell {
            lengths_angstrom: model.cell_lengths_angstrom,
        },
        settings: ParticleMeshReciprocalSettings {
            alpha_per_angstrom: model.alpha_per_angstrom,
            mesh_dimensions: model.mesh_dimensions,
            dielectric: model.dielectric,
        },
    }
}

unsafe fn gather_forces_into_provider_output(
    grid_derivative: &[Complex],
    dimensions: [usize; 3],
    assignments: &[ParticleAssignment],
    charges: &[f64],
    cell: OrthorhombicCell,
    grid_derivative_multiplier: f64,
    output: ParticleMeshReciprocalForceOutputV1,
) -> bool {
    let mut all_forces_are_finite = true;
    for (particle, (assignment, charge)) in
        assignments.iter().zip(charges.iter().copied()).enumerate()
    {
        let force = gather_force(
            grid_derivative,
            dimensions,
            assignment,
            charge,
            cell,
            grid_derivative_multiplier,
        );
        all_forces_are_finite &= force.iter().all(|component| component.is_finite());
        // SAFETY: The provider preflight proved that all three channels are
        // writable, pairwise disjoint, and have capacity for every particle.
        unsafe {
            output.x.add(particle).write(force[0]);
            output.y.add(particle).write(force[1]);
            output.z.add(particle).write(force[2]);
        }
    }
    all_forces_are_finite
}

fn evaluate_with_direct_force_output<I: ReciprocalInput + ?Sized>(
    input: &I,
    output: ParticleMeshReciprocalForceOutputV1,
) -> Result<f64, ParticleMeshReciprocalError> {
    Ok(
        compute_with_transform(input, fft::fft_3d, ForceStorageMode::Direct(output))?
            .evaluation
            .reciprocal_space_kcal_per_mol,
    )
}

unsafe fn evaluate_provider_impl(
    system_pointer: *const ParticleMeshReciprocalSystemV1,
    model_pointer: *const ParticleMeshReciprocalModelV1,
    force_mode: ProviderForceMode,
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

    let compute_forces = match force_mode {
        ProviderForceMode::Transactional(compute_forces) if matches!(compute_forces, 0 | 1) => {
            compute_forces
        }
        ProviderForceMode::Transactional(_) => {
            return Err(ProviderFailure::invalid(
                "compute_forces must be exactly zero or one",
            ));
        }
        ProviderForceMode::Direct => 1,
    };
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

    // SAFETY: All raw descriptor and channel ranges, capacities, mutable
    // output disjointness, and input/output aliases were preflighted above.
    // The borrowed input is consumed only by this call and is never retained.
    let input = unsafe { provider_input(&system, model) };
    let (reciprocal_space_kcal_per_mol, forces, force_output) = match force_mode {
        ProviderForceMode::Transactional(_) => {
            let result = evaluate_with_force_option(&input, compute_forces == 1)
                .map_err(ProviderFailure::from)?;
            (
                result.reciprocal_space_kcal_per_mol,
                result.forces_kcal_per_mol_angstrom,
                force_output,
            )
        }
        ProviderForceMode::Direct => {
            let output = force_output.ok_or_else(|| {
                ProviderFailure::invalid("direct force output is null after provider preflight")
            })?;
            let energy =
                evaluate_with_direct_force_output(&input, output).map_err(ProviderFailure::from)?;
            (energy, Vec::new(), None)
        }
    };
    Ok(ProviderCandidate {
        energy: ParticleMeshReciprocalEnergyV1 {
            struct_size: u32::try_from(size_of::<ParticleMeshReciprocalEnergyV1>()).unwrap_or(0),
            abi_version: PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION,
            reciprocal_space_kcal_per_mol,
            reserved: [0; 4],
        },
        forces,
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
/// its declared extent for the call. Input channels must remain immutable for
/// the call. Mutable outputs must not overlap one another or any input region.
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
        // SAFETY: The implementation validates every raw range and alias before
        // borrowing input channels or writing outputs.
        unsafe {
            evaluate_provider_impl(
                system,
                model,
                ProviderForceMode::Transactional(compute_forces),
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

/// Evaluate reciprocal-only order-4 particle-mesh electrostatics directly into
/// reusable caller-owned force channels.
///
/// This hidden dynamics-only entry point validates every descriptor, alias,
/// capacity, input borrow, and fallible allocation before the first force write.
/// A late scientific failure or panic may therefore modify force channels;
/// energy remains transactional and is committed only on success.
///
/// # Safety
/// The base evaluator safety contract applies. Force output is mandatory and
/// must provide three disjoint channels with capacity for every particle.
#[no_mangle]
pub unsafe extern "C" fn bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_v1(
    system: *const ParticleMeshReciprocalSystemV1,
    model: *const ParticleMeshReciprocalModelV1,
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
        // SAFETY: All raw pointer validation, input borrowing, and fallible work
        // precede direct force writes inside the implementation.
        unsafe {
            evaluate_provider_impl(
                system,
                model,
                ProviderForceMode::Direct,
                out_energy,
                out_forces,
                error_range,
                &alias_safety,
            )
        }
    }));
    match outcome {
        Ok(Ok(candidate)) => {
            // SAFETY: Direct forces are complete and candidate energy is valid;
            // no fallible operation remains in this success-only commit.
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

    fn provider_error_detail(error: &ParticleMeshReciprocalErrorV1) -> &str {
        let length = error
            .detail
            .iter()
            .position(|byte| *byte == 0)
            .unwrap_or(error.detail.len());
        core::str::from_utf8(&error.detail[..length]).expect("provider detail must be UTF-8")
    }

    fn assert_injected_allocation_remains_pending(site: AllocationSite) {
        INJECTED_ALLOCATION_FAILURE.with(|injected| {
            let request = injected
                .get()
                .expect("allocation failure injection must remain installed");
            assert_eq!(request.site, site);
            assert_eq!(request.matching_allocations_before_failure, 0);
        });
    }

    fn provider_system(
        position_x: &[f64],
        position_y: &[f64],
        position_z: &[f64],
        charges: &[f64],
    ) -> ParticleMeshReciprocalSystemV1 {
        ParticleMeshReciprocalSystemV1 {
            struct_size: u32::try_from(size_of::<ParticleMeshReciprocalSystemV1>()).unwrap(),
            abi_version: PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION,
            atom_count: charges.len(),
            position_x: position_x.as_ptr(),
            position_y: position_y.as_ptr(),
            position_z: position_z.as_ptr(),
            charge: charges.as_ptr(),
            reserved: [0; 4],
        }
    }

    fn provider_model(mesh_dimensions: [u32; 3]) -> ParticleMeshReciprocalModelV1 {
        ParticleMeshReciprocalModelV1 {
            struct_size: u32::try_from(size_of::<ParticleMeshReciprocalModelV1>()).unwrap(),
            abi_version: PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION,
            cell_lengths_angstrom: [18.0, 20.0, 22.0],
            alpha_per_angstrom: 0.31,
            mesh_dimensions,
            reserved0: 0,
            dielectric: 1.0,
            reserved: [0; 4],
        }
    }

    fn provider_force_output(
        force_x: &mut [f64],
        force_y: &mut [f64],
        force_z: &mut [f64],
    ) -> ParticleMeshReciprocalForceOutputV1 {
        ParticleMeshReciprocalForceOutputV1 {
            struct_size: u32::try_from(size_of::<ParticleMeshReciprocalForceOutputV1>()).unwrap(),
            abi_version: PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION,
            capacity: force_x.len(),
            x: force_x.as_mut_ptr(),
            y: force_y.as_mut_ptr(),
            z: force_z.as_mut_ptr(),
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
        for removed_copy in [
            concat!("copy_validated_", "slice"),
            concat!("ProviderChannel", "Copy"),
            concat!("Provider", "Positions"),
        ] {
            assert!(
                !production.contains(removed_copy),
                "removed provider allocation path must not return through {removed_copy}"
            );
        }

        let provider_channel = production
            .split_once("unsafe fn borrowed_provider_channel")
            .expect("borrowed provider channel helper must remain private")
            .1
            .split_once("unsafe fn provider_input")
            .expect("borrowed provider input constructor must follow its helper")
            .0;
        assert!(
            provider_channel
                .find("if system.atom_count == 0")
                .expect("zero-count provider channels must be explicit")
                < provider_channel
                    .find("core::slice::from_raw_parts")
                    .expect("non-empty provider channels must be borrowed"),
            "zero-count channels must become &[] before from_raw_parts"
        );

        let provider_impl = production
            .split_once("unsafe fn evaluate_provider_impl")
            .expect("provider implementation must remain explicit")
            .1
            .split_once("unsafe fn validate_error_output")
            .expect("provider implementation boundary must remain explicit")
            .0;
        let borrow = provider_impl
            .find("provider_input(&system, model)")
            .expect("provider must construct a borrowed input");
        for preflight in [
            "if output.capacity < system.atom_count",
            "require_disjoint_outputs(&mutable_ranges)",
            "for input_range in input_ranges.into_iter().flatten()",
        ] {
            assert!(
                provider_impl
                    .find(preflight)
                    .unwrap_or_else(|| panic!("missing provider preflight {preflight}"))
                    < borrow,
                "provider preflight {preflight} must precede raw input borrowing"
            );
        }
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

    #[test]
    fn borrowed_provider_input_preserves_channel_identity_length_and_bits() {
        let position_x = [1.25, 5.1, 10.2, 15.4];
        let position_y = [2.5, 3.2, 12.3, 17.1];
        let position_z = [3.75, 8.4, 7.7, 19.3];
        let charges = [0.7, -0.4, -0.6, 0.300_000_000_000_000_04];
        let system = provider_system(&position_x, &position_y, &position_z, &charges);
        let model = provider_model([16; 3]);

        // SAFETY: The descriptor channels are initialized, immutable, and
        // live for the complete lifetime of this call-local borrowed view.
        let input = unsafe { provider_input(&system, model) };
        for (borrowed, original) in [
            (input.position_x, position_x.as_slice()),
            (input.position_y, position_y.as_slice()),
            (input.position_z, position_z.as_slice()),
            (input.charges_elementary, charges.as_slice()),
        ] {
            assert_eq!(borrowed.as_ptr(), original.as_ptr());
            assert_eq!(borrowed.len(), original.len());
            assert_eq!(
                borrowed
                    .iter()
                    .copied()
                    .map(f64::to_bits)
                    .collect::<Vec<_>>(),
                original
                    .iter()
                    .copied()
                    .map(f64::to_bits)
                    .collect::<Vec<_>>()
            );
        }
    }

    #[test]
    fn zero_count_provider_accepts_null_channels_without_forming_raw_slices() {
        let system = ParticleMeshReciprocalSystemV1 {
            struct_size: 80,
            abi_version: 1,
            atom_count: 0,
            position_x: ptr::null(),
            position_y: ptr::null(),
            position_z: ptr::null(),
            charge: ptr::null(),
            reserved: [0; 4],
        };
        let model = provider_model([4; 3]);
        let mut energy = initialized_energy(123.0);
        let mut error = initialized_error();
        // SAFETY: Zero-length input channels may be null and no force output is
        // requested. The provider must reach semantic empty-system validation.
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
        assert_eq!(status, STATUS_INVALID_ARGUMENT);
        assert_eq!(
            error.typed_code,
            ParticleMeshReciprocalErrorCodeV1::EmptySystem as i32
        );
        assert_eq!(
            provider_error_detail(&error),
            "at least one particle is required"
        );
        assert_eq!(
            energy.reciprocal_space_kcal_per_mol.to_bits(),
            123.0_f64.to_bits()
        );
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
            line_scratch: &mut [Complex],
        ) {
            fft::fft_3d(values, dimensions, inverse, line_scratch);
            if inverse {
                values[0].real = f64::INFINITY;
            }
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
    fn reciprocal_axes_share_one_contiguous_noncubic_backing() {
        let dimensions = [4, 8, 16];
        let cell_lengths = [18.0, 20.0, 22.0];
        let storage = reciprocal_axis_data(dimensions, cell_lengths)
            .expect("validated reciprocal axes must allocate");
        assert_eq!(storage.len(), dimensions.into_iter().sum::<usize>());

        let (x_axis_data, yz_axis_data) = storage.split_at(dimensions[0]);
        let (y_axis_data, z_axis_data) = yz_axis_data.split_at(dimensions[1]);
        assert_eq!(
            [x_axis_data.len(), y_axis_data.len(), z_axis_data.len()],
            dimensions
        );
        assert_eq!(
            x_axis_data.as_ptr().wrapping_add(x_axis_data.len()),
            y_axis_data.as_ptr()
        );
        assert_eq!(
            y_axis_data.as_ptr().wrapping_add(y_axis_data.len()),
            z_axis_data.as_ptr()
        );

        let axes = [x_axis_data, y_axis_data, z_axis_data];
        for (axis, axis_data) in axes.into_iter().enumerate() {
            for (index, datum) in axis_data.iter().enumerate() {
                let signed_index = signed_mesh_index(index, dimensions[axis]);
                let wave = core::f64::consts::TAU * f64::from(signed_index) / cell_lengths[axis];
                let angle = core::f64::consts::TAU * f64::from(signed_index)
                    / bounded_usize_to_f64(dimensions[axis]);
                assert_eq!(datum.wave_squared.to_bits(), (wave * wave).to_bits());
                assert_eq!(
                    datum.assignment_modulus.to_bits(),
                    ((2.0 + libm::cos(angle)) / 3.0).to_bits()
                );
            }
        }
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
    fn noncubic_spectrum_and_fft_line_storage_has_exact_contiguous_split() {
        let validated = ValidatedInput {
            dimensions: [4, 8, 16],
            mesh_point_count: 512,
            volume_angstrom_cubed: 1.0,
        };
        let mut storage = spectrum_and_fft_line_scratch(&validated)
            .expect("combined spectrum and FFT line storage must allocate");
        assert_eq!(storage.len(), 528);
        let storage_pointer = storage.as_ptr();
        let (spectrum, fft_line_scratch) = storage.split_at_mut(validated.mesh_point_count);
        assert_eq!(spectrum.len(), 512);
        assert_eq!(fft_line_scratch.len(), 16);
        assert_eq!(spectrum.as_ptr(), storage_pointer);
        // SAFETY: The checked backing length is 528 and the split index is 512.
        assert_eq!(fft_line_scratch.as_ptr(), unsafe {
            storage_pointer.add(512)
        });
    }

    #[test]
    fn fft_reuses_one_line_scratch_overwrites_poison_and_remains_reversible() {
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
        let mut line_scratch = vec![Complex::default(); 8];
        assert_eq!(line_scratch.len(), 8);
        let line_pointer = line_scratch.as_ptr();
        let line_capacity = line_scratch.capacity();
        line_scratch.fill(Complex::new(f64::NAN, f64::NAN));
        fft::fft_3d(&mut transformed, dimensions, false, &mut line_scratch);
        assert_eq!(line_scratch.as_ptr(), line_pointer);
        assert_eq!(line_scratch.capacity(), line_capacity);
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
        line_scratch.fill(Complex::new(f64::NAN, f64::NAN));
        fft::fft_3d(&mut transformed, dimensions, true, &mut line_scratch);
        assert_eq!(line_scratch.as_ptr(), line_pointer);
        assert_eq!(line_scratch.capacity(), line_capacity);
        for (actual, expected) in transformed.iter().zip(original) {
            assert!((actual.real - expected.real).abs() <= 2.0e-12);
            assert!(actual.imaginary.abs() <= 2.0e-12);
        }
    }

    #[test]
    fn shared_fft_line_scratch_overwrites_poison_without_pipeline_bit_drift() {
        fn poison_scratch_after_forward(
            values: &mut [Complex],
            dimensions: [usize; 3],
            inverse: bool,
            line_scratch: &mut [Complex],
        ) {
            fft::fft_3d(values, dimensions, inverse, line_scratch);
            if !inverse {
                line_scratch.fill(Complex::new(f64::NAN, f64::NAN));
            }
        }

        let input = fixture([4, 8, 4]);
        let expected = evaluate(&input).expect("baseline must evaluate");
        let actual = evaluate_with_transform(&input, poison_scratch_after_forward, true)
            .expect("poisoned shared scratch must be overwritten before every read");
        assert_eq!(
            actual.reciprocal_space_kcal_per_mol.to_bits(),
            expected.reciprocal_space_kcal_per_mol.to_bits()
        );
        assert_eq!(actual.forces_kcal_per_mol_angstrom.len(), 4);
        for (actual_force, expected_force) in actual
            .forces_kcal_per_mol_angstrom
            .iter()
            .zip(expected.forces_kcal_per_mol_angstrom)
        {
            assert_eq!(
                actual_force.map(f64::to_bits),
                expected_force.map(f64::to_bits)
            );
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
    fn owned_and_three_borrowed_output_modes_are_bit_identical_and_retain_inputs() {
        let position_x = [1.25, 5.1, 10.2, 15.4];
        let position_y = [2.5, 3.2, 12.3, 17.1];
        let position_z = [3.75, 8.4, 7.7, 19.3];
        let charges = [0.7, -0.4, -0.6, 0.300_000_000_000_000_04];
        let position_x_before = position_x.map(f64::to_bits);
        let position_y_before = position_y.map(f64::to_bits);
        let position_z_before = position_z.map(f64::to_bits);
        let charges_before = charges.map(f64::to_bits);
        let system = provider_system(&position_x, &position_y, &position_z, &charges);
        let model = provider_model([16; 3]);
        let owned = fixture([16; 3]);
        let owned_with_forces = evaluate_with_force_option(&owned, true)
            .expect("owned fixture must evaluate with forces");
        let owned_energy_only = evaluate_with_force_option(&owned, false)
            .expect("owned fixture must evaluate without forces");

        let mut borrowed_energy_only = initialized_energy(11.0);
        let mut borrowed_energy_only_error = initialized_error();
        // SAFETY: Every input remains initialized, immutable, and live. The
        // energy-only mode requires a null force descriptor.
        assert_eq!(
            unsafe {
                super::bg_rust_particle_mesh_reciprocal_evaluate_v1(
                    &system,
                    &model,
                    0,
                    &mut borrowed_energy_only,
                    ptr::null_mut(),
                    &mut borrowed_energy_only_error,
                )
            },
            STATUS_OK
        );

        let mut transactional_energy = initialized_energy(101.0);
        let mut transactional_x = [201.0; 5];
        let mut transactional_y = [202.0; 5];
        let mut transactional_z = [203.0; 5];
        transactional_x[4] = 301.0;
        transactional_y[4] = 302.0;
        transactional_z[4] = 303.0;
        let mut transactional_output = provider_force_output(
            &mut transactional_x,
            &mut transactional_y,
            &mut transactional_z,
        );
        let mut transactional_error = initialized_error();
        // SAFETY: Every descriptor and channel is initialized, live, and
        // disjoint, with one extra force element beyond atom_count.
        assert_eq!(
            unsafe {
                super::bg_rust_particle_mesh_reciprocal_evaluate_v1(
                    &system,
                    &model,
                    1,
                    &mut transactional_energy,
                    &mut transactional_output,
                    &mut transactional_error,
                )
            },
            STATUS_OK
        );

        let mut direct_energy = initialized_energy(401.0);
        let mut direct_x = [501.0; 5];
        let mut direct_y = [502.0; 5];
        let mut direct_z = [503.0; 5];
        direct_x[4] = 301.0;
        direct_y[4] = 302.0;
        direct_z[4] = 303.0;
        let mut direct_output = provider_force_output(&mut direct_x, &mut direct_y, &mut direct_z);
        let mut direct_error = initialized_error();
        // SAFETY: The reusable output follows the same live, disjoint contract.
        assert_eq!(
            unsafe {
                super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_v1(
                    &system,
                    &model,
                    &mut direct_energy,
                    &mut direct_output,
                    &mut direct_error,
                )
            },
            STATUS_OK
        );

        assert_eq!(
            owned_with_forces.reciprocal_space_kcal_per_mol.to_bits(),
            owned_energy_only.reciprocal_space_kcal_per_mol.to_bits()
        );
        assert_eq!(
            owned_with_forces.reciprocal_space_kcal_per_mol.to_bits(),
            borrowed_energy_only.reciprocal_space_kcal_per_mol.to_bits()
        );
        assert_eq!(
            transactional_energy.reciprocal_space_kcal_per_mol.to_bits(),
            direct_energy.reciprocal_space_kcal_per_mol.to_bits()
        );
        assert_eq!(
            owned_with_forces.reciprocal_space_kcal_per_mol.to_bits(),
            transactional_energy.reciprocal_space_kcal_per_mol.to_bits()
        );
        for (particle, owned_force) in owned_with_forces
            .forces_kcal_per_mol_angstrom
            .iter()
            .enumerate()
        {
            assert_eq!(
                transactional_x[particle].to_bits(),
                owned_force[0].to_bits()
            );
            assert_eq!(
                transactional_y[particle].to_bits(),
                owned_force[1].to_bits()
            );
            assert_eq!(
                transactional_z[particle].to_bits(),
                owned_force[2].to_bits()
            );
        }
        assert_eq!(
            transactional_x.map(f64::to_bits),
            direct_x.map(f64::to_bits)
        );
        assert_eq!(
            transactional_y.map(f64::to_bits),
            direct_y.map(f64::to_bits)
        );
        assert_eq!(
            transactional_z.map(f64::to_bits),
            direct_z.map(f64::to_bits)
        );
        assert_eq!(direct_x[4].to_bits(), 301.0_f64.to_bits());
        assert_eq!(direct_y[4].to_bits(), 302.0_f64.to_bits());
        assert_eq!(direct_z[4].to_bits(), 303.0_f64.to_bits());
        assert_eq!(position_x.map(f64::to_bits), position_x_before);
        assert_eq!(position_y.map(f64::to_bits), position_y_before);
        assert_eq!(position_z.map(f64::to_bits), position_z_before);
        assert_eq!(charges.map(f64::to_bits), charges_before);
        assert_eq!(
            borrowed_energy_only_error.typed_code,
            ParticleMeshReciprocalErrorCodeV1::None as i32
        );
        assert!(borrowed_energy_only_error
            .detail
            .iter()
            .all(|byte| *byte == 0));
        assert_eq!(
            direct_error.typed_code,
            ParticleMeshReciprocalErrorCodeV1::None as i32
        );
        assert!(direct_error.detail.iter().all(|byte| *byte == 0));
    }

    #[test]
    fn direct_provider_skips_force_allocation_and_preserves_outputs_on_earlier_oom() {
        let position_x = [1.25, 5.1, 10.2, 15.4];
        let position_y = [2.5, 3.2, 12.3, 17.1];
        let position_z = [3.75, 8.4, 7.7, 19.3];
        let charges = [0.7, -0.4, -0.6, 0.300_000_000_000_000_04];
        let input_before = [
            position_x.map(f64::to_bits),
            position_y.map(f64::to_bits),
            position_z.map(f64::to_bits),
            charges.map(f64::to_bits),
        ];
        let system = provider_system(&position_x, &position_y, &position_z, &charges);
        let model = provider_model([4; 3]);

        let mut transactional_energy = initialized_energy(101.0);
        let mut transactional_x = [201.0; 4];
        let mut transactional_y = [202.0; 4];
        let mut transactional_z = [203.0; 4];
        let mut transactional_output = provider_force_output(
            &mut transactional_x,
            &mut transactional_y,
            &mut transactional_z,
        );
        let mut transactional_error = initialized_error();
        {
            let _injection = AllocationFailureGuard::inject(AllocationSite::ForceOutput);
            // SAFETY: The transactional output is valid; the test hook fails
            // only its private force-vector allocation.
            assert_eq!(
                unsafe {
                    super::bg_rust_particle_mesh_reciprocal_evaluate_v1(
                        &system,
                        &model,
                        1,
                        &mut transactional_energy,
                        &mut transactional_output,
                        &mut transactional_error,
                    )
                },
                STATUS_OUT_OF_MEMORY
            );
        }
        assert_eq!(
            transactional_energy.reciprocal_space_kcal_per_mol.to_bits(),
            101.0_f64.to_bits()
        );
        assert_eq!(transactional_x, [201.0; 4]);
        assert_eq!(transactional_y, [202.0; 4]);
        assert_eq!(transactional_z, [203.0; 4]);

        let mut direct_energy = initialized_energy(301.0);
        let mut direct_x = [401.0; 4];
        let mut direct_y = [402.0; 4];
        let mut direct_z = [403.0; 4];
        let mut direct_output = provider_force_output(&mut direct_x, &mut direct_y, &mut direct_z);
        let mut direct_error = initialized_error();
        {
            let _injection = AllocationFailureGuard::inject(AllocationSite::ForceOutput);
            // SAFETY: The direct output is valid. This path deliberately has no
            // force-vector allocation for the injected site to reject.
            assert_eq!(
                unsafe {
                    super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_v1(
                        &system,
                        &model,
                        &mut direct_energy,
                        &mut direct_output,
                        &mut direct_error,
                    )
                },
                STATUS_OK
            );
        }
        assert_ne!(
            direct_energy.reciprocal_space_kcal_per_mol.to_bits(),
            301.0_f64.to_bits()
        );

        for site in [
            AllocationSite::NeutralitySort,
            AllocationSite::ParticleAssignments,
            AllocationSite::SpectrumAndFftLineScratch,
            AllocationSite::ReciprocalAxisData,
        ] {
            let mut energy = initialized_energy(501.0);
            let mut force_x = [601.0; 4];
            let mut force_y = [602.0; 4];
            let mut force_z = [603.0; 4];
            let mut output = provider_force_output(&mut force_x, &mut force_y, &mut force_z);
            let mut error = initialized_error();
            let _injection = AllocationFailureGuard::inject(site);
            // SAFETY: Valid disjoint output exercises each fallible allocation
            // that must finish before the first direct force write.
            let status = unsafe {
                super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_v1(
                    &system,
                    &model,
                    &mut energy,
                    &mut output,
                    &mut error,
                )
            };
            assert_eq!(status, STATUS_OUT_OF_MEMORY, "allocation site {site:?}");
            assert_eq!(
                energy.reciprocal_space_kcal_per_mol.to_bits(),
                501.0_f64.to_bits(),
                "allocation site {site:?}"
            );
            assert_eq!(force_x, [601.0; 4], "allocation site {site:?}");
            assert_eq!(force_y, [602.0; 4], "allocation site {site:?}");
            assert_eq!(force_z, [603.0; 4], "allocation site {site:?}");
        }

        let mut energy = initialized_energy(701.0);
        let mut force_x = [801.0; 5];
        let mut force_y = [802.0; 5];
        let mut force_z = [803.0; 5];
        force_x[4] = 901.0;
        force_y[4] = 902.0;
        force_z[4] = 903.0;
        let mut output = provider_force_output(&mut force_x, &mut force_y, &mut force_z);
        output.capacity = 4;
        let mut error = initialized_error();
        {
            let _injection =
                AllocationFailureGuard::inject_at(AllocationSite::ReciprocalAxisData, 1);
            // SAFETY: The sole reciprocal-axis backing reserve remains the
            // final fallible direct allocation before the first force write.
            let status = unsafe {
                super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_v1(
                    &system,
                    &model,
                    &mut energy,
                    &mut output,
                    &mut error,
                )
            };
            assert_eq!(status, STATUS_OUT_OF_MEMORY);
        }
        assert_eq!(
            energy.reciprocal_space_kcal_per_mol.to_bits(),
            701.0_f64.to_bits()
        );
        assert_eq!(force_x, [801.0, 801.0, 801.0, 801.0, 901.0]);
        assert_eq!(force_y, [802.0, 802.0, 802.0, 802.0, 902.0]);
        assert_eq!(force_z, [803.0, 803.0, 803.0, 803.0, 903.0]);
        assert_eq!(position_x.map(f64::to_bits), input_before[0]);
        assert_eq!(position_y.map(f64::to_bits), input_before[1]);
        assert_eq!(position_z.map(f64::to_bits), input_before[2]);
        assert_eq!(charges.map(f64::to_bits), input_before[3]);

        let mut energy = initialized_energy(1_001.0);
        let mut force_x = [1_101.0; 5];
        let mut force_y = [1_102.0; 5];
        let mut force_z = [1_103.0; 5];
        force_x[4] = 1_201.0;
        force_y[4] = 1_202.0;
        force_z[4] = 1_203.0;
        let mut output = provider_force_output(&mut force_x, &mut force_y, &mut force_z);
        output.capacity = 4;
        let mut error = initialized_error();
        {
            let _injection =
                AllocationFailureGuard::inject_at(AllocationSite::SpectrumAndFftLineScratch, 1);
            // SAFETY: The combined storage allocation precedes every caller
            // force write, and the fifth elements are valid protected tails.
            let status = unsafe {
                super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_v1(
                    &system,
                    &model,
                    &mut energy,
                    &mut output,
                    &mut error,
                )
            };
            assert_eq!(status, STATUS_OUT_OF_MEMORY);
        }
        assert_eq!(
            provider_error_detail(&error),
            AllocationSite::SpectrumAndFftLineScratch.detail()
        );
        assert_eq!(
            energy.reciprocal_space_kcal_per_mol.to_bits(),
            1_001.0_f64.to_bits()
        );
        assert_eq!(force_x, [1_101.0, 1_101.0, 1_101.0, 1_101.0, 1_201.0]);
        assert_eq!(force_y, [1_102.0, 1_102.0, 1_102.0, 1_102.0, 1_202.0]);
        assert_eq!(force_z, [1_103.0, 1_103.0, 1_103.0, 1_103.0, 1_203.0]);
        assert_eq!(position_x.map(f64::to_bits), input_before[0]);
        assert_eq!(position_y.map(f64::to_bits), input_before[1]);
        assert_eq!(position_z.map(f64::to_bits), input_before[2]);
        assert_eq!(charges.map(f64::to_bits), input_before[3]);
    }

    #[test]
    fn provider_modes_share_one_reciprocal_axis_backing_and_leave_second_occurrence_pending() {
        let position_x = [1.25, 5.1, 10.2, 15.4];
        let position_y = [2.5, 3.2, 12.3, 17.1];
        let position_z = [3.75, 8.4, 7.7, 19.3];
        let charges = [0.7, -0.4, -0.6, 0.300_000_000_000_000_04];
        let input_before = [
            position_x.map(f64::to_bits),
            position_y.map(f64::to_bits),
            position_z.map(f64::to_bits),
            charges.map(f64::to_bits),
        ];
        let system = provider_system(&position_x, &position_y, &position_z, &charges);
        let model = provider_model([4, 8, 16]);
        let expected = evaluate(&fixture([4, 8, 16])).expect("noncubic baseline must evaluate");

        let mut energy_only = initialized_energy(101.0);
        let mut energy_only_error = initialized_error();
        {
            let _injection =
                AllocationFailureGuard::inject_at(AllocationSite::ReciprocalAxisData, 2);
            // SAFETY: Valid immutable input and disjoint descriptors exercise
            // the energy-only provider with a null force output.
            assert_eq!(
                unsafe {
                    super::bg_rust_particle_mesh_reciprocal_evaluate_v1(
                        &system,
                        &model,
                        0,
                        &mut energy_only,
                        ptr::null_mut(),
                        &mut energy_only_error,
                    )
                },
                STATUS_OK
            );
            assert_injected_allocation_remains_pending(AllocationSite::ReciprocalAxisData);
        }

        let mut transactional_energy = initialized_energy(201.0);
        let mut transactional_x = [301.0; 5];
        let mut transactional_y = [302.0; 5];
        let mut transactional_z = [303.0; 5];
        transactional_x[4] = 401.0;
        transactional_y[4] = 402.0;
        transactional_z[4] = 403.0;
        let mut transactional_output = provider_force_output(
            &mut transactional_x,
            &mut transactional_y,
            &mut transactional_z,
        );
        transactional_output.capacity = 4;
        let mut transactional_error = initialized_error();
        {
            let _injection =
                AllocationFailureGuard::inject_at(AllocationSite::ReciprocalAxisData, 2);
            // SAFETY: All transactional descriptors and channels are valid,
            // live, disjoint, and sized for the four-particle input.
            assert_eq!(
                unsafe {
                    super::bg_rust_particle_mesh_reciprocal_evaluate_v1(
                        &system,
                        &model,
                        1,
                        &mut transactional_energy,
                        &mut transactional_output,
                        &mut transactional_error,
                    )
                },
                STATUS_OK
            );
            assert_injected_allocation_remains_pending(AllocationSite::ReciprocalAxisData);
        }

        let mut direct_energy = initialized_energy(501.0);
        let mut direct_x = [601.0; 5];
        let mut direct_y = [602.0; 5];
        let mut direct_z = [603.0; 5];
        direct_x[4] = 701.0;
        direct_y[4] = 702.0;
        direct_z[4] = 703.0;
        let mut direct_output = provider_force_output(&mut direct_x, &mut direct_y, &mut direct_z);
        direct_output.capacity = 4;
        let mut direct_error = initialized_error();
        {
            let _injection =
                AllocationFailureGuard::inject_at(AllocationSite::ReciprocalAxisData, 2);
            // SAFETY: The direct output follows the same valid live,
            // disjoint, and four-particle capacity contract.
            assert_eq!(
                unsafe {
                    super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_v1(
                        &system,
                        &model,
                        &mut direct_energy,
                        &mut direct_output,
                        &mut direct_error,
                    )
                },
                STATUS_OK
            );
            assert_injected_allocation_remains_pending(AllocationSite::ReciprocalAxisData);
        }

        for actual_energy in [&energy_only, &transactional_energy, &direct_energy] {
            assert_eq!(
                actual_energy.reciprocal_space_kcal_per_mol.to_bits(),
                expected.reciprocal_space_kcal_per_mol.to_bits()
            );
        }
        for (particle, expected_force) in expected.forces_kcal_per_mol_angstrom.iter().enumerate() {
            assert_eq!(
                transactional_x[particle].to_bits(),
                expected_force[0].to_bits()
            );
            assert_eq!(
                transactional_y[particle].to_bits(),
                expected_force[1].to_bits()
            );
            assert_eq!(
                transactional_z[particle].to_bits(),
                expected_force[2].to_bits()
            );
            assert_eq!(direct_x[particle].to_bits(), expected_force[0].to_bits());
            assert_eq!(direct_y[particle].to_bits(), expected_force[1].to_bits());
            assert_eq!(direct_z[particle].to_bits(), expected_force[2].to_bits());
        }
        assert_eq!(transactional_x[4].to_bits(), 401.0_f64.to_bits());
        assert_eq!(transactional_y[4].to_bits(), 402.0_f64.to_bits());
        assert_eq!(transactional_z[4].to_bits(), 403.0_f64.to_bits());
        assert_eq!(direct_x[4].to_bits(), 701.0_f64.to_bits());
        assert_eq!(direct_y[4].to_bits(), 702.0_f64.to_bits());
        assert_eq!(direct_z[4].to_bits(), 703.0_f64.to_bits());
        for error in [&energy_only_error, &transactional_error, &direct_error] {
            assert_eq!(
                error.typed_code,
                ParticleMeshReciprocalErrorCodeV1::None as i32
            );
            assert!(error.detail.iter().all(|byte| *byte == 0));
        }
        assert_eq!(position_x.map(f64::to_bits), input_before[0]);
        assert_eq!(position_y.map(f64::to_bits), input_before[1]);
        assert_eq!(position_z.map(f64::to_bits), input_before[2]);
        assert_eq!(charges.map(f64::to_bits), input_before[3]);
    }

    #[test]
    fn provider_modes_share_one_spectrum_and_fft_line_storage_and_leave_second_occurrence_pending()
    {
        let position_x = [1.25, 5.1, 10.2, 15.4];
        let position_y = [2.5, 3.2, 12.3, 17.1];
        let position_z = [3.75, 8.4, 7.7, 19.3];
        let charges = [0.7, -0.4, -0.6, 0.300_000_000_000_000_04];
        let input_before = [
            position_x.map(f64::to_bits),
            position_y.map(f64::to_bits),
            position_z.map(f64::to_bits),
            charges.map(f64::to_bits),
        ];
        let system = provider_system(&position_x, &position_y, &position_z, &charges);
        let model = provider_model([4; 3]);
        let expected = evaluate(&fixture([4; 3])).expect("owned baseline must evaluate");

        let mut energy_only = initialized_energy(11.0);
        let mut energy_only_error = initialized_error();
        {
            let _injection =
                AllocationFailureGuard::inject_at(AllocationSite::SpectrumAndFftLineScratch, 2);
            // SAFETY: Valid immutable inputs and disjoint output descriptors
            // exercise the single combined provider allocation.
            assert_eq!(
                unsafe {
                    super::bg_rust_particle_mesh_reciprocal_evaluate_v1(
                        &system,
                        &model,
                        0,
                        &mut energy_only,
                        ptr::null_mut(),
                        &mut energy_only_error,
                    )
                },
                STATUS_OK
            );
            assert_injected_allocation_remains_pending(AllocationSite::SpectrumAndFftLineScratch);
        }

        let mut transactional_energy = initialized_energy(101.0);
        let mut transactional_x = [201.0; 5];
        let mut transactional_y = [202.0; 5];
        let mut transactional_z = [203.0; 5];
        transactional_x[4] = 301.0;
        transactional_y[4] = 302.0;
        transactional_z[4] = 303.0;
        let mut transactional_output = provider_force_output(
            &mut transactional_x,
            &mut transactional_y,
            &mut transactional_z,
        );
        transactional_output.capacity = 4;
        let mut transactional_error = initialized_error();
        {
            let _injection =
                AllocationFailureGuard::inject_at(AllocationSite::SpectrumAndFftLineScratch, 2);
            // SAFETY: The provider descriptors and output channels are valid,
            // live, disjoint, and sized for all four particles.
            assert_eq!(
                unsafe {
                    super::bg_rust_particle_mesh_reciprocal_evaluate_v1(
                        &system,
                        &model,
                        1,
                        &mut transactional_energy,
                        &mut transactional_output,
                        &mut transactional_error,
                    )
                },
                STATUS_OK
            );
            assert_injected_allocation_remains_pending(AllocationSite::SpectrumAndFftLineScratch);
        }

        let mut direct_energy = initialized_energy(401.0);
        let mut direct_x = [501.0; 5];
        let mut direct_y = [502.0; 5];
        let mut direct_z = [503.0; 5];
        direct_x[4] = 601.0;
        direct_y[4] = 602.0;
        direct_z[4] = 603.0;
        let mut direct_output = provider_force_output(&mut direct_x, &mut direct_y, &mut direct_z);
        direct_output.capacity = 4;
        let mut direct_error = initialized_error();
        {
            let _injection =
                AllocationFailureGuard::inject_at(AllocationSite::SpectrumAndFftLineScratch, 2);
            // SAFETY: The reusable output follows the same valid live and
            // disjoint contract as the transactional output above.
            assert_eq!(
                unsafe {
                    super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_v1(
                        &system,
                        &model,
                        &mut direct_energy,
                        &mut direct_output,
                        &mut direct_error,
                    )
                },
                STATUS_OK
            );
            assert_injected_allocation_remains_pending(AllocationSite::SpectrumAndFftLineScratch);
        }

        assert_eq!(
            energy_only.reciprocal_space_kcal_per_mol.to_bits(),
            expected.reciprocal_space_kcal_per_mol.to_bits()
        );
        assert_eq!(
            transactional_energy.reciprocal_space_kcal_per_mol.to_bits(),
            expected.reciprocal_space_kcal_per_mol.to_bits()
        );
        assert_eq!(
            direct_energy.reciprocal_space_kcal_per_mol.to_bits(),
            expected.reciprocal_space_kcal_per_mol.to_bits()
        );
        for (particle, expected_force) in expected.forces_kcal_per_mol_angstrom.iter().enumerate() {
            assert_eq!(
                transactional_x[particle].to_bits(),
                expected_force[0].to_bits()
            );
            assert_eq!(
                transactional_y[particle].to_bits(),
                expected_force[1].to_bits()
            );
            assert_eq!(
                transactional_z[particle].to_bits(),
                expected_force[2].to_bits()
            );
            assert_eq!(direct_x[particle].to_bits(), expected_force[0].to_bits());
            assert_eq!(direct_y[particle].to_bits(), expected_force[1].to_bits());
            assert_eq!(direct_z[particle].to_bits(), expected_force[2].to_bits());
        }
        assert_eq!(transactional_x[4].to_bits(), 301.0_f64.to_bits());
        assert_eq!(transactional_y[4].to_bits(), 302.0_f64.to_bits());
        assert_eq!(transactional_z[4].to_bits(), 303.0_f64.to_bits());
        assert_eq!(direct_x[4].to_bits(), 601.0_f64.to_bits());
        assert_eq!(direct_y[4].to_bits(), 602.0_f64.to_bits());
        assert_eq!(direct_z[4].to_bits(), 603.0_f64.to_bits());
        for error in [&energy_only_error, &transactional_error, &direct_error] {
            assert_eq!(
                error.typed_code,
                ParticleMeshReciprocalErrorCodeV1::None as i32
            );
            assert!(error.detail.iter().all(|byte| *byte == 0));
        }
        assert_eq!(position_x.map(f64::to_bits), input_before[0]);
        assert_eq!(position_y.map(f64::to_bits), input_before[1]);
        assert_eq!(position_z.map(f64::to_bits), input_before[2]);
        assert_eq!(charges.map(f64::to_bits), input_before[3]);
    }

    #[test]
    fn direct_provider_preflights_capacity_and_aliases_before_force_writes() {
        let mut position_x = [1.25, 5.1, 10.2, 15.4];
        let mut position_y = [2.5, 3.2, 12.3, 17.1];
        let mut position_z = [3.75, 8.4, 7.7, 19.3];
        let mut charges = [0.7, -0.4, -0.6, 0.300_000_000_000_000_04];
        let system = provider_system(&position_x, &position_y, &position_z, &charges);
        let model = provider_model([4; 3]);

        let mut energy = initialized_energy(101.0);
        let mut force_x = [201.0; 4];
        let mut force_y = [202.0; 4];
        let mut force_z = [203.0; 4];
        let mut undersized = provider_force_output(&mut force_x, &mut force_y, &mut force_z);
        undersized.capacity = 3;
        let mut error = initialized_error();
        // SAFETY: The backing channels are live for four particles while the
        // descriptor deliberately advertises insufficient capacity.
        assert_eq!(
            unsafe {
                super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_v1(
                    &system,
                    &model,
                    &mut energy,
                    &mut undersized,
                    &mut error,
                )
            },
            STATUS_CAPACITY_OVERFLOW
        );
        assert_eq!(
            energy.reciprocal_space_kcal_per_mol.to_bits(),
            101.0_f64.to_bits()
        );
        assert_eq!(force_x, [201.0; 4]);
        assert_eq!(force_y, [202.0; 4]);
        assert_eq!(force_z, [203.0; 4]);

        let mut overlapping = [301.0; 4];
        let mut separate_z = [303.0; 4];
        let mut overlapping_output = ParticleMeshReciprocalForceOutputV1 {
            struct_size: 72,
            abi_version: 1,
            capacity: 4,
            x: overlapping.as_mut_ptr(),
            y: overlapping.as_mut_ptr(),
            z: separate_z.as_mut_ptr(),
            reserved: [0; 4],
        };
        let mut error = initialized_error();
        // SAFETY: All storage is live, but x and y deliberately overlap so the
        // provider must reject the request without writing either channel.
        assert_eq!(
            unsafe {
                super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_v1(
                    &system,
                    &model,
                    &mut energy,
                    &mut overlapping_output,
                    &mut error,
                )
            },
            STATUS_INVALID_ARGUMENT
        );
        assert_eq!(overlapping, [301.0; 4]);
        assert_eq!(separate_z, [303.0; 4]);

        let position_x_before = position_x;
        let position_y_before = position_y;
        let position_z_before = position_z;
        let charges_before = charges;
        for (channel, alias_pointer) in [
            ("position_x", position_x.as_mut_ptr()),
            ("position_y", position_y.as_mut_ptr()),
            ("position_z", position_z.as_mut_ptr()),
            ("charge", charges.as_mut_ptr()),
        ] {
            let mut input_alias_y = [401.0; 4];
            let mut input_alias_z = [403.0; 4];
            let mut input_alias_output = ParticleMeshReciprocalForceOutputV1 {
                struct_size: 72,
                abi_version: 1,
                capacity: 4,
                x: alias_pointer,
                y: input_alias_y.as_mut_ptr(),
                z: input_alias_z.as_mut_ptr(),
                reserved: [0; 4],
            };
            let mut alias_energy = initialized_energy(101.0);
            let mut error = initialized_error();
            // SAFETY: Force x deliberately aliases one initialized input
            // channel. Arithmetic preflight must reject it before borrowing
            // any input slice or writing any output.
            assert_eq!(
                unsafe {
                    super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_v1(
                        &system,
                        &model,
                        &mut alias_energy,
                        &mut input_alias_output,
                        &mut error,
                    )
                },
                STATUS_INVALID_ARGUMENT,
                "input channel {channel}"
            );
            assert_eq!(
                error.typed_code,
                ParticleMeshReciprocalErrorCodeV1::None as i32,
                "input channel {channel}"
            );
            assert_eq!(
                provider_error_detail(&error),
                "particle-mesh reciprocal output storage must not overlap input storage",
                "input channel {channel}"
            );
            assert_eq!(position_x, position_x_before, "input channel {channel}");
            assert_eq!(position_y, position_y_before, "input channel {channel}");
            assert_eq!(position_z, position_z_before, "input channel {channel}");
            assert_eq!(charges, charges_before, "input channel {channel}");
            assert_eq!(input_alias_y, [401.0; 4], "input channel {channel}");
            assert_eq!(input_alias_z, [403.0; 4], "input channel {channel}");
            assert_eq!(
                alias_energy.reciprocal_space_kcal_per_mol.to_bits(),
                101.0_f64.to_bits(),
                "input channel {channel}"
            );
        }

        let non_neutral_charges = [0.95, -0.4, -0.6, 0.300_000_000_000_000_04];
        let non_neutral_system =
            provider_system(&position_x, &position_y, &position_z, &non_neutral_charges);
        let mut non_neutral_energy = initialized_energy(501.0);
        let mut non_neutral_x = [601.0; 4];
        let mut non_neutral_y = [602.0; 4];
        let mut non_neutral_z = [603.0; 4];
        let mut non_neutral_output =
            provider_force_output(&mut non_neutral_x, &mut non_neutral_y, &mut non_neutral_z);
        let mut non_neutral_error = initialized_error();
        // SAFETY: All storage is valid; scientific neutrality validation must
        // fail before the common pipeline reaches direct force writes.
        assert_eq!(
            unsafe {
                super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_v1(
                    &non_neutral_system,
                    &model,
                    &mut non_neutral_energy,
                    &mut non_neutral_output,
                    &mut non_neutral_error,
                )
            },
            STATUS_NUMERICAL_ERROR
        );
        assert_eq!(
            non_neutral_error.typed_code,
            ParticleMeshReciprocalErrorCodeV1::NonNeutralSystem as i32
        );
        assert_eq!(
            non_neutral_energy.reciprocal_space_kcal_per_mol.to_bits(),
            501.0_f64.to_bits()
        );
        assert_eq!(non_neutral_x, [601.0; 4]);
        assert_eq!(non_neutral_y, [602.0; 4]);
        assert_eq!(non_neutral_z, [603.0; 4]);

        let mut error_alias_energy = initialized_energy(701.0);
        let mut error_alias_y = [802.0; 4];
        let mut error_alias_z = [803.0; 4];
        let mut aliased_error = initialized_error();
        let error_pointer = &mut aliased_error as *mut ParticleMeshReciprocalErrorV1;
        let error_before = descriptor_bytes(error_pointer);
        let mut error_alias_output = ParticleMeshReciprocalForceOutputV1 {
            struct_size: 72,
            abi_version: 1,
            capacity: 4,
            x: error_pointer.cast(),
            y: error_alias_y.as_mut_ptr(),
            z: error_alias_z.as_mut_ptr(),
            reserved: [0; 4],
        };
        // SAFETY: Error storage deliberately aliases force x but is large and
        // aligned enough for arithmetic preflight. Rejection must not write it.
        assert_eq!(
            unsafe {
                super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_v1(
                    &system,
                    &model,
                    &mut error_alias_energy,
                    &mut error_alias_output,
                    error_pointer,
                )
            },
            STATUS_INVALID_ARGUMENT
        );
        assert_eq!(descriptor_bytes(error_pointer), error_before);
        assert_eq!(
            error_alias_energy.reciprocal_space_kcal_per_mol.to_bits(),
            701.0_f64.to_bits()
        );
        assert_eq!(error_alias_y, [802.0; 4]);
        assert_eq!(error_alias_z, [803.0; 4]);
    }

    #[test]
    fn late_scientific_failure_keeps_energy_transactional_and_direct_forces_disposable() {
        let position_x = [1.25, 5.1, 10.2, 15.4];
        let position_y = [2.5, 3.2, 12.3, 17.1];
        let position_z = [3.75, 8.4, 7.7, 19.3];
        let charges = [0.7, -0.4, -0.6, 0.300_000_000_000_000_04];
        let input_before = [
            position_x.map(f64::to_bits),
            position_y.map(f64::to_bits),
            position_z.map(f64::to_bits),
            charges.map(f64::to_bits),
        ];
        let system = provider_system(&position_x, &position_y, &position_z, &charges);
        let model = provider_model([4; 3]);

        let mut transactional_energy = initialized_energy(101.0);
        let mut transactional_x = [201.0; 4];
        let mut transactional_y = [202.0; 4];
        let mut transactional_z = [203.0; 4];
        let mut transactional_output = provider_force_output(
            &mut transactional_x,
            &mut transactional_y,
            &mut transactional_z,
        );
        let mut transactional_error = initialized_error();
        {
            let _injection = LateNonFiniteResultGuard::inject();
            // SAFETY: Valid storage exercises a failure after internal force
            // gathering but before transactional output commit.
            assert_eq!(
                unsafe {
                    super::bg_rust_particle_mesh_reciprocal_evaluate_v1(
                        &system,
                        &model,
                        1,
                        &mut transactional_energy,
                        &mut transactional_output,
                        &mut transactional_error,
                    )
                },
                STATUS_NUMERICAL_ERROR
            );
        }
        assert_eq!(
            transactional_energy.reciprocal_space_kcal_per_mol.to_bits(),
            101.0_f64.to_bits()
        );
        assert_eq!(transactional_x, [201.0; 4]);
        assert_eq!(transactional_y, [202.0; 4]);
        assert_eq!(transactional_z, [203.0; 4]);

        let mut direct_energy = initialized_energy(301.0);
        let mut direct_x = [401.0; 4];
        let mut direct_y = [402.0; 4];
        let mut direct_z = [403.0; 4];
        let mut direct_output = provider_force_output(&mut direct_x, &mut direct_y, &mut direct_z);
        let mut direct_error = initialized_error();
        {
            let _injection = LateNonFiniteResultGuard::inject();
            // SAFETY: Valid reusable channels may be modified before this
            // deliberately injected late non-finite scientific result fails.
            assert_eq!(
                unsafe {
                    super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_v1(
                        &system,
                        &model,
                        &mut direct_energy,
                        &mut direct_output,
                        &mut direct_error,
                    )
                },
                STATUS_NUMERICAL_ERROR
            );
        }
        assert_eq!(
            direct_error.typed_code,
            ParticleMeshReciprocalErrorCodeV1::NonFiniteResult as i32
        );
        assert_eq!(
            direct_energy.reciprocal_space_kcal_per_mol.to_bits(),
            301.0_f64.to_bits()
        );
        assert_ne!(direct_x, [401.0; 4]);
        assert_ne!(direct_y, [402.0; 4]);
        assert_ne!(direct_z, [403.0; 4]);
        assert_eq!(position_x.map(f64::to_bits), input_before[0]);
        assert_eq!(position_y.map(f64::to_bits), input_before[1]);
        assert_eq!(position_z.map(f64::to_bits), input_before[2]);
        assert_eq!(charges.map(f64::to_bits), input_before[3]);
    }

    #[test]
    fn injected_allocation_failures_map_to_out_of_memory_without_output_commit() {
        let position_x = [1.25, 5.1, 10.2, 15.4];
        let position_y = [2.5, 3.2, 12.3, 17.1];
        let position_z = [3.75, 8.4, 7.7, 19.3];
        let charges = [0.7, -0.4, -0.6, 0.300_000_000_000_000_04];
        let input_before = [
            position_x.map(f64::to_bits),
            position_y.map(f64::to_bits),
            position_z.map(f64::to_bits),
            charges.map(f64::to_bits),
        ];
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
            AllocationSite::NeutralitySort,
            AllocationSite::ParticleAssignments,
            AllocationSite::SpectrumAndFftLineScratch,
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

        for site in [
            AllocationSite::NeutralitySort,
            AllocationSite::ParticleAssignments,
            AllocationSite::SpectrumAndFftLineScratch,
            AllocationSite::ReciprocalAxisData,
        ] {
            let mut energy = initialized_energy(301.0);
            let mut error = initialized_error();
            let _injection = AllocationFailureGuard::inject(site);
            // SAFETY: Valid immutable inputs and disjoint descriptors exercise
            // every allocation that remains in the borrowed energy-only path.
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
            assert_eq!(status, STATUS_OUT_OF_MEMORY, "allocation site {site:?}");
            assert_eq!(
                provider_error_detail(&error),
                site.detail(),
                "allocation site {site:?}"
            );
            assert_eq!(
                energy.reciprocal_space_kcal_per_mol.to_bits(),
                301.0_f64.to_bits(),
                "allocation site {site:?}"
            );
        }
        assert_eq!(position_x.map(f64::to_bits), input_before[0]);
        assert_eq!(position_y.map(f64::to_bits), input_before[1]);
        assert_eq!(position_z.map(f64::to_bits), input_before[2]);
        assert_eq!(charges.map(f64::to_bits), input_before[3]);

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
