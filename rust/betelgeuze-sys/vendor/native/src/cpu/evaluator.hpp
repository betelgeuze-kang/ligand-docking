#ifndef BETELGEUZE_NATIVE_CPU_EVALUATOR_HPP
#define BETELGEUZE_NATIVE_CPU_EVALUATOR_HPP

#include "betelgeuze/engine.h"

#include <vector>

namespace betelgeuze::native::cpu {

struct Evaluation final {
    bg_energy_components_v1 energy{};
    std::vector<double> force_x;
    std::vector<double> force_y;
    std::vector<double> force_z;
};

bg_status evaluate(
    const bg_system &system,
    const bg_forcefield &forcefield,
    bool compute_forces,
    Evaluation *out_evaluation);

}  // namespace betelgeuze::native::cpu

#endif  // BETELGEUZE_NATIVE_CPU_EVALUATOR_HPP
