use betelgeuze_runtime as runtime;
use runtime::{
    AtomNonbonded, Backend, Context, ContextOptions, DirectEwaldCompositeEnergyComponents,
    DirectEwaldCompositeEvaluation, DirectEwaldError, DirectEwaldErrorCode, DirectEwaldModel,
    DirectEwaldPairExclusion, DirectEwaldPairScale, DirectEwaldParameters, DirectEwaldSettings,
    ErrorCode, ForceField, ForceFieldInput, HarmonicAngle, HarmonicBond, NonbondedSettings,
    OrthorhombicCell, PairExclusion, PairScale, ParticleSoa, PeriodicTorsion, PositionSoa, System,
};

const POSITIONS: [[f64; 3]; 4] = [
    [1.25, 2.50, 3.75],
    [5.10, 3.20, 8.40],
    [7.20, 8.30, 5.70],
    [12.40, 9.10, 8.30],
];
const MASSES: [f64; 4] = [12.0, 14.0, 16.0, 18.0];
const CHARGES: [f64; 4] = [0.7, -0.4, -0.6, 0.300_000_000_000_000_04];
const ZERO_CHARGES: [f64; 4] = [0.0; 4];
const CELL_LENGTHS: [f64; 3] = [18.0, 20.0, 22.0];

struct Fixture {
    system: System,
    zero_charge_system: System,
    forcefield: ForceField,
    model: DirectEwaldModel,
}

fn fixture() -> Fixture {
    Fixture {
        system: system(&CHARGES),
        zero_charge_system: system(&ZERO_CHARGES),
        forcefield: forcefield(CELL_LENGTHS, [true; 3]),
        model: matching_model(CELL_LENGTHS),
    }
}

fn system(charges: &[f64]) -> System {
    let x: Vec<_> = POSITIONS.iter().map(|position| position[0]).collect();
    let y: Vec<_> = POSITIONS.iter().map(|position| position[1]).collect();
    let z: Vec<_> = POSITIONS.iter().map(|position| position[2]).collect();
    System::new(ParticleSoa::new(
        PositionSoa::new(&x, &y, &z),
        &MASSES,
        charges,
    ))
    .expect("four-atom system must be accepted")
}

fn forcefield(cell_lengths: [f64; 3], periodic_axes: [bool; 3]) -> ForceField {
    let atoms = [
        AtomNonbonded {
            sigma_angstrom: 3.10,
            epsilon_kcal_per_mol: 0.14,
        },
        AtomNonbonded {
            sigma_angstrom: 3.35,
            epsilon_kcal_per_mol: 0.18,
        },
        AtomNonbonded {
            sigma_angstrom: 3.00,
            epsilon_kcal_per_mol: 0.11,
        },
        AtomNonbonded {
            sigma_angstrom: 3.45,
            epsilon_kcal_per_mol: 0.16,
        },
    ];
    let bonds = [
        HarmonicBond {
            atom_i: 0,
            atom_j: 1,
            equilibrium_angstrom: 5.70,
            force_constant_kcal_per_mol_angstrom2: 2.5,
        },
        HarmonicBond {
            atom_i: 1,
            atom_j: 2,
            equilibrium_angstrom: 5.80,
            force_constant_kcal_per_mol_angstrom2: 1.75,
        },
    ];
    let angles = [HarmonicAngle {
        atom_i: 0,
        atom_j: 1,
        atom_k: 2,
        equilibrium_radians: 1.7,
        force_constant_kcal_per_mol_radian2: 1.25,
    }];
    let torsions = [PeriodicTorsion {
        atom_i: 0,
        atom_j: 1,
        atom_k: 2,
        atom_l: 3,
        periodicity: 3,
        phase_radians: -0.4,
        amplitude_kcal_per_mol: 0.35,
    }];
    let exclusions = [PairExclusion {
        atom_i: 0,
        atom_j: 1,
    }];
    let pair_scales = [PairScale {
        atom_i: 2,
        atom_j: 3,
        lennard_jones_scale: 0.4,
        coulomb_scale: 0.5,
    }];
    let mut input = ForceFieldInput::new(&atoms);
    input.bonds = &bonds;
    input.angles = &angles;
    input.torsions = &torsions;
    input.exclusions = &exclusions;
    input.pair_scales = &pair_scales;
    input.cell = Some(OrthorhombicCell {
        lengths_angstrom: cell_lengths,
        periodic_axes,
    });
    input.nonbonded = NonbondedSettings {
        cutoff_angstrom: 8.9,
        switch_start_angstrom: 7.5,
        dielectric: 1.0,
        screening_kappa_per_angstrom: 0.0,
        minimum_pair_distance_angstrom: 1.0e-8,
    };
    ForceField::new(input).expect("four-atom force field must be accepted")
}

