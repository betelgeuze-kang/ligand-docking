#include "../dynamics/sha256.hpp"
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
#include <vector>

#ifndef BG_HAS_HIP_SAFE_PROVIDER
#  define BG_HAS_HIP_SAFE_PROVIDER 0
#endif
#ifndef BG_ENABLE_HIP
#  define BG_ENABLE_HIP 0
#endif

namespace betelgeuze::native::docking::geometric_admission {
namespace {

constexpr std::size_t kCandidateCount = BG_DOCKING_FIXED64_CANDIDATE_COUNT;
constexpr std::size_t kMaxLigandAtoms = 512;
constexpr std::size_t kMaxReceptorAtoms = 4'096;
constexpr std::size_t kMaxBatchPairEvaluations = 16'777'216;
constexpr double kMaximumCoordinateAngstrom = 100'000.0;
constexpr double kMinimumVdwRadiusAngstrom = 0.1;
constexpr double kMaximumVdwRadiusAngstrom = 10.0;
constexpr double kMaximumPocketRadiusAngstrom = 1'000.0;
constexpr double kHardRejectionMinimumVdwRatio = 0.55;
constexpr double kPi = 3.141592653589793238462643383279502884;
constexpr char kRowSchema[] =
    "betelgeuze.engine_v2_native_geometric_admission_row/1.0.0";
constexpr char kBatchSchema[] =
    "betelgeuze.engine_v2_native_geometric_admission_batch/1.0.0";

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

    void f64(double value) noexcept {
        uint64_t bits = UINT64_C(0);
        if (std::isnan(value)) {
            bits = UINT64_C(0x7ff8000000000000);
        } else if (value != 0.0) {
            static_assert(sizeof(bits) == sizeof(value));
            std::memcpy(&bits, &value, sizeof(bits));
        }
        u64(bits);
    }

    void bytes(const uint8_t *values, std::size_t count) noexcept {
        u64(static_cast<uint64_t>(count));
        hash_.update(values, count);
    }

