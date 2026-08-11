#include "../internal.hpp"
#include "../rust/provider.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <map>
#include <memory>
#include <set>
#include <tuple>
#include <utility>
#include <vector>

namespace betelgeuze::native::docking::validity {
namespace {

constexpr std::size_t kCandidateCount = BG_DOCKING_FIXED64_CANDIDATE_COUNT;
constexpr std::size_t kMaxLigandAtoms = 512;
constexpr std::size_t kMaxReceptorAtoms = 4096;
constexpr std::size_t kMaxPairChecks = 2'000'000;
constexpr std::size_t kMaxCrossChecks = 4'000'000;
constexpr double kMaxCoordinate = 100'000.0;
constexpr double kMinimumSentinel = 999.0;

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

using Pair = std::pair<std::size_t, std::size_t>;
using Chirality = std::array<std::size_t, 4>;
using Cell = std::tuple<int64_t, int64_t, int64_t>;

struct CppValidityContext final {
    std::vector<Vec3> reference_coordinates;
    std::vector<Vec3> receptor_coordinates;
    std::vector<double> ligand_radii;
    std::vector<double> receptor_radii;
    std::vector<Pair> bonds;
    std::set<Pair> exclusions;
    std::vector<Chirality> chirality_centers;
    Vec3 pocket_center;
    double pocket_radius = 0.0;
    double bond_length_tolerance = 0.0;
    double ligand_self_clash = 0.0;
    double receptor_ligand_clash = 0.0;
    double rotation_tolerance = 0.0;
    double chirality_volume_tolerance = 0.0;
    double severe_overlap_scale = 0.0;
    double contact_cell_size = 0.0;
    std::size_t max_pair_checks = 0;
    std::size_t max_cross_checks = 0;
    std::size_t max_element_ligand_pair_checks = 0;
    std::size_t max_element_receptor_candidate_pairs = 0;
    std::map<Cell, std::vector<std::size_t>> receptor_cells;
};

struct CandidateFailure final {
    bg_docking_pose_validity_failure code =
        BG_DOCKING_POSE_VALIDITY_FAILURE_NONE;
    std::size_t observed_count = 0;
};

[[nodiscard]] bool digest_present(const uint8_t (&digest)[32]) noexcept {
    return std::any_of(
        std::begin(digest), std::end(digest), [](uint8_t value) {
            return value != UINT8_C(0);
        });
}

[[nodiscard]] bool finite_coordinate(Vec3 value) noexcept {
    return std::isfinite(value.x) && std::isfinite(value.y) &&
           std::isfinite(value.z) && std::abs(value.x) <= kMaxCoordinate &&
           std::abs(value.y) <= kMaxCoordinate &&
           std::abs(value.z) <= kMaxCoordinate;
}

[[nodiscard]] Vec3 minus(Vec3 left, Vec3 right) noexcept {
    return {left.x - right.x, left.y - right.y, left.z - right.z};
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

[[nodiscard]] double distance(Vec3 left, Vec3 right) noexcept {
    const Vec3 delta = minus(left, right);
    return std::sqrt(dot(delta, delta));
}

[[nodiscard]] double minimum_or_sentinel(double value) noexcept {
    return std::isfinite(value) ? value : kMinimumSentinel;
}

[[nodiscard]] Cell cell_key(Vec3 value, double size) noexcept {
    return {
        static_cast<int64_t>(std::floor(value.x / size)),
        static_cast<int64_t>(std::floor(value.y / size)),
        static_cast<int64_t>(std::floor(value.z / size)),
    };
}

[[nodiscard]] double signed_volume(
    const std::vector<Vec3> &coordinates,
    const Chirality &indices) noexcept {
    const Vec3 origin = coordinates[indices[0]];
    return dot(
        cross(
            minus(coordinates[indices[1]], origin),
            minus(coordinates[indices[2]], origin)),
        minus(coordinates[indices[3]], origin));
}

[[nodiscard]] std::pair<double, double> rotation_measurements(
    Quaternion quaternion) noexcept {
    const double x = quaternion.x;
    const double y = quaternion.y;
    const double z = quaternion.z;
    const double w = quaternion.w;
    const std::array<std::array<double, 3>, 3> matrix = {{
        {{
            1.0 - 2.0 * (y * y + z * z),
            2.0 * (x * y - z * w),
            2.0 * (x * z + y * w),
        }},
        {{
            2.0 * (x * y + z * w),
            1.0 - 2.0 * (x * x + z * z),
            2.0 * (y * z - x * w),
        }},
        {{
            2.0 * (x * z - y * w),
            2.0 * (y * z + x * w),
            1.0 - 2.0 * (x * x + y * y),
        }},
    }};
    double maximum = 0.0;
    for (std::size_t row = 0; row < 3; ++row) {
        for (std::size_t column = 0; column < 3; ++column) {
            double value = 0.0;
            for (std::size_t index = 0; index < 3; ++index) {
                value += matrix[index][row] * matrix[index][column];
            }
            maximum = std::max(
                maximum,
                std::abs(value - (row == column ? 1.0 : 0.0)));
        }
    }
    const double determinant =
        matrix[0][0] *
            (matrix[1][1] * matrix[2][2] -
             matrix[1][2] * matrix[2][1]) -
        matrix[0][1] *
            (matrix[1][0] * matrix[2][2] -
             matrix[1][2] * matrix[2][0]) +
        matrix[0][2] *
            (matrix[1][0] * matrix[2][1] -
             matrix[1][1] * matrix[2][0]);
    return {maximum, determinant};
}

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

[[nodiscard]] bg_status checked_counts(
    const bg_docking_pose_validity_context_soa_v1 &descriptor,
    std::size_t *receptor_count,
    std::size_t *ligand_count,
    std::size_t *bond_count,
    std::size_t *exclusion_count,
    std::size_t *chirality_count) noexcept {
    if (descriptor.receptor_atom_count == 0 ||
        descriptor.receptor_atom_count > kMaxReceptorAtoms ||
        descriptor.ligand_atom_count == 0 ||
        descriptor.ligand_atom_count > kMaxLigandAtoms) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "pose-validity atom denominator is outside fixed bounds");
    }
    const uint64_t maximum_pairs =
        descriptor.ligand_atom_count *
        (descriptor.ligand_atom_count - UINT64_C(1)) / UINT64_C(2);
    if (descriptor.bond_count > maximum_pairs ||
        descriptor.ligand_exclusion_count > maximum_pairs ||
        descriptor.chirality_center_count > descriptor.ligand_atom_count) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "pose-validity topology denominator is outside fixed bounds");
    }
    *receptor_count =
        static_cast<std::size_t>(descriptor.receptor_atom_count);
    *ligand_count = static_cast<std::size_t>(descriptor.ligand_atom_count);
    *bond_count = static_cast<std::size_t>(descriptor.bond_count);
    *exclusion_count =
        static_cast<std::size_t>(descriptor.ligand_exclusion_count);
    *chirality_count =
        static_cast<std::size_t>(descriptor.chirality_center_count);
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status validate_context_channels(
    const bg_docking_pose_validity_context_soa_v1 &descriptor,
    std::size_t receptor_count,
    std::size_t ligand_count,
    std::size_t bond_count,
    std::size_t exclusion_count,
    std::size_t chirality_count) noexcept {
    const std::array<const double *, 4> receptor_channels = {
        descriptor.receptor_x_angstrom,
        descriptor.receptor_y_angstrom,
        descriptor.receptor_z_angstrom,
        descriptor.receptor_vdw_radius_angstrom,
    };
    const std::array<const double *, 4> ligand_channels = {
        descriptor.ligand_reference_x_angstrom,
        descriptor.ligand_reference_y_angstrom,
        descriptor.ligand_reference_z_angstrom,
        descriptor.ligand_vdw_radius_angstrom,
    };
    for (const double *channel : receptor_channels) {
        const bg_status status = require_channel(
            channel,
            receptor_count,
            "pose-validity receptor channel is null or misaligned");
        if (status != BG_STATUS_OK) {
            return status;
        }
    }
    for (const double *channel : ligand_channels) {
        const bg_status status = require_channel(
            channel,
            ligand_count,
            "pose-validity ligand channel is null or misaligned");
        if (status != BG_STATUS_OK) {
            return status;
        }
    }
    const std::array<std::pair<const uint64_t *, std::size_t>, 10>
        index_channels = {{
            {descriptor.bond_atom_i, bond_count},
            {descriptor.bond_atom_j, bond_count},
            {descriptor.ligand_exclusion_atom_i, exclusion_count},
            {descriptor.ligand_exclusion_atom_j, exclusion_count},
            {descriptor.chirality_center_atom, chirality_count},
            {descriptor.chirality_atom_i, chirality_count},
            {descriptor.chirality_atom_j, chirality_count},
            {descriptor.chirality_atom_k, chirality_count},
            {nullptr, 0},
            {nullptr, 0},
        }};
    for (const auto &[channel, count] : index_channels) {
        const bg_status status = require_channel(
            channel,
            count,
            "pose-validity topology channel is null or misaligned");
        if (status != BG_STATUS_OK) {
            return status;
        }
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status copy_coordinates_and_radii(
    const double *x,
    const double *y,
    const double *z,
    const double *radius,
    std::size_t count,
    std::vector<Vec3> *coordinates,
    std::vector<double> *radii) {
    coordinates->reserve(count);
    radii->reserve(count);
    for (std::size_t index = 0; index < count; ++index) {
        const Vec3 coordinate{x[index], y[index], z[index]};
        if (!finite_coordinate(coordinate) || !std::isfinite(radius[index]) ||
            radius[index] < 0.1 || radius[index] > 10.0) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "pose-validity atom coordinate or vdW radius is invalid");
        }
        coordinates->push_back(coordinate);
        radii->push_back(radius[index]);
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status copy_pairs(
    const uint64_t *first,
    const uint64_t *second,
    std::size_t count,
    std::size_t ligand_count,
    std::vector<Pair> *out) {
    out->reserve(count);
    for (std::size_t row = 0; row < count; ++row) {
        if (first[row] >= second[row] || second[row] >= ligand_count) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "pose-validity pair is not canonical and in-range");
        }
        const Pair pair{
            static_cast<std::size_t>(first[row]),
            static_cast<std::size_t>(second[row]),
        };
        if (!out->empty() && !(out->back() < pair)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "pose-validity pairs are duplicated or unsorted");
        }
        out->push_back(pair);
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status validate_config(
    const bg_docking_pose_validity_context_soa_v1 &descriptor,
    const std::vector<double> &ligand_radii,
    const std::vector<double> &receptor_radii) noexcept {
    const std::array<double, 5> bounded = {
        descriptor.bond_length_tolerance_angstrom,
        descriptor.ligand_self_clash_angstrom,
        descriptor.receptor_ligand_clash_angstrom,
        descriptor.rotation_tolerance,
        descriptor.chirality_volume_tolerance,
    };
    if (std::any_of(bounded.begin(), bounded.end(), [](double value) {
            return !std::isfinite(value) || value < 0.0 || value > 100.0;
        }) ||
        !std::isfinite(descriptor.severe_overlap_scale) ||
        descriptor.severe_overlap_scale < 0.1 ||
        descriptor.severe_overlap_scale > 1.0 ||
        !std::isfinite(descriptor.contact_cell_size_angstrom) ||
        descriptor.contact_cell_size_angstrom < 0.5 ||
        descriptor.contact_cell_size_angstrom > 10.0 ||
        descriptor.max_pair_checks > kMaxPairChecks ||
        descriptor.max_cross_checks > kMaxCrossChecks ||
        descriptor.max_element_ligand_pair_checks > kMaxPairChecks ||
        descriptor.max_element_receptor_candidate_pairs > kMaxCrossChecks) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "pose-validity configuration is outside frozen bounds");
    }
    const double maximum_radius = std::max(
        *std::max_element(ligand_radii.begin(), ligand_radii.end()),
        *std::max_element(receptor_radii.begin(), receptor_radii.end()));
    if (descriptor.contact_cell_size_angstrom + 1.0e-12 <
        2.0 * maximum_radius * descriptor.severe_overlap_scale) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "pose-validity contact cell does not cover severe overlap");
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status create_cpp_context(
    const bg_docking_pose_validity_context_soa_v1 &descriptor,
    void **out_state) {
    std::size_t receptor_count = 0;
    std::size_t ligand_count = 0;
    std::size_t bond_count = 0;
    std::size_t exclusion_count = 0;
    std::size_t chirality_count = 0;
    bg_status status = checked_counts(
        descriptor,
        &receptor_count,
        &ligand_count,
        &bond_count,
        &exclusion_count,
        &chirality_count);
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = validate_context_channels(
        descriptor,
        receptor_count,
        ligand_count,
        bond_count,
        exclusion_count,
        chirality_count);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (!digest_present(descriptor.authority_input_receipt_sha256) ||
        !digest_present(descriptor.receptor_system_sha256) ||
        !digest_present(descriptor.ligand_system_sha256) ||
        !digest_present(descriptor.scorer_context_receipt_sha256) ||
        !digest_present(descriptor.backend_receipt_sha256) ||
        !digest_present(descriptor.contact_policy_sha256)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "pose-validity identity digest is missing");
    }
    auto context = std::make_unique<CppValidityContext>();
    status = copy_coordinates_and_radii(
        descriptor.ligand_reference_x_angstrom,
        descriptor.ligand_reference_y_angstrom,
        descriptor.ligand_reference_z_angstrom,
        descriptor.ligand_vdw_radius_angstrom,
        ligand_count,
        &context->reference_coordinates,
        &context->ligand_radii);
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = copy_coordinates_and_radii(
        descriptor.receptor_x_angstrom,
        descriptor.receptor_y_angstrom,
        descriptor.receptor_z_angstrom,
        descriptor.receptor_vdw_radius_angstrom,
        receptor_count,
        &context->receptor_coordinates,
        &context->receptor_radii);
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = copy_pairs(
        descriptor.bond_atom_i,
        descriptor.bond_atom_j,
        bond_count,
        ligand_count,
        &context->bonds);
    if (status != BG_STATUS_OK) {
        return status;
    }
    std::vector<Pair> exclusions;
    status = copy_pairs(
        descriptor.ligand_exclusion_atom_i,
        descriptor.ligand_exclusion_atom_j,
        exclusion_count,
        ligand_count,
        &exclusions);
    if (status != BG_STATUS_OK) {
        return status;
    }
    context->exclusions.insert(exclusions.begin(), exclusions.end());
    if (std::any_of(
            context->bonds.begin(),
            context->bonds.end(),
            [&context](const Pair &bond) {
                return context->exclusions.find(bond) ==
                       context->exclusions.end();
            })) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "pose-validity exclusions must contain every bond");
    }
    std::set<Chirality> unique_chirality;
    context->chirality_centers.reserve(chirality_count);
    for (std::size_t row = 0; row < chirality_count; ++row) {
        const std::array<uint64_t, 4> raw = {
            descriptor.chirality_center_atom[row],
            descriptor.chirality_atom_i[row],
            descriptor.chirality_atom_j[row],
            descriptor.chirality_atom_k[row],
        };
        if (std::any_of(raw.begin(), raw.end(), [ligand_count](uint64_t value) {
                return value >= ligand_count;
            }) ||
            std::set<uint64_t>(raw.begin(), raw.end()).size() != raw.size()) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "pose-validity chirality row is invalid");
        }
        const Chirality chirality = {
            static_cast<std::size_t>(raw[0]),
            static_cast<std::size_t>(raw[1]),
            static_cast<std::size_t>(raw[2]),
            static_cast<std::size_t>(raw[3]),
        };
        if (!unique_chirality.insert(chirality).second) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "pose-validity chirality rows are duplicated");
        }
        context->chirality_centers.push_back(chirality);
    }
    context->pocket_center = {
        descriptor.pocket_center_angstrom[0],
        descriptor.pocket_center_angstrom[1],
        descriptor.pocket_center_angstrom[2],
    };
    context->pocket_radius = descriptor.pocket_radius_angstrom;
    if (!finite_coordinate(context->pocket_center) ||
        !std::isfinite(context->pocket_radius) ||
        context->pocket_radius <= 0.0 || context->pocket_radius > 1'000.0) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "pose-validity pocket geometry is outside frozen bounds");
    }
    status = validate_config(
        descriptor, context->ligand_radii, context->receptor_radii);
    if (status != BG_STATUS_OK) {
        return status;
    }
    context->bond_length_tolerance =
        descriptor.bond_length_tolerance_angstrom;
    context->ligand_self_clash = descriptor.ligand_self_clash_angstrom;
    context->receptor_ligand_clash =
        descriptor.receptor_ligand_clash_angstrom;
    context->rotation_tolerance = descriptor.rotation_tolerance;
    context->chirality_volume_tolerance =
        descriptor.chirality_volume_tolerance;
    context->severe_overlap_scale = descriptor.severe_overlap_scale;
    context->contact_cell_size = descriptor.contact_cell_size_angstrom;
    context->max_pair_checks =
        static_cast<std::size_t>(descriptor.max_pair_checks);
    context->max_cross_checks =
        static_cast<std::size_t>(descriptor.max_cross_checks);
    context->max_element_ligand_pair_checks =
        static_cast<std::size_t>(descriptor.max_element_ligand_pair_checks);
    context->max_element_receptor_candidate_pairs = static_cast<std::size_t>(
        descriptor.max_element_receptor_candidate_pairs);
    for (std::size_t index = 0;
         index < context->receptor_coordinates.size();
         ++index) {
        context
            ->receptor_cells[cell_key(
                context->receptor_coordinates[index],
                context->contact_cell_size)]
            .push_back(index);
    }
    *out_state = context.release();
    return BG_STATUS_OK;
}

