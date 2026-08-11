use betelgeuze_runtime::{
    Backend, Context, ContextOptions, ErrorCode, HostTensorView, HostTensorViewMut, ParticleSoa,
    PositionSoa, Stream, System, UnitSystem, VelocitySoa, CANONICAL_UNITS,
};

#[test]
fn canonical_units_are_explicit_and_exact() {
    assert_eq!(CANONICAL_UNITS.length, "angstrom");
    assert_eq!(CANONICAL_UNITS.energy, "kcal/mol");
    assert_eq!(CANONICAL_UNITS.force, "kcal/(mol*angstrom)");
    assert_eq!(CANONICAL_UNITS.time, "femtosecond");
    assert_eq!(
        CANONICAL_UNITS.coulomb_constant_kcal_angstrom_per_mol_e2,
        332.063_713_299
    );
}

#[test]
fn host_tensor_and_stream_adapters_preserve_exact_layout() {
    let values = [1.0_f64, 2.0, 3.0, 4.0, 5.0, 6.0];
    let tensor = HostTensorView::new(&values, &[2, 3]).unwrap();
    assert_eq!(tensor.as_slice(), values);
    assert_eq!(tensor.metadata().shape, vec![2, 3]);
    assert_eq!(tensor.metadata().stride_bytes, vec![24, 8]);
    assert_eq!(tensor.metadata().element_count, 6);
    assert_eq!(tensor.metadata().required_bytes, 48);

    let mut output = [0_i32; 6];
    let mut tensor = HostTensorViewMut::new(&mut output, &[2, 3]).unwrap();
    tensor.as_mut_slice()[5] = 7;
    assert_eq!(tensor.as_slice()[5], 7);
    assert_eq!(tensor.metadata().stride_bytes, vec![12, 4]);

    let stream = Stream::rust_cpu().unwrap();
    assert_eq!(stream.backend().unwrap(), Backend::RustCpu);
    assert_eq!(stream.device_ordinal(), 0);
    let stream = Stream::hip_default(Backend::HipSafe, 2).unwrap();
    assert_eq!(stream.backend().unwrap(), Backend::HipSafe);
    assert_eq!(stream.device_ordinal(), 2);
    // SAFETY: This test validates descriptor ownership semantics only; it does
    // not submit work or dereference the synthetic handle.
    let stream = unsafe { Stream::hip_borrowed(Backend::HipFast, 0, 0x1234) }.unwrap();
    assert_eq!(stream.backend().unwrap(), Backend::HipFast);
}

#[test]
fn tensor_adapters_reject_shape_and_capacity_errors() {
    let values = [1_u8, 2, 3];
    let error = HostTensorView::new(&values, &[2, 2]).err().unwrap();
    assert_eq!(error.code, ErrorCode::InvalidArgument);
    let error = HostTensorView::new(&values, &[1, 1, 1, 1, 3])
        .err()
        .unwrap();
    assert_eq!(error.code, ErrorCode::InvalidArgument);
    let error = Stream::hip_default(Backend::RustCpu, 0).err().unwrap();
    assert_eq!(error.code, ErrorCode::InvalidArgument);
}

#[test]
fn explicit_cpu_context_reports_the_selected_backend() {
    assert!(Context::backend_available(Backend::RustCpu, 0).unwrap());
    let context = Context::new(ContextOptions::cpu()).unwrap();
    assert_eq!(context.backend().unwrap(), Backend::RustCpu);
    assert_eq!(context.device_ordinal().unwrap(), 0);
    assert_eq!(context.unit_system().unwrap(), UnitSystem::AngstromKcalMol);
}

#[test]
fn unavailable_hip_backends_are_not_silently_replaced_with_cpu() {
    assert!(!Context::backend_available(Backend::HipSafe, 0).unwrap());
    assert!(!Context::backend_available(Backend::HipFast, 0).unwrap());
    let error = Context::new(ContextOptions::hip_safe(0)).err().unwrap();
    assert_eq!(error.code, ErrorCode::BackendUnavailable);
    assert!(error.message.contains("fallback is forbidden"));
}

