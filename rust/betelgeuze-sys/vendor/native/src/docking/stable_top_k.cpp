#include "../internal.hpp"
#include "../hip/provider.h"
#include "../rust/provider.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <memory>

#ifndef BG_HAS_HIP_SAFE_PROVIDER
#  define BG_HAS_HIP_SAFE_PROVIDER 0
#endif
#ifndef BG_ENABLE_HIP
#  define BG_ENABLE_HIP 0
#endif

namespace betelgeuze::native::docking::ranking {
namespace {

constexpr std::size_t kCandidateCount =
    BG_DOCKING_FIXED64_CANDIDATE_COUNT;
constexpr std::size_t kTopKLimit = BG_DOCKING_STABLE_TOP_K_LIMIT;
constexpr std::size_t kDigestSize = 32;

struct CppStableTopKState final {};

struct RankedEntry final {
    std::size_t slot_index = 0;
    double total_score = 0.0;
    std::array<uint8_t, kDigestSize> coordinate_sha256{};
};

struct DerivedRanking final {
    std::array<bg_docking_stable_top_k_row_v1, kCandidateCount> rows{};
    std::array<uint32_t, kCandidateCount> primary_slot_indices{};
    std::size_t primary_count = 0;
    std::array<uint32_t, kCandidateCount> valid_slot_indices{};
    std::size_t valid_count = 0;
};

[[nodiscard]] bool digest_is_zero(const uint8_t *digest) noexcept {
    return std::all_of(
        digest, digest + kDigestSize, [](uint8_t value) {
            return value == UINT8_C(0);
        });
}

[[nodiscard]] bool all_zero(
    const double *values,
    std::size_t count) noexcept {
    return std::all_of(values, values + count, [](double value) {
        return value == 0.0;
    });
}

[[nodiscard]] bool scorer_failure_evidence_is_zero(
    const bg_docking_scorer_v1_row_v1 &row) noexcept {
    return all_zero(
               row.weighted_terms,
               BG_DOCKING_SCORER_V1_TERM_COUNT) &&
           row.total_score == 0.0 &&
           row.receptor_candidate_pair_count == 0 &&
           row.ligand_pair_count == 0 && row.hbond_count == 0 &&
           row.hydrophobic_contact_count == 0 &&
           row.buried_polar_count == 0;
}

[[nodiscard]] bool validity_measurements_are_finite(
    const bg_docking_pose_validity_row_v1 &row) noexcept {
    const std::array<double, 11> values = {
        row.rotation_orthogonality_max_error,
        row.rotation_determinant,
        row.max_bond_length_delta_angstrom,
        row.minimum_ligand_nonbonded_distance_angstrom,
        row.minimum_receptor_ligand_distance_angstrom,
        row.minimum_declared_chiral_volume,
        row.maximum_pocket_center_distance_angstrom,
        row.element_vdw_ligand_minimum_distance_angstrom,
        row.element_vdw_ligand_minimum_ratio,
        row.element_vdw_receptor_minimum_distance_angstrom,
        row.element_vdw_receptor_minimum_ratio,
    };
    return std::all_of(values.begin(), values.end(), [](double value) {
        return std::isfinite(value);
    });
}

[[nodiscard]] bool validity_failure_evidence_is_zero(
    const bg_docking_pose_validity_row_v1 &row) noexcept {
    return row.passed_check_mask == 0 && row.blocker_mask == 0 &&
           row.atom_count == 0 &&
           row.rotation_orthogonality_max_error == 0.0 &&
           row.rotation_determinant == 0.0 &&
           row.max_bond_length_delta_angstrom == 0.0 &&
           row.minimum_ligand_nonbonded_distance_angstrom == 0.0 &&
           row.evaluated_ligand_nonbonded_pair_count == 0 &&
           row.excluded_ligand_pair_count == 0 &&
           row.minimum_receptor_ligand_distance_angstrom == 0.0 &&
           row.evaluated_receptor_ligand_pair_count == 0 &&
           row.minimum_declared_chiral_volume == 0.0 &&
           row.declared_chirality_center_count == 0 &&
           row.maximum_pocket_center_distance_angstrom == 0.0 &&
           row.element_vdw_ligand_pair_count == 0 &&
           row.element_vdw_ligand_severe_overlap_count == 0 &&
           row.element_vdw_ligand_minimum_distance_angstrom == 0.0 &&
           row.element_vdw_ligand_minimum_ratio == 0.0 &&
           row.element_vdw_receptor_candidate_pair_count == 0 &&
           row.element_vdw_receptor_full_cartesian_pair_count == 0 &&
           row.element_vdw_receptor_cell_count == 0 &&
           row.element_vdw_receptor_severe_overlap_count == 0 &&
           row.element_vdw_receptor_minimum_distance_angstrom == 0.0 &&
           row.element_vdw_receptor_minimum_ratio == 0.0;
}

[[nodiscard]] double canonical_score(double value) noexcept {
    return value == 0.0 ? 0.0 : value;
}

[[nodiscard]] bool entry_less(
    const RankedEntry &left,
    const RankedEntry &right) noexcept {
    if (left.total_score < right.total_score) {
        return true;
    }
    if (right.total_score < left.total_score) {
        return false;
    }
    if (left.slot_index != right.slot_index) {
        return left.slot_index < right.slot_index;
    }
    return left.coordinate_sha256 < right.coordinate_sha256;
}

[[nodiscard]] bg_status validate_scorer_row(
    const bg_docking_scorer_v1_row_v1 &row,
    std::size_t slot,
    const uint8_t *coordinate_sha256) noexcept {
    if (row.slot_index != slot || row.reserved0 != 0 ||
        !reserved_is_zero(row.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "stable Top-K scorer row identity is invalid");
    }
    if (row.status == BG_DOCKING_SCORER_V1_ROW_SCORED) {
        if (row.failure_code != BG_DOCKING_SCORER_V1_FAILURE_NONE ||
            digest_is_zero(coordinate_sha256) ||
            !std::isfinite(row.total_score) ||
            std::any_of(
                std::begin(row.weighted_terms),
                std::end(row.weighted_terms),
                [](double value) { return !std::isfinite(value); })) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "stable Top-K scored row evidence is invalid");
        }
        double sum = 0.0;
        for (const double value : row.weighted_terms) {
            sum += value;
        }
        if (std::abs(sum - row.total_score) > 1.0e-12) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "stable Top-K score-term semantics are inconsistent");
        }
        return BG_STATUS_OK;
    }
    if (row.status != BG_DOCKING_SCORER_V1_ROW_TYPED_FAILURE ||
        row.failure_code <
            BG_DOCKING_SCORER_V1_FAILURE_UPSTREAM_NOT_ADMITTED ||
        row.failure_code > BG_DOCKING_SCORER_V1_FAILURE_NONFINITE_SCORE ||
        !digest_is_zero(coordinate_sha256) ||
        !scorer_failure_evidence_is_zero(row)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "stable Top-K scorer failure evidence is invalid");
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status validate_validity_row(
    const bg_docking_pose_validity_row_v1 &row,
    const bg_docking_scorer_v1_row_v1 &scorer,
    std::size_t slot) noexcept {
    if (row.slot_index != slot || !reserved_is_zero(row.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "stable Top-K validity row identity is invalid");
    }
    if (row.status == BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED) {
        const uint32_t unknown_checks =
            row.passed_check_mask &
            ~static_cast<uint32_t>(BG_DOCKING_POSE_VALIDITY_CHECK_ALL);
        if (scorer.status != BG_DOCKING_SCORER_V1_ROW_SCORED ||
            row.failure_code != BG_DOCKING_POSE_VALIDITY_FAILURE_NONE ||
            row.upstream_scorer_failure_code !=
                BG_DOCKING_SCORER_V1_FAILURE_NONE ||
            unknown_checks != 0 ||
            row.blocker_mask !=
                (BG_DOCKING_POSE_VALIDITY_CHECK_ALL ^
                 row.passed_check_mask) ||
            row.observed_count != 0 || row.atom_count == 0 ||
            !validity_measurements_are_finite(row)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "stable Top-K evaluated validity evidence is invalid");
        }
        return BG_STATUS_OK;
    }
    if (!validity_failure_evidence_is_zero(row)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "stable Top-K failed validity row retains measurements");
    }
    if (row.status ==
        BG_DOCKING_POSE_VALIDITY_ROW_UPSTREAM_SCORER_FAILURE) {
        if (scorer.status != BG_DOCKING_SCORER_V1_ROW_TYPED_FAILURE ||
            row.failure_code !=
                BG_DOCKING_POSE_VALIDITY_FAILURE_UPSTREAM_SCORER ||
            row.upstream_scorer_failure_code != scorer.failure_code ||
            row.observed_count != 0) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "stable Top-K upstream failure is cross-wired");
        }
        return BG_STATUS_OK;
    }
    if (row.status != BG_DOCKING_POSE_VALIDITY_ROW_TYPED_FAILURE ||
        scorer.status != BG_DOCKING_SCORER_V1_ROW_SCORED ||
        row.failure_code <
            BG_DOCKING_POSE_VALIDITY_FAILURE_INVALID_CANDIDATE_COORDINATES ||
        row.failure_code >
            BG_DOCKING_POSE_VALIDITY_FAILURE_NONFINITE_DERIVED_MEASUREMENT ||
        row.upstream_scorer_failure_code !=
            BG_DOCKING_SCORER_V1_FAILURE_NONE) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "stable Top-K typed validity failure is invalid");
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bool ranges_overlap(
    const void *left,
    std::size_t left_size,
    const void *right,
    std::size_t right_size) noexcept {
    if (left == nullptr || right == nullptr || left_size == 0 ||
        right_size == 0) {
        return false;
    }
    const uintptr_t left_begin = reinterpret_cast<uintptr_t>(left);
    const uintptr_t right_begin = reinterpret_cast<uintptr_t>(right);
    if (left_begin > std::numeric_limits<uintptr_t>::max() - left_size ||
        right_begin > std::numeric_limits<uintptr_t>::max() - right_size) {
        return true;
    }
    return left_begin < right_begin + right_size &&
           right_begin < left_begin + left_size;
}