[[nodiscard]] bool measurements_finite(
    const bg_docking_pose_validity_row_v1 &row) noexcept {
    const std::array<double, 12> values = {
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
        static_cast<double>(row.atom_count),
    };
    return std::all_of(values.begin(), values.end(), [](double value) {
        return std::isfinite(value);
    });
}

[[nodiscard]] bg_docking_pose_validity_row_v1 failure_row(
    std::size_t slot,
    bg_docking_pose_validity_row_status status,
    bg_docking_pose_validity_failure failure_code,
    bg_docking_scorer_v1_failure upstream_failure,
    std::size_t observed_count) noexcept {
    bg_docking_pose_validity_row_v1 row{};
    row.slot_index = static_cast<uint32_t>(slot);
    row.status = status;
    row.failure_code = failure_code;
    row.upstream_scorer_failure_code = upstream_failure;
    row.observed_count = static_cast<uint64_t>(observed_count);
    return row;
}

[[nodiscard]] std::pair<bg_docking_pose_validity_row_v1, CandidateFailure>
evaluate_candidate(
    const CppValidityContext &context,
    const std::vector<Vec3> &coordinates,
    Quaternion quaternion,
    std::size_t slot) noexcept {
    bg_docking_pose_validity_row_v1 row{};
    row.slot_index = static_cast<uint32_t>(slot);
    row.status = BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED;
    row.failure_code = BG_DOCKING_POSE_VALIDITY_FAILURE_NONE;
    if (coordinates.size() != context.reference_coordinates.size() ||
        std::any_of(
            coordinates.begin(), coordinates.end(), [](Vec3 value) {
                return !finite_coordinate(value);
            })) {
        return {
            row,
            {
                BG_DOCKING_POSE_VALIDITY_FAILURE_INVALID_CANDIDATE_COORDINATES,
                coordinates.size(),
            },
        };
    }
    const auto [orthogonality_error, determinant] =
        rotation_measurements(quaternion);
    row.rotation_orthogonality_max_error = orthogonality_error;
    row.rotation_determinant = determinant;
    if (orthogonality_error <= context.rotation_tolerance &&
        std::abs(determinant - 1.0) <= context.rotation_tolerance) {
        row.passed_check_mask |=
            BG_DOCKING_POSE_VALIDITY_CHECK_PROPER_ROTATION;
    }

    double maximum_bond_delta = 0.0;
    for (const auto &[first, second] : context.bonds) {
        const double reference = distance(
            context.reference_coordinates[first],
            context.reference_coordinates[second]);
        const double observed =
            distance(coordinates[first], coordinates[second]);
        maximum_bond_delta =
            std::max(maximum_bond_delta, std::abs(reference - observed));
    }
    row.max_bond_length_delta_angstrom = maximum_bond_delta;
    if (maximum_bond_delta <= context.bond_length_tolerance) {
        row.passed_check_mask |=
            BG_DOCKING_POSE_VALIDITY_CHECK_BOND_LENGTHS;
    }

    const std::size_t ligand_pair_count =
        coordinates.size() * (coordinates.size() - 1) / 2;
    if (ligand_pair_count > context.max_pair_checks) {
        return {
            row,
            {
                BG_DOCKING_POSE_VALIDITY_FAILURE_LIGAND_PAIR_CAPACITY,
                ligand_pair_count,
            },
        };
    }
    double minimum_ligand_distance = INFINITY;
    double minimum_ligand_ratio = INFINITY;
    std::size_t evaluated_ligand_pairs = 0;
    std::size_t ligand_severe_overlap_count = 0;
    for (std::size_t first = 0; first < coordinates.size(); ++first) {
        for (std::size_t second = first + 1; second < coordinates.size();
             ++second) {
            if (context.exclusions.find({first, second}) !=
                context.exclusions.end()) {
                continue;
            }
            ++evaluated_ligand_pairs;
            if (evaluated_ligand_pairs >
                context.max_element_ligand_pair_checks) {
                return {
                    row,
                    {
                        BG_DOCKING_POSE_VALIDITY_FAILURE_ELEMENT_LIGAND_PAIR_CAPACITY,
                        evaluated_ligand_pairs,
                    },
                };
            }
            const double observed =
                distance(coordinates[first], coordinates[second]);
            minimum_ligand_distance =
                std::min(minimum_ligand_distance, observed);
            const double ratio =
                observed /
                (context.ligand_radii[first] + context.ligand_radii[second]);
            minimum_ligand_ratio = std::min(minimum_ligand_ratio, ratio);
            if (ratio < context.severe_overlap_scale) {
                ++ligand_severe_overlap_count;
            }
        }
    }
    row.minimum_ligand_nonbonded_distance_angstrom =
        minimum_or_sentinel(minimum_ligand_distance);
    row.evaluated_ligand_nonbonded_pair_count =
        static_cast<uint64_t>(evaluated_ligand_pairs);
    row.excluded_ligand_pair_count =
        static_cast<uint64_t>(context.exclusions.size());
    row.element_vdw_ligand_pair_count =
        static_cast<uint64_t>(evaluated_ligand_pairs);
    row.element_vdw_ligand_severe_overlap_count =
        static_cast<uint64_t>(ligand_severe_overlap_count);
    row.element_vdw_ligand_minimum_distance_angstrom =
        minimum_or_sentinel(minimum_ligand_distance);
    row.element_vdw_ligand_minimum_ratio =
        minimum_or_sentinel(minimum_ligand_ratio);
    if (row.minimum_ligand_nonbonded_distance_angstrom >=
        context.ligand_self_clash) {
        row.passed_check_mask |=
            BG_DOCKING_POSE_VALIDITY_CHECK_LIGAND_SELF_CLASH;
    }
    if (ligand_severe_overlap_count == 0) {
        row.passed_check_mask |=
            BG_DOCKING_POSE_VALIDITY_CHECK_ELEMENT_LIGAND_VDW;
    }

    const std::size_t cross_count =
        coordinates.size() * context.receptor_coordinates.size();
    if (cross_count > context.max_cross_checks) {
        return {
            row,
            {
                BG_DOCKING_POSE_VALIDITY_FAILURE_RECEPTOR_CROSS_CAPACITY,
                cross_count,
            },
        };
    }
    double minimum_receptor_distance = INFINITY;
    for (const Vec3 coordinate : coordinates) {
        for (const Vec3 receptor : context.receptor_coordinates) {
            minimum_receptor_distance = std::min(
                minimum_receptor_distance, distance(coordinate, receptor));
        }
    }
    row.minimum_receptor_ligand_distance_angstrom =
        minimum_receptor_distance;
    row.evaluated_receptor_ligand_pair_count =
        static_cast<uint64_t>(cross_count);
    if (minimum_receptor_distance >= context.receptor_ligand_clash) {
        row.passed_check_mask |=
            BG_DOCKING_POSE_VALIDITY_CHECK_RECEPTOR_LIGAND_CLASH;
    }

    double minimum_chiral_volume = INFINITY;
    bool chirality_preserved = true;
    for (const Chirality &indices : context.chirality_centers) {
        const double reference =
            signed_volume(context.reference_coordinates, indices);
        const double observed = signed_volume(coordinates, indices);
        minimum_chiral_volume = std::min(
            minimum_chiral_volume,
            std::min(std::abs(reference), std::abs(observed)));
        if (std::abs(reference) <= context.chirality_volume_tolerance ||
            std::abs(observed) <= context.chirality_volume_tolerance ||
            reference * observed < 0.0) {
            chirality_preserved = false;
        }
    }
    row.minimum_declared_chiral_volume =
        std::isfinite(minimum_chiral_volume) ? minimum_chiral_volume : 0.0;
    row.declared_chirality_center_count =
        static_cast<uint64_t>(context.chirality_centers.size());
    if (chirality_preserved) {
        row.passed_check_mask |= BG_DOCKING_POSE_VALIDITY_CHECK_CHIRALITY;
    }

    double maximum_pocket_distance = 0.0;
    for (const Vec3 coordinate : coordinates) {
        maximum_pocket_distance = std::max(
            maximum_pocket_distance,
            distance(coordinate, context.pocket_center));
    }
    row.maximum_pocket_center_distance_angstrom = maximum_pocket_distance;
    if (maximum_pocket_distance <= context.pocket_radius) {
        row.passed_check_mask |=
            BG_DOCKING_POSE_VALIDITY_CHECK_DECLARED_POCKET;
    }

    std::size_t receptor_candidate_pair_count = 0;
    std::size_t receptor_severe_overlap_count = 0;
    double minimum_receptor_element_distance = INFINITY;
    double minimum_receptor_ratio = INFINITY;
    for (std::size_t ligand_index = 0;
         ligand_index < coordinates.size();
         ++ligand_index) {
        const Vec3 coordinate = coordinates[ligand_index];
        const Cell center = cell_key(coordinate, context.contact_cell_size);
        for (int64_t x = std::get<0>(center) - 1;
             x <= std::get<0>(center) + 1;
             ++x) {
            for (int64_t y = std::get<1>(center) - 1;
                 y <= std::get<1>(center) + 1;
                 ++y) {
                for (int64_t z = std::get<2>(center) - 1;
                     z <= std::get<2>(center) + 1;
                     ++z) {
                    const auto found = context.receptor_cells.find({x, y, z});
                    if (found == context.receptor_cells.end()) {
                        continue;
                    }
                    for (const std::size_t receptor_index : found->second) {
                        ++receptor_candidate_pair_count;
                        if (receptor_candidate_pair_count >
                            context.max_element_receptor_candidate_pairs) {
                            return {
                                row,
                                {
                                    BG_DOCKING_POSE_VALIDITY_FAILURE_ELEMENT_RECEPTOR_CANDIDATE_CAPACITY,
                                    receptor_candidate_pair_count,
                                },
                            };
                        }
                        const double observed = distance(
                            coordinate,
                            context.receptor_coordinates[receptor_index]);
                        minimum_receptor_element_distance = std::min(
                            minimum_receptor_element_distance, observed);
                        const double ratio =
                            observed /
                            (context.ligand_radii[ligand_index] +
                             context.receptor_radii[receptor_index]);
                        minimum_receptor_ratio =
                            std::min(minimum_receptor_ratio, ratio);
                        if (ratio < context.severe_overlap_scale) {
                            ++receptor_severe_overlap_count;
                        }
                    }
                }
            }
        }
    }
    row.element_vdw_receptor_candidate_pair_count =
        static_cast<uint64_t>(receptor_candidate_pair_count);
    row.element_vdw_receptor_full_cartesian_pair_count =
        static_cast<uint64_t>(cross_count);
    row.element_vdw_receptor_cell_count =
        static_cast<uint64_t>(context.receptor_cells.size());
    row.element_vdw_receptor_severe_overlap_count =
        static_cast<uint64_t>(receptor_severe_overlap_count);
    row.element_vdw_receptor_minimum_distance_angstrom =
        minimum_or_sentinel(minimum_receptor_element_distance);
    row.element_vdw_receptor_minimum_ratio =
        minimum_or_sentinel(minimum_receptor_ratio);
    if (receptor_severe_overlap_count == 0) {
        row.passed_check_mask |=
            BG_DOCKING_POSE_VALIDITY_CHECK_ELEMENT_RECEPTOR_VDW;
    }
    row.atom_count = static_cast<uint64_t>(coordinates.size());
    row.blocker_mask =
        BG_DOCKING_POSE_VALIDITY_CHECK_ALL ^ row.passed_check_mask;
    if (!measurements_finite(row)) {
        return {
            row,
            {
                BG_DOCKING_POSE_VALIDITY_FAILURE_NONFINITE_DERIVED_MEASUREMENT,
                0,
            },
        };
    }
    return {row, {}};
}

