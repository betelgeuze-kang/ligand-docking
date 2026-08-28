use betelgeuze_reference_ewald::{
    evaluate as evaluate_direct_ewald, EwaldInput, EwaldSettings,
    OrthorhombicCell as DirectOrthorhombicCell, Position as DirectPosition,
};
use betelgeuze_reference_pme_reciprocal::{
    evaluate, OrthorhombicCell, ParticleMeshReciprocalErrorCode, ParticleMeshReciprocalInput,
    ParticleMeshReciprocalSettings, Position, CARDINAL_B_SPLINE_ORDER,
    PARTICLE_MESH_RECIPROCAL_SCHEMA_ID,
};

fn fixture(mesh_dimension: u32) -> ParticleMeshReciprocalInput {
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
        mesh_dimensions: [mesh_dimension; 3],
        dielectric: 1.0,
    };
    input
}

fn assert_close(actual: f64, expected: f64, tolerance: f64) {
    let scale = 1.0 + actual.abs().max(expected.abs());
    assert!(
        (actual - expected).abs() <= tolerance * scale,
        "actual={actual:.17e}, expected={expected:.17e}, tolerance={tolerance:.3e}"
    );
}

fn assert_error(input: &ParticleMeshReciprocalInput, expected: ParticleMeshReciprocalErrorCode) {
    let error = evaluate(input).expect_err("malformed input must fail");
    assert_eq!(error.code(), expected, "unexpected error: {error}");
    assert!(!error.detail().is_empty());
}

#[test]
fn public_schema_and_defaults_are_stable() {
    assert_eq!(
        PARTICLE_MESH_RECIPROCAL_SCHEMA_ID,
        "betelgeuze.reference_particle_mesh_reciprocal/1.0.0"
    );
    assert_eq!(CARDINAL_B_SPLINE_ORDER, 4);
    assert_eq!(
        ParticleMeshReciprocalSettings::default(),
        ParticleMeshReciprocalSettings {
            alpha_per_angstrom: 0.3,
            mesh_dimensions: [16, 16, 16],
            dielectric: 1.0,
        }
    );
}

#[test]
fn analytic_forces_match_central_finite_differences() {
    let input = fixture(16);
    let evaluated = evaluate(&input).expect("fixture is valid");
    let step = 1.0e-5;
    for atom in 0..input.positions.len() {
        for axis in 0..3 {
            let mut minus = input.clone();
            let mut plus = input.clone();
            *coordinate_mut(&mut minus.positions[atom], axis) -= step;
            *coordinate_mut(&mut plus.positions[atom], axis) += step;
            let minus_energy = evaluate(&minus)
                .expect("minus displacement is valid")
                .reciprocal_space_kcal_per_mol;
            let plus_energy = evaluate(&plus)
                .expect("plus displacement is valid")
                .reciprocal_space_kcal_per_mol;
            let finite_difference_force = -(plus_energy - minus_energy) / (2.0 * step);
            assert_close(
                evaluated.forces_kcal_per_mol_angstrom[atom][axis],
                finite_difference_force,
                2.0e-7,
            );
        }
    }
}