    void string(const char *value) noexcept {
        bytes(
            reinterpret_cast<const uint8_t *>(value),
            std::strlen(value));
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
    dynamics::Sha256 hash_;
};

struct Vec3 final {
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
};

struct CppGeometricContext final {
    std::vector<Vec3> receptor_coordinates;
    std::vector<double> receptor_radii;
    std::vector<double> ligand_radii;
    std::vector<uint8_t> ligand_heavy_atom_mask;
    Vec3 pocket_center;
    double pocket_radius = 0.0;
    double hard_rejection_minimum_vdw_ratio = 0.0;
    std::size_t max_batch_exact_pair_evaluations = 0;
};

struct MemoryRange final {
    uintptr_t begin = 0;
    uintptr_t end = 0;
};

template <typename Type>
[[nodiscard]] bg_status require_channel(
    const Type *pointer,
    std::size_t count,
    const char *message) noexcept {
    if (count > 0 && (pointer == nullptr || !pointer_is_aligned(pointer))) {
        return fail(BG_STATUS_INVALID_ARGUMENT, message);
    }
    return BG_STATUS_OK;
}

template <typename Type>
[[nodiscard]] bool memory_range(
    const Type *pointer,
    std::size_t count,
    MemoryRange *out) noexcept {
    if (pointer == nullptr || out == nullptr || count == 0 ||
        count > std::numeric_limits<std::size_t>::max() / sizeof(Type)) {
        return false;
    }
    const std::size_t bytes = count * sizeof(Type);
    const uintptr_t begin = reinterpret_cast<uintptr_t>(pointer);
    if (begin > std::numeric_limits<uintptr_t>::max() - bytes) {
        return false;
    }
    *out = {begin, begin + bytes};
    return true;
}

[[nodiscard]] bool overlaps(MemoryRange left, MemoryRange right) noexcept {
    return left.begin < right.end && right.begin < left.end;
}

template <typename Type>
[[nodiscard]] bg_status add_range(
    std::vector<MemoryRange> *ranges,
    const Type *pointer,
    std::size_t count,
    const char *message) {
    MemoryRange range{};
    if (!memory_range(pointer, count, &range)) {
        return fail(BG_STATUS_CAPACITY_OVERFLOW, message);
    }
    ranges->push_back(range);
    return BG_STATUS_OK;
}

[[nodiscard]] bool finite_coordinate(Vec3 value) noexcept {
    return std::isfinite(value.x) && std::isfinite(value.y) &&
           std::isfinite(value.z) &&
           std::abs(value.x) <= kMaximumCoordinateAngstrom &&
           std::abs(value.y) <= kMaximumCoordinateAngstrom &&
           std::abs(value.z) <= kMaximumCoordinateAngstrom;
}

[[nodiscard]] double distance(Vec3 left, Vec3 right) noexcept {
    const double x = left.x - right.x;
    const double y = left.y - right.y;
    const double z = left.z - right.z;
    // The 100,000 A coordinate envelope makes the frozen direct sum safe.
    // Keep this exact left-associated primitive in C++, Rust, and HIP so a
    // backend switch cannot move a row across the 0.55 rejection boundary.
    return std::sqrt((x * x + y * y) + z * z);
}

[[nodiscard]] bool digest_present(const uint8_t (&digest)[32]) noexcept {
    return std::any_of(
        std::begin(digest), std::end(digest), [](uint8_t value) {
            return value != UINT8_C(0);
        });
}

[[nodiscard]] double sphere_intersection_volume(
    double left_radius,
    double right_radius,
    double center_distance) noexcept {
    const double radius_sum = left_radius + right_radius;
    if (center_distance >= radius_sum) {
        return 0.0;
    }
    const double radius_difference = std::abs(left_radius - right_radius);
    if (center_distance <= radius_difference) {
        const double radius = std::min(left_radius, right_radius);
        return (4.0 / 3.0) * kPi * radius * radius * radius;
    }
    const double difference = radius_sum - center_distance;
    const double distance_squared = center_distance * center_distance;
    const double radius_difference_squared =
        radius_difference * radius_difference;
    const double numerator =
        kPi * difference * difference *
        (distance_squared + 2.0 * center_distance * radius_sum -
         3.0 * radius_difference_squared);
    return std::max(numerator / (12.0 * center_distance), 0.0);
}

[[nodiscard]] bg_status checked_counts(
    const bg_docking_geometric_admission_context_soa_v1 &descriptor,
    std::size_t *receptor_count,
    std::size_t *ligand_count) noexcept {
    if (descriptor.receptor_atom_count == 0 ||
        descriptor.receptor_atom_count > kMaxReceptorAtoms ||
        descriptor.ligand_atom_count == 0 ||
        descriptor.ligand_atom_count > kMaxLigandAtoms) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "geometric-admission atom denominator is outside fixed bounds");
    }
    *receptor_count =
        static_cast<std::size_t>(descriptor.receptor_atom_count);
    *ligand_count = static_cast<std::size_t>(descriptor.ligand_atom_count);
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status validate_context_descriptor(
    const bg_docking_geometric_admission_context_soa_v1 &descriptor) noexcept {
    bg_status status = validate_descriptor_header(
        descriptor.struct_size,
        sizeof(descriptor),
        descriptor.abi_version,
        "geometric-admission context size does not match ABI v1",
        "geometric-admission context ABI version does not match");
    if (status != BG_STATUS_OK) return status;
    status = validate_unit_system(descriptor.unit_system);
    if (status != BG_STATUS_OK) return status;
    if (descriptor.reserved0 != 0 ||
        !reserved_is_zero(descriptor.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "geometric-admission context reserved fields must be zero");
    }
    std::size_t receptor_count = 0;
    std::size_t ligand_count = 0;
    status = checked_counts(descriptor, &receptor_count, &ligand_count);
    if (status != BG_STATUS_OK) return status;
    const std::array<const double *, 4> receptor_channels = {
        descriptor.receptor_x_angstrom,
        descriptor.receptor_y_angstrom,
        descriptor.receptor_z_angstrom,
        descriptor.receptor_vdw_radius_angstrom,
    };
    for (const double *channel : receptor_channels) {
        status = require_channel(
            channel,
            receptor_count,
            "geometric-admission receptor channel is null or misaligned");
        if (status != BG_STATUS_OK) return status;
    }
    status = require_channel(
        descriptor.ligand_vdw_radius_angstrom,
        ligand_count,
        "geometric-admission ligand radii are null or misaligned");
    if (status != BG_STATUS_OK) return status;
    status = require_channel(
        descriptor.ligand_heavy_atom_mask,
        ligand_count,
        "geometric-admission heavy-atom mask is null or misaligned");
    if (status != BG_STATUS_OK) return status;
    const Vec3 pocket_center{
        descriptor.pocket_center_angstrom[0],
        descriptor.pocket_center_angstrom[1],
        descriptor.pocket_center_angstrom[2],
    };
    if (!finite_coordinate(pocket_center) ||
        !std::isfinite(descriptor.pocket_radius_angstrom) ||
        descriptor.pocket_radius_angstrom <= 0.0 ||
        descriptor.pocket_radius_angstrom > kMaximumPocketRadiusAngstrom ||
        descriptor.hard_rejection_minimum_vdw_ratio !=
            kHardRejectionMinimumVdwRatio ||
        descriptor.max_batch_exact_pair_evaluations !=
            kMaxBatchPairEvaluations ||
        !digest_present(descriptor.authority_input_receipt_sha256) ||
        !digest_present(descriptor.receptor_system_sha256) ||
        !digest_present(descriptor.ligand_system_sha256) ||
        !digest_present(descriptor.backend_receipt_sha256)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "geometric-admission policy, pocket, or identity binding is invalid");
    }
    for (std::size_t index = 0; index < receptor_count; ++index) {
        const Vec3 coordinate{
            descriptor.receptor_x_angstrom[index],
            descriptor.receptor_y_angstrom[index],
            descriptor.receptor_z_angstrom[index],
        };
        const double radius =
            descriptor.receptor_vdw_radius_angstrom[index];
        if (!finite_coordinate(coordinate) || !std::isfinite(radius) ||
            radius < kMinimumVdwRadiusAngstrom ||
            radius > kMaximumVdwRadiusAngstrom) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "geometric-admission receptor coordinate or radius is invalid");
        }
    }
    for (std::size_t index = 0; index < ligand_count; ++index) {
        const double radius = descriptor.ligand_vdw_radius_angstrom[index];
        if (!std::isfinite(radius) ||
            radius < kMinimumVdwRadiusAngstrom ||
            radius > kMaximumVdwRadiusAngstrom ||
            descriptor.ligand_heavy_atom_mask[index] > UINT8_C(1)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "geometric-admission ligand radius or heavy-atom flag is invalid");
        }
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status validate_create_output_range(
    const bg_context &context,
    const bg_docking_geometric_admission_context_soa_v1 &descriptor,
    bg_docking_geometric_admission_v1 **out_admission) {
    const std::size_t receptor_count =
        static_cast<std::size_t>(descriptor.receptor_atom_count);
    const std::size_t ligand_count =
        static_cast<std::size_t>(descriptor.ligand_atom_count);
    std::vector<MemoryRange> inputs;
    inputs.reserve(9);
    bg_status status = add_range(
        &inputs,
        &context,
        1,
        "geometric-admission context range overflowed");
    if (status != BG_STATUS_OK) return status;
    status = add_range(
        &inputs,
        &descriptor,
        1,
        "geometric-admission descriptor range overflowed");
    if (status != BG_STATUS_OK) return status;
    const std::array<const double *, 4> receptor_channels = {
        descriptor.receptor_x_angstrom,
        descriptor.receptor_y_angstrom,
        descriptor.receptor_z_angstrom,
        descriptor.receptor_vdw_radius_angstrom,
    };
    for (const double *channel : receptor_channels) {
        status = add_range(
            &inputs,
            channel,
            receptor_count,
            "geometric-admission receptor input range overflowed");
        if (status != BG_STATUS_OK) return status;
    }
    status = add_range(
        &inputs,
        descriptor.ligand_vdw_radius_angstrom,
        ligand_count,
        "geometric-admission ligand-radius range overflowed");
    if (status != BG_STATUS_OK) return status;
    status = add_range(
        &inputs,
        descriptor.ligand_heavy_atom_mask,
        ligand_count,
        "geometric-admission heavy-atom range overflowed");
    if (status != BG_STATUS_OK) return status;
    MemoryRange output{};
    if (!memory_range(out_admission, 1, &output)) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "geometric-admission handle output range overflowed");
    }
    for (const MemoryRange input : inputs) {
        if (overlaps(output, input)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "geometric-admission handle output overlaps an input");
        }
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status validate_backend_output_range(
    const bg_docking_geometric_admission_v1 *admission,
    bg_backend *backend) noexcept {
    MemoryRange handle_range{};
    MemoryRange output_range{};
    if (!memory_range(admission, 1, &handle_range) ||
        !memory_range(backend, 1, &output_range)) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "geometric-admission backend output range overflowed");
    }
    if (overlaps(handle_range, output_range)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "geometric-admission backend output overlaps its handle");
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status create_cpp_context(
    const bg_docking_geometric_admission_context_soa_v1 &descriptor,
    void **out_state) {
    if (out_state == nullptr) {
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "geometric-admission C++ state output is null");
    }
    *out_state = nullptr;
    bg_status status = validate_context_descriptor(descriptor);
    if (status != BG_STATUS_OK) return status;
    const std::size_t receptor_count =
        static_cast<std::size_t>(descriptor.receptor_atom_count);
    const std::size_t ligand_count =
        static_cast<std::size_t>(descriptor.ligand_atom_count);
    auto context = std::make_unique<CppGeometricContext>();
    context->receptor_coordinates.reserve(receptor_count);
    context->receptor_radii.reserve(receptor_count);
    for (std::size_t index = 0; index < receptor_count; ++index) {
        context->receptor_coordinates.push_back({
            descriptor.receptor_x_angstrom[index],
            descriptor.receptor_y_angstrom[index],
            descriptor.receptor_z_angstrom[index],
        });
        context->receptor_radii.push_back(
            descriptor.receptor_vdw_radius_angstrom[index]);
    }
    context->ligand_radii.assign(
        descriptor.ligand_vdw_radius_angstrom,
        descriptor.ligand_vdw_radius_angstrom + ligand_count);
    context->ligand_heavy_atom_mask.assign(
        descriptor.ligand_heavy_atom_mask,
        descriptor.ligand_heavy_atom_mask + ligand_count);
    context->pocket_center = {
        descriptor.pocket_center_angstrom[0],
        descriptor.pocket_center_angstrom[1],
        descriptor.pocket_center_angstrom[2],
    };
    context->pocket_radius = descriptor.pocket_radius_angstrom;
    context->hard_rejection_minimum_vdw_ratio =
        descriptor.hard_rejection_minimum_vdw_ratio;
    context->max_batch_exact_pair_evaluations =
        static_cast<std::size_t>(
            descriptor.max_batch_exact_pair_evaluations);
    *out_state = context.release();
    return BG_STATUS_OK;
}