[[nodiscard]] bg_status validate_input_and_output(
    const bg_docking_stable_top_k_input_v1 &input,
    const bg_docking_stable_top_k_output_v1 &output) noexcept {
    bg_status status = validate_descriptor_header(
        input.struct_size,
        sizeof(input),
        input.abi_version,
        "stable Top-K input size does not match ABI v1",
        "stable Top-K input ABI version does not match");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = validate_descriptor_header(
        output.struct_size,
        sizeof(output),
        output.abi_version,
        "stable Top-K output size does not match ABI v1",
        "stable Top-K output ABI version does not match");
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (validate_unit_system(input.unit_system) != BG_STATUS_OK ||
        validate_unit_system(output.unit_system) != BG_STATUS_OK ||
        input.candidate_count != kCandidateCount ||
        input.top_k_limit != kTopKLimit ||
        !reserved_is_zero(input.reserved) || output.reserved0 != 0 ||
        output.reserved1 != 0 || output.reserved2 != 0 ||
        !reserved_is_zero(output.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "stable Top-K denominator, units, or reserved fields are invalid");
    }
    if (input.scorer_rows == nullptr || input.validity_rows == nullptr ||
        input.coordinate_sha256 == nullptr || output.rows == nullptr ||
        output.primary_slot_indices == nullptr ||
        output.valid_slot_indices == nullptr ||
        !pointer_is_aligned(input.scorer_rows) ||
        !pointer_is_aligned(input.validity_rows) ||
        !pointer_is_aligned(output.rows) ||
        !pointer_is_aligned(output.primary_slot_indices) ||
        !pointer_is_aligned(output.valid_slot_indices) ||
        output.row_capacity < kCandidateCount ||
        output.primary_index_capacity < kCandidateCount ||
        output.valid_index_capacity < kCandidateCount) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "stable Top-K input channel or output capacity is invalid");
    }
    const std::array<std::pair<const void *, std::size_t>, 3> inputs = {{
        {input.scorer_rows,
         kCandidateCount * sizeof(bg_docking_scorer_v1_row_v1)},
        {input.validity_rows,
         kCandidateCount * sizeof(bg_docking_pose_validity_row_v1)},
        {input.coordinate_sha256, kCandidateCount * kDigestSize},
    }};
    const std::array<std::pair<const void *, std::size_t>, 3> outputs = {{
        {output.rows,
         kCandidateCount * sizeof(bg_docking_stable_top_k_row_v1)},
        {output.primary_slot_indices, kCandidateCount * sizeof(uint32_t)},
        {output.valid_slot_indices, kCandidateCount * sizeof(uint32_t)},
    }};
    for (std::size_t first = 0; first < outputs.size(); ++first) {
        for (std::size_t second = first + 1; second < outputs.size();
             ++second) {
            if (ranges_overlap(
                    outputs[first].first,
                    outputs[first].second,
                    outputs[second].first,
                    outputs[second].second)) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "stable Top-K output buffers overlap");
            }
        }
        for (const auto &input_range : inputs) {
            if (ranges_overlap(
                    outputs[first].first,
                    outputs[first].second,
                    input_range.first,
                    input_range.second)) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "stable Top-K input and output buffers overlap");
            }
        }
    }
    for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
        const uint8_t *const digest =
            input.coordinate_sha256 + slot * kDigestSize;
        status = validate_scorer_row(input.scorer_rows[slot], slot, digest);
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = validate_validity_row(
            input.validity_rows[slot], input.scorer_rows[slot], slot);
        if (status != BG_STATUS_OK) {
            return status;
        }
    }
    return BG_STATUS_OK;
}

