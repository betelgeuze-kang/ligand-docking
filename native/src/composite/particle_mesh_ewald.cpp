#if !defined(BG_DISABLE_DESCRIPTOR_INIT_CONVENIENCE_MACROS)
#  define BG_DISABLE_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#endif
#if !defined(BG_DISABLE_DIRECT_EWALD_DESCRIPTOR_INIT_CONVENIENCE_MACROS)
#  define BG_DISABLE_DIRECT_EWALD_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#endif
#if !defined(BG_DISABLE_PARTICLE_MESH_RECIPROCAL_DESCRIPTOR_INIT_CONVENIENCE_MACROS)
#  define BG_DISABLE_PARTICLE_MESH_RECIPROCAL_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#endif
#if !defined(BG_DISABLE_PARTICLE_MESH_EWALD_DESCRIPTOR_INIT_CONVENIENCE_MACROS)
#  define BG_DISABLE_PARTICLE_MESH_EWALD_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#endif
#include "betelgeuze/particle_mesh_ewald.h"

#include "../ewald/cpp_evaluator.hpp"
#include "../ewald/model.hpp"
#include "../ewald/rust_evaluator.hpp"
#include "../internal.hpp"
#include "../particle_mesh_reciprocal/cpp_evaluator.hpp"
#include "../particle_mesh_reciprocal/model.hpp"
#include "../particle_mesh_reciprocal/rust_evaluator.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace betelgeuze::native::particle_mesh_ewald {
namespace {

constexpr const char *kProfileId =
    "betelgeuze.native_particle_mesh_ewald/1.0.0";

struct ByteRange final {
    std::uintptr_t begin = 0U;
    std::uintptr_t end = 0U;
};

struct Evaluation final {
    double real_space = 0.0;
    double reciprocal_space = 0.0;
    double self = 0.0;
    double pair_correction = 0.0;
    double total = 0.0;
    std::vector<std::array<double, 3>> forces;
};

bool make_byte_range(
    const void *pointer,
    std::size_t byte_count,
    ByteRange *out_range) noexcept {
    if (pointer == nullptr || out_range == nullptr) {
        return false;
    }
    const std::uintptr_t begin = reinterpret_cast<std::uintptr_t>(pointer);
    if (byte_count > std::numeric_limits<std::uintptr_t>::max() - begin) {
        return false;
    }
    *out_range = {begin, begin + byte_count};
    return true;
}

bool ranges_overlap(const ByteRange &left, const ByteRange &right) noexcept {
    return left.begin < right.end && right.begin < left.end;
}

bg_status append_disjoint_range(
    const void *pointer,
    std::size_t byte_count,
    std::array<ByteRange, 20> *ranges,
    std::size_t *range_count,
    const char *detail) noexcept {
    if (pointer == nullptr || ranges == nullptr || range_count == nullptr ||
        *range_count >= ranges->size()) {
        return fail(BG_STATUS_INVALID_ARGUMENT, detail);
    }
    ByteRange candidate;
    if (!make_byte_range(pointer, byte_count, &candidate)) {
        return fail(BG_STATUS_INVALID_ARGUMENT, detail);
    }
    for (std::size_t index = 0U; index < *range_count; ++index) {
        if (ranges_overlap(candidate, (*ranges)[index])) {
            return fail(BG_STATUS_INVALID_ARGUMENT, detail);
        }
    }
    (*ranges)[(*range_count)++] = candidate;
    return BG_STATUS_OK;
}

bg_status validate_header(
    std::uint32_t observed_size,
    std::size_t expected_size,
    std::uint32_t observed_version,
    const char *name) {
    if (expected_size > std::numeric_limits<std::uint32_t>::max() ||
        observed_size != static_cast<std::uint32_t>(expected_size)) {
        const std::string detail = std::string(name) +
            " struct_size does not match particle-mesh Ewald ABI 1.0";
        return fail(BG_STATUS_ABI_MISMATCH, detail.c_str());
    }
    if (observed_version != BG_PARTICLE_MESH_EWALD_ABI_VERSION) {
        const std::string detail = std::string(name) +
            " abi_version does not match particle-mesh Ewald ABI 1.0";
        return fail(BG_STATUS_ABI_MISMATCH, detail.c_str());
    }
    return BG_STATUS_OK;
}

bg_status validate_initializer(
    const void *descriptor,
    std::size_t caller_size,
    std::size_t native_size,
    std::uint32_t caller_version,
    const char *name) {
    if (descriptor == nullptr) {
        const std::string detail = std::string(name) +
            " pointer must not be null";
        return fail(BG_STATUS_INVALID_ARGUMENT, detail.c_str());
    }
    if (caller_size != native_size ||
        native_size > std::numeric_limits<std::uint32_t>::max()) {
        const std::string detail = std::string(name) +
            " initializer size does not match particle-mesh Ewald ABI 1.0";
        return fail(BG_STATUS_ABI_MISMATCH, detail.c_str());
    }
    if (caller_version != BG_PARTICLE_MESH_EWALD_ABI_VERSION) {
        const std::string detail = std::string(name) +
            " initializer version does not match particle-mesh Ewald ABI 1.0";
        return fail(BG_STATUS_ABI_MISMATCH, detail.c_str());
    }
    return BG_STATUS_OK;
}

bg_status validate_error_descriptor(const bg_direct_ewald_error_v1 &error) {
    if (error.struct_size !=
            static_cast<std::uint32_t>(sizeof(bg_direct_ewald_error_v1)) ||
        error.abi_version != BG_DIRECT_EWALD_ABI_VERSION) {
        return fail(
            BG_STATUS_ABI_MISMATCH,
            "particle-mesh Ewald typed error does not match direct-Ewald ABI 1.0");
    }
    if (error.reserved0 != UINT32_C(0) ||
        !reserved_is_zero(error.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "particle-mesh Ewald typed-error reserved fields must be zero");
    }
    return BG_STATUS_OK;
}

void clear_error(bg_direct_ewald_error_v1 *error) noexcept {
    error->code = BG_DIRECT_EWALD_ERROR_NONE;
    std::fill_n(
        error->detail,
        static_cast<std::size_t>(BG_DIRECT_EWALD_ERROR_DETAIL_CAPACITY),
        '\0');
}

void commit_error(
    bg_direct_ewald_error_v1 *error,
    bg_direct_ewald_error_code code,
    std::string_view detail) noexcept {
    error->code = code;
    const std::size_t capacity =
        static_cast<std::size_t>(BG_DIRECT_EWALD_ERROR_DETAIL_CAPACITY);
    const std::size_t length = std::min(capacity - 1U, detail.size());
    std::fill_n(error->detail, capacity, '\0');
    if (length > 0U) {
        std::memcpy(error->detail, detail.data(), length);
    }
    set_last_error(error->detail);
}

bg_status status_for_direct_error(
    bg_direct_ewald_error_code code) noexcept {
    if (code == BG_DIRECT_EWALD_ERROR_CAPACITY_EXCEEDED) {
        return BG_STATUS_CAPACITY_OVERFLOW;
    }
    switch (code) {
        case BG_DIRECT_EWALD_ERROR_DAMPING_UNDERFLOW:
        case BG_DIRECT_EWALD_ERROR_PHASE_UNDERFLOW:
        case BG_DIRECT_EWALD_ERROR_NONFINITE_RESULT:
        case BG_DIRECT_EWALD_ERROR_AMBIGUOUS_PAIR_CORRECTION_IMAGE:
        case BG_DIRECT_EWALD_ERROR_AMBIGUOUS_REAL_SPACE_CUTOFF:
        case BG_DIRECT_EWALD_ERROR_AMBIGUOUS_MINIMUM_PAIR_DISTANCE:
        case BG_DIRECT_EWALD_ERROR_PAIR_BELOW_MINIMUM_DISTANCE:
        case BG_DIRECT_EWALD_ERROR_NON_NEUTRAL_SYSTEM:
            return BG_STATUS_NUMERICAL_ERROR;
        default:
            return BG_STATUS_INVALID_ARGUMENT;
    }
}

bool map_reciprocal_error(
    bg_particle_mesh_reciprocal_error_code source,
    bg_direct_ewald_error_code *destination) noexcept {
    if (destination == nullptr) {
        return false;
    }
    switch (source) {
        case BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONE:
            *destination = BG_DIRECT_EWALD_ERROR_NONE;
            return true;
        case BG_PARTICLE_MESH_RECIPROCAL_ERROR_EMPTY_SYSTEM:
            *destination = BG_DIRECT_EWALD_ERROR_EMPTY_SYSTEM;
            return true;
        case BG_PARTICLE_MESH_RECIPROCAL_ERROR_CAPACITY_EXCEEDED:
            *destination = BG_DIRECT_EWALD_ERROR_CAPACITY_EXCEEDED;
            return true;
        case BG_PARTICLE_MESH_RECIPROCAL_ERROR_CHARGE_COUNT_MISMATCH:
            *destination = BG_DIRECT_EWALD_ERROR_CHARGE_COUNT_MISMATCH;
            return true;
        case BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONFINITE_COORDINATE:
            *destination = BG_DIRECT_EWALD_ERROR_NONFINITE_COORDINATE;
            return true;
        case BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONFINITE_CHARGE:
            *destination = BG_DIRECT_EWALD_ERROR_NONFINITE_CHARGE;
            return true;
        case BG_PARTICLE_MESH_RECIPROCAL_ERROR_NON_NEUTRAL_SYSTEM:
            *destination = BG_DIRECT_EWALD_ERROR_NON_NEUTRAL_SYSTEM;
            return true;
        case BG_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_CELL:
            *destination = BG_DIRECT_EWALD_ERROR_INVALID_CELL;
            return true;
        case BG_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_PARAMETER:
        case BG_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_MESH:
            *destination = BG_DIRECT_EWALD_ERROR_INVALID_PARAMETER;
            return true;
        case BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONFINITE_RESULT:
            *destination = BG_DIRECT_EWALD_ERROR_NONFINITE_RESULT;
            return true;
        default:
            return false;
    }
}

bg_status validate_energy_output(
    const bg_particle_mesh_ewald_energy_components_v1 &energy) {
    static_assert(sizeof(bg_particle_mesh_ewald_energy_components_v1) == 88U);
    bg_status status = validate_header(
        energy.struct_size, sizeof(energy), energy.abi_version,
        "bg_particle_mesh_ewald_energy_components_v1");
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
            "particle-mesh Ewald energy reserved fields must be zero");
    }
    return BG_STATUS_OK;
}

