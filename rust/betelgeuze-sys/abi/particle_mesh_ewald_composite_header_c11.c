#include <betelgeuze/particle_mesh_ewald_composite.h>

#include <stddef.h>
#include <stdint.h>

_Static_assert(
    BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION == UINT32_C(1),
    "unexpected particle-mesh Ewald composite ABI version");
_Static_assert(
    BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION_MAJOR == UINT32_C(1),
    "unexpected particle-mesh Ewald composite ABI major version");
_Static_assert(
    BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION_MINOR == UINT32_C(0),
    "unexpected particle-mesh Ewald composite ABI minor version");

#if UINTPTR_MAX == UINT64_MAX
_Static_assert(
    sizeof(bg_particle_mesh_ewald_composite_energy_components_v1) == 144,
    "particle-mesh Ewald composite energy ABI changed");
_Static_assert(
    sizeof(bg_particle_mesh_ewald_composite_force_soa_v1) == 88,
    "particle-mesh Ewald composite force ABI changed");
#endif

_Static_assert(
    offsetof(
        bg_particle_mesh_ewald_composite_energy_components_v1,
        struct_size) == 0,
    "bad particle-mesh Ewald composite energy size offset");
_Static_assert(
    offsetof(
        bg_particle_mesh_ewald_composite_energy_components_v1,
        abi_version) == 4,
    "bad particle-mesh Ewald composite energy version offset");
_Static_assert(
    offsetof(
        bg_particle_mesh_ewald_composite_energy_components_v1,
        unit_system) == 8,
    "bad particle-mesh Ewald composite energy unit offset");
_Static_assert(
    offsetof(
        bg_particle_mesh_ewald_composite_energy_components_v1,
        reserved0) == 12,
    "bad particle-mesh Ewald composite energy reserved0 offset");
_Static_assert(
    offsetof(
        bg_particle_mesh_ewald_composite_energy_components_v1,
        short_harmonic_bond_kcal_per_mol) == 16,
    "bad particle-mesh Ewald composite short-bond offset");
_Static_assert(
    offsetof(
        bg_particle_mesh_ewald_composite_energy_components_v1,
        short_harmonic_angle_kcal_per_mol) == 24,
    "bad particle-mesh Ewald composite short-angle offset");
_Static_assert(
    offsetof(
        bg_particle_mesh_ewald_composite_energy_components_v1,
        short_periodic_torsion_kcal_per_mol) == 32,
    "bad particle-mesh Ewald composite short-torsion offset");
_Static_assert(
    offsetof(
        bg_particle_mesh_ewald_composite_energy_components_v1,
        short_lennard_jones_kcal_per_mol) == 40,
    "bad particle-mesh Ewald composite short-LJ offset");
_Static_assert(
    offsetof(
        bg_particle_mesh_ewald_composite_energy_components_v1,
        short_coulomb_kcal_per_mol) == 48,
    "bad particle-mesh Ewald composite short-Coulomb offset");
_Static_assert(
    offsetof(
        bg_particle_mesh_ewald_composite_energy_components_v1,
        short_total_kcal_per_mol) == 56,
    "bad particle-mesh Ewald composite short-total offset");
_Static_assert(
    offsetof(
        bg_particle_mesh_ewald_composite_energy_components_v1,
        pme_real_space_kcal_per_mol) == 64,
    "bad particle-mesh Ewald composite PME-real offset");
_Static_assert(
    offsetof(
        bg_particle_mesh_ewald_composite_energy_components_v1,
        pme_reciprocal_space_kcal_per_mol) == 72,
    "bad particle-mesh Ewald composite PME-reciprocal offset");
_Static_assert(
    offsetof(
        bg_particle_mesh_ewald_composite_energy_components_v1,
        pme_self_kcal_per_mol) == 80,
    "bad particle-mesh Ewald composite PME-self offset");
_Static_assert(
    offsetof(
        bg_particle_mesh_ewald_composite_energy_components_v1,
        pme_pair_correction_kcal_per_mol) == 88,
    "bad particle-mesh Ewald composite PME-pair-correction offset");
_Static_assert(
    offsetof(
        bg_particle_mesh_ewald_composite_energy_components_v1,
        pme_total_kcal_per_mol) == 96,
    "bad particle-mesh Ewald composite PME-total offset");
_Static_assert(
    offsetof(
        bg_particle_mesh_ewald_composite_energy_components_v1,
        total_kcal_per_mol) == 104,
    "bad particle-mesh Ewald composite total offset");
