use betelgeuze_reference_physics::{
    evaluate, AtomNonbonded, EnergyComponents, HarmonicAngle, HarmonicBond, NonbondedSettings,
    OracleErrorCode, OracleInput, OrthorhombicCell, PairExclusion, PairScale, PeriodicTorsion,
    Position,
};

fn atom(sigma: f64, epsilon: f64, charge: f64) -> AtomNonbonded {
    AtomNonbonded {
        sigma_angstrom: sigma,
        epsilon_kcal_per_mol: epsilon,
        charge_elementary: charge,
    }
}

fn quiet_input(positions: Vec<Position>) -> OracleInput {
    let parameters = positions.iter().map(|_| atom(1.0, 0.0, 0.0)).collect();
    OracleInput::new(positions, parameters)
}

fn pair_input() -> OracleInput {
    let mut input = OracleInput::new(
        vec![Position::new(0.0, 0.0, 0.0), Position::new(2.0, 0.0, 0.0)],
        vec![atom(1.0, 1.0, 1.0), atom(2.0, 4.0, -0.5)],
    );
    input.nonbonded = NonbondedSettings {
        cutoff_angstrom: 12.0,
        switch_start_angstrom: 10.0,
        ..NonbondedSettings::default()
    };
    input
}

fn rich_input() -> OracleInput {
    let mut input = OracleInput::new(
        vec![
            Position::new(0.2, -0.3, 0.4),
            Position::new(1.3, 0.1, -0.2),
            Position::new(1.7, 1.2, 0.5),
            Position::new(0.9, 1.8, 1.4),
        ],
        vec![
            atom(1.2, 0.4, 0.3),
            atom(1.5, 0.7, -0.2),
            atom(1.1, 0.2, 0.5),
            atom(1.8, 0.9, -0.4),
        ],
    );
    input.bonds = vec![
        HarmonicBond {
            atom_i: 0,
            atom_j: 1,
            equilibrium_angstrom: 1.1,
            force_constant_kcal_per_mol_angstrom2: 18.0,
        },
        HarmonicBond {
            atom_i: 1,
            atom_j: 2,
            equilibrium_angstrom: 1.3,
            force_constant_kcal_per_mol_angstrom2: 11.0,
        },
    ];
    input.angles = vec![HarmonicAngle {
        atom_i: 0,
        atom_j: 1,
        atom_k: 2,
        equilibrium_radians: 1.4,
        force_constant_kcal_per_mol_radian2: 7.0,
    }];
    input.torsions = vec![PeriodicTorsion {
        atom_i: 0,
        atom_j: 1,
        atom_k: 2,
        atom_l: 3,
        periodicity: 3,
        phase_radians: 0.37,
        amplitude_kcal_per_mol: 1.6,
    }];
    input.exclusions = vec![PairExclusion {
        atom_i: 0,
        atom_j: 1,
    }];
    input.pair_scales = vec![PairScale {
        atom_i: 3,
        atom_j: 1,
        lennard_jones_scale: 0.4,
        coulomb_scale: 0.7,
    }];
    input.nonbonded = NonbondedSettings {
        cutoff_angstrom: 12.0,
        switch_start_angstrom: 10.0,
        dielectric: 2.5,
        screening_kappa_per_angstrom: 0.08,
        minimum_pair_distance_angstrom: 1.0e-8,
    };
    input
}

fn assert_close(actual: f64, expected: f64) {
    let scale = 1.0 + actual.abs().max(expected.abs());
    assert!(
        (actual - expected).abs() <= 2.0e-12 * scale,
        "actual={actual:.17e}, expected={expected:.17e}"
    );
}

fn assert_components_close(actual: EnergyComponents, expected: EnergyComponents) {
    assert_close(
        actual.harmonic_bond_kcal_per_mol,
        expected.harmonic_bond_kcal_per_mol,
    );
    assert_close(
        actual.harmonic_angle_kcal_per_mol,
        expected.harmonic_angle_kcal_per_mol,
    );
    assert_close(
        actual.periodic_torsion_kcal_per_mol,
        expected.periodic_torsion_kcal_per_mol,
    );
    assert_close(
        actual.lennard_jones_kcal_per_mol,
        expected.lennard_jones_kcal_per_mol,
    );
    assert_close(actual.coulomb_kcal_per_mol, expected.coulomb_kcal_per_mol);
}

