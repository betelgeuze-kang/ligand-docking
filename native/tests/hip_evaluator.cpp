#include "betelgeuze/engine.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <memory>
#include <vector>

namespace {

[[noreturn]] void fail_test(const char *message) {
    std::fprintf(stderr, "HIP evaluator test failure: %s\n", message);
    std::abort();
}

void require(bool condition, const char *message) {
    if (!condition) {
        fail_test(message);
    }
}

void require_status(bg_status actual, bg_status expected, const char *message) {
    if (actual != expected) {
        std::fprintf(
            stderr,
            "HIP evaluator test failure: %s (expected %d, observed %d: %s)\n",
            message,
            static_cast<int>(expected),
            static_cast<int>(actual),
            bg_last_error_message());
        std::abort();
    }
}

uint64_t bits(double value) noexcept {
    uint64_t result = UINT64_C(0);
    static_assert(sizeof(result) == sizeof(value));
    std::memcpy(&result, &value, sizeof(result));
    return result;
}

void require_near(
    double actual,
    double expected,
    double absolute_tolerance,
    double relative_tolerance,
    const char *message) {
    const double tolerance = absolute_tolerance +
                             relative_tolerance *
                                 std::max(std::abs(actual), std::abs(expected));
    if (!std::isfinite(actual) || !std::isfinite(expected) ||
        std::abs(actual - expected) > tolerance) {
        std::fprintf(
            stderr,
            "HIP evaluator test failure: %s (expected %.17g, observed %.17g, "
            "tolerance %.17g)\n",
            message,
            expected,
            actual,
            tolerance);
        std::abort();
    }
}

template <typename Value>
const Value *data_or_null(const std::vector<Value> &values) noexcept {
    return values.empty() ? nullptr : values.data();
}

template <typename Value>
Value *data_or_null(std::vector<Value> &values) noexcept {
    return values.empty() ? nullptr : values.data();
}

struct ContextDeleter final {
    void operator()(bg_context *context) const noexcept {
        bg_context_destroy(context);
    }
};

struct SystemDeleter final {
    void operator()(bg_system *system) const noexcept {
        bg_system_destroy(system);
    }
};

struct ForceFieldDeleter final {
    void operator()(bg_forcefield *forcefield) const noexcept {
        bg_forcefield_destroy(forcefield);
    }
};

using ContextPtr = std::unique_ptr<bg_context, ContextDeleter>;
using SystemPtr = std::unique_ptr<bg_system, SystemDeleter>;
using ForceFieldPtr = std::unique_ptr<bg_forcefield, ForceFieldDeleter>;

struct ParticleData final {
    std::vector<double> x;
    std::vector<double> y;
    std::vector<double> z;
    std::vector<double> mass;
    std::vector<double> charge;

    [[nodiscard]] bg_particle_soa descriptor() const {
        require(
            x.size() == y.size() && x.size() == z.size() &&
                x.size() == mass.size() && x.size() == charge.size(),
            "particle fixture channels have different lengths");
        bg_particle_soa result{};
        require_status(
            bg_particle_soa_init(&result),
            BG_STATUS_OK,
            "particle descriptor initialization failed");
        result.particle_count = static_cast<uint64_t>(x.size());
        result.position_x_angstrom = data_or_null(x);
        result.position_y_angstrom = data_or_null(y);
        result.position_z_angstrom = data_or_null(z);
        result.mass_dalton = data_or_null(mass);
        result.charge_elementary = data_or_null(charge);
        return result;
    }
};

struct ForceFieldData final {
    std::vector<double> sigma;
    std::vector<double> epsilon;

    std::vector<uint64_t> bond_i;
    std::vector<uint64_t> bond_j;
    std::vector<double> bond_equilibrium;
    std::vector<double> bond_force_constant;

    std::vector<uint64_t> angle_i;
    std::vector<uint64_t> angle_j;
    std::vector<uint64_t> angle_k;
    std::vector<double> angle_equilibrium;
    std::vector<double> angle_force_constant;

    std::vector<uint64_t> torsion_i;
    std::vector<uint64_t> torsion_j;
    std::vector<uint64_t> torsion_k;
    std::vector<uint64_t> torsion_l;
    std::vector<uint32_t> torsion_periodicity;
    std::vector<double> torsion_phase;
    std::vector<double> torsion_amplitude;

    std::vector<uint64_t> exclusion_i;
    std::vector<uint64_t> exclusion_j;

    std::vector<uint64_t> scale_i;
    std::vector<uint64_t> scale_j;
    std::vector<double> scale_lennard_jones;
    std::vector<double> scale_coulomb;

    uint32_t periodic_axes_mask = UINT32_C(0);
    std::array<double, 3> cell_lengths{{0.0, 0.0, 0.0}};
    double cutoff = 10.0;
    double switch_start = 8.0;
    double dielectric = 1.0;
    double screening_kappa = 0.0;
    double minimum_pair_distance = 1.0e-6;

