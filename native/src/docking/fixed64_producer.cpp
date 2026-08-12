#include "../dynamics/sha256.hpp"
#include "../internal.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <vector>

namespace betelgeuze::native::docking::fixed64_producer {
namespace {

using dynamics::Sha256;

constexpr std::size_t kCandidateCount = BG_DOCKING_FIXED64_CANDIDATE_COUNT;
constexpr std::size_t kMaximumLigandAtoms = 512;
constexpr std::size_t kMaximumFeatureRows = 3072;
constexpr std::size_t kMaximumFeatureAtomIndices = 65536;
constexpr std::size_t kMaximumV7Sources = 24;
constexpr std::size_t kMaximumConformerSources = 7;
constexpr std::size_t kMaximumRetainedSources = 4;
constexpr double kMaximumCoordinateAngstrom = 100'000.0;
constexpr double kGeometryEpsilon = 1.0e-12;
constexpr char kProfileId[] =
    "betelgeuze.engine_v2_mixed64_native_fixed64_producer/1.0.0";
constexpr char kBatchSchema[] =
    "betelgeuze.engine_v2_mixed64_native_fixed64_producer_batch/1.0.0";

struct Vec3 final {
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
};

struct MemoryRange final {
    uintptr_t begin = 0;
    uintptr_t end = 0;
};

struct ValidatedInput final {
    std::array<bg_docking_fixed64_allocation_row_v1, kCandidateCount>
        allocation_rows{};
    std::array<uint8_t, 32> allocation_inventory{};
    std::array<uint8_t, 32> allocation_receipt{};
    Vec3 pocket_normal{};
    std::size_t ligand_count = 0;
    std::size_t coordinate_count = 0;
};

class CanonicalHash final {
  public:
    explicit CanonicalHash(const char *domain) noexcept { string(domain); }

    void byte(uint8_t value) noexcept { hash_.update(&value, 1); }

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

    void size(std::size_t value) noexcept { u64(static_cast<uint64_t>(value)); }

    void f64(double value) noexcept {
        if (value == 0.0) value = 0.0;
        uint64_t bits = 0;
        static_assert(sizeof(bits) == sizeof(value));
        std::memcpy(&bits, &value, sizeof(bits));
        u64(bits);
    }

    void bytes(const uint8_t *values, std::size_t count) noexcept {
        size(count);
        hash_.update(values, count);
    }

    void string(const char *value) noexcept {
        bytes(reinterpret_cast<const uint8_t *>(value), std::strlen(value));
    }

    void digest(const uint8_t (&value)[32]) noexcept {
        hash_.update(value, 32);
    }

    void digest(const std::array<uint8_t, 32> &value) noexcept {
        hash_.update(value.data(), value.size());
    }

    void vec3(Vec3 value) noexcept {
        f64(value.x);
        f64(value.y);
        f64(value.z);
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
    if (output == nullptr) return false;
    if (pointer == nullptr || count == 0) {
        *output = {};
        return true;
    }
    if (count > std::numeric_limits<std::size_t>::max() / sizeof(Type)) {
        return false;
    }
    const std::size_t bytes = count * sizeof(Type);
    const uintptr_t begin = reinterpret_cast<uintptr_t>(pointer);
    if (begin > std::numeric_limits<uintptr_t>::max() - bytes) return false;
    *output = {begin, begin + bytes};
    return true;
}

[[nodiscard]] bool overlaps(MemoryRange left, MemoryRange right) noexcept {
    return left.begin != left.end && right.begin != right.end &&
           left.begin < right.end && right.begin < left.end;
}

[[nodiscard]] bool digest_present(const uint8_t (&digest)[32]) noexcept {
    return std::any_of(
        std::begin(digest), std::end(digest),
        [](uint8_t value) { return value != UINT8_C(0); });
}

[[nodiscard]] bool finite_coordinate(double value) noexcept {
    return std::isfinite(value) &&
           std::abs(value) <= kMaximumCoordinateAngstrom;
}

[[nodiscard]] bool same_source(
    const bg_docking_fixed64_source_evidence_v1 &left,
    const bg_docking_fixed64_source_evidence_v1 &right) noexcept {
    return std::memcmp(left.receipt_sha256, right.receipt_sha256, 32) == 0 &&
           std::memcmp(left.proposal_sha256, right.proposal_sha256, 32) == 0 &&
           std::memcmp(left.coordinate_sha256, right.coordinate_sha256, 32) == 0;
}

[[nodiscard]] bool normalize(Vec3 value, Vec3 *output) noexcept {
    const double maximum =
        std::max({std::abs(value.x), std::abs(value.y), std::abs(value.z)});
    if (!std::isfinite(maximum) || maximum <= kGeometryEpsilon) return false;
    const double x = value.x / maximum;
    const double y = value.y / maximum;
    const double z = value.z / maximum;
    const double scaled_norm = std::hypot(std::hypot(x, y), z);
    if (!std::isfinite(scaled_norm) || scaled_norm <= 0.0) return false;
    const double inverse = (1.0 / maximum) / scaled_norm;
    *output = {value.x * inverse, value.y * inverse, value.z * inverse};
    if (output->x == 0.0) output->x = 0.0;
    if (output->y == 0.0) output->y = 0.0;
    if (output->z == 0.0) output->z = 0.0;
    return true;
}

[[nodiscard]] std::array<uint8_t, 32> coordinate_sha256(
    const double *x,
    const double *y,
    const double *z,
    std::size_t count) noexcept {
    CanonicalHash hash("betelgeuze.fixed64_coordinates/native-v1");
    hash.size(count);
    for (std::size_t index = 0; index < count; ++index) {
        hash.vec3({x[index], y[index], z[index]});
    }
    return hash.finish();
}

[[nodiscard]] std::array<uint8_t, 32> source_payload_sha256(
    const bg_docking_fixed64_coordinate_source_v1 &source) noexcept {
    CanonicalHash hash("betelgeuze.fixed64_coordinate_source_abi/native-v1");
    hash.digest(source.source.receipt_sha256);
    hash.digest(source.source.proposal_sha256);
    hash.digest(source.source.coordinate_sha256);
    hash.u64(source.ligand_atom_count);
    hash.byte(UINT8_C(1));
    hash.byte(UINT8_C(0));
    return hash.finish();
}

[[nodiscard]] bg_status validate_coordinate_source(
    const bg_docking_fixed64_coordinate_source_v1 &source,
    const bg_docking_fixed64_source_evidence_v1 &expected) noexcept {
    if (source.ligand_atom_count == 0 ||
        source.ligand_atom_count > kMaximumLigandAtoms ||
        source.x_angstrom == nullptr || source.y_angstrom == nullptr ||
        source.z_angstrom == nullptr || !pointer_is_aligned(source.x_angstrom) ||
        !pointer_is_aligned(source.y_angstrom) ||
        !pointer_is_aligned(source.z_angstrom) ||
        !reserved_is_zero(source.source.reserved) ||
        !reserved_is_zero(source.reserved) || !same_source(source.source, expected) ||
        !digest_present(source.source.receipt_sha256) ||
        !digest_present(source.source.proposal_sha256) ||
        !digest_present(source.source.coordinate_sha256)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 producer coordinate source is absent or cross-wired");
    }
    const std::size_t count =
        static_cast<std::size_t>(source.ligand_atom_count);
    for (const double *channel : {
             source.x_angstrom, source.y_angstrom, source.z_angstrom}) {
        for (std::size_t atom = 0; atom < count; ++atom) {
            if (!finite_coordinate(channel[atom])) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "fixed64 producer source coordinate is outside native bounds");
            }
        }
    }
    const auto observed = coordinate_sha256(
        source.x_angstrom, source.y_angstrom, source.z_angstrom, count);
    if (std::memcmp(
            observed.data(), source.source.coordinate_sha256, 32) != 0) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 producer source coordinate identity is invalid");
    }
    return BG_STATUS_OK;
}

[[nodiscard]] const bg_docking_fixed64_indexed_source_evidence_v1 *
find_indexed_evidence(
    const bg_docking_fixed64_indexed_source_evidence_v1 *values,
    std::size_t count,
    uint32_t source_index) noexcept {
    for (std::size_t index = 0; index < count; ++index) {
        if (values[index].source_index == source_index) return &values[index];
    }
    return nullptr;
}

[[nodiscard]] const bg_docking_fixed64_conformer_source_evidence_v1 *
find_conformer_evidence(
    const bg_docking_fixed64_conformer_source_evidence_v1 *values,
    std::size_t count,
    uint8_t rank) noexcept {
    for (std::size_t index = 0; index < count; ++index) {
        if (values[index].rank == rank) return &values[index];
    }
    return nullptr;
}

[[nodiscard]] const bg_docking_fixed64_indexed_coordinate_source_v1 *
find_indexed_source(
    const bg_docking_fixed64_indexed_coordinate_source_v1 *values,
    std::size_t count,
    uint32_t source_index) noexcept {
    for (std::size_t index = 0; index < count; ++index) {
        if (values[index].source_index == source_index) return &values[index];
    }
    return nullptr;
}

