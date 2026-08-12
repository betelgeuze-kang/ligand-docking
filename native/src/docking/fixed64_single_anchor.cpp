#include "../dynamics/sha256.hpp"
#include "../hip/provider.h"
#include "../internal.hpp"
#include "../rust/provider.h"
#include "fixed64_single_anchor_provider.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <vector>

#ifndef BG_HAS_HIP_SAFE_PROVIDER
#  define BG_HAS_HIP_SAFE_PROVIDER 0
#endif
#ifndef BG_ENABLE_HIP
#  define BG_ENABLE_HIP 0
#endif

namespace betelgeuze::native::docking::fixed64_single_anchor {
namespace {

using dynamics::Sha256;

constexpr std::size_t kCandidateCount = BG_DOCKING_FIXED64_CANDIDATE_COUNT;
constexpr std::size_t kMaximumLigandAtoms = 512;
constexpr std::size_t kMaximumReceptorAtoms = 4096;
constexpr std::size_t kMaximumFeatureRows = 3072;
constexpr std::size_t kMaximumFeatureAtomIndices = 65536;
constexpr double kMaximumCoordinateAngstrom = 100'000.0;
constexpr double kGeometryEpsilon = 1.0e-12;
constexpr double kPi = 3.141592653589793238462643383279502884;
constexpr char kFeatureSchema[] =
    "betelgeuze.engine_v2_mixed64_native_feature_geometry/1.0.0";
constexpr char kProfileId[] =
    "betelgeuze.engine_v2_mixed64_single_anchor_rigid_native/1.0.0";
constexpr char kPlacementSchema[] =
    "betelgeuze.engine_v2_native_fixed64_single_anchor_placement/1.0.0";

struct Vec3 final {
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
};

struct Quaternion final {
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
    double w = 1.0;
};

struct MemoryRange final {
    uintptr_t begin = 0;
    uintptr_t end = 0;
};

struct Generated final {
    bg_native_fixed64_single_anchor_kernel_result_v1 result{};
    std::vector<double> x;
    std::vector<double> y;
    std::vector<double> z;
};

struct SelectedFeatures final {
    const bg_docking_fixed64_feature_geometry_row_v1 *ligand = nullptr;
    const bg_docking_fixed64_feature_geometry_row_v1 *receptor = nullptr;
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
    const uintptr_t begin = reinterpret_cast<uintptr_t>(pointer);
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

[[nodiscard]] bool digest_present(const uint8_t (&digest)[32]) noexcept {
    return std::any_of(
        std::begin(digest), std::end(digest),
        [](uint8_t value) { return value != UINT8_C(0); });
}

[[nodiscard]] bool finite_coordinate(double value) noexcept {
    return std::isfinite(value) &&
           std::abs(value) <= kMaximumCoordinateAngstrom;
}

[[nodiscard]] Vec3 plus(Vec3 left, Vec3 right) noexcept {
    return {left.x + right.x, left.y + right.y, left.z + right.z};
}

[[nodiscard]] Vec3 minus(Vec3 left, Vec3 right) noexcept {
    return {left.x - right.x, left.y - right.y, left.z - right.z};
}

[[nodiscard]] Vec3 scale(Vec3 value, double factor) noexcept {
    return {value.x * factor, value.y * factor, value.z * factor};
}

[[nodiscard]] double dot(Vec3 left, Vec3 right) noexcept {
    return left.x * right.x + left.y * right.y + left.z * right.z;
}

[[nodiscard]] Vec3 cross(Vec3 left, Vec3 right) noexcept {
    return {
        left.y * right.z - left.z * right.y,
        left.z * right.x - left.x * right.z,
        left.x * right.y - left.y * right.x,
    };
}

[[nodiscard]] double norm(Vec3 value) noexcept {
    return std::hypot(std::hypot(value.x, value.y), value.z);
}

[[nodiscard]] bool normalize(Vec3 value, Vec3 *output) noexcept {
    const double maximum =
        std::max({std::abs(value.x), std::abs(value.y), std::abs(value.z)});
    if (!std::isfinite(maximum) || maximum <= kGeometryEpsilon) return false;
    const Vec3 scaled = scale(value, 1.0 / maximum);
    const double scaled_norm = norm(scaled);
    if (!std::isfinite(scaled_norm) || scaled_norm <= 0.0) return false;
    *output = scale(scaled, 1.0 / scaled_norm);
    return true;
}

[[nodiscard]] Vec3 canonical_direction(Vec3 value) noexcept {
    for (double component : {value.x, value.y, value.z}) {
        if (std::abs(component) <= kGeometryEpsilon) continue;
        if (component < 0.0) value = scale(value, -1.0);
        break;
    }
    if (value.x == 0.0) value.x = 0.0;
    if (value.y == 0.0) value.y = 0.0;
    if (value.z == 0.0) value.z = 0.0;
    return value;
}

[[nodiscard]] Quaternion canonicalize(Quaternion value, bool *ok) noexcept {
    const double maximum = std::max(
        {std::abs(value.x), std::abs(value.y), std::abs(value.z),
         std::abs(value.w)});
    if (!std::isfinite(maximum) || maximum <= kGeometryEpsilon) {
        *ok = false;
        return {};
    }
    const double scaled_norm = std::hypot(
        std::hypot(
            std::hypot(value.x / maximum, value.y / maximum),
            value.z / maximum),
        value.w / maximum);
    const double inverse = (1.0 / maximum) / scaled_norm;
    value = {
        value.x * inverse,
        value.y * inverse,
        value.z * inverse,
        value.w * inverse,
    };
    for (double component : {value.w, value.z, value.y, value.x}) {
        if (component > 0.0) break;
        if (component < 0.0) {
            value = {-value.x, -value.y, -value.z, -value.w};
            break;
        }
    }
    if (value.x == 0.0) value.x = 0.0;
    if (value.y == 0.0) value.y = 0.0;
    if (value.z == 0.0) value.z = 0.0;
    if (value.w == 0.0) value.w = 0.0;
    *ok = true;
    return value;
}

[[nodiscard]] Quaternion between(Vec3 source, Vec3 target, bool *ok) noexcept {
    Vec3 normalized_source{};
    Vec3 normalized_target{};
    if (!normalize(source, &normalized_source) ||
        !normalize(target, &normalized_target)) {
        *ok = false;
        return {};
    }
    const double cosine =
        std::clamp(dot(normalized_source, normalized_target), -1.0, 1.0);
    if (cosine >= 1.0 - 1.0e-12) {
        *ok = true;
        return {};
    }
    if (cosine <= -1.0 + 1.0e-12) {
        Vec3 reference{1.0, 0.0, 0.0};
        if (std::abs(dot(normalized_source, reference)) > 0.9) {
            reference = {0.0, 1.0, 0.0};
        }
        Vec3 axis{};
        if (!normalize(cross(normalized_source, reference), &axis)) {
            *ok = false;
            return {};
        }
        return canonicalize({axis.x, axis.y, axis.z, 0.0}, ok);
    }
    const Vec3 axis = cross(normalized_source, normalized_target);
    return canonicalize({axis.x, axis.y, axis.z, 1.0 + cosine}, ok);
}

[[nodiscard]] Quaternion rotation_about(
    Vec3 axis, double angle, bool *ok) noexcept {
    if (std::abs(angle) <= kGeometryEpsilon) {
        *ok = true;
        return {};
    }
    Vec3 normalized_axis{};
    if (!normalize(axis, &normalized_axis)) {
        *ok = false;
        return {};
    }
    const double half = 0.5 * angle;
    const double sine = std::sin(half);
    return canonicalize(
        {normalized_axis.x * sine,
         normalized_axis.y * sine,
         normalized_axis.z * sine,
         std::cos(half)},
        ok);
}

[[nodiscard]] Quaternion multiply(
    Quaternion left, Quaternion right, bool *ok) noexcept {
    return canonicalize(
        {left.w * right.x + left.x * right.w + left.y * right.z -
             left.z * right.y,
         left.w * right.y - left.x * right.z + left.y * right.w +
             left.z * right.x,
         left.w * right.z + left.x * right.y - left.y * right.x +
             left.z * right.w,
         left.w * right.w - left.x * right.x - left.y * right.y -
             left.z * right.z},
        ok);
}

[[nodiscard]] Vec3 rotate(Quaternion quaternion, Vec3 vector) noexcept {
    const Vec3 q{quaternion.x, quaternion.y, quaternion.z};
    const Vec3 twice_cross = scale(cross(q, vector), 2.0);
    return plus(plus(vector, scale(twice_cross, quaternion.w)), cross(q, twice_cross));
}

[[nodiscard]] Vec3 centroid(
    const double *x, const double *y, const double *z,
    std::size_t count) noexcept {
    Vec3 value{};
    for (std::size_t index = 0; index < count; ++index) {
        value.x += x[index];
        value.y += y[index];
        value.z += z[index];
    }
    return scale(value, 1.0 / static_cast<double>(count));
}

[[nodiscard]] bool is_ligand_feature(bg_docking_fixed64_feature_kind kind) noexcept {
    return kind == BG_DOCKING_FIXED64_FEATURE_LIGAND_DONOR ||
           kind == BG_DOCKING_FIXED64_FEATURE_LIGAND_ACCEPTOR ||
           kind == BG_DOCKING_FIXED64_FEATURE_LIGAND_POSITIVE_SITE ||
           kind == BG_DOCKING_FIXED64_FEATURE_LIGAND_NEGATIVE_SITE ||
           kind == BG_DOCKING_FIXED64_FEATURE_LIGAND_AROMATIC_PLANE ||
           kind == BG_DOCKING_FIXED64_FEATURE_LIGAND_SHAPE_AXIS;
}

[[nodiscard]] bool valid_feature_kind(bg_docking_fixed64_feature_kind kind) noexcept {
    return kind >= BG_DOCKING_FIXED64_FEATURE_LIGAND_DONOR &&
           kind <= BG_DOCKING_FIXED64_FEATURE_POCKET_SHAPE_AXIS;
}

[[nodiscard]] bool valid_feature_count(
    bg_docking_fixed64_feature_kind kind, std::size_t count) noexcept {
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
}

[[nodiscard]] std::array<uint8_t, 32> coordinate_sha256(
    const double *x, const double *y, const double *z,
    std::size_t count) noexcept {
    CanonicalHash hash("betelgeuze.fixed64_coordinates/native-v1");
    hash.size(count);
    for (std::size_t index = 0; index < count; ++index) {
        hash.vec3({x[index], y[index], z[index]});
    }
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

[[nodiscard]] std::array<uint8_t, 32> feature_receipt(
    const bg_docking_fixed64_feature_geometry_row_v1 &row,
    const uint64_t *indices) noexcept {
    CanonicalHash hash("betelgeuze.fixed64_feature_geometry/native-v1");
    hash.string(kFeatureSchema);
    hash.byte(static_cast<uint8_t>(row.kind));
    hash.digest(row.allocation_feature_receipt_sha256);
    hash.u64(row.atom_index_count);
    for (uint64_t index = 0; index < row.atom_index_count; ++index) {
        hash.u64(indices[static_cast<std::size_t>(row.atom_index_offset + index)]);
    }
    hash.byte(UINT8_C(0));
    return hash.finish();
}

[[nodiscard]] std::array<uint8_t, 32> feature_inventory_receipt(
    const bg_docking_fixed64_single_anchor_input_v1 &input) noexcept {
    CanonicalHash hash(
        "betelgeuze.fixed64_feature_geometry_inventory/native-v1");
    hash.u64(input.feature_geometry_count);
    for (uint64_t index = 0; index < input.feature_geometry_count; ++index) {
        hash.digest(input.feature_geometry_rows[index].feature_geometry_receipt_sha256);
    }
    return hash.finish();
}

[[nodiscard]] bool feature_pair_matches(
    bg_docking_fixed64_lane lane,
    bg_docking_fixed64_feature_kind ligand,
    bg_docking_fixed64_feature_kind receptor) noexcept {
    return (lane == BG_DOCKING_FIXED64_LANE_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR &&
            ligand == BG_DOCKING_FIXED64_FEATURE_LIGAND_DONOR &&
            receptor == BG_DOCKING_FIXED64_FEATURE_RECEPTOR_ACCEPTOR) ||
           (lane == BG_DOCKING_FIXED64_LANE_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR &&
            ligand == BG_DOCKING_FIXED64_FEATURE_LIGAND_ACCEPTOR &&
            receptor == BG_DOCKING_FIXED64_FEATURE_RECEPTOR_DONOR) ||
           (lane == BG_DOCKING_FIXED64_LANE_COMPLEMENTARY_CHARGE &&
            ((ligand == BG_DOCKING_FIXED64_FEATURE_LIGAND_POSITIVE_SITE &&
              receptor == BG_DOCKING_FIXED64_FEATURE_RECEPTOR_NEGATIVE_SITE) ||
             (ligand == BG_DOCKING_FIXED64_FEATURE_LIGAND_NEGATIVE_SITE &&
              receptor == BG_DOCKING_FIXED64_FEATURE_RECEPTOR_POSITIVE_SITE))) ||
           (lane == BG_DOCKING_FIXED64_LANE_AROMATIC_PLANE &&
            ligand == BG_DOCKING_FIXED64_FEATURE_LIGAND_AROMATIC_PLANE &&
            receptor == BG_DOCKING_FIXED64_FEATURE_RECEPTOR_AROMATIC_PLANE) ||
           (lane == BG_DOCKING_FIXED64_LANE_PRINCIPAL_AXIS_SHAPE &&
            ligand == BG_DOCKING_FIXED64_FEATURE_LIGAND_SHAPE_AXIS &&
            receptor == BG_DOCKING_FIXED64_FEATURE_POCKET_SHAPE_AXIS);
}

[[nodiscard]] bool allocation_contains_feature(
    const bg_docking_fixed64_allocation_input_v1 &allocation,
    const bg_docking_fixed64_feature_geometry_row_v1 &feature) noexcept {
    for (uint64_t index = 0; index < allocation.atomic_feature_count; ++index) {
        const auto &evidence = allocation.atomic_features[index];
        if (evidence.kind == feature.kind &&
            std::memcmp(
                evidence.receipt_sha256,
                feature.allocation_feature_receipt_sha256,
                32) == 0) {
            return true;
        }
    }
    return false;
}

[[nodiscard]] bg_status validate_feature_inventory(
    const bg_docking_fixed64_single_anchor_input_v1 &input,
    const bg_docking_fixed64_allocation_input_v1 &allocation,
    const bg_docking_fixed64_allocation_row_v1 &slot,
    const bg_docking_geometric_admission_v1 &admission,
    SelectedFeatures *selected) noexcept {
    if (input.feature_geometry_count == 0 ||
        input.feature_geometry_count > kMaximumFeatureRows ||
        input.feature_geometry_rows == nullptr ||
        !pointer_is_aligned(input.feature_geometry_rows) ||
        input.feature_atom_index_count == 0 ||
        input.feature_atom_index_count > kMaximumFeatureAtomIndices ||
        input.feature_atom_indices == nullptr ||
        !pointer_is_aligned(input.feature_atom_indices) ||
        !digest_present(input.feature_geometry_inventory_sha256)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "single-anchor feature inventory is absent or over capacity");
    }
    uint64_t expected_offset = 0;
    for (uint64_t row_index = 0; row_index < input.feature_geometry_count;
         ++row_index) {
        const auto &row = input.feature_geometry_rows[row_index];
        if (!valid_feature_kind(row.kind) || row.reserved0 != 0 ||
            !reserved_is_zero(row.reserved) ||
            !digest_present(row.allocation_feature_receipt_sha256) ||
            !digest_present(row.feature_geometry_receipt_sha256) ||
            row.atom_index_offset != expected_offset ||
            row.atom_index_count == 0 ||
            row.atom_index_count > input.feature_atom_index_count -
                row.atom_index_offset ||
            !valid_feature_count(
                row.kind, static_cast<std::size_t>(row.atom_index_count)) ||
            !allocation_contains_feature(allocation, row)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "single-anchor feature row is malformed or not predeclared");
        }
        if (row_index != 0) {
            const auto &previous = input.feature_geometry_rows[row_index - 1];
            const int receipt_order = std::memcmp(
                previous.allocation_feature_receipt_sha256,
                row.allocation_feature_receipt_sha256,
                32);
            if (previous.kind > row.kind ||
                (previous.kind == row.kind && receipt_order >= 0)) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "single-anchor feature rows are not canonically ordered");
            }
        }
        const uint64_t denominator = is_ligand_feature(row.kind)
            ? input.ligand_atom_count
            : admission.receptor_atom_count;
        for (uint64_t local = 0; local < row.atom_index_count; ++local) {
            const uint64_t atom = input.feature_atom_indices[
                static_cast<std::size_t>(row.atom_index_offset + local)];
            if (atom >= denominator) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "single-anchor feature atom index exceeds its denominator");
            }
            for (uint64_t earlier = 0; earlier < local; ++earlier) {
                if (atom == input.feature_atom_indices[static_cast<std::size_t>(
                                row.atom_index_offset + earlier)]) {
                    return fail(
                        BG_STATUS_INVALID_ARGUMENT,
                        "single-anchor feature atom indices are duplicated");
                }
            }
        }
        const auto observed = feature_receipt(row, input.feature_atom_indices);
        if (std::memcmp(
                observed.data(), row.feature_geometry_receipt_sha256, 32) != 0) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "single-anchor feature geometry receipt is invalid");
        }
        if (std::memcmp(
                row.allocation_feature_receipt_sha256,
                slot.selected_source_receipt_sha256[0], 32) == 0) {
            selected->ligand = &row;
        }
        if (std::memcmp(
                row.allocation_feature_receipt_sha256,
                slot.selected_source_receipt_sha256[1], 32) == 0) {
            selected->receptor = &row;
        }
        expected_offset += row.atom_index_count;
    }
    const auto inventory = feature_inventory_receipt(input);
    if (expected_offset != input.feature_atom_index_count ||
        std::memcmp(
            inventory.data(), input.feature_geometry_inventory_sha256, 32) != 0 ||
        selected->ligand == nullptr || selected->receptor == nullptr ||
        !is_ligand_feature(selected->ligand->kind) ||
        is_ligand_feature(selected->receptor->kind) ||
        !feature_pair_matches(
            slot.lane, selected->ligand->kind, selected->receptor->kind)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "single-anchor feature inventory or selected pair is cross-wired");
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status rebuild_allocation(
    const bg_docking_fixed64_single_anchor_input_v1 &input,
    std::array<bg_docking_fixed64_allocation_row_v1, kCandidateCount> *rows,
    std::array<uint8_t, 32> *inventory,
    std::array<uint8_t, 32> *receipt) noexcept {
    bg_docking_fixed64_allocation_output_v1 output{};
    output.struct_size = sizeof(output);
    output.abi_version = BG_ABI_VERSION;
    output.row_capacity = rows->size();
    output.rows = rows->data();
    const bg_status status = bg_docking_fixed64_allocation_v1_build(
        input.allocation_input, &output);
    if (status != BG_STATUS_OK) return status;
    if (output.row_count != rows->size() ||
        output.result_dependent_allocation != UINT8_C(0) ||
        output.molecular_execution_authorized != UINT8_C(0) ||
        output.reservation_authorized != UINT8_C(0) ||
        output.benchmark_execution_authorized != UINT8_C(0) ||
        output.existing_rank_auto_change_authorized != UINT8_C(0) ||
        output.customer_pose_emission_authorized != UINT8_C(0) ||
        output.production_claim_authorized != UINT8_C(0)) {
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "single-anchor allocation rebuild violated its authority boundary");
    }
    std::copy_n(output.inventory_sha256, 32, inventory->begin());
    std::copy_n(output.allocation_receipt_sha256, 32, receipt->begin());
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status validate_exact_geometry(
    const bg_docking_fixed64_single_anchor_input_v1 &input,
    const bg_docking_geometric_admission_v1 &admission) noexcept {
    const auto &exact = input.allocation_input->exact_v11_source;
    if (std::memcmp(input.source.receipt_sha256, exact.source_receipt_sha256, 32) != 0 ||
        std::memcmp(input.source.proposal_sha256, exact.proposal_sha256, 32) != 0 ||
        std::memcmp(input.source.coordinate_sha256, exact.ligand_coordinate_sha256, 32) != 0) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "single-anchor source is not the exact V1.1 source");
    }
    const auto ligand_coordinate = coordinate_sha256(
        input.source_x_angstrom,
        input.source_y_angstrom,
        input.source_z_angstrom,
        static_cast<std::size_t>(input.ligand_atom_count));
    const auto receptor_coordinate = coordinate_sha256(
        admission.receptor_x_angstrom.data(),
        admission.receptor_y_angstrom.data(),
        admission.receptor_z_angstrom.data(),
        admission.receptor_x_angstrom.size());
    const auto ligand_radii = radii_sha256(admission.ligand_vdw_radius_angstrom);
    const auto ligand_mask = heavy_mask_sha256(admission.ligand_heavy_atom_mask);
    const auto receptor_radii = radii_sha256(admission.receptor_vdw_radius_angstrom);
    if (std::memcmp(ligand_coordinate.data(), exact.ligand_coordinate_sha256, 32) != 0 ||
        std::memcmp(receptor_coordinate.data(), exact.receptor_coordinate_sha256, 32) != 0 ||
        std::memcmp(ligand_radii.data(), exact.ligand_vdw_radii_sha256, 32) != 0 ||
        std::memcmp(ligand_mask.data(), exact.ligand_heavy_atom_mask_sha256, 32) != 0 ||
        std::memcmp(receptor_radii.data(), exact.receptor_vdw_radii_sha256, 32) != 0) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "single-anchor exact source geometry is cross-wired");
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status validate_memory_ranges(
    const bg_context &context,
    const bg_docking_geometric_admission_v1 &admission,
    const bg_docking_fixed64_single_anchor_input_v1 &input,
    const bg_docking_fixed64_single_anchor_output_v1 &output) noexcept {
    const auto &allocation = *input.allocation_input;
    const std::size_t ligand_count =
        static_cast<std::size_t>(input.ligand_atom_count);
    std::array<MemoryRange, 17> ranges{};
    if (!make_range(&context, 1, &ranges[0]) ||
        !make_range(&admission, 1, &ranges[1]) ||
        !make_range(&input, 1, &ranges[2]) ||
        !make_range(&output, 1, &ranges[3]) ||
        !make_range(input.allocation_input, 1, &ranges[4]) ||
        !make_range(
            allocation.atomic_features,
            static_cast<std::size_t>(allocation.atomic_feature_count),
            &ranges[5]) ||
        !make_range(
            allocation.v7_control_sources,
            static_cast<std::size_t>(allocation.v7_control_source_count),
            &ranges[6]) ||
        !make_range(
            allocation.conformer_sources,
            static_cast<std::size_t>(allocation.conformer_source_count),
            &ranges[7]) ||
        !make_range(
            allocation.retained_sources,
            static_cast<std::size_t>(allocation.retained_source_count),
            &ranges[8]) ||
        !make_range(input.source_x_angstrom, ligand_count, &ranges[9]) ||
        !make_range(input.source_y_angstrom, ligand_count, &ranges[10]) ||
        !make_range(input.source_z_angstrom, ligand_count, &ranges[11]) ||
        !make_range(
            input.feature_geometry_rows,
            static_cast<std::size_t>(input.feature_geometry_count),
            &ranges[12]) ||
        !make_range(
            input.feature_atom_indices,
            static_cast<std::size_t>(input.feature_atom_index_count),
            &ranges[13]) ||
        !make_range(output.x_angstrom, ligand_count, &ranges[14]) ||
        !make_range(output.y_angstrom, ligand_count, &ranges[15]) ||
        !make_range(output.z_angstrom, ligand_count, &ranges[16])) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "single-anchor descriptor range overflows host address space");
    }
    for (std::size_t left = 0; left < ranges.size(); ++left) {
        for (std::size_t right = left + 1; right < ranges.size(); ++right) {
            if (overlaps(ranges[left], ranges[right])) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "single-anchor input and output ranges overlap");
            }
        }
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status validate_input(
    const bg_context &context,
    const bg_docking_geometric_admission_v1 &admission,
    const bg_docking_fixed64_single_anchor_input_v1 &input,
    const bg_docking_fixed64_single_anchor_output_v1 &output,
    std::array<bg_docking_fixed64_allocation_row_v1, kCandidateCount> *rows,
    std::array<uint8_t, 32> *allocation_inventory,
    std::array<uint8_t, 32> *allocation_receipt,
    SelectedFeatures *selected) noexcept {
    bg_status status = validate_descriptor_header(
        input.struct_size,
        sizeof(input),
        input.abi_version,
        "single-anchor input size does not match ABI v1",
        "single-anchor input ABI version does not match");
    if (status != BG_STATUS_OK) return status;
    status = validate_descriptor_header(
        output.struct_size,
        sizeof(output),
        output.abi_version,
        "single-anchor output size does not match ABI v1",
        "single-anchor output ABI version does not match");
    if (status != BG_STATUS_OK) return status;
    if (input.allocation_input == nullptr ||
        !pointer_is_aligned(input.allocation_input) || input.reserved0 != 0 ||
        !reserved_is_zero(input.reserved) || !reserved_is_zero(input.source.reserved) ||
        output.reserved0 != 0 || !reserved_is_zero(output.reserved) ||
        context.backend != admission.backend ||
        context.unit_system != admission.unit_system ||
        context.device_ordinal != admission.device_ordinal ||
        admission.provider_state == nullptr) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "single-anchor descriptors or context binding are invalid");
    }
    if (input.slot_index < 44 || input.slot_index >= 60 ||
        input.ligand_atom_count == 0 ||
        input.ligand_atom_count > kMaximumLigandAtoms ||
        input.ligand_atom_count != admission.ligand_atom_count ||
        admission.receptor_atom_count == 0 ||
        admission.receptor_atom_count > kMaximumReceptorAtoms) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "single-anchor slot or atom denominator is invalid");
    }
    if (output.coordinate_capacity < input.ligand_atom_count ||
        output.x_angstrom == nullptr || output.y_angstrom == nullptr ||
        output.z_angstrom == nullptr || !pointer_is_aligned(output.x_angstrom) ||
        !pointer_is_aligned(output.y_angstrom) ||
        !pointer_is_aligned(output.z_angstrom)) {
        return fail(
            BG_STATUS_BUFFER_TOO_SMALL,
            "single-anchor output requires aligned ligand coordinate channels");
    }
    for (const double *channel : {
             input.source_x_angstrom,
             input.source_y_angstrom,
             input.source_z_angstrom}) {
        if (channel == nullptr || !pointer_is_aligned(channel)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "single-anchor source channel is null or misaligned");
        }
        for (uint64_t atom = 0; atom < input.ligand_atom_count; ++atom) {
            if (!finite_coordinate(channel[atom])) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "single-anchor source coordinate is outside native bounds");
            }
        }
    }
    status = rebuild_allocation(
        input, rows, allocation_inventory, allocation_receipt);
    if (status != BG_STATUS_OK) return status;
    const auto &slot = (*rows)[input.slot_index];
    if (slot.status != BG_DOCKING_FIXED64_ALLOCATION_ROW_READY ||
        slot.generation_eligible != UINT8_C(1) ||
        slot.selected_source_receipt_count != 2 ||
        slot.generation_parent_role != BG_DOCKING_FIXED64_PARENT_GENERATOR_INPUT ||
        slot.declared_anchor_kind == BG_DOCKING_FIXED64_ANCHOR_NONE ||
        slot.fallback_allowed != UINT8_C(0) ||
        slot.multi_anchor_allowed != UINT8_C(0) ||
        slot.result_dependent_allocation != UINT8_C(0) ||
        slot.denominator_preserved != UINT8_C(1) ||
        slot.molecular_execution_authorized != UINT8_C(0) ||
        slot.reservation_authorized != UINT8_C(0) ||
        slot.benchmark_execution_authorized != UINT8_C(0) ||
        std::memcmp(
            slot.generation_parent_receipt_sha256,
            input.source.receipt_sha256, 32) != 0 ||
        std::memcmp(
            slot.generation_parent_proposal_sha256,
            input.source.proposal_sha256, 32) != 0 ||
        std::memcmp(
            slot.generation_parent_coordinate_sha256,
            input.source.coordinate_sha256, 32) != 0) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "single-anchor allocation slot is ineligible or cross-wired");
    }
    status = validate_exact_geometry(input, admission);
    if (status != BG_STATUS_OK) return status;
    status = validate_feature_inventory(
        input, *input.allocation_input, slot, admission, selected);
    if (status != BG_STATUS_OK) return status;
    return validate_memory_ranges(context, admission, input, output);
}

