#include "betelgeuze/engine.h"

#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string_view>
#include <string>
#include <tuple>
#include <type_traits>
#include <utility>
#include <vector>

namespace {

constexpr std::size_t kAtoms = 4;
constexpr std::size_t kFeatureCount = BG_DOCKING_FIXED64_FEATURE_KIND_COUNT;
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

struct Fixture final {
    std::array<double, kAtoms> source_x = {0.0, 1.0, 0.0, 0.0};
    std::array<double, kAtoms> source_y = {0.0, 0.0, 1.0, 0.0};
    std::array<double, kAtoms> source_z = {0.0, 0.0, 0.0, 1.0};
    std::array<double, kAtoms> receptor_x = {4.0, 3.5, 4.0, 4.0};
    std::array<double, kAtoms> receptor_y = {0.0, 0.0, 1.0, 0.0};
    std::array<double, kAtoms> receptor_z = {0.0, 0.0, 0.0, 1.0};
    std::array<double, kAtoms> ligand_radii = {1.5, 1.5, 1.5, 1.5};
    std::array<double, kAtoms> receptor_radii = {1.5, 1.5, 1.5, 1.5};
    std::array<uint8_t, kAtoms> heavy_mask = {1, 1, 1, 1};
    std::array<bg_docking_fixed64_atomic_feature_evidence_v1, kFeatureCount>
        atomic_features{};
    std::array<bg_docking_fixed64_feature_geometry_row_v1, kFeatureCount>
        feature_rows{};
    std::vector<uint64_t> feature_indices;
    bg_docking_fixed64_allocation_input_v1 allocation{};