fn matching_model(cell_lengths: [f64; 3]) -> DirectEwaldModel {
    let exclusions = [DirectEwaldPairExclusion {
        atom_i: 0,
        atom_j: 1,
    }];
    let pair_scales = [DirectEwaldPairScale {
        atom_i: 2,
        atom_j: 3,
        coulomb_scale: 0.5,
    }];
    model(cell_lengths, &exclusions, &pair_scales)
}

fn model(
    cell_lengths: [f64; 3],
    exclusions: &[DirectEwaldPairExclusion],
    pair_scales: &[DirectEwaldPairScale],
) -> DirectEwaldModel {
    let mut parameters = DirectEwaldParameters::new(4, cell_lengths);
    parameters.exclusions = exclusions;
    parameters.pair_scales = pair_scales;
    parameters.settings = DirectEwaldSettings {
        alpha_per_angstrom: 0.31,
        real_space_cutoff_angstrom: 8.9,
        reciprocal_max_indices: [5, 5, 5],
        dielectric: 1.0,
        minimum_pair_distance_angstrom: 1.0e-8,
    };
    DirectEwaldModel::new(parameters).expect("four-atom direct-Ewald model must be accepted")
}

fn context(backend: Backend) -> Context {
    let options = match backend {
        Backend::CppCpuReference => ContextOptions::cpu_reference(),
        Backend::RustCpu => ContextOptions::rust_cpu(),
        _ => panic!("test helper admits only explicit CPU lanes"),
    };
    Context::new(options).expect("CPU context must be available")
}

#[test]
fn both_cpu_lanes_equal_the_independent_parent_sum_without_coulomb_double_counting() {
    let fixture = fixture();
    let mut lane_results = Vec::new();

    for backend in [Backend::CppCpuReference, Backend::RustCpu] {
        let context = context(backend);
        let composite = context
            .evaluate_direct_ewald_composite(&fixture.system, &fixture.forcefield, &fixture.model)
            .expect("composite evaluation must succeed");
        let repeated = context
            .evaluate_direct_ewald_composite(&fixture.system, &fixture.forcefield, &fixture.model)
            .expect("repeated composite evaluation must succeed");
        assert_composite_bits(&composite, &repeated);

        let energy_only = context
            .evaluate_direct_ewald_composite_energy(
                &fixture.system,
                &fixture.forcefield,
                &fixture.model,
            )
            .expect("composite energy-only evaluation must succeed");
        assert_composite_energy_bits(&composite.energy, &energy_only);

        let zero_charge_short = context
            .evaluate(&fixture.zero_charge_system, &fixture.forcefield)
            .expect("independent zero-charge short-range evaluation must succeed");
        let ewald = context
            .evaluate_direct_ewald(&fixture.system, &fixture.model)
            .expect("independent direct-Ewald evaluation must succeed");

        assert_eq!(
            composite.energy.short_coulomb_kcal_per_mol.to_bits(),
            0.0_f64.to_bits(),
            "composite short Coulomb must be exact +0.0 on {backend:?}"
        );
        assert_eq!(
            zero_charge_short.energy.coulomb_kcal_per_mol.to_bits(),
            0.0_f64.to_bits(),
            "independent zero-charge short Coulomb must be exact +0.0 on {backend:?}"
        );
        assert_ne!(
            zero_charge_short
                .energy
                .harmonic_bond_kcal_per_mol
                .to_bits(),
            0.0_f64.to_bits(),
            "fixture must exercise bonded energy"
        );
        assert_ne!(
            zero_charge_short
                .energy
                .lennard_jones_kcal_per_mol
                .to_bits(),
            0.0_f64.to_bits(),
            "fixture must exercise Lennard-Jones energy"
        );
        assert_parent_energy_bits(&composite.energy, &zero_charge_short.energy, &ewald.energy);
        assert_parent_force_sum_bits(&composite, &zero_charge_short, &ewald);

        let charged_short = context
            .evaluate(&fixture.system, &fixture.forcefield)
            .expect("ordinary charged short-range evaluation must succeed");
        assert_eq!(
            charged_short.energy.harmonic_bond_kcal_per_mol.to_bits(),
            zero_charge_short
                .energy
                .harmonic_bond_kcal_per_mol
                .to_bits()
        );
        assert_eq!(
            charged_short.energy.harmonic_angle_kcal_per_mol.to_bits(),
            zero_charge_short
                .energy
                .harmonic_angle_kcal_per_mol
                .to_bits()
        );
        assert_eq!(
            charged_short.energy.periodic_torsion_kcal_per_mol.to_bits(),
            zero_charge_short
                .energy
                .periodic_torsion_kcal_per_mol
                .to_bits()
        );
        assert_eq!(
            charged_short.energy.lennard_jones_kcal_per_mol.to_bits(),
            zero_charge_short
                .energy
                .lennard_jones_kcal_per_mol
                .to_bits()
        );
        assert_ne!(
            charged_short.energy.coulomb_kcal_per_mol.to_bits(),
            0.0_f64.to_bits(),
            "charged short-range fixture must expose the double-counted term"
        );
        let naive_double_counted_total =
            charged_short.energy.total_kcal_per_mol + ewald.energy.total_kcal_per_mol;
        assert_ne!(
            naive_double_counted_total.to_bits(),
            composite.energy.total_kcal_per_mol.to_bits(),
            "composite must differ from charged-short plus Ewald on {backend:?}"
        );
        assert_close(
            naive_double_counted_total - composite.energy.total_kcal_per_mol,
            charged_short.energy.coulomb_kcal_per_mol,
            "double-counted Coulomb distinction",
        );

        lane_results.push(composite);
    }

    assert_composite_close(&lane_results[0], &lane_results[1]);
}