    [[nodiscard]] bg_forcefield_soa_v1 descriptor() const {
        require(sigma.size() == epsilon.size(), "atom parameter lengths differ");
        require(
            bond_i.size() == bond_j.size() &&
                bond_i.size() == bond_equilibrium.size() &&
                bond_i.size() == bond_force_constant.size(),
            "bond parameter lengths differ");
        require(
            angle_i.size() == angle_j.size() &&
                angle_i.size() == angle_k.size() &&
                angle_i.size() == angle_equilibrium.size() &&
                angle_i.size() == angle_force_constant.size(),
            "angle parameter lengths differ");
        require(
            torsion_i.size() == torsion_j.size() &&
                torsion_i.size() == torsion_k.size() &&
                torsion_i.size() == torsion_l.size() &&
                torsion_i.size() == torsion_periodicity.size() &&
                torsion_i.size() == torsion_phase.size() &&
                torsion_i.size() == torsion_amplitude.size(),
            "torsion parameter lengths differ");
        require(
            exclusion_i.size() == exclusion_j.size(),
            "exclusion parameter lengths differ");
        require(
            scale_i.size() == scale_j.size() &&
                scale_i.size() == scale_lennard_jones.size() &&
                scale_i.size() == scale_coulomb.size(),
            "pair-scale parameter lengths differ");

        bg_forcefield_soa_v1 result{};
        require_status(
            bg_forcefield_soa_v1_init(&result),
            BG_STATUS_OK,
            "force-field descriptor initialization failed");
        result.atom_count = static_cast<uint64_t>(sigma.size());
        result.periodic_axes_mask = periodic_axes_mask;
        result.sigma_angstrom = data_or_null(sigma);
        result.epsilon_kcal_per_mol = data_or_null(epsilon);

        result.bond_count = static_cast<uint64_t>(bond_i.size());
        result.bond_atom_i = data_or_null(bond_i);
        result.bond_atom_j = data_or_null(bond_j);
        result.bond_equilibrium_angstrom = data_or_null(bond_equilibrium);
        result.bond_force_constant_kcal_per_mol_angstrom2 =
            data_or_null(bond_force_constant);

        result.angle_count = static_cast<uint64_t>(angle_i.size());
        result.angle_atom_i = data_or_null(angle_i);
        result.angle_atom_j = data_or_null(angle_j);
        result.angle_atom_k = data_or_null(angle_k);
        result.angle_equilibrium_radians = data_or_null(angle_equilibrium);
        result.angle_force_constant_kcal_per_mol_radian2 =
            data_or_null(angle_force_constant);

        result.torsion_count = static_cast<uint64_t>(torsion_i.size());
        result.torsion_atom_i = data_or_null(torsion_i);
        result.torsion_atom_j = data_or_null(torsion_j);
        result.torsion_atom_k = data_or_null(torsion_k);
        result.torsion_atom_l = data_or_null(torsion_l);
        result.torsion_periodicity = data_or_null(torsion_periodicity);
        result.torsion_phase_radians = data_or_null(torsion_phase);
        result.torsion_amplitude_kcal_per_mol = data_or_null(torsion_amplitude);

        result.exclusion_count = static_cast<uint64_t>(exclusion_i.size());
        result.exclusion_atom_i = data_or_null(exclusion_i);
        result.exclusion_atom_j = data_or_null(exclusion_j);

        result.pair_scale_count = static_cast<uint64_t>(scale_i.size());
        result.pair_scale_atom_i = data_or_null(scale_i);
        result.pair_scale_atom_j = data_or_null(scale_j);
        result.pair_scale_lennard_jones = data_or_null(scale_lennard_jones);
        result.pair_scale_coulomb = data_or_null(scale_coulomb);

        std::copy(
            cell_lengths.begin(),
            cell_lengths.end(),
            result.cell_lengths_angstrom);
        result.cutoff_angstrom = cutoff;
        result.switch_start_angstrom = switch_start;
        result.dielectric = dielectric;
        result.screening_kappa_per_angstrom = screening_kappa;
        result.minimum_pair_distance_angstrom = minimum_pair_distance;
        return result;
    }
};

struct Evaluation final {
    bg_energy_components_v1 energy{};
    std::vector<double> force_x;
    std::vector<double> force_y;
    std::vector<double> force_z;
};

ContextPtr make_context(bg_backend backend) {
    bg_context_options options{};
    require_status(
        bg_context_options_init(&options),
        BG_STATUS_OK,
        "context options initialization failed");
    options.backend = backend;
    options.device_ordinal = 0;
    bg_context *raw = nullptr;
    require_status(
        bg_context_create(&options, &raw),
        BG_STATUS_OK,
        "context creation failed");
    require(raw != nullptr, "context creation returned null");
    bg_backend selected = BG_BACKEND_AUTO;
    require_status(
        bg_context_get_backend(raw, &selected),
        BG_STATUS_OK,
        "context backend query failed");
    require(selected == backend, "context silently selected another backend");
    return ContextPtr(raw);
}

SystemPtr make_system(const ParticleData &particles) {
    const bg_particle_soa descriptor = particles.descriptor();
    bg_system *raw = nullptr;
    require_status(
        bg_system_create(&descriptor, &raw),
        BG_STATUS_OK,
        "system creation failed");
    require(raw != nullptr, "system creation returned null");
    return SystemPtr(raw);
}

ForceFieldPtr make_forcefield(const ForceFieldData &parameters) {
    const bg_forcefield_soa_v1 descriptor = parameters.descriptor();
    bg_forcefield *raw = nullptr;
    require_status(
        bg_forcefield_create(&descriptor, &raw),
        BG_STATUS_OK,
        "force-field creation failed");
    require(raw != nullptr, "force-field creation returned null");
    return ForceFieldPtr(raw);
}

void set_positions(bg_system *system, const ParticleData &particles) {
    bg_position_soa descriptor{};
    require_status(
        bg_position_soa_init(&descriptor),
        BG_STATUS_OK,
        "position descriptor initialization failed");
    descriptor.particle_count = static_cast<uint64_t>(particles.x.size());
    descriptor.x_angstrom = data_or_null(particles.x);
    descriptor.y_angstrom = data_or_null(particles.y);
    descriptor.z_angstrom = data_or_null(particles.z);
    require_status(
        bg_system_set_positions(system, &descriptor),
        BG_STATUS_OK,
        "position replacement failed");
}

Evaluation evaluate_with_forces(
    const bg_context *context,
    const bg_system *system,
    const bg_forcefield *forcefield) {
    uint64_t atom_count = UINT64_C(0);
    require_status(
        bg_forcefield_get_atom_count(forcefield, &atom_count),
        BG_STATUS_OK,
        "force-field atom-count query failed");
    require(
        atom_count <= static_cast<uint64_t>(
                          std::numeric_limits<std::size_t>::max()),
        "fixture atom count does not fit size_t");
    const std::size_t count = static_cast<std::size_t>(atom_count);

    Evaluation result;
    result.force_x.assign(count, 0.0);
    result.force_y.assign(count, 0.0);
    result.force_z.assign(count, 0.0);
    require_status(
        bg_energy_components_v1_init(&result.energy),
        BG_STATUS_OK,
        "energy descriptor initialization failed");
    bg_force_soa_v1 forces{};
    require_status(
        bg_force_soa_v1_init(&forces),
        BG_STATUS_OK,
        "force descriptor initialization failed");
    forces.particle_capacity = atom_count;
    forces.x_kcal_per_mol_angstrom = data_or_null(result.force_x);
    forces.y_kcal_per_mol_angstrom = data_or_null(result.force_y);
    forces.z_kcal_per_mol_angstrom = data_or_null(result.force_z);
    require_status(
        bg_context_evaluate(
            context, system, forcefield, &result.energy, &forces),
        BG_STATUS_OK,
        "force evaluation failed");
    require(forces.particle_count == atom_count, "force count was not committed");
    return result;
}

bg_energy_components_v1 evaluate_energy(
    const bg_context *context,
    const bg_system *system,
    const bg_forcefield *forcefield) {
    bg_energy_components_v1 result{};
    require_status(
        bg_energy_components_v1_init(&result),
        BG_STATUS_OK,
        "energy descriptor initialization failed");
    require_status(
        bg_context_evaluate(context, system, forcefield, &result, nullptr),
        BG_STATUS_OK,
        "energy-only evaluation failed");
    return result;
}

void require_energy_only_failure_transactional(
    const bg_context *context,
    const bg_system *system,
    const bg_forcefield *forcefield,
    bg_status expected_status,
    const char *status_message,
    const char *transaction_message) {
    bg_energy_components_v1 output{};
    require_status(
        bg_energy_components_v1_init(&output),
        BG_STATUS_OK,
        "seeded energy descriptor initialization failed");
    output.harmonic_bond_kcal_per_mol = 11.0;
    output.harmonic_angle_kcal_per_mol = 12.0;
    output.periodic_torsion_kcal_per_mol = 13.0;
    output.lennard_jones_kcal_per_mol = 14.0;
    output.coulomb_kcal_per_mol = 15.0;
    output.total_kcal_per_mol = 16.0;
    const bg_energy_components_v1 before = output;
    require_status(
        bg_context_evaluate(
            context, system, forcefield, &output, nullptr),
        expected_status,
        status_message);
    require(
        std::memcmp(&output, &before, sizeof(output)) == 0,
        transaction_message);
}

void require_force_failure_transactional(
    const bg_context *context,
    const bg_system *system,
    const bg_forcefield *forcefield,
    std::size_t atom_count,
    bg_status expected_status,
    const char *status_message,
    const char *transaction_message) {
    bg_energy_components_v1 energy{};
    require_status(
        bg_energy_components_v1_init(&energy),
        BG_STATUS_OK,
        "seeded force-failure energy initialization failed");
    energy.harmonic_bond_kcal_per_mol = 21.0;
    energy.harmonic_angle_kcal_per_mol = 22.0;
    energy.periodic_torsion_kcal_per_mol = 23.0;
    energy.lennard_jones_kcal_per_mol = 24.0;
    energy.coulomb_kcal_per_mol = 25.0;
    energy.total_kcal_per_mol = 26.0;
    const bg_energy_components_v1 energy_before = energy;

    std::vector<double> force_x(atom_count, 31.0);
    std::vector<double> force_y(atom_count, 32.0);
    std::vector<double> force_z(atom_count, 33.0);
    const std::vector<double> force_x_before = force_x;
    const std::vector<double> force_y_before = force_y;
    const std::vector<double> force_z_before = force_z;
    bg_force_soa_v1 forces{};
    require_status(
        bg_force_soa_v1_init(&forces),
        BG_STATUS_OK,
        "seeded force-failure descriptor initialization failed");
    forces.particle_capacity = static_cast<uint64_t>(atom_count);
    forces.particle_count = UINT64_C(777);
    forces.x_kcal_per_mol_angstrom = data_or_null(force_x);
    forces.y_kcal_per_mol_angstrom = data_or_null(force_y);
    forces.z_kcal_per_mol_angstrom = data_or_null(force_z);

    require_status(
        bg_context_evaluate(
            context, system, forcefield, &energy, &forces),
        expected_status,
        status_message);
    require(
        std::memcmp(&energy, &energy_before, sizeof(energy)) == 0 &&
            forces.particle_count == UINT64_C(777) &&
            force_x == force_x_before && force_y == force_y_before &&
            force_z == force_z_before,
        transaction_message);
}

std::array<double, 6> energy_values(
    const bg_energy_components_v1 &energy) noexcept {
    return {{
        energy.harmonic_bond_kcal_per_mol,
        energy.harmonic_angle_kcal_per_mol,
        energy.periodic_torsion_kcal_per_mol,
        energy.lennard_jones_kcal_per_mol,
        energy.coulomb_kcal_per_mol,
        energy.total_kcal_per_mol,
    }};
}

void require_exact_zero(const Evaluation &evaluation, const char *message) {
    for (double component : energy_values(evaluation.energy)) {
        require(bits(component) == bits(0.0), message);
    }
    for (double component : evaluation.force_x) {
        require(bits(component) == bits(0.0), message);
    }
    for (double component : evaluation.force_y) {
        require(bits(component) == bits(0.0), message);
    }
    for (double component : evaluation.force_z) {
        require(bits(component) == bits(0.0), message);
    }
}

void require_energy_near(
    const bg_energy_components_v1 &actual,
    const bg_energy_components_v1 &expected,
    double absolute_tolerance,
    double relative_tolerance,
    const char *message) {
    const auto actual_values = energy_values(actual);
    const auto expected_values = energy_values(expected);
    for (std::size_t index = 0; index < actual_values.size(); ++index) {
        require_near(
            actual_values[index],
            expected_values[index],
            absolute_tolerance,
            relative_tolerance,
            message);
    }
}

void require_evaluation_near(
    const Evaluation &actual,
    const Evaluation &expected,
    double energy_absolute_tolerance,
    double energy_relative_tolerance,
    double force_absolute_tolerance,
    double force_relative_tolerance,
    const char *message) {
    require_energy_near(
        actual.energy,
        expected.energy,
        energy_absolute_tolerance,
        energy_relative_tolerance,
        message);
    require(actual.force_x.size() == expected.force_x.size(), message);
    require(actual.force_y.size() == expected.force_y.size(), message);
    require(actual.force_z.size() == expected.force_z.size(), message);
    for (std::size_t atom = 0; atom < actual.force_x.size(); ++atom) {
        require_near(
            actual.force_x[atom],
            expected.force_x[atom],
            force_absolute_tolerance,
            force_relative_tolerance,
            message);
        require_near(
            actual.force_y[atom],
            expected.force_y[atom],
            force_absolute_tolerance,
            force_relative_tolerance,
            message);
        require_near(
            actual.force_z[atom],
            expected.force_z[atom],
            force_absolute_tolerance,
            force_relative_tolerance,
            message);
    }
}

void require_evaluation_bitwise_equal(
    const Evaluation &actual,
    const Evaluation &expected,
    const char *message) {
    const auto actual_energy = energy_values(actual.energy);
    const auto expected_energy = energy_values(expected.energy);
    for (std::size_t index = 0; index < actual_energy.size(); ++index) {
        require(bits(actual_energy[index]) == bits(expected_energy[index]), message);
    }
    require(actual.force_x.size() == expected.force_x.size(), message);
    require(actual.force_y.size() == expected.force_y.size(), message);
    require(actual.force_z.size() == expected.force_z.size(), message);
    for (std::size_t atom = 0; atom < actual.force_x.size(); ++atom) {
        require(bits(actual.force_x[atom]) == bits(expected.force_x[atom]), message);
        require(bits(actual.force_y[atom]) == bits(expected.force_y[atom]), message);
        require(bits(actual.force_z[atom]) == bits(expected.force_z[atom]), message);
    }
}

ParticleData combined_particles() {
    return ParticleData{
        {7.2, -7.1, -5.6, -4.3, 2.35, 5.9},
        {0.2, 0.0, 0.8, 1.5, -1.2, -2.1},
        {0.1, 0.0, -0.5, 0.4, 1.7, -1.0},
        {12.0, 12.0, 14.0, 16.0, 15.0, 10.0},
        {0.31, -0.24, 0.18, -0.12, 0.27, -0.16},
    };
}

ForceFieldData combined_forcefield() {
    ForceFieldData result;
    result.sigma = {1.42, 1.55, 1.48, 1.61, 1.37, 1.52};
    result.epsilon = {0.18, 0.21, 0.16, 0.24, 0.13, 0.19};

    result.bond_i = {UINT64_C(0), UINT64_C(1), UINT64_C(2)};
    result.bond_j = {UINT64_C(1), UINT64_C(2), UINT64_C(3)};
    result.bond_equilibrium = {1.62, 1.55, 1.47};
    result.bond_force_constant = {32.0, 27.0, 30.0};

    result.angle_i = {UINT64_C(0), UINT64_C(1)};
    result.angle_j = {UINT64_C(1), UINT64_C(2)};
    result.angle_k = {UINT64_C(2), UINT64_C(3)};
    result.angle_equilibrium = {1.91, 1.78};
    result.angle_force_constant = {8.5, 6.75};

    result.torsion_i = {UINT64_C(0)};
    result.torsion_j = {UINT64_C(1)};
    result.torsion_k = {UINT64_C(2)};
    result.torsion_l = {UINT64_C(3)};
    result.torsion_periodicity = {UINT32_C(3)};
    result.torsion_phase = {0.47};
    result.torsion_amplitude = {0.83};

    result.exclusion_i = {UINT64_C(0), UINT64_C(1), UINT64_C(2)};
    result.exclusion_j = {UINT64_C(1), UINT64_C(2), UINT64_C(3)};

    result.scale_i = {UINT64_C(0), UINT64_C(1)};
    result.scale_j = {UINT64_C(4), UINT64_C(5)};
    result.scale_lennard_jones = {0.42, 0.71};
    result.scale_coulomb = {0.63, 0.35};

    result.periodic_axes_mask = BG_PERIODIC_AXES_ALL;
    result.cell_lengths = {{16.0, 17.0, 18.0}};
    result.cutoff = 7.5;
    result.switch_start = 3.5;
    result.dielectric = 2.7;
    result.screening_kappa = 0.23;
    result.minimum_pair_distance = 0.1;
    return result;
}

void test_combined_parity_and_analytic_forces(
    const bg_context *cpu_context,
    const bg_context *hip_context) {
    ParticleData particles = combined_particles();
    const ForceFieldData parameters = combined_forcefield();
    const SystemPtr system = make_system(particles);
    const ForceFieldPtr forcefield = make_forcefield(parameters);

    const Evaluation cpu =
        evaluate_with_forces(cpu_context, system.get(), forcefield.get());
    const Evaluation hip =
        evaluate_with_forces(hip_context, system.get(), forcefield.get());
    require_evaluation_near(
        hip,
        cpu,
        2.0e-10,
        2.0e-10,
        5.0e-8,
        2.0e-9,
        "combined CPU/HIP energy or force parity failed");

    require(
        cpu.energy.harmonic_bond_kcal_per_mol != 0.0,
        "combined bond component vanished");
    require(
        cpu.energy.harmonic_angle_kcal_per_mol != 0.0,
        "combined angle component vanished");
    require(
        cpu.energy.periodic_torsion_kcal_per_mol != 0.0,
        "combined signed torsion component vanished");
    require(
        cpu.energy.lennard_jones_kcal_per_mol != 0.0,
        "combined Lennard-Jones component vanished");
    require(
        cpu.energy.coulomb_kcal_per_mol != 0.0,
        "combined Coulomb component vanished");

    // A deterministic GPU reduction must reproduce all binary64 output bits.
    for (std::size_t repetition = 0; repetition < 24; ++repetition) {
        const Evaluation repeated =
            evaluate_with_forces(hip_context, system.get(), forcefield.get());
        require_evaluation_bitwise_equal(
            repeated, hip, "HIP evaluation was not repeat-deterministic");
    }

    const bg_energy_components_v1 energy_only =
        evaluate_energy(hip_context, system.get(), forcefield.get());
    require_energy_near(
        energy_only,
        hip.energy,
        2.0e-10,
        2.0e-10,
        "HIP energy-only and force evaluation disagreed");

    double net_x = 0.0;
    double net_y = 0.0;
    double net_z = 0.0;
    for (std::size_t atom = 0; atom < hip.force_x.size(); ++atom) {
        net_x += hip.force_x[atom];
        net_y += hip.force_y[atom];
        net_z += hip.force_z[atom];
    }
    require_near(net_x, 0.0, 1.0e-8, 0.0, "HIP net x force was non-zero");
    require_near(net_y, 0.0, 1.0e-8, 0.0, "HIP net y force was non-zero");
    require_near(net_z, 0.0, 1.0e-8, 0.0, "HIP net z force was non-zero");

    constexpr double finite_difference_step = 1.0e-5;
    std::array<std::vector<double> *, 3> coordinates = {
        &particles.x, &particles.y, &particles.z};
    const std::array<const std::vector<double> *, 3> analytic_forces = {
        &hip.force_x, &hip.force_y, &hip.force_z};
    for (std::size_t axis = 0; axis < coordinates.size(); ++axis) {
        for (std::size_t atom = 0; atom < coordinates[axis]->size(); ++atom) {
            const double original = (*coordinates[axis])[atom];
            (*coordinates[axis])[atom] = original + finite_difference_step;
            set_positions(system.get(), particles);
            const double energy_plus =
                evaluate_energy(hip_context, system.get(), forcefield.get())
                    .total_kcal_per_mol;
            (*coordinates[axis])[atom] = original - finite_difference_step;
            set_positions(system.get(), particles);
            const double energy_minus =
                evaluate_energy(hip_context, system.get(), forcefield.get())
                    .total_kcal_per_mol;
            (*coordinates[axis])[atom] = original;
            const double finite_difference =
                -(energy_plus - energy_minus) /
                (2.0 * finite_difference_step);
            require_near(
                (*analytic_forces[axis])[atom],
                finite_difference,
                2.5e-4,
                1.0e-5,
                "HIP analytic force differed from central finite difference");
        }
    }
    set_positions(system.get(), particles);
}

void test_signed_torsion_parity(
    const bg_context *cpu_context,
    const bg_context *hip_context) {
    ParticleData positive{
        {-1.1, 0.0, 1.2, 2.0},
        {0.2, 0.0, 0.4, 1.3},
        {0.3, 0.0, -0.1, 0.8},
        {12.0, 12.0, 14.0, 16.0},
        {0.0, 0.0, 0.0, 0.0},
    };
    ParticleData reflected = positive;
    for (double &coordinate : reflected.z) {
        coordinate = -coordinate;
    }

    ForceFieldData parameters;
    parameters.sigma = {1.0, 1.0, 1.0, 1.0};
    parameters.epsilon = {0.0, 0.0, 0.0, 0.0};
    parameters.torsion_i = {UINT64_C(0)};
    parameters.torsion_j = {UINT64_C(1)};
    parameters.torsion_k = {UINT64_C(2)};
    parameters.torsion_l = {UINT64_C(3)};
    parameters.torsion_periodicity = {UINT32_C(2)};
    parameters.torsion_phase = {0.61};
    parameters.torsion_amplitude = {1.15};

    const ForceFieldPtr forcefield = make_forcefield(parameters);
    const SystemPtr positive_system = make_system(positive);
    const SystemPtr reflected_system = make_system(reflected);
    const Evaluation positive_cpu = evaluate_with_forces(
        cpu_context, positive_system.get(), forcefield.get());
    const Evaluation positive_hip = evaluate_with_forces(
        hip_context, positive_system.get(), forcefield.get());
    const Evaluation reflected_cpu = evaluate_with_forces(
        cpu_context, reflected_system.get(), forcefield.get());
    const Evaluation reflected_hip = evaluate_with_forces(
        hip_context, reflected_system.get(), forcefield.get());

    require_evaluation_near(
        positive_hip,
        positive_cpu,
        2.0e-10,
        2.0e-10,
        5.0e-8,
        2.0e-9,
        "positive signed-torsion CPU/HIP parity failed");
    require_evaluation_near(
        reflected_hip,
        reflected_cpu,
        2.0e-10,
        2.0e-10,
        5.0e-8,
        2.0e-9,
        "reflected signed-torsion CPU/HIP parity failed");
    require(
        std::abs(
            positive_cpu.energy.periodic_torsion_kcal_per_mol -
            reflected_cpu.energy.periodic_torsion_kcal_per_mol) > 1.0e-4,
        "torsion fixture did not distinguish phi from -phi");
}

void test_exclusion_and_periodic_image(
    const bg_context *cpu_context,
    const bg_context *hip_context) {
    const ParticleData periodic_particles{
        {7.6, -7.2},
        {0.3, -0.1},
        {0.2, 0.0},
        {12.0, 16.0},
        {0.41, -0.29},
    };
    const ParticleData direct_particles{
        {0.0, 1.2},
        {0.3, -0.1},
        {0.2, 0.0},
        {12.0, 16.0},
        {0.41, -0.29},
    };
    ForceFieldData periodic_parameters;
    periodic_parameters.sigma = {1.3, 1.5};
    periodic_parameters.epsilon = {0.17, 0.23};
    periodic_parameters.periodic_axes_mask = BG_PERIODIC_AXES_ALL;
    periodic_parameters.cell_lengths = {{16.0, 17.0, 18.0}};
    periodic_parameters.cutoff = 7.5;
    periodic_parameters.switch_start = 1.0;
    periodic_parameters.dielectric = 2.2;
    periodic_parameters.screening_kappa = 0.19;
    ForceFieldData direct_parameters = periodic_parameters;
    direct_parameters.periodic_axes_mask = UINT32_C(0);
    direct_parameters.cell_lengths = {{0.0, 0.0, 0.0}};

    const SystemPtr periodic_system = make_system(periodic_particles);
    const SystemPtr direct_system = make_system(direct_particles);
    const ForceFieldPtr periodic_forcefield =
        make_forcefield(periodic_parameters);
    const ForceFieldPtr direct_forcefield = make_forcefield(direct_parameters);
    const Evaluation periodic_cpu = evaluate_with_forces(
        cpu_context, periodic_system.get(), periodic_forcefield.get());
    const Evaluation periodic_hip = evaluate_with_forces(
        hip_context, periodic_system.get(), periodic_forcefield.get());
    const Evaluation direct_cpu = evaluate_with_forces(
        cpu_context, direct_system.get(), direct_forcefield.get());
    require_evaluation_near(
        periodic_hip,
        periodic_cpu,
        2.0e-10,
        2.0e-10,
        5.0e-8,
        2.0e-9,
        "periodic-image CPU/HIP parity failed");
    require_evaluation_near(
        periodic_hip,
        direct_cpu,
        2.0e-10,
        2.0e-10,
        5.0e-8,
        2.0e-9,
        "minimum image differed from direct image");

    ForceFieldData excluded_parameters = periodic_parameters;
    excluded_parameters.exclusion_i = {UINT64_C(0)};
    excluded_parameters.exclusion_j = {UINT64_C(1)};
    const ForceFieldPtr excluded_forcefield =
        make_forcefield(excluded_parameters);
    const Evaluation excluded_cpu = evaluate_with_forces(
        cpu_context, periodic_system.get(), excluded_forcefield.get());
    const Evaluation excluded_hip = evaluate_with_forces(
        hip_context, periodic_system.get(), excluded_forcefield.get());
    require_evaluation_near(
        excluded_hip,
        excluded_cpu,
        0.0,
        0.0,
        0.0,
        0.0,
        "excluded CPU/HIP result differed");
    for (double component : energy_values(excluded_hip.energy)) {
        require(component == 0.0, "excluded pair contributed energy");
    }
    for (std::size_t atom = 0; atom < excluded_hip.force_x.size(); ++atom) {
        require(
            excluded_hip.force_x[atom] == 0.0 &&
                excluded_hip.force_y[atom] == 0.0 &&
                excluded_hip.force_z[atom] == 0.0,
            "excluded pair contributed force");
    }
}

void test_minimum_distance_precedes_cutoff_and_exclusion(
    const bg_context *cpu_context,
    const bg_context *hip_context) {
    const ParticleData particles{
        {0.0, 1.5},
        {0.0, 0.0},
        {0.0, 0.0},
        {12.0, 16.0},
        {0.35, -0.35},
    };
    ForceFieldData parameters;
    parameters.sigma = {1.2, 1.4};
    parameters.epsilon = {0.2, 0.3};
    parameters.cutoff = 1.0;
    parameters.switch_start = 0.5;
    parameters.minimum_pair_distance = 2.0;

    const SystemPtr system = make_system(particles);
    const ForceFieldPtr forcefield = make_forcefield(parameters);

    require_energy_only_failure_transactional(
        cpu_context,
        system.get(),
        forcefield.get(),
        BG_STATUS_NUMERICAL_ERROR,
        "CPU did not enforce minimum distance before cutoff",
        "CPU minimum-distance failure modified seeded energy output");
    require_energy_only_failure_transactional(
        hip_context,
        system.get(),
        forcefield.get(),
        BG_STATUS_NUMERICAL_ERROR,
        "HIP did not enforce minimum distance before cutoff",
        "HIP minimum-distance failure modified seeded energy output");

    ForceFieldData excluded_parameters = parameters;
    excluded_parameters.exclusion_i = {UINT64_C(0)};
    excluded_parameters.exclusion_j = {UINT64_C(1)};
    const ForceFieldPtr excluded_forcefield =
        make_forcefield(excluded_parameters);
    const bg_energy_components_v1 excluded_cpu = evaluate_energy(
        cpu_context, system.get(), excluded_forcefield.get());
    const bg_energy_components_v1 excluded_hip = evaluate_energy(
        hip_context, system.get(), excluded_forcefield.get());
    for (double component : energy_values(excluded_cpu)) {
        require(
            bits(component) == bits(0.0),
            "CPU excluded close pair contributed non-zero energy");
    }
    for (double component : energy_values(excluded_hip)) {
        require(
            bits(component) == bits(0.0),
            "HIP excluded close pair contributed non-zero energy");
    }
}

void test_exact_cutoff_pair_is_not_dropped(
    const bg_context *cpu_context,
    const bg_context *hip_context) {
    constexpr double cutoff = 0x1.0000000000000p+0;
    constexpr double transverse_delta = 0x1.79f505f35670cp-27;
    const double squared_distance =
        cutoff * cutoff + transverse_delta * transverse_delta;
    require(
        squared_distance == 0x1.0000000000001p+0 &&
            std::sqrt(squared_distance) == cutoff,
        "exact-cutoff regression constants lost their rounding property");

    const ParticleData particles{
        {0.0, cutoff},
        {0.0, transverse_delta},
        {0.0, 0.0},
        {12.0, 16.0},
        {0.0, 0.0},
    };
    ForceFieldData parameters;
    parameters.sigma = {
        0x1.249ad2594c37dp+332, 0x1.249ad2594c37dp+332};
    parameters.epsilon = {1.0, 1.0};
    parameters.cutoff = cutoff;
    parameters.switch_start = 0x1.0000000000000p-1;

    const SystemPtr system = make_system(particles);
    const ForceFieldPtr forcefield = make_forcefield(parameters);
    require_energy_only_failure_transactional(
        cpu_context,
        system.get(),
        forcefield.get(),
        BG_STATUS_NUMERICAL_ERROR,
        "CPU dropped a pair whose rounded distance equals cutoff",
        "CPU exact-cutoff failure modified seeded energy output");
    require_energy_only_failure_transactional(
        hip_context,
        system.get(),
        forcefield.get(),
        BG_STATUS_NUMERICAL_ERROR,
        "HIP cell list dropped a pair whose rounded distance equals cutoff",
        "HIP exact-cutoff failure modified seeded energy output");
}

void test_periodic_minimum_image_overflow_is_not_pruned(
    const bg_context *cpu_context,
    const bg_context *hip_context) {
    const ParticleData particles{
        {0.0, 1.0e154},
        {0.0, 0.0},
        {0.0, 0.0},
        {12.0, 16.0},
        {0.0, 0.0},
    };
    ForceFieldData parameters;
    parameters.sigma = {1.0, 1.0};
    parameters.epsilon = {0.0, 0.0};
    parameters.periodic_axes_mask = BG_PERIODIC_AXIS_X;
    parameters.cell_lengths = {{1.0e-155, 1.0, 1.0}};
    parameters.cutoff = 1.0e-156;
    parameters.switch_start = 0.0;
    parameters.minimum_pair_distance = 1.0e-157;

    const SystemPtr system = make_system(particles);
    const ForceFieldPtr forcefield = make_forcefield(parameters);
    require_energy_only_failure_transactional(
        cpu_context,
        system.get(),
        forcefield.get(),
        BG_STATUS_NUMERICAL_ERROR,
        "CPU accepted an overflowing periodic minimum-image quotient",
        "CPU periodic-quotient failure modified seeded energy output");
    require_energy_only_failure_transactional(
        hip_context,
        system.get(),
        forcefield.get(),
        BG_STATUS_NUMERICAL_ERROR,
        "HIP cell pruning hid an overflowing minimum-image quotient",
        "HIP periodic-quotient failure modified seeded energy output");
}

void test_periodic_phase_cancellation_is_not_pruned(
    const bg_context *cpu_context,
    const bg_context *hip_context) {
    const ParticleData particles{
        {0.0, 0x1.1c37937e08000p+53},
        {0.0, 0.0},
        {0.0, 0.0},
        {12.0, 16.0},
        {0.0, 0.0},
    };
    ForceFieldData parameters;
    parameters.sigma = {1.0, 1.0};
    parameters.epsilon = {0.0, 0.0};
    parameters.periodic_axes_mask = BG_PERIODIC_AXIS_X;
    parameters.cell_lengths = {{0x1.921fb54442d18p+1, 1.0, 1.0}};
    parameters.cutoff = 0x1.999999999999ap-4;
    parameters.switch_start = 0.0;
    parameters.minimum_pair_distance = 0x1.47ae147ae147bp-7;

    const SystemPtr system = make_system(particles);
    const ForceFieldPtr forcefield = make_forcefield(parameters);
    require_energy_only_failure_transactional(
        cpu_context,
        system.get(),
        forcefield.get(),
        BG_STATUS_NUMERICAL_ERROR,
        "CPU did not preserve frozen periodic cancellation arithmetic",
        "CPU periodic-cancellation failure modified seeded energy output");
    require_energy_only_failure_transactional(
        hip_context,
        system.get(),
        forcefield.get(),
        BG_STATUS_NUMERICAL_ERROR,
        "HIP cell phases pruned a frozen periodic-cancellation row",
        "HIP periodic-cancellation failure modified seeded energy output");
}

void test_cell_list_preserves_huge_periodic_pair(
    const bg_context *cpu_context,
    const bg_context *hip_context) {
    constexpr double periodic_length = 0x1.199929a736fa5p+1;
    constexpr double cutoff = 0x1.262d9908dbf62p-2;
    const ParticleData particles{
        {0x1.720b2c0dee5d0p+50, 0x1.720b2c0dee5d1p+50},
        {0.0, 0.0},
        {0.0, 0.0},
        {12.0, 16.0},
        {0.23, -0.17},
    };
    ForceFieldData parameters;
    parameters.sigma = {0.18, 0.22};
    parameters.epsilon = {0.21, 0.27};
    parameters.periodic_axes_mask = BG_PERIODIC_AXIS_X;
    parameters.cell_lengths = {{periodic_length, 4.0, 5.0}};
    parameters.cutoff = cutoff;
    parameters.switch_start = 0x1.0p-3;
    parameters.minimum_pair_distance = 0x1.0p-10;

    const SystemPtr system = make_system(particles);
    const ForceFieldPtr forcefield = make_forcefield(parameters);
    const Evaluation cpu =
        evaluate_with_forces(cpu_context, system.get(), forcefield.get());
    const Evaluation hip =
        evaluate_with_forces(hip_context, system.get(), forcefield.get());
    require_evaluation_near(
        hip,
        cpu,
        2.0e-10,
        2.0e-10,
        5.0e-8,
        2.0e-9,
        "huge-coordinate periodic CPU/HIP parity failed");
    require(
        cpu.energy.total_kcal_per_mol != 0.0,
        "huge-coordinate periodic pair produced zero CPU energy");
    require(
        std::abs(cpu.force_x[0]) > 0.0 &&
            std::abs(cpu.force_x[1]) > 0.0,
        "huge-coordinate periodic pair produced zero CPU force");
}

void test_direct_fallback_avoids_sparse_grid_allocation(
    const bg_context *cpu_context,
    const bg_context *hip_context) {
    const ParticleData particles{
        {0.0, 1.0e12},
        {0.0, 0.0},
        {0.0, 0.0},
        {12.0, 16.0},
        {0.29, -0.31},
    };
    ForceFieldData parameters;
    parameters.sigma = {1.2, 1.4};
    parameters.epsilon = {0.2, 0.3};
    parameters.cutoff = 10.0;
    parameters.switch_start = 8.0;

    const SystemPtr system = make_system(particles);
    const ForceFieldPtr forcefield = make_forcefield(parameters);
    const Evaluation cpu =
        evaluate_with_forces(cpu_context, system.get(), forcefield.get());
    const Evaluation hip =
        evaluate_with_forces(hip_context, system.get(), forcefield.get());
    require_exact_zero(
        cpu,
        "widely separated nonperiodic CPU pair was not exact zero");
    require_exact_zero(
        hip,
        "widely separated nonperiodic HIP pair was not exact zero");
    require_evaluation_bitwise_equal(
        hip,
        cpu,
        "widely separated nonperiodic CPU/HIP results differed");
}

void test_direct_fallback_preserves_pre_cutoff_norm_validation(
    const bg_context *cpu_context,
    const bg_context *hip_context) {
    const ParticleData particles{
        {0.0, 1.0e155},
        {0.0, 0.0},
        {0.0, 0.0},
        {12.0, 16.0},
        {0.0, 0.0},
    };
    ForceFieldData parameters;
    parameters.sigma = {1.0, 1.0};
    parameters.epsilon = {0.0, 0.0};
    parameters.cutoff = 1.0e154;
    parameters.switch_start = 5.0e153;

    const SystemPtr system = make_system(particles);
    const ForceFieldPtr forcefield = make_forcefield(parameters);
    require_energy_only_failure_transactional(
        cpu_context,
        system.get(),
        forcefield.get(),
        BG_STATUS_NUMERICAL_ERROR,
        "CPU squared-norm overflow did not report numerical error",
        "CPU squared-norm overflow modified seeded energy output");
    require_energy_only_failure_transactional(
        hip_context,
        system.get(),
        forcefield.get(),
        BG_STATUS_NUMERICAL_ERROR,
        "HIP direct fallback missed pre-cutoff squared-norm overflow",
        "HIP squared-norm overflow modified seeded energy output");
}

void test_direct_fallback_nonfinite_displacement_and_exclusion(
    const bg_context *cpu_context,
    const bg_context *hip_context) {
    constexpr double maximum = std::numeric_limits<double>::max();
    const ParticleData particles{
        {-maximum, maximum},
        {0.0, 0.0},
        {0.0, 0.0},
        {12.0, 16.0},
        {0.29, -0.31},
    };
    ForceFieldData parameters;
    parameters.sigma = {1.2, 1.4};
    parameters.epsilon = {0.2, 0.3};
    parameters.cutoff = 10.0;
    parameters.switch_start = 8.0;

    const SystemPtr system = make_system(particles);
    const ForceFieldPtr forcefield = make_forcefield(parameters);
    require_energy_only_failure_transactional(
        cpu_context,
        system.get(),
        forcefield.get(),
        BG_STATUS_NUMERICAL_ERROR,
        "CPU non-finite displacement did not report numerical error",
        "CPU non-finite displacement modified seeded energy output");
    require_energy_only_failure_transactional(
        hip_context,
        system.get(),
        forcefield.get(),
        BG_STATUS_NUMERICAL_ERROR,
        "HIP non-finite displacement did not report numerical error",
        "HIP non-finite displacement modified seeded energy output");

    ForceFieldData excluded_parameters = parameters;
    excluded_parameters.exclusion_i = {UINT64_C(0)};
    excluded_parameters.exclusion_j = {UINT64_C(1)};
    const ForceFieldPtr excluded_forcefield =
        make_forcefield(excluded_parameters);
    const Evaluation excluded_cpu = evaluate_with_forces(
        cpu_context, system.get(), excluded_forcefield.get());
    const Evaluation excluded_hip = evaluate_with_forces(
        hip_context, system.get(), excluded_forcefield.get());
    require_exact_zero(
        excluded_cpu,
        "CPU excluded DBL_MAX pair was not exact zero");
    require_exact_zero(
        excluded_hip,
        "HIP excluded DBL_MAX pair was not exact zero");
    require_evaluation_bitwise_equal(
        excluded_hip,
        excluded_cpu,
        "excluded DBL_MAX CPU/HIP results differed");
}

void test_force_reduction_latches_numeric_overflow(
    const bg_context *cpu_context,
    const bg_context *hip_context) {
    const ParticleData particles{
        {0.0, 1.0, 1.0, 1.0, 1.0, 1.5},
        {0.0, 0.0, 0.0, 0.0, 0.0, 0.0},
        {0.0, 0.0, 0.0, 0.0, 0.0, 0.0},
        {12.0, 12.0, 12.0, 12.0, 12.0, 12.0},
        {0.0, 0.0, 0.0, 0.0, 0.0, 0.0},
    };
    ForceFieldData parameters;
    parameters.sigma = {
        5.0e12, 5.0e12, 5.0e12, 5.0e12, 5.0e12, 1.0};
    parameters.epsilon = {
        1.0e154, 1.0e154, 1.0e154, 1.0e154, 1.0e154, 1.0e-154};
    parameters.exclusion_i = {
        UINT64_C(1),
        UINT64_C(1),
        UINT64_C(1),
        UINT64_C(1),
        UINT64_C(2),
        UINT64_C(2),
        UINT64_C(2),
        UINT64_C(3),
        UINT64_C(3),
        UINT64_C(4),
    };
    parameters.exclusion_j = {
        UINT64_C(2),
        UINT64_C(3),
        UINT64_C(4),
        UINT64_C(5),
        UINT64_C(3),
        UINT64_C(4),
        UINT64_C(5),
        UINT64_C(4),
        UINT64_C(5),
        UINT64_C(5),
    };
    parameters.scale_i = {UINT64_C(0)};
    parameters.scale_j = {UINT64_C(5)};
    parameters.scale_lennard_jones = {0.0};
    parameters.scale_coulomb = {0.0};
    parameters.cutoff = 3.0;
    parameters.switch_start = 2.0;
    parameters.minimum_pair_distance = 1.0e-6;

    const SystemPtr system = make_system(particles);
    const ForceFieldPtr forcefield = make_forcefield(parameters);
    const bg_energy_components_v1 cpu_energy =
        evaluate_energy(cpu_context, system.get(), forcefield.get());
    const bg_energy_components_v1 hip_energy =
        evaluate_energy(hip_context, system.get(), forcefield.get());
    require_energy_near(
        hip_energy,
        cpu_energy,
        1.0e292,
        2.0e-10,
        "force-overflow fixture energy-only CPU/HIP parity failed");
    require(
        std::isfinite(cpu_energy.total_kcal_per_mol),
        "force-overflow fixture also overflowed energy");

    require_force_failure_transactional(
        cpu_context,
        system.get(),
        forcefield.get(),
        particles.x.size(),
        BG_STATUS_NUMERICAL_ERROR,
        "CPU force accumulation overflow did not report numerical error",
        "CPU force accumulation overflow modified public outputs");
    require_force_failure_transactional(
        hip_context,
        system.get(),
        forcefield.get(),
        particles.x.size(),
        BG_STATUS_NUMERICAL_ERROR,
        "HIP force reduction dropped an overflowing incidence",
        "HIP force reduction overflow modified public outputs");
}

constexpr std::size_t kEnergyReductionAtomCount = 40;
using ActiveEnergyPairs = std::array<std::array<std::size_t, 2>, 3>;

ForceFieldData make_energy_reduction_forcefield(
    const ActiveEnergyPairs &active_pairs) {
    ForceFieldData parameters;
    parameters.sigma.assign(kEnergyReductionAtomCount, 1.0);
    parameters.epsilon.assign(kEnergyReductionAtomCount, 0.0);
    parameters.cutoff = 2.0;
    parameters.switch_start = 1.5;
    parameters.minimum_pair_distance = 1.0e-6;
    for (std::size_t atom_i = 0; atom_i < kEnergyReductionAtomCount;
         ++atom_i) {
        for (std::size_t atom_j = atom_i + 1;
             atom_j < kEnergyReductionAtomCount;
             ++atom_j) {
            bool active = false;
            for (const auto &pair : active_pairs) {
                active = active ||
                         (pair[0] == atom_i && pair[1] == atom_j);
            }
            if (!active) {
                parameters.exclusion_i.push_back(
                    static_cast<uint64_t>(atom_i));
                parameters.exclusion_j.push_back(
                    static_cast<uint64_t>(atom_j));
            }
        }
    }
    return parameters;
}

ParticleData make_energy_reduction_particles() {
    ParticleData particles;
    particles.x.assign(kEnergyReductionAtomCount, 0.0);
    particles.y.assign(kEnergyReductionAtomCount, 0.0);
    particles.z.assign(kEnergyReductionAtomCount, 0.0);
    particles.mass.assign(kEnergyReductionAtomCount, 1.0);
    particles.charge.assign(kEnergyReductionAtomCount, 0.0);
    return particles;
}

void test_energy_reduction_preserves_serial_overflow_status(
    const bg_context *cpu_context,
    const bg_context *hip_context) {
    constexpr double large_charge = 0x1.0000000000000p+1015;

    {
        const ActiveEnergyPairs active_pairs{{
            {{0, 1}},
            {{16, 25}},
            {{34, 38}},
        }};
        ParticleData particles = make_energy_reduction_particles();
        particles.x[1] = 1.0;
        particles.x[25] = 1.0;
        particles.x[38] = 1.0;
        particles.charge[0] = 1.0;
        particles.charge[1] = -large_charge;
        particles.charge[16] = 1.0;
        particles.charge[25] = large_charge;
        particles.charge[34] = 1.0;
        particles.charge[38] = large_charge;
        const ForceFieldData parameters =
            make_energy_reduction_forcefield(active_pairs);
        const SystemPtr system = make_system(particles);
        const ForceFieldPtr forcefield = make_forcefield(parameters);

        const bg_energy_components_v1 cpu =
            evaluate_energy(cpu_context, system.get(), forcefield.get());
        const bg_energy_components_v1 hip =
            evaluate_energy(hip_context, system.get(), forcefield.get());
        require_energy_near(
            hip,
            cpu,
            0.0,
            0.0,
            "HIP reassociation rejected a CPU-finite energy sequence");
        require(
            std::isfinite(cpu.total_kcal_per_mol) &&
                cpu.total_kcal_per_mol > 0.0,
            "serial-success energy fixture did not produce a finite value");
    }

    {
        const ActiveEnergyPairs active_pairs{{
            {{0, 1}},
            {{7, 12}},
            {{7, 13}},
        }};
        ParticleData particles = make_energy_reduction_particles();
        particles.x[1] = 1.0;
        particles.x[12] = 1.0;
        particles.x[13] = 1.0;
        particles.charge[0] = 1.0;
        particles.charge[1] = large_charge;
        particles.charge[7] = 1.0;
        particles.charge[12] = large_charge;
        particles.charge[13] = -large_charge;
        const ForceFieldData parameters =
            make_energy_reduction_forcefield(active_pairs);
        const SystemPtr system = make_system(particles);
        const ForceFieldPtr forcefield = make_forcefield(parameters);

        require_energy_only_failure_transactional(
            cpu_context,
            system.get(),
            forcefield.get(),
            BG_STATUS_NUMERICAL_ERROR,
            "CPU serial energy overflow fixture unexpectedly succeeded",
            "CPU serial energy overflow modified seeded output");
        require_energy_only_failure_transactional(
            hip_context,
            system.get(),
            forcefield.get(),
            BG_STATUS_NUMERICAL_ERROR,
            "HIP tree reassociation hid a serial energy overflow",
            "HIP serial energy overflow modified seeded output");
    }

    {
        const ActiveEnergyPairs active_pairs{{
            {{7, 11}},
            {{7, 12}},
            {{7, 13}},
        }};
        ParticleData particles = make_energy_reduction_particles();
        particles.x[11] = 1.0;
        particles.x[12] = 1.0;
        particles.x[13] = 1.0;
        particles.charge[7] = 1.0;
        particles.charge[11] =
            1.0e16 / BG_COULOMB_CONSTANT_KCAL_ANGSTROM_PER_MOL_E2;
        particles.charge[12] =
            -1.0e16 / BG_COULOMB_CONSTANT_KCAL_ANGSTROM_PER_MOL_E2;
        particles.charge[13] =
            1.0 / BG_COULOMB_CONSTANT_KCAL_ANGSTROM_PER_MOL_E2;
        const ForceFieldData parameters =
            make_energy_reduction_forcefield(active_pairs);
        const SystemPtr system = make_system(particles);
        const ForceFieldPtr forcefield = make_forcefield(parameters);

        const bg_energy_components_v1 cpu =
            evaluate_energy(cpu_context, system.get(), forcefield.get());
        const bg_energy_components_v1 hip =
            evaluate_energy(hip_context, system.get(), forcefield.get());
        require_energy_near(
            hip,
            cpu,
            1.0e-12,
            1.0e-12,
            "HIP tree lost a small serial residual after cancellation");
        require(
            std::abs(cpu.coulomb_kcal_per_mol) > 0.5,
            "serial cancellation fixture lost its expected residual");
    }
}

bool hip_is_available() {
    uint8_t available = UINT8_C(0);
    require_status(
        bg_backend_is_available(BG_BACKEND_HIP, 0, &available),
        BG_STATUS_OK,
        "HIP availability query failed");
    return available != UINT8_C(0);
}

bool hip_device_is_required() noexcept {
    const char *required = std::getenv("BG_REQUIRE_HIP_DEVICE");
    return required != nullptr && required[0] == '1' && required[1] == '\0';
}

}  // namespace