[[nodiscard]] DerivedRanking derive_cpp(
    const bg_docking_stable_top_k_input_v1 &input) noexcept {
    std::array<RankedEntry, kCandidateCount> primary{};
    std::size_t primary_count = 0;
    for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
        const auto &scorer = input.scorer_rows[slot];
        if (scorer.status != BG_DOCKING_SCORER_V1_ROW_SCORED) {
            continue;
        }
        RankedEntry entry{};
        entry.slot_index = slot;
        entry.total_score = canonical_score(scorer.total_score);
        std::copy_n(
            input.coordinate_sha256 + slot * kDigestSize,
            kDigestSize,
            entry.coordinate_sha256.begin());
        std::size_t position = primary_count;
        while (position > 0 && entry_less(entry, primary[position - 1])) {
            primary[position] = primary[position - 1];
            --position;
        }
        primary[position] = entry;
        ++primary_count;
    }
    std::array<uint32_t, kCandidateCount> stable_rank{};
    std::array<uint32_t, kCandidateCount> stable_valid_rank{};
    DerivedRanking result{};
    result.primary_count = primary_count;
    for (std::size_t offset = 0; offset < primary_count; ++offset) {
        const std::size_t slot = primary[offset].slot_index;
        result.primary_slot_indices[offset] = static_cast<uint32_t>(slot);
        stable_rank[slot] = static_cast<uint32_t>(offset + 1);
        const auto &validity = input.validity_rows[slot];
        if (validity.status == BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED &&
            validity.passed_check_mask ==
                BG_DOCKING_POSE_VALIDITY_CHECK_ALL) {
            result.valid_slot_indices[result.valid_count] =
                static_cast<uint32_t>(slot);
            stable_valid_rank[slot] =
                static_cast<uint32_t>(result.valid_count + 1);
            ++result.valid_count;
        }
    }
    for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
        auto &row = result.rows[slot];
        row.slot_index = static_cast<uint32_t>(slot);
        if (input.scorer_rows[slot].status ==
            BG_DOCKING_SCORER_V1_ROW_SCORED) {
            row.rank_eligible = UINT8_C(1);
            row.valid_rank_eligible =
                stable_valid_rank[slot] == 0 ? UINT8_C(0) : UINT8_C(1);
            row.stable_rank = stable_rank[slot];
            row.stable_valid_rank = stable_valid_rank[slot];
            row.total_score =
                canonical_score(input.scorer_rows[slot].total_score);
            std::copy_n(
                input.coordinate_sha256 + slot * kDigestSize,
                kDigestSize,
                row.coordinate_sha256);
        }
    }
    return result;
}

