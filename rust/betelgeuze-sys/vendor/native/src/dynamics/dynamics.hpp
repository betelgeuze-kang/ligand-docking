#ifndef BETELGEUZE_NATIVE_DYNAMICS_DYNAMICS_HPP
#define BETELGEUZE_NATIVE_DYNAMICS_DYNAMICS_HPP

#include "../cpu/evaluator.hpp"
#include "../internal.hpp"

#include <array>

namespace betelgeuze::native::dynamics {

inline constexpr double kAccelerationConversion = 4.184e-4;
inline constexpr double kGasConstantKcalPerMolKelvin =
    0.0019872042586408316;

bg_status evaluate(
    const bg_context &context,
    bg_simulation *simulation,
    const bg_system &system,
    bool compute_forces,
    cpu::Evaluation *out_evaluation);

[[nodiscard]] std::array<uint8_t, 32> compute_static_fingerprint(
    const bg_simulation &simulation) noexcept;

bg_status initialize_constraints(bg_simulation *simulation);
bg_status validate_constraint_state(const bg_simulation &simulation) noexcept;
bg_status validate_constraint_independence(const bg_simulation &simulation);

bg_status minimize(
    const bg_context &context,
    const bg_simulation &source,
    const bg_minimizer_options_v1 &options,
    bg_simulation *work,
    bg_minimization_report_v1 *out_report);

bg_status integrate(
    const bg_context &context,
    const bg_simulation &source,
    uint64_t step_count,
    bg_simulation *work,
    bg_dynamics_report_v1 *out_report);

}  // namespace betelgeuze::native::dynamics

#endif  // BETELGEUZE_NATIVE_DYNAMICS_DYNAMICS_HPP
