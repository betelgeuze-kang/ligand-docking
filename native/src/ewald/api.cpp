#if !defined(BG_DISABLE_DESCRIPTOR_INIT_CONVENIENCE_MACROS)
#  define BG_DISABLE_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#endif
#if !defined(BG_DISABLE_DIRECT_EWALD_DESCRIPTOR_INIT_CONVENIENCE_MACROS)
#  define BG_DISABLE_DIRECT_EWALD_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#endif
#include "cpp_evaluator.hpp"
#include "model.hpp"
#include "rust_evaluator.hpp"

#include "../internal.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <map>
#include <memory>
#include <string>
#include <utility>
#include <vector>

namespace betelgeuze::native::ewald {
namespace {

constexpr std::size_t kMaxAtomCount = 4'096;
constexpr int32_t kMaxReciprocalIndex = 32;
constexpr std::size_t kMaxEvaluationWorkUnits = 10'000'000;
constexpr double kMinCellLength = 1.0e-6;
constexpr double kMaxCellLength = 1.0e9;
constexpr double kMinAlpha = 1.0e-12;
constexpr double kMaxAlpha = 1.0e6;
constexpr double kMinCutoff = 1.0e-8;
constexpr double kMaxCutoff = 1.0e8;
constexpr double kMinDielectric = 1.0e-12;
constexpr double kMaxDielectric = 1.0e12;
constexpr double kMinPairDistance = 1.0e-8;
constexpr double kMaxPairDistance = 1.0e3;
constexpr const char *kProfileId =
    "betelgeuze.native_direct_ewald/1.0.0";

struct ByteRange final {
    std::uintptr_t begin = 0;
    std::uintptr_t end = 0;
};

struct PairKey final {
    std::size_t atom_i = 0;
    std::size_t atom_j = 0;

