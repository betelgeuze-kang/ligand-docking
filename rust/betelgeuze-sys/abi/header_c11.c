#include <betelgeuze/engine.h>

#include <stddef.h>
#include <stdint.h>

_Static_assert(BG_ABI_VERSION == UINT32_C(1), "unexpected ABI version");
_Static_assert(BG_ABI_VERSION_MAJOR == UINT32_C(1), "unexpected ABI major version");
_Static_assert(BG_ABI_VERSION_MINOR == UINT32_C(14), "unexpected ABI minor version");
_Static_assert(BG_STATUS_OK == 0, "unexpected success status");
_Static_assert(BG_STATUS_NUMERICAL_ERROR == 10, "unexpected numerical status");
_Static_assert(BG_BACKEND_CPU == 1, "unexpected CPU backend value");
_Static_assert(BG_BACKEND_HIP == 2, "unexpected HIP backend value");
_Static_assert(BG_BACKEND_CPP_CPU_REFERENCE == 1, "unexpected C++ CPU backend value");
_Static_assert(BG_BACKEND_HIP_FAST == 2, "unexpected fast HIP backend value");
_Static_assert(BG_BACKEND_RUST_CPU == 3, "unexpected Rust CPU backend value");
_Static_assert(BG_BACKEND_HIP_SAFE == 4, "unexpected safe HIP backend value");
_Static_assert(
    BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL == 1,
    "unexpected canonical unit-system value");
_Static_assert(sizeof(bg_status) == sizeof(int32_t), "bg_status width changed");
_Static_assert(sizeof(bg_backend) == sizeof(int32_t), "bg_backend width changed");
_Static_assert(
    sizeof(bg_unit_system) == sizeof(int32_t),
    "bg_unit_system width changed");
_Static_assert(
    sizeof(bg_docking_fixed64_lane) == sizeof(int32_t),
    "fixed64 lane width changed");
_Static_assert(
    sizeof(bg_docking_fixed64_feature_kind) == sizeof(int32_t),
    "fixed64 feature kind width changed");
_Static_assert(
    sizeof(bg_docking_fixed64_anchor_kind) == sizeof(int32_t),
    "fixed64 anchor kind width changed");
_Static_assert(
    sizeof(bg_docking_fixed64_parent_role) == sizeof(int32_t),
    "fixed64 parent role width changed");
_Static_assert(
    sizeof(bg_docking_fixed64_allocation_row_status) == sizeof(int32_t),
    "fixed64 allocation row status width changed");
_Static_assert(sizeof(bg_integrator) == sizeof(int32_t), "bg_integrator width changed");
_Static_assert(
    sizeof(bg_docking_geometric_admission_candidate_state) == sizeof(int32_t),
    "geometric-admission candidate state width changed");
_Static_assert(
    sizeof(bg_docking_geometric_admission_row_status) == sizeof(int32_t),
    "geometric-admission row status width changed");
_Static_assert(
    sizeof(bg_docking_geometric_admission_failure) == sizeof(int32_t),
    "geometric-admission failure width changed");
_Static_assert(
    sizeof(bg_docking_geometric_admission_decision) == sizeof(int32_t),
    "geometric-admission decision width changed");
_Static_assert(
    sizeof(bg_docking_scorer_v1_candidate_state) == sizeof(int32_t),
    "ScorerV1 candidate state width changed");
_Static_assert(
    sizeof(bg_docking_scorer_v1_row_status) == sizeof(int32_t),
    "ScorerV1 row status width changed");
_Static_assert(
    sizeof(bg_docking_scorer_v1_failure) == sizeof(int32_t),
    "ScorerV1 failure width changed");
_Static_assert(
    sizeof(bg_docking_pose_validity_candidate_state) == sizeof(int32_t),
    "pose-validity candidate state width changed");
_Static_assert(
    sizeof(bg_docking_pose_validity_row_status) == sizeof(int32_t),
    "pose-validity row status width changed");
