#include <betelgeuze/particle_mesh_ewald_composite.h>

#include <cstddef>
#include <cstdint>
#include <type_traits>

static_assert(std::is_standard_layout<
              bg_particle_mesh_ewald_composite_energy_components_v1>::value);
static_assert(std::is_standard_layout<
              bg_particle_mesh_ewald_composite_force_soa_v1>::value);

static_assert(
    sizeof(bg_particle_mesh_ewald_composite_energy_components_v1) == 144);
static_assert(
    alignof(bg_particle_mesh_ewald_composite_energy_components_v1) ==
    alignof(uint64_t));
static_assert(offsetof(
                  bg_particle_mesh_ewald_composite_energy_components_v1,
                  struct_size) == 0);
static_assert(offsetof(
                  bg_particle_mesh_ewald_composite_energy_components_v1,
                  abi_version) == 4);
static_assert(offsetof(
                  bg_particle_mesh_ewald_composite_energy_components_v1,
                  unit_system) == 8);
static_assert(offsetof(
                  bg_particle_mesh_ewald_composite_energy_components_v1,
                  reserved0) == 12);
static_assert(offsetof(
                  bg_particle_mesh_ewald_composite_energy_components_v1,
                  short_harmonic_bond_kcal_per_mol) == 16);
static_assert(offsetof(
                  bg_particle_mesh_ewald_composite_energy_components_v1,
                  short_harmonic_angle_kcal_per_mol) == 24);
static_assert(offsetof(
                  bg_particle_mesh_ewald_composite_energy_components_v1,
                  short_periodic_torsion_kcal_per_mol) == 32);
static_assert(offsetof(
                  bg_particle_mesh_ewald_composite_energy_components_v1,
                  short_lennard_jones_kcal_per_mol) == 40);
static_assert(offsetof(
                  bg_particle_mesh_ewald_composite_energy_components_v1,
                  short_coulomb_kcal_per_mol) == 48);
static_assert(offsetof(
                  bg_particle_mesh_ewald_composite_energy_components_v1,
                  short_total_kcal_per_mol) == 56);
static_assert(offsetof(
                  bg_particle_mesh_ewald_composite_energy_components_v1,
                  pme_real_space_kcal_per_mol) == 64);
static_assert(offsetof(
                  bg_particle_mesh_ewald_composite_energy_components_v1,
                  pme_reciprocal_space_kcal_per_mol) == 72);
static_assert(offsetof(
                  bg_particle_mesh_ewald_composite_energy_components_v1,
                  pme_self_kcal_per_mol) == 80);
static_assert(offsetof(
                  bg_particle_mesh_ewald_composite_energy_components_v1,
                  pme_pair_correction_kcal_per_mol) == 88);
static_assert(offsetof(
                  bg_particle_mesh_ewald_composite_energy_components_v1,
                  pme_total_kcal_per_mol) == 96);
static_assert(offsetof(
                  bg_particle_mesh_ewald_composite_energy_components_v1,
                  total_kcal_per_mol) == 104);
static_assert(offsetof(
                  bg_particle_mesh_ewald_composite_energy_components_v1,
                  reserved) == 112);

static_assert(sizeof(bg_particle_mesh_ewald_composite_force_soa_v1) == 88);
static_assert(
    alignof(bg_particle_mesh_ewald_composite_force_soa_v1) ==
    alignof(uint64_t));
static_assert(offsetof(
                  bg_particle_mesh_ewald_composite_force_soa_v1,
                  struct_size) == 0);
static_assert(offsetof(
                  bg_particle_mesh_ewald_composite_force_soa_v1,
                  abi_version) == 4);
static_assert(offsetof(
                  bg_particle_mesh_ewald_composite_force_soa_v1,
                  atom_capacity) == 8);
static_assert(offsetof(
                  bg_particle_mesh_ewald_composite_force_soa_v1,
                  atom_count) == 16);
static_assert(offsetof(
                  bg_particle_mesh_ewald_composite_force_soa_v1,
                  unit_system) == 24);
static_assert(offsetof(
                  bg_particle_mesh_ewald_composite_force_soa_v1,
                  reserved0) == 28);
static_assert(offsetof(
                  bg_particle_mesh_ewald_composite_force_soa_v1,
                  x_kcal_per_mol_angstrom) == 32);
static_assert(offsetof(
                  bg_particle_mesh_ewald_composite_force_soa_v1,
                  y_kcal_per_mol_angstrom) == 40);
static_assert(offsetof(
                  bg_particle_mesh_ewald_composite_force_soa_v1,
                  z_kcal_per_mol_angstrom) == 48);
static_assert(offsetof(
                  bg_particle_mesh_ewald_composite_force_soa_v1,
                  reserved) == 56);

static_assert(noexcept(bg_particle_mesh_ewald_composite_abi_version()));
static_assert(noexcept(bg_particle_mesh_ewald_composite_abi_version_major()));
static_assert(noexcept(bg_particle_mesh_ewald_composite_abi_version_minor()));
static_assert(noexcept(bg_particle_mesh_ewald_composite_abi_version_string()));
static_assert(noexcept(
    bg_particle_mesh_ewald_composite_energy_components_v1_init(
        static_cast<
            bg_particle_mesh_ewald_composite_energy_components_v1 *>(
            nullptr))));
static_assert(noexcept(bg_particle_mesh_ewald_composite_force_soa_v1_init(
    static_cast<bg_particle_mesh_ewald_composite_force_soa_v1 *>(nullptr))));
static_assert(noexcept(bg_particle_mesh_ewald_composite_v1_profile_id()));
static_assert(noexcept(bg_context_evaluate_particle_mesh_ewald_composite_v1(
    nullptr,
    nullptr,
    nullptr,
    nullptr,
    nullptr,
    nullptr,
    nullptr,
    nullptr)));
