#include "../internal.hpp"
#include "../rust/provider.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstring>
#include <memory>
#include <numeric>
#include <tuple>

#ifndef BG_HAS_HIP_SAFE_PROVIDER
#  define BG_HAS_HIP_SAFE_PROVIDER 0
#endif

namespace betelgeuze::native::docking::torsion_v7 {
namespace {

constexpr std::size_t kCandidateCount =
    BG_DOCKING_FIXED64_CANDIDATE_COUNT;
constexpr std::size_t kMaxMoves = BG_DOCKING_TORSION_V7_MAX_MOVES;
constexpr std::size_t kMaxLigandAtoms = 512;
constexpr std::size_t kMaxReceptorAtoms = 65'536;
constexpr std::size_t kMaxCallerSteps = 10'000;
constexpr std::size_t kMaxTotalPairEvaluations = 250'000'000;
constexpr double kPi = 3.141592653589793238462643383279502884;

struct Vec3 {
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
};

struct Config {
    double receptor_overlap_scale = 1.0;
    double internal_overlap_scale = 0.8;
    double internal_overlap_weight = 1.0;
    std::size_t maximum_baseline_v6_steps = 20;
    std::size_t maximum_torsions_evaluated = 4;
    std::size_t maximum_torsion_steps = 4;
    std::size_t maximum_backtracking_evaluations = 3;
    double maximum_torsion_step_radians = kPi / 8.0;
    double minimum_torsion_step_radians = kPi / 32.0;
    double maximum_total_torsion_path_radians = kPi / 2.0;
    double maximum_centroid_offset_angstrom = 4.0;
    double minimum_selected_final_receptor_penalty = 2.0;
    double maximum_selected_final_receptor_penalty = 4.0;
    double penalty_tolerance = 1.0e-18;
    double epsilon_angstrom = 1.0e-9;
};

struct Objective {
    double receptor = 0.0;
    double internal = 0.0;
    double combined = 0.0;
};

struct ObjectiveState {
    Objective total;
    std::vector<double> receptor_by_atom;
    std::vector<double> internal_by_pair;
};

struct ProviderEnvelope {
    std::vector<Vec3> receptor;
    std::vector<double> receptor_radii;
    std::vector<double> ligand_radii;
    Vec3 pocket_center;
    std::vector<int32_t> parents;
    std::vector<std::size_t> rotors;
    std::vector<std::pair<std::size_t, std::size_t>> internal_pairs;
    std::vector<std::vector<std::size_t>> descendants;
    std::vector<std::vector<std::size_t>> cross_internal_pair_indices;
    Config config;
    void *backend_state = nullptr;
};

struct LocalFailure {
    bg_docking_torsion_v7_failure code;
};

struct Trial {
    ObjectiveState state;
    std::size_t rotor_atom_index = 0;
    std::size_t sign_order = 0;
    double delta_radians = 0.0;
    std::vector<Vec3> coordinates;
    std::vector<double> torsion_angles;
};

struct CandidateResult {
    bg_docking_torsion_v7_row_v1 row{};
    std::array<bg_docking_torsion_v7_move_v1, kMaxMoves> moves{};
    std::vector<Vec3> optimized;
    std::vector<Vec3> final_coordinates;
    std::vector<double> optimized_angles;
    std::vector<double> final_angles;
};

struct BatchResult {
    std::array<bg_docking_torsion_v7_row_v1, kCandidateCount> rows{};
    std::array<bg_docking_torsion_v7_move_v1,
               kCandidateCount * kMaxMoves>
        moves{};
    std::vector<double> optimized_x;
    std::vector<double> optimized_y;
    std::vector<double> optimized_z;
    std::vector<double> optimized_angles;
    std::vector<double> final_x;
    std::vector<double> final_y;
    std::vector<double> final_z;
    std::vector<double> final_angles;
};

[[nodiscard]] double canonical_zero(double value) noexcept {
    return value == 0.0 ? 0.0 : value;
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

[[nodiscard]] Vec3 canonical(Vec3 value) noexcept {
    return {
        canonical_zero(value.x),
        canonical_zero(value.y),
        canonical_zero(value.z),
    };
}

[[nodiscard]] bool checked_multiply(
    std::size_t left,
    std::size_t right,
    std::size_t *output) noexcept {
    if (output == nullptr ||
        (right != 0 && left > std::numeric_limits<std::size_t>::max() / right)) {
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

[[nodiscard]] bool ranges_overlap(
    const void *left,
    std::size_t left_size,
    const void *right,
    std::size_t right_size) noexcept {
    if (left == nullptr || right == nullptr || left_size == 0 ||
        right_size == 0) {
        return false;
    }
    const auto left_begin = reinterpret_cast<std::uintptr_t>(left);
    const auto right_begin = reinterpret_cast<std::uintptr_t>(right);
    if (left_begin > std::numeric_limits<std::uintptr_t>::max() - left_size ||
        right_begin > std::numeric_limits<std::uintptr_t>::max() - right_size) {
        return true;
    }
    return left_begin < right_begin + right_size &&
           right_begin < left_begin + left_size;
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

[[nodiscard]] bool valid_config(const Config &config) noexcept {
    const std::array<double, 9> positive = {
        config.receptor_overlap_scale,
        config.internal_overlap_scale,
        config.internal_overlap_weight,
        config.maximum_torsion_step_radians,
        config.minimum_torsion_step_radians,
        config.maximum_total_torsion_path_radians,
        config.maximum_centroid_offset_angstrom,
        config.penalty_tolerance,
        config.epsilon_angstrom,
    };
    if (std::any_of(positive.begin(), positive.end(), [](double value) {
            return !std::isfinite(value) || value <= 0.0;
        })) {
        return false;
    }
    return config.receptor_overlap_scale >= 0.55 &&
           config.receptor_overlap_scale <= 1.0 &&
           config.internal_overlap_scale >= 0.55 &&
           config.internal_overlap_scale <= 1.0 &&
           config.minimum_torsion_step_radians <=
               config.maximum_torsion_step_radians &&
           config.maximum_torsion_step_radians <=
               config.maximum_total_torsion_path_radians &&
           config.maximum_total_torsion_path_radians <= kPi &&
           config.maximum_baseline_v6_steps >= 1 &&
           config.maximum_baseline_v6_steps <= 64 &&
           config.maximum_torsions_evaluated >= 1 &&
           config.maximum_torsions_evaluated <= 32 &&
           config.maximum_torsion_steps >= 1 &&
           config.maximum_torsion_steps <= kMaxMoves &&
           config.maximum_backtracking_evaluations >= 1 &&
           config.maximum_backtracking_evaluations <= 8 &&
           config.maximum_centroid_offset_angstrom >= 0.5 &&
           config.maximum_centroid_offset_angstrom <= 8.0 &&
           std::isfinite(config.minimum_selected_final_receptor_penalty) &&
           std::isfinite(config.maximum_selected_final_receptor_penalty) &&
           config.minimum_selected_final_receptor_penalty >= 0.0 &&
           config.minimum_selected_final_receptor_penalty <
               config.maximum_selected_final_receptor_penalty;
}

[[nodiscard]] bool is_descendant(
    std::size_t candidate,
    std::size_t rotor,
    const std::vector<int32_t> &parents) noexcept {
    std::size_t current = candidate;
    while (true) {
        if (current == rotor) {
            return true;
        }
        const int32_t parent = parents[current];
        if (parent < 0) {
            return false;
        }
        current = static_cast<std::size_t>(parent);
    }
}

[[nodiscard]] bg_status validate_parent_tree(
    const std::vector<int32_t> &parents) noexcept {
    std::size_t root_count = 0;
    for (std::size_t atom = 0; atom < parents.size(); ++atom) {
        const int32_t parent = parents[atom];
        if (parent < -1 ||
            (parent >= 0 && static_cast<std::size_t>(parent) >= parents.size()) ||
            parent == static_cast<int32_t>(atom)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "torsion V7 authority parent tree is invalid");
        }
        root_count += static_cast<std::size_t>(parent == -1);
    }
    if (root_count != 1) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "torsion V7 authority parent tree must have one root");
    }
    for (std::size_t atom = 0; atom < parents.size(); ++atom) {
        std::size_t current = atom;
        for (std::size_t depth = 0; depth <= parents.size(); ++depth) {
            const int32_t parent = parents[current];
            if (parent < 0) {
                break;
            }
            if (depth == parents.size()) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "torsion V7 authority parent tree contains a cycle");
            }
            current = static_cast<std::size_t>(parent);
        }
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status checked_public_count(
    uint64_t value,
    const char *message,
    std::size_t *output) noexcept {
    return checked_element_count(value, 1, message, output);
}

[[nodiscard]] bg_status build_envelope(
    const bg_docking_torsion_v7_context_soa_v1 &descriptor,
    std::unique_ptr<ProviderEnvelope> *output) {
    bg_status status = validate_descriptor_header(
        descriptor.struct_size,
        sizeof(descriptor),
        descriptor.abi_version,
        "torsion V7 context size does not match ABI v1",
        "torsion V7 context ABI version does not match");
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (output == nullptr) {
        return fail(BG_STATUS_INTERNAL_ERROR, "torsion V7 internal output is null");
    }
    status = validate_unit_system(descriptor.unit_system);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (descriptor.reserved0 != 0 || !reserved_is_zero(descriptor.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "torsion V7 context reserved fields must be zero");
    }
    std::size_t receptor_count = 0;
    std::size_t ligand_count = 0;
    std::size_t rotor_count = 0;
    std::size_t pair_count = 0;
    if (checked_public_count(
            descriptor.receptor_atom_count,
            "torsion V7 receptor count overflows",
            &receptor_count) != BG_STATUS_OK ||
        checked_public_count(
            descriptor.ligand_atom_count,
            "torsion V7 ligand count overflows",
            &ligand_count) != BG_STATUS_OK ||
        checked_public_count(
            descriptor.rotor_count,
            "torsion V7 rotor count overflows",
            &rotor_count) != BG_STATUS_OK ||
        checked_public_count(
            descriptor.internal_pair_count,
            "torsion V7 pair count overflows",
            &pair_count) != BG_STATUS_OK) {
        return BG_STATUS_CAPACITY_OVERFLOW;
    }
    if (receptor_count == 0 || receptor_count > kMaxReceptorAtoms ||
        ligand_count == 0 || ligand_count > kMaxLigandAtoms ||
        rotor_count > ligand_count) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "torsion V7 context denominator is outside native bounds");
    }
#define BG_REQUIRE_TORSION_CHANNEL(pointer, count, message)                 \
    do {                                                                   \
        status = require_channel((pointer), (count), (message));           \
        if (status != BG_STATUS_OK) {                                      \
            return status;                                                 \
        }                                                                  \
    } while (false)
    BG_REQUIRE_TORSION_CHANNEL(
        descriptor.receptor_x_angstrom,
        receptor_count,
        "torsion V7 receptor x is null or misaligned");
    BG_REQUIRE_TORSION_CHANNEL(
        descriptor.receptor_y_angstrom,
        receptor_count,
        "torsion V7 receptor y is null or misaligned");
    BG_REQUIRE_TORSION_CHANNEL(
        descriptor.receptor_z_angstrom,
        receptor_count,
        "torsion V7 receptor z is null or misaligned");
    BG_REQUIRE_TORSION_CHANNEL(
        descriptor.receptor_vdw_radius_angstrom,
        receptor_count,
        "torsion V7 receptor radii are null or misaligned");
    BG_REQUIRE_TORSION_CHANNEL(
        descriptor.ligand_vdw_radius_angstrom,
        ligand_count,
        "torsion V7 ligand radii are null or misaligned");
    BG_REQUIRE_TORSION_CHANNEL(
        descriptor.parent_atom_index,
        ligand_count,
        "torsion V7 parent tree is null or misaligned");
    BG_REQUIRE_TORSION_CHANNEL(
        descriptor.rotatable_child_atom_index,
        rotor_count,
        "torsion V7 rotor channel is null or misaligned");
    BG_REQUIRE_TORSION_CHANNEL(
        descriptor.internal_pair_atom_i,
        pair_count,
        "torsion V7 internal pair i is null or misaligned");
    BG_REQUIRE_TORSION_CHANNEL(
        descriptor.internal_pair_atom_j,
        pair_count,
        "torsion V7 internal pair j is null or misaligned");
#undef BG_REQUIRE_TORSION_CHANNEL

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
    state->parents.assign(
        descriptor.parent_atom_index,
        descriptor.parent_atom_index + ligand_count);
    state->rotors.reserve(rotor_count);
    for (std::size_t index = 0; index < rotor_count; ++index) {
        std::size_t value = 0;
        status = checked_public_count(
            descriptor.rotatable_child_atom_index[index],
            "torsion V7 rotor index overflows",
            &value);
        if (status != BG_STATUS_OK) {
            return status;
        }
        state->rotors.push_back(value);
    }
    state->internal_pairs.reserve(pair_count);
    for (std::size_t index = 0; index < pair_count; ++index) {
        std::size_t first = 0;
        std::size_t second = 0;
        status = checked_public_count(
            descriptor.internal_pair_atom_i[index],
            "torsion V7 internal pair index overflows",
            &first);
        if (status == BG_STATUS_OK) {
            status = checked_public_count(
                descriptor.internal_pair_atom_j[index],
                "torsion V7 internal pair index overflows",
                &second);
        }
        if (status != BG_STATUS_OK) {
            return status;
        }
        state->internal_pairs.emplace_back(first, second);
    }
    auto checked_config_count = [&](uint64_t value,
                                    const char *message,
                                    std::size_t *destination) -> bg_status {
        return checked_public_count(value, message, destination);
    };
    state->config.receptor_overlap_scale = descriptor.receptor_overlap_scale;
    state->config.internal_overlap_scale = descriptor.internal_overlap_scale;
    state->config.internal_overlap_weight = descriptor.internal_overlap_weight;
    if (checked_config_count(
            descriptor.maximum_baseline_v6_steps,
            "torsion V7 baseline step bound overflows",
            &state->config.maximum_baseline_v6_steps) != BG_STATUS_OK ||
        checked_config_count(
            descriptor.maximum_torsions_evaluated,
            "torsion V7 rotor bound overflows",
            &state->config.maximum_torsions_evaluated) != BG_STATUS_OK ||
        checked_config_count(
            descriptor.maximum_torsion_steps,
            "torsion V7 step bound overflows",
            &state->config.maximum_torsion_steps) != BG_STATUS_OK ||
        checked_config_count(
            descriptor.maximum_backtracking_evaluations,
            "torsion V7 backtracking bound overflows",
            &state->config.maximum_backtracking_evaluations) != BG_STATUS_OK) {
        return BG_STATUS_CAPACITY_OVERFLOW;
    }
    state->config.maximum_torsion_step_radians =
        descriptor.maximum_torsion_step_radians;
    state->config.minimum_torsion_step_radians =
        descriptor.minimum_torsion_step_radians;
    state->config.maximum_total_torsion_path_radians =
        descriptor.maximum_total_torsion_path_radians;
    state->config.maximum_centroid_offset_angstrom =
        descriptor.maximum_centroid_offset_angstrom;
    state->config.minimum_selected_final_receptor_penalty =
        descriptor.minimum_selected_final_receptor_penalty;
    state->config.maximum_selected_final_receptor_penalty =
        descriptor.maximum_selected_final_receptor_penalty;
    state->config.penalty_tolerance = descriptor.penalty_tolerance;
    state->config.epsilon_angstrom = descriptor.epsilon_angstrom;

