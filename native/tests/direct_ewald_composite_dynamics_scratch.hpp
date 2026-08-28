#ifndef BETELGEUZE_NATIVE_TESTS_DIRECT_EWALD_COMPOSITE_DYNAMICS_SCRATCH_HPP
#define BETELGEUZE_NATIVE_TESTS_DIRECT_EWALD_COMPOSITE_DYNAMICS_SCRATCH_HPP

#include "betelgeuze/direct_ewald_composite_dynamics.h"

#include <array>
#include <cstddef>

namespace betelgeuze::native::tests {

struct DirectEwaldCompositeForceScratchSnapshot final {
    std::array<const double *, 3> addresses{};
    std::array<std::size_t, 3> sizes{};
    std::array<std::size_t, 3> capacities{};
};

void reserve_direct_ewald_composite_force_scratch(
    bg_direct_ewald_composite_simulation_v1 *simulation,
    std::size_t capacity);

[[nodiscard]] DirectEwaldCompositeForceScratchSnapshot
direct_ewald_composite_force_scratch_snapshot(
    const bg_direct_ewald_composite_simulation_v1 *simulation);

}  // namespace betelgeuze::native::tests

#endif  // BETELGEUZE_NATIVE_TESTS_DIRECT_EWALD_COMPOSITE_DYNAMICS_SCRATCH_HPP
