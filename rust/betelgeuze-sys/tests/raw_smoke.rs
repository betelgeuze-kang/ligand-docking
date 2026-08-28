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

unsafe fn initialize<T>(
    initializer: unsafe extern "C" fn(*mut T, usize, u32) -> bg_status,
    descriptor: *mut T,
) -> bg_status {
    // SAFETY: The caller supplies writable storage for T. Passing size_of::<T>
    // and this binding's ABI version is the exact initializer contract.
    unsafe { initializer(descriptor, core::mem::size_of::<T>(), BG_ABI_VERSION) }
}

unsafe fn assert_initializer_exact<T>(
    initializer: unsafe extern "C" fn(*mut T, usize, u32) -> bg_status,
) {
    // SAFETY: This wrapper preserves the frozen Engine ABI version used by
    // the existing descriptor-initializer coverage below.
    unsafe { assert_versioned_initializer_exact(initializer, BG_ABI_VERSION) };
}

unsafe fn assert_versioned_initializer_exact<T>(
    initializer: unsafe extern "C" fn(*mut T, usize, u32) -> bg_status,
    abi_version: u32,
) {
    let size = core::mem::size_of::<T>();
    assert!(size > 0);
    let mut storage = core::mem::MaybeUninit::<T>::uninit();
    // SAFETY: MaybeUninit storage may hold arbitrary bytes. Mismatch calls are
    // required not to read or write them.
    unsafe { storage.as_mut_ptr().cast::<u8>().write_bytes(0xA5, size) };
    // SAFETY: Reading the object representation as bytes is always valid.
    let snapshot = unsafe { core::slice::from_raw_parts(storage.as_ptr().cast::<u8>(), size) };
    let snapshot = snapshot.to_vec();

    for (caller_size, caller_version) in [
        (size - 1, abi_version),
        (size + 1, abi_version),
        (size, abi_version + 1),
    ] {
        // SAFETY: The pointer addresses size bytes, and the initializer must
        // reject this incompatible identity before dereferencing it.
        assert_eq!(
            unsafe { initializer(storage.as_mut_ptr(), caller_size, caller_version) },
            BG_STATUS_ABI_MISMATCH
        );
        // SAFETY: The rejected initializer leaves the representation untouched.
        assert_eq!(
            unsafe { core::slice::from_raw_parts(storage.as_ptr().cast::<u8>(), size) },
            snapshot
        );
    }

    // SAFETY: Exact size/version authorizes initialization of the whole T.
    assert_eq!(
        unsafe { initializer(storage.as_mut_ptr(), size, abi_version) },
        BG_STATUS_OK
    );
}

#[test]
fn descriptor_initializers_reject_incompatible_callers_without_writing() {
    // SAFETY: The helper provides allocated storage of the exact descriptor
    // type and only asks mismatch calls to honor their no-access contract.
    unsafe {
        assert_initializer_exact(bg_context_options_init);
        assert_initializer_exact(bg_particle_soa_init);
        assert_initializer_exact(bg_particle_soa_view_init);
        assert_initializer_exact(bg_position_soa_init);
        assert_initializer_exact(bg_forcefield_soa_v1_init);
        assert_initializer_exact(bg_force_soa_v1_init);
        assert_initializer_exact(bg_energy_components_v1_init);
        assert_initializer_exact(bg_distance_constraints_v1_init);
        assert_initializer_exact(bg_simulation_options_v1_init);
        assert_initializer_exact(bg_minimizer_options_v1_init);
        assert_initializer_exact(bg_minimization_report_v1_init);
        assert_initializer_exact(bg_dynamics_report_v1_init);
        assert_initializer_exact(bg_docking_fixed64_allocation_input_v1_init);
        assert_initializer_exact(bg_docking_fixed64_allocation_output_v1_init);
        assert_initializer_exact(bg_docking_fixed64_so3_input_v1_init);
        assert_initializer_exact(bg_docking_fixed64_so3_output_v1_init);
        assert_initializer_exact(bg_docking_fixed64_indexed_so3_input_v1_init);
        assert_initializer_exact(bg_docking_fixed64_indexed_so3_output_v1_init);
        assert_initializer_exact(bg_docking_fixed64_single_anchor_input_v1_init);
        assert_initializer_exact(bg_docking_fixed64_single_anchor_output_v1_init);
        assert_initializer_exact(bg_docking_fixed64_producer_input_v1_init);
        assert_initializer_exact(bg_docking_fixed64_producer_output_v1_init);
        assert_initializer_exact(bg_docking_fixed64_pipeline_input_v1_init);
        assert_initializer_exact(bg_docking_fixed64_pipeline_output_v1_init);
        assert_initializer_exact(bg_docking_fixed64_pipeline_input_v2_init);
        assert_initializer_exact(bg_docking_fixed64_pipeline_output_v2_init);
        assert_initializer_exact(bg_docking_geometric_admission_context_soa_v1_init);
        assert_initializer_exact(bg_docking_geometric_admission_candidate_batch_soa_v1_init);
        assert_initializer_exact(bg_docking_geometric_admission_output_v1_init);
        assert_initializer_exact(bg_docking_scorer_v1_context_soa_v1_init);
        assert_initializer_exact(bg_docking_scorer_v1_candidate_batch_soa_v1_init);
        assert_initializer_exact(bg_docking_scorer_v1_output_v1_init);
        assert_initializer_exact(bg_docking_pose_validity_context_soa_v1_init);
        assert_initializer_exact(bg_docking_pose_validity_candidate_batch_soa_v1_init);
        assert_initializer_exact(bg_docking_pose_validity_output_v1_init);
        assert_initializer_exact(bg_docking_stable_top_k_input_v1_init);
        assert_initializer_exact(bg_docking_stable_top_k_output_v1_init);
        assert_initializer_exact(bg_docking_rmsd_cluster_input_v1_init);
        assert_initializer_exact(bg_docking_rmsd_cluster_output_v1_init);
        assert_initializer_exact(bg_docking_rigid_refinement_context_soa_v1_init);
        assert_initializer_exact(bg_docking_rigid_refinement_candidate_batch_soa_v1_init);
        assert_initializer_exact(bg_docking_rigid_refinement_output_v1_init);
        assert_initializer_exact(bg_docking_torsion_v7_context_soa_v1_init);
        assert_initializer_exact(bg_docking_torsion_v7_candidate_batch_soa_v1_init);
        assert_initializer_exact(bg_docking_torsion_v7_output_v1_init);
        assert_initializer_exact(bg_docking_fixed64_refinement_input_v1_init);
        assert_initializer_exact(bg_docking_fixed64_refinement_output_v1_init);
        assert_versioned_initializer_exact(
            bg_particle_mesh_reciprocal_parameters_v1_init,
            BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION,
        );
        assert_versioned_initializer_exact(
            bg_particle_mesh_reciprocal_energy_v1_init,
            BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION,
        );
        assert_versioned_initializer_exact(
            bg_particle_mesh_reciprocal_force_soa_v1_init,
            BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION,
        );
        assert_versioned_initializer_exact(
            bg_particle_mesh_reciprocal_error_v1_init,
            BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION,
        );
        assert_versioned_initializer_exact(
            bg_particle_mesh_ewald_energy_components_v1_init,
            BG_PARTICLE_MESH_EWALD_ABI_VERSION,
        );
        assert_versioned_initializer_exact(
            bg_particle_mesh_ewald_force_soa_v1_init,
            BG_PARTICLE_MESH_EWALD_ABI_VERSION,
        );
        assert_versioned_initializer_exact(
            bg_particle_mesh_ewald_composite_energy_components_v1_init,
            BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION,
        );
        assert_versioned_initializer_exact(
            bg_particle_mesh_ewald_composite_force_soa_v1_init,
            BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION,
        );
    }
}