_Static_assert(
    sizeof(bg_docking_pose_validity_failure) == sizeof(int32_t),
    "pose-validity failure width changed");
_Static_assert(
    sizeof(bg_docking_rmsd_cluster_row_status) == sizeof(int32_t),
    "RMSD-cluster row status width changed");
_Static_assert(
    sizeof(bg_docking_rigid_refinement_candidate_mode) == sizeof(int32_t),
    "rigid-refinement candidate mode width changed");
_Static_assert(
    sizeof(bg_docking_rigid_refinement_row_status) == sizeof(int32_t),
    "rigid-refinement row status width changed");
_Static_assert(
    sizeof(bg_docking_rigid_refinement_failure) == sizeof(int32_t),
    "rigid-refinement failure width changed");
_Static_assert(
    sizeof(bg_docking_rigid_refinement_profile) == sizeof(int32_t),
    "rigid-refinement profile width changed");
_Static_assert(
    sizeof(bg_docking_torsion_v7_candidate_state) == sizeof(int32_t),
    "torsion V7 candidate state width changed");
_Static_assert(
    sizeof(bg_docking_torsion_v7_row_status) == sizeof(int32_t),
    "torsion V7 row status width changed");
_Static_assert(
    sizeof(bg_docking_torsion_v7_failure) == sizeof(int32_t),
    "torsion V7 failure width changed");
_Static_assert(
    sizeof(bg_docking_fixed64_refinement_row_status) == sizeof(int32_t),
    "fixed64 refinement row status width changed");
_Static_assert(
    sizeof(bg_docking_fixed64_refinement_failure_stage) == sizeof(int32_t),
    "fixed64 refinement failure stage width changed");
_Static_assert(
    sizeof(bg_docking_fixed64_refinement_coordinate_origin) == sizeof(int32_t),
    "fixed64 refinement coordinate origin width changed");
_Static_assert(BG_DOCKING_FIXED64_CANDIDATE_COUNT == 64, "bad fixed64 denominator");
_Static_assert(BG_DOCKING_SCORER_V1_TERM_COUNT == 8, "bad ScorerV1 term count");
_Static_assert(BG_DOCKING_STABLE_TOP_K_LIMIT == 5, "bad stable Top-K limit");
_Static_assert(BG_DOCKING_RMSD_CLUSTER_TOP_K_LIMIT == 5, "bad RMSD-cluster Top-K limit");
_Static_assert(BG_DOCKING_TORSION_V7_MAX_MOVES == 8, "bad torsion V7 move count");
_Static_assert(BG_INTEGRATOR_VELOCITY_VERLET == 1, "unexpected Verlet value");
_Static_assert(BG_INTEGRATOR_LANGEVIN_BAOAB == 2, "unexpected BAOAB value");
_Static_assert(sizeof(bg_context_options) == 64, "context options ABI changed");
_Static_assert(BG_PERIODIC_AXIS_X == UINT32_C(1), "unexpected periodic X bit");
_Static_assert(BG_PERIODIC_AXIS_Y == UINT32_C(2), "unexpected periodic Y bit");
_Static_assert(BG_PERIODIC_AXIS_Z == UINT32_C(4), "unexpected periodic Z bit");
_Static_assert(BG_PERIODIC_AXES_ALL == UINT32_C(7), "unexpected periodic axes mask");

#if UINTPTR_MAX == UINT64_MAX
_Static_assert(
    sizeof(bg_docking_fixed64_source_evidence_v1) == 112,
    "fixed64 source evidence ABI changed");
_Static_assert(
    sizeof(bg_docking_fixed64_exact_source_evidence_v1) == 320,
    "fixed64 exact source evidence ABI changed");
_Static_assert(
    sizeof(bg_docking_fixed64_atomic_feature_evidence_v1) == 56,
    "fixed64 atomic feature evidence ABI changed");
