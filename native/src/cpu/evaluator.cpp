#include "evaluator.hpp"

#include "../internal.hpp"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <utility>

namespace betelgeuze::native::cpu {
namespace {

constexpr double kDegenerateSquaredAngstrom2 = 1.0e-24;
constexpr double kAngleCosineMargin = 1.0e-12;

struct Vector3 final {
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;

    [[nodiscard]] double dot(const Vector3 &other) const noexcept {
        return x * other.x + y * other.y + z * other.z;
    }

    [[nodiscard]] Vector3 cross(const Vector3 &other) const noexcept {
        return {
            y * other.z - z * other.y,
            z * other.x - x * other.z,
            x * other.y - y * other.x,
        };
    }

    [[nodiscard]] double squared_norm() const noexcept {
        return dot(*this);
    }

    [[nodiscard]] Vector3 scaled(double factor) const noexcept {
        return {x * factor, y * factor, z * factor};
    }

    [[nodiscard]] Vector3 plus(const Vector3 &other) const noexcept {
        return {x + other.x, y + other.y, z + other.z};
    }

    [[nodiscard]] Vector3 minus(const Vector3 &other) const noexcept {
        return {x - other.x, y - other.y, z - other.z};
    }
};

struct SwitchValue final {
    double value = 1.0;
    double derivative = 0.0;
};

struct PairScales final {
    double lennard_jones = 1.0;
    double coulomb = 1.0;
};

[[nodiscard]] bool is_finite(const Vector3 &value) noexcept {
    return std::isfinite(value.x) && std::isfinite(value.y) &&
           std::isfinite(value.z);
}

[[nodiscard]] bool storage_is_consistent(
    const bg_system &system,
    const bg_forcefield &forcefield) noexcept {
    const std::size_t atom_count = system.position_x.size();
    if (atom_count == 0 || system.position_y.size() != atom_count ||
        system.position_z.size() != atom_count ||
        system.velocity_x.size() != atom_count ||
        system.velocity_y.size() != atom_count ||
        system.velocity_z.size() != atom_count || system.mass.size() != atom_count ||
        system.charge.size() != atom_count || forcefield.atom_count != atom_count ||
        forcefield.sigma.size() != atom_count ||
        forcefield.epsilon.size() != atom_count) {
        return false;
    }

    const auto &bonds = forcefield.bonds;
    if (bonds.atom_i.size() != bonds.atom_j.size() ||
        bonds.atom_i.size() != bonds.equilibrium.size() ||
        bonds.atom_i.size() != bonds.force_constant.size()) {
        return false;
    }
    const auto &angles = forcefield.angles;
    if (angles.atom_i.size() != angles.atom_j.size() ||
        angles.atom_i.size() != angles.atom_k.size() ||
        angles.atom_i.size() != angles.equilibrium.size() ||
        angles.atom_i.size() != angles.force_constant.size()) {
        return false;
    }
    const auto &torsions = forcefield.torsions;
    return torsions.atom_i.size() == torsions.atom_j.size() &&
           torsions.atom_i.size() == torsions.atom_k.size() &&
           torsions.atom_i.size() == torsions.atom_l.size() &&
           torsions.atom_i.size() == torsions.periodicity.size() &&
           torsions.atom_i.size() == torsions.phase.size() &&
           torsions.atom_i.size() == torsions.amplitude.size();
}

[[nodiscard]] Vector3 displacement(
    const bg_system &system,
    const bg_forcefield &forcefield,
    std::size_t atom_i,
    std::size_t atom_j) noexcept {
    Vector3 result{
        system.position_x[atom_i] - system.position_x[atom_j],
        system.position_y[atom_i] - system.position_y[atom_j],
        system.position_z[atom_i] - system.position_z[atom_j],
    };
    double *const components[] = {&result.x, &result.y, &result.z};
    constexpr uint32_t axis_bits[] = {
        BG_PERIODIC_AXIS_X,
        BG_PERIODIC_AXIS_Y,
        BG_PERIODIC_AXIS_Z,
    };
    for (std::size_t axis = 0; axis < 3; ++axis) {
        if ((forcefield.periodic_axes_mask & axis_bits[axis]) != 0U) {
            const double length = forcefield.cell_lengths[axis];
            double &component = *components[axis];
            component -= length * std::floor(component / length + 0.5);
        }
    }
    return result;
}

bg_status checked_displacement(
    const bg_system &system,
    const bg_forcefield &forcefield,
    std::size_t atom_i,
    std::size_t atom_j,
    const char *error_message,
    Vector3 *out_value,
    double *out_squared_norm) noexcept {
    if (atom_i >= forcefield.atom_count || atom_j >= forcefield.atom_count) {
        return fail(BG_STATUS_INTERNAL_ERROR, "force-field atom index is out of range");
    }
    const Vector3 value = displacement(system, forcefield, atom_i, atom_j);
    const double squared_norm = value.squared_norm();
    if (!is_finite(value) || !std::isfinite(squared_norm)) {
        return fail(BG_STATUS_NUMERICAL_ERROR, error_message);
    }
    *out_value = value;
    *out_squared_norm = squared_norm;
    return BG_STATUS_OK;
}

bg_status checked_accumulate(
    double *target,
    double value,
    const char *error_message) noexcept {
    const double updated = *target + value;
    if (!std::isfinite(value) || !std::isfinite(updated)) {
        return fail(BG_STATUS_NUMERICAL_ERROR, error_message);
    }
    *target = updated;
    return BG_STATUS_OK;
}

bg_status checked_accumulate_force(
    Evaluation *evaluation,
    std::size_t atom,
    const Vector3 &value,
    const char *error_message) noexcept {
    const double updated_x = evaluation->force_x[atom] + value.x;
    const double updated_y = evaluation->force_y[atom] + value.y;
    const double updated_z = evaluation->force_z[atom] + value.z;
    if (!is_finite(value) || !std::isfinite(updated_x) ||
        !std::isfinite(updated_y) || !std::isfinite(updated_z)) {
        return fail(BG_STATUS_NUMERICAL_ERROR, error_message);
    }
    evaluation->force_x[atom] = updated_x;
    evaluation->force_y[atom] = updated_y;
    evaluation->force_z[atom] = updated_z;
    return BG_STATUS_OK;
}

[[nodiscard]] bool pair_is_excluded(
    const bg_forcefield &forcefield,
    std::size_t atom_i,
    std::size_t atom_j) noexcept {
    const bg_forcefield::Pair target{atom_i, atom_j};
    return std::binary_search(
        forcefield.exclusions.begin(), forcefield.exclusions.end(), target);
}

[[nodiscard]] PairScales pair_scales(
    const bg_forcefield &forcefield,
    std::size_t atom_i,
    std::size_t atom_j) noexcept {
    const bg_forcefield::Pair target{atom_i, atom_j};
    const auto found = std::lower_bound(
        forcefield.pair_scales.begin(),
        forcefield.pair_scales.end(),
        target,
        [](const bg_forcefield::PairScale &scale,
           const bg_forcefield::Pair &pair) noexcept {
            return scale.pair < pair;
        });
    if (found != forcefield.pair_scales.end() && found->pair == target) {
        return {found->lennard_jones, found->coulomb};
    }
    return {};
}

[[nodiscard]] SwitchValue switching_value(
    double distance,
    double start,
    double cutoff) noexcept {
    if (distance <= start) {
        return {1.0, 0.0};
    }
    if (distance >= cutoff) {
        return {0.0, 0.0};
    }
    const double width = cutoff - start;
    const double x = (distance - start) / width;
    const double x2 = x * x;
    const double x3 = x2 * x;
    const double x4 = x3 * x;
    const double x5 = x4 * x;
    const double value = 1.0 - 10.0 * x3 + 15.0 * x4 - 6.0 * x5;
    const double derivative =
        (-30.0 * x2 + 60.0 * x3 - 30.0 * x4) / width;
    return {value, derivative};
}

bg_status evaluate_bonds(
    const bg_system &system,
    const bg_forcefield &forcefield,
    bool compute_forces,
    Evaluation *evaluation) noexcept {
    for (std::size_t row = 0; row < forcefield.bonds.atom_i.size(); ++row) {
        const std::size_t atom_i = forcefield.bonds.atom_i[row];
        const std::size_t atom_j = forcefield.bonds.atom_j[row];
        Vector3 delta;
        double squared_distance = 0.0;
        bg_status status = checked_displacement(
            system,
            forcefield,
            atom_i,
            atom_j,
            "bond displacement is not finite",
            &delta,
            &squared_distance);
        if (status != BG_STATUS_OK) {
            return status;
        }
        // Unlike an angle or torsion, every strictly positive bond distance
        // has a defined radial gradient.  Reject only a distance whose square
        // is exactly zero (including multiplication underflow to zero).
        if (compute_forces && squared_distance <= 0.0) {
            return fail(BG_STATUS_NUMERICAL_ERROR, "bond has zero-length geometry");
        }

        const double distance = std::sqrt(squared_distance);
        const double difference = distance - forcefield.bonds.equilibrium[row];
        const double force_constant = forcefield.bonds.force_constant[row];
        const double energy = 0.5 * force_constant * difference * difference;
        status = checked_accumulate(
            &evaluation->energy.harmonic_bond_kcal_per_mol,
            energy,
            "bond produced a non-finite energy");
        if (status != BG_STATUS_OK) {
            return status;
        }
        if (!compute_forces) {
            continue;
        }

        const Vector3 force =
            delta.scaled(-force_constant * difference / distance);
        status = checked_accumulate_force(
            evaluation, atom_i, force, "bond produced a non-finite force");
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = checked_accumulate_force(
            evaluation,
            atom_j,
            force.scaled(-1.0),
            "bond produced a non-finite force");
        if (status != BG_STATUS_OK) {
            return status;
        }
    }
    return BG_STATUS_OK;
}

bg_status evaluate_angles(
    const bg_system &system,
    const bg_forcefield &forcefield,
    bool compute_forces,
    Evaluation *evaluation) noexcept {
    for (std::size_t row = 0; row < forcefield.angles.atom_i.size(); ++row) {
        const std::size_t atom_i = forcefield.angles.atom_i[row];
        const std::size_t atom_j = forcefield.angles.atom_j[row];
        const std::size_t atom_k = forcefield.angles.atom_k[row];
        Vector3 first;
        Vector3 second;
        double first_squared = 0.0;
        double second_squared = 0.0;
        bg_status status = checked_displacement(
            system,
            forcefield,
            atom_i,
            atom_j,
            "angle first arm is not finite",
            &first,
            &first_squared);
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = checked_displacement(
            system,
            forcefield,
            atom_k,
            atom_j,
            "angle second arm is not finite",
            &second,
            &second_squared);
        if (status != BG_STATUS_OK) {
            return status;
        }
        if (first_squared <= kDegenerateSquaredAngstrom2 ||
            second_squared <= kDegenerateSquaredAngstrom2) {
            return fail(BG_STATUS_NUMERICAL_ERROR, "angle has a zero-length arm");
        }

        const double first_length = std::sqrt(first_squared);
        const double second_length = std::sqrt(second_squared);
        const double denominator = first_length * second_length;
        const double raw_cosine = first.dot(second) / denominator;
        if (!std::isfinite(raw_cosine)) {
            return fail(BG_STATUS_NUMERICAL_ERROR, "angle cosine is not finite");
        }
        constexpr double lower_cosine = -1.0 + kAngleCosineMargin;
        constexpr double upper_cosine = 1.0 - kAngleCosineMargin;
        const double cosine = std::clamp(raw_cosine, lower_cosine, upper_cosine);
        const double angle = std::acos(cosine);
        const double difference = angle - forcefield.angles.equilibrium[row];
        const double force_constant = forcefield.angles.force_constant[row];
        const double energy = 0.5 * force_constant * difference * difference;
        status = checked_accumulate(
            &evaluation->energy.harmonic_angle_kcal_per_mol,
            energy,
            "angle produced a non-finite energy");
        if (status != BG_STATUS_OK) {
            return status;
        }
        if (!compute_forces) {
            continue;
        }

        // The oracle clamps cosine before acos.  Outside the unclamped interval
        // its implemented energy is locally constant, so its analytic force is
        // exactly zero rather than an unstable 1/sin(theta) extrapolation.
        if (raw_cosine <= lower_cosine || raw_cosine >= upper_cosine) {
            continue;
        }
        const double sine = std::sqrt(1.0 - cosine * cosine);
        const Vector3 first_unit = first.scaled(1.0 / first_length);
        const Vector3 second_unit = second.scaled(1.0 / second_length);
        const double derivative = force_constant * difference;
        const Vector3 force_i = second_unit
                                    .minus(first_unit.scaled(cosine))
                                    .scaled(derivative / (first_length * sine));
        const Vector3 force_k = first_unit
                                    .minus(second_unit.scaled(cosine))
                                    .scaled(derivative / (second_length * sine));
        const Vector3 force_j = force_i.plus(force_k).scaled(-1.0);
        status = checked_accumulate_force(
            evaluation, atom_i, force_i, "angle produced a non-finite force");
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = checked_accumulate_force(
            evaluation, atom_j, force_j, "angle produced a non-finite force");
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = checked_accumulate_force(
            evaluation, atom_k, force_k, "angle produced a non-finite force");
        if (status != BG_STATUS_OK) {
            return status;
        }
    }
    return BG_STATUS_OK;
}

bg_status evaluate_torsions(
    const bg_system &system,
    const bg_forcefield &forcefield,
    bool compute_forces,
    Evaluation *evaluation) noexcept {
    for (std::size_t row = 0; row < forcefield.torsions.atom_i.size(); ++row) {
        const std::size_t atom_i = forcefield.torsions.atom_i[row];
        const std::size_t atom_j = forcefield.torsions.atom_j[row];
        const std::size_t atom_k = forcefield.torsions.atom_k[row];
        const std::size_t atom_l = forcefield.torsions.atom_l[row];
        Vector3 b0;
        Vector3 b1;
        Vector3 b2;
        double b0_squared = 0.0;
        double central_squared = 0.0;
        double b2_squared = 0.0;
        bg_status status = checked_displacement(
            system,
            forcefield,
            atom_i,
            atom_j,
            "torsion first bond is not finite",
            &b0,
            &b0_squared);
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = checked_displacement(
            system,
            forcefield,
            atom_k,
            atom_j,
            "torsion central bond is not finite",
            &b1,
            &central_squared);
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = checked_displacement(
            system,
            forcefield,
            atom_l,
            atom_k,
            "torsion last bond is not finite",
            &b2,
            &b2_squared);
        if (status != BG_STATUS_OK) {
            return status;
        }
        (void)b0_squared;
        (void)b2_squared;
        if (central_squared <= kDegenerateSquaredAngstrom2) {
            return fail(
                BG_STATUS_NUMERICAL_ERROR,
                "torsion central bond has zero length");
        }

        const double central_length = std::sqrt(central_squared);
        const Vector3 axis = b1.scaled(1.0 / central_length);
        const Vector3 v = b0.minus(axis.scaled(b0.dot(axis)));
        const Vector3 w = b2.minus(axis.scaled(b2.dot(axis)));
        const double v_squared = v.squared_norm();
        const double w_squared = w.squared_norm();
        if (!is_finite(axis) || !is_finite(v) || !is_finite(w) ||
            !std::isfinite(v_squared) || !std::isfinite(w_squared) ||
            v_squared <= kDegenerateSquaredAngstrom2 ||
            w_squared <= kDegenerateSquaredAngstrom2) {
            return fail(
                BG_STATUS_NUMERICAL_ERROR,
                "torsion is undefined for collinear adjacent atoms");
        }

        const double sine_numerator = axis.cross(v).dot(w);
        const double cosine_numerator = v.dot(w);
        const double phi = std::atan2(sine_numerator, cosine_numerator);
        const double periodicity =
            static_cast<double>(forcefield.torsions.periodicity[row]);
        const double argument =
            periodicity * phi - forcefield.torsions.phase[row];
        const double amplitude = forcefield.torsions.amplitude[row];
        const double energy = amplitude * (1.0 + std::cos(argument));
        status = checked_accumulate(
            &evaluation->energy.periodic_torsion_kcal_per_mol,
            energy,
            "torsion produced a non-finite energy");
        if (status != BG_STATUS_OK) {
            return status;
        }
        if (!compute_forces) {
            continue;
        }

        // Convention: phi=atan2((b1_hat x v).w, v.w), with
        // b0=r_i-r_j, b1=r_k-r_j, and b2=r_l-r_k.  The endpoint
        // derivatives below therefore have signs opposite to formulas that
        // define the first bond as r_j-r_i.  Differentiating the normalized
        // b1 axis gives the central-bond derivative as a fixed combination of
        // those endpoint derivatives.
        const Vector3 gradient_b0 =
            axis.cross(v).scaled(-1.0 / v_squared);
        const Vector3 gradient_b2 =
            axis.cross(w).scaled(1.0 / w_squared);
        const Vector3 gradient_b1 = gradient_b0
                                        .scaled(-b0.dot(b1) / central_squared)
                                        .plus(gradient_b2.scaled(
                                            -b2.dot(b1) / central_squared));
        const Vector3 gradient_i = gradient_b0;
        const Vector3 gradient_j =
            gradient_b0.plus(gradient_b1).scaled(-1.0);
        const Vector3 gradient_k = gradient_b1.minus(gradient_b2);
        const Vector3 gradient_l = gradient_b2;
        const double force_factor =
            amplitude * periodicity * std::sin(argument);

        status = checked_accumulate_force(
            evaluation,
            atom_i,
            gradient_i.scaled(force_factor),
            "torsion produced a non-finite force");
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = checked_accumulate_force(
            evaluation,
            atom_j,
            gradient_j.scaled(force_factor),
            "torsion produced a non-finite force");
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = checked_accumulate_force(
            evaluation,
            atom_k,
            gradient_k.scaled(force_factor),
            "torsion produced a non-finite force");
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = checked_accumulate_force(
            evaluation,
            atom_l,
            gradient_l.scaled(force_factor),
            "torsion produced a non-finite force");
        if (status != BG_STATUS_OK) {
            return status;
        }
    }
    return BG_STATUS_OK;
}

bg_status evaluate_nonbonded(
    const bg_system &system,
    const bg_forcefield &forcefield,
    const std::vector<NeighborPair> *neighbor_pairs,
    bool compute_forces,
    Evaluation *evaluation);

using CellKey = std::array<std::size_t, 3>;
using CellAssignment = std::pair<CellKey, std::size_t>;

[[nodiscard]] double inclusive_squared_radius(double radius) noexcept {
    return std::nextafter(
        radius * radius, std::numeric_limits<double>::infinity());
}

[[nodiscard]] std::array<std::size_t, 3> periodic_cell_counts(
    const bg_forcefield &forcefield,
    double search_radius) noexcept {
    std::array<std::size_t, 3> counts{};
    for (std::size_t axis = 0; axis < counts.size(); ++axis) {
        const double count =
            std::floor(forcefield.cell_lengths[axis] / search_radius);
        counts[axis] = count >= static_cast<double>(forcefield.atom_count)
                           ? forcefield.atom_count
                           : std::max<std::size_t>(
                                 static_cast<std::size_t>(count), 1U);
    }
    return counts;
}

bg_status periodic_cell_key(
    const bg_system &system,
    const bg_forcefield &forcefield,
    const std::array<std::size_t, 3> &cell_counts,
    std::size_t atom,
    CellKey *out_key) noexcept {
    if (out_key == nullptr) {
        return fail(BG_STATUS_INTERNAL_ERROR, "neighbor-list cell output is null");
    }
    const std::array<double, 3> coordinates = {
        system.position_x[atom],
        system.position_y[atom],
        system.position_z[atom],
    };
    CellKey key{};
    for (std::size_t axis = 0; axis < key.size(); ++axis) {
        if (!std::isfinite(coordinates[axis])) {
            return fail(
                BG_STATUS_NUMERICAL_ERROR,
                "periodic neighbor-list coordinate is not finite");
        }
        const double length = forcefield.cell_lengths[axis];
        double wrapped = std::fmod(coordinates[axis], length);
        if (wrapped < 0.0) {
            wrapped += length;
        }
        const double width = length / static_cast<double>(cell_counts[axis]);
        const auto index = static_cast<std::size_t>(std::floor(wrapped / width));
        key[axis] = std::min(index, cell_counts[axis] - 1U);
    }
    *out_key = key;
    return BG_STATUS_OK;
}

[[nodiscard]] std::size_t offset_periodic_cell(
    std::size_t index,
    int offset,
    std::size_t count) noexcept {
    if (offset < 0) {
        return index == 0 ? count - 1U : index - 1U;
    }
    if (offset > 0) {
        return index + 1U == count ? 0U : index + 1U;
    }
    return index;
}

bg_status build_periodic_neighbor_pairs_impl(
    const bg_system &system,
    const bg_forcefield &forcefield,
    double search_radius,
    std::vector<NeighborPair> *out_pairs) {
    if (out_pairs == nullptr) {
        return fail(BG_STATUS_INTERNAL_ERROR, "neighbor-list pair output is null");
    }
    const double minimum_search_radius =
        std::max(forcefield.cutoff, forcefield.minimum_pair_distance);
    if (!std::isfinite(search_radius) ||
        search_radius < minimum_search_radius) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "periodic neighbor-list search radius is invalid");
    }
    const auto cell_counts = periodic_cell_counts(forcefield, search_radius);
    const double search_radius_squared =
        inclusive_squared_radius(search_radius);
    std::vector<CellKey> atom_cells(forcefield.atom_count);
    std::vector<CellAssignment> assignments;
    assignments.reserve(forcefield.atom_count);
    for (std::size_t atom = 0; atom < forcefield.atom_count; ++atom) {
        bg_status status = periodic_cell_key(
            system, forcefield, cell_counts, atom, &atom_cells[atom]);
        if (status != BG_STATUS_OK) {
            return status;
        }
        assignments.emplace_back(atom_cells[atom], atom);
    }
    std::sort(assignments.begin(), assignments.end());

