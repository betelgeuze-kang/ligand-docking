#include "../internal.hpp"
#include "../hip/provider.h"
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

#ifndef BG_HAS_HIP_SAFE_PROVIDER
#  define BG_HAS_HIP_SAFE_PROVIDER 0
#endif

namespace betelgeuze::native::docking {
namespace {

constexpr std::size_t kCandidateCount = BG_DOCKING_FIXED64_CANDIDATE_COUNT;
constexpr std::size_t kTermCount = BG_DOCKING_SCORER_V1_TERM_COUNT;
constexpr std::size_t kMaxLigandAtoms = 512;
constexpr std::size_t kMaxReceptorAtoms = 4096;
constexpr std::size_t kMaxReceptorCandidatePairs = 4'000'000;
constexpr std::size_t kMaxLigandPairChecks = 250'000;
constexpr double kMaxCoordinate = 100'000.0;

struct Vec3 final {
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
};

struct Atom final {
    double charge = 0.0;
    double radius = 0.0;
    double epsilon = 0.0;
    bool hydrophobic = false;
    bool acceptor = false;
};

struct Donor final {
    std::size_t donor = 0;
    std::size_t hydrogen = 0;

    friend bool operator<(const Donor &left, const Donor &right) noexcept {
        return std::tie(left.donor, left.hydrogen) <
               std::tie(right.donor, right.hydrogen);
    }
};

using Pair = std::pair<std::size_t, std::size_t>;
using Rotor = std::array<std::size_t, 4>;
using Cell = std::tuple<int64_t, int64_t, int64_t>;

struct CppScorerContext final {
    std::vector<Vec3> receptor_coordinates;
    std::vector<Atom> receptor_atoms;
    std::vector<Vec3> ligand_reference_coordinates;
    std::vector<Atom> ligand_atoms;
    std::vector<Donor> receptor_donors;
    std::vector<Donor> ligand_donors;
    std::set<Pair> ligand_exclusions;
    std::vector<Rotor> rotors;
    std::vector<double> reference_dihedrals;
    double reference_internal_vdw = 0.0;
    std::size_t reference_ligand_pair_count = 0;
    Vec3 pocket_center;
    double pocket_radius = 0.0;
    std::array<double, kTermCount> weights{};
    double dielectric = 0.0;
    double pair_cutoff = 0.0;
    double hbond_cutoff = 0.0;
    double polar_burial_distance = 0.0;
    std::size_t max_receptor_candidate_pairs = 0;
    std::size_t max_ligand_pair_checks = 0;
    std::map<Cell, std::vector<std::size_t>> receptor_cells;
    std::vector<std::size_t> receptor_donor_by_hydrogen;
    std::vector<std::size_t> ligand_donor_by_hydrogen;
    std::vector<uint8_t> ligand_donor_heavy_mask;
};

constexpr std::size_t kNoDonor = static_cast<std::size_t>(-1);

[[nodiscard]] bool finite_coordinate(Vec3 value) noexcept {
    return std::isfinite(value.x) && std::isfinite(value.y) &&
           std::isfinite(value.z) && std::abs(value.x) <= kMaxCoordinate &&
           std::abs(value.y) <= kMaxCoordinate &&
           std::abs(value.z) <= kMaxCoordinate;
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

[[nodiscard]] Cell cell_key(Vec3 value, double cell_size) noexcept {
    return {
        static_cast<int64_t>(std::floor(value.x / cell_size)),
        static_cast<int64_t>(std::floor(value.y / cell_size)),
        static_cast<int64_t>(std::floor(value.z / cell_size)),
    };
}

[[nodiscard]] double typed_lj(
    double first_epsilon,
    double second_epsilon,
    double sigma,
    double distance) noexcept {
    if (distance <= 1.0e-8) {
        return 1.0e6;
    }
    const double ratio = std::min(sigma / distance, 2.0);
    const double squared = ratio * ratio;
    const double sixth = squared * squared * squared;
    return std::sqrt(first_epsilon * second_epsilon) *
           (sixth * sixth - 2.0 * sixth);
}

[[nodiscard]] double hbond_reward(
    Vec3 donor,
    Vec3 hydrogen,
    Vec3 acceptor,
    double cutoff) noexcept {
    const double distance = norm(minus(hydrogen, acceptor));
    if (distance > cutoff || distance <= 1.0e-8) {
        return 0.0;
    }
    const Vec3 first = minus(donor, hydrogen);
    const Vec3 second = minus(acceptor, hydrogen);
    const double denominator = norm(first) * norm(second);
    if (denominator <= 1.0e-12) {
        return 0.0;
    }
    const double cosine = dot(first, second) / denominator;
    const double angular = std::clamp((-cosine - 0.5) / 0.5, 0.0, 1.0);
    const double radial = std::max(1.0 - distance / cutoff, 0.0);
    return angular * radial;
}

[[nodiscard]] bool dihedral(
    const std::vector<Vec3> &coordinates,
    const Rotor &atoms,
    double *out_value) noexcept {
    const Vec3 first = coordinates[atoms[0]];
    const Vec3 second = coordinates[atoms[1]];
    const Vec3 third = coordinates[atoms[2]];
    const Vec3 fourth = coordinates[atoms[3]];
    const Vec3 middle = minus(third, second);
    const double middle_norm = norm(middle);
    if (middle_norm <= 1.0e-12) {
        return false;
    }
    const Vec3 axis = scale(middle, 1.0 / middle_norm);
    Vec3 left = minus(first, second);
    Vec3 right = minus(fourth, third);
    left = minus(left, scale(axis, dot(left, axis)));
    right = minus(right, scale(axis, dot(right, axis)));
    const double left_norm = norm(left);
    const double right_norm = norm(right);
    if (std::min(left_norm, right_norm) <= 1.0e-12) {
        return false;
    }
    left = scale(left, 1.0 / left_norm);
    right = scale(right, 1.0 / right_norm);
    *out_value = std::atan2(dot(cross(left, right), axis), dot(left, right));
    return true;
}

[[nodiscard]] bool digest_present(const uint8_t (&digest)[32]) noexcept {
    return std::any_of(
        std::begin(digest), std::end(digest), [](uint8_t value) {
            return value != UINT8_C(0);
        });
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

[[nodiscard]] bg_status validate_context_header(
    const bg_docking_scorer_v1_context_soa_v1 &descriptor) noexcept {
    bg_status status = validate_descriptor_header(
        descriptor.struct_size,
        sizeof(descriptor),
        descriptor.abi_version,
        "ScorerV1 context descriptor size does not match ABI v1",
        "ScorerV1 context descriptor ABI version does not match");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = validate_unit_system(descriptor.unit_system);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (descriptor.reserved0 != 0 || !reserved_is_zero(descriptor.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "ScorerV1 context reserved fields must be zero");
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status checked_scorer_counts(
    const bg_docking_scorer_v1_context_soa_v1 &descriptor,
    std::size_t *receptor_count,
    std::size_t *ligand_count,
    std::size_t *receptor_donor_count,
    std::size_t *ligand_donor_count,
    std::size_t *exclusion_count,
    std::size_t *rotor_count) noexcept {
    if (descriptor.receptor_atom_count == 0 ||
        descriptor.receptor_atom_count > kMaxReceptorAtoms ||
        descriptor.ligand_atom_count == 0 ||
        descriptor.ligand_atom_count > kMaxLigandAtoms ||
        descriptor.receptor_donor_count > descriptor.receptor_atom_count ||
        descriptor.ligand_donor_count > descriptor.ligand_atom_count ||
        descriptor.rotor_count > descriptor.ligand_atom_count) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "ScorerV1 context denominator is outside fixed native bounds");
    }
    const uint64_t maximum_exclusions =
        descriptor.ligand_atom_count * (descriptor.ligand_atom_count - 1) / 2;
    if (descriptor.ligand_exclusion_count > maximum_exclusions) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "ScorerV1 ligand exclusion denominator is impossible");
    }
    *receptor_count = static_cast<std::size_t>(descriptor.receptor_atom_count);
    *ligand_count = static_cast<std::size_t>(descriptor.ligand_atom_count);
    *receptor_donor_count =
        static_cast<std::size_t>(descriptor.receptor_donor_count);
    *ligand_donor_count =
        static_cast<std::size_t>(descriptor.ligand_donor_count);
    *exclusion_count =
        static_cast<std::size_t>(descriptor.ligand_exclusion_count);
    *rotor_count = static_cast<std::size_t>(descriptor.rotor_count);
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status validate_context_channels(
    const bg_docking_scorer_v1_context_soa_v1 &descriptor,
    std::size_t receptor_count,
    std::size_t ligand_count,
    std::size_t receptor_donor_count,
    std::size_t ligand_donor_count,
    std::size_t exclusion_count,
    std::size_t rotor_count) noexcept {
    const std::array<const double *, 6> receptor_double_channels = {
        descriptor.receptor_x_angstrom,
        descriptor.receptor_y_angstrom,
        descriptor.receptor_z_angstrom,
        descriptor.receptor_charge_elementary,
        descriptor.receptor_vdw_radius_angstrom,
        descriptor.receptor_epsilon_kcal_per_mol,
    };
    const std::array<const double *, 6> ligand_double_channels = {
        descriptor.ligand_reference_x_angstrom,
        descriptor.ligand_reference_y_angstrom,
        descriptor.ligand_reference_z_angstrom,
        descriptor.ligand_charge_elementary,
        descriptor.ligand_vdw_radius_angstrom,
        descriptor.ligand_epsilon_kcal_per_mol,
    };
    for (const double *channel : receptor_double_channels) {
        const bg_status status = require_channel(
            channel, receptor_count, "ScorerV1 receptor channel is null or misaligned");
        if (status != BG_STATUS_OK) {
            return status;
        }
    }
    for (const double *channel : ligand_double_channels) {
        const bg_status status = require_channel(
            channel, ligand_count, "ScorerV1 ligand channel is null or misaligned");
        if (status != BG_STATUS_OK) {
            return status;
        }
    }
    if (descriptor.receptor_hydrophobic == nullptr ||
        descriptor.receptor_acceptor == nullptr ||
        descriptor.ligand_hydrophobic == nullptr ||
        descriptor.ligand_acceptor == nullptr) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "ScorerV1 atom boolean channel must not be null");
    }
    const std::array<std::pair<const uint64_t *, std::size_t>, 10> index_channels = {{
        {descriptor.receptor_donor_atom_index, receptor_donor_count},
        {descriptor.receptor_hydrogen_atom_index, receptor_donor_count},
        {descriptor.ligand_donor_atom_index, ligand_donor_count},
        {descriptor.ligand_hydrogen_atom_index, ligand_donor_count},
        {descriptor.ligand_exclusion_atom_i, exclusion_count},
        {descriptor.ligand_exclusion_atom_j, exclusion_count},
        {descriptor.rotor_atom_i, rotor_count},
        {descriptor.rotor_atom_j, rotor_count},
        {descriptor.rotor_atom_k, rotor_count},
        {descriptor.rotor_atom_l, rotor_count},
    }};
    for (const auto &[channel, count] : index_channels) {
        const bg_status status = require_channel(
            channel, count, "ScorerV1 index channel is null or misaligned");
        if (status != BG_STATUS_OK) {
            return status;
        }
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status validate_config(
    const bg_docking_scorer_v1_context_soa_v1 &descriptor) noexcept {
    for (const double weight : descriptor.weights) {
        if (!std::isfinite(weight) || weight < 0.0 || weight > 100.0) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "ScorerV1 weight is outside the frozen range");
        }
    }
    if (!std::isfinite(descriptor.electrostatic_dielectric) ||
        descriptor.electrostatic_dielectric < 1.0 ||
        descriptor.electrostatic_dielectric > 100.0 ||
        !std::isfinite(descriptor.pair_cutoff_angstrom) ||
        descriptor.pair_cutoff_angstrom < 3.0 ||
        descriptor.pair_cutoff_angstrom > 20.0 ||
        !std::isfinite(descriptor.hbond_distance_max_angstrom) ||
        descriptor.hbond_distance_max_angstrom < 2.0 ||
        descriptor.hbond_distance_max_angstrom > 4.0 ||
        !std::isfinite(descriptor.polar_burial_distance_angstrom) ||
        descriptor.polar_burial_distance_angstrom < 3.0 ||
        descriptor.polar_burial_distance_angstrom > 8.0 ||
        descriptor.pair_cutoff_angstrom <
            std::max(
                descriptor.hbond_distance_max_angstrom,
                descriptor.polar_burial_distance_angstrom) ||
        descriptor.max_receptor_candidate_pairs == 0 ||
        descriptor.max_receptor_candidate_pairs > kMaxReceptorCandidatePairs ||
        descriptor.max_ligand_pair_checks == 0 ||
        descriptor.max_ligand_pair_checks > kMaxLigandPairChecks) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "ScorerV1 configuration is outside frozen bounds");
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status validate_and_copy_atoms(
    const double *x,
    const double *y,
    const double *z,
    const double *charge,
    const double *radius,
    const double *epsilon,
    const uint8_t *hydrophobic,
    const uint8_t *acceptor,
    std::size_t count,
    std::vector<Vec3> *coordinates,
    std::vector<Atom> *atoms) {
    coordinates->reserve(count);
    atoms->reserve(count);
    for (std::size_t index = 0; index < count; ++index) {
        const Vec3 coordinate{x[index], y[index], z[index]};
        if (!finite_coordinate(coordinate) || !std::isfinite(charge[index]) ||
            !std::isfinite(radius[index]) || radius[index] < 0.1 ||
            radius[index] > 10.0 || !std::isfinite(epsilon[index]) ||
            epsilon[index] <= 0.0 || epsilon[index] > 100.0 ||
            hydrophobic[index] > UINT8_C(1) || acceptor[index] > UINT8_C(1)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "ScorerV1 atom data are outside frozen bounds");
        }
        coordinates->push_back(coordinate);
        atoms->push_back(Atom{
            charge[index],
            radius[index],
            epsilon[index],
            hydrophobic[index] == UINT8_C(1),
            acceptor[index] == UINT8_C(1),
        });
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status copy_donors(
    const uint64_t *donor_indices,
    const uint64_t *hydrogen_indices,
    std::size_t count,
    std::size_t atom_count,
    std::vector<Donor> *out) {
    std::set<std::size_t> hydrogens;
    out->reserve(count);
    for (std::size_t row = 0; row < count; ++row) {
        if (donor_indices[row] >= atom_count ||
            hydrogen_indices[row] >= atom_count ||
            donor_indices[row] == hydrogen_indices[row]) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "ScorerV1 donor row is out of range");
        }
        Donor value{
            static_cast<std::size_t>(donor_indices[row]),
            static_cast<std::size_t>(hydrogen_indices[row]),
        };
        if ((!out->empty() && !(out->back() < value)) ||
            !hydrogens.insert(value.hydrogen).second) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "ScorerV1 donor rows are duplicated or noncanonical");
        }
        out->push_back(value);
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status copy_exclusions(
    const bg_docking_scorer_v1_context_soa_v1 &descriptor,
    std::size_t count,
    std::size_t ligand_count,
    std::set<Pair> *out) {
    Pair previous{};
    bool has_previous = false;
    for (std::size_t row = 0; row < count; ++row) {
        const uint64_t first = descriptor.ligand_exclusion_atom_i[row];
        const uint64_t second = descriptor.ligand_exclusion_atom_j[row];
        if (first >= second || second >= ligand_count) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "ScorerV1 exclusion row is not a canonical in-range pair");
        }
        const Pair value{
            static_cast<std::size_t>(first),
            static_cast<std::size_t>(second),
        };
        if ((has_previous && !(previous < value)) || !out->insert(value).second) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "ScorerV1 exclusion rows are duplicated or unsorted");
        }
        previous = value;
        has_previous = true;
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status copy_rotors(
    const bg_docking_scorer_v1_context_soa_v1 &descriptor,
    std::size_t count,
    std::size_t ligand_count,
    std::vector<Rotor> *out) {
    std::set<Rotor> unique;
    out->reserve(count);
    for (std::size_t row = 0; row < count; ++row) {
        const std::array<uint64_t, 4> raw = {
            descriptor.rotor_atom_i[row],
            descriptor.rotor_atom_j[row],
            descriptor.rotor_atom_k[row],
            descriptor.rotor_atom_l[row],
        };
        if (std::any_of(raw.begin(), raw.end(), [ligand_count](uint64_t value) {
                return value >= ligand_count;
            })) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "ScorerV1 rotor atom index is out of range");
        }
        Rotor value = {
            static_cast<std::size_t>(raw[0]),
            static_cast<std::size_t>(raw[1]),
            static_cast<std::size_t>(raw[2]),
            static_cast<std::size_t>(raw[3]),
        };
        if (!unique.insert(value).second) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "ScorerV1 rotor rows must be unique");
        }
        out->push_back(value);
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bool ligand_internal_vdw(
    const std::vector<Vec3> &coordinates,
    const std::vector<Atom> &atoms,
    const std::set<Pair> &exclusions,
    std::size_t maximum_pair_count,
    double *out_value,
    std::size_t *out_count) noexcept {
    double value = 0.0;
    std::size_t count = 0;
    for (std::size_t first = 0; first < coordinates.size(); ++first) {
        for (std::size_t second = first + 1; second < coordinates.size(); ++second) {
            if (exclusions.find({first, second}) != exclusions.end()) {
                continue;
            }
            ++count;
            if (count > maximum_pair_count) {
                *out_count = count;
                return false;
            }
            value += typed_lj(
                atoms[first].epsilon,
                atoms[second].epsilon,
                atoms[first].radius + atoms[second].radius,
                norm(minus(coordinates[first], coordinates[second])));
        }
    }
    *out_value = value;
    *out_count = count;
    return true;
}

