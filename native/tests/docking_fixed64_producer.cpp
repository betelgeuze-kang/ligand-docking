#include "betelgeuze/engine.h"

#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <string_view>
#include <tuple>
#include <type_traits>
#include <utility>
#include <vector>

namespace {

constexpr std::size_t kAtoms = 4;
constexpr std::size_t kSlots = BG_DOCKING_FIXED64_CANDIDATE_COUNT;
constexpr std::size_t kCoordinates = kAtoms * kSlots;
constexpr std::size_t kFeatureCount = BG_DOCKING_FIXED64_FEATURE_KIND_COUNT;
constexpr std::array<uint32_t, 4> kRetainedIndices = {36, 45, 54, 63};
constexpr std::array<const char *, kFeatureCount> kFeatureReceipts = {
    "a4a9abe5385a5d950cc97fb3d6d17786e89f701fbaf0f536c7625cdb324a196c",
    "c5c7e1de6b795c4bbb48d3dd9e16d542af74992ae8b6a6c00c6469e2bc2c0d71",
    "91f058ffdfe22f1ac9109dedcf4613bd31d5b75cd7c935cb470e77360de5ac34",
    "6a141b8dff96c9203e272a8323908794e3326a653f384b44353cf4ee00b5ebca",
    "e2d39cb1d8ce38251fb647d013ffbe950e0380b0b91c6b8573c7b8ac0feda250",
    "7355e212bc8b602ebc010672ed24b28c6b0522f774403d0869f8b2054a48ffc7",
    "ff451a99520fa7861bb09059c6cb4d68b904ad894b9ec48c956d4fbabbaa6cfd",
    "bbf3b947353fccbb9630ce0fb1c052d0f708d40da73aee7fb6425a73c53b8836",
    "4e575a9d21486a700c15a4447df1c5aad6d7888ef31eabe9996b703477bc2785",
    "b21dc24325877d05045de061985c49b61859bd5164f70923e55f0bcba9a2abc9",
    "38dca0ef30fec0feabb58c167206e90e9b3f99f01d451850f38c2d89954c27f7",
    "9f440529e7ad7c91e047dabffde0f0a8ff58896ac37b9350584328353f37a766",
};

uint8_t hex_digit(char value) {
    if (value >= '0' && value <= '9') return static_cast<uint8_t>(value - '0');
    if (value >= 'a' && value <= 'f') {
        return static_cast<uint8_t>(10 + value - 'a');
    }
    assert(false);
    return 0;
}

void parse_digest(const char *hex, uint8_t (&output)[32]) {
    const std::string_view value(hex);
    assert(value.size() == 64);
    for (std::size_t index = 0; index < 32; ++index) {
        output[index] = static_cast<uint8_t>(
            (hex_digit(value[index * 2]) << 4U) |
            hex_digit(value[index * 2 + 1]));
    }
}

template <std::size_t Count>
void fill_digest(uint8_t (&digest)[Count], uint8_t marker) {
    static_assert(Count == 32);
    std::fill(std::begin(digest), std::end(digest), marker);
}

template <typename Type>
std::array<unsigned char, sizeof(Type)> object_bytes(const Type &value) {
    static_assert(std::is_trivially_copyable<Type>::value);
    std::array<unsigned char, sizeof(Type)> result{};
    std::memcpy(result.data(), &value, result.size());
    return result;
}

bool digest_present(const uint8_t (&digest)[32]) {
    return std::any_of(
        std::begin(digest), std::end(digest),
        [](uint8_t value) { return value != UINT8_C(0); });
}

void fill_source_evidence(
    bg_docking_fixed64_source_evidence_v1 *source,
    uint8_t marker) {
    fill_digest(source->receipt_sha256, marker);
    fill_digest(
        source->proposal_sha256,
        static_cast<uint8_t>(marker + UINT8_C(64)));
    parse_digest(
        "42bd9421b68e2e80a1b4d6b0e52173f6769feb8422b897d1b0131a124c35610a",
        source->coordinate_sha256);
}

struct Fixture final {
    std::array<double, kAtoms> source_x = {0.0, 1.0, 0.0, 0.0};
    std::array<double, kAtoms> source_y = {0.0, 0.0, 1.0, 0.0};
    std::array<double, kAtoms> source_z = {0.0, 0.0, 0.0, 1.5};
    std::array<double, kAtoms> receptor_x = {4.0, 3.5, 4.0, 4.0};
    std::array<double, kAtoms> receptor_y = {0.0, 0.0, 1.0, 0.0};
    std::array<double, kAtoms> receptor_z = {0.0, 0.0, 0.0, 1.25};
    std::array<double, kAtoms> ligand_radii = {1.5, 1.5, 1.5, 1.5};
    std::array<double, kAtoms> receptor_radii = {1.5, 1.5, 1.5, 1.5};
    std::array<uint8_t, kAtoms> heavy_mask = {1, 1, 1, 1};
    std::array<bg_docking_fixed64_atomic_feature_evidence_v1, kFeatureCount>
        atomic_features{};
    std::array<bg_docking_fixed64_feature_geometry_row_v1, kFeatureCount>
        feature_rows{};
    std::vector<uint64_t> feature_indices;
    std::array<bg_docking_fixed64_indexed_source_evidence_v1, 24>
        v7_evidence{};
    std::array<bg_docking_fixed64_conformer_source_evidence_v1, 7>
        conformer_evidence{};
    std::array<bg_docking_fixed64_indexed_source_evidence_v1, 4>
        retained_evidence{};
    std::array<bg_docking_fixed64_indexed_coordinate_source_v1, 24>
        v7_sources{};
    std::array<bg_docking_fixed64_conformer_coordinate_source_v1, 7>
        conformer_sources{};
    std::array<bg_docking_fixed64_indexed_coordinate_source_v1, 4>
        retained_sources{};
    bg_docking_fixed64_coordinate_source_v1 exact_source{};
    bg_docking_fixed64_allocation_input_v1 allocation{};

