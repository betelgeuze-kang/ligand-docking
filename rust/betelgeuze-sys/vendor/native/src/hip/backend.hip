#include "backend.hpp"

#include "planning.hpp"
#include "provider.h"
#include "../cpu/evaluator.hpp"
#include "../internal.hpp"

#include <hip/hip_runtime.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <limits>
#include <mutex>
#include <new>
#include <utility>
#include <vector>

#pragma STDC FP_CONTRACT OFF

namespace betelgeuze::native::hip {
namespace {

constexpr unsigned int kThreadsPerBlock = 128U;
constexpr std::size_t kMaximumLaunchBlocks = 65535;
constexpr std::size_t kEnergyRowsPerChunk = 256;
// This matches the strict public CPU/HIP comparison envelope used by the
// evaluator parity suite.  A reduction whose conservative forward-error
// bound exceeds this budget is replayed in canonical CPU order.
constexpr double kEnergyParityAbsoluteTolerance = 1.0e-10;
constexpr double kEnergyParityRelativeTolerance = 1.0e-10;
constexpr double kDegenerateSquaredAngstrom2 = 1.0e-24;
constexpr double kAngleCosineMargin = 1.0e-12;

enum DeviceError : int {
    kDeviceOk = 0,
    kDeviceNumericalError = 1,
    kDeviceInternalError = 2,
};

struct DeviceVector3 final {
    double x;
    double y;
    double z;
};

struct DevicePair final {
    std::size_t atom_i;
    std::size_t atom_j;
};

struct DevicePairScale final {
    DevicePair pair;
    double lennard_jones;
    double coulomb;
};

enum ContributionKind : uint32_t {
    kBondContribution = 0,
    kAngleContribution = 1,
    kTorsionContribution = 2,
    kNonbondedContribution = 3,
};

struct DeviceContribution final {
    double primary_energy;
    double secondary_energy;
    std::size_t atoms[4];
    DeviceVector3 forces[4];
    uint32_t force_count;
    uint32_t kind;
};

struct DeviceEnergy final {
    double bond;
    double angle;
    double torsion;
    double lennard_jones;
    double coulomb;
    double total;
};

struct DeviceGrid final {
    double origin[3];
    double width[3];
    double length[3];
    std::size_t dimensions[3];
    std::size_t cell_count;
    uint32_t periodic_axes_mask;
};

struct DeviceSystemView final {
    std::size_t atom_count;
    const double *position_x;
    const double *position_y;
    const double *position_z;
    const double *charge;
};

struct DeviceForceFieldView final {
    std::size_t atom_count;
    const double *sigma;
    const double *epsilon;

    std::size_t bond_count;
    const std::size_t *bond_i;
    const std::size_t *bond_j;
    const double *bond_equilibrium;
    const double *bond_force_constant;

    std::size_t angle_count;
    const std::size_t *angle_i;
    const std::size_t *angle_j;
    const std::size_t *angle_k;
    const double *angle_equilibrium;
    const double *angle_force_constant;

    std::size_t torsion_count;
    const std::size_t *torsion_i;
    const std::size_t *torsion_j;
    const std::size_t *torsion_k;
    const std::size_t *torsion_l;
    const uint32_t *torsion_periodicity;
    const double *torsion_phase;
    const double *torsion_amplitude;

    std::size_t exclusion_count;
    const DevicePair *exclusions;
    std::size_t pair_scale_count;
    const DevicePairScale *pair_scales;

    uint32_t periodic_axes_mask;
    double cell_lengths[3];
    double cutoff;
    double switch_start;
    double dielectric;
    double screening_kappa;
    double minimum_pair_distance;
};

struct HipState final {
    int32_t device_ordinal = 0;
    hipStream_t stream = nullptr;
    std::mutex mutex;
    EvaluationStats last_stats{};
    uint64_t allocation_attempt_count = 0;
    uint64_t allocation_failure_ordinal = 0;
    uint64_t live_allocation_count = 0;
};

[[nodiscard]] bg_status runtime_failure(
    hipError_t error,
    const char *operation) noexcept {
    const bg_status status = detail::map_runtime_error_code(
        static_cast<int>(error),
        static_cast<int>(hipSuccess),
        static_cast<int>(hipErrorOutOfMemory));
    if (status == BG_STATUS_OK) {
        return status;
    }
    std::array<char, 384> message{};
    const char *const description = hipGetErrorString(error);
    (void)std::snprintf(
        message.data(),
        message.size(),
        "%s failed: %s",
        operation,
        description == nullptr ? "unknown HIP runtime error" : description);
    return fail(status, message.data());
}

[[nodiscard]] bg_status check_runtime(
    hipError_t error,
    const char *operation) noexcept {
    if (error == hipSuccess) {
        return BG_STATUS_OK;
    }
    return runtime_failure(error, operation);
}

class ScopedDeviceGuard final {
public:
    ScopedDeviceGuard() = default;
    ScopedDeviceGuard(const ScopedDeviceGuard &) = delete;
    ScopedDeviceGuard &operator=(const ScopedDeviceGuard &) = delete;

    ~ScopedDeviceGuard() {
        if (active_ && changed_) {
            (void)hipSetDevice(previous_device_);
        }
    }

    bg_status select(int32_t device_ordinal) noexcept {
        if (active_) {
            return fail(
                BG_STATUS_INTERNAL_ERROR,
                "HIP device guard was selected more than once");
        }
        hipError_t error = hipGetDevice(&previous_device_);
        if (error != hipSuccess) {
            return runtime_failure(error, "hipGetDevice");
        }
        active_ = true;
        if (previous_device_ == device_ordinal) {
            return BG_STATUS_OK;
        }
        error = hipSetDevice(device_ordinal);
        if (error != hipSuccess) {
            active_ = false;
            return runtime_failure(error, "hipSetDevice");
        }
        changed_ = true;
        return BG_STATUS_OK;
    }

    bg_status restore() noexcept {
        if (!active_) {
            return BG_STATUS_OK;
        }
        if (!changed_) {
            active_ = false;
            return BG_STATUS_OK;
        }
        const hipError_t error = hipSetDevice(previous_device_);
        if (error != hipSuccess) {
            return runtime_failure(error, "hipSetDevice restore");
        }
        active_ = false;
        changed_ = false;
        return BG_STATUS_OK;
    }

private:
    int previous_device_ = 0;
    bool active_ = false;
    bool changed_ = false;
};

template <typename T>
class DeviceBuffer final {
public:
    DeviceBuffer() = default;
    DeviceBuffer(const DeviceBuffer &) = delete;
    DeviceBuffer &operator=(const DeviceBuffer &) = delete;

    DeviceBuffer(DeviceBuffer &&other) noexcept
        : pointer_(std::exchange(other.pointer_, nullptr)),
          count_(std::exchange(other.count_, 0)),
          owner_(std::exchange(other.owner_, nullptr)) {}

    DeviceBuffer &operator=(DeviceBuffer &&other) noexcept {
        if (this != &other) {
            release();
            pointer_ = std::exchange(other.pointer_, nullptr);
            count_ = std::exchange(other.count_, 0);
            owner_ = std::exchange(other.owner_, nullptr);
        }
        return *this;
    }

    ~DeviceBuffer() { release(); }

    bg_status allocate(
        std::size_t count,
        const char *label,
        HipState *owner) noexcept {
        release();
        if (count == 0) {
            return BG_STATUS_OK;
        }
        std::size_t byte_count = 0;
        if (!detail::checked_multiply_size(count, sizeof(T), &byte_count)) {
            return fail(
                BG_STATUS_CAPACITY_OVERFLOW,
                "HIP allocation byte count overflows size_t");
        }
#if defined(BG_HIP_TEST_FORCE_OOM)
        (void)label;
        (void)owner;
        return fail(
            BG_STATUS_OUT_OF_MEMORY,
            "HIP test hook forced device allocation failure");
#else
#if defined(BG_HIP_TESTING)
        if (owner != nullptr) {
            ++owner->allocation_attempt_count;
            if (owner->allocation_failure_ordinal != 0 &&
                owner->allocation_attempt_count ==
                    owner->allocation_failure_ordinal) {
                return fail(
                    BG_STATUS_OUT_OF_MEMORY,
                    "HIP test hook forced device allocation failure");
            }
        }
#endif
        void *raw_pointer = nullptr;
        const hipError_t error = hipMalloc(&raw_pointer, byte_count);
        if (error != hipSuccess) {
            return runtime_failure(error, label);
        }
        pointer_ = static_cast<T *>(raw_pointer);
        count_ = count;
        owner_ = owner;
        if (owner_ != nullptr) {
            ++owner_->live_allocation_count;
        }
        return BG_STATUS_OK;
#endif
    }

    bg_status copy_from_host(
        const T *source,
        std::size_t count,
        hipStream_t stream,
        const char *label) noexcept {
        if (count == 0) {
            return BG_STATUS_OK;
        }
        if (source == nullptr || pointer_ == nullptr || count > count_) {
            return fail(
                BG_STATUS_INTERNAL_ERROR,
                "HIP host-to-device copy range is invalid");
        }
        std::size_t byte_count = 0;
        if (!detail::checked_multiply_size(count, sizeof(T), &byte_count)) {
            return fail(
                BG_STATUS_CAPACITY_OVERFLOW,
                "HIP copy byte count overflows size_t");
        }
        return check_runtime(
            hipMemcpyAsync(
                pointer_, source, byte_count, hipMemcpyHostToDevice, stream),
            label);
    }

    bg_status copy_to_host(
        T *destination,
        std::size_t count,
        hipStream_t stream,
        const char *label) const noexcept {
        if (count == 0) {
            return BG_STATUS_OK;
        }
        if (destination == nullptr || pointer_ == nullptr || count > count_) {
            return fail(
                BG_STATUS_INTERNAL_ERROR,
                "HIP device-to-host copy range is invalid");
        }
        std::size_t byte_count = 0;
        if (!detail::checked_multiply_size(count, sizeof(T), &byte_count)) {
            return fail(
                BG_STATUS_CAPACITY_OVERFLOW,
                "HIP copy byte count overflows size_t");
        }
        return check_runtime(
            hipMemcpyAsync(
                destination,
                pointer_,
                byte_count,
                hipMemcpyDeviceToHost,
                stream),
            label);
    }

    bg_status zero(hipStream_t stream, const char *label) noexcept {
        if (count_ == 0) {
            return BG_STATUS_OK;
        }
        std::size_t byte_count = 0;
        if (!detail::checked_multiply_size(count_, sizeof(T), &byte_count)) {
            return fail(
                BG_STATUS_CAPACITY_OVERFLOW,
                "HIP memset byte count overflows size_t");
        }
        return check_runtime(hipMemsetAsync(pointer_, 0, byte_count, stream), label);
    }

    [[nodiscard]] T *get() noexcept { return pointer_; }
    [[nodiscard]] const T *get() const noexcept { return pointer_; }
    [[nodiscard]] std::size_t size() const noexcept { return count_; }

private:
    void release() noexcept {
        if (pointer_ != nullptr) {
            (void)hipFree(pointer_);
            if (owner_ != nullptr && owner_->live_allocation_count != 0) {
                --owner_->live_allocation_count;
            }
            pointer_ = nullptr;
            count_ = 0;
            owner_ = nullptr;
        }
    }

