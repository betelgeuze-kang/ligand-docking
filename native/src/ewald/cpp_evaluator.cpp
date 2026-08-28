#include "cpp_evaluator.hpp"

#include "../internal.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <sstream>
#include <tuple>
#include <utility>
#include <vector>

namespace betelgeuze::native::ewald::cpp_cpu {
namespace {

constexpr std::size_t kMaxAtomCount = 4'096;
constexpr std::size_t kMaxEvaluationWorkUnits = 10'000'000;
constexpr double kMaxAbsoluteCoordinateAngstrom = 1.0e12;
constexpr double kMinNonzeroAbsoluteCharge = 1.0e-12;
constexpr double kMaxAbsoluteCharge = 16.0;
constexpr double kChargeNormalizationScale =
    0x1.0p-40;
constexpr double kPeriodicComparisonRelativeTolerance = 5.0e-12;
constexpr double kLnHalfMinimumPositiveSubnormal = -745.1332191019411;
constexpr double kCoulombConstant =
    BG_COULOMB_CONSTANT_KCAL_ANGSTROM_PER_MOL_E2;
constexpr double kPi = 3.141592653589793238462643383279502884;
constexpr double kTau = 2.0 * kPi;

using Vector3 = std::array<double, 3>;
using ForceTerms = std::vector<std::array<std::vector<double>, 3>>;

bool set_error(
    Error *out_error,
    bg_direct_ewald_error_code code,
    std::string detail) {
    if (out_error != nullptr) {
        out_error->code = code;
        out_error->detail = std::move(detail);
    }
    return false;
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

bool checked_accumulate(
    std::size_t value,
    std::size_t *total) noexcept {
    if (value > std::numeric_limits<std::size_t>::max() - *total) {
        return false;
    }
    *total += value;
    return true;
}

std::uint64_t bits(double value) noexcept {
    std::uint64_t result = 0;
    static_assert(sizeof(result) == sizeof(value));
    std::memcpy(&result, &value, sizeof(result));
    return result;
}

std::uint64_t total_order_key(double value) noexcept {
    const std::uint64_t raw = bits(value);
    constexpr std::uint64_t sign = UINT64_C(1) << 63U;
    return (raw & sign) != 0 ? ~raw : raw | sign;
}

bool total_less(double left, double right) noexcept {
    return total_order_key(left) < total_order_key(right);
}

double accurate_sum(const std::vector<double> &values) {
    std::vector<double> ordered(values);
    std::sort(ordered.begin(), ordered.end(), [](double left, double right) {
        const double left_absolute = std::abs(left);
        const double right_absolute = std::abs(right);
        if (total_order_key(left_absolute) != total_order_key(right_absolute)) {
            return total_less(left_absolute, right_absolute);
        }
        return total_less(left, right);
    });
    double sum = 0.0;
    double correction = 0.0;
    for (const double value : ordered) {
        const double updated = sum + value;
        correction += std::abs(sum) >= std::abs(value)
                          ? (sum - updated) + value
                          : (value - updated) + sum;
        sum = updated;
    }
    return sum + correction;
}

double accurate_charge_square_sum(const std::vector<double> &charges) {
    std::vector<double> squares;
    squares.reserve(charges.size());
    for (const double charge : charges) {
        squares.push_back(charge * charge);
    }
    return accurate_sum(squares);
}

std::pair<double, double> two_difference(double first, double second) noexcept {
    const double difference = first - second;
    const double second_virtual = first - difference;
    const double first_virtual = difference + second_virtual;
    const double second_roundoff = second_virtual - second;
    const double first_roundoff = first - first_virtual;
    return {difference, first_roundoff + second_roundoff};
}

double add_to_expansion(double high, double low, double value) noexcept {
    const double sum = high + value;
    const double value_virtual = sum - high;
    const double high_virtual = sum - value_virtual;
    const double high_roundoff = high - high_virtual;
    const double value_roundoff = value - value_virtual;
    return sum + (low + high_roundoff + value_roundoff);
}

std::array<double, 3> reduce_position(
    const Vector3 &position,
    const std::array<double, 3> &lengths) noexcept {
    std::array<double, 3> reduced{};
    for (std::size_t axis = 0; axis < 3; ++axis) {
        const double length = lengths[axis];
        const double signed_residual = std::fmod(position[axis], length);
        double value = signed_residual < 0.0
                           ? signed_residual + length
                           : signed_residual;
        if (value == 0.0) {
            value = 0.0;
        } else if (bits(value) == bits(length)) {
            value = signed_residual == 0.0 ? 0.0 : signed_residual;
        } else if (value < 0.0) {
            value += length;
        } else if (value > length) {
            value -= length;
        }
        reduced[axis] = value;
    }
    return reduced;
}

int compare_primary_axis_separation(
    double first,
    double second,
    double length) noexcept {
    const double high = first > second ? first : second;
    const double low = first > second ? second : first;
    const auto [difference, error] = two_difference(high, low);
    const double half = 0.5 * length;
    if (total_order_key(difference) == total_order_key(half)) {
        if (total_order_key(error) == total_order_key(0.0)) {
            return 0;
        }
        return total_less(error, 0.0) ? -1 : 1;
    }
    return total_less(difference, half) ? -1 : 1;
}

Vector3 minimum_image(
    const Vector3 &first_position,
    const Vector3 &second_position,
    const std::array<double, 3> &lengths) noexcept {
    const Vector3 first = reduce_position(first_position, lengths);
    const Vector3 second = reduce_position(second_position, lengths);
    Vector3 delta{};
    for (std::size_t axis = 0; axis < 3; ++axis) {
        const double length = lengths[axis];
        const auto [raw, raw_error] = two_difference(first[axis], second[axis]);
        if (compare_primary_axis_separation(
                first[axis], second[axis], length) > 0) {
            delta[axis] = first[axis] > second[axis]
                              ? add_to_expansion(raw, raw_error, -length)
                              : add_to_expansion(raw, raw_error, length);
        } else {
            delta[axis] = raw;
        }
    }
    return delta;
}

Vector3 atom_position(const bg_system &system, std::size_t atom) noexcept {
    return {system.position_x[atom], system.position_y[atom],
            system.position_z[atom]};
}

double dot(const Vector3 &left, const Vector3 &right) noexcept {
    return left[0] * right[0] + left[1] * right[1] + left[2] * right[2];
}

double squared_norm(const Vector3 &vector) noexcept {
    return dot(vector, vector);
}

double cell_volume(std::array<double, 3> lengths) {
    std::sort(lengths.begin(), lengths.end(), total_less);
    return (lengths[0] * lengths[2]) * lengths[1];
}

bool checked_add(double *target, double value, Error *error, const char *context) {
    const double updated = *target + value;
    if (!std::isfinite(value) || !std::isfinite(updated)) {
        return set_error(
            error, BG_DIRECT_EWALD_ERROR_NONFINITE_RESULT,
            std::string(context) + " produced a non-finite value");
    }
    *target = updated;
    return true;
}

void push_pair_force_term(
    ForceTerms *terms,
    std::size_t atom_i,
    std::size_t atom_j,
    std::size_t axis,
    double component) {
    (*terms)[atom_i][axis].push_back(component);
    (*terms)[atom_j][axis].push_back(-component);
}

bool apply_canonical_force_terms(
    std::vector<Vector3> *forces,
    const ForceTerms &terms,
    Error *error,
    const char *context) {
    for (std::size_t atom = 0; atom < forces->size(); ++atom) {
        for (std::size_t axis = 0; axis < 3; ++axis) {
            if (!checked_add(
                    &(*forces)[atom][axis], accurate_sum(terms[atom][axis]),
                    error, context)) {
                return false;
            }
        }
    }
    return true;
}

bool validate_atom_arrays(
    const bg_system &system,
    const bg_direct_ewald_model_v1 &model,
    Error *error) {
    const std::size_t atom_count = system.position_x.size();
    if (atom_count == 0) {
        return set_error(
            error, BG_DIRECT_EWALD_ERROR_EMPTY_SYSTEM,
            "at least one atom is required");
    }
    if (atom_count > kMaxAtomCount) {
        return set_error(
            error, BG_DIRECT_EWALD_ERROR_CAPACITY_EXCEEDED,
            "atom count exceeds 4096");
    }
    if (system.position_y.size() != atom_count ||
        system.position_z.size() != atom_count ||
        system.charge.size() != atom_count || model.atom_count != atom_count) {
        return set_error(
            error, BG_DIRECT_EWALD_ERROR_CHARGE_COUNT_MISMATCH,
            "system position/charge count does not match the Ewald model");
    }
    for (std::size_t atom = 0; atom < atom_count; ++atom) {
        const Vector3 position = atom_position(system, atom);
        for (const double component : position) {
            if (!std::isfinite(component)) {
                return set_error(
                    error, BG_DIRECT_EWALD_ERROR_NONFINITE_COORDINATE,
                    "an atom has a non-finite coordinate");
            }
            if (std::abs(component) > kMaxAbsoluteCoordinateAngstrom) {
                return set_error(
                    error, BG_DIRECT_EWALD_ERROR_INVALID_PARAMETER,
                    "an atom coordinate exceeds 1e12 angstrom");
            }
        }
        const double charge = system.charge[atom];
        if (!std::isfinite(charge)) {
            return set_error(
                error, BG_DIRECT_EWALD_ERROR_NONFINITE_CHARGE,
                "an atom charge is not finite");
        }
        const double magnitude = std::abs(charge);
        if (magnitude > kMaxAbsoluteCharge ||
            (magnitude > 0.0 && magnitude < kMinNonzeroAbsoluteCharge)) {
            return set_error(
                error, BG_DIRECT_EWALD_ERROR_INVALID_PARAMETER,
                "nonzero charge magnitude must lie in [1e-12,16]");
        }
    }
    return true;
}

bool validate_work_limit(
    const bg_system &system,
    const bg_direct_ewald_model_v1 &model,
    Error *error) {
    std::size_t vector_count = 1;
    for (const int32_t maximum : model.reciprocal_max_indices) {
        const std::size_t dimension =
            static_cast<std::size_t>(2 * maximum + 1);
        if (vector_count > std::numeric_limits<std::size_t>::max() / dimension) {
            return set_error(
                error, BG_DIRECT_EWALD_ERROR_CAPACITY_EXCEEDED,
                "reciprocal vector count exceeds addressable capacity");
        }
        vector_count *= dimension;
    }
    --vector_count;
    const std::size_t atom_count = system.position_x.size();
    std::size_t pair_twice = 0;
    std::size_t phase_work = 0;
    if (!checked_multiply(
            atom_count, atom_count - 1U, &pair_twice) ||
        !checked_multiply(atom_count, vector_count, &phase_work) ||
        !checked_multiply(phase_work, 2U, &phase_work)) {
        return set_error(
            error, BG_DIRECT_EWALD_ERROR_CAPACITY_EXCEEDED,
            "pair or reciprocal phase work exceeds addressable capacity");
    }
    const std::size_t pair_count = pair_twice / 2U;
    double maximum_magnitude = 0.0;
    for (const double charge : system.charge) {
        if (std::abs(charge) != 0.0 &&
            (maximum_magnitude == 0.0 ||
             total_less(maximum_magnitude, std::abs(charge)))) {
            maximum_magnitude = std::abs(charge);
        }
    }
    std::size_t candidate_count = 0;
    if (maximum_magnitude != 0.0) {
        for (const double charge : system.charge) {
            if (bits(std::abs(charge)) == bits(maximum_magnitude)) {
                ++candidate_count;
            }
        }
    }
    std::size_t origin_work = 0;
    std::size_t pair_work = 0;
    std::size_t rule_work = 0;
    if (!checked_multiply(atom_count, candidate_count, &origin_work) ||
        !checked_multiply(pair_count, 7U, &pair_work) ||
        !checked_multiply(model.pair_rules.size(), 7U, &rule_work)) {
        return set_error(
            error, BG_DIRECT_EWALD_ERROR_CAPACITY_EXCEEDED,
            "pair accumulation work exceeds addressable capacity");
    }
    std::size_t total_work = 0;
    if (!checked_accumulate(pair_work, &total_work) ||
        !checked_accumulate(rule_work, &total_work) ||
        !checked_accumulate(phase_work, &total_work) ||
        !checked_accumulate(origin_work, &total_work) ||
        total_work > kMaxEvaluationWorkUnits) {
        return set_error(
            error, BG_DIRECT_EWALD_ERROR_CAPACITY_EXCEEDED,
            "combined evaluation work exceeds 10000000");
    }
    return true;
}

bool validate_input(
    const bg_system &system,
    const bg_direct_ewald_model_v1 &model,
    Error *error) {
    if (!validate_atom_arrays(system, model, error)) {
        return false;
    }
    if (accurate_sum(system.charge) != 0.0) {
        return set_error(
            error, BG_DIRECT_EWALD_ERROR_NON_NEUTRAL_SYSTEM,
            "total charge is not exactly zero");
    }
    return validate_work_limit(system, model, error);
}

using OriginEntry = std::array<double, 6>;

bool origin_entry_less(const OriginEntry &left, const OriginEntry &right) {
    for (std::size_t index = 0; index < left.size(); ++index) {
        if (total_order_key(left[index]) != total_order_key(right[index])) {
            return total_less(left[index], right[index]);
        }
    }
    return false;
}

std::vector<OriginEntry> phase_origin_signature(
    const bg_system &system,
    const bg_direct_ewald_model_v1 &model,
    std::size_t origin) {
    std::vector<OriginEntry> signature;
    signature.reserve(system.charge.size());
    const double origin_charge = system.charge[origin];
    const Vector3 origin_position = atom_position(system, origin);
    for (std::size_t atom = 0; atom < system.charge.size(); ++atom) {
        const double charge = system.charge[atom];
        if (charge == 0.0) {
            continue;
        }
        const Vector3 delta = minimum_image(
            atom_position(system, atom), origin_position,
            model.cell_lengths_angstrom);
        signature.push_back({
            std::abs(charge), charge * origin_charge, squared_norm(delta),
            delta[0], delta[1], delta[2]});
    }
    std::sort(signature.begin(), signature.end(), origin_entry_less);
    return signature;
}

bool signature_less(
    const std::vector<OriginEntry> &left,
    const std::vector<OriginEntry> &right) {
    const std::size_t common = std::min(left.size(), right.size());
    for (std::size_t index = 0; index < common; ++index) {
        if (origin_entry_less(left[index], right[index])) {
            return true;
        }
        if (origin_entry_less(right[index], left[index])) {
            return false;
        }
    }
    return left.size() < right.size();
}

Vector3 canonical_phase_origin(
    const bg_system &system,
    const bg_direct_ewald_model_v1 &model) {
    double maximum = 0.0;
    for (const double charge : system.charge) {
        const double magnitude = std::abs(charge);
        if (magnitude != 0.0 &&
            (maximum == 0.0 || total_less(maximum, magnitude))) {
            maximum = magnitude;
        }
    }
    if (maximum == 0.0) {
        return {};
    }
    std::vector<std::size_t> candidates;
    for (std::size_t atom = 0; atom < system.charge.size(); ++atom) {
        if (bits(std::abs(system.charge[atom])) == bits(maximum)) {
            candidates.push_back(atom);
        }
    }
    std::size_t selected = candidates.front();
    if (candidates.size() > 1U) {
        std::vector<OriginEntry> selected_signature =
            phase_origin_signature(system, model, selected);
        for (std::size_t index = 1; index < candidates.size(); ++index) {
            std::vector<OriginEntry> candidate_signature =
                phase_origin_signature(system, model, candidates[index]);
            if (signature_less(candidate_signature, selected_signature)) {
                selected = candidates[index];
                selected_signature = std::move(candidate_signature);
            }
        }
    }
    return atom_position(system, selected);
}

bool pair_correction_displacement(
    const Vector3 &first_position,
    const Vector3 &second_position,
    const std::array<double, 3> &lengths,
    Vector3 *out_delta,
    Error *error) {
    const Vector3 first = reduce_position(first_position, lengths);
    const Vector3 second = reduce_position(second_position, lengths);
    Vector3 delta{};
    for (std::size_t axis = 0; axis < 3; ++axis) {
        const double length = lengths[axis];
        const auto [raw, raw_error] = two_difference(first[axis], second[axis]);
        const int separation = compare_primary_axis_separation(
            first[axis], second[axis], length);
        const double half_length = 0.5 * length;
        const double expanded_separation =
            std::signbit(raw) ? -raw - raw_error : raw + raw_error;
        if (std::abs(expanded_separation - half_length) <=
            kPeriodicComparisonRelativeTolerance * half_length) {
            std::ostringstream message;
            message << "pair correction is within the periodic-image tolerance "
                       "of half a cell on axis "
                    << axis;
            return set_error(
                error, BG_DIRECT_EWALD_ERROR_AMBIGUOUS_PAIR_CORRECTION_IMAGE,
                message.str());
        }
        delta[axis] = separation > 0
                          ? (first[axis] > second[axis]
                                 ? add_to_expansion(raw, raw_error, -length)
                                 : add_to_expansion(raw, raw_error, length))
                          : raw;
    }
    *out_delta = delta;
    return true;
}

bool evaluate_real_space(
    const bg_system &system,
    const bg_direct_ewald_model_v1 &model,
    double coulomb_scale,
    bool compute_forces,
    Evaluation *result,
    Error *error) {
    std::vector<double> energy_terms;
    ForceTerms force_terms;
    if (compute_forces) {
        force_terms.resize(system.charge.size());
    }
    for (std::size_t atom_i = 0; atom_i < system.charge.size(); ++atom_i) {
        for (std::size_t atom_j = atom_i + 1U;
             atom_j < system.charge.size(); ++atom_j) {
            const double charge_product =
                system.charge[atom_i] * system.charge[atom_j];
            if (charge_product == 0.0) {
                continue;
            }
            const Vector3 delta = minimum_image(
                atom_position(system, atom_i), atom_position(system, atom_j),
                model.cell_lengths_angstrom);
            const double distance2 = squared_norm(delta);
            const double distance = std::sqrt(distance2);
            const double minimum_scale = std::max(
                std::abs(distance),
                std::abs(model.minimum_pair_distance_angstrom));
            if (std::abs(distance - model.minimum_pair_distance_angstrom) <=
                kPeriodicComparisonRelativeTolerance * minimum_scale) {
                return set_error(
                    error,
                    BG_DIRECT_EWALD_ERROR_AMBIGUOUS_MINIMUM_PAIR_DISTANCE,
                    "pair distance is within the periodic-image tolerance of "
                    "the minimum distance");
            }
            if (distance < model.minimum_pair_distance_angstrom) {
                return set_error(
                    error, BG_DIRECT_EWALD_ERROR_PAIR_BELOW_MINIMUM_DISTANCE,
                    "a pair is below the configured minimum distance");
            }
            const double cutoff_scale = std::max(
                std::abs(distance),
                std::abs(model.real_space_cutoff_angstrom));
            if (std::abs(distance - model.real_space_cutoff_angstrom) <=
                kPeriodicComparisonRelativeTolerance * cutoff_scale) {
                return set_error(
                    error, BG_DIRECT_EWALD_ERROR_AMBIGUOUS_REAL_SPACE_CUTOFF,
                    "pair distance is within the periodic-image tolerance of "
                    "the real-space cutoff");
            }
            if (distance <= model.real_space_cutoff_angstrom) {
                const double alpha_distance =
                    model.alpha_per_angstrom * distance;
                const double erfc_value = std::erfc(alpha_distance);
                const double exponential =
                    std::exp(-alpha_distance * alpha_distance);
                if (!std::isnormal(erfc_value) ||
                    !std::isnormal(exponential)) {
                    return set_error(
                        error, BG_DIRECT_EWALD_ERROR_DAMPING_UNDERFLOW,
                        "real-space damping is subnormal or zero");
                }
                const double charge_prefactor =
                    coulomb_scale * charge_product;
                const double pair_energy = distance < 1.0
                                               ? charge_prefactor *
                                                     (erfc_value / distance)
                                               : charge_prefactor * erfc_value /
                                                     distance;
                energy_terms.push_back(pair_energy);
                if (compute_forces) {
                    const double gaussian_prefactor =
                        charge_prefactor *
                        (2.0 * model.alpha_per_angstrom / std::sqrt(kPi));
                    const double radial_force_magnitude =
                        distance < 1.0
                            ? charge_prefactor * (erfc_value / distance2) +
                                  gaussian_prefactor * (exponential / distance)
                            : charge_prefactor * erfc_value / distance2 +
                                  gaussian_prefactor * exponential / distance;
                    for (std::size_t axis = 0; axis < 3; ++axis) {
                        const double component =
                            distance < 1.0
                                ? (radial_force_magnitude / distance) *
                                      delta[axis]
                                : (radial_force_magnitude * delta[axis]) /
                                      distance;
                        push_pair_force_term(
                            &force_terms, atom_i, atom_j, axis, component);
                    }
                }
            }
        }
    }
    if (!checked_add(
            &result->energy.real_space, accurate_sum(energy_terms), error,
            "real-space energy")) {
        return false;
    }
    return !compute_forces ||
           apply_canonical_force_terms(
               &result->forces, force_terms, error, "real-space force");
}

bool reciprocal_vector_is_provably_zero(
    std::size_t atom_count,
    double reciprocal_energy_factor,
    double reciprocal_force_factor,
    const Vector3 &wave,
    double wave2,
    double damping_exponent) {
    const double maximum_charge_sum =
        static_cast<double>(atom_count) * kMaxAbsoluteCharge;
    const double maximum_energy =
        std::abs(reciprocal_energy_factor) / wave2 * maximum_charge_sum *
        maximum_charge_sum;
    const double maximum_wave_component = std::max(
        {std::abs(wave[0]), std::abs(wave[1]), std::abs(wave[2])});
    const double maximum_force =
        std::abs(reciprocal_force_factor) * maximum_wave_component / wave2 *
        kMaxAbsoluteCharge * maximum_charge_sum;
    const double maximum_completed = std::max(maximum_energy, maximum_force);
    return std::isfinite(maximum_completed) &&
           std::log(maximum_completed) + damping_exponent <=
               kLnHalfMinimumPositiveSubnormal;
}

bool checked_phase(
    const Vector3 &wave,
    const Vector3 &position,
    double *out_phase,
    Error *error) {
    std::vector<double> terms{
        wave[0] * position[0], wave[1] * position[1],
        wave[2] * position[2]};
    for (std::size_t axis = 0; axis < 3; ++axis) {
        if (wave[axis] != 0.0 && position[axis] != 0.0 &&
            !std::isnormal(terms[axis])) {
            return set_error(
                error, BG_DIRECT_EWALD_ERROR_PHASE_UNDERFLOW,
                "reciprocal phase product is subnormal or zero");
        }
    }
    *out_phase = accurate_sum(terms);
    return true;
}

double apply_reciprocal_damping(
    double undamped_value,
    double damping_exponent,
    double exponential) {
    if (undamped_value == 0.0) {
        return 0.0;
    }
    if (std::isnormal(exponential)) {
        return undamped_value * exponential;
    }
    const double completed_log_magnitude =
        std::log(std::abs(undamped_value)) + damping_exponent;
    if (completed_log_magnitude <= kLnHalfMinimumPositiveSubnormal) {
        return 0.0;
    }
    const double magnitude = std::exp(completed_log_magnitude);
    return std::signbit(undamped_value) ? -magnitude : magnitude;
}

std::pair<double, double> canonical_structure_factor(
    const std::vector<double> &charges,
    const std::vector<std::pair<double, double>> &phases) {
    std::vector<double> cosine_terms;
    std::vector<double> sine_terms;
    cosine_terms.reserve(charges.size());
    sine_terms.reserve(charges.size());
    for (std::size_t atom = 0; atom < charges.size(); ++atom) {
        const double normalized_charge =
            charges[atom] / kChargeNormalizationScale;
        cosine_terms.push_back(normalized_charge * phases[atom].second);
        sine_terms.push_back(normalized_charge * phases[atom].first);
    }
    return {accurate_sum(cosine_terms), accurate_sum(sine_terms)};
}

double scaled_reciprocal_force_component(
    double reciprocal_force_factor,
    double wave_component,
    double wave2,
    double charge,
    const std::pair<double, double> &structure_cos_sin,
    const std::pair<double, double> &phase_sin_cos) {
    const double prefactor =
        reciprocal_force_factor * wave_component / wave2 * charge;
    return prefactor * structure_cos_sin.first * phase_sin_cos.first -
           prefactor * structure_cos_sin.second * phase_sin_cos.second;
}

bool evaluate_reciprocal_space(
    const bg_system &system,
    const bg_direct_ewald_model_v1 &model,
    double coulomb_scale,
    bool compute_forces,
    Evaluation *result,
    Error *error) {
    const double volume = cell_volume(model.cell_lengths_angstrom);
    const double reciprocal_energy_factor =
        coulomb_scale * 2.0 * kPi / volume;
    const double reciprocal_force_factor =
        coulomb_scale * 4.0 * kPi / volume;
    const double squared_charge_unit =
        kChargeNormalizationScale * kChargeNormalizationScale;
    const Vector3 origin = canonical_phase_origin(system, model);
    std::vector<Vector3> relative_positions;
    relative_positions.reserve(system.charge.size());
    for (std::size_t atom = 0; atom < system.charge.size(); ++atom) {
        relative_positions.push_back(
            system.charge[atom] == 0.0
                ? Vector3{}
                : minimum_image(
                      atom_position(system, atom), origin,
                      model.cell_lengths_angstrom));
    }
    for (int32_t nx = -model.reciprocal_max_indices[0];
         nx <= model.reciprocal_max_indices[0]; ++nx) {
        for (int32_t ny = -model.reciprocal_max_indices[1];
             ny <= model.reciprocal_max_indices[1]; ++ny) {
            for (int32_t nz = -model.reciprocal_max_indices[2];
                 nz <= model.reciprocal_max_indices[2]; ++nz) {
                if (nx == 0 && ny == 0 && nz == 0) {
                    continue;
                }
                const Vector3 wave{
                    kTau * static_cast<double>(nx) /
                        model.cell_lengths_angstrom[0],
                    kTau * static_cast<double>(ny) /
                        model.cell_lengths_angstrom[1],
                    kTau * static_cast<double>(nz) /
                        model.cell_lengths_angstrom[2]};
                const double wave2 = squared_norm(wave);
                const double damping_exponent =
                    -wave2 /
                    (4.0 * model.alpha_per_angstrom *
                     model.alpha_per_angstrom);
                const double exponential = std::exp(damping_exponent);
                if (reciprocal_vector_is_provably_zero(
                        system.charge.size(), reciprocal_energy_factor,
                        reciprocal_force_factor, wave, wave2,
                        damping_exponent)) {
                    continue;
                }
                std::vector<std::pair<double, double>> phases;
                phases.reserve(system.charge.size());
                for (std::size_t atom = 0; atom < system.charge.size(); ++atom) {
                    if (system.charge[atom] == 0.0) {
                        phases.emplace_back(0.0, 1.0);
                        continue;
                    }
                    double phase = 0.0;
                    if (!checked_phase(
                            wave, relative_positions[atom], &phase, error)) {
                        return false;
                    }
                    phases.emplace_back(std::sin(phase), std::cos(phase));
                }
                const auto structure =
                    canonical_structure_factor(system.charge, phases);
                const double scaled_energy_factor =
                    reciprocal_energy_factor * squared_charge_unit / wave2;
                const double undamped_energy =
                    scaled_energy_factor * structure.first * structure.first +
                    scaled_energy_factor * structure.second * structure.second;
                if (!checked_add(
                        &result->energy.reciprocal_space,
                        apply_reciprocal_damping(
                            undamped_energy, damping_exponent, exponential),
                        error, "reciprocal-space energy")) {
                    return false;
                }
                if (compute_forces) {
                    for (std::size_t atom = 0; atom < system.charge.size();
                         ++atom) {
                        for (std::size_t axis = 0; axis < 3; ++axis) {
                            const double undamped_force =
                                scaled_reciprocal_force_component(
                                    reciprocal_force_factor *
                                        squared_charge_unit,
                                    wave[axis], wave2,
                                    system.charge[atom] /
                                        kChargeNormalizationScale,
                                    structure, phases[atom]);
                            if (!checked_add(
                                    &result->forces[atom][axis],
                                    apply_reciprocal_damping(
                                        undamped_force, damping_exponent,
                                        exponential),
                                    error, "reciprocal force")) {
                                return false;
                            }
                        }
                    }
                }
            }
        }
    }
    return true;
}

bool evaluate_pair_corrections(
    const bg_system &system,
    const bg_direct_ewald_model_v1 &model,
    double coulomb_scale,
    bool compute_forces,
    Evaluation *result,
    Error *error) {
    std::vector<double> energy_terms;
    energy_terms.reserve(model.pair_rules.size());
    ForceTerms force_terms;
    if (compute_forces) {
        force_terms.resize(system.charge.size());
    }
    for (const PairRule &rule : model.pair_rules) {
        if (bits(rule.coulomb_scale) == bits(1.0)) {
            continue;
        }
        const double charge_product =
            system.charge[rule.atom_i] * system.charge[rule.atom_j];
        if (charge_product == 0.0) {
            continue;
        }
        Vector3 delta{};
        if (!pair_correction_displacement(
                atom_position(system, rule.atom_i),
                atom_position(system, rule.atom_j),
                model.cell_lengths_angstrom, &delta, error)) {
            return false;
        }
        const double distance2 = squared_norm(delta);
        const double distance = std::sqrt(distance2);
        const double correction_scale = rule.coulomb_scale - 1.0;
        energy_terms.push_back(
            coulomb_scale * charge_product * correction_scale / distance);
        if (compute_forces) {
            const double factor =
                coulomb_scale * charge_product * correction_scale /
                (distance2 * distance);
            for (std::size_t axis = 0; axis < 3; ++axis) {
                push_pair_force_term(
                    &force_terms, rule.atom_i, rule.atom_j, axis,
                    factor * delta[axis]);
            }
        }
    }
    if (!checked_add(
            &result->energy.pair_correction, accurate_sum(energy_terms), error,
            "pair-correction energy")) {
        return false;
    }
    return !compute_forces ||
           apply_canonical_force_terms(
               &result->forces, force_terms, error,
               "pair-correction force");
}

}  // namespace

bg_status evaluate(
    const bg_system &system,
    const bg_direct_ewald_model_v1 &model,
    bool compute_forces,
    Evaluation *out_evaluation,
    Error *out_error) {
    if (out_evaluation == nullptr || out_error == nullptr) {
        return BG_STATUS_INTERNAL_ERROR;
    }
    *out_error = Error{};
    if (!validate_input(system, model, out_error)) {
        return out_error->code == BG_DIRECT_EWALD_ERROR_CAPACITY_EXCEEDED
                   ? BG_STATUS_CAPACITY_OVERFLOW
                   : BG_STATUS_NUMERICAL_ERROR;
    }
    Evaluation result;
    if (compute_forces) {
        result.forces.assign(system.charge.size(), Vector3{});
    }
    const double coulomb_scale = kCoulombConstant / model.dielectric;
    if (!evaluate_real_space(
            system, model, coulomb_scale, compute_forces, &result,
            out_error) ||
        !evaluate_reciprocal_space(
            system, model, coulomb_scale, compute_forces, &result,
            out_error)) {
        return out_error->code == BG_DIRECT_EWALD_ERROR_CAPACITY_EXCEEDED
                   ? BG_STATUS_CAPACITY_OVERFLOW
                   : BG_STATUS_NUMERICAL_ERROR;
    }
    result.energy.self =
        -coulomb_scale * model.alpha_per_angstrom *
        accurate_charge_square_sum(system.charge) / std::sqrt(kPi);
    if (!evaluate_pair_corrections(
            system, model, coulomb_scale, compute_forces, &result,
            out_error)) {
        return BG_STATUS_NUMERICAL_ERROR;
    }
    if (!std::isfinite(result.energy.total())) {
        set_error(
            out_error, BG_DIRECT_EWALD_ERROR_NONFINITE_RESULT,
            "final energy is not finite");
        return BG_STATUS_NUMERICAL_ERROR;
    }
    for (const Vector3 &force : result.forces) {
        for (const double component : force) {
            if (!std::isfinite(component)) {
                set_error(
                    out_error, BG_DIRECT_EWALD_ERROR_NONFINITE_RESULT,
                    "final force is not finite");
                return BG_STATUS_NUMERICAL_ERROR;
            }
        }
    }
    *out_evaluation = std::move(result);
    return BG_STATUS_OK;
}

}  // namespace betelgeuze::native::ewald::cpp_cpu