[[nodiscard]] bg_status evaluate_cpp_fixed64(
    const CppValidityContext &context,
    const bg_docking_pose_validity_candidate_batch_soa_v1 &candidates,
    std::array<bg_docking_pose_validity_row_v1, kCandidateCount> *out) {
    const std::size_t ligand_count = context.reference_coordinates.size();
    for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
        if (candidates.candidate_state[slot] ==
            BG_DOCKING_POSE_VALIDITY_CANDIDATE_UPSTREAM_FAILURE) {
            (*out)[slot] = failure_row(
                slot,
                BG_DOCKING_POSE_VALIDITY_ROW_UPSTREAM_SCORER_FAILURE,
                BG_DOCKING_POSE_VALIDITY_FAILURE_UPSTREAM_SCORER,
                candidates.upstream_scorer_failure_code[slot],
                0);
            continue;
        }
        std::vector<Vec3> coordinates;
        coordinates.reserve(ligand_count);
        const std::size_t offset = slot * ligand_count;
        for (std::size_t atom = 0; atom < ligand_count; ++atom) {
            coordinates.push_back({
                candidates.x_angstrom[offset + atom],
                candidates.y_angstrom[offset + atom],
                candidates.z_angstrom[offset + atom],
            });
        }
        const Quaternion quaternion{
            candidates.quaternion_x[slot],
            candidates.quaternion_y[slot],
            candidates.quaternion_z[slot],
            candidates.quaternion_w[slot],
        };
        const auto [evaluated, failure] =
            evaluate_candidate(context, coordinates, quaternion, slot);
        if (failure.code == BG_DOCKING_POSE_VALIDITY_FAILURE_NONE) {
            (*out)[slot] = evaluated;
        } else {
            (*out)[slot] = failure_row(
                slot,
                BG_DOCKING_POSE_VALIDITY_ROW_TYPED_FAILURE,
                failure.code,
                BG_DOCKING_SCORER_V1_FAILURE_NONE,
                failure.observed_count);
        }
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status validate_batch_and_output(
    const bg_docking_pose_validity_v1 *validity,
    const bg_docking_pose_validity_candidate_batch_soa_v1 &candidates,
    const bg_docking_pose_validity_output_v1 &output) noexcept {
    bg_status status = validate_descriptor_header(
        candidates.struct_size,
        sizeof(candidates),
        candidates.abi_version,
        "pose-validity candidate descriptor size does not match ABI v1",
        "pose-validity candidate descriptor ABI version does not match");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = validate_descriptor_header(
        output.struct_size,
        sizeof(output),
        output.abi_version,
        "pose-validity output descriptor size does not match ABI v1",
        "pose-validity output descriptor ABI version does not match");
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (validate_unit_system(candidates.unit_system) != BG_STATUS_OK ||
        validate_unit_system(output.unit_system) != BG_STATUS_OK) {
        return BG_STATUS_INVALID_ARGUMENT;
    }
    if (candidates.reserved0 != 0 ||
        !reserved_is_zero(candidates.reserved) || output.reserved0 != 0 ||
        !reserved_is_zero(output.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "pose-validity batch or output reserved fields must be zero");
    }
    if (validity == nullptr ||
        candidates.candidate_count != kCandidateCount ||
        candidates.ligand_atom_count == 0 ||
        candidates.ligand_atom_count > kMaxLigandAtoms ||
        output.row_capacity < kCandidateCount || output.rows == nullptr ||
        !pointer_is_aligned(output.rows)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "pose-validity fixed64 denominator or output capacity is invalid");
    }
    const std::array<const void *, 9> channels = {
        candidates.candidate_state,
        candidates.upstream_scorer_failure_code,
        candidates.quaternion_x,
        candidates.quaternion_y,
        candidates.quaternion_z,
        candidates.quaternion_w,
        candidates.x_angstrom,
        candidates.y_angstrom,
        candidates.z_angstrom,
    };
    if (std::any_of(channels.begin(), channels.end(), [](const void *value) {
            return value == nullptr;
        }) ||
        !pointer_is_aligned(candidates.candidate_state) ||
        !pointer_is_aligned(candidates.upstream_scorer_failure_code) ||
        !pointer_is_aligned(candidates.quaternion_x) ||
        !pointer_is_aligned(candidates.quaternion_y) ||
        !pointer_is_aligned(candidates.quaternion_z) ||
        !pointer_is_aligned(candidates.quaternion_w) ||
        !pointer_is_aligned(candidates.x_angstrom) ||
        !pointer_is_aligned(candidates.y_angstrom) ||
        !pointer_is_aligned(candidates.z_angstrom)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "pose-validity candidate channel is null or misaligned");
    }
    for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
        const auto state = candidates.candidate_state[slot];
        const auto upstream =
            candidates.upstream_scorer_failure_code[slot];
        if ((state ==
                 BG_DOCKING_POSE_VALIDITY_CANDIDATE_UPSTREAM_FAILURE &&
             (upstream < BG_DOCKING_SCORER_V1_FAILURE_UPSTREAM_NOT_ADMITTED ||
              upstream > BG_DOCKING_SCORER_V1_FAILURE_NONFINITE_SCORE)) ||
            (state == BG_DOCKING_POSE_VALIDITY_CANDIDATE_EVALUATE &&
             upstream != BG_DOCKING_SCORER_V1_FAILURE_NONE) ||
            (state !=
                 BG_DOCKING_POSE_VALIDITY_CANDIDATE_UPSTREAM_FAILURE &&
             state != BG_DOCKING_POSE_VALIDITY_CANDIDATE_EVALUATE)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "pose-validity candidate state/failure binding is invalid");
        }
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status validate_context_header(
    const bg_docking_pose_validity_context_soa_v1 &descriptor) noexcept {
    bg_status status = validate_descriptor_header(
        descriptor.struct_size,
        sizeof(descriptor),
        descriptor.abi_version,
        "pose-validity context descriptor size does not match ABI v1",
        "pose-validity context descriptor ABI version does not match");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = validate_unit_system(descriptor.unit_system);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (descriptor.reserved0 != 0 ||
        !reserved_is_zero(descriptor.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "pose-validity context reserved fields must be zero");
    }
    return BG_STATUS_OK;
}

}  // namespace

