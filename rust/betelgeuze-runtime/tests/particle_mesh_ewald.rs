use betelgeuze_runtime as runtime;
use runtime::{
    Backend, Context, ContextOptions, DirectEwaldErrorCode, DirectEwaldModel,
    DirectEwaldPairExclusion, DirectEwaldPairScale, DirectEwaldParameters, DirectEwaldSettings,
    ErrorCode, ParticleMeshEwaldEnergyComponents, ParticleMeshEwaldEvaluation,
    ParticleMeshReciprocalModel, ParticleMeshReciprocalParameters, ParticleMeshReciprocalSettings,
    ParticleSoa, PositionSoa, System,
};

const POSITIONS: [[f64; 3]; 4] = [
    [1.25, 2.5, 3.75],
    [5.1, 3.2, 8.4],
    [10.2, 12.3, 7.7],
    [15.4, 17.1, 19.3],
];
const CHARGES: [f64; 4] = [0.7, -0.4, -0.6, 0.300_000_000_000_000_04];
const EXPECTED_ENERGY_BITS: [u64; 5] = [
    0xbfbe_3560_505c_8b5a,
    0x4044_1de7_1e7a_685d,
    0xc04f_f151_251c_f865,
    0x4031_acb8_1f3a_00d4,
    0xc018_6145_396d_ef20,
];

fn direct_model(atom_count: usize) -> DirectEwaldModel {
    let exclusions = [DirectEwaldPairExclusion {
        atom_i: 0,
        atom_j: 1,
    }];
    let pair_scales = [DirectEwaldPairScale {
        atom_i: 2,
        atom_j: 3,
        coulomb_scale: 0.5,
    }];
    let mut parameters = DirectEwaldParameters::new(atom_count, [18.0, 20.0, 22.0]);
    parameters.settings = DirectEwaldSettings {
        alpha_per_angstrom: 0.31,
        real_space_cutoff_angstrom: 8.9,
        reciprocal_max_indices: [5, 5, 5],
        dielectric: 1.0,
        minimum_pair_distance_angstrom: 1.0e-8,
    };
    if atom_count == 4 {
        parameters.exclusions = &exclusions;
        parameters.pair_scales = &pair_scales;
    }
    DirectEwaldModel::new(parameters).expect("direct parent model must be accepted")
}

fn reciprocal_model(atom_count: usize) -> ParticleMeshReciprocalModel {
    let mut parameters = ParticleMeshReciprocalParameters::new(atom_count, [18.0, 20.0, 22.0]);
    parameters.settings = ParticleMeshReciprocalSettings {
        alpha_per_angstrom: 0.31,
        mesh_dimensions: [16, 16, 16],
        dielectric: 1.0,
    };
    ParticleMeshReciprocalModel::new(parameters).expect("reciprocal parent model must be accepted")
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
        _ => panic!("test helper admits only explicit CPU lanes"),
    };
    Context::new(options).expect("CPU context must be available")
}

fn evaluate(backend: Backend) -> ParticleMeshEwaldEvaluation {
    context(backend)
        .evaluate_particle_mesh_ewald(
            &system(&POSITIONS, &CHARGES),
            &direct_model(4),
            &reciprocal_model(4),
        )
        .expect("frozen particle-mesh Ewald fixture must evaluate")
}

#[test]
fn both_cpu_lanes_preserve_parent_components_and_cross_lane_force_parity() {
    let cpp = evaluate(Backend::CppCpuReference);
    let rust = evaluate(Backend::RustCpu);

    for (backend, observed) in [(Backend::CppCpuReference, &cpp), (Backend::RustCpu, &rust)] {
        for (index, value) in energy_values(observed.energy).into_iter().enumerate() {
            let expected = f64::from_bits(EXPECTED_ENERGY_BITS[index]);
            assert_close(value, expected, &format!("{backend:?} energy {index}"));
            if backend == Backend::RustCpu {
                assert_eq!(
                    value.to_bits(),
                    EXPECTED_ENERGY_BITS[index],
                    "Rust CPU energy component {index}"
                );
            }
        }
        assert_eq!(observed.forces.x_kcal_per_mol_angstrom.len(), 4);
        assert!(observed
            .forces
            .x_kcal_per_mol_angstrom
            .iter()
            .chain(&observed.forces.y_kcal_per_mol_angstrom)
            .chain(&observed.forces.z_kcal_per_mol_angstrom)
            .all(|value| value.is_finite()));
    }

    for atom in 0..4 {
        for (axis, (left, right)) in [
            (
                cpp.forces.x_kcal_per_mol_angstrom[atom],
                rust.forces.x_kcal_per_mol_angstrom[atom],
            ),
            (
                cpp.forces.y_kcal_per_mol_angstrom[atom],
                rust.forces.y_kcal_per_mol_angstrom[atom],
            ),
            (
                cpp.forces.z_kcal_per_mol_angstrom[atom],
                rust.forces.z_kcal_per_mol_angstrom[atom],
            ),
        ]
        .into_iter()
        .enumerate()
        {
            assert_close(left, right, &format!("force atom {atom} axis {axis}"));
        }
    }
}

