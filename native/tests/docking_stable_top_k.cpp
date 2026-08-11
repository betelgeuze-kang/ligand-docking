#include "betelgeuze/engine.h"

#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <type_traits>

namespace {

constexpr std::size_t kSlots = BG_DOCKING_FIXED64_CANDIDATE_COUNT;

struct Fixture final {
    std::array<bg_docking_scorer_v1_row_v1, kSlots> scorer_rows{};
    std::array<bg_docking_pose_validity_row_v1, kSlots> validity_rows{};
    std::array<uint8_t, kSlots * 32> coordinate_sha256{};

    Fixture() {
        for (std::size_t slot = 0; slot < kSlots; ++slot) {
            scorer_rows[slot].slot_index = static_cast<uint32_t>(slot);
            scorer_rows[slot].status =
                BG_DOCKING_SCORER_V1_ROW_TYPED_FAILURE;
            scorer_rows[slot].failure_code =
                BG_DOCKING_SCORER_V1_FAILURE_UPSTREAM_NOT_ADMITTED;
            validity_rows[slot].slot_index = static_cast<uint32_t>(slot);
            validity_rows[slot].status =
                BG_DOCKING_POSE_VALIDITY_ROW_UPSTREAM_SCORER_FAILURE;
            validity_rows[slot].failure_code =
                BG_DOCKING_POSE_VALIDITY_FAILURE_UPSTREAM_SCORER;
            validity_rows[slot].upstream_scorer_failure_code =
                BG_DOCKING_SCORER_V1_FAILURE_UPSTREAM_NOT_ADMITTED;
        }
        const std::array<double, 6> scores = {
            2.0,
            -1.0,
            -1.0,
            -0.0,
            1.0,
            0.5,
        };
        for (std::size_t slot = 0; slot < scores.size(); ++slot) {
            auto &scorer = scorer_rows[slot];
            scorer.status = BG_DOCKING_SCORER_V1_ROW_SCORED;
            scorer.failure_code = BG_DOCKING_SCORER_V1_FAILURE_NONE;
            scorer.weighted_terms[0] = scores[slot];
            scorer.total_score = scores[slot];
            coordinate_sha256[slot * 32] =
                static_cast<uint8_t>(slot + 1);

            auto &validity = validity_rows[slot];
            validity.status = BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED;
            validity.failure_code =
                BG_DOCKING_POSE_VALIDITY_FAILURE_NONE;
            validity.upstream_scorer_failure_code =
                BG_DOCKING_SCORER_V1_FAILURE_NONE;
            validity.passed_check_mask =
                BG_DOCKING_POSE_VALIDITY_CHECK_ALL;
            validity.blocker_mask = 0;
            validity.atom_count = 4;
        }
        validity_rows[4].passed_check_mask =
            BG_DOCKING_POSE_VALIDITY_CHECK_ALL ^
            BG_DOCKING_POSE_VALIDITY_CHECK_DECLARED_POCKET;
        validity_rows[4].blocker_mask =
            BG_DOCKING_POSE_VALIDITY_CHECK_DECLARED_POCKET;
        validity_rows[5] = bg_docking_pose_validity_row_v1{};
        validity_rows[5].slot_index = 5;
        validity_rows[5].status =
            BG_DOCKING_POSE_VALIDITY_ROW_TYPED_FAILURE;
        validity_rows[5].failure_code =
            BG_DOCKING_POSE_VALIDITY_FAILURE_INVALID_CANDIDATE_COORDINATES;
        validity_rows[5].observed_count = 4;
    }

