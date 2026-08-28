//! Independent native Rust CPU provider for frozen direct-Ewald v1 semantics.
//!
//! This implementation has no dependency on or call path into the standalone
//! scalar oracle. The private C ABI below is consumed only by the native C++
//! dispatcher; the public API retains ownership and transaction boundaries.

use std::cmp::Ordering;
use std::collections::{BTreeMap, BTreeSet};
use std::error::Error;
use std::fmt;
use std::mem::{align_of, size_of};
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::ptr;

/// Coulomb conversion factor in kcal·angstrom/(mol·e²).
pub const COULOMB_KCAL_ANGSTROM_PER_MOL_E2: f64 = 332.063_713_299;
const MAX_ATOM_COUNT: usize = 4_096;
const MAX_RECIPROCAL_INDEX: i32 = 32;
const MAX_EVALUATION_WORK_UNITS: usize = 10_000_000;
const MAX_ABSOLUTE_COORDINATE_ANGSTROM: f64 = 1.0e12;
const MIN_CELL_LENGTH_ANGSTROM: f64 = 1.0e-6;
const MAX_CELL_LENGTH_ANGSTROM: f64 = 1.0e9;
const MIN_NONZERO_ABSOLUTE_CHARGE_E: f64 = 1.0e-12;
const MAX_ABSOLUTE_CHARGE_E: f64 = 16.0;
const CHARGE_NORMALIZATION_SCALE_E: f64 = f64::from_bits(0x3d70_0000_0000_0000);
const MIN_ALPHA_PER_ANGSTROM: f64 = 1.0e-12;
const MAX_ALPHA_PER_ANGSTROM: f64 = 1.0e6;
const MIN_CUTOFF_ANGSTROM: f64 = 1.0e-8;
const MAX_CUTOFF_ANGSTROM: f64 = 1.0e8;
const MIN_DIELECTRIC: f64 = 1.0e-12;
const MAX_DIELECTRIC: f64 = 1.0e12;
const MIN_SUPPORTED_PAIR_DISTANCE_ANGSTROM: f64 = 1.0e-8;
const MAX_SUPPORTED_PAIR_DISTANCE_ANGSTROM: f64 = 1.0e3;
const PERIODIC_IMAGE_COMPARISON_RELATIVE_TOLERANCE: f64 = 5.0e-12;
const LN_HALF_MIN_POSITIVE_SUBNORMAL: f64 = -745.133_219_101_941_1;

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

    fn components(self) -> [f64; 3] {
        [self.x_angstrom, self.y_angstrom, self.z_angstrom]
    }
}

/// Fully periodic orthorhombic cell in canonical angstrom units.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct OrthorhombicCell {
    pub lengths_angstrom: [f64; 3],
}

/// An unordered pair whose local full Coulomb interaction is removed.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct PairExclusion {
    pub atom_i: usize,
    pub atom_j: usize,
}

/// An unordered pair with a local full-Coulomb scale in `[0,1]`.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct PairScale {
    pub atom_i: usize,
    pub atom_j: usize,
    pub coulomb_scale: f64,
}

/// Frozen direct-Ewald numerical settings.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct EwaldSettings {
    pub alpha_per_angstrom: f64,
    pub real_space_cutoff_angstrom: f64,
    pub reciprocal_max_indices: [i32; 3],
    pub dielectric: f64,
    pub minimum_pair_distance_angstrom: f64,
}

impl Default for EwaldSettings {
    fn default() -> Self {
        Self {
            alpha_per_angstrom: 0.3,
            real_space_cutoff_angstrom: 8.0,
            reciprocal_max_indices: [5, 5, 5],
            dielectric: 1.0,
            minimum_pair_distance_angstrom: 1.0e-8,
        }
    }
}

/// Complete owned input to the independent direct-Ewald evaluator.
#[derive(Clone, Debug, PartialEq)]
pub struct EwaldInput {
    pub positions: Vec<Position>,
    pub charges_elementary: Vec<f64>,
    pub cell: OrthorhombicCell,
    pub exclusions: Vec<PairExclusion>,
    pub pair_scales: Vec<PairScale>,
    pub settings: EwaldSettings,
}

impl EwaldInput {
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
            exclusions: Vec::new(),
            pair_scales: Vec::new(),
            settings: EwaldSettings::default(),
        }
    }
}

/// Energy components in their frozen final summation order.
#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct EwaldEnergyComponents {
    pub real_space_kcal_per_mol: f64,
    pub reciprocal_space_kcal_per_mol: f64,
    pub self_kcal_per_mol: f64,
    pub pair_correction_kcal_per_mol: f64,
}

impl EwaldEnergyComponents {
    /// Sum real, reciprocal, self, and pair-correction components in that order.
    #[must_use]
    pub fn total_kcal_per_mol(self) -> f64 {
        self.real_space_kcal_per_mol
            + self.reciprocal_space_kcal_per_mol
            + self.self_kcal_per_mol
            + self.pair_correction_kcal_per_mol
    }
}

/// Direct-Ewald energy and analytic force result.
#[derive(Clone, Debug, PartialEq)]
pub struct EwaldEvaluation {
    pub energy: EwaldEnergyComponents,
    /// Force on each atom in kcal/(mol·angstrom), indexed like the input positions.
    pub forces_kcal_per_mol_angstrom: Vec<[f64; 3]>,
}

/// Stable error categories for malformed or unsupported Ewald inputs.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum EwaldErrorCode {
    EmptySystem,
    CapacityExceeded,
    ChargeCountMismatch,
    NonFiniteCoordinate,
    NonFiniteCharge,
    NonNeutralSystem,
    InvalidCell,
    CutoffViolatesMinimumImage,
    InvalidParameter,
    AtomIndexOutOfRange,
    RepeatedAtomIndex,
    DuplicatePairRule,
    ConflictingPairRule,
    AmbiguousPairCorrectionImage,
    AmbiguousRealSpaceCutoff,
    AmbiguousMinimumPairDistance,
    PairBelowMinimumDistance,
    DampingUnderflow,
    PhaseUnderflow,
    NonFiniteResult,
}

/// A validation or evaluation failure with a machine-readable category.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct EwaldError {
    code: EwaldErrorCode,
    detail: String,
}

impl EwaldError {
    fn new(code: EwaldErrorCode, detail: impl Into<String>) -> Self {
        Self {
            code,
            detail: detail.into(),
        }
    }

    #[must_use]
    pub const fn code(&self) -> EwaldErrorCode {
        self.code
    }
}

impl fmt::Display for EwaldError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "{:?}: {}", self.code, self.detail)
    }
}

impl Error for EwaldError {}

type PairKey = (usize, usize);

struct PairRules {
    corrections: BTreeMap<PairKey, f64>,
}

/// Evaluate direct Ewald electrostatics using scalar binary64 arithmetic.
///
/// Real-space pairs use lexicographic `i < j` order and strict comparisons at
/// the half-cell image boundary after primary-cell reduction. Reciprocal
/// vectors use nested `nx`, `ny`, `nz` ascending order over the inclusive
/// configured bounds, omitting only `(0,0,0)`. Structure factors and per-vector
/// forces traverse atoms in input order.
///
/// # Errors
///
/// Returns a typed [`EwaldError`] when the input violates a structural,
/// numerical, neutrality, periodic-cell, cutoff, or pair-rule invariant.
pub fn evaluate(input: &EwaldInput) -> Result<EwaldEvaluation, EwaldError> {
    evaluate_with_force_option(input, true)
}

fn evaluate_with_force_option(
    input: &EwaldInput,
    compute_forces: bool,
) -> Result<EwaldEvaluation, EwaldError> {
    let pair_rules = validate(input)?;
    let mut result = EwaldEvaluation {
        energy: EwaldEnergyComponents::default(),
        forces_kcal_per_mol_angstrom: if compute_forces {
            vec![[0.0; 3]; input.positions.len()]
        } else {
            Vec::new()
        },
    };
    let coulomb_scale = COULOMB_KCAL_ANGSTROM_PER_MOL_E2 / input.settings.dielectric;
    evaluate_real_space(input, coulomb_scale, compute_forces, &mut result)?;
    evaluate_reciprocal_space(input, coulomb_scale, compute_forces, &mut result)?;
    let charge_square_sum = accurate_charge_square_sum(&input.charges_elementary);
    result.energy.self_kcal_per_mol =
        -coulomb_scale * input.settings.alpha_per_angstrom * charge_square_sum
            / libm::sqrt(core::f64::consts::PI);
    evaluate_pair_corrections(
        input,
        &pair_rules,
        coulomb_scale,
        compute_forces,
        &mut result,
    )?;

    if !result.energy.total_kcal_per_mol().is_finite()
        || result
            .forces_kcal_per_mol_angstrom
            .iter()
            .flatten()
            .any(|value| !value.is_finite())
    {
        return Err(EwaldError::new(
            EwaldErrorCode::NonFiniteResult,
            "final energy or force is not finite",
        ));
    }
    Ok(result)
}

fn evaluate_real_space(
    input: &EwaldInput,
    coulomb_scale: f64,
    compute_forces: bool,
    result: &mut EwaldEvaluation,
) -> Result<(), EwaldError> {
    let alpha = input.settings.alpha_per_angstrom;
    let minimum_distance = input.settings.minimum_pair_distance_angstrom;
    let mut energy_terms = Vec::new();
    let mut force_terms = compute_forces.then(|| new_force_term_buffers(input.positions.len()));
    for atom_i in 0..input.positions.len() {
        for atom_j in (atom_i + 1)..input.positions.len() {
            let charge_product =
                input.charges_elementary[atom_i] * input.charges_elementary[atom_j];
            if matches!(charge_product.to_bits(), 0 | 0x8000_0000_0000_0000) {
                continue;
            }
            let delta = minimum_image(input.positions[atom_i], input.positions[atom_j], input.cell);
            let distance2 = squared_norm(delta);
            let distance = libm::sqrt(distance2);
            let minimum_scale = distance.abs().max(minimum_distance.abs());
            if (distance - minimum_distance).abs()
                <= PERIODIC_IMAGE_COMPARISON_RELATIVE_TOLERANCE * minimum_scale
            {
                return Err(EwaldError::new(
                    EwaldErrorCode::AmbiguousMinimumPairDistance,
                    format!(
                        "pair ({atom_i},{atom_j}) distance {distance} is within the periodic-image tolerance of minimum {minimum_distance}"
                    ),
                ));
            }
            if distance < minimum_distance {
                return Err(EwaldError::new(
                    EwaldErrorCode::PairBelowMinimumDistance,
                    format!("pair ({atom_i},{atom_j}) is below {minimum_distance} angstrom"),
                ));
            }
            let cutoff = input.settings.real_space_cutoff_angstrom;
            let cutoff_scale = distance.abs().max(cutoff.abs());
            if (distance - cutoff).abs()
                <= PERIODIC_IMAGE_COMPARISON_RELATIVE_TOLERANCE * cutoff_scale
            {
                return Err(EwaldError::new(
                    EwaldErrorCode::AmbiguousRealSpaceCutoff,
                    format!(
                        "pair ({atom_i},{atom_j}) distance {distance} is within the periodic-image tolerance of cutoff {cutoff}"
                    ),
                ));
            }
            if distance <= cutoff {
                let alpha_distance = alpha * distance;
                let erfc_value = libm::erfc(alpha_distance);
                let exponential = libm::exp(-alpha_distance * alpha_distance);
                if !erfc_value.is_normal() || !exponential.is_normal() {
                    return Err(EwaldError::new(
                        EwaldErrorCode::DampingUnderflow,
                        format!(
                            "pair ({atom_i},{atom_j}) damping is subnormal or zero at alpha-distance {alpha_distance}"
                        ),
                    ));
                }
                let charge_prefactor = coulomb_scale * charge_product;
                let pair_energy = if distance < 1.0 {
                    charge_prefactor * (erfc_value / distance)
                } else {
                    charge_prefactor * erfc_value / distance
                };
                energy_terms.push(pair_energy);

                if let Some(force_terms) = force_terms.as_mut() {
                    let gaussian_prefactor =
                        charge_prefactor * (2.0 * alpha / libm::sqrt(core::f64::consts::PI));
                    let radial_force_magnitude = if distance < 1.0 {
                        charge_prefactor * (erfc_value / distance2)
                            + gaussian_prefactor * (exponential / distance)
                    } else {
                        charge_prefactor * erfc_value / distance2
                            + gaussian_prefactor * exponential / distance
                    };
                    for (axis, &delta_component) in delta.iter().enumerate() {
                        let component = if distance < 1.0 {
                            (radial_force_magnitude / distance) * delta_component
                        } else {
                            (radial_force_magnitude * delta_component) / distance
                        };
                        push_pair_force_term(force_terms, atom_i, atom_j, axis, component);
                    }
                }
            }
        }
    }
    checked_add(
        &mut result.energy.real_space_kcal_per_mol,
        accurate_order_independent_sum(&energy_terms),
        "real-space energy",
    )?;
    if let Some(force_terms) = force_terms.as_ref() {
        apply_canonical_force_terms(
            &mut result.forces_kcal_per_mol_angstrom,
            force_terms,
            "real-space force",
        )?;
    }
    Ok(())
}

