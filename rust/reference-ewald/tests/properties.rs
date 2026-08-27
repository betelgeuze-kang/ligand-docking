use betelgeuze_reference_ewald::{
    evaluate, EwaldErrorCode, EwaldInput, EwaldSettings, OrthorhombicCell, PairExclusion,
    PairScale, Position, COULOMB_KCAL_ANGSTROM_PER_MOL_E2,
};

fn rich_input() -> EwaldInput {
    let mut input = EwaldInput::new(
        vec![
            Position::new(1.25, 2.5, 3.75),
            Position::new(5.1, 3.2, 8.4),
            Position::new(10.2, 12.3, 7.7),
            Position::new(15.4, 17.1, 19.3),
        ],
        vec![0.7, -0.4, -0.6, 0.3],
        OrthorhombicCell {
            lengths_angstrom: [18.0, 20.0, 22.0],
        },
    );
    input.settings = EwaldSettings {
        alpha_per_angstrom: 0.31,
        real_space_cutoff_angstrom: 8.9,
        reciprocal_max_indices: [5, 5, 5],
        dielectric: 1.0,
        minimum_pair_distance_angstrom: 1.0e-8,
        neutrality_tolerance_elementary: 1.0e-12,
    };
    input.exclusions.push(PairExclusion {
        atom_i: 0,
        atom_j: 1,
    });
    input.pair_scales.push(PairScale {
        atom_i: 2,
        atom_j: 3,
        coulomb_scale: 0.5,
    });
    input
}

fn assert_close(actual: f64, expected: f64, tolerance: f64) {
    let scale = 1.0 + actual.abs().max(expected.abs());
    assert!(
        (actual - expected).abs() <= tolerance * scale,
        "actual={actual:.17e}, expected={expected:.17e}, tolerance={tolerance:.3e}"
    );
}

fn assert_error(input: &EwaldInput, expected: EwaldErrorCode) {
    let error = evaluate(input).expect_err("malformed input must fail");
    assert_eq!(error.code(), expected, "unexpected error: {error}");
    assert!(!error.detail().is_empty());
}

#[test]
fn analytic_forces_match_central_finite_differences() {
    let input = rich_input();
    let evaluated = evaluate(&input).expect("fixture is valid");
    let step = 1.0e-5;
    let mut maximum_error = 0.0_f64;
    for atom in 0..input.positions.len() {
        for axis in 0..3 {
            let mut minus = input.clone();
            let mut plus = input.clone();
            coordinate_mut(&mut minus.positions[atom], axis)
                .clone_from(&(coordinate(&input.positions[atom], axis) - step));
            coordinate_mut(&mut plus.positions[atom], axis)
                .clone_from(&(coordinate(&input.positions[atom], axis) + step));
            let minus_energy = evaluate(&minus)
                .expect("minus displacement is valid")
                .energy
                .total_kcal_per_mol();
            let plus_energy = evaluate(&plus)
                .expect("plus displacement is valid")
                .energy
                .total_kcal_per_mol();
            let finite_difference_force = -(plus_energy - minus_energy) / (2.0 * step);
            let error = (evaluated.forces_kcal_per_mol_angstrom[atom][axis]
                - finite_difference_force)
                .abs();
            maximum_error = maximum_error.max(error);
            assert_close(
                evaluated.forces_kcal_per_mol_angstrom[atom][axis],
                finite_difference_force,
                2.0e-7,
            );
        }
    }
    assert!(maximum_error < 1.0e-5);
}

