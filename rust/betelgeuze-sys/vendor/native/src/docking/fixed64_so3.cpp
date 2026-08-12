#include "../dynamics/sha256.hpp"
#include "../hip/provider.h"
#include "../internal.hpp"
#include "../rust/provider.h"
#include "fixed64_so3_reference.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>

#ifndef BG_HAS_HIP_SAFE_PROVIDER
#  define BG_HAS_HIP_SAFE_PROVIDER 0
#endif
#ifndef BG_ENABLE_HIP
#  define BG_ENABLE_HIP 0
#endif

namespace betelgeuze::native::docking::fixed64_so3 {
namespace {

using dynamics::Sha256;

constexpr std::size_t kOrientationCount =
    BG_DOCKING_FIXED64_SO3_ORIENTATION_COUNT;
constexpr std::size_t kMaximumAttempts = kOrientationCount * 1024U;
constexpr double kDuplicateToleranceRadians = 1.0e-10;
constexpr double kGeometryEpsilon = 1.0e-12;
constexpr double kTwoPow64 = 18446744073709551616.0;
constexpr std::array<uint32_t, 3> kBases = {
    UINT32_C(2), UINT32_C(3), UINT32_C(5)};
constexpr char kRowSchema[] =
    "betelgeuze.engine_v2_native_fixed64_so3_row/1.0.0";
constexpr char kBatchSchema[] =
    "betelgeuze.engine_v2_native_fixed64_so3_batch/1.0.0";

struct Quaternion final {
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
    double w = 0.0;
};

struct MemoryRange final {
    uintptr_t begin = 0;
    uintptr_t end = 0;
};

class CanonicalHash final {
  public:
    explicit CanonicalHash(const char *domain) noexcept { string(domain); }

    void byte(uint8_t value) noexcept { hash_.update(&value, 1); }

    void u32(uint32_t value) noexcept {
        std::array<uint8_t, 4> bytes{};
        for (std::size_t index = 0; index < bytes.size(); ++index) {
            bytes[bytes.size() - 1U - index] = static_cast<uint8_t>(
                value >> static_cast<uint32_t>(index * 8U));
        }
        hash_.update(bytes.data(), bytes.size());
    }

    void u64(uint64_t value) noexcept {
        std::array<uint8_t, 8> bytes{};
        for (std::size_t index = 0; index < bytes.size(); ++index) {
            bytes[bytes.size() - 1U - index] = static_cast<uint8_t>(
                value >> static_cast<uint32_t>(index * 8U));
        }
        hash_.update(bytes.data(), bytes.size());
    }

    void f64(double value) noexcept {
        uint64_t bits = 0;
        static_assert(sizeof(bits) == sizeof(value));
        std::memcpy(&bits, &value, sizeof(bits));
        u64(bits);
    }

    void bytes(const uint8_t *values, std::size_t count) noexcept {
        u64(static_cast<uint64_t>(count));
        hash_.update(values, count);
    }

    void string(const char *value) noexcept {
        bytes(
            reinterpret_cast<const uint8_t *>(value),
            std::strlen(value));
    }

    void digest(const uint8_t (&value)[32]) noexcept {
        hash_.update(value, 32);
    }

    [[nodiscard]] std::array<uint8_t, 32> finish() noexcept {
        return hash_.finish();
    }

