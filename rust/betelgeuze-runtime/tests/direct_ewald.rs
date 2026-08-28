use std::collections::BTreeMap;

use betelgeuze_runtime as runtime;
use runtime::{
    Backend, Context, ContextOptions, DirectEwaldErrorCode, DirectEwaldEvaluation,
    DirectEwaldModel, DirectEwaldPairExclusion, DirectEwaldPairScale, DirectEwaldParameters,
    DirectEwaldSettings, ErrorCode, ParticleSoa, PositionSoa, System,
};

const FROZEN_ORACLE: &str = include_str!("fixtures/direct_ewald_v1.tsv");

const POSITIONS: [[f64; 3]; 4] = [
    [1.25, 2.5, 3.75],
    [5.1, 3.2, 8.4],
    [10.2, 12.3, 7.7],
    [15.4, 17.1, 19.3],
];
const CHARGES: [f64; 4] = [0.7, -0.4, -0.6, 0.300_000_000_000_000_04];

fn fixture_model() -> DirectEwaldModel {
    let exclusions = [DirectEwaldPairExclusion {
        atom_i: 0,
        atom_j: 1,
    }];
    let pair_scales = [DirectEwaldPairScale {
        atom_i: 2,
        atom_j: 3,
        coulomb_scale: 0.5,
    }];
    let mut parameters = DirectEwaldParameters::new(4, [18.0, 20.0, 22.0]);
    parameters.settings = DirectEwaldSettings {
        alpha_per_angstrom: 0.31,
        real_space_cutoff_angstrom: 8.9,
        reciprocal_max_indices: [5, 5, 5],
        dielectric: 1.0,
        minimum_pair_distance_angstrom: 1.0e-8,
    };
    parameters.exclusions = &exclusions;
    parameters.pair_scales = &pair_scales;
    DirectEwaldModel::new(parameters).expect("frozen model must be accepted")
}

fn system(positions: &[[f64; 3]], charges: &[f64]) -> System {
    let x: Vec<_> = positions.iter().map(|position| position[0]).collect();
    let y: Vec<_> = positions.iter().map(|position| position[1]).collect();
    let z: Vec<_> = positions.iter().map(|position| position[2]).collect();
    let masses = vec![1.0; positions.len()];
    System::new(ParticleSoa::new(
        PositionSoa::new(&x, &y, &z),
        &masses,
        charges,
    ))
    .expect("test system must be accepted")
}

fn context(backend: Backend) -> Context {
    let options = match backend {
        Backend::CppCpuReference => ContextOptions::cpu_reference(),
        Backend::RustCpu => ContextOptions::rust_cpu(),
        _ => panic!("test helper only admits explicit CPU lanes"),
    };
    Context::new(options).expect("CPU context must be available")
}

fn evaluate(backend: Backend) -> DirectEwaldEvaluation {
    context(backend)
        .evaluate_direct_ewald(&system(&POSITIONS, &CHARGES), &fixture_model())
        .expect("frozen fixture must evaluate")
}

#[test]
fn both_cpu_lanes_match_every_frozen_oracle_component_and_force() {
    let expected = frozen_values();
    let cpp = evaluate(Backend::CppCpuReference);
    let rust = evaluate(Backend::RustCpu);

    for (backend, observed) in [(Backend::CppCpuReference, &cpp), (Backend::RustCpu, &rust)] {
        for (name, value) in energy_rows(observed) {
            assert_close(value, expected[name], backend, name);
            if backend == Backend::RustCpu {
                assert_eq!(
                    value.to_bits(),
                    expected[name].to_bits(),
                    "Rust provider must preserve frozen oracle bits for {name}"
                );
            }
        }
        for atom in 0..4 {
            let force = [
                observed.forces.x_kcal_per_mol_angstrom[atom],
                observed.forces.y_kcal_per_mol_angstrom[atom],
                observed.forces.z_kcal_per_mol_angstrom[atom],
            ];
            for (axis, value) in force.into_iter().enumerate() {
                let name = format!("force_{atom}_{}", ["x", "y", "z"][axis]);
                assert_close(value, expected[name.as_str()], backend, &name);
                if backend == Backend::RustCpu {
                    assert_eq!(
                        value.to_bits(),
                        expected[name.as_str()].to_bits(),
                        "Rust provider must preserve frozen oracle bits for {name}"
                    );
                }
            }
        }
    }

    assert_evaluation_close(&cpp, &rust);
}

