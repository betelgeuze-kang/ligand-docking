#include "../internal.hpp"
#include "../hip/provider.h"
#include "../rust/provider.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstring>
#include <memory>
#include <tuple>

#ifndef BG_HAS_HIP_SAFE_PROVIDER
#  define BG_HAS_HIP_SAFE_PROVIDER 0
#endif
#ifndef BG_ENABLE_HIP
#  define BG_ENABLE_HIP 0
#endif

namespace betelgeuze::native::docking::rigid_refinement {
namespace {

constexpr std::size_t kCandidateCount =
    BG_DOCKING_FIXED64_CANDIDATE_COUNT;
constexpr std::size_t kMaxLigandAtoms = 512;
constexpr std::size_t kMaxReceptorAtoms = 65'536;
constexpr std::size_t kMaxPairEvaluations = 250'000'000;
constexpr std::size_t kMaxSteps = 128;
constexpr double kPi = 3.141592653589793238462643383279502884;
constexpr double kV6NearClearPenalty = 0.000244140625;

struct Vec3 {
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
};

struct Quaternion {
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
    double w = 1.0;
};

struct V2Config {
    double overlap_scale = 0.75;
    double maximum_step_angstrom = 0.30;
    double minimum_step_angstrom = 0.009375;
    double maximum_total_translation_angstrom = 2.25;
    std::size_t maximum_backtracking_evaluations = 6;
    double penalty_tolerance = 1.0e-18;
    double epsilon_angstrom = 1.0e-9;
};

struct V3Config {
    V2Config v2;
    double maximum_rotation_step_radians = kPi / 36.0;
    double minimum_rotation_step_radians = kPi / 1152.0;
    double maximum_total_rotation_radians = kPi / 18.0;
    std::size_t maximum_rotation_steps = 2;
    double minimum_rotation_relative_penalty_reduction = 0.01;
    double maximum_centroid_offset_angstrom = 4.0;
};

struct ProviderEnvelope {
    std::vector<Vec3> receptor;
    std::vector<double> receptor_radii;
    std::vector<double> ligand_radii;
    Vec3 pocket_center;
    double pocket_radius = 0.0;
    V2Config v2;
    V3Config v3;
    V3Config clearance_v4;
    void *backend_state = nullptr;
};

struct Outcome {
    bg_docking_rigid_refinement_profile profile =
        BG_DOCKING_RIGID_REFINEMENT_PROFILE_NONE;
    std::vector<Vec3> coordinates;
    double initial_penalty = 0.0;
    double final_penalty = 0.0;
    std::size_t accepted_steps = 0;
    std::size_t accepted_translation_steps = 0;
    std::size_t accepted_rotation_steps = 0;
    std::size_t line_search_evaluation_count = 0;
    std::size_t fallback_direction_step_count = 0;
    Vec3 total_translation;
    Vec3 total_rotation_vector;
    double total_rotation_path = 0.0;
    double initial_centroid_offset = 0.0;
    double final_centroid_offset = 0.0;
    double maximum_centroid_offset = 0.0;
};

struct V6Outcome {
    Outcome selected;
    Outcome comparison_v2;
    Outcome baseline_v3;
    Outcome clearance_v4;
    bool comparison_v2_available = false;
    bool baseline_v3_available = false;
    bool clearance_v4_available = false;
    bool baseline_duplicate_of_v2 = false;
    bool clearance_evaluated = false;
    bool clearance_selected = false;
};

struct TranslationTrial {
    double penalty = 0.0;
    std::size_t direction_index = 0;
    std::size_t backtracking_index = 0;
    std::vector<Vec3> coordinates;
    Vec3 total_shift;
};

struct RigidTrial {
    double penalty = 0.0;
    std::size_t direction_index = 0;
    std::size_t backtracking_index = 0;
    std::vector<Vec3> coordinates;
    Vec3 total_shift;
    Quaternion total_rotation;
    double total_rotation_path = 0.0;
};

struct LocalFailure {
    bg_docking_rigid_refinement_failure code;
};

struct BatchResult {
    std::array<bg_docking_rigid_refinement_row_v1, kCandidateCount> rows{};
    std::vector<double> selected_x;
    std::vector<double> selected_y;
    std::vector<double> selected_z;
    std::vector<double> comparison_v2_x;
    std::vector<double> comparison_v2_y;
    std::vector<double> comparison_v2_z;
    std::vector<double> baseline_v3_x;
    std::vector<double> baseline_v3_y;
    std::vector<double> baseline_v3_z;
    std::vector<double> clearance_v4_x;
    std::vector<double> clearance_v4_y;
    std::vector<double> clearance_v4_z;
};

[[nodiscard]] double canonical_zero(double value) noexcept {
    return value == 0.0 ? 0.0 : value;
}

[[nodiscard]] Vec3 canonical(Vec3 value) noexcept {
    return {
        canonical_zero(value.x),
        canonical_zero(value.y),
        canonical_zero(value.z),
    };
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
    return std::sqrt(dot(value, value));
}

[[nodiscard]] bool finite(Vec3 value) noexcept {
    return std::isfinite(value.x) && std::isfinite(value.y) &&
           std::isfinite(value.z);
}

[[nodiscard]] Quaternion normalized(Quaternion value) {
    const double magnitude = std::sqrt(
        value.x * value.x + value.y * value.y + value.z * value.z +
        value.w * value.w);
    if (!std::isfinite(magnitude) || magnitude <= 1.0e-18) {
        throw LocalFailure{
            BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONFINITE_DERIVED_VALUE};
    }
    const double inverse = 1.0 / magnitude;
    value = {
        value.x * inverse,
        value.y * inverse,
        value.z * inverse,
        value.w * inverse,
    };
    if (value.w < 0.0) {
        value = {-value.x, -value.y, -value.z, -value.w};
    }
    value.x = canonical_zero(value.x);
    value.y = canonical_zero(value.y);
    value.z = canonical_zero(value.z);
    value.w = canonical_zero(value.w);
    return value;
}

[[nodiscard]] Quaternion compose_rotation(
    Vec3 rotation_step,
    Quaternion current) {
    const double angle = norm(rotation_step);
    if (!std::isfinite(angle)) {
        throw LocalFailure{
            BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONFINITE_DERIVED_VALUE};
    }
    if (angle <= 1.0e-18) {
        return normalized(current);
    }
    const double half_angle = 0.5 * angle;
    const double scale_factor = std::sin(half_angle) / angle;
    const Quaternion step{
        rotation_step.x * scale_factor,
        rotation_step.y * scale_factor,
        rotation_step.z * scale_factor,
        std::cos(half_angle),
    };
    return normalized({
        step.w * current.x + step.x * current.w +
            step.y * current.z - step.z * current.y,
        step.w * current.y - step.x * current.z +
            step.y * current.w + step.z * current.x,
        step.w * current.z + step.x * current.y -
            step.y * current.x + step.z * current.w,
        step.w * current.w - step.x * current.x -
            step.y * current.y - step.z * current.z,
    });
}

[[nodiscard]] Vec3 rotation_vector(Quaternion value) {
    value = normalized(value);
    const double sine_half = std::sqrt(
        value.x * value.x + value.y * value.y + value.z * value.z);
    if (sine_half <= 1.0e-18) {
        return {};
    }
    const double angle = 2.0 * std::atan2(sine_half, value.w);
    if (!std::isfinite(angle)) {
        throw LocalFailure{
            BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONFINITE_DERIVED_VALUE};
    }
    return canonical({
        value.x * angle / sine_half,
        value.y * angle / sine_half,
        value.z * angle / sine_half,
    });
}

[[nodiscard]] bool checked_multiply(
    std::size_t left,
    std::size_t right,
    std::size_t *output) noexcept {
    if (output == nullptr ||
        (right != 0 &&
         left > std::numeric_limits<std::size_t>::max() / right)) {
        return false;
    }
    *output = left * right;
    return true;
}

[[nodiscard]] bool checked_add(
    std::size_t left,
    std::size_t right,
    std::size_t *output) noexcept {
    if (output == nullptr ||
        left > std::numeric_limits<std::size_t>::max() - right) {
        return false;
    }
    *output = left + right;
    return true;
}

template <typename Type>
[[nodiscard]] bg_status require_channel(
    const Type *pointer,
    std::size_t count,
    const char *message) noexcept {
    if (count != 0 && (pointer == nullptr || !pointer_is_aligned(pointer))) {
        return fail(BG_STATUS_INVALID_ARGUMENT, message);
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bool ranges_overlap(
    const void *left,
    std::size_t left_size,
    const void *right,
    std::size_t right_size) noexcept {
    if (left == nullptr || right == nullptr || left_size == 0 || right_size == 0) {
        return false;
    }
    const auto left_start = reinterpret_cast<std::uintptr_t>(left);
    const auto right_start = reinterpret_cast<std::uintptr_t>(right);
    if (left_start > std::numeric_limits<std::uintptr_t>::max() - left_size ||
        right_start > std::numeric_limits<std::uintptr_t>::max() - right_size) {
        return true;
    }
    return left_start < right_start + right_size &&
           right_start < left_start + left_size;
}

[[nodiscard]] bg_status public_count(
    uint64_t value,
    const char *message,
    std::size_t *output) noexcept {
    return checked_element_count(value, 1, message, output);
}

[[nodiscard]] bool finite_positive(double value) noexcept {
    return std::isfinite(value) && value > 0.0;
}

[[nodiscard]] bg_status convert_v2(
    const bg_docking_rigid_v2_config_v1 &source,
    V2Config *output) noexcept {
    if (output == nullptr) {
        return fail(BG_STATUS_INTERNAL_ERROR, "rigid V2 output is null");
    }
    if (!reserved_is_zero(source.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "rigid V2 configuration reserved fields must be zero");
    }
    std::size_t backtracking = 0;
    bg_status status = public_count(
        source.maximum_backtracking_evaluations,
        "rigid V2 backtracking count overflows",
        &backtracking);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (!finite_positive(source.overlap_scale) ||
        !finite_positive(source.maximum_step_angstrom) ||
        !finite_positive(source.minimum_step_angstrom) ||
        !finite_positive(source.maximum_total_translation_angstrom) ||
        !finite_positive(source.penalty_tolerance) ||
        !finite_positive(source.epsilon_angstrom) ||
        source.overlap_scale < 0.55 || source.overlap_scale > 1.0 ||
        source.minimum_step_angstrom > source.maximum_step_angstrom ||
        source.maximum_step_angstrom >
            source.maximum_total_translation_angstrom ||
        backtracking < 1 || backtracking > 16) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "rigid V2 configuration is non-finite or outside frozen bounds");
    }
    *output = {
        source.overlap_scale,
        source.maximum_step_angstrom,
        source.minimum_step_angstrom,
        source.maximum_total_translation_angstrom,
        backtracking,
        source.penalty_tolerance,
        source.epsilon_angstrom,
    };
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status convert_v3(
    const bg_docking_rigid_v3_config_v1 &source,
    V3Config *output) noexcept {
    if (output == nullptr) {
        return fail(BG_STATUS_INTERNAL_ERROR, "rigid V3 output is null");
    }
    if (!reserved_is_zero(source.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "rigid V3 configuration reserved fields must be zero");
    }
    V2Config v2;
    bg_status status = convert_v2(source.v2, &v2);
    if (status != BG_STATUS_OK) {
        return status;
    }
    std::size_t rotation_steps = 0;
    status = public_count(
        source.maximum_rotation_steps,
        "rigid V3 rotation step count overflows",
        &rotation_steps);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (!finite_positive(source.maximum_rotation_step_radians) ||
        !finite_positive(source.minimum_rotation_step_radians) ||
        !finite_positive(source.maximum_total_rotation_radians) ||
        !finite_positive(source.minimum_rotation_relative_penalty_reduction) ||
        !finite_positive(source.maximum_centroid_offset_angstrom) ||
        source.minimum_rotation_step_radians >
            source.maximum_rotation_step_radians ||
        source.maximum_rotation_step_radians >
            source.maximum_total_rotation_radians ||
        rotation_steps < 1 || rotation_steps > 8 ||
        source.minimum_rotation_relative_penalty_reduction > 0.25 ||
        source.maximum_centroid_offset_angstrom < 0.5 ||
        source.maximum_centroid_offset_angstrom > 8.0) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "rigid V3 configuration is non-finite or outside frozen bounds");
    }
    *output = {
        v2,
        source.maximum_rotation_step_radians,
        source.minimum_rotation_step_radians,
        source.maximum_total_rotation_radians,
        rotation_steps,
        source.minimum_rotation_relative_penalty_reduction,
        source.maximum_centroid_offset_angstrom,
    };
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status build_envelope(
    const bg_docking_rigid_refinement_context_soa_v1 &descriptor,
    std::unique_ptr<ProviderEnvelope> *output) {
    bg_status status = validate_descriptor_header(
        descriptor.struct_size,
        sizeof(descriptor),
        descriptor.abi_version,
        "rigid refinement context size does not match ABI v1",
        "rigid refinement context ABI version does not match");
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (output == nullptr) {
        return fail(BG_STATUS_INTERNAL_ERROR, "rigid refinement output is null");
    }
    status = validate_unit_system(descriptor.unit_system);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (descriptor.reserved0 != 0 || !reserved_is_zero(descriptor.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "rigid refinement context reserved fields must be zero");
    }
    std::size_t receptor_count = 0;
    std::size_t ligand_count = 0;
    status = public_count(
        descriptor.receptor_atom_count,
        "rigid refinement receptor count overflows",
        &receptor_count);
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = public_count(
        descriptor.ligand_atom_count,
        "rigid refinement ligand count overflows",
        &ligand_count);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (receptor_count == 0 || receptor_count > kMaxReceptorAtoms ||
        ligand_count == 0 || ligand_count > kMaxLigandAtoms) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "rigid refinement atom denominator is outside native bounds");
    }
    std::size_t pair_count = 0;
    if (!checked_multiply(receptor_count, ligand_count, &pair_count) ||
        pair_count > kMaxPairEvaluations) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "rigid refinement receptor-ligand pair budget exceeded");
    }