bg_status validate_force_output(
    const bg_particle_mesh_ewald_force_soa_v1 &forces,
    std::size_t atom_count) {
    static_assert(sizeof(bg_particle_mesh_ewald_force_soa_v1) == 88U);
    bg_status status = validate_header(
        forces.struct_size, sizeof(forces), forces.abi_version,
        "bg_particle_mesh_ewald_force_soa_v1");
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
            "particle-mesh Ewald force reserved fields must be zero");
    }
    const std::uint64_t maximum_capacity = static_cast<std::uint64_t>(
        std::numeric_limits<std::size_t>::max() / sizeof(double));
    if (forces.atom_capacity > maximum_capacity) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "particle-mesh Ewald force byte span exceeds addressable size");
    }
    if (forces.atom_capacity < static_cast<std::uint64_t>(atom_count)) {
        return fail(
            BG_STATUS_BUFFER_TOO_SMALL,
            "particle-mesh Ewald force capacity is smaller than atom count");
    }
    if (atom_count > 0U &&
        (forces.x_kcal_per_mol_angstrom == nullptr ||
         forces.y_kcal_per_mol_angstrom == nullptr ||
         forces.z_kcal_per_mol_angstrom == nullptr)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "non-empty particle-mesh Ewald force output requires three channels");
    }
    if (!pointer_is_aligned(forces.x_kcal_per_mol_angstrom) ||
        !pointer_is_aligned(forces.y_kcal_per_mol_angstrom) ||
        !pointer_is_aligned(forces.z_kcal_per_mol_angstrom)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "particle-mesh Ewald force channels must be naturally aligned");
    }
    return BG_STATUS_OK;
}

