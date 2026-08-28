#ifndef BETELGEUZE_PARTICLE_MESH_EWALD_COMPOSITE_H
#define BETELGEUZE_PARTICLE_MESH_EWALD_COMPOSITE_H

/*
 * Betelgeuze deterministic short-range + particle-mesh Ewald composite ABI
 * v1.
 *
 * This separately versioned stateless development boundary borrows existing
 * handles for one call.  It evaluates the frozen short-range force field with
 * exact +0.0 charges and the particle-mesh Ewald parent with the caller's
 * original exact-neutral charges, then transactionally commits their
 * deterministic sum.  It carries no production or scientific authority.
 */

#include "betelgeuze/particle_mesh_ewald.h"

#define BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION_MAJOR UINT32_C(1)
#define BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION_MINOR UINT32_C(0)
#define BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION UINT32_C(1)

#if defined(__cplusplus)
extern "C" {
#endif

/*
 * Frozen component order: short-range bond, angle, torsion, LJ, Coulomb,
 * short total; PME real, mesh-reciprocal, self, pair correction, PME total;
 * then grand total.  The short Coulomb component is exact +0.0.
 */
typedef struct bg_particle_mesh_ewald_composite_energy_components_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    bg_unit_system unit_system;
    uint32_t reserved0;
    double short_harmonic_bond_kcal_per_mol;
    double short_harmonic_angle_kcal_per_mol;
    double short_periodic_torsion_kcal_per_mol;
    double short_lennard_jones_kcal_per_mol;
    double short_coulomb_kcal_per_mol;
    double short_total_kcal_per_mol;
    double pme_real_space_kcal_per_mol;
    double pme_reciprocal_space_kcal_per_mol;
    double pme_self_kcal_per_mol;
    double pme_pair_correction_kcal_per_mol;
    double pme_total_kcal_per_mol;
    double total_kcal_per_mol;
    uint64_t reserved[4];
} bg_particle_mesh_ewald_composite_energy_components_v1;

/*
 * Caller-owned transactional combined-force output.  Capacity and pointers
 * are inputs; atom_count is committed only after success.  A null descriptor
 * asks both parents for energy only.  Used channel spans and all output
 * descriptors must be mutually disjoint and must not overlap borrowed handle
 * objects or their semantic storage.
 */
typedef struct bg_particle_mesh_ewald_composite_force_soa_v1 {
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
} bg_particle_mesh_ewald_composite_force_soa_v1;

BG_API uint32_t BG_CALL bg_particle_mesh_ewald_composite_abi_version(void)
    BG_NOEXCEPT;
BG_API uint32_t BG_CALL
bg_particle_mesh_ewald_composite_abi_version_major(void) BG_NOEXCEPT;
BG_API uint32_t BG_CALL
bg_particle_mesh_ewald_composite_abi_version_minor(void) BG_NOEXCEPT;
BG_API const char *BG_CALL
bg_particle_mesh_ewald_composite_abi_version_string(void) BG_NOEXCEPT;

BG_API bg_status BG_CALL
bg_particle_mesh_ewald_composite_energy_components_v1_init(
    bg_particle_mesh_ewald_composite_energy_components_v1 *energy,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_particle_mesh_ewald_composite_force_soa_v1_init(
    bg_particle_mesh_ewald_composite_force_soa_v1 *forces,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT;

#if !defined(BG_DISABLE_PARTICLE_MESH_EWALD_COMPOSITE_DESCRIPTOR_INIT_CONVENIENCE_MACROS)
#  define bg_particle_mesh_ewald_composite_energy_components_v1_init(energy) \
    bg_particle_mesh_ewald_composite_energy_components_v1_init( \
        (energy), sizeof(*(energy)), \
        BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION)
#  define bg_particle_mesh_ewald_composite_force_soa_v1_init(forces) \
    bg_particle_mesh_ewald_composite_force_soa_v1_init( \
        (forces), sizeof(*(forces)), \
        BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION)
#endif

BG_API const char *BG_CALL
bg_particle_mesh_ewald_composite_v1_profile_id(void) BG_NOEXCEPT;

/*
 * Every handle is borrowed for this call.  Units and atom counts must match;
 * the force field must be fully periodic with cell lengths bit-identical to
 * the direct model and pair-rule provenance preserved.  The two Ewald models'
 * cell lengths, alpha, and dielectric must be bit-identical.  Only explicit,
 * matching C++ and Rust CPU requested/resolved lanes are supported.  AUTO,
 * HIP, and lane mismatch fail before any scientific or output argument is
 * inspected.  Typed failures use bg_direct_ewald_error_v1.
 */
BG_API bg_status BG_CALL
bg_context_evaluate_particle_mesh_ewald_composite_v1(
    const bg_context *context,
    const bg_system *system,
    const bg_forcefield *forcefield,
    const bg_direct_ewald_model_v1 *direct_model,
    const bg_particle_mesh_reciprocal_model_v1 *reciprocal_model,
    bg_particle_mesh_ewald_composite_energy_components_v1 *out_energy,
    bg_particle_mesh_ewald_composite_force_soa_v1 *out_forces,
    bg_direct_ewald_error_v1 *out_error) BG_NOEXCEPT;

#if defined(__cplusplus)
}  /* extern "C" */
#endif

#endif  /* BETELGEUZE_PARTICLE_MESH_EWALD_COMPOSITE_H */