    std::vector<NeighborPair> pairs;
    std::vector<CellKey> neighbor_cells;
    neighbor_cells.reserve(27U);
    std::vector<std::size_t> candidates;
    candidates.reserve(forcefield.atom_count);
    for (std::size_t atom_i = 0; atom_i < forcefield.atom_count; ++atom_i) {
        neighbor_cells.clear();
        const CellKey center = atom_cells[atom_i];
        for (int dx = -1; dx <= 1; ++dx) {
            for (int dy = -1; dy <= 1; ++dy) {
                for (int dz = -1; dz <= 1; ++dz) {
                    neighbor_cells.push_back({
                        offset_periodic_cell(center[0], dx, cell_counts[0]),
                        offset_periodic_cell(center[1], dy, cell_counts[1]),
                        offset_periodic_cell(center[2], dz, cell_counts[2]),
                    });
                }
            }
        }
        std::sort(neighbor_cells.begin(), neighbor_cells.end());
        neighbor_cells.erase(
            std::unique(neighbor_cells.begin(), neighbor_cells.end()),
            neighbor_cells.end());

        candidates.clear();
        for (const CellKey &key : neighbor_cells) {
            const auto begin = std::lower_bound(
                assignments.begin(),
                assignments.end(),
                key,
                [](const CellAssignment &row, const CellKey &target) {
                    return row.first < target;
                });
            const auto end = std::upper_bound(
                begin,
                assignments.end(),
                key,
                [](const CellKey &target, const CellAssignment &row) {
                    return target < row.first;
                });
            for (auto row = begin; row != end; ++row) {
                const std::size_t atom_j = row->second;
                if (atom_j > atom_i) {
                    candidates.push_back(atom_j);
                }
            }
        }
        std::sort(candidates.begin(), candidates.end());
        candidates.erase(
            std::unique(candidates.begin(), candidates.end()),
            candidates.end());
        for (const std::size_t atom_j : candidates) {
            Vector3 delta;
            double squared_distance = 0.0;
            const bg_status status = checked_displacement(
                system,
                forcefield,
                atom_i,
                atom_j,
                "nonbonded displacement is not finite",
                &delta,
                &squared_distance);
            if (status != BG_STATUS_OK) {
                return status;
            }
            if (squared_distance <= search_radius_squared) {
                pairs.push_back({atom_i, atom_j});
            }
        }
    }
    *out_pairs = std::move(pairs);
    return BG_STATUS_OK;
}

