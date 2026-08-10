#include "hip/planning.hpp"

#include <hip/hip_runtime_api.h>

#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <limits>

namespace {

using betelgeuze::native::hip::detail::SizePlan;
using betelgeuze::native::hip::detail::checked_add_size;
using betelgeuze::native::hip::detail::checked_multiply_size;
using betelgeuze::native::hip::detail::checked_triangular_pair_count;
using betelgeuze::native::hip::detail::make_size_plan;
using betelgeuze::native::hip::detail::map_runtime_error_code;

[[noreturn]] void fail_test(const char *message) {
    std::fprintf(stderr, "HIP error-row test failure: %s\n", message);
    std::abort();
}

void require(bool condition, const char *message) {
    if (!condition) {
        fail_test(message);
    }
}

bool hip_device_is_required() noexcept {
    const char *required = std::getenv("BG_REQUIRE_HIP_DEVICE");
    return required != nullptr && required[0] == '1' && required[1] == '\0';
}

void test_checked_planner_rows() {
    constexpr std::size_t maximum =
        std::numeric_limits<std::size_t>::max();
    std::size_t output = std::size_t{73};
    require(
        !checked_add_size(maximum, std::size_t{1}, &output),
        "checked addition accepted an overflowing row");
    require(output == std::size_t{73}, "failed addition modified its output");
    require(
        !checked_multiply_size(maximum, std::size_t{2}, &output),
        "checked multiplication accepted an overflowing row");
    require(
        output == std::size_t{73},
        "failed multiplication modified its output");
    require(
        !checked_triangular_pair_count(maximum, &output),
        "triangular pair planner accepted an overflowing atom count");
    require(
        output == std::size_t{73},
        "failed triangular planning modified its output");

    SizePlan valid;
    require(
        make_size_plan(
            UINT64_C(6),
            UINT64_C(3),
            UINT64_C(2),
            UINT64_C(1),
            UINT64_C(8),
            UINT64_C(14),
            true,
            &valid) == BG_STATUS_OK,
        "valid combined-fixture size plan was rejected");
    require(valid.atom_count == std::size_t{6}, "planned atom count differed");
    require(
        valid.bonded_contribution_count == std::size_t{6},
        "planned bonded row count differed");
    require(valid.cell_count == std::size_t{8}, "planned cell count differed");
    require(
        valid.neighbor_pair_count == std::size_t{14},
        "planned neighbor count differed");
    require(
        valid.maximum_neighbor_pair_count == std::size_t{15},
        "planned maximum neighbor count differed");
    require(
        valid.scalar_atom_channel_bytes == std::size_t{48},
        "planned scalar channel bytes differed");
    require(
        valid.force_storage_bytes == std::size_t{144},
        "planned force storage bytes differed");
    require(
        valid.cell_index_bytes == std::size_t{48},
        "planned cell-index bytes differed");
    require(
        valid.cell_storage_bytes == std::size_t{72},
        "planned cell-storage bytes differed");
    require(
        valid.neighbor_pair_bytes == std::size_t{224},
        "planned neighbor-pair bytes differed");
    require(
        valid.contribution_count == std::size_t{20} &&
            valid.contribution_index_bytes == std::size_t{160},
        "planned contribution storage differed");

    SizePlan energy_only;
    require(
        make_size_plan(
            UINT64_C(6),
            UINT64_C(3),
            UINT64_C(2),
            UINT64_C(1),
            UINT64_C(8),
            UINT64_C(14),
            false,
            &energy_only) == BG_STATUS_OK,
        "valid energy-only size plan was rejected");
    require(
        energy_only.force_storage_bytes == std::size_t{0},
        "energy-only plan allocated force storage");

    SizePlan sentinel;
    sentinel.atom_count = std::size_t{91};
    sentinel.cell_count = std::size_t{92};
    sentinel.neighbor_pair_count = std::size_t{93};
    require(
        make_size_plan(
            UINT64_MAX,
            UINT64_C(0),
            UINT64_C(0),
            UINT64_C(0),
            UINT64_C(1),
            UINT64_C(0),
            true,
            &sentinel) == BG_STATUS_CAPACITY_OVERFLOW,
        "absurd atom-count row did not report capacity overflow");
    require(
        sentinel.atom_count == std::size_t{91} &&
            sentinel.cell_count == std::size_t{92} &&
            sentinel.neighbor_pair_count == std::size_t{93},
        "failed size planning partially committed its output");

    require(
        make_size_plan(
            UINT64_C(2),
            UINT64_C(0),
            UINT64_C(0),
            UINT64_C(0),
            UINT64_C(1),
            UINT64_C(2),
            true,
            &sentinel) == BG_STATUS_CAPACITY_OVERFLOW,
        "neighbor count above n*(n-1)/2 was accepted");
    require(
        make_size_plan(
            UINT64_C(1),
            UINT64_MAX,
            UINT64_C(1),
            UINT64_C(0),
            UINT64_C(1),
            UINT64_C(0),
            true,
            &sentinel) == BG_STATUS_CAPACITY_OVERFLOW,
        "overflowing bonded contribution sum was accepted");
    require(
        make_size_plan(
            UINT64_C(1),
            UINT64_C(0),
            UINT64_C(0),
            UINT64_C(0),
            UINT64_MAX,
            UINT64_C(0),
            true,
            &sentinel) == BG_STATUS_CAPACITY_OVERFLOW,
        "overflowing cell storage was accepted");
    require(
        make_size_plan(
            UINT64_C(1),
            UINT64_MAX,
            UINT64_C(0),
            UINT64_C(0),
            UINT64_C(1),
            UINT64_C(0),
            true,
            &sentinel) == BG_STATUS_CAPACITY_OVERFLOW,
        "overflowing contribution storage was accepted");
    require(
        make_size_plan(
            UINT64_C(1),
            UINT64_C(0),
            UINT64_C(0),
            UINT64_C(0),
            UINT64_C(1),
            UINT64_C(0),
            false,
            nullptr) == BG_STATUS_INVALID_ARGUMENT,
        "null size-plan output did not report invalid argument");
}

void test_runtime_error_mapping_rows() {
    const int success = static_cast<int>(hipSuccess);
    const int out_of_memory = static_cast<int>(hipErrorOutOfMemory);
    const int invalid_value = static_cast<int>(hipErrorInvalidValue);
    require(
        map_runtime_error_code(success, success, out_of_memory) ==
            BG_STATUS_OK,
        "HIP success did not map to BG_STATUS_OK");
    require(
        map_runtime_error_code(out_of_memory, success, out_of_memory) ==
            BG_STATUS_OUT_OF_MEMORY,
        "HIP out-of-memory did not map to BG_STATUS_OUT_OF_MEMORY");
    require(
        map_runtime_error_code(invalid_value, success, out_of_memory) ==
            BG_STATUS_BACKEND_ERROR,
        "HIP invalid-value did not map to BG_STATUS_BACKEND_ERROR");
}

bool device_zero_is_available() {
    int device_count = 0;
    const hipError_t status = hipGetDeviceCount(&device_count);
    if (status == hipErrorNoDevice) {
        return false;
    }
    require(status == hipSuccess, "hipGetDeviceCount failed");
    return device_count > 0;
}

void test_actual_absurd_allocation_row() {
    require(hipSetDevice(0) == hipSuccess, "hipSetDevice(0) failed");
    void *allocation = nullptr;
    const hipError_t observed = hipMalloc(
        &allocation, std::numeric_limits<std::size_t>::max());
    if (observed == hipSuccess) {
        static_cast<void>(hipFree(allocation));
        fail_test("absurd hipMalloc unexpectedly succeeded");
    }
    require(allocation == nullptr, "failed hipMalloc returned an allocation");
    require(
        observed == hipErrorOutOfMemory || observed == hipErrorInvalidValue,
        "absurd hipMalloc returned an unexpected runtime error");

    const bg_status mapped = map_runtime_error_code(
        static_cast<int>(observed),
        static_cast<int>(hipSuccess),
        static_cast<int>(hipErrorOutOfMemory));
    if (observed == hipErrorOutOfMemory) {
        require(
            mapped == BG_STATUS_OUT_OF_MEMORY,
            "actual HIP OOM did not map to BG_STATUS_OUT_OF_MEMORY");
    } else {
        require(
            mapped == BG_STATUS_BACKEND_ERROR,
            "actual invalid allocation did not map to BG_STATUS_BACKEND_ERROR");
    }
    static_cast<void>(hipGetLastError());
}

}  // namespace

int main() {
    test_checked_planner_rows();
    test_runtime_error_mapping_rows();
    if (!device_zero_is_available()) {
        if (hip_device_is_required()) {
            fail_test(
                "BG_REQUIRE_HIP_DEVICE=1 but no HIP device is available at "
                "ordinal zero");
        }
        std::puts("SKIP: no HIP device is available at ordinal zero");
        return 77;
    }
    test_actual_absurd_allocation_row();
    std::puts("HIP overflow and OOM error-row tests passed");
    return 0;
}
