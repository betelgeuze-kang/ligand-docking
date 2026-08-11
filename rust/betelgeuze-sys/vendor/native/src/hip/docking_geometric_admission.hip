#include <hip/hip_runtime.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <limits>
#include <memory>
#include <new>

#if !defined(BG_DOCKING_GEOMETRIC_CREATE) || \
    !defined(BG_DOCKING_GEOMETRIC_DESTROY) || \
    !defined(BG_DOCKING_GEOMETRIC_EVALUATE_FIXED64) || \
    !defined(BG_DOCKING_GEOMETRIC_LANE)
#  error "native HIP geometric-admission provider identity is not configured"
#endif

namespace {

constexpr size_t kGeometricCandidateCount =
    BG_DOCKING_FIXED64_CANDIDATE_COUNT;
constexpr size_t kGeometricMaxLigandAtoms = 512;
constexpr size_t kGeometricMaxReceptorAtoms = 4096;
constexpr uint64_t kGeometricMaxBatchPairs = UINT64_C(16777216);
constexpr double kGeometricMaximumCoordinate = 100000.0;
constexpr double kGeometricMinimumRadius = 0.1;
constexpr double kGeometricMaximumRadius = 10.0;
constexpr double kGeometricMaximumPocketRadius = 1000.0;
constexpr double kGeometricHardRejectionRatio = 0.55;
constexpr double kGeometricPi =
    3.141592653589793238462643383279502884;

void geometric_clear_error(char *message, size_t capacity) noexcept {
    if (message != nullptr && capacity > 0) {
        message[0] = '\0';
    }
}

int32_t geometric_fail(
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

int32_t geometric_fail_hip(
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
            BG_DOCKING_GEOMETRIC_LANE,
            operation,
            detail == nullptr ? "unknown HIP runtime error" : detail);
        message[capacity - 1] = '\0';
    }
    return status;
}

template <size_t Count>
bool geometric_reserved_is_zero(const uint64_t (&values)[Count]) noexcept {
    for (const uint64_t value : values) {
        if (value != UINT64_C(0)) {
            return false;
        }
    }
    return true;
}

bool geometric_digest_present(const uint8_t (&digest)[32]) noexcept {
    for (const uint8_t value : digest) {
        if (value != UINT8_C(0)) {
            return true;
        }
    }
    return false;
}

template <typename Value>
class GeometricDeviceBuffer final {
public:
    GeometricDeviceBuffer() = default;
    GeometricDeviceBuffer(const GeometricDeviceBuffer &) = delete;
    GeometricDeviceBuffer &operator=(const GeometricDeviceBuffer &) = delete;

