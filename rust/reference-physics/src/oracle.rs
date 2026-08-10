use std::collections::{BTreeMap, BTreeSet};

use crate::geometry::{angle_radians, displacement, torsion_radians, Vector3};
use crate::{
    EnergyComponents, OracleError, OracleErrorCode, OracleInput, PairScale,
    COULOMB_KCAL_ANGSTROM_PER_MOL_E2,
};

type PairKey = (usize, usize);

struct ValidatedPairRules {
    exclusions: BTreeSet<PairKey>,
    scales: BTreeMap<PairKey, (f64, f64)>,
}

/// Evaluate all terms with scalar binary64 arithmetic in the schema-frozen order.
///
/// Bonded rows retain input order. Nonbonded pairs are accumulated
/// lexicographically (`i = 0..N`, `j = i+1..N`).
pub fn evaluate(input: &OracleInput) -> Result<EnergyComponents, OracleError> {
    let pair_rules = validate(input)?;
    let mut result = EnergyComponents::default();

    for (row_index, row) in input.bonds.iter().enumerate() {
        let delta = checked_displacement(input, row.atom_i, row.atom_j, "bond displacement")?;
        let distance = delta.squared_norm().sqrt();
        let difference = distance - row.equilibrium_angstrom;
        let energy = 0.5 * row.force_constant_kcal_per_mol_angstrom2 * difference * difference;
        checked_accumulate(
            &mut result.harmonic_bond_kcal_per_mol,
            energy,
            &format!("bond row {row_index}"),
        )?;
    }

    for (row_index, row) in input.angles.iter().enumerate() {
        let first = checked_displacement(input, row.atom_i, row.atom_j, "angle first arm")?;
        let second = checked_displacement(input, row.atom_k, row.atom_j, "angle second arm")?;
        let value = angle_radians(first, second).map_err(|error| {
            OracleError::new(
                error.code(),
                format!("angle row {row_index}: {}", error.detail()),
            )
        })?;
        let difference = value - row.equilibrium_radians;
        let energy = 0.5 * row.force_constant_kcal_per_mol_radian2 * difference * difference;
        checked_accumulate(
            &mut result.harmonic_angle_kcal_per_mol,
            energy,
            &format!("angle row {row_index}"),
        )?;
    }

    for (row_index, row) in input.torsions.iter().enumerate() {
        let b0 = checked_displacement(input, row.atom_i, row.atom_j, "torsion first bond")?;
        let b1 = checked_displacement(input, row.atom_k, row.atom_j, "torsion central bond")?;
        let b2 = checked_displacement(input, row.atom_l, row.atom_k, "torsion last bond")?;
        let phi = torsion_radians(b0, b1, b2).map_err(|error| {
            OracleError::new(
                error.code(),
                format!("torsion row {row_index}: {}", error.detail()),
            )
        })?;
        let argument = f64::from(row.periodicity) * phi - row.phase_radians;
        let energy = row.amplitude_kcal_per_mol * (1.0 + argument.cos());
        checked_accumulate(
            &mut result.periodic_torsion_kcal_per_mol,
            energy,
            &format!("torsion row {row_index}"),
        )?;
    }

    for atom_i in 0..input.positions.len() {
        for atom_j in (atom_i + 1)..input.positions.len() {
            let pair = (atom_i, atom_j);
            // An excluded pair has no nonbonded equation and therefore no distance
            // singularity. Bonded terms for the same atoms remain active above.
            if pair_rules.exclusions.contains(&pair) {
                continue;
            }

            let delta = checked_displacement(input, atom_i, atom_j, "nonbonded displacement")?;
            let squared_distance = delta.squared_norm();
            let minimum = input.nonbonded.minimum_pair_distance_angstrom;
            if squared_distance < minimum * minimum {
                return Err(OracleError::new(
                    OracleErrorCode::PairBelowMinimumDistance,
                    format!("nonbonded pair ({atom_i},{atom_j}) is below {minimum} angstrom"),
                ));
            }
            let distance = squared_distance.sqrt();
            if distance > input.nonbonded.cutoff_angstrom {
                continue;
            }

            let first = input.atom_nonbonded[atom_i];
            let second = input.atom_nonbonded[atom_j];
            let (lennard_jones_scale, coulomb_scale) =
                pair_rules.scales.get(&pair).copied().unwrap_or((1.0, 1.0));

            let sigma = 0.5 * (first.sigma_angstrom + second.sigma_angstrom);
            let epsilon = (first.epsilon_kcal_per_mol * second.epsilon_kcal_per_mol).sqrt();
            let ratio = sigma / distance;
            let ratio2 = ratio * ratio;
            let ratio6 = ratio2 * ratio2 * ratio2;
            let lennard_jones = 4.0 * epsilon * (ratio6 * ratio6 - ratio6) * lennard_jones_scale;

            let screened_charge = first.charge_elementary
                * second.charge_elementary
                * (-input.nonbonded.screening_kappa_per_angstrom * distance).exp();
            let coulomb = COULOMB_KCAL_ANGSTROM_PER_MOL_E2 * screened_charge
                / (input.nonbonded.dielectric * distance)
                * coulomb_scale;
            let switch = switching_value(
                distance,
                input.nonbonded.switch_start_angstrom,
                input.nonbonded.cutoff_angstrom,
            );

            checked_accumulate(
                &mut result.lennard_jones_kcal_per_mol,
                lennard_jones * switch,
                &format!("Lennard-Jones pair ({atom_i},{atom_j})"),
            )?;
            checked_accumulate(
                &mut result.coulomb_kcal_per_mol,
                coulomb * switch,
                &format!("Coulomb pair ({atom_i},{atom_j})"),
            )?;
        }
    }

    if !result.total_kcal_per_mol().is_finite() {
        return Err(OracleError::new(
            OracleErrorCode::NonFiniteEnergy,
            "total energy is not finite",
        ));
    }
    Ok(result)
}

