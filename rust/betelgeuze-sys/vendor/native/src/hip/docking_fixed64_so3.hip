#include <hip/hip_runtime.h>

#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <limits>

#if !defined(BG_DOCKING_FIXED64_SO3_GENERATE) || \
    !defined(BG_DOCKING_FIXED64_INDEXED_SO3_PLACE) || \
    !defined(BG_DOCKING_FIXED64_SO3_LANE)
#  error "native HIP fixed64 SO3 provider identity is not configured"
#endif

namespace {

constexpr size_t kHipSo3Count = BG_DOCKING_FIXED64_SO3_ORIENTATION_COUNT;
constexpr size_t kHipSo3MaximumAttempts = kHipSo3Count * 1024U;
constexpr double kHipSo3DuplicateTolerance = 1.0e-10;
constexpr double kHipSo3Epsilon = 1.0e-12;
constexpr double kHipSo3TwoPow64 = 18446744073709551616.0;
constexpr double kHipSo3MaximumCoordinateAngstrom = 100000.0;

struct HipSo3Seed final {
    uint8_t bytes[32];
};

struct HipSo3Quaternion final {
    double x;
    double y;
    double z;
    double w;
};

void fixed64_so3_clear_error(char *message, size_t capacity) noexcept {
    if (message != nullptr && capacity > 0) {
        message[0] = '\0';
    }
}

int32_t fixed64_so3_fail(
    int32_t status,
    char *message,
    size_t capacity,
    const char *detail) noexcept {
    if (message != nullptr && capacity > 0) {
        std::snprintf(message, capacity, "%s", detail == nullptr ? "" : detail);
        message[capacity - 1] = '\0';
    }
    return status;
}

int32_t fixed64_so3_fail_hip(
    hipError_t error,
    char *message,
    size_t capacity,
    const char *operation) noexcept {
    const int32_t status = error == hipErrorOutOfMemory
                               ? BG_STATUS_OUT_OF_MEMORY
                               : BG_STATUS_BACKEND_ERROR;
    if (message != nullptr && capacity > 0) {
        const char *const detail = hipGetErrorString(error);
        std::snprintf(
            message,
            capacity,
            "%s %s failed: %s",
            BG_DOCKING_FIXED64_SO3_LANE,
            operation,
            detail == nullptr ? "unknown HIP runtime error" : detail);
        message[capacity - 1] = '\0';
    }
    return status;
}

template <size_t Count>
bool fixed64_so3_reserved_is_zero(
    const uint64_t (&values)[Count]) noexcept {
    for (const uint64_t value : values) {
        if (value != UINT64_C(0)) {
            return false;
        }
    }
    return true;
}

bool fixed64_so3_digest_is_zero(const uint8_t (&value)[32]) noexcept {
    for (uint8_t byte : value) {
        if (byte != UINT8_C(0)) {
            return false;
        }
    }
    return true;
}

class Fixed64So3DeviceGuard final {
public:
    Fixed64So3DeviceGuard() noexcept {
        if (hipGetDevice(&previous_) == hipSuccess) {
            has_previous_ = true;
        }
    }

    Fixed64So3DeviceGuard(const Fixed64So3DeviceGuard &) = delete;
    Fixed64So3DeviceGuard &operator=(const Fixed64So3DeviceGuard &) = delete;

    ~Fixed64So3DeviceGuard() {
        if (has_previous_) {
            static_cast<void>(hipSetDevice(previous_));
        }
    }

private:
    int previous_ = 0;
    bool has_previous_ = false;
};

class Fixed64So3RowsBuffer final {
public:
    Fixed64So3RowsBuffer() = default;
    Fixed64So3RowsBuffer(const Fixed64So3RowsBuffer &) = delete;
    Fixed64So3RowsBuffer &operator=(const Fixed64So3RowsBuffer &) = delete;

    ~Fixed64So3RowsBuffer() {
        if (rows_ != nullptr) {
            static_cast<void>(hipFree(rows_));
        }
    }

    hipError_t allocate() noexcept {
        return hipMalloc(
            reinterpret_cast<void **>(&rows_),
            kHipSo3Count * sizeof(*rows_));
    }

    hipError_t copy_to(bg_docking_fixed64_so3_row_v1 *rows) const noexcept {
        return hipMemcpy(
            rows,
            rows_,
            kHipSo3Count * sizeof(*rows_),
            hipMemcpyDeviceToHost);
    }

