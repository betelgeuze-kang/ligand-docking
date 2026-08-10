#include "internal.hpp"

#include <algorithm>
#include <array>
#include <cstring>
#include <memory>
#include <tuple>
#include <vector>

namespace betelgeuze::native {
namespace {

constexpr double kPi = 3.141592653589793238462643383279502884;

template <typename... Pointers>
bool counted_channels_are_present(
    std::size_t count,
    Pointers... pointers) noexcept {
    return count == 0 || ((pointers != nullptr) && ...);
}

template <typename... Pointers>
bool channels_are_aligned(Pointers... pointers) noexcept {
    return (pointer_is_aligned(pointers) && ...);
}

bg_status checked_owned_count(
    uint64_t observed_count,
    std::size_t bytes_per_row,
    const char *overflow_message,
    std::size_t *owned_bytes,
    std::size_t *out_count) noexcept {
    bg_status status = checked_element_count(
        observed_count,
        bytes_per_row,
        overflow_message,
        out_count);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (owned_bytes == nullptr) {
        return fail(BG_STATUS_INTERNAL_ERROR, "internal owned byte count is null");
    }
    if (*out_count >
        (std::numeric_limits<std::size_t>::max() - *owned_bytes) /
            bytes_per_row) {
        return fail(BG_STATUS_CAPACITY_OVERFLOW, overflow_message);
    }
    *owned_bytes += *out_count * bytes_per_row;
    return BG_STATUS_OK;
}

bg_status validate_descriptor(
    const bg_forcefield_soa_v1 &parameters) noexcept {
    bg_status status = validate_descriptor_header(
        parameters.struct_size,
        sizeof(bg_forcefield_soa_v1),
        parameters.abi_version,
        "bg_forcefield_soa_v1 struct_size does not match ABI v1",
        "bg_forcefield_soa_v1 abi_version does not match the native library");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = validate_unit_system(parameters.unit_system);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (!reserved_is_zero(parameters.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "bg_forcefield_soa_v1 reserved fields must be zero");
    }
    constexpr uint32_t allowed_axes =
        static_cast<uint32_t>(BG_PERIODIC_AXES_ALL);
    if ((parameters.periodic_axes_mask & ~allowed_axes) != UINT32_C(0)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "periodic_axes_mask contains unsupported bits");
    }
    if (parameters.atom_count == UINT64_C(0)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "force-field atom_count must be non-zero");
    }
    return BG_STATUS_OK;
}

bool finite_positive(double value) noexcept {
    return std::isfinite(value) && value > 0.0;
}

bool finite_nonnegative(double value) noexcept {
    return std::isfinite(value) && value >= 0.0;
}

bg_status validate_settings(const bg_forcefield_soa_v1 &parameters) noexcept {
    if (!finite_positive(parameters.cutoff_angstrom)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "cutoff_angstrom must be finite and positive");
    }
    if (!finite_nonnegative(parameters.switch_start_angstrom) ||
        parameters.switch_start_angstrom >= parameters.cutoff_angstrom) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "switch_start_angstrom must be finite, non-negative, and below cutoff");
    }
    if (!finite_positive(parameters.dielectric)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "dielectric must be finite and positive");
    }
    if (!finite_nonnegative(parameters.screening_kappa_per_angstrom)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "screening_kappa_per_angstrom must be finite and non-negative");
    }
    if (!finite_positive(parameters.minimum_pair_distance_angstrom)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "minimum_pair_distance_angstrom must be finite and positive");
    }

    if (parameters.periodic_axes_mask == UINT32_C(0)) {
        bool all_zero = true;
        for (double length : parameters.cell_lengths_angstrom) {
            all_zero = all_zero && length == 0.0;
        }
        if (!all_zero) {
            for (double length : parameters.cell_lengths_angstrom) {
                if (!finite_positive(length)) {
                    return fail(
                        BG_STATUS_INVALID_ARGUMENT,
                        "nonperiodic cell lengths must be all zero or all finite and positive");
                }
            }
        }
        return BG_STATUS_OK;
    }

    constexpr std::array<uint32_t, 3> axis_bits = {
        static_cast<uint32_t>(BG_PERIODIC_AXIS_X),
        static_cast<uint32_t>(BG_PERIODIC_AXIS_Y),
        static_cast<uint32_t>(BG_PERIODIC_AXIS_Z),
    };
    for (std::size_t axis = 0; axis < axis_bits.size(); ++axis) {
        const double length = parameters.cell_lengths_angstrom[axis];
        if (!finite_positive(length)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "periodic cells require three finite positive lengths");
        }
        if ((parameters.periodic_axes_mask & axis_bits[axis]) != UINT32_C(0) &&
            parameters.cutoff_angstrom >= 0.5 * length) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "cutoff must be strictly below half each periodic cell length");
        }
    }
    return BG_STATUS_OK;
}