[[nodiscard]] Vec3 indexed_coordinate(
    const bg_docking_fixed64_single_anchor_input_v1 &input,
    const bg_docking_fixed64_feature_geometry_row_v1 &feature,
    const bg_docking_geometric_admission_v1 &admission,
    std::size_t local) noexcept {
    const auto atom = static_cast<std::size_t>(input.feature_atom_indices[
        static_cast<std::size_t>(feature.atom_index_offset) + local]);
    if (is_ligand_feature(feature.kind)) {
        return {
            input.source_x_angstrom[atom],
            input.source_y_angstrom[atom],
            input.source_z_angstrom[atom],
        };
    }
    return {
        admission.receptor_x_angstrom[atom],
        admission.receptor_y_angstrom[atom],
        admission.receptor_z_angstrom[atom],
    };
}

[[nodiscard]] bg_native_fixed64_single_anchor_kernel_input_v1 make_kernel_input(
    const bg_docking_fixed64_single_anchor_input_v1 &input,
    const bg_docking_fixed64_allocation_row_v1 &slot,
    const bg_docking_geometric_admission_v1 &admission,
    const SelectedFeatures &selected,
    std::vector<double> *ligand_x,
    std::vector<double> *ligand_y,
    std::vector<double> *ligand_z,
    std::vector<double> *receptor_x,
    std::vector<double> *receptor_y,
    std::vector<double> *receptor_z) {
    const auto append = [](Vec3 value, std::vector<double> *x,
                           std::vector<double> *y, std::vector<double> *z) {
        x->push_back(value.x);
        y->push_back(value.y);
        z->push_back(value.z);
    };
    for (std::size_t index = 0;
         index < static_cast<std::size_t>(selected.ligand->atom_index_count);
         ++index) {
        append(indexed_coordinate(input, *selected.ligand, admission, index),
               ligand_x, ligand_y, ligand_z);
    }
    for (std::size_t index = 0;
         index < static_cast<std::size_t>(selected.receptor->atom_index_count);
         ++index) {
        append(indexed_coordinate(input, *selected.receptor, admission, index),
               receptor_x, receptor_y, receptor_z);
    }
    bg_native_fixed64_single_anchor_kernel_input_v1 kernel{};
    kernel.struct_size = sizeof(kernel);
    kernel.abi_version = BG_RUST_CPU_PROVIDER_ABI_VERSION;
    kernel.lane = slot.lane;
    kernel.anchor_kind = slot.declared_anchor_kind;
    kernel.lane_offset = slot.lane_offset;
    kernel.ligand_atom_count = input.ligand_atom_count;
    kernel.source_x_angstrom = input.source_x_angstrom;
    kernel.source_y_angstrom = input.source_y_angstrom;
    kernel.source_z_angstrom = input.source_z_angstrom;
    kernel.ligand_feature_atom_count = ligand_x->size();
    kernel.ligand_feature_x_angstrom = ligand_x->data();
    kernel.ligand_feature_y_angstrom = ligand_y->data();
    kernel.ligand_feature_z_angstrom = ligand_z->data();
    kernel.receptor_feature_atom_count = receptor_x->size();
    kernel.receptor_feature_x_angstrom = receptor_x->data();
    kernel.receptor_feature_y_angstrom = receptor_y->data();
    kernel.receptor_feature_z_angstrom = receptor_z->data();
    std::copy(
        admission.pocket_center_angstrom.begin(),
        admission.pocket_center_angstrom.end(),
        kernel.pocket_center_angstrom);
    return kernel;
}

