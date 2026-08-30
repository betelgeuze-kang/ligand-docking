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
use std::ffi::c_void;
use std::fmt;
use std::mem::{align_of, size_of, ManuallyDrop};
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::ptr;

use fft::Complex;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum AllocationSite {
    ParticleAssignments,
    ReciprocalWorkspace,
    ForceOutput,
    NeutralitySort,
}

impl AllocationSite {
    const fn detail(self) -> &'static str {
        match self {
            Self::ParticleAssignments => "particle assignment allocation failed",
            Self::ReciprocalWorkspace => {
                "particle-mesh spectrum, FFT line-scratch, and reciprocal axis-data allocation failed"
            }
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
    static INJECTED_REUSABLE_WORKSPACE_PANIC: Cell<bool> = const { Cell::new(false) };
}

#[cfg(test)]
struct LateNonFiniteResultGuard {
    previous: bool,
}

#[cfg(test)]
struct ReusableWorkspacePanicGuard {
    previous: bool,
}

#[cfg(test)]
impl ReusableWorkspacePanicGuard {
    fn inject() -> Self {
        let previous = INJECTED_REUSABLE_WORKSPACE_PANIC.with(|injected| {
            let previous = injected.get();
            injected.set(true);
            previous
        });
        Self { previous }
    }
}

#[cfg(test)]
impl Drop for ReusableWorkspacePanicGuard {
    fn drop(&mut self) {
        INJECTED_REUSABLE_WORKSPACE_PANIC.with(|injected| injected.set(self.previous));
    }
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

struct ReciprocalWorkspace {
    storage: Vec<Complex>,
}

impl ReciprocalWorkspace {
    fn new(validated: &ValidatedInput) -> Result<Self, AllocationFailure> {
        let mut workspace = Self {
            storage: Vec::new(),
        };
        workspace.prepare(validated)?;
        Ok(workspace)
    }