[[nodiscard]] bool derived_shape_is_valid(
    const DerivedRanking &result,
    const bg_docking_stable_top_k_input_v1 &input) noexcept {
    if (result.primary_count > kCandidateCount ||
        result.valid_count > result.primary_count) {
        return false;
    }
    std::array<uint8_t, kCandidateCount> primary_seen{};
    std::array<uint8_t, kCandidateCount> valid_seen{};
    for (std::size_t offset = 0; offset < result.primary_count; ++offset) {
        const std::size_t slot = result.primary_slot_indices[offset];
        if (slot >= kCandidateCount || primary_seen[slot] != 0 ||
            result.rows[slot].stable_rank != offset + 1) {
            return false;
        }
        primary_seen[slot] = UINT8_C(1);
    }
    for (std::size_t offset = 0; offset < result.valid_count; ++offset) {
        const std::size_t slot = result.valid_slot_indices[offset];
        if (slot >= kCandidateCount || valid_seen[slot] != 0 ||
            primary_seen[slot] == 0 ||
            result.rows[slot].stable_valid_rank != offset + 1) {
            return false;
        }
        valid_seen[slot] = UINT8_C(1);
    }
    for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
        const auto &row = result.rows[slot];
        const bool eligible = primary_seen[slot] != 0;
        const bool valid_eligible = valid_seen[slot] != 0;
        if (row.slot_index != slot || row.rank_eligible != eligible ||
            row.valid_rank_eligible != valid_eligible ||
            (eligible != (row.stable_rank != 0)) ||
            (valid_eligible != (row.stable_valid_rank != 0)) ||
            !reserved_is_zero(row.reserved) || row.reserved0 != 0) {
            return false;
        }
        if (eligible) {
            if (!std::isfinite(row.total_score) ||
                digest_is_zero(row.coordinate_sha256) ||
                row.total_score !=
                    canonical_score(input.scorer_rows[slot].total_score) ||
                std::memcmp(
                    row.coordinate_sha256,
                    input.coordinate_sha256 + slot * kDigestSize,
                    kDigestSize) != 0) {
                return false;
            }
        } else if (row.total_score != 0.0 ||
                   !digest_is_zero(row.coordinate_sha256)) {
            return false;
        }
    }
    return true;
}

