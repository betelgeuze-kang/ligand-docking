//! Independent scalar direct-Ewald electrostatics for tiny validation fixtures.
//!
//! This standalone crate deliberately sits outside the production Rust workspace
//! and the consumed fixed64 CPU-v7 source closure. It has no dependency on native
//! compute, accelerator code, runtime state, or an external MD engine.

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
    exclusions: BTreeSet<PairKey>,
    scales: BTreeMap<PairKey, f64>,
}

/// Evaluate direct Ewald electrostatics using scalar binary64 arithmetic.
///
/// Real-space pairs use lexicographic `i < j` order and the half-open minimum
/// image. Reciprocal vectors use nested `nx`, `ny`, `nz` ascending order over
/// the inclusive configured bounds, omitting only `(0,0,0)`. Structure factors
/// and per-vector forces traverse atoms in input order.
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
            / core::f64::consts::PI.sqrt();
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
            let distance = distance2.sqrt();
            if distance <= input.settings.real_space_cutoff_angstrom {
                let charge_product =
                    input.charges_elementary[atom_i] * input.charges_elementary[atom_j];
                let alpha_distance = alpha * distance;
                let erfc_value = libm::erfc(alpha_distance);
                let exponential = (-alpha_distance * alpha_distance).exp();
                let pair_energy = coulomb_scale * charge_product * erfc_value / distance;
                checked_add(
                    &mut result.energy.real_space_kcal_per_mol,
                    pair_energy,
                    "real-space energy",
                )?;

                let force_factor = coulomb_scale
                    * charge_product
                    * (erfc_value / (distance2 * distance)
                        + 2.0 * alpha * exponential / (core::f64::consts::PI.sqrt() * distance2));
                add_pair_force(
                    &mut result.forces_kcal_per_mol_angstrom,
                    atom_i,
                    atom_j,
                    delta,
                    force_factor,
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
    let volume = lengths[0] * lengths[1] * lengths[2];
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
                let damping = (-wave2 / (4.0 * alpha * alpha)).exp() / wave2;
                let mut structure_cos = 0.0;
                let mut structure_sin = 0.0;
                for (&charge, &position) in input.charges_elementary.iter().zip(&reduced_positions)
                {
                    let phase = dot(wave, position);
                    let (phase_sin, phase_cos) = phase.sin_cos();
                    structure_cos += charge * phase_cos;
                    structure_sin += charge * phase_sin;
                }
                checked_add(
                    &mut result.energy.reciprocal_space_kcal_per_mol,
                    reciprocal_energy_factor
                        * damping
                        * (structure_cos * structure_cos + structure_sin * structure_sin),
                    "reciprocal-space energy",
                )?;
                for ((force, &charge), &position) in result
                    .forces_kcal_per_mol_angstrom
                    .iter_mut()
                    .zip(&input.charges_elementary)
                    .zip(&reduced_positions)
                {
                    let phase = dot(wave, position);
                    let (phase_sin, phase_cos) = phase.sin_cos();
                    let factor = reciprocal_force_factor
                        * charge
                        * damping
                        * (structure_cos * phase_sin - structure_sin * phase_cos);
                    for axis in 0..3 {
                        checked_add(&mut force[axis], factor * wave[axis], "reciprocal force")?;
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
    for atom_i in 0..input.positions.len() {
        for atom_j in (atom_i + 1)..input.positions.len() {
            let pair = (atom_i, atom_j);
            let pair_scale = if pair_rules.exclusions.contains(&pair) {
                0.0
            } else if let Some(scale) = pair_rules.scales.get(&pair) {
                *scale
            } else {
                continue;
            };
            let delta = pair_correction_displacement(
                input.positions[atom_i],
                input.positions[atom_j],
                input.cell,
            );
            let distance2 = squared_norm(delta);
            let distance = distance2.sqrt();
            let charge_product =
                input.charges_elementary[atom_i] * input.charges_elementary[atom_j];
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
    }
    Ok(())
}

fn validate(input: &EwaldInput) -> Result<PairRules, EwaldError> {
    validate_atom_arrays(input)?;
    validate_cell(input.cell)?;
    validate_settings(input)?;
    validate_pair_rules(input)
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
    }
    for (atom, charge) in input.charges_elementary.iter().enumerate() {
        if !charge.is_finite() {
            return Err(EwaldError::new(
                EwaldErrorCode::NonFiniteCharge,
                format!("atom {atom} charge is not finite"),
            ));
        }
    }
    Ok(())
}

fn validate_cell(cell: OrthorhombicCell) -> Result<(), EwaldError> {
    for (axis, length) in cell.lengths_angstrom.iter().copied().enumerate() {
        if !length.is_finite() || length <= 0.0 {
            return Err(EwaldError::new(
                EwaldErrorCode::InvalidCell,
                format!("cell length axis {axis} must be finite and positive"),
            ));
        }
    }
    let volume = cell.lengths_angstrom.into_iter().product::<f64>();
    if !volume.is_finite() || volume <= 0.0 {
        return Err(EwaldError::new(
            EwaldErrorCode::InvalidCell,
            "cell volume must be finite and positive",
        ));
    }
    Ok(())
}

fn validate_settings(input: &EwaldInput) -> Result<(), EwaldError> {
    require_positive(input.settings.alpha_per_angstrom, "alpha_per_angstrom")?;
    require_positive(
        input.settings.real_space_cutoff_angstrom,
        "real_space_cutoff_angstrom",
    )?;
    require_positive(input.settings.dielectric, "dielectric")?;
    require_positive(
        input.settings.minimum_pair_distance_angstrom,
        "minimum_pair_distance_angstrom",
    )?;
    let neutrality_tolerance = input.settings.neutrality_tolerance_elementary;
    if !neutrality_tolerance.is_finite()
        || !(0.0..=MAX_NEUTRALITY_TOLERANCE_E).contains(&neutrality_tolerance)
    {
        return Err(invalid_parameter(format!(
            "neutrality_tolerance_elementary must lie in [0,{MAX_NEUTRALITY_TOLERANCE_E}]"
        )));
    }
    let total_charge = input.charges_elementary.iter().sum::<f64>();
    if total_charge.abs() > neutrality_tolerance {
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
    Ok(PairRules { exclusions, scales })
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
        delta[axis] = raw - length * (raw / length + 0.5).floor();
    }
    delta
}

fn reduce_to_primary_cell(position: Position, cell: OrthorhombicCell) -> [f64; 3] {
    let components = position.components();
    let mut reduced = [0.0; 3];
    for axis in 0..3 {
        let value = components[axis].rem_euclid(cell.lengths_angstrom[axis]);
        reduced[axis] = if value == 0.0 { 0.0 } else { value };
    }
    reduced
}

fn pair_correction_displacement(
    first: Position,
    second: Position,
    cell: OrthorhombicCell,
) -> [f64; 3] {
    let first = reduce_to_primary_cell(first, cell);
    let second = reduce_to_primary_cell(second, cell);
    let mut delta = [0.0; 3];
    for axis in 0..3 {
        let length = cell.lengths_angstrom[axis];
        let raw = first[axis] - second[axis];
        let minimum = raw - length * (raw / length + 0.5).floor();
        delta[axis] = if minimum.to_bits() == (-0.5 * length).to_bits() && raw > 0.0 {
            0.5 * length
        } else {
            minimum
        };
    }
    delta
}

fn dot(first: [f64; 3], second: [f64; 3]) -> f64 {
    first[0] * second[0] + first[1] * second[1] + first[2] * second[2]
}

fn squared_norm(vector: [f64; 3]) -> f64 {
    dot(vector, vector)
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

fn require_positive(value: f64, name: &str) -> Result<(), EwaldError> {
    if !value.is_finite() || value <= 0.0 {
        return Err(invalid_parameter(format!(
            "{name} must be finite and positive"
        )));
    }
    Ok(())
}

fn invalid_parameter(detail: impl Into<String>) -> EwaldError {
    EwaldError::new(EwaldErrorCode::InvalidParameter, detail)
}

#[cfg(test)]
mod tests {
    use super::{minimum_image, OrthorhombicCell, Position};

    #[test]
    fn minimum_image_uses_frozen_half_open_tie_rule() {
        let cell = OrthorhombicCell {
            lengths_angstrom: [10.0, 12.0, 14.0],
        };
        let positive = minimum_image(Position::new(5.0, 0.0, 0.0), Position::default(), cell);
        let negative = minimum_image(Position::new(-5.0, 0.0, 0.0), Position::default(), cell);
        assert_eq!(positive[0].to_bits(), (-5.0_f64).to_bits());
        assert_eq!(negative[0].to_bits(), (-5.0_f64).to_bits());
    }
}