    if (!valid_config(state->config) || !finite(state->pocket_center) ||
        std::any_of(state->receptor.begin(), state->receptor.end(), [](Vec3 value) {
            return !finite(value);
        }) ||
        std::any_of(
            state->receptor_radii.begin(),
            state->receptor_radii.end(),
            [](double value) { return !std::isfinite(value) || value <= 0.0; }) ||
        std::any_of(
            state->ligand_radii.begin(),
            state->ligand_radii.end(),
            [](double value) { return !std::isfinite(value) || value <= 0.0; })) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "torsion V7 context contains invalid configuration or values");
    }
    status = validate_parent_tree(state->parents);
    if (status != BG_STATUS_OK) {
        return status;
    }
    std::size_t previous = 0;
    bool have_previous = false;
    for (const std::size_t rotor : state->rotors) {
        if (rotor >= ligand_count || state->parents[rotor] < 0 ||
            (have_previous && previous >= rotor)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "torsion V7 authority rotor indices are not canonical");
        }
        previous = rotor;
        have_previous = true;
    }
    std::pair<std::size_t, std::size_t> previous_pair{};
    bool have_previous_pair = false;
    for (const auto &pair : state->internal_pairs) {
        if (pair.first >= pair.second || pair.second >= ligand_count ||
            (have_previous_pair && previous_pair >= pair)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "torsion V7 internal pairs are not canonical");
        }
        previous_pair = pair;
        have_previous_pair = true;
    }

    std::size_t maximum_trials = state->config.maximum_torsion_steps;
    if (!checked_multiply(
            maximum_trials,
            std::min(
                state->config.maximum_torsions_evaluated,
                state->rotors.size()),
            &maximum_trials) ||
        !checked_multiply(
            maximum_trials,
            state->config.maximum_backtracking_evaluations,
            &maximum_trials) ||
        !checked_multiply(maximum_trials, 2, &maximum_trials)) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "torsion V7 trial count overflows");
    }
    std::size_t pairs_per_objective = 0;
    if (!checked_multiply(ligand_count, receptor_count, &pairs_per_objective) ||
        !checked_add(
            pairs_per_objective,
            state->internal_pairs.size(),
            &pairs_per_objective)) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "torsion V7 pair count overflows");
    }
    std::size_t objective_count = 0;
    std::size_t maximum_pairs = 0;
    if (!checked_add(maximum_trials, 2, &objective_count) ||
        !checked_multiply(
            pairs_per_objective, objective_count, &maximum_pairs) ||
        maximum_pairs > kMaxTotalPairEvaluations) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "torsion V7 total pair budget exceeded");
    }

    state->descendants.reserve(state->rotors.size());
    state->cross_internal_pair_indices.reserve(state->rotors.size());
    for (const std::size_t rotor : state->rotors) {
        std::vector<std::size_t> descendants;
        std::vector<uint8_t> membership(ligand_count, UINT8_C(0));
        for (std::size_t atom = 0; atom < ligand_count; ++atom) {
            if (is_descendant(atom, rotor, state->parents)) {
                descendants.push_back(atom);
                membership[atom] = UINT8_C(1);
            }
        }
        std::vector<std::size_t> cross_pairs;
        for (std::size_t index = 0; index < state->internal_pairs.size();
             ++index) {
            const auto pair = state->internal_pairs[index];
            if (membership[pair.first] != membership[pair.second]) {
                cross_pairs.push_back(index);
            }
        }
        state->descendants.push_back(std::move(descendants));
        state->cross_internal_pair_indices.push_back(std::move(cross_pairs));
    }
    *output = std::move(state);
    return BG_STATUS_OK;
}

