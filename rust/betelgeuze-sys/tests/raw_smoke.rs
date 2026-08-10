use core::ffi::c_char;
use core::ptr;
use std::ffi::CStr;

use betelgeuze_sys::*;

unsafe fn owned_string(pointer: *const c_char) -> String {
    assert!(!pointer.is_null());
    // SAFETY: The native ABI promises that diagnostic pointers address
    // NUL-terminated strings with at least thread-local lifetime.
    unsafe { CStr::from_ptr(pointer) }
        .to_str()
        .expect("native diagnostics are UTF-8")
        .to_owned()
}

#[test]
fn native_abi_identity_and_canonical_units_match_the_header() {
    // SAFETY: These functions take no pointers and return static diagnostics.
    unsafe {
        assert_eq!(bg_abi_version(), BG_ABI_VERSION);
        assert_eq!(bg_abi_version_major(), BG_ABI_VERSION_MAJOR);
        assert_eq!(bg_abi_version_minor(), BG_ABI_VERSION_MINOR);
        assert!(!owned_string(bg_abi_version_string()).is_empty());
        assert!(!owned_string(bg_status_string(BG_STATUS_OK)).is_empty());
        assert!(!owned_string(bg_backend_string(BG_BACKEND_CPU)).is_empty());
        assert!(!owned_string(bg_unit_system_string(BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL)).is_empty());
    }
    assert_eq!(BG_CANONICAL_LENGTH_UNIT, b"angstrom\0");
    assert_eq!(BG_CANONICAL_ENERGY_UNIT, b"kcal/mol\0");
    assert_eq!(
        BG_COULOMB_CONSTANT_KCAL_ANGSTROM_PER_MOL_E2,
        332.063_713_299
    );
}

#[test]
fn descriptor_initializers_bind_size_version_and_units() {
    // SAFETY: Each MaybeUninit output points to writable storage for exactly
    // the descriptor accepted by the initializer.
    unsafe {
        let mut options = core::mem::MaybeUninit::<bg_context_options>::uninit();
        assert_eq!(bg_context_options_init(options.as_mut_ptr()), BG_STATUS_OK);
        let options = options.assume_init();
        assert_eq!(
            options.struct_size as usize,
            core::mem::size_of_val(&options)
        );
        assert_eq!(options.abi_version, BG_ABI_VERSION);
        assert_eq!(options.unit_system, BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);

        let mut particles = core::mem::MaybeUninit::<bg_particle_soa>::uninit();
        assert_eq!(bg_particle_soa_init(particles.as_mut_ptr()), BG_STATUS_OK);
        let particles = particles.assume_init();
        assert_eq!(
            particles.struct_size as usize,
            core::mem::size_of_val(&particles)
        );
        assert_eq!(particles.abi_version, BG_ABI_VERSION);
        assert_eq!(particles.unit_system, BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);

        let mut view = core::mem::MaybeUninit::<bg_particle_soa_view>::uninit();
        assert_eq!(bg_particle_soa_view_init(view.as_mut_ptr()), BG_STATUS_OK);
        let view = view.assume_init();
        assert_eq!(view.struct_size as usize, core::mem::size_of_val(&view));
        assert_eq!(view.abi_version, BG_ABI_VERSION);
        assert_eq!(view.unit_system, BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);

        let mut positions = core::mem::MaybeUninit::<bg_position_soa>::uninit();
        assert_eq!(bg_position_soa_init(positions.as_mut_ptr()), BG_STATUS_OK);
        let positions = positions.assume_init();
        assert_eq!(
            positions.struct_size as usize,
            core::mem::size_of_val(&positions)
        );
        assert_eq!(positions.abi_version, BG_ABI_VERSION);
        assert_eq!(positions.unit_system, BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);
    }
}

#[test]
fn explicit_cpu_context_round_trips_without_fallback() {
    // SAFETY: All outputs point to live writable values, and the returned
    // context is destroyed exactly once after the queries complete.
    unsafe {
        let mut available = 0_u8;
        assert_eq!(
            bg_backend_is_available(BG_BACKEND_CPU, 0, &mut available),
            BG_STATUS_OK
        );
        assert_eq!(available, 1);

        let mut options = core::mem::MaybeUninit::<bg_context_options>::uninit();
        assert_eq!(bg_context_options_init(options.as_mut_ptr()), BG_STATUS_OK);
        let mut options = options.assume_init();
        options.backend = BG_BACKEND_CPU;
        options.device_ordinal = 0;

        let mut context = ptr::null_mut();
        assert_eq!(bg_context_create(&options, &mut context), BG_STATUS_OK);
        assert!(!context.is_null());

        let mut backend = BG_BACKEND_AUTO;
        let mut device_ordinal = -1;
        let mut units = 0;
        assert_eq!(bg_context_get_backend(context, &mut backend), BG_STATUS_OK);
        assert_eq!(
            bg_context_get_device_ordinal(context, &mut device_ordinal),
            BG_STATUS_OK
        );
        assert_eq!(
            bg_context_get_unit_system(context, &mut units),
            BG_STATUS_OK
        );
        assert_eq!(backend, BG_BACKEND_CPU);
        assert_eq!(device_ordinal, 0);
        assert_eq!(units, BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);

        bg_context_destroy(context);
        bg_context_destroy(ptr::null_mut());
    }
}

