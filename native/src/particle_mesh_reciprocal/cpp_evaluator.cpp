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
#include <utility>
#include <vector>

namespace betelgeuze::native::particle_mesh_reciprocal::cpp_cpu {
namespace {

constexpr std::size_t kAssignmentOrder = 4U;
constexpr std::size_t kMaxAtomCount = 4'096U;
constexpr std::size_t kMaxMeshPointCount = 1'048'576U;
constexpr double kMaxAbsoluteCoordinateAngstrom = 1.0e12;
constexpr double kMinNonzeroAbsoluteCharge = 1.0e-12;
constexpr double kMaxAbsoluteCharge = 16.0;
constexpr double kLnHalfMinimumPositiveSubnormal = -745.1332191019411;
constexpr double kRescueScale = 0x1.0p256;
constexpr double kLogRescueScale =
    177.44567822334599327471483452202978;
constexpr double kCoulombConstant =
    BG_COULOMB_CONSTANT_KCAL_ANGSTROM_PER_MOL_E2;
constexpr double kPi = 3.141592653589793238462643383279502884;
constexpr double kTau = 2.0 * kPi;

struct Complex final {
    double real = 0.0;
    double imaginary = 0.0;

    [[nodiscard]] Complex scaled(double factor) const noexcept {
        return {real * factor, imaginary * factor};
    }

    [[nodiscard]] double norm_squared() const noexcept {
        return real * real + imaginary * imaginary;
    }
};

struct CompensatedSum final {
    double sum = 0.0;
    double correction = 0.0;

    void add(double value) noexcept {
        const double updated = sum + value;
        correction += std::abs(sum) >= std::abs(value)
                          ? (sum - updated) + value
                          : (value - updated) + sum;
        sum = updated;
    }