  private:
    Sha256 hash_;
};

template <typename Type>
[[nodiscard]] bool make_range(
    const Type *pointer,
    std::size_t count,
    MemoryRange *output) noexcept {
    if (output == nullptr) {
        return false;
    }
    if (pointer == nullptr || count == 0) {
        *output = {};
        return true;
    }
    if (count > std::numeric_limits<std::size_t>::max() / sizeof(Type)) {
        return false;
    }
    const std::size_t bytes = count * sizeof(Type);
    const auto begin = reinterpret_cast<uintptr_t>(pointer);
    if (begin > std::numeric_limits<uintptr_t>::max() - bytes) {
        return false;
    }
    *output = {begin, begin + bytes};
    return true;
}

[[nodiscard]] bool overlaps(MemoryRange left, MemoryRange right) noexcept {
    return left.begin != left.end && right.begin != right.end &&
           left.begin < right.end && right.begin < left.end;
}

[[nodiscard]] double radical_inverse(uint64_t index, uint32_t base) noexcept {
    const double inverse_base = 1.0 / static_cast<double>(base);
    double fraction = inverse_base;
    double value = 0.0;
    const uint64_t wide_base = base;
    while (index != 0) {
        const uint64_t digit = index % wide_base;
        index /= wide_base;
        value += static_cast<double>(digit) * fraction;
        fraction *= inverse_base;
    }
    return value;
}

[[nodiscard]] uint64_t read_u64_be(const uint8_t *bytes) noexcept {
    uint64_t value = 0;
    for (std::size_t index = 0; index < 8; ++index) {
        value = (value << 8U) | bytes[index];
    }
    return value;
}

[[nodiscard]] std::array<double, 3> seed_offsets(
    const uint8_t (&seed)[32]) noexcept {
    return {
        static_cast<double>(read_u64_be(seed)) / kTwoPow64,
        static_cast<double>(read_u64_be(seed + 8)) / kTwoPow64,
        static_cast<double>(read_u64_be(seed + 16)) / kTwoPow64,
    };
}

[[nodiscard]] Quaternion canonicalize(Quaternion value) noexcept {
    const double maximum = std::max(
        {std::abs(value.x),
         std::abs(value.y),
         std::abs(value.z),
         std::abs(value.w)});
    if (!std::isfinite(maximum) || maximum <= kGeometryEpsilon) {
        return {};
    }
    const double scaled_norm = std::hypot(
        std::hypot(std::hypot(value.x / maximum, value.y / maximum),
                   value.z / maximum),
        value.w / maximum);
    const double norm = maximum * scaled_norm;
    const double inverse =
        std::isfinite(norm) && std::abs(norm - 1.0) <= 1.0e-15
            ? 1.0
            : (1.0 / maximum) / scaled_norm;
    value = {
        value.x * inverse,
        value.y * inverse,
        value.z * inverse,
        value.w * inverse,
    };
    const std::array<double, 4> order = {
        value.w, value.z, value.y, value.x};
    for (double component : order) {
        if (component > 0.0) {
            break;
        }
        if (component < 0.0) {
            value = {-value.x, -value.y, -value.z, -value.w};
            break;
        }
    }
    if (value.x == 0.0) {
        value.x = 0.0;
    }
    if (value.y == 0.0) {
        value.y = 0.0;
    }
    if (value.z == 0.0) {
        value.z = 0.0;
    }
    if (value.w == 0.0) {
        value.w = 0.0;
    }
    return value;
}

[[nodiscard]] Quaternion low_discrepancy_quaternion(
    uint64_t raw_index,
    const std::array<double, 3> &offsets) noexcept {
    std::array<double, 3> unit{};
    for (std::size_t index = 0; index < unit.size(); ++index) {
        const double shifted =
            radical_inverse(raw_index, kBases[index]) + offsets[index];
        unit[index] = shifted - std::floor(shifted);
    }
    const double first_radius = std::sqrt(std::max(0.0, 1.0 - unit[0]));
    const double second_radius = std::sqrt(std::max(0.0, unit[0]));
    const double first_angle = 2.0 * std::acos(-1.0) * unit[1];
    const double second_angle = 2.0 * std::acos(-1.0) * unit[2];
    return canonicalize({
        first_radius * std::sin(first_angle),
        first_radius * std::cos(first_angle),
        second_radius * std::sin(second_angle),
        second_radius * std::cos(second_angle),
    });
}

[[nodiscard]] double geodesic_distance(
    Quaternion left,
    Quaternion right) noexcept {
    const double dot = left.x * right.x + left.y * right.y +
                       left.z * right.z + left.w * right.w;
    const double sign = dot < 0.0 ? -1.0 : 1.0;
    const double difference = std::hypot(
        std::hypot(
            std::hypot(left.x - sign * right.x,
                       left.y - sign * right.y),
            left.z - sign * right.z),
        left.w - sign * right.w);
    const double sum = std::hypot(
        std::hypot(
            std::hypot(left.x + sign * right.x,
                       left.y + sign * right.y),
            left.z + sign * right.z),
        left.w + sign * right.w);
    if (difference <= kGeometryEpsilon && sum <= kGeometryEpsilon) {
        return 0.0;
    }
    return 4.0 * std::atan2(difference, sum);
}

[[nodiscard]] std::array<bg_docking_fixed64_so3_row_v1, kOrientationCount>
generate_cpp(const bg_docking_fixed64_so3_input_v1 &input) noexcept {
    std::array<bg_docking_fixed64_so3_row_v1, kOrientationCount> rows{};
    const auto offsets = seed_offsets(input.source_seed_sha256);
    std::size_t accepted = 0;
    for (std::size_t raw = 0;
         raw < kMaximumAttempts && accepted < kOrientationCount;
         ++raw) {
        const Quaternion quaternion = low_discrepancy_quaternion(
            static_cast<uint64_t>(raw), offsets);
        if (!std::isfinite(quaternion.x) || !std::isfinite(quaternion.y) ||
            !std::isfinite(quaternion.z) || !std::isfinite(quaternion.w)) {
            continue;
        }
        bool duplicate = false;
        for (std::size_t previous = 0; previous < accepted; ++previous) {
            const auto &row = rows[previous];
            duplicate = duplicate || geodesic_distance(
                quaternion,
                {row.quaternion_x,
                 row.quaternion_y,
                 row.quaternion_z,
                 row.quaternion_w}) <= kDuplicateToleranceRadians;
        }
        if (duplicate) {
            continue;
        }
        auto &row = rows[accepted];
        row.orientation_index = static_cast<uint32_t>(accepted);
        row.status = BG_DOCKING_FIXED64_SO3_ROW_GENERATED;
        row.failure_code = BG_DOCKING_FIXED64_SO3_FAILURE_NONE;
        row.raw_sequence_index = static_cast<uint64_t>(raw);
        row.quaternion_x = quaternion.x;
        row.quaternion_y = quaternion.y;
        row.quaternion_z = quaternion.z;
        row.quaternion_w = quaternion.w;
        const double norm = std::hypot(
            std::hypot(std::hypot(quaternion.x, quaternion.y), quaternion.z),
            quaternion.w);
        row.norm_error = std::abs(norm - 1.0);
        row.denominator_preserved = UINT8_C(1);
        ++accepted;
    }
    if (accepted != kOrientationCount) {
        for (std::size_t index = accepted; index < kOrientationCount;
             ++index) {
            rows[index].orientation_index = static_cast<uint32_t>(index);
            rows[index].status =
                BG_DOCKING_FIXED64_SO3_ROW_TYPED_FAILURE;
            rows[index].failure_code =
                BG_DOCKING_FIXED64_SO3_FAILURE_SEQUENCE_EXHAUSTED;
            rows[index].denominator_preserved = UINT8_C(1);
        }
    }
    return rows;
}

[[nodiscard]] bool digest_is_zero(const uint8_t *value) noexcept {
    return std::all_of(value, value + 32, [](uint8_t byte) {
        return byte == UINT8_C(0);
    });
}

[[nodiscard]] bool row_shape_is_valid(
    const bg_docking_fixed64_so3_row_v1 &row,
    const bg_docking_fixed64_so3_row_v1 &expected,
    std::size_t index,
    double norm_tolerance) noexcept {
    if (row.orientation_index != index ||
        row.status != BG_DOCKING_FIXED64_SO3_ROW_GENERATED ||
        row.failure_code != BG_DOCKING_FIXED64_SO3_FAILURE_NONE ||
        row.reserved0 != 0 || row.raw_sequence_index < index ||
        !std::isfinite(row.quaternion_x) ||
        !std::isfinite(row.quaternion_y) ||
        !std::isfinite(row.quaternion_z) ||
        !std::isfinite(row.quaternion_w) ||
        !std::isfinite(row.norm_error) || row.norm_error < 0.0 ||
        row.norm_error > norm_tolerance ||
        !digest_is_zero(row.row_receipt_sha256) ||
        row.result_dependent_input_consumed != UINT8_C(0) ||
        row.duplicate_orientation_emitted != UINT8_C(0) ||
        row.denominator_preserved != UINT8_C(1) ||
        row.molecular_execution_authorized != UINT8_C(0) ||
        row.reservation_authorized != UINT8_C(0) ||
        row.benchmark_execution_authorized != UINT8_C(0) ||
        row.production_claim_authorized != UINT8_C(0) ||
        row.reserved1 != UINT8_C(0) || !reserved_is_zero(row.reserved)) {
        return false;
    }
    const Quaternion quaternion = {
        row.quaternion_x,
        row.quaternion_y,
        row.quaternion_z,
        row.quaternion_w};
    const double norm = std::hypot(
        std::hypot(std::hypot(quaternion.x, quaternion.y), quaternion.z),
        quaternion.w);
    const double observed_norm_error = std::abs(norm - 1.0);
    const auto component_matches = [norm_tolerance](
                                       double observed,
                                       double reference) noexcept {
        return std::isfinite(observed) &&
               std::abs(observed - reference) <= norm_tolerance &&
               !(observed == 0.0 && std::signbit(observed));
    };
    return std::isfinite(norm) &&
           observed_norm_error <= norm_tolerance &&
           std::abs(observed_norm_error - row.norm_error) <= norm_tolerance &&
           row.raw_sequence_index == expected.raw_sequence_index &&
           component_matches(row.quaternion_x, expected.quaternion_x) &&
           component_matches(row.quaternion_y, expected.quaternion_y) &&
           component_matches(row.quaternion_z, expected.quaternion_z) &&
           component_matches(row.quaternion_w, expected.quaternion_w);
}

[[nodiscard]] bool batch_shape_is_valid(
    const bg_docking_fixed64_so3_input_v1 &input,
    const std::array<bg_docking_fixed64_so3_row_v1, kOrientationCount> &rows,
    bg_backend backend) noexcept {
    const double norm_tolerance =
        backend == BG_BACKEND_HIP_FAST
            ? 2.0e-9
            : (backend == BG_BACKEND_HIP_SAFE ? 2.0e-10 : 2.0e-12);
    const auto reference = reference_rows(input);
    for (std::size_t index = 0; index < rows.size(); ++index) {
        if (!row_shape_is_valid(
                rows[index], reference[index], index, norm_tolerance) ||
            (index != 0 && rows[index].raw_sequence_index <=
                               rows[index - 1U].raw_sequence_index)) {
            return false;
        }
        const Quaternion current = {
            rows[index].quaternion_x,
            rows[index].quaternion_y,
            rows[index].quaternion_z,
            rows[index].quaternion_w};
        for (std::size_t previous = 0; previous < index; ++previous) {
            const auto &candidate = rows[previous];
            if (geodesic_distance(
                    current,
                    {candidate.quaternion_x,
                     candidate.quaternion_y,
                     candidate.quaternion_z,
                     candidate.quaternion_w}) <=
                kDuplicateToleranceRadians) {
                return false;
            }
        }
    }
    return true;
}

[[nodiscard]] std::array<uint8_t, 32> row_receipt(
    const bg_docking_fixed64_so3_input_v1 &input,
    bg_backend backend,
    const bg_docking_fixed64_so3_row_v1 &row) noexcept {
    CanonicalHash hash("betelgeuze.fixed64_so3_row/native-v1");
    hash.string(kRowSchema);
    hash.digest(input.source_seed_sha256);
    hash.u32(static_cast<uint32_t>(backend));
    hash.u32(row.orientation_index);
    hash.u64(row.raw_sequence_index);
    hash.f64(row.quaternion_x);
    hash.f64(row.quaternion_y);
    hash.f64(row.quaternion_z);
    hash.f64(row.quaternion_w);
    hash.f64(row.norm_error);
    hash.byte(row.result_dependent_input_consumed);
    hash.byte(row.duplicate_orientation_emitted);
    hash.byte(row.denominator_preserved);
    hash.byte(row.molecular_execution_authorized);
    hash.byte(row.reservation_authorized);
    hash.byte(row.benchmark_execution_authorized);
    hash.byte(row.production_claim_authorized);
    return hash.finish();
}

[[nodiscard]] std::array<uint8_t, 32> batch_receipt(
    const bg_docking_fixed64_so3_input_v1 &input,
    bg_backend backend,
    const std::array<bg_docking_fixed64_so3_row_v1, kOrientationCount> &rows)
    noexcept {
    CanonicalHash hash("betelgeuze.fixed64_so3_batch/native-v1");
    hash.string(kBatchSchema);
    hash.digest(input.source_seed_sha256);
    hash.u32(static_cast<uint32_t>(backend));
    hash.u64(static_cast<uint64_t>(rows.size()));
    for (const auto &row : rows) {
        hash.digest(row.row_receipt_sha256);
    }
    hash.byte(UINT8_C(0));
    hash.byte(UINT8_C(1));
    hash.byte(UINT8_C(0));
    hash.byte(UINT8_C(0));
    hash.byte(UINT8_C(0));
    hash.byte(UINT8_C(0));
    return hash.finish();
}

[[nodiscard]] bg_status validate_input(
    const bg_docking_fixed64_so3_input_v1 &input) noexcept {
    const bg_status status = validate_descriptor_header(
        input.struct_size,
        sizeof(input),
        input.abi_version,
        "fixed64 SO3 input size does not match ABI v1",
        "fixed64 SO3 input ABI version does not match");
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (!reserved_is_zero(input.reserved) ||
        digest_is_zero(input.source_seed_sha256)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 SO3 seed must be present and reserved fields zero");
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status validate_output(
    const bg_context &context,
    const bg_docking_fixed64_so3_input_v1 &input,
    const bg_docking_fixed64_so3_output_v1 &output) noexcept {
    const bg_status status = validate_descriptor_header(
        output.struct_size,
        sizeof(output),
        output.abi_version,
        "fixed64 SO3 output size does not match ABI v1",
        "fixed64 SO3 output ABI version does not match");
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (output.row_capacity < kOrientationCount || output.rows == nullptr ||
        !pointer_is_aligned(output.rows)) {
        return fail(
            BG_STATUS_BUFFER_TOO_SMALL,
            "fixed64 SO3 output requires 64 aligned rows");
    }
    if (output.reserved0 != 0 || output.reserved1[0] != 0 ||
        output.reserved1[1] != 0 || !reserved_is_zero(output.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 SO3 output reserved fields must be zero");
    }
    std::array<MemoryRange, 4> ranges{};
    if (!make_range(&context, 1, &ranges[0]) ||
        !make_range(&input, 1, &ranges[1]) ||
        !make_range(&output, 1, &ranges[2]) ||
        !make_range(output.rows, kOrientationCount, &ranges[3])) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "fixed64 SO3 input or output range overflows");
    }
    for (std::size_t left = 0; left < ranges.size(); ++left) {
        for (std::size_t right = left + 1; right < ranges.size(); ++right) {
            if (overlaps(ranges[left], ranges[right])) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "fixed64 SO3 context, input, and output ranges overlap");
            }
        }
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status rust_failure(
    int32_t raw_status,
    const bg_rust_cpu_error_v1 &error) noexcept {
    return fail(
        static_cast<bg_status>(raw_status),
        error.message[0] == '\0'
            ? "rust_cpu fixed64 SO3 generation failed"
            : error.message);
}

#if BG_HAS_HIP_SAFE_PROVIDER || BG_ENABLE_HIP
[[nodiscard]] bg_status hip_failure(
    int32_t raw_status,
    const char *error,
    const char *fallback) noexcept {
    return fail(
        static_cast<bg_status>(raw_status),
        error != nullptr && error[0] != '\0' ? error : fallback);
}
#endif

[[nodiscard]] bg_status generate_backend(
    const bg_context &context,
    const bg_docking_fixed64_so3_input_v1 &input,
    std::array<bg_docking_fixed64_so3_row_v1, kOrientationCount> *rows)
    noexcept {
    if (context.backend == BG_BACKEND_CPP_CPU_REFERENCE) {
        *rows = generate_cpp(input);
        return BG_STATUS_OK;
    }
    if (context.backend == BG_BACKEND_RUST_CPU) {
        bg_rust_cpu_error_v1 error{};
        error.struct_size = sizeof(error);
        error.abi_version = BG_RUST_CPU_PROVIDER_ABI_VERSION;
        const int32_t status =
            bg_rust_cpu_docking_fixed64_so3_v1_generate(
                &input, rows->data(), &error);
        return status == BG_STATUS_OK ? BG_STATUS_OK
                                      : rust_failure(status, error);
    }
#if BG_HAS_HIP_SAFE_PROVIDER
    if (context.backend == BG_BACKEND_HIP_SAFE) {
        char error[BG_HIP_SAFE_ERROR_CAPACITY]{};
        const int32_t status =
            bg_hip_safe_docking_fixed64_so3_v1_generate(
                context.device_ordinal,
                &input,
                rows->data(),
                error,
                sizeof(error));
        return status == BG_STATUS_OK
                   ? BG_STATUS_OK
                   : hip_failure(
                         status,
                         error,
                         "hip_safe fixed64 SO3 generation failed");
    }
#endif
#if BG_ENABLE_HIP
    if (context.backend == BG_BACKEND_HIP_FAST) {
        char error[BG_HIP_SAFE_ERROR_CAPACITY]{};
        const int32_t status =
            bg_hip_fast_docking_fixed64_so3_v1_generate(
                context.device_ordinal,
                &input,
                rows->data(),
                error,
                sizeof(error));
        return status == BG_STATUS_OK
                   ? BG_STATUS_OK
                   : hip_failure(
                         status,
                         error,
                         "hip_fast fixed64 SO3 generation failed");
    }
#endif
    return fail(
        BG_STATUS_BACKEND_UNAVAILABLE,
        "selected backend has no native fixed64 SO3 kernel; fallback is forbidden");
}

}  // namespace

std::array<
    bg_docking_fixed64_so3_row_v1,
    BG_DOCKING_FIXED64_SO3_ORIENTATION_COUNT>
reference_rows(const bg_docking_fixed64_so3_input_v1 &input) noexcept {
    return generate_cpp(input);
}

}  // namespace betelgeuze::native::docking::fixed64_so3

using namespace betelgeuze::native;

extern "C" BG_API bg_status BG_CALL
bg_docking_fixed64_so3_input_v1_init(
    bg_docking_fixed64_so3_input_v1 *input,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            input,
            caller_struct_size,
            sizeof(bg_docking_fixed64_so3_input_v1),
            caller_abi_version,
            "fixed64 SO3 input initializer pointer is null",
            "fixed64 SO3 input initializer size does not match",
            "fixed64 SO3 input initializer ABI version does not match");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *input = bg_docking_fixed64_so3_input_v1{};
        input->struct_size = static_cast<uint32_t>(sizeof(*input));
        input->abi_version = BG_ABI_VERSION;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL
bg_docking_fixed64_so3_output_v1_init(
    bg_docking_fixed64_so3_output_v1 *output,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            output,
            caller_struct_size,
            sizeof(bg_docking_fixed64_so3_output_v1),
            caller_abi_version,
            "fixed64 SO3 output initializer pointer is null",
            "fixed64 SO3 output initializer size does not match",
            "fixed64 SO3 output initializer ABI version does not match");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *output = bg_docking_fixed64_so3_output_v1{};
        output->struct_size = static_cast<uint32_t>(sizeof(*output));
        output->abi_version = BG_ABI_VERSION;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_docking_fixed64_so3_v1_generate(
    const bg_context *context,
    const bg_docking_fixed64_so3_input_v1 *input,
    bg_docking_fixed64_so3_output_v1 *output) BG_NOEXCEPT {
    using namespace betelgeuze::native::docking::fixed64_so3;
    return guarded_status([&]() -> bg_status {
        if (context == nullptr || input == nullptr || output == nullptr ||
            !pointer_is_aligned(context) || !pointer_is_aligned(input) ||
            !pointer_is_aligned(output)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 SO3 context, input, and output must be non-null and aligned");
        }
        bg_status status = validate_input(*input);
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = validate_output(*context, *input, *output);
        if (status != BG_STATUS_OK) {
            return status;
        }

        std::array<
            bg_docking_fixed64_so3_row_v1,
            BG_DOCKING_FIXED64_SO3_ORIENTATION_COUNT>
            rows{};
        status = generate_backend(*context, *input, &rows);
        if (status != BG_STATUS_OK) {
            return status;
        }
        if (!batch_shape_is_valid(*input, rows, context->backend)) {
            return fail(
                BG_STATUS_BACKEND_ERROR,
                "fixed64 SO3 backend returned invalid or duplicate orientations");
        }
        for (auto &row : rows) {
            const auto digest = row_receipt(*input, context->backend, row);
            std::copy(
                digest.begin(), digest.end(), row.row_receipt_sha256);
        }
        const auto receipt = batch_receipt(*input, context->backend, rows);

        std::memcpy(output->rows, rows.data(), sizeof(rows));
        output->row_count = rows.size();
        output->backend = context->backend;
        std::copy(
            receipt.begin(), receipt.end(), output->batch_receipt_sha256);
        output->result_dependent_input_consumed = UINT8_C(0);
        output->denominator_preserved = UINT8_C(1);
        output->molecular_execution_authorized = UINT8_C(0);
        output->reservation_authorized = UINT8_C(0);
        output->benchmark_execution_authorized = UINT8_C(0);
        output->production_claim_authorized = UINT8_C(0);
        return BG_STATUS_OK;
    });
}
