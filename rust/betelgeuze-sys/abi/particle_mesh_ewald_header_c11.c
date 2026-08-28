#include <betelgeuze/particle_mesh_ewald.h>

#include <stddef.h>
#include <stdint.h>

_Static_assert(
    BG_PARTICLE_MESH_EWALD_ABI_VERSION == UINT32_C(1),
    "unexpected particle-mesh Ewald ABI version");
_Static_assert(
    BG_PARTICLE_MESH_EWALD_ABI_VERSION_MAJOR == UINT32_C(1),
    "unexpected particle-mesh Ewald ABI major version");
_Static_assert(
    BG_PARTICLE_MESH_EWALD_ABI_VERSION_MINOR == UINT32_C(0),
    "unexpected particle-mesh Ewald ABI minor version");

#if UINTPTR_MAX == UINT64_MAX
_Static_assert(
    sizeof(bg_particle_mesh_ewald_energy_components_v1) == 88,
    "particle-mesh Ewald energy ABI changed");
_Static_assert(
    sizeof(bg_particle_mesh_ewald_force_soa_v1) == 88,
    "particle-mesh Ewald force ABI changed");
#endif

_Static_assert(
    offsetof(bg_particle_mesh_ewald_energy_components_v1, struct_size) == 0,
    "bad particle-mesh Ewald energy size offset");
_Static_assert(
    offsetof(bg_particle_mesh_ewald_energy_components_v1, abi_version) == 4,
    "bad particle-mesh Ewald energy version offset");
_Static_assert(
    offsetof(bg_particle_mesh_ewald_energy_components_v1, unit_system) == 8,
    "bad particle-mesh Ewald energy unit offset");
_Static_assert(
    offsetof(bg_particle_mesh_ewald_energy_components_v1, reserved0) == 12,
    "bad particle-mesh Ewald energy reserved0 offset");
_Static_assert(
    offsetof(
        bg_particle_mesh_ewald_energy_components_v1,
        real_space_kcal_per_mol) == 16,
    "bad particle-mesh Ewald real-space offset");
_Static_assert(
    offsetof(
        bg_particle_mesh_ewald_energy_components_v1,
        reciprocal_space_kcal_per_mol) == 24,
    "bad particle-mesh Ewald reciprocal-space offset");
_Static_assert(
    offsetof(bg_particle_mesh_ewald_energy_components_v1, self_kcal_per_mol) ==
        32,
    "bad particle-mesh Ewald self offset");
_Static_assert(
    offsetof(
        bg_particle_mesh_ewald_energy_components_v1,
        pair_correction_kcal_per_mol) == 40,
    "bad particle-mesh Ewald pair-correction offset");
_Static_assert(
    offsetof(bg_particle_mesh_ewald_energy_components_v1, total_kcal_per_mol) ==
        48,
    "bad particle-mesh Ewald total offset");
_Static_assert(
    offsetof(bg_particle_mesh_ewald_energy_components_v1, reserved) == 56,
    "bad particle-mesh Ewald energy reserved offset");

_Static_assert(
    offsetof(bg_particle_mesh_ewald_force_soa_v1, struct_size) == 0,
    "bad particle-mesh Ewald force size offset");
_Static_assert(
    offsetof(bg_particle_mesh_ewald_force_soa_v1, abi_version) == 4,
    "bad particle-mesh Ewald force version offset");
_Static_assert(
    offsetof(bg_particle_mesh_ewald_force_soa_v1, atom_capacity) == 8,
    "bad particle-mesh Ewald force capacity offset");
_Static_assert(
    offsetof(bg_particle_mesh_ewald_force_soa_v1, atom_count) == 16,
    "bad particle-mesh Ewald force count offset");
_Static_assert(
    offsetof(bg_particle_mesh_ewald_force_soa_v1, unit_system) == 24,
    "bad particle-mesh Ewald force unit offset");
_Static_assert(
    offsetof(bg_particle_mesh_ewald_force_soa_v1, reserved0) == 28,
    "bad particle-mesh Ewald force reserved0 offset");
_Static_assert(
    offsetof(
        bg_particle_mesh_ewald_force_soa_v1,
        x_kcal_per_mol_angstrom) == 32,
    "bad particle-mesh Ewald force x offset");
_Static_assert(
    offsetof(
        bg_particle_mesh_ewald_force_soa_v1,
        y_kcal_per_mol_angstrom) == 40,
    "bad particle-mesh Ewald force y offset");
_Static_assert(
    offsetof(
        bg_particle_mesh_ewald_force_soa_v1,
        z_kcal_per_mol_angstrom) == 48,
    "bad particle-mesh Ewald force z offset");
_Static_assert(
    offsetof(bg_particle_mesh_ewald_force_soa_v1, reserved) == 56,
    "bad particle-mesh Ewald force reserved offset");

typedef uint32_t(BG_CALL *bg_particle_mesh_ewald_version_fn)(void);
typedef const char *(BG_CALL *bg_particle_mesh_ewald_string_fn)(void);
typedef bg_status(BG_CALL *bg_particle_mesh_ewald_energy_init_fn)(
    bg_particle_mesh_ewald_energy_components_v1 *, size_t, uint32_t);
typedef bg_status(BG_CALL *bg_particle_mesh_ewald_force_init_fn)(
    bg_particle_mesh_ewald_force_soa_v1 *, size_t, uint32_t);
typedef bg_status(BG_CALL *bg_particle_mesh_ewald_evaluate_fn)(
    const bg_context *,
    const bg_system *,
    const bg_direct_ewald_model_v1 *,
    const bg_particle_mesh_reciprocal_model_v1 *,
    bg_particle_mesh_ewald_energy_components_v1 *,
    bg_particle_mesh_ewald_force_soa_v1 *,
    bg_direct_ewald_error_v1 *);

void betelgeuze_sys_particle_mesh_ewald_header_c11_typecheck(void) {
    bg_particle_mesh_ewald_energy_components_v1 energy;
    bg_particle_mesh_ewald_force_soa_v1 forces;
    bg_particle_mesh_ewald_version_fn version =
        bg_particle_mesh_ewald_abi_version;
    bg_particle_mesh_ewald_version_fn version_major =
        bg_particle_mesh_ewald_abi_version_major;
    bg_particle_mesh_ewald_version_fn version_minor =
        bg_particle_mesh_ewald_abi_version_minor;
    bg_particle_mesh_ewald_string_fn version_string =
        bg_particle_mesh_ewald_abi_version_string;
    bg_particle_mesh_ewald_string_fn profile_id =
        bg_particle_mesh_ewald_v1_profile_id;
    bg_particle_mesh_ewald_energy_init_fn energy_init =
        bg_particle_mesh_ewald_energy_components_v1_init;
    bg_particle_mesh_ewald_force_init_fn force_init =
        bg_particle_mesh_ewald_force_soa_v1_init;
    bg_particle_mesh_ewald_evaluate_fn evaluate =
        bg_context_evaluate_particle_mesh_ewald_v1;

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