template <std::size_t Count>
bg_status validate_indices(
    const std::array<uint64_t, Count> &indices,
    uint64_t atom_count,
    const char *range_message,
    const char *distinct_message) noexcept {
    for (std::size_t index = 0; index < Count; ++index) {
        if (indices[index] >= atom_count) {
            return fail(BG_STATUS_INVALID_ARGUMENT, range_message);
        }
        for (std::size_t prior = 0; prior < index; ++prior) {
            if (indices[index] == indices[prior]) {
                return fail(BG_STATUS_INVALID_ARGUMENT, distinct_message);
            }
        }
    }
    return BG_STATUS_OK;
}

bg_forcefield::Pair canonical_pair(uint64_t atom_i, uint64_t atom_j) noexcept {
    const uint64_t first = std::min(atom_i, atom_j);
    const uint64_t second = std::max(atom_i, atom_j);
    return bg_forcefield::Pair{
        static_cast<std::size_t>(first),
        static_cast<std::size_t>(second),
    };
}

uint64_t normalized_bits(double value) noexcept {
    if (value == 0.0) {
        return UINT64_C(0);
    }
    uint64_t bits = UINT64_C(0);
    static_assert(sizeof(bits) == sizeof(value));
    std::memcpy(&bits, &value, sizeof(bits));
    return bits;
}

template <typename Value>
bool sorted_has_duplicate(const std::vector<Value> &values) noexcept {
    return std::adjacent_find(values.begin(), values.end()) != values.end();
}

bg_status validate_and_copy_atom_parameters(
    const bg_forcefield_soa_v1 &parameters,
    std::size_t atom_count,
    bg_forcefield *forcefield) {
    forcefield->sigma = copy_channel(parameters.sigma_angstrom, atom_count);
    forcefield->epsilon =
        copy_channel(parameters.epsilon_kcal_per_mol, atom_count);
    for (std::size_t atom = 0; atom < atom_count; ++atom) {
        if (!finite_positive(forcefield->sigma[atom])) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "atom sigma values must be finite and positive");
        }
        if (!finite_nonnegative(forcefield->epsilon[atom])) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "atom epsilon values must be finite and non-negative");
        }
    }
    return BG_STATUS_OK;
}

bg_status validate_and_copy_bonds(
    const bg_forcefield_soa_v1 &parameters,
    std::size_t bond_count,
    bg_forcefield *forcefield) {
    auto &bonds = forcefield->bonds;
    bonds.atom_i.resize(bond_count);
    bonds.atom_j.resize(bond_count);
    bonds.equilibrium =
        copy_channel(parameters.bond_equilibrium_angstrom, bond_count);
    bonds.force_constant = copy_channel(
        parameters.bond_force_constant_kcal_per_mol_angstrom2,
        bond_count);

    std::vector<bg_forcefield::Pair> canonical_keys;
    canonical_keys.reserve(bond_count);
    for (std::size_t row = 0; row < bond_count; ++row) {
        const std::array<uint64_t, 2> indices = {
            parameters.bond_atom_i[row], parameters.bond_atom_j[row]};
        bg_status status = validate_indices(
            indices,
            parameters.atom_count,
            "bond atom index is out of range",
            "bond atom indices must be distinct");
        if (status != BG_STATUS_OK) {
            return status;
        }
        if (!finite_positive(bonds.equilibrium[row]) ||
            !finite_positive(bonds.force_constant[row])) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "bond equilibrium and force constant must be finite and positive");
        }
        bonds.atom_i[row] = static_cast<std::size_t>(indices[0]);
        bonds.atom_j[row] = static_cast<std::size_t>(indices[1]);
        canonical_keys.push_back(canonical_pair(indices[0], indices[1]));
    }
    std::sort(canonical_keys.begin(), canonical_keys.end());
    if (sorted_has_duplicate(canonical_keys)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "bond rows contain a canonical duplicate");
    }
    return BG_STATUS_OK;
}