[[nodiscard]] const bg_docking_fixed64_conformer_coordinate_source_v1 *
find_conformer_source(
    const bg_docking_fixed64_conformer_coordinate_source_v1 *values,
    std::size_t count,
    uint8_t rank) noexcept {
    for (std::size_t index = 0; index < count; ++index) {
        if (values[index].rank == rank) return &values[index];
    }
    return nullptr;
}

[[nodiscard]] bg_status validate_indexed_sources(
    const bg_docking_fixed64_indexed_coordinate_source_v1 *sources,
    std::size_t count,
    std::size_t maximum,
    const bg_docking_fixed64_indexed_source_evidence_v1 *evidence,
    std::size_t evidence_count) noexcept {
    if (count > maximum ||
        (count != 0 &&
         (sources == nullptr || !pointer_is_aligned(sources)))) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 producer indexed source group is outside frozen bounds");
    }
    for (std::size_t index = 0; index < count; ++index) {
        const auto &source = sources[index];
        if (source.reserved0 != 0 || !reserved_is_zero(source.reserved) ||
            (index != 0 &&
             sources[index - 1].source_index >= source.source_index)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 producer indexed sources are not canonical");
        }
        const auto *expected = find_indexed_evidence(
            evidence, evidence_count, source.source_index);
        if (expected == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 producer indexed source is not allocation-declared");
        }
        const bg_status status =
            validate_coordinate_source(source.payload, expected->source);
        if (status != BG_STATUS_OK) return status;
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status validate_conformer_sources(
    const bg_docking_fixed64_conformer_coordinate_source_v1 *sources,
    std::size_t count,
    const bg_docking_fixed64_conformer_source_evidence_v1 *evidence,
    std::size_t evidence_count) noexcept {
    if (count > kMaximumConformerSources ||
        (count != 0 &&
         (sources == nullptr || !pointer_is_aligned(sources)))) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 producer conformer source group is outside frozen bounds");
    }
    for (std::size_t index = 0; index < count; ++index) {
        const auto &source = sources[index];
        if (!std::all_of(
                std::begin(source.reserved0), std::end(source.reserved0),
                [](uint8_t value) { return value == UINT8_C(0); }) ||
            !reserved_is_zero(source.reserved) ||
            (index != 0 && sources[index - 1].rank >= source.rank)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 producer conformer sources are not canonical");
        }
        const auto *expected = find_conformer_evidence(
            evidence, evidence_count, source.rank);
        if (expected == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 producer conformer source is not allocation-declared");
        }
        const bg_status status =
            validate_coordinate_source(source.payload, expected->source);
        if (status != BG_STATUS_OK) return status;
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status rebuild_allocation(
    const bg_docking_fixed64_allocation_input_v1 &input,
    ValidatedInput *validated) noexcept {
    bg_docking_fixed64_allocation_output_v1 output{};
    output.struct_size = sizeof(output);
    output.abi_version = BG_ABI_VERSION;
    output.row_capacity = validated->allocation_rows.size();
    output.rows = validated->allocation_rows.data();
    const bg_status status = bg_docking_fixed64_allocation_v1_build(
        &input, &output);
    if (status != BG_STATUS_OK) return status;
    if (output.row_count != kCandidateCount ||
        output.ready_count + output.typed_failure_count != kCandidateCount ||
        output.result_dependent_allocation != UINT8_C(0) ||
        output.molecular_execution_authorized != UINT8_C(0) ||
        output.reservation_authorized != UINT8_C(0) ||
        output.benchmark_execution_authorized != UINT8_C(0) ||
        output.existing_rank_auto_change_authorized != UINT8_C(0) ||
        output.customer_pose_emission_authorized != UINT8_C(0) ||
        output.production_claim_authorized != UINT8_C(0)) {
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "fixed64 producer allocation rebuild violated its authority boundary");
    }
    std::copy_n(
        output.inventory_sha256,
        32,
        validated->allocation_inventory.begin());
    std::copy_n(
        output.allocation_receipt_sha256,
        32,
        validated->allocation_receipt.begin());
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status validate_source_bundle(
    const bg_docking_fixed64_producer_input_v1 &input) noexcept {
    const auto &allocation = *input.allocation_input;
    if (input.v7_control_source_count > kMaximumV7Sources ||
        input.conformer_source_count > kMaximumConformerSources ||
        input.retained_source_count > kMaximumRetainedSources ||
        allocation.v7_control_source_count > kMaximumV7Sources ||
        allocation.conformer_source_count > kMaximumConformerSources ||
        allocation.retained_source_count > kMaximumRetainedSources) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "fixed64 producer source count exceeds its frozen bound");
    }
    if (input.exact_v11_source != nullptr) {
        if (!pointer_is_aligned(input.exact_v11_source)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 producer exact source is misaligned");
        }
        bg_docking_fixed64_source_evidence_v1 expected{};
        std::copy_n(
            allocation.exact_v11_source.source_receipt_sha256,
            32,
            expected.receipt_sha256);
        std::copy_n(
            allocation.exact_v11_source.proposal_sha256,
            32,
            expected.proposal_sha256);
        std::copy_n(
            allocation.exact_v11_source.ligand_coordinate_sha256,
            32,
            expected.coordinate_sha256);
        const bg_status status =
            validate_coordinate_source(*input.exact_v11_source, expected);
        if (status != BG_STATUS_OK) return status;
    }
    bg_status status = validate_indexed_sources(
        input.v7_control_sources,
        static_cast<std::size_t>(input.v7_control_source_count),
        kMaximumV7Sources,
        allocation.v7_control_sources,
        static_cast<std::size_t>(allocation.v7_control_source_count));
    if (status != BG_STATUS_OK) return status;
    status = validate_conformer_sources(
        input.conformer_sources,
        static_cast<std::size_t>(input.conformer_source_count),
        allocation.conformer_sources,
        static_cast<std::size_t>(allocation.conformer_source_count));
    if (status != BG_STATUS_OK) return status;
    return validate_indexed_sources(
        input.retained_sources,
        static_cast<std::size_t>(input.retained_source_count),
        kMaximumRetainedSources,
        allocation.retained_sources,
        static_cast<std::size_t>(allocation.retained_source_count));
}

[[nodiscard]] std::array<uint8_t, 32> source_bundle_sha256(
    const bg_docking_fixed64_producer_input_v1 &input,
    const bg_docking_geometric_admission_v1 &admission,
    Vec3 pocket_normal,
    const std::array<uint8_t, 32> &allocation_receipt) noexcept {
    CanonicalHash hash("betelgeuze.fixed64_source_bundle_abi/native-v1");
    hash.digest(allocation_receipt);
    hash.byte(input.exact_v11_source == nullptr ? UINT8_C(0) : UINT8_C(1));
    if (input.exact_v11_source != nullptr) {
        hash.digest(source_payload_sha256(*input.exact_v11_source));
    }
    hash.u64(input.v7_control_source_count);
    for (uint64_t index = 0; index < input.v7_control_source_count; ++index) {
        hash.u32(input.v7_control_sources[index].source_index);
        hash.digest(source_payload_sha256(input.v7_control_sources[index].payload));
    }
    hash.u64(input.conformer_source_count);
    for (uint64_t index = 0; index < input.conformer_source_count; ++index) {
        hash.byte(input.conformer_sources[index].rank);
        hash.digest(source_payload_sha256(input.conformer_sources[index].payload));
    }
    hash.u64(input.retained_source_count);
    for (uint64_t index = 0; index < input.retained_source_count; ++index) {
        hash.u32(input.retained_sources[index].source_index);
        hash.digest(source_payload_sha256(input.retained_sources[index].payload));
    }
    hash.u64(input.feature_geometry_count);
    hash.u64(input.feature_atom_index_count);
    hash.digest(input.feature_geometry_inventory_sha256);
    hash.vec3({
        admission.pocket_center_angstrom[0],
        admission.pocket_center_angstrom[1],
        admission.pocket_center_angstrom[2],
    });
    hash.vec3(pocket_normal);
    hash.digest(admission.authority_input_receipt_sha256);
    hash.digest(admission.receptor_system_sha256);
    hash.digest(admission.ligand_system_sha256);
    hash.digest(admission.backend_receipt_sha256);
    hash.byte(UINT8_C(1));
    hash.byte(UINT8_C(0));
    return hash.finish();
}

[[nodiscard]] std::array<uint8_t, 32> radii_sha256(
    const std::vector<double> &radii) noexcept {
    CanonicalHash hash("betelgeuze.fixed64_vdw_radii/native-v1");
    hash.size(radii.size());
    for (double radius : radii) hash.f64(radius);
    return hash.finish();
}

[[nodiscard]] std::array<uint8_t, 32> heavy_mask_sha256(
    const std::vector<uint8_t> &mask) noexcept {
    CanonicalHash hash("betelgeuze.fixed64_heavy_atom_mask/native-v1");
    hash.size(mask.size());
    for (uint8_t value : mask) hash.byte(value);
    return hash.finish();
}

