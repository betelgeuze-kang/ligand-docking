use betelgeuze_runtime as runtime;

const TOLERANCE: f64 = 2.0e-11;
const BAOAB_SEED: u64 = 0x42d0_3301_a5a5_0101;

#[test]
fn frozen_single_water_matches_across_cpu_backends() {
    let cpp = runtime::Context::new(runtime::ContextOptions::cpu_reference()).unwrap();
    let rust = runtime::Context::new(runtime::ContextOptions::rust_cpu()).unwrap();
    let cpp_evaluation = runtime::evaluate_development_single_water_v1(&cpp).unwrap();
    let rust_evaluation = runtime::evaluate_development_single_water_v1(&rust).unwrap();

    assert!(cpp_evaluation.energy.total_kcal_per_mol.abs() < 1.0e-24);
    assert_evaluation_close(&cpp_evaluation, &rust_evaluation, TOLERANCE);
}

#[test]
fn frozen_initial_water_box_matches_across_cpu_backends() {
    assert_eq!(runtime::DEVELOPMENT_WATER_BOX_V1_ATOM_COUNT, 6);
    assert_eq!(
        runtime::DEVELOPMENT_WATER_BOX_V1_SCHEMA_ID,
        "betelgeuze.engine_v2_native_water_box/1.0.0"
    );
    assert_eq!(
        runtime::DEVELOPMENT_WATER_BOX_V1_PROFILE_ID,
        "engine_v2_native_two_water_development_v1"
    );
    assert_eq!(
        runtime::development_water_box_v1_profile_sha256(),
        [
            0x2b, 0x0b, 0xe8, 0x3b, 0x57, 0x08, 0x5c, 0x65, 0x50, 0x92, 0xab, 0x02, 0x72, 0xae,
            0xa5, 0xa9, 0x1b, 0x9c, 0x3f, 0x90, 0xc3, 0x44, 0xfa, 0x06, 0x2d, 0x49, 0x4a, 0xd3,
            0x24, 0xf0, 0x01, 0x9e,
        ]
    );

    let cpp = runtime::Context::new(runtime::ContextOptions::cpu_reference()).unwrap();
    let rust = runtime::Context::new(runtime::ContextOptions::rust_cpu()).unwrap();
    let cpp_evaluation = runtime::evaluate_development_water_box_v1(&cpp).unwrap();
    let rust_evaluation = runtime::evaluate_development_water_box_v1(&rust).unwrap();

    assert_close(
        cpp_evaluation.energy.total_kcal_per_mol,
        -2.235452238349433,
        TOLERANCE,
    );
    assert_evaluation_close(&cpp_evaluation, &rust_evaluation, TOLERANCE);
}

#[test]
fn frozen_nve_is_cpu_parity_complete_and_checkpoint_exact() {
    let cpp = runtime::Context::new(runtime::ContextOptions::cpu_reference()).unwrap();
    let rust = runtime::Context::new(runtime::ContextOptions::rust_cpu()).unwrap();
    let mut cpp_box = runtime::DevelopmentWaterBoxV1::nve().unwrap();
    let mut rust_box = runtime::DevelopmentWaterBoxV1::nve().unwrap();

    let cpp_report = cpp_box.integrate(&cpp, 100).unwrap();
    let rust_report = rust_box.integrate(&rust, 100).unwrap();
    assert_eq!(cpp_report.steps_completed, 100);
    assert_eq!(cpp_report.absolute_step, 100);
    assert_eq!(cpp_report.degrees_of_freedom, 18);
    assert_close(cpp_report.total_kcal_per_mol, -2.235428271468032, TOLERANCE);
    assert_report_close(cpp_report, rust_report, TOLERANCE);
    assert_snapshot_close(
        &cpp_box.snapshot().unwrap(),
        &rust_box.snapshot().unwrap(),
        TOLERANCE,
    );

    let checkpoint = rust_box.checkpoint().unwrap();
    assert_eq!(checkpoint, rust_box.checkpoint().unwrap());
    let mut restarted = runtime::DevelopmentWaterBoxV1::nve().unwrap();
    restarted.load_checkpoint(&checkpoint).unwrap();
    assert_snapshot_bits_equal(
        &rust_box.snapshot().unwrap(),
        &restarted.snapshot().unwrap(),
    );
    let continued = rust_box.integrate(&rust, 32).unwrap();
    let restarted_report = restarted.integrate(&rust, 32).unwrap();
    assert_eq!(continued, restarted_report);
    assert_snapshot_bits_equal(
        &rust_box.snapshot().unwrap(),
        &restarted.snapshot().unwrap(),
    );
}

