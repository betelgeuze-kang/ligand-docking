#include <betelgeuze/direct_ewald.h>

#include <cstddef>
#include <cstdint>
#include <type_traits>

template <typename T, typename = void>
struct direct_ewald_is_complete : std::false_type {};

template <typename T>
struct direct_ewald_is_complete<T, std::void_t<decltype(sizeof(T))>>
    : std::true_type {};

static_assert(!direct_ewald_is_complete<bg_direct_ewald_model_v1>::value);
static_assert(std::is_standard_layout<bg_direct_ewald_parameters_v1>::value);
static_assert(
    std::is_standard_layout<bg_direct_ewald_energy_components_v1>::value);
static_assert(std::is_standard_layout<bg_direct_ewald_force_soa_v1>::value);
static_assert(std::is_standard_layout<bg_direct_ewald_error_v1>::value);

static_assert(sizeof(bg_direct_ewald_parameters_v1) == 184);
static_assert(alignof(bg_direct_ewald_parameters_v1) == alignof(uint64_t));
static_assert(offsetof(bg_direct_ewald_parameters_v1, struct_size) == 0);
static_assert(offsetof(bg_direct_ewald_parameters_v1, abi_version) == 4);
static_assert(offsetof(bg_direct_ewald_parameters_v1, atom_count) == 8);
static_assert(offsetof(bg_direct_ewald_parameters_v1, unit_system) == 16);
static_assert(offsetof(bg_direct_ewald_parameters_v1, reserved0) == 20);
static_assert(
    offsetof(bg_direct_ewald_parameters_v1, cell_lengths_angstrom) == 24);
static_assert(
    offsetof(bg_direct_ewald_parameters_v1, alpha_per_angstrom) == 48);
static_assert(
    offsetof(bg_direct_ewald_parameters_v1, real_space_cutoff_angstrom) == 56);
static_assert(
    offsetof(bg_direct_ewald_parameters_v1, reciprocal_max_indices) == 64);
static_assert(offsetof(bg_direct_ewald_parameters_v1, reserved1) == 76);
static_assert(offsetof(bg_direct_ewald_parameters_v1, dielectric) == 80);
static_assert(
    offsetof(bg_direct_ewald_parameters_v1, minimum_pair_distance_angstrom) ==
    88);
static_assert(offsetof(bg_direct_ewald_parameters_v1, exclusion_count) == 96);
static_assert(offsetof(bg_direct_ewald_parameters_v1, exclusion_atom_i) == 104);
static_assert(offsetof(bg_direct_ewald_parameters_v1, exclusion_atom_j) == 112);
static_assert(offsetof(bg_direct_ewald_parameters_v1, pair_scale_count) == 120);
static_assert(offsetof(bg_direct_ewald_parameters_v1, pair_scale_atom_i) == 128);
static_assert(offsetof(bg_direct_ewald_parameters_v1, pair_scale_atom_j) == 136);
static_assert(
    offsetof(bg_direct_ewald_parameters_v1, pair_scale_coulomb) == 144);
static_assert(offsetof(bg_direct_ewald_parameters_v1, reserved) == 152);

static_assert(sizeof(bg_direct_ewald_energy_components_v1) == 88);
static_assert(
    alignof(bg_direct_ewald_energy_components_v1) == alignof(uint64_t));
static_assert(
    offsetof(bg_direct_ewald_energy_components_v1, struct_size) == 0);
static_assert(
    offsetof(bg_direct_ewald_energy_components_v1, abi_version) == 4);
static_assert(
    offsetof(bg_direct_ewald_energy_components_v1, unit_system) == 8);
static_assert(
    offsetof(bg_direct_ewald_energy_components_v1, reserved0) == 12);
static_assert(
    offsetof(bg_direct_ewald_energy_components_v1, real_space_kcal_per_mol) ==
    16);
static_assert(
    offsetof(
        bg_direct_ewald_energy_components_v1,
        reciprocal_space_kcal_per_mol) == 24);
