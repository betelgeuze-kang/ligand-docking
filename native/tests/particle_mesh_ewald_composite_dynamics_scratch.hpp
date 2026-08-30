#ifndef BETELGEUZE_NATIVE_TESTS_PARTICLE_MESH_EWALD_COMPOSITE_DYNAMICS_SCRATCH_HPP
#define BETELGEUZE_NATIVE_TESTS_PARTICLE_MESH_EWALD_COMPOSITE_DYNAMICS_SCRATCH_HPP

#include "betelgeuze/particle_mesh_ewald_composite_dynamics.h"

#include "../src/particle_mesh_reciprocal/rust_provider.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace betelgeuze::native::tests {

struct ParticleMeshEwaldCompositeForceScratchSnapshot final {
    std::array<const double *, 3> addresses{};
    std::array<std::size_t, 3> sizes{};
    std::array<std::size_t, 3> capacities{};
};

struct ParticleMeshEwaldCompositeShortParentForceScratchSnapshot final {
    std::array<const double *, 3> addresses{};
    std::array<std::size_t, 3> sizes{};
    std::array<std::size_t, 3> capacities{};
    uint8_t rust_cpu_forcefield_validated = UINT8_C(0);
};

struct ParticleMeshEwaldCompositeDirectParentForceScratchSnapshot final {
    const std::array<double, 3> *address = nullptr;
    std::size_t size = 0U;
    std::size_t capacity = 0U;
};

struct ParticleMeshEwaldCompositeReciprocalParentForceScratchSnapshot final {
    const std::array<double, 3> *address = nullptr;
    std::size_t size = 0U;
    std::size_t capacity = 0U;
};

struct ParticleMeshEwaldCompositeRustReciprocalProviderForceScratchSnapshot final {
    std::array<const double *, 3> addresses{};
    std::array<std::size_t, 3> sizes{};
    std::array<std::size_t, 3> capacities{};
    std::uint32_t workspace_struct_size = 0U;
    std::uint32_t workspace_abi_version = 0U;
    std::uint32_t workspace_state =
        BG_RUST_PARTICLE_MESH_RECIPROCAL_WORKSPACE_STATE_EMPTY;
    std::uint32_t workspace_reserved0 = 0U;
    const void *workspace_storage = nullptr;
    std::size_t workspace_length = 0U;
    std::size_t workspace_capacity = 0U;
    std::array<std::uint64_t, 4> workspace_reserved{};
    std::uint32_t neutrality_sort_struct_size = 0U;
    std::uint32_t neutrality_sort_abi_version = 0U;
    std::uint32_t neutrality_sort_state =
        BG_RUST_PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_STATE_EMPTY;
    std::uint32_t neutrality_sort_reserved0 = 0U;
    const void *neutrality_sort_storage = nullptr;
    std::size_t neutrality_sort_length = 0U;
    std::size_t neutrality_sort_capacity = 0U;
    std::array<std::uint64_t, 4> neutrality_sort_reserved{};
};

struct ParticleMeshEwaldCompositeShortSystemScratchSnapshot final {
    bg_unit_system unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
    std::array<const double *, 8> addresses{};
    std::array<std::size_t, 8> sizes{};
    std::array<std::size_t, 8> capacities{};
};

void reserve_particle_mesh_ewald_composite_force_scratch(
    bg_particle_mesh_ewald_composite_simulation_v1 *simulation,
    std::size_t capacity);

void reserve_particle_mesh_ewald_composite_short_parent_force_scratch(
    bg_particle_mesh_ewald_composite_simulation_v1 *simulation,
    std::size_t capacity);

void reserve_particle_mesh_ewald_composite_direct_parent_force_scratch(
    bg_particle_mesh_ewald_composite_simulation_v1 *simulation,
    std::size_t capacity);

void reserve_particle_mesh_ewald_composite_reciprocal_parent_force_scratch(
    bg_particle_mesh_ewald_composite_simulation_v1 *simulation,
    std::size_t capacity);

void reserve_particle_mesh_ewald_composite_rust_reciprocal_provider_force_scratch(
    bg_particle_mesh_ewald_composite_simulation_v1 *simulation,
    std::size_t capacity);

void shrink_particle_mesh_ewald_composite_rust_reciprocal_provider_neutrality_sort_scratch_for_test(
    bg_particle_mesh_ewald_composite_simulation_v1 *simulation,
    std::size_t logical_length);

[[nodiscard]] ParticleMeshEwaldCompositeForceScratchSnapshot
particle_mesh_ewald_composite_force_scratch_snapshot(
    const bg_particle_mesh_ewald_composite_simulation_v1 *simulation);

[[nodiscard]] ParticleMeshEwaldCompositeShortParentForceScratchSnapshot
particle_mesh_ewald_composite_short_parent_force_scratch_snapshot(
    const bg_particle_mesh_ewald_composite_simulation_v1 *simulation);

[[nodiscard]] ParticleMeshEwaldCompositeDirectParentForceScratchSnapshot
particle_mesh_ewald_composite_direct_parent_force_scratch_snapshot(
    const bg_particle_mesh_ewald_composite_simulation_v1 *simulation);

[[nodiscard]] ParticleMeshEwaldCompositeReciprocalParentForceScratchSnapshot
particle_mesh_ewald_composite_reciprocal_parent_force_scratch_snapshot(
    const bg_particle_mesh_ewald_composite_simulation_v1 *simulation);

[[nodiscard]]
ParticleMeshEwaldCompositeRustReciprocalProviderForceScratchSnapshot
particle_mesh_ewald_composite_rust_reciprocal_provider_force_scratch_snapshot(
    const bg_particle_mesh_ewald_composite_simulation_v1 *simulation);

[[nodiscard]] ParticleMeshEwaldCompositeShortSystemScratchSnapshot
particle_mesh_ewald_composite_short_system_scratch_snapshot(
    const bg_particle_mesh_ewald_composite_simulation_v1 *simulation);

void set_particle_mesh_ewald_composite_short_system_scratch_unit_for_test(
    bg_particle_mesh_ewald_composite_simulation_v1 *simulation,
    bg_unit_system unit_system);

void truncate_particle_mesh_ewald_composite_short_system_scratch_for_test(
    bg_particle_mesh_ewald_composite_simulation_v1 *simulation);

void set_particle_mesh_ewald_composite_short_system_scratch_charge_for_test(
    bg_particle_mesh_ewald_composite_simulation_v1 *simulation,
    double charge);

}  // namespace betelgeuze::native::tests

#endif  // BETELGEUZE_NATIVE_TESTS_PARTICLE_MESH_EWALD_COMPOSITE_DYNAMICS_SCRATCH_HPP