    T *pointer_ = nullptr;
    std::size_t count_ = 0;
    HipState *owner_ = nullptr;
};

[[nodiscard]] unsigned int launch_block_count(std::size_t work_items) noexcept {
    if (work_items == 0) {
        return 0U;
    }
    const std::size_t rounded =
        (work_items - 1) / static_cast<std::size_t>(kThreadsPerBlock) + 1;
    const std::size_t bounded = std::min(rounded, kMaximumLaunchBlocks);
    return static_cast<unsigned int>(bounded);
}

[[nodiscard]] bool storage_is_consistent(
    const bg_system &system,
    const bg_forcefield &forcefield) noexcept {
    const std::size_t atom_count = system.position_x.size();
    if (system.position_y.size() != atom_count ||
        system.position_z.size() != atom_count ||
        system.charge.size() != atom_count || forcefield.atom_count != atom_count ||
        forcefield.sigma.size() != atom_count ||
        forcefield.epsilon.size() != atom_count) {
        return false;
    }
    const auto &bonds = forcefield.bonds;
    const auto &angles = forcefield.angles;
    const auto &torsions = forcefield.torsions;
    return bonds.atom_i.size() == bonds.atom_j.size() &&
           bonds.atom_i.size() == bonds.equilibrium.size() &&
           bonds.atom_i.size() == bonds.force_constant.size() &&
           angles.atom_i.size() == angles.atom_j.size() &&
           angles.atom_i.size() == angles.atom_k.size() &&
           angles.atom_i.size() == angles.equilibrium.size() &&
           angles.atom_i.size() == angles.force_constant.size() &&
           torsions.atom_i.size() == torsions.atom_j.size() &&
           torsions.atom_i.size() == torsions.atom_k.size() &&
           torsions.atom_i.size() == torsions.atom_l.size() &&
           torsions.atom_i.size() == torsions.periodicity.size() &&
           torsions.atom_i.size() == torsions.phase.size() &&
           torsions.atom_i.size() == torsions.amplitude.size();
}

[[nodiscard]] bg_status build_grid(
    const bg_system &system,
    const bg_forcefield &forcefield,
    DeviceGrid *out_grid) noexcept {
    if (out_grid == nullptr) {
        return fail(BG_STATUS_INTERNAL_ERROR, "HIP grid output is null");
    }
    DeviceGrid grid{};
    grid.periodic_axes_mask = forcefield.periodic_axes_mask;
    /* A pair below the numerical safety floor must be observed before cutoff
     * handling, even when that floor is larger than cutoff.  The cell search
     * radius therefore covers both evaluation and validation. */
    const double search_radius =
        std::max(forcefield.cutoff, forcefield.minimum_pair_distance);
    const auto select_direct_fallback = [&]() noexcept -> bg_status {
        grid.dimensions[0] = 1;
        grid.dimensions[1] = 1;
        grid.dimensions[2] = 1;
        grid.cell_count = 0;
        *out_grid = grid;
        return BG_STATUS_OK;
    };
    const std::array<const std::vector<double> *, 3> channels = {
        &system.position_x,
        &system.position_y,
        &system.position_z,
    };
    std::array<double, 3> bounding_minimum{};
    std::array<long double, 3> bounding_span{};
    long double displacement_squared_bound = 0.0L;
    for (std::size_t axis = 0; axis < 3; ++axis) {
        const auto minmax = std::minmax_element(
            channels[axis]->begin(), channels[axis]->end());
        bounding_minimum[axis] = *minmax.first;
        bounding_span[axis] =
            static_cast<long double>(*minmax.second) -
            static_cast<long double>(*minmax.first);
        if (!std::isfinite(bounding_span[axis])) {
            return select_direct_fallback();
        }
        const long double squared_axis_bound =
            bounding_span[axis] * bounding_span[axis];
        displacement_squared_bound += squared_axis_bound;
        if (!std::isfinite(squared_axis_bound) ||
            !std::isfinite(displacement_squared_bound) ||
            displacement_squared_bound > static_cast<long double>(
                                             std::numeric_limits<double>::max())) {
            return select_direct_fallback();
        }
    }
    const uint32_t axis_bits[3] = {
        BG_PERIODIC_AXIS_X,
        BG_PERIODIC_AXIS_Y,
        BG_PERIODIC_AXIS_Z,
    };
    for (std::size_t axis = 0; axis < 3; ++axis) {
        const bool periodic =
            (forcefield.periodic_axes_mask & axis_bits[axis]) != 0U;
        if (periodic) {
            const double length = forcefield.cell_lengths[axis];
            /* CPU minimum-image evaluation forms displacement / length in
             * binary64 before applying floor().  If any displacement on this
             * axis can overflow that quotient, cell pruning must not hide the
             * resulting numerical-error row.  The direct path visits every
             * canonical pair and applies the same validation ordering. */
            const long double quotient_bound =
                bounding_span[axis] / static_cast<long double>(length);
            if (!std::isfinite(quotient_bound) ||
                quotient_bound > static_cast<long double>(
                                     std::numeric_limits<double>::max())) {
                return select_direct_fallback();
            }
            const double safe_denominator = std::nextafter(
                search_radius, std::numeric_limits<double>::infinity());
            const double quotient = length / safe_denominator;
            const double raw_cells = std::max(1.0, std::floor(quotient));
            if (!std::isfinite(raw_cells) || raw_cells < 1.0 ||
                raw_cells >= static_cast<double>(
                                std::numeric_limits<std::size_t>::max())) {
                return select_direct_fallback();
            }
            grid.dimensions[axis] = static_cast<std::size_t>(raw_cells);
            grid.origin[axis] = bounding_minimum[axis];
            grid.length[axis] = length;
            grid.width[axis] =
                length / static_cast<double>(grid.dimensions[axis]);
            while (grid.dimensions[axis] > 1 &&
                   !(grid.width[axis] > search_radius)) {
                --grid.dimensions[axis];
                grid.width[axis] =
                    length / static_cast<double>(grid.dimensions[axis]);
            }
            /* Cell phases use shifted fmod while the frozen evaluator uses
             * d - L*floor(d/L + 0.5).  Their modulo-L difference is bounded
             * by the binary64 operations on the observed span.  If that
             * conservative bound can consume the gap between cell width and
             * search radius, a +/-1-cell halo is not a completeness proof,
             * so visit every canonical pair instead. */
            constexpr long double kPhaseErrorOperations = 32.0L;
            const long double phase_error_bound =
                kPhaseErrorOperations *
                    static_cast<long double>(
                        std::numeric_limits<double>::epsilon()) *
                    (bounding_span[axis] +
                     static_cast<long double>(length)) +
                kPhaseErrorOperations *
                    static_cast<long double>(
                        std::numeric_limits<double>::denorm_min());
            const long double cell_margin =
                static_cast<long double>(grid.width[axis]) -
                static_cast<long double>(search_radius);
            if (!std::isfinite(phase_error_bound) ||
                !(cell_margin > phase_error_bound)) {
                return select_direct_fallback();
            }
        } else {
            const double minimum = bounding_minimum[axis];
            const long double span = bounding_span[axis];
            if (!std::isfinite(span)) {
                return select_direct_fallback();
            }
            const long double raw_cells =
                std::floor(span / static_cast<long double>(search_radius)) +
                1.0L;
            if (!std::isfinite(raw_cells) || raw_cells < 1.0L ||
                raw_cells >= static_cast<long double>(
                                std::numeric_limits<std::size_t>::max())) {
                return select_direct_fallback();
            }
            grid.dimensions[axis] = static_cast<std::size_t>(raw_cells);
            grid.origin[axis] = minimum;
            grid.length[axis] = 0.0;
            grid.width[axis] = search_radius;
        }
    }
    std::size_t xy_cells = 0;
    if (!detail::checked_multiply_size(
            grid.dimensions[0], grid.dimensions[1], &xy_cells) ||
        !detail::checked_multiply_size(
            xy_cells, grid.dimensions[2], &grid.cell_count)) {
        return select_direct_fallback();
    }
    std::size_t scaled_atom_budget = 0;
    if (!detail::checked_multiply_size(
            system.position_x.size(), std::size_t{64}, &scaled_atom_budget)) {
        scaled_atom_budget = std::numeric_limits<std::size_t>::max();
    }
    const std::size_t cell_budget =
        std::max(std::size_t{1024}, scaled_atom_budget);
    if (grid.cell_count > cell_budget) {
        return select_direct_fallback();
    }
    *out_grid = grid;
    return BG_STATUS_OK;
}

template <typename T>
bg_status allocate_and_upload(
    DeviceBuffer<T> *buffer,
    const T *source,
    std::size_t count,
    hipStream_t stream,
    HipState *owner,
    const char *allocation_label,
    const char *copy_label) noexcept {
    bg_status status = buffer->allocate(count, allocation_label, owner);
    if (status != BG_STATUS_OK) {
        return status;
    }
    return buffer->copy_from_host(source, count, stream, copy_label);
}

template <typename T>
bg_status allocate_and_upload(
    DeviceBuffer<T> *buffer,
    const std::vector<T> &source,
    hipStream_t stream,
    HipState *owner,
    const char *allocation_label,
    const char *copy_label) noexcept {
    return allocate_and_upload(
        buffer,
        source.data(),
        source.size(),
        stream,
        owner,
        allocation_label,
        copy_label);
}

__device__ void set_device_error(int *error, DeviceError value) {
    (void)atomicCAS(error, kDeviceOk, static_cast<int>(value));
}

__device__ DeviceVector3 vector_plus(
    DeviceVector3 left,
    DeviceVector3 right) {
    return {left.x + right.x, left.y + right.y, left.z + right.z};
}

__device__ DeviceVector3 vector_minus(
    DeviceVector3 left,
    DeviceVector3 right) {
    return {left.x - right.x, left.y - right.y, left.z - right.z};
}

__device__ DeviceVector3 vector_scale(DeviceVector3 value, double factor) {
    return {value.x * factor, value.y * factor, value.z * factor};
}

__device__ double vector_dot(DeviceVector3 left, DeviceVector3 right) {
    return left.x * right.x + left.y * right.y + left.z * right.z;
}

__device__ DeviceVector3 vector_cross(
    DeviceVector3 left,
    DeviceVector3 right) {
    return {
        left.y * right.z - left.z * right.y,
        left.z * right.x - left.x * right.z,
        left.x * right.y - left.y * right.x,
    };
}

__device__ bool vector_is_finite(DeviceVector3 value) {
    return isfinite(value.x) && isfinite(value.y) && isfinite(value.z);
}

__device__ DeviceVector3 displacement(
    DeviceSystemView system,
    DeviceForceFieldView forcefield,
    std::size_t atom_i,
    std::size_t atom_j) {
    DeviceVector3 result{
        system.position_x[atom_i] - system.position_x[atom_j],
        system.position_y[atom_i] - system.position_y[atom_j],
        system.position_z[atom_i] - system.position_z[atom_j],
    };
    double *components[3] = {&result.x, &result.y, &result.z};
    const uint32_t axis_bits[3] = {
        BG_PERIODIC_AXIS_X,
        BG_PERIODIC_AXIS_Y,
        BG_PERIODIC_AXIS_Z,
    };
    for (unsigned int axis = 0; axis < 3U; ++axis) {
        if ((forcefield.periodic_axes_mask & axis_bits[axis]) != 0U) {
            const double length = forcefield.cell_lengths[axis];
            double &component = *components[axis];
            component -= length * floor(component / length + 0.5);
        }
    }
    return result;
}

__device__ bool pair_less(DevicePair left, DevicePair right) {
    return left.atom_i < right.atom_i ||
           (left.atom_i == right.atom_i && left.atom_j < right.atom_j);
}

__device__ bool pair_equal(DevicePair left, DevicePair right) {
    return left.atom_i == right.atom_i && left.atom_j == right.atom_j;
}

__device__ bool pair_is_excluded(
    DeviceForceFieldView forcefield,
    DevicePair target) {
    std::size_t begin = 0;
    std::size_t end = forcefield.exclusion_count;
    while (begin < end) {
        const std::size_t middle = begin + (end - begin) / 2;
        if (pair_less(forcefield.exclusions[middle], target)) {
            begin = middle + 1;
        } else {
            end = middle;
        }
    }
    return begin < forcefield.exclusion_count &&
           pair_equal(forcefield.exclusions[begin], target);
}

__device__ DevicePairScale find_pair_scale(
    DeviceForceFieldView forcefield,
    DevicePair target) {
    std::size_t begin = 0;
    std::size_t end = forcefield.pair_scale_count;
    while (begin < end) {
        const std::size_t middle = begin + (end - begin) / 2;
        if (pair_less(forcefield.pair_scales[middle].pair, target)) {
            begin = middle + 1;
        } else {
            end = middle;
        }
    }
    if (begin < forcefield.pair_scale_count &&
        pair_equal(forcefield.pair_scales[begin].pair, target)) {
        return forcefield.pair_scales[begin];
    }
    return {target, 1.0, 1.0};
}

__device__ std::size_t global_thread_index() {
    return static_cast<std::size_t>(blockIdx.x) * blockDim.x + threadIdx.x;
}

__device__ std::size_t global_thread_stride() {
    return static_cast<std::size_t>(gridDim.x) * blockDim.x;
}

__device__ std::size_t atomic_increment_size(std::size_t *value) {
    static_assert(sizeof(std::size_t) == sizeof(unsigned long long));
    static_assert(alignof(std::size_t) == alignof(unsigned long long));
    return static_cast<std::size_t>(atomicAdd(
        reinterpret_cast<unsigned long long *>(value), UINT64_C(1)));
}

__device__ std::size_t coordinate_cell(
    double coordinate,
    DeviceGrid grid,
    unsigned int axis) {
    double local = coordinate;
    const uint32_t axis_bits[3] = {
        BG_PERIODIC_AXIS_X,
        BG_PERIODIC_AXIS_Y,
        BG_PERIODIC_AXIS_Z,
    };
    if ((grid.periodic_axes_mask & axis_bits[axis]) != 0U) {
        const double length = grid.length[axis];
        /* Subtract the shared host-computed origin before argument reduction;
         * build_grid proves the residual phase error fits the cell halo. */
        local = fmod(coordinate - grid.origin[axis], length);
        if (local < 0.0) {
            local += length;
        }
        if (local == length) {
            local = 0.0;
        }
    } else {
        local -= grid.origin[axis];
    }
    double raw = floor(local / grid.width[axis]);
    if (raw < 0.0) {
        raw = 0.0;
    }
    const double maximum = static_cast<double>(grid.dimensions[axis] - 1);
    if (raw > maximum) {
        raw = maximum;
    }
    return static_cast<std::size_t>(raw);
}

__device__ std::size_t encode_cell(
    DeviceGrid grid,
    std::size_t x,
    std::size_t y,
    std::size_t z) {
    return (z * grid.dimensions[1] + y) * grid.dimensions[0] + x;
}

__device__ void decode_cell(
    DeviceGrid grid,
    std::size_t cell,
    std::size_t *x,
    std::size_t *y,
    std::size_t *z) {
    *x = cell % grid.dimensions[0];
    const std::size_t yz = cell / grid.dimensions[0];
    *y = yz % grid.dimensions[1];
    *z = yz / grid.dimensions[1];
}

__device__ bool offset_coordinate(
    std::size_t coordinate,
    int offset,
    std::size_t dimension,
    bool periodic,
    std::size_t *out_coordinate) {
    if (offset < 0) {
        if (coordinate == 0) {
            if (!periodic) {
                return false;
            }
            *out_coordinate = dimension - 1;
            return true;
        }
        *out_coordinate = coordinate - 1;
        return true;
    }
    if (offset > 0) {
        if (coordinate + 1 == dimension) {
            if (!periodic) {
                return false;
            }
            *out_coordinate = 0;
            return true;
        }
        *out_coordinate = coordinate + 1;
        return true;
    }
    *out_coordinate = coordinate;
    return true;
}

__device__ unsigned int collect_neighbor_cells(
    DeviceGrid grid,
    std::size_t cell,
    std::size_t *neighbors) {
    std::size_t x = 0;
    std::size_t y = 0;
    std::size_t z = 0;
    decode_cell(grid, cell, &x, &y, &z);
    unsigned int count = 0U;
    const bool periodic_x =
        (grid.periodic_axes_mask & BG_PERIODIC_AXIS_X) != 0U;
    const bool periodic_y =
        (grid.periodic_axes_mask & BG_PERIODIC_AXIS_Y) != 0U;
    const bool periodic_z =
        (grid.periodic_axes_mask & BG_PERIODIC_AXIS_Z) != 0U;
    for (int dz = -1; dz <= 1; ++dz) {
        std::size_t neighbor_z = 0;
        if (!offset_coordinate(
                z, dz, grid.dimensions[2], periodic_z, &neighbor_z)) {
            continue;
        }
        for (int dy = -1; dy <= 1; ++dy) {
            std::size_t neighbor_y = 0;
            if (!offset_coordinate(
                    y, dy, grid.dimensions[1], periodic_y, &neighbor_y)) {
                continue;
            }
            for (int dx = -1; dx <= 1; ++dx) {
                std::size_t neighbor_x = 0;
                if (!offset_coordinate(
                        x, dx, grid.dimensions[0], periodic_x, &neighbor_x)) {
                    continue;
                }
                const std::size_t candidate = encode_cell(
                    grid, neighbor_x, neighbor_y, neighbor_z);
                bool duplicate = false;
                for (unsigned int index = 0; index < count; ++index) {
                    if (neighbors[index] == candidate) {
                        duplicate = true;
                    }
                }
                if (!duplicate) {
                    neighbors[count] = candidate;
                    ++count;
                }
            }
        }
    }
    for (unsigned int outer = 1U; outer < count; ++outer) {
        const std::size_t value = neighbors[outer];
        unsigned int inner = outer;
        while (inner > 0U && value < neighbors[inner - 1U]) {
            neighbors[inner] = neighbors[inner - 1U];
            --inner;
        }
        neighbors[inner] = value;
    }
    return count;
}

__global__ void availability_probe_kernel() {}

__global__ void assign_cell_ids_kernel(
    DeviceSystemView system,
    DeviceGrid grid,
    std::size_t *atom_cells,
    std::size_t *cell_counts,
    int *error) {
    for (std::size_t atom = global_thread_index(); atom < system.atom_count;
         atom += global_thread_stride()) {
        const std::size_t x = coordinate_cell(system.position_x[atom], grid, 0U);
        const std::size_t y = coordinate_cell(system.position_y[atom], grid, 1U);
        const std::size_t z = coordinate_cell(system.position_z[atom], grid, 2U);
        const std::size_t cell = encode_cell(grid, x, y, z);
        if (cell >= grid.cell_count) {
            set_device_error(error, kDeviceInternalError);
            continue;
        }
        atom_cells[atom] = cell;
        (void)atomic_increment_size(&cell_counts[cell]);
    }
}

__global__ void prefix_cell_counts_kernel(
    DeviceGrid grid,
    const std::size_t *cell_counts,
    std::size_t *cell_offsets,
    int *error) {
    if (blockIdx.x != 0U || threadIdx.x != 0U) {
        return;
    }
    std::size_t prefix = 0;
    cell_offsets[0] = 0;
    for (std::size_t cell = 0; cell < grid.cell_count; ++cell) {
        const std::size_t count = cell_counts[cell];
        if (count > SIZE_MAX - prefix) {
            set_device_error(error, kDeviceInternalError);
            return;
        }
        prefix += count;
        cell_offsets[cell + 1] = prefix;
    }
}

__global__ void fill_cell_atoms_kernel(
    std::size_t atom_count,
    const std::size_t *atom_cells,
    const std::size_t *cell_offsets,
    std::size_t *cell_cursors,
    std::size_t *cell_atoms) {
    for (std::size_t atom = global_thread_index(); atom < atom_count;
         atom += global_thread_stride()) {
        const std::size_t cell = atom_cells[atom];
        const std::size_t rank = atomic_increment_size(&cell_cursors[cell]);
        cell_atoms[cell_offsets[cell] + rank] = atom;
    }
}

__device__ bool pair_inside_search_radius(
    DeviceSystemView system,
    DeviceForceFieldView forcefield,
    DevicePair pair,
    int *error) {
    const bool excluded = pair_is_excluded(forcefield, pair);
    const DeviceVector3 delta =
        displacement(system, forcefield, pair.atom_i, pair.atom_j);
    const double squared_distance = vector_dot(delta, delta);
    if (!vector_is_finite(delta) || !isfinite(squared_distance)) {
        if (!excluded) {
            set_device_error(error, kDeviceNumericalError);
        }
        return false;
    }
    const double minimum = forcefield.minimum_pair_distance;
    if (!excluded && squared_distance < minimum * minimum) {
        set_device_error(error, kDeviceNumericalError);
        return false;
    }
    const double search_radius =
        fmax(forcefield.cutoff, forcefield.minimum_pair_distance);
    const double distance = sqrt(squared_distance);
    return isfinite(distance) && distance <= search_radius;
}

__global__ void count_direct_neighbor_pairs_kernel(
    DeviceSystemView system,
    DeviceForceFieldView forcefield,
    std::size_t *pair_counts,
    int *error) {
    for (std::size_t atom_i = global_thread_index(); atom_i < system.atom_count;
         atom_i += global_thread_stride()) {
        std::size_t count = 0;
        for (std::size_t atom_j = atom_i + 1; atom_j < system.atom_count;
             ++atom_j) {
            const DevicePair pair{atom_i, atom_j};
            if (pair_inside_search_radius(system, forcefield, pair, error)) {
                ++count;
            }
        }
        pair_counts[atom_i] = count;
    }
}

__global__ void fill_direct_neighbor_pairs_kernel(
    DeviceSystemView system,
    DeviceForceFieldView forcefield,
    const std::size_t *pair_offsets,
    DevicePair *pairs,
    int *error) {
    for (std::size_t atom_i = global_thread_index(); atom_i < system.atom_count;
         atom_i += global_thread_stride()) {
        std::size_t output = pair_offsets[atom_i];
        for (std::size_t atom_j = atom_i + 1; atom_j < system.atom_count;
             ++atom_j) {
            const DevicePair pair{atom_i, atom_j};
            if (pair_inside_search_radius(system, forcefield, pair, error)) {
                pairs[output] = pair;
                ++output;
            }
        }
        if (output != pair_offsets[atom_i + 1]) {
            set_device_error(error, kDeviceInternalError);
        }
    }
}

__global__ void count_neighbor_pairs_kernel(
    DeviceSystemView system,
    DeviceForceFieldView forcefield,
    DeviceGrid grid,
    const std::size_t *atom_cells,
    const std::size_t *cell_offsets,
    const std::size_t *cell_atoms,
    std::size_t *pair_counts,
    int *error) {
    for (std::size_t atom_i = global_thread_index(); atom_i < system.atom_count;
         atom_i += global_thread_stride()) {
        std::size_t neighbor_cells[27];
        const unsigned int neighbor_cell_count = collect_neighbor_cells(
            grid, atom_cells[atom_i], neighbor_cells);
        std::size_t count = 0;
        for (unsigned int index = 0; index < neighbor_cell_count; ++index) {
            const std::size_t cell = neighbor_cells[index];
            for (std::size_t offset = cell_offsets[cell];
                 offset < cell_offsets[cell + 1];
                 ++offset) {
                const std::size_t atom_j = cell_atoms[offset];
                if (atom_j <= atom_i) {
                    continue;
                }
                const DevicePair pair{atom_i, atom_j};
                if (pair_inside_search_radius(
                        system, forcefield, pair, error)) {
                    ++count;
                }
            }
        }
        pair_counts[atom_i] = count;
    }
}

__global__ void prefix_pair_counts_kernel(
    std::size_t atom_count,
    const std::size_t *pair_counts,
    std::size_t *pair_offsets,
    int *error) {
    if (blockIdx.x != 0U || threadIdx.x != 0U) {
        return;
    }
    std::size_t prefix = 0;
    pair_offsets[0] = 0;
    for (std::size_t atom = 0; atom < atom_count; ++atom) {
        const std::size_t count = pair_counts[atom];
        if (count > SIZE_MAX - prefix) {
            set_device_error(error, kDeviceInternalError);
            return;
        }
        prefix += count;
        pair_offsets[atom + 1] = prefix;
    }
}

__global__ void fill_neighbor_pairs_kernel(
    DeviceSystemView system,
    DeviceForceFieldView forcefield,
    DeviceGrid grid,
    const std::size_t *atom_cells,
    const std::size_t *cell_offsets,
    const std::size_t *cell_atoms,
    const std::size_t *pair_offsets,
    DevicePair *pairs,
    int *error) {
    for (std::size_t atom_i = global_thread_index(); atom_i < system.atom_count;
         atom_i += global_thread_stride()) {
        std::size_t neighbor_cells[27];
        const unsigned int neighbor_cell_count = collect_neighbor_cells(
            grid, atom_cells[atom_i], neighbor_cells);
        std::size_t output = pair_offsets[atom_i];
        for (unsigned int index = 0; index < neighbor_cell_count; ++index) {
            const std::size_t cell = neighbor_cells[index];
            for (std::size_t offset = cell_offsets[cell];
                 offset < cell_offsets[cell + 1];
                 ++offset) {
                const std::size_t atom_j = cell_atoms[offset];
                if (atom_j <= atom_i) {
                    continue;
                }
                const DevicePair pair{atom_i, atom_j};
                if (pair_inside_search_radius(
                        system, forcefield, pair, error)) {
                    pairs[output] = pair;
                    ++output;
                }
            }
        }
        if (output != pair_offsets[atom_i + 1]) {
            set_device_error(error, kDeviceInternalError);
        }
    }
}

template <typename T, typename Less>
__device__ void merge_sort_segment(
    std::size_t segment,
    std::size_t item_count,
    const std::size_t *segment_offsets,
    T *original,
    T *scratch,
    Less less,
    int *error) {
    const std::size_t begin = segment_offsets[segment];
    const std::size_t end = segment_offsets[segment + 1];
    if (begin > end || end > item_count) {
        set_device_error(error, kDeviceInternalError);
        return;
    }
    const std::size_t length = end - begin;
    if (length < 2) {
        return;
    }
    std::size_t pass_count = 0;
    for (std::size_t run_count = length; run_count > 1;
         run_count = run_count / 2 + (run_count & std::size_t{1})) {
        ++pass_count;
    }
    T *source = original;
    T *destination = scratch;
    if ((pass_count & std::size_t{1}) != 0) {
        for (std::size_t index = begin; index < end; ++index) {
            scratch[index] = original[index];
        }
        source = scratch;
        destination = original;
    }
    for (std::size_t width = 1; width < length;) {
        for (std::size_t left = begin; left < end;) {
            const std::size_t left_remaining = end - left;
            const std::size_t middle =
                left + (width < left_remaining ? width : left_remaining);
            const std::size_t right_remaining = end - middle;
            const std::size_t right =
                middle +
                (width < right_remaining ? width : right_remaining);
            std::size_t left_index = left;
            std::size_t right_index = middle;
            std::size_t output = left;
            while (left_index < middle && right_index < right) {
                if (less(source[right_index], source[left_index])) {
                    destination[output++] = source[right_index++];
                } else {
                    destination[output++] = source[left_index++];
                }
            }
            while (left_index < middle) {
                destination[output++] = source[left_index++];
            }
            while (right_index < right) {
                destination[output++] = source[right_index++];
            }
            left = right;
        }
        T *const previous_source = source;
        source = destination;
        destination = previous_source;
        width = width > length / 2 ? length : width * 2;
    }
    if (source != original) {
        set_device_error(error, kDeviceInternalError);
    }
}

struct DevicePairLess final {
    __device__ bool operator()(DevicePair left, DevicePair right) const {
        return pair_less(left, right);
    }
};

__global__ void merge_sort_neighbor_segments_kernel(
    std::size_t atom_count,
    std::size_t pair_count,
    const std::size_t *pair_offsets,
    DevicePair *pairs,
    DevicePair *scratch,
    int *error) {
    for (std::size_t atom = global_thread_index(); atom < atom_count;
         atom += global_thread_stride()) {
        merge_sort_segment(
            atom,
            pair_count,
            pair_offsets,
            pairs,
            scratch,
            DevicePairLess{},
            error);
    }
}

__device__ DeviceContribution empty_contribution(uint32_t kind) {
    DeviceContribution contribution{};
    contribution.kind = kind;
    return contribution;
}

__device__ void set_contribution_force(
    DeviceContribution *contribution,
    uint32_t slot,
    std::size_t atom,
    DeviceVector3 force) {
    contribution->atoms[slot] = atom;
    contribution->forces[slot] = force;
}

__global__ void evaluate_bonds_kernel(
    DeviceSystemView system,
    DeviceForceFieldView forcefield,
    bool compute_forces,
    DeviceContribution *contributions,
    int *error) {
    for (std::size_t row = global_thread_index(); row < forcefield.bond_count;
         row += global_thread_stride()) {
        DeviceContribution contribution = empty_contribution(kBondContribution);
        const std::size_t atom_i = forcefield.bond_i[row];
        const std::size_t atom_j = forcefield.bond_j[row];
        if (atom_i >= forcefield.atom_count || atom_j >= forcefield.atom_count) {
            set_device_error(error, kDeviceInternalError);
            contributions[row] = contribution;
            continue;
        }
        const DeviceVector3 delta =
            displacement(system, forcefield, atom_i, atom_j);
        const double squared_distance = vector_dot(delta, delta);
        if (!vector_is_finite(delta) || !isfinite(squared_distance) ||
            (compute_forces && squared_distance <= 0.0)) {
            set_device_error(error, kDeviceNumericalError);
            contributions[row] = contribution;
            continue;
        }
        const double distance = sqrt(squared_distance);
        const double difference = distance - forcefield.bond_equilibrium[row];
        const double energy = 0.5 * forcefield.bond_force_constant[row] *
                              difference * difference;
        if (!isfinite(energy)) {
            set_device_error(error, kDeviceNumericalError);
            contributions[row] = contribution;
            continue;
        }
        contribution.primary_energy = energy;
        if (compute_forces) {
            const DeviceVector3 force = vector_scale(
                delta,
                -forcefield.bond_force_constant[row] * difference / distance);
            if (!vector_is_finite(force)) {
                set_device_error(error, kDeviceNumericalError);
                contributions[row] = empty_contribution(kBondContribution);
                continue;
            }
            contribution.force_count = 2U;
            set_contribution_force(&contribution, 0U, atom_i, force);
            set_contribution_force(
                &contribution, 1U, atom_j, vector_scale(force, -1.0));
        }
        contributions[row] = contribution;
    }
}

__global__ void evaluate_angles_kernel(
    DeviceSystemView system,
    DeviceForceFieldView forcefield,
    bool compute_forces,
    std::size_t contribution_offset,
    DeviceContribution *contributions,
    int *error) {
    constexpr double lower_cosine = -1.0 + kAngleCosineMargin;
    constexpr double upper_cosine = 1.0 - kAngleCosineMargin;
    for (std::size_t row = global_thread_index(); row < forcefield.angle_count;
         row += global_thread_stride()) {
        DeviceContribution contribution = empty_contribution(kAngleContribution);
        const std::size_t atom_i = forcefield.angle_i[row];
        const std::size_t atom_j = forcefield.angle_j[row];
        const std::size_t atom_k = forcefield.angle_k[row];
        if (atom_i >= forcefield.atom_count || atom_j >= forcefield.atom_count ||
            atom_k >= forcefield.atom_count) {
            set_device_error(error, kDeviceInternalError);
            contributions[contribution_offset + row] = contribution;
            continue;
        }
        const DeviceVector3 first =
            displacement(system, forcefield, atom_i, atom_j);
        const DeviceVector3 second =
            displacement(system, forcefield, atom_k, atom_j);
        const double first_squared = vector_dot(first, first);
        const double second_squared = vector_dot(second, second);
        if (!vector_is_finite(first) || !vector_is_finite(second) ||
            !isfinite(first_squared) || !isfinite(second_squared) ||
            first_squared <= kDegenerateSquaredAngstrom2 ||
            second_squared <= kDegenerateSquaredAngstrom2) {
            set_device_error(error, kDeviceNumericalError);
            contributions[contribution_offset + row] = contribution;
            continue;
        }
        const double first_length = sqrt(first_squared);
        const double second_length = sqrt(second_squared);
        const double denominator = first_length * second_length;
        const double raw_cosine = vector_dot(first, second) / denominator;
        if (!isfinite(raw_cosine)) {
            set_device_error(error, kDeviceNumericalError);
            contributions[contribution_offset + row] = contribution;
            continue;
        }
        const double cosine = raw_cosine < lower_cosine
                                  ? lower_cosine
                                  : (raw_cosine > upper_cosine ? upper_cosine
                                                               : raw_cosine);
        const double angle = acos(cosine);
        const double difference = angle - forcefield.angle_equilibrium[row];
        const double derivative =
            forcefield.angle_force_constant[row] * difference;
        const double energy = 0.5 * forcefield.angle_force_constant[row] *
                              difference * difference;
        if (!isfinite(energy)) {
            set_device_error(error, kDeviceNumericalError);
            contributions[contribution_offset + row] = contribution;
            continue;
        }
        contribution.primary_energy = energy;
        if (compute_forces && raw_cosine > lower_cosine &&
            raw_cosine < upper_cosine) {
            const double sine = sqrt(1.0 - cosine * cosine);
            const DeviceVector3 first_unit =
                vector_scale(first, 1.0 / first_length);
            const DeviceVector3 second_unit =
                vector_scale(second, 1.0 / second_length);
            const DeviceVector3 force_i = vector_scale(
                vector_minus(second_unit, vector_scale(first_unit, cosine)),
                derivative / (first_length * sine));
            const DeviceVector3 force_k = vector_scale(
                vector_minus(first_unit, vector_scale(second_unit, cosine)),
                derivative / (second_length * sine));
            const DeviceVector3 force_j =
                vector_scale(vector_plus(force_i, force_k), -1.0);
            if (!vector_is_finite(force_i) || !vector_is_finite(force_j) ||
                !vector_is_finite(force_k)) {
                set_device_error(error, kDeviceNumericalError);
                contributions[contribution_offset + row] =
                    empty_contribution(kAngleContribution);
                continue;
            }
            contribution.force_count = 3U;
            set_contribution_force(&contribution, 0U, atom_i, force_i);
            set_contribution_force(&contribution, 1U, atom_j, force_j);
            set_contribution_force(&contribution, 2U, atom_k, force_k);
        }
        contributions[contribution_offset + row] = contribution;
    }
}

__global__ void evaluate_torsions_kernel(
    DeviceSystemView system,
    DeviceForceFieldView forcefield,
    bool compute_forces,
    std::size_t contribution_offset,
    DeviceContribution *contributions,
    int *error) {
    for (std::size_t row = global_thread_index(); row < forcefield.torsion_count;
         row += global_thread_stride()) {
        DeviceContribution contribution =
            empty_contribution(kTorsionContribution);
        const std::size_t atom_i = forcefield.torsion_i[row];
        const std::size_t atom_j = forcefield.torsion_j[row];
        const std::size_t atom_k = forcefield.torsion_k[row];
        const std::size_t atom_l = forcefield.torsion_l[row];
        if (atom_i >= forcefield.atom_count || atom_j >= forcefield.atom_count ||
            atom_k >= forcefield.atom_count || atom_l >= forcefield.atom_count) {
            set_device_error(error, kDeviceInternalError);
            contributions[contribution_offset + row] = contribution;
            continue;
        }
        const DeviceVector3 b0 =
            displacement(system, forcefield, atom_i, atom_j);
        const DeviceVector3 b1 =
            displacement(system, forcefield, atom_k, atom_j);
        const DeviceVector3 b2 =
            displacement(system, forcefield, atom_l, atom_k);
        const double central_squared = vector_dot(b1, b1);
        if (!vector_is_finite(b0) || !vector_is_finite(b1) ||
            !vector_is_finite(b2) || !isfinite(central_squared) ||
            central_squared <= kDegenerateSquaredAngstrom2) {
            set_device_error(error, kDeviceNumericalError);
            contributions[contribution_offset + row] = contribution;
            continue;
        }
        const double central_length = sqrt(central_squared);
        const DeviceVector3 axis = vector_scale(b1, 1.0 / central_length);
        const DeviceVector3 v =
            vector_minus(b0, vector_scale(axis, vector_dot(b0, axis)));
        const DeviceVector3 w =
            vector_minus(b2, vector_scale(axis, vector_dot(b2, axis)));
        const double v_squared = vector_dot(v, v);
        const double w_squared = vector_dot(w, w);
        if (!vector_is_finite(axis) || !vector_is_finite(v) ||
            !vector_is_finite(w) || !isfinite(v_squared) ||
            !isfinite(w_squared) || v_squared <= kDegenerateSquaredAngstrom2 ||
            w_squared <= kDegenerateSquaredAngstrom2) {
            set_device_error(error, kDeviceNumericalError);
            contributions[contribution_offset + row] = contribution;
            continue;
        }
        const double sine_numerator = vector_dot(vector_cross(axis, v), w);
        const double cosine_numerator = vector_dot(v, w);
        const double phi = atan2(sine_numerator, cosine_numerator);
        const double periodicity =
            static_cast<double>(forcefield.torsion_periodicity[row]);
        const double argument =
            periodicity * phi - forcefield.torsion_phase[row];
        const double amplitude = forcefield.torsion_amplitude[row];
        const double energy = amplitude * (1.0 + cos(argument));
        if (!isfinite(energy)) {
            set_device_error(error, kDeviceNumericalError);
            contributions[contribution_offset + row] = contribution;
            continue;
        }
        contribution.primary_energy = energy;
        if (compute_forces) {
            const DeviceVector3 gradient_b0 =
                vector_scale(vector_cross(axis, v), -1.0 / v_squared);
            const DeviceVector3 gradient_b2 =
                vector_scale(vector_cross(axis, w), 1.0 / w_squared);
            const DeviceVector3 gradient_b1 = vector_plus(
                vector_scale(
                    gradient_b0,
                    -vector_dot(b0, b1) / central_squared),
                vector_scale(
                    gradient_b2,
                    -vector_dot(b2, b1) / central_squared));
            const DeviceVector3 gradient_i = gradient_b0;
            const DeviceVector3 gradient_j =
                vector_scale(vector_plus(gradient_b0, gradient_b1), -1.0);
            const DeviceVector3 gradient_k =
                vector_minus(gradient_b1, gradient_b2);
            const DeviceVector3 gradient_l = gradient_b2;
            const double force_factor =
                amplitude * periodicity * sin(argument);
            const DeviceVector3 force_i =
                vector_scale(gradient_i, force_factor);
            const DeviceVector3 force_j =
                vector_scale(gradient_j, force_factor);
            const DeviceVector3 force_k =
                vector_scale(gradient_k, force_factor);
            const DeviceVector3 force_l =
                vector_scale(gradient_l, force_factor);
            if (!vector_is_finite(force_i) || !vector_is_finite(force_j) ||
                !vector_is_finite(force_k) || !vector_is_finite(force_l)) {
                set_device_error(error, kDeviceNumericalError);
                contributions[contribution_offset + row] =
                    empty_contribution(kTorsionContribution);
                continue;
            }
            contribution.force_count = 4U;
            set_contribution_force(&contribution, 0U, atom_i, force_i);
            set_contribution_force(&contribution, 1U, atom_j, force_j);
            set_contribution_force(&contribution, 2U, atom_k, force_k);
            set_contribution_force(&contribution, 3U, atom_l, force_l);
        }
        contributions[contribution_offset + row] = contribution;
    }
}

struct DeviceSwitchValue final {
    double value;
    double derivative;
};

__device__ DeviceSwitchValue switching_value(
    double distance,
    double start,
    double cutoff) {
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

__global__ void evaluate_nonbonded_kernel(
    DeviceSystemView system,
    DeviceForceFieldView forcefield,
    bool compute_forces,
    const DevicePair *pairs,
    std::size_t pair_count,
    std::size_t contribution_offset,
    DeviceContribution *contributions,
    int *error) {
    for (std::size_t row = global_thread_index(); row < pair_count;
         row += global_thread_stride()) {
        DeviceContribution contribution =
            empty_contribution(kNonbondedContribution);
        const DevicePair pair = pairs[row];
        if (pair.atom_i >= forcefield.atom_count ||
            pair.atom_j >= forcefield.atom_count ||
            pair.atom_i >= pair.atom_j) {
            set_device_error(error, kDeviceInternalError);
            contributions[contribution_offset + row] = contribution;
            continue;
        }
        if (pair_is_excluded(forcefield, pair)) {
            contributions[contribution_offset + row] = contribution;
            continue;
        }
        const DeviceVector3 delta =
            displacement(system, forcefield, pair.atom_i, pair.atom_j);
        const double squared_distance = vector_dot(delta, delta);
        const double minimum = forcefield.minimum_pair_distance;
        if (!vector_is_finite(delta) || !isfinite(squared_distance) ||
            squared_distance < minimum * minimum) {
            set_device_error(error, kDeviceNumericalError);
            contributions[contribution_offset + row] = contribution;
            continue;
        }
        const double distance = sqrt(squared_distance);
        if (distance > forcefield.cutoff) {
            contributions[contribution_offset + row] = contribution;
            continue;
        }
        const DevicePairScale scales = find_pair_scale(forcefield, pair);
        const double sigma =
            0.5 * (forcefield.sigma[pair.atom_i] +
                   forcefield.sigma[pair.atom_j]);
        const double epsilon = sqrt(
            forcefield.epsilon[pair.atom_i] *
            forcefield.epsilon[pair.atom_j]);
        const double ratio = sigma / distance;
        const double ratio2 = ratio * ratio;
        const double ratio6 = ratio2 * ratio2 * ratio2;
        const double ratio12 = ratio6 * ratio6;
        const double lennard_jones =
            4.0 * epsilon * (ratio12 - ratio6) * scales.lennard_jones;
        const double screened_charge =
            system.charge[pair.atom_i] * system.charge[pair.atom_j] *
            exp(-forcefield.screening_kappa * distance);
        const double coulomb =
            BG_COULOMB_CONSTANT_KCAL_ANGSTROM_PER_MOL_E2 * screened_charge /
            (forcefield.dielectric * distance) * scales.coulomb;
        const DeviceSwitchValue switching = switching_value(
            distance, forcefield.switch_start, forcefield.cutoff);
        contribution.primary_energy = lennard_jones * switching.value;
        contribution.secondary_energy = coulomb * switching.value;
        if (!isfinite(contribution.primary_energy) ||
            !isfinite(contribution.secondary_energy)) {
            set_device_error(error, kDeviceNumericalError);
            contributions[contribution_offset + row] =
                empty_contribution(kNonbondedContribution);
            continue;
        }
        if (compute_forces) {
            const double lennard_jones_derivative =
                24.0 * epsilon * scales.lennard_jones *
                (ratio6 - 2.0 * ratio12) / distance;
            const double coulomb_derivative =
                coulomb * (-forcefield.screening_kappa - 1.0 / distance);
            const double radial_derivative =
                lennard_jones_derivative * switching.value +
                lennard_jones * switching.derivative +
                coulomb_derivative * switching.value +
                coulomb * switching.derivative;
            const DeviceVector3 force =
                vector_scale(delta, -radial_derivative / distance);
            if (!vector_is_finite(force)) {
                set_device_error(error, kDeviceNumericalError);
                contributions[contribution_offset + row] =
                    empty_contribution(kNonbondedContribution);
                continue;
            }
            contribution.force_count = 2U;
            set_contribution_force(&contribution, 0U, pair.atom_i, force);
            set_contribution_force(
                &contribution,
                1U,
                pair.atom_j,
                vector_scale(force, -1.0));
        }
        contributions[contribution_offset + row] = contribution;
    }
}

__device__ bool checked_add_device(double *target, double value) {
    const double updated = *target + value;
    if (!isfinite(value) || !isfinite(updated)) {
        return false;
    }
    *target = updated;
    return true;
}

__device__ bool accumulate_contribution_energy(
    DeviceEnergy *result,
    DeviceContribution contribution) {
    switch (contribution.kind) {
        case kBondContribution:
            return checked_add_device(
                &result->bond, contribution.primary_energy);
        case kAngleContribution:
            return checked_add_device(
                &result->angle, contribution.primary_energy);
        case kTorsionContribution:
            return checked_add_device(
                &result->torsion, contribution.primary_energy);
        case kNonbondedContribution:
            return checked_add_device(
                       &result->lennard_jones,
                       contribution.primary_energy) &&
                   checked_add_device(
                       &result->coulomb,
                       contribution.secondary_energy);
        default:
            return false;
    }
}

__device__ bool accumulate_contribution_magnitude(
    DeviceEnergy *result,
    DeviceContribution contribution) {
    const double primary = fabs(contribution.primary_energy);
    const double secondary = fabs(contribution.secondary_energy);
    switch (contribution.kind) {
        case kBondContribution:
            return checked_add_device(&result->bond, primary) &&
                   checked_add_device(&result->total, primary);
        case kAngleContribution:
            return checked_add_device(&result->angle, primary) &&
                   checked_add_device(&result->total, primary);
        case kTorsionContribution:
            return checked_add_device(&result->torsion, primary) &&
                   checked_add_device(&result->total, primary);
        case kNonbondedContribution:
            return checked_add_device(&result->lennard_jones, primary) &&
                   checked_add_device(&result->coulomb, secondary) &&
                   checked_add_device(&result->total, primary) &&
                   checked_add_device(&result->total, secondary);
        default:
            return false;
    }
}

__global__ void detect_serial_energy_risk_kernel(
    const DeviceContribution *contributions,
    std::size_t contribution_count,
    double risk_threshold,
    int *serial_risk) {
    for (std::size_t row = global_thread_index(); row < contribution_count;
         row += global_thread_stride()) {
        const DeviceContribution contribution = contributions[row];
        if (fabs(contribution.primary_energy) >= risk_threshold ||
            fabs(contribution.secondary_energy) >= risk_threshold) {
            (void)atomicExch(serial_risk, 1);
        }
    }
}

__global__ void reduce_energy_chunks_kernel(
    const DeviceContribution *contributions,
    std::size_t contribution_count,
    std::size_t chunk_count,
    int *serial_risk,
    DeviceEnergy *partials,
    DeviceEnergy *magnitude_partials) {
    for (std::size_t chunk = global_thread_index(); chunk < chunk_count;
         chunk += global_thread_stride()) {
        if (*serial_risk != 0) {
            partials[chunk] = DeviceEnergy{};
            magnitude_partials[chunk] = DeviceEnergy{};
            continue;
        }
        const std::size_t begin = chunk * kEnergyRowsPerChunk;
        const std::size_t remaining = contribution_count - begin;
        const std::size_t row_count =
            remaining < kEnergyRowsPerChunk ? remaining : kEnergyRowsPerChunk;
        const std::size_t end = begin + row_count;
        DeviceEnergy result{};
        DeviceEnergy magnitude{};
        bool valid = true;
        for (std::size_t row = begin; row < end; ++row) {
            const DeviceContribution contribution = contributions[row];
            valid = accumulate_contribution_energy(&result, contribution) &&
                    accumulate_contribution_magnitude(
                        &magnitude, contribution);
            if (!valid) {
                break;
            }
        }
        if (!valid) {
            (void)atomicExch(serial_risk, 1);
            result = DeviceEnergy{};
            magnitude = DeviceEnergy{};
        }
        partials[chunk] = result;
        magnitude_partials[chunk] = magnitude;
    }
}

__device__ bool combine_energy(
    DeviceEnergy *left,
    const DeviceEnergy &right) {
    return checked_add_device(&left->bond, right.bond) &&
           checked_add_device(&left->angle, right.angle) &&
           checked_add_device(&left->torsion, right.torsion) &&
           checked_add_device(&left->lennard_jones, right.lennard_jones) &&
           checked_add_device(&left->coulomb, right.coulomb);
}

__device__ bool combine_energy_magnitude(
    DeviceEnergy *left,
    const DeviceEnergy &right) {
    return combine_energy(left, right) &&
           checked_add_device(&left->total, right.total);
}

__global__ void reduce_energy_tree_kernel(
    DeviceEnergy *partials,
    DeviceEnergy *magnitude_partials,
    std::size_t partial_count,
    std::size_t stride,
    std::size_t work_count,
    int *serial_risk) {
    if (*serial_risk != 0) {
        return;
    }
    const std::size_t span = stride * 2;
    for (std::size_t work = global_thread_index(); work < work_count;
         work += global_thread_stride()) {
        const std::size_t left = work * span;
        const std::size_t right = left + stride;
        if (right < partial_count) {
            const bool valid =
                combine_energy(&partials[left], partials[right]) &&
                combine_energy_magnitude(
                    &magnitude_partials[left], magnitude_partials[right]);
            if (!valid) {
                (void)atomicExch(serial_risk, 1);
                partials[left] = DeviceEnergy{};
                magnitude_partials[left] = DeviceEnergy{};
            }
        }
    }
}

__device__ bool energy_forward_error_threatens_parity(
    double value,
    double magnitude,
    double error_factor) {
    if (magnitude == 0.0) {
        return false;
    }
    const double error_bound = magnitude * error_factor;
    const double tolerance =
        kEnergyParityAbsoluteTolerance +
        kEnergyParityRelativeTolerance * fabs(value);
    return !isfinite(error_bound) || error_bound > tolerance;
}

__global__ void assess_energy_reduction_kernel(
    const DeviceEnergy *energy,
    const DeviceEnergy *magnitude,
    double component_error_factor,
    double total_error_factor,
    int *serial_risk) {
    if (blockIdx.x != 0U || threadIdx.x != 0U || *serial_risk != 0) {
        return;
    }
    const DeviceEnergy value = energy[0];
    const DeviceEnergy absolute_sum = magnitude[0];
    if (energy_forward_error_threatens_parity(
            value.bond, absolute_sum.bond, component_error_factor) ||
        energy_forward_error_threatens_parity(
            value.angle, absolute_sum.angle, component_error_factor) ||
        energy_forward_error_threatens_parity(
            value.torsion, absolute_sum.torsion, component_error_factor) ||
        energy_forward_error_threatens_parity(
            value.lennard_jones,
            absolute_sum.lennard_jones,
            component_error_factor) ||
        energy_forward_error_threatens_parity(
            value.coulomb, absolute_sum.coulomb, component_error_factor)) {
        (void)atomicExch(serial_risk, 1);
        return;
    }

    const double total = value.bond + value.angle + value.torsion +
                         value.lennard_jones + value.coulomb;
    if (!isfinite(total) ||
        energy_forward_error_threatens_parity(
            total, absolute_sum.total, total_error_factor)) {
        (void)atomicExch(serial_risk, 1);
    }
}

__global__ void finalize_energy_kernel(
    DeviceEnergy *energy,
    int *serial_risk) {
    if (blockIdx.x != 0U || threadIdx.x != 0U) {
        return;
    }
    if (*serial_risk != 0) {
        return;
    }
    DeviceEnergy result = energy[0];
    result.total = result.bond + result.angle + result.torsion +
                   result.lennard_jones + result.coulomb;
    if (!isfinite(result.total)) {
        (void)atomicExch(serial_risk, 1);
        result = DeviceEnergy{};
    }
    energy[0] = result;
}

__global__ void reduce_energy_serial_fallback_kernel(
    const DeviceContribution *contributions,
    std::size_t contribution_count,
    const int *serial_risk,
    DeviceEnergy *energy,
    int *error) {
    if (blockIdx.x != 0U || threadIdx.x != 0U || *serial_risk == 0) {
        return;
    }
    DeviceEnergy result{};
    for (std::size_t row = 0; row < contribution_count; ++row) {
        if (!accumulate_contribution_energy(&result, contributions[row])) {
            set_device_error(error, kDeviceNumericalError);
            *energy = DeviceEnergy{};
            return;
        }
    }
    result.total = result.bond + result.angle + result.torsion +
                   result.lennard_jones + result.coulomb;
    if (!isfinite(result.total)) {
        set_device_error(error, kDeviceNumericalError);
        *energy = DeviceEnergy{};
        return;
    }
    *energy = result;
}

struct DeviceForceIncidence final {
    std::size_t contribution;
    uint32_t slot;
    uint32_t reserved;
};

__global__ void count_force_incidences_kernel(
    const DeviceContribution *contributions,
    std::size_t contribution_count,
    std::size_t atom_count,
    std::size_t *incidence_counts,
    int *error) {
    for (std::size_t row = global_thread_index(); row < contribution_count;
         row += global_thread_stride()) {
        const DeviceContribution contribution = contributions[row];
        if (contribution.force_count > 4U) {
            set_device_error(error, kDeviceInternalError);
            continue;
        }
        for (uint32_t slot = 0; slot < contribution.force_count; ++slot) {
            const std::size_t atom = contribution.atoms[slot];
            if (atom >= atom_count) {
                set_device_error(error, kDeviceInternalError);
                continue;
            }
            (void)atomic_increment_size(&incidence_counts[atom]);
        }
    }
}

__global__ void fill_force_incidences_kernel(
    const DeviceContribution *contributions,
    std::size_t contribution_count,
    std::size_t atom_count,
    const std::size_t *incidence_offsets,
    std::size_t *incidence_cursors,
    DeviceForceIncidence *incidences,
    int *error) {
    for (std::size_t row = global_thread_index(); row < contribution_count;
         row += global_thread_stride()) {
        const DeviceContribution contribution = contributions[row];
        if (contribution.force_count > 4U) {
            set_device_error(error, kDeviceInternalError);
            continue;
        }
        for (uint32_t slot = 0; slot < contribution.force_count; ++slot) {
            const std::size_t atom = contribution.atoms[slot];
            if (atom >= atom_count) {
                set_device_error(error, kDeviceInternalError);
                continue;
            }
            const std::size_t rank =
                atomic_increment_size(&incidence_cursors[atom]);
            incidences[incidence_offsets[atom] + rank] = {row, slot, 0U};
        }
    }
}

__device__ bool incidence_less(
    DeviceForceIncidence left,
    DeviceForceIncidence right) {
    return left.contribution < right.contribution ||
           (left.contribution == right.contribution && left.slot < right.slot);
}

struct DeviceForceIncidenceLess final {
    __device__ bool operator()(
        DeviceForceIncidence left,
        DeviceForceIncidence right) const {
        return incidence_less(left, right);
    }
};

__global__ void merge_sort_force_incidence_segments_kernel(
    std::size_t atom_count,
    std::size_t incidence_count,
    const std::size_t *incidence_offsets,
    DeviceForceIncidence *incidences,
    DeviceForceIncidence *scratch,
    int *error) {
    for (std::size_t atom = global_thread_index(); atom < atom_count;
         atom += global_thread_stride()) {
        merge_sort_segment(
            atom,
            incidence_count,
            incidence_offsets,
            incidences,
            scratch,
            DeviceForceIncidenceLess{},
            error);
    }
}

__global__ void reduce_force_incidences_kernel(
    std::size_t atom_count,
    const DeviceContribution *contributions,
    const std::size_t *incidence_offsets,
    const DeviceForceIncidence *incidences,
    double *force_x,
    double *force_y,
    double *force_z,
    int *error) {
    for (std::size_t atom = global_thread_index(); atom < atom_count;
        atom += global_thread_stride()) {
        DeviceVector3 sum{};
        bool valid = true;
        for (std::size_t index = incidence_offsets[atom];
             index < incidence_offsets[atom + 1];
             ++index) {
            const DeviceForceIncidence incidence = incidences[index];
            const DeviceContribution contribution =
                contributions[incidence.contribution];
            if (incidence.slot >= contribution.force_count) {
                valid = false;
                break;
            }
            const DeviceVector3 value = contribution.forces[incidence.slot];
            valid = checked_add_device(&sum.x, value.x) &&
                    checked_add_device(&sum.y, value.y) &&
                    checked_add_device(&sum.z, value.z);
            if (!valid) {
                break;
            }
        }
        if (!valid || !vector_is_finite(sum)) {
            set_device_error(error, kDeviceNumericalError);
            force_x[atom] = 0.0;
            force_y[atom] = 0.0;
            force_z[atom] = 0.0;
            continue;
        }
        force_x[atom] = sum.x;
        force_y[atom] = sum.y;
        force_z[atom] = sum.z;
    }
}

[[nodiscard]] bg_status check_kernel_launch(const char *label) noexcept {
    return check_runtime(hipGetLastError(), label);
}

[[nodiscard]] bg_status merge_sort_neighbor_segments(
    HipState *state,
    std::size_t atom_count,
    std::size_t pair_count,
    const DeviceBuffer<std::size_t> *pair_offsets,
    DeviceBuffer<DevicePair> *pairs,
    DeviceBuffer<DevicePair> *scratch,
    DeviceBuffer<int> *device_error) noexcept {
    if (pair_count < 2) {
        return BG_STATUS_OK;
    }
    if (pair_offsets == nullptr || pairs == nullptr || scratch == nullptr ||
        device_error == nullptr || device_error->size() < 1 ||
        pair_offsets->size() <= atom_count || pairs->size() < pair_count ||
        scratch->size() < pair_count) {
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "HIP neighbor merge-sort storage is inconsistent");
    }
    const unsigned int blocks = launch_block_count(atom_count);
    if (blocks == 0U) {
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "HIP neighbor merge-sort has no segments");
    }
    hipLaunchKernelGGL(
        merge_sort_neighbor_segments_kernel,
        dim3(blocks),
        dim3(kThreadsPerBlock),
        0,
        state->stream,
        atom_count,
        pair_count,
        pair_offsets->get(),
        pairs->get(),
        scratch->get(),
        device_error->get());
    return check_kernel_launch("HIP neighbor merge-sort kernel launch");
}

[[nodiscard]] bg_status merge_sort_force_incidence_segments(
    HipState *state,
    std::size_t atom_count,
    std::size_t incidence_count,
    const DeviceBuffer<std::size_t> *incidence_offsets,
    DeviceBuffer<DeviceForceIncidence> *incidences,
    DeviceBuffer<DeviceForceIncidence> *scratch,
    DeviceBuffer<int> *device_error) noexcept {
    if (incidence_count < 2) {
        return BG_STATUS_OK;
    }
    if (incidence_offsets == nullptr || incidences == nullptr ||
        scratch == nullptr || device_error == nullptr ||
        device_error->size() < 1 ||
        incidence_offsets->size() <= atom_count ||
        incidences->size() < incidence_count ||
        scratch->size() < incidence_count) {
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "HIP force-incidence merge-sort storage is inconsistent");
    }
    const unsigned int blocks = launch_block_count(atom_count);
    if (blocks == 0U) {
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "HIP force-incidence merge-sort has no segments");
    }
    hipLaunchKernelGGL(
        merge_sort_force_incidence_segments_kernel,
        dim3(blocks),
        dim3(kThreadsPerBlock),
        0,
        state->stream,
        atom_count,
        incidence_count,
        incidence_offsets->get(),
        incidences->get(),
        scratch->get(),
        device_error->get());
    return check_kernel_launch(
        "HIP force-incidence merge-sort kernel launch");
}