#[test]
fn translation_images_permutation_and_charge_inversion_are_invariant() {
    let input = rich_input();
    let expected = evaluate(&input).expect("fixture is valid");

    let mut translated = input.clone();
    for position in &mut translated.positions {
        position.x_angstrom += 2.25;
        position.y_angstrom -= 1.5;
        position.z_angstrom += 0.75;
    }
    assert_evaluation_close(
        &evaluate(&translated).expect("translation is valid"),
        &expected,
        3.0e-12,
    );

    let mut imaged = input.clone();
    imaged.positions[0].x_angstrom += 2.0 * input.cell.lengths_angstrom[0];
    imaged.positions[1].y_angstrom -= 3.0 * input.cell.lengths_angstrom[1];
    imaged.positions[2].z_angstrom += input.cell.lengths_angstrom[2];
    assert_evaluation_close(
        &evaluate(&imaged).expect("integer images are valid"),
        &expected,
        5.0e-12,
    );

    let order = [3_usize, 2, 1, 0];
    let mut old_to_new = [0_usize; 4];
    for (new, old) in order.iter().copied().enumerate() {
        old_to_new[old] = new;
    }
    let mut permuted = EwaldInput::new(
        order.iter().map(|&old| input.positions[old]).collect(),
        order
            .iter()
            .map(|&old| input.charges_elementary[old])
            .collect(),
        input.cell,
    );
    permuted.settings = input.settings;
    permuted.exclusions = input
        .exclusions
        .iter()
        .map(|row| PairExclusion {
            atom_i: old_to_new[row.atom_i],
            atom_j: old_to_new[row.atom_j],
        })
        .collect();
    permuted.pair_scales = input
        .pair_scales
        .iter()
        .map(|row| PairScale {
            atom_i: old_to_new[row.atom_i],
            atom_j: old_to_new[row.atom_j],
            coulomb_scale: row.coulomb_scale,
        })
        .collect();
    let permuted_result = evaluate(&permuted).expect("permutation is valid");
    assert_close(
        permuted_result.energy.total_kcal_per_mol(),
        expected.energy.total_kcal_per_mol(),
        3.0e-12,
    );
    for (new, old) in order.iter().copied().enumerate() {
        for axis in 0..3 {
            assert_close(
                permuted_result.forces_kcal_per_mol_angstrom[new][axis],
                expected.forces_kcal_per_mol_angstrom[old][axis],
                3.0e-12,
            );
        }
    }

    let mut inverted = input;
    for charge in &mut inverted.charges_elementary {
        *charge = -*charge;
    }
    assert_evaluation_close(
        &evaluate(&inverted).expect("charge inversion is valid"),
        &expected,
        1.0e-15,
    );
}

#[test]
fn reciprocal_bound_converges_toward_a_higher_bound() {
    let mut low = rich_input();
    low.settings.reciprocal_max_indices = [3, 3, 3];
    let mut medium = low.clone();
    medium.settings.reciprocal_max_indices = [5, 5, 5];
    let mut high = low.clone();
    high.settings.reciprocal_max_indices = [7, 7, 7];
    let mut reference = low.clone();
    reference.settings.reciprocal_max_indices = [9, 9, 9];

    let low = evaluate(&low).expect("low bound is valid");
    let medium = evaluate(&medium).expect("medium bound is valid");
    let high = evaluate(&high).expect("high bound is valid");
    let reference = evaluate(&reference).expect("reference bound is valid");
    let low_error = (low.energy.total_kcal_per_mol() - reference.energy.total_kcal_per_mol()).abs();
    let medium_error =
        (medium.energy.total_kcal_per_mol() - reference.energy.total_kcal_per_mol()).abs();
    let high_error =
        (high.energy.total_kcal_per_mol() - reference.energy.total_kcal_per_mol()).abs();
    assert!(
        medium_error < low_error,
        "medium={medium_error}, low={low_error}"
    );
    assert!(
        high_error < medium_error,
        "high={high_error}, medium={medium_error}"
    );
    assert!(
        high_error < 2.0e-6,
        "high-bound truncation observation={high_error}"
    );
}

#[test]
fn exclusion_and_scale_apply_unscreened_local_corrections() {
    let mut base = EwaldInput::new(
        vec![Position::new(1.0, 2.0, 3.0), Position::new(4.0, 2.0, 3.0)],
        vec![1.0, -1.0],
        OrthorhombicCell {
            lengths_angstrom: [20.0, 20.0, 20.0],
        },
    );
    base.settings.real_space_cutoff_angstrom = 9.0;
    let unmodified = evaluate(&base).expect("base pair is valid");

    let mut excluded = base.clone();
    excluded.exclusions.push(PairExclusion {
        atom_i: 1,
        atom_j: 0,
    });
    let excluded = evaluate(&excluded).expect("excluded pair is valid");
    let full_pair = -COULOMB_KCAL_ANGSTROM_PER_MOL_E2 / 3.0;
    assert_close(
        excluded.energy.pair_correction_kcal_per_mol,
        -full_pair,
        1.0e-15,
    );
    assert_close(
        excluded.energy.total_kcal_per_mol() - unmodified.energy.total_kcal_per_mol(),
        -full_pair,
        1.0e-15,
    );

    let mut half_scaled = base;
    half_scaled.pair_scales.push(PairScale {
        atom_i: 0,
        atom_j: 1,
        coulomb_scale: 0.5,
    });
    let half_scaled = evaluate(&half_scaled).expect("scaled pair is valid");
    assert_close(
        half_scaled.energy.pair_correction_kcal_per_mol,
        -0.5 * full_pair,
        1.0e-15,
    );
}