#[test]
fn typed_non_neutral_failure_is_stable_and_recoverable_on_both_cpu_lanes() {
    let fixture = fixture();
    let non_neutral = system(&[0.7, -0.4, -0.6, 0.4]);

    for backend in [Backend::CppCpuReference, Backend::RustCpu] {
        let context = context(backend);
        let baseline = context
            .evaluate_direct_ewald_composite(&fixture.system, &fixture.forcefield, &fixture.model)
            .expect("baseline composite evaluation must succeed");
        let force_error = context
            .evaluate_direct_ewald_composite(&non_neutral, &fixture.forcefield, &fixture.model)
            .expect_err("non-neutral composite force evaluation must fail");
        let energy_error = context
            .evaluate_direct_ewald_composite_energy(
                &non_neutral,
                &fixture.forcefield,
                &fixture.model,
            )
            .expect_err("non-neutral composite energy evaluation must fail");
        assert_eq!(force_error, energy_error);
        assert_eq!(force_error.status, ErrorCode::NumericalError);
        assert_eq!(
            force_error.code,
            Some(DirectEwaldErrorCode::NonNeutralSystem)
        );
        assert!(!force_error.detail.is_empty());

        let recovered = context
            .evaluate_direct_ewald_composite(&fixture.system, &fixture.forcefield, &fixture.model)
            .expect("typed failure must not poison later evaluation");
        assert_composite_bits(&baseline, &recovered);
    }
}

#[test]
fn pair_provenance_cell_and_periodicity_mismatches_fail_closed() {
    let fixture = fixture();
    let provenance_scales = [
        DirectEwaldPairScale {
            atom_i: 0,
            atom_j: 1,
            coulomb_scale: 0.0,
        },
        DirectEwaldPairScale {
            atom_i: 2,
            atom_j: 3,
            coulomb_scale: 0.5,
        },
    ];
    let provenance_mismatch = model(CELL_LENGTHS, &[], &provenance_scales);

    let mut mismatched_cell = CELL_LENGTHS;
    mismatched_cell[2] = f64::from_bits(mismatched_cell[2].to_bits() + 1);
    let cell_mismatch = matching_model(mismatched_cell);
    let periodicity_mismatch = forcefield(CELL_LENGTHS, [true, true, false]);

    for backend in [Backend::CppCpuReference, Backend::RustCpu] {
        let context = context(backend);
        let error = context
            .evaluate_direct_ewald_composite(
                &fixture.system,
                &fixture.forcefield,
                &provenance_mismatch,
            )
            .expect_err("pair provenance mismatch must fail");
        assert_untyped_mismatch(error, "exclusion provenance");

        let error = context
            .evaluate_direct_ewald_composite(&fixture.system, &fixture.forcefield, &cell_mismatch)
            .expect_err("cell-bit mismatch must fail");
        assert_untyped_mismatch(error, "cell bits must match");

        let error = context
            .evaluate_direct_ewald_composite(&fixture.system, &periodicity_mismatch, &fixture.model)
            .expect_err("partial-periodicity mismatch must fail");
        assert_untyped_mismatch(error, "periodic on all three axes");

        context
            .evaluate_direct_ewald_composite(&fixture.system, &fixture.forcefield, &fixture.model)
            .expect("compatibility failures must not poison valid handles");
    }
}

