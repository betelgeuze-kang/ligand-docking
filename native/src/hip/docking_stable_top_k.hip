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