fn validate(input: &OracleInput) -> Result<ValidatedPairRules, OracleError> {
    let atom_count = input.positions.len();
    if atom_count == 0 {
        return Err(OracleError::new(
            OracleErrorCode::EmptySystem,
            "at least one atom is required",
        ));
    }
    if input.atom_nonbonded.len() != atom_count {
        return Err(OracleError::new(
            OracleErrorCode::AtomParameterCountMismatch,
            format!(
                "{} positions have {} nonbonded parameter rows",
                atom_count,
                input.atom_nonbonded.len()
            ),
        ));
    }

    for (atom, position) in input.positions.iter().enumerate() {
        for (axis, value) in [
            position.x_angstrom,
            position.y_angstrom,
            position.z_angstrom,
        ]
        .into_iter()
        .enumerate()
        {
            if !value.is_finite() {
                return Err(OracleError::new(
                    OracleErrorCode::NonFiniteCoordinate,
                    format!("atom {atom} coordinate axis {axis} is not finite"),
                ));
            }
        }
    }

    for (atom, parameter) in input.atom_nonbonded.iter().enumerate() {
        require_positive(
            parameter.sigma_angstrom,
            &format!("atom {atom} sigma_angstrom"),
        )?;
        require_nonnegative(
            parameter.epsilon_kcal_per_mol,
            &format!("atom {atom} epsilon_kcal_per_mol"),
        )?;
        require_finite(
            parameter.charge_elementary,
            &format!("atom {atom} charge_elementary"),
        )?;
    }

    validate_nonbonded_settings(input)?;
    validate_bonds(input)?;
    validate_angles(input)?;
    validate_torsions(input)?;
    validate_pair_rules(input)
}

fn validate_nonbonded_settings(input: &OracleInput) -> Result<(), OracleError> {
    let settings = input.nonbonded;
    require_positive(settings.cutoff_angstrom, "cutoff_angstrom")?;
    require_nonnegative(settings.switch_start_angstrom, "switch_start_angstrom")?;
    if settings.switch_start_angstrom >= settings.cutoff_angstrom {
        return Err(invalid_parameter(
            "switch_start_angstrom must be smaller than cutoff_angstrom",
        ));
    }
    require_positive(settings.dielectric, "dielectric")?;
    require_nonnegative(
        settings.screening_kappa_per_angstrom,
        "screening_kappa_per_angstrom",
    )?;
    require_positive(
        settings.minimum_pair_distance_angstrom,
        "minimum_pair_distance_angstrom",
    )?;

    if let Some(cell) = input.cell {
        for (axis, length) in cell.lengths_angstrom.into_iter().enumerate() {
            if !length.is_finite() || length <= 0.0 {
                return Err(OracleError::new(
                    OracleErrorCode::InvalidCell,
                    format!("cell length axis {axis} must be finite and positive"),
                ));
            }
            if cell.periodic_axes[axis] && settings.cutoff_angstrom >= 0.5 * length {
                return Err(OracleError::new(
                    OracleErrorCode::CutoffViolatesMinimumImage,
                    format!(
                        "cutoff {} must be below half of periodic axis {axis} length {length}",
                        settings.cutoff_angstrom
                    ),
                ));
            }
        }
    }
    Ok(())
}

