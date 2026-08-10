#include "backend.hpp"

#include "../internal.hpp"

namespace betelgeuze::native::hip {

bg_status query_availability(
    int32_t device_ordinal,
    bool *out_available) noexcept {
    if (out_available == nullptr || device_ordinal < 0) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "HIP availability query arguments are invalid");
    }
    *out_available = false;
    return BG_STATUS_OK;
}

bg_status initialize(bg_context *context) noexcept {
    if (context == nullptr) {
        return fail(BG_STATUS_INVALID_ARGUMENT, "HIP context is null");
    }
    context->backend_state = nullptr;
    return fail(
        BG_STATUS_BACKEND_UNAVAILABLE,
        "HIP backend was disabled when the native library was built");
}

void shutdown(bg_context *context) noexcept {
    if (context != nullptr) {
        context->backend_state = nullptr;
    }
}

bg_status evaluate(
    const bg_context & /*context*/,
    const bg_system & /*system*/,
    const bg_forcefield & /*forcefield*/,
    bool /*compute_forces*/,
    cpu::Evaluation * /*out_evaluation*/) {
    return fail(
        BG_STATUS_BACKEND_UNAVAILABLE,
        "HIP backend was disabled when the native library was built");
}

bg_status get_last_evaluation_stats(
    const bg_context & /*context*/,
    EvaluationStats *out_stats) noexcept {
    if (out_stats == nullptr) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "HIP evaluation statistics output is null");
    }
    *out_stats = EvaluationStats{};
    return fail(
        BG_STATUS_BACKEND_UNAVAILABLE,
        "HIP backend was disabled when the native library was built");
}

#if defined(BG_HIP_TESTING)
bg_status set_allocation_failure(
    bg_context & /*context*/,
    uint64_t /*allocation_ordinal*/) noexcept {
    return fail(
        BG_STATUS_BACKEND_UNAVAILABLE,
        "HIP backend was disabled when the native library was built");
}

uint64_t live_allocation_count(const bg_context & /*context*/) noexcept {
    return UINT64_C(0);
}
#endif

}  // namespace betelgeuze::native::hip
