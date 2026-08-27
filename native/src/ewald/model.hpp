#ifndef BETELGEUZE_NATIVE_EWALD_MODEL_HPP
#define BETELGEUZE_NATIVE_EWALD_MODEL_HPP

#if !defined(BG_DISABLE_DIRECT_EWALD_DESCRIPTOR_INIT_CONVENIENCE_MACROS)
#  define BG_DISABLE_DIRECT_EWALD_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#  define BG_EWALD_MODEL_UNDEF_DIRECT_INIT_MACROS
#endif
#include "betelgeuze/direct_ewald.h"
#if defined(BG_EWALD_MODEL_UNDEF_DIRECT_INIT_MACROS)
#  undef BG_DISABLE_DIRECT_EWALD_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#  undef BG_EWALD_MODEL_UNDEF_DIRECT_INIT_MACROS
#endif

#include <array>
#include <cstddef>
#include <vector>

namespace betelgeuze::native::ewald {

struct PairRule final {
    std::size_t atom_i = 0;
    std::size_t atom_j = 0;
    double coulomb_scale = 1.0;
};

}  // namespace betelgeuze::native::ewald

struct bg_direct_ewald_model_v1 final {
    bg_unit_system unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
    std::size_t atom_count = 0;
    std::array<double, 3> cell_lengths_angstrom{};
    double alpha_per_angstrom = 0.3;
    double real_space_cutoff_angstrom = 8.0;
    std::array<int32_t, 3> reciprocal_max_indices{{5, 5, 5}};
    double dielectric = 1.0;
    double minimum_pair_distance_angstrom = 1.0e-8;
    std::vector<betelgeuze::native::ewald::PairRule> pair_rules;
};

#endif