void write_vec3(double (&output)[3], Vec3 value) noexcept {
    output[0] = value.x;
    output[1] = value.y;
    output[2] = value.z;
}

[[nodiscard]] bool aromatic_normal(
    const double *x, const double *y, const double *z,
    std::size_t count, Vec3 *output) noexcept {
    for (std::size_t first = 0; first < count; ++first) {
        const Vec3 first_point{x[first], y[first], z[first]};
        for (std::size_t second = first + 1; second < count; ++second) {
            const Vec3 second_point{x[second], y[second], z[second]};
            for (std::size_t third = second + 1; third < count; ++third) {
                const Vec3 third_point{x[third], y[third], z[third]};
                Vec3 normal = cross(
                    minus(second_point, first_point),
                    minus(third_point, first_point));
                if (norm(normal) > kGeometryEpsilon && normalize(normal, &normal)) {
                    *output = canonical_direction(normal);
                    return true;
                }
            }
        }
    }
    return false;
}

[[nodiscard]] bool principal_axis(
    const double *x, const double *y, const double *z,
    std::size_t count, Vec3 *output) noexcept {
    const Vec3 center = centroid(x, y, z, count);
    double covariance[3][3]{};
    for (std::size_t point = 0; point < count; ++point) {
        const double components[3] = {
            x[point] - center.x,
            y[point] - center.y,
            z[point] - center.z,
        };
        for (std::size_t left = 0; left < 3; ++left) {
            for (std::size_t right = 0; right < 3; ++right) {
                covariance[left][right] += components[left] * components[right];
            }
        }
    }
    const double variance = std::max(
        {covariance[0][0], covariance[1][1], covariance[2][2]});
    if (!std::isfinite(variance) || variance <= kGeometryEpsilon) return false;
    double matrix[3][3]{};
    double eigenvectors[3][3]{};
    std::memcpy(matrix, covariance, sizeof(matrix));
    for (std::size_t index = 0; index < 3; ++index) {
        eigenvectors[index][index] = 1.0;
    }
    constexpr std::array<std::array<std::size_t, 2>, 3> pairs{{
        {{0, 1}}, {{0, 2}}, {{1, 2}},
    }};
    for (std::size_t rotation_index = 0; rotation_index < 64;
         ++rotation_index) {
        auto selected = pairs[0];
        double selected_value = std::abs(matrix[selected[0]][selected[1]]);
        for (std::size_t pair_index = 1; pair_index < pairs.size();
             ++pair_index) {
            const auto pair = pairs[pair_index];
            const double value = std::abs(matrix[pair[0]][pair[1]]);
            if (value > selected_value) {
                selected = pair;
                selected_value = value;
            }
        }
        const double scale_value = std::max(
            {std::abs(matrix[0][0]), std::abs(matrix[1][1]),
             std::abs(matrix[2][2])});
        if (selected_value <= kGeometryEpsilon * scale_value) break;
        const std::size_t first = selected[0];
        const std::size_t second = selected[1];
        const double angle = 0.5 * std::atan2(
            2.0 * matrix[first][second],
            matrix[second][second] - matrix[first][first]);
        const double cosine = std::cos(angle);
        const double sine = std::sin(angle);
        double rotation[3][3]{};
        for (std::size_t index = 0; index < 3; ++index) {
            rotation[index][index] = 1.0;
        }
        rotation[first][first] = cosine;
        rotation[second][second] = cosine;
        rotation[first][second] = sine;
        rotation[second][first] = -sine;
        double right_product[3][3]{};
        for (std::size_t row = 0; row < 3; ++row) {
            for (std::size_t column = 0; column < 3; ++column) {
                for (std::size_t inner = 0; inner < 3; ++inner) {
                    right_product[row][column] +=
                        matrix[row][inner] * rotation[inner][column];
                }
            }
        }
        double next_matrix[3][3]{};
        for (std::size_t row = 0; row < 3; ++row) {
            for (std::size_t column = 0; column < 3; ++column) {
                for (std::size_t inner = 0; inner < 3; ++inner) {
                    next_matrix[row][column] +=
                        rotation[inner][row] * right_product[inner][column];
                }
            }
        }
        std::memcpy(matrix, next_matrix, sizeof(matrix));
        double next_eigenvectors[3][3]{};
        for (std::size_t row = 0; row < 3; ++row) {
            for (std::size_t column = 0; column < 3; ++column) {
                for (std::size_t inner = 0; inner < 3; ++inner) {
                    next_eigenvectors[row][column] +=
                        eigenvectors[row][inner] * rotation[inner][column];
                }
            }
        }
        std::memcpy(eigenvectors, next_eigenvectors, sizeof(eigenvectors));
    }
    std::size_t dominant = 0;
    for (std::size_t index = 1; index < 3; ++index) {
        if (matrix[index][index] > matrix[dominant][dominant]) dominant = index;
    }
    Vec3 vector{
        eigenvectors[0][dominant],
        eigenvectors[1][dominant],
        eigenvectors[2][dominant],
    };
    if (!normalize(vector, &vector)) return false;
    const Vec3 transformed{
        covariance[0][0] * vector.x + covariance[0][1] * vector.y +
            covariance[0][2] * vector.z,
        covariance[1][0] * vector.x + covariance[1][1] * vector.y +
            covariance[1][2] * vector.z,
        covariance[2][0] * vector.x + covariance[2][1] * vector.y +
            covariance[2][2] * vector.z,
    };
    const double rayleigh = dot(vector, transformed);
    const double residual = norm(minus(transformed, scale(vector, rayleigh)));
    if (!std::isfinite(residual) ||
        residual > kGeometryEpsilon * std::max(kGeometryEpsilon, std::abs(rayleigh))) {
        return false;
    }
    *output = canonical_direction(vector);
    return true;
}