#define BG_REQUIRE_RIGID_CHANNEL(pointer, count, message)                    \
    do {                                                                     \
        status = require_channel((pointer), (count), (message));             \
        if (status != BG_STATUS_OK) {                                        \
            return status;                                                   \
        }                                                                    \
    } while (false)
    BG_REQUIRE_RIGID_CHANNEL(
        descriptor.receptor_x_angstrom,
        receptor_count,
        "rigid refinement receptor x is null or misaligned");
    BG_REQUIRE_RIGID_CHANNEL(
        descriptor.receptor_y_angstrom,
        receptor_count,
        "rigid refinement receptor y is null or misaligned");
    BG_REQUIRE_RIGID_CHANNEL(
        descriptor.receptor_z_angstrom,
        receptor_count,
        "rigid refinement receptor z is null or misaligned");
    BG_REQUIRE_RIGID_CHANNEL(
        descriptor.receptor_vdw_radius_angstrom,
        receptor_count,
        "rigid refinement receptor radii are null or misaligned");
    BG_REQUIRE_RIGID_CHANNEL(
        descriptor.ligand_vdw_radius_angstrom,
        ligand_count,
        "rigid refinement ligand radii are null or misaligned");
#undef BG_REQUIRE_RIGID_CHANNEL

    auto state = std::make_unique<ProviderEnvelope>();
    state->receptor.reserve(receptor_count);
    for (std::size_t index = 0; index < receptor_count; ++index) {
        state->receptor.push_back({
            descriptor.receptor_x_angstrom[index],
            descriptor.receptor_y_angstrom[index],
            descriptor.receptor_z_angstrom[index],
        });
    }
    state->receptor_radii.assign(
        descriptor.receptor_vdw_radius_angstrom,
        descriptor.receptor_vdw_radius_angstrom + receptor_count);
    state->ligand_radii.assign(
        descriptor.ligand_vdw_radius_angstrom,
        descriptor.ligand_vdw_radius_angstrom + ligand_count);
    state->pocket_center = {
        descriptor.pocket_center_angstrom[0],
        descriptor.pocket_center_angstrom[1],
        descriptor.pocket_center_angstrom[2],
    };
    state->pocket_radius = descriptor.pocket_radius_angstrom;
    if (std::any_of(
            state->receptor.begin(),
            state->receptor.end(),
            [](Vec3 value) { return !finite(value); }) ||
        !all_positive_finite(state->receptor_radii) ||
        !all_positive_finite(state->ligand_radii) ||
        !finite(state->pocket_center) || !finite_positive(state->pocket_radius)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "rigid refinement context contains non-finite values");
    }
    status = convert_v2(descriptor.v2, &state->v2);
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = convert_v3(descriptor.v3, &state->v3);
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = convert_v3(descriptor.clearance_v4, &state->clearance_v4);
    if (status != BG_STATUS_OK) {
        return status;
    }
    *output = std::move(state);
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status validate_create_output_range(
    const bg_context &context,
    const bg_docking_rigid_refinement_context_soa_v1 &descriptor,
    const ProviderEnvelope &state,
    bg_docking_rigid_refinement **out_refiner) noexcept {
    const std::size_t receptor_count = state.receptor.size();
    const std::size_t ligand_count = state.ligand_radii.size();
    const std::array<std::pair<const void *, std::size_t>, 7> inputs = {{
        {&context, sizeof(context)},
        {&descriptor, sizeof(descriptor)},
        {descriptor.receptor_x_angstrom,
         receptor_count * sizeof(*descriptor.receptor_x_angstrom)},
        {descriptor.receptor_y_angstrom,
         receptor_count * sizeof(*descriptor.receptor_y_angstrom)},
        {descriptor.receptor_z_angstrom,
         receptor_count * sizeof(*descriptor.receptor_z_angstrom)},
        {descriptor.receptor_vdw_radius_angstrom,
         receptor_count * sizeof(*descriptor.receptor_vdw_radius_angstrom)},
        {descriptor.ligand_vdw_radius_angstrom,
         ligand_count * sizeof(*descriptor.ligand_vdw_radius_angstrom)},
    }};
    for (const auto &input : inputs) {
        if (ranges_overlap(
                out_refiner,
                sizeof(*out_refiner),
                input.first,
                input.second)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "rigid refinement handle output overlaps a create input");
        }
    }
    return BG_STATUS_OK;
}

[[nodiscard]] std::pair<double, Vec3> penalty_and_direction(
    const ProviderEnvelope &state,
    const std::vector<Vec3> &coordinates,
    const V2Config &config) {
    double penalty = 0.0;
    Vec3 direction;
    for (std::size_t ligand = 0; ligand < coordinates.size(); ++ligand) {
        for (std::size_t receptor = 0; receptor < state.receptor.size();
             ++receptor) {
            const Vec3 delta = minus(coordinates[ligand], state.receptor[receptor]);
            const double distance =
                std::max(norm(delta), config.epsilon_angstrom);
            const double cutoff = config.overlap_scale *
                                  (state.ligand_radii[ligand] +
                                   state.receptor_radii[receptor]);
            const double penetration = std::max(cutoff - distance, 0.0);
            const double squared = penetration * penetration;
            penalty += squared * squared;
            direction = plus(
                direction,
                scale(delta, squared * penetration / distance));
        }
    }
    if (!std::isfinite(penalty) || !finite(direction)) {
        throw LocalFailure{
            BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONFINITE_DERIVED_VALUE};
    }
    return {canonical_zero(penalty), canonical(direction)};
}

[[nodiscard]] Vec3 maximum_penetration_direction(
    const ProviderEnvelope &state,
    const std::vector<Vec3> &coordinates,
    const V2Config &config) {
    double best_penetration = -1.0;
    std::size_t best_ligand = 0;
    std::size_t best_receptor = 0;
    Vec3 best_delta;
    double best_distance = config.epsilon_angstrom;
    for (std::size_t ligand = 0; ligand < coordinates.size(); ++ligand) {
        for (std::size_t receptor = 0; receptor < state.receptor.size();
             ++receptor) {
            const Vec3 delta = minus(coordinates[ligand], state.receptor[receptor]);
            const double distance =
                std::max(norm(delta), config.epsilon_angstrom);
            const double cutoff = config.overlap_scale *
                                  (state.ligand_radii[ligand] +
                                   state.receptor_radii[receptor]);
            const double penetration = std::max(cutoff - distance, 0.0);
            if (penetration > best_penetration ||
                (penetration == best_penetration &&
                 std::tie(ligand, receptor) <
                     std::tie(best_ligand, best_receptor))) {
                best_penetration = penetration;
                best_ligand = ligand;
                best_receptor = receptor;
                best_delta = delta;
                best_distance = distance;
            }
        }
    }
    if (best_penetration <= 0.0) {
        return {};
    }
    if (norm(best_delta) > config.epsilon_angstrom) {
        return canonical(scale(best_delta, 1.0 / best_distance));
    }
    const std::size_t signed_axis = (best_ligand * 131 + best_receptor) % 6;
    const double sign = signed_axis % 2 == 0 ? 1.0 : -1.0;
    if (signed_axis / 2 == 0) {
        return {sign, 0.0, 0.0};
    }
    if (signed_axis / 2 == 1) {
        return {0.0, sign, 0.0};
    }
    return {0.0, 0.0, sign};
}

[[nodiscard]] bool vector_close(Vec3 left, Vec3 right, double tolerance) noexcept {
    return std::abs(left.x - right.x) <= tolerance &&
           std::abs(left.y - right.y) <= tolerance &&
           std::abs(left.z - right.z) <= tolerance;
}

[[nodiscard]] std::vector<Vec3> candidate_directions(
    const ProviderEnvelope &state,
    const std::vector<Vec3> &coordinates,
    Vec3 aggregate,
    const V2Config &config) {
    std::vector<Vec3> result;
    result.reserve(2);
    const double aggregate_norm = norm(aggregate);
    if (aggregate_norm > config.epsilon_angstrom) {
        result.push_back(canonical(scale(aggregate, 1.0 / aggregate_norm)));
    }
    const Vec3 fallback =
        maximum_penetration_direction(state, coordinates, config);
    const double fallback_norm = norm(fallback);
    if (fallback_norm > config.epsilon_angstrom) {
        const Vec3 normalized =
            canonical(scale(fallback, 1.0 / fallback_norm));
        if (result.empty() || !vector_close(result.front(), normalized, 1.0e-12)) {
            result.push_back(normalized);
        }
    }
    return result;
}

[[nodiscard]] Vec3 centroid(const std::vector<Vec3> &coordinates) noexcept {
    Vec3 total;
    for (const Vec3 coordinate : coordinates) {
        total = plus(total, coordinate);
    }
    return canonical(scale(total, 1.0 / static_cast<double>(coordinates.size())));
}

[[nodiscard]] std::vector<Vec3> translated(
    const std::vector<Vec3> &coordinates,
    Vec3 step) {
    std::vector<Vec3> result;
    result.reserve(coordinates.size());
    for (const Vec3 coordinate : coordinates) {
        result.push_back(canonical(plus(coordinate, step)));
    }
    return result;
}