void failure_row(
    std::size_t slot,
    bg_docking_geometric_admission_row_status status,
    bg_docking_geometric_admission_failure failure,
    bg_docking_geometric_admission_row_v1 *row) noexcept {
    *row = bg_docking_geometric_admission_row_v1{};
    row->slot_index = static_cast<uint32_t>(slot);
    row->status = status;
    row->failure_code = failure;
    row->decision = BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_NOT_EVALUATED;
}

[[nodiscard]] bg_status evaluate_cpp_fixed64(
    const CppGeometricContext &context,
    const bg_docking_geometric_admission_candidate_batch_soa_v1 &candidates,
    std::array<bg_docking_geometric_admission_row_v1, kCandidateCount>
        *out_rows) noexcept {
    const std::size_t ligand_count = context.ligand_radii.size();
    const std::size_t receptor_count = context.receptor_radii.size();
    for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
        auto &row = (*out_rows)[slot];
        if (candidates.candidate_state[slot] ==
            BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_UPSTREAM_FAILURE) {
            failure_row(
                slot,
                BG_DOCKING_GEOMETRIC_ADMISSION_ROW_UPSTREAM_FAILURE,
                BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_UPSTREAM_NOT_AVAILABLE,
                &row);
            continue;
        }
        const std::size_t begin = slot * ligand_count;
        bool coordinates_valid = true;
        for (std::size_t atom = 0; atom < ligand_count; ++atom) {
            const Vec3 coordinate{
                candidates.x_angstrom[begin + atom],
                candidates.y_angstrom[begin + atom],
                candidates.z_angstrom[begin + atom],
            };
            coordinates_valid = coordinates_valid && finite_coordinate(coordinate);
        }
        if (!coordinates_valid) {
            failure_row(
                slot,
                BG_DOCKING_GEOMETRIC_ADMISSION_ROW_TYPED_FAILURE,
                BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_INVALID_CANDIDATE_COORDINATES,
                &row);
            continue;
        }
        row = bg_docking_geometric_admission_row_v1{};
        row.slot_index = static_cast<uint32_t>(slot);
        row.status = BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED;
        row.failure_code = BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_NONE;
        row.ligand_atom_count = ligand_count;
        row.receptor_atom_count = receptor_count;
        row.exact_pair_count = ligand_count * receptor_count;
        row.raw_minimum_distance_angstrom =
            std::numeric_limits<double>::infinity();
        row.minimum_vdw_surface_gap_angstrom =
            std::numeric_limits<double>::infinity();
        row.minimum_vdw_ratio = std::numeric_limits<double>::infinity();
        double overlap = 0.0;
        double pocket_escape = 0.0;
        for (std::size_t ligand = 0; ligand < ligand_count; ++ligand) {
            const Vec3 coordinate{
                candidates.x_angstrom[begin + ligand],
                candidates.y_angstrom[begin + ligand],
                candidates.z_angstrom[begin + ligand],
            };
            bool penetrates = false;
            for (std::size_t receptor = 0; receptor < receptor_count;
                 ++receptor) {
                const double observed =
                    distance(coordinate, context.receptor_coordinates[receptor]);
                const double radius_sum = context.ligand_radii[ligand] +
                                          context.receptor_radii[receptor];
                row.raw_minimum_distance_angstrom = std::min(
                    row.raw_minimum_distance_angstrom, observed);
                row.minimum_vdw_surface_gap_angstrom = std::min(
                    row.minimum_vdw_surface_gap_angstrom,
                    observed - radius_sum);
                row.minimum_vdw_ratio =
                    std::min(row.minimum_vdw_ratio, observed / radius_sum);
                if (observed < radius_sum) {
                    ++row.penetration_pair_count;
                    penetrates = true;
                    overlap += sphere_intersection_volume(
                        context.ligand_radii[ligand],
                        context.receptor_radii[receptor],
                        observed);
                }
            }
            if (penetrates) {
                ++row.unique_ligand_penetration_atom_count;
                if (context.ligand_heavy_atom_mask[ligand] != UINT8_C(0)) {
                    ++row.unique_ligand_heavy_atom_penetration_count;
                }
            }
            pocket_escape = std::max(
                pocket_escape,
                std::max(
                    distance(coordinate, context.pocket_center) +
                            context.ligand_radii[ligand] -
                            context.pocket_radius,
                    0.0));
        }
        row.sphere_overlap_proxy_angstrom3 = overlap;
        row.pocket_escape_angstrom = pocket_escape;
        if (!std::isfinite(row.raw_minimum_distance_angstrom) ||
            !std::isfinite(row.minimum_vdw_surface_gap_angstrom) ||
            !std::isfinite(row.minimum_vdw_ratio) ||
            !std::isfinite(overlap) || !std::isfinite(pocket_escape)) {
            failure_row(
                slot,
                BG_DOCKING_GEOMETRIC_ADMISSION_ROW_TYPED_FAILURE,
                BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_NONFINITE_DERIVED_MEASUREMENT,
                &row);
            continue;
        }
        row.rank_eligible = static_cast<uint8_t>(
            row.minimum_vdw_ratio >=
            context.hard_rejection_minimum_vdw_ratio);
        row.decision = row.rank_eligible != UINT8_C(0)
                           ? BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED
                           : BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_SEVERE_PENETRATION_REJECTED;
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bool scientific_fields_are_zero(
    const bg_docking_geometric_admission_row_v1 &row) noexcept {
    return row.ligand_atom_count == 0 && row.receptor_atom_count == 0 &&
           row.exact_pair_count == 0 && row.penetration_pair_count == 0 &&
           row.unique_ligand_penetration_atom_count == 0 &&
           row.unique_ligand_heavy_atom_penetration_count == 0 &&
           row.raw_minimum_distance_angstrom == 0.0 &&
           row.minimum_vdw_surface_gap_angstrom == 0.0 &&
           row.minimum_vdw_ratio == 0.0 &&
           row.sphere_overlap_proxy_angstrom3 == 0.0 &&
           row.pocket_escape_angstrom == 0.0;
}

[[nodiscard]] bool evaluated_row_is_valid(
    const bg_docking_geometric_admission_v1 &admission,
    const bg_docking_geometric_admission_row_v1 &row) noexcept {
    const uint64_t exact_pair_count =
        admission.ligand_atom_count * admission.receptor_atom_count;
    const bool accepted =
        row.minimum_vdw_ratio >= admission.hard_rejection_minimum_vdw_ratio;
    if (row.status != BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED ||
        row.failure_code != BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_NONE ||
        row.rank_eligible != static_cast<uint8_t>(accepted) ||
        row.decision !=
            (accepted
                 ? BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED
                 : BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_SEVERE_PENETRATION_REJECTED) ||
        row.ligand_atom_count != admission.ligand_atom_count ||
        row.receptor_atom_count != admission.receptor_atom_count ||
        row.exact_pair_count != exact_pair_count ||
        row.penetration_pair_count > exact_pair_count ||
        row.unique_ligand_penetration_atom_count >
            admission.ligand_atom_count ||
        row.unique_ligand_heavy_atom_penetration_count >
            admission.ligand_heavy_atom_count ||
        row.unique_ligand_heavy_atom_penetration_count >
            row.unique_ligand_penetration_atom_count ||
        !std::isfinite(row.raw_minimum_distance_angstrom) ||
        !std::isfinite(row.minimum_vdw_surface_gap_angstrom) ||
        !std::isfinite(row.minimum_vdw_ratio) ||
        !std::isfinite(row.sphere_overlap_proxy_angstrom3) ||
        !std::isfinite(row.pocket_escape_angstrom) ||
        row.raw_minimum_distance_angstrom < 0.0 ||
        row.minimum_vdw_surface_gap_angstrom <
            -(2.0 * kMaximumVdwRadiusAngstrom) ||
        row.minimum_vdw_ratio < 0.0 ||
        row.sphere_overlap_proxy_angstrom3 < 0.0 ||
        row.pocket_escape_angstrom < 0.0) {
        return false;
    }
    if (row.penetration_pair_count == 0) {
        return row.unique_ligand_penetration_atom_count == 0 &&
               row.unique_ligand_heavy_atom_penetration_count == 0 &&
               row.minimum_vdw_surface_gap_angstrom >= 0.0 &&
               row.sphere_overlap_proxy_angstrom3 == 0.0;
    }
    return row.unique_ligand_penetration_atom_count > 0 &&
           row.minimum_vdw_surface_gap_angstrom < 0.0 &&
           row.sphere_overlap_proxy_angstrom3 > 0.0;
}

[[nodiscard]] bool provider_row_is_valid(
    const bg_docking_geometric_admission_v1 &admission,
    const bg_docking_geometric_admission_candidate_batch_soa_v1 &candidates,
    const bg_docking_geometric_admission_row_v1 &row,
    std::size_t slot) noexcept {
    if (row.slot_index != slot || row.reserved0[0] != 0 ||
        row.reserved0[1] != 0 || row.reserved0[2] != 0 ||
        row.reserved1 != 0 || digest_present(row.row_receipt_sha256)) {
        return false;
    }
    const auto candidate_state = candidates.candidate_state[slot];
    if (candidate_state ==
        BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_UPSTREAM_FAILURE) {
        return row.status ==
                   BG_DOCKING_GEOMETRIC_ADMISSION_ROW_UPSTREAM_FAILURE &&
               row.failure_code ==
                   BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_UPSTREAM_NOT_AVAILABLE &&
               row.decision ==
                   BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_NOT_EVALUATED &&
               row.rank_eligible == 0 && scientific_fields_are_zero(row);
    }
    if (candidate_state !=
        BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_EVALUATE) {
        return false;
    }
    if (row.status == BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED) {
        return evaluated_row_is_valid(admission, row);
    }
    return row.status == BG_DOCKING_GEOMETRIC_ADMISSION_ROW_TYPED_FAILURE &&
           (row.failure_code ==
                BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_INVALID_CANDIDATE_COORDINATES ||
            row.failure_code ==
                BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_NONFINITE_DERIVED_MEASUREMENT) &&
           row.decision ==
               BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_NOT_EVALUATED &&
           row.rank_eligible == 0 && scientific_fields_are_zero(row);
}

[[nodiscard]] std::array<uint8_t, 32> coordinate_receipt(
    const bg_docking_geometric_admission_candidate_batch_soa_v1 &candidates,
    std::size_t ligand_atom_count,
    std::size_t slot) noexcept {
    CanonicalHash hash(
        "betelgeuze.geometric_admission_coordinate/native-v1");
    hash.u64(static_cast<uint64_t>(slot));
    hash.u64(static_cast<uint64_t>(ligand_atom_count));
    const std::size_t begin = slot * ligand_atom_count;
    for (std::size_t atom = 0; atom < ligand_atom_count; ++atom) {
        hash.f64(candidates.x_angstrom[begin + atom]);
        hash.f64(candidates.y_angstrom[begin + atom]);
        hash.f64(candidates.z_angstrom[begin + atom]);
    }
    return hash.finish();
}

[[nodiscard]] std::array<uint8_t, 32> row_receipt(
    const bg_docking_geometric_admission_v1 &admission,
    bg_docking_geometric_admission_candidate_state candidate_state,
    const std::array<uint8_t, 32> &coordinate,
    const bg_docking_geometric_admission_row_v1 &row) noexcept {
    CanonicalHash hash("betelgeuze.geometric_admission_row/native-v1");
    hash.string(kRowSchema);
    hash.digest(admission.authority_input_receipt_sha256);
    hash.digest(admission.receptor_system_sha256);
    hash.digest(admission.ligand_system_sha256);
    hash.digest(admission.backend_receipt_sha256);
    hash.u32(static_cast<uint32_t>(admission.backend));
    hash.u32(static_cast<uint32_t>(admission.unit_system));
    hash.u64(admission.receptor_atom_count);
    hash.u64(admission.ligand_atom_count);
    hash.u64(admission.ligand_heavy_atom_count);
    hash.u64(admission.max_batch_exact_pair_evaluations);
    hash.f64(admission.pocket_center_angstrom[0]);
    hash.f64(admission.pocket_center_angstrom[1]);
    hash.f64(admission.pocket_center_angstrom[2]);
    hash.f64(admission.pocket_radius_angstrom);
    hash.f64(admission.hard_rejection_minimum_vdw_ratio);
    hash.u32(static_cast<uint32_t>(candidate_state));
    hash.digest(coordinate);
    hash.u32(row.slot_index);
    hash.u32(static_cast<uint32_t>(row.status));
    hash.u32(static_cast<uint32_t>(row.failure_code));
    hash.u32(static_cast<uint32_t>(row.decision));
    hash.byte(row.rank_eligible);
    hash.u64(row.ligand_atom_count);
    hash.u64(row.receptor_atom_count);
    hash.u64(row.exact_pair_count);
    hash.u64(row.penetration_pair_count);
    hash.u64(row.unique_ligand_penetration_atom_count);
    hash.u64(row.unique_ligand_heavy_atom_penetration_count);
    hash.f64(row.raw_minimum_distance_angstrom);
    hash.f64(row.minimum_vdw_surface_gap_angstrom);
    hash.f64(row.minimum_vdw_ratio);
    hash.f64(row.sphere_overlap_proxy_angstrom3);
    hash.f64(row.pocket_escape_angstrom);
    return hash.finish();
}

[[nodiscard]] std::array<uint8_t, 32> batch_receipt(
    const bg_docking_geometric_admission_v1 &admission,
    const std::array<bg_docking_geometric_admission_row_v1, kCandidateCount>
        &rows) noexcept {
    CanonicalHash hash("betelgeuze.geometric_admission_batch/native-v1");
    hash.string(kBatchSchema);
    hash.digest(admission.authority_input_receipt_sha256);
    hash.digest(admission.receptor_system_sha256);
    hash.digest(admission.ligand_system_sha256);
    hash.digest(admission.backend_receipt_sha256);
    hash.u32(static_cast<uint32_t>(admission.backend));
    hash.u32(static_cast<uint32_t>(admission.unit_system));
    hash.u64(admission.receptor_atom_count);
    hash.u64(admission.ligand_atom_count);
    hash.u64(admission.ligand_heavy_atom_count);
    hash.u64(admission.max_batch_exact_pair_evaluations);
    hash.f64(admission.pocket_center_angstrom[0]);
    hash.f64(admission.pocket_center_angstrom[1]);
    hash.f64(admission.pocket_center_angstrom[2]);
    hash.f64(admission.pocket_radius_angstrom);
    hash.f64(admission.hard_rejection_minimum_vdw_ratio);
    hash.u64(static_cast<uint64_t>(rows.size()));
    for (const auto &row : rows) {
        hash.digest(row.row_receipt_sha256);
    }
    hash.byte(UINT8_C(0));  // result-dependent input consumed
    hash.byte(UINT8_C(1));  // denominator preserved
    hash.byte(UINT8_C(0));  // molecular execution authority
    hash.byte(UINT8_C(0));  // reservation authority
    hash.byte(UINT8_C(0));  // benchmark authority
    hash.byte(UINT8_C(0));  // existing-rank mutation authority
    hash.byte(UINT8_C(0));  // customer-pose authority
    hash.byte(UINT8_C(0));  // production-claim authority
    hash.byte(UINT8_C(0));  // scientific-claim authority
    return hash.finish();
}

[[nodiscard]] bg_status validate_and_bind_provider_rows(
    const bg_docking_geometric_admission_v1 &admission,
    const bg_docking_geometric_admission_candidate_batch_soa_v1 &candidates,
    std::array<bg_docking_geometric_admission_row_v1, kCandidateCount> *rows,
    std::array<uint8_t, 32> *out_batch_receipt) noexcept {
    const std::array<uint8_t, 32> no_coordinate{};
    for (std::size_t slot = 0; slot < rows->size(); ++slot) {
        auto &row = (*rows)[slot];
        if (!provider_row_is_valid(admission, candidates, row, slot)) {
            return fail(
                BG_STATUS_BACKEND_ERROR,
                "geometric-admission backend returned a non-canonical fixed64 row");
        }
        const auto coordinate =
            candidates.candidate_state[slot] ==
                    BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_UPSTREAM_FAILURE
                ? no_coordinate
                : coordinate_receipt(
                      candidates,
                      static_cast<std::size_t>(admission.ligand_atom_count),
                      slot);
        const auto receipt = row_receipt(
            admission, candidates.candidate_state[slot], coordinate, row);
        std::copy(
            receipt.begin(), receipt.end(), row.row_receipt_sha256);
    }
    *out_batch_receipt = batch_receipt(admission, *rows);
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status validate_batch_and_output(
    const bg_context &context,
    const bg_docking_geometric_admission_v1 &admission,
    const bg_docking_geometric_admission_candidate_batch_soa_v1 &candidates,
    bg_docking_geometric_admission_output_v1 &output) {
    bg_status status = validate_descriptor_header(
        candidates.struct_size,
        sizeof(candidates),
        candidates.abi_version,
        "geometric-admission batch size does not match ABI v1",
        "geometric-admission batch ABI version does not match");
    if (status != BG_STATUS_OK) return status;
    status = validate_descriptor_header(
        output.struct_size,
        sizeof(output),
        output.abi_version,
        "geometric-admission output size does not match ABI v1",
        "geometric-admission output ABI version does not match");
    if (status != BG_STATUS_OK) return status;
    if (candidates.candidate_count != kCandidateCount ||
        candidates.ligand_atom_count != admission.ligand_atom_count ||
        candidates.unit_system != admission.unit_system ||
        candidates.reserved0 != 0 ||
        !reserved_is_zero(candidates.reserved) ||
        output.row_capacity != kCandidateCount ||
        output.unit_system != admission.unit_system || output.reserved0 != 0 ||
        output.molecular_execution_authorized != 0 ||
        output.reservation_authorized != 0 ||
        output.benchmark_execution_authorized != 0 ||
        output.existing_rank_auto_change_authorized != 0 ||
        output.customer_pose_emission_authorized != 0 ||
        output.production_claim_authorized != 0 ||
        output.scientific_claim_authorized != 0 || output.reserved1 != 0) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "geometric-admission denominator, units, authority, or reserved fields are invalid");
    }
    const std::size_t coordinate_count =
        kCandidateCount * static_cast<std::size_t>(admission.ligand_atom_count);
    status = require_channel(
        candidates.candidate_state,
        kCandidateCount,
        "geometric-admission candidate state is null or misaligned");
    if (status != BG_STATUS_OK) return status;
    const std::array<const double *, 3> coordinates = {
        candidates.x_angstrom,
        candidates.y_angstrom,
        candidates.z_angstrom,
    };
    for (const double *channel : coordinates) {
        status = require_channel(
            channel,
            coordinate_count,
            "geometric-admission coordinate channel is null or misaligned");
        if (status != BG_STATUS_OK) return status;
    }
    status = require_channel(
        output.rows,
        kCandidateCount,
        "geometric-admission output rows are null or misaligned");
    if (status != BG_STATUS_OK) return status;
    std::size_t active_count = 0;
    for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
        const auto state = candidates.candidate_state[slot];
        if (state == BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_EVALUATE) {
            ++active_count;
        } else if (state !=
                   BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_UPSTREAM_FAILURE) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "geometric-admission candidate state is invalid");
        }
    }
    const uint64_t per_candidate_pairs =
        admission.ligand_atom_count * admission.receptor_atom_count;
    if (active_count > 0 &&
        per_candidate_pairs >
            std::numeric_limits<uint64_t>::max() / active_count) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "geometric-admission batch pair work overflowed");
    }
    if (per_candidate_pairs * active_count >
        admission.max_batch_exact_pair_evaluations) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "geometric-admission batch pair work exceeds the frozen cap");
    }
    std::vector<MemoryRange> inputs;
    std::vector<MemoryRange> outputs;
    inputs.reserve(7);
    outputs.reserve(2);
    status = add_range(
        &inputs, &context, 1, "geometric-admission context range overflowed");
    if (status != BG_STATUS_OK) return status;
    status = add_range(
        &inputs,
        &admission,
        1,
        "geometric-admission handle range overflowed");
    if (status != BG_STATUS_OK) return status;
    status = add_range(
        &inputs, &candidates, 1, "geometric-admission input range overflowed");
    if (status != BG_STATUS_OK) return status;
    status = add_range(
        &inputs,
        candidates.candidate_state,
        kCandidateCount,
        "geometric-admission state range overflowed");
    if (status != BG_STATUS_OK) return status;
    for (const double *channel : coordinates) {
        status = add_range(
            &inputs,
            channel,
            coordinate_count,
            "geometric-admission coordinate range overflowed");
        if (status != BG_STATUS_OK) return status;
    }
    status = add_range(
        &outputs, &output, 1, "geometric-admission output range overflowed");
    if (status != BG_STATUS_OK) return status;
    status = add_range(
        &outputs,
        output.rows,
        kCandidateCount,
        "geometric-admission row range overflowed");
    if (status != BG_STATUS_OK) return status;
    for (std::size_t left = 0; left < inputs.size(); ++left) {
        for (std::size_t right = left + 1; right < inputs.size(); ++right) {
            if (overlaps(inputs[left], inputs[right])) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "geometric-admission input channels overlap");
            }
        }
    }
    for (std::size_t left = 0; left < outputs.size(); ++left) {
        for (std::size_t right = left + 1; right < outputs.size(); ++right) {
            if (overlaps(outputs[left], outputs[right])) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "geometric-admission output channels overlap");
            }
        }
        for (MemoryRange input : inputs) {
            if (overlaps(outputs[left], input)) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "geometric-admission input and output channels overlap");
            }
        }
    }
    return BG_STATUS_OK;
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
    delete static_cast<CppGeometricContext *>(state);
}

}  // namespace betelgeuze::native::docking::geometric_admission