    bg_docking_stable_top_k_input_v1 input() const {
        bg_docking_stable_top_k_input_v1 value{};
        assert(bg_docking_stable_top_k_input_v1_init(&value) == BG_STATUS_OK);
        value.scorer_rows = scorer_rows.data();
        value.validity_rows = validity_rows.data();
        value.coordinate_sha256 = coordinate_sha256.data();
        return value;
    }
};

struct RankingOutput final {
    std::array<bg_docking_stable_top_k_row_v1, kSlots> rows{};
    std::array<uint32_t, kSlots> primary{};
    std::array<uint32_t, kSlots> valid{};
    uint64_t row_count = 0;
    uint64_t primary_count = 0;
    uint64_t valid_count = 0;
    uint8_t existing_rank_auto_change_authorized = UINT8_C(1);
    uint8_t customer_pose_emission_authorized = UINT8_C(1);
    uint8_t production_claim_authorized = UINT8_C(1);
};

bg_context *create_context(bg_backend backend) {
    bg_context_options options{};
    assert(bg_context_options_init(&options) == BG_STATUS_OK);
    options.backend = backend;
    bg_context *context = nullptr;
    assert(bg_context_create(&options, &context) == BG_STATUS_OK);
    assert(context != nullptr);
    return context;
}

bg_docking_stable_top_k_v1 *create_ranker(bg_context *context) {
    bg_docking_stable_top_k_v1 *ranker = nullptr;
    assert(
        bg_docking_stable_top_k_v1_create(context, &ranker) ==
        BG_STATUS_OK);
    assert(ranker != nullptr);
    return ranker;
}

RankingOutput rank(
    bg_context *context,
    bg_docking_stable_top_k_v1 *ranker,
    const bg_docking_stable_top_k_input_v1 &input) {
    RankingOutput result{};
    bg_docking_stable_top_k_output_v1 output{};
    assert(bg_docking_stable_top_k_output_v1_init(&output) == BG_STATUS_OK);
    output.row_capacity = kSlots;
    output.primary_index_capacity = kSlots;
    output.valid_index_capacity = kSlots;
    output.rows = result.rows.data();
    output.primary_slot_indices = result.primary.data();
    output.valid_slot_indices = result.valid.data();
    output.existing_rank_auto_change_authorized = UINT8_C(1);
    output.customer_pose_emission_authorized = UINT8_C(1);
    output.production_claim_authorized = UINT8_C(1);
    assert(
        bg_docking_stable_top_k_v1_rank_fixed64(
            context, ranker, &input, &output) == BG_STATUS_OK);
    result.row_count = output.row_count;
    result.primary_count = output.primary_index_count;
    result.valid_count = output.valid_index_count;
    result.existing_rank_auto_change_authorized =
        output.existing_rank_auto_change_authorized;
    result.customer_pose_emission_authorized =
        output.customer_pose_emission_authorized;
    result.production_claim_authorized =
        output.production_claim_authorized;
    return result;
}

void assert_output_equal(
    const RankingOutput &left,
    const RankingOutput &right) {
    assert(std::memcmp(left.rows.data(), right.rows.data(), sizeof(left.rows)) == 0);
    assert(
        std::memcmp(
            left.primary.data(), right.primary.data(), sizeof(left.primary)) ==
        0);
    assert(std::memcmp(left.valid.data(), right.valid.data(), sizeof(left.valid)) == 0);
    assert(left.row_count == right.row_count);
    assert(left.primary_count == right.primary_count);
    assert(left.valid_count == right.valid_count);
    assert(
        left.existing_rank_auto_change_authorized ==
        right.existing_rank_auto_change_authorized);
    assert(
        left.customer_pose_emission_authorized ==
        right.customer_pose_emission_authorized);
    assert(
        left.production_claim_authorized ==
        right.production_claim_authorized);
}

void test_cpu_parity_stable_order_and_authority_false() {
    const Fixture fixture;
    const auto input = fixture.input();
    bg_context *cpp_context = create_context(BG_BACKEND_CPP_CPU_REFERENCE);
    bg_context *rust_context = create_context(BG_BACKEND_RUST_CPU);
    bg_docking_stable_top_k_v1 *cpp_ranker = create_ranker(cpp_context);
    bg_docking_stable_top_k_v1 *rust_ranker = create_ranker(rust_context);

    bg_backend backend = BG_BACKEND_AUTO;
    assert(
        bg_docking_stable_top_k_v1_get_backend(cpp_ranker, &backend) ==
        BG_STATUS_OK);
    assert(backend == BG_BACKEND_CPP_CPU_REFERENCE);
    assert(
        bg_docking_stable_top_k_v1_get_backend(rust_ranker, &backend) ==
        BG_STATUS_OK);
    assert(backend == BG_BACKEND_RUST_CPU);

    const RankingOutput cpp = rank(cpp_context, cpp_ranker, input);
    const RankingOutput rust = rank(rust_context, rust_ranker, input);
    const RankingOutput repeat = rank(rust_context, rust_ranker, input);
    assert_output_equal(cpp, rust);
    assert_output_equal(rust, repeat);
    assert(cpp.row_count == kSlots);
    assert(cpp.primary_count == 6);
    assert(cpp.valid_count == 4);
    const std::array<uint32_t, 6> expected_primary = {1, 2, 3, 5, 4, 0};
    const std::array<uint32_t, 4> expected_valid = {1, 2, 3, 0};
    assert(std::equal(expected_primary.begin(), expected_primary.end(), cpp.primary.begin()));
    assert(std::equal(expected_valid.begin(), expected_valid.end(), cpp.valid.begin()));
    assert(cpp.rows[1].stable_rank == 1);
    assert(cpp.rows[2].stable_rank == 2);
    assert(cpp.rows[3].total_score == 0.0);
    assert(!std::signbit(cpp.rows[3].total_score));
    assert(cpp.rows[4].rank_eligible == UINT8_C(1));
    assert(cpp.rows[4].valid_rank_eligible == UINT8_C(0));
    assert(cpp.rows[5].stable_valid_rank == 0);
    assert(cpp.rows[6].rank_eligible == UINT8_C(0));
    assert(cpp.existing_rank_auto_change_authorized == UINT8_C(0));
    assert(cpp.customer_pose_emission_authorized == UINT8_C(0));
    assert(cpp.production_claim_authorized == UINT8_C(0));

    bg_docking_stable_top_k_v1_destroy(cpp_ranker);
    bg_docking_stable_top_k_v1_destroy(rust_ranker);
    bg_context_destroy(cpp_context);
    bg_context_destroy(rust_context);
}

void test_invalid_binding_is_transactional_and_cross_wiring_fails() {
    Fixture fixture;
    auto input = fixture.input();
    bg_context *cpp_context = create_context(BG_BACKEND_CPP_CPU_REFERENCE);
    bg_context *rust_context = create_context(BG_BACKEND_RUST_CPU);
    bg_docking_stable_top_k_v1 *cpp_ranker = create_ranker(cpp_context);
    bg_docking_stable_top_k_v1 *rust_ranker = create_ranker(rust_context);

    std::array<bg_docking_stable_top_k_row_v1, kSlots> rows{};
    std::array<uint32_t, kSlots> primary{};
    std::array<uint32_t, kSlots> valid{};
    std::memset(rows.data(), 0x5a, sizeof(rows));
    primary.fill(UINT32_C(0x5a5a5a5a));
    valid.fill(UINT32_C(0x6b6b6b6b));
    const auto rows_before = rows;
    const auto primary_before = primary;
    const auto valid_before = valid;
    bg_docking_stable_top_k_output_v1 output{};
    assert(bg_docking_stable_top_k_output_v1_init(&output) == BG_STATUS_OK);
    output.row_capacity = kSlots;
    output.row_count = 17;
    output.primary_index_capacity = kSlots;
    output.primary_index_count = 19;
    output.valid_index_capacity = kSlots;
    output.valid_index_count = 23;
    output.rows = rows.data();
    output.primary_slot_indices = primary.data();
    output.valid_slot_indices = valid.data();
    fixture.coordinate_sha256[0] = 0;
    input.coordinate_sha256 = fixture.coordinate_sha256.data();
    assert(
        bg_docking_stable_top_k_v1_rank_fixed64(
            rust_context, rust_ranker, &input, &output) ==
        BG_STATUS_INVALID_ARGUMENT);
    assert(output.row_count == 17);
    assert(output.primary_index_count == 19);
    assert(output.valid_index_count == 23);
    assert(std::memcmp(rows.data(), rows_before.data(), sizeof(rows)) == 0);
    assert(primary == primary_before);
    assert(valid == valid_before);

    const Fixture valid_fixture;
    const auto valid_input = valid_fixture.input();
    assert(
        bg_docking_stable_top_k_v1_rank_fixed64(
            cpp_context, rust_ranker, &valid_input, &output) ==
        BG_STATUS_INVALID_ARGUMENT);

    bg_docking_stable_top_k_v1_destroy(cpp_ranker);
    bg_docking_stable_top_k_v1_destroy(rust_ranker);
    bg_context_destroy(cpp_context);
    bg_context_destroy(rust_context);
}

void test_hip_parity_when_device_is_available(bg_backend backend) {
    uint8_t available = UINT8_C(0);
    assert(bg_backend_is_available(backend, 0, &available) == BG_STATUS_OK);
    if (available == UINT8_C(0)) {
        return;
    }
    const Fixture fixture;
    const auto input = fixture.input();
    bg_context *rust_context = create_context(BG_BACKEND_RUST_CPU);
    bg_context *hip_context = create_context(backend);
    bg_docking_stable_top_k_v1 *rust_ranker = create_ranker(rust_context);
    bg_docking_stable_top_k_v1 *hip_ranker = create_ranker(hip_context);
    const RankingOutput rust = rank(rust_context, rust_ranker, input);
    const RankingOutput hip = rank(hip_context, hip_ranker, input);
    const RankingOutput repeat = rank(hip_context, hip_ranker, input);
    assert_output_equal(rust, hip);
    assert_output_equal(hip, repeat);
    bg_docking_stable_top_k_v1_destroy(rust_ranker);
    bg_docking_stable_top_k_v1_destroy(hip_ranker);
    bg_context_destroy(rust_context);
    bg_context_destroy(hip_context);
}

}  // namespace

int main() {
    static_assert(
        std::is_standard_layout_v<bg_docking_stable_top_k_input_v1>);
    static_assert(
        std::is_standard_layout_v<bg_docking_stable_top_k_row_v1>);
    static_assert(
        std::is_standard_layout_v<bg_docking_stable_top_k_output_v1>);
    test_cpu_parity_stable_order_and_authority_false();
    test_invalid_binding_is_transactional_and_cross_wiring_fails();
    test_hip_parity_when_device_is_available(BG_BACKEND_HIP_SAFE);
    test_hip_parity_when_device_is_available(BG_BACKEND_HIP_FAST);
    return 0;
}