[[nodiscard]] Vec3 rotation_torque(
    const ProviderEnvelope &state,
    const std::vector<Vec3> &coordinates,
    const V2Config &config) {
    const Vec3 center = centroid(coordinates);
    Vec3 torque;
    for (std::size_t ligand = 0; ligand < coordinates.size(); ++ligand) {
        const Vec3 lever = minus(coordinates[ligand], center);
        for (std::size_t receptor = 0; receptor < state.receptor.size();
             ++receptor) {
            const Vec3 delta = minus(coordinates[ligand], state.receptor[receptor]);
            const double distance =
                std::max(norm(delta), config.epsilon_angstrom);
            const double cutoff = config.overlap_scale *
                                  (state.ligand_radii[ligand] +
                                   state.receptor_radii[receptor]);
            const double penetration = std::max(cutoff - distance, 0.0);
            const Vec3 force = scale(
                delta,
                penetration * penetration * penetration / distance);
            torque = plus(torque, cross(lever, force));
        }
    }
    if (!finite(torque)) {
        throw LocalFailure{
            BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONFINITE_DERIVED_VALUE};
    }
    return canonical(torque);
}

[[nodiscard]] std::vector<Vec3> rotate_about_centroid(
    const std::vector<Vec3> &coordinates,
    Vec3 rotation_vector) {
    const double angle = norm(rotation_vector);
    if (!std::isfinite(angle)) {
        throw LocalFailure{
            BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONFINITE_DERIVED_VALUE};
    }
    if (angle <= 1.0e-18) {
        return coordinates;
    }
    const Vec3 axis = scale(rotation_vector, 1.0 / angle);
    const Vec3 center = centroid(coordinates);
    const double cosine = std::cos(angle);
    const double sine = std::sin(angle);
    std::vector<Vec3> result;
    result.reserve(coordinates.size());
    for (const Vec3 coordinate : coordinates) {
        const Vec3 centered = minus(coordinate, center);
        const Vec3 rotated = plus(
            plus(
                plus(
                    scale(centered, cosine),
                    scale(cross(axis, centered), sine)),
                scale(axis, dot(axis, centered) * (1.0 - cosine))),
            center);
        if (!finite(rotated)) {
            throw LocalFailure{
                BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONFINITE_DERIVED_VALUE};
        }
        result.push_back(canonical(rotated));
    }
    return result;
}

[[nodiscard]] bool translation_less(
    const TranslationTrial &left,
    const TranslationTrial &right) noexcept {
    return std::tie(
               left.penalty,
               left.direction_index,
               left.backtracking_index) <
           std::tie(
               right.penalty,
               right.direction_index,
               right.backtracking_index);
}

[[nodiscard]] bool rigid_less(
    const RigidTrial &left,
    const RigidTrial &right) noexcept {
    return std::tie(
               left.penalty,
               left.direction_index,
               left.backtracking_index) <
           std::tie(
               right.penalty,
               right.direction_index,
               right.backtracking_index);
}

[[nodiscard]] Outcome refine_v2(
    const ProviderEnvelope &state,
    const std::vector<Vec3> &source,
    std::size_t max_steps,
    const V2Config &config) {
    std::vector<Vec3> coordinates = source;
    const double initial_penalty =
        penalty_and_direction(state, coordinates, config).first;
    Vec3 total_shift;
    std::size_t accepted_steps = 0;
    std::size_t evaluations = 0;
    std::size_t fallback_steps = 0;
    for (std::size_t iteration = 0; iteration < max_steps; ++iteration) {
        const auto [penalty, aggregate] =
            penalty_and_direction(state, coordinates, config);
        if (penalty <= config.penalty_tolerance) {
            break;
        }
        const double remaining =
            config.maximum_total_translation_angstrom - norm(total_shift);
        if (remaining <= config.minimum_step_angstrom) {
            break;
        }
        const auto directions =
            candidate_directions(state, coordinates, aggregate, config);
        if (directions.empty()) {
            break;
        }
        const double base_step =
            std::min(config.maximum_step_angstrom, remaining);
        bool has_best = false;
        TranslationTrial best;
        for (std::size_t direction_index = 0;
             direction_index < directions.size();
             ++direction_index) {
            double step_size = base_step;
            for (std::size_t backtracking = 0;
                 backtracking < config.maximum_backtracking_evaluations;
                 ++backtracking) {
                if (step_size < config.minimum_step_angstrom) {
                    break;
                }
                const Vec3 step = scale(directions[direction_index], step_size);
                const Vec3 trial_shift = plus(total_shift, step);
                if (norm(trial_shift) >
                    config.maximum_total_translation_angstrom +
                        config.epsilon_angstrom) {
                    step_size *= 0.5;
                    continue;
                }
                auto trial_coordinates = translated(coordinates, step);
                const double trial_penalty =
                    penalty_and_direction(state, trial_coordinates, config).first;
                ++evaluations;
                TranslationTrial trial{
                    trial_penalty,
                    direction_index,
                    backtracking,
                    std::move(trial_coordinates),
                    trial_shift,
                };
                if (!has_best || translation_less(trial, best)) {
                    best = std::move(trial);
                    has_best = true;
                }
                step_size *= 0.5;
            }
        }
        const double reduction =
            std::max(config.penalty_tolerance, std::abs(penalty) * 1.0e-12);
        if (!has_best || best.penalty > penalty - reduction) {
            break;
        }
        coordinates = std::move(best.coordinates);
        total_shift = best.total_shift;
        ++accepted_steps;
        fallback_steps += static_cast<std::size_t>(best.direction_index > 0);
    }
    const double final_penalty =
        penalty_and_direction(state, coordinates, config).first;
    return {
        BG_DOCKING_RIGID_REFINEMENT_PROFILE_V2_TRANSLATION,
        std::move(coordinates),
        initial_penalty,
        final_penalty,
        accepted_steps,
        accepted_steps,
        0,
        evaluations,
        fallback_steps,
        canonical(total_shift),
        {},
        0.0,
        0.0,
        0.0,
        0.0,
    };
}

[[nodiscard]] Outcome refine_v3(
    const ProviderEnvelope &state,
    const std::vector<Vec3> &source,
    std::size_t max_steps,
    const V3Config &config) {
    std::vector<Vec3> coordinates = source;
    const double initial_penalty =
        penalty_and_direction(state, coordinates, config.v2).first;
    const double initial_centroid_offset =
        norm(minus(centroid(coordinates), state.pocket_center));
    const double maximum_centroid_offset =
        std::min(config.maximum_centroid_offset_angstrom, state.pocket_radius);
    Vec3 total_shift;
    Quaternion total_rotation;
    double total_rotation_path = 0.0;
    std::size_t accepted_steps = 0;
    std::size_t accepted_rotation_steps = 0;
    std::size_t evaluations = 0;
    std::size_t fallback_steps = 0;
    for (std::size_t iteration = 0; iteration < max_steps; ++iteration) {
        const auto [penalty, aggregate] =
            penalty_and_direction(state, coordinates, config.v2);
        if (penalty <= config.v2.penalty_tolerance) {
            break;
        }
        const double remaining_translation =
            config.v2.maximum_total_translation_angstrom - norm(total_shift);
        const double remaining_rotation =
            config.maximum_total_rotation_radians - total_rotation_path;
        if (remaining_translation <= config.v2.minimum_step_angstrom &&
            remaining_rotation <= config.minimum_rotation_step_radians) {
            break;
        }
        const auto directions =
            candidate_directions(state, coordinates, aggregate, config.v2);
        bool has_best = false;
        RigidTrial best;
        if (remaining_translation > config.v2.minimum_step_angstrom) {
            const double base_step =
                std::min(config.v2.maximum_step_angstrom, remaining_translation);
            for (std::size_t direction_index = 0;
                 direction_index < directions.size();
                 ++direction_index) {
                double step_size = base_step;
                for (std::size_t backtracking = 0;
                     backtracking <
                     config.v2.maximum_backtracking_evaluations;
                     ++backtracking) {
                    if (step_size < config.v2.minimum_step_angstrom) {
                        break;
                    }
                    const Vec3 step =
                        scale(directions[direction_index], step_size);
                    const Vec3 trial_shift = plus(total_shift, step);
                    if (norm(trial_shift) >
                        config.v2.maximum_total_translation_angstrom +
                            config.v2.epsilon_angstrom) {
                        step_size *= 0.5;
                        continue;
                    }
                    auto trial_coordinates = translated(coordinates, step);
                    const double trial_centroid_offset = norm(minus(
                        centroid(trial_coordinates), state.pocket_center));
                    if (trial_centroid_offset >
                        maximum_centroid_offset + config.v2.epsilon_angstrom) {
                        step_size *= 0.5;
                        continue;
                    }
                    const double trial_penalty = penalty_and_direction(
                                                     state,
                                                     trial_coordinates,
                                                     config.v2)
                                                     .first;
                    ++evaluations;
                    RigidTrial trial{
                        trial_penalty,
                        direction_index,
                        backtracking,
                        std::move(trial_coordinates),
                        trial_shift,
                        total_rotation,
                        total_rotation_path,
                    };
                    if (!has_best || rigid_less(trial, best)) {
                        best = std::move(trial);
                        has_best = true;
                    }
                    step_size *= 0.5;
                }
            }
        }
        const double reduction = std::max(
            config.v2.penalty_tolerance,
            std::abs(penalty) * 1.0e-12);
        const bool translation_improves =
            has_best && best.penalty <= penalty - reduction;
        const Vec3 torque = rotation_torque(state, coordinates, config.v2);
        const double torque_norm = norm(torque);
        if (!translation_improves &&
            torque_norm > config.v2.epsilon_angstrom &&
            remaining_rotation > config.minimum_rotation_step_radians &&
            accepted_rotation_steps < config.maximum_rotation_steps) {
            const Vec3 axis = scale(torque, 1.0 / torque_norm);
            const double rotation_reduction = std::max(
                reduction,
                std::abs(penalty) *
                    config.minimum_rotation_relative_penalty_reduction);
            double angle = std::min(
                config.maximum_rotation_step_radians,
                remaining_rotation);
            for (std::size_t backtracking = 0;
                 backtracking < config.v2.maximum_backtracking_evaluations;
                 ++backtracking) {
                if (angle < config.minimum_rotation_step_radians) {
                    break;
                }
                const Vec3 rotation_step = scale(axis, angle);
                auto trial_coordinates =
                    rotate_about_centroid(coordinates, rotation_step);
                const double trial_penalty = penalty_and_direction(
                                                 state,
                                                 trial_coordinates,
                                                 config.v2)
                                                 .first;
                ++evaluations;
                RigidTrial trial{
                    trial_penalty,
                    2,
                    backtracking,
                    std::move(trial_coordinates),
                    total_shift,
                    compose_rotation(rotation_step, total_rotation),
                    total_rotation_path + angle,
                };
                if (trial_penalty <= penalty - rotation_reduction &&
                    (!has_best || rigid_less(trial, best))) {
                    best = std::move(trial);
                    has_best = true;
                }
                angle *= 0.5;
            }
        }
        if (!has_best || best.penalty > penalty - reduction) {
            break;
        }
        coordinates = std::move(best.coordinates);
        total_shift = best.total_shift;
        total_rotation = best.total_rotation;
        total_rotation_path = best.total_rotation_path;
        ++accepted_steps;
        accepted_rotation_steps +=
            static_cast<std::size_t>(best.direction_index == 2);
        fallback_steps +=
            static_cast<std::size_t>(best.direction_index == 1);
    }
    const double final_penalty =
        penalty_and_direction(state, coordinates, config.v2).first;
    const double final_centroid_offset =
        norm(minus(centroid(coordinates), state.pocket_center));
    return {
        BG_DOCKING_RIGID_REFINEMENT_PROFILE_V3_TRANSLATION_ROTATION,
        std::move(coordinates),
        initial_penalty,
        final_penalty,
        accepted_steps,
        accepted_steps - accepted_rotation_steps,
        accepted_rotation_steps,
        evaluations,
        fallback_steps,
        canonical(total_shift),
        rotation_vector(total_rotation),
        canonical_zero(total_rotation_path),
        initial_centroid_offset,
        final_centroid_offset,
        maximum_centroid_offset,
    };
}