#[test]
fn system_owns_float64_soa_and_updates_transactionally() {
    let mut x = vec![1.0, 2.0, 3.0];
    let y = vec![4.0, 5.0, 6.0];
    let z = vec![7.0, 8.0, 9.0];
    let vx = vec![0.1, 0.2, 0.3];
    let vy = vec![0.4, 0.5, 0.6];
    let vz = vec![0.7, 0.8, 0.9];
    let mass = vec![1.008, 12.011, 15.999];
    let charge = vec![0.25, -0.5, 0.25];

    let particles = ParticleSoa::new(PositionSoa::new(&x, &y, &z), &mass, &charge)
        .with_velocities(VelocitySoa::new(&vx, &vy, &vz));
    let mut system = System::new(particles).unwrap();
    x[0] = 99.0;

    assert_eq!(system.len().unwrap(), 3);
    assert_eq!(system.unit_system().unwrap(), UnitSystem::AngstromKcalMol);
    let snapshot = system.snapshot().unwrap();
    assert_eq!(snapshot.positions.x_angstrom, vec![1.0, 2.0, 3.0]);
    assert_eq!(snapshot.positions.y_angstrom, y);
    assert_eq!(snapshot.velocities.z_angstrom_per_femtosecond, vz);
    assert_eq!(snapshot.mass_dalton, mass);
    assert_eq!(snapshot.charge_elementary, charge);

    let new_x = [-1.0, -2.0, -3.0];
    let new_y = [-4.0, -5.0, -6.0];
    let new_z = [-7.0, -8.0, -9.0];
    system
        .set_positions(PositionSoa::new(&new_x, &new_y, &new_z))
        .unwrap();
    let snapshot = system.snapshot().unwrap();
    assert_eq!(snapshot.positions.x_angstrom, new_x);
    assert_eq!(snapshot.positions.y_angstrom, new_y);
    assert_eq!(snapshot.positions.z_angstrom, new_z);

    let invalid_x = [0.0, f64::NAN, 2.0];
    let error = system
        .set_positions(PositionSoa::new(&invalid_x, &new_y, &new_z))
        .unwrap_err();
    assert_eq!(error.code, ErrorCode::InvalidArgument);
    assert_eq!(system.snapshot().unwrap().positions.x_angstrom, new_x);
}

#[test]
fn absent_velocities_are_zero_filled_and_empty_systems_are_valid() {
    let positions = PositionSoa::new(&[], &[], &[]);
    let system = System::new(ParticleSoa::new(positions, &[], &[])).unwrap();
    assert!(system.is_empty().unwrap());
    assert!(system.snapshot().unwrap().is_empty());

    let x = [0.0];
    let y = [1.0];
    let z = [2.0];
    let mass = [12.0];
    let charge = [0.0];
    let system = System::new(ParticleSoa::new(
        PositionSoa::new(&x, &y, &z),
        &mass,
        &charge,
    ))
    .unwrap();
    assert_eq!(
        system
            .snapshot()
            .unwrap()
            .velocities
            .x_angstrom_per_femtosecond,
        vec![0.0]
    );
}

#[test]
fn safe_layer_rejects_invalid_lengths_values_masses_and_devices() {
    let x = [0.0, 1.0];
    let y = [0.0];
    let z = [0.0, 1.0];
    let mass = [1.0, 1.0];
    let charge = [0.0, 0.0];
    let error = System::new(ParticleSoa::new(
        PositionSoa::new(&x, &y, &z),
        &mass,
        &charge,
    ))
    .err()
    .unwrap();
    assert_eq!(error.code, ErrorCode::InvalidArgument);

    let y = [0.0, 1.0];
    let bad_mass = [1.0, 0.0];
    let error = System::new(ParticleSoa::new(
        PositionSoa::new(&x, &y, &z),
        &bad_mass,
        &charge,
    ))
    .err()
    .unwrap();
    assert_eq!(error.code, ErrorCode::InvalidArgument);

    let error = Context::new(ContextOptions::hip_safe(-1)).err().unwrap();
    assert_eq!(error.code, ErrorCode::InvalidArgument);
    assert_eq!(ErrorCode::from_raw(12345), Some(ErrorCode::Unknown(12345)));
    assert_eq!(ErrorCode::Unknown(12345).as_raw(), 12345);
}

#[test]
fn repeated_raii_lifecycle_is_stable() {
    for _ in 0..256 {
        let context = Context::new(ContextOptions::default()).unwrap();
        assert_eq!(context.backend().unwrap(), Backend::RustCpu);
        let system =
            System::new(ParticleSoa::new(PositionSoa::new(&[], &[], &[]), &[], &[])).unwrap();
        assert!(system.is_empty().unwrap());
    }
}