    fn prepare(&mut self, validated: &ValidatedInput) -> Result<(), AllocationFailure> {
        let axis_data_count = reciprocal_axis_data_count(validated.dimensions);
        let storage_count = validated
            .mesh_point_count
            .checked_add(axis_data_count)
            .expect("validated reciprocal workspace count fits usize");
        if storage_count > self.storage.capacity() {
            let additional = storage_count
                .checked_sub(self.storage.len())
                .expect("workspace growth exceeds its current length");
            fallible_reserve_exact(
                &mut self.storage,
                additional,
                AllocationSite::ReciprocalWorkspace,
            )?;
        }
        self.storage.resize(storage_count, Complex::default());
        self.storage.fill(Complex::default());
        Ok(())
    }
}

struct NeutralitySortScratch {
    storage: Vec<f64>,
}

impl NeutralitySortScratch {
    fn prepare(&mut self, values: &[f64]) -> Result<(), AllocationFailure> {
        if values.len() > self.storage.capacity() {
            let additional = values
                .len()
                .checked_sub(self.storage.len())
                .expect("neutrality scratch growth exceeds its current length");
            fallible_reserve_exact(
                &mut self.storage,
                additional,
                AllocationSite::NeutralitySort,
            )?;
        }
        self.storage.clear();
        self.storage.extend_from_slice(values);
        Ok(())
    }
}

struct ParticleAssignmentScratch {
    storage: Vec<ParticleAssignment>,
}

impl ParticleAssignmentScratch {
    fn prepare<I: ReciprocalInput + ?Sized>(
        &mut self,
        input: &I,
        validated: &ValidatedInput,
    ) -> Result<(), AllocationFailure> {
        let particle_count = input.particle_count();
        if particle_count > self.storage.capacity() {
            let additional = particle_count
                .checked_sub(self.storage.len())
                .expect("particle assignment scratch growth exceeds its current length");
            fallible_reserve_exact(
                &mut self.storage,
                additional,
                AllocationSite::ParticleAssignments,
            )?;
        }
        self.storage.clear();
        let cell = input.cell();
        self.storage.extend(
            (0..particle_count)
                .map(|particle| assignment(input.position(particle), cell, validated.dimensions)),
        );
        Ok(())
    }
}

fn reciprocal_axis_data_count(dimensions: [usize; 3]) -> usize {
    dimensions
        .into_iter()
        .try_fold(0_usize, usize::checked_add)
        .expect("validated reciprocal axis-data count fits usize")
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
    compute_with_transform_and_workspace(input, transform, force_mode, None)
}

fn compute_with_transform_and_workspace<I: ReciprocalInput + ?Sized>(
    input: &I,
    transform: Transform3d,
    force_mode: ForceStorageMode,
    reusable_workspace: Option<&mut ReciprocalWorkspace>,
) -> Result<InternalEvaluation, ParticleMeshReciprocalError> {
    compute_with_transform_and_reusable_storage(
        input,
        transform,
        force_mode,
        reusable_workspace,
        None,
        None,
    )
}

fn compute_with_transform_and_reusable_storage<I: ReciprocalInput + ?Sized>(
    input: &I,
    transform: Transform3d,
    force_mode: ForceStorageMode,
    reusable_workspace: Option<&mut ReciprocalWorkspace>,
    reusable_neutrality_sort_scratch: Option<&mut NeutralitySortScratch>,
    reusable_particle_assignment_scratch: Option<&mut ParticleAssignmentScratch>,
) -> Result<InternalEvaluation, ParticleMeshReciprocalError> {
    #[cfg(test)]
    let is_reusing_workspace = reusable_workspace.is_some();
    let validated = validate_with_neutrality_sort_scratch(input, reusable_neutrality_sort_scratch)?;
    let charges = input.charges_elementary();
    let cell = input.cell();
    let mut local_particle_assignment_scratch = ParticleAssignmentScratch {
        storage: Vec::new(),
    };
    let particle_assignment_scratch =
        reusable_particle_assignment_scratch.unwrap_or(&mut local_particle_assignment_scratch);
    particle_assignment_scratch
        .prepare(input, &validated)
        .map_err(ParticleMeshReciprocalError::from)?;
    let assignments = &particle_assignment_scratch.storage;
    let mut local_workspace = None;
    let reciprocal_workspace = if let Some(workspace) = reusable_workspace {
        workspace
            .prepare(&validated)
            .map_err(ParticleMeshReciprocalError::from)?;
        workspace
    } else {
        local_workspace.insert(
            ReciprocalWorkspace::new(&validated).map_err(ParticleMeshReciprocalError::from)?,
        )
    };
    #[cfg(test)]
    INJECTED_REUSABLE_WORKSPACE_PANIC.with(|injected| {
        if is_reusing_workspace && injected.get() {
            panic!("injected reusable reciprocal workspace panic");
        }
    });
    let line_count = validated.dimensions.into_iter().max().unwrap_or(0);
    let (spectrum, reciprocal_tail) = reciprocal_workspace
        .storage
        .split_at_mut(validated.mesh_point_count);
    debug_assert_eq!(
        reciprocal_tail.len(),
        reciprocal_axis_data_count(validated.dimensions)
    );
    debug_assert!(line_count <= reciprocal_tail.len());
    spread_charges(spectrum, validated.dimensions, assignments, charges);
    transform(
        spectrum,
        validated.dimensions,
        false,
        &mut reciprocal_tail[..line_count],
    );

    fill_reciprocal_axis_data(
        &mut *reciprocal_tail,
        validated.dimensions,
        cell.lengths_angstrom,
    );

    let reciprocal = apply_reciprocal_operator(input, &validated, spectrum, &*reciprocal_tail);
    let reciprocal_space_kcal_per_mol = reciprocal.energy;

    let (forces_kcal_per_mol_angstrom, all_forces_are_finite) = if matches!(
        force_mode,
        ForceStorageMode::Transactional | ForceStorageMode::Direct(_)
    ) {
        transform(
            spectrum,
            validated.dimensions,
            true,
            &mut reciprocal_tail[..line_count],
        );
        let scaled_grid_multiplier = reciprocal.grid_derivative_scale / RESCUE_SCALE;
        let (forces, all_forces_are_finite) = match force_mode {
            ForceStorageMode::Transactional => {
                let forces = gather_forces(
                    spectrum,
                    validated.dimensions,
                    assignments,
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
                        assignments,
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
    reciprocal_axis_data: &[Complex],
) -> ReciprocalOperator {
    let settings = input.settings();
    let alpha = settings.alpha_per_angstrom;
    let energy_prefactor = COULOMB_KCAL_ANGSTROM_PER_MOL_E2 / settings.dielectric
        * core::f64::consts::TAU
        / validated.volume_angstrom_cubed;
    let grid_derivative_scale =
        2.0 * energy_prefactor * bounded_usize_to_f64(validated.mesh_point_count);
    let [x_count, y_count, z_count] = validated.dimensions;
    debug_assert_eq!(
        reciprocal_axis_data.len(),
        reciprocal_axis_data_count(validated.dimensions)
    );
    let (x_axis_data, yz_axis_data) = reciprocal_axis_data.split_at(x_count);
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
                let wave_squared = dimension_data[0][x].real
                    + dimension_data[1][y].real
                    + dimension_data[2][z].real;
                let assignment_modulus = dimension_data[0][x].imaginary
                    * dimension_data[1][y].imaginary
                    * dimension_data[2][z].imaginary;
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
#[cfg(test)]
fn validate<I: ReciprocalInput + ?Sized>(
    input: &I,
) -> Result<ValidatedInput, ParticleMeshReciprocalError> {
    validate_with_neutrality_sort_scratch(input, None)
}

#[allow(clippy::too_many_lines)]
fn validate_with_neutrality_sort_scratch<I: ReciprocalInput + ?Sized>(
    input: &I,
    reusable_neutrality_sort_scratch: Option<&mut NeutralitySortScratch>,
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
        accurate_order_independent_sum_with_scratch(charges, reusable_neutrality_sort_scratch)
            .map_err(ParticleMeshReciprocalError::from)?;
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

// Owner-private callers may test spare-capacity aliasing by shrinking only the
// logical byte count before the next prepare overwrites every element. This is
// sound only while assignment elements have no drop glue.
const _: () = assert!(!std::mem::needs_drop::<ParticleAssignment>());
const _: () = assert!(size_of::<ParticleAssignment>() != 0);

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

fn fill_reciprocal_axis_data(
    storage: &mut [Complex],
    dimensions: [usize; 3],
    cell_lengths: [f64; 3],
) {
    debug_assert_eq!(storage.len(), reciprocal_axis_data_count(dimensions));
    let mut storage_index = 0;
    for axis in 0..3 {
        let dimension = dimensions[axis];
        let cell_length = cell_lengths[axis];
        for index in 0..dimension {
            let signed_index = signed_mesh_index(index, dimension);
            let wave = core::f64::consts::TAU * f64::from(signed_index) / cell_length;
            let angle =
                core::f64::consts::TAU * f64::from(signed_index) / bounded_usize_to_f64(dimension);
            storage[storage_index] = Complex::new(wave * wave, (2.0 + libm::cos(angle)) / 3.0);
            storage_index += 1;
        }
    }
    debug_assert_eq!(storage_index, storage.len());
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

fn accurate_order_independent_sum_with_scratch(
    values: &[f64],
    reusable_scratch: Option<&mut NeutralitySortScratch>,
) -> Result<f64, AllocationFailure> {
    let mut local_scratch = NeutralitySortScratch {
        storage: Vec::new(),
    };
    let scratch = reusable_scratch.unwrap_or(&mut local_scratch);
    scratch.prepare(values)?;
    scratch.storage.sort_unstable_by(|left, right| {
        left.abs()
            .total_cmp(&right.abs())
            .then_with(|| left.total_cmp(right))
    });
    let mut sum = CompensatedSum::default();
    for value in scratch.storage.iter().copied() {
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
const PARTICLE_MESH_RECIPROCAL_WORKSPACE_EMPTY: u32 = 0;
const PARTICLE_MESH_RECIPROCAL_WORKSPACE_READY: u32 = 0x5257_5331;
const PARTICLE_MESH_RECIPROCAL_WORKSPACE_LEASED: u32 = 0x4c45_5331;
const PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_EMPTY: u32 = 0;
const PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_READY: u32 = 0x4e53_5331;
const PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_LEASED: u32 = 0x4e53_4c31;
const PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_EMPTY: u32 = 0;
const PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_READY: u32 = 0x5041_5331;
const PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_LEASED: u32 = 0x5041_4c31;
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
pub(crate) struct ParticleMeshReciprocalWorkspaceV1 {
    struct_size: u32,
    abi_version: u32,
    state: u32,
    reserved0: u32,
    storage: *mut c_void,
    length: usize,
    capacity: usize,
    reserved: [u64; 4],
}

#[repr(C)]
#[derive(Clone, Copy)]
pub(crate) struct ParticleMeshReciprocalNeutralitySortScratchV1 {
    struct_size: u32,
    abi_version: u32,
    state: u32,
    reserved0: u32,
    storage: *mut c_void,
    length: usize,
    capacity: usize,
    reserved: [u64; 4],
}

#[repr(C)]
#[derive(Clone, Copy)]
pub(crate) struct ParticleMeshReciprocalParticleAssignmentScratchV1 {
    struct_size: u32,
    abi_version: u32,
    state: u32,
    reserved0: u32,
    storage: *mut c_void,
    logical_length_bytes: usize,
    allocation_capacity_bytes: usize,
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
enum WorkspaceSnapshot {
    Empty,
    Ready {
        storage: *mut Complex,
        length: usize,
        capacity: usize,
    },
    Leased,
}

#[derive(Clone, Copy)]
struct WorkspacePreflight {
    pointer: *mut ParticleMeshReciprocalWorkspaceV1,
    snapshot: WorkspaceSnapshot,
    descriptor_range: MemoryRange,
    backing_range: Option<MemoryRange>,
}

struct ReciprocalWorkspaceLease {
    descriptor: *mut ParticleMeshReciprocalWorkspaceV1,
    restore_empty_if_unallocated: bool,
    workspace: Option<ReciprocalWorkspace>,
}

impl ReciprocalWorkspaceLease {
    unsafe fn acquire(preflight: WorkspacePreflight) -> Self {
        let (workspace, restore_empty_if_unallocated) = match preflight.snapshot {
            WorkspaceSnapshot::Empty => (
                ReciprocalWorkspace {
                    storage: Vec::new(),
                },
                true,
            ),
            WorkspaceSnapshot::Ready {
                storage,
                length,
                capacity,
            } => {
                let values = if capacity == 0 {
                    Vec::new()
                } else {
                    // SAFETY: The canonical READY descriptor owns exactly this
                    // Rust Vec allocation, and preflight proved alignment,
                    // length/capacity ordering, and addressable capacity. The
                    // owner-private ABI excludes concurrent access.
                    unsafe { Vec::from_raw_parts(storage, length, capacity) }
                };
                (ReciprocalWorkspace { storage: values }, false)
            }
            WorkspaceSnapshot::Leased => {
                unreachable!("leased reciprocal workspace cannot be acquired")
            }
        };
        let storage = workspace.storage.as_ptr().cast_mut();
        let length = workspace.storage.len();
        let capacity = workspace.storage.capacity();
        let external_storage = if capacity == 0 {
            ptr::null_mut()
        } else {
            storage.cast::<c_void>()
        };
        // SAFETY: The descriptor is initialized, writable, and disjoint from
        // every caller descriptor/channel and from its backing allocation.
        unsafe {
            ptr::write(
                preflight.pointer,
                canonical_workspace_descriptor(
                    PARTICLE_MESH_RECIPROCAL_WORKSPACE_LEASED,
                    external_storage,
                    length,
                    capacity,
                ),
            )
        };
        Self {
            descriptor: preflight.pointer,
            restore_empty_if_unallocated,
            workspace: Some(workspace),
        }
    }

    fn workspace_mut(&mut self) -> &mut ReciprocalWorkspace {
        self.workspace
            .as_mut()
            .expect("live reciprocal workspace lease owns storage")
    }
}

impl Drop for ReciprocalWorkspaceLease {
    fn drop(&mut self) {
        let workspace = self
            .workspace
            .take()
            .expect("reciprocal workspace lease restores exactly once");
        let mut storage = ManuallyDrop::new(workspace.storage);
        let length = storage.len();
        let capacity = storage.capacity();
        if self.restore_empty_if_unallocated && capacity == 0 {
            // SAFETY: The lease exclusively owns the descriptor and no backing
            // allocation exists. Restoring all-zero preserves cold-failure
            // retention and remains accepted by the next call or destroy.
            unsafe { ptr::write(self.descriptor, empty_workspace_descriptor()) };
            return;
        }
        let pointer = if capacity == 0 {
            ptr::null_mut()
        } else {
            storage.as_mut_ptr().cast::<c_void>()
        };
        // SAFETY: The ManuallyDrop transfers the Vec raw parts back to the
        // canonical READY descriptor, which remains owner-private and live.
        unsafe {
            ptr::write(
                self.descriptor,
                canonical_workspace_descriptor(
                    PARTICLE_MESH_RECIPROCAL_WORKSPACE_READY,
                    pointer,
                    length,
                    capacity,
                ),
            )
        };
    }
}

#[derive(Clone, Copy)]
enum NeutralitySortScratchSnapshot {
    Empty,
    Ready {
        storage: *mut f64,
        length: usize,
        capacity: usize,
    },
    Leased,
}

#[derive(Clone, Copy)]
struct NeutralitySortScratchPreflight {
    pointer: *mut ParticleMeshReciprocalNeutralitySortScratchV1,
    snapshot: NeutralitySortScratchSnapshot,
    descriptor_range: MemoryRange,
    backing_range: Option<MemoryRange>,
}

struct NeutralitySortScratchLease {
    descriptor: *mut ParticleMeshReciprocalNeutralitySortScratchV1,
    restore_empty_if_unallocated: bool,
    scratch: Option<NeutralitySortScratch>,
}

impl NeutralitySortScratchLease {
    unsafe fn acquire(preflight: NeutralitySortScratchPreflight) -> Self {
        let (scratch, restore_empty_if_unallocated) = match preflight.snapshot {
            NeutralitySortScratchSnapshot::Empty => (
                NeutralitySortScratch {
                    storage: Vec::new(),
                },
                true,
            ),
            NeutralitySortScratchSnapshot::Ready {
                storage,
                length,
                capacity,
            } => {
                let values = if capacity == 0 {
                    Vec::new()
                } else {
                    // SAFETY: The canonical READY descriptor owns exactly this
                    // Rust Vec allocation, and preflight proved alignment,
                    // length/capacity ordering, and addressable capacity. The
                    // owner-private ABI excludes concurrent access.
                    unsafe { Vec::from_raw_parts(storage, length, capacity) }
                };
                (NeutralitySortScratch { storage: values }, false)
            }
            NeutralitySortScratchSnapshot::Leased => {
                unreachable!("leased neutrality sort scratch cannot be acquired")
            }
        };
        let storage = scratch.storage.as_ptr().cast_mut();
        let length = scratch.storage.len();
        let capacity = scratch.storage.capacity();
        let external_storage = if capacity == 0 {
            ptr::null_mut()
        } else {
            storage.cast::<c_void>()
        };
        // SAFETY: The descriptor is initialized, writable, and disjoint from
        // every caller descriptor/channel and from both retained allocations.
        unsafe {
            ptr::write(
                preflight.pointer,
                canonical_neutrality_sort_scratch_descriptor(
                    PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_LEASED,
                    external_storage,
                    length,
                    capacity,
                ),
            )
        };
        Self {
            descriptor: preflight.pointer,
            restore_empty_if_unallocated,
            scratch: Some(scratch),
        }
    }

    fn scratch_mut(&mut self) -> &mut NeutralitySortScratch {
        self.scratch
            .as_mut()
            .expect("live neutrality sort scratch lease owns storage")
    }
}

impl Drop for NeutralitySortScratchLease {
    fn drop(&mut self) {
        let scratch = self
            .scratch
            .take()
            .expect("neutrality sort scratch lease restores exactly once");
        let mut storage = ManuallyDrop::new(scratch.storage);
        let length = storage.len();
        let capacity = storage.capacity();
        if self.restore_empty_if_unallocated && capacity == 0 {
            // SAFETY: No allocation exists and the lease exclusively owns the
            // descriptor. Restoring all-zero preserves cold-failure retention.
            unsafe { ptr::write(self.descriptor, empty_neutrality_sort_scratch_descriptor()) };
            return;
        }
        let pointer = if capacity == 0 {
            ptr::null_mut()
        } else {
            storage.as_mut_ptr().cast::<c_void>()
        };
        // SAFETY: The ManuallyDrop transfers the Vec raw parts back to the
        // canonical READY descriptor, which remains owner-private and live.
        unsafe {
            ptr::write(
                self.descriptor,
                canonical_neutrality_sort_scratch_descriptor(
                    PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_READY,
                    pointer,
                    length,
                    capacity,
                ),
            )
        };
    }
}

#[derive(Clone, Copy)]
enum ParticleAssignmentScratchSnapshot {
    Empty,
    Ready {
        storage: *mut c_void,
        logical_length_bytes: usize,
        allocation_capacity_bytes: usize,
    },
    Leased,
}

#[derive(Clone, Copy)]
struct ParticleAssignmentScratchPreflight {
    pointer: *mut ParticleMeshReciprocalParticleAssignmentScratchV1,
    snapshot: ParticleAssignmentScratchSnapshot,
    descriptor_range: MemoryRange,
    backing_range: Option<MemoryRange>,
}

struct ParticleAssignmentScratchLease {
    descriptor: *mut ParticleMeshReciprocalParticleAssignmentScratchV1,
    restore_empty_if_unallocated: bool,
    scratch: Option<ParticleAssignmentScratch>,
}

impl ParticleAssignmentScratchLease {
    unsafe fn acquire(preflight: ParticleAssignmentScratchPreflight) -> Self {
        let (scratch, restore_empty_if_unallocated) = match preflight.snapshot {
            ParticleAssignmentScratchSnapshot::Empty => (
                ParticleAssignmentScratch {
                    storage: Vec::new(),
                },
                true,
            ),
            ParticleAssignmentScratchSnapshot::Ready {
                storage,
                logical_length_bytes,
                allocation_capacity_bytes,
            } => {
                // Conversion from the opaque byte-count descriptor deliberately
                // occurs only after complete descriptor/backing alias preflight.
                let element_size = size_of::<ParticleAssignment>();
                let length = logical_length_bytes / element_size;
                let capacity = allocation_capacity_bytes / element_size;
                let values = if capacity == 0 {
                    Vec::new()
                } else {
                    // SAFETY: The canonical READY descriptor owns exactly this
                    // Rust Vec allocation. Preflight proved whole-element byte
                    // counts, alignment, ordering, addressability, and complete
                    // alias disjointness before this conversion and lease.
                    unsafe {
                        Vec::from_raw_parts(storage.cast::<ParticleAssignment>(), length, capacity)
                    }
                };
                (ParticleAssignmentScratch { storage: values }, false)
            }
            ParticleAssignmentScratchSnapshot::Leased => {
                unreachable!("leased particle assignment scratch cannot be acquired")
            }
        };
        let storage = scratch.storage.as_ptr().cast_mut();
        let length = scratch.storage.len();
        let capacity = scratch.storage.capacity();
        let external_storage = if capacity == 0 {
            ptr::null_mut()
        } else {
            storage.cast::<c_void>()
        };
        // SAFETY: The descriptor is initialized, writable, and disjoint from
        // every caller descriptor/channel and all three retained allocations.
        unsafe {
            ptr::write(
                preflight.pointer,
                canonical_particle_assignment_scratch_descriptor(
                    PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_LEASED,
                    external_storage,
                    length,
                    capacity,
                ),
            )
        };
        Self {
            descriptor: preflight.pointer,
            restore_empty_if_unallocated,
            scratch: Some(scratch),
        }
    }

    fn scratch_mut(&mut self) -> &mut ParticleAssignmentScratch {
        self.scratch
            .as_mut()
            .expect("live particle assignment scratch lease owns storage")
    }
}

impl Drop for ParticleAssignmentScratchLease {
    fn drop(&mut self) {
        let scratch = self
            .scratch
            .take()
            .expect("particle assignment scratch lease restores exactly once");
        let mut storage = ManuallyDrop::new(scratch.storage);
        let length = storage.len();
        let capacity = storage.capacity();
        if self.restore_empty_if_unallocated && capacity == 0 {
            // SAFETY: No allocation exists and the lease exclusively owns the
            // descriptor. Restoring all-zero preserves cold-failure retention.
            unsafe {
                ptr::write(
                    self.descriptor,
                    empty_particle_assignment_scratch_descriptor(),
                )
            };
            return;
        }
        let pointer = if capacity == 0 {
            ptr::null_mut()
        } else {
            storage.as_mut_ptr().cast::<c_void>()
        };
        // SAFETY: ManuallyDrop transfers the Vec raw parts back to the canonical
        // owner-private READY descriptor without exposing its element layout.
        unsafe {
            ptr::write(
                self.descriptor,
                canonical_particle_assignment_scratch_descriptor(
                    PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_READY,
                    pointer,
                    length,
                    capacity,
                ),
            )
        };
    }
}

const fn empty_workspace_descriptor() -> ParticleMeshReciprocalWorkspaceV1 {
    ParticleMeshReciprocalWorkspaceV1 {
        struct_size: 0,
        abi_version: 0,
        state: PARTICLE_MESH_RECIPROCAL_WORKSPACE_EMPTY,
        reserved0: 0,
        storage: ptr::null_mut(),
        length: 0,
        capacity: 0,
        reserved: [0; 4],
    }
}

fn canonical_workspace_descriptor(
    state: u32,
    storage: *mut c_void,
    length: usize,
    capacity: usize,
) -> ParticleMeshReciprocalWorkspaceV1 {
    ParticleMeshReciprocalWorkspaceV1 {
        struct_size: u32::try_from(size_of::<ParticleMeshReciprocalWorkspaceV1>()).unwrap_or(0),
        abi_version: PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION,
        state,
        reserved0: 0,
        storage,
        length,
        capacity,
        reserved: [0; 4],
    }
}

const fn empty_neutrality_sort_scratch_descriptor() -> ParticleMeshReciprocalNeutralitySortScratchV1
{
    ParticleMeshReciprocalNeutralitySortScratchV1 {
        struct_size: 0,
        abi_version: 0,
        state: PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_EMPTY,
        reserved0: 0,
        storage: ptr::null_mut(),
        length: 0,
        capacity: 0,
        reserved: [0; 4],
    }
}

fn canonical_neutrality_sort_scratch_descriptor(
    state: u32,
    storage: *mut c_void,
    length: usize,
    capacity: usize,
) -> ParticleMeshReciprocalNeutralitySortScratchV1 {
    ParticleMeshReciprocalNeutralitySortScratchV1 {
        struct_size: u32::try_from(size_of::<ParticleMeshReciprocalNeutralitySortScratchV1>())
            .unwrap_or(0),
        abi_version: PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION,
        state,
        reserved0: 0,
        storage,
        length,
        capacity,
        reserved: [0; 4],
    }
}

const fn empty_particle_assignment_scratch_descriptor(
) -> ParticleMeshReciprocalParticleAssignmentScratchV1 {
    ParticleMeshReciprocalParticleAssignmentScratchV1 {
        struct_size: 0,
        abi_version: 0,
        state: PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_EMPTY,
        reserved0: 0,
        storage: ptr::null_mut(),
        logical_length_bytes: 0,
        allocation_capacity_bytes: 0,
        reserved: [0; 4],
    }
}

fn canonical_particle_assignment_scratch_descriptor(
    state: u32,
    storage: *mut c_void,
    length: usize,
    capacity: usize,
) -> ParticleMeshReciprocalParticleAssignmentScratchV1 {
    let element_size = size_of::<ParticleAssignment>();
    ParticleMeshReciprocalParticleAssignmentScratchV1 {
        struct_size: u32::try_from(size_of::<ParticleMeshReciprocalParticleAssignmentScratchV1>())
            .unwrap_or(0),
        abi_version: PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION,
        state,
        reserved0: 0,
        storage,
        logical_length_bytes: length
            .checked_mul(element_size)
            .expect("validated assignment scratch length fits bytes"),
        allocation_capacity_bytes: capacity
            .checked_mul(element_size)
            .expect("validated assignment scratch capacity fits bytes"),
        reserved: [0; 4],
    }
}

#[derive(Clone, Copy)]
enum ProviderForceMode {
    Transactional(u8),
    Direct {
        workspace: Option<*mut ParticleMeshReciprocalWorkspaceV1>,
        neutrality_sort_scratch: Option<*mut ParticleMeshReciprocalNeutralitySortScratchV1>,
        particle_assignment_scratch: Option<*mut ParticleMeshReciprocalParticleAssignmentScratchV1>,
    },
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

fn workspace_descriptor_is_empty(workspace: ParticleMeshReciprocalWorkspaceV1) -> bool {
    workspace.struct_size == 0
        && workspace.abi_version == 0
        && workspace.state == PARTICLE_MESH_RECIPROCAL_WORKSPACE_EMPTY
        && workspace.reserved0 == 0
        && workspace.storage.is_null()
        && workspace.length == 0
        && workspace.capacity == 0
        && reserved_is_zero(&workspace.reserved)
}

unsafe fn preflight_workspace_descriptor(
    pointer: *mut ParticleMeshReciprocalWorkspaceV1,
    descriptor_range: MemoryRange,
) -> Result<WorkspacePreflight, ProviderFailure> {
    // SAFETY: The caller checked this fixed-size descriptor for non-nullness,
    // natural alignment, addressability, and disjointness from error storage.
    let workspace = unsafe { ptr::read(pointer) };
    if workspace_descriptor_is_empty(workspace) {
        return Ok(WorkspacePreflight {
            pointer,
            snapshot: WorkspaceSnapshot::Empty,
            descriptor_range,
            backing_range: None,
        });
    }
    validate_header::<ParticleMeshReciprocalWorkspaceV1>(
        workspace.struct_size,
        workspace.abi_version,
        &workspace.reserved,
        "reciprocal workspace",
    )?;
    if workspace.reserved0 != 0 {
        return Err(ProviderFailure::abi(
            "reciprocal workspace reserved0 must be zero",
        ));
    }
    if !matches!(
        workspace.state,
        PARTICLE_MESH_RECIPROCAL_WORKSPACE_READY | PARTICLE_MESH_RECIPROCAL_WORKSPACE_LEASED
    ) {
        return Err(ProviderFailure::abi(
            "reciprocal workspace state is not canonical",
        ));
    }
    if workspace.length > workspace.capacity {
        return Err(ProviderFailure::capacity(
            "reciprocal workspace length exceeds capacity",
        ));
    }
    let backing_range = if workspace.capacity == 0 {
        if !workspace.storage.is_null() || workspace.length != 0 {
            return Err(ProviderFailure::abi(
                "empty reciprocal workspace raw parts are not canonical",
            ));
        }
        None
    } else {
        if workspace.storage.is_null() {
            return Err(ProviderFailure::invalid(
                "reciprocal workspace storage is null",
            ));
        }
        checked_range(
            workspace.storage.cast::<Complex>().cast_const(),
            workspace.capacity,
            "reciprocal workspace storage is null",
        )?
    };
    let snapshot = if workspace.state == PARTICLE_MESH_RECIPROCAL_WORKSPACE_READY {
        WorkspaceSnapshot::Ready {
            storage: workspace.storage.cast::<Complex>(),
            length: workspace.length,
            capacity: workspace.capacity,
        }
    } else {
        WorkspaceSnapshot::Leased
    };
    Ok(WorkspacePreflight {
        pointer,
        snapshot,
        descriptor_range,
        backing_range,
    })
}

fn neutrality_sort_scratch_descriptor_is_empty(
    scratch: ParticleMeshReciprocalNeutralitySortScratchV1,
) -> bool {
    scratch.struct_size == 0
        && scratch.abi_version == 0
        && scratch.state == PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_EMPTY
        && scratch.reserved0 == 0
        && scratch.storage.is_null()
        && scratch.length == 0
        && scratch.capacity == 0
        && reserved_is_zero(&scratch.reserved)
}

unsafe fn preflight_neutrality_sort_scratch_descriptor(
    pointer: *mut ParticleMeshReciprocalNeutralitySortScratchV1,
    descriptor_range: MemoryRange,
) -> Result<NeutralitySortScratchPreflight, ProviderFailure> {
    // SAFETY: The caller checked this fixed-size descriptor for non-nullness,
    // natural alignment, addressability, and disjointness from error storage.
    let scratch = unsafe { ptr::read(pointer) };
    if neutrality_sort_scratch_descriptor_is_empty(scratch) {
        return Ok(NeutralitySortScratchPreflight {
            pointer,
            snapshot: NeutralitySortScratchSnapshot::Empty,
            descriptor_range,
            backing_range: None,
        });
    }
    validate_header::<ParticleMeshReciprocalNeutralitySortScratchV1>(
        scratch.struct_size,
        scratch.abi_version,
        &scratch.reserved,
        "neutrality sort scratch",
    )?;
    if scratch.reserved0 != 0 {
        return Err(ProviderFailure::abi(
            "neutrality sort scratch reserved0 must be zero",
        ));
    }
    if !matches!(
        scratch.state,
        PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_READY
            | PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_LEASED
    ) {
        return Err(ProviderFailure::abi(
            "neutrality sort scratch state is not canonical",
        ));
    }
    if scratch.length > scratch.capacity {
        return Err(ProviderFailure::capacity(
            "neutrality sort scratch length exceeds capacity",
        ));
    }
    let backing_range = if scratch.capacity == 0 {
        if !scratch.storage.is_null() || scratch.length != 0 {
            return Err(ProviderFailure::abi(
                "empty neutrality sort scratch raw parts are not canonical",
            ));
        }
        None
    } else {
        if scratch.storage.is_null() {
            return Err(ProviderFailure::invalid(
                "neutrality sort scratch storage is null",
            ));
        }
        checked_range(
            scratch.storage.cast::<f64>().cast_const(),
            scratch.capacity,
            "neutrality sort scratch storage is null",
        )?
    };
    let snapshot = if scratch.state == PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_READY {
        NeutralitySortScratchSnapshot::Ready {
            storage: scratch.storage.cast::<f64>(),
            length: scratch.length,
            capacity: scratch.capacity,
        }
    } else {
        NeutralitySortScratchSnapshot::Leased
    };
    Ok(NeutralitySortScratchPreflight {
        pointer,
        snapshot,
        descriptor_range,
        backing_range,
    })
}

fn particle_assignment_scratch_descriptor_is_empty(
    scratch: ParticleMeshReciprocalParticleAssignmentScratchV1,
) -> bool {
    scratch.struct_size == 0
        && scratch.abi_version == 0
        && scratch.state == PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_EMPTY
        && scratch.reserved0 == 0
        && scratch.storage.is_null()
        && scratch.logical_length_bytes == 0
        && scratch.allocation_capacity_bytes == 0
        && reserved_is_zero(&scratch.reserved)
}

unsafe fn preflight_particle_assignment_scratch_descriptor(
    pointer: *mut ParticleMeshReciprocalParticleAssignmentScratchV1,
    descriptor_range: MemoryRange,
) -> Result<ParticleAssignmentScratchPreflight, ProviderFailure> {
    // SAFETY: The caller checked this fixed-size descriptor for non-nullness,
    // natural alignment, addressability, and disjointness from error storage.
    let scratch = unsafe { ptr::read(pointer) };
    if particle_assignment_scratch_descriptor_is_empty(scratch) {
        return Ok(ParticleAssignmentScratchPreflight {
            pointer,
            snapshot: ParticleAssignmentScratchSnapshot::Empty,
            descriptor_range,
            backing_range: None,
        });
    }
    validate_header::<ParticleMeshReciprocalParticleAssignmentScratchV1>(
        scratch.struct_size,
        scratch.abi_version,
        &scratch.reserved,
        "particle assignment scratch",
    )?;
    if scratch.reserved0 != 0 {
        return Err(ProviderFailure::abi(
            "particle assignment scratch reserved0 must be zero",
        ));
    }
    if !matches!(
        scratch.state,
        PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_READY
            | PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_LEASED
    ) {
        return Err(ProviderFailure::abi(
            "particle assignment scratch state is not canonical",
        ));
    }
    if scratch.logical_length_bytes > scratch.allocation_capacity_bytes {
        return Err(ProviderFailure::capacity(
            "particle assignment scratch logical length exceeds allocation capacity",
        ));
    }
    let element_size = size_of::<ParticleAssignment>();
    if scratch.logical_length_bytes % element_size != 0
        || scratch.allocation_capacity_bytes % element_size != 0
    {
        return Err(ProviderFailure::abi(
            "particle assignment scratch byte counts are not whole elements",
        ));
    }
    let backing_range = if scratch.allocation_capacity_bytes == 0 {
        if !scratch.storage.is_null() || scratch.logical_length_bytes != 0 {
            return Err(ProviderFailure::abi(
                "empty particle assignment scratch raw parts are not canonical",
            ));
        }
        None
    } else {
        if scratch.storage.is_null() {
            return Err(ProviderFailure::invalid(
                "particle assignment scratch storage is null",
            ));
        }
        if (scratch.storage as usize) % align_of::<ParticleAssignment>() != 0 {
            return Err(ProviderFailure::invalid(
                "particle assignment scratch storage is not naturally aligned",
            ));
        }
        checked_range(
            scratch.storage.cast::<u8>().cast_const(),
            scratch.allocation_capacity_bytes,
            "particle assignment scratch storage is null",
        )?
    };
    let snapshot = if scratch.state == PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_READY {
        ParticleAssignmentScratchSnapshot::Ready {
            storage: scratch.storage,
            logical_length_bytes: scratch.logical_length_bytes,
            allocation_capacity_bytes: scratch.allocation_capacity_bytes,
        }
    } else {
        ParticleAssignmentScratchSnapshot::Leased
    };
    Ok(ParticleAssignmentScratchPreflight {
        pointer,
        snapshot,
        descriptor_range,
        backing_range,
    })
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

fn evaluate_with_direct_force_output_and_workspace<I: ReciprocalInput + ?Sized>(
    input: &I,
    output: ParticleMeshReciprocalForceOutputV1,
    workspace: &mut ReciprocalWorkspace,
) -> Result<f64, ParticleMeshReciprocalError> {
    Ok(compute_with_transform_and_workspace(
        input,
        fft::fft_3d,
        ForceStorageMode::Direct(output),
        Some(workspace),
    )?
    .evaluation
    .reciprocal_space_kcal_per_mol)
}

fn evaluate_with_direct_force_output_and_reusable_storage<I: ReciprocalInput + ?Sized>(
    input: &I,
    output: ParticleMeshReciprocalForceOutputV1,
    workspace: &mut ReciprocalWorkspace,
    neutrality_sort_scratch: &mut NeutralitySortScratch,
) -> Result<f64, ParticleMeshReciprocalError> {
    Ok(compute_with_transform_and_reusable_storage(
        input,
        fft::fft_3d,
        ForceStorageMode::Direct(output),
        Some(workspace),
        Some(neutrality_sort_scratch),
        None,
    )?
    .evaluation
    .reciprocal_space_kcal_per_mol)
}

fn evaluate_with_direct_force_output_and_all_reusable_storage<I: ReciprocalInput + ?Sized>(
    input: &I,
    output: ParticleMeshReciprocalForceOutputV1,
    workspace: &mut ReciprocalWorkspace,
    neutrality_sort_scratch: &mut NeutralitySortScratch,
    particle_assignment_scratch: &mut ParticleAssignmentScratch,
) -> Result<f64, ParticleMeshReciprocalError> {
    Ok(compute_with_transform_and_reusable_storage(
        input,
        fft::fft_3d,
        ForceStorageMode::Direct(output),
        Some(workspace),
        Some(neutrality_sort_scratch),
        Some(particle_assignment_scratch),
    )?
    .evaluation
    .reciprocal_space_kcal_per_mol)
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
    let (workspace_pointer, neutrality_sort_scratch_pointer, particle_assignment_scratch_pointer) =
        match force_mode {
            ProviderForceMode::Transactional(_) => (None, None, None),
            ProviderForceMode::Direct {
                workspace,
                neutrality_sort_scratch,
                particle_assignment_scratch,
            } => (
                workspace,
                neutrality_sort_scratch,
                particle_assignment_scratch,
            ),
        };
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
    let workspace_descriptor_range = if let Some(pointer) = workspace_pointer {
        Some(
            checked_range(
                pointer.cast_const(),
                1,
                "reciprocal workspace descriptor is null",
            )
            .map_err(ProviderFailure::without_error_write)?
            .ok_or_else(|| {
                ProviderFailure::invalid("reciprocal workspace descriptor is null")
                    .without_error_write()
            })?,
        )
    } else {
        None
    };
    let neutrality_sort_scratch_descriptor_range =
        if let Some(pointer) = neutrality_sort_scratch_pointer {
            Some(
                checked_range(
                    pointer.cast_const(),
                    1,
                    "neutrality sort scratch descriptor is null",
                )
                .map_err(ProviderFailure::without_error_write)?
                .ok_or_else(|| {
                    ProviderFailure::invalid("neutrality sort scratch descriptor is null")
                        .without_error_write()
                })?,
            )
        } else {
            None
        };
    let particle_assignment_scratch_descriptor_range =
        if let Some(pointer) = particle_assignment_scratch_pointer {
            Some(
                checked_range(
                    pointer.cast_const(),
                    1,
                    "particle assignment scratch descriptor is null",
                )
                .map_err(ProviderFailure::without_error_write)?
                .ok_or_else(|| {
                    ProviderFailure::invalid("particle assignment scratch descriptor is null")
                        .without_error_write()
                })?,
            )
        } else {
            None
        };
    let descriptor_ranges = [
        Some(system_range),
        Some(model_range),
        Some(energy_range),
        force_descriptor_range,
        workspace_descriptor_range,
        neutrality_sort_scratch_descriptor_range,
        particle_assignment_scratch_descriptor_range,
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
    let workspace_preflight = if let Some(descriptor_range) = workspace_descriptor_range {
        // SAFETY: The workspace descriptor has a valid fixed-size range and is
        // disjoint from writable error storage. Raw backing is only described,
        // not borrowed, during this preflight.
        let pointer = workspace_pointer.expect("workspace range requires a pointer mode");
        let preflight = unsafe { preflight_workspace_descriptor(pointer, descriptor_range) }
            .map_err(ProviderFailure::without_error_write)?;
        if preflight
            .backing_range
            .is_some_and(|range| ranges_overlap(error_range, range))
        {
            return Err(ProviderFailure::invalid(
                "error output must not overlap reciprocal workspace storage",
            )
            .without_error_write());
        }
        Some(preflight)
    } else {
        None
    };
    let neutrality_sort_scratch_preflight =
        if let Some(descriptor_range) = neutrality_sort_scratch_descriptor_range {
            // SAFETY: The scratch descriptor has a valid fixed-size range and
            // is disjoint from writable error storage. Raw backing is only
            // described, not borrowed, during this preflight.
            let pointer = neutrality_sort_scratch_pointer
                .expect("neutrality sort scratch range requires a pointer mode");
            let preflight =
                unsafe { preflight_neutrality_sort_scratch_descriptor(pointer, descriptor_range) }
                    .map_err(ProviderFailure::without_error_write)?;
            if preflight
                .backing_range
                .is_some_and(|range| ranges_overlap(error_range, range))
            {
                return Err(ProviderFailure::invalid(
                    "error output must not overlap neutrality sort scratch storage",
                )
                .without_error_write());
            }
            Some(preflight)
        } else {
            None
        };
    let particle_assignment_scratch_preflight = if let Some(descriptor_range) =
        particle_assignment_scratch_descriptor_range
    {
        // SAFETY: The assignment descriptor has a valid fixed-size range
        // and is disjoint from writable error storage. Opaque byte counts
        // describe backing only; they are not converted to elements here.
        let pointer = particle_assignment_scratch_pointer
            .expect("particle assignment scratch range requires a pointer mode");
        let preflight =
            unsafe { preflight_particle_assignment_scratch_descriptor(pointer, descriptor_range) }
                .map_err(ProviderFailure::without_error_write)?;
        if preflight
            .backing_range
            .is_some_and(|range| ranges_overlap(error_range, range))
        {
            return Err(ProviderFailure::invalid(
                "error output must not overlap particle assignment scratch storage",
            )
            .without_error_write());
        }
        Some(preflight)
    } else {
        None
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
    if workspace_preflight.is_none()
        && neutrality_sort_scratch_preflight.is_none()
        && particle_assignment_scratch_preflight.is_none()
    {
        // Preserve the established stateless panic/error-write boundary. The
        // persistent entry delays this marker until its descriptor and entire
        // backing capacity complete the stronger alias preflight below.
        alias_safety.set(true);
    }

    let compute_forces = match force_mode {
        ProviderForceMode::Transactional(compute_forces) if matches!(compute_forces, 0 | 1) => {
            compute_forces
        }
        ProviderForceMode::Transactional(_) => {
            return Err(ProviderFailure::invalid(
                "compute_forces must be exactly zero or one",
            ));
        }
        ProviderForceMode::Direct { .. } => 1,
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
        workspace_preflight.map(|workspace| workspace.descriptor_range),
        workspace_preflight.and_then(|workspace| workspace.backing_range),
        neutrality_sort_scratch_preflight.map(|scratch| scratch.descriptor_range),
        neutrality_sort_scratch_preflight.and_then(|scratch| scratch.backing_range),
        particle_assignment_scratch_preflight.map(|scratch| scratch.descriptor_range),
        particle_assignment_scratch_preflight.and_then(|scratch| scratch.backing_range),
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

    if workspace_preflight.is_some()
        || neutrality_sort_scratch_preflight.is_some()
        || particle_assignment_scratch_preflight.is_some()
    {
        alias_safety.set(true);
    }
    if workspace_preflight
        .is_some_and(|preflight| matches!(preflight.snapshot, WorkspaceSnapshot::Leased))
    {
        return Err(ProviderFailure::invalid(
            "reciprocal workspace is already leased",
        ));
    }
    if neutrality_sort_scratch_preflight.is_some_and(|preflight| {
        matches!(preflight.snapshot, NeutralitySortScratchSnapshot::Leased)
    }) {
        return Err(ProviderFailure::invalid(
            "neutrality sort scratch is already leased",
        ));
    }
    if particle_assignment_scratch_preflight.is_some_and(|preflight| {
        matches!(
            preflight.snapshot,
            ParticleAssignmentScratchSnapshot::Leased
        )
    }) {
        return Err(ProviderFailure::invalid(
            "particle assignment scratch is already leased",
        ));
    }

    let mut workspace_lease = workspace_preflight.map(|preflight| {
        // SAFETY: Header/raw-parts validation and complete descriptor, backing,
        // error, input, and force alias preflight all finished above.
        unsafe { ReciprocalWorkspaceLease::acquire(preflight) }
    });
    let mut neutrality_sort_scratch_lease = neutrality_sort_scratch_preflight.map(|preflight| {
        // SAFETY: Header/raw-parts validation and complete two-descriptor,
        // two-backing, error, input, and force alias preflight finished.
        unsafe { NeutralitySortScratchLease::acquire(preflight) }
    });
    let mut particle_assignment_scratch_lease =
        particle_assignment_scratch_preflight.map(|preflight| {
            // SAFETY: Whole-element byte counts, raw-parts validity, and the
            // complete three-descriptor/three-backing alias preflight finished.
            unsafe { ParticleAssignmentScratchLease::acquire(preflight) }
        });

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
        ProviderForceMode::Direct { .. } => {
            let output = force_output.ok_or_else(|| {
                ProviderFailure::invalid("direct force output is null after provider preflight")
            })?;
            let energy = match (
                workspace_lease.as_mut(),
                neutrality_sort_scratch_lease.as_mut(),
                particle_assignment_scratch_lease.as_mut(),
            ) {
                (
                    Some(workspace),
                    Some(neutrality_sort_scratch),
                    Some(particle_assignment_scratch),
                ) => evaluate_with_direct_force_output_and_all_reusable_storage(
                    &input,
                    output,
                    workspace.workspace_mut(),
                    neutrality_sort_scratch.scratch_mut(),
                    particle_assignment_scratch.scratch_mut(),
                )
                .map_err(ProviderFailure::from)?,
                (Some(workspace), Some(neutrality_sort_scratch), None) => {
                    evaluate_with_direct_force_output_and_reusable_storage(
                        &input,
                        output,
                        workspace.workspace_mut(),
                        neutrality_sort_scratch.scratch_mut(),
                    )
                    .map_err(ProviderFailure::from)?
                }
                (Some(workspace), None, None) => evaluate_with_direct_force_output_and_workspace(
                    &input,
                    output,
                    workspace.workspace_mut(),
                )
                .map_err(ProviderFailure::from)?,
                (None, None, None) => evaluate_with_direct_force_output(&input, output)
                    .map_err(ProviderFailure::from)?,
                (_, None, Some(_)) => {
                    return Err(ProviderFailure::invalid(
                        "particle assignment scratch requires neutrality sort scratch and reciprocal workspace",
                    ));
                }
                (None, Some(_), Some(_)) => {
                    return Err(ProviderFailure::invalid(
                        "particle assignment scratch requires neutrality sort scratch and reciprocal workspace",
                    ));
                }
                (None, Some(_), None) => {
                    return Err(ProviderFailure::invalid(
                        "neutrality sort scratch requires a reciprocal workspace",
                    ));
                }
            };
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
                ProviderForceMode::Direct {
                    workspace: None,
                    neutrality_sort_scratch: None,
                    particle_assignment_scratch: None,
                },
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

/// Evaluate through the direct-force provider while leasing an owner-private
/// reciprocal workspace whose Rust allocation persists across calls.
///
/// # Safety
/// The direct-force evaluator contract applies. `workspace` must point to an
/// all-zero EMPTY descriptor or to the canonical READY descriptor previously
/// returned by this entry point. The descriptor and its complete allocation
/// capacity must remain exclusively owned, initialized, writable, and live for
/// the call and must not overlap any other descriptor or channel.
#[no_mangle]
pub unsafe extern "C" fn bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_v1(
    system: *const ParticleMeshReciprocalSystemV1,
    model: *const ParticleMeshReciprocalModelV1,
    workspace: *mut ParticleMeshReciprocalWorkspaceV1,
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
        // SAFETY: The implementation preflights the workspace descriptor and
        // its entire backing capacity alongside all established provider ranges
        // before taking the RAII ownership lease or borrowing any channel.
        unsafe {
            evaluate_provider_impl(
                system,
                model,
                ProviderForceMode::Direct {
                    workspace: Some(workspace),
                    neutrality_sort_scratch: None,
                    particle_assignment_scratch: None,
                },
                out_energy,
                out_forces,
                error_range,
                &alias_safety,
            )
        }
    }));
    match outcome {
        Ok(Ok(candidate)) => {
            // SAFETY: Direct forces are complete, the lease restored READY
            // ownership during closure return, and no fallible work remains.
            unsafe { commit_candidate(candidate, out_energy) };
            // SAFETY: Error storage completed the full persistent alias preflight.
            unsafe { write_provider_error(out_error, ParticleMeshReciprocalErrorCodeV1::None, "") };
            STATUS_OK
        }
        Ok(Err(failure)) => {
            if failure.may_write_error {
                // SAFETY: The failure records whether error storage was fully
                // proven safe before any potentially overlapping raw range.
                unsafe { write_provider_error(out_error, failure.code, failure.detail) };
            }
            failure.status
        }
        Err(_) => {
            if alias_safety.get() {
                // SAFETY: All descriptor, backing-capacity, and channel ranges
                // were proven disjoint before the leased computation began.
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

/// Evaluate through the direct-force provider while leasing both retained
/// owner-private reciprocal and neutrality-sort allocations.
///
/// # Safety
/// The direct-force evaluator contract applies. `workspace` and
/// `neutrality_sort_scratch` must each point to an all-zero EMPTY descriptor or
/// to the matching canonical READY descriptor previously returned by this
/// entry point. Both descriptors and their complete allocation capacities must
/// remain exclusively owned, initialized, writable, live, and pairwise
/// disjoint from every other descriptor and channel for the call.
#[no_mangle]
pub unsafe extern "C" fn bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_and_neutrality_sort_scratch_v1(
    system: *const ParticleMeshReciprocalSystemV1,
    model: *const ParticleMeshReciprocalModelV1,
    workspace: *mut ParticleMeshReciprocalWorkspaceV1,
    neutrality_sort_scratch: *mut ParticleMeshReciprocalNeutralitySortScratchV1,
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
        // SAFETY: The implementation preflights both descriptors and their
        // entire backing capacities alongside all established provider ranges
        // before either RAII ownership lease or any raw channel borrow.
        unsafe {
            evaluate_provider_impl(
                system,
                model,
                ProviderForceMode::Direct {
                    workspace: Some(workspace),
                    neutrality_sort_scratch: Some(neutrality_sort_scratch),
                    particle_assignment_scratch: None,
                },
                out_energy,
                out_forces,
                error_range,
                &alias_safety,
            )
        }
    }));
    match outcome {
        Ok(Ok(candidate)) => {
            // SAFETY: Direct forces are complete, both leases restored READY
            // ownership during closure return, and no fallible work remains.
            unsafe { commit_candidate(candidate, out_energy) };
            // SAFETY: Error storage completed the full persistent alias preflight.
            unsafe { write_provider_error(out_error, ParticleMeshReciprocalErrorCodeV1::None, "") };
            STATUS_OK
        }
        Ok(Err(failure)) => {
            if failure.may_write_error {
                // SAFETY: The failure records whether error storage was fully
                // proven safe before either potentially overlapping raw range.
                unsafe { write_provider_error(out_error, failure.code, failure.detail) };
            }
            failure.status
        }
        Err(_) => {
            if alias_safety.get() {
                // SAFETY: All descriptors, backing capacities, and channels
                // were proven disjoint before the leased computation began.
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

/// Evaluate through the direct-force provider while leasing all three retained
/// owner-private reciprocal, neutrality-sort, and particle-assignment stores.
///
/// # Safety
/// The direct-force evaluator contract applies. `workspace`,
/// `neutrality_sort_scratch`, and `particle_assignment_scratch` must each point
/// to an all-zero EMPTY descriptor or to the matching canonical READY
/// descriptor previously returned by this entry point. Every descriptor and
/// its complete allocation capacity must remain exclusively owned, initialized,
/// writable, live, and pairwise disjoint from every other descriptor and
/// channel for the call.
#[no_mangle]
pub unsafe extern "C" fn bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_and_neutrality_sort_scratch_and_particle_assignment_scratch_v1(
    system: *const ParticleMeshReciprocalSystemV1,
    model: *const ParticleMeshReciprocalModelV1,
    workspace: *mut ParticleMeshReciprocalWorkspaceV1,
    neutrality_sort_scratch: *mut ParticleMeshReciprocalNeutralitySortScratchV1,
    particle_assignment_scratch: *mut ParticleMeshReciprocalParticleAssignmentScratchV1,
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
        // SAFETY: The implementation preflights all three descriptors and
        // complete backing capacities alongside every provider range before
        // any RAII ownership lease, byte-to-element conversion, or raw borrow.
        unsafe {
            evaluate_provider_impl(
                system,
                model,
                ProviderForceMode::Direct {
                    workspace: Some(workspace),
                    neutrality_sort_scratch: Some(neutrality_sort_scratch),
                    particle_assignment_scratch: Some(particle_assignment_scratch),
                },
                out_energy,
                out_forces,
                error_range,
                &alias_safety,
            )
        }
    }));
    match outcome {
        Ok(Ok(candidate)) => {
            // SAFETY: Direct forces are complete, all leases restored canonical
            // READY ownership during closure return, and no fallible work remains.
            unsafe { commit_candidate(candidate, out_energy) };
            // SAFETY: Error storage completed full persistent alias preflight.
            unsafe { write_provider_error(out_error, ParticleMeshReciprocalErrorCodeV1::None, "") };
            STATUS_OK
        }
        Ok(Err(failure)) => {
            if failure.may_write_error {
                // SAFETY: Failure tracks whether error storage completed every
                // descriptor and full-capacity backing preflight.
                unsafe { write_provider_error(out_error, failure.code, failure.detail) };
            }
            failure.status
        }
        Err(_) => {
            if alias_safety.get() {
                // SAFETY: All descriptors, complete backing capacities, and
                // channels were proven disjoint before leased computation.
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

/// Release a canonical owner-private reciprocal workspace allocation.
///
/// Null, all-zero EMPTY, malformed, and currently LEASED descriptors are
/// fail-closed no-ops. A canonical READY allocation is dropped exactly once and
/// its descriptor becomes all-zero EMPTY before deallocation.
///
/// # Safety
/// `workspace` must be null or point to initialized writable storage for one
/// descriptor. A canonical READY descriptor must have originated from the
/// paired workspace evaluator and remain exclusively owned for this call.
#[no_mangle]
pub unsafe extern "C" fn bg_rust_particle_mesh_reciprocal_workspace_destroy_v1(
    workspace: *mut ParticleMeshReciprocalWorkspaceV1,
) {
    let Some(descriptor_range) = checked_range(
        workspace.cast_const(),
        1,
        "reciprocal workspace descriptor is null",
    )
    .ok()
    .flatten() else {
        return;
    };
    // SAFETY: Fixed-size range validation proved this descriptor readable. Any
    // malformed state returns before a raw allocation is reconstructed.
    let Ok(preflight) = (unsafe { preflight_workspace_descriptor(workspace, descriptor_range) })
    else {
        return;
    };
    let WorkspaceSnapshot::Ready {
        storage,
        length,
        capacity,
    } = preflight.snapshot
    else {
        return;
    };
    if preflight
        .backing_range
        .is_some_and(|range| ranges_overlap(range, descriptor_range))
    {
        return;
    }
    // SAFETY: Canonical READY raw parts were validated and are exclusively
    // owned. Clearing first makes repeat destruction a no-op even while the
    // local Vec subsequently releases the allocation.
    unsafe { ptr::write(workspace, empty_workspace_descriptor()) };
    if capacity != 0 {
        // SAFETY: The canonical descriptor was created from this exact Rust Vec
        // allocation and no other owner exists after the descriptor was zeroed.
        drop(unsafe { Vec::from_raw_parts(storage, length, capacity) });
    }
}

/// Release a canonical owner-private neutrality-sort scratch allocation.
///
/// Null, all-zero EMPTY, malformed, and currently LEASED descriptors are
/// fail-closed no-ops. A canonical READY allocation is dropped exactly once and
/// its descriptor becomes all-zero EMPTY before deallocation.
///
/// # Safety
/// `scratch` must be null or point to initialized writable storage for one
/// descriptor. A canonical READY descriptor must have originated from the
/// paired evaluator and remain exclusively owned for this call.
#[no_mangle]
pub unsafe extern "C" fn bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_destroy_v1(
    scratch: *mut ParticleMeshReciprocalNeutralitySortScratchV1,
) {
    let Some(descriptor_range) = checked_range(
        scratch.cast_const(),
        1,
        "neutrality sort scratch descriptor is null",
    )
    .ok()
    .flatten() else {
        return;
    };
    // SAFETY: Fixed-size range validation proved this descriptor readable. Any
    // malformed state returns before a raw allocation is reconstructed.
    let Ok(preflight) =
        (unsafe { preflight_neutrality_sort_scratch_descriptor(scratch, descriptor_range) })
    else {
        return;
    };
    let NeutralitySortScratchSnapshot::Ready {
        storage,
        length,
        capacity,
    } = preflight.snapshot
    else {
        return;
    };
    if preflight
        .backing_range
        .is_some_and(|range| ranges_overlap(range, descriptor_range))
    {
        return;
    }
    // SAFETY: Canonical READY raw parts were validated and are exclusively
    // owned. Clearing first makes repeat destruction a no-op even while the
    // local Vec subsequently releases the allocation.
    unsafe { ptr::write(scratch, empty_neutrality_sort_scratch_descriptor()) };
    if capacity != 0 {
        // SAFETY: The canonical descriptor was created from this exact Rust Vec
        // allocation and no other owner exists after the descriptor was zeroed.
        drop(unsafe { Vec::from_raw_parts(storage, length, capacity) });
    }
}

/// Release a canonical owner-private particle-assignment scratch allocation.
///
/// Null, all-zero EMPTY, malformed, and currently LEASED descriptors are
/// fail-closed no-ops. A canonical READY allocation is dropped exactly once and
/// its descriptor becomes all-zero EMPTY before deallocation.
///
/// # Safety
/// `scratch` must be null or point to initialized writable storage for one
/// descriptor. A canonical READY descriptor must have originated from the
/// paired evaluator and remain exclusively owned for this call.
#[no_mangle]
pub unsafe extern "C" fn bg_rust_particle_mesh_reciprocal_particle_assignment_scratch_destroy_v1(
    scratch: *mut ParticleMeshReciprocalParticleAssignmentScratchV1,
) {
    let Some(descriptor_range) = checked_range(
        scratch.cast_const(),
        1,
        "particle assignment scratch descriptor is null",
    )
    .ok()
    .flatten() else {
        return;
    };
    // SAFETY: Fixed-size range validation proved this descriptor readable. Any
    // malformed state returns before byte counts become Vec element counts.
    let Ok(preflight) =
        (unsafe { preflight_particle_assignment_scratch_descriptor(scratch, descriptor_range) })
    else {
        return;
    };
    let ParticleAssignmentScratchSnapshot::Ready {
        storage,
        logical_length_bytes,
        allocation_capacity_bytes,
    } = preflight.snapshot
    else {
        return;
    };
    if preflight
        .backing_range
        .is_some_and(|range| ranges_overlap(range, descriptor_range))
    {
        return;
    }
    let element_size = size_of::<ParticleAssignment>();
    let length = logical_length_bytes / element_size;
    let capacity = allocation_capacity_bytes / element_size;
    // SAFETY: Canonical READY raw parts were validated and are exclusively
    // owned. Clearing first makes repeat destruction a no-op before deallocation.
    unsafe { ptr::write(scratch, empty_particle_assignment_scratch_descriptor()) };
    if capacity != 0 {
        // SAFETY: The descriptor originated from this exact Rust Vec allocation;
        // whole-element conversion occurs only after its final alias preflight.
        drop(unsafe {
            Vec::from_raw_parts(storage.cast::<ParticleAssignment>(), length, capacity)
        });
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

    fn empty_workspace() -> ParticleMeshReciprocalWorkspaceV1 {
        empty_workspace_descriptor()
    }

    fn empty_neutrality_sort_scratch() -> ParticleMeshReciprocalNeutralitySortScratchV1 {
        empty_neutrality_sort_scratch_descriptor()
    }

    fn empty_particle_assignment_scratch() -> ParticleMeshReciprocalParticleAssignmentScratchV1 {
        empty_particle_assignment_scratch_descriptor()
    }

    fn neutrality_sort_scratch_storage_bits(
        scratch: &ParticleMeshReciprocalNeutralitySortScratchV1,
    ) -> Vec<u64> {
        assert_eq!(
            scratch.state,
            PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_READY
        );
        if scratch.length == 0 {
            return Vec::new();
        }
        // SAFETY: Tests inspect a live canonical READY scratch returned by the
        // provider, bounded strictly by its initialized logical length.
        unsafe { core::slice::from_raw_parts(scratch.storage.cast::<f64>(), scratch.length) }
            .iter()
            .map(|value| value.to_bits())
            .collect()
    }

    fn particle_assignment_scratch_storage_bits(
        scratch: &ParticleMeshReciprocalParticleAssignmentScratchV1,
    ) -> Vec<u64> {
        assert_eq!(
            scratch.state,
            PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_READY
        );
        assert_eq!(
            scratch.logical_length_bytes % size_of::<ParticleAssignment>(),
            0
        );
        let length = scratch.logical_length_bytes / size_of::<ParticleAssignment>();
        if length == 0 {
            return Vec::new();
        }
        // SAFETY: Tests inspect a live canonical READY scratch returned by the
        // provider, bounded strictly by its initialized logical element count.
        let assignments = unsafe {
            core::slice::from_raw_parts(scratch.storage.cast::<ParticleAssignment>(), length)
        };
        particle_assignment_bits(assignments)
    }

    fn particle_assignment_bits(assignments: &[ParticleAssignment]) -> Vec<u64> {
        let mut bits = Vec::with_capacity(assignments.len() * 3 * CARDINAL_B_SPLINE_ORDER * 3);
        for assignment in assignments {
            for axis in &assignment.axes {
                bits.extend(
                    axis.indices
                        .iter()
                        .map(|index| u64::try_from(*index).unwrap()),
                );
                bits.extend(axis.weights.iter().map(|value| value.to_bits()));
                bits.extend(axis.derivatives.iter().map(|value| value.to_bits()));
            }
        }
        bits
    }

    fn workspace_storage_bits(workspace: &ParticleMeshReciprocalWorkspaceV1) -> Vec<[u64; 2]> {
        assert_eq!(workspace.state, PARTICLE_MESH_RECIPROCAL_WORKSPACE_READY);
        if workspace.length == 0 {
            return Vec::new();
        }
        // SAFETY: Tests inspect a live canonical READY workspace returned by
        // the provider, bounded by its initialized logical length.
        unsafe {
            core::slice::from_raw_parts(workspace.storage.cast::<Complex>(), workspace.length)
        }
        .iter()
        .map(|value| [value.real.to_bits(), value.imaginary.to_bits()])
        .collect()
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

    unsafe fn evaluate_with_owner_reusable_storage(
        system: *const ParticleMeshReciprocalSystemV1,
        model: *const ParticleMeshReciprocalModelV1,
        workspace: *mut ParticleMeshReciprocalWorkspaceV1,
        neutrality_sort_scratch: *mut ParticleMeshReciprocalNeutralitySortScratchV1,
        energy: *mut ParticleMeshReciprocalEnergyV1,
        forces: *mut ParticleMeshReciprocalForceOutputV1,
        error: *mut ParticleMeshReciprocalErrorV1,
    ) -> i32 {
        // SAFETY: Each test documents and owns the descriptor/channel storage
        // supplied to this thin wrapper around the hidden combined entry.
        unsafe {
            super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_and_neutrality_sort_scratch_v1(
                system,
                model,
                workspace,
                neutrality_sort_scratch,
                energy,
                forces,
                error,
            )
        }
    }

    #[allow(clippy::too_many_arguments)]
    unsafe fn evaluate_with_all_owner_reusable_storage(
        system: *const ParticleMeshReciprocalSystemV1,
        model: *const ParticleMeshReciprocalModelV1,
        workspace: *mut ParticleMeshReciprocalWorkspaceV1,
        neutrality_sort_scratch: *mut ParticleMeshReciprocalNeutralitySortScratchV1,
        particle_assignment_scratch: *mut ParticleMeshReciprocalParticleAssignmentScratchV1,
        energy: *mut ParticleMeshReciprocalEnergyV1,
        forces: *mut ParticleMeshReciprocalForceOutputV1,
        error: *mut ParticleMeshReciprocalErrorV1,
    ) -> i32 {
        // SAFETY: Each test documents and owns every descriptor and channel
        // supplied to this thin wrapper around the hidden triple-scratch entry.
        unsafe {
            super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_and_neutrality_sort_scratch_and_particle_assignment_scratch_v1(
                system,
                model,
                workspace,
                neutrality_sort_scratch,
                particle_assignment_scratch,
                energy,
                forces,
                error,
            )
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
        assert_eq!(size_of::<ParticleMeshReciprocalWorkspaceV1>(), 72);
        assert_eq!(
            size_of::<ParticleMeshReciprocalNeutralitySortScratchV1>(),
            72
        );
        assert_eq!(
            size_of::<ParticleMeshReciprocalParticleAssignmentScratchV1>(),
            72
        );
        assert_eq!(size_of::<AxisAssignment>(), 96);
        assert_eq!(size_of::<ParticleAssignment>(), 288);
        assert!(!std::mem::needs_drop::<ParticleAssignment>());
        assert_eq!(size_of::<Complex>(), 16);
        assert_eq!(size_of::<ParticleMeshReciprocalErrorV1>(), 304);
        assert_eq!(align_of::<ParticleMeshReciprocalSystemV1>(), 8);
        assert_eq!(align_of::<ParticleMeshReciprocalModelV1>(), 8);
        assert_eq!(align_of::<ParticleMeshReciprocalEnergyV1>(), 8);
        assert_eq!(align_of::<ParticleMeshReciprocalForceOutputV1>(), 8);
        assert_eq!(align_of::<ParticleMeshReciprocalWorkspaceV1>(), 8);
        assert_eq!(
            align_of::<ParticleMeshReciprocalNeutralitySortScratchV1>(),
            8
        );
        assert_eq!(
            align_of::<ParticleMeshReciprocalParticleAssignmentScratchV1>(),
            8
        );
        assert_eq!(align_of::<ParticleAssignment>(), 8);
        assert_eq!(align_of::<ParticleMeshReciprocalErrorV1>(), 8);
        assert_eq!(PARTICLE_MESH_RECIPROCAL_WORKSPACE_EMPTY, 0);
        assert_eq!(PARTICLE_MESH_RECIPROCAL_WORKSPACE_READY, 0x5257_5331);
        assert_eq!(PARTICLE_MESH_RECIPROCAL_WORKSPACE_LEASED, 0x4c45_5331);
        assert_eq!(PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_EMPTY, 0);
        assert_eq!(
            PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_READY,
            0x4e53_5331
        );
        assert_eq!(
            PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_LEASED,
            0x4e53_4c31
        );
        assert_eq!(
            PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_EMPTY,
            0
        );
        assert_eq!(
            PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_READY,
            0x5041_5331
        );
        assert_eq!(
            PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_LEASED,
            0x5041_4c31
        );
        assert_ne!(
            PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_READY,
            PARTICLE_MESH_RECIPROCAL_WORKSPACE_READY
        );
        assert_ne!(
            PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_LEASED,
            PARTICLE_MESH_RECIPROCAL_WORKSPACE_LEASED
        );
        assert_ne!(
            PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_READY,
            PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_READY
        );
        assert_ne!(
            PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_LEASED,
            PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_LEASED
        );
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
    fn reciprocal_workspace_has_exact_noncubic_spectrum_and_axis_tail_layout() {
        let dimensions = [4, 8, 16];
        let cell_lengths = [18.0, 20.0, 22.0];
        let validated = ValidatedInput {
            dimensions,
            mesh_point_count: 512,
            volume_angstrom_cubed: 1.0,
        };
        let mut workspace = ReciprocalWorkspace::new(&validated)
            .expect("validated reciprocal workspace must allocate");
        assert_eq!(workspace.storage.len(), 540);
        let storage_pointer = workspace.storage.as_ptr();
        let (spectrum, reciprocal_tail) =
            workspace.storage.split_at_mut(validated.mesh_point_count);
        assert_eq!(spectrum.len(), 512);
        assert_eq!(reciprocal_tail.len(), 28);
        assert_eq!(spectrum.as_ptr(), storage_pointer);
        assert_eq!(
            spectrum.as_ptr().wrapping_add(spectrum.len()),
            reciprocal_tail.as_ptr()
        );

        fill_reciprocal_axis_data(reciprocal_tail, dimensions, cell_lengths);
        let (x_axis_data, yz_axis_data) = reciprocal_tail.split_at(dimensions[0]);
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
                assert_eq!(datum.real.to_bits(), (wave * wave).to_bits());
                assert_eq!(
                    datum.imaginary.to_bits(),
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
    fn reciprocal_workspace_tail_reuses_fft_prefix_around_exact_axis_phase() {
        let input = fixture([4, 8, 16]);
        let validated = validate(&input).expect("noncubic fixture must validate");
        let dimensions = validated.dimensions;
        let mut workspace = ReciprocalWorkspace::new(&validated)
            .expect("validated reciprocal workspace must allocate");
        let line_count = dimensions.into_iter().max().unwrap();
        assert_eq!(line_count, 16);
        let (spectrum, reciprocal_tail) =
            workspace.storage.split_at_mut(validated.mesh_point_count);
        let tail_pointer = reciprocal_tail.as_ptr();

        for (index, value) in spectrum.iter_mut().enumerate() {
            *value = Complex::new(libm::sin(0.37 * bounded_usize_to_f64(index)), 0.0);
        }
        reciprocal_tail.fill(Complex::new(f64::NAN, f64::NAN));
        fft::fft_3d(
            spectrum,
            dimensions,
            false,
            &mut reciprocal_tail[..line_count],
        );
        assert!(reciprocal_tail[..line_count]
            .iter()
            .all(|value| value.real.is_finite() && value.imaginary.is_finite()));
        assert!(reciprocal_tail[line_count..]
            .iter()
            .all(|value| value.real.is_nan() && value.imaginary.is_nan()));

        fill_reciprocal_axis_data(reciprocal_tail, dimensions, input.cell.lengths_angstrom);
        let axis_bits = reciprocal_tail
            .iter()
            .map(|value| [value.real.to_bits(), value.imaginary.to_bits()])
            .collect::<Vec<_>>();
        let reciprocal = apply_reciprocal_operator(&input, &validated, spectrum, reciprocal_tail);
        assert!(reciprocal.energy.is_finite());
        assert_eq!(
            reciprocal_tail
                .iter()
                .map(|value| [value.real.to_bits(), value.imaginary.to_bits()])
                .collect::<Vec<_>>(),
            axis_bits
        );

        reciprocal_tail[..line_count].fill(Complex::new(f64::NAN, f64::NAN));
        fft::fft_3d(
            spectrum,
            dimensions,
            true,
            &mut reciprocal_tail[..line_count],
        );
        assert_eq!(reciprocal_tail.as_ptr(), tail_pointer);
        assert!(reciprocal_tail[..line_count]
            .iter()
            .all(|value| value.real.is_finite() && value.imaginary.is_finite()));
        assert_eq!(
            reciprocal_tail[line_count..]
                .iter()
                .map(|value| [value.real.to_bits(), value.imaginary.to_bits()])
                .collect::<Vec<_>>(),
            axis_bits[line_count..]
        );
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
            AllocationSite::ReciprocalWorkspace,
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
                AllocationFailureGuard::inject_at(AllocationSite::ReciprocalWorkspace, 1);
            // SAFETY: The reciprocal workspace allocation precedes every
            // caller force write, and the fifth elements are protected tails.
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
            AllocationSite::ReciprocalWorkspace.detail()
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
    fn provider_modes_share_one_reciprocal_workspace_and_leave_second_occurrence_pending() {
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
                AllocationFailureGuard::inject_at(AllocationSite::ReciprocalWorkspace, 2);
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
            assert_injected_allocation_remains_pending(AllocationSite::ReciprocalWorkspace);
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
                AllocationFailureGuard::inject_at(AllocationSite::ReciprocalWorkspace, 2);
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
            assert_injected_allocation_remains_pending(AllocationSite::ReciprocalWorkspace);
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
                AllocationFailureGuard::inject_at(AllocationSite::ReciprocalWorkspace, 2);
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
            assert_injected_allocation_remains_pending(AllocationSite::ReciprocalWorkspace);
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
    fn first_reciprocal_workspace_oom_is_transactional_in_all_provider_modes() {
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

        let mut energy_only = initialized_energy(11.0);
        let mut energy_only_error = initialized_error();
        {
            let _injection =
                AllocationFailureGuard::inject_at(AllocationSite::ReciprocalWorkspace, 1);
            // SAFETY: Valid immutable inputs and disjoint output descriptors
            // exercise the first and only reciprocal workspace allocation.
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
                STATUS_OUT_OF_MEMORY
            );
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
                AllocationFailureGuard::inject_at(AllocationSite::ReciprocalWorkspace, 1);
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
                STATUS_OUT_OF_MEMORY
            );
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
                AllocationFailureGuard::inject_at(AllocationSite::ReciprocalWorkspace, 1);
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
                STATUS_OUT_OF_MEMORY
            );
        }

        assert_eq!(
            energy_only.reciprocal_space_kcal_per_mol.to_bits(),
            11.0_f64.to_bits()
        );
        assert_eq!(
            transactional_energy.reciprocal_space_kcal_per_mol.to_bits(),
            101.0_f64.to_bits()
        );
        assert_eq!(
            direct_energy.reciprocal_space_kcal_per_mol.to_bits(),
            401.0_f64.to_bits()
        );
        assert_eq!(transactional_x, [201.0, 201.0, 201.0, 201.0, 301.0]);
        assert_eq!(transactional_y, [202.0, 202.0, 202.0, 202.0, 302.0]);
        assert_eq!(transactional_z, [203.0, 203.0, 203.0, 203.0, 303.0]);
        assert_eq!(direct_x, [501.0, 501.0, 501.0, 501.0, 601.0]);
        assert_eq!(direct_y, [502.0, 502.0, 502.0, 502.0, 602.0]);
        assert_eq!(direct_z, [503.0, 503.0, 503.0, 503.0, 603.0]);
        for error in [&energy_only_error, &transactional_error, &direct_error] {
            assert_eq!(
                provider_error_detail(error),
                AllocationSite::ReciprocalWorkspace.detail()
            );
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
            AllocationSite::ReciprocalWorkspace,
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
            AllocationSite::ReciprocalWorkspace,
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

    #[test]
    fn owner_workspace_cold_oom_warm_reuse_and_stateless_allocation_are_frozen() {
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
        let expected = evaluate(&fixture([4, 8, 16])).expect("baseline must evaluate");
        for site in [
            AllocationSite::NeutralitySort,
            AllocationSite::ParticleAssignments,
            AllocationSite::ReciprocalWorkspace,
        ] {
            let mut cold_workspace = empty_workspace();
            let cold_workspace_before = descriptor_bytes(&cold_workspace);
            let mut cold_energy = initialized_energy(11.0);
            let mut cold_x = [21.0; 4];
            let mut cold_y = [22.0; 4];
            let mut cold_z = [23.0; 4];
            let mut cold_output = provider_force_output(&mut cold_x, &mut cold_y, &mut cold_z);
            let mut cold_error = initialized_error();
            let _injection = AllocationFailureGuard::inject(site);
            // SAFETY: Valid disjoint storage exercises each cold allocation in
            // the frozen neutrality -> assignments -> workspace order.
            assert_eq!(
                unsafe {
                    super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_v1(
                        &system,
                        &model,
                        &mut cold_workspace,
                        &mut cold_energy,
                        &mut cold_output,
                        &mut cold_error,
                    )
                },
                STATUS_OUT_OF_MEMORY,
                "cold allocation site {site:?}"
            );
            assert_eq!(provider_error_detail(&cold_error), site.detail());
            assert_eq!(descriptor_bytes(&cold_workspace), cold_workspace_before);
            assert_eq!(
                cold_energy.reciprocal_space_kcal_per_mol.to_bits(),
                11.0_f64.to_bits()
            );
            assert_eq!(cold_x, [21.0; 4]);
            assert_eq!(cold_y, [22.0; 4]);
            assert_eq!(cold_z, [23.0; 4]);
        }
        let mut workspace = empty_workspace();
        let empty_bytes = descriptor_bytes(&workspace);

        let mut energy = initialized_energy(101.0);
        let mut force_x = [201.0; 5];
        let mut force_y = [202.0; 5];
        let mut force_z = [203.0; 5];
        force_x[4] = 301.0;
        force_y[4] = 302.0;
        force_z[4] = 303.0;
        let mut output = provider_force_output(&mut force_x, &mut force_y, &mut force_z);
        output.capacity = charges.len();
        let mut error = initialized_error();
        {
            let _injection =
                AllocationFailureGuard::inject_at(AllocationSite::ReciprocalWorkspace, 1);
            // SAFETY: Every descriptor/channel is live and disjoint. The hook
            // rejects the cold workspace reserve after earlier allocations.
            assert_eq!(
                unsafe {
                    super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_v1(
                        &system,
                        &model,
                        &mut workspace,
                        &mut energy,
                        &mut output,
                        &mut error,
                    )
                },
                STATUS_OUT_OF_MEMORY
            );
        }
        assert_eq!(
            provider_error_detail(&error),
            AllocationSite::ReciprocalWorkspace.detail()
        );
        assert_eq!(descriptor_bytes(&workspace), empty_bytes);
        assert_eq!(
            energy.reciprocal_space_kcal_per_mol.to_bits(),
            101.0_f64.to_bits()
        );
        assert_eq!(force_x, [201.0, 201.0, 201.0, 201.0, 301.0]);
        assert_eq!(force_y, [202.0, 202.0, 202.0, 202.0, 302.0]);
        assert_eq!(force_z, [203.0, 203.0, 203.0, 203.0, 303.0]);

        let mut error = initialized_error();
        // SAFETY: Same valid owner-private descriptors provision the workspace.
        assert_eq!(
            unsafe {
                super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_v1(
                    &system,
                    &model,
                    &mut workspace,
                    &mut energy,
                    &mut output,
                    &mut error,
                )
            },
            STATUS_OK
        );
        let workspace_pointer = workspace.storage;
        let workspace_capacity = workspace.capacity;
        assert_eq!(workspace.state, PARTICLE_MESH_RECIPROCAL_WORKSPACE_READY);
        assert_eq!(workspace.length, 4 * 8 * 16 + 4 + 8 + 16);
        assert!(workspace.capacity >= workspace.length);
        assert!(!workspace.storage.is_null());
        assert_eq!(
            energy.reciprocal_space_kcal_per_mol.to_bits(),
            expected.reciprocal_space_kcal_per_mol.to_bits()
        );

        let mut warm_energy = initialized_energy(401.0);
        let mut warm_x = [501.0; 5];
        let mut warm_y = [502.0; 5];
        let mut warm_z = [503.0; 5];
        warm_x[4] = 601.0;
        warm_y[4] = 602.0;
        warm_z[4] = 603.0;
        let mut warm_output = provider_force_output(&mut warm_x, &mut warm_y, &mut warm_z);
        warm_output.capacity = charges.len();
        let mut warm_error = initialized_error();
        {
            let _injection =
                AllocationFailureGuard::inject_at(AllocationSite::ReciprocalWorkspace, 1);
            // SAFETY: Capacity-sufficient reuse must not request a workspace
            // reserve, leaving the one-shot injection pending.
            assert_eq!(
                unsafe {
                    super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_v1(
                        &system,
                        &model,
                        &mut workspace,
                        &mut warm_energy,
                        &mut warm_output,
                        &mut warm_error,
                    )
                },
                STATUS_OK
            );
            assert_injected_allocation_remains_pending(AllocationSite::ReciprocalWorkspace);
        }
        assert_eq!(workspace.storage, workspace_pointer);
        assert_eq!(workspace.capacity, workspace_capacity);
        assert_eq!(
            warm_energy.reciprocal_space_kcal_per_mol.to_bits(),
            expected.reciprocal_space_kcal_per_mol.to_bits()
        );
        for (particle, expected_force) in expected.forces_kcal_per_mol_angstrom.iter().enumerate() {
            assert_eq!(warm_x[particle].to_bits(), expected_force[0].to_bits());
            assert_eq!(warm_y[particle].to_bits(), expected_force[1].to_bits());
            assert_eq!(warm_z[particle].to_bits(), expected_force[2].to_bits());
        }
        assert_eq!(warm_x[4].to_bits(), 601.0_f64.to_bits());
        assert_eq!(warm_y[4].to_bits(), 602.0_f64.to_bits());
        assert_eq!(warm_z[4].to_bits(), 603.0_f64.to_bits());

        let mut stateless_energy = initialized_energy(701.0);
        let mut stateless_x = [801.0; 4];
        let mut stateless_y = [802.0; 4];
        let mut stateless_z = [803.0; 4];
        let mut stateless_output =
            provider_force_output(&mut stateless_x, &mut stateless_y, &mut stateless_z);
        let mut stateless_error = initialized_error();
        {
            let _injection = AllocationFailureGuard::inject(AllocationSite::ReciprocalWorkspace);
            // SAFETY: The established stateless direct entry remains call-local
            // even while a separate persistent workspace is warm.
            assert_eq!(
                unsafe {
                    super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_v1(
                        &system,
                        &model,
                        &mut stateless_energy,
                        &mut stateless_output,
                        &mut stateless_error,
                    )
                },
                STATUS_OUT_OF_MEMORY
            );
        }
        assert_eq!(
            stateless_energy.reciprocal_space_kcal_per_mol.to_bits(),
            701.0_f64.to_bits()
        );
        assert_eq!(stateless_x, [801.0; 4]);
        assert_eq!(stateless_y, [802.0; 4]);
        assert_eq!(stateless_z, [803.0; 4]);
        assert_eq!(position_x.map(f64::to_bits), input_before[0]);
        assert_eq!(position_y.map(f64::to_bits), input_before[1]);
        assert_eq!(position_z.map(f64::to_bits), input_before[2]);
        assert_eq!(charges.map(f64::to_bits), input_before[3]);

        // SAFETY: The canonical READY descriptor is exclusively owned here.
        unsafe { super::bg_rust_particle_mesh_reciprocal_workspace_destroy_v1(&mut workspace) };
        assert_eq!(descriptor_bytes(&workspace), empty_bytes);
        // SAFETY: Repeat destruction of all-zero EMPTY is a no-op.
        unsafe { super::bg_rust_particle_mesh_reciprocal_workspace_destroy_v1(&mut workspace) };
        assert_eq!(descriptor_bytes(&workspace), empty_bytes);
    }

    #[test]
    fn owner_workspace_poison_shrink_growth_and_failed_growth_are_deterministic() {
        let position_x = [1.25, 5.1, 10.2, 15.4];
        let position_y = [2.5, 3.2, 12.3, 17.1];
        let position_z = [3.75, 8.4, 7.7, 19.3];
        let charges = [0.7, -0.4, -0.6, 0.300_000_000_000_000_04];
        let system = provider_system(&position_x, &position_y, &position_z, &charges);
        let mut model = provider_model([8; 3]);
        let mut workspace = empty_workspace();
        let mut energy = initialized_energy(101.0);
        let mut force_x = [201.0; 4];
        let mut force_y = [202.0; 4];
        let mut force_z = [203.0; 4];
        let mut output = provider_force_output(&mut force_x, &mut force_y, &mut force_z);
        let mut error = initialized_error();
        // SAFETY: Valid disjoint owner-private storage provisions [8,8,8].
        assert_eq!(
            unsafe {
                super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_v1(
                    &system, &model, &mut workspace, &mut energy, &mut output, &mut error,
                )
            },
            STATUS_OK
        );
        assert_eq!(workspace.length, 8 * 8 * 8 + 8 + 8 + 8);
        let initial_pointer = workspace.storage;
        let initial_capacity = workspace.capacity;
        // SAFETY: Canonical READY grants exclusive access to every initialized
        // element in its logical length between calls. Poisoning the complete
        // retained payload demonstrates that prepare and the pipeline
        // initialize every element that the same-shape warm call may read.
        unsafe {
            core::slice::from_raw_parts_mut(workspace.storage.cast::<Complex>(), workspace.length)
                .fill(Complex::new(f64::NAN, f64::INFINITY));
        }

        let expected_same = evaluate(&fixture([8; 3])).expect("same-shape baseline must evaluate");
        let mut error = initialized_error();
        assert_eq!(
            unsafe {
                super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_v1(
                    &system, &model, &mut workspace, &mut energy, &mut output, &mut error,
                )
            },
            STATUS_OK
        );
        assert_eq!(workspace.storage, initial_pointer);
        assert_eq!(workspace.capacity, initial_capacity);
        assert_eq!(
            energy.reciprocal_space_kcal_per_mol.to_bits(),
            expected_same.reciprocal_space_kcal_per_mol.to_bits()
        );

        for dimensions in [[4; 3], [4, 8, 8]] {
            model.mesh_dimensions = dimensions;
            let expected =
                evaluate(&fixture(dimensions)).expect("capacity reuse baseline must evaluate");
            let mut error = initialized_error();
            {
                let _injection =
                    AllocationFailureGuard::inject(AllocationSite::ReciprocalWorkspace);
                assert_eq!(
                    unsafe {
                        super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_v1(
                            &system, &model, &mut workspace, &mut energy, &mut output, &mut error,
                        )
                    },
                    STATUS_OK
                );
                assert_injected_allocation_remains_pending(AllocationSite::ReciprocalWorkspace);
            }
            assert_eq!(workspace.storage, initial_pointer);
            assert_eq!(workspace.capacity, initial_capacity);
            assert_eq!(
                energy.reciprocal_space_kcal_per_mol.to_bits(),
                expected.reciprocal_space_kcal_per_mol.to_bits()
            );
        }

        let retained_pointer = workspace.storage;
        let retained_length = workspace.length;
        let retained_capacity = workspace.capacity;
        let retained_bits = workspace_storage_bits(&workspace);
        model.mesh_dimensions = [16; 3];
        energy.reciprocal_space_kcal_per_mol = 701.0;
        force_x.fill(801.0);
        force_y.fill(802.0);
        force_z.fill(803.0);
        let mut error = initialized_error();
        {
            let _injection = AllocationFailureGuard::inject(AllocationSite::ReciprocalWorkspace);
            assert_eq!(
                unsafe {
                    super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_v1(
                        &system, &model, &mut workspace, &mut energy, &mut output, &mut error,
                    )
                },
                STATUS_OUT_OF_MEMORY
            );
        }
        assert_eq!(
            provider_error_detail(&error),
            AllocationSite::ReciprocalWorkspace.detail()
        );
        assert_eq!(workspace.storage, retained_pointer);
        assert_eq!(workspace.length, retained_length);
        assert_eq!(workspace.capacity, retained_capacity);
        assert_eq!(workspace_storage_bits(&workspace), retained_bits);
        assert_eq!(
            energy.reciprocal_space_kcal_per_mol.to_bits(),
            701.0_f64.to_bits()
        );
        assert_eq!(force_x, [801.0; 4]);
        assert_eq!(force_y, [802.0; 4]);
        assert_eq!(force_z, [803.0; 4]);

        let expected_growth = evaluate(&fixture([16; 3])).expect("growth baseline must evaluate");
        let mut error = initialized_error();
        assert_eq!(
            unsafe {
                super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_v1(
                    &system, &model, &mut workspace, &mut energy, &mut output, &mut error,
                )
            },
            STATUS_OK
        );
        assert_eq!(workspace.length, 16 * 16 * 16 + 16 + 16 + 16);
        assert!(workspace.capacity >= workspace.length);
        assert_eq!(
            energy.reciprocal_space_kcal_per_mol.to_bits(),
            expected_growth.reciprocal_space_kcal_per_mol.to_bits()
        );
        // SAFETY: Canonical READY is uniquely owned after successful growth.
        unsafe { super::bg_rust_particle_mesh_reciprocal_workspace_destroy_v1(&mut workspace) };
    }

    #[test]
    fn owner_workspace_panic_restores_ready_lease_and_next_call_succeeds() {
        let position_x = [1.25, 5.1, 10.2, 15.4];
        let position_y = [2.5, 3.2, 12.3, 17.1];
        let position_z = [3.75, 8.4, 7.7, 19.3];
        let charges = [0.7, -0.4, -0.6, 0.300_000_000_000_000_04];
        let system = provider_system(&position_x, &position_y, &position_z, &charges);
        let model = provider_model([4, 8, 16]);
        let expected = evaluate(&fixture([4, 8, 16])).expect("baseline must evaluate");
        let mut workspace = empty_workspace();
        let mut energy = initialized_energy(101.0);
        let mut force_x = [201.0; 4];
        let mut force_y = [202.0; 4];
        let mut force_z = [203.0; 4];
        let mut output = provider_force_output(&mut force_x, &mut force_y, &mut force_z);
        let mut error = initialized_error();
        assert_eq!(
            unsafe {
                super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_v1(
                    &system, &model, &mut workspace, &mut energy, &mut output, &mut error,
                )
            },
            STATUS_OK
        );
        let pointer_before = workspace.storage;
        let capacity_before = workspace.capacity;

        energy.reciprocal_space_kcal_per_mol = 211.0;
        force_x.fill(221.0);
        force_y.fill(222.0);
        force_z.fill(223.0);
        let mut late_error = initialized_error();
        {
            let _late = LateNonFiniteResultGuard::inject();
            // SAFETY: The injected late scientific failure occurs after direct
            // force writes and must still return workspace ownership to READY.
            assert_eq!(
                unsafe {
                    super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_v1(
                        &system,
                        &model,
                        &mut workspace,
                        &mut energy,
                        &mut output,
                        &mut late_error,
                    )
                },
                STATUS_NUMERICAL_ERROR
            );
        }
        assert_eq!(
            late_error.typed_code,
            ParticleMeshReciprocalErrorCodeV1::NonFiniteResult as i32
        );
        assert_eq!(workspace.state, PARTICLE_MESH_RECIPROCAL_WORKSPACE_READY);
        assert_eq!(workspace.storage, pointer_before);
        assert_eq!(workspace.capacity, capacity_before);
        assert_eq!(
            energy.reciprocal_space_kcal_per_mol.to_bits(),
            211.0_f64.to_bits()
        );
        assert_ne!(force_x, [221.0; 4]);
        assert_ne!(force_y, [222.0; 4]);
        assert_ne!(force_z, [223.0; 4]);

        let mut late_recovery_error = initialized_error();
        assert_eq!(
            unsafe {
                super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_v1(
                    &system,
                    &model,
                    &mut workspace,
                    &mut energy,
                    &mut output,
                    &mut late_recovery_error,
                )
            },
            STATUS_OK
        );
        assert_eq!(
            energy.reciprocal_space_kcal_per_mol.to_bits(),
            expected.reciprocal_space_kcal_per_mol.to_bits()
        );
        assert_eq!(workspace.storage, pointer_before);
        assert_eq!(workspace.capacity, capacity_before);

        energy.reciprocal_space_kcal_per_mol = 301.0;
        force_x.fill(401.0);
        force_y.fill(402.0);
        force_z.fill(403.0);
        let mut error = initialized_error();
        {
            let _panic = ReusableWorkspacePanicGuard::inject();
            // SAFETY: The test-only panic fires after capacity preparation but
            // before spectrum spreading or any direct caller force write.
            assert_eq!(
                unsafe {
                    super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_v1(
                        &system, &model, &mut workspace, &mut energy, &mut output, &mut error,
                    )
                },
                STATUS_INTERNAL_ERROR
            );
        }
        assert_eq!(
            provider_error_detail(&error),
            "rust particle-mesh reciprocal provider panicked"
        );
        assert_eq!(workspace.state, PARTICLE_MESH_RECIPROCAL_WORKSPACE_READY);
        assert_eq!(workspace.storage, pointer_before);
        assert_eq!(workspace.capacity, capacity_before);
        assert_eq!(
            energy.reciprocal_space_kcal_per_mol.to_bits(),
            301.0_f64.to_bits()
        );
        assert_eq!(force_x, [401.0; 4]);
        assert_eq!(force_y, [402.0; 4]);
        assert_eq!(force_z, [403.0; 4]);

        let mut error = initialized_error();
        assert_eq!(
            unsafe {
                super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_v1(
                    &system, &model, &mut workspace, &mut energy, &mut output, &mut error,
                )
            },
            STATUS_OK
        );
        assert_eq!(
            energy.reciprocal_space_kcal_per_mol.to_bits(),
            expected.reciprocal_space_kcal_per_mol.to_bits()
        );
        // SAFETY: The recovered canonical READY workspace is uniquely owned.
        unsafe { super::bg_rust_particle_mesh_reciprocal_workspace_destroy_v1(&mut workspace) };
    }

    #[test]
    fn owner_workspace_malformed_busy_and_alias_cases_fail_closed() {
        // SAFETY: Null destruction is explicitly an idempotent no-op.
        unsafe { super::bg_rust_particle_mesh_reciprocal_workspace_destroy_v1(ptr::null_mut()) };
        let position_x = [1.25, 5.1, 10.2, 15.4];
        let position_y = [2.5, 3.2, 12.3, 17.1];
        let position_z = [3.75, 8.4, 7.7, 19.3];
        let charges = [0.7, -0.4, -0.6, 0.300_000_000_000_000_04];
        let system = provider_system(&position_x, &position_y, &position_z, &charges);
        let model = provider_model([16; 3]);
        let mut energy = initialized_energy(101.0);
        let mut force_x = [201.0; 4];
        let mut force_y = [202.0; 4];
        let mut force_z = [203.0; 4];
        let mut output = provider_force_output(&mut force_x, &mut force_y, &mut force_z);

        let mut null_error = initialized_error();
        let null_error_before = descriptor_bytes(&null_error);
        // SAFETY: Null workspace is deliberately invalid and must fail before
        // treating this persistent entry as the established stateless path.
        assert_eq!(
            unsafe {
                super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_v1(
                    &system,
                    &model,
                    ptr::null_mut(),
                    &mut energy,
                    &mut output,
                    &mut null_error,
                )
            },
            STATUS_INVALID_ARGUMENT
        );
        assert_eq!(descriptor_bytes(&null_error), null_error_before);

        let mut misaligned_storage = [0_u8; size_of::<Complex>() + align_of::<Complex>()];
        let misaligned_offset = (0..align_of::<Complex>())
            .find(|offset| {
                (misaligned_storage.as_ptr() as usize + offset) % align_of::<Complex>() != 0
            })
            .expect("complex alignment has a misaligned byte offset");
        let misaligned_pointer = unsafe {
            misaligned_storage
                .as_mut_ptr()
                .add(misaligned_offset)
                .cast::<c_void>()
        };
        let oversized_capacity = (isize::MAX as usize) / size_of::<Complex>() + 1;

        let malformed_cases = [
            ParticleMeshReciprocalWorkspaceV1 {
                struct_size: 1,
                ..empty_workspace()
            },
            canonical_workspace_descriptor(
                PARTICLE_MESH_RECIPROCAL_WORKSPACE_READY,
                ptr::null_mut(),
                0,
                1,
            ),
            ParticleMeshReciprocalWorkspaceV1 {
                length: 1,
                ..canonical_workspace_descriptor(
                    PARTICLE_MESH_RECIPROCAL_WORKSPACE_READY,
                    ptr::null_mut(),
                    0,
                    0,
                )
            },
            ParticleMeshReciprocalWorkspaceV1 {
                reserved: [1, 0, 0, 0],
                ..canonical_workspace_descriptor(
                    PARTICLE_MESH_RECIPROCAL_WORKSPACE_READY,
                    ptr::null_mut(),
                    0,
                    0,
                )
            },
            canonical_workspace_descriptor(0x554e_4b4e, ptr::null_mut(), 0, 0),
            canonical_workspace_descriptor(
                PARTICLE_MESH_RECIPROCAL_WORKSPACE_READY,
                misaligned_pointer,
                1,
                1,
            ),
            canonical_workspace_descriptor(
                PARTICLE_MESH_RECIPROCAL_WORKSPACE_READY,
                ptr::dangling::<Complex>().cast_mut().cast::<c_void>(),
                1,
                oversized_capacity,
            ),
        ];
        for mut workspace in malformed_cases {
            let workspace_before = descriptor_bytes(&workspace);
            let mut error = initialized_error();
            let error_before = descriptor_bytes(&error);
            // SAFETY: Each live descriptor is deliberately malformed. Hardened
            // preflight must neither acquire/free it nor write the error until
            // a claimed backing range can be proven disjoint.
            let status = unsafe {
                super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_v1(
                    &system, &model, &mut workspace, &mut energy, &mut output, &mut error,
                )
            };
            assert_ne!(status, STATUS_OK);
            assert_eq!(descriptor_bytes(&workspace), workspace_before);
            assert_eq!(descriptor_bytes(&error), error_before);
            // SAFETY: Malformed descriptors are fail-closed destroy no-ops.
            unsafe { super::bg_rust_particle_mesh_reciprocal_workspace_destroy_v1(&mut workspace) };
            assert_eq!(descriptor_bytes(&workspace), workspace_before);
        }

        let mut busy = canonical_workspace_descriptor(
            PARTICLE_MESH_RECIPROCAL_WORKSPACE_LEASED,
            ptr::null_mut(),
            0,
            0,
        );
        let busy_before = descriptor_bytes(&busy);
        let mut busy_aliased_storage =
            [0_u64; { size_of::<ParticleMeshReciprocalErrorV1>() / size_of::<u64>() }];
        let busy_aliased_error = busy_aliased_storage
            .as_mut_ptr()
            .cast::<ParticleMeshReciprocalErrorV1>();
        // SAFETY: u64 storage has the error descriptor's alignment and exact
        // size. Its first four f64-width words also form an initialized input
        // channel that deliberately aliases writable error storage.
        unsafe { ptr::write(busy_aliased_error, initialized_error()) };
        let busy_aliased_before = descriptor_bytes(busy_aliased_error);
        let busy_alias_system = ParticleMeshReciprocalSystemV1 {
            position_x: busy_aliased_error.cast::<f64>(),
            ..system
        };
        assert_eq!(
            unsafe {
                super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_v1(
                    &busy_alias_system,
                    &model,
                    &mut busy,
                    &mut energy,
                    &mut output,
                    busy_aliased_error,
                )
            },
            STATUS_INVALID_ARGUMENT
        );
        assert_eq!(descriptor_bytes(busy_aliased_error), busy_aliased_before);
        assert_eq!(descriptor_bytes(&busy), busy_before);
        let mut busy_error = initialized_error();
        assert_eq!(
            unsafe {
                super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_v1(
                    &system, &model, &mut busy, &mut energy, &mut output, &mut busy_error,
                )
            },
            STATUS_INVALID_ARGUMENT
        );
        assert_eq!(
            provider_error_detail(&busy_error),
            "reciprocal workspace is already leased"
        );
        // SAFETY: LEASED is intentionally a destroy no-op.
        unsafe { super::bg_rust_particle_mesh_reciprocal_workspace_destroy_v1(&mut busy) };
        assert_eq!(descriptor_bytes(&busy), busy_before);

        let mut workspace = empty_workspace();
        let mut error = initialized_error();
        assert_eq!(
            unsafe {
                super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_v1(
                    &system, &model, &mut workspace, &mut energy, &mut output, &mut error,
                )
            },
            STATUS_OK
        );
        let workspace_before = descriptor_bytes(&workspace);
        let backing_before = workspace_storage_bits(&workspace);
        let mut alias_y = [501.0; 4];
        let mut alias_z = [502.0; 4];
        let mut alias_output = ParticleMeshReciprocalForceOutputV1 {
            struct_size: u32::try_from(size_of::<ParticleMeshReciprocalForceOutputV1>()).unwrap(),
            abi_version: PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION,
            capacity: 4,
            x: workspace.storage.cast::<f64>(),
            y: alias_y.as_mut_ptr(),
            z: alias_z.as_mut_ptr(),
            reserved: [0; 4],
        };
        let mut alias_error = initialized_error();
        assert_eq!(
            unsafe {
                super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_v1(
                    &system, &model, &mut workspace, &mut energy, &mut alias_output, &mut alias_error,
                )
            },
            STATUS_INVALID_ARGUMENT
        );
        assert_eq!(descriptor_bytes(&workspace), workspace_before);
        assert_eq!(workspace_storage_bits(&workspace), backing_before);
        assert_eq!(alias_y, [501.0; 4]);
        assert_eq!(alias_z, [502.0; 4]);

        let aliased_error_pointer = workspace.storage.cast::<ParticleMeshReciprocalErrorV1>();
        // SAFETY: The workspace allocation is large enough and naturally
        // aligned; writing a valid error descriptor sets up an exact backing
        // alias without creating a retained Rust reference.
        unsafe { ptr::write(aliased_error_pointer, initialized_error()) };
        let aliased_error_before = descriptor_bytes(aliased_error_pointer);
        assert_eq!(
            unsafe {
                super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_v1(
                    &system, &model, &mut workspace, &mut energy, &mut output, aliased_error_pointer,
                )
            },
            STATUS_INVALID_ARGUMENT
        );
        assert_eq!(
            descriptor_bytes(aliased_error_pointer),
            aliased_error_before
        );
        assert_eq!(workspace.state, PARTICLE_MESH_RECIPROCAL_WORKSPACE_READY);

        let mut recovered_error = initialized_error();
        assert_eq!(
            unsafe {
                super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_v1(
                    &system, &model, &mut workspace, &mut energy, &mut output, &mut recovered_error,
                )
            },
            STATUS_OK
        );
        // SAFETY: Canonical READY is exclusively owned after alias recovery.
        unsafe { super::bg_rust_particle_mesh_reciprocal_workspace_destroy_v1(&mut workspace) };
    }

    #[test]
    fn owner_neutrality_sort_scratch_cold_warm_growth_and_stateless_paths_are_frozen() {
        let position_x = [1.25, 5.1, 10.2, 15.4];
        let position_y = [2.5, 3.2, 12.3, 17.1];
        let position_z = [3.75, 8.4, 7.7, 19.3];
        let charges = [0.7, -0.4, -0.6, 0.300_000_000_000_000_04];
        let system = provider_system(&position_x, &position_y, &position_z, &charges);
        let model = provider_model([4, 8, 16]);
        let expected = evaluate(&fixture([4, 8, 16])).expect("baseline must evaluate");

        for site in [
            AllocationSite::NeutralitySort,
            AllocationSite::ParticleAssignments,
            AllocationSite::ReciprocalWorkspace,
        ] {
            let mut workspace = empty_workspace();
            let workspace_empty = descriptor_bytes(&workspace);
            let mut scratch = empty_neutrality_sort_scratch();
            let scratch_empty = descriptor_bytes(&scratch);
            let mut energy = initialized_energy(11.0);
            let mut force_x = [21.0; 4];
            let mut force_y = [22.0; 4];
            let mut force_z = [23.0; 4];
            let mut output = provider_force_output(&mut force_x, &mut force_y, &mut force_z);
            let mut error = initialized_error();
            {
                let _injection = AllocationFailureGuard::inject(site);
                // SAFETY: Valid disjoint owner-private storage exercises the
                // exact cold neutrality -> assignments -> workspace order.
                assert_eq!(
                    unsafe {
                        evaluate_with_owner_reusable_storage(
                            &system,
                            &model,
                            &mut workspace,
                            &mut scratch,
                            &mut energy,
                            &mut output,
                            &mut error,
                        )
                    },
                    STATUS_OUT_OF_MEMORY,
                    "cold allocation site {site:?}"
                );
            }
            assert_eq!(provider_error_detail(&error), site.detail());
            assert_eq!(descriptor_bytes(&workspace), workspace_empty);
            if site == AllocationSite::NeutralitySort {
                assert_eq!(descriptor_bytes(&scratch), scratch_empty);
            } else {
                assert_eq!(
                    scratch.state,
                    PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_READY
                );
                assert_eq!(scratch.length, charges.len());
            }
            assert_eq!(
                energy.reciprocal_space_kcal_per_mol.to_bits(),
                11.0_f64.to_bits()
            );
            assert_eq!(force_x, [21.0; 4]);
            assert_eq!(force_y, [22.0; 4]);
            assert_eq!(force_z, [23.0; 4]);
            // SAFETY: READY scratch, if allocated, and EMPTY workspace are
            // exclusively owned. Both destroy operations are idempotent.
            unsafe {
                super::bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_destroy_v1(
                    &mut scratch,
                );
                super::bg_rust_particle_mesh_reciprocal_workspace_destroy_v1(&mut workspace);
            }
            assert_eq!(descriptor_bytes(&scratch), scratch_empty);
            assert_eq!(descriptor_bytes(&workspace), workspace_empty);
        }

        let mut workspace = empty_workspace();
        let workspace_empty = descriptor_bytes(&workspace);
        let mut scratch = empty_neutrality_sort_scratch();
        let scratch_empty = descriptor_bytes(&scratch);
        let mut energy = initialized_energy(101.0);
        let mut force_x = [201.0; 5];
        let mut force_y = [202.0; 5];
        let mut force_z = [203.0; 5];
        force_x[4] = 301.0;
        force_y[4] = 302.0;
        force_z[4] = 303.0;
        let mut output = provider_force_output(&mut force_x, &mut force_y, &mut force_z);
        output.capacity = charges.len();
        let mut error = initialized_error();
        // SAFETY: Valid disjoint owner-private storage provisions both retained
        // allocations and writes only the first four force elements.
        assert_eq!(
            unsafe {
                evaluate_with_owner_reusable_storage(
                    &system,
                    &model,
                    &mut workspace,
                    &mut scratch,
                    &mut energy,
                    &mut output,
                    &mut error,
                )
            },
            STATUS_OK
        );
        let workspace_pointer = workspace.storage;
        let workspace_capacity = workspace.capacity;
        let scratch_pointer = scratch.storage;
        let scratch_capacity = scratch.capacity;
        assert_eq!(
            scratch.state,
            PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_READY
        );
        assert_eq!(scratch.length, charges.len());
        assert!(scratch.capacity >= scratch.length);
        assert!(!scratch.storage.is_null());
        assert_eq!(
            energy.reciprocal_space_kcal_per_mol.to_bits(),
            expected.reciprocal_space_kcal_per_mol.to_bits()
        );
        assert_eq!(force_x[4].to_bits(), 301.0_f64.to_bits());
        assert_eq!(force_y[4].to_bits(), 302.0_f64.to_bits());
        assert_eq!(force_z[4].to_bits(), 303.0_f64.to_bits());

        let mut warm_error = initialized_error();
        {
            let _injection = AllocationFailureGuard::inject(AllocationSite::NeutralitySort);
            // SAFETY: Capacity-sufficient scratch reuse must not request a
            // reserve, leaving the one-shot injection pending.
            assert_eq!(
                unsafe {
                    evaluate_with_owner_reusable_storage(
                        &system,
                        &model,
                        &mut workspace,
                        &mut scratch,
                        &mut energy,
                        &mut output,
                        &mut warm_error,
                    )
                },
                STATUS_OK
            );
            assert_injected_allocation_remains_pending(AllocationSite::NeutralitySort);
        }
        assert_eq!(workspace.storage, workspace_pointer);
        assert_eq!(workspace.capacity, workspace_capacity);
        assert_eq!(scratch.storage, scratch_pointer);
        assert_eq!(scratch.capacity, scratch_capacity);

        let workspace_before_stateless = descriptor_bytes(&workspace);
        let workspace_bits_before_stateless = workspace_storage_bits(&workspace);
        let scratch_before_stateless = descriptor_bytes(&scratch);
        let scratch_bits_before_stateless = neutrality_sort_scratch_storage_bits(&scratch);
        energy.reciprocal_space_kcal_per_mol = 401.0;
        force_x[..4].fill(501.0);
        force_y[..4].fill(502.0);
        force_z[..4].fill(503.0);
        let mut old_workspace_error = initialized_error();
        {
            let _injection = AllocationFailureGuard::inject(AllocationSite::NeutralitySort);
            // SAFETY: The predecessor workspace-only entry remains call-local
            // for neutrality sorting and must consume this injected failure.
            assert_eq!(
                unsafe {
                    super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_v1(
                        &system,
                        &model,
                        &mut workspace,
                        &mut energy,
                        &mut output,
                        &mut old_workspace_error,
                    )
                },
                STATUS_OUT_OF_MEMORY
            );
        }
        assert_eq!(
            provider_error_detail(&old_workspace_error),
            AllocationSite::NeutralitySort.detail()
        );
        assert_eq!(descriptor_bytes(&workspace), workspace_before_stateless);
        assert_eq!(
            workspace_storage_bits(&workspace),
            workspace_bits_before_stateless
        );
        assert_eq!(descriptor_bytes(&scratch), scratch_before_stateless);
        assert_eq!(
            neutrality_sort_scratch_storage_bits(&scratch),
            scratch_bits_before_stateless
        );
        assert_eq!(
            energy.reciprocal_space_kcal_per_mol.to_bits(),
            401.0_f64.to_bits()
        );
        assert_eq!(&force_x[..4], &[501.0; 4]);
        assert_eq!(&force_y[..4], &[502.0; 4]);
        assert_eq!(&force_z[..4], &[503.0; 4]);

        let mut stateless_error = initialized_error();
        {
            let _injection = AllocationFailureGuard::inject(AllocationSite::NeutralitySort);
            // SAFETY: The original direct entry also retains its call-local
            // neutrality allocation behavior.
            assert_eq!(
                unsafe {
                    super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_v1(
                        &system,
                        &model,
                        &mut energy,
                        &mut output,
                        &mut stateless_error,
                    )
                },
                STATUS_OUT_OF_MEMORY
            );
        }
        assert_eq!(
            provider_error_detail(&stateless_error),
            AllocationSite::NeutralitySort.detail()
        );
        assert_eq!(descriptor_bytes(&workspace), workspace_before_stateless);
        assert_eq!(descriptor_bytes(&scratch), scratch_before_stateless);

        let mut growth_count = scratch
            .capacity
            .checked_add(8)
            .expect("test scratch growth count must fit usize");
        if growth_count % 2 != 0 {
            growth_count += 1;
        }
        assert!(growth_count <= MAX_PARTICLE_COUNT);
        let growth_position_x: Vec<f64> = (0..growth_count)
            .map(|particle| bounded_usize_to_f64(particle) * 0.125)
            .collect();
        let growth_position_y: Vec<f64> = (0..growth_count)
            .map(|particle| bounded_usize_to_f64(particle) * 0.25)
            .collect();
        let growth_position_z: Vec<f64> = (0..growth_count)
            .map(|particle| bounded_usize_to_f64(particle) * 0.375)
            .collect();
        let growth_charges: Vec<f64> = (0..growth_count)
            .map(|particle| if particle % 2 == 0 { 1.0 } else { -1.0 })
            .collect();
        let growth_system = provider_system(
            &growth_position_x,
            &growth_position_y,
            &growth_position_z,
            &growth_charges,
        );
        let mut growth_x = vec![601.0; growth_count];
        let mut growth_y = vec![602.0; growth_count];
        let mut growth_z = vec![603.0; growth_count];
        let mut growth_output = provider_force_output(&mut growth_x, &mut growth_y, &mut growth_z);
        let retained_workspace = descriptor_bytes(&workspace);
        let retained_workspace_bits = workspace_storage_bits(&workspace);
        let retained_scratch = descriptor_bytes(&scratch);
        let retained_scratch_bits = neutrality_sort_scratch_storage_bits(&scratch);
        let mut growth_error = initialized_error();
        {
            let _injection = AllocationFailureGuard::inject(AllocationSite::NeutralitySort);
            // SAFETY: The larger valid system requires scratch growth. Reserve
            // failure must precede clear and preserve both retained owners.
            assert_eq!(
                unsafe {
                    evaluate_with_owner_reusable_storage(
                        &growth_system,
                        &model,
                        &mut workspace,
                        &mut scratch,
                        &mut energy,
                        &mut growth_output,
                        &mut growth_error,
                    )
                },
                STATUS_OUT_OF_MEMORY
            );
        }
        assert_eq!(descriptor_bytes(&workspace), retained_workspace);
        assert_eq!(workspace_storage_bits(&workspace), retained_workspace_bits);
        assert_eq!(descriptor_bytes(&scratch), retained_scratch);
        assert_eq!(
            neutrality_sort_scratch_storage_bits(&scratch),
            retained_scratch_bits
        );
        assert_eq!(growth_x, vec![601.0; growth_count]);
        assert_eq!(growth_y, vec![602.0; growth_count]);
        assert_eq!(growth_z, vec![603.0; growth_count]);

        let mut growth_error = initialized_error();
        assert_eq!(
            unsafe {
                evaluate_with_owner_reusable_storage(
                    &growth_system,
                    &model,
                    &mut workspace,
                    &mut scratch,
                    &mut energy,
                    &mut growth_output,
                    &mut growth_error,
                )
            },
            STATUS_OK
        );
        assert_eq!(scratch.length, growth_count);
        assert!(scratch.capacity >= growth_count);
        let grown_scratch_pointer = scratch.storage;
        let grown_scratch_capacity = scratch.capacity;

        // SAFETY: Only the initialized logical payload is poisoned. The next
        // prepare must clear and overwrite it without reading spare capacity.
        unsafe {
            core::slice::from_raw_parts_mut(scratch.storage.cast::<f64>(), scratch.length)
                .fill(f64::NAN);
        }
        let mut shrink_error = initialized_error();
        {
            let _injection = AllocationFailureGuard::inject(AllocationSite::NeutralitySort);
            assert_eq!(
                unsafe {
                    evaluate_with_owner_reusable_storage(
                        &system,
                        &model,
                        &mut workspace,
                        &mut scratch,
                        &mut energy,
                        &mut output,
                        &mut shrink_error,
                    )
                },
                STATUS_OK
            );
            assert_injected_allocation_remains_pending(AllocationSite::NeutralitySort);
        }
        assert_eq!(scratch.storage, grown_scratch_pointer);
        assert_eq!(scratch.capacity, grown_scratch_capacity);
        assert_eq!(scratch.length, charges.len());
        let mut expected_sorted_charges = charges;
        expected_sorted_charges.sort_unstable_by(|left, right| {
            left.abs()
                .total_cmp(&right.abs())
                .then_with(|| left.total_cmp(right))
        });
        assert_eq!(
            neutrality_sort_scratch_storage_bits(&scratch),
            expected_sorted_charges.map(f64::to_bits)
        );
        assert_eq!(
            energy.reciprocal_space_kcal_per_mol.to_bits(),
            expected.reciprocal_space_kcal_per_mol.to_bits()
        );
        for (particle, expected_force) in expected.forces_kcal_per_mol_angstrom.iter().enumerate() {
            assert_eq!(force_x[particle].to_bits(), expected_force[0].to_bits());
            assert_eq!(force_y[particle].to_bits(), expected_force[1].to_bits());
            assert_eq!(force_z[particle].to_bits(), expected_force[2].to_bits());
        }

        // SAFETY: Both canonical READY descriptors are exclusively owned.
        unsafe {
            super::bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_destroy_v1(
                &mut scratch,
            );
            super::bg_rust_particle_mesh_reciprocal_workspace_destroy_v1(&mut workspace);
        }
        assert_eq!(descriptor_bytes(&scratch), scratch_empty);
        assert_eq!(descriptor_bytes(&workspace), workspace_empty);
        // SAFETY: Repeat destruction of all-zero EMPTY descriptors is a no-op.
        unsafe {
            super::bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_destroy_v1(
                &mut scratch,
            );
            super::bg_rust_particle_mesh_reciprocal_workspace_destroy_v1(&mut workspace);
        }
        assert_eq!(descriptor_bytes(&scratch), scratch_empty);
        assert_eq!(descriptor_bytes(&workspace), workspace_empty);
    }

    #[test]
    fn owner_neutrality_sort_scratch_late_error_and_panic_restore_both_leases() {
        let position_x = [1.25, 5.1, 10.2, 15.4];
        let position_y = [2.5, 3.2, 12.3, 17.1];
        let position_z = [3.75, 8.4, 7.7, 19.3];
        let charges = [0.7, -0.4, -0.6, 0.300_000_000_000_000_04];
        let system = provider_system(&position_x, &position_y, &position_z, &charges);
        let model = provider_model([4, 8, 16]);
        let expected = evaluate(&fixture([4, 8, 16])).expect("baseline must evaluate");
        let mut workspace = empty_workspace();
        let mut scratch = empty_neutrality_sort_scratch();
        let mut energy = initialized_energy(101.0);
        let mut force_x = [201.0; 4];
        let mut force_y = [202.0; 4];
        let mut force_z = [203.0; 4];
        let mut output = provider_force_output(&mut force_x, &mut force_y, &mut force_z);
        let mut error = initialized_error();
        // SAFETY: Valid disjoint owner-private descriptors provision both
        // retained allocations before recovery paths are exercised.
        assert_eq!(
            unsafe {
                evaluate_with_owner_reusable_storage(
                    &system,
                    &model,
                    &mut workspace,
                    &mut scratch,
                    &mut energy,
                    &mut output,
                    &mut error,
                )
            },
            STATUS_OK
        );
        let workspace_pointer = workspace.storage;
        let workspace_capacity = workspace.capacity;
        let scratch_pointer = scratch.storage;
        let scratch_capacity = scratch.capacity;

        energy.reciprocal_space_kcal_per_mol = 211.0;
        force_x.fill(221.0);
        force_y.fill(222.0);
        force_z.fill(223.0);
        let mut late_error = initialized_error();
        {
            let _late = LateNonFiniteResultGuard::inject();
            // SAFETY: The injected scientific failure occurs after direct
            // force writes and must return both allocation owners to READY.
            assert_eq!(
                unsafe {
                    evaluate_with_owner_reusable_storage(
                        &system,
                        &model,
                        &mut workspace,
                        &mut scratch,
                        &mut energy,
                        &mut output,
                        &mut late_error,
                    )
                },
                STATUS_NUMERICAL_ERROR
            );
        }
        assert_eq!(
            late_error.typed_code,
            ParticleMeshReciprocalErrorCodeV1::NonFiniteResult as i32
        );
        assert_eq!(workspace.state, PARTICLE_MESH_RECIPROCAL_WORKSPACE_READY);
        assert_eq!(workspace.storage, workspace_pointer);
        assert_eq!(workspace.capacity, workspace_capacity);
        assert_eq!(
            scratch.state,
            PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_READY
        );
        assert_eq!(scratch.storage, scratch_pointer);
        assert_eq!(scratch.capacity, scratch_capacity);
        assert_eq!(
            energy.reciprocal_space_kcal_per_mol.to_bits(),
            211.0_f64.to_bits()
        );
        assert_ne!(force_x, [221.0; 4]);
        assert_ne!(force_y, [222.0; 4]);
        assert_ne!(force_z, [223.0; 4]);

        let mut recovery_error = initialized_error();
        assert_eq!(
            unsafe {
                evaluate_with_owner_reusable_storage(
                    &system,
                    &model,
                    &mut workspace,
                    &mut scratch,
                    &mut energy,
                    &mut output,
                    &mut recovery_error,
                )
            },
            STATUS_OK
        );
        assert_eq!(
            energy.reciprocal_space_kcal_per_mol.to_bits(),
            expected.reciprocal_space_kcal_per_mol.to_bits()
        );

        energy.reciprocal_space_kcal_per_mol = 301.0;
        force_x.fill(401.0);
        force_y.fill(402.0);
        force_z.fill(403.0);
        let mut panic_error = initialized_error();
        {
            let _panic = ReusableWorkspacePanicGuard::inject();
            // SAFETY: The test panic fires after neutrality sorting, assignment
            // allocation, and reciprocal workspace preparation, but before any
            // direct caller force write.
            assert_eq!(
                unsafe {
                    evaluate_with_owner_reusable_storage(
                        &system,
                        &model,
                        &mut workspace,
                        &mut scratch,
                        &mut energy,
                        &mut output,
                        &mut panic_error,
                    )
                },
                STATUS_INTERNAL_ERROR
            );
        }
        assert_eq!(
            provider_error_detail(&panic_error),
            "rust particle-mesh reciprocal provider panicked"
        );
        assert_eq!(workspace.state, PARTICLE_MESH_RECIPROCAL_WORKSPACE_READY);
        assert_eq!(workspace.storage, workspace_pointer);
        assert_eq!(workspace.capacity, workspace_capacity);
        assert_eq!(
            scratch.state,
            PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_READY
        );
        assert_eq!(scratch.storage, scratch_pointer);
        assert_eq!(scratch.capacity, scratch_capacity);
        assert_eq!(
            energy.reciprocal_space_kcal_per_mol.to_bits(),
            301.0_f64.to_bits()
        );
        assert_eq!(force_x, [401.0; 4]);
        assert_eq!(force_y, [402.0; 4]);
        assert_eq!(force_z, [403.0; 4]);

        let mut final_error = initialized_error();
        assert_eq!(
            unsafe {
                evaluate_with_owner_reusable_storage(
                    &system,
                    &model,
                    &mut workspace,
                    &mut scratch,
                    &mut energy,
                    &mut output,
                    &mut final_error,
                )
            },
            STATUS_OK
        );
        assert_eq!(
            energy.reciprocal_space_kcal_per_mol.to_bits(),
            expected.reciprocal_space_kcal_per_mol.to_bits()
        );
        // SAFETY: Both recovered canonical READY descriptors are exclusively
        // owned by this test.
        unsafe {
            super::bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_destroy_v1(
                &mut scratch,
            );
            super::bg_rust_particle_mesh_reciprocal_workspace_destroy_v1(&mut workspace);
        }
    }

    #[test]
    fn owner_neutrality_sort_scratch_malformed_busy_type_and_cross_aliases_fail_closed() {
        // SAFETY: Null destruction is explicitly an idempotent no-op.
        unsafe {
            super::bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_destroy_v1(
                ptr::null_mut(),
            );
        }
        let position_x = [1.25, 5.1, 10.2, 15.4];
        let position_y = [2.5, 3.2, 12.3, 17.1];
        let position_z = [3.75, 8.4, 7.7, 19.3];
        let charges = [0.7, -0.4, -0.6, 0.300_000_000_000_000_04];
        let system = provider_system(&position_x, &position_y, &position_z, &charges);
        let model = provider_model([4; 3]);
        let mut energy = initialized_energy(101.0);
        let mut force_x = [201.0; 4];
        let mut force_y = [202.0; 4];
        let mut force_z = [203.0; 4];
        let mut output = provider_force_output(&mut force_x, &mut force_y, &mut force_z);

        let mut null_workspace = empty_workspace();
        let null_workspace_before = descriptor_bytes(&null_workspace);
        let mut null_error = initialized_error();
        let null_error_before = descriptor_bytes(&null_error);
        // SAFETY: A null neutrality descriptor is deliberately invalid and
        // must fail before either descriptor can be leased or error written.
        assert_eq!(
            unsafe {
                evaluate_with_owner_reusable_storage(
                    &system,
                    &model,
                    &mut null_workspace,
                    ptr::null_mut(),
                    &mut energy,
                    &mut output,
                    &mut null_error,
                )
            },
            STATUS_INVALID_ARGUMENT
        );
        assert_eq!(descriptor_bytes(&null_workspace), null_workspace_before);
        assert_eq!(descriptor_bytes(&null_error), null_error_before);

        let mut misaligned_storage = [0_u8; size_of::<f64>() + align_of::<f64>()];
        let misaligned_offset = (0..align_of::<f64>())
            .find(|offset| (misaligned_storage.as_ptr() as usize + offset) % align_of::<f64>() != 0)
            .expect("f64 alignment has a misaligned byte offset");
        // SAFETY: The offset remains inside local storage; only raw range
        // validation observes this deliberately misaligned address.
        let misaligned_pointer = unsafe {
            misaligned_storage
                .as_mut_ptr()
                .add(misaligned_offset)
                .cast::<c_void>()
        };
        let oversized_capacity = (isize::MAX as usize) / size_of::<f64>() + 1;
        let malformed_cases = [
            ParticleMeshReciprocalNeutralitySortScratchV1 {
                struct_size: 1,
                ..empty_neutrality_sort_scratch()
            },
            canonical_neutrality_sort_scratch_descriptor(
                PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_READY,
                ptr::null_mut(),
                0,
                1,
            ),
            ParticleMeshReciprocalNeutralitySortScratchV1 {
                length: 1,
                ..canonical_neutrality_sort_scratch_descriptor(
                    PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_READY,
                    ptr::null_mut(),
                    0,
                    0,
                )
            },
            ParticleMeshReciprocalNeutralitySortScratchV1 {
                reserved: [1, 0, 0, 0],
                ..canonical_neutrality_sort_scratch_descriptor(
                    PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_READY,
                    ptr::null_mut(),
                    0,
                    0,
                )
            },
            canonical_neutrality_sort_scratch_descriptor(0x554e_4b4e, ptr::null_mut(), 0, 0),
            canonical_neutrality_sort_scratch_descriptor(
                PARTICLE_MESH_RECIPROCAL_WORKSPACE_READY,
                ptr::null_mut(),
                0,
                0,
            ),
            canonical_neutrality_sort_scratch_descriptor(
                PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_READY,
                misaligned_pointer,
                1,
                1,
            ),
            canonical_neutrality_sort_scratch_descriptor(
                PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_READY,
                ptr::dangling::<f64>().cast_mut().cast::<c_void>(),
                1,
                oversized_capacity,
            ),
        ];
        for mut scratch in malformed_cases {
            let mut workspace = empty_workspace();
            let workspace_before = descriptor_bytes(&workspace);
            let scratch_before = descriptor_bytes(&scratch);
            let mut error = initialized_error();
            let error_before = descriptor_bytes(&error);
            // SAFETY: Each live descriptor is deliberately malformed. Full
            // preflight must neither lease/free it nor write error storage
            // before a claimed backing range is proven safe.
            assert_ne!(
                unsafe {
                    evaluate_with_owner_reusable_storage(
                        &system,
                        &model,
                        &mut workspace,
                        &mut scratch,
                        &mut energy,
                        &mut output,
                        &mut error,
                    )
                },
                STATUS_OK
            );
            assert_eq!(descriptor_bytes(&workspace), workspace_before);
            assert_eq!(descriptor_bytes(&scratch), scratch_before);
            assert_eq!(descriptor_bytes(&error), error_before);
            // SAFETY: Malformed descriptors are fail-closed destroy no-ops.
            unsafe {
                super::bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_destroy_v1(
                    &mut scratch,
                );
            }
            assert_eq!(descriptor_bytes(&scratch), scratch_before);
        }

        let mut swapped_workspace = canonical_workspace_descriptor(
            PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_READY,
            ptr::null_mut(),
            0,
            0,
        );
        let swapped_workspace_before = descriptor_bytes(&swapped_workspace);
        let mut empty_scratch = empty_neutrality_sort_scratch();
        let mut swap_error = initialized_error();
        let swap_error_before = descriptor_bytes(&swap_error);
        // SAFETY: The reciprocal descriptor deliberately carries the distinct
        // NSS1 type tag and must be rejected before either lease.
        assert_eq!(
            unsafe {
                evaluate_with_owner_reusable_storage(
                    &system,
                    &model,
                    &mut swapped_workspace,
                    &mut empty_scratch,
                    &mut energy,
                    &mut output,
                    &mut swap_error,
                )
            },
            STATUS_ABI_MISMATCH
        );
        assert_eq!(
            descriptor_bytes(&swapped_workspace),
            swapped_workspace_before
        );
        assert_eq!(descriptor_bytes(&swap_error), swap_error_before);
        // SAFETY: A reciprocal descriptor with a neutrality tag is malformed
        // and therefore a destroy no-op.
        unsafe {
            super::bg_rust_particle_mesh_reciprocal_workspace_destroy_v1(&mut swapped_workspace);
        }
        assert_eq!(
            descriptor_bytes(&swapped_workspace),
            swapped_workspace_before
        );

        let mut zero_capacity_ready = canonical_neutrality_sort_scratch_descriptor(
            PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_READY,
            ptr::null_mut(),
            0,
            0,
        );
        // SAFETY: Canonical zero-capacity READY owns no allocation and destroy
        // still transitions it exactly to all-zero EMPTY.
        unsafe {
            super::bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_destroy_v1(
                &mut zero_capacity_ready,
            );
        }
        assert_eq!(
            descriptor_bytes(&zero_capacity_ready),
            descriptor_bytes(&empty_neutrality_sort_scratch())
        );

        let mut busy_workspace = empty_workspace();
        let mut busy_scratch = canonical_neutrality_sort_scratch_descriptor(
            PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_LEASED,
            ptr::null_mut(),
            0,
            0,
        );
        let busy_before = descriptor_bytes(&busy_scratch);
        let mut busy_error = initialized_error();
        // SAFETY: Canonical LEASED is deliberately busy and all surrounding
        // regions are valid and disjoint, permitting a diagnostic write.
        assert_eq!(
            unsafe {
                evaluate_with_owner_reusable_storage(
                    &system,
                    &model,
                    &mut busy_workspace,
                    &mut busy_scratch,
                    &mut energy,
                    &mut output,
                    &mut busy_error,
                )
            },
            STATUS_INVALID_ARGUMENT
        );
        assert_eq!(
            provider_error_detail(&busy_error),
            "neutrality sort scratch is already leased"
        );
        assert_eq!(descriptor_bytes(&busy_scratch), busy_before);
        // SAFETY: LEASED is intentionally a destroy no-op.
        unsafe {
            super::bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_destroy_v1(
                &mut busy_scratch,
            );
        }
        assert_eq!(descriptor_bytes(&busy_scratch), busy_before);

        let mut shared_descriptor = empty_workspace();
        let shared_before = descriptor_bytes(&shared_descriptor);
        let mut shared_error = initialized_error();
        // SAFETY: Both typed pointers deliberately designate the same all-zero
        // 72-byte descriptor. Pairwise descriptor preflight must reject it
        // before either ownership lease.
        assert_eq!(
            unsafe {
                evaluate_with_owner_reusable_storage(
                    &system,
                    &model,
                    &mut shared_descriptor,
                    (&mut shared_descriptor as *mut ParticleMeshReciprocalWorkspaceV1)
                        .cast::<ParticleMeshReciprocalNeutralitySortScratchV1>(),
                    &mut energy,
                    &mut output,
                    &mut shared_error,
                )
            },
            STATUS_INVALID_ARGUMENT
        );
        assert_eq!(descriptor_bytes(&shared_descriptor), shared_before);

        let large_count = 32_usize;
        let large_position_x: Vec<f64> = (0..large_count)
            .map(|particle| bounded_usize_to_f64(particle) * 0.125)
            .collect();
        let large_position_y: Vec<f64> = (0..large_count)
            .map(|particle| bounded_usize_to_f64(particle) * 0.25)
            .collect();
        let large_position_z: Vec<f64> = (0..large_count)
            .map(|particle| bounded_usize_to_f64(particle) * 0.375)
            .collect();
        let large_charges: Vec<f64> = (0..large_count)
            .map(|particle| if particle % 2 == 0 { 1.0 } else { -1.0 })
            .collect();
        let large_system = provider_system(
            &large_position_x,
            &large_position_y,
            &large_position_z,
            &large_charges,
        );
        let mut large_x = vec![0.0; large_count];
        let mut large_y = vec![0.0; large_count];
        let mut large_z = vec![0.0; large_count];
        let mut large_output = provider_force_output(&mut large_x, &mut large_y, &mut large_z);
        let mut workspace = empty_workspace();
        let mut scratch = empty_neutrality_sort_scratch();
        let mut large_error = initialized_error();
        // SAFETY: Valid large channels establish at least 32 initialized
        // logical scratch elements and a retained reciprocal allocation.
        assert_eq!(
            unsafe {
                evaluate_with_owner_reusable_storage(
                    &large_system,
                    &model,
                    &mut workspace,
                    &mut scratch,
                    &mut energy,
                    &mut large_output,
                    &mut large_error,
                )
            },
            STATUS_OK
        );
        assert!(
            scratch.length >= size_of::<ParticleMeshReciprocalWorkspaceV1>() / size_of::<f64>()
        );
        let scratch_before_descriptor_alias = descriptor_bytes(&scratch);
        let scratch_before_descriptor_alias_bits = neutrality_sort_scratch_storage_bits(&scratch);
        let mut descriptor_alias_error = initialized_error();
        let descriptor_alias_error_before = descriptor_bytes(&descriptor_alias_error);
        // SAFETY: The complete workspace-sized prefix lies inside initialized
        // logical f64 storage. Its bytes are deliberately not a canonical
        // workspace descriptor and must be rejected without taking either
        // lease or retaining a typed reference into scratch storage.
        assert_ne!(
            unsafe {
                evaluate_with_owner_reusable_storage(
                    &large_system,
                    &model,
                    scratch.storage.cast::<ParticleMeshReciprocalWorkspaceV1>(),
                    &mut scratch,
                    &mut energy,
                    &mut large_output,
                    &mut descriptor_alias_error,
                )
            },
            STATUS_OK
        );
        assert_eq!(
            descriptor_bytes(&descriptor_alias_error),
            descriptor_alias_error_before
        );
        assert_eq!(descriptor_bytes(&scratch), scratch_before_descriptor_alias);
        assert_eq!(
            neutrality_sort_scratch_storage_bits(&scratch),
            scratch_before_descriptor_alias_bits
        );

        let workspace_before_cross = descriptor_bytes(&workspace);
        let workspace_bits_before_cross = workspace_storage_bits(&workspace);
        let scratch_before_cross = descriptor_bytes(&scratch);
        let scratch_bits_before_cross = neutrality_sort_scratch_storage_bits(&scratch);
        let mut forged_scratch = canonical_neutrality_sort_scratch_descriptor(
            PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_READY,
            workspace.storage,
            1,
            1,
        );
        let forged_scratch_before = descriptor_bytes(&forged_scratch);
        let mut cross_error = initialized_error();
        // SAFETY: The forged scratch backing deliberately overlaps the complete
        // reciprocal allocation. Pairwise full-capacity preflight rejects it
        // before reconstructing either Vec.
        assert_eq!(
            unsafe {
                evaluate_with_owner_reusable_storage(
                    &large_system,
                    &model,
                    &mut workspace,
                    &mut forged_scratch,
                    &mut energy,
                    &mut large_output,
                    &mut cross_error,
                )
            },
            STATUS_INVALID_ARGUMENT
        );
        assert_eq!(descriptor_bytes(&workspace), workspace_before_cross);
        assert_eq!(
            workspace_storage_bits(&workspace),
            workspace_bits_before_cross
        );
        assert_eq!(descriptor_bytes(&forged_scratch), forged_scratch_before);

        let mut forged_workspace = canonical_workspace_descriptor(
            PARTICLE_MESH_RECIPROCAL_WORKSPACE_READY,
            scratch.storage,
            1,
            1,
        );
        let forged_workspace_before = descriptor_bytes(&forged_workspace);
        let mut reverse_cross_error = initialized_error();
        // SAFETY: The forged reciprocal backing deliberately overlaps the
        // complete neutrality allocation and is rejected before either lease.
        assert_eq!(
            unsafe {
                evaluate_with_owner_reusable_storage(
                    &large_system,
                    &model,
                    &mut forged_workspace,
                    &mut scratch,
                    &mut energy,
                    &mut large_output,
                    &mut reverse_cross_error,
                )
            },
            STATUS_INVALID_ARGUMENT
        );
        assert_eq!(descriptor_bytes(&forged_workspace), forged_workspace_before);
        assert_eq!(descriptor_bytes(&scratch), scratch_before_cross);
        assert_eq!(
            neutrality_sort_scratch_storage_bits(&scratch),
            scratch_bits_before_cross
        );

        let mut shrink_error = initialized_error();
        assert_eq!(
            unsafe {
                evaluate_with_owner_reusable_storage(
                    &system,
                    &model,
                    &mut workspace,
                    &mut scratch,
                    &mut energy,
                    &mut output,
                    &mut shrink_error,
                )
            },
            STATUS_OK
        );
        assert_eq!(scratch.length, charges.len());
        assert!(scratch.capacity >= large_count);
        assert!(scratch.capacity - scratch.length >= charges.len());
        let workspace_before_tail = descriptor_bytes(&workspace);
        let scratch_before_tail = descriptor_bytes(&scratch);
        let scratch_bits_before_tail = neutrality_sort_scratch_storage_bits(&scratch);
        // SAFETY: Only the raw address of spare capacity is formed. The call
        // must reject the full-capacity overlap before a slice, read, or write
        // can touch the capacity tail.
        let capacity_tail = unsafe { scratch.storage.cast::<f64>().add(scratch.length) };
        let mut tail_y = [701.0; 4];
        let mut tail_z = [702.0; 4];
        let mut tail_output = ParticleMeshReciprocalForceOutputV1 {
            struct_size: u32::try_from(size_of::<ParticleMeshReciprocalForceOutputV1>()).unwrap(),
            abi_version: PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION,
            capacity: charges.len(),
            x: capacity_tail,
            y: tail_y.as_mut_ptr(),
            z: tail_z.as_mut_ptr(),
            reserved: [0; 4],
        };
        let mut tail_error = initialized_error();
        assert_eq!(
            unsafe {
                evaluate_with_owner_reusable_storage(
                    &system,
                    &model,
                    &mut workspace,
                    &mut scratch,
                    &mut energy,
                    &mut tail_output,
                    &mut tail_error,
                )
            },
            STATUS_INVALID_ARGUMENT
        );
        assert_eq!(descriptor_bytes(&workspace), workspace_before_tail);
        assert_eq!(descriptor_bytes(&scratch), scratch_before_tail);
        assert_eq!(
            neutrality_sort_scratch_storage_bits(&scratch),
            scratch_bits_before_tail
        );
        assert_eq!(tail_y, [701.0; 4]);
        assert_eq!(tail_z, [702.0; 4]);

        // SAFETY: Only the two actual canonical READY descriptors own their
        // allocations. Forged descriptors were never leased or destroyed.
        unsafe {
            super::bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_destroy_v1(
                &mut scratch,
            );
            super::bg_rust_particle_mesh_reciprocal_workspace_destroy_v1(&mut workspace);
        }
    }

    #[test]
    fn owner_particle_assignment_scratch_cold_warm_growth_overwrite_and_routes_are_frozen() {
        let position_x = [1.25, 5.1, 10.2, 15.4];
        let position_y = [2.5, 3.2, 12.3, 17.1];
        let position_z = [3.75, 8.4, 7.7, 19.3];
        let charges = [0.7, -0.4, -0.6, 0.300_000_000_000_000_04];
        let system = provider_system(&position_x, &position_y, &position_z, &charges);
        let model = provider_model([4, 8, 16]);

        for site in [
            AllocationSite::NeutralitySort,
            AllocationSite::ParticleAssignments,
            AllocationSite::ReciprocalWorkspace,
        ] {
            let mut workspace = empty_workspace();
            let workspace_empty = descriptor_bytes(&workspace);
            let mut neutrality = empty_neutrality_sort_scratch();
            let neutrality_empty = descriptor_bytes(&neutrality);
            let mut assignments = empty_particle_assignment_scratch();
            let assignments_empty = descriptor_bytes(&assignments);
            let mut energy = initialized_energy(11.0);
            let mut force_x = [21.0; 4];
            let mut force_y = [22.0; 4];
            let mut force_z = [23.0; 4];
            let mut output = provider_force_output(&mut force_x, &mut force_y, &mut force_z);
            let mut error = initialized_error();
            {
                let _injection = AllocationFailureGuard::inject(site);
                // SAFETY: Valid disjoint EMPTY descriptors exercise the frozen
                // neutrality -> assignments -> reciprocal allocation order.
                assert_eq!(
                    unsafe {
                        evaluate_with_all_owner_reusable_storage(
                            &system,
                            &model,
                            &mut workspace,
                            &mut neutrality,
                            &mut assignments,
                            &mut energy,
                            &mut output,
                            &mut error,
                        )
                    },
                    STATUS_OUT_OF_MEMORY,
                    "cold allocation site {site:?}"
                );
            }
            assert_eq!(provider_error_detail(&error), site.detail());
            assert_eq!(descriptor_bytes(&workspace), workspace_empty);
            if site == AllocationSite::NeutralitySort {
                assert_eq!(descriptor_bytes(&neutrality), neutrality_empty);
            } else {
                assert_eq!(
                    neutrality.state,
                    PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_READY
                );
                assert_eq!(neutrality.length, charges.len());
            }
            if site == AllocationSite::ReciprocalWorkspace {
                assert_eq!(
                    assignments.state,
                    PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_READY
                );
                assert_eq!(
                    assignments.logical_length_bytes,
                    charges.len() * size_of::<ParticleAssignment>()
                );
            } else {
                assert_eq!(descriptor_bytes(&assignments), assignments_empty);
            }
            assert_eq!(
                energy.reciprocal_space_kcal_per_mol.to_bits(),
                11.0_f64.to_bits()
            );
            assert_eq!(force_x, [21.0; 4]);
            assert_eq!(force_y, [22.0; 4]);
            assert_eq!(force_z, [23.0; 4]);
            // SAFETY: Every canonical READY allocation, if any, is exclusively
            // owned; EMPTY destruction is an idempotent no-op.
            unsafe {
                super::bg_rust_particle_mesh_reciprocal_particle_assignment_scratch_destroy_v1(
                    &mut assignments,
                );
                super::bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_destroy_v1(
                    &mut neutrality,
                );
                super::bg_rust_particle_mesh_reciprocal_workspace_destroy_v1(&mut workspace);
            }
            assert_eq!(descriptor_bytes(&workspace), workspace_empty);
            assert_eq!(descriptor_bytes(&neutrality), neutrality_empty);
            assert_eq!(descriptor_bytes(&assignments), assignments_empty);
        }

        let expected = evaluate(&fixture([4, 8, 16])).expect("baseline must evaluate");
        let mut workspace = empty_workspace();
        let workspace_empty = descriptor_bytes(&workspace);
        let mut neutrality = empty_neutrality_sort_scratch();
        let neutrality_empty = descriptor_bytes(&neutrality);
        let mut assignments = empty_particle_assignment_scratch();
        let assignments_empty = descriptor_bytes(&assignments);
        let mut energy = initialized_energy(101.0);
        let mut force_x = [201.0; 5];
        let mut force_y = [202.0; 5];
        let mut force_z = [203.0; 5];
        force_x[4] = 301.0;
        force_y[4] = 302.0;
        force_z[4] = 303.0;
        let mut output = provider_force_output(&mut force_x, &mut force_y, &mut force_z);
        output.capacity = charges.len();
        let mut error = initialized_error();
        {
            let _injection =
                AllocationFailureGuard::inject_at(AllocationSite::ParticleAssignments, 2);
            // SAFETY: All descriptors/channels are valid, disjoint, and
            // exclusively owned. Only the first four forces are writable. A
            // second matching reserve would fail, freezing one cold occurrence.
            assert_eq!(
                unsafe {
                    evaluate_with_all_owner_reusable_storage(
                        &system,
                        &model,
                        &mut workspace,
                        &mut neutrality,
                        &mut assignments,
                        &mut energy,
                        &mut output,
                        &mut error,
                    )
                },
                STATUS_OK
            );
            assert_injected_allocation_remains_pending(AllocationSite::ParticleAssignments);
        }
        let assignment_pointer = assignments.storage;
        let assignment_capacity_bytes = assignments.allocation_capacity_bytes;
        assert_eq!(
            assignments.state,
            PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_READY
        );
        assert_eq!(
            assignments.logical_length_bytes,
            charges.len() * size_of::<ParticleAssignment>()
        );
        assert!(assignments.allocation_capacity_bytes >= assignments.logical_length_bytes);
        assert!(!assignments.storage.is_null());
        assert_eq!(
            energy.reciprocal_space_kcal_per_mol.to_bits(),
            expected.reciprocal_space_kcal_per_mol.to_bits()
        );
        for particle in 0..charges.len() {
            assert_eq!(
                [
                    force_x[particle].to_bits(),
                    force_y[particle].to_bits(),
                    force_z[particle].to_bits(),
                ],
                expected.forces_kcal_per_mol_angstrom[particle].map(f64::to_bits)
            );
        }
        assert_eq!(force_x[4].to_bits(), 301.0_f64.to_bits());
        assert_eq!(force_y[4].to_bits(), 302.0_f64.to_bits());
        assert_eq!(force_z[4].to_bits(), 303.0_f64.to_bits());

        let mut warm_error = initialized_error();
        {
            let _injection = AllocationFailureGuard::inject(AllocationSite::ParticleAssignments);
            // SAFETY: Capacity-sufficient assignment reuse must not reserve and
            // therefore leaves the one-shot assignment failure pending.
            assert_eq!(
                unsafe {
                    evaluate_with_all_owner_reusable_storage(
                        &system,
                        &model,
                        &mut workspace,
                        &mut neutrality,
                        &mut assignments,
                        &mut energy,
                        &mut output,
                        &mut warm_error,
                    )
                },
                STATUS_OK
            );
            assert_injected_allocation_remains_pending(AllocationSite::ParticleAssignments);
        }
        assert_eq!(assignments.storage, assignment_pointer);
        assert_eq!(
            assignments.allocation_capacity_bytes,
            assignment_capacity_bytes
        );

        let poison = assignment(
            Position::new(17.25, 19.5, 21.75),
            OrthorhombicCell {
                lengths_angstrom: [18.0, 20.0, 22.0],
            },
            [4, 8, 16],
        );
        // SAFETY: The canonical READY descriptor exposes exactly four fully
        // initialized ParticleAssignment elements; this test poisons only them.
        unsafe {
            core::slice::from_raw_parts_mut(
                assignments.storage.cast::<ParticleAssignment>(),
                charges.len(),
            )
            .fill(poison);
        }
        let poison_bits = particle_assignment_scratch_storage_bits(&assignments);
        let changed_position_x = [1.75, 5.6, 10.7, 15.9];
        let changed_position_y = [2.75, 3.45, 12.55, 17.35];
        let changed_position_z = [3.5, 8.15, 7.45, 19.05];
        let changed_system = provider_system(
            &changed_position_x,
            &changed_position_y,
            &changed_position_z,
            &charges,
        );
        let mut changed_input = fixture([4, 8, 16]);
        changed_input.positions = (0..charges.len())
            .map(|particle| {
                Position::new(
                    changed_position_x[particle],
                    changed_position_y[particle],
                    changed_position_z[particle],
                )
            })
            .collect();
        let changed_expected = evaluate(&changed_input).expect("changed input must evaluate");
        let expected_assignments: Vec<_> = changed_input
            .positions
            .iter()
            .copied()
            .map(|position| assignment(position, changed_input.cell, [4, 8, 16]))
            .collect();
        let mut changed_error = initialized_error();
        // SAFETY: Warm scratch is canonical READY. Prepare must clear and
        // recompute every assignment from the changed particle order.
        assert_eq!(
            unsafe {
                evaluate_with_all_owner_reusable_storage(
                    &changed_system,
                    &model,
                    &mut workspace,
                    &mut neutrality,
                    &mut assignments,
                    &mut energy,
                    &mut output,
                    &mut changed_error,
                )
            },
            STATUS_OK
        );
        let changed_bits = particle_assignment_scratch_storage_bits(&assignments);
        assert_ne!(changed_bits, poison_bits);
        assert_eq!(
            changed_bits,
            particle_assignment_bits(&expected_assignments)
        );
        assert_eq!(
            energy.reciprocal_space_kcal_per_mol.to_bits(),
            changed_expected.reciprocal_space_kcal_per_mol.to_bits()
        );
        for particle in 0..charges.len() {
            assert_eq!(
                [
                    force_x[particle].to_bits(),
                    force_y[particle].to_bits(),
                    force_z[particle].to_bits(),
                ],
                changed_expected.forces_kcal_per_mol_angstrom[particle].map(f64::to_bits)
            );
        }

        let large_count = 32_usize;
        let large_position_x: Vec<f64> = (0..large_count)
            .map(|particle| bounded_usize_to_f64(particle) * 0.125)
            .collect();
        let large_position_y: Vec<f64> = (0..large_count)
            .map(|particle| bounded_usize_to_f64(particle) * 0.25)
            .collect();
        let large_position_z: Vec<f64> = (0..large_count)
            .map(|particle| bounded_usize_to_f64(particle) * 0.375)
            .collect();
        let large_charges: Vec<f64> = (0..large_count)
            .map(|particle| if particle % 2 == 0 { 1.0 } else { -1.0 })
            .collect();
        let large_system = provider_system(
            &large_position_x,
            &large_position_y,
            &large_position_z,
            &large_charges,
        );
        let mut large_x = vec![401.0; large_count];
        let mut large_y = vec![402.0; large_count];
        let mut large_z = vec![403.0; large_count];
        let mut large_output = provider_force_output(&mut large_x, &mut large_y, &mut large_z);
        let assignment_before_growth = descriptor_bytes(&assignments);
        let assignment_bits_before_growth = particle_assignment_scratch_storage_bits(&assignments);
        let workspace_before_growth = descriptor_bytes(&workspace);
        let mut growth_error = initialized_error();
        {
            let _injection = AllocationFailureGuard::inject(AllocationSite::ParticleAssignments);
            // SAFETY: Neutrality growth succeeds first; assignment reserve then
            // fails before clear, retaining its prior logical payload exactly.
            assert_eq!(
                unsafe {
                    evaluate_with_all_owner_reusable_storage(
                        &large_system,
                        &model,
                        &mut workspace,
                        &mut neutrality,
                        &mut assignments,
                        &mut energy,
                        &mut large_output,
                        &mut growth_error,
                    )
                },
                STATUS_OUT_OF_MEMORY
            );
        }
        assert_eq!(
            provider_error_detail(&growth_error),
            AllocationSite::ParticleAssignments.detail()
        );
        assert_eq!(neutrality.length, large_count);
        assert!(neutrality.capacity >= large_count);
        assert_eq!(descriptor_bytes(&assignments), assignment_before_growth);
        assert_eq!(
            particle_assignment_scratch_storage_bits(&assignments),
            assignment_bits_before_growth
        );
        assert_eq!(descriptor_bytes(&workspace), workspace_before_growth);
        assert_eq!(large_x, vec![401.0; large_count]);
        assert_eq!(large_y, vec![402.0; large_count]);
        assert_eq!(large_z, vec![403.0; large_count]);

        let mut growth_recovery_error = initialized_error();
        // SAFETY: All three canonical descriptors recover after the injected
        // reserve failure and may grow to the larger input.
        assert_eq!(
            unsafe {
                evaluate_with_all_owner_reusable_storage(
                    &large_system,
                    &model,
                    &mut workspace,
                    &mut neutrality,
                    &mut assignments,
                    &mut energy,
                    &mut large_output,
                    &mut growth_recovery_error,
                )
            },
            STATUS_OK
        );
        assert_eq!(
            assignments.logical_length_bytes,
            large_count * size_of::<ParticleAssignment>()
        );
        assert!(assignments.allocation_capacity_bytes >= assignments.logical_length_bytes);
        assert!(assignments.allocation_capacity_bytes > assignment_capacity_bytes);

        let mut shrink_error = initialized_error();
        assert_eq!(
            unsafe {
                evaluate_with_all_owner_reusable_storage(
                    &system,
                    &model,
                    &mut workspace,
                    &mut neutrality,
                    &mut assignments,
                    &mut energy,
                    &mut output,
                    &mut shrink_error,
                )
            },
            STATUS_OK
        );
        let assignment_before_old_routes = descriptor_bytes(&assignments);
        let assignment_bits_before_old_routes =
            particle_assignment_scratch_storage_bits(&assignments);
        for route in 0..3 {
            let mut route_error = initialized_error();
            let status = {
                let _injection =
                    AllocationFailureGuard::inject(AllocationSite::ParticleAssignments);
                // SAFETY: Every legacy route receives valid storage but no
                // assignment descriptor, so its local allocation must fail.
                unsafe {
                    match route {
                        0 => super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_v1(
                            &system,
                            &model,
                            &mut energy,
                            &mut output,
                            &mut route_error,
                        ),
                        1 => super::bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_v1(
                            &system,
                            &model,
                            &mut workspace,
                            &mut energy,
                            &mut output,
                            &mut route_error,
                        ),
                        _ => evaluate_with_owner_reusable_storage(
                            &system,
                            &model,
                            &mut workspace,
                            &mut neutrality,
                            &mut energy,
                            &mut output,
                            &mut route_error,
                        ),
                    }
                }
            };
            assert_eq!(status, STATUS_OUT_OF_MEMORY, "legacy route {route}");
            assert_eq!(
                provider_error_detail(&route_error),
                AllocationSite::ParticleAssignments.detail()
            );
            assert_eq!(descriptor_bytes(&assignments), assignment_before_old_routes);
            assert_eq!(
                particle_assignment_scratch_storage_bits(&assignments),
                assignment_bits_before_old_routes
            );
        }

        // SAFETY: Canonical READY descriptors are exclusively owned. Repeated
        // destroys verify exact all-zero EMPTY idempotence.
        unsafe {
            super::bg_rust_particle_mesh_reciprocal_particle_assignment_scratch_destroy_v1(
                &mut assignments,
            );
            super::bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_destroy_v1(
                &mut neutrality,
            );
            super::bg_rust_particle_mesh_reciprocal_workspace_destroy_v1(&mut workspace);
        }
        assert_eq!(descriptor_bytes(&assignments), assignments_empty);
        assert_eq!(descriptor_bytes(&neutrality), neutrality_empty);
        assert_eq!(descriptor_bytes(&workspace), workspace_empty);
        unsafe {
            super::bg_rust_particle_mesh_reciprocal_particle_assignment_scratch_destroy_v1(
                &mut assignments,
            );
            super::bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_destroy_v1(
                &mut neutrality,
            );
            super::bg_rust_particle_mesh_reciprocal_workspace_destroy_v1(&mut workspace);
        }
        assert_eq!(descriptor_bytes(&assignments), assignments_empty);
        assert_eq!(descriptor_bytes(&neutrality), neutrality_empty);
        assert_eq!(descriptor_bytes(&workspace), workspace_empty);
    }

    #[test]
    fn owner_particle_assignment_scratch_late_error_and_panic_restore_three_leases() {
        let position_x = [1.25, 5.1, 10.2, 15.4];
        let position_y = [2.5, 3.2, 12.3, 17.1];
        let position_z = [3.75, 8.4, 7.7, 19.3];
        let charges = [0.7, -0.4, -0.6, 0.300_000_000_000_000_04];
        let system = provider_system(&position_x, &position_y, &position_z, &charges);
        let model = provider_model([4, 8, 16]);
        let mut workspace = empty_workspace();
        let mut neutrality = empty_neutrality_sort_scratch();
        let mut assignments = empty_particle_assignment_scratch();
        let mut energy = initialized_energy(101.0);
        let mut force_x = [201.0; 4];
        let mut force_y = [202.0; 4];
        let mut force_z = [203.0; 4];
        let mut output = provider_force_output(&mut force_x, &mut force_y, &mut force_z);
        let mut error = initialized_error();
        // SAFETY: Valid disjoint EMPTY descriptors establish all three retained
        // allocations before late-failure restoration checks.
        assert_eq!(
            unsafe {
                evaluate_with_all_owner_reusable_storage(
                    &system,
                    &model,
                    &mut workspace,
                    &mut neutrality,
                    &mut assignments,
                    &mut energy,
                    &mut output,
                    &mut error,
                )
            },
            STATUS_OK
        );
        let workspace_pointer = workspace.storage;
        let workspace_capacity = workspace.capacity;
        let neutrality_pointer = neutrality.storage;
        let neutrality_capacity = neutrality.capacity;
        let assignment_pointer = assignments.storage;
        let assignment_capacity_bytes = assignments.allocation_capacity_bytes;

        energy.reciprocal_space_kcal_per_mol = 301.0;
        force_x.fill(401.0);
        force_y.fill(402.0);
        force_z.fill(403.0);
        let mut late_error = initialized_error();
        {
            let _late = LateNonFiniteResultGuard::inject();
            // SAFETY: The injected scientific failure occurs after all three
            // leases and direct force writes; every RAII lease must restore.
            assert_eq!(
                unsafe {
                    evaluate_with_all_owner_reusable_storage(
                        &system,
                        &model,
                        &mut workspace,
                        &mut neutrality,
                        &mut assignments,
                        &mut energy,
                        &mut output,
                        &mut late_error,
                    )
                },
                STATUS_NUMERICAL_ERROR
            );
        }
        assert_eq!(
            late_error.typed_code,
            ParticleMeshReciprocalErrorCodeV1::NonFiniteResult as i32
        );
        assert_eq!(
            energy.reciprocal_space_kcal_per_mol.to_bits(),
            301.0_f64.to_bits()
        );
        assert_eq!(workspace.state, PARTICLE_MESH_RECIPROCAL_WORKSPACE_READY);
        assert_eq!(workspace.storage, workspace_pointer);
        assert_eq!(workspace.capacity, workspace_capacity);
        assert_eq!(
            neutrality.state,
            PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_READY
        );
        assert_eq!(neutrality.storage, neutrality_pointer);
        assert_eq!(neutrality.capacity, neutrality_capacity);
        assert_eq!(
            assignments.state,
            PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_READY
        );
        assert_eq!(assignments.storage, assignment_pointer);
        assert_eq!(
            assignments.allocation_capacity_bytes,
            assignment_capacity_bytes
        );
        assert_eq!(
            assignments.logical_length_bytes,
            charges.len() * size_of::<ParticleAssignment>()
        );

        energy.reciprocal_space_kcal_per_mol = 501.0;
        force_x.fill(601.0);
        force_y.fill(602.0);
        force_z.fill(603.0);
        let mut panic_error = initialized_error();
        {
            let _panic = ReusableWorkspacePanicGuard::inject();
            // SAFETY: The injected panic occurs after all prepares. catch_unwind
            // must run three drops before reporting the internal error.
            assert_eq!(
                unsafe {
                    evaluate_with_all_owner_reusable_storage(
                        &system,
                        &model,
                        &mut workspace,
                        &mut neutrality,
                        &mut assignments,
                        &mut energy,
                        &mut output,
                        &mut panic_error,
                    )
                },
                STATUS_INTERNAL_ERROR
            );
        }
        assert_eq!(
            provider_error_detail(&panic_error),
            "rust particle-mesh reciprocal provider panicked"
        );
        assert_eq!(
            energy.reciprocal_space_kcal_per_mol.to_bits(),
            501.0_f64.to_bits()
        );
        assert_eq!(force_x, [601.0; 4]);
        assert_eq!(force_y, [602.0; 4]);
        assert_eq!(force_z, [603.0; 4]);
        assert_eq!(workspace.state, PARTICLE_MESH_RECIPROCAL_WORKSPACE_READY);
        assert_eq!(workspace.storage, workspace_pointer);
        assert_eq!(workspace.capacity, workspace_capacity);
        assert_eq!(
            neutrality.state,
            PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_READY
        );
        assert_eq!(neutrality.storage, neutrality_pointer);
        assert_eq!(neutrality.capacity, neutrality_capacity);
        assert_eq!(
            assignments.state,
            PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_READY
        );
        assert_eq!(assignments.storage, assignment_pointer);
        assert_eq!(
            assignments.allocation_capacity_bytes,
            assignment_capacity_bytes
        );

        let mut recovered_error = initialized_error();
        // SAFETY: All three recovered READY descriptors are reusable.
        assert_eq!(
            unsafe {
                evaluate_with_all_owner_reusable_storage(
                    &system,
                    &model,
                    &mut workspace,
                    &mut neutrality,
                    &mut assignments,
                    &mut energy,
                    &mut output,
                    &mut recovered_error,
                )
            },
            STATUS_OK
        );
        // SAFETY: Canonical READY allocations remain exclusively owned.
        unsafe {
            super::bg_rust_particle_mesh_reciprocal_particle_assignment_scratch_destroy_v1(
                &mut assignments,
            );
            super::bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_destroy_v1(
                &mut neutrality,
            );
            super::bg_rust_particle_mesh_reciprocal_workspace_destroy_v1(&mut workspace);
        }
    }

    #[test]
    fn owner_particle_assignment_scratch_malformed_busy_type_and_cross_aliases_fail_closed() {
        // SAFETY: Null destruction is explicitly an idempotent no-op.
        unsafe {
            super::bg_rust_particle_mesh_reciprocal_particle_assignment_scratch_destroy_v1(
                ptr::null_mut(),
            );
        }
        let position_x = [1.25, 5.1, 10.2, 15.4];
        let position_y = [2.5, 3.2, 12.3, 17.1];
        let position_z = [3.75, 8.4, 7.7, 19.3];
        let charges = [0.7, -0.4, -0.6, 0.300_000_000_000_000_04];
        let system = provider_system(&position_x, &position_y, &position_z, &charges);
        let model = provider_model([4, 8, 16]);
        let mut energy = initialized_energy(101.0);
        let mut force_x = [201.0; 4];
        let mut force_y = [202.0; 4];
        let mut force_z = [203.0; 4];
        let mut output = provider_force_output(&mut force_x, &mut force_y, &mut force_z);

        let mut null_workspace = empty_workspace();
        let null_workspace_before = descriptor_bytes(&null_workspace);
        let mut null_neutrality = empty_neutrality_sort_scratch();
        let null_neutrality_before = descriptor_bytes(&null_neutrality);
        let mut null_error = initialized_error();
        let null_error_before = descriptor_bytes(&null_error);
        // SAFETY: A null assignment descriptor is deliberately invalid and
        // must fail before any other descriptor lease or error write.
        assert_eq!(
            unsafe {
                evaluate_with_all_owner_reusable_storage(
                    &system,
                    &model,
                    &mut null_workspace,
                    &mut null_neutrality,
                    ptr::null_mut(),
                    &mut energy,
                    &mut output,
                    &mut null_error,
                )
            },
            STATUS_INVALID_ARGUMENT
        );
        assert_eq!(descriptor_bytes(&null_workspace), null_workspace_before);
        assert_eq!(descriptor_bytes(&null_neutrality), null_neutrality_before);
        assert_eq!(descriptor_bytes(&null_error), null_error_before);

        let element_size = size_of::<ParticleAssignment>();
        let mut misaligned_storage = [0_u8; align_of::<ParticleAssignment>() + 1];
        let misaligned_offset = (0..align_of::<ParticleAssignment>())
            .find(|offset| {
                (misaligned_storage.as_ptr() as usize + offset) % align_of::<ParticleAssignment>()
                    != 0
            })
            .expect("assignment alignment has a misaligned byte offset");
        // SAFETY: The offset lies inside local storage; preflight only observes
        // this deliberately misaligned raw address and never dereferences it.
        let misaligned_pointer = unsafe {
            misaligned_storage
                .as_mut_ptr()
                .add(misaligned_offset)
                .cast::<c_void>()
        };
        let oversized_capacity_bytes = ((isize::MAX as usize) / element_size + 1)
            .checked_mul(element_size)
            .expect("rounded oversized assignment byte count fits usize");
        let end_overflow_address = usize::MAX & !(align_of::<ParticleAssignment>() - 1);
        let dangling_assignment = ptr::dangling::<ParticleAssignment>()
            .cast_mut()
            .cast::<c_void>();
        let malformed_cases = [
            ParticleMeshReciprocalParticleAssignmentScratchV1 {
                struct_size: 1,
                ..empty_particle_assignment_scratch()
            },
            canonical_particle_assignment_scratch_descriptor(
                PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_READY,
                ptr::null_mut(),
                0,
                1,
            ),
            ParticleMeshReciprocalParticleAssignmentScratchV1 {
                logical_length_bytes: element_size,
                ..canonical_particle_assignment_scratch_descriptor(
                    PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_READY,
                    ptr::null_mut(),
                    0,
                    0,
                )
            },
            ParticleMeshReciprocalParticleAssignmentScratchV1 {
                reserved0: 1,
                ..canonical_particle_assignment_scratch_descriptor(
                    PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_READY,
                    ptr::null_mut(),
                    0,
                    0,
                )
            },
            ParticleMeshReciprocalParticleAssignmentScratchV1 {
                reserved: [1, 0, 0, 0],
                ..canonical_particle_assignment_scratch_descriptor(
                    PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_READY,
                    ptr::null_mut(),
                    0,
                    0,
                )
            },
            canonical_particle_assignment_scratch_descriptor(0x554e_4b4e, ptr::null_mut(), 0, 0),
            canonical_particle_assignment_scratch_descriptor(
                PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_READY,
                ptr::null_mut(),
                0,
                0,
            ),
            ParticleMeshReciprocalParticleAssignmentScratchV1 {
                logical_length_bytes: 1,
                ..canonical_particle_assignment_scratch_descriptor(
                    PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_READY,
                    dangling_assignment,
                    0,
                    1,
                )
            },
            ParticleMeshReciprocalParticleAssignmentScratchV1 {
                storage: dangling_assignment,
                allocation_capacity_bytes: 1,
                ..canonical_particle_assignment_scratch_descriptor(
                    PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_READY,
                    ptr::null_mut(),
                    0,
                    0,
                )
            },
            canonical_particle_assignment_scratch_descriptor(
                PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_READY,
                misaligned_pointer,
                1,
                1,
            ),
            ParticleMeshReciprocalParticleAssignmentScratchV1 {
                storage: dangling_assignment,
                logical_length_bytes: element_size,
                allocation_capacity_bytes: oversized_capacity_bytes,
                ..canonical_particle_assignment_scratch_descriptor(
                    PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_READY,
                    ptr::null_mut(),
                    0,
                    0,
                )
            },
            ParticleMeshReciprocalParticleAssignmentScratchV1 {
                storage: end_overflow_address as *mut c_void,
                logical_length_bytes: element_size,
                allocation_capacity_bytes: element_size,
                ..canonical_particle_assignment_scratch_descriptor(
                    PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_READY,
                    ptr::null_mut(),
                    0,
                    0,
                )
            },
        ];
        for mut assignments in malformed_cases {
            let mut workspace = empty_workspace();
            let workspace_before = descriptor_bytes(&workspace);
            let mut neutrality = empty_neutrality_sort_scratch();
            let neutrality_before = descriptor_bytes(&neutrality);
            let assignments_before = descriptor_bytes(&assignments);
            let mut error = initialized_error();
            let error_before = descriptor_bytes(&error);
            // SAFETY: Every assignment descriptor is deliberately malformed.
            // Preflight must not convert byte counts, lease/free, or write error.
            assert_ne!(
                unsafe {
                    evaluate_with_all_owner_reusable_storage(
                        &system,
                        &model,
                        &mut workspace,
                        &mut neutrality,
                        &mut assignments,
                        &mut energy,
                        &mut output,
                        &mut error,
                    )
                },
                STATUS_OK
            );
            assert_eq!(descriptor_bytes(&workspace), workspace_before);
            assert_eq!(descriptor_bytes(&neutrality), neutrality_before);
            assert_eq!(descriptor_bytes(&assignments), assignments_before);
            assert_eq!(descriptor_bytes(&error), error_before);
            // SAFETY: Malformed assignment descriptors are destroy no-ops.
            unsafe {
                super::bg_rust_particle_mesh_reciprocal_particle_assignment_scratch_destroy_v1(
                    &mut assignments,
                );
            }
            assert_eq!(descriptor_bytes(&assignments), assignments_before);
        }

        let mut swapped_workspace = canonical_workspace_descriptor(
            PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_READY,
            ptr::null_mut(),
            0,
            0,
        );
        let swapped_workspace_before = descriptor_bytes(&swapped_workspace);
        let mut swapped_neutrality = empty_neutrality_sort_scratch();
        let mut swapped_assignments = empty_particle_assignment_scratch();
        let mut swapped_error = initialized_error();
        let swapped_error_before = descriptor_bytes(&swapped_error);
        // SAFETY: The workspace deliberately carries the distinct PAS1 tag and
        // must be rejected before any descriptor lease or error write.
        assert_eq!(
            unsafe {
                evaluate_with_all_owner_reusable_storage(
                    &system,
                    &model,
                    &mut swapped_workspace,
                    &mut swapped_neutrality,
                    &mut swapped_assignments,
                    &mut energy,
                    &mut output,
                    &mut swapped_error,
                )
            },
            STATUS_ABI_MISMATCH
        );
        assert_eq!(
            descriptor_bytes(&swapped_workspace),
            swapped_workspace_before
        );
        assert_eq!(descriptor_bytes(&swapped_error), swapped_error_before);
        // SAFETY: Type-swapped workspace is a malformed destroy no-op.
        unsafe {
            super::bg_rust_particle_mesh_reciprocal_workspace_destroy_v1(&mut swapped_workspace);
        }
        assert_eq!(
            descriptor_bytes(&swapped_workspace),
            swapped_workspace_before
        );

        let mut zero_capacity_ready = canonical_particle_assignment_scratch_descriptor(
            PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_READY,
            ptr::null_mut(),
            0,
            0,
        );
        // SAFETY: Canonical zero-capacity READY owns no allocation and destroy
        // transitions it exactly to all-zero EMPTY.
        unsafe {
            super::bg_rust_particle_mesh_reciprocal_particle_assignment_scratch_destroy_v1(
                &mut zero_capacity_ready,
            );
        }
        assert_eq!(
            descriptor_bytes(&zero_capacity_ready),
            descriptor_bytes(&empty_particle_assignment_scratch())
        );

        let mut busy_workspace = empty_workspace();
        let mut busy_neutrality = empty_neutrality_sort_scratch();
        let mut busy_assignments = canonical_particle_assignment_scratch_descriptor(
            PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_LEASED,
            ptr::null_mut(),
            0,
            0,
        );
        let busy_before = descriptor_bytes(&busy_assignments);
        let mut busy_error = initialized_error();
        // SAFETY: Canonical LEASED is deliberately busy; complete disjoint
        // preflight permits a diagnostic but never acquires or destroys it.
        assert_eq!(
            unsafe {
                evaluate_with_all_owner_reusable_storage(
                    &system,
                    &model,
                    &mut busy_workspace,
                    &mut busy_neutrality,
                    &mut busy_assignments,
                    &mut energy,
                    &mut output,
                    &mut busy_error,
                )
            },
            STATUS_INVALID_ARGUMENT
        );
        assert_eq!(
            provider_error_detail(&busy_error),
            "particle assignment scratch is already leased"
        );
        assert_eq!(descriptor_bytes(&busy_assignments), busy_before);
        unsafe {
            super::bg_rust_particle_mesh_reciprocal_particle_assignment_scratch_destroy_v1(
                &mut busy_assignments,
            );
        }
        assert_eq!(descriptor_bytes(&busy_assignments), busy_before);

        let mut shared_descriptor = empty_workspace();
        let shared_before = descriptor_bytes(&shared_descriptor);
        let mut shared_neutrality = empty_neutrality_sort_scratch();
        let mut shared_error = initialized_error();
        // SAFETY: Workspace and assignment pointers deliberately designate the
        // same 72-byte EMPTY descriptor. Pairwise preflight must reject it.
        assert_eq!(
            unsafe {
                evaluate_with_all_owner_reusable_storage(
                    &system,
                    &model,
                    &mut shared_descriptor,
                    &mut shared_neutrality,
                    (&mut shared_descriptor as *mut ParticleMeshReciprocalWorkspaceV1)
                        .cast::<ParticleMeshReciprocalParticleAssignmentScratchV1>(),
                    &mut energy,
                    &mut output,
                    &mut shared_error,
                )
            },
            STATUS_INVALID_ARGUMENT
        );
        assert_eq!(descriptor_bytes(&shared_descriptor), shared_before);

        let mut self_alias = canonical_particle_assignment_scratch_descriptor(
            PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_READY,
            ptr::null_mut(),
            1,
            1,
        );
        self_alias.storage = (&mut self_alias
            as *mut ParticleMeshReciprocalParticleAssignmentScratchV1)
            .cast::<c_void>();
        let self_alias_before = descriptor_bytes(&self_alias);
        let mut self_workspace = empty_workspace();
        let mut self_neutrality = empty_neutrality_sort_scratch();
        let mut self_error = initialized_error();
        // SAFETY: The claimed assignment backing deliberately overlaps its own
        // descriptor; only integer ranges are examined before rejection.
        assert_eq!(
            unsafe {
                evaluate_with_all_owner_reusable_storage(
                    &system,
                    &model,
                    &mut self_workspace,
                    &mut self_neutrality,
                    &mut self_alias,
                    &mut energy,
                    &mut output,
                    &mut self_error,
                )
            },
            STATUS_INVALID_ARGUMENT
        );
        assert_eq!(descriptor_bytes(&self_alias), self_alias_before);
        // SAFETY: Self-aliased backing makes destroy a fail-closed no-op.
        unsafe {
            super::bg_rust_particle_mesh_reciprocal_particle_assignment_scratch_destroy_v1(
                &mut self_alias,
            );
        }
        assert_eq!(descriptor_bytes(&self_alias), self_alias_before);

        let large_count = 32_usize;
        let large_position_x: Vec<f64> = (0..large_count)
            .map(|particle| bounded_usize_to_f64(particle) * 0.125)
            .collect();
        let large_position_y: Vec<f64> = (0..large_count)
            .map(|particle| bounded_usize_to_f64(particle) * 0.25)
            .collect();
        let large_position_z: Vec<f64> = (0..large_count)
            .map(|particle| bounded_usize_to_f64(particle) * 0.375)
            .collect();
        let large_charges: Vec<f64> = (0..large_count)
            .map(|particle| if particle % 2 == 0 { 1.0 } else { -1.0 })
            .collect();
        let large_system = provider_system(
            &large_position_x,
            &large_position_y,
            &large_position_z,
            &large_charges,
        );
        let mut large_x = vec![0.0; large_count];
        let mut large_y = vec![0.0; large_count];
        let mut large_z = vec![0.0; large_count];
        let mut large_output = provider_force_output(&mut large_x, &mut large_y, &mut large_z);
        let mut workspace = empty_workspace();
        let mut neutrality = empty_neutrality_sort_scratch();
        let mut assignments = empty_particle_assignment_scratch();
        let mut large_error = initialized_error();
        // SAFETY: Valid large channels establish all three canonical READY
        // allocations with 32 initialized logical assignment elements.
        assert_eq!(
            unsafe {
                evaluate_with_all_owner_reusable_storage(
                    &large_system,
                    &model,
                    &mut workspace,
                    &mut neutrality,
                    &mut assignments,
                    &mut energy,
                    &mut large_output,
                    &mut large_error,
                )
            },
            STATUS_OK
        );
        let workspace_before_cross = descriptor_bytes(&workspace);
        let workspace_bits_before_cross = workspace_storage_bits(&workspace);
        let neutrality_before_cross = descriptor_bytes(&neutrality);
        let neutrality_bits_before_cross = neutrality_sort_scratch_storage_bits(&neutrality);
        let assignments_before_cross = descriptor_bytes(&assignments);
        let assignment_bits_before_cross = particle_assignment_scratch_storage_bits(&assignments);

        let mut assignment_over_workspace = canonical_particle_assignment_scratch_descriptor(
            PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_READY,
            workspace.storage,
            1,
            1,
        );
        let assignment_over_workspace_before = descriptor_bytes(&assignment_over_workspace);
        let mut cross_error = initialized_error();
        // SAFETY: Forged assignment backing overlaps reciprocal workspace and
        // is rejected before either allocation becomes a Vec owner.
        assert_eq!(
            unsafe {
                evaluate_with_all_owner_reusable_storage(
                    &large_system,
                    &model,
                    &mut workspace,
                    &mut neutrality,
                    &mut assignment_over_workspace,
                    &mut energy,
                    &mut large_output,
                    &mut cross_error,
                )
            },
            STATUS_INVALID_ARGUMENT
        );
        assert_eq!(descriptor_bytes(&workspace), workspace_before_cross);
        assert_eq!(
            workspace_storage_bits(&workspace),
            workspace_bits_before_cross
        );
        assert_eq!(
            descriptor_bytes(&assignment_over_workspace),
            assignment_over_workspace_before
        );

        let mut assignment_over_neutrality = canonical_particle_assignment_scratch_descriptor(
            PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_READY,
            neutrality.storage,
            1,
            1,
        );
        let assignment_over_neutrality_before = descriptor_bytes(&assignment_over_neutrality);
        let mut reverse_cross_error = initialized_error();
        // SAFETY: Forged assignment backing overlaps neutrality storage and is
        // rejected using complete capacity ranges before lease conversion.
        assert_eq!(
            unsafe {
                evaluate_with_all_owner_reusable_storage(
                    &large_system,
                    &model,
                    &mut workspace,
                    &mut neutrality,
                    &mut assignment_over_neutrality,
                    &mut energy,
                    &mut large_output,
                    &mut reverse_cross_error,
                )
            },
            STATUS_INVALID_ARGUMENT
        );
        assert_eq!(descriptor_bytes(&neutrality), neutrality_before_cross);
        assert_eq!(
            neutrality_sort_scratch_storage_bits(&neutrality),
            neutrality_bits_before_cross
        );
        assert_eq!(
            descriptor_bytes(&assignment_over_neutrality),
            assignment_over_neutrality_before
        );

        let mut workspace_over_assignment = canonical_workspace_descriptor(
            PARTICLE_MESH_RECIPROCAL_WORKSPACE_READY,
            assignments.storage,
            1,
            1,
        );
        let workspace_over_assignment_before = descriptor_bytes(&workspace_over_assignment);
        let mut workspace_cross_error = initialized_error();
        // SAFETY: Forged reciprocal backing overlaps the assignment allocation
        // and is rejected before reconstructing any raw Vec parts.
        assert_eq!(
            unsafe {
                evaluate_with_all_owner_reusable_storage(
                    &large_system,
                    &model,
                    &mut workspace_over_assignment,
                    &mut neutrality,
                    &mut assignments,
                    &mut energy,
                    &mut large_output,
                    &mut workspace_cross_error,
                )
            },
            STATUS_INVALID_ARGUMENT
        );
        assert_eq!(
            descriptor_bytes(&workspace_over_assignment),
            workspace_over_assignment_before
        );
        assert_eq!(descriptor_bytes(&assignments), assignments_before_cross);
        assert_eq!(
            particle_assignment_scratch_storage_bits(&assignments),
            assignment_bits_before_cross
        );

        let mut neutrality_over_assignment = canonical_neutrality_sort_scratch_descriptor(
            PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_READY,
            assignments.storage,
            1,
            1,
        );
        let neutrality_over_assignment_before = descriptor_bytes(&neutrality_over_assignment);
        let mut neutrality_cross_error = initialized_error();
        // SAFETY: Forged f64 scratch backing overlaps assignment storage and is
        // rejected before taking either ownership lease.
        assert_eq!(
            unsafe {
                evaluate_with_all_owner_reusable_storage(
                    &large_system,
                    &model,
                    &mut workspace,
                    &mut neutrality_over_assignment,
                    &mut assignments,
                    &mut energy,
                    &mut large_output,
                    &mut neutrality_cross_error,
                )
            },
            STATUS_INVALID_ARGUMENT
        );
        assert_eq!(
            descriptor_bytes(&neutrality_over_assignment),
            neutrality_over_assignment_before
        );
        assert_eq!(descriptor_bytes(&assignments), assignments_before_cross);

        let mut shrink_error = initialized_error();
        // SAFETY: The real descriptors remain canonical and shrink logical
        // assignment length while preserving the larger allocation capacity.
        assert_eq!(
            unsafe {
                evaluate_with_all_owner_reusable_storage(
                    &system,
                    &model,
                    &mut workspace,
                    &mut neutrality,
                    &mut assignments,
                    &mut energy,
                    &mut output,
                    &mut shrink_error,
                )
            },
            STATUS_OK
        );
        assert_eq!(
            assignments.logical_length_bytes,
            charges.len() * element_size
        );
        assert!(
            assignments.allocation_capacity_bytes - assignments.logical_length_bytes
                >= charges.len() * size_of::<f64>()
        );
        let workspace_before_tail = descriptor_bytes(&workspace);
        let neutrality_before_tail = descriptor_bytes(&neutrality);
        let assignments_before_tail = descriptor_bytes(&assignments);
        let assignment_bits_before_tail = particle_assignment_scratch_storage_bits(&assignments);
        // SAFETY: Only a raw address inside spare capacity is formed. No slice,
        // read, or write touches the logically uninitialized capacity tail.
        let capacity_tail = unsafe {
            assignments
                .storage
                .cast::<u8>()
                .add(assignments.logical_length_bytes)
                .cast::<f64>()
        };
        let mut tail_y = [701.0; 4];
        let mut tail_z = [702.0; 4];
        let mut tail_output = ParticleMeshReciprocalForceOutputV1 {
            struct_size: u32::try_from(size_of::<ParticleMeshReciprocalForceOutputV1>()).unwrap(),
            abi_version: PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION,
            capacity: charges.len(),
            x: capacity_tail,
            y: tail_y.as_mut_ptr(),
            z: tail_z.as_mut_ptr(),
            reserved: [0; 4],
        };
        let mut tail_error = initialized_error();
        assert_eq!(
            unsafe {
                evaluate_with_all_owner_reusable_storage(
                    &system,
                    &model,
                    &mut workspace,
                    &mut neutrality,
                    &mut assignments,
                    &mut energy,
                    &mut tail_output,
                    &mut tail_error,
                )
            },
            STATUS_INVALID_ARGUMENT
        );
        assert_eq!(descriptor_bytes(&workspace), workspace_before_tail);
        assert_eq!(descriptor_bytes(&neutrality), neutrality_before_tail);
        assert_eq!(descriptor_bytes(&assignments), assignments_before_tail);
        assert_eq!(
            particle_assignment_scratch_storage_bits(&assignments),
            assignment_bits_before_tail
        );
        assert_eq!(tail_y, [701.0; 4]);
        assert_eq!(tail_z, [702.0; 4]);

        let assignment_pointer_before_zero_length = assignments.storage;
        let assignment_capacity_before_zero_length = assignments.allocation_capacity_bytes;
        assignments.logical_length_bytes = 0;
        let mut zero_length_error = initialized_error();
        {
            let _injection = AllocationFailureGuard::inject(AllocationSite::ParticleAssignments);
            // SAFETY: ParticleAssignment is compile-time no-Drop. Shrinking only
            // the Rust-origin logical byte count forgets no drop obligations;
            // prepare performs no read and overwrites all four elements.
            assert_eq!(
                unsafe {
                    evaluate_with_all_owner_reusable_storage(
                        &system,
                        &model,
                        &mut workspace,
                        &mut neutrality,
                        &mut assignments,
                        &mut energy,
                        &mut output,
                        &mut zero_length_error,
                    )
                },
                STATUS_OK
            );
            assert_injected_allocation_remains_pending(AllocationSite::ParticleAssignments);
        }
        assert_eq!(assignments.storage, assignment_pointer_before_zero_length);
        assert_eq!(
            assignments.allocation_capacity_bytes,
            assignment_capacity_before_zero_length
        );
        assert_eq!(
            assignments.logical_length_bytes,
            charges.len() * element_size
        );

        // SAFETY: Only the three actual canonical READY descriptors own their
        // allocations. Every forged descriptor above was left untouched.
        unsafe {
            super::bg_rust_particle_mesh_reciprocal_particle_assignment_scratch_destroy_v1(
                &mut assignments,
            );
            super::bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_destroy_v1(
                &mut neutrality,
            );
            super::bg_rust_particle_mesh_reciprocal_workspace_destroy_v1(&mut workspace);
        }
    }
}