fn assert_error(input: &OracleInput, expected: OracleErrorCode) {
    let error = evaluate(input).expect_err("malformed input must be rejected");
    assert_eq!(error.code(), expected, "unexpected error: {error}");
    assert!(!error.detail().is_empty());
}

#[test]
fn energy_is_invariant_under_global_translation_and_rotation() {
    let input = rich_input();
    let expected = evaluate(&input).expect("base geometry is valid");

    let mut translated = input.clone();
    for point in &mut translated.positions {
        point.x_angstrom += 3.25;
        point.y_angstrom -= 1.75;
        point.z_angstrom += 2.5;
    }
    assert_components_close(
        evaluate(&translated).expect("translated geometry is valid"),
        expected,
    );

    // A proper 90-degree rotation about z: (x, y, z) -> (-y, x, z).
    let mut rotated = input.clone();
    for point in &mut rotated.positions {
        let old_x = point.x_angstrom;
        point.x_angstrom = -point.y_angstrom;
        point.y_angstrom = old_x;
    }
    assert_components_close(
        evaluate(&rotated).expect("rotated geometry is valid"),
        expected,
    );
}

#[test]
fn bonded_energy_is_invariant_under_endpoint_and_quartet_reversal() {
    let positions = vec![
        Position::new(0.2, -0.3, 0.4),
        Position::new(1.3, 0.1, -0.2),
        Position::new(1.7, 1.2, 0.5),
        Position::new(0.9, 1.8, 1.4),
    ];
    let mut forward = quiet_input(positions);
    forward.bonds = vec![HarmonicBond {
        atom_i: 0,
        atom_j: 1,
        equilibrium_angstrom: 1.1,
        force_constant_kcal_per_mol_angstrom2: 18.0,
    }];
    forward.angles = vec![HarmonicAngle {
        atom_i: 0,
        atom_j: 1,
        atom_k: 2,
        equilibrium_radians: 1.4,
        force_constant_kcal_per_mol_radian2: 7.0,
    }];
    forward.torsions = vec![PeriodicTorsion {
        atom_i: 0,
        atom_j: 1,
        atom_k: 2,
        atom_l: 3,
        periodicity: 3,
        phase_radians: 0.37,
        amplitude_kcal_per_mol: 1.6,
    }];

    let mut reversed = forward.clone();
    reversed.bonds[0].atom_i = 1;
    reversed.bonds[0].atom_j = 0;
    reversed.angles[0].atom_i = 2;
    reversed.angles[0].atom_k = 0;
    reversed.torsions[0] = PeriodicTorsion {
        atom_i: 3,
        atom_j: 2,
        atom_k: 1,
        atom_l: 0,
        ..reversed.torsions[0]
    };

    assert_components_close(
        evaluate(&reversed).expect("reversed terms are valid"),
        evaluate(&forward).expect("forward terms are valid"),
    );
}

#[test]
fn reversed_bonded_terms_are_canonical_duplicates() {
    let positions = vec![
        Position::new(0.0, 0.0, 0.0),
        Position::new(1.0, 0.0, 0.0),
        Position::new(1.0, 1.0, 0.0),
        Position::new(1.0, 1.0, 1.0),
    ];

    let mut bonds = quiet_input(positions.clone());
    let bond = HarmonicBond {
        atom_i: 0,
        atom_j: 1,
        equilibrium_angstrom: 1.0,
        force_constant_kcal_per_mol_angstrom2: 1.0,
    };
    bonds.bonds = vec![
        bond,
        HarmonicBond {
            atom_i: 1,
            atom_j: 0,
            ..bond
        },
    ];
    assert_error(&bonds, OracleErrorCode::DuplicateTerm);

    let mut angles = quiet_input(positions.clone());
    let angle = HarmonicAngle {
        atom_i: 0,
        atom_j: 1,
        atom_k: 2,
        equilibrium_radians: 1.0,
        force_constant_kcal_per_mol_radian2: 1.0,
    };
    angles.angles = vec![
        angle,
        HarmonicAngle {
            atom_i: 2,
            atom_k: 0,
            ..angle
        },
    ];
    assert_error(&angles, OracleErrorCode::DuplicateTerm);

    let mut torsions = quiet_input(positions);
    let torsion = PeriodicTorsion {
        atom_i: 0,
        atom_j: 1,
        atom_k: 2,
        atom_l: 3,
        periodicity: 2,
        phase_radians: 0.3,
        amplitude_kcal_per_mol: 1.0,
    };
    torsions.torsions = vec![
        torsion,
        PeriodicTorsion {
            atom_i: 3,
            atom_j: 2,
            atom_k: 1,
            atom_l: 0,
            ..torsion
        },
    ];
    assert_error(&torsions, OracleErrorCode::DuplicateTerm);
}

