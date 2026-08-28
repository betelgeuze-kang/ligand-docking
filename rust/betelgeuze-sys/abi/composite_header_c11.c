#include <betelgeuze/direct_ewald_composite.h>

#include <stddef.h>
#include <stdint.h>

_Static_assert(
    BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION == UINT32_C(1),
    "unexpected composite ABI version");
_Static_assert(
    BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION_MAJOR == UINT32_C(1),
    "unexpected composite ABI major version");
_Static_assert(
    BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION_MINOR == UINT32_C(0),
    "unexpected composite ABI minor version");

#if UINTPTR_MAX == UINT64_MAX
_Static_assert(
    sizeof(bg_direct_ewald_composite_energy_components_v1) == 144,
    "composite energy ABI changed");
_Static_assert(
    sizeof(bg_direct_ewald_composite_force_soa_v1) == 88,
    "composite force ABI changed");
#endif

_Static_assert(
    offsetof(bg_direct_ewald_composite_energy_components_v1, struct_size) == 0,
    "bad composite energy size offset");
_Static_assert(
    offsetof(bg_direct_ewald_composite_energy_components_v1, abi_version) == 4,
    "bad composite energy version offset");
_Static_assert(
    offsetof(bg_direct_ewald_composite_energy_components_v1, unit_system) == 8,
    "bad composite energy unit offset");
_Static_assert(
    offsetof(bg_direct_ewald_composite_energy_components_v1, reserved0) == 12,
    "bad composite energy reserved0 offset");
_Static_assert(
    offsetof(
        bg_direct_ewald_composite_energy_components_v1,
        short_harmonic_bond_kcal_per_mol) == 16,
    "bad composite short-energy offset");
_Static_assert(
    offsetof(
        bg_direct_ewald_composite_energy_components_v1,
        short_harmonic_angle_kcal_per_mol) == 24,
    "bad composite short-angle offset");
_Static_assert(
    offsetof(
        bg_direct_ewald_composite_energy_components_v1,
        short_periodic_torsion_kcal_per_mol) == 32,
    "bad composite short-torsion offset");
_Static_assert(
    offsetof(
        bg_direct_ewald_composite_energy_components_v1,
        short_lennard_jones_kcal_per_mol) == 40,
    "bad composite short-LJ offset");
_Static_assert(
    offsetof(
        bg_direct_ewald_composite_energy_components_v1,
        short_coulomb_kcal_per_mol) == 48,
    "bad composite short-Coulomb offset");
_Static_assert(
    offsetof(
        bg_direct_ewald_composite_energy_components_v1,
        short_total_kcal_per_mol) == 56,
    "bad composite short-total offset");
_Static_assert(
    offsetof(
        bg_direct_ewald_composite_energy_components_v1,
        ewald_real_space_kcal_per_mol) == 64,
    "bad composite Ewald-energy offset");
_Static_assert(
    offsetof(
        bg_direct_ewald_composite_energy_components_v1,
        ewald_reciprocal_space_kcal_per_mol) == 72,
    "bad composite Ewald-reciprocal offset");
_Static_assert(
    offsetof(
        bg_direct_ewald_composite_energy_components_v1,
        ewald_self_kcal_per_mol) == 80,
    "bad composite Ewald-self offset");
_Static_assert(
    offsetof(
        bg_direct_ewald_composite_energy_components_v1,
        ewald_pair_correction_kcal_per_mol) == 88,
    "bad composite Ewald-correction offset");
_Static_assert(
    offsetof(
        bg_direct_ewald_composite_energy_components_v1,
        ewald_total_kcal_per_mol) == 96,
    "bad composite Ewald-total offset");
_Static_assert(
    offsetof(
        bg_direct_ewald_composite_energy_components_v1,
        total_kcal_per_mol) == 104,
    "bad composite total-energy offset");
_Static_assert(
    offsetof(bg_direct_ewald_composite_energy_components_v1, reserved) == 112,
    "bad composite energy reserved offset");
_Static_assert(
    offsetof(bg_direct_ewald_composite_force_soa_v1, struct_size) == 0,
    "bad composite force size offset");
_Static_assert(
    offsetof(bg_direct_ewald_composite_force_soa_v1, abi_version) == 4,
    "bad composite force version offset");
_Static_assert(
    offsetof(bg_direct_ewald_composite_force_soa_v1, atom_capacity) == 8,
    "bad composite force capacity offset");
_Static_assert(
    offsetof(bg_direct_ewald_composite_force_soa_v1, atom_count) == 16,
    "bad composite force count offset");
_Static_assert(
    offsetof(bg_direct_ewald_composite_force_soa_v1, unit_system) == 24,
    "bad composite force unit offset");
_Static_assert(
    offsetof(bg_direct_ewald_composite_force_soa_v1, reserved0) == 28,
    "bad composite force reserved0 offset");
_Static_assert(
    offsetof(
        bg_direct_ewald_composite_force_soa_v1,
        x_kcal_per_mol_angstrom) == 32,
    "bad composite force channel offset");
_Static_assert(
    offsetof(
        bg_direct_ewald_composite_force_soa_v1,
        y_kcal_per_mol_angstrom) == 40,
    "bad composite force y-channel offset");
_Static_assert(
    offsetof(
        bg_direct_ewald_composite_force_soa_v1,
        z_kcal_per_mol_angstrom) == 48,
    "bad composite force z-channel offset");
_Static_assert(
    offsetof(bg_direct_ewald_composite_force_soa_v1, reserved) == 56,
    "bad composite force reserved offset");

typedef uint32_t(BG_CALL *bg_composite_version_fn)(void);
typedef const char *(BG_CALL *bg_composite_string_fn)(void);
typedef bg_status(BG_CALL *bg_composite_energy_init_fn)(
    bg_direct_ewald_composite_energy_components_v1 *, size_t, uint32_t);
typedef bg_status(BG_CALL *bg_composite_force_init_fn)(
    bg_direct_ewald_composite_force_soa_v1 *, size_t, uint32_t);
typedef bg_status(BG_CALL *bg_composite_evaluate_fn)(
    const bg_context *,
    const bg_system *,
    const bg_forcefield *,
    const bg_direct_ewald_model_v1 *,
    bg_direct_ewald_composite_energy_components_v1 *,
    bg_direct_ewald_composite_force_soa_v1 *,
    bg_direct_ewald_error_v1 *);

void betelgeuze_sys_composite_header_c11_typecheck(void) {
    bg_direct_ewald_composite_energy_components_v1 energy;
    bg_direct_ewald_composite_force_soa_v1 forces;
    bg_composite_version_fn version =
        bg_direct_ewald_composite_abi_version;
    bg_composite_version_fn version_major =
        bg_direct_ewald_composite_abi_version_major;
    bg_composite_version_fn version_minor =
        bg_direct_ewald_composite_abi_version_minor;
    bg_composite_string_fn version_string =
        bg_direct_ewald_composite_abi_version_string;
    bg_composite_string_fn profile_id =
        bg_direct_ewald_composite_v1_profile_id;
    bg_composite_energy_init_fn energy_init =
        bg_direct_ewald_composite_energy_components_v1_init;
    bg_composite_force_init_fn force_init =
        bg_direct_ewald_composite_force_soa_v1_init;
    bg_composite_evaluate_fn evaluate =
        bg_context_evaluate_direct_ewald_composite_v1;

    (void)energy;
    (void)forces;
    (void)version;
    (void)version_major;
    (void)version_minor;
    (void)version_string;
    (void)profile_id;
    (void)energy_init;
    (void)force_init;
    (void)evaluate;
}