[[nodiscard]] bg_status synchronize(
    hipStream_t stream,
    const char *label) noexcept {
    return check_runtime(hipStreamSynchronize(stream), label);
}

[[nodiscard]] bg_status device_error_status(int error) noexcept {
    if (error == kDeviceOk) {
        return BG_STATUS_OK;
    }
    if (error == kDeviceNumericalError) {
        return fail(
            BG_STATUS_NUMERICAL_ERROR,
            "HIP evaluator produced invalid geometry or non-finite arithmetic");
    }
    return fail(
        BG_STATUS_INTERNAL_ERROR,
        "HIP evaluator detected an inconsistent device work row");
}

struct DeviceInputs final {
    DeviceBuffer<double> position_x;
    DeviceBuffer<double> position_y;
    DeviceBuffer<double> position_z;
    DeviceBuffer<double> charge;
    DeviceBuffer<double> sigma;
    DeviceBuffer<double> epsilon;

    DeviceBuffer<std::size_t> bond_i;
    DeviceBuffer<std::size_t> bond_j;
    DeviceBuffer<double> bond_equilibrium;
    DeviceBuffer<double> bond_force_constant;

    DeviceBuffer<std::size_t> angle_i;
    DeviceBuffer<std::size_t> angle_j;
    DeviceBuffer<std::size_t> angle_k;
    DeviceBuffer<double> angle_equilibrium;
    DeviceBuffer<double> angle_force_constant;