_Static_assert(
    sizeof(bg_docking_fixed64_indexed_source_evidence_v1) == 136,
    "fixed64 indexed source evidence ABI changed");
_Static_assert(
    sizeof(bg_docking_fixed64_conformer_source_evidence_v1) == 136,
    "fixed64 conformer source evidence ABI changed");
_Static_assert(
    sizeof(bg_docking_fixed64_allocation_input_v1) == 456,
    "fixed64 allocation input ABI changed");
_Static_assert(
    sizeof(bg_docking_fixed64_requirement_v1) == 24,
    "fixed64 requirement ABI changed");
_Static_assert(
    sizeof(bg_docking_fixed64_missing_feature_v1) == 24,
    "fixed64 missing feature ABI changed");
_Static_assert(
    sizeof(bg_docking_fixed64_allocation_row_v1) == 384,
    "fixed64 allocation row ABI changed");
_Static_assert(
    sizeof(bg_docking_fixed64_allocation_output_v1) == 184,
    "fixed64 allocation output ABI changed");
_Static_assert(
    sizeof(bg_docking_geometric_admission_context_soa_v1) == 320,
    "geometric-admission context ABI changed");
_Static_assert(
    sizeof(bg_docking_geometric_admission_candidate_batch_soa_v1) == 96,
    "geometric-admission candidate batch ABI changed");
_Static_assert(
    sizeof(bg_docking_geometric_admission_row_v1) == 144,
    "geometric-admission row ABI changed");
_Static_assert(
    sizeof(bg_docking_geometric_admission_output_v1) == 80,
    "geometric-admission output ABI changed");
_Static_assert(
    sizeof(bg_docking_scorer_v1_context_soa_v1) == 608,
    "ScorerV1 context ABI changed");
_Static_assert(
    sizeof(bg_docking_scorer_v1_candidate_batch_soa_v1) == 96,
    "ScorerV1 candidate batch ABI changed");
_Static_assert(
    sizeof(bg_docking_scorer_v1_row_v1) == 160,
    "ScorerV1 row ABI changed");
_Static_assert(
    sizeof(bg_docking_scorer_v1_output_v1) == 72,
    "ScorerV1 output ABI changed");
_Static_assert(
    sizeof(bg_docking_pose_validity_context_soa_v1) == 560,
    "pose-validity context ABI changed");
_Static_assert(
    sizeof(bg_docking_pose_validity_candidate_batch_soa_v1) == 136,
    "pose-validity candidate batch ABI changed");
_Static_assert(
    sizeof(bg_docking_pose_validity_row_v1) == 240,
    "pose-validity row ABI changed");
_Static_assert(
    sizeof(bg_docking_pose_validity_output_v1) == 72,
    "pose-validity output ABI changed");
_Static_assert(
    sizeof(bg_docking_stable_top_k_input_v1) == 80,
    "stable Top-K input ABI changed");
_Static_assert(
    sizeof(bg_docking_stable_top_k_row_v1) == 88,
    "stable Top-K row ABI changed");
_Static_assert(
    sizeof(bg_docking_stable_top_k_output_v1) == 128,
    "stable Top-K output ABI changed");
_Static_assert(
    sizeof(bg_docking_rmsd_cluster_input_v1) == 120,
    "RMSD-cluster input ABI changed");
_Static_assert(
    sizeof(bg_docking_rmsd_cluster_row_v1) == 112,
    "RMSD-cluster row ABI changed");
_Static_assert(
    offsetof(bg_docking_rmsd_cluster_row_v1, reserved1) == 36,
    "bad RMSD-cluster reserved1 offset");
_Static_assert(
    sizeof(bg_docking_rmsd_cluster_output_v1) == 128,
    "RMSD-cluster output ABI changed");
_Static_assert(
    sizeof(bg_docking_rigid_v2_config_v1) == 88,
    "rigid V2 config ABI changed");