    Fixture() {
        assert(bg_docking_fixed64_allocation_input_v1_init(&allocation) ==
               BG_STATUS_OK);
        fill_digest(allocation.exact_v11_source.source_receipt_sha256, 0x10);
        fill_digest(allocation.exact_v11_source.proposal_sha256, 0x11);
        parse_digest(
            "fe2cd37291f9fe4f48ee1379c7c7e4cabaf7bb8b6d216b4d6814e308d6ca286c",
            allocation.exact_v11_source.ligand_coordinate_sha256);
        parse_digest(
            "8cb1e4a6f8ae2a82832c1d5ae36c914fcb15030faa20c4901b2f842e0348ca58",
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
        const std::array<std::vector<uint64_t>, kFeatureCount> indices = {
            std::vector<uint64_t>{0, 1},
            std::vector<uint64_t>{2},
            std::vector<uint64_t>{0, 1},
            std::vector<uint64_t>{2},
            std::vector<uint64_t>{1},
            std::vector<uint64_t>{2},
            std::vector<uint64_t>{1},
            std::vector<uint64_t>{2},
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
                atomic.receipt_sha256,
                32,
                geometry.allocation_feature_receipt_sha256);
            geometry.atom_index_offset = feature_indices.size();
            geometry.atom_index_count = indices[index].size();
            feature_indices.insert(
                feature_indices.end(),
                indices[index].begin(),
                indices[index].end());
            parse_digest(
                kFeatureReceipts[index],
                geometry.feature_geometry_receipt_sha256);
        }
        allocation.atomic_feature_count = atomic_features.size();
        allocation.atomic_features = atomic_features.data();
        std::array<bg_docking_fixed64_allocation_row_v1,
                   BG_DOCKING_FIXED64_CANDIDATE_COUNT>
            rows{};
        bg_docking_fixed64_allocation_output_v1 output{};
        assert(bg_docking_fixed64_allocation_output_v1_init(&output) ==
               BG_STATUS_OK);
        output.row_capacity = rows.size();
        output.rows = rows.data();
        assert(bg_docking_fixed64_allocation_v1_build(&allocation, &output) ==
               BG_STATUS_OK);
        for (std::size_t slot = 44; slot < 60; ++slot) {
            assert(rows[slot].status ==
                   BG_DOCKING_FIXED64_ALLOCATION_ROW_READY);
            assert(rows[slot].selected_source_receipt_count == 2);
        }
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
    std::array<double, 3> pocket_center = {0.0, 0.0, 0.0}) {
    bg_docking_geometric_admission_context_soa_v1 descriptor{};
    assert(bg_docking_geometric_admission_context_soa_v1_init(&descriptor) ==
           BG_STATUS_OK);
    descriptor.unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
    descriptor.receptor_atom_count = kAtoms;
    descriptor.ligand_atom_count = kAtoms;
    descriptor.receptor_x_angstrom = fixture.receptor_x.data();
    descriptor.receptor_y_angstrom = fixture.receptor_y.data();
    descriptor.receptor_z_angstrom = fixture.receptor_z.data();
    descriptor.receptor_vdw_radius_angstrom = fixture.receptor_radii.data();
    descriptor.ligand_vdw_radius_angstrom = fixture.ligand_radii.data();
    descriptor.ligand_heavy_atom_mask = fixture.heavy_mask.data();
    std::copy(
        pocket_center.begin(),
        pocket_center.end(),
        descriptor.pocket_center_angstrom);
    descriptor.pocket_radius_angstrom = 10.0;
    descriptor.hard_rejection_minimum_vdw_ratio = 0.55;
    descriptor.max_batch_exact_pair_evaluations = UINT64_C(16'777'216);
    fill_digest(descriptor.authority_input_receipt_sha256, 0x70);
    fill_digest(descriptor.receptor_system_sha256, 0x71);
    fill_digest(descriptor.ligand_system_sha256, 0x72);
    fill_digest(descriptor.backend_receipt_sha256, 0x73);
    bg_docking_geometric_admission_v1 *admission = nullptr;
    const bg_status status = bg_docking_geometric_admission_v1_create(
        context, &descriptor, &admission);
    if (status != BG_STATUS_OK) {
        std::fprintf(stderr, "admission create failed: %s\n", bg_last_error_message());
    }
    assert(status == BG_STATUS_OK);
    assert(admission != nullptr);
    return admission;
}

bg_docking_fixed64_single_anchor_input_v1 make_input(
    const Fixture &fixture,
    uint32_t slot) {
    bg_docking_fixed64_single_anchor_input_v1 input{};
    assert(bg_docking_fixed64_single_anchor_input_v1_init(&input) ==
           BG_STATUS_OK);
    input.allocation_input = &fixture.allocation;
    input.slot_index = slot;
    std::copy_n(
        fixture.allocation.exact_v11_source.source_receipt_sha256,
        32,
        input.source.receipt_sha256);
    std::copy_n(
        fixture.allocation.exact_v11_source.proposal_sha256,
        32,
        input.source.proposal_sha256);
    std::copy_n(
        fixture.allocation.exact_v11_source.ligand_coordinate_sha256,
        32,
        input.source.coordinate_sha256);
    input.ligand_atom_count = kAtoms;
    input.source_x_angstrom = fixture.source_x.data();
    input.source_y_angstrom = fixture.source_y.data();
    input.source_z_angstrom = fixture.source_z.data();
    input.feature_geometry_count = fixture.feature_rows.size();
    input.feature_geometry_rows = fixture.feature_rows.data();
    input.feature_atom_index_count = fixture.feature_indices.size();
    input.feature_atom_indices = fixture.feature_indices.data();
    parse_digest(
        "0f93ce2e442cdcdd01d8c6e0840f09c485a17b0169f66a341355797877981ea2",
        input.feature_geometry_inventory_sha256);
    return input;
}

struct Placement final {
    std::array<double, kAtoms> x{};
    std::array<double, kAtoms> y{};
    std::array<double, kAtoms> z{};
    bg_docking_fixed64_single_anchor_output_v1 output{};
};

Placement place(
    bg_context *context,
    bg_docking_geometric_admission_v1 *admission,
    const bg_docking_fixed64_single_anchor_input_v1 &input) {
    Placement value{};
    assert(bg_docking_fixed64_single_anchor_output_v1_init(&value.output) ==
           BG_STATUS_OK);
    value.output.coordinate_capacity = kAtoms;
    value.output.x_angstrom = value.x.data();
    value.output.y_angstrom = value.y.data();
    value.output.z_angstrom = value.z.data();
    const bg_status status = bg_docking_fixed64_single_anchor_v1_place(
        context, admission, &input, &value.output);
    if (status != BG_STATUS_OK) {
        const std::string detail = bg_last_error_message();
        bg_backend backend = BG_BACKEND_AUTO;
        assert(bg_context_get_backend(context, &backend) == BG_STATUS_OK);
        std::fprintf(
            stderr,
            "single-anchor backend %d slot %u placement failed: %s\n",
            backend,
            input.slot_index,
            detail.c_str());
    }
    assert(status == BG_STATUS_OK);
    return value;
}

void assert_complete(const Placement &value, bg_backend backend, uint32_t slot) {
    assert(value.output.slot_index == slot);
    assert(value.output.status == BG_DOCKING_FIXED64_SINGLE_ANCHOR_PLACED);
    assert(value.output.failure_code ==
           BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_NONE);
    assert(value.output.backend == backend);
    assert(value.output.ligand_atom_count == kAtoms);
    assert(value.output.coordinates_written == 1);
    assert(value.output.source_identity_verified == 1);
    assert(value.output.allocation_identity_verified == 1);
    assert(value.output.feature_identity_verified == 1);
    assert(value.output.geometric_identity_verified == 1);
    assert(value.output.result_dependent_input_consumed == 0);
    assert(value.output.fallback_allowed == 0);
    assert(value.output.multi_anchor_consumed == 0);
    assert(value.output.denominator_preserved == 1);
    assert(value.output.molecular_execution_authorized == 0);
    assert(value.output.reservation_authorized == 0);
    assert(value.output.benchmark_execution_authorized == 0);
    assert(value.output.existing_rank_auto_change_authorized == 0);
    assert(value.output.customer_pose_emission_authorized == 0);
    assert(value.output.production_claim_authorized == 0);
    assert(value.output.scientific_claim_authorized == 0);
    assert(value.output.geometric_admission.slot_index == slot);
    assert(value.output.geometric_admission.status ==
           BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED);
    assert(value.output.geometric_admission.exact_pair_count == kAtoms * kAtoms);
    assert(digest_present(value.output.output_coordinate_sha256));
    assert(digest_present(value.output.placement_receipt_sha256));
    assert(digest_present(
        value.output.geometric_admission_batch_receipt_sha256));
}

void assert_geometric_parity(
    const Placement &reference,
    const Placement &observed,
    double tolerance) {
    const auto &left = reference.output.geometric_admission;
    const auto &right = observed.output.geometric_admission;
    assert(left.status == right.status);
    assert(left.failure_code == right.failure_code);
    assert(left.decision == right.decision);
    assert(left.rank_eligible == right.rank_eligible);
    assert(left.ligand_atom_count == right.ligand_atom_count);
    assert(left.receptor_atom_count == right.receptor_atom_count);
    assert(left.exact_pair_count == right.exact_pair_count);
    assert(left.penetration_pair_count == right.penetration_pair_count);
    assert(left.unique_ligand_penetration_atom_count ==
           right.unique_ligand_penetration_atom_count);
    assert(left.unique_ligand_heavy_atom_penetration_count ==
           right.unique_ligand_heavy_atom_penetration_count);
    for (const auto &[expected, actual] : {
             std::pair{left.raw_minimum_distance_angstrom,
                       right.raw_minimum_distance_angstrom},
             std::pair{left.minimum_vdw_surface_gap_angstrom,
                       right.minimum_vdw_surface_gap_angstrom},
             std::pair{left.minimum_vdw_ratio, right.minimum_vdw_ratio},
             std::pair{left.sphere_overlap_proxy_angstrom3,
                       right.sphere_overlap_proxy_angstrom3},
             std::pair{left.pocket_escape_angstrom,
                       right.pocket_escape_angstrom},
         }) {
        const double scale =
            std::max({1.0, std::abs(expected), std::abs(actual)});
        assert(std::abs(expected - actual) <= tolerance * scale);
    }
}

void test_all_anchor_lanes_repeat_and_backend_parity() {
    const Fixture fixture;
    bg_context *cpp = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    bg_context *rust = make_context(BG_BACKEND_RUST_CPU);
    bg_context *hip_safe = make_context(BG_BACKEND_HIP_SAFE);
    bg_context *hip_fast = make_context(BG_BACKEND_HIP_FAST);
    assert(cpp != nullptr && rust != nullptr);
    auto *cpp_admission = make_admission(fixture, cpp);
    auto *rust_admission = make_admission(fixture, rust);
    auto *hip_safe_admission = hip_safe == nullptr
        ? nullptr
        : make_admission(fixture, hip_safe);
    auto *hip_fast_admission = hip_fast == nullptr
        ? nullptr
        : make_admission(fixture, hip_fast);
    std::size_t severe_penetration_slots = 0;
    for (uint32_t slot = 44; slot < 60; ++slot) {
        const auto input = make_input(fixture, slot);
        const Placement cpp_first = place(cpp, cpp_admission, input);
        const Placement cpp_repeat = place(cpp, cpp_admission, input);
        const Placement rust_first = place(rust, rust_admission, input);
        const Placement rust_repeat = place(rust, rust_admission, input);
        assert_complete(cpp_first, BG_BACKEND_CPP_CPU_REFERENCE, slot);
        assert_complete(rust_first, BG_BACKEND_RUST_CPU, slot);
        if (cpp_first.output.steric_precheck_passed == 0) {
            ++severe_penetration_slots;
        }
        assert(cpp_first.output.steric_precheck_passed ==
               rust_first.output.steric_precheck_passed);
        assert_geometric_parity(cpp_first, rust_first, 2.0e-12);
        assert(cpp_first.x == cpp_repeat.x);
        assert(rust_first.x == rust_repeat.x);
        for (std::size_t atom = 0; atom < kAtoms; ++atom) {
            assert(std::abs(cpp_first.x[atom] - rust_first.x[atom]) < 2.0e-12);
            assert(std::abs(cpp_first.y[atom] - rust_first.y[atom]) < 2.0e-12);
            assert(std::abs(cpp_first.z[atom] - rust_first.z[atom]) < 2.0e-12);
        }
        for (const auto &[backend, context, admission] : {
                 std::tuple{BG_BACKEND_HIP_SAFE, hip_safe, hip_safe_admission},
                 std::tuple{BG_BACKEND_HIP_FAST, hip_fast, hip_fast_admission}}) {
            if (context == nullptr) continue;
            const Placement hip_first = place(context, admission, input);
            const Placement hip_repeat = place(context, admission, input);
            assert_complete(hip_first, backend, slot);
            assert(hip_first.x == hip_repeat.x);
            assert(cpp_first.output.steric_precheck_passed ==
                   hip_first.output.steric_precheck_passed);
            assert_geometric_parity(cpp_first, hip_first, 2.0e-9);
            for (std::size_t atom = 0; atom < kAtoms; ++atom) {
                assert(std::abs(hip_first.x[atom] - rust_first.x[atom]) < 2.0e-9);
                assert(std::abs(hip_first.y[atom] - rust_first.y[atom]) < 2.0e-9);
                assert(std::abs(hip_first.z[atom] - rust_first.z[atom]) < 2.0e-9);
            }
        }
    }
    assert(severe_penetration_slots > 0);
    if (hip_safe_admission != nullptr) {
        bg_docking_geometric_admission_v1_destroy(hip_safe_admission);
        bg_context_destroy(hip_safe);
    }
    if (hip_fast_admission != nullptr) {
        bg_docking_geometric_admission_v1_destroy(hip_fast_admission);
        bg_context_destroy(hip_fast);
    }
    bg_docking_geometric_admission_v1_destroy(cpp_admission);
    bg_docking_geometric_admission_v1_destroy(rust_admission);
    bg_context_destroy(cpp);
    bg_context_destroy(rust);
}

void test_crosswired_feature_is_transactional() {
    Fixture fixture;
    bg_context *context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    assert(context != nullptr);
    auto *admission = make_admission(fixture, context);
    auto input = make_input(fixture, 44);
    std::array<double, kAtoms> x = {91.0, 92.0, 93.0, 94.0};
    std::array<double, kAtoms> y = {81.0, 82.0, 83.0, 84.0};
    std::array<double, kAtoms> z = {71.0, 72.0, 73.0, 74.0};
    bg_docking_fixed64_single_anchor_output_v1 output{};
    assert(bg_docking_fixed64_single_anchor_output_v1_init(&output) ==
           BG_STATUS_OK);
    output.coordinate_capacity = kAtoms;
    output.x_angstrom = x.data();
    output.y_angstrom = y.data();
    output.z_angstrom = z.data();
    output.slot_index = 61;
    fill_digest(output.placement_receipt_sha256, 0x99);
    const auto output_before = object_bytes(output);
    const auto x_before = x;
    const auto y_before = y;
    const auto z_before = z;
    input.feature_geometry_inventory_sha256[0] ^= UINT8_C(1);
    assert(bg_docking_fixed64_single_anchor_v1_place(
               context, admission, &input, &output) ==
           BG_STATUS_INVALID_ARGUMENT);
    assert(object_bytes(output) == output_before);
    assert(x == x_before && y == y_before && z == z_before);
    bg_docking_geometric_admission_v1_destroy(admission);
    bg_context_destroy(context);
}

void test_capacity_and_alias_are_transactional() {
    Fixture fixture;
    bg_context *context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    assert(context != nullptr);
    auto *admission = make_admission(fixture, context);
    const auto input = make_input(fixture, 44);
    std::array<double, kAtoms> x = {91.0, 92.0, 93.0, 94.0};
    std::array<double, kAtoms> y = {81.0, 82.0, 83.0, 84.0};
    std::array<double, kAtoms> z = {71.0, 72.0, 73.0, 74.0};
    bg_docking_fixed64_single_anchor_output_v1 output{};
    assert(bg_docking_fixed64_single_anchor_output_v1_init(&output) ==
           BG_STATUS_OK);
    output.coordinate_capacity = kAtoms - 1;
    output.x_angstrom = x.data();
    output.y_angstrom = y.data();
    output.z_angstrom = z.data();
    const auto small_before = object_bytes(output);
    assert(bg_docking_fixed64_single_anchor_v1_place(
               context, admission, &input, &output) ==
           BG_STATUS_BUFFER_TOO_SMALL);
    assert(object_bytes(output) == small_before);
    assert((x == std::array<double, kAtoms>{91.0, 92.0, 93.0, 94.0}));

    output.coordinate_capacity = kAtoms;
    output.x_angstrom = fixture.source_x.data();
    const auto output_before = object_bytes(output);
    const auto source_before = fixture.source_x;
    assert(bg_docking_fixed64_single_anchor_v1_place(
               context, admission, &input, &output) ==
           BG_STATUS_INVALID_ARGUMENT);
    assert(object_bytes(output) == output_before);
    assert(fixture.source_x == source_before);
    bg_docking_geometric_admission_v1_destroy(admission);
    bg_context_destroy(context);
}

void test_typed_geometry_failure_preserves_denominator_and_coordinates() {
    const Fixture fixture;
    const auto input = make_input(fixture, 44);
    for (const bg_backend backend : {
             BG_BACKEND_CPP_CPU_REFERENCE,
             BG_BACKEND_RUST_CPU,
             BG_BACKEND_HIP_SAFE,
             BG_BACKEND_HIP_FAST,
         }) {
        bg_context *context = make_context(backend);
        if (context == nullptr) continue;
        auto *admission = make_admission(
            fixture,
            context,
            {fixture.receptor_x[2], fixture.receptor_y[2],
             fixture.receptor_z[2]});
        std::array<double, kAtoms> x = {91.0, 92.0, 93.0, 94.0};
        std::array<double, kAtoms> y = {81.0, 82.0, 83.0, 84.0};
        std::array<double, kAtoms> z = {71.0, 72.0, 73.0, 74.0};
        bg_docking_fixed64_single_anchor_output_v1 output{};
        assert(bg_docking_fixed64_single_anchor_output_v1_init(&output) ==
               BG_STATUS_OK);
        output.coordinate_capacity = kAtoms;
        output.x_angstrom = x.data();
        output.y_angstrom = y.data();
        output.z_angstrom = z.data();
        assert(bg_docking_fixed64_single_anchor_v1_place(
                   context, admission, &input, &output) == BG_STATUS_OK);
        assert(output.status == BG_DOCKING_FIXED64_SINGLE_ANCHOR_TYPED_FAILURE);
        assert(output.failure_code ==
               BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_LOCAL_SURFACE_NORMAL);
        assert(output.backend == backend);
        assert(output.coordinates_written == 0);
        assert(output.denominator_preserved == 1);
        assert(output.geometric_admission.slot_index == 44);
        assert(output.geometric_admission.status ==
               BG_DOCKING_GEOMETRIC_ADMISSION_ROW_UPSTREAM_FAILURE);
        assert(output.geometric_admission.failure_code ==
               BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_UPSTREAM_NOT_AVAILABLE);
        assert(digest_present(output.geometric_admission.row_receipt_sha256));
        assert(digest_present(output.geometric_admission_batch_receipt_sha256));
        assert(digest_present(output.placement_receipt_sha256));
        assert((x == std::array<double, kAtoms>{91.0, 92.0, 93.0, 94.0}));
        assert((y == std::array<double, kAtoms>{81.0, 82.0, 83.0, 84.0}));
        assert((z == std::array<double, kAtoms>{71.0, 72.0, 73.0, 74.0}));
        bg_docking_geometric_admission_v1_destroy(admission);
        bg_context_destroy(context);
    }
}

}  // namespace

int main() {
    test_all_anchor_lanes_repeat_and_backend_parity();
    test_crosswired_feature_is_transactional();
    test_capacity_and_alias_are_transactional();
    test_typed_geometry_failure_preserves_denominator_and_coordinates();
    return 0;
}