[[nodiscard]] Generated typed_failure(
    bg_docking_fixed64_single_anchor_failure failure) {
    Generated generated{};
    generated.result.status = BG_DOCKING_FIXED64_SINGLE_ANCHOR_TYPED_FAILURE;
    generated.result.failure_code = failure;
    return generated;
}

[[nodiscard]] Generated generate_reference(
    const bg_native_fixed64_single_anchor_kernel_input_v1 &input) {
    Generated generated{};
    generated.x.resize(static_cast<std::size_t>(input.ligand_atom_count));
    generated.y.resize(static_cast<std::size_t>(input.ligand_atom_count));
    generated.z.resize(static_cast<std::size_t>(input.ligand_atom_count));
    const std::size_t ligand_feature_count =
        static_cast<std::size_t>(input.ligand_feature_atom_count);
    const std::size_t receptor_feature_count =
        static_cast<std::size_t>(input.receptor_feature_atom_count);
    const Vec3 ligand_center = centroid(
        input.source_x_angstrom,
        input.source_y_angstrom,
        input.source_z_angstrom,
        static_cast<std::size_t>(input.ligand_atom_count));
    Vec3 ligand_anchor = centroid(
        input.ligand_feature_x_angstrom,
        input.ligand_feature_y_angstrom,
        input.ligand_feature_z_angstrom,
        ligand_feature_count);
    Vec3 receptor_anchor = centroid(
        input.receptor_feature_x_angstrom,
        input.receptor_feature_y_angstrom,
        input.receptor_feature_z_angstrom,
        receptor_feature_count);
    const Vec3 pocket_center{
        input.pocket_center_angstrom[0],
        input.pocket_center_angstrom[1],
        input.pocket_center_angstrom[2],
    };
    Vec3 ligand_direction{};
    Vec3 local_normal{};
    Vec3 alignment_target{};
    if (input.lane ==
        BG_DOCKING_FIXED64_LANE_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR) {
        ligand_anchor = {
            input.ligand_feature_x_angstrom[0],
            input.ligand_feature_y_angstrom[0],
            input.ligand_feature_z_angstrom[0],
        };
        const Vec3 hydrogen{
            input.ligand_feature_x_angstrom[1],
            input.ligand_feature_y_angstrom[1],
            input.ligand_feature_z_angstrom[1],
        };
        if (!normalize(minus(hydrogen, ligand_anchor), &ligand_direction)) {
            return typed_failure(
                BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_LIGAND_DIRECTION);
        }
        if (!normalize(minus(pocket_center, receptor_anchor), &local_normal)) {
            return typed_failure(
                BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_LOCAL_SURFACE_NORMAL);
        }
        alignment_target = scale(local_normal, -1.0);
    } else if (input.lane ==
               BG_DOCKING_FIXED64_LANE_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR) {
        if (!normalize(minus(ligand_anchor, ligand_center), &ligand_direction)) {
            return typed_failure(
                BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_LIGAND_DIRECTION);
        }
        receptor_anchor = {
            input.receptor_feature_x_angstrom[0],
            input.receptor_feature_y_angstrom[0],
            input.receptor_feature_z_angstrom[0],
        };
        const Vec3 hydrogen{
            input.receptor_feature_x_angstrom[1],
            input.receptor_feature_y_angstrom[1],
            input.receptor_feature_z_angstrom[1],
        };
        if (!normalize(minus(hydrogen, receptor_anchor), &local_normal)) {
            return typed_failure(
                BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_RECEPTOR_DIRECTION);
        }
        alignment_target = scale(local_normal, -1.0);
    } else if (input.lane == BG_DOCKING_FIXED64_LANE_COMPLEMENTARY_CHARGE) {
        if (!normalize(minus(ligand_anchor, ligand_center), &ligand_direction)) {
            return typed_failure(
                BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_LIGAND_DIRECTION);
        }
        if (!normalize(minus(pocket_center, receptor_anchor), &local_normal)) {
            return typed_failure(
                BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_LOCAL_SURFACE_NORMAL);
        }
        alignment_target = scale(local_normal, -1.0);
    } else if (input.lane == BG_DOCKING_FIXED64_LANE_AROMATIC_PLANE) {
        if (!aromatic_normal(
                input.ligand_feature_x_angstrom,
                input.ligand_feature_y_angstrom,
                input.ligand_feature_z_angstrom,
                ligand_feature_count,
                &ligand_direction)) {
            return typed_failure(
                BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_AROMATIC_PLANE);
        }
        Vec3 receptor_normal{};
        if (!aromatic_normal(
                input.receptor_feature_x_angstrom,
                input.receptor_feature_y_angstrom,
                input.receptor_feature_z_angstrom,
                receptor_feature_count,
                &receptor_normal)) {
            return typed_failure(
                BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_AROMATIC_PLANE);
        }
        Vec3 toward_pocket{};
        if (!normalize(minus(pocket_center, receptor_anchor), &toward_pocket)) {
            return typed_failure(
                BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_LOCAL_SURFACE_NORMAL);
        }
        const double facing = dot(receptor_normal, toward_pocket);
        if (std::abs(facing) <= kGeometryEpsilon) {
            return typed_failure(
                BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_LOCAL_SURFACE_NORMAL);
        }
        if (facing < 0.0) receptor_normal = scale(receptor_normal, -1.0);
        if (!normalize(receptor_normal, &local_normal)) {
            return typed_failure(
                BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_LOCAL_SURFACE_NORMAL);
        }
        alignment_target = local_normal;
    } else if (input.lane == BG_DOCKING_FIXED64_LANE_PRINCIPAL_AXIS_SHAPE) {
        if (!principal_axis(
                input.ligand_feature_x_angstrom,
                input.ligand_feature_y_angstrom,
                input.ligand_feature_z_angstrom,
                ligand_feature_count,
                &ligand_direction) ||
            !principal_axis(
                input.receptor_feature_x_angstrom,
                input.receptor_feature_y_angstrom,
                input.receptor_feature_z_angstrom,
                receptor_feature_count,
                &alignment_target)) {
            return typed_failure(
                BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_PRINCIPAL_AXIS);
        }
        if (!normalize(minus(pocket_center, receptor_anchor), &local_normal)) {
            return typed_failure(
                BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_LOCAL_SURFACE_NORMAL);
        }
    } else {
        return typed_failure(
            BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_NONFINITE_OUTPUT);
    }
    double target_distance = 3.0;
    std::size_t lane_width = 2;
    if (input.anchor_kind ==
            BG_DOCKING_FIXED64_ANCHOR_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR ||
        input.anchor_kind ==
            BG_DOCKING_FIXED64_ANCHOR_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR) {
        target_distance = 2.9;
        lane_width = 4;
    } else if (input.anchor_kind ==
               BG_DOCKING_FIXED64_ANCHOR_COMPLEMENTARY_CHARGE) {
        target_distance = 3.5;
        lane_width = 4;
    } else if (input.anchor_kind == BG_DOCKING_FIXED64_ANCHOR_AROMATIC_PLANE) {
        target_distance = 3.8;
    }
    if (input.lane_offset >= lane_width) {
        return typed_failure(
            BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_NONFINITE_OUTPUT);
    }
    const Vec3 target_anchor = plus(
        receptor_anchor, scale(local_normal, target_distance));
    bool quaternion_ok = false;
    const Quaternion base = between(
        ligand_direction, alignment_target, &quaternion_ok);
    if (!quaternion_ok) {
        return typed_failure(
            BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_DEGENERATE_LIGAND_DIRECTION);
    }
    const double twist_angle =
        2.0 * kPi * static_cast<double>(input.lane_offset) /
        static_cast<double>(lane_width);
    const Quaternion twist = rotation_about(
        alignment_target, twist_angle, &quaternion_ok);
    if (!quaternion_ok) {
        return typed_failure(
            BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_NONFINITE_OUTPUT);
    }
    const Quaternion quaternion = multiply(twist, base, &quaternion_ok);
    if (!quaternion_ok) {
        return typed_failure(
            BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_NONFINITE_OUTPUT);
    }
    const Vec3 translation = minus(
        target_anchor, rotate(quaternion, ligand_anchor));
    for (std::size_t atom = 0;
         atom < static_cast<std::size_t>(input.ligand_atom_count);
         ++atom) {
        const Vec3 placed = plus(
            rotate(
                quaternion,
                {input.source_x_angstrom[atom],
                 input.source_y_angstrom[atom],
                 input.source_z_angstrom[atom]}),
            translation);
        if (!finite_coordinate(placed.x) || !finite_coordinate(placed.y) ||
            !finite_coordinate(placed.z)) {
            return typed_failure(
                BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_NONFINITE_OUTPUT);
        }
        generated.x[atom] = placed.x;
        generated.y[atom] = placed.y;
        generated.z[atom] = placed.z;
    }
    auto &result = generated.result;
    result.status = BG_DOCKING_FIXED64_SINGLE_ANCHOR_PLACED;
    result.failure_code = BG_DOCKING_FIXED64_SINGLE_ANCHOR_FAILURE_NONE;
    write_vec3(result.ligand_anchor_point_angstrom, ligand_anchor);
    write_vec3(result.receptor_anchor_point_angstrom, receptor_anchor);
    write_vec3(result.target_anchor_point_angstrom, target_anchor);
    write_vec3(result.local_surface_normal, local_normal);
    write_vec3(result.approach_vector, scale(local_normal, -1.0));
    write_vec3(result.ligand_direction, ligand_direction);
    write_vec3(result.alignment_target_direction, alignment_target);
    result.target_distance_angstrom = target_distance;
    result.twist_angle_radians = twist_angle;
    result.quaternion_x = quaternion.x;
    result.quaternion_y = quaternion.y;
    result.quaternion_z = quaternion.z;
    result.quaternion_w = quaternion.w;
    write_vec3(result.translation_angstrom, translation);
    result.coordinates_written = UINT8_C(1);
    return generated;
}

