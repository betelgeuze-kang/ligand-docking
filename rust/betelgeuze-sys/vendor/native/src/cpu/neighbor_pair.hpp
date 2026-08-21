#ifndef BETELGEUZE_NATIVE_CPU_NEIGHBOR_PAIR_HPP
#define BETELGEUZE_NATIVE_CPU_NEIGHBOR_PAIR_HPP

#include <cstddef>

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

}  // namespace betelgeuze::native::cpu

#endif  // BETELGEUZE_NATIVE_CPU_NEIGHBOR_PAIR_HPP