#[test]
fn composite_profile_identity_is_frozen() {
    assert_eq!(
        runtime::direct_ewald_composite_profile_id().unwrap(),
        "betelgeuze.native_direct_ewald_composite/1.0.0"
    );
}

fn assert_parent_energy_bits(
    composite: &DirectEwaldCompositeEnergyComponents,
    short: &runtime::EnergyComponents,
    ewald: &runtime::DirectEwaldEnergyComponents,
) {
    for (name, observed, expected) in [
        (
            "short bond",
            composite.short_harmonic_bond_kcal_per_mol,
            short.harmonic_bond_kcal_per_mol,
        ),
        (
            "short angle",
            composite.short_harmonic_angle_kcal_per_mol,
            short.harmonic_angle_kcal_per_mol,
        ),
        (
            "short torsion",
            composite.short_periodic_torsion_kcal_per_mol,
            short.periodic_torsion_kcal_per_mol,
        ),
        (
            "short Lennard-Jones",
            composite.short_lennard_jones_kcal_per_mol,
            short.lennard_jones_kcal_per_mol,
        ),
        (
            "short Coulomb",
            composite.short_coulomb_kcal_per_mol,
            short.coulomb_kcal_per_mol,
        ),
        (
            "short total",
            composite.short_total_kcal_per_mol,
            short.total_kcal_per_mol,
        ),
        (
            "Ewald real",
            composite.ewald_real_space_kcal_per_mol,
            ewald.real_space_kcal_per_mol,
        ),
        (
            "Ewald reciprocal",
            composite.ewald_reciprocal_space_kcal_per_mol,
            ewald.reciprocal_space_kcal_per_mol,
        ),
        (
            "Ewald self",
            composite.ewald_self_kcal_per_mol,
            ewald.self_kcal_per_mol,
        ),
        (
            "Ewald pair correction",
            composite.ewald_pair_correction_kcal_per_mol,
            ewald.pair_correction_kcal_per_mol,
        ),
        (
            "Ewald total",
            composite.ewald_total_kcal_per_mol,
            ewald.total_kcal_per_mol,
        ),
        (
            "grand total",
            composite.total_kcal_per_mol,
            short.total_kcal_per_mol + ewald.total_kcal_per_mol,
        ),
    ] {
        assert_eq!(
            observed.to_bits(),
            expected.to_bits(),
            "composite component differs from independent parent: {name}"
        );
    }
}

fn assert_parent_force_sum_bits(
    composite: &DirectEwaldCompositeEvaluation,
    short: &runtime::Evaluation,
    ewald: &runtime::DirectEwaldEvaluation,
) {
    for (axis, composite, short, ewald) in [
        (
            "x",
            composite.forces.x_kcal_per_mol_angstrom.as_slice(),
            short.forces.x_kcal_per_mol_angstrom.as_slice(),
            ewald.forces.x_kcal_per_mol_angstrom.as_slice(),
        ),
        (
            "y",
            composite.forces.y_kcal_per_mol_angstrom.as_slice(),
            short.forces.y_kcal_per_mol_angstrom.as_slice(),
            ewald.forces.y_kcal_per_mol_angstrom.as_slice(),
        ),
        (
            "z",
            composite.forces.z_kcal_per_mol_angstrom.as_slice(),
            short.forces.z_kcal_per_mol_angstrom.as_slice(),
            ewald.forces.z_kcal_per_mol_angstrom.as_slice(),
        ),
    ] {
        assert_eq!(composite.len(), short.len());
        assert_eq!(composite.len(), ewald.len());
        for (atom, ((observed, short), ewald)) in composite.iter().zip(short).zip(ewald).enumerate()
        {
            assert_eq!(
                observed.to_bits(),
                (short + ewald).to_bits(),
                "composite force differs from independent parent sum: atom {atom} axis {axis}"
            );
        }
    }
}

