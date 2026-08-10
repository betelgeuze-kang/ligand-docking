#include "dynamics.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <utility>
#include <vector>

namespace betelgeuze::native::dynamics {
namespace {

constexpr double kPi = 3.141592653589793238462643383279502884;

struct Vector3 final {
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
};

struct VectorChannels final {
    std::vector<double> x;
    std::vector<double> y;
    std::vector<double> z;
};

[[nodiscard]] bool finite_vector(const Vector3 &value) noexcept {
    return std::isfinite(value.x) && std::isfinite(value.y) &&
           std::isfinite(value.z);
}

[[nodiscard]] double dot(
    const Vector3 &left,
    const Vector3 &right) noexcept {
    return left.x * right.x + left.y * right.y + left.z * right.z;
}

bool minimum_image_component(
    double raw,
    double length,
    bool periodic,
    double *out_value) noexcept {
    double value = raw;
    if (periodic) {
        const double quotient = raw / length + 0.5;
        if (!std::isfinite(quotient)) {
            return false;
        }
        value -= length * std::floor(quotient);
    }
    if (!std::isfinite(value)) {
        return false;
    }
    *out_value = value;
    return true;
}

bool constraint_displacement(
    const bg_system &system,
    const bg_forcefield &forcefield,
    std::size_t atom_i,
    std::size_t atom_j,
    Vector3 *out_displacement,
    double *out_squared_norm) noexcept {
    Vector3 displacement;
    const std::array<double, 3> raw = {
        system.position_x[atom_i] - system.position_x[atom_j],
        system.position_y[atom_i] - system.position_y[atom_j],
        system.position_z[atom_i] - system.position_z[atom_j],
    };
    double *const output[] = {
        &displacement.x, &displacement.y, &displacement.z};
    constexpr std::array<uint32_t, 3> axis_bits = {
        static_cast<uint32_t>(BG_PERIODIC_AXIS_X),
        static_cast<uint32_t>(BG_PERIODIC_AXIS_Y),
        static_cast<uint32_t>(BG_PERIODIC_AXIS_Z),
    };
    for (std::size_t axis = 0; axis < axis_bits.size(); ++axis) {
        if (!minimum_image_component(
                raw[axis],
                forcefield.cell_lengths[axis],
                (forcefield.periodic_axes_mask & axis_bits[axis]) != 0U,
                output[axis])) {
            return false;
        }
    }
    const double squared_norm = dot(displacement, displacement);
    if (!finite_vector(displacement) || !std::isfinite(squared_norm) ||
        squared_norm <= 0.0) {
        return false;
    }
    *out_displacement = displacement;
    *out_squared_norm = squared_norm;
    return true;
}

bg_status apply_shake(
    const bg_simulation &simulation,
    bg_system *system) noexcept {
    if (simulation.constraints.empty()) {
        return BG_STATUS_OK;
    }
    for (uint32_t sweep = 0; sweep < simulation.constraint_max_iterations;
         ++sweep) {
        bool converged = true;
        for (const bg_simulation::DistanceConstraint &constraint :
             simulation.constraints) {
            Vector3 displacement;
            double squared_norm = 0.0;
            if (!constraint_displacement(
                    *system,
                    simulation.forcefield,
                    constraint.atom_i,
                    constraint.atom_j,
                    &displacement,
                    &squared_norm)) {
                return fail(
                    BG_STATUS_NUMERICAL_ERROR,
                    "SHAKE encountered a non-finite or zero constraint displacement");
            }
            const double distance = std::sqrt(squared_norm);
            const double error = distance - constraint.distance;
            if (!std::isfinite(error)) {
                return fail(
                    BG_STATUS_NUMERICAL_ERROR,
                    "SHAKE constraint error is non-finite");
            }
            if (std::abs(error) <= simulation.constraint_tolerance) {
                continue;
            }
            converged = false;
            const double inverse_mass_i =
                1.0 / system->mass[constraint.atom_i];
            const double inverse_mass_j =
                1.0 / system->mass[constraint.atom_j];
            const double inverse_mass_sum = inverse_mass_i + inverse_mass_j;
            const double beta =
                (1.0 - constraint.distance / distance) / inverse_mass_sum;
            const Vector3 correction_i{
                beta * inverse_mass_i * displacement.x,
                beta * inverse_mass_i * displacement.y,
                beta * inverse_mass_i * displacement.z,
            };
            const Vector3 correction_j{
                beta * inverse_mass_j * displacement.x,
                beta * inverse_mass_j * displacement.y,
                beta * inverse_mass_j * displacement.z,
            };
            const double next_ix =
                system->position_x[constraint.atom_i] - correction_i.x;
            const double next_iy =
                system->position_y[constraint.atom_i] - correction_i.y;
            const double next_iz =
                system->position_z[constraint.atom_i] - correction_i.z;
            const double next_jx =
                system->position_x[constraint.atom_j] + correction_j.x;
            const double next_jy =
                system->position_y[constraint.atom_j] + correction_j.y;
            const double next_jz =
                system->position_z[constraint.atom_j] + correction_j.z;
            if (!finite_vector(correction_i) || !finite_vector(correction_j) ||
                !std::isfinite(next_ix) || !std::isfinite(next_iy) ||
                !std::isfinite(next_iz) || !std::isfinite(next_jx) ||
                !std::isfinite(next_jy) || !std::isfinite(next_jz)) {
                return fail(
                    BG_STATUS_NUMERICAL_ERROR,
                    "SHAKE position correction overflowed");
            }
            system->position_x[constraint.atom_i] = next_ix;
            system->position_y[constraint.atom_i] = next_iy;
            system->position_z[constraint.atom_i] = next_iz;
            system->position_x[constraint.atom_j] = next_jx;
            system->position_y[constraint.atom_j] = next_jy;
            system->position_z[constraint.atom_j] = next_jz;
        }
        if (converged) {
            return BG_STATUS_OK;
        }
        bool corrected_state_converged = true;
        for (const bg_simulation::DistanceConstraint &constraint :
             simulation.constraints) {
            Vector3 displacement;
            double squared_norm = 0.0;
            if (!constraint_displacement(
                    *system,
                    simulation.forcefield,
                    constraint.atom_i,
                    constraint.atom_j,
                    &displacement,
                    &squared_norm) ||
                std::abs(std::sqrt(squared_norm) - constraint.distance) >
                    simulation.constraint_tolerance) {
                corrected_state_converged = false;
                break;
            }
        }
        if (corrected_state_converged) {
            return BG_STATUS_OK;
        }
    }
    return fail(
        BG_STATUS_NUMERICAL_ERROR,
        "SHAKE did not converge within max_iterations");
}

bg_status apply_rattle(
    const bg_simulation &simulation,
    bg_system *system) noexcept {
    if (simulation.constraints.empty()) {
        return BG_STATUS_OK;
    }
    for (uint32_t sweep = 0; sweep < simulation.constraint_max_iterations;
         ++sweep) {
        bool converged = true;
        for (const bg_simulation::DistanceConstraint &constraint :
             simulation.constraints) {
            Vector3 displacement;
            double squared_norm = 0.0;
            if (!constraint_displacement(
                    *system,
                    simulation.forcefield,
                    constraint.atom_i,
                    constraint.atom_j,
                    &displacement,
                    &squared_norm)) {
                return fail(
                    BG_STATUS_NUMERICAL_ERROR,
                    "RATTLE encountered a non-finite or zero constraint displacement");
            }
            const Vector3 relative_velocity{
                system->velocity_x[constraint.atom_i] -
                    system->velocity_x[constraint.atom_j],
                system->velocity_y[constraint.atom_i] -
                    system->velocity_y[constraint.atom_j],
                system->velocity_z[constraint.atom_i] -
                    system->velocity_z[constraint.atom_j],
            };
            const double radial_velocity =
                dot(displacement, relative_velocity) / std::sqrt(squared_norm);
            if (!std::isfinite(radial_velocity)) {
                return fail(
                    BG_STATUS_NUMERICAL_ERROR,
                    "RATTLE velocity residual is non-finite");
            }
            if (std::abs(radial_velocity) <=
                simulation.constraint_velocity_tolerance) {
                continue;
            }
            converged = false;
            const double inverse_mass_i =
                1.0 / system->mass[constraint.atom_i];
            const double inverse_mass_j =
                1.0 / system->mass[constraint.atom_j];
            const double beta = dot(displacement, relative_velocity) /
                                ((inverse_mass_i + inverse_mass_j) * squared_norm);
            const Vector3 correction_i{
                beta * inverse_mass_i * displacement.x,
                beta * inverse_mass_i * displacement.y,
                beta * inverse_mass_i * displacement.z,
            };
            const Vector3 correction_j{
                beta * inverse_mass_j * displacement.x,
                beta * inverse_mass_j * displacement.y,
                beta * inverse_mass_j * displacement.z,
            };
            const double next_ix =
                system->velocity_x[constraint.atom_i] - correction_i.x;
            const double next_iy =
                system->velocity_y[constraint.atom_i] - correction_i.y;
            const double next_iz =
                system->velocity_z[constraint.atom_i] - correction_i.z;
            const double next_jx =
                system->velocity_x[constraint.atom_j] + correction_j.x;
            const double next_jy =
                system->velocity_y[constraint.atom_j] + correction_j.y;
            const double next_jz =
                system->velocity_z[constraint.atom_j] + correction_j.z;
            if (!finite_vector(correction_i) || !finite_vector(correction_j) ||
                !std::isfinite(next_ix) || !std::isfinite(next_iy) ||
                !std::isfinite(next_iz) || !std::isfinite(next_jx) ||
                !std::isfinite(next_jy) || !std::isfinite(next_jz)) {
                return fail(
                    BG_STATUS_NUMERICAL_ERROR,
                    "RATTLE velocity correction overflowed");
            }
            system->velocity_x[constraint.atom_i] = next_ix;
            system->velocity_y[constraint.atom_i] = next_iy;
            system->velocity_z[constraint.atom_i] = next_iz;
            system->velocity_x[constraint.atom_j] = next_jx;
            system->velocity_y[constraint.atom_j] = next_jy;
            system->velocity_z[constraint.atom_j] = next_jz;
        }
        if (converged) {
            return BG_STATUS_OK;
        }
        bool corrected_state_converged = true;
        for (const bg_simulation::DistanceConstraint &constraint :
             simulation.constraints) {
            Vector3 displacement;
            double squared_norm = 0.0;
            if (!constraint_displacement(
                    *system,
                    simulation.forcefield,
                    constraint.atom_i,
                    constraint.atom_j,
                    &displacement,
                    &squared_norm)) {
                corrected_state_converged = false;
                break;
            }
            const Vector3 relative_velocity{
                system->velocity_x[constraint.atom_i] -
                    system->velocity_x[constraint.atom_j],
                system->velocity_y[constraint.atom_i] -
                    system->velocity_y[constraint.atom_j],
                system->velocity_z[constraint.atom_i] -
                    system->velocity_z[constraint.atom_j],
            };
            const double radial =
                std::abs(dot(displacement, relative_velocity)) /
                std::sqrt(squared_norm);
            if (!std::isfinite(radial) ||
                radial > simulation.constraint_velocity_tolerance) {
                corrected_state_converged = false;
                break;
            }
        }
        if (corrected_state_converged) {
            return BG_STATUS_OK;
        }
    }
    return fail(
        BG_STATUS_NUMERICAL_ERROR,
        "RATTLE did not converge within max_iterations");
}

bg_status drift_and_constrain(
    const bg_simulation &simulation,
    double duration,
    bg_system *system) {
    for (std::size_t atom = 0; atom < system->position_x.size(); ++atom) {
        const double next_x =
            system->position_x[atom] + duration * system->velocity_x[atom];
        const double next_y =
            system->position_y[atom] + duration * system->velocity_y[atom];
        const double next_z =
            system->position_z[atom] + duration * system->velocity_z[atom];
        if (!std::isfinite(next_x) || !std::isfinite(next_y) ||
            !std::isfinite(next_z)) {
            return fail(
                BG_STATUS_NUMERICAL_ERROR,
                "position drift overflowed");
        }
        system->position_x[atom] = next_x;
        system->position_y[atom] = next_y;
        system->position_z[atom] = next_z;
    }
    const std::vector<double> unconstrained_x = system->position_x;
    const std::vector<double> unconstrained_y = system->position_y;
    const std::vector<double> unconstrained_z = system->position_z;
    const bg_status status = apply_shake(simulation, system);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (!simulation.constraints.empty()) {
        for (std::size_t atom = 0; atom < system->position_x.size(); ++atom) {
            const double next_vx = system->velocity_x[atom] +
                (system->position_x[atom] - unconstrained_x[atom]) / duration;
            const double next_vy = system->velocity_y[atom] +
                (system->position_y[atom] - unconstrained_y[atom]) / duration;
            const double next_vz = system->velocity_z[atom] +
                (system->position_z[atom] - unconstrained_z[atom]) / duration;
            if (!std::isfinite(next_vx) || !std::isfinite(next_vy) ||
                !std::isfinite(next_vz)) {
                return fail(
                    BG_STATUS_NUMERICAL_ERROR,
                    "constraint velocity reconstruction overflowed");
            }
            system->velocity_x[atom] = next_vx;
            system->velocity_y[atom] = next_vy;
            system->velocity_z[atom] = next_vz;
        }
    }
    return apply_rattle(simulation, system);
}

bg_status kick(
    const cpu::Evaluation &evaluation,
    double duration,
    bg_system *system) noexcept {
    for (std::size_t atom = 0; atom < system->mass.size(); ++atom) {
        const double scale =
            kAccelerationConversion * duration / system->mass[atom];
        const double next_x =
            system->velocity_x[atom] + scale * evaluation.force_x[atom];
        const double next_y =
            system->velocity_y[atom] + scale * evaluation.force_y[atom];
        const double next_z =
            system->velocity_z[atom] + scale * evaluation.force_z[atom];
        if (!std::isfinite(next_x) || !std::isfinite(next_y) ||
            !std::isfinite(next_z)) {
            return fail(BG_STATUS_NUMERICAL_ERROR, "velocity kick overflowed");
        }
        system->velocity_x[atom] = next_x;
        system->velocity_y[atom] = next_y;
        system->velocity_z[atom] = next_z;
    }
    return BG_STATUS_OK;
}

uint32_t multiply_high(uint32_t left, uint32_t right) noexcept {
    const uint64_t product =
        static_cast<uint64_t>(left) * static_cast<uint64_t>(right);
    return static_cast<uint32_t>(product >> 32U);
}

std::array<uint32_t, 4> philox4x32_10(
    std::array<uint32_t, 4> counter,
    std::array<uint32_t, 2> key) noexcept {
    constexpr uint32_t multiplier0 = UINT32_C(0xD2511F53);
    constexpr uint32_t multiplier1 = UINT32_C(0xCD9E8D57);
    constexpr uint32_t Weyl0 = UINT32_C(0x9E3779B9);
    constexpr uint32_t Weyl1 = UINT32_C(0xBB67AE85);
    for (uint32_t round = 0; round < UINT32_C(10); ++round) {
        const uint32_t low0 = multiplier0 * counter[0];
        const uint32_t high0 = multiply_high(multiplier0, counter[0]);
        const uint32_t low1 = multiplier1 * counter[2];
        const uint32_t high1 = multiply_high(multiplier1, counter[2]);
        counter = {
            high1 ^ counter[1] ^ key[0],
            low1,
            high0 ^ counter[3] ^ key[1],
            low0,
        };
        key[0] += Weyl0;
        key[1] += Weyl1;
    }
    return counter;
}

std::array<double, 3> counter_normals(
    uint64_t seed,
    uint64_t absolute_step,
    uint64_t atom) noexcept {
    const std::array<uint32_t, 4> words = philox4x32_10(
        {static_cast<uint32_t>(absolute_step),
         static_cast<uint32_t>(absolute_step >> 32U),
         static_cast<uint32_t>(atom),
         static_cast<uint32_t>(atom >> 32U)},
        {static_cast<uint32_t>(seed), static_cast<uint32_t>(seed >> 32U)});
    constexpr double inverse_two32 = 0x1.0p-32;
    const double uniform0 =
        (static_cast<double>(words[0]) + 0.5) * inverse_two32;
    const double uniform1 =
        (static_cast<double>(words[1]) + 0.5) * inverse_two32;
    const double uniform2 =
        (static_cast<double>(words[2]) + 0.5) * inverse_two32;
    const double uniform3 =
        (static_cast<double>(words[3]) + 0.5) * inverse_two32;
    const double radius0 = std::sqrt(-2.0 * std::log(uniform0));
    const double angle0 = 2.0 * kPi * uniform1;
    const double radius1 = std::sqrt(-2.0 * std::log(uniform2));
    const double angle1 = 2.0 * kPi * uniform3;
    return {
        radius0 * std::cos(angle0),
        radius0 * std::sin(angle0),
        radius1 * std::cos(angle1),
    };
}

bg_status ornstein_uhlenbeck(
    const bg_simulation &simulation,
    bg_system *system) noexcept {
    const double dt = simulation.timestep_femtoseconds;
    const double exponent = -simulation.friction_per_femtosecond * dt;
    const double decay = std::exp(exponent);
    const double variance_factor = -std::expm1(2.0 * exponent);
    if (!std::isfinite(decay) || !std::isfinite(variance_factor) ||
        variance_factor < 0.0) {
        return fail(
            BG_STATUS_NUMERICAL_ERROR,
            "Langevin OU coefficient is non-finite");
    }
    for (std::size_t atom = 0; atom < system->mass.size(); ++atom) {
        const double variance =
            kAccelerationConversion * kGasConstantKcalPerMolKelvin *
            simulation.temperature_kelvin * variance_factor /
            system->mass[atom];
        const double sigma = std::sqrt(variance);
        if (!std::isfinite(sigma)) {
            return fail(
                BG_STATUS_NUMERICAL_ERROR,
                "Langevin OU variance is non-finite");
        }
        const std::array<double, 3> normal = counter_normals(
            simulation.random_seed,
            simulation.absolute_step,
            static_cast<uint64_t>(atom));
        const double next_x = decay * system->velocity_x[atom] +
                              sigma * normal[0];
        const double next_y = decay * system->velocity_y[atom] +
                              sigma * normal[1];
        const double next_z = decay * system->velocity_z[atom] +
                              sigma * normal[2];
        if (!std::isfinite(next_x) || !std::isfinite(next_y) ||
            !std::isfinite(next_z)) {
            return fail(
                BG_STATUS_NUMERICAL_ERROR,
                "Langevin OU velocity update overflowed");
        }
        system->velocity_x[atom] = next_x;
        system->velocity_y[atom] = next_y;
        system->velocity_z[atom] = next_z;
    }
    return apply_rattle(simulation, system);
}

bg_status velocity_verlet_step(
    const bg_context &context,
    bg_simulation *simulation,
    cpu::Evaluation *out_final_evaluation) {
    cpu::Evaluation evaluation;
    bg_status status = evaluate(
        context, simulation->system, simulation->forcefield, true, &evaluation);
    if (status != BG_STATUS_OK) {
        return status;
    }
    const double half_dt = 0.5 * simulation->timestep_femtoseconds;
    status = kick(evaluation, half_dt, &simulation->system);
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = drift_and_constrain(
        *simulation, simulation->timestep_femtoseconds, &simulation->system);
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = evaluate(
        context, simulation->system, simulation->forcefield, true, &evaluation);
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = kick(evaluation, half_dt, &simulation->system);
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = apply_rattle(*simulation, &simulation->system);
    if (status != BG_STATUS_OK) {
        return status;
    }
    *out_final_evaluation = std::move(evaluation);
    return BG_STATUS_OK;
}

bg_status baoab_step(
    const bg_context &context,
    bg_simulation *simulation,
    cpu::Evaluation *out_final_evaluation) {
    cpu::Evaluation evaluation;
    bg_status status = evaluate(
        context, simulation->system, simulation->forcefield, true, &evaluation);
    if (status != BG_STATUS_OK) {
        return status;
    }
    const double half_dt = 0.5 * simulation->timestep_femtoseconds;
    status = kick(evaluation, half_dt, &simulation->system);
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = drift_and_constrain(*simulation, half_dt, &simulation->system);
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = ornstein_uhlenbeck(*simulation, &simulation->system);
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = drift_and_constrain(*simulation, half_dt, &simulation->system);
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = evaluate(
        context, simulation->system, simulation->forcefield, true, &evaluation);
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = kick(evaluation, half_dt, &simulation->system);
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = apply_rattle(*simulation, &simulation->system);
    if (status != BG_STATUS_OK) {
        return status;
    }
    *out_final_evaluation = std::move(evaluation);
    return BG_STATUS_OK;
}

bg_status kinetic_energy(
    const bg_system &system,
    double *out_energy) noexcept {
    double sum = 0.0;
    for (std::size_t atom = 0; atom < system.mass.size(); ++atom) {
        const std::array<double, 3> velocity = {
            system.velocity_x[atom],
            system.velocity_y[atom],
            system.velocity_z[atom],
        };
        for (const double component : velocity) {
            const double term = system.mass[atom] * component * component;
            const double next = sum + term;
            if (!std::isfinite(term) || !std::isfinite(next)) {
                return fail(
                    BG_STATUS_NUMERICAL_ERROR,
                    "kinetic energy accumulation overflowed");
            }
            sum = next;
        }
    }
    const double energy = 0.5 * sum / kAccelerationConversion;
    if (!std::isfinite(energy)) {
        return fail(BG_STATUS_NUMERICAL_ERROR, "kinetic energy is non-finite");
    }
    *out_energy = energy;
    return BG_STATUS_OK;
}

bg_status project_direction(
    const bg_simulation &simulation,
    const bg_system &system,
    VectorChannels *direction) noexcept {
    if (simulation.constraints.empty()) {
        return BG_STATUS_OK;
    }
    for (uint32_t sweep = 0; sweep < simulation.constraint_max_iterations;
         ++sweep) {
        double largest_component = 0.0;
        for (std::size_t atom = 0; atom < direction->x.size(); ++atom) {
            largest_component = std::max(
                largest_component,
                std::hypot(direction->x[atom], direction->y[atom],
                           direction->z[atom]));
        }
        const double tolerance = 64.0 * std::numeric_limits<double>::epsilon() *
                                 (1.0 + largest_component);
        bool converged = true;
        for (const bg_simulation::DistanceConstraint &constraint :
             simulation.constraints) {
            Vector3 displacement;
            double squared_norm = 0.0;
            if (!constraint_displacement(
                    system,
                    simulation.forcefield,
                    constraint.atom_i,
                    constraint.atom_j,
                    &displacement,
                    &squared_norm)) {
                return fail(
                    BG_STATUS_NUMERICAL_ERROR,
                    "force projection encountered an invalid constraint displacement");
            }
            const Vector3 relative{
                direction->x[constraint.atom_i] -
                    direction->x[constraint.atom_j],
                direction->y[constraint.atom_i] -
                    direction->y[constraint.atom_j],
                direction->z[constraint.atom_i] -
                    direction->z[constraint.atom_j],
            };
            const double radial = dot(displacement, relative) /
                                  std::sqrt(squared_norm);
            if (std::abs(radial) <= tolerance) {
                continue;
            }
            converged = false;
            const double beta =
                dot(displacement, relative) / (2.0 * squared_norm);
            direction->x[constraint.atom_i] -=
                beta * displacement.x;
            direction->y[constraint.atom_i] -=
                beta * displacement.y;
            direction->z[constraint.atom_i] -=
                beta * displacement.z;
            direction->x[constraint.atom_j] +=
                beta * displacement.x;
            direction->y[constraint.atom_j] +=
                beta * displacement.y;
            direction->z[constraint.atom_j] +=
                beta * displacement.z;
        }
        if (converged) {
            return BG_STATUS_OK;
        }
        bool corrected_state_converged = true;
        for (const bg_simulation::DistanceConstraint &constraint :
             simulation.constraints) {
            Vector3 displacement;
            double squared_norm = 0.0;
            if (!constraint_displacement(
                    system,
                    simulation.forcefield,
                    constraint.atom_i,
                    constraint.atom_j,
                    &displacement,
                    &squared_norm)) {
                corrected_state_converged = false;
                break;
            }
            const Vector3 relative{
                direction->x[constraint.atom_i] -
                    direction->x[constraint.atom_j],
                direction->y[constraint.atom_i] -
                    direction->y[constraint.atom_j],
                direction->z[constraint.atom_i] -
                    direction->z[constraint.atom_j],
            };
            const double largest_component = std::max(
                std::hypot(
                    direction->x[constraint.atom_i],
                    direction->y[constraint.atom_i],
                    direction->z[constraint.atom_i]),
                std::hypot(
                    direction->x[constraint.atom_j],
                    direction->y[constraint.atom_j],
                    direction->z[constraint.atom_j]));
            const double tolerance =
                64.0 * std::numeric_limits<double>::epsilon() *
                (1.0 + largest_component);
            const double radial =
                std::abs(dot(displacement, relative)) /
                std::sqrt(squared_norm);
            if (!std::isfinite(radial) || radial > tolerance) {
                corrected_state_converged = false;
                break;
            }
        }
        if (corrected_state_converged) {
            return BG_STATUS_OK;
        }
    }
    return fail(
        BG_STATUS_NUMERICAL_ERROR,
        "constraint force projection did not converge");
}

bg_status projected_force(
    const bg_simulation &simulation,
    const cpu::Evaluation &evaluation,
    VectorChannels *out_direction,
    double *out_maximum) {
    out_direction->x = evaluation.force_x;
    out_direction->y = evaluation.force_y;
    out_direction->z = evaluation.force_z;
    bg_status status =
        project_direction(simulation, simulation.system, out_direction);
    if (status != BG_STATUS_OK) {
        return status;
    }
    double maximum = 0.0;
    for (std::size_t atom = 0; atom < out_direction->x.size(); ++atom) {
        const double magnitude = std::hypot(
            out_direction->x[atom], out_direction->y[atom],
            out_direction->z[atom]);
        if (!std::isfinite(magnitude)) {
            return fail(
                BG_STATUS_NUMERICAL_ERROR,
                "projected force magnitude is non-finite");
        }
        maximum = std::max(maximum, magnitude);
    }
    *out_maximum = maximum;
    return BG_STATUS_OK;
}

}  // namespace

bg_status initialize_constraints(bg_simulation *simulation) {
    bg_status status = apply_shake(*simulation, &simulation->system);
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = apply_rattle(*simulation, &simulation->system);
    if (status != BG_STATUS_OK) {
        return status;
    }
    return validate_constraint_independence(*simulation);
}

bg_status validate_constraint_independence(
    const bg_simulation &simulation) {
    const std::size_t count = simulation.constraints.size();
    if (count == 0) {
        return BG_STATUS_OK;
    }
    if (count > std::numeric_limits<std::size_t>::max() / count) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "constraint Jacobian rank matrix size overflowed");
    }
    std::vector<double> gram(count * count, 0.0);
    std::vector<Vector3> directions(count);
    for (std::size_t row = 0; row < count; ++row) {
        double squared_norm = 0.0;
        if (!constraint_displacement(
                simulation.system,
                simulation.forcefield,
                simulation.constraints[row].atom_i,
                simulation.constraints[row].atom_j,
                &directions[row],
                &squared_norm)) {
            return fail(
                BG_STATUS_NUMERICAL_ERROR,
                "constraint Jacobian contains an invalid displacement");
        }
        const double inverse_norm = 1.0 / std::sqrt(squared_norm);
        directions[row].x *= inverse_norm;
        directions[row].y *= inverse_norm;
        directions[row].z *= inverse_norm;
    }
    for (std::size_t left = 0; left < count; ++left) {
        for (std::size_t right = 0; right <= left; ++right) {
            double value = 0.0;
            const auto &left_constraint = simulation.constraints[left];
            const auto &right_constraint = simulation.constraints[right];
            if (left_constraint.atom_i == right_constraint.atom_i) {
                value += dot(directions[left], directions[right]);
            }
            if (left_constraint.atom_i == right_constraint.atom_j) {
                value -= dot(directions[left], directions[right]);
            }
            if (left_constraint.atom_j == right_constraint.atom_i) {
                value -= dot(directions[left], directions[right]);
            }
            if (left_constraint.atom_j == right_constraint.atom_j) {
                value += dot(directions[left], directions[right]);
            }
            gram[left * count + right] = value;
            gram[right * count + left] = value;
        }
    }
    const double rank_tolerance =
        128.0 * std::numeric_limits<double>::epsilon() *
        static_cast<double>(std::max<std::size_t>(count, 1U));
    for (std::size_t column = 0; column < count; ++column) {
        std::size_t pivot = column;
        double pivot_magnitude = std::abs(gram[column * count + column]);
        for (std::size_t row = column + 1U; row < count; ++row) {
            const double magnitude = std::abs(gram[row * count + column]);
            if (magnitude > pivot_magnitude) {
                pivot = row;
                pivot_magnitude = magnitude;
            }
        }
        if (!std::isfinite(pivot_magnitude) ||
            pivot_magnitude <= rank_tolerance) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "constraint Jacobian rows are linearly dependent");
        }
        if (pivot != column) {
            for (std::size_t entry = 0; entry < count; ++entry) {
                std::swap(
                    gram[column * count + entry],
                    gram[pivot * count + entry]);
            }
        }
        const double diagonal = gram[column * count + column];
        for (std::size_t row = column + 1U; row < count; ++row) {
            const double factor = gram[row * count + column] / diagonal;
            for (std::size_t entry = column; entry < count; ++entry) {
                gram[row * count + entry] -=
                    factor * gram[column * count + entry];
            }
        }
    }
    return BG_STATUS_OK;
}

