#ifndef BETELGEUZE_NATIVE_RUST_EVALUATOR_HPP
#define BETELGEUZE_NATIVE_RUST_EVALUATOR_HPP

#include "../cpu/evaluator.hpp"

namespace betelgeuze::native::rust_cpu {

bg_status evaluate(
    const bg_system &system,
    const bg_forcefield &forcefield,
    bool compute_forces,
    cpu::Evaluation *out_evaluation);

bg_status evaluate_reusing_force_storage(
    const bg_system &system,
    const bg_forcefield &forcefield,
    bool compute_forces,
    uint8_t *inout_forcefield_validated,
    cpu::Evaluation *out_evaluation);

bg_status evaluate_with_neighbor_pairs(
    const bg_system &system,
    const bg_forcefield &forcefield,
    const std::vector<cpu::NeighborPair> &neighbor_pairs,
    bool compute_forces,
    cpu::Evaluation *out_evaluation);

bg_status evaluate_with_neighbor_pairs_reusing_force_storage(
    const bg_system &system,
    const bg_forcefield &forcefield,
    const std::vector<cpu::NeighborPair> &neighbor_pairs,
    bool compute_forces,
    uint8_t *inout_forcefield_validated,
    cpu::Evaluation *out_evaluation);

}  // namespace betelgeuze::native::rust_cpu

#endif  // BETELGEUZE_NATIVE_RUST_EVALUATOR_HPP