extern "C" BG_API bg_status BG_CALL
bg_docking_geometric_admission_context_soa_v1_init(
    bg_docking_geometric_admission_context_soa_v1 *descriptor,
    std::size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::docking::geometric_admission;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            descriptor,
            caller_struct_size,
            sizeof(*descriptor),
            caller_abi_version,
            "geometric-admission context initializer pointer is null",
            "geometric-admission context initializer size does not match",
            "geometric-admission context initializer ABI version does not match");
        if (status != BG_STATUS_OK) return status;
        *descriptor = bg_docking_geometric_admission_context_soa_v1{};
        descriptor->struct_size = static_cast<uint32_t>(sizeof(*descriptor));
        descriptor->abi_version = BG_ABI_VERSION;
        descriptor->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        descriptor->hard_rejection_minimum_vdw_ratio =
            kHardRejectionMinimumVdwRatio;
        descriptor->max_batch_exact_pair_evaluations =
            kMaxBatchPairEvaluations;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL
bg_docking_geometric_admission_candidate_batch_soa_v1_init(
    bg_docking_geometric_admission_candidate_batch_soa_v1 *batch,
    std::size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            batch,
            caller_struct_size,
            sizeof(*batch),
            caller_abi_version,
            "geometric-admission batch initializer pointer is null",
            "geometric-admission batch initializer size does not match",
            "geometric-admission batch initializer ABI version does not match");
        if (status != BG_STATUS_OK) return status;
        *batch = bg_docking_geometric_admission_candidate_batch_soa_v1{};
        batch->struct_size = static_cast<uint32_t>(sizeof(*batch));
        batch->abi_version = BG_ABI_VERSION;
        batch->candidate_count = BG_DOCKING_FIXED64_CANDIDATE_COUNT;
        batch->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL
