#include "betelgeuze/engine.h"

#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <numeric>
#include <type_traits>
#include <utility>

namespace {

constexpr std::size_t kSlots = BG_DOCKING_FIXED64_CANDIDATE_COUNT;
constexpr std::size_t kAtoms = 4;
constexpr std::array<uint8_t, 32> kSourceCoordinateSha256 = {
    0xfe, 0x2c, 0xd3, 0x72, 0x91, 0xf9, 0xfe, 0x4f,
    0x48, 0xee, 0x13, 0x79, 0xc7, 0xc7, 0xe4, 0xca,
    0xba, 0xf7, 0xbb, 0x8b, 0x6d, 0x21, 0x6b, 0x4d,
    0x68, 0x14, 0xe3, 0x08, 0xd6, 0xca, 0x28, 0x6c,
};
constexpr std::array<uint8_t, 32> kDegenerateCoordinateSha256 = {
    0xe5, 0x31, 0x73, 0xe8, 0x1d, 0x72, 0xc0, 0xa2,
    0xf4, 0x09, 0xe7, 0xef, 0x86, 0x8d, 0x10, 0xfb,
    0xef, 0xeb, 0x7f, 0xc3, 0x2f, 0x36, 0x12, 0x07,
    0x8c, 0x13, 0xaa, 0xad, 0xf4, 0x16, 0x9d, 0xa3,
};

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

struct Allocation final {
    bg_docking_fixed64_allocation_input_v1 input{};
    std::array<bg_docking_fixed64_conformer_source_evidence_v1, 7>
        conformer_sources{};
    std::array<bg_docking_fixed64_allocation_row_v1, kSlots> rows{};
    bg_docking_fixed64_allocation_output_v1 output{};

    explicit Allocation(const std::array<uint8_t, 32> &coordinate) {
        assert(bg_docking_fixed64_allocation_input_v1_init(&input) ==
               BG_STATUS_OK);
        fill_digest(input.exact_v11_source.source_receipt_sha256, 0x10);
        fill_digest(input.exact_v11_source.proposal_sha256, 0x11);
        std::copy(
            coordinate.begin(),
            coordinate.end(),
            input.exact_v11_source.ligand_coordinate_sha256);
        fill_digest(input.exact_v11_source.receptor_coordinate_sha256, 0x12);
        fill_digest(
            input.exact_v11_source.prepared_ligand_topology_sha256,
            0x13);
        fill_digest(
            input.exact_v11_source.prepared_receptor_topology_sha256,
            0x14);
        fill_digest(input.exact_v11_source.ligand_vdw_radii_sha256, 0x15);
        fill_digest(
            input.exact_v11_source.ligand_heavy_atom_mask_sha256,
            0x16);
        fill_digest(input.exact_v11_source.receptor_vdw_radii_sha256, 0x17);
        for (std::size_t index = 0; index < conformer_sources.size(); ++index) {
            auto &source = conformer_sources[index];
            source.rank = static_cast<uint8_t>(index + 2U);
            fill_digest(
                source.source.receipt_sha256,
                static_cast<uint8_t>(0x30U + source.rank));
            fill_digest(
                source.source.proposal_sha256,
                static_cast<uint8_t>(0x40U + source.rank));
            std::copy(
                coordinate.begin(),
                coordinate.end(),
                source.source.coordinate_sha256);
        }
        input.conformer_source_count = conformer_sources.size();
        input.conformer_sources = conformer_sources.data();
        assert(bg_docking_fixed64_allocation_output_v1_init(&output) ==
               BG_STATUS_OK);
        output.row_capacity = rows.size();
        output.rows = rows.data();
        assert(bg_docking_fixed64_allocation_v1_build(&input, &output) ==
               BG_STATUS_OK);
        for (std::size_t slot = 24; slot < 44; ++slot) {
            assert(rows[slot].status ==
                   BG_DOCKING_FIXED64_ALLOCATION_ROW_READY);
        }
    }

