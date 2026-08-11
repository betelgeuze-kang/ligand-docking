#include "betelgeuze/engine.h"
#include "hip/backend.hpp"
#include "internal.hpp"

#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

namespace {

[[noreturn]] void fail_test(const char *message) {
    std::fprintf(stderr, "HIP fault-row test failure: %s\n", message);
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
            "HIP fault-row test failure: %s (expected %d, observed %d: %s)\n",
            message,
            static_cast<int>(expected),
            static_cast<int>(actual),
            bg_last_error_message());
        std::abort();
    }
}

bool same_energy(
    const bg_energy_components_v1 &left,
    const bg_energy_components_v1 &right) noexcept {
    return std::memcmp(&left, &right, sizeof(left)) == 0;
}

void require_outputs_unchanged(
    const bg_energy_components_v1 &energy,
    const bg_energy_components_v1 &energy_before,
    const bg_force_soa_v1 &forces,
    const std::vector<double> &force_x,
    const std::vector<double> &force_y,
    const std::vector<double> &force_z,
    const std::vector<double> &force_x_before,
    const std::vector<double> &force_y_before,
    const std::vector<double> &force_z_before,
    const char *phase) {
    if (!same_energy(energy, energy_before) ||
        forces.particle_count != UINT64_C(777) ||
        force_x != force_x_before || force_y != force_y_before ||
        force_z != force_z_before) {
        fail_test(phase);
    }
}

}  // namespace

