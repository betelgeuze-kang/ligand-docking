#include <hip/hip_runtime.h>

#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <limits>

#if !defined(BG_DOCKING_FIXED64_SINGLE_ANCHOR_PLACE) || \
    !defined(BG_DOCKING_FIXED64_SINGLE_ANCHOR_LANE)
#  error "native HIP fixed64 single-anchor provider identity is not configured"
#endif

namespace {

constexpr size_t kHipAnchorMaximumLigandAtoms = 512;
constexpr size_t kHipAnchorMaximumFeatureAtoms = 65536;
constexpr double kHipAnchorMaximumCoordinateAngstrom = 100000.0;
constexpr double kHipAnchorEpsilon = 1.0e-12;
constexpr double kHipAnchorPi = 3.141592653589793238462643383279502884;

struct HipAnchorVec3 final {
    double x;
    double y;
    double z;
};

struct HipAnchorQuaternion final {
    double x;
    double y;
    double z;
    double w;
};

template <typename Type>
class Fixed64AnchorDeviceBuffer final {
public:
    Fixed64AnchorDeviceBuffer() = default;
    Fixed64AnchorDeviceBuffer(const Fixed64AnchorDeviceBuffer &) = delete;
    Fixed64AnchorDeviceBuffer &operator=(const Fixed64AnchorDeviceBuffer &) = delete;
    ~Fixed64AnchorDeviceBuffer() {
        if (values_ != nullptr) static_cast<void>(hipFree(values_));
    }
    hipError_t allocate(size_t count) noexcept {
        if (count == 0 || count > std::numeric_limits<size_t>::max() / sizeof(Type)) {
            return hipErrorInvalidValue;
        }
        return hipMalloc(reinterpret_cast<void **>(&values_), count * sizeof(Type));
    }
    hipError_t copy_from(const Type *values, size_t count) noexcept {
        return hipMemcpy(values_, values, count * sizeof(Type), hipMemcpyHostToDevice);
    }
    hipError_t copy_to(Type *values, size_t count) const noexcept {
        return hipMemcpy(values, values_, count * sizeof(Type), hipMemcpyDeviceToHost);
    }
    Type *get() noexcept { return values_; }
private:
    Type *values_ = nullptr;
};

void fixed64_anchor_clear_error(char *message, size_t capacity) noexcept {
    if (message != nullptr && capacity > 0) message[0] = '\0';
}

int32_t fixed64_anchor_fail(
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

int32_t fixed64_anchor_fail_hip(
    hipError_t error,
    char *message,
    size_t capacity,
    const char *operation) noexcept {
    const int32_t status = error == hipErrorOutOfMemory
        ? BG_STATUS_OUT_OF_MEMORY
        : BG_STATUS_BACKEND_ERROR;
    if (message != nullptr && capacity > 0) {
        const char *detail = hipGetErrorString(error);
        std::snprintf(
            message,
            capacity,
            "%s %s failed: %s",
            BG_DOCKING_FIXED64_SINGLE_ANCHOR_LANE,
            operation,
            detail == nullptr ? "unknown HIP runtime error" : detail);
        message[capacity - 1] = '\0';
    }
    return status;
}

template <size_t Count>
bool fixed64_anchor_reserved_is_zero(const uint64_t (&values)[Count]) noexcept {
    for (uint64_t value : values) {
        if (value != UINT64_C(0)) return false;
    }
    return true;
}

__device__ HipAnchorVec3 anchor_plus(HipAnchorVec3 left, HipAnchorVec3 right) {
    return {left.x + right.x, left.y + right.y, left.z + right.z};
}

__device__ HipAnchorVec3 anchor_minus(HipAnchorVec3 left, HipAnchorVec3 right) {
    return {left.x - right.x, left.y - right.y, left.z - right.z};
}

__device__ HipAnchorVec3 anchor_scale(HipAnchorVec3 value, double factor) {
    return {value.x * factor, value.y * factor, value.z * factor};
}

__device__ double anchor_dot(HipAnchorVec3 left, HipAnchorVec3 right) {
    return left.x * right.x + left.y * right.y + left.z * right.z;
}

__device__ HipAnchorVec3 anchor_cross(HipAnchorVec3 left, HipAnchorVec3 right) {
    return {
        left.y * right.z - left.z * right.y,
        left.z * right.x - left.x * right.z,
        left.x * right.y - left.y * right.x,
    };
}

__device__ double anchor_norm(HipAnchorVec3 value) {
    return sqrt(value.x * value.x + value.y * value.y + value.z * value.z);
}

__device__ bool anchor_normalize(HipAnchorVec3 value, HipAnchorVec3 *output) {
    const double maximum = fmax(fmax(fabs(value.x), fabs(value.y)), fabs(value.z));
    if (!isfinite(maximum) || maximum <= kHipAnchorEpsilon) return false;
    HipAnchorVec3 scaled = anchor_scale(value, 1.0 / maximum);
    const double length = anchor_norm(scaled);
    if (!isfinite(length) || length <= 0.0) return false;
    *output = anchor_scale(scaled, 1.0 / length);
    return true;
}

__device__ HipAnchorVec3 anchor_canonical_direction(HipAnchorVec3 value) {
    const double components[3] = {value.x, value.y, value.z};
    for (size_t index = 0; index < 3; ++index) {
        if (fabs(components[index]) <= kHipAnchorEpsilon) continue;
        if (components[index] < 0.0) value = anchor_scale(value, -1.0);
        break;
    }
    value.x = value.x == 0.0 ? 0.0 : value.x;
    value.y = value.y == 0.0 ? 0.0 : value.y;
    value.z = value.z == 0.0 ? 0.0 : value.z;
    return value;
}

__device__ HipAnchorQuaternion anchor_canonicalize(
    HipAnchorQuaternion value,
    bool *ok) {
    const double maximum = fmax(
        fmax(fabs(value.x), fabs(value.y)),
        fmax(fabs(value.z), fabs(value.w)));
    if (!isfinite(maximum) || maximum <= kHipAnchorEpsilon) {
        *ok = false;
        return {0.0, 0.0, 0.0, 1.0};
    }
    const double sx = value.x / maximum;
    const double sy = value.y / maximum;
    const double sz = value.z / maximum;
    const double sw = value.w / maximum;
    const double length = sqrt(sx * sx + sy * sy + sz * sz + sw * sw);
    const double inverse = (1.0 / maximum) / length;
    value = {
        value.x * inverse,
        value.y * inverse,
        value.z * inverse,
        value.w * inverse,
    };
    const double order[4] = {value.w, value.z, value.y, value.x};
    for (size_t index = 0; index < 4; ++index) {
        if (order[index] > 0.0) break;
        if (order[index] < 0.0) {
            value = {-value.x, -value.y, -value.z, -value.w};
            break;
        }
    }
    value.x = value.x == 0.0 ? 0.0 : value.x;
    value.y = value.y == 0.0 ? 0.0 : value.y;
    value.z = value.z == 0.0 ? 0.0 : value.z;
    value.w = value.w == 0.0 ? 0.0 : value.w;
    *ok = true;
    return value;
}

__device__ HipAnchorQuaternion anchor_between(
    HipAnchorVec3 source,
    HipAnchorVec3 target,
    bool *ok) {
    if (!anchor_normalize(source, &source) || !anchor_normalize(target, &target)) {
        *ok = false;
        return {0.0, 0.0, 0.0, 1.0};
    }
    const double cosine = fmax(-1.0, fmin(1.0, anchor_dot(source, target)));
    if (cosine >= 1.0 - 1.0e-12) {
        *ok = true;
        return {0.0, 0.0, 0.0, 1.0};
    }
    if (cosine <= -1.0 + 1.0e-12) {
        HipAnchorVec3 reference{1.0, 0.0, 0.0};
        if (fabs(anchor_dot(source, reference)) > 0.9) {
            reference = {0.0, 1.0, 0.0};
        }
        HipAnchorVec3 axis{};
        if (!anchor_normalize(anchor_cross(source, reference), &axis)) {
            *ok = false;
            return {0.0, 0.0, 0.0, 1.0};
        }
        return anchor_canonicalize({axis.x, axis.y, axis.z, 0.0}, ok);
    }
    const HipAnchorVec3 axis = anchor_cross(source, target);
    return anchor_canonicalize(
        {axis.x, axis.y, axis.z, 1.0 + cosine}, ok);
}

__device__ HipAnchorQuaternion anchor_rotation_about(
    HipAnchorVec3 axis,
    double angle,
    bool *ok) {
    if (fabs(angle) <= kHipAnchorEpsilon) {
        *ok = true;
        return {0.0, 0.0, 0.0, 1.0};
    }
    if (!anchor_normalize(axis, &axis)) {
        *ok = false;
        return {0.0, 0.0, 0.0, 1.0};
    }
    const double half = 0.5 * angle;
    const double sine = sin(half);
    return anchor_canonicalize(
        {axis.x * sine, axis.y * sine, axis.z * sine, cos(half)}, ok);
}

__device__ HipAnchorQuaternion anchor_multiply(
    HipAnchorQuaternion left,
    HipAnchorQuaternion right,
    bool *ok) {
    return anchor_canonicalize(
        {left.w * right.x + left.x * right.w + left.y * right.z - left.z * right.y,
         left.w * right.y - left.x * right.z + left.y * right.w + left.z * right.x,
         left.w * right.z + left.x * right.y - left.y * right.x + left.z * right.w,
         left.w * right.w - left.x * right.x - left.y * right.y - left.z * right.z},
        ok);
}

__device__ HipAnchorVec3 anchor_rotate(
    HipAnchorQuaternion quaternion,
    HipAnchorVec3 vector) {
    const HipAnchorVec3 q{quaternion.x, quaternion.y, quaternion.z};
    const HipAnchorVec3 twice_cross = anchor_scale(anchor_cross(q, vector), 2.0);
    return anchor_plus(
        anchor_plus(vector, anchor_scale(twice_cross, quaternion.w)),
        anchor_cross(q, twice_cross));
}

__device__ HipAnchorVec3 anchor_centroid(
    const double *x,
    const double *y,
    const double *z,
    size_t count) {
    HipAnchorVec3 value{};
    for (size_t index = 0; index < count; ++index) {
        value.x += x[index];
        value.y += y[index];
        value.z += z[index];
    }
    return anchor_scale(value, 1.0 / static_cast<double>(count));
}

__device__ bool anchor_aromatic_normal(
    const double *x,
    const double *y,
    const double *z,
    size_t count,
    HipAnchorVec3 *output) {
    for (size_t first = 0; first < count; ++first) {
        const HipAnchorVec3 first_point{x[first], y[first], z[first]};
        for (size_t second = first + 1; second < count; ++second) {
            const HipAnchorVec3 second_point{x[second], y[second], z[second]};
            for (size_t third = second + 1; third < count; ++third) {
                const HipAnchorVec3 third_point{x[third], y[third], z[third]};
                HipAnchorVec3 normal = anchor_cross(
                    anchor_minus(second_point, first_point),
                    anchor_minus(third_point, first_point));
                if (anchor_norm(normal) > kHipAnchorEpsilon &&
                    anchor_normalize(normal, &normal)) {
                    *output = anchor_canonical_direction(normal);
                    return true;
                }
            }
        }
    }
    return false;
}

__device__ bool anchor_principal_axis(
    const double *x,
    const double *y,
    const double *z,
    size_t count,
    HipAnchorVec3 *output) {
    const HipAnchorVec3 center = anchor_centroid(x, y, z, count);
    double covariance[3][3]{};
    for (size_t point = 0; point < count; ++point) {
        const double components[3] = {
            x[point] - center.x,
            y[point] - center.y,
            z[point] - center.z,
        };
        for (size_t left = 0; left < 3; ++left) {
            for (size_t right = 0; right < 3; ++right) {
                covariance[left][right] += components[left] * components[right];
            }
        }
    }
    const double variance = fmax(covariance[0][0], fmax(covariance[1][1], covariance[2][2]));
    if (!isfinite(variance) || variance <= kHipAnchorEpsilon) return false;
    double matrix[3][3]{};
    double eigenvectors[3][3]{};
    for (size_t row = 0; row < 3; ++row) {
        for (size_t column = 0; column < 3; ++column) {
            matrix[row][column] = covariance[row][column];
        }
        eigenvectors[row][row] = 1.0;
    }
    const size_t pair_first[3] = {0, 0, 1};
    const size_t pair_second[3] = {1, 2, 2};
    for (size_t rotation_index = 0; rotation_index < 64; ++rotation_index) {
        size_t selected = 0;
        double selected_value = fabs(matrix[0][1]);
        for (size_t pair = 1; pair < 3; ++pair) {
            const double value = fabs(matrix[pair_first[pair]][pair_second[pair]]);
            if (value > selected_value) {
                selected = pair;
                selected_value = value;
            }
        }
        const double scale_value = fmax(
            fabs(matrix[0][0]),
            fmax(fabs(matrix[1][1]), fabs(matrix[2][2])));
        if (selected_value <= kHipAnchorEpsilon * scale_value) break;
        const size_t first = pair_first[selected];
        const size_t second = pair_second[selected];
        const double angle = 0.5 * atan2(
            2.0 * matrix[first][second],
            matrix[second][second] - matrix[first][first]);
        const double cosine = cos(angle);
        const double sine = sin(angle);
        double rotation[3][3]{};
        for (size_t index = 0; index < 3; ++index) rotation[index][index] = 1.0;
        rotation[first][first] = cosine;
        rotation[second][second] = cosine;
        rotation[first][second] = sine;
        rotation[second][first] = -sine;
        double right_product[3][3]{};
        for (size_t row = 0; row < 3; ++row) {
            for (size_t column = 0; column < 3; ++column) {
                for (size_t inner = 0; inner < 3; ++inner) {
                    right_product[row][column] += matrix[row][inner] * rotation[inner][column];
                }
            }
        }
        double next_matrix[3][3]{};
        for (size_t row = 0; row < 3; ++row) {
            for (size_t column = 0; column < 3; ++column) {
                for (size_t inner = 0; inner < 3; ++inner) {
                    next_matrix[row][column] += rotation[inner][row] * right_product[inner][column];
                }
            }
        }
        for (size_t row = 0; row < 3; ++row) {
            for (size_t column = 0; column < 3; ++column) matrix[row][column] = next_matrix[row][column];
        }
        double next_eigenvectors[3][3]{};
        for (size_t row = 0; row < 3; ++row) {
            for (size_t column = 0; column < 3; ++column) {
                for (size_t inner = 0; inner < 3; ++inner) {
                    next_eigenvectors[row][column] += eigenvectors[row][inner] * rotation[inner][column];
                }
            }
        }
        for (size_t row = 0; row < 3; ++row) {
            for (size_t column = 0; column < 3; ++column) eigenvectors[row][column] = next_eigenvectors[row][column];
        }
    }
    size_t dominant = 0;
    for (size_t index = 1; index < 3; ++index) {
        if (matrix[index][index] > matrix[dominant][dominant]) dominant = index;
    }
    HipAnchorVec3 vector{
        eigenvectors[0][dominant], eigenvectors[1][dominant], eigenvectors[2][dominant]};
    if (!anchor_normalize(vector, &vector)) return false;
    const HipAnchorVec3 transformed{
        covariance[0][0] * vector.x + covariance[0][1] * vector.y + covariance[0][2] * vector.z,
        covariance[1][0] * vector.x + covariance[1][1] * vector.y + covariance[1][2] * vector.z,
        covariance[2][0] * vector.x + covariance[2][1] * vector.y + covariance[2][2] * vector.z};
    const double rayleigh = anchor_dot(vector, transformed);
    const double residual = anchor_norm(anchor_minus(transformed, anchor_scale(vector, rayleigh)));
    if (!isfinite(residual) || residual > kHipAnchorEpsilon * fmax(kHipAnchorEpsilon, fabs(rayleigh))) {
        return false;
    }
    *output = anchor_canonical_direction(vector);
    return true;
}

__device__ void anchor_write_vec(double *output, HipAnchorVec3 value) {
    output[0] = value.x;
    output[1] = value.y;
    output[2] = value.z;
}

__device__ void anchor_typed_failure(
    bg_native_fixed64_single_anchor_kernel_result_v1 *result,
    bg_docking_fixed64_single_anchor_failure failure) {
    result->status = BG_DOCKING_FIXED64_SINGLE_ANCHOR_TYPED_FAILURE;
    result->failure_code = failure;
}

__global__ void fixed64_single_anchor_kernel(
    bg_docking_fixed64_lane lane,
    bg_docking_fixed64_anchor_kind anchor_kind,
    uint32_t lane_offset,
    size_t ligand_count,
    const double *source_x,
    const double *source_y,
    const double *source_z,
    size_t ligand_feature_count,
    const double *ligand_feature_x,
    const double *ligand_feature_y,
    const double *ligand_feature_z,
    size_t receptor_feature_count,
    const double *receptor_feature_x,
    const double *receptor_feature_y,
    const double *receptor_feature_z,
    HipAnchorVec3 pocket_center,
    double *out_x,
    double *out_y,
    double *out_z,
    bg_native_fixed64_single_anchor_kernel_result_v1 *out_result) {
    if (blockIdx.x != 0 || threadIdx.x != 0) return;
    bg_native_fixed64_single_anchor_kernel_result_v1 result{};
    const HipAnchorVec3 ligand_center = anchor_centroid(source_x, source_y, source_z, ligand_count);
    HipAnchorVec3 ligand_anchor = anchor_centroid(
        ligand_feature_x, ligand_feature_y, ligand_feature_z, ligand_feature_count);
    HipAnchorVec3 receptor_anchor = anchor_centroid(
        receptor_feature_x, receptor_feature_y, receptor_feature_z, receptor_feature_count);
    HipAnchorVec3 ligand_direction{};
    HipAnchorVec3 local_normal{};
    HipAnchorVec3 alignment_target{};
    if (lane == BG_DOCKING_FIXED64_LANE_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR) {
        ligand_anchor = {ligand_feature_x[0], ligand_feature_y[0], ligand_feature_z[0]};
        const HipAnchorVec3 hydrogen{ligand_feature_x[1], ligand_feature_y[1], ligand_feature_z[1]};
        if (!anchor_normalize(anchor_minus(hydrogen, ligand_anchor), &ligand_direction)) {
            anchor_typed_failure(&result, BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_LIGAND_DIRECTION);
            *out_result = result;
            return;
        }
        if (!anchor_normalize(anchor_minus(pocket_center, receptor_anchor), &local_normal)) {
            anchor_typed_failure(&result, BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_LOCAL_SURFACE_NORMAL);
            *out_result = result;
            return;
        }
        alignment_target = anchor_scale(local_normal, -1.0);
    } else if (lane == BG_DOCKING_FIXED64_LANE_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR) {
        if (!anchor_normalize(anchor_minus(ligand_anchor, ligand_center), &ligand_direction)) {
            anchor_typed_failure(&result, BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_LIGAND_DIRECTION);
            *out_result = result;
            return;
        }
        receptor_anchor = {receptor_feature_x[0], receptor_feature_y[0], receptor_feature_z[0]};
        const HipAnchorVec3 hydrogen{receptor_feature_x[1], receptor_feature_y[1], receptor_feature_z[1]};
        if (!anchor_normalize(anchor_minus(hydrogen, receptor_anchor), &local_normal)) {
            anchor_typed_failure(&result, BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_RECEPTOR_DIRECTION);
            *out_result = result;
            return;
        }
        alignment_target = anchor_scale(local_normal, -1.0);
    } else if (lane == BG_DOCKING_FIXED64_LANE_COMPLEMENTARY_CHARGE) {
        if (!anchor_normalize(anchor_minus(ligand_anchor, ligand_center), &ligand_direction)) {
            anchor_typed_failure(&result, BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_LIGAND_DIRECTION);
            *out_result = result;
            return;
        }
        if (!anchor_normalize(anchor_minus(pocket_center, receptor_anchor), &local_normal)) {
            anchor_typed_failure(&result, BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_LOCAL_SURFACE_NORMAL);
            *out_result = result;
            return;
        }
        alignment_target = anchor_scale(local_normal, -1.0);
    } else if (lane == BG_DOCKING_FIXED64_LANE_AROMATIC_PLANE) {
        if (!anchor_aromatic_normal(ligand_feature_x, ligand_feature_y, ligand_feature_z, ligand_feature_count, &ligand_direction)) {
            anchor_typed_failure(&result, BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_AROMATIC_PLANE);
            *out_result = result;
            return;
        }
        HipAnchorVec3 receptor_normal{};
        if (!anchor_aromatic_normal(receptor_feature_x, receptor_feature_y, receptor_feature_z, receptor_feature_count, &receptor_normal)) {
            anchor_typed_failure(&result, BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_AROMATIC_PLANE);
            *out_result = result;
            return;
        }
        HipAnchorVec3 toward_pocket{};
        if (!anchor_normalize(anchor_minus(pocket_center, receptor_anchor), &toward_pocket)) {
            anchor_typed_failure(&result, BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_LOCAL_SURFACE_NORMAL);
            *out_result = result;
            return;
        }
        const double facing = anchor_dot(receptor_normal, toward_pocket);
        if (fabs(facing) <= kHipAnchorEpsilon) {
            anchor_typed_failure(&result, BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_LOCAL_SURFACE_NORMAL);
            *out_result = result;
            return;
        }
        if (facing < 0.0) receptor_normal = anchor_scale(receptor_normal, -1.0);
        if (!anchor_normalize(receptor_normal, &local_normal)) {
            anchor_typed_failure(&result, BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_LOCAL_SURFACE_NORMAL);
            *out_result = result;
            return;
        }
        alignment_target = local_normal;
    } else {
        if (!anchor_principal_axis(ligand_feature_x, ligand_feature_y, ligand_feature_z, ligand_feature_count, &ligand_direction) ||
            !anchor_principal_axis(receptor_feature_x, receptor_feature_y, receptor_feature_z, receptor_feature_count, &alignment_target)) {
            anchor_typed_failure(&result, BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_PRINCIPAL_AXIS);
            *out_result = result;
            return;
        }
        if (!anchor_normalize(anchor_minus(pocket_center, receptor_anchor), &local_normal)) {
            anchor_typed_failure(&result, BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_LOCAL_SURFACE_NORMAL);
            *out_result = result;
            return;
        }
    }
    double target_distance = 3.0;
    size_t lane_width = 2;
    if (anchor_kind == BG_DOCKING_FIXED64_ANCHOR_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR ||
        anchor_kind == BG_DOCKING_FIXED64_ANCHOR_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR) {
        target_distance = 2.9;
        lane_width = 4;
    } else if (anchor_kind == BG_DOCKING_FIXED64_ANCHOR_COMPLEMENTARY_CHARGE) {
        target_distance = 3.5;
        lane_width = 4;
    } else if (anchor_kind == BG_DOCKING_FIXED64_ANCHOR_AROMATIC_PLANE) {
        target_distance = 3.8;
    }
    const HipAnchorVec3 target_anchor = anchor_plus(receptor_anchor, anchor_scale(local_normal, target_distance));
    bool ok = false;
    const HipAnchorQuaternion base = anchor_between(ligand_direction, alignment_target, &ok);
    if (!ok) {
        anchor_typed_failure(&result, BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_LIGAND_DIRECTION);
        *out_result = result;
        return;
    }
    const double twist_angle = 2.0 * kHipAnchorPi * static_cast<double>(lane_offset) / static_cast<double>(lane_width);
    const HipAnchorQuaternion twist = anchor_rotation_about(alignment_target, twist_angle, &ok);
    const HipAnchorQuaternion quaternion = ok ? anchor_multiply(twist, base, &ok) : twist;
    if (!ok) {
        anchor_typed_failure(&result, BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_NONFINITE_OUTPUT);
        *out_result = result;
        return;
    }
    const HipAnchorVec3 translation = anchor_minus(target_anchor, anchor_rotate(quaternion, ligand_anchor));
    for (size_t atom = 0; atom < ligand_count; ++atom) {
        const HipAnchorVec3 placed = anchor_plus(
            anchor_rotate(quaternion, {source_x[atom], source_y[atom], source_z[atom]}),
            translation);
        if (!isfinite(placed.x) || !isfinite(placed.y) || !isfinite(placed.z) ||
            fabs(placed.x) > kHipAnchorMaximumCoordinateAngstrom ||
            fabs(placed.y) > kHipAnchorMaximumCoordinateAngstrom ||
            fabs(placed.z) > kHipAnchorMaximumCoordinateAngstrom) {
            bg_native_fixed64_single_anchor_kernel_result_v1 failure{};
            anchor_typed_failure(&failure, BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_NONFINITE_OUTPUT);
            *out_result = failure;
            return;
        }
        out_x[atom] = placed.x;
        out_y[atom] = placed.y;
        out_z[atom] = placed.z;
    }
    result.status = BG_DOCKING_FIXED64_SINGLE_ANCHOR_PLACED;
    result.failure_code = BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_NONE;
    anchor_write_vec(result.ligand_anchor_point_angstrom, ligand_anchor);
    anchor_write_vec(result.receptor_anchor_point_angstrom, receptor_anchor);
    anchor_write_vec(result.target_anchor_point_angstrom, target_anchor);
    anchor_write_vec(result.local_surface_normal, local_normal);
    anchor_write_vec(result.approach_vector, anchor_scale(local_normal, -1.0));
    anchor_write_vec(result.ligand_direction, ligand_direction);
    anchor_write_vec(result.alignment_target_direction, alignment_target);
    result.target_distance_angstrom = target_distance;
    result.twist_angle_radians = twist_angle;
    result.quaternion_x = quaternion.x;
    result.quaternion_y = quaternion.y;
    result.quaternion_z = quaternion.z;
    result.quaternion_w = quaternion.w;
    anchor_write_vec(result.translation_angstrom, translation);
    result.coordinates_written = UINT8_C(1);
    *out_result = result;
}

}  // namespace

extern "C" int32_t BG_DOCKING_FIXED64_SINGLE_ANCHOR_PLACE(
    int32_t device_ordinal,
    const bg_native_fixed64_single_anchor_kernel_input_v1 *input,
    double *out_x,
    double *out_y,
    double *out_z,
    bg_native_fixed64_single_anchor_kernel_result_v1 *out_result,
    char *error_message,
    size_t error_capacity) {
    fixed64_anchor_clear_error(error_message, error_capacity);
    if (input == nullptr || out_x == nullptr || out_y == nullptr || out_z == nullptr ||
        out_result == nullptr || input->struct_size != sizeof(*input) ||
        input->abi_version != UINT32_C(1) || input->reserved0 != 0 ||
        !fixed64_anchor_reserved_is_zero(input->reserved) ||
        input->ligand_atom_count == 0 || input->ligand_atom_count > kHipAnchorMaximumLigandAtoms ||
        input->ligand_feature_atom_count == 0 || input->ligand_feature_atom_count > kHipAnchorMaximumFeatureAtoms ||
        input->receptor_feature_atom_count == 0 || input->receptor_feature_atom_count > kHipAnchorMaximumFeatureAtoms ||
        input->source_x_angstrom == nullptr || input->source_y_angstrom == nullptr || input->source_z_angstrom == nullptr ||
        input->ligand_feature_x_angstrom == nullptr || input->ligand_feature_y_angstrom == nullptr || input->ligand_feature_z_angstrom == nullptr ||
        input->receptor_feature_x_angstrom == nullptr || input->receptor_feature_y_angstrom == nullptr || input->receptor_feature_z_angstrom == nullptr) {
        return fixed64_anchor_fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            "HIP single-anchor descriptor is invalid");
    }
    if (hipSetDevice(device_ordinal) != hipSuccess) {
        return fixed64_anchor_fail(
            BG_STATUS_BACKEND_UNAVAILABLE,
            error_message,
            error_capacity,
            "HIP single-anchor device is unavailable");
    }
    const size_t ligand_count = static_cast<size_t>(input->ligand_atom_count);
    const size_t ligand_feature_count = static_cast<size_t>(input->ligand_feature_atom_count);
    const size_t receptor_feature_count = static_cast<size_t>(input->receptor_feature_atom_count);
    Fixed64AnchorDeviceBuffer<double> source_x;
    Fixed64AnchorDeviceBuffer<double> source_y;
    Fixed64AnchorDeviceBuffer<double> source_z;
    Fixed64AnchorDeviceBuffer<double> ligand_feature_x;
    Fixed64AnchorDeviceBuffer<double> ligand_feature_y;
    Fixed64AnchorDeviceBuffer<double> ligand_feature_z;
    Fixed64AnchorDeviceBuffer<double> receptor_feature_x;
    Fixed64AnchorDeviceBuffer<double> receptor_feature_y;
    Fixed64AnchorDeviceBuffer<double> receptor_feature_z;
    Fixed64AnchorDeviceBuffer<double> result_x;
    Fixed64AnchorDeviceBuffer<double> result_y;
    Fixed64AnchorDeviceBuffer<double> result_z;
    Fixed64AnchorDeviceBuffer<bg_native_fixed64_single_anchor_kernel_result_v1> result;
    hipError_t status = source_x.allocate(ligand_count);
#define BG_ANCHOR_ALLOCATE(buffer, count) \
    if (status == hipSuccess) status = buffer.allocate(count)
    BG_ANCHOR_ALLOCATE(source_y, ligand_count);
    BG_ANCHOR_ALLOCATE(source_z, ligand_count);
    BG_ANCHOR_ALLOCATE(ligand_feature_x, ligand_feature_count);
    BG_ANCHOR_ALLOCATE(ligand_feature_y, ligand_feature_count);
    BG_ANCHOR_ALLOCATE(ligand_feature_z, ligand_feature_count);
    BG_ANCHOR_ALLOCATE(receptor_feature_x, receptor_feature_count);
    BG_ANCHOR_ALLOCATE(receptor_feature_y, receptor_feature_count);
    BG_ANCHOR_ALLOCATE(receptor_feature_z, receptor_feature_count);
    BG_ANCHOR_ALLOCATE(result_x, ligand_count);
    BG_ANCHOR_ALLOCATE(result_y, ligand_count);
    BG_ANCHOR_ALLOCATE(result_z, ligand_count);
    BG_ANCHOR_ALLOCATE(result, 1);
#undef BG_ANCHOR_ALLOCATE
    if (status != hipSuccess) {
        return fixed64_anchor_fail_hip(status, error_message, error_capacity, "allocation");
    }
#define BG_ANCHOR_COPY(buffer, values, count) \
    if (status == hipSuccess) status = buffer.copy_from(values, count)
    BG_ANCHOR_COPY(source_x, input->source_x_angstrom, ligand_count);
    BG_ANCHOR_COPY(source_y, input->source_y_angstrom, ligand_count);
    BG_ANCHOR_COPY(source_z, input->source_z_angstrom, ligand_count);
    BG_ANCHOR_COPY(ligand_feature_x, input->ligand_feature_x_angstrom, ligand_feature_count);
    BG_ANCHOR_COPY(ligand_feature_y, input->ligand_feature_y_angstrom, ligand_feature_count);
    BG_ANCHOR_COPY(ligand_feature_z, input->ligand_feature_z_angstrom, ligand_feature_count);
    BG_ANCHOR_COPY(receptor_feature_x, input->receptor_feature_x_angstrom, receptor_feature_count);
    BG_ANCHOR_COPY(receptor_feature_y, input->receptor_feature_y_angstrom, receptor_feature_count);
    BG_ANCHOR_COPY(receptor_feature_z, input->receptor_feature_z_angstrom, receptor_feature_count);
#undef BG_ANCHOR_COPY
    if (status != hipSuccess) {
        return fixed64_anchor_fail_hip(status, error_message, error_capacity, "input copy");
    }
    const HipAnchorVec3 pocket_center{
        input->pocket_center_angstrom[0],
        input->pocket_center_angstrom[1],
        input->pocket_center_angstrom[2]};
    hipLaunchKernelGGL(
        fixed64_single_anchor_kernel,
        dim3(1),
        dim3(1),
        0,
        0,
        input->lane,
        input->anchor_kind,
        input->lane_offset,
        ligand_count,
        source_x.get(), source_y.get(), source_z.get(),
        ligand_feature_count,
        ligand_feature_x.get(), ligand_feature_y.get(), ligand_feature_z.get(),
        receptor_feature_count,
        receptor_feature_x.get(), receptor_feature_y.get(), receptor_feature_z.get(),
        pocket_center,
        result_x.get(), result_y.get(), result_z.get(), result.get());
    status = hipGetLastError();
    if (status == hipSuccess) status = hipDeviceSynchronize();
    if (status != hipSuccess) {
        return fixed64_anchor_fail_hip(status, error_message, error_capacity, "kernel");
    }
    bg_native_fixed64_single_anchor_kernel_result_v1 host_result{};
    status = result.copy_to(&host_result, 1);
    if (status == hipSuccess && host_result.coordinates_written != UINT8_C(0)) {
        status = result_x.copy_to(out_x, ligand_count);
        if (status == hipSuccess) status = result_y.copy_to(out_y, ligand_count);
        if (status == hipSuccess) status = result_z.copy_to(out_z, ligand_count);
    }
    if (status != hipSuccess) {
        return fixed64_anchor_fail_hip(status, error_message, error_capacity, "result copy");
    }
    *out_result = host_result;
    return BG_STATUS_OK;
}