fn validate_bonds(input: &OracleInput) -> Result<(), OracleError> {
    let mut keys = BTreeSet::new();
    for (row_index, row) in input.bonds.iter().enumerate() {
        let key = canonical_pair(row.atom_i, row.atom_j, input.positions.len(), "bond")?;
        if !keys.insert(key) {
            return Err(OracleError::new(
                OracleErrorCode::DuplicateTerm,
                format!("bond row {row_index} duplicates pair ({},{})", key.0, key.1),
            ));
        }
        require_positive(
            row.equilibrium_angstrom,
            &format!("bond row {row_index} equilibrium_angstrom"),
        )?;
        require_positive(
            row.force_constant_kcal_per_mol_angstrom2,
            &format!("bond row {row_index} force constant"),
        )?;
    }
    Ok(())
}

fn validate_angles(input: &OracleInput) -> Result<(), OracleError> {
    let mut keys = BTreeSet::new();
    for (row_index, row) in input.angles.iter().enumerate() {
        validate_distinct_indices(
            &[row.atom_i, row.atom_j, row.atom_k],
            input.positions.len(),
            "angle",
        )?;
        let key = (
            row.atom_i.min(row.atom_k),
            row.atom_j,
            row.atom_i.max(row.atom_k),
        );
        if !keys.insert(key) {
            return Err(OracleError::new(
                OracleErrorCode::DuplicateTerm,
                format!("angle row {row_index} duplicates canonical angle {key:?}"),
            ));
        }
        require_finite(
            row.equilibrium_radians,
            &format!("angle row {row_index} equilibrium_radians"),
        )?;
        if !(0.0..core::f64::consts::PI).contains(&row.equilibrium_radians)
            || row.equilibrium_radians == 0.0
        {
            return Err(invalid_parameter(format!(
                "angle row {row_index} equilibrium_radians must lie in (0,pi)"
            )));
        }
        require_positive(
            row.force_constant_kcal_per_mol_radian2,
            &format!("angle row {row_index} force constant"),
        )?;
    }
    Ok(())
}

fn validate_torsions(input: &OracleInput) -> Result<(), OracleError> {
    let mut keys = BTreeSet::new();
    for (row_index, row) in input.torsions.iter().enumerate() {
        let forward = [row.atom_i, row.atom_j, row.atom_k, row.atom_l];
        validate_distinct_indices(&forward, input.positions.len(), "torsion")?;
        if !(1..=12).contains(&row.periodicity) {
            return Err(invalid_parameter(format!(
                "torsion row {row_index} periodicity must lie in [1,12]"
            )));
        }
        require_finite(
            row.phase_radians,
            &format!("torsion row {row_index} phase_radians"),
        )?;
        require_nonnegative(
            row.amplitude_kcal_per_mol,
            &format!("torsion row {row_index} amplitude"),
        )?;
        let reverse = [row.atom_l, row.atom_k, row.atom_j, row.atom_i];
        let canonical = forward.min(reverse);
        let phase_bits = if row.phase_radians == 0.0 {
            0
        } else {
            row.phase_radians.to_bits()
        };
        let key = (canonical, row.periodicity, phase_bits);
        if !keys.insert(key) {
            return Err(OracleError::new(
                OracleErrorCode::DuplicateTerm,
                format!("torsion row {row_index} duplicates an existing term"),
            ));
        }
    }
    Ok(())
}

fn validate_pair_rules(input: &OracleInput) -> Result<ValidatedPairRules, OracleError> {
    let mut exclusions = BTreeSet::new();
    for (row_index, row) in input.exclusions.iter().enumerate() {
        let key = canonical_pair(row.atom_i, row.atom_j, input.positions.len(), "exclusion")?;
        if !exclusions.insert(key) {
            return Err(OracleError::new(
                OracleErrorCode::DuplicatePairRule,
                format!("exclusion row {row_index} duplicates pair {key:?}"),
            ));
        }
    }

    let mut scales = BTreeMap::new();
    for (row_index, row) in input.pair_scales.iter().enumerate() {
        let key = validate_pair_scale(input, row_index, *row)?;
        if scales
            .insert(key, (row.lennard_jones_scale, row.coulomb_scale))
            .is_some()
        {
            return Err(OracleError::new(
                OracleErrorCode::DuplicatePairRule,
                format!("pair scale row {row_index} duplicates pair {key:?}"),
            ));
        }
    }
    if let Some(pair) = exclusions.iter().find(|pair| scales.contains_key(pair)) {
        return Err(OracleError::new(
            OracleErrorCode::ConflictingPairRule,
            format!("pair {pair:?} cannot be both excluded and scaled"),
        ));
    }
    Ok(ValidatedPairRules { exclusions, scales })
}