[[nodiscard]] ObjectiveState evaluate_objective(
    const ProviderEnvelope &state,
    const std::vector<Vec3> &coordinates) {
    ObjectiveState output;
    output.receptor_by_atom.reserve(coordinates.size());
    for (std::size_t ligand = 0; ligand < coordinates.size(); ++ligand) {
        double atom_penalty = 0.0;
        for (std::size_t receptor = 0; receptor < state.receptor.size();
             ++receptor) {
            const double raw_distance =
                norm(minus(coordinates[ligand], state.receptor[receptor]));
            if (!std::isfinite(raw_distance)) {
                throw LocalFailure{
                    BG_DOCKING_TORSION_V7_FAILURE_NONFINITE_DERIVED_VALUE};
            }
            const double distance =
                std::max(raw_distance, state.config.epsilon_angstrom);
            const double cutoff = state.config.receptor_overlap_scale *
                                  (state.ligand_radii[ligand] +
                                   state.receptor_radii[receptor]);
            const double overlap = std::max(cutoff - distance, 0.0);
            const double squared = overlap * overlap;
            atom_penalty += squared * squared;
        }
        if (!std::isfinite(atom_penalty)) {
            throw LocalFailure{
                BG_DOCKING_TORSION_V7_FAILURE_NONFINITE_DERIVED_VALUE};
        }
        output.receptor_by_atom.push_back(canonical_zero(atom_penalty));
    }
    output.internal_by_pair.reserve(state.internal_pairs.size());
    for (const auto &pair : state.internal_pairs) {
        const double raw_distance =
            norm(minus(coordinates[pair.first], coordinates[pair.second]));
        if (!std::isfinite(raw_distance)) {
            throw LocalFailure{
                BG_DOCKING_TORSION_V7_FAILURE_NONFINITE_DERIVED_VALUE};
        }
        const double distance =
            std::max(raw_distance, state.config.epsilon_angstrom);
        const double cutoff = state.config.internal_overlap_scale *
                              (state.ligand_radii[pair.first] +
                               state.ligand_radii[pair.second]);
        const double overlap = std::max(cutoff - distance, 0.0);
        const double squared = overlap * overlap;
        const double penalty = squared * squared;
        if (!std::isfinite(penalty)) {
            throw LocalFailure{
                BG_DOCKING_TORSION_V7_FAILURE_NONFINITE_DERIVED_VALUE};
        }
        output.internal_by_pair.push_back(canonical_zero(penalty));
    }
    output.total.receptor = canonical_zero(std::accumulate(
        output.receptor_by_atom.begin(),
        output.receptor_by_atom.end(),
        0.0));
    output.total.internal = canonical_zero(std::accumulate(
        output.internal_by_pair.begin(),
        output.internal_by_pair.end(),
        0.0));
    output.total.combined = canonical_zero(
        output.total.receptor +
        state.config.internal_overlap_weight * output.total.internal);
    if (!std::isfinite(output.total.receptor) ||
        !std::isfinite(output.total.internal) ||
        !std::isfinite(output.total.combined)) {
        throw LocalFailure{
            BG_DOCKING_TORSION_V7_FAILURE_NONFINITE_DERIVED_VALUE};
    }
    return output;
}

[[nodiscard]] double rotor_priority(
    const ProviderEnvelope &state,
    std::size_t rotor_position,
    const ObjectiveState &objective) noexcept {
    double receptor = 0.0;
    for (const std::size_t atom : state.descendants[rotor_position]) {
        receptor += objective.receptor_by_atom[atom];
    }
    double internal = 0.0;
    for (const std::size_t pair :
         state.cross_internal_pair_indices[rotor_position]) {
        internal += objective.internal_by_pair[pair];
    }
    return canonical_zero(
        receptor + state.config.internal_overlap_weight * internal);
}

[[nodiscard]] std::vector<Vec3> rotate_subtree(
    const ProviderEnvelope &state,
    const std::vector<Vec3> &coordinates,
    std::size_t rotor_position,
    double delta_radians) {
    const std::size_t rotor = state.rotors[rotor_position];
    const int32_t parent = state.parents[rotor];
    if (parent < 0) {
        throw LocalFailure{BG_DOCKING_TORSION_V7_FAILURE_INVALID_INPUT};
    }
    const Vec3 origin = coordinates[static_cast<std::size_t>(parent)];
    const Vec3 axis_vector = minus(coordinates[rotor], origin);
    const double axis_norm = norm(axis_vector);
    if (!std::isfinite(axis_norm) ||
        axis_norm <= state.config.epsilon_angstrom) {
        throw LocalFailure{BG_DOCKING_TORSION_V7_FAILURE_DEGENERATE_ROTOR};
    }
    const Vec3 axis = scale(axis_vector, 1.0 / axis_norm);
    const double cosine = std::cos(delta_radians);
    const double sine = std::sin(delta_radians);
    std::vector<Vec3> output = coordinates;
    for (const std::size_t atom : state.descendants[rotor_position]) {
        const Vec3 vector = minus(coordinates[atom], origin);
        const Vec3 rotated = plus(
            plus(
                scale(vector, cosine),
                scale(cross(axis, vector), sine)),
            plus(
                scale(axis, dot(axis, vector) * (1.0 - cosine)),
                origin));
        if (!finite(rotated)) {
            throw LocalFailure{
                BG_DOCKING_TORSION_V7_FAILURE_NONFINITE_DERIVED_VALUE};
        }
        output[atom] = canonical(rotated);
    }
    return output;
}

[[nodiscard]] Vec3 centroid(const std::vector<Vec3> &coordinates) noexcept {
    Vec3 total{};
    for (const Vec3 coordinate : coordinates) {
        total = plus(total, coordinate);
    }
    return canonical(scale(total, 1.0 / static_cast<double>(coordinates.size())));
}

[[nodiscard]] double normalized_angle(double value) noexcept {
    return canonical_zero(std::atan2(std::sin(value), std::cos(value)));
}

[[nodiscard]] bool trial_less(const Trial &left, const Trial &right) noexcept {
    return std::tie(
               left.state.total.combined,
               left.state.total.receptor,
               left.state.total.internal,
               left.rotor_atom_index,
               left.sign_order) <
           std::tie(
               right.state.total.combined,
               right.state.total.receptor,
               right.state.total.internal,
               right.rotor_atom_index,
               right.sign_order);
}

[[nodiscard]] bg_docking_torsion_v7_row_v1 failure_row(
    std::size_t slot,
    bg_docking_torsion_v7_failure failure) noexcept {
    bg_docking_torsion_v7_row_v1 row{};
    row.slot_index = static_cast<uint32_t>(slot);
    row.status = BG_DOCKING_TORSION_V7_ROW_TYPED_FAILURE;
    row.failure_code = failure;
    return row;
}

[[nodiscard]] bg_docking_torsion_v7_move_v1 empty_move(
    std::size_t slot,
    std::size_t index) noexcept {
    bg_docking_torsion_v7_move_v1 move{};
    move.slot_index = static_cast<uint32_t>(slot);
    move.move_index = static_cast<uint32_t>(index);
    return move;
}

