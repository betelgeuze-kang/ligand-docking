#ifndef BETELGEUZE_NATIVE_COMPOSITE_EVALUATOR_HPP
#define BETELGEUZE_NATIVE_COMPOSITE_EVALUATOR_HPP

#include "../cpu/evaluator.hpp"
#include "../ewald/cpp_evaluator.hpp"

#include <array>
#include <cstdint>
#include <vector>

struct bg_context;
struct bg_forcefield;
struct bg_system;

namespace betelgeuze::native::composite {

struct Energy final {
    double short_harmonic_bond = 0.0;
    double short_harmonic_angle = 0.0;
    double short_periodic_torsion = 0.0;
    double short_lennard_jones = 0.0;
    double short_coulomb = 0.0;
    double short_total = 0.0;
    double ewald_real_space = 0.0;
    double ewald_reciprocal_space = 0.0;
    double ewald_self = 0.0;
    double ewald_pair_correction = 0.0;
    double ewald_total = 0.0;
    double total = 0.0;
};

struct Evaluation final {
    Energy energy;
    std::vector<std::array<double, 3>> forces;
};

[[nodiscard]] bg_status validate_static_compatibility(
    const bg_system &system,
    const bg_forcefield &forcefield,
    const bg_direct_ewald_model_v1 &model);

[[nodiscard]] bg_status validate_handle_compatibility(
    const bg_context &context,
    const bg_system &system,
    const bg_forcefield &forcefield,
    const bg_direct_ewald_model_v1 &model);

/*
 * The caller must first establish validate_handle_compatibility(). The three
 * private scratch/cache pointers must be null for the stateless path or
 * non-null for the stateful path. The stateful force output must be non-null
 * exactly for a force-producing stateful call. A non-null short-system
 * scratch must be independent, deep-owned, shape/unit matched, and contain
 * exact +0.0 charges; only its positions are refreshed. Force-producing
 * stateful calls reuse the short parent's Evaluation storage and write the
 * final force directly to the supplied SoA Evaluation after all parent force
 * shapes and values have been validated. Stateless force-producing calls
 * retain the composite AoS force result. Force-free calls leave the private
 * force storage and Rust validation cache untouched. Failed calls need not
 * restore private derived scratch/cache contents.
 */
[[nodiscard]] bg_status evaluate_prevalidated(
    const bg_context &context,
    const bg_system &system,
    const bg_forcefield &forcefield,
    const bg_direct_ewald_model_v1 &model,
    bg_system *short_system_scratch,
    cpu::Evaluation *short_parent_evaluation_scratch,
    uint8_t *inout_rust_cpu_forcefield_validated,
    cpu::Evaluation *stateful_force_output,
    bool compute_forces,
    Evaluation *out_evaluation,
    ewald::Error *out_error);

}  // namespace betelgeuze::native::composite

#endif  // BETELGEUZE_NATIVE_COMPOSITE_EVALUATOR_HPP