#[test]
fn native_abi_identity_and_canonical_units_match_the_header() {
    // SAFETY: These functions take no pointers and return static diagnostics.
    unsafe {
        assert_eq!(bg_abi_version(), BG_ABI_VERSION);
        assert_eq!(bg_abi_version_major(), BG_ABI_VERSION_MAJOR);
        assert_eq!(bg_abi_version_minor(), BG_ABI_VERSION_MINOR);
        assert_eq!(owned_string(bg_abi_version_string()), "1.21");
        assert_eq!(
            owned_string(bg_docking_fixed64_producer_v1_profile_id()),
            "betelgeuze.engine_v2_mixed64_native_fixed64_producer/1.1.2"
        );
        assert_eq!(
            owned_string(bg_docking_fixed64_pipeline_v1_profile_id()),
            "betelgeuze.engine_v2_native_fixed64_complete_pipeline/1.0.0"
        );
        assert_eq!(
            owned_string(bg_docking_fixed64_pipeline_v2_profile_id()),
            "betelgeuze.engine_v2_native_fixed64_complete_pipeline/2.0.0"
        );
        assert!(!owned_string(bg_status_string(BG_STATUS_OK)).is_empty());
        assert!(!owned_string(bg_backend_string(BG_BACKEND_CPU)).is_empty());
        assert!(!owned_string(bg_unit_system_string(BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL)).is_empty());
    }
    assert_eq!(BG_CANONICAL_LENGTH_UNIT, b"angstrom\0");
    assert_eq!(BG_CANONICAL_ENERGY_UNIT, b"kcal/mol\0");
    assert_eq!(BG_CANONICAL_FORCE_UNIT, b"kcal/(mol*angstrom)\0");
    assert_eq!(BG_CANONICAL_CHARGE_UNIT, b"elementary_charge\0");
    assert_eq!(BG_CANONICAL_MASS_UNIT, b"dalton\0");
    assert_eq!(BG_CANONICAL_ANGLE_UNIT, b"radian\0");
    assert_eq!(BG_CANONICAL_TIME_UNIT, b"femtosecond\0");
    assert_eq!(BG_CANONICAL_VELOCITY_UNIT, b"angstrom/femtosecond\0");
    assert_eq!(BG_CANONICAL_TEMPERATURE_UNIT, b"kelvin\0");
    assert_eq!(
        BG_COULOMB_CONSTANT_KCAL_ANGSTROM_PER_MOL_E2,
        332.063_713_299
    );
}

#[test]
fn direct_ewald_abi_identity_and_initializers_match_the_header() {
    // SAFETY: Identity functions return static strings, while each initializer
    // receives exact writable storage, size, and direct-Ewald ABI version.
    unsafe {
        assert_eq!(bg_direct_ewald_abi_version(), BG_DIRECT_EWALD_ABI_VERSION);
        assert_eq!(
            bg_direct_ewald_abi_version_major(),
            BG_DIRECT_EWALD_ABI_VERSION_MAJOR
        );
        assert_eq!(
            bg_direct_ewald_abi_version_minor(),
            BG_DIRECT_EWALD_ABI_VERSION_MINOR
        );
        assert_eq!(owned_string(bg_direct_ewald_abi_version_string()), "1.0.0");
        assert_eq!(
            owned_string(bg_direct_ewald_model_v1_profile_id()),
            "betelgeuze.native_direct_ewald/1.0.0"
        );

        let mut parameters = core::mem::MaybeUninit::<bg_direct_ewald_parameters_v1>::uninit();
        assert_eq!(
            bg_direct_ewald_parameters_v1_init(
                parameters.as_mut_ptr(),
                core::mem::size_of::<bg_direct_ewald_parameters_v1>(),
                BG_DIRECT_EWALD_ABI_VERSION,
            ),
            BG_STATUS_OK
        );
        let parameters = parameters.assume_init();
        assert_eq!(
            parameters.struct_size as usize,
            core::mem::size_of::<bg_direct_ewald_parameters_v1>()
        );
        assert_eq!(parameters.abi_version, BG_DIRECT_EWALD_ABI_VERSION);
        assert_eq!(parameters.unit_system, BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);

        let mut energy = core::mem::MaybeUninit::<bg_direct_ewald_energy_components_v1>::uninit();
        assert_eq!(
            bg_direct_ewald_energy_components_v1_init(
                energy.as_mut_ptr(),
                core::mem::size_of::<bg_direct_ewald_energy_components_v1>(),
                BG_DIRECT_EWALD_ABI_VERSION,
            ),
            BG_STATUS_OK
        );
        let energy = energy.assume_init();
        assert_eq!(energy.abi_version, BG_DIRECT_EWALD_ABI_VERSION);
        assert_eq!(energy.unit_system, BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);

        let mut forces = core::mem::MaybeUninit::<bg_direct_ewald_force_soa_v1>::uninit();
        assert_eq!(
            bg_direct_ewald_force_soa_v1_init(
                forces.as_mut_ptr(),
                core::mem::size_of::<bg_direct_ewald_force_soa_v1>(),
                BG_DIRECT_EWALD_ABI_VERSION,
            ),
            BG_STATUS_OK
        );
        let forces = forces.assume_init();
        assert_eq!(forces.abi_version, BG_DIRECT_EWALD_ABI_VERSION);
        assert_eq!(forces.unit_system, BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);

        let mut error = core::mem::MaybeUninit::<bg_direct_ewald_error_v1>::uninit();
        assert_eq!(
            bg_direct_ewald_error_v1_init(
                error.as_mut_ptr(),
                core::mem::size_of::<bg_direct_ewald_error_v1>(),
                BG_DIRECT_EWALD_ABI_VERSION,
            ),
            BG_STATUS_OK
        );
        let error = error.assume_init();
        assert_eq!(error.abi_version, BG_DIRECT_EWALD_ABI_VERSION);
        assert_eq!(error.code, BG_DIRECT_EWALD_ERROR_NONE);
        assert!(error.detail.iter().all(|byte| *byte == 0));
    }
}

#[test]
fn particle_mesh_reciprocal_identity_and_initializers_match_the_header() {
    // SAFETY: Identity functions take no pointers and exact writable storage
    // is passed to each descriptor initializer.
    unsafe {
        assert_eq!(
            bg_particle_mesh_reciprocal_abi_version(),
            BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION
        );
        assert_eq!(bg_particle_mesh_reciprocal_abi_version_major(), 1);
        assert_eq!(bg_particle_mesh_reciprocal_abi_version_minor(), 0);
        assert_eq!(
            owned_string(bg_particle_mesh_reciprocal_abi_version_string()),
            "1.0.0"
        );
        assert_eq!(
            owned_string(bg_particle_mesh_reciprocal_model_v1_profile_id()),
            "betelgeuze.native_particle_mesh_reciprocal/1.0.0"
        );

        let mut parameters =
            core::mem::MaybeUninit::<bg_particle_mesh_reciprocal_parameters_v1>::uninit();
        assert_eq!(
            bg_particle_mesh_reciprocal_parameters_v1_init(
                parameters.as_mut_ptr(),
                core::mem::size_of::<bg_particle_mesh_reciprocal_parameters_v1>(),
                BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION,
            ),
            BG_STATUS_OK
        );
        let mut parameters = parameters.assume_init();
        assert_eq!(
            parameters.abi_version,
            BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION
        );
        assert_eq!(parameters.unit_system, BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);

        let mut energy = core::mem::MaybeUninit::<bg_particle_mesh_reciprocal_energy_v1>::uninit();
        assert_eq!(
            bg_particle_mesh_reciprocal_energy_v1_init(
                energy.as_mut_ptr(),
                core::mem::size_of::<bg_particle_mesh_reciprocal_energy_v1>(),
                BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION,
            ),
            BG_STATUS_OK
        );
        assert_eq!(
            energy.assume_init().unit_system,
            BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL
        );

        let mut forces =
            core::mem::MaybeUninit::<bg_particle_mesh_reciprocal_force_soa_v1>::uninit();
        assert_eq!(
            bg_particle_mesh_reciprocal_force_soa_v1_init(
                forces.as_mut_ptr(),
                core::mem::size_of::<bg_particle_mesh_reciprocal_force_soa_v1>(),
                BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION,
            ),
            BG_STATUS_OK
        );
        assert_eq!(
            forces.assume_init().unit_system,
            BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL
        );

        let mut error = core::mem::MaybeUninit::<bg_particle_mesh_reciprocal_error_v1>::uninit();
        assert_eq!(
            bg_particle_mesh_reciprocal_error_v1_init(
                error.as_mut_ptr(),
                core::mem::size_of::<bg_particle_mesh_reciprocal_error_v1>(),
                BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION,
            ),
            BG_STATUS_OK
        );
        let error = error.assume_init();
        assert_eq!(error.code, BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONE);
        assert!(error.detail.iter().all(|byte| *byte == 0));

        let mut error = error;
        let mut model =
            core::ptr::NonNull::<bg_particle_mesh_reciprocal_model_v1>::dangling().as_ptr();
        assert_eq!(
            bg_particle_mesh_reciprocal_model_v1_create(&parameters, &mut model, &mut error,),
            BG_STATUS_INVALID_ARGUMENT
        );
        assert!(model.is_null());
        assert_eq!(error.code, BG_PARTICLE_MESH_RECIPROCAL_ERROR_EMPTY_SYSTEM);

        assert_eq!(
            bg_particle_mesh_reciprocal_error_v1_init(
                &mut error,
                core::mem::size_of::<bg_particle_mesh_reciprocal_error_v1>(),
                BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION,
            ),
            BG_STATUS_OK
        );
        parameters.atom_count = 1;
        parameters.cell_lengths_angstrom = [18.0, 20.0, 22.0];
        assert_eq!(
            bg_particle_mesh_reciprocal_model_v1_create(&parameters, &mut model, &mut error,),
            BG_STATUS_OK
        );
        assert!(!model.is_null());
        assert_eq!(error.code, BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONE);
        let mut atom_count = 0;
        assert_eq!(
            bg_particle_mesh_reciprocal_model_v1_get_atom_count(model, &mut atom_count),
            BG_STATUS_OK
        );
        assert_eq!(atom_count, 1);
        bg_particle_mesh_reciprocal_model_v1_destroy(model);
    }
}