[[nodiscard]] CandidateResult evaluate_candidate(
    const ProviderEnvelope &state,
    std::size_t slot,
    const std::vector<Vec3> &source,
    const std::vector<Vec3> &baseline,
    const std::vector<double> &baseline_angles,
    bool eligible,
    std::size_t maximum_steps,
    std::size_t baseline_accepted_steps) {
    const Config &config = state.config;
    if (source.size() != state.ligand_radii.size() ||
        baseline.size() != state.ligand_radii.size() ||
        baseline_angles.size() != state.ligand_radii.size() ||
        maximum_steps > kMaxCallerSteps ||
        baseline_accepted_steps > maximum_steps ||
        baseline_accepted_steps > config.maximum_baseline_v6_steps ||
        std::any_of(source.begin(), source.end(), [](Vec3 value) {
            return !finite(value);
        }) ||
        std::any_of(baseline.begin(), baseline.end(), [](Vec3 value) {
            return !finite(value);
        }) ||
        std::any_of(
            baseline_angles.begin(),
            baseline_angles.end(),
            [](double value) { return !std::isfinite(value); })) {
        throw LocalFailure{BG_DOCKING_TORSION_V7_FAILURE_INVALID_INPUT};
    }
    const ObjectiveState source_state = evaluate_objective(state, source);
    const ObjectiveState baseline_state = evaluate_objective(state, baseline);
    ObjectiveState current_state = baseline_state;
    std::vector<Vec3> coordinates = baseline;
    std::vector<double> torsion_angles = baseline_angles;
    std::array<bg_docking_torsion_v7_move_v1, kMaxMoves> evaluated_moves{};
    for (std::size_t index = 0; index < kMaxMoves; ++index) {
        evaluated_moves[index] = empty_move(slot, index);
    }
    std::size_t evaluated_move_count = 0;
    std::size_t trial_evaluation_count = 0;
    double total_path = 0.0;
    const std::size_t remaining_steps =
        maximum_steps >= baseline_accepted_steps
            ? maximum_steps - baseline_accepted_steps
            : 0;
    const std::size_t torsion_step_budget =
        std::min(config.maximum_torsion_steps, remaining_steps);
    const double reachable_bound =
        baseline_state.total.receptor +
        static_cast<double>(torsion_step_budget) * config.penalty_tolerance;
    if (!std::isfinite(reachable_bound)) {
        throw LocalFailure{
            BG_DOCKING_TORSION_V7_FAILURE_NONFINITE_DERIVED_VALUE};
    }
    const bool selection_window_reachable =
        reachable_bound >= config.minimum_selected_final_receptor_penalty;
    bg_docking_torsion_v7_skip_reason skip =
        BG_DOCKING_TORSION_V7_SKIP_NONE;
    if (!eligible) {
        skip = BG_DOCKING_TORSION_V7_SKIP_NOT_ELIGIBLE;
    } else if (state.rotors.empty()) {
        skip = BG_DOCKING_TORSION_V7_SKIP_NO_AUTHORITY_ROTOR;
    } else if (torsion_step_budget == 0) {
        skip = BG_DOCKING_TORSION_V7_SKIP_NO_REMAINING_STEP_BUDGET;
    } else if (current_state.total.combined <= config.penalty_tolerance) {
        skip = BG_DOCKING_TORSION_V7_SKIP_OBJECTIVE_AT_OR_BELOW_TOLERANCE;
    } else if (!selection_window_reachable) {
        skip = BG_DOCKING_TORSION_V7_SKIP_SELECTION_WINDOW_UNREACHABLE;
    }
    const bool torsion_evaluated = skip == BG_DOCKING_TORSION_V7_SKIP_NONE;
    bool stopped_after_window_unreachable = false;

    for (std::size_t iteration = 0;
         torsion_evaluated && iteration < torsion_step_budget;
         ++iteration) {
        struct Priority {
            double value;
            std::size_t position;
            std::size_t atom;
        };
        std::vector<Priority> priorities;
        priorities.reserve(state.rotors.size());
        for (std::size_t position = 0; position < state.rotors.size();
             ++position) {
            priorities.push_back({
                rotor_priority(state, position, current_state),
                position,
                state.rotors[position],
            });
        }
        std::sort(
            priorities.begin(),
            priorities.end(),
            [](const Priority &left, const Priority &right) {
                if (left.value != right.value) {
                    return left.value > right.value;
                }
                return left.atom < right.atom;
            });
        if (priorities.size() > config.maximum_torsions_evaluated) {
            priorities.resize(config.maximum_torsions_evaluated);
        }

        std::unique_ptr<Trial> best;
        double step = config.maximum_torsion_step_radians;
        for (std::size_t backtrack = 0;
             backtrack < config.maximum_backtracking_evaluations;
             ++backtrack) {
            if (step + config.penalty_tolerance <
                config.minimum_torsion_step_radians) {
                break;
            }
            if (total_path + step >
                config.maximum_total_torsion_path_radians +
                    config.penalty_tolerance) {
                step *= 0.5;
                continue;
            }
            for (const Priority priority : priorities) {
                for (std::size_t sign_order = 0; sign_order < 2;
                     ++sign_order) {
                    const double delta =
                        (sign_order == 0 ? -1.0 : 1.0) * step;
                    std::vector<Vec3> candidate_coordinates = rotate_subtree(
                        state, coordinates, priority.position, delta);
                    const double centroid_offset = norm(minus(
                        centroid(candidate_coordinates), state.pocket_center));
                    if (!std::isfinite(centroid_offset)) {
                        throw LocalFailure{
                            BG_DOCKING_TORSION_V7_FAILURE_NONFINITE_DERIVED_VALUE};
                    }
                    if (centroid_offset >
                        config.maximum_centroid_offset_angstrom +
                            config.penalty_tolerance) {
                        continue;
                    }
                    ObjectiveState candidate_state =
                        evaluate_objective(state, candidate_coordinates);
                    ++trial_evaluation_count;
                    if (candidate_state.total.receptor >
                            current_state.total.receptor +
                                config.penalty_tolerance ||
                        candidate_state.total.combined >=
                            current_state.total.combined -
                                config.penalty_tolerance) {
                        continue;
                    }
                    std::vector<double> candidate_angles = torsion_angles;
                    candidate_angles[priority.atom] = normalized_angle(
                        candidate_angles[priority.atom] + delta);
                    auto candidate = std::make_unique<Trial>();
                    candidate->state = std::move(candidate_state);
                    candidate->rotor_atom_index = priority.atom;
                    candidate->sign_order = sign_order;
                    candidate->delta_radians = delta;
                    candidate->coordinates = std::move(candidate_coordinates);
                    candidate->torsion_angles = std::move(candidate_angles);
                    if (best == nullptr || trial_less(*candidate, *best)) {
                        best = std::move(candidate);
                    }
                }
            }
            if (best != nullptr) {
                break;
            }
            step *= 0.5;
        }
        if (best == nullptr) {
            break;
        }
        total_path += std::abs(best->delta_radians);
        if (!std::isfinite(total_path)) {
            throw LocalFailure{
                BG_DOCKING_TORSION_V7_FAILURE_NONFINITE_DERIVED_VALUE};
        }
        bg_docking_torsion_v7_move_v1 &movement =
            evaluated_moves[evaluated_move_count];
        movement.evaluated = UINT8_C(1);
        movement.rotatable_child_atom_index =
            static_cast<uint64_t>(best->rotor_atom_index);
        movement.delta_radians = canonical_zero(best->delta_radians);
        movement.receptor_penalty = best->state.total.receptor;
        movement.internal_penalty = best->state.total.internal;
        movement.combined_penalty = best->state.total.combined;
        ++evaluated_move_count;
        coordinates = std::move(best->coordinates);
        torsion_angles = std::move(best->torsion_angles);
        current_state = std::move(best->state);
        const std::size_t remaining_torsion_steps =
            torsion_step_budget - evaluated_move_count;
        const double remaining_reachable_bound =
            current_state.total.receptor +
            static_cast<double>(remaining_torsion_steps) *
                config.penalty_tolerance;
        if (!std::isfinite(remaining_reachable_bound)) {
            throw LocalFailure{
                BG_DOCKING_TORSION_V7_FAILURE_NONFINITE_DERIVED_VALUE};
        }
        if (remaining_reachable_bound <
            config.minimum_selected_final_receptor_penalty) {
            stopped_after_window_unreachable = true;
            break;
        }
    }

    const bool variant_available = evaluated_move_count != 0;
    const bool selected =
        variant_available &&
        config.minimum_selected_final_receptor_penalty <=
            current_state.total.receptor &&
        current_state.total.receptor <
            config.maximum_selected_final_receptor_penalty;
    const std::vector<Vec3> &final_coordinates = selected ? coordinates : baseline;
    const std::vector<double> &final_angles =
        selected ? torsion_angles : baseline_angles;
    const Objective final_objective =
        selected ? current_state.total : baseline_state.total;
    const auto selection =
        selected
            ? BG_DOCKING_TORSION_V7_SELECTION_FINAL_PENALTY_WINDOW
            : (variant_available
                   ? BG_DOCKING_TORSION_V7_SELECTION_V6_RETAINED_OUTSIDE_WINDOW
                   : BG_DOCKING_TORSION_V7_SELECTION_V6_RETAINED_NO_REDUCTION);
    for (std::size_t index = 0; index < evaluated_move_count; ++index) {
        evaluated_moves[index].selected = static_cast<uint8_t>(selected);
    }
    CandidateResult result;
    result.row.slot_index = static_cast<uint32_t>(slot);
    result.row.status = BG_DOCKING_TORSION_V7_ROW_REFINED;
    result.row.failure_code = BG_DOCKING_TORSION_V7_FAILURE_NONE;
    result.row.skip_reason = skip;
    result.row.selection_reason = selection;
    result.row.selection_window_reachable =
        static_cast<uint8_t>(selection_window_reachable);
    result.row.evaluation_stopped_after_selection_window_became_unreachable =
        static_cast<uint8_t>(stopped_after_window_unreachable);
    result.row.torsion_evaluated = static_cast<uint8_t>(torsion_evaluated);
    result.row.torsion_variant_available =
        static_cast<uint8_t>(variant_available);
    result.row.torsion_selected = static_cast<uint8_t>(selected);
    result.row.torsion_step_budget =
        static_cast<uint64_t>(torsion_step_budget);
    result.row.fixed_objective_evaluation_count = UINT64_C(2);
    result.row.torsion_trial_objective_evaluation_count =
        static_cast<uint64_t>(trial_evaluation_count);
    result.row.evaluated_torsion_steps =
        static_cast<uint64_t>(evaluated_move_count);
    result.row.accepted_torsion_steps =
        selected ? static_cast<uint64_t>(evaluated_move_count) : UINT64_C(0);
    result.row.baseline_v6_accepted_steps =
        static_cast<uint64_t>(baseline_accepted_steps);
    result.row.source_receptor_penalty = source_state.total.receptor;
    result.row.source_internal_penalty = source_state.total.internal;
    result.row.source_combined_penalty = source_state.total.combined;
    result.row.baseline_receptor_penalty = baseline_state.total.receptor;
    result.row.baseline_internal_penalty = baseline_state.total.internal;
    result.row.baseline_combined_penalty = baseline_state.total.combined;
    result.row.optimized_receptor_penalty = current_state.total.receptor;
    result.row.optimized_internal_penalty = current_state.total.internal;
    result.row.optimized_combined_penalty = current_state.total.combined;
    result.row.final_receptor_penalty = final_objective.receptor;
    result.row.final_internal_penalty = final_objective.internal;
    result.row.final_combined_penalty = final_objective.combined;
    result.row.evaluated_total_torsion_path_radians =
        canonical_zero(total_path);
    result.row.accepted_total_torsion_path_radians =
        selected ? canonical_zero(total_path) : 0.0;
    result.moves = evaluated_moves;
    result.final_coordinates = final_coordinates;
    result.final_angles = final_angles;
    result.optimized = std::move(coordinates);
    result.optimized_angles = std::move(torsion_angles);
    return result;
}

[[nodiscard]] bg_status validate_batch_and_output(
    const bg_docking_torsion_v7 *refiner,
    const bg_docking_torsion_v7_candidate_batch_soa_v1 &candidates,
    const bg_docking_torsion_v7_output_v1 &output,
    std::size_t *coordinate_count) noexcept {
    bg_status status = validate_descriptor_header(
        candidates.struct_size,
        sizeof(candidates),
        candidates.abi_version,
        "torsion V7 batch size does not match ABI v1",
        "torsion V7 batch ABI version does not match");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = validate_descriptor_header(
        output.struct_size,
        sizeof(output),
        output.abi_version,
        "torsion V7 output size does not match ABI v1",
        "torsion V7 output ABI version does not match");
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (refiner == nullptr || coordinate_count == nullptr) {
        return fail(BG_STATUS_INVALID_ARGUMENT, "torsion V7 handle is null");
    }
    if (validate_unit_system(candidates.unit_system) != BG_STATUS_OK ||
        validate_unit_system(output.unit_system) != BG_STATUS_OK) {
        return BG_STATUS_INVALID_ARGUMENT;
    }
    if (candidates.reserved0 != 0 ||
        !reserved_is_zero(candidates.reserved) || output.reserved0 != 0 ||
        output.reserved1 != 0 || !reserved_is_zero(output.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "torsion V7 batch or output reserved fields must be zero");
    }
    if (candidates.candidate_count != kCandidateCount ||
        candidates.ligand_atom_count != refiner->ligand_atom_count ||
        candidates.ligand_atom_count == 0 ||
        candidates.ligand_atom_count > kMaxLigandAtoms) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "torsion V7 fixed64 or ligand denominator is cross-wired");
    }
    std::size_t ligand_count = 0;
    status = checked_public_count(
        candidates.ligand_atom_count,
        "torsion V7 ligand denominator overflows",
        &ligand_count);
    if (status != BG_STATUS_OK ||
        !checked_multiply(kCandidateCount, ligand_count, coordinate_count)) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "torsion V7 coordinate denominator overflows");
    }
    const std::size_t move_count = kCandidateCount * kMaxMoves;
    if (output.row_capacity < kCandidateCount ||
        output.move_capacity < move_count ||
        output.coordinate_capacity < *coordinate_count || output.rows == nullptr ||
        output.moves == nullptr || output.optimized_x_angstrom == nullptr ||
        output.optimized_y_angstrom == nullptr ||
        output.optimized_z_angstrom == nullptr ||
        output.optimized_torsion_angles_radians == nullptr ||
        output.final_x_angstrom == nullptr || output.final_y_angstrom == nullptr ||
        output.final_z_angstrom == nullptr ||
        output.final_torsion_angles_radians == nullptr ||
        !pointer_is_aligned(output.rows) || !pointer_is_aligned(output.moves) ||
        !pointer_is_aligned(output.optimized_x_angstrom) ||
        !pointer_is_aligned(output.optimized_y_angstrom) ||
        !pointer_is_aligned(output.optimized_z_angstrom) ||
        !pointer_is_aligned(output.optimized_torsion_angles_radians) ||
        !pointer_is_aligned(output.final_x_angstrom) ||
        !pointer_is_aligned(output.final_y_angstrom) ||
        !pointer_is_aligned(output.final_z_angstrom) ||
        !pointer_is_aligned(output.final_torsion_angles_radians)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "torsion V7 output capacity or channel is invalid");
    }
