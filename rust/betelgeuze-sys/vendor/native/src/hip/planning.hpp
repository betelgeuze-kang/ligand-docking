#ifndef BETELGEUZE_NATIVE_HIP_PLANNING_HPP
#define BETELGEUZE_NATIVE_HIP_PLANNING_HPP

#include "betelgeuze/engine.h"

#include <cstddef>
#include <cstdint>
#include <limits>

namespace betelgeuze::native::hip::detail {

struct SizePlan final {
    std::size_t atom_count = 0;
    std::size_t bonded_contribution_count = 0;
    std::size_t cell_count = 0;
    std::size_t neighbor_pair_count = 0;
    std::size_t maximum_neighbor_pair_count = 0;
    std::size_t scalar_atom_channel_bytes = 0;
    std::size_t force_storage_bytes = 0;
    std::size_t cell_index_bytes = 0;
    std::size_t cell_storage_bytes = 0;
    std::size_t neighbor_pair_bytes = 0;
    std::size_t contribution_count = 0;
    std::size_t contribution_index_bytes = 0;
};

[[nodiscard]] constexpr bool checked_add_size(
    std::size_t left,
    std::size_t right,
    std::size_t *out_value) noexcept {
    if (out_value == nullptr ||
        right > std::numeric_limits<std::size_t>::max() - left) {
        return false;
    }
    *out_value = left + right;
    return true;
}

[[nodiscard]] constexpr bool checked_multiply_size(
    std::size_t left,
    std::size_t right,
    std::size_t *out_value) noexcept {
    if (out_value == nullptr ||
        (left != 0 && right > std::numeric_limits<std::size_t>::max() / left)) {
        return false;
    }
    *out_value = left * right;
    return true;
}

[[nodiscard]] constexpr bool checked_triangular_pair_count(
    std::size_t atom_count,
    std::size_t *out_value) noexcept {
    if (out_value == nullptr) {
        return false;
    }
    if (atom_count < 2) {
        *out_value = 0;
        return true;
    }
    const std::size_t left = atom_count;
    const std::size_t right = atom_count - 1;
    if ((left & std::size_t{1}) == 0) {
        return checked_multiply_size(left / 2, right, out_value);
    }
    return checked_multiply_size(left, right / 2, out_value);
}

[[nodiscard]] constexpr bool checked_u64_to_size(
    uint64_t value,
    std::size_t *out_value) noexcept {
    if (out_value == nullptr) {
        return false;
    }
    if constexpr (sizeof(std::size_t) < sizeof(uint64_t)) {
        if (value > static_cast<uint64_t>(
                        std::numeric_limits<std::size_t>::max())) {
            return false;
        }
    }
    *out_value = static_cast<std::size_t>(value);
    return true;
}

/* This planner is deliberately independent of HIP headers and runtime state.
 * It lets ordinary C++ tests prove that hostile row counts are rejected before
 * a device allocator, pointer arithmetic, or a kernel launch sees them. */
[[nodiscard]] inline bg_status make_size_plan(
    uint64_t atom_count,
    uint64_t bond_count,
    uint64_t angle_count,
    uint64_t torsion_count,
    uint64_t cell_count,
    uint64_t neighbor_pair_count,
    bool compute_forces,
    SizePlan *out_plan) noexcept {
    if (out_plan == nullptr) {
        return BG_STATUS_INVALID_ARGUMENT;
    }

    SizePlan candidate;
    std::size_t bonds = 0;
    std::size_t angles = 0;
    std::size_t torsions = 0;
    if (!checked_u64_to_size(atom_count, &candidate.atom_count) ||
        !checked_u64_to_size(bond_count, &bonds) ||
        !checked_u64_to_size(angle_count, &angles) ||
        !checked_u64_to_size(torsion_count, &torsions) ||
        !checked_u64_to_size(cell_count, &candidate.cell_count) ||
        !checked_u64_to_size(
            neighbor_pair_count, &candidate.neighbor_pair_count)) {
        return BG_STATUS_CAPACITY_OVERFLOW;
    }

    std::size_t bonded_prefix = 0;
    if (!checked_add_size(bonds, angles, &bonded_prefix) ||
        !checked_add_size(
            bonded_prefix,
            torsions,
            &candidate.bonded_contribution_count) ||
        !checked_triangular_pair_count(
            candidate.atom_count,
            &candidate.maximum_neighbor_pair_count) ||
        candidate.neighbor_pair_count > candidate.maximum_neighbor_pair_count ||
        !checked_multiply_size(
            candidate.atom_count,
            sizeof(double),
            &candidate.scalar_atom_channel_bytes) ||
        !checked_multiply_size(
            candidate.atom_count,
            sizeof(uint64_t),
            &candidate.cell_index_bytes)) {
        return BG_STATUS_CAPACITY_OVERFLOW;
    }

    std::size_t cell_offset_count = 0;
    if (!checked_add_size(
            candidate.cell_count, std::size_t{1}, &cell_offset_count) ||
        !checked_multiply_size(
            cell_offset_count,
            sizeof(uint64_t),
            &candidate.cell_storage_bytes) ||
        !checked_add_size(
            candidate.bonded_contribution_count,
            candidate.neighbor_pair_count,
            &candidate.contribution_count) ||
        !checked_multiply_size(
            candidate.contribution_count,
            sizeof(uint64_t),
            &candidate.contribution_index_bytes)) {
        return BG_STATUS_CAPACITY_OVERFLOW;
    }

    if (compute_forces) {
        std::size_t xyz_channels = 0;
        if (!checked_multiply_size(
                candidate.scalar_atom_channel_bytes,
                std::size_t{3},
                &xyz_channels)) {
            return BG_STATUS_CAPACITY_OVERFLOW;
        }
        candidate.force_storage_bytes = xyz_channels;
    }
    if (!checked_multiply_size(
            candidate.neighbor_pair_count,
            std::size_t{2} * sizeof(uint64_t),
            &candidate.neighbor_pair_bytes)) {
        return BG_STATUS_CAPACITY_OVERFLOW;
    }

    *out_plan = candidate;
    return BG_STATUS_OK;
}

/* HIP enum values are not part of the stable ABI.  Passing the observed
 * runtime values keeps this helper usable in a compiler-only unit test. */
[[nodiscard]] constexpr bg_status map_runtime_error_code(
    int observed,
    int success_code,
    int out_of_memory_code) noexcept {
    if (observed == success_code) {
        return BG_STATUS_OK;
    }
    if (observed == out_of_memory_code) {
        return BG_STATUS_OUT_OF_MEMORY;
    }
    return BG_STATUS_BACKEND_ERROR;
}

}  // namespace betelgeuze::native::hip::detail

#endif  // BETELGEUZE_NATIVE_HIP_PLANNING_HPP
