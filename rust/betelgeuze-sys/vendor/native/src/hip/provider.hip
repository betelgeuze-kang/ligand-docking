#include "provider.h"

#include <hip/hip_runtime.h>

#include <cmath>
#include <cstdio>
#include <cstring>
#include <limits>
#include <memory>
#include <new>
#include <type_traits>

#ifndef BG_HIP_SAFE_QUALIFIED_ARCHITECTURES
#  error "hip_safe requires an explicit qualified architecture set"
#endif

static_assert(
    HIP_VERSION == 60032831,
    "hip_safe is qualified only for the reviewed HIP 6.0.32831 toolchain");

namespace {

constexpr double kCoulombConstant =
    BG_COULOMB_CONSTANT_KCAL_ANGSTROM_PER_MOL_E2;
constexpr double kDegenerateSquaredAngstrom2 = 1.0e-24;
constexpr double kAngleCosineMargin = 1.0e-12;

enum DeviceFailure : int32_t {
    kDeviceSuccess = 0,
    kDeviceBondZeroLength = 1,
    kDeviceAngleDegenerate = 2,
    kDeviceTorsionDegenerate = 3,
    kDeviceMinimumPairDistance = 4,
    kDeviceNonFinite = 5,
    kDeviceInternal = 100,
};

void clear_error(char *message, size_t capacity) noexcept {
    if (message != nullptr && capacity > 0) {
        message[0] = '\0';
    }
}

int32_t fail(
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

int32_t fail_hip(
    hipError_t error,
    char *message,
    size_t capacity,
    const char *operation) noexcept {
    const int32_t status = error == hipErrorOutOfMemory
                               ? BG_STATUS_OUT_OF_MEMORY
                               : BG_STATUS_BACKEND_ERROR;
    if (message != nullptr && capacity > 0) {
        std::snprintf(
            message,
            capacity,
            "hip_safe %s failed: %s",
            operation,
            hipGetErrorString(error));
        message[capacity - 1] = '\0';
    }
    return status;
}

template <typename Descriptor>
bool valid_header(const Descriptor &descriptor) noexcept {
    return descriptor.struct_size == sizeof(Descriptor) &&
           descriptor.abi_version == BG_HIP_SAFE_PROVIDER_ABI_VERSION;
}

template <size_t Count>
bool reserved_is_zero(const uint64_t (&values)[Count]) noexcept {
    for (uint64_t value : values) {
        if (value != UINT64_C(0)) {
            return false;
        }
    }
    return true;
}

template <typename Value>
bool counted_pointer_is_valid(const Value *pointer, size_t count) noexcept {
    return count == 0 || pointer != nullptr;
}

bool ranges_overlap(
    const double *left,
    const double *right,
    size_t count) noexcept {
    if (count == 0 || left == nullptr || right == nullptr) {
        return false;
    }
    if (count > std::numeric_limits<size_t>::max() / sizeof(double)) {
        return true;
    }
    const uintptr_t bytes = count * sizeof(double);
    const uintptr_t left_begin = reinterpret_cast<uintptr_t>(left);
    const uintptr_t right_begin = reinterpret_cast<uintptr_t>(right);
    if (left_begin > std::numeric_limits<uintptr_t>::max() - bytes ||
        right_begin > std::numeric_limits<uintptr_t>::max() - bytes) {
        return true;
    }
    return left_begin < right_begin + bytes && right_begin < left_begin + bytes;
}

bool architecture_is_qualified(const char *observed) noexcept {
    if (observed == nullptr || observed[0] == '\0') {
        return false;
    }
    size_t observed_length = 0;
    while (observed[observed_length] != '\0' &&
           observed[observed_length] != ':') {
        ++observed_length;
    }
    const char *qualified = BG_HIP_SAFE_QUALIFIED_ARCHITECTURES;
    while (*qualified != '\0') {
        const char *token_begin = qualified;
        while (*qualified != '\0' && *qualified != ',') {
            ++qualified;
        }
        const size_t token_length =
            static_cast<size_t>(qualified - token_begin);
        if (token_length == observed_length &&
            std::strncmp(token_begin, observed, observed_length) == 0) {
            return true;
        }
        if (*qualified == ',') {
            ++qualified;
        }
    }
    return false;
}

template <typename Value>
class DeviceBuffer final {
public:
    DeviceBuffer() = default;
    DeviceBuffer(const DeviceBuffer &) = delete;
    DeviceBuffer &operator=(const DeviceBuffer &) = delete;

    ~DeviceBuffer() {
        if (pointer_ != nullptr) {
            static_cast<void>(hipFree(pointer_));
        }
    }

    hipError_t copy_from(const Value *source, size_t count) noexcept {
        if (count == 0) {
            return hipSuccess;
        }
        if (source == nullptr ||
            count > std::numeric_limits<size_t>::max() / sizeof(Value)) {
            return hipErrorInvalidValue;
        }
        const size_t bytes = count * sizeof(Value);
        hipError_t status = hipMalloc(reinterpret_cast<void **>(&pointer_), bytes);
        if (status != hipSuccess) {
            return status;
        }
        status = hipMemcpy(pointer_, source, bytes, hipMemcpyHostToDevice);
        return status;
    }

    hipError_t allocate(size_t count) noexcept {
        if (count == 0) {
            return hipSuccess;
        }
        if (count > std::numeric_limits<size_t>::max() / sizeof(Value)) {
            return hipErrorInvalidValue;
        }
        return hipMalloc(
            reinterpret_cast<void **>(&pointer_), count * sizeof(Value));
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

    Value *get() noexcept {
        return pointer_;
    }

    const Value *get() const noexcept {
        return pointer_;
    }

private:
    Value *pointer_ = nullptr;
};

class DeviceGuard final {
public:
    DeviceGuard() noexcept {
        if (hipGetDevice(&previous_) == hipSuccess) {
            has_previous_ = true;
        }
    }

    DeviceGuard(const DeviceGuard &) = delete;
    DeviceGuard &operator=(const DeviceGuard &) = delete;

    ~DeviceGuard() {
        if (has_previous_) {
            static_cast<void>(hipSetDevice(previous_));
        }
    }

private:
    int previous_ = 0;
    bool has_previous_ = false;
};

struct Vector3 {
    double x;
    double y;
    double z;
};

__device__ Vector3 scaled(Vector3 value, double factor) {
    return {value.x * factor, value.y * factor, value.z * factor};
}

__device__ Vector3 plus(Vector3 left, Vector3 right) {
    return {left.x + right.x, left.y + right.y, left.z + right.z};
}

__device__ Vector3 minus(Vector3 left, Vector3 right) {
    return {left.x - right.x, left.y - right.y, left.z - right.z};
}

__device__ double dot(Vector3 left, Vector3 right) {
    return left.x * right.x + left.y * right.y + left.z * right.z;
}

__device__ Vector3 cross(Vector3 left, Vector3 right) {
    return {
        left.y * right.z - left.z * right.y,
        left.z * right.x - left.x * right.z,
        left.x * right.y - left.y * right.x,
    };
}

__device__ bool finite_vector(Vector3 value) {
    return isfinite(value.x) && isfinite(value.y) && isfinite(value.z);
}

__device__ Vector3 displacement(
    const bg_hip_safe_system_v1 &system,
    const bg_hip_safe_forcefield_v1 &forcefield,
    size_t atom_i,
    size_t atom_j,
    int32_t *failure) {
    if (atom_i >= forcefield.atom_count || atom_j >= forcefield.atom_count) {
        *failure = kDeviceInternal;
        return {0.0, 0.0, 0.0};
    }
    Vector3 result{
        system.position_x[atom_i] - system.position_x[atom_j],
        system.position_y[atom_i] - system.position_y[atom_j],
        system.position_z[atom_i] - system.position_z[atom_j],
    };
    if ((forcefield.periodic_axes_mask & UINT32_C(1)) != 0) {
        const double length = forcefield.cell_lengths[0];
        result.x -= length * floor(result.x / length + 0.5);
    }
    if ((forcefield.periodic_axes_mask & UINT32_C(2)) != 0) {
        const double length = forcefield.cell_lengths[1];
        result.y -= length * floor(result.y / length + 0.5);
    }
    if ((forcefield.periodic_axes_mask & UINT32_C(4)) != 0) {
        const double length = forcefield.cell_lengths[2];
        result.z -= length * floor(result.z / length + 0.5);
    }
    const double squared = dot(result, result);
    if (!finite_vector(result) || !isfinite(squared)) {
        *failure = kDeviceNonFinite;
    }
    return result;
}

__device__ bool accumulate(double *target, double value) {
    const double updated = *target + value;
    if (!isfinite(value) || !isfinite(updated)) {
        return false;
    }
    *target = updated;
    return true;
}

__device__ bool accumulate_force(
    double *force_x,
    double *force_y,
    double *force_z,
    size_t atom,
    Vector3 value) {
    const double updated_x = force_x[atom] + value.x;
    const double updated_y = force_y[atom] + value.y;
    const double updated_z = force_z[atom] + value.z;
    if (!finite_vector(value) || !isfinite(updated_x) || !isfinite(updated_y) ||
        !isfinite(updated_z)) {
        return false;
    }
    force_x[atom] = updated_x;
    force_y[atom] = updated_y;
    force_z[atom] = updated_z;
    return true;
}

__device__ bool pair_is_excluded(
    const bg_hip_safe_forcefield_v1 &forcefield,
    size_t atom_i,
    size_t atom_j) {
    size_t begin = 0;
    size_t end = forcefield.exclusion_count;
    while (begin < end) {
        const size_t middle = begin + (end - begin) / 2;
        const bg_hip_safe_pair_v1 pair = forcefield.exclusions[middle];
        if (pair.atom_i < atom_i ||
            (pair.atom_i == atom_i && pair.atom_j < atom_j)) {
            begin = middle + 1;
        } else {
            end = middle;
        }
    }
    return begin < forcefield.exclusion_count &&
           forcefield.exclusions[begin].atom_i == atom_i &&
           forcefield.exclusions[begin].atom_j == atom_j;
}

__device__ void pair_scales(
    const bg_hip_safe_forcefield_v1 &forcefield,
    size_t atom_i,
    size_t atom_j,
    double *lennard_jones,
    double *coulomb) {
    *lennard_jones = 1.0;
    *coulomb = 1.0;
    size_t begin = 0;
    size_t end = forcefield.pair_scale_count;
    while (begin < end) {
        const size_t middle = begin + (end - begin) / 2;
        const bg_hip_safe_pair_scale_v1 scale = forcefield.pair_scales[middle];
        if (scale.atom_i < atom_i ||
            (scale.atom_i == atom_i && scale.atom_j < atom_j)) {
            begin = middle + 1;
        } else {
            end = middle;
        }
    }
    if (begin < forcefield.pair_scale_count &&
        forcefield.pair_scales[begin].atom_i == atom_i &&
        forcefield.pair_scales[begin].atom_j == atom_j) {
        *lennard_jones = forcefield.pair_scales[begin].lennard_jones;
        *coulomb = forcefield.pair_scales[begin].coulomb;
    }
}

struct SwitchValue {
    double value;
    double derivative;
};

__device__ SwitchValue switching_value(double distance, double start, double cutoff) {
    if (distance <= start) {
        return {1.0, 0.0};
    }
    if (distance >= cutoff) {
        return {0.0, 0.0};
    }
    const double width = cutoff - start;
    const double x = (distance - start) / width;
    const double x2 = x * x;
    const double x3 = x2 * x;
    const double x4 = x3 * x;
    const double x5 = x4 * x;
    return {
        1.0 - 10.0 * x3 + 15.0 * x4 - 6.0 * x5,
        (-30.0 * x2 + 60.0 * x3 - 30.0 * x4) / width,
    };
}

__global__ void evaluate_kernel(
    bg_hip_safe_system_v1 system,
    bg_hip_safe_forcefield_v1 forcefield,
    uint8_t compute_forces,
    bg_hip_safe_energy_v1 *out_energy,
    double *force_x,
    double *force_y,
    double *force_z,
    int32_t *out_failure) {
    if (blockIdx.x != 0 || threadIdx.x != 0) {
        return;
    }
    *out_failure = kDeviceSuccess;
    bg_hip_safe_energy_v1 energy{};
    energy.struct_size = sizeof(bg_hip_safe_energy_v1);
    energy.abi_version = BG_HIP_SAFE_PROVIDER_ABI_VERSION;
    if (compute_forces != 0) {
        for (size_t atom = 0; atom < forcefield.atom_count; ++atom) {
            force_x[atom] = 0.0;
            force_y[atom] = 0.0;
            force_z[atom] = 0.0;
        }
    }

    for (size_t row = 0; row < forcefield.bonds.count; ++row) {
        const size_t atom_i = forcefield.bonds.atom_i[row];
        const size_t atom_j = forcefield.bonds.atom_j[row];
        const Vector3 delta =
            displacement(system, forcefield, atom_i, atom_j, out_failure);
        if (*out_failure != kDeviceSuccess) {
            return;
        }
        const double squared_distance = dot(delta, delta);
        if (compute_forces != 0 && squared_distance <= 0.0) {
            *out_failure = kDeviceBondZeroLength;
            return;
        }
        const double distance = sqrt(squared_distance);
        const double difference = distance - forcefield.bonds.equilibrium[row];
        const double force_constant = forcefield.bonds.force_constant[row];
        const double row_energy = 0.5 * force_constant * difference * difference;
        if (!accumulate(&energy.harmonic_bond, row_energy)) {
            *out_failure = kDeviceNonFinite;
            return;
        }
        if (compute_forces != 0) {
            const Vector3 force =
                scaled(delta, -force_constant * difference / distance);
            if (!accumulate_force(
                    force_x, force_y, force_z, atom_i, force) ||
                !accumulate_force(
                    force_x, force_y, force_z, atom_j, scaled(force, -1.0))) {
                *out_failure = kDeviceNonFinite;
                return;
            }
        }
    }

    for (size_t row = 0; row < forcefield.angles.count; ++row) {
        const size_t atom_i = forcefield.angles.atom_i[row];
        const size_t atom_j = forcefield.angles.atom_j[row];
        const size_t atom_k = forcefield.angles.atom_k[row];
        const Vector3 first =
            displacement(system, forcefield, atom_i, atom_j, out_failure);
        const Vector3 second =
            displacement(system, forcefield, atom_k, atom_j, out_failure);
        if (*out_failure != kDeviceSuccess) {
            return;
        }
        const double first_squared = dot(first, first);
        const double second_squared = dot(second, second);
        if (first_squared <= kDegenerateSquaredAngstrom2 ||
            second_squared <= kDegenerateSquaredAngstrom2) {
            *out_failure = kDeviceAngleDegenerate;
            return;
        }
        const double first_length = sqrt(first_squared);
        const double second_length = sqrt(second_squared);
        const double raw_cosine =
            dot(first, second) / (first_length * second_length);
        if (!isfinite(raw_cosine)) {
            *out_failure = kDeviceNonFinite;
            return;
        }
        const double lower = -1.0 + kAngleCosineMargin;
        const double upper = 1.0 - kAngleCosineMargin;
        const double cosine = fmin(fmax(raw_cosine, lower), upper);
        const double angle = acos(cosine);
        const double difference = angle - forcefield.angles.equilibrium[row];
        const double force_constant = forcefield.angles.force_constant[row];
        const double row_energy = 0.5 * force_constant * difference * difference;
        if (!accumulate(&energy.harmonic_angle, row_energy)) {
            *out_failure = kDeviceNonFinite;
            return;
        }
        if (compute_forces == 0 || raw_cosine <= lower || raw_cosine >= upper) {
            continue;
        }
        const double sine = sqrt(1.0 - cosine * cosine);
        const Vector3 first_unit = scaled(first, 1.0 / first_length);
        const Vector3 second_unit = scaled(second, 1.0 / second_length);
        const double derivative = force_constant * difference;
        const Vector3 force_i = scaled(
            minus(second_unit, scaled(first_unit, cosine)),
            derivative / (first_length * sine));
        const Vector3 force_k = scaled(
            minus(first_unit, scaled(second_unit, cosine)),
            derivative / (second_length * sine));
        const Vector3 force_j = scaled(plus(force_i, force_k), -1.0);
        if (!accumulate_force(force_x, force_y, force_z, atom_i, force_i) ||
            !accumulate_force(force_x, force_y, force_z, atom_j, force_j) ||
            !accumulate_force(force_x, force_y, force_z, atom_k, force_k)) {
            *out_failure = kDeviceNonFinite;
            return;
        }
    }

    for (size_t row = 0; row < forcefield.torsions.count; ++row) {
        const size_t atom_i = forcefield.torsions.atom_i[row];
        const size_t atom_j = forcefield.torsions.atom_j[row];
        const size_t atom_k = forcefield.torsions.atom_k[row];
        const size_t atom_l = forcefield.torsions.atom_l[row];
        const Vector3 b0 =
            displacement(system, forcefield, atom_i, atom_j, out_failure);
        const Vector3 b1 =
            displacement(system, forcefield, atom_k, atom_j, out_failure);
        const Vector3 b2 =
            displacement(system, forcefield, atom_l, atom_k, out_failure);
        if (*out_failure != kDeviceSuccess) {
            return;
        }
        const double central_squared = dot(b1, b1);
        if (central_squared <= kDegenerateSquaredAngstrom2) {
            *out_failure = kDeviceTorsionDegenerate;
            return;
        }
        const double central_length = sqrt(central_squared);
        const Vector3 axis = scaled(b1, 1.0 / central_length);
        const Vector3 v = minus(b0, scaled(axis, dot(b0, axis)));
        const Vector3 w = minus(b2, scaled(axis, dot(b2, axis)));
        const double v_squared = dot(v, v);
        const double w_squared = dot(w, w);
        if (!finite_vector(axis) || !finite_vector(v) || !finite_vector(w) ||
            !isfinite(v_squared) || !isfinite(w_squared) ||
            v_squared <= kDegenerateSquaredAngstrom2 ||
            w_squared <= kDegenerateSquaredAngstrom2) {
            *out_failure = kDeviceTorsionDegenerate;
            return;
        }
        const double sine_numerator = dot(cross(axis, v), w);
        const double cosine_numerator = dot(v, w);
        const double phi = atan2(sine_numerator, cosine_numerator);
        const double periodicity =
            static_cast<double>(forcefield.torsions.periodicity[row]);
        const double argument =
            periodicity * phi - forcefield.torsions.phase[row];
        const double amplitude = forcefield.torsions.amplitude[row];
        const double row_energy = amplitude * (1.0 + cos(argument));
        if (!accumulate(&energy.periodic_torsion, row_energy)) {
            *out_failure = kDeviceNonFinite;
            return;
        }
        if (compute_forces == 0) {
            continue;
        }
        const Vector3 gradient_b0 =
            scaled(cross(axis, v), -1.0 / v_squared);
        const Vector3 gradient_b2 =
            scaled(cross(axis, w), 1.0 / w_squared);
        const Vector3 gradient_b1 = plus(
            scaled(gradient_b0, -dot(b0, b1) / central_squared),
            scaled(gradient_b2, -dot(b2, b1) / central_squared));
        const Vector3 gradient_i = gradient_b0;
        const Vector3 gradient_j = scaled(plus(gradient_b0, gradient_b1), -1.0);
        const Vector3 gradient_k = minus(gradient_b1, gradient_b2);
        const Vector3 gradient_l = gradient_b2;
        const double force_factor = amplitude * periodicity * sin(argument);
        if (!accumulate_force(
                force_x,
                force_y,
                force_z,
                atom_i,
                scaled(gradient_i, force_factor)) ||
            !accumulate_force(
                force_x,
                force_y,
                force_z,
                atom_j,
                scaled(gradient_j, force_factor)) ||
            !accumulate_force(
                force_x,
                force_y,
                force_z,
                atom_k,
                scaled(gradient_k, force_factor)) ||
            !accumulate_force(
                force_x,
                force_y,
                force_z,
                atom_l,
                scaled(gradient_l, force_factor))) {
            *out_failure = kDeviceNonFinite;
            return;
        }
    }

    for (size_t atom_i = 0; atom_i < forcefield.atom_count; ++atom_i) {
        for (size_t atom_j = atom_i + 1; atom_j < forcefield.atom_count; ++atom_j) {
            if (pair_is_excluded(forcefield, atom_i, atom_j)) {
                continue;
            }
            const Vector3 delta =
                displacement(system, forcefield, atom_i, atom_j, out_failure);
            if (*out_failure != kDeviceSuccess) {
                return;
            }
            const double distance = sqrt(dot(delta, delta));
            if (distance < forcefield.minimum_pair_distance) {
                *out_failure = kDeviceMinimumPairDistance;
                return;
            }
            if (distance > forcefield.cutoff) {
                continue;
            }
            double lennard_jones_scale = 1.0;
            double coulomb_scale = 1.0;
            pair_scales(
                forcefield,
                atom_i,
                atom_j,
                &lennard_jones_scale,
                &coulomb_scale);
            const double sigma =
                0.5 * (forcefield.sigma[atom_i] + forcefield.sigma[atom_j]);
            const double epsilon =
                sqrt(forcefield.epsilon[atom_i] * forcefield.epsilon[atom_j]);
            const double ratio = sigma / distance;
            const double ratio2 = ratio * ratio;
            const double ratio6 = ratio2 * ratio2 * ratio2;
            const double ratio12 = ratio6 * ratio6;
            const double lennard_jones =
                4.0 * epsilon * (ratio12 - ratio6) * lennard_jones_scale;
            const double screened_charge = system.charge[atom_i] *
                                           system.charge[atom_j] *
                                           exp(-forcefield.screening_kappa * distance);
            const double coulomb = kCoulombConstant * screened_charge /
                                   (forcefield.dielectric * distance) *
                                   coulomb_scale;
            const SwitchValue switching = switching_value(
                distance, forcefield.switch_start, forcefield.cutoff);
            if (!accumulate(
                    &energy.lennard_jones,
                    lennard_jones * switching.value) ||
                !accumulate(&energy.coulomb, coulomb * switching.value)) {
                *out_failure = kDeviceNonFinite;
                return;
            }
            if (compute_forces == 0) {
                continue;
            }
            const double lennard_jones_derivative =
                24.0 * epsilon * lennard_jones_scale *
                (ratio6 - 2.0 * ratio12) / distance;
            const double coulomb_derivative =
                coulomb * (-forcefield.screening_kappa - 1.0 / distance);
            const double radial_derivative =
                lennard_jones_derivative * switching.value +
                lennard_jones * switching.derivative +
                coulomb_derivative * switching.value +
                coulomb * switching.derivative;
            const Vector3 force = scaled(delta, -radial_derivative / distance);
            if (!accumulate_force(
                    force_x, force_y, force_z, atom_i, force) ||
                !accumulate_force(
                    force_x,
                    force_y,
                    force_z,
                    atom_j,
                    scaled(force, -1.0))) {
                *out_failure = kDeviceNonFinite;
                return;
            }
        }
    }

    energy.total = energy.harmonic_bond + energy.harmonic_angle +
                   energy.periodic_torsion + energy.lennard_jones +
                   energy.coulomb;
    if (!isfinite(energy.total)) {
        *out_failure = kDeviceNonFinite;
        return;
    }
    *out_energy = energy;
}

int32_t validate_request(
    const bg_hip_safe_system_v1 *system,
    const bg_hip_safe_forcefield_v1 *forcefield,
    uint8_t compute_forces,
    bg_hip_safe_energy_v1 *out_energy,
    bg_hip_safe_force_output_v1 *out_forces,
    char *error_message,
    size_t error_capacity) noexcept {
    if (system == nullptr || forcefield == nullptr || out_energy == nullptr ||
        compute_forces > UINT8_C(1)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            "hip_safe request descriptor is null or invalid");
    }
    if (!valid_header(*system) || !valid_header(*forcefield) ||
        !valid_header(*out_energy)) {
        return fail(
            BG_STATUS_ABI_MISMATCH,
            error_message,
            error_capacity,
            "hip_safe provider descriptor ABI mismatch");
    }
    if (!reserved_is_zero(system->reserved) ||
        !reserved_is_zero(forcefield->reserved) || forcefield->reserved0 != 0 ||
        !reserved_is_zero(out_energy->reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            "hip_safe provider reserved fields must be zero");
    }
    if (system->atom_count == 0 || system->atom_count != forcefield->atom_count ||
        !counted_pointer_is_valid(system->position_x, system->atom_count) ||
        !counted_pointer_is_valid(system->position_y, system->atom_count) ||
        !counted_pointer_is_valid(system->position_z, system->atom_count) ||
        !counted_pointer_is_valid(system->charge, system->atom_count) ||
        !counted_pointer_is_valid(forcefield->sigma, forcefield->atom_count) ||
        !counted_pointer_is_valid(forcefield->epsilon, forcefield->atom_count) ||
        !counted_pointer_is_valid(
            forcefield->bonds.atom_i, forcefield->bonds.count) ||
        !counted_pointer_is_valid(
            forcefield->bonds.atom_j, forcefield->bonds.count) ||
        !counted_pointer_is_valid(
            forcefield->bonds.equilibrium, forcefield->bonds.count) ||
        !counted_pointer_is_valid(
            forcefield->bonds.force_constant, forcefield->bonds.count) ||
        !counted_pointer_is_valid(
            forcefield->angles.atom_i, forcefield->angles.count) ||
        !counted_pointer_is_valid(
            forcefield->angles.atom_j, forcefield->angles.count) ||
        !counted_pointer_is_valid(
            forcefield->angles.atom_k, forcefield->angles.count) ||
        !counted_pointer_is_valid(
            forcefield->angles.equilibrium, forcefield->angles.count) ||
        !counted_pointer_is_valid(
            forcefield->angles.force_constant, forcefield->angles.count) ||
        !counted_pointer_is_valid(
            forcefield->torsions.atom_i, forcefield->torsions.count) ||
        !counted_pointer_is_valid(
            forcefield->torsions.atom_j, forcefield->torsions.count) ||
        !counted_pointer_is_valid(
            forcefield->torsions.atom_k, forcefield->torsions.count) ||
        !counted_pointer_is_valid(
            forcefield->torsions.atom_l, forcefield->torsions.count) ||
        !counted_pointer_is_valid(
            forcefield->torsions.periodicity, forcefield->torsions.count) ||
        !counted_pointer_is_valid(
            forcefield->torsions.phase, forcefield->torsions.count) ||
        !counted_pointer_is_valid(
            forcefield->torsions.amplitude, forcefield->torsions.count) ||
        !counted_pointer_is_valid(
            forcefield->exclusions, forcefield->exclusion_count) ||
        !counted_pointer_is_valid(
            forcefield->pair_scales, forcefield->pair_scale_count)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            "hip_safe provider channel identity is invalid");
    }
    if (compute_forces == UINT8_C(0)) {
        return BG_STATUS_OK;
    }
    if (out_forces == nullptr || !valid_header(*out_forces) ||
        !reserved_is_zero(out_forces->reserved) ||
        out_forces->capacity < system->atom_count || out_forces->x == nullptr ||
        out_forces->y == nullptr || out_forces->z == nullptr ||
        ranges_overlap(out_forces->x, out_forces->y, system->atom_count) ||
        ranges_overlap(out_forces->x, out_forces->z, system->atom_count) ||
        ranges_overlap(out_forces->y, out_forces->z, system->atom_count)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            "hip_safe force output is invalid, undersized, or overlapping");
    }
    return BG_STATUS_OK;
}