#define BG_REQUIRE_BATCH_CHANNEL(pointer, count, message)                   \
    do {                                                                   \
        status = require_channel((pointer), (count), (message));           \
        if (status != BG_STATUS_OK) {                                      \
            return status;                                                 \
        }                                                                  \
    } while (false)
    BG_REQUIRE_BATCH_CHANNEL(
        candidates.candidate_state,
        kCandidateCount,
        "torsion V7 candidate-state channel is null or misaligned");
    BG_REQUIRE_BATCH_CHANNEL(
        candidates.proposal_is_torsion_eligible,
        kCandidateCount,
        "torsion V7 eligibility channel is null or misaligned");
    BG_REQUIRE_BATCH_CHANNEL(
        candidates.max_steps,
        kCandidateCount,
        "torsion V7 max-step channel is null or misaligned");
    BG_REQUIRE_BATCH_CHANNEL(
        candidates.baseline_v6_accepted_steps,
        kCandidateCount,
        "torsion V7 baseline-step channel is null or misaligned");
    BG_REQUIRE_BATCH_CHANNEL(
        candidates.source_x_angstrom,
        *coordinate_count,
        "torsion V7 source x is null or misaligned");
    BG_REQUIRE_BATCH_CHANNEL(
        candidates.source_y_angstrom,
        *coordinate_count,
        "torsion V7 source y is null or misaligned");
    BG_REQUIRE_BATCH_CHANNEL(
        candidates.source_z_angstrom,
        *coordinate_count,
        "torsion V7 source z is null or misaligned");
    BG_REQUIRE_BATCH_CHANNEL(
        candidates.baseline_v6_x_angstrom,
        *coordinate_count,
        "torsion V7 baseline x is null or misaligned");
    BG_REQUIRE_BATCH_CHANNEL(
        candidates.baseline_v6_y_angstrom,
        *coordinate_count,
        "torsion V7 baseline y is null or misaligned");
    BG_REQUIRE_BATCH_CHANNEL(
        candidates.baseline_v6_z_angstrom,
        *coordinate_count,
        "torsion V7 baseline z is null or misaligned");
    BG_REQUIRE_BATCH_CHANNEL(
        candidates.baseline_v6_torsion_angles_radians,
        *coordinate_count,
        "torsion V7 baseline angles are null or misaligned");
#undef BG_REQUIRE_BATCH_CHANNEL
    for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
        if (candidates.candidate_state[slot] !=
                BG_DOCKING_TORSION_V7_CANDIDATE_INACTIVE &&
            candidates.candidate_state[slot] !=
                BG_DOCKING_TORSION_V7_CANDIDATE_REFINE) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "torsion V7 candidate state is not frozen inactive/refine");
        }
    }

    const std::array<std::pair<const void *, std::size_t>, 11> inputs = {{
        {candidates.candidate_state,
         kCandidateCount * sizeof(*candidates.candidate_state)},
        {candidates.proposal_is_torsion_eligible,
         kCandidateCount * sizeof(*candidates.proposal_is_torsion_eligible)},
        {candidates.max_steps, kCandidateCount * sizeof(*candidates.max_steps)},
        {candidates.baseline_v6_accepted_steps,
         kCandidateCount * sizeof(*candidates.baseline_v6_accepted_steps)},
        {candidates.source_x_angstrom,
         *coordinate_count * sizeof(*candidates.source_x_angstrom)},
        {candidates.source_y_angstrom,
         *coordinate_count * sizeof(*candidates.source_y_angstrom)},
        {candidates.source_z_angstrom,
         *coordinate_count * sizeof(*candidates.source_z_angstrom)},
        {candidates.baseline_v6_x_angstrom,
         *coordinate_count * sizeof(*candidates.baseline_v6_x_angstrom)},
        {candidates.baseline_v6_y_angstrom,
         *coordinate_count * sizeof(*candidates.baseline_v6_y_angstrom)},
        {candidates.baseline_v6_z_angstrom,
         *coordinate_count * sizeof(*candidates.baseline_v6_z_angstrom)},
        {candidates.baseline_v6_torsion_angles_radians,
         *coordinate_count *
             sizeof(*candidates.baseline_v6_torsion_angles_radians)},
    }};
    const std::array<std::pair<const void *, std::size_t>, 10> outputs = {{
        {output.rows, kCandidateCount * sizeof(*output.rows)},
        {output.moves, move_count * sizeof(*output.moves)},
        {output.optimized_x_angstrom,
         *coordinate_count * sizeof(*output.optimized_x_angstrom)},
        {output.optimized_y_angstrom,
         *coordinate_count * sizeof(*output.optimized_y_angstrom)},
        {output.optimized_z_angstrom,
         *coordinate_count * sizeof(*output.optimized_z_angstrom)},
        {output.optimized_torsion_angles_radians,
         *coordinate_count * sizeof(*output.optimized_torsion_angles_radians)},
        {output.final_x_angstrom,
         *coordinate_count * sizeof(*output.final_x_angstrom)},
        {output.final_y_angstrom,
         *coordinate_count * sizeof(*output.final_y_angstrom)},
        {output.final_z_angstrom,
         *coordinate_count * sizeof(*output.final_z_angstrom)},
        {output.final_torsion_angles_radians,
         *coordinate_count * sizeof(*output.final_torsion_angles_radians)},
    }};
    for (std::size_t first = 0; first < outputs.size(); ++first) {
        for (std::size_t second = first + 1; second < outputs.size();
             ++second) {
            if (ranges_overlap(
                    outputs[first].first,
                    outputs[first].second,
                    outputs[second].first,
                    outputs[second].second)) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "torsion V7 output buffers overlap");
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
                    "torsion V7 input and output buffers overlap");
            }
        }
    }
    return BG_STATUS_OK;
}

[[nodiscard]] BatchResult make_empty_batch_result(std::size_t coordinate_count) {
    BatchResult result;
    result.optimized_x.assign(coordinate_count, 0.0);
    result.optimized_y.assign(coordinate_count, 0.0);
    result.optimized_z.assign(coordinate_count, 0.0);
    result.optimized_angles.assign(coordinate_count, 0.0);
    result.final_x.assign(coordinate_count, 0.0);
    result.final_y.assign(coordinate_count, 0.0);
    result.final_z.assign(coordinate_count, 0.0);
    result.final_angles.assign(coordinate_count, 0.0);
    for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
        result.rows[slot] = failure_row(
            slot,
            BG_DOCKING_TORSION_V7_FAILURE_UPSTREAM_NOT_ELIGIBLE);
        for (std::size_t move = 0; move < kMaxMoves; ++move) {
            result.moves[slot * kMaxMoves + move] = empty_move(slot, move);
        }
    }
    return result;
}

[[nodiscard]] std::vector<Vec3> coordinates_from_batch(
    const double *x,
    const double *y,
    const double *z,
    std::size_t start,
    std::size_t atom_count) {
    std::vector<Vec3> result;
    result.reserve(atom_count);
    for (std::size_t atom = 0; atom < atom_count; ++atom) {
        const std::size_t index = start + atom;
        result.push_back({x[index], y[index], z[index]});
    }
    return result;
}

[[nodiscard]] BatchResult refine_cpp_fixed64(
    const ProviderEnvelope &state,
    const bg_docking_torsion_v7_candidate_batch_soa_v1 &candidates,
    std::size_t coordinate_count) {
    const std::size_t ligand_count = state.ligand_radii.size();
    BatchResult result = make_empty_batch_result(coordinate_count);
    for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
        if (candidates.candidate_state[slot] ==
            BG_DOCKING_TORSION_V7_CANDIDATE_INACTIVE) {
            continue;
        }
        if (candidates.proposal_is_torsion_eligible[slot] > UINT8_C(1)) {
            result.rows[slot] = failure_row(
                slot, BG_DOCKING_TORSION_V7_FAILURE_INVALID_INPUT);
            continue;
        }
        if constexpr (sizeof(std::size_t) < sizeof(uint64_t)) {
            if (candidates.max_steps[slot] >
                    static_cast<uint64_t>(
                        std::numeric_limits<std::size_t>::max()) ||
                candidates.baseline_v6_accepted_steps[slot] >
                    static_cast<uint64_t>(
                        std::numeric_limits<std::size_t>::max())) {
                result.rows[slot] = failure_row(
                    slot, BG_DOCKING_TORSION_V7_FAILURE_INVALID_INPUT);
                continue;
            }
        }
        const std::size_t maximum_steps =
            static_cast<std::size_t>(candidates.max_steps[slot]);
        const std::size_t baseline_steps = static_cast<std::size_t>(
            candidates.baseline_v6_accepted_steps[slot]);
        const std::size_t start = slot * ligand_count;
        try {
            CandidateResult candidate = evaluate_candidate(
                state,
                slot,
                coordinates_from_batch(
                    candidates.source_x_angstrom,
                    candidates.source_y_angstrom,
                    candidates.source_z_angstrom,
                    start,
                    ligand_count),
                coordinates_from_batch(
                    candidates.baseline_v6_x_angstrom,
                    candidates.baseline_v6_y_angstrom,
                    candidates.baseline_v6_z_angstrom,
                    start,
                    ligand_count),
                std::vector<double>(
                    candidates.baseline_v6_torsion_angles_radians + start,
                    candidates.baseline_v6_torsion_angles_radians + start +
                        ligand_count),
                candidates.proposal_is_torsion_eligible[slot] == UINT8_C(1),
                maximum_steps,
                baseline_steps);
            result.rows[slot] = candidate.row;
            std::copy(
                candidate.moves.begin(),
                candidate.moves.end(),
                result.moves.begin() +
                    static_cast<std::ptrdiff_t>(slot * kMaxMoves));
            for (std::size_t atom = 0; atom < ligand_count; ++atom) {
                const std::size_t destination = start + atom;
                result.optimized_x[destination] = candidate.optimized[atom].x;
                result.optimized_y[destination] = candidate.optimized[atom].y;
                result.optimized_z[destination] = candidate.optimized[atom].z;
                result.optimized_angles[destination] =
                    candidate.optimized_angles[atom];
                result.final_x[destination] = candidate.final_coordinates[atom].x;
                result.final_y[destination] = candidate.final_coordinates[atom].y;
                result.final_z[destination] = candidate.final_coordinates[atom].z;
                result.final_angles[destination] = candidate.final_angles[atom];
            }
        } catch (const LocalFailure &failure) {
            result.rows[slot] = failure_row(slot, failure.code);
        }
    }
    return result;
}