    Allocation(const Allocation &) = delete;
    Allocation &operator=(const Allocation &) = delete;
    Allocation(Allocation &&) = delete;
    Allocation &operator=(Allocation &&) = delete;
};

Allocation make_allocation(const std::array<uint8_t, 32> &coordinate) {
    return Allocation(coordinate);
}

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

struct Placement final {
    std::array<double, kAtoms> x{};
    std::array<double, kAtoms> y{};
    std::array<double, kAtoms> z{};
    bg_docking_fixed64_indexed_so3_output_v1 output{};
};

bg_docking_fixed64_indexed_so3_input_v1 make_input(
    const Allocation &allocation,
    const double *x,
    const double *y,
    const double *z,
    std::size_t count,
    uint32_t slot_index = 24) {
    bg_docking_fixed64_indexed_so3_input_v1 input{};
    assert(bg_docking_fixed64_indexed_so3_input_v1_init(&input) ==
           BG_STATUS_OK);
    std::copy(
        std::begin(allocation.output.inventory_sha256),
        std::end(allocation.output.inventory_sha256),
        input.allocation_inventory_sha256);
    std::copy(
        std::begin(allocation.output.allocation_receipt_sha256),
        std::end(allocation.output.allocation_receipt_sha256),
        input.allocation_receipt_sha256);
    input.allocation_row_count = allocation.rows.size();
    input.allocation_rows = allocation.rows.data();
    input.slot_index = slot_index;
    const auto &row = allocation.rows[slot_index];
    std::copy(
        std::begin(row.generation_parent_receipt_sha256),
        std::end(row.generation_parent_receipt_sha256),
        input.source.receipt_sha256);
    std::copy(
        std::begin(row.generation_parent_proposal_sha256),
        std::end(row.generation_parent_proposal_sha256),
        input.source.proposal_sha256);
    std::copy(
        std::begin(row.generation_parent_coordinate_sha256),
        std::end(row.generation_parent_coordinate_sha256),
        input.source.coordinate_sha256);
    input.ligand_atom_count = count;
    input.source_x_angstrom = x;
    input.source_y_angstrom = y;
    input.source_z_angstrom = z;
    input.pocket_center_angstrom[0] = 4.0;
    input.pocket_center_angstrom[1] = -3.0;
    input.pocket_center_angstrom[2] = 8.0;
    input.pocket_normal[2] = 2.0;
    return input;
}

Placement place(
    const bg_context *context,
    const bg_docking_fixed64_indexed_so3_input_v1 &input) {
    Placement value{};
    assert(bg_docking_fixed64_indexed_so3_output_v1_init(&value.output) ==
           BG_STATUS_OK);
    value.output.coordinate_capacity = value.x.size();
    value.output.x_angstrom = value.x.data();
    value.output.y_angstrom = value.y.data();
    value.output.z_angstrom = value.z.data();
    assert(bg_docking_fixed64_indexed_so3_v1_place(
               context, &input, &value.output) == BG_STATUS_OK);
    return value;
}

void assert_placed(
    const Placement &value,
    bg_backend backend,
    uint32_t slot_index) {
    const bool independent = slot_index < 36;
    const uint32_t expected_sequence = independent
        ? slot_index - 24U
        : slot_index - 36U;
    assert(value.output.slot_index == slot_index);
    assert(value.output.lane ==
           (independent
                ? BG_DOCKING_FIXED64_LANE_DETERMINISTIC_INDEPENDENT_SO3
                : BG_DOCKING_FIXED64_LANE_TRUE_CONFORMER_INDEPENDENT_SO3));
    assert(value.output.status == BG_DOCKING_FIXED64_INDEXED_SO3_PLACED);
    assert(value.output.failure_code ==
           BG_DOCKING_FIXED64_INDEXED_SO3_FAILURE_NONE);
    assert(value.output.backend == backend);
    assert(value.output.accepted_sequence_index == expected_sequence);
    assert(value.output.raw_sequence_index >= expected_sequence);
    assert(value.output.ligand_atom_count == kAtoms);
    assert(value.output.coordinates_written == 1);
    assert(value.output.source_identity_verified == 1);
    assert(value.output.allocation_identity_verified == 1);
    assert(value.output.result_dependent_input_consumed == 0);
    assert(value.output.denominator_preserved == 1);
    assert(value.output.molecular_execution_authorized == 0);
    assert(value.output.reservation_authorized == 0);
    assert(value.output.benchmark_execution_authorized == 0);
    assert(value.output.production_claim_authorized == 0);
    assert(digest_present(value.output.source_seed_sha256));
    assert(digest_present(value.output.output_coordinate_sha256));
    assert(digest_present(value.output.placement_receipt_sha256));
    const double center_x =
        std::accumulate(value.x.begin(), value.x.end(), 0.0) / kAtoms;
    const double center_y =
        std::accumulate(value.y.begin(), value.y.end(), 0.0) / kAtoms;
    const double center_z =
        std::accumulate(value.z.begin(), value.z.end(), 0.0) / kAtoms;
    assert(std::abs(center_x - 4.0) < 2.0e-9);
    assert(std::abs(center_y + 3.0) < 2.0e-9);
    assert(std::abs(center_z - 8.0) < 2.0e-9);
}

void test_backend_parity_and_repeat() {
    const std::array<double, kAtoms> x = {-0.0, 1.0, 0.0, 0.0};
    const std::array<double, kAtoms> y = {0.0, 0.0, 1.0, 0.0};
    const std::array<double, kAtoms> z = {0.0, 0.0, 0.0, 1.0};
    const Allocation allocation = make_allocation(kSourceCoordinateSha256);
    bg_context *cpp = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    bg_context *rust = make_context(BG_BACKEND_RUST_CPU);
    assert(cpp != nullptr && rust != nullptr);
    bg_context *hip_safe = make_context(BG_BACKEND_HIP_SAFE);
    bg_context *hip_fast = make_context(BG_BACKEND_HIP_FAST);
    for (uint32_t slot = 24; slot < 44; ++slot) {
        const auto input = make_input(
            allocation, x.data(), y.data(), z.data(), x.size(), slot);
        const Placement cpp_first = place(cpp, input);
        const Placement cpp_repeat = place(cpp, input);
        const Placement rust_first = place(rust, input);
        const Placement rust_repeat = place(rust, input);
        assert_placed(cpp_first, BG_BACKEND_CPP_CPU_REFERENCE, slot);
        assert_placed(rust_first, BG_BACKEND_RUST_CPU, slot);
        assert(cpp_first.x == cpp_repeat.x);
        assert(cpp_first.y == cpp_repeat.y);
        assert(cpp_first.z == cpp_repeat.z);
        assert(rust_first.x == rust_repeat.x);
        assert(rust_first.y == rust_repeat.y);
        assert(rust_first.z == rust_repeat.z);
        assert(std::memcmp(
                   cpp_first.output.source_seed_sha256,
                   rust_first.output.source_seed_sha256,
                   32) == 0);
        for (std::size_t atom = 0; atom < kAtoms; ++atom) {
            assert(std::abs(cpp_first.x[atom] - rust_first.x[atom]) < 2.0e-12);
            assert(std::abs(cpp_first.y[atom] - rust_first.y[atom]) < 2.0e-12);
            assert(std::abs(cpp_first.z[atom] - rust_first.z[atom]) < 2.0e-12);
        }
        for (const auto &[backend, hip] :
             {std::pair{BG_BACKEND_HIP_SAFE, hip_safe},
              std::pair{BG_BACKEND_HIP_FAST, hip_fast}}) {
            if (hip == nullptr) continue;
            const Placement hip_first = place(hip, input);
            const Placement hip_repeat = place(hip, input);
            assert_placed(hip_first, backend, slot);
            assert(hip_first.x == hip_repeat.x);
            assert(hip_first.y == hip_repeat.y);
            assert(hip_first.z == hip_repeat.z);
            assert(std::memcmp(
                       hip_first.output.source_seed_sha256,
                       rust_first.output.source_seed_sha256,
                       32) == 0);
            for (std::size_t atom = 0; atom < kAtoms; ++atom) {
                assert(std::abs(hip_first.x[atom] - rust_first.x[atom]) < 2.0e-9);
                assert(std::abs(hip_first.y[atom] - rust_first.y[atom]) < 2.0e-9);
                assert(std::abs(hip_first.z[atom] - rust_first.z[atom]) < 2.0e-9);
            }
        }
    }
    if (hip_safe != nullptr) bg_context_destroy(hip_safe);
    if (hip_fast != nullptr) bg_context_destroy(hip_fast);
    bg_context_destroy(cpp);
    bg_context_destroy(rust);
}

void test_typed_degenerate_source_preserves_coordinate_channels() {
    const std::array<double, 2> source_x = {1.0, 1.0};
    const std::array<double, 2> source_y = {1.0, 1.0};
    const std::array<double, 2> source_z = {1.0, 1.0};
    const Allocation allocation = make_allocation(kDegenerateCoordinateSha256);
    const auto input = make_input(
        allocation,
        source_x.data(),
        source_y.data(),
        source_z.data(),
        source_x.size());
    bg_context *context = make_context(BG_BACKEND_RUST_CPU);
    assert(context != nullptr);
    std::array<double, 2> x = {91.0, 92.0};
    std::array<double, 2> y = {93.0, 94.0};
    std::array<double, 2> z = {95.0, 96.0};
    const auto x_before = x;
    const auto y_before = y;
    const auto z_before = z;
    bg_docking_fixed64_indexed_so3_output_v1 output{};
    assert(bg_docking_fixed64_indexed_so3_output_v1_init(&output) ==
           BG_STATUS_OK);
    output.coordinate_capacity = x.size();
    output.x_angstrom = x.data();
    output.y_angstrom = y.data();
    output.z_angstrom = z.data();
    assert(bg_docking_fixed64_indexed_so3_v1_place(
               context, &input, &output) == BG_STATUS_OK);
    assert(output.status == BG_DOCKING_FIXED64_INDEXED_SO3_TYPED_FAILURE);
    assert(output.failure_code ==
           BG_DOCKING_FIXED64_INDEXED_SO3_FAILURE_DEGENERATE_SOURCE_GEOMETRY);
    assert(output.coordinates_written == 0);
    assert(x == x_before && y == y_before && z == z_before);
    assert(digest_present(output.placement_receipt_sha256));
    assert(!digest_present(output.output_coordinate_sha256));
    bg_context_destroy(context);
}

void test_invalid_snapshot_and_capacity_are_transactional() {
    const std::array<double, kAtoms> source_x = {0.0, 1.0, 0.0, 0.0};
    const std::array<double, kAtoms> source_y = {0.0, 0.0, 1.0, 0.0};
    const std::array<double, kAtoms> source_z = {0.0, 0.0, 0.0, 1.0};
    const Allocation allocation = make_allocation(kSourceCoordinateSha256);
    auto input = make_input(
        allocation,
        source_x.data(),
        source_y.data(),
        source_z.data(),
        source_x.size());
    bg_context *context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    assert(context != nullptr);
    Placement storage{};
    std::fill(storage.x.begin(), storage.x.end(), 31.0);
    std::fill(storage.y.begin(), storage.y.end(), 32.0);
    std::fill(storage.z.begin(), storage.z.end(), 33.0);
    assert(bg_docking_fixed64_indexed_so3_output_v1_init(&storage.output) ==
           BG_STATUS_OK);
    storage.output.coordinate_capacity = storage.x.size();
    storage.output.x_angstrom = storage.x.data();
    storage.output.y_angstrom = storage.y.data();
    storage.output.z_angstrom = storage.z.data();
    storage.output.slot_index = 61;
    std::fill(
        std::begin(storage.output.placement_receipt_sha256),
        std::end(storage.output.placement_receipt_sha256),
        UINT8_C(0x77));
    const auto x_before = storage.x;
    const auto y_before = storage.y;
    const auto z_before = storage.z;
    const auto output_before = object_bytes(storage.output);
    input.allocation_receipt_sha256[0] ^= UINT8_C(1);
    assert(bg_docking_fixed64_indexed_so3_v1_place(
               context, &input, &storage.output) == BG_STATUS_INVALID_ARGUMENT);
    assert(storage.x == x_before && storage.y == y_before && storage.z == z_before);
    assert(object_bytes(storage.output) == output_before);

    input = make_input(
        allocation,
        source_x.data(),
        source_y.data(),
        source_z.data(),
        source_x.size());
    input.source.receipt_sha256[0] ^= UINT8_C(1);
    const auto source_crosswire_before = object_bytes(storage.output);
    assert(bg_docking_fixed64_indexed_so3_v1_place(
               context, &input, &storage.output) == BG_STATUS_INVALID_ARGUMENT);
    assert(storage.x == x_before && storage.y == y_before && storage.z == z_before);
    assert(object_bytes(storage.output) == source_crosswire_before);

    input = make_input(
        allocation,
        source_x.data(),
        source_y.data(),
        source_z.data(),
        source_x.size());
    storage.output.coordinate_capacity = kAtoms - 1U;
    const auto small_before = object_bytes(storage.output);
    assert(bg_docking_fixed64_indexed_so3_v1_place(
               context, &input, &storage.output) == BG_STATUS_BUFFER_TOO_SMALL);
    assert(storage.x == x_before && storage.y == y_before && storage.z == z_before);
    assert(object_bytes(storage.output) == small_before);

    storage.output.coordinate_capacity = kAtoms;
    storage.output.x_angstrom = reinterpret_cast<double *>(context);
    const auto context_alias_before = object_bytes(storage.output);
    assert(bg_docking_fixed64_indexed_so3_v1_place(
               context, &input, &storage.output) == BG_STATUS_INVALID_ARGUMENT);
    assert(storage.y == y_before && storage.z == z_before);
    assert(object_bytes(storage.output) == context_alias_before);
    bg_context_destroy(context);
}

}  // namespace

int main() {
    test_backend_parity_and_repeat();
    test_typed_degenerate_source_preserves_coordinate_channels();
    test_invalid_snapshot_and_capacity_are_transactional();
    return 0;
}
