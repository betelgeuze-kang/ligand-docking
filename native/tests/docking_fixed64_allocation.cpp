#include "betelgeuze/engine.h"

#include <algorithm>
#include <array>
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <type_traits>

namespace {

constexpr std::size_t kSlots = BG_DOCKING_FIXED64_CANDIDATE_COUNT;
constexpr std::array<uint32_t, 4> kRetainedIndices = {36, 45, 54, 63};

template <std::size_t Count>
void fill_digest(uint8_t (&digest)[Count], uint8_t marker) {
    static_assert(Count == 32);
    std::fill(std::begin(digest), std::end(digest), marker);
}

void fill_source(
    bg_docking_fixed64_source_evidence_v1 *source,
    uint8_t marker) {
    fill_digest(source->receipt_sha256, marker);
    fill_digest(
        source->proposal_sha256,
        static_cast<uint8_t>(marker + UINT8_C(64)));
    fill_digest(
        source->coordinate_sha256,
        static_cast<uint8_t>(marker + UINT8_C(128)));
}

struct Fixture final {
    std::array<bg_docking_fixed64_atomic_feature_evidence_v1, 12>
        atomic_features{};
    std::array<bg_docking_fixed64_indexed_source_evidence_v1, 24>
        v7_sources{};
    std::array<bg_docking_fixed64_conformer_source_evidence_v1, 7>
        conformer_sources{};
    std::array<bg_docking_fixed64_indexed_source_evidence_v1, 4>
        retained_sources{};

    Fixture() {
        for (std::size_t index = 0; index < atomic_features.size(); ++index) {
            atomic_features[index].kind =
                static_cast<bg_docking_fixed64_feature_kind>(index);
            fill_digest(
                atomic_features[index].receipt_sha256,
                static_cast<uint8_t>(UINT8_C(80) + index));
        }
        for (std::size_t index = 0; index < v7_sources.size(); ++index) {
            v7_sources[index].source_index = static_cast<uint32_t>(index);
            fill_source(
                &v7_sources[index].source,
                static_cast<uint8_t>(UINT8_C(1) + index));
        }
        for (std::size_t index = 0; index < conformer_sources.size(); ++index) {
            const auto rank = static_cast<uint8_t>(index + 2U);
            conformer_sources[index].rank = rank;
            fill_source(
                &conformer_sources[index].source,
                static_cast<uint8_t>(UINT8_C(32) + rank));
        }
        for (std::size_t index = 0; index < retained_sources.size(); ++index) {
            retained_sources[index].source_index = kRetainedIndices[index];
            fill_source(
                &retained_sources[index].source,
                static_cast<uint8_t>(UINT8_C(48) + index));
        }
    }