    bool operator<(const PairKey &other) const noexcept {
        return atom_i < other.atom_i ||
               (atom_i == other.atom_i && atom_j < other.atom_j);
    }
};

bool make_byte_range(
    const void *pointer,
    std::size_t byte_count,
    ByteRange *out_range) noexcept {
    if (pointer == nullptr || out_range == nullptr) {
        return false;
    }
    const std::uintptr_t begin = reinterpret_cast<std::uintptr_t>(pointer);
    if (byte_count > std::numeric_limits<std::uintptr_t>::max() - begin) {
        return false;
    }
    *out_range = ByteRange{begin, begin + byte_count};
    return true;
}

bool ranges_overlap(const ByteRange &left, const ByteRange &right) noexcept {
    return left.begin < right.end && right.begin < left.end;
}

bool checked_multiply(
    std::size_t left,
    std::size_t right,
    std::size_t *out_value) noexcept {
    if (right != 0U &&
        left > std::numeric_limits<std::size_t>::max() / right) {
        return false;
    }
    *out_value = left * right;
    return true;
}

bool counted_range_overlaps(
    const void *pointer,
    uint64_t element_count,
    std::size_t element_size,
    const ByteRange &candidate) noexcept {
    if (pointer == nullptr || element_count == 0 || element_size == 0) {
        return false;
    }
    const std::uintptr_t begin = reinterpret_cast<std::uintptr_t>(pointer);
    if (candidate.end <= begin) {
        return false;
    }
    if (candidate.begin < begin) {
        return true;
    }
    const std::uintptr_t element_offset =
        (candidate.begin - begin) / element_size;
    if (element_offset > std::numeric_limits<uint64_t>::max()) {
        return false;
    }
    return element_count > static_cast<uint64_t>(element_offset);
}

bool checked_accumulate(
    std::size_t value,
    std::size_t *total) noexcept {
    if (value > std::numeric_limits<std::size_t>::max() - *total) {
        return false;
    }
    *total += value;
    return true;
}

bg_status validate_direct_header(
    uint32_t observed_size,
    std::size_t expected_size,
    uint32_t observed_version,
    const char *name) {
    if (expected_size > std::numeric_limits<uint32_t>::max() ||
        observed_size != static_cast<uint32_t>(expected_size)) {
        const std::string message =
            std::string(name) + " struct_size does not match direct-Ewald ABI 1.0";
        return fail(BG_STATUS_ABI_MISMATCH, message.c_str());
    }
    if (observed_version != BG_DIRECT_EWALD_ABI_VERSION) {
        const std::string message =
            std::string(name) + " abi_version does not match direct-Ewald ABI 1.0";
        return fail(BG_STATUS_ABI_MISMATCH, message.c_str());
    }
    return BG_STATUS_OK;
}

bg_status validate_direct_initializer(
    const void *descriptor,
    std::size_t caller_size,
    std::size_t native_size,
    uint32_t caller_version,
    const char *name) {
    if (descriptor == nullptr) {
        const std::string message = std::string(name) + " pointer must not be null";
        return fail(BG_STATUS_INVALID_ARGUMENT, message.c_str());
    }
    if (caller_size != native_size ||
        native_size > std::numeric_limits<uint32_t>::max()) {
        const std::string message =
            std::string(name) + " initializer size does not match direct-Ewald ABI 1.0";
        return fail(BG_STATUS_ABI_MISMATCH, message.c_str());
    }
    if (caller_version != BG_DIRECT_EWALD_ABI_VERSION) {
        const std::string message =
            std::string(name) + " initializer version does not match direct-Ewald ABI 1.0";
        return fail(BG_STATUS_ABI_MISMATCH, message.c_str());
    }
    return BG_STATUS_OK;
}

bg_status validate_error_descriptor(const bg_direct_ewald_error_v1 &error) {
    bg_status status = validate_direct_header(
        error.struct_size, sizeof(error), error.abi_version,
        "bg_direct_ewald_error_v1");
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (error.reserved0 != UINT32_C(0) ||
        !reserved_is_zero(error.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "bg_direct_ewald_error_v1 reserved fields must be zero");
    }
    return BG_STATUS_OK;
}

void clear_error(bg_direct_ewald_error_v1 *error) noexcept {
    error->code = BG_DIRECT_EWALD_ERROR_NONE;
    std::fill_n(
        error->detail,
        static_cast<std::size_t>(BG_DIRECT_EWALD_ERROR_DETAIL_CAPACITY), '\0');
}

void commit_error(
    bg_direct_ewald_error_v1 *error,
    bg_direct_ewald_error_code code,
    const std::string &detail) noexcept {
    error->code = code;
    const std::size_t limit =
        static_cast<std::size_t>(BG_DIRECT_EWALD_ERROR_DETAIL_CAPACITY) - 1U;
    const std::size_t length = std::min(limit, detail.size());
    std::fill_n(
        error->detail,
        static_cast<std::size_t>(BG_DIRECT_EWALD_ERROR_DETAIL_CAPACITY), '\0');
    if (length > 0) {
        std::memcpy(error->detail, detail.data(), length);
    }
    set_last_error(error->detail);
}

bg_status typed_failure(
    bg_direct_ewald_error_v1 *error,
    bg_direct_ewald_error_code code,
    const char *detail,
    bg_status status = BG_STATUS_INVALID_ARGUMENT) noexcept {
    commit_error(error, code, detail);
    return status;
}

bool in_range(double value, double minimum, double maximum) noexcept {
    return std::isfinite(value) && value >= minimum && value <= maximum;
}

bg_status checked_rule_count(
    uint64_t observed,
    const char *detail,
    std::size_t *out_count,
    bg_direct_ewald_error_v1 *error) noexcept {
    if (observed > static_cast<uint64_t>(
                       std::numeric_limits<std::size_t>::max())) {
        return typed_failure(
            error, BG_DIRECT_EWALD_ERROR_CAPACITY_EXCEEDED, detail,
            BG_STATUS_CAPACITY_OVERFLOW);
    }
    const uint64_t max_vector_count = static_cast<uint64_t>(
        std::numeric_limits<std::ptrdiff_t>::max() / sizeof(PairRule));
    if (observed > max_vector_count) {
        return typed_failure(
            error, BG_DIRECT_EWALD_ERROR_CAPACITY_EXCEEDED, detail,
            BG_STATUS_CAPACITY_OVERFLOW);
    }
    *out_count = static_cast<std::size_t>(observed);
    return BG_STATUS_OK;
}

bg_status validate_raw_work_limit(
    std::size_t atom_count,
    const std::array<int32_t, 3> &max_indices,
    std::size_t rule_count,
    bg_direct_ewald_error_v1 *error) noexcept {
    std::size_t vector_count = 1;
    for (const int32_t maximum : max_indices) {
        vector_count *= static_cast<std::size_t>(2 * maximum + 1);
    }
    --vector_count;
    std::size_t pair_twice = 0;
    std::size_t pair_work = 0;
    std::size_t rule_work = 0;
    std::size_t phase_work = 0;
    if (!checked_multiply(
            atom_count, atom_count - 1U, &pair_twice) ||
        !checked_multiply(pair_twice / 2U, 7U, &pair_work) ||
        !checked_multiply(rule_count, 7U, &rule_work) ||
        !checked_multiply(atom_count, vector_count, &phase_work) ||
        !checked_multiply(phase_work, 2U, &phase_work)) {
        return typed_failure(
            error, BG_DIRECT_EWALD_ERROR_CAPACITY_EXCEEDED,
            "raw pair or reciprocal work exceeds addressable capacity",
            BG_STATUS_CAPACITY_OVERFLOW);
    }
    std::size_t total_work = 0;
    if (!checked_accumulate(pair_work, &total_work) ||
        !checked_accumulate(rule_work, &total_work) ||
        !checked_accumulate(phase_work, &total_work) ||
        total_work > kMaxEvaluationWorkUnits) {
        return typed_failure(
            error, BG_DIRECT_EWALD_ERROR_CAPACITY_EXCEEDED,
            "combined raw evaluation work exceeds 10000000",
            BG_STATUS_CAPACITY_OVERFLOW);
    }
    return BG_STATUS_OK;
}

bg_status validate_parameters(
    const bg_direct_ewald_parameters_v1 &parameters,
    bg_direct_ewald_error_v1 *error,
    std::size_t *out_exclusion_count,
    std::size_t *out_scale_count) {
    bg_status status = validate_direct_header(
        parameters.struct_size, sizeof(parameters), parameters.abi_version,
        "bg_direct_ewald_parameters_v1");
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (parameters.reserved0 != UINT32_C(0) ||
        parameters.reserved1 != UINT32_C(0) ||
        !reserved_is_zero(parameters.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "bg_direct_ewald_parameters_v1 reserved fields must be zero");
    }
    status = validate_unit_system(parameters.unit_system);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (parameters.atom_count == 0) {
        return typed_failure(
            error, BG_DIRECT_EWALD_ERROR_EMPTY_SYSTEM,
            "at least one atom is required");
    }
    if (parameters.atom_count > kMaxAtomCount) {
        return typed_failure(
            error, BG_DIRECT_EWALD_ERROR_CAPACITY_EXCEEDED,
            "atom count exceeds 4096", BG_STATUS_CAPACITY_OVERFLOW);
    }
    for (std::size_t axis = 0; axis < 3; ++axis) {
        if (!in_range(
                parameters.cell_lengths_angstrom[axis], kMinCellLength,
                kMaxCellLength)) {
            return typed_failure(
                error, BG_DIRECT_EWALD_ERROR_INVALID_CELL,
                "cell lengths must lie in [1e-6,1e9] angstrom");
        }
        if (parameters.reciprocal_max_indices[axis] < 1 ||
            parameters.reciprocal_max_indices[axis] > kMaxReciprocalIndex) {
            return typed_failure(
                error, BG_DIRECT_EWALD_ERROR_INVALID_PARAMETER,
                "reciprocal maximum indices must lie in [1,32]");
        }
    }
    std::array<double, 3> sorted_lengths{
        parameters.cell_lengths_angstrom[0],
        parameters.cell_lengths_angstrom[1],
        parameters.cell_lengths_angstrom[2]};
    std::sort(sorted_lengths.begin(), sorted_lengths.end());
    const double volume =
        (sorted_lengths[0] * sorted_lengths[2]) * sorted_lengths[1];
    if (!std::isfinite(volume) || volume <= 0.0) {
        return typed_failure(
            error, BG_DIRECT_EWALD_ERROR_INVALID_CELL,
            "cell volume must be finite and positive");
    }
    if (!in_range(parameters.alpha_per_angstrom, kMinAlpha, kMaxAlpha) ||
        !in_range(
            parameters.real_space_cutoff_angstrom, kMinCutoff, kMaxCutoff) ||
        !in_range(parameters.dielectric, kMinDielectric, kMaxDielectric) ||
        !in_range(
            parameters.minimum_pair_distance_angstrom, kMinPairDistance,
            kMaxPairDistance)) {
        return typed_failure(
            error, BG_DIRECT_EWALD_ERROR_INVALID_PARAMETER,
            "direct-Ewald settings lie outside the supported numeric envelope");
    }
    if (parameters.minimum_pair_distance_angstrom >=
        parameters.real_space_cutoff_angstrom) {
        return typed_failure(
            error, BG_DIRECT_EWALD_ERROR_INVALID_PARAMETER,
            "minimum pair distance must be below the real-space cutoff");
    }
    for (const double length : parameters.cell_lengths_angstrom) {
        if (parameters.real_space_cutoff_angstrom >= 0.5 * length) {
            return typed_failure(
                error,
                BG_DIRECT_EWALD_ERROR_CUTOFF_VIOLATES_MINIMUM_IMAGE,
                "real-space cutoff must be below half every cell length");
        }
    }
    status = checked_rule_count(
        parameters.exclusion_count,
        "exclusion count exceeds native capacity", out_exclusion_count,
        error);
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = checked_rule_count(
        parameters.pair_scale_count,
        "pair-scale count exceeds native capacity", out_scale_count, error);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (*out_exclusion_count >
        std::numeric_limits<std::size_t>::max() - *out_scale_count) {
        return typed_failure(
            error, BG_DIRECT_EWALD_ERROR_CAPACITY_EXCEEDED,
            "combined pair-rule count exceeds native capacity",
            BG_STATUS_CAPACITY_OVERFLOW);
    }
    const std::size_t raw_count = *out_exclusion_count + *out_scale_count;
    status = validate_raw_work_limit(
        static_cast<std::size_t>(parameters.atom_count),
        {parameters.reciprocal_max_indices[0],
         parameters.reciprocal_max_indices[1],
         parameters.reciprocal_max_indices[2]},
        raw_count, error);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (*out_exclusion_count > 0 &&
        (parameters.exclusion_atom_i == nullptr ||
         parameters.exclusion_atom_j == nullptr)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "non-empty exclusions require both index channels");
    }
    if (*out_scale_count > 0 &&
        (parameters.pair_scale_atom_i == nullptr ||
         parameters.pair_scale_atom_j == nullptr ||
         parameters.pair_scale_coulomb == nullptr)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "non-empty pair scales require both indices and scale channel");
    }
    if (!pointer_is_aligned(parameters.exclusion_atom_i) ||
        !pointer_is_aligned(parameters.exclusion_atom_j) ||
        !pointer_is_aligned(parameters.pair_scale_atom_i) ||
        !pointer_is_aligned(parameters.pair_scale_atom_j) ||
        !pointer_is_aligned(parameters.pair_scale_coulomb)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "direct-Ewald pair-rule channels must be naturally aligned");
    }
    return BG_STATUS_OK;
}

