#include <hip/hip_runtime.h>

#include <array>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <limits>
#include <memory>
#include <new>

#if !defined(BG_DOCKING_STABLE_TOP_K_CREATE) || \
    !defined(BG_DOCKING_STABLE_TOP_K_DESTROY) || \
    !defined(BG_DOCKING_STABLE_TOP_K_RANK_FIXED64) || \
    !defined(BG_DOCKING_STABLE_TOP_K_CLUSTER_FIXED64) || \
    !defined(BG_DOCKING_STABLE_TOP_K_LANE)
#  error "native HIP stable Top-K provider identity is not configured"
#endif

namespace {

constexpr size_t kHipStableTopKCandidateCount =
    BG_DOCKING_FIXED64_CANDIDATE_COUNT;
constexpr size_t kHipStableTopKDigestSize = 32;

void stable_top_k_clear_error(char *message, size_t capacity) noexcept {
    if (message != nullptr && capacity > 0) {
        message[0] = '\0';
    }
}

int32_t stable_top_k_fail(
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

int32_t stable_top_k_fail_hip(
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
            BG_DOCKING_STABLE_TOP_K_LANE,
            operation,
            detail == nullptr ? "unknown HIP runtime error" : detail);
        message[capacity - 1] = '\0';
    }
    return status;
}

template <size_t Count>
bool stable_top_k_reserved_is_zero(
    const uint64_t (&values)[Count]) noexcept {
    for (const uint64_t value : values) {
        if (value != UINT64_C(0)) {
            return false;
        }
    }
    return true;
}

template <typename Value>
class StableTopKDeviceBuffer final {
public:
    StableTopKDeviceBuffer() = default;
    StableTopKDeviceBuffer(const StableTopKDeviceBuffer &) = delete;
    StableTopKDeviceBuffer &operator=(const StableTopKDeviceBuffer &) = delete;

    ~StableTopKDeviceBuffer() {
        if (pointer_ != nullptr) {
            static_cast<void>(hipFree(pointer_));
        }
    }

    hipError_t copy_from(const Value *source, size_t count) noexcept {
        if (source == nullptr || count == 0 ||
            count > std::numeric_limits<size_t>::max() / sizeof(Value)) {
            return hipErrorInvalidValue;
        }
        const size_t bytes = count * sizeof(Value);
        hipError_t status =
            hipMalloc(reinterpret_cast<void **>(&pointer_), bytes);
        if (status != hipSuccess) {
            return status;
        }
        return hipMemcpy(pointer_, source, bytes, hipMemcpyHostToDevice);
    }

    hipError_t allocate(size_t count) noexcept {
        if (count == 0 ||
            count > std::numeric_limits<size_t>::max() / sizeof(Value)) {
            return hipErrorInvalidValue;
        }
        return hipMalloc(
            reinterpret_cast<void **>(&pointer_), count * sizeof(Value));
    }

