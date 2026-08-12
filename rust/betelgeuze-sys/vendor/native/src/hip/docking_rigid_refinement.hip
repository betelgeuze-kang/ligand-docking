#include <hip/hip_runtime.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <limits>
#include <memory>
#include <new>

#if !defined(BG_DOCKING_RIGID_CREATE) || \
    !defined(BG_DOCKING_RIGID_DESTROY) || \
    !defined(BG_DOCKING_RIGID_REFINE_FIXED64) || \
    !defined(BG_DOCKING_RIGID_LANE)
#  error "native HIP rigid-refinement provider identity is not configured"
#endif

namespace {

constexpr size_t kRigidCandidateCount =
    BG_DOCKING_FIXED64_CANDIDATE_COUNT;
constexpr size_t kRigidMaxLigandAtoms = 512;
constexpr size_t kRigidMaxReceptorAtoms = 65'536;
constexpr size_t kRigidMaxPairEvaluations = 250'000'000;
constexpr uint64_t kRigidMaxSteps = UINT64_C(128);
constexpr double kRigidNearClearPenalty = 0.000244140625;

void rigid_clear_error(char *message, size_t capacity) noexcept {
    if (message != nullptr && capacity > 0) {
        message[0] = '\0';
    }
}

int32_t rigid_fail(
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

int32_t rigid_fail_hip(
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
            BG_DOCKING_RIGID_LANE,
            operation,
            detail == nullptr ? "unknown HIP runtime error" : detail);
        message[capacity - 1] = '\0';
    }
    return status;
}

template <size_t Count>
bool rigid_reserved_is_zero(const uint64_t (&values)[Count]) noexcept {
    for (const uint64_t value : values) {
        if (value != UINT64_C(0)) {
            return false;
        }
    }
    return true;
}

template <typename Value>
bool rigid_pointer_valid(const Value *pointer, size_t count) noexcept {
    return count == 0 ||
           (pointer != nullptr &&
            reinterpret_cast<uintptr_t>(pointer) % alignof(Value) == 0);
}

template <typename Value>
class RigidDeviceBuffer final {
public:
    RigidDeviceBuffer() = default;
    RigidDeviceBuffer(const RigidDeviceBuffer &) = delete;
    RigidDeviceBuffer &operator=(const RigidDeviceBuffer &) = delete;

    ~RigidDeviceBuffer() {
        if (pointer_ != nullptr) {
            static_cast<void>(hipFree(pointer_));
        }
    }

    hipError_t allocate(size_t count) noexcept {
        if (count == 0) {
            return hipSuccess;
        }
        if (pointer_ != nullptr ||
            count > std::numeric_limits<size_t>::max() / sizeof(Value)) {
            return hipErrorInvalidValue;
        }
        return hipMalloc(
            reinterpret_cast<void **>(&pointer_), count * sizeof(Value));
    }

    hipError_t copy_from(const Value *source, size_t count) noexcept {
        if (count == 0) {
            return hipSuccess;
        }
        if (source == nullptr) {
            return hipErrorInvalidValue;
        }
        hipError_t status = allocate(count);
        if (status != hipSuccess) {
            return status;
        }
        return hipMemcpy(
            pointer_, source, count * sizeof(Value), hipMemcpyHostToDevice);
    }

    hipError_t copy_to(Value *destination, size_t count) const noexcept {
        if (count == 0) {
            return hipSuccess;
        }
        if (destination == nullptr || pointer_ == nullptr ||
            count > std::numeric_limits<size_t>::max() / sizeof(Value)) {
            return hipErrorInvalidValue;
        }
        return hipMemcpy(
            destination,
            pointer_,
            count * sizeof(Value),
            hipMemcpyDeviceToHost);
    }

    Value *get() noexcept { return pointer_; }
    const Value *get() const noexcept { return pointer_; }

private:
    Value *pointer_ = nullptr;
};

class RigidDeviceGuard final {
public:
    RigidDeviceGuard() noexcept {
        if (hipGetDevice(&previous_) == hipSuccess) {
            has_previous_ = true;
        }
    }
    RigidDeviceGuard(const RigidDeviceGuard &) = delete;
    RigidDeviceGuard &operator=(const RigidDeviceGuard &) = delete;
    ~RigidDeviceGuard() {
        if (has_previous_) {
            static_cast<void>(hipSetDevice(previous_));
        }
    }

private:
    int previous_ = 0;
    bool has_previous_ = false;
};

struct RigidV2Config final {
    double overlap_scale;
    double maximum_step_angstrom;
    double minimum_step_angstrom;
    double maximum_total_translation_angstrom;
    uint64_t maximum_backtracking_evaluations;
    double penalty_tolerance;
    double epsilon_angstrom;
};

struct RigidV3Config final {
    RigidV2Config v2;
    double maximum_rotation_step_radians;
    double minimum_rotation_step_radians;
    double maximum_total_rotation_radians;
    uint64_t maximum_rotation_steps;
    double minimum_rotation_relative_penalty_reduction;
    double maximum_centroid_offset_angstrom;
};

struct RigidDeviceContext final {
    size_t receptor_count;
    size_t ligand_count;
    const double *receptor_x;
    const double *receptor_y;
    const double *receptor_z;
    const double *receptor_radii;
    const double *ligand_radii;
    double pocket_center[3];
    double pocket_radius;
    RigidV2Config v2;
    RigidV3Config v3;
    RigidV3Config clearance_v4;
};

struct RigidState final {
    int32_t device_ordinal = 0;
    size_t receptor_count = 0;
    size_t ligand_count = 0;
    double pocket_center[3]{};
    double pocket_radius = 0.0;
    RigidV2Config v2{};
    RigidV3Config v3{};
    RigidV3Config clearance_v4{};
    RigidDeviceBuffer<double> receptor_x;
    RigidDeviceBuffer<double> receptor_y;
    RigidDeviceBuffer<double> receptor_z;
    RigidDeviceBuffer<double> receptor_radii;
    RigidDeviceBuffer<double> ligand_radii;

    RigidDeviceContext device_context() const noexcept {
        RigidDeviceContext result{};
        result.receptor_count = receptor_count;
        result.ligand_count = ligand_count;
        result.receptor_x = receptor_x.get();
        result.receptor_y = receptor_y.get();
        result.receptor_z = receptor_z.get();
        result.receptor_radii = receptor_radii.get();
        result.ligand_radii = ligand_radii.get();
        result.pocket_center[0] = pocket_center[0];
        result.pocket_center[1] = pocket_center[1];
        result.pocket_center[2] = pocket_center[2];
        result.pocket_radius = pocket_radius;
        result.v2 = v2;
        result.v3 = v3;
        result.clearance_v4 = clearance_v4;
        return result;
    }
};

struct RigidDeviceBatch final {
    const int32_t *mode;
    const uint64_t *max_steps;
    const double *x;
    const double *y;
    const double *z;
};

struct RigidDeviceOutputs final {
    bg_docking_rigid_refinement_row_v1 *rows;
    double *selected_x;
    double *selected_y;
    double *selected_z;
    double *comparison_x;
    double *comparison_y;
    double *comparison_z;
    double *baseline_x;
    double *baseline_y;
    double *baseline_z;
    double *clearance_x;
    double *clearance_y;
    double *clearance_z;
};

struct RigidScratch final {
    double *current_x;
    double *current_y;
    double *current_z;
    double *trial_x;
    double *trial_y;
    double *trial_z;
    double *best_x;
    double *best_y;
    double *best_z;
};

struct RigidVector3 final {
    double x;
    double y;
    double z;
};

struct RigidQuaternion final {
    double x;
    double y;
    double z;
    double w;
};

__device__ double rigid_canonical_zero(double value) {
    return value == 0.0 ? 0.0 : value;
}

__device__ RigidVector3 rigid_canonical(RigidVector3 value) {
    return {
        rigid_canonical_zero(value.x),
        rigid_canonical_zero(value.y),
        rigid_canonical_zero(value.z),
    };
}

__device__ RigidVector3 rigid_plus(
    RigidVector3 left,
    RigidVector3 right) {
    return {left.x + right.x, left.y + right.y, left.z + right.z};
}

__device__ RigidVector3 rigid_minus(
    RigidVector3 left,
    RigidVector3 right) {
    return {left.x - right.x, left.y - right.y, left.z - right.z};
}

__device__ RigidVector3 rigid_scale(RigidVector3 value, double factor) {
    return {value.x * factor, value.y * factor, value.z * factor};
}

__device__ double rigid_dot(RigidVector3 left, RigidVector3 right) {
    return left.x * right.x + left.y * right.y + left.z * right.z;
}