    bg_docking_fixed64_so3_row_v1 *get() noexcept { return rows_; }

private:
    bg_docking_fixed64_so3_row_v1 *rows_ = nullptr;
};

template <typename Type>
class Fixed64So3DeviceBuffer final {
public:
    Fixed64So3DeviceBuffer() = default;
    Fixed64So3DeviceBuffer(const Fixed64So3DeviceBuffer &) = delete;
    Fixed64So3DeviceBuffer &operator=(const Fixed64So3DeviceBuffer &) = delete;

    ~Fixed64So3DeviceBuffer() {
        if (values_ != nullptr) {
            static_cast<void>(hipFree(values_));
        }
    }

    hipError_t allocate(size_t count) noexcept {
        if (count == 0 ||
            count > std::numeric_limits<size_t>::max() / sizeof(Type)) {
            return hipErrorInvalidValue;
        }
        return hipMalloc(
            reinterpret_cast<void **>(&values_), count * sizeof(Type));
    }

    hipError_t copy_from(const Type *values, size_t count) noexcept {
        return hipMemcpy(
            values_, values, count * sizeof(Type), hipMemcpyHostToDevice);
    }

    hipError_t copy_to(Type *values, size_t count) const noexcept {
        return hipMemcpy(
            values, values_, count * sizeof(Type), hipMemcpyDeviceToHost);
    }