[[nodiscard]] bg_status provider_failure(
    int32_t raw_status,
    const char *message,
    const char *fallback) noexcept {
    return fail(
        static_cast<bg_status>(raw_status),
        message != nullptr && message[0] != '\0' ? message : fallback);
}

[[nodiscard]] bg_status generate_backend(
    const bg_context &context,
    const bg_native_fixed64_single_anchor_kernel_input_v1 &kernel,
    Generated *generated) {
    if (context.backend == BG_BACKEND_CPP_CPU_REFERENCE) {
        *generated = generate_reference(kernel);
        return BG_STATUS_OK;
    }
    const auto ligand_count = static_cast<std::size_t>(kernel.ligand_atom_count);
    generated->x.assign(ligand_count, 0.0);
    generated->y.assign(ligand_count, 0.0);
    generated->z.assign(ligand_count, 0.0);
    int32_t raw_status = BG_STATUS_BACKEND_UNAVAILABLE;
    if (context.backend == BG_BACKEND_RUST_CPU) {
        bg_rust_cpu_error_v1 error{};
        error.struct_size = sizeof(error);
        error.abi_version = BG_RUST_CPU_PROVIDER_ABI_VERSION;
        raw_status = bg_rust_cpu_docking_fixed64_single_anchor_v1_place(
            &kernel,
            generated->x.data(),
            generated->y.data(),
            generated->z.data(),
            &generated->result,
            &error);
        return raw_status == BG_STATUS_OK
            ? BG_STATUS_OK
            : provider_failure(
                  raw_status,
                  error.message,
                  "rust_cpu single-anchor placement failed");
    }
#if BG_HAS_HIP_SAFE_PROVIDER
    if (context.backend == BG_BACKEND_HIP_SAFE) {
        char error[BG_HIP_SAFE_ERROR_CAPACITY]{};
        raw_status = bg_hip_safe_docking_fixed64_single_anchor_v1_place(
            context.device_ordinal,
            &kernel,
            generated->x.data(),
            generated->y.data(),
            generated->z.data(),
            &generated->result,
            error,
            sizeof(error));
        return raw_status == BG_STATUS_OK
            ? BG_STATUS_OK
            : provider_failure(
                  raw_status,
                  error,
                  "hip_safe single-anchor placement failed");
    }
#endif
#if BG_ENABLE_HIP
    if (context.backend == BG_BACKEND_HIP_FAST) {
        char error[BG_HIP_SAFE_ERROR_CAPACITY]{};
        raw_status = bg_hip_fast_docking_fixed64_single_anchor_v1_place(
            context.device_ordinal,
            &kernel,
            generated->x.data(),
            generated->y.data(),
            generated->z.data(),
            &generated->result,
            error,
            sizeof(error));
        return raw_status == BG_STATUS_OK
            ? BG_STATUS_OK
            : provider_failure(
                  raw_status,
                  error,
                  "hip_fast single-anchor placement failed");
    }
#endif
    return fail(
        BG_STATUS_BACKEND_UNAVAILABLE,
        "selected backend has no single-anchor kernel; fallback is forbidden");
}