fn evaluate_reciprocal_space(
    input: &EwaldInput,
    coulomb_scale: f64,
    compute_forces: bool,
    result: &mut EwaldEvaluation,
) -> Result<(), EwaldError> {
    let lengths = input.cell.lengths_angstrom;
    let volume = cell_volume(input.cell);
    let reciprocal_energy_factor = coulomb_scale * 2.0 * core::f64::consts::PI / volume;
    let reciprocal_force_factor = coulomb_scale * 4.0 * core::f64::consts::PI / volume;
    let charge_unit = CHARGE_NORMALIZATION_SCALE_E;
    let squared_charge_unit = charge_unit * charge_unit;
    let alpha = input.settings.alpha_per_angstrom;
    let max_indices = input.settings.reciprocal_max_indices;
    let phase_origin = canonical_phase_origin(input);
    let relative_positions = input
        .positions
        .iter()
        .zip(&input.charges_elementary)
        .map(|(&position, &charge)| {
            if charge == 0.0 {
                [0.0; 3]
            } else {
                minimum_image(position, phase_origin, input.cell)
            }
        })
        .collect::<Vec<_>>();
    for nx in -max_indices[0]..=max_indices[0] {
        for ny in -max_indices[1]..=max_indices[1] {
            for nz in -max_indices[2]..=max_indices[2] {
                if nx == 0 && ny == 0 && nz == 0 {
                    continue;
                }
                let wave = [
                    core::f64::consts::TAU * f64::from(nx) / lengths[0],
                    core::f64::consts::TAU * f64::from(ny) / lengths[1],
                    core::f64::consts::TAU * f64::from(nz) / lengths[2],
                ];
                let wave2 = squared_norm(wave);
                let damping_exponent = -wave2 / (4.0 * alpha * alpha);
                let exponential = libm::exp(damping_exponent);
                if reciprocal_vector_is_provably_zero(
                    input.positions.len(),
                    reciprocal_energy_factor,
                    reciprocal_force_factor,
                    wave,
                    wave2,
                    damping_exponent,
                ) {
                    continue;
                }
                let phases = relative_positions
                    .iter()
                    .zip(&input.charges_elementary)
                    .map(|(&position, &charge)| {
                        if charge == 0.0 {
                            return Ok((0.0, 1.0));
                        }
                        let phase = checked_phase(wave, position)?;
                        Ok(libm::sincos(phase))
                    })
                    .collect::<Result<Vec<_>, EwaldError>>()?;
                let (structure_cos, structure_sin) =
                    canonical_structure_factor(&input.charges_elementary, &phases, charge_unit);
                let scaled_energy_factor = reciprocal_energy_factor * squared_charge_unit / wave2;
                let undamped_energy = scaled_energy_factor * structure_cos * structure_cos
                    + scaled_energy_factor * structure_sin * structure_sin;
                checked_add(
                    &mut result.energy.reciprocal_space_kcal_per_mol,
                    apply_reciprocal_damping(undamped_energy, damping_exponent, exponential),
                    "reciprocal-space energy",
                )?;
                if compute_forces {
                    for ((force, &charge), &(phase_sin, phase_cos)) in result
                        .forces_kcal_per_mol_angstrom
                        .iter_mut()
                        .zip(&input.charges_elementary)
                        .zip(&phases)
                    {
                        for axis in 0..3 {
                            let undamped_force = scaled_reciprocal_force_component(
                                reciprocal_force_factor * squared_charge_unit,
                                wave[axis],
                                wave2,
                                charge / charge_unit,
                                (structure_cos, structure_sin),
                                (phase_sin, phase_cos),
                                1.0,
                            );
                            checked_add(
                                &mut force[axis],
                                apply_reciprocal_damping(
                                    undamped_force,
                                    damping_exponent,
                                    exponential,
                                ),
                                "reciprocal force",
                            )?;
                        }
                    }
                }
            }
        }
    }
    Ok(())
}

fn evaluate_pair_corrections(
    input: &EwaldInput,
    pair_rules: &PairRules,
    coulomb_scale: f64,
    compute_forces: bool,
    result: &mut EwaldEvaluation,
) -> Result<(), EwaldError> {
    let mut energy_terms = Vec::with_capacity(pair_rules.corrections.len());
    let mut force_terms = compute_forces.then(|| new_force_term_buffers(input.positions.len()));
    for (&(atom_i, atom_j), &pair_scale) in &pair_rules.corrections {
        if pair_scale.to_bits() == 1.0_f64.to_bits() {
            continue;
        }
        let charge_product = input.charges_elementary[atom_i] * input.charges_elementary[atom_j];
        if matches!(charge_product.to_bits(), 0 | 0x8000_0000_0000_0000) {
            continue;
        }
        let delta = pair_correction_displacement(
            input.positions[atom_i],
            input.positions[atom_j],
            input.cell,
        )?;
        let distance2 = squared_norm(delta);
        let distance = libm::sqrt(distance2);
        let correction_scale = pair_scale - 1.0;
        energy_terms.push(coulomb_scale * charge_product * correction_scale / distance);
        if let Some(force_terms) = force_terms.as_mut() {
            let factor = coulomb_scale * charge_product * correction_scale / (distance2 * distance);
            for (axis, &delta_component) in delta.iter().enumerate() {
                push_pair_force_term(force_terms, atom_i, atom_j, axis, factor * delta_component);
            }
        }
    }
    checked_add(
        &mut result.energy.pair_correction_kcal_per_mol,
        accurate_order_independent_sum(&energy_terms),
        "pair-correction energy",
    )?;
    if let Some(force_terms) = force_terms.as_ref() {
        apply_canonical_force_terms(
            &mut result.forces_kcal_per_mol_angstrom,
            force_terms,
            "pair-correction force",
        )?;
    }
    Ok(())
}

fn validate(input: &EwaldInput) -> Result<PairRules, EwaldError> {
    validate_atom_arrays(input)?;
    validate_cell(input.cell)?;
    validate_settings(input)?;
    let raw_pair_rule_count = input
        .exclusions
        .len()
        .checked_add(input.pair_scales.len())
        .ok_or_else(|| {
            EwaldError::new(
                EwaldErrorCode::CapacityExceeded,
                "pair-rule row count exceeds addressable capacity",
            )
        })?;
    validate_work_limit(input, raw_pair_rule_count)?;
    let pair_rules = validate_pair_rules(input)?;
    validate_work_limit(input, pair_rules.corrections.len())?;
    Ok(pair_rules)
}

fn validate_atom_arrays(input: &EwaldInput) -> Result<(), EwaldError> {
    let atom_count = input.positions.len();
    if atom_count == 0 {
        return Err(EwaldError::new(
            EwaldErrorCode::EmptySystem,
            "at least one atom is required",
        ));
    }
    if atom_count > MAX_ATOM_COUNT {
        return Err(EwaldError::new(
            EwaldErrorCode::CapacityExceeded,
            format!("atom count {atom_count} exceeds {MAX_ATOM_COUNT}"),
        ));
    }
    if input.charges_elementary.len() != atom_count {
        return Err(EwaldError::new(
            EwaldErrorCode::ChargeCountMismatch,
            format!(
                "{atom_count} positions have {} charges",
                input.charges_elementary.len()
            ),
        ));
    }
    for (atom, position) in input.positions.iter().enumerate() {
        if position.components().iter().any(|value| !value.is_finite()) {
            return Err(EwaldError::new(
                EwaldErrorCode::NonFiniteCoordinate,
                format!("atom {atom} has a non-finite coordinate"),
            ));
        }
        if position
            .components()
            .iter()
            .any(|value| value.abs() > MAX_ABSOLUTE_COORDINATE_ANGSTROM)
        {
            return Err(invalid_parameter(format!(
                "atom {atom} coordinate exceeds {MAX_ABSOLUTE_COORDINATE_ANGSTROM} angstrom"
            )));
        }
    }
    for (atom, charge) in input.charges_elementary.iter().enumerate() {
        if !charge.is_finite() {
            return Err(EwaldError::new(
                EwaldErrorCode::NonFiniteCharge,
                format!("atom {atom} charge is not finite"),
            ));
        }
        let magnitude = charge.abs();
        if magnitude > MAX_ABSOLUTE_CHARGE_E
            || (magnitude > 0.0 && magnitude < MIN_NONZERO_ABSOLUTE_CHARGE_E)
        {
            return Err(invalid_parameter(format!(
                "atom {atom} nonzero charge magnitude must lie in [{MIN_NONZERO_ABSOLUTE_CHARGE_E},{MAX_ABSOLUTE_CHARGE_E}] elementary"
            )));
        }
    }
    Ok(())
}

fn validate_cell(cell: OrthorhombicCell) -> Result<(), EwaldError> {
    for (axis, length) in cell.lengths_angstrom.iter().copied().enumerate() {
        if !length.is_finite()
            || !(MIN_CELL_LENGTH_ANGSTROM..=MAX_CELL_LENGTH_ANGSTROM).contains(&length)
        {
            return Err(EwaldError::new(
                EwaldErrorCode::InvalidCell,
                format!(
                    "cell length axis {axis} must lie in [{MIN_CELL_LENGTH_ANGSTROM},{MAX_CELL_LENGTH_ANGSTROM}] angstrom"
                ),
            ));
        }
    }
    let volume = cell_volume(cell);
    if !volume.is_finite() || volume <= 0.0 {
        return Err(EwaldError::new(
            EwaldErrorCode::InvalidCell,
            "cell volume must be finite and positive",
        ));
    }
    Ok(())
}