bg_status copy_pair_rules(
    const bg_direct_ewald_parameters_v1 &parameters,
    std::size_t exclusion_count,
    std::size_t scale_count,
    bg_direct_ewald_error_v1 *error,
    std::vector<PairRule> *out_rules) {
    std::map<PairKey, double> exclusions;
    std::map<PairKey, double> scales;
    for (std::size_t row = 0; row < exclusion_count; ++row) {
        const uint64_t raw_i = parameters.exclusion_atom_i[row];
        const uint64_t raw_j = parameters.exclusion_atom_j[row];
        if (raw_i >= parameters.atom_count || raw_j >= parameters.atom_count) {
            return typed_failure(
                error, BG_DIRECT_EWALD_ERROR_ATOM_INDEX_OUT_OF_RANGE,
                "an exclusion atom index is outside the model atom range");
        }
        if (raw_i == raw_j) {
            return typed_failure(
                error, BG_DIRECT_EWALD_ERROR_REPEATED_ATOM_INDEX,
                "an exclusion repeats an atom index");
        }
        const PairKey pair{
            static_cast<std::size_t>(std::min(raw_i, raw_j)),
            static_cast<std::size_t>(std::max(raw_i, raw_j))};
        if (!exclusions.emplace(pair, 0.0).second) {
            return typed_failure(
                error, BG_DIRECT_EWALD_ERROR_DUPLICATE_PAIR_RULE,
                "duplicate exclusion pair");
        }
    }
    for (std::size_t row = 0; row < scale_count; ++row) {
        const uint64_t raw_i = parameters.pair_scale_atom_i[row];
        const uint64_t raw_j = parameters.pair_scale_atom_j[row];
        if (raw_i >= parameters.atom_count || raw_j >= parameters.atom_count) {
            return typed_failure(
                error, BG_DIRECT_EWALD_ERROR_ATOM_INDEX_OUT_OF_RANGE,
                "a pair-scale atom index is outside the model atom range");
        }
        if (raw_i == raw_j) {
            return typed_failure(
                error, BG_DIRECT_EWALD_ERROR_REPEATED_ATOM_INDEX,
                "a pair scale repeats an atom index");
        }
        const double scale = parameters.pair_scale_coulomb[row];
        if (!std::isfinite(scale) || scale < 0.0 || scale > 1.0) {
            return typed_failure(
                error, BG_DIRECT_EWALD_ERROR_INVALID_PARAMETER,
                "pair Coulomb scales must lie in [0,1]");
        }
        const PairKey pair{
            static_cast<std::size_t>(std::min(raw_i, raw_j)),
            static_cast<std::size_t>(std::max(raw_i, raw_j))};
        if (!scales.emplace(pair, scale).second) {
            return typed_failure(
                error, BG_DIRECT_EWALD_ERROR_DUPLICATE_PAIR_RULE,
                "duplicate scaled pair");
        }
    }
    for (const auto &entry : exclusions) {
        if (scales.find(entry.first) != scales.end()) {
            return typed_failure(
                error, BG_DIRECT_EWALD_ERROR_CONFLICTING_PAIR_RULE,
                "a pair cannot be both excluded and scaled");
        }
    }
    out_rules->clear();
    out_rules->reserve(exclusions.size() + scales.size());
    auto exclusion = exclusions.begin();
    auto scale = scales.begin();
    while (exclusion != exclusions.end() || scale != scales.end()) {
        if (scale == scales.end() ||
            (exclusion != exclusions.end() &&
             exclusion->first < scale->first)) {
            out_rules->push_back(PairRule{
                exclusion->first.atom_i, exclusion->first.atom_j, 0.0});
            ++exclusion;
        } else {
            out_rules->push_back(PairRule{
                scale->first.atom_i, scale->first.atom_j, scale->second});
            ++scale;
        }
    }
    return BG_STATUS_OK;
}