#[test]
fn explicit_hip_request_is_unavailable_and_never_falls_back_to_cpu() {
    // SAFETY: All outputs point to live writable values. A failed create must
    // leave the output null, so there is no handle to destroy.
    unsafe {
        let mut available = 1_u8;
        assert_eq!(
            bg_backend_is_available(BG_BACKEND_HIP, 0, &mut available),
            BG_STATUS_OK
        );
        assert_eq!(available, 0);

        let mut options = core::mem::MaybeUninit::<bg_context_options>::uninit();
        assert_eq!(bg_context_options_init(options.as_mut_ptr()), BG_STATUS_OK);
        let mut options = options.assume_init();
        options.backend = BG_BACKEND_HIP;

        let mut context = ptr::dangling_mut::<bg_context>();
        assert_eq!(
            bg_context_create(&options, &mut context),
            BG_STATUS_BACKEND_UNAVAILABLE
        );
        assert!(context.is_null());
    }
}

#[test]
fn system_deep_copies_soa_and_replaces_positions_transactionally() {
    let mut x = [1.0, 2.0];
    let y = [3.0, 4.0];
    let z = [5.0, 6.0];
    let mass = [12.0, 1.0];
    let charge = [-0.25, 0.25];

    // SAFETY: Descriptor channels point to arrays of particle_count elements.
    // The returned borrowed view is only read while the system remains alive.
    unsafe {
        let mut particles = core::mem::MaybeUninit::<bg_particle_soa>::uninit();
        assert_eq!(bg_particle_soa_init(particles.as_mut_ptr()), BG_STATUS_OK);
        let mut particles = particles.assume_init();
        particles.particle_count = 2;
        particles.position_x_angstrom = x.as_ptr();
        particles.position_y_angstrom = y.as_ptr();
        particles.position_z_angstrom = z.as_ptr();
        particles.mass_dalton = mass.as_ptr();
        particles.charge_elementary = charge.as_ptr();

        let mut system = ptr::null_mut();
        assert_eq!(bg_system_create(&particles, &mut system), BG_STATUS_OK);
        assert!(!system.is_null());

        x[0] = 99.0;
        assert_eq!(x[0], 99.0);
        let mut view = core::mem::MaybeUninit::<bg_particle_soa_view>::uninit();
        assert_eq!(bg_particle_soa_view_init(view.as_mut_ptr()), BG_STATUS_OK);
        let mut view = view.assume_init();
        assert_eq!(bg_system_get_particles(system, &mut view), BG_STATUS_OK);
        assert_eq!(view.particle_count, 2);
        assert_eq!(
            std::slice::from_raw_parts(view.position_x_angstrom, 2),
            &[1.0, 2.0]
        );
        assert_eq!(
            std::slice::from_raw_parts(view.velocity_x_angstrom_per_femtosecond, 2),
            &[0.0, 0.0]
        );

        let replacement_x = [7.0, 8.0];
        let replacement_y = [9.0, 10.0];
        let replacement_z = [11.0, 12.0];
        let mut positions = core::mem::MaybeUninit::<bg_position_soa>::uninit();
        assert_eq!(bg_position_soa_init(positions.as_mut_ptr()), BG_STATUS_OK);
        let mut positions = positions.assume_init();
        positions.particle_count = 2;
        positions.x_angstrom = replacement_x.as_ptr();
        positions.y_angstrom = replacement_y.as_ptr();
        positions.z_angstrom = replacement_z.as_ptr();
        assert_eq!(bg_system_set_positions(system, &positions), BG_STATUS_OK);

        assert_eq!(bg_particle_soa_view_init(&mut view), BG_STATUS_OK);
        assert_eq!(bg_system_get_particles(system, &mut view), BG_STATUS_OK);
        assert_eq!(
            std::slice::from_raw_parts(view.position_x_angstrom, 2),
            &[7.0, 8.0]
        );
        assert_eq!(
            std::slice::from_raw_parts(view.position_y_angstrom, 2),
            &[9.0, 10.0]
        );
        assert_eq!(
            std::slice::from_raw_parts(view.position_z_angstrom, 2),
            &[11.0, 12.0]
        );

        let mut count = 0;
        let mut units = 0;
        assert_eq!(
            bg_system_get_particle_count(system, &mut count),
            BG_STATUS_OK
        );
        assert_eq!(bg_system_get_unit_system(system, &mut units), BG_STATUS_OK);
        assert_eq!(count, 2);
        assert_eq!(units, BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);

        bg_system_destroy(system);
        bg_system_destroy(ptr::null_mut());
    }
}

#[test]
fn invalid_call_sets_copyable_thread_local_error() {
    // SAFETY: The out pointer is valid, and null options deliberately exercise
    // the documented invalid-argument path. Diagnostic buffers are sized from
    // the native size query before the copy call.
    unsafe {
        let mut context = ptr::dangling_mut::<bg_context>();
        assert_eq!(
            bg_context_create(ptr::null(), &mut context),
            BG_STATUS_INVALID_ARGUMENT
        );
        assert!(context.is_null());
        assert!(!owned_string(bg_last_error_message()).is_empty());

        let mut required_size = 0_u64;
        assert_eq!(
            bg_last_error_message_copy(ptr::null_mut(), 0, &mut required_size),
            BG_STATUS_OK
        );
        assert!(required_size > 1);
        let mut buffer = vec![0 as c_char; required_size as usize];
        assert_eq!(
            bg_last_error_message_copy(
                buffer.as_mut_ptr(),
                buffer.len() as u64,
                &mut required_size,
            ),
            BG_STATUS_OK
        );
        assert!(!owned_string(buffer.as_ptr()).is_empty());
    }
}
