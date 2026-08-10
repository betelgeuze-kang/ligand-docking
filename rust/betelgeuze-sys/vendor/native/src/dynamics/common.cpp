#include "dynamics.hpp"

#include "../hip/backend.hpp"
#include "sha256.hpp"

#include <cstddef>

namespace betelgeuze::native::dynamics {
namespace {

void hash_size_vector(
    Sha256 *hash,
    const std::vector<std::size_t> &values) noexcept {
    hash_u64(hash, static_cast<uint64_t>(values.size()));
    for (const std::size_t value : values) {
        hash_u64(hash, static_cast<uint64_t>(value));
    }
}

void hash_u32_vector(
    Sha256 *hash,
    const std::vector<uint32_t> &values) noexcept {
    hash_u64(hash, static_cast<uint64_t>(values.size()));
    for (const uint32_t value : values) {
        hash_u32(hash, value);
    }
}

void hash_double_vector(
    Sha256 *hash,
    const std::vector<double> &values) noexcept {
    hash_u64(hash, static_cast<uint64_t>(values.size()));
    for (const double value : values) {
        hash_double(hash, value);
    }
}

}  // namespace

bg_status evaluate(
    const bg_context &context,
    const bg_system &system,
    const bg_forcefield &forcefield,
    bool compute_forces,
    cpu::Evaluation *out_evaluation) {
    if (out_evaluation == nullptr) {
        return fail(BG_STATUS_INTERNAL_ERROR, "dynamics evaluation output is null");
    }
    if (context.unit_system != system.unit_system ||
        context.unit_system != forcefield.unit_system) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "context and simulation unit systems must match");
    }
    switch (context.backend) {
        case BG_BACKEND_CPU:
            return cpu::evaluate(
                system, forcefield, compute_forces, out_evaluation);
        case BG_BACKEND_HIP:
            return hip::evaluate(
                context, system, forcefield, compute_forces, out_evaluation);
        default:
            return fail(
                BG_STATUS_UNSUPPORTED_BACKEND,
                "the selected backend has no dynamics force evaluator");
    }
}

std::array<uint8_t, 32> compute_static_fingerprint(
    const bg_simulation &simulation) noexcept {
    Sha256 hash;
    constexpr uint8_t tag[] = {
        'B', 'G', '-', 'D', 'Y', 'N', '-', 'S', 'T', 'A', 'T', 'I', 'C',
        '-', '1'};
    hash.update(tag, sizeof(tag));
    hash_u32(&hash, static_cast<uint32_t>(simulation.system.unit_system));
    hash_u64(
        &hash, static_cast<uint64_t>(simulation.system.position_x.size()));
    hash_double_vector(&hash, simulation.system.mass);
    hash_double_vector(&hash, simulation.system.charge);

    const bg_forcefield &forcefield = simulation.forcefield;
    hash_u32(&hash, static_cast<uint32_t>(forcefield.unit_system));
    hash_u64(&hash, static_cast<uint64_t>(forcefield.atom_count));
    hash_double_vector(&hash, forcefield.sigma);
    hash_double_vector(&hash, forcefield.epsilon);

    hash_size_vector(&hash, forcefield.bonds.atom_i);
    hash_size_vector(&hash, forcefield.bonds.atom_j);
    hash_double_vector(&hash, forcefield.bonds.equilibrium);
    hash_double_vector(&hash, forcefield.bonds.force_constant);

    hash_size_vector(&hash, forcefield.angles.atom_i);
    hash_size_vector(&hash, forcefield.angles.atom_j);
    hash_size_vector(&hash, forcefield.angles.atom_k);
    hash_double_vector(&hash, forcefield.angles.equilibrium);
    hash_double_vector(&hash, forcefield.angles.force_constant);

    hash_size_vector(&hash, forcefield.torsions.atom_i);
    hash_size_vector(&hash, forcefield.torsions.atom_j);
    hash_size_vector(&hash, forcefield.torsions.atom_k);
    hash_size_vector(&hash, forcefield.torsions.atom_l);
    hash_u32_vector(&hash, forcefield.torsions.periodicity);
    hash_double_vector(&hash, forcefield.torsions.phase);
    hash_double_vector(&hash, forcefield.torsions.amplitude);

    hash_u64(&hash, static_cast<uint64_t>(forcefield.exclusions.size()));
    for (const bg_forcefield::Pair &pair : forcefield.exclusions) {
        hash_u64(&hash, static_cast<uint64_t>(pair.atom_i));
        hash_u64(&hash, static_cast<uint64_t>(pair.atom_j));
    }
    hash_u64(&hash, static_cast<uint64_t>(forcefield.pair_scales.size()));
    for (const bg_forcefield::PairScale &scale : forcefield.pair_scales) {
        hash_u64(&hash, static_cast<uint64_t>(scale.pair.atom_i));
        hash_u64(&hash, static_cast<uint64_t>(scale.pair.atom_j));
        hash_double(&hash, scale.lennard_jones);
        hash_double(&hash, scale.coulomb);
    }
    hash_u32(&hash, forcefield.periodic_axes_mask);
    for (const double length : forcefield.cell_lengths) {
        hash_double(&hash, length);
    }
    hash_double(&hash, forcefield.cutoff);
    hash_double(&hash, forcefield.switch_start);
    hash_double(&hash, forcefield.dielectric);
    hash_double(&hash, forcefield.screening_kappa);
    hash_double(&hash, forcefield.minimum_pair_distance);

    hash_u64(&hash, static_cast<uint64_t>(simulation.constraints.size()));
    for (const bg_simulation::DistanceConstraint &constraint :
         simulation.constraints) {
        hash_u64(&hash, static_cast<uint64_t>(constraint.atom_i));
        hash_u64(&hash, static_cast<uint64_t>(constraint.atom_j));
        hash_double(&hash, constraint.distance);
    }
    hash_double(&hash, simulation.constraint_tolerance);
    hash_double(&hash, simulation.constraint_velocity_tolerance);
    hash_u32(&hash, simulation.constraint_max_iterations);
    hash_u32(&hash, static_cast<uint32_t>(simulation.integrator));
    hash_double(&hash, simulation.timestep_femtoseconds);
    hash_double(&hash, simulation.temperature_kelvin);
    hash_double(&hash, simulation.friction_per_femtosecond);
    hash_u64(&hash, simulation.random_seed);
    return hash.finish();
}

}  // namespace betelgeuze::native::dynamics
