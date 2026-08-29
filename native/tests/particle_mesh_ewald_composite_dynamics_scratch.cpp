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

void reserve_particle_mesh_ewald_composite_short_parent_force_scratch(
    bg_particle_mesh_ewald_composite_simulation_v1 *simulation,
    std::size_t capacity) {
    assert(simulation != nullptr);
    cpu::Evaluation &scratch =
        simulation->short_parent_evaluation_scratch;
    scratch.force_x.reserve(capacity);
    scratch.force_y.reserve(capacity);
    scratch.force_z.reserve(capacity);
}

void reserve_particle_mesh_ewald_composite_direct_parent_force_scratch(
    bg_particle_mesh_ewald_composite_simulation_v1 *simulation,
    std::size_t capacity) {
    assert(simulation != nullptr);
    simulation->direct_parent_evaluation_scratch.forces.reserve(capacity);
}

void reserve_particle_mesh_ewald_composite_reciprocal_parent_force_scratch(
    bg_particle_mesh_ewald_composite_simulation_v1 *simulation,
    std::size_t capacity) {
    assert(simulation != nullptr);
    simulation->reciprocal_parent_evaluation_scratch.forces.reserve(capacity);
}

void reserve_particle_mesh_ewald_composite_rust_reciprocal_provider_force_scratch(
    bg_particle_mesh_ewald_composite_simulation_v1 *simulation,
    std::size_t capacity) {
    assert(simulation != nullptr);
    auto &scratch = simulation->rust_reciprocal_provider_force_scratch;
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

ParticleMeshEwaldCompositeShortParentForceScratchSnapshot
particle_mesh_ewald_composite_short_parent_force_scratch_snapshot(
    const bg_particle_mesh_ewald_composite_simulation_v1 *simulation) {
    assert(simulation != nullptr);
    assert(simulation->simulation != nullptr);
    const cpu::Evaluation &scratch =
        simulation->short_parent_evaluation_scratch;
    ParticleMeshEwaldCompositeShortParentForceScratchSnapshot snapshot;
    snapshot.addresses = {
        scratch.force_x.data(),
        scratch.force_y.data(),
        scratch.force_z.data(),
    };
    snapshot.sizes = {
        scratch.force_x.size(),
        scratch.force_y.size(),
        scratch.force_z.size(),
    };
    snapshot.capacities = {
        scratch.force_x.capacity(),
        scratch.force_y.capacity(),
        scratch.force_z.capacity(),
    };
    snapshot.rust_cpu_forcefield_validated =
        simulation->simulation->rust_cpu_forcefield_validated;
    return snapshot;
}

ParticleMeshEwaldCompositeDirectParentForceScratchSnapshot
particle_mesh_ewald_composite_direct_parent_force_scratch_snapshot(
    const bg_particle_mesh_ewald_composite_simulation_v1 *simulation) {
    assert(simulation != nullptr);
    const std::vector<std::array<double, 3>> &scratch =
        simulation->direct_parent_evaluation_scratch.forces;
    ParticleMeshEwaldCompositeDirectParentForceScratchSnapshot snapshot;
    snapshot.address = scratch.data();
    snapshot.size = scratch.size();
    snapshot.capacity = scratch.capacity();
    return snapshot;
}

ParticleMeshEwaldCompositeReciprocalParentForceScratchSnapshot
particle_mesh_ewald_composite_reciprocal_parent_force_scratch_snapshot(
    const bg_particle_mesh_ewald_composite_simulation_v1 *simulation) {
    assert(simulation != nullptr);
    const std::vector<std::array<double, 3>> &scratch =
        simulation->reciprocal_parent_evaluation_scratch.forces;
    ParticleMeshEwaldCompositeReciprocalParentForceScratchSnapshot snapshot;
    snapshot.address = scratch.data();
    snapshot.size = scratch.size();
    snapshot.capacity = scratch.capacity();
    return snapshot;
}

ParticleMeshEwaldCompositeRustReciprocalProviderForceScratchSnapshot
particle_mesh_ewald_composite_rust_reciprocal_provider_force_scratch_snapshot(
    const bg_particle_mesh_ewald_composite_simulation_v1 *simulation) {
    assert(simulation != nullptr);
    const auto &scratch =
        simulation->rust_reciprocal_provider_force_scratch;
    ParticleMeshEwaldCompositeRustReciprocalProviderForceScratchSnapshot
        snapshot;
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

ParticleMeshEwaldCompositeShortSystemScratchSnapshot
particle_mesh_ewald_composite_short_system_scratch_snapshot(
    const bg_particle_mesh_ewald_composite_simulation_v1 *simulation) {
    assert(simulation != nullptr);
    const bg_system &scratch = simulation->short_system_scratch;
    ParticleMeshEwaldCompositeShortSystemScratchSnapshot snapshot;
    snapshot.unit_system = scratch.unit_system;
    snapshot.addresses = {
        scratch.position_x.data(),
        scratch.position_y.data(),
        scratch.position_z.data(),
        scratch.velocity_x.data(),
        scratch.velocity_y.data(),
        scratch.velocity_z.data(),
        scratch.mass.data(),
        scratch.charge.data(),
    };
    snapshot.sizes = {
        scratch.position_x.size(),
        scratch.position_y.size(),
        scratch.position_z.size(),
        scratch.velocity_x.size(),
        scratch.velocity_y.size(),
        scratch.velocity_z.size(),
        scratch.mass.size(),
        scratch.charge.size(),
    };
    snapshot.capacities = {
        scratch.position_x.capacity(),
        scratch.position_y.capacity(),
        scratch.position_z.capacity(),
        scratch.velocity_x.capacity(),
        scratch.velocity_y.capacity(),
        scratch.velocity_z.capacity(),
        scratch.mass.capacity(),
        scratch.charge.capacity(),
    };
    return snapshot;
}

void set_particle_mesh_ewald_composite_short_system_scratch_unit_for_test(
    bg_particle_mesh_ewald_composite_simulation_v1 *simulation,
    bg_unit_system unit_system) {
    assert(simulation != nullptr);
    simulation->short_system_scratch.unit_system = unit_system;
}

void truncate_particle_mesh_ewald_composite_short_system_scratch_for_test(
    bg_particle_mesh_ewald_composite_simulation_v1 *simulation) {
    assert(simulation != nullptr);
    assert(!simulation->short_system_scratch.position_x.empty());
    simulation->short_system_scratch.position_x.pop_back();
}

void set_particle_mesh_ewald_composite_short_system_scratch_charge_for_test(
    bg_particle_mesh_ewald_composite_simulation_v1 *simulation,
    double charge) {
    assert(simulation != nullptr);
    assert(!simulation->short_system_scratch.charge.empty());
    simulation->short_system_scratch.charge.front() = charge;
}

}  // namespace betelgeuze::native::tests
