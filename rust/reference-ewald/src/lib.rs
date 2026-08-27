//! Independent scalar direct-Ewald electrostatics for tiny validation fixtures.
//!
//! This standalone crate deliberately sits outside the production Rust workspace
//! and the consumed fixed64 CPU-v7 source closure. It has no dependency on native
//! compute, accelerator code, runtime state, or an external MD engine.

use std::cmp::Ordering;
use std::collections::{BTreeMap, BTreeSet};
use std::error::Error;
use std::fmt;

/// Coulomb conversion factor in kcal·angstrom/(mol·e²).
pub const COULOMB_KCAL_ANGSTROM_PER_MOL_E2: f64 = 332.063_713_299;
/// Frozen semantic version for the equations and traversal order in this crate.
pub const EWALD_SCHEMA_ID: &str = "betelgeuze.reference_direct_ewald/1.0.0";

const MAX_ATOM_COUNT: usize = 4_096;
const MAX_RECIPROCAL_INDEX: i32 = 32;
const MAX_NEUTRALITY_TOLERANCE_E: f64 = 1.0e-8;
const MAX_EVALUATION_WORK_UNITS: usize = 10_000_000;
const MAX_ABSOLUTE_COORDINATE_ANGSTROM: f64 = 1.0e12;
const MIN_CELL_LENGTH_ANGSTROM: f64 = 1.0e-6;
const MAX_CELL_LENGTH_ANGSTROM: f64 = 1.0e9;
const MIN_NONZERO_ABSOLUTE_CHARGE_E: f64 = 1.0e-12;
const MAX_ABSOLUTE_CHARGE_E: f64 = 16.0;
const MIN_ALPHA_PER_ANGSTROM: f64 = 1.0e-12;
const MAX_ALPHA_PER_ANGSTROM: f64 = 1.0e6;
const MIN_CUTOFF_ANGSTROM: f64 = 1.0e-8;
const MAX_CUTOFF_ANGSTROM: f64 = 1.0e8;
const MIN_DIELECTRIC: f64 = 1.0e-12;
const MAX_DIELECTRIC: f64 = 1.0e12;
const MIN_SUPPORTED_PAIR_DISTANCE_ANGSTROM: f64 = 1.0e-8;
const MAX_SUPPORTED_PAIR_DISTANCE_ANGSTROM: f64 = 1.0e3;

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
    pub neutrality_tolerance_elementary: f64,
}

