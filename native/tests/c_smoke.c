#include "betelgeuze/engine.h"

#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <string.h>

#ifndef BG_TEST_HIP_ENABLED
#define BG_TEST_HIP_ENABLED 0
#endif

#define BG_TEST_EXACT_INITIALIZER(TYPE, INITIALIZER)                         \
    do {                                                                    \
        TYPE descriptor;                                                    \
        unsigned char snapshot[sizeof(descriptor)];                         \
        bg_status(BG_CALL * initializer_function)(                          \
            TYPE *, size_t, uint32_t) = (INITIALIZER);                      \
        memset(&descriptor, 0xA5, sizeof(descriptor));                      \
        memcpy(snapshot, &descriptor, sizeof(descriptor));                  \
        assert(initializer_function(                                        \
                   &descriptor, sizeof(descriptor) - 1, BG_ABI_VERSION) ==  \
               BG_STATUS_ABI_MISMATCH);                                     \
        assert(memcmp(snapshot, &descriptor, sizeof(descriptor)) == 0);      \
        assert(initializer_function(                                        \
                   &descriptor, sizeof(descriptor) + 1, BG_ABI_VERSION) ==  \
               BG_STATUS_ABI_MISMATCH);                                     \
        assert(memcmp(snapshot, &descriptor, sizeof(descriptor)) == 0);      \
        assert(initializer_function(                                        \
                   &descriptor, sizeof(descriptor), BG_ABI_VERSION + 1) ==  \
               BG_STATUS_ABI_MISMATCH);                                     \
        assert(memcmp(snapshot, &descriptor, sizeof(descriptor)) == 0);      \
        assert(INITIALIZER(&descriptor) == BG_STATUS_OK);                   \
        assert((size_t)descriptor.struct_size == sizeof(descriptor));       \
        assert(descriptor.abi_version == BG_ABI_VERSION);                   \
    } while (0)

static void test_descriptor_initializer_compatibility(void) {
    BG_TEST_EXACT_INITIALIZER(bg_context_options, bg_context_options_init);
    BG_TEST_EXACT_INITIALIZER(bg_particle_soa, bg_particle_soa_init);
    BG_TEST_EXACT_INITIALIZER(bg_particle_soa_view, bg_particle_soa_view_init);
    BG_TEST_EXACT_INITIALIZER(bg_position_soa, bg_position_soa_init);
    BG_TEST_EXACT_INITIALIZER(
        bg_forcefield_soa_v1, bg_forcefield_soa_v1_init);
    BG_TEST_EXACT_INITIALIZER(bg_force_soa_v1, bg_force_soa_v1_init);
    BG_TEST_EXACT_INITIALIZER(
        bg_energy_components_v1, bg_energy_components_v1_init);
    BG_TEST_EXACT_INITIALIZER(
        bg_distance_constraints_v1, bg_distance_constraints_v1_init);
    BG_TEST_EXACT_INITIALIZER(
        bg_simulation_options_v1, bg_simulation_options_v1_init);
    BG_TEST_EXACT_INITIALIZER(
        bg_minimizer_options_v1, bg_minimizer_options_v1_init);
    BG_TEST_EXACT_INITIALIZER(
        bg_minimization_report_v1, bg_minimization_report_v1_init);
    BG_TEST_EXACT_INITIALIZER(
        bg_dynamics_report_v1, bg_dynamics_report_v1_init);
}

