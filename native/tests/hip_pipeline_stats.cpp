#include "betelgeuze/engine.h"
#include "hip/backend.hpp"
#include "internal.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <vector>

namespace {

constexpr std::size_t kXCount = 10;
constexpr std::size_t kYCount = 10;
constexpr std::size_t kZCount = 3;
constexpr std::size_t kAtomCount = kXCount * kYCount * kZCount;
constexpr double kSpacingAngstrom = 3.0;
constexpr uint64_t kExpectedNeighborPairs = UINT64_C(800);

[[noreturn]] void fail_test(const char *message) {
    std::fprintf(stderr, "HIP pipeline-stat test failure: %s\n", message);
    std::abort();
}

void require(bool condition, const char *message) {
    if (!condition) {
        fail_test(message);
    }
}

bool hip_device_is_required() noexcept {
    const char *required = std::getenv("BG_REQUIRE_HIP_DEVICE");
    return required != nullptr && required[0] == '1' && required[1] == '\0';
}

void require_status(bg_status actual, bg_status expected, const char *message) {
    if (actual != expected) {
        std::fprintf(
            stderr,
            "HIP pipeline-stat test failure: %s (expected %d, observed %d: "
            "%s)\n",
            message,
            static_cast<int>(expected),
            static_cast<int>(actual),
            bg_last_error_message());
        std::abort();
    }
}

uint64_t bits(double value) noexcept {
    uint64_t result = UINT64_C(0);
    static_assert(sizeof(result) == sizeof(value));
    std::memcpy(&result, &value, sizeof(result));
    return result;
}

struct ContextDeleter final {
    void operator()(bg_context *context) const noexcept {
        bg_context_destroy(context);
    }
};

struct SystemDeleter final {
    void operator()(bg_system *system) const noexcept {
        bg_system_destroy(system);
    }
};

struct ForceFieldDeleter final {
    void operator()(bg_forcefield *forcefield) const noexcept {
        bg_forcefield_destroy(forcefield);
    }
};

using ContextPtr = std::unique_ptr<bg_context, ContextDeleter>;
using SystemPtr = std::unique_ptr<bg_system, SystemDeleter>;
using ForceFieldPtr = std::unique_ptr<bg_forcefield, ForceFieldDeleter>;

struct Evaluation final {
    bg_energy_components_v1 energy{};
    std::vector<double> force_x;
    std::vector<double> force_y;
    std::vector<double> force_z;
};

ContextPtr make_hip_context() {
    bg_context_options options{};
    require_status(
        bg_context_options_init(&options, sizeof(options), BG_ABI_VERSION),
        BG_STATUS_OK,
        "context option initialization failed");
    options.backend = BG_BACKEND_HIP;
    options.device_ordinal = 0;

    bg_context *raw_context = nullptr;
    require_status(
        bg_context_create(&options, &raw_context),
        BG_STATUS_OK,
        "HIP context creation failed");
    require(raw_context != nullptr, "HIP context creation returned null");

    bg_backend selected_backend = BG_BACKEND_AUTO;
    require_status(
        bg_context_get_backend(raw_context, &selected_backend),
        BG_STATUS_OK,
        "context backend query failed");
    require(
        selected_backend == BG_BACKEND_HIP,
        "HIP context silently selected another backend");
    return ContextPtr(raw_context);
}

SystemPtr make_grid_system(double translation = 0.0) {
    std::vector<double> position_x(kAtomCount, 0.0);
    std::vector<double> position_y(kAtomCount, 0.0);
    std::vector<double> position_z(kAtomCount, 0.0);
    std::vector<double> mass(kAtomCount, 1.0);
    std::vector<double> charge(kAtomCount, 0.0);

    std::size_t atom = 0;
    for (std::size_t z = 0; z < kZCount; ++z) {
        for (std::size_t y = 0; y < kYCount; ++y) {
            for (std::size_t x = 0; x < kXCount; ++x) {
                position_x[atom] = translation +
                                    static_cast<double>(x) *
                                        kSpacingAngstrom;
                position_y[atom] = translation +
                                    static_cast<double>(y) *
                                        kSpacingAngstrom;
                position_z[atom] = translation +
                                    static_cast<double>(z) *
                                        kSpacingAngstrom;
                ++atom;
            }
        }
    }
    require(atom == kAtomCount, "grid construction produced the wrong size");

    bg_particle_soa particles{};
    require_status(
        bg_particle_soa_init(&particles, sizeof(particles), BG_ABI_VERSION),
        BG_STATUS_OK,
        "particle descriptor initialization failed");
    particles.particle_count = static_cast<uint64_t>(kAtomCount);
    particles.position_x_angstrom = position_x.data();
    particles.position_y_angstrom = position_y.data();
    particles.position_z_angstrom = position_z.data();
    particles.mass_dalton = mass.data();
    particles.charge_elementary = charge.data();

    bg_system *raw_system = nullptr;
    require_status(
        bg_system_create(&particles, &raw_system),
        BG_STATUS_OK,
        "grid system creation failed");
    require(raw_system != nullptr, "grid system creation returned null");
    return SystemPtr(raw_system);
}

ForceFieldPtr make_zero_forcefield() {
    const std::vector<double> sigma(kAtomCount, 1.0);
    const std::vector<double> epsilon(kAtomCount, 0.0);
    const std::array<uint64_t, 1> bond_i{{UINT64_C(0)}};
    const std::array<uint64_t, 1> bond_j{{UINT64_C(1)}};
    const std::array<double, 1> bond_equilibrium{{kSpacingAngstrom}};
    const std::array<double, 1> bond_force_constant{{1.0}};
    const std::array<uint64_t, 1> exclusion_i{{UINT64_C(0)}};
    const std::array<uint64_t, 1> exclusion_j{{UINT64_C(1)}};

    bg_forcefield_soa_v1 parameters{};
    require_status(
        bg_forcefield_soa_v1_init(
            &parameters, sizeof(parameters), BG_ABI_VERSION),
        BG_STATUS_OK,
        "force-field descriptor initialization failed");
    parameters.atom_count = static_cast<uint64_t>(kAtomCount);
    parameters.periodic_axes_mask = BG_PERIODIC_AXES_ALL;
    parameters.sigma_angstrom = sigma.data();
    parameters.epsilon_kcal_per_mol = epsilon.data();

    parameters.bond_count = UINT64_C(1);
    parameters.bond_atom_i = bond_i.data();
    parameters.bond_atom_j = bond_j.data();
    parameters.bond_equilibrium_angstrom = bond_equilibrium.data();
    parameters.bond_force_constant_kcal_per_mol_angstrom2 =
        bond_force_constant.data();

    parameters.exclusion_count = UINT64_C(1);
    parameters.exclusion_atom_i = exclusion_i.data();
    parameters.exclusion_atom_j = exclusion_j.data();

    parameters.cell_lengths_angstrom[0] = 30.0;
    parameters.cell_lengths_angstrom[1] = 30.0;
    parameters.cell_lengths_angstrom[2] = 30.0;
    parameters.cutoff_angstrom = 4.0;
    parameters.switch_start_angstrom = 3.0;
    parameters.dielectric = 1.0;
    parameters.screening_kappa_per_angstrom = 0.0;
    parameters.minimum_pair_distance_angstrom = 1.0e-6;

    bg_forcefield *raw_forcefield = nullptr;
    require_status(
        bg_forcefield_create(&parameters, &raw_forcefield),
        BG_STATUS_OK,
        "force-field creation failed");
    require(raw_forcefield != nullptr, "force-field creation returned null");
    return ForceFieldPtr(raw_forcefield);
}

Evaluation evaluate(
    const bg_context *context,
    const bg_system *system,
    const bg_forcefield *forcefield) {
    Evaluation result;
    result.force_x.assign(kAtomCount, 0.0);
    result.force_y.assign(kAtomCount, 0.0);
    result.force_z.assign(kAtomCount, 0.0);

    require_status(
        bg_energy_components_v1_init(
            &result.energy, sizeof(result.energy), BG_ABI_VERSION),
        BG_STATUS_OK,
        "energy descriptor initialization failed");
    bg_force_soa_v1 forces{};
    require_status(
        bg_force_soa_v1_init(&forces, sizeof(forces), BG_ABI_VERSION),
        BG_STATUS_OK,
        "force descriptor initialization failed");
    forces.particle_capacity = static_cast<uint64_t>(kAtomCount);
    forces.x_kcal_per_mol_angstrom = result.force_x.data();
    forces.y_kcal_per_mol_angstrom = result.force_y.data();
    forces.z_kcal_per_mol_angstrom = result.force_z.data();

    require_status(
        bg_context_evaluate(context, system, forcefield, &result.energy, &forces),
        BG_STATUS_OK,
        "HIP pipeline evaluation failed");
    require(
        forces.particle_count == static_cast<uint64_t>(kAtomCount),
        "force particle count was not committed");
    return result;
}

std::array<double, 6> energy_values(
    const bg_energy_components_v1 &energy) noexcept {
    return {{
        energy.harmonic_bond_kcal_per_mol,
        energy.harmonic_angle_kcal_per_mol,
        energy.periodic_torsion_kcal_per_mol,
        energy.lennard_jones_kcal_per_mol,
        energy.coulomb_kcal_per_mol,
        energy.total_kcal_per_mol,
    }};
}

void require_zero_evaluation(const Evaluation &evaluation) {
    for (const double energy : energy_values(evaluation.energy)) {
        require(energy == 0.0, "zero fixture produced non-zero energy");
    }
    for (std::size_t atom = 0; atom < kAtomCount; ++atom) {
        require(
            evaluation.force_x[atom] == 0.0 &&
                evaluation.force_y[atom] == 0.0 &&
                evaluation.force_z[atom] == 0.0,
            "zero fixture produced a non-zero force");
    }
}

void require_repeat_determinism(
    const Evaluation &first,
    const Evaluation &second) {
    const auto first_energy = energy_values(first.energy);
    const auto second_energy = energy_values(second.energy);
    for (std::size_t component = 0; component < first_energy.size();
         ++component) {
        require(
            bits(first_energy[component]) == bits(second_energy[component]),
            "repeated energy changed bits");
    }
    for (std::size_t atom = 0; atom < kAtomCount; ++atom) {
        require(
            bits(first.force_x[atom]) == bits(second.force_x[atom]) &&
                bits(first.force_y[atom]) == bits(second.force_y[atom]) &&
                bits(first.force_z[atom]) == bits(second.force_z[atom]),
            "repeated force changed bits");
    }
}

void require_expected_stats(
    const betelgeuze::native::hip::EvaluationStats &stats) {
    require(stats.cell_count > UINT64_C(1), "cell list used only one cell");
    require(
        stats.neighbor_pair_count == kExpectedNeighborPairs,
        "neighbor list did not contain the 800 canonical grid pairs");
    require(
        stats.bonded_contribution_count == UINT64_C(1),
        "bonded kernel did not receive exactly one contribution");
}

bool same_stats(
    const betelgeuze::native::hip::EvaluationStats &left,
    const betelgeuze::native::hip::EvaluationStats &right) noexcept {
    return left.cell_count == right.cell_count &&
           left.neighbor_pair_count == right.neighbor_pair_count &&
           left.bonded_contribution_count == right.bonded_contribution_count;
}

bool hip_is_available() {
    uint8_t available = UINT8_C(0);
    require_status(
        bg_backend_is_available(BG_BACKEND_HIP, 0, &available),
        BG_STATUS_OK,
        "HIP availability query failed");
    return available != UINT8_C(0);
}

}  // namespace