const char *device_failure_message(int32_t failure) noexcept {
    switch (failure) {
        case kDeviceBondZeroLength:
            return "hip_safe bond has zero-length geometry";
        case kDeviceAngleDegenerate:
            return "hip_safe angle has a zero-length arm";
        case kDeviceTorsionDegenerate:
            return "hip_safe torsion geometry is degenerate";
        case kDeviceMinimumPairDistance:
            return "hip_safe nonbonded pair is below minimum_pair_distance";
        case kDeviceNonFinite:
            return "hip_safe device evaluation produced a non-finite value";
        default:
            return "hip_safe device evaluation failed internally";
    }
}

}  // namespace

extern "C" int32_t bg_hip_safe_provider_is_available_v1(
    int32_t device_ordinal,
    uint8_t *available,
    char *error_message,
    size_t error_capacity) {
    clear_error(error_message, error_capacity);
    if (available == nullptr || device_ordinal < 0) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            "hip_safe availability arguments are invalid");
    }
    *available = UINT8_C(0);
    int runtime_version = 0;
    const hipError_t version_status = hipRuntimeGetVersion(&runtime_version);
    if (version_status != hipSuccess) {
        return fail_hip(
            version_status, error_message, error_capacity, "runtime version query");
    }
    if (runtime_version != HIP_VERSION) {
        return BG_STATUS_OK;
    }
    int device_count = 0;
    const hipError_t count_status = hipGetDeviceCount(&device_count);
    if (count_status == hipErrorNoDevice) {
        static_cast<void>(hipGetLastError());
        return BG_STATUS_OK;
    }
    if (count_status != hipSuccess) {
        return fail_hip(
            count_status, error_message, error_capacity, "device enumeration");
    }
    if (device_ordinal >= device_count) {
        return BG_STATUS_OK;
    }
    hipDeviceProp_t properties{};
    const hipError_t property_status =
        hipGetDeviceProperties(&properties, device_ordinal);
    if (property_status != hipSuccess) {
        return fail_hip(
            property_status, error_message, error_capacity, "device query");
    }
    if (properties.totalGlobalMem == 0 ||
        !architecture_is_qualified(properties.gcnArchName)) {
        return BG_STATUS_OK;
    }
    *available = UINT8_C(1);
    return BG_STATUS_OK;
}