_Static_assert(
    sizeof(bg_docking_rigid_v3_config_v1) == 168,
    "rigid V3 config ABI changed");
_Static_assert(
    sizeof(bg_docking_rigid_refinement_context_soa_v1) == 592,
    "rigid-refinement context ABI changed");
_Static_assert(
    sizeof(bg_docking_rigid_refinement_candidate_batch_soa_v1) == 136,
    "rigid-refinement batch ABI changed");
_Static_assert(
    sizeof(bg_docking_rigid_refinement_evidence_v1) == 176,
    "rigid-refinement evidence ABI changed");
_Static_assert(
    sizeof(bg_docking_rigid_refinement_row_v1) == 792,
    "rigid-refinement row ABI changed");
_Static_assert(
    sizeof(bg_docking_rigid_refinement_output_v1) == 224,
    "rigid-refinement output ABI changed");
_Static_assert(
    sizeof(bg_docking_torsion_v7_context_soa_v1) == 328,
    "torsion V7 context ABI changed");
_Static_assert(
    sizeof(bg_docking_torsion_v7_candidate_batch_soa_v1) == 184,
    "torsion V7 candidate batch ABI changed");
_Static_assert(
    sizeof(bg_docking_torsion_v7_row_v1) == 256,
    "torsion V7 row ABI changed");
_Static_assert(
    sizeof(bg_docking_torsion_v7_move_v1) == 88,
    "torsion V7 move ABI changed");
_Static_assert(
    sizeof(bg_docking_torsion_v7_output_v1) == 216,
    "torsion V7 output ABI changed");
_Static_assert(
    sizeof(bg_docking_fixed64_refinement_input_v1) == 200,
    "fixed64 refinement input ABI changed");
_Static_assert(
    sizeof(bg_docking_fixed64_refinement_row_v1) == 104,
    "fixed64 refinement row ABI changed");
_Static_assert(
    sizeof(bg_docking_fixed64_refinement_output_v1) == 200,
    "fixed64 refinement output ABI changed");
_Static_assert(sizeof(bg_forcefield_soa_v1) == 352, "force-field SoA ABI changed");
_Static_assert(offsetof(bg_forcefield_soa_v1, struct_size) == 0, "bad struct_size offset");
_Static_assert(offsetof(bg_forcefield_soa_v1, abi_version) == 4, "bad abi_version offset");
_Static_assert(offsetof(bg_forcefield_soa_v1, atom_count) == 8, "bad atom_count offset");
_Static_assert(offsetof(bg_forcefield_soa_v1, unit_system) == 16, "bad unit_system offset");
_Static_assert(
    offsetof(bg_forcefield_soa_v1, periodic_axes_mask) == 20,
    "bad periodic_axes_mask offset");
_Static_assert(offsetof(bg_forcefield_soa_v1, sigma_angstrom) == 24, "bad sigma offset");
_Static_assert(
    offsetof(bg_forcefield_soa_v1, epsilon_kcal_per_mol) == 32,
    "bad epsilon offset");
_Static_assert(offsetof(bg_forcefield_soa_v1, bond_count) == 40, "bad bond_count offset");
_Static_assert(offsetof(bg_forcefield_soa_v1, bond_atom_i) == 48, "bad bond i offset");
_Static_assert(offsetof(bg_forcefield_soa_v1, bond_atom_j) == 56, "bad bond j offset");
_Static_assert(
    offsetof(bg_forcefield_soa_v1, bond_equilibrium_angstrom) == 64,
    "bad bond equilibrium offset");
_Static_assert(
    offsetof(bg_forcefield_soa_v1, bond_force_constant_kcal_per_mol_angstrom2) == 72,
    "bad bond force constant offset");