    Type *get() noexcept { return values_; }
    const Type *get() const noexcept { return values_; }

private:
    Type *values_ = nullptr;
};

__device__ uint64_t fixed64_so3_read_u64_be(const uint8_t *bytes) {
    uint64_t value = 0;
    for (size_t index = 0; index < 8; ++index) {
        value = (value << 8U) | bytes[index];
    }
    return value;
}

__device__ double fixed64_so3_radical_inverse(
    uint64_t index,
    uint32_t base) {
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

__device__ HipSo3Quaternion fixed64_so3_canonicalize(
    HipSo3Quaternion value) {
    const double maximum = fmax(
        fmax(fabs(value.x), fabs(value.y)),
        fmax(fabs(value.z), fabs(value.w)));
    if (!isfinite(maximum) || maximum <= kHipSo3Epsilon) {
        return {0.0, 0.0, 0.0, 0.0};
    }
    const double scaled_x = value.x / maximum;
    const double scaled_y = value.y / maximum;
    const double scaled_z = value.z / maximum;
    const double scaled_w = value.w / maximum;
    const double scaled_norm = sqrt(
        scaled_x * scaled_x + scaled_y * scaled_y +
        scaled_z * scaled_z + scaled_w * scaled_w);
    const double norm = maximum * scaled_norm;
    const double inverse =
        isfinite(norm) && fabs(norm - 1.0) <= 1.0e-15
            ? 1.0
            : (1.0 / maximum) / scaled_norm;
    value.x *= inverse;
    value.y *= inverse;
    value.z *= inverse;
    value.w *= inverse;
    const double order[4] = {value.w, value.z, value.y, value.x};
    for (size_t index = 0; index < 4; ++index) {
        if (order[index] > 0.0) {
            break;
        }
        if (order[index] < 0.0) {
            value.x = -value.x;
            value.y = -value.y;
            value.z = -value.z;
            value.w = -value.w;
            break;
        }
    }
    value.x = value.x == 0.0 ? 0.0 : value.x;
    value.y = value.y == 0.0 ? 0.0 : value.y;
    value.z = value.z == 0.0 ? 0.0 : value.z;
    value.w = value.w == 0.0 ? 0.0 : value.w;
    return value;
}

__device__ HipSo3Quaternion fixed64_so3_quaternion(
    uint64_t raw_index,
    const double (&offsets)[3]) {
    const uint32_t bases[3] = {2, 3, 5};
    double unit[3]{};
    for (size_t index = 0; index < 3; ++index) {
        const double shifted =
            fixed64_so3_radical_inverse(raw_index, bases[index]) +
            offsets[index];
        unit[index] = shifted - floor(shifted);
    }
    const double first_radius = sqrt(fmax(0.0, 1.0 - unit[0]));
    const double second_radius = sqrt(fmax(0.0, unit[0]));
    const double pi = acos(-1.0);
    const double first_angle = 2.0 * pi * unit[1];
    const double second_angle = 2.0 * pi * unit[2];
    return fixed64_so3_canonicalize({
        first_radius * sin(first_angle),
        first_radius * cos(first_angle),
        second_radius * sin(second_angle),
        second_radius * cos(second_angle),
    });
}

__device__ double fixed64_so3_geodesic_distance(
    HipSo3Quaternion left,
    HipSo3Quaternion right) {
    const double dot = left.x * right.x + left.y * right.y +
                       left.z * right.z + left.w * right.w;
    const double sign = dot < 0.0 ? -1.0 : 1.0;
    const double dx = left.x - sign * right.x;
    const double dy = left.y - sign * right.y;
    const double dz = left.z - sign * right.z;
    const double dw = left.w - sign * right.w;
    const double sx = left.x + sign * right.x;
    const double sy = left.y + sign * right.y;
    const double sz = left.z + sign * right.z;
    const double sw = left.w + sign * right.w;
    const double difference = sqrt(dx * dx + dy * dy + dz * dz + dw * dw);
    const double sum = sqrt(sx * sx + sy * sy + sz * sz + sw * sw);
    if (difference <= kHipSo3Epsilon && sum <= kHipSo3Epsilon) {
        return 0.0;
    }
    return 4.0 * atan2(difference, sum);
}

__global__ void fixed64_so3_kernel(
    HipSo3Seed seed,
    bg_docking_fixed64_so3_row_v1 *rows) {
    if (blockIdx.x != 0 || threadIdx.x != 0) {
        return;
    }
    double offsets[3] = {
        static_cast<double>(fixed64_so3_read_u64_be(seed.bytes)) /
            kHipSo3TwoPow64,
        static_cast<double>(fixed64_so3_read_u64_be(seed.bytes + 8)) /
            kHipSo3TwoPow64,
        static_cast<double>(fixed64_so3_read_u64_be(seed.bytes + 16)) /
            kHipSo3TwoPow64,
    };
    HipSo3Quaternion accepted[kHipSo3Count]{};
    size_t accepted_count = 0;
    for (size_t raw = 0;
         raw < kHipSo3MaximumAttempts && accepted_count < kHipSo3Count;
         ++raw) {
        const HipSo3Quaternion quaternion = fixed64_so3_quaternion(
            static_cast<uint64_t>(raw), offsets);
        if (!isfinite(quaternion.x) || !isfinite(quaternion.y) ||
            !isfinite(quaternion.z) || !isfinite(quaternion.w)) {
            continue;
        }
        bool duplicate = false;
        for (size_t previous = 0; previous < accepted_count; ++previous) {
            if (fixed64_so3_geodesic_distance(
                    quaternion, accepted[previous]) <=
                kHipSo3DuplicateTolerance) {
                duplicate = true;
            }
        }
        if (duplicate) {
            continue;
        }
        accepted[accepted_count] = quaternion;
        bg_docking_fixed64_so3_row_v1 row{};
        row.orientation_index = static_cast<uint32_t>(accepted_count);
        row.status = BG_DOCKING_FIXED64_SO3_ROW_GENERATED;
        row.failure_code = BG_DOCKING_FIXED64_SO3_FAILURE_NONE;
        row.raw_sequence_index = static_cast<uint64_t>(raw);
        row.quaternion_x = quaternion.x;
        row.quaternion_y = quaternion.y;
        row.quaternion_z = quaternion.z;
        row.quaternion_w = quaternion.w;
        const double norm = sqrt(
            quaternion.x * quaternion.x + quaternion.y * quaternion.y +
            quaternion.z * quaternion.z + quaternion.w * quaternion.w);
        row.norm_error = fabs(norm - 1.0);
        row.denominator_preserved = UINT8_C(1);
        rows[accepted_count] = row;
        ++accepted_count;
    }
    for (size_t index = accepted_count; index < kHipSo3Count; ++index) {
        bg_docking_fixed64_so3_row_v1 row{};
        row.orientation_index = static_cast<uint32_t>(index);
        row.status = BG_DOCKING_FIXED64_SO3_ROW_TYPED_FAILURE;
        row.failure_code = BG_DOCKING_FIXED64_SO3_FAILURE_SEQUENCE_EXHAUSTED;
        row.denominator_preserved = UINT8_C(1);
        rows[index] = row;
    }
}

__device__ bool fixed64_so3_select_orientation(
    HipSo3Seed seed,
    uint32_t sequence_index,
    HipSo3Quaternion *selected,
    uint64_t *selected_raw_index) {
    double offsets[3] = {
        static_cast<double>(fixed64_so3_read_u64_be(seed.bytes)) /
            kHipSo3TwoPow64,
        static_cast<double>(fixed64_so3_read_u64_be(seed.bytes + 8)) /
            kHipSo3TwoPow64,
        static_cast<double>(fixed64_so3_read_u64_be(seed.bytes + 16)) /
            kHipSo3TwoPow64,
    };
    HipSo3Quaternion accepted[kHipSo3Count]{};
    size_t accepted_count = 0;
    for (size_t raw = 0; raw < kHipSo3MaximumAttempts; ++raw) {
        const HipSo3Quaternion quaternion = fixed64_so3_quaternion(
            static_cast<uint64_t>(raw), offsets);
        if (!isfinite(quaternion.x) || !isfinite(quaternion.y) ||
            !isfinite(quaternion.z) || !isfinite(quaternion.w)) {
            continue;
        }
        bool duplicate = false;
        for (size_t previous = 0; previous < accepted_count; ++previous) {
            if (fixed64_so3_geodesic_distance(
                    quaternion, accepted[previous]) <=
                kHipSo3DuplicateTolerance) {
                duplicate = true;
            }
        }
        if (duplicate) {
            continue;
        }
        accepted[accepted_count] = quaternion;
        if (accepted_count == static_cast<size_t>(sequence_index)) {
            *selected = quaternion;
            *selected_raw_index = static_cast<uint64_t>(raw);
            return true;
        }
        ++accepted_count;
        if (accepted_count >= kHipSo3Count) {
            break;
        }
    }
    return false;
}

__global__ void fixed64_indexed_so3_kernel(
    HipSo3Seed seed,
    uint32_t sequence_index,
    size_t ligand_atom_count,
    const double *source_x,
    const double *source_y,
    const double *source_z,
    double pocket_center_x,
    double pocket_center_y,
    double pocket_center_z,
    double *out_x,
    double *out_y,
    double *out_z,
    bg_native_fixed64_indexed_so3_kernel_result_v1 *out_result) {
    if (blockIdx.x != 0 || threadIdx.x != 0) {
        return;
    }
    bg_native_fixed64_indexed_so3_kernel_result_v1 result{};
    result.accepted_sequence_index = sequence_index;
    double centroid_x = 0.0;
    double centroid_y = 0.0;
    double centroid_z = 0.0;
    for (size_t atom = 0; atom < ligand_atom_count; ++atom) {
        centroid_x += source_x[atom];
        centroid_y += source_y[atom];
        centroid_z += source_z[atom];
    }
    const double inverse = 1.0 / static_cast<double>(ligand_atom_count);
    centroid_x *= inverse;
    centroid_y *= inverse;
    centroid_z *= inverse;
    result.source_centroid_angstrom[0] = centroid_x;
    result.source_centroid_angstrom[1] = centroid_y;
    result.source_centroid_angstrom[2] = centroid_z;

    bool distinct = false;
    for (size_t atom = 1; atom < ligand_atom_count; ++atom) {
        const double dx = source_x[atom] - source_x[0];
        const double dy = source_y[atom] - source_y[0];
        const double dz = source_z[atom] - source_z[0];
        if (dx * dx + dy * dy + dz * dz > kHipSo3Epsilon) {
            distinct = true;
        }
    }
    if (!distinct) {
        result.status = BG_DOCKING_FIXED64_INDEXED_SO3_TYPED_FAILURE;
        result.failure_code =
            BG_DOCKING_FIXED64_INDEXED_SO3_FAILURE_DEGENERATE_SOURCE_GEOMETRY;
        *out_result = result;
        return;
    }

    HipSo3Quaternion quaternion{};
    uint64_t raw_sequence_index = 0;
    if (!fixed64_so3_select_orientation(
            seed, sequence_index, &quaternion, &raw_sequence_index)) {
        result.status = BG_DOCKING_FIXED64_INDEXED_SO3_TYPED_FAILURE;
        result.failure_code =
            BG_DOCKING_FIXED64_INDEXED_SO3_FAILURE_NONFINITE_OUTPUT;
        *out_result = result;
        return;
    }
    result.raw_sequence_index = raw_sequence_index;
    result.quaternion_x = quaternion.x;
    result.quaternion_y = quaternion.y;
    result.quaternion_z = quaternion.z;
    result.quaternion_w = quaternion.w;

    const double twice_cross_x =
        2.0 * (quaternion.y * centroid_z - quaternion.z * centroid_y);
    const double twice_cross_y =
        2.0 * (quaternion.z * centroid_x - quaternion.x * centroid_z);
    const double twice_cross_z =
        2.0 * (quaternion.x * centroid_y - quaternion.y * centroid_x);
    const double rotated_centroid_x =
        centroid_x + quaternion.w * twice_cross_x +
        quaternion.y * twice_cross_z - quaternion.z * twice_cross_y;
    const double rotated_centroid_y =
        centroid_y + quaternion.w * twice_cross_y +
        quaternion.z * twice_cross_x - quaternion.x * twice_cross_z;
    const double rotated_centroid_z =
        centroid_z + quaternion.w * twice_cross_z +
        quaternion.x * twice_cross_y - quaternion.y * twice_cross_x;
    const double translation_x = pocket_center_x - rotated_centroid_x;
    const double translation_y = pocket_center_y - rotated_centroid_y;
    const double translation_z = pocket_center_z - rotated_centroid_z;
    result.translation_angstrom[0] = translation_x;
    result.translation_angstrom[1] = translation_y;
    result.translation_angstrom[2] = translation_z;

    for (size_t atom = 0; atom < ligand_atom_count; ++atom) {
        const double x = source_x[atom];
        const double y = source_y[atom];
        const double z = source_z[atom];
        const double cross_x =
            2.0 * (quaternion.y * z - quaternion.z * y);
        const double cross_y =
            2.0 * (quaternion.z * x - quaternion.x * z);
        const double cross_z =
            2.0 * (quaternion.x * y - quaternion.y * x);
        const double placed_x =
            x + quaternion.w * cross_x +
            quaternion.y * cross_z - quaternion.z * cross_y +
            translation_x;
        const double placed_y =
            y + quaternion.w * cross_y +
            quaternion.z * cross_x - quaternion.x * cross_z +
            translation_y;
        const double placed_z =
            z + quaternion.w * cross_z +
            quaternion.x * cross_y - quaternion.y * cross_x +
            translation_z;
        if (!isfinite(placed_x) || !isfinite(placed_y) ||
            !isfinite(placed_z) ||
            fabs(placed_x) > kHipSo3MaximumCoordinateAngstrom ||
            fabs(placed_y) > kHipSo3MaximumCoordinateAngstrom ||
            fabs(placed_z) > kHipSo3MaximumCoordinateAngstrom) {
            result.status = BG_DOCKING_FIXED64_INDEXED_SO3_TYPED_FAILURE;
            result.failure_code =
                BG_DOCKING_FIXED64_INDEXED_SO3_FAILURE_NONFINITE_OUTPUT;
            *out_result = result;
            return;
        }
        out_x[atom] = placed_x;
        out_y[atom] = placed_y;
        out_z[atom] = placed_z;
    }
    result.status = BG_DOCKING_FIXED64_INDEXED_SO3_PLACED;
    result.failure_code = BG_DOCKING_FIXED64_INDEXED_SO3_FAILURE_NONE;
    result.coordinates_written = UINT8_C(1);
    *out_result = result;
}

}  // namespace

extern "C" int32_t BG_DOCKING_FIXED64_SO3_GENERATE(
    int32_t device_ordinal,
    const bg_docking_fixed64_so3_input_v1 *input,
    bg_docking_fixed64_so3_row_v1 *out_rows,
    char *error_message,
    size_t error_capacity) {
    fixed64_so3_clear_error(error_message, error_capacity);
    if (device_ordinal < 0 || input == nullptr || out_rows == nullptr ||
        reinterpret_cast<uintptr_t>(input) %
                alignof(bg_docking_fixed64_so3_input_v1) !=
            0 ||
        reinterpret_cast<uintptr_t>(out_rows) %
                alignof(bg_docking_fixed64_so3_row_v1) !=
            0) {
        return fixed64_so3_fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            BG_DOCKING_FIXED64_SO3_LANE
            " fixed64 SO3 arguments are invalid");
    }
    if (input->struct_size != sizeof(*input) ||
        input->abi_version != BG_ABI_VERSION ||
        fixed64_so3_digest_is_zero(input->source_seed_sha256) ||
        !fixed64_so3_reserved_is_zero(input->reserved)) {
        return fixed64_so3_fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            BG_DOCKING_FIXED64_SO3_LANE
            " fixed64 SO3 input identity is invalid");
    }

    Fixed64So3DeviceGuard guard;
    hipError_t status = hipSetDevice(device_ordinal);
    if (status != hipSuccess) {
        return fixed64_so3_fail_hip(
            status,
            error_message,
            error_capacity,
            "fixed64 SO3 device selection");
    }
    Fixed64So3RowsBuffer device_rows;
    status = device_rows.allocate();
    if (status != hipSuccess) {
        return fixed64_so3_fail_hip(
            status,
            error_message,
            error_capacity,
            "fixed64 SO3 output allocation");
    }
    HipSo3Seed seed{};
    std::memcpy(seed.bytes, input->source_seed_sha256, sizeof(seed.bytes));
    hipLaunchKernelGGL(
        fixed64_so3_kernel,
        dim3(1),
        dim3(1),
        0,
        0,
        seed,
        device_rows.get());
    hipError_t execution_status = hipGetLastError();
    if (execution_status == hipSuccess) {
        execution_status = hipDeviceSynchronize();
    }
    if (execution_status != hipSuccess) {
        return fixed64_so3_fail_hip(
            execution_status,
            error_message,
            error_capacity,
            "fixed64 SO3 kernel execution");
    }
    status = device_rows.copy_to(out_rows);
    if (status != hipSuccess) {
        return fixed64_so3_fail_hip(
            status,
            error_message,
            error_capacity,
            "fixed64 SO3 result copy");
    }
    return BG_STATUS_OK;
}