    DeviceBuffer<std::size_t> torsion_i;
    DeviceBuffer<std::size_t> torsion_j;
    DeviceBuffer<std::size_t> torsion_k;
    DeviceBuffer<std::size_t> torsion_l;
    DeviceBuffer<uint32_t> torsion_periodicity;
    DeviceBuffer<double> torsion_phase;
    DeviceBuffer<double> torsion_amplitude;

    std::vector<DevicePair> host_exclusions;
    std::vector<DevicePairScale> host_pair_scales;
    DeviceBuffer<DevicePair> exclusions;
    DeviceBuffer<DevicePairScale> pair_scales;

    DeviceSystemView system_view{};
    DeviceForceFieldView forcefield_view{};

    bg_status upload(
        const bg_system &system,
        const bg_forcefield &forcefield,
        HipState *state) {
        hipStream_t stream = state->stream;
#define BG_UPLOAD(BUFFER, SOURCE)                                              \
    do {                                                                       \
        const bg_status upload_status = allocate_and_upload(                   \
            &(BUFFER),                                                         \
            (SOURCE),                                                          \
            stream,                                                            \
            state,                                                             \
            "hipMalloc evaluator input",                                     \
            "hipMemcpyAsync evaluator input");                               \
        if (upload_status != BG_STATUS_OK) {                                   \
            return upload_status;                                              \
        }                                                                      \
    } while (false)

        BG_UPLOAD(position_x, system.position_x);
        BG_UPLOAD(position_y, system.position_y);
        BG_UPLOAD(position_z, system.position_z);
        BG_UPLOAD(charge, system.charge);
        BG_UPLOAD(sigma, forcefield.sigma);
        BG_UPLOAD(epsilon, forcefield.epsilon);

        BG_UPLOAD(bond_i, forcefield.bonds.atom_i);
        BG_UPLOAD(bond_j, forcefield.bonds.atom_j);
        BG_UPLOAD(bond_equilibrium, forcefield.bonds.equilibrium);
        BG_UPLOAD(bond_force_constant, forcefield.bonds.force_constant);

        BG_UPLOAD(angle_i, forcefield.angles.atom_i);
        BG_UPLOAD(angle_j, forcefield.angles.atom_j);
        BG_UPLOAD(angle_k, forcefield.angles.atom_k);
        BG_UPLOAD(angle_equilibrium, forcefield.angles.equilibrium);
        BG_UPLOAD(angle_force_constant, forcefield.angles.force_constant);

        BG_UPLOAD(torsion_i, forcefield.torsions.atom_i);
        BG_UPLOAD(torsion_j, forcefield.torsions.atom_j);
        BG_UPLOAD(torsion_k, forcefield.torsions.atom_k);
        BG_UPLOAD(torsion_l, forcefield.torsions.atom_l);
        BG_UPLOAD(torsion_periodicity, forcefield.torsions.periodicity);
        BG_UPLOAD(torsion_phase, forcefield.torsions.phase);
        BG_UPLOAD(torsion_amplitude, forcefield.torsions.amplitude);

        host_exclusions.reserve(forcefield.exclusions.size());
        for (const bg_forcefield::Pair &pair : forcefield.exclusions) {
            host_exclusions.push_back({pair.atom_i, pair.atom_j});
        }
        host_pair_scales.reserve(forcefield.pair_scales.size());
        for (const bg_forcefield::PairScale &scale : forcefield.pair_scales) {
            host_pair_scales.push_back({
                {scale.pair.atom_i, scale.pair.atom_j},
                scale.lennard_jones,
                scale.coulomb,
            });
        }
        BG_UPLOAD(exclusions, host_exclusions);
        BG_UPLOAD(pair_scales, host_pair_scales);
#undef BG_UPLOAD

        system_view = {
            system.position_x.size(),
            position_x.get(),
            position_y.get(),
            position_z.get(),
            charge.get(),
        };
        forcefield_view.atom_count = forcefield.atom_count;
        forcefield_view.sigma = sigma.get();
        forcefield_view.epsilon = epsilon.get();

        forcefield_view.bond_count = forcefield.bonds.atom_i.size();
        forcefield_view.bond_i = bond_i.get();
        forcefield_view.bond_j = bond_j.get();
        forcefield_view.bond_equilibrium = bond_equilibrium.get();
        forcefield_view.bond_force_constant = bond_force_constant.get();

        forcefield_view.angle_count = forcefield.angles.atom_i.size();
        forcefield_view.angle_i = angle_i.get();
        forcefield_view.angle_j = angle_j.get();
        forcefield_view.angle_k = angle_k.get();
        forcefield_view.angle_equilibrium = angle_equilibrium.get();
        forcefield_view.angle_force_constant = angle_force_constant.get();

        forcefield_view.torsion_count = forcefield.torsions.atom_i.size();
        forcefield_view.torsion_i = torsion_i.get();
        forcefield_view.torsion_j = torsion_j.get();
        forcefield_view.torsion_k = torsion_k.get();
        forcefield_view.torsion_l = torsion_l.get();
        forcefield_view.torsion_periodicity = torsion_periodicity.get();
        forcefield_view.torsion_phase = torsion_phase.get();
        forcefield_view.torsion_amplitude = torsion_amplitude.get();

        forcefield_view.exclusion_count = host_exclusions.size();
        forcefield_view.exclusions = exclusions.get();
        forcefield_view.pair_scale_count = host_pair_scales.size();
        forcefield_view.pair_scales = pair_scales.get();
        forcefield_view.periodic_axes_mask = forcefield.periodic_axes_mask;
        for (std::size_t axis = 0; axis < 3; ++axis) {
            forcefield_view.cell_lengths[axis] =
                forcefield.cell_lengths[axis];
        }
        forcefield_view.cutoff = forcefield.cutoff;
        forcefield_view.switch_start = forcefield.switch_start;
        forcefield_view.dielectric = forcefield.dielectric;
        forcefield_view.screening_kappa = forcefield.screening_kappa;
        forcefield_view.minimum_pair_distance =
            forcefield.minimum_pair_distance;
        return BG_STATUS_OK;
    }
};