bg_status validate_and_copy_angles(
    const bg_forcefield_soa_v1 &parameters,
    std::size_t angle_count,
    bg_forcefield *forcefield) {
    auto &angles = forcefield->angles;
    angles.atom_i.resize(angle_count);
    angles.atom_j.resize(angle_count);
    angles.atom_k.resize(angle_count);
    angles.equilibrium =
        copy_channel(parameters.angle_equilibrium_radians, angle_count);
    angles.force_constant = copy_channel(
        parameters.angle_force_constant_kcal_per_mol_radian2,
        angle_count);

    using AngleKey = std::array<std::size_t, 3>;
    std::vector<AngleKey> canonical_keys;
    canonical_keys.reserve(angle_count);
    for (std::size_t row = 0; row < angle_count; ++row) {
        const std::array<uint64_t, 3> indices = {
            parameters.angle_atom_i[row],
            parameters.angle_atom_j[row],
            parameters.angle_atom_k[row],
        };
        bg_status status = validate_indices(
            indices,
            parameters.atom_count,
            "angle atom index is out of range",
            "angle atom indices must be distinct");
        if (status != BG_STATUS_OK) {
            return status;
        }
        if (!std::isfinite(angles.equilibrium[row]) ||
            angles.equilibrium[row] <= 0.0 ||
            angles.equilibrium[row] >= kPi ||
            !finite_positive(angles.force_constant[row])) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "angle equilibrium must lie in (0,pi) and its force constant must be positive");
        }
        angles.atom_i[row] = static_cast<std::size_t>(indices[0]);
        angles.atom_j[row] = static_cast<std::size_t>(indices[1]);
        angles.atom_k[row] = static_cast<std::size_t>(indices[2]);
        canonical_keys.push_back(AngleKey{
            static_cast<std::size_t>(std::min(indices[0], indices[2])),
            static_cast<std::size_t>(indices[1]),
            static_cast<std::size_t>(std::max(indices[0], indices[2])),
        });
    }
    std::sort(canonical_keys.begin(), canonical_keys.end());
    if (sorted_has_duplicate(canonical_keys)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "angle rows contain a canonical duplicate");
    }
    return BG_STATUS_OK;
}

bg_status validate_and_copy_torsions(
    const bg_forcefield_soa_v1 &parameters,
    std::size_t torsion_count,
    bg_forcefield *forcefield) {
    auto &torsions = forcefield->torsions;
    torsions.atom_i.resize(torsion_count);
    torsions.atom_j.resize(torsion_count);
    torsions.atom_k.resize(torsion_count);
    torsions.atom_l.resize(torsion_count);
    if (torsion_count > 0) {
        torsions.periodicity.assign(
            parameters.torsion_periodicity,
            parameters.torsion_periodicity + torsion_count);
    }
    torsions.phase =
        copy_channel(parameters.torsion_phase_radians, torsion_count);
    torsions.amplitude =
        copy_channel(parameters.torsion_amplitude_kcal_per_mol, torsion_count);

    using TorsionKey =
        std::tuple<std::array<std::size_t, 4>, uint32_t, uint64_t>;
    std::vector<TorsionKey> canonical_keys;
    canonical_keys.reserve(torsion_count);
    for (std::size_t row = 0; row < torsion_count; ++row) {
        const std::array<uint64_t, 4> indices = {
            parameters.torsion_atom_i[row],
            parameters.torsion_atom_j[row],
            parameters.torsion_atom_k[row],
            parameters.torsion_atom_l[row],
        };
        bg_status status = validate_indices(
            indices,
            parameters.atom_count,
            "torsion atom index is out of range",
            "torsion atom indices must be distinct");
        if (status != BG_STATUS_OK) {
            return status;
        }
        if (torsions.periodicity[row] < UINT32_C(1) ||
            torsions.periodicity[row] > UINT32_C(12)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "torsion periodicity must lie in [1,12]");
        }
        if (!std::isfinite(torsions.phase[row]) ||
            !finite_nonnegative(torsions.amplitude[row])) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "torsion phase must be finite and amplitude must be finite and non-negative");
        }

        const std::array<std::size_t, 4> forward = {
            static_cast<std::size_t>(indices[0]),
            static_cast<std::size_t>(indices[1]),
            static_cast<std::size_t>(indices[2]),
            static_cast<std::size_t>(indices[3]),
        };
        const std::array<std::size_t, 4> reverse = {
            forward[3], forward[2], forward[1], forward[0]};
        const auto &canonical = std::min(forward, reverse);
        canonical_keys.emplace_back(
            canonical,
            torsions.periodicity[row],
            normalized_bits(torsions.phase[row]));
        torsions.atom_i[row] = forward[0];
        torsions.atom_j[row] = forward[1];
        torsions.atom_k[row] = forward[2];
        torsions.atom_l[row] = forward[3];
    }
    std::sort(canonical_keys.begin(), canonical_keys.end());
    if (sorted_has_duplicate(canonical_keys)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "torsion rows contain a canonical duplicate");
    }
    return BG_STATUS_OK;
}