#[test]
fn periodic_images_permutation_and_charge_inversion_are_invariant() {
    let input = fixture(16);
    let expected = evaluate(&input).expect("fixture is valid");
    let repeated = evaluate(&input).expect("repeat fixture is valid");
    assert_evaluation_bits_equal(&repeated, &expected);

    let mut imaged = input.clone();
    imaged.positions[0].x_angstrom += 2.0 * input.cell.lengths_angstrom[0];
    imaged.positions[1].y_angstrom -= 3.0 * input.cell.lengths_angstrom[1];
    imaged.positions[2].z_angstrom += input.cell.lengths_angstrom[2];
    assert_evaluation_close(
        &evaluate(&imaged).expect("periodic image is valid"),
        &expected,
        8.0e-12,
    );

    let order = [3_usize, 1, 0, 2];
    let mut permuted = ParticleMeshReciprocalInput::new(
        order.iter().map(|&old| input.positions[old]).collect(),
        order
            .iter()
            .map(|&old| input.charges_elementary[old])
            .collect(),
        input.cell,
    );
    permuted.settings = input.settings;
    let permuted_result = evaluate(&permuted).expect("permutation is valid");
    assert_close(
        permuted_result.reciprocal_space_kcal_per_mol,
        expected.reciprocal_space_kcal_per_mol,
        3.0e-12,
    );
    for (new, old) in order.iter().copied().enumerate() {
        for axis in 0..3 {
            assert_close(
                permuted_result.forces_kcal_per_mol_angstrom[new][axis],
                expected.forces_kcal_per_mol_angstrom[old][axis],
                5.0e-12,
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
fn integer_grid_translation_is_invariant_but_arbitrary_translation_is_bounded_aliasing() {
    let input = fixture(16);
    let expected = evaluate(&input).expect("fixture is valid");
    let mut grid_translated = input.clone();
    for position in &mut grid_translated.positions {
        position.x_angstrom += input.cell.lengths_angstrom[0] / 16.0;
        position.y_angstrom += input.cell.lengths_angstrom[1] / 16.0;
        position.z_angstrom += input.cell.lengths_angstrom[2] / 16.0;
    }
    assert_evaluation_close(
        &evaluate(&grid_translated).expect("integer-grid translation is valid"),
        &expected,
        2.0e-13,
    );

    let mut arbitrarily_translated = input;
    for position in &mut arbitrarily_translated.positions {
        position.x_angstrom += 0.317;
        position.y_angstrom -= 0.229;
        position.z_angstrom += 0.141;
    }
    let translated = evaluate(&arbitrarily_translated).expect("arbitrary translation is valid");
    let energy_aliasing =
        (translated.reciprocal_space_kcal_per_mol - expected.reciprocal_space_kcal_per_mol).abs();
    assert!(energy_aliasing > 1.0e-6);
    assert!(energy_aliasing < 2.0e-2);
    assert!(maximum_force_difference(&translated, &expected) < 5.0e-2);
    let mut net_force = [0.0_f64; 3];
    for force in &expected.forces_kcal_per_mol_angstrom {
        for axis in 0..3 {
            net_force[axis] += force[axis];
        }
    }
    assert!(net_force.into_iter().map(f64::abs).fold(0.0, f64::max) < 5.0e-2);
}

#[test]
fn mesh_refinement_is_observed_against_direct_ewald_reciprocal_energy_and_force() {
    let direct_input = direct_reciprocal_fixture();
    let direct = evaluate_direct_ewald(&direct_input)
        .expect("direct reciprocal fixture is valid")
        .energy
        .reciprocal_space_kcal_per_mol;
    let direct_forces = direct_reciprocal_finite_difference_forces(&direct_input, 1.0e-5);
    let observations = [8_u32, 16, 32].map(|dimension| {
        let particle_mesh = evaluate(&fixture(dimension)).expect("particle-mesh fixture is valid");
        (
            (particle_mesh.reciprocal_space_kcal_per_mol - direct).abs(),
            particle_mesh
                .forces_kcal_per_mol_angstrom
                .iter()
                .flatten()
                .zip(direct_forces.iter().flatten())
                .map(|(particle_mesh, direct)| (particle_mesh - direct).abs())
                .fold(0.0, f64::max),
        )
    });
    for pair in observations.windows(2) {
        assert!(pair[1].0 < pair[0].0, "mesh observations: {observations:?}");
        assert!(pair[1].1 < pair[0].1, "mesh observations: {observations:?}");
    }
    assert!(observations[2].0 < 2.0e-3);
    assert!(observations[2].1 < 3.0e-3);
}

#[test]
fn zero_mode_is_omitted_without_a_background_convention() {
    let mut input = ParticleMeshReciprocalInput::new(
        vec![Position::new(1.0, 2.0, 3.0), Position::new(4.0, 5.0, 6.0)],
        vec![0.0, -0.0],
        OrthorhombicCell {
            lengths_angstrom: [10.0, 12.0, 14.0],
        },
    );
    input.settings.mesh_dimensions = [8; 3];
    let result = evaluate(&input).expect("zero charges are exactly neutral");
    assert_eq!(result.reciprocal_space_kcal_per_mol.to_bits(), 0);
    assert!(result
        .forces_kcal_per_mol_angstrom
        .iter()
        .flatten()
        .all(|value| *value == 0.0));
}

#[test]
fn log_domain_rescues_representable_energy_and_force_after_raw_damping_underflow() {
    let mut input = ParticleMeshReciprocalInput::new(
        vec![Position::new(0.0, 0.0, 0.0), Position::new(4.0e8, 0.0, 0.0)],
        vec![16.0, -16.0],
        OrthorhombicCell {
            lengths_angstrom: [1.0e9, 1.0e-6, 1.0e-6],
        },
    );
    input.settings = ParticleMeshReciprocalSettings {
        alpha_per_angstrom: 1.15e-10,
        mesh_dimensions: [4; 3],
        dielectric: 1.0e-12,
    };
    let first_wave = core::f64::consts::TAU / input.cell.lengths_angstrom[0];
    let raw_damping = libm::exp(
        -(first_wave * first_wave)
            / (4.0 * input.settings.alpha_per_angstrom * input.settings.alpha_per_angstrom),
    );
    assert_eq!(raw_damping.to_bits(), 0);

    let evaluated = evaluate(&input).expect("log-domain fixture must evaluate");
    let energy = evaluated.reciprocal_space_kcal_per_mol;
    let force = evaluated.forces_kcal_per_mol_angstrom[1][0];
    assert!(
        energy.is_normal() && energy > 0.0,
        "rescued energy={energy:e}"
    );
    assert!(force.is_normal() && force < 0.0, "rescued force={force:e}");
    assert_relative_without_unit_floor(energy, 7.474_641_776_1e-287, 1.0e-8);
    assert_relative_without_unit_floor(force, -1.699_957_466_4e-295, 1.0e-8);

    let step = 1.0e3;
    let mut minus = input.clone();
    let mut plus = input;
    minus.positions[1].x_angstrom -= step;
    plus.positions[1].x_angstrom += step;
    let minus_energy = evaluate(&minus)
        .expect("minus rescue displacement must evaluate")
        .reciprocal_space_kcal_per_mol;
    let plus_energy = evaluate(&plus)
        .expect("plus rescue displacement must evaluate")
        .reciprocal_space_kcal_per_mol;
    let finite_difference_force = -(plus_energy - minus_energy) / (2.0 * step);
    assert!(finite_difference_force.is_normal());
    assert_relative_without_unit_floor(force, finite_difference_force, 1.0e-8);
}

#[test]
fn power_of_two_scaled_rescue_preserves_force_when_energy_and_phihat_round_to_zero() {
    let mut input = ParticleMeshReciprocalInput::new(
        vec![
            Position::new(0.0, 0.0, 0.0),
            Position::new(4.0e-7, 0.0, 0.0),
        ],
        vec![16.0, -16.0],
        OrthorhombicCell {
            lengths_angstrom: [1.0e-6; 3],
        },
    );
    input.settings = ParticleMeshReciprocalSettings {
        alpha_per_angstrom: 1.15e5,
        mesh_dimensions: [4; 3],
        dielectric: 1.0e12,
    };
    let first_wave = core::f64::consts::TAU / input.cell.lengths_angstrom[0];
    let raw_damping = libm::exp(
        -(first_wave * first_wave)
            / (4.0 * input.settings.alpha_per_angstrom * input.settings.alpha_per_angstrom),
    );
    assert_eq!(raw_damping.to_bits(), 0);

    let evaluated = evaluate(&input).expect("force-rescue fixture must evaluate");
    assert_eq!(evaluated.reciprocal_space_kcal_per_mol.to_bits(), 0);
    let force = evaluated.forces_kcal_per_mol_angstrom[1][0];
    assert!(
        force.is_subnormal() && force < 0.0,
        "rescued force={force:e}"
    );
    assert_relative_without_unit_floor(force, -1.699_957_466_4e-319, 1.0e-3);

    let mut aggregate_energy = input;
    aggregate_energy.settings.dielectric = 2.5e10;
    let aggregated = evaluate(&aggregate_energy).expect("energy aggregation must evaluate");
    assert_eq!(aggregated.reciprocal_space_kcal_per_mol.to_bits(), 1);
}

#[test]
fn validation_error_categories_are_stable() {
    let base = fixture(4);

    let mut malformed = base.clone();
    malformed.positions.clear();
    malformed.charges_elementary.clear();
    assert_error(&malformed, ParticleMeshReciprocalErrorCode::EmptySystem);

    let mut malformed = base.clone();
    malformed.positions = vec![Position::default(); 4_097];
    malformed.charges_elementary = vec![0.0; 4_097];
    assert_error(
        &malformed,
        ParticleMeshReciprocalErrorCode::CapacityExceeded,
    );

    let mut malformed = base.clone();
    malformed.charges_elementary.pop();
    assert_error(
        &malformed,
        ParticleMeshReciprocalErrorCode::ChargeCountMismatch,
    );

    let mut malformed = base.clone();
    malformed.positions[0].x_angstrom = f64::NAN;
    assert_error(
        &malformed,
        ParticleMeshReciprocalErrorCode::NonFiniteCoordinate,
    );

    let mut malformed = base.clone();
    malformed.charges_elementary[0] = f64::INFINITY;
    assert_error(&malformed, ParticleMeshReciprocalErrorCode::NonFiniteCharge);

    let mut malformed = base.clone();
    malformed.charges_elementary[0] += 0.25;
    assert_error(
        &malformed,
        ParticleMeshReciprocalErrorCode::NonNeutralSystem,
    );

    let mut malformed = base.clone();
    malformed.cell.lengths_angstrom[1] = 0.0;
    assert_error(&malformed, ParticleMeshReciprocalErrorCode::InvalidCell);

    let mut malformed = base.clone();
    malformed.settings.alpha_per_angstrom = 0.0;
    assert_error(
        &malformed,
        ParticleMeshReciprocalErrorCode::InvalidParameter,
    );

    let mut malformed = base.clone();
    malformed.charges_elementary = vec![f64::from_bits(1), -f64::from_bits(1), 0.0, 0.0];
    assert_error(
        &malformed,
        ParticleMeshReciprocalErrorCode::InvalidParameter,
    );

    let mut malformed = base.clone();
    malformed.settings.mesh_dimensions = [4, 6, 4];
    assert_error(&malformed, ParticleMeshReciprocalErrorCode::InvalidMesh);

    let mut malformed = base;
    malformed.settings.mesh_dimensions = [128; 3];
    assert_error(
        &malformed,
        ParticleMeshReciprocalErrorCode::CapacityExceeded,
    );

    let mut work_bounded = fixture(4);
    work_bounded.settings.mesh_dimensions = [64, 128, 128];
    assert_eq!(
        work_bounded
            .settings
            .mesh_dimensions
            .into_iter()
            .product::<u32>(),
        1_048_576
    );
    assert_error(
        &work_bounded,
        ParticleMeshReciprocalErrorCode::CapacityExceeded,
    );
}

fn direct_reciprocal_fixture() -> EwaldInput {
    let mut input = EwaldInput::new(
        vec![
            DirectPosition::new(1.25, 2.5, 3.75),
            DirectPosition::new(5.1, 3.2, 8.4),
            DirectPosition::new(10.2, 12.3, 7.7),
            DirectPosition::new(15.4, 17.1, 19.3),
        ],
        vec![0.7, -0.4, -0.6, 0.300_000_000_000_000_04],
        DirectOrthorhombicCell {
            lengths_angstrom: [18.0, 20.0, 22.0],
        },
    );
    input.settings = EwaldSettings {
        alpha_per_angstrom: 0.31,
        real_space_cutoff_angstrom: 1.0e-7,
        reciprocal_max_indices: [9; 3],
        dielectric: 1.0,
        minimum_pair_distance_angstrom: 1.0e-8,
    };
    input
}

fn direct_reciprocal_finite_difference_forces(input: &EwaldInput, step: f64) -> Vec<[f64; 3]> {
    (0..input.positions.len())
        .map(|atom| {
            core::array::from_fn(|axis| {
                let mut minus = input.clone();
                let mut plus = input.clone();
                *direct_coordinate_mut(&mut minus.positions[atom], axis) -= step;
                *direct_coordinate_mut(&mut plus.positions[atom], axis) += step;
                let minus_energy = evaluate_direct_ewald(&minus)
                    .expect("direct minus displacement is valid")
                    .energy
                    .reciprocal_space_kcal_per_mol;
                let plus_energy = evaluate_direct_ewald(&plus)
                    .expect("direct plus displacement is valid")
                    .energy
                    .reciprocal_space_kcal_per_mol;
                -(plus_energy - minus_energy) / (2.0 * step)
            })
        })
        .collect()
}

fn coordinate_mut(position: &mut Position, axis: usize) -> &mut f64 {
    match axis {
        0 => &mut position.x_angstrom,
        1 => &mut position.y_angstrom,
        2 => &mut position.z_angstrom,
        _ => unreachable!(),
    }
}

fn direct_coordinate_mut(position: &mut DirectPosition, axis: usize) -> &mut f64 {
    match axis {
        0 => &mut position.x_angstrom,
        1 => &mut position.y_angstrom,
        2 => &mut position.z_angstrom,
        _ => unreachable!(),
    }
}

fn assert_evaluation_close(
    actual: &betelgeuze_reference_pme_reciprocal::ParticleMeshReciprocalEvaluation,
    expected: &betelgeuze_reference_pme_reciprocal::ParticleMeshReciprocalEvaluation,
    tolerance: f64,
) {
    assert_close(
        actual.reciprocal_space_kcal_per_mol,
        expected.reciprocal_space_kcal_per_mol,
        tolerance,
    );
    for (actual, expected) in actual
        .forces_kcal_per_mol_angstrom
        .iter()
        .flatten()
        .zip(expected.forces_kcal_per_mol_angstrom.iter().flatten())
    {
        assert_close(*actual, *expected, tolerance);
    }
}

fn assert_evaluation_bits_equal(
    actual: &betelgeuze_reference_pme_reciprocal::ParticleMeshReciprocalEvaluation,
    expected: &betelgeuze_reference_pme_reciprocal::ParticleMeshReciprocalEvaluation,
) {
    assert_eq!(
        actual.reciprocal_space_kcal_per_mol.to_bits(),
        expected.reciprocal_space_kcal_per_mol.to_bits()
    );
    for (actual, expected) in actual
        .forces_kcal_per_mol_angstrom
        .iter()
        .flatten()
        .zip(expected.forces_kcal_per_mol_angstrom.iter().flatten())
    {
        assert_eq!(actual.to_bits(), expected.to_bits());
    }
}

fn maximum_force_difference(
    actual: &betelgeuze_reference_pme_reciprocal::ParticleMeshReciprocalEvaluation,
    expected: &betelgeuze_reference_pme_reciprocal::ParticleMeshReciprocalEvaluation,
) -> f64 {
    actual
        .forces_kcal_per_mol_angstrom
        .iter()
        .flatten()
        .zip(expected.forces_kcal_per_mol_angstrom.iter().flatten())
        .map(|(actual, expected)| (actual - expected).abs())
        .fold(0.0, f64::max)
}

fn assert_relative_without_unit_floor(actual: f64, expected: f64, tolerance: f64) {
    let scale = actual.abs().max(expected.abs());
    assert!(scale > 0.0);
    assert!(
        (actual - expected).abs() <= tolerance * scale,
        "actual={actual:.17e}, expected={expected:.17e}, tolerance={tolerance:.3e}"
    );
}