[[nodiscard]] bg_status provider_failure(
    int32_t raw_status,
    const bg_rust_cpu_error_v1 &error,
    const char *fallback) noexcept {
    return fail(
        static_cast<bg_status>(raw_status),
        error.message[0] == '\0' ? fallback : error.message);
}

#if BG_HAS_HIP_SAFE_PROVIDER || BG_ENABLE_HIP
[[nodiscard]] bg_status hip_provider_failure(
    int32_t raw_status,
    const char *provider_error,
    const char *fallback) noexcept {
    return fail(
        static_cast<bg_status>(raw_status),
        provider_error != nullptr && provider_error[0] != '\0'
            ? provider_error
            : fallback);
}
#endif

}  // namespace

void destroy_cpp_state(void *state) noexcept {
    delete static_cast<CppStableTopKState *>(state);
}

}  // namespace betelgeuze::native::docking::ranking

extern "C" BG_API bg_status BG_CALL bg_docking_stable_top_k_input_v1_init(
    bg_docking_stable_top_k_input_v1 *input,
    std::size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            input,
            caller_struct_size,
            sizeof(*input),
            caller_abi_version,
            "stable Top-K input initializer pointer is null",
            "stable Top-K input initializer size does not match",
            "stable Top-K input initializer ABI version does not match");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *input = bg_docking_stable_top_k_input_v1{};
        input->struct_size = static_cast<uint32_t>(sizeof(*input));
        input->abi_version = BG_ABI_VERSION;
        input->candidate_count = BG_DOCKING_FIXED64_CANDIDATE_COUNT;
        input->top_k_limit = BG_DOCKING_STABLE_TOP_K_LIMIT;
        input->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_docking_stable_top_k_output_v1_init(
    bg_docking_stable_top_k_output_v1 *output,
    std::size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            output,
            caller_struct_size,
            sizeof(*output),
            caller_abi_version,
            "stable Top-K output initializer pointer is null",
            "stable Top-K output initializer size does not match",
            "stable Top-K output initializer ABI version does not match");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *output = bg_docking_stable_top_k_output_v1{};
        output->struct_size = static_cast<uint32_t>(sizeof(*output));
        output->abi_version = BG_ABI_VERSION;
        output->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_docking_stable_top_k_v1_create(
    const bg_context *context,
    bg_docking_stable_top_k_v1 **out_ranker) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::docking::ranking;
    if (out_ranker != nullptr) {
        *out_ranker = nullptr;
    }
    return guarded_status([&]() -> bg_status {
        if (context == nullptr || out_ranker == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "stable Top-K create input and output must not be null");
        }
        auto ranker = std::make_unique<bg_docking_stable_top_k_v1>();
        ranker->backend = context->backend;
        ranker->device_ordinal = context->device_ordinal;
        bg_status status = BG_STATUS_OK;
        if (context->backend == BG_BACKEND_CPP_CPU_REFERENCE) {
            ranker->provider_state = new CppStableTopKState{};
        } else if (context->backend == BG_BACKEND_RUST_CPU) {
            bg_rust_cpu_error_v1 error{};
            error.struct_size = sizeof(error);
            error.abi_version = BG_RUST_CPU_PROVIDER_ABI_VERSION;
            const int32_t raw_status =
                bg_rust_cpu_docking_stable_top_k_v1_create(
                    &ranker->provider_state, &error);
            if (raw_status != BG_STATUS_OK) {
                return provider_failure(
                    raw_status,
                    error,
                    "rust_cpu stable Top-K create failed");
            }
        } else if (context->backend == BG_BACKEND_HIP_SAFE) {
#if BG_HAS_HIP_SAFE_PROVIDER
            char provider_error[BG_HIP_SAFE_ERROR_CAPACITY]{};
            const int32_t raw_status =
                bg_hip_safe_docking_stable_top_k_v1_create(
                    context->device_ordinal,
                    &ranker->provider_state,
                    provider_error,
                    sizeof(provider_error));
            if (raw_status != BG_STATUS_OK) {
                return hip_provider_failure(
                    raw_status,
                    provider_error,
                    "hip_safe stable Top-K create failed");
            }
#else
            return fail(
                BG_STATUS_BACKEND_UNAVAILABLE,
                "hip_safe stable Top-K provider is not compiled; fallback is forbidden");
#endif
        } else if (context->backend == BG_BACKEND_HIP_FAST) {
#if BG_ENABLE_HIP
            char provider_error[BG_HIP_SAFE_ERROR_CAPACITY]{};
            const int32_t raw_status =
                bg_hip_fast_docking_stable_top_k_v1_create(
                    context->device_ordinal,
                    &ranker->provider_state,
                    provider_error,
                    sizeof(provider_error));
            if (raw_status != BG_STATUS_OK) {
                return hip_provider_failure(
                    raw_status,
                    provider_error,
                    "hip_fast stable Top-K create failed");
            }
#else
            return fail(
                BG_STATUS_BACKEND_UNAVAILABLE,
                "hip_fast stable Top-K provider is not compiled; fallback is forbidden");
#endif
        } else {
            return fail(
                BG_STATUS_UNSUPPORTED_BACKEND,
                "selected backend has no stable Top-K implementation");
        }
        if (status != BG_STATUS_OK || ranker->provider_state == nullptr) {
            return status == BG_STATUS_OK
                       ? fail(
                             BG_STATUS_INTERNAL_ERROR,
                             "stable Top-K provider returned null state")
                       : status;
        }
        *out_ranker = ranker.release();
        return BG_STATUS_OK;
    });
}