bg_status validate_evaluation_overlap(
    const bg_context *context,
    const bg_system *system,
    const bg_direct_ewald_model_v1 *direct_model,
    const bg_particle_mesh_reciprocal_model_v1 *reciprocal_model,
    const bg_particle_mesh_ewald_energy_components_v1 *energy,
    const bg_particle_mesh_ewald_force_soa_v1 *forces,
    const bg_direct_ewald_error_v1 *error) noexcept {
    constexpr const char *detail =
        "particle-mesh Ewald borrowed inputs, outputs, and descriptors must not overlap";
    std::array<ByteRange, 20> ranges{};
    std::size_t range_count = 0U;
    const auto append = [&](const void *pointer, std::size_t byte_count) {
        return append_disjoint_range(
            pointer, byte_count, &ranges, &range_count, detail);
    };
    bg_status status = append(context, sizeof(*context));
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = append(system, sizeof(*system));
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = append(direct_model, sizeof(*direct_model));
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = append(reciprocal_model, sizeof(*reciprocal_model));
    if (status != BG_STATUS_OK) {
        return status;
    }
    const std::array<const std::vector<double> *, 8> system_channels{{
        &system->position_x, &system->position_y, &system->position_z,
        &system->velocity_x, &system->velocity_y, &system->velocity_z,
        &system->mass, &system->charge,
    }};
    for (const std::vector<double> *channel : system_channels) {
        if (channel->empty()) {
            continue;
        }
        if (channel->size() >
            std::numeric_limits<std::size_t>::max() / sizeof(double)) {
            return fail(BG_STATUS_INVALID_ARGUMENT, detail);
        }
        status = append(channel->data(), channel->size() * sizeof(double));
        if (status != BG_STATUS_OK) {
            return status;
        }
    }
    if (!direct_model->pair_rules.empty()) {
        if (direct_model->pair_rules.size() >
            std::numeric_limits<std::size_t>::max() /
                sizeof(direct_model->pair_rules[0])) {
            return fail(BG_STATUS_INVALID_ARGUMENT, detail);
        }
        status = append(
            direct_model->pair_rules.data(),
            direct_model->pair_rules.size() *
                sizeof(direct_model->pair_rules[0]));
        if (status != BG_STATUS_OK) {
            return status;
        }
    }
    status = append(error, sizeof(*error));
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = append(energy, sizeof(*energy));
    if (status != BG_STATUS_OK || forces == nullptr) {
        return status;
    }
    status = append(forces, sizeof(*forces));
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (direct_model->atom_count >
        std::numeric_limits<std::size_t>::max() / sizeof(double)) {
        return fail(BG_STATUS_INVALID_ARGUMENT, detail);
    }
    const std::size_t force_bytes = direct_model->atom_count * sizeof(double);
    if (force_bytes == 0U) {
        return BG_STATUS_OK;
    }
    const std::array<const double *, 3> force_channels{{
        forces->x_kcal_per_mol_angstrom,
        forces->y_kcal_per_mol_angstrom,
        forces->z_kcal_per_mol_angstrom,
    }};
    for (const double *channel : force_channels) {
        status = append(channel, force_bytes);
        if (status != BG_STATUS_OK) {
            return status;
        }
    }
    return BG_STATUS_OK;
}

