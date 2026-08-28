#define BG_DISABLE_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#define BG_DISABLE_DIRECT_EWALD_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#define BG_DISABLE_DIRECT_EWALD_COMPOSITE_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#define BG_DISABLE_PARTICLE_MESH_RECIPROCAL_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#define BG_DISABLE_PARTICLE_MESH_EWALD_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#define BG_DISABLE_PARTICLE_MESH_EWALD_COMPOSITE_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#include "betelgeuze/particle_mesh_ewald_composite.h"
#include "betelgeuze/direct_ewald_composite.h"

#include "../src/ewald/model.hpp"
#include "../src/internal.hpp"
#include "../src/particle_mesh_reciprocal/model.hpp"

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
#include <string>
#include <type_traits>
#include <vector>

namespace {

[[noreturn]] void fail_test(const char *message) {
    std::fprintf(
        stderr, "particle-mesh Ewald composite test failure: %s\n",
        message);
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
            "particle-mesh Ewald composite test failure: %s "
            "(expected %d, observed %d: %s)\n",
            message, static_cast<int>(expected), static_cast<int>(actual),
            bg_last_error_message());
        std::abort();
    }
}

std::uint64_t bits(double value) noexcept {
    std::uint64_t result = 0U;
    std::memcpy(&result, &value, sizeof(result));
    return result;
}

double from_bits(std::uint64_t value) noexcept {
    double result = 0.0;
    std::memcpy(&result, &value, sizeof(result));
    return result;
}

void require_exact(double actual, double expected, const char *message) {
    require(bits(actual) == bits(expected), message);
}

void require_near(double actual, double expected, const char *message) {
    const double scale = 1.0 + std::max(std::abs(actual), std::abs(expected));
    require(
        std::isfinite(actual) && std::isfinite(expected) &&
            std::abs(actual - expected) <= 5.0e-12 * scale,
        message);
}

struct ContextDeleter final {
    void operator()(bg_context *value) const noexcept {
        bg_context_destroy(value);
    }
};

struct SystemDeleter final {
    void operator()(bg_system *value) const noexcept {
        bg_system_destroy(value);
    }
};

struct ForceFieldDeleter final {
    void operator()(bg_forcefield *value) const noexcept {
        bg_forcefield_destroy(value);
    }
};

struct DirectModelDeleter final {
    void operator()(bg_direct_ewald_model_v1 *value) const noexcept {
        bg_direct_ewald_model_v1_destroy(value);
    }
};

struct ReciprocalModelDeleter final {
    void operator()(
        bg_particle_mesh_reciprocal_model_v1 *value) const noexcept {
        bg_particle_mesh_reciprocal_model_v1_destroy(value);
    }
};

using ContextPtr = std::unique_ptr<bg_context, ContextDeleter>;
using SystemPtr = std::unique_ptr<bg_system, SystemDeleter>;
using ForceFieldPtr = std::unique_ptr<bg_forcefield, ForceFieldDeleter>;
using DirectModelPtr =
    std::unique_ptr<bg_direct_ewald_model_v1, DirectModelDeleter>;
using ReciprocalModelPtr = std::unique_ptr<
    bg_particle_mesh_reciprocal_model_v1, ReciprocalModelDeleter>;

struct Fixture final {
    std::array<double, 4> x{{1.25, 3.1, 5.2, 7.4}};
    std::array<double, 4> y{{2.5, 3.2, 5.3, 6.1}};
    std::array<double, 4> z{{3.75, 4.4, 4.7, 6.3}};
    std::array<double, 4> mass{{12.0, 14.0, 16.0, 19.0}};
    std::array<double, 4> charge{{
        0.7, -0.4, -0.6, 0.30000000000000004}};
    std::array<double, 4> sigma{{1.1, 1.2, 1.3, 1.4}};
    std::array<double, 4> epsilon{{0.15, 0.20, 0.25, 0.30}};

    std::array<std::uint64_t, 1> bond_i{{0U}};
    std::array<std::uint64_t, 1> bond_j{{1U}};
    std::array<double, 1> bond_equilibrium{{5.0}};
    std::array<double, 1> bond_force_constant{{3.0}};

    std::array<std::uint64_t, 1> angle_i{{0U}};
    std::array<std::uint64_t, 1> angle_j{{1U}};
    std::array<std::uint64_t, 1> angle_k{{2U}};
    std::array<double, 1> angle_equilibrium{{1.4}};
    std::array<double, 1> angle_force_constant{{2.0}};

    std::array<std::uint64_t, 1> torsion_i{{0U}};
    std::array<std::uint64_t, 1> torsion_j{{1U}};
    std::array<std::uint64_t, 1> torsion_k{{2U}};
    std::array<std::uint64_t, 1> torsion_l{{3U}};
    std::array<std::uint32_t, 1> torsion_periodicity{{3U}};
    std::array<double, 1> torsion_phase{{0.4}};
    std::array<double, 1> torsion_amplitude{{0.7}};

    std::array<std::uint64_t, 1> exclusion_i{{0U}};
    std::array<std::uint64_t, 1> exclusion_j{{1U}};
    std::array<std::uint64_t, 1> scale_i{{2U}};
    std::array<std::uint64_t, 1> scale_j{{3U}};
    std::array<double, 1> scale_lennard_jones{{0.25}};
    std::array<double, 1> scale_coulomb{{0.5}};

    std::array<double, 3> cell{{18.0, 20.0, 22.0}};
    double alpha = 0.31;
    double cutoff = 8.9;
    double switch_start = 7.0;
    double dielectric = 1.0;
    double minimum_pair_distance = 1.0e-8;
};

void init_error(bg_direct_ewald_error_v1 *error) {
    require_status(
        bg_direct_ewald_error_v1_init(
            error, sizeof(*error), BG_DIRECT_EWALD_ABI_VERSION),
        BG_STATUS_OK, "typed-error initializer failed");
}

ContextPtr make_context(bg_backend backend) {
    bg_context_options options{};
    require_status(
        bg_context_options_init(&options, sizeof(options), BG_ABI_VERSION),
        BG_STATUS_OK, "context initializer failed");
    options.backend = backend;
    bg_context *raw = nullptr;
    require_status(
        bg_context_create(&options, &raw), BG_STATUS_OK,
        "CPU context creation failed");
    require(raw != nullptr, "CPU context creation returned null");
    return ContextPtr(raw);
}

SystemPtr make_system(
    const Fixture &fixture,
    const std::array<double, 4> &charge) {
    bg_particle_soa particles{};
    require_status(
        bg_particle_soa_init(
            &particles, sizeof(particles), BG_ABI_VERSION),
        BG_STATUS_OK, "particle initializer failed");
    particles.particle_count = fixture.x.size();
    particles.position_x_angstrom = fixture.x.data();
    particles.position_y_angstrom = fixture.y.data();
    particles.position_z_angstrom = fixture.z.data();
    particles.mass_dalton = fixture.mass.data();
    particles.charge_elementary = charge.data();
    bg_system *raw = nullptr;
    require_status(
        bg_system_create(&particles, &raw), BG_STATUS_OK,
        "system creation failed");
    require(raw != nullptr, "system creation returned null");
    return SystemPtr(raw);
}

