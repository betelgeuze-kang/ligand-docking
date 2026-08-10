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
#include <type_traits>
#include <utility>
#include <vector>

namespace {

[[noreturn]] void fail_test(const char *message) {
    std::fprintf(stderr, "cpu evaluator test failure: %s\n", message);
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
            "cpu evaluator test failure: %s (expected %d, observed %d: %s)\n",
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

void require_exact(double actual, double expected, const char *message) {
    require(bits(actual) == bits(expected), message);
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
    require(std::isfinite(actual), message);
    require(std::abs(actual - expected) <= tolerance, message);
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
            "particle test channels have inconsistent lengths");
        bg_particle_soa result{};
        require_status(
            bg_particle_soa_init(&result),
            BG_STATUS_OK,
            "particle descriptor initializer failed");
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
            "force-field descriptor initializer failed");
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

ContextPtr make_cpu_context() {
    bg_context_options options{};
    require_status(
        bg_context_options_init(&options),
        BG_STATUS_OK,
        "context options initializer failed");
    options.backend = BG_BACKEND_CPU;
    bg_context *raw = nullptr;
    require_status(
        bg_context_create(&options, &raw),
        BG_STATUS_OK,
        "CPU context creation failed");
    require(raw != nullptr, "CPU context creation returned null");
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
        "position descriptor initializer failed");
    descriptor.particle_count = static_cast<uint64_t>(particles.x.size());
    descriptor.x_angstrom = data_or_null(particles.x);
    descriptor.y_angstrom = data_or_null(particles.y);
    descriptor.z_angstrom = data_or_null(particles.z);
    require_status(
        bg_system_set_positions(system, &descriptor),
        BG_STATUS_OK,
        "position replacement failed");
}

struct Evaluation final {
    bg_energy_components_v1 energy{};
    std::vector<double> force_x;
    std::vector<double> force_y;
    std::vector<double> force_z;
};

Evaluation evaluate_with_forces(
    const bg_context *context,
    const bg_system *system,
    const bg_forcefield *forcefield) {
    uint64_t atom_count = UINT64_C(0);
    require_status(
        bg_forcefield_get_atom_count(forcefield, &atom_count),
        BG_STATUS_OK,
        "force-field atom count query failed");
    require(
        atom_count <= static_cast<uint64_t>(std::numeric_limits<std::size_t>::max()),
        "test force-field count does not fit size_t");
    const std::size_t count = static_cast<std::size_t>(atom_count);

    Evaluation result;
    result.force_x.assign(count, 0.0);
    result.force_y.assign(count, 0.0);
    result.force_z.assign(count, 0.0);
    require_status(
        bg_energy_components_v1_init(&result.energy),
        BG_STATUS_OK,
        "energy descriptor initializer failed");
    bg_force_soa_v1 forces{};
    require_status(
        bg_force_soa_v1_init(&forces),
        BG_STATUS_OK,
        "force descriptor initializer failed");
    forces.particle_capacity = atom_count;
    forces.x_kcal_per_mol_angstrom = data_or_null(result.force_x);
    forces.y_kcal_per_mol_angstrom = data_or_null(result.force_y);
    forces.z_kcal_per_mol_angstrom = data_or_null(result.force_z);
    require_status(
        bg_context_evaluate(
            context, system, forcefield, &result.energy, &forces),
        BG_STATUS_OK,
        "CPU force evaluation failed");
    require(forces.particle_count == atom_count, "force count was not committed");
    return result;
}

