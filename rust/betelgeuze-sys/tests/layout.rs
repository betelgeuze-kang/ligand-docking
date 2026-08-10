use core::mem::{align_of, offset_of, size_of};

use betelgeuze_sys::*;

#[test]
fn scalar_aliases_and_discriminants_match_the_c_header() {
    assert_eq!(size_of::<bg_status>(), 4);
    assert_eq!(size_of::<bg_backend>(), 4);
    assert_eq!(size_of::<bg_unit_system>(), 4);
    assert_eq!(BG_STATUS_OK, 0);
    assert_eq!(BG_STATUS_INTERNAL_ERROR, 9);
    assert_eq!(BG_BACKEND_AUTO, 0);
    assert_eq!(BG_BACKEND_CPU, 1);
    assert_eq!(BG_BACKEND_HIP, 2);
    assert_eq!(BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL, 1);
}

#[test]
fn context_options_layout_matches_the_c_header() {
    assert_eq!(size_of::<bg_context_options>(), 64);
    assert_eq!(align_of::<bg_context_options>(), align_of::<u64>());
    assert_eq!(offset_of!(bg_context_options, struct_size), 0);
    assert_eq!(offset_of!(bg_context_options, abi_version), 4);
    assert_eq!(offset_of!(bg_context_options, backend), 8);
    assert_eq!(offset_of!(bg_context_options, unit_system), 12);
    assert_eq!(offset_of!(bg_context_options, device_ordinal), 16);
    assert_eq!(offset_of!(bg_context_options, reserved0), 20);
    assert_eq!(offset_of!(bg_context_options, flags), 24);
    assert_eq!(offset_of!(bg_context_options, reserved), 32);
}

#[cfg(target_pointer_width = "64")]
#[test]
fn particle_soa_layout_matches_the_c_header() {
    assert_eq!(size_of::<bg_particle_soa>(), 120);
    assert_eq!(align_of::<bg_particle_soa>(), 8);
    assert_eq!(offset_of!(bg_particle_soa, struct_size), 0);
    assert_eq!(offset_of!(bg_particle_soa, abi_version), 4);
    assert_eq!(offset_of!(bg_particle_soa, particle_count), 8);
    assert_eq!(offset_of!(bg_particle_soa, unit_system), 16);
    assert_eq!(offset_of!(bg_particle_soa, reserved0), 20);
    assert_eq!(offset_of!(bg_particle_soa, position_x_angstrom), 24);
    assert_eq!(offset_of!(bg_particle_soa, position_y_angstrom), 32);
    assert_eq!(offset_of!(bg_particle_soa, position_z_angstrom), 40);
    assert_eq!(
        offset_of!(bg_particle_soa, velocity_x_angstrom_per_femtosecond),
        48
    );
    assert_eq!(
        offset_of!(bg_particle_soa, velocity_y_angstrom_per_femtosecond),
        56
    );
    assert_eq!(
        offset_of!(bg_particle_soa, velocity_z_angstrom_per_femtosecond),
        64
    );
    assert_eq!(offset_of!(bg_particle_soa, mass_dalton), 72);
    assert_eq!(offset_of!(bg_particle_soa, charge_elementary), 80);
    assert_eq!(offset_of!(bg_particle_soa, reserved), 88);

    assert_eq!(size_of::<bg_particle_soa_view>(), 120);
    assert_eq!(align_of::<bg_particle_soa_view>(), 8);
    assert_eq!(offset_of!(bg_particle_soa_view, particle_count), 8);
    assert_eq!(offset_of!(bg_particle_soa_view, position_x_angstrom), 24);
    assert_eq!(offset_of!(bg_particle_soa_view, charge_elementary), 80);
    assert_eq!(offset_of!(bg_particle_soa_view, reserved), 88);
}

#[cfg(target_pointer_width = "64")]
#[test]
fn position_soa_layout_matches_the_c_header() {
    assert_eq!(size_of::<bg_position_soa>(), 80);
    assert_eq!(align_of::<bg_position_soa>(), 8);
    assert_eq!(offset_of!(bg_position_soa, struct_size), 0);
    assert_eq!(offset_of!(bg_position_soa, abi_version), 4);
    assert_eq!(offset_of!(bg_position_soa, particle_count), 8);
    assert_eq!(offset_of!(bg_position_soa, unit_system), 16);
    assert_eq!(offset_of!(bg_position_soa, reserved0), 20);
    assert_eq!(offset_of!(bg_position_soa, x_angstrom), 24);
    assert_eq!(offset_of!(bg_position_soa, y_angstrom), 32);
    assert_eq!(offset_of!(bg_position_soa, z_angstrom), 40);
    assert_eq!(offset_of!(bg_position_soa, reserved), 48);
}

#[test]
fn opaque_handles_are_only_used_behind_pointers() {
    assert_eq!(size_of::<*mut bg_context>(), size_of::<usize>());
    assert_eq!(size_of::<*mut bg_system>(), size_of::<usize>());
}