bg_status validate_and_copy_pair_rules(
    const bg_forcefield_soa_v1 &parameters,
    std::size_t exclusion_count,
    std::size_t pair_scale_count,
    bg_forcefield *forcefield) {
    forcefield->exclusions.reserve(exclusion_count);
    for (std::size_t row = 0; row < exclusion_count; ++row) {
        const std::array<uint64_t, 2> indices = {
            parameters.exclusion_atom_i[row],
            parameters.exclusion_atom_j[row],
        };
        bg_status status = validate_indices(
            indices,
            parameters.atom_count,
            "exclusion atom index is out of range",
            "exclusion atom indices must be distinct");
        if (status != BG_STATUS_OK) {
            return status;
        }
        forcefield->exclusions.push_back(
            canonical_pair(indices[0], indices[1]));
    }
    std::sort(forcefield->exclusions.begin(), forcefield->exclusions.end());
    if (sorted_has_duplicate(forcefield->exclusions)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "exclusion rows contain a canonical duplicate");
    }

    forcefield->pair_scales.reserve(pair_scale_count);
    for (std::size_t row = 0; row < pair_scale_count; ++row) {
        const std::array<uint64_t, 2> indices = {
            parameters.pair_scale_atom_i[row],
            parameters.pair_scale_atom_j[row],
        };
        bg_status status = validate_indices(
            indices,
            parameters.atom_count,
            "pair scale atom index is out of range",
            "pair scale atom indices must be distinct");
        if (status != BG_STATUS_OK) {
            return status;
        }
        const double lennard_jones =
            parameters.pair_scale_lennard_jones[row];
        const double coulomb = parameters.pair_scale_coulomb[row];
        if (!std::isfinite(lennard_jones) || lennard_jones < 0.0 ||
            lennard_jones > 1.0 || !std::isfinite(coulomb) ||
            coulomb < 0.0 || coulomb > 1.0) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "pair scale values must be finite and lie in [0,1]");
        }
        forcefield->pair_scales.push_back(bg_forcefield::PairScale{
            canonical_pair(indices[0], indices[1]),
            lennard_jones,
            coulomb,
        });
    }
    std::sort(
        forcefield->pair_scales.begin(),
        forcefield->pair_scales.end(),
        [](const bg_forcefield::PairScale &left,
           const bg_forcefield::PairScale &right) noexcept {
            return left.pair < right.pair;
        });
    for (std::size_t row = 1; row < forcefield->pair_scales.size(); ++row) {
        if (forcefield->pair_scales[row - 1].pair ==
            forcefield->pair_scales[row].pair) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "pair scale rows contain a canonical duplicate");
        }
    }

    std::size_t exclusion = 0;
    std::size_t scale = 0;
    while (exclusion < forcefield->exclusions.size() &&
           scale < forcefield->pair_scales.size()) {
        const auto &excluded_pair = forcefield->exclusions[exclusion];
        const auto &scaled_pair = forcefield->pair_scales[scale].pair;
        if (excluded_pair == scaled_pair) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "a pair cannot be both excluded and scaled");
        }
        if (excluded_pair < scaled_pair) {
            ++exclusion;
        } else {
            ++scale;
        }
    }
    return BG_STATUS_OK;
}

