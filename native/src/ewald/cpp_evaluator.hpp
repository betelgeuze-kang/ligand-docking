#ifndef BETELGEUZE_NATIVE_EWALD_CPP_EVALUATOR_HPP
#define BETELGEUZE_NATIVE_EWALD_CPP_EVALUATOR_HPP

#include "model.hpp"

#include <array>
#include <string>
#include <vector>

struct bg_system;

namespace betelgeuze::native::ewald {

struct Energy final {
    double real_space = 0.0;
    double reciprocal_space = 0.0;
    double self = 0.0;
    double pair_correction = 0.0;

    [[nodiscard]] double total() const noexcept {
        return real_space + reciprocal_space + self + pair_correction;
    }
};

struct Evaluation final {
    Energy energy;
    std::vector<std::array<double, 3>> forces;
};

struct Error final {
    bg_direct_ewald_error_code code = BG_DIRECT_EWALD_ERROR_NONE;
    std::string detail;
};

namespace cpp_cpu {

[[nodiscard]] bg_status evaluate(
    const bg_system &system,
    const bg_direct_ewald_model_v1 &model,
    bool compute_forces,
    Evaluation *out_evaluation,
    Error *out_error);

[[nodiscard]] bg_status evaluate_reusing_force_storage(
    const bg_system &system,
    const bg_direct_ewald_model_v1 &model,
    bool compute_forces,
    Evaluation *out_evaluation,
    Error *out_error);

}  // namespace cpp_cpu
}  // namespace betelgeuze::native::ewald

#endif
