#define BG_DISABLE_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#define BG_DISABLE_DIRECT_EWALD_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#define BG_DISABLE_DIRECT_EWALD_COMPOSITE_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#include "betelgeuze/direct_ewald_composite.h"

#include "../src/internal.hpp"

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

namespace {

[[noreturn]] void fail_test(const char *message) {
    std::fprintf(stderr, "direct-Ewald composite test failure: %s\n", message);
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
            "direct-Ewald composite test failure: %s "
            "(expected %d, observed %d: %s)\n",
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

void require_near(double actual, double expected, const char *message) {
    const double scale = std::max(1.0, std::abs(expected));
    require(std::isfinite(actual), message);
    require(std::abs(actual - expected) <= 5.0e-12 * scale, message);
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

struct ModelDeleter final {
    void operator()(bg_direct_ewald_model_v1 *value) const noexcept {
        bg_direct_ewald_model_v1_destroy(value);
    }
};

using ContextPtr = std::unique_ptr<bg_context, ContextDeleter>;
using SystemPtr = std::unique_ptr<bg_system, SystemDeleter>;
using ForceFieldPtr = std::unique_ptr<bg_forcefield, ForceFieldDeleter>;
using ModelPtr = std::unique_ptr<bg_direct_ewald_model_v1, ModelDeleter>;

struct Fixture final {
    std::array<double, 4> x{{1.25, 3.1, 5.2, 7.4}};
    std::array<double, 4> y{{2.5, 3.2, 5.3, 6.1}};
    std::array<double, 4> z{{3.75, 4.4, 4.7, 6.3}};
    std::array<double, 4> mass{{12.0, 14.0, 16.0, 19.0}};
    std::array<double, 4> charge{{
        0.7, -0.4, -0.6, 0.30000000000000004}};
    std::array<double, 4> sigma{{1.1, 1.2, 1.3, 1.4}};
    std::array<double, 4> epsilon{{0.15, 0.20, 0.25, 0.30}};

    std::array<uint64_t, 1> bond_i{{0}};
    std::array<uint64_t, 1> bond_j{{1}};
    std::array<double, 1> bond_equilibrium{{5.0}};
    std::array<double, 1> bond_force_constant{{3.0}};

    std::array<uint64_t, 1> angle_i{{0}};
    std::array<uint64_t, 1> angle_j{{1}};
    std::array<uint64_t, 1> angle_k{{2}};
    std::array<double, 1> angle_equilibrium{{1.4}};
    std::array<double, 1> angle_force_constant{{2.0}};

    std::array<uint64_t, 1> torsion_i{{0}};
    std::array<uint64_t, 1> torsion_j{{1}};
    std::array<uint64_t, 1> torsion_k{{2}};
    std::array<uint64_t, 1> torsion_l{{3}};
    std::array<uint32_t, 1> torsion_periodicity{{3}};
    std::array<double, 1> torsion_phase{{0.4}};
    std::array<double, 1> torsion_amplitude{{0.7}};

    std::array<uint64_t, 1> exclusion_i{{0}};
    std::array<uint64_t, 1> exclusion_j{{1}};
    std::array<uint64_t, 1> scale_i{{2}};
    std::array<uint64_t, 1> scale_j{{3}};
    std::array<double, 1> scale_lennard_jones{{0.25}};
    std::array<double, 1> scale_coulomb{{0.5}};

    std::array<double, 3> cell{{18.0, 20.0, 22.0}};
    uint32_t periodic_axes_mask = BG_PERIODIC_AXES_ALL;
    double cutoff = 8.9;
    double switch_start = 7.0;
    double dielectric = 1.0;
    double screening_kappa = 0.0;
    double minimum_pair_distance = 1.0e-8;
};

enum class ModelVariant {
    matching,
    no_pair_rules,
    scaled_zero_instead_of_exclusion,
    exclusion_instead_of_scaled_zero,
    different_coulomb_scale,
    different_cell,
    different_atom_count,
};

void init_error(bg_direct_ewald_error_v1 *error) {
    require_status(
        bg_direct_ewald_error_v1_init(
            error, sizeof(*error), BG_DIRECT_EWALD_ABI_VERSION),
        BG_STATUS_OK,
        "direct-Ewald error initializer failed");
}

ContextPtr make_context(bg_backend backend) {
    bg_context_options options{};
    require_status(
        bg_context_options_init(&options, sizeof(options), BG_ABI_VERSION),
        BG_STATUS_OK,
        "context initializer failed");
    options.backend = backend;
    bg_context *raw = nullptr;
    require_status(
        bg_context_create(&options, &raw),
        BG_STATUS_OK,
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
        BG_STATUS_OK,
        "particle initializer failed");
    particles.particle_count = fixture.x.size();
    particles.position_x_angstrom = fixture.x.data();
    particles.position_y_angstrom = fixture.y.data();
    particles.position_z_angstrom = fixture.z.data();
    particles.mass_dalton = fixture.mass.data();
    particles.charge_elementary = charge.data();
    bg_system *raw = nullptr;
    require_status(
        bg_system_create(&particles, &raw),
        BG_STATUS_OK,
        "system creation failed");
    require(raw != nullptr, "system creation returned null");
    return SystemPtr(raw);
}

ForceFieldPtr make_forcefield(const Fixture &fixture) {
    bg_forcefield_soa_v1 parameters{};
    require_status(
        bg_forcefield_soa_v1_init(
            &parameters, sizeof(parameters), BG_ABI_VERSION),
        BG_STATUS_OK,
        "force-field initializer failed");
    parameters.atom_count = fixture.sigma.size();
    parameters.unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
    parameters.periodic_axes_mask = fixture.periodic_axes_mask;
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

    std::copy(fixture.cell.begin(), fixture.cell.end(), parameters.cell_lengths_angstrom);
    parameters.cutoff_angstrom = fixture.cutoff;
    parameters.switch_start_angstrom = fixture.switch_start;
    parameters.dielectric = fixture.dielectric;
    parameters.screening_kappa_per_angstrom = fixture.screening_kappa;
    parameters.minimum_pair_distance_angstrom = fixture.minimum_pair_distance;

    bg_forcefield *raw = nullptr;
    require_status(
        bg_forcefield_create(&parameters, &raw),
        BG_STATUS_OK,
        "force-field creation failed");
    require(raw != nullptr, "force-field creation returned null");
    return ForceFieldPtr(raw);
}

ModelPtr make_model(const Fixture &fixture, ModelVariant variant) {
    bg_direct_ewald_parameters_v1 parameters{};
    require_status(
        bg_direct_ewald_parameters_v1_init(
            &parameters, sizeof(parameters), BG_DIRECT_EWALD_ABI_VERSION),
        BG_STATUS_OK,
        "direct-Ewald parameter initializer failed");
    parameters.atom_count =
        variant == ModelVariant::different_atom_count ? UINT64_C(3)
                                                      : fixture.x.size();
    std::copy(fixture.cell.begin(), fixture.cell.end(), parameters.cell_lengths_angstrom);
    if (variant == ModelVariant::different_cell) {
        parameters.cell_lengths_angstrom[0] = 19.0;
    }
    parameters.alpha_per_angstrom = 0.31;
    parameters.real_space_cutoff_angstrom = fixture.cutoff;
    parameters.reciprocal_max_indices[0] = 5;
    parameters.reciprocal_max_indices[1] = 5;
    parameters.reciprocal_max_indices[2] = 5;
    parameters.dielectric = fixture.dielectric;
    parameters.minimum_pair_distance_angstrom = fixture.minimum_pair_distance;

    std::array<uint64_t, 2> scale_i{{0, 2}};
    std::array<uint64_t, 2> scale_j{{1, 3}};
    std::array<double, 2> scale_value{{0.0, fixture.scale_coulomb[0]}};
    std::array<uint64_t, 2> exclusion_i{{0, 2}};
    std::array<uint64_t, 2> exclusion_j{{1, 3}};
    std::array<double, 1> different_scale{{0.75}};
    if (variant == ModelVariant::matching ||
        variant == ModelVariant::different_cell) {
        parameters.exclusion_count = fixture.exclusion_i.size();
        parameters.exclusion_atom_i = fixture.exclusion_i.data();
        parameters.exclusion_atom_j = fixture.exclusion_j.data();
        parameters.pair_scale_count = fixture.scale_i.size();
        parameters.pair_scale_atom_i = fixture.scale_i.data();
        parameters.pair_scale_atom_j = fixture.scale_j.data();
        parameters.pair_scale_coulomb = fixture.scale_coulomb.data();
    } else if (variant == ModelVariant::scaled_zero_instead_of_exclusion) {
        parameters.pair_scale_count = scale_i.size();
        parameters.pair_scale_atom_i = scale_i.data();
        parameters.pair_scale_atom_j = scale_j.data();
        parameters.pair_scale_coulomb = scale_value.data();
    } else if (variant == ModelVariant::exclusion_instead_of_scaled_zero) {
        parameters.exclusion_count = exclusion_i.size();
        parameters.exclusion_atom_i = exclusion_i.data();
        parameters.exclusion_atom_j = exclusion_j.data();
    } else if (variant == ModelVariant::different_coulomb_scale) {
        parameters.exclusion_count = fixture.exclusion_i.size();
        parameters.exclusion_atom_i = fixture.exclusion_i.data();
        parameters.exclusion_atom_j = fixture.exclusion_j.data();
        parameters.pair_scale_count = fixture.scale_i.size();
        parameters.pair_scale_atom_i = fixture.scale_i.data();
        parameters.pair_scale_atom_j = fixture.scale_j.data();
        parameters.pair_scale_coulomb = different_scale.data();
    }

    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    bg_direct_ewald_model_v1 *raw = nullptr;
    require_status(
        bg_direct_ewald_model_v1_create(&parameters, &raw, &error),
        BG_STATUS_OK,
        "direct-Ewald model creation failed");
    require(raw != nullptr, "direct-Ewald model creation returned null");
    require(error.code == BG_DIRECT_EWALD_ERROR_NONE, "model creation set a typed error");
    return ModelPtr(raw);
}

struct CompositeResult final {
    bg_direct_ewald_composite_energy_components_v1 energy{};
    std::array<double, 4> force_x{};
    std::array<double, 4> force_y{};
    std::array<double, 4> force_z{};
};

struct ParentResult final {
    bg_energy_components_v1 short_energy{};
    bg_direct_ewald_energy_components_v1 ewald_energy{};
    std::array<double, 4> short_force_x{};
    std::array<double, 4> short_force_y{};
    std::array<double, 4> short_force_z{};
    std::array<double, 4> ewald_force_x{};
    std::array<double, 4> ewald_force_y{};
    std::array<double, 4> ewald_force_z{};
};

CompositeResult evaluate_composite(
    const bg_context *context,
    const bg_system *system,
    const bg_forcefield *forcefield,
    const bg_direct_ewald_model_v1 *model) {
    CompositeResult result;
    require_status(
        bg_direct_ewald_composite_energy_components_v1_init(
            &result.energy, sizeof(result.energy),
            BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION),
        BG_STATUS_OK,
        "composite energy initializer failed");
    bg_direct_ewald_composite_force_soa_v1 forces{};
    require_status(
        bg_direct_ewald_composite_force_soa_v1_init(
            &forces, sizeof(forces), BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION),
        BG_STATUS_OK,
        "composite force initializer failed");
    forces.atom_capacity = result.force_x.size();
    forces.x_kcal_per_mol_angstrom = result.force_x.data();
    forces.y_kcal_per_mol_angstrom = result.force_y.data();
    forces.z_kcal_per_mol_angstrom = result.force_z.data();
    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    require_status(
        bg_context_evaluate_direct_ewald_composite_v1(
            context, system, forcefield, model, &result.energy, &forces,
            &error),
        BG_STATUS_OK,
        "composite evaluation failed");
    require(forces.atom_count == result.force_x.size(), "composite force count was not committed");
    require(error.code == BG_DIRECT_EWALD_ERROR_NONE, "composite success set a typed error");
    require(error.detail[0] == '\0', "composite success set typed-error detail");
    return result;
}

bg_direct_ewald_composite_energy_components_v1 evaluate_composite_energy(
    const bg_context *context,
    const bg_system *system,
    const bg_forcefield *forcefield,
    const bg_direct_ewald_model_v1 *model) {
    bg_direct_ewald_composite_energy_components_v1 energy{};
    require_status(
        bg_direct_ewald_composite_energy_components_v1_init(
            &energy, sizeof(energy), BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION),
        BG_STATUS_OK,
        "composite energy-only initializer failed");
    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    require_status(
        bg_context_evaluate_direct_ewald_composite_v1(
            context, system, forcefield, model, &energy, nullptr, &error),
        BG_STATUS_OK,
        "composite energy-only evaluation failed");
    require(error.code == BG_DIRECT_EWALD_ERROR_NONE, "energy-only success set a typed error");
    return energy;
}

ParentResult evaluate_parents(
    const bg_context *context,
    const bg_system *charged_system,
    const bg_system *zero_charge_system,
    const bg_forcefield *forcefield,
    const bg_direct_ewald_model_v1 *model) {
    ParentResult result;
    require_status(
        bg_energy_components_v1_init(
            &result.short_energy, sizeof(result.short_energy), BG_ABI_VERSION),
        BG_STATUS_OK,
        "short-range energy initializer failed");
    bg_force_soa_v1 short_forces{};
    require_status(
        bg_force_soa_v1_init(
            &short_forces, sizeof(short_forces), BG_ABI_VERSION),
        BG_STATUS_OK,
        "short-range force initializer failed");
    short_forces.particle_capacity = result.short_force_x.size();
    short_forces.x_kcal_per_mol_angstrom = result.short_force_x.data();
    short_forces.y_kcal_per_mol_angstrom = result.short_force_y.data();
    short_forces.z_kcal_per_mol_angstrom = result.short_force_z.data();
    require_status(
        bg_context_evaluate(
            context, zero_charge_system, forcefield, &result.short_energy,
            &short_forces),
        BG_STATUS_OK,
        "zero-charge short-range parent evaluation failed");
    require(short_forces.particle_count == result.short_force_x.size(), "short parent force count differed");

    require_status(
        bg_direct_ewald_energy_components_v1_init(
            &result.ewald_energy, sizeof(result.ewald_energy),
            BG_DIRECT_EWALD_ABI_VERSION),
        BG_STATUS_OK,
        "direct-Ewald parent energy initializer failed");
    bg_direct_ewald_force_soa_v1 ewald_forces{};
    require_status(
        bg_direct_ewald_force_soa_v1_init(
            &ewald_forces, sizeof(ewald_forces),
            BG_DIRECT_EWALD_ABI_VERSION),
        BG_STATUS_OK,
        "direct-Ewald parent force initializer failed");
    ewald_forces.atom_capacity = result.ewald_force_x.size();
    ewald_forces.x_kcal_per_mol_angstrom = result.ewald_force_x.data();
    ewald_forces.y_kcal_per_mol_angstrom = result.ewald_force_y.data();
    ewald_forces.z_kcal_per_mol_angstrom = result.ewald_force_z.data();
    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    require_status(
        bg_context_evaluate_direct_ewald_v1(
            context, charged_system, model, &result.ewald_energy,
            &ewald_forces, &error),
        BG_STATUS_OK,
        "direct-Ewald parent evaluation failed");
    require(ewald_forces.atom_count == result.ewald_force_x.size(), "Ewald parent force count differed");
    require(error.code == BG_DIRECT_EWALD_ERROR_NONE, "Ewald parent success set a typed error");
    return result;
}

std::array<double, 12> energy_values(
    const bg_direct_ewald_composite_energy_components_v1 &energy) noexcept {
    return {{
        energy.short_harmonic_bond_kcal_per_mol,
        energy.short_harmonic_angle_kcal_per_mol,
        energy.short_periodic_torsion_kcal_per_mol,
        energy.short_lennard_jones_kcal_per_mol,
        energy.short_coulomb_kcal_per_mol,
        energy.short_total_kcal_per_mol,
        energy.ewald_real_space_kcal_per_mol,
        energy.ewald_reciprocal_space_kcal_per_mol,
        energy.ewald_self_kcal_per_mol,
        energy.ewald_pair_correction_kcal_per_mol,
        energy.ewald_total_kcal_per_mol,
        energy.total_kcal_per_mol,
    }};
}

void require_energy_exact(
    const bg_direct_ewald_composite_energy_components_v1 &actual,
    const bg_direct_ewald_composite_energy_components_v1 &expected,
    const char *message) {
    const auto actual_values = energy_values(actual);
    const auto expected_values = energy_values(expected);
    for (std::size_t index = 0; index < actual_values.size(); ++index) {
        require_exact(actual_values[index], expected_values[index], message);
    }
}

void require_result_exact(
    const CompositeResult &actual,
    const CompositeResult &expected,
    const char *message) {
    require_energy_exact(actual.energy, expected.energy, message);
    for (std::size_t atom = 0; atom < actual.force_x.size(); ++atom) {
        require_exact(actual.force_x[atom], expected.force_x[atom], message);
        require_exact(actual.force_y[atom], expected.force_y[atom], message);
        require_exact(actual.force_z[atom], expected.force_z[atom], message);
    }
}

void require_system_exact(
    const bg_system &actual,
    const bg_system &expected,
    const char *message) {
    require(actual.unit_system == expected.unit_system, message);
    require(actual.position_x == expected.position_x, message);
    require(actual.position_y == expected.position_y, message);
    require(actual.position_z == expected.position_z, message);
    require(actual.velocity_x == expected.velocity_x, message);
    require(actual.velocity_y == expected.velocity_y, message);
    require(actual.velocity_z == expected.velocity_z, message);
    require(actual.mass == expected.mass, message);
    require(actual.charge == expected.charge, message);
}

void require_composite_matches_parents(
    const CompositeResult &composite,
    const ParentResult &parents) {
    require_exact(
        composite.energy.short_harmonic_bond_kcal_per_mol,
        parents.short_energy.harmonic_bond_kcal_per_mol,
        "composite bond component differed from short parent");
    require_exact(
        composite.energy.short_harmonic_angle_kcal_per_mol,
        parents.short_energy.harmonic_angle_kcal_per_mol,
        "composite angle component differed from short parent");
    require_exact(
        composite.energy.short_periodic_torsion_kcal_per_mol,
        parents.short_energy.periodic_torsion_kcal_per_mol,
        "composite torsion component differed from short parent");
    require_exact(
        composite.energy.short_lennard_jones_kcal_per_mol,
        parents.short_energy.lennard_jones_kcal_per_mol,
        "composite LJ component differed from short parent");
    require_exact(
        composite.energy.short_coulomb_kcal_per_mol,
        parents.short_energy.coulomb_kcal_per_mol,
        "composite short Coulomb component differed from zero-charge parent");
    require_exact(
        composite.energy.short_coulomb_kcal_per_mol,
        0.0,
        "composite short Coulomb component was not exact positive zero");
    require_exact(
        composite.energy.short_total_kcal_per_mol,
        parents.short_energy.total_kcal_per_mol,
        "composite short total differed from short parent");
    require_exact(
        composite.energy.ewald_real_space_kcal_per_mol,
        parents.ewald_energy.real_space_kcal_per_mol,
        "composite real-space component differed from Ewald parent");
    require_exact(
        composite.energy.ewald_reciprocal_space_kcal_per_mol,
        parents.ewald_energy.reciprocal_space_kcal_per_mol,
        "composite reciprocal component differed from Ewald parent");
    require_exact(
        composite.energy.ewald_self_kcal_per_mol,
        parents.ewald_energy.self_kcal_per_mol,
        "composite self component differed from Ewald parent");
    require_exact(
        composite.energy.ewald_pair_correction_kcal_per_mol,
        parents.ewald_energy.pair_correction_kcal_per_mol,
        "composite pair correction differed from Ewald parent");
    require_exact(
        composite.energy.ewald_total_kcal_per_mol,
        parents.ewald_energy.total_kcal_per_mol,
        "composite Ewald total differed from Ewald parent");
    require_exact(
        composite.energy.total_kcal_per_mol,
        parents.short_energy.total_kcal_per_mol +
            parents.ewald_energy.total_kcal_per_mol,
        "composite grand total used a different addition order");
    for (std::size_t atom = 0; atom < composite.force_x.size(); ++atom) {
        require_exact(
            composite.force_x[atom],
            parents.short_force_x[atom] + parents.ewald_force_x[atom],
            "composite x force differed from parent sum");
        require_exact(
            composite.force_y[atom],
            parents.short_force_y[atom] + parents.ewald_force_y[atom],
            "composite y force differed from parent sum");
        require_exact(
            composite.force_z[atom],
            parents.short_force_z[atom] + parents.ewald_force_z[atom],
            "composite z force differed from parent sum");
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
            BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION),
        BG_STATUS_ABI_MISMATCH,
        "composite initializer accepted a short descriptor");
    require(
        std::memcmp(&descriptor, before.data(), sizeof(descriptor)) == 0,
        "composite initializer changed storage on size mismatch");
    require_status(
        initializer(&descriptor, sizeof(descriptor), UINT32_C(99)),
        BG_STATUS_ABI_MISMATCH,
        "composite initializer accepted a wrong version");
    require(
        std::memcmp(&descriptor, before.data(), sizeof(descriptor)) == 0,
        "composite initializer changed storage on version mismatch");
    require_status(
        initializer(
            &descriptor, sizeof(descriptor),
            BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION),
        BG_STATUS_OK,
        "composite initializer rejected the current ABI");
    require(descriptor.struct_size == sizeof(descriptor), "composite initializer size differed");
    require(
        descriptor.abi_version == BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION,
        "composite initializer version differed");
}

void verify_abi_and_initializers() {
    static_assert(
        std::is_standard_layout_v<
            bg_direct_ewald_composite_energy_components_v1>);
    static_assert(
        std::is_standard_layout_v<bg_direct_ewald_composite_force_soa_v1>);
    static_assert(sizeof(bg_direct_ewald_composite_energy_components_v1) == 144U);
    static_assert(sizeof(bg_direct_ewald_composite_force_soa_v1) == 88U);
    require(bg_direct_ewald_composite_abi_version() == 1U, "composite ABI version differed");
    require(bg_direct_ewald_composite_abi_version_major() == 1U, "composite ABI major differed");
    require(bg_direct_ewald_composite_abi_version_minor() == 0U, "composite ABI minor differed");
    require(
        std::string(bg_direct_ewald_composite_abi_version_string()) == "1.0.0",
        "composite ABI version string differed");
    require(
        std::string(bg_direct_ewald_composite_v1_profile_id()) ==
            "betelgeuze.native_direct_ewald_composite/1.0.0",
        "composite profile identity differed");
    verify_initializer_transactionality<
        bg_direct_ewald_composite_energy_components_v1>(
        bg_direct_ewald_composite_energy_components_v1_init);
    verify_initializer_transactionality<
        bg_direct_ewald_composite_force_soa_v1>(
        bg_direct_ewald_composite_force_soa_v1_init);
}

void verify_parent_composition_and_cpu_parity() {
    Fixture fixture;
    const std::array<double, 4> zero_charge{{0.0, 0.0, 0.0, 0.0}};
    const SystemPtr charged_system = make_system(fixture, fixture.charge);
    const SystemPtr zero_charge_system = make_system(fixture, zero_charge);
    const ForceFieldPtr forcefield = make_forcefield(fixture);
    const ModelPtr model = make_model(fixture, ModelVariant::matching);
    const bg_system charged_system_before = *charged_system;

    /* Both borrowed handles must remain independent of their create inputs. */
    fixture.x[0] = 900.0;
    fixture.sigma[0] = 9.0;
    fixture.bond_equilibrium[0] = 9.0;
    fixture.exclusion_i[0] = 2;
    fixture.exclusion_j[0] = 3;
    fixture.scale_i[0] = 0;
    fixture.scale_j[0] = 1;
    fixture.scale_lennard_jones[0] = 1.0;
    fixture.scale_coulomb[0] = 1.0;
    fixture.cell[0] = 90.0;

    const ContextPtr cpp_context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    const ParentResult cpp_parents = evaluate_parents(
        cpp_context.get(), charged_system.get(), zero_charge_system.get(),
        forcefield.get(), model.get());
    const CompositeResult cpp = evaluate_composite(
        cpp_context.get(), charged_system.get(), forcefield.get(), model.get());
    const CompositeResult cpp_repeat = evaluate_composite(
        cpp_context.get(), charged_system.get(), forcefield.get(), model.get());
    require_composite_matches_parents(cpp, cpp_parents);
    require_result_exact(cpp_repeat, cpp, "C++ composite repeat was not bitwise exact");

    require(cpp.energy.short_harmonic_bond_kcal_per_mol != 0.0, "bond component vanished");
    require(cpp.energy.short_harmonic_angle_kcal_per_mol != 0.0, "angle component vanished");
    require(cpp.energy.short_periodic_torsion_kcal_per_mol != 0.0, "torsion component vanished");
    require(cpp.energy.short_lennard_jones_kcal_per_mol != 0.0, "LJ component vanished");
    require(cpp.energy.ewald_real_space_kcal_per_mol != 0.0, "real-space component vanished");
    require(cpp.energy.ewald_reciprocal_space_kcal_per_mol != 0.0, "reciprocal component vanished");
    require(cpp.energy.ewald_self_kcal_per_mol != 0.0, "self component vanished");
    require(cpp.energy.ewald_pair_correction_kcal_per_mol != 0.0, "pair correction vanished");

    const auto cpp_energy_only = evaluate_composite_energy(
        cpp_context.get(), charged_system.get(), forcefield.get(), model.get());
    const auto cpp_energy_only_repeat = evaluate_composite_energy(
        cpp_context.get(), charged_system.get(), forcefield.get(), model.get());
    require_energy_exact(cpp_energy_only, cpp.energy, "C++ energy-only bits differed from full evaluation");
    require_energy_exact(cpp_energy_only_repeat, cpp_energy_only, "C++ energy-only repeat differed");

    const ContextPtr rust_context = make_context(BG_BACKEND_RUST_CPU);
    const ParentResult rust_parents = evaluate_parents(
        rust_context.get(), charged_system.get(), zero_charge_system.get(),
        forcefield.get(), model.get());
    const CompositeResult rust = evaluate_composite(
        rust_context.get(), charged_system.get(), forcefield.get(), model.get());
    const CompositeResult rust_repeat = evaluate_composite(
        rust_context.get(), charged_system.get(), forcefield.get(), model.get());
    require_composite_matches_parents(rust, rust_parents);
    require_result_exact(rust_repeat, rust, "Rust composite repeat was not bitwise exact");
    const auto rust_energy_only = evaluate_composite_energy(
        rust_context.get(), charged_system.get(), forcefield.get(), model.get());
    require_energy_exact(rust_energy_only, rust.energy, "Rust energy-only bits differed from full evaluation");

    const auto cpp_energy = energy_values(cpp.energy);
    const auto rust_energy = energy_values(rust.energy);
    for (std::size_t index = 0; index < cpp_energy.size(); ++index) {
        require_near(cpp_energy[index], rust_energy[index], "C++/Rust composite energy parity failed");
    }
    for (std::size_t atom = 0; atom < cpp.force_x.size(); ++atom) {
        require_near(cpp.force_x[atom], rust.force_x[atom], "C++/Rust x-force parity failed");
        require_near(cpp.force_y[atom], rust.force_y[atom], "C++/Rust y-force parity failed");
        require_near(cpp.force_z[atom], rust.force_z[atom], "C++/Rust z-force parity failed");
    }
    require_system_exact(
        *charged_system, charged_system_before,
        "composite evaluation mutated the caller system");
}

void verify_central_finite_difference() {
    const Fixture fixture;
    constexpr double displacement = 1.0e-5;
    const SystemPtr system = make_system(fixture, fixture.charge);
    const ForceFieldPtr forcefield = make_forcefield(fixture);
    const ModelPtr model = make_model(fixture, ModelVariant::matching);

    for (const bg_backend backend :
         {BG_BACKEND_CPP_CPU_REFERENCE, BG_BACKEND_RUST_CPU}) {
        const ContextPtr context = make_context(backend);
        const CompositeResult analytic = evaluate_composite(
            context.get(), system.get(), forcefield.get(), model.get());
        const std::array<const std::array<double, 4> *, 3> analytic_axes{{
            &analytic.force_x,
            &analytic.force_y,
            &analytic.force_z,
        }};
        for (std::size_t atom = 0; atom < fixture.x.size(); ++atom) {
            for (std::size_t axis = 0; axis < analytic_axes.size(); ++axis) {
                Fixture plus_fixture = fixture;
                Fixture minus_fixture = fixture;
                const std::array<std::array<double, 4> *, 3> plus_axes{{
                    &plus_fixture.x,
                    &plus_fixture.y,
                    &plus_fixture.z,
                }};
                const std::array<std::array<double, 4> *, 3> minus_axes{{
                    &minus_fixture.x,
                    &minus_fixture.y,
                    &minus_fixture.z,
                }};
                (*plus_axes[axis])[atom] += displacement;
                (*minus_axes[axis])[atom] -= displacement;
                const SystemPtr plus_system = make_system(
                    plus_fixture, plus_fixture.charge);
                const SystemPtr minus_system = make_system(
                    minus_fixture, minus_fixture.charge);
                const auto plus = evaluate_composite_energy(
                    context.get(), plus_system.get(), forcefield.get(),
                    model.get());
                const auto minus = evaluate_composite_energy(
                    context.get(), minus_system.get(), forcefield.get(),
                    model.get());
                const double numerical_force =
                    -(plus.total_kcal_per_mol -
                      minus.total_kcal_per_mol) /
                    (2.0 * displacement);
                const double analytic_force =
                    (*analytic_axes[axis])[atom];
                const double scale =
                    std::max(1.0, std::abs(analytic_force));
                require(
                    std::isfinite(numerical_force) &&
                        std::abs(numerical_force - analytic_force) <=
                            2.0e-6 * scale,
                    "composite force failed the central finite-difference check");
            }
        }
    }
}

void verify_unused_capacity_overlap_is_allowed() {
    const Fixture fixture;
    const SystemPtr system = make_system(fixture, fixture.charge);
    const ForceFieldPtr forcefield = make_forcefield(fixture);
    const ModelPtr model = make_model(fixture, ModelVariant::matching);
    for (const bg_backend backend :
         {BG_BACKEND_CPP_CPU_REFERENCE, BG_BACKEND_RUST_CPU}) {
        const ContextPtr context = make_context(backend);
        const CompositeResult expected = evaluate_composite(
            context.get(), system.get(), forcefield.get(), model.get());
        bg_direct_ewald_composite_energy_components_v1 energy{};
        require_status(
            bg_direct_ewald_composite_energy_components_v1_init(
                &energy, sizeof(energy),
                BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION),
            BG_STATUS_OK,
            "unused-tail energy initializer failed");
        bg_direct_ewald_composite_force_soa_v1 forces{};
        require_status(
            bg_direct_ewald_composite_force_soa_v1_init(
                &forces, sizeof(forces),
                BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION),
            BG_STATUS_OK,
            "unused-tail force initializer failed");
        std::array<double, 12> shared_xy{};
        std::array<double, 8> force_z{};
        shared_xy.fill(std::numeric_limits<double>::quiet_NaN());
        force_z.fill(std::numeric_limits<double>::quiet_NaN());
        forces.atom_capacity = UINT64_C(8);
        forces.x_kcal_per_mol_angstrom = shared_xy.data();
        forces.y_kcal_per_mol_angstrom = shared_xy.data() + 4U;
        forces.z_kcal_per_mol_angstrom = force_z.data();
        bg_direct_ewald_error_v1 error{};
        init_error(&error);
        require_status(
            bg_context_evaluate_direct_ewald_composite_v1(
                context.get(), system.get(), forcefield.get(), model.get(),
                &energy, &forces, &error),
            BG_STATUS_OK,
            "composite rejected disjoint used spans with overlapping unused tails");
        require_energy_exact(
            energy, expected.energy,
            "unused-tail capacity changed composite energy");
        require(forces.atom_count == UINT64_C(4), "unused-tail force count differed");
        for (std::size_t atom = 0; atom < expected.force_x.size(); ++atom) {
            require_exact(shared_xy[atom], expected.force_x[atom], "unused-tail x force differed");
            require_exact(shared_xy[atom + 4U], expected.force_y[atom], "unused-tail y force differed");
            require_exact(force_z[atom], expected.force_z[atom], "unused-tail z force differed");
        }
    }
}

struct FailureState final {
    bg_direct_ewald_composite_energy_components_v1 energy{};
    bg_direct_ewald_composite_force_soa_v1 forces{};
    std::array<double, 4> force_x{{11.0, 12.0, 13.0, 14.0}};
    std::array<double, 4> force_y{{21.0, 22.0, 23.0, 24.0}};
    std::array<double, 4> force_z{{31.0, 32.0, 33.0, 34.0}};
    bg_direct_ewald_error_v1 error{};

    FailureState() {
        require_status(
            bg_direct_ewald_composite_energy_components_v1_init(
                &energy, sizeof(energy),
                BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION),
            BG_STATUS_OK,
            "failure energy initializer failed");
        double value = 101.0;
        for (double *field : std::array<double *, 12>{{
                 &energy.short_harmonic_bond_kcal_per_mol,
                 &energy.short_harmonic_angle_kcal_per_mol,
                 &energy.short_periodic_torsion_kcal_per_mol,
                 &energy.short_lennard_jones_kcal_per_mol,
                 &energy.short_coulomb_kcal_per_mol,
                 &energy.short_total_kcal_per_mol,
                 &energy.ewald_real_space_kcal_per_mol,
                 &energy.ewald_reciprocal_space_kcal_per_mol,
                 &energy.ewald_self_kcal_per_mol,
                 &energy.ewald_pair_correction_kcal_per_mol,
                 &energy.ewald_total_kcal_per_mol,
                 &energy.total_kcal_per_mol,
             }}) {
            *field = value;
            value += 1.0;
        }
        require_status(
            bg_direct_ewald_composite_force_soa_v1_init(
                &forces, sizeof(forces),
                BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION),
            BG_STATUS_OK,
            "failure force initializer failed");
        forces.atom_capacity = force_x.size();
        forces.atom_count = UINT64_C(77);
        forces.x_kcal_per_mol_angstrom = force_x.data();
        forces.y_kcal_per_mol_angstrom = force_y.data();
        forces.z_kcal_per_mol_angstrom = force_z.data();
        init_error(&error);
        error.code = BG_DIRECT_EWALD_ERROR_NON_NEUTRAL_SYSTEM;
        std::memcpy(error.detail, "stale", sizeof("stale"));
    }
};

void expect_failure_without_commit(
    const bg_context *context,
    const bg_system *system,
    const bg_forcefield *forcefield,
    const bg_direct_ewald_model_v1 *model,
    bg_status expected_status,
    bg_direct_ewald_error_code expected_code,
    const char *message,
    bool overlap_force_channels = false,
    uint64_t force_capacity = UINT64_C(4),
    bool preserve_error = false) {
    FailureState state;
    state.forces.atom_capacity = force_capacity;
    if (overlap_force_channels) {
        state.forces.y_kcal_per_mol_angstrom = state.force_x.data();
    }
    const auto energy_before = state.energy;
    const auto force_x_before = state.force_x;
    const auto force_y_before = state.force_y;
    const auto force_z_before = state.force_z;
    const auto error_before = state.error;
    const uint64_t count_before = state.forces.atom_count;
    require_status(
        bg_context_evaluate_direct_ewald_composite_v1(
            context, system, forcefield, model, &state.energy, &state.forces,
            &state.error),
        expected_status,
        message);
    require(
        std::memcmp(&state.energy, &energy_before, sizeof(state.energy)) == 0,
        "failed composite evaluation changed energy");
    require(state.force_x == force_x_before, "failed composite evaluation changed x forces");
    require(state.force_y == force_y_before, "failed composite evaluation changed y forces");
    require(state.force_z == force_z_before, "failed composite evaluation changed z forces");
    require(state.forces.atom_count == count_before, "failed composite evaluation changed force count");
    if (preserve_error) {
        require(
            std::memcmp(&state.error, &error_before, sizeof(state.error)) == 0,
            "descriptor failure changed the typed-error output");
    } else {
        require(state.error.code == expected_code, "failed composite evaluation set the wrong typed code");
        if (expected_code == BG_DIRECT_EWALD_ERROR_NONE) {
            require(state.error.detail[0] == '\0', "untyped failure retained stale typed detail");
        } else {
            require(state.error.detail[0] != '\0', "typed failure omitted detail");
        }
    }
}

enum class DescriptorAliasTarget {
    energy,
    force_descriptor,
    typed_error,
};

void expect_descriptor_alias_failure(
    const bg_context *context,
    const bg_system *system,
    const bg_forcefield *forcefield,
    const bg_direct_ewald_model_v1 *model,
    DescriptorAliasTarget target) {
    FailureState state;
    switch (target) {
        case DescriptorAliasTarget::energy:
            state.forces.x_kcal_per_mol_angstrom =
                &state.energy.short_harmonic_bond_kcal_per_mol;
            break;
        case DescriptorAliasTarget::force_descriptor:
            state.forces.x_kcal_per_mol_angstrom =
                reinterpret_cast<double *>(&state.forces.atom_capacity);
            break;
        case DescriptorAliasTarget::typed_error:
            state.forces.x_kcal_per_mol_angstrom =
                reinterpret_cast<double *>(state.error.detail);
            break;
    }
    const auto energy_before = state.energy;
    const auto forces_before = state.forces;
    const auto force_x_before = state.force_x;
    const auto force_y_before = state.force_y;
    const auto force_z_before = state.force_z;
    const auto error_before = state.error;
    require_status(
        bg_context_evaluate_direct_ewald_composite_v1(
            context, system, forcefield, model, &state.energy, &state.forces,
            &state.error),
        BG_STATUS_INVALID_ARGUMENT,
        "composite accepted a force channel aliasing an output descriptor");
    require(
        std::memcmp(&state.energy, &energy_before, sizeof(state.energy)) == 0,
        "descriptor-alias failure changed energy");
    require(
        std::memcmp(&state.forces, &forces_before, sizeof(state.forces)) == 0,
        "descriptor-alias failure changed the force descriptor");
    require(state.force_x == force_x_before, "descriptor-alias failure changed x forces");
    require(state.force_y == force_y_before, "descriptor-alias failure changed y forces");
    require(state.force_z == force_z_before, "descriptor-alias failure changed z forces");
    require(
        std::memcmp(&state.error, &error_before, sizeof(state.error)) == 0,
        "descriptor-alias failure changed the typed-error output");
}

void verify_compatibility_and_transactionality() {
    const Fixture fixture;
    const ContextPtr context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    const SystemPtr system = make_system(fixture, fixture.charge);
    const ForceFieldPtr forcefield = make_forcefield(fixture);
    const ModelPtr model = make_model(fixture, ModelVariant::matching);

    const ModelPtr no_rules = make_model(fixture, ModelVariant::no_pair_rules);
    expect_failure_without_commit(
        context.get(), system.get(), forcefield.get(), no_rules.get(),
        BG_STATUS_INVALID_ARGUMENT, BG_DIRECT_EWALD_ERROR_NONE,
        "composite accepted a pair-rule count mismatch");

    const ModelPtr lost_provenance = make_model(
        fixture, ModelVariant::scaled_zero_instead_of_exclusion);
    expect_failure_without_commit(
        context.get(), system.get(), forcefield.get(), lost_provenance.get(),
        BG_STATUS_INVALID_ARGUMENT, BG_DIRECT_EWALD_ERROR_NONE,
        "composite accepted a scaled zero in place of an exclusion");

    Fixture zero_scale_fixture = fixture;
    zero_scale_fixture.scale_coulomb[0] = 0.0;
    require(
        zero_scale_fixture.scale_lennard_jones[0] != 0.0,
        "explicit-zero provenance fixture lost its independent LJ scale");
    const SystemPtr zero_scale_system = make_system(
        zero_scale_fixture, zero_scale_fixture.charge);
    const ForceFieldPtr zero_scale_forcefield = make_forcefield(
        zero_scale_fixture);
    const ModelPtr zero_scale_model = make_model(
        zero_scale_fixture, ModelVariant::matching);
    const ContextPtr zero_scale_rust_context = make_context(
        BG_BACKEND_RUST_CPU);
    const CompositeResult zero_scale_cpp = evaluate_composite(
        context.get(), zero_scale_system.get(), zero_scale_forcefield.get(),
        zero_scale_model.get());
    const CompositeResult zero_scale_rust = evaluate_composite(
        zero_scale_rust_context.get(), zero_scale_system.get(),
        zero_scale_forcefield.get(), zero_scale_model.get());
    const auto zero_scale_cpp_energy = energy_values(zero_scale_cpp.energy);
    const auto zero_scale_rust_energy = energy_values(zero_scale_rust.energy);
    for (std::size_t index = 0; index < zero_scale_cpp_energy.size(); ++index) {
        require_near(
            zero_scale_cpp_energy[index], zero_scale_rust_energy[index],
            "matching explicit-zero scale lost C++/Rust energy parity");
    }
    for (std::size_t atom = 0; atom < zero_scale_cpp.force_x.size(); ++atom) {
        require_near(
            zero_scale_cpp.force_x[atom], zero_scale_rust.force_x[atom],
            "matching explicit-zero scale lost C++/Rust x-force parity");
        require_near(
            zero_scale_cpp.force_y[atom], zero_scale_rust.force_y[atom],
            "matching explicit-zero scale lost C++/Rust y-force parity");
        require_near(
            zero_scale_cpp.force_z[atom], zero_scale_rust.force_z[atom],
            "matching explicit-zero scale lost C++/Rust z-force parity");
    }
    const ModelPtr exclusion_instead_of_zero = make_model(
        zero_scale_fixture, ModelVariant::exclusion_instead_of_scaled_zero);
    expect_failure_without_commit(
        context.get(), zero_scale_system.get(), zero_scale_forcefield.get(),
        exclusion_instead_of_zero.get(), BG_STATUS_INVALID_ARGUMENT,
        BG_DIRECT_EWALD_ERROR_NONE,
        "composite accepted an exclusion in place of an explicit-zero scale");

    const ModelPtr different_scale = make_model(
        fixture, ModelVariant::different_coulomb_scale);
    expect_failure_without_commit(
        context.get(), system.get(), forcefield.get(), different_scale.get(),
        BG_STATUS_INVALID_ARGUMENT, BG_DIRECT_EWALD_ERROR_NONE,
        "composite accepted a Coulomb-scale mismatch");

    const ModelPtr different_cell = make_model(
        fixture, ModelVariant::different_cell);
    expect_failure_without_commit(
        context.get(), system.get(), forcefield.get(), different_cell.get(),
        BG_STATUS_INVALID_ARGUMENT, BG_DIRECT_EWALD_ERROR_NONE,
        "composite accepted different force-field/model cell bits");

    const ModelPtr different_count = make_model(
        fixture, ModelVariant::different_atom_count);
    expect_failure_without_commit(
        context.get(), system.get(), forcefield.get(), different_count.get(),
        BG_STATUS_INVALID_ARGUMENT, BG_DIRECT_EWALD_ERROR_NONE,
        "composite accepted a model atom-count mismatch");

    Fixture nonperiodic_fixture = fixture;
    nonperiodic_fixture.periodic_axes_mask = UINT32_C(0);
    const ForceFieldPtr nonperiodic = make_forcefield(nonperiodic_fixture);
    expect_failure_without_commit(
        context.get(), system.get(), nonperiodic.get(), model.get(),
        BG_STATUS_INVALID_ARGUMENT, BG_DIRECT_EWALD_ERROR_NONE,
        "composite accepted a nonperiodic force field");

    expect_failure_without_commit(
        context.get(), system.get(), forcefield.get(), model.get(),
        BG_STATUS_BUFFER_TOO_SMALL, BG_DIRECT_EWALD_ERROR_NONE,
        "composite accepted a short force buffer", false, UINT64_C(3), true);
    expect_failure_without_commit(
        context.get(), system.get(), forcefield.get(), model.get(),
        BG_STATUS_INVALID_ARGUMENT, BG_DIRECT_EWALD_ERROR_NONE,
        "composite accepted overlapping force channels", true, UINT64_C(4),
        true);
    for (const DescriptorAliasTarget target : {
             DescriptorAliasTarget::energy,
             DescriptorAliasTarget::force_descriptor,
             DescriptorAliasTarget::typed_error,
         }) {
        expect_descriptor_alias_failure(
            context.get(), system.get(), forcefield.get(), model.get(), target);
    }
    expect_descriptor_alias_failure(
        context.get(), system.get(), forcefield.get(), nullptr,
        DescriptorAliasTarget::typed_error);
    expect_failure_without_commit(
        context.get(), system.get(), forcefield.get(), nullptr,
        BG_STATUS_INVALID_ARGUMENT, BG_DIRECT_EWALD_ERROR_NONE,
        "composite accepted a null model");

    {
        FailureState state;
        state.forces.x_kcal_per_mol_angstrom = system->position_x.data();
        const bg_system system_before = *system;
        const auto energy_before = state.energy;
        const auto forces_before = state.forces;
        const auto force_y_before = state.force_y;
        const auto force_z_before = state.force_z;
        const auto error_before = state.error;
        require_status(
            bg_context_evaluate_direct_ewald_composite_v1(
                context.get(), system.get(), forcefield.get(), model.get(),
                &state.energy, &state.forces, &state.error),
            BG_STATUS_INVALID_ARGUMENT,
            "composite accepted a force channel aliasing the caller system");
        require(
            std::memcmp(&state.energy, &energy_before, sizeof(state.energy)) ==
                0,
            "system-alias failure changed energy");
        require(
            std::memcmp(
                &state.forces, &forces_before, sizeof(state.forces)) == 0,
            "system-alias failure changed the force descriptor");
        require(state.force_y == force_y_before, "system-alias failure changed y forces");
        require(state.force_z == force_z_before, "system-alias failure changed z forces");
        require(
            std::memcmp(&state.error, &error_before, sizeof(state.error)) == 0,
            "system-alias failure changed the typed-error output");
        require_system_exact(
            *system, system_before,
            "system-alias failure mutated the caller system");
    }

    auto nonneutral_charge = fixture.charge;
    nonneutral_charge[3] = 0.31;
    const SystemPtr nonneutral = make_system(fixture, nonneutral_charge);
    expect_failure_without_commit(
        context.get(), nonneutral.get(), forcefield.get(), model.get(),
        BG_STATUS_NUMERICAL_ERROR,
        BG_DIRECT_EWALD_ERROR_NON_NEUTRAL_SYSTEM,
        "composite accepted a non-neutral system");

    Fixture short_failure_fixture = fixture;
    short_failure_fixture.x[2] = short_failure_fixture.x[0];
    short_failure_fixture.y[2] = short_failure_fixture.y[0];
    short_failure_fixture.z[2] = short_failure_fixture.z[0];
    const SystemPtr short_failure = make_system(
        short_failure_fixture, short_failure_fixture.charge);
    const ContextPtr rust_context = make_context(BG_BACKEND_RUST_CPU);
    for (const bg_context *failure_context :
         {context.get(), rust_context.get()}) {
        expect_failure_without_commit(
            failure_context, short_failure.get(), forcefield.get(), model.get(),
            BG_STATUS_NUMERICAL_ERROR, BG_DIRECT_EWALD_ERROR_NONE,
            "short-range parent failure changed outputs or typed error");
    }
}

void verify_hip_fails_closed() {
    const Fixture fixture;
    const SystemPtr system = make_system(fixture, fixture.charge);
    const ForceFieldPtr forcefield = make_forcefield(fixture);
    const ModelPtr model = make_model(fixture, ModelVariant::matching);
    for (const bg_backend backend :
         {BG_BACKEND_HIP_SAFE, BG_BACKEND_HIP_FAST}) {
        bg_context fake_context{};
        fake_context.backend = backend;
        fake_context.unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        expect_failure_without_commit(
            &fake_context, system.get(), forcefield.get(), model.get(),
            BG_STATUS_UNSUPPORTED_BACKEND, BG_DIRECT_EWALD_ERROR_NONE,
            "composite HIP lane did not fail closed");
    }
}

}  // namespace

int main() {
    verify_abi_and_initializers();
    verify_parent_composition_and_cpu_parity();
    verify_central_finite_difference();
    verify_unused_capacity_overlap_is_allowed();
    verify_compatibility_and_transactionality();
    verify_hip_fails_closed();
    return 0;
}