bg_status validate_energy_output(
    const bg_direct_ewald_energy_components_v1 &energy) {
    bg_status status = validate_direct_header(
        energy.struct_size, sizeof(energy), energy.abi_version,
        "bg_direct_ewald_energy_components_v1");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = validate_unit_system(energy.unit_system);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (energy.reserved0 != UINT32_C(0) ||
        !reserved_is_zero(energy.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "direct-Ewald energy reserved fields must be zero");
    }
    return BG_STATUS_OK;
}

bg_status validate_force_output(
    const bg_direct_ewald_force_soa_v1 &forces,
    const bg_direct_ewald_energy_components_v1 *energy,
    const bg_direct_ewald_error_v1 *error,
    std::size_t atom_count) {
    bg_status status = validate_direct_header(
        forces.struct_size, sizeof(forces), forces.abi_version,
        "bg_direct_ewald_force_soa_v1");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = validate_unit_system(forces.unit_system);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (forces.reserved0 != UINT32_C(0) ||
        !reserved_is_zero(forces.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "direct-Ewald force reserved fields must be zero");
    }
    if (forces.atom_capacity < static_cast<uint64_t>(atom_count)) {
        return fail(
            BG_STATUS_BUFFER_TOO_SMALL,
            "direct-Ewald force capacity is smaller than atom count");
    }
    if (atom_count > 0 &&
        (forces.x_kcal_per_mol_angstrom == nullptr ||
         forces.y_kcal_per_mol_angstrom == nullptr ||
         forces.z_kcal_per_mol_angstrom == nullptr)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "non-empty direct-Ewald force output requires three channels");
    }
    if (!pointer_is_aligned(forces.x_kcal_per_mol_angstrom) ||
        !pointer_is_aligned(forces.y_kcal_per_mol_angstrom) ||
        !pointer_is_aligned(forces.z_kcal_per_mol_angstrom)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "direct-Ewald force channels must be naturally aligned");
    }
    const std::size_t bytes = atom_count * sizeof(double);
    std::array<ByteRange, 6> ranges{};
    if (!make_byte_range(forces.x_kcal_per_mol_angstrom, bytes, &ranges[0]) ||
        !make_byte_range(forces.y_kcal_per_mol_angstrom, bytes, &ranges[1]) ||
        !make_byte_range(forces.z_kcal_per_mol_angstrom, bytes, &ranges[2]) ||
        !make_byte_range(&forces, sizeof(forces), &ranges[3]) ||
        !make_byte_range(energy, sizeof(*energy), &ranges[4]) ||
        !make_byte_range(error, sizeof(*error), &ranges[5])) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "direct-Ewald output byte ranges are not representable");
    }
    for (std::size_t left = 0; left < ranges.size(); ++left) {
        for (std::size_t right = left + 1U; right < ranges.size(); ++right) {
            if (ranges_overlap(ranges[left], ranges[right])) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "direct-Ewald output channels/descriptors must not overlap");
            }
        }
    }
    return BG_STATUS_OK;
}

