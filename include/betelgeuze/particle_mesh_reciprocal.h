#ifndef BETELGEUZE_PARTICLE_MESH_RECIPROCAL_H
#define BETELGEUZE_PARTICLE_MESH_RECIPROCAL_H

/*
 * Betelgeuze deterministic particle-mesh reciprocal development ABI v1.
 *
 * This separately versioned boundary evaluates only the order-4 reciprocal
 * mesh term for neutral, fully periodic, orthorhombic systems in the canonical
 * Engine unit system.  It does not include real-space, self, pair-correction,
 * total-energy, virial, timing, or complete-PME semantics and carries no
 * production or scientific authority.
 */

#include "betelgeuze/engine.h"

#define BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION_MAJOR UINT32_C(1)
#define BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION_MINOR UINT32_C(0)
#define BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION UINT32_C(1)
#define BG_PARTICLE_MESH_RECIPROCAL_ERROR_DETAIL_CAPACITY UINT32_C(256)
#define BG_PARTICLE_MESH_RECIPROCAL_CARDINAL_B_SPLINE_ORDER UINT32_C(4)

#if defined(__cplusplus)
extern "C" {
#endif

typedef struct bg_particle_mesh_reciprocal_model_v1
    bg_particle_mesh_reciprocal_model_v1;

typedef int32_t bg_particle_mesh_reciprocal_error_code;
enum {
    BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONE = 0,
    BG_PARTICLE_MESH_RECIPROCAL_ERROR_EMPTY_SYSTEM = 1,
    BG_PARTICLE_MESH_RECIPROCAL_ERROR_CAPACITY_EXCEEDED = 2,
    BG_PARTICLE_MESH_RECIPROCAL_ERROR_CHARGE_COUNT_MISMATCH = 3,
    BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONFINITE_COORDINATE = 4,
    BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONFINITE_CHARGE = 5,
    BG_PARTICLE_MESH_RECIPROCAL_ERROR_NON_NEUTRAL_SYSTEM = 6,
    BG_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_CELL = 7,
    BG_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_PARAMETER = 8,
    BG_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_MESH = 9,
    BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONFINITE_RESULT = 10
};

/* Immutable model input.  Create validates and deep-copies every value. */
typedef struct bg_particle_mesh_reciprocal_parameters_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    uint64_t atom_count;
    bg_unit_system unit_system;
    uint32_t reserved0;
    double cell_lengths_angstrom[3];
    double alpha_per_angstrom;
    uint32_t mesh_dimensions[3];
    uint32_t reserved1;
    double dielectric;
    uint64_t reserved[4];
} bg_particle_mesh_reciprocal_parameters_v1;

/* Reciprocal-only energy.  This is not a complete-PME or total energy. */
typedef struct bg_particle_mesh_reciprocal_energy_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    bg_unit_system unit_system;
    uint32_t reserved0;
    double reciprocal_space_kcal_per_mol;
    uint64_t reserved[4];
} bg_particle_mesh_reciprocal_energy_v1;

/*
 * Caller-owned transactional force output.  Capacity and pointers are inputs;
 * atom_count is committed only after success.  A null descriptor requests the
 * energy-only path.  Used channels must be mutually disjoint and must not
 * overlap any descriptor.
 */
typedef struct bg_particle_mesh_reciprocal_force_soa_v1 {
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
} bg_particle_mesh_reciprocal_force_soa_v1;

/* Typed, success-cleared diagnostic output. */
typedef struct bg_particle_mesh_reciprocal_error_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    bg_particle_mesh_reciprocal_error_code code;
    uint32_t reserved0;
    char detail[BG_PARTICLE_MESH_RECIPROCAL_ERROR_DETAIL_CAPACITY];
    uint64_t reserved[4];
} bg_particle_mesh_reciprocal_error_v1;

BG_API uint32_t BG_CALL bg_particle_mesh_reciprocal_abi_version(void)
    BG_NOEXCEPT;
BG_API uint32_t BG_CALL bg_particle_mesh_reciprocal_abi_version_major(void)
    BG_NOEXCEPT;
BG_API uint32_t BG_CALL bg_particle_mesh_reciprocal_abi_version_minor(void)
    BG_NOEXCEPT;
BG_API const char *BG_CALL bg_particle_mesh_reciprocal_abi_version_string(void)
    BG_NOEXCEPT;

BG_API bg_status BG_CALL bg_particle_mesh_reciprocal_parameters_v1_init(
    bg_particle_mesh_reciprocal_parameters_v1 *parameters,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_particle_mesh_reciprocal_energy_v1_init(
    bg_particle_mesh_reciprocal_energy_v1 *energy,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_particle_mesh_reciprocal_force_soa_v1_init(
    bg_particle_mesh_reciprocal_force_soa_v1 *forces,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_particle_mesh_reciprocal_error_v1_init(
    bg_particle_mesh_reciprocal_error_v1 *error,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT;

#if !defined(BG_DISABLE_PARTICLE_MESH_RECIPROCAL_DESCRIPTOR_INIT_CONVENIENCE_MACROS)
#  define bg_particle_mesh_reciprocal_parameters_v1_init(parameters) \
    bg_particle_mesh_reciprocal_parameters_v1_init( \
        (parameters), sizeof(*(parameters)), \
        BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION)
#  define bg_particle_mesh_reciprocal_energy_v1_init(energy) \
    bg_particle_mesh_reciprocal_energy_v1_init( \
        (energy), sizeof(*(energy)), \
        BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION)
#  define bg_particle_mesh_reciprocal_force_soa_v1_init(forces) \
    bg_particle_mesh_reciprocal_force_soa_v1_init( \
        (forces), sizeof(*(forces)), \
        BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION)
#  define bg_particle_mesh_reciprocal_error_v1_init(error) \
    bg_particle_mesh_reciprocal_error_v1_init( \
        (error), sizeof(*(error)), \
        BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION)
#endif

BG_API bg_status BG_CALL bg_particle_mesh_reciprocal_model_v1_create(
    const bg_particle_mesh_reciprocal_parameters_v1 *parameters,
    bg_particle_mesh_reciprocal_model_v1 **out_model,
    bg_particle_mesh_reciprocal_error_v1 *out_error) BG_NOEXCEPT;
BG_API void BG_CALL bg_particle_mesh_reciprocal_model_v1_destroy(
    bg_particle_mesh_reciprocal_model_v1 *model) BG_NOEXCEPT;
BG_API bg_status BG_CALL bg_particle_mesh_reciprocal_model_v1_get_atom_count(
    const bg_particle_mesh_reciprocal_model_v1 *model,
    uint64_t *atom_count) BG_NOEXCEPT;
BG_API const char *BG_CALL bg_particle_mesh_reciprocal_model_v1_profile_id(
    void) BG_NOEXCEPT;

/*
 * CPP_CPU_REFERENCE and RUST_CPU are explicit independent CPU lanes.  AUTO
 * and both HIP backends fail closed; this function never falls back.
 */
BG_API bg_status BG_CALL bg_context_evaluate_particle_mesh_reciprocal_v1(
    const bg_context *context,
    const bg_system *system,
    const bg_particle_mesh_reciprocal_model_v1 *model,
    bg_particle_mesh_reciprocal_energy_v1 *out_energy,
    bg_particle_mesh_reciprocal_force_soa_v1 *out_forces,
    bg_particle_mesh_reciprocal_error_v1 *out_error) BG_NOEXCEPT;

#if defined(__cplusplus)
}  /* extern "C" */
#endif

#endif  /* BETELGEUZE_PARTICLE_MESH_RECIPROCAL_H */