_Static_assert(offsetof(bg_forcefield_soa_v1, angle_count) == 80, "bad angle_count offset");
_Static_assert(offsetof(bg_forcefield_soa_v1, angle_atom_i) == 88, "bad angle i offset");
_Static_assert(offsetof(bg_forcefield_soa_v1, angle_atom_j) == 96, "bad angle j offset");
_Static_assert(offsetof(bg_forcefield_soa_v1, angle_atom_k) == 104, "bad angle k offset");
_Static_assert(
    offsetof(bg_forcefield_soa_v1, angle_equilibrium_radians) == 112,
    "bad angle equilibrium offset");
_Static_assert(
    offsetof(bg_forcefield_soa_v1, angle_force_constant_kcal_per_mol_radian2) == 120,
    "bad angle force constant offset");
_Static_assert(
    offsetof(bg_forcefield_soa_v1, torsion_count) == 128,
    "bad torsion_count offset");
_Static_assert(
    offsetof(bg_forcefield_soa_v1, torsion_atom_i) == 136,
    "bad torsion i offset");
_Static_assert(
    offsetof(bg_forcefield_soa_v1, torsion_atom_j) == 144,
    "bad torsion j offset");
_Static_assert(
    offsetof(bg_forcefield_soa_v1, torsion_atom_k) == 152,
    "bad torsion k offset");
_Static_assert(
    offsetof(bg_forcefield_soa_v1, torsion_atom_l) == 160,
    "bad torsion l offset");
_Static_assert(
    offsetof(bg_forcefield_soa_v1, torsion_periodicity) == 168,
    "bad torsion periodicity offset");
_Static_assert(
    offsetof(bg_forcefield_soa_v1, torsion_phase_radians) == 176,
    "bad torsion phase offset");
_Static_assert(
    offsetof(bg_forcefield_soa_v1, torsion_amplitude_kcal_per_mol) == 184,
    "bad torsion amplitude offset");
_Static_assert(
    offsetof(bg_forcefield_soa_v1, exclusion_count) == 192,
    "bad exclusion_count offset");
_Static_assert(
    offsetof(bg_forcefield_soa_v1, exclusion_atom_i) == 200,
    "bad exclusion i offset");
_Static_assert(
    offsetof(bg_forcefield_soa_v1, exclusion_atom_j) == 208,
    "bad exclusion j offset");
_Static_assert(
    offsetof(bg_forcefield_soa_v1, pair_scale_count) == 216,
    "bad pair_scale_count offset");
_Static_assert(
    offsetof(bg_forcefield_soa_v1, pair_scale_atom_i) == 224,
    "bad pair scale i offset");
_Static_assert(
    offsetof(bg_forcefield_soa_v1, pair_scale_atom_j) == 232,
    "bad pair scale j offset");
_Static_assert(
    offsetof(bg_forcefield_soa_v1, pair_scale_lennard_jones) == 240,
    "bad pair LJ scale offset");
_Static_assert(
    offsetof(bg_forcefield_soa_v1, pair_scale_coulomb) == 248,
    "bad pair Coulomb scale offset");
_Static_assert(
    offsetof(bg_forcefield_soa_v1, cell_lengths_angstrom) == 256,
    "bad cell lengths offset");
_Static_assert(
    offsetof(bg_forcefield_soa_v1, cutoff_angstrom) == 280,
    "bad cutoff offset");
_Static_assert(
    offsetof(bg_forcefield_soa_v1, switch_start_angstrom) == 288,
    "bad switch start offset");
_Static_assert(offsetof(bg_forcefield_soa_v1, dielectric) == 296, "bad dielectric offset");
_Static_assert(
    offsetof(bg_forcefield_soa_v1, screening_kappa_per_angstrom) == 304,
    "bad screening kappa offset");
_Static_assert(
    offsetof(bg_forcefield_soa_v1, minimum_pair_distance_angstrom) == 312,
    "bad minimum distance offset");
_Static_assert(offsetof(bg_forcefield_soa_v1, reserved) == 320, "bad reserved offset");

