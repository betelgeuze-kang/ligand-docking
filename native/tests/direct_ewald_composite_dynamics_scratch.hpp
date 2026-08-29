#ifndef BETELGEUZE_NATIVE_TESTS_DIRECT_EWALD_COMPOSITE_DYNAMICS_SCRATCH_HPP
#define BETELGEUZE_NATIVE_TESTS_DIRECT_EWALD_COMPOSITE_DYNAMICS_SCRATCH_HPP

#include "betelgeuze/direct_ewald_composite_dynamics.h"

#include <array>
#include <cstddef>
#include <cstdint>

namespace betelgeuze::native::tests {

struct DirectEwaldCompositeForceScratchSnapshot final {
    std::array<const double *, 3> addresses{};
    std::array<std::size_t, 3> sizes{};
    std::array<std::size_t, 3> capacities{};
};

struct DirectEwaldCompositeShortParentForceScratchSnapshot final {
    std::array<const double *, 3> addresses{};
    std::array<std::size_t, 3> sizes{};
    std::array<std::size_t, 3> capacities{};
    uint8_t rust_cpu_forcefield_validated = UINT8_C(0);
};

struct DirectEwaldCompositeEwaldParentForceScratchSnapshot final {
    const std::array<double, 3> *address = nullptr;
    std::size_t size = 0U;
    std::size_t capacity = 0U;
};

struct DirectEwaldCompositeShortSystemScratchSnapshot final {
    bg_unit_system unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
    std::array<const double *, 8> addresses{};
    std::array<std::size_t, 8> sizes{};
    std::array<std::size_t, 8> capacities{};
};

void reserve_direct_ewald_composite_force_scratch(
    bg_direct_ewald_composite_simulation_v1 *simulation,
    std::size_t capacity);

void reserve_direct_ewald_composite_short_parent_force_scratch(
    bg_direct_ewald_composite_simulation_v1 *simulation,
    std::size_t capacity);

void reserve_direct_ewald_composite_ewald_parent_force_scratch(
    bg_direct_ewald_composite_simulation_v1 *simulation,
    std::size_t capacity);

[[nodiscard]] DirectEwaldCompositeForceScratchSnapshot
direct_ewald_composite_force_scratch_snapshot(
    const bg_direct_ewald_composite_simulation_v1 *simulation);

[[nodiscard]] DirectEwaldCompositeShortParentForceScratchSnapshot
direct_ewald_composite_short_parent_force_scratch_snapshot(
    const bg_direct_ewald_composite_simulation_v1 *simulation);

[[nodiscard]] DirectEwaldCompositeEwaldParentForceScratchSnapshot
direct_ewald_composite_ewald_parent_force_scratch_snapshot(
    const bg_direct_ewald_composite_simulation_v1 *simulation);

[[nodiscard]] DirectEwaldCompositeShortSystemScratchSnapshot
direct_ewald_composite_short_system_scratch_snapshot(
    const bg_direct_ewald_composite_simulation_v1 *simulation);

void set_direct_ewald_composite_short_system_scratch_unit_for_test(
    bg_direct_ewald_composite_simulation_v1 *simulation,
    bg_unit_system unit_system);

void truncate_direct_ewald_composite_short_system_scratch_for_test(
    bg_direct_ewald_composite_simulation_v1 *simulation);

void set_direct_ewald_composite_short_system_scratch_charge_for_test(
    bg_direct_ewald_composite_simulation_v1 *simulation,
    double charge);

}  // namespace betelgeuze::native::tests

#endif  // BETELGEUZE_NATIVE_TESTS_DIRECT_EWALD_COMPOSITE_DYNAMICS_SCRATCH_HPP