ForceFieldPtr make_forcefield(const Fixture &fixture) {
    bg_forcefield_soa_v1 parameters{};
    require_status(
        bg_forcefield_soa_v1_init(
            &parameters, sizeof(parameters), BG_ABI_VERSION),
        BG_STATUS_OK, "force-field initializer failed");
    parameters.atom_count = fixture.sigma.size();
    parameters.unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
    parameters.periodic_axes_mask = BG_PERIODIC_AXES_ALL;
    parameters.sigma_angstrom = fixture.sigma.data();
    parameters.epsilon_kcal_per_mol = fixture.epsilon.data();
    parameters.bond_count = fixture.bond_i.size();
    parameters.bond_atom_i = fixture.bond_i.data();
    parameters.bond_atom_j = fixture.bond_j.data();
    parameters.bond_equilibrium_angstrom = fixture.bond_equilibrium.data();
    parameters.bond_force_constant_kcal_per_mol_angstrom2 =
        fixture.bond_force_constant.data();
    parameters.angle_count = fixture.angle_i.size();
    parameters.angle_atom_i = fixture.angle_i.data();
    parameters.angle_atom_j = fixture.angle_j.data();
    parameters.angle_atom_k = fixture.angle_k.data();
    parameters.angle_equilibrium_radians = fixture.angle_equilibrium.data();
    parameters.angle_force_constant_kcal_per_mol_radian2 =
        fixture.angle_force_constant.data();
    parameters.torsion_count = fixture.torsion_i.size();
    parameters.torsion_atom_i = fixture.torsion_i.data();
    parameters.torsion_atom_j = fixture.torsion_j.data();
    parameters.torsion_atom_k = fixture.torsion_k.data();
    parameters.torsion_atom_l = fixture.torsion_l.data();
    parameters.torsion_periodicity = fixture.torsion_periodicity.data();
    parameters.torsion_phase_radians = fixture.torsion_phase.data();
    parameters.torsion_amplitude_kcal_per_mol =
        fixture.torsion_amplitude.data();
    parameters.exclusion_count = fixture.exclusion_i.size();
    parameters.exclusion_atom_i = fixture.exclusion_i.data();
    parameters.exclusion_atom_j = fixture.exclusion_j.data();
    parameters.pair_scale_count = fixture.scale_i.size();
    parameters.pair_scale_atom_i = fixture.scale_i.data();
    parameters.pair_scale_atom_j = fixture.scale_j.data();
    parameters.pair_scale_lennard_jones =
        fixture.scale_lennard_jones.data();
    parameters.pair_scale_coulomb = fixture.scale_coulomb.data();
    std::copy(
        fixture.cell.begin(), fixture.cell.end(),
        parameters.cell_lengths_angstrom);
    parameters.cutoff_angstrom = fixture.cutoff;
    parameters.switch_start_angstrom = fixture.switch_start;
    parameters.dielectric = fixture.dielectric;
    parameters.screening_kappa_per_angstrom = 0.0;
    parameters.minimum_pair_distance_angstrom =
        fixture.minimum_pair_distance;
    bg_forcefield *raw = nullptr;
    require_status(
        bg_forcefield_create(&parameters, &raw), BG_STATUS_OK,
        "force-field creation failed");
    require(raw != nullptr, "force-field creation returned null");
    return ForceFieldPtr(raw);
}

DirectModelPtr make_direct_model(
    const Fixture &fixture,
    bool with_pair_rules = true,
    std::int32_t reciprocal_bound = 5) {
    bg_direct_ewald_parameters_v1 parameters{};
    require_status(
        bg_direct_ewald_parameters_v1_init(
            &parameters, sizeof(parameters), BG_DIRECT_EWALD_ABI_VERSION),
        BG_STATUS_OK, "direct-model parameter initializer failed");
    parameters.atom_count = fixture.x.size();
    std::copy(
        fixture.cell.begin(), fixture.cell.end(),
        parameters.cell_lengths_angstrom);
    parameters.alpha_per_angstrom = fixture.alpha;
    parameters.real_space_cutoff_angstrom = fixture.cutoff;
    parameters.reciprocal_max_indices[0] = reciprocal_bound;
    parameters.reciprocal_max_indices[1] = reciprocal_bound;
    parameters.reciprocal_max_indices[2] = reciprocal_bound;
    parameters.dielectric = fixture.dielectric;
    parameters.minimum_pair_distance_angstrom =
        fixture.minimum_pair_distance;
    if (with_pair_rules) {
        parameters.exclusion_count = fixture.exclusion_i.size();
        parameters.exclusion_atom_i = fixture.exclusion_i.data();
        parameters.exclusion_atom_j = fixture.exclusion_j.data();
        parameters.pair_scale_count = fixture.scale_i.size();
        parameters.pair_scale_atom_i = fixture.scale_i.data();
        parameters.pair_scale_atom_j = fixture.scale_j.data();
        parameters.pair_scale_coulomb = fixture.scale_coulomb.data();
    }
    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    bg_direct_ewald_model_v1 *raw = nullptr;
    require_status(
        bg_direct_ewald_model_v1_create(&parameters, &raw, &error),
        BG_STATUS_OK, "direct model creation failed");
    require(raw != nullptr, "direct model creation returned null");
    require(
        error.code == BG_DIRECT_EWALD_ERROR_NONE,
        "direct model creation set typed error");
    return DirectModelPtr(raw);
}

ReciprocalModelPtr make_reciprocal_model(
    const Fixture &fixture,
    std::uint32_t mesh_dimension = 16U) {
    bg_particle_mesh_reciprocal_parameters_v1 parameters{};
    require_status(
        bg_particle_mesh_reciprocal_parameters_v1_init(
            &parameters, sizeof(parameters),
            BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION),
        BG_STATUS_OK, "reciprocal-model parameter initializer failed");
    parameters.atom_count = fixture.x.size();
    std::copy(
        fixture.cell.begin(), fixture.cell.end(),
        parameters.cell_lengths_angstrom);
    parameters.alpha_per_angstrom = fixture.alpha;
    parameters.mesh_dimensions[0] = mesh_dimension;
    parameters.mesh_dimensions[1] = mesh_dimension;
    parameters.mesh_dimensions[2] = mesh_dimension;
    parameters.dielectric = fixture.dielectric;
    bg_particle_mesh_reciprocal_error_v1 error{};
    require_status(
        bg_particle_mesh_reciprocal_error_v1_init(
            &error, sizeof(error),
            BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION),
        BG_STATUS_OK, "reciprocal-model error initializer failed");
    bg_particle_mesh_reciprocal_model_v1 *raw = nullptr;
    require_status(
        bg_particle_mesh_reciprocal_model_v1_create(
            &parameters, &raw, &error),
        BG_STATUS_OK, "reciprocal model creation failed");
    require(raw != nullptr, "reciprocal model creation returned null");
    require(
        error.code == BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONE,
        "reciprocal model creation set typed error");
    return ReciprocalModelPtr(raw);
}

struct Result final {
    bg_particle_mesh_ewald_composite_energy_components_v1 energy{};
    std::array<double, 4> force_x{};
    std::array<double, 4> force_y{};
    std::array<double, 4> force_z{};
};

struct ParentResult final {
    bg_energy_components_v1 short_energy{};
    bg_particle_mesh_ewald_energy_components_v1 pme_energy{};
    std::array<double, 4> short_force_x{};
    std::array<double, 4> short_force_y{};
    std::array<double, 4> short_force_z{};
    std::array<double, 4> pme_force_x{};
    std::array<double, 4> pme_force_y{};
    std::array<double, 4> pme_force_z{};
};

Result evaluate_composite(
    const bg_context *context,
    const bg_system *system,
    const bg_forcefield *forcefield,
    const bg_direct_ewald_model_v1 *direct_model,
    const bg_particle_mesh_reciprocal_model_v1 *reciprocal_model) {
    Result result;
    require_status(
        bg_particle_mesh_ewald_composite_energy_components_v1_init(
            &result.energy, sizeof(result.energy),
            BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION),
        BG_STATUS_OK, "composite energy initializer failed");
    bg_particle_mesh_ewald_composite_force_soa_v1 forces{};
    require_status(
        bg_particle_mesh_ewald_composite_force_soa_v1_init(
            &forces, sizeof(forces),
            BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION),
        BG_STATUS_OK, "composite force initializer failed");
    forces.atom_capacity = result.force_x.size();
    forces.x_kcal_per_mol_angstrom = result.force_x.data();
    forces.y_kcal_per_mol_angstrom = result.force_y.data();
    forces.z_kcal_per_mol_angstrom = result.force_z.data();
    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    require_status(
        bg_context_evaluate_particle_mesh_ewald_composite_v1(
            context, system, forcefield, direct_model, reciprocal_model,
            &result.energy, &forces, &error),
        BG_STATUS_OK, "composite evaluation failed");
    require(
        forces.atom_count == result.force_x.size(),
        "composite force count was not committed");
    require(
        error.code == BG_DIRECT_EWALD_ERROR_NONE &&
            error.detail[0] == '\0',
        "composite success set typed error");
    return result;
}