_Static_assert(sizeof(bg_force_soa_v1) == 88, "force output SoA ABI changed");
_Static_assert(offsetof(bg_force_soa_v1, struct_size) == 0, "bad force struct_size offset");
_Static_assert(offsetof(bg_force_soa_v1, abi_version) == 4, "bad force abi_version offset");
_Static_assert(
    offsetof(bg_force_soa_v1, particle_capacity) == 8,
    "bad force capacity offset");
_Static_assert(offsetof(bg_force_soa_v1, particle_count) == 16, "bad force count offset");
_Static_assert(offsetof(bg_force_soa_v1, unit_system) == 24, "bad force units offset");
_Static_assert(offsetof(bg_force_soa_v1, reserved0) == 28, "bad force reserved0 offset");
_Static_assert(
    offsetof(bg_force_soa_v1, x_kcal_per_mol_angstrom) == 32,
    "bad force x offset");
_Static_assert(
    offsetof(bg_force_soa_v1, y_kcal_per_mol_angstrom) == 40,
    "bad force y offset");
_Static_assert(
    offsetof(bg_force_soa_v1, z_kcal_per_mol_angstrom) == 48,
    "bad force z offset");
_Static_assert(offsetof(bg_force_soa_v1, reserved) == 56, "bad force reserved offset");

_Static_assert(
    sizeof(bg_distance_constraints_v1) == 104,
    "distance constraints ABI changed");
_Static_assert(
    offsetof(bg_distance_constraints_v1, constraint_count) == 8,
    "bad constraint count offset");
_Static_assert(
    offsetof(bg_distance_constraints_v1, atom_i) == 24,
    "bad constraint atom_i offset");
_Static_assert(
    offsetof(bg_distance_constraints_v1, distance_angstrom) == 40,
    "bad constraint distance offset");
_Static_assert(
    offsetof(bg_distance_constraints_v1, tolerance_angstrom) == 48,
    "bad constraint position tolerance offset");
_Static_assert(
    offsetof(
        bg_distance_constraints_v1,
        velocity_tolerance_angstrom_per_femtosecond) == 56,
    "bad constraint velocity tolerance offset");
_Static_assert(
    offsetof(bg_distance_constraints_v1, max_iterations) == 64,
    "bad constraint iteration offset");
_Static_assert(
    offsetof(bg_distance_constraints_v1, reserved) == 72,
    "bad constraint reserved offset");
#endif

_Static_assert(sizeof(bg_energy_components_v1) == 96, "energy output ABI changed");
_Static_assert(offsetof(bg_energy_components_v1, struct_size) == 0, "bad energy size offset");
_Static_assert(offsetof(bg_energy_components_v1, abi_version) == 4, "bad energy ABI offset");
_Static_assert(offsetof(bg_energy_components_v1, unit_system) == 8, "bad energy units offset");
_Static_assert(offsetof(bg_energy_components_v1, reserved0) == 12, "bad energy reserved0 offset");
_Static_assert(
    offsetof(bg_energy_components_v1, harmonic_bond_kcal_per_mol) == 16,
    "bad bond energy offset");
_Static_assert(
    offsetof(bg_energy_components_v1, harmonic_angle_kcal_per_mol) == 24,
    "bad angle energy offset");
_Static_assert(
    offsetof(bg_energy_components_v1, periodic_torsion_kcal_per_mol) == 32,
    "bad torsion energy offset");
_Static_assert(
    offsetof(bg_energy_components_v1, lennard_jones_kcal_per_mol) == 40,
    "bad LJ energy offset");
_Static_assert(
    offsetof(bg_energy_components_v1, coulomb_kcal_per_mol) == 48,
    "bad Coulomb energy offset");
_Static_assert(
    offsetof(bg_energy_components_v1, total_kcal_per_mol) == 56,
    "bad total energy offset");
_Static_assert(offsetof(bg_energy_components_v1, reserved) == 64, "bad energy reserved offset");