__device__ RigidVector3 rigid_cross(
    RigidVector3 left,
    RigidVector3 right) {
    return {
        left.y * right.z - left.z * right.y,
        left.z * right.x - left.x * right.z,
        left.x * right.y - left.y * right.x,
    };
}

__device__ double rigid_norm(RigidVector3 value) {
    return sqrt(rigid_dot(value, value));
}

__device__ bool rigid_finite(RigidVector3 value) {
    return isfinite(value.x) && isfinite(value.y) && isfinite(value.z);
}

__device__ int32_t rigid_normalize_quaternion(
    RigidQuaternion value,
    RigidQuaternion *output) {
    const double magnitude = sqrt(
        value.x * value.x + value.y * value.y + value.z * value.z +
        value.w * value.w);
    if (output == nullptr || !isfinite(magnitude) || magnitude <= 1.0e-18) {
        return BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONFINITE_DERIVED_VALUE;
    }
    const double inverse = 1.0 / magnitude;
    value = {
        value.x * inverse,
        value.y * inverse,
        value.z * inverse,
        value.w * inverse,
    };
    if (value.w < 0.0) {
        value = {-value.x, -value.y, -value.z, -value.w};
    }
    *output = {
        rigid_canonical_zero(value.x),
        rigid_canonical_zero(value.y),
        rigid_canonical_zero(value.z),
        rigid_canonical_zero(value.w),
    };
    return BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE;
}

__device__ int32_t rigid_compose_rotation(
    RigidVector3 rotation_step,
    RigidQuaternion current,
    RigidQuaternion *output) {
    const double angle = rigid_norm(rotation_step);
    if (!isfinite(angle)) {
        return BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONFINITE_DERIVED_VALUE;
    }
    if (angle <= 1.0e-18) {
        return rigid_normalize_quaternion(current, output);
    }
    const double half_angle = 0.5 * angle;
    const double scale = sin(half_angle) / angle;
    const RigidQuaternion step{
        rotation_step.x * scale,
        rotation_step.y * scale,
        rotation_step.z * scale,
        cos(half_angle),
    };
    return rigid_normalize_quaternion(
        {
            step.w * current.x + step.x * current.w +
                step.y * current.z - step.z * current.y,
            step.w * current.y - step.x * current.z +
                step.y * current.w + step.z * current.x,
            step.w * current.z + step.x * current.y -
                step.y * current.x + step.z * current.w,
            step.w * current.w - step.x * current.x -
                step.y * current.y - step.z * current.z,
        },
        output);
}

__device__ int32_t rigid_rotation_vector(
    RigidQuaternion value,
    RigidVector3 *output) {
    RigidQuaternion normalized{};
    int32_t failure = rigid_normalize_quaternion(value, &normalized);
    if (failure != BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE ||
        output == nullptr) {
        return BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONFINITE_DERIVED_VALUE;
    }
    const double sine_half = sqrt(
        normalized.x * normalized.x + normalized.y * normalized.y +
        normalized.z * normalized.z);
    if (sine_half <= 1.0e-18) {
        *output = {};
        return BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE;
    }
    const double angle = 2.0 * atan2(sine_half, normalized.w);
    if (!isfinite(angle)) {
        return BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONFINITE_DERIVED_VALUE;
    }
    *output = rigid_canonical({
        normalized.x * angle / sine_half,
        normalized.y * angle / sine_half,
        normalized.z * angle / sine_half,
    });
    return BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE;
}

__device__ void rigid_copy_coordinates(
    size_t count,
    const double *source_x,
    const double *source_y,
    const double *source_z,
    double *target_x,
    double *target_y,
    double *target_z) {
    for (size_t atom = 0; atom < count; ++atom) {
        target_x[atom] = source_x[atom];
        target_y[atom] = source_y[atom];
        target_z[atom] = source_z[atom];
    }
}

__device__ void rigid_zero_coordinates(
    size_t count,
    double *x,
    double *y,
    double *z) {
    for (size_t atom = 0; atom < count; ++atom) {
        x[atom] = 0.0;
        y[atom] = 0.0;
        z[atom] = 0.0;
    }
}

__device__ int32_t rigid_penalty_direction(
    const RigidDeviceContext &context,
    const double *x,
    const double *y,
    const double *z,
    const RigidV2Config &config,
    double *penalty_output,
    RigidVector3 *direction_output) {
    double penalty = 0.0;
    RigidVector3 direction{};
    for (size_t ligand = 0; ligand < context.ligand_count; ++ligand) {
        const RigidVector3 ligand_coordinate{x[ligand], y[ligand], z[ligand]};
        for (size_t receptor = 0; receptor < context.receptor_count;
             ++receptor) {
            const RigidVector3 receptor_coordinate{
                context.receptor_x[receptor],
                context.receptor_y[receptor],
                context.receptor_z[receptor],
            };
            const RigidVector3 delta =
                rigid_minus(ligand_coordinate, receptor_coordinate);
            const double distance =
                fmax(rigid_norm(delta), config.epsilon_angstrom);
            const double cutoff = config.overlap_scale *
                                  (context.ligand_radii[ligand] +
                                   context.receptor_radii[receptor]);
            const double penetration = fmax(cutoff - distance, 0.0);
            const double squared = penetration * penetration;
            penalty += squared * squared;
            direction = rigid_plus(
                direction,
                rigid_scale(delta, squared * penetration / distance));
        }
    }
    if (!isfinite(penalty) || !rigid_finite(direction)) {
        return BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONFINITE_DERIVED_VALUE;
    }
    *penalty_output = rigid_canonical_zero(penalty);
    *direction_output = rigid_canonical(direction);
    return BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE;
}

__device__ int32_t rigid_maximum_penetration_direction(
    const RigidDeviceContext &context,
    const double *x,
    const double *y,
    const double *z,
    const RigidV2Config &config,
    RigidVector3 *output) {
    double best_penetration = -1.0;
    size_t best_ligand = 0;
    size_t best_receptor = 0;
    RigidVector3 best_delta{};
    double best_distance = config.epsilon_angstrom;
    for (size_t ligand = 0; ligand < context.ligand_count; ++ligand) {
        const RigidVector3 ligand_coordinate{x[ligand], y[ligand], z[ligand]};
        for (size_t receptor = 0; receptor < context.receptor_count;
             ++receptor) {
            const RigidVector3 receptor_coordinate{
                context.receptor_x[receptor],
                context.receptor_y[receptor],
                context.receptor_z[receptor],
            };
            const RigidVector3 delta =
                rigid_minus(ligand_coordinate, receptor_coordinate);
            const double distance =
                fmax(rigid_norm(delta), config.epsilon_angstrom);
            const double cutoff = config.overlap_scale *
                                  (context.ligand_radii[ligand] +
                                   context.receptor_radii[receptor]);
            const double penetration = fmax(cutoff - distance, 0.0);
            if (penetration > best_penetration ||
                (penetration == best_penetration &&
                 (ligand < best_ligand ||
                  (ligand == best_ligand && receptor < best_receptor)))) {
                best_penetration = penetration;
                best_ligand = ligand;
                best_receptor = receptor;
                best_delta = delta;
                best_distance = distance;
            }
        }
    }
    if (best_penetration <= 0.0) {
        *output = {};
        return BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE;
    }
    if (rigid_norm(best_delta) > config.epsilon_angstrom) {
        *output = rigid_canonical(rigid_scale(best_delta, 1.0 / best_distance));
        return BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE;
    }
    const size_t signed_axis = (best_ligand * 131 + best_receptor) % 6;
    const double sign = signed_axis % 2 == 0 ? 1.0 : -1.0;
    if (signed_axis / 2 == 0) {
        *output = {sign, 0.0, 0.0};
    } else if (signed_axis / 2 == 1) {
        *output = {0.0, sign, 0.0};
    } else {
        *output = {0.0, 0.0, sign};
    }
    return BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE;
}