    ~GeometricDeviceBuffer() {
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
        hipError_t status = hipMalloc(
            reinterpret_cast<void **>(&pointer_), count * sizeof(Value));
        if (status != hipSuccess) {
            return status;
        }
        return hipMemcpy(
            pointer_, source, count * sizeof(Value), hipMemcpyHostToDevice);
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

    Value *get() noexcept { return pointer_; }
    const Value *get() const noexcept { return pointer_; }

private:
    Value *pointer_ = nullptr;
};

class GeometricDeviceGuard final {
public:
    GeometricDeviceGuard() noexcept {
        if (hipGetDevice(&previous_) == hipSuccess) {
            has_previous_ = true;
        }
    }
    GeometricDeviceGuard(const GeometricDeviceGuard &) = delete;
    GeometricDeviceGuard &operator=(const GeometricDeviceGuard &) = delete;
    ~GeometricDeviceGuard() {
        if (has_previous_) {
            static_cast<void>(hipSetDevice(previous_));
        }
    }

private:
    int previous_ = 0;
    bool has_previous_ = false;
};

struct GeometricDeviceContext final {
    size_t receptor_atom_count;
    size_t ligand_atom_count;
    const double *receptor_x;
    const double *receptor_y;
    const double *receptor_z;
    const double *receptor_radius;
    const double *ligand_radius;
    const uint8_t *ligand_heavy_atom_mask;
    double pocket_center[3];
    double pocket_radius;
    double hard_rejection_ratio;
};

struct GeometricState final {
    int32_t device_ordinal = -1;
    GeometricDeviceBuffer<double> receptor_x;
    GeometricDeviceBuffer<double> receptor_y;
    GeometricDeviceBuffer<double> receptor_z;
    GeometricDeviceBuffer<double> receptor_radius;
    GeometricDeviceBuffer<double> ligand_radius;
    GeometricDeviceBuffer<uint8_t> ligand_heavy_atom_mask;
    GeometricDeviceContext context{};
};

__device__ double geometric_sphere_intersection_volume(
    double left_radius,
    double right_radius,
    double center_distance) {
    const double radius_sum = left_radius + right_radius;
    if (center_distance >= radius_sum) {
        return 0.0;
    }
    const double radius_difference = fabs(left_radius - right_radius);
    if (center_distance <= radius_difference) {
        const double radius = fmin(left_radius, right_radius);
        return (4.0 / 3.0) * kGeometricPi * radius * radius * radius;
    }
    const double difference = radius_sum - center_distance;
    const double distance_squared = center_distance * center_distance;
    const double numerator =
        kGeometricPi * difference * difference *
        (distance_squared + 2.0 * center_distance * radius_sum -
         3.0 * radius_difference * radius_difference);
    return fmax(numerator / (12.0 * center_distance), 0.0);
}

__device__ void geometric_failure_row(
    uint32_t slot,
    bg_docking_geometric_admission_row_status status,
    bg_docking_geometric_admission_failure failure,
    bg_docking_geometric_admission_row_v1 *row) {
    *row = bg_docking_geometric_admission_row_v1{};
    row->slot_index = slot;
    row->status = status;
    row->failure_code = failure;
    row->decision =
        BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_NOT_EVALUATED;
}

__global__ void geometric_fixed64_kernel(
    GeometricDeviceContext context,
    const bg_docking_geometric_admission_candidate_state *candidate_state,
    const double *x,
    const double *y,
    const double *z,
    bg_docking_geometric_admission_row_v1 *rows) {
    const uint32_t slot = blockIdx.x * blockDim.x + threadIdx.x;
    if (slot >= kGeometricCandidateCount) {
        return;
    }
    auto *const row = &rows[slot];
    if (candidate_state[slot] ==
        BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_UPSTREAM_FAILURE) {
        geometric_failure_row(
            slot,
            BG_DOCKING_GEOMETRIC_ADMISSION_ROW_UPSTREAM_FAILURE,
            BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_UPSTREAM_NOT_AVAILABLE,
            row);
        return;
    }
    const size_t begin = static_cast<size_t>(slot) * context.ligand_atom_count;
    for (size_t ligand = 0; ligand < context.ligand_atom_count; ++ligand) {
        const size_t index = begin + ligand;
        if (!isfinite(x[index]) || !isfinite(y[index]) ||
            !isfinite(z[index]) || fabs(x[index]) > kGeometricMaximumCoordinate ||
            fabs(y[index]) > kGeometricMaximumCoordinate ||
            fabs(z[index]) > kGeometricMaximumCoordinate) {
            geometric_failure_row(
                slot,
                BG_DOCKING_GEOMETRIC_ADMISSION_ROW_TYPED_FAILURE,
                BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_INVALID_CANDIDATE_COORDINATES,
                row);
            return;
        }
    }

    *row = bg_docking_geometric_admission_row_v1{};
    row->slot_index = slot;
    row->status = BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED;
    row->failure_code = BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_NONE;
    row->ligand_atom_count = context.ligand_atom_count;
    row->receptor_atom_count = context.receptor_atom_count;
    row->exact_pair_count =
        context.ligand_atom_count * context.receptor_atom_count;
    row->raw_minimum_distance_angstrom = INFINITY;
    row->minimum_vdw_surface_gap_angstrom = INFINITY;
    row->minimum_vdw_ratio = INFINITY;
    double overlap = 0.0;
    double pocket_escape = 0.0;
    for (size_t ligand = 0; ligand < context.ligand_atom_count; ++ligand) {
        const size_t index = begin + ligand;
        bool penetrates = false;
        for (size_t receptor = 0; receptor < context.receptor_atom_count;
             ++receptor) {
            const double dx = x[index] - context.receptor_x[receptor];
            const double dy = y[index] - context.receptor_y[receptor];
            const double dz = z[index] - context.receptor_z[receptor];
            const double distance = sqrt(dx * dx + dy * dy + dz * dz);
            const double radius_sum = context.ligand_radius[ligand] +
                                      context.receptor_radius[receptor];
            row->raw_minimum_distance_angstrom =
                fmin(row->raw_minimum_distance_angstrom, distance);
            row->minimum_vdw_surface_gap_angstrom = fmin(
                row->minimum_vdw_surface_gap_angstrom,
                distance - radius_sum);
            row->minimum_vdw_ratio =
                fmin(row->minimum_vdw_ratio, distance / radius_sum);
            if (distance < radius_sum) {
                ++row->penetration_pair_count;
                penetrates = true;
                overlap += geometric_sphere_intersection_volume(
                    context.ligand_radius[ligand],
                    context.receptor_radius[receptor],
                    distance);
            }
        }
        if (penetrates) {
            ++row->unique_ligand_penetration_atom_count;
            if (context.ligand_heavy_atom_mask[ligand] != UINT8_C(0)) {
                ++row->unique_ligand_heavy_atom_penetration_count;
            }
        }
        const double pocket_dx = x[index] - context.pocket_center[0];
        const double pocket_dy = y[index] - context.pocket_center[1];
        const double pocket_dz = z[index] - context.pocket_center[2];
        const double escape =
            sqrt(
                pocket_dx * pocket_dx + pocket_dy * pocket_dy +
                pocket_dz * pocket_dz) +
            context.ligand_radius[ligand] - context.pocket_radius;
        pocket_escape = fmax(pocket_escape, fmax(escape, 0.0));
    }
    row->sphere_overlap_proxy_angstrom3 = overlap;
    row->pocket_escape_angstrom = pocket_escape;
    if (!isfinite(row->raw_minimum_distance_angstrom) ||
        !isfinite(row->minimum_vdw_surface_gap_angstrom) ||
        !isfinite(row->minimum_vdw_ratio) || !isfinite(overlap) ||
        !isfinite(pocket_escape)) {
        geometric_failure_row(
            slot,
            BG_DOCKING_GEOMETRIC_ADMISSION_ROW_TYPED_FAILURE,
            BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_NONFINITE_DERIVED_MEASUREMENT,
            row);
        return;
    }
    row->rank_eligible = static_cast<uint8_t>(
        row->minimum_vdw_ratio >= context.hard_rejection_ratio);
    row->decision = row->rank_eligible != UINT8_C(0)
                        ? BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED
                        : BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_SEVERE_PENETRATION_REJECTED;
}

bool geometric_row_is_valid(
    const bg_docking_geometric_admission_row_v1 &row,
    size_t slot) noexcept {
    if (row.slot_index != slot || row.reserved1 != 0 ||
        !geometric_reserved_is_zero(row.reserved) || row.reserved0[0] != 0 ||
        row.reserved0[1] != 0 || row.reserved0[2] != 0) {
        return false;
    }
    if (row.status == BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED) {
        return row.failure_code ==
                   BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_NONE &&
               (row.decision ==
                    BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED ||
                row.decision ==
                    BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_SEVERE_PENETRATION_REJECTED) &&
               row.rank_eligible == static_cast<uint8_t>(
                   row.decision ==
                   BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED) &&
               row.ligand_atom_count > 0 && row.receptor_atom_count > 0 &&
               row.exact_pair_count ==
                   row.ligand_atom_count * row.receptor_atom_count &&
               std::isfinite(row.raw_minimum_distance_angstrom) &&
               std::isfinite(row.minimum_vdw_surface_gap_angstrom) &&
               std::isfinite(row.minimum_vdw_ratio) &&
               std::isfinite(row.sphere_overlap_proxy_angstrom3) &&
               std::isfinite(row.pocket_escape_angstrom);
    }
    return row.rank_eligible == 0 &&
           row.decision ==
               BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_NOT_EVALUATED &&
           ((row.status ==
                 BG_DOCKING_GEOMETRIC_ADMISSION_ROW_UPSTREAM_FAILURE &&
             row.failure_code ==
                 BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_UPSTREAM_NOT_AVAILABLE) ||
            (row.status ==
                 BG_DOCKING_GEOMETRIC_ADMISSION_ROW_TYPED_FAILURE &&
             (row.failure_code ==
                  BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_INVALID_CANDIDATE_COORDINATES ||
              row.failure_code ==
                  BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_NONFINITE_DERIVED_MEASUREMENT)));
}

}  // namespace