fn validate_pair_scale(
    input: &OracleInput,
    row_index: usize,
    row: PairScale,
) -> Result<PairKey, OracleError> {
    let key = canonical_pair(row.atom_i, row.atom_j, input.positions.len(), "pair scale")?;
    for (name, value) in [
        ("Lennard-Jones", row.lennard_jones_scale),
        ("Coulomb", row.coulomb_scale),
    ] {
        if !value.is_finite() || !(0.0..=1.0).contains(&value) {
            return Err(invalid_parameter(format!(
                "pair scale row {row_index} {name} scale must lie in [0,1]"
            )));
        }
    }
    Ok(key)
}

fn validate_distinct_indices(
    indices: &[usize],
    atom_count: usize,
    term: &str,
) -> Result<(), OracleError> {
    let mut seen = BTreeSet::new();
    for &atom in indices {
        if atom >= atom_count {
            return Err(OracleError::new(
                OracleErrorCode::AtomIndexOutOfRange,
                format!("{term} atom index {atom} is outside 0..{atom_count}"),
            ));
        }
        if !seen.insert(atom) {
            return Err(OracleError::new(
                OracleErrorCode::RepeatedAtomIndex,
                format!("{term} repeats atom index {atom}"),
            ));
        }
    }
    Ok(())
}

fn canonical_pair(
    atom_i: usize,
    atom_j: usize,
    atom_count: usize,
    term: &str,
) -> Result<PairKey, OracleError> {
    validate_distinct_indices(&[atom_i, atom_j], atom_count, term)?;
    Ok((atom_i.min(atom_j), atom_i.max(atom_j)))
}

fn checked_displacement(
    input: &OracleInput,
    atom_i: usize,
    atom_j: usize,
    context: &str,
) -> Result<Vector3, OracleError> {
    let value = displacement(input.positions[atom_i], input.positions[atom_j], input.cell);
    if !value.x.is_finite() || !value.y.is_finite() || !value.z.is_finite() {
        return Err(OracleError::new(
            OracleErrorCode::NonFiniteEnergy,
            format!("{context} produced a non-finite value"),
        ));
    }
    let squared = value.squared_norm();
    if !squared.is_finite() {
        return Err(OracleError::new(
            OracleErrorCode::NonFiniteEnergy,
            format!("{context} squared distance is not finite"),
        ));
    }
    Ok(value)
}

fn switching_value(distance: f64, start: f64, cutoff: f64) -> f64 {
    if distance <= start {
        return 1.0;
    }
    if distance >= cutoff {
        return 0.0;
    }
    let x = (distance - start) / (cutoff - start);
    let x2 = x * x;
    let x3 = x2 * x;
    let x4 = x3 * x;
    let x5 = x4 * x;
    1.0 - 10.0 * x3 + 15.0 * x4 - 6.0 * x5
}

fn checked_accumulate(target: &mut f64, value: f64, context: &str) -> Result<(), OracleError> {
    let updated = *target + value;
    if !value.is_finite() || !updated.is_finite() {
        return Err(OracleError::new(
            OracleErrorCode::NonFiniteEnergy,
            format!("{context} produced a non-finite energy"),
        ));
    }
    *target = updated;
    Ok(())
}

fn require_finite(value: f64, name: &str) -> Result<(), OracleError> {
    if !value.is_finite() {
        return Err(invalid_parameter(format!("{name} must be finite")));
    }
    Ok(())
}

fn require_positive(value: f64, name: &str) -> Result<(), OracleError> {
    if !value.is_finite() || value <= 0.0 {
        return Err(invalid_parameter(format!(
            "{name} must be finite and positive"
        )));
    }
    Ok(())
}

fn require_nonnegative(value: f64, name: &str) -> Result<(), OracleError> {
    if !value.is_finite() || value < 0.0 {
        return Err(invalid_parameter(format!(
            "{name} must be finite and non-negative"
        )));
    }
    Ok(())
}

fn invalid_parameter(detail: impl Into<String>) -> OracleError {
    OracleError::new(OracleErrorCode::InvalidParameter, detail)
}

#[cfg(test)]
mod tests {
    use super::switching_value;

    #[test]
    fn quintic_switch_has_frozen_boundaries_and_midpoint() {
        assert_eq!(switching_value(2.0, 2.0, 4.0).to_bits(), 1.0_f64.to_bits());
        assert_eq!(switching_value(3.0, 2.0, 4.0).to_bits(), 0.5_f64.to_bits());
        assert_eq!(switching_value(4.0, 2.0, 4.0).to_bits(), 0.0_f64.to_bits());
    }
}
