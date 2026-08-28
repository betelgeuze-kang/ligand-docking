#define BG_DISABLE_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#define BG_DISABLE_DIRECT_EWALD_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#define BG_DISABLE_DIRECT_EWALD_COMPOSITE_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#include "betelgeuze/direct_ewald_composite_dynamics.h"

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
#include <utility>
#include <vector>

namespace {

constexpr std::size_t kAtomCount = 4U;
constexpr double kAccelerationConversion = 4.184e-4;

[[noreturn]] void fail_test(const char *message) {
    std::fprintf(
        stderr,
        "direct-Ewald composite dynamics test failure: %s\n",
        message);
    std::abort();
}

void require(bool condition, const char *message) {
    if (!condition) {
        fail_test(message);
    }
}

void require_status(
    bg_status actual,
    bg_status expected,
    const char *message) {
    if (actual != expected) {
        std::fprintf(
            stderr,
            "direct-Ewald composite dynamics test failure: %s "
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

struct ModelDeleter final {
    void operator()(bg_direct_ewald_model_v1 *value) const noexcept {
        bg_direct_ewald_model_v1_destroy(value);
    }
};

struct CompositeSimulationDeleter final {
    void operator()(
        bg_direct_ewald_composite_simulation_v1 *value) const noexcept {
        bg_direct_ewald_composite_simulation_v1_destroy(value);
    }
};

struct LegacySimulationDeleter final {
    void operator()(bg_simulation *value) const noexcept {
        bg_simulation_destroy(value);
    }
};

using ContextPtr = std::unique_ptr<bg_context, ContextDeleter>;
using SystemPtr = std::unique_ptr<bg_system, SystemDeleter>;
using ForceFieldPtr = std::unique_ptr<bg_forcefield, ForceFieldDeleter>;
using ModelPtr =
    std::unique_ptr<bg_direct_ewald_model_v1, ModelDeleter>;
using CompositeSimulationPtr = std::unique_ptr<
    bg_direct_ewald_composite_simulation_v1,
    CompositeSimulationDeleter>;
using LegacySimulationPtr =
    std::unique_ptr<bg_simulation, LegacySimulationDeleter>;

enum class PairProvenance {
    exclusion,
    explicit_zero_scale,
};

struct Fixture final {
    std::array<double, kAtomCount> x{{1.25, 3.1, 5.2, 7.4}};
    std::array<double, kAtomCount> y{{2.5, 3.2, 5.3, 6.1}};
    std::array<double, kAtomCount> z{{3.75, 4.4, 4.7, 6.3}};
    std::array<double, kAtomCount> velocity_x{{
        0.0010, -0.0007, 0.0004, -0.0002}};
    std::array<double, kAtomCount> velocity_y{{
        -0.0004, 0.0006, -0.0003, 0.0005}};
    std::array<double, kAtomCount> velocity_z{{
        0.0002, -0.0001, 0.0003, -0.0004}};
    std::array<double, kAtomCount> mass{{12.0, 14.0, 16.0, 19.0}};
    std::array<double, kAtomCount> charge{{
        0.7, -0.4, -0.6, 0.30000000000000004}};
    std::array<double, kAtomCount> sigma{{1.1, 1.2, 1.3, 1.4}};
    std::array<double, kAtomCount> epsilon{{0.15, 0.20, 0.25, 0.30}};

    std::array<uint64_t, 1> bond_i{{UINT64_C(0)}};
    std::array<uint64_t, 1> bond_j{{UINT64_C(1)}};
    std::array<double, 1> bond_equilibrium{{5.0}};
    std::array<double, 1> bond_force_constant{{3.0}};

    std::array<uint64_t, 1> angle_i{{UINT64_C(0)}};
    std::array<uint64_t, 1> angle_j{{UINT64_C(1)}};
    std::array<uint64_t, 1> angle_k{{UINT64_C(2)}};
    std::array<double, 1> angle_equilibrium{{1.4}};
    std::array<double, 1> angle_force_constant{{2.0}};

    std::array<uint64_t, 1> torsion_i{{UINT64_C(0)}};
    std::array<uint64_t, 1> torsion_j{{UINT64_C(1)}};
    std::array<uint64_t, 1> torsion_k{{UINT64_C(2)}};
    std::array<uint64_t, 1> torsion_l{{UINT64_C(3)}};
    std::array<uint32_t, 1> torsion_periodicity{{UINT32_C(3)}};
    std::array<double, 1> torsion_phase{{0.4}};
    std::array<double, 1> torsion_amplitude{{0.7}};

    std::array<uint64_t, 1> exclusion_i{{UINT64_C(0)}};
    std::array<uint64_t, 1> exclusion_j{{UINT64_C(1)}};
    std::array<uint64_t, 1> scale_i{{UINT64_C(2)}};
    std::array<uint64_t, 1> scale_j{{UINT64_C(3)}};
    std::array<double, 1> scale_lennard_jones{{0.25}};
    std::array<double, 1> scale_coulomb{{0.5}};

    std::array<double, 3> cell{{18.0, 20.0, 22.0}};
    double cutoff = 8.9;
    double switch_start = 7.0;
    double dielectric = 1.0;
    double forcefield_minimum_pair_distance = 1.0e-8;
};

struct ModelSettings final {
    double alpha_per_angstrom = 0.31;
    double minimum_pair_distance_angstrom = 1.0e-8;
    PairProvenance provenance = PairProvenance::exclusion;
};

void init_error(bg_direct_ewald_error_v1 *error) {
    require_status(
        bg_direct_ewald_error_v1_init(
            error, sizeof(*error), BG_DIRECT_EWALD_ABI_VERSION),
        BG_STATUS_OK,
        "direct-Ewald error initializer failed");
}

void init_options(
    bg_simulation_options_v1 *options,
    double timestep,
    bg_integrator integrator = BG_INTEGRATOR_VELOCITY_VERLET) {
    require_status(
        bg_simulation_options_v1_init(
            options, sizeof(*options), BG_ABI_VERSION),
        BG_STATUS_OK,
        "simulation-options initializer failed");
    options->integrator = integrator;
    options->timestep_femtoseconds = timestep;
}

void init_report(bg_dynamics_report_v1 *report) {
    require_status(
        bg_dynamics_report_v1_init(
            report, sizeof(*report), BG_ABI_VERSION),
        BG_STATUS_OK,
        "dynamics-report initializer failed");
}

ContextPtr make_context(bg_backend backend) {
    bg_context_options options{};
    require_status(
        bg_context_options_init(
            &options, sizeof(options), BG_ABI_VERSION),
        BG_STATUS_OK,
        "context-options initializer failed");
    options.backend = backend;
    bg_context *raw = nullptr;
    require_status(
        bg_context_create(&options, &raw),
        BG_STATUS_OK,
        "CPU context creation failed");
    require(raw != nullptr, "CPU context creation returned null");
    return ContextPtr(raw);
}

SystemPtr make_system(const Fixture &fixture) {
    bg_particle_soa particles{};
    require_status(
        bg_particle_soa_init(
            &particles, sizeof(particles), BG_ABI_VERSION),
        BG_STATUS_OK,
        "particle initializer failed");
    particles.particle_count = UINT64_C(4);
    particles.position_x_angstrom = fixture.x.data();
    particles.position_y_angstrom = fixture.y.data();
    particles.position_z_angstrom = fixture.z.data();
    particles.velocity_x_angstrom_per_femtosecond =
        fixture.velocity_x.data();
    particles.velocity_y_angstrom_per_femtosecond =
        fixture.velocity_y.data();
    particles.velocity_z_angstrom_per_femtosecond =
        fixture.velocity_z.data();
    particles.mass_dalton = fixture.mass.data();
    particles.charge_elementary = fixture.charge.data();
    bg_system *raw = nullptr;
    require_status(
        bg_system_create(&particles, &raw),
        BG_STATUS_OK,
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
        BG_STATUS_OK,
        "force-field initializer failed");
    parameters.atom_count = UINT64_C(4);
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
    parameters.angle_equilibrium_radians =
        fixture.angle_equilibrium.data();
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

    std::array<uint64_t, 2> scale_i{{UINT64_C(0), UINT64_C(2)}};
    std::array<uint64_t, 2> scale_j{{UINT64_C(1), UINT64_C(3)}};
    std::array<double, 2> scale_lj{{0.0, fixture.scale_lennard_jones[0]}};
    std::array<double, 2> scale_coulomb{{0.0, fixture.scale_coulomb[0]}};
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

    parameters.periodic_axes_mask = BG_PERIODIC_AXES_ALL;
    std::copy(
        fixture.cell.begin(), fixture.cell.end(),
        parameters.cell_lengths_angstrom);
    parameters.cutoff_angstrom = fixture.cutoff;
    parameters.switch_start_angstrom = fixture.switch_start;
    parameters.dielectric = fixture.dielectric;
    parameters.screening_kappa_per_angstrom = 0.0;
    parameters.minimum_pair_distance_angstrom =
        fixture.forcefield_minimum_pair_distance;

    bg_forcefield *raw = nullptr;
    require_status(
        bg_forcefield_create(&parameters, &raw),
        BG_STATUS_OK,
        "force-field creation failed");
    require(raw != nullptr, "force-field creation returned null");
    return ForceFieldPtr(raw);
}

ModelPtr make_model(
    const Fixture &fixture,
    ModelSettings settings = ModelSettings{}) {
    bg_direct_ewald_parameters_v1 parameters{};
    require_status(
        bg_direct_ewald_parameters_v1_init(
            &parameters, sizeof(parameters),
            BG_DIRECT_EWALD_ABI_VERSION),
        BG_STATUS_OK,
        "direct-Ewald parameter initializer failed");
    parameters.atom_count = UINT64_C(4);
    std::copy(
        fixture.cell.begin(), fixture.cell.end(),
        parameters.cell_lengths_angstrom);
    parameters.alpha_per_angstrom = settings.alpha_per_angstrom;
    parameters.real_space_cutoff_angstrom = fixture.cutoff;
    parameters.reciprocal_max_indices[0] = 5;
    parameters.reciprocal_max_indices[1] = 5;
    parameters.reciprocal_max_indices[2] = 5;
    parameters.dielectric = fixture.dielectric;
    parameters.minimum_pair_distance_angstrom =
        settings.minimum_pair_distance_angstrom;

    std::array<uint64_t, 2> scale_i{{UINT64_C(0), UINT64_C(2)}};
    std::array<uint64_t, 2> scale_j{{UINT64_C(1), UINT64_C(3)}};
    std::array<double, 2> scale_value{{0.0, fixture.scale_coulomb[0]}};
    if (settings.provenance == PairProvenance::exclusion) {
        parameters.exclusion_count = fixture.exclusion_i.size();
        parameters.exclusion_atom_i = fixture.exclusion_i.data();
        parameters.exclusion_atom_j = fixture.exclusion_j.data();
        parameters.pair_scale_count = fixture.scale_i.size();
        parameters.pair_scale_atom_i = fixture.scale_i.data();
        parameters.pair_scale_atom_j = fixture.scale_j.data();
        parameters.pair_scale_coulomb = fixture.scale_coulomb.data();
    } else {
        parameters.pair_scale_count = scale_i.size();
        parameters.pair_scale_atom_i = scale_i.data();
        parameters.pair_scale_atom_j = scale_j.data();
        parameters.pair_scale_coulomb = scale_value.data();
    }

    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    bg_direct_ewald_model_v1 *raw = nullptr;
    require_status(
        bg_direct_ewald_model_v1_create(&parameters, &raw, &error),
        BG_STATUS_OK,
        "direct-Ewald model creation failed");
    require(raw != nullptr, "direct-Ewald model creation returned null");
    require(
        error.code == BG_DIRECT_EWALD_ERROR_NONE &&
            error.detail[0] == '\0',
        "direct-Ewald model success set a typed error");
    return ModelPtr(raw);
}

CompositeSimulationPtr make_composite_simulation(
    const bg_system *system,
    const bg_forcefield *forcefield,
    const bg_direct_ewald_model_v1 *model,
    double timestep,
    const bg_distance_constraints_v1 *constraints = nullptr) {
    bg_simulation_options_v1 options{};
    init_options(&options, timestep);
    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    bg_direct_ewald_composite_simulation_v1 *raw = nullptr;
    require_status(
        bg_direct_ewald_composite_simulation_v1_create(
            system, forcefield, model, constraints, &options, &raw, &error),
        BG_STATUS_OK,
        "composite simulation creation failed");
    require(raw != nullptr, "composite simulation creation returned null");
    require(
        error.code == BG_DIRECT_EWALD_ERROR_NONE &&
            error.detail[0] == '\0',
        "composite simulation creation set a typed error");
    return CompositeSimulationPtr(raw);
}

LegacySimulationPtr make_legacy_simulation(
    const bg_system *system,
    const bg_forcefield *forcefield,
    double timestep) {
    bg_simulation_options_v1 options{};
    init_options(&options, timestep);
    bg_simulation *raw = nullptr;
    require_status(
        bg_simulation_create(
            system, forcefield, nullptr, &options, &raw),
        BG_STATUS_OK,
        "legacy simulation creation failed");
    require(raw != nullptr, "legacy simulation creation returned null");
    return LegacySimulationPtr(raw);
}

bg_particle_soa_view system_view(const bg_system *system) {
    bg_particle_soa_view view{};
    require_status(
        bg_particle_soa_view_init(
            &view, sizeof(view), BG_ABI_VERSION),
        BG_STATUS_OK,
        "particle-view initializer failed");
    require_status(
        bg_system_get_particles(system, &view),
        BG_STATUS_OK,
        "system particle view failed");
    return view;
}

bg_particle_soa_view composite_view(
    const bg_direct_ewald_composite_simulation_v1 *simulation) {
    bg_particle_soa_view view{};
    require_status(
        bg_particle_soa_view_init(
            &view, sizeof(view), BG_ABI_VERSION),
        BG_STATUS_OK,
        "particle-view initializer failed");
    require_status(
        bg_direct_ewald_composite_simulation_v1_get_particles(
            simulation, &view),
        BG_STATUS_OK,
        "composite particle view failed");
    return view;
}

bg_particle_soa_view legacy_view(const bg_simulation *simulation) {
    bg_particle_soa_view view{};
    require_status(
        bg_particle_soa_view_init(
            &view, sizeof(view), BG_ABI_VERSION),
        BG_STATUS_OK,
        "legacy particle-view initializer failed");
    require_status(
        bg_simulation_get_particles(simulation, &view),
        BG_STATUS_OK,
        "legacy particle view failed");
    return view;
}

std::array<const double *, 8> view_addresses(
    const bg_particle_soa_view &view) noexcept {
    return {{
        view.position_x_angstrom,
        view.position_y_angstrom,
        view.position_z_angstrom,
        view.velocity_x_angstrom_per_femtosecond,
        view.velocity_y_angstrom_per_femtosecond,
        view.velocity_z_angstrom_per_femtosecond,
        view.mass_dalton,
        view.charge_elementary,
    }};
}

struct ParticleSnapshot final {
    std::array<std::array<uint64_t, kAtomCount>, 8> channels{};
    uint64_t absolute_step = UINT64_C(0);
};

ParticleSnapshot snapshot_view(
    const bg_particle_soa_view &view,
    uint64_t absolute_step) {
    require(
        view.particle_count == UINT64_C(4),
        "particle snapshot received a non-four-atom view");
    const std::array<const double *, 8> channels = view_addresses(view);
    ParticleSnapshot snapshot;
    for (std::size_t channel = 0; channel < channels.size(); ++channel) {
        require(channels[channel] != nullptr, "particle view channel is null");
        for (std::size_t atom = 0; atom < kAtomCount; ++atom) {
            snapshot.channels[channel][atom] = bits(channels[channel][atom]);
        }
    }
    snapshot.absolute_step = absolute_step;
    return snapshot;
}

ParticleSnapshot snapshot_composite(
    const bg_direct_ewald_composite_simulation_v1 *simulation) {
    uint64_t step = UINT64_C(0);
    require_status(
        bg_direct_ewald_composite_simulation_v1_get_absolute_step(
            simulation, &step),
        BG_STATUS_OK,
        "composite absolute-step query failed");
    return snapshot_view(composite_view(simulation), step);
}

ParticleSnapshot snapshot_system(const bg_system *system) {
    return snapshot_view(system_view(system), UINT64_C(0));
}

ParticleSnapshot snapshot_legacy(const bg_simulation *simulation) {
    uint64_t step = UINT64_C(0);
    require_status(
        bg_simulation_get_absolute_step(simulation, &step),
        BG_STATUS_OK,
        "legacy absolute-step query failed");
    return snapshot_view(legacy_view(simulation), step);
}

void require_snapshot_exact(
    const ParticleSnapshot &actual,
    const ParticleSnapshot &expected,
    const char *message) {
    require(
        actual.channels == expected.channels &&
            actual.absolute_step == expected.absolute_step,
        message);
}

void require_dynamic_state_exact(
    const ParticleSnapshot &actual,
    const ParticleSnapshot &expected,
    const char *message) {
    for (std::size_t channel = 0; channel < 6U; ++channel) {
        require(actual.channels[channel] == expected.channels[channel], message);
    }
    require(actual.absolute_step == expected.absolute_step, message);
}

struct StatelessEvaluation final {
    bg_direct_ewald_composite_energy_components_v1 energy{};
    std::array<double, kAtomCount> force_x{};
    std::array<double, kAtomCount> force_y{};
    std::array<double, kAtomCount> force_z{};
};

StatelessEvaluation evaluate_stateless(
    const bg_context *context,
    const bg_system *system,
    const bg_forcefield *forcefield,
    const bg_direct_ewald_model_v1 *model) {
    StatelessEvaluation result;
    require_status(
        bg_direct_ewald_composite_energy_components_v1_init(
            &result.energy,
            sizeof(result.energy),
            BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION),
        BG_STATUS_OK,
        "stateless composite-energy initializer failed");
    bg_direct_ewald_composite_force_soa_v1 forces{};
    require_status(
        bg_direct_ewald_composite_force_soa_v1_init(
            &forces,
            sizeof(forces),
            BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION),
        BG_STATUS_OK,
        "stateless composite-force initializer failed");
    forces.atom_capacity = UINT64_C(4);
    forces.x_kcal_per_mol_angstrom = result.force_x.data();
    forces.y_kcal_per_mol_angstrom = result.force_y.data();
    forces.z_kcal_per_mol_angstrom = result.force_z.data();
    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    require_status(
        bg_context_evaluate_direct_ewald_composite_v1(
            context,
            system,
            forcefield,
            model,
            &result.energy,
            &forces,
            &error),
        BG_STATUS_OK,
        "stateless composite evaluation failed");
    require(
        forces.atom_count == UINT64_C(4),
        "stateless composite force count differed");
    require(
        error.code == BG_DIRECT_EWALD_ERROR_NONE &&
            error.detail[0] == '\0',
        "stateless composite success set a typed error");
    return result;
}

bg_dynamics_report_v1 integrate_success(
    const bg_context *context,
    bg_direct_ewald_composite_simulation_v1 *simulation,
    uint64_t step_count) {
    bg_dynamics_report_v1 report{};
    init_report(&report);
    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    require_status(
        bg_context_integrate_direct_ewald_composite_v1(
            context, simulation, step_count, &report, &error),
        BG_STATUS_OK,
        "composite integration failed");
    require(
        error.code == BG_DIRECT_EWALD_ERROR_NONE &&
            error.detail[0] == '\0',
        "composite integration success set a typed error");
    require(
        report.steps_completed == step_count,
        "composite report completed-step count differed");
    return report;
}

std::vector<uint8_t> write_composite_checkpoint(
    const bg_direct_ewald_composite_simulation_v1 *simulation) {
    uint64_t size = UINT64_C(0);
    require_status(
        bg_direct_ewald_composite_simulation_v1_checkpoint_size(
            simulation, &size),
        BG_STATUS_OK,
        "composite checkpoint-size query failed");
    require(size >= UINT64_C(104), "composite checkpoint size was too small");
    const std::size_t native_size = static_cast<std::size_t>(size);
    require(
        static_cast<uint64_t>(native_size) == size,
        "composite checkpoint size exceeded size_t");
    std::vector<uint8_t> bytes(native_size, UINT8_C(0xa5));
    uint64_t written = UINT64_C(0);
    require_status(
        bg_direct_ewald_composite_simulation_v1_checkpoint_write(
            simulation, bytes.data(), size, &written),
        BG_STATUS_OK,
        "composite checkpoint write failed");
    require(written == size, "composite checkpoint write size differed");
    return bytes;
}

std::vector<uint8_t> write_legacy_checkpoint(
    const bg_simulation *simulation) {
    uint64_t size = UINT64_C(0);
    require_status(
        bg_simulation_checkpoint_size(simulation, &size),
        BG_STATUS_OK,
        "legacy checkpoint-size query failed");
    std::vector<uint8_t> bytes(static_cast<std::size_t>(size));
    uint64_t written = UINT64_C(0);
    require_status(
        bg_simulation_checkpoint_write(
            simulation, bytes.data(), size, &written),
        BG_STATUS_OK,
        "legacy checkpoint write failed");
    require(written == size, "legacy checkpoint write size differed");
    return bytes;
}

void require_report_finite(
    const bg_dynamics_report_v1 &report,
    const char *message) {
    require(
        std::isfinite(report.potential_kcal_per_mol) &&
            std::isfinite(report.kinetic_kcal_per_mol) &&
            std::isfinite(report.total_kcal_per_mol) &&
            std::isfinite(report.temperature_kelvin),
        message);
}

void verify_abi_profile_and_descriptor_transactionality() {
    static_assert(
        !is_complete<bg_direct_ewald_composite_simulation_v1>::value,
        "public composite simulation owner must remain opaque");
    static_assert(sizeof(bg_simulation_options_v1) == 80U);
    static_assert(sizeof(bg_distance_constraints_v1) == 104U);
    static_assert(sizeof(bg_dynamics_report_v1) == 104U);

    require(
        bg_direct_ewald_composite_dynamics_abi_version() == UINT32_C(1),
        "composite dynamics ABI version differed");
    require(
        bg_direct_ewald_composite_dynamics_abi_version_major() ==
            UINT32_C(1),
        "composite dynamics ABI major differed");
    require(
        bg_direct_ewald_composite_dynamics_abi_version_minor() ==
            UINT32_C(0),
        "composite dynamics ABI minor differed");
    const char *const version =
        bg_direct_ewald_composite_dynamics_abi_version_string();
    require(
        version != nullptr && std::string(version) == "1.0.0",
        "composite dynamics ABI version string differed");
    const char *const profile =
        bg_direct_ewald_composite_dynamics_v1_profile_id();
    require(
        profile != nullptr &&
            std::string(profile) ==
                "betelgeuze.native_direct_ewald_composite_dynamics/1.0.0",
        "composite dynamics profile identity differed");

    bg_direct_ewald_composite_simulation_v1_destroy(nullptr);

    const Fixture fixture;
    const SystemPtr system = make_system(fixture);
    const ForceFieldPtr forcefield = make_forcefield(fixture);
    const ModelPtr model = make_model(fixture);
    bg_simulation_options_v1 options{};
    init_options(&options, 0.001);
    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    bg_direct_ewald_composite_simulation_v1 *raw = nullptr;

    require_status(
        bg_direct_ewald_composite_simulation_v1_create(
            nullptr,
            forcefield.get(),
            model.get(),
            nullptr,
            &options,
            &raw,
            &error),
        BG_STATUS_INVALID_ARGUMENT,
        "composite creation accepted a null system");
    require(raw == nullptr, "failed composite creation returned an owner");
    require(
        error.code == BG_DIRECT_EWALD_ERROR_NONE &&
            error.detail[0] == '\0',
        "validated null-input failure retained stale typed error");

    init_error(&error);
    error.code = BG_DIRECT_EWALD_ERROR_NON_NEUTRAL_SYSTEM;
    std::memcpy(error.detail, "stale", sizeof("stale"));
    require_status(
        bg_direct_ewald_composite_simulation_v1_create(
            system.get(),
            nullptr,
            model.get(),
            nullptr,
            &options,
            &raw,
            &error),
        BG_STATUS_INVALID_ARGUMENT,
        "composite creation accepted a null force field");
    require(raw == nullptr, "null-force-field creation returned an owner");
    require(
        error.code == BG_DIRECT_EWALD_ERROR_NONE &&
            error.detail[0] == '\0',
        "null-force-field failure did not clear typed error");

    init_error(&error);
    require_status(
        bg_direct_ewald_composite_simulation_v1_create(
            system.get(),
            forcefield.get(),
            nullptr,
            nullptr,
            &options,
            &raw,
            &error),
        BG_STATUS_INVALID_ARGUMENT,
        "composite creation accepted a null model");
    require(raw == nullptr, "null-model creation returned an owner");

    init_error(&error);
    require_status(
        bg_direct_ewald_composite_simulation_v1_create(
            system.get(),
            forcefield.get(),
            model.get(),
            nullptr,
            nullptr,
            &raw,
            &error),
        BG_STATUS_INVALID_ARGUMENT,
        "composite creation accepted null options");
    require(raw == nullptr, "null-options creation returned an owner");

    require_status(
        bg_direct_ewald_composite_simulation_v1_create(
            system.get(),
            forcefield.get(),
            model.get(),
            nullptr,
            &options,
            nullptr,
            &error),
        BG_STATUS_INVALID_ARGUMENT,
        "composite creation accepted null owner output");
    require_status(
        bg_direct_ewald_composite_simulation_v1_create(
            system.get(),
            forcefield.get(),
            model.get(),
            nullptr,
            &options,
            &raw,
            nullptr),
        BG_STATUS_INVALID_ARGUMENT,
        "composite creation accepted null typed-error output");
    require(raw == nullptr, "null-error creation returned an owner");

    init_error(&error);
    error.struct_size -= UINT32_C(1);
    const bg_direct_ewald_error_v1 invalid_error_before = error;
    require_status(
        bg_direct_ewald_composite_simulation_v1_create(
            system.get(),
            forcefield.get(),
            model.get(),
            nullptr,
            &options,
            &raw,
            &error),
        BG_STATUS_ABI_MISMATCH,
        "composite creation accepted a short typed-error descriptor");
    require(raw == nullptr, "descriptor failure returned an owner");
    require(
        std::memcmp(&error, &invalid_error_before, sizeof(error)) == 0,
        "typed-error descriptor failure changed its storage");

    init_error(&error);
    bg_simulation_options_v1 invalid_options = options;
    invalid_options.struct_size -= UINT32_C(1);
    require_status(
        bg_direct_ewald_composite_simulation_v1_create(
            system.get(),
            forcefield.get(),
            model.get(),
            nullptr,
            &invalid_options,
            &raw,
            &error),
        BG_STATUS_ABI_MISMATCH,
        "composite creation accepted a short options descriptor");
    require(raw == nullptr, "invalid-options creation returned an owner");

    const CompositeSimulationPtr simulation = make_composite_simulation(
        system.get(), forcefield.get(), model.get(), 0.001);
    const ParticleSnapshot state_before = snapshot_composite(simulation.get());

    require_status(
        bg_direct_ewald_composite_simulation_v1_get_particles(
            nullptr, nullptr),
        BG_STATUS_INVALID_ARGUMENT,
        "particle query accepted null arguments");
    require_status(
        bg_direct_ewald_composite_simulation_v1_get_particles(
            simulation.get(), nullptr),
        BG_STATUS_INVALID_ARGUMENT,
        "particle query accepted null output");
    bg_particle_soa_view invalid_view{};
    require_status(
        bg_particle_soa_view_init(
            &invalid_view, sizeof(invalid_view), BG_ABI_VERSION),
        BG_STATUS_OK,
        "invalid-view initializer failed");
    invalid_view.reserved[0] = UINT64_C(1);
    const bg_particle_soa_view invalid_view_before = invalid_view;
    require_status(
        bg_direct_ewald_composite_simulation_v1_get_particles(
            simulation.get(), &invalid_view),
        BG_STATUS_INVALID_ARGUMENT,
        "particle query accepted nonzero reserved data");
    require(
        std::memcmp(
            &invalid_view, &invalid_view_before, sizeof(invalid_view)) == 0,
        "failed particle query changed its descriptor");

    uint64_t step = UINT64_C(77);
    require_status(
        bg_direct_ewald_composite_simulation_v1_get_absolute_step(
            nullptr, &step),
        BG_STATUS_INVALID_ARGUMENT,
        "absolute-step query accepted null owner");
    require(step == UINT64_C(77), "failed step query changed output");
    require_status(
        bg_direct_ewald_composite_simulation_v1_get_absolute_step(
            simulation.get(), nullptr),
        BG_STATUS_INVALID_ARGUMENT,
        "absolute-step query accepted null output");

    bg_dynamics_report_v1 report{};
    init_report(&report);
    report.steps_completed = UINT64_C(91);
    report.total_kcal_per_mol = 123.5;
    bg_dynamics_report_v1 invalid_report = report;
    invalid_report.struct_size -= UINT32_C(1);
    const bg_dynamics_report_v1 invalid_report_before = invalid_report;
    init_error(&error);
    require_status(
        bg_context_integrate_direct_ewald_composite_v1(
            make_context(BG_BACKEND_CPP_CPU_REFERENCE).get(),
            simulation.get(),
            UINT64_C(0),
            &invalid_report,
            &error),
        BG_STATUS_ABI_MISMATCH,
        "integration accepted a short report descriptor");
    require(
        std::memcmp(
            &invalid_report,
            &invalid_report_before,
            sizeof(invalid_report)) == 0,
        "report descriptor failure changed report storage");

    const ContextPtr context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    init_report(&report);
    report.steps_completed = UINT64_C(92);
    report.total_kcal_per_mol = 456.5;
    const bg_dynamics_report_v1 report_before = report;
    init_error(&error);
    error.struct_size -= UINT32_C(1);
    const bg_direct_ewald_error_v1 bad_call_error_before = error;
    require_status(
        bg_context_integrate_direct_ewald_composite_v1(
            context.get(), simulation.get(), UINT64_C(0), &report, &error),
        BG_STATUS_ABI_MISMATCH,
        "integration accepted a short typed-error descriptor");
    require(
        std::memcmp(&report, &report_before, sizeof(report)) == 0,
        "typed-error descriptor failure changed report");
    require(
        std::memcmp(
            &error, &bad_call_error_before, sizeof(error)) == 0,
        "typed-error descriptor failure changed typed error");

    init_error(&error);
    require_status(
        bg_context_integrate_direct_ewald_composite_v1(
            nullptr, simulation.get(), UINT64_C(0), &report, &error),
        BG_STATUS_INVALID_ARGUMENT,
        "integration accepted a null context");
    require(
        std::memcmp(&report, &report_before, sizeof(report)) == 0,
        "null-context failure changed report");
    require_status(
        bg_context_integrate_direct_ewald_composite_v1(
            context.get(), simulation.get(), UINT64_C(0), nullptr, &error),
        BG_STATUS_INVALID_ARGUMENT,
        "integration accepted a null report");
    require_status(
        bg_context_integrate_direct_ewald_composite_v1(
            context.get(), simulation.get(), UINT64_C(0), &report, nullptr),
        BG_STATUS_INVALID_ARGUMENT,
        "integration accepted a null typed-error output");
    require_snapshot_exact(
        snapshot_composite(simulation.get()),
        state_before,
        "descriptor failures changed composite state");
}

void verify_deep_ownership_and_stable_views() {
    Fixture fixture;
    SystemPtr system = make_system(fixture);
    ForceFieldPtr forcefield = make_forcefield(fixture);
    ModelPtr model = make_model(fixture);
    const ParticleSnapshot input_before = snapshot_system(system.get());

    uint64_t constraint_i = UINT64_C(0);
    uint64_t constraint_j = UINT64_C(1);
    const double dx = fixture.x[0] - fixture.x[1];
    const double dy = fixture.y[0] - fixture.y[1];
    const double dz = fixture.z[0] - fixture.z[1];
    double constraint_distance = std::sqrt(dx * dx + dy * dy + dz * dz);
    bg_distance_constraints_v1 constraints{};
    require_status(
        bg_distance_constraints_v1_init(
            &constraints, sizeof(constraints), BG_ABI_VERSION),
        BG_STATUS_OK,
        "constraint initializer failed");
    constraints.constraint_count = UINT64_C(1);
    constraints.atom_i = &constraint_i;
    constraints.atom_j = &constraint_j;
    constraints.distance_angstrom = &constraint_distance;

    CompositeSimulationPtr simulation = make_composite_simulation(
        system.get(),
        forcefield.get(),
        model.get(),
        0.0005,
        &constraints);
    require_snapshot_exact(
        snapshot_system(system.get()),
        input_before,
        "composite creation mutated its input system");

    fixture.x.fill(900.0);
    fixture.velocity_x.fill(800.0);
    fixture.mass.fill(700.0);
    fixture.charge.fill(0.0);
    fixture.sigma.fill(600.0);
    fixture.epsilon.fill(500.0);
    constraint_i = UINT64_C(2);
    constraint_j = UINT64_C(3);
    constraint_distance = 8.0;
    system.reset();
    forcefield.reset();
    model.reset();

    const bg_particle_soa_view initial_view = composite_view(simulation.get());
    const auto addresses = view_addresses(initial_view);
    const ParticleSnapshot initial = snapshot_composite(simulation.get());
    const std::vector<uint8_t> checkpoint =
        write_composite_checkpoint(simulation.get());

    const bg_dynamics_report_v1 zero =
        integrate_success(
            make_context(BG_BACKEND_CPP_CPU_REFERENCE).get(),
            simulation.get(),
            UINT64_C(0));
    require_report_finite(zero, "deep-owned zero-step report was non-finite");
    require(
        view_addresses(composite_view(simulation.get())) == addresses,
        "zero-step integration changed borrowed channel addresses");
    require_snapshot_exact(
        snapshot_composite(simulation.get()),
        initial,
        "zero-step integration changed deep-owned state");

    const ContextPtr context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    integrate_success(context.get(), simulation.get(), UINT64_C(2));
    require(
        view_addresses(composite_view(simulation.get())) == addresses,
        "nonzero integration changed borrowed channel addresses");
    require_status(
        bg_direct_ewald_composite_simulation_v1_checkpoint_load(
            simulation.get(), checkpoint.data(), checkpoint.size()),
        BG_STATUS_OK,
        "deep-owned checkpoint reload failed");
    require(
        view_addresses(composite_view(simulation.get())) == addresses,
        "checkpoint load changed borrowed channel addresses");
    require_snapshot_exact(
        snapshot_composite(simulation.get()),
        initial,
        "checkpoint load did not restore deep-owned state exactly");
}

void require_thermodynamic_report_exact(
    const bg_dynamics_report_v1 &actual,
    const bg_dynamics_report_v1 &expected,
    const char *message) {
    require(
        actual.absolute_step == expected.absolute_step &&
            actual.degrees_of_freedom == expected.degrees_of_freedom &&
            bits(actual.potential_kcal_per_mol) ==
                bits(expected.potential_kcal_per_mol) &&
            bits(actual.kinetic_kcal_per_mol) ==
                bits(expected.kinetic_kcal_per_mol) &&
            bits(actual.total_kcal_per_mol) ==
                bits(expected.total_kcal_per_mol) &&
            bits(actual.temperature_kelvin) ==
                bits(expected.temperature_kelvin),
        message);
}

void verify_zero_step_matches_stateless() {
    const Fixture fixture;
    const SystemPtr system = make_system(fixture);
    const ForceFieldPtr forcefield = make_forcefield(fixture);
    const ModelPtr model = make_model(fixture);

    for (const bg_backend backend : {
             BG_BACKEND_CPP_CPU_REFERENCE,
             BG_BACKEND_RUST_CPU,
         }) {
        const ContextPtr context = make_context(backend);
        const StatelessEvaluation stateless = evaluate_stateless(
            context.get(), system.get(), forcefield.get(), model.get());
        const CompositeSimulationPtr simulation = make_composite_simulation(
            system.get(), forcefield.get(), model.get(), 0.001);
        const ParticleSnapshot before = snapshot_composite(simulation.get());
        const auto addresses = view_addresses(composite_view(simulation.get()));
        const bg_dynamics_report_v1 report = integrate_success(
            context.get(), simulation.get(), UINT64_C(0));
        require_exact(
            report.potential_kcal_per_mol,
            stateless.energy.total_kcal_per_mol,
            "zero-step potential differed from stateless composite total");
        require(
            report.absolute_step == UINT64_C(0) &&
                report.degrees_of_freedom == UINT64_C(12),
            "zero-step report counters differed");
        require_report_finite(report, "zero-step report was non-finite");
        require_snapshot_exact(
            snapshot_composite(simulation.get()),
            before,
            "zero-step integration changed state");
        require(
            view_addresses(composite_view(simulation.get())) == addresses,
            "zero-step integration changed view addresses");
    }
}

void verify_manual_velocity_verlet_and_same_lane_repeat() {
    constexpr double timestep = 0.001;
    const Fixture fixture;
    const SystemPtr initial_system = make_system(fixture);
    const ForceFieldPtr forcefield = make_forcefield(fixture);
    const ModelPtr model = make_model(fixture);
    const ParticleSnapshot caller_before = snapshot_system(initial_system.get());

    for (const bg_backend backend : {
             BG_BACKEND_CPP_CPU_REFERENCE,
             BG_BACKEND_RUST_CPU,
         }) {
        const ContextPtr context = make_context(backend);
        const StatelessEvaluation initial_force = evaluate_stateless(
            context.get(), initial_system.get(), forcefield.get(), model.get());

        Fixture drifted = fixture;
        const std::array<const std::array<double, kAtomCount> *, 3>
            force_channels{{
                &initial_force.force_x,
                &initial_force.force_y,
                &initial_force.force_z,
            }};
        const std::array<const std::array<double, kAtomCount> *, 3>
            initial_positions{{&fixture.x, &fixture.y, &fixture.z}};
        const std::array<const std::array<double, kAtomCount> *, 3>
            initial_velocities{{
                &fixture.velocity_x,
                &fixture.velocity_y,
                &fixture.velocity_z,
            }};
        const std::array<std::array<double, kAtomCount> *, 3>
            drifted_positions{{&drifted.x, &drifted.y, &drifted.z}};
        const std::array<std::array<double, kAtomCount> *, 3>
            half_velocities{{
                &drifted.velocity_x,
                &drifted.velocity_y,
                &drifted.velocity_z,
            }};
        const double half_timestep = 0.5 * timestep;
        for (std::size_t atom = 0; atom < kAtomCount; ++atom) {
            const double half_kick_scale =
                kAccelerationConversion * half_timestep /
                fixture.mass[atom];
            for (std::size_t axis = 0; axis < 3U; ++axis) {
                const double velocity =
                    (*initial_velocities[axis])[atom] +
                    half_kick_scale * (*force_channels[axis])[atom];
                (*half_velocities[axis])[atom] = velocity;
                (*drifted_positions[axis])[atom] =
                    (*initial_positions[axis])[atom] +
                    timestep * velocity;
            }
        }

        const SystemPtr drifted_system = make_system(drifted);
        const StatelessEvaluation final_force = evaluate_stateless(
            context.get(), drifted_system.get(), forcefield.get(), model.get());
        std::array<std::array<double, kAtomCount>, 3> final_velocities{{
            drifted.velocity_x,
            drifted.velocity_y,
            drifted.velocity_z,
        }};
        const std::array<const std::array<double, kAtomCount> *, 3>
            final_force_channels{{
                &final_force.force_x,
                &final_force.force_y,
                &final_force.force_z,
            }};
        for (std::size_t atom = 0; atom < kAtomCount; ++atom) {
            const double half_kick_scale =
                kAccelerationConversion * half_timestep /
                fixture.mass[atom];
            for (std::size_t axis = 0; axis < 3U; ++axis) {
                final_velocities[axis][atom] =
                    final_velocities[axis][atom] +
                    half_kick_scale * (*final_force_channels[axis])[atom];
            }
        }

        const CompositeSimulationPtr first = make_composite_simulation(
            initial_system.get(), forcefield.get(), model.get(), timestep);
        const CompositeSimulationPtr second = make_composite_simulation(
            initial_system.get(), forcefield.get(), model.get(), timestep);
        const bg_dynamics_report_v1 first_report = integrate_success(
            context.get(), first.get(), UINT64_C(1));
        const bg_dynamics_report_v1 second_report = integrate_success(
            context.get(), second.get(), UINT64_C(1));
        const bg_particle_soa_view observed = composite_view(first.get());
        const std::array<const double *, 3> observed_positions{{
            observed.position_x_angstrom,
            observed.position_y_angstrom,
            observed.position_z_angstrom,
        }};
        const std::array<const double *, 3> observed_velocities{{
            observed.velocity_x_angstrom_per_femtosecond,
            observed.velocity_y_angstrom_per_femtosecond,
            observed.velocity_z_angstrom_per_femtosecond,
        }};
        for (std::size_t atom = 0; atom < kAtomCount; ++atom) {
            for (std::size_t axis = 0; axis < 3U; ++axis) {
                require_exact(
                    observed_positions[axis][atom],
                    (*drifted_positions[axis])[atom],
                    "one-step position differed from manual Velocity Verlet");
                require_exact(
                    observed_velocities[axis][atom],
                    final_velocities[axis][atom],
                    "one-step velocity differed from manual Velocity Verlet");
            }
        }
        require_exact(
            first_report.potential_kcal_per_mol,
            final_force.energy.total_kcal_per_mol,
            "one-step report potential differed from final stateless total");
        require_dynamic_state_exact(
            snapshot_composite(first.get()),
            snapshot_composite(second.get()),
            "same-lane one-step repeat changed state bits");
        require_thermodynamic_report_exact(
            first_report,
            second_report,
            "same-lane one-step repeat changed report bits");
    }

    require_snapshot_exact(
        snapshot_system(initial_system.get()),
        caller_before,
        "composite dynamics mutated the caller system");
}

void verify_checkpoint_continuation_and_small_nve() {
    constexpr double timestep = 0.0005;
    const Fixture fixture;
    const SystemPtr system = make_system(fixture);
    const ForceFieldPtr forcefield = make_forcefield(fixture);
    const ModelPtr model = make_model(fixture);

    for (const bg_backend backend : {
             BG_BACKEND_CPP_CPU_REFERENCE,
             BG_BACKEND_RUST_CPU,
         }) {
        const ContextPtr context = make_context(backend);
        const CompositeSimulationPtr uninterrupted =
            make_composite_simulation(
                system.get(), forcefield.get(), model.get(), timestep);
        const CompositeSimulationPtr split = make_composite_simulation(
            system.get(), forcefield.get(), model.get(), timestep);
        const CompositeSimulationPtr restarted = make_composite_simulation(
            system.get(), forcefield.get(), model.get(), timestep);

        const bg_dynamics_report_v1 initial = integrate_success(
            context.get(), uninterrupted.get(), UINT64_C(0));
        const bg_dynamics_report_v1 uninterrupted_report = integrate_success(
            context.get(), uninterrupted.get(), UINT64_C(12));
        integrate_success(context.get(), split.get(), UINT64_C(5));
        const std::vector<uint8_t> split_checkpoint =
            write_composite_checkpoint(split.get());
        require(
            split_checkpoint == write_composite_checkpoint(split.get()),
            "repeated composite checkpoint writes differed");
        constexpr std::array<uint8_t, 8> composite_magic{{
            'B', 'G', 'D', 'E', 'C', '0', '0', '1'}};
        require(
            std::equal(
                composite_magic.begin(),
                composite_magic.end(),
                split_checkpoint.begin()),
            "composite checkpoint magic differed");
        require_status(
            bg_direct_ewald_composite_simulation_v1_checkpoint_load(
                restarted.get(),
                split_checkpoint.data(),
                split_checkpoint.size()),
            BG_STATUS_OK,
            "composite checkpoint continuation load failed");
        require_dynamic_state_exact(
            snapshot_composite(restarted.get()),
            snapshot_composite(split.get()),
            "checkpoint load did not restore split state exactly");

        const bg_dynamics_report_v1 split_report = integrate_success(
            context.get(), split.get(), UINT64_C(7));
        const bg_dynamics_report_v1 restarted_report = integrate_success(
            context.get(), restarted.get(), UINT64_C(7));
        const ParticleSnapshot expected = snapshot_composite(uninterrupted.get());
        require_dynamic_state_exact(
            snapshot_composite(split.get()),
            expected,
            "split integration differed from uninterrupted state");
        require_dynamic_state_exact(
            snapshot_composite(restarted.get()),
            expected,
            "checkpoint continuation differed from uninterrupted state");
        require_thermodynamic_report_exact(
            split_report,
            restarted_report,
            "checkpoint continuation changed final report bits");
        require_thermodynamic_report_exact(
            split_report,
            uninterrupted_report,
            "split integration changed uninterrupted thermodynamics");
        require(
            write_composite_checkpoint(split.get()) ==
                write_composite_checkpoint(uninterrupted.get()) &&
                write_composite_checkpoint(restarted.get()) ==
                    write_composite_checkpoint(uninterrupted.get()),
            "equivalent final states produced different checkpoints");

        require_report_finite(
            uninterrupted_report,
            "small NVE report contained a non-finite value");
        const double drift =
            std::abs(
                uninterrupted_report.total_kcal_per_mol -
                initial.total_kcal_per_mol);
        require(
            std::isfinite(drift) &&
                drift <=
                    1.0e-5 *
                        (1.0 + std::abs(initial.total_kcal_per_mol)),
            "small NVE total-energy drift exceeded its development bound");
    }
}

void verify_baoab_hip_and_step_overflow_fail_closed() {
    const Fixture fixture;
    const SystemPtr system = make_system(fixture);
    const ForceFieldPtr forcefield = make_forcefield(fixture);
    const ModelPtr model = make_model(fixture);
    const ParticleSnapshot caller_before = snapshot_system(system.get());

    bg_simulation_options_v1 baoab{};
    init_options(&baoab, 0.001, BG_INTEGRATOR_LANGEVIN_BAOAB);
    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    error.code = BG_DIRECT_EWALD_ERROR_NONFINITE_RESULT;
    std::memcpy(error.detail, "stale", sizeof("stale"));
    bg_direct_ewald_composite_simulation_v1 *raw = nullptr;
    require_status(
        bg_direct_ewald_composite_simulation_v1_create(
            system.get(),
            forcefield.get(),
            model.get(),
            nullptr,
            &baoab,
            &raw,
            &error),
        BG_STATUS_INVALID_ARGUMENT,
        "composite dynamics accepted BAOAB");
    require(raw == nullptr, "BAOAB rejection returned an owner");
    require(
        error.code == BG_DIRECT_EWALD_ERROR_NONE &&
            error.detail[0] == '\0',
        "BAOAB rejection retained a typed Ewald error");
    require_snapshot_exact(
        snapshot_system(system.get()),
        caller_before,
        "BAOAB rejection changed the caller system");

    const CompositeSimulationPtr simulation = make_composite_simulation(
        system.get(), forcefield.get(), model.get(), 0.001);
    for (const bg_backend backend : {
             BG_BACKEND_HIP_SAFE,
             BG_BACKEND_HIP_FAST,
         }) {
        bg_context fake_context{};
        fake_context.backend = backend;
        fake_context.unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        const ParticleSnapshot before = snapshot_composite(simulation.get());
        bg_dynamics_report_v1 report{};
        init_report(&report);
        report.steps_completed = UINT64_C(55);
        report.total_kcal_per_mol = 66.0;
        const bg_dynamics_report_v1 report_before = report;
        init_error(&error);
        error.code = BG_DIRECT_EWALD_ERROR_NONFINITE_RESULT;
        std::memcpy(error.detail, "stale", sizeof("stale"));
        require_status(
            bg_context_integrate_direct_ewald_composite_v1(
                &fake_context,
                simulation.get(),
                UINT64_C(0),
                &report,
                &error),
            BG_STATUS_UNSUPPORTED_BACKEND,
            "composite HIP integration did not fail closed");
        require(
            std::memcmp(&report, &report_before, sizeof(report)) == 0,
            "HIP rejection changed report");
        require(
            error.code == BG_DIRECT_EWALD_ERROR_NONE &&
                error.detail[0] == '\0',
            "HIP rejection retained a typed Ewald error");
        require_snapshot_exact(
            snapshot_composite(simulation.get()),
            before,
            "HIP rejection changed state");
    }

    const ContextPtr context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    integrate_success(context.get(), simulation.get(), UINT64_C(1));
    const ParticleSnapshot overflow_before = snapshot_composite(simulation.get());
    bg_dynamics_report_v1 overflow_report{};
    init_report(&overflow_report);
    overflow_report.steps_completed = UINT64_C(77);
    overflow_report.total_kcal_per_mol = 88.0;
    const bg_dynamics_report_v1 overflow_report_before = overflow_report;
    init_error(&error);
    error.code = BG_DIRECT_EWALD_ERROR_NONFINITE_RESULT;
    std::memcpy(error.detail, "stale", sizeof("stale"));
    require_status(
        bg_context_integrate_direct_ewald_composite_v1(
            context.get(),
            simulation.get(),
            UINT64_MAX,
            &overflow_report,
            &error),
        BG_STATUS_CAPACITY_OVERFLOW,
        "composite dynamics accepted an overflowing step count");
    require(
        std::memcmp(
            &overflow_report,
            &overflow_report_before,
            sizeof(overflow_report)) == 0,
        "step overflow changed report");
    require(
        error.code == BG_DIRECT_EWALD_ERROR_NONE &&
            error.detail[0] == '\0',
        "step overflow retained a typed Ewald error");
    require_snapshot_exact(
        snapshot_composite(simulation.get()),
        overflow_before,
        "step overflow changed composite state");
}

void verify_late_typed_ewald_failure_rolls_back() {
    constexpr double timestep = 0.01;
    const Fixture fixture;
    const ForceFieldPtr forcefield = make_forcefield(fixture);
    ModelSettings model_settings;
    model_settings.minimum_pair_distance_angstrom = 1.0;
    const ModelPtr model = make_model(fixture, model_settings);

    for (const bg_backend backend : {
             BG_BACKEND_CPP_CPU_REFERENCE,
             BG_BACKEND_RUST_CPU,
         }) {
        const ContextPtr context = make_context(backend);
        const SystemPtr force_system = make_system(fixture);
        const StatelessEvaluation initial_force = evaluate_stateless(
            context.get(), force_system.get(), forcefield.get(), model.get());

        Fixture moving = fixture;
        std::array<std::array<double, kAtomCount>, 3> targets{{
            fixture.x,
            fixture.y,
            fixture.z,
        }};
        targets[0][3] = fixture.x[0] + 0.5;
        targets[1][3] = fixture.y[0];
        targets[2][3] = fixture.z[0];
        const std::array<const std::array<double, kAtomCount> *, 3>
            initial_positions{{&fixture.x, &fixture.y, &fixture.z}};
        const std::array<const std::array<double, kAtomCount> *, 3>
            force_channels{{
                &initial_force.force_x,
                &initial_force.force_y,
                &initial_force.force_z,
            }};
        const std::array<std::array<double, kAtomCount> *, 3>
            velocity_channels{{
                &moving.velocity_x,
                &moving.velocity_y,
                &moving.velocity_z,
            }};
        const double half_timestep = 0.5 * timestep;
        for (std::size_t atom = 0; atom < kAtomCount; ++atom) {
            const double scale =
                kAccelerationConversion * half_timestep /
                fixture.mass[atom];
            for (std::size_t axis = 0; axis < 3U; ++axis) {
                const double desired_half_velocity =
                    (targets[axis][atom] -
                     (*initial_positions[axis])[atom]) /
                    timestep;
                (*velocity_channels[axis])[atom] =
                    desired_half_velocity -
                    scale * (*force_channels[axis])[atom];
            }
        }

        const SystemPtr moving_system = make_system(moving);
        const CompositeSimulationPtr simulation = make_composite_simulation(
            moving_system.get(),
            forcefield.get(),
            model.get(),
            timestep);
        const ParticleSnapshot before = snapshot_composite(simulation.get());
        const auto addresses = view_addresses(composite_view(simulation.get()));
        bg_dynamics_report_v1 report{};
        init_report(&report);
        report.steps_completed = UINT64_C(123);
        report.absolute_step = UINT64_C(456);
        report.total_kcal_per_mol = 789.0;
        const bg_dynamics_report_v1 report_before = report;
        bg_direct_ewald_error_v1 error{};
        init_error(&error);
        require_status(
            bg_context_integrate_direct_ewald_composite_v1(
                context.get(),
                simulation.get(),
                UINT64_C(1),
                &report,
                &error),
            BG_STATUS_NUMERICAL_ERROR,
            "late direct-Ewald failure did not propagate numerical status");
        require(
            error.code ==
                BG_DIRECT_EWALD_ERROR_PAIR_BELOW_MINIMUM_DISTANCE,
            "late direct-Ewald failure returned the wrong typed code");
        require(
            error.detail[0] != '\0',
            "late direct-Ewald failure omitted typed detail");
        require(
            std::memcmp(&report, &report_before, sizeof(report)) == 0,
            "late direct-Ewald failure changed report");
        require_snapshot_exact(
            snapshot_composite(simulation.get()),
            before,
            "late direct-Ewald failure did not roll back whole state");
        require(
            view_addresses(composite_view(simulation.get())) == addresses,
            "late direct-Ewald rollback changed view addresses");
    }
}

void expect_composite_checkpoint_load_failure(
    bg_direct_ewald_composite_simulation_v1 *simulation,
    const void *bytes,
    uint64_t size,
    const char *message) {
    const ParticleSnapshot before = snapshot_composite(simulation);
    const auto addresses = view_addresses(composite_view(simulation));
    require_status(
        bg_direct_ewald_composite_simulation_v1_checkpoint_load(
            simulation, bytes, size),
        BG_STATUS_INVALID_ARGUMENT,
        message);
    require_snapshot_exact(
        snapshot_composite(simulation),
        before,
        "failed composite checkpoint load changed state");
    require(
        view_addresses(composite_view(simulation)) == addresses,
        "failed composite checkpoint load changed view addresses");
}

void verify_checkpoint_format_failures_and_output_transactionality() {
    constexpr double timestep = 0.0005;
    const Fixture fixture;
    const SystemPtr system = make_system(fixture);
    const ForceFieldPtr forcefield = make_forcefield(fixture);
    const ModelPtr model = make_model(fixture);
    const ContextPtr context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    const CompositeSimulationPtr simulation = make_composite_simulation(
        system.get(), forcefield.get(), model.get(), timestep);
    integrate_success(context.get(), simulation.get(), UINT64_C(3));
    const std::vector<uint8_t> checkpoint =
        write_composite_checkpoint(simulation.get());
    require(
        checkpoint.size() == 104U + 6U * kAtomCount * sizeof(double),
        "composite checkpoint size did not match canonical payload");

    uint64_t scalar = UINT64_C(91);
    require_status(
        bg_direct_ewald_composite_simulation_v1_checkpoint_size(
            nullptr, &scalar),
        BG_STATUS_INVALID_ARGUMENT,
        "checkpoint-size query accepted null owner");
    require(scalar == UINT64_C(91), "failed size query changed output");
    require_status(
        bg_direct_ewald_composite_simulation_v1_checkpoint_size(
            simulation.get(), nullptr),
        BG_STATUS_INVALID_ARGUMENT,
        "checkpoint-size query accepted null output");
    const bg_particle_soa_view owner_view = composite_view(simulation.get());
    require_status(
        bg_direct_ewald_composite_simulation_v1_checkpoint_size(
            simulation.get(),
            reinterpret_cast<uint64_t *>(
                const_cast<double *>(owner_view.position_x_angstrom))),
        BG_STATUS_INVALID_ARGUMENT,
        "checkpoint-size output aliased owner state");

    std::vector<uint8_t> too_small(checkpoint.size() - 1U, UINT8_C(0x5a));
    const std::vector<uint8_t> too_small_before = too_small;
    uint64_t written = UINT64_C(77);
    require_status(
        bg_direct_ewald_composite_simulation_v1_checkpoint_write(
            simulation.get(),
            too_small.data(),
            too_small.size(),
            &written),
        BG_STATUS_BUFFER_TOO_SMALL,
        "checkpoint writer accepted a short buffer");
    require(
        too_small == too_small_before && written == UINT64_C(77),
        "short-buffer failure changed checkpoint outputs");
    require_status(
        bg_direct_ewald_composite_simulation_v1_checkpoint_write(
            simulation.get(),
            nullptr,
            checkpoint.size(),
            &written),
        BG_STATUS_INVALID_ARGUMENT,
        "checkpoint writer accepted null storage");
    require(written == UINT64_C(77), "null-buffer failure changed size output");
    require_status(
        bg_direct_ewald_composite_simulation_v1_checkpoint_write(
            nullptr,
            too_small.data(),
            too_small.size(),
            &written),
        BG_STATUS_INVALID_ARGUMENT,
        "checkpoint writer accepted null owner");
    require_status(
        bg_direct_ewald_composite_simulation_v1_checkpoint_write(
            simulation.get(),
            too_small.data(),
            too_small.size(),
            nullptr),
        BG_STATUS_INVALID_ARGUMENT,
        "checkpoint writer accepted null written-size output");

    std::vector<uint8_t> output(checkpoint.size(), UINT8_C(0x3c));
    const std::vector<uint8_t> output_before = output;
    require_status(
        bg_direct_ewald_composite_simulation_v1_checkpoint_write(
            simulation.get(),
            const_cast<double *>(owner_view.position_x_angstrom),
            checkpoint.size(),
            &written),
        BG_STATUS_INVALID_ARGUMENT,
        "checkpoint output aliased owner particle state");
    require(written == UINT64_C(77), "owner-alias failure changed size output");
    require_status(
        bg_direct_ewald_composite_simulation_v1_checkpoint_write(
            simulation.get(),
            output.data(),
            output.size(),
            reinterpret_cast<uint64_t *>(
                const_cast<double *>(owner_view.position_x_angstrom))),
        BG_STATUS_INVALID_ARGUMENT,
        "checkpoint size output aliased owner particle state");
    require(
        output == output_before,
        "checkpoint alias failure changed output bytes");

    std::vector<uint8_t> corrupt = checkpoint;
    corrupt.back() ^= UINT8_C(0x01);
    expect_composite_checkpoint_load_failure(
        simulation.get(),
        corrupt.data(),
        corrupt.size(),
        "composite checkpoint accepted corrupt bytes");
    expect_composite_checkpoint_load_failure(
        simulation.get(),
        checkpoint.data(),
        checkpoint.size() - 1U,
        "composite checkpoint accepted truncated bytes");
    std::vector<uint8_t> appended = checkpoint;
    appended.push_back(UINT8_C(0));
    expect_composite_checkpoint_load_failure(
        simulation.get(),
        appended.data(),
        appended.size(),
        "composite checkpoint accepted appended bytes");
    require_status(
        bg_direct_ewald_composite_simulation_v1_checkpoint_load(
            nullptr, checkpoint.data(), checkpoint.size()),
        BG_STATUS_INVALID_ARGUMENT,
        "checkpoint load accepted null owner");
    require_status(
        bg_direct_ewald_composite_simulation_v1_checkpoint_load(
            simulation.get(), nullptr, checkpoint.size()),
        BG_STATUS_INVALID_ARGUMENT,
        "checkpoint load accepted null input");

    const LegacySimulationPtr legacy = make_legacy_simulation(
        system.get(), forcefield.get(), timestep);
    const std::vector<uint8_t> legacy_checkpoint =
        write_legacy_checkpoint(legacy.get());
    constexpr std::array<uint8_t, 8> legacy_magic{{
        'B', 'G', 'D', 'Y', 'N', '0', '0', '1'}};
    constexpr std::array<uint8_t, 8> composite_magic{{
        'B', 'G', 'D', 'E', 'C', '0', '0', '1'}};
    require(
        std::equal(
            legacy_magic.begin(),
            legacy_magic.end(),
            legacy_checkpoint.begin()),
        "legacy checkpoint magic changed");
    require(
        std::equal(
            composite_magic.begin(),
            composite_magic.end(),
            checkpoint.begin()),
        "composite checkpoint magic changed");
    expect_composite_checkpoint_load_failure(
        simulation.get(),
        legacy_checkpoint.data(),
        legacy_checkpoint.size(),
        "composite loader accepted BGDYN001 bytes");
    const ParticleSnapshot legacy_before = snapshot_legacy(legacy.get());
    require_status(
        bg_simulation_checkpoint_load(
            legacy.get(), checkpoint.data(), checkpoint.size()),
        BG_STATUS_INVALID_ARGUMENT,
        "legacy loader accepted BGDEC001 bytes");
    require_snapshot_exact(
        snapshot_legacy(legacy.get()),
        legacy_before,
        "BGDEC001 rejection changed legacy state");
}

void verify_checkpoint_fingerprint_mismatches() {
    constexpr double timestep = 0.0005;
    const Fixture fixture;
    const SystemPtr system = make_system(fixture);
    const ForceFieldPtr forcefield = make_forcefield(fixture);
    const ModelPtr model = make_model(fixture);
    const CompositeSimulationPtr source = make_composite_simulation(
        system.get(), forcefield.get(), model.get(), timestep);
    const ContextPtr context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    integrate_success(context.get(), source.get(), UINT64_C(2));
    const std::vector<uint8_t> checkpoint =
        write_composite_checkpoint(source.get());

    ModelSettings changed_model_settings;
    changed_model_settings.alpha_per_angstrom = 0.32;
    const ModelPtr changed_model = make_model(fixture, changed_model_settings);
    const CompositeSimulationPtr changed_model_owner =
        make_composite_simulation(
            system.get(),
            forcefield.get(),
            changed_model.get(),
            timestep);
    expect_composite_checkpoint_load_failure(
        changed_model_owner.get(),
        checkpoint.data(),
        checkpoint.size(),
        "checkpoint accepted a changed Ewald model field");

    const CompositeSimulationPtr changed_timestep_owner =
        make_composite_simulation(
            system.get(), forcefield.get(), model.get(), timestep * 2.0);
    expect_composite_checkpoint_load_failure(
        changed_timestep_owner.get(),
        checkpoint.data(),
        checkpoint.size(),
        "checkpoint accepted a changed timestep");

    const ForceFieldPtr explicit_zero_forcefield = make_forcefield(
        fixture, PairProvenance::explicit_zero_scale);
    ModelSettings explicit_zero_settings;
    explicit_zero_settings.provenance =
        PairProvenance::explicit_zero_scale;
    const ModelPtr explicit_zero_model = make_model(
        fixture, explicit_zero_settings);
    const CompositeSimulationPtr explicit_zero_owner =
        make_composite_simulation(
            system.get(),
            explicit_zero_forcefield.get(),
            explicit_zero_model.get(),
            timestep);
    expect_composite_checkpoint_load_failure(
        explicit_zero_owner.get(),
        checkpoint.data(),
        checkpoint.size(),
        "checkpoint accepted explicit-zero in place of exclusion provenance");
}

}  // namespace

int main() {
    verify_abi_profile_and_descriptor_transactionality();
    verify_deep_ownership_and_stable_views();
    verify_zero_step_matches_stateless();
    verify_manual_velocity_verlet_and_same_lane_repeat();
    verify_checkpoint_continuation_and_small_nve();
    verify_baoab_hip_and_step_overflow_fail_closed();
    verify_late_typed_ewald_failure_rolls_back();
    verify_checkpoint_format_failures_and_output_transactionality();
    verify_checkpoint_fingerprint_mismatches();
    return 0;
}