[[nodiscard]] bool bit_equal(
    const std::vector<Vec3> &left,
    const std::vector<Vec3> &right) noexcept {
    if (left.size() != right.size()) {
        return false;
    }
    for (std::size_t index = 0; index < left.size(); ++index) {
        uint64_t left_x = 0;
        uint64_t left_y = 0;
        uint64_t left_z = 0;
        uint64_t right_x = 0;
        uint64_t right_y = 0;
        uint64_t right_z = 0;
        std::memcpy(&left_x, &left[index].x, sizeof(left_x));
        std::memcpy(&left_y, &left[index].y, sizeof(left_y));
        std::memcpy(&left_z, &left[index].z, sizeof(left_z));
        std::memcpy(&right_x, &right[index].x, sizeof(right_x));
        std::memcpy(&right_y, &right[index].y, sizeof(right_y));
        std::memcpy(&right_z, &right[index].z, sizeof(right_z));
        if (left_x != right_x || left_y != right_y || left_z != right_z) {
            return false;
        }
    }
    return true;
}

[[nodiscard]] V6Outcome refine_v6(
    const ProviderEnvelope &state,
    const std::vector<Vec3> &source,
    std::size_t max_steps,
    bool v3_lane) {
    if (!v3_lane) {
        Outcome selected = refine_v2(state, source, max_steps, state.v2);
        selected.profile =
            BG_DOCKING_RIGID_REFINEMENT_PROFILE_V6_BASELINE_V2;
        V6Outcome result;
        result.selected = std::move(selected);
        return result;
    }
    V6Outcome result;
    result.comparison_v2 = refine_v2(state, source, max_steps, state.v2);
    result.comparison_v2_available = true;
    result.baseline_v3 = refine_v3(state, source, max_steps, state.v3);
    result.baseline_v3.profile =
        BG_DOCKING_RIGID_REFINEMENT_PROFILE_V6_BASELINE_V3;
    result.baseline_v3_available = true;
    result.baseline_duplicate_of_v2 = bit_equal(
        result.comparison_v2.coordinates,
        result.baseline_v3.coordinates);
    result.clearance_evaluated =
        result.baseline_duplicate_of_v2 ||
        result.baseline_v3.final_penalty <= kV6NearClearPenalty;
    if (result.clearance_evaluated) {
        result.clearance_v4 =
            refine_v3(state, source, max_steps, state.clearance_v4);
        result.clearance_v4.profile =
            BG_DOCKING_RIGID_REFINEMENT_PROFILE_V6_CLEARANCE_V4;
        result.clearance_v4_available = true;
        result.clearance_selected =
            result.baseline_duplicate_of_v2 ||
            result.clearance_v4.final_penalty <
                result.clearance_v4.initial_penalty;
    }
    result.selected = result.clearance_selected ? result.clearance_v4
                                                : result.baseline_v3;
    return result;
}

[[nodiscard]] bg_docking_rigid_refinement_evidence_v1 evidence(
    const Outcome &outcome) noexcept {
    bg_docking_rigid_refinement_evidence_v1 result{};
    result.profile = outcome.profile;
    result.available = UINT8_C(1);
    result.accepted_steps = outcome.accepted_steps;
    result.accepted_translation_steps = outcome.accepted_translation_steps;
    result.accepted_rotation_steps = outcome.accepted_rotation_steps;
    result.line_search_evaluation_count =
        outcome.line_search_evaluation_count;
    result.fallback_direction_step_count =
        outcome.fallback_direction_step_count;
    result.initial_penalty = outcome.initial_penalty;
    result.final_penalty = outcome.final_penalty;
    result.total_translation_angstrom[0] = outcome.total_translation.x;
    result.total_translation_angstrom[1] = outcome.total_translation.y;
    result.total_translation_angstrom[2] = outcome.total_translation.z;
    result.total_rotation_vector_radians[0] =
        outcome.total_rotation_vector.x;
    result.total_rotation_vector_radians[1] =
        outcome.total_rotation_vector.y;
    result.total_rotation_vector_radians[2] =
        outcome.total_rotation_vector.z;
    result.total_rotation_path_radians = outcome.total_rotation_path;
    result.initial_centroid_offset_angstrom =
        outcome.initial_centroid_offset;
    result.final_centroid_offset_angstrom = outcome.final_centroid_offset;
    result.maximum_centroid_offset_angstrom =
        outcome.maximum_centroid_offset;
    return result;
}

[[nodiscard]] bg_docking_rigid_refinement_row_v1 failure_row(
    std::size_t slot,
    bg_docking_rigid_refinement_candidate_mode mode,
    bg_docking_rigid_refinement_failure failure) noexcept {
    bg_docking_rigid_refinement_row_v1 row{};
    row.slot_index = static_cast<uint32_t>(slot);
    row.status = BG_DOCKING_RIGID_REFINEMENT_ROW_TYPED_FAILURE;
    row.failure_code = failure;
    row.candidate_mode = mode;
    return row;
}

void copy_coordinates(
    const Outcome &outcome,
    std::size_t slot,
    std::size_t ligand_count,
    std::vector<double> *x,
    std::vector<double> *y,
    std::vector<double> *z) noexcept {
    const std::size_t offset = slot * ligand_count;
    for (std::size_t atom = 0; atom < ligand_count; ++atom) {
        (*x)[offset + atom] = outcome.coordinates[atom].x;
        (*y)[offset + atom] = outcome.coordinates[atom].y;
        (*z)[offset + atom] = outcome.coordinates[atom].z;
    }
}

[[nodiscard]] BatchResult empty_batch(std::size_t coordinate_count) {
    BatchResult result;
    result.selected_x.assign(coordinate_count, 0.0);
    result.selected_y.assign(coordinate_count, 0.0);
    result.selected_z.assign(coordinate_count, 0.0);
    result.comparison_v2_x.assign(coordinate_count, 0.0);
    result.comparison_v2_y.assign(coordinate_count, 0.0);
    result.comparison_v2_z.assign(coordinate_count, 0.0);
    result.baseline_v3_x.assign(coordinate_count, 0.0);
    result.baseline_v3_y.assign(coordinate_count, 0.0);
    result.baseline_v3_z.assign(coordinate_count, 0.0);
    result.clearance_v4_x.assign(coordinate_count, 0.0);
    result.clearance_v4_y.assign(coordinate_count, 0.0);
    result.clearance_v4_z.assign(coordinate_count, 0.0);
    return result;
}

[[nodiscard]] BatchResult refine_cpp_fixed64(
    const ProviderEnvelope &state,
    const bg_docking_rigid_refinement_candidate_batch_soa_v1 &batch,
    std::size_t coordinate_count) {
    BatchResult result = empty_batch(coordinate_count);
    const std::size_t ligand_count = state.ligand_radii.size();
    for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
        const auto mode = batch.candidate_mode[slot];
        result.rows[slot] = failure_row(
            slot,
            mode,
            BG_DOCKING_RIGID_REFINEMENT_FAILURE_UPSTREAM_NOT_ELIGIBLE);
        if (mode == BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_INACTIVE) {
            continue;
        }
        if (mode < BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION ||
            mode >
                BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V3_LANE ||
            batch.max_steps[slot] < 1 || batch.max_steps[slot] > kMaxSteps) {
            result.rows[slot] = failure_row(
                slot,
                mode,
                BG_DOCKING_RIGID_REFINEMENT_FAILURE_INVALID_INPUT);
            continue;
        }
        const std::size_t offset = slot * ligand_count;
        std::vector<Vec3> source;
        source.reserve(ligand_count);
        bool all_coordinates_finite = true;
        for (std::size_t atom = 0; atom < ligand_count; ++atom) {
            const std::size_t index = offset + atom;
            const Vec3 coordinate{
                batch.x_angstrom[index],
                batch.y_angstrom[index],
                batch.z_angstrom[index],
            };
            all_coordinates_finite = all_coordinates_finite && finite(coordinate);
            source.push_back(coordinate);
        }
        if (!all_coordinates_finite) {
            result.rows[slot] = failure_row(
                slot,
                mode,
                BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONFINITE_INPUT);
            continue;
        }
        try {
            V6Outcome outcome;
            if (mode ==
                BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION) {
                outcome.selected = refine_v2(
                    state,
                    source,
                    static_cast<std::size_t>(batch.max_steps[slot]),
                    state.v2);
            } else if (
                mode ==
                BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V3_TRANSLATION_ROTATION) {
                outcome.selected = refine_v3(
                    state,
                    source,
                    static_cast<std::size_t>(batch.max_steps[slot]),
                    state.v3);
            } else {
                outcome = refine_v6(
                    state,
                    source,
                    static_cast<std::size_t>(batch.max_steps[slot]),
                    mode ==
                        BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V3_LANE);
            }
            auto &row = result.rows[slot];
            row = {};
            row.slot_index = static_cast<uint32_t>(slot);
            row.status = BG_DOCKING_RIGID_REFINEMENT_ROW_REFINED;
            row.failure_code = BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE;
            row.candidate_mode = mode;
            row.selected_profile = outcome.selected.profile;
            row.baseline_duplicate_of_v2 =
                static_cast<uint8_t>(outcome.baseline_duplicate_of_v2);
            row.clearance_evaluated =
                static_cast<uint8_t>(outcome.clearance_evaluated);
            row.clearance_selected =
                static_cast<uint8_t>(outcome.clearance_selected);
            row.selected = evidence(outcome.selected);
            copy_coordinates(
                outcome.selected,
                slot,
                ligand_count,
                &result.selected_x,
                &result.selected_y,
                &result.selected_z);
            if (outcome.comparison_v2_available) {
                row.comparison_v2 = evidence(outcome.comparison_v2);
                copy_coordinates(
                    outcome.comparison_v2,
                    slot,
                    ligand_count,
                    &result.comparison_v2_x,
                    &result.comparison_v2_y,
                    &result.comparison_v2_z);
            }
            if (outcome.baseline_v3_available) {
                row.baseline_v3 = evidence(outcome.baseline_v3);
                copy_coordinates(
                    outcome.baseline_v3,
                    slot,
                    ligand_count,
                    &result.baseline_v3_x,
                    &result.baseline_v3_y,
                    &result.baseline_v3_z);
            }
            if (outcome.clearance_v4_available) {
                row.clearance_v4 = evidence(outcome.clearance_v4);
                copy_coordinates(
                    outcome.clearance_v4,
                    slot,
                    ligand_count,
                    &result.clearance_v4_x,
                    &result.clearance_v4_y,
                    &result.clearance_v4_z);
            }
        } catch (const LocalFailure &failure) {
            result.rows[slot] = failure_row(slot, mode, failure.code);
        }
    }
    return result;
}

