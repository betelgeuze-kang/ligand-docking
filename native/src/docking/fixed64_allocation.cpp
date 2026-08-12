#include "../dynamics/sha256.hpp"
#include "../internal.hpp"
#include "../rust/provider.h"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <iterator>
#include <limits>
#include <utility>

namespace betelgeuze::native::docking::fixed64_allocation {
namespace {

using dynamics::Sha256;

constexpr std::size_t kCandidateCount =
    BG_DOCKING_FIXED64_CANDIDATE_COUNT;
constexpr std::size_t kFeatureKindCount =
    BG_DOCKING_FIXED64_FEATURE_KIND_COUNT;
constexpr std::size_t kMaximumFeaturesPerKind = 256;
constexpr std::size_t kMaximumAtomicFeatures =
    kFeatureKindCount * kMaximumFeaturesPerKind;
constexpr std::array<uint8_t, 8> kTrueConformerRanks = {
    UINT8_C(2), UINT8_C(3), UINT8_C(4), UINT8_C(5),
    UINT8_C(6), UINT8_C(7), UINT8_C(8), UINT8_C(2),
};
constexpr std::array<uint32_t, 4> kRetainedSourceIndices = {
    UINT32_C(36), UINT32_C(45), UINT32_C(54), UINT32_C(63)};
constexpr char kProfileId[] =
    "betelgeuze.engine_v2_global_orientation_fixed_mixed64/1.0.0";
constexpr char kAllocationSchemaId[] =
    "betelgeuze.engine_v2_global_orientation_fixed_mixed64_native_allocation/1.1.0";
constexpr char kSlotSchemaId[] =
    "betelgeuze.engine_v2_global_orientation_fixed_mixed64_native_slot/1.1.0";

struct MemoryRange final {
    uintptr_t begin = 0;
    uintptr_t end = 0;
};

class CanonicalHash final {
  public:
    explicit CanonicalHash(const char *domain) noexcept { string(domain); }

    void byte(uint8_t value) noexcept { hash_.update(&value, 1); }
    void boolean(bool value) noexcept { byte(value ? UINT8_C(1) : UINT8_C(0)); }

    void u32(uint32_t value) noexcept {
        std::array<uint8_t, 4> bytes{};
        for (std::size_t index = 0; index < bytes.size(); ++index) {
            bytes[bytes.size() - 1U - index] = static_cast<uint8_t>(
                value >> static_cast<uint32_t>(index * 8U));
        }
        hash_.update(bytes.data(), bytes.size());
    }

    void u64(uint64_t value) noexcept {
        std::array<uint8_t, 8> bytes{};
        for (std::size_t index = 0; index < bytes.size(); ++index) {
            bytes[bytes.size() - 1U - index] = static_cast<uint8_t>(
                value >> static_cast<uint32_t>(index * 8U));
        }
        hash_.update(bytes.data(), bytes.size());
    }

    void size(std::size_t value) noexcept {
        u64(static_cast<uint64_t>(value));
    }

    void bytes(const uint8_t *values, std::size_t count) noexcept {
        size(count);
        hash_.update(values, count);
    }

    void string(const char *value) noexcept {
        const auto count = std::strlen(value);
        bytes(reinterpret_cast<const uint8_t *>(value), count);
    }

    void digest(const uint8_t (&value)[32]) noexcept {
        hash_.update(value, 32);
    }

    void digest(const std::array<uint8_t, 32> &value) noexcept {
        hash_.update(value.data(), value.size());
    }

    [[nodiscard]] std::array<uint8_t, 32> finish() noexcept {
        return hash_.finish();
    }