bg_status validate_channel_contracts(
    const bg_forcefield_soa_v1 &parameters,
    std::size_t atom_count,
    std::size_t bond_count,
    std::size_t angle_count,
    std::size_t torsion_count,
    std::size_t exclusion_count,
    std::size_t pair_scale_count) noexcept {
    if (!counted_channels_are_present(
            atom_count, parameters.sigma_angstrom, parameters.epsilon_kcal_per_mol)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "non-empty force fields require sigma and epsilon channels");
    }
    if (!counted_channels_are_present(
            bond_count,
            parameters.bond_atom_i,
            parameters.bond_atom_j,
            parameters.bond_equilibrium_angstrom,
            parameters.bond_force_constant_kcal_per_mol_angstrom2)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "non-zero bond_count requires every bond channel");
    }
    if (!counted_channels_are_present(
            angle_count,
            parameters.angle_atom_i,
            parameters.angle_atom_j,
            parameters.angle_atom_k,
            parameters.angle_equilibrium_radians,
            parameters.angle_force_constant_kcal_per_mol_radian2)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "non-zero angle_count requires every angle channel");
    }
    if (!counted_channels_are_present(
            torsion_count,
            parameters.torsion_atom_i,
            parameters.torsion_atom_j,
            parameters.torsion_atom_k,
            parameters.torsion_atom_l,
            parameters.torsion_periodicity,
            parameters.torsion_phase_radians,
            parameters.torsion_amplitude_kcal_per_mol)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "non-zero torsion_count requires every torsion channel");
    }
    if (!counted_channels_are_present(
            exclusion_count,
            parameters.exclusion_atom_i,
            parameters.exclusion_atom_j)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "non-zero exclusion_count requires both exclusion channels");
    }
    if (!counted_channels_are_present(
            pair_scale_count,
            parameters.pair_scale_atom_i,
            parameters.pair_scale_atom_j,
            parameters.pair_scale_lennard_jones,
            parameters.pair_scale_coulomb)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "non-zero pair_scale_count requires every pair scale channel");
    }

    if (!channels_are_aligned(
            parameters.sigma_angstrom,
            parameters.epsilon_kcal_per_mol,
            parameters.bond_atom_i,
            parameters.bond_atom_j,
            parameters.bond_equilibrium_angstrom,
            parameters.bond_force_constant_kcal_per_mol_angstrom2,
            parameters.angle_atom_i,
            parameters.angle_atom_j,
            parameters.angle_atom_k,
            parameters.angle_equilibrium_radians,
            parameters.angle_force_constant_kcal_per_mol_radian2,
            parameters.torsion_atom_i,
            parameters.torsion_atom_j,
            parameters.torsion_atom_k,
            parameters.torsion_atom_l,
            parameters.torsion_periodicity,
            parameters.torsion_phase_radians,
            parameters.torsion_amplitude_kcal_per_mol,
            parameters.exclusion_atom_i,
            parameters.exclusion_atom_j,
            parameters.pair_scale_atom_i,
            parameters.pair_scale_atom_j,
            parameters.pair_scale_lennard_jones,
            parameters.pair_scale_coulomb)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "force-field channels must be naturally aligned");
    }
    return BG_STATUS_OK;
}

}  // namespace
}  // namespace betelgeuze::native