[[nodiscard]] bg_status validate_batch_and_output(
    const bg_context *context,
    const bg_docking_rigid_refinement *refiner,
    const bg_docking_rigid_refinement_candidate_batch_soa_v1 &batch,
    const bg_docking_rigid_refinement_output_v1 &output,
    std::size_t *coordinate_count) noexcept {
    bg_status status = validate_descriptor_header(
        batch.struct_size,
        sizeof(batch),
        batch.abi_version,
        "rigid refinement batch size does not match ABI v1",
        "rigid refinement batch ABI version does not match");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = validate_descriptor_header(
        output.struct_size,
        sizeof(output),
        output.abi_version,
        "rigid refinement output size does not match ABI v1",
        "rigid refinement output ABI version does not match");
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (refiner == nullptr || coordinate_count == nullptr) {
        return fail(BG_STATUS_INVALID_ARGUMENT, "rigid refinement handle is null");
    }
    if (validate_unit_system(batch.unit_system) != BG_STATUS_OK ||
        validate_unit_system(output.unit_system) != BG_STATUS_OK) {
        return BG_STATUS_INVALID_ARGUMENT;
    }
    if (batch.reserved0 != 0 || !reserved_is_zero(batch.reserved) ||
        output.reserved0 != 0 || output.reserved1 != 0 ||
        !reserved_is_zero(output.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "rigid refinement batch or output reserved fields must be zero");
    }
    if (batch.candidate_count != kCandidateCount ||
        batch.ligand_atom_count != refiner->ligand_atom_count ||
        batch.ligand_atom_count == 0 ||
        batch.ligand_atom_count > kMaxLigandAtoms) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "rigid refinement fixed64 or ligand denominator is cross-wired");
    }
    std::size_t ligand_count = 0;
    status = public_count(
        batch.ligand_atom_count,
        "rigid refinement ligand count overflows",
        &ligand_count);
    if (status != BG_STATUS_OK ||
        !checked_multiply(kCandidateCount, ligand_count, coordinate_count)) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "rigid refinement coordinate denominator overflows");
    }
    const std::array<const void *, 13> output_pointers = {
        output.rows,
        output.selected_x_angstrom,
        output.selected_y_angstrom,
        output.selected_z_angstrom,
        output.comparison_v2_x_angstrom,
        output.comparison_v2_y_angstrom,
        output.comparison_v2_z_angstrom,
        output.baseline_v3_x_angstrom,
        output.baseline_v3_y_angstrom,
        output.baseline_v3_z_angstrom,
        output.clearance_v4_x_angstrom,
        output.clearance_v4_y_angstrom,
        output.clearance_v4_z_angstrom,
    };
    if (output.row_capacity < kCandidateCount ||
        output.coordinate_capacity < *coordinate_count ||
        std::any_of(
            output_pointers.begin(),
            output_pointers.end(),
            [](const void *pointer) { return pointer == nullptr; }) ||
        !pointer_is_aligned(output.rows) ||
        !pointer_is_aligned(output.selected_x_angstrom) ||
        !pointer_is_aligned(output.selected_y_angstrom) ||
        !pointer_is_aligned(output.selected_z_angstrom) ||
        !pointer_is_aligned(output.comparison_v2_x_angstrom) ||
        !pointer_is_aligned(output.comparison_v2_y_angstrom) ||
        !pointer_is_aligned(output.comparison_v2_z_angstrom) ||
        !pointer_is_aligned(output.baseline_v3_x_angstrom) ||
        !pointer_is_aligned(output.baseline_v3_y_angstrom) ||
        !pointer_is_aligned(output.baseline_v3_z_angstrom) ||
        !pointer_is_aligned(output.clearance_v4_x_angstrom) ||
        !pointer_is_aligned(output.clearance_v4_y_angstrom) ||
        !pointer_is_aligned(output.clearance_v4_z_angstrom)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "rigid refinement output capacity or channel is invalid");
    }
#define BG_REQUIRE_RIGID_BATCH_CHANNEL(pointer, count, message)              \
    do {                                                                     \
        status = require_channel((pointer), (count), (message));             \
        if (status != BG_STATUS_OK) {                                        \
            return status;                                                   \
        }                                                                    \
    } while (false)
    BG_REQUIRE_RIGID_BATCH_CHANNEL(
        batch.candidate_mode,
        kCandidateCount,
        "rigid refinement mode channel is null or misaligned");
    BG_REQUIRE_RIGID_BATCH_CHANNEL(
        batch.max_steps,
        kCandidateCount,
        "rigid refinement step channel is null or misaligned");
    BG_REQUIRE_RIGID_BATCH_CHANNEL(
        batch.x_angstrom,
        *coordinate_count,
        "rigid refinement x channel is null or misaligned");
    BG_REQUIRE_RIGID_BATCH_CHANNEL(
        batch.y_angstrom,
        *coordinate_count,
        "rigid refinement y channel is null or misaligned");
    BG_REQUIRE_RIGID_BATCH_CHANNEL(
        batch.z_angstrom,
        *coordinate_count,
        "rigid refinement z channel is null or misaligned");
#undef BG_REQUIRE_RIGID_BATCH_CHANNEL

    const std::array<std::pair<const void *, std::size_t>, 8> inputs = {{
        {context, sizeof(*context)},
        {refiner, sizeof(*refiner)},
        {&batch, sizeof(batch)},
        {batch.candidate_mode,
         kCandidateCount * sizeof(*batch.candidate_mode)},
        {batch.max_steps, kCandidateCount * sizeof(*batch.max_steps)},
        {batch.x_angstrom, *coordinate_count * sizeof(*batch.x_angstrom)},
        {batch.y_angstrom, *coordinate_count * sizeof(*batch.y_angstrom)},
        {batch.z_angstrom, *coordinate_count * sizeof(*batch.z_angstrom)},
    }};
    std::array<std::pair<const void *, std::size_t>, 14> outputs{};
    outputs[0] = {&output, sizeof(output)};
    outputs[1] = {output.rows, kCandidateCount * sizeof(*output.rows)};
    for (std::size_t index = 2; index < outputs.size(); ++index) {
        outputs[index] = {
            output_pointers[index - 1],
            *coordinate_count * sizeof(double),
        };
    }
    for (std::size_t first = 0; first < outputs.size(); ++first) {
        for (std::size_t second = first + 1; second < outputs.size(); ++second) {
            if (ranges_overlap(
                    outputs[first].first,
                    outputs[first].second,
                    outputs[second].first,
                    outputs[second].second)) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "rigid refinement output buffers overlap");
            }
        }
        for (const auto &input : inputs) {
            if (ranges_overlap(
                    outputs[first].first,
                    outputs[first].second,
                    input.first,
                    input.second)) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "rigid refinement input and output buffers overlap");
            }
        }
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bool v2_traversal_upper_bound(
    std::size_t steps,
    const V2Config &config,
    std::size_t *output) noexcept {
    std::size_t backtracking = 0;
    std::size_t per_step = 0;
    std::size_t iterative = 0;
    return checked_multiply(
               2U, config.maximum_backtracking_evaluations, &backtracking) &&
           checked_add(2U, backtracking, &per_step) &&
           checked_multiply(steps, per_step, &iterative) &&
           checked_add(2U, iterative, output);
}

[[nodiscard]] bool v3_traversal_upper_bound(
    std::size_t steps,
    const V3Config &config,
    std::size_t *output) noexcept {
    std::size_t backtracking = 0;
    std::size_t per_step = 0;
    std::size_t iterative = 0;
    return checked_multiply(
               3U,
               config.v2.maximum_backtracking_evaluations,
               &backtracking) &&
           checked_add(3U, backtracking, &per_step) &&
           checked_multiply(steps, per_step, &iterative) &&
           checked_add(2U, iterative, output);
}

[[nodiscard]] bg_status validate_total_pair_work(
    const ProviderEnvelope &state,
    const bg_docking_rigid_refinement_candidate_batch_soa_v1 &batch) noexcept {
    std::size_t pair_count = 0;
    if (!checked_multiply(
            state.receptor.size(), state.ligand_radii.size(), &pair_count) ||
        pair_count == 0) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "rigid refinement pair denominator overflows");
    }
    const std::size_t maximum_traversals =
        kMaxPairEvaluations / pair_count;
    std::size_t total_traversals = 0;
    for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
        const auto mode = batch.candidate_mode[slot];
        if (mode == BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_INACTIVE ||
            mode < BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION ||
            mode >
                BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V3_LANE ||
            batch.max_steps[slot] < 1 ||
            batch.max_steps[slot] > kMaxSteps) {
            continue;
        }
        const auto steps =
            static_cast<std::size_t>(batch.max_steps[slot]);
        std::size_t candidate_traversals = 0;
        bool valid_bound = false;
        if (mode == BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION ||
            mode ==
                BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V2_LANE) {
            valid_bound = v2_traversal_upper_bound(
                steps, state.v2, &candidate_traversals);
        } else if (
            mode ==
            BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V3_TRANSLATION_ROTATION) {
            valid_bound = v3_traversal_upper_bound(
                steps, state.v3, &candidate_traversals);
        } else {
            std::size_t comparison_v2 = 0;
            std::size_t baseline_v3 = 0;
            std::size_t clearance_v4 = 0;
            std::size_t combined_v2_v3 = 0;
            valid_bound = v2_traversal_upper_bound(
                              steps, state.v2, &comparison_v2) &&
                          v3_traversal_upper_bound(
                              steps, state.v3, &baseline_v3) &&
                          v3_traversal_upper_bound(
                              steps, state.clearance_v4, &clearance_v4) &&
                          checked_add(
                              comparison_v2,
                              baseline_v3,
                              &combined_v2_v3) &&
                          checked_add(
                              combined_v2_v3,
                              clearance_v4,
                              &candidate_traversals);
        }
        if (!valid_bound ||
            !checked_add(
                total_traversals,
                candidate_traversals,
                &total_traversals) ||
            total_traversals > maximum_traversals) {
            return fail(
                BG_STATUS_CAPACITY_OVERFLOW,
                "rigid refinement fixed64 total pair-work budget exceeded");
        }
    }
    return BG_STATUS_OK;
}

void initialize_rust_error(bg_rust_cpu_error_v1 *error) noexcept {
    *error = {};
    error->struct_size = static_cast<uint32_t>(sizeof(*error));
    error->abi_version = BG_RUST_CPU_PROVIDER_ABI_VERSION;
}

[[nodiscard]] bg_status rust_failure(
    int32_t status,
    const bg_rust_cpu_error_v1 &error,
    const char *fallback) noexcept {
    const auto mapped = status >= BG_STATUS_OK && status <= BG_STATUS_NUMERICAL_ERROR
                            ? static_cast<bg_status>(status)
                            : BG_STATUS_BACKEND_ERROR;
    return fail(mapped, error.message[0] == '\0' ? fallback : error.message);
}

[[nodiscard]] bg_status hip_failure(
    int32_t raw_status,
    const std::array<char, BG_HIP_SAFE_ERROR_CAPACITY> &error,
    const char *fallback) noexcept {
    const char *message = error[0] == '\0' ? fallback : error.data();
    switch (raw_status) {
        case BG_STATUS_INVALID_ARGUMENT:
        case BG_STATUS_ABI_MISMATCH:
        case BG_STATUS_UNSUPPORTED_BACKEND:
        case BG_STATUS_BACKEND_UNAVAILABLE:
        case BG_STATUS_OUT_OF_MEMORY:
        case BG_STATUS_CAPACITY_OVERFLOW:
        case BG_STATUS_BUFFER_TOO_SMALL:
        case BG_STATUS_BACKEND_ERROR:
        case BG_STATUS_INTERNAL_ERROR:
        case BG_STATUS_NUMERICAL_ERROR:
            return fail(static_cast<bg_status>(raw_status), message);
        default:
            return fail(BG_STATUS_INTERNAL_ERROR, fallback);
    }
}