bg_status validate_descriptor_overlap(
    const bg_direct_ewald_energy_components_v1 *energy,
    const bg_direct_ewald_force_soa_v1 *forces,
    const bg_direct_ewald_error_v1 *error) noexcept {
    ByteRange error_range;
    if (!make_byte_range(error, sizeof(*error), &error_range)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "direct-Ewald output descriptor byte ranges are not representable");
    }
    ByteRange energy_range;
    const bool has_energy = energy != nullptr;
    if (has_energy &&
        (!make_byte_range(energy, sizeof(*energy), &energy_range) ||
         ranges_overlap(energy_range, error_range))) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "direct-Ewald energy and error descriptors must not overlap");
    }
    if (forces != nullptr) {
        ByteRange force_range;
        if (!make_byte_range(forces, sizeof(*forces), &force_range) ||
            (has_energy && ranges_overlap(force_range, energy_range)) ||
            ranges_overlap(force_range, error_range)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "direct-Ewald output descriptors must not overlap");
        }
    }
    return BG_STATUS_OK;
}

bg_status validate_create_descriptor_overlap(
    const bg_direct_ewald_parameters_v1 *parameters,
    bg_direct_ewald_model_v1 **out_model,
    const bg_direct_ewald_error_v1 *error) noexcept {
    ByteRange error_range;
    if (!make_byte_range(error, sizeof(*error), &error_range)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "direct-Ewald create descriptor byte ranges are not representable");
    }
    ByteRange parameter_range;
    const bool has_parameters = parameters != nullptr;
    if (has_parameters &&
        (!make_byte_range(
             parameters, sizeof(*parameters), &parameter_range) ||
         ranges_overlap(parameter_range, error_range))) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "direct-Ewald parameters and error descriptors must not overlap");
    }
    ByteRange model_output_range;
    const bool has_model_output = out_model != nullptr;
    if (has_model_output) {
        if (!make_byte_range(
                out_model, sizeof(*out_model), &model_output_range) ||
            ranges_overlap(model_output_range, error_range) ||
            (has_parameters &&
             ranges_overlap(model_output_range, parameter_range))) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "direct-Ewald create descriptors and model output must not overlap");
        }
    }
    constexpr uint64_t kMaxPlausibleRuleCount =
        static_cast<uint64_t>(kMaxEvaluationWorkUnits / 7U);
    const bool channels_may_be_used =
        has_parameters &&
        parameters->exclusion_count <= kMaxPlausibleRuleCount &&
        parameters->pair_scale_count <=
            kMaxPlausibleRuleCount - parameters->exclusion_count;
    if (channels_may_be_used) {
        struct ChannelRange final {
            const void *pointer;
            uint64_t element_count;
            std::size_t element_size;
        };
        const std::array<ChannelRange, 5> channels{{
            {parameters->exclusion_atom_i, parameters->exclusion_count,
             sizeof(*parameters->exclusion_atom_i)},
            {parameters->exclusion_atom_j, parameters->exclusion_count,
             sizeof(*parameters->exclusion_atom_j)},
            {parameters->pair_scale_atom_i, parameters->pair_scale_count,
             sizeof(*parameters->pair_scale_atom_i)},
            {parameters->pair_scale_atom_j, parameters->pair_scale_count,
             sizeof(*parameters->pair_scale_atom_j)},
            {parameters->pair_scale_coulomb, parameters->pair_scale_count,
             sizeof(*parameters->pair_scale_coulomb)},
        }};
        for (const ChannelRange &channel : channels) {
            if (counted_range_overlaps(
                    channel.pointer, channel.element_count,
                    channel.element_size, error_range) ||
                (has_model_output &&
                 counted_range_overlaps(
                     channel.pointer, channel.element_count,
                     channel.element_size, model_output_range))) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "direct-Ewald create output storage must not overlap pair-rule channels");
            }
        }
    }
    return BG_STATUS_OK;
}