[[nodiscard]] bg_status validate_admission_identity(
    const bg_docking_geometric_admission_v1 &admission,
    const bg_docking_fixed64_allocation_input_v1 &allocation) noexcept {
    const auto receptor_coordinate = coordinate_sha256(
        admission.receptor_x_angstrom.data(),
        admission.receptor_y_angstrom.data(),
        admission.receptor_z_angstrom.data(),
        admission.receptor_x_angstrom.size());
    const auto ligand_radii =
        radii_sha256(admission.ligand_vdw_radius_angstrom);
    const auto ligand_mask =
        heavy_mask_sha256(admission.ligand_heavy_atom_mask);
    const auto receptor_radii =
        radii_sha256(admission.receptor_vdw_radius_angstrom);
    const auto &exact = allocation.exact_v11_source;
    if (std::memcmp(
            receptor_coordinate.data(), exact.receptor_coordinate_sha256,
            32) != 0 ||
        std::memcmp(
            ligand_radii.data(), exact.ligand_vdw_radii_sha256, 32) != 0 ||
        std::memcmp(
            ligand_mask.data(), exact.ligand_heavy_atom_mask_sha256, 32) !=
            0 ||
        std::memcmp(
            receptor_radii.data(), exact.receptor_vdw_radii_sha256, 32) !=
            0) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 producer admission geometry is cross-wired");
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_docking_fixed64_producer_placement_kind placement_kind(
    bg_docking_fixed64_lane lane) noexcept {
    if (lane == BG_DOCKING_FIXED64_LANE_POCKET_CENTERED_CONTROLS ||
        lane == BG_DOCKING_FIXED64_LANE_UNIFORM_SOURCE_CONTROLS ||
        lane == BG_DOCKING_FIXED64_LANE_PAIRED_RETAINED_CONTROLS) {
        return BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_EXACT_PASSTHROUGH;
    }
    if (lane == BG_DOCKING_FIXED64_LANE_DETERMINISTIC_INDEPENDENT_SO3 ||
        lane == BG_DOCKING_FIXED64_LANE_TRUE_CONFORMER_INDEPENDENT_SO3) {
        return BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_INDEXED_SO3;
    }
    if (lane >=
            BG_DOCKING_FIXED64_LANE_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR &&
        lane <= BG_DOCKING_FIXED64_LANE_PRINCIPAL_AXIS_SHAPE) {
        return BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_SINGLE_ANCHOR;
    }
    return BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_NONE;
}

[[nodiscard]] const bg_docking_fixed64_coordinate_source_v1 *source_for_row(
    const bg_docking_fixed64_producer_input_v1 &input,
    const bg_docking_fixed64_allocation_row_v1 &row) noexcept {
    if (row.lane == BG_DOCKING_FIXED64_LANE_POCKET_CENTERED_CONTROLS ||
        row.lane == BG_DOCKING_FIXED64_LANE_UNIFORM_SOURCE_CONTROLS) {
        if (row.v7_control_source_index < 0) return nullptr;
        const auto *source = find_indexed_source(
            input.v7_control_sources,
            static_cast<std::size_t>(input.v7_control_source_count),
            static_cast<uint32_t>(row.v7_control_source_index));
        return source == nullptr ? nullptr : &source->payload;
    }
    if (row.lane ==
        BG_DOCKING_FIXED64_LANE_TRUE_CONFORMER_INDEPENDENT_SO3) {
        if (row.true_conformer_rank < 0 || row.true_conformer_rank > 255) {
            return nullptr;
        }
        const auto *source = find_conformer_source(
            input.conformer_sources,
            static_cast<std::size_t>(input.conformer_source_count),
            static_cast<uint8_t>(row.true_conformer_rank));
        return source == nullptr ? nullptr : &source->payload;
    }
    if (row.lane == BG_DOCKING_FIXED64_LANE_PAIRED_RETAINED_CONTROLS) {
        if (row.retained_source_index < 0) return nullptr;
        const auto *source = find_indexed_source(
            input.retained_sources,
            static_cast<std::size_t>(input.retained_source_count),
            static_cast<uint32_t>(row.retained_source_index));
        return source == nullptr ? nullptr : &source->payload;
    }
    return input.exact_v11_source;
}

[[nodiscard]] bool source_matches_parent(
    const bg_docking_fixed64_coordinate_source_v1 &source,
    const bg_docking_fixed64_allocation_row_v1 &row) noexcept {
    return std::memcmp(
               source.source.receipt_sha256,
               row.generation_parent_receipt_sha256, 32) == 0 &&
           std::memcmp(
               source.source.proposal_sha256,
               row.generation_parent_proposal_sha256, 32) == 0 &&
           std::memcmp(
               source.source.coordinate_sha256,
               row.generation_parent_coordinate_sha256, 32) == 0;
}

[[nodiscard]] bool selected_feature_geometry_available(
    const bg_docking_fixed64_producer_input_v1 &input,
    const bg_docking_fixed64_allocation_row_v1 &row) noexcept {
    if (row.selected_source_receipt_count != 2) return false;
    bg_docking_fixed64_feature_kind ligand_kind = -1;
    bg_docking_fixed64_feature_kind receptor_kind = -1;
    switch (row.lane) {
        case BG_DOCKING_FIXED64_LANE_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR:
            ligand_kind = BG_DOCKING_FIXED64_FEATURE_LIGAND_DONOR;
            receptor_kind = BG_DOCKING_FIXED64_FEATURE_RECEPTOR_ACCEPTOR;
            break;
        case BG_DOCKING_FIXED64_LANE_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR:
            ligand_kind = BG_DOCKING_FIXED64_FEATURE_LIGAND_ACCEPTOR;
            receptor_kind = BG_DOCKING_FIXED64_FEATURE_RECEPTOR_DONOR;
            break;
        case BG_DOCKING_FIXED64_LANE_AROMATIC_PLANE:
            ligand_kind = BG_DOCKING_FIXED64_FEATURE_LIGAND_AROMATIC_PLANE;
            receptor_kind = BG_DOCKING_FIXED64_FEATURE_RECEPTOR_AROMATIC_PLANE;
            break;
        case BG_DOCKING_FIXED64_LANE_PRINCIPAL_AXIS_SHAPE:
            ligand_kind = BG_DOCKING_FIXED64_FEATURE_LIGAND_SHAPE_AXIS;
            receptor_kind = BG_DOCKING_FIXED64_FEATURE_POCKET_SHAPE_AXIS;
            break;
        case BG_DOCKING_FIXED64_LANE_COMPLEMENTARY_CHARGE: {
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
            const auto feature_count = [&input](
                bg_docking_fixed64_feature_kind kind) noexcept {
                std::size_t count = 0;
                for (uint64_t index = 0;
                     index < input.allocation_input->atomic_feature_count;
                     ++index) {
                    if (input.allocation_input->atomic_features[index].kind ==
                        kind) {
                        ++count;
                    }
                }
                return count;
            };
            std::array<std::size_t, 2> available{};
            std::size_t available_count = 0;
            for (std::size_t pair = 0; pair < pairs.size(); ++pair) {
                if (feature_count(pairs[pair].first) != 0 &&
                    feature_count(pairs[pair].second) != 0) {
                    available[available_count++] = pair;
                }
            }
            if (available_count == 0) return false;
            const auto &selected =
                pairs[available[row.lane_offset % available_count]];
            ligand_kind = selected.first;
            receptor_kind = selected.second;
            break;
        }
        default:
            return false;
    }
    std::size_t ligand_count = 0;
    std::size_t receptor_count = 0;
    for (uint64_t feature = 0; feature < input.feature_geometry_count;
         ++feature) {
        const auto &geometry = input.feature_geometry_rows[feature];
        if (std::memcmp(
                row.selected_source_receipt_sha256[0],
                geometry.allocation_feature_receipt_sha256,
                32) == 0 &&
            geometry.kind == ligand_kind) {
            ++ligand_count;
        }
        if (std::memcmp(
                row.selected_source_receipt_sha256[1],
                geometry.allocation_feature_receipt_sha256,
                32) == 0 &&
            geometry.kind == receptor_kind) {
            ++receptor_count;
        }
    }
    return ligand_count == 1 && receptor_count == 1;
}

[[nodiscard]] std::array<uint8_t, 32> passthrough_receipt(
    const std::array<uint8_t, 32> &allocation_receipt,
    const bg_docking_fixed64_allocation_row_v1 &allocation_row,
    const bg_docking_fixed64_coordinate_source_v1 &source,
    bg_backend backend) noexcept {
    CanonicalHash hash("betelgeuze.fixed64_passthrough_abi/native-v1");
    hash.string(kProfileId);
    hash.digest(allocation_receipt);
    hash.digest(allocation_row.slot_receipt_sha256);
    hash.u32(allocation_row.slot_index);
    hash.u32(static_cast<uint32_t>(allocation_row.lane));
    hash.u32(static_cast<uint32_t>(backend));
    hash.digest(source_payload_sha256(source));
    hash.digest(source.source.coordinate_sha256);
    hash.byte(UINT8_C(1));
    hash.byte(UINT8_C(0));
    return hash.finish();
}

[[nodiscard]] std::array<uint8_t, 32> generated_proposal_sha256(
    const std::array<uint8_t, 32> &allocation_receipt,
    const bg_docking_fixed64_allocation_row_v1 &allocation_row,
    const std::array<uint8_t, 32> &source_payload,
    const uint8_t (&placement_receipt)[32],
    const uint8_t (&coordinate)[32]) noexcept {
    CanonicalHash hash("betelgeuze.fixed64_generated_proposal_abi/native-v1");
    hash.string(kProfileId);
    hash.digest(allocation_receipt);
    hash.digest(allocation_row.slot_receipt_sha256);
    hash.u32(allocation_row.slot_index);
    hash.digest(source_payload);
    hash.digest(placement_receipt);
    hash.digest(coordinate);
    hash.byte(UINT8_C(0));
    return hash.finish();
}

[[nodiscard]] std::array<uint8_t, 32> producer_row_receipt(
    const std::array<uint8_t, 32> &allocation_receipt,
    const std::array<uint8_t, 32> &source_bundle,
    const bg_docking_fixed64_producer_row_v1 &row) noexcept {
    CanonicalHash hash("betelgeuze.fixed64_producer_row_abi/native-v1");
    hash.string(kProfileId);
    hash.digest(allocation_receipt);
    hash.digest(source_bundle);
    hash.digest(row.allocation_slot_receipt_sha256);
    hash.u32(row.slot_index);
    hash.u32(static_cast<uint32_t>(row.lane));
    hash.u32(static_cast<uint32_t>(row.status));
    hash.u32(static_cast<uint32_t>(row.failure_code));
    hash.u32(static_cast<uint32_t>(row.placement_kind));
    hash.u32(static_cast<uint32_t>(row.component_failure_code));
    hash.u32(static_cast<uint32_t>(row.backend));
    hash.u64(row.ligand_atom_count);
    hash.u64(row.coordinate_offset);
    hash.digest(row.source_payload_receipt_sha256);
    hash.digest(row.source_proposal_sha256);
    hash.digest(row.source_coordinate_sha256);
    hash.digest(row.placement_receipt_sha256);
    hash.digest(row.output_proposal_sha256);
    hash.digest(row.output_coordinate_sha256);
    hash.digest(row.geometric_admission.row_receipt_sha256);
    hash.byte(row.coordinates_available);
    hash.byte(row.steric_precheck_passed);
    hash.byte(row.source_identity_verified);
    hash.byte(row.allocation_identity_verified);
    hash.byte(row.geometric_identity_verified);
    hash.byte(row.result_dependent_input_consumed);
    hash.byte(row.fallback_allowed);
    hash.byte(row.multi_anchor_consumed);
    hash.byte(row.denominator_preserved);
    hash.byte(row.molecular_execution_authorized);
    hash.byte(row.reservation_authorized);
    hash.byte(row.benchmark_execution_authorized);
    hash.byte(row.existing_rank_auto_change_authorized);
    hash.byte(row.customer_pose_emission_authorized);
    hash.byte(row.production_claim_authorized);
    hash.byte(row.scientific_claim_authorized);
    return hash.finish();
}

[[nodiscard]] std::array<uint8_t, 32> producer_batch_receipt(
    const std::array<uint8_t, 32> &allocation_inventory,
    const std::array<uint8_t, 32> &allocation_receipt,
    const std::array<uint8_t, 32> &source_bundle,
    const std::array<uint8_t, 32> &geometric_batch,
    const std::array<bg_docking_fixed64_producer_row_v1, kCandidateCount>
        &rows,
    std::size_t generated_count,
    bg_backend backend) noexcept {
    CanonicalHash hash("betelgeuze.fixed64_producer_batch_abi/native-v1");
    hash.string(kBatchSchema);
    hash.string(kProfileId);
    hash.u32(static_cast<uint32_t>(backend));
    hash.u64(kCandidateCount);
    hash.size(generated_count);
    hash.size(kCandidateCount - generated_count);
    hash.digest(allocation_inventory);
    hash.digest(allocation_receipt);
    hash.digest(source_bundle);
    hash.digest(geometric_batch);
    for (const auto &row : rows) hash.digest(row.row_receipt_sha256);
    hash.byte(UINT8_C(0));
    hash.byte(UINT8_C(0));
    hash.byte(UINT8_C(0));
    hash.byte(UINT8_C(1));
    for (std::size_t index = 0; index < 7; ++index) hash.byte(UINT8_C(0));
    return hash.finish();
}

void initialize_row(
    const bg_docking_fixed64_allocation_row_v1 &allocation,
    std::size_t ligand_count,
    bg_backend backend,
    bg_docking_fixed64_producer_row_v1 *row) noexcept {
    *row = bg_docking_fixed64_producer_row_v1{};
    row->slot_index = allocation.slot_index;
    row->lane = allocation.lane;
    row->placement_kind = placement_kind(allocation.lane);
    row->backend = backend;
    row->ligand_atom_count = ligand_count;
    row->coordinate_offset =
        static_cast<uint64_t>(allocation.slot_index) * ligand_count;
    std::copy_n(
        allocation.slot_receipt_sha256, 32,
        row->allocation_slot_receipt_sha256);
    row->allocation_identity_verified = UINT8_C(1);
    row->denominator_preserved = UINT8_C(1);
}

void mark_failure(
    bg_docking_fixed64_producer_failure failure,
    int32_t component_failure,
    bg_docking_fixed64_producer_row_v1 *row) noexcept {
    row->status = BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE;
    row->failure_code = failure;
    row->component_failure_code = component_failure;
}

void bind_source(
    const bg_docking_fixed64_coordinate_source_v1 &source,
    bg_docking_fixed64_producer_row_v1 *row) noexcept {
    const auto payload = source_payload_sha256(source);
    std::copy(
        payload.begin(), payload.end(), row->source_payload_receipt_sha256);
    std::copy_n(
        source.source.proposal_sha256, 32, row->source_proposal_sha256);
    std::copy_n(
        source.source.coordinate_sha256, 32, row->source_coordinate_sha256);
    row->source_identity_verified = UINT8_C(1);
}

[[nodiscard]] bg_status validate_feature_shape(
    const bg_docking_fixed64_producer_input_v1 &input,
    const bg_docking_fixed64_allocation_input_v1 &allocation,
    const bg_docking_geometric_admission_v1 &admission) noexcept {
    const bool absent = input.feature_geometry_count == 0 &&
                        input.feature_atom_index_count == 0;
    if (absent) {
        if (input.feature_geometry_rows != nullptr ||
            input.feature_atom_indices != nullptr ||
            digest_present(input.feature_geometry_inventory_sha256)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 producer absent feature geometry is not canonical");
        }
        return BG_STATUS_OK;
    }
    if (input.feature_geometry_count == 0 ||
        input.feature_geometry_count > kMaximumFeatureRows ||
        input.feature_atom_index_count == 0 ||
        input.feature_atom_index_count > kMaximumFeatureAtomIndices ||
        input.feature_geometry_rows == nullptr ||
        input.feature_atom_indices == nullptr ||
        !pointer_is_aligned(input.feature_geometry_rows) ||
        !pointer_is_aligned(input.feature_atom_indices) ||
        !digest_present(input.feature_geometry_inventory_sha256)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 producer feature geometry shape is invalid");
    }
    const auto is_ligand_feature = [](bg_docking_fixed64_feature_kind kind) {
        return kind == BG_DOCKING_FIXED64_FEATURE_LIGAND_DONOR ||
               kind == BG_DOCKING_FIXED64_FEATURE_LIGAND_ACCEPTOR ||
               kind == BG_DOCKING_FIXED64_FEATURE_LIGAND_POSITIVE_SITE ||
               kind == BG_DOCKING_FIXED64_FEATURE_LIGAND_NEGATIVE_SITE ||
               kind == BG_DOCKING_FIXED64_FEATURE_LIGAND_AROMATIC_PLANE ||
               kind == BG_DOCKING_FIXED64_FEATURE_LIGAND_SHAPE_AXIS;
    };
    const auto valid_count = [](
        bg_docking_fixed64_feature_kind kind, std::size_t count) {
        if (kind == BG_DOCKING_FIXED64_FEATURE_LIGAND_DONOR ||
            kind == BG_DOCKING_FIXED64_FEATURE_RECEPTOR_DONOR) {
            return count == 2;
        }
        if (kind == BG_DOCKING_FIXED64_FEATURE_LIGAND_ACCEPTOR ||
            kind == BG_DOCKING_FIXED64_FEATURE_RECEPTOR_ACCEPTOR) {
            return count == 1;
        }
        if (kind == BG_DOCKING_FIXED64_FEATURE_LIGAND_AROMATIC_PLANE ||
            kind == BG_DOCKING_FIXED64_FEATURE_RECEPTOR_AROMATIC_PLANE) {
            return count >= 3 && count <= kMaximumFeatureAtomIndices;
        }
        return count >= 1 && count <= kMaximumFeatureAtomIndices;
    };
    const auto allocation_contains = [&allocation](
        const bg_docking_fixed64_feature_geometry_row_v1 &row) {
        for (uint64_t index = 0; index < allocation.atomic_feature_count;
             ++index) {
            const auto &feature = allocation.atomic_features[index];
            if (feature.kind == row.kind &&
                std::memcmp(
                    feature.receipt_sha256,
                    row.allocation_feature_receipt_sha256, 32) == 0) {
                return true;
            }
        }
        return false;
    };
    uint64_t expected_offset = 0;
    CanonicalHash inventory(
        "betelgeuze.fixed64_feature_geometry_inventory/native-v1");
    inventory.u64(input.feature_geometry_count);
    for (uint64_t row_index = 0; row_index < input.feature_geometry_count;
         ++row_index) {
        const auto &row = input.feature_geometry_rows[row_index];
        if (row.kind < BG_DOCKING_FIXED64_FEATURE_LIGAND_DONOR ||
            row.kind > BG_DOCKING_FIXED64_FEATURE_POCKET_SHAPE_AXIS ||
            row.reserved0 != 0 || !reserved_is_zero(row.reserved) ||
            !digest_present(row.allocation_feature_receipt_sha256) ||
            !digest_present(row.feature_geometry_receipt_sha256) ||
            row.atom_index_offset != expected_offset ||
            row.atom_index_offset > input.feature_atom_index_count ||
            row.atom_index_count == 0 ||
            row.atom_index_count >
                input.feature_atom_index_count - row.atom_index_offset ||
            !valid_count(
                row.kind, static_cast<std::size_t>(row.atom_index_count)) ||
            !allocation_contains(row)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 producer feature row is malformed or undeclared");
        }
        if (row_index != 0) {
            const auto &previous = input.feature_geometry_rows[row_index - 1];
            const int receipt_order = std::memcmp(
                previous.allocation_feature_receipt_sha256,
                row.allocation_feature_receipt_sha256, 32);
            if (previous.kind > row.kind ||
                (previous.kind == row.kind && receipt_order >= 0)) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "fixed64 producer feature rows are not canonical");
            }
        }
        const uint64_t denominator = is_ligand_feature(row.kind)
            ? admission.ligand_atom_count
            : admission.receptor_atom_count;
        CanonicalHash receipt("betelgeuze.fixed64_feature_geometry/native-v1");
        receipt.string(
            "betelgeuze.engine_v2_mixed64_native_feature_geometry/1.0.0");
        receipt.byte(static_cast<uint8_t>(row.kind));
        receipt.digest(row.allocation_feature_receipt_sha256);
        receipt.u64(row.atom_index_count);
        for (uint64_t local = 0; local < row.atom_index_count; ++local) {
            const uint64_t atom = input.feature_atom_indices[
                static_cast<std::size_t>(row.atom_index_offset + local)];
            if (atom >= denominator) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "fixed64 producer feature atom exceeds its denominator");
            }
            for (uint64_t earlier = 0; earlier < local; ++earlier) {
                if (atom == input.feature_atom_indices[
                                static_cast<std::size_t>(
                                    row.atom_index_offset + earlier)]) {
                    return fail(
                        BG_STATUS_INVALID_ARGUMENT,
                        "fixed64 producer feature atom is duplicated");
                }
            }
            receipt.u64(atom);
        }
        receipt.byte(UINT8_C(0));
        const auto observed = receipt.finish();
        if (std::memcmp(
                observed.data(), row.feature_geometry_receipt_sha256, 32) !=
            0) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 producer feature geometry receipt is invalid");
        }
        inventory.digest(row.feature_geometry_receipt_sha256);
        expected_offset += row.atom_index_count;
    }
    const auto observed_inventory = inventory.finish();
    if (expected_offset != input.feature_atom_index_count ||
        std::memcmp(
            observed_inventory.data(),
            input.feature_geometry_inventory_sha256, 32) != 0) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 producer feature inventory receipt is invalid");
    }
    return BG_STATUS_OK;
}