bg_status require_disjoint_from_error(
    const void *pointer,
    std::size_t byte_count,
    const ByteRange &error_range,
    const char *detail) noexcept {
    if (pointer == nullptr || byte_count == 0U) {
        return BG_STATUS_OK;
    }
    ByteRange candidate;
    if (!make_byte_range(pointer, byte_count, &candidate) ||
        ranges_overlap(candidate, error_range)) {
        return fail(BG_STATUS_INVALID_ARGUMENT, detail);
    }
    return BG_STATUS_OK;
}

bg_status validate_required_null_error_write_safety(
    const bg_context *context,
    const bg_system *system,
    const bg_direct_ewald_model_v1 *direct_model,
    const bg_particle_mesh_reciprocal_model_v1 *reciprocal_model,
    const bg_particle_mesh_ewald_energy_components_v1 *energy,
    const bg_particle_mesh_ewald_force_soa_v1 *forces,
    const bg_direct_ewald_error_v1 *error) noexcept {
    constexpr const char *detail =
        "particle-mesh Ewald typed error must not overlap borrowed or output storage";
    ByteRange error_range;
    if (!make_byte_range(error, sizeof(*error), &error_range)) {
        return fail(BG_STATUS_INVALID_ARGUMENT, detail);
    }
    const std::array<std::pair<const void *, std::size_t>, 6> fixed{{
        {context, context == nullptr ? 0U : sizeof(*context)},
        {system, system == nullptr ? 0U : sizeof(*system)},
        {direct_model,
         direct_model == nullptr ? 0U : sizeof(*direct_model)},
        {reciprocal_model,
         reciprocal_model == nullptr ? 0U : sizeof(*reciprocal_model)},
        {energy, energy == nullptr ? 0U : sizeof(*energy)},
        {forces, forces == nullptr ? 0U : sizeof(*forces)},
    }};
    for (const auto &range : fixed) {
        const bg_status status = require_disjoint_from_error(
            range.first, range.second, error_range, detail);
        if (status != BG_STATUS_OK) {
            return status;
        }
    }
    if (system != nullptr) {
        const std::array<const std::vector<double> *, 8> channels{{
            &system->position_x, &system->position_y, &system->position_z,
            &system->velocity_x, &system->velocity_y, &system->velocity_z,
            &system->mass, &system->charge,
        }};
        for (const std::vector<double> *channel : channels) {
            if (channel->size() >
                std::numeric_limits<std::size_t>::max() / sizeof(double)) {
                return fail(BG_STATUS_INVALID_ARGUMENT, detail);
            }
            const bg_status status = require_disjoint_from_error(
                channel->data(), channel->size() * sizeof(double),
                error_range, detail);
            if (status != BG_STATUS_OK) {
                return status;
            }
        }
    }
    if (direct_model != nullptr && !direct_model->pair_rules.empty()) {
        if (direct_model->pair_rules.size() >
            std::numeric_limits<std::size_t>::max() /
                sizeof(direct_model->pair_rules[0])) {
            return fail(BG_STATUS_INVALID_ARGUMENT, detail);
        }
        const bg_status status = require_disjoint_from_error(
            direct_model->pair_rules.data(),
            direct_model->pair_rules.size() *
                sizeof(direct_model->pair_rules[0]),
            error_range, detail);
        if (status != BG_STATUS_OK) {
            return status;
        }
    }
    if (forces != nullptr) {
        if (forces->atom_capacity > static_cast<std::uint64_t>(
                std::numeric_limits<std::size_t>::max() / sizeof(double))) {
            return fail(BG_STATUS_INVALID_ARGUMENT, detail);
        }
        const std::size_t bytes =
            static_cast<std::size_t>(forces->atom_capacity) * sizeof(double);
        const std::array<const double *, 3> channels{{
            forces->x_kcal_per_mol_angstrom,
            forces->y_kcal_per_mol_angstrom,
            forces->z_kcal_per_mol_angstrom,
        }};
        for (const double *channel : channels) {
            const bg_status status = require_disjoint_from_error(
                channel, bytes, error_range, detail);
            if (status != BG_STATUS_OK) {
                return status;
            }
        }
    }
    return BG_STATUS_OK;
}