  private:
    Sha256 hash_;
};

template <typename Type>
[[nodiscard]] bool make_range(
    const Type *pointer,
    std::size_t count,
    MemoryRange *output) noexcept {
    if (output == nullptr) {
        return false;
    }
    if (pointer == nullptr || count == 0) {
        *output = {};
        return true;
    }
    if (count > std::numeric_limits<std::size_t>::max() / sizeof(Type)) {
        return false;
    }
    const std::size_t bytes = count * sizeof(Type);
    const auto begin = reinterpret_cast<uintptr_t>(pointer);
    if (begin > std::numeric_limits<uintptr_t>::max() - bytes) {
        return false;
    }
    *output = {begin, begin + bytes};
    return true;
}

[[nodiscard]] bool overlaps(MemoryRange left, MemoryRange right) noexcept {
    return left.begin != left.end && right.begin != right.end &&
           left.begin < right.end && right.begin < left.end;
}

template <typename Type, std::size_t Count>
[[nodiscard]] bool zero_array(const Type (&values)[Count]) noexcept {
    return std::all_of(std::begin(values), std::end(values), [](Type value) {
        return value == Type{};
    });
}

[[nodiscard]] bool valid_feature_kind(
    bg_docking_fixed64_feature_kind value) noexcept {
    return value >= BG_DOCKING_FIXED64_FEATURE_LIGAND_DONOR &&
           value <= BG_DOCKING_FIXED64_FEATURE_POCKET_SHAPE_AXIS;
}

[[nodiscard]] int digest_compare(
    const uint8_t (&left)[32],
    const uint8_t (&right)[32]) noexcept {
    return std::memcmp(left, right, 32);
}

[[nodiscard]] bool digest_present(const uint8_t (&digest)[32]) noexcept {
    return std::any_of(
        std::begin(digest), std::end(digest),
        [](uint8_t value) { return value != UINT8_C(0); });
}

[[nodiscard]] bool valid_source(
    const bg_docking_fixed64_source_evidence_v1 &source) noexcept {
    return reserved_is_zero(source.reserved) &&
           digest_present(source.receipt_sha256) &&
           digest_present(source.proposal_sha256) &&
           digest_present(source.coordinate_sha256);
}

[[nodiscard]] bool valid_exact_source(
    const bg_docking_fixed64_exact_source_evidence_v1 &source) noexcept {
    return reserved_is_zero(source.reserved) &&
           digest_present(source.source_receipt_sha256) &&
           digest_present(source.proposal_sha256) &&
           digest_present(source.ligand_coordinate_sha256) &&
           digest_present(source.receptor_coordinate_sha256) &&
           digest_present(source.prepared_ligand_topology_sha256) &&
           digest_present(source.prepared_receptor_topology_sha256) &&
           digest_present(source.ligand_vdw_radii_sha256) &&
           digest_present(source.ligand_heavy_atom_mask_sha256) &&
           digest_present(source.receptor_vdw_radii_sha256);
}

[[nodiscard]] bool source_receipts_unique(
    const bg_docking_fixed64_indexed_source_evidence_v1 *values,
    std::size_t count) noexcept {
    for (std::size_t left = 0; left < count; ++left) {
        for (std::size_t right = left + 1; right < count; ++right) {
            if (digest_compare(
                    values[left].source.receipt_sha256,
                    values[right].source.receipt_sha256) == 0) {
                return false;
            }
        }
    }
    return true;
}

[[nodiscard]] bool source_receipts_unique(
    const bg_docking_fixed64_conformer_source_evidence_v1 *values,
    std::size_t count) noexcept {
    for (std::size_t left = 0; left < count; ++left) {
        for (std::size_t right = left + 1; right < count; ++right) {
            if (digest_compare(
                    values[left].source.receipt_sha256,
                    values[right].source.receipt_sha256) == 0) {
                return false;
            }
        }
    }
    return true;
}

[[nodiscard]] bool retained_index_allowed(uint32_t value) noexcept {
    return std::find(
               kRetainedSourceIndices.begin(),
               kRetainedSourceIndices.end(),
               value) != kRetainedSourceIndices.end();
}

[[nodiscard]] bg_status validate_input(
    const bg_docking_fixed64_allocation_input_v1 &input) noexcept {
    bg_status status = validate_descriptor_header(
        input.struct_size,
        sizeof(input),
        input.abi_version,
        "fixed64 allocation input size does not match ABI v1",
        "fixed64 allocation input ABI version does not match");
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (!reserved_is_zero(input.reserved) ||
        !valid_exact_source(input.exact_v11_source)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 allocation exact-source identities must be present and reserved fields zero");
    }
    if (input.atomic_feature_count > kMaximumAtomicFeatures ||
        input.v7_control_source_count > 24 ||
        input.conformer_source_count > 7 ||
        input.retained_source_count > 4) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "fixed64 allocation inventory exceeds frozen capacities");
    }
    const auto atomic_count =
        static_cast<std::size_t>(input.atomic_feature_count);
    const auto v7_count =
        static_cast<std::size_t>(input.v7_control_source_count);
    const auto conformer_count =
        static_cast<std::size_t>(input.conformer_source_count);
    const auto retained_count =
        static_cast<std::size_t>(input.retained_source_count);
    if ((atomic_count != 0 &&
         (input.atomic_features == nullptr ||
          !pointer_is_aligned(input.atomic_features))) ||
        (v7_count != 0 &&
         (input.v7_control_sources == nullptr ||
          !pointer_is_aligned(input.v7_control_sources))) ||
        (conformer_count != 0 &&
         (input.conformer_sources == nullptr ||
          !pointer_is_aligned(input.conformer_sources))) ||
        (retained_count != 0 &&
         (input.retained_sources == nullptr ||
          !pointer_is_aligned(input.retained_sources)))) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 allocation inventory channel is null or misaligned");
    }

    std::array<std::size_t, kFeatureKindCount> per_kind{};
    for (std::size_t index = 0; index < atomic_count; ++index) {
        const auto &row = input.atomic_features[index];
        if (!valid_feature_kind(row.kind) || row.reserved0 != 0 ||
            !digest_present(row.receipt_sha256) ||
            !reserved_is_zero(row.reserved)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 allocation atomic feature row is invalid");
        }
        const auto kind = static_cast<std::size_t>(row.kind);
        ++per_kind[kind];
        if (per_kind[kind] > kMaximumFeaturesPerKind) {
            return fail(
                BG_STATUS_CAPACITY_OVERFLOW,
                "fixed64 allocation per-kind feature capacity exceeded");
        }
        if (index != 0) {
            const auto &previous = input.atomic_features[index - 1U];
            if (previous.kind > row.kind ||
                (previous.kind == row.kind &&
                 digest_compare(
                     previous.receipt_sha256, row.receipt_sha256) >= 0)) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "fixed64 allocation atomic features are not unique canonical rows");
            }
        }
    }

    for (std::size_t index = 0; index < v7_count; ++index) {
        const auto &row = input.v7_control_sources[index];
        if (row.source_index >= 24 || row.reserved0 != 0 ||
            !reserved_is_zero(row.reserved) || !valid_source(row.source) ||
            (index != 0 &&
             input.v7_control_sources[index - 1U].source_index >=
                 row.source_index)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 allocation V7 control source rows are invalid");
        }
    }
    if (!source_receipts_unique(input.v7_control_sources, v7_count)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 allocation V7 control receipts are not unique");
    }

    for (std::size_t index = 0; index < conformer_count; ++index) {
        const auto &row = input.conformer_sources[index];
        if (row.rank < UINT8_C(2) || row.rank > UINT8_C(8) ||
            !zero_array(row.reserved0) || !reserved_is_zero(row.reserved) ||
            !valid_source(row.source) ||
            (index != 0 &&
             input.conformer_sources[index - 1U].rank >= row.rank)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 allocation conformer source rows are invalid");
        }
    }
    if (!source_receipts_unique(input.conformer_sources, conformer_count)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 allocation conformer receipts are not unique");
    }

    for (std::size_t index = 0; index < retained_count; ++index) {
        const auto &row = input.retained_sources[index];
        if (!retained_index_allowed(row.source_index) || row.reserved0 != 0 ||
            !reserved_is_zero(row.reserved) || !valid_source(row.source) ||
            (index != 0 &&
             input.retained_sources[index - 1U].source_index >=
                 row.source_index)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 allocation retained source rows are invalid");
        }
    }
    if (!source_receipts_unique(input.retained_sources, retained_count)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 allocation retained receipts are not unique");
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status validate_output(
    const bg_docking_fixed64_allocation_input_v1 &input,
    const bg_docking_fixed64_allocation_output_v1 &output) noexcept {
    bg_status status = validate_descriptor_header(
        output.struct_size,
        sizeof(output),
        output.abi_version,
        "fixed64 allocation output size does not match ABI v1",
        "fixed64 allocation output ABI version does not match");
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (output.row_capacity < kCandidateCount || output.rows == nullptr ||
        !pointer_is_aligned(output.rows)) {
        return fail(
            BG_STATUS_BUFFER_TOO_SMALL,
            "fixed64 allocation output requires 64 aligned rows");
    }
    if (output.reserved0 != 0 || !reserved_is_zero(output.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 allocation output reserved fields must be zero");
    }

    MemoryRange input_descriptor{};
    MemoryRange atomic_features{};
    MemoryRange v7_sources{};
    MemoryRange conformer_sources{};
    MemoryRange retained_sources{};
    MemoryRange output_descriptor{};
    MemoryRange output_rows{};
    if (!make_range(&input, 1, &input_descriptor) ||
        !make_range(
            input.atomic_features,
            static_cast<std::size_t>(input.atomic_feature_count),
            &atomic_features) ||
        !make_range(
            input.v7_control_sources,
            static_cast<std::size_t>(input.v7_control_source_count),
            &v7_sources) ||
        !make_range(
            input.conformer_sources,
            static_cast<std::size_t>(input.conformer_source_count),
            &conformer_sources) ||
        !make_range(
            input.retained_sources,
            static_cast<std::size_t>(input.retained_source_count),
            &retained_sources) ||
        !make_range(&output, 1, &output_descriptor) ||
        !make_range(output.rows, kCandidateCount, &output_rows)) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "fixed64 allocation input or output range overflows");
    }
    const std::array<MemoryRange, 5> inputs = {
        input_descriptor,
        atomic_features,
        v7_sources,
        conformer_sources,
        retained_sources,
    };
    for (std::size_t left = 0; left < inputs.size(); ++left) {
        for (std::size_t right = left + 1; right < inputs.size(); ++right) {
            if (overlaps(inputs[left], inputs[right])) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "fixed64 allocation input channels overlap");
            }
        }
    }
    for (const MemoryRange range : inputs) {
        if (overlaps(output_descriptor, range) || overlaps(output_rows, range)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 allocation output overlaps an input");
        }
    }
    if (overlaps(output_descriptor, output_rows)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 allocation output rows overlap their descriptor");
    }
    return BG_STATUS_OK;
}

[[nodiscard]] const bg_docking_fixed64_indexed_source_evidence_v1 *
indexed_source(
    const bg_docking_fixed64_indexed_source_evidence_v1 *values,
    std::size_t count,
    uint32_t index) noexcept {
    for (std::size_t row = 0; row < count; ++row) {
        if (values[row].source_index == index) {
            return &values[row];
        }
    }
    return nullptr;
}

[[nodiscard]] const bg_docking_fixed64_conformer_source_evidence_v1 *
conformer_source(
    const bg_docking_fixed64_allocation_input_v1 &input,
    uint8_t rank) noexcept {
    const auto count = static_cast<std::size_t>(input.conformer_source_count);
    for (std::size_t row = 0; row < count; ++row) {
        if (input.conformer_sources[row].rank == rank) {
            return &input.conformer_sources[row];
        }
    }
    return nullptr;
}