    Fixture() {
        assert(bg_docking_fixed64_allocation_input_v1_init(&allocation) ==
               BG_STATUS_OK);
        fill_digest(allocation.exact_v11_source.source_receipt_sha256, 0x10);
        fill_digest(allocation.exact_v11_source.proposal_sha256, 0x11);
        parse_digest(
            "42bd9421b68e2e80a1b4d6b0e52173f6769feb8422b897d1b0131a124c35610a",
            allocation.exact_v11_source.ligand_coordinate_sha256);
        parse_digest(
            "eec85cfe7d1e2cb444ed309e7b1861819ec8c6fd9391baa71c26db323fdc847c",
            allocation.exact_v11_source.receptor_coordinate_sha256);
        fill_digest(
            allocation.exact_v11_source.prepared_ligand_topology_sha256,
            0x12);
        fill_digest(
            allocation.exact_v11_source.prepared_receptor_topology_sha256,
            0x13);
        parse_digest(
            "142a64fce99277370fc239fbbb59e85aee8c8c9472a6eb394231b8bff31981f6",
            allocation.exact_v11_source.ligand_vdw_radii_sha256);
        parse_digest(
            "47db80b60571a69d0c98dca872f4c6ab561bb7ce179e4300d440639b234015dc",
            allocation.exact_v11_source.ligand_heavy_atom_mask_sha256);
        parse_digest(
            "142a64fce99277370fc239fbbb59e85aee8c8c9472a6eb394231b8bff31981f6",
            allocation.exact_v11_source.receptor_vdw_radii_sha256);
        std::copy_n(
            allocation.exact_v11_source.source_receipt_sha256, 32,
            exact_source.source.receipt_sha256);
        std::copy_n(
            allocation.exact_v11_source.proposal_sha256, 32,
            exact_source.source.proposal_sha256);
        std::copy_n(
            allocation.exact_v11_source.ligand_coordinate_sha256, 32,
            exact_source.source.coordinate_sha256);
        exact_source.ligand_atom_count = kAtoms;
        exact_source.x_angstrom = source_x.data();
        exact_source.y_angstrom = source_y.data();
        exact_source.z_angstrom = source_z.data();

        const std::array<std::vector<uint64_t>, kFeatureCount> indices = {
            std::vector<uint64_t>{0, 1}, std::vector<uint64_t>{2},
            std::vector<uint64_t>{0, 1}, std::vector<uint64_t>{2},
            std::vector<uint64_t>{1}, std::vector<uint64_t>{2},
            std::vector<uint64_t>{1}, std::vector<uint64_t>{2},
            std::vector<uint64_t>{0, 1, 2},
            std::vector<uint64_t>{0, 2, 3},
            std::vector<uint64_t>{0, 1, 2, 3},
            std::vector<uint64_t>{0, 1, 2, 3},
        };
        for (std::size_t index = 0; index < kFeatureCount; ++index) {
            auto &atomic = atomic_features[index];
            atomic.kind = static_cast<bg_docking_fixed64_feature_kind>(index);
            fill_digest(
                atomic.receipt_sha256,
                static_cast<uint8_t>(0x40U + index));
            auto &geometry = feature_rows[index];
            geometry.kind = atomic.kind;
            std::copy_n(
                atomic.receipt_sha256, 32,
                geometry.allocation_feature_receipt_sha256);
            geometry.atom_index_offset = feature_indices.size();
            geometry.atom_index_count = indices[index].size();
            feature_indices.insert(
                feature_indices.end(), indices[index].begin(),
                indices[index].end());
            parse_digest(
                kFeatureReceipts[index],
                geometry.feature_geometry_receipt_sha256);
        }
        for (std::size_t index = 0; index < v7_evidence.size(); ++index) {
            v7_evidence[index].source_index = static_cast<uint32_t>(index);
            fill_source_evidence(
                &v7_evidence[index].source,
                static_cast<uint8_t>(1U + index));
            v7_sources[index].source_index = static_cast<uint32_t>(index);
            assign_payload(v7_evidence[index].source, &v7_sources[index].payload);
        }
        for (std::size_t index = 0; index < conformer_evidence.size(); ++index) {
            const auto rank = static_cast<uint8_t>(index + 2U);
            conformer_evidence[index].rank = rank;
            fill_source_evidence(
                &conformer_evidence[index].source,
                static_cast<uint8_t>(32U + rank));
            conformer_sources[index].rank = rank;
            assign_payload(
                conformer_evidence[index].source,
                &conformer_sources[index].payload);
        }
        for (std::size_t index = 0; index < retained_evidence.size(); ++index) {
            retained_evidence[index].source_index = kRetainedIndices[index];
            fill_source_evidence(
                &retained_evidence[index].source,
                static_cast<uint8_t>(48U + index));
            retained_sources[index].source_index = kRetainedIndices[index];
            assign_payload(
                retained_evidence[index].source,
                &retained_sources[index].payload);
        }
        allocation.atomic_feature_count = atomic_features.size();
        allocation.atomic_features = atomic_features.data();
        allocation.v7_control_source_count = v7_evidence.size();
        allocation.v7_control_sources = v7_evidence.data();
        allocation.conformer_source_count = conformer_evidence.size();
        allocation.conformer_sources = conformer_evidence.data();
        allocation.retained_source_count = retained_evidence.size();
        allocation.retained_sources = retained_evidence.data();
    }