extern "C" int32_t BG_DOCKING_GEOMETRIC_CREATE(
    int32_t device_ordinal,
    const bg_docking_geometric_admission_context_soa_v1 *descriptor,
    void **out_state,
    char *error_message,
    size_t error_capacity) {
    geometric_clear_error(error_message, error_capacity);
    if (out_state != nullptr) {
        *out_state = nullptr;
    }
    if (descriptor == nullptr || out_state == nullptr || device_ordinal < 0) {
        return geometric_fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            BG_DOCKING_GEOMETRIC_LANE
            " geometric-admission create arguments are invalid");
    }
    if (descriptor->struct_size != sizeof(*descriptor) ||
        descriptor->abi_version != BG_ABI_VERSION) {
        return geometric_fail(
            BG_STATUS_ABI_MISMATCH,
            error_message,
            error_capacity,
            BG_DOCKING_GEOMETRIC_LANE
            " geometric-admission context ABI mismatch");
    }
    if (descriptor->unit_system != BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL ||
        descriptor->reserved0 != 0 ||
        !geometric_reserved_is_zero(descriptor->reserved) ||
        descriptor->receptor_atom_count == 0 ||
        descriptor->receptor_atom_count > kGeometricMaxReceptorAtoms ||
        descriptor->ligand_atom_count == 0 ||
        descriptor->ligand_atom_count > kGeometricMaxLigandAtoms ||
        descriptor->receptor_x_angstrom == nullptr ||
        descriptor->receptor_y_angstrom == nullptr ||
        descriptor->receptor_z_angstrom == nullptr ||
        descriptor->receptor_vdw_radius_angstrom == nullptr ||
        descriptor->ligand_vdw_radius_angstrom == nullptr ||
        descriptor->ligand_heavy_atom_mask == nullptr ||
        !std::isfinite(descriptor->pocket_center_angstrom[0]) ||
        !std::isfinite(descriptor->pocket_center_angstrom[1]) ||
        !std::isfinite(descriptor->pocket_center_angstrom[2]) ||
        !std::isfinite(descriptor->pocket_radius_angstrom) ||
        descriptor->pocket_radius_angstrom <= 0.0 ||
        descriptor->pocket_radius_angstrom >
            kGeometricMaximumPocketRadius ||
        descriptor->hard_rejection_minimum_vdw_ratio !=
            kGeometricHardRejectionRatio ||
        descriptor->max_batch_exact_pair_evaluations !=
            kGeometricMaxBatchPairs ||
        !geometric_digest_present(
            descriptor->authority_input_receipt_sha256) ||
        !geometric_digest_present(descriptor->receptor_system_sha256) ||
        !geometric_digest_present(descriptor->ligand_system_sha256) ||
        !geometric_digest_present(descriptor->backend_receipt_sha256)) {
        return geometric_fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            BG_DOCKING_GEOMETRIC_LANE
            " geometric-admission context identity is invalid");
    }
    const size_t receptor_count =
        static_cast<size_t>(descriptor->receptor_atom_count);
    const size_t ligand_count =
        static_cast<size_t>(descriptor->ligand_atom_count);
    for (size_t index = 0; index < receptor_count; ++index) {
        const double radius =
            descriptor->receptor_vdw_radius_angstrom[index];
        if (!std::isfinite(descriptor->receptor_x_angstrom[index]) ||
            !std::isfinite(descriptor->receptor_y_angstrom[index]) ||
            !std::isfinite(descriptor->receptor_z_angstrom[index]) ||
            std::abs(descriptor->receptor_x_angstrom[index]) >
                kGeometricMaximumCoordinate ||
            std::abs(descriptor->receptor_y_angstrom[index]) >
                kGeometricMaximumCoordinate ||
            std::abs(descriptor->receptor_z_angstrom[index]) >
                kGeometricMaximumCoordinate ||
            !std::isfinite(radius) || radius < kGeometricMinimumRadius ||
            radius > kGeometricMaximumRadius) {
            return geometric_fail(
                BG_STATUS_INVALID_ARGUMENT,
                error_message,
                error_capacity,
                BG_DOCKING_GEOMETRIC_LANE
                " geometric-admission receptor geometry is invalid");
        }
    }
    for (size_t index = 0; index < ligand_count; ++index) {
        const double radius = descriptor->ligand_vdw_radius_angstrom[index];
        if (!std::isfinite(radius) || radius < kGeometricMinimumRadius ||
            radius > kGeometricMaximumRadius ||
            descriptor->ligand_heavy_atom_mask[index] > UINT8_C(1)) {
            return geometric_fail(
                BG_STATUS_INVALID_ARGUMENT,
                error_message,
                error_capacity,
                BG_DOCKING_GEOMETRIC_LANE
                " geometric-admission ligand geometry is invalid");
        }
    }

    GeometricDeviceGuard device_guard;
    hipError_t status = hipSetDevice(device_ordinal);
    if (status != hipSuccess) {
        return geometric_fail_hip(
            status,
            error_message,
            error_capacity,
            "geometric-admission device selection");
    }
    auto state = std::unique_ptr<GeometricState>(
        new (std::nothrow) GeometricState());
    if (!state) {
        return geometric_fail(
            BG_STATUS_OUT_OF_MEMORY,
            error_message,
            error_capacity,
            BG_DOCKING_GEOMETRIC_LANE
            " geometric-admission state allocation failed");
    }
    state->device_ordinal = device_ordinal;