[[nodiscard]] bg_status create_hip_backend(
    ProviderEnvelope *state,
    bg_backend backend,
    int32_t device_ordinal,
    const bg_docking_rigid_refinement_context_soa_v1 &descriptor) {
    static_cast<void>(device_ordinal);
    static_cast<void>(descriptor);
    if (state == nullptr) {
        return fail(BG_STATUS_INTERNAL_ERROR, "rigid HIP state is null");
    }
    std::array<char, BG_HIP_SAFE_ERROR_CAPACITY> error{};
    void *provider_state = nullptr;
    int32_t raw_status = BG_STATUS_BACKEND_UNAVAILABLE;
    if (backend == BG_BACKEND_HIP_SAFE) {
#if BG_HAS_HIP_SAFE_PROVIDER
        raw_status = bg_hip_safe_docking_rigid_refinement_create(
            device_ordinal,
            &descriptor,
            &provider_state,
            error.data(),
            error.size());
#else
        return fail(
            BG_STATUS_BACKEND_UNAVAILABLE,
            "hip_safe rigid refinement provider is not compiled; fallback is forbidden");
#endif
    } else if (backend == BG_BACKEND_HIP_FAST) {
#if BG_ENABLE_HIP
        raw_status = bg_hip_fast_docking_rigid_refinement_create(
            device_ordinal,
            &descriptor,
            &provider_state,
            error.data(),
            error.size());
#else
        return fail(
            BG_STATUS_BACKEND_UNAVAILABLE,
            "hip_fast rigid refinement provider is not compiled; fallback is forbidden");
#endif
    } else {
        return fail(
            BG_STATUS_UNSUPPORTED_BACKEND,
            "rigid refinement HIP provider received a non-HIP backend");
    }
    if (raw_status != BG_STATUS_OK) {
        return hip_failure(
            raw_status, error, "native HIP rigid refinement creation failed");
    }
    state->backend_state = provider_state;
    return BG_STATUS_OK;
}

[[nodiscard]] bg_rust_cpu_rigid_v2_config_v1 rust_v2(
    const V2Config &source) noexcept {
    bg_rust_cpu_rigid_v2_config_v1 result{};
    result.overlap_scale = source.overlap_scale;
    result.maximum_step_angstrom = source.maximum_step_angstrom;
    result.minimum_step_angstrom = source.minimum_step_angstrom;
    result.maximum_total_translation_angstrom =
        source.maximum_total_translation_angstrom;
    result.maximum_backtracking_evaluations =
        source.maximum_backtracking_evaluations;
    result.penalty_tolerance = source.penalty_tolerance;
    result.epsilon_angstrom = source.epsilon_angstrom;
    return result;
}

[[nodiscard]] bg_rust_cpu_rigid_v3_config_v1 rust_v3(
    const V3Config &source) noexcept {
    bg_rust_cpu_rigid_v3_config_v1 result{};
    result.v2 = rust_v2(source.v2);
    result.maximum_rotation_step_radians =
        source.maximum_rotation_step_radians;
    result.minimum_rotation_step_radians =
        source.minimum_rotation_step_radians;
    result.maximum_total_rotation_radians =
        source.maximum_total_rotation_radians;
    result.maximum_rotation_steps = source.maximum_rotation_steps;
    result.minimum_rotation_relative_penalty_reduction =
        source.minimum_rotation_relative_penalty_reduction;
    result.maximum_centroid_offset_angstrom =
        source.maximum_centroid_offset_angstrom;
    return result;
}

[[nodiscard]] bg_status create_rust_backend(ProviderEnvelope *state) {
    if (state == nullptr) {
        return fail(BG_STATUS_INTERNAL_ERROR, "rigid Rust state is null");
    }
    std::vector<double> receptor_x;
    std::vector<double> receptor_y;
    std::vector<double> receptor_z;
    receptor_x.reserve(state->receptor.size());
    receptor_y.reserve(state->receptor.size());
    receptor_z.reserve(state->receptor.size());
    for (const Vec3 value : state->receptor) {
        receptor_x.push_back(value.x);
        receptor_y.push_back(value.y);
        receptor_z.push_back(value.z);
    }
    bg_rust_cpu_rigid_context_v1 descriptor{};
    descriptor.struct_size = static_cast<uint32_t>(sizeof(descriptor));
    descriptor.abi_version = BG_RUST_CPU_PROVIDER_ABI_VERSION;
    descriptor.receptor_atom_count = state->receptor.size();
    descriptor.ligand_atom_count = state->ligand_radii.size();
    descriptor.receptor_x_angstrom = receptor_x.data();
    descriptor.receptor_y_angstrom = receptor_y.data();
    descriptor.receptor_z_angstrom = receptor_z.data();
    descriptor.receptor_vdw_radius_angstrom = state->receptor_radii.data();
    descriptor.ligand_vdw_radius_angstrom = state->ligand_radii.data();
    descriptor.pocket_center_angstrom[0] = state->pocket_center.x;
    descriptor.pocket_center_angstrom[1] = state->pocket_center.y;
    descriptor.pocket_center_angstrom[2] = state->pocket_center.z;
    descriptor.pocket_radius_angstrom = state->pocket_radius;
    descriptor.v2 = rust_v2(state->v2);
    descriptor.v3 = rust_v3(state->v3);
    descriptor.clearance_v4 = rust_v3(state->clearance_v4);
    bg_rust_cpu_error_v1 error{};
    initialize_rust_error(&error);
    const int32_t status = bg_rust_cpu_docking_rigid_refinement_create(
        &descriptor, &state->backend_state, &error);
    if (status != BG_STATUS_OK) {
        return rust_failure(status, error, "rust_cpu rigid create failed");
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_docking_rigid_refinement_evidence_v1 public_evidence(
    const bg_rust_cpu_rigid_evidence_v1 &source) noexcept {
    bg_docking_rigid_refinement_evidence_v1 result{};
    result.profile = source.profile;
    result.available = source.available;
    result.accepted_steps = source.accepted_steps;
    result.accepted_translation_steps = source.accepted_translation_steps;
    result.accepted_rotation_steps = source.accepted_rotation_steps;
    result.line_search_evaluation_count =
        source.line_search_evaluation_count;
    result.fallback_direction_step_count =
        source.fallback_direction_step_count;
    result.initial_penalty = source.initial_penalty;
    result.final_penalty = source.final_penalty;
    std::copy_n(
        source.total_translation_angstrom,
        3,
        result.total_translation_angstrom);
    std::copy_n(
        source.total_rotation_vector_radians,
        3,
        result.total_rotation_vector_radians);
    result.total_rotation_path_radians = source.total_rotation_path_radians;
    result.initial_centroid_offset_angstrom =
        source.initial_centroid_offset_angstrom;
    result.final_centroid_offset_angstrom =
        source.final_centroid_offset_angstrom;
    result.maximum_centroid_offset_angstrom =
        source.maximum_centroid_offset_angstrom;
    return result;
}

[[nodiscard]] bg_docking_rigid_refinement_row_v1 public_row(
    const bg_rust_cpu_rigid_row_v1 &source) noexcept {
    bg_docking_rigid_refinement_row_v1 result{};
    result.slot_index = source.slot_index;
    result.status = source.status;
    result.failure_code = source.failure_code;
    result.candidate_mode = source.candidate_mode;
    result.selected_profile = source.selected_profile;
    result.baseline_duplicate_of_v2 = source.baseline_duplicate_of_v2;
    result.clearance_evaluated = source.clearance_evaluated;
    result.clearance_selected = source.clearance_selected;
    result.selected = public_evidence(source.selected);
    result.comparison_v2 = public_evidence(source.comparison_v2);
    result.baseline_v3 = public_evidence(source.baseline_v3);
    result.clearance_v4 = public_evidence(source.clearance_v4);
    return result;
}

[[nodiscard]] bg_status refine_rust_fixed64(
    const ProviderEnvelope &state,
    const bg_docking_rigid_refinement_candidate_batch_soa_v1 &batch,
    std::size_t coordinate_count,
    BatchResult *output) {
    if (state.backend_state == nullptr || output == nullptr) {
        return fail(BG_STATUS_INTERNAL_ERROR, "rigid Rust provider is null");
    }
    std::array<std::size_t, kCandidateCount> steps{};
    for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
        if constexpr (sizeof(std::size_t) < sizeof(uint64_t)) {
            if (batch.max_steps[slot] > static_cast<uint64_t>(
                                            std::numeric_limits<std::size_t>::max())) {
                steps[slot] = kMaxSteps + 1;
                continue;
            }
        }
        steps[slot] = static_cast<std::size_t>(batch.max_steps[slot]);
    }
    bg_rust_cpu_rigid_batch_v1 rust_batch{};
    rust_batch.struct_size = static_cast<uint32_t>(sizeof(rust_batch));
    rust_batch.abi_version = BG_RUST_CPU_PROVIDER_ABI_VERSION;
    rust_batch.candidate_count = kCandidateCount;
    rust_batch.ligand_atom_count = state.ligand_radii.size();
    rust_batch.candidate_mode = batch.candidate_mode;
    rust_batch.max_steps = steps.data();
    rust_batch.x_angstrom = batch.x_angstrom;
    rust_batch.y_angstrom = batch.y_angstrom;
    rust_batch.z_angstrom = batch.z_angstrom;
    BatchResult result = empty_batch(coordinate_count);
    std::array<bg_rust_cpu_rigid_row_v1, kCandidateCount> rows{};
    bg_rust_cpu_error_v1 error{};
    initialize_rust_error(&error);
    const int32_t status = bg_rust_cpu_docking_rigid_refinement_fixed64(
        state.backend_state,
        &rust_batch,
        rows.data(),
        result.selected_x.data(),
        result.selected_y.data(),
        result.selected_z.data(),
        result.comparison_v2_x.data(),
        result.comparison_v2_y.data(),
        result.comparison_v2_z.data(),
        result.baseline_v3_x.data(),
        result.baseline_v3_y.data(),
        result.baseline_v3_z.data(),
        result.clearance_v4_x.data(),
        result.clearance_v4_y.data(),
        result.clearance_v4_z.data(),
        &error);
    if (status != BG_STATUS_OK) {
        return rust_failure(status, error, "rust_cpu rigid batch failed");
    }
    for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
        result.rows[slot] = public_row(rows[slot]);
    }
    *output = std::move(result);
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status refine_hip_fixed64(
    const ProviderEnvelope &state,
    bg_backend backend,
    const bg_docking_rigid_refinement_candidate_batch_soa_v1 &batch,
    std::size_t coordinate_count,
    BatchResult *output) {
    static_cast<void>(batch);
    if (state.backend_state == nullptr || output == nullptr) {
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "native HIP rigid refinement state or output is null");
    }
    BatchResult result = empty_batch(coordinate_count);
    std::array<char, BG_HIP_SAFE_ERROR_CAPACITY> error{};
    int32_t raw_status = BG_STATUS_BACKEND_UNAVAILABLE;
    if (backend == BG_BACKEND_HIP_SAFE) {
#if BG_HAS_HIP_SAFE_PROVIDER
        raw_status = bg_hip_safe_docking_rigid_refinement_fixed64(
            state.backend_state,
            &batch,
            result.rows.data(),
            result.selected_x.data(),
            result.selected_y.data(),
            result.selected_z.data(),
            result.comparison_v2_x.data(),
            result.comparison_v2_y.data(),
            result.comparison_v2_z.data(),
            result.baseline_v3_x.data(),
            result.baseline_v3_y.data(),
            result.baseline_v3_z.data(),
            result.clearance_v4_x.data(),
            result.clearance_v4_y.data(),
            result.clearance_v4_z.data(),
            error.data(),
            error.size());
#else
        return fail(
            BG_STATUS_BACKEND_UNAVAILABLE,
            "hip_safe rigid refinement provider is not compiled; fallback is forbidden");
#endif
    } else if (backend == BG_BACKEND_HIP_FAST) {
#if BG_ENABLE_HIP
        raw_status = bg_hip_fast_docking_rigid_refinement_fixed64(
            state.backend_state,
            &batch,
            result.rows.data(),
            result.selected_x.data(),
            result.selected_y.data(),
            result.selected_z.data(),
            result.comparison_v2_x.data(),
            result.comparison_v2_y.data(),
            result.comparison_v2_z.data(),
            result.baseline_v3_x.data(),
            result.baseline_v3_y.data(),
            result.baseline_v3_z.data(),
            result.clearance_v4_x.data(),
            result.clearance_v4_y.data(),
            result.clearance_v4_z.data(),
            error.data(),
            error.size());
#else
        return fail(
            BG_STATUS_BACKEND_UNAVAILABLE,
            "hip_fast rigid refinement provider is not compiled; fallback is forbidden");
#endif
    } else {
        return fail(
            BG_STATUS_UNSUPPORTED_BACKEND,
            "rigid refinement HIP dispatch received a non-HIP backend");
    }
    if (raw_status != BG_STATUS_OK) {
        return hip_failure(
            raw_status, error, "native HIP rigid refinement batch failed");
    }
    *output = std::move(result);
    return BG_STATUS_OK;
}