[[nodiscard]] bg_status allocate_buffer_set(
    HipState *state,
    std::size_t atom_count,
    std::size_t cell_count,
    DeviceBuffer<int> *device_error,
    DeviceBuffer<std::size_t> *atom_cells,
    DeviceBuffer<std::size_t> *cell_counts,
    DeviceBuffer<std::size_t> *cell_offsets,
    DeviceBuffer<std::size_t> *cell_atoms,
    DeviceBuffer<std::size_t> *pair_counts,
    DeviceBuffer<std::size_t> *pair_offsets) noexcept {
    std::size_t cell_offset_count = 0;
    std::size_t pair_offset_count = 0;
    if (!detail::checked_add_size(cell_count, 1, &cell_offset_count) ||
        !detail::checked_add_size(atom_count, 1, &pair_offset_count)) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "HIP offset row count overflows size_t");
    }
#define BG_ALLOCATE(BUFFER, COUNT, LABEL)                                      \
    do {                                                                       \
        const bg_status allocation_status =                                   \
            (BUFFER)->allocate((COUNT), (LABEL), state);                       \
        if (allocation_status != BG_STATUS_OK) {                               \
            return allocation_status;                                         \
        }                                                                      \
    } while (false)
    BG_ALLOCATE(device_error, 1, "hipMalloc device error row");
    BG_ALLOCATE(atom_cells, atom_count, "hipMalloc atom cell ids");
    BG_ALLOCATE(cell_counts, cell_count, "hipMalloc cell counts");
    BG_ALLOCATE(cell_offsets, cell_offset_count, "hipMalloc cell offsets");
    BG_ALLOCATE(cell_atoms, atom_count, "hipMalloc cell atom rows");
    BG_ALLOCATE(pair_counts, atom_count, "hipMalloc neighbor counts");
    BG_ALLOCATE(pair_offsets, pair_offset_count, "hipMalloc neighbor offsets");
