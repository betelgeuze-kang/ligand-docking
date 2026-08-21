#include "dynamics.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <memory>
#include <utility>
#include <vector>

namespace betelgeuze::native::dynamics {
namespace {

template <typename Descriptor>
bg_status validate_header(
    const Descriptor &descriptor,
    const char *size_message,
    const char *version_message) noexcept {
    return validate_descriptor_header(
        descriptor.struct_size,
        sizeof(Descriptor),
        descriptor.abi_version,
        size_message,
        version_message);
}

bg_status validate_constraints_descriptor(
    const bg_distance_constraints_v1 &constraints) noexcept {
    bg_status status = validate_header(
        constraints,
        "bg_distance_constraints_v1 struct_size does not match ABI v1",
        "bg_distance_constraints_v1 abi_version does not match the native library");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = validate_unit_system(constraints.unit_system);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (constraints.reserved0 != UINT32_C(0) ||
        constraints.reserved1 != UINT32_C(0) ||
        !reserved_is_zero(constraints.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "bg_distance_constraints_v1 reserved fields must be zero");
    }
    if (!std::isfinite(constraints.tolerance_angstrom) ||
        constraints.tolerance_angstrom <= 0.0) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "constraint tolerance must be finite and positive");
    }
    if (!std::isfinite(
            constraints.velocity_tolerance_angstrom_per_femtosecond) ||
        constraints.velocity_tolerance_angstrom_per_femtosecond <= 0.0) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "constraint velocity tolerance must be finite and positive");
    }
    if (constraints.max_iterations == UINT32_C(0)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "constraint max_iterations must be non-zero");
    }
    return BG_STATUS_OK;
}

bg_status validate_simulation_options(
    const bg_simulation_options_v1 &options) noexcept {
    bg_status status = validate_header(
        options,
        "bg_simulation_options_v1 struct_size does not match ABI v1",
        "bg_simulation_options_v1 abi_version does not match the native library");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = validate_unit_system(options.unit_system);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (!reserved_is_zero(options.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "bg_simulation_options_v1 reserved fields must be zero");
    }
    if (options.integrator != BG_INTEGRATOR_VELOCITY_VERLET &&
        options.integrator != BG_INTEGRATOR_LANGEVIN_BAOAB) {
        return fail(BG_STATUS_INVALID_ARGUMENT, "unsupported integrator identifier");
    }
    if (!std::isfinite(options.timestep_femtoseconds) ||
        options.timestep_femtoseconds <= 0.0 ||
        0.5 * options.timestep_femtoseconds <= 0.0) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "timestep_femtoseconds and its half-step must be finite and positive");
    }
    if (!std::isfinite(options.temperature_kelvin) ||
        options.temperature_kelvin < 0.0) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "temperature_kelvin must be finite and non-negative");
    }
    if (!std::isfinite(options.friction_per_femtosecond) ||
        options.friction_per_femtosecond < 0.0) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "friction_per_femtosecond must be finite and non-negative");
    }
    return BG_STATUS_OK;
}