bool double_bits_equal(double left, double right) noexcept {
    std::uint64_t left_bits = 0U;
    std::uint64_t right_bits = 0U;
    std::memcpy(&left_bits, &left, sizeof(left_bits));
    std::memcpy(&right_bits, &right, sizeof(right_bits));
    return left_bits == right_bits;
}

bg_status validate_compatibility(
    const bg_context &context,
    const bg_system &system,
    const bg_direct_ewald_model_v1 &direct_model,
    const bg_particle_mesh_reciprocal_model_v1 &reciprocal_model,
    const bg_particle_mesh_ewald_energy_components_v1 &energy,
    const bg_particle_mesh_ewald_force_soa_v1 *forces) {
    if (context.unit_system != system.unit_system ||
        context.unit_system != direct_model.unit_system ||
        context.unit_system != reciprocal_model.unit_system ||
        context.unit_system != energy.unit_system ||
        (forces != nullptr && context.unit_system != forces->unit_system)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "particle-mesh Ewald context, system, models, and outputs must use matching units");
    }
    const std::size_t atom_count = system.position_x.size();
    if (system.position_y.size() != atom_count ||
        system.position_z.size() != atom_count ||
        system.charge.size() != atom_count ||
        direct_model.atom_count != atom_count ||
        reciprocal_model.atom_count != atom_count) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "particle-mesh Ewald system and model atom counts must match exactly");
    }
    for (std::size_t axis = 0U; axis < 3U; ++axis) {
        if (!double_bits_equal(
                direct_model.cell_lengths_angstrom[axis],
                reciprocal_model.cell_lengths_angstrom[axis])) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "particle-mesh Ewald model cell-length bits must match exactly");
        }
    }
    if (!double_bits_equal(
            direct_model.alpha_per_angstrom,
            reciprocal_model.alpha_per_angstrom) ||
        !double_bits_equal(
            direct_model.dielectric, reciprocal_model.dielectric)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "particle-mesh Ewald model alpha and dielectric bits must match exactly");
    }
    return BG_STATUS_OK;
}