[[nodiscard]] bg_status create_cpp_context(
    const bg_docking_scorer_v1_context_soa_v1 &descriptor,
    void **out_state) {
    std::size_t receptor_count = 0;
    std::size_t ligand_count = 0;
    std::size_t receptor_donor_count = 0;
    std::size_t ligand_donor_count = 0;
    std::size_t exclusion_count = 0;
    std::size_t rotor_count = 0;
    bg_status status = checked_scorer_counts(
        descriptor,
        &receptor_count,
        &ligand_count,
        &receptor_donor_count,
        &ligand_donor_count,
        &exclusion_count,
        &rotor_count);
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = validate_context_channels(
        descriptor,
        receptor_count,
        ligand_count,
        receptor_donor_count,
        ligand_donor_count,
        exclusion_count,
        rotor_count);
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = validate_config(descriptor);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (!digest_present(descriptor.authority_input_receipt_sha256) ||
        !digest_present(descriptor.receptor_system_sha256) ||
        !digest_present(descriptor.ligand_system_sha256) ||
        !digest_present(descriptor.backend_receipt_sha256)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "ScorerV1 identity digest must not be all zero");
    }
    const Vec3 pocket_center{
        descriptor.pocket_center_angstrom[0],
        descriptor.pocket_center_angstrom[1],
        descriptor.pocket_center_angstrom[2],
    };
    if (!finite_coordinate(pocket_center) ||
        !std::isfinite(descriptor.pocket_radius_angstrom) ||
        descriptor.pocket_radius_angstrom <= 0.0 ||
        descriptor.pocket_radius_angstrom > 1000.0) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "ScorerV1 pocket geometry is outside frozen bounds");
    }

    auto context = std::make_unique<CppScorerContext>();
    status = validate_and_copy_atoms(
        descriptor.receptor_x_angstrom,
        descriptor.receptor_y_angstrom,
        descriptor.receptor_z_angstrom,
        descriptor.receptor_charge_elementary,
        descriptor.receptor_vdw_radius_angstrom,
        descriptor.receptor_epsilon_kcal_per_mol,
        descriptor.receptor_hydrophobic,
        descriptor.receptor_acceptor,
        receptor_count,
        &context->receptor_coordinates,
        &context->receptor_atoms);
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = validate_and_copy_atoms(
        descriptor.ligand_reference_x_angstrom,
        descriptor.ligand_reference_y_angstrom,
        descriptor.ligand_reference_z_angstrom,
        descriptor.ligand_charge_elementary,
        descriptor.ligand_vdw_radius_angstrom,
        descriptor.ligand_epsilon_kcal_per_mol,
        descriptor.ligand_hydrophobic,
        descriptor.ligand_acceptor,
        ligand_count,
        &context->ligand_reference_coordinates,
        &context->ligand_atoms);
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = copy_donors(
        descriptor.receptor_donor_atom_index,
        descriptor.receptor_hydrogen_atom_index,
        receptor_donor_count,
        receptor_count,
        &context->receptor_donors);
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = copy_donors(
        descriptor.ligand_donor_atom_index,
        descriptor.ligand_hydrogen_atom_index,
        ligand_donor_count,
        ligand_count,
        &context->ligand_donors);
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = copy_exclusions(
        descriptor, exclusion_count, ligand_count, &context->ligand_exclusions);
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = copy_rotors(descriptor, rotor_count, ligand_count, &context->rotors);
    if (status != BG_STATUS_OK) {
        return status;
    }

    context->pocket_center = pocket_center;
    context->pocket_radius = descriptor.pocket_radius_angstrom;
    std::copy(std::begin(descriptor.weights), std::end(descriptor.weights), context->weights.begin());
    context->dielectric = descriptor.electrostatic_dielectric;
    context->pair_cutoff = descriptor.pair_cutoff_angstrom;
    context->hbond_cutoff = descriptor.hbond_distance_max_angstrom;
    context->polar_burial_distance = descriptor.polar_burial_distance_angstrom;
    context->max_receptor_candidate_pairs =
        static_cast<std::size_t>(descriptor.max_receptor_candidate_pairs);
    context->max_ligand_pair_checks =
        static_cast<std::size_t>(descriptor.max_ligand_pair_checks);

    context->reference_dihedrals.reserve(context->rotors.size());
    for (const Rotor &rotor : context->rotors) {
        double value = 0.0;
        if (!dihedral(context->ligand_reference_coordinates, rotor, &value)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "ScorerV1 reference rotor geometry is degenerate");
        }
        context->reference_dihedrals.push_back(value);
    }
    if (!ligand_internal_vdw(
            context->ligand_reference_coordinates,
            context->ligand_atoms,
            context->ligand_exclusions,
            context->max_ligand_pair_checks,
            &context->reference_internal_vdw,
            &context->reference_ligand_pair_count) ||
        !std::isfinite(context->reference_internal_vdw)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "ScorerV1 reference ligand pair capacity or value is invalid");
    }
    for (std::size_t index = 0; index < receptor_count; ++index) {
        context->receptor_cells[cell_key(
            context->receptor_coordinates[index], context->pair_cutoff)]
            .push_back(index);
    }
    context->receptor_donor_by_hydrogen.assign(receptor_count, kNoDonor);
    for (const Donor &donor : context->receptor_donors) {
        context->receptor_donor_by_hydrogen[donor.hydrogen] = donor.donor;
    }
    context->ligand_donor_by_hydrogen.assign(ligand_count, kNoDonor);
    context->ligand_donor_heavy_mask.assign(ligand_count, UINT8_C(0));
    for (const Donor &donor : context->ligand_donors) {
        context->ligand_donor_by_hydrogen[donor.hydrogen] = donor.donor;
        context->ligand_donor_heavy_mask[donor.donor] = UINT8_C(1);
    }
    *out_state = context.release();
    return BG_STATUS_OK;
}