#[test]
fn pbc_is_invariant_to_integer_images_and_respects_mixed_axes() {
    let mut base = OracleInput::new(
        vec![Position::new(1.0, 1.0, 1.0), Position::new(3.0, 3.0, 3.0)],
        vec![atom(1.0, 1.0, 0.5), atom(2.0, 0.25, -0.75)],
    );
    base.cell = Some(OrthorhombicCell {
        lengths_angstrom: [10.0, 12.0, 14.0],
        periodic_axes: [true, false, true],
    });
    base.nonbonded = NonbondedSettings {
        cutoff_angstrom: 4.9,
        switch_start_angstrom: 4.0,
        ..NonbondedSettings::default()
    };
    let expected = evaluate(&base).expect("base periodic geometry is valid");
    assert_ne!(expected.lennard_jones_kcal_per_mol, 0.0);
    assert_ne!(expected.coulomb_kcal_per_mol, 0.0);

    let mut periodic_image = base.clone();
    periodic_image.positions[1].x_angstrom += 2.0 * 10.0;
    periodic_image.positions[1].z_angstrom -= 2.0 * 14.0;
    let image_energy = evaluate(&periodic_image).expect("integer image is valid");
    assert_eq!(
        image_energy.lennard_jones_kcal_per_mol.to_bits(),
        expected.lennard_jones_kcal_per_mol.to_bits()
    );
    assert_eq!(
        image_energy.coulomb_kcal_per_mol.to_bits(),
        expected.coulomb_kcal_per_mol.to_bits()
    );

    let mut nonperiodic_image = base;
    nonperiodic_image.positions[1].y_angstrom += 12.0;
    let nonperiodic_energy = evaluate(&nonperiodic_image).expect("mixed-axis geometry is valid");
    assert_eq!(nonperiodic_energy.lennard_jones_kcal_per_mol, 0.0);
    assert_eq!(nonperiodic_energy.coulomb_kcal_per_mol, 0.0);
}

#[test]
fn periodic_cutoff_must_be_strictly_below_half_box() {
    let mut input = quiet_input(vec![Position::default()]);
    input.cell = Some(OrthorhombicCell {
        lengths_angstrom: [10.0, 4.0, 3.0],
        periodic_axes: [true, false, false],
    });
    input.nonbonded.cutoff_angstrom = 5.0;
    input.nonbonded.switch_start_angstrom = 4.0;
    assert_error(&input, OracleErrorCode::CutoffViolatesMinimumImage);

    input.nonbonded.cutoff_angstrom = f64::from_bits(5.0_f64.to_bits() - 1);
    evaluate(&input).expect("the representable value immediately below half-box is valid");
}

#[test]
fn exclusion_pairs_are_unordered_and_allow_coincident_atoms() {
    let mut excluded = OracleInput::new(
        vec![Position::default(), Position::default()],
        vec![atom(1.0, 1.0, 1.0), atom(1.0, 1.0, -1.0)],
    );
    excluded.exclusions = vec![PairExclusion {
        atom_i: 1,
        atom_j: 0,
    }];
    let energy = evaluate(&excluded).expect("excluded pair has no distance singularity");
    assert_eq!(energy.lennard_jones_kcal_per_mol, 0.0);
    assert_eq!(energy.coulomb_kcal_per_mol, 0.0);

    excluded.exclusions.clear();
    assert_error(&excluded, OracleErrorCode::PairBelowMinimumDistance);
}

