#ifndef BETELGEUZE_NATIVE_EWALD_RUST_EVALUATOR_HPP
#define BETELGEUZE_NATIVE_EWALD_RUST_EVALUATOR_HPP

#include "cpp_evaluator.hpp"

namespace betelgeuze::native::ewald::rust_cpu {

[[nodiscard]] bg_status evaluate(
    const bg_system &system,
    const bg_direct_ewald_model_v1 &model,
    bool compute_forces,
    Evaluation *out_evaluation,
    Error *out_error);

}  // namespace betelgeuze::native::ewald::rust_cpu

#endif  // BETELGEUZE_NATIVE_EWALD_RUST_EVALUATOR_HPP