[[nodiscard]] std::size_t feature_count(
    const bg_docking_fixed64_allocation_input_v1 &input,
    bg_docking_fixed64_feature_kind kind) noexcept {
    std::size_t count = 0;
    for (std::size_t index = 0;
         index < static_cast<std::size_t>(input.atomic_feature_count);
         ++index) {
        if (input.atomic_features[index].kind == kind) {
            ++count;
        }
    }
    return count;
}

[[nodiscard]] const uint8_t *feature_receipt(
    const bg_docking_fixed64_allocation_input_v1 &input,
    bg_docking_fixed64_feature_kind kind,
    std::size_t offset) noexcept {
    const std::size_t count = feature_count(input, kind);
    if (count == 0) {
        return nullptr;
    }
    std::size_t selected = offset % count;
    for (std::size_t index = 0;
         index < static_cast<std::size_t>(input.atomic_feature_count);
         ++index) {
        if (input.atomic_features[index].kind != kind) {
            continue;
        }
        if (selected == 0) {
            return input.atomic_features[index].receipt_sha256;
        }
        --selected;
    }
    return nullptr;
}

void add_requirement(
    bg_docking_fixed64_allocation_row_v1 *row,
    bg_docking_fixed64_requirement_kind kind,
    uint32_t value) noexcept {
    const std::size_t index = row->requirement_count;
    row->requirements[index].kind = kind;
    row->requirements[index].value = value;
    ++row->requirement_count;
}

void add_missing(
    bg_docking_fixed64_allocation_row_v1 *row,
    bg_docking_fixed64_missing_feature_kind kind,
    uint32_t value) noexcept {
    const std::size_t index = row->missing_feature_count;
    row->missing_features[index].kind = kind;
    row->missing_features[index].value = value;
    ++row->missing_feature_count;
}

void add_selected_receipt(
    bg_docking_fixed64_allocation_row_v1 *row,
    const uint8_t *receipt) noexcept {
    const std::size_t index = row->selected_source_receipt_count;
    std::memcpy(row->selected_source_receipt_sha256[index], receipt, 32);
    ++row->selected_source_receipt_count;
}

void set_parent(
    bg_docking_fixed64_allocation_row_v1 *row,
    const uint8_t *receipt_sha256,
    const uint8_t *proposal_sha256,
    const uint8_t *coordinate_sha256,
    bg_docking_fixed64_parent_role role) noexcept {
    row->generation_parent_role = role;
    std::memcpy(row->generation_parent_receipt_sha256, receipt_sha256, 32);
    std::memcpy(row->generation_parent_proposal_sha256, proposal_sha256, 32);
    std::memcpy(row->generation_parent_coordinate_sha256, coordinate_sha256, 32);
}

void set_exact_parent(
    const bg_docking_fixed64_allocation_input_v1 &input,
    bg_docking_fixed64_allocation_row_v1 *row) noexcept {
    set_parent(
        row,
        input.exact_v11_source.source_receipt_sha256,
        input.exact_v11_source.proposal_sha256,
        input.exact_v11_source.ligand_coordinate_sha256,
        BG_DOCKING_FIXED64_PARENT_GENERATOR_INPUT);
}

void select_feature_pair(
    const bg_docking_fixed64_allocation_input_v1 &input,
    bg_docking_fixed64_allocation_row_v1 *row,
    bg_docking_fixed64_feature_kind first,
    bg_docking_fixed64_feature_kind second,
    bg_docking_fixed64_missing_feature_kind missing_first,
    bg_docking_fixed64_missing_feature_kind missing_second) noexcept {
    add_requirement(
        row,
        BG_DOCKING_FIXED64_REQUIREMENT_FEATURE,
        static_cast<uint32_t>(first));
    add_requirement(
        row,
        BG_DOCKING_FIXED64_REQUIREMENT_FEATURE,
        static_cast<uint32_t>(second));
    if (const uint8_t *receipt =
            feature_receipt(input, first, row->lane_offset)) {
        add_selected_receipt(row, receipt);
    } else {
        add_missing(row, missing_first, 0);
    }
    if (const uint8_t *receipt =
            feature_receipt(input, second, row->lane_offset)) {
        add_selected_receipt(row, receipt);
    } else {
        add_missing(row, missing_second, 0);
    }
    set_exact_parent(input, row);
}

[[nodiscard]] std::pair<bg_docking_fixed64_lane, uint32_t> lane_for_slot(
    std::size_t slot) noexcept {
    if (slot < 8) {
        return {BG_DOCKING_FIXED64_LANE_POCKET_CENTERED_CONTROLS,
                static_cast<uint32_t>(slot)};
    }
    if (slot < 24) {
        return {BG_DOCKING_FIXED64_LANE_UNIFORM_SOURCE_CONTROLS,
                static_cast<uint32_t>(slot - 8)};
    }
    if (slot < 36) {
        return {BG_DOCKING_FIXED64_LANE_DETERMINISTIC_INDEPENDENT_SO3,
                static_cast<uint32_t>(slot - 24)};
    }
    if (slot < 44) {
        return {BG_DOCKING_FIXED64_LANE_TRUE_CONFORMER_INDEPENDENT_SO3,
                static_cast<uint32_t>(slot - 36)};
    }
    if (slot < 48) {
        return {BG_DOCKING_FIXED64_LANE_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR,
                static_cast<uint32_t>(slot - 44)};
    }
    if (slot < 52) {
        return {BG_DOCKING_FIXED64_LANE_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR,
                static_cast<uint32_t>(slot - 48)};
    }
    if (slot < 56) {
        return {BG_DOCKING_FIXED64_LANE_COMPLEMENTARY_CHARGE,
                static_cast<uint32_t>(slot - 52)};
    }
    if (slot < 58) {
        return {BG_DOCKING_FIXED64_LANE_AROMATIC_PLANE,
                static_cast<uint32_t>(slot - 56)};
    }
    if (slot < 60) {
        return {BG_DOCKING_FIXED64_LANE_PRINCIPAL_AXIS_SHAPE,
                static_cast<uint32_t>(slot - 58)};
    }
    return {BG_DOCKING_FIXED64_LANE_PAIRED_RETAINED_CONTROLS,
            static_cast<uint32_t>(slot - 60)};
}

[[nodiscard]] bg_docking_fixed64_anchor_kind anchor_for_lane(
    bg_docking_fixed64_lane lane) noexcept {
    switch (lane) {
        case BG_DOCKING_FIXED64_LANE_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR:
            return BG_DOCKING_FIXED64_ANCHOR_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR;
        case BG_DOCKING_FIXED64_LANE_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR:
            return BG_DOCKING_FIXED64_ANCHOR_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR;
        case BG_DOCKING_FIXED64_LANE_COMPLEMENTARY_CHARGE:
            return BG_DOCKING_FIXED64_ANCHOR_COMPLEMENTARY_CHARGE;
        case BG_DOCKING_FIXED64_LANE_AROMATIC_PLANE:
            return BG_DOCKING_FIXED64_ANCHOR_AROMATIC_PLANE;
        case BG_DOCKING_FIXED64_LANE_PRINCIPAL_AXIS_SHAPE:
            return BG_DOCKING_FIXED64_ANCHOR_PRINCIPAL_AXIS_SHAPE;
        default:
            return BG_DOCKING_FIXED64_ANCHOR_NONE;
    }
}

void hash_requirement(
    CanonicalHash *hash,
    const bg_docking_fixed64_requirement_v1 &value) noexcept {
    hash->byte(static_cast<uint8_t>(value.kind));
    if (value.kind == BG_DOCKING_FIXED64_REQUIREMENT_V7_CONTROL_SOURCE ||
        value.kind == BG_DOCKING_FIXED64_REQUIREMENT_TRUE_CONFORMER_RANK ||
        value.kind == BG_DOCKING_FIXED64_REQUIREMENT_FEATURE) {
        hash->byte(static_cast<uint8_t>(value.value));
    } else if (value.kind == BG_DOCKING_FIXED64_REQUIREMENT_RETAINED_SOURCE) {
        hash->u32(value.value);
    }
}