#[test]
fn each_cpu_lane_is_bitwise_repeatable_and_energy_only_is_identical() {
    for backend in [Backend::CppCpuReference, Backend::RustCpu] {
        let context = context(backend);
        let system = system(&POSITIONS, &CHARGES);
        let direct = direct_model(4);
        let reciprocal = reciprocal_model(4);
        let first = context
            .evaluate_particle_mesh_ewald(&system, &direct, &reciprocal)
            .expect("first evaluation must succeed");
        for _ in 0..3 {
            let repeated = context
                .evaluate_particle_mesh_ewald(&system, &direct, &reciprocal)
                .expect("repeat evaluation must succeed");
            assert_evaluation_bits(&first, &repeated);
        }
        let energy_only = context
            .evaluate_particle_mesh_ewald_energy(&system, &direct, &reciprocal)
            .expect("energy-only evaluation must succeed");
        assert_eq!(
            energy_values(first.energy).map(f64::to_bits),
            energy_values(energy_only).map(f64::to_bits),
            "{backend:?}"
        );
    }
}

#[test]
fn failures_are_transactional_and_valid_evaluation_recovers() {
    let context = context(Backend::RustCpu);
    let direct = direct_model(4);
    let reciprocal = reciprocal_model(4);
    let non_neutral = system(&POSITIONS, &[0.7, -0.4, -0.6, 0.4]);
    for _ in 0..2 {
        let error = context
            .evaluate_particle_mesh_ewald(&non_neutral, &direct, &reciprocal)
            .expect_err("non-neutral input must fail");
        assert_eq!(error.status, ErrorCode::NumericalError);
        assert_eq!(error.code, Some(DirectEwaldErrorCode::NonNeutralSystem));
    }

    let mismatch = context
        .evaluate_particle_mesh_ewald_energy(
            &system(&POSITIONS, &CHARGES),
            &direct_model(3),
            &reciprocal,
        )
        .expect_err("mismatched parent length must fail locally");
    assert_eq!(mismatch.status, ErrorCode::InvalidArgument);
    assert_eq!(mismatch.code, None);

    let recovered = context
        .evaluate_particle_mesh_ewald(&system(&POSITIONS, &CHARGES), &direct, &reciprocal)
        .expect("prior failures must not poison any borrowed handle");
    assert_eq!(
        recovered.energy.total_kcal_per_mol.to_bits(),
        0xc018_6145_396d_ef20
    );
}

#[test]
fn auto_request_fails_closed_and_profile_identity_is_stable() {
    let context =
        Context::new(ContextOptions::auto(0)).expect("AUTO context creation is available");
    let error = context
        .evaluate_particle_mesh_ewald(
            &system(&POSITIONS, &CHARGES),
            &direct_model(4),
            &reciprocal_model(4),
        )
        .expect_err("AUTO must not inherit its resolved CPU lane");
    assert_eq!(error.status, ErrorCode::UnsupportedBackend);
    assert_eq!(error.code, None);
    assert!(error.detail.contains("cannot fall back"));
    assert_eq!(
        runtime::particle_mesh_ewald_profile_id().unwrap(),
        "betelgeuze.native_particle_mesh_ewald/1.0.0"
    );
}

fn energy_values(energy: ParticleMeshEwaldEnergyComponents) -> [f64; 5] {
    [
        energy.real_space_kcal_per_mol,
        energy.reciprocal_space_kcal_per_mol,
        energy.self_kcal_per_mol,
        energy.pair_correction_kcal_per_mol,
        energy.total_kcal_per_mol,
    ]
}

fn assert_close(observed: f64, expected: f64, label: &str) {
    let tolerance = 5.0e-12 * expected.abs().max(1.0);
    assert!(
        (observed - expected).abs() <= tolerance,
        "{label}: observed {observed:.17e}, expected {expected:.17e}, tolerance {tolerance:.3e}"
    );
}

fn assert_evaluation_bits(left: &ParticleMeshEwaldEvaluation, right: &ParticleMeshEwaldEvaluation) {
    assert_eq!(
        energy_values(left.energy).map(f64::to_bits),
        energy_values(right.energy).map(f64::to_bits)
    );
    for (left, right) in [
        (
            &left.forces.x_kcal_per_mol_angstrom,
            &right.forces.x_kcal_per_mol_angstrom,
        ),
        (
            &left.forces.y_kcal_per_mol_angstrom,
            &right.forces.y_kcal_per_mol_angstrom,
        ),
        (
            &left.forces.z_kcal_per_mol_angstrom,
            &right.forces.z_kcal_per_mol_angstrom,
        ),
    ] {
        assert_eq!(left.len(), right.len());
        for (left, right) in left.iter().zip(right) {
            assert_eq!(left.to_bits(), right.to_bits());
        }
    }
}