[[nodiscard]] bool finite_evidence(
    const bg_docking_rigid_refinement_evidence_v1 &value) noexcept {
    const std::array<double, 13> values = {
        value.initial_penalty,
        value.final_penalty,
        value.total_translation_angstrom[0],
        value.total_translation_angstrom[1],
        value.total_translation_angstrom[2],
        value.total_rotation_vector_radians[0],
        value.total_rotation_vector_radians[1],
        value.total_rotation_vector_radians[2],
        value.total_rotation_path_radians,
        value.initial_centroid_offset_angstrom,
        value.final_centroid_offset_angstrom,
        value.maximum_centroid_offset_angstrom,
        static_cast<double>(value.available),
    };
    return std::all_of(values.begin(), values.end(), [](double item) {
        return std::isfinite(item);
    });
}

[[nodiscard]] bool zero_evidence(
    const bg_docking_rigid_refinement_evidence_v1 &value) noexcept {
    const bg_docking_rigid_refinement_evidence_v1 zero{};
    return std::memcmp(&value, &zero, sizeof(value)) == 0;
}

[[nodiscard]] bool consistent_evidence(
    const bg_docking_rigid_refinement_evidence_v1 &value) noexcept {
    if (!finite_evidence(value)) {
        return false;
    }
    if (value.available == UINT8_C(0)) {
        return zero_evidence(value);
    }
    if (value.available != UINT8_C(1) || value.reserved0[0] != 0 ||
        value.reserved0[1] != 0 || value.reserved0[2] != 0 ||
        !reserved_is_zero(value.reserved) ||
        value.profile < BG_DOCKING_RIGID_REFINEMENT_PROFILE_V2_TRANSLATION ||
        value.profile > BG_DOCKING_RIGID_REFINEMENT_PROFILE_V6_CLEARANCE_V4 ||
        value.accepted_translation_steps > value.accepted_steps ||
        value.accepted_rotation_steps !=
            value.accepted_steps - value.accepted_translation_steps ||
        value.initial_penalty < 0.0 || value.final_penalty < 0.0 ||
        value.total_rotation_path_radians < 0.0) {
        return false;
    }
    const Vec3 rotation{
        value.total_rotation_vector_radians[0],
        value.total_rotation_vector_radians[1],
        value.total_rotation_vector_radians[2],
    };
    const double rotation_angle = norm(rotation);
    if (!std::isfinite(rotation_angle) ||
        rotation_angle > value.total_rotation_path_radians + 2.0e-12) {
        return false;
    }
    if (value.accepted_rotation_steps == 0 &&
        (rotation_angle != 0.0 || value.total_rotation_path_radians != 0.0)) {
        return false;
    }
    return true;
}

[[nodiscard]] bool transform_matches(
    const bg_docking_rigid_refinement_evidence_v1 &evidence,
    const bg_docking_rigid_refinement_candidate_batch_soa_v1 &batch,
    std::size_t slot,
    std::size_t ligand_count,
    const std::vector<double> &x,
    const std::vector<double> &y,
    const std::vector<double> &z) noexcept {
    const std::size_t offset = slot * ligand_count;
    if (evidence.available == UINT8_C(0)) {
        for (std::size_t atom = 0; atom < ligand_count; ++atom) {
            const std::size_t index = offset + atom;
            if (x[index] != 0.0 || y[index] != 0.0 || z[index] != 0.0) {
                return false;
            }
        }
        return true;
    }

    Vec3 source_centroid;
    for (std::size_t atom = 0; atom < ligand_count; ++atom) {
        const std::size_t index = offset + atom;
        const Vec3 source{
            batch.x_angstrom[index],
            batch.y_angstrom[index],
            batch.z_angstrom[index],
        };
        if (!finite(source)) {
            return false;
        }
        source_centroid = plus(source_centroid, source);
    }
    source_centroid = scale(
        source_centroid, 1.0 / static_cast<double>(ligand_count));
    const Vec3 rotation{
        evidence.total_rotation_vector_radians[0],
        evidence.total_rotation_vector_radians[1],
        evidence.total_rotation_vector_radians[2],
    };
    const Vec3 translation{
        evidence.total_translation_angstrom[0],
        evidence.total_translation_angstrom[1],
        evidence.total_translation_angstrom[2],
    };
    const double angle = norm(rotation);
    Vec3 axis;
    double cosine = 1.0;
    double sine = 0.0;
    if (angle > 1.0e-18) {
        axis = scale(rotation, 1.0 / angle);
        cosine = std::cos(angle);
        sine = std::sin(angle);
    }
    for (std::size_t atom = 0; atom < ligand_count; ++atom) {
        const std::size_t index = offset + atom;
        const Vec3 source{
            batch.x_angstrom[index],
            batch.y_angstrom[index],
            batch.z_angstrom[index],
        };
        const Vec3 centered = minus(source, source_centroid);
        Vec3 rotated = centered;
        if (angle > 1.0e-18) {
            rotated = plus(
                plus(
                    scale(centered, cosine),
                    scale(cross(axis, centered), sine)),
                scale(axis, dot(axis, centered) * (1.0 - cosine)));
        }
        const Vec3 expected = plus(
            plus(rotated, source_centroid), translation);
        const std::array<std::pair<double, double>, 3> coordinates = {{
            {expected.x, x[index]},
            {expected.y, y[index]},
            {expected.z, z[index]},
        }};
        for (const auto &[expected_value, observed_value] : coordinates) {
            const double magnitude = std::max(
                {1.0, std::abs(expected_value), std::abs(observed_value)});
            if (std::abs(expected_value - observed_value) >
                2.0e-9 * magnitude) {
                return false;
            }
        }
    }
    return true;
}

[[nodiscard]] bg_status validate_result(
    const BatchResult &result,
    const bg_docking_rigid_refinement_candidate_batch_soa_v1 &batch,
    std::size_t ligand_count) noexcept {
    const std::size_t coordinate_count = kCandidateCount * ligand_count;
    const std::array<const std::vector<double> *, 12> channels = {
        &result.selected_x,
        &result.selected_y,
        &result.selected_z,
        &result.comparison_v2_x,
        &result.comparison_v2_y,
        &result.comparison_v2_z,
        &result.baseline_v3_x,
        &result.baseline_v3_y,
        &result.baseline_v3_z,
        &result.clearance_v4_x,
        &result.clearance_v4_y,
        &result.clearance_v4_z,
    };
    for (const auto *channel : channels) {
        if (channel->size() != coordinate_count ||
            std::any_of(channel->begin(), channel->end(), [](double value) {
                return !std::isfinite(value);
            })) {
            return fail(
                BG_STATUS_NUMERICAL_ERROR,
                "rigid provider returned a malformed coordinate denominator");
        }
    }
    for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
        const auto &row = result.rows[slot];
        if (row.slot_index != slot || row.reserved0 != 0 ||
            !reserved_is_zero(row.reserved) ||
            row.baseline_duplicate_of_v2 > UINT8_C(1) ||
            row.clearance_evaluated > UINT8_C(1) ||
            row.clearance_selected > UINT8_C(1) ||
            !consistent_evidence(row.selected) ||
            !consistent_evidence(row.comparison_v2) ||
            !consistent_evidence(row.baseline_v3) ||
            !consistent_evidence(row.clearance_v4) ||
            !transform_matches(
                row.selected,
                batch,
                slot,
                ligand_count,
                result.selected_x,
                result.selected_y,
                result.selected_z) ||
            !transform_matches(
                row.comparison_v2,
                batch,
                slot,
                ligand_count,
                result.comparison_v2_x,
                result.comparison_v2_y,
                result.comparison_v2_z) ||
            !transform_matches(
                row.baseline_v3,
                batch,
                slot,
                ligand_count,
                result.baseline_v3_x,
                result.baseline_v3_y,
                result.baseline_v3_z) ||
            !transform_matches(
                row.clearance_v4,
                batch,
                slot,
                ligand_count,
                result.clearance_v4_x,
                result.clearance_v4_y,
                result.clearance_v4_z)) {
            return fail(
                BG_STATUS_INTERNAL_ERROR,
                "rigid provider returned malformed row evidence");
        }
        if (row.status == BG_DOCKING_RIGID_REFINEMENT_ROW_TYPED_FAILURE) {
            if (row.failure_code <
                    BG_DOCKING_RIGID_REFINEMENT_FAILURE_UPSTREAM_NOT_ELIGIBLE ||
                row.failure_code >
                    BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONFINITE_DERIVED_VALUE ||
                row.selected_profile !=
                    BG_DOCKING_RIGID_REFINEMENT_PROFILE_NONE ||
                row.baseline_duplicate_of_v2 != 0 ||
                row.clearance_evaluated != 0 || row.clearance_selected != 0 ||
                !zero_evidence(row.selected) ||
                !zero_evidence(row.comparison_v2) ||
                !zero_evidence(row.baseline_v3) ||
                !zero_evidence(row.clearance_v4)) {
                return fail(
                    BG_STATUS_INTERNAL_ERROR,
                    "rigid provider returned malformed typed failure");
            }
        } else if (row.status == BG_DOCKING_RIGID_REFINEMENT_ROW_REFINED) {
            if (row.failure_code != BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONE ||
                row.selected.available != UINT8_C(1) ||
                row.selected.profile != row.selected_profile ||
                row.selected_profile <
                    BG_DOCKING_RIGID_REFINEMENT_PROFILE_V2_TRANSLATION ||
                row.selected_profile >
                    BG_DOCKING_RIGID_REFINEMENT_PROFILE_V6_CLEARANCE_V4 ||
                row.selected.accepted_translation_steps +
                        row.selected.accepted_rotation_steps !=
                    row.selected.accepted_steps ||
                row.clearance_selected > row.clearance_evaluated) {
                return fail(
                    BG_STATUS_INTERNAL_ERROR,
                    "rigid provider returned inconsistent selected evidence");
            }
        } else {
            return fail(
                BG_STATUS_INTERNAL_ERROR,
                "rigid provider returned an unknown row status");
        }
    }
    return BG_STATUS_OK;
}