extern "C" BG_API void BG_CALL bg_docking_stable_top_k_v1_destroy(
    bg_docking_stable_top_k_v1 *ranker) BG_NOEXCEPT {
    if (ranker == nullptr) {
        return;
    }
    if (ranker->backend == BG_BACKEND_CPP_CPU_REFERENCE) {
        betelgeuze::native::docking::ranking::destroy_cpp_state(
            ranker->provider_state);
    } else if (ranker->backend == BG_BACKEND_RUST_CPU) {
        bg_rust_cpu_docking_stable_top_k_v1_destroy(
            ranker->provider_state);
#if BG_HAS_HIP_SAFE_PROVIDER
    } else if (ranker->backend == BG_BACKEND_HIP_SAFE) {
        bg_hip_safe_docking_stable_top_k_v1_destroy(
            ranker->provider_state);
#endif
#if BG_ENABLE_HIP
    } else if (ranker->backend == BG_BACKEND_HIP_FAST) {
        bg_hip_fast_docking_stable_top_k_v1_destroy(
            ranker->provider_state);
#endif
    }
    delete ranker;
}

extern "C" BG_API bg_status BG_CALL
bg_docking_stable_top_k_v1_get_backend(
    const bg_docking_stable_top_k_v1 *ranker,
    bg_backend *backend) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        if (ranker == nullptr || backend == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "stable Top-K handle and backend output must not be null");
        }
        *backend = ranker->backend;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL
bg_docking_stable_top_k_v1_rank_fixed64(
    const bg_context *context,
    const bg_docking_stable_top_k_v1 *ranker,
    const bg_docking_stable_top_k_input_v1 *input,
    bg_docking_stable_top_k_output_v1 *output) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::docking::ranking;
    return guarded_status([&]() -> bg_status {
        if (context == nullptr || ranker == nullptr || input == nullptr ||
            output == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "stable Top-K rank inputs and output must not be null");
        }
        if (context->backend != ranker->backend ||
            context->device_ordinal != ranker->device_ordinal) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "stable Top-K handle is cross-wired to another backend or device");
        }
        bg_status status = validate_input_and_output(*input, *output);
        if (status != BG_STATUS_OK) {
            return status;
        }
        DerivedRanking candidate{};
        if (ranker->backend == BG_BACKEND_CPP_CPU_REFERENCE) {
            if (ranker->provider_state == nullptr) {
                return fail(
                    BG_STATUS_INTERNAL_ERROR,
                    "stable Top-K C++ provider state is null");
            }
            candidate = derive_cpp(*input);
        } else if (ranker->backend == BG_BACKEND_RUST_CPU) {
            bg_rust_cpu_error_v1 error{};
            error.struct_size = sizeof(error);
            error.abi_version = BG_RUST_CPU_PROVIDER_ABI_VERSION;
            uint64_t primary_count = 0;
            uint64_t valid_count = 0;
            const int32_t raw_status =
                bg_rust_cpu_docking_stable_top_k_v1_rank_fixed64(
                    ranker->provider_state,
                    input,
                    candidate.rows.data(),
                    candidate.primary_slot_indices.data(),
                    &primary_count,
                    candidate.valid_slot_indices.data(),
                    &valid_count,
                    &error);
            if (raw_status != BG_STATUS_OK) {
                return provider_failure(
                    raw_status,
                    error,
                    "rust_cpu stable Top-K batch failed");
            }
            if (primary_count > kCandidateCount ||
                valid_count > kCandidateCount) {
                return fail(
                    BG_STATUS_BACKEND_ERROR,
                    "rust_cpu stable Top-K counts exceed fixed64");
            }
            candidate.primary_count =
                static_cast<std::size_t>(primary_count);
            candidate.valid_count = static_cast<std::size_t>(valid_count);
#if BG_HAS_HIP_SAFE_PROVIDER
        } else if (ranker->backend == BG_BACKEND_HIP_SAFE) {
            char provider_error[BG_HIP_SAFE_ERROR_CAPACITY]{};
            uint64_t primary_count = 0;
            uint64_t valid_count = 0;
            const int32_t raw_status =
                bg_hip_safe_docking_stable_top_k_v1_rank_fixed64(
                    ranker->provider_state,
                    input,
                    candidate.rows.data(),
                    candidate.primary_slot_indices.data(),
                    &primary_count,
                    candidate.valid_slot_indices.data(),
                    &valid_count,
                    provider_error,
                    sizeof(provider_error));
            if (raw_status != BG_STATUS_OK) {
                return hip_provider_failure(
                    raw_status,
                    provider_error,
                    "hip_safe stable Top-K batch failed");
            }
            if (primary_count > kCandidateCount ||
                valid_count > kCandidateCount) {
                return fail(
                    BG_STATUS_BACKEND_ERROR,
                    "hip_safe stable Top-K counts exceed fixed64");
            }
            candidate.primary_count =
                static_cast<std::size_t>(primary_count);
            candidate.valid_count = static_cast<std::size_t>(valid_count);
#endif
#if BG_ENABLE_HIP
        } else if (ranker->backend == BG_BACKEND_HIP_FAST) {
            char provider_error[BG_HIP_SAFE_ERROR_CAPACITY]{};
            uint64_t primary_count = 0;
            uint64_t valid_count = 0;
            const int32_t raw_status =
                bg_hip_fast_docking_stable_top_k_v1_rank_fixed64(
                    ranker->provider_state,
                    input,
                    candidate.rows.data(),
                    candidate.primary_slot_indices.data(),
                    &primary_count,
                    candidate.valid_slot_indices.data(),
                    &valid_count,
                    provider_error,
                    sizeof(provider_error));
            if (raw_status != BG_STATUS_OK) {
                return hip_provider_failure(
                    raw_status,
                    provider_error,
                    "hip_fast stable Top-K batch failed");
            }
            if (primary_count > kCandidateCount ||
                valid_count > kCandidateCount) {
                return fail(
                    BG_STATUS_BACKEND_ERROR,
                    "hip_fast stable Top-K counts exceed fixed64");
            }
            candidate.primary_count =
                static_cast<std::size_t>(primary_count);
            candidate.valid_count = static_cast<std::size_t>(valid_count);
#endif
        } else {
            return fail(
                BG_STATUS_BACKEND_UNAVAILABLE,
                "selected backend has no qualified stable Top-K kernel; fallback is forbidden");
        }
        if (!derived_shape_is_valid(candidate, *input)) {
            return fail(
                BG_STATUS_BACKEND_ERROR,
                "stable Top-K backend returned inconsistent ranking evidence");
        }
        std::memcpy(
            output->rows, candidate.rows.data(), sizeof(candidate.rows));
        std::memcpy(
            output->primary_slot_indices,
            candidate.primary_slot_indices.data(),
            sizeof(candidate.primary_slot_indices));
        std::memcpy(
            output->valid_slot_indices,
            candidate.valid_slot_indices.data(),
            sizeof(candidate.valid_slot_indices));
        output->row_count = kCandidateCount;
        output->primary_index_count = candidate.primary_count;
        output->valid_index_count = candidate.valid_count;
        output->existing_rank_auto_change_authorized = UINT8_C(0);
        output->customer_pose_emission_authorized = UINT8_C(0);
        output->production_claim_authorized = UINT8_C(0);
        return BG_STATUS_OK;
    });
}