    bg_docking_fixed64_allocation_input_v1 input() const {
        bg_docking_fixed64_allocation_input_v1 value{};
        assert(
            bg_docking_fixed64_allocation_input_v1_init(&value) ==
            BG_STATUS_OK);
        fill_digest(
            value.exact_v11_source.source_receipt_sha256, UINT8_C(240));
        fill_digest(value.exact_v11_source.proposal_sha256, UINT8_C(241));
        fill_digest(
            value.exact_v11_source.ligand_coordinate_sha256, UINT8_C(242));
        fill_digest(
            value.exact_v11_source.receptor_coordinate_sha256, UINT8_C(243));
        fill_digest(
            value.exact_v11_source.prepared_ligand_topology_sha256,
            UINT8_C(244));
        fill_digest(
            value.exact_v11_source.prepared_receptor_topology_sha256,
            UINT8_C(245));
        fill_digest(
            value.exact_v11_source.ligand_vdw_radii_sha256, UINT8_C(246));
        fill_digest(
            value.exact_v11_source.ligand_heavy_atom_mask_sha256,
            UINT8_C(247));
        fill_digest(
            value.exact_v11_source.receptor_vdw_radii_sha256,
            UINT8_C(248));
        value.atomic_feature_count = atomic_features.size();
        value.atomic_features = atomic_features.data();
        value.v7_control_source_count = v7_sources.size();
        value.v7_control_sources = v7_sources.data();
        value.conformer_source_count = conformer_sources.size();
        value.conformer_sources = conformer_sources.data();
        value.retained_source_count = retained_sources.size();
        value.retained_sources = retained_sources.data();
        return value;
    }
};

struct Evaluation final {
    std::array<bg_docking_fixed64_allocation_row_v1, kSlots> rows{};
    bg_docking_fixed64_allocation_output_v1 output{};
};

Evaluation evaluate(const bg_docking_fixed64_allocation_input_v1 &input) {
    Evaluation value{};
    assert(
        bg_docking_fixed64_allocation_output_v1_init(&value.output) ==
        BG_STATUS_OK);
    value.output.row_capacity = value.rows.size();
    value.output.rows = value.rows.data();
    assert(
        bg_docking_fixed64_allocation_v1_build(&input, &value.output) ==
        BG_STATUS_OK);
    return value;
}

bool digest_present(const uint8_t (&digest)[32]) {
    return std::any_of(
        std::begin(digest), std::end(digest), [](uint8_t value) {
            return value != UINT8_C(0);
        });
}

void assert_authority_false(
    const bg_docking_fixed64_allocation_output_v1 &output) {
    assert(output.result_dependent_allocation == 0);
    assert(output.molecular_execution_authorized == 0);
    assert(output.reservation_authorized == 0);
    assert(output.benchmark_execution_authorized == 0);
    assert(output.existing_rank_auto_change_authorized == 0);
    assert(output.customer_pose_emission_authorized == 0);
    assert(output.production_claim_authorized == 0);
}

void test_complete_inventory_and_repeat_stability() {
    const Fixture fixture;
    const auto input = fixture.input();
    const Evaluation first = evaluate(input);
    const Evaluation repeated = evaluate(input);

    assert(first.output.row_count == kSlots);
    assert(first.output.ready_count == kSlots);
    assert(first.output.typed_failure_count == 0);
    assert(digest_present(first.output.inventory_sha256));
    assert(digest_present(first.output.allocation_receipt_sha256));
    assert_authority_false(first.output);
    assert(
        std::memcmp(
            first.rows.data(),
            repeated.rows.data(),
            sizeof(first.rows)) == 0);
    assert(
        std::memcmp(
            first.output.inventory_sha256,
            repeated.output.inventory_sha256,
            32) == 0);
    assert(
        std::memcmp(
            first.output.allocation_receipt_sha256,
            repeated.output.allocation_receipt_sha256,
            32) == 0);

    constexpr std::array<std::size_t, 10> expected_lane_counts = {
        8, 16, 12, 8, 4, 4, 4, 2, 2, 4};
    std::array<std::size_t, 10> observed_lane_counts{};
    for (std::size_t slot = 0; slot < first.rows.size(); ++slot) {
        const auto &row = first.rows[slot];
        assert(row.slot_index == slot);
        assert(row.status == BG_DOCKING_FIXED64_ALLOCATION_ROW_READY);
        assert(row.generation_eligible == 1);
        assert(row.fallback_allowed == 0);
        assert(row.multi_anchor_allowed == 0);
        assert(row.result_dependent_allocation == 0);
        assert(row.denominator_preserved == 1);
        assert(row.molecular_execution_authorized == 0);
        assert(row.reservation_authorized == 0);
        assert(row.benchmark_execution_authorized == 0);
        assert(digest_present(row.generation_parent_receipt_sha256));
        assert(digest_present(row.generation_parent_proposal_sha256));
        assert(digest_present(row.generation_parent_coordinate_sha256));
        assert(digest_present(row.slot_receipt_sha256));
        assert(row.lane >= 0);
        const auto lane = static_cast<std::size_t>(row.lane);
        assert(lane < observed_lane_counts.size());
        ++observed_lane_counts[lane];
    }
    assert(observed_lane_counts == expected_lane_counts);

    for (std::size_t slot = 0; slot < 24; ++slot) {
        const auto &row = first.rows[slot];
        assert(row.v7_control_source_index == static_cast<int32_t>(slot));
        assert(
            row.generation_parent_role ==
            BG_DOCKING_FIXED64_PARENT_EXACT_PASSTHROUGH);
        assert(row.selected_source_receipt_count == 1);
        assert(std::memcmp(
                   row.generation_parent_receipt_sha256,
                   row.selected_source_receipt_sha256[0],
                   32) == 0);
    }
    for (std::size_t slot = 24; slot < 36; ++slot) {
        const auto &row = first.rows[slot];
        assert(row.so3_sequence_index == static_cast<int32_t>(slot - 24));
        assert(
            row.generation_parent_role ==
            BG_DOCKING_FIXED64_PARENT_GENERATOR_INPUT);
        assert(row.selected_source_receipt_count == 0);
        assert(std::memcmp(
                   row.generation_parent_receipt_sha256,
                   input.exact_v11_source.source_receipt_sha256,
                   32) == 0);
    }
    constexpr std::array<int32_t, 8> conformer_ranks = {2, 3, 4, 5, 6, 7, 8, 2};
    for (std::size_t offset = 0; offset < conformer_ranks.size(); ++offset) {
        const auto &row = first.rows[36 + offset];
        assert(row.so3_sequence_index == static_cast<int32_t>(offset));
        assert(row.true_conformer_rank == conformer_ranks[offset]);
        assert(row.selected_source_receipt_count == 1);
    }
    for (std::size_t slot = 44; slot < 60; ++slot) {
        assert(first.rows[slot].declared_anchor_kind != BG_DOCKING_FIXED64_ANCHOR_NONE);
        assert(first.rows[slot].selected_source_receipt_count == 2);
    }
    for (std::size_t offset = 0; offset < kRetainedIndices.size(); ++offset) {
        const auto &row = first.rows[60 + offset];
        assert(
            row.retained_source_index ==
            static_cast<int32_t>(kRetainedIndices[offset]));
        assert(
            row.generation_parent_role ==
            BG_DOCKING_FIXED64_PARENT_EXACT_PASSTHROUGH);
    }
}

void test_missing_feature_preserves_exact_denominator() {
    const Fixture fixture;
    auto input = fixture.input();
    std::array<bg_docking_fixed64_atomic_feature_evidence_v1, 11>
        without_receptor_acceptor{};
    std::size_t output_index = 0;
    for (const auto &feature : fixture.atomic_features) {
        if (feature.kind == BG_DOCKING_FIXED64_FEATURE_RECEPTOR_ACCEPTOR) {
            continue;
        }
        without_receptor_acceptor[output_index++] = feature;
    }
    assert(output_index == without_receptor_acceptor.size());
    input.atomic_feature_count = without_receptor_acceptor.size();
    input.atomic_features = without_receptor_acceptor.data();

    const Evaluation value = evaluate(input);
    assert(value.output.row_count == 64);
    assert(value.output.ready_count == 60);
    assert(value.output.typed_failure_count == 4);
    assert_authority_false(value.output);
    for (std::size_t slot = 0; slot < value.rows.size(); ++slot) {
        const bool expected_failure = slot >= 44 && slot <= 47;
        assert(
            value.rows[slot].status ==
            (expected_failure
                 ? BG_DOCKING_FIXED64_ALLOCATION_ROW_TYPED_FAILURE
                 : BG_DOCKING_FIXED64_ALLOCATION_ROW_READY));
        assert(value.rows[slot].denominator_preserved == 1);
        if (expected_failure) {
            assert(value.rows[slot].generation_eligible == 0);
            assert(value.rows[slot].missing_feature_count == 1);
            assert(
                value.rows[slot].missing_features[0].kind ==
                BG_DOCKING_FIXED64_MISSING_RECEPTOR_ACCEPTOR);
            assert(value.rows[slot].selected_source_receipt_count == 1);
        }
    }
}

template <typename Type>
std::array<unsigned char, sizeof(Type)> object_bytes(const Type &value) {
    static_assert(std::is_trivially_copyable<Type>::value);
    std::array<unsigned char, sizeof(Type)> result{};
    std::memcpy(result.data(), &value, result.size());
    return result;
}

void test_invalid_inputs_and_aliases_are_transactional() {
    const Fixture fixture;
    auto input = fixture.input();
    Evaluation storage{};
    assert(
        bg_docking_fixed64_allocation_output_v1_init(&storage.output) ==
        BG_STATUS_OK);
    storage.output.row_capacity = storage.rows.size();
    storage.output.rows = storage.rows.data();
    std::memset(storage.rows.data(), 0xA5, sizeof(storage.rows));
    const auto rows_before = object_bytes(storage.rows);
    const auto output_before = object_bytes(storage.output);

    auto unsorted = fixture.atomic_features;
    std::swap(unsorted[0], unsorted[1]);
    input.atomic_features = unsorted.data();
    assert(
        bg_docking_fixed64_allocation_v1_build(&input, &storage.output) ==
        BG_STATUS_INVALID_ARGUMENT);
    assert(object_bytes(storage.rows) == rows_before);
    assert(object_bytes(storage.output) == output_before);

    input = fixture.input();
    storage.output.row_capacity = 63;
    const auto undersized_before = object_bytes(storage.output);
    assert(
        bg_docking_fixed64_allocation_v1_build(&input, &storage.output) ==
        BG_STATUS_BUFFER_TOO_SMALL);
    assert(object_bytes(storage.rows) == rows_before);
    assert(object_bytes(storage.output) == undersized_before);

    storage.output.row_capacity = 64;
    storage.output.rows = reinterpret_cast<
        bg_docking_fixed64_allocation_row_v1 *>(
        const_cast<bg_docking_fixed64_atomic_feature_evidence_v1 *>(
            input.atomic_features));
    const auto alias_before = object_bytes(storage.output);
    assert(
        bg_docking_fixed64_allocation_v1_build(&input, &storage.output) ==
        BG_STATUS_INVALID_ARGUMENT);
    assert(object_bytes(storage.output) == alias_before);

    assert(
        bg_docking_fixed64_allocation_output_v1_init(&storage.output) ==
        BG_STATUS_OK);
    storage.output.row_capacity = 64;
    storage.output.rows = reinterpret_cast<
        bg_docking_fixed64_allocation_row_v1 *>(&storage.output);
    const auto descriptor_alias_before = object_bytes(storage.output);
    assert(
        bg_docking_fixed64_allocation_v1_build(&input, &storage.output) ==
        BG_STATUS_INVALID_ARGUMENT);
    assert(object_bytes(storage.output) == descriptor_alias_before);

    input = fixture.input();
    std::fill(
        std::begin(input.exact_v11_source.source_receipt_sha256),
        std::end(input.exact_v11_source.source_receipt_sha256),
        UINT8_C(0));
    assert(
        bg_docking_fixed64_allocation_output_v1_init(&storage.output) ==
        BG_STATUS_OK);
    storage.output.row_capacity = storage.rows.size();
    storage.output.rows = storage.rows.data();
    std::memset(storage.rows.data(), 0x5A, sizeof(storage.rows));
    const auto zero_identity_rows_before = object_bytes(storage.rows);
    const auto zero_identity_output_before = object_bytes(storage.output);
    assert(
        bg_docking_fixed64_allocation_v1_build(&input, &storage.output) ==
        BG_STATUS_INVALID_ARGUMENT);
    assert(object_bytes(storage.rows) == zero_identity_rows_before);
    assert(object_bytes(storage.output) == zero_identity_output_before);

    input = fixture.input();
    auto zero_source = fixture.v7_sources;
    std::fill(
        std::begin(zero_source[0].source.coordinate_sha256),
        std::end(zero_source[0].source.coordinate_sha256),
        UINT8_C(0));
    input.v7_control_sources = zero_source.data();
    assert(
        bg_docking_fixed64_allocation_v1_build(&input, &storage.output) ==
        BG_STATUS_INVALID_ARGUMENT);
    assert(object_bytes(storage.rows) == zero_identity_rows_before);
    assert(object_bytes(storage.output) == zero_identity_output_before);
}

}  // namespace

int main() {
    test_complete_inventory_and_repeat_stability();
    test_missing_feature_preserves_exact_denominator();
    test_invalid_inputs_and_aliases_are_transactional();
    return 0;
}