#undef BG_ALLOCATE
    return device_error->zero(state->stream, "hipMemsetAsync device error row");
}

[[nodiscard]] bg_status build_neighbor_list(
    HipState *state,
    DeviceSystemView system,
    DeviceForceFieldView forcefield,
    DeviceGrid grid,
    DeviceBuffer<int> *device_error,
    DeviceBuffer<std::size_t> *atom_cells,
    DeviceBuffer<std::size_t> *cell_counts,
    DeviceBuffer<std::size_t> *cell_offsets,
    DeviceBuffer<std::size_t> *cell_atoms,
    DeviceBuffer<std::size_t> *pair_counts,
    DeviceBuffer<std::size_t> *pair_offsets,
    DeviceBuffer<DevicePair> *pairs,
    DeviceBuffer<DevicePair> *pair_sort_scratch,
    std::size_t *out_pair_count) noexcept {
    const unsigned int atom_blocks = launch_block_count(system.atom_count);
    bg_status status = cell_counts->zero(
        state->stream, "hipMemsetAsync cell counts");
    if (status != BG_STATUS_OK) {
        return status;
    }
    hipLaunchKernelGGL(
        assign_cell_ids_kernel,
        dim3(atom_blocks),
        dim3(kThreadsPerBlock),
        0,
        state->stream,
        system,
        grid,
        atom_cells->get(),
        cell_counts->get(),
        device_error->get());
    status = check_kernel_launch("HIP assign-cell/count kernel launch");
    if (status != BG_STATUS_OK) {
        return status;
    }
    hipLaunchKernelGGL(
        prefix_cell_counts_kernel,
        dim3(1U),
        dim3(1U),
        0,
        state->stream,
        grid,
        cell_counts->get(),
        cell_offsets->get(),
        device_error->get());
    status = check_kernel_launch("HIP cell-prefix kernel launch");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = cell_counts->zero(
        state->stream, "hipMemsetAsync cell fill cursors");
    if (status != BG_STATUS_OK) {
        return status;
    }
    hipLaunchKernelGGL(
        fill_cell_atoms_kernel,
        dim3(atom_blocks),
        dim3(kThreadsPerBlock),
        0,
        state->stream,
        system.atom_count,
        atom_cells->get(),
        cell_offsets->get(),
        cell_counts->get(),
        cell_atoms->get());
    status = check_kernel_launch("HIP cell-fill kernel launch");
    if (status != BG_STATUS_OK) {
        return status;
    }
    hipLaunchKernelGGL(
        count_neighbor_pairs_kernel,
        dim3(atom_blocks),
        dim3(kThreadsPerBlock),
        0,
        state->stream,
        system,
        forcefield,
        grid,
        atom_cells->get(),
        cell_offsets->get(),
        cell_atoms->get(),
        pair_counts->get(),
        device_error->get());
    status = check_kernel_launch("HIP neighbor-count kernel launch");
    if (status != BG_STATUS_OK) {
        return status;
    }
    hipLaunchKernelGGL(
        prefix_pair_counts_kernel,
        dim3(1U),
        dim3(1U),
        0,
        state->stream,
        system.atom_count,
        pair_counts->get(),
        pair_offsets->get(),
        device_error->get());
    status = check_kernel_launch("HIP neighbor-prefix kernel launch");
    if (status != BG_STATUS_OK) {
        return status;
    }

    std::size_t pair_count = 0;
    std::size_t cell_atom_total = 0;
    int observed_device_error = kDeviceOk;
    status = check_runtime(
        hipMemcpyAsync(
            &pair_count,
            pair_offsets->get() + system.atom_count,
            sizeof(pair_count),
            hipMemcpyDeviceToHost,
            state->stream),
        "hipMemcpyAsync neighbor pair total");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = check_runtime(
        hipMemcpyAsync(
            &cell_atom_total,
            cell_offsets->get() + grid.cell_count,
            sizeof(cell_atom_total),
            hipMemcpyDeviceToHost,
            state->stream),
        "hipMemcpyAsync cell atom total");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = device_error->copy_to_host(
        &observed_device_error,
        1,
        state->stream,
        "hipMemcpyAsync neighbor device status");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = synchronize(state->stream, "HIP neighbor count synchronization");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = device_error_status(observed_device_error);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (cell_atom_total != system.atom_count) {
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "HIP cell list did not contain every atom exactly once");
    }
    std::size_t maximum_pair_count = 0;
    if (!detail::checked_triangular_pair_count(
            system.atom_count, &maximum_pair_count) ||
        pair_count > maximum_pair_count) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "HIP neighbor pair count exceeds canonical pair capacity");
    }
    status = pairs->allocate(pair_count, "hipMalloc neighbor pairs", state);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (pair_count > 1) {
        if (pair_sort_scratch == nullptr) {
            return fail(
                BG_STATUS_INTERNAL_ERROR,
                "HIP neighbor merge-sort scratch is null");
        }
        status = pair_sort_scratch->allocate(
            pair_count, "hipMalloc neighbor sort scratch", state);
        if (status != BG_STATUS_OK) {
            return status;
        }
    }
    if (pair_count != 0) {
        hipLaunchKernelGGL(
            fill_neighbor_pairs_kernel,
            dim3(atom_blocks),
            dim3(kThreadsPerBlock),
            0,
            state->stream,
            system,
            forcefield,
            grid,
            atom_cells->get(),
            cell_offsets->get(),
            cell_atoms->get(),
            pair_offsets->get(),
            pairs->get(),
            device_error->get());
        status = check_kernel_launch("HIP neighbor-fill kernel launch");
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = merge_sort_neighbor_segments(
            state,
            system.atom_count,
            pair_count,
            pair_offsets,
            pairs,
            pair_sort_scratch,
            device_error);
        if (status != BG_STATUS_OK) {
            return status;
        }
    }
    *out_pair_count = pair_count;
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status build_direct_neighbor_list(
    HipState *state,
    DeviceSystemView system,
    DeviceForceFieldView forcefield,
    DeviceBuffer<int> *device_error,
    DeviceBuffer<std::size_t> *pair_counts,
    DeviceBuffer<std::size_t> *pair_offsets,
    DeviceBuffer<DevicePair> *pairs,
    std::size_t *out_pair_count) noexcept {
    bg_status status = device_error->allocate(
        1, "hipMalloc direct device error row", state);
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = pair_counts->allocate(
        system.atom_count, "hipMalloc direct neighbor counts", state);
    if (status != BG_STATUS_OK) {
        return status;
    }
    std::size_t offset_count = 0;
    if (!detail::checked_add_size(system.atom_count, 1, &offset_count)) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "HIP direct neighbor offset count overflows size_t");
    }
    status = pair_offsets->allocate(
        offset_count, "hipMalloc direct neighbor offsets", state);
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = device_error->zero(
        state->stream, "hipMemsetAsync direct device error row");
    if (status != BG_STATUS_OK) {
        return status;
    }

    const unsigned int atom_blocks = launch_block_count(system.atom_count);
    hipLaunchKernelGGL(
        count_direct_neighbor_pairs_kernel,
        dim3(atom_blocks),
        dim3(kThreadsPerBlock),
        0,
        state->stream,
        system,
        forcefield,
        pair_counts->get(),
        device_error->get());
    status = check_kernel_launch("HIP direct neighbor-count kernel launch");
    if (status != BG_STATUS_OK) {
        return status;
    }
    hipLaunchKernelGGL(
        prefix_pair_counts_kernel,
        dim3(1U),
        dim3(1U),
        0,
        state->stream,
        system.atom_count,
        pair_counts->get(),
        pair_offsets->get(),
        device_error->get());
    status = check_kernel_launch("HIP direct neighbor-prefix kernel launch");
    if (status != BG_STATUS_OK) {
        return status;
    }

    std::size_t pair_count = 0;
    int observed_device_error = kDeviceOk;
    status = check_runtime(
        hipMemcpyAsync(
            &pair_count,
            pair_offsets->get() + system.atom_count,
            sizeof(pair_count),
            hipMemcpyDeviceToHost,
            state->stream),
        "hipMemcpyAsync direct neighbor pair total");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = device_error->copy_to_host(
        &observed_device_error,
        1,
        state->stream,
        "hipMemcpyAsync direct neighbor device status");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = synchronize(
        state->stream, "HIP direct neighbor count synchronization");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = device_error_status(observed_device_error);
    if (status != BG_STATUS_OK) {
        return status;
    }
    std::size_t maximum_pair_count = 0;
    if (!detail::checked_triangular_pair_count(
            system.atom_count, &maximum_pair_count) ||
        pair_count > maximum_pair_count) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "HIP direct neighbor count exceeds canonical pair capacity");
    }
    status = pairs->allocate(
        pair_count, "hipMalloc direct neighbor pairs", state);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (pair_count != 0) {
        hipLaunchKernelGGL(
            fill_direct_neighbor_pairs_kernel,
            dim3(atom_blocks),
            dim3(kThreadsPerBlock),
            0,
            state->stream,
            system,
            forcefield,
            pair_offsets->get(),
            pairs->get(),
            device_error->get());
        status = check_kernel_launch("HIP direct neighbor-fill kernel launch");
        if (status != BG_STATUS_OK) {
            return status;
        }
    }
    *out_pair_count = pair_count;
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status reduce_forces_by_incidence(
    HipState *state,
    std::size_t atom_count,
    DeviceBuffer<DeviceContribution> *contributions,
    std::size_t contribution_count,
    DeviceBuffer<int> *device_error,
    DeviceBuffer<std::size_t> *incidence_counts,
    DeviceBuffer<std::size_t> *incidence_offsets,
    DeviceBuffer<std::size_t> *reusable_cursors,
    DeviceBuffer<double> *force_x,
    DeviceBuffer<double> *force_y,
    DeviceBuffer<double> *force_z) noexcept {
    std::size_t maximum_incidence_count = 0;
    if (!detail::checked_multiply_size(
            contribution_count,
            std::size_t{4},
            &maximum_incidence_count)) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "HIP force incidence capacity overflows size_t");
    }
    bg_status status = incidence_counts->zero(
        state->stream, "hipMemsetAsync force incidence counts");
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (contribution_count != 0) {
        hipLaunchKernelGGL(
            count_force_incidences_kernel,
            dim3(launch_block_count(contribution_count)),
            dim3(kThreadsPerBlock),
            0,
            state->stream,
            contributions->get(),
            contribution_count,
            atom_count,
            incidence_counts->get(),
            device_error->get());
        status = check_kernel_launch("HIP force-incidence count kernel launch");
        if (status != BG_STATUS_OK) {
            return status;
        }
    }
    hipLaunchKernelGGL(
        prefix_pair_counts_kernel,
        dim3(1U),
        dim3(1U),
        0,
        state->stream,
        atom_count,
        incidence_counts->get(),
        incidence_offsets->get(),
        device_error->get());
    status = check_kernel_launch("HIP force-incidence prefix kernel launch");
    if (status != BG_STATUS_OK) {
        return status;
    }

    std::size_t incidence_count = 0;
    int observed_device_error = kDeviceOk;
    status = check_runtime(
        hipMemcpyAsync(
            &incidence_count,
            incidence_offsets->get() + atom_count,
            sizeof(incidence_count),
            hipMemcpyDeviceToHost,
            state->stream),
        "hipMemcpyAsync force incidence total");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = device_error->copy_to_host(
        &observed_device_error,
        1,
        state->stream,
        "hipMemcpyAsync force incidence device status");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = synchronize(
        state->stream, "HIP force incidence count synchronization");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = device_error_status(observed_device_error);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (incidence_count > maximum_incidence_count) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "HIP force incidence count exceeds contribution capacity");
    }

    DeviceBuffer<std::size_t> owned_cursors;
    DeviceBuffer<std::size_t> *cursors = reusable_cursors;
    if (reusable_cursors->size() < atom_count) {
        status = owned_cursors.allocate(
            atom_count, "hipMalloc force incidence cursors", state);
        if (status != BG_STATUS_OK) {
            return status;
        }
        cursors = &owned_cursors;
    }
    status = cursors->zero(
        state->stream, "hipMemsetAsync force incidence cursors");
    if (status != BG_STATUS_OK) {
        return status;
    }
    DeviceBuffer<DeviceForceIncidence> incidences;
    status = incidences.allocate(
        incidence_count, "hipMalloc force incidences", state);
    if (status != BG_STATUS_OK) {
        return status;
    }
    DeviceBuffer<DeviceForceIncidence> incidence_sort_scratch;
    if (incidence_count > 1) {
        status = incidence_sort_scratch.allocate(
            incidence_count,
            "hipMalloc force incidence sort scratch",
            state);
        if (status != BG_STATUS_OK) {
            return status;
        }
    }
    if (contribution_count != 0) {
        hipLaunchKernelGGL(
            fill_force_incidences_kernel,
            dim3(launch_block_count(contribution_count)),
            dim3(kThreadsPerBlock),
            0,
            state->stream,
            contributions->get(),
            contribution_count,
            atom_count,
            incidence_offsets->get(),
            cursors->get(),
            incidences.get(),
            device_error->get());
        status = check_kernel_launch("HIP force-incidence fill kernel launch");
        if (status != BG_STATUS_OK) {
            return status;
        }
    }
    status = merge_sort_force_incidence_segments(
        state,
        atom_count,
        incidence_count,
        incidence_offsets,
        &incidences,
        &incidence_sort_scratch,
        device_error);
    if (status != BG_STATUS_OK) {
        return status;
    }
    hipLaunchKernelGGL(
        reduce_force_incidences_kernel,
        dim3(launch_block_count(atom_count)),
        dim3(kThreadsPerBlock),
        0,
        state->stream,
        atom_count,
        contributions->get(),
        incidence_offsets->get(),
        incidences.get(),
        force_x->get(),
        force_y->get(),
        force_z->get(),
        device_error->get());
    status = check_kernel_launch("HIP force-incidence reduction kernel launch");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = device_error->copy_to_host(
        &observed_device_error,
        1,
        state->stream,
        "hipMemcpyAsync force reduction device status");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = synchronize(
        state->stream, "HIP force incidence reduction synchronization");
    if (status != BG_STATUS_OK) {
        return status;
    }
    return device_error_status(observed_device_error);
}