[[nodiscard]] bg_docking_scorer_v1_row_v1 failure_row(
    std::size_t slot,
    bg_docking_scorer_v1_failure code,
    std::size_t receptor_pairs,
    std::size_t ligand_pairs) noexcept {
    bg_docking_scorer_v1_row_v1 row{};
    row.slot_index = static_cast<uint32_t>(slot);
    row.status = BG_DOCKING_SCORER_V1_ROW_TYPED_FAILURE;
    row.failure_code = code;
    row.receptor_candidate_pair_count = receptor_pairs;
    row.ligand_pair_count = ligand_pairs;
    return row;
}

[[nodiscard]] bg_docking_scorer_v1_row_v1 score_cpp_candidate(
    const CppScorerContext &context,
    const std::vector<Vec3> &pose,
    std::size_t slot) noexcept {
    if (pose.size() != context.ligand_atoms.size() ||
        std::any_of(pose.begin(), pose.end(), [](Vec3 value) {
            return !finite_coordinate(value);
        })) {
        return failure_row(
            slot,
            BG_DOCKING_SCORER_V1_FAILURE_INVALID_CANDIDATE_COORDINATES,
            0,
            0);
    }
    double typed_vdw_raw = 0.0;
    double electro_raw = 0.0;
    double hbond_raw = 0.0;
    double hydrophobic_raw = 0.0;
    std::size_t hbond_count = 0;
    std::size_t hydrophobic_count = 0;
    std::size_t receptor_pair_count = 0;
    std::vector<uint8_t> polar_buried(pose.size(), UINT8_C(0));
    std::vector<uint8_t> polar_satisfied(pose.size(), UINT8_C(0));
    for (std::size_t ligand_index = 0; ligand_index < pose.size(); ++ligand_index) {
        const Vec3 coordinate = pose[ligand_index];
        const Cell center = cell_key(coordinate, context.pair_cutoff);
        const int64_t center_x = std::get<0>(center);
        const int64_t center_y = std::get<1>(center);
        const int64_t center_z = std::get<2>(center);
        for (int64_t x = center_x - 1; x <= center_x + 1; ++x) {
            for (int64_t y = center_y - 1; y <= center_y + 1; ++y) {
                for (int64_t z = center_z - 1; z <= center_z + 1; ++z) {
                    const auto found = context.receptor_cells.find({x, y, z});
                    if (found == context.receptor_cells.end()) {
                        continue;
                    }
                    for (const std::size_t receptor_index : found->second) {
                        ++receptor_pair_count;
                        if (receptor_pair_count >
                            context.max_receptor_candidate_pairs) {
                            return failure_row(
                                slot,
                                BG_DOCKING_SCORER_V1_FAILURE_RECEPTOR_PAIR_CAPACITY,
                                receptor_pair_count,
                                0);
                        }
                        const double distance = norm(minus(
                            coordinate,
                            context.receptor_coordinates[receptor_index]));
                        if (distance > context.pair_cutoff) {
                            continue;
                        }
                        const Atom ligand_atom = context.ligand_atoms[ligand_index];
                        const Atom receptor_atom = context.receptor_atoms[receptor_index];
                        const double sigma = ligand_atom.radius + receptor_atom.radius;
                        typed_vdw_raw += typed_lj(
                            ligand_atom.epsilon,
                            receptor_atom.epsilon,
                            sigma,
                            distance);
                        electro_raw += ligand_atom.charge * receptor_atom.charge /
                                       (context.dielectric * std::max(distance, 0.5));
                        if (ligand_atom.hydrophobic && receptor_atom.hydrophobic &&
                            distance <= 1.25 * sigma) {
                            ++hydrophobic_count;
                            hydrophobic_raw +=
                                std::max(1.0 - distance / (1.25 * sigma), 0.0);
                        }
                        if ((ligand_atom.acceptor ||
                             context.ligand_donor_heavy_mask[ligand_index] != 0) &&
                            distance <= context.polar_burial_distance) {
                            polar_buried[ligand_index] = UINT8_C(1);
                        }
                        const std::size_t ligand_donor =
                            context.ligand_donor_by_hydrogen[ligand_index];
                        if (ligand_donor != kNoDonor && receptor_atom.acceptor) {
                            const double reward = hbond_reward(
                                pose[ligand_donor],
                                pose[ligand_index],
                                context.receptor_coordinates[receptor_index],
                                context.hbond_cutoff);
                            if (reward > 0.0) {
                                hbond_raw += reward;
                                ++hbond_count;
                                polar_satisfied[ligand_donor] = UINT8_C(1);
                            }
                        }
                        const std::size_t receptor_donor =
                            context.receptor_donor_by_hydrogen[receptor_index];
                        if (receptor_donor != kNoDonor && ligand_atom.acceptor) {
                            const double reward = hbond_reward(
                                context.receptor_coordinates[receptor_donor],
                                context.receptor_coordinates[receptor_index],
                                pose[ligand_index],
                                context.hbond_cutoff);
                            if (reward > 0.0) {
                                hbond_raw += reward;
                                ++hbond_count;
                                polar_satisfied[ligand_index] = UINT8_C(1);
                            }
                        }
                    }
                }
            }
        }
    }

    double current_internal_vdw = 0.0;
    std::size_t ligand_pair_count = 0;
    if (!ligand_internal_vdw(
            pose,
            context.ligand_atoms,
            context.ligand_exclusions,
            context.max_ligand_pair_checks,
            &current_internal_vdw,
            &ligand_pair_count)) {
        return failure_row(
            slot,
            BG_DOCKING_SCORER_V1_FAILURE_LIGAND_PAIR_CAPACITY,
            receptor_pair_count,
            ligand_pair_count);
    }
    const double ligand_strain_raw =
        std::max(current_internal_vdw - context.reference_internal_vdw, 0.0);
    double torsion_raw = 0.0;
    for (std::size_t index = 0; index < context.rotors.size(); ++index) {
        double observed = 0.0;
        if (!dihedral(pose, context.rotors[index], &observed)) {
            return failure_row(
                slot,
                BG_DOCKING_SCORER_V1_FAILURE_DEGENERATE_ROTOR,
                receptor_pair_count,
                ligand_pair_count);
        }
        const double difference = observed - context.reference_dihedrals[index];
        const double delta = std::atan2(std::sin(difference), std::cos(difference));
        torsion_raw += 0.5 * (1.0 - std::cos(3.0 * delta));
    }
    Vec3 centroid{};
    for (const Vec3 value : pose) {
        centroid.x += value.x;
        centroid.y += value.y;
        centroid.z += value.z;
    }
    centroid = scale(centroid, 1.0 / static_cast<double>(pose.size()));
    const double pocket_ratio =
        norm(minus(centroid, context.pocket_center)) / context.pocket_radius;
    const double pocket_raw = pocket_ratio * pocket_ratio;
    std::size_t buried_polar_count = 0;
    std::size_t unsatisfied_buried_count = 0;
    for (std::size_t index = 0; index < pose.size(); ++index) {
        if (polar_buried[index] != 0) {
            ++buried_polar_count;
            if (polar_satisfied[index] == 0) {
                ++unsatisfied_buried_count;
            }
        }
    }
    const std::array<double, kTermCount> raw = {
        typed_vdw_raw,
        electro_raw,
        -hbond_raw,
        -hydrophobic_raw,
        static_cast<double>(unsatisfied_buried_count),
        torsion_raw,
        ligand_strain_raw,
        pocket_raw,
    };
    bg_docking_scorer_v1_row_v1 row{};
    row.slot_index = static_cast<uint32_t>(slot);
    row.status = BG_DOCKING_SCORER_V1_ROW_SCORED;
    row.failure_code = BG_DOCKING_SCORER_V1_FAILURE_NONE;
    double total = 0.0;
    for (std::size_t index = 0; index < kTermCount; ++index) {
        row.weighted_terms[index] = raw[index] * context.weights[index];
        total += row.weighted_terms[index];
    }
    row.total_score = total;
    row.receptor_candidate_pair_count = receptor_pair_count;
    row.ligand_pair_count = ligand_pair_count;
    row.hbond_count = hbond_count;
    row.hydrophobic_contact_count = hydrophobic_count;
    row.buried_polar_count = buried_polar_count;
    if (!std::isfinite(total) ||
        std::any_of(
            std::begin(row.weighted_terms),
            std::end(row.weighted_terms),
            [](double value) { return !std::isfinite(value); })) {
        return failure_row(
            slot,
            BG_DOCKING_SCORER_V1_FAILURE_NONFINITE_SCORE,
            receptor_pair_count,
            ligand_pair_count);
    }
    return row;
}