#[test]
fn pair_rule_duplicates_conflicts_self_pairs_and_oob_indices_are_rejected() {
    let mut duplicate_exclusion = pair_input();
    duplicate_exclusion.exclusions = vec![
        PairExclusion {
            atom_i: 0,
            atom_j: 1,
        },
        PairExclusion {
            atom_i: 1,
            atom_j: 0,
        },
    ];
    assert_error(&duplicate_exclusion, OracleErrorCode::DuplicatePairRule);

    let mut duplicate_scale = pair_input();
    duplicate_scale.pair_scales = vec![
        PairScale {
            atom_i: 0,
            atom_j: 1,
            lennard_jones_scale: 0.5,
            coulomb_scale: 0.5,
        },
        PairScale {
            atom_i: 1,
            atom_j: 0,
            lennard_jones_scale: 0.25,
            coulomb_scale: 0.75,
        },
    ];
    assert_error(&duplicate_scale, OracleErrorCode::DuplicatePairRule);

    let mut conflict = pair_input();
    conflict.exclusions = vec![PairExclusion {
        atom_i: 0,
        atom_j: 1,
    }];
    conflict.pair_scales = vec![PairScale {
        atom_i: 1,
        atom_j: 0,
        lennard_jones_scale: 0.5,
        coulomb_scale: 0.5,
    }];
    assert_error(&conflict, OracleErrorCode::ConflictingPairRule);

    let mut self_pair = pair_input();
    self_pair.exclusions = vec![PairExclusion {
        atom_i: 0,
        atom_j: 0,
    }];
    assert_error(&self_pair, OracleErrorCode::RepeatedAtomIndex);

    let mut out_of_bounds = pair_input();
    out_of_bounds.pair_scales = vec![PairScale {
        atom_i: 0,
        atom_j: 2,
        lennard_jones_scale: 0.5,
        coulomb_scale: 0.5,
    }];
    assert_error(&out_of_bounds, OracleErrorCode::AtomIndexOutOfRange);
}

#[test]
fn pair_scales_apply_independently_and_are_unordered() {
    let base = pair_input();
    let unscaled = evaluate(&base).expect("base pair is valid");

    let mut scaled_input = base;
    scaled_input.pair_scales = vec![PairScale {
        atom_i: 1,
        atom_j: 0,
        lennard_jones_scale: 0.25,
        coulomb_scale: 0.5,
    }];
    let scaled = evaluate(&scaled_input).expect("reversed scale pair is valid");
    assert_close(
        scaled.lennard_jones_kcal_per_mol,
        unscaled.lennard_jones_kcal_per_mol * 0.25,
    );
    assert_close(
        scaled.coulomb_kcal_per_mol,
        unscaled.coulomb_kcal_per_mol * 0.5,
    );

    for invalid in [-0.01, 1.01, f64::NAN, f64::INFINITY] {
        let mut malformed = pair_input();
        malformed.pair_scales = vec![PairScale {
            atom_i: 0,
            atom_j: 1,
            lennard_jones_scale: invalid,
            coulomb_scale: 0.5,
        }];
        assert_error(&malformed, OracleErrorCode::InvalidParameter);
    }
}

#[test]
fn structural_and_finite_validation_is_strict() {
    let empty = OracleInput::new(Vec::new(), Vec::new());
    assert_error(&empty, OracleErrorCode::EmptySystem);

    let mismatch = OracleInput::new(vec![Position::default()], Vec::new());
    assert_error(&mismatch, OracleErrorCode::AtomParameterCountMismatch);

    for coordinate in [f64::NAN, f64::INFINITY, f64::NEG_INFINITY] {
        let input = OracleInput::new(
            vec![Position::new(coordinate, 0.0, 0.0)],
            vec![atom(1.0, 0.0, 0.0)],
        );
        assert_error(&input, OracleErrorCode::NonFiniteCoordinate);
    }

    let malformed_parameters = [
        atom(0.0, 0.0, 0.0),
        atom(-1.0, 0.0, 0.0),
        atom(f64::NAN, 0.0, 0.0),
        atom(1.0, -1.0, 0.0),
        atom(1.0, f64::INFINITY, 0.0),
        atom(1.0, 0.0, f64::NAN),
    ];
    for parameter in malformed_parameters {
        let input = OracleInput::new(vec![Position::default()], vec![parameter]);
        assert_error(&input, OracleErrorCode::InvalidParameter);
    }
}