fn validate_settings(input: &EwaldInput) -> Result<(), EwaldError> {
    require_range(
        input.settings.alpha_per_angstrom,
        MIN_ALPHA_PER_ANGSTROM,
        MAX_ALPHA_PER_ANGSTROM,
        "alpha_per_angstrom",
    )?;
    require_range(
        input.settings.real_space_cutoff_angstrom,
        MIN_CUTOFF_ANGSTROM,
        MAX_CUTOFF_ANGSTROM,
        "real_space_cutoff_angstrom",
    )?;
    require_range(
        input.settings.dielectric,
        MIN_DIELECTRIC,
        MAX_DIELECTRIC,
        "dielectric",
    )?;
    require_range(
        input.settings.minimum_pair_distance_angstrom,
        MIN_SUPPORTED_PAIR_DISTANCE_ANGSTROM,
        MAX_SUPPORTED_PAIR_DISTANCE_ANGSTROM,
        "minimum_pair_distance_angstrom",
    )?;
    if input.settings.minimum_pair_distance_angstrom >= input.settings.real_space_cutoff_angstrom {
        return Err(invalid_parameter(
            "minimum_pair_distance_angstrom must be below real_space_cutoff_angstrom",
        ));
    }
    let total_charge = accurate_order_independent_sum(&input.charges_elementary);
    if !total_charge.is_finite() || total_charge != 0.0 {
        return Err(EwaldError::new(
            EwaldErrorCode::NonNeutralSystem,
            format!("total charge {total_charge} is not exactly zero"),
        ));
    }
    for (axis, maximum) in input
        .settings
        .reciprocal_max_indices
        .iter()
        .copied()
        .enumerate()
    {
        if !(1..=MAX_RECIPROCAL_INDEX).contains(&maximum) {
            return Err(invalid_parameter(format!(
                "reciprocal_max_indices axis {axis} must lie in [1,{MAX_RECIPROCAL_INDEX}]"
            )));
        }
    }
    for (axis, length) in input.cell.lengths_angstrom.iter().copied().enumerate() {
        if input.settings.real_space_cutoff_angstrom >= 0.5 * length {
            return Err(EwaldError::new(
                EwaldErrorCode::CutoffViolatesMinimumImage,
                format!(
                    "cutoff {} must be below half of axis {axis} length {length}",
                    input.settings.real_space_cutoff_angstrom
                ),
            ));
        }
    }
    Ok(())
}

fn validate_pair_rules(input: &EwaldInput) -> Result<PairRules, EwaldError> {
    let mut exclusions = BTreeSet::new();
    for (row_index, row) in input.exclusions.iter().enumerate() {
        let pair = canonical_pair(row.atom_i, row.atom_j, input.positions.len(), "exclusion")?;
        if !exclusions.insert(pair) {
            return Err(EwaldError::new(
                EwaldErrorCode::DuplicatePairRule,
                format!("exclusion row {row_index} duplicates pair {pair:?}"),
            ));
        }
    }
    let mut scales = BTreeMap::new();
    for (row_index, row) in input.pair_scales.iter().enumerate() {
        let pair = canonical_pair(row.atom_i, row.atom_j, input.positions.len(), "pair scale")?;
        if !row.coulomb_scale.is_finite() || !(0.0..=1.0).contains(&row.coulomb_scale) {
            return Err(invalid_parameter(format!(
                "pair scale row {row_index} must lie in [0,1]"
            )));
        }
        if scales.insert(pair, row.coulomb_scale).is_some() {
            return Err(EwaldError::new(
                EwaldErrorCode::DuplicatePairRule,
                format!("pair scale row {row_index} duplicates pair {pair:?}"),
            ));
        }
    }
    if let Some(pair) = exclusions.iter().find(|pair| scales.contains_key(pair)) {
        return Err(EwaldError::new(
            EwaldErrorCode::ConflictingPairRule,
            format!("pair {pair:?} cannot be both excluded and scaled"),
        ));
    }
    let mut corrections = scales;
    for pair in exclusions {
        corrections.insert(pair, 0.0);
    }
    Ok(PairRules { corrections })
}

fn canonical_pair(
    atom_i: usize,
    atom_j: usize,
    atom_count: usize,
    context: &str,
) -> Result<PairKey, EwaldError> {
    if atom_i >= atom_count || atom_j >= atom_count {
        return Err(EwaldError::new(
            EwaldErrorCode::AtomIndexOutOfRange,
            format!("{context} pair ({atom_i},{atom_j}) is outside 0..{atom_count}"),
        ));
    }
    if atom_i == atom_j {
        return Err(EwaldError::new(
            EwaldErrorCode::RepeatedAtomIndex,
            format!("{context} repeats atom index {atom_i}"),
        ));
    }
    Ok((atom_i.min(atom_j), atom_i.max(atom_j)))
}

fn minimum_image(first: Position, second: Position, cell: OrthorhombicCell) -> [f64; 3] {
    let first = reduce_to_primary_cell(first, cell);
    let second = reduce_to_primary_cell(second, cell);
    let mut delta = [0.0; 3];
    for axis in 0..3 {
        let length = cell.lengths_angstrom[axis];
        let (raw, raw_error) = two_difference(first[axis], second[axis]);
        delta[axis] = if compare_primary_axis_separation(first[axis], second[axis], length)
            == Ordering::Greater
        {
            if first[axis] > second[axis] {
                add_to_expansion(raw, raw_error, -length)
            } else {
                add_to_expansion(raw, raw_error, length)
            }
        } else {
            raw
        };
    }
    delta
}

fn reduce_to_primary_cell(position: Position, cell: OrthorhombicCell) -> [f64; 3] {
    let components = position.components();
    let mut reduced = [0.0; 3];
    for axis in 0..3 {
        let length = cell.lengths_angstrom[axis];
        let component = components[axis];
        let value = component.rem_euclid(length);
        reduced[axis] = if matches!(value.to_bits(), 0 | 0x8000_0000_0000_0000) {
            0.0
        } else if value.to_bits() == length.to_bits() {
            let signed_residual = component % length;
            if matches!(signed_residual.to_bits(), 0 | 0x8000_0000_0000_0000) {
                0.0
            } else {
                signed_residual
            }
        } else if value < 0.0 {
            value + length
        } else if value > length {
            value - length
        } else {
            value
        };
    }
    reduced
}

fn canonical_phase_origin(input: &EwaldInput) -> Position {
    let Some(maximum_charge_magnitude) = input
        .charges_elementary
        .iter()
        .map(|charge| charge.abs())
        .filter(|magnitude| *magnitude != 0.0)
        .max_by(f64::total_cmp)
    else {
        return Position::default();
    };
    let candidates = input
        .charges_elementary
        .iter()
        .enumerate()
        .filter_map(|(atom, &charge)| {
            (charge.abs().to_bits() == maximum_charge_magnitude.to_bits()).then_some(atom)
        })
        .collect::<Vec<_>>();
    let atom = if candidates.len() == 1 {
        candidates[0]
    } else {
        candidates
            .into_iter()
            .map(|candidate| (candidate, phase_origin_signature(input, candidate)))
            .min_by(|left, right| compare_phase_origin_signatures(&left.1, &right.1))
            .expect("a maximum-charge phase-origin candidate exists")
            .0
    };
    input.positions[atom]
}

fn phase_origin_signature(input: &EwaldInput, origin: usize) -> Vec<[f64; 6]> {
    let origin_charge = input.charges_elementary[origin];
    let mut signature = input
        .positions
        .iter()
        .zip(&input.charges_elementary)
        .filter(|(_, charge)| **charge != 0.0)
        .map(|(&position, &charge)| {
            let delta = minimum_image(position, input.positions[origin], input.cell);
            [
                charge.abs(),
                charge * origin_charge,
                squared_norm(delta),
                delta[0],
                delta[1],
                delta[2],
            ]
        })
        .collect::<Vec<_>>();
    signature.sort_by(compare_phase_origin_entries);
    signature
}

fn compare_phase_origin_entries(left: &[f64; 6], right: &[f64; 6]) -> Ordering {
    left.iter()
        .zip(right)
        .map(|(left, right)| left.total_cmp(right))
        .find(|ordering| *ordering != Ordering::Equal)
        .unwrap_or(Ordering::Equal)
}

fn compare_phase_origin_signatures(left: &[[f64; 6]], right: &[[f64; 6]]) -> Ordering {
    left.iter()
        .zip(right)
        .map(|(left, right)| compare_phase_origin_entries(left, right))
        .find(|ordering| *ordering != Ordering::Equal)
        .unwrap_or_else(|| left.len().cmp(&right.len()))
}

fn pair_correction_displacement(
    first: Position,
    second: Position,
    cell: OrthorhombicCell,
) -> Result<[f64; 3], EwaldError> {
    let first = reduce_to_primary_cell(first, cell);
    let second = reduce_to_primary_cell(second, cell);
    let mut delta = [0.0; 3];
    for axis in 0..3 {
        let length = cell.lengths_angstrom[axis];
        let (raw, raw_error) = two_difference(first[axis], second[axis]);
        let separation = compare_primary_axis_separation(first[axis], second[axis], length);
        let half_length = 0.5 * length;
        let expanded_separation = if raw.is_sign_negative() {
            -raw - raw_error
        } else {
            raw + raw_error
        };
        if (expanded_separation - half_length).abs()
            <= PERIODIC_IMAGE_COMPARISON_RELATIVE_TOLERANCE * half_length
        {
            return Err(EwaldError::new(
                EwaldErrorCode::AmbiguousPairCorrectionImage,
                format!(
                    "pair correction is within the periodic-image tolerance of half a cell on axis {axis}"
                ),
            ));
        }
        delta[axis] = if separation == Ordering::Greater {
            if first[axis] > second[axis] {
                add_to_expansion(raw, raw_error, -length)
            } else {
                add_to_expansion(raw, raw_error, length)
            }
        } else {
            raw
        };
    }
    Ok(delta)
}

fn compare_primary_axis_separation(first: f64, second: f64, length: f64) -> Ordering {
    let (high, low) = if first > second {
        (first, second)
    } else {
        (second, first)
    };
    let (difference, error) = two_difference(high, low);
    match difference.total_cmp(&(0.5 * length)) {
        Ordering::Equal => error.total_cmp(&0.0),
        ordering => ordering,
    }
}

fn two_difference(first: f64, second: f64) -> (f64, f64) {
    let difference = first - second;
    let second_virtual = first - difference;
    let first_virtual = difference + second_virtual;
    let second_roundoff = second_virtual - second;
    let first_roundoff = first - first_virtual;
    (difference, first_roundoff + second_roundoff)
}

fn add_to_expansion(high: f64, low: f64, value: f64) -> f64 {
    let sum = high + value;
    let value_virtual = sum - high;
    let high_virtual = sum - value_virtual;
    let high_roundoff = high - high_virtual;
    let value_roundoff = value - value_virtual;
    sum + (low + high_roundoff + value_roundoff)
}

fn accurate_order_independent_sum(values: &[f64]) -> f64 {
    let mut ordered = values.to_vec();
    ordered.sort_by(|left, right| {
        left.abs()
            .total_cmp(&right.abs())
            .then_with(|| left.total_cmp(right))
    });
    let mut sum = 0.0;
    let mut correction = 0.0;
    for value in ordered {
        let updated = sum + value;
        correction += if sum.abs() >= value.abs() {
            (sum - updated) + value
        } else {
            (value - updated) + sum
        };
        sum = updated;
    }
    sum + correction
}

fn accurate_charge_square_sum(charges: &[f64]) -> f64 {
    let squares = charges
        .iter()
        .map(|charge| charge * charge)
        .collect::<Vec<_>>();
    accurate_order_independent_sum(&squares)
}

fn cell_volume(cell: OrthorhombicCell) -> f64 {
    let mut lengths = cell.lengths_angstrom;
    lengths.sort_by(f64::total_cmp);
    (lengths[0] * lengths[2]) * lengths[1]
}