extern "C" int32_t BG_DOCKING_FIXED64_INDEXED_SO3_PLACE(
    int32_t device_ordinal,
    const bg_native_fixed64_indexed_so3_kernel_input_v1 *input,
    double *out_x_angstrom,
    double *out_y_angstrom,
    double *out_z_angstrom,
    bg_native_fixed64_indexed_so3_kernel_result_v1 *out_result,
    char *error_message,
    size_t error_capacity) {
    fixed64_so3_clear_error(error_message, error_capacity);
    if (device_ordinal < 0 || input == nullptr || out_x_angstrom == nullptr ||
        out_y_angstrom == nullptr || out_z_angstrom == nullptr ||
        out_result == nullptr ||
        reinterpret_cast<uintptr_t>(input) %
                alignof(bg_native_fixed64_indexed_so3_kernel_input_v1) !=
            0 ||
        reinterpret_cast<uintptr_t>(out_x_angstrom) % alignof(double) != 0 ||
        reinterpret_cast<uintptr_t>(out_y_angstrom) % alignof(double) != 0 ||
        reinterpret_cast<uintptr_t>(out_z_angstrom) % alignof(double) != 0 ||
        reinterpret_cast<uintptr_t>(out_result) %
                alignof(bg_native_fixed64_indexed_so3_kernel_result_v1) !=
            0) {
        return fixed64_so3_fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            BG_DOCKING_FIXED64_SO3_LANE
            " indexed SO3 arguments are invalid");
    }
    const size_t count = static_cast<size_t>(input->ligand_atom_count);
    if (input->struct_size != sizeof(*input) ||
        input->abi_version != UINT32_C(1) ||
        count < 2 || count > 512 || input->sequence_index >= kHipSo3Count ||
        input->reserved0 != 0 ||
        !fixed64_so3_reserved_is_zero(input->reserved)) {
        return fixed64_so3_fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            BG_DOCKING_FIXED64_SO3_LANE
            " indexed SO3 input identity is invalid");
    }
    for (size_t axis = 0; axis < 3; ++axis) {
        if (!std::isfinite(input->pocket_center_angstrom[axis]) ||
            std::abs(input->pocket_center_angstrom[axis]) >
                kHipSo3MaximumCoordinateAngstrom) {
            return fixed64_so3_fail(
                BG_STATUS_INVALID_ARGUMENT,
                error_message,
                error_capacity,
                BG_DOCKING_FIXED64_SO3_LANE
                " indexed SO3 pocket center is invalid");
        }
    }
    const double *const source_channels[3] = {
        input->source_x_angstrom,
        input->source_y_angstrom,
        input->source_z_angstrom};
    for (const double *channel : source_channels) {
        if (channel == nullptr ||
            reinterpret_cast<uintptr_t>(channel) % alignof(double) != 0) {
            return fixed64_so3_fail(
                BG_STATUS_INVALID_ARGUMENT,
                error_message,
                error_capacity,
                BG_DOCKING_FIXED64_SO3_LANE
                " indexed SO3 source channel is invalid");
        }
        for (size_t atom = 0; atom < count; ++atom) {
            if (!std::isfinite(channel[atom]) ||
                std::abs(channel[atom]) > kHipSo3MaximumCoordinateAngstrom) {
                return fixed64_so3_fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    error_message,
                    error_capacity,
                    BG_DOCKING_FIXED64_SO3_LANE
                    " indexed SO3 source coordinate is invalid");
            }
        }
    }

    Fixed64So3DeviceGuard guard;
    hipError_t status = hipSetDevice(device_ordinal);
    if (status != hipSuccess) {
        return fixed64_so3_fail_hip(
            status, error_message, error_capacity,
            "indexed SO3 device selection");
    }
    Fixed64So3DeviceBuffer<double> source_x;
    Fixed64So3DeviceBuffer<double> source_y;
    Fixed64So3DeviceBuffer<double> source_z;
    Fixed64So3DeviceBuffer<double> output_x;
    Fixed64So3DeviceBuffer<double> output_y;
    Fixed64So3DeviceBuffer<double> output_z;
    Fixed64So3DeviceBuffer<bg_native_fixed64_indexed_so3_kernel_result_v1>
        result_buffer;
    Fixed64So3DeviceBuffer<double> *const coordinate_buffers[6] = {
        &source_x, &source_y, &source_z, &output_x, &output_y, &output_z};
    for (auto *buffer : coordinate_buffers) {
        status = buffer->allocate(count);
        if (status != hipSuccess) {
            return fixed64_so3_fail_hip(
                status, error_message, error_capacity,
                "indexed SO3 coordinate allocation");
        }
    }
    status = result_buffer.allocate(1);
    if (status == hipSuccess) {
        status = source_x.copy_from(input->source_x_angstrom, count);
    }
    if (status == hipSuccess) {
        status = source_y.copy_from(input->source_y_angstrom, count);
    }
    if (status == hipSuccess) {
        status = source_z.copy_from(input->source_z_angstrom, count);
    }
    if (status != hipSuccess) {
        return fixed64_so3_fail_hip(
            status, error_message, error_capacity,
            "indexed SO3 input transfer");
    }
    HipSo3Seed seed{};
    std::memcpy(seed.bytes, input->source_seed_sha256, sizeof(seed.bytes));
    hipLaunchKernelGGL(
        fixed64_indexed_so3_kernel,
        dim3(1),
        dim3(1),
        0,
        0,
        seed,
        input->sequence_index,
        count,
        source_x.get(),
        source_y.get(),
        source_z.get(),
        input->pocket_center_angstrom[0],
        input->pocket_center_angstrom[1],
        input->pocket_center_angstrom[2],
        output_x.get(),
        output_y.get(),
        output_z.get(),
        result_buffer.get());
    status = hipGetLastError();
    if (status == hipSuccess) {
        status = hipDeviceSynchronize();
    }
    bg_native_fixed64_indexed_so3_kernel_result_v1 local_result{};
    if (status == hipSuccess) {
        status = result_buffer.copy_to(&local_result, 1);
    }
    if (status == hipSuccess && local_result.coordinates_written != UINT8_C(0)) {
        status = output_x.copy_to(out_x_angstrom, count);
        if (status == hipSuccess) {
            status = output_y.copy_to(out_y_angstrom, count);
        }
        if (status == hipSuccess) {
            status = output_z.copy_to(out_z_angstrom, count);
        }
    }
    if (status != hipSuccess) {
        return fixed64_so3_fail_hip(
            status, error_message, error_capacity,
            "indexed SO3 kernel or result transfer");
    }
    *out_result = local_result;
    return BG_STATUS_OK;
}
