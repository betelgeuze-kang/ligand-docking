#ifndef BETELGEUZE_NATIVE_HIP_SAFE_EVALUATOR_HPP
#define BETELGEUZE_NATIVE_HIP_SAFE_EVALUATOR_HPP

#include "../cpu/evaluator.hpp"

#include <cstdint>

namespace betelgeuze::native::hip_safe {

bool is_available(int32_t device_ordinal) noexcept;

bg_status evaluate(
    int32_t device_ordinal,
    const bg_system &system,
    const bg_forcefield &forcefield,
    bool compute_forces,
    cpu::Evaluation *out_evaluation);

}  // namespace betelgeuze::native::hip_safe

#endif  // BETELGEUZE_NATIVE_HIP_SAFE_EVALUATOR_HPP