bg_status validate_minimizer_options(
    const bg_minimizer_options_v1 &options) noexcept {
    bg_status status = validate_header(
        options,
        "bg_minimizer_options_v1 struct_size does not match ABI v1",
        "bg_minimizer_options_v1 abi_version does not match the native library");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = validate_unit_system(options.unit_system);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (options.reserved0 != UINT32_C(0) ||
        options.reserved1 != UINT32_C(0) ||
        !reserved_is_zero(options.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "bg_minimizer_options_v1 reserved fields must be zero");
    }
    if (options.max_iterations == UINT64_C(0) ||
        options.max_line_search_steps == UINT32_C(0)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "minimizer iteration limits must be non-zero");
    }
    if (!std::isfinite(options.initial_step_angstrom2_mol_per_kcal) ||
        options.initial_step_angstrom2_mol_per_kcal <= 0.0 ||
        !std::isfinite(options.minimum_step_angstrom2_mol_per_kcal) ||
        options.minimum_step_angstrom2_mol_per_kcal <= 0.0 ||
        options.minimum_step_angstrom2_mol_per_kcal >
            options.initial_step_angstrom2_mol_per_kcal) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "minimizer steps must be finite, positive, and minimum <= initial");
    }
    if (!std::isfinite(options.energy_tolerance_kcal_per_mol) ||
        options.energy_tolerance_kcal_per_mol < 0.0 ||
        !std::isfinite(options.force_tolerance_kcal_per_mol_angstrom) ||
        options.force_tolerance_kcal_per_mol_angstrom < 0.0) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "minimizer convergence tolerances must be finite and non-negative");
    }
    if (!std::isfinite(options.armijo_coefficient) ||
        options.armijo_coefficient <= 0.0 ||
        options.armijo_coefficient >= 1.0 ||
        !std::isfinite(options.backtrack_factor) ||
        options.backtrack_factor <= 0.0 || options.backtrack_factor >= 1.0) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "Armijo coefficient and backtrack factor must lie strictly in (0,1)");
    }
    return BG_STATUS_OK;
}

template <typename Report>
bg_status validate_report(
    const Report &report,
    const char *size_message,
    const char *version_message,
    const char *reserved_message) noexcept {
    bg_status status =
        validate_header(report, size_message, version_message);
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = validate_unit_system(report.unit_system);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (report.reserved0 != UINT32_C(0) ||
        !reserved_is_zero(report.reserved)) {
        return fail(BG_STATUS_INVALID_ARGUMENT, reserved_message);
    }
    return BG_STATUS_OK;
}

bg_status validate_particle_view(bg_particle_soa_view &view) noexcept {
    bg_status status = validate_header(
        view,
        "bg_particle_soa_view struct_size does not match ABI v1",
        "bg_particle_soa_view abi_version does not match the native library");
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (view.reserved0 != UINT32_C(0) || !reserved_is_zero(view.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "bg_particle_soa_view reserved fields must be zero");
    }
    return BG_STATUS_OK;
}

void fill_particle_view(
    const bg_system &system,
    bg_particle_soa_view *view) noexcept {
    view->struct_size = static_cast<uint32_t>(sizeof(*view));
    view->abi_version = BG_ABI_VERSION;
    view->particle_count = static_cast<uint64_t>(system.position_x.size());
    view->unit_system = system.unit_system;
    view->reserved0 = UINT32_C(0);
    view->position_x_angstrom = borrowed_data(system.position_x);
    view->position_y_angstrom = borrowed_data(system.position_y);
    view->position_z_angstrom = borrowed_data(system.position_z);
    view->velocity_x_angstrom_per_femtosecond =
        borrowed_data(system.velocity_x);
    view->velocity_y_angstrom_per_femtosecond =
        borrowed_data(system.velocity_y);
    view->velocity_z_angstrom_per_femtosecond =
        borrowed_data(system.velocity_z);
    view->mass_dalton = borrowed_data(system.mass);
    view->charge_elementary = borrowed_data(system.charge);
    for (uint64_t &value : view->reserved) {
        value = UINT64_C(0);
    }
}

class DynamicStateRollback final {
  public:
    DynamicStateRollback(
        bg_simulation *simulation,
        bool snapshot_particle_channels)
        : simulation_(simulation),
          snapshot_particle_channels_(snapshot_particle_channels),
          absolute_step_(simulation->absolute_step),
          neighbor_list_data_(simulation->neighbor_list_cache.data),
          neighbor_list_build_count_(
              simulation->neighbor_list_cache.build_count),
          neighbor_list_reuse_count_(
              simulation->neighbor_list_cache.reuse_count) {
        if (snapshot_particle_channels_) {
            position_x_ = simulation_->system.position_x;
            position_y_ = simulation_->system.position_y;
            position_z_ = simulation_->system.position_z;
            velocity_x_ = simulation_->system.velocity_x;
            velocity_y_ = simulation_->system.velocity_y;
            velocity_z_ = simulation_->system.velocity_z;
        }
    }