#[test]
fn each_cpu_lane_is_bitwise_repeatable_and_energy_only_is_identical() {
    for backend in [Backend::CppCpuReference, Backend::RustCpu] {
        let context = context(backend);
        let system = system(&POSITIONS, &CHARGES);
        let model = fixture_model();
        let first = context
            .evaluate_direct_ewald(&system, &model)
            .expect("first evaluation must succeed");
        for _ in 0..3 {
            let repeated = context
                .evaluate_direct_ewald(&system, &model)
                .expect("repeat must succeed");
            assert_evaluation_bits(&first, &repeated);
        }
        let energy_only = context
            .evaluate_direct_ewald_energy(&system, &model)
            .expect("energy-only evaluation must succeed");
        for (left, right) in energy_rows(&first)
            .into_iter()
            .map(|(_, value)| value)
            .zip(energy_component_values(energy_only))
        {
            assert_eq!(left.to_bits(), right.to_bits());
        }
    }
}

#[test]
fn model_deep_copies_pair_rules_and_drops_independently() {
    let model = {
        let mut exclusions = vec![DirectEwaldPairExclusion {
            atom_i: 0,
            atom_j: 1,
        }];
        let mut scales = vec![DirectEwaldPairScale {
            atom_i: 2,
            atom_j: 3,
            coulomb_scale: 0.5,
        }];
        let mut parameters = DirectEwaldParameters::new(4, [18.0, 20.0, 22.0]);
        parameters.settings = DirectEwaldSettings {
            alpha_per_angstrom: 0.31,
            real_space_cutoff_angstrom: 8.9,
            reciprocal_max_indices: [5, 5, 5],
            dielectric: 1.0,
            minimum_pair_distance_angstrom: 1.0e-8,
        };
        parameters.exclusions = &exclusions;
        parameters.pair_scales = &scales;
        let model = DirectEwaldModel::new(parameters).unwrap();
        exclusions.clear();
        scales[0].coulomb_scale = 1.0;
        model
    };

    assert_eq!(model.len().unwrap(), 4);
    let observed = context(Backend::RustCpu)
        .evaluate_direct_ewald(&system(&POSITIONS, &CHARGES), &model)
        .unwrap();
    let expected = frozen_values();
    for (name, value) in energy_rows(&observed) {
        assert_close(value, expected[name], Backend::RustCpu, name);
    }

    for _ in 0..32 {
        let temporary = fixture_model();
        assert_eq!(temporary.len().unwrap(), 4);
        drop(temporary);
    }
}

#[test]
fn typed_creation_and_evaluation_errors_are_preserved_without_poisoning_state() {
    let duplicate = [
        DirectEwaldPairExclusion {
            atom_i: 0,
            atom_j: 1,
        },
        DirectEwaldPairExclusion {
            atom_i: 1,
            atom_j: 0,
        },
    ];
    let mut invalid = DirectEwaldParameters::new(4, [18.0, 20.0, 22.0]);
    invalid.exclusions = &duplicate;
    let error = DirectEwaldModel::new(invalid)
        .err()
        .expect("duplicate pair rule must fail");
    assert_eq!(error.status, ErrorCode::InvalidArgument);
    assert_eq!(error.code, Some(DirectEwaldErrorCode::DuplicatePairRule));
    assert!(!error.detail.is_empty());

    let model = fixture_model();
    let context = context(Backend::RustCpu);
    let non_neutral = system(&POSITIONS, &[0.7, -0.4, -0.6, 0.4]);
    let first_error = context
        .evaluate_direct_ewald(&non_neutral, &model)
        .unwrap_err();
    let second_error = context
        .evaluate_direct_ewald(&non_neutral, &model)
        .unwrap_err();
    assert_eq!(first_error, second_error);
    assert_eq!(first_error.status, ErrorCode::NumericalError);
    assert_eq!(
        first_error.code,
        Some(DirectEwaldErrorCode::NonNeutralSystem)
    );

    let count_mismatch = system(&POSITIONS[..3], &[0.7, -0.4, -0.3]);
    let error = context
        .evaluate_direct_ewald(&count_mismatch, &model)
        .unwrap_err();
    assert_eq!(error.status, ErrorCode::InvalidArgument);
    assert_eq!(error.code, Some(DirectEwaldErrorCode::ChargeCountMismatch));

    let recovered = context
        .evaluate_direct_ewald(&system(&POSITIONS, &CHARGES), &model)
        .expect("prior transactional failures must not poison the model or context");
    assert_close(
        recovered.energy.total_kcal_per_mol,
        frozen_values()["total_kcal_per_mol"],
        Backend::RustCpu,
        "total_kcal_per_mol",
    );
}

