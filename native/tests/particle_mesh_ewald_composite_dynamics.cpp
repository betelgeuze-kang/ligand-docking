#define BG_DISABLE_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#define BG_DISABLE_DIRECT_EWALD_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#define BG_DISABLE_DIRECT_EWALD_COMPOSITE_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#define BG_DISABLE_PARTICLE_MESH_RECIPROCAL_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#define BG_DISABLE_PARTICLE_MESH_EWALD_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#define BG_DISABLE_PARTICLE_MESH_EWALD_COMPOSITE_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#include "betelgeuze/particle_mesh_ewald_composite_dynamics.h"
#include "betelgeuze/direct_ewald_composite.h"
#include "betelgeuze/direct_ewald_composite_dynamics.h"

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

constexpr double kAccelerationConversion = 4.184e-4;

enum class PairProvenance { exclusion, explicit_zero_scale };

[[noreturn]] void fail_test(const char *message) {
    std::fprintf(
        stderr, "particle-mesh Ewald composite dynamics test failure: %s\n",
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
            "particle-mesh Ewald composite dynamics test failure: %s "
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

void require_exact(double actual, double expected, const char *message) {
    require(bits(actual) == bits(expected), message);
}

template <typename Type, typename = void>
struct is_complete : std::false_type {};

template <typename Type>
struct is_complete<Type, std::void_t<decltype(sizeof(Type))>>
    : std::true_type {};

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

struct SimulationDeleter final {
    void operator()(bg_particle_mesh_ewald_composite_simulation_v1 *value) const noexcept {
        bg_particle_mesh_ewald_composite_simulation_v1_destroy(value);
    }
};
using SimulationPtr = std::unique_ptr<
    bg_particle_mesh_ewald_composite_simulation_v1, SimulationDeleter>;

struct LegacySimulationDeleter final {
    void operator()(bg_simulation *value) const noexcept {
        bg_simulation_destroy(value);
    }
};
using LegacySimulationPtr =
    std::unique_ptr<bg_simulation, LegacySimulationDeleter>;

struct DirectSimulationDeleter final {
    void operator()(
        bg_direct_ewald_composite_simulation_v1 *value) const noexcept {
        bg_direct_ewald_composite_simulation_v1_destroy(value);
    }
};
using DirectSimulationPtr = std::unique_ptr<
    bg_direct_ewald_composite_simulation_v1, DirectSimulationDeleter>;

struct Fixture final {
    std::array<double, 4> x{{1.25, 3.1, 5.2, 7.4}};
    std::array<double, 4> y{{2.5, 3.2, 5.3, 6.1}};
    std::array<double, 4> z{{3.75, 4.4, 4.7, 6.3}};
    std::array<double, 4> velocity_x{{0.0, 0.0, 0.0, 0.0}};
    std::array<double, 4> velocity_y{{0.0, 0.0, 0.0, 0.0}};
    std::array<double, 4> velocity_z{{0.0, 0.0, 0.0, 0.0}};
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
    particles.velocity_x_angstrom_per_femtosecond = fixture.velocity_x.data();
    particles.velocity_y_angstrom_per_femtosecond = fixture.velocity_y.data();
    particles.velocity_z_angstrom_per_femtosecond = fixture.velocity_z.data();
    particles.mass_dalton = fixture.mass.data();
    particles.charge_elementary = charge.data();
    bg_system *raw = nullptr;
    require_status(
        bg_system_create(&particles, &raw), BG_STATUS_OK,
        "system creation failed");
    require(raw != nullptr, "system creation returned null");
    return SystemPtr(raw);
}

ForceFieldPtr make_forcefield(
    const Fixture &fixture,
    PairProvenance provenance = PairProvenance::exclusion) {
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
    const std::array<std::uint64_t, 2> scale_i{{0U, 2U}};
    const std::array<std::uint64_t, 2> scale_j{{1U, 3U}};
    const std::array<double, 2> scale_lj{{0.0, fixture.scale_lennard_jones[0]}};
    const std::array<double, 2> scale_coulomb{{0.0, fixture.scale_coulomb[0]}};
    if (provenance == PairProvenance::exclusion) {
        parameters.exclusion_count = fixture.exclusion_i.size();
        parameters.exclusion_atom_i = fixture.exclusion_i.data();
        parameters.exclusion_atom_j = fixture.exclusion_j.data();
        parameters.pair_scale_count = fixture.scale_i.size();
        parameters.pair_scale_atom_i = fixture.scale_i.data();
        parameters.pair_scale_atom_j = fixture.scale_j.data();
        parameters.pair_scale_lennard_jones =
            fixture.scale_lennard_jones.data();
        parameters.pair_scale_coulomb = fixture.scale_coulomb.data();
    } else {
        parameters.pair_scale_count = scale_i.size();
        parameters.pair_scale_atom_i = scale_i.data();
        parameters.pair_scale_atom_j = scale_j.data();
        parameters.pair_scale_lennard_jones = scale_lj.data();
        parameters.pair_scale_coulomb = scale_coulomb.data();
    }
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
    std::int32_t reciprocal_bound = 5,
    PairProvenance provenance = PairProvenance::exclusion) {
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
    const std::array<std::uint64_t, 2> explicit_scale_i{{0U, 2U}};
    const std::array<std::uint64_t, 2> explicit_scale_j{{1U, 3U}};
    const std::array<double, 2> explicit_scale_coulomb{{
        0.0, fixture.scale_coulomb[0]}};
    if (with_pair_rules) {
        if (provenance == PairProvenance::exclusion) {
            parameters.exclusion_count = fixture.exclusion_i.size();
            parameters.exclusion_atom_i = fixture.exclusion_i.data();
            parameters.exclusion_atom_j = fixture.exclusion_j.data();
            parameters.pair_scale_count = fixture.scale_i.size();
            parameters.pair_scale_atom_i = fixture.scale_i.data();
            parameters.pair_scale_atom_j = fixture.scale_j.data();
            parameters.pair_scale_coulomb = fixture.scale_coulomb.data();
        } else {
            parameters.pair_scale_count = explicit_scale_i.size();
            parameters.pair_scale_atom_i = explicit_scale_i.data();
            parameters.pair_scale_atom_j = explicit_scale_j.data();
            parameters.pair_scale_coulomb = explicit_scale_coulomb.data();
        }
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


void init_report(bg_dynamics_report_v1 *report);

SimulationPtr make_simulation(
    const bg_system *system,
    const bg_forcefield *forcefield,
    const bg_direct_ewald_model_v1 *direct_model,
    const bg_particle_mesh_reciprocal_model_v1 *reciprocal_model,
    const bg_distance_constraints_v1 *constraints = nullptr,
    double timestep = 0.001) {
    bg_simulation_options_v1 options{};
    require_status(bg_simulation_options_v1_init(
        &options, sizeof(options), BG_ABI_VERSION), BG_STATUS_OK,
        "options init failed");
    options.integrator = BG_INTEGRATOR_VELOCITY_VERLET;
    options.timestep_femtoseconds = timestep;
    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    bg_particle_mesh_ewald_composite_simulation_v1 *raw = nullptr;
    require_status(bg_particle_mesh_ewald_composite_simulation_v1_create(
        system, forcefield, direct_model, reciprocal_model, constraints,
        &options, &raw, &error), BG_STATUS_OK, "simulation create failed");
    require(raw != nullptr, "simulation create returned null");
    require(error.code == BG_DIRECT_EWALD_ERROR_NONE,
            "simulation create retained typed error");
    return SimulationPtr(raw);
}

bg_dynamics_report_v1 integrate(
    const bg_context *context,
    bg_particle_mesh_ewald_composite_simulation_v1 *simulation,
    std::uint64_t steps) {
    bg_dynamics_report_v1 report{};
    init_report(&report);
    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    require_status(bg_context_integrate_particle_mesh_ewald_composite_v1(
        context, simulation, steps, &report, &error), BG_STATUS_OK,
        "integration failed");
    require(error.code == BG_DIRECT_EWALD_ERROR_NONE,
            "successful integration retained typed error");
    return report;
}

double stateless_total(
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
        BG_STATUS_OK, "stateless energy init failed");
    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    require_status(bg_context_evaluate_particle_mesh_ewald_composite_v1(
        context, system, forcefield, direct_model, reciprocal_model,
        &energy, nullptr, &error), BG_STATUS_OK,
        "stateless energy evaluation failed");
    return energy.total_kcal_per_mol;
}

void init_report(bg_dynamics_report_v1 *report) {
    require_status(bg_dynamics_report_v1_init(
        report, sizeof(*report), BG_ABI_VERSION), BG_STATUS_OK,
        "report init failed");
}

std::vector<std::uint8_t> checkpoint(
    const bg_particle_mesh_ewald_composite_simulation_v1 *simulation) {
    std::uint64_t size = 0;
    require_status(
        bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_size(
            simulation, &size), BG_STATUS_OK, "checkpoint size failed");
    std::vector<std::uint8_t> bytes(static_cast<std::size_t>(size));
    std::uint64_t written = 0;
    require_status(
        bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_write(
            simulation, bytes.data(), size, &written), BG_STATUS_OK,
        "checkpoint write failed");
    require(written == size, "checkpoint size mismatch");
    require(std::memcmp(bytes.data(), "BGPME001", 8U) == 0,
            "checkpoint magic mismatch");
    return bytes;
}

void verify_runtime_and_checkpoint_identity() {
    Fixture fixture;
    auto context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    auto system = make_system(fixture, fixture.charge);
    auto forcefield = make_forcefield(fixture);
    auto direct5 = make_direct_model(fixture, true, 5);
    auto direct9 = make_direct_model(fixture, true, 9);
    auto reciprocal16 = make_reciprocal_model(fixture, 16U);
    auto reciprocal32 = make_reciprocal_model(fixture, 32U);
    auto simulation = make_simulation(
        system.get(), forcefield.get(), direct5.get(), reciprocal16.get());
    auto ignored_bounds_peer = make_simulation(
        system.get(), forcefield.get(), direct9.get(), reciprocal16.get());
    auto semantic_peer = make_simulation(
        system.get(), forcefield.get(), direct5.get(), reciprocal32.get());
    Fixture changed_alpha = fixture;
    changed_alpha.alpha = 0.29;
    auto alpha_direct = make_direct_model(changed_alpha);
    auto alpha_reciprocal = make_reciprocal_model(changed_alpha, 16U);
    auto alpha_peer = make_simulation(
        system.get(), forcefield.get(), alpha_direct.get(),
        alpha_reciprocal.get());
    auto timestep_peer = make_simulation(
        system.get(), forcefield.get(), direct5.get(), reciprocal16.get(),
        nullptr, 0.002);
    Fixture changed_dielectric = fixture;
    changed_dielectric.dielectric = 2.0;
    auto dielectric_forcefield = make_forcefield(changed_dielectric);
    auto dielectric_direct = make_direct_model(changed_dielectric);
    auto dielectric_reciprocal = make_reciprocal_model(changed_dielectric);
    auto dielectric_peer = make_simulation(
        system.get(), dielectric_forcefield.get(), dielectric_direct.get(),
        dielectric_reciprocal.get());
    auto explicit_zero_forcefield = make_forcefield(
        fixture, PairProvenance::explicit_zero_scale);
    auto explicit_zero_direct = make_direct_model(
        fixture, true, 5, PairProvenance::explicit_zero_scale);
    auto explicit_zero_peer = make_simulation(
        system.get(), explicit_zero_forcefield.get(),
        explicit_zero_direct.get(), reciprocal16.get());

    bg_dynamics_report_v1 report{};
    init_report(&report);
    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    require_status(bg_context_integrate_particle_mesh_ewald_composite_v1(
        context.get(), simulation.get(), 1U, &report, &error), BG_STATUS_OK,
        "one-step integration failed");
    require(error.code == BG_DIRECT_EWALD_ERROR_NONE,
            "successful integration retained typed error");
    std::uint64_t step = 0;
    require_status(
        bg_particle_mesh_ewald_composite_simulation_v1_get_absolute_step(
            simulation.get(), &step), BG_STATUS_OK, "step query failed");
    require(step == 1U, "integration did not advance absolute step");

    const auto bytes = checkpoint(simulation.get());
    require_status(
        bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_load(
            ignored_bounds_peer.get(), bytes.data(), bytes.size()),
        BG_STATUS_OK, "ignored direct reciprocal bounds changed identity");
    require_status(
        bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_load(
            semantic_peer.get(), bytes.data(), bytes.size()),
        BG_STATUS_INVALID_ARGUMENT,
        "semantic reciprocal mesh change preserved identity");
    for (auto *peer : {alpha_peer.get(), timestep_peer.get(),
                       dielectric_peer.get(), explicit_zero_peer.get()}) {
        require_status(
            bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_load(
                peer, bytes.data(), bytes.size()),
            BG_STATUS_INVALID_ARGUMENT,
            "semantic model or timestep change preserved identity");
    }
}

void verify_late_typed_failure_rolls_back() {
    constexpr double timestep = 0.01;
    const Fixture base;
    auto forcefield = make_forcefield(base);
    Fixture direct_fixture = base;
    direct_fixture.minimum_pair_distance = 1.0;
    auto direct = make_direct_model(direct_fixture);
    auto reciprocal = make_reciprocal_model(base);

    for (const bg_backend lane :
         {BG_BACKEND_CPP_CPU_REFERENCE, BG_BACKEND_RUST_CPU}) {
        auto context = make_context(lane);
        auto initial_system = make_system(base, base.charge);
        std::array<double, 4> force_x{};
        std::array<double, 4> force_y{};
        std::array<double, 4> force_z{};
        bg_particle_mesh_ewald_composite_force_soa_v1 forces{};
        require_status(bg_particle_mesh_ewald_composite_force_soa_v1_init(
            &forces, sizeof(forces),
            BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION), BG_STATUS_OK,
            "force output init failed");
        forces.atom_capacity = base.x.size();
        forces.x_kcal_per_mol_angstrom = force_x.data();
        forces.y_kcal_per_mol_angstrom = force_y.data();
        forces.z_kcal_per_mol_angstrom = force_z.data();
        bg_particle_mesh_ewald_composite_energy_components_v1 energy{};
        require_status(bg_particle_mesh_ewald_composite_energy_components_v1_init(
            &energy, sizeof(energy),
            BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION), BG_STATUS_OK,
            "energy output init failed");
        bg_direct_ewald_error_v1 eval_error{};
        init_error(&eval_error);
        require_status(bg_context_evaluate_particle_mesh_ewald_composite_v1(
            context.get(), initial_system.get(), forcefield.get(), direct.get(),
            reciprocal.get(), &energy, &forces, &eval_error), BG_STATUS_OK,
            "initial force evaluation failed");

        Fixture moving = base;
        const std::array<std::array<double, 4>, 3> targets{{
            std::array<double, 4>{{base.x[0], base.x[1], base.x[2],
                                   base.x[0] + 0.5}},
            std::array<double, 4>{{base.y[0], base.y[1], base.y[2], base.y[0]}},
            std::array<double, 4>{{base.z[0], base.z[1], base.z[2], base.z[0]}}}};
        const std::array<const std::array<double, 4> *, 3> positions{{
            &base.x, &base.y, &base.z}};
        const std::array<const std::array<double, 4> *, 3> force_channels{{
            &force_x, &force_y, &force_z}};
        const std::array<std::array<double, 4> *, 3> velocities{{
            &moving.velocity_x, &moving.velocity_y, &moving.velocity_z}};
        for (std::size_t atom = 0; atom < base.x.size(); ++atom) {
            const double scale = kAccelerationConversion * 0.5 * timestep /
                                 base.mass[atom];
            for (std::size_t axis = 0; axis < 3U; ++axis) {
                const double desired =
                    (targets[axis][atom] - (*positions[axis])[atom]) / timestep;
                (*velocities[axis])[atom] =
                    desired - scale * (*force_channels[axis])[atom];
            }
        }

        auto moving_system = make_system(moving, moving.charge);
        auto simulation = make_simulation(
            moving_system.get(), forcefield.get(), direct.get(),
            reciprocal.get(), nullptr, timestep);
        bg_particle_soa_view view{};
        require_status(bg_particle_soa_view_init(
            &view, sizeof(view), BG_ABI_VERSION), BG_STATUS_OK,
            "particle view init failed");
        require_status(bg_particle_mesh_ewald_composite_simulation_v1_get_particles(
            simulation.get(), &view), BG_STATUS_OK, "particle view failed");
        const auto address = view.position_x_angstrom;
        const auto before = checkpoint(simulation.get());
        bg_dynamics_report_v1 report{};
        init_report(&report);
        report.steps_completed = 123U;
        report.absolute_step = 456U;
        report.total_kcal_per_mol = 789.0;
        const auto report_before = report;
        bg_direct_ewald_error_v1 error{};
        init_error(&error);
        require_status(bg_context_integrate_particle_mesh_ewald_composite_v1(
            context.get(), simulation.get(), 1U, &report, &error),
            BG_STATUS_NUMERICAL_ERROR,
            "late typed evaluator failure did not propagate");
        require(error.code ==
                    BG_DIRECT_EWALD_ERROR_PAIR_BELOW_MINIMUM_DISTANCE &&
                error.detail[0] != '\0',
                "late evaluator failure omitted typed detail");
        require(std::memcmp(&report, &report_before, sizeof(report)) == 0,
                "late evaluator failure mutated report");
        require(checkpoint(simulation.get()) == before,
                "late evaluator failure did not roll back complete state");
        require_status(bg_particle_mesh_ewald_composite_simulation_v1_get_particles(
            simulation.get(), &view), BG_STATUS_OK, "particle view failed");
        require(view.position_x_angstrom == address,
                "late evaluator rollback changed particle addresses");
    }
}

void verify_zero_step_and_restart() {
    const Fixture fixture;
    for (const bg_backend lane :
         {BG_BACKEND_CPP_CPU_REFERENCE, BG_BACKEND_RUST_CPU}) {
        auto context = make_context(lane);
        auto system = make_system(fixture, fixture.charge);
        auto forcefield = make_forcefield(fixture);
        auto direct = make_direct_model(fixture);
        auto reciprocal = make_reciprocal_model(fixture);
        auto zero = make_simulation(
            system.get(), forcefield.get(), direct.get(), reciprocal.get());
        const auto zero_before = checkpoint(zero.get());
        const double expected = stateless_total(
            context.get(), system.get(), forcefield.get(), direct.get(),
            reciprocal.get());
        const bg_dynamics_report_v1 zero_report =
            integrate(context.get(), zero.get(), 0U);
        require_exact(zero_report.potential_kcal_per_mol, expected,
                      "zero-step potential differed from stateless evaluator");
        require(checkpoint(zero.get()) == zero_before,
                "zero-step integration mutated simulation state");

        auto uninterrupted = make_simulation(
            system.get(), forcefield.get(), direct.get(), reciprocal.get());
        auto split = make_simulation(
            system.get(), forcefield.get(), direct.get(), reciprocal.get());
        auto restarted = make_simulation(
            system.get(), forcefield.get(), direct.get(), reciprocal.get());
        integrate(context.get(), uninterrupted.get(), 1U);
        integrate(context.get(), split.get(), 1U);
        const auto mid = checkpoint(split.get());
        require_status(
            bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_load(
                restarted.get(), mid.data(), mid.size()),
            BG_STATUS_OK, "restart checkpoint load failed");
        const bg_dynamics_report_v1 uninterrupted_report =
            integrate(context.get(), uninterrupted.get(), 1U);
        const bg_dynamics_report_v1 restarted_report =
            integrate(context.get(), restarted.get(), 1U);
        require(std::memcmp(&uninterrupted_report, &restarted_report,
                            sizeof(uninterrupted_report)) == 0,
                "same-lane restart report was not bit exact");
        require(checkpoint(uninterrupted.get()) == checkpoint(restarted.get()),
                "same-lane restart checkpoint was not bit exact");
    }
}

void verify_deep_ownership_and_constraints() {
    const Fixture fixture;
    auto context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    auto system = make_system(fixture, fixture.charge);
    auto forcefield = make_forcefield(fixture);
    auto direct = make_direct_model(fixture);
    auto reciprocal = make_reciprocal_model(fixture);
    const std::array<std::uint64_t, 1> atom_i{{0U}};
    const std::array<std::uint64_t, 1> atom_j{{1U}};
    const std::array<double, 1> distance{{
        std::sqrt(std::pow(fixture.x[0] - fixture.x[1], 2.0) +
                  std::pow(fixture.y[0] - fixture.y[1], 2.0) +
                  std::pow(fixture.z[0] - fixture.z[1], 2.0))}};
    bg_distance_constraints_v1 constraints{};
    require_status(bg_distance_constraints_v1_init(
        &constraints, sizeof(constraints), BG_ABI_VERSION), BG_STATUS_OK,
        "constraint init failed");
    constraints.constraint_count = 1U;
    constraints.atom_i = atom_i.data();
    constraints.atom_j = atom_j.data();
    constraints.distance_angstrom = distance.data();
    auto simulation = make_simulation(
        system.get(), forcefield.get(), direct.get(), reciprocal.get(),
        &constraints);
    bg_particle_soa_view before{};
    require_status(bg_particle_soa_view_init(
        &before, sizeof(before), BG_ABI_VERSION), BG_STATUS_OK,
        "particle view init failed");
    require_status(bg_particle_mesh_ewald_composite_simulation_v1_get_particles(
        simulation.get(), &before), BG_STATUS_OK, "particle view failed");
    system.reset();
    forcefield.reset();
    direct.reset();
    reciprocal.reset();
    integrate(context.get(), simulation.get(), 1U);
    bg_particle_soa_view after{};
    require_status(bg_particle_soa_view_init(
        &after, sizeof(after), BG_ABI_VERSION), BG_STATUS_OK,
        "particle view init failed");
    require_status(bg_particle_mesh_ewald_composite_simulation_v1_get_particles(
        simulation.get(), &after), BG_STATUS_OK, "particle view failed");
    require(before.position_x_angstrom == after.position_x_angstrom &&
            before.velocity_x_angstrom_per_femtosecond ==
                after.velocity_x_angstrom_per_femtosecond,
            "owned particle addresses changed");
}

void verify_checkpoint_rejections() {
    const Fixture fixture;
    auto system = make_system(fixture, fixture.charge);
    auto forcefield = make_forcefield(fixture);
    auto direct = make_direct_model(fixture);
    auto reciprocal = make_reciprocal_model(fixture);
    auto simulation = make_simulation(
        system.get(), forcefield.get(), direct.get(), reciprocal.get());
    const auto valid = checkpoint(simulation.get());
    bg_simulation_options_v1 options{};
    require_status(bg_simulation_options_v1_init(
        &options, sizeof(options), BG_ABI_VERSION), BG_STATUS_OK,
        "options init failed");
    options.integrator = BG_INTEGRATOR_VELOCITY_VERLET;
    options.timestep_femtoseconds = 0.001;
    bg_simulation *legacy_raw = nullptr;
    require_status(bg_simulation_create(
        system.get(), forcefield.get(), nullptr, &options, &legacy_raw),
        BG_STATUS_OK, "legacy simulation create failed");
    LegacySimulationPtr legacy(legacy_raw);
    std::uint64_t legacy_size = 0U;
    require_status(bg_simulation_checkpoint_size(legacy.get(), &legacy_size),
                   BG_STATUS_OK, "legacy checkpoint size failed");
    std::vector<std::uint8_t> legacy_bytes(legacy_size);
    std::uint64_t written = 0U;
    require_status(bg_simulation_checkpoint_write(
        legacy.get(), legacy_bytes.data(), legacy_bytes.size(), &written),
        BG_STATUS_OK, "legacy checkpoint write failed");
    require(written == legacy_bytes.size(), "legacy checkpoint size changed");

    bg_direct_ewald_composite_simulation_v1 *direct_raw = nullptr;
    bg_direct_ewald_error_v1 create_error{};
    init_error(&create_error);
    require_status(bg_direct_ewald_composite_simulation_v1_create(
        system.get(), forcefield.get(), direct.get(), nullptr, &options,
        &direct_raw, &create_error), BG_STATUS_OK,
        "direct composite simulation create failed");
    DirectSimulationPtr direct_simulation(direct_raw);
    std::uint64_t direct_size = 0U;
    require_status(bg_direct_ewald_composite_simulation_v1_checkpoint_size(
        direct_simulation.get(), &direct_size), BG_STATUS_OK,
        "direct checkpoint size failed");
    std::vector<std::uint8_t> direct_bytes(direct_size);
    require_status(bg_direct_ewald_composite_simulation_v1_checkpoint_write(
        direct_simulation.get(), direct_bytes.data(), direct_bytes.size(),
        &written), BG_STATUS_OK, "direct checkpoint write failed");
    require(written == direct_bytes.size(), "direct checkpoint size changed");

    for (const auto *bytes : {&legacy_bytes, &direct_bytes}) {
        require_status(
            bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_load(
                simulation.get(), bytes->data(), bytes->size()),
            BG_STATUS_INVALID_ARGUMENT, "cross-format magic was accepted");
        require(checkpoint(simulation.get()) == valid,
                "cross-format checkpoint changed destination state");
    }
    auto corrupt = valid;
    corrupt.back() ^= 1U;
    require_status(
        bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_load(
            simulation.get(), corrupt.data(), corrupt.size()),
        BG_STATUS_INVALID_ARGUMENT, "corrupt checkpoint was accepted");
    require_status(
        bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_load(
            simulation.get(), valid.data(), valid.size() - 1U),
        BG_STATUS_INVALID_ARGUMENT, "truncated checkpoint was accepted");
    auto appended = valid;
    appended.push_back(0U);
    require_status(
        bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_load(
            simulation.get(), appended.data(), appended.size()),
        BG_STATUS_INVALID_ARGUMENT, "appended checkpoint was accepted");
}

void verify_backend_preflight_transactionality() {
    Fixture fixture;
    auto system = make_system(fixture, fixture.charge);
    auto forcefield = make_forcefield(fixture);
    auto direct = make_direct_model(fixture);
    auto reciprocal = make_reciprocal_model(fixture);
    auto simulation = make_simulation(
        system.get(), forcefield.get(), direct.get(), reciprocal.get());
    const auto before = checkpoint(simulation.get());
    auto auto_context = make_context(BG_BACKEND_AUTO);
    bg_dynamics_report_v1 report{};
    init_report(&report);
    report.total_kcal_per_mol = 123.0;
    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    error.code = BG_DIRECT_EWALD_ERROR_PAIR_BELOW_MINIMUM_DISTANCE;
    std::strcpy(error.detail, "stale typed error");
    require_status(bg_context_integrate_particle_mesh_ewald_composite_v1(
        auto_context.get(), simulation.get(), 1U, &report, &error),
        BG_STATUS_UNSUPPORTED_BACKEND, "AUTO did not fail closed");
    require_exact(report.total_kcal_per_mol, 123.0,
                  "AUTO mutated report");
    require(error.code == BG_DIRECT_EWALD_ERROR_NONE && error.detail[0] == '\0',
            "AUTO preflight retained stale typed error");
    std::uint64_t step = 99U;
    require_status(
        bg_particle_mesh_ewald_composite_simulation_v1_get_absolute_step(
            simulation.get(), &step), BG_STATUS_OK, "step query failed");
    require(step == 0U, "AUTO mutated simulation step");
    require(checkpoint(simulation.get()) == before,
            "AUTO mutated checkpoint state");

    auto explicit_context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    explicit_context->requested_backend = BG_BACKEND_RUST_CPU;
    error.code = BG_DIRECT_EWALD_ERROR_PAIR_BELOW_MINIMUM_DISTANCE;
    std::strcpy(error.detail, "stale typed error");
    require_status(bg_context_integrate_particle_mesh_ewald_composite_v1(
        explicit_context.get(), simulation.get(), 1U, &report, &error),
        BG_STATUS_ABI_MISMATCH, "requested/resolved mismatch was accepted");
    require_exact(report.total_kcal_per_mol, 123.0,
                  "lane mismatch mutated report");
    require(error.code == BG_DIRECT_EWALD_ERROR_NONE && error.detail[0] == '\0',
            "lane mismatch retained stale typed error");
    require(checkpoint(simulation.get()) == before,
            "lane mismatch mutated checkpoint state");

    const std::array<bg_backend, 3U> unsupported_lanes{
        static_cast<bg_backend>(BG_BACKEND_HIP_SAFE),
        static_cast<bg_backend>(BG_BACKEND_HIP_FAST),
        static_cast<bg_backend>(999)};
    for (const bg_backend lane : unsupported_lanes) {
        explicit_context->requested_backend = lane;
        explicit_context->backend = lane;
        error.code = BG_DIRECT_EWALD_ERROR_PAIR_BELOW_MINIMUM_DISTANCE;
        std::strcpy(error.detail, "stale typed error");
        require_status(bg_context_integrate_particle_mesh_ewald_composite_v1(
            explicit_context.get(), simulation.get(), 1U, &report, &error),
            BG_STATUS_UNSUPPORTED_BACKEND,
            "HIP or unknown requested lane was accepted");
        require(checkpoint(simulation.get()) == before,
                "unsupported lane mutated checkpoint state");
        require(error.code == BG_DIRECT_EWALD_ERROR_NONE &&
                    error.detail[0] == '\0',
                "unsupported lane retained stale typed error");
    }
}

}  // namespace

int main() {
    static_assert(!is_complete<bg_particle_mesh_ewald_composite_simulation_v1>::value,
                  "public owner must remain opaque");
    require(bg_particle_mesh_ewald_composite_dynamics_abi_version() == 1U,
            "ABI version mismatch");
    require(std::strcmp(
        bg_particle_mesh_ewald_composite_dynamics_v1_profile_id(),
        "betelgeuze.native_particle_mesh_ewald_composite_dynamics/1.0.0") == 0,
        "profile mismatch");
    verify_runtime_and_checkpoint_identity();
    verify_zero_step_and_restart();
    verify_deep_ownership_and_constraints();
    verify_checkpoint_rejections();
    verify_backend_preflight_transactionality();
    verify_late_typed_failure_rolls_back();
    return 0;
}
