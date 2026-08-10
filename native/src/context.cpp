#include "internal.hpp"

#include <cstring>
#include <memory>

namespace betelgeuze::native {

thread_local std::array<char, kLastErrorCapacity> last_error{};

namespace {

bg_status validate_context_options(const bg_context_options &options) noexcept {
    bg_status status = validate_descriptor_header(
        options.struct_size,
        sizeof(bg_context_options),
        options.abi_version,
        "bg_context_options struct_size does not match ABI v1",
        "bg_context_options abi_version does not match the native library");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = validate_unit_system(options.unit_system);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (options.reserved0 != UINT32_C(0) ||
        !reserved_is_zero(options.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "bg_context_options reserved fields must be zero");
    }
    if (options.flags != UINT64_C(0)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "bg_context_options flags must be zero for ABI v1");
    }
    if (options.device_ordinal < 0) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "device_ordinal must be non-negative");
    }
    switch (options.backend) {
        case BG_BACKEND_AUTO:
        case BG_BACKEND_CPU:
        case BG_BACKEND_HIP:
            return BG_STATUS_OK;
        default:
            return fail(
                BG_STATUS_UNSUPPORTED_BACKEND,
                "unsupported backend identifier");
    }
}

bool cpu_is_available(int32_t device_ordinal) noexcept {
    return device_ordinal == 0;
}

/* No HIP provider is linked in ABI v1 yet.  Merely compiling with hipcc must
 * never make this return true; a provider must implement allocation, stream,
 * and execution ownership before it can be wired here. */
bool hip_is_available(int32_t /*device_ordinal*/) noexcept {
    return false;
}

}  // namespace
}  // namespace betelgeuze::native

extern "C" BG_API uint32_t BG_CALL bg_abi_version(void) BG_NOEXCEPT {
    return BG_ABI_VERSION;
}

extern "C" BG_API uint32_t BG_CALL bg_abi_version_major(void) BG_NOEXCEPT {
    return BG_ABI_VERSION_MAJOR;
}

extern "C" BG_API uint32_t BG_CALL bg_abi_version_minor(void) BG_NOEXCEPT {
    return BG_ABI_VERSION_MINOR;
}

extern "C" BG_API const char *BG_CALL bg_abi_version_string(void) BG_NOEXCEPT {
    return "1.0";
}

extern "C" BG_API const char *BG_CALL bg_status_string(
    bg_status status) BG_NOEXCEPT {
    switch (status) {
        case BG_STATUS_OK:
            return "ok";
        case BG_STATUS_INVALID_ARGUMENT:
            return "invalid_argument";
        case BG_STATUS_ABI_MISMATCH:
            return "abi_mismatch";
        case BG_STATUS_UNSUPPORTED_BACKEND:
            return "unsupported_backend";
        case BG_STATUS_BACKEND_UNAVAILABLE:
            return "backend_unavailable";
        case BG_STATUS_OUT_OF_MEMORY:
            return "out_of_memory";
        case BG_STATUS_CAPACITY_OVERFLOW:
            return "capacity_overflow";
        case BG_STATUS_BUFFER_TOO_SMALL:
            return "buffer_too_small";
        case BG_STATUS_BACKEND_ERROR:
            return "backend_error";
        case BG_STATUS_INTERNAL_ERROR:
            return "internal_error";
        default:
            return "unknown_status";
    }
}

extern "C" BG_API const char *BG_CALL bg_backend_string(
    bg_backend backend) BG_NOEXCEPT {
    switch (backend) {
        case BG_BACKEND_AUTO:
            return "auto";
        case BG_BACKEND_CPU:
            return "cpu";
        case BG_BACKEND_HIP:
            return "hip";
        default:
            return "unknown_backend";
    }
}

extern "C" BG_API const char *BG_CALL bg_unit_system_string(
    bg_unit_system units) BG_NOEXCEPT {
    if (units == BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL) {
        return "angstrom_kcal_mol";
    }
    return "unknown_unit_system";
}

extern "C" BG_API const char *BG_CALL bg_last_error_message(void) BG_NOEXCEPT {
    return betelgeuze::native::last_error.data();
}

extern "C" BG_API bg_status BG_CALL bg_last_error_message_copy(
    char *buffer,
    uint64_t buffer_capacity,
    uint64_t *required_size) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    if (required_size == nullptr) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "required_size must not be null");
    }

    const std::array<char, kLastErrorCapacity> snapshot = last_error;
    const std::size_t message_size = std::strlen(snapshot.data()) + 1;
    *required_size = static_cast<uint64_t>(message_size);
    if (buffer == nullptr) {
        if (buffer_capacity == UINT64_C(0)) {
            return BG_STATUS_OK;
        }
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "buffer must not be null when buffer_capacity is non-zero");
    }
    if (buffer_capacity < static_cast<uint64_t>(message_size)) {
        return BG_STATUS_BUFFER_TOO_SMALL;
    }
    std::memmove(buffer, snapshot.data(), message_size);
    return BG_STATUS_OK;
}

