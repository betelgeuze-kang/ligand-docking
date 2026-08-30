#define BG_DISABLE_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#define BG_DISABLE_DIRECT_EWALD_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#define BG_DISABLE_DIRECT_EWALD_COMPOSITE_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#define BG_DISABLE_PARTICLE_MESH_RECIPROCAL_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#define BG_DISABLE_PARTICLE_MESH_EWALD_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#define BG_DISABLE_PARTICLE_MESH_EWALD_COMPOSITE_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#include "betelgeuze/particle_mesh_ewald_composite_dynamics.h"
#include "betelgeuze/direct_ewald_composite.h"
#include "betelgeuze/direct_ewald_composite_dynamics.h"

#include "particle_mesh_ewald_composite_dynamics_scratch.hpp"

#include "../src/ewald/model.hpp"
#include "../src/internal.hpp"
#include "../src/particle_mesh_reciprocal/model.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <memory>
#include <string>
#include <type_traits>
#include <vector>

namespace {

constexpr std::size_t kAtomCount = 4U;
constexpr double kAccelerationConversion = 4.184e-4;

enum class PairProvenance { exclusion, explicit_zero_scale };

[[noreturn]] void fail_test(const char *message) {
    std::fprintf(
        stderr, "particle-mesh Ewald composite dynamics test failure: %s\n",
        message);
    std::abort();
}

void require(bool condition, const char *message) {
    if (!condition) {
        fail_test(message);
    }
}

void require_status(bg_status actual, bg_status expected, const char *message) {
    if (actual != expected) {
        std::fprintf(
            stderr,
            "particle-mesh Ewald composite dynamics test failure: %s "
            "(expected %d, observed %d: %s)\n",
            message, static_cast<int>(expected), static_cast<int>(actual),
            bg_last_error_message());
        std::abort();
    }
}

std::uint64_t bits(double value) noexcept {
    std::uint64_t result = 0U;
    std::memcpy(&result, &value, sizeof(result));
    return result;
}

void require_exact(double actual, double expected, const char *message) {
    require(bits(actual) == bits(expected), message);
}

using ForceScratchSnapshot = betelgeuze::native::tests::
    ParticleMeshEwaldCompositeForceScratchSnapshot;
using ShortParentForceScratchSnapshot = betelgeuze::native::tests::
    ParticleMeshEwaldCompositeShortParentForceScratchSnapshot;
using DirectParentForceScratchSnapshot = betelgeuze::native::tests::
    ParticleMeshEwaldCompositeDirectParentForceScratchSnapshot;
using ReciprocalParentForceScratchSnapshot = betelgeuze::native::tests::
    ParticleMeshEwaldCompositeReciprocalParentForceScratchSnapshot;
using RustReciprocalProviderForceScratchSnapshot =
    betelgeuze::native::tests::
        ParticleMeshEwaldCompositeRustReciprocalProviderForceScratchSnapshot;
using ShortSystemScratchSnapshot = betelgeuze::native::tests::
    ParticleMeshEwaldCompositeShortSystemScratchSnapshot;

ForceScratchSnapshot force_scratch_snapshot(
    const bg_particle_mesh_ewald_composite_simulation_v1 *simulation) {
    return betelgeuze::native::tests::
        particle_mesh_ewald_composite_force_scratch_snapshot(simulation);
}

void require_same_force_scratch_storage(
    const ForceScratchSnapshot &actual,
    const ForceScratchSnapshot &expected,
    const char *message) {
    require(
        actual.addresses == expected.addresses &&
            actual.capacities == expected.capacities,
        message);
}

void require_force_scratch_sizes(
    const ForceScratchSnapshot &snapshot,
    std::size_t expected,
    const char *message) {
    require(
        snapshot.sizes == std::array<std::size_t, 3>{
            expected, expected, expected},
        message);
}

ShortParentForceScratchSnapshot short_parent_force_scratch_snapshot(
    const bg_particle_mesh_ewald_composite_simulation_v1 *simulation) {
    return betelgeuze::native::tests::
        particle_mesh_ewald_composite_short_parent_force_scratch_snapshot(
            simulation);
}

void require_same_short_parent_force_scratch_storage(
    const ShortParentForceScratchSnapshot &actual,
    const ShortParentForceScratchSnapshot &expected,
    const char *message) {
    require(
        actual.addresses == expected.addresses &&
            actual.capacities == expected.capacities,
        message);
}

void require_short_parent_force_scratch_sizes(
    const ShortParentForceScratchSnapshot &snapshot,
    std::size_t expected,
    const char *message) {
    require(
        snapshot.sizes == std::array<std::size_t, 3>{
            expected, expected, expected},
        message);
}

DirectParentForceScratchSnapshot direct_parent_force_scratch_snapshot(
    const bg_particle_mesh_ewald_composite_simulation_v1 *simulation) {
    return betelgeuze::native::tests::
        particle_mesh_ewald_composite_direct_parent_force_scratch_snapshot(
            simulation);
}

void require_same_direct_parent_force_scratch_storage(
    const DirectParentForceScratchSnapshot &actual,
    const DirectParentForceScratchSnapshot &expected,
    const char *message) {
    require(
        actual.address == expected.address &&
            actual.capacity == expected.capacity,
        message);
}

ReciprocalParentForceScratchSnapshot reciprocal_parent_force_scratch_snapshot(
    const bg_particle_mesh_ewald_composite_simulation_v1 *simulation) {
    return betelgeuze::native::tests::
        particle_mesh_ewald_composite_reciprocal_parent_force_scratch_snapshot(
            simulation);
}

void require_same_reciprocal_parent_force_scratch_storage(
    const ReciprocalParentForceScratchSnapshot &actual,
    const ReciprocalParentForceScratchSnapshot &expected,
    const char *message) {
    require(
        actual.address == expected.address &&
            actual.capacity == expected.capacity,
        message);
}

RustReciprocalProviderForceScratchSnapshot
rust_reciprocal_provider_force_scratch_snapshot(
    const bg_particle_mesh_ewald_composite_simulation_v1 *simulation) {
    return betelgeuze::native::tests::
        particle_mesh_ewald_composite_rust_reciprocal_provider_force_scratch_snapshot(
            simulation);
}

void require_same_rust_reciprocal_provider_force_scratch_storage(
    const RustReciprocalProviderForceScratchSnapshot &actual,
    const RustReciprocalProviderForceScratchSnapshot &expected,
    const char *message) {
    require(
        actual.addresses == expected.addresses &&
            actual.capacities == expected.capacities,
        message);
}

void require_rust_reciprocal_provider_force_scratch_sizes(
    const RustReciprocalProviderForceScratchSnapshot &snapshot,
    std::size_t expected,
    const char *message) {
    require(
        snapshot.sizes == std::array<std::size_t, 3>{
            expected, expected, expected},
        message);
}

ShortSystemScratchSnapshot short_system_scratch_snapshot(
    const bg_particle_mesh_ewald_composite_simulation_v1 *simulation) {
    return betelgeuze::native::tests::
        particle_mesh_ewald_composite_short_system_scratch_snapshot(
            simulation);
}

void require_same_short_system_scratch_storage(
    const ShortSystemScratchSnapshot &actual,
    const ShortSystemScratchSnapshot &expected,
    const char *message) {
    require(
        actual.addresses == expected.addresses &&
            actual.capacities == expected.capacities,
        message);
}

void require_short_system_scratch_layout(
    const ShortSystemScratchSnapshot &snapshot,
    const char *message) {
    require(
        snapshot.unit_system == BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL,
        message);
    require(
        snapshot.sizes == std::array<std::size_t, 8>{
            kAtomCount, kAtomCount, kAtomCount, kAtomCount,
            kAtomCount, kAtomCount, kAtomCount, kAtomCount},
        message);
    for (std::size_t channel = 0U; channel < snapshot.addresses.size();
         ++channel) {
        require(
            snapshot.addresses[channel] != nullptr &&
                snapshot.capacities[channel] >= kAtomCount,
            message);
        for (std::size_t other = channel + 1U;
             other < snapshot.addresses.size(); ++other) {
            require(
                snapshot.addresses[channel] != snapshot.addresses[other],
                message);
        }
    }
    for (std::size_t atom = 0U; atom < kAtomCount; ++atom) {
        require_exact(snapshot.addresses[7][atom], 0.0, message);
    }
}

void require_short_system_scratch_positions_current(
    const ShortSystemScratchSnapshot &snapshot,
    const bg_particle_soa_view &view,
    const char *message) {
    const std::array<const double *, 8> owner_addresses{{
        view.position_x_angstrom,
        view.position_y_angstrom,
        view.position_z_angstrom,
        view.velocity_x_angstrom_per_femtosecond,
        view.velocity_y_angstrom_per_femtosecond,
        view.velocity_z_angstrom_per_femtosecond,
        view.mass_dalton,
        view.charge_elementary,
    }};
    for (const double *const scratch_address : snapshot.addresses) {
        for (const double *const owner_address : owner_addresses) {
            require(
                scratch_address != owner_address,
                "short-system scratch aliased authoritative owner storage");
        }
    }
    const std::array<const double *, 3> positions{{
        view.position_x_angstrom,
        view.position_y_angstrom,
        view.position_z_angstrom,
    }};
    for (std::size_t axis = 0U; axis < positions.size(); ++axis) {
        require(positions[axis] != nullptr, message);
        for (std::size_t atom = 0U; atom < kAtomCount; ++atom) {
            require_exact(
                snapshot.addresses[axis][atom],
                positions[axis][atom],
                message);
        }
    }
}

using PositionBits =
    std::array<std::array<std::uint64_t, kAtomCount>, 3>;

using ForceBits = PositionBits;

ForceBits force_scratch_bits(const ForceScratchSnapshot &snapshot) {
    require_force_scratch_sizes(
        snapshot,
        kAtomCount,
        "final force scratch bit snapshot had the wrong size");
    ForceBits result{};
    for (std::size_t axis = 0U; axis < result.size(); ++axis) {
        require(
            snapshot.addresses[axis] != nullptr,
            "final force scratch bit snapshot had a null channel");
        for (std::size_t atom = 0U; atom < kAtomCount; ++atom) {
            result[axis][atom] = bits(snapshot.addresses[axis][atom]);
        }
    }
    return result;
}

ForceBits direct_parent_force_scratch_bits(
    const DirectParentForceScratchSnapshot &snapshot) {
    require(
        snapshot.address != nullptr && snapshot.size == kAtomCount,
        "direct-parent force scratch bit snapshot had the wrong shape");
    ForceBits result{};
    for (std::size_t atom = 0U; atom < kAtomCount; ++atom) {
        for (std::size_t axis = 0U; axis < result.size(); ++axis) {
            result[axis][atom] = bits(snapshot.address[atom][axis]);
        }
    }
    return result;
}

ForceBits reciprocal_parent_force_scratch_bits(
    const ReciprocalParentForceScratchSnapshot &snapshot) {
    require(
        snapshot.address != nullptr && snapshot.size == kAtomCount,
        "reciprocal-parent force scratch bit snapshot had the wrong shape");
    ForceBits result{};
    for (std::size_t atom = 0U; atom < kAtomCount; ++atom) {
        for (std::size_t axis = 0U; axis < result.size(); ++axis) {
            result[axis][atom] = bits(snapshot.address[atom][axis]);
        }
    }
    return result;
}

ForceBits rust_reciprocal_provider_force_scratch_bits(
    const RustReciprocalProviderForceScratchSnapshot &snapshot) {
    require_rust_reciprocal_provider_force_scratch_sizes(
        snapshot,
        kAtomCount,
        "Rust reciprocal-provider force scratch bit snapshot had the wrong size");
    ForceBits result{};
    for (std::size_t axis = 0U; axis < result.size(); ++axis) {
        require(
            snapshot.addresses[axis] != nullptr,
            "Rust reciprocal-provider force scratch bit snapshot had a null channel");
        for (std::size_t atom = 0U; atom < kAtomCount; ++atom) {
            result[axis][atom] = bits(snapshot.addresses[axis][atom]);
        }
    }
    return result;
}

ForceBits short_parent_force_scratch_bits(
    const ShortParentForceScratchSnapshot &snapshot) {
    require_short_parent_force_scratch_sizes(
        snapshot,
        kAtomCount,
        "short-parent force scratch bit snapshot had the wrong size");
    ForceBits result{};
    for (std::size_t axis = 0U; axis < result.size(); ++axis) {
        require(
            snapshot.addresses[axis] != nullptr,
            "short-parent force scratch bit snapshot had a null channel");
        for (std::size_t atom = 0U; atom < kAtomCount; ++atom) {
            result[axis][atom] = bits(snapshot.addresses[axis][atom]);
        }
    }
    return result;
}

PositionBits short_system_scratch_position_bits(
    const ShortSystemScratchSnapshot &snapshot) {
    PositionBits result{};
    for (std::size_t axis = 0U; axis < result.size(); ++axis) {
        for (std::size_t atom = 0U; atom < kAtomCount; ++atom) {
            result[axis][atom] = bits(snapshot.addresses[axis][atom]);
        }
    }
    return result;
}

PositionBits view_position_bits(const bg_particle_soa_view &view) {
    const std::array<const double *, 3> positions{{
        view.position_x_angstrom,
        view.position_y_angstrom,
        view.position_z_angstrom,
    }};
    PositionBits result{};
    for (std::size_t axis = 0U; axis < result.size(); ++axis) {
        require(positions[axis] != nullptr, "particle position was null");
        for (std::size_t atom = 0U; atom < kAtomCount; ++atom) {
            result[axis][atom] = bits(positions[axis][atom]);
        }
    }
    return result;
}

template <typename Type, typename = void>
struct is_complete : std::false_type {};

template <typename Type>
struct is_complete<Type, std::void_t<decltype(sizeof(Type))>>
    : std::true_type {};

struct ContextDeleter final {
    void operator()(bg_context *value) const noexcept {
        bg_context_destroy(value);
    }
};

struct SystemDeleter final {
    void operator()(bg_system *value) const noexcept {
        bg_system_destroy(value);
    }
};

struct ForceFieldDeleter final {
    void operator()(bg_forcefield *value) const noexcept {
        bg_forcefield_destroy(value);
    }
};

struct DirectModelDeleter final {
    void operator()(bg_direct_ewald_model_v1 *value) const noexcept {
        bg_direct_ewald_model_v1_destroy(value);
    }
};

struct ReciprocalModelDeleter final {
    void operator()(
        bg_particle_mesh_reciprocal_model_v1 *value) const noexcept {
        bg_particle_mesh_reciprocal_model_v1_destroy(value);
    }
};

using ContextPtr = std::unique_ptr<bg_context, ContextDeleter>;
using SystemPtr = std::unique_ptr<bg_system, SystemDeleter>;
using ForceFieldPtr = std::unique_ptr<bg_forcefield, ForceFieldDeleter>;
using DirectModelPtr =
    std::unique_ptr<bg_direct_ewald_model_v1, DirectModelDeleter>;
using ReciprocalModelPtr = std::unique_ptr<
    bg_particle_mesh_reciprocal_model_v1, ReciprocalModelDeleter>;

struct SimulationDeleter final {
    void operator()(bg_particle_mesh_ewald_composite_simulation_v1 *value) const noexcept {
        bg_particle_mesh_ewald_composite_simulation_v1_destroy(value);
    }
};
using SimulationPtr = std::unique_ptr<
    bg_particle_mesh_ewald_composite_simulation_v1, SimulationDeleter>;

struct LegacySimulationDeleter final {
    void operator()(bg_simulation *value) const noexcept {
        bg_simulation_destroy(value);
    }
};
using LegacySimulationPtr =
    std::unique_ptr<bg_simulation, LegacySimulationDeleter>;

struct DirectSimulationDeleter final {
    void operator()(
        bg_direct_ewald_composite_simulation_v1 *value) const noexcept {
        bg_direct_ewald_composite_simulation_v1_destroy(value);
    }
};
using DirectSimulationPtr = std::unique_ptr<
    bg_direct_ewald_composite_simulation_v1, DirectSimulationDeleter>;

struct Fixture final {
    std::array<double, 4> x{{1.25, 3.1, 5.2, 7.4}};
    std::array<double, 4> y{{2.5, 3.2, 5.3, 6.1}};
    std::array<double, 4> z{{3.75, 4.4, 4.7, 6.3}};
    std::array<double, 4> velocity_x{{0.0, 0.0, 0.0, 0.0}};
    std::array<double, 4> velocity_y{{0.0, 0.0, 0.0, 0.0}};
    std::array<double, 4> velocity_z{{0.0, 0.0, 0.0, 0.0}};
    std::array<double, 4> mass{{12.0, 14.0, 16.0, 19.0}};
    std::array<double, 4> charge{{
        0.7, -0.4, -0.6, 0.30000000000000004}};
    std::array<double, 4> sigma{{1.1, 1.2, 1.3, 1.4}};
    std::array<double, 4> epsilon{{0.15, 0.20, 0.25, 0.30}};

    std::array<std::uint64_t, 1> bond_i{{0U}};
    std::array<std::uint64_t, 1> bond_j{{1U}};
    std::array<double, 1> bond_equilibrium{{5.0}};
    std::array<double, 1> bond_force_constant{{3.0}};

    std::array<std::uint64_t, 1> angle_i{{0U}};
    std::array<std::uint64_t, 1> angle_j{{1U}};
    std::array<std::uint64_t, 1> angle_k{{2U}};
    std::array<double, 1> angle_equilibrium{{1.4}};
    std::array<double, 1> angle_force_constant{{2.0}};

    std::array<std::uint64_t, 1> torsion_i{{0U}};
    std::array<std::uint64_t, 1> torsion_j{{1U}};
    std::array<std::uint64_t, 1> torsion_k{{2U}};
    std::array<std::uint64_t, 1> torsion_l{{3U}};
    std::array<std::uint32_t, 1> torsion_periodicity{{3U}};
    std::array<double, 1> torsion_phase{{0.4}};
    std::array<double, 1> torsion_amplitude{{0.7}};

    std::array<std::uint64_t, 1> exclusion_i{{0U}};
    std::array<std::uint64_t, 1> exclusion_j{{1U}};
    std::array<std::uint64_t, 1> scale_i{{2U}};
    std::array<std::uint64_t, 1> scale_j{{3U}};
    std::array<double, 1> scale_lennard_jones{{0.25}};
    std::array<double, 1> scale_coulomb{{0.5}};

