#include <betelgeuze/engine.h>

#include <cstddef>
#include <cstdint>
#include <type_traits>

template <typename T, typename = void>
struct is_complete : std::false_type {};

template <typename T>
struct is_complete<T, std::void_t<decltype(sizeof(T))>> : std::true_type {};

static_assert(std::is_standard_layout<bg_context_options>::value);
static_assert(std::is_standard_layout<bg_particle_soa>::value);
static_assert(std::is_standard_layout<bg_particle_soa_view>::value);
static_assert(std::is_standard_layout<bg_position_soa>::value);
static_assert(std::is_standard_layout<bg_forcefield_soa_v1>::value);
static_assert(std::is_standard_layout<bg_force_soa_v1>::value);
static_assert(std::is_standard_layout<bg_energy_components_v1>::value);
static_assert(std::is_standard_layout<bg_distance_constraints_v1>::value);
static_assert(std::is_standard_layout<bg_simulation_options_v1>::value);
static_assert(std::is_standard_layout<bg_minimizer_options_v1>::value);
static_assert(std::is_standard_layout<bg_minimization_report_v1>::value);
static_assert(std::is_standard_layout<bg_dynamics_report_v1>::value);
static_assert(std::is_standard_layout<bg_docking_scorer_v1_context_soa_v1>::value);
static_assert(
    std::is_standard_layout<bg_docking_scorer_v1_candidate_batch_soa_v1>::value);
static_assert(std::is_standard_layout<bg_docking_scorer_v1_row_v1>::value);
static_assert(std::is_standard_layout<bg_docking_scorer_v1_output_v1>::value);

static_assert(!is_complete<bg_context>::value);
static_assert(!is_complete<bg_system>::value);
static_assert(!is_complete<bg_forcefield>::value);
static_assert(!is_complete<bg_simulation>::value);
static_assert(!is_complete<bg_docking_scorer_v1>::value);

static_assert(sizeof(bg_context_options) == 64);
static_assert(alignof(bg_context_options) == alignof(uint64_t));
static_assert(offsetof(bg_context_options, struct_size) == 0);
static_assert(offsetof(bg_context_options, abi_version) == 4);
static_assert(offsetof(bg_context_options, backend) == 8);
static_assert(offsetof(bg_context_options, unit_system) == 12);
static_assert(offsetof(bg_context_options, device_ordinal) == 16);
static_assert(offsetof(bg_context_options, reserved0) == 20);
static_assert(offsetof(bg_context_options, flags) == 24);
static_assert(offsetof(bg_context_options, reserved) == 32);

#if INTPTR_MAX == INT64_MAX
static_assert(sizeof(bg_docking_scorer_v1_context_soa_v1) == 608);
static_assert(alignof(bg_docking_scorer_v1_context_soa_v1) == 8);
static_assert(offsetof(bg_docking_scorer_v1_context_soa_v1, receptor_atom_count) == 16);
static_assert(offsetof(bg_docking_scorer_v1_context_soa_v1, receptor_x_angstrom) == 32);
static_assert(
    offsetof(bg_docking_scorer_v1_context_soa_v1, ligand_reference_x_angstrom) == 96);
static_assert(offsetof(bg_docking_scorer_v1_context_soa_v1, receptor_donor_count) == 160);
static_assert(offsetof(bg_docking_scorer_v1_context_soa_v1, ligand_exclusion_count) == 208);
static_assert(offsetof(bg_docking_scorer_v1_context_soa_v1, rotor_count) == 232);
static_assert(offsetof(bg_docking_scorer_v1_context_soa_v1, pocket_center_angstrom) == 272);
static_assert(offsetof(bg_docking_scorer_v1_context_soa_v1, weights) == 304);
static_assert(
    offsetof(bg_docking_scorer_v1_context_soa_v1, max_receptor_candidate_pairs) == 400);
static_assert(
    offsetof(bg_docking_scorer_v1_context_soa_v1, authority_input_receipt_sha256) == 416);
static_assert(offsetof(bg_docking_scorer_v1_context_soa_v1, reserved) == 544);