_Static_assert(sizeof(bg_simulation_options_v1) == 80, "simulation options ABI changed");
_Static_assert(offsetof(bg_simulation_options_v1, integrator) == 12, "bad integrator offset");
_Static_assert(
    offsetof(bg_simulation_options_v1, timestep_femtoseconds) == 16,
    "bad timestep offset");
_Static_assert(offsetof(bg_simulation_options_v1, random_seed) == 40, "bad seed offset");
_Static_assert(offsetof(bg_simulation_options_v1, reserved) == 48, "bad options reserved offset");
_Static_assert(sizeof(bg_minimizer_options_v1) == 112, "minimizer options ABI changed");
_Static_assert(
    offsetof(bg_minimizer_options_v1, max_iterations) == 16,
    "bad minimizer iterations offset");
_Static_assert(
    offsetof(bg_minimizer_options_v1, initial_step_angstrom2_mol_per_kcal) == 32,
    "bad minimizer initial step offset");
_Static_assert(
    offsetof(bg_minimizer_options_v1, reserved) == 80,
    "bad minimizer reserved offset");
_Static_assert(sizeof(bg_minimization_report_v1) == 88, "minimizer report ABI changed");
_Static_assert(
    offsetof(bg_minimization_report_v1, iterations) == 16,
    "bad minimizer report iterations offset");
_Static_assert(
    offsetof(bg_minimization_report_v1, reserved) == 56,
    "bad minimizer report reserved offset");
_Static_assert(sizeof(bg_dynamics_report_v1) == 104, "dynamics report ABI changed");
_Static_assert(
    offsetof(bg_dynamics_report_v1, steps_completed) == 16,
    "bad dynamics steps offset");
_Static_assert(
    offsetof(bg_dynamics_report_v1, temperature_kelvin) == 64,
    "bad dynamics temperature offset");
_Static_assert(
    offsetof(bg_dynamics_report_v1, reserved) == 72,
    "bad dynamics report reserved offset");

typedef bg_status(BG_CALL *bg_forcefield_soa_v1_init_fn)(
    bg_forcefield_soa_v1 *, size_t, uint32_t);
typedef bg_status(BG_CALL *bg_force_soa_v1_init_fn)(
    bg_force_soa_v1 *, size_t, uint32_t);
typedef bg_status(BG_CALL *bg_energy_components_v1_init_fn)(
    bg_energy_components_v1 *, size_t, uint32_t);
typedef bg_status(BG_CALL *bg_forcefield_create_fn)(
    const bg_forcefield_soa_v1 *, bg_forcefield **);
typedef void(BG_CALL *bg_forcefield_destroy_fn)(bg_forcefield *);
typedef bg_status(BG_CALL *bg_forcefield_get_atom_count_fn)(const bg_forcefield *, uint64_t *);
typedef bg_status(BG_CALL *bg_context_evaluate_fn)(
    const bg_context *,
    const bg_system *,
    const bg_forcefield *,
    bg_energy_components_v1 *,
    bg_force_soa_v1 *);
typedef bg_status(BG_CALL *bg_simulation_create_fn)(
    const bg_system *,
    const bg_forcefield *,
    const bg_distance_constraints_v1 *,
    const bg_simulation_options_v1 *,
    bg_simulation **);
typedef void(BG_CALL *bg_simulation_destroy_fn)(bg_simulation *);
typedef bg_status(BG_CALL *bg_context_minimize_fn)(
    const bg_context *,
    bg_simulation *,
    const bg_minimizer_options_v1 *,
    bg_minimization_report_v1 *);
typedef bg_status(BG_CALL *bg_context_integrate_fn)(
    const bg_context *, bg_simulation *, uint64_t, bg_dynamics_report_v1 *);
typedef bg_status(BG_CALL *bg_docking_rmsd_cluster_input_v1_init_fn)(
    bg_docking_rmsd_cluster_input_v1 *, size_t, uint32_t);