    hipError_t copy_to(Value *destination, size_t count) const noexcept {
        if (destination == nullptr || pointer_ == nullptr || count == 0 ||
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

class StableTopKDeviceGuard final {
public:
    StableTopKDeviceGuard() noexcept {
        if (hipGetDevice(&previous_) == hipSuccess) {
            has_previous_ = true;
        }
    }

    StableTopKDeviceGuard(const StableTopKDeviceGuard &) = delete;
    StableTopKDeviceGuard &operator=(const StableTopKDeviceGuard &) = delete;

    ~StableTopKDeviceGuard() {
        if (has_previous_) {
            static_cast<void>(hipSetDevice(previous_));
        }
    }

private:
    int previous_ = 0;
    bool has_previous_ = false;
};

struct StableTopKState final {
    int32_t device_ordinal = 0;
};

struct StableTopKEntry final {
    uint32_t slot_index;
    double total_score;
    uint8_t coordinate_sha256[kHipStableTopKDigestSize];
};

struct StableTopKDeviceOutput final {
    bg_docking_stable_top_k_row_v1 rows[kHipStableTopKCandidateCount];
    uint32_t primary_slot_indices[kHipStableTopKCandidateCount];
    uint64_t primary_count;
    uint32_t valid_slot_indices[kHipStableTopKCandidateCount];
    uint64_t valid_count;
};

struct RmsdClusterDeviceOutput final {
    bg_docking_rmsd_cluster_row_v1 rows[kHipStableTopKCandidateCount];
    uint32_t representative_slot_indices[kHipStableTopKCandidateCount];
    uint64_t cluster_count;
    uint32_t top_k_slot_indices[BG_DOCKING_RMSD_CLUSTER_TOP_K_LIMIT];
    uint64_t top_k_count;
    uint32_t numerical_failure;
};

__device__ double stable_top_k_canonical_score(double value) {
    return value == 0.0 ? 0.0 : value;
}

__device__ bool stable_top_k_entry_less(
    const StableTopKEntry &left,
    const StableTopKEntry &right) {
    if (left.total_score < right.total_score) {
        return true;
    }
    if (right.total_score < left.total_score) {
        return false;
    }
    if (left.slot_index != right.slot_index) {
        return left.slot_index < right.slot_index;
    }
    for (size_t index = 0; index < kHipStableTopKDigestSize; ++index) {
        if (left.coordinate_sha256[index] !=
            right.coordinate_sha256[index]) {
            return left.coordinate_sha256[index] <
                   right.coordinate_sha256[index];
        }
    }
    return false;
}

__global__ void stable_top_k_fixed64_kernel(
    const bg_docking_scorer_v1_row_v1 *scorer_rows,
    const bg_docking_pose_validity_row_v1 *validity_rows,
    const uint8_t *coordinate_sha256,
    StableTopKDeviceOutput *out) {
    if (blockIdx.x != 0 || threadIdx.x != 0) {
        return;
    }
    *out = StableTopKDeviceOutput{};
    StableTopKEntry primary[kHipStableTopKCandidateCount]{};
    size_t primary_count = 0;
    for (size_t slot = 0; slot < kHipStableTopKCandidateCount; ++slot) {
        if (scorer_rows[slot].status !=
            BG_DOCKING_SCORER_V1_ROW_SCORED) {
            continue;
        }
        StableTopKEntry entry{};
        entry.slot_index = static_cast<uint32_t>(slot);
        entry.total_score =
            stable_top_k_canonical_score(scorer_rows[slot].total_score);
        for (size_t index = 0; index < kHipStableTopKDigestSize; ++index) {
            entry.coordinate_sha256[index] =
                coordinate_sha256[slot * kHipStableTopKDigestSize + index];
        }
        size_t position = primary_count;
        while (position > 0 &&
               stable_top_k_entry_less(entry, primary[position - 1])) {
            primary[position] = primary[position - 1];
            --position;
        }
        primary[position] = entry;
        ++primary_count;
    }
    uint32_t stable_rank[kHipStableTopKCandidateCount]{};
    uint32_t stable_valid_rank[kHipStableTopKCandidateCount]{};
    size_t valid_count = 0;
    for (size_t offset = 0; offset < primary_count; ++offset) {
        const size_t slot = static_cast<size_t>(primary[offset].slot_index);
        out->primary_slot_indices[offset] = primary[offset].slot_index;
        stable_rank[slot] = static_cast<uint32_t>(offset + 1);
        if (validity_rows[slot].status ==
                BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED &&
            validity_rows[slot].passed_check_mask ==
                BG_DOCKING_POSE_VALIDITY_CHECK_ALL) {
            out->valid_slot_indices[valid_count] =
                static_cast<uint32_t>(slot);
            stable_valid_rank[slot] =
                static_cast<uint32_t>(valid_count + 1);
            ++valid_count;
        }
    }
    out->primary_count = static_cast<uint64_t>(primary_count);
    out->valid_count = static_cast<uint64_t>(valid_count);
    for (size_t slot = 0; slot < kHipStableTopKCandidateCount; ++slot) {
        bg_docking_stable_top_k_row_v1 row{};
        row.slot_index = static_cast<uint32_t>(slot);
        if (scorer_rows[slot].status ==
            BG_DOCKING_SCORER_V1_ROW_SCORED) {
            row.rank_eligible = UINT8_C(1);
            row.valid_rank_eligible =
                stable_valid_rank[slot] == 0 ? UINT8_C(0) : UINT8_C(1);
            row.stable_rank = stable_rank[slot];
            row.stable_valid_rank = stable_valid_rank[slot];
            row.total_score =
                stable_top_k_canonical_score(scorer_rows[slot].total_score);
            for (size_t index = 0; index < kHipStableTopKDigestSize; ++index) {
                row.coordinate_sha256[index] =
                    coordinate_sha256[
                        slot * kHipStableTopKDigestSize + index];
            }
        }
        out->rows[slot] = row;
    }
}

__device__ double direct_rmsd_fixed64(
    const double *x,
    const double *y,
    const double *z,
    size_t atom_count,
    size_t left_slot,
    size_t right_slot) {
    const size_t left_begin = left_slot * atom_count;
    const size_t right_begin = right_slot * atom_count;
    double squared_sum = 0.0;
    for (size_t atom = 0; atom < atom_count; ++atom) {
        const double dx = x[left_begin + atom] - x[right_begin + atom];
        const double dy = y[left_begin + atom] - y[right_begin + atom];
        const double dz = z[left_begin + atom] - z[right_begin + atom];
        squared_sum += dx * dx + dy * dy + dz * dz;
    }
    const double value = sqrt(squared_sum / static_cast<double>(atom_count));
    return value == 0.0 ? 0.0 : value;
}

__global__ void direct_rmsd_cluster_fixed64_kernel(
    const bg_docking_stable_top_k_row_v1 *ranking_rows,
    const uint32_t *valid_slot_indices,
    size_t valid_count,
    const double *x,
    const double *y,
    const double *z,
    size_t atom_count,
    double rmsd_threshold,
    RmsdClusterDeviceOutput *out) {
    if (blockIdx.x != 0 || threadIdx.x != 0) {
        return;
    }
    *out = RmsdClusterDeviceOutput{};
    uint32_t cluster_sizes[kHipStableTopKCandidateCount]{};
    for (size_t slot = 0; slot < kHipStableTopKCandidateCount; ++slot) {
        out->rows[slot].slot_index = static_cast<uint32_t>(slot);
        out->rows[slot].status =
            BG_DOCKING_RMSD_CLUSTER_ROW_UPSTREAM_NOT_VALID;
    }
    size_t cluster_count = 0;
    for (size_t offset = 0; offset < valid_count; ++offset) {
        const size_t slot = static_cast<size_t>(valid_slot_indices[offset]);
        size_t cluster_offset = cluster_count;
        size_t representative_slot = slot;
        double rmsd = 0.0;
        bool representative = true;
        for (size_t existing = 0; existing < cluster_count; ++existing) {
            const size_t existing_slot = static_cast<size_t>(
                out->representative_slot_indices[existing]);
            const double candidate_rmsd = direct_rmsd_fixed64(
                x, y, z, atom_count, slot, existing_slot);
            if (!isfinite(candidate_rmsd)) {
                out->numerical_failure = UINT32_C(1);
                return;
            }
            if (candidate_rmsd <= rmsd_threshold) {
                cluster_offset = existing;
                representative_slot = existing_slot;
                rmsd = candidate_rmsd;
                representative = false;
                break;
            }
        }
        if (representative) {
            out->representative_slot_indices[cluster_count] =
                static_cast<uint32_t>(slot);
            ++cluster_count;
        }
        ++cluster_sizes[cluster_offset];
        bg_docking_rmsd_cluster_row_v1 row{};
        row.slot_index = static_cast<uint32_t>(slot);
        row.status = BG_DOCKING_RMSD_CLUSTER_ROW_CLUSTERED;
        row.cluster_eligible = UINT8_C(1);
        row.representative = representative ? UINT8_C(1) : UINT8_C(0);
        row.top_k_representative =
            representative &&
                    cluster_offset < BG_DOCKING_RMSD_CLUSTER_TOP_K_LIMIT
                ? UINT8_C(1)
                : UINT8_C(0);
        row.stable_valid_rank = static_cast<uint32_t>(offset + 1);
        row.cluster_id = static_cast<uint32_t>(cluster_offset + 1);
        row.representative_slot_index =
            static_cast<uint32_t>(representative_slot);
        row.cluster_rank = static_cast<uint32_t>(cluster_offset + 1);
        row.top_k_rank =
            representative &&
                    cluster_offset < BG_DOCKING_RMSD_CLUSTER_TOP_K_LIMIT
                ? static_cast<uint32_t>(cluster_offset + 1)
                : 0;
        row.direct_rmsd_to_representative_angstrom = rmsd;
        for (size_t index = 0; index < kHipStableTopKDigestSize; ++index) {
            row.coordinate_sha256[index] =
                ranking_rows[slot].coordinate_sha256[index];
        }
        out->rows[slot] = row;
    }
    for (size_t offset = 0; offset < valid_count; ++offset) {
        const size_t slot = static_cast<size_t>(valid_slot_indices[offset]);
        out->rows[slot].cluster_size =
            cluster_sizes[out->rows[slot].cluster_id - 1];
    }
    out->cluster_count = static_cast<uint64_t>(cluster_count);
    const size_t top_k_count =
        cluster_count < BG_DOCKING_RMSD_CLUSTER_TOP_K_LIMIT
            ? cluster_count
            : BG_DOCKING_RMSD_CLUSTER_TOP_K_LIMIT;
    out->top_k_count = static_cast<uint64_t>(top_k_count);
    for (size_t index = 0; index < top_k_count; ++index) {
        out->top_k_slot_indices[index] =
            out->representative_slot_indices[index];
    }
}

}  // namespace

extern "C" int32_t BG_DOCKING_STABLE_TOP_K_CREATE(
    int32_t device_ordinal,
    void **out_state,
    char *error_message,
    size_t error_capacity) {
    stable_top_k_clear_error(error_message, error_capacity);
    if (out_state != nullptr) {
        *out_state = nullptr;
    }
    if (device_ordinal < 0 || out_state == nullptr) {
        return stable_top_k_fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            BG_DOCKING_STABLE_TOP_K_LANE
            " stable Top-K create arguments are invalid");
    }
    StableTopKDeviceGuard guard;
    const hipError_t status = hipSetDevice(device_ordinal);
    if (status != hipSuccess) {
        return stable_top_k_fail_hip(
            status,
            error_message,
            error_capacity,
            "stable Top-K device selection");
    }
    std::unique_ptr<StableTopKState> state(
        new (std::nothrow) StableTopKState{});
    if (state == nullptr) {
        return stable_top_k_fail(
            BG_STATUS_OUT_OF_MEMORY,
            error_message,
            error_capacity,
            BG_DOCKING_STABLE_TOP_K_LANE
            " stable Top-K state allocation failed");
    }
    state->device_ordinal = device_ordinal;
    *out_state = state.release();
    return BG_STATUS_OK;
}

extern "C" void BG_DOCKING_STABLE_TOP_K_DESTROY(void *state) {
    delete static_cast<StableTopKState *>(state);
}

extern "C" int32_t BG_DOCKING_STABLE_TOP_K_RANK_FIXED64(
    const void *state,
    const bg_docking_stable_top_k_input_v1 *input,
    bg_docking_stable_top_k_row_v1 *out_rows,
    uint32_t *out_primary_slot_indices,
    uint64_t *out_primary_count,
    uint32_t *out_valid_slot_indices,
    uint64_t *out_valid_count,
    char *error_message,
    size_t error_capacity) {
    stable_top_k_clear_error(error_message, error_capacity);
    if (state == nullptr || input == nullptr || out_rows == nullptr ||
        out_primary_slot_indices == nullptr || out_primary_count == nullptr ||
        out_valid_slot_indices == nullptr || out_valid_count == nullptr) {
        return stable_top_k_fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            BG_DOCKING_STABLE_TOP_K_LANE
            " stable Top-K rank pointer is null");
    }
    if (input->struct_size != sizeof(*input) ||
        input->abi_version != BG_ABI_VERSION ||
        input->candidate_count != kHipStableTopKCandidateCount ||
        input->top_k_limit != BG_DOCKING_STABLE_TOP_K_LIMIT ||
        input->unit_system != BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL ||
        !stable_top_k_reserved_is_zero(input->reserved) ||
        input->scorer_rows == nullptr || input->validity_rows == nullptr ||
        input->coordinate_sha256 == nullptr) {
        return stable_top_k_fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            BG_DOCKING_STABLE_TOP_K_LANE
            " stable Top-K input identity is invalid");
    }
    const auto *typed = static_cast<const StableTopKState *>(state);
    StableTopKDeviceGuard guard;
    hipError_t status = hipSetDevice(typed->device_ordinal);
    if (status != hipSuccess) {
        return stable_top_k_fail_hip(
            status,
            error_message,
            error_capacity,
            "stable Top-K device selection");
    }
    StableTopKDeviceBuffer<bg_docking_scorer_v1_row_v1> device_scorer;
    StableTopKDeviceBuffer<bg_docking_pose_validity_row_v1> device_validity;
    StableTopKDeviceBuffer<uint8_t> device_coordinate_sha256;
    StableTopKDeviceBuffer<StableTopKDeviceOutput> device_output;