void hash_missing(
    CanonicalHash *hash,
    const bg_docking_fixed64_missing_feature_v1 &value) noexcept {
    hash->byte(static_cast<uint8_t>(value.kind));
    if (value.kind == BG_DOCKING_FIXED64_MISSING_V7_CONTROL_SOURCE ||
        value.kind == BG_DOCKING_FIXED64_MISSING_TRUE_CONFORMER) {
        hash->byte(static_cast<uint8_t>(value.value));
    } else if (value.kind == BG_DOCKING_FIXED64_MISSING_RETAINED_SOURCE) {
        hash->u32(value.value);
    }
}

[[nodiscard]] std::array<uint8_t, 32> slot_sha256(
    const bg_docking_fixed64_allocation_row_v1 &row) noexcept {
    CanonicalHash hash("betelgeuze.fixed64_slot/native-v1");
    hash.string(kSlotSchemaId);
    hash.size(row.slot_index);
    hash.byte(static_cast<uint8_t>(row.lane));
    hash.size(row.lane_offset);
    hash.boolean(row.declared_anchor_kind != BG_DOCKING_FIXED64_ANCHOR_NONE);
    if (row.declared_anchor_kind != BG_DOCKING_FIXED64_ANCHOR_NONE) {
        hash.byte(static_cast<uint8_t>(row.declared_anchor_kind - 1));
    }
    hash.size(row.requirement_count);
    for (std::size_t index = 0; index < row.requirement_count; ++index) {
        hash_requirement(&hash, row.requirements[index]);
    }
    hash.size(row.missing_feature_count);
    for (std::size_t index = 0; index < row.missing_feature_count; ++index) {
        hash_missing(&hash, row.missing_features[index]);
    }
    hash.boolean(row.v7_control_source_index >= 0);
    if (row.v7_control_source_index >= 0) {
        hash.u32(static_cast<uint32_t>(row.v7_control_source_index));
    }
    hash.boolean(row.so3_sequence_index >= 0);
    if (row.so3_sequence_index >= 0) {
        hash.byte(static_cast<uint8_t>(row.so3_sequence_index));
    }
    hash.boolean(row.true_conformer_rank >= 0);
    if (row.true_conformer_rank >= 0) {
        hash.byte(static_cast<uint8_t>(row.true_conformer_rank));
    }
    hash.boolean(row.retained_source_index >= 0);
    if (row.retained_source_index >= 0) {
        hash.u32(static_cast<uint32_t>(row.retained_source_index));
    }
    hash.size(row.selected_source_receipt_count);
    for (std::size_t index = 0;
         index < row.selected_source_receipt_count;
         ++index) {
        hash.digest(row.selected_source_receipt_sha256[index]);
    }
    hash.boolean(row.generation_parent_role != BG_DOCKING_FIXED64_PARENT_NONE);
    if (row.generation_parent_role != BG_DOCKING_FIXED64_PARENT_NONE) {
        hash.digest(row.generation_parent_receipt_sha256);
        hash.digest(row.generation_parent_proposal_sha256);
        hash.digest(row.generation_parent_coordinate_sha256);
        hash.byte(static_cast<uint8_t>(row.generation_parent_role - 1));
    }
    hash.boolean(row.generation_eligible != UINT8_C(0));
    hash.boolean(false);
    hash.boolean(false);
    hash.boolean(true);
    return hash.finish();
}

[[nodiscard]] std::array<uint8_t, 32> inventory_sha256(
    const bg_docking_fixed64_allocation_input_v1 &input) noexcept {
    CanonicalHash hash("betelgeuze.fixed64_feature_inventory/native-v1");
    hash.digest(input.exact_v11_source.source_receipt_sha256);
    hash.digest(input.exact_v11_source.proposal_sha256);
    hash.digest(input.exact_v11_source.ligand_coordinate_sha256);
    hash.digest(input.exact_v11_source.receptor_coordinate_sha256);
    hash.digest(input.exact_v11_source.prepared_ligand_topology_sha256);
    hash.digest(input.exact_v11_source.prepared_receptor_topology_sha256);
    hash.digest(input.exact_v11_source.ligand_vdw_radii_sha256);
    hash.digest(input.exact_v11_source.ligand_heavy_atom_mask_sha256);
    hash.digest(input.exact_v11_source.receptor_vdw_radii_sha256);
    hash.size(static_cast<std::size_t>(input.atomic_feature_count));
    for (std::size_t index = 0;
         index < static_cast<std::size_t>(input.atomic_feature_count);
         ++index) {
        hash.byte(static_cast<uint8_t>(input.atomic_features[index].kind));
        hash.digest(input.atomic_features[index].receipt_sha256);
    }
    hash.size(static_cast<std::size_t>(input.v7_control_source_count));
    for (std::size_t index = 0;
         index < static_cast<std::size_t>(input.v7_control_source_count);
         ++index) {
        const auto &row = input.v7_control_sources[index];
        hash.u32(row.source_index);
        hash.digest(row.source.receipt_sha256);
        hash.digest(row.source.proposal_sha256);
        hash.digest(row.source.coordinate_sha256);
    }
    hash.size(static_cast<std::size_t>(input.conformer_source_count));
    for (std::size_t index = 0;
         index < static_cast<std::size_t>(input.conformer_source_count);
         ++index) {
        const auto &row = input.conformer_sources[index];
        hash.byte(row.rank);
        hash.digest(row.source.receipt_sha256);
        hash.digest(row.source.proposal_sha256);
        hash.digest(row.source.coordinate_sha256);
    }
    hash.size(static_cast<std::size_t>(input.retained_source_count));
    for (std::size_t index = 0;
         index < static_cast<std::size_t>(input.retained_source_count);
         ++index) {
        const auto &row = input.retained_sources[index];
        hash.u32(row.source_index);
        hash.digest(row.source.receipt_sha256);
        hash.digest(row.source.proposal_sha256);
        hash.digest(row.source.coordinate_sha256);
    }
    return hash.finish();
}

[[nodiscard]] std::array<uint8_t, 32> allocation_sha256(
    const std::array<uint8_t, 32> &inventory,
    const std::array<bg_docking_fixed64_allocation_row_v1, kCandidateCount>
        &rows) noexcept {
    CanonicalHash hash("betelgeuze.fixed64_allocation/native-v1");
    hash.string(kAllocationSchemaId);
    hash.string(kProfileId);
    hash.digest(inventory);
    hash.size(kCandidateCount);
    for (const auto &row : rows) {
        hash.digest(row.slot_receipt_sha256);
    }
    hash.boolean(false);
    hash.boolean(false);
    hash.boolean(false);
    hash.boolean(true);
    hash.boolean(false);
    return hash.finish();
}