#define BG_HIP_GEOMETRIC_CONTEXT_COPY(buffer, source, count, operation)       \
    do {                                                                      \
        status = (buffer).copy_from((source), (count));                       \
        if (status != hipSuccess) {                                           \
            return geometric_fail_hip(                                        \
                status, error_message, error_capacity, (operation));          \
        }                                                                     \
    } while (false)

    BG_HIP_GEOMETRIC_CONTEXT_COPY(
        state->receptor_x,
        descriptor->receptor_x_angstrom,
        receptor_count,
        "geometric-admission receptor x copy");
    BG_HIP_GEOMETRIC_CONTEXT_COPY(
        state->receptor_y,
        descriptor->receptor_y_angstrom,
        receptor_count,
        "geometric-admission receptor y copy");
    BG_HIP_GEOMETRIC_CONTEXT_COPY(
        state->receptor_z,
        descriptor->receptor_z_angstrom,
        receptor_count,
        "geometric-admission receptor z copy");
    BG_HIP_GEOMETRIC_CONTEXT_COPY(
        state->receptor_radius,
        descriptor->receptor_vdw_radius_angstrom,
        receptor_count,
        "geometric-admission receptor radius copy");
    BG_HIP_GEOMETRIC_CONTEXT_COPY(
        state->ligand_radius,
        descriptor->ligand_vdw_radius_angstrom,
        ligand_count,
        "geometric-admission ligand radius copy");
    BG_HIP_GEOMETRIC_CONTEXT_COPY(
        state->ligand_heavy_atom_mask,
        descriptor->ligand_heavy_atom_mask,
        ligand_count,
        "geometric-admission heavy-atom mask copy");