#[test]
fn nonbonded_and_cell_parameters_are_validated() {
    let invalid_settings = [
        NonbondedSettings {
            cutoff_angstrom: 0.0,
            ..NonbondedSettings::default()
        },
        NonbondedSettings {
            cutoff_angstrom: f64::NAN,
            ..NonbondedSettings::default()
        },
        NonbondedSettings {
            switch_start_angstrom: -1.0,
            ..NonbondedSettings::default()
        },
        NonbondedSettings {
            switch_start_angstrom: 10.0,
            ..NonbondedSettings::default()
        },
        NonbondedSettings {
            dielectric: 0.0,
            ..NonbondedSettings::default()
        },
        NonbondedSettings {
            screening_kappa_per_angstrom: -0.1,
            ..NonbondedSettings::default()
        },
        NonbondedSettings {
            minimum_pair_distance_angstrom: 0.0,
            ..NonbondedSettings::default()
        },
    ];
    for settings in invalid_settings {
        let mut input = quiet_input(vec![Position::default()]);
        input.nonbonded = settings;
        assert_error(&input, OracleErrorCode::InvalidParameter);
    }

    for invalid_length in [0.0, -1.0, f64::NAN, f64::INFINITY] {
        let mut input = quiet_input(vec![Position::default()]);
        input.cell = Some(OrthorhombicCell {
            lengths_angstrom: [invalid_length, 20.0, 20.0],
            periodic_axes: [false, false, false],
        });
        assert_error(&input, OracleErrorCode::InvalidCell);
    }
}

#[test]
fn bonded_parameter_and_index_validation_is_strict() {
    let positions = vec![
        Position::new(0.0, 0.0, 0.0),
        Position::new(1.0, 0.0, 0.0),
        Position::new(1.0, 1.0, 0.0),
        Position::new(1.0, 1.0, 1.0),
    ];

    let mut bond_out_of_bounds = quiet_input(positions.clone());
    bond_out_of_bounds.bonds = vec![HarmonicBond {
        atom_i: 0,
        atom_j: 4,
        equilibrium_angstrom: 1.0,
        force_constant_kcal_per_mol_angstrom2: 1.0,
    }];
    assert_error(&bond_out_of_bounds, OracleErrorCode::AtomIndexOutOfRange);

    let mut bond_repeated = quiet_input(positions.clone());
    bond_repeated.bonds = vec![HarmonicBond {
        atom_i: 1,
        atom_j: 1,
        equilibrium_angstrom: 1.0,
        force_constant_kcal_per_mol_angstrom2: 1.0,
    }];
    assert_error(&bond_repeated, OracleErrorCode::RepeatedAtomIndex);

    for (equilibrium, force) in [(0.0, 1.0), (1.0, 0.0), (f64::NAN, 1.0)] {
        let mut input = quiet_input(positions.clone());
        input.bonds = vec![HarmonicBond {
            atom_i: 0,
            atom_j: 1,
            equilibrium_angstrom: equilibrium,
            force_constant_kcal_per_mol_angstrom2: force,
        }];
        assert_error(&input, OracleErrorCode::InvalidParameter);
    }

    for (equilibrium, force) in [
        (0.0, 1.0),
        (core::f64::consts::PI, 1.0),
        (1.0, 0.0),
        (f64::NAN, 1.0),
    ] {
        let mut input = quiet_input(positions.clone());
        input.angles = vec![HarmonicAngle {
            atom_i: 0,
            atom_j: 1,
            atom_k: 2,
            equilibrium_radians: equilibrium,
            force_constant_kcal_per_mol_radian2: force,
        }];
        assert_error(&input, OracleErrorCode::InvalidParameter);
    }

    let mut repeated_angle = quiet_input(positions.clone());
    repeated_angle.angles = vec![HarmonicAngle {
        atom_i: 0,
        atom_j: 1,
        atom_k: 0,
        equilibrium_radians: 1.0,
        force_constant_kcal_per_mol_radian2: 1.0,
    }];
    assert_error(&repeated_angle, OracleErrorCode::RepeatedAtomIndex);

    for (periodicity, phase, amplitude) in [
        (0, 0.0, 1.0),
        (13, 0.0, 1.0),
        (1, f64::NAN, 1.0),
        (1, 0.0, -1.0),
    ] {
        let mut input = quiet_input(positions.clone());
        input.torsions = vec![PeriodicTorsion {
            atom_i: 0,
            atom_j: 1,
            atom_k: 2,
            atom_l: 3,
            periodicity,
            phase_radians: phase,
            amplitude_kcal_per_mol: amplitude,
        }];
        assert_error(&input, OracleErrorCode::InvalidParameter);
    }

    let mut torsion_out_of_bounds = quiet_input(positions);
    torsion_out_of_bounds.torsions = vec![PeriodicTorsion {
        atom_i: 0,
        atom_j: 1,
        atom_k: 2,
        atom_l: 4,
        periodicity: 1,
        phase_radians: 0.0,
        amplitude_kcal_per_mol: 1.0,
    }];
    assert_error(&torsion_out_of_bounds, OracleErrorCode::AtomIndexOutOfRange);
}