[[nodiscard]] bg_status score_cpp_fixed64(
    const CppScorerContext &context,
    const bg_docking_scorer_v1_candidate_batch_soa_v1 &candidates,
    std::array<bg_docking_scorer_v1_row_v1, kCandidateCount> *out_rows) {
    const std::size_t ligand_count = context.ligand_atoms.size();
    std::vector<Vec3> pose(ligand_count);
    for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
        if (candidates.candidate_state[slot] ==
            BG_DOCKING_SCORER_V1_CANDIDATE_INACTIVE) {
            (*out_rows)[slot] = failure_row(
                slot,
                BG_DOCKING_SCORER_V1_FAILURE_UPSTREAM_NOT_ADMITTED,
                0,
                0);
            continue;
        }
        const std::size_t offset = slot * ligand_count;
        for (std::size_t atom = 0; atom < ligand_count; ++atom) {
            pose[atom] = {
                candidates.x_angstrom[offset + atom],
                candidates.y_angstrom[offset + atom],
                candidates.z_angstrom[offset + atom],
            };
        }
        (*out_rows)[slot] = score_cpp_candidate(context, pose, slot);
    }
    return BG_STATUS_OK;
}

[[nodiscard]] int32_t normalize_provider_status(int32_t status) noexcept {
    switch (status) {
        case BG_STATUS_OK:
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
            return status;
        default:
            return BG_STATUS_BACKEND_ERROR;
    }
}