bg_particle_mesh_ewald_composite_energy_components_v1
evaluate_composite_energy(
    const bg_context *context,
    const bg_system *system,
    const bg_forcefield *forcefield,
    const bg_direct_ewald_model_v1 *direct_model,
    const bg_particle_mesh_reciprocal_model_v1 *reciprocal_model) {
    bg_particle_mesh_ewald_composite_energy_components_v1 energy{};
    require_status(
        bg_particle_mesh_ewald_composite_energy_components_v1_init(
            &energy, sizeof(energy),
            BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION),
        BG_STATUS_OK, "energy-only initializer failed");
    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    require_status(
        bg_context_evaluate_particle_mesh_ewald_composite_v1(
            context, system, forcefield, direct_model, reciprocal_model,
            &energy, nullptr, &error),
        BG_STATUS_OK, "energy-only composite evaluation failed");
    require(
        error.code == BG_DIRECT_EWALD_ERROR_NONE,
        "energy-only success set typed error");
    return energy;
}

ParentResult evaluate_parents(
    const bg_context *context,
    const bg_system *charged_system,
    const bg_system *zero_charge_system,
    const bg_forcefield *forcefield,
    const bg_direct_ewald_model_v1 *direct_model,
    const bg_particle_mesh_reciprocal_model_v1 *reciprocal_model) {
    ParentResult result;
    require_status(
        bg_energy_components_v1_init(
            &result.short_energy, sizeof(result.short_energy),
            BG_ABI_VERSION),
        BG_STATUS_OK, "short parent energy initializer failed");
    bg_force_soa_v1 short_forces{};
    require_status(
        bg_force_soa_v1_init(
            &short_forces, sizeof(short_forces), BG_ABI_VERSION),
        BG_STATUS_OK, "short parent force initializer failed");
    short_forces.particle_capacity = result.short_force_x.size();
    short_forces.x_kcal_per_mol_angstrom = result.short_force_x.data();
    short_forces.y_kcal_per_mol_angstrom = result.short_force_y.data();
    short_forces.z_kcal_per_mol_angstrom = result.short_force_z.data();
    require_status(
        bg_context_evaluate(
            context, zero_charge_system, forcefield, &result.short_energy,
            &short_forces),
        BG_STATUS_OK, "short parent evaluation failed");
    require(
        short_forces.particle_count == result.short_force_x.size(),
        "short parent force count differed");

    require_status(
        bg_particle_mesh_ewald_energy_components_v1_init(
            &result.pme_energy, sizeof(result.pme_energy),
            BG_PARTICLE_MESH_EWALD_ABI_VERSION),
        BG_STATUS_OK, "PME parent energy initializer failed");
    bg_particle_mesh_ewald_force_soa_v1 pme_forces{};
    require_status(
        bg_particle_mesh_ewald_force_soa_v1_init(
            &pme_forces, sizeof(pme_forces),
            BG_PARTICLE_MESH_EWALD_ABI_VERSION),
        BG_STATUS_OK, "PME parent force initializer failed");
    pme_forces.atom_capacity = result.pme_force_x.size();
    pme_forces.x_kcal_per_mol_angstrom = result.pme_force_x.data();
    pme_forces.y_kcal_per_mol_angstrom = result.pme_force_y.data();
    pme_forces.z_kcal_per_mol_angstrom = result.pme_force_z.data();
    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    require_status(
        bg_context_evaluate_particle_mesh_ewald_v1(
            context, charged_system, direct_model, reciprocal_model,
            &result.pme_energy, &pme_forces, &error),
        BG_STATUS_OK, "PME parent evaluation failed");
    require(
        pme_forces.atom_count == result.pme_force_x.size(),
        "PME parent force count differed");
    require(
        error.code == BG_DIRECT_EWALD_ERROR_NONE,
        "PME parent success set typed error");
    return result;
}

std::array<double, 12> energy_values(
    const bg_particle_mesh_ewald_composite_energy_components_v1 &energy) {
    return {{
        energy.short_harmonic_bond_kcal_per_mol,
        energy.short_harmonic_angle_kcal_per_mol,
        energy.short_periodic_torsion_kcal_per_mol,
        energy.short_lennard_jones_kcal_per_mol,
        energy.short_coulomb_kcal_per_mol,
        energy.short_total_kcal_per_mol,
        energy.pme_real_space_kcal_per_mol,
        energy.pme_reciprocal_space_kcal_per_mol,
        energy.pme_self_kcal_per_mol,
        energy.pme_pair_correction_kcal_per_mol,
        energy.pme_total_kcal_per_mol,
        energy.total_kcal_per_mol,
    }};
}

void require_energy_exact(
    const bg_particle_mesh_ewald_composite_energy_components_v1 &actual,
    const bg_particle_mesh_ewald_composite_energy_components_v1 &expected,
    const char *message) {
    const auto actual_values = energy_values(actual);
    const auto expected_values = energy_values(expected);
    for (std::size_t index = 0U; index < actual_values.size(); ++index) {
        require_exact(actual_values[index], expected_values[index], message);
    }
}

void require_result_exact(
    const Result &actual,
    const Result &expected,
    const char *message) {
    require_energy_exact(actual.energy, expected.energy, message);
    for (std::size_t atom = 0U; atom < actual.force_x.size(); ++atom) {
        require_exact(actual.force_x[atom], expected.force_x[atom], message);
        require_exact(actual.force_y[atom], expected.force_y[atom], message);
        require_exact(actual.force_z[atom], expected.force_z[atom], message);
    }
}

template <typename Descriptor, typename Initializer>
void verify_initializer_transactionality(Initializer initializer) {
    Descriptor descriptor{};
    std::memset(&descriptor, 0x5a, sizeof(descriptor));
    std::array<unsigned char, sizeof(Descriptor)> before{};
    std::memcpy(before.data(), &descriptor, sizeof(descriptor));
    require_status(
        initializer(
            &descriptor, sizeof(descriptor) - 1U,
            BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION),
        BG_STATUS_ABI_MISMATCH,
        "composite initializer accepted a short descriptor");
    require(
        std::memcmp(&descriptor, before.data(), sizeof(descriptor)) == 0,
        "short initializer changed its descriptor");
    require_status(
        initializer(&descriptor, sizeof(descriptor), UINT32_C(99)),
        BG_STATUS_ABI_MISMATCH,
        "composite initializer accepted a foreign version");
    require(
        std::memcmp(&descriptor, before.data(), sizeof(descriptor)) == 0,
        "foreign-version initializer changed its descriptor");
    require_status(
        initializer(
            &descriptor, sizeof(descriptor),
            BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION),
        BG_STATUS_OK, "valid composite initializer failed");
}

