#ifndef BETELGEUZE_NATIVE_PARTICLE_MESH_RECIPROCAL_RUST_PROVIDER_H
#define BETELGEUZE_NATIVE_PARTICLE_MESH_RECIPROCAL_RUST_PROVIDER_H

#include <stddef.h>
#include <stdint.h>

#if defined(__cplusplus)
extern "C" {
#endif

#define BG_RUST_PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION UINT32_C(1)
#define BG_RUST_PARTICLE_MESH_RECIPROCAL_ERROR_CAPACITY UINT32_C(256)

typedef enum bg_rust_particle_mesh_reciprocal_error_code_v1 {
    BG_RUST_PARTICLE_MESH_RECIPROCAL_ERROR_NONE = 0,
    BG_RUST_PARTICLE_MESH_RECIPROCAL_ERROR_EMPTY_SYSTEM = 1,
    BG_RUST_PARTICLE_MESH_RECIPROCAL_ERROR_CAPACITY_EXCEEDED = 2,
    BG_RUST_PARTICLE_MESH_RECIPROCAL_ERROR_CHARGE_COUNT_MISMATCH = 3,
    BG_RUST_PARTICLE_MESH_RECIPROCAL_ERROR_NONFINITE_COORDINATE = 4,
    BG_RUST_PARTICLE_MESH_RECIPROCAL_ERROR_NONFINITE_CHARGE = 5,
    BG_RUST_PARTICLE_MESH_RECIPROCAL_ERROR_NON_NEUTRAL_SYSTEM = 6,
    BG_RUST_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_CELL = 7,
    BG_RUST_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_PARAMETER = 8,
    BG_RUST_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_MESH = 9,
    BG_RUST_PARTICLE_MESH_RECIPROCAL_ERROR_NONFINITE_RESULT = 10,
} bg_rust_particle_mesh_reciprocal_error_code_v1;

typedef struct bg_rust_particle_mesh_reciprocal_system_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    size_t atom_count;
    const double *position_x;
    const double *position_y;
    const double *position_z;
    const double *charge;
    uint64_t reserved[4];
} bg_rust_particle_mesh_reciprocal_system_v1;

typedef struct bg_rust_particle_mesh_reciprocal_model_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    double cell_lengths_angstrom[3];
    double alpha_per_angstrom;
    uint32_t mesh_dimensions[3];
    uint32_t reserved0;
    double dielectric;
    uint64_t reserved[4];
} bg_rust_particle_mesh_reciprocal_model_v1;

typedef struct bg_rust_particle_mesh_reciprocal_energy_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    double reciprocal_space_kcal_per_mol;
    uint64_t reserved[4];
} bg_rust_particle_mesh_reciprocal_energy_v1;

typedef struct bg_rust_particle_mesh_reciprocal_force_output_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    size_t capacity;
    double *x;
    double *y;
    double *z;
    uint64_t reserved[4];
} bg_rust_particle_mesh_reciprocal_force_output_v1;

typedef struct bg_rust_particle_mesh_reciprocal_error_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    int32_t typed_code;
    uint32_t reserved0;
    char detail[BG_RUST_PARTICLE_MESH_RECIPROCAL_ERROR_CAPACITY];
    uint64_t reserved[4];
} bg_rust_particle_mesh_reciprocal_error_v1;

uint32_t bg_rust_particle_mesh_reciprocal_provider_abi_version_v1(void);

int32_t bg_rust_particle_mesh_reciprocal_evaluate_v1(
    const bg_rust_particle_mesh_reciprocal_system_v1 *system,
    const bg_rust_particle_mesh_reciprocal_model_v1 *model,
    uint8_t compute_forces,
    bg_rust_particle_mesh_reciprocal_energy_v1 *out_energy,
    bg_rust_particle_mesh_reciprocal_force_output_v1 *out_forces,
    bg_rust_particle_mesh_reciprocal_error_v1 *out_error);

int32_t bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_v1(
    const bg_rust_particle_mesh_reciprocal_system_v1 *system,
    const bg_rust_particle_mesh_reciprocal_model_v1 *model,
    bg_rust_particle_mesh_reciprocal_energy_v1 *out_energy,
    bg_rust_particle_mesh_reciprocal_force_output_v1 *out_forces,
    bg_rust_particle_mesh_reciprocal_error_v1 *out_error);

#if defined(__cplusplus)
}  // extern "C"
#endif

#endif  // BETELGEUZE_NATIVE_PARTICLE_MESH_RECIPROCAL_RUST_PROVIDER_H