void initialize_provider_error(bg_rust_cpu_error_v1 *error) noexcept {
    *error = bg_rust_cpu_error_v1{};
    error->struct_size = static_cast<uint32_t>(sizeof(*error));
    error->abi_version = BG_RUST_CPU_PROVIDER_ABI_VERSION;
}

[[nodiscard]] bg_status provider_failure(
    int32_t raw_status,
    bg_rust_cpu_error_v1 *error,
    const char *fallback) noexcept {
    const bg_status status = normalize_provider_status(raw_status);
    error->message[BG_RUST_CPU_ERROR_CAPACITY - 1U] = '\0';
    return fail(status, error->message[0] == '\0' ? fallback : error->message);
}

#if BG_HAS_HIP_SAFE_PROVIDER
[[nodiscard]] bg_status hip_provider_failure(
    int32_t raw_status,
    char *error,
    const char *fallback) noexcept {
    const bg_status status = normalize_provider_status(raw_status);
    error[BG_HIP_SAFE_ERROR_CAPACITY - 1U] = '\0';
    return fail(status, error[0] == '\0' ? fallback : error);
}
#endif

[[nodiscard]] bg_status validate_batch_and_output(
    const bg_docking_scorer_v1 *scorer,
    const bg_docking_scorer_v1_candidate_batch_soa_v1 &candidates,
    const bg_docking_scorer_v1_output_v1 &output) noexcept {
    bg_status status = validate_descriptor_header(
        candidates.struct_size,
        sizeof(candidates),
        candidates.abi_version,
        "ScorerV1 candidate batch size does not match ABI v1",
        "ScorerV1 candidate batch ABI version does not match");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = validate_descriptor_header(
        output.struct_size,
        sizeof(output),
        output.abi_version,
        "ScorerV1 output size does not match ABI v1",
        "ScorerV1 output ABI version does not match");
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (validate_unit_system(candidates.unit_system) != BG_STATUS_OK ||
        validate_unit_system(output.unit_system) != BG_STATUS_OK) {
        return BG_STATUS_INVALID_ARGUMENT;
    }
    if (candidates.reserved0 != 0 || !reserved_is_zero(candidates.reserved) ||
        output.reserved0 != 0 || !reserved_is_zero(output.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "ScorerV1 batch or output reserved fields must be zero");
    }
    if (candidates.candidate_count != kCandidateCount ||
        candidates.ligand_atom_count == 0 ||
        candidates.ligand_atom_count > kMaxLigandAtoms ||
        output.row_capacity < kCandidateCount || output.rows == nullptr ||
        !pointer_is_aligned(output.rows)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "ScorerV1 fixed64 denominator or output capacity is invalid");
    }
    if (scorer == nullptr) {
        return fail(BG_STATUS_INVALID_ARGUMENT, "ScorerV1 handle is null");
    }
    if (candidates.candidate_state == nullptr ||
        !pointer_is_aligned(candidates.candidate_state) ||
        candidates.x_angstrom == nullptr || candidates.y_angstrom == nullptr ||
        candidates.z_angstrom == nullptr ||
        !pointer_is_aligned(candidates.x_angstrom) ||
        !pointer_is_aligned(candidates.y_angstrom) ||
        !pointer_is_aligned(candidates.z_angstrom)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "ScorerV1 candidate channel is null or misaligned");
    }
    for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
        const auto state = candidates.candidate_state[slot];
        if (state != BG_DOCKING_SCORER_V1_CANDIDATE_INACTIVE &&
            state != BG_DOCKING_SCORER_V1_CANDIDATE_ACTIVE) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "ScorerV1 candidate state is not frozen inactive/active");
        }
    }
    return BG_STATUS_OK;
}

}  // namespace

