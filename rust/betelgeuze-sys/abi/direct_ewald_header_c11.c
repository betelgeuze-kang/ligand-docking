#include <betelgeuze/direct_ewald.h>

#include <stddef.h>
#include <stdint.h>

_Static_assert(
    BG_DIRECT_EWALD_ABI_VERSION == UINT32_C(1),
    "unexpected direct-Ewald ABI version");
_Static_assert(
    BG_DIRECT_EWALD_ABI_VERSION_MAJOR == UINT32_C(1),
    "unexpected direct-Ewald ABI major version");
_Static_assert(
    BG_DIRECT_EWALD_ABI_VERSION_MINOR == UINT32_C(0),
    "unexpected direct-Ewald ABI minor version");
_Static_assert(
    BG_DIRECT_EWALD_ERROR_DETAIL_CAPACITY == UINT32_C(256),
    "unexpected direct-Ewald error detail capacity");
_Static_assert(
    sizeof(bg_direct_ewald_error_code) == sizeof(int32_t),
    "direct-Ewald error-code width changed");

_Static_assert(BG_DIRECT_EWALD_ERROR_NONE == 0, "bad NONE code");
_Static_assert(BG_DIRECT_EWALD_ERROR_EMPTY_SYSTEM == 1, "bad EMPTY_SYSTEM code");
_Static_assert(BG_DIRECT_EWALD_ERROR_CAPACITY_EXCEEDED == 2, "bad CAPACITY_EXCEEDED code");
_Static_assert(BG_DIRECT_EWALD_ERROR_CHARGE_COUNT_MISMATCH == 3, "bad CHARGE_COUNT_MISMATCH code");
_Static_assert(BG_DIRECT_EWALD_ERROR_NONFINITE_COORDINATE == 4, "bad NONFINITE_COORDINATE code");
_Static_assert(BG_DIRECT_EWALD_ERROR_NONFINITE_CHARGE == 5, "bad NONFINITE_CHARGE code");
_Static_assert(BG_DIRECT_EWALD_ERROR_NON_NEUTRAL_SYSTEM == 6, "bad NON_NEUTRAL_SYSTEM code");
_Static_assert(BG_DIRECT_EWALD_ERROR_INVALID_CELL == 7, "bad INVALID_CELL code");
_Static_assert(
    BG_DIRECT_EWALD_ERROR_CUTOFF_VIOLATES_MINIMUM_IMAGE == 8,
    "bad CUTOFF_VIOLATES_MINIMUM_IMAGE code");
_Static_assert(BG_DIRECT_EWALD_ERROR_INVALID_PARAMETER == 9, "bad INVALID_PARAMETER code");
_Static_assert(BG_DIRECT_EWALD_ERROR_ATOM_INDEX_OUT_OF_RANGE == 10, "bad ATOM_INDEX_OUT_OF_RANGE code");
_Static_assert(BG_DIRECT_EWALD_ERROR_REPEATED_ATOM_INDEX == 11, "bad REPEATED_ATOM_INDEX code");
_Static_assert(BG_DIRECT_EWALD_ERROR_DUPLICATE_PAIR_RULE == 12, "bad DUPLICATE_PAIR_RULE code");
_Static_assert(BG_DIRECT_EWALD_ERROR_CONFLICTING_PAIR_RULE == 13, "bad CONFLICTING_PAIR_RULE code");
_Static_assert(
    BG_DIRECT_EWALD_ERROR_AMBIGUOUS_PAIR_CORRECTION_IMAGE == 14,
    "bad AMBIGUOUS_PAIR_CORRECTION_IMAGE code");
_Static_assert(
    BG_DIRECT_EWALD_ERROR_AMBIGUOUS_REAL_SPACE_CUTOFF == 15,
    "bad AMBIGUOUS_REAL_SPACE_CUTOFF code");
_Static_assert(
    BG_DIRECT_EWALD_ERROR_AMBIGUOUS_MINIMUM_PAIR_DISTANCE == 16,
    "bad AMBIGUOUS_MINIMUM_PAIR_DISTANCE code");
_Static_assert(
    BG_DIRECT_EWALD_ERROR_PAIR_BELOW_MINIMUM_DISTANCE == 17,
    "bad PAIR_BELOW_MINIMUM_DISTANCE code");
_Static_assert(BG_DIRECT_EWALD_ERROR_DAMPING_UNDERFLOW == 18, "bad DAMPING_UNDERFLOW code");
_Static_assert(BG_DIRECT_EWALD_ERROR_PHASE_UNDERFLOW == 19, "bad PHASE_UNDERFLOW code");
_Static_assert(BG_DIRECT_EWALD_ERROR_NONFINITE_RESULT == 20, "bad NONFINITE_RESULT code");