bg_status validate_constraint_state(const bg_simulation &simulation) noexcept {
    for (const bg_simulation::DistanceConstraint &constraint :
         simulation.constraints) {
        Vector3 displacement;
        double squared_norm = 0.0;
        if (!constraint_displacement(
                simulation.system,
                simulation.forcefield,
                constraint.atom_i,
                constraint.atom_j,
                &displacement,
                &squared_norm)) {
            return fail(
                BG_STATUS_NUMERICAL_ERROR,
                "constraint state contains an invalid displacement");
        }
        const double distance_error =
            std::abs(std::sqrt(squared_norm) - constraint.distance);
        const Vector3 relative_velocity{
            simulation.system.velocity_x[constraint.atom_i] -
                simulation.system.velocity_x[constraint.atom_j],
            simulation.system.velocity_y[constraint.atom_i] -
                simulation.system.velocity_y[constraint.atom_j],
            simulation.system.velocity_z[constraint.atom_i] -
                simulation.system.velocity_z[constraint.atom_j],
        };
        const double radial_velocity =
            std::abs(dot(displacement, relative_velocity)) /
            std::sqrt(squared_norm);
        if (!std::isfinite(distance_error) ||
            distance_error > simulation.constraint_tolerance ||
            !std::isfinite(radial_velocity) ||
            radial_velocity > simulation.constraint_velocity_tolerance) {
            return fail(
                BG_STATUS_NUMERICAL_ERROR,
                "constraint state violates its position or velocity tolerance");
        }
    }
    return BG_STATUS_OK;
}

