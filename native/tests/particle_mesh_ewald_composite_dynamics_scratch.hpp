#ifndef BETELGEUZE_NATIVE_TESTS_PARTICLE_MESH_EWALD_COMPOSITE_DYNAMICS_SCRATCH_HPP
#define BETELGEUZE_NATIVE_TESTS_PARTICLE_MESH_EWALD_COMPOSITE_DYNAMICS_SCRATCH_HPP

#include "betelgeuze/particle_mesh_ewald_composite_dynamics.h"

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

[[nodiscard]] ParticleMeshEwaldCompositeForceScratchSnapshot
particle_mesh_ewald_composite_force_scratch_snapshot(
    const bg_particle_mesh_ewald_composite_simulation_v1 *simulation);

[[nodiscard]] ParticleMeshEwaldCompositeShortParentForceScratchSnapshot
particle_mesh_ewald_composite_short_parent_force_scratch_snapshot(
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