fn validate_work_limit(input: &EwaldInput, pair_rule_count: usize) -> Result<(), EwaldError> {
    let dimensions = input
        .settings
        .reciprocal_max_indices
        .map(|maximum| usize::try_from(2 * maximum + 1).expect("validated positive bound"));
    let vector_count = dimensions
        .into_iter()
        .try_fold(1_usize, usize::checked_mul)
        .and_then(|count| count.checked_sub(1))
        .ok_or_else(|| {
            EwaldError::new(
                EwaldErrorCode::CapacityExceeded,
                "reciprocal vector count exceeds addressable capacity",
            )
        })?;
    let atom_count = input.positions.len();
    let pair_count = atom_count
        .checked_mul(atom_count.saturating_sub(1))
        .and_then(|count| count.checked_div(2))
        .ok_or_else(|| {
            EwaldError::new(
                EwaldErrorCode::CapacityExceeded,
                "real-space pair count exceeds addressable capacity",
            )
        })?;
    let phase_work = atom_count
        .checked_mul(vector_count)
        .and_then(|count| count.checked_mul(2))
        .ok_or_else(|| {
            EwaldError::new(
                EwaldErrorCode::CapacityExceeded,
                "reciprocal phase work exceeds addressable capacity",
            )
        })?;
    let phase_origin_candidate_count = input
        .charges_elementary
        .iter()
        .map(|charge| charge.abs())
        .filter(|magnitude| *magnitude != 0.0)
        .max_by(f64::total_cmp)
        .map_or(0, |maximum| {
            input
                .charges_elementary
                .iter()
                .filter(|charge| charge.abs().to_bits() == maximum.to_bits())
                .count()
        });
    let phase_origin_work = atom_count
        .checked_mul(phase_origin_candidate_count)
        .ok_or_else(|| {
            EwaldError::new(
                EwaldErrorCode::CapacityExceeded,
                "phase-origin canonicalization work exceeds addressable capacity",
            )
        })?;
    let pair_accumulation_work = pair_count.checked_mul(7).ok_or_else(|| {
        EwaldError::new(
            EwaldErrorCode::CapacityExceeded,
            "real-space accumulation work exceeds addressable capacity",
        )
    })?;
    let pair_rule_accumulation_work = pair_rule_count.checked_mul(7).ok_or_else(|| {
        EwaldError::new(
            EwaldErrorCode::CapacityExceeded,
            "pair-correction accumulation work exceeds addressable capacity",
        )
    })?;
    let total_work = pair_accumulation_work
        .checked_add(pair_rule_accumulation_work)
        .and_then(|work| work.checked_add(phase_work))
        .and_then(|work| work.checked_add(phase_origin_work))
        .ok_or_else(|| {
            EwaldError::new(
                EwaldErrorCode::CapacityExceeded,
                "combined evaluation work exceeds addressable capacity",
            )
        })?;
    if total_work > MAX_EVALUATION_WORK_UNITS {
        return Err(EwaldError::new(
            EwaldErrorCode::CapacityExceeded,
            format!("combined evaluation work {total_work} exceeds {MAX_EVALUATION_WORK_UNITS}"),
        ));
    }
    Ok(())
}

fn dot(first: [f64; 3], second: [f64; 3]) -> f64 {
    first[0] * second[0] + first[1] * second[1] + first[2] * second[2]
}

fn checked_phase(wave: [f64; 3], position: [f64; 3]) -> Result<f64, EwaldError> {
    let terms = [
        wave[0] * position[0],
        wave[1] * position[1],
        wave[2] * position[2],
    ];
    for axis in 0..3 {
        if wave[axis] != 0.0 && position[axis] != 0.0 && !terms[axis].is_normal() {
            return Err(EwaldError::new(
                EwaldErrorCode::PhaseUnderflow,
                format!("reciprocal phase product is subnormal or zero on axis {axis}"),
            ));
        }
    }
    Ok(accurate_order_independent_sum(&terms))
}

fn apply_reciprocal_damping(undamped_value: f64, damping_exponent: f64, exponential: f64) -> f64 {
    if undamped_value == 0.0 {
        return 0.0;
    }
    if exponential.is_normal() {
        return undamped_value * exponential;
    }
    let completed_log_magnitude = libm::log(undamped_value.abs()) + damping_exponent;
    if completed_log_magnitude <= LN_HALF_MIN_POSITIVE_SUBNORMAL {
        return 0.0;
    }
    let magnitude = libm::exp(completed_log_magnitude);
    if undamped_value.is_sign_negative() {
        -magnitude
    } else {
        magnitude
    }
}

fn reciprocal_vector_is_provably_zero(
    atom_count: usize,
    reciprocal_energy_factor: f64,
    reciprocal_force_factor: f64,
    wave: [f64; 3],
    wave2: f64,
    damping_exponent: f64,
) -> bool {
    let maximum_charge_sum =
        f64::from(u32::try_from(atom_count).expect("validated atom count fits u32"))
            * MAX_ABSOLUTE_CHARGE_E;
    let maximum_energy =
        reciprocal_energy_factor.abs() / wave2 * maximum_charge_sum * maximum_charge_sum;
    let maximum_wave_component = wave.into_iter().map(f64::abs).fold(0.0, f64::max);
    let maximum_force = reciprocal_force_factor.abs() * maximum_wave_component / wave2
        * MAX_ABSOLUTE_CHARGE_E
        * maximum_charge_sum;
    let maximum_completed = maximum_energy.max(maximum_force);
    maximum_completed.is_finite()
        && libm::log(maximum_completed) + damping_exponent <= LN_HALF_MIN_POSITIVE_SUBNORMAL
}

fn canonical_structure_factor(
    charges: &[f64],
    phases: &[(f64, f64)],
    charge_unit: f64,
) -> (f64, f64) {
    let mut cosine_terms = Vec::with_capacity(charges.len());
    let mut sine_terms = Vec::with_capacity(charges.len());
    for (&charge, &(phase_sin, phase_cos)) in charges.iter().zip(phases) {
        let normalized_charge = charge / charge_unit;
        cosine_terms.push(normalized_charge * phase_cos);
        sine_terms.push(normalized_charge * phase_sin);
    }
    (
        accurate_order_independent_sum(&cosine_terms),
        accurate_order_independent_sum(&sine_terms),
    )
}

fn squared_norm(vector: [f64; 3]) -> f64 {
    dot(vector, vector)
}

fn scaled_reciprocal_force_component(
    reciprocal_force_factor: f64,
    wave_component: f64,
    wave2: f64,
    charge: f64,
    structure_cos_sin: (f64, f64),
    phase_sin_cos: (f64, f64),
    exponential: f64,
) -> f64 {
    let prefactor = reciprocal_force_factor * wave_component / wave2 * charge;
    (prefactor * structure_cos_sin.0 * phase_sin_cos.0
        - prefactor * structure_cos_sin.1 * phase_sin_cos.1)
        * exponential
}

fn new_force_term_buffers(atom_count: usize) -> Vec<[Vec<f64>; 3]> {
    (0..atom_count)
        .map(|_| [Vec::new(), Vec::new(), Vec::new()])
        .collect()
}

fn push_pair_force_term(
    terms: &mut [[Vec<f64>; 3]],
    atom_i: usize,
    atom_j: usize,
    axis: usize,
    component: f64,
) {
    terms[atom_i][axis].push(component);
    terms[atom_j][axis].push(-component);
}

fn apply_canonical_force_terms(
    forces: &mut [[f64; 3]],
    terms: &[[Vec<f64>; 3]],
    context: &str,
) -> Result<(), EwaldError> {
    for (force, atom_terms) in forces.iter_mut().zip(terms) {
        for axis in 0..3 {
            checked_add(
                &mut force[axis],
                accurate_order_independent_sum(&atom_terms[axis]),
                context,
            )?;
        }
    }
    Ok(())
}

fn checked_add(target: &mut f64, value: f64, context: &str) -> Result<(), EwaldError> {
    let updated = *target + value;
    if !value.is_finite() || !updated.is_finite() {
        return Err(EwaldError::new(
            EwaldErrorCode::NonFiniteResult,
            format!("{context} produced a non-finite value"),
        ));
    }
    *target = updated;
    Ok(())
}

fn require_range(value: f64, minimum: f64, maximum: f64, name: &str) -> Result<(), EwaldError> {
    if !value.is_finite() || !(minimum..=maximum).contains(&value) {
        return Err(invalid_parameter(format!(
            "{name} must lie in [{minimum},{maximum}]"
        )));
    }
    Ok(())
}

fn invalid_parameter(detail: impl Into<String>) -> EwaldError {
    EwaldError::new(EwaldErrorCode::InvalidParameter, detail)
}

const DIRECT_EWALD_PROVIDER_ABI_VERSION: u32 = 1;
const DIRECT_EWALD_ERROR_CAPACITY: usize = 256;
const STATUS_OK: i32 = 0;
const STATUS_INVALID_ARGUMENT: i32 = 1;
const STATUS_ABI_MISMATCH: i32 = 2;
const STATUS_CAPACITY_OVERFLOW: i32 = 6;
const STATUS_INTERNAL_ERROR: i32 = 9;
const STATUS_NUMERICAL_ERROR: i32 = 10;

#[repr(i32)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum DirectEwaldErrorCodeV1 {
    None = 0,
    EmptySystem = 1,
    CapacityExceeded = 2,
    ChargeCountMismatch = 3,
    NonFiniteCoordinate = 4,
    NonFiniteCharge = 5,
    NonNeutralSystem = 6,
    InvalidCell = 7,
    CutoffViolatesMinimumImage = 8,
    InvalidParameter = 9,
    AtomIndexOutOfRange = 10,
    RepeatedAtomIndex = 11,
    DuplicatePairRule = 12,
    ConflictingPairRule = 13,
    AmbiguousPairCorrectionImage = 14,
    AmbiguousRealSpaceCutoff = 15,
    AmbiguousMinimumPairDistance = 16,
    PairBelowMinimumDistance = 17,
    DampingUnderflow = 18,
    PhaseUnderflow = 19,
    NonFiniteResult = 20,
}

impl From<EwaldErrorCode> for DirectEwaldErrorCodeV1 {
    fn from(value: EwaldErrorCode) -> Self {
        match value {
            EwaldErrorCode::EmptySystem => Self::EmptySystem,
            EwaldErrorCode::CapacityExceeded => Self::CapacityExceeded,
            EwaldErrorCode::ChargeCountMismatch => Self::ChargeCountMismatch,
            EwaldErrorCode::NonFiniteCoordinate => Self::NonFiniteCoordinate,
            EwaldErrorCode::NonFiniteCharge => Self::NonFiniteCharge,
            EwaldErrorCode::NonNeutralSystem => Self::NonNeutralSystem,
            EwaldErrorCode::InvalidCell => Self::InvalidCell,
            EwaldErrorCode::CutoffViolatesMinimumImage => Self::CutoffViolatesMinimumImage,
            EwaldErrorCode::InvalidParameter => Self::InvalidParameter,
            EwaldErrorCode::AtomIndexOutOfRange => Self::AtomIndexOutOfRange,
            EwaldErrorCode::RepeatedAtomIndex => Self::RepeatedAtomIndex,
            EwaldErrorCode::DuplicatePairRule => Self::DuplicatePairRule,
            EwaldErrorCode::ConflictingPairRule => Self::ConflictingPairRule,
            EwaldErrorCode::AmbiguousPairCorrectionImage => Self::AmbiguousPairCorrectionImage,
            EwaldErrorCode::AmbiguousRealSpaceCutoff => Self::AmbiguousRealSpaceCutoff,
            EwaldErrorCode::AmbiguousMinimumPairDistance => Self::AmbiguousMinimumPairDistance,
            EwaldErrorCode::PairBelowMinimumDistance => Self::PairBelowMinimumDistance,
            EwaldErrorCode::DampingUnderflow => Self::DampingUnderflow,
            EwaldErrorCode::PhaseUnderflow => Self::PhaseUnderflow,
            EwaldErrorCode::NonFiniteResult => Self::NonFiniteResult,
        }
    }
}