    [[nodiscard]] double total() const noexcept {
        return sum + correction;
    }
};

struct AxisAssignment final {
    std::array<std::size_t, kAssignmentOrder> indices{};
    std::array<double, kAssignmentOrder> weights{};
    std::array<double, kAssignmentOrder> derivatives{};
};

struct ParticleAssignment final {
    std::array<AxisAssignment, 3> axes{};
};

struct AxisReciprocalData final {
    double wave_squared = 0.0;
    double assignment_modulus = 1.0;
};

struct OperatorResult final {
    double energy = 0.0;
    double grid_derivative_scale = 0.0;
};

bool set_error(
    Error *error,
    bg_particle_mesh_reciprocal_error_code code,
    std::string detail) {
    if (error != nullptr) {
        error->code = code;
        error->detail = std::move(detail);
    }
    return false;
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
    return (raw & sign) != 0U ? ~raw : raw | sign;
}

bool total_less(double left, double right) noexcept {
    return total_order_key(left) < total_order_key(right);
}

double accurate_order_independent_sum(const std::vector<double> &values) {
    std::vector<double> ordered(values);
    std::sort(ordered.begin(), ordered.end(), [](double left, double right) {
        const auto left_absolute = total_order_key(std::abs(left));
        const auto right_absolute = total_order_key(std::abs(right));
        return left_absolute == right_absolute
                   ? total_less(left, right)
                   : left_absolute < right_absolute;
    });
    CompensatedSum sum;
    for (const double value : ordered) {
        sum.add(value);
    }
    return sum.total();
}

std::size_t grid_index(
    std::size_t x,
    std::size_t y,
    std::size_t z,
    const std::array<std::size_t, 3> &dimensions) noexcept {
    return (x * dimensions[1] + y) * dimensions[2] + z;
}

Complex multiply(Complex left, Complex right) noexcept {
    return {
        left.real * right.real - left.imaginary * right.imaginary,
        left.real * right.imaginary + left.imaginary * right.real};
}

void transform_line(std::vector<Complex> *line, bool inverse) {
    const std::size_t count = line->size();
    std::size_t target = 0U;
    for (std::size_t source = 1U; source < count; ++source) {
        std::size_t bit = count >> 1U;
        while ((target & bit) != 0U) {
            target ^= bit;
            bit >>= 1U;
        }
        target ^= bit;
        if (source < target) {
            std::swap((*line)[source], (*line)[target]);
        }
    }
    for (std::size_t span = 2U; span <= count; span *= 2U) {
        const double direction = inverse ? 1.0 : -1.0;
        const double angle = direction * kTau / static_cast<double>(span);
        const Complex root{std::cos(angle), std::sin(angle)};
        for (std::size_t start = 0U; start < count; start += span) {
            Complex twiddle{1.0, 0.0};
            for (std::size_t offset = 0U; offset < span / 2U; ++offset) {
                const Complex even = (*line)[start + offset];
                const Complex odd = multiply(
                    (*line)[start + offset + span / 2U], twiddle);
                (*line)[start + offset] = {
                    even.real + odd.real,
                    even.imaginary + odd.imaginary};
                (*line)[start + offset + span / 2U] = {
                    even.real - odd.real,
                    even.imaginary - odd.imaginary};
                twiddle = multiply(twiddle, root);
            }
        }
        if (span > count / 2U) {
            break;
        }
    }
    if (inverse) {
        const double normalization = 1.0 / static_cast<double>(count);
        for (Complex &value : *line) {
            value = value.scaled(normalization);
        }
    }
}

void transform_3d(
    std::vector<Complex> *values,
    const std::array<std::size_t, 3> &dimensions,
    bool inverse) {
    const auto [x_count, y_count, z_count] = dimensions;
    const std::size_t line_capacity =
        std::max(x_count, std::max(y_count, z_count));
    std::vector<Complex> line;
    line.reserve(line_capacity);
    for (std::size_t x = 0U; x < x_count; ++x) {
        for (std::size_t y = 0U; y < y_count; ++y) {
            line.assign(z_count, Complex{});
            for (std::size_t z = 0U; z < z_count; ++z) {
                line[z] = (*values)[grid_index(x, y, z, dimensions)];
            }
            transform_line(&line, inverse);
            for (std::size_t z = 0U; z < z_count; ++z) {
                (*values)[grid_index(x, y, z, dimensions)] = line[z];
            }
        }
    }
    for (std::size_t x = 0U; x < x_count; ++x) {
        for (std::size_t z = 0U; z < z_count; ++z) {
            line.assign(y_count, Complex{});
            for (std::size_t y = 0U; y < y_count; ++y) {
                line[y] = (*values)[grid_index(x, y, z, dimensions)];
            }
            transform_line(&line, inverse);
            for (std::size_t y = 0U; y < y_count; ++y) {
                (*values)[grid_index(x, y, z, dimensions)] = line[y];
            }
        }
    }
    for (std::size_t y = 0U; y < y_count; ++y) {
        for (std::size_t z = 0U; z < z_count; ++z) {
            line.assign(x_count, Complex{});
            for (std::size_t x = 0U; x < x_count; ++x) {
                line[x] = (*values)[grid_index(x, y, z, dimensions)];
            }
            transform_line(&line, inverse);
            for (std::size_t x = 0U; x < x_count; ++x) {
                (*values)[grid_index(x, y, z, dimensions)] = line[x];
            }
        }
    }
}

double periodic_reduction(double coordinate, double length) noexcept {
    double reduced = std::fmod(coordinate, length);
    if (reduced < 0.0) {
        reduced += length;
    }
    if (reduced == 0.0 || bits(reduced) == bits(length)) {
        return 0.0;
    }
    if (reduced < 0.0) {
        return reduced + length;
    }
    if (reduced > length) {
        return reduced - length;
    }
    return reduced;
}

AxisAssignment make_axis_assignment(double scaled, std::size_t dimension) {
    const auto base = static_cast<std::size_t>(std::floor(scaled));
    const double fraction = scaled - static_cast<double>(base);
    const double square = fraction * fraction;
    const double cube = square * fraction;
    const double complement = 1.0 - fraction;
    AxisAssignment result;
    result.weights = {
        complement * complement * complement / 6.0,
        (3.0 * cube - 6.0 * square + 4.0) / 6.0,
        (-3.0 * cube + 3.0 * square + 3.0 * fraction + 1.0) / 6.0,
        cube / 6.0};
    result.derivatives = {
        -0.5 * complement * complement,
        1.5 * square - 2.0 * fraction,
        -1.5 * square + fraction + 0.5,
        0.5 * square};
    result.indices = {
        (base + dimension - 1U) % dimension,
        base % dimension,
        (base + 1U) % dimension,
        (base + 2U) % dimension};
    return result;
}

ParticleAssignment make_assignment(
    const bg_system &system,
    std::size_t atom,
    const bg_particle_mesh_reciprocal_model_v1 &model,
    const std::array<std::size_t, 3> &dimensions) {
    const std::array<double, 3> coordinate{
        system.position_x[atom], system.position_y[atom],
        system.position_z[atom]};
    ParticleAssignment result;
    for (std::size_t axis = 0U; axis < 3U; ++axis) {
        const double length = model.cell_lengths_angstrom[axis];
        const double dimension = static_cast<double>(dimensions[axis]);
        const double reduced = periodic_reduction(coordinate[axis], length);
        double scaled = reduced / length * dimension;
        if (scaled >= dimension) {
            scaled = 0.0;
        }
        result.axes[axis] =
            make_axis_assignment(scaled, dimensions[axis]);
    }
    return result;
}

std::vector<AxisReciprocalData> make_axis_reciprocal_data(
    std::size_t dimension,
    double cell_length) {
    std::vector<AxisReciprocalData> result(dimension);
    const auto signed_dimension = static_cast<std::int32_t>(dimension);
    for (std::size_t index = 0U; index < dimension; ++index) {
        const auto raw_index = static_cast<std::int32_t>(index);
        const auto signed_index = raw_index < signed_dimension / 2
                                      ? raw_index
                                      : raw_index - signed_dimension;
        const double wave =
            kTau * static_cast<double>(signed_index) / cell_length;
        const double angle =
            kTau * static_cast<double>(signed_index) /
            static_cast<double>(dimension);
        result[index] = {
            wave * wave, (2.0 + std::cos(angle)) / 3.0};
    }
    return result;
}

bool is_normal(double value) noexcept {
    return std::fpclassify(value) == FP_NORMAL;
}

double completed_positive_from_log(double log_magnitude) noexcept {
    return log_magnitude <= kLnHalfMinimumPositiveSubnormal
               ? 0.0
               : std::exp(log_magnitude);
}

double completed_scaled_component(double component, double log_scale) noexcept {
    if (component == 0.0) {
        return 0.0;
    }
    const double magnitude = completed_positive_from_log(
        log_scale + std::log(std::abs(component)));
    return std::signbit(component) ? -magnitude : magnitude;
}

double completed_squared_component(double component, double log_scale) noexcept {
    return component == 0.0
               ? 0.0
               : completed_positive_from_log(
                     log_scale + 2.0 * std::log(std::abs(component)));
}

bool mode_requires_log_rescue(
    Complex charge_mode,
    double damping,
    double influence,
    Complex regular_grid_mode,
    double regular_energy_mode) noexcept {
    const bool has_charge =
        charge_mode.real != 0.0 || charge_mode.imaginary != 0.0;
    return has_charge &&
           (!is_normal(damping) || !is_normal(influence) ||
            (charge_mode.real != 0.0 &&
             !is_normal(regular_grid_mode.real)) ||
            (charge_mode.imaginary != 0.0 &&
             !is_normal(regular_grid_mode.imaginary)) ||
            !is_normal(regular_energy_mode));
}

double complete_energy(
    double energy_prefactor,
    double regular_sum,
    double rescued_energy_scaled,
    bool has_rescued_energy) noexcept {
    if (!has_rescued_energy) {
        return energy_prefactor * regular_sum;
    }
    CompensatedSum combined;
    combined.add((energy_prefactor * kRescueScale) * regular_sum);
    combined.add(rescued_energy_scaled);
    return combined.total() / kRescueScale;
}

OperatorResult apply_operator(
    const bg_particle_mesh_reciprocal_model_v1 &model,
    const std::array<std::size_t, 3> &dimensions,
    double volume,
    std::vector<Complex> *spectrum) {
    const double energy_prefactor =
        kCoulombConstant / model.dielectric * kTau / volume;
    const double grid_derivative_scale =
        2.0 * energy_prefactor * static_cast<double>(spectrum->size());
    std::array<std::vector<AxisReciprocalData>, 3> axes;
    for (std::size_t axis = 0U; axis < 3U; ++axis) {
        axes[axis] = make_axis_reciprocal_data(
            dimensions[axis], model.cell_lengths_angstrom[axis]);
    }
    CompensatedSum regular_sum;
    CompensatedSum rescued_energy_scaled;
    bool has_rescued_energy = false;
    for (std::size_t x = 0U; x < dimensions[0]; ++x) {
        for (std::size_t y = 0U; y < dimensions[1]; ++y) {
            for (std::size_t z = 0U; z < dimensions[2]; ++z) {
                const std::size_t index = grid_index(x, y, z, dimensions);
                if (x == 0U && y == 0U && z == 0U) {
                    (*spectrum)[index] = {};
                    continue;
                }
                const double wave_squared =
                    axes[0][x].wave_squared + axes[1][y].wave_squared +
                    axes[2][z].wave_squared;
                const double assignment_modulus =
                    axes[0][x].assignment_modulus *
                    axes[1][y].assignment_modulus *
                    axes[2][z].assignment_modulus;
                const double damping_exponent =
                    -wave_squared /
                    (4.0 * model.alpha_per_angstrom *
                     model.alpha_per_angstrom);
                const double damping = std::exp(damping_exponent);
                const double influence =
                    damping / wave_squared /
                    (assignment_modulus * assignment_modulus);
                const Complex charge_mode = (*spectrum)[index];
                const Complex regular_grid_mode = charge_mode.scaled(influence);
                const double regular_energy_mode =
                    influence * charge_mode.norm_squared();
                if (mode_requires_log_rescue(
                        charge_mode, damping, influence, regular_grid_mode,
                        regular_energy_mode)) {
                    has_rescued_energy = true;
                    const double denominator_log =
                        std::log(wave_squared) +
                        2.0 * std::log(assignment_modulus);
                    const double energy_log_scale =
                        std::log(energy_prefactor) - denominator_log +
                        damping_exponent;
                    rescued_energy_scaled.add(completed_squared_component(
                        charge_mode.real,
                        energy_log_scale + kLogRescueScale));
                    rescued_energy_scaled.add(completed_squared_component(
                        charge_mode.imaginary,
                        energy_log_scale + kLogRescueScale));
                    const double influence_log_scale =
                        -denominator_log + damping_exponent +
                        kLogRescueScale;
                    (*spectrum)[index] = {
                        completed_scaled_component(
                            charge_mode.real, influence_log_scale),
                        completed_scaled_component(
                            charge_mode.imaginary, influence_log_scale)};
                } else {
                    regular_sum.add(regular_energy_mode);
                    (*spectrum)[index] = regular_grid_mode.scaled(kRescueScale);
                }
            }
        }
    }
    return {
        complete_energy(
            energy_prefactor, regular_sum.total(),
            rescued_energy_scaled.total(), has_rescued_energy),
        grid_derivative_scale};
}

std::vector<std::array<double, 3>> gather_forces(
    const std::vector<Complex> &grid_derivative,
    const std::array<std::size_t, 3> &dimensions,
    const std::vector<ParticleAssignment> &assignments,
    const std::vector<double> &charges,
    const bg_particle_mesh_reciprocal_model_v1 &model,
    double grid_derivative_multiplier) {
    std::vector<std::array<double, 3>> result(assignments.size());
    for (std::size_t atom = 0U; atom < assignments.size(); ++atom) {
        const ParticleAssignment &assignment = assignments[atom];
        for (std::size_t derivative_axis = 0U; derivative_axis < 3U;
             ++derivative_axis) {
            CompensatedSum derivative;
            for (std::size_t x_support = 0U;
                 x_support < kAssignmentOrder; ++x_support) {
                for (std::size_t y_support = 0U;
                     y_support < kAssignmentOrder; ++y_support) {
                    for (std::size_t z_support = 0U;
                         z_support < kAssignmentOrder; ++z_support) {
                        const std::array<std::size_t, 3> support{
                            x_support, y_support, z_support};
                        const std::size_t index = grid_index(
                            assignment.axes[0].indices[x_support],
                            assignment.axes[1].indices[y_support],
                            assignment.axes[2].indices[z_support],
                            dimensions);
                        double weight_derivative = 1.0;
                        for (std::size_t axis = 0U; axis < 3U; ++axis) {
                            weight_derivative *= axis == derivative_axis
                                ? assignment.axes[axis].derivatives[support[axis]]
                                : assignment.axes[axis].weights[support[axis]];
                        }
                        derivative.add(
                            grid_derivative[index].real * weight_derivative);
                    }
                }
            }
            const double force_scale =
                (-charges[atom] *
                 static_cast<double>(dimensions[derivative_axis]) /
                 model.cell_lengths_angstrom[derivative_axis]) *
                grid_derivative_multiplier;
            result[atom][derivative_axis] =
                force_scale * derivative.total();
        }
    }
    return result;
}

bool validate_system(
    const bg_system &system,
    const bg_particle_mesh_reciprocal_model_v1 &model,
    Error *error) {
    const std::size_t count = system.position_x.size();
    if (count == 0U) {
        return set_error(
            error, BG_PARTICLE_MESH_RECIPROCAL_ERROR_EMPTY_SYSTEM,
            "at least one particle is required");
    }
    if (count > kMaxAtomCount) {
        return set_error(
            error, BG_PARTICLE_MESH_RECIPROCAL_ERROR_CAPACITY_EXCEEDED,
            "particle count exceeds 4096");
    }
    if (system.position_y.size() != count ||
        system.position_z.size() != count || system.charge.size() != count ||
        model.atom_count != count) {
        return set_error(
            error, BG_PARTICLE_MESH_RECIPROCAL_ERROR_CHARGE_COUNT_MISMATCH,
            "system position/charge count does not match the particle-mesh reciprocal model");
    }
    for (std::size_t atom = 0U; atom < count; ++atom) {
        const std::array<double, 3> position{
            system.position_x[atom], system.position_y[atom],
            system.position_z[atom]};
        for (std::size_t axis = 0U; axis < 3U; ++axis) {
            if (!std::isfinite(position[axis])) {
                return set_error(
                    error,
                    BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONFINITE_COORDINATE,
                    "an atom has a non-finite coordinate");
            }
            if (std::abs(position[axis]) > kMaxAbsoluteCoordinateAngstrom) {
                return set_error(
                    error,
                    BG_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_PARAMETER,
                    "an atom coordinate exceeds 1e12 angstrom");
            }
        }
    }
    for (std::size_t atom = 0U; atom < count; ++atom) {
        const double charge = system.charge[atom];
        if (!std::isfinite(charge)) {
            return set_error(
                error, BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONFINITE_CHARGE,
                "an atom charge is not finite");
        }
        const double magnitude = std::abs(charge);
        if (magnitude > kMaxAbsoluteCharge ||
            (magnitude > 0.0 && magnitude < kMinNonzeroAbsoluteCharge)) {
            return set_error(
                error, BG_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_PARAMETER,
                "nonzero charge magnitude must lie in [1e-12,16]");
        }
    }
    const double total_charge =
        accurate_order_independent_sum(system.charge);
    if (total_charge != 0.0) {
        std::ostringstream detail;
        detail << "total charge " << total_charge << " is not exactly zero";
        return set_error(
            error, BG_PARTICLE_MESH_RECIPROCAL_ERROR_NON_NEUTRAL_SYSTEM,
            detail.str());
    }
    return true;
}

double cell_volume(const std::array<double, 3> &cell) {
    std::array<double, 3> sorted = cell;
    std::sort(sorted.begin(), sorted.end(), total_less);
    return (sorted[0] * sorted[2]) * sorted[1];
}

bool all_finite(
    double energy,
    const std::vector<Complex> &spectrum,
    const std::vector<std::array<double, 3>> &forces) noexcept {
    if (!std::isfinite(energy)) {
        return false;
    }
    for (const Complex value : spectrum) {
        if (!std::isfinite(value.real) || !std::isfinite(value.imaginary)) {
            return false;
        }
    }
    for (const auto &force : forces) {
        for (const double value : force) {
            if (!std::isfinite(value)) {
                return false;
            }
        }
    }
    return true;
}

}  // namespace

bg_status evaluate(
    const bg_system &system,
    const bg_particle_mesh_reciprocal_model_v1 &model,
    bool compute_forces,
    Evaluation *out_evaluation,
    Error *out_error) {
    if (out_evaluation == nullptr || out_error == nullptr) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "C++ particle-mesh reciprocal evaluation outputs must not be null");
    }
    *out_error = Error{};
    if (!validate_system(system, model, out_error)) {
        return BG_STATUS_INVALID_ARGUMENT;
    }

    const std::array<std::size_t, 3> dimensions{
        model.mesh_dimensions[0], model.mesh_dimensions[1],
        model.mesh_dimensions[2]};
    const std::size_t mesh_point_count =
        dimensions[0] * dimensions[1] * dimensions[2];
    if (mesh_point_count > kMaxMeshPointCount) {
        set_error(
            out_error, BG_PARTICLE_MESH_RECIPROCAL_ERROR_CAPACITY_EXCEEDED,
            "mesh point count exceeds 1048576");
        return BG_STATUS_CAPACITY_OVERFLOW;
    }

    std::vector<ParticleAssignment> assignments;
    assignments.reserve(model.atom_count);
    for (std::size_t atom = 0U; atom < model.atom_count; ++atom) {
        assignments.push_back(
            make_assignment(system, atom, model, dimensions));
    }
    std::vector<Complex> spectrum(mesh_point_count);
    for (std::size_t atom = 0U; atom < model.atom_count; ++atom) {
        const ParticleAssignment &assignment = assignments[atom];
        for (std::size_t x_support = 0U;
             x_support < kAssignmentOrder; ++x_support) {
            for (std::size_t y_support = 0U;
                 y_support < kAssignmentOrder; ++y_support) {
                for (std::size_t z_support = 0U;
                     z_support < kAssignmentOrder; ++z_support) {
                    const std::size_t index = grid_index(
                        assignment.axes[0].indices[x_support],
                        assignment.axes[1].indices[y_support],
                        assignment.axes[2].indices[z_support], dimensions);
                    spectrum[index].real +=
                        system.charge[atom] *
                        assignment.axes[0].weights[x_support] *
                        assignment.axes[1].weights[y_support] *
                        assignment.axes[2].weights[z_support];
                }
            }
        }
    }
    transform_3d(&spectrum, dimensions, false);
    const OperatorResult reciprocal = apply_operator(
        model, dimensions, cell_volume(model.cell_lengths_angstrom),
        &spectrum);

    Evaluation candidate;
    candidate.reciprocal_space_kcal_per_mol = reciprocal.energy;
    if (compute_forces) {
        transform_3d(&spectrum, dimensions, true);
        const double multiplier = reciprocal.grid_derivative_scale /
                                  kRescueScale;
        candidate.forces = gather_forces(
            spectrum, dimensions, assignments, system.charge, model,
            multiplier);
        for (Complex &value : spectrum) {
            value = value.scaled(multiplier);
        }
    }
    if (!all_finite(
            candidate.reciprocal_space_kcal_per_mol, spectrum,
            candidate.forces)) {
        set_error(
            out_error, BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONFINITE_RESULT,
            "reciprocal energy, grid derivative, or force is not finite");
        return BG_STATUS_NUMERICAL_ERROR;
    }
    *out_evaluation = std::move(candidate);
    return BG_STATUS_OK;
}

}  // namespace betelgeuze::native::particle_mesh_reciprocal::cpp_cpu
