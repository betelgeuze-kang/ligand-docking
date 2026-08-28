#include <betelgeuze/direct_ewald_composite_dynamics.h>

#include <cstddef>
#include <cstdint>
#include <type_traits>

template <typename Type, typename = void>
struct is_complete : std::false_type {};

template <typename Type>
struct is_complete<Type, std::void_t<decltype(sizeof(Type))>>
    : std::true_type {};

static_assert(
    !is_complete<bg_direct_ewald_composite_simulation_v1>::value,
    "composite-dynamics owner must remain opaque");
static_assert(std::is_standard_layout<bg_distance_constraints_v1>::value);
static_assert(std::is_standard_layout<bg_simulation_options_v1>::value);
static_assert(std::is_standard_layout<bg_dynamics_report_v1>::value);

static_assert(sizeof(bg_distance_constraints_v1) == 104);
static_assert(alignof(bg_distance_constraints_v1) == alignof(uint64_t));
static_assert(offsetof(bg_distance_constraints_v1, constraint_count) == 8);
static_assert(offsetof(bg_distance_constraints_v1, atom_i) == 24);
static_assert(offsetof(bg_distance_constraints_v1, reserved) == 72);

static_assert(sizeof(bg_simulation_options_v1) == 80);
static_assert(alignof(bg_simulation_options_v1) == alignof(uint64_t));
static_assert(offsetof(bg_simulation_options_v1, integrator) == 12);
static_assert(offsetof(bg_simulation_options_v1, timestep_femtoseconds) == 16);
static_assert(offsetof(bg_simulation_options_v1, random_seed) == 40);
static_assert(offsetof(bg_simulation_options_v1, reserved) == 48);

static_assert(sizeof(bg_dynamics_report_v1) == 104);
static_assert(alignof(bg_dynamics_report_v1) == alignof(uint64_t));
static_assert(offsetof(bg_dynamics_report_v1, steps_completed) == 16);
static_assert(offsetof(bg_dynamics_report_v1, absolute_step) == 24);
static_assert(offsetof(bg_dynamics_report_v1, degrees_of_freedom) == 32);
static_assert(offsetof(bg_dynamics_report_v1, potential_kcal_per_mol) == 40);
static_assert(offsetof(bg_dynamics_report_v1, reserved) == 72);

static_assert(noexcept(bg_direct_ewald_composite_dynamics_abi_version()));
static_assert(noexcept(
    bg_direct_ewald_composite_dynamics_abi_version_major()));
static_assert(noexcept(
    bg_direct_ewald_composite_dynamics_abi_version_minor()));
static_assert(noexcept(
    bg_direct_ewald_composite_dynamics_abi_version_string()));
static_assert(noexcept(
    bg_direct_ewald_composite_dynamics_v1_profile_id()));
static_assert(noexcept(bg_direct_ewald_composite_simulation_v1_create(
    nullptr, nullptr, nullptr, nullptr, nullptr, nullptr, nullptr)));
static_assert(noexcept(
    bg_direct_ewald_composite_simulation_v1_destroy(nullptr)));
static_assert(noexcept(
    bg_direct_ewald_composite_simulation_v1_get_particles(nullptr, nullptr)));
static_assert(noexcept(
    bg_direct_ewald_composite_simulation_v1_get_absolute_step(
        nullptr, nullptr)));
static_assert(noexcept(bg_context_integrate_direct_ewald_composite_v1(
    nullptr, nullptr, UINT64_C(0), nullptr, nullptr)));
static_assert(noexcept(
    bg_direct_ewald_composite_simulation_v1_checkpoint_size(
        nullptr, nullptr)));
static_assert(noexcept(
    bg_direct_ewald_composite_simulation_v1_checkpoint_write(
        nullptr, nullptr, UINT64_C(0), nullptr)));
static_assert(noexcept(
    bg_direct_ewald_composite_simulation_v1_checkpoint_load(
        nullptr, nullptr, UINT64_C(0))));
