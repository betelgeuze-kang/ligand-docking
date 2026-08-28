#ifndef BETELGEUZE_NATIVE_PARTICLE_MESH_RECIPROCAL_MODEL_HPP
#define BETELGEUZE_NATIVE_PARTICLE_MESH_RECIPROCAL_MODEL_HPP

#if !defined(BG_DISABLE_PARTICLE_MESH_RECIPROCAL_DESCRIPTOR_INIT_CONVENIENCE_MACROS)
#  define BG_DISABLE_PARTICLE_MESH_RECIPROCAL_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#  define BG_PMR_MODEL_UNDEF_INIT_MACROS
#endif
#include "betelgeuze/particle_mesh_reciprocal.h"
#if defined(BG_PMR_MODEL_UNDEF_INIT_MACROS)
#  undef BG_DISABLE_PARTICLE_MESH_RECIPROCAL_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#  undef BG_PMR_MODEL_UNDEF_INIT_MACROS
#endif

#include <array>
#include <cstddef>
#include <cstdint>

struct bg_particle_mesh_reciprocal_model_v1 final {
    bg_unit_system unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
    std::size_t atom_count = 0;
    std::array<double, 3> cell_lengths_angstrom{};
    double alpha_per_angstrom = 0.3;
    std::array<std::uint32_t, 3> mesh_dimensions{{16U, 16U, 16U}};
    double dielectric = 1.0;
};

#endif  // BETELGEUZE_NATIVE_PARTICLE_MESH_RECIPROCAL_MODEL_HPP
