use std::collections::BTreeMap;

use betelgeuze_runtime as runtime;
use runtime::{
    Backend, Context, ContextOptions, ErrorCode, ParticleMeshReciprocalErrorCode,
    ParticleMeshReciprocalEvaluation, ParticleMeshReciprocalModel,
    ParticleMeshReciprocalParameters, ParticleMeshReciprocalSettings, ParticleSoa, PositionSoa,
    System,
};

const FROZEN: &str = include_str!("fixtures/particle_mesh_reciprocal_v1.tsv");
const PACKAGED_FROZEN: &[u8] = include_bytes!("fixtures/particle_mesh_reciprocal_v1.tsv");

const POSITIONS: [[f64; 3]; 4] = [
    [1.25, 2.5, 3.75],
    [5.1, 3.2, 8.4],
    [10.2, 12.3, 7.7],
    [15.4, 17.1, 19.3],
];
const CHARGES: [f64; 4] = [0.7, -0.4, -0.6, 0.300_000_000_000_000_04];

fn fixture_model() -> ParticleMeshReciprocalModel {
    let mut parameters = ParticleMeshReciprocalParameters::new(4, [18.0, 20.0, 22.0]);
    parameters.settings = ParticleMeshReciprocalSettings {
        alpha_per_angstrom: 0.31,
        mesh_dimensions: [16, 16, 16],
        dielectric: 1.0,
    };
    ParticleMeshReciprocalModel::new(parameters).expect("frozen model must be accepted")
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

fn evaluate(backend: Backend) -> ParticleMeshReciprocalEvaluation {
    context(backend)
        .evaluate_particle_mesh_reciprocal(&system(&POSITIONS, &CHARGES), &fixture_model())
        .expect("frozen reciprocal-only fixture must evaluate")
}

#[test]
fn packaged_fixture_is_byte_identical_to_the_reference_fixture() {
    let reference_path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../reference-pme/fixtures/pme_reciprocal_v1.tsv");
    if reference_path.is_file() {
        assert_eq!(
            PACKAGED_FROZEN,
            std::fs::read(reference_path)
                .expect("reference fixture must be readable")
                .as_slice()
        );
    }
    assert!(FROZEN
        .lines()
        .any(|line| line == "# schema_id=betelgeuze.reference_particle_mesh_reciprocal/1.0.0"));
    assert_eq!(frozen_values().len(), 13);
}

#[test]
fn rust_cpu_lane_preserves_all_thirteen_frozen_bits() {
    let expected = frozen_values();
    let observed = evaluate(Backend::RustCpu);
    let repeated = evaluate(Backend::RustCpu);
    assert_evaluation_bits(&observed, &repeated);
    assert_eq!(
        observed.energy.reciprocal_space_kcal_per_mol.to_bits(),
        expected["reciprocal_space_kcal_per_mol"]
    );
    for atom in 0..4 {
        for (axis, value) in [
            observed.forces.x_kcal_per_mol_angstrom[atom],
            observed.forces.y_kcal_per_mol_angstrom[atom],
            observed.forces.z_kcal_per_mol_angstrom[atom],
        ]
        .into_iter()
        .enumerate()
        {
            let key = format!("force_{atom}_{}", ["x", "y", "z"][axis]);
            assert_eq!(value.to_bits(), expected[key.as_str()], "{key}");
        }
    }
}

#[test]
fn cpp_cpu_lane_is_repeatable_and_matches_the_frozen_reference() {
    let expected = frozen_values();
    let first = evaluate(Backend::CppCpuReference);
    let second = evaluate(Backend::CppCpuReference);
    assert_evaluation_bits(&first, &second);
    assert_close(
        first.energy.reciprocal_space_kcal_per_mol,
        f64::from_bits(expected["reciprocal_space_kcal_per_mol"]),
        "energy",
    );
    for atom in 0..4 {
        for (axis, value) in [
            first.forces.x_kcal_per_mol_angstrom[atom],
            first.forces.y_kcal_per_mol_angstrom[atom],
            first.forces.z_kcal_per_mol_angstrom[atom],
        ]
        .into_iter()
        .enumerate()
        {
            let key = format!("force_{atom}_{}", ["x", "y", "z"][axis]);
            assert_close(value, f64::from_bits(expected[key.as_str()]), &key);
        }
    }
}

#[test]
fn energy_only_path_equals_force_path_for_both_cpu_lanes() {
    for backend in [Backend::CppCpuReference, Backend::RustCpu] {
        let context = context(backend);
        let system = system(&POSITIONS, &CHARGES);
        let model = fixture_model();
        let with_forces = context
            .evaluate_particle_mesh_reciprocal(&system, &model)
            .unwrap();
        let energy_only = context
            .evaluate_particle_mesh_reciprocal_energy(&system, &model)
            .unwrap();
        assert_eq!(
            with_forces.energy.reciprocal_space_kcal_per_mol.to_bits(),
            energy_only.reciprocal_space_kcal_per_mol.to_bits(),
            "{backend:?}"
        );
    }
}

#[test]
fn typed_creation_and_evaluation_errors_preserve_statuses() {
    let empty = ParticleMeshReciprocalModel::new(ParticleMeshReciprocalParameters::new(
        0,
        [18.0, 20.0, 22.0],
    ))
    .err()
    .expect("empty model must fail");
    assert_eq!(empty.status, ErrorCode::InvalidArgument);
    assert_eq!(
        empty.code,
        Some(ParticleMeshReciprocalErrorCode::EmptySystem)
    );

    let capacity = ParticleMeshReciprocalModel::new(ParticleMeshReciprocalParameters::new(
        4_097,
        [18.0, 20.0, 22.0],
    ))
    .err()
    .expect("oversized model must fail");
    assert_eq!(capacity.status, ErrorCode::CapacityOverflow);
    assert_eq!(
        capacity.code,
        Some(ParticleMeshReciprocalErrorCode::CapacityExceeded)
    );

    let mut invalid_mesh = ParticleMeshReciprocalParameters::new(4, [18.0, 20.0, 22.0]);
    invalid_mesh.settings.mesh_dimensions = [15, 16, 16];
    let invalid_mesh = ParticleMeshReciprocalModel::new(invalid_mesh)
        .err()
        .expect("invalid mesh must fail");
    assert_eq!(invalid_mesh.status, ErrorCode::InvalidArgument);
    assert_eq!(
        invalid_mesh.code,
        Some(ParticleMeshReciprocalErrorCode::InvalidMesh)
    );

    let context = context(Backend::RustCpu);
    let model = fixture_model();
    let non_neutral = system(&POSITIONS, &[0.7, -0.4, -0.6, 0.4]);
    let non_neutral = context
        .evaluate_particle_mesh_reciprocal(&non_neutral, &model)
        .unwrap_err();
    assert_eq!(non_neutral.status, ErrorCode::NumericalError);
    assert_eq!(
        non_neutral.code,
        Some(ParticleMeshReciprocalErrorCode::NonNeutralSystem)
    );

    let count_mismatch = system(&POSITIONS[..3], &[0.7, -0.4, -0.3]);
    let count_mismatch = context
        .evaluate_particle_mesh_reciprocal(&count_mismatch, &model)
        .unwrap_err();
    assert_eq!(count_mismatch.status, ErrorCode::InvalidArgument);
    assert_eq!(
        count_mismatch.code,
        Some(ParticleMeshReciprocalErrorCode::ChargeCountMismatch)
    );

    let recovered = context
        .evaluate_particle_mesh_reciprocal(&system(&POSITIONS, &CHARGES), &model)
        .expect("transactional failures must not poison model or context");
    assert_eq!(
        recovered.energy.reciprocal_space_kcal_per_mol.to_bits(),
        frozen_values()["reciprocal_space_kcal_per_mol"]
    );
}

#[test]
fn auto_request_fails_closed_even_if_native_context_resolves_it_to_cpu() {
    let context =
        Context::new(ContextOptions::auto(0)).expect("AUTO context creation is available");
    let error = context
        .evaluate_particle_mesh_reciprocal_energy(&system(&POSITIONS, &CHARGES), &fixture_model())
        .unwrap_err();
    assert_eq!(error.status, ErrorCode::UnsupportedBackend);
    assert_eq!(error.code, None);
    assert!(error.detail.contains("cannot fall back"));
}

#[test]
fn model_is_deep_owned_and_profile_identity_is_stable() {
    let mut parameters = ParticleMeshReciprocalParameters::new(4, [18.0, 20.0, 22.0]);
    parameters.settings = ParticleMeshReciprocalSettings {
        alpha_per_angstrom: 0.31,
        mesh_dimensions: [16, 16, 16],
        dielectric: 1.0,
    };
    let model = ParticleMeshReciprocalModel::new(parameters).unwrap();
    parameters.cell_lengths_angstrom = [9.0, 10.0, 11.0];
    parameters.settings.alpha_per_angstrom = 0.7;
    assert_eq!(parameters.cell_lengths_angstrom, [9.0, 10.0, 11.0]);
    assert_eq!(parameters.settings.alpha_per_angstrom, 0.7);
    let evaluation = context(Backend::RustCpu)
        .evaluate_particle_mesh_reciprocal(&system(&POSITIONS, &CHARGES), &model)
        .expect("model must retain its copied configuration");
    assert_eq!(
        evaluation.energy.reciprocal_space_kcal_per_mol.to_bits(),
        frozen_values()["reciprocal_space_kcal_per_mol"]
    );
    assert_eq!(model.len().unwrap(), 4);
    assert!(!model.is_empty().unwrap());
    for _ in 0..32 {
        drop(fixture_model());
    }
    assert_eq!(
        runtime::particle_mesh_reciprocal_profile_id().unwrap(),
        "betelgeuze.native_particle_mesh_reciprocal/1.0.0"
    );
}

fn frozen_values() -> BTreeMap<&'static str, u64> {
    FROZEN
        .lines()
        .filter(|line| !line.is_empty() && !line.starts_with('#') && !line.starts_with("value_id"))
        .map(|line| {
            let (name, bits) = line.split_once('\t').expect("row must be tab-separated");
            let bits = u64::from_str_radix(bits, 16).expect("bits must be hexadecimal");
            (name, bits)
        })
        .collect()
}

fn assert_close(observed: f64, expected: f64, label: &str) {
    let tolerance = 3.0e-12 * expected.abs().max(1.0);
    assert!(
        (observed - expected).abs() <= tolerance,
        "{label}: observed {observed:.17e}, expected {expected:.17e}, tolerance {tolerance:.3e}"
    );
}

fn assert_evaluation_bits(
    left: &ParticleMeshReciprocalEvaluation,
    right: &ParticleMeshReciprocalEvaluation,
) {
    assert_eq!(
        left.energy.reciprocal_space_kcal_per_mol.to_bits(),
        right.energy.reciprocal_space_kcal_per_mol.to_bits()
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