bg_status minimize(
    const bg_context &context,
    const bg_simulation &source,
    const bg_minimizer_options_v1 &options,
    bg_simulation *work,
    bg_minimization_report_v1 *out_report) {
    (void)source;
    cpu::Evaluation evaluation;
    bg_status status =
        evaluate(context, work->system, work->forcefield, true, &evaluation);
    if (status != BG_STATUS_OK) {
        return status;
    }
    const double initial_energy = evaluation.energy.total_kcal_per_mol;
    double current_energy = initial_energy;
    VectorChannels direction;
    double maximum_force = 0.0;
    status = projected_force(*work, evaluation, &direction, &maximum_force);
    if (status != BG_STATUS_OK) {
        return status;
    }
    uint64_t completed = UINT64_C(0);
    bool converged = maximum_force <=
                     options.force_tolerance_kcal_per_mol_angstrom;

    while (!converged && completed < options.max_iterations) {
        const std::vector<double> base_x = work->system.position_x;
        const std::vector<double> base_y = work->system.position_y;
        const std::vector<double> base_z = work->system.position_z;
        bool accepted = false;
        double accepted_energy = current_energy;
        bg_system accepted_system;
        double step = options.initial_step_angstrom2_mol_per_kcal;
        for (uint32_t attempt = 0;
             attempt < options.max_line_search_steps &&
             step >= options.minimum_step_angstrom2_mol_per_kcal;
             ++attempt) {
            bg_system candidate = work->system;
            bool finite = true;
            for (std::size_t atom = 0; atom < base_x.size(); ++atom) {
                candidate.position_x[atom] =
                    base_x[atom] + step * direction.x[atom];
                candidate.position_y[atom] =
                    base_y[atom] + step * direction.y[atom];
                candidate.position_z[atom] =
                    base_z[atom] + step * direction.z[atom];
                finite = finite && std::isfinite(candidate.position_x[atom]) &&
                         std::isfinite(candidate.position_y[atom]) &&
                         std::isfinite(candidate.position_z[atom]);
            }
            status = finite ? apply_shake(*work, &candidate)
                            : BG_STATUS_NUMERICAL_ERROR;
            if (status == BG_STATUS_OK) {
                double force_dot_displacement = 0.0;
                for (std::size_t atom = 0; atom < base_x.size(); ++atom) {
                    const double contribution =
                        evaluation.force_x[atom] *
                            (candidate.position_x[atom] - base_x[atom]) +
                        evaluation.force_y[atom] *
                            (candidate.position_y[atom] - base_y[atom]) +
                        evaluation.force_z[atom] *
                            (candidate.position_z[atom] - base_z[atom]);
                    force_dot_displacement += contribution;
                }
                cpu::Evaluation trial_evaluation;
                if (std::isfinite(force_dot_displacement) &&
                    force_dot_displacement > 0.0) {
                    status = evaluate(
                        context,
                        candidate,
                        work->forcefield,
                        false,
                        &trial_evaluation);
                    const double armijo_bound = current_energy -
                        options.armijo_coefficient * force_dot_displacement;
                    if (status == BG_STATUS_OK &&
                        trial_evaluation.energy.total_kcal_per_mol <=
                            armijo_bound) {
                        accepted = true;
                        accepted_energy =
                            trial_evaluation.energy.total_kcal_per_mol;
                        accepted_system = std::move(candidate);
                        break;
                    }
                }
            }
            if (status != BG_STATUS_OK && status != BG_STATUS_NUMERICAL_ERROR) {
                return status;
            }
            if (status == BG_STATUS_NUMERICAL_ERROR) {
                clear_last_error();
            }
            step *= options.backtrack_factor;
        }
        if (!accepted) {
            return fail(
                BG_STATUS_NUMERICAL_ERROR,
                "bounded Armijo line search did not find an acceptable step");
        }
        work->system = std::move(accepted_system);
        const double energy_change = std::abs(accepted_energy - current_energy);
        current_energy = accepted_energy;
        ++completed;
        status =
            evaluate(context, work->system, work->forcefield, true, &evaluation);
        if (status != BG_STATUS_OK) {
            return status;
        }
        current_energy = evaluation.energy.total_kcal_per_mol;
        status = projected_force(*work, evaluation, &direction, &maximum_force);
        if (status != BG_STATUS_OK) {
            return status;
        }
        converged =
            maximum_force <= options.force_tolerance_kcal_per_mol_angstrom ||
            (options.energy_tolerance_kcal_per_mol > 0.0 &&
             energy_change <= options.energy_tolerance_kcal_per_mol);
    }

    status = validate_constraint_independence(*work);
    if (status != BG_STATUS_OK) {
        return fail(
            BG_STATUS_NUMERICAL_ERROR,
            "minimization evolved to a singular constraint Jacobian");
    }
    status = apply_rattle(*work, &work->system);
    if (status != BG_STATUS_OK) {
        return status;
    }

    bg_minimization_report_v1 report{};
    report.struct_size = static_cast<uint32_t>(sizeof(report));
    report.abi_version = BG_ABI_VERSION;
    report.unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
    report.iterations = completed;
    report.converged = converged ? UINT32_C(1) : UINT32_C(0);
    report.initial_potential_kcal_per_mol = initial_energy;
    report.final_potential_kcal_per_mol = current_energy;
    report.maximum_force_kcal_per_mol_angstrom = maximum_force;
    *out_report = report;
    return BG_STATUS_OK;
}

