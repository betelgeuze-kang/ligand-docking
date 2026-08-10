#include <betelgeuze/engine.h>

#include <cstddef>
#include <cstdint>
#include <type_traits>

static_assert(std::is_standard_layout<bg_context_options>::value);
static_assert(std::is_standard_layout<bg_particle_soa>::value);
static_assert(std::is_standard_layout<bg_particle_soa_view>::value);
static_assert(std::is_standard_layout<bg_position_soa>::value);

static_assert(sizeof(bg_context_options) == 64);
static_assert(alignof(bg_context_options) == alignof(uint64_t));
static_assert(offsetof(bg_context_options, struct_size) == 0);
static_assert(offsetof(bg_context_options, abi_version) == 4);
static_assert(offsetof(bg_context_options, backend) == 8);
static_assert(offsetof(bg_context_options, unit_system) == 12);
static_assert(offsetof(bg_context_options, device_ordinal) == 16);
static_assert(offsetof(bg_context_options, reserved0) == 20);
static_assert(offsetof(bg_context_options, flags) == 24);
static_assert(offsetof(bg_context_options, reserved) == 32);

#if INTPTR_MAX == INT64_MAX
static_assert(sizeof(bg_particle_soa) == 120);
static_assert(alignof(bg_particle_soa) == 8);
static_assert(offsetof(bg_particle_soa, struct_size) == 0);
static_assert(offsetof(bg_particle_soa, abi_version) == 4);
static_assert(offsetof(bg_particle_soa, particle_count) == 8);
static_assert(offsetof(bg_particle_soa, unit_system) == 16);
static_assert(offsetof(bg_particle_soa, reserved0) == 20);
static_assert(offsetof(bg_particle_soa, position_x_angstrom) == 24);
static_assert(offsetof(bg_particle_soa, position_y_angstrom) == 32);
static_assert(offsetof(bg_particle_soa, position_z_angstrom) == 40);
static_assert(offsetof(bg_particle_soa, velocity_x_angstrom_per_femtosecond) == 48);
static_assert(offsetof(bg_particle_soa, velocity_y_angstrom_per_femtosecond) == 56);
static_assert(offsetof(bg_particle_soa, velocity_z_angstrom_per_femtosecond) == 64);
static_assert(offsetof(bg_particle_soa, mass_dalton) == 72);
static_assert(offsetof(bg_particle_soa, charge_elementary) == 80);
static_assert(offsetof(bg_particle_soa, reserved) == 88);

static_assert(sizeof(bg_particle_soa_view) == 120);
static_assert(alignof(bg_particle_soa_view) == 8);
static_assert(offsetof(bg_particle_soa_view, particle_count) == 8);
static_assert(offsetof(bg_particle_soa_view, position_x_angstrom) == 24);
static_assert(offsetof(bg_particle_soa_view, charge_elementary) == 80);
static_assert(offsetof(bg_particle_soa_view, reserved) == 88);

static_assert(sizeof(bg_position_soa) == 80);
static_assert(alignof(bg_position_soa) == 8);
static_assert(offsetof(bg_position_soa, struct_size) == 0);
static_assert(offsetof(bg_position_soa, abi_version) == 4);
static_assert(offsetof(bg_position_soa, particle_count) == 8);
static_assert(offsetof(bg_position_soa, unit_system) == 16);
static_assert(offsetof(bg_position_soa, reserved0) == 20);
static_assert(offsetof(bg_position_soa, x_angstrom) == 24);
static_assert(offsetof(bg_position_soa, y_angstrom) == 32);
static_assert(offsetof(bg_position_soa, z_angstrom) == 40);
static_assert(offsetof(bg_position_soa, reserved) == 48);
#endif

static_assert(noexcept(bg_abi_version()));
static_assert(noexcept(bg_context_destroy(nullptr)));
static_assert(noexcept(bg_system_destroy(nullptr)));