#define BG_HIP_STABLE_TOP_K_COPY(member, source, count, operation)           \
    do {                                                                     \
        status = member.copy_from((source), (count));                        \
        if (status != hipSuccess) {                                          \
            return stable_top_k_fail_hip(                                    \
                status, error_message, error_capacity, (operation));         \
        }                                                                    \
    } while (false)

    BG_HIP_STABLE_TOP_K_COPY(
        device_scorer,
        input->scorer_rows,
        kHipStableTopKCandidateCount,
        "stable Top-K scorer row copy");
    BG_HIP_STABLE_TOP_K_COPY(
        device_validity,
        input->validity_rows,
        kHipStableTopKCandidateCount,
        "stable Top-K validity row copy");
    BG_HIP_STABLE_TOP_K_COPY(
        device_coordinate_sha256,
        input->coordinate_sha256,
        kHipStableTopKCandidateCount * kHipStableTopKDigestSize,
        "stable Top-K coordinate identity copy");

#undef BG_HIP_STABLE_TOP_K_COPY

    status = device_output.allocate(1);
    if (status != hipSuccess) {
        return stable_top_k_fail_hip(
            status,
            error_message,
            error_capacity,
            "stable Top-K output allocation");
    }
    hipLaunchKernelGGL(
        stable_top_k_fixed64_kernel,
        dim3(1),
        dim3(1),
        0,
        0,
        device_scorer.get(),
        device_validity.get(),
        device_coordinate_sha256.get(),
        device_output.get());
    hipError_t execution_status = hipGetLastError();
    if (execution_status == hipSuccess) {
        execution_status = hipDeviceSynchronize();
    }
    if (execution_status != hipSuccess) {
        return stable_top_k_fail_hip(
            execution_status,
            error_message,
            error_capacity,
            "stable Top-K kernel execution");
    }
    StableTopKDeviceOutput host_output{};
    const hipError_t copy_status = device_output.copy_to(&host_output, 1);
    if (copy_status != hipSuccess) {
        return stable_top_k_fail_hip(
            copy_status,
            error_message,
            error_capacity,
            "stable Top-K result copy");
    }
    if (host_output.primary_count > kHipStableTopKCandidateCount ||
        host_output.valid_count > host_output.primary_count) {
        return stable_top_k_fail(
            BG_STATUS_BACKEND_ERROR,
            error_message,
            error_capacity,
            BG_DOCKING_STABLE_TOP_K_LANE
            " stable Top-K returned invalid counts");
    }
    std::memcpy(
        out_rows, host_output.rows, sizeof(host_output.rows));
    std::memcpy(
        out_primary_slot_indices,
        host_output.primary_slot_indices,
        sizeof(host_output.primary_slot_indices));
    std::memcpy(
        out_valid_slot_indices,
        host_output.valid_slot_indices,
        sizeof(host_output.valid_slot_indices));
    *out_primary_count = host_output.primary_count;
    *out_valid_count = host_output.valid_count;
    return BG_STATUS_OK;
}

