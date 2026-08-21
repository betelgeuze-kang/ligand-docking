#include "betelgeuze/engine.h"
#include "../src/internal.hpp"

#include <array>
#include <cassert>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <vector>

#ifndef BG_TEST_HIP_ENABLED
#define BG_TEST_HIP_ENABLED 0
#endif

namespace {

struct NativeHandles final {
    bg_context *context = nullptr;
    bg_system *system = nullptr;
    bg_forcefield *forcefield = nullptr;
    bg_simulation *simulation = nullptr;

    NativeHandles() = default;
    NativeHandles(const NativeHandles &) = delete;
    NativeHandles &operator=(const NativeHandles &) = delete;

    ~NativeHandles() {
        bg_simulation_destroy(simulation);
        bg_forcefield_destroy(forcefield);
        bg_system_destroy(system);
        bg_context_destroy(context);
    }
};

bg_context *make_context(bg_backend backend) {
    bg_context_options options;
    assert(bg_context_options_init(&options) == BG_STATUS_OK);
    options.backend = backend;
    bg_context *context = nullptr;
    assert(bg_context_create(&options, &context) == BG_STATUS_OK);
    assert(context != nullptr);
    return context;
}

bg_system *make_system(
    const std::vector<double> &position_x,
    const std::vector<double> &position_y,
    const std::vector<double> &position_z,
    const std::vector<double> &velocity_x,
    const std::vector<double> &velocity_y,
    const std::vector<double> &velocity_z,
    const std::vector<double> &mass) {
    const std::size_t count = position_x.size();
    assert(count > 0);
    assert(position_y.size() == count && position_z.size() == count);
    assert(velocity_x.size() == count && velocity_y.size() == count &&
           velocity_z.size() == count && mass.size() == count);
    const std::vector<double> charge(count, 0.0);
    bg_particle_soa particles;
    assert(bg_particle_soa_init(&particles) == BG_STATUS_OK);
    particles.particle_count = static_cast<uint64_t>(count);
    particles.position_x_angstrom = position_x.data();
    particles.position_y_angstrom = position_y.data();
    particles.position_z_angstrom = position_z.data();
    particles.velocity_x_angstrom_per_femtosecond = velocity_x.data();
    particles.velocity_y_angstrom_per_femtosecond = velocity_y.data();
    particles.velocity_z_angstrom_per_femtosecond = velocity_z.data();
    particles.mass_dalton = mass.data();
    particles.charge_elementary = charge.data();
    bg_system *system = nullptr;
    assert(bg_system_create(&particles, &system) == BG_STATUS_OK);
    return system;
}

bg_forcefield *make_forcefield(
    std::size_t atom_count,
    double bond_equilibrium,
    double bond_force_constant,
    bool periodic) {
    assert(atom_count > 0);
    const std::vector<double> sigma(atom_count, 1.0);
    const std::vector<double> epsilon(atom_count, 0.0);
    const uint64_t bond_i = UINT64_C(0);
    const uint64_t bond_j = UINT64_C(1);
    const uint64_t exclusion_i = UINT64_C(0);
    const uint64_t exclusion_j = UINT64_C(1);
    bg_forcefield_soa_v1 descriptor;
    assert(bg_forcefield_soa_v1_init(&descriptor) == BG_STATUS_OK);
    descriptor.atom_count = static_cast<uint64_t>(atom_count);
    descriptor.sigma_angstrom = sigma.data();
    descriptor.epsilon_kcal_per_mol = epsilon.data();
    if (bond_force_constant > 0.0) {
        assert(atom_count >= 2U);
        descriptor.bond_count = UINT64_C(1);
        descriptor.bond_atom_i = &bond_i;
        descriptor.bond_atom_j = &bond_j;
        descriptor.bond_equilibrium_angstrom = &bond_equilibrium;
        descriptor.bond_force_constant_kcal_per_mol_angstrom2 =
            &bond_force_constant;
    }
    if (atom_count == 2U) {
        descriptor.exclusion_count = UINT64_C(1);
        descriptor.exclusion_atom_i = &exclusion_i;
        descriptor.exclusion_atom_j = &exclusion_j;
    }
    if (periodic) {
        descriptor.periodic_axes_mask = BG_PERIODIC_AXES_ALL;
        descriptor.cell_lengths_angstrom[0] = 10.0;
        descriptor.cell_lengths_angstrom[1] = 10.0;
        descriptor.cell_lengths_angstrom[2] = 10.0;
        descriptor.cutoff_angstrom = 4.0;
        descriptor.switch_start_angstrom = 3.0;
    }
    bg_forcefield *forcefield = nullptr;
    assert(bg_forcefield_create(&descriptor, &forcefield) == BG_STATUS_OK);
    return forcefield;
}

bg_forcefield *make_rotating_constraint_forcefield() {
    const std::array<double, 3> sigma = {1.0, 1.0, 1.0};
    const std::array<double, 3> epsilon = {0.0, 0.0, 0.0};
    const uint64_t bond_i = UINT64_C(1);
    const uint64_t bond_j = UINT64_C(2);
    const double equilibrium = 1.0;
    const double force_constant = 20.0;
    const std::array<uint64_t, 3> exclusion_i = {
        UINT64_C(0), UINT64_C(0), UINT64_C(1)};
    const std::array<uint64_t, 3> exclusion_j = {
        UINT64_C(1), UINT64_C(2), UINT64_C(2)};
    bg_forcefield_soa_v1 descriptor;
    assert(bg_forcefield_soa_v1_init(&descriptor) == BG_STATUS_OK);
    descriptor.atom_count = UINT64_C(3);
    descriptor.sigma_angstrom = sigma.data();
    descriptor.epsilon_kcal_per_mol = epsilon.data();
    descriptor.bond_count = UINT64_C(1);
    descriptor.bond_atom_i = &bond_i;
    descriptor.bond_atom_j = &bond_j;
    descriptor.bond_equilibrium_angstrom = &equilibrium;
    descriptor.bond_force_constant_kcal_per_mol_angstrom2 = &force_constant;
    descriptor.exclusion_count = UINT64_C(3);
    descriptor.exclusion_atom_i = exclusion_i.data();
    descriptor.exclusion_atom_j = exclusion_j.data();
    bg_forcefield *forcefield = nullptr;
    assert(bg_forcefield_create(&descriptor, &forcefield) == BG_STATUS_OK);
    return forcefield;
}

bg_forcefield *make_periodic_nonbonded_forcefield(std::size_t atom_count) {
    const std::vector<double> sigma(atom_count, 1.5);
    const std::vector<double> epsilon(atom_count, 0.05);
    bg_forcefield_soa_v1 descriptor;
    assert(bg_forcefield_soa_v1_init(&descriptor) == BG_STATUS_OK);
    descriptor.atom_count = static_cast<uint64_t>(atom_count);
    descriptor.sigma_angstrom = sigma.data();
    descriptor.epsilon_kcal_per_mol = epsilon.data();
    descriptor.periodic_axes_mask = BG_PERIODIC_AXES_ALL;
    descriptor.cell_lengths_angstrom[0] = 10.0;
    descriptor.cell_lengths_angstrom[1] = 10.0;
    descriptor.cell_lengths_angstrom[2] = 10.0;
    descriptor.cutoff_angstrom = 4.0;
    descriptor.switch_start_angstrom = 3.0;
    bg_forcefield *forcefield = nullptr;
    assert(bg_forcefield_create(&descriptor, &forcefield) == BG_STATUS_OK);
    return forcefield;
}

bg_simulation *make_simulation(
    const bg_system *system,
    const bg_forcefield *forcefield,
    bg_integrator integrator,
    double timestep,
    double temperature,
    double friction,
    uint64_t seed,
    const bg_distance_constraints_v1 *constraints) {
    bg_simulation_options_v1 options;
    assert(bg_simulation_options_v1_init(&options) == BG_STATUS_OK);
    options.integrator = integrator;
    options.timestep_femtoseconds = timestep;
    options.temperature_kelvin = temperature;
    options.friction_per_femtosecond = friction;
    options.random_seed = seed;
    bg_simulation *simulation = nullptr;
    assert(bg_simulation_create(
               system, forcefield, constraints, &options, &simulation) ==
           BG_STATUS_OK);
    return simulation;
}

bg_particle_soa_view particle_view(const bg_simulation *simulation) {
    bg_particle_soa_view view;
    assert(bg_particle_soa_view_init(&view) == BG_STATUS_OK);
    assert(bg_simulation_get_particles(simulation, &view) == BG_STATUS_OK);
    return view;
}

std::array<const double *, 8> particle_addresses(
    const bg_particle_soa_view &view) {
    return {
        view.position_x_angstrom,
        view.position_y_angstrom,
        view.position_z_angstrom,
        view.velocity_x_angstrom_per_femtosecond,
        view.velocity_y_angstrom_per_femtosecond,
        view.velocity_z_angstrom_per_femtosecond,
        view.mass_dalton,
        view.charge_elementary,
    };
}

std::array<const double *, 6> dynamic_rollback_scratch_addresses(
    const bg_simulation *simulation) {
    const bg_simulation::DynamicStateScratch &scratch =
        simulation->dynamic_state_scratch;
    return {
        scratch.position_x.data(),
        scratch.position_y.data(),
        scratch.position_z.data(),
        scratch.velocity_x.data(),
        scratch.velocity_y.data(),
        scratch.velocity_z.data(),
    };
}

bg_dynamics_report_v1 integrate(
    const bg_context *context,
    bg_simulation *simulation,
    uint64_t count) {
    bg_dynamics_report_v1 report;
    assert(bg_dynamics_report_v1_init(&report) == BG_STATUS_OK);
    assert(bg_context_integrate(context, simulation, count, &report) ==
           BG_STATUS_OK);
    return report;
}

bool same_bits(double left, double right) {
    static_assert(sizeof(left) == sizeof(uint64_t));
    uint64_t left_bits = UINT64_C(0);
    uint64_t right_bits = UINT64_C(0);
    std::memcpy(&left_bits, &left, sizeof(left));
    std::memcpy(&right_bits, &right, sizeof(right));
    return left_bits == right_bits;
}

void assert_same_dynamic_state(
    const bg_simulation *left,
    const bg_simulation *right) {
    const bg_particle_soa_view a = particle_view(left);
    const bg_particle_soa_view b = particle_view(right);
    assert(a.particle_count == b.particle_count);
    const double *const a_channels[] = {
        a.position_x_angstrom,
        a.position_y_angstrom,
        a.position_z_angstrom,
        a.velocity_x_angstrom_per_femtosecond,
        a.velocity_y_angstrom_per_femtosecond,
        a.velocity_z_angstrom_per_femtosecond,
    };
    const double *const b_channels[] = {
        b.position_x_angstrom,
        b.position_y_angstrom,
        b.position_z_angstrom,
        b.velocity_x_angstrom_per_femtosecond,
        b.velocity_y_angstrom_per_femtosecond,
        b.velocity_z_angstrom_per_femtosecond,
    };
    for (std::size_t channel = 0; channel < 6U; ++channel) {
        for (uint64_t atom = UINT64_C(0); atom < a.particle_count; ++atom) {
            const std::size_t index = static_cast<std::size_t>(atom);
            assert(same_bits(a_channels[channel][index],
                             b_channels[channel][index]));
        }
    }
    uint64_t a_step = UINT64_C(0);
    uint64_t b_step = UINT64_C(0);
    assert(bg_simulation_get_absolute_step(left, &a_step) == BG_STATUS_OK);
    assert(bg_simulation_get_absolute_step(right, &b_step) == BG_STATUS_OK);
    assert(a_step == b_step);
}

void test_initializers_and_invalid_rows() {
    assert(bg_abi_version_minor() == UINT32_C(21));
    bg_distance_constraints_v1 constraints;
    assert(bg_distance_constraints_v1_init(&constraints) == BG_STATUS_OK);
    assert(constraints.tolerance_angstrom > 0.0);
    assert(constraints.velocity_tolerance_angstrom_per_femtosecond > 0.0);
    bg_simulation_options_v1 options;
    assert(bg_simulation_options_v1_init(&options) == BG_STATUS_OK);
    options.timestep_femtoseconds = std::numeric_limits<double>::denorm_min();

    NativeHandles handles;
    handles.system = make_system(
        {0.0, 1.0}, {0.0, 0.0}, {0.0, 0.0},
        {0.0, 0.0}, {0.0, 0.0}, {0.0, 0.0}, {1.0, 1.0});
    handles.forcefield = make_forcefield(2U, 1.0, 20.0, false);
    bg_simulation *simulation = reinterpret_cast<bg_simulation *>(
        static_cast<std::uintptr_t>(UINTPTR_MAX));
    assert(bg_simulation_create(
               handles.system, handles.forcefield, nullptr, &options,
               &simulation) == BG_STATUS_INVALID_ARGUMENT);
    assert(simulation == nullptr);

    const std::array<uint64_t, 2> atom_i = {UINT64_C(0), UINT64_C(1)};
    const std::array<uint64_t, 2> atom_j = {UINT64_C(1), UINT64_C(0)};
    const std::array<double, 2> distance = {1.0, 1.0};
    assert(bg_distance_constraints_v1_init(&constraints) == BG_STATUS_OK);
    constraints.constraint_count = UINT64_C(2);
    constraints.atom_i = atom_i.data();
    constraints.atom_j = atom_j.data();
    constraints.distance_angstrom = distance.data();
    assert(bg_simulation_options_v1_init(&options) == BG_STATUS_OK);
    assert(bg_simulation_create(
               handles.system, handles.forcefield, &constraints, &options,
               &simulation) == BG_STATUS_INVALID_ARGUMENT);

    NativeHandles dependent;
    dependent.system = make_system(
        {0.0, 1.0, 2.0}, {0.0, 0.0, 0.0}, {0.0, 0.0, 0.0},
        {0.0, 0.0, 0.0}, {0.0, 0.0, 0.0}, {0.0, 0.0, 0.0},
        {1.0, 1.0, 1.0});
    dependent.forcefield = make_forcefield(3U, 1.0, 0.0, false);
    const std::array<uint64_t, 3> dependent_i = {
        UINT64_C(0), UINT64_C(1), UINT64_C(0)};
    const std::array<uint64_t, 3> dependent_j = {
        UINT64_C(1), UINT64_C(2), UINT64_C(2)};
    const std::array<double, 3> dependent_distance = {1.0, 1.0, 2.0};
    assert(bg_distance_constraints_v1_init(&constraints) == BG_STATUS_OK);
    constraints.constraint_count = UINT64_C(3);
    constraints.atom_i = dependent_i.data();
    constraints.atom_j = dependent_j.data();
    constraints.distance_angstrom = dependent_distance.data();
    assert(bg_simulation_create(
               dependent.system, dependent.forcefield, &constraints, &options,
               &simulation) == BG_STATUS_INVALID_ARGUMENT);
    assert(simulation == nullptr);
    assert(simulation == nullptr);

    const uint64_t self = UINT64_C(0);
    constraints.constraint_count = UINT64_C(1);
    constraints.atom_i = &self;
    constraints.atom_j = &self;
    constraints.distance_angstrom = distance.data();
    assert(bg_simulation_create(
               handles.system, handles.forcefield, &constraints, &options,
               &simulation) == BG_STATUS_INVALID_ARGUMENT);
}

void test_minimizer_and_transactionality() {
    NativeHandles handles;
    handles.context = make_context(BG_BACKEND_CPU);
    handles.system = make_system(
        {0.0, 1.5}, {0.0, 0.0}, {0.0, 0.0},
        {0.25, -0.125}, {0.0, 0.0}, {0.0, 0.0}, {12.0, 16.0});
    handles.forcefield = make_forcefield(2U, 1.0, 20.0, false);
    handles.simulation = make_simulation(
        handles.system, handles.forcefield, BG_INTEGRATOR_VELOCITY_VERLET,
        0.2, 0.0, 0.0, UINT64_C(0), nullptr);
    const bg_particle_soa_view before = particle_view(handles.simulation);
    const auto addresses = particle_addresses(before);
    const std::array<double, 2> velocities = {
        before.velocity_x_angstrom_per_femtosecond[0],
        before.velocity_x_angstrom_per_femtosecond[1]};

    bg_minimizer_options_v1 options;
    assert(bg_minimizer_options_v1_init(&options) == BG_STATUS_OK);
    options.max_iterations = UINT64_C(100);
    options.initial_step_angstrom2_mol_per_kcal = 0.02;
    options.energy_tolerance_kcal_per_mol = 0.0;
    options.force_tolerance_kcal_per_mol_angstrom = 1.0e-10;
    bg_minimization_report_v1 report;
    assert(bg_minimization_report_v1_init(&report) == BG_STATUS_OK);
    assert(bg_context_minimize(
               handles.context, handles.simulation, &options, &report) ==
           BG_STATUS_OK);
    assert(report.converged == UINT32_C(1));
    assert(report.initial_potential_kcal_per_mol == 2.5);
    assert(report.final_potential_kcal_per_mol < 1.0e-20);
    assert(report.maximum_force_kcal_per_mol_angstrom <= 1.0e-10);
    const bg_particle_soa_view after = particle_view(handles.simulation);
    assert(particle_addresses(after) == addresses);
    const auto rollback_scratch_addresses =
        dynamic_rollback_scratch_addresses(handles.simulation);
    for (const double *address : rollback_scratch_addresses) {
        assert(address != nullptr);
    }
    assert(after.velocity_x_angstrom_per_femtosecond[0] == velocities[0]);
    assert(after.velocity_x_angstrom_per_femtosecond[1] == velocities[1]);
    uint64_t step = UINT64_C(99);
    assert(bg_simulation_get_absolute_step(handles.simulation, &step) ==
           BG_STATUS_OK);
    assert(step == UINT64_C(0));

    const std::array<double, 2> positions = {
        after.position_x_angstrom[0], after.position_x_angstrom[1]};
    options.max_line_search_steps = UINT32_C(1);
    options.initial_step_angstrom2_mol_per_kcal = 1.0e12;
    options.minimum_step_angstrom2_mol_per_kcal = 1.0e12;
    options.force_tolerance_kcal_per_mol_angstrom = 0.0;
    bg_minimization_report_v1 failed_report;
    assert(bg_minimization_report_v1_init(&failed_report) == BG_STATUS_OK);
    failed_report.iterations = UINT64_C(777);
    const bg_minimization_report_v1 failed_snapshot = failed_report;
    assert(bg_context_minimize(
               handles.context, handles.simulation, &options,
               &failed_report) == BG_STATUS_NUMERICAL_ERROR);
    assert(std::memcmp(
               &failed_report, &failed_snapshot, sizeof(failed_report)) == 0);
    const bg_particle_soa_view failed_view = particle_view(handles.simulation);
    assert(particle_addresses(failed_view) == addresses);
    assert(dynamic_rollback_scratch_addresses(handles.simulation) ==
           rollback_scratch_addresses);
    assert(failed_view.position_x_angstrom[0] == positions[0]);
    assert(failed_view.position_x_angstrom[1] == positions[1]);

    NativeHandles recovered;
    recovered.context = make_context(BG_BACKEND_CPU);
    recovered.system = make_system(
        {0.0, 1.5}, {0.0, 0.0}, {0.0, 0.0},
        {0.0, 0.0}, {0.0, 0.0}, {0.0, 0.0}, {12.0, 16.0});
    recovered.forcefield = make_forcefield(2U, 1.0, 20.0, false);
    recovered.simulation = make_simulation(
        recovered.system, recovered.forcefield,
        BG_INTEGRATOR_VELOCITY_VERLET, 0.1, 0.0, 0.0, UINT64_C(0),
        nullptr);
    assert(bg_minimizer_options_v1_init(&options) == BG_STATUS_OK);
    options.max_iterations = UINT64_C(1);
    options.max_line_search_steps = UINT32_C(300);
    options.initial_step_angstrom2_mol_per_kcal = 1.0e200;
    options.minimum_step_angstrom2_mol_per_kcal = 1.0e-12;
    options.backtrack_factor = 0.1;
    options.energy_tolerance_kcal_per_mol = 0.0;
    options.force_tolerance_kcal_per_mol_angstrom = 0.0;
    assert(bg_minimization_report_v1_init(&report) == BG_STATUS_OK);
    const auto recovered_addresses =
        particle_addresses(particle_view(recovered.simulation));
    assert(bg_context_minimize(
               recovered.context, recovered.simulation, &options, &report) ==
           BG_STATUS_OK);
    assert(particle_addresses(particle_view(recovered.simulation)) ==
           recovered_addresses);
    assert(std::strlen(bg_last_error_message()) == 0U);
}

void test_constraints_and_periodic_images() {
    NativeHandles handles;
    handles.context = make_context(BG_BACKEND_CPU);
    handles.system = make_system(
        {-0.8, 0.8}, {0.0, 0.0}, {0.0, 0.0},
        {1.0, -1.0}, {0.0, 0.0}, {0.0, 0.0}, {1.0, 3.0});
    handles.forcefield = make_forcefield(2U, 1.0, 20.0, false);
    const uint64_t atom_i = UINT64_C(0);
    const uint64_t atom_j = UINT64_C(1);
    const double target = 1.0;
    bg_distance_constraints_v1 constraints;
    assert(bg_distance_constraints_v1_init(&constraints) == BG_STATUS_OK);
    constraints.constraint_count = UINT64_C(1);
    constraints.atom_i = &atom_i;
    constraints.atom_j = &atom_j;
    constraints.distance_angstrom = &target;
    constraints.tolerance_angstrom = 1.0e-12;
    constraints.velocity_tolerance_angstrom_per_femtosecond = 1.0e-12;
    constraints.max_iterations = UINT32_C(1);
    handles.simulation = make_simulation(
        handles.system, handles.forcefield, BG_INTEGRATOR_VELOCITY_VERLET,
        0.1, 0.0, 0.0, UINT64_C(0), &constraints);
    bg_particle_soa_view view = particle_view(handles.simulation);
    assert(std::abs(
               std::abs(view.position_x_angstrom[0] -
                        view.position_x_angstrom[1]) -
               target) <= 1.0e-12);
    assert(std::abs(
               view.velocity_x_angstrom_per_femtosecond[0] -
               view.velocity_x_angstrom_per_femtosecond[1]) <= 1.0e-12);
    const double *const address = view.position_x_angstrom;
    const bg_dynamics_report_v1 report =
        integrate(handles.context, handles.simulation, UINT64_C(100));
    assert(report.degrees_of_freedom == UINT64_C(5));
    view = particle_view(handles.simulation);
    assert(view.position_x_angstrom == address);
    assert(std::abs(
               std::abs(view.position_x_angstrom[0] -
                        view.position_x_angstrom[1]) -
               target) <= 1.0e-12);

    NativeHandles periodic;
    periodic.system = make_system(
        {0.1, 9.0}, {0.0, 0.0}, {0.0, 0.0},
        {0.0, 0.0}, {0.0, 0.0}, {0.0, 0.0}, {1.0, 2.0});
    periodic.forcefield = make_forcefield(2U, 1.1, 20.0, true);
    const double periodic_target = 1.1;
    constraints.distance_angstrom = &periodic_target;
    constraints.max_iterations = UINT32_C(10);
    periodic.simulation = make_simulation(
        periodic.system, periodic.forcefield, BG_INTEGRATOR_VELOCITY_VERLET,
        0.1, 0.0, 0.0, UINT64_C(0), &constraints);
    const bg_particle_soa_view periodic_view =
        particle_view(periodic.simulation);
    double displacement = periodic_view.position_x_angstrom[0] -
                          periodic_view.position_x_angstrom[1];
    displacement -= 10.0 * std::floor(displacement / 10.0 + 0.5);
    assert(std::abs(std::abs(displacement) - periodic_target) <= 1.0e-12);

    bg_simulation_options_v1 simulation_options;
    assert(bg_simulation_options_v1_init(&simulation_options) == BG_STATUS_OK);
    const double invalid_target = 5.0;
    constraints.distance_angstrom = &invalid_target;
    bg_simulation *invalid = nullptr;
    assert(bg_simulation_create(
               periodic.system, periodic.forcefield, &constraints,
               &simulation_options, &invalid) == BG_STATUS_INVALID_ARGUMENT);
    assert(invalid == nullptr);
}

void test_constrained_minimizer_rattle_checkpoint() {
    NativeHandles first;
    first.context = make_context(BG_BACKEND_CPU);
    first.system = make_system(
        {0.0, 1.0, 1.0}, {0.0, 0.0, 1.5}, {0.0, 0.0, 0.0},
        {0.0, 0.0, 0.0}, {1.0, -1.0, 0.0}, {0.0, 0.0, 0.0},
        {1.0, 3.0, 2.0});
    first.forcefield = make_rotating_constraint_forcefield();
    const uint64_t atom_i = UINT64_C(0);
    const uint64_t atom_j = UINT64_C(1);
    const double target = 1.0;
    bg_distance_constraints_v1 constraints;
    assert(bg_distance_constraints_v1_init(&constraints) == BG_STATUS_OK);
    constraints.constraint_count = UINT64_C(1);
    constraints.atom_i = &atom_i;
    constraints.atom_j = &atom_j;
    constraints.distance_angstrom = &target;
    constraints.tolerance_angstrom = 1.0e-10;
    constraints.velocity_tolerance_angstrom_per_femtosecond = 1.0e-10;
    constraints.max_iterations = UINT32_C(100);
    first.simulation = make_simulation(
        first.system, first.forcefield, BG_INTEGRATOR_VELOCITY_VERLET,
        0.1, 0.0, 0.0, UINT64_C(0), &constraints);
    const bg_particle_soa_view initial = particle_view(first.simulation);
    const std::array<double, 2> initial_velocity_y = {
        initial.velocity_y_angstrom_per_femtosecond[0],
        initial.velocity_y_angstrom_per_femtosecond[1]};
    bg_minimizer_options_v1 options;
    assert(bg_minimizer_options_v1_init(&options) == BG_STATUS_OK);
    options.max_iterations = UINT64_C(200);
    options.initial_step_angstrom2_mol_per_kcal = 0.01;
    options.energy_tolerance_kcal_per_mol = 1.0e-14;
    options.force_tolerance_kcal_per_mol_angstrom = 1.0e-9;
    bg_minimization_report_v1 report;
    assert(bg_minimization_report_v1_init(&report) == BG_STATUS_OK);
    assert(bg_context_minimize(
               first.context, first.simulation, &options, &report) ==
           BG_STATUS_OK);
    assert(report.converged == UINT32_C(1));
    const bg_particle_soa_view minimized = particle_view(first.simulation);
    const double dx = minimized.position_x_angstrom[0] -
                      minimized.position_x_angstrom[1];
    const double dy = minimized.position_y_angstrom[0] -
                      minimized.position_y_angstrom[1];
    const double dvx = minimized.velocity_x_angstrom_per_femtosecond[0] -
                       minimized.velocity_x_angstrom_per_femtosecond[1];
    const double dvy = minimized.velocity_y_angstrom_per_femtosecond[0] -
                       minimized.velocity_y_angstrom_per_femtosecond[1];
    assert(std::abs(std::hypot(dx, dy) - target) <= 1.0e-10);
    assert(std::abs((dx * dvx + dy * dvy) / std::hypot(dx, dy)) <=
           1.0e-10);
    assert(minimized.velocity_y_angstrom_per_femtosecond[0] !=
               initial_velocity_y[0] ||
           minimized.velocity_y_angstrom_per_femtosecond[1] !=
               initial_velocity_y[1]);

    uint64_t size = UINT64_C(0);
    assert(bg_simulation_checkpoint_size(first.simulation, &size) ==
           BG_STATUS_OK);
    std::vector<uint8_t> checkpoint(static_cast<std::size_t>(size));
    uint64_t written = UINT64_C(0);
    assert(bg_simulation_checkpoint_write(
               first.simulation, checkpoint.data(), size, &written) ==
           BG_STATUS_OK);
    NativeHandles second;
    second.system = make_system(
        {0.0, 1.0, 1.0}, {0.0, 0.0, 1.5}, {0.0, 0.0, 0.0},
        {0.0, 0.0, 0.0}, {1.0, -1.0, 0.0}, {0.0, 0.0, 0.0},
        {1.0, 3.0, 2.0});
    second.forcefield = make_rotating_constraint_forcefield();
    second.simulation = make_simulation(
        second.system, second.forcefield, BG_INTEGRATOR_VELOCITY_VERLET,
        0.1, 0.0, 0.0, UINT64_C(0), &constraints);
    assert(bg_simulation_checkpoint_load(
               second.simulation, checkpoint.data(), size) == BG_STATUS_OK);
    assert_same_dynamic_state(first.simulation, second.simulation);
}

void test_nve_fixture_and_zero_step() {
    NativeHandles first;
    first.context = make_context(BG_BACKEND_CPU);
    first.system = make_system(
        {-0.6, 0.6}, {0.0, 0.0}, {0.0, 0.0},
        {0.001, -0.001}, {0.0, 0.0}, {0.0, 0.0}, {12.0, 16.0});
    first.forcefield = make_forcefield(2U, 1.0, 20.0, false);
    first.simulation = make_simulation(
        first.system, first.forcefield, BG_INTEGRATOR_VELOCITY_VERLET,
        0.2, 999.0, 5.0, UINT64_C(123), nullptr);
    const bg_particle_soa_view initial_view = particle_view(first.simulation);
    const std::array<double, 4> initial_state = {
        initial_view.position_x_angstrom[0],
        initial_view.position_x_angstrom[1],
        initial_view.velocity_x_angstrom_per_femtosecond[0],
        initial_view.velocity_x_angstrom_per_femtosecond[1],
    };
    const auto initial_addresses = particle_addresses(initial_view);
    const bg_dynamics_report_v1 initial_report =
        integrate(first.context, first.simulation, UINT64_C(0));
    assert(initial_report.steps_completed == UINT64_C(0));
    assert(initial_report.absolute_step == UINT64_C(0));
    const bg_particle_soa_view zero_view = particle_view(first.simulation);
    assert(particle_addresses(zero_view) == initial_addresses);
    assert(zero_view.position_x_angstrom[0] == initial_state[0]);
    assert(zero_view.position_x_angstrom[1] == initial_state[1]);
    assert(zero_view.velocity_x_angstrom_per_femtosecond[0] == initial_state[2]);
    assert(zero_view.velocity_x_angstrom_per_femtosecond[1] == initial_state[3]);

    NativeHandles second;
    second.system = make_system(
        {-0.6, 0.6}, {0.0, 0.0}, {0.0, 0.0},
        {0.001, -0.001}, {0.0, 0.0}, {0.0, 0.0}, {12.0, 16.0});
    second.forcefield = make_forcefield(2U, 1.0, 20.0, false);
    second.simulation = make_simulation(
        second.system, second.forcefield, BG_INTEGRATOR_VELOCITY_VERLET,
        0.2, 0.0, 0.0, UINT64_C(0), nullptr);
    const bg_dynamics_report_v1 first_report =
        integrate(first.context, first.simulation, UINT64_C(1000));
    const bg_dynamics_report_v1 second_report =
        integrate(first.context, second.simulation, UINT64_C(1000));
    assert_same_dynamic_state(first.simulation, second.simulation);
    assert(same_bits(first_report.total_kcal_per_mol,
                     second_report.total_kcal_per_mol));
    assert(std::abs(first_report.total_kcal_per_mol -
                    initial_report.total_kcal_per_mol) < 1.0e-5);
    assert(first_report.absolute_step == UINT64_C(1000));
    const bg_particle_soa_view frozen_nve = particle_view(first.simulation);
    assert(particle_addresses(frozen_nve) == initial_addresses);
    assert(frozen_nve.position_x_angstrom[0] == -0x1.2919f91fb7dfbp-1);
    assert(frozen_nve.position_x_angstrom[1] == 0x1.1206ae0afd1abp-1);
    assert(frozen_nve.velocity_x_angstrom_per_femtosecond[0] ==
           0x1.b202c75245288p-9);
    assert(frozen_nve.velocity_x_angstrom_per_femtosecond[1] ==
           -0x1.6646b12397327p-9);
    assert(first_report.potential_kcal_per_mol == 0x1.1121585e111cp-3);
    assert(first_report.kinetic_kcal_per_mol == 0x1.334b9f89504e4p-2);
    assert(first_report.total_kcal_per_mol == 0x1.bbdc4bb858dc4p-2);
    assert(first_report.temperature_kelvin == 0x1.92b35dc301dafp+5);
}

void test_nvt_fixture_and_checkpoint() {
    NativeHandles first;
    first.context = make_context(BG_BACKEND_CPU);
    first.system = make_system(
        {-2.0, 2.0}, {0.0, 0.0}, {0.0, 0.0},
        {0.0, 0.0}, {0.0, 0.0}, {0.0, 0.0}, {12.0, 16.0});
    first.forcefield = make_forcefield(2U, 1.0, 0.0, false);
    constexpr uint64_t seed = UINT64_C(0x0123456789abcdef);
    first.simulation = make_simulation(
        first.system, first.forcefield, BG_INTEGRATOR_LANGEVIN_BAOAB,
        1.0, 300.0, 0.05, seed, nullptr);
    const bg_dynamics_report_v1 one_step =
        integrate(first.context, first.simulation, UINT64_C(1));
    assert(one_step.absolute_step == UINT64_C(1));
    assert(one_step.degrees_of_freedom == UINT64_C(6));
    assert(one_step.potential_kcal_per_mol == 0.0);
    assert(one_step.temperature_kelvin > 0.0);
    const bg_particle_soa_view frozen_nvt = particle_view(first.simulation);
    assert(frozen_nvt.position_x_angstrom[0] == -0x1.fffaed6632ca8p+0);
    assert(frozen_nvt.position_x_angstrom[1] == 0x1.fff8bcbcd7f75p+0);
    assert(frozen_nvt.velocity_x_angstrom_per_femtosecond[0] ==
           0x1.44a6734d5ed13p-13);
    assert(frozen_nvt.velocity_x_angstrom_per_femtosecond[1] ==
           -0x1.d0d0ca022a9fp-13);
    assert(frozen_nvt.velocity_y_angstrom_per_femtosecond[0] ==
           -0x1.28180858742ep-10);
    assert(frozen_nvt.velocity_y_angstrom_per_femtosecond[1] ==
           0x1.ef01d3763d5dfp-14);
    assert(one_step.kinetic_kcal_per_mol == 0x1.acf708db57a01p-3);
    assert(one_step.temperature_kelvin == 0x1.191284d3b64fp+5);

    NativeHandles replica;
    replica.system = make_system(
        {-2.0, 2.0}, {0.0, 0.0}, {0.0, 0.0},
        {0.0, 0.0}, {0.0, 0.0}, {0.0, 0.0}, {12.0, 16.0});
    replica.forcefield = make_forcefield(2U, 1.0, 0.0, false);
    replica.simulation = make_simulation(
        replica.system, replica.forcefield, BG_INTEGRATOR_LANGEVIN_BAOAB,
        1.0, 300.0, 0.05, seed, nullptr);
    integrate(first.context, replica.simulation, UINT64_C(1));
    assert_same_dynamic_state(first.simulation, replica.simulation);

    uint64_t checkpoint_size = UINT64_C(0);
    assert(bg_simulation_checkpoint_size(
               first.simulation, &checkpoint_size) == BG_STATUS_OK);
    std::vector<uint8_t> checkpoint(
        static_cast<std::size_t>(checkpoint_size), UINT8_C(0));
    uint64_t written = UINT64_C(0);
    assert(bg_simulation_checkpoint_write(
               first.simulation, checkpoint.data(), checkpoint_size,
               &written) == BG_STATUS_OK);
    assert(written == checkpoint_size);
    assert(checkpoint_size == UINT64_C(200));
    assert(checkpoint[32] == UINT8_C(1));
    constexpr std::array<uint8_t, 32> expected_nvt_fingerprint = {
        0x32, 0xe0, 0xf1, 0x8a, 0x09, 0x08, 0xad, 0xa3,
        0xb4, 0xb1, 0x07, 0x58, 0x6a, 0x4c, 0x8b, 0xd3,
        0x37, 0x7a, 0xca, 0x9a, 0x4b, 0x74, 0x59, 0xb2,
        0xac, 0xbf, 0x9b, 0x07, 0x11, 0xcc, 0xab, 0x85,
    };
    constexpr std::array<uint8_t, 32> expected_nvt_digest = {
        0x78, 0x91, 0x5f, 0x2e, 0x64, 0x4e, 0x7f, 0xca,
        0x5b, 0x5f, 0x7a, 0x35, 0x17, 0xe0, 0xaf, 0x6e,
        0xaf, 0x6b, 0xf1, 0x03, 0x82, 0x76, 0x6c, 0x7b,
        0xb1, 0xd5, 0xb9, 0x3d, 0xdb, 0xc2, 0xcd, 0x42,
    };
    constexpr std::array<uint8_t, 96> expected_nvt_payload = {
        0xa8, 0x2c, 0x63, 0xd6, 0xae, 0xff, 0xff, 0xbf,
        0x75, 0x7f, 0xcd, 0xcb, 0x8b, 0xff, 0xff, 0x3f,
        0xe0, 0x42, 0x87, 0x85, 0x80, 0x81, 0x42, 0xbf,
        0xdf, 0xd5, 0x63, 0x37, 0x1d, 0xf0, 0x0e, 0x3f,
        0x7a, 0x34, 0x02, 0x9c, 0x37, 0x9e, 0x59, 0xbf,
        0x09, 0x99, 0x88, 0x2c, 0xcf, 0x53, 0x4a, 0x3f,
        0x13, 0xed, 0xd5, 0x34, 0x67, 0x4a, 0x24, 0x3f,
        0xf0, 0xa9, 0x22, 0xa0, 0x0c, 0x0d, 0x2d, 0xbf,
        0xe0, 0x42, 0x87, 0x85, 0x80, 0x81, 0x52, 0xbf,
        0xdf, 0xd5, 0x63, 0x37, 0x1d, 0xf0, 0x1e, 0x3f,
        0x7a, 0x34, 0x02, 0x9c, 0x37, 0x9e, 0x69, 0xbf,
        0x09, 0x99, 0x88, 0x2c, 0xcf, 0x53, 0x5a, 0x3f,
    };
    assert(std::equal(
        expected_nvt_fingerprint.begin(), expected_nvt_fingerprint.end(),
        checkpoint.begin() + 40));
    assert(std::equal(
        expected_nvt_digest.begin(), expected_nvt_digest.end(),
        checkpoint.begin() + 72));
    assert(std::equal(
        expected_nvt_payload.begin(), expected_nvt_payload.end(),
        checkpoint.begin() + 104));
    const bg_particle_soa_view checkpoint_view = particle_view(first.simulation);
    const double *const position_address = checkpoint_view.position_x_angstrom;
    integrate(first.context, first.simulation, UINT64_C(25));
    assert(bg_simulation_checkpoint_load(
               replica.simulation, checkpoint.data(), checkpoint_size) ==
           BG_STATUS_OK);
    const bg_particle_soa_view loaded_view = particle_view(replica.simulation);
    const double *const loaded_address = loaded_view.position_x_angstrom;
    integrate(first.context, replica.simulation, UINT64_C(25));
    assert_same_dynamic_state(first.simulation, replica.simulation);
    assert(particle_view(first.simulation).position_x_angstrom ==
           position_address);
    assert(particle_view(replica.simulation).position_x_angstrom ==
           loaded_address);

    const uint64_t step_before_corruption = one_step.absolute_step + UINT64_C(25);
    uint64_t observed_step = UINT64_C(0);
    assert(bg_simulation_get_absolute_step(
               replica.simulation, &observed_step) == BG_STATUS_OK);
    assert(observed_step == step_before_corruption);
    checkpoint.back() ^= UINT8_C(1);
    assert(bg_simulation_checkpoint_load(
               replica.simulation, checkpoint.data(), checkpoint_size) ==
           BG_STATUS_INVALID_ARGUMENT);
    uint64_t step_after_corruption = UINT64_C(0);
    assert(bg_simulation_get_absolute_step(
               replica.simulation, &step_after_corruption) == BG_STATUS_OK);
    assert(step_after_corruption == observed_step);
    checkpoint.back() ^= UINT8_C(1);
    assert(bg_simulation_checkpoint_load(
               replica.simulation, checkpoint.data(), checkpoint_size -
                   UINT64_C(1)) == BG_STATUS_INVALID_ARGUMENT);
    std::vector<uint8_t> appended = checkpoint;
    appended.push_back(UINT8_C(0));
    assert(bg_simulation_checkpoint_load(
               replica.simulation, appended.data(),
               static_cast<uint64_t>(appended.size())) ==
           BG_STATUS_INVALID_ARGUMENT);

    std::vector<uint8_t> too_small(
        static_cast<std::size_t>(checkpoint_size - UINT64_C(1)), UINT8_C(0xa5));
    const std::vector<uint8_t> too_small_snapshot = too_small;
    uint64_t unchanged_written = UINT64_C(77);
    assert(bg_simulation_checkpoint_write(
               replica.simulation, too_small.data(), checkpoint_size -
                   UINT64_C(1), &unchanged_written) ==
           BG_STATUS_BUFFER_TOO_SMALL);
    assert(unchanged_written == UINT64_C(77));
    assert(too_small == too_small_snapshot);
    bg_particle_soa_view alias_view = particle_view(replica.simulation);
    assert(bg_simulation_checkpoint_write(
               replica.simulation,
               const_cast<double *>(alias_view.position_x_angstrom),
               checkpoint_size, &unchanged_written) ==
           BG_STATUS_INVALID_ARGUMENT);
    assert(bg_simulation_checkpoint_write(
               replica.simulation, checkpoint.data(), checkpoint_size,
               reinterpret_cast<uint64_t *>(
                   const_cast<double *>(alias_view.position_x_angstrom))) ==
           BG_STATUS_INVALID_ARGUMENT);

    NativeHandles mismatch;
    mismatch.system = make_system(
        {-2.0, 2.0}, {0.0, 0.0}, {0.0, 0.0},
        {0.0, 0.0}, {0.0, 0.0}, {0.0, 0.0}, {12.0, 16.0});
    mismatch.forcefield = make_forcefield(2U, 1.0, 0.0, false);
    mismatch.simulation = make_simulation(
        mismatch.system, mismatch.forcefield, BG_INTEGRATOR_LANGEVIN_BAOAB,
        1.0, 300.0, 0.05, seed + UINT64_C(1), nullptr);
    assert(bg_simulation_checkpoint_load(
               mismatch.simulation, checkpoint.data(), checkpoint_size) ==
           BG_STATUS_INVALID_ARGUMENT);
}

void test_report_and_state_failure_transactionality() {
    NativeHandles handles;
    handles.context = make_context(BG_BACKEND_CPU);
    const double huge = std::numeric_limits<double>::max() / 2.0;
    handles.system = make_system(
        {-1.0, 1.0}, {0.0, 0.0}, {0.0, 0.0},
        {huge, -huge}, {0.0, 0.0}, {0.0, 0.0}, {1.0, 1.0});
    handles.forcefield = make_forcefield(2U, 1.0, 0.0, false);
    handles.simulation = make_simulation(
        handles.system, handles.forcefield, BG_INTEGRATOR_VELOCITY_VERLET,
        4.0, 0.0, 0.0, UINT64_C(0), nullptr);
    const bg_particle_soa_view before = particle_view(handles.simulation);
    const auto addresses = particle_addresses(before);
    const std::array<double, 4> snapshot = {
        before.position_x_angstrom[0], before.position_x_angstrom[1],
        before.velocity_x_angstrom_per_femtosecond[0],
        before.velocity_x_angstrom_per_femtosecond[1],
    };
    bg_dynamics_report_v1 report;
    assert(bg_dynamics_report_v1_init(&report) == BG_STATUS_OK);
    report.steps_completed = UINT64_C(123);
    report.total_kcal_per_mol = 456.0;
    const bg_dynamics_report_v1 report_snapshot = report;
    assert(bg_context_integrate(
               handles.context, handles.simulation, UINT64_C(1), &report) ==
           BG_STATUS_NUMERICAL_ERROR);
    assert(std::memcmp(&report, &report_snapshot, sizeof(report)) == 0);
    const bg_particle_soa_view after = particle_view(handles.simulation);
    assert(particle_addresses(after) == addresses);
    assert(after.position_x_angstrom[0] == snapshot[0]);
    assert(after.position_x_angstrom[1] == snapshot[1]);
    assert(after.velocity_x_angstrom_per_femtosecond[0] == snapshot[2]);
    assert(after.velocity_x_angstrom_per_femtosecond[1] == snapshot[3]);
    const auto rollback_scratch_addresses =
        dynamic_rollback_scratch_addresses(handles.simulation);
    assert(bg_dynamics_report_v1_init(&report) == BG_STATUS_OK);
    assert(bg_context_integrate(
               handles.context, handles.simulation, UINT64_C(1), &report) ==
           BG_STATUS_NUMERICAL_ERROR);
    assert(dynamic_rollback_scratch_addresses(handles.simulation) ==
           rollback_scratch_addresses);
    const bg_particle_soa_view repeated_after =
        particle_view(handles.simulation);
    assert(particle_addresses(repeated_after) == addresses);
    assert(repeated_after.position_x_angstrom[0] == snapshot[0]);
    assert(repeated_after.position_x_angstrom[1] == snapshot[1]);
    assert(repeated_after.velocity_x_angstrom_per_femtosecond[0] ==
           snapshot[2]);
    assert(repeated_after.velocity_x_angstrom_per_femtosecond[1] ==
           snapshot[3]);

    NativeHandles overflow;
    overflow.context = make_context(BG_BACKEND_CPU);
    overflow.system = make_system(
        {0.0, 1.0}, {0.0, 0.0}, {0.0, 0.0},
        {0.0, 0.0}, {0.0, 0.0}, {0.0, 0.0}, {1.0, 1.0});
    overflow.forcefield = make_forcefield(2U, 1.0, 20.0, false);
    overflow.simulation = make_simulation(
        overflow.system, overflow.forcefield, BG_INTEGRATOR_VELOCITY_VERLET,
        0.1, 0.0, 0.0, UINT64_C(0), nullptr);
    integrate(overflow.context, overflow.simulation, UINT64_C(1));
    assert(bg_dynamics_report_v1_init(&report) == BG_STATUS_OK);
    report.steps_completed = UINT64_C(42);
    const bg_dynamics_report_v1 overflow_report_snapshot = report;
    assert(bg_context_integrate(
               overflow.context, overflow.simulation, UINT64_MAX, &report) ==
           BG_STATUS_CAPACITY_OVERFLOW);
    assert(std::memcmp(
               &report, &overflow_report_snapshot, sizeof(report)) == 0);
    report.reserved[0] = UINT64_C(1);
    const bg_dynamics_report_v1 invalid_report_snapshot = report;
    assert(bg_context_integrate(
               overflow.context, overflow.simulation, UINT64_C(0), &report) ==
           BG_STATUS_INVALID_ARGUMENT);
    assert(std::memcmp(
               &report, &invalid_report_snapshot, sizeof(report)) == 0);
}

void test_deep_ownership_and_signed_zero_checkpoint() {
    NativeHandles handles;
    handles.context = make_context(BG_BACKEND_CPU);
    handles.system = make_system(
        {-0.0, 2.0}, {0.0, 0.0}, {0.0, 0.0},
        {0.0, 0.0}, {0.0, 0.0}, {0.0, 0.0}, {1.0, 2.0});
    handles.forcefield = make_forcefield(2U, 1.0, 0.0, false);
    handles.simulation = make_simulation(
        handles.system, handles.forcefield, BG_INTEGRATOR_VELOCITY_VERLET,
        0.1, 0.0, 0.0, UINT64_C(0), nullptr);
    bg_system_destroy(handles.system);
    handles.system = nullptr;
    bg_forcefield_destroy(handles.forcefield);
    handles.forcefield = nullptr;
    assert(std::signbit(particle_view(handles.simulation).position_x_angstrom[0]));
    uint64_t size = UINT64_C(0);
    assert(bg_simulation_checkpoint_size(handles.simulation, &size) ==
           BG_STATUS_OK);
    std::vector<uint8_t> checkpoint(static_cast<std::size_t>(size));
    uint64_t written = UINT64_C(0);
    assert(bg_simulation_checkpoint_write(
               handles.simulation, checkpoint.data(), size, &written) ==
           BG_STATUS_OK);
    assert(size == UINT64_C(200));
    constexpr std::array<uint8_t, 8> magic = {
        'B', 'G', 'D', 'Y', 'N', '0', '0', '1'};
    assert(std::equal(magic.begin(), magic.end(), checkpoint.begin()));
    assert(checkpoint[8] == UINT8_C(1));
    assert(checkpoint[12] == UINT8_C(104));
    assert(checkpoint[16] == UINT8_C(200));
    assert(checkpoint[24] == UINT8_C(2));
    constexpr std::array<uint8_t, 32> expected_fingerprint = {
        0x1c, 0x2b, 0x2c, 0x8b, 0x84, 0x3c, 0xef, 0xa1,
        0xf9, 0x74, 0x73, 0x69, 0x4b, 0xe9, 0x74, 0xb6,
        0x2d, 0xfb, 0xb8, 0x3f, 0xe4, 0x60, 0xc5, 0x4f,
        0xcc, 0xd2, 0x21, 0xf5, 0x10, 0x4d, 0x57, 0x4a,
    };
    constexpr std::array<uint8_t, 32> expected_digest = {
        0xe1, 0x9b, 0x19, 0x91, 0xe8, 0xf4, 0x52, 0x90,
        0x52, 0x78, 0x92, 0x1d, 0xfb, 0x76, 0x80, 0x75,
        0xc3, 0x81, 0xa7, 0xe5, 0x25, 0xc7, 0x27, 0x7b,
        0x54, 0xda, 0x83, 0x2d, 0x44, 0x04, 0x69, 0x87,
    };
    assert(std::equal(
        expected_fingerprint.begin(), expected_fingerprint.end(),
        checkpoint.begin() + 40));
    assert(std::equal(
        expected_digest.begin(), expected_digest.end(),
        checkpoint.begin() + 72));
    for (std::size_t index = 104U; index < checkpoint.size(); ++index) {
        const uint8_t expected =
            index == 111U ? UINT8_C(0x80) :
            (index == 119U ? UINT8_C(0x40) : UINT8_C(0));
        assert(checkpoint[index] == expected);
    }
    assert(bg_simulation_checkpoint_load(
               handles.simulation, checkpoint.data(), size) == BG_STATUS_OK);
    assert(std::signbit(particle_view(handles.simulation).position_x_angstrom[0]));
    integrate(handles.context, handles.simulation, UINT64_C(1));
}

void test_periodic_cpu_neighbor_cache() {
    NativeHandles cpp;
    cpp.context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    cpp.system = make_system(
        {-3.5, 0.0, 3.5}, {0.0, 0.0, 0.0}, {0.0, 0.0, 0.0},
        {0.0, 0.0, 0.0}, {0.0, 0.0, 0.0}, {0.0, 0.0, 0.0},
        {12.0, 16.0, 14.0});
    cpp.forcefield = make_periodic_nonbonded_forcefield(3U);
    cpp.simulation = make_simulation(
        cpp.system, cpp.forcefield, BG_INTEGRATOR_VELOCITY_VERLET,
        0.1, 0.0, 0.0, UINT64_C(0), nullptr);

    NativeHandles rust;
    rust.context = make_context(BG_BACKEND_RUST_CPU);
    rust.system = make_system(
        {-3.5, 0.0, 3.5}, {0.0, 0.0, 0.0}, {0.0, 0.0, 0.0},
        {0.0, 0.0, 0.0}, {0.0, 0.0, 0.0}, {0.0, 0.0, 0.0},
        {12.0, 16.0, 14.0});
    rust.forcefield = make_periodic_nonbonded_forcefield(3U);
    rust.simulation = make_simulation(
        rust.system, rust.forcefield, BG_INTEGRATOR_VELOCITY_VERLET,
        0.1, 0.0, 0.0, UINT64_C(0), nullptr);

    const bg_dynamics_report_v1 cpp_initial =
        integrate(cpp.context, cpp.simulation, UINT64_C(0));
    const bg_dynamics_report_v1 rust_initial =
        integrate(rust.context, rust.simulation, UINT64_C(0));
    assert(same_bits(
        cpp_initial.potential_kcal_per_mol,
        rust_initial.potential_kcal_per_mol));
    assert(same_bits(
        cpp_initial.total_kcal_per_mol,
        rust_initial.total_kcal_per_mol));
    assert(cpp.simulation->neighbor_list_cache.data != nullptr);
    assert(cpp.simulation->neighbor_list_cache.build_scratch != nullptr);
    assert(cpp.simulation->neighbor_list_cache.data->pairs.size() == 3U);
    assert(cpp.simulation->neighbor_list_cache.build_count == UINT64_C(1));
    assert(cpp.simulation->neighbor_list_cache.reuse_count == UINT64_C(0));
    assert(rust.simulation->neighbor_list_cache.data->pairs ==
           cpp.simulation->neighbor_list_cache.data->pairs);
    const auto *const initial_cache_data =
        cpp.simulation->neighbor_list_cache.data.get();
    const auto *const build_scratch =
        cpp.simulation->neighbor_list_cache.build_scratch.get();
    const auto *const atom_cells_storage =
        build_scratch->atom_cells.data();
    const auto *const assignments_storage =
        build_scratch->assignments.data();
    const auto *const neighbor_cells_storage =
        build_scratch->neighbor_cells.data();
    const auto *const candidates_storage =
        build_scratch->candidates.data();

    const bg_dynamics_report_v1 switched_backend =
        integrate(rust.context, cpp.simulation, UINT64_C(0));
    assert(same_bits(
        switched_backend.potential_kcal_per_mol,
        cpp_initial.potential_kcal_per_mol));
    assert(cpp.simulation->neighbor_list_cache.build_count == UINT64_C(1));
    assert(cpp.simulation->neighbor_list_cache.reuse_count == UINT64_C(1));
    assert(cpp.simulation->neighbor_list_cache.data.get() == initial_cache_data);
    integrate(cpp.context, cpp.simulation, UINT64_C(0));
    assert(cpp.simulation->neighbor_list_cache.build_count == UINT64_C(1));
    assert(cpp.simulation->neighbor_list_cache.reuse_count == UINT64_C(2));
    assert(cpp.simulation->neighbor_list_cache.data.get() == initial_cache_data);
    cpp.simulation->system.position_x[0] += 0.4;
    integrate(cpp.context, cpp.simulation, UINT64_C(0));
    assert(cpp.simulation->neighbor_list_cache.build_count == UINT64_C(1));
    assert(cpp.simulation->neighbor_list_cache.reuse_count == UINT64_C(3));
    assert(cpp.simulation->neighbor_list_cache.data.get() == initial_cache_data);
    cpp.simulation->system.position_x[0] += 0.2;
    integrate(cpp.context, cpp.simulation, UINT64_C(0));
    assert(cpp.simulation->neighbor_list_cache.build_count == UINT64_C(2));
    assert(cpp.simulation->neighbor_list_cache.reuse_count == UINT64_C(3));
    assert(cpp.simulation->neighbor_list_cache.data.get() != initial_cache_data);
    assert(cpp.simulation->neighbor_list_cache.build_scratch.get() ==
           build_scratch);
    assert(build_scratch->atom_cells.data() == atom_cells_storage);
    assert(build_scratch->assignments.data() == assignments_storage);
    assert(build_scratch->neighbor_cells.data() == neighbor_cells_storage);
    assert(build_scratch->candidates.data() == candidates_storage);

    const uint64_t builds_before_failure =
        cpp.simulation->neighbor_list_cache.build_count;
    const uint64_t reuses_before_failure =
        cpp.simulation->neighbor_list_cache.reuse_count;
    const auto *const cache_data_before_failure =
        cpp.simulation->neighbor_list_cache.data.get();
    const double saved_x = cpp.simulation->system.position_x[0];
    cpp.simulation->system.position_x[0] =
        cpp.simulation->system.position_x[1];
    bg_dynamics_report_v1 failed_report;
    assert(bg_dynamics_report_v1_init(&failed_report) == BG_STATUS_OK);
    assert(bg_context_integrate(
               cpp.context, cpp.simulation, UINT64_C(0), &failed_report) ==
           BG_STATUS_NUMERICAL_ERROR);
    assert(cpp.simulation->neighbor_list_cache.build_count ==
           builds_before_failure);
    assert(cpp.simulation->neighbor_list_cache.reuse_count ==
           reuses_before_failure);
    assert(cpp.simulation->neighbor_list_cache.data.get() ==
           cache_data_before_failure);
    assert(cpp.simulation->neighbor_list_cache.build_scratch.get() ==
           build_scratch);
    assert(build_scratch->atom_cells.data() == atom_cells_storage);
    assert(build_scratch->assignments.data() == assignments_storage);
    assert(build_scratch->neighbor_cells.data() == neighbor_cells_storage);
    assert(build_scratch->candidates.data() == candidates_storage);
    cpp.simulation->system.position_x[0] = saved_x;

    uint64_t checkpoint_size = UINT64_C(0);
    assert(bg_simulation_checkpoint_size(
               cpp.simulation, &checkpoint_size) == BG_STATUS_OK);
    std::vector<uint8_t> checkpoint(
        static_cast<std::size_t>(checkpoint_size));
    uint64_t written = UINT64_C(0);
    assert(bg_simulation_checkpoint_write(
               cpp.simulation,
               checkpoint.data(),
               checkpoint_size,
               &written) == BG_STATUS_OK);
    assert(written == checkpoint_size);
    assert(bg_simulation_checkpoint_load(
               cpp.simulation,
               checkpoint.data(),
               checkpoint_size) == BG_STATUS_OK);
    assert(cpp.simulation->neighbor_list_cache.data == nullptr);
    assert(cpp.simulation->neighbor_list_cache.build_count == UINT64_C(0));
    assert(cpp.simulation->neighbor_list_cache.reuse_count == UINT64_C(0));
    integrate(cpp.context, cpp.simulation, UINT64_C(0));
    assert(cpp.simulation->neighbor_list_cache.data != nullptr);
    assert(cpp.simulation->neighbor_list_cache.build_count == UINT64_C(1));
}

void test_hip_parity_if_available() {
#if BG_TEST_HIP_ENABLED
    uint8_t available = UINT8_C(0);
    assert(bg_backend_is_available(BG_BACKEND_HIP, 0, &available) ==
           BG_STATUS_OK);
    if (available == UINT8_C(0)) {
        return;
    }
    NativeHandles cpu;
    cpu.context = make_context(BG_BACKEND_CPU);
    cpu.system = make_system(
        {-0.6, 0.6}, {0.0, 0.0}, {0.0, 0.0},
        {0.001, -0.001}, {0.0, 0.0}, {0.0, 0.0}, {12.0, 16.0});
    cpu.forcefield = make_forcefield(2U, 1.0, 20.0, false);
    cpu.simulation = make_simulation(
        cpu.system, cpu.forcefield, BG_INTEGRATOR_VELOCITY_VERLET,
        0.2, 0.0, 0.0, UINT64_C(0), nullptr);
    NativeHandles hip;
    hip.context = make_context(BG_BACKEND_HIP);
    hip.system = make_system(
        {-0.6, 0.6}, {0.0, 0.0}, {0.0, 0.0},
        {0.001, -0.001}, {0.0, 0.0}, {0.0, 0.0}, {12.0, 16.0});
    hip.forcefield = make_forcefield(2U, 1.0, 20.0, false);
    hip.simulation = make_simulation(
        hip.system, hip.forcefield, BG_INTEGRATOR_VELOCITY_VERLET,
        0.2, 0.0, 0.0, UINT64_C(0), nullptr);
    integrate(cpu.context, cpu.simulation, UINT64_C(20));
    integrate(hip.context, hip.simulation, UINT64_C(20));
    assert_same_dynamic_state(cpu.simulation, hip.simulation);
#endif
}

}  // namespace

int main() {
    test_initializers_and_invalid_rows();
    test_minimizer_and_transactionality();
    test_constraints_and_periodic_images();
    test_constrained_minimizer_rattle_checkpoint();
    test_nve_fixture_and_zero_step();
    test_nvt_fixture_and_checkpoint();
    test_report_and_state_failure_transactionality();
    test_deep_ownership_and_signed_zero_checkpoint();
    test_periodic_cpu_neighbor_cache();
    test_hip_parity_if_available();
    return 0;
}
