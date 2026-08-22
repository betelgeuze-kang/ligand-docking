#ifndef BETELGEUZE_NATIVE_CPU_EVALUATOR_HPP
#define BETELGEUZE_NATIVE_CPU_EVALUATOR_HPP

#include "neighbor_pair.hpp"

#include "betelgeuze/engine.h"

#include <cstddef>
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

bg_status evaluate_reusing_force_storage(
    const bg_system &system,
    const bg_forcefield &forcefield,
    bool compute_forces,
    Evaluation *out_evaluation);

bg_status build_periodic_neighbor_pairs(
    const bg_system &system,
    const bg_forcefield &forcefield,
    double search_radius,
    std::vector<NeighborPair> *out_pairs);

bg_status build_periodic_neighbor_pairs_reusing_scratch(
    const bg_system &system,
    const bg_forcefield &forcefield,
    double search_radius,
    NeighborBuildScratch *scratch,
    std::vector<NeighborPair> *out_pairs);

bg_status evaluate_with_neighbor_pairs(
    const bg_system &system,
    const bg_forcefield &forcefield,
    const std::vector<NeighborPair> &neighbor_pairs,
    bool compute_forces,
    Evaluation *out_evaluation);

bg_status evaluate_with_neighbor_pairs_reusing_force_storage(
    const bg_system &system,
    const bg_forcefield &forcefield,
    const std::vector<NeighborPair> &neighbor_pairs,
    bool compute_forces,
    Evaluation *out_evaluation);

}  // namespace betelgeuze::native::cpu

#endif  // BETELGEUZE_NATIVE_CPU_EVALUATOR_HPP