[[nodiscard]] bg_status validate_generated(
    const bg_native_fixed64_single_anchor_kernel_input_v1 &kernel,
    Generated &generated,
    bg_backend backend) noexcept {
    const Generated expected = generate_reference(kernel);
    auto &observed = generated.result;
    const auto &reference = expected.result;
    if (!std::all_of(
            std::begin(observed.reserved0), std::end(observed.reserved0),
            [](uint8_t value) { return value == UINT8_C(0); }) ||
        !reserved_is_zero(observed.reserved) ||
        observed.status != reference.status ||
        observed.failure_code != reference.failure_code ||
        observed.coordinates_written != reference.coordinates_written) {
        return fail(
            BG_STATUS_BACKEND_ERROR,
            "single-anchor backend status violates its private ABI");
    }
    const double tolerance = backend == BG_BACKEND_HIP_FAST
        ? 2.0e-9
        : (backend == BG_BACKEND_HIP_SAFE ? 2.0e-10 : 2.0e-12);
    const auto close = [tolerance](double left, double right) noexcept {
        const double magnitude =
            std::max({1.0, std::abs(left), std::abs(right)});
        return std::isfinite(left) && std::isfinite(right) &&
               std::abs(left - right) <= tolerance * magnitude;
    };
    const std::array<const double *, 8> observed_vectors = {
        observed.ligand_anchor_point_angstrom,
        observed.receptor_anchor_point_angstrom,
        observed.target_anchor_point_angstrom,
        observed.local_surface_normal,
        observed.approach_vector,
        observed.ligand_direction,
        observed.alignment_target_direction,
        observed.translation_angstrom,
    };
    const std::array<const double *, 8> reference_vectors = {
        reference.ligand_anchor_point_angstrom,
        reference.receptor_anchor_point_angstrom,
        reference.target_anchor_point_angstrom,
        reference.local_surface_normal,
        reference.approach_vector,
        reference.ligand_direction,
        reference.alignment_target_direction,
        reference.translation_angstrom,
    };
    for (std::size_t vector = 0; vector < observed_vectors.size(); ++vector) {
        for (std::size_t axis = 0; axis < 3; ++axis) {
            if (!close(
                    observed_vectors[vector][axis],
                    reference_vectors[vector][axis])) {
                return fail(
                    BG_STATUS_BACKEND_ERROR,
                    "single-anchor backend mutated derived geometry");
            }
        }
    }
    const bool opposite_quaternion =
        close(observed.quaternion_x, -reference.quaternion_x) &&
        close(observed.quaternion_y, -reference.quaternion_y) &&
        close(observed.quaternion_z, -reference.quaternion_z) &&
        close(observed.quaternion_w, -reference.quaternion_w);
    if (opposite_quaternion) {
        observed.quaternion_x = -observed.quaternion_x;
        observed.quaternion_y = -observed.quaternion_y;
        observed.quaternion_z = -observed.quaternion_z;
        observed.quaternion_w = -observed.quaternion_w;
    }
    if (observed.quaternion_x == 0.0) observed.quaternion_x = 0.0;
    if (observed.quaternion_y == 0.0) observed.quaternion_y = 0.0;
    if (observed.quaternion_z == 0.0) observed.quaternion_z = 0.0;
    if (observed.quaternion_w == 0.0) observed.quaternion_w = 0.0;
    const std::array<double, 6> observed_scalars = {
        observed.target_distance_angstrom,
        observed.twist_angle_radians,
        observed.quaternion_x,
        observed.quaternion_y,
        observed.quaternion_z,
        observed.quaternion_w,
    };
    const std::array<double, 6> reference_scalars = {
        reference.target_distance_angstrom,
        reference.twist_angle_radians,
        reference.quaternion_x,
        reference.quaternion_y,
        reference.quaternion_z,
        reference.quaternion_w,
    };
    for (std::size_t index = 0; index < observed_scalars.size(); ++index) {
        if (!close(observed_scalars[index], reference_scalars[index])) {
            return fail(
                BG_STATUS_BACKEND_ERROR,
                "single-anchor backend scalar parity failed");
        }
        if (observed_scalars[index] == 0.0 &&
            std::signbit(observed_scalars[index])) {
            return fail(
                BG_STATUS_BACKEND_ERROR,
                "single-anchor backend emitted negative-zero scalar evidence");
        }
    }
    if (reference.coordinates_written != UINT8_C(0)) {
        const auto ligand_count =
            static_cast<std::size_t>(kernel.ligand_atom_count);
        if (generated.x.size() != ligand_count ||
            generated.y.size() != ligand_count ||
            generated.z.size() != ligand_count) {
            return fail(
                BG_STATUS_BACKEND_ERROR,
                "single-anchor backend omitted coordinate channels");
        }
        for (std::size_t atom = 0; atom < ligand_count; ++atom) {
            if (!close(generated.x[atom], expected.x[atom]) ||
                !close(generated.y[atom], expected.y[atom]) ||
                !close(generated.z[atom], expected.z[atom]) ||
                !finite_coordinate(generated.x[atom]) ||
                !finite_coordinate(generated.y[atom]) ||
                !finite_coordinate(generated.z[atom])) {
                return fail(
                    BG_STATUS_BACKEND_ERROR,
                    "single-anchor backend coordinate parity failed");
            }
        }
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status geometric_precheck(
    const bg_context &context,
    const bg_docking_geometric_admission_v1 &admission,
    uint32_t slot_index,
    const Generated &generated,
    bg_docking_geometric_admission_row_v1 *selected_row,
    std::array<uint8_t, 32> *batch_receipt) {
    const auto ligand_count = static_cast<std::size_t>(admission.ligand_atom_count);
    std::array<bg_docking_geometric_admission_candidate_state, kCandidateCount>
        states{};
    states.fill(BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_UPSTREAM_FAILURE);
    std::vector<double> x(kCandidateCount * ligand_count, 0.0);
    std::vector<double> y(kCandidateCount * ligand_count, 0.0);
    std::vector<double> z(kCandidateCount * ligand_count, 0.0);
    if (generated.result.coordinates_written != UINT8_C(0)) {
        states[slot_index] = BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_EVALUATE;
        const std::size_t offset = static_cast<std::size_t>(slot_index) * ligand_count;
        std::copy_n(generated.x.data(), ligand_count, x.data() + offset);
        std::copy_n(generated.y.data(), ligand_count, y.data() + offset);
        std::copy_n(generated.z.data(), ligand_count, z.data() + offset);
    }
    bg_docking_geometric_admission_candidate_batch_soa_v1 batch{};
    batch.struct_size = sizeof(batch);
    batch.abi_version = BG_ABI_VERSION;
    batch.candidate_count = kCandidateCount;
    batch.ligand_atom_count = ligand_count;
    batch.unit_system = admission.unit_system;
    batch.candidate_state = states.data();
    batch.x_angstrom = x.data();
    batch.y_angstrom = y.data();
    batch.z_angstrom = z.data();
    std::array<bg_docking_geometric_admission_row_v1, kCandidateCount> rows{};
    bg_docking_geometric_admission_output_v1 output{};
    output.struct_size = sizeof(output);
    output.abi_version = BG_ABI_VERSION;
    output.row_capacity = rows.size();
    output.unit_system = admission.unit_system;
    output.rows = rows.data();
    const bg_status status = bg_docking_geometric_admission_v1_evaluate_fixed64(
        &context, &admission, &batch, &output);
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
            "single-anchor geometric precheck violated its authority boundary");
    }
    *selected_row = rows[slot_index];
    std::copy_n(output.batch_receipt_sha256, 32, batch_receipt->begin());
    return BG_STATUS_OK;
}