void verify_abi_layout_profile_and_initializers() {
    static_assert(std::is_standard_layout_v<
                  bg_particle_mesh_ewald_composite_energy_components_v1>);
    static_assert(std::is_standard_layout_v<
                  bg_particle_mesh_ewald_composite_force_soa_v1>);
    static_assert(
        sizeof(bg_particle_mesh_ewald_composite_energy_components_v1) ==
        144U);
    static_assert(
        sizeof(bg_particle_mesh_ewald_composite_force_soa_v1) == 88U);
    static_assert(offsetof(
                      bg_particle_mesh_ewald_composite_energy_components_v1,
                      short_harmonic_bond_kcal_per_mol) == 16U);
    static_assert(offsetof(
                      bg_particle_mesh_ewald_composite_energy_components_v1,
                      total_kcal_per_mol) == 104U);
    static_assert(offsetof(
                      bg_particle_mesh_ewald_composite_force_soa_v1,
                      x_kcal_per_mol_angstrom) == 32U);
    require(
        bg_particle_mesh_ewald_composite_abi_version() == 1U,
        "wrong composite ABI version");
    require(
        bg_particle_mesh_ewald_composite_abi_version_major() == 1U,
        "wrong composite ABI major");
    require(
        bg_particle_mesh_ewald_composite_abi_version_minor() == 0U,
        "wrong composite ABI minor");
    require(
        std::string(
            bg_particle_mesh_ewald_composite_abi_version_string()) ==
            "1.0.0",
        "wrong composite ABI version string");
    require(
        std::string(bg_particle_mesh_ewald_composite_v1_profile_id()) ==
            "betelgeuze.native_particle_mesh_ewald_composite/1.0.0",
        "wrong composite profile id");
    verify_initializer_transactionality<
        bg_particle_mesh_ewald_composite_energy_components_v1>(
        bg_particle_mesh_ewald_composite_energy_components_v1_init);
    verify_initializer_transactionality<
        bg_particle_mesh_ewald_composite_force_soa_v1>(
        bg_particle_mesh_ewald_composite_force_soa_v1_init);
}

void require_matches_parents(
    const Result &composite,
    const ParentResult &parents) {
    const std::array<double, 6> composite_short{{
        composite.energy.short_harmonic_bond_kcal_per_mol,
        composite.energy.short_harmonic_angle_kcal_per_mol,
        composite.energy.short_periodic_torsion_kcal_per_mol,
        composite.energy.short_lennard_jones_kcal_per_mol,
        composite.energy.short_coulomb_kcal_per_mol,
        composite.energy.short_total_kcal_per_mol,
    }};
    const std::array<double, 6> parent_short{{
        parents.short_energy.harmonic_bond_kcal_per_mol,
        parents.short_energy.harmonic_angle_kcal_per_mol,
        parents.short_energy.periodic_torsion_kcal_per_mol,
        parents.short_energy.lennard_jones_kcal_per_mol,
        parents.short_energy.coulomb_kcal_per_mol,
        parents.short_energy.total_kcal_per_mol,
    }};
    for (std::size_t index = 0U; index < composite_short.size(); ++index) {
        require_exact(
            composite_short[index], parent_short[index],
            "composite short component differed from zero-charge parent");
    }
    require_exact(
        composite.energy.short_coulomb_kcal_per_mol, 0.0,
        "composite short Coulomb was not exact positive zero");
    require_exact(
        composite.energy.pme_real_space_kcal_per_mol,
        parents.pme_energy.real_space_kcal_per_mol,
        "composite PME real component differed from parent");
    require_exact(
        composite.energy.pme_reciprocal_space_kcal_per_mol,
        parents.pme_energy.reciprocal_space_kcal_per_mol,
        "composite PME reciprocal component differed from parent");
    require_exact(
        composite.energy.pme_self_kcal_per_mol,
        parents.pme_energy.self_kcal_per_mol,
        "composite PME self component differed from parent");
    require_exact(
        composite.energy.pme_pair_correction_kcal_per_mol,
        parents.pme_energy.pair_correction_kcal_per_mol,
        "composite PME pair component differed from parent");
    const double expected_pme_total =
        ((parents.pme_energy.real_space_kcal_per_mol +
          parents.pme_energy.reciprocal_space_kcal_per_mol) +
         parents.pme_energy.self_kcal_per_mol) +
        parents.pme_energy.pair_correction_kcal_per_mol;
    require_exact(
        composite.energy.pme_total_kcal_per_mol, expected_pme_total,
        "composite PME total used a different addition order");
    require_exact(
        composite.energy.total_kcal_per_mol,
        parents.short_energy.total_kcal_per_mol + expected_pme_total,
        "composite grand total used a different addition order");
    for (std::size_t atom = 0U; atom < composite.force_x.size(); ++atom) {
        require_exact(
            composite.force_x[atom],
            parents.short_force_x[atom] + parents.pme_force_x[atom],
            "composite x force differed from short + PME parent sum");
        require_exact(
            composite.force_y[atom],
            parents.short_force_y[atom] + parents.pme_force_y[atom],
            "composite y force differed from short + PME parent sum");
        require_exact(
            composite.force_z[atom],
            parents.short_force_z[atom] + parents.pme_force_z[atom],
            "composite z force differed from short + PME parent sum");
    }
}

void verify_parent_composition_repeat_parity_and_energy_only() {
    constexpr std::uint64_t kFrozenRustTotal =
        UINT64_C(0x4012dc3129bce12e);
    const Fixture fixture;
    const std::array<double, 4> zero_charge{{0.0, 0.0, 0.0, 0.0}};
    const SystemPtr system = make_system(fixture, fixture.charge);
    const SystemPtr zero_system = make_system(fixture, zero_charge);
    const ForceFieldPtr forcefield = make_forcefield(fixture);
    const DirectModelPtr direct_model = make_direct_model(fixture);
    const ReciprocalModelPtr reciprocal_model =
        make_reciprocal_model(fixture);
    std::array<Result, 2> lane_results;
    const std::array<bg_backend, 2> lanes{{
        BG_BACKEND_CPP_CPU_REFERENCE, BG_BACKEND_RUST_CPU,
    }};
    for (std::size_t lane = 0U; lane < lanes.size(); ++lane) {
        const ContextPtr context = make_context(lanes[lane]);
        const ParentResult parents = evaluate_parents(
            context.get(), system.get(), zero_system.get(),
            forcefield.get(), direct_model.get(), reciprocal_model.get());
        lane_results[lane] = evaluate_composite(
            context.get(), system.get(), forcefield.get(),
            direct_model.get(), reciprocal_model.get());
        require_matches_parents(lane_results[lane], parents);
        const Result repeated = evaluate_composite(
            context.get(), system.get(), forcefield.get(),
            direct_model.get(), reciprocal_model.get());
        require_result_exact(
            repeated, lane_results[lane],
            "same-lane composite repeat changed bits");
        const auto energy_only = evaluate_composite_energy(
            context.get(), system.get(), forcefield.get(),
            direct_model.get(), reciprocal_model.get());
        require_energy_exact(
            energy_only, lane_results[lane].energy,
            "energy-only composite path changed energy bits");
    }
    const auto cpp_energy = energy_values(lane_results[0].energy);
    const auto rust_energy = energy_values(lane_results[1].energy);
    for (std::size_t index = 0U; index < cpp_energy.size(); ++index) {
        require_near(
            cpp_energy[index], rust_energy[index],
            "C++/Rust composite energy parity failed");
    }
    require(
        bits(lane_results[1].energy.total_kcal_per_mol) ==
            kFrozenRustTotal,
        "Rust composite frozen total bits changed");
    require_near(
        lane_results[0].energy.total_kcal_per_mol,
        from_bits(kFrozenRustTotal),
        "C++ composite total diverged from the frozen Rust fixture");
    for (std::size_t atom = 0U; atom < lane_results[0].force_x.size(); ++atom) {
        require_near(
            lane_results[0].force_x[atom], lane_results[1].force_x[atom],
            "C++/Rust composite x-force parity failed");
        require_near(
            lane_results[0].force_y[atom], lane_results[1].force_y[atom],
            "C++/Rust composite y-force parity failed");
        require_near(
            lane_results[0].force_z[atom], lane_results[1].force_z[atom],
            "C++/Rust composite z-force parity failed");
    }
}

