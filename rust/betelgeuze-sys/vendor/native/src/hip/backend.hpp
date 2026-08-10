#ifndef BETELGEUZE_NATIVE_HIP_BACKEND_HPP
#define BETELGEUZE_NATIVE_HIP_BACKEND_HPP

#include "betelgeuze/engine.h"

#include <cstdint>

struct bg_context;
struct bg_forcefield;
struct bg_system;

namespace betelgeuze::native::cpu {
struct Evaluation;
}

namespace betelgeuze::native::hip {

struct EvaluationStats final {
    /* Total cells in the regular grid, including empty cells.  Zero denotes
     * the deterministic direct canonical-pair fallback. */
    uint64_t cell_count = 0;
    /* Canonical i < j pairs inside max(cutoff, minimum pair distance).
     * Exclusions remain present in the neighbor list and are discarded by
     * the nonbonded kernel.  Extending the search radius preserves the ABI's
     * required minimum-distance validation-before-cutoff ordering. */
    uint64_t neighbor_pair_count = 0;
    /* Number of bond, angle, and torsion rows submitted to bonded kernels. */
    uint64_t bonded_contribution_count = 0;
};

bg_status query_availability(
    int32_t device_ordinal,
    bool *out_available) noexcept;

bg_status initialize(bg_context *context) noexcept;

void shutdown(bg_context *context) noexcept;

bg_status evaluate(
    const bg_context &context,
    const bg_system &system,
    const bg_forcefield &forcefield,
    bool compute_forces,
    cpu::Evaluation *out_evaluation);

bg_status get_last_evaluation_stats(
    const bg_context &context,
    EvaluationStats *out_stats) noexcept;

#if defined(BG_HIP_TESTING)
/* Internal fault injection.  Ordinals are one-based; zero disables failure. */
bg_status set_allocation_failure(
    bg_context &context,
    uint64_t allocation_ordinal) noexcept;

[[nodiscard]] uint64_t live_allocation_count(
    const bg_context &context) noexcept;
#endif

}  // namespace betelgeuze::native::hip

#endif  // BETELGEUZE_NATIVE_HIP_BACKEND_HPP
