#include "betelgeuze/engine.h"

#include <cassert>
#include <cstdint>
#include <limits>
#include <memory>
#include <type_traits>

namespace {

struct ContextDeleter {
    void operator()(bg_context *context) const noexcept {
        bg_context_destroy(context);
    }
};

struct SystemDeleter {
    void operator()(bg_system *system) const noexcept {
        bg_system_destroy(system);
    }
};

}  // namespace

int main() {
    using ContextOptionsInitializer = bg_status(BG_CALL *)(
        bg_context_options *, std::size_t, uint32_t) noexcept;
    static_assert(std::is_standard_layout_v<bg_context_options>);
    static_assert(std::is_standard_layout_v<bg_particle_soa>);
    static_assert(std::is_standard_layout_v<bg_particle_soa_view>);
    static_assert(std::is_standard_layout_v<bg_position_soa>);
    static_assert(std::is_standard_layout_v<bg_docking_scorer_v1_context_soa_v1>);
    static_assert(
        std::is_standard_layout_v<bg_docking_scorer_v1_candidate_batch_soa_v1>);
    static_assert(std::is_standard_layout_v<bg_docking_scorer_v1_row_v1>);
    static_assert(std::is_standard_layout_v<bg_docking_scorer_v1_output_v1>);
    static_assert(
        std::is_standard_layout_v<bg_docking_pose_validity_context_soa_v1>);
    static_assert(std::is_standard_layout_v<
                  bg_docking_pose_validity_candidate_batch_soa_v1>);
    static_assert(
        std::is_standard_layout_v<bg_docking_pose_validity_row_v1>);
    static_assert(
        std::is_standard_layout_v<bg_docking_pose_validity_output_v1>);
    static_assert(
        std::is_standard_layout_v<bg_docking_torsion_v7_context_soa_v1>);
    static_assert(std::is_standard_layout_v<
                  bg_docking_torsion_v7_candidate_batch_soa_v1>);
    static_assert(std::is_standard_layout_v<bg_docking_torsion_v7_row_v1>);
    static_assert(std::is_standard_layout_v<bg_docking_torsion_v7_move_v1>);
    static_assert(
        std::is_standard_layout_v<bg_docking_torsion_v7_output_v1>);
    static_assert(noexcept(bg_abi_version()));
    static_assert(noexcept(bg_context_destroy(nullptr)));
    static_assert(noexcept(bg_system_destroy(nullptr)));
    static_assert(noexcept(bg_docking_torsion_v7_destroy(nullptr)));
    static_assert(std::is_same_v<
                  decltype(&bg_context_options_init),
                  ContextOptionsInitializer>);

    const ContextOptionsInitializer context_options_initializer =
        (bg_context_options_init);
    bg_context_options raw_options{};
    assert(context_options_initializer(
               &raw_options,
               sizeof(raw_options),
               BG_ABI_VERSION) == BG_STATUS_OK);

    bg_context_options options{};
    assert(bg_context_options_init(&options) == BG_STATUS_OK);
    options.backend = BG_BACKEND_CPU;
    bg_context *raw_context = nullptr;
    assert(bg_context_create(&options, &raw_context) == BG_STATUS_OK);
    std::unique_ptr<bg_context, ContextDeleter> context(raw_context);

    const double x[] = {0.0, 1.25};
    const double y[] = {0.5, 1.5};
    const double z[] = {1.0, 1.75};
    const double vx[] = {0.01, 0.02};
    const double vy[] = {0.03, 0.04};
    const double vz[] = {0.05, 0.06};
    const double mass[] = {12.0, 1.0};
    const double charge[] = {-0.1, 0.1};

    bg_particle_soa particles{};
    assert(bg_particle_soa_init(&particles) == BG_STATUS_OK);
    particles.particle_count = 2;
    particles.position_x_angstrom = x;
    particles.position_y_angstrom = y;
    particles.position_z_angstrom = z;
    particles.velocity_x_angstrom_per_femtosecond = vx;
    particles.velocity_y_angstrom_per_femtosecond = vy;
    particles.velocity_z_angstrom_per_femtosecond = vz;
    particles.mass_dalton = mass;
    particles.charge_elementary = charge;

    bg_system *raw_system = nullptr;
    assert(bg_system_create(&particles, &raw_system) == BG_STATUS_OK);
    std::unique_ptr<bg_system, SystemDeleter> system(raw_system);

    bg_particle_soa_view view{};
    assert(bg_particle_soa_view_init(&view) == BG_STATUS_OK);
    assert(bg_system_get_particles(system.get(), &view) == BG_STATUS_OK);
    assert(view.position_x_angstrom[1] == 1.25);
    assert(view.velocity_z_angstrom_per_femtosecond[0] == 0.05);

    bg_position_soa invalid{};
    assert(bg_position_soa_init(&invalid) == BG_STATUS_OK);
    invalid.particle_count = 2;
    const double bad_x[] = {0.0, std::numeric_limits<double>::infinity()};
    invalid.x_angstrom = bad_x;
    invalid.y_angstrom = y;
    invalid.z_angstrom = z;
    assert(bg_system_set_positions(system.get(), &invalid) ==
           BG_STATUS_INVALID_ARGUMENT);

    assert(bg_context_get_backend(nullptr, nullptr) ==
           BG_STATUS_INVALID_ARGUMENT);
    assert(bg_system_get_particle_count(nullptr, nullptr) ==
           BG_STATUS_INVALID_ARGUMENT);
    return 0;
}