void destroy_cpp_state(void *state) noexcept {
    delete static_cast<CppScorerContext *>(state);
}

}  // namespace betelgeuze::native::docking

extern "C" BG_API bg_status BG_CALL bg_docking_scorer_v1_context_soa_v1_init(
    bg_docking_scorer_v1_context_soa_v1 *descriptor,
    std::size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            descriptor,
            caller_struct_size,
            sizeof(*descriptor),
            caller_abi_version,
            "ScorerV1 context initializer pointer is null",
            "ScorerV1 context initializer size does not match",
            "ScorerV1 context initializer ABI version does not match");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *descriptor = bg_docking_scorer_v1_context_soa_v1{};
        descriptor->struct_size = static_cast<uint32_t>(sizeof(*descriptor));
        descriptor->abi_version = BG_ABI_VERSION;
        descriptor->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        descriptor->weights[0] = 1.0;
        descriptor->weights[1] = 0.35;
        descriptor->weights[2] = 1.5;
        descriptor->weights[3] = 0.6;
        descriptor->weights[4] = 0.4;
        descriptor->weights[5] = 0.15;
        descriptor->weights[6] = 0.5;
        descriptor->weights[7] = 0.05;
        descriptor->electrostatic_dielectric = 4.0;
        descriptor->pair_cutoff_angstrom = 8.0;
        descriptor->hbond_distance_max_angstrom = 3.0;
        descriptor->polar_burial_distance_angstrom = 4.5;
        descriptor->max_receptor_candidate_pairs = 1'000'000;
        descriptor->max_ligand_pair_checks = 250'000;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL
bg_docking_scorer_v1_candidate_batch_soa_v1_init(
    bg_docking_scorer_v1_candidate_batch_soa_v1 *batch,
    std::size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            batch,
            caller_struct_size,
            sizeof(*batch),
            caller_abi_version,
            "ScorerV1 batch initializer pointer is null",
            "ScorerV1 batch initializer size does not match",
            "ScorerV1 batch initializer ABI version does not match");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *batch = bg_docking_scorer_v1_candidate_batch_soa_v1{};
        batch->struct_size = static_cast<uint32_t>(sizeof(*batch));
        batch->abi_version = BG_ABI_VERSION;
        batch->candidate_count = BG_DOCKING_FIXED64_CANDIDATE_COUNT;
        batch->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_docking_scorer_v1_output_v1_init(
    bg_docking_scorer_v1_output_v1 *output,
    std::size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            output,
            caller_struct_size,
            sizeof(*output),
            caller_abi_version,
            "ScorerV1 output initializer pointer is null",
            "ScorerV1 output initializer size does not match",
            "ScorerV1 output initializer ABI version does not match");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *output = bg_docking_scorer_v1_output_v1{};
        output->struct_size = static_cast<uint32_t>(sizeof(*output));
        output->abi_version = BG_ABI_VERSION;
        output->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_docking_scorer_v1_create(
    const bg_context *context,
    const bg_docking_scorer_v1_context_soa_v1 *descriptor,
    bg_docking_scorer_v1 **out_scorer) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::docking;
    if (out_scorer != nullptr) {
        *out_scorer = nullptr;
    }
    return guarded_status([&]() -> bg_status {
        if (context == nullptr || descriptor == nullptr || out_scorer == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "ScorerV1 create inputs and output must not be null");
        }
        bg_status status = validate_context_header(*descriptor);
        if (status != BG_STATUS_OK) {
            return status;
        }
        auto scorer = std::make_unique<bg_docking_scorer_v1>();
        scorer->backend = context->backend;
        scorer->device_ordinal = context->device_ordinal;
        if (context->backend == BG_BACKEND_CPP_CPU_REFERENCE) {
            status = create_cpp_context(*descriptor, &scorer->provider_state);
        } else if (context->backend == BG_BACKEND_RUST_CPU) {
            bg_rust_cpu_error_v1 error{};
            initialize_provider_error(&error);
            const int32_t raw_status = bg_rust_cpu_docking_scorer_v1_create(
                descriptor, &scorer->provider_state, &error);
            if (raw_status != BG_STATUS_OK) {
                return provider_failure(
                    raw_status, &error, "rust_cpu ScorerV1 create failed");
            }
            status = BG_STATUS_OK;
        } else if (context->backend == BG_BACKEND_HIP_SAFE) {
#if BG_HAS_HIP_SAFE_PROVIDER
            void *qualification_raw = nullptr;
            status = create_cpp_context(*descriptor, &qualification_raw);
            if (status != BG_STATUS_OK) {
                return status;
            }
            std::unique_ptr<CppScorerContext> qualification(
                static_cast<CppScorerContext *>(qualification_raw));
            bg_hip_safe_docking_scorer_derived_v1 derived{};
            derived.struct_size = static_cast<uint32_t>(sizeof(derived));
            derived.abi_version = BG_HIP_SAFE_PROVIDER_ABI_VERSION;
            derived.reference_dihedrals_radians =
                qualification->reference_dihedrals.empty()
                    ? nullptr
                    : qualification->reference_dihedrals.data();
            derived.reference_internal_vdw =
                qualification->reference_internal_vdw;
            derived.receptor_donor_by_hydrogen =
                qualification->receptor_donor_by_hydrogen.data();
            derived.ligand_donor_by_hydrogen =
                qualification->ligand_donor_by_hydrogen.data();
            derived.ligand_donor_heavy_mask =
                qualification->ligand_donor_heavy_mask.data();
            char provider_error[BG_HIP_SAFE_ERROR_CAPACITY]{};
            const int32_t raw_status = bg_hip_safe_docking_scorer_v1_create(
                context->device_ordinal,
                descriptor,
                &derived,
                &scorer->provider_state,
                provider_error,
                sizeof(provider_error));
            if (raw_status != BG_STATUS_OK) {
                return hip_provider_failure(
                    raw_status,
                    provider_error,
                    "hip_safe ScorerV1 create failed");
            }
            status = BG_STATUS_OK;
#else
            return fail(
                BG_STATUS_BACKEND_UNAVAILABLE,
                "hip_safe ScorerV1 provider is not compiled; fallback is forbidden");
#endif
        } else if (context->backend == BG_BACKEND_HIP_FAST) {
            return fail(
                BG_STATUS_BACKEND_UNAVAILABLE,
                "hip_fast has no qualified ScorerV1 provider; fallback is forbidden");
        } else {
            return fail(
                BG_STATUS_UNSUPPORTED_BACKEND,
                "selected backend has no ScorerV1 implementation");
        }
        if (status != BG_STATUS_OK) {
            return status;
        }
        *out_scorer = scorer.release();
        return BG_STATUS_OK;
    });
}

