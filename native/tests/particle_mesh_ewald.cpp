#define BG_DISABLE_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#define BG_DISABLE_DIRECT_EWALD_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#define BG_DISABLE_PARTICLE_MESH_RECIPROCAL_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#define BG_DISABLE_PARTICLE_MESH_EWALD_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#include "betelgeuze/particle_mesh_ewald.h"

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
#include <utility>
#include <vector>

namespace {

[[noreturn]] void fail_test(const char *message) {
    std::fprintf(stderr, "particle-mesh Ewald test failure: %s\n", message);
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
            "particle-mesh Ewald test failure: %s "
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

bool close(double observed, double expected, double tolerance = 5.0e-12) {
    const double scale = 1.0 + std::max(std::abs(observed), std::abs(expected));
    return std::isfinite(observed) && std::isfinite(expected) &&
           std::abs(observed - expected) <= tolerance * scale;
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

struct DirectModelDeleter final {
    void operator()(bg_direct_ewald_model_v1 *value) const noexcept {
        bg_direct_ewald_model_v1_destroy(value);
    }
};

struct ReciprocalModelDeleter final {
    void operator()(bg_particle_mesh_reciprocal_model_v1 *value) const noexcept {
        bg_particle_mesh_reciprocal_model_v1_destroy(value);
    }
};

using ContextPtr = std::unique_ptr<bg_context, ContextDeleter>;
using SystemPtr = std::unique_ptr<bg_system, SystemDeleter>;
using DirectModelPtr =
    std::unique_ptr<bg_direct_ewald_model_v1, DirectModelDeleter>;
using ReciprocalModelPtr = std::unique_ptr<
    bg_particle_mesh_reciprocal_model_v1, ReciprocalModelDeleter>;

struct Fixture final {
    std::array<double, 4> x{{1.25, 5.1, 10.2, 15.4}};
    std::array<double, 4> y{{2.5, 3.2, 12.3, 17.1}};
    std::array<double, 4> z{{3.75, 8.4, 7.7, 19.3}};
    std::array<double, 4> mass{{1.0, 1.0, 1.0, 1.0}};
    std::array<double, 4> charge{{
        0.7, -0.4, -0.6, 0.30000000000000004}};
    std::array<std::uint64_t, 1> exclusion_i{{0U}};
    std::array<std::uint64_t, 1> exclusion_j{{1U}};
    std::array<std::uint64_t, 1> scale_i{{2U}};
    std::array<std::uint64_t, 1> scale_j{{3U}};
    std::array<double, 1> scales{{0.5}};
};

struct Result final {
    bg_particle_mesh_ewald_energy_components_v1 energy{};
    std::vector<double> force_x;
    std::vector<double> force_y;
    std::vector<double> force_z;
};

void init_error(bg_direct_ewald_error_v1 *error) {
    require_status(
        bg_direct_ewald_error_v1_init(
            error, sizeof(*error), BG_DIRECT_EWALD_ABI_VERSION),
        BG_STATUS_OK, "direct typed-error initializer failed");
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
    const std::array<double, 4> &x,
    const std::array<double, 4> &y,
    const std::array<double, 4> &z,
    const std::array<double, 4> &mass,
    const std::array<double, 4> &charge) {
    bg_particle_soa particles{};
    require_status(
        bg_particle_soa_init(
            &particles, sizeof(particles), BG_ABI_VERSION),
        BG_STATUS_OK, "particle initializer failed");
    particles.particle_count = x.size();
    particles.position_x_angstrom = x.data();
    particles.position_y_angstrom = y.data();
    particles.position_z_angstrom = z.data();
    particles.mass_dalton = mass.data();
    particles.charge_elementary = charge.data();
    bg_system *raw = nullptr;
    require_status(
        bg_system_create(&particles, &raw), BG_STATUS_OK,
        "system creation failed");
    require(raw != nullptr, "system creation returned null");
    return SystemPtr(raw);
}

SystemPtr make_system(const Fixture &fixture) {
    return make_system(
        fixture.x, fixture.y, fixture.z, fixture.mass, fixture.charge);
}

DirectModelPtr make_direct_model(
    const Fixture &fixture,
    std::int32_t reciprocal_bound = 5,
    bool with_pair_rules = true,
    std::uint64_t atom_count = 4U,
    bool include_exclusion = true,
    bool include_scale = true) {
    bg_direct_ewald_parameters_v1 parameters{};
    require_status(
        bg_direct_ewald_parameters_v1_init(
            &parameters, sizeof(parameters), BG_DIRECT_EWALD_ABI_VERSION),
        BG_STATUS_OK, "direct-model parameter initializer failed");
    parameters.atom_count = atom_count;
    parameters.cell_lengths_angstrom[0] = 18.0;
    parameters.cell_lengths_angstrom[1] = 20.0;
    parameters.cell_lengths_angstrom[2] = 22.0;
    parameters.alpha_per_angstrom = 0.31;
    parameters.real_space_cutoff_angstrom = 8.9;
    parameters.reciprocal_max_indices[0] = reciprocal_bound;
    parameters.reciprocal_max_indices[1] = reciprocal_bound;
    parameters.reciprocal_max_indices[2] = reciprocal_bound;
    parameters.dielectric = 1.0;
    parameters.minimum_pair_distance_angstrom = 1.0e-8;
    if (with_pair_rules && include_exclusion) {
        parameters.exclusion_count = fixture.exclusion_i.size();
        parameters.exclusion_atom_i = fixture.exclusion_i.data();
        parameters.exclusion_atom_j = fixture.exclusion_j.data();
    }
    if (with_pair_rules && include_scale) {
        parameters.pair_scale_count = fixture.scale_i.size();
        parameters.pair_scale_atom_i = fixture.scale_i.data();
        parameters.pair_scale_atom_j = fixture.scale_j.data();
        parameters.pair_scale_coulomb = fixture.scales.data();
    }
    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    bg_direct_ewald_model_v1 *raw = nullptr;
    require_status(
        bg_direct_ewald_model_v1_create(&parameters, &raw, &error),
        BG_STATUS_OK, "direct model creation failed");
    require(raw != nullptr, "direct model creation returned null");
    require(error.code == BG_DIRECT_EWALD_ERROR_NONE,
            "direct model creation set typed error");
    return DirectModelPtr(raw);
}

enum class ReciprocalVariant {
    matching,
    different_cell,
    different_alpha,
    different_dielectric,
    different_atom_count,
};

ReciprocalModelPtr make_reciprocal_model(
    ReciprocalVariant variant = ReciprocalVariant::matching,
    std::uint32_t mesh_dimension = 16U) {
    bg_particle_mesh_reciprocal_parameters_v1 parameters{};
    require_status(
        bg_particle_mesh_reciprocal_parameters_v1_init(
            &parameters, sizeof(parameters),
            BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION),
        BG_STATUS_OK, "reciprocal-model parameter initializer failed");
    parameters.atom_count =
        variant == ReciprocalVariant::different_atom_count ? 3U : 4U;
    parameters.cell_lengths_angstrom[0] = 18.0;
    parameters.cell_lengths_angstrom[1] = 20.0;
    parameters.cell_lengths_angstrom[2] = 22.0;
    parameters.alpha_per_angstrom = 0.31;
    parameters.mesh_dimensions[0] = mesh_dimension;
    parameters.mesh_dimensions[1] = mesh_dimension;
    parameters.mesh_dimensions[2] = mesh_dimension;
    parameters.dielectric = 1.0;
    if (variant == ReciprocalVariant::different_cell) {
        parameters.cell_lengths_angstrom[0] =
            std::nextafter(18.0, std::numeric_limits<double>::infinity());
    } else if (variant == ReciprocalVariant::different_alpha) {
        parameters.alpha_per_angstrom = std::nextafter(
            0.31, std::numeric_limits<double>::infinity());
    } else if (variant == ReciprocalVariant::different_dielectric) {
        parameters.dielectric = std::nextafter(
            1.0, std::numeric_limits<double>::infinity());
    }
    bg_particle_mesh_reciprocal_error_v1 error{};
    require_status(
        bg_particle_mesh_reciprocal_error_v1_init(
            &error, sizeof(error),
            BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION),
        BG_STATUS_OK, "reciprocal typed-error initializer failed");
    bg_particle_mesh_reciprocal_model_v1 *raw = nullptr;
    require_status(
        bg_particle_mesh_reciprocal_model_v1_create(
            &parameters, &raw, &error),
        BG_STATUS_OK, "reciprocal model creation failed");
    require(raw != nullptr, "reciprocal model creation returned null");
    require(error.code == BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONE,
            "reciprocal model creation set typed error");
    return ReciprocalModelPtr(raw);
}

Result evaluate(
    const bg_context *context,
    const bg_system *system,
    const bg_direct_ewald_model_v1 *direct_model,
    const bg_particle_mesh_reciprocal_model_v1 *reciprocal_model,
    bool compute_forces = true) {
    Result result;
    require_status(
        bg_particle_mesh_ewald_energy_components_v1_init(
            &result.energy, sizeof(result.energy),
            BG_PARTICLE_MESH_EWALD_ABI_VERSION),
        BG_STATUS_OK, "PME energy initializer failed");
    bg_particle_mesh_ewald_force_soa_v1 force_descriptor{};
    bg_particle_mesh_ewald_force_soa_v1 *force_pointer = nullptr;
    if (compute_forces) {
        result.force_x.resize(4U);
        result.force_y.resize(4U);
        result.force_z.resize(4U);
        require_status(
            bg_particle_mesh_ewald_force_soa_v1_init(
                &force_descriptor, sizeof(force_descriptor),
                BG_PARTICLE_MESH_EWALD_ABI_VERSION),
            BG_STATUS_OK, "PME force initializer failed");
        force_descriptor.atom_capacity = 4U;
        force_descriptor.x_kcal_per_mol_angstrom = result.force_x.data();
        force_descriptor.y_kcal_per_mol_angstrom = result.force_y.data();
        force_descriptor.z_kcal_per_mol_angstrom = result.force_z.data();
        force_pointer = &force_descriptor;
    }
    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    require_status(
        bg_context_evaluate_particle_mesh_ewald_v1(
            context, system, direct_model, reciprocal_model, &result.energy,
            force_pointer, &error),
        BG_STATUS_OK, "PME evaluation failed");
    require(error.code == BG_DIRECT_EWALD_ERROR_NONE,
            "PME success set a typed error");
    require(error.detail[0] == '\0', "PME success left typed-error detail");
    if (compute_forces) {
        require(force_descriptor.atom_count == 4U,
                "PME success did not commit force atom count");
    }
    return result;
}

struct DirectParentResult final {
    bg_direct_ewald_energy_components_v1 energy{};
    std::array<double, 4> force_x{};
    std::array<double, 4> force_y{};
    std::array<double, 4> force_z{};
};

DirectParentResult evaluate_direct_parent(
    const bg_context *context,
    const bg_system *system,
    const bg_direct_ewald_model_v1 *model) {
    DirectParentResult result;
    require_status(
        bg_direct_ewald_energy_components_v1_init(
            &result.energy, sizeof(result.energy),
            BG_DIRECT_EWALD_ABI_VERSION),
        BG_STATUS_OK, "direct-parent energy initializer failed");
    bg_direct_ewald_force_soa_v1 forces{};
    require_status(
        bg_direct_ewald_force_soa_v1_init(
            &forces, sizeof(forces), BG_DIRECT_EWALD_ABI_VERSION),
        BG_STATUS_OK, "direct-parent force initializer failed");
    forces.atom_capacity = result.force_x.size();
    forces.x_kcal_per_mol_angstrom = result.force_x.data();
    forces.y_kcal_per_mol_angstrom = result.force_y.data();
    forces.z_kcal_per_mol_angstrom = result.force_z.data();
    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    require_status(
        bg_context_evaluate_direct_ewald_v1(
            context, system, model, &result.energy, &forces, &error),
        BG_STATUS_OK, "direct-parent evaluation failed");
    require(forces.atom_count == result.force_x.size(),
            "direct parent returned wrong force count");
    require(error.code == BG_DIRECT_EWALD_ERROR_NONE &&
                error.detail[0] == '\0',
            "direct parent returned error state on success");
    return result;
}

struct ReciprocalParentResult final {
    bg_particle_mesh_reciprocal_energy_v1 energy{};
    std::array<double, 4> force_x{};
    std::array<double, 4> force_y{};
    std::array<double, 4> force_z{};
};

ReciprocalParentResult evaluate_reciprocal_parent(
    const bg_context *context,
    const bg_system *system,
    const bg_particle_mesh_reciprocal_model_v1 *model) {
    ReciprocalParentResult result;
    require_status(
        bg_particle_mesh_reciprocal_energy_v1_init(
            &result.energy, sizeof(result.energy),
            BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION),
        BG_STATUS_OK, "reciprocal-parent energy initializer failed");
    bg_particle_mesh_reciprocal_force_soa_v1 forces{};
    require_status(
        bg_particle_mesh_reciprocal_force_soa_v1_init(
            &forces, sizeof(forces),
            BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION),
        BG_STATUS_OK, "reciprocal-parent force initializer failed");
    forces.atom_capacity = result.force_x.size();
    forces.x_kcal_per_mol_angstrom = result.force_x.data();
    forces.y_kcal_per_mol_angstrom = result.force_y.data();
    forces.z_kcal_per_mol_angstrom = result.force_z.data();
    bg_particle_mesh_reciprocal_error_v1 error{};
    require_status(
        bg_particle_mesh_reciprocal_error_v1_init(
            &error, sizeof(error),
            BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION),
        BG_STATUS_OK, "reciprocal-parent error initializer failed");
    require_status(
        bg_context_evaluate_particle_mesh_reciprocal_v1(
            context, system, model, &result.energy, &forces, &error),
        BG_STATUS_OK, "reciprocal-parent evaluation failed");
    require(forces.atom_count == result.force_x.size(),
            "reciprocal parent returned wrong force count");
    require(error.code == BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONE &&
                error.detail[0] == '\0',
            "reciprocal parent returned error state on success");
    return result;
}

std::array<double, 5> energy_values(const Result &result) {
    return {{
        result.energy.real_space_kcal_per_mol,
        result.energy.reciprocal_space_kcal_per_mol,
        result.energy.self_kcal_per_mol,
        result.energy.pair_correction_kcal_per_mol,
        result.energy.total_kcal_per_mol,
    }};
}

void require_exact_result(
    const Result &observed,
    const Result &expected,
    const char *message) {
    const auto observed_energy = energy_values(observed);
    const auto expected_energy = energy_values(expected);
    for (std::size_t index = 0U; index < observed_energy.size(); ++index) {
        require(bits(observed_energy[index]) == bits(expected_energy[index]),
                message);
    }
    require(observed.force_x.size() == expected.force_x.size(), message);
    for (std::size_t atom = 0U; atom < observed.force_x.size(); ++atom) {
        require(bits(observed.force_x[atom]) == bits(expected.force_x[atom]),
                message);
        require(bits(observed.force_y[atom]) == bits(expected.force_y[atom]),
                message);
        require(bits(observed.force_z[atom]) == bits(expected.force_z[atom]),
                message);
    }
}

void require_near_result(
    const Result &observed,
    const Result &expected,
    const char *message) {
    const auto observed_energy = energy_values(observed);
    const auto expected_energy = energy_values(expected);
    for (std::size_t index = 0U; index < observed_energy.size(); ++index) {
        require(close(observed_energy[index], expected_energy[index]), message);
    }
    require(observed.force_x.size() == expected.force_x.size(), message);
    for (std::size_t atom = 0U; atom < observed.force_x.size(); ++atom) {
        require(close(observed.force_x[atom], expected.force_x[atom]), message);
        require(close(observed.force_y[atom], expected.force_y[atom]), message);
        require(close(observed.force_z[atom], expected.force_z[atom]), message);
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
            BG_PARTICLE_MESH_EWALD_ABI_VERSION),
        BG_STATUS_ABI_MISMATCH, "initializer accepted a short descriptor");
    require(std::memcmp(&descriptor, before.data(), sizeof(descriptor)) == 0,
            "short initializer call changed its descriptor");
    require_status(
        initializer(&descriptor, sizeof(descriptor), UINT32_C(99)),
        BG_STATUS_ABI_MISMATCH, "initializer accepted a foreign version");
    require(std::memcmp(&descriptor, before.data(), sizeof(descriptor)) == 0,
            "version-mismatch initializer changed its descriptor");
    require_status(
        initializer(
            &descriptor, sizeof(descriptor),
            BG_PARTICLE_MESH_EWALD_ABI_VERSION),
        BG_STATUS_OK, "valid initializer failed");
}

void verify_abi_layout_profile_and_initializers() {
    static_assert(sizeof(bg_particle_mesh_ewald_energy_components_v1) == 88U);
    static_assert(sizeof(bg_particle_mesh_ewald_force_soa_v1) == 88U);
    static_assert(offsetof(
                      bg_particle_mesh_ewald_energy_components_v1,
                      real_space_kcal_per_mol) == 16U);
    static_assert(offsetof(
                      bg_particle_mesh_ewald_energy_components_v1,
                      total_kcal_per_mol) == 48U);
    static_assert(offsetof(
                      bg_particle_mesh_ewald_force_soa_v1,
                      x_kcal_per_mol_angstrom) == 32U);
    require(bg_particle_mesh_ewald_abi_version() == 1U,
            "wrong PME ABI version");
    require(bg_particle_mesh_ewald_abi_version_major() == 1U,
            "wrong PME ABI major");
    require(bg_particle_mesh_ewald_abi_version_minor() == 0U,
            "wrong PME ABI minor");
    require(std::string(bg_particle_mesh_ewald_abi_version_string()) ==
                "1.0.0",
            "wrong PME ABI version string");
    require(std::string(bg_particle_mesh_ewald_v1_profile_id()) ==
                "betelgeuze.native_particle_mesh_ewald/1.0.0",
            "wrong PME profile id");

    verify_initializer_transactionality<
        bg_particle_mesh_ewald_energy_components_v1>(
        bg_particle_mesh_ewald_energy_components_v1_init);
    verify_initializer_transactionality<bg_particle_mesh_ewald_force_soa_v1>(
        bg_particle_mesh_ewald_force_soa_v1_init);
    require_status(
        bg_particle_mesh_ewald_energy_components_v1_init(
            nullptr, sizeof(bg_particle_mesh_ewald_energy_components_v1),
            BG_PARTICLE_MESH_EWALD_ABI_VERSION),
        BG_STATUS_INVALID_ARGUMENT, "null PME energy initializer succeeded");
}

void verify_cpu_lanes_repeat_parity_and_energy_only() {
    constexpr std::uint64_t kExpectedTotal = UINT64_C(0xc0186145396def20);
    Fixture fixture;
    const SystemPtr system = make_system(fixture);
    const DirectModelPtr direct_model = make_direct_model(fixture);
    const ReciprocalModelPtr reciprocal_model = make_reciprocal_model();
    std::array<Result, 2> lane_results;
    const std::array<bg_backend, 2> lanes{{
        BG_BACKEND_CPP_CPU_REFERENCE, BG_BACKEND_RUST_CPU}};
    for (std::size_t lane = 0U; lane < lanes.size(); ++lane) {
        const ContextPtr context = make_context(lanes[lane]);
        lane_results[lane] = evaluate(
            context.get(), system.get(), direct_model.get(),
            reciprocal_model.get());
        const Result repeated = evaluate(
            context.get(), system.get(), direct_model.get(),
            reciprocal_model.get());
        require_exact_result(
            repeated, lane_results[lane],
            "same-lane repeated PME evaluation changed bits");
        const Result energy_only = evaluate(
            context.get(), system.get(), direct_model.get(),
            reciprocal_model.get(), false);
        const auto full_energy = energy_values(lane_results[lane]);
        const auto only_energy = energy_values(energy_only);
        for (std::size_t index = 0U; index < full_energy.size(); ++index) {
            require(bits(full_energy[index]) == bits(only_energy[index]),
                    "energy-only PME path changed energy bits");
        }
        require(energy_only.force_x.empty(),
                "energy-only PME path returned forces");
    }
    require(bits(lane_results[1].energy.total_kcal_per_mol) ==
                kExpectedTotal,
            "Rust PME frozen total bits changed");
    require(close(
                lane_results[0].energy.total_kcal_per_mol,
                from_bits(kExpectedTotal)),
            "C++ PME total diverged from the frozen fixture");
    require_near_result(
        lane_results[0], lane_results[1],
        "C++ and Rust PME CPU lanes diverged");
}

void verify_exact_parent_composition() {
    Fixture fixture;
    const SystemPtr system = make_system(fixture);
    const DirectModelPtr direct_model = make_direct_model(fixture);
    const ReciprocalModelPtr reciprocal_model = make_reciprocal_model();
    for (const bg_backend lane :
         {BG_BACKEND_CPP_CPU_REFERENCE, BG_BACKEND_RUST_CPU}) {
        const ContextPtr context = make_context(lane);
        const std::array<std::int32_t, 3> configured_bounds =
            direct_model->reciprocal_max_indices;
        direct_model->reciprocal_max_indices = {{0, 0, 0}};
        const DirectParentResult direct = evaluate_direct_parent(
            context.get(), system.get(), direct_model.get());
        direct_model->reciprocal_max_indices = configured_bounds;
        const ReciprocalParentResult reciprocal = evaluate_reciprocal_parent(
            context.get(), system.get(), reciprocal_model.get());
        const Result composite = evaluate(
            context.get(), system.get(), direct_model.get(),
            reciprocal_model.get());

        require(bits(direct.energy.reciprocal_space_kcal_per_mol) == 0U,
                "zero-bound direct parent returned reciprocal energy");
        require(bits(composite.energy.real_space_kcal_per_mol) ==
                    bits(direct.energy.real_space_kcal_per_mol),
                "PME real component differs from direct parent");
        require(bits(composite.energy.reciprocal_space_kcal_per_mol) ==
                    bits(reciprocal.energy.reciprocal_space_kcal_per_mol),
                "PME reciprocal component differs from reciprocal parent");
        require(bits(composite.energy.self_kcal_per_mol) ==
                    bits(direct.energy.self_kcal_per_mol),
                "PME self component differs from direct parent");
        require(bits(composite.energy.pair_correction_kcal_per_mol) ==
                    bits(direct.energy.pair_correction_kcal_per_mol),
                "PME pair component differs from direct parent");
        const double expected_total =
            ((direct.energy.real_space_kcal_per_mol +
              reciprocal.energy.reciprocal_space_kcal_per_mol) +
             direct.energy.self_kcal_per_mol) +
            direct.energy.pair_correction_kcal_per_mol;
        require(bits(composite.energy.total_kcal_per_mol) ==
                    bits(expected_total),
                "PME total did not use frozen parent component order");
        for (std::size_t atom = 0U; atom < fixture.x.size(); ++atom) {
            const double expected_x =
                direct.force_x[atom] + reciprocal.force_x[atom];
            const double expected_y =
                direct.force_y[atom] + reciprocal.force_y[atom];
            const double expected_z =
                direct.force_z[atom] + reciprocal.force_z[atom];
            require(bits(composite.force_x[atom]) == bits(expected_x),
                    "PME x force differs from parent sum");
            require(bits(composite.force_y[atom]) == bits(expected_y),
                    "PME y force differs from parent sum");
            require(bits(composite.force_z[atom]) == bits(expected_z),
                    "PME z force differs from parent sum");
        }
    }
}

void verify_direct_reciprocal_bounds_are_ignored() {
    Fixture fixture;
    const SystemPtr system = make_system(fixture);
    const DirectModelPtr low_bound = make_direct_model(fixture, 1);
    const DirectModelPtr high_bound = make_direct_model(fixture, 32);
    const ReciprocalModelPtr reciprocal_model = make_reciprocal_model();
    for (const bg_backend lane :
         {BG_BACKEND_CPP_CPU_REFERENCE, BG_BACKEND_RUST_CPU}) {
        const ContextPtr context = make_context(lane);
        const Result low = evaluate(
            context.get(), system.get(), low_bound.get(),
            reciprocal_model.get());
        const Result high = evaluate(
            context.get(), system.get(), high_bound.get(),
            reciprocal_model.get());
        require_exact_result(
            high, low,
            "direct reciprocal bound influenced particle-mesh Ewald");
    }
}

void verify_mesh_8_16_32_approaches_direct_total() {
    Fixture fixture;
    const SystemPtr system = make_system(fixture);
    const DirectModelPtr direct_model = make_direct_model(fixture, 9);
    const std::array<std::uint32_t, 3> meshes{{8U, 16U, 32U}};
    for (const bg_backend lane :
         {BG_BACKEND_CPP_CPU_REFERENCE, BG_BACKEND_RUST_CPU}) {
        const ContextPtr context = make_context(lane);
        const DirectParentResult direct = evaluate_direct_parent(
            context.get(), system.get(), direct_model.get());
        std::array<double, 3> absolute_errors{};
        for (std::size_t index = 0U; index < meshes.size(); ++index) {
            const ReciprocalModelPtr reciprocal_model =
                make_reciprocal_model(
                    ReciprocalVariant::matching, meshes[index]);
            const Result composite = evaluate(
                context.get(), system.get(), direct_model.get(),
                reciprocal_model.get(), false);
            absolute_errors[index] = std::abs(
                composite.energy.total_kcal_per_mol -
                direct.energy.total_kcal_per_mol);
        }
        require(absolute_errors[1] < absolute_errors[0],
                "mesh 16 PME total did not approach direct Ewald from mesh 8");
        require(absolute_errors[2] < absolute_errors[1],
                "mesh 32 PME total did not approach direct Ewald from mesh 16");
        require(absolute_errors[2] < 2.0e-3,
                "mesh 32 PME total remained too far from direct Ewald");
    }
}

struct OutputState final {
    bg_particle_mesh_ewald_energy_components_v1 energy{};
    bg_particle_mesh_ewald_force_soa_v1 forces{};
    std::array<double, 4> force_x{{91.0, 92.0, 93.0, 94.0}};
    std::array<double, 4> force_y{{81.0, 82.0, 83.0, 84.0}};
    std::array<double, 4> force_z{{71.0, 72.0, 73.0, 74.0}};
    bg_direct_ewald_error_v1 error{};

    OutputState() {
        require_status(
            bg_particle_mesh_ewald_energy_components_v1_init(
                &energy, sizeof(energy),
                BG_PARTICLE_MESH_EWALD_ABI_VERSION),
            BG_STATUS_OK, "output-state energy initializer failed");
        require_status(
            bg_particle_mesh_ewald_force_soa_v1_init(
                &forces, sizeof(forces),
                BG_PARTICLE_MESH_EWALD_ABI_VERSION),
            BG_STATUS_OK, "output-state force initializer failed");
        energy.real_space_kcal_per_mol = 901.0;
        energy.reciprocal_space_kcal_per_mol = 902.0;
        energy.self_kcal_per_mol = 903.0;
        energy.pair_correction_kcal_per_mol = 904.0;
        energy.total_kcal_per_mol = 905.0;
        forces.atom_capacity = 4U;
        forces.atom_count = 77U;
        forces.x_kcal_per_mol_angstrom = force_x.data();
        forces.y_kcal_per_mol_angstrom = force_y.data();
        forces.z_kcal_per_mol_angstrom = force_z.data();
        init_error(&error);
        error.code = BG_DIRECT_EWALD_ERROR_INVALID_PARAMETER;
        std::strcpy(error.detail, "stale");
    }
};

struct OutputSnapshot final {
    bg_particle_mesh_ewald_energy_components_v1 energy{};
    bg_particle_mesh_ewald_force_soa_v1 forces{};
    std::array<double, 4> force_x{};
    std::array<double, 4> force_y{};
    std::array<double, 4> force_z{};
};

OutputSnapshot snapshot(const OutputState &state) {
    return {
        state.energy, state.forces, state.force_x, state.force_y,
        state.force_z};
}

void require_outputs_unchanged(
    const OutputState &state,
    const OutputSnapshot &before,
    const char *message) {
    require(std::memcmp(&state.energy, &before.energy, sizeof(state.energy)) == 0,
            message);
    require(std::memcmp(&state.forces, &before.forces, sizeof(state.forces)) == 0,
            message);
    require(state.force_x == before.force_x, message);
    require(state.force_y == before.force_y, message);
    require(state.force_z == before.force_z, message);
}

void verify_failure_transactionality_and_error_mapping() {
    Fixture fixture;
    const ContextPtr context = make_context(BG_BACKEND_RUST_CPU);
    const SystemPtr system = make_system(fixture);
    const DirectModelPtr direct_model = make_direct_model(fixture);
    const ReciprocalModelPtr reciprocal_model = make_reciprocal_model();

    OutputState state;
    const OutputSnapshot before = snapshot(state);
    system->charge[0] += 0.25;
    require_status(
        bg_context_evaluate_particle_mesh_ewald_v1(
            context.get(), system.get(), direct_model.get(),
            reciprocal_model.get(), &state.energy, &state.forces,
            &state.error),
        BG_STATUS_NUMERICAL_ERROR, "non-neutral PME input had wrong status");
    require(state.error.code == BG_DIRECT_EWALD_ERROR_NON_NEUTRAL_SYSTEM,
            "non-neutral PME input had wrong typed error");
    require_outputs_unchanged(state, before,
                              "non-neutral PME failure changed outputs");

    system->charge = std::vector<double>(
        fixture.charge.begin(), fixture.charge.end());
    system->position_z[3] = std::numeric_limits<double>::quiet_NaN();
    init_error(&state.error);
    require_status(
        bg_context_evaluate_particle_mesh_ewald_v1(
            context.get(), system.get(), direct_model.get(),
            reciprocal_model.get(), &state.energy, &state.forces,
            &state.error),
        BG_STATUS_INVALID_ARGUMENT,
        "non-finite PME coordinate had wrong status");
    require(state.error.code == BG_DIRECT_EWALD_ERROR_NONFINITE_COORDINATE,
            "non-finite PME coordinate had wrong typed error");
    require_outputs_unchanged(state, before,
                              "non-finite PME failure changed outputs");

    system->position_z[3] = fixture.z[3];
    reciprocal_model->mesh_dimensions[0] = 3U;
    init_error(&state.error);
    require_status(
        bg_context_evaluate_particle_mesh_ewald_v1(
            context.get(), system.get(), direct_model.get(),
            reciprocal_model.get(), &state.energy, &state.forces,
            &state.error),
        BG_STATUS_INVALID_ARGUMENT,
        "invalid reciprocal mesh had wrong composite status");
    require(state.error.code == BG_DIRECT_EWALD_ERROR_INVALID_PARAMETER,
            "invalid reciprocal mesh was not mapped to direct invalid parameter");
    require_outputs_unchanged(state, before,
                              "reciprocal typed failure changed outputs");
    reciprocal_model->mesh_dimensions[0] = 16U;
}

void verify_compatibility_failures() {
    Fixture fixture;
    const ContextPtr context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    const SystemPtr system = make_system(fixture);
    const DirectModelPtr direct_model = make_direct_model(fixture);
    for (const ReciprocalVariant variant : {
             ReciprocalVariant::different_cell,
             ReciprocalVariant::different_alpha,
             ReciprocalVariant::different_dielectric,
             ReciprocalVariant::different_atom_count}) {
        const ReciprocalModelPtr incompatible = make_reciprocal_model(variant);
        OutputState state;
        const OutputSnapshot before = snapshot(state);
        require_status(
            bg_context_evaluate_particle_mesh_ewald_v1(
                context.get(), system.get(), direct_model.get(),
                incompatible.get(), &state.energy, &state.forces,
                &state.error),
            BG_STATUS_INVALID_ARGUMENT,
            "incompatible PME models were accepted");
        require(state.error.code == BG_DIRECT_EWALD_ERROR_NONE,
                "compatibility failure set a typed error");
        require(state.error.detail[0] == '\0',
                "compatibility failure left typed detail");
        require_outputs_unchanged(
            state, before, "compatibility failure changed outputs");
    }

    const ReciprocalModelPtr matching = make_reciprocal_model();
    system->unit_system = static_cast<bg_unit_system>(UINT32_C(77));
    OutputState state;
    const OutputSnapshot before = snapshot(state);
    require_status(
        bg_context_evaluate_particle_mesh_ewald_v1(
            context.get(), system.get(), direct_model.get(), matching.get(),
            &state.energy, &state.forces, &state.error),
        BG_STATUS_INVALID_ARGUMENT, "unit-incompatible PME system accepted");
    require_outputs_unchanged(state, before,
                              "unit failure changed PME outputs");
}

void verify_fail_closed_requested_backends() {
    for (const bg_backend backend :
         {BG_BACKEND_AUTO, BG_BACKEND_HIP_SAFE, BG_BACKEND_HIP_FAST}) {
        bg_context context{};
        context.requested_backend = backend;
        context.backend = BG_BACKEND_RUST_CPU;
        const auto *bad_system = reinterpret_cast<const bg_system *>(
            static_cast<std::uintptr_t>(1U));
        const auto *bad_direct = reinterpret_cast<
            const bg_direct_ewald_model_v1 *>(
            static_cast<std::uintptr_t>(3U));
        const auto *bad_reciprocal = reinterpret_cast<
            const bg_particle_mesh_reciprocal_model_v1 *>(
            static_cast<std::uintptr_t>(5U));
        auto *bad_energy = reinterpret_cast<
            bg_particle_mesh_ewald_energy_components_v1 *>(
            static_cast<std::uintptr_t>(7U));
        auto *bad_forces = reinterpret_cast<
            bg_particle_mesh_ewald_force_soa_v1 *>(
            static_cast<std::uintptr_t>(9U));
        auto *bad_error = reinterpret_cast<bg_direct_ewald_error_v1 *>(
            static_cast<std::uintptr_t>(11U));
        require_status(
            bg_context_evaluate_particle_mesh_ewald_v1(
                &context, bad_system, bad_direct, bad_reciprocal, bad_energy,
                bad_forces, bad_error),
            BG_STATUS_UNSUPPORTED_BACKEND,
            "AUTO/HIP PME request did not fail before other inputs");
    }
    for (const auto &mismatch : {
             std::pair<bg_backend, bg_backend>{
                 BG_BACKEND_CPP_CPU_REFERENCE, BG_BACKEND_RUST_CPU},
             std::pair<bg_backend, bg_backend>{
                 BG_BACKEND_RUST_CPU, BG_BACKEND_CPP_CPU_REFERENCE}}) {
        bg_context context{};
        context.requested_backend = mismatch.first;
        context.backend = mismatch.second;
        const auto *bad_system = reinterpret_cast<const bg_system *>(
            static_cast<std::uintptr_t>(1U));
        const auto *bad_direct = reinterpret_cast<
            const bg_direct_ewald_model_v1 *>(
            static_cast<std::uintptr_t>(3U));
        const auto *bad_reciprocal = reinterpret_cast<
            const bg_particle_mesh_reciprocal_model_v1 *>(
            static_cast<std::uintptr_t>(5U));
        auto *bad_energy = reinterpret_cast<
            bg_particle_mesh_ewald_energy_components_v1 *>(
            static_cast<std::uintptr_t>(7U));
        auto *bad_error = reinterpret_cast<bg_direct_ewald_error_v1 *>(
            static_cast<std::uintptr_t>(11U));
        require_status(
            bg_context_evaluate_particle_mesh_ewald_v1(
                &context, bad_system, bad_direct, bad_reciprocal, bad_energy,
                nullptr, bad_error),
            BG_STATUS_ABI_MISMATCH,
            "requested/resolved PME CPU mismatch did not fail before inputs");
    }
}

void verify_descriptor_validation_and_alias_rejection() {
    Fixture fixture;
    const ContextPtr context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    const SystemPtr system = make_system(fixture);
    const DirectModelPtr direct_model = make_direct_model(fixture);
    const ReciprocalModelPtr reciprocal_model = make_reciprocal_model();

    {
        OutputState state;
        state.energy.struct_size -= 1U;
        const OutputSnapshot before = snapshot(state);
        require_status(
            bg_context_evaluate_particle_mesh_ewald_v1(
                context.get(), system.get(), direct_model.get(),
                reciprocal_model.get(), &state.energy, &state.forces,
                &state.error),
            BG_STATUS_ABI_MISMATCH,
            "short PME energy descriptor was accepted");
        require(state.error.code == BG_DIRECT_EWALD_ERROR_NONE &&
                    state.error.detail[0] == '\0',
                "energy ABI failure did not clear a valid typed error");
        require_outputs_unchanged(state, before,
                                  "energy ABI failure changed outputs");
    }
    {
        OutputState state;
        state.energy.reserved[0] = 1U;
        const OutputSnapshot before = snapshot(state);
        require_status(
            bg_context_evaluate_particle_mesh_ewald_v1(
                context.get(), system.get(), direct_model.get(),
                reciprocal_model.get(), &state.energy, &state.forces,
                &state.error),
            BG_STATUS_INVALID_ARGUMENT, "reserved PME energy field accepted");
        require_outputs_unchanged(state, before,
                                  "energy validation changed outputs");
    }
    {
        OutputState state;
        state.energy.unit_system = static_cast<bg_unit_system>(UINT32_C(77));
        const OutputSnapshot before = snapshot(state);
        require_status(
            bg_context_evaluate_particle_mesh_ewald_v1(
                context.get(), system.get(), direct_model.get(),
                reciprocal_model.get(), &state.energy, &state.forces,
                &state.error),
            BG_STATUS_INVALID_ARGUMENT, "invalid PME output units accepted");
        require_outputs_unchanged(state, before,
                                  "output-unit failure changed outputs");
    }
    {
        OutputState state;
        state.forces.reserved0 = 1U;
        const OutputSnapshot before = snapshot(state);
        require_status(
            bg_context_evaluate_particle_mesh_ewald_v1(
                context.get(), system.get(), direct_model.get(),
                reciprocal_model.get(), &state.energy, &state.forces,
                &state.error),
            BG_STATUS_INVALID_ARGUMENT, "reserved PME force field accepted");
        require_outputs_unchanged(state, before,
                                  "force validation changed outputs");
    }
    {
        OutputState state;
        state.error.reserved[0] = 1U;
        const OutputSnapshot before = snapshot(state);
        const bg_direct_ewald_error_v1 error_before = state.error;
        require_status(
            bg_context_evaluate_particle_mesh_ewald_v1(
                context.get(), system.get(), direct_model.get(),
                reciprocal_model.get(), &state.energy, &state.forces,
                &state.error),
            BG_STATUS_INVALID_ARGUMENT,
            "reserved direct typed-error field accepted by PME");
        require_outputs_unchanged(state, before,
                                  "typed-error validation changed outputs");
        require(std::memcmp(
                    &state.error, &error_before, sizeof(state.error)) == 0,
                "invalid typed-error descriptor was modified");
    }
    {
        OutputState state;
        state.forces.x_kcal_per_mol_angstrom = nullptr;
        const OutputSnapshot before = snapshot(state);
        const bg_direct_ewald_error_v1 error_before = state.error;
        require_status(
            bg_context_evaluate_particle_mesh_ewald_v1(
                context.get(), system.get(), direct_model.get(),
                reciprocal_model.get(), &state.energy, &state.forces,
                &state.error),
            BG_STATUS_INVALID_ARGUMENT, "null PME force channel accepted");
        require_outputs_unchanged(state, before,
                                  "null force-channel failure changed outputs");
        require(std::memcmp(
                    &state.error, &error_before, sizeof(state.error)) == 0,
                "overlap-stage force failure modified typed error");
    }
    {
        OutputState state;
        state.forces.atom_capacity = 3U;
        const OutputSnapshot invalid_before = snapshot(state);
        require_status(
            bg_context_evaluate_particle_mesh_ewald_v1(
                context.get(), system.get(), direct_model.get(),
                reciprocal_model.get(), &state.energy, &state.forces,
                &state.error),
            BG_STATUS_BUFFER_TOO_SMALL, "short PME force capacity accepted");
        require_outputs_unchanged(state, invalid_before,
                                  "capacity failure changed outputs");
    }
    {
        OutputState state;
        state.forces.atom_capacity = UINT64_MAX;
        const OutputSnapshot before = snapshot(state);
        require_status(
            bg_context_evaluate_particle_mesh_ewald_v1(
                context.get(), system.get(), direct_model.get(),
                reciprocal_model.get(), &state.energy, &state.forces,
                &state.error),
            BG_STATUS_CAPACITY_OVERFLOW,
            "unaddressable PME force capacity accepted");
        require_outputs_unchanged(state, before,
                                  "capacity-overflow failure changed outputs");
    }
    {
        OutputState state;
        state.forces.x_kcal_per_mol_angstrom = system->position_x.data();
        const OutputSnapshot before = snapshot(state);
        require_status(
            bg_context_evaluate_particle_mesh_ewald_v1(
                context.get(), system.get(), direct_model.get(),
                reciprocal_model.get(), &state.energy, &state.forces,
                &state.error),
            BG_STATUS_INVALID_ARGUMENT,
            "PME force channel aliasing System storage accepted");
        require_outputs_unchanged(state, before,
                                  "System-alias failure changed outputs");
    }
    {
        OutputState state;
        require(!direct_model->pair_rules.empty(),
                "fixture direct model unexpectedly has no pair rules");
        state.forces.x_kcal_per_mol_angstrom =
            reinterpret_cast<double *>(direct_model->pair_rules.data());
        const OutputSnapshot before = snapshot(state);
        require_status(
            bg_context_evaluate_particle_mesh_ewald_v1(
                context.get(), system.get(), direct_model.get(),
                reciprocal_model.get(), &state.energy, &state.forces,
                &state.error),
            BG_STATUS_INVALID_ARGUMENT,
            "PME force channel aliasing direct pair rules accepted");
        require_outputs_unchanged(state, before,
                                  "pair-rule alias failure changed outputs");
    }
    {
        OutputState state;
        state.forces.x_kcal_per_mol_angstrom =
            reinterpret_cast<double *>(&state.energy);
        const OutputSnapshot before = snapshot(state);
        require_status(
            bg_context_evaluate_particle_mesh_ewald_v1(
                context.get(), system.get(), direct_model.get(),
                reciprocal_model.get(), &state.energy, &state.forces,
                &state.error),
            BG_STATUS_INVALID_ARGUMENT,
            "PME force channel aliasing energy descriptor accepted");
        require_outputs_unchanged(state, before,
                                  "descriptor alias failure changed outputs");
    }
    {
        OutputState state;
        const OutputSnapshot before = snapshot(state);
        const bg_direct_ewald_error_v1 error_before = state.error;
        require_status(
            bg_context_evaluate_particle_mesh_ewald_v1(
                context.get(), nullptr, direct_model.get(),
                reciprocal_model.get(), &state.energy, &state.forces,
                &state.error),
            BG_STATUS_INVALID_ARGUMENT, "required-null PME system accepted");
        require(state.error.code == BG_DIRECT_EWALD_ERROR_NONE &&
                    state.error.detail[0] == '\0',
                "safe required-null PME call did not clear typed error");
        require(std::memcmp(&error_before, &state.error, sizeof(state.error)) !=
                    0,
                "safe required-null PME call did not touch typed error");
        require_outputs_unchanged(state, before,
                                  "required-null failure changed outputs");
    }
    {
        alignas(bg_direct_ewald_error_v1)
            std::array<unsigned char, sizeof(bg_direct_ewald_error_v1)> bytes{};
        auto *error = reinterpret_cast<bg_direct_ewald_error_v1 *>(bytes.data());
        init_error(error);
        error->code = BG_DIRECT_EWALD_ERROR_INVALID_PARAMETER;
        std::strcpy(error->detail, "preserve alias");
        const auto before = bytes;
        OutputState state;
        state.forces.x_kcal_per_mol_angstrom =
            reinterpret_cast<double *>(bytes.data());
        require_status(
            bg_context_evaluate_particle_mesh_ewald_v1(
                context.get(), nullptr, direct_model.get(),
                reciprocal_model.get(), &state.energy, &state.forces, error),
            BG_STATUS_INVALID_ARGUMENT,
            "required-null PME error/channel alias accepted");
        require(bytes == before,
                "unsafe required-null PME call changed aliased error storage");
    }
}

void verify_transformations_and_pair_rules() {
    Fixture fixture;
    const DirectModelPtr direct_model = make_direct_model(fixture);
    const DirectModelPtr no_rules = make_direct_model(fixture, 5, false);
    const DirectModelPtr exclusion_only =
        make_direct_model(fixture, 5, true, 4U, true, false);
    const DirectModelPtr scaled_only =
        make_direct_model(fixture, 5, true, 4U, false, true);
    const ReciprocalModelPtr reciprocal_model = make_reciprocal_model();
    const SystemPtr base_system = make_system(fixture);
    require(exclusion_only->pair_rules.size() == 1U &&
                exclusion_only->pair_rules[0].is_exclusion &&
                bits(exclusion_only->pair_rules[0].coulomb_scale) == 0U,
            "exclusion provenance was not preserved by the direct model");
    require(scaled_only->pair_rules.size() == 1U &&
                !scaled_only->pair_rules[0].is_exclusion &&
                bits(scaled_only->pair_rules[0].coulomb_scale) == bits(0.5),
            "scaled-pair provenance was not preserved by the direct model");
    for (const bg_backend lane :
         {BG_BACKEND_CPP_CPU_REFERENCE, BG_BACKEND_RUST_CPU}) {
        const ContextPtr context = make_context(lane);
        const Result base = evaluate(
            context.get(), base_system.get(), direct_model.get(),
            reciprocal_model.get());
        const Result uncorrected = evaluate(
            context.get(), base_system.get(), no_rules.get(),
            reciprocal_model.get());
        const Result excluded = evaluate(
            context.get(), base_system.get(), exclusion_only.get(),
            reciprocal_model.get());
        const Result scaled = evaluate(
            context.get(), base_system.get(), scaled_only.get(),
            reciprocal_model.get());
        require(uncorrected.energy.pair_correction_kcal_per_mol == 0.0,
                "no-rule PME model produced a pair correction");
        require(bits(base.energy.pair_correction_kcal_per_mol) !=
                    bits(uncorrected.energy.pair_correction_kcal_per_mol),
                "PME pair rules did not influence pair correction");
        require(excluded.energy.pair_correction_kcal_per_mol != 0.0,
                "PME exclusion produced no pair correction");
        require(scaled.energy.pair_correction_kcal_per_mol != 0.0,
                "PME scaled pair produced no pair correction");
        require(close(
                    base.energy.pair_correction_kcal_per_mol,
                    excluded.energy.pair_correction_kcal_per_mol +
                        scaled.energy.pair_correction_kcal_per_mol),
                "PME exclusion and scaled-pair corrections did not compose");
        for (std::size_t atom = 0U; atom < fixture.x.size(); ++atom) {
            const double expected_x =
                (excluded.force_x[atom] - uncorrected.force_x[atom]) +
                (scaled.force_x[atom] - uncorrected.force_x[atom]);
            const double expected_y =
                (excluded.force_y[atom] - uncorrected.force_y[atom]) +
                (scaled.force_y[atom] - uncorrected.force_y[atom]);
            const double expected_z =
                (excluded.force_z[atom] - uncorrected.force_z[atom]) +
                (scaled.force_z[atom] - uncorrected.force_z[atom]);
            require(close(
                        base.force_x[atom] - uncorrected.force_x[atom],
                        expected_x),
                    "PME exclusion/scaled x-force provenance did not compose");
            require(close(
                        base.force_y[atom] - uncorrected.force_y[atom],
                        expected_y),
                    "PME exclusion/scaled y-force provenance did not compose");
            require(close(
                        base.force_z[atom] - uncorrected.force_z[atom],
                        expected_z),
                    "PME exclusion/scaled z-force provenance did not compose");
        }

        Fixture translated = fixture;
        translated.x[0] += 18.0;
        translated.y[1] -= 40.0;
        translated.z[2] += 66.0;
        const SystemPtr translated_system = make_system(translated);
        const Result translated_result = evaluate(
            context.get(), translated_system.get(), direct_model.get(),
            reciprocal_model.get());
        require_near_result(
            translated_result, base,
            "periodic translations changed particle-mesh Ewald");

        Fixture inverted = fixture;
        for (double &charge : inverted.charge) {
            charge = -charge;
        }
        const SystemPtr inverted_system = make_system(inverted);
        const Result inverted_result = evaluate(
            context.get(), inverted_system.get(), direct_model.get(),
            reciprocal_model.get());
        require_near_result(
            inverted_result, base,
            "global charge inversion changed particle-mesh Ewald");

        const std::array<std::size_t, 4> order{{2U, 0U, 3U, 1U}};
        Fixture permuted = fixture;
        for (std::size_t atom = 0U; atom < order.size(); ++atom) {
            permuted.x[atom] = fixture.x[order[atom]];
            permuted.y[atom] = fixture.y[order[atom]];
            permuted.z[atom] = fixture.z[order[atom]];
            permuted.mass[atom] = fixture.mass[order[atom]];
            permuted.charge[atom] = fixture.charge[order[atom]];
        }
        permuted.exclusion_i[0] = 1U;
        permuted.exclusion_j[0] = 3U;
        permuted.scale_i[0] = 0U;
        permuted.scale_j[0] = 2U;
        const SystemPtr permuted_system = make_system(permuted);
        const DirectModelPtr permuted_direct = make_direct_model(permuted);
        const Result permuted_result = evaluate(
            context.get(), permuted_system.get(), permuted_direct.get(),
            reciprocal_model.get());
        const auto base_energy = energy_values(base);
        const auto permuted_energy = energy_values(permuted_result);
        for (std::size_t index = 0U; index < base_energy.size(); ++index) {
            require(close(base_energy[index], permuted_energy[index]),
                    "atom permutation changed PME energy");
        }
        for (std::size_t atom = 0U; atom < order.size(); ++atom) {
            require(close(permuted_result.force_x[atom],
                          base.force_x[order[atom]]),
                    "atom permutation changed PME x force");
            require(close(permuted_result.force_y[atom],
                          base.force_y[order[atom]]),
                    "atom permutation changed PME y force");
            require(close(permuted_result.force_z[atom],
                          base.force_z[order[atom]]),
                    "atom permutation changed PME z force");
        }
    }
}

void verify_all_force_finite_differences() {
    Fixture fixture;
    const DirectModelPtr direct_model = make_direct_model(fixture);
    const ReciprocalModelPtr reciprocal_model = make_reciprocal_model();
    constexpr double step = 1.0e-5;
    for (const bg_backend lane :
         {BG_BACKEND_CPP_CPU_REFERENCE, BG_BACKEND_RUST_CPU}) {
        const ContextPtr context = make_context(lane);
        const SystemPtr base_system = make_system(fixture);
        const Result analytic = evaluate(
            context.get(), base_system.get(), direct_model.get(),
            reciprocal_model.get());
        const std::array<const std::vector<double> *, 3> analytic_forces{{
            &analytic.force_x, &analytic.force_y, &analytic.force_z}};
        for (std::size_t atom = 0U; atom < fixture.x.size(); ++atom) {
            for (std::size_t axis = 0U; axis < 3U; ++axis) {
                Fixture plus = fixture;
                Fixture minus = fixture;
                std::array<double *, 3> plus_axes{{
                    plus.x.data(), plus.y.data(), plus.z.data()}};
                std::array<double *, 3> minus_axes{{
                    minus.x.data(), minus.y.data(), minus.z.data()}};
                plus_axes[axis][atom] += step;
                minus_axes[axis][atom] -= step;
                const SystemPtr plus_system = make_system(plus);
                const SystemPtr minus_system = make_system(minus);
                const Result plus_energy = evaluate(
                    context.get(), plus_system.get(), direct_model.get(),
                    reciprocal_model.get(), false);
                const Result minus_energy = evaluate(
                    context.get(), minus_system.get(), direct_model.get(),
                    reciprocal_model.get(), false);
                const double numerical_force =
                    (minus_energy.energy.total_kcal_per_mol -
                     plus_energy.energy.total_kcal_per_mol) /
                    (2.0 * step);
                const double observed = (*analytic_forces[axis])[atom];
                require(
                    close(observed, numerical_force, 2.0e-6),
                    "PME analytic force failed a central finite difference");
            }
        }
    }
}

}  // namespace

int main() {
    verify_abi_layout_profile_and_initializers();
    verify_cpu_lanes_repeat_parity_and_energy_only();
    verify_exact_parent_composition();
    verify_direct_reciprocal_bounds_are_ignored();
    verify_mesh_8_16_32_approaches_direct_total();
    verify_failure_transactionality_and_error_mapping();
    verify_compatibility_failures();
    verify_fail_closed_requested_backends();
    verify_descriptor_validation_and_alias_rejection();
    verify_transformations_and_pair_rules();
    verify_all_force_finite_differences();
    return 0;
}