__device__ int32_t rigid_candidate_directions(
    const RigidDeviceContext &context,
    const double *x,
    const double *y,
    const double *z,
    RigidVector3 aggregate,
    const RigidV2Config &config,
    RigidVector3 directions[2],
    size_t *count) {
    *count = 0;
    const double aggregate_norm = rigid_norm(aggregate);
    if (aggregate_norm > config.epsilon_angstrom) {
        directions[(*count)++] =
            rigid_canonical(rigid_scale(aggregate, 1.0 / aggregate_norm));
    }
    RigidVector3 fallback{};
    const int32_t failure = rigid_maximum_penetration_direction(
        context, x, y, z, config, &fallback);
    if (failure != BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE) {
        return failure;
    }
    const double fallback_norm = rigid_norm(fallback);
    if (fallback_norm > config.epsilon_angstrom) {
        const RigidVector3 normalized =
            rigid_canonical(rigid_scale(fallback, 1.0 / fallback_norm));
        const bool duplicate =
            *count > 0 && fabs(directions[0].x - normalized.x) <= 1.0e-12 &&
            fabs(directions[0].y - normalized.y) <= 1.0e-12 &&
            fabs(directions[0].z - normalized.z) <= 1.0e-12;
        if (!duplicate) {
            directions[(*count)++] = normalized;
        }
    }
    return BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE;
}

__device__ RigidVector3 rigid_centroid(
    size_t count,
    const double *x,
    const double *y,
    const double *z) {
    RigidVector3 total{};
    for (size_t atom = 0; atom < count; ++atom) {
        total = rigid_plus(total, {x[atom], y[atom], z[atom]});
    }
    return rigid_canonical(rigid_scale(total, 1.0 / static_cast<double>(count)));
}

__device__ void rigid_translate(
    size_t count,
    const double *source_x,
    const double *source_y,
    const double *source_z,
    RigidVector3 step,
    double *target_x,
    double *target_y,
    double *target_z) {
    for (size_t atom = 0; atom < count; ++atom) {
        const RigidVector3 value = rigid_canonical(rigid_plus(
            {source_x[atom], source_y[atom], source_z[atom]}, step));
        target_x[atom] = value.x;
        target_y[atom] = value.y;
        target_z[atom] = value.z;
    }
}

__device__ int32_t rigid_rotation_torque(
    const RigidDeviceContext &context,
    const double *x,
    const double *y,
    const double *z,
    const RigidV2Config &config,
    RigidVector3 *output) {
    const RigidVector3 center =
        rigid_centroid(context.ligand_count, x, y, z);
    RigidVector3 torque{};
    for (size_t ligand = 0; ligand < context.ligand_count; ++ligand) {
        const RigidVector3 ligand_coordinate{x[ligand], y[ligand], z[ligand]};
        const RigidVector3 lever = rigid_minus(ligand_coordinate, center);
        for (size_t receptor = 0; receptor < context.receptor_count;
             ++receptor) {
            const RigidVector3 receptor_coordinate{
                context.receptor_x[receptor],
                context.receptor_y[receptor],
                context.receptor_z[receptor],
            };
            const RigidVector3 delta =
                rigid_minus(ligand_coordinate, receptor_coordinate);
            const double distance =
                fmax(rigid_norm(delta), config.epsilon_angstrom);
            const double cutoff = config.overlap_scale *
                                  (context.ligand_radii[ligand] +
                                   context.receptor_radii[receptor]);
            const double penetration = fmax(cutoff - distance, 0.0);
            const RigidVector3 force = rigid_scale(
                delta,
                penetration * penetration * penetration / distance);
            torque = rigid_plus(torque, rigid_cross(lever, force));
        }
    }
    if (!rigid_finite(torque)) {
        return BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONFINITE_DERIVED_VALUE;
    }
    *output = rigid_canonical(torque);
    return BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE;
}

__device__ int32_t rigid_rotate(
    size_t count,
    const double *source_x,
    const double *source_y,
    const double *source_z,
    RigidVector3 rotation_vector,
    double *target_x,
    double *target_y,
    double *target_z) {
    const double angle = rigid_norm(rotation_vector);
    if (!isfinite(angle)) {
        return BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONFINITE_DERIVED_VALUE;
    }
    if (angle <= 1.0e-18) {
        rigid_copy_coordinates(
            count,
            source_x,
            source_y,
            source_z,
            target_x,
            target_y,
            target_z);
        return BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE;
    }
    const RigidVector3 axis = rigid_scale(rotation_vector, 1.0 / angle);
    const RigidVector3 center =
        rigid_centroid(count, source_x, source_y, source_z);
    const double cosine = cos(angle);
    const double sine = sin(angle);
    for (size_t atom = 0; atom < count; ++atom) {
        const RigidVector3 centered = rigid_minus(
            {source_x[atom], source_y[atom], source_z[atom]}, center);
        const RigidVector3 rotated = rigid_plus(
            rigid_plus(
                rigid_plus(
                    rigid_scale(centered, cosine),
                    rigid_scale(rigid_cross(axis, centered), sine)),
                rigid_scale(axis, rigid_dot(axis, centered) * (1.0 - cosine))),
            center);
        if (!rigid_finite(rotated)) {
            return BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONFINITE_DERIVED_VALUE;
        }
        const RigidVector3 canonical = rigid_canonical(rotated);
        target_x[atom] = canonical.x;
        target_y[atom] = canonical.y;
        target_z[atom] = canonical.z;
    }
    return BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE;
}

__device__ bool rigid_trial_less(
    double penalty,
    size_t direction,
    size_t backtracking,
    double best_penalty,
    size_t best_direction,
    size_t best_backtracking) {
    return penalty < best_penalty ||
           (penalty == best_penalty &&
            (direction < best_direction ||
             (direction == best_direction &&
              backtracking < best_backtracking)));
}

__device__ bg_docking_rigid_refinement_evidence_v1 rigid_empty_evidence() {
    bg_docking_rigid_refinement_evidence_v1 result{};
    return result;
}

__device__ int32_t rigid_refine_v2(
    const RigidDeviceContext &context,
    const double *source_x,
    const double *source_y,
    const double *source_z,
    uint64_t max_steps,
    const RigidV2Config &config,
    bg_docking_rigid_refinement_profile profile,
    RigidScratch scratch,
    double *output_x,
    double *output_y,
    double *output_z,
    bg_docking_rigid_refinement_evidence_v1 *evidence) {
    rigid_copy_coordinates(
        context.ligand_count,
        source_x,
        source_y,
        source_z,
        scratch.current_x,
        scratch.current_y,
        scratch.current_z);
    double initial_penalty = 0.0;
    RigidVector3 unused_direction{};
    int32_t failure = rigid_penalty_direction(
        context,
        scratch.current_x,
        scratch.current_y,
        scratch.current_z,
        config,
        &initial_penalty,
        &unused_direction);
    if (failure != BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE) {
        return failure;
    }
    RigidVector3 total_shift{};
    uint64_t accepted_steps = 0;
    uint64_t evaluation_count = 0;
    uint64_t fallback_count = 0;
    for (uint64_t iteration = 0; iteration < max_steps; ++iteration) {
        double penalty = 0.0;
        RigidVector3 aggregate{};
        failure = rigid_penalty_direction(
            context,
            scratch.current_x,
            scratch.current_y,
            scratch.current_z,
            config,
            &penalty,
            &aggregate);
        if (failure != BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE) {
            return failure;
        }
        if (penalty <= config.penalty_tolerance) {
            break;
        }
        const double remaining =
            config.maximum_total_translation_angstrom - rigid_norm(total_shift);
        if (remaining <= config.minimum_step_angstrom) {
            break;
        }
        RigidVector3 directions[2]{};
        size_t direction_count = 0;
        failure = rigid_candidate_directions(
            context,
            scratch.current_x,
            scratch.current_y,
            scratch.current_z,
            aggregate,
            config,
            directions,
            &direction_count);
        if (failure != BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE) {
            return failure;
        }
        if (direction_count == 0) {
            break;
        }
        const double base_step =
            fmin(config.maximum_step_angstrom, remaining);
        bool has_best = false;
        double best_penalty = 0.0;
        size_t best_direction = 0;
        size_t best_backtracking = 0;
        RigidVector3 best_shift{};
        for (size_t direction = 0; direction < direction_count; ++direction) {
            double step_size = base_step;
            for (uint64_t backtracking = 0;
                 backtracking < config.maximum_backtracking_evaluations;
                 ++backtracking) {
                if (step_size < config.minimum_step_angstrom) {
                    break;
                }
                const RigidVector3 step =
                    rigid_scale(directions[direction], step_size);
                const RigidVector3 trial_shift =
                    rigid_plus(total_shift, step);
                if (rigid_norm(trial_shift) >
                    config.maximum_total_translation_angstrom +
                        config.epsilon_angstrom) {
                    step_size *= 0.5;
                    continue;
                }
                rigid_translate(
                    context.ligand_count,
                    scratch.current_x,
                    scratch.current_y,
                    scratch.current_z,
                    step,
                    scratch.trial_x,
                    scratch.trial_y,
                    scratch.trial_z);
                double trial_penalty = 0.0;
                RigidVector3 trial_direction{};
                failure = rigid_penalty_direction(
                    context,
                    scratch.trial_x,
                    scratch.trial_y,
                    scratch.trial_z,
                    config,
                    &trial_penalty,
                    &trial_direction);
                if (failure != BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE) {
                    return failure;
                }
                ++evaluation_count;
                if (!has_best ||
                    rigid_trial_less(
                        trial_penalty,
                        direction,
                        static_cast<size_t>(backtracking),
                        best_penalty,
                        best_direction,
                        best_backtracking)) {
                    has_best = true;
                    best_penalty = trial_penalty;
                    best_direction = direction;
                    best_backtracking = static_cast<size_t>(backtracking);
                    best_shift = trial_shift;
                    rigid_copy_coordinates(
                        context.ligand_count,
                        scratch.trial_x,
                        scratch.trial_y,
                        scratch.trial_z,
                        scratch.best_x,
                        scratch.best_y,
                        scratch.best_z);
                }
                step_size *= 0.5;
            }
        }
        const double reduction =
            fmax(config.penalty_tolerance, fabs(penalty) * 1.0e-12);
        if (!has_best || best_penalty > penalty - reduction) {
            break;
        }
        rigid_copy_coordinates(
            context.ligand_count,
            scratch.best_x,
            scratch.best_y,
            scratch.best_z,
            scratch.current_x,
            scratch.current_y,
            scratch.current_z);
        total_shift = best_shift;
        ++accepted_steps;
        fallback_count += static_cast<uint64_t>(best_direction > 0);
    }
    double final_penalty = 0.0;
    failure = rigid_penalty_direction(
        context,
        scratch.current_x,
        scratch.current_y,
        scratch.current_z,
        config,
        &final_penalty,
        &unused_direction);
    if (failure != BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE) {
        return failure;
    }
    rigid_copy_coordinates(
        context.ligand_count,
        scratch.current_x,
        scratch.current_y,
        scratch.current_z,
        output_x,
        output_y,
        output_z);
    *evidence = rigid_empty_evidence();
    evidence->profile = profile;
    evidence->available = UINT8_C(1);
    evidence->accepted_steps = accepted_steps;
    evidence->accepted_translation_steps = accepted_steps;
    evidence->line_search_evaluation_count = evaluation_count;
    evidence->fallback_direction_step_count = fallback_count;
    evidence->initial_penalty = initial_penalty;
    evidence->final_penalty = final_penalty;
    evidence->total_translation_angstrom[0] =
        rigid_canonical_zero(total_shift.x);
    evidence->total_translation_angstrom[1] =
        rigid_canonical_zero(total_shift.y);
    evidence->total_translation_angstrom[2] =
        rigid_canonical_zero(total_shift.z);
    return BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE;
}