static_assert(sizeof(bg_docking_scorer_v1_candidate_batch_soa_v1) == 96);
static_assert(
    offsetof(bg_docking_scorer_v1_candidate_batch_soa_v1, candidate_state) == 32);
static_assert(offsetof(bg_docking_scorer_v1_candidate_batch_soa_v1, reserved) == 64);
static_assert(sizeof(bg_docking_scorer_v1_row_v1) == 160);
static_assert(offsetof(bg_docking_scorer_v1_row_v1, weighted_terms) == 16);
static_assert(offsetof(bg_docking_scorer_v1_row_v1, total_score) == 80);
static_assert(
    offsetof(bg_docking_scorer_v1_row_v1, receptor_candidate_pair_count) == 88);
static_assert(offsetof(bg_docking_scorer_v1_row_v1, reserved) == 128);
static_assert(sizeof(bg_docking_scorer_v1_output_v1) == 72);
static_assert(offsetof(bg_docking_scorer_v1_output_v1, rows) == 32);
static_assert(offsetof(bg_docking_scorer_v1_output_v1, reserved) == 40);

static_assert(sizeof(bg_particle_soa) == 120);
static_assert(alignof(bg_particle_soa) == 8);
static_assert(offsetof(bg_particle_soa, struct_size) == 0);
static_assert(offsetof(bg_particle_soa, abi_version) == 4);
static_assert(offsetof(bg_particle_soa, particle_count) == 8);
static_assert(offsetof(bg_particle_soa, unit_system) == 16);
static_assert(offsetof(bg_particle_soa, reserved0) == 20);
static_assert(offsetof(bg_particle_soa, position_x_angstrom) == 24);
static_assert(offsetof(bg_particle_soa, position_y_angstrom) == 32);
static_assert(offsetof(bg_particle_soa, position_z_angstrom) == 40);
static_assert(offsetof(bg_particle_soa, velocity_x_angstrom_per_femtosecond) == 48);
static_assert(offsetof(bg_particle_soa, velocity_y_angstrom_per_femtosecond) == 56);
static_assert(offsetof(bg_particle_soa, velocity_z_angstrom_per_femtosecond) == 64);
static_assert(offsetof(bg_particle_soa, mass_dalton) == 72);
static_assert(offsetof(bg_particle_soa, charge_elementary) == 80);
static_assert(offsetof(bg_particle_soa, reserved) == 88);

static_assert(sizeof(bg_particle_soa_view) == 120);
static_assert(alignof(bg_particle_soa_view) == 8);
static_assert(offsetof(bg_particle_soa_view, particle_count) == 8);
static_assert(offsetof(bg_particle_soa_view, position_x_angstrom) == 24);
static_assert(offsetof(bg_particle_soa_view, charge_elementary) == 80);
static_assert(offsetof(bg_particle_soa_view, reserved) == 88);

static_assert(sizeof(bg_position_soa) == 80);
static_assert(alignof(bg_position_soa) == 8);
static_assert(offsetof(bg_position_soa, struct_size) == 0);
static_assert(offsetof(bg_position_soa, abi_version) == 4);
static_assert(offsetof(bg_position_soa, particle_count) == 8);
static_assert(offsetof(bg_position_soa, unit_system) == 16);
static_assert(offsetof(bg_position_soa, reserved0) == 20);
static_assert(offsetof(bg_position_soa, x_angstrom) == 24);
static_assert(offsetof(bg_position_soa, y_angstrom) == 32);
static_assert(offsetof(bg_position_soa, z_angstrom) == 40);
static_assert(offsetof(bg_position_soa, reserved) == 48);

