#ifndef BETELGEUZE_DIRECT_EWALD_COMPOSITE_DYNAMICS_H
#define BETELGEUZE_DIRECT_EWALD_COMPOSITE_DYNAMICS_H

/*
 * Betelgeuze deterministic short-range + direct-Ewald composite dynamics
 * ABI v1.
 *
 * This development boundary deep-owns the canonical molecular state, short-
 * range force field, direct-Ewald model, constraints, and Velocity-Verlet
 * configuration.  It is separately versioned from the frozen Engine,
 * direct-Ewald, and stateless composite ABIs.  It is not a PME, HIP,
 * production, performance, or scientific-authority interface.
 */

#include "betelgeuze/direct_ewald_composite.h"

#define BG_DIRECT_EWALD_COMPOSITE_DYNAMICS_ABI_VERSION_MAJOR UINT32_C(1)
#define BG_DIRECT_EWALD_COMPOSITE_DYNAMICS_ABI_VERSION_MINOR UINT32_C(0)
#define BG_DIRECT_EWALD_COMPOSITE_DYNAMICS_ABI_VERSION UINT32_C(1)

#if defined(__cplusplus)
extern "C" {
#endif

typedef struct bg_direct_ewald_composite_simulation_v1
    bg_direct_ewald_composite_simulation_v1;

BG_API uint32_t BG_CALL
bg_direct_ewald_composite_dynamics_abi_version(void) BG_NOEXCEPT;
BG_API uint32_t BG_CALL
bg_direct_ewald_composite_dynamics_abi_version_major(void) BG_NOEXCEPT;
BG_API uint32_t BG_CALL
bg_direct_ewald_composite_dynamics_abi_version_minor(void) BG_NOEXCEPT;
BG_API const char *BG_CALL
bg_direct_ewald_composite_dynamics_abi_version_string(void) BG_NOEXCEPT;

BG_API const char *BG_CALL
bg_direct_ewald_composite_dynamics_v1_profile_id(void) BG_NOEXCEPT;

/*
 * Creation borrows every input only for the duration of the call and returns
 * an independent owner.  The force field must be fully periodic and must
 * project exactly to the immutable direct-Ewald model, including exclusion
 * versus explicit-zero provenance.  Only Velocity-Verlet options are
 * accepted.  A null constraints pointer means no constraints.
 *
 * The typed error is cleared only after all output descriptors and aliases
 * have been validated.  It is populated only for a typed direct-Ewald
 * failure.  The output owner is committed only after complete success.
 */
BG_API bg_status BG_CALL
bg_direct_ewald_composite_simulation_v1_create(
    const bg_system *system,
    const bg_forcefield *forcefield,
    const bg_direct_ewald_model_v1 *model,
    const bg_distance_constraints_v1 *constraints,
    const bg_simulation_options_v1 *options,
    bg_direct_ewald_composite_simulation_v1 **out_simulation,
    bg_direct_ewald_error_v1 *out_error) BG_NOEXCEPT;

BG_API void BG_CALL bg_direct_ewald_composite_simulation_v1_destroy(
    bg_direct_ewald_composite_simulation_v1 *simulation) BG_NOEXCEPT;

/* Borrowed particle-channel addresses remain stable until destruction. */
BG_API bg_status BG_CALL
bg_direct_ewald_composite_simulation_v1_get_particles(
    const bg_direct_ewald_composite_simulation_v1 *simulation,
    bg_particle_soa_view *out_view) BG_NOEXCEPT;
BG_API bg_status BG_CALL
bg_direct_ewald_composite_simulation_v1_get_absolute_step(
    const bg_direct_ewald_composite_simulation_v1 *simulation,
    uint64_t *absolute_step) BG_NOEXCEPT;

/*
 * Runs the shared canonical Velocity-Verlet/SHAKE/RATTLE pipeline with the
 * exact short-range + direct-Ewald force provider.  Only explicit C++ and
 * Rust CPU contexts are supported.  HIP fails closed without CPU fallback.
 * Zero steps reports current energy while leaving dynamic state unchanged.
 * Every failure preserves positions, velocities, absolute step, and report;
 * a late direct-Ewald failure still commits its typed error.
 */
BG_API bg_status BG_CALL bg_context_integrate_direct_ewald_composite_v1(
    const bg_context *context,
    bg_direct_ewald_composite_simulation_v1 *simulation,
    uint64_t step_count,
    bg_dynamics_report_v1 *out_report,
    bg_direct_ewald_error_v1 *out_error) BG_NOEXCEPT;

/*
 * Composite checkpoint v1 is canonical little-endian and padding-free.  It
 * uses magic "BGDEC001" and the Engine checkpoint's 104-byte header plus
 * x,y,z,vx,vy,vz float64 SoA payload, but has an independent fingerprint that
 * also binds the direct-Ewald evaluator family and every model field.  It is
 * intentionally incompatible with legacy "BGDYN001" checkpoints.
 */
BG_API bg_status BG_CALL
bg_direct_ewald_composite_simulation_v1_checkpoint_size(
    const bg_direct_ewald_composite_simulation_v1 *simulation,
    uint64_t *required_size) BG_NOEXCEPT;
BG_API bg_status BG_CALL
bg_direct_ewald_composite_simulation_v1_checkpoint_write(
    const bg_direct_ewald_composite_simulation_v1 *simulation,
    void *buffer,
    uint64_t buffer_capacity,
    uint64_t *written_size) BG_NOEXCEPT;
BG_API bg_status BG_CALL
bg_direct_ewald_composite_simulation_v1_checkpoint_load(
    bg_direct_ewald_composite_simulation_v1 *simulation,
    const void *buffer,
    uint64_t buffer_size) BG_NOEXCEPT;

#if defined(__cplusplus)
}  /* extern "C" */
#endif

#endif  /* BETELGEUZE_DIRECT_EWALD_COMPOSITE_DYNAMICS_H */