template <typename Type>
[[nodiscard]] bg_status append_range(
    std::vector<MemoryRange> *ranges,
    const Type *pointer,
    std::size_t count,
    const char *message) {
    MemoryRange range{};
    if (!make_range(pointer, count, &range)) {
        return fail(BG_STATUS_CAPACITY_OVERFLOW, message);
    }
    if (range.begin != range.end) ranges->push_back(range);
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status validate_memory_ranges(
    const bg_context &context,
    const bg_docking_geometric_admission_v1 &admission,
    const bg_docking_fixed64_producer_input_v1 &input,
    const bg_docking_fixed64_producer_output_v1 &output,
    const ValidatedInput &validated) {
    std::vector<MemoryRange> inputs;
    std::vector<MemoryRange> outputs;
    inputs.reserve(64);
    outputs.reserve(5);
    bg_status status = append_range(
        &inputs, &context, 1, "fixed64 producer context range overflowed");
    if (status != BG_STATUS_OK) return status;
    status = append_range(
        &inputs, &admission, 1,
        "fixed64 producer admission range overflowed");
    if (status != BG_STATUS_OK) return status;
    status = append_range(
        &inputs, &input, 1, "fixed64 producer input range overflowed");
    if (status != BG_STATUS_OK) return status;
    status = append_range(
        &inputs, input.allocation_input, 1,
        "fixed64 producer allocation descriptor range overflowed");
    if (status != BG_STATUS_OK) return status;
    const auto &allocation = *input.allocation_input;
    status = append_range(
        &inputs, allocation.atomic_features,
        static_cast<std::size_t>(allocation.atomic_feature_count),
        "fixed64 producer allocation feature range overflowed");
    if (status != BG_STATUS_OK) return status;
    status = append_range(
        &inputs, allocation.v7_control_sources,
        static_cast<std::size_t>(allocation.v7_control_source_count),
        "fixed64 producer allocation V7 range overflowed");
    if (status != BG_STATUS_OK) return status;
    status = append_range(
        &inputs, allocation.conformer_sources,
        static_cast<std::size_t>(allocation.conformer_source_count),
        "fixed64 producer allocation conformer range overflowed");
    if (status != BG_STATUS_OK) return status;
    status = append_range(
        &inputs, allocation.retained_sources,
        static_cast<std::size_t>(allocation.retained_source_count),
        "fixed64 producer allocation retained range overflowed");
    if (status != BG_STATUS_OK) return status;
    status = append_range(
        &inputs, input.v7_control_sources,
        static_cast<std::size_t>(input.v7_control_source_count),
        "fixed64 producer V7 source range overflowed");
    if (status != BG_STATUS_OK) return status;
    status = append_range(
        &inputs, input.conformer_sources,
        static_cast<std::size_t>(input.conformer_source_count),
        "fixed64 producer conformer source range overflowed");
    if (status != BG_STATUS_OK) return status;
    status = append_range(
        &inputs, input.retained_sources,
        static_cast<std::size_t>(input.retained_source_count),
        "fixed64 producer retained source range overflowed");
    if (status != BG_STATUS_OK) return status;
    status = append_range(
        &inputs, input.feature_geometry_rows,
        static_cast<std::size_t>(input.feature_geometry_count),
        "fixed64 producer feature row range overflowed");
    if (status != BG_STATUS_OK) return status;
    status = append_range(
        &inputs, input.feature_atom_indices,
        static_cast<std::size_t>(input.feature_atom_index_count),
        "fixed64 producer feature index range overflowed");
    if (status != BG_STATUS_OK) return status;
    const auto append_source_coordinates = [&](
        const bg_docking_fixed64_coordinate_source_v1 &source) -> bg_status {
        const auto count = static_cast<std::size_t>(source.ligand_atom_count);
        for (const double *channel : {
                 source.x_angstrom, source.y_angstrom, source.z_angstrom}) {
            const bg_status channel_status = append_range(
                &inputs, channel, count,
                "fixed64 producer source coordinate range overflowed");
            if (channel_status != BG_STATUS_OK) return channel_status;
        }
        return BG_STATUS_OK;
    };
    if (input.exact_v11_source != nullptr) {
        status = append_range(
            &inputs, input.exact_v11_source, 1,
            "fixed64 producer exact source range overflowed");
        if (status != BG_STATUS_OK) return status;
        status = append_source_coordinates(*input.exact_v11_source);
        if (status != BG_STATUS_OK) return status;
    }
    for (uint64_t index = 0; index < input.v7_control_source_count; ++index) {
        status = append_source_coordinates(input.v7_control_sources[index].payload);
        if (status != BG_STATUS_OK) return status;
    }
    for (uint64_t index = 0; index < input.conformer_source_count; ++index) {
        status = append_source_coordinates(input.conformer_sources[index].payload);
        if (status != BG_STATUS_OK) return status;
    }
    for (uint64_t index = 0; index < input.retained_source_count; ++index) {
        status = append_source_coordinates(input.retained_sources[index].payload);
        if (status != BG_STATUS_OK) return status;
    }
    status = append_range(
        &outputs, &output, 1, "fixed64 producer output range overflowed");
    if (status != BG_STATUS_OK) return status;
    status = append_range(
        &outputs, output.rows, kCandidateCount,
        "fixed64 producer row range overflowed");
    if (status != BG_STATUS_OK) return status;
    for (double *channel : {
             output.x_angstrom, output.y_angstrom, output.z_angstrom}) {
        status = append_range(
            &outputs, channel, validated.coordinate_count,
            "fixed64 producer output coordinate range overflowed");
        if (status != BG_STATUS_OK) return status;
    }
    for (std::size_t left = 0; left < outputs.size(); ++left) {
        for (std::size_t right = left + 1; right < outputs.size(); ++right) {
            if (overlaps(outputs[left], outputs[right])) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "fixed64 producer output ranges overlap");
            }
        }
        for (MemoryRange source : inputs) {
            if (overlaps(outputs[left], source)) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "fixed64 producer input and output ranges overlap");
            }
        }
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status validate_descriptors(
    const bg_context &context,
    const bg_docking_geometric_admission_v1 &admission,
    const bg_docking_fixed64_producer_input_v1 &input,
    const bg_docking_fixed64_producer_output_v1 &output,
    ValidatedInput *validated) {
    bg_status status = validate_descriptor_header(
        input.struct_size, sizeof(input), input.abi_version,
        "fixed64 producer input size does not match ABI v1",
        "fixed64 producer input ABI version does not match");
    if (status != BG_STATUS_OK) return status;
    status = validate_descriptor_header(
        output.struct_size, sizeof(output), output.abi_version,
        "fixed64 producer output size does not match ABI v1",
        "fixed64 producer output ABI version does not match");
    if (status != BG_STATUS_OK) return status;
    if (input.allocation_input == nullptr ||
        !pointer_is_aligned(input.allocation_input) ||
        !reserved_is_zero(input.reserved) ||
        !reserved_is_zero(output.reserved) ||
        !std::all_of(
            std::begin(output.reserved0), std::end(output.reserved0),
            [](uint8_t value) { return value == UINT8_C(0); }) ||
        context.backend != admission.backend ||
        context.unit_system != admission.unit_system ||
        context.device_ordinal != admission.device_ordinal ||
        admission.provider_state == nullptr) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 producer descriptors or context binding are invalid");
    }
    if (admission.ligand_atom_count == 0 ||
        admission.ligand_atom_count > kMaximumLigandAtoms ||
        admission.receptor_atom_count == 0 ||
        admission.receptor_x_angstrom.size() !=
            static_cast<std::size_t>(admission.receptor_atom_count) ||
        admission.ligand_vdw_radius_angstrom.size() !=
            static_cast<std::size_t>(admission.ligand_atom_count)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 producer admission denominator is invalid");
    }
    validated->ligand_count =
        static_cast<std::size_t>(admission.ligand_atom_count);
    if (validated->ligand_count >
        std::numeric_limits<std::size_t>::max() / kCandidateCount) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "fixed64 producer coordinate denominator overflowed");
    }
    validated->coordinate_count = kCandidateCount * validated->ligand_count;
    if (output.row_capacity < kCandidateCount || output.rows == nullptr ||
        !pointer_is_aligned(output.rows) ||
        output.coordinate_capacity < validated->coordinate_count ||
        output.x_angstrom == nullptr || output.y_angstrom == nullptr ||
        output.z_angstrom == nullptr ||
        !pointer_is_aligned(output.x_angstrom) ||
        !pointer_is_aligned(output.y_angstrom) ||
        !pointer_is_aligned(output.z_angstrom)) {
        return fail(
            BG_STATUS_BUFFER_TOO_SMALL,
            "fixed64 producer output requires exact rows and coordinates");
    }
    if (output.result_dependent_input_consumed != UINT8_C(0) ||
        output.fallback_allowed != UINT8_C(0) ||
        output.multi_anchor_consumed != UINT8_C(0) ||
        output.molecular_execution_authorized != UINT8_C(0) ||
        output.reservation_authorized != UINT8_C(0) ||
        output.benchmark_execution_authorized != UINT8_C(0) ||
        output.existing_rank_auto_change_authorized != UINT8_C(0) ||
        output.customer_pose_emission_authorized != UINT8_C(0) ||
        output.production_claim_authorized != UINT8_C(0) ||
        output.scientific_claim_authorized != UINT8_C(0)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 producer output cannot carry authority input");
    }
    const Vec3 normal{
        input.pocket_normal[0], input.pocket_normal[1], input.pocket_normal[2]};
    if (!normalize(normal, &validated->pocket_normal)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 producer pocket normal is degenerate");
    }
    status = rebuild_allocation(*input.allocation_input, validated);
    if (status != BG_STATUS_OK) return status;
    status = validate_source_bundle(input);
    if (status != BG_STATUS_OK) return status;
    status = validate_feature_shape(input, *input.allocation_input, admission);
    if (status != BG_STATUS_OK) return status;
    status = validate_admission_identity(admission, *input.allocation_input);
    if (status != BG_STATUS_OK) return status;
    return validate_memory_ranges(
        context, admission, input, output, *validated);
}