void verify_direct_bound_independence_and_mesh_convergence() {
    const Fixture fixture;
    const SystemPtr system = make_system(fixture, fixture.charge);
    const ForceFieldPtr forcefield = make_forcefield(fixture);
    const DirectModelPtr low_bound = make_direct_model(fixture, true, 1);
    const DirectModelPtr high_bound = make_direct_model(fixture, true, 32);
    const DirectModelPtr reference_model =
        make_direct_model(fixture, true, 9);
    const ReciprocalModelPtr mesh16 = make_reciprocal_model(fixture, 16U);
    const std::array<std::uint32_t, 3> meshes{{8U, 16U, 32U}};
    for (const bg_backend lane :
         {BG_BACKEND_CPP_CPU_REFERENCE, BG_BACKEND_RUST_CPU}) {
        const ContextPtr context = make_context(lane);
        const Result low = evaluate_composite(
            context.get(), system.get(), forcefield.get(), low_bound.get(),
            mesh16.get());
        const Result high = evaluate_composite(
            context.get(), system.get(), forcefield.get(), high_bound.get(),
            mesh16.get());
        require_result_exact(
            high, low,
            "direct reciprocal bounds influenced the PME composite");

        bg_direct_ewald_composite_energy_components_v1 reference{};
        require_status(
            bg_direct_ewald_composite_energy_components_v1_init(
                &reference, sizeof(reference),
                BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION),
            BG_STATUS_OK,
            "direct composite reference energy initializer failed");
        bg_direct_ewald_error_v1 error{};
        init_error(&error);
        require_status(
            bg_context_evaluate_direct_ewald_composite_v1(
                context.get(), system.get(), forcefield.get(),
                reference_model.get(), &reference, nullptr, &error),
            BG_STATUS_OK, "direct composite reference evaluation failed");
        std::array<double, 3> absolute_errors{};
        for (std::size_t index = 0U; index < meshes.size(); ++index) {
            const ReciprocalModelPtr reciprocal =
                make_reciprocal_model(fixture, meshes[index]);
            const auto composite = evaluate_composite_energy(
                context.get(), system.get(), forcefield.get(),
                reference_model.get(), reciprocal.get());
            absolute_errors[index] = std::abs(
                composite.total_kcal_per_mol -
                reference.total_kcal_per_mol);
        }
        require(
            absolute_errors[1] < absolute_errors[0],
            "mesh 16 composite did not approach direct Ewald from mesh 8");
        require(
            absolute_errors[2] < absolute_errors[1],
            "mesh 32 composite did not approach direct Ewald from mesh 16");
        require(
            absolute_errors[2] < 2.0e-3,
            "mesh 32 composite remained too far from direct Ewald");
    }
}

Fixture permute_fixture(const Fixture &source) {
    constexpr std::array<std::size_t, 4> new_to_old{{2U, 0U, 3U, 1U}};
    constexpr std::array<std::size_t, 4> old_to_new{{1U, 3U, 0U, 2U}};
    Fixture result = source;
    for (std::size_t index = 0U; index < new_to_old.size(); ++index) {
        const std::size_t old = new_to_old[index];
        result.x[index] = source.x[old];
        result.y[index] = source.y[old];
        result.z[index] = source.z[old];
        result.mass[index] = source.mass[old];
        result.charge[index] = source.charge[old];
        result.sigma[index] = source.sigma[old];
        result.epsilon[index] = source.epsilon[old];
    }
    result.bond_i[0] = old_to_new[source.bond_i[0]];
    result.bond_j[0] = old_to_new[source.bond_j[0]];
    result.angle_i[0] = old_to_new[source.angle_i[0]];
    result.angle_j[0] = old_to_new[source.angle_j[0]];
    result.angle_k[0] = old_to_new[source.angle_k[0]];
    result.torsion_i[0] = old_to_new[source.torsion_i[0]];
    result.torsion_j[0] = old_to_new[source.torsion_j[0]];
    result.torsion_k[0] = old_to_new[source.torsion_k[0]];
    result.torsion_l[0] = old_to_new[source.torsion_l[0]];
    result.exclusion_i[0] = std::min(
        old_to_new[source.exclusion_i[0]],
        old_to_new[source.exclusion_j[0]]);
    result.exclusion_j[0] = std::max(
        old_to_new[source.exclusion_i[0]],
        old_to_new[source.exclusion_j[0]]);
    result.scale_i[0] = std::min(
        old_to_new[source.scale_i[0]], old_to_new[source.scale_j[0]]);
    result.scale_j[0] = std::max(
        old_to_new[source.scale_i[0]], old_to_new[source.scale_j[0]]);
    return result;
}

void require_result_near(
    const Result &actual,
    const Result &expected,
    const char *message) {
    const auto actual_energy = energy_values(actual.energy);
    const auto expected_energy = energy_values(expected.energy);
    for (std::size_t index = 0U; index < actual_energy.size(); ++index) {
        require_near(actual_energy[index], expected_energy[index], message);
    }
    for (std::size_t atom = 0U; atom < actual.force_x.size(); ++atom) {
        require_near(actual.force_x[atom], expected.force_x[atom], message);
        require_near(actual.force_y[atom], expected.force_y[atom], message);
        require_near(actual.force_z[atom], expected.force_z[atom], message);
    }
}

void verify_symmetry_invariances() {
    const Fixture fixture;
    const SystemPtr system = make_system(fixture, fixture.charge);
    const ForceFieldPtr forcefield = make_forcefield(fixture);
    const DirectModelPtr direct_model = make_direct_model(fixture);
    const ReciprocalModelPtr reciprocal_model =
        make_reciprocal_model(fixture);
    for (const bg_backend lane :
         {BG_BACKEND_CPP_CPU_REFERENCE, BG_BACKEND_RUST_CPU}) {
        const ContextPtr context = make_context(lane);
        const Result reference = evaluate_composite(
            context.get(), system.get(), forcefield.get(),
            direct_model.get(), reciprocal_model.get());

        Fixture translated = fixture;
        for (std::size_t atom = 0U; atom < translated.x.size(); ++atom) {
            translated.x[atom] += fixture.cell[0];
            translated.y[atom] -= 2.0 * fixture.cell[1];
            translated.z[atom] += 3.0 * fixture.cell[2];
        }
        const SystemPtr translated_system = make_system(
            translated, translated.charge);
        const Result translated_result = evaluate_composite(
            context.get(), translated_system.get(), forcefield.get(),
            direct_model.get(), reciprocal_model.get());
        require_result_near(
            translated_result, reference,
            "whole-cell translation changed the composite result");

        Fixture imaged = fixture;
        imaged.x[2] += fixture.cell[0];
        imaged.y[2] -= fixture.cell[1];
        imaged.z[2] += fixture.cell[2];
        const SystemPtr imaged_system = make_system(imaged, imaged.charge);
        const Result imaged_result = evaluate_composite(
            context.get(), imaged_system.get(), forcefield.get(),
            direct_model.get(), reciprocal_model.get());
        require_result_near(
            imaged_result, reference,
            "equivalent periodic image changed the composite result");

        Fixture inverted = fixture;
        for (double &charge : inverted.charge) {
            charge = -charge;
        }
        const SystemPtr inverted_system = make_system(
            inverted, inverted.charge);
        const Result inverted_result = evaluate_composite(
            context.get(), inverted_system.get(), forcefield.get(),
            direct_model.get(), reciprocal_model.get());
        require_result_near(
            inverted_result, reference,
            "global charge inversion changed the composite result");

        const Fixture permuted = permute_fixture(fixture);
        const SystemPtr permuted_system = make_system(
            permuted, permuted.charge);
        const ForceFieldPtr permuted_forcefield = make_forcefield(permuted);
        const DirectModelPtr permuted_direct = make_direct_model(permuted);
        const ReciprocalModelPtr permuted_reciprocal =
            make_reciprocal_model(permuted);
        const Result permuted_result = evaluate_composite(
            context.get(), permuted_system.get(), permuted_forcefield.get(),
            permuted_direct.get(), permuted_reciprocal.get());
        const auto reference_energy = energy_values(reference.energy);
        const auto permuted_energy = energy_values(permuted_result.energy);
        for (std::size_t index = 0U; index < reference_energy.size(); ++index) {
            require_near(
                permuted_energy[index], reference_energy[index],
                "atom permutation changed composite energy");
        }
        constexpr std::array<std::size_t, 4> new_to_old{{2U, 0U, 3U, 1U}};
        for (std::size_t atom = 0U; atom < new_to_old.size(); ++atom) {
            const std::size_t old = new_to_old[atom];
            require_near(
                permuted_result.force_x[atom], reference.force_x[old],
                "atom permutation changed x force covariance");
            require_near(
                permuted_result.force_y[atom], reference.force_y[old],
                "atom permutation changed y force covariance");
            require_near(
                permuted_result.force_z[atom], reference.force_z[old],
                "atom permutation changed z force covariance");
        }
    }
}

