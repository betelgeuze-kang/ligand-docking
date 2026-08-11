#ifndef BETELGEUZE_NATIVE_RUST_PROVIDER_H
#define BETELGEUZE_NATIVE_RUST_PROVIDER_H

#include "betelgeuze/engine.h"

#include <stddef.h>
#include <stdint.h>

#if defined(__cplusplus)
extern "C" {
#endif

#define BG_RUST_CPU_PROVIDER_ABI_VERSION UINT32_C(1)
#define BG_RUST_CPU_ERROR_CAPACITY UINT32_C(256)

typedef struct bg_rust_cpu_system_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    size_t atom_count;
    const double *position_x;
    const double *position_y;
    const double *position_z;
    const double *charge;
    uint64_t reserved[4];
} bg_rust_cpu_system_v1;

typedef struct bg_rust_cpu_bond_soa_v1 {
    size_t count;
    const size_t *atom_i;
    const size_t *atom_j;
    const double *equilibrium;
    const double *force_constant;
} bg_rust_cpu_bond_soa_v1;

typedef struct bg_rust_cpu_angle_soa_v1 {
    size_t count;
    const size_t *atom_i;
    const size_t *atom_j;
    const size_t *atom_k;
    const double *equilibrium;
    const double *force_constant;
} bg_rust_cpu_angle_soa_v1;

typedef struct bg_rust_cpu_torsion_soa_v1 {
    size_t count;
    const size_t *atom_i;
    const size_t *atom_j;
    const size_t *atom_k;
    const size_t *atom_l;
    const uint32_t *periodicity;
    const double *phase;
    const double *amplitude;
} bg_rust_cpu_torsion_soa_v1;

typedef struct bg_rust_cpu_pair_v1 {
    size_t atom_i;
    size_t atom_j;
} bg_rust_cpu_pair_v1;

typedef struct bg_rust_cpu_pair_scale_v1 {
    size_t atom_i;
    size_t atom_j;
    double lennard_jones;
    double coulomb;
} bg_rust_cpu_pair_scale_v1;

typedef struct bg_rust_cpu_forcefield_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    size_t atom_count;
    const double *sigma;
    const double *epsilon;
    bg_rust_cpu_bond_soa_v1 bonds;
    bg_rust_cpu_angle_soa_v1 angles;
    bg_rust_cpu_torsion_soa_v1 torsions;
    size_t exclusion_count;
    const bg_rust_cpu_pair_v1 *exclusions;
    size_t pair_scale_count;
    const bg_rust_cpu_pair_scale_v1 *pair_scales;
    uint32_t periodic_axes_mask;
    uint32_t reserved0;
    double cell_lengths[3];
    double cutoff;
    double switch_start;
    double dielectric;
    double screening_kappa;
    double minimum_pair_distance;
    uint64_t reserved[4];
} bg_rust_cpu_forcefield_v1;

typedef struct bg_rust_cpu_energy_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    double harmonic_bond;
    double harmonic_angle;
    double periodic_torsion;
    double lennard_jones;
    double coulomb;
    double total;
    uint64_t reserved[4];
} bg_rust_cpu_energy_v1;

typedef struct bg_rust_cpu_force_output_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    size_t capacity;
    double *x;
    double *y;
    double *z;
    uint64_t reserved[4];
} bg_rust_cpu_force_output_v1;

typedef struct bg_rust_cpu_error_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    char message[BG_RUST_CPU_ERROR_CAPACITY];
    uint64_t reserved[4];
} bg_rust_cpu_error_v1;

uint32_t bg_rust_cpu_provider_abi_version_v1(void);

int32_t bg_rust_cpu_evaluate_v1(
    const bg_rust_cpu_system_v1 *system,
    const bg_rust_cpu_forcefield_v1 *forcefield,
    uint8_t compute_forces,
    bg_rust_cpu_energy_v1 *out_energy,
    bg_rust_cpu_force_output_v1 *out_forces,
    bg_rust_cpu_error_v1 *out_error);

int32_t bg_rust_cpu_docking_scorer_v1_create(
    const bg_docking_scorer_v1_context_soa_v1 *descriptor,
    void **out_state,
    bg_rust_cpu_error_v1 *out_error);

void bg_rust_cpu_docking_scorer_v1_destroy(void *state);

int32_t bg_rust_cpu_docking_scorer_v1_score_fixed64(
    const void *state,
    const bg_docking_scorer_v1_candidate_batch_soa_v1 *candidates,
    bg_docking_scorer_v1_row_v1 *out_rows,
    bg_rust_cpu_error_v1 *out_error);

#if defined(__cplusplus)
}
#endif

#endif  // BETELGEUZE_NATIVE_RUST_PROVIDER_H