static void test_context_contract(void) {
    assert(bg_abi_version() == BG_ABI_VERSION);
    assert(bg_abi_version_major() == BG_ABI_VERSION_MAJOR);
    assert(bg_abi_version_minor() == BG_ABI_VERSION_MINOR);
    assert(strcmp(bg_abi_version_string(), "1.4") == 0);
    assert(strcmp(BG_CANONICAL_TEMPERATURE_UNIT, "kelvin") == 0);
    assert(strcmp(bg_status_string(BG_STATUS_OK), "ok") == 0);
    assert(strcmp(
               bg_backend_string(BG_BACKEND_CPP_CPU_REFERENCE),
               "cpp_cpu_reference") == 0);
    assert(strcmp(bg_backend_string(BG_BACKEND_RUST_CPU), "rust_cpu") == 0);
    assert(strcmp(bg_backend_string(BG_BACKEND_HIP_SAFE), "hip_safe") == 0);
    assert(strcmp(bg_backend_string(BG_BACKEND_HIP_FAST), "hip_fast") == 0);
    assert(strcmp(
               bg_unit_system_string(BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL),
               "angstrom_kcal_mol") == 0);

    uint8_t available = 0;
    assert(bg_backend_is_available(
               BG_BACKEND_CPP_CPU_REFERENCE, 0, &available) ==
           BG_STATUS_OK);
    assert(available == 1);
    assert(bg_backend_is_available(BG_BACKEND_RUST_CPU, 0, &available) ==
           BG_STATUS_OK);
    assert(available == 1);
    assert(bg_backend_is_available(BG_BACKEND_HIP_SAFE, 0, &available) ==
           BG_STATUS_OK);
    const uint8_t hip_safe_available = available;
    assert(bg_backend_is_available(BG_BACKEND_HIP_FAST, 0, &available) ==
           BG_STATUS_OK);
    const uint8_t hip_available = available;
    available = 1;
    assert(bg_backend_is_available(BG_BACKEND_HIP_SAFE, INT32_MAX, &available) ==
           BG_STATUS_OK);
    assert(available == 0);
#if !BG_TEST_HIP_ENABLED
    assert(hip_available == 0);
#endif

    bg_context_options options;
    assert(bg_context_options_init(&options) == BG_STATUS_OK);
    bg_context *context = NULL;
    assert(bg_context_create(&options, &context) == BG_STATUS_OK);
    assert(context != NULL);

    bg_backend selected = BG_BACKEND_AUTO;
    bg_unit_system units = 0;
    int32_t ordinal = -1;
    assert(bg_context_get_backend(context, &selected) == BG_STATUS_OK);
    assert(selected == BG_BACKEND_RUST_CPU);
    assert(bg_context_get_unit_system(context, &units) == BG_STATUS_OK);
    assert(units == BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);
    assert(bg_context_get_device_ordinal(context, &ordinal) == BG_STATUS_OK);
    assert(ordinal == 0);
    bg_context_destroy(context);

    options.backend = BG_BACKEND_CPP_CPU_REFERENCE;
    context = NULL;
    assert(bg_context_create(&options, &context) == BG_STATUS_OK);
    assert(context != NULL);
    assert(bg_context_get_backend(context, &selected) == BG_STATUS_OK);
    assert(selected == BG_BACKEND_CPP_CPU_REFERENCE);
    bg_context_destroy(context);

    options.backend = BG_BACKEND_RUST_CPU;
    context = NULL;
    assert(bg_context_create(&options, &context) == BG_STATUS_OK);
    assert(context != NULL);
    assert(bg_context_get_backend(context, &selected) == BG_STATUS_OK);
    assert(selected == BG_BACKEND_RUST_CPU);
    bg_context_destroy(context);

    options.backend = BG_BACKEND_HIP_SAFE;
    context = NULL;
    if (hip_safe_available == 1) {
        assert(bg_context_create(&options, &context) == BG_STATUS_OK);
        assert(context != NULL);
        assert(bg_context_get_backend(context, &selected) == BG_STATUS_OK);
        assert(selected == BG_BACKEND_HIP_SAFE);
        bg_context_destroy(context);
    } else {
        assert(bg_context_create(&options, &context) ==
               BG_STATUS_BACKEND_UNAVAILABLE);
        assert(context == NULL);
    }

    options.backend = BG_BACKEND_HIP_FAST;
    context = (bg_context *)(uintptr_t)1;
    const bg_status hip_create_status = bg_context_create(&options, &context);
    bg_status unavailable_hip_status = hip_create_status;
#if BG_TEST_HIP_ENABLED
    if (hip_available != 0) {
        assert(hip_create_status == BG_STATUS_OK);
        assert(context != NULL);
        assert(bg_context_get_backend(context, &selected) == BG_STATUS_OK);
        assert(selected == BG_BACKEND_HIP);
        bg_context_destroy(context);
        context = NULL;

        /* Even in a HIP-enabled process, an explicitly unavailable ordinal
         * must fail closed instead of selecting CPU. */
        options.device_ordinal = INT32_MAX;
        context = (bg_context *)(uintptr_t)1;
        unavailable_hip_status = bg_context_create(&options, &context);
        assert(unavailable_hip_status == BG_STATUS_BACKEND_UNAVAILABLE);
        assert(context == NULL);
        assert(strstr(bg_last_error_message(), "fallback is forbidden") != NULL);
    } else {
        assert(hip_create_status == BG_STATUS_BACKEND_UNAVAILABLE);
        assert(context == NULL);
        assert(strstr(bg_last_error_message(), "fallback is forbidden") != NULL);
    }
#else
    assert(hip_create_status == BG_STATUS_BACKEND_UNAVAILABLE);
    assert(context == NULL);
    assert(strstr(bg_last_error_message(), "fallback is forbidden") != NULL);
#endif

    if (unavailable_hip_status == BG_STATUS_BACKEND_UNAVAILABLE) {
        uint64_t required = 0;
        assert(bg_last_error_message_copy(NULL, 0, &required) == BG_STATUS_OK);
        assert(required > 1);
        char too_small[2];
        assert(bg_last_error_message_copy(
                   too_small, sizeof(too_small), &required) ==
               BG_STATUS_BUFFER_TOO_SMALL);
        char message[256];
        assert(bg_last_error_message_copy(message, sizeof(message), &required) ==
               BG_STATUS_OK);
        assert(strstr(message, "fallback is forbidden") != NULL);
    }

    assert(bg_context_options_init(&options) == BG_STATUS_OK);
    options.reserved[2] = 1;
    assert(bg_context_create(&options, &context) == BG_STATUS_INVALID_ARGUMENT);
    assert(context == NULL);

    assert(bg_context_options_init(&options) == BG_STATUS_OK);
    options.abi_version += 1;
    assert(bg_context_create(&options, &context) == BG_STATUS_ABI_MISMATCH);
    assert(context == NULL);
}

