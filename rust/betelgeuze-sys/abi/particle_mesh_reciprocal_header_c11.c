#include <betelgeuze/particle_mesh_reciprocal.h>

#include <stddef.h>
#include <stdint.h>

_Static_assert(BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION == UINT32_C(1), "bad ABI version");
_Static_assert(BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION_MAJOR == UINT32_C(1), "bad ABI major");
_Static_assert(BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION_MINOR == UINT32_C(0), "bad ABI minor");
_Static_assert(BG_PARTICLE_MESH_RECIPROCAL_ERROR_DETAIL_CAPACITY == UINT32_C(256), "bad error capacity");
_Static_assert(BG_PARTICLE_MESH_RECIPROCAL_CARDINAL_B_SPLINE_ORDER == UINT32_C(4), "bad spline order");
_Static_assert(sizeof(bg_particle_mesh_reciprocal_error_code) == sizeof(int32_t), "bad error width");

_Static_assert(BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONE == 0, "bad NONE code");
_Static_assert(BG_PARTICLE_MESH_RECIPROCAL_ERROR_EMPTY_SYSTEM == 1, "bad EMPTY_SYSTEM code");
_Static_assert(BG_PARTICLE_MESH_RECIPROCAL_ERROR_CAPACITY_EXCEEDED == 2, "bad CAPACITY_EXCEEDED code");
_Static_assert(BG_PARTICLE_MESH_RECIPROCAL_ERROR_CHARGE_COUNT_MISMATCH == 3, "bad CHARGE_COUNT_MISMATCH code");
_Static_assert(BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONFINITE_COORDINATE == 4, "bad NONFINITE_COORDINATE code");
_Static_assert(BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONFINITE_CHARGE == 5, "bad NONFINITE_CHARGE code");
_Static_assert(BG_PARTICLE_MESH_RECIPROCAL_ERROR_NON_NEUTRAL_SYSTEM == 6, "bad NON_NEUTRAL_SYSTEM code");
_Static_assert(BG_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_CELL == 7, "bad INVALID_CELL code");
_Static_assert(BG_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_PARAMETER == 8, "bad INVALID_PARAMETER code");
_Static_assert(BG_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_MESH == 9, "bad INVALID_MESH code");
_Static_assert(BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONFINITE_RESULT == 10, "bad NONFINITE_RESULT code");

#if UINTPTR_MAX == UINT64_MAX
_Static_assert(sizeof(bg_particle_mesh_reciprocal_parameters_v1) == 112, "parameters ABI changed");
_Static_assert(sizeof(bg_particle_mesh_reciprocal_energy_v1) == 56, "energy ABI changed");
_Static_assert(sizeof(bg_particle_mesh_reciprocal_force_soa_v1) == 88, "force ABI changed");
_Static_assert(sizeof(bg_particle_mesh_reciprocal_error_v1) == 304, "error ABI changed");
#endif

typedef uint32_t(BG_CALL *version_fn)(void);
typedef const char *(BG_CALL *string_fn)(void);
typedef bg_status(BG_CALL *parameters_init_fn)(bg_particle_mesh_reciprocal_parameters_v1 *, size_t, uint32_t);
typedef bg_status(BG_CALL *energy_init_fn)(bg_particle_mesh_reciprocal_energy_v1 *, size_t, uint32_t);
typedef bg_status(BG_CALL *forces_init_fn)(bg_particle_mesh_reciprocal_force_soa_v1 *, size_t, uint32_t);
typedef bg_status(BG_CALL *error_init_fn)(bg_particle_mesh_reciprocal_error_v1 *, size_t, uint32_t);
typedef bg_status(BG_CALL *create_fn)(const bg_particle_mesh_reciprocal_parameters_v1 *, bg_particle_mesh_reciprocal_model_v1 **, bg_particle_mesh_reciprocal_error_v1 *);
typedef void(BG_CALL *destroy_fn)(bg_particle_mesh_reciprocal_model_v1 *);
typedef bg_status(BG_CALL *get_count_fn)(const bg_particle_mesh_reciprocal_model_v1 *, uint64_t *);
typedef bg_status(BG_CALL *evaluate_fn)(const bg_context *, const bg_system *, const bg_particle_mesh_reciprocal_model_v1 *, bg_particle_mesh_reciprocal_energy_v1 *, bg_particle_mesh_reciprocal_force_soa_v1 *, bg_particle_mesh_reciprocal_error_v1 *);

void betelgeuze_sys_particle_mesh_reciprocal_header_c11_typecheck(void) {
    bg_particle_mesh_reciprocal_parameters_v1 parameters;
    bg_particle_mesh_reciprocal_energy_v1 energy;
    bg_particle_mesh_reciprocal_force_soa_v1 forces;
    bg_particle_mesh_reciprocal_error_v1 error;
    bg_particle_mesh_reciprocal_model_v1 *model = NULL;
    version_fn version = bg_particle_mesh_reciprocal_abi_version;
    version_fn version_major = bg_particle_mesh_reciprocal_abi_version_major;
    version_fn version_minor = bg_particle_mesh_reciprocal_abi_version_minor;
    string_fn version_string = bg_particle_mesh_reciprocal_abi_version_string;
    string_fn profile_id = bg_particle_mesh_reciprocal_model_v1_profile_id;
    parameters_init_fn parameters_init = bg_particle_mesh_reciprocal_parameters_v1_init;
    energy_init_fn energy_init = bg_particle_mesh_reciprocal_energy_v1_init;
    forces_init_fn forces_init = bg_particle_mesh_reciprocal_force_soa_v1_init;
    error_init_fn error_init = bg_particle_mesh_reciprocal_error_v1_init;
    create_fn create = bg_particle_mesh_reciprocal_model_v1_create;
    destroy_fn destroy = bg_particle_mesh_reciprocal_model_v1_destroy;
    get_count_fn get_count = bg_particle_mesh_reciprocal_model_v1_get_atom_count;
    evaluate_fn evaluate = bg_context_evaluate_particle_mesh_reciprocal_v1;
    (void)parameters; (void)energy; (void)forces; (void)error; (void)model;
    (void)version; (void)version_major; (void)version_minor; (void)version_string;
    (void)profile_id; (void)parameters_init; (void)energy_init; (void)forces_init;
    (void)error_init; (void)create; (void)destroy; (void)get_count; (void)evaluate;
}