void initialize_rust_error(bg_rust_cpu_error_v1 *error) noexcept {
    *error = bg_rust_cpu_error_v1{};
    error->struct_size = static_cast<uint32_t>(sizeof(*error));
    error->abi_version = BG_RUST_CPU_PROVIDER_ABI_VERSION;
}

[[nodiscard]] bg_status rust_failure(
    int32_t raw_status,
    const bg_rust_cpu_error_v1 &error,
    const char *fallback) noexcept {
    const char *message = error.message[0] == UINT8_C(0)
                              ? fallback
                              : reinterpret_cast<const char *>(error.message);
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

[[nodiscard]] bg_status create_rust_backend(ProviderEnvelope *state) {
    std::vector<double> receptor_x;
    std::vector<double> receptor_y;
    std::vector<double> receptor_z;
    receptor_x.reserve(state->receptor.size());
    receptor_y.reserve(state->receptor.size());
    receptor_z.reserve(state->receptor.size());
    for (const Vec3 coordinate : state->receptor) {
        receptor_x.push_back(coordinate.x);
        receptor_y.push_back(coordinate.y);
        receptor_z.push_back(coordinate.z);
    }
    std::vector<std::size_t> pair_i;
    std::vector<std::size_t> pair_j;
    pair_i.reserve(state->internal_pairs.size());
    pair_j.reserve(state->internal_pairs.size());
    for (const auto &pair : state->internal_pairs) {
        pair_i.push_back(pair.first);
        pair_j.push_back(pair.second);
    }
    bg_rust_cpu_torsion_v7_context_v1 descriptor{};
    descriptor.struct_size = static_cast<uint32_t>(sizeof(descriptor));
    descriptor.abi_version = BG_RUST_CPU_PROVIDER_ABI_VERSION;
    descriptor.receptor_atom_count = state->receptor.size();
    descriptor.ligand_atom_count = state->ligand_radii.size();
    descriptor.rotor_count = state->rotors.size();
    descriptor.internal_pair_count = state->internal_pairs.size();
    descriptor.receptor_x_angstrom = receptor_x.data();
    descriptor.receptor_y_angstrom = receptor_y.data();
    descriptor.receptor_z_angstrom = receptor_z.data();
    descriptor.receptor_vdw_radius_angstrom = state->receptor_radii.data();
    descriptor.ligand_vdw_radius_angstrom = state->ligand_radii.data();
    descriptor.pocket_center_angstrom[0] = state->pocket_center.x;
    descriptor.pocket_center_angstrom[1] = state->pocket_center.y;
    descriptor.pocket_center_angstrom[2] = state->pocket_center.z;
    descriptor.parent_atom_index = state->parents.data();
    descriptor.rotatable_child_atom_index = state->rotors.data();
    descriptor.internal_pair_atom_i = pair_i.data();
    descriptor.internal_pair_atom_j = pair_j.data();
    descriptor.receptor_overlap_scale = state->config.receptor_overlap_scale;
    descriptor.internal_overlap_scale = state->config.internal_overlap_scale;
    descriptor.internal_overlap_weight = state->config.internal_overlap_weight;
    descriptor.maximum_baseline_v6_steps =
        state->config.maximum_baseline_v6_steps;
    descriptor.maximum_torsions_evaluated =
        state->config.maximum_torsions_evaluated;
    descriptor.maximum_torsion_steps = state->config.maximum_torsion_steps;
    descriptor.maximum_backtracking_evaluations =
        state->config.maximum_backtracking_evaluations;
    descriptor.maximum_torsion_step_radians =
        state->config.maximum_torsion_step_radians;
    descriptor.minimum_torsion_step_radians =
        state->config.minimum_torsion_step_radians;
    descriptor.maximum_total_torsion_path_radians =
        state->config.maximum_total_torsion_path_radians;
    descriptor.maximum_centroid_offset_angstrom =
        state->config.maximum_centroid_offset_angstrom;
    descriptor.minimum_selected_final_receptor_penalty =
        state->config.minimum_selected_final_receptor_penalty;
    descriptor.maximum_selected_final_receptor_penalty =
        state->config.maximum_selected_final_receptor_penalty;
    descriptor.penalty_tolerance = state->config.penalty_tolerance;
    descriptor.epsilon_angstrom = state->config.epsilon_angstrom;
    bg_rust_cpu_error_v1 error{};
    initialize_rust_error(&error);
    void *provider_state = nullptr;
    const int32_t raw_status = bg_rust_cpu_docking_torsion_v7_create(
        &descriptor, &provider_state, &error);
    if (raw_status != BG_STATUS_OK) {
        return rust_failure(
            raw_status, error, "rust_cpu torsion V7 creation failed");
    }
    state->backend_state = provider_state;
    return BG_STATUS_OK;
}

[[nodiscard]] bg_docking_torsion_v7_row_v1 public_row(
    const bg_rust_cpu_torsion_v7_row_v1 &source) noexcept {
    bg_docking_torsion_v7_row_v1 row{};
    row.slot_index = source.slot_index;
    row.status = source.status;
    row.failure_code = source.failure_code;
    row.skip_reason = source.skip_reason;
    row.selection_reason = source.selection_reason;
    row.selection_window_reachable = source.selection_window_reachable;
    row.evaluation_stopped_after_selection_window_became_unreachable =
        source.evaluation_stopped_after_selection_window_became_unreachable;
    row.torsion_evaluated = source.torsion_evaluated;
    row.torsion_variant_available = source.torsion_variant_available;
    row.torsion_selected = source.torsion_selected;
    row.torsion_step_budget = static_cast<uint64_t>(source.torsion_step_budget);
    row.fixed_objective_evaluation_count =
        static_cast<uint64_t>(source.fixed_objective_evaluation_count);
    row.torsion_trial_objective_evaluation_count =
        static_cast<uint64_t>(source.torsion_trial_objective_evaluation_count);
    row.evaluated_torsion_steps =
        static_cast<uint64_t>(source.evaluated_torsion_steps);
    row.accepted_torsion_steps =
        static_cast<uint64_t>(source.accepted_torsion_steps);
    row.baseline_v6_accepted_steps =
        static_cast<uint64_t>(source.baseline_v6_accepted_steps);
    row.source_receptor_penalty = source.source_receptor_penalty;
    row.source_internal_penalty = source.source_internal_penalty;
    row.source_combined_penalty = source.source_combined_penalty;
    row.baseline_receptor_penalty = source.baseline_receptor_penalty;
    row.baseline_internal_penalty = source.baseline_internal_penalty;
    row.baseline_combined_penalty = source.baseline_combined_penalty;
    row.optimized_receptor_penalty = source.optimized_receptor_penalty;
    row.optimized_internal_penalty = source.optimized_internal_penalty;
    row.optimized_combined_penalty = source.optimized_combined_penalty;
    row.final_receptor_penalty = source.final_receptor_penalty;
    row.final_internal_penalty = source.final_internal_penalty;
    row.final_combined_penalty = source.final_combined_penalty;
    row.evaluated_total_torsion_path_radians =
        source.evaluated_total_torsion_path_radians;
    row.accepted_total_torsion_path_radians =
        source.accepted_total_torsion_path_radians;
    return row;
}

[[nodiscard]] bg_docking_torsion_v7_move_v1 public_move(
    const bg_rust_cpu_torsion_v7_move_v1 &source) noexcept {
    bg_docking_torsion_v7_move_v1 movement{};
    movement.slot_index = source.slot_index;
    movement.move_index = source.move_index;
    movement.evaluated = source.evaluated;
    movement.selected = source.selected;
    movement.rotatable_child_atom_index =
        static_cast<uint64_t>(source.rotatable_child_atom_index);
    movement.delta_radians = source.delta_radians;
    movement.receptor_penalty = source.receptor_penalty;
    movement.internal_penalty = source.internal_penalty;
    movement.combined_penalty = source.combined_penalty;
    return movement;
}

[[nodiscard]] bg_status refine_rust_fixed64(
    const ProviderEnvelope &state,
    const bg_docking_torsion_v7_candidate_batch_soa_v1 &candidates,
    std::size_t coordinate_count,
    BatchResult *out_result) {
    std::array<int32_t, kCandidateCount> candidate_states{};
    std::array<uint8_t, kCandidateCount> eligibility{};
    std::array<std::size_t, kCandidateCount> maximum_steps{};
    std::array<std::size_t, kCandidateCount> baseline_steps{};
    for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
        candidate_states[slot] = candidates.candidate_state[slot];
        eligibility[slot] = candidates.proposal_is_torsion_eligible[slot];
        if (candidates.candidate_state[slot] ==
            BG_DOCKING_TORSION_V7_CANDIDATE_INACTIVE) {
            continue;
        }
        if constexpr (sizeof(std::size_t) < sizeof(uint64_t)) {
            if (candidates.max_steps[slot] >
                    static_cast<uint64_t>(
                        std::numeric_limits<std::size_t>::max()) ||
                candidates.baseline_v6_accepted_steps[slot] >
                    static_cast<uint64_t>(
                        std::numeric_limits<std::size_t>::max())) {
                eligibility[slot] = UINT8_C(2);
                continue;
            }
        }
        maximum_steps[slot] =
            static_cast<std::size_t>(candidates.max_steps[slot]);
        baseline_steps[slot] = static_cast<std::size_t>(
            candidates.baseline_v6_accepted_steps[slot]);
    }
    bg_rust_cpu_torsion_v7_batch_v1 batch{};
    batch.struct_size = static_cast<uint32_t>(sizeof(batch));
    batch.abi_version = BG_RUST_CPU_PROVIDER_ABI_VERSION;
    batch.candidate_count = kCandidateCount;
    batch.ligand_atom_count = state.ligand_radii.size();
    batch.candidate_state = candidate_states.data();
    batch.proposal_is_torsion_eligible = eligibility.data();
    batch.max_steps = maximum_steps.data();
    batch.baseline_v6_accepted_steps = baseline_steps.data();
    batch.source_x_angstrom = candidates.source_x_angstrom;
    batch.source_y_angstrom = candidates.source_y_angstrom;
    batch.source_z_angstrom = candidates.source_z_angstrom;
    batch.baseline_v6_x_angstrom = candidates.baseline_v6_x_angstrom;
    batch.baseline_v6_y_angstrom = candidates.baseline_v6_y_angstrom;
    batch.baseline_v6_z_angstrom = candidates.baseline_v6_z_angstrom;
    batch.baseline_v6_torsion_angles_radians =
        candidates.baseline_v6_torsion_angles_radians;

    std::array<bg_rust_cpu_torsion_v7_row_v1, kCandidateCount> rows{};
    std::array<bg_rust_cpu_torsion_v7_move_v1,
               kCandidateCount * kMaxMoves>
        moves{};
    BatchResult output = make_empty_batch_result(coordinate_count);
    bg_rust_cpu_error_v1 error{};
    initialize_rust_error(&error);
    const int32_t raw_status =
        bg_rust_cpu_docking_torsion_v7_refine_fixed64(
            state.backend_state,
            &batch,
            rows.data(),
            moves.data(),
            output.optimized_x.data(),
            output.optimized_y.data(),
            output.optimized_z.data(),
            output.optimized_angles.data(),
            output.final_x.data(),
            output.final_y.data(),
            output.final_z.data(),
            output.final_angles.data(),
            &error);
    if (raw_status != BG_STATUS_OK) {
        return rust_failure(
            raw_status, error, "rust_cpu torsion V7 batch failed");
    }
    for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
        output.rows[slot] = public_row(rows[slot]);
    }
    for (std::size_t index = 0; index < moves.size(); ++index) {
        output.moves[index] = public_move(moves[index]);
    }
    *out_result = std::move(output);
    return BG_STATUS_OK;
}