void verify_central_finite_difference() {
    const Fixture fixture;
    constexpr double displacement = 1.0e-5;
    const SystemPtr system = make_system(fixture, fixture.charge);
    const ForceFieldPtr forcefield = make_forcefield(fixture);
    const DirectModelPtr direct_model = make_direct_model(fixture);
    const ReciprocalModelPtr reciprocal_model =
        make_reciprocal_model(fixture);
    for (const bg_backend lane :
         {BG_BACKEND_CPP_CPU_REFERENCE, BG_BACKEND_RUST_CPU}) {
        const ContextPtr context = make_context(lane);
        const Result analytic = evaluate_composite(
            context.get(), system.get(), forcefield.get(),
            direct_model.get(), reciprocal_model.get());
        const std::array<const std::array<double, 4> *, 3> analytic_axes{{
            &analytic.force_x, &analytic.force_y, &analytic.force_z,
        }};
        for (std::size_t atom = 0U; atom < fixture.x.size(); ++atom) {
            for (std::size_t axis = 0U; axis < 3U; ++axis) {
                Fixture plus = fixture;
                Fixture minus = fixture;
                const std::array<std::array<double, 4> *, 3> plus_axes{{
                    &plus.x, &plus.y, &plus.z,
                }};
                const std::array<std::array<double, 4> *, 3> minus_axes{{
                    &minus.x, &minus.y, &minus.z,
                }};
                (*plus_axes[axis])[atom] += displacement;
                (*minus_axes[axis])[atom] -= displacement;
                const SystemPtr plus_system = make_system(plus, plus.charge);
                const SystemPtr minus_system = make_system(minus, minus.charge);
                const auto plus_energy = evaluate_composite_energy(
                    context.get(), plus_system.get(), forcefield.get(),
                    direct_model.get(), reciprocal_model.get());
                const auto minus_energy = evaluate_composite_energy(
                    context.get(), minus_system.get(), forcefield.get(),
                    direct_model.get(), reciprocal_model.get());
                const double numerical =
                    -(plus_energy.total_kcal_per_mol -
                      minus_energy.total_kcal_per_mol) /
                    (2.0 * displacement);
                const double expected = (*analytic_axes[axis])[atom];
                const double scale = std::max(1.0, std::abs(expected));
                require(
                    std::isfinite(numerical) &&
                        std::abs(numerical - expected) <= 2.0e-6 * scale,
                    "composite force failed central finite difference");
            }
        }
    }
}

struct FailureState final {
    bg_particle_mesh_ewald_composite_energy_components_v1 energy{};
    bg_particle_mesh_ewald_composite_force_soa_v1 forces{};
    std::array<double, 4> force_x{{11.0, 12.0, 13.0, 14.0}};
    std::array<double, 4> force_y{{21.0, 22.0, 23.0, 24.0}};
    std::array<double, 4> force_z{{31.0, 32.0, 33.0, 34.0}};
    bg_direct_ewald_error_v1 error{};

    FailureState() {
        require_status(
            bg_particle_mesh_ewald_composite_energy_components_v1_init(
                &energy, sizeof(energy),
                BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION),
            BG_STATUS_OK, "failure-state energy initializer failed");
        double marker = 101.0;
        for (double *field : std::array<double *, 12>{{
                 &energy.short_harmonic_bond_kcal_per_mol,
                 &energy.short_harmonic_angle_kcal_per_mol,
                 &energy.short_periodic_torsion_kcal_per_mol,
                 &energy.short_lennard_jones_kcal_per_mol,
                 &energy.short_coulomb_kcal_per_mol,
                 &energy.short_total_kcal_per_mol,
                 &energy.pme_real_space_kcal_per_mol,
                 &energy.pme_reciprocal_space_kcal_per_mol,
                 &energy.pme_self_kcal_per_mol,
                 &energy.pme_pair_correction_kcal_per_mol,
                 &energy.pme_total_kcal_per_mol,
                 &energy.total_kcal_per_mol,
             }}) {
            *field = marker;
            marker += 1.0;
        }
        require_status(
            bg_particle_mesh_ewald_composite_force_soa_v1_init(
                &forces, sizeof(forces),
                BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION),
            BG_STATUS_OK, "failure-state force initializer failed");
        forces.atom_capacity = force_x.size();
        forces.atom_count = UINT64_C(77);
        forces.x_kcal_per_mol_angstrom = force_x.data();
        forces.y_kcal_per_mol_angstrom = force_y.data();
        forces.z_kcal_per_mol_angstrom = force_z.data();
        init_error(&error);
        error.code = BG_DIRECT_EWALD_ERROR_INVALID_PARAMETER;
        std::memcpy(error.detail, "stale", sizeof("stale"));
    }
};

struct BorrowedSpan final {
    const void *pointer = nullptr;
    std::size_t bytes = 0U;
};

void expect_borrowed_channel_alias_rejected(
    const bg_context *context,
    const bg_system *system,
    const bg_forcefield *forcefield,
    const bg_direct_ewald_model_v1 *direct_model,
    const bg_particle_mesh_reciprocal_model_v1 *reciprocal_model,
    const BorrowedSpan &span) {
    require(
        span.pointer != nullptr && span.bytes > 0U,
        "borrowed alias fixture contained an empty span");
    FailureState state;
    state.forces.x_kcal_per_mol_angstrom = reinterpret_cast<double *>(
        const_cast<void *>(span.pointer));
    const auto energy_before = state.energy;
    const auto forces_before = state.forces;
    const auto force_x_before = state.force_x;
    const auto force_y_before = state.force_y;
    const auto force_z_before = state.force_z;
    const auto error_before = state.error;
    std::vector<unsigned char> borrowed_before(span.bytes);
    std::memcpy(borrowed_before.data(), span.pointer, span.bytes);
    require_status(
        bg_context_evaluate_particle_mesh_ewald_composite_v1(
            context, system, forcefield, direct_model, reciprocal_model,
            &state.energy, &state.forces, &state.error),
        BG_STATUS_INVALID_ARGUMENT,
        "composite accepted a force channel aliasing borrowed storage");
    require(
        std::memcmp(&state.energy, &energy_before, sizeof(state.energy)) == 0,
        "borrowed alias failure changed energy");
    require(
        std::memcmp(&state.forces, &forces_before, sizeof(state.forces)) == 0,
        "borrowed alias failure changed force descriptor");
    require(state.force_x == force_x_before, "borrowed alias changed x scratch");
    require(state.force_y == force_y_before, "borrowed alias changed y scratch");
    require(state.force_z == force_z_before, "borrowed alias changed z scratch");
    require(
        std::memcmp(&state.error, &error_before, sizeof(state.error)) == 0,
        "borrowed alias failure changed typed error");
    require(
        std::memcmp(span.pointer, borrowed_before.data(), span.bytes) == 0,
        "borrowed alias failure changed borrowed storage");
}