[[nodiscard]] std::array<uint8_t, 32> placement_receipt(
    const bg_docking_fixed64_single_anchor_input_v1 &input,
    const bg_docking_fixed64_allocation_row_v1 &slot,
    const SelectedFeatures &selected,
    const Generated &generated,
    bg_backend backend,
    const std::array<uint8_t, 32> &allocation_inventory,
    const std::array<uint8_t, 32> &allocation_receipt,
    const std::array<uint8_t, 32> &coordinate,
    const bg_docking_geometric_admission_row_v1 &geometric,
    const std::array<uint8_t, 32> &geometric_batch) noexcept {
    const auto &result = generated.result;
    CanonicalHash hash("betelgeuze.fixed64_single_anchor_abi/native-v1");
    hash.string(kPlacementSchema);
    hash.string(kProfileId);
    hash.digest(allocation_inventory);
    hash.digest(allocation_receipt);
    hash.digest(slot.slot_receipt_sha256);
    hash.u32(input.slot_index);
    hash.u32(static_cast<uint32_t>(slot.lane));
    hash.u32(slot.lane_offset);
    hash.u32(static_cast<uint32_t>(slot.declared_anchor_kind));
    hash.u32(static_cast<uint32_t>(backend));
    hash.digest(input.source.receipt_sha256);
    hash.digest(input.source.proposal_sha256);
    hash.digest(input.source.coordinate_sha256);
    hash.digest(input.feature_geometry_inventory_sha256);
    hash.digest(selected.ligand->feature_geometry_receipt_sha256);
    hash.digest(selected.receptor->feature_geometry_receipt_sha256);
    hash.u32(static_cast<uint32_t>(result.status));
    hash.u32(static_cast<uint32_t>(result.failure_code));
    hash.vec3({result.ligand_anchor_point_angstrom[0],
               result.ligand_anchor_point_angstrom[1],
               result.ligand_anchor_point_angstrom[2]});
    hash.vec3({result.receptor_anchor_point_angstrom[0],
               result.receptor_anchor_point_angstrom[1],
               result.receptor_anchor_point_angstrom[2]});
    hash.vec3({result.target_anchor_point_angstrom[0],
               result.target_anchor_point_angstrom[1],
               result.target_anchor_point_angstrom[2]});
    hash.vec3({result.local_surface_normal[0],
               result.local_surface_normal[1],
               result.local_surface_normal[2]});
    hash.vec3({result.approach_vector[0],
               result.approach_vector[1],
               result.approach_vector[2]});
    hash.vec3({result.ligand_direction[0],
               result.ligand_direction[1],
               result.ligand_direction[2]});
    hash.vec3({result.alignment_target_direction[0],
               result.alignment_target_direction[1],
               result.alignment_target_direction[2]});
    hash.f64(result.target_distance_angstrom);
    hash.f64(result.twist_angle_radians);
    hash.f64(result.quaternion_x);
    hash.f64(result.quaternion_y);
    hash.f64(result.quaternion_z);
    hash.f64(result.quaternion_w);
    hash.vec3({result.translation_angstrom[0],
               result.translation_angstrom[1],
               result.translation_angstrom[2]});
    hash.digest(coordinate);
    hash.digest(geometric.row_receipt_sha256);
    hash.digest(geometric_batch);
    hash.byte(result.coordinates_written);
    hash.byte(geometric.rank_eligible);
    hash.byte(UINT8_C(1));
    hash.byte(UINT8_C(1));
    hash.byte(UINT8_C(1));
    hash.byte(UINT8_C(1));
    hash.byte(UINT8_C(0));
    hash.byte(UINT8_C(0));
    hash.byte(UINT8_C(0));
    hash.byte(UINT8_C(1));
    for (std::size_t index = 0; index < 7; ++index) hash.byte(UINT8_C(0));
    return hash.finish();
}

}  // namespace
}  // namespace betelgeuze::native::docking::fixed64_single_anchor