    DynamicStateRollback(const DynamicStateRollback &) = delete;
    DynamicStateRollback &operator=(const DynamicStateRollback &) = delete;

    ~DynamicStateRollback() noexcept {
        if (committed_) {
            return;
        }
        if (snapshot_particle_channels_) {
            restore_channel(position_x_, &simulation_->system.position_x);
            restore_channel(position_y_, &simulation_->system.position_y);
            restore_channel(position_z_, &simulation_->system.position_z);
            restore_channel(velocity_x_, &simulation_->system.velocity_x);
            restore_channel(velocity_y_, &simulation_->system.velocity_y);
            restore_channel(velocity_z_, &simulation_->system.velocity_z);
        }
        simulation_->absolute_step = absolute_step_;
        simulation_->neighbor_list_cache.data =
            std::move(neighbor_list_data_);
        simulation_->neighbor_list_cache.build_count =
            neighbor_list_build_count_;
        simulation_->neighbor_list_cache.reuse_count =
            neighbor_list_reuse_count_;
    }

    void commit() noexcept {
        committed_ = true;
    }

  private:
    static void restore_channel(
        const std::vector<double> &source,
        std::vector<double> *destination) noexcept {
        std::copy(source.begin(), source.end(), destination->begin());
    }

    bg_simulation *simulation_ = nullptr;
    bool snapshot_particle_channels_ = false;
    uint64_t absolute_step_ = UINT64_C(0);
    std::shared_ptr<const bg_simulation::NeighborListCacheData>
        neighbor_list_data_;
    uint64_t neighbor_list_build_count_ = UINT64_C(0);
    uint64_t neighbor_list_reuse_count_ = UINT64_C(0);
    std::vector<double> position_x_;
    std::vector<double> position_y_;
    std::vector<double> position_z_;
    std::vector<double> velocity_x_;
    std::vector<double> velocity_y_;
    std::vector<double> velocity_z_;
    bool committed_ = false;
};

}  // namespace
}  // namespace betelgeuze::native::dynamics