__device__ int32_t rigid_refine_v3(
    const RigidDeviceContext &context,
    const double *source_x,
    const double *source_y,
    const double *source_z,
    uint64_t max_steps,
    const RigidV3Config &config,
    bg_docking_rigid_refinement_profile profile,
    RigidScratch scratch,
    double *output_x,
    double *output_y,
    double *output_z,
    bg_docking_rigid_refinement_evidence_v1 *evidence) {
    rigid_copy_coordinates(
        context.ligand_count,
        source_x,
        source_y,
        source_z,
        scratch.current_x,
        scratch.current_y,
        scratch.current_z);
    double initial_penalty = 0.0;
    RigidVector3 unused_direction{};
    int32_t failure = rigid_penalty_direction(
        context,
        scratch.current_x,
        scratch.current_y,
        scratch.current_z,
        config.v2,
        &initial_penalty,
        &unused_direction);
    if (failure != BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE) {
        return failure;
    }
    const double initial_centroid_offset = rigid_norm(rigid_minus(
        rigid_centroid(
            context.ligand_count,
            scratch.current_x,
            scratch.current_y,
            scratch.current_z),
        {context.pocket_center[0],
         context.pocket_center[1],
         context.pocket_center[2]}));
    const double maximum_centroid_offset =
        fmin(config.maximum_centroid_offset_angstrom, context.pocket_radius);
    RigidVector3 total_shift{};
    RigidQuaternion total_rotation{0.0, 0.0, 0.0, 1.0};
    double total_rotation_path = 0.0;
    uint64_t accepted_steps = 0;
    uint64_t accepted_rotation_steps = 0;
    uint64_t evaluation_count = 0;
    uint64_t fallback_count = 0;
    for (uint64_t iteration = 0; iteration < max_steps; ++iteration) {
        double penalty = 0.0;
        RigidVector3 aggregate{};
        failure = rigid_penalty_direction(
            context,
            scratch.current_x,
            scratch.current_y,
            scratch.current_z,
            config.v2,
            &penalty,
            &aggregate);
        if (failure != BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE) {
            return failure;
        }
        if (penalty <= config.v2.penalty_tolerance) {
            break;
        }
        const double remaining_translation =
            config.v2.maximum_total_translation_angstrom -
            rigid_norm(total_shift);
        const double remaining_rotation =
            config.maximum_total_rotation_radians - total_rotation_path;
        if (remaining_translation <= config.v2.minimum_step_angstrom &&
            remaining_rotation <= config.minimum_rotation_step_radians) {
            break;
        }
        RigidVector3 directions[2]{};
        size_t direction_count = 0;
        failure = rigid_candidate_directions(
            context,
            scratch.current_x,
            scratch.current_y,
            scratch.current_z,
            aggregate,
            config.v2,
            directions,
            &direction_count);
        if (failure != BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE) {
            return failure;
        }
        bool has_best = false;
        double best_penalty = 0.0;
        size_t best_direction = 0;
        size_t best_backtracking = 0;
        RigidVector3 best_shift{};
        RigidQuaternion best_rotation{};
        double best_rotation_path = 0.0;
        if (remaining_translation > config.v2.minimum_step_angstrom) {
            const double base_step =
                fmin(config.v2.maximum_step_angstrom, remaining_translation);
            for (size_t direction = 0; direction < direction_count; ++direction) {
                double step_size = base_step;
                for (uint64_t backtracking = 0;
                     backtracking < config.v2.maximum_backtracking_evaluations;
                     ++backtracking) {
                    if (step_size < config.v2.minimum_step_angstrom) {
                        break;
                    }
                    const RigidVector3 step =
                        rigid_scale(directions[direction], step_size);
                    const RigidVector3 trial_shift =
                        rigid_plus(total_shift, step);
                    if (rigid_norm(trial_shift) >
                        config.v2.maximum_total_translation_angstrom +
                            config.v2.epsilon_angstrom) {
                        step_size *= 0.5;
                        continue;
                    }
                    rigid_translate(
                        context.ligand_count,
                        scratch.current_x,
                        scratch.current_y,
                        scratch.current_z,
                        step,
                        scratch.trial_x,
                        scratch.trial_y,
                        scratch.trial_z);
                    const double centroid_offset = rigid_norm(rigid_minus(
                        rigid_centroid(
                            context.ligand_count,
                            scratch.trial_x,
                            scratch.trial_y,
                            scratch.trial_z),
                        {context.pocket_center[0],
                         context.pocket_center[1],
                         context.pocket_center[2]}));
                    if (centroid_offset >
                        maximum_centroid_offset + config.v2.epsilon_angstrom) {
                        step_size *= 0.5;
                        continue;
                    }
                    double trial_penalty = 0.0;
                    RigidVector3 trial_direction{};
                    failure = rigid_penalty_direction(
                        context,
                        scratch.trial_x,
                        scratch.trial_y,
                        scratch.trial_z,
                        config.v2,
                        &trial_penalty,
                        &trial_direction);
                    if (failure != BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE) {
                        return failure;
                    }
                    ++evaluation_count;
                    if (!has_best ||
                        rigid_trial_less(
                            trial_penalty,
                            direction,
                            static_cast<size_t>(backtracking),
                            best_penalty,
                            best_direction,
                            best_backtracking)) {
                        has_best = true;
                        best_penalty = trial_penalty;
                        best_direction = direction;
                        best_backtracking = static_cast<size_t>(backtracking);
                        best_shift = trial_shift;
                        best_rotation = total_rotation;
                        best_rotation_path = total_rotation_path;
                        rigid_copy_coordinates(
                            context.ligand_count,
                            scratch.trial_x,
                            scratch.trial_y,
                            scratch.trial_z,
                            scratch.best_x,
                            scratch.best_y,
                            scratch.best_z);
                    }
                    step_size *= 0.5;
                }
            }
        }
        const double reduction = fmax(
            config.v2.penalty_tolerance,
            fabs(penalty) * 1.0e-12);
        const bool translation_improves =
            has_best && best_penalty <= penalty - reduction;
        RigidVector3 torque{};
        failure = rigid_rotation_torque(
            context,
            scratch.current_x,
            scratch.current_y,
            scratch.current_z,
            config.v2,
            &torque);
        if (failure != BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE) {
            return failure;
        }
        const double torque_norm = rigid_norm(torque);
        if (!translation_improves &&
            torque_norm > config.v2.epsilon_angstrom &&
            remaining_rotation > config.minimum_rotation_step_radians &&
            accepted_rotation_steps < config.maximum_rotation_steps) {
            const RigidVector3 axis = rigid_scale(torque, 1.0 / torque_norm);
            const double rotation_reduction = fmax(
                reduction,
                fabs(penalty) *
                    config.minimum_rotation_relative_penalty_reduction);
            double angle = fmin(
                config.maximum_rotation_step_radians,
                remaining_rotation);
            for (uint64_t backtracking = 0;
                 backtracking < config.v2.maximum_backtracking_evaluations;
                 ++backtracking) {
                if (angle < config.minimum_rotation_step_radians) {
                    break;
                }
                const RigidVector3 rotation_step = rigid_scale(axis, angle);
                failure = rigid_rotate(
                    context.ligand_count,
                    scratch.current_x,
                    scratch.current_y,
                    scratch.current_z,
                    rotation_step,
                    scratch.trial_x,
                    scratch.trial_y,
                    scratch.trial_z);
                if (failure != BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE) {
                    return failure;
                }
                double trial_penalty = 0.0;
                RigidVector3 trial_direction{};
                failure = rigid_penalty_direction(
                    context,
                    scratch.trial_x,
                    scratch.trial_y,
                    scratch.trial_z,
                    config.v2,
                    &trial_penalty,
                    &trial_direction);
                if (failure != BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE) {
                    return failure;
                }
                ++evaluation_count;
                const size_t direction = 2;
                if (trial_penalty <= penalty - rotation_reduction &&
                    (!has_best ||
                     rigid_trial_less(
                         trial_penalty,
                         direction,
                         static_cast<size_t>(backtracking),
                         best_penalty,
                         best_direction,
                         best_backtracking))) {
                    has_best = true;
                    best_penalty = trial_penalty;
                    best_direction = direction;
                    best_backtracking = static_cast<size_t>(backtracking);
                    best_shift = total_shift;
                    failure = rigid_compose_rotation(
                        rotation_step, total_rotation, &best_rotation);
                    if (failure !=
                        BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE) {
                        return failure;
                    }
                    best_rotation_path = total_rotation_path + angle;
                    rigid_copy_coordinates(
                        context.ligand_count,
                        scratch.trial_x,
                        scratch.trial_y,
                        scratch.trial_z,
                        scratch.best_x,
                        scratch.best_y,
                        scratch.best_z);
                }
                angle *= 0.5;
            }
        }
        if (!has_best || best_penalty > penalty - reduction) {
            break;
        }
        rigid_copy_coordinates(
            context.ligand_count,
            scratch.best_x,
            scratch.best_y,
            scratch.best_z,
            scratch.current_x,
            scratch.current_y,
            scratch.current_z);
        total_shift = best_shift;
        total_rotation = best_rotation;
        total_rotation_path = best_rotation_path;
        ++accepted_steps;
        accepted_rotation_steps +=
            static_cast<uint64_t>(best_direction == 2);
        fallback_count += static_cast<uint64_t>(best_direction == 1);
    }
    double final_penalty = 0.0;
    failure = rigid_penalty_direction(
        context,
        scratch.current_x,
        scratch.current_y,
        scratch.current_z,
        config.v2,
        &final_penalty,
        &unused_direction);
    if (failure != BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE) {
        return failure;
    }
    const double final_centroid_offset = rigid_norm(rigid_minus(
        rigid_centroid(
            context.ligand_count,
            scratch.current_x,
            scratch.current_y,
            scratch.current_z),
        {context.pocket_center[0],
         context.pocket_center[1],
         context.pocket_center[2]}));
    RigidVector3 total_rotation_vector{};
    failure = rigid_rotation_vector(total_rotation, &total_rotation_vector);
    if (failure != BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE) {
        return failure;
    }
    rigid_copy_coordinates(
        context.ligand_count,
        scratch.current_x,
        scratch.current_y,
        scratch.current_z,
        output_x,
        output_y,
        output_z);
    *evidence = rigid_empty_evidence();
    evidence->profile = profile;
    evidence->available = UINT8_C(1);
    evidence->accepted_steps = accepted_steps;
    evidence->accepted_translation_steps =
        accepted_steps - accepted_rotation_steps;
    evidence->accepted_rotation_steps = accepted_rotation_steps;
    evidence->line_search_evaluation_count = evaluation_count;
    evidence->fallback_direction_step_count = fallback_count;
    evidence->initial_penalty = initial_penalty;
    evidence->final_penalty = final_penalty;
    evidence->total_translation_angstrom[0] =
        rigid_canonical_zero(total_shift.x);
    evidence->total_translation_angstrom[1] =
        rigid_canonical_zero(total_shift.y);
    evidence->total_translation_angstrom[2] =
        rigid_canonical_zero(total_shift.z);
    evidence->total_rotation_vector_radians[0] =
        rigid_canonical_zero(total_rotation_vector.x);
    evidence->total_rotation_vector_radians[1] =
        rigid_canonical_zero(total_rotation_vector.y);
    evidence->total_rotation_vector_radians[2] =
        rigid_canonical_zero(total_rotation_vector.z);
    evidence->total_rotation_path_radians =
        rigid_canonical_zero(total_rotation_path);
    evidence->initial_centroid_offset_angstrom = initial_centroid_offset;
    evidence->final_centroid_offset_angstrom = final_centroid_offset;
    evidence->maximum_centroid_offset_angstrom = maximum_centroid_offset;
    return BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE;
}

