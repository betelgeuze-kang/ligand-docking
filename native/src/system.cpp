#include "internal.hpp"

#include <algorithm>
#include <memory>

namespace betelgeuze::native {
namespace {

bg_status validate_particle_descriptor(const bg_particle_soa &particles) noexcept {
    bg_status status = validate_descriptor_header(
        particles.struct_size,
        sizeof(bg_particle_soa),
        particles.abi_version,
        "bg_particle_soa struct_size does not match ABI v1",
        "bg_particle_soa abi_version does not match the native library");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = validate_unit_system(particles.unit_system);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (particles.reserved0 != UINT32_C(0) ||
        !reserved_is_zero(particles.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "bg_particle_soa reserved fields must be zero");
    }
    return BG_STATUS_OK;
}

bg_status validate_view_descriptor(const bg_particle_soa_view &view) noexcept {
    bg_status status = validate_descriptor_header(
        view.struct_size,
        sizeof(bg_particle_soa_view),
        view.abi_version,
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

bg_status validate_position_descriptor(const bg_position_soa &positions) noexcept {
    bg_status status = validate_descriptor_header(
        positions.struct_size,
        sizeof(bg_position_soa),
        positions.abi_version,
        "bg_position_soa struct_size does not match ABI v1",
        "bg_position_soa abi_version does not match the native library");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = validate_unit_system(positions.unit_system);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (positions.reserved0 != UINT32_C(0) ||
        !reserved_is_zero(positions.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "bg_position_soa reserved fields must be zero");
    }
    return BG_STATUS_OK;
}

bg_status validate_finite_particles(const bg_system &system) noexcept {
    if (!all_finite(system.position_x) || !all_finite(system.position_y) ||
        !all_finite(system.position_z)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "particle positions must contain only finite values");
    }
    if (!all_finite(system.velocity_x) || !all_finite(system.velocity_y) ||
        !all_finite(system.velocity_z)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "particle velocities must contain only finite values");
    }
    if (!all_positive_finite(system.mass)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "particle masses must be finite and strictly positive");
    }
    if (!all_finite(system.charge)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "particle charges must contain only finite values");
    }
    return BG_STATUS_OK;
}

}  // namespace
}  // namespace betelgeuze::native

extern "C" BG_API bg_status BG_CALL bg_system_create(
    const bg_particle_soa *particles,
    bg_system **out_system) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    if (out_system != nullptr) {
        *out_system = nullptr;
    }
    return guarded_status([&]() -> bg_status {
        if (out_system == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "out_system must not be null");
        }
        if (particles == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "bg_particle_soa must not be null");
        }
        bg_status status = validate_particle_descriptor(*particles);
        if (status != BG_STATUS_OK) {
            return status;
        }

        std::size_t count = 0;
        status = checked_particle_count(particles->particle_count, &count);
        if (status != BG_STATUS_OK) {
            return status;
        }

        if (count > 0 &&
            (particles->position_x_angstrom == nullptr ||
             particles->position_y_angstrom == nullptr ||
             particles->position_z_angstrom == nullptr ||
             particles->mass_dalton == nullptr ||
             particles->charge_elementary == nullptr)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "non-empty particles require position, mass, and charge channels");
        }
        const bool velocity_x_present =
            particles->velocity_x_angstrom_per_femtosecond != nullptr;
        const bool velocity_y_present =
            particles->velocity_y_angstrom_per_femtosecond != nullptr;
        const bool velocity_z_present =
            particles->velocity_z_angstrom_per_femtosecond != nullptr;
        if (!(velocity_x_present == velocity_y_present &&
              velocity_y_present == velocity_z_present)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "velocity channels must be either all null or all non-null");
        }
        if (!double_pointer_is_aligned(particles->position_x_angstrom) ||
            !double_pointer_is_aligned(particles->position_y_angstrom) ||
            !double_pointer_is_aligned(particles->position_z_angstrom) ||
            !double_pointer_is_aligned(
                particles->velocity_x_angstrom_per_femtosecond) ||
            !double_pointer_is_aligned(
                particles->velocity_y_angstrom_per_femtosecond) ||
            !double_pointer_is_aligned(
                particles->velocity_z_angstrom_per_femtosecond) ||
            !double_pointer_is_aligned(particles->mass_dalton) ||
            !double_pointer_is_aligned(particles->charge_elementary)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "particle channels must be aligned for double access");
        }

        auto system = std::make_unique<bg_system>();
        system->unit_system = particles->unit_system;
        system->position_x = copy_channel(particles->position_x_angstrom, count);
        system->position_y = copy_channel(particles->position_y_angstrom, count);
        system->position_z = copy_channel(particles->position_z_angstrom, count);
        if (velocity_x_present) {
            system->velocity_x = copy_channel(
                particles->velocity_x_angstrom_per_femtosecond, count);
            system->velocity_y = copy_channel(
                particles->velocity_y_angstrom_per_femtosecond, count);
            system->velocity_z = copy_channel(
                particles->velocity_z_angstrom_per_femtosecond, count);
        } else {
            system->velocity_x.assign(count, 0.0);
            system->velocity_y.assign(count, 0.0);
            system->velocity_z.assign(count, 0.0);
        }
        system->mass = copy_channel(particles->mass_dalton, count);
        system->charge = copy_channel(particles->charge_elementary, count);

        status = validate_finite_particles(*system);
        if (status != BG_STATUS_OK) {
            return status;
        }
        *out_system = system.release();
        return BG_STATUS_OK;
    });
}