#[test]
fn particle_mesh_ewald_identity_initializers_and_null_failure_are_transactional() {
    // SAFETY: Identity functions take no pointers. Initializers receive exact
    // writable storage. The evaluation deliberately supplies null borrowed
    // handles while retaining valid output and direct-error descriptors.
    unsafe {
        assert_eq!(
            bg_particle_mesh_ewald_abi_version(),
            BG_PARTICLE_MESH_EWALD_ABI_VERSION
        );
        assert_eq!(
            bg_particle_mesh_ewald_abi_version_major(),
            BG_PARTICLE_MESH_EWALD_ABI_VERSION_MAJOR
        );
        assert_eq!(
            bg_particle_mesh_ewald_abi_version_minor(),
            BG_PARTICLE_MESH_EWALD_ABI_VERSION_MINOR
        );
        assert_eq!(
            owned_string(bg_particle_mesh_ewald_abi_version_string()),
            "1.0.0"
        );
        assert_eq!(
            owned_string(bg_particle_mesh_ewald_v1_profile_id()),
            "betelgeuze.native_particle_mesh_ewald/1.0.0"
        );

        let mut energy =
            core::mem::MaybeUninit::<bg_particle_mesh_ewald_energy_components_v1>::uninit();
        assert_eq!(
            bg_particle_mesh_ewald_energy_components_v1_init(
                energy.as_mut_ptr(),
                core::mem::size_of::<bg_particle_mesh_ewald_energy_components_v1>(),
                BG_PARTICLE_MESH_EWALD_ABI_VERSION,
            ),
            BG_STATUS_OK
        );
        let mut energy = energy.assume_init();
        assert_eq!(
            energy.struct_size as usize,
            core::mem::size_of::<bg_particle_mesh_ewald_energy_components_v1>()
        );
        assert_eq!(energy.abi_version, BG_PARTICLE_MESH_EWALD_ABI_VERSION);
        assert_eq!(energy.unit_system, BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);
        assert_eq!(energy.reserved0, 0);
        assert_eq!(energy.reserved, [0; 4]);

        let mut forces = core::mem::MaybeUninit::<bg_particle_mesh_ewald_force_soa_v1>::uninit();
        assert_eq!(
            bg_particle_mesh_ewald_force_soa_v1_init(
                forces.as_mut_ptr(),
                core::mem::size_of::<bg_particle_mesh_ewald_force_soa_v1>(),
                BG_PARTICLE_MESH_EWALD_ABI_VERSION,
            ),
            BG_STATUS_OK
        );
        let mut forces = forces.assume_init();
        assert_eq!(forces.abi_version, BG_PARTICLE_MESH_EWALD_ABI_VERSION);
        assert_eq!(forces.unit_system, BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);
        assert_eq!(forces.atom_capacity, 0);
        assert_eq!(forces.atom_count, 0);
        assert!(forces.x_kcal_per_mol_angstrom.is_null());
        assert!(forces.y_kcal_per_mol_angstrom.is_null());
        assert!(forces.z_kcal_per_mol_angstrom.is_null());
        assert_eq!(forces.reserved, [0; 4]);

        energy.real_space_kcal_per_mol = 1.0;
        energy.reciprocal_space_kcal_per_mol = 2.0;
        energy.self_kcal_per_mol = 3.0;
        energy.pair_correction_kcal_per_mol = 4.0;
        energy.total_kcal_per_mol = 5.0;
        let mut force_x = [11.0, 12.0];
        let mut force_y = [21.0, 22.0];
        let mut force_z = [31.0, 32.0];
        forces.atom_capacity = 2;
        forces.atom_count = 17;
        forces.x_kcal_per_mol_angstrom = force_x.as_mut_ptr();
        forces.y_kcal_per_mol_angstrom = force_y.as_mut_ptr();
        forces.z_kcal_per_mol_angstrom = force_z.as_mut_ptr();

        let mut error = core::mem::MaybeUninit::<bg_direct_ewald_error_v1>::uninit();
        assert_eq!(
            bg_direct_ewald_error_v1_init(
                error.as_mut_ptr(),
                core::mem::size_of::<bg_direct_ewald_error_v1>(),
                BG_DIRECT_EWALD_ABI_VERSION,
            ),
            BG_STATUS_OK
        );
        let mut error = error.assume_init();
        error.code = BG_DIRECT_EWALD_ERROR_NONFINITE_RESULT;
        error.detail[0] = b'x' as c_char;

        let mut options = core::mem::MaybeUninit::<bg_context_options>::uninit();
        assert_eq!(
            initialize(bg_context_options_init, options.as_mut_ptr()),
            BG_STATUS_OK
        );
        let mut options = options.assume_init();
        options.backend = BG_BACKEND_RUST_CPU;
        let mut context = ptr::null_mut();
        assert_eq!(bg_context_create(&options, &mut context), BG_STATUS_OK);
        assert!(!context.is_null());

        assert_eq!(
            bg_context_evaluate_particle_mesh_ewald_v1(
                context,
                ptr::null(),
                ptr::null(),
                ptr::null(),
                &mut energy,
                &mut forces,
                &mut error,
            ),
            BG_STATUS_INVALID_ARGUMENT
        );
        assert_eq!(
            [
                energy.real_space_kcal_per_mol,
                energy.reciprocal_space_kcal_per_mol,
                energy.self_kcal_per_mol,
                energy.pair_correction_kcal_per_mol,
                energy.total_kcal_per_mol,
            ],
            [1.0, 2.0, 3.0, 4.0, 5.0]
        );
        assert_eq!(forces.atom_capacity, 2);
        assert_eq!(forces.atom_count, 17);
        assert_eq!(force_x, [11.0, 12.0]);
        assert_eq!(force_y, [21.0, 22.0]);
        assert_eq!(force_z, [31.0, 32.0]);
        assert_eq!(error.code, BG_DIRECT_EWALD_ERROR_NONE);
        assert!(error.detail.iter().all(|byte| *byte == 0));
        bg_context_destroy(context);
    }
}