__device__ bool rigid_coordinates_bit_equal(
    size_t count,
    const double *left_x,
    const double *left_y,
    const double *left_z,
    const double *right_x,
    const double *right_y,
    const double *right_z) {
    for (size_t atom = 0; atom < count; ++atom) {
        if (__double_as_longlong(left_x[atom]) !=
                __double_as_longlong(right_x[atom]) ||
            __double_as_longlong(left_y[atom]) !=
                __double_as_longlong(right_y[atom]) ||
            __double_as_longlong(left_z[atom]) !=
                __double_as_longlong(right_z[atom])) {
            return false;
        }
    }
    return true;
}

__device__ void rigid_clear_slot_outputs(
    size_t ligand_count,
    RigidDeviceOutputs outputs,
    size_t offset) {
    rigid_zero_coordinates(
        ligand_count,
        outputs.selected_x + offset,
        outputs.selected_y + offset,
        outputs.selected_z + offset);
    rigid_zero_coordinates(
        ligand_count,
        outputs.comparison_x + offset,
        outputs.comparison_y + offset,
        outputs.comparison_z + offset);
    rigid_zero_coordinates(
        ligand_count,
        outputs.baseline_x + offset,
        outputs.baseline_y + offset,
        outputs.baseline_z + offset);
    rigid_zero_coordinates(
        ligand_count,
        outputs.clearance_x + offset,
        outputs.clearance_y + offset,
        outputs.clearance_z + offset);
}

__device__ bg_docking_rigid_refinement_row_v1 rigid_failure_row(
    size_t slot,
    int32_t mode,
    int32_t failure) {
    bg_docking_rigid_refinement_row_v1 row{};
    row.slot_index = static_cast<uint32_t>(slot);
    row.status = BG_DOCKING_RIGID_REFINEMENT_ROW_TYPED_FAILURE;
    row.failure_code = failure;
    row.candidate_mode = mode;
    return row;
}