#[test]
fn profile_identity_is_stable_and_nonempty() {
    assert_eq!(
        runtime::direct_ewald_profile_id().unwrap(),
        "betelgeuze.native_direct_ewald/1.0.0"
    );
}

fn energy_rows(evaluation: &DirectEwaldEvaluation) -> [(&'static str, f64); 5] {
    [
        (
            "real_space_kcal_per_mol",
            evaluation.energy.real_space_kcal_per_mol,
        ),
        (
            "reciprocal_space_kcal_per_mol",
            evaluation.energy.reciprocal_space_kcal_per_mol,
        ),
        ("self_kcal_per_mol", evaluation.energy.self_kcal_per_mol),
        (
            "pair_correction_kcal_per_mol",
            evaluation.energy.pair_correction_kcal_per_mol,
        ),
        ("total_kcal_per_mol", evaluation.energy.total_kcal_per_mol),
    ]
}

fn energy_component_values(energy: runtime::DirectEwaldEnergyComponents) -> [f64; 5] {
    [
        energy.real_space_kcal_per_mol,
        energy.reciprocal_space_kcal_per_mol,
        energy.self_kcal_per_mol,
        energy.pair_correction_kcal_per_mol,
        energy.total_kcal_per_mol,
    ]
}

fn frozen_values() -> BTreeMap<&'static str, f64> {
    assert!(FROZEN_ORACLE
        .lines()
        .any(|line| line == "# schema_id=betelgeuze.reference_direct_ewald/1.0.0"));
    FROZEN_ORACLE
        .lines()
        .filter(|line| !line.is_empty() && !line.starts_with('#') && !line.starts_with("value_id"))
        .map(|line| {
            let (name, bits) = line
                .split_once('\t')
                .expect("frozen row must be tab-separated");
            let bits = u64::from_str_radix(bits, 16).expect("frozen bits must be hexadecimal");
            (name, f64::from_bits(bits))
        })
        .collect()
}

fn assert_close(observed: f64, expected: f64, backend: Backend, field: &str) {
    let tolerance = 3.0e-12 * expected.abs().max(1.0);
    assert!(
        (observed - expected).abs() <= tolerance,
        "{backend:?} {field}: observed {observed:.17e}, expected {expected:.17e}, tolerance {tolerance:.3e}"
    );
}

fn assert_evaluation_close(left: &DirectEwaldEvaluation, right: &DirectEwaldEvaluation) {
    for ((name, left), (_, right)) in energy_rows(left).into_iter().zip(energy_rows(right)) {
        assert_close(left, right, Backend::RustCpu, name);
    }
    for atom in 0..left.forces.x_kcal_per_mol_angstrom.len() {
        for (axis, (left, right)) in [
            (
                left.forces.x_kcal_per_mol_angstrom[atom],
                right.forces.x_kcal_per_mol_angstrom[atom],
            ),
            (
                left.forces.y_kcal_per_mol_angstrom[atom],
                right.forces.y_kcal_per_mol_angstrom[atom],
            ),
            (
                left.forces.z_kcal_per_mol_angstrom[atom],
                right.forces.z_kcal_per_mol_angstrom[atom],
            ),
        ]
        .into_iter()
        .enumerate()
        {
            assert_close(
                left,
                right,
                Backend::RustCpu,
                &format!("cross_backend_force_{atom}_{axis}"),
            );
        }
    }
}

fn assert_evaluation_bits(left: &DirectEwaldEvaluation, right: &DirectEwaldEvaluation) {
    for ((name, left), (_, right)) in energy_rows(left).into_iter().zip(energy_rows(right)) {
        assert_eq!(left.to_bits(), right.to_bits(), "energy repeat: {name}");
    }
    for (channel_name, (left, right)) in [
        (
            "x",
            (
                &left.forces.x_kcal_per_mol_angstrom,
                &right.forces.x_kcal_per_mol_angstrom,
            ),
        ),
        (
            "y",
            (
                &left.forces.y_kcal_per_mol_angstrom,
                &right.forces.y_kcal_per_mol_angstrom,
            ),
        ),
        (
            "z",
            (
                &left.forces.z_kcal_per_mol_angstrom,
                &right.forces.z_kcal_per_mol_angstrom,
            ),
        ),
    ] {
        assert_eq!(left.len(), right.len());
        for (atom, (left, right)) in left.iter().zip(right).enumerate() {
            assert_eq!(
                left.to_bits(),
                right.to_bits(),
                "force repeat: atom {atom} channel {channel_name}"
            );
        }
    }
}