extern "C" BG_API void BG_CALL bg_docking_scorer_v1_destroy(
    bg_docking_scorer_v1 *scorer) BG_NOEXCEPT {
    if (scorer == nullptr) {
        return;
    }
    if (scorer->backend == BG_BACKEND_CPP_CPU_REFERENCE) {
        betelgeuze::native::docking::destroy_cpp_state(scorer->provider_state);
    } else if (scorer->backend == BG_BACKEND_RUST_CPU) {
        bg_rust_cpu_docking_scorer_v1_destroy(scorer->provider_state);
#if BG_HAS_HIP_SAFE_PROVIDER
    } else if (scorer->backend == BG_BACKEND_HIP_SAFE) {
        bg_hip_safe_docking_scorer_v1_destroy(scorer->provider_state);
#endif
    }
    delete scorer;
}

extern "C" BG_API bg_status BG_CALL bg_docking_scorer_v1_get_backend(
    const bg_docking_scorer_v1 *scorer,
    bg_backend *backend) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        if (scorer == nullptr || backend == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "ScorerV1 handle and backend output must not be null");
        }
        *backend = scorer->backend;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_docking_scorer_v1_score_fixed64(
    const bg_context *context,
    const bg_docking_scorer_v1 *scorer,
    const bg_docking_scorer_v1_candidate_batch_soa_v1 *candidates,
    bg_docking_scorer_v1_output_v1 *out_rows) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::docking;
    return guarded_status([&]() -> bg_status {
        if (context == nullptr || scorer == nullptr || candidates == nullptr ||
            out_rows == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "ScorerV1 score inputs and output must not be null");
        }
        if (context->backend != scorer->backend ||
            context->device_ordinal != scorer->device_ordinal) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "ScorerV1 handle is cross-wired to another backend or device");
        }
        bg_status status = validate_batch_and_output(scorer, *candidates, *out_rows);
        if (status != BG_STATUS_OK) {
            return status;
        }
        std::array<bg_docking_scorer_v1_row_v1, kCandidateCount> candidate_rows{};
        if (scorer->backend == BG_BACKEND_CPP_CPU_REFERENCE) {
            const auto *state = static_cast<const CppScorerContext *>(
                scorer->provider_state);
            if (state == nullptr ||
                candidates->ligand_atom_count != state->ligand_atoms.size()) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "ScorerV1 candidate ligand denominator is cross-wired");
            }
            status = score_cpp_fixed64(*state, *candidates, &candidate_rows);
        } else if (scorer->backend == BG_BACKEND_RUST_CPU) {
            bg_rust_cpu_error_v1 error{};
            initialize_provider_error(&error);
            const int32_t raw_status =
                bg_rust_cpu_docking_scorer_v1_score_fixed64(
                    scorer->provider_state,
                    candidates,
                    candidate_rows.data(),
                    &error);
            if (raw_status != BG_STATUS_OK) {
                return provider_failure(
                    raw_status, &error, "rust_cpu ScorerV1 batch failed");
            }
            status = BG_STATUS_OK;
#if BG_HAS_HIP_SAFE_PROVIDER
        } else if (scorer->backend == BG_BACKEND_HIP_SAFE) {
            char provider_error[BG_HIP_SAFE_ERROR_CAPACITY]{};
            const int32_t raw_status =
                bg_hip_safe_docking_scorer_v1_score_fixed64(
                    scorer->provider_state,
                    candidates,
                    candidate_rows.data(),
                    provider_error,
                    sizeof(provider_error));
            if (raw_status != BG_STATUS_OK) {
                return hip_provider_failure(
                    raw_status,
                    provider_error,
                    "hip_safe ScorerV1 batch failed");
            }
            status = BG_STATUS_OK;
#endif
        } else {
            return fail(
                BG_STATUS_BACKEND_UNAVAILABLE,
                "selected backend has no qualified ScorerV1 kernel; fallback is forbidden");
        }
        if (status != BG_STATUS_OK) {
            return status;
        }
        std::copy(candidate_rows.begin(), candidate_rows.end(), out_rows->rows);
        out_rows->row_count = kCandidateCount;
        return BG_STATUS_OK;
    });
}