#[repr(C)]
#[derive(Clone, Copy)]
pub(crate) struct DirectEwaldSystemV1 {
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
pub(crate) struct DirectEwaldPairRuleV1 {
    atom_i: usize,
    atom_j: usize,
    coulomb_scale: f64,
    reserved: [u64; 2],
}

#[repr(C)]
#[derive(Clone, Copy)]
pub(crate) struct DirectEwaldModelV1 {
    struct_size: u32,
    abi_version: u32,
    cell_lengths_angstrom: [f64; 3],
    alpha_per_angstrom: f64,
    real_space_cutoff_angstrom: f64,
    reciprocal_max_indices: [i32; 3],
    reserved0: u32,
    dielectric: f64,
    minimum_pair_distance_angstrom: f64,
    pair_rule_count: usize,
    pair_rules: *const DirectEwaldPairRuleV1,
    reserved: [u64; 4],
}

#[repr(C)]
#[derive(Clone, Copy)]
pub(crate) struct DirectEwaldEnergyV1 {
    struct_size: u32,
    abi_version: u32,
    real_space_kcal_per_mol: f64,
    reciprocal_space_kcal_per_mol: f64,
    self_kcal_per_mol: f64,
    pair_correction_kcal_per_mol: f64,
    total_kcal_per_mol: f64,
    reserved: [u64; 4],
}

#[repr(C)]
#[derive(Clone, Copy)]
pub(crate) struct DirectEwaldForceOutputV1 {
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
pub(crate) struct DirectEwaldErrorV1 {
    struct_size: u32,
    abi_version: u32,
    typed_code: i32,
    reserved0: u32,
    detail: [u8; DIRECT_EWALD_ERROR_CAPACITY],
    reserved: [u64; 4],
}

#[derive(Clone, Copy)]
struct MemoryRange {
    begin: usize,
    end: usize,
}

#[derive(Debug)]
struct ProviderFailure {
    status: i32,
    code: DirectEwaldErrorCodeV1,
    detail: String,
    may_write_error: bool,
}

impl ProviderFailure {
    fn new(status: i32, code: DirectEwaldErrorCodeV1, detail: impl Into<String>) -> Self {
        Self {
            status,
            code,
            detail: detail.into(),
            may_write_error: true,
        }
    }

    fn invalid(detail: impl Into<String>) -> Self {
        Self::new(
            STATUS_INVALID_ARGUMENT,
            DirectEwaldErrorCodeV1::None,
            detail,
        )
    }

    fn abi(detail: impl Into<String>) -> Self {
        Self::new(STATUS_ABI_MISMATCH, DirectEwaldErrorCodeV1::None, detail)
    }

    fn capacity(detail: impl Into<String>) -> Self {
        Self::new(
            STATUS_CAPACITY_OVERFLOW,
            DirectEwaldErrorCodeV1::CapacityExceeded,
            detail,
        )
    }