__global__ void rigid_refinement_kernel(
    RigidDeviceContext context,
    RigidDeviceBatch batch,
    RigidDeviceOutputs outputs,
    RigidScratch scratch) {
    const size_t slot = blockIdx.x;
    if (slot >= kRigidCandidateCount || threadIdx.x != 0) {
        return;
    }
    const size_t coordinate_offset = slot * context.ligand_count;
    RigidScratch local_scratch{
        scratch.current_x + coordinate_offset,
        scratch.current_y + coordinate_offset,
        scratch.current_z + coordinate_offset,
        scratch.trial_x + coordinate_offset,
        scratch.trial_y + coordinate_offset,
        scratch.trial_z + coordinate_offset,
        scratch.best_x + coordinate_offset,
        scratch.best_y + coordinate_offset,
        scratch.best_z + coordinate_offset,
    };
    const int32_t mode = batch.mode[slot];
    rigid_clear_slot_outputs(context.ligand_count, outputs, coordinate_offset);
    outputs.rows[slot] = rigid_failure_row(
        slot,
        mode,
        BG_DOCKING_RIGID_REFINEMENT_FAILURE_UPSTREAM_NOT_ELIGIBLE);
    if (mode == BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_INACTIVE) {
        return;
    }
    if (mode < BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION ||
        mode >
            BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V3_LANE ||
        batch.max_steps[slot] < UINT64_C(1) ||
        batch.max_steps[slot] > kRigidMaxSteps) {
        outputs.rows[slot] = rigid_failure_row(
            slot,
            mode,
            BG_DOCKING_RIGID_REFINEMENT_FAILURE_INVALID_INPUT);
        return;
    }
    for (size_t atom = 0; atom < context.ligand_count; ++atom) {
        const size_t index = coordinate_offset + atom;
        if (!isfinite(batch.x[index]) || !isfinite(batch.y[index]) ||
            !isfinite(batch.z[index])) {
            outputs.rows[slot] = rigid_failure_row(
                slot,
                mode,
                BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONFINITE_INPUT);
            return;
        }
    }
    const double *const source_x = batch.x + coordinate_offset;
    const double *const source_y = batch.y + coordinate_offset;
    const double *const source_z = batch.z + coordinate_offset;
    bg_docking_rigid_refinement_row_v1 row{};
    row.slot_index = static_cast<uint32_t>(slot);
    row.status = BG_DOCKING_RIGID_REFINEMENT_ROW_REFINED;
    row.failure_code = BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE;
    row.candidate_mode = mode;
    int32_t failure = BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE;
    if (mode == BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION) {
        failure = rigid_refine_v2(
            context,
            source_x,
            source_y,
            source_z,
            batch.max_steps[slot],
            context.v2,
            BG_DOCKING_RIGID_REFINEMENT_PROFILE_V2_TRANSLATION,
            local_scratch,
            outputs.selected_x + coordinate_offset,
            outputs.selected_y + coordinate_offset,
            outputs.selected_z + coordinate_offset,
            &row.selected);
    } else if (
        mode ==
        BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V3_TRANSLATION_ROTATION) {
        failure = rigid_refine_v3(
            context,
            source_x,
            source_y,
            source_z,
            batch.max_steps[slot],
            context.v3,
            BG_DOCKING_RIGID_REFINEMENT_PROFILE_V3_TRANSLATION_ROTATION,
            local_scratch,
            outputs.selected_x + coordinate_offset,
            outputs.selected_y + coordinate_offset,
            outputs.selected_z + coordinate_offset,
            &row.selected);
    } else if (
        mode ==
        BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V2_LANE) {
        failure = rigid_refine_v2(
            context,
            source_x,
            source_y,
            source_z,
            batch.max_steps[slot],
            context.v2,
            BG_DOCKING_RIGID_REFINEMENT_PROFILE_V6_BASELINE_V2,
            local_scratch,
            outputs.selected_x + coordinate_offset,
            outputs.selected_y + coordinate_offset,
            outputs.selected_z + coordinate_offset,
            &row.selected);
    } else {
        failure = rigid_refine_v2(
            context,
            source_x,
            source_y,
            source_z,
            batch.max_steps[slot],
            context.v2,
            BG_DOCKING_RIGID_REFINEMENT_PROFILE_V2_TRANSLATION,
            local_scratch,
            outputs.comparison_x + coordinate_offset,
            outputs.comparison_y + coordinate_offset,
            outputs.comparison_z + coordinate_offset,
            &row.comparison_v2);
        if (failure == BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE) {
            failure = rigid_refine_v3(
                context,
                source_x,
                source_y,
                source_z,
                batch.max_steps[slot],
                context.v3,
                BG_DOCKING_RIGID_REFINEMENT_PROFILE_V6_BASELINE_V3,
                local_scratch,
                outputs.baseline_x + coordinate_offset,
                outputs.baseline_y + coordinate_offset,
                outputs.baseline_z + coordinate_offset,
                &row.baseline_v3);
        }
        if (failure == BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE) {
            row.baseline_duplicate_of_v2 = static_cast<uint8_t>(
                rigid_coordinates_bit_equal(
                    context.ligand_count,
                    outputs.comparison_x + coordinate_offset,
                    outputs.comparison_y + coordinate_offset,
                    outputs.comparison_z + coordinate_offset,
                    outputs.baseline_x + coordinate_offset,
                    outputs.baseline_y + coordinate_offset,
                    outputs.baseline_z + coordinate_offset));
            row.clearance_evaluated = static_cast<uint8_t>(
                row.baseline_duplicate_of_v2 != 0 ||
                row.baseline_v3.final_penalty <= kRigidNearClearPenalty);
        }
        if (failure == BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE &&
            row.clearance_evaluated != 0) {
            failure = rigid_refine_v3(
                context,
                source_x,
                source_y,
                source_z,
                batch.max_steps[slot],
                context.clearance_v4,
                BG_DOCKING_RIGID_REFINEMENT_PROFILE_V6_CLEARANCE_V4,
                local_scratch,
                outputs.clearance_x + coordinate_offset,
                outputs.clearance_y + coordinate_offset,
                outputs.clearance_z + coordinate_offset,
                &row.clearance_v4);
            if (failure == BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE) {
                row.clearance_selected = static_cast<uint8_t>(
                    row.baseline_duplicate_of_v2 != 0 ||
                    row.clearance_v4.final_penalty <
                        row.clearance_v4.initial_penalty);
            }
        }
        if (failure == BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE) {
            if (row.clearance_selected != 0) {
                row.selected = row.clearance_v4;
                rigid_copy_coordinates(
                    context.ligand_count,
                    outputs.clearance_x + coordinate_offset,
                    outputs.clearance_y + coordinate_offset,
                    outputs.clearance_z + coordinate_offset,
                    outputs.selected_x + coordinate_offset,
                    outputs.selected_y + coordinate_offset,
                    outputs.selected_z + coordinate_offset);
            } else {
                row.selected = row.baseline_v3;
                rigid_copy_coordinates(
                    context.ligand_count,
                    outputs.baseline_x + coordinate_offset,
                    outputs.baseline_y + coordinate_offset,
                    outputs.baseline_z + coordinate_offset,
                    outputs.selected_x + coordinate_offset,
                    outputs.selected_y + coordinate_offset,
                    outputs.selected_z + coordinate_offset);
            }
        }
    }
    if (failure != BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE) {
        rigid_clear_slot_outputs(context.ligand_count, outputs, coordinate_offset);
        outputs.rows[slot] = rigid_failure_row(slot, mode, failure);
        return;
    }
    row.selected_profile = row.selected.profile;
    outputs.rows[slot] = row;
}

RigidV2Config rigid_v2_config(
    const bg_docking_rigid_v2_config_v1 &source) noexcept {
    return {
        source.overlap_scale,
        source.maximum_step_angstrom,
        source.minimum_step_angstrom,
        source.maximum_total_translation_angstrom,
        source.maximum_backtracking_evaluations,
        source.penalty_tolerance,
        source.epsilon_angstrom,
    };
}

RigidV3Config rigid_v3_config(
    const bg_docking_rigid_v3_config_v1 &source) noexcept {
    return {
        rigid_v2_config(source.v2),
        source.maximum_rotation_step_radians,
        source.minimum_rotation_step_radians,
        source.maximum_total_rotation_radians,
        source.maximum_rotation_steps,
        source.minimum_rotation_relative_penalty_reduction,
        source.maximum_centroid_offset_angstrom,
    };
}

bool rigid_v2_valid(const bg_docking_rigid_v2_config_v1 &value) noexcept {
    return rigid_reserved_is_zero(value.reserved) &&
           std::isfinite(value.overlap_scale) && value.overlap_scale >= 0.55 &&
           value.overlap_scale <= 1.0 &&
           std::isfinite(value.maximum_step_angstrom) &&
           value.maximum_step_angstrom > 0.0 &&
           std::isfinite(value.minimum_step_angstrom) &&
           value.minimum_step_angstrom > 0.0 &&
           value.minimum_step_angstrom <= value.maximum_step_angstrom &&
           std::isfinite(value.maximum_total_translation_angstrom) &&
           value.maximum_total_translation_angstrom >=
               value.maximum_step_angstrom &&
           value.maximum_backtracking_evaluations >= UINT64_C(1) &&
           value.maximum_backtracking_evaluations <= UINT64_C(16) &&
           std::isfinite(value.penalty_tolerance) &&
           value.penalty_tolerance > 0.0 &&
           std::isfinite(value.epsilon_angstrom) &&
           value.epsilon_angstrom > 0.0;
}