void commit_result(
    const BatchResult &result,
    bg_docking_rigid_refinement_output_v1 *output) noexcept {
    std::copy(result.rows.begin(), result.rows.end(), output->rows);
#define BG_COPY_RIGID_CHANNEL(source, destination)                           \
    std::copy((source).begin(), (source).end(), (destination))
    BG_COPY_RIGID_CHANNEL(result.selected_x, output->selected_x_angstrom);
    BG_COPY_RIGID_CHANNEL(result.selected_y, output->selected_y_angstrom);
    BG_COPY_RIGID_CHANNEL(result.selected_z, output->selected_z_angstrom);
    BG_COPY_RIGID_CHANNEL(
        result.comparison_v2_x, output->comparison_v2_x_angstrom);
    BG_COPY_RIGID_CHANNEL(
        result.comparison_v2_y, output->comparison_v2_y_angstrom);
    BG_COPY_RIGID_CHANNEL(
        result.comparison_v2_z, output->comparison_v2_z_angstrom);
    BG_COPY_RIGID_CHANNEL(result.baseline_v3_x, output->baseline_v3_x_angstrom);
    BG_COPY_RIGID_CHANNEL(result.baseline_v3_y, output->baseline_v3_y_angstrom);
    BG_COPY_RIGID_CHANNEL(result.baseline_v3_z, output->baseline_v3_z_angstrom);
    BG_COPY_RIGID_CHANNEL(
        result.clearance_v4_x, output->clearance_v4_x_angstrom);
    BG_COPY_RIGID_CHANNEL(
        result.clearance_v4_y, output->clearance_v4_y_angstrom);
    BG_COPY_RIGID_CHANNEL(
        result.clearance_v4_z, output->clearance_v4_z_angstrom);
#undef BG_COPY_RIGID_CHANNEL
    output->row_count = kCandidateCount;
    output->coordinate_count = result.selected_x.size();
    output->molecular_execution_authorized = UINT8_C(0);
    output->existing_rank_auto_change_authorized = UINT8_C(0);
    output->customer_pose_emission_authorized = UINT8_C(0);
    output->production_claim_authorized = UINT8_C(0);
}

}  // namespace

void destroy_provider(bg_docking_rigid_refinement *refiner) noexcept {
    if (refiner == nullptr || refiner->provider_state == nullptr) {
        return;
    }
    auto *state = static_cast<ProviderEnvelope *>(refiner->provider_state);
    if (refiner->backend == BG_BACKEND_RUST_CPU &&
        state->backend_state != nullptr) {
        bg_rust_cpu_docking_rigid_refinement_destroy(state->backend_state);
    } else if (refiner->backend == BG_BACKEND_HIP_SAFE &&
               state->backend_state != nullptr) {
#if BG_HAS_HIP_SAFE_PROVIDER
        bg_hip_safe_docking_rigid_refinement_destroy(state->backend_state);
#endif
    } else if (refiner->backend == BG_BACKEND_HIP_FAST &&
               state->backend_state != nullptr) {
#if BG_ENABLE_HIP
        bg_hip_fast_docking_rigid_refinement_destroy(state->backend_state);
#endif
    }
    delete state;
    refiner->provider_state = nullptr;
}

}  // namespace betelgeuze::native::docking::rigid_refinement

extern "C" BG_API bg_status BG_CALL
bg_docking_rigid_refinement_context_soa_v1_init(
    bg_docking_rigid_refinement_context_soa_v1 *descriptor,
    std::size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            descriptor,
            caller_struct_size,
            sizeof(*descriptor),
            caller_abi_version,
            "rigid context initializer pointer is null",
            "rigid context initializer size does not match",
            "rigid context initializer ABI version does not match");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *descriptor = bg_docking_rigid_refinement_context_soa_v1{};
        descriptor->struct_size = static_cast<uint32_t>(sizeof(*descriptor));
        descriptor->abi_version = BG_ABI_VERSION;
        descriptor->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        descriptor->pocket_radius_angstrom = 8.0;
        descriptor->v2.overlap_scale = 0.75;
        descriptor->v2.maximum_step_angstrom = 0.30;
        descriptor->v2.minimum_step_angstrom = 0.009375;
        descriptor->v2.maximum_total_translation_angstrom = 2.25;
        descriptor->v2.maximum_backtracking_evaluations = UINT64_C(6);
        descriptor->v2.penalty_tolerance = 1.0e-18;
        descriptor->v2.epsilon_angstrom = 1.0e-9;
        descriptor->v3.v2 = descriptor->v2;
        descriptor->v3.maximum_rotation_step_radians =
            betelgeuze::native::docking::rigid_refinement::kPi / 36.0;
        descriptor->v3.minimum_rotation_step_radians =
            betelgeuze::native::docking::rigid_refinement::kPi / 1152.0;
        descriptor->v3.maximum_total_rotation_radians =
            betelgeuze::native::docking::rigid_refinement::kPi / 18.0;
        descriptor->v3.maximum_rotation_steps = UINT64_C(2);
        descriptor->v3.minimum_rotation_relative_penalty_reduction = 0.01;
        descriptor->v3.maximum_centroid_offset_angstrom = 4.0;
        descriptor->clearance_v4 = descriptor->v3;
        descriptor->clearance_v4.v2.overlap_scale = 0.80;
        descriptor->clearance_v4.v2.maximum_total_translation_angstrom = 4.0;
        descriptor->clearance_v4.maximum_total_rotation_radians =
            betelgeuze::native::docking::rigid_refinement::kPi / 6.0;
        descriptor->clearance_v4.maximum_rotation_steps = UINT64_C(6);
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL
bg_docking_rigid_refinement_candidate_batch_soa_v1_init(
    bg_docking_rigid_refinement_candidate_batch_soa_v1 *batch,
    std::size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            batch,
            caller_struct_size,
            sizeof(*batch),
            caller_abi_version,
            "rigid batch initializer pointer is null",
            "rigid batch initializer size does not match",
            "rigid batch initializer ABI version does not match");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *batch = bg_docking_rigid_refinement_candidate_batch_soa_v1{};
        batch->struct_size = static_cast<uint32_t>(sizeof(*batch));
        batch->abi_version = BG_ABI_VERSION;
        batch->candidate_count = BG_DOCKING_FIXED64_CANDIDATE_COUNT;
        batch->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_docking_rigid_refinement_output_v1_init(
    bg_docking_rigid_refinement_output_v1 *output,
    std::size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            output,
            caller_struct_size,
            sizeof(*output),
            caller_abi_version,
            "rigid output initializer pointer is null",
            "rigid output initializer size does not match",
            "rigid output initializer ABI version does not match");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *output = bg_docking_rigid_refinement_output_v1{};
        output->struct_size = static_cast<uint32_t>(sizeof(*output));
        output->abi_version = BG_ABI_VERSION;
        output->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_docking_rigid_refinement_create(
    const bg_context *context,
    const bg_docking_rigid_refinement_context_soa_v1 *descriptor,
    bg_docking_rigid_refinement **out_refiner) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::docking::rigid_refinement;
    return guarded_status([&]() -> bg_status {
        if (context == nullptr || descriptor == nullptr ||
            out_refiner == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "rigid refinement create inputs and output must not be null");
        }
        if (!pointer_is_aligned(context) ||
            !pointer_is_aligned(descriptor) ||
            !pointer_is_aligned(out_refiner)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "rigid refinement create pointers are misaligned");
        }
        if (context->unit_system != descriptor->unit_system) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "rigid refinement context unit system is cross-wired");
        }
        std::unique_ptr<ProviderEnvelope> state;
        bg_status status = build_envelope(*descriptor, &state);
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = validate_create_output_range(
            *context, *descriptor, *state, out_refiner);
        if (status != BG_STATUS_OK) {
            return status;
        }
        *out_refiner = nullptr;
        if (context->backend == BG_BACKEND_RUST_CPU) {
            status = create_rust_backend(state.get());
            if (status != BG_STATUS_OK) {
                return status;
            }
        } else if (context->backend == BG_BACKEND_CPP_CPU_REFERENCE) {
            status = BG_STATUS_OK;
        } else if (context->backend == BG_BACKEND_HIP_SAFE ||
                   context->backend == BG_BACKEND_HIP_FAST) {
            status = create_hip_backend(
                state.get(),
                context->backend,
                context->device_ordinal,
                *descriptor);
            if (status != BG_STATUS_OK) {
                return status;
            }
        } else {
            return fail(
                BG_STATUS_UNSUPPORTED_BACKEND,
                "rigid refinement backend is unsupported");
        }
        auto refiner = std::make_unique<bg_docking_rigid_refinement>();
        refiner->backend = context->backend;
        refiner->device_ordinal = context->device_ordinal;
        refiner->ligand_atom_count = descriptor->ligand_atom_count;
        refiner->provider_state = state.release();
        *out_refiner = refiner.release();
        return BG_STATUS_OK;
    });
}

extern "C" BG_API void BG_CALL bg_docking_rigid_refinement_destroy(
    bg_docking_rigid_refinement *refiner) BG_NOEXCEPT {
    betelgeuze::native::docking::rigid_refinement::destroy_provider(refiner);
    delete refiner;
}

extern "C" BG_API bg_status BG_CALL bg_docking_rigid_refinement_get_backend(
    const bg_docking_rigid_refinement *refiner,
    bg_backend *backend) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::docking::rigid_refinement;
    return guarded_status([&]() -> bg_status {
        if (refiner == nullptr || backend == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "rigid refinement handle and backend output must not be null");
        }
        if (!pointer_is_aligned(refiner) || !pointer_is_aligned(backend)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "rigid refinement handle or backend output is misaligned");
        }
        if (ranges_overlap(
                refiner,
                sizeof(*refiner),
                backend,
                sizeof(*backend))) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "rigid refinement backend output overlaps its handle");
        }
        *backend = refiner->backend;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_docking_rigid_refinement_fixed64(
    const bg_context *context,
    const bg_docking_rigid_refinement *refiner,
    const bg_docking_rigid_refinement_candidate_batch_soa_v1 *candidates,
    bg_docking_rigid_refinement_output_v1 *output) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::docking::rigid_refinement;
    return guarded_status([&]() -> bg_status {
        if (context == nullptr || refiner == nullptr || candidates == nullptr ||
            output == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "rigid refinement inputs and output must not be null");
        }
        if (!pointer_is_aligned(context) || !pointer_is_aligned(refiner) ||
            !pointer_is_aligned(candidates) || !pointer_is_aligned(output)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "rigid refinement descriptors or handles are misaligned");
        }
        if (context->backend != refiner->backend ||
            context->device_ordinal != refiner->device_ordinal) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "rigid refinement handle is cross-wired to another backend or device");
        }
        std::size_t coordinate_count = 0;
        bg_status status = validate_batch_and_output(
            context, refiner, *candidates, *output, &coordinate_count);
        if (status != BG_STATUS_OK) {
            return status;
        }
        const auto *state =
            static_cast<const ProviderEnvelope *>(refiner->provider_state);
        if (state == nullptr ||
            state->ligand_radii.size() != candidates->ligand_atom_count) {
            return fail(
                BG_STATUS_INTERNAL_ERROR,
                "rigid refinement persistent state is invalid");
        }
        status = validate_total_pair_work(*state, *candidates);
        if (status != BG_STATUS_OK) {
            return status;
        }
        BatchResult result;
        if (refiner->backend == BG_BACKEND_CPP_CPU_REFERENCE) {
            result = refine_cpp_fixed64(*state, *candidates, coordinate_count);
        } else if (refiner->backend == BG_BACKEND_RUST_CPU) {
            status = refine_rust_fixed64(
                *state, *candidates, coordinate_count, &result);
            if (status != BG_STATUS_OK) {
                return status;
            }
        } else if (refiner->backend == BG_BACKEND_HIP_SAFE ||
                   refiner->backend == BG_BACKEND_HIP_FAST) {
            status = refine_hip_fixed64(
                *state,
                refiner->backend,
                *candidates,
                coordinate_count,
                &result);
            if (status != BG_STATUS_OK) {
                return status;
            }
        } else {
            return fail(
                BG_STATUS_BACKEND_UNAVAILABLE,
                "selected backend has no rigid refinement kernel; fallback is forbidden");
        }
        status = validate_result(
            result, *candidates, state->ligand_radii.size());
        if (status != BG_STATUS_OK) {
            return status;
        }
        commit_result(result, output);
        return BG_STATUS_OK;
    });
}