[[nodiscard]] bool zero_bytes(const uint8_t *values, std::size_t count) noexcept {
    return std::all_of(values, values + count, [](uint8_t value) {
        return value == UINT8_C(0);
    });
}

[[nodiscard]] bool finite_row(
    const bg_docking_torsion_v7_row_v1 &row) noexcept {
    const std::array<double, 14> values = {
        row.source_receptor_penalty,
        row.source_internal_penalty,
        row.source_combined_penalty,
        row.baseline_receptor_penalty,
        row.baseline_internal_penalty,
        row.baseline_combined_penalty,
        row.optimized_receptor_penalty,
        row.optimized_internal_penalty,
        row.optimized_combined_penalty,
        row.final_receptor_penalty,
        row.final_internal_penalty,
        row.final_combined_penalty,
        row.evaluated_total_torsion_path_radians,
        row.accepted_total_torsion_path_radians,
    };
    return std::all_of(values.begin(), values.end(), [](double value) {
        return std::isfinite(value);
    });
}

[[nodiscard]] bg_status validate_result(
    const BatchResult &result,
    std::size_t ligand_count) noexcept {
    const std::size_t coordinate_count = kCandidateCount * ligand_count;
    if (result.optimized_x.size() != coordinate_count ||
        result.optimized_y.size() != coordinate_count ||
        result.optimized_z.size() != coordinate_count ||
        result.optimized_angles.size() != coordinate_count ||
        result.final_x.size() != coordinate_count ||
        result.final_y.size() != coordinate_count ||
        result.final_z.size() != coordinate_count ||
        result.final_angles.size() != coordinate_count) {
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "torsion V7 provider changed the coordinate denominator");
    }
    const std::array<const std::vector<double> *, 8> channels = {
        &result.optimized_x,
        &result.optimized_y,
        &result.optimized_z,
        &result.optimized_angles,
        &result.final_x,
        &result.final_y,
        &result.final_z,
        &result.final_angles,
    };
    for (const auto *channel : channels) {
        if (std::any_of(channel->begin(), channel->end(), [](double value) {
                return !std::isfinite(value);
            })) {
            return fail(
                BG_STATUS_NUMERICAL_ERROR,
                "torsion V7 provider returned non-finite coordinates");
        }
    }
    for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
        const auto &row = result.rows[slot];
        if (row.slot_index != slot || !reserved_is_zero(row.reserved) ||
            !zero_bytes(row.reserved0, sizeof(row.reserved0)) ||
            row.selection_window_reachable > UINT8_C(1) ||
            row.evaluation_stopped_after_selection_window_became_unreachable >
                UINT8_C(1) ||
            row.torsion_evaluated > UINT8_C(1) ||
            row.torsion_variant_available > UINT8_C(1) ||
            row.torsion_selected > UINT8_C(1) || !finite_row(row)) {
            return fail(
                BG_STATUS_INTERNAL_ERROR,
                "torsion V7 provider returned a malformed row");
        }
        if (row.status == BG_DOCKING_TORSION_V7_ROW_TYPED_FAILURE) {
            if (row.failure_code <
                    BG_DOCKING_TORSION_V7_FAILURE_UPSTREAM_NOT_ELIGIBLE ||
                row.failure_code >
                    BG_DOCKING_TORSION_V7_FAILURE_NONFINITE_DERIVED_VALUE ||
                row.skip_reason != 0 || row.selection_reason != 0 ||
                row.selection_window_reachable != 0 ||
                row.evaluation_stopped_after_selection_window_became_unreachable !=
                    0 ||
                row.torsion_evaluated != 0 ||
                row.torsion_variant_available != 0 ||
                row.torsion_selected != 0 || row.torsion_step_budget != 0 ||
                row.fixed_objective_evaluation_count != 0 ||
                row.torsion_trial_objective_evaluation_count != 0 ||
                row.evaluated_torsion_steps != 0 ||
                row.accepted_torsion_steps != 0 ||
                row.baseline_v6_accepted_steps != 0 ||
                row.source_receptor_penalty != 0.0 ||
                row.source_internal_penalty != 0.0 ||
                row.source_combined_penalty != 0.0 ||
                row.baseline_receptor_penalty != 0.0 ||
                row.baseline_internal_penalty != 0.0 ||
                row.baseline_combined_penalty != 0.0 ||
                row.optimized_receptor_penalty != 0.0 ||
                row.optimized_internal_penalty != 0.0 ||
                row.optimized_combined_penalty != 0.0 ||
                row.final_receptor_penalty != 0.0 ||
                row.final_internal_penalty != 0.0 ||
                row.final_combined_penalty != 0.0 ||
                row.evaluated_total_torsion_path_radians != 0.0 ||
                row.accepted_total_torsion_path_radians != 0.0) {
                return fail(
                    BG_STATUS_INTERNAL_ERROR,
                    "torsion V7 provider returned malformed typed failure evidence");
            }
        } else if (row.status == BG_DOCKING_TORSION_V7_ROW_REFINED) {
            if (row.failure_code != BG_DOCKING_TORSION_V7_FAILURE_NONE ||
                row.skip_reason < BG_DOCKING_TORSION_V7_SKIP_NONE ||
                row.skip_reason >
                    BG_DOCKING_TORSION_V7_SKIP_SELECTION_WINDOW_UNREACHABLE ||
                row.selection_reason <
                    BG_DOCKING_TORSION_V7_SELECTION_FINAL_PENALTY_WINDOW ||
                row.selection_reason >
                    BG_DOCKING_TORSION_V7_SELECTION_V6_RETAINED_NO_REDUCTION ||
                row.evaluated_torsion_steps > kMaxMoves ||
                row.accepted_torsion_steps > row.evaluated_torsion_steps ||
                (row.torsion_variant_available !=
                 static_cast<uint8_t>(row.evaluated_torsion_steps != 0)) ||
                (row.torsion_selected == 0 &&
                 row.accepted_torsion_steps != 0) ||
                (row.torsion_selected != 0 &&
                 row.accepted_torsion_steps != row.evaluated_torsion_steps)) {
                return fail(
                    BG_STATUS_INTERNAL_ERROR,
                    "torsion V7 provider returned inconsistent refinement evidence");
            }
        } else {
            return fail(
                BG_STATUS_INTERNAL_ERROR,
                "torsion V7 provider returned an unknown row status");
        }
        for (std::size_t move_index = 0; move_index < kMaxMoves;
             ++move_index) {
            const auto &movement = result.moves[slot * kMaxMoves + move_index];
            if (movement.slot_index != slot ||
                movement.move_index != move_index ||
                movement.evaluated > UINT8_C(1) ||
                movement.selected > UINT8_C(1) || movement.reserved0 != 0 ||
                !reserved_is_zero(movement.reserved) ||
                !std::isfinite(movement.delta_radians) ||
                !std::isfinite(movement.receptor_penalty) ||
                !std::isfinite(movement.internal_penalty) ||
                !std::isfinite(movement.combined_penalty)) {
                return fail(
                    BG_STATUS_INTERNAL_ERROR,
                    "torsion V7 provider returned malformed move evidence");
            }
            const bool expected_evaluated =
                row.status == BG_DOCKING_TORSION_V7_ROW_REFINED &&
                move_index < row.evaluated_torsion_steps;
            if ((movement.evaluated != 0) != expected_evaluated ||
                (expected_evaluated &&
                 movement.selected != row.torsion_selected) ||
                (!expected_evaluated &&
                 (movement.selected != 0 ||
                  movement.rotatable_child_atom_index != 0 ||
                  movement.delta_radians != 0.0 ||
                  movement.receptor_penalty != 0.0 ||
                  movement.internal_penalty != 0.0 ||
                  movement.combined_penalty != 0.0))) {
                return fail(
                    BG_STATUS_INTERNAL_ERROR,
                    "torsion V7 move rows do not match candidate evidence");
            }
        }
    }
    return BG_STATUS_OK;
}