[[nodiscard]] bg_docking_fixed64_allocation_row_v1 build_row(
    const bg_docking_fixed64_allocation_input_v1 &input,
    std::size_t slot) noexcept {
    bg_docking_fixed64_allocation_row_v1 row{};
    row.slot_index = static_cast<uint32_t>(slot);
    const auto [lane, lane_offset] = lane_for_slot(slot);
    row.lane = lane;
    row.lane_offset = lane_offset;
    row.declared_anchor_kind = anchor_for_lane(lane);
    row.generation_parent_role = BG_DOCKING_FIXED64_PARENT_NONE;
    row.v7_control_source_index = -1;
    row.so3_sequence_index = -1;
    row.true_conformer_rank = -1;
    row.retained_source_index = -1;
    row.denominator_preserved = UINT8_C(1);

    const auto v7_count =
        static_cast<std::size_t>(input.v7_control_source_count);
    const auto retained_count =
        static_cast<std::size_t>(input.retained_source_count);
    switch (lane) {
        case BG_DOCKING_FIXED64_LANE_POCKET_CENTERED_CONTROLS:
        case BG_DOCKING_FIXED64_LANE_UNIFORM_SOURCE_CONTROLS: {
            const uint32_t source_index =
                lane == BG_DOCKING_FIXED64_LANE_UNIFORM_SOURCE_CONTROLS
                ? lane_offset + UINT32_C(8)
                : lane_offset;
            row.v7_control_source_index =
                static_cast<int32_t>(source_index);
            add_requirement(
                &row,
                BG_DOCKING_FIXED64_REQUIREMENT_V7_CONTROL_SOURCE,
                source_index);
            const auto *source = indexed_source(
                input.v7_control_sources, v7_count, source_index);
            if (source == nullptr) {
                add_missing(
                    &row,
                    BG_DOCKING_FIXED64_MISSING_V7_CONTROL_SOURCE,
                    source_index);
            } else {
                add_selected_receipt(&row, source->source.receipt_sha256);
                set_parent(
                    &row,
                    source->source.receipt_sha256,
                    source->source.proposal_sha256,
                    source->source.coordinate_sha256,
                    BG_DOCKING_FIXED64_PARENT_EXACT_PASSTHROUGH);
            }
            break;
        }
        case BG_DOCKING_FIXED64_LANE_DETERMINISTIC_INDEPENDENT_SO3:
            row.so3_sequence_index = static_cast<int32_t>(lane_offset);
            set_exact_parent(input, &row);
            break;
        case BG_DOCKING_FIXED64_LANE_TRUE_CONFORMER_INDEPENDENT_SO3: {
            const uint8_t rank = kTrueConformerRanks[lane_offset];
            row.so3_sequence_index = static_cast<int32_t>(lane_offset);
            row.true_conformer_rank = static_cast<int32_t>(rank);
            add_requirement(
                &row,
                BG_DOCKING_FIXED64_REQUIREMENT_TRUE_CONFORMER_RANK,
                rank);
            const auto *source = conformer_source(input, rank);
            if (source == nullptr) {
                add_missing(
                    &row,
                    BG_DOCKING_FIXED64_MISSING_TRUE_CONFORMER,
                    rank);
            } else {
                add_selected_receipt(&row, source->source.receipt_sha256);
                set_parent(
                    &row,
                    source->source.receipt_sha256,
                    source->source.proposal_sha256,
                    source->source.coordinate_sha256,
                    BG_DOCKING_FIXED64_PARENT_GENERATOR_INPUT);
            }
            break;
        }
        case BG_DOCKING_FIXED64_LANE_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR:
            select_feature_pair(
                input,
                &row,
                BG_DOCKING_FIXED64_FEATURE_LIGAND_DONOR,
                BG_DOCKING_FIXED64_FEATURE_RECEPTOR_ACCEPTOR,
                BG_DOCKING_FIXED64_MISSING_LIGAND_DONOR,
                BG_DOCKING_FIXED64_MISSING_RECEPTOR_ACCEPTOR);
            break;
        case BG_DOCKING_FIXED64_LANE_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR:
            select_feature_pair(
                input,
                &row,
                BG_DOCKING_FIXED64_FEATURE_LIGAND_ACCEPTOR,
                BG_DOCKING_FIXED64_FEATURE_RECEPTOR_DONOR,
                BG_DOCKING_FIXED64_MISSING_LIGAND_ACCEPTOR,
                BG_DOCKING_FIXED64_MISSING_RECEPTOR_DONOR);
            break;
        case BG_DOCKING_FIXED64_LANE_COMPLEMENTARY_CHARGE: {
            add_requirement(
                &row,
                BG_DOCKING_FIXED64_REQUIREMENT_COMPLEMENTARY_CHARGE_ANCHOR,
                0);
            constexpr std::array<
                std::pair<bg_docking_fixed64_feature_kind,
                          bg_docking_fixed64_feature_kind>,
                2>
                pairs = {{
                    {BG_DOCKING_FIXED64_FEATURE_LIGAND_POSITIVE_SITE,
                     BG_DOCKING_FIXED64_FEATURE_RECEPTOR_NEGATIVE_SITE},
                    {BG_DOCKING_FIXED64_FEATURE_LIGAND_NEGATIVE_SITE,
                     BG_DOCKING_FIXED64_FEATURE_RECEPTOR_POSITIVE_SITE},
                }};
            std::array<std::size_t, 2> available{};
            std::size_t available_count = 0;
            for (std::size_t index = 0; index < pairs.size(); ++index) {
                if (feature_count(input, pairs[index].first) != 0 &&
                    feature_count(input, pairs[index].second) != 0) {
                    available[available_count++] = index;
                }
            }
            if (available_count == 0) {
                add_missing(
                    &row,
                    BG_DOCKING_FIXED64_MISSING_COMPLEMENTARY_CHARGE_ANCHOR,
                    0);
            } else {
                const auto pair =
                    pairs[available[lane_offset % available_count]];
                add_selected_receipt(
                    &row,
                    feature_receipt(input, pair.first, lane_offset));
                add_selected_receipt(
                    &row,
                    feature_receipt(input, pair.second, lane_offset));
            }
            set_exact_parent(input, &row);
            break;
        }
        case BG_DOCKING_FIXED64_LANE_AROMATIC_PLANE:
            select_feature_pair(
                input,
                &row,
                BG_DOCKING_FIXED64_FEATURE_LIGAND_AROMATIC_PLANE,
                BG_DOCKING_FIXED64_FEATURE_RECEPTOR_AROMATIC_PLANE,
                BG_DOCKING_FIXED64_MISSING_LIGAND_AROMATIC_PLANE,
                BG_DOCKING_FIXED64_MISSING_RECEPTOR_AROMATIC_PLANE);
            break;
        case BG_DOCKING_FIXED64_LANE_PRINCIPAL_AXIS_SHAPE:
            select_feature_pair(
                input,
                &row,
                BG_DOCKING_FIXED64_FEATURE_LIGAND_SHAPE_AXIS,
                BG_DOCKING_FIXED64_FEATURE_POCKET_SHAPE_AXIS,
                BG_DOCKING_FIXED64_MISSING_LIGAND_SHAPE_AXIS,
                BG_DOCKING_FIXED64_MISSING_POCKET_SHAPE_AXIS);
            break;
        case BG_DOCKING_FIXED64_LANE_PAIRED_RETAINED_CONTROLS: {
            const uint32_t source_index = kRetainedSourceIndices[lane_offset];
            row.retained_source_index = static_cast<int32_t>(source_index);
            add_requirement(
                &row,
                BG_DOCKING_FIXED64_REQUIREMENT_RETAINED_SOURCE,
                source_index);
            const auto *source = indexed_source(
                input.retained_sources, retained_count, source_index);
            if (source == nullptr) {
                add_missing(
                    &row,
                    BG_DOCKING_FIXED64_MISSING_RETAINED_SOURCE,
                    source_index);
            } else {
                add_selected_receipt(&row, source->source.receipt_sha256);
                set_parent(
                    &row,
                    source->source.receipt_sha256,
                    source->source.proposal_sha256,
                    source->source.coordinate_sha256,
                    BG_DOCKING_FIXED64_PARENT_EXACT_PASSTHROUGH);
            }
            break;
        }
        default:
            break;
    }
    row.generation_eligible =
        row.missing_feature_count == 0 ? UINT8_C(1) : UINT8_C(0);
    row.status = row.generation_eligible != UINT8_C(0)
        ? BG_DOCKING_FIXED64_ALLOCATION_ROW_READY
        : BG_DOCKING_FIXED64_ALLOCATION_ROW_TYPED_FAILURE;
    const auto receipt = slot_sha256(row);
    std::copy(receipt.begin(), receipt.end(), row.slot_receipt_sha256);
    return row;
}