typedef bg_status(BG_CALL *bg_docking_rmsd_cluster_output_v1_init_fn)(
    bg_docking_rmsd_cluster_output_v1 *, size_t, uint32_t);
typedef bg_status(BG_CALL *bg_docking_cluster_direct_rmsd_fixed64_fn)(
    const bg_context *,
    const bg_docking_stable_top_k_v1 *,
    const bg_docking_rmsd_cluster_input_v1 *,
    bg_docking_rmsd_cluster_output_v1 *);

void betelgeuze_sys_header_c11_typecheck(void) {
    bg_context *context = NULL;
    bg_system *system = NULL;
    bg_forcefield *forcefield = NULL;
    bg_simulation *simulation = NULL;
    bg_context_options options;
    bg_particle_soa particles;
    bg_particle_soa_view view;
    bg_position_soa positions;
    bg_forcefield_soa_v1 forcefield_parameters;
    bg_force_soa_v1 forces;
    bg_energy_components_v1 energy;
    bg_distance_constraints_v1 constraints;
    bg_simulation_options_v1 simulation_options;
    bg_minimizer_options_v1 minimizer_options;
    bg_minimization_report_v1 minimization_report;
    bg_dynamics_report_v1 dynamics_report;
    bg_docking_rmsd_cluster_input_v1 rmsd_cluster_input;
    bg_docking_rmsd_cluster_row_v1 rmsd_cluster_row;
    bg_docking_rmsd_cluster_output_v1 rmsd_cluster_output;
    bg_forcefield_soa_v1_init_fn forcefield_init = bg_forcefield_soa_v1_init;
    bg_force_soa_v1_init_fn forces_init = bg_force_soa_v1_init;
    bg_energy_components_v1_init_fn energy_init = bg_energy_components_v1_init;
    bg_forcefield_create_fn forcefield_create = bg_forcefield_create;
    bg_forcefield_destroy_fn forcefield_destroy = bg_forcefield_destroy;
    bg_forcefield_get_atom_count_fn forcefield_get_atom_count = bg_forcefield_get_atom_count;
    bg_context_evaluate_fn context_evaluate = bg_context_evaluate;
    bg_simulation_create_fn simulation_create = bg_simulation_create;
    bg_simulation_destroy_fn simulation_destroy = bg_simulation_destroy;
    bg_context_minimize_fn context_minimize = bg_context_minimize;
    bg_context_integrate_fn context_integrate = bg_context_integrate;
    bg_docking_rmsd_cluster_input_v1_init_fn rmsd_cluster_input_init =
        bg_docking_rmsd_cluster_input_v1_init;
    bg_docking_rmsd_cluster_output_v1_init_fn rmsd_cluster_output_init =
        bg_docking_rmsd_cluster_output_v1_init;
    bg_docking_cluster_direct_rmsd_fixed64_fn rmsd_cluster =
        bg_docking_stable_top_k_v1_cluster_direct_rmsd_fixed64;
    (void)context;
    (void)system;
    (void)forcefield;
    (void)simulation;
    (void)options;
    (void)particles;
    (void)view;
    (void)positions;
    (void)forcefield_parameters;
    (void)forces;
    (void)energy;
    (void)constraints;
    (void)simulation_options;
    (void)minimizer_options;
    (void)minimization_report;
    (void)dynamics_report;
    (void)rmsd_cluster_input;
    (void)rmsd_cluster_row;
    (void)rmsd_cluster_output;
    (void)forcefield_init;
    (void)forces_init;
    (void)energy_init;
    (void)forcefield_create;
    (void)forcefield_destroy;
    (void)forcefield_get_atom_count;
    (void)context_evaluate;
    (void)simulation_create;
    (void)simulation_destroy;
    (void)context_minimize;
    (void)context_integrate;
    (void)rmsd_cluster_input_init;
    (void)rmsd_cluster_output_init;
    (void)rmsd_cluster;
}