bg_status status_for_typed_error(bg_direct_ewald_error_code code) noexcept {
    if (code == BG_DIRECT_EWALD_ERROR_CAPACITY_EXCEEDED) {
        return BG_STATUS_CAPACITY_OVERFLOW;
    }
    switch (code) {
        case BG_DIRECT_EWALD_ERROR_DAMPING_UNDERFLOW:
        case BG_DIRECT_EWALD_ERROR_PHASE_UNDERFLOW:
        case BG_DIRECT_EWALD_ERROR_NONFINITE_RESULT:
        case BG_DIRECT_EWALD_ERROR_AMBIGUOUS_PAIR_CORRECTION_IMAGE:
        case BG_DIRECT_EWALD_ERROR_AMBIGUOUS_REAL_SPACE_CUTOFF:
        case BG_DIRECT_EWALD_ERROR_AMBIGUOUS_MINIMUM_PAIR_DISTANCE:
        case BG_DIRECT_EWALD_ERROR_PAIR_BELOW_MINIMUM_DISTANCE:
        case BG_DIRECT_EWALD_ERROR_NON_NEUTRAL_SYSTEM:
            return BG_STATUS_NUMERICAL_ERROR;
        default:
            return BG_STATUS_INVALID_ARGUMENT;
    }
}

}  // namespace
}  // namespace betelgeuze::native::ewald

extern "C" BG_API uint32_t BG_CALL bg_direct_ewald_abi_version(
    void) BG_NOEXCEPT {
    return BG_DIRECT_EWALD_ABI_VERSION;
}

extern "C" BG_API uint32_t BG_CALL bg_direct_ewald_abi_version_major(
    void) BG_NOEXCEPT {
    return BG_DIRECT_EWALD_ABI_VERSION_MAJOR;
}