[[nodiscard]] bg_status verify_rust_parity(
    const bg_docking_fixed64_allocation_input_v1 &input,
    const std::array<bg_docking_fixed64_allocation_row_v1, kCandidateCount>
        &cpp_rows,
    const std::array<uint8_t, 32> &cpp_inventory,
    const std::array<uint8_t, 32> &cpp_allocation,
    uint64_t cpp_ready_count) noexcept {
    std::array<bg_docking_fixed64_allocation_row_v1, kCandidateCount>
        rust_rows{};
    std::array<uint8_t, 32> rust_inventory{};
    std::array<uint8_t, 32> rust_allocation{};
    uint64_t rust_ready_count = 0;
    uint64_t rust_failure_count = 0;
    bg_rust_cpu_error_v1 error{};
    error.struct_size = static_cast<uint32_t>(sizeof(error));
    error.abi_version = BG_RUST_CPU_PROVIDER_ABI_VERSION;
    const int32_t provider_status =
        bg_rust_cpu_docking_fixed64_allocation_v1_build(
            &input,
            rust_rows.data(),
            rust_inventory.data(),
            rust_allocation.data(),
            &rust_ready_count,
            &rust_failure_count,
            &error);
    if (provider_status != BG_STATUS_OK) {
        return fail(
            BG_STATUS_BACKEND_ERROR,
            error.message[0] != '\0'
                ? error.message
                : "Rust fixed64 allocation provider failed");
    }
    const uint64_t cpp_failure_count = kCandidateCount - cpp_ready_count;
    if (std::memcmp(
            cpp_rows.data(), rust_rows.data(), sizeof(cpp_rows)) != 0 ||
        cpp_inventory != rust_inventory ||
        cpp_allocation != rust_allocation ||
        cpp_ready_count != rust_ready_count ||
        cpp_failure_count != rust_failure_count) {
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "C++ and Rust fixed64 allocation receipts diverged");
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bool requirement_is(
    const bg_docking_fixed64_allocation_row_v1 &row,
    std::size_t index,
    bg_docking_fixed64_requirement_kind kind,
    uint32_t value) noexcept {
    return index < row.requirement_count &&
           row.requirements[index].kind == kind &&
           row.requirements[index].value == value &&
           reserved_is_zero(row.requirements[index].reserved);
}

[[nodiscard]] bool missing_is(
    const bg_docking_fixed64_allocation_row_v1 &row,
    std::size_t index,
    bg_docking_fixed64_missing_feature_kind kind,
    uint32_t value) noexcept {
    return index < row.missing_feature_count &&
           row.missing_features[index].kind == kind &&
           row.missing_features[index].value == value &&
           reserved_is_zero(row.missing_features[index].reserved);
}

[[nodiscard]] bool missing_subset_is(
    const bg_docking_fixed64_allocation_row_v1 &row,
    bg_docking_fixed64_missing_feature_kind first,
    bg_docking_fixed64_missing_feature_kind second) noexcept {
    if (row.missing_feature_count > 2) return false;
    bool first_seen = false;
    bool second_seen = false;
    for (std::size_t index = 0; index < row.missing_feature_count; ++index) {
        const auto &missing = row.missing_features[index];
        if (missing.value != 0 || !reserved_is_zero(missing.reserved)) {
            return false;
        }
        if (missing.kind == first && !first_seen) {
            first_seen = true;
        } else if (missing.kind == second && !second_seen) {
            second_seen = true;
        } else {
            return false;
        }
    }
    return true;
}

[[nodiscard]] bool parent_shape_is_valid(
    const bg_docking_fixed64_allocation_row_v1 &row) noexcept {
    if (row.generation_parent_role < BG_DOCKING_FIXED64_PARENT_NONE ||
        row.generation_parent_role >
            BG_DOCKING_FIXED64_PARENT_GENERATOR_INPUT) {
        return false;
    }
    const bool receipt_zero = zero_array(row.generation_parent_receipt_sha256);
    const bool proposal_zero = zero_array(row.generation_parent_proposal_sha256);
    const bool coordinate_zero =
        zero_array(row.generation_parent_coordinate_sha256);
    if (row.generation_parent_role == BG_DOCKING_FIXED64_PARENT_NONE) {
        return receipt_zero && proposal_zero && coordinate_zero;
    }
    return !receipt_zero && !proposal_zero && !coordinate_zero;
}

[[nodiscard]] bool selected_receipts_are_present(
    const bg_docking_fixed64_allocation_row_v1 &row) noexcept {
    for (std::size_t index = 0;
         index < row.selected_source_receipt_count;
         ++index) {
        if (zero_array(row.selected_source_receipt_sha256[index])) {
            return false;
        }
    }
    return true;
}

[[nodiscard]] bool lane_shape_is_valid(
    const bg_docking_fixed64_allocation_row_v1 &row) noexcept {
    const bool ready =
        row.status == BG_DOCKING_FIXED64_ALLOCATION_ROW_READY;
    const bool base_indexes_absent =
        row.v7_control_source_index == -1 &&
        row.so3_sequence_index == -1 &&
        row.true_conformer_rank == -1 &&
        row.retained_source_index == -1;
    switch (row.lane) {
        case BG_DOCKING_FIXED64_LANE_POCKET_CENTERED_CONTROLS:
        case BG_DOCKING_FIXED64_LANE_UNIFORM_SOURCE_CONTROLS: {
            const uint32_t source_index =
                row.lane == BG_DOCKING_FIXED64_LANE_UNIFORM_SOURCE_CONTROLS
                ? row.lane_offset + UINT32_C(8)
                : row.lane_offset;
            return row.requirement_count == 1 &&
                   requirement_is(
                       row,
                       0,
                       BG_DOCKING_FIXED64_REQUIREMENT_V7_CONTROL_SOURCE,
                       source_index) &&
                   row.v7_control_source_index ==
                       static_cast<int32_t>(source_index) &&
                   row.so3_sequence_index == -1 &&
                   row.true_conformer_rank == -1 &&
                   row.retained_source_index == -1 &&
                   (ready
                        ? row.missing_feature_count == 0 &&
                              row.selected_source_receipt_count == 1 &&
                              row.generation_parent_role ==
                                  BG_DOCKING_FIXED64_PARENT_EXACT_PASSTHROUGH
                        : row.missing_feature_count == 1 &&
                              missing_is(
                                  row,
                                  0,
                                  BG_DOCKING_FIXED64_MISSING_V7_CONTROL_SOURCE,
                                  source_index) &&
                              row.selected_source_receipt_count == 0 &&
                              row.generation_parent_role ==
                                  BG_DOCKING_FIXED64_PARENT_NONE);
        }
        case BG_DOCKING_FIXED64_LANE_DETERMINISTIC_INDEPENDENT_SO3:
            return row.requirement_count == 0 &&
                   row.missing_feature_count == 0 &&
                   row.selected_source_receipt_count == 0 &&
                   row.v7_control_source_index == -1 &&
                   row.so3_sequence_index ==
                       static_cast<int32_t>(row.lane_offset) &&
                   row.true_conformer_rank == -1 &&
                   row.retained_source_index == -1 && ready &&
                   row.generation_parent_role ==
                       BG_DOCKING_FIXED64_PARENT_GENERATOR_INPUT;
        case BG_DOCKING_FIXED64_LANE_TRUE_CONFORMER_INDEPENDENT_SO3: {
            const uint32_t rank = kTrueConformerRanks[row.lane_offset];
            return row.requirement_count == 1 &&
                   requirement_is(
                       row,
                       0,
                       BG_DOCKING_FIXED64_REQUIREMENT_TRUE_CONFORMER_RANK,
                       rank) &&
                   row.v7_control_source_index == -1 &&
                   row.so3_sequence_index ==
                       static_cast<int32_t>(row.lane_offset) &&
                   row.true_conformer_rank == static_cast<int32_t>(rank) &&
                   row.retained_source_index == -1 &&
                   (ready
                        ? row.missing_feature_count == 0 &&
                              row.selected_source_receipt_count == 1 &&
                              row.generation_parent_role ==
                                  BG_DOCKING_FIXED64_PARENT_GENERATOR_INPUT
                        : row.missing_feature_count == 1 &&
                              missing_is(
                                  row,
                                  0,
                                  BG_DOCKING_FIXED64_MISSING_TRUE_CONFORMER,
                                  rank) &&
                              row.selected_source_receipt_count == 0 &&
                              row.generation_parent_role ==
                                  BG_DOCKING_FIXED64_PARENT_NONE);
        }
        case BG_DOCKING_FIXED64_LANE_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR:
            return base_indexes_absent && row.requirement_count == 2 &&
                   requirement_is(
                       row,
                       0,
                       BG_DOCKING_FIXED64_REQUIREMENT_FEATURE,
                       BG_DOCKING_FIXED64_FEATURE_LIGAND_DONOR) &&
                   requirement_is(
                       row,
                       1,
                       BG_DOCKING_FIXED64_REQUIREMENT_FEATURE,
                       BG_DOCKING_FIXED64_FEATURE_RECEPTOR_ACCEPTOR) &&
                   missing_subset_is(
                       row,
                       BG_DOCKING_FIXED64_MISSING_LIGAND_DONOR,
                       BG_DOCKING_FIXED64_MISSING_RECEPTOR_ACCEPTOR) &&
                   row.selected_source_receipt_count +
                           row.missing_feature_count ==
                       2 &&
                   ready == (row.missing_feature_count == 0) &&
                   row.generation_parent_role ==
                       BG_DOCKING_FIXED64_PARENT_GENERATOR_INPUT;
        case BG_DOCKING_FIXED64_LANE_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR:
            return base_indexes_absent && row.requirement_count == 2 &&
                   requirement_is(
                       row,
                       0,
                       BG_DOCKING_FIXED64_REQUIREMENT_FEATURE,
                       BG_DOCKING_FIXED64_FEATURE_LIGAND_ACCEPTOR) &&
                   requirement_is(
                       row,
                       1,
                       BG_DOCKING_FIXED64_REQUIREMENT_FEATURE,
                       BG_DOCKING_FIXED64_FEATURE_RECEPTOR_DONOR) &&
                   missing_subset_is(
                       row,
                       BG_DOCKING_FIXED64_MISSING_LIGAND_ACCEPTOR,
                       BG_DOCKING_FIXED64_MISSING_RECEPTOR_DONOR) &&
                   row.selected_source_receipt_count +
                           row.missing_feature_count ==
                       2 &&
                   ready == (row.missing_feature_count == 0) &&
                   row.generation_parent_role ==
                       BG_DOCKING_FIXED64_PARENT_GENERATOR_INPUT;
        case BG_DOCKING_FIXED64_LANE_COMPLEMENTARY_CHARGE:
            return base_indexes_absent && row.requirement_count == 1 &&
                   requirement_is(
                       row,
                       0,
                       BG_DOCKING_FIXED64_REQUIREMENT_COMPLEMENTARY_CHARGE_ANCHOR,
                       0) &&
                   row.generation_parent_role ==
                       BG_DOCKING_FIXED64_PARENT_GENERATOR_INPUT &&
                   (ready
                        ? row.missing_feature_count == 0 &&
                              row.selected_source_receipt_count == 2
                        : row.missing_feature_count == 1 &&
                              missing_is(
                                  row,
                                  0,
                                  BG_DOCKING_FIXED64_MISSING_COMPLEMENTARY_CHARGE_ANCHOR,
                                  0) &&
                              row.selected_source_receipt_count == 0);
        case BG_DOCKING_FIXED64_LANE_AROMATIC_PLANE:
            return base_indexes_absent && row.requirement_count == 2 &&
                   requirement_is(
                       row,
                       0,
                       BG_DOCKING_FIXED64_REQUIREMENT_FEATURE,
                       BG_DOCKING_FIXED64_FEATURE_LIGAND_AROMATIC_PLANE) &&
                   requirement_is(
                       row,
                       1,
                       BG_DOCKING_FIXED64_REQUIREMENT_FEATURE,
                       BG_DOCKING_FIXED64_FEATURE_RECEPTOR_AROMATIC_PLANE) &&
                   missing_subset_is(
                       row,
                       BG_DOCKING_FIXED64_MISSING_LIGAND_AROMATIC_PLANE,
                       BG_DOCKING_FIXED64_MISSING_RECEPTOR_AROMATIC_PLANE) &&
                   row.selected_source_receipt_count +
                           row.missing_feature_count ==
                       2 &&
                   ready == (row.missing_feature_count == 0) &&
                   row.generation_parent_role ==
                       BG_DOCKING_FIXED64_PARENT_GENERATOR_INPUT;
        case BG_DOCKING_FIXED64_LANE_PRINCIPAL_AXIS_SHAPE:
            return base_indexes_absent && row.requirement_count == 2 &&
                   requirement_is(
                       row,
                       0,
                       BG_DOCKING_FIXED64_REQUIREMENT_FEATURE,
                       BG_DOCKING_FIXED64_FEATURE_LIGAND_SHAPE_AXIS) &&
                   requirement_is(
                       row,
                       1,
                       BG_DOCKING_FIXED64_REQUIREMENT_FEATURE,
                       BG_DOCKING_FIXED64_FEATURE_POCKET_SHAPE_AXIS) &&
                   missing_subset_is(
                       row,
                       BG_DOCKING_FIXED64_MISSING_LIGAND_SHAPE_AXIS,
                       BG_DOCKING_FIXED64_MISSING_POCKET_SHAPE_AXIS) &&
                   row.selected_source_receipt_count +
                           row.missing_feature_count ==
                       2 &&
                   ready == (row.missing_feature_count == 0) &&
                   row.generation_parent_role ==
                       BG_DOCKING_FIXED64_PARENT_GENERATOR_INPUT;
        case BG_DOCKING_FIXED64_LANE_PAIRED_RETAINED_CONTROLS: {
            const uint32_t source_index =
                kRetainedSourceIndices[row.lane_offset];
            return row.requirement_count == 1 &&
                   requirement_is(
                       row,
                       0,
                       BG_DOCKING_FIXED64_REQUIREMENT_RETAINED_SOURCE,
                       source_index) &&
                   row.v7_control_source_index == -1 &&
                   row.so3_sequence_index == -1 &&
                   row.true_conformer_rank == -1 &&
                   row.retained_source_index ==
                       static_cast<int32_t>(source_index) &&
                   (ready
                        ? row.missing_feature_count == 0 &&
                              row.selected_source_receipt_count == 1 &&
                              row.generation_parent_role ==
                                  BG_DOCKING_FIXED64_PARENT_EXACT_PASSTHROUGH
                        : row.missing_feature_count == 1 &&
                              missing_is(
                                  row,
                                  0,
                                  BG_DOCKING_FIXED64_MISSING_RETAINED_SOURCE,
                                  source_index) &&
                              row.selected_source_receipt_count == 0 &&
                              row.generation_parent_role ==
                                  BG_DOCKING_FIXED64_PARENT_NONE);
        }
        default:
            return false;
    }
}

}  // namespace

