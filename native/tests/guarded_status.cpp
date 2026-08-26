#include "../src/internal.hpp"

#include <array>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <new>
#include <stdexcept>
#include <utility>

namespace betelgeuze::native {

// The product library intentionally hides its thread-local error buffer. This
// test-owned buffer exercises the exact header-defined production boundary
// without exporting internals or adding a product-library test hook.
thread_local std::array<char, kLastErrorCapacity> last_error{};

}  // namespace betelgeuze::native

namespace {

template <typename Function>
void expect_boundary(
    Function &&function,
    bg_status expected_status,
    const char *expected_message) {
    betelgeuze::native::set_last_error("stale test error");
    const bg_status observed = betelgeuze::native::guarded_status(
        std::forward<Function>(function));
    assert(observed == expected_status);
    assert(std::strcmp(
               betelgeuze::native::last_error.data(),
               expected_message) == 0);
}

void test_complete_guarded_status_matrix() {
    expect_boundary(
        []() -> bg_status { return BG_STATUS_INVALID_ARGUMENT; },
        BG_STATUS_INVALID_ARGUMENT,
        "");

    const std::length_error length_error("deterministic length error");
    expect_boundary(
        [&length_error]() -> bg_status { throw length_error; },
        BG_STATUS_CAPACITY_OVERFLOW,
        "native container capacity exceeded");

    expect_boundary(
        []() -> bg_status { throw std::bad_alloc(); },
        BG_STATUS_OUT_OF_MEMORY,
        "native allocation failed");

    const std::runtime_error runtime_error("deterministic runtime error");
    expect_boundary(
        [&runtime_error]() -> bg_status { throw runtime_error; },
        BG_STATUS_INTERNAL_ERROR,
        "native operation failed");

    expect_boundary(
        []() -> bg_status { throw static_cast<int32_t>(7); },
        BG_STATUS_INTERNAL_ERROR,
        "unknown native exception");

    expect_boundary(
        []() -> bg_status { return BG_STATUS_OK; },
        BG_STATUS_OK,
        "");
}

}  // namespace

int main() {
    test_complete_guarded_status_matrix();
    return 0;
}