int main() {
    uint8_t available = UINT8_C(0);
    require_status(
        bg_backend_is_available(BG_BACKEND_HIP, 0, &available),
        BG_STATUS_OK,
        "HIP availability query failed");
    if (available == UINT8_C(0)) {
        if (hip_device_is_required()) {
            fail_test(
                "BG_REQUIRE_HIP_DEVICE=1 but no HIP device is available at "
                "ordinal zero");
        }
        std::puts("SKIP: no HIP device is available at ordinal zero");
        return 77;
    }

    bg_context_options options{};
    require_status(
        bg_context_options_init(&options, sizeof(options), BG_ABI_VERSION),
        BG_STATUS_OK,
        "context option initialization failed");
    options.backend = BG_BACKEND_HIP;
    bg_context *context = nullptr;
    require_status(
        bg_context_create(&options, &context),
        BG_STATUS_OK,
        "fault-injected HIP context creation failed");
    require(context != nullptr, "HIP context creation returned null");

    const std::array<double, 2> x = {0.0, 2.0};
    const std::array<double, 2> y = {0.0, 0.0};
    const std::array<double, 2> z = {0.0, 0.0};
    const std::array<double, 2> mass = {1.0, 1.0};
    const std::array<double, 2> charge = {0.25, -0.25};
    bg_particle_soa particles{};
    require_status(
        bg_particle_soa_init(&particles, sizeof(particles), BG_ABI_VERSION),
        BG_STATUS_OK,
        "particle descriptor initialization failed");
    particles.particle_count = UINT64_C(2);
    particles.position_x_angstrom = x.data();
    particles.position_y_angstrom = y.data();
    particles.position_z_angstrom = z.data();
    particles.mass_dalton = mass.data();
    particles.charge_elementary = charge.data();
    bg_system *system = nullptr;
    require_status(
        bg_system_create(&particles, &system),
        BG_STATUS_OK,
        "system creation failed");

    const std::array<double, 2> sigma = {1.0, 1.2};
    const std::array<double, 2> epsilon = {0.2, 0.3};
    bg_forcefield_soa_v1 parameters{};
    require_status(
        bg_forcefield_soa_v1_init(
            &parameters, sizeof(parameters), BG_ABI_VERSION),
        BG_STATUS_OK,
        "force-field descriptor initialization failed");
    parameters.atom_count = UINT64_C(2);
    parameters.sigma_angstrom = sigma.data();
    parameters.epsilon_kcal_per_mol = epsilon.data();
    bg_forcefield *forcefield = nullptr;
    require_status(
        bg_forcefield_create(&parameters, &forcefield),
        BG_STATUS_OK,
        "force-field creation failed");

    bg_energy_components_v1 energy{};
    require_status(
        bg_energy_components_v1_init(&energy, sizeof(energy), BG_ABI_VERSION),
        BG_STATUS_OK,
        "energy descriptor initialization failed");
    energy.harmonic_bond_kcal_per_mol = 101.25;
    energy.harmonic_angle_kcal_per_mol = 102.25;
    energy.periodic_torsion_kcal_per_mol = 103.25;
    energy.lennard_jones_kcal_per_mol = 104.25;
    energy.coulomb_kcal_per_mol = 105.25;
    energy.total_kcal_per_mol = 106.25;
    const bg_energy_components_v1 energy_before = energy;

    std::vector<double> force_x(2, 201.5);
    std::vector<double> force_y(2, 202.5);
    std::vector<double> force_z(2, 203.5);
    const std::vector<double> force_x_before = force_x;
    const std::vector<double> force_y_before = force_y;
    const std::vector<double> force_z_before = force_z;
    bg_force_soa_v1 forces{};
    require_status(
        bg_force_soa_v1_init(&forces, sizeof(forces), BG_ABI_VERSION),
        BG_STATUS_OK,
        "force descriptor initialization failed");
    forces.particle_capacity = UINT64_C(2);
    forces.particle_count = UINT64_C(777);
    forces.x_kcal_per_mol_angstrom = force_x.data();
    forces.y_kcal_per_mol_angstrom = force_y.data();
    forces.z_kcal_per_mol_angstrom = force_z.data();

    require_status(
        betelgeuze::native::hip::set_allocation_failure(
            *context, UINT64_C(1)),
        BG_STATUS_OK,
        "first-allocation fault setup failed");
    require_status(
        bg_context_evaluate(
            context, system, forcefield, &energy, &forces),
        BG_STATUS_OUT_OF_MEMORY,
        "first-allocation fault did not report out of memory");
    require_outputs_unchanged(
        energy,
        energy_before,
        forces,
        force_x,
        force_y,
        force_z,
        force_x_before,
        force_y_before,
        force_z_before,
        "first-allocation OOM changed public outputs");
    require(
        betelgeuze::native::hip::live_allocation_count(*context) ==
            UINT64_C(0),
        "first-allocation OOM leaked a device allocation");

    /* This fixture performs fifteen successful device allocations before its
     * reduced-energy row.  Failing allocation sixteen therefore exercises
     * cleanup after input upload, cell/neighbor construction, and the
     * contribution allocation have all succeeded. */
    require_status(
        betelgeuze::native::hip::set_allocation_failure(
            *context, UINT64_C(16)),
        BG_STATUS_OK,
        "late-allocation fault setup failed");
    require_status(
        bg_context_evaluate(
            context, system, forcefield, &energy, &forces),
        BG_STATUS_OUT_OF_MEMORY,
        "late-allocation fault did not report out of memory");
    require_outputs_unchanged(
        energy,
        energy_before,
        forces,
        force_x,
        force_y,
        force_z,
        force_x_before,
        force_y_before,
        force_z_before,
        "late-allocation OOM changed public outputs");
    require(
        betelgeuze::native::hip::live_allocation_count(*context) ==
            UINT64_C(0),
        "late-allocation OOM leaked a device allocation");

    /* The two-atom force path reaches its deterministic incidence merge-sort
     * scratch at allocation twenty-two.  This is the latest owned allocation
     * in the fixture and exercises rollback after every evaluator kernel and
     * all other output storage have been prepared. */
    require_status(
        betelgeuze::native::hip::set_allocation_failure(
            *context, UINT64_C(22)),
        BG_STATUS_OK,
        "merge-sort scratch fault setup failed");
    require_status(
        bg_context_evaluate(
            context, system, forcefield, &energy, &forces),
        BG_STATUS_OUT_OF_MEMORY,
        "merge-sort scratch fault did not report out of memory");
    require_outputs_unchanged(
        energy,
        energy_before,
        forces,
        force_x,
        force_y,
        force_z,
        force_x_before,
        force_y_before,
        force_z_before,
        "merge-sort scratch OOM changed public outputs");
    require(
        betelgeuze::native::hip::live_allocation_count(*context) ==
            UINT64_C(0),
        "merge-sort scratch OOM leaked a device allocation");

    require_status(
        betelgeuze::native::hip::set_allocation_failure(
            *context, UINT64_C(0)),
        BG_STATUS_OK,
        "fault-injection disable failed");
    require_status(
        bg_context_evaluate(
            context, system, forcefield, &energy, &forces),
        BG_STATUS_OK,
        "evaluator did not recover after fault injection was disabled");
    require(!same_energy(energy, energy_before), "success did not commit energy");
    require(
        forces.particle_count == UINT64_C(2),
        "success did not commit force particle_count");
    require(force_x != force_x_before, "success did not commit force output");
    require(
        betelgeuze::native::hip::live_allocation_count(*context) ==
            UINT64_C(0),
        "successful evaluation leaked a device allocation");

    bg_forcefield_destroy(forcefield);
    bg_system_destroy(system);
    bg_context_destroy(context);
    std::puts("HIP fault-injected OOM transactionality test passed");
    return 0;
}