#[test]
fn degenerate_angle_and_torsion_geometry_is_rejected() {
    let mut angle = quiet_input(vec![
        Position::default(),
        Position::default(),
        Position::new(1.0, 0.0, 0.0),
    ]);
    angle.angles = vec![HarmonicAngle {
        atom_i: 0,
        atom_j: 1,
        atom_k: 2,
        equilibrium_radians: 1.0,
        force_constant_kcal_per_mol_radian2: 1.0,
    }];
    assert_error(&angle, OracleErrorCode::DegenerateAngle);

    let mut zero_central_bond = quiet_input(vec![
        Position::new(-1.0, 0.0, 0.0),
        Position::default(),
        Position::default(),
        Position::new(0.0, 1.0, 0.0),
    ]);
    zero_central_bond.torsions = vec![PeriodicTorsion {
        atom_i: 0,
        atom_j: 1,
        atom_k: 2,
        atom_l: 3,
        periodicity: 1,
        phase_radians: 0.0,
        amplitude_kcal_per_mol: 1.0,
    }];
    assert_error(&zero_central_bond, OracleErrorCode::DegenerateTorsion);

    let mut collinear = quiet_input(vec![
        Position::new(-1.0, 0.0, 0.0),
        Position::new(0.0, 0.0, 0.0),
        Position::new(1.0, 0.0, 0.0),
        Position::new(2.0, 0.0, 0.0),
    ]);
    collinear.torsions = zero_central_bond.torsions;
    assert_error(&collinear, OracleErrorCode::DegenerateTorsion);
}

#[test]
fn evaluation_is_bitwise_repeatable_and_total_order_is_frozen() {
    let input = rich_input();
    let first = evaluate(&input).expect("rich input is valid");
    assert_ne!(first.harmonic_bond_kcal_per_mol, 0.0);
    assert_ne!(first.harmonic_angle_kcal_per_mol, 0.0);
    assert_ne!(first.periodic_torsion_kcal_per_mol, 0.0);
    assert_ne!(first.lennard_jones_kcal_per_mol, 0.0);
    assert_ne!(first.coulomb_kcal_per_mol, 0.0);

    for _ in 0..64 {
        let repeated = evaluate(&input).expect("repeat evaluation is valid");
        assert_eq!(repeated, first);
    }

    let manual_total = first.harmonic_bond_kcal_per_mol
        + first.harmonic_angle_kcal_per_mol
        + first.periodic_torsion_kcal_per_mol
        + first.lennard_jones_kcal_per_mol
        + first.coulomb_kcal_per_mol;
    assert_eq!(first.total_kcal_per_mol().to_bits(), manual_total.to_bits());
}