extern "C" int32_t bg_hip_safe_evaluate_v1(
    int32_t device_ordinal,
    const bg_hip_safe_system_v1 *system,
    const bg_hip_safe_forcefield_v1 *forcefield,
    uint8_t compute_forces,
    bg_hip_safe_energy_v1 *out_energy,
    bg_hip_safe_force_output_v1 *out_forces,
    char *error_message,
    size_t error_capacity) {
    clear_error(error_message, error_capacity);
    const int32_t validation_status = validate_request(
        system,
        forcefield,
        compute_forces,
        out_energy,
        out_forces,
        error_message,
        error_capacity);
    if (validation_status != BG_STATUS_OK) {
        return validation_status;
    }
    uint8_t available = UINT8_C(0);
    const int32_t availability_status = bg_hip_safe_provider_is_available_v1(
        device_ordinal,
        &available,
        error_message,
        error_capacity);
    if (availability_status != BG_STATUS_OK) {
        return availability_status;
    }
    if (available == UINT8_C(0)) {
        return fail(
            BG_STATUS_BACKEND_UNAVAILABLE,
            error_message,
            error_capacity,
            "hip_safe device ordinal is unavailable");
    }

    DeviceGuard device_guard;
    const hipError_t set_status = hipSetDevice(device_ordinal);
    if (set_status != hipSuccess) {
        return fail_hip(
            set_status, error_message, error_capacity, "device selection");
    }

#define BG_HIP_COPY_INPUT(buffer, source, count, operation)                \
    do {                                                                   \
        const hipError_t copy_status = (buffer).copy_from((source), (count)); \
        if (copy_status != hipSuccess) {                                   \
            return fail_hip(                                               \
                copy_status, error_message, error_capacity, (operation));  \
        }                                                                  \
    } while (false)

    DeviceBuffer<double> position_x;
    DeviceBuffer<double> position_y;
    DeviceBuffer<double> position_z;
    DeviceBuffer<double> charge;
    DeviceBuffer<double> sigma;
    DeviceBuffer<double> epsilon;
    BG_HIP_COPY_INPUT(position_x, system->position_x, system->atom_count, "position_x copy");
    BG_HIP_COPY_INPUT(position_y, system->position_y, system->atom_count, "position_y copy");
    BG_HIP_COPY_INPUT(position_z, system->position_z, system->atom_count, "position_z copy");
    BG_HIP_COPY_INPUT(charge, system->charge, system->atom_count, "charge copy");
    BG_HIP_COPY_INPUT(sigma, forcefield->sigma, forcefield->atom_count, "sigma copy");
    BG_HIP_COPY_INPUT(epsilon, forcefield->epsilon, forcefield->atom_count, "epsilon copy");

    DeviceBuffer<size_t> bond_i;
    DeviceBuffer<size_t> bond_j;
    DeviceBuffer<double> bond_equilibrium;
    DeviceBuffer<double> bond_force_constant;
    BG_HIP_COPY_INPUT(bond_i, forcefield->bonds.atom_i, forcefield->bonds.count, "bond atom_i copy");
    BG_HIP_COPY_INPUT(bond_j, forcefield->bonds.atom_j, forcefield->bonds.count, "bond atom_j copy");
    BG_HIP_COPY_INPUT(
        bond_equilibrium,
        forcefield->bonds.equilibrium,
        forcefield->bonds.count,
        "bond equilibrium copy");
    BG_HIP_COPY_INPUT(
        bond_force_constant,
        forcefield->bonds.force_constant,
        forcefield->bonds.count,
        "bond force constant copy");

    DeviceBuffer<size_t> angle_i;
    DeviceBuffer<size_t> angle_j;
    DeviceBuffer<size_t> angle_k;
    DeviceBuffer<double> angle_equilibrium;
    DeviceBuffer<double> angle_force_constant;
    BG_HIP_COPY_INPUT(angle_i, forcefield->angles.atom_i, forcefield->angles.count, "angle atom_i copy");
    BG_HIP_COPY_INPUT(angle_j, forcefield->angles.atom_j, forcefield->angles.count, "angle atom_j copy");
    BG_HIP_COPY_INPUT(angle_k, forcefield->angles.atom_k, forcefield->angles.count, "angle atom_k copy");
    BG_HIP_COPY_INPUT(
        angle_equilibrium,
        forcefield->angles.equilibrium,
        forcefield->angles.count,
        "angle equilibrium copy");
    BG_HIP_COPY_INPUT(
        angle_force_constant,
        forcefield->angles.force_constant,
        forcefield->angles.count,
        "angle force constant copy");

    DeviceBuffer<size_t> torsion_i;
    DeviceBuffer<size_t> torsion_j;
    DeviceBuffer<size_t> torsion_k;
    DeviceBuffer<size_t> torsion_l;
    DeviceBuffer<uint32_t> torsion_periodicity;
    DeviceBuffer<double> torsion_phase;
    DeviceBuffer<double> torsion_amplitude;
    BG_HIP_COPY_INPUT(torsion_i, forcefield->torsions.atom_i, forcefield->torsions.count, "torsion atom_i copy");
    BG_HIP_COPY_INPUT(torsion_j, forcefield->torsions.atom_j, forcefield->torsions.count, "torsion atom_j copy");
    BG_HIP_COPY_INPUT(torsion_k, forcefield->torsions.atom_k, forcefield->torsions.count, "torsion atom_k copy");
    BG_HIP_COPY_INPUT(torsion_l, forcefield->torsions.atom_l, forcefield->torsions.count, "torsion atom_l copy");
    BG_HIP_COPY_INPUT(
        torsion_periodicity,
        forcefield->torsions.periodicity,
        forcefield->torsions.count,
        "torsion periodicity copy");
    BG_HIP_COPY_INPUT(torsion_phase, forcefield->torsions.phase, forcefield->torsions.count, "torsion phase copy");
    BG_HIP_COPY_INPUT(
        torsion_amplitude,
        forcefield->torsions.amplitude,
        forcefield->torsions.count,
        "torsion amplitude copy");

    DeviceBuffer<bg_hip_safe_pair_v1> exclusions;
    DeviceBuffer<bg_hip_safe_pair_scale_v1> pair_scales_buffer;
    BG_HIP_COPY_INPUT(
        exclusions,
        forcefield->exclusions,
        forcefield->exclusion_count,
        "exclusion copy");
    BG_HIP_COPY_INPUT(
        pair_scales_buffer,
        forcefield->pair_scales,
        forcefield->pair_scale_count,
        "pair scale copy");

    bg_hip_safe_system_v1 device_system = *system;
    device_system.position_x = position_x.get();
    device_system.position_y = position_y.get();
    device_system.position_z = position_z.get();
    device_system.charge = charge.get();
    bg_hip_safe_forcefield_v1 device_forcefield = *forcefield;
    device_forcefield.sigma = sigma.get();
    device_forcefield.epsilon = epsilon.get();
    device_forcefield.bonds = {
        forcefield->bonds.count,
        bond_i.get(),
        bond_j.get(),
        bond_equilibrium.get(),
        bond_force_constant.get(),
    };
    device_forcefield.angles = {
        forcefield->angles.count,
        angle_i.get(),
        angle_j.get(),
        angle_k.get(),
        angle_equilibrium.get(),
        angle_force_constant.get(),
    };
    device_forcefield.torsions = {
        forcefield->torsions.count,
        torsion_i.get(),
        torsion_j.get(),
        torsion_k.get(),
        torsion_l.get(),
        torsion_periodicity.get(),
        torsion_phase.get(),
        torsion_amplitude.get(),
    };
    device_forcefield.exclusions = exclusions.get();
    device_forcefield.pair_scales = pair_scales_buffer.get();

    DeviceBuffer<bg_hip_safe_energy_v1> device_energy;
    DeviceBuffer<double> device_force_x;
    DeviceBuffer<double> device_force_y;
    DeviceBuffer<double> device_force_z;
    DeviceBuffer<int32_t> device_failure;
    hipError_t allocation_status = device_energy.allocate(1);
    if (allocation_status == hipSuccess) {
        allocation_status = device_failure.allocate(1);
    }
    if (allocation_status == hipSuccess && compute_forces != UINT8_C(0)) {
        allocation_status = device_force_x.allocate(system->atom_count);
    }
    if (allocation_status == hipSuccess && compute_forces != UINT8_C(0)) {
        allocation_status = device_force_y.allocate(system->atom_count);
    }
    if (allocation_status == hipSuccess && compute_forces != UINT8_C(0)) {
        allocation_status = device_force_z.allocate(system->atom_count);
    }
    if (allocation_status != hipSuccess) {
        return fail_hip(
            allocation_status, error_message, error_capacity, "output allocation");
    }

    hipLaunchKernelGGL(
        evaluate_kernel,
        dim3(1),
        dim3(1),
        0,
        0,
        device_system,
        device_forcefield,
        compute_forces,
        device_energy.get(),
        device_force_x.get(),
        device_force_y.get(),
        device_force_z.get(),
        device_failure.get());
    hipError_t execution_status = hipGetLastError();
    if (execution_status == hipSuccess) {
        execution_status = hipDeviceSynchronize();
    }
    if (execution_status != hipSuccess) {
        return fail_hip(
            execution_status, error_message, error_capacity, "kernel execution");
    }

    int32_t host_failure = kDeviceSuccess;
    hipError_t copy_status = device_failure.copy_to(&host_failure, 1);
    if (copy_status != hipSuccess) {
        return fail_hip(
            copy_status, error_message, error_capacity, "failure status copy");
    }
    if (host_failure != kDeviceSuccess) {
        const int32_t status = host_failure == kDeviceInternal
                                   ? BG_STATUS_INTERNAL_ERROR
                                   : BG_STATUS_NUMERICAL_ERROR;
        return fail(
            status,
            error_message,
            error_capacity,
            device_failure_message(host_failure));
    }

    std::unique_ptr<double[]> host_force_x;
    std::unique_ptr<double[]> host_force_y;
    std::unique_ptr<double[]> host_force_z;
    if (compute_forces != UINT8_C(0)) {
        host_force_x.reset(new (std::nothrow) double[system->atom_count]);
        host_force_y.reset(new (std::nothrow) double[system->atom_count]);
        host_force_z.reset(new (std::nothrow) double[system->atom_count]);
        if (host_force_x == nullptr || host_force_y == nullptr ||
            host_force_z == nullptr) {
            return fail(
                BG_STATUS_OUT_OF_MEMORY,
                error_message,
                error_capacity,
                "hip_safe host result allocation failed");
        }
    }

    bg_hip_safe_energy_v1 host_energy{};
    copy_status = device_energy.copy_to(&host_energy, 1);
    if (copy_status == hipSuccess && compute_forces != UINT8_C(0)) {
        copy_status =
            device_force_x.copy_to(host_force_x.get(), system->atom_count);
    }
    if (copy_status == hipSuccess && compute_forces != UINT8_C(0)) {
        copy_status =
            device_force_y.copy_to(host_force_y.get(), system->atom_count);
    }
    if (copy_status == hipSuccess && compute_forces != UINT8_C(0)) {
        copy_status =
            device_force_z.copy_to(host_force_z.get(), system->atom_count);
    }
    if (copy_status != hipSuccess) {
        return fail_hip(
            copy_status, error_message, error_capacity, "result copy");
    }
    if (compute_forces != UINT8_C(0)) {
        const size_t bytes = system->atom_count * sizeof(double);
        std::memcpy(out_forces->x, host_force_x.get(), bytes);
        std::memcpy(out_forces->y, host_force_y.get(), bytes);
        std::memcpy(out_forces->z, host_force_z.get(), bytes);
    }
    *out_energy = host_energy;
    return BG_STATUS_OK;

#undef BG_HIP_COPY_INPUT
}