static_assert(sizeof(bg_forcefield_soa_v1) == 352);
static_assert(alignof(bg_forcefield_soa_v1) == 8);
static_assert(offsetof(bg_forcefield_soa_v1, struct_size) == 0);
static_assert(offsetof(bg_forcefield_soa_v1, abi_version) == 4);
static_assert(offsetof(bg_forcefield_soa_v1, atom_count) == 8);
static_assert(offsetof(bg_forcefield_soa_v1, unit_system) == 16);
static_assert(offsetof(bg_forcefield_soa_v1, periodic_axes_mask) == 20);
static_assert(offsetof(bg_forcefield_soa_v1, sigma_angstrom) == 24);
static_assert(offsetof(bg_forcefield_soa_v1, epsilon_kcal_per_mol) == 32);
static_assert(offsetof(bg_forcefield_soa_v1, bond_count) == 40);
static_assert(offsetof(bg_forcefield_soa_v1, bond_atom_i) == 48);
static_assert(offsetof(bg_forcefield_soa_v1, bond_atom_j) == 56);
static_assert(offsetof(bg_forcefield_soa_v1, bond_equilibrium_angstrom) == 64);
static_assert(
    offsetof(bg_forcefield_soa_v1, bond_force_constant_kcal_per_mol_angstrom2) == 72);
static_assert(offsetof(bg_forcefield_soa_v1, angle_count) == 80);
static_assert(offsetof(bg_forcefield_soa_v1, angle_atom_i) == 88);
static_assert(offsetof(bg_forcefield_soa_v1, angle_atom_j) == 96);
static_assert(offsetof(bg_forcefield_soa_v1, angle_atom_k) == 104);
static_assert(offsetof(bg_forcefield_soa_v1, angle_equilibrium_radians) == 112);
static_assert(
    offsetof(bg_forcefield_soa_v1, angle_force_constant_kcal_per_mol_radian2) == 120);
static_assert(offsetof(bg_forcefield_soa_v1, torsion_count) == 128);
static_assert(offsetof(bg_forcefield_soa_v1, torsion_atom_i) == 136);
static_assert(offsetof(bg_forcefield_soa_v1, torsion_atom_j) == 144);
static_assert(offsetof(bg_forcefield_soa_v1, torsion_atom_k) == 152);
static_assert(offsetof(bg_forcefield_soa_v1, torsion_atom_l) == 160);
static_assert(offsetof(bg_forcefield_soa_v1, torsion_periodicity) == 168);
static_assert(offsetof(bg_forcefield_soa_v1, torsion_phase_radians) == 176);
static_assert(offsetof(bg_forcefield_soa_v1, torsion_amplitude_kcal_per_mol) == 184);
static_assert(offsetof(bg_forcefield_soa_v1, exclusion_count) == 192);
static_assert(offsetof(bg_forcefield_soa_v1, exclusion_atom_i) == 200);
static_assert(offsetof(bg_forcefield_soa_v1, exclusion_atom_j) == 208);
static_assert(offsetof(bg_forcefield_soa_v1, pair_scale_count) == 216);
static_assert(offsetof(bg_forcefield_soa_v1, pair_scale_atom_i) == 224);
static_assert(offsetof(bg_forcefield_soa_v1, pair_scale_atom_j) == 232);
static_assert(offsetof(bg_forcefield_soa_v1, pair_scale_lennard_jones) == 240);
static_assert(offsetof(bg_forcefield_soa_v1, pair_scale_coulomb) == 248);
static_assert(offsetof(bg_forcefield_soa_v1, cell_lengths_angstrom) == 256);
static_assert(offsetof(bg_forcefield_soa_v1, cutoff_angstrom) == 280);
static_assert(offsetof(bg_forcefield_soa_v1, switch_start_angstrom) == 288);
static_assert(offsetof(bg_forcefield_soa_v1, dielectric) == 296);
static_assert(offsetof(bg_forcefield_soa_v1, screening_kappa_per_angstrom) == 304);
static_assert(offsetof(bg_forcefield_soa_v1, minimum_pair_distance_angstrom) == 312);
static_assert(offsetof(bg_forcefield_soa_v1, reserved) == 320);