extern "C" BG_API uint32_t BG_CALL bg_direct_ewald_abi_version_minor(
    void) BG_NOEXCEPT {
    return BG_DIRECT_EWALD_ABI_VERSION_MINOR;
}

extern "C" BG_API const char *BG_CALL bg_direct_ewald_abi_version_string(
    void) BG_NOEXCEPT {
    return "1.0.0";
}

extern "C" BG_API bg_status BG_CALL bg_direct_ewald_parameters_v1_init(
    bg_direct_ewald_parameters_v1 *parameters,
    std::size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::ewald;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_direct_initializer(
            parameters, caller_struct_size, sizeof(*parameters),
            caller_abi_version, "bg_direct_ewald_parameters_v1");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *parameters = bg_direct_ewald_parameters_v1{};
        parameters->struct_size = static_cast<uint32_t>(sizeof(*parameters));
        parameters->abi_version = BG_DIRECT_EWALD_ABI_VERSION;
        parameters->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        parameters->alpha_per_angstrom = 0.3;
        parameters->real_space_cutoff_angstrom = 8.0;
        parameters->reciprocal_max_indices[0] = 5;
        parameters->reciprocal_max_indices[1] = 5;
        parameters->reciprocal_max_indices[2] = 5;
        parameters->dielectric = 1.0;
        parameters->minimum_pair_distance_angstrom = 1.0e-8;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL
bg_direct_ewald_energy_components_v1_init(
    bg_direct_ewald_energy_components_v1 *energy,
    std::size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::ewald;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_direct_initializer(
            energy, caller_struct_size, sizeof(*energy), caller_abi_version,
            "bg_direct_ewald_energy_components_v1");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *energy = bg_direct_ewald_energy_components_v1{};
        energy->struct_size = static_cast<uint32_t>(sizeof(*energy));
        energy->abi_version = BG_DIRECT_EWALD_ABI_VERSION;
        energy->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_direct_ewald_force_soa_v1_init(
    bg_direct_ewald_force_soa_v1 *forces,
    std::size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::ewald;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_direct_initializer(
            forces, caller_struct_size, sizeof(*forces), caller_abi_version,
            "bg_direct_ewald_force_soa_v1");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *forces = bg_direct_ewald_force_soa_v1{};
        forces->struct_size = static_cast<uint32_t>(sizeof(*forces));
        forces->abi_version = BG_DIRECT_EWALD_ABI_VERSION;
        forces->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_direct_ewald_error_v1_init(
    bg_direct_ewald_error_v1 *error,
    std::size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::ewald;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_direct_initializer(
            error, caller_struct_size, sizeof(*error), caller_abi_version,
            "bg_direct_ewald_error_v1");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *error = bg_direct_ewald_error_v1{};
        error->struct_size = static_cast<uint32_t>(sizeof(*error));
        error->abi_version = BG_DIRECT_EWALD_ABI_VERSION;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_direct_ewald_model_v1_create(
    const bg_direct_ewald_parameters_v1 *parameters,
    bg_direct_ewald_model_v1 **out_model,
    bg_direct_ewald_error_v1 *out_error) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::ewald;
    return guarded_status([&]() -> bg_status {
        if (out_error == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "typed error must not be null");
        }
        bg_status status = validate_create_descriptor_overlap(
            parameters, out_model, out_error);
        if (status != BG_STATUS_OK) {
            return status;
        }
        if (out_model != nullptr) {
            *out_model = nullptr;
        }
        status = validate_error_descriptor(*out_error);
        if (status != BG_STATUS_OK) {
            return status;
        }
        clear_error(out_error);
        if (parameters == nullptr || out_model == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "parameters and model output must not be null");
        }
        std::size_t exclusion_count = 0;
        std::size_t scale_count = 0;
        status = validate_parameters(
            *parameters, out_error, &exclusion_count, &scale_count);
        if (status != BG_STATUS_OK) {
            return status;
        }
        auto model = std::make_unique<bg_direct_ewald_model_v1>();
        model->unit_system = parameters->unit_system;
        model->atom_count = static_cast<std::size_t>(parameters->atom_count);
        std::copy_n(
            parameters->cell_lengths_angstrom, 3,
            model->cell_lengths_angstrom.begin());
        model->alpha_per_angstrom = parameters->alpha_per_angstrom;
        model->real_space_cutoff_angstrom =
            parameters->real_space_cutoff_angstrom;
        std::copy_n(
            parameters->reciprocal_max_indices, 3,
            model->reciprocal_max_indices.begin());
        model->dielectric = parameters->dielectric;
        model->minimum_pair_distance_angstrom =
            parameters->minimum_pair_distance_angstrom;
        status = copy_pair_rules(
            *parameters, exclusion_count, scale_count, out_error,
            &model->pair_rules);
        if (status != BG_STATUS_OK) {
            return status;
        }
        *out_model = model.release();
        return BG_STATUS_OK;
    });
}

extern "C" BG_API void BG_CALL bg_direct_ewald_model_v1_destroy(
    bg_direct_ewald_model_v1 *model) BG_NOEXCEPT {
    delete model;
}

extern "C" BG_API bg_status BG_CALL
bg_direct_ewald_model_v1_get_atom_count(
    const bg_direct_ewald_model_v1 *model,
    uint64_t *atom_count) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        if (model == nullptr || atom_count == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "model and atom-count output must not be null");
        }
        *atom_count = static_cast<uint64_t>(model->atom_count);
        return BG_STATUS_OK;
    });
}