    void assign_payload(
        const bg_docking_fixed64_source_evidence_v1 &evidence,
        bg_docking_fixed64_coordinate_source_v1 *payload) {
        payload->source = evidence;
        payload->ligand_atom_count = kAtoms;
        payload->x_angstrom = source_x.data();
        payload->y_angstrom = source_y.data();
        payload->z_angstrom = source_z.data();
    }
};

bg_context *make_context(bg_backend backend) {
    uint8_t available = 0;
    assert(bg_backend_is_available(backend, 0, &available) == BG_STATUS_OK);
    if (available == 0) return nullptr;
    bg_context_options options{};
    assert(bg_context_options_init(&options) == BG_STATUS_OK);
    options.backend = backend;
    bg_context *context = nullptr;
    assert(bg_context_create(&options, &context) == BG_STATUS_OK);
    return context;
}

bg_docking_geometric_admission_v1 *make_admission(
    const Fixture &fixture,
    bg_context *context,
    std::array<double, 3> pocket_center = {0.0, 0.0, 0.0},
    uint64_t ligand_atom_count = kAtoms) {
    bg_docking_geometric_admission_context_soa_v1 descriptor{};
    assert(bg_docking_geometric_admission_context_soa_v1_init(&descriptor) ==
           BG_STATUS_OK);
    descriptor.unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
    descriptor.receptor_atom_count = kAtoms;
    descriptor.ligand_atom_count = ligand_atom_count;
    descriptor.receptor_x_angstrom = fixture.receptor_x.data();
    descriptor.receptor_y_angstrom = fixture.receptor_y.data();
    descriptor.receptor_z_angstrom = fixture.receptor_z.data();
    descriptor.receptor_vdw_radius_angstrom = fixture.receptor_radii.data();
    descriptor.ligand_vdw_radius_angstrom = fixture.ligand_radii.data();
    descriptor.ligand_heavy_atom_mask = fixture.heavy_mask.data();
    std::copy(
        pocket_center.begin(), pocket_center.end(),
        descriptor.pocket_center_angstrom);
    descriptor.pocket_radius_angstrom = 10.0;
    descriptor.hard_rejection_minimum_vdw_ratio = 0.55;
    descriptor.max_batch_exact_pair_evaluations = UINT64_C(16'777'216);
    fill_digest(descriptor.authority_input_receipt_sha256, 0x70);
    fill_digest(descriptor.receptor_system_sha256, 0x71);
    fill_digest(descriptor.ligand_system_sha256, 0x72);
    fill_digest(descriptor.backend_receipt_sha256, 0x73);
    bg_docking_geometric_admission_v1 *admission = nullptr;
    assert(bg_docking_geometric_admission_v1_create(
               context, &descriptor, &admission) == BG_STATUS_OK);
    return admission;
}

bg_docking_fixed64_producer_input_v1 make_input(const Fixture &fixture) {
    bg_docking_fixed64_producer_input_v1 input{};
    assert(bg_docking_fixed64_producer_input_v1_init(&input) == BG_STATUS_OK);
    input.allocation_input = &fixture.allocation;
    input.exact_v11_source = &fixture.exact_source;
    input.v7_control_source_count = fixture.v7_sources.size();
    input.v7_control_sources = fixture.v7_sources.data();
    input.conformer_source_count = fixture.conformer_sources.size();
    input.conformer_sources = fixture.conformer_sources.data();
    input.retained_source_count = fixture.retained_sources.size();
    input.retained_sources = fixture.retained_sources.data();
    input.feature_geometry_count = fixture.feature_rows.size();
    input.feature_geometry_rows = fixture.feature_rows.data();
    input.feature_atom_index_count = fixture.feature_indices.size();
    input.feature_atom_indices = fixture.feature_indices.data();
    parse_digest(
        "0f93ce2e442cdcdd01d8c6e0840f09c485a17b0169f66a341355797877981ea2",
        input.feature_geometry_inventory_sha256);
    input.pocket_normal[2] = 1.0;
    return input;
}

struct Batch final {
    std::array<bg_docking_fixed64_producer_row_v1, kSlots> rows{};
    std::array<double, kCoordinates> x{};
    std::array<double, kCoordinates> y{};
    std::array<double, kCoordinates> z{};
    bg_docking_fixed64_producer_output_v1 output{};
};

Batch produce(
    bg_context *context,
    bg_docking_geometric_admission_v1 *admission,
    const bg_docking_fixed64_producer_input_v1 &input) {
    Batch batch{};
    assert(bg_docking_fixed64_producer_output_v1_init(&batch.output) ==
           BG_STATUS_OK);
    batch.output.row_capacity = batch.rows.size();
    batch.output.coordinate_capacity = batch.x.size();
    batch.output.rows = batch.rows.data();
    batch.output.x_angstrom = batch.x.data();
    batch.output.y_angstrom = batch.y.data();
    batch.output.z_angstrom = batch.z.data();
    const bg_status status = bg_docking_fixed64_producer_v1_run(
        context, admission, &input, &batch.output);
    if (status != BG_STATUS_OK) {
        bg_backend backend = BG_BACKEND_AUTO;
        assert(bg_context_get_backend(context, &backend) == BG_STATUS_OK);
        std::fprintf(
            stderr, "producer backend %d failed: %s\n", backend,
            bg_last_error_message());
    }
    assert(status == BG_STATUS_OK);
    return batch;
}

void assert_authority_false(const bg_docking_fixed64_producer_output_v1 &out) {
    assert(out.result_dependent_input_consumed == 0);
    assert(out.fallback_allowed == 0);
    assert(out.multi_anchor_consumed == 0);
    assert(out.denominator_preserved == 1);
    assert(out.molecular_execution_authorized == 0);
    assert(out.reservation_authorized == 0);
    assert(out.benchmark_execution_authorized == 0);
    assert(out.existing_rank_auto_change_authorized == 0);
    assert(out.customer_pose_emission_authorized == 0);
    assert(out.production_claim_authorized == 0);
    assert(out.scientific_claim_authorized == 0);
}

void assert_complete(const Batch &batch, bg_backend backend) {
    assert(batch.output.row_count == kSlots);
    assert(batch.output.coordinate_count == kCoordinates);
    assert(batch.output.generated_count == kSlots);
    assert(batch.output.typed_failure_count == 0);
    assert(batch.output.backend == backend);
    assert_authority_false(batch.output);
    assert(digest_present(batch.output.allocation_inventory_sha256));
    assert(digest_present(batch.output.allocation_receipt_sha256));
    assert(digest_present(batch.output.source_bundle_receipt_sha256));
    assert(digest_present(
        batch.output.geometric_admission_batch_receipt_sha256));
    assert(digest_present(batch.output.producer_batch_receipt_sha256));
    std::size_t severe = 0;
    for (std::size_t slot = 0; slot < kSlots; ++slot) {
        const auto &row = batch.rows[slot];
        assert(row.slot_index == slot);
        assert(row.status == BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED);
        assert(row.failure_code == BG_DOCKING_FIXED64_PRODUCER_FAILURE_NONE);
        assert(row.backend == backend);
        assert(row.ligand_atom_count == kAtoms);
        assert(row.coordinate_offset == slot * kAtoms);
        assert(row.coordinates_available == 1);
        assert(row.source_identity_verified == 1);
        assert(row.allocation_identity_verified == 1);
        assert(row.geometric_identity_verified == 1);
        assert(row.denominator_preserved == 1);
        assert(row.result_dependent_input_consumed == 0);
        assert(row.fallback_allowed == 0);
        assert(row.multi_anchor_consumed == 0);
        assert(row.molecular_execution_authorized == 0);
        assert(row.reservation_authorized == 0);
        assert(row.benchmark_execution_authorized == 0);
        assert(row.existing_rank_auto_change_authorized == 0);
        assert(row.customer_pose_emission_authorized == 0);
        assert(row.production_claim_authorized == 0);
        assert(row.scientific_claim_authorized == 0);
        assert(digest_present(row.allocation_slot_receipt_sha256));
        assert(digest_present(row.source_payload_receipt_sha256));
        assert(digest_present(row.source_proposal_sha256));
        assert(digest_present(row.source_coordinate_sha256));
        assert(digest_present(row.placement_receipt_sha256));
        assert(digest_present(row.output_proposal_sha256));
        assert(digest_present(row.output_coordinate_sha256));
        assert(digest_present(row.row_receipt_sha256));
        assert(row.geometric_admission.slot_index == slot);
        assert(row.geometric_admission.status ==
               BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED);
        assert(row.geometric_admission.exact_pair_count == kAtoms * kAtoms);
        assert(digest_present(row.geometric_admission.row_receipt_sha256));
        if (row.steric_precheck_passed == 0) ++severe;
        const auto expected_kind = slot < 24 || slot >= 60
            ? BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_EXACT_PASSTHROUGH
            : (slot < 44
                   ? BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_INDEXED_SO3
                   : BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_SINGLE_ANCHOR);
        assert(row.placement_kind == expected_kind);
    }
    assert(severe > 0);
}

void assert_coordinate_parity(
    const Batch &reference, const Batch &observed, double tolerance) {
    for (std::size_t index = 0; index < kCoordinates; ++index) {
        for (const auto &[left, right] : {
                 std::pair{reference.x[index], observed.x[index]},
                 std::pair{reference.y[index], observed.y[index]},
                 std::pair{reference.z[index], observed.z[index]},
             }) {
            const double scale =
                std::max({1.0, std::abs(left), std::abs(right)});
            assert(std::abs(left - right) <= tolerance * scale);
        }
    }
    for (std::size_t slot = 0; slot < kSlots; ++slot) {
        assert(reference.rows[slot].steric_precheck_passed ==
               observed.rows[slot].steric_precheck_passed);
        assert(reference.rows[slot].geometric_admission.decision ==
               observed.rows[slot].geometric_admission.decision);
    }
}

void test_exact64_repeat_and_backend_parity() {
    const Fixture fixture;
    const auto input = make_input(fixture);
    bg_context *cpp = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    assert(cpp != nullptr);
    auto *cpp_admission = make_admission(fixture, cpp);
    const Batch cpp_first = produce(cpp, cpp_admission, input);
    const Batch cpp_repeat = produce(cpp, cpp_admission, input);
    assert_complete(cpp_first, BG_BACKEND_CPP_CPU_REFERENCE);
    assert(cpp_first.x == cpp_repeat.x);
    assert(cpp_first.y == cpp_repeat.y);
    assert(cpp_first.z == cpp_repeat.z);
    assert(std::memcmp(
               cpp_first.rows.data(), cpp_repeat.rows.data(),
               sizeof(cpp_first.rows)) == 0);
    for (const bg_backend backend : {
             BG_BACKEND_RUST_CPU, BG_BACKEND_HIP_SAFE, BG_BACKEND_HIP_FAST}) {
        bg_context *context = make_context(backend);
        if (context == nullptr) continue;
        auto *admission = make_admission(fixture, context);
        const Batch observed = produce(context, admission, input);
        const Batch repeated = produce(context, admission, input);
        assert_complete(observed, backend);
        assert(observed.x == repeated.x);
        assert(observed.y == repeated.y);
        assert(observed.z == repeated.z);
        assert_coordinate_parity(
            cpp_first, observed,
            backend == BG_BACKEND_RUST_CPU ? 2.0e-12 : 2.0e-9);
        bg_docking_geometric_admission_v1_destroy(admission);
        bg_context_destroy(context);
    }
    bg_docking_geometric_admission_v1_destroy(cpp_admission);
    bg_context_destroy(cpp);
}

void test_missing_source_is_typed_and_zero_filled() {
    const Fixture fixture;
    auto input = make_input(fixture);
    input.v7_control_source_count = fixture.v7_sources.size() - 1;
    bg_context *context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    assert(context != nullptr);
    auto *admission = make_admission(fixture, context);
    const Batch batch = produce(context, admission, input);
    assert(batch.output.generated_count == 63);
    assert(batch.output.typed_failure_count == 1);
    const auto &row = batch.rows[23];
    assert(row.status == BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE);
    assert(row.failure_code ==
           BG_DOCKING_FIXED64_PRODUCER_FAILURE_SOURCE_NOT_AVAILABLE);
    assert(row.coordinates_available == 0);
    assert(row.source_identity_verified == 0);
    assert(row.geometric_identity_verified == 1);
    assert(row.geometric_admission.status ==
           BG_DOCKING_GEOMETRIC_ADMISSION_ROW_UPSTREAM_FAILURE);
    for (std::size_t atom = 0; atom < kAtoms; ++atom) {
        const std::size_t offset = 23 * kAtoms + atom;
        assert(batch.x[offset] == 0.0);
        assert(batch.y[offset] == 0.0);
        assert(batch.z[offset] == 0.0);
    }
    assert(digest_present(row.row_receipt_sha256));
    assert_authority_false(batch.output);
    bg_docking_geometric_admission_v1_destroy(admission);
    bg_context_destroy(context);
}

void test_missing_feature_allocation_preserves_denominator() {
    Fixture fixture;
    fixture.allocation.atomic_feature_count = 0;
    fixture.allocation.atomic_features = nullptr;
    auto input = make_input(fixture);
    input.feature_geometry_count = 0;
    input.feature_geometry_rows = nullptr;
    input.feature_atom_index_count = 0;
    input.feature_atom_indices = nullptr;
    std::fill(
        std::begin(input.feature_geometry_inventory_sha256),
        std::end(input.feature_geometry_inventory_sha256), UINT8_C(0));
    bg_context *context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    assert(context != nullptr);
    auto *admission = make_admission(fixture, context);
    const Batch batch = produce(context, admission, input);
    assert(batch.output.generated_count == 48);
    assert(batch.output.typed_failure_count == 16);
    for (std::size_t slot = 44; slot < 60; ++slot) {
        const auto &row = batch.rows[slot];
        assert(row.status == BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE);
        assert(row.failure_code ==
               BG_DOCKING_FIXED64_PRODUCER_FAILURE_ALLOCATION_INELIGIBLE);
        assert(row.source_identity_verified == 1);
        assert(digest_present(row.source_payload_receipt_sha256));
        assert(digest_present(row.source_proposal_sha256));
        assert(digest_present(row.source_coordinate_sha256));
        assert(row.geometric_admission.status ==
               BG_DOCKING_GEOMETRIC_ADMISSION_ROW_UPSTREAM_FAILURE);
        assert(row.denominator_preserved == 1);
    }
    assert_authority_false(batch.output);
    bg_docking_geometric_admission_v1_destroy(admission);
    bg_context_destroy(context);
}

void test_partial_feature_geometry_only_fails_affected_slots() {
    const Fixture fixture;
    auto input = make_input(fixture);
    input.feature_geometry_count = kFeatureCount - 1;
    input.feature_atom_index_count =
        fixture.feature_rows.back().atom_index_offset;
    parse_digest(
        "bde1cd992227894f7c0a8827ba738b3e13c59d7ade8ece6fd0c5e9dd24ea43c1",
        input.feature_geometry_inventory_sha256);
    bg_context *context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    assert(context != nullptr);
    auto *admission = make_admission(fixture, context);
    const Batch batch = produce(context, admission, input);
    assert(batch.output.generated_count == 62);
    assert(batch.output.typed_failure_count == 2);
    for (std::size_t slot = 0; slot < kSlots; ++slot) {
        const auto &row = batch.rows[slot];
        if (slot == 58 || slot == 59) {
            assert(row.status ==
                   BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE);
            assert(row.failure_code ==
                   BG_DOCKING_FIXED64_PRODUCER_FAILURE_FEATURE_GEOMETRY_NOT_AVAILABLE);
            assert(row.coordinates_available == 0);
            assert(row.source_identity_verified == 1);
            assert(row.denominator_preserved == 1);
            assert(row.geometric_admission.status ==
                   BG_DOCKING_GEOMETRIC_ADMISSION_ROW_UPSTREAM_FAILURE);
        } else {
            assert(row.status == BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED);
            assert(row.coordinates_available == 1);
        }
        assert(digest_present(row.row_receipt_sha256));
    }
    assert_authority_false(batch.output);
    bg_docking_geometric_admission_v1_destroy(admission);
    bg_context_destroy(context);
}

void test_equal_cross_kind_receipt_cannot_mask_missing_ligand_geometry() {
    Fixture fixture;
    std::copy_n(
        fixture.atomic_features[0].receipt_sha256,
        32,
        fixture.atomic_features[3].receipt_sha256);
    std::array<bg_docking_fixed64_feature_geometry_row_v1, kFeatureCount - 1>
        feature_rows{};
    std::vector<uint64_t> feature_indices;
    for (std::size_t source = 1; source < kFeatureCount; ++source) {
        auto &target = feature_rows[source - 1];
        target = fixture.feature_rows[source];
        target.atom_index_offset = feature_indices.size();
        const auto first = static_cast<std::size_t>(
            fixture.feature_rows[source].atom_index_offset);
        const auto count = static_cast<std::size_t>(
            fixture.feature_rows[source].atom_index_count);
        feature_indices.insert(
            feature_indices.end(),
            fixture.feature_indices.data() + first,
            fixture.feature_indices.data() + first + count);
    }
    std::copy_n(
        fixture.atomic_features[0].receipt_sha256,
        32,
        feature_rows[2].allocation_feature_receipt_sha256);
    parse_digest(
        "d32faa67a5d4759e5c9e5679207a2b87f94a9ce1877f64a342970c552931fd84",
        feature_rows[2].feature_geometry_receipt_sha256);

    auto input = make_input(fixture);
    input.feature_geometry_count = feature_rows.size();
    input.feature_geometry_rows = feature_rows.data();
    input.feature_atom_index_count = feature_indices.size();
    input.feature_atom_indices = feature_indices.data();
    parse_digest(
        "2c7036e5304e5be45b38e3161fed44471392b168db2669c7675b26ce15f27981",
        input.feature_geometry_inventory_sha256);
    bg_context *context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    assert(context != nullptr);
    auto *admission = make_admission(fixture, context);
    const Batch batch = produce(context, admission, input);
    assert(batch.output.generated_count == 60);
    assert(batch.output.typed_failure_count == 4);
    for (std::size_t slot = 0; slot < kSlots; ++slot) {
        const auto &row = batch.rows[slot];
        if (slot >= 44 && slot < 48) {
            assert(row.status ==
                   BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE);
            assert(row.failure_code ==
                   BG_DOCKING_FIXED64_PRODUCER_FAILURE_FEATURE_GEOMETRY_NOT_AVAILABLE);
            assert(row.source_identity_verified == UINT8_C(1));
            assert(row.coordinates_available == UINT8_C(0));
        } else {
            assert(row.status == BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED);
        }
        assert(row.geometric_identity_verified == UINT8_C(1));
        assert(digest_present(row.row_receipt_sha256));
    }
    assert_authority_false(batch.output);
    bg_docking_geometric_admission_v1_destroy(admission);
    bg_context_destroy(context);
}

void test_single_atom_ligand_preserves_all_fixed64_rows() {
    Fixture fixture;
    fixture.allocation.atomic_feature_count = 0;
    fixture.allocation.atomic_features = nullptr;
    parse_digest(
        "70c6f2b5446c0652d7bbc81537a0ac8a93553e961ecb3c2c40fee2620de1545b",
        fixture.allocation.exact_v11_source.ligand_coordinate_sha256);
    parse_digest(
        "d4379c8a5c7b2291893bd45b047e8736168136002dd646b705a735875a947919",
        fixture.allocation.exact_v11_source.ligand_vdw_radii_sha256);
    parse_digest(
        "49e14fc025f4768dc72e02fe53803e4cd9906d5dc7c89c1f7b08c6fb39b9223a",
        fixture.allocation.exact_v11_source.ligand_heavy_atom_mask_sha256);
    fixture.exact_source.ligand_atom_count = 1;
    std::copy_n(
        fixture.allocation.exact_v11_source.ligand_coordinate_sha256,
        32,
        fixture.exact_source.source.coordinate_sha256);
    for (std::size_t index = 0; index < fixture.v7_evidence.size(); ++index) {
        fixture.v7_sources[index].payload.ligand_atom_count = 1;
        std::copy_n(
            fixture.allocation.exact_v11_source.ligand_coordinate_sha256,
            32,
            fixture.v7_evidence[index].source.coordinate_sha256);
        std::copy_n(
            fixture.allocation.exact_v11_source.ligand_coordinate_sha256,
            32,
            fixture.v7_sources[index].payload.source.coordinate_sha256);
    }
    for (std::size_t index = 0; index < fixture.conformer_evidence.size();
         ++index) {
        fixture.conformer_sources[index].payload.ligand_atom_count = 1;
        std::copy_n(
            fixture.allocation.exact_v11_source.ligand_coordinate_sha256,
            32,
            fixture.conformer_evidence[index].source.coordinate_sha256);
        std::copy_n(
            fixture.allocation.exact_v11_source.ligand_coordinate_sha256,
            32,
            fixture.conformer_sources[index].payload.source.coordinate_sha256);
    }
    for (std::size_t index = 0; index < fixture.retained_evidence.size();
         ++index) {
        fixture.retained_sources[index].payload.ligand_atom_count = 1;
        std::copy_n(
            fixture.allocation.exact_v11_source.ligand_coordinate_sha256,
            32,
            fixture.retained_evidence[index].source.coordinate_sha256);
        std::copy_n(
            fixture.allocation.exact_v11_source.ligand_coordinate_sha256,
            32,
            fixture.retained_sources[index].payload.source.coordinate_sha256);
    }

    auto input = make_input(fixture);
    input.feature_geometry_count = 0;
    input.feature_geometry_rows = nullptr;
    input.feature_atom_index_count = 0;
    input.feature_atom_indices = nullptr;
    std::fill(
        std::begin(input.feature_geometry_inventory_sha256),
        std::end(input.feature_geometry_inventory_sha256),
        UINT8_C(0));

    bg_context *context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    assert(context != nullptr);
    auto *admission = make_admission(fixture, context, {0.0, 0.0, 0.0}, 1);
    const Batch batch = produce(context, admission, input);
    assert(batch.output.row_count == kSlots);
    assert(batch.output.coordinate_count == kSlots);
    assert(batch.output.generated_count == 28);
    assert(batch.output.typed_failure_count == 36);
    for (std::size_t slot = 0; slot < kSlots; ++slot) {
        const auto &row = batch.rows[slot];
        assert(row.slot_index == slot);
        assert(row.ligand_atom_count == 1);
        assert(row.coordinate_offset == slot);
        assert(row.denominator_preserved == UINT8_C(1));
        assert(row.geometric_identity_verified == UINT8_C(1));
        assert(digest_present(row.row_receipt_sha256));
        if (slot < 24 || slot >= 60) {
            assert(row.status == BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED);
            assert(row.coordinates_available == UINT8_C(1));
        } else {
            assert(row.status ==
                   BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE);
            assert(row.coordinates_available == UINT8_C(0));
        }
    }
    assert_authority_false(batch.output);
    bg_docking_geometric_admission_v1_destroy(admission);
    bg_context_destroy(context);
}

void test_ready_anchor_without_geometry_is_typed() {
    const Fixture fixture;
    auto input = make_input(fixture);
    input.feature_geometry_count = 0;
    input.feature_geometry_rows = nullptr;
    input.feature_atom_index_count = 0;
    input.feature_atom_indices = nullptr;
    std::fill(
        std::begin(input.feature_geometry_inventory_sha256),
        std::end(input.feature_geometry_inventory_sha256), UINT8_C(0));
    bg_context *context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    assert(context != nullptr);
    auto *admission = make_admission(fixture, context);
    const Batch batch = produce(context, admission, input);
    assert(batch.output.generated_count == 48);
    assert(batch.output.typed_failure_count == 16);
    for (std::size_t slot = 44; slot < 60; ++slot) {
        const auto &row = batch.rows[slot];
        assert(row.status == BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE);
        assert(row.failure_code ==
               BG_DOCKING_FIXED64_PRODUCER_FAILURE_FEATURE_GEOMETRY_NOT_AVAILABLE);
        assert(row.placement_kind ==
               BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_SINGLE_ANCHOR);
        assert(row.source_identity_verified == 1);
        assert(row.coordinates_available == 0);
        assert(row.geometric_admission.status ==
               BG_DOCKING_GEOMETRIC_ADMISSION_ROW_UPSTREAM_FAILURE);
        assert(digest_present(row.row_receipt_sha256));
    }
    assert_authority_false(batch.output);
    bg_docking_geometric_admission_v1_destroy(admission);
    bg_context_destroy(context);
}

void test_component_typed_failure_is_retained() {
    const Fixture fixture;
    const auto input = make_input(fixture);
    for (const bg_backend backend : {
             BG_BACKEND_CPP_CPU_REFERENCE, BG_BACKEND_RUST_CPU,
             BG_BACKEND_HIP_SAFE, BG_BACKEND_HIP_FAST}) {
        bg_context *context = make_context(backend);
        if (context == nullptr) continue;
        auto *admission = make_admission(
            fixture, context,
            {fixture.receptor_x[2], fixture.receptor_y[2],
             fixture.receptor_z[2]});
        const Batch batch = produce(context, admission, input);
        assert(batch.output.row_count == kSlots);
        assert(batch.output.generated_count < kSlots);
        assert(batch.output.generated_count + batch.output.typed_failure_count ==
               kSlots);
        bool found = false;
        for (std::size_t slot = 44; slot < 60; ++slot) {
            const auto &row = batch.rows[slot];
            if (row.failure_code !=
                BG_DOCKING_FIXED64_PRODUCER_FAILURE_SINGLE_ANCHOR_TYPED_FAILURE) {
                continue;
            }
            found = true;
            assert(row.coordinates_available == 0);
            assert(row.component_failure_code != 0);
            assert(row.geometric_admission.status ==
                   BG_DOCKING_GEOMETRIC_ADMISSION_ROW_UPSTREAM_FAILURE);
            assert(row.denominator_preserved == 1);
        }
        assert(found);
        assert_authority_false(batch.output);
        bg_docking_geometric_admission_v1_destroy(admission);
        bg_context_destroy(context);
    }
}

void test_invalid_input_capacity_and_alias_are_transactional() {
    Fixture fixture;
    auto input = make_input(fixture);
    bg_context *context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    assert(context != nullptr);
    auto *admission = make_admission(fixture, context);
    Batch batch{};
    assert(bg_docking_fixed64_producer_output_v1_init(&batch.output) ==
           BG_STATUS_OK);
    batch.output.row_capacity = kSlots;
    batch.output.coordinate_capacity = kCoordinates - 1;
    batch.output.rows = batch.rows.data();
    batch.output.x_angstrom = batch.x.data();
    batch.output.y_angstrom = batch.y.data();
    batch.output.z_angstrom = batch.z.data();
    std::fill(batch.x.begin(), batch.x.end(), 91.0);
    std::fill(batch.y.begin(), batch.y.end(), 81.0);
    std::fill(batch.z.begin(), batch.z.end(), 71.0);
    std::memset(batch.rows.data(), 0xA5, sizeof(batch.rows));
    const auto output_before = object_bytes(batch.output);
    const auto rows_before = batch.rows;
    const auto x_before = batch.x;
    assert(bg_docking_fixed64_producer_v1_run(
               context, admission, &input, &batch.output) ==
           BG_STATUS_BUFFER_TOO_SMALL);
    assert(object_bytes(batch.output) == output_before);
    assert(std::memcmp(
               batch.rows.data(), rows_before.data(), sizeof(batch.rows)) == 0);
    assert(batch.x == x_before);

    batch.output.coordinate_capacity = kCoordinates;
    batch.output.x_angstrom = fixture.source_x.data();
    const auto alias_before = object_bytes(batch.output);
    const auto source_before = fixture.source_x;
    assert(bg_docking_fixed64_producer_v1_run(
               context, admission, &input, &batch.output) ==
           BG_STATUS_INVALID_ARGUMENT);
    assert(object_bytes(batch.output) == alias_before);
    assert(fixture.source_x == source_before);

    batch.output.x_angstrom = batch.x.data();
    input.feature_geometry_inventory_sha256[0] ^= UINT8_C(1);
    const auto crosswire_before = object_bytes(batch.output);
    assert(bg_docking_fixed64_producer_v1_run(
               context, admission, &input, &batch.output) ==
           BG_STATUS_INVALID_ARGUMENT);
    assert(object_bytes(batch.output) == crosswire_before);
    assert(std::memcmp(
               batch.rows.data(), rows_before.data(), sizeof(batch.rows)) == 0);
    assert(batch.x == x_before);
    bg_docking_geometric_admission_v1_destroy(admission);
    bg_context_destroy(context);
}

void test_oversized_source_count_is_rejected_before_narrowing() {
    const Fixture fixture;
    auto input = make_input(fixture);
    input.v7_control_source_count = UINT64_MAX;
    bg_context *context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    assert(context != nullptr);
    auto *admission = make_admission(fixture, context);
    Batch batch{};
    assert(bg_docking_fixed64_producer_output_v1_init(&batch.output) ==
           BG_STATUS_OK);
    batch.output.row_capacity = batch.rows.size();
    batch.output.coordinate_capacity = batch.x.size();
    batch.output.rows = batch.rows.data();
    batch.output.x_angstrom = batch.x.data();
    batch.output.y_angstrom = batch.y.data();
    batch.output.z_angstrom = batch.z.data();
    std::memset(batch.rows.data(), 0xA5, sizeof(batch.rows));
    std::fill(batch.x.begin(), batch.x.end(), 91.0);
    std::fill(batch.y.begin(), batch.y.end(), 81.0);
    std::fill(batch.z.begin(), batch.z.end(), 71.0);
    const auto output_before = object_bytes(batch.output);
    const auto rows_before = batch.rows;
    const auto x_before = batch.x;
    const auto y_before = batch.y;
    const auto z_before = batch.z;
    assert(bg_docking_fixed64_producer_v1_run(
               context, admission, &input, &batch.output) ==
           BG_STATUS_CAPACITY_OVERFLOW);
    assert(object_bytes(batch.output) == output_before);
    assert(std::memcmp(
               batch.rows.data(), rows_before.data(), sizeof(batch.rows)) == 0);
    assert(batch.x == x_before && batch.y == y_before && batch.z == z_before);
    bg_docking_geometric_admission_v1_destroy(admission);
    bg_context_destroy(context);
}

}  // namespace

int main() {
    test_exact64_repeat_and_backend_parity();
    test_missing_source_is_typed_and_zero_filled();
    test_missing_feature_allocation_preserves_denominator();
    test_partial_feature_geometry_only_fails_affected_slots();
    test_equal_cross_kind_receipt_cannot_mask_missing_ligand_geometry();
    test_single_atom_ligand_preserves_all_fixed64_rows();
    test_ready_anchor_without_geometry_is_typed();
    test_component_typed_failure_is_retained();
    test_invalid_input_capacity_and_alias_are_transactional();
    test_oversized_source_count_is_rejected_before_narrowing();
    return 0;
}