double evaluate_energy(
    const bg_context *context,
    const bg_system *system,
    const bg_forcefield *forcefield) {
    bg_energy_components_v1 energy{};
    require_status(
        bg_energy_components_v1_init(&energy),
        BG_STATUS_OK,
        "energy descriptor initializer failed");
    require_status(
        bg_context_evaluate(context, system, forcefield, &energy, nullptr),
        BG_STATUS_OK,
        "CPU energy evaluation failed");
    return energy.total_kcal_per_mol;
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

void require_energy_bitwise_equal(
    const bg_energy_components_v1 &actual,
    const bg_energy_components_v1 &expected,
    const char *message) {
    const auto actual_values = energy_values(actual);
    const auto expected_values = energy_values(expected);
    for (std::size_t index = 0; index < actual_values.size(); ++index) {
        require(bits(actual_values[index]) == bits(expected_values[index]), message);
    }
}

void require_evaluation_bitwise_equal(
    const Evaluation &actual,
    const Evaluation &expected,
    const char *message) {
    require_energy_bitwise_equal(actual.energy, expected.energy, message);
    require(actual.force_x.size() == expected.force_x.size(), message);
    require(actual.force_y.size() == expected.force_y.size(), message);
    require(actual.force_z.size() == expected.force_z.size(), message);
    for (std::size_t atom = 0; atom < actual.force_x.size(); ++atom) {
        require(bits(actual.force_x[atom]) == bits(expected.force_x[atom]), message);
        require(bits(actual.force_y[atom]) == bits(expected.force_y[atom]), message);
        require(bits(actual.force_z[atom]) == bits(expected.force_z[atom]), message);
    }
}

void set_energy_sentinel(bg_energy_components_v1 *energy) {
    require_status(
        bg_energy_components_v1_init(energy),
        BG_STATUS_OK,
        "energy descriptor initializer failed");
    energy->harmonic_bond_kcal_per_mol = 101.25;
    energy->harmonic_angle_kcal_per_mol = 102.25;
    energy->periodic_torsion_kcal_per_mol = 103.25;
    energy->lennard_jones_kcal_per_mol = 104.25;
    energy->coulomb_kcal_per_mol = 105.25;
    energy->total_kcal_per_mol = 106.25;
}

bg_force_soa_v1 make_force_output(
    std::vector<double> *x,
    std::vector<double> *y,
    std::vector<double> *z,
    uint64_t capacity) {
    bg_force_soa_v1 result{};
    require_status(
        bg_force_soa_v1_init(&result),
        BG_STATUS_OK,
        "force descriptor initializer failed");
    result.particle_capacity = capacity;
    result.particle_count = UINT64_C(777);
    result.x_kcal_per_mol_angstrom = data_or_null(*x);
    result.y_kcal_per_mol_angstrom = data_or_null(*y);
    result.z_kcal_per_mol_angstrom = data_or_null(*z);
    return result;
}

void require_unchanged(
    const bg_energy_components_v1 &energy,
    const bg_energy_components_v1 &energy_before,
    const bg_force_soa_v1 &forces,
    uint64_t force_count_before,
    const std::vector<double> &force_x,
    const std::vector<double> &force_x_before,
    const std::vector<double> &force_y,
    const std::vector<double> &force_y_before,
    const std::vector<double> &force_z,
    const std::vector<double> &force_z_before,
    const char *message) {
    require_energy_bitwise_equal(energy, energy_before, message);
    require(forces.particle_count == force_count_before, message);
    require(force_x == force_x_before, message);
    require(force_y == force_y_before, message);
    require(force_z == force_z_before, message);
}

void test_descriptor_initializers_and_exact_bond(const bg_context *context) {
    static_assert(std::is_standard_layout_v<bg_forcefield_soa_v1>);
    static_assert(std::is_standard_layout_v<bg_force_soa_v1>);
    static_assert(std::is_standard_layout_v<bg_energy_components_v1>);
    static_assert(noexcept(bg_forcefield_destroy(nullptr)));

    bg_forcefield_soa_v1 forcefield_descriptor{};
    require_status(
        bg_forcefield_soa_v1_init(&forcefield_descriptor),
        BG_STATUS_OK,
        "force-field descriptor init failed");
    require(
        forcefield_descriptor.struct_size == sizeof(bg_forcefield_soa_v1),
        "force-field descriptor size was not initialized");
    require(
        forcefield_descriptor.abi_version == BG_ABI_VERSION,
        "force-field descriptor ABI was not initialized");
    require(
        forcefield_descriptor.unit_system ==
            BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL,
        "force-field descriptor units were not initialized");
    for (uint64_t value : forcefield_descriptor.reserved) {
        require(value == UINT64_C(0), "force-field reserved field was not zeroed");
    }

    bg_force_soa_v1 force_descriptor{};
    require_status(
        bg_force_soa_v1_init(&force_descriptor),
        BG_STATUS_OK,
        "force output descriptor init failed");
    require(
        force_descriptor.struct_size == sizeof(bg_force_soa_v1) &&
            force_descriptor.abi_version == BG_ABI_VERSION,
        "force output descriptor header was not initialized");

    bg_energy_components_v1 energy_descriptor{};
    require_status(
        bg_energy_components_v1_init(&energy_descriptor),
        BG_STATUS_OK,
        "energy output descriptor init failed");
    require(
        energy_descriptor.struct_size == sizeof(bg_energy_components_v1) &&
            energy_descriptor.abi_version == BG_ABI_VERSION,
        "energy output descriptor header was not initialized");

    ParticleData particles{
        {0.0, 2.0},
        {0.0, 0.0},
        {0.0, 0.0},
        {12.0, 1.0},
        {0.0, 0.0},
    };
    ForceFieldData parameters;
    parameters.sigma = {1.0, 1.0};
    parameters.epsilon = {0.0, 0.0};
    parameters.bond_i = {UINT64_C(0)};
    parameters.bond_j = {UINT64_C(1)};
    parameters.bond_equilibrium = {1.0};
    parameters.bond_force_constant = {4.0};

    SystemPtr system = make_system(particles);
    ForceFieldPtr forcefield = make_forcefield(parameters);
    uint64_t atom_count = UINT64_C(0);
    require_status(
        bg_forcefield_get_atom_count(forcefield.get(), &atom_count),
        BG_STATUS_OK,
        "force-field count query failed");
    require(atom_count == UINT64_C(2), "force-field count was incorrect");

    // Both opaque handles must own copies rather than borrowing these arrays.
    particles.x[1] = 200.0;
    particles.mass[0] = 99.0;
    parameters.sigma[0] = 9.0;
    parameters.bond_equilibrium[0] = 7.0;
    parameters.bond_force_constant[0] = 400.0;

    const Evaluation result =
        evaluate_with_forces(context, system.get(), forcefield.get());
    require_exact(
        result.energy.harmonic_bond_kcal_per_mol,
        2.0,
        "exact bond energy differed");
    require(result.energy.harmonic_angle_kcal_per_mol == 0.0, "angle leaked");
    require(result.energy.periodic_torsion_kcal_per_mol == 0.0, "torsion leaked");
    require(result.energy.lennard_jones_kcal_per_mol == 0.0, "LJ leaked");
    require(result.energy.coulomb_kcal_per_mol == 0.0, "Coulomb leaked");
    require_exact(result.energy.total_kcal_per_mol, 2.0, "bond total differed");
    require_exact(result.force_x[0], 4.0, "bond force on atom zero differed");
    require_exact(result.force_x[1], -4.0, "bond force on atom one differed");
    require(result.force_y[0] == 0.0 && result.force_y[1] == 0.0, "bond y force leaked");
    require(result.force_z[0] == 0.0 && result.force_z[1] == 0.0, "bond z force leaked");
}

void test_exact_lennard_jones(const bg_context *context) {
    const ParticleData particles{
        {0.0, 2.0},
        {0.0, 0.0},
        {0.0, 0.0},
        {1.0, 1.0},
        {0.0, 0.0},
    };
    ForceFieldData parameters;
    parameters.sigma = {1.0, 1.0};
    parameters.epsilon = {1.0, 1.0};
    const SystemPtr system = make_system(particles);
    const ForceFieldPtr forcefield = make_forcefield(parameters);
    const Evaluation result =
        evaluate_with_forces(context, system.get(), forcefield.get());

    constexpr double expected_energy = -63.0 / 1024.0;
    constexpr double expected_force = 93.0 / 512.0;
    require_exact(
        result.energy.lennard_jones_kcal_per_mol,
        expected_energy,
        "exact LJ energy differed");
    require_exact(
        result.energy.total_kcal_per_mol,
        expected_energy,
        "exact LJ total differed");
    require_exact(result.force_x[0], expected_force, "exact LJ force differed");
    require_exact(result.force_x[1], -expected_force, "opposite LJ force differed");
}

void test_combined_finite_difference_and_determinism(
    const bg_context *context) {
    ParticleData particles{
        {-1.1, 0.0, 1.2, 2.0},
        {0.2, 0.0, 0.4, 1.3},
        {0.3, 0.0, -0.1, 0.8},
        {12.0, 12.0, 14.0, 16.0},
        {0.30, -0.20, 0.15, -0.10},
    };
    ForceFieldData parameters;
    parameters.sigma = {0.90, 0.95, 1.10, 1.05};
    parameters.epsilon = {0.12, 0.18, 0.15, 0.20};
    parameters.bond_i = {UINT64_C(0), UINT64_C(1), UINT64_C(2)};
    parameters.bond_j = {UINT64_C(1), UINT64_C(2), UINT64_C(3)};
    parameters.bond_equilibrium = {1.05, 1.15, 1.30};
    parameters.bond_force_constant = {35.0, 28.0, 31.0};
    parameters.angle_i = {UINT64_C(0), UINT64_C(1)};
    parameters.angle_j = {UINT64_C(1), UINT64_C(2)};
    parameters.angle_k = {UINT64_C(2), UINT64_C(3)};
    parameters.angle_equilibrium = {1.75, 1.65};
    parameters.angle_force_constant = {9.0, 7.0};
    parameters.torsion_i = {UINT64_C(0)};
    parameters.torsion_j = {UINT64_C(1)};
    parameters.torsion_k = {UINT64_C(2)};
    parameters.torsion_l = {UINT64_C(3)};
    parameters.torsion_periodicity = {UINT32_C(3)};
    parameters.torsion_phase = {0.4};
    parameters.torsion_amplitude = {0.7};
    parameters.scale_i = {UINT64_C(0)};
    parameters.scale_j = {UINT64_C(3)};
    parameters.scale_lennard_jones = {0.65};
    parameters.scale_coulomb = {0.40};
    parameters.cutoff = 4.5;
    parameters.switch_start = 1.4;
    parameters.dielectric = 3.0;
    parameters.screening_kappa = 0.35;
    parameters.minimum_pair_distance = 0.2;

    const double far_dx = particles.x[0] - particles.x[3];
    const double far_dy = particles.y[0] - particles.y[3];
    const double far_dz = particles.z[0] - particles.z[3];
    const double far_distance =
        std::sqrt(far_dx * far_dx + far_dy * far_dy + far_dz * far_dz);
    require(
        far_distance > parameters.switch_start && far_distance < parameters.cutoff,
        "combined fixture has no switched long pair");

    const SystemPtr system = make_system(particles);
    const ForceFieldPtr forcefield = make_forcefield(parameters);
    const Evaluation baseline =
        evaluate_with_forces(context, system.get(), forcefield.get());
    require(
        baseline.energy.harmonic_bond_kcal_per_mol != 0.0,
        "combined bond component vanished");
    require(
        baseline.energy.harmonic_angle_kcal_per_mol != 0.0,
        "combined angle component vanished");
    require(
        baseline.energy.periodic_torsion_kcal_per_mol != 0.0,
        "combined torsion component vanished");
    require(
        baseline.energy.lennard_jones_kcal_per_mol != 0.0,
        "combined LJ component vanished");
    require(
        baseline.energy.coulomb_kcal_per_mol != 0.0,
        "combined screened Coulomb component vanished");

    for (std::size_t repetition = 0; repetition < 64; ++repetition) {
        const Evaluation repeated =
            evaluate_with_forces(context, system.get(), forcefield.get());
        require_evaluation_bitwise_equal(
            repeated,
            baseline,
            "CPU evaluation was not bitwise deterministic");
    }

    double net_x = 0.0;
    double net_y = 0.0;
    double net_z = 0.0;
    for (std::size_t atom = 0; atom < baseline.force_x.size(); ++atom) {
        net_x += baseline.force_x[atom];
        net_y += baseline.force_y[atom];
        net_z += baseline.force_z[atom];
    }
    require_near(net_x, 0.0, 1.0e-11, 0.0, "net x force was non-zero");
    require_near(net_y, 0.0, 1.0e-11, 0.0, "net y force was non-zero");
    require_near(net_z, 0.0, 1.0e-11, 0.0, "net z force was non-zero");

    constexpr double step = 1.0e-6;
    std::array<std::vector<double> *, 3> coordinates = {
        &particles.x, &particles.y, &particles.z};
    const std::array<const std::vector<double> *, 3> analytic_forces = {
        &baseline.force_x, &baseline.force_y, &baseline.force_z};
    for (std::size_t axis = 0; axis < coordinates.size(); ++axis) {
        for (std::size_t atom = 0; atom < coordinates[axis]->size(); ++atom) {
            const double original = (*coordinates[axis])[atom];
            (*coordinates[axis])[atom] = original + step;
            set_positions(system.get(), particles);
            const double energy_plus =
                evaluate_energy(context, system.get(), forcefield.get());
            (*coordinates[axis])[atom] = original - step;
            set_positions(system.get(), particles);
            const double energy_minus =
                evaluate_energy(context, system.get(), forcefield.get());
            (*coordinates[axis])[atom] = original;
            const double finite_difference =
                -(energy_plus - energy_minus) / (2.0 * step);
            require_near(
                (*analytic_forces[axis])[atom],
                finite_difference,
                4.0e-5,
                8.0e-6,
                "analytic force differed from central finite difference");
        }
    }
    set_positions(system.get(), particles);
    const Evaluation restored =
        evaluate_with_forces(context, system.get(), forcefield.get());
    require_evaluation_bitwise_equal(
        restored,
        baseline,
        "restoring coordinates did not restore bitwise outputs");
}

void test_periodic_image_parity(const bg_context *context) {
    const ParticleData periodic_particles{
        {0.0, 9.0},
        {0.0, 0.0},
        {0.0, 0.0},
        {1.0, 1.0},
        {0.4, -0.3},
    };
    const ParticleData direct_particles{
        {0.0, -1.0},
        {0.0, 0.0},
        {0.0, 0.0},
        {1.0, 1.0},
        {0.4, -0.3},
    };
    ForceFieldData periodic_parameters;
    periodic_parameters.sigma = {0.7, 1.3};
    periodic_parameters.epsilon = {0.2, 0.8};
    periodic_parameters.periodic_axes_mask = BG_PERIODIC_AXIS_X;
    periodic_parameters.cell_lengths = {{10.0, 11.0, 12.0}};
    periodic_parameters.cutoff = 4.0;
    periodic_parameters.switch_start = 3.5;
    periodic_parameters.dielectric = 2.0;
    periodic_parameters.screening_kappa = 0.2;
    ForceFieldData direct_parameters = periodic_parameters;
    direct_parameters.periodic_axes_mask = UINT32_C(0);
    direct_parameters.cell_lengths = {{0.0, 0.0, 0.0}};

    const SystemPtr periodic_system = make_system(periodic_particles);
    const SystemPtr direct_system = make_system(direct_particles);
    const ForceFieldPtr periodic_forcefield =
        make_forcefield(periodic_parameters);
    const ForceFieldPtr direct_forcefield = make_forcefield(direct_parameters);
    const Evaluation periodic = evaluate_with_forces(
        context, periodic_system.get(), periodic_forcefield.get());
    const Evaluation direct = evaluate_with_forces(
        context, direct_system.get(), direct_forcefield.get());
    require_evaluation_bitwise_equal(
        periodic,
        direct,
        "minimum-image evaluation differed from its direct image");

    // The canonical half-box rule maps +L/2 to -L/2.  A bonded term is used
    // because the nonbonded cutoff must remain strictly below L/2.
    const ParticleData half_box_particles{
        {0.0, -5.0},
        {0.0, 0.0},
        {0.0, 0.0},
        {1.0, 1.0},
        {0.0, 0.0},
    };
    const ParticleData negative_half_image{
        {0.0, 5.0},
        {0.0, 0.0},
        {0.0, 0.0},
        {1.0, 1.0},
        {0.0, 0.0},
    };
    ForceFieldData half_box_parameters;
    half_box_parameters.sigma = {1.0, 1.0};
    half_box_parameters.epsilon = {0.0, 0.0};
    half_box_parameters.bond_i = {UINT64_C(0)};
    half_box_parameters.bond_j = {UINT64_C(1)};
    half_box_parameters.bond_equilibrium = {4.0};
    half_box_parameters.bond_force_constant = {2.0};
    half_box_parameters.periodic_axes_mask = BG_PERIODIC_AXIS_X;
    half_box_parameters.cell_lengths = {{10.0, 11.0, 12.0}};
    half_box_parameters.cutoff = 4.0;
    half_box_parameters.switch_start = 3.5;
    ForceFieldData negative_half_parameters = half_box_parameters;
    negative_half_parameters.periodic_axes_mask = UINT32_C(0);
    negative_half_parameters.cell_lengths = {{0.0, 0.0, 0.0}};

    const SystemPtr half_box_system = make_system(half_box_particles);
    const SystemPtr negative_half_system = make_system(negative_half_image);
    const ForceFieldPtr half_box_forcefield =
        make_forcefield(half_box_parameters);
    const ForceFieldPtr negative_half_forcefield =
        make_forcefield(negative_half_parameters);
    const Evaluation half_box = evaluate_with_forces(
        context, half_box_system.get(), half_box_forcefield.get());
    const Evaluation negative_half = evaluate_with_forces(
        context, negative_half_system.get(), negative_half_forcefield.get());
    require_evaluation_bitwise_equal(
        half_box,
        negative_half,
        "half-box tie did not map to the canonical negative image");
}

void test_excluded_coincident_pair(const bg_context *context) {
    const ParticleData particles{
        {0.0, 0.0},
        {0.0, 0.0},
        {0.0, 0.0},
        {1.0, 1.0},
        {1.0, -1.0},
    };
    ForceFieldData parameters;
    parameters.sigma = {1.0, 1.0};
    parameters.epsilon = {1.0, 1.0};
    parameters.exclusion_i = {UINT64_C(1)};
    parameters.exclusion_j = {UINT64_C(0)};
    parameters.minimum_pair_distance = 0.5;
    const SystemPtr system = make_system(particles);
    const ForceFieldPtr forcefield = make_forcefield(parameters);
    const Evaluation result =
        evaluate_with_forces(context, system.get(), forcefield.get());
    for (double value : energy_values(result.energy)) {
        require(value == 0.0, "excluded coincident pair produced energy");
    }
    for (std::size_t atom = 0; atom < result.force_x.size(); ++atom) {
        require(
            result.force_x[atom] == 0.0 && result.force_y[atom] == 0.0 &&
                result.force_z[atom] == 0.0,
            "excluded coincident pair produced force");
    }
}

void test_descriptor_and_count_failures() {
    ForceFieldData valid_parameters;
    valid_parameters.sigma = {1.0};
    valid_parameters.epsilon = {0.0};

    bg_forcefield_soa_v1 wrong_abi = valid_parameters.descriptor();
    wrong_abi.abi_version += UINT32_C(1);
    bg_forcefield *raw_forcefield = nullptr;
    require_status(
        bg_forcefield_create(&wrong_abi, &raw_forcefield),
        BG_STATUS_ABI_MISMATCH,
        "force-field ABI mismatch was not rejected");
    require(raw_forcefield == nullptr, "failed force-field creation returned a handle");

    bg_forcefield_soa_v1 reserved = valid_parameters.descriptor();
    reserved.reserved[1] = UINT64_C(1);
    require_status(
        bg_forcefield_create(&reserved, &raw_forcefield),
        BG_STATUS_INVALID_ARGUMENT,
        "force-field reserved field was not rejected");
    require(raw_forcefield == nullptr, "reserved failure returned a handle");

    bg_forcefield_soa_v1 overflowing = valid_parameters.descriptor();
    overflowing.atom_count = UINT64_MAX;
    require_status(
        bg_forcefield_create(&overflowing, &raw_forcefield),
        BG_STATUS_CAPACITY_OVERFLOW,
        "overflowing force-field atom count was not rejected");
    require(raw_forcefield == nullptr, "overflowing count returned a handle");

    bg_forcefield_soa_v1 missing_channels = valid_parameters.descriptor();
    missing_channels.bond_count = UINT64_C(1);
    require_status(
        bg_forcefield_create(&missing_channels, &raw_forcefield),
        BG_STATUS_INVALID_ARGUMENT,
        "non-zero term count without channels was not rejected");
    require(raw_forcefield == nullptr, "missing channels returned a handle");
}

void test_output_validation_and_transactionality(const bg_context *context) {
    const ParticleData particles{
        {0.0, 2.0},
        {0.0, 0.0},
        {0.0, 0.0},
        {1.0, 1.0},
        {0.0, 0.0},
    };
    ForceFieldData parameters;
    parameters.sigma = {1.0, 1.0};
    parameters.epsilon = {1.0, 1.0};
    const SystemPtr system = make_system(particles);
    const ForceFieldPtr forcefield = make_forcefield(parameters);

    auto run_output_failure = [&](bg_energy_components_v1 *energy,
                                  bg_force_soa_v1 *forces,
                                  bg_status expected,
                                  const char *message) {
        const bg_energy_components_v1 energy_before = *energy;
        const uint64_t force_count_before = forces->particle_count;
        const std::vector<double> force_x_before(
            forces->x_kcal_per_mol_angstrom,
            forces->x_kcal_per_mol_angstrom + 2);
        const std::vector<double> force_y_before(
            forces->y_kcal_per_mol_angstrom,
            forces->y_kcal_per_mol_angstrom + 2);
        const std::vector<double> force_z_before(
            forces->z_kcal_per_mol_angstrom,
            forces->z_kcal_per_mol_angstrom + 2);
        require_status(
            bg_context_evaluate(
                context, system.get(), forcefield.get(), energy, forces),
            expected,
            message);
        const std::vector<double> force_x_after(
            forces->x_kcal_per_mol_angstrom,
            forces->x_kcal_per_mol_angstrom + 2);
        const std::vector<double> force_y_after(
            forces->y_kcal_per_mol_angstrom,
            forces->y_kcal_per_mol_angstrom + 2);
        const std::vector<double> force_z_after(
            forces->z_kcal_per_mol_angstrom,
            forces->z_kcal_per_mol_angstrom + 2);
        require_unchanged(
            *energy,
            energy_before,
            *forces,
            force_count_before,
            force_x_after,
            force_x_before,
            force_y_after,
            force_y_before,
            force_z_after,
            force_z_before,
            message);
    };

    {
        bg_energy_components_v1 energy{};
        set_energy_sentinel(&energy);
        std::vector<double> x(2, 201.5);
        std::vector<double> y(2, 202.5);
        std::vector<double> z(2, 203.5);
        bg_force_soa_v1 forces = make_force_output(&x, &y, &z, UINT64_C(2));
        energy.abi_version += UINT32_C(1);
        run_output_failure(
            &energy,
            &forces,
            BG_STATUS_ABI_MISMATCH,
            "energy ABI mismatch did not preserve outputs");
    }
    {
        bg_energy_components_v1 energy{};
        set_energy_sentinel(&energy);
        std::vector<double> x(2, 211.5);
        std::vector<double> y(2, 212.5);
        std::vector<double> z(2, 213.5);
        bg_force_soa_v1 forces = make_force_output(&x, &y, &z, UINT64_C(2));
        energy.reserved[0] = UINT64_C(1);
        run_output_failure(
            &energy,
            &forces,
            BG_STATUS_INVALID_ARGUMENT,
            "energy reserved field did not preserve outputs");
    }
    {
        bg_energy_components_v1 energy{};
        set_energy_sentinel(&energy);
        std::vector<double> x(2, 221.5);
        std::vector<double> y(2, 222.5);
        std::vector<double> z(2, 223.5);
        bg_force_soa_v1 forces = make_force_output(&x, &y, &z, UINT64_C(2));
        forces.reserved[0] = UINT64_C(1);
        run_output_failure(
            &energy,
            &forces,
            BG_STATUS_INVALID_ARGUMENT,
            "force reserved field did not preserve outputs");
    }
    {
        bg_energy_components_v1 energy{};
        set_energy_sentinel(&energy);
        std::vector<double> x(2, 231.5);
        std::vector<double> y(2, 232.5);
        std::vector<double> z(2, 233.5);
        bg_force_soa_v1 forces = make_force_output(&x, &y, &z, UINT64_C(1));
        run_output_failure(
            &energy,
            &forces,
            BG_STATUS_BUFFER_TOO_SMALL,
            "small force buffer did not preserve outputs");
    }
    {
        bg_energy_components_v1 energy{};
        set_energy_sentinel(&energy);
        const bg_energy_components_v1 energy_before = energy;
        std::vector<double> shared(2, 234.5);
        std::vector<double> z(2, 235.5);
        const std::vector<double> shared_before = shared;
        const std::vector<double> z_before = z;
        bg_force_soa_v1 forces{};
        require_status(
            bg_force_soa_v1_init(&forces),
            BG_STATUS_OK,
            "force descriptor initializer failed");
        forces.particle_capacity = UINT64_C(2);
        forces.particle_count = UINT64_C(777);
        forces.x_kcal_per_mol_angstrom = shared.data();
        forces.y_kcal_per_mol_angstrom = shared.data();
        forces.z_kcal_per_mol_angstrom = z.data();
        require_status(
            bg_context_evaluate(
                context, system.get(), forcefield.get(), &energy, &forces),
            BG_STATUS_INVALID_ARGUMENT,
            "overlapping force channels were not rejected");
        require_energy_bitwise_equal(
            energy, energy_before, "overlapping outputs changed energy");
        require(
            forces.particle_count == UINT64_C(777),
            "overlapping outputs changed force count");
        require(
            shared == shared_before && z == z_before,
            "overlapping outputs changed force buffers");
    }

    ForceFieldData three_parameters;
    three_parameters.sigma = {1.0, 1.0, 1.0};
    three_parameters.epsilon = {0.0, 0.0, 0.0};
    const ForceFieldPtr three_forcefield = make_forcefield(three_parameters);
    bg_energy_components_v1 count_energy{};
    set_energy_sentinel(&count_energy);
    const bg_energy_components_v1 count_energy_before = count_energy;
    std::vector<double> count_x(3, 241.5);
    std::vector<double> count_y(3, 242.5);
    std::vector<double> count_z(3, 243.5);
    const std::vector<double> count_x_before = count_x;
    const std::vector<double> count_y_before = count_y;
    const std::vector<double> count_z_before = count_z;
    bg_force_soa_v1 count_forces =
        make_force_output(&count_x, &count_y, &count_z, UINT64_C(3));
    const uint64_t count_before = count_forces.particle_count;
    require_status(
        bg_context_evaluate(
            context,
            system.get(),
            three_forcefield.get(),
            &count_energy,
            &count_forces),
        BG_STATUS_INVALID_ARGUMENT,
        "system/force-field count mismatch was not rejected");
    require_unchanged(
        count_energy,
        count_energy_before,
        count_forces,
        count_before,
        count_x,
        count_x_before,
        count_y,
        count_y_before,
        count_z,
        count_z_before,
        "count mismatch changed outputs");
}

void test_numerical_failures_are_transactional(const bg_context *context) {
    const ParticleData zero_bond_particles{
        {0.0, 0.0},
        {0.0, 0.0},
        {0.0, 0.0},
        {1.0, 1.0},
        {0.0, 0.0},
    };
    ForceFieldData zero_bond_parameters;
    zero_bond_parameters.sigma = {1.0, 1.0};
    zero_bond_parameters.epsilon = {0.0, 0.0};
    zero_bond_parameters.bond_i = {UINT64_C(0)};
    zero_bond_parameters.bond_j = {UINT64_C(1)};
    zero_bond_parameters.bond_equilibrium = {1.0};
    zero_bond_parameters.bond_force_constant = {2.0};
    zero_bond_parameters.exclusion_i = {UINT64_C(0)};
    zero_bond_parameters.exclusion_j = {UINT64_C(1)};
    const SystemPtr zero_bond_system = make_system(zero_bond_particles);
    const ForceFieldPtr zero_bond_forcefield =
        make_forcefield(zero_bond_parameters);
    require_exact(
        evaluate_energy(
            context, zero_bond_system.get(), zero_bond_forcefield.get()),
        1.0,
        "zero-length bond energy-only evaluation differed");

    bg_energy_components_v1 zero_bond_energy{};
    set_energy_sentinel(&zero_bond_energy);
    const bg_energy_components_v1 zero_bond_energy_before = zero_bond_energy;
    std::vector<double> zero_bond_x(2, 291.5);
    std::vector<double> zero_bond_y(2, 292.5);
    std::vector<double> zero_bond_z(2, 293.5);
    const std::vector<double> zero_bond_x_before = zero_bond_x;
    const std::vector<double> zero_bond_y_before = zero_bond_y;
    const std::vector<double> zero_bond_z_before = zero_bond_z;
    bg_force_soa_v1 zero_bond_forces = make_force_output(
        &zero_bond_x, &zero_bond_y, &zero_bond_z, UINT64_C(2));
    const uint64_t zero_bond_count_before = zero_bond_forces.particle_count;
    require_status(
        bg_context_evaluate(
            context,
            zero_bond_system.get(),
            zero_bond_forcefield.get(),
            &zero_bond_energy,
            &zero_bond_forces),
        BG_STATUS_NUMERICAL_ERROR,
        "zero-length bond force evaluation was not rejected");
    require_unchanged(
        zero_bond_energy,
        zero_bond_energy_before,
        zero_bond_forces,
        zero_bond_count_before,
        zero_bond_x,
        zero_bond_x_before,
        zero_bond_y,
        zero_bond_y_before,
        zero_bond_z,
        zero_bond_z_before,
        "zero-length bond force failure changed outputs");

    const ParticleData degenerate_particles{
        {0.0, 1.0, 2.0, 3.0},
        {0.0, 0.0, 0.0, 0.0},
        {0.0, 0.0, 0.0, 0.0},
        {1.0, 1.0, 1.0, 1.0},
        {0.0, 0.0, 0.0, 0.0},
    };
    ForceFieldData degenerate_parameters;
    degenerate_parameters.sigma = {1.0, 1.0, 1.0, 1.0};
    degenerate_parameters.epsilon = {0.0, 0.0, 0.0, 0.0};
    degenerate_parameters.torsion_i = {UINT64_C(0)};
    degenerate_parameters.torsion_j = {UINT64_C(1)};
    degenerate_parameters.torsion_k = {UINT64_C(2)};
    degenerate_parameters.torsion_l = {UINT64_C(3)};
    degenerate_parameters.torsion_periodicity = {UINT32_C(1)};
    degenerate_parameters.torsion_phase = {0.0};
    degenerate_parameters.torsion_amplitude = {1.0};
    const SystemPtr degenerate_system = make_system(degenerate_particles);
    const ForceFieldPtr degenerate_forcefield =
        make_forcefield(degenerate_parameters);
    bg_energy_components_v1 degenerate_energy{};
    set_energy_sentinel(&degenerate_energy);
    const bg_energy_components_v1 degenerate_energy_before = degenerate_energy;
    std::vector<double> degenerate_x(4, 301.5);
    std::vector<double> degenerate_y(4, 302.5);
    std::vector<double> degenerate_z(4, 303.5);
    const std::vector<double> degenerate_x_before = degenerate_x;
    const std::vector<double> degenerate_y_before = degenerate_y;
    const std::vector<double> degenerate_z_before = degenerate_z;
    bg_force_soa_v1 degenerate_forces = make_force_output(
        &degenerate_x, &degenerate_y, &degenerate_z, UINT64_C(4));
    const uint64_t degenerate_count_before = degenerate_forces.particle_count;
    require_status(
        bg_context_evaluate(
            context,
            degenerate_system.get(),
            degenerate_forcefield.get(),
            &degenerate_energy,
            &degenerate_forces),
        BG_STATUS_NUMERICAL_ERROR,
        "degenerate torsion was not rejected");
    require_unchanged(
        degenerate_energy,
        degenerate_energy_before,
        degenerate_forces,
        degenerate_count_before,
        degenerate_x,
        degenerate_x_before,
        degenerate_y,
        degenerate_y_before,
        degenerate_z,
        degenerate_z_before,
        "degenerate torsion changed outputs");

    // A valid bond is accumulated before the coincident pair is discovered;
    // the public outputs must still remain entirely untouched on failure.
    const ParticleData close_particles{
        {0.0, 1.0, 1.0},
        {0.0, 0.0, 0.0},
        {0.0, 0.0, 0.0},
        {1.0, 1.0, 1.0},
        {0.0, 0.0, 0.0},
    };
    ForceFieldData close_parameters;
    close_parameters.sigma = {1.0, 1.0, 1.0};
    close_parameters.epsilon = {0.0, 0.0, 0.0};
    close_parameters.bond_i = {UINT64_C(0)};
    close_parameters.bond_j = {UINT64_C(1)};
    close_parameters.bond_equilibrium = {0.5};
    close_parameters.bond_force_constant = {2.0};
    close_parameters.minimum_pair_distance = 0.25;
    const SystemPtr close_system = make_system(close_particles);
    const ForceFieldPtr close_forcefield = make_forcefield(close_parameters);
    bg_energy_components_v1 close_energy{};
    set_energy_sentinel(&close_energy);
    const bg_energy_components_v1 close_energy_before = close_energy;
    std::vector<double> close_x(3, 311.5);
    std::vector<double> close_y(3, 312.5);
    std::vector<double> close_z(3, 313.5);
    const std::vector<double> close_x_before = close_x;
    const std::vector<double> close_y_before = close_y;
    const std::vector<double> close_z_before = close_z;
    bg_force_soa_v1 close_forces =
        make_force_output(&close_x, &close_y, &close_z, UINT64_C(3));
    const uint64_t close_count_before = close_forces.particle_count;
    require_status(
        bg_context_evaluate(
            context,
            close_system.get(),
            close_forcefield.get(),
            &close_energy,
            &close_forces),
        BG_STATUS_NUMERICAL_ERROR,
        "minimum pair distance violation was not rejected");
    require_unchanged(
        close_energy,
        close_energy_before,
        close_forces,
        close_count_before,
        close_x,
        close_x_before,
        close_y,
        close_y_before,
        close_z,
        close_z_before,
        "minimum-distance failure changed outputs");
}

}  // namespace

int main() {
    const ContextPtr context = make_cpu_context();
    test_descriptor_initializers_and_exact_bond(context.get());
    test_exact_lennard_jones(context.get());
    test_combined_finite_difference_and_determinism(context.get());
    test_periodic_image_parity(context.get());
    test_excluded_coincident_pair(context.get());
    test_descriptor_and_count_failures();
    test_output_validation_and_transactionality(context.get());
    test_numerical_failures_are_transactional(context.get());
    return 0;
}