[[nodiscard]] bg_status place_indexed(
    const bg_context &context,
    const bg_docking_geometric_admission_v1 &admission,
    const ValidatedInput &validated,
    const bg_docking_fixed64_coordinate_source_v1 &source,
    std::size_t slot,
    std::vector<double> *x,
    std::vector<double> *y,
    std::vector<double> *z,
    bg_docking_fixed64_producer_row_v1 *row) {
    bg_docking_fixed64_indexed_so3_input_v1 descriptor{};
    descriptor.struct_size = sizeof(descriptor);
    descriptor.abi_version = BG_ABI_VERSION;
    std::copy(
        validated.allocation_inventory.begin(),
        validated.allocation_inventory.end(),
        descriptor.allocation_inventory_sha256);
    std::copy(
        validated.allocation_receipt.begin(),
        validated.allocation_receipt.end(),
        descriptor.allocation_receipt_sha256);
    descriptor.allocation_row_count = kCandidateCount;
    descriptor.allocation_rows = validated.allocation_rows.data();
    descriptor.slot_index = static_cast<uint32_t>(slot);
    descriptor.source = source.source;
    descriptor.ligand_atom_count = source.ligand_atom_count;
    descriptor.source_x_angstrom = source.x_angstrom;
    descriptor.source_y_angstrom = source.y_angstrom;
    descriptor.source_z_angstrom = source.z_angstrom;
    std::copy(
        admission.pocket_center_angstrom.begin(),
        admission.pocket_center_angstrom.end(),
        descriptor.pocket_center_angstrom);
    descriptor.pocket_normal[0] = validated.pocket_normal.x;
    descriptor.pocket_normal[1] = validated.pocket_normal.y;
    descriptor.pocket_normal[2] = validated.pocket_normal.z;
    const std::size_t offset = slot * validated.ligand_count;
    bg_docking_fixed64_indexed_so3_output_v1 placed{};
    placed.struct_size = sizeof(placed);
    placed.abi_version = BG_ABI_VERSION;
    placed.coordinate_capacity = validated.ligand_count;
    placed.x_angstrom = x->data() + offset;
    placed.y_angstrom = y->data() + offset;
    placed.z_angstrom = z->data() + offset;
    const bg_status status = bg_docking_fixed64_indexed_so3_v1_place(
        &context, &descriptor, &placed);
    if (status != BG_STATUS_OK) return status;
    row->component_failure_code = placed.failure_code;
    std::copy_n(
        placed.placement_receipt_sha256, 32,
        row->placement_receipt_sha256);
    if (placed.status == BG_DOCKING_FIXED64_INDEXED_SO3_TYPED_FAILURE) {
        mark_failure(
            BG_DOCKING_FIXED64_PRODUCER_FAILURE_INDEXED_SO3_TYPED_FAILURE,
            placed.failure_code, row);
        return BG_STATUS_OK;
    }
    if (placed.status != BG_DOCKING_FIXED64_INDEXED_SO3_PLACED ||
        placed.coordinates_written != UINT8_C(1) ||
        placed.source_identity_verified != UINT8_C(1) ||
        placed.allocation_identity_verified != UINT8_C(1) ||
        placed.result_dependent_input_consumed != UINT8_C(0) ||
        placed.denominator_preserved != UINT8_C(1) ||
        placed.molecular_execution_authorized != UINT8_C(0) ||
        placed.reservation_authorized != UINT8_C(0) ||
        placed.benchmark_execution_authorized != UINT8_C(0) ||
        placed.production_claim_authorized != UINT8_C(0)) {
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "fixed64 producer indexed placement violated its boundary");
    }
    row->status = BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED;
    row->failure_code = BG_DOCKING_FIXED64_PRODUCER_FAILURE_NONE;
    row->coordinates_available = UINT8_C(1);
    std::copy_n(
        placed.output_coordinate_sha256, 32,
        row->output_coordinate_sha256);
    const auto proposal = generated_proposal_sha256(
        validated.allocation_receipt,
        validated.allocation_rows[slot],
        source_payload_sha256(source),
        row->placement_receipt_sha256,
        row->output_coordinate_sha256);
    std::copy(
        proposal.begin(), proposal.end(), row->output_proposal_sha256);
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status place_single_anchor(
    const bg_context &context,
    const bg_docking_geometric_admission_v1 &admission,
    const bg_docking_fixed64_producer_input_v1 &input,
    const ValidatedInput &validated,
    const bg_docking_fixed64_coordinate_source_v1 &source,
    std::size_t slot,
    std::vector<double> *x,
    std::vector<double> *y,
    std::vector<double> *z,
    bg_docking_fixed64_producer_row_v1 *row) {
    bg_docking_fixed64_single_anchor_input_v1 descriptor{};
    descriptor.struct_size = sizeof(descriptor);
    descriptor.abi_version = BG_ABI_VERSION;
    descriptor.allocation_input = input.allocation_input;
    descriptor.slot_index = static_cast<uint32_t>(slot);
    descriptor.source = source.source;
    descriptor.ligand_atom_count = source.ligand_atom_count;
    descriptor.source_x_angstrom = source.x_angstrom;
    descriptor.source_y_angstrom = source.y_angstrom;
    descriptor.source_z_angstrom = source.z_angstrom;
    descriptor.feature_geometry_count = input.feature_geometry_count;
    descriptor.feature_geometry_rows = input.feature_geometry_rows;
    descriptor.feature_atom_index_count = input.feature_atom_index_count;
    descriptor.feature_atom_indices = input.feature_atom_indices;
    std::copy_n(
        input.feature_geometry_inventory_sha256, 32,
        descriptor.feature_geometry_inventory_sha256);
    const std::size_t offset = slot * validated.ligand_count;
    bg_docking_fixed64_single_anchor_output_v1 placed{};
    placed.struct_size = sizeof(placed);
    placed.abi_version = BG_ABI_VERSION;
    placed.coordinate_capacity = validated.ligand_count;
    placed.x_angstrom = x->data() + offset;
    placed.y_angstrom = y->data() + offset;
    placed.z_angstrom = z->data() + offset;
    const bg_status status =
        fixed64_single_anchor::place_for_shared_admission(
            context, admission, descriptor, &placed);
    if (status != BG_STATUS_OK) return status;
    row->component_failure_code = placed.failure_code;
    std::copy_n(
        placed.placement_receipt_sha256, 32,
        row->placement_receipt_sha256);
    if (placed.status == BG_DOCKING_FIXED64_SINGLE_ANCHOR_TYPED_FAILURE) {
        mark_failure(
            BG_DOCKING_FIXED64_PRODUCER_FAILURE_SINGLE_ANCHOR_TYPED_FAILURE,
            placed.failure_code, row);
        return BG_STATUS_OK;
    }
    if (placed.status != BG_DOCKING_FIXED64_SINGLE_ANCHOR_PLACED ||
        placed.coordinates_written != UINT8_C(1) ||
        placed.source_identity_verified != UINT8_C(1) ||
        placed.allocation_identity_verified != UINT8_C(1) ||
        placed.feature_identity_verified != UINT8_C(1) ||
        placed.geometric_identity_verified != UINT8_C(0) ||
        placed.steric_precheck_passed != UINT8_C(0) ||
        digest_present(
            placed.geometric_admission.row_receipt_sha256) ||
        digest_present(
            placed.geometric_admission_batch_receipt_sha256) ||
        placed.result_dependent_input_consumed != UINT8_C(0) ||
        placed.fallback_allowed != UINT8_C(0) ||
        placed.multi_anchor_consumed != UINT8_C(0) ||
        placed.denominator_preserved != UINT8_C(1) ||
        placed.molecular_execution_authorized != UINT8_C(0) ||
        placed.reservation_authorized != UINT8_C(0) ||
        placed.benchmark_execution_authorized != UINT8_C(0) ||
        placed.existing_rank_auto_change_authorized != UINT8_C(0) ||
        placed.customer_pose_emission_authorized != UINT8_C(0) ||
        placed.production_claim_authorized != UINT8_C(0) ||
        placed.scientific_claim_authorized != UINT8_C(0)) {
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "fixed64 producer single-anchor placement violated its boundary");
    }
    row->status = BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED;
    row->failure_code = BG_DOCKING_FIXED64_PRODUCER_FAILURE_NONE;
    row->coordinates_available = UINT8_C(1);
    std::copy_n(
        placed.output_coordinate_sha256, 32,
        row->output_coordinate_sha256);
    const auto proposal = generated_proposal_sha256(
        validated.allocation_receipt,
        validated.allocation_rows[slot],
        source_payload_sha256(source),
        row->placement_receipt_sha256,
        row->output_coordinate_sha256);
    std::copy(
        proposal.begin(), proposal.end(), row->output_proposal_sha256);
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status generate_rows(
    const bg_context &context,
    const bg_docking_geometric_admission_v1 &admission,
    const bg_docking_fixed64_producer_input_v1 &input,
    const ValidatedInput &validated,
    std::array<bg_docking_fixed64_producer_row_v1, kCandidateCount> *rows,
    std::array<bg_docking_geometric_admission_candidate_state, kCandidateCount>
        *states,
    std::vector<double> *x,
    std::vector<double> *y,
    std::vector<double> *z,
    std::size_t *generated_count) {
    states->fill(
        BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_UPSTREAM_FAILURE);
    *generated_count = 0;
    for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
        const auto &allocation = validated.allocation_rows[slot];
        auto &row = (*rows)[slot];
        initialize_row(allocation, validated.ligand_count, context.backend, &row);
        if (allocation.slot_index != slot ||
            placement_kind(allocation.lane) ==
                BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_NONE) {
            return fail(
                BG_STATUS_INTERNAL_ERROR,
                "fixed64 producer allocation row is not canonical");
        }
        const auto *source = source_for_row(input, allocation);
        if (source != nullptr) {
            bind_source(*source, &row);
            if (!source_matches_parent(*source, allocation)) {
                return fail(
                    BG_STATUS_INTERNAL_ERROR,
                    "fixed64 producer source disagrees with allocation parent");
            }
        }
        if (allocation.status != BG_DOCKING_FIXED64_ALLOCATION_ROW_READY ||
            allocation.generation_eligible != UINT8_C(1)) {
            mark_failure(
                BG_DOCKING_FIXED64_PRODUCER_FAILURE_ALLOCATION_INELIGIBLE,
                0, &row);
            continue;
        }
        if (source == nullptr) {
            mark_failure(
                BG_DOCKING_FIXED64_PRODUCER_FAILURE_SOURCE_NOT_AVAILABLE,
                0, &row);
            continue;
        }
        if (source->ligand_atom_count != validated.ligand_count) {
            mark_failure(
                BG_DOCKING_FIXED64_PRODUCER_FAILURE_LIGAND_DENOMINATOR_MISMATCH,
                0, &row);
            continue;
        }
        bg_status status = BG_STATUS_OK;
        if (row.placement_kind ==
            BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_EXACT_PASSTHROUGH) {
            const std::size_t offset = slot * validated.ligand_count;
            std::copy_n(
                source->x_angstrom, validated.ligand_count,
                x->data() + offset);
            std::copy_n(
                source->y_angstrom, validated.ligand_count,
                y->data() + offset);
            std::copy_n(
                source->z_angstrom, validated.ligand_count,
                z->data() + offset);
            const auto placement = passthrough_receipt(
                validated.allocation_receipt, allocation, *source,
                context.backend);
            std::copy(
                placement.begin(), placement.end(),
                row.placement_receipt_sha256);
            std::copy_n(
                source->source.coordinate_sha256, 32,
                row.output_coordinate_sha256);
            std::copy_n(
                source->source.proposal_sha256, 32,
                row.output_proposal_sha256);
            row.status = BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED;
            row.failure_code = BG_DOCKING_FIXED64_PRODUCER_FAILURE_NONE;
            row.coordinates_available = UINT8_C(1);
        } else if (row.placement_kind ==
                   BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_INDEXED_SO3) {
            status = place_indexed(
                context, admission, validated, *source, slot,
                x, y, z, &row);
        } else if (!selected_feature_geometry_available(input, allocation)) {
            mark_failure(
                BG_DOCKING_FIXED64_PRODUCER_FAILURE_FEATURE_GEOMETRY_NOT_AVAILABLE,
                0, &row);
        } else {
            status = place_single_anchor(
                context, admission, input, validated, *source, slot,
                x, y, z, &row);
        }
        if (status != BG_STATUS_OK) return status;
        if (row.status == BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED) {
            (*states)[slot] =
                BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_EVALUATE;
            ++*generated_count;
        }
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status apply_shared_admission(
    const bg_context &context,
    const bg_docking_geometric_admission_v1 &admission,
    const ValidatedInput &validated,
    const std::array<
        bg_docking_geometric_admission_candidate_state, kCandidateCount>
        &states,
    const std::vector<double> &x,
    const std::vector<double> &y,
    const std::vector<double> &z,
    std::array<bg_docking_fixed64_producer_row_v1, kCandidateCount> *rows,
    std::array<uint8_t, 32> *batch_receipt) {
    bg_docking_geometric_admission_candidate_batch_soa_v1 candidates{};
    candidates.struct_size = sizeof(candidates);
    candidates.abi_version = BG_ABI_VERSION;
    candidates.candidate_count = kCandidateCount;
    candidates.ligand_atom_count = validated.ligand_count;
    candidates.unit_system = admission.unit_system;
    candidates.candidate_state = states.data();
    candidates.x_angstrom = x.data();
    candidates.y_angstrom = y.data();
    candidates.z_angstrom = z.data();
    std::array<bg_docking_geometric_admission_row_v1, kCandidateCount>
        geometric_rows{};
    bg_docking_geometric_admission_output_v1 output{};
    output.struct_size = sizeof(output);
    output.abi_version = BG_ABI_VERSION;
    output.row_capacity = kCandidateCount;
    output.unit_system = admission.unit_system;
    output.rows = geometric_rows.data();
    const bg_status status =
        bg_docking_geometric_admission_v1_evaluate_fixed64(
            &context, &admission, &candidates, &output);
    if (status != BG_STATUS_OK) return status;
    if (output.row_count != kCandidateCount ||
        output.molecular_execution_authorized != UINT8_C(0) ||
        output.reservation_authorized != UINT8_C(0) ||
        output.benchmark_execution_authorized != UINT8_C(0) ||
        output.existing_rank_auto_change_authorized != UINT8_C(0) ||
        output.customer_pose_emission_authorized != UINT8_C(0) ||
        output.production_claim_authorized != UINT8_C(0) ||
        output.scientific_claim_authorized != UINT8_C(0)) {
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "fixed64 producer shared admission violated its authority boundary");
    }
    for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
        const bool generated = states[slot] ==
            BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_EVALUATE;
        const auto &geometric = geometric_rows[slot];
        if (geometric.slot_index != slot ||
            (generated &&
             geometric.status != BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED) ||
            (!generated &&
             geometric.status !=
                 BG_DOCKING_GEOMETRIC_ADMISSION_ROW_UPSTREAM_FAILURE)) {
            return fail(
                BG_STATUS_INTERNAL_ERROR,
                "fixed64 producer shared admission changed candidate state");
        }
        (*rows)[slot].geometric_admission = geometric;
        (*rows)[slot].steric_precheck_passed = geometric.rank_eligible;
        (*rows)[slot].geometric_identity_verified = UINT8_C(1);
    }
    std::copy_n(output.batch_receipt_sha256, 32, batch_receipt->begin());
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status run(
    const bg_context &context,
    const bg_docking_geometric_admission_v1 &admission,
    const bg_docking_fixed64_producer_input_v1 &input,
    bg_docking_fixed64_producer_output_v1 *output) {
    ValidatedInput validated{};
    bg_status status = validate_descriptors(
        context, admission, input, *output, &validated);
    if (status != BG_STATUS_OK) return status;
    const auto source_bundle = source_bundle_sha256(
        input, admission, validated.pocket_normal,
        validated.allocation_receipt);
    std::array<bg_docking_fixed64_producer_row_v1, kCandidateCount> rows{};
    std::array<
        bg_docking_geometric_admission_candidate_state, kCandidateCount>
        states{};
    std::vector<double> x(validated.coordinate_count, 0.0);
    std::vector<double> y(validated.coordinate_count, 0.0);
    std::vector<double> z(validated.coordinate_count, 0.0);
    std::size_t generated_count = 0;
    status = generate_rows(
        context, admission, input, validated, &rows, &states,
        &x, &y, &z, &generated_count);
    if (status != BG_STATUS_OK) return status;
    std::array<uint8_t, 32> geometric_batch{};
    status = apply_shared_admission(
        context, admission, validated, states, x, y, z, &rows,
        &geometric_batch);
    if (status != BG_STATUS_OK) return status;
    for (auto &row : rows) {
        const auto receipt = producer_row_receipt(
            validated.allocation_receipt, source_bundle, row);
        std::copy(receipt.begin(), receipt.end(), row.row_receipt_sha256);
    }
    const auto batch = producer_batch_receipt(
        validated.allocation_inventory, validated.allocation_receipt,
        source_bundle, geometric_batch, rows, generated_count,
        context.backend);
    const std::size_t bytes = validated.coordinate_count * sizeof(double);
    std::memcpy(output->rows, rows.data(), sizeof(rows));
    std::memcpy(output->x_angstrom, x.data(), bytes);
    std::memcpy(output->y_angstrom, y.data(), bytes);
    std::memcpy(output->z_angstrom, z.data(), bytes);
    bg_docking_fixed64_producer_output_v1 committed{};
    committed.struct_size = output->struct_size;
    committed.abi_version = output->abi_version;
    committed.row_capacity = output->row_capacity;
    committed.row_count = kCandidateCount;
    committed.coordinate_capacity = output->coordinate_capacity;
    committed.coordinate_count = validated.coordinate_count;
    committed.unit_system = admission.unit_system;
    committed.backend = context.backend;
    committed.rows = output->rows;
    committed.x_angstrom = output->x_angstrom;
    committed.y_angstrom = output->y_angstrom;
    committed.z_angstrom = output->z_angstrom;
    committed.generated_count = generated_count;
    committed.typed_failure_count = kCandidateCount - generated_count;
    std::copy(
        validated.allocation_inventory.begin(),
        validated.allocation_inventory.end(),
        committed.allocation_inventory_sha256);
    std::copy(
        validated.allocation_receipt.begin(),
        validated.allocation_receipt.end(),
        committed.allocation_receipt_sha256);
    std::copy(
        source_bundle.begin(), source_bundle.end(),
        committed.source_bundle_receipt_sha256);
    std::copy(
        geometric_batch.begin(), geometric_batch.end(),
        committed.geometric_admission_batch_receipt_sha256);
    std::copy(
        batch.begin(), batch.end(),
        committed.producer_batch_receipt_sha256);
    committed.result_dependent_input_consumed = UINT8_C(0);
    committed.fallback_allowed = UINT8_C(0);
    committed.multi_anchor_consumed = UINT8_C(0);
    committed.denominator_preserved = UINT8_C(1);
    committed.molecular_execution_authorized = UINT8_C(0);
    committed.reservation_authorized = UINT8_C(0);
    committed.benchmark_execution_authorized = UINT8_C(0);
    committed.existing_rank_auto_change_authorized = UINT8_C(0);
    committed.customer_pose_emission_authorized = UINT8_C(0);
    committed.production_claim_authorized = UINT8_C(0);
    committed.scientific_claim_authorized = UINT8_C(0);
    *output = committed;
    return BG_STATUS_OK;
}

}  // namespace
}  // namespace betelgeuze::native::docking::fixed64_producer