#[test]
fn malformed_inputs_have_typed_failures() {
    let input = rich_input();

    let capacity = EwaldInput::new(
        vec![Position::default(); 4_097],
        vec![0.0; 4_097],
        input.cell,
    );
    assert_error(&capacity, EwaldErrorCode::CapacityExceeded);

    let mut empty = input.clone();
    empty.positions.clear();
    empty.charges_elementary.clear();
    assert_error(&empty, EwaldErrorCode::EmptySystem);

    let mut mismatch = input.clone();
    mismatch.charges_elementary.pop();
    assert_error(&mismatch, EwaldErrorCode::ChargeCountMismatch);

    let mut nonfinite_position = input.clone();
    nonfinite_position.positions[0].x_angstrom = f64::NAN;
    assert_error(&nonfinite_position, EwaldErrorCode::NonFiniteCoordinate);

    let mut nonfinite_charge = input.clone();
    nonfinite_charge.charges_elementary[0] = f64::INFINITY;
    assert_error(&nonfinite_charge, EwaldErrorCode::NonFiniteCharge);

    let mut charged = input.clone();
    charged.charges_elementary[0] += 0.01;
    assert_error(&charged, EwaldErrorCode::NonNeutralSystem);

    let mut invalid_cell = input.clone();
    invalid_cell.cell.lengths_angstrom[1] = 0.0;
    assert_error(&invalid_cell, EwaldErrorCode::InvalidCell);

    let mut invalid_cutoff = input.clone();
    invalid_cutoff.settings.real_space_cutoff_angstrom = 9.0;
    assert_error(&invalid_cutoff, EwaldErrorCode::CutoffViolatesMinimumImage);

    for reciprocal in [0, 33] {
        let mut invalid = input.clone();
        invalid.settings.reciprocal_max_indices[0] = reciprocal;
        assert_error(&invalid, EwaldErrorCode::InvalidParameter);
    }

    for alpha in [0.0, -0.1, f64::NAN] {
        let mut invalid = input.clone();
        invalid.settings.alpha_per_angstrom = alpha;
        assert_error(&invalid, EwaldErrorCode::InvalidParameter);
    }

    let mut duplicate = input.clone();
    duplicate.exclusions.push(PairExclusion {
        atom_i: 1,
        atom_j: 0,
    });
    assert_error(&duplicate, EwaldErrorCode::DuplicatePairRule);

    let mut conflict = input.clone();
    conflict.pair_scales.push(PairScale {
        atom_i: 1,
        atom_j: 0,
        coulomb_scale: 0.25,
    });
    assert_error(&conflict, EwaldErrorCode::ConflictingPairRule);

    let mut self_pair = input.clone();
    self_pair.exclusions = vec![PairExclusion {
        atom_i: 0,
        atom_j: 0,
    }];
    assert_error(&self_pair, EwaldErrorCode::RepeatedAtomIndex);

    let mut out_of_range = input.clone();
    out_of_range.pair_scales = vec![PairScale {
        atom_i: 0,
        atom_j: 4,
        coulomb_scale: 0.5,
    }];
    assert_error(&out_of_range, EwaldErrorCode::AtomIndexOutOfRange);

    let mut coincident = input;
    coincident.positions[1] = coincident.positions[0];
    assert_error(&coincident, EwaldErrorCode::PairBelowMinimumDistance);
}

#[test]
fn evaluation_is_bitwise_repeatable_and_net_force_is_near_zero() {
    let input = rich_input();
    let first = evaluate(&input).expect("fixture is valid");
    for _ in 0..32 {
        assert_eq!(evaluate(&input).expect("repeat is valid"), first);
    }
    for axis in 0..3 {
        let net = first
            .forces_kcal_per_mol_angstrom
            .iter()
            .map(|force| force[axis])
            .sum::<f64>();
        assert_close(net, 0.0, 2.0e-12);
    }
}

fn coordinate(position: &Position, axis: usize) -> f64 {
    match axis {
        0 => position.x_angstrom,
        1 => position.y_angstrom,
        2 => position.z_angstrom,
        _ => unreachable!(),
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

fn assert_evaluation_close(
    actual: &betelgeuze_reference_ewald::EwaldEvaluation,
    expected: &betelgeuze_reference_ewald::EwaldEvaluation,
    tolerance: f64,
) {
    assert_close(
        actual.energy.real_space_kcal_per_mol,
        expected.energy.real_space_kcal_per_mol,
        tolerance,
    );
    assert_close(
        actual.energy.reciprocal_space_kcal_per_mol,
        expected.energy.reciprocal_space_kcal_per_mol,
        tolerance,
    );
    assert_close(
        actual.energy.self_kcal_per_mol,
        expected.energy.self_kcal_per_mol,
        tolerance,
    );
    assert_close(
        actual.energy.pair_correction_kcal_per_mol,
        expected.energy.pair_correction_kcal_per_mol,
        tolerance,
    );
    for (actual_force, expected_force) in actual
        .forces_kcal_per_mol_angstrom
        .iter()
        .zip(&expected.forces_kcal_per_mol_angstrom)
    {
        for axis in 0..3 {
            assert_close(actual_force[axis], expected_force[axis], tolerance);
        }
    }
}