void expect_failure_without_scientific_commit(
    const bg_context *context,
    const bg_system *system,
    const bg_forcefield *forcefield,
    const bg_direct_ewald_model_v1 *direct_model,
    const bg_particle_mesh_reciprocal_model_v1 *reciprocal_model,
    bg_status expected_status,
    bg_direct_ewald_error_code expected_code,
    const char *message,
    bool preserve_error = false) {
    FailureState state;
    const auto energy_before = state.energy;
    const auto force_x_before = state.force_x;
    const auto force_y_before = state.force_y;
    const auto force_z_before = state.force_z;
    const auto count_before = state.forces.atom_count;
    const auto error_before = state.error;
    require_status(
        bg_context_evaluate_particle_mesh_ewald_composite_v1(
            context, system, forcefield, direct_model, reciprocal_model,
            &state.energy, &state.forces, &state.error),
        expected_status, message);
    require(
        std::memcmp(&state.energy, &energy_before, sizeof(state.energy)) == 0,
        "failed composite evaluation changed energy");
    require(state.force_x == force_x_before, "failed evaluation changed x force");
    require(state.force_y == force_y_before, "failed evaluation changed y force");
    require(state.force_z == force_z_before, "failed evaluation changed z force");
    require(
        state.forces.atom_count == count_before,
        "failed evaluation changed force count");
    if (preserve_error) {
        require(
            std::memcmp(&state.error, &error_before, sizeof(state.error)) == 0,
            "prevalidation failure changed typed error");
    } else {
        require(
            state.error.code == expected_code,
            "failed evaluation set wrong typed-error code");
        require(
            expected_code != BG_DIRECT_EWALD_ERROR_NONE ||
                state.error.detail[0] == '\0',
            "untyped failure retained stale typed detail");
    }
}

void verify_compatibility_transactionality_and_aliases() {
    const Fixture fixture;
    const ContextPtr context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    const SystemPtr system = make_system(fixture, fixture.charge);
    const ForceFieldPtr forcefield = make_forcefield(fixture);
    const DirectModelPtr direct_model = make_direct_model(fixture);
    const ReciprocalModelPtr reciprocal_model =
        make_reciprocal_model(fixture);

    const DirectModelPtr no_pair_rules = make_direct_model(fixture, false);
    expect_failure_without_scientific_commit(
        context.get(), system.get(), forcefield.get(), no_pair_rules.get(),
        reciprocal_model.get(), BG_STATUS_INVALID_ARGUMENT,
        BG_DIRECT_EWALD_ERROR_NONE,
        "composite accepted a missing pair-rule projection");

    bg_direct_ewald_model_v1 exclusion_as_scale = *direct_model;
    exclusion_as_scale.pair_rules[0].is_exclusion = false;
    exclusion_as_scale.pair_rules[0].coulomb_scale = 0.0;
    expect_failure_without_scientific_commit(
        context.get(), system.get(), forcefield.get(), &exclusion_as_scale,
        reciprocal_model.get(), BG_STATUS_INVALID_ARGUMENT,
        BG_DIRECT_EWALD_ERROR_NONE,
        "composite accepted an explicit-zero scale in place of an exclusion");

    Fixture explicit_zero_fixture = fixture;
    explicit_zero_fixture.scale_coulomb[0] = 0.0;
    const SystemPtr explicit_zero_system = make_system(
        explicit_zero_fixture, explicit_zero_fixture.charge);
    const ForceFieldPtr explicit_zero_forcefield =
        make_forcefield(explicit_zero_fixture);
    const DirectModelPtr explicit_zero_model =
        make_direct_model(explicit_zero_fixture);
    const ReciprocalModelPtr explicit_zero_reciprocal =
        make_reciprocal_model(explicit_zero_fixture);
    bg_direct_ewald_model_v1 scale_as_exclusion = *explicit_zero_model;
    scale_as_exclusion.pair_rules[1].is_exclusion = true;
    expect_failure_without_scientific_commit(
        context.get(), explicit_zero_system.get(),
        explicit_zero_forcefield.get(), &scale_as_exclusion,
        explicit_zero_reciprocal.get(), BG_STATUS_INVALID_ARGUMENT,
        BG_DIRECT_EWALD_ERROR_NONE,
        "composite accepted an exclusion in place of an explicit-zero scale");

    bg_particle_mesh_reciprocal_model_v1 mismatched = *reciprocal_model;
    mismatched.alpha_per_angstrom = std::nextafter(
        mismatched.alpha_per_angstrom,
        std::numeric_limits<double>::infinity());
    expect_failure_without_scientific_commit(
        context.get(), system.get(), forcefield.get(), direct_model.get(),
        &mismatched, BG_STATUS_INVALID_ARGUMENT,
        BG_DIRECT_EWALD_ERROR_NONE,
        "composite accepted mismatched model alpha bits");

    {
        FailureState state;
        state.forces.atom_capacity = UINT64_C(3);
        const auto before = state;
        require_status(
            bg_context_evaluate_particle_mesh_ewald_composite_v1(
                context.get(), system.get(), forcefield.get(),
                direct_model.get(), reciprocal_model.get(), &state.energy,
                &state.forces, &state.error),
            BG_STATUS_BUFFER_TOO_SMALL,
            "composite accepted a short force capacity");
        require(
            std::memcmp(&state.energy, &before.energy, sizeof(state.energy)) ==
                0 &&
                state.force_x == before.force_x &&
                state.force_y == before.force_y &&
                state.force_z == before.force_z &&
                state.forces.atom_count == before.forces.atom_count,
            "short-capacity failure changed scientific outputs");
    }

    {
        FailureState state;
        state.forces.y_kcal_per_mol_angstrom = state.force_x.data();
        const auto energy_before = state.energy;
        const auto error_before = state.error;
        require_status(
            bg_context_evaluate_particle_mesh_ewald_composite_v1(
                context.get(), system.get(), forcefield.get(),
                direct_model.get(), reciprocal_model.get(), &state.energy,
                &state.forces, &state.error),
            BG_STATUS_INVALID_ARGUMENT,
            "composite accepted overlapping force channels");
        require(
            std::memcmp(
                &state.energy, &energy_before, sizeof(state.energy)) == 0,
            "force-overlap failure changed energy");
        require(
            std::memcmp(&state.error, &error_before, sizeof(state.error)) == 0,
            "force-overlap failure changed typed error");
    }

    for (int target = 0; target < 3; ++target) {
        FailureState state;
        if (target == 0) {
            state.forces.x_kcal_per_mol_angstrom =
                &state.energy.short_harmonic_bond_kcal_per_mol;
        } else if (target == 1) {
            state.forces.x_kcal_per_mol_angstrom =
                reinterpret_cast<double *>(&state.forces.atom_capacity);
        } else {
            state.forces.x_kcal_per_mol_angstrom =
                reinterpret_cast<double *>(state.error.detail);
        }
        const auto energy_before = state.energy;
        const auto forces_before = state.forces;
        const auto error_before = state.error;
        require_status(
            bg_context_evaluate_particle_mesh_ewald_composite_v1(
                context.get(), system.get(), forcefield.get(),
                direct_model.get(), reciprocal_model.get(), &state.energy,
                &state.forces, &state.error),
            BG_STATUS_INVALID_ARGUMENT,
            "composite accepted a force channel aliasing an output descriptor");
        require(
            std::memcmp(
                &state.energy, &energy_before, sizeof(state.energy)) == 0 &&
                std::memcmp(
                    &state.forces, &forces_before, sizeof(state.forces)) ==
                    0 &&
                std::memcmp(
                    &state.error, &error_before, sizeof(state.error)) == 0,
            "descriptor alias failure changed output storage");
    }

    std::vector<BorrowedSpan> borrowed_spans;
    const auto add_vector = [&](const auto &storage) {
        using Value = typename std::decay_t<decltype(storage)>::value_type;
        if (!storage.empty()) {
            borrowed_spans.push_back(BorrowedSpan{
                storage.data(), storage.size() * sizeof(Value)});
        }
    };
    add_vector(system->position_x);
    add_vector(system->position_y);
    add_vector(system->position_z);
    add_vector(system->velocity_x);
    add_vector(system->velocity_y);
    add_vector(system->velocity_z);
    add_vector(system->mass);
    add_vector(system->charge);
    add_vector(forcefield->sigma);
    add_vector(forcefield->epsilon);
    add_vector(forcefield->bonds.atom_i);
    add_vector(forcefield->bonds.atom_j);
    add_vector(forcefield->bonds.equilibrium);
    add_vector(forcefield->bonds.force_constant);
    add_vector(forcefield->angles.atom_i);
    add_vector(forcefield->angles.atom_j);
    add_vector(forcefield->angles.atom_k);
    add_vector(forcefield->angles.equilibrium);
    add_vector(forcefield->angles.force_constant);
    add_vector(forcefield->torsions.atom_i);
    add_vector(forcefield->torsions.atom_j);
    add_vector(forcefield->torsions.atom_k);
    add_vector(forcefield->torsions.atom_l);
    add_vector(forcefield->torsions.periodicity);
    add_vector(forcefield->torsions.phase);
    add_vector(forcefield->torsions.amplitude);
    add_vector(forcefield->exclusions);
    add_vector(forcefield->pair_scales);
    add_vector(direct_model->pair_rules);
    for (const BorrowedSpan &span : borrowed_spans) {
        expect_borrowed_channel_alias_rejected(
            context.get(), system.get(), forcefield.get(),
            direct_model.get(), reciprocal_model.get(), span);
    }

    {
        FailureState state;
        const bg_system system_before = *system;
        const auto energy_before = state.energy;
        const auto forces_before = state.forces;
        auto *aliased_error = reinterpret_cast<bg_direct_ewald_error_v1 *>(
            system->position_x.data());
        require_status(
            bg_context_evaluate_particle_mesh_ewald_composite_v1(
                context.get(), system.get(), forcefield.get(),
                direct_model.get(), reciprocal_model.get(), &state.energy,
                &state.forces, aliased_error),
            BG_STATUS_INVALID_ARGUMENT,
            "composite accepted typed error aliasing borrowed storage");
        require(
            system->position_x == system_before.position_x &&
                system->position_y == system_before.position_y &&
                system->position_z == system_before.position_z &&
                system->velocity_x == system_before.velocity_x &&
                system->velocity_y == system_before.velocity_y &&
                system->velocity_z == system_before.velocity_z &&
                system->mass == system_before.mass &&
                system->charge == system_before.charge,
            "typed-error alias failure changed system storage");
        require(
            std::memcmp(
                &state.energy, &energy_before, sizeof(state.energy)) == 0 &&
                std::memcmp(
                    &state.forces, &forces_before, sizeof(state.forces)) == 0,
            "typed-error alias failure changed output descriptors");
    }

    auto nonneutral_charge = fixture.charge;
    nonneutral_charge[3] = 0.31;
    const SystemPtr nonneutral = make_system(fixture, nonneutral_charge);
    expect_failure_without_scientific_commit(
        context.get(), nonneutral.get(), forcefield.get(), direct_model.get(),
        reciprocal_model.get(), BG_STATUS_NUMERICAL_ERROR,
        BG_DIRECT_EWALD_ERROR_NON_NEUTRAL_SYSTEM,
        "composite accepted a non-neutral system");

    {
        FailureState state;
        const auto energy_before = state.energy;
        const auto force_x_before = state.force_x;
        const auto force_y_before = state.force_y;
        const auto force_z_before = state.force_z;
        require_status(
            bg_context_evaluate_particle_mesh_ewald_composite_v1(
                context.get(), nonneutral.get(), forcefield.get(),
                direct_model.get(), reciprocal_model.get(), &state.energy,
                &state.forces, &state.error),
            BG_STATUS_NUMERICAL_ERROR,
            "late typed failure unexpectedly succeeded");
        require(
            state.error.code == BG_DIRECT_EWALD_ERROR_NON_NEUTRAL_SYSTEM,
            "late typed failure set the wrong code");
        require(
            std::memcmp(
                &state.energy, &energy_before, sizeof(state.energy)) == 0 &&
                state.force_x == force_x_before &&
                state.force_y == force_y_before &&
                state.force_z == force_z_before,
            "late typed failure changed scientific outputs");
        require_status(
            bg_context_evaluate_particle_mesh_ewald_composite_v1(
                context.get(), system.get(), forcefield.get(),
                direct_model.get(), reciprocal_model.get(), &state.energy,
                &state.forces, &state.error),
            BG_STATUS_OK,
            "valid evaluation did not recover after a typed failure");
        require(
            state.error.code == BG_DIRECT_EWALD_ERROR_NONE &&
                state.error.detail[0] == '\0' &&
                state.forces.atom_count == fixture.x.size(),
            "recovery left stale typed-error or force-count state");
    }
}