fn assert_composite_bits(
    left: &DirectEwaldCompositeEvaluation,
    right: &DirectEwaldCompositeEvaluation,
) {
    assert_composite_energy_bits(&left.energy, &right.energy);
    for (axis, left, right) in [
        (
            "x",
            left.forces.x_kcal_per_mol_angstrom.as_slice(),
            right.forces.x_kcal_per_mol_angstrom.as_slice(),
        ),
        (
            "y",
            left.forces.y_kcal_per_mol_angstrom.as_slice(),
            right.forces.y_kcal_per_mol_angstrom.as_slice(),
        ),
        (
            "z",
            left.forces.z_kcal_per_mol_angstrom.as_slice(),
            right.forces.z_kcal_per_mol_angstrom.as_slice(),
        ),
    ] {
        assert_eq!(left.len(), right.len());
        for (atom, (left, right)) in left.iter().zip(right).enumerate() {
            assert_eq!(
                left.to_bits(),
                right.to_bits(),
                "composite force is not bit-repeatable: atom {atom} axis {axis}"
            );
        }
    }
}

fn assert_composite_energy_bits(
    left: &DirectEwaldCompositeEnergyComponents,
    right: &DirectEwaldCompositeEnergyComponents,
) {
    for (name, left, right) in composite_energy_rows(left)
        .into_iter()
        .zip(composite_energy_rows(right))
        .map(|((name, left), (_, right))| (name, left, right))
    {
        assert_eq!(
            left.to_bits(),
            right.to_bits(),
            "composite energy is not bit-identical: {name}"
        );
    }
}

fn assert_composite_close(
    left: &DirectEwaldCompositeEvaluation,
    right: &DirectEwaldCompositeEvaluation,
) {
    for ((name, left), (_, right)) in composite_energy_rows(&left.energy)
        .into_iter()
        .zip(composite_energy_rows(&right.energy))
    {
        assert_close(left, right, name);
    }
    for (axis, left, right) in [
        (
            "x",
            left.forces.x_kcal_per_mol_angstrom.as_slice(),
            right.forces.x_kcal_per_mol_angstrom.as_slice(),
        ),
        (
            "y",
            left.forces.y_kcal_per_mol_angstrom.as_slice(),
            right.forces.y_kcal_per_mol_angstrom.as_slice(),
        ),
        (
            "z",
            left.forces.z_kcal_per_mol_angstrom.as_slice(),
            right.forces.z_kcal_per_mol_angstrom.as_slice(),
        ),
    ] {
        for (atom, (left, right)) in left.iter().zip(right).enumerate() {
            assert_close(*left, *right, &format!("cross-lane force {atom} {axis}"));
        }
    }
}

fn composite_energy_rows(
    energy: &DirectEwaldCompositeEnergyComponents,
) -> [(&'static str, f64); 12] {
    [
        ("short bond", energy.short_harmonic_bond_kcal_per_mol),
        ("short angle", energy.short_harmonic_angle_kcal_per_mol),
        ("short torsion", energy.short_periodic_torsion_kcal_per_mol),
        (
            "short Lennard-Jones",
            energy.short_lennard_jones_kcal_per_mol,
        ),
        ("short Coulomb", energy.short_coulomb_kcal_per_mol),
        ("short total", energy.short_total_kcal_per_mol),
        ("Ewald real", energy.ewald_real_space_kcal_per_mol),
        (
            "Ewald reciprocal",
            energy.ewald_reciprocal_space_kcal_per_mol,
        ),
        ("Ewald self", energy.ewald_self_kcal_per_mol),
        (
            "Ewald pair correction",
            energy.ewald_pair_correction_kcal_per_mol,
        ),
        ("Ewald total", energy.ewald_total_kcal_per_mol),
        ("grand total", energy.total_kcal_per_mol),
    ]
}

fn assert_untyped_mismatch(error: DirectEwaldError, expected_detail: &str) {
    assert_eq!(error.status, ErrorCode::InvalidArgument);
    assert_eq!(error.code, None);
    assert!(
        error.detail.contains(expected_detail),
        "unexpected mismatch detail: {}",
        error.detail
    );
}

fn assert_close(observed: f64, expected: f64, field: &str) {
    let tolerance = 3.0e-12 * expected.abs().max(1.0);
    assert!(
        (observed - expected).abs() <= tolerance,
        "{field}: observed {observed:.17e}, expected {expected:.17e}, tolerance {tolerance:.3e}"
    );
}