    fn without_error_write(mut self) -> Self {
        self.may_write_error = false;
        self
    }
}

impl From<EwaldError> for ProviderFailure {
    fn from(error: EwaldError) -> Self {
        let status = match error.code() {
            EwaldErrorCode::CapacityExceeded => STATUS_CAPACITY_OVERFLOW,
            EwaldErrorCode::AmbiguousPairCorrectionImage
            | EwaldErrorCode::AmbiguousRealSpaceCutoff
            | EwaldErrorCode::AmbiguousMinimumPairDistance
            | EwaldErrorCode::PairBelowMinimumDistance
            | EwaldErrorCode::DampingUnderflow
            | EwaldErrorCode::PhaseUnderflow
            | EwaldErrorCode::NonNeutralSystem
            | EwaldErrorCode::NonFiniteResult => STATUS_NUMERICAL_ERROR,
            _ => STATUS_INVALID_ARGUMENT,
        };
        Self::new(status, error.code().into(), error.detail)
    }
}

struct ProviderCandidate {
    energy: DirectEwaldEnergyV1,
    forces: Vec<[f64; 3]>,
    force_output: Option<DirectEwaldForceOutputV1>,
}

fn reserved_is_zero(values: &[u64]) -> bool {
    values.iter().all(|value| *value == 0)
}

fn validate_header<T>(
    struct_size: u32,
    abi_version: u32,
    reserved: &[u64],
    label: &str,
) -> Result<(), ProviderFailure> {
    if usize::try_from(struct_size).ok() != Some(size_of::<T>()) {
        return Err(ProviderFailure::abi(format!(
            "{label} struct size does not match the provider ABI"
        )));
    }
    if abi_version != DIRECT_EWALD_PROVIDER_ABI_VERSION {
        return Err(ProviderFailure::abi(format!(
            "{label} provider ABI version does not match"
        )));
    }
    if !reserved_is_zero(reserved) {
        return Err(ProviderFailure::abi(format!(
            "{label} reserved fields must be zero"
        )));
    }
    Ok(())
}

fn checked_range<T>(
    pointer: *const T,
    length: usize,
    null_detail: &str,
) -> Result<Option<MemoryRange>, ProviderFailure> {
    if length == 0 {
        return Ok(None);
    }
    if pointer.is_null() {
        return Err(ProviderFailure::invalid(null_detail));
    }
    if (pointer as usize) % align_of::<T>() != 0 {
        return Err(ProviderFailure::invalid(format!(
            "{null_detail}; pointer is not naturally aligned"
        )));
    }
    if length > (isize::MAX as usize) / size_of::<T>() {
        return Err(ProviderFailure::capacity(format!(
            "{null_detail}; range exceeds addressable capacity"
        )));
    }
    let byte_count = length * size_of::<T>();
    let begin = pointer as usize;
    let end = begin.checked_add(byte_count).ok_or_else(|| {
        ProviderFailure::capacity(format!("{null_detail}; pointer range overflows"))
    })?;
    Ok(Some(MemoryRange { begin, end }))
}

fn ranges_overlap(first: MemoryRange, second: MemoryRange) -> bool {
    first.begin < second.end && second.begin < first.end
}

fn require_disjoint_outputs(
    mutable_ranges: &[MemoryRange],
    error_range: MemoryRange,
) -> Result<(), ProviderFailure> {
    for first_index in 0..mutable_ranges.len() {
        for &second in &mutable_ranges[(first_index + 1)..] {
            if ranges_overlap(mutable_ranges[first_index], second) {
                let failure = ProviderFailure::invalid(
                    "direct-Ewald mutable output regions must not overlap",
                );
                return Err(
                    if ranges_overlap(mutable_ranges[first_index], error_range)
                        || ranges_overlap(second, error_range)
                    {
                        failure.without_error_write()
                    } else {
                        failure
                    },
                );
            }
        }
    }
    Ok(())
}

unsafe fn read_descriptor<T: Copy>(
    pointer: *const T,
    label: &str,
) -> Result<(T, MemoryRange), ProviderFailure> {
    let range = checked_range(pointer, 1, &format!("{label} descriptor is null"))?
        .expect("one-element descriptor has a range");
    // SAFETY: The private ABI requires an initialized, naturally aligned
    // descriptor for the duration of the call; alignment was checked above.
    Ok((unsafe { ptr::read(pointer) }, range))
}

unsafe fn copy_slice<T: Copy>(
    pointer: *const T,
    length: usize,
    label: &str,
) -> Result<(Vec<T>, Option<MemoryRange>), ProviderFailure> {
    let range = checked_range(pointer, length, &format!("{label} channel is null"))?;
    if length == 0 {
        return Ok((Vec::new(), range));
    }
    // SAFETY: The caller supplies `length` initialized elements and the range
    // and alignment have been validated above. Copying removes all input
    // borrows before any output is committed.
    let values = unsafe { core::slice::from_raw_parts(pointer, length) }.to_vec();
    Ok((values, range))
}

fn provider_input(
    system: DirectEwaldSystemV1,
    model: DirectEwaldModelV1,
    input_ranges: &mut Vec<MemoryRange>,
) -> Result<EwaldInput, ProviderFailure> {
    // SAFETY: The private ABI supplies initialized channels. Each channel is
    // range checked and immediately copied into Rust-owned storage.
    let (position_x, range_x) =
        unsafe { copy_slice(system.position_x, system.atom_count, "position_x")? };
    // SAFETY: Same contract and validation as `position_x`.
    let (position_y, range_y) =
        unsafe { copy_slice(system.position_y, system.atom_count, "position_y")? };
    // SAFETY: Same contract and validation as `position_x`.
    let (position_z, range_z) =
        unsafe { copy_slice(system.position_z, system.atom_count, "position_z")? };
    // SAFETY: Same contract and validation as `position_x`.
    let (charges, range_charge) =
        unsafe { copy_slice(system.charge, system.atom_count, "charge")? };
    // SAFETY: Pair rows follow the same initialized-channel contract.
    let (pair_rows, range_pairs) =
        unsafe { copy_slice(model.pair_rules, model.pair_rule_count, "pair_rules")? };
    input_ranges.extend(
        [range_x, range_y, range_z, range_charge, range_pairs]
            .into_iter()
            .flatten(),
    );

    let positions = position_x
        .into_iter()
        .zip(position_y)
        .zip(position_z)
        .map(|((x, y), z)| Position::new(x, y, z))
        .collect::<Vec<_>>();
    let mut pair_scales = Vec::with_capacity(pair_rows.len());
    let mut previous_pair = None;
    for (row_index, row) in pair_rows.into_iter().enumerate() {
        if !reserved_is_zero(&row.reserved) {
            return Err(ProviderFailure::abi(format!(
                "pair rule row {row_index} reserved fields must be zero"
            )));
        }
        if row.atom_i == row.atom_j {
            return Err(ProviderFailure::new(
                STATUS_INVALID_ARGUMENT,
                DirectEwaldErrorCodeV1::RepeatedAtomIndex,
                format!("pair rule row {row_index} repeats atom {}", row.atom_i),
            ));
        }
        if row.atom_i > row.atom_j {
            return Err(ProviderFailure::new(
                STATUS_INVALID_ARGUMENT,
                DirectEwaldErrorCodeV1::InvalidParameter,
                format!("pair rule row {row_index} is not canonical i < j"),
            ));
        }
        let pair = (row.atom_i, row.atom_j);
        if previous_pair == Some(pair) {
            return Err(ProviderFailure::new(
                STATUS_INVALID_ARGUMENT,
                DirectEwaldErrorCodeV1::DuplicatePairRule,
                format!("pair rule row {row_index} duplicates pair {pair:?}"),
            ));
        }
        if previous_pair.is_some_and(|previous| previous > pair) {
            return Err(ProviderFailure::new(
                STATUS_INVALID_ARGUMENT,
                DirectEwaldErrorCodeV1::InvalidParameter,
                format!("pair rule row {row_index} is not lexicographically sorted"),
            ));
        }
        previous_pair = Some(pair);
        pair_scales.push(PairScale {
            atom_i: row.atom_i,
            atom_j: row.atom_j,
            coulomb_scale: row.coulomb_scale,
        });
    }

    Ok(EwaldInput {
        positions,
        charges_elementary: charges,
        cell: OrthorhombicCell {
            lengths_angstrom: model.cell_lengths_angstrom,
        },
        exclusions: Vec::new(),
        pair_scales,
        settings: EwaldSettings {
            alpha_per_angstrom: model.alpha_per_angstrom,
            real_space_cutoff_angstrom: model.real_space_cutoff_angstrom,
            reciprocal_max_indices: model.reciprocal_max_indices,
            dielectric: model.dielectric,
            minimum_pair_distance_angstrom: model.minimum_pair_distance_angstrom,
        },
    })
}

unsafe fn evaluate_provider_impl(
    system_pointer: *const DirectEwaldSystemV1,
    model_pointer: *const DirectEwaldModelV1,
    compute_forces: u8,
    energy_pointer: *mut DirectEwaldEnergyV1,
    force_pointer: *mut DirectEwaldForceOutputV1,
    error_range: MemoryRange,
) -> Result<ProviderCandidate, ProviderFailure> {
    if !matches!(compute_forces, 0 | 1) {
        return Err(ProviderFailure::invalid(
            "compute_forces must be exactly zero or one",
        ));
    }
    // SAFETY: `read_descriptor` validates non-nullness and alignment before
    // copying each caller-owned descriptor.
    let (system, system_range) = unsafe { read_descriptor(system_pointer, "system")? };
    // SAFETY: Same descriptor contract as `system`.
    let (model, model_range) = unsafe { read_descriptor(model_pointer, "model")? };
    validate_header::<DirectEwaldSystemV1>(
        system.struct_size,
        system.abi_version,
        &system.reserved,
        "system",
    )?;
    validate_header::<DirectEwaldModelV1>(
        model.struct_size,
        model.abi_version,
        &model.reserved,
        "model",
    )?;
    if model.reserved0 != 0 {
        return Err(ProviderFailure::abi("model reserved0 must be zero"));
    }
    if system.atom_count > MAX_ATOM_COUNT {
        return Err(ProviderFailure::new(
            STATUS_CAPACITY_OVERFLOW,
            DirectEwaldErrorCodeV1::CapacityExceeded,
            format!("atom count {} exceeds {MAX_ATOM_COUNT}", system.atom_count),
        ));
    }
    if model.pair_rule_count > MAX_EVALUATION_WORK_UNITS / 7 {
        return Err(ProviderFailure::new(
            STATUS_CAPACITY_OVERFLOW,
            DirectEwaldErrorCodeV1::CapacityExceeded,
            "pair-rule row count exceeds the direct-Ewald work envelope",
        ));
    }
    // SAFETY: Energy is an initialized output descriptor whose header is read
    // before its complete value is transactionally replaced.
    let (energy_output, energy_range) = unsafe { read_descriptor(energy_pointer, "energy")? };
    validate_header::<DirectEwaldEnergyV1>(
        energy_output.struct_size,
        energy_output.abi_version,
        &energy_output.reserved,
        "energy output",
    )?;

    let mut input_ranges = vec![system_range, model_range];
    let mut mutable_ranges = vec![error_range, energy_range];
    let force_output = if compute_forces == 1 {
        // SAFETY: The force descriptor follows the same initialized descriptor
        // contract and is not mutated by the provider.
        let (output, descriptor_range) = unsafe { read_descriptor(force_pointer, "force")? };
        validate_header::<DirectEwaldForceOutputV1>(
            output.struct_size,
            output.abi_version,
            &output.reserved,
            "force output",
        )?;
        if output.capacity < system.atom_count {
            return Err(ProviderFailure::capacity(format!(
                "force capacity {} is below atom count {}",
                output.capacity, system.atom_count
            )));
        }
        input_ranges.push(descriptor_range);
        for (pointer, label) in [
            (output.x, "force x output"),
            (output.y, "force y output"),
            (output.z, "force z output"),
        ] {
            let range = checked_range(pointer.cast_const(), system.atom_count, label)?;
            mutable_ranges.extend(range);
        }
        Some(output)
    } else {
        if !force_pointer.is_null() {
            return Err(ProviderFailure::invalid(
                "force output must be null when compute_forces is zero",
            ));
        }
        None
    };
    require_disjoint_outputs(&mutable_ranges, error_range)?;

    let input = provider_input(system, model, &mut input_ranges)?;
    for input_range in input_ranges {
        if mutable_ranges
            .iter()
            .copied()
            .any(|output_range| ranges_overlap(input_range, output_range))
        {
            let failure = ProviderFailure::invalid(
                "direct-Ewald output storage must not overlap input storage",
            );
            return Err(if ranges_overlap(input_range, error_range) {
                failure.without_error_write()
            } else {
                failure
            });
        }
    }

    let result = if compute_forces == 1 {
        evaluate(&input)
    } else {
        evaluate_with_force_option(&input, false)
    }
    .map_err(ProviderFailure::from)?;
    let components = result.energy;
    let energy = DirectEwaldEnergyV1 {
        struct_size: u32::try_from(size_of::<DirectEwaldEnergyV1>()).unwrap_or(0),
        abi_version: DIRECT_EWALD_PROVIDER_ABI_VERSION,
        real_space_kcal_per_mol: components.real_space_kcal_per_mol,
        reciprocal_space_kcal_per_mol: components.reciprocal_space_kcal_per_mol,
        self_kcal_per_mol: components.self_kcal_per_mol,
        pair_correction_kcal_per_mol: components.pair_correction_kcal_per_mol,
        total_kcal_per_mol: components.total_kcal_per_mol(),
        reserved: [0; 4],
    };
    Ok(ProviderCandidate {
        energy,
        forces: result.forces_kcal_per_mol_angstrom,
        force_output,
    })
}

unsafe fn validate_error_output(
    pointer: *mut DirectEwaldErrorV1,
) -> Result<(DirectEwaldErrorV1, MemoryRange), i32> {
    let Some(range) = checked_range(pointer.cast_const(), 1, "error output is null")
        .map_err(|failure| failure.status)?
    else {
        return Err(STATUS_INVALID_ARGUMENT);
    };
    // SAFETY: The descriptor pointer was checked for non-nullness and natural
    // alignment and the private caller guarantees initialized storage.
    let output = unsafe { ptr::read(pointer) };
    if validate_header::<DirectEwaldErrorV1>(
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
    pointer: *mut DirectEwaldErrorV1,
    code: DirectEwaldErrorCodeV1,
    detail: &str,
) {
    let mut output = DirectEwaldErrorV1 {
        struct_size: u32::try_from(size_of::<DirectEwaldErrorV1>()).unwrap_or(0),
        abi_version: DIRECT_EWALD_PROVIDER_ABI_VERSION,
        typed_code: code as i32,
        reserved0: 0,
        detail: [0; DIRECT_EWALD_ERROR_CAPACITY],
        reserved: [0; 4],
    };
    let bytes = detail.as_bytes();
    let copy_length = bytes.len().min(DIRECT_EWALD_ERROR_CAPACITY - 1);
    output.detail[..copy_length].copy_from_slice(&bytes[..copy_length]);
    // SAFETY: The entry point validates writable, aligned error storage before
    // reaching this helper. The complete descriptor is committed at once.
    unsafe { ptr::write(pointer, output) };
}

unsafe fn commit_candidate(candidate: ProviderCandidate, energy_pointer: *mut DirectEwaldEnergyV1) {
    if let Some(output) = candidate.force_output {
        for (atom, force) in candidate.forces.into_iter().enumerate() {
            // SAFETY: All three non-overlapping channels were validated for the
            // atom count before evaluation; no fallible work remains.
            unsafe {
                output.x.add(atom).write(force[0]);
                output.y.add(atom).write(force[1]);
                output.z.add(atom).write(force[2]);
            }
        }
    }
    // SAFETY: Energy storage was validated and is disjoint from every force
    // channel. This is the final infallible step of the transaction.
    unsafe { ptr::write(energy_pointer, candidate.energy) };
}

#[no_mangle]
pub extern "C" fn bg_rust_direct_ewald_provider_abi_version_v1() -> u32 {
    DIRECT_EWALD_PROVIDER_ABI_VERSION
}

/// Evaluate frozen direct-Ewald v1 through the hidden Rust CPU provider ABI.
///
/// # Safety
/// Every descriptor and non-null channel must remain initialized and valid for
/// its declared extent for the duration of this call. Mutable output regions
/// must not overlap each other or any input region.
#[no_mangle]
pub unsafe extern "C" fn bg_rust_direct_ewald_evaluate_v1(
    system: *const DirectEwaldSystemV1,
    model: *const DirectEwaldModelV1,
    compute_forces: u8,
    out_energy: *mut DirectEwaldEnergyV1,
    out_forces: *mut DirectEwaldForceOutputV1,
    out_error: *mut DirectEwaldErrorV1,
) -> i32 {
    // SAFETY: This validates the raw pointer before reading the initialized
    // output descriptor supplied by the private C++ caller.
    let (_error_output, error_range) = match unsafe { validate_error_output(out_error) } {
        Ok(validated) => validated,
        Err(status) => return status,
    };

    let outcome = catch_unwind(AssertUnwindSafe(|| {
        // SAFETY: All raw-pointer validation and copying is contained inside
        // the implementation before references or output writes are formed.
        unsafe {
            evaluate_provider_impl(
                system,
                model,
                compute_forces,
                out_energy,
                out_forces,
                error_range,
            )
        }
    }));
    match outcome {
        Ok(Ok(candidate)) => {
            // SAFETY: Candidate construction validated all output regions and
            // no fallible operations remain in the commit path.
            unsafe { commit_candidate(candidate, out_energy) };
            // SAFETY: Error storage was validated before evaluation.
            unsafe { write_provider_error(out_error, DirectEwaldErrorCodeV1::None, "") };
            STATUS_OK
        }
        Ok(Err(failure)) => {
            if failure.may_write_error {
                // SAFETY: Error storage was validated before evaluation.
                unsafe { write_provider_error(out_error, failure.code, &failure.detail) };
            }
            failure.status
        }
        Err(_) => {
            // SAFETY: Error storage was validated before panic containment.
            unsafe {
                write_provider_error(
                    out_error,
                    DirectEwaldErrorCodeV1::None,
                    "rust direct-Ewald provider panicked",
                )
            };
            STATUS_INTERNAL_ERROR
        }
    }
}

#[cfg(test)]
mod tests {
    use super::{
        accurate_charge_square_sum, accurate_order_independent_sum, cell_volume,
        evaluate_real_space, minimum_image, reduce_to_primary_cell,
        scaled_reciprocal_force_component, validate, DirectEwaldEnergyV1, DirectEwaldErrorCodeV1,
        DirectEwaldErrorV1, DirectEwaldForceOutputV1, DirectEwaldModelV1, DirectEwaldPairRuleV1,
        DirectEwaldSystemV1, EwaldEnergyComponents, EwaldErrorCode, EwaldEvaluation, EwaldInput,
        OrthorhombicCell, PairExclusion, Position, CHARGE_NORMALIZATION_SCALE_E,
        COULOMB_KCAL_ANGSTROM_PER_MOL_E2, DIRECT_EWALD_ERROR_CAPACITY,
        DIRECT_EWALD_PROVIDER_ABI_VERSION, MAX_EVALUATION_WORK_UNITS, STATUS_INVALID_ARGUMENT,
        STATUS_NUMERICAL_ERROR, STATUS_OK,
    };
    use core::mem::{align_of, size_of};
    use core::ptr;

    #[test]
    fn provider_abi_layout_is_frozen() {
        assert_eq!(size_of::<DirectEwaldSystemV1>(), 80);
        assert_eq!(size_of::<DirectEwaldPairRuleV1>(), 40);
        assert_eq!(size_of::<DirectEwaldModelV1>(), 128);
        assert_eq!(size_of::<DirectEwaldEnergyV1>(), 80);
        assert_eq!(size_of::<DirectEwaldForceOutputV1>(), 72);
        assert_eq!(size_of::<DirectEwaldErrorV1>(), 304);
        assert_eq!(align_of::<DirectEwaldSystemV1>(), 8);
        assert_eq!(align_of::<DirectEwaldPairRuleV1>(), 8);
        assert_eq!(align_of::<DirectEwaldModelV1>(), 8);
        assert_eq!(align_of::<DirectEwaldEnergyV1>(), 8);
        assert_eq!(align_of::<DirectEwaldForceOutputV1>(), 8);
        assert_eq!(align_of::<DirectEwaldErrorV1>(), 8);
    }

    #[test]
    fn provider_rejects_a_misaligned_descriptor_without_reading_it() {
        let model = DirectEwaldModelV1 {
            struct_size: u32::try_from(size_of::<DirectEwaldModelV1>()).unwrap(),
            abi_version: DIRECT_EWALD_PROVIDER_ABI_VERSION,
            cell_lengths_angstrom: [10.0; 3],
            alpha_per_angstrom: 0.3,
            real_space_cutoff_angstrom: 4.0,
            reciprocal_max_indices: [1; 3],
            reserved0: 0,
            dielectric: 1.0,
            minimum_pair_distance_angstrom: 1.0e-8,
            pair_rule_count: 0,
            pair_rules: ptr::null(),
            reserved: [0; 4],
        };
        let mut energy = DirectEwaldEnergyV1 {
            struct_size: u32::try_from(size_of::<DirectEwaldEnergyV1>()).unwrap(),
            abi_version: DIRECT_EWALD_PROVIDER_ABI_VERSION,
            real_space_kcal_per_mol: 101.0,
            reciprocal_space_kcal_per_mol: 102.0,
            self_kcal_per_mol: 103.0,
            pair_correction_kcal_per_mol: 104.0,
            total_kcal_per_mol: 105.0,
            reserved: [0; 4],
        };
        let mut error = DirectEwaldErrorV1 {
            struct_size: u32::try_from(size_of::<DirectEwaldErrorV1>()).unwrap(),
            abi_version: DIRECT_EWALD_PROVIDER_ABI_VERSION,
            typed_code: -1,
            reserved0: 0,
            detail: [0; DIRECT_EWALD_ERROR_CAPACITY],
            reserved: [0; 4],
        };
        let mut storage =
            vec![0_u8; size_of::<DirectEwaldSystemV1>() + align_of::<DirectEwaldSystemV1>()];
        let offset = (0..align_of::<DirectEwaldSystemV1>())
            .find(|offset| {
                (storage.as_ptr() as usize + offset) % align_of::<DirectEwaldSystemV1>() != 0
            })
            .expect("an alignment greater than one has a misaligned offset");
        let misaligned = storage.as_mut_ptr().wrapping_add(offset).cast();
        // SAFETY: The system pointer is intentionally misaligned. The ABI must
        // reject it based on its address without dereferencing it; all output
        // descriptors are valid and initialized.
        let status = unsafe {
            super::bg_rust_direct_ewald_evaluate_v1(
                misaligned,
                &model,
                0,
                &mut energy,
                ptr::null_mut(),
                &mut error,
            )
        };
        assert_eq!(status, STATUS_INVALID_ARGUMENT);
        assert_eq!(error.typed_code, DirectEwaldErrorCodeV1::None as i32);
        assert_eq!(energy.total_kcal_per_mol.to_bits(), 105.0_f64.to_bits());
    }

    fn frozen_provider_evaluation() -> (DirectEwaldEnergyV1, Vec<[f64; 3]>) {
        let position_x = [1.25, 5.1, 10.2, 15.4];
        let position_y = [2.5, 3.2, 12.3, 17.1];
        let position_z = [3.75, 8.4, 7.7, 19.3];
        let charges = [0.7, -0.4, -0.6, 0.300_000_000_000_000_04];
        let pair_rules = [
            DirectEwaldPairRuleV1 {
                atom_i: 0,
                atom_j: 1,
                coulomb_scale: 0.0,
                reserved: [0; 2],
            },
            DirectEwaldPairRuleV1 {
                atom_i: 2,
                atom_j: 3,
                coulomb_scale: 0.5,
                reserved: [0; 2],
            },
        ];
        let system = DirectEwaldSystemV1 {
            struct_size: u32::try_from(size_of::<DirectEwaldSystemV1>()).unwrap(),
            abi_version: DIRECT_EWALD_PROVIDER_ABI_VERSION,
            atom_count: charges.len(),
            position_x: position_x.as_ptr(),
            position_y: position_y.as_ptr(),
            position_z: position_z.as_ptr(),
            charge: charges.as_ptr(),
            reserved: [0; 4],
        };
        let model = DirectEwaldModelV1 {
            struct_size: u32::try_from(size_of::<DirectEwaldModelV1>()).unwrap(),
            abi_version: DIRECT_EWALD_PROVIDER_ABI_VERSION,
            cell_lengths_angstrom: [18.0, 20.0, 22.0],
            alpha_per_angstrom: 0.31,
            real_space_cutoff_angstrom: 8.9,
            reciprocal_max_indices: [5; 3],
            reserved0: 0,
            dielectric: 1.0,
            minimum_pair_distance_angstrom: 1.0e-8,
            pair_rule_count: pair_rules.len(),
            pair_rules: pair_rules.as_ptr(),
            reserved: [0; 4],
        };
        let mut energy = DirectEwaldEnergyV1 {
            struct_size: u32::try_from(size_of::<DirectEwaldEnergyV1>()).unwrap(),
            abi_version: DIRECT_EWALD_PROVIDER_ABI_VERSION,
            real_space_kcal_per_mol: f64::NAN,
            reciprocal_space_kcal_per_mol: f64::NAN,
            self_kcal_per_mol: f64::NAN,
            pair_correction_kcal_per_mol: f64::NAN,
            total_kcal_per_mol: f64::NAN,
            reserved: [0; 4],
        };
        let mut force_x = vec![f64::NAN; charges.len()];
        let mut force_y = vec![f64::NAN; charges.len()];
        let mut force_z = vec![f64::NAN; charges.len()];
        let mut force_output = DirectEwaldForceOutputV1 {
            struct_size: u32::try_from(size_of::<DirectEwaldForceOutputV1>()).unwrap(),
            abi_version: DIRECT_EWALD_PROVIDER_ABI_VERSION,
            capacity: charges.len(),
            x: force_x.as_mut_ptr(),
            y: force_y.as_mut_ptr(),
            z: force_z.as_mut_ptr(),
            reserved: [0; 4],
        };
        let mut error = DirectEwaldErrorV1 {
            struct_size: u32::try_from(size_of::<DirectEwaldErrorV1>()).unwrap(),
            abi_version: DIRECT_EWALD_PROVIDER_ABI_VERSION,
            typed_code: -1,
            reserved0: 0,
            detail: [0xff; DIRECT_EWALD_ERROR_CAPACITY],
            reserved: [0; 4],
        };
        // SAFETY: Every descriptor and channel is initialized and remains live
        // for the duration of this private-ABI test call.
        let status = unsafe {
            super::bg_rust_direct_ewald_evaluate_v1(
                &system,
                &model,
                1,
                &mut energy,
                &mut force_output,
                &mut error,
            )
        };
        assert_eq!(status, STATUS_OK);
        assert_eq!(error.typed_code, DirectEwaldErrorCodeV1::None as i32);
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
    fn provider_frozen_energy_and_force_bits_match() {
        let (energy, forces) = frozen_provider_evaluation();
        let actual_energy = [
            energy.real_space_kcal_per_mol,
            energy.reciprocal_space_kcal_per_mol,
            energy.self_kcal_per_mol,
            energy.pair_correction_kcal_per_mol,
            energy.total_kcal_per_mol,
        ];
        let expected_energy = [
            0xbfbe_3560_505c_8b5a,
            0x4044_21fc_c228_58dd,
            0xc04f_f151_251c_f865,
            0x4031_acb8_1f3a_00d4,
            0xc018_4098_1bfe_6b20,
        ];
        assert_eq!(actual_energy.map(f64::to_bits), expected_energy);
        let expected_forces = [
            [
                0xbf94_b039_bd76_cc80,
                0x3fd6_aa0d_9171_ed72,
                0x3fe6_5887_b557_df96,
            ],
            [
                0xbf96_a2ad_5015_fb00,
                0xbfcb_27e2_90ac_16a8,
                0x3fc7_b0e0_6de8_1818,
            ],
            [
                0x3fd0_4eaa_3c83_bf1c,
                0x3fc8_6025_9fdc_0bfa,
                0xbfd4_8c1a_9531_1f4a,
            ],
            [
                0xbfcb_32f7_9755_e5ae,
                0xbfd5_462f_1909_e822,
                0xbfe1_feb2_8639_55fd,
            ],
        ];
        for (actual, expected) in forces.iter().zip(expected_forces) {
            assert_eq!(actual.map(f64::to_bits), expected);
        }
    }

    #[test]
    fn provider_repeats_identical_bits() {
        let first = frozen_provider_evaluation();
        let second = frozen_provider_evaluation();
        assert_eq!(
            [
                first.0.real_space_kcal_per_mol,
                first.0.reciprocal_space_kcal_per_mol,
                first.0.self_kcal_per_mol,
                first.0.pair_correction_kcal_per_mol,
                first.0.total_kcal_per_mol,
            ]
            .map(f64::to_bits),
            [
                second.0.real_space_kcal_per_mol,
                second.0.reciprocal_space_kcal_per_mol,
                second.0.self_kcal_per_mol,
                second.0.pair_correction_kcal_per_mol,
                second.0.total_kcal_per_mol,
            ]
            .map(f64::to_bits)
        );
        assert_eq!(
            first
                .1
                .iter()
                .flat_map(|force| force.map(f64::to_bits))
                .collect::<Vec<_>>(),
            second
                .1
                .iter()
                .flat_map(|force| force.map(f64::to_bits))
                .collect::<Vec<_>>()
        );
    }

    #[test]
    fn energy_only_path_has_identical_bits_without_force_storage() {
        let mut input = EwaldInput::new(
            vec![Position::default(), Position::new(1.3, 0.4, 0.7)],
            vec![1.0, -1.0],
            OrthorhombicCell {
                lengths_angstrom: [10.0, 12.0, 14.0],
            },
        );
        input.settings.real_space_cutoff_angstrom = 4.0;
        input.settings.reciprocal_max_indices = [2, 2, 2];
        let with_forces = super::evaluate(&input).expect("full evaluation must succeed");
        let energy_only = super::evaluate_with_force_option(&input, false)
            .expect("energy-only evaluation must succeed");
        assert!(energy_only.forces_kcal_per_mol_angstrom.is_empty());
        let energy_bits = |energy: EwaldEnergyComponents| {
            [
                energy.real_space_kcal_per_mol.to_bits(),
                energy.reciprocal_space_kcal_per_mol.to_bits(),
                energy.self_kcal_per_mol.to_bits(),
                energy.pair_correction_kcal_per_mol.to_bits(),
                energy.total_kcal_per_mol().to_bits(),
            ]
        };
        assert_eq!(
            energy_bits(with_forces.energy),
            energy_bits(energy_only.energy)
        );
    }

    #[test]
    fn provider_failure_leaves_energy_and_forces_untouched() {
        let position_x = [0.0, 1.0];
        let position_y = [0.0; 2];
        let position_z = [0.0; 2];
        let charges = [1.0, 1.0];
        let system = DirectEwaldSystemV1 {
            struct_size: u32::try_from(size_of::<DirectEwaldSystemV1>()).unwrap(),
            abi_version: DIRECT_EWALD_PROVIDER_ABI_VERSION,
            atom_count: 2,
            position_x: position_x.as_ptr(),
            position_y: position_y.as_ptr(),
            position_z: position_z.as_ptr(),
            charge: charges.as_ptr(),
            reserved: [0; 4],
        };
        let model = DirectEwaldModelV1 {
            struct_size: u32::try_from(size_of::<DirectEwaldModelV1>()).unwrap(),
            abi_version: DIRECT_EWALD_PROVIDER_ABI_VERSION,
            cell_lengths_angstrom: [10.0; 3],
            alpha_per_angstrom: 0.3,
            real_space_cutoff_angstrom: 4.0,
            reciprocal_max_indices: [1; 3],
            reserved0: 0,
            dielectric: 1.0,
            minimum_pair_distance_angstrom: 1.0e-8,
            pair_rule_count: 0,
            pair_rules: ptr::null(),
            reserved: [0; 4],
        };
        let mut energy = DirectEwaldEnergyV1 {
            struct_size: u32::try_from(size_of::<DirectEwaldEnergyV1>()).unwrap(),
            abi_version: DIRECT_EWALD_PROVIDER_ABI_VERSION,
            real_space_kcal_per_mol: 101.0,
            reciprocal_space_kcal_per_mol: 102.0,
            self_kcal_per_mol: 103.0,
            pair_correction_kcal_per_mol: 104.0,
            total_kcal_per_mol: 105.0,
            reserved: [0; 4],
        };
        let energy_bits = [
            energy.real_space_kcal_per_mol,
            energy.reciprocal_space_kcal_per_mol,
            energy.self_kcal_per_mol,
            energy.pair_correction_kcal_per_mol,
            energy.total_kcal_per_mol,
        ]
        .map(f64::to_bits);
        let mut force_x = [201.0; 2];
        let mut force_y = [202.0; 2];
        let mut force_z = [203.0; 2];
        let mut force_output = DirectEwaldForceOutputV1 {
            struct_size: u32::try_from(size_of::<DirectEwaldForceOutputV1>()).unwrap(),
            abi_version: DIRECT_EWALD_PROVIDER_ABI_VERSION,
            capacity: 2,
            x: force_x.as_mut_ptr(),
            y: force_y.as_mut_ptr(),
            z: force_z.as_mut_ptr(),
            reserved: [0; 4],
        };
        let mut error = DirectEwaldErrorV1 {
            struct_size: u32::try_from(size_of::<DirectEwaldErrorV1>()).unwrap(),
            abi_version: DIRECT_EWALD_PROVIDER_ABI_VERSION,
            typed_code: -1,
            reserved0: 0,
            detail: [0; DIRECT_EWALD_ERROR_CAPACITY],
            reserved: [0; 4],
        };
        // SAFETY: Every descriptor and channel is initialized and remains live
        // for the duration of this private-ABI test call.
        let status = unsafe {
            super::bg_rust_direct_ewald_evaluate_v1(
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
            DirectEwaldErrorCodeV1::NonNeutralSystem as i32
        );
        assert_eq!(
            [
                energy.real_space_kcal_per_mol,
                energy.reciprocal_space_kcal_per_mol,
                energy.self_kcal_per_mol,
                energy.pair_correction_kcal_per_mol,
                energy.total_kcal_per_mol,
            ]
            .map(f64::to_bits),
            energy_bits
        );
        assert_eq!(force_x, [201.0; 2]);
        assert_eq!(force_y, [202.0; 2]);
        assert_eq!(force_z, [203.0; 2]);
    }

    #[test]
    fn minimum_image_exact_half_is_image_stable_and_atom_order_antisymmetric() {
        let cell = OrthorhombicCell {
            lengths_angstrom: [10.0, 12.0, 14.0],
        };
        let positive = minimum_image(Position::new(5.0, 0.0, 0.0), Position::default(), cell);
        let negative = minimum_image(Position::new(-5.0, 0.0, 0.0), Position::default(), cell);
        let swapped = minimum_image(Position::default(), Position::new(5.0, 0.0, 0.0), cell);
        assert_eq!(positive[0].to_bits(), 5.0_f64.to_bits());
        assert_eq!(negative[0].to_bits(), 5.0_f64.to_bits());
        assert_eq!(swapped[0].to_bits(), (-5.0_f64).to_bits());
    }

    #[test]
    fn primary_cell_reduction_preserves_rounded_signed_residual() {
        let cell = OrthorhombicCell {
            lengths_angstrom: [10.0, 12.0, 14.0],
        };
        let reduced = reduce_to_primary_cell(Position::new(-1.0e-16, 0.0, 0.0), cell);
        assert_eq!(reduced[0].to_bits(), (-1.0e-16_f64).to_bits());
    }

    #[test]
    fn strongly_damped_subnormal_real_force_is_rejected() {
        let mut input = EwaldInput::new(
            vec![Position::default(), Position::new(9.0e7, 0.0, 0.0)],
            vec![16.0, -16.0],
            OrthorhombicCell {
                lengths_angstrom: [1.0e9; 3],
            },
        );
        input.settings.alpha_per_angstrom = 3.0e-7;
        input.settings.real_space_cutoff_angstrom = 1.0e8;
        input.settings.dielectric = 1.0e-12;
        validate(&input).expect("strongly damped fixture is inside the numeric envelope");
        let mut result = EwaldEvaluation {
            energy: EwaldEnergyComponents::default(),
            forces_kcal_per_mol_angstrom: vec![[0.0; 3]; 2],
        };
        let error = evaluate_real_space(
            &input,
            COULOMB_KCAL_ANGSTROM_PER_MOL_E2 / input.settings.dielectric,
            true,
            &mut result,
        )
        .expect_err("subnormal real damping must fail closed");
        assert_eq!(error.code(), EwaldErrorCode::DampingUnderflow);
    }

    #[test]
    fn strongly_damped_subunit_real_energy_remains_representable() {
        let mut input = EwaldInput::new(
            vec![Position::default(), Position::new(2.58e-5, 0.0, 0.0)],
            vec![1.0e-12, -1.0e-12],
            OrthorhombicCell {
                lengths_angstrom: [1.0; 3],
            },
        );
        input.settings.alpha_per_angstrom = 1.0e6;
        input.settings.real_space_cutoff_angstrom = 2.59e-5;
        input.settings.dielectric = 1.0e12;
        validate(&input).expect("subunit damping fixture is inside the numeric envelope");
        let mut result = EwaldEvaluation {
            energy: EwaldEnergyComponents::default(),
            forces_kcal_per_mol_angstrom: vec![[0.0; 3]; 2],
        };
        evaluate_real_space(
            &input,
            COULOMB_KCAL_ANGSTROM_PER_MOL_E2 / input.settings.dielectric,
            true,
            &mut result,
        )
        .expect("real-space evaluation remains finite");
        assert!(result.energy.real_space_kcal_per_mol.is_subnormal());
        assert!(result.energy.real_space_kcal_per_mol.is_sign_negative());
    }

    #[test]
    fn strongly_damped_subunit_real_force_remains_representable() {
        let mut input = EwaldInput::new(
            vec![Position::default(), Position::new(2.62e-5, 0.0, 0.0)],
            vec![1.0e-12, -1.0e-12],
            OrthorhombicCell {
                lengths_angstrom: [1.0; 3],
            },
        );
        input.settings.alpha_per_angstrom = 1.0e6;
        input.settings.real_space_cutoff_angstrom = 2.63e-5;
        input.settings.dielectric = 1.0e12;
        validate(&input).expect("subunit force fixture is inside the numeric envelope");
        let mut result = EwaldEvaluation {
            energy: EwaldEnergyComponents::default(),
            forces_kcal_per_mol_angstrom: vec![[0.0; 3]; 2],
        };
        evaluate_real_space(
            &input,
            COULOMB_KCAL_ANGSTROM_PER_MOL_E2 / input.settings.dielectric,
            true,
            &mut result,
        )
        .expect("real-space evaluation remains finite");
        assert!(result.forces_kcal_per_mol_angstrom[0][0].is_subnormal());
        assert!(result.forces_kcal_per_mol_angstrom[0][0].is_sign_positive());
    }

    #[test]
    fn reciprocal_wave_scaling_rescues_a_representable_subnormal_force() {
        let reciprocal_force_factor =
            COULOMB_KCAL_ANGSTROM_PER_MOL_E2 * 4.0 * core::f64::consts::PI / 1.0e24;
        let wave_component = core::f64::consts::TAU / 1.0e-6;
        let wave2 = wave_component * wave_component;
        let phase_sin = 6.0e-291;
        let exponential = libm::exp(-wave2 / (4.0 * 1.0e12));
        let underflowed_old_order =
            (reciprocal_force_factor / wave2) * phase_sin * wave_component * exponential;
        let force = scaled_reciprocal_force_component(
            reciprocal_force_factor,
            wave_component,
            wave2,
            1.0,
            (1.0, 0.0),
            (phase_sin, 1.0),
            exponential,
        );
        assert_eq!(underflowed_old_order.to_bits(), 0.0_f64.to_bits());
        assert!(force.is_subnormal());
        assert!(force.is_sign_positive());
    }

    #[test]
    fn power_of_two_charge_normalization_is_exact_and_neutrality_preserving() {
        let charges = [0.7, -0.4, -0.6, 0.300_000_000_000_000_04];
        let normalized = charges.map(|charge| charge / CHARGE_NORMALIZATION_SCALE_E);
        for (&charge, &scaled) in charges.iter().zip(&normalized) {
            assert_eq!(
                (scaled * CHARGE_NORMALIZATION_SCALE_E).to_bits(),
                charge.to_bits()
            );
        }
        assert_eq!(accurate_order_independent_sum(&normalized).to_bits(), 0);
    }

    #[test]
    fn charge_square_sum_is_atom_order_independent() {
        let first = [
            13.249_214_005_789_042,
            -13.249_214_005_789_042,
            14.375_751_207_670_909,
            -14.375_751_207_670_909,
            8.071_499_065_172_876,
            -8.071_499_065_172_876,
        ];
        let mut reversed = first;
        reversed.reverse();
        assert_eq!(
            accurate_charge_square_sum(&first).to_bits(),
            accurate_charge_square_sum(&reversed).to_bits()
        );
    }

    #[test]
    fn raw_pair_rule_work_is_rejected_before_tree_validation() {
        let atom_count = 100;
        let mut input = EwaldInput::new(
            vec![Position::default(); atom_count],
            vec![0.0; atom_count],
            OrthorhombicCell {
                lengths_angstrom: [20.0; 3],
            },
        );
        input.settings.reciprocal_max_indices = [1; 3];
        let pair_count = atom_count * (atom_count - 1) / 2;
        let phase_work = atom_count * 26 * 2;
        let rows_to_exceed_cap = (MAX_EVALUATION_WORK_UNITS - 7 * pair_count - phase_work) / 7 + 1;
        input.exclusions = vec![
            PairExclusion {
                atom_i: 0,
                atom_j: 1,
            };
            rows_to_exceed_cap
        ];
        let Err(error) = validate(&input) else {
            panic!("raw rule rows must exceed the work cap");
        };
        assert_eq!(error.code(), EwaldErrorCode::CapacityExceeded);
    }

    #[test]
    fn large_radial_force_restores_a_subnormal_cartesian_component() {
        let mut input = EwaldInput::new(
            vec![
                Position::default(),
                Position::new(f64::from_bits(1), 100.0, 0.0),
            ],
            vec![16.0, -16.0],
            OrthorhombicCell {
                lengths_angstrom: [1.0e9; 3],
            },
        );
        input.settings.alpha_per_angstrom = 1.0e-12;
        input.settings.real_space_cutoff_angstrom = 101.0;
        input.settings.dielectric = 1.0e-12;
        validate(&input).expect("subnormal component fixture is inside the numeric envelope");
        let mut result = EwaldEvaluation {
            energy: EwaldEnergyComponents::default(),
            forces_kcal_per_mol_angstrom: vec![[0.0; 3]; 2],
        };
        evaluate_real_space(
            &input,
            COULOMB_KCAL_ANGSTROM_PER_MOL_E2 / input.settings.dielectric,
            true,
            &mut result,
        )
        .expect("real-space evaluation remains finite");
        assert!(result.forces_kcal_per_mol_angstrom[0][0].is_subnormal());
        assert!(result.forces_kcal_per_mol_angstrom[0][0].is_sign_positive());
    }

    #[test]
    fn compensated_charge_sum_is_permutation_independent() {
        let tiny = 2.0_f64.powi(-54);
        let first = accurate_order_independent_sum(&[1.0, tiny, -1.0]);
        let second = accurate_order_independent_sum(&[1.0, -1.0, tiny]);
        assert_eq!(first.to_bits(), second.to_bits());
        assert_eq!(first.to_bits(), tiny.to_bits());
    }

    #[test]
    fn volume_avoids_axis_order_intermediate_overflow() {
        let first = cell_volume(OrthorhombicCell {
            lengths_angstrom: [1.0e200, 1.0e200, 1.0e-200],
        });
        let second = cell_volume(OrthorhombicCell {
            lengths_angstrom: [1.0e200, 1.0e-200, 1.0e200],
        });
        assert!(first.is_finite());
        assert_eq!(first.to_bits(), second.to_bits());
        assert!((first - 1.0e200).abs() / 1.0e200 < 2.0e-15);
    }
}