void verify_backend_preflight_precedes_other_arguments() {
    const auto *invalid_system =
        reinterpret_cast<const bg_system *>(static_cast<std::uintptr_t>(1U));
    const auto *invalid_forcefield = reinterpret_cast<const bg_forcefield *>(
        static_cast<std::uintptr_t>(1U));
    const auto *invalid_direct = reinterpret_cast<
        const bg_direct_ewald_model_v1 *>(static_cast<std::uintptr_t>(1U));
    const auto *invalid_reciprocal = reinterpret_cast<
        const bg_particle_mesh_reciprocal_model_v1 *>(
        static_cast<std::uintptr_t>(1U));
    auto *invalid_energy = reinterpret_cast<
        bg_particle_mesh_ewald_composite_energy_components_v1 *>(
        static_cast<std::uintptr_t>(1U));
    auto *invalid_forces = reinterpret_cast<
        bg_particle_mesh_ewald_composite_force_soa_v1 *>(
        static_cast<std::uintptr_t>(1U));
    auto *invalid_error = reinterpret_cast<bg_direct_ewald_error_v1 *>(
        static_cast<std::uintptr_t>(1U));

    for (const bg_backend lane :
         {BG_BACKEND_AUTO, BG_BACKEND_HIP_SAFE, BG_BACKEND_HIP_FAST}) {
        bg_context context{};
        context.requested_backend = lane;
        context.backend = lane;
        require_status(
            bg_context_evaluate_particle_mesh_ewald_composite_v1(
                &context, invalid_system, invalid_forcefield, invalid_direct,
                invalid_reciprocal, invalid_energy, invalid_forces,
                invalid_error),
            BG_STATUS_UNSUPPORTED_BACKEND,
            "unsupported backend inspected a later argument");
    }
    bg_context mismatch{};
    mismatch.requested_backend = BG_BACKEND_CPP_CPU_REFERENCE;
    mismatch.backend = BG_BACKEND_RUST_CPU;
    require_status(
        bg_context_evaluate_particle_mesh_ewald_composite_v1(
            &mismatch, invalid_system, invalid_forcefield, invalid_direct,
            invalid_reciprocal, invalid_energy, invalid_forces,
            invalid_error),
        BG_STATUS_ABI_MISMATCH,
        "backend mismatch inspected a later argument");
}

}  // namespace

int main() {
    verify_abi_layout_profile_and_initializers();
    verify_parent_composition_repeat_parity_and_energy_only();
    verify_direct_bound_independence_and_mesh_convergence();
    verify_symmetry_invariances();
    verify_central_finite_difference();
    verify_compatibility_transactionality_and_aliases();
    verify_backend_preflight_precedes_other_arguments();
    return 0;
}