int main() {
    if (!hip_is_available()) {
        if (hip_device_is_required()) {
            fail_test(
                "BG_REQUIRE_HIP_DEVICE=1 but no HIP device is available at "
                "ordinal zero");
        }
        std::puts("SKIP: no HIP device is available at ordinal zero");
        return 77;
    }

    const ContextPtr cpu_context = make_context(BG_BACKEND_CPU);
    const ContextPtr hip_context = make_context(BG_BACKEND_HIP);
    test_combined_parity_and_analytic_forces(
        cpu_context.get(), hip_context.get());
    test_signed_torsion_parity(cpu_context.get(), hip_context.get());
    test_exclusion_and_periodic_image(cpu_context.get(), hip_context.get());
    test_minimum_distance_precedes_cutoff_and_exclusion(
        cpu_context.get(), hip_context.get());
    test_exact_cutoff_pair_is_not_dropped(
        cpu_context.get(), hip_context.get());
    test_periodic_minimum_image_overflow_is_not_pruned(
        cpu_context.get(), hip_context.get());
    test_periodic_phase_cancellation_is_not_pruned(
        cpu_context.get(), hip_context.get());
    test_cell_list_preserves_huge_periodic_pair(
        cpu_context.get(), hip_context.get());
    test_direct_fallback_avoids_sparse_grid_allocation(
        cpu_context.get(), hip_context.get());
    test_direct_fallback_preserves_pre_cutoff_norm_validation(
        cpu_context.get(), hip_context.get());
    test_direct_fallback_nonfinite_displacement_and_exclusion(
        cpu_context.get(), hip_context.get());
    test_force_reduction_latches_numeric_overflow(
        cpu_context.get(), hip_context.get());
    test_energy_reduction_preserves_serial_overflow_status(
        cpu_context.get(), hip_context.get());
    std::puts("HIP evaluator tests passed");
    return 0;
}
