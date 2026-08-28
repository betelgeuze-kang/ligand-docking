#ifndef BETELGEUZE_NATIVE_PARTICLE_MESH_RECIPROCAL_CPP_EVALUATOR_HPP
#define BETELGEUZE_NATIVE_PARTICLE_MESH_RECIPROCAL_CPP_EVALUATOR_HPP

#include "model.hpp"

#include <array>
#include <string>
#include <vector>

struct bg_system;

namespace betelgeuze::native::particle_mesh_reciprocal {

struct Evaluation final {
    double reciprocal_space_kcal_per_mol = 0.0;
    std::vector<std::array<double, 3>> forces;
};

struct Error final {
    bg_particle_mesh_reciprocal_error_code code =
        BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONE;
    std::string detail;
};

namespace cpp_cpu {

[[nodiscard]] bg_status evaluate(
    const bg_system &system,
    const bg_particle_mesh_reciprocal_model_v1 &model,
    bool compute_forces,
    Evaluation *out_evaluation,
    Error *out_error);

}  // namespace cpp_cpu
}  // namespace betelgeuze::native::particle_mesh_reciprocal

#endif  // BETELGEUZE_NATIVE_PARTICLE_MESH_RECIPROCAL_CPP_EVALUATOR_HPP