#[test]
fn particle_mesh_ewald_composite_identity_and_null_failure_are_transactional() {
    // SAFETY: Identity functions take no pointers. Initializers receive exact
    // writable storage. The evaluation deliberately supplies null borrowed
    // handles while retaining valid, disjoint output descriptors.
    unsafe {
        assert_eq!(
            bg_particle_mesh_ewald_composite_abi_version(),
            BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION
        );
        assert_eq!(
            bg_particle_mesh_ewald_composite_abi_version_major(),
            BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION_MAJOR
        );
        assert_eq!(
            bg_particle_mesh_ewald_composite_abi_version_minor(),
            BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION_MINOR
        );
        assert_eq!(
            owned_string(bg_particle_mesh_ewald_composite_abi_version_string()),
            "1.0.0"
        );
        assert_eq!(
            owned_string(bg_particle_mesh_ewald_composite_v1_profile_id()),
            "betelgeuze.native_particle_mesh_ewald_composite/1.0.0"
        );
        assert_eq!(
            bg_particle_mesh_ewald_composite_energy_components_v1_init(
                ptr::null_mut(),
                core::mem::size_of::<bg_particle_mesh_ewald_composite_energy_components_v1>(),
                BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION,
            ),
            BG_STATUS_INVALID_ARGUMENT
        );

        let mut energy = core::mem::MaybeUninit::<
            bg_particle_mesh_ewald_composite_energy_components_v1,
        >::uninit();
        assert_eq!(
            bg_particle_mesh_ewald_composite_energy_components_v1_init(
                energy.as_mut_ptr(),
                core::mem::size_of::<bg_particle_mesh_ewald_composite_energy_components_v1>(),
                BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION,
            ),
            BG_STATUS_OK
        );
        let mut energy = energy.assume_init();
        assert_eq!(
            energy.struct_size as usize,
            core::mem::size_of::<bg_particle_mesh_ewald_composite_energy_components_v1>()
        );
        assert_eq!(
            energy.abi_version,
            BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION
        );
        assert_eq!(energy.unit_system, BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);
        assert_eq!(
            energy.short_coulomb_kcal_per_mol.to_bits(),
            0.0_f64.to_bits()
        );
        assert_eq!(energy.reserved, [0; 4]);

        let mut forces =
            core::mem::MaybeUninit::<bg_particle_mesh_ewald_composite_force_soa_v1>::uninit();
        assert_eq!(
            bg_particle_mesh_ewald_composite_force_soa_v1_init(
                forces.as_mut_ptr(),
                core::mem::size_of::<bg_particle_mesh_ewald_composite_force_soa_v1>(),
                BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION,
            ),
            BG_STATUS_OK
        );
        let mut forces = forces.assume_init();
        assert_eq!(
            forces.abi_version,
            BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION
        );
        assert_eq!(forces.unit_system, BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);
        assert_eq!(forces.atom_capacity, 0);
        assert_eq!(forces.atom_count, 0);
        assert!(forces.x_kcal_per_mol_angstrom.is_null());
        assert!(forces.y_kcal_per_mol_angstrom.is_null());
        assert!(forces.z_kcal_per_mol_angstrom.is_null());
        assert_eq!(forces.reserved, [0; 4]);

        energy.short_harmonic_bond_kcal_per_mol = 1.0;
        energy.short_harmonic_angle_kcal_per_mol = 2.0;
        energy.short_periodic_torsion_kcal_per_mol = 3.0;
        energy.short_lennard_jones_kcal_per_mol = 4.0;
        energy.short_coulomb_kcal_per_mol = 5.0;
        energy.short_total_kcal_per_mol = 6.0;
        energy.pme_real_space_kcal_per_mol = 7.0;
        energy.pme_reciprocal_space_kcal_per_mol = 8.0;
        energy.pme_self_kcal_per_mol = 9.0;
        energy.pme_pair_correction_kcal_per_mol = 10.0;
        energy.pme_total_kcal_per_mol = 11.0;
        energy.total_kcal_per_mol = 12.0;

        let mut force_x = [11.0, 12.0];
        let mut force_y = [21.0, 22.0];
        let mut force_z = [31.0, 32.0];
        forces.atom_capacity = 2;
        forces.atom_count = 17;
        forces.x_kcal_per_mol_angstrom = force_x.as_mut_ptr();
        forces.y_kcal_per_mol_angstrom = force_y.as_mut_ptr();
        forces.z_kcal_per_mol_angstrom = force_z.as_mut_ptr();

        let mut error = core::mem::MaybeUninit::<bg_direct_ewald_error_v1>::uninit();
        assert_eq!(
            bg_direct_ewald_error_v1_init(
                error.as_mut_ptr(),
                core::mem::size_of::<bg_direct_ewald_error_v1>(),
                BG_DIRECT_EWALD_ABI_VERSION,
            ),
            BG_STATUS_OK
        );
        let mut error = error.assume_init();
        error.code = BG_DIRECT_EWALD_ERROR_NONFINITE_RESULT;
        error.detail[0] = b'x' as c_char;

        let mut options = core::mem::MaybeUninit::<bg_context_options>::uninit();
        assert_eq!(
            initialize(bg_context_options_init, options.as_mut_ptr()),
            BG_STATUS_OK
        );
        let mut options = options.assume_init();
        options.backend = BG_BACKEND_RUST_CPU;
        let mut context = ptr::null_mut();
        assert_eq!(bg_context_create(&options, &mut context), BG_STATUS_OK);
        assert!(!context.is_null());

        assert_eq!(
            bg_context_evaluate_particle_mesh_ewald_composite_v1(
                context,
                ptr::null(),
                ptr::null(),
                ptr::null(),
                ptr::null(),
                &mut energy,
                &mut forces,
                &mut error,
            ),
            BG_STATUS_INVALID_ARGUMENT
        );
        assert_eq!(
            [
                energy.short_harmonic_bond_kcal_per_mol,
                energy.short_harmonic_angle_kcal_per_mol,
                energy.short_periodic_torsion_kcal_per_mol,
                energy.short_lennard_jones_kcal_per_mol,
                energy.short_coulomb_kcal_per_mol,
                energy.short_total_kcal_per_mol,
                energy.pme_real_space_kcal_per_mol,
                energy.pme_reciprocal_space_kcal_per_mol,
                energy.pme_self_kcal_per_mol,
                energy.pme_pair_correction_kcal_per_mol,
                energy.pme_total_kcal_per_mol,
                energy.total_kcal_per_mol,
            ],
            [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0]
        );
        assert_eq!(forces.atom_capacity, 2);
        assert_eq!(forces.atom_count, 17);
        assert_eq!(force_x, [11.0, 12.0]);
        assert_eq!(force_y, [21.0, 22.0]);
        assert_eq!(force_z, [31.0, 32.0]);
        assert_eq!(error.code, BG_DIRECT_EWALD_ERROR_NONE);
        assert!(error.detail.iter().all(|byte| *byte == 0));
        bg_context_destroy(context);
    }
}