bg_docking_geometric_admission_output_v1_init(
    bg_docking_geometric_admission_output_v1 *output,
    std::size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            output,
            caller_struct_size,
            sizeof(*output),
            caller_abi_version,
            "geometric-admission output initializer pointer is null",
            "geometric-admission output initializer size does not match",
            "geometric-admission output initializer ABI version does not match");
        if (status != BG_STATUS_OK) return status;
        *output = bg_docking_geometric_admission_output_v1{};
        output->struct_size = static_cast<uint32_t>(sizeof(*output));
        output->abi_version = BG_ABI_VERSION;
        output->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL
bg_docking_geometric_admission_v1_create(
    const bg_context *context,
    const bg_docking_geometric_admission_context_soa_v1 *descriptor,
    bg_docking_geometric_admission_v1 **out_admission) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::docking::geometric_admission;
    return guarded_status([&]() -> bg_status {
        if (context == nullptr || descriptor == nullptr ||
            out_admission == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "geometric-admission create inputs and output must not be null");
        }
        if (!pointer_is_aligned(context) ||
            !pointer_is_aligned(descriptor) ||
            !pointer_is_aligned(out_admission)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "geometric-admission create pointers are misaligned");
        }
        bg_status status = validate_context_descriptor(*descriptor);
        if (status != BG_STATUS_OK) return status;
        status = validate_create_output_range(
            *context, *descriptor, out_admission);
        if (status != BG_STATUS_OK) return status;
        *out_admission = nullptr;
        if (context->unit_system != descriptor->unit_system) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "geometric-admission context unit system is cross-wired");
        }
        auto admission =
            std::make_unique<bg_docking_geometric_admission_v1>();
        admission->backend = context->backend;
        admission->unit_system = context->unit_system;
        admission->device_ordinal = context->device_ordinal;
        admission->receptor_atom_count = descriptor->receptor_atom_count;
        admission->ligand_atom_count = descriptor->ligand_atom_count;
        admission->ligand_heavy_atom_count = static_cast<uint64_t>(
            std::count(
                descriptor->ligand_heavy_atom_mask,
                descriptor->ligand_heavy_atom_mask +
                    static_cast<std::size_t>(descriptor->ligand_atom_count),
                UINT8_C(1)));
        admission->max_batch_exact_pair_evaluations =
            descriptor->max_batch_exact_pair_evaluations;
        std::copy_n(
            descriptor->pocket_center_angstrom,
            3,
            admission->pocket_center_angstrom.begin());
        admission->pocket_radius_angstrom =
            descriptor->pocket_radius_angstrom;
        admission->hard_rejection_minimum_vdw_ratio =
            descriptor->hard_rejection_minimum_vdw_ratio;
        const std::size_t receptor_count =
            static_cast<std::size_t>(descriptor->receptor_atom_count);
        const std::size_t ligand_count =
            static_cast<std::size_t>(descriptor->ligand_atom_count);
        admission->receptor_x_angstrom.assign(
            descriptor->receptor_x_angstrom,
            descriptor->receptor_x_angstrom + receptor_count);
        admission->receptor_y_angstrom.assign(
            descriptor->receptor_y_angstrom,
            descriptor->receptor_y_angstrom + receptor_count);
        admission->receptor_z_angstrom.assign(
            descriptor->receptor_z_angstrom,
            descriptor->receptor_z_angstrom + receptor_count);
        admission->receptor_vdw_radius_angstrom.assign(
            descriptor->receptor_vdw_radius_angstrom,
            descriptor->receptor_vdw_radius_angstrom + receptor_count);
        admission->ligand_vdw_radius_angstrom.assign(
            descriptor->ligand_vdw_radius_angstrom,
            descriptor->ligand_vdw_radius_angstrom + ligand_count);
        admission->ligand_heavy_atom_mask.assign(
            descriptor->ligand_heavy_atom_mask,
            descriptor->ligand_heavy_atom_mask + ligand_count);
        std::copy_n(
            descriptor->authority_input_receipt_sha256,
            32,
            admission->authority_input_receipt_sha256.begin());
        std::copy_n(
            descriptor->receptor_system_sha256,
            32,
            admission->receptor_system_sha256.begin());
        std::copy_n(
            descriptor->ligand_system_sha256,
            32,
            admission->ligand_system_sha256.begin());
        std::copy_n(
            descriptor->backend_receipt_sha256,
            32,
            admission->backend_receipt_sha256.begin());
        if (context->backend == BG_BACKEND_CPP_CPU_REFERENCE) {
            status = create_cpp_context(*descriptor, &admission->provider_state);
        } else if (context->backend == BG_BACKEND_RUST_CPU) {
            bg_rust_cpu_error_v1 error{};
            error.struct_size = sizeof(error);
            error.abi_version = BG_RUST_CPU_PROVIDER_ABI_VERSION;
            const int32_t raw_status =
                bg_rust_cpu_docking_geometric_admission_v1_create(
                    descriptor, &admission->provider_state, &error);
            if (raw_status != BG_STATUS_OK) {
                return fail(
                    static_cast<bg_status>(raw_status),
                    error.message[0] == '\0'
                        ? "rust_cpu geometric-admission create failed"
                        : error.message);
            }
            status = BG_STATUS_OK;
        } else if (context->backend == BG_BACKEND_HIP_SAFE) {
#if BG_HAS_HIP_SAFE_PROVIDER
            void *qualification_state = nullptr;
            status = create_cpp_context(*descriptor, &qualification_state);
            if (status != BG_STATUS_OK) return status;
            std::unique_ptr<CppGeometricContext> qualification(
                static_cast<CppGeometricContext *>(qualification_state));
            char provider_error[BG_HIP_SAFE_ERROR_CAPACITY]{};
            const int32_t raw_status =
                bg_hip_safe_docking_geometric_admission_v1_create(
                    context->device_ordinal,
                    descriptor,
                    &admission->provider_state,
                    provider_error,
                    sizeof(provider_error));
            if (raw_status != BG_STATUS_OK) {
                return hip_provider_failure(
                    raw_status,
                    provider_error,
                    "hip_safe geometric-admission create failed");
            }
            status = BG_STATUS_OK;
#else
            return fail(
                BG_STATUS_BACKEND_UNAVAILABLE,
                "hip_safe geometric-admission provider is not compiled; fallback is forbidden");
#endif
        } else if (context->backend == BG_BACKEND_HIP_FAST) {
#if BG_ENABLE_HIP
            void *qualification_state = nullptr;
            status = create_cpp_context(*descriptor, &qualification_state);
            if (status != BG_STATUS_OK) return status;
            std::unique_ptr<CppGeometricContext> qualification(
                static_cast<CppGeometricContext *>(qualification_state));
            char provider_error[BG_HIP_SAFE_ERROR_CAPACITY]{};
            const int32_t raw_status =
                bg_hip_fast_docking_geometric_admission_v1_create(
                    context->device_ordinal,
                    descriptor,
                    &admission->provider_state,
                    provider_error,
                    sizeof(provider_error));
            if (raw_status != BG_STATUS_OK) {
                return hip_provider_failure(
                    raw_status,
                    provider_error,
                    "hip_fast geometric-admission create failed");
            }
            status = BG_STATUS_OK;
#else
            return fail(
                BG_STATUS_BACKEND_UNAVAILABLE,
                "hip_fast geometric-admission provider is not compiled; fallback is forbidden");
#endif
        } else {
            return fail(
                BG_STATUS_UNSUPPORTED_BACKEND,
                "selected backend has no geometric-admission implementation");
        }
        if (status != BG_STATUS_OK) return status;
        *out_admission = admission.release();
        return BG_STATUS_OK;
    });
}

