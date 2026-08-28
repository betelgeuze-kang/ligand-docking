#include <betelgeuze/particle_mesh_reciprocal.h>

#include <cstddef>
#include <cstdint>
#include <type_traits>

template <typename T, typename = void>
struct particle_mesh_reciprocal_is_complete : std::false_type {};
template <typename T>
struct particle_mesh_reciprocal_is_complete<T, std::void_t<decltype(sizeof(T))>> : std::true_type {};

static_assert(!particle_mesh_reciprocal_is_complete<bg_particle_mesh_reciprocal_model_v1>::value);
static_assert(std::is_standard_layout<bg_particle_mesh_reciprocal_parameters_v1>::value);
static_assert(std::is_standard_layout<bg_particle_mesh_reciprocal_energy_v1>::value);
static_assert(std::is_standard_layout<bg_particle_mesh_reciprocal_force_soa_v1>::value);
static_assert(std::is_standard_layout<bg_particle_mesh_reciprocal_error_v1>::value);

static_assert(sizeof(bg_particle_mesh_reciprocal_parameters_v1) == 112);
static_assert(alignof(bg_particle_mesh_reciprocal_parameters_v1) == alignof(uint64_t));
static_assert(offsetof(bg_particle_mesh_reciprocal_parameters_v1, struct_size) == 0);
static_assert(offsetof(bg_particle_mesh_reciprocal_parameters_v1, abi_version) == 4);
static_assert(offsetof(bg_particle_mesh_reciprocal_parameters_v1, atom_count) == 8);
static_assert(offsetof(bg_particle_mesh_reciprocal_parameters_v1, unit_system) == 16);
static_assert(offsetof(bg_particle_mesh_reciprocal_parameters_v1, reserved0) == 20);
static_assert(offsetof(bg_particle_mesh_reciprocal_parameters_v1, cell_lengths_angstrom) == 24);
static_assert(offsetof(bg_particle_mesh_reciprocal_parameters_v1, alpha_per_angstrom) == 48);
static_assert(offsetof(bg_particle_mesh_reciprocal_parameters_v1, mesh_dimensions) == 56);
static_assert(offsetof(bg_particle_mesh_reciprocal_parameters_v1, reserved1) == 68);
static_assert(offsetof(bg_particle_mesh_reciprocal_parameters_v1, dielectric) == 72);
static_assert(offsetof(bg_particle_mesh_reciprocal_parameters_v1, reserved) == 80);

static_assert(sizeof(bg_particle_mesh_reciprocal_energy_v1) == 56);
static_assert(alignof(bg_particle_mesh_reciprocal_energy_v1) == alignof(uint64_t));
static_assert(offsetof(bg_particle_mesh_reciprocal_energy_v1, struct_size) == 0);
static_assert(offsetof(bg_particle_mesh_reciprocal_energy_v1, abi_version) == 4);
static_assert(offsetof(bg_particle_mesh_reciprocal_energy_v1, unit_system) == 8);
static_assert(offsetof(bg_particle_mesh_reciprocal_energy_v1, reserved0) == 12);
static_assert(offsetof(bg_particle_mesh_reciprocal_energy_v1, reciprocal_space_kcal_per_mol) == 16);
static_assert(offsetof(bg_particle_mesh_reciprocal_energy_v1, reserved) == 24);

static_assert(sizeof(bg_particle_mesh_reciprocal_force_soa_v1) == 88);
static_assert(alignof(bg_particle_mesh_reciprocal_force_soa_v1) == alignof(uint64_t));
static_assert(offsetof(bg_particle_mesh_reciprocal_force_soa_v1, struct_size) == 0);
static_assert(offsetof(bg_particle_mesh_reciprocal_force_soa_v1, abi_version) == 4);
static_assert(offsetof(bg_particle_mesh_reciprocal_force_soa_v1, atom_capacity) == 8);
static_assert(offsetof(bg_particle_mesh_reciprocal_force_soa_v1, atom_count) == 16);
static_assert(offsetof(bg_particle_mesh_reciprocal_force_soa_v1, unit_system) == 24);
static_assert(offsetof(bg_particle_mesh_reciprocal_force_soa_v1, reserved0) == 28);
static_assert(offsetof(bg_particle_mesh_reciprocal_force_soa_v1, x_kcal_per_mol_angstrom) == 32);
static_assert(offsetof(bg_particle_mesh_reciprocal_force_soa_v1, y_kcal_per_mol_angstrom) == 40);
static_assert(offsetof(bg_particle_mesh_reciprocal_force_soa_v1, z_kcal_per_mol_angstrom) == 48);
static_assert(offsetof(bg_particle_mesh_reciprocal_force_soa_v1, reserved) == 56);

static_assert(sizeof(bg_particle_mesh_reciprocal_error_v1) == 304);
static_assert(alignof(bg_particle_mesh_reciprocal_error_v1) == alignof(uint64_t));
static_assert(offsetof(bg_particle_mesh_reciprocal_error_v1, struct_size) == 0);
static_assert(offsetof(bg_particle_mesh_reciprocal_error_v1, abi_version) == 4);
static_assert(offsetof(bg_particle_mesh_reciprocal_error_v1, code) == 8);
static_assert(offsetof(bg_particle_mesh_reciprocal_error_v1, reserved0) == 12);
static_assert(offsetof(bg_particle_mesh_reciprocal_error_v1, detail) == 16);
static_assert(offsetof(bg_particle_mesh_reciprocal_error_v1, reserved) == 272);

static_assert(noexcept(bg_particle_mesh_reciprocal_abi_version()));
static_assert(noexcept(bg_particle_mesh_reciprocal_abi_version_major()));
static_assert(noexcept(bg_particle_mesh_reciprocal_abi_version_minor()));
static_assert(noexcept(bg_particle_mesh_reciprocal_abi_version_string()));
static_assert(noexcept(bg_particle_mesh_reciprocal_parameters_v1_init(static_cast<bg_particle_mesh_reciprocal_parameters_v1 *>(nullptr))));
static_assert(noexcept(bg_particle_mesh_reciprocal_energy_v1_init(static_cast<bg_particle_mesh_reciprocal_energy_v1 *>(nullptr))));
static_assert(noexcept(bg_particle_mesh_reciprocal_force_soa_v1_init(static_cast<bg_particle_mesh_reciprocal_force_soa_v1 *>(nullptr))));
static_assert(noexcept(bg_particle_mesh_reciprocal_error_v1_init(static_cast<bg_particle_mesh_reciprocal_error_v1 *>(nullptr))));
static_assert(noexcept(bg_particle_mesh_reciprocal_model_v1_create(nullptr, nullptr, nullptr)));
static_assert(noexcept(bg_particle_mesh_reciprocal_model_v1_destroy(nullptr)));
static_assert(noexcept(bg_particle_mesh_reciprocal_model_v1_get_atom_count(nullptr, nullptr)));
static_assert(noexcept(bg_particle_mesh_reciprocal_model_v1_profile_id()));
static_assert(noexcept(bg_context_evaluate_particle_mesh_reciprocal_v1(nullptr, nullptr, nullptr, nullptr, nullptr, nullptr)));