extern "C" BG_API bg_status BG_CALL bg_context_options_init(
    bg_context_options *options) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        if (options == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "bg_context_options pointer must not be null");
        }
        *options = bg_context_options{};
        options->struct_size = static_cast<uint32_t>(sizeof(bg_context_options));
        options->abi_version = BG_ABI_VERSION;
        options->backend = BG_BACKEND_AUTO;
        options->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        options->device_ordinal = 0;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_particle_soa_init(
    bg_particle_soa *particles) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        if (particles == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "bg_particle_soa pointer must not be null");
        }
        *particles = bg_particle_soa{};
        particles->struct_size = static_cast<uint32_t>(sizeof(bg_particle_soa));
        particles->abi_version = BG_ABI_VERSION;
        particles->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_particle_soa_view_init(
    bg_particle_soa_view *view) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        if (view == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "bg_particle_soa_view pointer must not be null");
        }
        *view = bg_particle_soa_view{};
        view->struct_size = static_cast<uint32_t>(sizeof(bg_particle_soa_view));
        view->abi_version = BG_ABI_VERSION;
        view->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_position_soa_init(
    bg_position_soa *positions) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        if (positions == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "bg_position_soa pointer must not be null");
        }
        *positions = bg_position_soa{};
        positions->struct_size = static_cast<uint32_t>(sizeof(bg_position_soa));
        positions->abi_version = BG_ABI_VERSION;
        positions->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_backend_is_available(
    bg_backend backend,
    int32_t device_ordinal,
    uint8_t *available) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        if (available == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "available output must not be null");
        }
        *available = UINT8_C(0);
        if (device_ordinal < 0) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "device_ordinal must be non-negative");
        }
        switch (backend) {
            case BG_BACKEND_AUTO:
            case BG_BACKEND_CPU:
                *available = cpu_is_available(device_ordinal) ? UINT8_C(1)
                                                               : UINT8_C(0);
                return BG_STATUS_OK;
            case BG_BACKEND_HIP:
                *available = hip_is_available(device_ordinal) ? UINT8_C(1)
                                                               : UINT8_C(0);
                return BG_STATUS_OK;
            default:
                return fail(
                    BG_STATUS_UNSUPPORTED_BACKEND,
                    "unsupported backend identifier");
        }
    });
}

extern "C" BG_API bg_status BG_CALL bg_context_create(
    const bg_context_options *options,
    bg_context **out_context) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    if (out_context != nullptr) {
        *out_context = nullptr;
    }
    return guarded_status([&]() -> bg_status {
        if (out_context == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "out_context must not be null");
        }
        if (options == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "bg_context_options must not be null");
        }
        bg_status status = validate_context_options(*options);
        if (status != BG_STATUS_OK) {
            return status;
        }

        bg_backend selected_backend = options->backend;
        if (selected_backend == BG_BACKEND_AUTO) {
            if (!cpu_is_available(options->device_ordinal)) {
                return fail(
                    BG_STATUS_BACKEND_UNAVAILABLE,
                    "no backend is available at the requested device ordinal");
            }
            selected_backend = BG_BACKEND_CPU;
        } else if (selected_backend == BG_BACKEND_CPU) {
            if (!cpu_is_available(options->device_ordinal)) {
                return fail(
                    BG_STATUS_BACKEND_UNAVAILABLE,
                    "requested CPU device ordinal is unavailable");
            }
        } else if (!hip_is_available(options->device_ordinal)) {
            return fail(
                BG_STATUS_BACKEND_UNAVAILABLE,
                "HIP backend is unavailable; CPU fallback is forbidden");
        }

        auto context = std::make_unique<bg_context>();
        context->backend = selected_backend;
        context->unit_system = options->unit_system;
        context->device_ordinal = options->device_ordinal;
        *out_context = context.release();
        return BG_STATUS_OK;
    });
}

extern "C" BG_API void BG_CALL bg_context_destroy(
    bg_context *context) BG_NOEXCEPT {
    delete context;
}

extern "C" BG_API bg_status BG_CALL bg_context_get_backend(
    const bg_context *context,
    bg_backend *backend) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        if (context == nullptr || backend == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "context and backend output must not be null");
        }
        *backend = context->backend;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_context_get_device_ordinal(
    const bg_context *context,
    int32_t *device_ordinal) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        if (context == nullptr || device_ordinal == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "context and device_ordinal output must not be null");
        }
        *device_ordinal = context->device_ordinal;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_context_get_unit_system(
    const bg_context *context,
    bg_unit_system *unit_system) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        if (context == nullptr || unit_system == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "context and unit_system output must not be null");
        }
        *unit_system = context->unit_system;
        return BG_STATUS_OK;
    });
}