using namespace betelgeuze::native;

extern "C" BG_API bg_status BG_CALL
bg_docking_fixed64_producer_input_v1_init(
    bg_docking_fixed64_producer_input_v1 *input,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            input, caller_struct_size, sizeof(*input), caller_abi_version,
            "fixed64 producer input initializer pointer is null",
            "fixed64 producer input initializer size does not match",
            "fixed64 producer input initializer ABI version does not match");
        if (status != BG_STATUS_OK) return status;
        *input = bg_docking_fixed64_producer_input_v1{};
        input->struct_size = static_cast<uint32_t>(sizeof(*input));
        input->abi_version = BG_ABI_VERSION;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL
bg_docking_fixed64_producer_output_v1_init(
    bg_docking_fixed64_producer_output_v1 *output,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            output, caller_struct_size, sizeof(*output), caller_abi_version,
            "fixed64 producer output initializer pointer is null",
            "fixed64 producer output initializer size does not match",
            "fixed64 producer output initializer ABI version does not match");
        if (status != BG_STATUS_OK) return status;
        *output = bg_docking_fixed64_producer_output_v1{};
        output->struct_size = static_cast<uint32_t>(sizeof(*output));
        output->abi_version = BG_ABI_VERSION;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_docking_fixed64_producer_v1_run(
    const bg_context *context,
    const bg_docking_geometric_admission_v1 *admission,
    const bg_docking_fixed64_producer_input_v1 *input,
    bg_docking_fixed64_producer_output_v1 *output) BG_NOEXCEPT {
    using namespace betelgeuze::native::docking::fixed64_producer;
    return guarded_status([&]() -> bg_status {
        if (context == nullptr || admission == nullptr || input == nullptr ||
            output == nullptr || !pointer_is_aligned(context) ||
            !pointer_is_aligned(admission) || !pointer_is_aligned(input) ||
            !pointer_is_aligned(output)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 producer descriptors must be non-null and aligned");
        }
        return run(*context, *admission, *input, output);
    });
}