bool direct_parent_is_valid(
    const ewald::Evaluation &evaluation,
    const ewald::Error &error,
    bool compute_forces,
    std::size_t atom_count) noexcept {
    const std::array<double, 5> energies{{
        evaluation.energy.real_space,
        evaluation.energy.reciprocal_space,
        evaluation.energy.self,
        evaluation.energy.pair_correction,
        evaluation.energy.total(),
    }};
    if (error.code != BG_DIRECT_EWALD_ERROR_NONE ||
        !error.detail.empty() || evaluation.energy.reciprocal_space != 0.0 ||
        std::any_of(energies.begin(), energies.end(), [](double value) {
            return !std::isfinite(value);
        }) ||
        evaluation.forces.size() != (compute_forces ? atom_count : 0U)) {
        return false;
    }
    for (const auto &force : evaluation.forces) {
        if (std::any_of(force.begin(), force.end(), [](double value) {
                return !std::isfinite(value);
            })) {
            return false;
        }
    }
    return true;
}

bool reciprocal_parent_is_valid(
    const particle_mesh_reciprocal::Evaluation &evaluation,
    const particle_mesh_reciprocal::Error &error,
    bool compute_forces,
    std::size_t atom_count) noexcept {
    if (error.code != BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONE ||
        !error.detail.empty() ||
        !std::isfinite(evaluation.reciprocal_space_kcal_per_mol) ||
        evaluation.forces.size() != (compute_forces ? atom_count : 0U)) {
        return false;
    }
    for (const auto &force : evaluation.forces) {
        if (std::any_of(force.begin(), force.end(), [](double value) {
                return !std::isfinite(value);
            })) {
            return false;
        }
    }
    return true;
}

bg_status evaluate_parents(
    bg_backend lane,
    const bg_system &system,
    const bg_direct_ewald_model_v1 &direct_model,
    const bg_particle_mesh_reciprocal_model_v1 &reciprocal_model,
    bool compute_forces,
    Evaluation *out_evaluation,
    bg_direct_ewald_error_v1 *out_error) {
    bg_direct_ewald_model_v1 local_model = direct_model;
    local_model.reciprocal_max_indices = {{0, 0, 0}};

    ewald::Evaluation direct_evaluation;
    ewald::Error direct_error;
    bg_status status = BG_STATUS_INTERNAL_ERROR;
    if (lane == BG_BACKEND_CPP_CPU_REFERENCE) {
        status = ewald::cpp_cpu::evaluate(
            system, local_model, compute_forces, &direct_evaluation,
            &direct_error);
    } else {
        status = ewald::rust_cpu::evaluate(
            system, local_model, compute_forces, &direct_evaluation,
            &direct_error);
    }
    if (status != BG_STATUS_OK) {
        if (direct_error.code != BG_DIRECT_EWALD_ERROR_NONE) {
            commit_error(
                out_error, direct_error.code,
                std::string_view{
                    direct_error.detail.data(), direct_error.detail.size()});
            return status_for_direct_error(direct_error.code);
        }
        return status;
    }
    const std::size_t atom_count = direct_model.atom_count;
    if (!direct_parent_is_valid(
            direct_evaluation, direct_error, compute_forces, atom_count)) {
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "particle-mesh Ewald direct parent returned inconsistent energy, forces, or error state");
    }

    particle_mesh_reciprocal::Evaluation reciprocal_evaluation;
    particle_mesh_reciprocal::Error reciprocal_error;
    if (lane == BG_BACKEND_CPP_CPU_REFERENCE) {
        status = particle_mesh_reciprocal::cpp_cpu::evaluate(
            system, reciprocal_model, compute_forces,
            &reciprocal_evaluation, &reciprocal_error);
    } else {
        status = particle_mesh_reciprocal::rust_cpu::evaluate(
            system, reciprocal_model, compute_forces,
            &reciprocal_evaluation, &reciprocal_error);
    }
    if (status != BG_STATUS_OK) {
        if (reciprocal_error.code !=
            BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONE) {
            bg_direct_ewald_error_code mapped = BG_DIRECT_EWALD_ERROR_NONE;
            if (!map_reciprocal_error(reciprocal_error.code, &mapped) ||
                mapped == BG_DIRECT_EWALD_ERROR_NONE) {
                return fail(
                    BG_STATUS_INTERNAL_ERROR,
                    "particle-mesh Ewald reciprocal parent returned an unknown typed error");
            }
            commit_error(
                out_error, mapped,
                std::string_view{
                    reciprocal_error.detail.data(),
                    reciprocal_error.detail.size()});
            return status_for_direct_error(mapped);
        }
        return status;
    }
    if (!reciprocal_parent_is_valid(
            reciprocal_evaluation, reciprocal_error, compute_forces,
            atom_count)) {
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "particle-mesh Ewald reciprocal parent returned inconsistent energy, forces, or error state");
    }

    Evaluation candidate;
    candidate.real_space = direct_evaluation.energy.real_space;
    candidate.reciprocal_space =
        reciprocal_evaluation.reciprocal_space_kcal_per_mol;
    candidate.self = direct_evaluation.energy.self;
    candidate.pair_correction = direct_evaluation.energy.pair_correction;
    candidate.total =
        ((candidate.real_space + candidate.reciprocal_space) +
         candidate.self) +
        candidate.pair_correction;
    if (!std::isfinite(candidate.total)) {
        commit_error(
            out_error, BG_DIRECT_EWALD_ERROR_NONFINITE_RESULT,
            "particle-mesh Ewald total energy is not finite");
        return BG_STATUS_NUMERICAL_ERROR;
    }
    if (compute_forces) {
        candidate.forces.resize(atom_count);
        for (std::size_t atom = 0U; atom < atom_count; ++atom) {
            for (std::size_t axis = 0U; axis < 3U; ++axis) {
                candidate.forces[atom][axis] =
                    direct_evaluation.forces[atom][axis] +
                    reciprocal_evaluation.forces[atom][axis];
                if (!std::isfinite(candidate.forces[atom][axis])) {
                    commit_error(
                        out_error, BG_DIRECT_EWALD_ERROR_NONFINITE_RESULT,
                        "particle-mesh Ewald force is not finite");
                    return BG_STATUS_NUMERICAL_ERROR;
                }
            }
        }
    }
    *out_evaluation = std::move(candidate);
    return BG_STATUS_OK;
}

}  // namespace
}  // namespace betelgeuze::native::particle_mesh_ewald