extern "C" BG_API void BG_CALL bg_docking_geometric_admission_v1_destroy(
    bg_docking_geometric_admission_v1 *admission) BG_NOEXCEPT {
    if (admission == nullptr) return;
    if (admission->backend == BG_BACKEND_CPP_CPU_REFERENCE) {
        betelgeuze::native::docking::geometric_admission::destroy_cpp_state(
            admission->provider_state);
    } else if (admission->backend == BG_BACKEND_RUST_CPU) {
        bg_rust_cpu_docking_geometric_admission_v1_destroy(
            admission->provider_state);
#if BG_HAS_HIP_SAFE_PROVIDER
    } else if (admission->backend == BG_BACKEND_HIP_SAFE) {
        bg_hip_safe_docking_geometric_admission_v1_destroy(
            admission->provider_state);
#endif
#if BG_ENABLE_HIP
    } else if (admission->backend == BG_BACKEND_HIP_FAST) {
        bg_hip_fast_docking_geometric_admission_v1_destroy(
            admission->provider_state);
#endif
    }
    delete admission;
}

extern "C" BG_API bg_status BG_CALL
bg_docking_geometric_admission_v1_get_backend(
    const bg_docking_geometric_admission_v1 *admission,
    bg_backend *backend) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::docking::geometric_admission;
    return guarded_status([&]() -> bg_status {
        if (admission == nullptr || backend == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "geometric-admission handle and backend output must not be null");
        }
        if (!pointer_is_aligned(admission) || !pointer_is_aligned(backend)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "geometric-admission handle or backend output is misaligned");
        }
        const bg_status range_status =
            validate_backend_output_range(admission, backend);
        if (range_status != BG_STATUS_OK) return range_status;
        *backend = admission->backend;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL
bg_docking_geometric_admission_v1_evaluate_fixed64(
    const bg_context *context,
    const bg_docking_geometric_admission_v1 *admission,
    const bg_docking_geometric_admission_candidate_batch_soa_v1 *candidates,
    bg_docking_geometric_admission_output_v1 *output) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::docking::geometric_admission;
    return guarded_status([&]() -> bg_status {
        if (context == nullptr || admission == nullptr ||
            candidates == nullptr || output == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "geometric-admission evaluation inputs and output must not be null");
        }
        if (!pointer_is_aligned(context) ||
            !pointer_is_aligned(admission) ||
            !pointer_is_aligned(candidates) ||
            !pointer_is_aligned(output)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "geometric-admission evaluation descriptors are misaligned");
        }
        if (context->backend != admission->backend ||
            context->unit_system != admission->unit_system ||
            context->device_ordinal != admission->device_ordinal ||
            admission->provider_state == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "geometric-admission handle is cross-wired to another context");
        }
        bg_status status = validate_batch_and_output(
            *context, *admission, *candidates, *output);
        if (status != BG_STATUS_OK) return status;
        std::array<bg_docking_geometric_admission_row_v1, kCandidateCount>
            rows{};
        if (admission->backend == BG_BACKEND_CPP_CPU_REFERENCE) {
            status = evaluate_cpp_fixed64(
                *static_cast<const CppGeometricContext *>(
                    admission->provider_state),
                *candidates,
                &rows);
        } else if (admission->backend == BG_BACKEND_RUST_CPU) {
            bg_rust_cpu_error_v1 error{};
            error.struct_size = sizeof(error);
            error.abi_version = BG_RUST_CPU_PROVIDER_ABI_VERSION;
            const int32_t raw_status =
                bg_rust_cpu_docking_geometric_admission_v1_evaluate_fixed64(
                    admission->provider_state,
                    candidates,
                    rows.data(),
                    &error);
            if (raw_status != BG_STATUS_OK) {
                return fail(
                    static_cast<bg_status>(raw_status),
                    error.message[0] == '\0'
                        ? "rust_cpu geometric-admission batch failed"
                        : error.message);
            }
            status = BG_STATUS_OK;
#if BG_HAS_HIP_SAFE_PROVIDER
        } else if (admission->backend == BG_BACKEND_HIP_SAFE) {
            char provider_error[BG_HIP_SAFE_ERROR_CAPACITY]{};
            const int32_t raw_status =
                bg_hip_safe_docking_geometric_admission_v1_evaluate_fixed64(
                    admission->provider_state,
                    candidates,
                    rows.data(),
                    provider_error,
                    sizeof(provider_error));
            if (raw_status != BG_STATUS_OK) {
                return hip_provider_failure(
                    raw_status,
                    provider_error,
                    "hip_safe geometric-admission batch failed");
            }
            status = BG_STATUS_OK;
#endif
#if BG_ENABLE_HIP
        } else if (admission->backend == BG_BACKEND_HIP_FAST) {
            char provider_error[BG_HIP_SAFE_ERROR_CAPACITY]{};
            const int32_t raw_status =
                bg_hip_fast_docking_geometric_admission_v1_evaluate_fixed64(
                    admission->provider_state,
                    candidates,
                    rows.data(),
                    provider_error,
                    sizeof(provider_error));
            if (raw_status != BG_STATUS_OK) {
                return hip_provider_failure(
                    raw_status,
                    provider_error,
                    "hip_fast geometric-admission batch failed");
            }
            status = BG_STATUS_OK;
#endif
        } else {
            return fail(
                BG_STATUS_BACKEND_UNAVAILABLE,
                "selected backend has no geometric-admission kernel; fallback is forbidden");
        }
        if (status != BG_STATUS_OK) return status;
        std::array<uint8_t, 32> receipt{};
        status = validate_and_bind_provider_rows(
            *admission, *candidates, &rows, &receipt);
        if (status != BG_STATUS_OK) return status;
        std::memcpy(output->rows, rows.data(), sizeof(rows));
        output->row_count = kCandidateCount;
        std::copy(
            receipt.begin(), receipt.end(), output->batch_receipt_sha256);
        return BG_STATUS_OK;
    });
}