bool rigid_v3_valid(const bg_docking_rigid_v3_config_v1 &value) noexcept {
    return rigid_v2_valid(value.v2) && rigid_reserved_is_zero(value.reserved) &&
           std::isfinite(value.maximum_rotation_step_radians) &&
           value.maximum_rotation_step_radians > 0.0 &&
           std::isfinite(value.minimum_rotation_step_radians) &&
           value.minimum_rotation_step_radians > 0.0 &&
           value.minimum_rotation_step_radians <=
               value.maximum_rotation_step_radians &&
           std::isfinite(value.maximum_total_rotation_radians) &&
           value.maximum_total_rotation_radians >=
               value.maximum_rotation_step_radians &&
           value.maximum_rotation_steps >= UINT64_C(1) &&
           value.maximum_rotation_steps <= UINT64_C(8) &&
           std::isfinite(value.minimum_rotation_relative_penalty_reduction) &&
           value.minimum_rotation_relative_penalty_reduction > 0.0 &&
           value.minimum_rotation_relative_penalty_reduction <= 0.25 &&
           std::isfinite(value.maximum_centroid_offset_angstrom) &&
           value.maximum_centroid_offset_angstrom >= 0.5 &&
           value.maximum_centroid_offset_angstrom <= 8.0;
}

}  // namespace

extern "C" int32_t BG_DOCKING_RIGID_CREATE(
    int32_t device_ordinal,
    const bg_docking_rigid_refinement_context_soa_v1 *descriptor,
    void **out_state,
    char *error_message,
    size_t error_capacity) {
    rigid_clear_error(error_message, error_capacity);
    if (descriptor == nullptr || out_state == nullptr) {
        return rigid_fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            "HIP rigid create pointer is null");
    }
    *out_state = nullptr;
    if (descriptor->struct_size != sizeof(*descriptor) ||
        descriptor->abi_version != BG_ABI_VERSION) {
        return rigid_fail(
            BG_STATUS_ABI_MISMATCH,
            error_message,
            error_capacity,
            "HIP rigid context ABI mismatch");
    }
    if (descriptor->unit_system != BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL ||
        descriptor->reserved0 != 0 ||
        !rigid_reserved_is_zero(descriptor->reserved) ||
        descriptor->receptor_atom_count == 0 ||
        descriptor->receptor_atom_count > kRigidMaxReceptorAtoms ||
        descriptor->ligand_atom_count == 0 ||
        descriptor->ligand_atom_count > kRigidMaxLigandAtoms ||
        descriptor->receptor_atom_count >
            kRigidMaxPairEvaluations / descriptor->ligand_atom_count ||
        !rigid_pointer_valid(
            descriptor->receptor_x_angstrom,
            static_cast<size_t>(descriptor->receptor_atom_count)) ||
        !rigid_pointer_valid(
            descriptor->receptor_y_angstrom,
            static_cast<size_t>(descriptor->receptor_atom_count)) ||
        !rigid_pointer_valid(
            descriptor->receptor_z_angstrom,
            static_cast<size_t>(descriptor->receptor_atom_count)) ||
        !rigid_pointer_valid(
            descriptor->receptor_vdw_radius_angstrom,
            static_cast<size_t>(descriptor->receptor_atom_count)) ||
        !rigid_pointer_valid(
            descriptor->ligand_vdw_radius_angstrom,
            static_cast<size_t>(descriptor->ligand_atom_count)) ||
        !std::isfinite(descriptor->pocket_center_angstrom[0]) ||
        !std::isfinite(descriptor->pocket_center_angstrom[1]) ||
        !std::isfinite(descriptor->pocket_center_angstrom[2]) ||
        !std::isfinite(descriptor->pocket_radius_angstrom) ||
        descriptor->pocket_radius_angstrom <= 0.0 ||
        !rigid_v2_valid(descriptor->v2) ||
        !rigid_v3_valid(descriptor->v3) ||
        !rigid_v3_valid(descriptor->clearance_v4)) {
        return rigid_fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            "HIP rigid context is invalid");
    }
    const size_t receptor_count =
        static_cast<size_t>(descriptor->receptor_atom_count);
    const size_t ligand_count =
        static_cast<size_t>(descriptor->ligand_atom_count);
    for (size_t index = 0; index < receptor_count; ++index) {
        if (!std::isfinite(descriptor->receptor_x_angstrom[index]) ||
            !std::isfinite(descriptor->receptor_y_angstrom[index]) ||
            !std::isfinite(descriptor->receptor_z_angstrom[index]) ||
            !std::isfinite(descriptor->receptor_vdw_radius_angstrom[index]) ||
            descriptor->receptor_vdw_radius_angstrom[index] <= 0.0) {
            return rigid_fail(
                BG_STATUS_INVALID_ARGUMENT,
                error_message,
                error_capacity,
                "HIP rigid receptor context is non-finite");
        }
    }
    for (size_t index = 0; index < ligand_count; ++index) {
        if (!std::isfinite(descriptor->ligand_vdw_radius_angstrom[index]) ||
            descriptor->ligand_vdw_radius_angstrom[index] <= 0.0) {
            return rigid_fail(
                BG_STATUS_INVALID_ARGUMENT,
                error_message,
                error_capacity,
                "HIP rigid ligand context is non-finite");
        }
    }
    RigidDeviceGuard guard;
    hipError_t status = hipSetDevice(device_ordinal);
    if (status != hipSuccess) {
        return rigid_fail_hip(
            status, error_message, error_capacity, "device selection");
    }
    std::unique_ptr<RigidState> state(new (std::nothrow) RigidState());
    if (state == nullptr) {
        return rigid_fail(
            BG_STATUS_OUT_OF_MEMORY,
            error_message,
            error_capacity,
            "HIP rigid host state allocation failed");
    }
    state->device_ordinal = device_ordinal;
    state->receptor_count = receptor_count;
    state->ligand_count = ligand_count;
    std::copy_n(
        descriptor->pocket_center_angstrom, 3, state->pocket_center);
    state->pocket_radius = descriptor->pocket_radius_angstrom;
    state->v2 = rigid_v2_config(descriptor->v2);
    state->v3 = rigid_v3_config(descriptor->v3);
    state->clearance_v4 = rigid_v3_config(descriptor->clearance_v4);
#define BG_RIGID_COPY_CONTEXT(target, source, count, operation)              \
    do {                                                                     \
        status = (target).copy_from((source), (count));                      \
        if (status != hipSuccess) {                                          \
            return rigid_fail_hip(                                           \
                status, error_message, error_capacity, (operation));        \
        }                                                                    \
    } while (false)
    BG_RIGID_COPY_CONTEXT(
        state->receptor_x,
        descriptor->receptor_x_angstrom,
        receptor_count,
        "receptor x copy");
    BG_RIGID_COPY_CONTEXT(
        state->receptor_y,
        descriptor->receptor_y_angstrom,
        receptor_count,
        "receptor y copy");
    BG_RIGID_COPY_CONTEXT(
        state->receptor_z,
        descriptor->receptor_z_angstrom,
        receptor_count,
        "receptor z copy");
    BG_RIGID_COPY_CONTEXT(
        state->receptor_radii,
        descriptor->receptor_vdw_radius_angstrom,
        receptor_count,
        "receptor radius copy");
    BG_RIGID_COPY_CONTEXT(
        state->ligand_radii,
        descriptor->ligand_vdw_radius_angstrom,
        ligand_count,
        "ligand radius copy");
#undef BG_RIGID_COPY_CONTEXT
    *out_state = state.release();
    return BG_STATUS_OK;
}

extern "C" void BG_DOCKING_RIGID_DESTROY(void *opaque_state) {
    delete static_cast<RigidState *>(opaque_state);
}