void destroy_cpp_state(void *state) noexcept {
    delete static_cast<CppValidityContext *>(state);
}

}  // namespace betelgeuze::native::docking::validity

extern "C" BG_API bg_status BG_CALL
bg_docking_pose_validity_context_soa_v1_init(
    bg_docking_pose_validity_context_soa_v1 *descriptor,
    std::size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            descriptor,
            caller_struct_size,
            sizeof(*descriptor),
            caller_abi_version,
            "pose-validity context initializer pointer is null",
            "pose-validity context initializer size does not match",
            "pose-validity context initializer ABI version does not match");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *descriptor = bg_docking_pose_validity_context_soa_v1{};
        descriptor->struct_size =
            static_cast<uint32_t>(sizeof(*descriptor));
        descriptor->abi_version = BG_ABI_VERSION;
        descriptor->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        descriptor->bond_length_tolerance_angstrom = 0.15;
        descriptor->ligand_self_clash_angstrom = 0.75;
        descriptor->receptor_ligand_clash_angstrom = 0.8;
        descriptor->rotation_tolerance = 1.0e-6;
        descriptor->chirality_volume_tolerance = 1.0e-8;
        descriptor->severe_overlap_scale = 0.55;
        descriptor->contact_cell_size_angstrom = 3.5;
        descriptor->max_pair_checks = 250'000;
        descriptor->max_cross_checks = 1'000'000;
        descriptor->max_element_ligand_pair_checks = 250'000;
        descriptor->max_element_receptor_candidate_pairs = 1'000'000;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL
bg_docking_pose_validity_candidate_batch_soa_v1_init(
    bg_docking_pose_validity_candidate_batch_soa_v1 *batch,
    std::size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            batch,
            caller_struct_size,
            sizeof(*batch),
            caller_abi_version,
            "pose-validity batch initializer pointer is null",
            "pose-validity batch initializer size does not match",
            "pose-validity batch initializer ABI version does not match");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *batch = bg_docking_pose_validity_candidate_batch_soa_v1{};
        batch->struct_size = static_cast<uint32_t>(sizeof(*batch));
        batch->abi_version = BG_ABI_VERSION;
        batch->candidate_count = BG_DOCKING_FIXED64_CANDIDATE_COUNT;
        batch->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_docking_pose_validity_output_v1_init(
    bg_docking_pose_validity_output_v1 *output,
    std::size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            output,
            caller_struct_size,
            sizeof(*output),
            caller_abi_version,
            "pose-validity output initializer pointer is null",
            "pose-validity output initializer size does not match",
            "pose-validity output initializer ABI version does not match");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *output = bg_docking_pose_validity_output_v1{};
        output->struct_size = static_cast<uint32_t>(sizeof(*output));
        output->abi_version = BG_ABI_VERSION;
        output->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_docking_pose_validity_v1_create(
    const bg_context *context,
    const bg_docking_pose_validity_context_soa_v1 *descriptor,
    bg_docking_pose_validity_v1 **out_validity) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::docking::validity;
    if (out_validity != nullptr) {
        *out_validity = nullptr;
    }
    return guarded_status([&]() -> bg_status {
        if (context == nullptr || descriptor == nullptr ||
            out_validity == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "pose-validity create inputs and output must not be null");
        }
        bg_status status = validate_context_header(*descriptor);
        if (status != BG_STATUS_OK) {
            return status;
        }
        auto validity = std::make_unique<bg_docking_pose_validity_v1>();
        validity->backend = context->backend;
        validity->device_ordinal = context->device_ordinal;
        if (context->backend == BG_BACKEND_CPP_CPU_REFERENCE) {
            status = create_cpp_context(
                *descriptor, &validity->provider_state);
        } else if (context->backend == BG_BACKEND_RUST_CPU) {
            bg_rust_cpu_error_v1 error{};
            error.struct_size = sizeof(error);
            error.abi_version = BG_RUST_CPU_PROVIDER_ABI_VERSION;
            const int32_t raw_status =
                bg_rust_cpu_docking_pose_validity_v1_create(
                    descriptor, &validity->provider_state, &error);
            if (raw_status != BG_STATUS_OK) {
                return fail(
                    static_cast<bg_status>(raw_status),
                    error.message[0] == '\0'
                        ? "rust_cpu pose-validity create failed"
                        : error.message);
            }
            status = BG_STATUS_OK;
        } else if (context->backend == BG_BACKEND_HIP_SAFE) {
            return fail(
                BG_STATUS_BACKEND_UNAVAILABLE,
                "hip_safe pose-validity provider is not compiled; fallback is forbidden");
        } else if (context->backend == BG_BACKEND_HIP_FAST) {
            return fail(
                BG_STATUS_BACKEND_UNAVAILABLE,
                "hip_fast pose-validity provider is not compiled; fallback is forbidden");
        } else {
            return fail(
                BG_STATUS_UNSUPPORTED_BACKEND,
                "selected backend has no pose-validity implementation");
        }
        if (status != BG_STATUS_OK) {
            return status;
        }
        *out_validity = validity.release();
        return BG_STATUS_OK;
    });
}