static_assert(sizeof(bg_force_soa_v1) == 88);
static_assert(alignof(bg_force_soa_v1) == 8);
static_assert(offsetof(bg_force_soa_v1, struct_size) == 0);
static_assert(offsetof(bg_force_soa_v1, abi_version) == 4);
static_assert(offsetof(bg_force_soa_v1, particle_capacity) == 8);
static_assert(offsetof(bg_force_soa_v1, particle_count) == 16);
static_assert(offsetof(bg_force_soa_v1, unit_system) == 24);
static_assert(offsetof(bg_force_soa_v1, reserved0) == 28);
static_assert(offsetof(bg_force_soa_v1, x_kcal_per_mol_angstrom) == 32);
static_assert(offsetof(bg_force_soa_v1, y_kcal_per_mol_angstrom) == 40);
static_assert(offsetof(bg_force_soa_v1, z_kcal_per_mol_angstrom) == 48);
static_assert(offsetof(bg_force_soa_v1, reserved) == 56);
#endif

static_assert(sizeof(bg_energy_components_v1) == 96);
static_assert(alignof(bg_energy_components_v1) == alignof(uint64_t));
static_assert(offsetof(bg_energy_components_v1, struct_size) == 0);
static_assert(offsetof(bg_energy_components_v1, abi_version) == 4);
static_assert(offsetof(bg_energy_components_v1, unit_system) == 8);
static_assert(offsetof(bg_energy_components_v1, reserved0) == 12);
static_assert(offsetof(bg_energy_components_v1, harmonic_bond_kcal_per_mol) == 16);
static_assert(offsetof(bg_energy_components_v1, harmonic_angle_kcal_per_mol) == 24);
static_assert(offsetof(bg_energy_components_v1, periodic_torsion_kcal_per_mol) == 32);
static_assert(offsetof(bg_energy_components_v1, lennard_jones_kcal_per_mol) == 40);
static_assert(offsetof(bg_energy_components_v1, coulomb_kcal_per_mol) == 48);
static_assert(offsetof(bg_energy_components_v1, total_kcal_per_mol) == 56);
static_assert(offsetof(bg_energy_components_v1, reserved) == 64);

#if INTPTR_MAX == INT64_MAX
static_assert(sizeof(bg_distance_constraints_v1) == 104);
static_assert(alignof(bg_distance_constraints_v1) == 8);
static_assert(offsetof(bg_distance_constraints_v1, constraint_count) == 8);
static_assert(offsetof(bg_distance_constraints_v1, atom_i) == 24);
static_assert(offsetof(bg_distance_constraints_v1, atom_j) == 32);
static_assert(offsetof(bg_distance_constraints_v1, distance_angstrom) == 40);
static_assert(offsetof(bg_distance_constraints_v1, tolerance_angstrom) == 48);
static_assert(
    offsetof(
        bg_distance_constraints_v1,
        velocity_tolerance_angstrom_per_femtosecond) == 56);
static_assert(offsetof(bg_distance_constraints_v1, max_iterations) == 64);
static_assert(offsetof(bg_distance_constraints_v1, reserved1) == 68);
static_assert(offsetof(bg_distance_constraints_v1, reserved) == 72);
#endif

static_assert(sizeof(bg_simulation_options_v1) == 80);
static_assert(alignof(bg_simulation_options_v1) == 8);
static_assert(offsetof(bg_simulation_options_v1, integrator) == 12);
static_assert(offsetof(bg_simulation_options_v1, timestep_femtoseconds) == 16);
static_assert(offsetof(bg_simulation_options_v1, temperature_kelvin) == 24);
static_assert(offsetof(bg_simulation_options_v1, friction_per_femtosecond) == 32);
static_assert(offsetof(bg_simulation_options_v1, random_seed) == 40);
static_assert(offsetof(bg_simulation_options_v1, reserved) == 48);

static_assert(sizeof(bg_minimizer_options_v1) == 112);
static_assert(alignof(bg_minimizer_options_v1) == 8);
static_assert(offsetof(bg_minimizer_options_v1, max_iterations) == 16);
static_assert(offsetof(bg_minimizer_options_v1, max_line_search_steps) == 24);
static_assert(
    offsetof(bg_minimizer_options_v1, initial_step_angstrom2_mol_per_kcal) == 32);
static_assert(
    offsetof(bg_minimizer_options_v1, minimum_step_angstrom2_mol_per_kcal) == 40);
static_assert(
    offsetof(bg_minimizer_options_v1, energy_tolerance_kcal_per_mol) == 48);
