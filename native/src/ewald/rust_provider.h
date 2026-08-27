#ifndef BETELGEUZE_NATIVE_EWALD_RUST_PROVIDER_H
#define BETELGEUZE_NATIVE_EWALD_RUST_PROVIDER_H

#include <stddef.h>
#include <stdint.h>

#if defined(__cplusplus)
extern "C" {
#endif

#define BG_RUST_DIRECT_EWALD_PROVIDER_ABI_VERSION UINT32_C(1)
#define BG_RUST_DIRECT_EWALD_ERROR_CAPACITY UINT32_C(256)

typedef enum bg_rust_direct_ewald_error_code_v1 {
    BG_RUST_DIRECT_EWALD_ERROR_NONE = 0,
    BG_RUST_DIRECT_EWALD_ERROR_EMPTY_SYSTEM = 1,
    BG_RUST_DIRECT_EWALD_ERROR_CAPACITY_EXCEEDED = 2,
    BG_RUST_DIRECT_EWALD_ERROR_CHARGE_COUNT_MISMATCH = 3,
    BG_RUST_DIRECT_EWALD_ERROR_NONFINITE_COORDINATE = 4,
    BG_RUST_DIRECT_EWALD_ERROR_NONFINITE_CHARGE = 5,
    BG_RUST_DIRECT_EWALD_ERROR_NON_NEUTRAL_SYSTEM = 6,
    BG_RUST_DIRECT_EWALD_ERROR_INVALID_CELL = 7,
    BG_RUST_DIRECT_EWALD_ERROR_CUTOFF_VIOLATES_MINIMUM_IMAGE = 8,
    BG_RUST_DIRECT_EWALD_ERROR_INVALID_PARAMETER = 9,
    BG_RUST_DIRECT_EWALD_ERROR_ATOM_INDEX_OUT_OF_RANGE = 10,
    BG_RUST_DIRECT_EWALD_ERROR_REPEATED_ATOM_INDEX = 11,
    BG_RUST_DIRECT_EWALD_ERROR_DUPLICATE_PAIR_RULE = 12,
    BG_RUST_DIRECT_EWALD_ERROR_CONFLICTING_PAIR_RULE = 13,
    BG_RUST_DIRECT_EWALD_ERROR_AMBIGUOUS_PAIR_CORRECTION_IMAGE = 14,
    BG_RUST_DIRECT_EWALD_ERROR_AMBIGUOUS_REAL_SPACE_CUTOFF = 15,
    BG_RUST_DIRECT_EWALD_ERROR_AMBIGUOUS_MINIMUM_PAIR_DISTANCE = 16,
    BG_RUST_DIRECT_EWALD_ERROR_PAIR_BELOW_MINIMUM_DISTANCE = 17,
    BG_RUST_DIRECT_EWALD_ERROR_DAMPING_UNDERFLOW = 18,
    BG_RUST_DIRECT_EWALD_ERROR_PHASE_UNDERFLOW = 19,
    BG_RUST_DIRECT_EWALD_ERROR_NONFINITE_RESULT = 20,
} bg_rust_direct_ewald_error_code_v1;

typedef struct bg_rust_direct_ewald_system_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    size_t atom_count;
    const double *position_x;
    const double *position_y;
    const double *position_z;
    const double *charge;
    uint64_t reserved[4];
} bg_rust_direct_ewald_system_v1;

typedef struct bg_rust_direct_ewald_pair_rule_v1 {
    size_t atom_i;
    size_t atom_j;
    double coulomb_scale;
    uint64_t reserved[2];
} bg_rust_direct_ewald_pair_rule_v1;

typedef struct bg_rust_direct_ewald_model_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    double cell_lengths_angstrom[3];
    double alpha_per_angstrom;
    double real_space_cutoff_angstrom;
    int32_t reciprocal_max_indices[3];
    uint32_t reserved0;
    double dielectric;
    double minimum_pair_distance_angstrom;
    size_t pair_rule_count;
    const bg_rust_direct_ewald_pair_rule_v1 *pair_rules;
    uint64_t reserved[4];
} bg_rust_direct_ewald_model_v1;

typedef struct bg_rust_direct_ewald_energy_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    double real_space_kcal_per_mol;
    double reciprocal_space_kcal_per_mol;
    double self_kcal_per_mol;
    double pair_correction_kcal_per_mol;
    double total_kcal_per_mol;
    uint64_t reserved[4];
} bg_rust_direct_ewald_energy_v1;

typedef struct bg_rust_direct_ewald_force_output_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    size_t capacity;
    double *x;
    double *y;
    double *z;
    uint64_t reserved[4];
} bg_rust_direct_ewald_force_output_v1;

typedef struct bg_rust_direct_ewald_error_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    int32_t typed_code;
    uint32_t reserved0;
    char detail[BG_RUST_DIRECT_EWALD_ERROR_CAPACITY];
    uint64_t reserved[4];
} bg_rust_direct_ewald_error_v1;

uint32_t bg_rust_direct_ewald_provider_abi_version_v1(void);

int32_t bg_rust_direct_ewald_evaluate_v1(
    const bg_rust_direct_ewald_system_v1 *system,
    const bg_rust_direct_ewald_model_v1 *model,
    uint8_t compute_forces,
    bg_rust_direct_ewald_energy_v1 *out_energy,
    bg_rust_direct_ewald_force_output_v1 *out_forces,
    bg_rust_direct_ewald_error_v1 *out_error);

#if defined(__cplusplus)
}  // extern "C"
#endif

#endif  // BETELGEUZE_NATIVE_EWALD_RUST_PROVIDER_H