extern "C" BG_API void BG_CALL bg_docking_pose_validity_v1_destroy(
    bg_docking_pose_validity_v1 *validity) BG_NOEXCEPT {
    if (validity == nullptr) {
        return;
    }
    if (validity->backend == BG_BACKEND_CPP_CPU_REFERENCE) {
        betelgeuze::native::docking::validity::destroy_cpp_state(
            validity->provider_state);
    } else if (validity->backend == BG_BACKEND_RUST_CPU) {
        bg_rust_cpu_docking_pose_validity_v1_destroy(
            validity->provider_state);
    }
    delete validity;
}

extern "C" BG_API bg_status BG_CALL
bg_docking_pose_validity_v1_get_backend(
    const bg_docking_pose_validity_v1 *validity,
    bg_backend *backend) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        if (validity == nullptr || backend == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "pose-validity handle and backend output must not be null");
        }
        *backend = validity->backend;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL
bg_docking_pose_validity_v1_evaluate_fixed64(
    const bg_context *context,
    const bg_docking_pose_validity_v1 *validity,
    const bg_docking_pose_validity_candidate_batch_soa_v1 *candidates,
    bg_docking_pose_validity_output_v1 *out_rows) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::docking::validity;
    return guarded_status([&]() -> bg_status {
        if (context == nullptr || validity == nullptr ||
            candidates == nullptr || out_rows == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "pose-validity evaluation inputs and output must not be null");
        }
        if (context->backend != validity->backend ||
            context->device_ordinal != validity->device_ordinal) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "pose-validity handle is cross-wired to another backend or device");
        }
        bg_status status =
            validate_batch_and_output(validity, *candidates, *out_rows);
        if (status != BG_STATUS_OK) {
            return status;
        }
        std::array<bg_docking_pose_validity_row_v1, kCandidateCount>
            candidate_rows{};
        if (validity->backend == BG_BACKEND_CPP_CPU_REFERENCE) {
            const auto *state = static_cast<const CppValidityContext *>(
                validity->provider_state);
            if (state == nullptr ||
                candidates->ligand_atom_count !=
                    state->reference_coordinates.size()) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "pose-validity candidate ligand denominator is cross-wired");
            }
            status = evaluate_cpp_fixed64(
                *state, *candidates, &candidate_rows);
        } else if (validity->backend == BG_BACKEND_RUST_CPU) {
            bg_rust_cpu_error_v1 error{};
            error.struct_size = sizeof(error);
            error.abi_version = BG_RUST_CPU_PROVIDER_ABI_VERSION;
            const int32_t raw_status =
                bg_rust_cpu_docking_pose_validity_v1_evaluate_fixed64(
                    validity->provider_state,
                    candidates,
                    candidate_rows.data(),
                    &error);
            if (raw_status != BG_STATUS_OK) {
                return fail(
                    static_cast<bg_status>(raw_status),
                    error.message[0] == '\0'
                        ? "rust_cpu pose-validity batch failed"
                        : error.message);
            }
            status = BG_STATUS_OK;
        } else {
            return fail(
                BG_STATUS_BACKEND_UNAVAILABLE,
                "selected backend has no qualified pose-validity kernel; fallback is forbidden");
        }
        if (status != BG_STATUS_OK) {
            return status;
        }
        std::memcpy(
            out_rows->rows,
            candidate_rows.data(),
            sizeof(candidate_rows));
        out_rows->row_count = kCandidateCount;
        return BG_STATUS_OK;
    });
}
