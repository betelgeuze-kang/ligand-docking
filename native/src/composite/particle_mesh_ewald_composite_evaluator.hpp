#ifndef BETELGEUZE_NATIVE_PARTICLE_MESH_EWALD_COMPOSITE_EVALUATOR_HPP
#define BETELGEUZE_NATIVE_PARTICLE_MESH_EWALD_COMPOSITE_EVALUATOR_HPP

#include "betelgeuze/particle_mesh_ewald_composite.h"

#include <array>
#include <vector>

namespace betelgeuze::native::particle_mesh_ewald_composite {

struct Evaluation final {
    double short_harmonic_bond = 0.0;
    double short_harmonic_angle = 0.0;
    double short_periodic_torsion = 0.0;
    double short_lennard_jones = 0.0;
    double short_coulomb = 0.0;
    double short_total = 0.0;
    double pme_real_space = 0.0;
    double pme_reciprocal_space = 0.0;
    double pme_self = 0.0;
    double pme_pair_correction = 0.0;
    double pme_total = 0.0;
    double total = 0.0;
    std::vector<std::array<double, 3>> forces;
};

[[nodiscard]] bg_status validate_static_compatibility(
    const bg_system &system,
    const bg_forcefield &forcefield,
    const bg_direct_ewald_model_v1 &direct_model,
    const bg_particle_mesh_reciprocal_model_v1 &reciprocal_model);

[[nodiscard]] bg_status evaluate_prevalidated(
    bg_backend lane,
    const bg_system &system,
    const bg_forcefield &forcefield,
    const bg_direct_ewald_model_v1 &direct_model,
    const bg_particle_mesh_reciprocal_model_v1 &reciprocal_model,
    bool compute_forces,
    Evaluation *out_evaluation,
    bg_direct_ewald_error_v1 *out_error);

}  // namespace betelgeuze::native::particle_mesh_ewald_composite

#endif