extern "C" int32_t BG_DOCKING_RIGID_REFINE_FIXED64(
    const void *opaque_state,
    const bg_docking_rigid_refinement_candidate_batch_soa_v1 *candidates,
    bg_docking_rigid_refinement_row_v1 *out_rows,
    double *out_selected_x,
    double *out_selected_y,
    double *out_selected_z,
    double *out_comparison_v2_x,
    double *out_comparison_v2_y,
    double *out_comparison_v2_z,
    double *out_baseline_v3_x,
    double *out_baseline_v3_y,
    double *out_baseline_v3_z,
    double *out_clearance_v4_x,
    double *out_clearance_v4_y,
    double *out_clearance_v4_z,
    char *error_message,
    size_t error_capacity) {
    rigid_clear_error(error_message, error_capacity);
    if (opaque_state == nullptr || candidates == nullptr) {
        return rigid_fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            "HIP rigid batch state or descriptor is null");
    }
    const auto *state = static_cast<const RigidState *>(opaque_state);
    if (candidates->struct_size != sizeof(*candidates) ||
        candidates->abi_version != BG_ABI_VERSION) {
        return rigid_fail(
            BG_STATUS_ABI_MISMATCH,
            error_message,
            error_capacity,
            "HIP rigid batch ABI mismatch");
    }
    const size_t coordinate_count =
        kRigidCandidateCount * state->ligand_count;
    const bool valid =
        candidates->candidate_count == kRigidCandidateCount &&
        candidates->ligand_atom_count == state->ligand_count &&
        candidates->unit_system == BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL &&
        candidates->reserved0 == 0 &&
        rigid_reserved_is_zero(candidates->reserved) &&
        rigid_pointer_valid(candidates->candidate_mode, kRigidCandidateCount) &&
        rigid_pointer_valid(candidates->max_steps, kRigidCandidateCount) &&
        rigid_pointer_valid(candidates->x_angstrom, coordinate_count) &&
        rigid_pointer_valid(candidates->y_angstrom, coordinate_count) &&
        rigid_pointer_valid(candidates->z_angstrom, coordinate_count) &&
        rigid_pointer_valid(out_rows, kRigidCandidateCount) &&
        rigid_pointer_valid(out_selected_x, coordinate_count) &&
        rigid_pointer_valid(out_selected_y, coordinate_count) &&
        rigid_pointer_valid(out_selected_z, coordinate_count) &&
        rigid_pointer_valid(out_comparison_v2_x, coordinate_count) &&
        rigid_pointer_valid(out_comparison_v2_y, coordinate_count) &&
        rigid_pointer_valid(out_comparison_v2_z, coordinate_count) &&
        rigid_pointer_valid(out_baseline_v3_x, coordinate_count) &&
        rigid_pointer_valid(out_baseline_v3_y, coordinate_count) &&
        rigid_pointer_valid(out_baseline_v3_z, coordinate_count) &&
        rigid_pointer_valid(out_clearance_v4_x, coordinate_count) &&
        rigid_pointer_valid(out_clearance_v4_y, coordinate_count) &&
        rigid_pointer_valid(out_clearance_v4_z, coordinate_count);
    if (!valid) {
        return rigid_fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            "HIP rigid batch identity or output channel is invalid");
    }
    RigidDeviceGuard guard;
    hipError_t status = hipSetDevice(state->device_ordinal);
    if (status != hipSuccess) {
        return rigid_fail_hip(
            status, error_message, error_capacity, "device selection");
    }
    RigidDeviceBuffer<int32_t> device_mode;
    RigidDeviceBuffer<uint64_t> device_steps;
    RigidDeviceBuffer<double> device_x;
    RigidDeviceBuffer<double> device_y;
    RigidDeviceBuffer<double> device_z;
    RigidDeviceBuffer<bg_docking_rigid_refinement_row_v1> device_rows;
    std::array<RigidDeviceBuffer<double>, 21> coordinate_buffers;
#define BG_RIGID_COPY_BATCH(target, source, count, operation)                \
    do {                                                                     \
        status = (target).copy_from((source), (count));                      \
        if (status != hipSuccess) {                                          \
            return rigid_fail_hip(                                           \
                status, error_message, error_capacity, (operation));        \
        }                                                                    \
    } while (false)
    BG_RIGID_COPY_BATCH(
        device_mode,
        candidates->candidate_mode,
        kRigidCandidateCount,
        "mode copy");
    BG_RIGID_COPY_BATCH(
        device_steps,
        candidates->max_steps,
        kRigidCandidateCount,
        "step copy");
    BG_RIGID_COPY_BATCH(
        device_x, candidates->x_angstrom, coordinate_count, "x copy");
    BG_RIGID_COPY_BATCH(
        device_y, candidates->y_angstrom, coordinate_count, "y copy");
    BG_RIGID_COPY_BATCH(
        device_z, candidates->z_angstrom, coordinate_count, "z copy");
#undef BG_RIGID_COPY_BATCH
    status = device_rows.allocate(kRigidCandidateCount);
    if (status != hipSuccess) {
        return rigid_fail_hip(
            status, error_message, error_capacity, "row allocation");
    }
    for (auto &buffer : coordinate_buffers) {
        status = buffer.allocate(coordinate_count);
        if (status != hipSuccess) {
            return rigid_fail_hip(
                status,
                error_message,
                error_capacity,
                "coordinate or scratch allocation");
        }
    }
    RigidDeviceOutputs outputs{
        device_rows.get(),
        coordinate_buffers[0].get(),
        coordinate_buffers[1].get(),
        coordinate_buffers[2].get(),
        coordinate_buffers[3].get(),
        coordinate_buffers[4].get(),
        coordinate_buffers[5].get(),
        coordinate_buffers[6].get(),
        coordinate_buffers[7].get(),
        coordinate_buffers[8].get(),
        coordinate_buffers[9].get(),
        coordinate_buffers[10].get(),
        coordinate_buffers[11].get(),
    };
    RigidScratch scratch{
        coordinate_buffers[12].get(),
        coordinate_buffers[13].get(),
        coordinate_buffers[14].get(),
        coordinate_buffers[15].get(),
        coordinate_buffers[16].get(),
        coordinate_buffers[17].get(),
        coordinate_buffers[18].get(),
        coordinate_buffers[19].get(),
        coordinate_buffers[20].get(),
    };
    const RigidDeviceBatch batch{
        device_mode.get(),
        device_steps.get(),
        device_x.get(),
        device_y.get(),
        device_z.get(),
    };
    hipLaunchKernelGGL(
        rigid_refinement_kernel,
        dim3(static_cast<uint32_t>(kRigidCandidateCount)),
        dim3(1),
        0,
        0,
        state->device_context(),
        batch,
        outputs,
        scratch);
    status = hipGetLastError();
    if (status == hipSuccess) {
        status = hipDeviceSynchronize();
    }
    if (status != hipSuccess) {
        return rigid_fail_hip(
            status, error_message, error_capacity, "kernel execution");
    }
    std::unique_ptr<bg_docking_rigid_refinement_row_v1[]> host_rows(
        new (std::nothrow)
            bg_docking_rigid_refinement_row_v1[kRigidCandidateCount]);
    std::array<std::unique_ptr<double[]>, 12> host_coordinates;
    if (host_rows == nullptr) {
        return rigid_fail(
            BG_STATUS_OUT_OF_MEMORY,
            error_message,
            error_capacity,
            "HIP rigid host row allocation failed");
    }
    for (auto &coordinates : host_coordinates) {
        coordinates.reset(new (std::nothrow) double[coordinate_count]);
        if (coordinates == nullptr) {
            return rigid_fail(
                BG_STATUS_OUT_OF_MEMORY,
                error_message,
                error_capacity,
                "HIP rigid host coordinate allocation failed");
        }
    }
    status = device_rows.copy_to(host_rows.get(), kRigidCandidateCount);
    for (size_t index = 0; index < host_coordinates.size() &&
                           status == hipSuccess;
         ++index) {
        status = coordinate_buffers[index].copy_to(
            host_coordinates[index].get(), coordinate_count);
    }
    if (status != hipSuccess) {
        return rigid_fail_hip(
            status, error_message, error_capacity, "result copy");
    }
    std::memcpy(
        out_rows,
        host_rows.get(),
        kRigidCandidateCount * sizeof(*out_rows));
    std::array<double *, 12> destinations = {
        out_selected_x,
        out_selected_y,
        out_selected_z,
        out_comparison_v2_x,
        out_comparison_v2_y,
        out_comparison_v2_z,
        out_baseline_v3_x,
        out_baseline_v3_y,
        out_baseline_v3_z,
        out_clearance_v4_x,
        out_clearance_v4_y,
        out_clearance_v4_z,
    };
    for (size_t index = 0; index < destinations.size(); ++index) {
        std::memcpy(
            destinations[index],
            host_coordinates[index].get(),
            coordinate_count * sizeof(double));
    }
    return BG_STATUS_OK;
}
