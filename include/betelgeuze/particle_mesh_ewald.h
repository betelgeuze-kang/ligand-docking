#ifndef BETELGEUZE_PARTICLE_MESH_EWALD_H
#define BETELGEUZE_PARTICLE_MESH_EWALD_H

/*
 * Betelgeuze deterministic particle-mesh Ewald development ABI v1.
 *
 * This separately versioned stateless boundary borrows an existing direct-
 * Ewald model for the real-space, self, and pair-correction terms and an
 * existing particle-mesh reciprocal model for the reciprocal term.  It is a
 * CPU-only development interface and carries no production or scientific
 * authority.
 */

#include "betelgeuze/direct_ewald.h"
#include "betelgeuze/particle_mesh_reciprocal.h"

#define BG_PARTICLE_MESH_EWALD_ABI_VERSION_MAJOR UINT32_C(1)
#define BG_PARTICLE_MESH_EWALD_ABI_VERSION_MINOR UINT32_C(0)
#define BG_PARTICLE_MESH_EWALD_ABI_VERSION UINT32_C(1)

#if defined(__cplusplus)
extern "C" {
#endif

/* Frozen real, mesh-reciprocal, self, pair-correction, then total order. */
typedef struct bg_particle_mesh_ewald_energy_components_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    bg_unit_system unit_system;
    uint32_t reserved0;
    double real_space_kcal_per_mol;
    double reciprocal_space_kcal_per_mol;
    double self_kcal_per_mol;
    double pair_correction_kcal_per_mol;
    double total_kcal_per_mol;
    uint64_t reserved[4];
} bg_particle_mesh_ewald_energy_components_v1;

/*
 * Caller-owned transactional force output.  Capacity and pointers are
 * inputs; atom_count is committed only after success.  A null descriptor
 * requests energy only.  Used output spans must be mutually disjoint and
 * must not overlap any borrowed handle, System channel, or direct-model
 * pair-rule storage.
 */
typedef struct bg_particle_mesh_ewald_force_soa_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    uint64_t atom_capacity;
    uint64_t atom_count;
    bg_unit_system unit_system;
    uint32_t reserved0;
    double *x_kcal_per_mol_angstrom;
    double *y_kcal_per_mol_angstrom;
    double *z_kcal_per_mol_angstrom;
    uint64_t reserved[4];
} bg_particle_mesh_ewald_force_soa_v1;

BG_API uint32_t BG_CALL bg_particle_mesh_ewald_abi_version(void)
    BG_NOEXCEPT;
BG_API uint32_t BG_CALL bg_particle_mesh_ewald_abi_version_major(void)
    BG_NOEXCEPT;
BG_API uint32_t BG_CALL bg_particle_mesh_ewald_abi_version_minor(void)
    BG_NOEXCEPT;
BG_API const char *BG_CALL bg_particle_mesh_ewald_abi_version_string(void)
    BG_NOEXCEPT;

BG_API bg_status BG_CALL bg_particle_mesh_ewald_energy_components_v1_init(
    bg_particle_mesh_ewald_energy_components_v1 *energy,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_particle_mesh_ewald_force_soa_v1_init(
    bg_particle_mesh_ewald_force_soa_v1 *forces,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT;

#if !defined(BG_DISABLE_PARTICLE_MESH_EWALD_DESCRIPTOR_INIT_CONVENIENCE_MACROS)
#  define bg_particle_mesh_ewald_energy_components_v1_init(energy) \
    bg_particle_mesh_ewald_energy_components_v1_init( \
        (energy), sizeof(*(energy)), BG_PARTICLE_MESH_EWALD_ABI_VERSION)
#  define bg_particle_mesh_ewald_force_soa_v1_init(forces) \
    bg_particle_mesh_ewald_force_soa_v1_init( \
        (forces), sizeof(*(forces)), BG_PARTICLE_MESH_EWALD_ABI_VERSION)
#endif

BG_API const char *BG_CALL bg_particle_mesh_ewald_v1_profile_id(void)
    BG_NOEXCEPT;

/*
 * All handles are borrowed for this call.  The System and both models must
 * have identical atom counts and units; the two models' cell lengths, alpha,
 * and dielectric must be bit-identical.  The direct model's reciprocal bounds
 * do not participate.  Only explicit C++ and Rust CPU contexts are accepted,
 * and the requested and resolved CPU lanes must match; AUTO, HIP, and a lane
 * mismatch fail closed without inspecting any other argument.  Typed failures
 * use bg_direct_ewald_error_v1.
 */
BG_API bg_status BG_CALL bg_context_evaluate_particle_mesh_ewald_v1(
    const bg_context *context,
    const bg_system *system,
    const bg_direct_ewald_model_v1 *direct_model,
    const bg_particle_mesh_reciprocal_model_v1 *reciprocal_model,
    bg_particle_mesh_ewald_energy_components_v1 *out_energy,
    bg_particle_mesh_ewald_force_soa_v1 *out_forces,
    bg_direct_ewald_error_v1 *out_error) BG_NOEXCEPT;

#if defined(__cplusplus)
}  /* extern "C" */
#endif

#endif  /* BETELGEUZE_PARTICLE_MESH_EWALD_H */