bg_status integrate(
    const bg_context &context,
    const bg_simulation &source,
    uint64_t step_count,
    bg_simulation *work,
    bg_dynamics_report_v1 *out_report) {
    (void)source;
    cpu::Evaluation final_evaluation;
    bg_status status = BG_STATUS_OK;
    if (step_count == UINT64_C(0)) {
        status = evaluate(
            context, work->system, work->forcefield, false, &final_evaluation);
        if (status != BG_STATUS_OK) {
            return status;
        }
    } else {
        for (uint64_t step = UINT64_C(0); step < step_count; ++step) {
            switch (work->integrator) {
                case BG_INTEGRATOR_VELOCITY_VERLET:
                    status = velocity_verlet_step(
                        context, work, &final_evaluation);
                    break;
                case BG_INTEGRATOR_LANGEVIN_BAOAB:
                    status = baoab_step(context, work, &final_evaluation);
                    break;
                default:
                    return fail(
                        BG_STATUS_INTERNAL_ERROR,
                        "simulation contains an invalid integrator");
            }
            if (status != BG_STATUS_OK) {
                return status;
            }
            ++work->absolute_step;
        }
    }

    double kinetic = 0.0;
    status = validate_constraint_independence(*work);
    if (status != BG_STATUS_OK) {
        return fail(
            BG_STATUS_NUMERICAL_ERROR,
            "integration evolved to a singular constraint Jacobian");
    }
    status = kinetic_energy(work->system, &kinetic);
    if (status != BG_STATUS_OK) {
        return status;
    }
    const uint64_t atom_count =
        static_cast<uint64_t>(work->system.position_x.size());
    const uint64_t degrees_of_freedom = atom_count * UINT64_C(3) -
        static_cast<uint64_t>(work->constraints.size());
    const double temperature =
        2.0 * kinetic /
        (static_cast<double>(degrees_of_freedom) *
         kGasConstantKcalPerMolKelvin);
    const double potential = final_evaluation.energy.total_kcal_per_mol;
    const double total = potential + kinetic;
    if (!std::isfinite(temperature) || !std::isfinite(total)) {
        return fail(
            BG_STATUS_NUMERICAL_ERROR,
            "dynamics thermodynamic report is non-finite");
    }
    bg_dynamics_report_v1 report{};
    report.struct_size = static_cast<uint32_t>(sizeof(report));
    report.abi_version = BG_ABI_VERSION;
    report.unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
    report.steps_completed = step_count;
    report.absolute_step = work->absolute_step;
    report.degrees_of_freedom = degrees_of_freedom;
    report.potential_kcal_per_mol = potential;
    report.kinetic_kcal_per_mol = kinetic;
    report.total_kcal_per_mol = total;
    report.temperature_kelvin = temperature;
    *out_report = report;
    return BG_STATUS_OK;
}

}  // namespace betelgeuze::native::dynamics
