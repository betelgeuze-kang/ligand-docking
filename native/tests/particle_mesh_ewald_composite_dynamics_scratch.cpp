#include "particle_mesh_ewald_composite_dynamics_scratch.hpp"

#include "../src/composite/particle_mesh_ewald_composite_dynamics.hpp"

#include <cassert>
#include <cstddef>

namespace betelgeuze::native::tests {

void reserve_particle_mesh_ewald_composite_force_scratch(
    bg_particle_mesh_ewald_composite_simulation_v1 *simulation,
    std::size_t capacity) {
    assert(simulation != nullptr);
    assert(simulation->simulation != nullptr);
    bg_simulation::ParticleVectorScratch &scratch =
        simulation->simulation->force_evaluation_scratch;
    scratch.x.reserve(capacity);
    scratch.y.reserve(capacity);
    scratch.z.reserve(capacity);
}

ParticleMeshEwaldCompositeForceScratchSnapshot
particle_mesh_ewald_composite_force_scratch_snapshot(
    const bg_particle_mesh_ewald_composite_simulation_v1 *simulation) {
    assert(simulation != nullptr);
    assert(simulation->simulation != nullptr);
    const bg_simulation::ParticleVectorScratch &scratch =
        simulation->simulation->force_evaluation_scratch;
    ParticleMeshEwaldCompositeForceScratchSnapshot snapshot;
    snapshot.addresses = {
        scratch.x.data(),
        scratch.y.data(),
        scratch.z.data(),
    };
    snapshot.sizes = {
        scratch.x.size(),
        scratch.y.size(),
        scratch.z.size(),
    };
    snapshot.capacities = {
        scratch.x.capacity(),
        scratch.y.capacity(),
        scratch.z.capacity(),
    };
    return snapshot;
}

}  // namespace betelgeuze::native::tests