impl Default for EwaldSettings {
    fn default() -> Self {
        Self {
            alpha_per_angstrom: 0.3,
            real_space_cutoff_angstrom: 8.0,
            reciprocal_max_indices: [5, 5, 5],
            dielectric: 1.0,
            minimum_pair_distance_angstrom: 1.0e-8,
            neutrality_tolerance_elementary: 1.0e-12,
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
    PairBelowMinimumDistance,
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

    #[must_use]
    pub fn detail(&self) -> &str {
        &self.detail
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
    let pair_rules = validate(input)?;
    let mut result = EwaldEvaluation {
        energy: EwaldEnergyComponents::default(),
        forces_kcal_per_mol_angstrom: vec![[0.0; 3]; input.positions.len()],
    };
    let coulomb_scale = COULOMB_KCAL_ANGSTROM_PER_MOL_E2 / input.settings.dielectric;
    evaluate_real_space(input, coulomb_scale, &mut result)?;
    evaluate_reciprocal_space(input, coulomb_scale, &mut result)?;
    let charge_square_sum = input
        .charges_elementary
        .iter()
        .map(|charge| charge * charge)
        .sum::<f64>();
    result.energy.self_kcal_per_mol =
        -coulomb_scale * input.settings.alpha_per_angstrom * charge_square_sum
            / libm::sqrt(core::f64::consts::PI);
    evaluate_pair_corrections(input, &pair_rules, coulomb_scale, &mut result)?;

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
    result: &mut EwaldEvaluation,
) -> Result<(), EwaldError> {
    let alpha = input.settings.alpha_per_angstrom;
    let minimum2 = input.settings.minimum_pair_distance_angstrom.powi(2);
    for atom_i in 0..input.positions.len() {
        for atom_j in (atom_i + 1)..input.positions.len() {
            let delta = minimum_image(input.positions[atom_i], input.positions[atom_j], input.cell);
            let distance2 = squared_norm(delta);
            if distance2 < minimum2 {
                return Err(EwaldError::new(
                    EwaldErrorCode::PairBelowMinimumDistance,
                    format!(
                        "pair ({atom_i},{atom_j}) is below {} angstrom",
                        input.settings.minimum_pair_distance_angstrom
                    ),
                ));
            }
            let distance = libm::sqrt(distance2);
            if distance <= input.settings.real_space_cutoff_angstrom {
                let charge_product =
                    input.charges_elementary[atom_i] * input.charges_elementary[atom_j];
                let alpha_distance = alpha * distance;
                let erfc_value = libm::erfc(alpha_distance);
                let exponential = libm::exp(-alpha_distance * alpha_distance);
                let charge_prefactor = coulomb_scale * charge_product;
                let pair_energy = if distance < 1.0 {
                    charge_prefactor * (erfc_value / distance)
                } else {
                    charge_prefactor * erfc_value / distance
                };
                checked_add(
                    &mut result.energy.real_space_kcal_per_mol,
                    pair_energy,
                    "real-space energy",
                )?;

                let gaussian_prefactor =
                    charge_prefactor * (2.0 * alpha / libm::sqrt(core::f64::consts::PI));
                let radial_force_magnitude = if distance < 1.0 {
                    charge_prefactor * (erfc_value / distance2)
                        + gaussian_prefactor * (exponential / distance)
                } else {
                    charge_prefactor * erfc_value / distance2
                        + gaussian_prefactor * exponential / distance
                };
                add_radial_pair_force(
                    &mut result.forces_kcal_per_mol_angstrom,
                    atom_i,
                    atom_j,
                    delta,
                    distance,
                    radial_force_magnitude,
                )?;
            }
        }
    }
    Ok(())
}

fn evaluate_reciprocal_space(
    input: &EwaldInput,
    coulomb_scale: f64,
    result: &mut EwaldEvaluation,
) -> Result<(), EwaldError> {
    let lengths = input.cell.lengths_angstrom;
    let volume = cell_volume(input.cell);
    let reciprocal_energy_factor = coulomb_scale * 2.0 * core::f64::consts::PI / volume;
    let reciprocal_force_factor = coulomb_scale * 4.0 * core::f64::consts::PI / volume;
    let alpha = input.settings.alpha_per_angstrom;
    let max_indices = input.settings.reciprocal_max_indices;
    let reduced_positions = input
        .positions
        .iter()
        .map(|position| reduce_to_primary_cell(*position, input.cell))
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
                let exponential = libm::exp(-wave2 / (4.0 * alpha * alpha));
                let mut structure_cos = 0.0;
                let mut structure_sin = 0.0;
                for (&charge, &position) in input.charges_elementary.iter().zip(&reduced_positions)
                {
                    let phase = dot(wave, position);
                    let (phase_sin, phase_cos) = libm::sincos(phase);
                    structure_cos += charge * phase_cos;
                    structure_sin += charge * phase_sin;
                }
                checked_add(
                    &mut result.energy.reciprocal_space_kcal_per_mol,
                    (reciprocal_energy_factor / wave2)
                        * (structure_cos * structure_cos + structure_sin * structure_sin)
                        * exponential,
                    "reciprocal-space energy",
                )?;
                for ((force, &charge), &position) in result
                    .forces_kcal_per_mol_angstrom
                    .iter_mut()
                    .zip(&input.charges_elementary)
                    .zip(&reduced_positions)
                {
                    let phase = dot(wave, position);
                    let (phase_sin, phase_cos) = libm::sincos(phase);
                    for axis in 0..3 {
                        checked_add(
                            &mut force[axis],
                            scaled_reciprocal_force_component(
                                reciprocal_force_factor,
                                wave[axis],
                                wave2,
                                charge,
                                (structure_cos, structure_sin),
                                (phase_sin, phase_cos),
                                exponential,
                            ),
                            "reciprocal force",
                        )?;
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
    result: &mut EwaldEvaluation,
) -> Result<(), EwaldError> {
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
        checked_add(
            &mut result.energy.pair_correction_kcal_per_mol,
            coulomb_scale * charge_product * correction_scale / distance,
            "pair-correction energy",
        )?;
        add_pair_force(
            &mut result.forces_kcal_per_mol_angstrom,
            atom_i,
            atom_j,
            delta,
            coulomb_scale * charge_product * correction_scale / (distance2 * distance),
        )?;
    }
    Ok(())
}

fn validate(input: &EwaldInput) -> Result<PairRules, EwaldError> {
    validate_atom_arrays(input)?;
    validate_cell(input.cell)?;
    validate_settings(input)?;
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
    let neutrality_tolerance = input.settings.neutrality_tolerance_elementary;
    if !neutrality_tolerance.is_finite()
        || !(0.0..=MAX_NEUTRALITY_TOLERANCE_E).contains(&neutrality_tolerance)
    {
        return Err(invalid_parameter(format!(
            "neutrality_tolerance_elementary must lie in [0,{MAX_NEUTRALITY_TOLERANCE_E}]"
        )));
    }
    let total_charge = accurate_order_independent_sum(&input.charges_elementary);
    if !total_charge.is_finite() || total_charge.abs() > neutrality_tolerance {
        return Err(EwaldError::new(
            EwaldErrorCode::NonNeutralSystem,
            format!(
                "total charge {total_charge} exceeds neutrality tolerance {neutrality_tolerance}"
            ),
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
        let raw = first[axis] - second[axis];
        delta[axis] = if compare_primary_axis_separation(first[axis], second[axis], length)
            == Ordering::Greater
        {
            if first[axis] > second[axis] {
                raw - length
            } else {
                raw + length
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
        } else {
            value
        };
    }
    reduced
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
        let raw = first[axis] - second[axis];
        let separation = compare_primary_axis_separation(first[axis], second[axis], length);
        if separation == Ordering::Equal {
            return Err(EwaldError::new(
                EwaldErrorCode::AmbiguousPairCorrectionImage,
                format!("pair correction is exactly half a cell on axis {axis}"),
            ));
        }
        delta[axis] = if separation == Ordering::Greater {
            if first[axis] > second[axis] {
                raw - length
            } else {
                raw + length
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
    let difference = high - low;
    let low_virtual = high - difference;
    let high_virtual = difference + low_virtual;
    let low_roundoff = low_virtual - low;
    let high_roundoff = high - high_virtual;
    let error = high_roundoff + low_roundoff;
    match difference.total_cmp(&(0.5 * length)) {
        Ordering::Equal => error.total_cmp(&0.0),
        ordering => ordering,
    }
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
    let total_work = pair_count
        .checked_add(pair_rule_count)
        .and_then(|work| work.checked_add(phase_work))
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

fn add_pair_force(
    forces: &mut [[f64; 3]],
    atom_i: usize,
    atom_j: usize,
    delta: [f64; 3],
    factor: f64,
) -> Result<(), EwaldError> {
    for axis in 0..3 {
        let component = factor * delta[axis];
        checked_add(&mut forces[atom_i][axis], component, "pair force")?;
        checked_add(&mut forces[atom_j][axis], -component, "pair force")?;
    }
    Ok(())
}

fn add_radial_pair_force(
    forces: &mut [[f64; 3]],
    atom_i: usize,
    atom_j: usize,
    delta: [f64; 3],
    distance: f64,
    radial_force_magnitude: f64,
) -> Result<(), EwaldError> {
    for axis in 0..3 {
        let component = if distance < 1.0 {
            (radial_force_magnitude / distance) * delta[axis]
        } else {
            (radial_force_magnitude * delta[axis]) / distance
        };
        checked_add(&mut forces[atom_i][axis], component, "radial pair force")?;
        checked_add(&mut forces[atom_j][axis], -component, "radial pair force")?;
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

#[cfg(test)]
mod tests {
    use super::{
        accurate_order_independent_sum, cell_volume, evaluate_real_space, minimum_image,
        reduce_to_primary_cell, scaled_reciprocal_force_component, validate, EwaldEnergyComponents,
        EwaldEvaluation, EwaldInput, OrthorhombicCell, Position, COULOMB_KCAL_ANGSTROM_PER_MOL_E2,
    };

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
    fn strongly_damped_real_force_retains_a_representable_subnormal_component() {
        let mut input = EwaldInput::new(
            vec![Position::default(), Position::new(1.0e8, 0.0, 0.0)],
            vec![16.0, -16.0],
            OrthorhombicCell {
                lengths_angstrom: [1.0e9; 3],
            },
        );
        input.settings.alpha_per_angstrom = 2.7e-7;
        input.settings.real_space_cutoff_angstrom = 1.0e8;
        input.settings.dielectric = 1.0e-12;
        validate(&input).expect("strongly damped fixture is inside the numeric envelope");
        let mut result = EwaldEvaluation {
            energy: EwaldEnergyComponents::default(),
            forces_kcal_per_mol_angstrom: vec![[0.0; 3]; 2],
        };
        evaluate_real_space(
            &input,
            COULOMB_KCAL_ANGSTROM_PER_MOL_E2 / input.settings.dielectric,
            &mut result,
        )
        .expect("real-space evaluation remains finite");
        assert!(result.forces_kcal_per_mol_angstrom[0][0].is_subnormal());
        assert!(result.forces_kcal_per_mol_angstrom[0][0].is_sign_positive());
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
        input.settings.real_space_cutoff_angstrom = 2.58e-5;
        input.settings.dielectric = 1.0e12;
        validate(&input).expect("subunit damping fixture is inside the numeric envelope");
        let mut result = EwaldEvaluation {
            energy: EwaldEnergyComponents::default(),
            forces_kcal_per_mol_angstrom: vec![[0.0; 3]; 2],
        };
        evaluate_real_space(
            &input,
            COULOMB_KCAL_ANGSTROM_PER_MOL_E2 / input.settings.dielectric,
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
        input.settings.real_space_cutoff_angstrom = 2.62e-5;
        input.settings.dielectric = 1.0e12;
        validate(&input).expect("subunit force fixture is inside the numeric envelope");
        let mut result = EwaldEvaluation {
            energy: EwaldEnergyComponents::default(),
            forces_kcal_per_mol_angstrom: vec![[0.0; 3]; 2],
        };
        evaluate_real_space(
            &input,
            COULOMB_KCAL_ANGSTROM_PER_MOL_E2 / input.settings.dielectric,
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