#[test]
fn frozen_baoab_is_seed_repeatable_and_cpu_parity_complete() {
    let cpp = runtime::Context::new(runtime::ContextOptions::cpu_reference()).unwrap();
    let rust = runtime::Context::new(runtime::ContextOptions::rust_cpu()).unwrap();
    let mut cpp_box = runtime::DevelopmentWaterBoxV1::baoab(BAOAB_SEED).unwrap();
    let mut rust_box = runtime::DevelopmentWaterBoxV1::baoab(BAOAB_SEED).unwrap();
    let mut repeated = runtime::DevelopmentWaterBoxV1::baoab(BAOAB_SEED).unwrap();

    let cpp_report = cpp_box.integrate(&cpp, 128).unwrap();
    let rust_report = rust_box.integrate(&rust, 128).unwrap();
    let repeated_report = repeated.integrate(&rust, 128).unwrap();
    assert_eq!(rust_report, repeated_report);
    assert!(rust_report.temperature_kelvin.is_finite());
    assert!(rust_report.temperature_kelvin >= 0.0);
    assert_report_close(cpp_report, rust_report, TOLERANCE);
    assert_snapshot_close(
        &cpp_box.snapshot().unwrap(),
        &rust_box.snapshot().unwrap(),
        TOLERANCE,
    );
    assert_snapshot_bits_equal(&rust_box.snapshot().unwrap(), &repeated.snapshot().unwrap());
}

fn assert_evaluation_close(
    left: &runtime::Evaluation,
    right: &runtime::Evaluation,
    tolerance: f64,
) {
    for (left, right) in [
        (
            left.energy.harmonic_bond_kcal_per_mol,
            right.energy.harmonic_bond_kcal_per_mol,
        ),
        (
            left.energy.harmonic_angle_kcal_per_mol,
            right.energy.harmonic_angle_kcal_per_mol,
        ),
        (
            left.energy.lennard_jones_kcal_per_mol,
            right.energy.lennard_jones_kcal_per_mol,
        ),
        (
            left.energy.coulomb_kcal_per_mol,
            right.energy.coulomb_kcal_per_mol,
        ),
        (
            left.energy.total_kcal_per_mol,
            right.energy.total_kcal_per_mol,
        ),
    ] {
        assert_close(left, right, tolerance);
    }
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
        for (&left, &right) in left.iter().zip(right) {
            assert_close(left, right, tolerance);
        }
    }
}

fn assert_report_close(
    left: runtime::DynamicsReport,
    right: runtime::DynamicsReport,
    tolerance: f64,
) {
    assert_eq!(left.steps_completed, right.steps_completed);
    assert_eq!(left.absolute_step, right.absolute_step);
    assert_eq!(left.degrees_of_freedom, right.degrees_of_freedom);
    for (left, right) in [
        (left.potential_kcal_per_mol, right.potential_kcal_per_mol),
        (left.kinetic_kcal_per_mol, right.kinetic_kcal_per_mol),
        (left.total_kcal_per_mol, right.total_kcal_per_mol),
        (left.temperature_kelvin, right.temperature_kelvin),
    ] {
        assert_close(left, right, tolerance);
    }
}

fn assert_snapshot_close(
    left: &runtime::ParticleSnapshot,
    right: &runtime::ParticleSnapshot,
    tolerance: f64,
) {
    assert_eq!(left.mass_dalton, right.mass_dalton);
    assert_eq!(left.charge_elementary, right.charge_elementary);
    for (left, right) in snapshot_channels(left, right) {
        assert_eq!(left.len(), right.len());
        for (&left, &right) in left.iter().zip(right) {
            assert_close(left, right, tolerance);
        }
    }
}

fn assert_snapshot_bits_equal(left: &runtime::ParticleSnapshot, right: &runtime::ParticleSnapshot) {
    assert_eq!(left.mass_dalton, right.mass_dalton);
    assert_eq!(left.charge_elementary, right.charge_elementary);
    for (left, right) in snapshot_channels(left, right) {
        assert_eq!(left.len(), right.len());
        for (&left, &right) in left.iter().zip(right) {
            assert_eq!(left.to_bits(), right.to_bits());
        }
    }
}

fn snapshot_channels<'a>(
    left: &'a runtime::ParticleSnapshot,
    right: &'a runtime::ParticleSnapshot,
) -> [(&'a [f64], &'a [f64]); 6] {
    [
        (&left.positions.x_angstrom, &right.positions.x_angstrom),
        (&left.positions.y_angstrom, &right.positions.y_angstrom),
        (&left.positions.z_angstrom, &right.positions.z_angstrom),
        (
            &left.velocities.x_angstrom_per_femtosecond,
            &right.velocities.x_angstrom_per_femtosecond,
        ),
        (
            &left.velocities.y_angstrom_per_femtosecond,
            &right.velocities.y_angstrom_per_femtosecond,
        ),
        (
            &left.velocities.z_angstrom_per_femtosecond,
            &right.velocities.z_angstrom_per_femtosecond,
        ),
    ]
}

fn assert_close(actual: f64, expected: f64, tolerance: f64) {
    let error = (actual - expected).abs();
    assert!(
        error <= tolerance * (1.0 + expected.abs()),
        "actual={actual:.17e}, expected={expected:.17e}, error={error:.3e}, tolerance={tolerance:.3e}"
    );
}
