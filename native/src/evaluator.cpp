#include "cpu/evaluator.hpp"
#include "internal.hpp"

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <limits>

namespace betelgeuze::native {
namespace {

struct ByteRange final {
    std::uintptr_t begin = 0;
    std::uintptr_t end = 0;
};

bool make_byte_range(
    const void *pointer,
    std::size_t byte_count,
    ByteRange *out_range) noexcept {
    if (pointer == nullptr || out_range == nullptr) {
        return false;
    }
    const auto begin = reinterpret_cast<std::uintptr_t>(pointer);
    if (byte_count > std::numeric_limits<std::uintptr_t>::max() - begin) {
        return false;
    }
    *out_range = ByteRange{begin, begin + byte_count};
    return true;
}

bool ranges_overlap(const ByteRange &left, const ByteRange &right) noexcept {
    return left.begin < right.end && right.begin < left.end;
}

bg_status validate_energy_output(
    const bg_energy_components_v1 &energy) noexcept {
    bg_status status = validate_descriptor_header(
        energy.struct_size,
        sizeof(bg_energy_components_v1),
        energy.abi_version,
        "bg_energy_components_v1 struct_size does not match ABI v1",
        "bg_energy_components_v1 abi_version does not match the native library");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = validate_unit_system(energy.unit_system);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (energy.reserved0 != UINT32_C(0) ||
        !reserved_is_zero(energy.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "bg_energy_components_v1 reserved fields must be zero");
    }
    return BG_STATUS_OK;
}

bg_status validate_force_output(
    const bg_force_soa_v1 &forces,
    const bg_energy_components_v1 *energy,
    std::size_t atom_count) noexcept {
    bg_status status = validate_descriptor_header(
        forces.struct_size,
        sizeof(bg_force_soa_v1),
        forces.abi_version,
        "bg_force_soa_v1 struct_size does not match ABI v1",
        "bg_force_soa_v1 abi_version does not match the native library");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = validate_unit_system(forces.unit_system);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (forces.reserved0 != UINT32_C(0) ||
        !reserved_is_zero(forces.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "bg_force_soa_v1 reserved fields must be zero");
    }
    const uint64_t required = static_cast<uint64_t>(atom_count);
    if (forces.particle_capacity < required) {
        return fail(
            BG_STATUS_BUFFER_TOO_SMALL,
            "force output capacity is smaller than the system atom count");
    }
    if (atom_count > 0 &&
        (forces.x_kcal_per_mol_angstrom == nullptr ||
         forces.y_kcal_per_mol_angstrom == nullptr ||
         forces.z_kcal_per_mol_angstrom == nullptr)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "non-empty force output requires all three SoA channels");
    }
    if (!pointer_is_aligned(forces.x_kcal_per_mol_angstrom) ||
        !pointer_is_aligned(forces.y_kcal_per_mol_angstrom) ||
        !pointer_is_aligned(forces.z_kcal_per_mol_angstrom)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "force output channels must be naturally aligned");
    }

    const std::size_t channel_bytes = atom_count * sizeof(double);
    ByteRange x_range;
    ByteRange y_range;
    ByteRange z_range;
    ByteRange force_descriptor_range;
    ByteRange energy_descriptor_range;
    if (!make_byte_range(
            forces.x_kcal_per_mol_angstrom, channel_bytes, &x_range) ||
        !make_byte_range(
            forces.y_kcal_per_mol_angstrom, channel_bytes, &y_range) ||
        !make_byte_range(
            forces.z_kcal_per_mol_angstrom, channel_bytes, &z_range) ||
        !make_byte_range(&forces, sizeof(forces), &force_descriptor_range) ||
        !make_byte_range(
            energy, sizeof(bg_energy_components_v1), &energy_descriptor_range)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "force output byte ranges are not representable");
    }
    if (ranges_overlap(x_range, y_range) ||
        ranges_overlap(x_range, z_range) ||
        ranges_overlap(y_range, z_range) ||
        ranges_overlap(x_range, force_descriptor_range) ||
        ranges_overlap(y_range, force_descriptor_range) ||
        ranges_overlap(z_range, force_descriptor_range) ||
        ranges_overlap(x_range, energy_descriptor_range) ||
        ranges_overlap(y_range, energy_descriptor_range) ||
        ranges_overlap(z_range, energy_descriptor_range) ||
        ranges_overlap(force_descriptor_range, energy_descriptor_range)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "force output channels and output descriptors must not overlap");
    }
    return BG_STATUS_OK;
}

}  // namespace
}  // namespace betelgeuze::native

extern "C" BG_API bg_status BG_CALL bg_context_evaluate(
    const bg_context *context,
    const bg_system *system,
    const bg_forcefield *forcefield,
    bg_energy_components_v1 *out_energy,
    bg_force_soa_v1 *out_forces) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    return guarded_status([&]() -> bg_status {
        if (context == nullptr || system == nullptr || forcefield == nullptr ||
            out_energy == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "context, system, forcefield, and energy output must not be null");
        }
        bg_status status = validate_energy_output(*out_energy);
        if (status != BG_STATUS_OK) {
            return status;
        }
        if (out_forces != nullptr) {
            status = validate_force_output(
                *out_forces, out_energy, forcefield->atom_count);
            if (status != BG_STATUS_OK) {
                return status;
            }
        }
        if (context->unit_system != system->unit_system ||
            context->unit_system != forcefield->unit_system) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "context, system, and forcefield unit systems must match");
        }
        if (context->backend != BG_BACKEND_CPU) {
            return fail(
                BG_STATUS_UNSUPPORTED_BACKEND,
                "the selected backend has no evaluator implementation");
        }

        cpu::Evaluation evaluation;
        status = cpu::evaluate(
            *system, *forcefield, out_forces != nullptr, &evaluation);
        if (status != BG_STATUS_OK) {
            return status;
        }

        if (out_forces != nullptr) {
            std::copy(
                evaluation.force_x.begin(),
                evaluation.force_x.end(),
                out_forces->x_kcal_per_mol_angstrom);
            std::copy(
                evaluation.force_y.begin(),
                evaluation.force_y.end(),
                out_forces->y_kcal_per_mol_angstrom);
            std::copy(
                evaluation.force_z.begin(),
                evaluation.force_z.end(),
                out_forces->z_kcal_per_mol_angstrom);
            out_forces->particle_count =
                static_cast<uint64_t>(forcefield->atom_count);
        }
        *out_energy = evaluation.energy;
        return BG_STATUS_OK;
    });
}