    std::array<double, 3> cell{{18.0, 20.0, 22.0}};
    double alpha = 0.31;
    double cutoff = 8.9;
    double switch_start = 7.0;
    double dielectric = 1.0;
    double minimum_pair_distance = 1.0e-8;
};

void init_error(bg_direct_ewald_error_v1 *error) {
    require_status(
        bg_direct_ewald_error_v1_init(
            error, sizeof(*error), BG_DIRECT_EWALD_ABI_VERSION),
        BG_STATUS_OK, "typed-error initializer failed");
}

ContextPtr make_context(bg_backend backend) {
    bg_context_options options{};
    require_status(
        bg_context_options_init(&options, sizeof(options), BG_ABI_VERSION),
        BG_STATUS_OK, "context initializer failed");
    options.backend = backend;
    bg_context *raw = nullptr;
    require_status(
        bg_context_create(&options, &raw), BG_STATUS_OK,
        "CPU context creation failed");
    require(raw != nullptr, "CPU context creation returned null");
    return ContextPtr(raw);
}

SystemPtr make_system(
    const Fixture &fixture,
    const std::array<double, 4> &charge) {
    bg_particle_soa particles{};
    require_status(
        bg_particle_soa_init(
            &particles, sizeof(particles), BG_ABI_VERSION),
        BG_STATUS_OK, "particle initializer failed");
    particles.particle_count = fixture.x.size();
    particles.position_x_angstrom = fixture.x.data();
    particles.position_y_angstrom = fixture.y.data();
    particles.position_z_angstrom = fixture.z.data();
    particles.velocity_x_angstrom_per_femtosecond = fixture.velocity_x.data();
    particles.velocity_y_angstrom_per_femtosecond = fixture.velocity_y.data();
    particles.velocity_z_angstrom_per_femtosecond = fixture.velocity_z.data();
    particles.mass_dalton = fixture.mass.data();
    particles.charge_elementary = charge.data();
    bg_system *raw = nullptr;
    require_status(
        bg_system_create(&particles, &raw), BG_STATUS_OK,
        "system creation failed");
    require(raw != nullptr, "system creation returned null");
    return SystemPtr(raw);
}

ForceFieldPtr make_forcefield(
    const Fixture &fixture,
    PairProvenance provenance = PairProvenance::exclusion) {
    bg_forcefield_soa_v1 parameters{};
    require_status(
        bg_forcefield_soa_v1_init(
            &parameters, sizeof(parameters), BG_ABI_VERSION),
        BG_STATUS_OK, "force-field initializer failed");
    parameters.atom_count = fixture.sigma.size();
    parameters.unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
    parameters.periodic_axes_mask = BG_PERIODIC_AXES_ALL;
    parameters.sigma_angstrom = fixture.sigma.data();
    parameters.epsilon_kcal_per_mol = fixture.epsilon.data();
    parameters.bond_count = fixture.bond_i.size();
    parameters.bond_atom_i = fixture.bond_i.data();
    parameters.bond_atom_j = fixture.bond_j.data();
    parameters.bond_equilibrium_angstrom = fixture.bond_equilibrium.data();
    parameters.bond_force_constant_kcal_per_mol_angstrom2 =
        fixture.bond_force_constant.data();
    parameters.angle_count = fixture.angle_i.size();
    parameters.angle_atom_i = fixture.angle_i.data();
    parameters.angle_atom_j = fixture.angle_j.data();
    parameters.angle_atom_k = fixture.angle_k.data();
    parameters.angle_equilibrium_radians = fixture.angle_equilibrium.data();
    parameters.angle_force_constant_kcal_per_mol_radian2 =
        fixture.angle_force_constant.data();
    parameters.torsion_count = fixture.torsion_i.size();
    parameters.torsion_atom_i = fixture.torsion_i.data();
    parameters.torsion_atom_j = fixture.torsion_j.data();
    parameters.torsion_atom_k = fixture.torsion_k.data();
    parameters.torsion_atom_l = fixture.torsion_l.data();
    parameters.torsion_periodicity = fixture.torsion_periodicity.data();
    parameters.torsion_phase_radians = fixture.torsion_phase.data();
    parameters.torsion_amplitude_kcal_per_mol =
        fixture.torsion_amplitude.data();
    const std::array<std::uint64_t, 2> scale_i{{0U, 2U}};
    const std::array<std::uint64_t, 2> scale_j{{1U, 3U}};
    const std::array<double, 2> scale_lj{{0.0, fixture.scale_lennard_jones[0]}};
    const std::array<double, 2> scale_coulomb{{0.0, fixture.scale_coulomb[0]}};
    if (provenance == PairProvenance::exclusion) {
        parameters.exclusion_count = fixture.exclusion_i.size();
        parameters.exclusion_atom_i = fixture.exclusion_i.data();
        parameters.exclusion_atom_j = fixture.exclusion_j.data();
        parameters.pair_scale_count = fixture.scale_i.size();
        parameters.pair_scale_atom_i = fixture.scale_i.data();
        parameters.pair_scale_atom_j = fixture.scale_j.data();
        parameters.pair_scale_lennard_jones =
            fixture.scale_lennard_jones.data();
        parameters.pair_scale_coulomb = fixture.scale_coulomb.data();
    } else {
        parameters.pair_scale_count = scale_i.size();
        parameters.pair_scale_atom_i = scale_i.data();
        parameters.pair_scale_atom_j = scale_j.data();
        parameters.pair_scale_lennard_jones = scale_lj.data();
        parameters.pair_scale_coulomb = scale_coulomb.data();
    }
    std::copy(
        fixture.cell.begin(), fixture.cell.end(),
        parameters.cell_lengths_angstrom);
    parameters.cutoff_angstrom = fixture.cutoff;
    parameters.switch_start_angstrom = fixture.switch_start;
    parameters.dielectric = fixture.dielectric;
    parameters.screening_kappa_per_angstrom = 0.0;
    parameters.minimum_pair_distance_angstrom =
        fixture.minimum_pair_distance;
    bg_forcefield *raw = nullptr;
    require_status(
        bg_forcefield_create(&parameters, &raw), BG_STATUS_OK,
        "force-field creation failed");
    require(raw != nullptr, "force-field creation returned null");
    return ForceFieldPtr(raw);
}

DirectModelPtr make_direct_model(
    const Fixture &fixture,
    bool with_pair_rules = true,
    std::int32_t reciprocal_bound = 5,
    PairProvenance provenance = PairProvenance::exclusion) {
    bg_direct_ewald_parameters_v1 parameters{};
    require_status(
        bg_direct_ewald_parameters_v1_init(
            &parameters, sizeof(parameters), BG_DIRECT_EWALD_ABI_VERSION),
        BG_STATUS_OK, "direct-model parameter initializer failed");
    parameters.atom_count = fixture.x.size();
    std::copy(
        fixture.cell.begin(), fixture.cell.end(),
        parameters.cell_lengths_angstrom);
    parameters.alpha_per_angstrom = fixture.alpha;
    parameters.real_space_cutoff_angstrom = fixture.cutoff;
    parameters.reciprocal_max_indices[0] = reciprocal_bound;
    parameters.reciprocal_max_indices[1] = reciprocal_bound;
    parameters.reciprocal_max_indices[2] = reciprocal_bound;
    parameters.dielectric = fixture.dielectric;
    parameters.minimum_pair_distance_angstrom =
        fixture.minimum_pair_distance;
    const std::array<std::uint64_t, 2> explicit_scale_i{{0U, 2U}};
    const std::array<std::uint64_t, 2> explicit_scale_j{{1U, 3U}};
    const std::array<double, 2> explicit_scale_coulomb{{
        0.0, fixture.scale_coulomb[0]}};
    if (with_pair_rules) {
        if (provenance == PairProvenance::exclusion) {
            parameters.exclusion_count = fixture.exclusion_i.size();
            parameters.exclusion_atom_i = fixture.exclusion_i.data();
            parameters.exclusion_atom_j = fixture.exclusion_j.data();
            parameters.pair_scale_count = fixture.scale_i.size();
            parameters.pair_scale_atom_i = fixture.scale_i.data();
            parameters.pair_scale_atom_j = fixture.scale_j.data();
            parameters.pair_scale_coulomb = fixture.scale_coulomb.data();
        } else {
            parameters.pair_scale_count = explicit_scale_i.size();
            parameters.pair_scale_atom_i = explicit_scale_i.data();
            parameters.pair_scale_atom_j = explicit_scale_j.data();
            parameters.pair_scale_coulomb = explicit_scale_coulomb.data();
        }
    }
    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    bg_direct_ewald_model_v1 *raw = nullptr;
    require_status(
        bg_direct_ewald_model_v1_create(&parameters, &raw, &error),
        BG_STATUS_OK, "direct model creation failed");
    require(raw != nullptr, "direct model creation returned null");
    require(
        error.code == BG_DIRECT_EWALD_ERROR_NONE,
        "direct model creation set typed error");
    return DirectModelPtr(raw);
}

ReciprocalModelPtr make_reciprocal_model(
    const Fixture &fixture,
    std::uint32_t mesh_dimension = 16U) {
    bg_particle_mesh_reciprocal_parameters_v1 parameters{};
    require_status(
        bg_particle_mesh_reciprocal_parameters_v1_init(
            &parameters, sizeof(parameters),
            BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION),
        BG_STATUS_OK, "reciprocal-model parameter initializer failed");
    parameters.atom_count = fixture.x.size();
    std::copy(
        fixture.cell.begin(), fixture.cell.end(),
        parameters.cell_lengths_angstrom);
    parameters.alpha_per_angstrom = fixture.alpha;
    parameters.mesh_dimensions[0] = mesh_dimension;
    parameters.mesh_dimensions[1] = mesh_dimension;
    parameters.mesh_dimensions[2] = mesh_dimension;
    parameters.dielectric = fixture.dielectric;
    bg_particle_mesh_reciprocal_error_v1 error{};
    require_status(
        bg_particle_mesh_reciprocal_error_v1_init(
            &error, sizeof(error),
            BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION),
        BG_STATUS_OK, "reciprocal-model error initializer failed");
    bg_particle_mesh_reciprocal_model_v1 *raw = nullptr;
    require_status(
        bg_particle_mesh_reciprocal_model_v1_create(
            &parameters, &raw, &error),
        BG_STATUS_OK, "reciprocal model creation failed");
    require(raw != nullptr, "reciprocal model creation returned null");
    require(
        error.code == BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONE,
        "reciprocal model creation set typed error");
    return ReciprocalModelPtr(raw);
}


void init_report(bg_dynamics_report_v1 *report);

SimulationPtr make_simulation(
    const bg_system *system,
    const bg_forcefield *forcefield,
    const bg_direct_ewald_model_v1 *direct_model,
    const bg_particle_mesh_reciprocal_model_v1 *reciprocal_model,
    const bg_distance_constraints_v1 *constraints = nullptr,
    double timestep = 0.001) {
    bg_simulation_options_v1 options{};
    require_status(bg_simulation_options_v1_init(
        &options, sizeof(options), BG_ABI_VERSION), BG_STATUS_OK,
        "options init failed");
    options.integrator = BG_INTEGRATOR_VELOCITY_VERLET;
    options.timestep_femtoseconds = timestep;
    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    bg_particle_mesh_ewald_composite_simulation_v1 *raw = nullptr;
    require_status(bg_particle_mesh_ewald_composite_simulation_v1_create(
        system, forcefield, direct_model, reciprocal_model, constraints,
        &options, &raw, &error), BG_STATUS_OK, "simulation create failed");
    require(raw != nullptr, "simulation create returned null");
    require(error.code == BG_DIRECT_EWALD_ERROR_NONE,
            "simulation create retained typed error");
    return SimulationPtr(raw);
}

bg_particle_soa_view simulation_view(
    const bg_particle_mesh_ewald_composite_simulation_v1 *simulation) {
    bg_particle_soa_view view{};
    require_status(
        bg_particle_soa_view_init(
            &view, sizeof(view), BG_ABI_VERSION),
        BG_STATUS_OK,
        "particle-view initializer failed");
    require_status(
        bg_particle_mesh_ewald_composite_simulation_v1_get_particles(
            simulation, &view),
        BG_STATUS_OK,
        "particle-view query failed");
    return view;
}

bg_dynamics_report_v1 integrate(
    const bg_context *context,
    bg_particle_mesh_ewald_composite_simulation_v1 *simulation,
    std::uint64_t steps) {
    bg_dynamics_report_v1 report{};
    init_report(&report);
    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    require_status(bg_context_integrate_particle_mesh_ewald_composite_v1(
        context, simulation, steps, &report, &error), BG_STATUS_OK,
        "integration failed");
    require(error.code == BG_DIRECT_EWALD_ERROR_NONE,
            "successful integration retained typed error");
    return report;
}

struct StatelessEvaluation final {
    bg_particle_mesh_ewald_composite_energy_components_v1 energy{};
    std::array<double, kAtomCount> force_x{};
    std::array<double, kAtomCount> force_y{};
    std::array<double, kAtomCount> force_z{};
};

ForceBits stateless_force_bits(const StatelessEvaluation &evaluation) {
    const std::array<const std::array<double, kAtomCount> *, 3> channels{{
        &evaluation.force_x,
        &evaluation.force_y,
        &evaluation.force_z,
    }};
    ForceBits result{};
    for (std::size_t axis = 0U; axis < result.size(); ++axis) {
        for (std::size_t atom = 0U; atom < kAtomCount; ++atom) {
            result[axis][atom] = bits((*channels[axis])[atom]);
        }
    }
    return result;
}

StatelessEvaluation evaluate_stateless(
    const bg_context *context,
    const bg_system *system,
    const bg_forcefield *forcefield,
    const bg_direct_ewald_model_v1 *direct_model,
    const bg_particle_mesh_reciprocal_model_v1 *reciprocal_model) {
    StatelessEvaluation result;
    require_status(
        bg_particle_mesh_ewald_composite_energy_components_v1_init(
            &result.energy, sizeof(result.energy),
            BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION),
        BG_STATUS_OK, "stateless energy init failed");
    bg_particle_mesh_ewald_composite_force_soa_v1 forces{};
    require_status(
        bg_particle_mesh_ewald_composite_force_soa_v1_init(
            &forces, sizeof(forces),
            BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION),
        BG_STATUS_OK, "stateless force init failed");
    forces.atom_capacity = kAtomCount;
    forces.x_kcal_per_mol_angstrom = result.force_x.data();
    forces.y_kcal_per_mol_angstrom = result.force_y.data();
    forces.z_kcal_per_mol_angstrom = result.force_z.data();
    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    require_status(bg_context_evaluate_particle_mesh_ewald_composite_v1(
        context, system, forcefield, direct_model, reciprocal_model,
        &result.energy, &forces, &error), BG_STATUS_OK,
        "stateless energy evaluation failed");
    require(
        forces.atom_count == kAtomCount,
        "stateless force count differed");
    require(
        error.code == BG_DIRECT_EWALD_ERROR_NONE &&
            error.detail[0] == '\0',
        "stateless evaluation set a typed error");
    return result;
}

ForceBits evaluate_stateless_direct_local_force_bits(
    const bg_context *context,
    const bg_system *system,
    const bg_direct_ewald_model_v1 *model) {
    require(model != nullptr, "stateless direct-local model was null");
    bg_direct_ewald_model_v1 direct_local_model = *model;
    direct_local_model.reciprocal_max_indices = {{0, 0, 0}};

    bg_direct_ewald_energy_components_v1 energy{};
    require_status(
        bg_direct_ewald_energy_components_v1_init(
            &energy, sizeof(energy), BG_DIRECT_EWALD_ABI_VERSION),
        BG_STATUS_OK,
        "stateless direct-local energy initializer failed");
    std::array<double, kAtomCount> force_x{};
    std::array<double, kAtomCount> force_y{};
    std::array<double, kAtomCount> force_z{};
    bg_direct_ewald_force_soa_v1 forces{};
    require_status(
        bg_direct_ewald_force_soa_v1_init(
            &forces, sizeof(forces), BG_DIRECT_EWALD_ABI_VERSION),
        BG_STATUS_OK,
        "stateless direct-local force initializer failed");
    forces.atom_capacity = kAtomCount;
    forces.x_kcal_per_mol_angstrom = force_x.data();
    forces.y_kcal_per_mol_angstrom = force_y.data();
    forces.z_kcal_per_mol_angstrom = force_z.data();
    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    require_status(
        bg_context_evaluate_direct_ewald_v1(
            context, system, &direct_local_model, &energy, &forces, &error),
        BG_STATUS_OK,
        "stateless direct-local evaluation failed");
    require(
        forces.atom_count == kAtomCount &&
            error.code == BG_DIRECT_EWALD_ERROR_NONE &&
            error.detail[0] == '\0',
        "stateless direct-local evaluation returned inconsistent outputs");

    const std::array<const std::array<double, kAtomCount> *, 3> channels{{
        &force_x,
        &force_y,
        &force_z,
    }};
    ForceBits result{};
    for (std::size_t axis = 0U; axis < result.size(); ++axis) {
        for (std::size_t atom = 0U; atom < kAtomCount; ++atom) {
            result[axis][atom] = bits((*channels[axis])[atom]);
        }
    }
    return result;
}

ForceBits evaluate_stateless_reciprocal_force_bits(
    const bg_context *context,
    const bg_system *system,
    const bg_particle_mesh_reciprocal_model_v1 *model) {
    bg_particle_mesh_reciprocal_energy_v1 energy{};
    require_status(
        bg_particle_mesh_reciprocal_energy_v1_init(
            &energy, sizeof(energy),
            BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION),
        BG_STATUS_OK,
        "stateless reciprocal energy initializer failed");
    std::array<double, kAtomCount> force_x{};
    std::array<double, kAtomCount> force_y{};
    std::array<double, kAtomCount> force_z{};
    bg_particle_mesh_reciprocal_force_soa_v1 forces{};
    require_status(
        bg_particle_mesh_reciprocal_force_soa_v1_init(
            &forces, sizeof(forces),
            BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION),
        BG_STATUS_OK,
        "stateless reciprocal force initializer failed");
    forces.atom_capacity = kAtomCount;
    forces.x_kcal_per_mol_angstrom = force_x.data();
    forces.y_kcal_per_mol_angstrom = force_y.data();
    forces.z_kcal_per_mol_angstrom = force_z.data();
    bg_particle_mesh_reciprocal_error_v1 error{};
    require_status(
        bg_particle_mesh_reciprocal_error_v1_init(
            &error, sizeof(error),
            BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION),
        BG_STATUS_OK,
        "stateless reciprocal error initializer failed");
    require_status(
        bg_context_evaluate_particle_mesh_reciprocal_v1(
            context, system, model, &energy, &forces, &error),
        BG_STATUS_OK,
        "stateless reciprocal evaluation failed");
    require(
        forces.atom_count == kAtomCount &&
            error.code == BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONE &&
            error.detail[0] == '\0',
        "stateless reciprocal evaluation returned inconsistent outputs");

    const std::array<const std::array<double, kAtomCount> *, 3> channels{{
        &force_x,
        &force_y,
        &force_z,
    }};
    ForceBits result{};
    for (std::size_t axis = 0U; axis < result.size(); ++axis) {
        for (std::size_t atom = 0U; atom < kAtomCount; ++atom) {
            result[axis][atom] = bits((*channels[axis])[atom]);
        }
    }
    return result;
}

double stateless_total(
    const bg_context *context,
    const bg_system *system,
    const bg_forcefield *forcefield,
    const bg_direct_ewald_model_v1 *direct_model,
    const bg_particle_mesh_reciprocal_model_v1 *reciprocal_model) {
    bg_particle_mesh_ewald_composite_energy_components_v1 energy{};
    require_status(
        bg_particle_mesh_ewald_composite_energy_components_v1_init(
            &energy, sizeof(energy),
            BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION),
        BG_STATUS_OK, "stateless energy init failed");
    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    require_status(bg_context_evaluate_particle_mesh_ewald_composite_v1(
        context, system, forcefield, direct_model, reciprocal_model,
        &energy, nullptr, &error), BG_STATUS_OK,
        "stateless energy evaluation failed");
    return energy.total_kcal_per_mol;
}

void init_report(bg_dynamics_report_v1 *report) {
    require_status(bg_dynamics_report_v1_init(
        report, sizeof(*report), BG_ABI_VERSION), BG_STATUS_OK,
        "report init failed");
}

std::vector<std::uint8_t> checkpoint(
    const bg_particle_mesh_ewald_composite_simulation_v1 *simulation) {
    std::uint64_t size = 0;
    require_status(
        bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_size(
            simulation, &size), BG_STATUS_OK, "checkpoint size failed");
    std::vector<std::uint8_t> bytes(static_cast<std::size_t>(size));
    std::uint64_t written = 0;
    require_status(
        bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_write(
            simulation, bytes.data(), size, &written), BG_STATUS_OK,
        "checkpoint write failed");
    require(written == size, "checkpoint size mismatch");
    require(std::memcmp(bytes.data(), "BGPME001", 8U) == 0,
            "checkpoint magic mismatch");
    return bytes;
}

void verify_runtime_and_checkpoint_identity() {
    Fixture fixture;
    auto context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    auto system = make_system(fixture, fixture.charge);
    auto forcefield = make_forcefield(fixture);
    auto direct5 = make_direct_model(fixture, true, 5);
    auto direct9 = make_direct_model(fixture, true, 9);
    auto reciprocal16 = make_reciprocal_model(fixture, 16U);
    auto reciprocal32 = make_reciprocal_model(fixture, 32U);
    auto simulation = make_simulation(
        system.get(), forcefield.get(), direct5.get(), reciprocal16.get());
    auto ignored_bounds_peer = make_simulation(
        system.get(), forcefield.get(), direct9.get(), reciprocal16.get());
    auto semantic_peer = make_simulation(
        system.get(), forcefield.get(), direct5.get(), reciprocal32.get());
    Fixture changed_alpha = fixture;
    changed_alpha.alpha = 0.29;
    auto alpha_direct = make_direct_model(changed_alpha);
    auto alpha_reciprocal = make_reciprocal_model(changed_alpha, 16U);
    auto alpha_peer = make_simulation(
        system.get(), forcefield.get(), alpha_direct.get(),
        alpha_reciprocal.get());
    auto timestep_peer = make_simulation(
        system.get(), forcefield.get(), direct5.get(), reciprocal16.get(),
        nullptr, 0.002);
    Fixture changed_dielectric = fixture;
    changed_dielectric.dielectric = 2.0;
    auto dielectric_forcefield = make_forcefield(changed_dielectric);
    auto dielectric_direct = make_direct_model(changed_dielectric);
    auto dielectric_reciprocal = make_reciprocal_model(changed_dielectric);
    auto dielectric_peer = make_simulation(
        system.get(), dielectric_forcefield.get(), dielectric_direct.get(),
        dielectric_reciprocal.get());
    auto explicit_zero_forcefield = make_forcefield(
        fixture, PairProvenance::explicit_zero_scale);
    auto explicit_zero_direct = make_direct_model(
        fixture, true, 5, PairProvenance::explicit_zero_scale);
    auto explicit_zero_peer = make_simulation(
        system.get(), explicit_zero_forcefield.get(),
        explicit_zero_direct.get(), reciprocal16.get());

    bg_dynamics_report_v1 report{};
    init_report(&report);
    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    require_status(bg_context_integrate_particle_mesh_ewald_composite_v1(
        context.get(), simulation.get(), 1U, &report, &error), BG_STATUS_OK,
        "one-step integration failed");
    require(error.code == BG_DIRECT_EWALD_ERROR_NONE,
            "successful integration retained typed error");
    std::uint64_t step = 0;
    require_status(
        bg_particle_mesh_ewald_composite_simulation_v1_get_absolute_step(
            simulation.get(), &step), BG_STATUS_OK, "step query failed");
    require(step == 1U, "integration did not advance absolute step");

    const auto bytes = checkpoint(simulation.get());
    require_status(
        bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_load(
            ignored_bounds_peer.get(), bytes.data(), bytes.size()),
        BG_STATUS_OK, "ignored direct reciprocal bounds changed identity");
    require_status(
        bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_load(
            semantic_peer.get(), bytes.data(), bytes.size()),
        BG_STATUS_INVALID_ARGUMENT,
        "semantic reciprocal mesh change preserved identity");
    for (auto *peer : {alpha_peer.get(), timestep_peer.get(),
                       dielectric_peer.get(), explicit_zero_peer.get()}) {
        require_status(
            bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_load(
                peer, bytes.data(), bytes.size()),
            BG_STATUS_INVALID_ARGUMENT,
            "semantic model or timestep change preserved identity");
    }
}

void verify_force_output_scratch_reuse() {
    constexpr std::size_t kReservedCapacity = 64U;
    const Fixture fixture;
    for (const bg_backend lane :
         {BG_BACKEND_CPP_CPU_REFERENCE, BG_BACKEND_RUST_CPU}) {
        auto context = make_context(lane);
        auto system = make_system(fixture, fixture.charge);
        auto forcefield = make_forcefield(fixture);
        auto direct = make_direct_model(fixture);
        auto reciprocal = make_reciprocal_model(fixture);
        auto simulation = make_simulation(
            system.get(), forcefield.get(), direct.get(), reciprocal.get());
        auto peer = make_simulation(
            system.get(), forcefield.get(), direct.get(), reciprocal.get());

        const ForceScratchSnapshot initial =
            force_scratch_snapshot(simulation.get());
        require_force_scratch_sizes(
            initial, 0U, "new simulation force scratch was not empty");
        require(
            initial.capacities == std::array<std::size_t, 3>{0U, 0U, 0U},
            "new simulation force scratch retained capacity");

        betelgeuze::native::tests::
            reserve_particle_mesh_ewald_composite_force_scratch(
                simulation.get(), kReservedCapacity);
        const ForceScratchSnapshot reserved =
            force_scratch_snapshot(simulation.get());
        require_force_scratch_sizes(
            reserved, 0U, "reserved force scratch changed logical size");
        for (std::size_t axis = 0U; axis < 3U; ++axis) {
            require(
                reserved.addresses[axis] != nullptr &&
                    reserved.capacities[axis] >= kReservedCapacity,
                "force scratch reserve did not materialize storage");
            for (std::size_t other = axis + 1U; other < 3U; ++other) {
                require(
                    reserved.addresses[axis] != reserved.addresses[other],
                    "force scratch channels aliased");
            }
        }

        const auto before_zero = checkpoint(simulation.get());
        const bg_dynamics_report_v1 zero_report =
            integrate(context.get(), simulation.get(), 0U);
        const bg_dynamics_report_v1 peer_zero_report =
            integrate(context.get(), peer.get(), 0U);
        require(
            std::memcmp(
                &zero_report, &peer_zero_report, sizeof(zero_report)) == 0,
            "reserved scratch changed zero-step report bits");
        require(
            checkpoint(simulation.get()) == before_zero,
            "zero-step integration changed checkpoint state");
        const ForceScratchSnapshot after_zero =
            force_scratch_snapshot(simulation.get());
        require_same_force_scratch_storage(
            after_zero, reserved, "zero-step integration changed scratch storage");
        require_force_scratch_sizes(
            after_zero, 0U, "zero-step integration changed scratch size");

        for (const std::uint64_t step_count : {UINT64_C(1), UINT64_C(2)}) {
            const bg_dynamics_report_v1 report =
                integrate(context.get(), simulation.get(), step_count);
            const bg_dynamics_report_v1 peer_report =
                integrate(context.get(), peer.get(), step_count);
            require(
                std::memcmp(&report, &peer_report, sizeof(report)) == 0,
                "reserved scratch changed integration report bits");
            require(
                checkpoint(simulation.get()) == checkpoint(peer.get()),
                "reserved scratch changed checkpoint bits");
            const ForceScratchSnapshot current =
                force_scratch_snapshot(simulation.get());
            require_same_force_scratch_storage(
                current, reserved,
                "integration replaced reusable force scratch storage");
            require_force_scratch_sizes(
                current, fixture.x.size(),
                "integration retained the wrong force scratch size");
            require(
                force_scratch_bits(current) ==
                    force_scratch_bits(force_scratch_snapshot(peer.get())),
                "PME SoA force output differed from the peer bits");
        }

        const auto checkpoint_a = checkpoint(simulation.get());
        const ForceBits forces_a =
            force_scratch_bits(force_scratch_snapshot(simulation.get()));
        integrate(context.get(), simulation.get(), 1U);
        const ForceScratchSnapshot state_b =
            force_scratch_snapshot(simulation.get());
        require_same_force_scratch_storage(
            state_b, reserved,
            "state-B integration replaced final force scratch storage");
        const ForceBits forces_b = force_scratch_bits(state_b);
        require(
            forces_b != forces_a,
            "state-B integration did not refresh final force scratch");

        require_status(
            bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_load(
                simulation.get(), checkpoint_a.data(), checkpoint_a.size()),
            BG_STATUS_OK, "final force scratch checkpoint reload failed");
        const ForceScratchSnapshot after_load =
            force_scratch_snapshot(simulation.get());
        require_same_force_scratch_storage(
            after_load, state_b,
            "checkpoint reload replaced final force scratch storage");
        require(
            force_scratch_bits(after_load) == forces_b,
            "checkpoint reload unexpectedly rewrote stale final force scratch");

        const bg_dynamics_report_v1 restart_zero =
            integrate(context.get(), simulation.get(), 0U);
        const bg_dynamics_report_v1 peer_zero =
            integrate(context.get(), peer.get(), 0U);
        require(
            std::memcmp(&restart_zero, &peer_zero, sizeof(restart_zero)) == 0,
            "stale final force scratch changed zero-step report bits");
        require(
            checkpoint(simulation.get()) == checkpoint_a &&
                checkpoint(peer.get()) == checkpoint_a,
            "stale final force scratch changed zero-step checkpoint bits");
        const ForceScratchSnapshot after_restart_zero =
            force_scratch_snapshot(simulation.get());
        require_same_force_scratch_storage(
            after_restart_zero, state_b,
            "zero-step restart replaced final force scratch storage");
        require(
            force_scratch_bits(after_restart_zero) == forces_b,
            "zero-step restart changed stale final force scratch bits");

        const bg_dynamics_report_v1 restarted =
            integrate(context.get(), simulation.get(), 1U);
        const bg_dynamics_report_v1 peer_restarted =
            integrate(context.get(), peer.get(), 1U);
        require(
            std::memcmp(
                &restarted, &peer_restarted, sizeof(restarted)) == 0,
            "forceful restart with stale final scratch changed report bits");
        require(
            checkpoint(simulation.get()) == checkpoint(peer.get()),
            "forceful restart with stale final scratch changed state bits");
        const ForceScratchSnapshot after_resync =
            force_scratch_snapshot(simulation.get());
        require_same_force_scratch_storage(
            after_resync, reserved,
            "forceful restart replaced final force scratch storage");
        require(
            force_scratch_bits(after_resync) ==
                force_scratch_bits(force_scratch_snapshot(peer.get())),
            "forceful restart did not resynchronize final force scratch");

        const auto before_alias = checkpoint(simulation.get());
        const bg_particle_soa_view particles_before_alias =
            simulation_view(simulation.get());
        const std::array<const double *, 8> particle_addresses_before_alias{{
            particles_before_alias.position_x_angstrom,
            particles_before_alias.position_y_angstrom,
            particles_before_alias.position_z_angstrom,
            particles_before_alias.velocity_x_angstrom_per_femtosecond,
            particles_before_alias.velocity_y_angstrom_per_femtosecond,
            particles_before_alias.velocity_z_angstrom_per_femtosecond,
            particles_before_alias.mass_dalton,
            particles_before_alias.charge_elementary,
        }};
        const ForceBits forces_before_alias = force_scratch_bits(after_resync);
        auto *const aliased_step = reinterpret_cast<std::uint64_t *>(
            const_cast<double *>(after_resync.addresses[0]));
        require_status(
            bg_particle_mesh_ewald_composite_simulation_v1_get_absolute_step(
                simulation.get(), aliased_step),
            BG_STATUS_INVALID_ARGUMENT,
            "absolute-step output aliased final force scratch");
        const ForceScratchSnapshot after_alias =
            force_scratch_snapshot(simulation.get());
        require_same_force_scratch_storage(
            after_alias, after_resync,
            "rejected alias changed final force scratch storage");
        require(
            force_scratch_bits(after_alias) == forces_before_alias,
            "rejected alias changed final force scratch bits");
        require(
            checkpoint(simulation.get()) == before_alias,
            "rejected final-scratch alias changed checkpoint state");
        const bg_particle_soa_view particles_after_alias =
            simulation_view(simulation.get());
        const std::array<const double *, 8> particle_addresses_after_alias{{
            particles_after_alias.position_x_angstrom,
            particles_after_alias.position_y_angstrom,
            particles_after_alias.position_z_angstrom,
            particles_after_alias.velocity_x_angstrom_per_femtosecond,
            particles_after_alias.velocity_y_angstrom_per_femtosecond,
            particles_after_alias.velocity_z_angstrom_per_femtosecond,
            particles_after_alias.mass_dalton,
            particles_after_alias.charge_elementary,
        }};
        require(
            particle_addresses_after_alias == particle_addresses_before_alias,
            "rejected final-scratch alias changed authoritative storage identity");
    }
}

void verify_manual_velocity_verlet_final_force_bits() {
    constexpr double timestep = 0.001;
    const Fixture fixture;
    auto initial_system = make_system(fixture, fixture.charge);
    auto forcefield = make_forcefield(fixture);
    auto direct = make_direct_model(fixture);
    auto reciprocal = make_reciprocal_model(fixture);

    for (const bg_backend lane :
         {BG_BACKEND_CPP_CPU_REFERENCE, BG_BACKEND_RUST_CPU}) {
        auto context = make_context(lane);
        const StatelessEvaluation initial_force = evaluate_stateless(
            context.get(), initial_system.get(), forcefield.get(), direct.get(),
            reciprocal.get());

        Fixture drifted = fixture;
        const std::array<const std::array<double, kAtomCount> *, 3>
            force_channels{{
                &initial_force.force_x,
                &initial_force.force_y,
                &initial_force.force_z,
            }};
        const std::array<const std::array<double, kAtomCount> *, 3>
            initial_positions{{&fixture.x, &fixture.y, &fixture.z}};
        const std::array<const std::array<double, kAtomCount> *, 3>
            initial_velocities{{
                &fixture.velocity_x,
                &fixture.velocity_y,
                &fixture.velocity_z,
            }};
        const std::array<std::array<double, kAtomCount> *, 3>
            drifted_positions{{&drifted.x, &drifted.y, &drifted.z}};
        const std::array<std::array<double, kAtomCount> *, 3>
            half_velocities{{
                &drifted.velocity_x,
                &drifted.velocity_y,
                &drifted.velocity_z,
            }};
        const double half_timestep = 0.5 * timestep;
        for (std::size_t atom = 0U; atom < kAtomCount; ++atom) {
            const double half_kick_scale =
                kAccelerationConversion * half_timestep / fixture.mass[atom];
            for (std::size_t axis = 0U; axis < 3U; ++axis) {
                const double velocity =
                    (*initial_velocities[axis])[atom] +
                    half_kick_scale * (*force_channels[axis])[atom];
                (*half_velocities[axis])[atom] = velocity;
                (*drifted_positions[axis])[atom] =
                    (*initial_positions[axis])[atom] + timestep * velocity;
            }
        }

        auto drifted_system = make_system(drifted, drifted.charge);
        const StatelessEvaluation final_force = evaluate_stateless(
            context.get(), drifted_system.get(), forcefield.get(), direct.get(),
            reciprocal.get());
        auto simulation = make_simulation(
            initial_system.get(), forcefield.get(), direct.get(),
            reciprocal.get(), nullptr, timestep);
        integrate(context.get(), simulation.get(), 1U);
        const ForceScratchSnapshot stateful_force =
            force_scratch_snapshot(simulation.get());
        require(
            force_scratch_bits(stateful_force) ==
                stateless_force_bits(final_force),
            "PME stateful SoA force bits differed from stateless AoS bits");

        const bg_particle_soa_view observed = simulation_view(simulation.get());
        const std::array<const double *, 3> observed_positions{{
            observed.position_x_angstrom,
            observed.position_y_angstrom,
            observed.position_z_angstrom,
        }};
        for (std::size_t atom = 0U; atom < kAtomCount; ++atom) {
            for (std::size_t axis = 0U; axis < 3U; ++axis) {
                require_exact(
                    observed_positions[axis][atom],
                    (*drifted_positions[axis])[atom],
                    "PME one-step position differed from manual Velocity Verlet");
            }
        }
    }
}

void verify_short_parent_force_scratch_reuse() {
    constexpr std::size_t kReservedCapacity = 64U;
    const Fixture fixture;

    for (const bg_backend lane : {
             BG_BACKEND_CPP_CPU_REFERENCE,
             BG_BACKEND_RUST_CPU,
         }) {
        auto context = make_context(lane);
        auto system = make_system(fixture, fixture.charge);
        auto forcefield = make_forcefield(fixture);
        auto direct = make_direct_model(fixture);
        auto reciprocal = make_reciprocal_model(fixture);
        auto simulation = make_simulation(
            system.get(), forcefield.get(), direct.get(), reciprocal.get());
        auto peer = make_simulation(
            system.get(), forcefield.get(), direct.get(), reciprocal.get());

        const ShortParentForceScratchSnapshot initial =
            short_parent_force_scratch_snapshot(simulation.get());
        require_short_parent_force_scratch_sizes(
            initial,
            0U,
            "new PME short-parent force scratch was not empty");
        require(
            initial.capacities ==
                    std::array<std::size_t, 3>{0U, 0U, 0U} &&
                initial.rust_cpu_forcefield_validated == UINT8_C(0),
            "new PME short-parent force scratch or validation cache was not clear");

        betelgeuze::native::tests::
            reserve_particle_mesh_ewald_composite_force_scratch(
                simulation.get(), kReservedCapacity);
        betelgeuze::native::tests::
            reserve_particle_mesh_ewald_composite_short_parent_force_scratch(
                simulation.get(), kReservedCapacity);
        const ForceScratchSnapshot final_reserved =
            force_scratch_snapshot(simulation.get());
        const ShortParentForceScratchSnapshot reserved =
            short_parent_force_scratch_snapshot(simulation.get());
        require_short_parent_force_scratch_sizes(
            reserved,
            0U,
            "PME short-parent force scratch reserve changed logical size");
        require(
            reserved.rust_cpu_forcefield_validated == UINT8_C(0),
            "PME short-parent force scratch reserve changed validation cache");
        for (std::size_t axis = 0U; axis < 3U; ++axis) {
            require(
                reserved.addresses[axis] != nullptr &&
                    reserved.capacities[axis] >= kReservedCapacity,
                "PME short-parent force scratch reserve did not materialize storage");
            for (std::size_t other = axis + 1U; other < 3U; ++other) {
                require(
                    reserved.addresses[axis] != reserved.addresses[other],
                    "PME short-parent force scratch channels aliased");
            }
        }

        const ShortSystemScratchSnapshot short_system =
            short_system_scratch_snapshot(simulation.get());
        const bg_particle_soa_view view = simulation_view(simulation.get());
        const std::array<const double *, 8> authoritative{{
            view.position_x_angstrom,
            view.position_y_angstrom,
            view.position_z_angstrom,
            view.velocity_x_angstrom_per_femtosecond,
            view.velocity_y_angstrom_per_femtosecond,
            view.velocity_z_angstrom_per_femtosecond,
            view.mass_dalton,
            view.charge_elementary,
        }};
        for (const double *const short_parent_address : reserved.addresses) {
            for (const double *const final_address :
                 final_reserved.addresses) {
                require(
                    short_parent_address != final_address,
                    "PME short-parent scratch aliased final force scratch");
            }
            for (const double *const short_system_address :
                 short_system.addresses) {
                require(
                    short_parent_address != short_system_address,
                    "PME short-parent scratch aliased short-system scratch");
            }
            for (const double *const owner_address : authoritative) {
                require(
                    short_parent_address != owner_address,
                    "PME short-parent scratch aliased authoritative owner storage");
            }
        }

        const auto before_zero = checkpoint(simulation.get());
        const bg_dynamics_report_v1 zero_report =
            integrate(context.get(), simulation.get(), UINT64_C(0));
        const bg_dynamics_report_v1 peer_zero_report =
            integrate(context.get(), peer.get(), UINT64_C(0));
        require(
            std::memcmp(
                &zero_report, &peer_zero_report, sizeof(zero_report)) == 0,
            "reserved PME short-parent scratch changed zero-step report bits");
        require(
            checkpoint(simulation.get()) == before_zero,
            "zero-step integration changed checkpoint state");
        const ShortParentForceScratchSnapshot after_zero =
            short_parent_force_scratch_snapshot(simulation.get());
        require_same_short_parent_force_scratch_storage(
            after_zero,
            reserved,
            "zero-step integration changed PME short-parent scratch storage");
        require_short_parent_force_scratch_sizes(
            after_zero,
            0U,
            "zero-step integration changed PME short-parent scratch size");
        require(
            after_zero.rust_cpu_forcefield_validated == UINT8_C(0),
            "zero-step integration changed PME Rust validation cache");

        for (const std::uint64_t step_count :
             {UINT64_C(1), UINT64_C(2)}) {
            const bg_dynamics_report_v1 report =
                integrate(context.get(), simulation.get(), step_count);
            const bg_dynamics_report_v1 peer_report =
                integrate(context.get(), peer.get(), step_count);
            require(
                std::memcmp(&report, &peer_report, sizeof(report)) == 0,
                "reused PME short-parent scratch changed integration report bits");
            require(
                checkpoint(simulation.get()) == checkpoint(peer.get()),
                "reused PME short-parent scratch changed checkpoint bits");
            const ShortParentForceScratchSnapshot current =
                short_parent_force_scratch_snapshot(simulation.get());
            require_same_short_parent_force_scratch_storage(
                current,
                reserved,
                "integration replaced PME short-parent force scratch storage");
            require_short_parent_force_scratch_sizes(
                current,
                kAtomCount,
                "integration retained the wrong PME short-parent scratch size");
            require(
                current.rust_cpu_forcefield_validated ==
                    (lane == BG_BACKEND_RUST_CPU ? UINT8_C(1)
                                                 : UINT8_C(0)),
                "PME short-parent evaluation retained the wrong Rust validation flag");
        }

        const auto checkpoint_a = checkpoint(simulation.get());
        const ForceBits forces_a = short_parent_force_scratch_bits(
            short_parent_force_scratch_snapshot(simulation.get()));
        integrate(context.get(), simulation.get(), UINT64_C(1));
        const ShortParentForceScratchSnapshot state_b =
            short_parent_force_scratch_snapshot(simulation.get());
        require_same_short_parent_force_scratch_storage(
            state_b,
            reserved,
            "state-B integration replaced PME short-parent force scratch storage");
        const ForceBits forces_b = short_parent_force_scratch_bits(state_b);
        require(
            forces_b != forces_a,
            "state-B integration did not refresh PME short-parent force scratch");

        require_status(
            bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_load(
                simulation.get(), checkpoint_a.data(), checkpoint_a.size()),
            BG_STATUS_OK,
            "PME short-parent scratch checkpoint reload failed");
        const ShortParentForceScratchSnapshot after_load =
            short_parent_force_scratch_snapshot(simulation.get());
        require_same_short_parent_force_scratch_storage(
            after_load,
            state_b,
            "checkpoint reload replaced PME short-parent force scratch storage");
        require(
            short_parent_force_scratch_bits(after_load) == forces_b &&
                after_load.rust_cpu_forcefield_validated ==
                    state_b.rust_cpu_forcefield_validated,
            "checkpoint reload unexpectedly rewrote PME short-parent scratch/cache");

        const bg_dynamics_report_v1 restart_zero =
            integrate(context.get(), simulation.get(), UINT64_C(0));
        const bg_dynamics_report_v1 peer_zero =
            integrate(context.get(), peer.get(), UINT64_C(0));
        require(
            std::memcmp(&restart_zero, &peer_zero, sizeof(restart_zero)) == 0,
            "stale PME short-parent scratch changed zero-step report bits");
        require(
            checkpoint(simulation.get()) == checkpoint_a &&
                checkpoint(peer.get()) == checkpoint_a,
            "stale PME short-parent scratch changed zero-step checkpoint bits");
        const ShortParentForceScratchSnapshot after_restart_zero =
            short_parent_force_scratch_snapshot(simulation.get());
        require_same_short_parent_force_scratch_storage(
            after_restart_zero,
            state_b,
            "zero-step restart replaced PME short-parent force scratch storage");
        require(
            short_parent_force_scratch_bits(after_restart_zero) == forces_b &&
                after_restart_zero.rust_cpu_forcefield_validated ==
                    state_b.rust_cpu_forcefield_validated,
            "zero-step restart changed stale PME short-parent scratch/cache");

        const bg_dynamics_report_v1 restarted =
            integrate(context.get(), simulation.get(), UINT64_C(1));
        const bg_dynamics_report_v1 peer_restarted =
            integrate(context.get(), peer.get(), UINT64_C(1));
        require(
            std::memcmp(&restarted, &peer_restarted, sizeof(restarted)) == 0,
            "forceful restart with stale PME scratch changed report bits");
        require(
            checkpoint(simulation.get()) == checkpoint(peer.get()),
            "forceful restart with stale PME scratch changed checkpoint bits");
        const ShortParentForceScratchSnapshot after_resync =
            short_parent_force_scratch_snapshot(simulation.get());
        require_same_short_parent_force_scratch_storage(
            after_resync,
            reserved,
            "forceful restart replaced PME short-parent force scratch storage");
        require(
            short_parent_force_scratch_bits(after_resync) ==
                short_parent_force_scratch_bits(
                    short_parent_force_scratch_snapshot(peer.get())),
            "forceful restart did not resynchronize PME short-parent force scratch");

        const auto before_alias = checkpoint(simulation.get());
        const bg_particle_soa_view particles_before_alias =
            simulation_view(simulation.get());
        const std::array<const double *, 8> particle_addresses_before_alias{{
            particles_before_alias.position_x_angstrom,
            particles_before_alias.position_y_angstrom,
            particles_before_alias.position_z_angstrom,
            particles_before_alias.velocity_x_angstrom_per_femtosecond,
            particles_before_alias.velocity_y_angstrom_per_femtosecond,
            particles_before_alias.velocity_z_angstrom_per_femtosecond,
            particles_before_alias.mass_dalton,
            particles_before_alias.charge_elementary,
        }};
        const ForceBits forces_before_alias =
            short_parent_force_scratch_bits(after_resync);
        auto *const aliased_step = reinterpret_cast<std::uint64_t *>(
            const_cast<double *>(after_resync.addresses[0]));
        require_status(
            bg_particle_mesh_ewald_composite_simulation_v1_get_absolute_step(
                simulation.get(), aliased_step),
            BG_STATUS_INVALID_ARGUMENT,
            "absolute-step output aliased PME short-parent force scratch");
        const ShortParentForceScratchSnapshot after_alias =
            short_parent_force_scratch_snapshot(simulation.get());
        require_same_short_parent_force_scratch_storage(
            after_alias,
            after_resync,
            "rejected scratch alias changed PME short-parent storage");
        require(
            short_parent_force_scratch_bits(after_alias) ==
                    forces_before_alias &&
                after_alias.rust_cpu_forcefield_validated ==
                    after_resync.rust_cpu_forcefield_validated,
            "rejected scratch alias changed PME short-parent scratch/cache");
        require(
            checkpoint(simulation.get()) == before_alias,
            "rejected scratch alias changed PME checkpoint state");
        const bg_particle_soa_view particles_after_alias =
            simulation_view(simulation.get());
        const std::array<const double *, 8> particle_addresses_after_alias{{
            particles_after_alias.position_x_angstrom,
            particles_after_alias.position_y_angstrom,
            particles_after_alias.position_z_angstrom,
            particles_after_alias.velocity_x_angstrom_per_femtosecond,
            particles_after_alias.velocity_y_angstrom_per_femtosecond,
            particles_after_alias.velocity_z_angstrom_per_femtosecond,
            particles_after_alias.mass_dalton,
            particles_after_alias.charge_elementary,
        }};
        require(
            particle_addresses_after_alias == particle_addresses_before_alias,
            "rejected scratch alias changed PME authoritative storage identity");
    }
}

void verify_direct_parent_force_scratch_reuse() {
    constexpr std::size_t kReservedCapacity = 64U;
    const Fixture fixture;

    for (const bg_backend lane : {
             BG_BACKEND_CPP_CPU_REFERENCE,
             BG_BACKEND_RUST_CPU,
         }) {
        auto context = make_context(lane);
        auto system = make_system(fixture, fixture.charge);
        auto forcefield = make_forcefield(fixture);
        auto direct = make_direct_model(fixture);
        auto reciprocal = make_reciprocal_model(fixture);
        auto simulation = make_simulation(
            system.get(), forcefield.get(), direct.get(), reciprocal.get());
        auto peer = make_simulation(
            system.get(), forcefield.get(), direct.get(), reciprocal.get());

        const DirectParentForceScratchSnapshot initial =
            direct_parent_force_scratch_snapshot(simulation.get());
        require(
            initial.size == 0U && initial.capacity == 0U,
            "new PME direct-parent force scratch was not empty");
        betelgeuze::native::tests::
            reserve_particle_mesh_ewald_composite_direct_parent_force_scratch(
                simulation.get(), kReservedCapacity);
        const DirectParentForceScratchSnapshot reserved =
            direct_parent_force_scratch_snapshot(simulation.get());
        require(
            reserved.address != nullptr && reserved.size == 0U &&
                reserved.capacity >= kReservedCapacity,
            "PME direct-parent force scratch reserve did not retain empty storage");

        const auto before_zero = checkpoint(simulation.get());
        const bg_dynamics_report_v1 zero_report =
            integrate(context.get(), simulation.get(), UINT64_C(0));
        const bg_dynamics_report_v1 peer_zero_report =
            integrate(context.get(), peer.get(), UINT64_C(0));
        require(
            std::memcmp(
                &zero_report, &peer_zero_report, sizeof(zero_report)) == 0,
            "reserved PME direct-parent scratch changed zero-step report bits");
        require(
            checkpoint(simulation.get()) == before_zero,
            "zero-step integration changed checkpoint state");
        const DirectParentForceScratchSnapshot after_zero =
            direct_parent_force_scratch_snapshot(simulation.get());
        require_same_direct_parent_force_scratch_storage(
            after_zero,
            reserved,
            "zero-step integration changed PME direct-parent scratch storage");
        require(
            after_zero.size == 0U,
            "zero-step integration changed PME direct-parent scratch size");

        const auto stateless_bits_for_owner = [&]() {
            Fixture current = fixture;
            const bg_particle_soa_view view = simulation_view(simulation.get());
            std::copy_n(
                view.position_x_angstrom, kAtomCount, current.x.begin());
            std::copy_n(
                view.position_y_angstrom, kAtomCount, current.y.begin());
            std::copy_n(
                view.position_z_angstrom, kAtomCount, current.z.begin());
            const auto current_system = make_system(current, current.charge);
            return evaluate_stateless_direct_local_force_bits(
                context.get(), current_system.get(), direct.get());
        };

        for (const std::uint64_t step_count : {
                 UINT64_C(1),
                 UINT64_C(2),
             }) {
            const bg_dynamics_report_v1 report =
                integrate(context.get(), simulation.get(), step_count);
            const bg_dynamics_report_v1 peer_report =
                integrate(context.get(), peer.get(), step_count);
            require(
                std::memcmp(&report, &peer_report, sizeof(report)) == 0,
                "reused PME direct-parent scratch changed integration report bits");
            require(
                checkpoint(simulation.get()) == checkpoint(peer.get()),
                "reused PME direct-parent scratch changed checkpoint bits");
            const DirectParentForceScratchSnapshot current =
                direct_parent_force_scratch_snapshot(simulation.get());
            require_same_direct_parent_force_scratch_storage(
                current,
                reserved,
                "integration replaced PME direct-parent force scratch storage");
            require(
                current.size == kAtomCount,
                "integration retained the wrong PME direct-parent scratch size");
            require(
                direct_parent_force_scratch_bits(current) ==
                    direct_parent_force_scratch_bits(
                        direct_parent_force_scratch_snapshot(peer.get())),
                "PME direct-parent scratch differed from same-lane peer bits");
            require(
                direct_parent_force_scratch_bits(current) ==
                    stateless_bits_for_owner(),
                "PME direct-parent scratch differed from stateless direct-local force bits");
        }

        const auto checkpoint_a = checkpoint(simulation.get());
        const ForceBits forces_a = direct_parent_force_scratch_bits(
            direct_parent_force_scratch_snapshot(simulation.get()));
        integrate(context.get(), simulation.get(), UINT64_C(1));
        const DirectParentForceScratchSnapshot state_b =
            direct_parent_force_scratch_snapshot(simulation.get());
        require_same_direct_parent_force_scratch_storage(
            state_b,
            reserved,
            "state-B integration replaced PME direct-parent scratch storage");
        const ForceBits forces_b = direct_parent_force_scratch_bits(state_b);
        require(
            forces_b != forces_a,
            "state-B integration did not refresh PME direct-parent scratch");

        require_status(
            bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_load(
                simulation.get(), checkpoint_a.data(), checkpoint_a.size()),
            BG_STATUS_OK,
            "PME direct-parent scratch checkpoint reload failed");
        const DirectParentForceScratchSnapshot after_load =
            direct_parent_force_scratch_snapshot(simulation.get());
        require_same_direct_parent_force_scratch_storage(
            after_load,
            state_b,
            "checkpoint reload replaced PME direct-parent scratch storage");
        require(
            direct_parent_force_scratch_bits(after_load) == forces_b,
            "checkpoint reload unexpectedly rewrote stale PME direct-parent scratch");

        const bg_dynamics_report_v1 restart_zero =
            integrate(context.get(), simulation.get(), UINT64_C(0));
        const bg_dynamics_report_v1 peer_zero =
            integrate(context.get(), peer.get(), UINT64_C(0));
        require(
            std::memcmp(&restart_zero, &peer_zero, sizeof(restart_zero)) == 0,
            "stale PME direct-parent scratch changed zero-step report bits");
        require(
            checkpoint(simulation.get()) == checkpoint_a &&
                checkpoint(peer.get()) == checkpoint_a,
            "stale PME direct-parent scratch changed zero-step checkpoint bits");
        const DirectParentForceScratchSnapshot after_restart_zero =
            direct_parent_force_scratch_snapshot(simulation.get());
        require_same_direct_parent_force_scratch_storage(
            after_restart_zero,
            state_b,
            "zero-step restart replaced PME direct-parent scratch storage");
        require(
            direct_parent_force_scratch_bits(after_restart_zero) == forces_b,
            "zero-step restart changed stale PME direct-parent scratch bits");

        const bg_dynamics_report_v1 restarted =
            integrate(context.get(), simulation.get(), UINT64_C(1));
        const bg_dynamics_report_v1 peer_restarted =
            integrate(context.get(), peer.get(), UINT64_C(1));
        require(
            std::memcmp(
                &restarted, &peer_restarted, sizeof(restarted)) == 0,
            "forceful restart with stale PME direct scratch changed report bits");
        require(
            checkpoint(simulation.get()) == checkpoint(peer.get()),
            "forceful restart with stale PME direct scratch changed state bits");
        const DirectParentForceScratchSnapshot after_resync =
            direct_parent_force_scratch_snapshot(simulation.get());
        require_same_direct_parent_force_scratch_storage(
            after_resync,
            reserved,
            "forceful restart replaced PME direct-parent scratch storage");
        require(
            direct_parent_force_scratch_bits(after_resync) ==
                    direct_parent_force_scratch_bits(
                        direct_parent_force_scratch_snapshot(peer.get())) &&
                direct_parent_force_scratch_bits(after_resync) ==
                    stateless_bits_for_owner(),
            "forceful restart did not resynchronize PME direct-parent scratch");

        const auto before_step_alias = checkpoint(simulation.get());
        const bg_particle_soa_view particles_before_step_alias =
            simulation_view(simulation.get());
        const PositionBits positions_before_step_alias =
            view_position_bits(particles_before_step_alias);
        const std::array<const double *, 8> addresses_before_step_alias{{
            particles_before_step_alias.position_x_angstrom,
            particles_before_step_alias.position_y_angstrom,
            particles_before_step_alias.position_z_angstrom,
            particles_before_step_alias.velocity_x_angstrom_per_femtosecond,
            particles_before_step_alias.velocity_y_angstrom_per_femtosecond,
            particles_before_step_alias.velocity_z_angstrom_per_femtosecond,
            particles_before_step_alias.mass_dalton,
            particles_before_step_alias.charge_elementary,
        }};
        const ForceBits forces_before_step_alias =
            direct_parent_force_scratch_bits(after_resync);
        auto *const aliased_step = reinterpret_cast<std::uint64_t *>(
            const_cast<double *>(&after_resync.address[1][1]));
        require_status(
            bg_particle_mesh_ewald_composite_simulation_v1_get_absolute_step(
                simulation.get(), aliased_step),
            BG_STATUS_INVALID_ARGUMENT,
            "absolute-step output aliased PME direct-parent force scratch");
        require(
            std::strcmp(
                bg_last_error_message(),
                "absolute_step output must not overlap particle-mesh composite dynamics owner storage") ==
                0,
            "absolute-step alias was not rejected by the PME owner-overlap guard");
        const DirectParentForceScratchSnapshot after_step_alias =
            direct_parent_force_scratch_snapshot(simulation.get());
        require_same_direct_parent_force_scratch_storage(
            after_step_alias,
            after_resync,
            "rejected step alias changed PME direct-parent scratch storage");
        require(
            direct_parent_force_scratch_bits(after_step_alias) ==
                    forces_before_step_alias &&
                checkpoint(simulation.get()) == before_step_alias,
            "rejected step alias changed PME direct scratch or checkpoint bits");
        const bg_particle_soa_view particles_after_step_alias =
            simulation_view(simulation.get());
        const std::array<const double *, 8> addresses_after_step_alias{{
            particles_after_step_alias.position_x_angstrom,
            particles_after_step_alias.position_y_angstrom,
            particles_after_step_alias.position_z_angstrom,
            particles_after_step_alias.velocity_x_angstrom_per_femtosecond,
            particles_after_step_alias.velocity_y_angstrom_per_femtosecond,
            particles_after_step_alias.velocity_z_angstrom_per_femtosecond,
            particles_after_step_alias.mass_dalton,
            particles_after_step_alias.charge_elementary,
        }};
        require(
            addresses_after_step_alias == addresses_before_step_alias &&
                view_position_bits(particles_after_step_alias) ==
                    positions_before_step_alias,
            "rejected PME direct step alias changed authoritative state");

        const DirectParentForceScratchSnapshot before_view_alias =
            direct_parent_force_scratch_snapshot(simulation.get());
        const ForceBits forces_before_view_alias =
            direct_parent_force_scratch_bits(before_view_alias);
        const auto checkpoint_before_view_alias = checkpoint(simulation.get());
        const bg_particle_soa_view particles_before_view_alias =
            simulation_view(simulation.get());
        const PositionBits positions_before_view_alias =
            view_position_bits(particles_before_view_alias);
        const std::array<const double *, 8> addresses_before_view_alias{{
            particles_before_view_alias.position_x_angstrom,
            particles_before_view_alias.position_y_angstrom,
            particles_before_view_alias.position_z_angstrom,
            particles_before_view_alias.velocity_x_angstrom_per_femtosecond,
            particles_before_view_alias.velocity_y_angstrom_per_femtosecond,
            particles_before_view_alias.velocity_z_angstrom_per_femtosecond,
            particles_before_view_alias.mass_dalton,
            particles_before_view_alias.charge_elementary,
        }};
        auto *const aliased_view = reinterpret_cast<bg_particle_soa_view *>(
            const_cast<std::array<double, 3> *>(
                before_view_alias.address + 1U));
        require_status(
            bg_particle_mesh_ewald_composite_simulation_v1_get_particles(
                simulation.get(), aliased_view),
            BG_STATUS_INVALID_ARGUMENT,
            "particle-view output aliased PME direct-parent force scratch");
        require(
            std::strcmp(
                bg_last_error_message(),
                "particle view output must not overlap particle-mesh composite dynamics owner storage") ==
                0,
            "particle-view alias was not rejected by the PME owner-overlap guard");
        const DirectParentForceScratchSnapshot after_view_alias =
            direct_parent_force_scratch_snapshot(simulation.get());
        require_same_direct_parent_force_scratch_storage(
            after_view_alias,
            before_view_alias,
            "rejected view alias changed PME direct-parent scratch storage");
        require(
            after_view_alias.size == before_view_alias.size &&
                direct_parent_force_scratch_bits(after_view_alias) ==
                    forces_before_view_alias,
            "rejected view alias changed PME direct-parent scratch bytes");
        require(
            checkpoint(simulation.get()) == checkpoint_before_view_alias,
            "rejected view alias changed PME checkpoint state");
        const bg_particle_soa_view particles_after_view_alias =
            simulation_view(simulation.get());
        const std::array<const double *, 8> addresses_after_view_alias{{
            particles_after_view_alias.position_x_angstrom,
            particles_after_view_alias.position_y_angstrom,
            particles_after_view_alias.position_z_angstrom,
            particles_after_view_alias.velocity_x_angstrom_per_femtosecond,
            particles_after_view_alias.velocity_y_angstrom_per_femtosecond,
            particles_after_view_alias.velocity_z_angstrom_per_femtosecond,
            particles_after_view_alias.mass_dalton,
            particles_after_view_alias.charge_elementary,
        }};
        require(
            addresses_after_view_alias == addresses_before_view_alias &&
                view_position_bits(particles_after_view_alias) ==
                    positions_before_view_alias,
            "rejected PME direct view alias changed authoritative state");
    }
}

void verify_reciprocal_parent_force_scratch_reuse() {
    constexpr std::size_t kReservedCapacity = 64U;
    const Fixture fixture;

    for (const bg_backend lane : {BG_BACKEND_CPP_CPU_REFERENCE}) {
        auto context = make_context(lane);
        auto system = make_system(fixture, fixture.charge);
        auto forcefield = make_forcefield(fixture);
        auto direct = make_direct_model(fixture);
        auto reciprocal = make_reciprocal_model(fixture);
        auto simulation = make_simulation(
            system.get(), forcefield.get(), direct.get(), reciprocal.get());
        auto peer = make_simulation(
            system.get(), forcefield.get(), direct.get(), reciprocal.get());

        const ReciprocalParentForceScratchSnapshot initial =
            reciprocal_parent_force_scratch_snapshot(simulation.get());
        require(
            initial.size == 0U && initial.capacity == 0U,
            "new PME reciprocal-parent force scratch was not empty");
        betelgeuze::native::tests::
            reserve_particle_mesh_ewald_composite_reciprocal_parent_force_scratch(
                simulation.get(), kReservedCapacity);
        const ReciprocalParentForceScratchSnapshot reserved =
            reciprocal_parent_force_scratch_snapshot(simulation.get());
        require(
            reserved.address != nullptr && reserved.size == 0U &&
                reserved.capacity >= kReservedCapacity,
            "PME reciprocal-parent force scratch reserve did not retain empty storage");

        const auto before_zero = checkpoint(simulation.get());
        const bg_dynamics_report_v1 zero_report =
            integrate(context.get(), simulation.get(), UINT64_C(0));
        const bg_dynamics_report_v1 peer_zero_report =
            integrate(context.get(), peer.get(), UINT64_C(0));
        require(
            std::memcmp(
                &zero_report, &peer_zero_report, sizeof(zero_report)) == 0,
            "reserved PME reciprocal-parent scratch changed zero-step report bits");
        require(
            checkpoint(simulation.get()) == before_zero,
            "zero-step integration changed checkpoint state");
        const ReciprocalParentForceScratchSnapshot after_zero =
            reciprocal_parent_force_scratch_snapshot(simulation.get());
        require_same_reciprocal_parent_force_scratch_storage(
            after_zero,
            reserved,
            "zero-step integration changed PME reciprocal-parent scratch storage");
        require(
            after_zero.size == 0U,
            "zero-step integration changed PME reciprocal-parent scratch size");

        const auto stateless_bits_for_owner = [&]() {
            Fixture current = fixture;
            const bg_particle_soa_view view = simulation_view(simulation.get());
            std::copy_n(
                view.position_x_angstrom, kAtomCount, current.x.begin());
            std::copy_n(
                view.position_y_angstrom, kAtomCount, current.y.begin());
            std::copy_n(
                view.position_z_angstrom, kAtomCount, current.z.begin());
            const auto current_system = make_system(current, current.charge);
            return evaluate_stateless_reciprocal_force_bits(
                context.get(), current_system.get(), reciprocal.get());
        };

        for (const std::uint64_t step_count : {
                 UINT64_C(1),
                 UINT64_C(2),
             }) {
            const bg_dynamics_report_v1 report =
                integrate(context.get(), simulation.get(), step_count);
            const bg_dynamics_report_v1 peer_report =
                integrate(context.get(), peer.get(), step_count);
            require(
                std::memcmp(&report, &peer_report, sizeof(report)) == 0,
                "reused PME reciprocal-parent scratch changed integration report bits");
            require(
                checkpoint(simulation.get()) == checkpoint(peer.get()),
                "reused PME reciprocal-parent scratch changed checkpoint bits");
            const ReciprocalParentForceScratchSnapshot current =
                reciprocal_parent_force_scratch_snapshot(simulation.get());
            require_same_reciprocal_parent_force_scratch_storage(
                current,
                reserved,
                "integration replaced PME reciprocal-parent force scratch storage");
            require(
                current.size == kAtomCount,
                "integration retained the wrong PME reciprocal-parent scratch size");
            require(
                reciprocal_parent_force_scratch_bits(current) ==
                    reciprocal_parent_force_scratch_bits(
                        reciprocal_parent_force_scratch_snapshot(peer.get())),
                "PME reciprocal-parent scratch differed from same-lane peer bits");
            require(
                reciprocal_parent_force_scratch_bits(current) ==
                    stateless_bits_for_owner(),
                "PME reciprocal-parent scratch differed from stateless reciprocal force bits");
        }

        const auto checkpoint_a = checkpoint(simulation.get());
        const ForceBits forces_a = reciprocal_parent_force_scratch_bits(
            reciprocal_parent_force_scratch_snapshot(simulation.get()));
        integrate(context.get(), simulation.get(), UINT64_C(1));
        const ReciprocalParentForceScratchSnapshot state_b =
            reciprocal_parent_force_scratch_snapshot(simulation.get());
        require_same_reciprocal_parent_force_scratch_storage(
            state_b,
            reserved,
            "state-B integration replaced PME reciprocal-parent scratch storage");
        const ForceBits forces_b =
            reciprocal_parent_force_scratch_bits(state_b);
        require(
            forces_b != forces_a,
            "state-B integration did not refresh PME reciprocal-parent scratch");

        require_status(
            bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_load(
                simulation.get(), checkpoint_a.data(), checkpoint_a.size()),
            BG_STATUS_OK,
            "PME reciprocal-parent scratch checkpoint reload failed");
        const ReciprocalParentForceScratchSnapshot after_load =
            reciprocal_parent_force_scratch_snapshot(simulation.get());
        require_same_reciprocal_parent_force_scratch_storage(
            after_load,
            state_b,
            "checkpoint reload replaced PME reciprocal-parent scratch storage");
        require(
            reciprocal_parent_force_scratch_bits(after_load) == forces_b,
            "checkpoint reload unexpectedly rewrote stale PME reciprocal-parent scratch");

        const bg_dynamics_report_v1 restart_zero =
            integrate(context.get(), simulation.get(), UINT64_C(0));
        const bg_dynamics_report_v1 peer_zero =
            integrate(context.get(), peer.get(), UINT64_C(0));
        require(
            std::memcmp(&restart_zero, &peer_zero, sizeof(restart_zero)) == 0,
            "stale PME reciprocal-parent scratch changed zero-step report bits");
        require(
            checkpoint(simulation.get()) == checkpoint_a &&
                checkpoint(peer.get()) == checkpoint_a,
            "stale PME reciprocal-parent scratch changed zero-step checkpoint bits");
        const ReciprocalParentForceScratchSnapshot after_restart_zero =
            reciprocal_parent_force_scratch_snapshot(simulation.get());
        require_same_reciprocal_parent_force_scratch_storage(
            after_restart_zero,
            state_b,
            "zero-step restart replaced PME reciprocal-parent scratch storage");
        require(
            reciprocal_parent_force_scratch_bits(after_restart_zero) == forces_b,
            "zero-step restart changed stale PME reciprocal-parent scratch bits");

        const bg_dynamics_report_v1 restarted =
            integrate(context.get(), simulation.get(), UINT64_C(1));
        const bg_dynamics_report_v1 peer_restarted =
            integrate(context.get(), peer.get(), UINT64_C(1));
        require(
            std::memcmp(
                &restarted, &peer_restarted, sizeof(restarted)) == 0,
            "forceful restart with stale PME reciprocal scratch changed report bits");
        require(
            checkpoint(simulation.get()) == checkpoint(peer.get()),
            "forceful restart with stale PME reciprocal scratch changed state bits");
        const ReciprocalParentForceScratchSnapshot after_resync =
            reciprocal_parent_force_scratch_snapshot(simulation.get());
        require_same_reciprocal_parent_force_scratch_storage(
            after_resync,
            reserved,
            "forceful restart replaced PME reciprocal-parent scratch storage");
        require(
            reciprocal_parent_force_scratch_bits(after_resync) ==
                    reciprocal_parent_force_scratch_bits(
                        reciprocal_parent_force_scratch_snapshot(peer.get())) &&
                reciprocal_parent_force_scratch_bits(after_resync) ==
                    stateless_bits_for_owner(),
            "forceful restart did not resynchronize PME reciprocal-parent scratch");

        const auto before_step_alias = checkpoint(simulation.get());
        const bg_particle_soa_view particles_before_step_alias =
            simulation_view(simulation.get());
        const PositionBits positions_before_step_alias =
            view_position_bits(particles_before_step_alias);
        const std::array<const double *, 8> addresses_before_step_alias{{
            particles_before_step_alias.position_x_angstrom,
            particles_before_step_alias.position_y_angstrom,
            particles_before_step_alias.position_z_angstrom,
            particles_before_step_alias.velocity_x_angstrom_per_femtosecond,
            particles_before_step_alias.velocity_y_angstrom_per_femtosecond,
            particles_before_step_alias.velocity_z_angstrom_per_femtosecond,
            particles_before_step_alias.mass_dalton,
            particles_before_step_alias.charge_elementary,
        }};
        const ForceBits forces_before_step_alias =
            reciprocal_parent_force_scratch_bits(after_resync);
        auto *const aliased_step = reinterpret_cast<std::uint64_t *>(
            const_cast<double *>(&after_resync.address[1][1]));
        require_status(
            bg_particle_mesh_ewald_composite_simulation_v1_get_absolute_step(
                simulation.get(), aliased_step),
            BG_STATUS_INVALID_ARGUMENT,
            "absolute-step output aliased PME reciprocal-parent force scratch");
        require(
            std::strcmp(
                bg_last_error_message(),
                "absolute_step output must not overlap particle-mesh composite dynamics owner storage") ==
                0,
            "absolute-step reciprocal alias was not rejected by the PME owner-overlap guard");
        const ReciprocalParentForceScratchSnapshot after_step_alias =
            reciprocal_parent_force_scratch_snapshot(simulation.get());
        require_same_reciprocal_parent_force_scratch_storage(
            after_step_alias,
            after_resync,
            "rejected step alias changed PME reciprocal-parent scratch storage");
        require(
            reciprocal_parent_force_scratch_bits(after_step_alias) ==
                    forces_before_step_alias &&
                checkpoint(simulation.get()) == before_step_alias,
            "rejected step alias changed PME reciprocal scratch or checkpoint bits");
        const bg_particle_soa_view particles_after_step_alias =
            simulation_view(simulation.get());
        const std::array<const double *, 8> addresses_after_step_alias{{
            particles_after_step_alias.position_x_angstrom,
            particles_after_step_alias.position_y_angstrom,
            particles_after_step_alias.position_z_angstrom,
            particles_after_step_alias.velocity_x_angstrom_per_femtosecond,
            particles_after_step_alias.velocity_y_angstrom_per_femtosecond,
            particles_after_step_alias.velocity_z_angstrom_per_femtosecond,
            particles_after_step_alias.mass_dalton,
            particles_after_step_alias.charge_elementary,
        }};
        require(
            addresses_after_step_alias == addresses_before_step_alias &&
                view_position_bits(particles_after_step_alias) ==
                    positions_before_step_alias,
            "rejected PME reciprocal step alias changed authoritative state");

        const ReciprocalParentForceScratchSnapshot before_view_alias =
            reciprocal_parent_force_scratch_snapshot(simulation.get());
        const ForceBits forces_before_view_alias =
            reciprocal_parent_force_scratch_bits(before_view_alias);
        const auto checkpoint_before_view_alias = checkpoint(simulation.get());
        const bg_particle_soa_view particles_before_view_alias =
            simulation_view(simulation.get());
        const PositionBits positions_before_view_alias =
            view_position_bits(particles_before_view_alias);
        const std::array<const double *, 8> addresses_before_view_alias{{
            particles_before_view_alias.position_x_angstrom,
            particles_before_view_alias.position_y_angstrom,
            particles_before_view_alias.position_z_angstrom,
            particles_before_view_alias.velocity_x_angstrom_per_femtosecond,
            particles_before_view_alias.velocity_y_angstrom_per_femtosecond,
            particles_before_view_alias.velocity_z_angstrom_per_femtosecond,
            particles_before_view_alias.mass_dalton,
            particles_before_view_alias.charge_elementary,
        }};
        auto *const aliased_view = reinterpret_cast<bg_particle_soa_view *>(
            const_cast<std::array<double, 3> *>(
                before_view_alias.address + 1U));
        require_status(
            bg_particle_mesh_ewald_composite_simulation_v1_get_particles(
                simulation.get(), aliased_view),
            BG_STATUS_INVALID_ARGUMENT,
            "particle-view output aliased PME reciprocal-parent force scratch");
        require(
            std::strcmp(
                bg_last_error_message(),
                "particle view output must not overlap particle-mesh composite dynamics owner storage") ==
                0,
            "particle-view reciprocal alias was not rejected by the PME owner-overlap guard");
        const ReciprocalParentForceScratchSnapshot after_view_alias =
            reciprocal_parent_force_scratch_snapshot(simulation.get());
        require_same_reciprocal_parent_force_scratch_storage(
            after_view_alias,
            before_view_alias,
            "rejected view alias changed PME reciprocal-parent scratch storage");
        require(
            after_view_alias.size == before_view_alias.size &&
                reciprocal_parent_force_scratch_bits(after_view_alias) ==
                    forces_before_view_alias,
            "rejected view alias changed PME reciprocal-parent scratch bytes");
        require(
            checkpoint(simulation.get()) == checkpoint_before_view_alias,
            "rejected reciprocal view alias changed PME checkpoint state");
        const bg_particle_soa_view particles_after_view_alias =
            simulation_view(simulation.get());
        const std::array<const double *, 8> addresses_after_view_alias{{
            particles_after_view_alias.position_x_angstrom,
            particles_after_view_alias.position_y_angstrom,
            particles_after_view_alias.position_z_angstrom,
            particles_after_view_alias.velocity_x_angstrom_per_femtosecond,
            particles_after_view_alias.velocity_y_angstrom_per_femtosecond,
            particles_after_view_alias.velocity_z_angstrom_per_femtosecond,
            particles_after_view_alias.mass_dalton,
            particles_after_view_alias.charge_elementary,
        }};
        require(
            addresses_after_view_alias == addresses_before_view_alias &&
                view_position_bits(particles_after_view_alias) ==
                    positions_before_view_alias,
            "rejected PME reciprocal view alias changed authoritative state");
    }
}

void verify_rust_reciprocal_provider_force_scratch_reuse() {
    constexpr std::size_t kReservedCapacity = 64U;
    const Fixture fixture;

    {
        auto context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
        auto system = make_system(fixture, fixture.charge);
        auto forcefield = make_forcefield(fixture);
        auto direct = make_direct_model(fixture);
        auto reciprocal = make_reciprocal_model(fixture);
        auto simulation = make_simulation(
            system.get(), forcefield.get(), direct.get(), reciprocal.get());
        auto peer = make_simulation(
            system.get(), forcefield.get(), direct.get(), reciprocal.get());

        const RustReciprocalProviderForceScratchSnapshot initial =
            rust_reciprocal_provider_force_scratch_snapshot(simulation.get());
        require_rust_reciprocal_provider_force_scratch_sizes(
            initial,
            0U,
            "new C++-lane PME Rust reciprocal-provider force scratch was not empty");
        require(
            initial.capacities == std::array<std::size_t, 3>{0U, 0U, 0U},
            "new C++-lane PME Rust reciprocal-provider force scratch retained capacity");

        for (const std::uint64_t step_count : {
                 UINT64_C(0),
                 UINT64_C(1),
                 UINT64_C(2),
             }) {
            const bg_dynamics_report_v1 report =
                integrate(context.get(), simulation.get(), step_count);
            const bg_dynamics_report_v1 peer_report =
                integrate(context.get(), peer.get(), step_count);
            require(
                std::memcmp(&report, &peer_report, sizeof(report)) == 0,
                "unused Rust reciprocal-provider scratch changed C++-lane report bits");
            require(
                checkpoint(simulation.get()) == checkpoint(peer.get()),
                "unused Rust reciprocal-provider scratch changed C++-lane checkpoint bits");
            const RustReciprocalProviderForceScratchSnapshot current =
                rust_reciprocal_provider_force_scratch_snapshot(
                    simulation.get());
            require_same_rust_reciprocal_provider_force_scratch_storage(
                current,
                initial,
                "C++-lane integration changed unused Rust reciprocal-provider scratch storage");
            require_rust_reciprocal_provider_force_scratch_sizes(
                current,
                0U,
                "C++-lane integration populated Rust reciprocal-provider force scratch");
        }
    }

    {
        auto context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
        auto system = make_system(fixture, fixture.charge);
        auto forcefield = make_forcefield(fixture);
        auto direct = make_direct_model(fixture);
        auto reciprocal = make_reciprocal_model(fixture);
        auto simulation = make_simulation(
            system.get(), forcefield.get(), direct.get(), reciprocal.get());
        betelgeuze::native::tests::
            reserve_particle_mesh_ewald_composite_rust_reciprocal_provider_force_scratch(
                simulation.get(), kReservedCapacity);
        const RustReciprocalProviderForceScratchSnapshot reserved =
            rust_reciprocal_provider_force_scratch_snapshot(simulation.get());
        require_rust_reciprocal_provider_force_scratch_sizes(
            reserved,
            0U,
            "reserved C++-lane PME Rust reciprocal-provider scratch was not empty");
        for (std::size_t axis = 0U; axis < reserved.addresses.size(); ++axis) {
            require(
                reserved.addresses[axis] != nullptr &&
                    reserved.capacities[axis] >= kReservedCapacity,
                "PME Rust reciprocal-provider force scratch reserve failed");
        }

        for (const std::uint64_t step_count : {
                 UINT64_C(0),
                 UINT64_C(1),
                 UINT64_C(2),
             }) {
            integrate(context.get(), simulation.get(), step_count);
            const RustReciprocalProviderForceScratchSnapshot current =
                rust_reciprocal_provider_force_scratch_snapshot(
                    simulation.get());
            require_same_rust_reciprocal_provider_force_scratch_storage(
                current,
                reserved,
                "C++-lane integration replaced reserved Rust reciprocal-provider scratch storage");
            require_rust_reciprocal_provider_force_scratch_sizes(
                current,
                0U,
                "C++-lane integration populated reserved Rust reciprocal-provider scratch");
        }
    }

    {
        auto rust_context = make_context(BG_BACKEND_RUST_CPU);
        auto cpp_context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
        auto system = make_system(fixture, fixture.charge);
        auto forcefield = make_forcefield(fixture);
        auto direct = make_direct_model(fixture);
        auto reciprocal = make_reciprocal_model(fixture);
        auto simulation = make_simulation(
            system.get(), forcefield.get(), direct.get(), reciprocal.get());
        auto peer = make_simulation(
            system.get(), forcefield.get(), direct.get(), reciprocal.get());
        betelgeuze::native::tests::
            reserve_particle_mesh_ewald_composite_rust_reciprocal_provider_force_scratch(
                simulation.get(), kReservedCapacity);

        integrate(rust_context.get(), simulation.get(), UINT64_C(1));
        const RustReciprocalProviderForceScratchSnapshot stale =
            rust_reciprocal_provider_force_scratch_snapshot(simulation.get());
        const ForceBits stale_bits =
            rust_reciprocal_provider_force_scratch_bits(stale);
        const auto rust_checkpoint = checkpoint(simulation.get());
        require_status(
            bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_load(
                peer.get(), rust_checkpoint.data(), rust_checkpoint.size()),
            BG_STATUS_OK,
            "C++-lane stale-scratch peer checkpoint load failed");
        const RustReciprocalProviderForceScratchSnapshot peer_empty =
            rust_reciprocal_provider_force_scratch_snapshot(peer.get());
        require_rust_reciprocal_provider_force_scratch_sizes(
            peer_empty,
            0U,
            "checkpoint load populated an empty Rust reciprocal-provider scratch");

        const bg_dynamics_report_v1 report =
            integrate(cpp_context.get(), simulation.get(), UINT64_C(1));
        const bg_dynamics_report_v1 peer_report =
            integrate(cpp_context.get(), peer.get(), UINT64_C(1));
        require(
            std::memcmp(&report, &peer_report, sizeof(report)) == 0 &&
                checkpoint(simulation.get()) == checkpoint(peer.get()),
            "stale Rust reciprocal-provider scratch changed C++-lane integration bits");
        const RustReciprocalProviderForceScratchSnapshot after_cpp =
            rust_reciprocal_provider_force_scratch_snapshot(simulation.get());
        require_same_rust_reciprocal_provider_force_scratch_storage(
            after_cpp,
            stale,
            "C++-lane integration replaced stale Rust reciprocal-provider scratch storage");
        require(
            rust_reciprocal_provider_force_scratch_bits(after_cpp) ==
                stale_bits,
            "C++-lane integration rewrote stale Rust reciprocal-provider force bits");
        const RustReciprocalProviderForceScratchSnapshot peer_after_cpp =
            rust_reciprocal_provider_force_scratch_snapshot(peer.get());
        require_same_rust_reciprocal_provider_force_scratch_storage(
            peer_after_cpp,
            peer_empty,
            "C++-lane integration changed empty Rust reciprocal-provider scratch storage");
        require_rust_reciprocal_provider_force_scratch_sizes(
            peer_after_cpp,
            0U,
            "C++-lane integration populated empty Rust reciprocal-provider scratch");
        require(
            stale_bits != reciprocal_parent_force_scratch_bits(
                              reciprocal_parent_force_scratch_snapshot(
                                  simulation.get())),
            "C++-lane integration did not leave Rust reciprocal-provider forces stale");
    }

    auto context = make_context(BG_BACKEND_RUST_CPU);
    auto cpp_context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    auto system = make_system(fixture, fixture.charge);
    auto forcefield = make_forcefield(fixture);
    auto direct = make_direct_model(fixture);
    auto reciprocal = make_reciprocal_model(fixture);
    auto simulation = make_simulation(
        system.get(), forcefield.get(), direct.get(), reciprocal.get());
    auto peer = make_simulation(
        system.get(), forcefield.get(), direct.get(), reciprocal.get());

    const RustReciprocalProviderForceScratchSnapshot initial =
        rust_reciprocal_provider_force_scratch_snapshot(simulation.get());
    require_rust_reciprocal_provider_force_scratch_sizes(
        initial,
        0U,
        "new Rust-lane PME reciprocal-provider force scratch was not empty");
    require(
        initial.capacities == std::array<std::size_t, 3>{0U, 0U, 0U},
        "new Rust-lane PME reciprocal-provider force scratch retained capacity");

    const ReciprocalParentForceScratchSnapshot initial_parent =
        reciprocal_parent_force_scratch_snapshot(simulation.get());
    const ReciprocalParentForceScratchSnapshot initial_peer_parent =
        reciprocal_parent_force_scratch_snapshot(peer.get());
    require(
        initial_parent.size == 0U && initial_parent.capacity == 0U &&
            initial_peer_parent.size == 0U &&
            initial_peer_parent.capacity == 0U,
        "new Rust-lane PME reciprocal-parent force scratch was not empty");
    betelgeuze::native::tests::
        reserve_particle_mesh_ewald_composite_reciprocal_parent_force_scratch(
            simulation.get(), kReservedCapacity);
    const ReciprocalParentForceScratchSnapshot reserved_parent =
        reciprocal_parent_force_scratch_snapshot(simulation.get());
    require(
        reserved_parent.address != nullptr && reserved_parent.size == 0U &&
            reserved_parent.capacity >= kReservedCapacity,
        "Rust-lane PME reciprocal-parent force scratch reserve failed");

    integrate(cpp_context.get(), simulation.get(), UINT64_C(1));
    const ReciprocalParentForceScratchSnapshot stale_parent =
        reciprocal_parent_force_scratch_snapshot(simulation.get());
    require_same_reciprocal_parent_force_scratch_storage(
        stale_parent,
        reserved_parent,
        "C++ seed replaced the pre-reserved PME reciprocal-parent scratch storage");
    require(
        stale_parent.size == kAtomCount,
        "C++ seed retained the wrong PME reciprocal-parent scratch size");
    const ForceBits stale_parent_bits =
        reciprocal_parent_force_scratch_bits(stale_parent);
    const RustReciprocalProviderForceScratchSnapshot after_cpp_seed =
        rust_reciprocal_provider_force_scratch_snapshot(simulation.get());
    require_same_rust_reciprocal_provider_force_scratch_storage(
        after_cpp_seed,
        initial,
        "C++ seed changed empty Rust reciprocal-provider scratch storage");
    require_rust_reciprocal_provider_force_scratch_sizes(
        after_cpp_seed,
        0U,
        "C++ seed populated Rust reciprocal-provider force scratch");

    const auto rust_start = checkpoint(simulation.get());
    require_status(
        bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_load(
            peer.get(), rust_start.data(), rust_start.size()),
        BG_STATUS_OK,
        "Rust-lane peer checkpoint load after C++ reciprocal seed failed");
    const ReciprocalParentForceScratchSnapshot peer_parent_after_load =
        reciprocal_parent_force_scratch_snapshot(peer.get());
    require_same_reciprocal_parent_force_scratch_storage(
        peer_parent_after_load,
        initial_peer_parent,
        "checkpoint load changed empty peer reciprocal-parent scratch storage");
    require(
        peer_parent_after_load.size == 0U,
        "checkpoint load populated empty peer reciprocal-parent force scratch");

    betelgeuze::native::tests::
        reserve_particle_mesh_ewald_composite_rust_reciprocal_provider_force_scratch(
            simulation.get(), kReservedCapacity);
    const RustReciprocalProviderForceScratchSnapshot reserved =
        rust_reciprocal_provider_force_scratch_snapshot(simulation.get());
    require_rust_reciprocal_provider_force_scratch_sizes(
        reserved,
        0U,
        "PME Rust reciprocal-provider force scratch reserve changed logical size");
    for (std::size_t axis = 0U; axis < reserved.addresses.size(); ++axis) {
        require(
            reserved.addresses[axis] != nullptr &&
                reserved.capacities[axis] >= kReservedCapacity,
            "PME Rust reciprocal-provider force scratch reserve did not retain storage");
        for (std::size_t other = axis + 1U;
             other < reserved.addresses.size(); ++other) {
            require(
                reserved.addresses[axis] != reserved.addresses[other],
                "PME Rust reciprocal-provider force scratch channels aliased");
        }
    }

    const auto before_zero = checkpoint(simulation.get());
    const bg_dynamics_report_v1 zero_report =
        integrate(context.get(), simulation.get(), UINT64_C(0));
    const bg_dynamics_report_v1 peer_zero_report =
        integrate(context.get(), peer.get(), UINT64_C(0));
    require(
        std::memcmp(&zero_report, &peer_zero_report, sizeof(zero_report)) == 0,
        "reserved Rust reciprocal-provider scratch changed zero-step report bits");
    require(
        checkpoint(simulation.get()) == before_zero,
        "zero-step integration changed checkpoint state");
    const RustReciprocalProviderForceScratchSnapshot after_zero =
        rust_reciprocal_provider_force_scratch_snapshot(simulation.get());
    require_same_rust_reciprocal_provider_force_scratch_storage(
        after_zero,
        reserved,
        "zero-step integration changed Rust reciprocal-provider scratch storage");
    require_rust_reciprocal_provider_force_scratch_sizes(
        after_zero,
        0U,
        "zero-step integration populated Rust reciprocal-provider force scratch");
    const ReciprocalParentForceScratchSnapshot parent_after_zero =
        reciprocal_parent_force_scratch_snapshot(simulation.get());
    require_same_reciprocal_parent_force_scratch_storage(
        parent_after_zero,
        stale_parent,
        "Rust zero-step integration replaced stale reciprocal-parent storage");
    require(
        parent_after_zero.size == kAtomCount &&
            reciprocal_parent_force_scratch_bits(parent_after_zero) ==
                stale_parent_bits,
        "Rust zero-step integration changed stale reciprocal-parent force bits");
    const ReciprocalParentForceScratchSnapshot peer_parent_after_zero =
        reciprocal_parent_force_scratch_snapshot(peer.get());
    require_same_reciprocal_parent_force_scratch_storage(
        peer_parent_after_zero,
        initial_peer_parent,
        "Rust zero-step integration changed empty peer reciprocal-parent storage");
    require(
        peer_parent_after_zero.size == 0U,
        "Rust zero-step integration populated empty peer reciprocal-parent scratch");

    const auto stateless_bits_for_owner = [&]() {
        Fixture current = fixture;
        const bg_particle_soa_view view = simulation_view(simulation.get());
        std::copy_n(view.position_x_angstrom, kAtomCount, current.x.begin());
        std::copy_n(view.position_y_angstrom, kAtomCount, current.y.begin());
        std::copy_n(view.position_z_angstrom, kAtomCount, current.z.begin());
        const auto current_system = make_system(current, current.charge);
        return evaluate_stateless_reciprocal_force_bits(
            context.get(), current_system.get(), reciprocal.get());
    };

    bg_dynamics_report_v1 last_report{};
    init_report(&last_report);
    for (const std::uint64_t step_count : {
             UINT64_C(1),
             UINT64_C(2),
         }) {
        const bg_dynamics_report_v1 report =
            integrate(context.get(), simulation.get(), step_count);
        const bg_dynamics_report_v1 peer_report =
            integrate(context.get(), peer.get(), step_count);
        require(
            std::memcmp(&report, &peer_report, sizeof(report)) == 0,
            "reused Rust reciprocal-provider scratch changed integration report bits");
        require(
            checkpoint(simulation.get()) == checkpoint(peer.get()),
            "reused Rust reciprocal-provider scratch changed checkpoint bits");
        last_report = report;
        const RustReciprocalProviderForceScratchSnapshot current =
            rust_reciprocal_provider_force_scratch_snapshot(simulation.get());
        require_same_rust_reciprocal_provider_force_scratch_storage(
            current,
            reserved,
            "integration replaced Rust reciprocal-provider force scratch storage");
        require_rust_reciprocal_provider_force_scratch_sizes(
            current,
            kAtomCount,
            "integration retained the wrong Rust reciprocal-provider scratch size");
        const ForceBits current_bits =
            rust_reciprocal_provider_force_scratch_bits(current);
        require(
            current_bits == rust_reciprocal_provider_force_scratch_bits(
                                rust_reciprocal_provider_force_scratch_snapshot(
                                    peer.get())),
            "Rust reciprocal-provider scratch differed from same-lane peer bits");
        require(
            current_bits == stateless_bits_for_owner(),
            "Rust reciprocal-provider scratch differed from stateless reciprocal force bits");
        const ReciprocalParentForceScratchSnapshot current_parent =
            reciprocal_parent_force_scratch_snapshot(simulation.get());
        require_same_reciprocal_parent_force_scratch_storage(
            current_parent,
            stale_parent,
            "Rust integration replaced stale reciprocal-parent scratch storage");
        require(
            current_parent.size == kAtomCount &&
                reciprocal_parent_force_scratch_bits(current_parent) ==
                    stale_parent_bits,
            "Rust integration rewrote stale reciprocal-parent force bits");
        const ReciprocalParentForceScratchSnapshot current_peer_parent =
            reciprocal_parent_force_scratch_snapshot(peer.get());
        require_same_reciprocal_parent_force_scratch_storage(
            current_peer_parent,
            initial_peer_parent,
            "Rust integration changed empty peer reciprocal-parent scratch storage");
        require(
            current_peer_parent.size == 0U,
            "Rust integration populated empty peer reciprocal-parent scratch");
    }

    const auto checkpoint_a = checkpoint(simulation.get());
    const ForceBits forces_a =
        rust_reciprocal_provider_force_scratch_bits(
            rust_reciprocal_provider_force_scratch_snapshot(simulation.get()));
    integrate(context.get(), simulation.get(), UINT64_C(1));
    const RustReciprocalProviderForceScratchSnapshot state_b =
        rust_reciprocal_provider_force_scratch_snapshot(simulation.get());
    require_same_rust_reciprocal_provider_force_scratch_storage(
        state_b,
        reserved,
        "state-B integration replaced Rust reciprocal-provider scratch storage");
    const ForceBits forces_b =
        rust_reciprocal_provider_force_scratch_bits(state_b);
    require(
        forces_b != forces_a && forces_b == stateless_bits_for_owner(),
        "state-B integration did not refresh Rust reciprocal-provider scratch");
    const ReciprocalParentForceScratchSnapshot parent_at_state_b =
        reciprocal_parent_force_scratch_snapshot(simulation.get());
    require_same_reciprocal_parent_force_scratch_storage(
        parent_at_state_b,
        stale_parent,
        "state-B Rust integration replaced stale reciprocal-parent storage");
    require(
        parent_at_state_b.size == kAtomCount &&
            reciprocal_parent_force_scratch_bits(parent_at_state_b) ==
                stale_parent_bits,
        "state-B Rust integration rewrote stale reciprocal-parent forces");

    require_status(
        bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_load(
            simulation.get(), checkpoint_a.data(), checkpoint_a.size()),
        BG_STATUS_OK,
        "Rust reciprocal-provider scratch checkpoint reload failed");
    const RustReciprocalProviderForceScratchSnapshot after_load =
        rust_reciprocal_provider_force_scratch_snapshot(simulation.get());
    require_same_rust_reciprocal_provider_force_scratch_storage(
        after_load,
        state_b,
        "checkpoint reload replaced Rust reciprocal-provider scratch storage");
    require(
        rust_reciprocal_provider_force_scratch_bits(after_load) == forces_b,
        "checkpoint reload unexpectedly rewrote stale Rust reciprocal-provider scratch");
    const ReciprocalParentForceScratchSnapshot parent_after_restart_load =
        reciprocal_parent_force_scratch_snapshot(simulation.get());
    require_same_reciprocal_parent_force_scratch_storage(
        parent_after_restart_load,
        stale_parent,
        "checkpoint reload replaced stale reciprocal-parent scratch storage");
    require(
        parent_after_restart_load.size == kAtomCount &&
            reciprocal_parent_force_scratch_bits(parent_after_restart_load) ==
                stale_parent_bits,
        "checkpoint reload rewrote stale reciprocal-parent force bits");

    const bg_dynamics_report_v1 restart_zero =
        integrate(context.get(), simulation.get(), UINT64_C(0));
    const bg_dynamics_report_v1 peer_restart_zero =
        integrate(context.get(), peer.get(), UINT64_C(0));
    require(
        std::memcmp(
            &restart_zero, &peer_restart_zero, sizeof(restart_zero)) == 0,
        "stale Rust reciprocal-provider scratch changed zero-step report bits");
    require(
        checkpoint(simulation.get()) == checkpoint_a &&
            checkpoint(peer.get()) == checkpoint_a,
        "stale Rust reciprocal-provider scratch changed zero-step checkpoint bits");
    const RustReciprocalProviderForceScratchSnapshot after_restart_zero =
        rust_reciprocal_provider_force_scratch_snapshot(simulation.get());
    require_same_rust_reciprocal_provider_force_scratch_storage(
        after_restart_zero,
        state_b,
        "zero-step restart replaced stale Rust reciprocal-provider scratch storage");
    require(
        rust_reciprocal_provider_force_scratch_bits(after_restart_zero) ==
            forces_b,
        "zero-step restart changed stale Rust reciprocal-provider scratch bits");
    const ReciprocalParentForceScratchSnapshot parent_after_restart_zero =
        reciprocal_parent_force_scratch_snapshot(simulation.get());
    require_same_reciprocal_parent_force_scratch_storage(
        parent_after_restart_zero,
        stale_parent,
        "zero-step restart replaced stale reciprocal-parent scratch storage");
    require(
        parent_after_restart_zero.size == kAtomCount &&
            reciprocal_parent_force_scratch_bits(parent_after_restart_zero) ==
                stale_parent_bits,
        "zero-step restart rewrote stale reciprocal-parent force bits");
    const ReciprocalParentForceScratchSnapshot peer_parent_after_restart_zero =
        reciprocal_parent_force_scratch_snapshot(peer.get());
    require_same_reciprocal_parent_force_scratch_storage(
        peer_parent_after_restart_zero,
        initial_peer_parent,
        "zero-step restart changed empty peer reciprocal-parent storage");
    require(
        peer_parent_after_restart_zero.size == 0U,
        "zero-step restart populated empty peer reciprocal-parent scratch");

    const bg_dynamics_report_v1 restarted =
        integrate(context.get(), simulation.get(), UINT64_C(1));
    const bg_dynamics_report_v1 peer_restarted =
        integrate(context.get(), peer.get(), UINT64_C(1));
    require(
        std::memcmp(&restarted, &peer_restarted, sizeof(restarted)) == 0,
        "forceful restart with stale Rust reciprocal-provider scratch changed report bits");
    require(
        checkpoint(simulation.get()) == checkpoint(peer.get()),
        "forceful restart with stale Rust reciprocal-provider scratch changed state bits");
    last_report = restarted;
    const RustReciprocalProviderForceScratchSnapshot after_resync =
        rust_reciprocal_provider_force_scratch_snapshot(simulation.get());
    require_same_rust_reciprocal_provider_force_scratch_storage(
        after_resync,
        reserved,
        "forceful restart replaced Rust reciprocal-provider scratch storage");
    const ForceBits resynced_bits =
        rust_reciprocal_provider_force_scratch_bits(after_resync);
    require(
        resynced_bits == rust_reciprocal_provider_force_scratch_bits(
                             rust_reciprocal_provider_force_scratch_snapshot(
                                 peer.get())) &&
            resynced_bits == stateless_bits_for_owner(),
        "forceful restart did not resynchronize Rust reciprocal-provider scratch");
    const ReciprocalParentForceScratchSnapshot parent_after_resync =
        reciprocal_parent_force_scratch_snapshot(simulation.get());
    require_same_reciprocal_parent_force_scratch_storage(
        parent_after_resync,
        stale_parent,
        "forceful Rust restart replaced stale reciprocal-parent scratch storage");
    require(
        parent_after_resync.size == kAtomCount &&
            reciprocal_parent_force_scratch_bits(parent_after_resync) ==
                stale_parent_bits,
        "forceful Rust restart rewrote stale reciprocal-parent force bits");
    const ReciprocalParentForceScratchSnapshot peer_parent_after_resync =
        reciprocal_parent_force_scratch_snapshot(peer.get());
    require_same_reciprocal_parent_force_scratch_storage(
        peer_parent_after_resync,
        initial_peer_parent,
        "forceful Rust restart changed empty peer reciprocal-parent storage");
    require(
        peer_parent_after_resync.size == 0U,
        "forceful Rust restart populated empty peer reciprocal-parent scratch");

    const auto before_alias = checkpoint(simulation.get());
    const bg_dynamics_report_v1 report_before_alias = last_report;
    const bg_particle_soa_view particles_before_alias =
        simulation_view(simulation.get());
    const PositionBits positions_before_alias =
        view_position_bits(particles_before_alias);
    const std::array<const double *, 8> particle_addresses_before_alias{{
        particles_before_alias.position_x_angstrom,
        particles_before_alias.position_y_angstrom,
        particles_before_alias.position_z_angstrom,
        particles_before_alias.velocity_x_angstrom_per_femtosecond,
        particles_before_alias.velocity_y_angstrom_per_femtosecond,
        particles_before_alias.velocity_z_angstrom_per_femtosecond,
        particles_before_alias.mass_dalton,
        particles_before_alias.charge_elementary,
    }};
    std::uint64_t absolute_step_before_alias = 0U;
    require_status(
        bg_particle_mesh_ewald_composite_simulation_v1_get_absolute_step(
            simulation.get(), &absolute_step_before_alias),
        BG_STATUS_OK,
        "pre-alias absolute-step query failed");

    for (std::size_t axis = 0U; axis < after_resync.addresses.size(); ++axis) {
        auto *const aliased_step = reinterpret_cast<std::uint64_t *>(
            const_cast<double *>(after_resync.addresses[axis] + 1U));
        require_status(
            bg_particle_mesh_ewald_composite_simulation_v1_get_absolute_step(
                simulation.get(), aliased_step),
            BG_STATUS_INVALID_ARGUMENT,
            "absolute-step output aliased Rust reciprocal-provider force scratch");
        require(
            std::strcmp(
                bg_last_error_message(),
                "absolute_step output must not overlap particle-mesh composite dynamics owner storage") ==
                0,
            "Rust reciprocal-provider absolute-step alias returned the wrong error");
        const RustReciprocalProviderForceScratchSnapshot after_step_alias =
            rust_reciprocal_provider_force_scratch_snapshot(simulation.get());
        require_same_rust_reciprocal_provider_force_scratch_storage(
            after_step_alias,
            after_resync,
            "rejected absolute-step alias changed Rust reciprocal-provider scratch storage");
        require(
            rust_reciprocal_provider_force_scratch_bits(after_step_alias) ==
                    resynced_bits &&
                reciprocal_parent_force_scratch_bits(
                    reciprocal_parent_force_scratch_snapshot(
                        simulation.get())) == stale_parent_bits &&
                checkpoint(simulation.get()) == before_alias &&
                std::memcmp(
                    &last_report,
                    &report_before_alias,
                    sizeof(last_report)) == 0,
            "rejected absolute-step alias changed scratch, report, or checkpoint bits");
        const bg_particle_soa_view particles_after_step_alias =
            simulation_view(simulation.get());
        const std::array<const double *, 8> particle_addresses_after_step_alias{{
            particles_after_step_alias.position_x_angstrom,
            particles_after_step_alias.position_y_angstrom,
            particles_after_step_alias.position_z_angstrom,
            particles_after_step_alias.velocity_x_angstrom_per_femtosecond,
            particles_after_step_alias.velocity_y_angstrom_per_femtosecond,
            particles_after_step_alias.velocity_z_angstrom_per_femtosecond,
            particles_after_step_alias.mass_dalton,
            particles_after_step_alias.charge_elementary,
        }};
        require(
            particle_addresses_after_step_alias ==
                    particle_addresses_before_alias &&
                view_position_bits(particles_after_step_alias) ==
                    positions_before_alias,
            "rejected absolute-step alias changed authoritative particle state");
        std::uint64_t absolute_step_after_alias = 0U;
        require_status(
            bg_particle_mesh_ewald_composite_simulation_v1_get_absolute_step(
                simulation.get(), &absolute_step_after_alias),
            BG_STATUS_OK,
            "post-alias absolute-step query failed");
        require(
            absolute_step_after_alias == absolute_step_before_alias,
            "rejected absolute-step alias changed authoritative step state");
    }

    auto *const aliased_view = reinterpret_cast<bg_particle_soa_view *>(
        const_cast<double *>(after_resync.addresses[2] + 1U));
    require_status(
        bg_particle_mesh_ewald_composite_simulation_v1_get_particles(
            simulation.get(), aliased_view),
        BG_STATUS_INVALID_ARGUMENT,
        "particle-view output aliased Rust reciprocal-provider z-force scratch");
    require(
        std::strcmp(
            bg_last_error_message(),
            "particle view output must not overlap particle-mesh composite dynamics owner storage") ==
            0,
        "Rust reciprocal-provider particle-view alias returned the wrong error");
    const RustReciprocalProviderForceScratchSnapshot after_view_alias =
        rust_reciprocal_provider_force_scratch_snapshot(simulation.get());
    require_same_rust_reciprocal_provider_force_scratch_storage(
        after_view_alias,
        after_resync,
        "rejected particle-view alias changed Rust reciprocal-provider scratch storage");
    require(
        rust_reciprocal_provider_force_scratch_bits(after_view_alias) ==
                resynced_bits &&
            reciprocal_parent_force_scratch_bits(
                reciprocal_parent_force_scratch_snapshot(simulation.get())) ==
                stale_parent_bits &&
            checkpoint(simulation.get()) == before_alias &&
            std::memcmp(
                &last_report,
                &report_before_alias,
                sizeof(last_report)) == 0,
        "rejected particle-view alias changed scratch, report, or checkpoint bits");
    const bg_particle_soa_view particles_after_view_alias =
        simulation_view(simulation.get());
    const std::array<const double *, 8> particle_addresses_after_view_alias{{
        particles_after_view_alias.position_x_angstrom,
        particles_after_view_alias.position_y_angstrom,
        particles_after_view_alias.position_z_angstrom,
        particles_after_view_alias.velocity_x_angstrom_per_femtosecond,
        particles_after_view_alias.velocity_y_angstrom_per_femtosecond,
        particles_after_view_alias.velocity_z_angstrom_per_femtosecond,
        particles_after_view_alias.mass_dalton,
        particles_after_view_alias.charge_elementary,
    }};
    require(
        particle_addresses_after_view_alias == particle_addresses_before_alias &&
            view_position_bits(particles_after_view_alias) ==
                positions_before_alias,
        "rejected particle-view alias changed authoritative particle state");
    std::uint64_t absolute_step_after_view_alias = 0U;
    require_status(
        bg_particle_mesh_ewald_composite_simulation_v1_get_absolute_step(
            simulation.get(), &absolute_step_after_view_alias),
        BG_STATUS_OK,
        "post-view-alias absolute-step query failed");
    require(
        absolute_step_after_view_alias == absolute_step_before_alias,
        "rejected particle-view alias changed authoritative step state");
}

void verify_short_system_scratch_reuse() {
    const Fixture fixture;
    for (const bg_backend lane :
         {BG_BACKEND_CPP_CPU_REFERENCE, BG_BACKEND_RUST_CPU}) {
        auto context = make_context(lane);
        auto system = make_system(fixture, fixture.charge);
        auto forcefield = make_forcefield(fixture);
        auto direct = make_direct_model(fixture);
        auto reciprocal = make_reciprocal_model(fixture);
        auto simulation = make_simulation(
            system.get(), forcefield.get(), direct.get(), reciprocal.get());

        const ShortSystemScratchSnapshot initial =
            short_system_scratch_snapshot(simulation.get());
        require_short_system_scratch_layout(
            initial, "new PME short-system scratch layout was invalid");
        require_short_system_scratch_positions_current(
            initial, simulation_view(simulation.get()),
            "new PME short-system scratch positions differed from owner state");

        const auto before_zero = checkpoint(simulation.get());
        integrate(context.get(), simulation.get(), UINT64_C(0));
        require(
            checkpoint(simulation.get()) == before_zero,
            "zero-step PME scratch evaluation changed checkpoint state");
        const ShortSystemScratchSnapshot after_zero =
            short_system_scratch_snapshot(simulation.get());
        require_same_short_system_scratch_storage(
            after_zero, initial,
            "zero-step evaluation replaced PME short-system scratch storage");
        require_short_system_scratch_layout(
            after_zero,
            "zero-step evaluation changed PME short-system scratch layout");
        require_short_system_scratch_positions_current(
            after_zero, simulation_view(simulation.get()),
            "zero-step PME short-system scratch positions were stale");

        for (const std::uint64_t step_count :
             {UINT64_C(1), UINT64_C(2)}) {
            integrate(context.get(), simulation.get(), step_count);
            const ShortSystemScratchSnapshot current =
                short_system_scratch_snapshot(simulation.get());
            require_same_short_system_scratch_storage(
                current, initial,
                "integration replaced PME short-system scratch storage");
            require_short_system_scratch_layout(
                current,
                "integration changed PME short-system scratch layout");
            require_short_system_scratch_positions_current(
                current, simulation_view(simulation.get()),
                "integration left PME short-system scratch positions stale");
        }

        const auto saved = checkpoint(simulation.get());
        auto peer = make_simulation(
            system.get(), forcefield.get(), direct.get(), reciprocal.get());
        require_status(
            bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_load(
                peer.get(), saved.data(), saved.size()),
            BG_STATUS_OK,
            "PME short-system scratch peer checkpoint load failed");

        integrate(context.get(), simulation.get(), UINT64_C(1));
        const ShortSystemScratchSnapshot before_load =
            short_system_scratch_snapshot(simulation.get());
        const PositionBits state_b_scratch =
            short_system_scratch_position_bits(before_load);
        require_status(
            bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_load(
                simulation.get(), saved.data(), saved.size()),
            BG_STATUS_OK,
            "PME short-system scratch checkpoint reload failed");
        const ShortSystemScratchSnapshot after_load =
            short_system_scratch_snapshot(simulation.get());
        require_same_short_system_scratch_storage(
            after_load, before_load,
            "checkpoint reload replaced PME short-system scratch storage");
        require_short_system_scratch_layout(
            after_load,
            "checkpoint reload changed PME short-system scratch layout");
        require(
            short_system_scratch_position_bits(after_load) ==
                state_b_scratch,
            "checkpoint reload unexpectedly rewrote private PME scratch state");
        require(
            short_system_scratch_position_bits(after_load) !=
                view_position_bits(simulation_view(simulation.get())),
            "checkpoint reload did not create stale PME short-system scratch");

        const bg_dynamics_report_v1 restart_report =
            integrate(context.get(), simulation.get(), UINT64_C(0));
        const bg_dynamics_report_v1 peer_report =
            integrate(context.get(), peer.get(), UINT64_C(0));
        require(
            std::memcmp(
                &restart_report, &peer_report, sizeof(restart_report)) == 0,
            "post-checkpoint PME scratch resync changed report bits");
        require(
            checkpoint(simulation.get()) == saved &&
                checkpoint(peer.get()) == saved,
            "post-checkpoint PME scratch resync changed checkpoint bits");
        const ShortSystemScratchSnapshot after_restart_evaluation =
            short_system_scratch_snapshot(simulation.get());
        require_same_short_system_scratch_storage(
            after_restart_evaluation, initial,
            "post-checkpoint evaluation replaced PME short-system scratch storage");
        require_short_system_scratch_layout(
            after_restart_evaluation,
            "post-checkpoint evaluation changed PME short-system scratch layout");
        require_short_system_scratch_positions_current(
            after_restart_evaluation, simulation_view(simulation.get()),
            "post-checkpoint PME short-system scratch positions were stale");
    }
}

void expect_short_system_scratch_drift_failure(
    const bg_context *context,
    bg_particle_mesh_ewald_composite_simulation_v1 *simulation,
    const char *message) {
    const auto before = checkpoint(simulation);
    const bg_particle_soa_view view_before = simulation_view(simulation);
    const std::array<const double *, 8> addresses_before{{
        view_before.position_x_angstrom,
        view_before.position_y_angstrom,
        view_before.position_z_angstrom,
        view_before.velocity_x_angstrom_per_femtosecond,
        view_before.velocity_y_angstrom_per_femtosecond,
        view_before.velocity_z_angstrom_per_femtosecond,
        view_before.mass_dalton,
        view_before.charge_elementary,
    }};
    bg_dynamics_report_v1 report{};
    init_report(&report);
    report.steps_completed = UINT64_C(91);
    report.absolute_step = UINT64_C(92);
    report.total_kcal_per_mol = 93.0;
    const bg_dynamics_report_v1 report_before = report;
    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    error.code = BG_DIRECT_EWALD_ERROR_NONFINITE_RESULT;
    std::memcpy(error.detail, "stale", sizeof("stale"));
    require_status(
        bg_context_integrate_particle_mesh_ewald_composite_v1(
            context, simulation, UINT64_C(1), &report, &error),
        BG_STATUS_INTERNAL_ERROR,
        message);
    require(
        std::memcmp(&report, &report_before, sizeof(report)) == 0,
        "PME short-system scratch drift changed report output");
    require(
        error.code == BG_DIRECT_EWALD_ERROR_NONE &&
            error.detail[0] == '\0',
        "PME short-system scratch drift retained a typed Ewald error");
    require(
        checkpoint(simulation) == before,
        "PME short-system scratch drift changed checkpoint state");
    const bg_particle_soa_view view_after = simulation_view(simulation);
    const std::array<const double *, 8> addresses_after{{
        view_after.position_x_angstrom,
        view_after.position_y_angstrom,
        view_after.position_z_angstrom,
        view_after.velocity_x_angstrom_per_femtosecond,
        view_after.velocity_y_angstrom_per_femtosecond,
        view_after.velocity_z_angstrom_per_femtosecond,
        view_after.mass_dalton,
        view_after.charge_elementary,
    }};
    require(
        addresses_after == addresses_before,
        "PME short-system scratch drift changed particle storage identity");
}

void verify_short_system_scratch_drift_fails_closed() {
    const Fixture fixture;
    auto system = make_system(fixture, fixture.charge);
    auto forcefield = make_forcefield(fixture);
    auto direct = make_direct_model(fixture);
    auto reciprocal = make_reciprocal_model(fixture);

    for (const bg_backend lane :
         {BG_BACKEND_CPP_CPU_REFERENCE, BG_BACKEND_RUST_CPU}) {
        auto context = make_context(lane);
        auto unit_drift = make_simulation(
            system.get(), forcefield.get(), direct.get(), reciprocal.get());
        betelgeuze::native::tests::
            set_particle_mesh_ewald_composite_short_system_scratch_unit_for_test(
                unit_drift.get(), static_cast<bg_unit_system>(0));
        expect_short_system_scratch_drift_failure(
            context.get(), unit_drift.get(),
            "PME short-system scratch unit drift did not fail closed");

        auto shape_drift = make_simulation(
            system.get(), forcefield.get(), direct.get(), reciprocal.get());
        betelgeuze::native::tests::
            truncate_particle_mesh_ewald_composite_short_system_scratch_for_test(
                shape_drift.get());
        expect_short_system_scratch_drift_failure(
            context.get(), shape_drift.get(),
            "PME short-system scratch shape drift did not fail closed");

        auto negative_zero = make_simulation(
            system.get(), forcefield.get(), direct.get(), reciprocal.get());
        betelgeuze::native::tests::
            set_particle_mesh_ewald_composite_short_system_scratch_charge_for_test(
                negative_zero.get(), -0.0);
        expect_short_system_scratch_drift_failure(
            context.get(), negative_zero.get(),
            "PME short-system scratch negative-zero charge did not fail closed");
    }
}

void verify_late_typed_failure_rolls_back() {
    constexpr double timestep = 0.01;
    const Fixture base;
    auto forcefield = make_forcefield(base);
    Fixture direct_fixture = base;
    direct_fixture.minimum_pair_distance = 1.0;
    auto direct = make_direct_model(direct_fixture);
    auto reciprocal = make_reciprocal_model(base);

    for (const bg_backend lane :
         {BG_BACKEND_CPP_CPU_REFERENCE, BG_BACKEND_RUST_CPU}) {
        auto context = make_context(lane);
        auto initial_system = make_system(base, base.charge);
        std::array<double, 4> force_x{};
        std::array<double, 4> force_y{};
        std::array<double, 4> force_z{};
        bg_particle_mesh_ewald_composite_force_soa_v1 forces{};
        require_status(bg_particle_mesh_ewald_composite_force_soa_v1_init(
            &forces, sizeof(forces),
            BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION), BG_STATUS_OK,
            "force output init failed");
        forces.atom_capacity = base.x.size();
        forces.x_kcal_per_mol_angstrom = force_x.data();
        forces.y_kcal_per_mol_angstrom = force_y.data();
        forces.z_kcal_per_mol_angstrom = force_z.data();
        bg_particle_mesh_ewald_composite_energy_components_v1 energy{};
        require_status(bg_particle_mesh_ewald_composite_energy_components_v1_init(
            &energy, sizeof(energy),
            BG_PARTICLE_MESH_EWALD_COMPOSITE_ABI_VERSION), BG_STATUS_OK,
            "energy output init failed");
        bg_direct_ewald_error_v1 eval_error{};
        init_error(&eval_error);
        require_status(bg_context_evaluate_particle_mesh_ewald_composite_v1(
            context.get(), initial_system.get(), forcefield.get(), direct.get(),
            reciprocal.get(), &energy, &forces, &eval_error), BG_STATUS_OK,
            "initial force evaluation failed");
        StatelessEvaluation initial_evaluation{};
        initial_evaluation.force_x = force_x;
        initial_evaluation.force_y = force_y;
        initial_evaluation.force_z = force_z;
        const ForceBits initial_force_bits =
            stateless_force_bits(initial_evaluation);

        Fixture moving = base;
        const std::array<std::array<double, 4>, 3> targets{{
            std::array<double, 4>{{base.x[0], base.x[1], base.x[2],
                                   base.x[0] + 0.5}},
            std::array<double, 4>{{base.y[0], base.y[1], base.y[2], base.y[0]}},
            std::array<double, 4>{{base.z[0], base.z[1], base.z[2], base.z[0]}}}};
        const std::array<const std::array<double, 4> *, 3> positions{{
            &base.x, &base.y, &base.z}};
        const std::array<const std::array<double, 4> *, 3> force_channels{{
            &force_x, &force_y, &force_z}};
        const std::array<std::array<double, 4> *, 3> velocities{{
            &moving.velocity_x, &moving.velocity_y, &moving.velocity_z}};
        for (std::size_t atom = 0; atom < base.x.size(); ++atom) {
            const double scale = kAccelerationConversion * 0.5 * timestep /
                                 base.mass[atom];
            for (std::size_t axis = 0; axis < 3U; ++axis) {
                const double desired =
                    (targets[axis][atom] - (*positions[axis])[atom]) / timestep;
                (*velocities[axis])[atom] =
                    desired - scale * (*force_channels[axis])[atom];
            }
        }

        auto moving_system = make_system(moving, moving.charge);
        auto simulation = make_simulation(
            moving_system.get(), forcefield.get(), direct.get(),
            reciprocal.get(), nullptr, timestep);
        bg_particle_soa_view view{};
        require_status(bg_particle_soa_view_init(
            &view, sizeof(view), BG_ABI_VERSION), BG_STATUS_OK,
            "particle view init failed");
        require_status(bg_particle_mesh_ewald_composite_simulation_v1_get_particles(
            simulation.get(), &view), BG_STATUS_OK, "particle view failed");
        const auto address = view.position_x_angstrom;
        betelgeuze::native::tests::
            reserve_particle_mesh_ewald_composite_force_scratch(
                simulation.get(), 64U);
        betelgeuze::native::tests::
            reserve_particle_mesh_ewald_composite_short_parent_force_scratch(
                simulation.get(), 64U);
        const ForceScratchSnapshot reserved =
            force_scratch_snapshot(simulation.get());
        const ShortParentForceScratchSnapshot short_parent_reserved =
            short_parent_force_scratch_snapshot(simulation.get());
        require_short_parent_force_scratch_sizes(
            short_parent_reserved,
            0U,
            "late-failure PME short-parent scratch reserve changed logical size");
        require(
            short_parent_reserved.rust_cpu_forcefield_validated ==
                UINT8_C(0),
            "late-failure PME short-parent validation cache started populated");
        const ShortSystemScratchSnapshot short_system_reserved =
            short_system_scratch_snapshot(simulation.get());
        require_short_system_scratch_layout(
            short_system_reserved,
            "late-failure PME short-system scratch layout was invalid");
        require_short_system_scratch_positions_current(
            short_system_reserved, simulation_view(simulation.get()),
            "late-failure PME short-system scratch started stale");
        const auto before = checkpoint(simulation.get());
        for (std::size_t attempt = 0U; attempt < 2U; ++attempt) {
            bg_dynamics_report_v1 report{};
            init_report(&report);
            report.steps_completed = 123U;
            report.absolute_step = 456U;
            report.total_kcal_per_mol = 789.0;
            const auto report_before = report;
            bg_direct_ewald_error_v1 error{};
            init_error(&error);
            require_status(
                bg_context_integrate_particle_mesh_ewald_composite_v1(
                    context.get(), simulation.get(), 1U, &report, &error),
                BG_STATUS_NUMERICAL_ERROR,
                "late typed evaluator failure did not propagate");
            require(error.code ==
                        BG_DIRECT_EWALD_ERROR_PAIR_BELOW_MINIMUM_DISTANCE &&
                    error.detail[0] != '\0',
                    "late evaluator failure omitted typed detail");
            require(
                std::memcmp(&report, &report_before, sizeof(report)) == 0,
                "late evaluator failure mutated report");
            require(
                checkpoint(simulation.get()) == before,
                "late evaluator failure did not roll back complete state");
            require_status(
                bg_particle_mesh_ewald_composite_simulation_v1_get_particles(
                    simulation.get(), &view),
                BG_STATUS_OK, "particle view failed");
            require(
                view.position_x_angstrom == address,
                "late evaluator rollback changed particle addresses");
            const ForceScratchSnapshot after_failure =
                force_scratch_snapshot(simulation.get());
            require_same_force_scratch_storage(
                after_failure, reserved,
                "late evaluator failure replaced force scratch storage");
            require_force_scratch_sizes(
                after_failure, base.x.size(),
                "late evaluator failure retained the wrong scratch size");
            require(
                force_scratch_bits(after_failure) == initial_force_bits,
                "late direct-local failure overwrote the last successful final force bits");
            const ShortSystemScratchSnapshot short_system_after_failure =
                short_system_scratch_snapshot(simulation.get());
            require_same_short_system_scratch_storage(
                short_system_after_failure, short_system_reserved,
                "late direct-local failure replaced PME short-system scratch storage");
            require_short_system_scratch_layout(
                short_system_after_failure,
                "late direct-local failure changed PME short-system scratch layout");
            const ShortParentForceScratchSnapshot
                short_parent_after_failure =
                    short_parent_force_scratch_snapshot(simulation.get());
            require_same_short_parent_force_scratch_storage(
                short_parent_after_failure,
                short_parent_reserved,
                "late direct-local failure replaced PME short-parent force scratch storage");
            require_short_parent_force_scratch_sizes(
                short_parent_after_failure,
                kAtomCount,
                "late direct-local failure retained the wrong PME short-parent scratch size");
            require(
                short_parent_after_failure.rust_cpu_forcefield_validated ==
                    (lane == BG_BACKEND_RUST_CPU ? UINT8_C(1)
                                                 : UINT8_C(0)),
                "late direct-local failure retained the wrong PME Rust validation flag");
        }
    }
}

void verify_zero_step_and_restart() {
    const Fixture fixture;
    for (const bg_backend lane :
         {BG_BACKEND_CPP_CPU_REFERENCE, BG_BACKEND_RUST_CPU}) {
        auto context = make_context(lane);
        auto system = make_system(fixture, fixture.charge);
        auto forcefield = make_forcefield(fixture);
        auto direct = make_direct_model(fixture);
        auto reciprocal = make_reciprocal_model(fixture);
        auto zero = make_simulation(
            system.get(), forcefield.get(), direct.get(), reciprocal.get());
        const auto zero_before = checkpoint(zero.get());
        const double expected = stateless_total(
            context.get(), system.get(), forcefield.get(), direct.get(),
            reciprocal.get());
        const bg_dynamics_report_v1 zero_report =
            integrate(context.get(), zero.get(), 0U);
        require_exact(zero_report.potential_kcal_per_mol, expected,
                      "zero-step potential differed from stateless evaluator");
        require(checkpoint(zero.get()) == zero_before,
                "zero-step integration mutated simulation state");

        auto uninterrupted = make_simulation(
            system.get(), forcefield.get(), direct.get(), reciprocal.get());
        auto split = make_simulation(
            system.get(), forcefield.get(), direct.get(), reciprocal.get());
        auto restarted = make_simulation(
            system.get(), forcefield.get(), direct.get(), reciprocal.get());
        integrate(context.get(), uninterrupted.get(), 1U);
        integrate(context.get(), split.get(), 1U);
        const auto mid = checkpoint(split.get());
        require_status(
            bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_load(
                restarted.get(), mid.data(), mid.size()),
            BG_STATUS_OK, "restart checkpoint load failed");
        const bg_dynamics_report_v1 uninterrupted_report =
            integrate(context.get(), uninterrupted.get(), 1U);
        const bg_dynamics_report_v1 restarted_report =
            integrate(context.get(), restarted.get(), 1U);
        require(std::memcmp(&uninterrupted_report, &restarted_report,
                            sizeof(uninterrupted_report)) == 0,
                "same-lane restart report was not bit exact");
        require(checkpoint(uninterrupted.get()) == checkpoint(restarted.get()),
                "same-lane restart checkpoint was not bit exact");
    }
}

void verify_deep_ownership_and_constraints() {
    const Fixture fixture;
    auto context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    auto system = make_system(fixture, fixture.charge);
    auto forcefield = make_forcefield(fixture);
    auto direct = make_direct_model(fixture);
    auto reciprocal = make_reciprocal_model(fixture);
    const std::array<std::uint64_t, 1> atom_i{{0U}};
    const std::array<std::uint64_t, 1> atom_j{{1U}};
    const std::array<double, 1> distance{{
        std::sqrt(std::pow(fixture.x[0] - fixture.x[1], 2.0) +
                  std::pow(fixture.y[0] - fixture.y[1], 2.0) +
                  std::pow(fixture.z[0] - fixture.z[1], 2.0))}};
    bg_distance_constraints_v1 constraints{};
    require_status(bg_distance_constraints_v1_init(
        &constraints, sizeof(constraints), BG_ABI_VERSION), BG_STATUS_OK,
        "constraint init failed");
    constraints.constraint_count = 1U;
    constraints.atom_i = atom_i.data();
    constraints.atom_j = atom_j.data();
    constraints.distance_angstrom = distance.data();
    auto simulation = make_simulation(
        system.get(), forcefield.get(), direct.get(), reciprocal.get(),
        &constraints);
    bg_particle_soa_view before{};
    require_status(bg_particle_soa_view_init(
        &before, sizeof(before), BG_ABI_VERSION), BG_STATUS_OK,
        "particle view init failed");
    require_status(bg_particle_mesh_ewald_composite_simulation_v1_get_particles(
        simulation.get(), &before), BG_STATUS_OK, "particle view failed");
    system.reset();
    forcefield.reset();
    direct.reset();
    reciprocal.reset();
    integrate(context.get(), simulation.get(), 1U);
    bg_particle_soa_view after{};
    require_status(bg_particle_soa_view_init(
        &after, sizeof(after), BG_ABI_VERSION), BG_STATUS_OK,
        "particle view init failed");
    require_status(bg_particle_mesh_ewald_composite_simulation_v1_get_particles(
        simulation.get(), &after), BG_STATUS_OK, "particle view failed");
    require(before.position_x_angstrom == after.position_x_angstrom &&
            before.velocity_x_angstrom_per_femtosecond ==
                after.velocity_x_angstrom_per_femtosecond,
            "owned particle addresses changed");
}

void verify_checkpoint_rejections() {
    const Fixture fixture;
    auto system = make_system(fixture, fixture.charge);
    auto forcefield = make_forcefield(fixture);
    auto direct = make_direct_model(fixture);
    auto reciprocal = make_reciprocal_model(fixture);
    auto simulation = make_simulation(
        system.get(), forcefield.get(), direct.get(), reciprocal.get());
    const auto valid = checkpoint(simulation.get());
    bg_simulation_options_v1 options{};
    require_status(bg_simulation_options_v1_init(
        &options, sizeof(options), BG_ABI_VERSION), BG_STATUS_OK,
        "options init failed");
    options.integrator = BG_INTEGRATOR_VELOCITY_VERLET;
    options.timestep_femtoseconds = 0.001;
    bg_simulation *legacy_raw = nullptr;
    require_status(bg_simulation_create(
        system.get(), forcefield.get(), nullptr, &options, &legacy_raw),
        BG_STATUS_OK, "legacy simulation create failed");
    LegacySimulationPtr legacy(legacy_raw);
    std::uint64_t legacy_size = 0U;
    require_status(bg_simulation_checkpoint_size(legacy.get(), &legacy_size),
                   BG_STATUS_OK, "legacy checkpoint size failed");
    std::vector<std::uint8_t> legacy_bytes(legacy_size);
    std::uint64_t written = 0U;
    require_status(bg_simulation_checkpoint_write(
        legacy.get(), legacy_bytes.data(), legacy_bytes.size(), &written),
        BG_STATUS_OK, "legacy checkpoint write failed");
    require(written == legacy_bytes.size(), "legacy checkpoint size changed");

    bg_direct_ewald_composite_simulation_v1 *direct_raw = nullptr;
    bg_direct_ewald_error_v1 create_error{};
    init_error(&create_error);
    require_status(bg_direct_ewald_composite_simulation_v1_create(
        system.get(), forcefield.get(), direct.get(), nullptr, &options,
        &direct_raw, &create_error), BG_STATUS_OK,
        "direct composite simulation create failed");
    DirectSimulationPtr direct_simulation(direct_raw);
    std::uint64_t direct_size = 0U;
    require_status(bg_direct_ewald_composite_simulation_v1_checkpoint_size(
        direct_simulation.get(), &direct_size), BG_STATUS_OK,
        "direct checkpoint size failed");
    std::vector<std::uint8_t> direct_bytes(direct_size);
    require_status(bg_direct_ewald_composite_simulation_v1_checkpoint_write(
        direct_simulation.get(), direct_bytes.data(), direct_bytes.size(),
        &written), BG_STATUS_OK, "direct checkpoint write failed");
    require(written == direct_bytes.size(), "direct checkpoint size changed");

    for (const auto *bytes : {&legacy_bytes, &direct_bytes}) {
        require_status(
            bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_load(
                simulation.get(), bytes->data(), bytes->size()),
            BG_STATUS_INVALID_ARGUMENT, "cross-format magic was accepted");
        require(checkpoint(simulation.get()) == valid,
                "cross-format checkpoint changed destination state");
    }
    auto corrupt = valid;
    corrupt.back() ^= 1U;
    require_status(
        bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_load(
            simulation.get(), corrupt.data(), corrupt.size()),
        BG_STATUS_INVALID_ARGUMENT, "corrupt checkpoint was accepted");
    require_status(
        bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_load(
            simulation.get(), valid.data(), valid.size() - 1U),
        BG_STATUS_INVALID_ARGUMENT, "truncated checkpoint was accepted");
    auto appended = valid;
    appended.push_back(0U);
    require_status(
        bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_load(
            simulation.get(), appended.data(), appended.size()),
        BG_STATUS_INVALID_ARGUMENT, "appended checkpoint was accepted");
}

void verify_backend_preflight_transactionality() {
    Fixture fixture;
    auto system = make_system(fixture, fixture.charge);
    auto forcefield = make_forcefield(fixture);
    auto direct = make_direct_model(fixture);
    auto reciprocal = make_reciprocal_model(fixture);
    auto simulation = make_simulation(
        system.get(), forcefield.get(), direct.get(), reciprocal.get());
    const auto before = checkpoint(simulation.get());
    auto auto_context = make_context(BG_BACKEND_AUTO);
    bg_dynamics_report_v1 report{};
    init_report(&report);
    report.total_kcal_per_mol = 123.0;
    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    error.code = BG_DIRECT_EWALD_ERROR_PAIR_BELOW_MINIMUM_DISTANCE;
    std::strcpy(error.detail, "stale typed error");
    require_status(bg_context_integrate_particle_mesh_ewald_composite_v1(
        auto_context.get(), simulation.get(), 1U, &report, &error),
        BG_STATUS_UNSUPPORTED_BACKEND, "AUTO did not fail closed");
    require_exact(report.total_kcal_per_mol, 123.0,
                  "AUTO mutated report");
    require(error.code == BG_DIRECT_EWALD_ERROR_NONE && error.detail[0] == '\0',
            "AUTO preflight retained stale typed error");
    std::uint64_t step = 99U;
    require_status(
        bg_particle_mesh_ewald_composite_simulation_v1_get_absolute_step(
            simulation.get(), &step), BG_STATUS_OK, "step query failed");
    require(step == 0U, "AUTO mutated simulation step");
    require(checkpoint(simulation.get()) == before,
            "AUTO mutated checkpoint state");

    auto explicit_context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    explicit_context->requested_backend = BG_BACKEND_RUST_CPU;
    error.code = BG_DIRECT_EWALD_ERROR_PAIR_BELOW_MINIMUM_DISTANCE;
    std::strcpy(error.detail, "stale typed error");
    require_status(bg_context_integrate_particle_mesh_ewald_composite_v1(
        explicit_context.get(), simulation.get(), 1U, &report, &error),
        BG_STATUS_ABI_MISMATCH, "requested/resolved mismatch was accepted");
    require_exact(report.total_kcal_per_mol, 123.0,
                  "lane mismatch mutated report");
    require(error.code == BG_DIRECT_EWALD_ERROR_NONE && error.detail[0] == '\0',
            "lane mismatch retained stale typed error");
    require(checkpoint(simulation.get()) == before,
            "lane mismatch mutated checkpoint state");

    const std::array<bg_backend, 3U> unsupported_lanes{
        static_cast<bg_backend>(BG_BACKEND_HIP_SAFE),
        static_cast<bg_backend>(BG_BACKEND_HIP_FAST),
        static_cast<bg_backend>(999)};
    for (const bg_backend lane : unsupported_lanes) {
        explicit_context->requested_backend = lane;
        explicit_context->backend = lane;
        error.code = BG_DIRECT_EWALD_ERROR_PAIR_BELOW_MINIMUM_DISTANCE;
        std::strcpy(error.detail, "stale typed error");
        require_status(bg_context_integrate_particle_mesh_ewald_composite_v1(
            explicit_context.get(), simulation.get(), 1U, &report, &error),
            BG_STATUS_UNSUPPORTED_BACKEND,
            "HIP or unknown requested lane was accepted");
        require(checkpoint(simulation.get()) == before,
                "unsupported lane mutated checkpoint state");
        require(error.code == BG_DIRECT_EWALD_ERROR_NONE &&
                    error.detail[0] == '\0',
                "unsupported lane retained stale typed error");
    }
}

}  // namespace

int main() {
    static_assert(!is_complete<bg_particle_mesh_ewald_composite_simulation_v1>::value,
                  "public owner must remain opaque");
    require(bg_particle_mesh_ewald_composite_dynamics_abi_version() == 1U,
            "ABI version mismatch");
    require(std::strcmp(
        bg_particle_mesh_ewald_composite_dynamics_v1_profile_id(),
        "betelgeuze.native_particle_mesh_ewald_composite_dynamics/1.0.0") == 0,
        "profile mismatch");
    verify_runtime_and_checkpoint_identity();
    verify_force_output_scratch_reuse();
    verify_manual_velocity_verlet_final_force_bits();
    verify_short_parent_force_scratch_reuse();
    verify_direct_parent_force_scratch_reuse();
    verify_reciprocal_parent_force_scratch_reuse();
    verify_rust_reciprocal_provider_force_scratch_reuse();
    verify_short_system_scratch_reuse();
    verify_short_system_scratch_drift_fails_closed();
    verify_zero_step_and_restart();
    verify_deep_ownership_and_constraints();
    verify_checkpoint_rejections();
    verify_backend_preflight_transactionality();
    verify_late_typed_failure_rolls_back();
    return 0;
}