#[test]
fn direct_ewald_composite_identity_initializers_and_null_failure_are_transactional() {
    // SAFETY: Identity functions take no pointers. Initializers receive exact
    // writable storage. The evaluation deliberately supplies null borrowed
    // handles while retaining valid, disjoint output descriptors.
    unsafe {
        assert_eq!(
            bg_direct_ewald_composite_abi_version(),
            BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION
        );
        assert_eq!(
            bg_direct_ewald_composite_abi_version_major(),
            BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION_MAJOR
        );
        assert_eq!(
            bg_direct_ewald_composite_abi_version_minor(),
            BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION_MINOR
        );
        assert_eq!(
            owned_string(bg_direct_ewald_composite_abi_version_string()),
            "1.0.0"
        );
        assert_eq!(
            owned_string(bg_direct_ewald_composite_v1_profile_id()),
            "betelgeuze.native_direct_ewald_composite/1.0.0"
        );

        assert_versioned_initializer_exact(
            bg_direct_ewald_composite_energy_components_v1_init,
            BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION,
        );
        assert_versioned_initializer_exact(
            bg_direct_ewald_composite_force_soa_v1_init,
            BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION,
        );
        assert_eq!(
            bg_direct_ewald_composite_energy_components_v1_init(
                ptr::null_mut(),
                core::mem::size_of::<bg_direct_ewald_composite_energy_components_v1>(),
                BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION,
            ),
            BG_STATUS_INVALID_ARGUMENT
        );

        let mut energy =
            core::mem::MaybeUninit::<bg_direct_ewald_composite_energy_components_v1>::uninit();
        assert_eq!(
            bg_direct_ewald_composite_energy_components_v1_init(
                energy.as_mut_ptr(),
                core::mem::size_of::<bg_direct_ewald_composite_energy_components_v1>(),
                BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION,
            ),
            BG_STATUS_OK
        );
        let mut energy = energy.assume_init();
        assert_eq!(
            energy.struct_size as usize,
            core::mem::size_of::<bg_direct_ewald_composite_energy_components_v1>()
        );
        assert_eq!(energy.abi_version, BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION);
        assert_eq!(energy.unit_system, BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);
        assert_eq!(
            energy.short_coulomb_kcal_per_mol.to_bits(),
            0.0_f64.to_bits()
        );
        assert!(energy.reserved.iter().all(|value| *value == 0));

        let mut forces = core::mem::MaybeUninit::<bg_direct_ewald_composite_force_soa_v1>::uninit();
        assert_eq!(
            bg_direct_ewald_composite_force_soa_v1_init(
                forces.as_mut_ptr(),
                core::mem::size_of::<bg_direct_ewald_composite_force_soa_v1>(),
                BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION,
            ),
            BG_STATUS_OK
        );
        let mut forces = forces.assume_init();
        assert_eq!(
            forces.struct_size as usize,
            core::mem::size_of::<bg_direct_ewald_composite_force_soa_v1>()
        );
        assert_eq!(forces.abi_version, BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION);
        assert_eq!(forces.unit_system, BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);
        assert_eq!(forces.atom_capacity, 0);
        assert_eq!(forces.atom_count, 0);
        assert!(forces.x_kcal_per_mol_angstrom.is_null());
        assert!(forces.y_kcal_per_mol_angstrom.is_null());
        assert!(forces.z_kcal_per_mol_angstrom.is_null());
        assert!(forces.reserved.iter().all(|value| *value == 0));

        let mut force_x = [11.0, 12.0, 13.0, 14.0];
        let mut force_y = [21.0, 22.0, 23.0, 24.0];
        let mut force_z = [31.0, 32.0, 33.0, 34.0];
        forces.atom_capacity = 4;
        forces.atom_count = 77;
        forces.x_kcal_per_mol_angstrom = force_x.as_mut_ptr();
        forces.y_kcal_per_mol_angstrom = force_y.as_mut_ptr();
        forces.z_kcal_per_mol_angstrom = force_z.as_mut_ptr();

        energy.short_harmonic_bond_kcal_per_mol = 1.0;
        energy.short_harmonic_angle_kcal_per_mol = 2.0;
        energy.short_periodic_torsion_kcal_per_mol = 3.0;
        energy.short_lennard_jones_kcal_per_mol = 4.0;
        energy.short_coulomb_kcal_per_mol = 5.0;
        energy.short_total_kcal_per_mol = 6.0;
        energy.ewald_real_space_kcal_per_mol = 7.0;
        energy.ewald_reciprocal_space_kcal_per_mol = 8.0;
        energy.ewald_self_kcal_per_mol = 9.0;
        energy.ewald_pair_correction_kcal_per_mol = 10.0;
        energy.ewald_total_kcal_per_mol = 11.0;
        energy.total_kcal_per_mol = 12.0;

        let mut error = core::mem::MaybeUninit::<bg_direct_ewald_error_v1>::uninit();
        assert_eq!(
            bg_direct_ewald_error_v1_init(
                error.as_mut_ptr(),
                core::mem::size_of::<bg_direct_ewald_error_v1>(),
                BG_DIRECT_EWALD_ABI_VERSION,
            ),
            BG_STATUS_OK
        );
        let mut error = error.assume_init();
        error.code = BG_DIRECT_EWALD_ERROR_NONFINITE_RESULT;
        error.detail[0] = b'x' as c_char;

        assert_eq!(
            bg_context_evaluate_direct_ewald_composite_v1(
                ptr::null(),
                ptr::null(),
                ptr::null(),
                ptr::null(),
                &mut energy,
                &mut forces,
                &mut error,
            ),
            BG_STATUS_INVALID_ARGUMENT
        );
        assert_eq!(
            [
                energy.short_harmonic_bond_kcal_per_mol,
                energy.short_harmonic_angle_kcal_per_mol,
                energy.short_periodic_torsion_kcal_per_mol,
                energy.short_lennard_jones_kcal_per_mol,
                energy.short_coulomb_kcal_per_mol,
                energy.short_total_kcal_per_mol,
                energy.ewald_real_space_kcal_per_mol,
                energy.ewald_reciprocal_space_kcal_per_mol,
                energy.ewald_self_kcal_per_mol,
                energy.ewald_pair_correction_kcal_per_mol,
                energy.ewald_total_kcal_per_mol,
                energy.total_kcal_per_mol,
            ],
            [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0]
        );
        assert_eq!(error.code, BG_DIRECT_EWALD_ERROR_NONE);
        assert!(error.detail.iter().all(|byte| *byte == 0));
        assert_eq!(forces.atom_capacity, 4);
        assert_eq!(forces.atom_count, 77);
        assert_eq!(forces.x_kcal_per_mol_angstrom, force_x.as_mut_ptr());
        assert_eq!(forces.y_kcal_per_mol_angstrom, force_y.as_mut_ptr());
        assert_eq!(forces.z_kcal_per_mol_angstrom, force_z.as_mut_ptr());
        assert_eq!(force_x, [11.0, 12.0, 13.0, 14.0]);
        assert_eq!(force_y, [21.0, 22.0, 23.0, 24.0]);
        assert_eq!(force_z, [31.0, 32.0, 33.0, 34.0]);

        assert_eq!(
            bg_context_evaluate_direct_ewald_composite_v1(
                ptr::null(),
                ptr::null(),
                ptr::null(),
                ptr::null(),
                &mut energy,
                &mut forces,
                ptr::null_mut(),
            ),
            BG_STATUS_INVALID_ARGUMENT
        );
        assert_eq!(
            [
                energy.short_harmonic_bond_kcal_per_mol,
                energy.short_harmonic_angle_kcal_per_mol,
                energy.short_periodic_torsion_kcal_per_mol,
                energy.short_lennard_jones_kcal_per_mol,
                energy.short_coulomb_kcal_per_mol,
                energy.short_total_kcal_per_mol,
                energy.ewald_real_space_kcal_per_mol,
                energy.ewald_reciprocal_space_kcal_per_mol,
                energy.ewald_self_kcal_per_mol,
                energy.ewald_pair_correction_kcal_per_mol,
                energy.ewald_total_kcal_per_mol,
                energy.total_kcal_per_mol,
            ],
            [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0]
        );
        assert_eq!(forces.atom_count, 77);
        assert_eq!(force_x, [11.0, 12.0, 13.0, 14.0]);
        assert_eq!(force_y, [21.0, 22.0, 23.0, 24.0]);
        assert_eq!(force_z, [31.0, 32.0, 33.0, 34.0]);
    }
}

#[test]
fn direct_ewald_composite_dynamics_identity_and_null_failures_are_transactional() {
    // SAFETY: Identity functions take no pointers. Every descriptor points to
    // initialized writable storage, and null handles deliberately exercise
    // the documented invalid-argument paths without native dereferences.
    unsafe {
        assert_eq!(
            bg_direct_ewald_composite_dynamics_abi_version(),
            BG_DIRECT_EWALD_COMPOSITE_DYNAMICS_ABI_VERSION
        );
        assert_eq!(
            bg_direct_ewald_composite_dynamics_abi_version_major(),
            BG_DIRECT_EWALD_COMPOSITE_DYNAMICS_ABI_VERSION_MAJOR
        );
        assert_eq!(
            bg_direct_ewald_composite_dynamics_abi_version_minor(),
            BG_DIRECT_EWALD_COMPOSITE_DYNAMICS_ABI_VERSION_MINOR
        );
        assert_eq!(
            owned_string(bg_direct_ewald_composite_dynamics_abi_version_string()),
            "1.0.0"
        );
        assert_eq!(
            owned_string(bg_direct_ewald_composite_dynamics_v1_profile_id()),
            "betelgeuze.native_direct_ewald_composite_dynamics/1.0.0"
        );

        bg_direct_ewald_composite_simulation_v1_destroy(ptr::null_mut());

        let mut options = core::mem::MaybeUninit::<bg_simulation_options_v1>::uninit();
        assert_eq!(
            bg_simulation_options_v1_init(
                options.as_mut_ptr(),
                core::mem::size_of::<bg_simulation_options_v1>(),
                BG_ABI_VERSION,
            ),
            BG_STATUS_OK
        );
        let options = options.assume_init();

        let mut error = core::mem::MaybeUninit::<bg_direct_ewald_error_v1>::uninit();
        assert_eq!(
            bg_direct_ewald_error_v1_init(
                error.as_mut_ptr(),
                core::mem::size_of::<bg_direct_ewald_error_v1>(),
                BG_DIRECT_EWALD_ABI_VERSION,
            ),
            BG_STATUS_OK
        );
        let mut error = error.assume_init();
        error.code = BG_DIRECT_EWALD_ERROR_NONFINITE_RESULT;
        error.detail[0] = b'x' as c_char;

        let mut simulation = ptr::null_mut();
        assert_eq!(
            bg_direct_ewald_composite_simulation_v1_create(
                ptr::null(),
                ptr::null(),
                ptr::null(),
                ptr::null(),
                &options,
                &mut simulation,
                &mut error,
            ),
            BG_STATUS_INVALID_ARGUMENT
        );
        assert!(simulation.is_null());
        assert_eq!(error.code, BG_DIRECT_EWALD_ERROR_NONE);
        assert!(error.detail.iter().all(|byte| *byte == 0));

        let mut view = core::mem::MaybeUninit::<bg_particle_soa_view>::uninit();
        assert_eq!(
            bg_particle_soa_view_init(
                view.as_mut_ptr(),
                core::mem::size_of::<bg_particle_soa_view>(),
                BG_ABI_VERSION,
            ),
            BG_STATUS_OK
        );
        let mut view = view.assume_init();
        view.particle_count = 77;
        assert_eq!(
            bg_direct_ewald_composite_simulation_v1_get_particles(ptr::null(), &mut view),
            BG_STATUS_INVALID_ARGUMENT
        );
        assert_eq!(view.particle_count, 77);

        let mut absolute_step = 91_u64;
        assert_eq!(
            bg_direct_ewald_composite_simulation_v1_get_absolute_step(
                ptr::null(),
                &mut absolute_step,
            ),
            BG_STATUS_INVALID_ARGUMENT
        );
        assert_eq!(absolute_step, 91);

        let mut report = core::mem::MaybeUninit::<bg_dynamics_report_v1>::uninit();
        assert_eq!(
            bg_dynamics_report_v1_init(
                report.as_mut_ptr(),
                core::mem::size_of::<bg_dynamics_report_v1>(),
                BG_ABI_VERSION,
            ),
            BG_STATUS_OK
        );
        let mut report = report.assume_init();
        report.steps_completed = 73;
        report.absolute_step = 74;
        report.degrees_of_freedom = 75;
        report.potential_kcal_per_mol = 1.25;
        report.kinetic_kcal_per_mol = 2.5;
        report.total_kcal_per_mol = 3.75;
        report.temperature_kelvin = 4.5;
        error.code = BG_DIRECT_EWALD_ERROR_NONFINITE_RESULT;
        error.detail[0] = b'y' as c_char;
        assert_eq!(
            bg_context_integrate_direct_ewald_composite_v1(
                ptr::null(),
                ptr::null_mut(),
                5,
                &mut report,
                &mut error,
            ),
            BG_STATUS_INVALID_ARGUMENT
        );
        assert_eq!(
            [
                report.steps_completed,
                report.absolute_step,
                report.degrees_of_freedom,
            ],
            [73, 74, 75]
        );
        assert_eq!(
            [
                report.potential_kcal_per_mol.to_bits(),
                report.kinetic_kcal_per_mol.to_bits(),
                report.total_kcal_per_mol.to_bits(),
                report.temperature_kelvin.to_bits(),
            ],
            [
                1.25_f64.to_bits(),
                2.5_f64.to_bits(),
                3.75_f64.to_bits(),
                4.5_f64.to_bits(),
            ]
        );
        assert_eq!(error.code, BG_DIRECT_EWALD_ERROR_NONE);
        assert!(error.detail.iter().all(|byte| *byte == 0));

        let mut required_size = 123_u64;
        assert_eq!(
            bg_direct_ewald_composite_simulation_v1_checkpoint_size(
                ptr::null(),
                &mut required_size,
            ),
            BG_STATUS_INVALID_ARGUMENT
        );
        assert_eq!(required_size, 123);

        let mut buffer = [0xA5_u8; 16];
        let mut written_size = 456_u64;
        assert_eq!(
            bg_direct_ewald_composite_simulation_v1_checkpoint_write(
                ptr::null(),
                buffer.as_mut_ptr().cast(),
                buffer.len() as u64,
                &mut written_size,
            ),
            BG_STATUS_INVALID_ARGUMENT
        );
        assert_eq!(written_size, 456);
        assert_eq!(buffer, [0xA5; 16]);
        assert_eq!(
            bg_direct_ewald_composite_simulation_v1_checkpoint_load(
                ptr::null_mut(),
                buffer.as_ptr().cast(),
                buffer.len() as u64,
            ),
            BG_STATUS_INVALID_ARGUMENT
        );
    }
}