#undef BG_HIP_GEOMETRIC_CONTEXT_COPY

    state->context = {
        receptor_count,
        ligand_count,
        state->receptor_x.get(),
        state->receptor_y.get(),
        state->receptor_z.get(),
        state->receptor_radius.get(),
        state->ligand_radius.get(),
        state->ligand_heavy_atom_mask.get(),
        {
            descriptor->pocket_center_angstrom[0],
            descriptor->pocket_center_angstrom[1],
            descriptor->pocket_center_angstrom[2],
        },
        descriptor->pocket_radius_angstrom,
        descriptor->hard_rejection_minimum_vdw_ratio,
    };
    *out_state = state.release();
    return BG_STATUS_OK;
}

extern "C" void BG_DOCKING_GEOMETRIC_DESTROY(void *state) {
    auto *const typed = static_cast<GeometricState *>(state);
    if (typed == nullptr) {
        return;
    }
    GeometricDeviceGuard device_guard;
    if (hipSetDevice(typed->device_ordinal) == hipSuccess) {
        static_cast<void>(hipDeviceSynchronize());
    }
    delete typed;
}

extern "C" int32_t BG_DOCKING_GEOMETRIC_EVALUATE_FIXED64(
    const void *state,
    const bg_docking_geometric_admission_candidate_batch_soa_v1 *candidates,
    bg_docking_geometric_admission_row_v1 *out_rows,
    char *error_message,
    size_t error_capacity) {
    geometric_clear_error(error_message, error_capacity);
    const auto *const typed = static_cast<const GeometricState *>(state);
    if (typed == nullptr || candidates == nullptr || out_rows == nullptr) {
        return geometric_fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            BG_DOCKING_GEOMETRIC_LANE
            " geometric-admission batch arguments are invalid");
    }
    if (candidates->struct_size != sizeof(*candidates) ||
        candidates->abi_version != BG_ABI_VERSION) {
        return geometric_fail(
            BG_STATUS_ABI_MISMATCH,
            error_message,
            error_capacity,
            BG_DOCKING_GEOMETRIC_LANE
            " geometric-admission candidate ABI mismatch");
    }
    if (candidates->candidate_count != kGeometricCandidateCount ||
        candidates->ligand_atom_count != typed->context.ligand_atom_count ||
        candidates->unit_system != BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL ||
        candidates->reserved0 != 0 ||
        !geometric_reserved_is_zero(candidates->reserved) ||
        candidates->candidate_state == nullptr ||
        candidates->x_angstrom == nullptr || candidates->y_angstrom == nullptr ||
        candidates->z_angstrom == nullptr) {
        return geometric_fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            BG_DOCKING_GEOMETRIC_LANE
            " geometric-admission fixed64 descriptor is invalid");
    }
    size_t active_count = 0;
    for (size_t slot = 0; slot < kGeometricCandidateCount; ++slot) {
        const auto candidate = candidates->candidate_state[slot];
        if (candidate ==
            BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_EVALUATE) {
            ++active_count;
        } else if (
            candidate !=
            BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_UPSTREAM_FAILURE) {
            return geometric_fail(
                BG_STATUS_INVALID_ARGUMENT,
                error_message,
                error_capacity,
                BG_DOCKING_GEOMETRIC_LANE
                " geometric-admission candidate state is invalid");
        }
    }
    const uint64_t per_candidate_pairs =
        static_cast<uint64_t>(typed->context.ligand_atom_count) *
        static_cast<uint64_t>(typed->context.receptor_atom_count);
    if (active_count != 0 &&
        per_candidate_pairs >
            std::numeric_limits<uint64_t>::max() / active_count) {
        return geometric_fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            error_message,
            error_capacity,
            BG_DOCKING_GEOMETRIC_LANE
            " geometric-admission pair denominator overflowed");
    }
    if (per_candidate_pairs * active_count > kGeometricMaxBatchPairs) {
        return geometric_fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            error_message,
            error_capacity,
            BG_DOCKING_GEOMETRIC_LANE
            " geometric-admission pair work exceeds the frozen cap");
    }
    if (typed->context.ligand_atom_count >
        std::numeric_limits<size_t>::max() / kGeometricCandidateCount) {
        return geometric_fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            error_message,
            error_capacity,
            BG_DOCKING_GEOMETRIC_LANE
            " geometric-admission coordinate denominator overflowed");
    }
    const size_t coordinate_count =
        kGeometricCandidateCount * typed->context.ligand_atom_count;
    GeometricDeviceGuard device_guard;
    hipError_t status = hipSetDevice(typed->device_ordinal);
    if (status != hipSuccess) {
        return geometric_fail_hip(
            status,
            error_message,
            error_capacity,
            "geometric-admission device selection");
    }
    GeometricDeviceBuffer<bg_docking_geometric_admission_candidate_state>
        device_candidate_state;
    GeometricDeviceBuffer<double> device_x;
    GeometricDeviceBuffer<double> device_y;
    GeometricDeviceBuffer<double> device_z;
    GeometricDeviceBuffer<bg_docking_geometric_admission_row_v1> device_rows;

