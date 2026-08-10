#include <betelgeuze/engine.h>

#include <stddef.h>
#include <stdint.h>

_Static_assert(BG_ABI_VERSION == UINT32_C(1), "unexpected ABI version");
_Static_assert(BG_ABI_VERSION_MAJOR == UINT32_C(1), "unexpected ABI major version");
_Static_assert(BG_ABI_VERSION_MINOR == UINT32_C(2), "unexpected ABI minor version");
_Static_assert(BG_STATUS_OK == 0, "unexpected success status");
_Static_assert(BG_STATUS_NUMERICAL_ERROR == 10, "unexpected numerical status");
_Static_assert(BG_BACKEND_CPU == 1, "unexpected CPU backend value");
_Static_assert(BG_BACKEND_HIP == 2, "unexpected HIP backend value");
_Static_assert(
    BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL == 1,
    "unexpected canonical unit-system value");
_Static_assert(sizeof(bg_status) == sizeof(int32_t), "bg_status width changed");
_Static_assert(sizeof(bg_backend) == sizeof(int32_t), "bg_backend width changed");
_Static_assert(
    sizeof(bg_unit_system) == sizeof(int32_t),
    "bg_unit_system width changed");
_Static_assert(sizeof(bg_context_options) == 64, "context options ABI changed");
_Static_assert(BG_PERIODIC_AXIS_X == UINT32_C(1), "unexpected periodic X bit");
_Static_assert(BG_PERIODIC_AXIS_Y == UINT32_C(2), "unexpected periodic Y bit");
_Static_assert(BG_PERIODIC_AXIS_Z == UINT32_C(4), "unexpected periodic Z bit");
_Static_assert(BG_PERIODIC_AXES_ALL == UINT32_C(7), "unexpected periodic axes mask");

#if UINTPTR_MAX == UINT64_MAX
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

typedef bg_status(BG_CALL *bg_forcefield_soa_v1_init_fn)(bg_forcefield_soa_v1 *);
typedef bg_status(BG_CALL *bg_force_soa_v1_init_fn)(bg_force_soa_v1 *);
typedef bg_status(BG_CALL *bg_energy_components_v1_init_fn)(bg_energy_components_v1 *);
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

void betelgeuze_sys_header_c11_typecheck(void) {
    bg_context *context = NULL;
    bg_system *system = NULL;
    bg_forcefield *forcefield = NULL;
    bg_context_options options;
    bg_particle_soa particles;
    bg_particle_soa_view view;
    bg_position_soa positions;
    bg_forcefield_soa_v1 forcefield_parameters;
    bg_force_soa_v1 forces;
    bg_energy_components_v1 energy;
    bg_forcefield_soa_v1_init_fn forcefield_init = bg_forcefield_soa_v1_init;
    bg_force_soa_v1_init_fn forces_init = bg_force_soa_v1_init;
    bg_energy_components_v1_init_fn energy_init = bg_energy_components_v1_init;
    bg_forcefield_create_fn forcefield_create = bg_forcefield_create;
    bg_forcefield_destroy_fn forcefield_destroy = bg_forcefield_destroy;
    bg_forcefield_get_atom_count_fn forcefield_get_atom_count = bg_forcefield_get_atom_count;
    bg_context_evaluate_fn context_evaluate = bg_context_evaluate;
    (void)context;
    (void)system;
    (void)forcefield;
    (void)options;
    (void)particles;
    (void)view;
    (void)positions;
    (void)forcefield_parameters;
    (void)forces;
    (void)energy;
    (void)forcefield_init;
    (void)forces_init;
    (void)energy_init;
    (void)forcefield_create;
    (void)forcefield_destroy;
    (void)forcefield_get_atom_count;
    (void)context_evaluate;
}