bg_status evaluate_nonbonded_pair(
    const bg_system &system,
    const bg_forcefield &forcefield,
    std::size_t atom_i,
    std::size_t atom_j,
    bool compute_forces,
    Evaluation *evaluation) noexcept {
    // Exclusion means that no nonbonded equation exists, so it must be
    // applied before the pair-distance singularity check.
    if (pair_is_excluded(forcefield, atom_i, atom_j)) {
        return BG_STATUS_OK;
    }

    Vector3 delta;
    double squared_distance = 0.0;
    bg_status status = checked_displacement(
        system,
        forcefield,
        atom_i,
        atom_j,
        "nonbonded displacement is not finite",
        &delta,
        &squared_distance);
    if (status != BG_STATUS_OK) {
        return status;
    }
    const double minimum = forcefield.minimum_pair_distance;
    if (squared_distance < minimum * minimum) {
        return fail(
            BG_STATUS_NUMERICAL_ERROR,
            "nonbonded pair is below minimum_pair_distance");
    }
    const double distance = std::sqrt(squared_distance);
    if (distance > forcefield.cutoff) {
        return BG_STATUS_OK;
    }

    const PairScales scales = pair_scales(forcefield, atom_i, atom_j);
    const double sigma =
        0.5 * (forcefield.sigma[atom_i] + forcefield.sigma[atom_j]);
    const double epsilon = std::sqrt(
        forcefield.epsilon[atom_i] * forcefield.epsilon[atom_j]);
    const double ratio = sigma / distance;
    const double ratio2 = ratio * ratio;
    const double ratio6 = ratio2 * ratio2 * ratio2;
    const double ratio12 = ratio6 * ratio6;
    const double lennard_jones =
        4.0 * epsilon * (ratio12 - ratio6) * scales.lennard_jones;

    const double screened_charge =
        system.charge[atom_i] * system.charge[atom_j] *
        std::exp(-forcefield.screening_kappa * distance);
    const double coulomb =
        BG_COULOMB_CONSTANT_KCAL_ANGSTROM_PER_MOL_E2 * screened_charge /
        (forcefield.dielectric * distance) * scales.coulomb;
    const SwitchValue switching = switching_value(
        distance, forcefield.switch_start, forcefield.cutoff);

    status = checked_accumulate(
        &evaluation->energy.lennard_jones_kcal_per_mol,
        lennard_jones * switching.value,
        "Lennard-Jones pair produced a non-finite energy");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = checked_accumulate(
        &evaluation->energy.coulomb_kcal_per_mol,
        coulomb * switching.value,
        "Coulomb pair produced a non-finite energy");
    if (status != BG_STATUS_OK || !compute_forces) {
        return status;
    }

    const double lennard_jones_derivative =
        24.0 * epsilon * scales.lennard_jones *
        (ratio6 - 2.0 * ratio12) / distance;
    const double coulomb_derivative =
        coulomb * (-forcefield.screening_kappa - 1.0 / distance);
    const double radial_derivative =
        lennard_jones_derivative * switching.value +
        lennard_jones * switching.derivative +
        coulomb_derivative * switching.value +
        coulomb * switching.derivative;
    const Vector3 force = delta.scaled(-radial_derivative / distance);
    status = checked_accumulate_force(
        evaluation,
        atom_i,
        force,
        "nonbonded pair produced a non-finite force");
    if (status != BG_STATUS_OK) {
        return status;
    }
    return checked_accumulate_force(
        evaluation,
        atom_j,
        force.scaled(-1.0),
        "nonbonded pair produced a non-finite force");
}