using namespace betelgeuze::native;

extern "C" BG_API bg_status BG_CALL
bg_docking_fixed64_single_anchor_input_v1_init(
    bg_docking_fixed64_single_anchor_input_v1 *input,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            input, caller_struct_size, sizeof(*input), caller_abi_version,
            "single-anchor input initializer pointer is null",
            "single-anchor input initializer size does not match",
            "single-anchor input initializer ABI version does not match");
        if (status != BG_STATUS_OK) return status;
        *input = bg_docking_fixed64_single_anchor_input_v1{};
        input->struct_size = static_cast<uint32_t>(sizeof(*input));
        input->abi_version = BG_ABI_VERSION;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL
bg_docking_fixed64_single_anchor_output_v1_init(
    bg_docking_fixed64_single_anchor_output_v1 *output,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            output, caller_struct_size, sizeof(*output), caller_abi_version,
            "single-anchor output initializer pointer is null",
            "single-anchor output initializer size does not match",
            "single-anchor output initializer ABI version does not match");
        if (status != BG_STATUS_OK) return status;
        *output = bg_docking_fixed64_single_anchor_output_v1{};
        output->struct_size = static_cast<uint32_t>(sizeof(*output));
        output->abi_version = BG_ABI_VERSION;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL
bg_docking_fixed64_single_anchor_v1_place(
    const bg_context *context,
    const bg_docking_geometric_admission_v1 *admission,
    const bg_docking_fixed64_single_anchor_input_v1 *input,
    bg_docking_fixed64_single_anchor_output_v1 *output) BG_NOEXCEPT {
    using namespace betelgeuze::native::docking::fixed64_single_anchor;
    return guarded_status([&]() -> bg_status {
        if (context == nullptr || admission == nullptr || input == nullptr ||
            output == nullptr || !pointer_is_aligned(context) ||
            !pointer_is_aligned(admission) || !pointer_is_aligned(input) ||
            !pointer_is_aligned(output)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "single-anchor context, admission, input, and output must be aligned");
        }
        std::array<bg_docking_fixed64_allocation_row_v1, kCandidateCount>
            allocation_rows{};
        std::array<uint8_t, 32> allocation_inventory{};
        std::array<uint8_t, 32> allocation_receipt{};
        SelectedFeatures selected{};
        bg_status status = validate_input(
            *context,
            *admission,
            *input,
            *output,
            &allocation_rows,
            &allocation_inventory,
            &allocation_receipt,
            &selected);
        if (status != BG_STATUS_OK) return status;
        const auto &slot = allocation_rows[input->slot_index];
        std::vector<double> ligand_feature_x;
        std::vector<double> ligand_feature_y;
        std::vector<double> ligand_feature_z;
        std::vector<double> receptor_feature_x;
        std::vector<double> receptor_feature_y;
        std::vector<double> receptor_feature_z;
        const auto kernel = make_kernel_input(
            *input,
            slot,
            *admission,
            selected,
            &ligand_feature_x,
            &ligand_feature_y,
            &ligand_feature_z,
            &receptor_feature_x,
            &receptor_feature_y,
            &receptor_feature_z);
        Generated generated{};
        status = generate_backend(*context, kernel, &generated);
        if (status != BG_STATUS_OK) return status;
        status = validate_generated(kernel, generated, context->backend);
        if (status != BG_STATUS_OK) return status;
        bg_docking_geometric_admission_row_v1 geometric{};
        std::array<uint8_t, 32> geometric_batch{};
        status = geometric_precheck(
            *context,
            *admission,
            input->slot_index,
            generated,
            &geometric,
            &geometric_batch);
        if (status != BG_STATUS_OK) return status;
        const bool placed =
            generated.result.coordinates_written != UINT8_C(0);
        if ((placed &&
             geometric.status != BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED) ||
            (!placed &&
             geometric.status !=
                 BG_DOCKING_GEOMETRIC_ADMISSION_ROW_UPSTREAM_FAILURE)) {
            return fail(
                BG_STATUS_INTERNAL_ERROR,
                "single-anchor geometric precheck did not preserve slot state");
        }
        std::array<uint8_t, 32> coordinate{};
        if (placed) {
            coordinate = coordinate_sha256(
                generated.x.data(),
                generated.y.data(),
                generated.z.data(),
                generated.x.size());
        }
        const auto receipt = placement_receipt(
            *input,
            slot,
            selected,
            generated,
            context->backend,
            allocation_inventory,
            allocation_receipt,
            coordinate,
            geometric,
            geometric_batch);

        bg_docking_fixed64_single_anchor_output_v1 committed{};
        committed.struct_size = output->struct_size;
        committed.abi_version = output->abi_version;
        committed.coordinate_capacity = output->coordinate_capacity;
        committed.x_angstrom = output->x_angstrom;
        committed.y_angstrom = output->y_angstrom;
        committed.z_angstrom = output->z_angstrom;
        committed.slot_index = input->slot_index;
        committed.lane = slot.lane;
        committed.lane_offset = slot.lane_offset;
        committed.anchor_kind = slot.declared_anchor_kind;
        committed.status = generated.result.status;
        committed.failure_code = generated.result.failure_code;
        committed.backend = context->backend;
        committed.ligand_atom_count = input->ligand_atom_count;
        std::copy_n(
            generated.result.ligand_anchor_point_angstrom,
            3,
            committed.ligand_anchor_point_angstrom);
        std::copy_n(
            generated.result.receptor_anchor_point_angstrom,
            3,
            committed.receptor_anchor_point_angstrom);
        std::copy_n(
            generated.result.target_anchor_point_angstrom,
            3,
            committed.target_anchor_point_angstrom);
        std::copy_n(
            generated.result.local_surface_normal,
            3,
            committed.local_surface_normal);
        std::copy_n(
            generated.result.approach_vector,
            3,
            committed.approach_vector);
        std::copy_n(
            generated.result.ligand_direction,
            3,
            committed.ligand_direction);
        std::copy_n(
            generated.result.alignment_target_direction,
            3,
            committed.alignment_target_direction);
        committed.target_distance_angstrom =
            generated.result.target_distance_angstrom;
        committed.twist_angle_radians = generated.result.twist_angle_radians;
        committed.quaternion_x = generated.result.quaternion_x;
        committed.quaternion_y = generated.result.quaternion_y;
        committed.quaternion_z = generated.result.quaternion_z;
        committed.quaternion_w = generated.result.quaternion_w;
        std::copy_n(
            generated.result.translation_angstrom,
            3,
            committed.translation_angstrom);
        std::copy(allocation_inventory.begin(), allocation_inventory.end(),
                  committed.allocation_inventory_sha256);
        std::copy(allocation_receipt.begin(), allocation_receipt.end(),
                  committed.allocation_receipt_sha256);
        std::copy_n(slot.slot_receipt_sha256, 32,
                    committed.allocation_slot_receipt_sha256);
        std::copy_n(input->source.receipt_sha256, 32,
                    committed.source_receipt_sha256);
        std::copy_n(input->feature_geometry_inventory_sha256, 32,
                    committed.feature_geometry_inventory_sha256);
        std::copy_n(selected.ligand->feature_geometry_receipt_sha256, 32,
                    committed.selected_ligand_feature_geometry_sha256);
        std::copy_n(selected.receptor->feature_geometry_receipt_sha256, 32,
                    committed.selected_receptor_feature_geometry_sha256);
        std::copy(coordinate.begin(), coordinate.end(),
                  committed.output_coordinate_sha256);
        committed.geometric_admission = geometric;
        std::copy(geometric_batch.begin(), geometric_batch.end(),
                  committed.geometric_admission_batch_receipt_sha256);
        std::copy(receipt.begin(), receipt.end(),
                  committed.placement_receipt_sha256);
        committed.coordinates_written = generated.result.coordinates_written;
        committed.steric_precheck_passed = geometric.rank_eligible;
        committed.source_identity_verified = UINT8_C(1);
        committed.allocation_identity_verified = UINT8_C(1);
        committed.feature_identity_verified = UINT8_C(1);
        committed.geometric_identity_verified = UINT8_C(1);
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
        if (placed) {
            const std::size_t bytes = generated.x.size() * sizeof(double);
            std::memcpy(output->x_angstrom, generated.x.data(), bytes);
            std::memcpy(output->y_angstrom, generated.y.data(), bytes);
            std::memcpy(output->z_angstrom, generated.z.data(), bytes);
        }
        *output = committed;
        return BG_STATUS_OK;
    });
}