_Static_assert(
    offsetof(
        bg_particle_mesh_ewald_composite_energy_components_v1,
        reserved) == 112,
    "bad particle-mesh Ewald composite energy reserved offset");

_Static_assert(
    offsetof(bg_particle_mesh_ewald_composite_force_soa_v1, struct_size) == 0,
    "bad particle-mesh Ewald composite force size offset");
_Static_assert(
    offsetof(bg_particle_mesh_ewald_composite_force_soa_v1, abi_version) == 4,
    "bad particle-mesh Ewald composite force version offset");
_Static_assert(
    offsetof(bg_particle_mesh_ewald_composite_force_soa_v1, atom_capacity) == 8,
    "bad particle-mesh Ewald composite force capacity offset");
_Static_assert(
    offsetof(bg_particle_mesh_ewald_composite_force_soa_v1, atom_count) == 16,
    "bad particle-mesh Ewald composite force count offset");
_Static_assert(
    offsetof(bg_particle_mesh_ewald_composite_force_soa_v1, unit_system) == 24,
    "bad particle-mesh Ewald composite force unit offset");
_Static_assert(
    offsetof(bg_particle_mesh_ewald_composite_force_soa_v1, reserved0) == 28,
    "bad particle-mesh Ewald composite force reserved0 offset");
_Static_assert(
    offsetof(
        bg_particle_mesh_ewald_composite_force_soa_v1,
        x_kcal_per_mol_angstrom) == 32,
    "bad particle-mesh Ewald composite force x offset");
_Static_assert(
    offsetof(
        bg_particle_mesh_ewald_composite_force_soa_v1,
        y_kcal_per_mol_angstrom) == 40,
    "bad particle-mesh Ewald composite force y offset");
_Static_assert(
    offsetof(
        bg_particle_mesh_ewald_composite_force_soa_v1,
        z_kcal_per_mol_angstrom) == 48,
    "bad particle-mesh Ewald composite force z offset");
_Static_assert(
    offsetof(bg_particle_mesh_ewald_composite_force_soa_v1, reserved) == 56,
    "bad particle-mesh Ewald composite force reserved offset");

typedef uint32_t(BG_CALL *bg_pme_composite_version_fn)(void);
typedef const char *(BG_CALL *bg_pme_composite_string_fn)(void);
typedef bg_status(BG_CALL *bg_pme_composite_energy_init_fn)(
    bg_particle_mesh_ewald_composite_energy_components_v1 *,
    size_t,
    uint32_t);
typedef bg_status(BG_CALL *bg_pme_composite_force_init_fn)(
    bg_particle_mesh_ewald_composite_force_soa_v1 *,
    size_t,
    uint32_t);
typedef bg_status(BG_CALL *bg_pme_composite_evaluate_fn)(
    const bg_context *,
    const bg_system *,
    const bg_forcefield *,
    const bg_direct_ewald_model_v1 *,
    const bg_particle_mesh_reciprocal_model_v1 *,
    bg_particle_mesh_ewald_composite_energy_components_v1 *,
    bg_particle_mesh_ewald_composite_force_soa_v1 *,
    bg_direct_ewald_error_v1 *);

void betelgeuze_sys_particle_mesh_ewald_composite_header_c11_typecheck(void) {
    bg_particle_mesh_ewald_composite_energy_components_v1 energy;
    bg_particle_mesh_ewald_composite_force_soa_v1 forces;
    bg_pme_composite_version_fn version =
        bg_particle_mesh_ewald_composite_abi_version;
    bg_pme_composite_version_fn version_major =
        bg_particle_mesh_ewald_composite_abi_version_major;
    bg_pme_composite_version_fn version_minor =
        bg_particle_mesh_ewald_composite_abi_version_minor;
    bg_pme_composite_string_fn version_string =
        bg_particle_mesh_ewald_composite_abi_version_string;
    bg_pme_composite_string_fn profile_id =
        bg_particle_mesh_ewald_composite_v1_profile_id;
    bg_pme_composite_energy_init_fn energy_init =
        bg_particle_mesh_ewald_composite_energy_components_v1_init;
    bg_pme_composite_force_init_fn force_init =
        bg_particle_mesh_ewald_composite_force_soa_v1_init;
    bg_pme_composite_evaluate_fn evaluate =
        bg_context_evaluate_particle_mesh_ewald_composite_v1;

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