bg_status verify_snapshot(
    const uint8_t (&inventory)[32],
    const uint8_t (&allocation)[32],
    const bg_docking_fixed64_allocation_row_v1 *rows,
    std::size_t row_count) noexcept {
    if (rows == nullptr || !pointer_is_aligned(rows) ||
        row_count != kCandidateCount ||
        std::all_of(std::begin(inventory), std::end(inventory),
                    [](uint8_t value) { return value == UINT8_C(0); }) ||
        std::all_of(std::begin(allocation), std::end(allocation),
                    [](uint8_t value) { return value == UINT8_C(0); })) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 allocation snapshot is absent or has the wrong denominator");
    }
    std::array<bg_docking_fixed64_allocation_row_v1, kCandidateCount>
        snapshot{};
    for (std::size_t index = 0; index < snapshot.size(); ++index) {
        const auto &row = rows[index];
        const auto [expected_lane, expected_offset] = lane_for_slot(index);
        if (row.slot_index != index || row.lane != expected_lane ||
            row.lane_offset != expected_offset ||
            row.declared_anchor_kind != anchor_for_lane(expected_lane) ||
            row.requirement_count > BG_DOCKING_FIXED64_MAX_REQUIREMENTS ||
            row.missing_feature_count > BG_DOCKING_FIXED64_MAX_MISSING_FEATURES ||
            row.selected_source_receipt_count >
                BG_DOCKING_FIXED64_MAX_SELECTED_SOURCE_RECEIPTS ||
            row.reserved0 != 0 || !reserved_is_zero(row.reserved) ||
            row.fallback_allowed != UINT8_C(0) ||
            row.multi_anchor_allowed != UINT8_C(0) ||
            row.result_dependent_allocation != UINT8_C(0) ||
            row.denominator_preserved != UINT8_C(1) ||
            row.molecular_execution_authorized != UINT8_C(0) ||
            row.reservation_authorized != UINT8_C(0) ||
            row.benchmark_execution_authorized != UINT8_C(0) ||
            !parent_shape_is_valid(row) ||
            !selected_receipts_are_present(row) ||
            !lane_shape_is_valid(row) ||
            (row.status == BG_DOCKING_FIXED64_ALLOCATION_ROW_READY) !=
                (row.generation_eligible == UINT8_C(1)) ||
            (row.status == BG_DOCKING_FIXED64_ALLOCATION_ROW_TYPED_FAILURE) !=
                (row.generation_eligible == UINT8_C(0)) ||
            (row.generation_eligible == UINT8_C(1)) !=
                (row.missing_feature_count == 0)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 allocation snapshot row violates frozen shape");
        }
        for (std::size_t requirement = row.requirement_count;
             requirement < BG_DOCKING_FIXED64_MAX_REQUIREMENTS;
             ++requirement) {
            if (row.requirements[requirement].kind != 0 ||
                row.requirements[requirement].value != 0 ||
                !reserved_is_zero(row.requirements[requirement].reserved)) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "fixed64 allocation snapshot unused requirement is nonzero");
            }
        }
        for (std::size_t missing = row.missing_feature_count;
             missing < BG_DOCKING_FIXED64_MAX_MISSING_FEATURES;
             ++missing) {
            if (row.missing_features[missing].kind != 0 ||
                row.missing_features[missing].value != 0 ||
                !reserved_is_zero(row.missing_features[missing].reserved)) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "fixed64 allocation snapshot unused missing feature is nonzero");
            }
        }
        for (std::size_t selected = row.selected_source_receipt_count;
             selected < BG_DOCKING_FIXED64_MAX_SELECTED_SOURCE_RECEIPTS;
             ++selected) {
            if (!std::all_of(
                    std::begin(row.selected_source_receipt_sha256[selected]),
                    std::end(row.selected_source_receipt_sha256[selected]),
                    [](uint8_t value) { return value == UINT8_C(0); })) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "fixed64 allocation snapshot unused receipt is nonzero");
            }
        }
        const auto expected_receipt = slot_sha256(row);
        if (std::memcmp(
                expected_receipt.data(), row.slot_receipt_sha256, 32) != 0) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 allocation snapshot slot receipt is invalid");
        }
        snapshot[index] = row;
    }
    const std::array<uint8_t, 32> inventory_value = [&]() {
        std::array<uint8_t, 32> value{};
        std::copy(std::begin(inventory), std::end(inventory), value.begin());
        return value;
    }();
    const auto expected_allocation =
        allocation_sha256(inventory_value, snapshot);
    if (std::memcmp(expected_allocation.data(), allocation, 32) != 0) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 allocation snapshot receipt is invalid");
    }
    return BG_STATUS_OK;
}

}  // namespace betelgeuze::native::docking::fixed64_allocation

