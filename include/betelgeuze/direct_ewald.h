#ifndef BETELGEUZE_DIRECT_EWALD_H
#define BETELGEUZE_DIRECT_EWALD_H

/*
 * Betelgeuze deterministic direct-Ewald development ABI v1.
 *
 * This boundary is deliberately separate from the frozen Engine ABI 1.21
 * force-field descriptors.  It evaluates only neutral, fully periodic,
 * orthorhombic systems in the canonical Engine unit system.  It is direct
 * Ewald, not PME, and carries no production or scientific authority.
 */

#include "betelgeuze/engine.h"

#define BG_DIRECT_EWALD_ABI_VERSION_MAJOR UINT32_C(1)
#define BG_DIRECT_EWALD_ABI_VERSION_MINOR UINT32_C(0)
#define BG_DIRECT_EWALD_ABI_VERSION UINT32_C(1)
#define BG_DIRECT_EWALD_ERROR_DETAIL_CAPACITY UINT32_C(256)

#if defined(__cplusplus)
extern "C" {
#endif

typedef struct bg_direct_ewald_model_v1 bg_direct_ewald_model_v1;

typedef int32_t bg_direct_ewald_error_code;
enum {
    BG_DIRECT_EWALD_ERROR_NONE = 0,
    BG_DIRECT_EWALD_ERROR_EMPTY_SYSTEM = 1,
    BG_DIRECT_EWALD_ERROR_CAPACITY_EXCEEDED = 2,
    BG_DIRECT_EWALD_ERROR_CHARGE_COUNT_MISMATCH = 3,
    BG_DIRECT_EWALD_ERROR_NONFINITE_COORDINATE = 4,
    BG_DIRECT_EWALD_ERROR_NONFINITE_CHARGE = 5,
    BG_DIRECT_EWALD_ERROR_NON_NEUTRAL_SYSTEM = 6,
    BG_DIRECT_EWALD_ERROR_INVALID_CELL = 7,
    BG_DIRECT_EWALD_ERROR_CUTOFF_VIOLATES_MINIMUM_IMAGE = 8,
    BG_DIRECT_EWALD_ERROR_INVALID_PARAMETER = 9,
    BG_DIRECT_EWALD_ERROR_ATOM_INDEX_OUT_OF_RANGE = 10,
    BG_DIRECT_EWALD_ERROR_REPEATED_ATOM_INDEX = 11,
    BG_DIRECT_EWALD_ERROR_DUPLICATE_PAIR_RULE = 12,
    BG_DIRECT_EWALD_ERROR_CONFLICTING_PAIR_RULE = 13,
    BG_DIRECT_EWALD_ERROR_AMBIGUOUS_PAIR_CORRECTION_IMAGE = 14,
    BG_DIRECT_EWALD_ERROR_AMBIGUOUS_REAL_SPACE_CUTOFF = 15,
    BG_DIRECT_EWALD_ERROR_AMBIGUOUS_MINIMUM_PAIR_DISTANCE = 16,
    BG_DIRECT_EWALD_ERROR_PAIR_BELOW_MINIMUM_DISTANCE = 17,
    BG_DIRECT_EWALD_ERROR_DAMPING_UNDERFLOW = 18,
    BG_DIRECT_EWALD_ERROR_PHASE_UNDERFLOW = 19,
    BG_DIRECT_EWALD_ERROR_NONFINITE_RESULT = 20
};

/*
 * Immutable model input.  All non-empty pair channels are required, naturally
 * aligned, and deep-copied by create.  Pair indices are zero-based.  An
 * exclusion has local Coulomb scale zero; scaled-pair values must lie in
 * [0,1].  Duplicate rows and a pair present in both collections are rejected.
 */
typedef struct bg_direct_ewald_parameters_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    uint64_t atom_count;
    bg_unit_system unit_system;
    uint32_t reserved0;
    double cell_lengths_angstrom[3];
    double alpha_per_angstrom;
    double real_space_cutoff_angstrom;
    int32_t reciprocal_max_indices[3];
    uint32_t reserved1;
    double dielectric;
    double minimum_pair_distance_angstrom;
    uint64_t exclusion_count;
    const uint64_t *exclusion_atom_i;
    const uint64_t *exclusion_atom_j;
    uint64_t pair_scale_count;
    const uint64_t *pair_scale_atom_i;
    const uint64_t *pair_scale_atom_j;
    const double *pair_scale_coulomb;
    uint64_t reserved[4];
} bg_direct_ewald_parameters_v1;

