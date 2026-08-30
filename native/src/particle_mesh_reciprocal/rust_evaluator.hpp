#ifndef BETELGEUZE_NATIVE_PARTICLE_MESH_RECIPROCAL_RUST_EVALUATOR_HPP
#define BETELGEUZE_NATIVE_PARTICLE_MESH_RECIPROCAL_RUST_EVALUATOR_HPP

#include "cpp_evaluator.hpp"
#include "rust_provider.h"

#include <vector>

namespace betelgeuze::native::particle_mesh_reciprocal::rust_cpu {

struct ProviderForceScratch final {
    std::vector<double> x;
    std::vector<double> y;
    std::vector<double> z;
    bg_rust_particle_mesh_reciprocal_workspace_v1 reciprocal_workspace{};
    bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_v1
        neutrality_sort_scratch{};

    ProviderForceScratch() noexcept = default;
    ~ProviderForceScratch() noexcept;
    ProviderForceScratch(const ProviderForceScratch &) = delete;
    ProviderForceScratch &operator=(const ProviderForceScratch &) = delete;
    ProviderForceScratch(ProviderForceScratch &&) = delete;
    ProviderForceScratch &operator=(ProviderForceScratch &&) = delete;
};

struct ProviderForceSourceResult final {
    double reciprocal_space_kcal_per_mol = 0.0;
};

[[nodiscard]] bg_status evaluate(
    const bg_system &system,
    const bg_particle_mesh_reciprocal_model_v1 &model,
    bool compute_forces,
    Evaluation *out_evaluation,
    Error *out_error);

[[nodiscard]] bg_status evaluate_reusing_force_storage(
    const bg_system &system,
    const bg_particle_mesh_reciprocal_model_v1 &model,
    bool compute_forces,
    ProviderForceScratch *provider_force_scratch,
    Evaluation *out_evaluation,
    Error *out_error);

[[nodiscard]] bg_status evaluate_reusing_provider_force_storage(
    const bg_system &system,
    const bg_particle_mesh_reciprocal_model_v1 &model,
    ProviderForceScratch *provider_force_scratch,
    ProviderForceSourceResult *out_result,
    Error *out_error);

}  // namespace betelgeuze::native::particle_mesh_reciprocal::rust_cpu

#endif  // BETELGEUZE_NATIVE_PARTICLE_MESH_RECIPROCAL_RUST_EVALUATOR_HPP