static_assert(
    offsetof(bg_minimizer_options_v1, force_tolerance_kcal_per_mol_angstrom) == 56);
static_assert(offsetof(bg_minimizer_options_v1, armijo_coefficient) == 64);
static_assert(offsetof(bg_minimizer_options_v1, backtrack_factor) == 72);
static_assert(offsetof(bg_minimizer_options_v1, reserved) == 80);

static_assert(sizeof(bg_minimization_report_v1) == 88);
static_assert(alignof(bg_minimization_report_v1) == 8);
static_assert(offsetof(bg_minimization_report_v1, iterations) == 16);
static_assert(offsetof(bg_minimization_report_v1, converged) == 24);
static_assert(
    offsetof(bg_minimization_report_v1, initial_potential_kcal_per_mol) == 32);
static_assert(
    offsetof(bg_minimization_report_v1, final_potential_kcal_per_mol) == 40);
static_assert(
    offsetof(bg_minimization_report_v1, maximum_force_kcal_per_mol_angstrom) == 48);
static_assert(offsetof(bg_minimization_report_v1, reserved) == 56);

static_assert(sizeof(bg_dynamics_report_v1) == 104);
static_assert(alignof(bg_dynamics_report_v1) == 8);
static_assert(offsetof(bg_dynamics_report_v1, steps_completed) == 16);
static_assert(offsetof(bg_dynamics_report_v1, absolute_step) == 24);
static_assert(offsetof(bg_dynamics_report_v1, degrees_of_freedom) == 32);
static_assert(offsetof(bg_dynamics_report_v1, potential_kcal_per_mol) == 40);
static_assert(offsetof(bg_dynamics_report_v1, kinetic_kcal_per_mol) == 48);
static_assert(offsetof(bg_dynamics_report_v1, total_kcal_per_mol) == 56);
static_assert(offsetof(bg_dynamics_report_v1, temperature_kelvin) == 64);
static_assert(offsetof(bg_dynamics_report_v1, reserved) == 72);

static_assert(noexcept(bg_abi_version()));
static_assert(noexcept(bg_context_destroy(nullptr)));
static_assert(noexcept(bg_system_destroy(nullptr)));
static_assert(noexcept(bg_forcefield_soa_v1_init(nullptr)));
static_assert(noexcept(bg_force_soa_v1_init(nullptr)));
static_assert(noexcept(bg_energy_components_v1_init(nullptr)));
static_assert(noexcept(bg_forcefield_create(nullptr, nullptr)));
static_assert(noexcept(bg_forcefield_destroy(nullptr)));
static_assert(noexcept(bg_forcefield_get_atom_count(nullptr, nullptr)));
static_assert(noexcept(bg_context_evaluate(nullptr, nullptr, nullptr, nullptr, nullptr)));
static_assert(noexcept(bg_distance_constraints_v1_init(nullptr)));
static_assert(noexcept(bg_simulation_options_v1_init(nullptr)));
static_assert(noexcept(bg_minimizer_options_v1_init(nullptr)));
static_assert(noexcept(bg_minimization_report_v1_init(nullptr)));
static_assert(noexcept(bg_dynamics_report_v1_init(nullptr)));
static_assert(noexcept(bg_simulation_create(nullptr, nullptr, nullptr, nullptr, nullptr)));
static_assert(noexcept(bg_simulation_destroy(nullptr)));
static_assert(noexcept(bg_simulation_get_particles(nullptr, nullptr)));
static_assert(noexcept(bg_simulation_get_absolute_step(nullptr, nullptr)));
static_assert(noexcept(bg_context_minimize(nullptr, nullptr, nullptr, nullptr)));
static_assert(noexcept(bg_context_integrate(nullptr, nullptr, 0, nullptr)));
static_assert(noexcept(bg_simulation_checkpoint_size(nullptr, nullptr)));
static_assert(noexcept(bg_simulation_checkpoint_write(nullptr, nullptr, 0, nullptr)));
static_assert(noexcept(bg_simulation_checkpoint_load(nullptr, nullptr, 0)));