extern "C" BG_API std::uint32_t BG_CALL
bg_particle_mesh_ewald_abi_version(void) BG_NOEXCEPT {
    return BG_PARTICLE_MESH_EWALD_ABI_VERSION;
}

extern "C" BG_API std::uint32_t BG_CALL
bg_particle_mesh_ewald_abi_version_major(void) BG_NOEXCEPT {
    return BG_PARTICLE_MESH_EWALD_ABI_VERSION_MAJOR;
}

extern "C" BG_API std::uint32_t BG_CALL
bg_particle_mesh_ewald_abi_version_minor(void) BG_NOEXCEPT {
    return BG_PARTICLE_MESH_EWALD_ABI_VERSION_MINOR;
}

extern "C" BG_API const char *BG_CALL
bg_particle_mesh_ewald_abi_version_string(void) BG_NOEXCEPT {
    return "1.0.0";
}

extern "C" BG_API bg_status BG_CALL
bg_particle_mesh_ewald_energy_components_v1_init(
    bg_particle_mesh_ewald_energy_components_v1 *energy,
    std::size_t caller_struct_size,
    std::uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::particle_mesh_ewald;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer(
            energy, caller_struct_size, sizeof(*energy), caller_abi_version,
            "bg_particle_mesh_ewald_energy_components_v1");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *energy = bg_particle_mesh_ewald_energy_components_v1{};
        energy->struct_size = static_cast<std::uint32_t>(sizeof(*energy));
        energy->abi_version = BG_PARTICLE_MESH_EWALD_ABI_VERSION;
        energy->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL bg_particle_mesh_ewald_force_soa_v1_init(
    bg_particle_mesh_ewald_force_soa_v1 *forces,
    std::size_t caller_struct_size,
    std::uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::particle_mesh_ewald;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer(
            forces, caller_struct_size, sizeof(*forces), caller_abi_version,
            "bg_particle_mesh_ewald_force_soa_v1");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *forces = bg_particle_mesh_ewald_force_soa_v1{};
        forces->struct_size = static_cast<std::uint32_t>(sizeof(*forces));
        forces->abi_version = BG_PARTICLE_MESH_EWALD_ABI_VERSION;
        forces->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API const char *BG_CALL
bg_particle_mesh_ewald_v1_profile_id(void) BG_NOEXCEPT {
    return betelgeuze::native::particle_mesh_ewald::kProfileId;
}

extern "C" BG_API bg_status BG_CALL
bg_context_evaluate_particle_mesh_ewald_v1(
    const bg_context *context,
    const bg_system *system,
    const bg_direct_ewald_model_v1 *direct_model,
    const bg_particle_mesh_reciprocal_model_v1 *reciprocal_model,
    bg_particle_mesh_ewald_energy_components_v1 *out_energy,
    bg_particle_mesh_ewald_force_soa_v1 *out_forces,
    bg_direct_ewald_error_v1 *out_error) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::particle_mesh_ewald;
    return guarded_status([&]() -> bg_status {
        if (context == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "particle-mesh Ewald context must not be null");
        }
        const bg_backend lane = context->requested_backend;
        switch (lane) {
            case BG_BACKEND_CPP_CPU_REFERENCE:
            case BG_BACKEND_RUST_CPU:
                break;
            case BG_BACKEND_AUTO:
            case BG_BACKEND_HIP_SAFE:
            case BG_BACKEND_HIP_FAST:
            default:
                return fail(
                    BG_STATUS_UNSUPPORTED_BACKEND,
                    "particle-mesh Ewald execution supports only explicit CPU backends and never falls back");
        }
        if (context->backend != lane) {
            return fail(
                BG_STATUS_ABI_MISMATCH,
                "particle-mesh Ewald explicit requested and resolved CPU backends must match");
        }
        if (out_error == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "particle-mesh Ewald typed error must not be null");
        }
        if (system == nullptr || direct_model == nullptr ||
            reciprocal_model == nullptr || out_energy == nullptr) {
            bg_status status = validate_required_null_error_write_safety(
                context, system, direct_model, reciprocal_model, out_energy,
                out_forces, out_error);
            if (status != BG_STATUS_OK) {
                return status;
            }
            status = validate_error_descriptor(*out_error);
            if (status != BG_STATUS_OK) {
                return status;
            }
            clear_error(out_error);
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "particle-mesh Ewald system, models, and energy must not be null");
        }
        bg_status status = validate_evaluation_overlap(
            context, system, direct_model, reciprocal_model, out_energy,
            out_forces, out_error);
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = validate_error_descriptor(*out_error);
        if (status != BG_STATUS_OK) {
            return status;
        }
        clear_error(out_error);
        status = validate_energy_output(*out_energy);
        if (status != BG_STATUS_OK) {
            return status;
        }
        if (out_forces != nullptr) {
            status = validate_force_output(
                *out_forces, direct_model->atom_count);
            if (status != BG_STATUS_OK) {
                return status;
            }
        }
        status = validate_compatibility(
            *context, *system, *direct_model, *reciprocal_model,
            *out_energy, out_forces);
        if (status != BG_STATUS_OK) {
            return status;
        }

        Evaluation evaluation;
        status = evaluate_parents(
            lane, *system, *direct_model, *reciprocal_model,
            out_forces != nullptr, &evaluation, out_error);
        if (status != BG_STATUS_OK) {
            return status;
        }

        bg_particle_mesh_ewald_energy_components_v1 committed_energy =
            *out_energy;
        committed_energy.real_space_kcal_per_mol = evaluation.real_space;
        committed_energy.reciprocal_space_kcal_per_mol =
            evaluation.reciprocal_space;
        committed_energy.self_kcal_per_mol = evaluation.self;
        committed_energy.pair_correction_kcal_per_mol =
            evaluation.pair_correction;
        committed_energy.total_kcal_per_mol = evaluation.total;
        if (out_forces != nullptr) {
            for (std::size_t atom = 0U; atom < direct_model->atom_count;
                 ++atom) {
                out_forces->x_kcal_per_mol_angstrom[atom] =
                    evaluation.forces[atom][0];
                out_forces->y_kcal_per_mol_angstrom[atom] =
                    evaluation.forces[atom][1];
                out_forces->z_kcal_per_mol_angstrom[atom] =
                    evaluation.forces[atom][2];
            }
            out_forces->atom_count =
                static_cast<std::uint64_t>(direct_model->atom_count);
        }
        *out_energy = committed_energy;
        return BG_STATUS_OK;
    });
}