using namespace betelgeuze::native;

extern "C" BG_API bg_status BG_CALL
bg_docking_fixed64_allocation_input_v1_init(
    bg_docking_fixed64_allocation_input_v1 *input,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            input,
            caller_struct_size,
            sizeof(bg_docking_fixed64_allocation_input_v1),
            caller_abi_version,
            "fixed64 allocation input initializer pointer is null",
            "fixed64 allocation input initializer size does not match",
            "fixed64 allocation input initializer ABI version does not match");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *input = bg_docking_fixed64_allocation_input_v1{};
        input->struct_size = static_cast<uint32_t>(sizeof(*input));
        input->abi_version = BG_ABI_VERSION;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL
bg_docking_fixed64_allocation_output_v1_init(
    bg_docking_fixed64_allocation_output_v1 *output,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            output,
            caller_struct_size,
            sizeof(bg_docking_fixed64_allocation_output_v1),
            caller_abi_version,
            "fixed64 allocation output initializer pointer is null",
            "fixed64 allocation output initializer size does not match",
            "fixed64 allocation output initializer ABI version does not match");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *output = bg_docking_fixed64_allocation_output_v1{};
        output->struct_size = static_cast<uint32_t>(sizeof(*output));
        output->abi_version = BG_ABI_VERSION;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL
bg_docking_fixed64_allocation_v1_build(
    const bg_docking_fixed64_allocation_input_v1 *input,
    bg_docking_fixed64_allocation_output_v1 *output) BG_NOEXCEPT {
    using namespace betelgeuze::native::docking::fixed64_allocation;
    return guarded_status([&]() -> bg_status {
        if (input == nullptr || output == nullptr ||
            !pointer_is_aligned(input) || !pointer_is_aligned(output)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 allocation input and output must be non-null and aligned");
        }
        bg_status status = validate_input(*input);
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = validate_output(*input, *output);
        if (status != BG_STATUS_OK) {
            return status;
        }

        std::array<bg_docking_fixed64_allocation_row_v1, kCandidateCount>
            local_rows{};
        uint64_t ready_count = 0;
        for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
            local_rows[slot] = build_row(*input, slot);
            ready_count += local_rows[slot].generation_eligible;
        }
        const auto inventory = inventory_sha256(*input);
        const auto allocation = allocation_sha256(inventory, local_rows);
        status = verify_rust_parity(
            *input, local_rows, inventory, allocation, ready_count);
        if (status != BG_STATUS_OK) {
            return status;
        }

        std::memcpy(
            output->rows,
            local_rows.data(),
            sizeof(local_rows));
        output->row_count = kCandidateCount;
        output->ready_count = ready_count;
        output->typed_failure_count = kCandidateCount - ready_count;
        std::copy(
            inventory.begin(), inventory.end(), output->inventory_sha256);
        std::copy(
            allocation.begin(),
            allocation.end(),
            output->allocation_receipt_sha256);
        output->result_dependent_allocation = UINT8_C(0);
        output->molecular_execution_authorized = UINT8_C(0);
        output->reservation_authorized = UINT8_C(0);
        output->benchmark_execution_authorized = UINT8_C(0);
        output->existing_rank_auto_change_authorized = UINT8_C(0);
        output->customer_pose_emission_authorized = UINT8_C(0);
        output->production_claim_authorized = UINT8_C(0);
        return BG_STATUS_OK;
    });
}
