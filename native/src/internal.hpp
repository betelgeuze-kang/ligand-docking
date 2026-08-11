#ifndef BETELGEUZE_NATIVE_INTERNAL_HPP
#define BETELGEUZE_NATIVE_INTERNAL_HPP

#if !defined(BG_DISABLE_DESCRIPTOR_INIT_CONVENIENCE_MACROS)
#  define BG_DISABLE_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#  define BG_INTERNAL_UNDEF_DESCRIPTOR_INIT_MACRO_GUARD
#endif
#include "betelgeuze/engine.h"
#if defined(BG_INTERNAL_UNDEF_DESCRIPTOR_INIT_MACRO_GUARD)
#  undef BG_DISABLE_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#  undef BG_INTERNAL_UNDEF_DESCRIPTOR_INIT_MACRO_GUARD
#endif

#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <new>
#include <stdexcept>
#include <type_traits>
#include <utility>
#include <vector>

struct bg_context final {
    bg_backend backend = BG_BACKEND_RUST_CPU;
    bg_unit_system unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
    int32_t device_ordinal = 0;
};

struct bg_system final {
    bg_unit_system unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
    std::vector<double> position_x;
    std::vector<double> position_y;
    std::vector<double> position_z;
    std::vector<double> velocity_x;
    std::vector<double> velocity_y;
    std::vector<double> velocity_z;
    std::vector<double> mass;
    std::vector<double> charge;
};

namespace betelgeuze::native {

inline constexpr std::size_t kLastErrorCapacity = 1024;
extern thread_local std::array<char, kLastErrorCapacity> last_error;

inline void clear_last_error() noexcept {
    last_error[0] = '\0';
}

inline void set_last_error(const char *message) noexcept {
    if (message == nullptr) {
        message = "";
    }
    std::size_t index = 0;
    while (index + 1 < last_error.size() && message[index] != '\0') {
        last_error[index] = message[index];
        ++index;
    }
    last_error[index] = '\0';
}

inline bg_status fail(bg_status status, const char *message) noexcept {
    set_last_error(message);
    return status;
}

template <typename Function>
bg_status guarded_status(Function &&function) noexcept {
    clear_last_error();
    try {
        return std::forward<Function>(function)();
    } catch (const std::length_error &) {
        set_last_error("native container capacity exceeded");
        return BG_STATUS_CAPACITY_OVERFLOW;
    } catch (const std::bad_alloc &) {
        set_last_error("native allocation failed");
        return BG_STATUS_OUT_OF_MEMORY;
    } catch (const std::exception &) {
        set_last_error("native operation failed");
        return BG_STATUS_INTERNAL_ERROR;
    } catch (...) {
        set_last_error("unknown native exception");
        return BG_STATUS_INTERNAL_ERROR;
    }
}

inline bg_status validate_descriptor_header(
    uint32_t observed_size,
    std::size_t expected_size,
    uint32_t observed_version,
    const char *size_error,
    const char *version_error) noexcept {
    static_assert(sizeof(std::size_t) <= sizeof(uint64_t));
    if (expected_size > std::numeric_limits<uint32_t>::max() ||
        observed_size != static_cast<uint32_t>(expected_size)) {
        return fail(BG_STATUS_ABI_MISMATCH, size_error);
    }
    if (observed_version != BG_ABI_VERSION) {
        return fail(BG_STATUS_ABI_MISMATCH, version_error);
    }
    return BG_STATUS_OK;
}

/* Check the caller's compiled layout before dereferencing its descriptor. */
inline bg_status validate_initializer_compatibility(
    const void *descriptor,
    std::size_t caller_struct_size,
    std::size_t native_struct_size,
    uint32_t caller_abi_version,
    const char *null_error,
    const char *size_error,
    const char *version_error) noexcept {
    if (descriptor == nullptr) {
        return fail(BG_STATUS_INVALID_ARGUMENT, null_error);
    }
    if (native_struct_size > std::numeric_limits<uint32_t>::max() ||
        caller_struct_size != native_struct_size) {
        return fail(BG_STATUS_ABI_MISMATCH, size_error);
    }
    if (caller_abi_version != BG_ABI_VERSION) {
        return fail(BG_STATUS_ABI_MISMATCH, version_error);
    }
    return BG_STATUS_OK;
}

template <std::size_t Size>
bool reserved_is_zero(const uint64_t (&reserved)[Size]) noexcept {
    for (const uint64_t value : reserved) {
        if (value != UINT64_C(0)) {
            return false;
        }
    }
    return true;
}

inline bg_status validate_unit_system(bg_unit_system units) noexcept {
    if (units != BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "unit_system must be BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL");
    }
    return BG_STATUS_OK;
}

inline bg_status checked_particle_count(
    uint64_t particle_count,
    std::size_t *out_count) noexcept {
    if (out_count == nullptr) {
        return fail(BG_STATUS_INTERNAL_ERROR, "internal count output is null");
    }
    if constexpr (sizeof(std::size_t) < sizeof(uint64_t)) {
        if (particle_count > static_cast<uint64_t>(
                                 std::numeric_limits<std::size_t>::max())) {
            return fail(
                BG_STATUS_CAPACITY_OVERFLOW,
                "particle_count does not fit the native address space");
        }
    }

    constexpr std::size_t channel_count = 8;
    constexpr std::size_t bytes_per_particle = channel_count * sizeof(double);
    const uint64_t max_total_count = static_cast<uint64_t>(
        std::numeric_limits<std::size_t>::max() / bytes_per_particle);
    if (particle_count > max_total_count) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "particle_count overflows owned SoA capacity");
    }

    const uint64_t max_vector_count = static_cast<uint64_t>(
        std::numeric_limits<std::ptrdiff_t>::max() / sizeof(double));
    if (particle_count > max_vector_count) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "particle_count exceeds vector capacity");
    }

    *out_count = static_cast<std::size_t>(particle_count);
    return BG_STATUS_OK;
}

inline std::vector<double> copy_channel(
    const double *source,
    std::size_t count) {
    if (count == 0) {
        return {};
    }
    return std::vector<double>(source, source + count);
}

inline bool all_finite(const std::vector<double> &values) noexcept {
    for (const double value : values) {
        if (!std::isfinite(value)) {
            return false;
        }
    }
    return true;
}

inline bool all_positive_finite(const std::vector<double> &values) noexcept {
    for (const double value : values) {
        if (!std::isfinite(value) || value <= 0.0) {
            return false;
        }
    }
    return true;
}

inline bool double_pointer_is_aligned(const double *pointer) noexcept {
    return pointer == nullptr ||
           (reinterpret_cast<std::uintptr_t>(pointer) % alignof(double)) == 0;
}

inline const double *borrowed_data(const std::vector<double> &values) noexcept {
    return values.empty() ? nullptr : values.data();
}

}  // namespace betelgeuze::native

#endif  // BETELGEUZE_NATIVE_INTERNAL_HPP