static void test_owned_soa_and_transactional_update(void) {
    double x[3] = {1.0, 2.0, 3.0};
    double y[3] = {4.0, 5.0, 6.0};
    double z[3] = {7.0, 8.0, 9.0};
    double mass[3] = {1.0, 12.0, 16.0};
    double charge[3] = {0.25, -0.5, 0.25};

    bg_particle_soa particles;
    assert(bg_particle_soa_init(&particles) == BG_STATUS_OK);
    particles.particle_count = 3;
    particles.position_x_angstrom = x;
    particles.position_y_angstrom = y;
    particles.position_z_angstrom = z;
    particles.mass_dalton = mass;
    particles.charge_elementary = charge;

    bg_system *system = NULL;
    assert(bg_system_create(&particles, &system) == BG_STATUS_OK);
    assert(system != NULL);
    x[0] = 999.0;
    charge[1] = 999.0;

    uint64_t count = 0;
    bg_unit_system units = 0;
    assert(bg_system_get_particle_count(system, &count) == BG_STATUS_OK);
    assert(count == 3);
    assert(bg_system_get_unit_system(system, &units) == BG_STATUS_OK);
    assert(units == BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);

    bg_particle_soa_view view;
    assert(bg_particle_soa_view_init(&view) == BG_STATUS_OK);
    assert(bg_system_get_particles(system, &view) == BG_STATUS_OK);
    assert(view.particle_count == 3);
    assert(view.position_x_angstrom[0] == 1.0);
    assert(view.position_y_angstrom[1] == 5.0);
    assert(view.position_z_angstrom[2] == 9.0);
    assert(view.charge_elementary[1] == -0.5);
    assert(view.velocity_x_angstrom_per_femtosecond[0] == 0.0);
    assert(view.velocity_y_angstrom_per_femtosecond[1] == 0.0);
    assert(view.velocity_z_angstrom_per_femtosecond[2] == 0.0);
    const double *borrowed_x = view.position_x_angstrom;
    const double *borrowed_y = view.position_y_angstrom;
    const double *borrowed_z = view.position_z_angstrom;

    double new_x[3] = {-1.0, -2.0, -3.0};
    double new_y[3] = {-4.0, -5.0, -6.0};
    double new_z[3] = {-7.0, -8.0, -9.0};
    bg_position_soa positions;
    assert(bg_position_soa_init(&positions) == BG_STATUS_OK);
    positions.particle_count = 3;
    positions.x_angstrom = new_x;
    positions.y_angstrom = new_y;
    positions.z_angstrom = new_z;
    assert(bg_system_set_positions(system, &positions) == BG_STATUS_OK);

    assert(borrowed_x[2] == -3.0);
    assert(borrowed_y[0] == -4.0);
    assert(borrowed_z[1] == -8.0);

    assert(bg_particle_soa_view_init(&view) == BG_STATUS_OK);
    assert(bg_system_get_particles(system, &view) == BG_STATUS_OK);
    assert(view.position_x_angstrom == borrowed_x);
    assert(view.position_y_angstrom == borrowed_y);
    assert(view.position_z_angstrom == borrowed_z);
    assert(view.position_x_angstrom[2] == -3.0);
    assert(view.position_y_angstrom[0] == -4.0);

    new_x[1] = NAN;
    assert(bg_system_set_positions(system, &positions) ==
           BG_STATUS_INVALID_ARGUMENT);
    assert(bg_particle_soa_view_init(&view) == BG_STATUS_OK);
    assert(bg_system_get_particles(system, &view) == BG_STATUS_OK);
    assert(view.position_x_angstrom[0] == -1.0);
    assert(view.position_x_angstrom[1] == -2.0);
    assert(view.position_x_angstrom[2] == -3.0);

    bg_system_destroy(system);
}