extern "C" BG_API bg_status BG_CALL bg_distance_constraints_v1_init(
    bg_distance_constraints_v1 *constraints,
    std::size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            constraints,
            caller_struct_size,
            sizeof(bg_distance_constraints_v1),
            caller_abi_version,
            "constraints pointer is null",
            "distance constraints initializer size does not match the native ABI",
            "distance constraints initializer ABI version does not match");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *constraints = bg_distance_constraints_v1{};
        constraints->struct_size = static_cast<uint32_t>(sizeof(*constraints));
        constraints->abi_version = BG_ABI_VERSION;
        constraints->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        constraints->tolerance_angstrom = 1.0e-10;
        constraints->velocity_tolerance_angstrom_per_femtosecond = 1.0e-10;
        constraints->max_iterations = UINT32_C(100);
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_simulation_options_v1_init(
    bg_simulation_options_v1 *options,
    std::size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            options,
            caller_struct_size,
            sizeof(bg_simulation_options_v1),
            caller_abi_version,
            "simulation options pointer is null",
            "simulation options initializer size does not match the native ABI",
            "simulation options initializer ABI version does not match");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *options = bg_simulation_options_v1{};
        options->struct_size = static_cast<uint32_t>(sizeof(*options));
        options->abi_version = BG_ABI_VERSION;
        options->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        options->integrator = BG_INTEGRATOR_VELOCITY_VERLET;
        options->timestep_femtoseconds = 1.0;
        options->temperature_kelvin = 300.0;
        options->friction_per_femtosecond = 0.001;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_minimizer_options_v1_init(
    bg_minimizer_options_v1 *options,
    std::size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            options,
            caller_struct_size,
            sizeof(bg_minimizer_options_v1),
            caller_abi_version,
            "minimizer options pointer is null",
            "minimizer options initializer size does not match the native ABI",
            "minimizer options initializer ABI version does not match");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *options = bg_minimizer_options_v1{};
        options->struct_size = static_cast<uint32_t>(sizeof(*options));
        options->abi_version = BG_ABI_VERSION;
        options->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        options->max_iterations = UINT64_C(1000);
        options->max_line_search_steps = UINT32_C(32);
        options->initial_step_angstrom2_mol_per_kcal = 1.0e-3;
        options->minimum_step_angstrom2_mol_per_kcal = 1.0e-12;
        options->energy_tolerance_kcal_per_mol = 1.0e-12;
        options->force_tolerance_kcal_per_mol_angstrom = 1.0e-6;
        options->armijo_coefficient = 1.0e-4;
        options->backtrack_factor = 0.5;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_minimization_report_v1_init(
    bg_minimization_report_v1 *report,
    std::size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            report,
            caller_struct_size,
            sizeof(bg_minimization_report_v1),
            caller_abi_version,
            "minimization report pointer is null",
            "minimization report initializer size does not match the native ABI",
            "minimization report initializer ABI version does not match");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *report = bg_minimization_report_v1{};
        report->struct_size = static_cast<uint32_t>(sizeof(*report));
        report->abi_version = BG_ABI_VERSION;
        report->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_dynamics_report_v1_init(
    bg_dynamics_report_v1 *report,
    std::size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            report,
            caller_struct_size,
            sizeof(bg_dynamics_report_v1),
            caller_abi_version,
            "dynamics report pointer is null",
            "dynamics report initializer size does not match the native ABI",
            "dynamics report initializer ABI version does not match");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *report = bg_dynamics_report_v1{};
        report->struct_size = static_cast<uint32_t>(sizeof(*report));
        report->abi_version = BG_ABI_VERSION;
        report->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_simulation_create(
    const bg_system *system,
    const bg_forcefield *forcefield,
    const bg_distance_constraints_v1 *constraints,
    const bg_simulation_options_v1 *options,
    bg_simulation **out_simulation) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::dynamics;
    if (out_simulation != nullptr) {
        *out_simulation = nullptr;
    }
    return guarded_status([&]() -> bg_status {
        if (out_simulation == nullptr) {
            return fail(BG_STATUS_INVALID_ARGUMENT, "out_simulation must not be null");
        }
        if (system == nullptr || forcefield == nullptr || options == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "system, forcefield, and simulation options must not be null");
        }
        bg_status status = validate_simulation_options(*options);
        if (status != BG_STATUS_OK) {
            return status;
        }
        if (constraints != nullptr) {
            status = validate_constraints_descriptor(*constraints);
            if (status != BG_STATUS_OK) {
                return status;
            }
        }
        if (system->unit_system != forcefield->unit_system ||
            system->unit_system != options->unit_system ||
            (constraints != nullptr &&
             system->unit_system != constraints->unit_system)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "simulation inputs must use the same canonical unit system");
        }
        const std::size_t atom_count = system->position_x.size();
        if (atom_count == 0 || forcefield->atom_count != atom_count ||
            system->position_y.size() != atom_count ||
            system->position_z.size() != atom_count ||
            system->velocity_x.size() != atom_count ||
            system->velocity_y.size() != atom_count ||
            system->velocity_z.size() != atom_count ||
            system->mass.size() != atom_count ||
            system->charge.size() != atom_count) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "system and forcefield atom storage must match and be non-empty");
        }

        std::size_t constraint_count = 0;
        if (constraints != nullptr) {
            status = checked_element_count(
                constraints->constraint_count,
                sizeof(bg_simulation::DistanceConstraint),
                "constraint_count exceeds native capacity",
                &constraint_count);
            if (status != BG_STATUS_OK) {
                return status;
            }
            if (constraint_count > 0 &&
                (constraints->atom_i == nullptr || constraints->atom_j == nullptr ||
                 constraints->distance_angstrom == nullptr)) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "non-empty constraints require all three input channels");
            }
            if (!pointer_is_aligned(constraints->atom_i) ||
                !pointer_is_aligned(constraints->atom_j) ||
                !pointer_is_aligned(constraints->distance_angstrom)) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "constraint channels must be naturally aligned");
            }
        }
        if (atom_count > static_cast<std::size_t>(UINT64_MAX / UINT64_C(3))) {
            return fail(BG_STATUS_CAPACITY_OVERFLOW, "dynamics degrees of freedom overflow");
        }
        const uint64_t unconstrained_dof =
            static_cast<uint64_t>(atom_count) * UINT64_C(3);
        if (static_cast<uint64_t>(constraint_count) >= unconstrained_dof) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "constraints must leave at least one degree of freedom");
        }

        auto simulation = std::make_unique<bg_simulation>();
        simulation->system = *system;
        simulation->forcefield = *forcefield;
        simulation->integrator = options->integrator;
        simulation->timestep_femtoseconds = options->timestep_femtoseconds;
        simulation->temperature_kelvin = options->temperature_kelvin;
        simulation->friction_per_femtosecond =
            options->friction_per_femtosecond;
        simulation->random_seed = options->random_seed;
        if (simulation->integrator == BG_INTEGRATOR_VELOCITY_VERLET) {
            simulation->temperature_kelvin = 0.0;
            simulation->friction_per_femtosecond = 0.0;
            simulation->random_seed = UINT64_C(0);
        }
        if (constraints != nullptr) {
            simulation->constraint_tolerance = constraints->tolerance_angstrom;
            simulation->constraint_velocity_tolerance =
                constraints->velocity_tolerance_angstrom_per_femtosecond;
            simulation->constraint_max_iterations = constraints->max_iterations;
            simulation->constraints.reserve(constraint_count);
            for (std::size_t row = 0; row < constraint_count; ++row) {
                const uint64_t observed_i = constraints->atom_i[row];
                const uint64_t observed_j = constraints->atom_j[row];
                const double distance = constraints->distance_angstrom[row];
                if (observed_i >= static_cast<uint64_t>(atom_count) ||
                    observed_j >= static_cast<uint64_t>(atom_count)) {
                    return fail(
                        BG_STATUS_INVALID_ARGUMENT,
                        "constraint atom index is out of range");
                }
                if (observed_i == observed_j) {
                    return fail(
                        BG_STATUS_INVALID_ARGUMENT,
                        "constraint atom indices must be distinct");
                }
                if (!std::isfinite(distance) || distance <= 0.0) {
                    return fail(
                        BG_STATUS_INVALID_ARGUMENT,
                        "constraint distances must be finite and positive");
                }
                constexpr std::array<uint32_t, 3> axis_bits = {
                    static_cast<uint32_t>(BG_PERIODIC_AXIS_X),
                    static_cast<uint32_t>(BG_PERIODIC_AXIS_Y),
                    static_cast<uint32_t>(BG_PERIODIC_AXIS_Z),
                };
                for (std::size_t axis = 0; axis < axis_bits.size(); ++axis) {
                    if ((forcefield->periodic_axes_mask & axis_bits[axis]) != 0U &&
                        distance >= 0.5 * forcefield->cell_lengths[axis]) {
                        return fail(
                            BG_STATUS_INVALID_ARGUMENT,
                            "constraint distance must be below half each periodic cell length");
                    }
                }
                const std::size_t atom_i = static_cast<std::size_t>(
                    std::min(observed_i, observed_j));
                const std::size_t atom_j = static_cast<std::size_t>(
                    std::max(observed_i, observed_j));
                simulation->constraints.push_back({atom_i, atom_j, distance});
            }
            std::sort(
                simulation->constraints.begin(),
                simulation->constraints.end(),
                [](const bg_simulation::DistanceConstraint &left,
                   const bg_simulation::DistanceConstraint &right) noexcept {
                    return left.atom_i < right.atom_i ||
                           (left.atom_i == right.atom_i &&
                            left.atom_j < right.atom_j);
                });
            const auto duplicate = std::adjacent_find(
                simulation->constraints.begin(),
                simulation->constraints.end(),
                [](const bg_simulation::DistanceConstraint &left,
                   const bg_simulation::DistanceConstraint &right) noexcept {
                    return left.atom_i == right.atom_i &&
                           left.atom_j == right.atom_j;
                });
            if (duplicate != simulation->constraints.end()) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "constraints contain a duplicate unordered atom pair");
            }
        } else {
            simulation->constraint_tolerance = 0.0;
            simulation->constraint_velocity_tolerance = 0.0;
            simulation->constraint_max_iterations = UINT32_C(0);
        }
        status = initialize_constraints(simulation.get());
        if (status != BG_STATUS_OK) {
            return status;
        }
        simulation->static_fingerprint = compute_static_fingerprint(*simulation);
        *out_simulation = simulation.release();
        return BG_STATUS_OK;
    });
}