bg_status evaluate_nonbonded(
    const bg_system &system,
    const bg_forcefield &forcefield,
    const std::vector<NeighborPair> *neighbor_pairs,
    bool compute_forces,
    Evaluation *evaluation) {
    if (forcefield.periodic_axes_mask ==
        static_cast<uint32_t>(BG_PERIODIC_AXES_ALL)) {
        std::vector<NeighborPair> built_pairs;
        if (neighbor_pairs == nullptr) {
            const double search_radius =
                std::max(forcefield.cutoff, forcefield.minimum_pair_distance);
            bg_status status = build_periodic_neighbor_pairs_impl(
                system, forcefield, search_radius, &built_pairs);
            if (status != BG_STATUS_OK) {
                return status;
            }
            neighbor_pairs = &built_pairs;
        }
        NeighborPair previous{};
        bool has_previous = false;
        for (const NeighborPair &pair : *neighbor_pairs) {
            if (pair.atom_i >= pair.atom_j ||
                pair.atom_j >= forcefield.atom_count ||
                (has_previous && !(previous < pair))) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "neighbor pairs must be unique sorted in-range canonical pairs");
            }
            has_previous = true;
            previous = pair;
            const bg_status status = evaluate_nonbonded_pair(
                system,
                forcefield,
                pair.atom_i,
                pair.atom_j,
                compute_forces,
                evaluation);
            if (status != BG_STATUS_OK) {
                return status;
            }
        }
        return BG_STATUS_OK;
    }

    if (neighbor_pairs != nullptr) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "neighbor pairs require a fully periodic orthorhombic system");
    }

    for (std::size_t atom_i = 0; atom_i < forcefield.atom_count; ++atom_i) {
        for (std::size_t atom_j = atom_i + 1; atom_j < forcefield.atom_count;
             ++atom_j) {
            const bg_status status = evaluate_nonbonded_pair(
                system,
                forcefield,
                atom_i,
                atom_j,
                compute_forces,
                evaluation);
            if (status != BG_STATUS_OK) {
                return status;
            }
        }
    }
    return BG_STATUS_OK;
}

}  // namespace