static_assert(
    offsetof(bg_direct_ewald_energy_components_v1, self_kcal_per_mol) == 32);
static_assert(
    offsetof(
        bg_direct_ewald_energy_components_v1,
        pair_correction_kcal_per_mol) == 40);
static_assert(
    offsetof(bg_direct_ewald_energy_components_v1, total_kcal_per_mol) == 48);
static_assert(offsetof(bg_direct_ewald_energy_components_v1, reserved) == 56);

static_assert(sizeof(bg_direct_ewald_force_soa_v1) == 88);
static_assert(alignof(bg_direct_ewald_force_soa_v1) == alignof(uint64_t));
static_assert(offsetof(bg_direct_ewald_force_soa_v1, struct_size) == 0);
static_assert(offsetof(bg_direct_ewald_force_soa_v1, abi_version) == 4);
static_assert(offsetof(bg_direct_ewald_force_soa_v1, atom_capacity) == 8);
static_assert(offsetof(bg_direct_ewald_force_soa_v1, atom_count) == 16);
static_assert(offsetof(bg_direct_ewald_force_soa_v1, unit_system) == 24);
static_assert(offsetof(bg_direct_ewald_force_soa_v1, reserved0) == 28);
static_assert(
    offsetof(bg_direct_ewald_force_soa_v1, x_kcal_per_mol_angstrom) == 32);
static_assert(
    offsetof(bg_direct_ewald_force_soa_v1, y_kcal_per_mol_angstrom) == 40);
static_assert(
    offsetof(bg_direct_ewald_force_soa_v1, z_kcal_per_mol_angstrom) == 48);
static_assert(offsetof(bg_direct_ewald_force_soa_v1, reserved) == 56);

static_assert(sizeof(bg_direct_ewald_error_v1) == 304);
static_assert(alignof(bg_direct_ewald_error_v1) == alignof(uint64_t));
static_assert(offsetof(bg_direct_ewald_error_v1, struct_size) == 0);
static_assert(offsetof(bg_direct_ewald_error_v1, abi_version) == 4);
static_assert(offsetof(bg_direct_ewald_error_v1, code) == 8);
static_assert(offsetof(bg_direct_ewald_error_v1, reserved0) == 12);
static_assert(offsetof(bg_direct_ewald_error_v1, detail) == 16);
static_assert(offsetof(bg_direct_ewald_error_v1, reserved) == 272);

static_assert(noexcept(bg_direct_ewald_abi_version()));
static_assert(noexcept(bg_direct_ewald_abi_version_major()));
static_assert(noexcept(bg_direct_ewald_abi_version_minor()));
static_assert(noexcept(bg_direct_ewald_abi_version_string()));
static_assert(noexcept(bg_direct_ewald_parameters_v1_init(
    static_cast<bg_direct_ewald_parameters_v1 *>(nullptr))));
static_assert(noexcept(bg_direct_ewald_energy_components_v1_init(
    static_cast<bg_direct_ewald_energy_components_v1 *>(nullptr))));
static_assert(noexcept(bg_direct_ewald_force_soa_v1_init(
    static_cast<bg_direct_ewald_force_soa_v1 *>(nullptr))));
static_assert(noexcept(bg_direct_ewald_error_v1_init(
    static_cast<bg_direct_ewald_error_v1 *>(nullptr))));
static_assert(noexcept(bg_direct_ewald_model_v1_create(nullptr, nullptr, nullptr)));
static_assert(noexcept(bg_direct_ewald_model_v1_destroy(nullptr)));
static_assert(noexcept(bg_direct_ewald_model_v1_get_atom_count(nullptr, nullptr)));
static_assert(noexcept(bg_direct_ewald_model_v1_profile_id()));
static_assert(noexcept(bg_context_evaluate_direct_ewald_v1(
    nullptr, nullptr, nullptr, nullptr, nullptr, nullptr)));