extern "C" int32_t BG_DOCKING_STABLE_TOP_K_CLUSTER_FIXED64(
    const void *state,
    const bg_docking_rmsd_cluster_input_v1 *input,
    bg_docking_rmsd_cluster_row_v1 *out_rows,
    uint32_t *out_representative_slot_indices,
    uint64_t *out_cluster_count,
    uint32_t *out_top_k_slot_indices,
    uint64_t *out_top_k_count,
    char *error_message,
    size_t error_capacity) {
    stable_top_k_clear_error(error_message, error_capacity);
    if (state == nullptr || input == nullptr || out_rows == nullptr ||
        out_representative_slot_indices == nullptr ||
        out_cluster_count == nullptr || out_top_k_slot_indices == nullptr ||
        out_top_k_count == nullptr) {
        return stable_top_k_fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            BG_DOCKING_STABLE_TOP_K_LANE
            " RMSD cluster pointer is null");
    }
    if (input->struct_size != sizeof(*input) ||
        input->abi_version != BG_ABI_VERSION ||
        input->candidate_count != kHipStableTopKCandidateCount ||
        input->ligand_atom_count == 0 || input->ligand_atom_count > 512 ||
        input->valid_index_count > kHipStableTopKCandidateCount ||
        input->top_k_limit != BG_DOCKING_RMSD_CLUSTER_TOP_K_LIMIT ||
        input->unit_system != BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL ||
        !std::isfinite(input->rmsd_threshold_angstrom) ||
        input->rmsd_threshold_angstrom <= 0.0 ||
        !stable_top_k_reserved_is_zero(input->reserved) ||
        input->ranking_rows == nullptr ||
        input->valid_slot_indices == nullptr || input->x_angstrom == nullptr ||
        input->y_angstrom == nullptr || input->z_angstrom == nullptr) {
        return stable_top_k_fail(
            BG_STATUS_INVALID_ARGUMENT,
            error_message,
            error_capacity,
            BG_DOCKING_STABLE_TOP_K_LANE
            " RMSD cluster input identity is invalid");
    }
    const size_t atom_count = static_cast<size_t>(input->ligand_atom_count);
    if (atom_count > std::numeric_limits<size_t>::max() /
                         kHipStableTopKCandidateCount) {
        return stable_top_k_fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            error_message,
            error_capacity,
            BG_DOCKING_STABLE_TOP_K_LANE
            " RMSD cluster coordinate count overflowed");
    }
    const size_t coordinate_count = atom_count * kHipStableTopKCandidateCount;
    const auto *typed = static_cast<const StableTopKState *>(state);
    StableTopKDeviceGuard guard;
    hipError_t status = hipSetDevice(typed->device_ordinal);
    if (status != hipSuccess) {
        return stable_top_k_fail_hip(
            status,
            error_message,
            error_capacity,
            "RMSD cluster device selection");
    }
    StableTopKDeviceBuffer<bg_docking_stable_top_k_row_v1> device_ranking;
    StableTopKDeviceBuffer<uint32_t> device_valid_indices;
    StableTopKDeviceBuffer<double> device_x;
    StableTopKDeviceBuffer<double> device_y;
    StableTopKDeviceBuffer<double> device_z;
    StableTopKDeviceBuffer<RmsdClusterDeviceOutput> device_output;
    const uint32_t zero_index = 0;
    const uint32_t *const valid_source = input->valid_index_count == 0
                                             ? &zero_index
                                             : input->valid_slot_indices;
    const size_t valid_copy_count = input->valid_index_count == 0
                                        ? 1
                                        : static_cast<size_t>(
                                              input->valid_index_count);