extern "C" BG_API void BG_CALL bg_system_destroy(
    bg_system *system) BG_NOEXCEPT {
    delete system;
}

extern "C" BG_API bg_status BG_CALL bg_system_get_particle_count(
    const bg_system *system,
    uint64_t *particle_count) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        if (system == nullptr || particle_count == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "system and particle_count output must not be null");
        }
        *particle_count = static_cast<uint64_t>(system->position_x.size());
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_system_get_unit_system(
    const bg_system *system,
    bg_unit_system *unit_system) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        if (system == nullptr || unit_system == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "system and unit_system output must not be null");
        }
        *unit_system = system->unit_system;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_system_get_particles(
    const bg_system *system,
    bg_particle_soa_view *out_view) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        if (system == nullptr || out_view == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "system and particle view output must not be null");
        }
        bg_status status = validate_view_descriptor(*out_view);
        if (status != BG_STATUS_OK) {
            return status;
        }

        out_view->struct_size =
            static_cast<uint32_t>(sizeof(bg_particle_soa_view));
        out_view->abi_version = BG_ABI_VERSION;
        out_view->particle_count =
            static_cast<uint64_t>(system->position_x.size());
        out_view->unit_system = system->unit_system;
        out_view->reserved0 = UINT32_C(0);
        out_view->position_x_angstrom = borrowed_data(system->position_x);
        out_view->position_y_angstrom = borrowed_data(system->position_y);
        out_view->position_z_angstrom = borrowed_data(system->position_z);
        out_view->velocity_x_angstrom_per_femtosecond =
            borrowed_data(system->velocity_x);
        out_view->velocity_y_angstrom_per_femtosecond =
            borrowed_data(system->velocity_y);
        out_view->velocity_z_angstrom_per_femtosecond =
            borrowed_data(system->velocity_z);
        out_view->mass_dalton = borrowed_data(system->mass);
        out_view->charge_elementary = borrowed_data(system->charge);
        for (uint64_t &value : out_view->reserved) {
            value = UINT64_C(0);
        }
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_system_set_positions(
    bg_system *system,
    const bg_position_soa *positions) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        if (system == nullptr || positions == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "system and position descriptor must not be null");
        }
        bg_status status = validate_position_descriptor(*positions);
        if (status != BG_STATUS_OK) {
            return status;
        }
        if (positions->unit_system != system->unit_system) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "position unit_system does not match the system");
        }
        if (positions->particle_count !=
            static_cast<uint64_t>(system->position_x.size())) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "position particle_count does not match the system");
        }

        const std::size_t count = system->position_x.size();
        if (count > 0 &&
            (positions->x_angstrom == nullptr ||
             positions->y_angstrom == nullptr ||
             positions->z_angstrom == nullptr)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "non-empty position replacement requires x, y, and z channels");
        }
        if (!double_pointer_is_aligned(positions->x_angstrom) ||
            !double_pointer_is_aligned(positions->y_angstrom) ||
            !double_pointer_is_aligned(positions->z_angstrom)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "position channels must be aligned for double access");
        }

        std::vector<double> position_x =
            copy_channel(positions->x_angstrom, count);
        std::vector<double> position_y =
            copy_channel(positions->y_angstrom, count);
        std::vector<double> position_z =
            copy_channel(positions->z_angstrom, count);
        if (!all_finite(position_x) || !all_finite(position_y) ||
            !all_finite(position_z)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "replacement positions must contain only finite values");
        }

        /* Preserve addresses previously returned by bg_system_get_particles.
         * All allocations and validation completed above, and assigning
         * doubles into equal-sized owned channels is non-throwing. */
        std::copy(position_x.begin(), position_x.end(), system->position_x.begin());
        std::copy(position_y.begin(), position_y.end(), system->position_y.begin());
        std::copy(position_z.begin(), position_z.end(), system->position_z.begin());
        return BG_STATUS_OK;
    });
}
