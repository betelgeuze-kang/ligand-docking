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
        vec![0.7, -0.4, -0.6, 0.300_000_000_000_000_04],
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

    let mut distant_images = input.clone();
    distant_images.positions[0].x_angstrom += 1_000_000.0 * input.cell.lengths_angstrom[0];
    distant_images.positions[0].y_angstrom -= 1_000_000.0 * input.cell.lengths_angstrom[1];
    distant_images.positions[0].z_angstrom += 1_000_000.0 * input.cell.lengths_angstrom[2];
    assert_evaluation_close(
        &evaluate(&distant_images).expect("distant integer images are valid"),
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
fn scale_one_pair_rule_is_a_noop_before_half_cell_image_selection() {
    let mut base = EwaldInput::new(
        vec![Position::new(0.0, 1.0, 1.0), Position::new(5.0, 1.0, 1.0)],
        vec![1.0, -1.0],
        OrthorhombicCell {
            lengths_angstrom: [10.0, 12.0, 14.0],
        },
    );
    base.settings.real_space_cutoff_angstrom = 4.9;
    let expected = evaluate(&base).expect("base half-cell pair is valid without correction");
    base.pair_scales.push(PairScale {
        atom_i: 0,
        atom_j: 1,
        coulomb_scale: 1.0,
    });
    assert_eq!(
        evaluate(&base).expect("unit scale is semantically neutral"),
        expected
    );
}

#[test]
fn zero_charge_pair_rule_is_a_noop_before_half_cell_image_selection() {
    let mut base = EwaldInput::new(
        vec![Position::new(0.0, 1.0, 1.0), Position::new(5.0, 1.0, 1.0)],
        vec![0.0, 0.0],
        OrthorhombicCell {
            lengths_angstrom: [10.0, 12.0, 14.0],
        },
    );
    base.settings.real_space_cutoff_angstrom = 4.9;
    let expected = evaluate(&base).expect("base zero-charge pair is valid");
    base.exclusions.push(PairExclusion {
        atom_i: 0,
        atom_j: 1,
    });
    assert_eq!(
        evaluate(&base).expect("zero-charge correction is semantically neutral"),
        expected
    );
}

#[test]
fn near_half_cell_real_space_pair_is_antisymmetric_under_atom_swap() {
    let below_half = f64::from_bits(1.5_f64.to_bits() - 1);
    let mut input = EwaldInput::new(
        vec![
            Position::new(0.0, 1.0, 1.0),
            Position::new(below_half, 1.0, 1.0),
        ],
        vec![1.0, -1.0],
        OrthorhombicCell {
            lengths_angstrom: [3.0, 12.0, 14.0],
        },
    );
    input.settings.real_space_cutoff_angstrom = below_half;
    let forward = evaluate(&input).expect("near-half pair is valid");
    input.positions.swap(0, 1);
    input.charges_elementary.swap(0, 1);
    let swapped = evaluate(&input).expect("swapped near-half pair is valid");
    assert_close(
        swapped.energy.total_kcal_per_mol(),
        forward.energy.total_kcal_per_mol(),
        2.0e-12,
    );
    for axis in 0..3 {
        assert_close(
            swapped.forces_kcal_per_mol_angstrom[0][axis],
            forward.forces_kcal_per_mol_angstrom[1][axis],
            2.0e-12,
        );
        assert_close(
            swapped.forces_kcal_per_mol_angstrom[1][axis],
            forward.forces_kcal_per_mol_angstrom[0][axis],
            2.0e-12,
        );
    }
}

#[test]
fn half_cell_pair_correction_image_is_rejected_independent_of_representation() {
    let mut input = EwaldInput::new(
        vec![Position::new(0.0, 1.0, 1.0), Position::new(5.0, 1.0, 1.0)],
        vec![1.0, -1.0],
        OrthorhombicCell {
            lengths_angstrom: [10.0, 12.0, 14.0],
        },
    );
    input.settings.real_space_cutoff_angstrom = 4.9;
    input.exclusions.push(PairExclusion {
        atom_i: 0,
        atom_j: 1,
    });
    assert_error(&input, EwaldErrorCode::AmbiguousPairCorrectionImage);

    input.positions.swap(0, 1);
    input.charges_elementary.swap(0, 1);
    assert_error(&input, EwaldErrorCode::AmbiguousPairCorrectionImage);

    for position in &mut input.positions {
        position.x_angstrom += 6.0;
    }
    assert_error(&input, EwaldErrorCode::AmbiguousPairCorrectionImage);
}

#[test]
fn rounded_half_cell_difference_is_not_an_exact_pair_correction_tie() {
    let mut input = EwaldInput::new(
        vec![
            Position::new(5.0, 1.0, 1.0),
            Position::new(1.0e-16, 1.0, 1.0),
        ],
        vec![1.0, -1.0],
        OrthorhombicCell {
            lengths_angstrom: [10.0, 12.0, 14.0],
        },
    );
    input.settings.real_space_cutoff_angstrom = 4.9;
    input.exclusions.push(PairExclusion {
        atom_i: 0,
        atom_j: 1,
    });
    evaluate(&input).expect("represented separation is strictly below half a cell");
}

#[test]
fn supported_negative_boundary_residual_is_not_collapsed_to_zero() {
    let mut input = EwaldInput::new(
        vec![Position::default(), Position::new(-5.0e-8, 0.0, 0.0)],
        vec![1.0, -1.0],
        OrthorhombicCell {
            lengths_angstrom: [1.0e9; 3],
        },
    );
    input.settings.real_space_cutoff_angstrom = 1.0;
    let evaluation = evaluate(&input).expect("supported boundary residual is a distinct position");
    assert!(evaluation.energy.real_space_kcal_per_mol.is_finite());
    assert!(evaluation.energy.real_space_kcal_per_mol.is_sign_negative());
}

#[test]
fn multidimensional_rounded_boundary_translation_is_invariant() {
    let mut input = EwaldInput::new(
        vec![
            Position::new(-5.0e-9, 0.0, 0.0),
            Position::new(0.0, 2.0e-8, 0.0),
        ],
        vec![1.0, -1.0],
        OrthorhombicCell {
            lengths_angstrom: [1.0e9; 3],
        },
    );
    input.settings.real_space_cutoff_angstrom = 1.0;
    let expected = evaluate(&input).expect("boundary fixture is valid");
    for position in &mut input.positions {
        position.x_angstrom += 5.0e-9;
    }
    let translated = evaluate(&input).expect("translated boundary fixture is valid");
    assert_evaluation_close(&translated, &expected, 3.0e-12);
}

#[test]
fn reciprocal_scaling_preserves_representable_damped_terms() {
    let mut input = EwaldInput::new(
        vec![Position::default(), Position::new(2.5e-7, 0.0, 0.0)],
        vec![1.0, -1.0],
        OrthorhombicCell {
            lengths_angstrom: [1.0e-6; 3],
        },
    );
    input.settings.alpha_per_angstrom = 1.174_889e5;
    input.settings.real_space_cutoff_angstrom = 1.0e-7;
    input.settings.reciprocal_max_indices = [1; 3];
    input.settings.dielectric = 1.0e-12;
    let evaluation = evaluate(&input).expect("bounded underflow fixture is valid");
    assert!(evaluation.energy.reciprocal_space_kcal_per_mol > 0.0);
    assert!(evaluation.energy.reciprocal_space_kcal_per_mol.is_finite());
}

#[test]
fn normalized_structure_factor_preserves_tiny_phase_force() {
    let mut input = EwaldInput::new(
        vec![Position::default(), Position::new(3.0e-7, 0.0, 1.0e-305)],
        vec![1.0e-12, -1.0e-12],
        OrthorhombicCell {
            lengths_angstrom: [1.0e-6, 1.0e-6, 1.0e9],
        },
    );
    input.settings.alpha_per_angstrom = 1.0;
    input.settings.real_space_cutoff_angstrom = 2.0e-7;
    input.settings.reciprocal_max_indices = [1; 3];
    input.settings.dielectric = 1.0e-12;
    let evaluation = evaluate(&input).expect("tiny-phase fixture is inside the numeric envelope");
    let force = evaluation.forces_kcal_per_mol_angstrom[0][2];
    assert!(force.is_subnormal());
    assert_ne!(force.to_bits(), 0.0_f64.to_bits());
}

#[test]
fn unscaled_real_damping_underflow_is_rejected() {
    let mut input = EwaldInput::new(
        vec![Position::default(), Position::new(1.0, 0.0, 0.0)],
        vec![16.0, -16.0],
        OrthorhombicCell {
            lengths_angstrom: [3.0; 3],
        },
    );
    input.settings.alpha_per_angstrom = 27.4;
    input.settings.real_space_cutoff_angstrom = 1.1;
    input.settings.dielectric = 1.0e-12;
    assert_error(&input, EwaldErrorCode::DampingUnderflow);
}

#[test]
fn representable_reciprocal_zero_damping_is_scaled() {
    let mut input = EwaldInput::new(
        vec![Position::default(), Position::new(2.5e-7, 0.0, 0.0)],
        vec![16.0, -16.0],
        OrthorhombicCell {
            lengths_angstrom: [1.0e-6; 3],
        },
    );
    input.settings.alpha_per_angstrom = 114_714.744_190_909_54;
    input.settings.real_space_cutoff_angstrom = 2.0e-7;
    input.settings.reciprocal_max_indices = [1; 3];
    input.settings.dielectric = 1.0e-12;
    let evaluation = evaluate(&input).expect("zero damping is scaled in the log domain");
    assert!(evaluation.energy.reciprocal_space_kcal_per_mol > 1.0e-304);
    assert!(evaluation.energy.reciprocal_space_kcal_per_mol < 2.0e-303);
}

#[test]
fn representable_reciprocal_subnormal_damping_is_scaled() {
    let mut input = EwaldInput::new(
        vec![Position::default(), Position::new(2.5e-7, 0.0, 0.0)],
        vec![16.0, -16.0],
        OrthorhombicCell {
            lengths_angstrom: [1.0e-6; 3],
        },
    );
    input.settings.alpha_per_angstrom = 115_106.774_814_174_32;
    input.settings.real_space_cutoff_angstrom = 2.0e-7;
    input.settings.reciprocal_max_indices = [1; 3];
    input.settings.dielectric = 1.0e-12;
    let evaluation = evaluate(&input).expect("subnormal damping is scaled in the log domain");
    assert!(evaluation.energy.reciprocal_space_kcal_per_mol > 1.6e-301);
    assert!(evaluation.energy.reciprocal_space_kcal_per_mol < 1.8e-301);
}

#[test]
fn reciprocal_phase_product_underflow_is_rejected() {
    let mut input = EwaldInput::new(
        vec![Position::default(), Position::new(0.3, 0.0, 1.0e-317)],
        vec![16.0, -16.0],
        OrthorhombicCell {
            lengths_angstrom: [1.0, 1.0, 1.0e9],
        },
    );
    input.settings.alpha_per_angstrom = 1.0;
    input.settings.real_space_cutoff_angstrom = 0.2;
    input.settings.reciprocal_max_indices = [1; 3];
    input.settings.dielectric = 1.0e-12;
    assert_error(&input, EwaldErrorCode::PhaseUnderflow);
}

#[test]
fn reciprocal_phase_sum_preserves_cancellation_residual() {
    let inverse_tau = 1.0 / core::f64::consts::TAU;
    let mut input = EwaldInput::new(
        vec![
            Position::new(0.0, 0.0, inverse_tau),
            Position::new(inverse_tau, 1.0e-292, 0.0),
        ],
        vec![16.0, -16.0],
        OrthorhombicCell {
            lengths_angstrom: [1.0, 1.0e9, 1.0],
        },
    );
    input.settings.alpha_per_angstrom = 1.0;
    input.settings.real_space_cutoff_angstrom = 0.1;
    input.settings.reciprocal_max_indices = [1; 3];
    input.settings.dielectric = 1.0e-12;
    let evaluation = evaluate(&input).expect("phase cancellation fixture is valid");
    let residual_force = evaluation.forces_kcal_per_mol_angstrom[0][1].abs();
    assert!(residual_force > 1.0e-311);
    assert!(residual_force < 1.0e-309);
}

#[test]
fn wrapped_pair_displacement_preserves_boundary_residuals() {
    let mut input = EwaldInput::new(
        vec![
            Position::new(-5.0e-8, 0.0, 0.0),
            Position::new(999_999_999.999_999_9, 0.0, 0.0),
        ],
        vec![1.0, -1.0],
        OrthorhombicCell {
            lengths_angstrom: [1.0e9; 3],
        },
    );
    input.settings.real_space_cutoff_angstrom = 8.0e-8;
    let evaluation = evaluate(&input).expect("wrapped residual fixture is valid");
    assert!(evaluation.energy.real_space_kcal_per_mol.is_sign_negative());
    assert_ne!(evaluation.energy.real_space_kcal_per_mol.to_bits(), 0);
}

#[test]
fn reciprocal_phases_are_common_translation_stable() {
    let shared_z = 1.0e8_f64;
    let next_z = f64::from_bits(shared_z.to_bits() + 1);
    let mut input = EwaldInput::new(
        vec![
            Position::new(0.0, 0.0, shared_z),
            Position::new(3.0e-7, 0.0, next_z),
        ],
        vec![16.0, -16.0],
        OrthorhombicCell {
            lengths_angstrom: [1.0e-6, 1.0e-6, 1.0e9],
        },
    );
    input.settings.alpha_per_angstrom = 1.0;
    input.settings.real_space_cutoff_angstrom = 2.0e-7;
    input.settings.reciprocal_max_indices = [1; 3];
    input.settings.dielectric = 1.0e-12;
    let expected = evaluate(&input).expect("large shared-coordinate fixture is valid");
    for position in &mut input.positions {
        position.z_angstrom -= shared_z;
    }
    let translated = evaluate(&input).expect("origin-translated fixture is valid");
    assert_evaluation_close(&translated, &expected, 3.0e-12);
}

#[test]
fn reciprocal_structure_factor_is_atom_order_independent() {
    let positions = vec![
        Position::new(0.0, 0.0, 1.0e8),
        Position::new(3.0e-7, 0.0, 1.0e8),
        Position::new(0.0, 3.0e-7, 1.0e8),
        Position::new(3.0e-7, 3.0e-7, 1.0e8),
    ];
    let charges = vec![1.0, 1.0e-12, -1.0, -1.0e-12];
    let mut input = EwaldInput::new(
        positions.clone(),
        charges.clone(),
        OrthorhombicCell {
            lengths_angstrom: [1.0e-6, 1.0e-6, 1.0e9],
        },
    );
    input.settings.alpha_per_angstrom = 1.0;
    input.settings.real_space_cutoff_angstrom = 2.0e-7;
    input.settings.reciprocal_max_indices = [1; 3];
    input.settings.dielectric = 1.0e-12;
    let first = evaluate(&input).expect("first atom order is valid");
    let order = [2_usize, 0, 3, 1];
    input.positions = order.iter().map(|&atom| positions[atom]).collect();
    input.charges_elementary = order.iter().map(|&atom| charges[atom]).collect();
    let permuted = evaluate(&input).expect("permuted atom order is valid");
    assert_eq!(
        first.energy.reciprocal_space_kcal_per_mol.to_bits(),
        permuted.energy.reciprocal_space_kcal_per_mol.to_bits()
    );
}

#[test]
fn reciprocal_phase_origin_is_atom_order_independent() {
    let positions = vec![
        Position::new(0.0, 0.0, 0.0),
        Position::new(0.0, 0.0, 158_453_747.399_991_48),
        Position::new(0.0, 0.0, 158_453_747.399_991_45),
        Position::new(0.0, 0.0, 57_217_295.914_571_5),
    ];
    let charges = vec![16.0, -16.0, 1.0e-12, -1.0e-12];
    let mut input = EwaldInput::new(
        positions.clone(),
        charges.clone(),
        OrthorhombicCell {
            lengths_angstrom: [1.0e-6, 1.0e-6, 1.0e9],
        },
    );
    input.settings.alpha_per_angstrom = 1.0;
    input.settings.real_space_cutoff_angstrom = 2.0e-7;
    input.settings.reciprocal_max_indices = [1; 3];
    input.settings.dielectric = 1.0e-12;
    let expected = evaluate(&input).expect("first phase origin order is valid");
    input.positions.swap(0, 1);
    input.charges_elementary.swap(0, 1);
    let permuted = evaluate(&input).expect("permuted phase origin order is valid");
    assert_eq!(
        permuted.energy.reciprocal_space_kcal_per_mol.to_bits(),
        expected.energy.reciprocal_space_kcal_per_mol.to_bits()
    );
}

#[test]
fn exact_box_shift_preserves_interior_remainder_bits() {
    let length = 0.001;
    let mut input = EwaldInput::new(
        vec![
            Position::new(0.000_123_456_789, 0.0, 0.0),
            Position::default(),
        ],
        vec![1.0, -1.0],
        OrthorhombicCell {
            lengths_angstrom: [length; 3],
        },
    );
    input.settings.alpha_per_angstrom = 1.0;
    input.settings.real_space_cutoff_angstrom = 0.000_4;
    input.settings.reciprocal_max_indices = [1; 3];
    input.settings.dielectric = 1.0e-12;
    let expected = evaluate(&input).expect("interior residue fixture is valid");
    input.positions[0].x_angstrom = 0.001_123_456_789;
    assert_eq!(
        (input.positions[0].x_angstrom - 0.000_123_456_789).to_bits(),
        length.to_bits()
    );
    let shifted = evaluate(&input).expect("exact image shift is valid");
    assert_eq!(shifted, expected);
}

#[test]
fn zero_charge_atoms_bypass_reciprocal_phase_checks() {
    let mut base = EwaldInput::new(
        vec![Position::default(), Position::new(0.3, 0.0, 0.0)],
        vec![1.0, -1.0],
        OrthorhombicCell {
            lengths_angstrom: [1.0, 1.0, 1.0e9],
        },
    );
    base.settings.alpha_per_angstrom = 1.0;
    base.settings.real_space_cutoff_angstrom = 0.2;
    base.settings.reciprocal_max_indices = [1; 3];
    let expected = evaluate(&base).expect("charged fixture is valid");
    base.positions.push(Position::new(0.6, 0.0, 1.0e-317));
    base.charges_elementary.push(0.0);
    let extended = evaluate(&base).expect("zero-charge phase is not evaluated");
    assert_close(
        extended.energy.total_kcal_per_mol(),
        expected.energy.total_kcal_per_mol(),
        1.0e-15,
    );
    assert!(extended.forces_kcal_per_mol_angstrom[2]
        .iter()
        .all(|component| component.to_bits() == 0));
}

#[test]
fn pair_correction_energy_is_atom_order_independent() {
    let positions = vec![
        Position::default(),
        Position::new(10.0, 0.0, 0.0),
        Position::new(0.0, 10.0, 0.0),
        Position::new(50.0, 0.0, 0.0),
    ];
    let charges = vec![1.0, 1.0, -1.0, -1.0];
    let mut input = EwaldInput::new(
        positions.clone(),
        charges.clone(),
        OrthorhombicCell {
            lengths_angstrom: [200.0; 3],
        },
    );
    input.settings.real_space_cutoff_angstrom = 1.0;
    input.settings.reciprocal_max_indices = [1; 3];
    input.settings.dielectric = 1.0e-12;
    input.pair_scales = vec![
        PairScale {
            atom_i: 0,
            atom_j: 1,
            coulomb_scale: 0.0,
        },
        PairScale {
            atom_i: 0,
            atom_j: 2,
            coulomb_scale: 0.0,
        },
        PairScale {
            atom_i: 1,
            atom_j: 3,
            coulomb_scale: f64::from_bits(1.0_f64.to_bits() - 1),
        },
    ];
    let expected = evaluate(&input).expect("first correction order is valid");

    let order = [1_usize, 0, 2, 3];
    let old_to_new = [1_usize, 0, 2, 3];
    input.positions = order.iter().map(|&atom| positions[atom]).collect();
    input.charges_elementary = order.iter().map(|&atom| charges[atom]).collect();
    for scale in &mut input.pair_scales {
        scale.atom_i = old_to_new[scale.atom_i];
        scale.atom_j = old_to_new[scale.atom_j];
    }
    let permuted = evaluate(&input).expect("permuted correction order is valid");
    assert_ne!(expected.energy.pair_correction_kcal_per_mol.to_bits(), 0);
    assert_eq!(
        permuted.energy.pair_correction_kcal_per_mol.to_bits(),
        expected.energy.pair_correction_kcal_per_mol.to_bits()
    );
}

#[test]
fn unsupported_numeric_extremes_have_typed_failures() {
    let input = rich_input();

    for coordinate in [-1.0e13, 1.0e13] {
        let mut invalid = input.clone();
        invalid.positions[0].x_angstrom = coordinate;
        assert_error(&invalid, EwaldErrorCode::InvalidParameter);
    }

    for charge in [1.0e-200, 17.0] {
        let mut invalid = input.clone();
        invalid.charges_elementary = vec![charge, -charge, 0.0, 0.0];
        assert_error(&invalid, EwaldErrorCode::InvalidParameter);
    }

    for length in [1.0e-7, 1.0e10] {
        let mut invalid = input.clone();
        invalid.cell.lengths_angstrom[0] = length;
        assert_error(&invalid, EwaldErrorCode::InvalidCell);
    }

    for alpha in [1.0e-13, 1.0e7] {
        let mut invalid = input.clone();
        invalid.settings.alpha_per_angstrom = alpha;
        assert_error(&invalid, EwaldErrorCode::InvalidParameter);
    }

    for cutoff in [1.0e-9, 1.0e9] {
        let mut invalid = input.clone();
        invalid.settings.real_space_cutoff_angstrom = cutoff;
        assert_error(&invalid, EwaldErrorCode::InvalidParameter);
    }

    for dielectric in [1.0e-13, 1.0e13] {
        let mut invalid = input.clone();
        invalid.settings.dielectric = dielectric;
        assert_error(&invalid, EwaldErrorCode::InvalidParameter);
    }

    for minimum_distance in [1.0e-201, 1.0e4] {
        let mut invalid = input.clone();
        invalid.settings.minimum_pair_distance_angstrom = minimum_distance;
        assert_error(&invalid, EwaldErrorCode::InvalidParameter);
    }

    let mut invalid_relation = input;
    invalid_relation.settings.minimum_pair_distance_angstrom = 7.0;
    invalid_relation.settings.real_space_cutoff_angstrom = 7.0;
    assert_error(&invalid_relation, EwaldErrorCode::InvalidParameter);
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

    let mut excessive_work = EwaldInput::new(
        vec![Position::default(); 4_096],
        vec![0.0; 4_096],
        input.cell,
    );
    excessive_work.settings.reciprocal_max_indices = [32, 32, 32];
    assert_error(&excessive_work, EwaldErrorCode::CapacityExceeded);

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

    let mut minimum_charged = EwaldInput::new(
        vec![Position::new(1.0e-7, 0.0, 0.0)],
        vec![1.0e-12],
        OrthorhombicCell {
            lengths_angstrom: [1.0e-6; 3],
        },
    );
    minimum_charged.settings.alpha_per_angstrom = 1.0e-12;
    minimum_charged.settings.real_space_cutoff_angstrom = 2.0e-8;
    minimum_charged.settings.dielectric = 1.0e-12;
    assert_error(&minimum_charged, EwaldErrorCode::NonNeutralSystem);

    let tiny = 2.0_f64.powi(-39);
    for charges in [[1.0, tiny, -1.0], [1.0, -1.0, tiny]] {
        let order_sensitive = EwaldInput::new(
            vec![
                Position::new(1.0, 1.0, 1.0),
                Position::new(2.0, 2.0, 2.0),
                Position::new(3.0, 3.0, 3.0),
            ],
            charges.to_vec(),
            input.cell,
        );
        assert_error(&order_sensitive, EwaldErrorCode::NonNeutralSystem);
    }

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