void commit_result(
    const BatchResult &result,
    bg_docking_torsion_v7_output_v1 *output) noexcept {
    std::copy(result.rows.begin(), result.rows.end(), output->rows);
    std::copy(result.moves.begin(), result.moves.end(), output->moves);
    std::copy(
        result.optimized_x.begin(),
        result.optimized_x.end(),
        output->optimized_x_angstrom);
    std::copy(
        result.optimized_y.begin(),
        result.optimized_y.end(),
        output->optimized_y_angstrom);
    std::copy(
        result.optimized_z.begin(),
        result.optimized_z.end(),
        output->optimized_z_angstrom);
    std::copy(
        result.optimized_angles.begin(),
        result.optimized_angles.end(),
        output->optimized_torsion_angles_radians);
    std::copy(
        result.final_x.begin(), result.final_x.end(), output->final_x_angstrom);
    std::copy(
        result.final_y.begin(), result.final_y.end(), output->final_y_angstrom);
    std::copy(
        result.final_z.begin(), result.final_z.end(), output->final_z_angstrom);
    std::copy(
        result.final_angles.begin(),
        result.final_angles.end(),
        output->final_torsion_angles_radians);
    output->row_count = kCandidateCount;
    output->move_count = kCandidateCount * kMaxMoves;
    output->coordinate_count = result.optimized_x.size();
    output->molecular_execution_authorized = UINT8_C(0);
    output->existing_rank_auto_change_authorized = UINT8_C(0);
    output->customer_pose_emission_authorized = UINT8_C(0);
    output->production_claim_authorized = UINT8_C(0);
}

}  // namespace

void destroy_provider(bg_docking_torsion_v7 *refiner) noexcept {
    if (refiner == nullptr || refiner->provider_state == nullptr) {
        return;
    }
    auto *state = static_cast<ProviderEnvelope *>(refiner->provider_state);
    if (refiner->backend == BG_BACKEND_RUST_CPU &&
        state->backend_state != nullptr) {
        bg_rust_cpu_docking_torsion_v7_destroy(state->backend_state);
    }
    delete state;
    refiner->provider_state = nullptr;
}

}  // namespace betelgeuze::native::docking::torsion_v7

extern "C" BG_API bg_status BG_CALL
bg_docking_torsion_v7_context_soa_v1_init(
    bg_docking_torsion_v7_context_soa_v1 *descriptor,
    std::size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            descriptor,
            caller_struct_size,
            sizeof(*descriptor),
            caller_abi_version,
            "torsion V7 context initializer pointer is null",
            "torsion V7 context initializer size does not match",
            "torsion V7 context initializer ABI version does not match");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *descriptor = bg_docking_torsion_v7_context_soa_v1{};
        descriptor->struct_size = static_cast<uint32_t>(sizeof(*descriptor));
        descriptor->abi_version = BG_ABI_VERSION;
        descriptor->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        descriptor->receptor_overlap_scale = 1.0;
        descriptor->internal_overlap_scale = 0.8;
        descriptor->internal_overlap_weight = 1.0;
        descriptor->maximum_baseline_v6_steps = UINT64_C(20);
        descriptor->maximum_torsions_evaluated = UINT64_C(4);
        descriptor->maximum_torsion_steps = UINT64_C(4);
        descriptor->maximum_backtracking_evaluations = UINT64_C(3);
        descriptor->maximum_torsion_step_radians =
            3.141592653589793238462643383279502884 / 8.0;
        descriptor->minimum_torsion_step_radians =
            3.141592653589793238462643383279502884 / 32.0;
        descriptor->maximum_total_torsion_path_radians =
            3.141592653589793238462643383279502884 / 2.0;
        descriptor->maximum_centroid_offset_angstrom = 4.0;
        descriptor->minimum_selected_final_receptor_penalty = 2.0;
        descriptor->maximum_selected_final_receptor_penalty = 4.0;
        descriptor->penalty_tolerance = 1.0e-18;
        descriptor->epsilon_angstrom = 1.0e-9;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL
bg_docking_torsion_v7_candidate_batch_soa_v1_init(
    bg_docking_torsion_v7_candidate_batch_soa_v1 *batch,
    std::size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            batch,
            caller_struct_size,
            sizeof(*batch),
            caller_abi_version,
            "torsion V7 batch initializer pointer is null",
            "torsion V7 batch initializer size does not match",
            "torsion V7 batch initializer ABI version does not match");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *batch = bg_docking_torsion_v7_candidate_batch_soa_v1{};
        batch->struct_size = static_cast<uint32_t>(sizeof(*batch));
        batch->abi_version = BG_ABI_VERSION;
        batch->candidate_count = BG_DOCKING_FIXED64_CANDIDATE_COUNT;
        batch->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_docking_torsion_v7_output_v1_init(
    bg_docking_torsion_v7_output_v1 *output,
    std::size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            output,
            caller_struct_size,
            sizeof(*output),
            caller_abi_version,
            "torsion V7 output initializer pointer is null",
            "torsion V7 output initializer size does not match",
            "torsion V7 output initializer ABI version does not match");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *output = bg_docking_torsion_v7_output_v1{};
        output->struct_size = static_cast<uint32_t>(sizeof(*output));
        output->abi_version = BG_ABI_VERSION;
        output->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_docking_torsion_v7_create(
    const bg_context *context,
    const bg_docking_torsion_v7_context_soa_v1 *descriptor,
    bg_docking_torsion_v7 **out_refiner) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::docking::torsion_v7;
    return guarded_status([&]() -> bg_status {
        if (context == nullptr || descriptor == nullptr ||
            out_refiner == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "torsion V7 create inputs and output must not be null");
        }
        *out_refiner = nullptr;
        if (context->unit_system != descriptor->unit_system) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "torsion V7 context unit system is cross-wired");
        }
        std::unique_ptr<ProviderEnvelope> state;
        bg_status status = build_envelope(*descriptor, &state);
        if (status != BG_STATUS_OK) {
            return status;
        }
        if (context->backend == BG_BACKEND_RUST_CPU) {
            status = create_rust_backend(state.get());
            if (status != BG_STATUS_OK) {
                return status;
            }
        } else if (context->backend == BG_BACKEND_CPP_CPU_REFERENCE) {
            status = BG_STATUS_OK;
        } else if (context->backend == BG_BACKEND_HIP_SAFE ||
                   context->backend == BG_BACKEND_HIP_FAST) {
            return fail(
                BG_STATUS_BACKEND_UNAVAILABLE,
                "selected HIP backend has no compiled torsion V7 provider; fallback is forbidden");
        } else {
            return fail(
                BG_STATUS_UNSUPPORTED_BACKEND,
                "torsion V7 backend is unsupported");
        }
        auto refiner = std::make_unique<bg_docking_torsion_v7>();
        refiner->backend = context->backend;
        refiner->device_ordinal = context->device_ordinal;
        refiner->ligand_atom_count = descriptor->ligand_atom_count;
        refiner->provider_state = state.release();
        *out_refiner = refiner.release();
        return BG_STATUS_OK;
    });
}

extern "C" BG_API void BG_CALL bg_docking_torsion_v7_destroy(
    bg_docking_torsion_v7 *refiner) BG_NOEXCEPT {
    betelgeuze::native::docking::torsion_v7::destroy_provider(refiner);
    delete refiner;
}

extern "C" BG_API bg_status BG_CALL bg_docking_torsion_v7_get_backend(
    const bg_docking_torsion_v7 *refiner,
    bg_backend *backend) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        if (refiner == nullptr || backend == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "torsion V7 handle and backend output must not be null");
        }
        *backend = refiner->backend;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_docking_torsion_v7_refine_fixed64(
    const bg_context *context,
    const bg_docking_torsion_v7 *refiner,
    const bg_docking_torsion_v7_candidate_batch_soa_v1 *candidates,
    bg_docking_torsion_v7_output_v1 *output) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::docking::torsion_v7;
    return guarded_status([&]() -> bg_status {
        if (context == nullptr || refiner == nullptr || candidates == nullptr ||
            output == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "torsion V7 refine inputs and output must not be null");
        }
        if (context->backend != refiner->backend ||
            context->device_ordinal != refiner->device_ordinal) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "torsion V7 handle is cross-wired to another backend or device");
        }
        std::size_t coordinate_count = 0;
        bg_status status = validate_batch_and_output(
            refiner, *candidates, *output, &coordinate_count);
        if (status != BG_STATUS_OK) {
            return status;
        }
        const auto *state =
            static_cast<const ProviderEnvelope *>(refiner->provider_state);
        if (state == nullptr ||
            state->ligand_radii.size() != candidates->ligand_atom_count) {
            return fail(
                BG_STATUS_INTERNAL_ERROR,
                "torsion V7 persistent state is invalid");
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
        } else {
            return fail(
                BG_STATUS_BACKEND_UNAVAILABLE,
                "selected backend has no torsion V7 kernel; fallback is forbidden");
        }
        status = validate_result(result, state->ligand_radii.size());
        if (status != BG_STATUS_OK) {
            return status;
        }
        commit_result(result, output);
        return BG_STATUS_OK;
    });
}