#[test]
fn descriptor_initializers_bind_size_version_and_units() {
    // SAFETY: Each MaybeUninit output points to writable storage for exactly
    // the descriptor accepted by the initializer.
    unsafe {
        let mut options = core::mem::MaybeUninit::<bg_context_options>::uninit();
        assert_eq!(
            initialize(bg_context_options_init, options.as_mut_ptr()),
            BG_STATUS_OK
        );
        let options = options.assume_init();
        assert_eq!(
            options.struct_size as usize,
            core::mem::size_of_val(&options)
        );
        assert_eq!(options.abi_version, BG_ABI_VERSION);
        assert_eq!(options.unit_system, BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);

        let mut particles = core::mem::MaybeUninit::<bg_particle_soa>::uninit();
        assert_eq!(
            initialize(bg_particle_soa_init, particles.as_mut_ptr()),
            BG_STATUS_OK
        );
        let particles = particles.assume_init();
        assert_eq!(
            particles.struct_size as usize,
            core::mem::size_of_val(&particles)
        );
        assert_eq!(particles.abi_version, BG_ABI_VERSION);
        assert_eq!(particles.unit_system, BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);

        let mut view = core::mem::MaybeUninit::<bg_particle_soa_view>::uninit();
        assert_eq!(
            initialize(bg_particle_soa_view_init, view.as_mut_ptr()),
            BG_STATUS_OK
        );
        let view = view.assume_init();
        assert_eq!(view.struct_size as usize, core::mem::size_of_val(&view));
        assert_eq!(view.abi_version, BG_ABI_VERSION);
        assert_eq!(view.unit_system, BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);

        let mut positions = core::mem::MaybeUninit::<bg_position_soa>::uninit();
        assert_eq!(
            initialize(bg_position_soa_init, positions.as_mut_ptr()),
            BG_STATUS_OK
        );
        let positions = positions.assume_init();
        assert_eq!(
            positions.struct_size as usize,
            core::mem::size_of_val(&positions)
        );
        assert_eq!(positions.abi_version, BG_ABI_VERSION);
        assert_eq!(positions.unit_system, BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);

        let mut constraints = core::mem::MaybeUninit::<bg_distance_constraints_v1>::uninit();
        assert_eq!(
            initialize(bg_distance_constraints_v1_init, constraints.as_mut_ptr()),
            BG_STATUS_OK
        );
        let constraints = constraints.assume_init();
        assert_eq!(
            constraints.struct_size as usize,
            core::mem::size_of_val(&constraints)
        );
        assert_eq!(constraints.abi_version, BG_ABI_VERSION);
        assert_eq!(constraints.unit_system, BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);
        assert!(constraints.tolerance_angstrom > 0.0);
        assert!(constraints.velocity_tolerance_angstrom_per_femtosecond > 0.0);
        assert!(constraints.max_iterations > 0);

        let mut simulation = core::mem::MaybeUninit::<bg_simulation_options_v1>::uninit();
        assert_eq!(
            initialize(bg_simulation_options_v1_init, simulation.as_mut_ptr()),
            BG_STATUS_OK
        );
        let simulation = simulation.assume_init();
        assert_eq!(
            simulation.struct_size as usize,
            core::mem::size_of_val(&simulation)
        );
        assert_eq!(simulation.abi_version, BG_ABI_VERSION);
        assert_eq!(simulation.unit_system, BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);
        assert_eq!(simulation.integrator, BG_INTEGRATOR_VELOCITY_VERLET);

        let mut minimizer = core::mem::MaybeUninit::<bg_minimizer_options_v1>::uninit();
        assert_eq!(
            initialize(bg_minimizer_options_v1_init, minimizer.as_mut_ptr()),
            BG_STATUS_OK
        );
        let minimizer = minimizer.assume_init();
        assert_eq!(
            minimizer.struct_size as usize,
            core::mem::size_of_val(&minimizer)
        );
        assert_eq!(minimizer.abi_version, BG_ABI_VERSION);
        assert_eq!(minimizer.unit_system, BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);

        let mut minimization_report = core::mem::MaybeUninit::<bg_minimization_report_v1>::uninit();
        assert_eq!(
            initialize(
                bg_minimization_report_v1_init,
                minimization_report.as_mut_ptr(),
            ),
            BG_STATUS_OK
        );
        let minimization_report = minimization_report.assume_init();
        assert_eq!(
            minimization_report.struct_size as usize,
            core::mem::size_of_val(&minimization_report)
        );

        let mut dynamics_report = core::mem::MaybeUninit::<bg_dynamics_report_v1>::uninit();
        assert_eq!(
            initialize(bg_dynamics_report_v1_init, dynamics_report.as_mut_ptr()),
            BG_STATUS_OK
        );
        let dynamics_report = dynamics_report.assume_init();
        assert_eq!(
            dynamics_report.struct_size as usize,
            core::mem::size_of_val(&dynamics_report)
        );

        let mut geometric_context =
            core::mem::MaybeUninit::<bg_docking_geometric_admission_context_soa_v1>::uninit();
        assert_eq!(
            initialize(
                bg_docking_geometric_admission_context_soa_v1_init,
                geometric_context.as_mut_ptr(),
            ),
            BG_STATUS_OK
        );
        let geometric_context = geometric_context.assume_init();
        assert_eq!(
            geometric_context.unit_system,
            BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL
        );
        assert_eq!(geometric_context.hard_rejection_minimum_vdw_ratio, 0.55);
        assert_eq!(
            geometric_context.max_batch_exact_pair_evaluations,
            16_777_216
        );

        let mut geometric_batch = core::mem::MaybeUninit::<
            bg_docking_geometric_admission_candidate_batch_soa_v1,
        >::uninit();
        assert_eq!(
            initialize(
                bg_docking_geometric_admission_candidate_batch_soa_v1_init,
                geometric_batch.as_mut_ptr(),
            ),
            BG_STATUS_OK
        );
        let geometric_batch = geometric_batch.assume_init();
        assert_eq!(geometric_batch.candidate_count, 64);
        assert_eq!(
            geometric_batch.unit_system,
            BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL
        );

        let mut geometric_output =
            core::mem::MaybeUninit::<bg_docking_geometric_admission_output_v1>::uninit();
        assert_eq!(
            initialize(
                bg_docking_geometric_admission_output_v1_init,
                geometric_output.as_mut_ptr(),
            ),
            BG_STATUS_OK
        );
        let geometric_output = geometric_output.assume_init();
        assert_eq!(
            geometric_output.unit_system,
            BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL
        );
        assert_eq!(geometric_output.molecular_execution_authorized, 0);
        assert_eq!(geometric_output.reservation_authorized, 0);
        assert_eq!(geometric_output.benchmark_execution_authorized, 0);
        assert_eq!(geometric_output.existing_rank_auto_change_authorized, 0);
        assert_eq!(geometric_output.customer_pose_emission_authorized, 0);
        assert_eq!(geometric_output.production_claim_authorized, 0);
        assert_eq!(geometric_output.scientific_claim_authorized, 0);

        let mut ranking_input =
            core::mem::MaybeUninit::<bg_docking_stable_top_k_input_v1>::uninit();
        assert_eq!(
            initialize(
                bg_docking_stable_top_k_input_v1_init,
                ranking_input.as_mut_ptr(),
            ),
            BG_STATUS_OK
        );
        let ranking_input = ranking_input.assume_init();
        assert_eq!(
            ranking_input.struct_size as usize,
            core::mem::size_of_val(&ranking_input)
        );
        assert_eq!(ranking_input.candidate_count, 64);
        assert_eq!(ranking_input.top_k_limit, BG_DOCKING_STABLE_TOP_K_LIMIT);
        assert_eq!(ranking_input.unit_system, BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);

        let mut ranking_output =
            core::mem::MaybeUninit::<bg_docking_stable_top_k_output_v1>::uninit();
        assert_eq!(
            initialize(
                bg_docking_stable_top_k_output_v1_init,
                ranking_output.as_mut_ptr(),
            ),
            BG_STATUS_OK
        );
        let ranking_output = ranking_output.assume_init();
        assert_eq!(
            ranking_output.struct_size as usize,
            core::mem::size_of_val(&ranking_output)
        );
        assert_eq!(ranking_output.unit_system, BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);
        assert_eq!(ranking_output.existing_rank_auto_change_authorized, 0);
        assert_eq!(ranking_output.customer_pose_emission_authorized, 0);
        assert_eq!(ranking_output.production_claim_authorized, 0);

        let mut cluster_input =
            core::mem::MaybeUninit::<bg_docking_rmsd_cluster_input_v1>::uninit();
        assert_eq!(
            initialize(
                bg_docking_rmsd_cluster_input_v1_init,
                cluster_input.as_mut_ptr(),
            ),
            BG_STATUS_OK
        );
        let cluster_input = cluster_input.assume_init();
        assert_eq!(
            cluster_input.struct_size as usize,
            core::mem::size_of_val(&cluster_input)
        );
        assert_eq!(cluster_input.candidate_count, 64);
        assert_eq!(
            cluster_input.top_k_limit,
            BG_DOCKING_RMSD_CLUSTER_TOP_K_LIMIT
        );
        assert_eq!(cluster_input.unit_system, BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);

        let mut cluster_output =
            core::mem::MaybeUninit::<bg_docking_rmsd_cluster_output_v1>::uninit();
        assert_eq!(
            initialize(
                bg_docking_rmsd_cluster_output_v1_init,
                cluster_output.as_mut_ptr(),
            ),
            BG_STATUS_OK
        );
        let cluster_output = cluster_output.assume_init();
        assert_eq!(
            cluster_output.struct_size as usize,
            core::mem::size_of_val(&cluster_output)
        );
        assert_eq!(cluster_output.unit_system, BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);
        assert_eq!(cluster_output.existing_rank_auto_change_authorized, 0);
        assert_eq!(cluster_output.customer_pose_emission_authorized, 0);
        assert_eq!(cluster_output.production_claim_authorized, 0);

        let mut rigid_context =
            core::mem::MaybeUninit::<bg_docking_rigid_refinement_context_soa_v1>::uninit();
        assert_eq!(
            initialize(
                bg_docking_rigid_refinement_context_soa_v1_init,
                rigid_context.as_mut_ptr(),
            ),
            BG_STATUS_OK
        );
        let rigid_context = rigid_context.assume_init();
        assert_eq!(rigid_context.unit_system, BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);
        assert_eq!(rigid_context.v2.maximum_backtracking_evaluations, 6);
        assert_eq!(rigid_context.v3.maximum_rotation_steps, 2);
        assert_eq!(rigid_context.clearance_v4.maximum_rotation_steps, 6);

        let mut rigid_batch =
            core::mem::MaybeUninit::<bg_docking_rigid_refinement_candidate_batch_soa_v1>::uninit();
        assert_eq!(
            initialize(
                bg_docking_rigid_refinement_candidate_batch_soa_v1_init,
                rigid_batch.as_mut_ptr(),
            ),
            BG_STATUS_OK
        );
        let rigid_batch = rigid_batch.assume_init();
        assert_eq!(rigid_batch.candidate_count, 64);
        assert_eq!(rigid_batch.unit_system, BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);

        let mut rigid_output =
            core::mem::MaybeUninit::<bg_docking_rigid_refinement_output_v1>::uninit();
        assert_eq!(
            initialize(
                bg_docking_rigid_refinement_output_v1_init,
                rigid_output.as_mut_ptr(),
            ),
            BG_STATUS_OK
        );
        let rigid_output = rigid_output.assume_init();
        assert_eq!(rigid_output.unit_system, BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);
        assert_eq!(rigid_output.molecular_execution_authorized, 0);
        assert_eq!(rigid_output.existing_rank_auto_change_authorized, 0);
        assert_eq!(rigid_output.customer_pose_emission_authorized, 0);
        assert_eq!(rigid_output.production_claim_authorized, 0);
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
        assert_eq!(
            initialize(bg_context_options_init, options.as_mut_ptr()),
            BG_STATUS_OK
        );
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
fn explicit_rust_cpu_context_round_trips_without_cpp_fallback() {
    // SAFETY: Outputs and descriptor storage are live; the returned context is
    // queried and destroyed exactly once.
    unsafe {
        let mut available = 0_u8;
        assert_eq!(
            bg_backend_is_available(BG_BACKEND_RUST_CPU, 0, &mut available),
            BG_STATUS_OK
        );
        assert_eq!(available, 1);

        let mut options = core::mem::MaybeUninit::<bg_context_options>::uninit();
        assert_eq!(
            initialize(bg_context_options_init, options.as_mut_ptr()),
            BG_STATUS_OK
        );
        let mut options = options.assume_init();
        options.backend = BG_BACKEND_RUST_CPU;

        let mut context = ptr::null_mut();
        assert_eq!(bg_context_create(&options, &mut context), BG_STATUS_OK);
        assert!(!context.is_null());
        let mut selected = BG_BACKEND_AUTO;
        assert_eq!(bg_context_get_backend(context, &mut selected), BG_STATUS_OK);
        assert_eq!(selected, BG_BACKEND_RUST_CPU);
        bg_context_destroy(context);
    }
}

#[test]
fn rust_cpu_geometric_admission_preserves_fixed64_and_authority_false() {
    // SAFETY: Every descriptor channel remains live for the call, all outputs
    // have exact fixed64 capacity, and both native handles are destroyed once.
    unsafe {
        let mut options = core::mem::MaybeUninit::<bg_context_options>::uninit();
        assert_eq!(
            initialize(bg_context_options_init, options.as_mut_ptr()),
            BG_STATUS_OK
        );
        let mut options = options.assume_init();
        options.backend = BG_BACKEND_RUST_CPU;
        let mut context = ptr::null_mut();
        assert_eq!(bg_context_create(&options, &mut context), BG_STATUS_OK);

        let receptor_x = [0.0];
        let receptor_y = [0.0];
        let receptor_z = [0.0];
        let receptor_radius = [1.0];
        let ligand_radius = [1.0];
        let ligand_heavy = [1_u8];
        let mut descriptor =
            core::mem::MaybeUninit::<bg_docking_geometric_admission_context_soa_v1>::uninit();
        assert_eq!(
            initialize(
                bg_docking_geometric_admission_context_soa_v1_init,
                descriptor.as_mut_ptr(),
            ),
            BG_STATUS_OK
        );
        let mut descriptor = descriptor.assume_init();
        descriptor.receptor_atom_count = 1;
        descriptor.ligand_atom_count = 1;
        descriptor.receptor_x_angstrom = receptor_x.as_ptr();
        descriptor.receptor_y_angstrom = receptor_y.as_ptr();
        descriptor.receptor_z_angstrom = receptor_z.as_ptr();
        descriptor.receptor_vdw_radius_angstrom = receptor_radius.as_ptr();
        descriptor.ligand_vdw_radius_angstrom = ligand_radius.as_ptr();
        descriptor.ligand_heavy_atom_mask = ligand_heavy.as_ptr();
        descriptor.pocket_radius_angstrom = 10.0;
        descriptor.authority_input_receipt_sha256.fill(0x11);
        descriptor.receptor_system_sha256.fill(0x22);
        descriptor.ligand_system_sha256.fill(0x33);
        descriptor.backend_receipt_sha256.fill(0x44);
        let mut admission = ptr::null_mut();
        assert_eq!(
            bg_docking_geometric_admission_v1_create(context, &descriptor, &mut admission,),
            BG_STATUS_OK
        );
        assert!(!admission.is_null());
        let mut observed_backend = BG_BACKEND_AUTO;
        assert_eq!(
            bg_docking_geometric_admission_v1_get_backend(admission, &mut observed_backend,),
            BG_STATUS_OK
        );
        assert_eq!(observed_backend, BG_BACKEND_RUST_CPU);

        let mut states = [BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_UPSTREAM_FAILURE;
            BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize];
        states[0] = BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_EVALUATE;
        let mut x = [5.0; BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize];
        let y = [0.0; BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize];
        let z = [0.0; BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize];
        x[0] = 1.1;
        let mut batch = core::mem::MaybeUninit::<
            bg_docking_geometric_admission_candidate_batch_soa_v1,
        >::uninit();
        assert_eq!(
            initialize(
                bg_docking_geometric_admission_candidate_batch_soa_v1_init,
                batch.as_mut_ptr(),
            ),
            BG_STATUS_OK
        );
        let mut batch = batch.assume_init();
        batch.ligand_atom_count = 1;
        batch.candidate_state = states.as_ptr();
        batch.x_angstrom = x.as_ptr();
        batch.y_angstrom = y.as_ptr();
        batch.z_angstrom = z.as_ptr();
        let mut rows = [core::mem::zeroed::<bg_docking_geometric_admission_row_v1>();
            BG_DOCKING_FIXED64_CANDIDATE_COUNT as usize];
        let mut output =
            core::mem::MaybeUninit::<bg_docking_geometric_admission_output_v1>::uninit();
        assert_eq!(
            initialize(
                bg_docking_geometric_admission_output_v1_init,
                output.as_mut_ptr(),
            ),
            BG_STATUS_OK
        );
        let mut output = output.assume_init();
        output.row_capacity = rows.len() as u64;
        output.rows = rows.as_mut_ptr();
        assert_eq!(
            bg_docking_geometric_admission_v1_evaluate_fixed64(
                context,
                admission,
                &batch,
                &mut output,
            ),
            BG_STATUS_OK
        );
        assert_eq!(output.row_count, 64);
        assert_eq!(rows[0].status, BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED);
        assert_eq!(
            rows[0].decision,
            BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED
        );
        assert_eq!(rows[0].rank_eligible, 1);
        assert_eq!(rows[0].minimum_vdw_ratio, 0.55);
        assert_eq!(
            rows[1].status,
            BG_DOCKING_GEOMETRIC_ADMISSION_ROW_UPSTREAM_FAILURE
        );
        assert_eq!(output.molecular_execution_authorized, 0);
        assert_eq!(output.reservation_authorized, 0);
        assert_eq!(output.benchmark_execution_authorized, 0);
        assert_eq!(output.existing_rank_auto_change_authorized, 0);
        assert_eq!(output.customer_pose_emission_authorized, 0);
        assert_eq!(output.production_claim_authorized, 0);
        assert_eq!(output.scientific_claim_authorized, 0);
        assert!(output.batch_receipt_sha256.iter().any(|byte| *byte != 0));
        assert!(rows
            .iter()
            .all(|row| row.row_receipt_sha256.iter().any(|byte| *byte != 0)));

        bg_docking_geometric_admission_v1_destroy(admission);
        bg_context_destroy(context);
    }
}

#[test]
fn explicit_hip_safe_request_never_falls_back_to_cpu() {
    // SAFETY: All outputs point to live writable values. A successful context
    // is queried and destroyed exactly once; a failed create leaves it null.
    unsafe {
        let mut available = 0_u8;
        assert_eq!(
            bg_backend_is_available(BG_BACKEND_HIP_SAFE, 0, &mut available),
            BG_STATUS_OK
        );
        let hip_safe_available = available == 1;

        let mut options = core::mem::MaybeUninit::<bg_context_options>::uninit();
        assert_eq!(
            initialize(bg_context_options_init, options.as_mut_ptr()),
            BG_STATUS_OK
        );
        let mut options = options.assume_init();
        options.backend = BG_BACKEND_HIP_SAFE;

        let mut context = ptr::null_mut::<bg_context>();
        let status = bg_context_create(&options, &mut context);
        if hip_safe_available {
            assert_eq!(status, BG_STATUS_OK);
            assert!(!context.is_null());
            let mut selected = BG_BACKEND_AUTO;
            assert_eq!(bg_context_get_backend(context, &mut selected), BG_STATUS_OK);
            assert_eq!(selected, BG_BACKEND_HIP_SAFE);
            bg_context_destroy(context);
        } else {
            assert_eq!(status, BG_STATUS_BACKEND_UNAVAILABLE);
            assert!(context.is_null());
        }

        #[cfg(not(feature = "hip"))]
        {
            assert_eq!(
                bg_backend_is_available(BG_BACKEND_HIP_FAST, 0, &mut available),
                BG_STATUS_OK
            );
            assert_eq!(available, 0);
        }
    }
}

#[test]
#[cfg(feature = "hip")]
fn explicit_hip_request_round_trips_without_cpu_fallback() {
    // SAFETY: All outputs point to live writable values, and the returned
    // context is destroyed exactly once after the backend query.
    unsafe {
        let mut available = 0_u8;
        assert_eq!(
            bg_backend_is_available(BG_BACKEND_HIP, 0, &mut available),
            BG_STATUS_OK
        );
        if available == 0 {
            assert_ne!(
                std::env::var("BG_REQUIRE_HIP_DEVICE").as_deref(),
                Ok("1"),
                "BG_REQUIRE_HIP_DEVICE=1 but no HIP device is available at ordinal zero"
            );
            eprintln!("SKIP: HIP feature was compiled without a visible device zero");
            return;
        }

        let mut options = core::mem::MaybeUninit::<bg_context_options>::uninit();
        assert_eq!(
            initialize(bg_context_options_init, options.as_mut_ptr()),
            BG_STATUS_OK
        );
        let mut options = options.assume_init();
        options.backend = BG_BACKEND_HIP;

        let mut context = ptr::null_mut();
        assert_eq!(bg_context_create(&options, &mut context), BG_STATUS_OK);
        assert!(!context.is_null());
        let mut backend = BG_BACKEND_AUTO;
        assert_eq!(bg_context_get_backend(context, &mut backend), BG_STATUS_OK);
        assert_eq!(backend, BG_BACKEND_HIP);
        bg_context_destroy(context);
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
        assert_eq!(
            initialize(bg_particle_soa_init, particles.as_mut_ptr()),
            BG_STATUS_OK
        );
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
        assert_eq!(
            initialize(bg_particle_soa_view_init, view.as_mut_ptr()),
            BG_STATUS_OK
        );
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
        assert_eq!(
            initialize(bg_position_soa_init, positions.as_mut_ptr()),
            BG_STATUS_OK
        );
        let mut positions = positions.assume_init();
        positions.particle_count = 2;
        positions.x_angstrom = replacement_x.as_ptr();
        positions.y_angstrom = replacement_y.as_ptr();
        positions.z_angstrom = replacement_z.as_ptr();
        assert_eq!(bg_system_set_positions(system, &positions), BG_STATUS_OK);

        assert_eq!(
            initialize(bg_particle_soa_view_init, &mut view),
            BG_STATUS_OK
        );
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