/* Frozen real, reciprocal, self, pair-correction, then total order. */
typedef struct bg_direct_ewald_energy_components_v1 {
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
} bg_direct_ewald_energy_components_v1;

/*
 * Caller-owned transactional force output.  Capacity and channel pointers are
 * inputs; atom_count is committed only after a successful evaluation.  A null
 * force descriptor requests energy only.  Used channel spans must be mutually
 * disjoint and must not overlap either output descriptor.
 */
typedef struct bg_direct_ewald_force_soa_v1 {
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
} bg_direct_ewald_force_soa_v1;

/*
 * Typed diagnostics.  The descriptor header and reserved fields are inputs.
 * A valid descriptor is cleared before create/evaluate and receives a stable
 * code plus a nul-terminated, possibly truncated detail on typed failure.
 */
typedef struct bg_direct_ewald_error_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    bg_direct_ewald_error_code code;
    uint32_t reserved0;
    char detail[BG_DIRECT_EWALD_ERROR_DETAIL_CAPACITY];
    uint64_t reserved[4];
} bg_direct_ewald_error_v1;

BG_API uint32_t BG_CALL bg_direct_ewald_abi_version(void) BG_NOEXCEPT;
BG_API uint32_t BG_CALL bg_direct_ewald_abi_version_major(void) BG_NOEXCEPT;
BG_API uint32_t BG_CALL bg_direct_ewald_abi_version_minor(void) BG_NOEXCEPT;
BG_API const char *BG_CALL bg_direct_ewald_abi_version_string(void) BG_NOEXCEPT;

BG_API bg_status BG_CALL bg_direct_ewald_parameters_v1_init(
    bg_direct_ewald_parameters_v1 *parameters,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_direct_ewald_energy_components_v1_init(
    bg_direct_ewald_energy_components_v1 *energy,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_direct_ewald_force_soa_v1_init(
    bg_direct_ewald_force_soa_v1 *forces,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_direct_ewald_error_v1_init(
    bg_direct_ewald_error_v1 *error,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT;

#if !defined(BG_DISABLE_DIRECT_EWALD_DESCRIPTOR_INIT_CONVENIENCE_MACROS)
#  define bg_direct_ewald_parameters_v1_init(parameters) \
    bg_direct_ewald_parameters_v1_init( \
        (parameters), sizeof(*(parameters)), BG_DIRECT_EWALD_ABI_VERSION)
#  define bg_direct_ewald_energy_components_v1_init(energy) \
    bg_direct_ewald_energy_components_v1_init( \
        (energy), sizeof(*(energy)), BG_DIRECT_EWALD_ABI_VERSION)
#  define bg_direct_ewald_force_soa_v1_init(forces) \
    bg_direct_ewald_force_soa_v1_init( \
        (forces), sizeof(*(forces)), BG_DIRECT_EWALD_ABI_VERSION)
#  define bg_direct_ewald_error_v1_init(error) \
    bg_direct_ewald_error_v1_init( \
        (error), sizeof(*(error)), BG_DIRECT_EWALD_ABI_VERSION)
#endif

BG_API bg_status BG_CALL bg_direct_ewald_model_v1_create(
    const bg_direct_ewald_parameters_v1 *parameters,
    bg_direct_ewald_model_v1 **out_model,
    bg_direct_ewald_error_v1 *out_error) BG_NOEXCEPT;
BG_API void BG_CALL bg_direct_ewald_model_v1_destroy(
    bg_direct_ewald_model_v1 *model) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_direct_ewald_model_v1_get_atom_count(
    const bg_direct_ewald_model_v1 *model,
    uint64_t *atom_count) BG_NOEXCEPT;
BG_API const char *BG_CALL bg_direct_ewald_model_v1_profile_id(void) BG_NOEXCEPT;

/*
 * Evaluate against the positions and charges owned by system.  Context,
 * system, and model units/counts must agree.  CPP_CPU_REFERENCE and RUST_CPU
 * are explicit independent lanes; AUTO is resolved at context creation.  HIP
 * lanes fail closed and never execute or fall back to CPU.
 */
BG_API bg_status BG_CALL bg_context_evaluate_direct_ewald_v1(
    const bg_context *context,
    const bg_system *system,
    const bg_direct_ewald_model_v1 *model,
    bg_direct_ewald_energy_components_v1 *out_energy,
    bg_direct_ewald_force_soa_v1 *out_forces,
    bg_direct_ewald_error_v1 *out_error) BG_NOEXCEPT;

#if defined(__cplusplus)
}  /* extern "C" */
#endif

#endif  /* BETELGEUZE_DIRECT_EWALD_H */