#define BG_HIP_GEOMETRIC_BATCH_COPY(buffer, source, count, operation)         \
    do {                                                                      \
        status = (buffer).copy_from((source), (count));                       \
        if (status != hipSuccess) {                                           \
            return geometric_fail_hip(                                        \
                status, error_message, error_capacity, (operation));          \
        }                                                                     \
    } while (false)

    BG_HIP_GEOMETRIC_BATCH_COPY(
        device_candidate_state,
        candidates->candidate_state,
        kGeometricCandidateCount,
        "geometric-admission candidate state copy");
    BG_HIP_GEOMETRIC_BATCH_COPY(
        device_x,
        candidates->x_angstrom,
        coordinate_count,
        "geometric-admission x copy");
    BG_HIP_GEOMETRIC_BATCH_COPY(
        device_y,
        candidates->y_angstrom,
        coordinate_count,
        "geometric-admission y copy");
    BG_HIP_GEOMETRIC_BATCH_COPY(
        device_z,
        candidates->z_angstrom,
        coordinate_count,
        "geometric-admission z copy");

#undef BG_HIP_GEOMETRIC_BATCH_COPY

    status = device_rows.allocate(kGeometricCandidateCount);
    if (status != hipSuccess) {
        return geometric_fail_hip(
            status,
            error_message,
            error_capacity,
            "geometric-admission output allocation");
    }
    hipLaunchKernelGGL(
        geometric_fixed64_kernel,
        dim3(static_cast<uint32_t>(kGeometricCandidateCount)),
        dim3(1),
        0,
        0,
        typed->context,
        device_candidate_state.get(),
        device_x.get(),
        device_y.get(),
        device_z.get(),
        device_rows.get());
    hipError_t execution_status = hipGetLastError();
    if (execution_status == hipSuccess) {
        execution_status = hipDeviceSynchronize();
    }
    if (execution_status != hipSuccess) {
        return geometric_fail_hip(
            execution_status,
            error_message,
            error_capacity,
            "geometric-admission kernel execution");
    }
    std::array<
        bg_docking_geometric_admission_row_v1,
        kGeometricCandidateCount>
        host_rows{};
    const hipError_t copy_status =
        device_rows.copy_to(host_rows.data(), host_rows.size());
    if (copy_status != hipSuccess) {
        return geometric_fail_hip(
            copy_status,
            error_message,
            error_capacity,
            "geometric-admission result copy");
    }
    for (size_t slot = 0; slot < host_rows.size(); ++slot) {
        if (!geometric_row_is_valid(host_rows[slot], slot)) {
            return geometric_fail(
                BG_STATUS_BACKEND_ERROR,
                error_message,
                error_capacity,
                BG_DOCKING_GEOMETRIC_LANE
                " geometric-admission returned an invalid device row");
        }
    }
    std::memcpy(out_rows, host_rows.data(), sizeof(host_rows));
    return BG_STATUS_OK;
}