static void test_empty_and_invalid_systems(void) {
    bg_particle_soa particles;
    assert(bg_particle_soa_init(&particles) == BG_STATUS_OK);
    bg_system *system = NULL;
    assert(bg_system_create(&particles, &system) == BG_STATUS_OK);
    assert(system != NULL);

    bg_particle_soa_view view;
    assert(bg_particle_soa_view_init(&view) == BG_STATUS_OK);
    assert(bg_system_get_particles(system, &view) == BG_STATUS_OK);
    assert(view.particle_count == 0);
    assert(view.position_x_angstrom == NULL);
    assert(view.mass_dalton == NULL);
    bg_system_destroy(system);

    double one = 1.0;
    assert(bg_particle_soa_init(&particles) == BG_STATUS_OK);
    particles.particle_count = UINT64_MAX;
    particles.position_x_angstrom = &one;
    particles.position_y_angstrom = &one;
    particles.position_z_angstrom = &one;
    particles.mass_dalton = &one;
    particles.charge_elementary = &one;
    assert(bg_system_create(&particles, &system) ==
           BG_STATUS_CAPACITY_OVERFLOW);
    assert(system == NULL);

    assert(bg_particle_soa_init(&particles) == BG_STATUS_OK);
    particles.particle_count = 1;
    particles.position_x_angstrom = &one;
    particles.position_y_angstrom = &one;
    particles.position_z_angstrom = &one;
    particles.mass_dalton = &one;
    particles.charge_elementary = &one;
    particles.velocity_x_angstrom_per_femtosecond = &one;
    assert(bg_system_create(&particles, &system) == BG_STATUS_INVALID_ARGUMENT);
    assert(system == NULL);

    assert(bg_particle_soa_init(&particles) == BG_STATUS_OK);
    particles.particle_count = 1;
    particles.position_x_angstrom = &one;
    particles.position_y_angstrom = &one;
    particles.position_z_angstrom = &one;
    particles.mass_dalton = &one;
    particles.charge_elementary = &one;
    one = 0.0;
    assert(bg_system_create(&particles, &system) == BG_STATUS_INVALID_ARGUMENT);
    assert(system == NULL);

    one = 1.0;
    if (_Alignof(double) > 1) {
        unsigned char misaligned_storage[sizeof(double) + _Alignof(double)];
        size_t misaligned_offset = 0;
        while ((((uintptr_t)(const void *)(misaligned_storage + misaligned_offset)) %
                _Alignof(double)) == 0) {
            ++misaligned_offset;
        }
        const double *misaligned =
            (const double *)(const void *)(misaligned_storage + misaligned_offset);
        particles.position_x_angstrom = misaligned;
        assert(bg_system_create(&particles, &system) ==
               BG_STATUS_INVALID_ARGUMENT);
        assert(system == NULL);
        assert(strstr(bg_last_error_message(), "aligned") != NULL);
    }
}

int main(void) {
    test_descriptor_initializer_compatibility();
    test_context_contract();
    test_owned_soa_and_transactional_update();
    test_empty_and_invalid_systems();
    return 0;
}