#define BG_HIP_RMSD_CLUSTER_COPY(member, source, count, operation)          \
    do {                                                                     \
        status = member.copy_from((source), (count));                        \
        if (status != hipSuccess) {                                          \
            return stable_top_k_fail_hip(                                    \
                status, error_message, error_capacity, (operation));         \
        }                                                                    \
    } while (false)

    BG_HIP_RMSD_CLUSTER_COPY(
        device_ranking,
        input->ranking_rows,
        kHipStableTopKCandidateCount,
        "RMSD cluster ranking copy");
    BG_HIP_RMSD_CLUSTER_COPY(
        device_valid_indices,
        valid_source,
        valid_copy_count,
        "RMSD cluster valid index copy");
    BG_HIP_RMSD_CLUSTER_COPY(
        device_x, input->x_angstrom, coordinate_count, "RMSD cluster x copy");
    BG_HIP_RMSD_CLUSTER_COPY(
        device_y, input->y_angstrom, coordinate_count, "RMSD cluster y copy");
    BG_HIP_RMSD_CLUSTER_COPY(
        device_z, input->z_angstrom, coordinate_count, "RMSD cluster z copy");

#undef BG_HIP_RMSD_CLUSTER_COPY

    status = device_output.allocate(1);
    if (status != hipSuccess) {
        return stable_top_k_fail_hip(
            status,
            error_message,
            error_capacity,
            "RMSD cluster output allocation");
    }
    hipLaunchKernelGGL(
        direct_rmsd_cluster_fixed64_kernel,
        dim3(1),
        dim3(1),
        0,
        0,
        device_ranking.get(),
        device_valid_indices.get(),
        static_cast<size_t>(input->valid_index_count),
        device_x.get(),
        device_y.get(),
        device_z.get(),
        atom_count,
        input->rmsd_threshold_angstrom,
        device_output.get());
    hipError_t execution_status = hipGetLastError();
    if (execution_status == hipSuccess) {
        execution_status = hipDeviceSynchronize();
    }
    if (execution_status != hipSuccess) {
        return stable_top_k_fail_hip(
            execution_status,
            error_message,
            error_capacity,
            "RMSD cluster kernel execution");
    }
    RmsdClusterDeviceOutput host_output{};
    const hipError_t copy_status = device_output.copy_to(&host_output, 1);
    if (copy_status != hipSuccess) {
        return stable_top_k_fail_hip(
            copy_status,
            error_message,
            error_capacity,
            "RMSD cluster result copy");
    }
    if (host_output.cluster_count > kHipStableTopKCandidateCount ||
        host_output.top_k_count > BG_DOCKING_RMSD_CLUSTER_TOP_K_LIMIT) {
        return stable_top_k_fail(
            BG_STATUS_BACKEND_ERROR,
            error_message,
            error_capacity,
            BG_DOCKING_STABLE_TOP_K_LANE
            " RMSD cluster returned invalid counts");
    }
    if (host_output.numerical_failure != UINT32_C(0)) {
        return stable_top_k_fail(
            BG_STATUS_NUMERICAL_ERROR,
            error_message,
            error_capacity,
            BG_DOCKING_STABLE_TOP_K_LANE
            " RMSD cluster derived a non-finite distance");
    }
    std::memcpy(out_rows, host_output.rows, sizeof(host_output.rows));
    std::memcpy(
        out_representative_slot_indices,
        host_output.representative_slot_indices,
        sizeof(host_output.representative_slot_indices));
    std::memcpy(
        out_top_k_slot_indices,
        host_output.top_k_slot_indices,
        sizeof(host_output.top_k_slot_indices));
    *out_cluster_count = host_output.cluster_count;
    *out_top_k_count = host_output.top_k_count;
    return BG_STATUS_OK;
}