int main() {
    static_assert(kAtomCount == 300);
    static_assert(kAtomCount > 256);

    if (!hip_is_available()) {
        if (hip_device_is_required()) {
            fail_test(
                "BG_REQUIRE_HIP_DEVICE=1 but no HIP device is available at "
                "ordinal zero");
        }
        std::puts("SKIP: no HIP device is available at ordinal zero");
        return 77;
    }

    const ContextPtr context = make_hip_context();
    const SystemPtr system = make_grid_system();
    const ForceFieldPtr forcefield = make_zero_forcefield();

    const Evaluation first =
        evaluate(context.get(), system.get(), forcefield.get());
    betelgeuze::native::hip::EvaluationStats first_stats{};
    require_status(
        betelgeuze::native::hip::get_last_evaluation_stats(
            *context, &first_stats),
        BG_STATUS_OK,
        "first HIP pipeline-stat query failed");
    require_expected_stats(first_stats);
    require_zero_evaluation(first);

    const Evaluation second =
        evaluate(context.get(), system.get(), forcefield.get());
    betelgeuze::native::hip::EvaluationStats second_stats{};
    require_status(
        betelgeuze::native::hip::get_last_evaluation_stats(
            *context, &second_stats),
        BG_STATUS_OK,
        "repeated HIP pipeline-stat query failed");
    require_expected_stats(second_stats);
    require(same_stats(first_stats, second_stats), "pipeline stats changed");
    require_zero_evaluation(second);
    require_repeat_determinism(first, second);

    /* A large common unwrapped image offset must be removed before periodic
     * phase reduction without degrading the regular cell pipeline to the
     * direct-pair fallback. */
    const SystemPtr translated_system =
        make_grid_system(0x1.720b2c0dee5d0p+50);
    const Evaluation translated =
        evaluate(context.get(), translated_system.get(), forcefield.get());
    betelgeuze::native::hip::EvaluationStats translated_stats{};
    require_status(
        betelgeuze::native::hip::get_last_evaluation_stats(
            *context, &translated_stats),
        BG_STATUS_OK,
        "translated HIP pipeline-stat query failed");
    require_expected_stats(translated_stats);
    require_zero_evaluation(translated);

    std::puts("HIP cell/neighbor/bonded pipeline-stat test passed");
    return 0;
}