extern "C" BG_API const char *BG_CALL
bg_direct_ewald_model_v1_profile_id(void) BG_NOEXCEPT {
    return betelgeuze::native::ewald::kProfileId;
}

extern "C" BG_API bg_status BG_CALL bg_context_evaluate_direct_ewald_v1(
    const bg_context *context,
    const bg_system *system,
    const bg_direct_ewald_model_v1 *model,
    bg_direct_ewald_energy_components_v1 *out_energy,
    bg_direct_ewald_force_soa_v1 *out_forces,
    bg_direct_ewald_error_v1 *out_error) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::ewald;
    return guarded_status([&]() -> bg_status {
        if (out_error == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "typed error must not be null");
        }
        bg_status status = validate_error_descriptor(*out_error);
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = validate_descriptor_overlap(
            out_energy, out_forces, out_error);
        if (status != BG_STATUS_OK) {
            return status;
        }
        clear_error(out_error);
        if (context == nullptr || system == nullptr || model == nullptr ||
            out_energy == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "context, system, model, and energy must not be null");
        }
        status = validate_energy_output(*out_energy);
        if (status != BG_STATUS_OK) {
            return status;
        }
        if (out_forces != nullptr) {
            status = validate_force_output(
                *out_forces, out_energy, out_error, model->atom_count);
            if (status != BG_STATUS_OK) {
                return status;
            }
        }
        if (context->unit_system != system->unit_system ||
            context->unit_system != model->unit_system) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "context, system, and direct-Ewald model units must match");
        }
        Evaluation evaluation;
        Error typed_error;
        switch (context->backend) {
            case BG_BACKEND_CPP_CPU_REFERENCE:
                status = cpp_cpu::evaluate(
                    *system, *model, out_forces != nullptr, &evaluation,
                    &typed_error);
                break;
            case BG_BACKEND_RUST_CPU:
                status = rust_cpu::evaluate(
                    *system, *model, out_forces != nullptr, &evaluation,
                    &typed_error);
                break;
            case BG_BACKEND_HIP_SAFE:
            case BG_BACKEND_HIP_FAST:
                return fail(
                    BG_STATUS_UNSUPPORTED_BACKEND,
                    "direct-Ewald HIP execution is unsupported and CPU fallback is forbidden");
            default:
                return fail(
                    BG_STATUS_UNSUPPORTED_BACKEND,
                    "selected backend has no direct-Ewald evaluator");
        }
        if (status != BG_STATUS_OK) {
            if (typed_error.code != BG_DIRECT_EWALD_ERROR_NONE) {
                commit_error(
                    out_error, typed_error.code, typed_error.detail);
                return status_for_typed_error(typed_error.code);
            }
            return status;
        }
        bg_direct_ewald_energy_components_v1 committed_energy = *out_energy;
        committed_energy.real_space_kcal_per_mol =
            evaluation.energy.real_space;
        committed_energy.reciprocal_space_kcal_per_mol =
            evaluation.energy.reciprocal_space;
        committed_energy.self_kcal_per_mol = evaluation.energy.self;
        committed_energy.pair_correction_kcal_per_mol =
            evaluation.energy.pair_correction;
        committed_energy.total_kcal_per_mol = evaluation.energy.total();
        if (out_forces != nullptr) {
            for (std::size_t atom = 0; atom < model->atom_count; ++atom) {
                out_forces->x_kcal_per_mol_angstrom[atom] =
                    evaluation.forces[atom][0];
                out_forces->y_kcal_per_mol_angstrom[atom] =
                    evaluation.forces[atom][1];
                out_forces->z_kcal_per_mol_angstrom[atom] =
                    evaluation.forces[atom][2];
            }
            out_forces->atom_count = static_cast<uint64_t>(model->atom_count);
        }
        *out_energy = committed_energy;
        return BG_STATUS_OK;
    });
}
