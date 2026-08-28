#include <betelgeuze/particle_mesh_ewald_composite_dynamics.h>

#include <stddef.h>
#include <stdint.h>

_Static_assert(
    BG_PARTICLE_MESH_EWALD_COMPOSITE_DYNAMICS_ABI_VERSION == UINT32_C(1),
    "unexpected particle-mesh composite-dynamics ABI version");
_Static_assert(
    BG_PARTICLE_MESH_EWALD_COMPOSITE_DYNAMICS_ABI_VERSION_MAJOR ==
        UINT32_C(1),
    "unexpected particle-mesh composite-dynamics ABI major version");
_Static_assert(
    BG_PARTICLE_MESH_EWALD_COMPOSITE_DYNAMICS_ABI_VERSION_MINOR ==
        UINT32_C(0),
    "unexpected particle-mesh composite-dynamics ABI minor version");

#if UINTPTR_MAX == UINT64_MAX
_Static_assert(
    sizeof(bg_distance_constraints_v1) == 104,
    "reused constraints ABI changed");
_Static_assert(
    sizeof(bg_simulation_options_v1) == 80,
    "reused simulation-options ABI changed");
_Static_assert(
    sizeof(bg_dynamics_report_v1) == 104,
    "reused dynamics-report ABI changed");
#endif

_Static_assert(
    offsetof(bg_distance_constraints_v1, constraint_count) == 8,
    "bad reused constraint-count offset");
_Static_assert(
    offsetof(bg_simulation_options_v1, integrator) == 12,
    "bad reused integrator offset");
_Static_assert(
    offsetof(bg_simulation_options_v1, timestep_femtoseconds) == 16,
    "bad reused timestep offset");
_Static_assert(
    offsetof(bg_dynamics_report_v1, steps_completed) == 16,
    "bad reused report step-count offset");
_Static_assert(
    offsetof(bg_dynamics_report_v1, absolute_step) == 24,
    "bad reused report absolute-step offset");
_Static_assert(
    offsetof(bg_dynamics_report_v1, potential_kcal_per_mol) == 40,
    "bad reused report potential offset");

typedef uint32_t(BG_CALL *bg_pme_composite_dynamics_version_fn)(void);
typedef const char *(BG_CALL *bg_pme_composite_dynamics_string_fn)(void);
typedef bg_status(BG_CALL *bg_pme_composite_dynamics_create_fn)(
    const bg_system *,
    const bg_forcefield *,
    const bg_direct_ewald_model_v1 *,
    const bg_particle_mesh_reciprocal_model_v1 *,
    const bg_distance_constraints_v1 *,
    const bg_simulation_options_v1 *,
    bg_particle_mesh_ewald_composite_simulation_v1 **,
    bg_direct_ewald_error_v1 *);
typedef void(BG_CALL *bg_pme_composite_dynamics_destroy_fn)(
    bg_particle_mesh_ewald_composite_simulation_v1 *);
typedef bg_status(BG_CALL *bg_pme_composite_dynamics_particles_fn)(
    const bg_particle_mesh_ewald_composite_simulation_v1 *,
    bg_particle_soa_view *);
typedef bg_status(BG_CALL *bg_pme_composite_dynamics_step_fn)(
    const bg_particle_mesh_ewald_composite_simulation_v1 *, uint64_t *);
typedef bg_status(BG_CALL *bg_pme_composite_dynamics_integrate_fn)(
    const bg_context *,
    bg_particle_mesh_ewald_composite_simulation_v1 *,
    uint64_t,
    bg_dynamics_report_v1 *,
    bg_direct_ewald_error_v1 *);
typedef bg_status(BG_CALL *bg_pme_composite_dynamics_checkpoint_size_fn)(
    const bg_particle_mesh_ewald_composite_simulation_v1 *, uint64_t *);
typedef bg_status(BG_CALL *bg_pme_composite_dynamics_checkpoint_write_fn)(
    const bg_particle_mesh_ewald_composite_simulation_v1 *,
    void *,
    uint64_t,
    uint64_t *);
typedef bg_status(BG_CALL *bg_pme_composite_dynamics_checkpoint_load_fn)(
    bg_particle_mesh_ewald_composite_simulation_v1 *,
    const void *,
    uint64_t);

void betelgeuze_sys_particle_mesh_ewald_composite_dynamics_header_c11_typecheck(
    void) {
    bg_particle_mesh_ewald_composite_simulation_v1 *simulation = NULL;
    bg_pme_composite_dynamics_version_fn version =
        bg_particle_mesh_ewald_composite_dynamics_abi_version;
    bg_pme_composite_dynamics_version_fn version_major =
        bg_particle_mesh_ewald_composite_dynamics_abi_version_major;
    bg_pme_composite_dynamics_version_fn version_minor =
        bg_particle_mesh_ewald_composite_dynamics_abi_version_minor;
    bg_pme_composite_dynamics_string_fn version_string =
        bg_particle_mesh_ewald_composite_dynamics_abi_version_string;
    bg_pme_composite_dynamics_string_fn profile_id =
        bg_particle_mesh_ewald_composite_dynamics_v1_profile_id;
    bg_pme_composite_dynamics_create_fn create =
        bg_particle_mesh_ewald_composite_simulation_v1_create;
    bg_pme_composite_dynamics_destroy_fn destroy =
        bg_particle_mesh_ewald_composite_simulation_v1_destroy;
    bg_pme_composite_dynamics_particles_fn particles =
        bg_particle_mesh_ewald_composite_simulation_v1_get_particles;
    bg_pme_composite_dynamics_step_fn absolute_step =
        bg_particle_mesh_ewald_composite_simulation_v1_get_absolute_step;
    bg_pme_composite_dynamics_integrate_fn integrate =
        bg_context_integrate_particle_mesh_ewald_composite_v1;
    bg_pme_composite_dynamics_checkpoint_size_fn checkpoint_size =
        bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_size;
    bg_pme_composite_dynamics_checkpoint_write_fn checkpoint_write =
        bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_write;
    bg_pme_composite_dynamics_checkpoint_load_fn checkpoint_load =
        bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_load;

    (void)simulation;
    (void)version;
    (void)version_major;
    (void)version_minor;
    (void)version_string;
    (void)profile_id;
    (void)create;
    (void)destroy;
    (void)particles;
    (void)absolute_step;
    (void)integrate;
    (void)checkpoint_size;
    (void)checkpoint_write;
    (void)checkpoint_load;
}