[[nodiscard]] bg_status run_evaluator(
    HipState *state,
    const bg_system &system,
    const bg_forcefield &forcefield,
    bool compute_forces,
    cpu::Evaluation *out_evaluation) {
    if (forcefield.atom_count == 0) {
        cpu::Evaluation candidate;
        candidate.energy.struct_size =
            static_cast<uint32_t>(sizeof(bg_energy_components_v1));
        candidate.energy.abi_version = BG_ABI_VERSION;
        candidate.energy.unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        /* Empty force vectors are already the canonical SoA result. */
        state->last_stats = EvaluationStats{};
        *out_evaluation = std::move(candidate);
        return BG_STATUS_OK;
    }

    DeviceGrid grid{};
    bg_status status = build_grid(system, forcefield, &grid);
    if (status != BG_STATUS_OK) {
        return status;
    }

    const std::size_t bond_count = forcefield.bonds.atom_i.size();
    const std::size_t angle_count = forcefield.angles.atom_i.size();
    const std::size_t torsion_count = forcefield.torsions.atom_i.size();
    detail::SizePlan initial_plan;
    status = detail::make_size_plan(
        static_cast<uint64_t>(forcefield.atom_count),
        static_cast<uint64_t>(bond_count),
        static_cast<uint64_t>(angle_count),
        static_cast<uint64_t>(torsion_count),
        static_cast<uint64_t>(grid.cell_count),
        UINT64_C(0),
        compute_forces,
        &initial_plan);
    if (status != BG_STATUS_OK) {
        return fail(status, "HIP evaluator allocation plan overflows");
    }

    state->allocation_attempt_count = 0;
    DeviceInputs inputs;
    status = inputs.upload(system, forcefield, state);
    if (status != BG_STATUS_OK) {
        return status;
    }

    DeviceBuffer<int> device_error;
    DeviceBuffer<std::size_t> atom_cells;
    DeviceBuffer<std::size_t> cell_counts;
    DeviceBuffer<std::size_t> cell_offsets;
    DeviceBuffer<std::size_t> cell_atoms;
    DeviceBuffer<std::size_t> pair_counts;
    DeviceBuffer<std::size_t> pair_offsets;
    DeviceBuffer<DevicePair> pairs;
    DeviceBuffer<DevicePair> pair_sort_scratch;
    std::size_t pair_count = 0;
    if (grid.cell_count == 0) {
        status = build_direct_neighbor_list(
            state,
            inputs.system_view,
            inputs.forcefield_view,
            &device_error,
            &pair_counts,
            &pair_offsets,
            &pairs,
            &pair_count);
    } else {
        status = allocate_buffer_set(
            state,
            forcefield.atom_count,
            grid.cell_count,
            &device_error,
            &atom_cells,
            &cell_counts,
            &cell_offsets,
            &cell_atoms,
            &pair_counts,
            &pair_offsets);
        if (status == BG_STATUS_OK) {
            status = build_neighbor_list(
                state,
                inputs.system_view,
                inputs.forcefield_view,
                grid,
                &device_error,
                &atom_cells,
                &cell_counts,
                &cell_offsets,
                &cell_atoms,
                &pair_counts,
                &pair_offsets,
                &pairs,
                &pair_sort_scratch,
                &pair_count);
        }
    }
    if (status != BG_STATUS_OK) {
        return status;
    }

    detail::SizePlan final_plan;
    status = detail::make_size_plan(
        static_cast<uint64_t>(forcefield.atom_count),
        static_cast<uint64_t>(bond_count),
        static_cast<uint64_t>(angle_count),
        static_cast<uint64_t>(torsion_count),
        static_cast<uint64_t>(grid.cell_count),
        static_cast<uint64_t>(pair_count),
        compute_forces,
        &final_plan);
    if (status != BG_STATUS_OK) {
        return fail(status, "HIP contribution allocation plan overflows");
    }

    const std::size_t angle_offset = bond_count;
    std::size_t torsion_offset = 0;
    std::size_t nonbonded_offset = 0;
    if (!detail::checked_add_size(
            angle_offset, angle_count, &torsion_offset) ||
        !detail::checked_add_size(
            torsion_offset, torsion_count, &nonbonded_offset) ||
        nonbonded_offset != final_plan.bonded_contribution_count) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "HIP bonded contribution offsets overflow size_t");
    }

    DeviceBuffer<DeviceContribution> contributions;
    status = contributions.allocate(
        final_plan.contribution_count,
        "hipMalloc evaluator contributions",
        state);
    if (status != BG_STATUS_OK) {
        return status;
    }
    DeviceBuffer<DeviceEnergy> device_energy;
    const std::size_t energy_partial_count =
        final_plan.contribution_count == 0
            ? std::size_t{1}
            : (final_plan.contribution_count - 1) / kEnergyRowsPerChunk + 1;
    std::size_t energy_storage_count = 0;
    if (!detail::checked_multiply_size(
            energy_partial_count, std::size_t{2}, &energy_storage_count)) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "HIP energy and magnitude partial count overflows size_t");
    }
    status = device_energy.allocate(
        energy_storage_count, "hipMalloc reduced energy", state);
    if (status != BG_STATUS_OK) {
        return status;
    }
    DeviceEnergy *const device_energy_magnitude =
        device_energy.get() + energy_partial_count;
    DeviceBuffer<int> serial_energy_risk;
    status = serial_energy_risk.allocate(
        1, "hipMalloc serial energy risk row", state);
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = serial_energy_risk.zero(
        state->stream, "hipMemsetAsync serial energy risk row");
    if (status != BG_STATUS_OK) {
        return status;
    }
    DeviceBuffer<double> device_force_x;
    DeviceBuffer<double> device_force_y;
    DeviceBuffer<double> device_force_z;
    if (compute_forces) {
        status = device_force_x.allocate(
            forcefield.atom_count, "hipMalloc force x", state);
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = device_force_y.allocate(
            forcefield.atom_count, "hipMalloc force y", state);
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = device_force_z.allocate(
            forcefield.atom_count, "hipMalloc force z", state);
        if (status != BG_STATUS_OK) {
            return status;
        }
    }

    if (bond_count != 0) {
        hipLaunchKernelGGL(
            evaluate_bonds_kernel,
            dim3(launch_block_count(bond_count)),
            dim3(kThreadsPerBlock),
            0,
            state->stream,
            inputs.system_view,
            inputs.forcefield_view,
            compute_forces,
            contributions.get(),
            device_error.get());
        status = check_kernel_launch("HIP bond kernel launch");
        if (status != BG_STATUS_OK) {
            return status;
        }
    }
    if (angle_count != 0) {
        hipLaunchKernelGGL(
            evaluate_angles_kernel,
            dim3(launch_block_count(angle_count)),
            dim3(kThreadsPerBlock),
            0,
            state->stream,
            inputs.system_view,
            inputs.forcefield_view,
            compute_forces,
            angle_offset,
            contributions.get(),
            device_error.get());
        status = check_kernel_launch("HIP angle kernel launch");
        if (status != BG_STATUS_OK) {
            return status;
        }
    }
    if (torsion_count != 0) {
        hipLaunchKernelGGL(
            evaluate_torsions_kernel,
            dim3(launch_block_count(torsion_count)),
            dim3(kThreadsPerBlock),
            0,
            state->stream,
            inputs.system_view,
            inputs.forcefield_view,
            compute_forces,
            torsion_offset,
            contributions.get(),
            device_error.get());
        status = check_kernel_launch("HIP torsion kernel launch");
        if (status != BG_STATUS_OK) {
            return status;
        }
    }
    if (pair_count != 0) {
        hipLaunchKernelGGL(
            evaluate_nonbonded_kernel,
            dim3(launch_block_count(pair_count)),
            dim3(kThreadsPerBlock),
            0,
            state->stream,
            inputs.system_view,
            inputs.forcefield_view,
            compute_forces,
            pairs.get(),
            pair_count,
            nonbonded_offset,
            contributions.get(),
            device_error.get());
        status = check_kernel_launch("HIP nonbonded kernel launch");
        if (status != BG_STATUS_OK) {
            return status;
        }
    }
    if (final_plan.contribution_count != 0) {
        const double risk_denominator =
            2.0 * static_cast<double>(final_plan.contribution_count);
        const double risk_threshold = std::nextafter(
            std::numeric_limits<double>::max() / risk_denominator, 0.0);
        hipLaunchKernelGGL(
            detect_serial_energy_risk_kernel,
            dim3(launch_block_count(final_plan.contribution_count)),
            dim3(kThreadsPerBlock),
            0,
            state->stream,
            contributions.get(),
            final_plan.contribution_count,
            risk_threshold,
            serial_energy_risk.get());
        status = check_kernel_launch("HIP serial-energy risk kernel launch");
        if (status != BG_STATUS_OK) {
            return status;
        }
    }
    hipLaunchKernelGGL(
        reduce_energy_chunks_kernel,
        dim3(launch_block_count(energy_partial_count)),
        dim3(kThreadsPerBlock),
        0,
        state->stream,
        contributions.get(),
        final_plan.contribution_count,
        energy_partial_count,
        serial_energy_risk.get(),
        device_energy.get(),
        device_energy_magnitude);
    status = check_kernel_launch("HIP energy chunk reduction launch");
    if (status != BG_STATUS_OK) {
        return status;
    }
    for (std::size_t stride = 1; stride < energy_partial_count;) {
        std::size_t span = 0;
        if (!detail::checked_multiply_size(stride, std::size_t{2}, &span)) {
            return fail(
                BG_STATUS_CAPACITY_OVERFLOW,
                "HIP energy reduction stride overflows size_t");
        }
        const std::size_t work_count =
            (energy_partial_count - 1) / span + 1;
        hipLaunchKernelGGL(
            reduce_energy_tree_kernel,
            dim3(launch_block_count(work_count)),
            dim3(kThreadsPerBlock),
            0,
            state->stream,
            device_energy.get(),
            device_energy_magnitude,
            energy_partial_count,
            stride,
            work_count,
            serial_energy_risk.get());
        status = check_kernel_launch("HIP energy tree reduction launch");
        if (status != BG_STATUS_OK) {
            return status;
        }
        stride = span;
    }
    const long double unit_roundoff =
        static_cast<long double>(std::numeric_limits<double>::epsilon()) /
        2.0L;
    const auto forward_error_factor = [unit_roundoff](
                                          long double addition_count) noexcept {
        const long double accumulated_roundoff =
            addition_count * unit_roundoff;
        if (accumulated_roundoff >= 1.0L) {
            return std::numeric_limits<double>::infinity();
        }
        const long double gamma =
            accumulated_roundoff / (1.0L - accumulated_roundoff);
        const long double cpu_and_hip_bound = 2.0L * gamma;
        if (cpu_and_hip_bound > static_cast<long double>(
                                         std::numeric_limits<double>::max())) {
            return std::numeric_limits<double>::infinity();
        }
        return static_cast<double>(cpu_and_hip_bound);
    };
    const long double contribution_count_as_long_double =
        static_cast<long double>(final_plan.contribution_count);
    const double component_error_factor =
        forward_error_factor(contribution_count_as_long_double);
    // A nonbonded row has two component energies, and final total formation
    // adds the five component totals in fixed CPU order.
    const double total_error_factor = forward_error_factor(
        2.0L * contribution_count_as_long_double + 5.0L);
    hipLaunchKernelGGL(
        assess_energy_reduction_kernel,
        dim3(1U),
        dim3(1U),
        0,
        state->stream,
        device_energy.get(),
        device_energy_magnitude,
        component_error_factor,
        total_error_factor,
        serial_energy_risk.get());
    status = check_kernel_launch("HIP energy reduction assessment launch");
    if (status != BG_STATUS_OK) {
        return status;
    }
    hipLaunchKernelGGL(
        finalize_energy_kernel,
        dim3(1U),
        dim3(1U),
        0,
        state->stream,
        device_energy.get(),
        serial_energy_risk.get());
    status = check_kernel_launch("HIP energy finalization launch");
    if (status != BG_STATUS_OK) {
        return status;
    }
    hipLaunchKernelGGL(
        reduce_energy_serial_fallback_kernel,
        dim3(1U),
        dim3(1U),
        0,
        state->stream,
        contributions.get(),
        final_plan.contribution_count,
        serial_energy_risk.get(),
        device_energy.get(),
        device_error.get());
    status = check_kernel_launch("HIP serial energy fallback launch");
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (compute_forces) {
        status = reduce_forces_by_incidence(
            state,
            forcefield.atom_count,
            &contributions,
            final_plan.contribution_count,
            &device_error,
            &pair_counts,
            &pair_offsets,
            &atom_cells,
            &device_force_x,
            &device_force_y,
            &device_force_z);
        if (status != BG_STATUS_OK) {
            return status;
        }
    }

    cpu::Evaluation candidate;
    candidate.energy.struct_size =
        static_cast<uint32_t>(sizeof(bg_energy_components_v1));
    candidate.energy.abi_version = BG_ABI_VERSION;
    candidate.energy.unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
    if (compute_forces) {
        candidate.force_x.resize(forcefield.atom_count);
        candidate.force_y.resize(forcefield.atom_count);
        candidate.force_z.resize(forcefield.atom_count);
    }
    DeviceEnergy host_energy{};
    int observed_device_error = kDeviceOk;
    status = device_energy.copy_to_host(
        &host_energy,
        1,
        state->stream,
        "hipMemcpyAsync reduced energy");
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (compute_forces) {
        status = device_force_x.copy_to_host(
            candidate.force_x.data(),
            candidate.force_x.size(),
            state->stream,
            "hipMemcpyAsync force x");
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = device_force_y.copy_to_host(
            candidate.force_y.data(),
            candidate.force_y.size(),
            state->stream,
            "hipMemcpyAsync force y");
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = device_force_z.copy_to_host(
            candidate.force_z.data(),
            candidate.force_z.size(),
            state->stream,
            "hipMemcpyAsync force z");
        if (status != BG_STATUS_OK) {
            return status;
        }
    }
    status = device_error.copy_to_host(
        &observed_device_error,
        1,
        state->stream,
        "hipMemcpyAsync final device status");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = synchronize(state->stream, "HIP evaluator synchronization");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = device_error_status(observed_device_error);
    if (status != BG_STATUS_OK) {
        return status;
    }

    candidate.energy.harmonic_bond_kcal_per_mol = host_energy.bond;
    candidate.energy.harmonic_angle_kcal_per_mol = host_energy.angle;
    candidate.energy.periodic_torsion_kcal_per_mol = host_energy.torsion;
    candidate.energy.lennard_jones_kcal_per_mol = host_energy.lennard_jones;
    candidate.energy.coulomb_kcal_per_mol = host_energy.coulomb;
    candidate.energy.total_kcal_per_mol = host_energy.total;

    state->last_stats = {
        static_cast<uint64_t>(grid.cell_count),
        static_cast<uint64_t>(pair_count),
        static_cast<uint64_t>(final_plan.bonded_contribution_count),
    };
    *out_evaluation = std::move(candidate);
    return BG_STATUS_OK;
}

}  // namespace

