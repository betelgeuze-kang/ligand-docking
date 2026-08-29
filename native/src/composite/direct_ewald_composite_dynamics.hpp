#ifndef BETELGEUZE_NATIVE_COMPOSITE_DIRECT_EWALD_COMPOSITE_DYNAMICS_HPP
#define BETELGEUZE_NATIVE_COMPOSITE_DIRECT_EWALD_COMPOSITE_DYNAMICS_HPP

#include "betelgeuze/direct_ewald_composite_dynamics.h"

#include "../dynamics/dynamics.hpp"
#include "../ewald/model.hpp"

#include <array>
#include <cstdint>
#include <memory>

struct bg_direct_ewald_composite_simulation_v1 final {
    std::unique_ptr<bg_simulation> simulation;
    bg_direct_ewald_model_v1 model;
    bg_system short_system_scratch;
    std::array<uint8_t, 32> static_fingerprint{};
};

namespace betelgeuze::native::composite::dynamics {

/* The owner must contain a non-null canonical Engine simulation. */
[[nodiscard]] std::array<uint8_t, 32> compute_static_fingerprint(
    const bg_direct_ewald_composite_simulation_v1 &owner) noexcept;

/* Shared by runtime and checkpoint entry points before any state mutation. */
[[nodiscard]] bg_status validate_owner_invariant(
    const bg_direct_ewald_composite_simulation_v1 &owner);

}  // namespace betelgeuze::native::composite::dynamics

#endif  // BETELGEUZE_NATIVE_COMPOSITE_DIRECT_EWALD_COMPOSITE_DYNAMICS_HPP
