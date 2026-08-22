#ifndef BETELGEUZE_NATIVE_CPU_NEIGHBOR_PAIR_HPP
#define BETELGEUZE_NATIVE_CPU_NEIGHBOR_PAIR_HPP

#include <array>
#include <cstddef>
#include <utility>
#include <vector>

namespace betelgeuze::native::cpu {

struct NeighborPair final {
    std::size_t atom_i = 0;
    std::size_t atom_j = 0;

    friend bool operator<(const NeighborPair &left, const NeighborPair &right) noexcept {
        return left.atom_i < right.atom_i ||
               (left.atom_i == right.atom_i && left.atom_j < right.atom_j);
    }

    friend bool operator==(const NeighborPair &left, const NeighborPair &right) noexcept {
        return left.atom_i == right.atom_i && left.atom_j == right.atom_j;
    }
};

using NeighborCellKey = std::array<std::size_t, 3>;
using NeighborCellAssignment =
    std::pair<NeighborCellKey, std::size_t>;

struct NeighborBuildScratch final {
    std::vector<NeighborCellKey> atom_cells;
    std::vector<NeighborCellAssignment> assignments;
    std::vector<NeighborCellKey> neighbor_cells;
    std::vector<std::size_t> candidates;
};

}  // namespace betelgeuze::native::cpu

#endif  // BETELGEUZE_NATIVE_CPU_NEIGHBOR_PAIR_HPP