extern "C" BG_API void BG_CALL bg_simulation_destroy(
    bg_simulation *simulation) BG_NOEXCEPT {
    delete simulation;
}

extern "C" BG_API bg_status BG_CALL bg_simulation_get_particles(
    const bg_simulation *simulation,
    bg_particle_soa_view *out_view) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::dynamics;
    return guarded_status([&]() -> bg_status {
        if (simulation == nullptr || out_view == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "simulation and particle view output must not be null");
        }
        const bg_status status = validate_particle_view(*out_view);
        if (status != BG_STATUS_OK) {
            return status;
        }
        fill_particle_view(simulation->system, out_view);
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_simulation_get_absolute_step(
    const bg_simulation *simulation,
    uint64_t *absolute_step) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        if (simulation == nullptr || absolute_step == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "simulation and absolute_step output must not be null");
        }
        *absolute_step = simulation->absolute_step;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_context_minimize(
    const bg_context *context,
    bg_simulation *simulation,
    const bg_minimizer_options_v1 *options,
    bg_minimization_report_v1 *out_report) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::dynamics;
    return guarded_status([&]() -> bg_status {
        if (context == nullptr || simulation == nullptr || options == nullptr ||
            out_report == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "context, simulation, minimizer options, and report must not be null");
        }
        bg_status status = validate_minimizer_options(*options);
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = validate_report(
            *out_report,
            "bg_minimization_report_v1 struct_size does not match ABI v1",
            "bg_minimization_report_v1 abi_version does not match the native library",
            "bg_minimization_report_v1 reserved fields must be zero");
        if (status != BG_STATUS_OK) {
            return status;
        }
        if (out_report->reserved1 != UINT32_C(0)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "bg_minimization_report_v1 reserved fields must be zero");
        }
        if (context->unit_system != simulation->system.unit_system ||
            options->unit_system != simulation->system.unit_system) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "context, simulation, and minimizer units must match");
        }
        DynamicStateRollback rollback(simulation, true);
        bg_minimization_report_v1 report = *out_report;
        status = minimize(*context, *options, simulation, &report);
        if (status != BG_STATUS_OK) {
            return status;
        }
        rollback.commit();
        *out_report = report;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_context_integrate(
    const bg_context *context,
    bg_simulation *simulation,
    uint64_t step_count,
    bg_dynamics_report_v1 *out_report) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::dynamics;
    return guarded_status([&]() -> bg_status {
        if (context == nullptr || simulation == nullptr || out_report == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "context, simulation, and dynamics report must not be null");
        }
        bg_status status = validate_report(
            *out_report,
            "bg_dynamics_report_v1 struct_size does not match ABI v1",
            "bg_dynamics_report_v1 abi_version does not match the native library",
            "bg_dynamics_report_v1 reserved fields must be zero");
        if (status != BG_STATUS_OK) {
            return status;
        }
        if (context->unit_system != simulation->system.unit_system) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "context and simulation units must match");
        }
        if (step_count > UINT64_MAX - simulation->absolute_step) {
            return fail(
                BG_STATUS_CAPACITY_OVERFLOW,
                "absolute dynamics step would overflow uint64");
        }
        DynamicStateRollback rollback(
            simulation, step_count != UINT64_C(0));
        bg_dynamics_report_v1 report = *out_report;
        status = integrate(*context, step_count, simulation, &report);
        if (status != BG_STATUS_OK) {
            return status;
        }
        rollback.commit();
        *out_report = report;
        return BG_STATUS_OK;
    });
}