extern "C" BG_API bg_status BG_CALL bg_forcefield_soa_v1_init(
    bg_forcefield_soa_v1 *forcefield,
    std::size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            forcefield,
            caller_struct_size,
            sizeof(bg_forcefield_soa_v1),
            caller_abi_version,
            "bg_forcefield_soa_v1 pointer must not be null",
            "bg_forcefield_soa_v1 initializer size does not match the native ABI",
            "bg_forcefield_soa_v1 initializer ABI version does not match");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *forcefield = bg_forcefield_soa_v1{};
        forcefield->struct_size =
            static_cast<uint32_t>(sizeof(bg_forcefield_soa_v1));
        forcefield->abi_version = BG_ABI_VERSION;
        forcefield->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        forcefield->cutoff_angstrom = 10.0;
        forcefield->switch_start_angstrom = 8.0;
        forcefield->dielectric = 1.0;
        forcefield->minimum_pair_distance_angstrom = 1.0e-6;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_force_soa_v1_init(
    bg_force_soa_v1 *forces,
    std::size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            forces,
            caller_struct_size,
            sizeof(bg_force_soa_v1),
            caller_abi_version,
            "bg_force_soa_v1 pointer must not be null",
            "bg_force_soa_v1 initializer size does not match the native ABI",
            "bg_force_soa_v1 initializer ABI version does not match");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *forces = bg_force_soa_v1{};
        forces->struct_size = static_cast<uint32_t>(sizeof(bg_force_soa_v1));
        forces->abi_version = BG_ABI_VERSION;
        forces->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_energy_components_v1_init(
    bg_energy_components_v1 *energy,
    std::size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            energy,
            caller_struct_size,
            sizeof(bg_energy_components_v1),
            caller_abi_version,
            "bg_energy_components_v1 pointer must not be null",
            "bg_energy_components_v1 initializer size does not match the native ABI",
            "bg_energy_components_v1 initializer ABI version does not match");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *energy = bg_energy_components_v1{};
        energy->struct_size =
            static_cast<uint32_t>(sizeof(bg_energy_components_v1));
        energy->abi_version = BG_ABI_VERSION;
        energy->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_forcefield_create(
    const bg_forcefield_soa_v1 *parameters,
    bg_forcefield **out_forcefield) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    if (out_forcefield != nullptr) {
        *out_forcefield = nullptr;
    }
    return guarded_status([&]() -> bg_status {
        if (out_forcefield == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "out_forcefield must not be null");
        }
        if (parameters == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "bg_forcefield_soa_v1 must not be null");
        }
        bg_status status = validate_descriptor(*parameters);
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = validate_settings(*parameters);
        if (status != BG_STATUS_OK) {
            return status;
        }

        std::size_t owned_bytes = 0;
        std::size_t atom_count = 0;
        std::size_t bond_count = 0;
        std::size_t angle_count = 0;
        std::size_t torsion_count = 0;
        std::size_t exclusion_count = 0;
        std::size_t pair_scale_count = 0;
        status = checked_owned_count(
            parameters->atom_count,
            2 * sizeof(double),
            "atom_count overflows owned force-field capacity",
            &owned_bytes,
            &atom_count);
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = checked_owned_count(
            parameters->bond_count,
            2 * sizeof(std::size_t) + 2 * sizeof(double),
            "bond_count overflows owned force-field capacity",
            &owned_bytes,
            &bond_count);
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = checked_owned_count(
            parameters->angle_count,
            3 * sizeof(std::size_t) + 2 * sizeof(double),
            "angle_count overflows owned force-field capacity",
            &owned_bytes,
            &angle_count);
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = checked_owned_count(
            parameters->torsion_count,
            4 * sizeof(std::size_t) + sizeof(uint32_t) + 2 * sizeof(double),
            "torsion_count overflows owned force-field capacity",
            &owned_bytes,
            &torsion_count);
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = checked_owned_count(
            parameters->exclusion_count,
            sizeof(bg_forcefield::Pair),
            "exclusion_count overflows owned force-field capacity",
            &owned_bytes,
            &exclusion_count);
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = checked_owned_count(
            parameters->pair_scale_count,
            sizeof(bg_forcefield::PairScale),
            "pair_scale_count overflows owned force-field capacity",
            &owned_bytes,
            &pair_scale_count);
        if (status != BG_STATUS_OK) {
            return status;
        }

        status = validate_channel_contracts(
            *parameters,
            atom_count,
            bond_count,
            angle_count,
            torsion_count,
            exclusion_count,
            pair_scale_count);
        if (status != BG_STATUS_OK) {
            return status;
        }

        auto forcefield = std::make_unique<bg_forcefield>();
        forcefield->unit_system = parameters->unit_system;
        forcefield->atom_count = atom_count;
        forcefield->periodic_axes_mask = parameters->periodic_axes_mask;
        std::copy(
            std::begin(parameters->cell_lengths_angstrom),
            std::end(parameters->cell_lengths_angstrom),
            forcefield->cell_lengths.begin());
        forcefield->cutoff = parameters->cutoff_angstrom;
        forcefield->switch_start = parameters->switch_start_angstrom;
        forcefield->dielectric = parameters->dielectric;
        forcefield->screening_kappa =
            parameters->screening_kappa_per_angstrom;
        forcefield->minimum_pair_distance =
            parameters->minimum_pair_distance_angstrom;

        status = validate_and_copy_atom_parameters(
            *parameters, atom_count, forcefield.get());
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = validate_and_copy_bonds(
            *parameters, bond_count, forcefield.get());
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = validate_and_copy_angles(
            *parameters, angle_count, forcefield.get());
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = validate_and_copy_torsions(
            *parameters, torsion_count, forcefield.get());
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = validate_and_copy_pair_rules(
            *parameters,
            exclusion_count,
            pair_scale_count,
            forcefield.get());
        if (status != BG_STATUS_OK) {
            return status;
        }

        *out_forcefield = forcefield.release();
        return BG_STATUS_OK;
    });
}

extern "C" BG_API void BG_CALL bg_forcefield_destroy(
    bg_forcefield *forcefield) BG_NOEXCEPT {
    delete forcefield;
}

extern "C" BG_API bg_status BG_CALL bg_forcefield_get_atom_count(
    const bg_forcefield *forcefield,
    uint64_t *atom_count) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        if (forcefield == nullptr || atom_count == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "forcefield and atom_count output must not be null");
        }
        *atom_count = static_cast<uint64_t>(forcefield->atom_count);
        return BG_STATUS_OK;
    });
}