bg_status evaluate_impl(
    const bg_system &system,
    const bg_forcefield &forcefield,
    const std::vector<NeighborPair> *neighbor_pairs,
    bool compute_forces,
    Evaluation *out_evaluation) {
    if (out_evaluation == nullptr) {
        return fail(BG_STATUS_INVALID_ARGUMENT, "evaluation output is null");
    }
    if (system.unit_system != BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL ||
        forcefield.unit_system != BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL ||
        system.unit_system != forcefield.unit_system) {
        return fail(BG_STATUS_INVALID_ARGUMENT, "evaluation unit systems do not match");
    }
    if (!storage_is_consistent(system, forcefield)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "system and force-field atom storage do not match");
    }

    Evaluation candidate;
    candidate.energy.struct_size =
        static_cast<uint32_t>(sizeof(bg_energy_components_v1));
    candidate.energy.abi_version = BG_ABI_VERSION;
    candidate.energy.unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
    if (compute_forces) {
        candidate.force_x.assign(forcefield.atom_count, 0.0);
        candidate.force_y.assign(forcefield.atom_count, 0.0);
        candidate.force_z.assign(forcefield.atom_count, 0.0);
    }

    bg_status status =
        evaluate_bonds(system, forcefield, compute_forces, &candidate);
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = evaluate_angles(system, forcefield, compute_forces, &candidate);
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = evaluate_torsions(system, forcefield, compute_forces, &candidate);
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = evaluate_nonbonded(
        system, forcefield, neighbor_pairs, compute_forces, &candidate);
    if (status != BG_STATUS_OK) {
        return status;
    }

    candidate.energy.total_kcal_per_mol =
        candidate.energy.harmonic_bond_kcal_per_mol +
        candidate.energy.harmonic_angle_kcal_per_mol +
        candidate.energy.periodic_torsion_kcal_per_mol +
        candidate.energy.lennard_jones_kcal_per_mol +
        candidate.energy.coulomb_kcal_per_mol;
    if (!std::isfinite(candidate.energy.total_kcal_per_mol)) {
        return fail(BG_STATUS_NUMERICAL_ERROR, "total energy is not finite");
    }
    if (compute_forces) {
        for (std::size_t atom = 0; atom < forcefield.atom_count; ++atom) {
            if (!std::isfinite(candidate.force_x[atom]) ||
                !std::isfinite(candidate.force_y[atom]) ||
                !std::isfinite(candidate.force_z[atom])) {
                return fail(
                    BG_STATUS_NUMERICAL_ERROR,
                    "force output is not finite");
            }
        }
    }

    *out_evaluation = std::move(candidate);
    return BG_STATUS_OK;
}

bg_status evaluate(
    const bg_system &system,
    const bg_forcefield &forcefield,
    bool compute_forces,
    Evaluation *out_evaluation) {
    return evaluate_impl(
        system, forcefield, nullptr, compute_forces, out_evaluation);
}

bg_status build_periodic_neighbor_pairs(
    const bg_system &system,
    const bg_forcefield &forcefield,
    double search_radius,
    std::vector<NeighborPair> *out_pairs) {
    if (forcefield.periodic_axes_mask !=
        static_cast<uint32_t>(BG_PERIODIC_AXES_ALL)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "periodic neighbor-list construction requires all periodic axes");
    }
    return build_periodic_neighbor_pairs_impl(
        system, forcefield, search_radius, out_pairs);
}

bg_status evaluate_with_neighbor_pairs(
    const bg_system &system,
    const bg_forcefield &forcefield,
    const std::vector<NeighborPair> &neighbor_pairs,
    bool compute_forces,
    Evaluation *out_evaluation) {
    return evaluate_impl(
        system,
        forcefield,
        &neighbor_pairs,
        compute_forces,
        out_evaluation);
}

}  // namespace betelgeuze::native::cpu