#if UINTPTR_MAX == UINT64_MAX
_Static_assert(
    sizeof(bg_direct_ewald_parameters_v1) == 184,
    "direct-Ewald parameters ABI changed");
_Static_assert(
    sizeof(bg_direct_ewald_energy_components_v1) == 88,
    "direct-Ewald energy ABI changed");
_Static_assert(
    sizeof(bg_direct_ewald_force_soa_v1) == 88,
    "direct-Ewald force ABI changed");
_Static_assert(
    sizeof(bg_direct_ewald_error_v1) == 304,
    "direct-Ewald error ABI changed");
#endif

typedef uint32_t(BG_CALL *bg_direct_ewald_version_fn)(void);
typedef const char *(BG_CALL *bg_direct_ewald_string_fn)(void);
typedef bg_status(BG_CALL *bg_direct_ewald_parameters_v1_init_fn)(
    bg_direct_ewald_parameters_v1 *, size_t, uint32_t);
typedef bg_status(BG_CALL *bg_direct_ewald_energy_components_v1_init_fn)(
    bg_direct_ewald_energy_components_v1 *, size_t, uint32_t);
typedef bg_status(BG_CALL *bg_direct_ewald_force_soa_v1_init_fn)(
    bg_direct_ewald_force_soa_v1 *, size_t, uint32_t);
typedef bg_status(BG_CALL *bg_direct_ewald_error_v1_init_fn)(
    bg_direct_ewald_error_v1 *, size_t, uint32_t);
typedef bg_status(BG_CALL *bg_direct_ewald_model_v1_create_fn)(
    const bg_direct_ewald_parameters_v1 *,
    bg_direct_ewald_model_v1 **,
    bg_direct_ewald_error_v1 *);
typedef void(BG_CALL *bg_direct_ewald_model_v1_destroy_fn)(
    bg_direct_ewald_model_v1 *);
typedef bg_status(BG_CALL *bg_direct_ewald_model_v1_get_atom_count_fn)(
    const bg_direct_ewald_model_v1 *, uint64_t *);
typedef bg_status(BG_CALL *bg_context_evaluate_direct_ewald_v1_fn)(
    const bg_context *,
    const bg_system *,
    const bg_direct_ewald_model_v1 *,
    bg_direct_ewald_energy_components_v1 *,
    bg_direct_ewald_force_soa_v1 *,
    bg_direct_ewald_error_v1 *);

void betelgeuze_sys_direct_ewald_header_c11_typecheck(void) {
    bg_direct_ewald_parameters_v1 parameters;
    bg_direct_ewald_energy_components_v1 energy;
    bg_direct_ewald_force_soa_v1 forces;
    bg_direct_ewald_error_v1 error;
    bg_direct_ewald_model_v1 *model = NULL;
    bg_direct_ewald_version_fn version = bg_direct_ewald_abi_version;
    bg_direct_ewald_version_fn version_major = bg_direct_ewald_abi_version_major;
    bg_direct_ewald_version_fn version_minor = bg_direct_ewald_abi_version_minor;
    bg_direct_ewald_string_fn version_string = bg_direct_ewald_abi_version_string;
    bg_direct_ewald_string_fn profile_id = bg_direct_ewald_model_v1_profile_id;
    bg_direct_ewald_parameters_v1_init_fn parameters_init =
        bg_direct_ewald_parameters_v1_init;
    bg_direct_ewald_energy_components_v1_init_fn energy_init =
        bg_direct_ewald_energy_components_v1_init;
    bg_direct_ewald_force_soa_v1_init_fn forces_init =
        bg_direct_ewald_force_soa_v1_init;
    bg_direct_ewald_error_v1_init_fn error_init =
        bg_direct_ewald_error_v1_init;
    bg_direct_ewald_model_v1_create_fn create =
        bg_direct_ewald_model_v1_create;
    bg_direct_ewald_model_v1_destroy_fn destroy =
        bg_direct_ewald_model_v1_destroy;
    bg_direct_ewald_model_v1_get_atom_count_fn get_atom_count =
        bg_direct_ewald_model_v1_get_atom_count;
    bg_context_evaluate_direct_ewald_v1_fn evaluate =
        bg_context_evaluate_direct_ewald_v1;

    (void)parameters;
    (void)energy;
    (void)forces;
    (void)error;
    (void)model;
    (void)version;
    (void)version_major;
    (void)version_minor;
    (void)version_string;
    (void)profile_id;
    (void)parameters_init;
    (void)energy_init;
    (void)forces_init;
    (void)error_init;
    (void)create;
    (void)destroy;
    (void)get_atom_count;
    (void)evaluate;
}
