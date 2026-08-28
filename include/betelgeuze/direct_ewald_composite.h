#ifndef BETELGEUZE_DIRECT_EWALD_COMPOSITE_H
#define BETELGEUZE_DIRECT_EWALD_COMPOSITE_H

/*
 * Betelgeuze deterministic short-range + direct-Ewald composite ABI v1.
 *
 * This stateless development boundary is separately versioned from both the
 * frozen Engine ABI and the direct-Ewald model ABI.  It borrows existing
 * handles for one call, evaluates the frozen short-range force field with
 * exact +0.0 charges, evaluates direct Ewald with the caller's original
 * exact-neutral charges, and transactionally commits their deterministic sum.
 * It is not a dynamics, PME, production, or scientific-authority interface.
 */

#include "betelgeuze/direct_ewald.h"

#define BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION_MAJOR UINT32_C(1)
#define BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION_MINOR UINT32_C(0)
#define BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION UINT32_C(1)

#if defined(__cplusplus)
extern "C" {
#endif

/*
 * Frozen component order: short-range bond, angle, torsion, LJ, Coulomb,
 * short total; direct-Ewald real, reciprocal, self, pair correction, Ewald
 * total; then grand total.  The short Coulomb component is exact +0.0.
 */
typedef struct bg_direct_ewald_composite_energy_components_v1 {
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
    double ewald_real_space_kcal_per_mol;
    double ewald_reciprocal_space_kcal_per_mol;
    double ewald_self_kcal_per_mol;
    double ewald_pair_correction_kcal_per_mol;
    double ewald_total_kcal_per_mol;
    double total_kcal_per_mol;
    uint64_t reserved[4];
} bg_direct_ewald_composite_energy_components_v1;

/*
 * Caller-owned transactional combined-force output.  A null descriptor asks
 * both parent evaluators for energy only.  Used channel spans and all output
 * descriptors must be mutually disjoint and must not overlap any borrowed
 * System SoA channel.
 */
typedef struct bg_direct_ewald_composite_force_soa_v1 {
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
} bg_direct_ewald_composite_force_soa_v1;

BG_API uint32_t BG_CALL
bg_direct_ewald_composite_abi_version(void) BG_NOEXCEPT;
BG_API uint32_t BG_CALL
bg_direct_ewald_composite_abi_version_major(void) BG_NOEXCEPT;
BG_API uint32_t BG_CALL
bg_direct_ewald_composite_abi_version_minor(void) BG_NOEXCEPT;
BG_API const char *BG_CALL
bg_direct_ewald_composite_abi_version_string(void) BG_NOEXCEPT;

BG_API bg_status BG_CALL
bg_direct_ewald_composite_energy_components_v1_init(
    bg_direct_ewald_composite_energy_components_v1 *energy,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_direct_ewald_composite_force_soa_v1_init(
    bg_direct_ewald_composite_force_soa_v1 *forces,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT;

#if !defined(BG_DISABLE_DIRECT_EWALD_COMPOSITE_DESCRIPTOR_INIT_CONVENIENCE_MACROS)
#  define bg_direct_ewald_composite_energy_components_v1_init(energy) \
    bg_direct_ewald_composite_energy_components_v1_init( \
        (energy), sizeof(*(energy)), BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION)
#  define bg_direct_ewald_composite_force_soa_v1_init(forces) \
    bg_direct_ewald_composite_force_soa_v1_init( \
        (forces), sizeof(*(forces)), BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION)
#endif

BG_API const char *BG_CALL
bg_direct_ewald_composite_v1_profile_id(void) BG_NOEXCEPT;

/*
 * Every handle is borrowed for this call.  Units and atom counts must match;
 * the force field must be fully periodic with cell lengths bit-identical to
 * the model, and its exclusions/scaled Coulomb pairs must exactly project to
 * the model with exclusion provenance preserved.  Only the explicit C++ and
 * Rust CPU lanes are supported.  HIP fails before evaluation and never falls
 * back.  The direct-Ewald typed error is cleared on entry after descriptor
 * validation and populated only for a typed direct-Ewald failure.
 */
BG_API bg_status BG_CALL bg_context_evaluate_direct_ewald_composite_v1(
    const bg_context *context,
    const bg_system *system,
    const bg_forcefield *forcefield,
    const bg_direct_ewald_model_v1 *model,
    bg_direct_ewald_composite_energy_components_v1 *out_energy,
    bg_direct_ewald_composite_force_soa_v1 *out_forces,
    bg_direct_ewald_error_v1 *out_error) BG_NOEXCEPT;

#if defined(__cplusplus)
}  /* extern "C" */
#endif

#endif  /* BETELGEUZE_DIRECT_EWALD_COMPOSITE_H */