bg_status query_availability(
    int32_t device_ordinal,
    bool *out_available) noexcept {
    if (out_available == nullptr || device_ordinal < 0) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "HIP availability query arguments are invalid");
    }
    *out_available = false;
    int device_count = 0;
    const hipError_t count_error = hipGetDeviceCount(&device_count);
    if (count_error == hipErrorNoDevice) {
        return BG_STATUS_OK;
    }
    bg_status status = check_runtime(count_error, "hipGetDeviceCount");
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (device_ordinal >= device_count) {
        return BG_STATUS_OK;
    }
    hipDeviceProp_t properties{};
    status = check_runtime(
        hipGetDeviceProperties(&properties, device_ordinal),
        "hipGetDeviceProperties");
    if (status != BG_STATUS_OK) {
        return status;
    }
    /* The public HIP contract is binary64.  A visible device that cannot
     * execute double-precision arithmetic is therefore unavailable rather
     * than a backend that may silently weaken the canonical numeric model. */
    if (properties.arch.hasDoubles == 0U) {
        return BG_STATUS_OK;
    }

    ScopedDeviceGuard device_guard;
    status = device_guard.select(device_ordinal);
    if (status != BG_STATUS_OK) {
        return status;
    }
    hipFuncAttributes attributes{};
    const hipError_t probe_error = hipFuncGetAttributes(
        &attributes,
        reinterpret_cast<const void *>(availability_probe_kernel));
    const bool incompatible_code_object =
        probe_error == hipErrorNoBinaryForGpu ||
        probe_error == hipErrorInvalidDeviceFunction ||
        probe_error == hipErrorInvalidKernelFile;
    if (incompatible_code_object) {
        /* These errors are part of the successful "unavailable" result, so
         * do not leak the probe's sticky HIP error into the caller's next
         * hipGetLastError() observation. */
        (void)hipGetLastError();
    }
    bg_status probe_status = BG_STATUS_OK;
    if (probe_error != hipSuccess && !incompatible_code_object) {
        probe_status = runtime_failure(
            probe_error, "hipFuncGetAttributes availability probe");
    }
    const bg_status restore_status = device_guard.restore();
    if (restore_status != BG_STATUS_OK) {
        return restore_status;
    }
    if (probe_status != BG_STATUS_OK) {
        return probe_status;
    }
    *out_available = !incompatible_code_object;
    return BG_STATUS_OK;
}

bg_status initialize(bg_context *context) noexcept {
    if (context == nullptr) {
        return fail(BG_STATUS_INVALID_ARGUMENT, "HIP context is null");
    }
    if (context->backend_state != nullptr) {
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "HIP context already owns backend state");
    }
    bool available = false;
    bg_status status = query_availability(context->device_ordinal, &available);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (!available) {
        return fail(
            BG_STATUS_BACKEND_UNAVAILABLE,
            "requested HIP device ordinal is unavailable");
    }
    ScopedDeviceGuard device_guard;
    status = device_guard.select(context->device_ordinal);
    if (status != BG_STATUS_OK) {
        return status;
    }
    HipState *const state = new (std::nothrow) HipState{};
    if (state == nullptr) {
        const bg_status allocation_status = fail(
            BG_STATUS_OUT_OF_MEMORY,
            "HIP context state allocation failed");
        const bg_status restore_status = device_guard.restore();
        return restore_status == BG_STATUS_OK ? allocation_status
                                               : restore_status;
    }
    state->device_ordinal = context->device_ordinal;
    const hipError_t stream_error =
        hipStreamCreateWithFlags(&state->stream, hipStreamNonBlocking);
    if (stream_error != hipSuccess) {
        delete state;
        const bg_status stream_status =
            runtime_failure(stream_error, "hipStreamCreateWithFlags");
        const bg_status restore_status = device_guard.restore();
        return restore_status == BG_STATUS_OK ? stream_status : restore_status;
    }
    context->backend_state = state;
    const bg_status restore_status = device_guard.restore();
    if (restore_status != BG_STATUS_OK) {
        context->backend_state = nullptr;
        (void)hipStreamDestroy(state->stream);
        delete state;
        return restore_status;
    }
    return BG_STATUS_OK;
}

void shutdown(bg_context *context) noexcept {
    if (context == nullptr || context->backend_state == nullptr) {
        return;
    }
    HipState *const state = static_cast<HipState *>(context->backend_state);
    context->backend_state = nullptr;
    ScopedDeviceGuard device_guard;
    if (device_guard.select(state->device_ordinal) == BG_STATUS_OK) {
        (void)hipStreamSynchronize(state->stream);
        (void)hipStreamDestroy(state->stream);
        (void)device_guard.restore();
    }
    delete state;
}

bg_status evaluate(
    const bg_context &context,
    const bg_system &system,
    const bg_forcefield &forcefield,
    bool compute_forces,
    cpu::Evaluation *out_evaluation) {
    if (out_evaluation == nullptr) {
        return fail(BG_STATUS_INVALID_ARGUMENT, "HIP evaluation output is null");
    }
    if (context.backend != BG_BACKEND_HIP || context.backend_state == nullptr) {
        return fail(
            BG_STATUS_BACKEND_UNAVAILABLE,
            "HIP context backend state is unavailable");
    }
    if (context.unit_system != BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL ||
        system.unit_system != context.unit_system ||
        forcefield.unit_system != context.unit_system) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "HIP evaluation unit systems do not match");
    }
    if (!storage_is_consistent(system, forcefield)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "HIP system and force-field atom storage do not match");
    }
    HipState *const state = static_cast<HipState *>(context.backend_state);
    std::lock_guard<std::mutex> lock(state->mutex);
    ScopedDeviceGuard device_guard;
    bg_status status = device_guard.select(state->device_ordinal);
    if (status != BG_STATUS_OK) {
        return status;
    }
    const EvaluationStats previous_stats = state->last_stats;
    status = run_evaluator(
        state, system, forcefield, compute_forces, out_evaluation);
    const bg_status restore_status = device_guard.restore();
    if (restore_status != BG_STATUS_OK) {
        state->last_stats = previous_stats;
        return restore_status;
    }
    return status;
}

bg_status get_last_evaluation_stats(
    const bg_context &context,
    EvaluationStats *out_stats) noexcept {
    if (out_stats == nullptr) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "HIP evaluation statistics output is null");
    }
    if (context.backend != BG_BACKEND_HIP || context.backend_state == nullptr) {
        return fail(
            BG_STATUS_BACKEND_UNAVAILABLE,
            "HIP context backend state is unavailable");
    }
    HipState *const state = static_cast<HipState *>(context.backend_state);
    std::lock_guard<std::mutex> lock(state->mutex);
    *out_stats = state->last_stats;
    return BG_STATUS_OK;
}

#if defined(BG_HIP_TESTING)
bg_status set_allocation_failure(
    bg_context &context,
    uint64_t allocation_ordinal) noexcept {
    if (context.backend != BG_BACKEND_HIP || context.backend_state == nullptr) {
        return fail(
            BG_STATUS_BACKEND_UNAVAILABLE,
            "HIP context backend state is unavailable");
    }
    HipState *const state = static_cast<HipState *>(context.backend_state);
    std::lock_guard<std::mutex> lock(state->mutex);
    state->allocation_failure_ordinal = allocation_ordinal;
    state->allocation_attempt_count = 0;
    return BG_STATUS_OK;
}

uint64_t live_allocation_count(const bg_context &context) noexcept {
    if (context.backend != BG_BACKEND_HIP || context.backend_state == nullptr) {
        return UINT64_C(0);
    }
    HipState *const state = static_cast<HipState *>(context.backend_state);
    std::lock_guard<std::mutex> lock(state->mutex);
    return state->live_allocation_count;
}
#endif

}  // namespace betelgeuze::native::hip

#define BG_DOCKING_SCORER_CREATE bg_hip_fast_docking_scorer_v1_create
#define BG_DOCKING_SCORER_DESTROY bg_hip_fast_docking_scorer_v1_destroy
#define BG_DOCKING_SCORER_SCORE_FIXED64 \
    bg_hip_fast_docking_scorer_v1_score_fixed64
#define BG_DOCKING_SCORER_LANE "hip_fast"
#include "docking_scorer.hip"
#undef BG_DOCKING_SCORER_LANE
#undef BG_DOCKING_SCORER_SCORE_FIXED64
#undef BG_DOCKING_SCORER_DESTROY
#undef BG_DOCKING_SCORER_CREATE

#define BG_DOCKING_VALIDITY_CREATE \
    bg_hip_fast_docking_pose_validity_v1_create
#define BG_DOCKING_VALIDITY_DESTROY \
    bg_hip_fast_docking_pose_validity_v1_destroy
#define BG_DOCKING_VALIDITY_EVALUATE_FIXED64 \
    bg_hip_fast_docking_pose_validity_v1_evaluate_fixed64
#define BG_DOCKING_VALIDITY_LANE "hip_fast"
#include "docking_pose_validity.hip"
#undef BG_DOCKING_VALIDITY_LANE
#undef BG_DOCKING_VALIDITY_EVALUATE_FIXED64
#undef BG_DOCKING_VALIDITY_DESTROY
#undef BG_DOCKING_VALIDITY_CREATE

#define BG_DOCKING_STABLE_TOP_K_CREATE \
    bg_hip_fast_docking_stable_top_k_v1_create
#define BG_DOCKING_STABLE_TOP_K_DESTROY \
    bg_hip_fast_docking_stable_top_k_v1_destroy
#define BG_DOCKING_STABLE_TOP_K_RANK_FIXED64 \
    bg_hip_fast_docking_stable_top_k_v1_rank_fixed64
#define BG_DOCKING_STABLE_TOP_K_LANE "hip_fast"
#include "docking_stable_top_k.hip"
#undef BG_DOCKING_STABLE_TOP_K_LANE
#undef BG_DOCKING_STABLE_TOP_K_RANK_FIXED64
#undef BG_DOCKING_STABLE_TOP_K_DESTROY
#undef BG_DOCKING_STABLE_TOP_K_CREATE
