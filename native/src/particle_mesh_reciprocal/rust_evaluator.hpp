#ifndef BETELGEUZE_NATIVE_PARTICLE_MESH_RECIPROCAL_RUST_EVALUATOR_HPP
#define BETELGEUZE_NATIVE_PARTICLE_MESH_RECIPROCAL_RUST_EVALUATOR_HPP

#include "cpp_evaluator.hpp"

namespace betelgeuze::native::particle_mesh_reciprocal::rust_cpu {

[[nodiscard]] bg_status evaluate(
    const bg_system &system,
    const bg_particle_mesh_reciprocal_model_v1 &model,
    bool compute_forces,
    Evaluation *out_evaluation,
    Error *out_error);

}  // namespace betelgeuze::native::particle_mesh_reciprocal::rust_cpu

#endif  // BETELGEUZE_NATIVE_PARTICLE_MESH_RECIPROCAL_RUST_EVALUATOR_HPP
