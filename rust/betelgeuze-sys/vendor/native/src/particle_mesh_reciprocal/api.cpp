#if !defined(BG_DISABLE_DESCRIPTOR_INIT_CONVENIENCE_MACROS)
#  define BG_DISABLE_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#endif
#if !defined(BG_DISABLE_PARTICLE_MESH_RECIPROCAL_DESCRIPTOR_INIT_CONVENIENCE_MACROS)
#  define BG_DISABLE_PARTICLE_MESH_RECIPROCAL_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#endif
#include "cpp_evaluator.hpp"
#include "model.hpp"
#include "rust_evaluator.hpp"

#include "../internal.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <memory>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace betelgeuze::native::particle_mesh_reciprocal {
namespace {

constexpr std::size_t kMaxAtomCount = 4'096U;
constexpr std::size_t kMaxMeshPointCount = 1'048'576U;
constexpr std::size_t kMaxEvaluationWorkUnits = 16'000'000U;
constexpr double kMinCellLength = 1.0e-6;
constexpr double kMaxCellLength = 1.0e9;
constexpr double kMinAlpha = 1.0e-12;
constexpr double kMaxAlpha = 1.0e6;
constexpr double kMinDielectric = 1.0e-12;
constexpr double kMaxDielectric = 1.0e12;
constexpr const char *kProfileId =
    "betelgeuze.native_particle_mesh_reciprocal/1.0.0";

struct ByteRange final {
    std::uintptr_t begin = 0U;
    std::uintptr_t end = 0U;
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

bool counted_range_overlaps(
    const void *pointer,
    std::size_t element_count,
    std::size_t element_size,
    const ByteRange &candidate) noexcept {
    if (pointer == nullptr || element_count == 0U || element_size == 0U ||
        element_count >
            std::numeric_limits<std::size_t>::max() / element_size) {
        return false;
    }
    ByteRange counted;
    return make_byte_range(
               pointer, element_count * element_size, &counted) &&
           ranges_overlap(counted, candidate);
}

bool any_overlap(
    const ByteRange &candidate,
    const ByteRange *ranges,
    std::size_t range_count) noexcept {
    for (std::size_t index = 0U; index < range_count; ++index) {
        if (ranges_overlap(candidate, ranges[index])) {
            return true;
        }
    }
    return false;
}

bg_status validate_header(
    std::uint32_t observed_size,
    std::size_t expected_size,
    std::uint32_t observed_version,
    const char *name) {
    if (expected_size > std::numeric_limits<std::uint32_t>::max() ||
        observed_size != static_cast<std::uint32_t>(expected_size)) {
        const std::string detail = std::string(name) +
            " struct_size does not match particle-mesh reciprocal ABI 1.0";
        return fail(BG_STATUS_ABI_MISMATCH, detail.c_str());
    }
    if (observed_version != BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION) {
        const std::string detail = std::string(name) +
            " abi_version does not match particle-mesh reciprocal ABI 1.0";
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
            " initializer size does not match particle-mesh reciprocal ABI 1.0";
        return fail(BG_STATUS_ABI_MISMATCH, detail.c_str());
    }
    if (caller_version != BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION) {
        const std::string detail = std::string(name) +
            " initializer version does not match particle-mesh reciprocal ABI 1.0";
        return fail(BG_STATUS_ABI_MISMATCH, detail.c_str());
    }
    return BG_STATUS_OK;
}

bg_status validate_error_descriptor(
    const bg_particle_mesh_reciprocal_error_v1 &error) {
    bg_status status = validate_header(
        error.struct_size, sizeof(error), error.abi_version,
        "bg_particle_mesh_reciprocal_error_v1");
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (error.reserved0 != UINT32_C(0) ||
        !reserved_is_zero(error.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "particle-mesh reciprocal error reserved fields must be zero");
    }
    return BG_STATUS_OK;
}

void clear_error(bg_particle_mesh_reciprocal_error_v1 *error) noexcept {
    error->code = BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONE;
    std::fill_n(
        error->detail,
        static_cast<std::size_t>(
            BG_PARTICLE_MESH_RECIPROCAL_ERROR_DETAIL_CAPACITY),
        '\0');
}

void commit_error(
    bg_particle_mesh_reciprocal_error_v1 *error,
    bg_particle_mesh_reciprocal_error_code code,
    std::string_view detail) noexcept {
    error->code = code;
    const std::size_t capacity = static_cast<std::size_t>(
        BG_PARTICLE_MESH_RECIPROCAL_ERROR_DETAIL_CAPACITY);
    const std::size_t length = std::min(capacity - 1U, detail.size());
    std::fill_n(error->detail, capacity, '\0');
    if (length > 0U) {
        std::memcpy(error->detail, detail.data(), length);
    }
    set_last_error(error->detail);
}

template <std::size_t Size>
bg_status typed_failure(
    bg_particle_mesh_reciprocal_error_v1 *error,
    bg_particle_mesh_reciprocal_error_code code,
    const char (&detail)[Size],
    bg_status status = BG_STATUS_INVALID_ARGUMENT) noexcept {
    static_assert(Size > 0U);
    // The array-reference overload makes every noexcept typed-failure caller
    // use a bounded literal view instead of constructing an owning string.
    commit_error(error, code, std::string_view{detail, Size - 1U});
    return status;
}

bool in_range(double value, double minimum, double maximum) noexcept {
    return std::isfinite(value) && value >= minimum && value <= maximum;
}

unsigned integer_log2(std::uint32_t value) noexcept {
    unsigned result = 0U;
    while (value > 1U) {
        value >>= 1U;
        ++result;
    }
    return result;
}

bg_status validate_work_limit(
    std::size_t atom_count,
    const std::array<std::uint32_t, 3> &mesh,
    bg_particle_mesh_reciprocal_error_v1 *error) noexcept {
    std::size_t mesh_point_count = 1U;
    std::size_t stage_count = 0U;
    for (const std::uint32_t dimension : mesh) {
        if (mesh_point_count >
            std::numeric_limits<std::size_t>::max() / dimension) {
            return typed_failure(
                error,
                BG_PARTICLE_MESH_RECIPROCAL_ERROR_CAPACITY_EXCEEDED,
                "mesh point count exceeds addressable capacity",
                BG_STATUS_CAPACITY_OVERFLOW);
        }
        mesh_point_count *= dimension;
        stage_count += integer_log2(dimension);
    }
    if (mesh_point_count > kMaxMeshPointCount) {
        return typed_failure(
            error, BG_PARTICLE_MESH_RECIPROCAL_ERROR_CAPACITY_EXCEEDED,
            "mesh point count exceeds 1048576",
            BG_STATUS_CAPACITY_OVERFLOW);
    }
    if (stage_count == std::numeric_limits<std::size_t>::max() ||
        mesh_point_count >
            std::numeric_limits<std::size_t>::max() / (stage_count + 1U) ||
        atom_count > std::numeric_limits<std::size_t>::max() / 256U) {
        return typed_failure(
            error, BG_PARTICLE_MESH_RECIPROCAL_ERROR_CAPACITY_EXCEEDED,
            "particle-mesh evaluation work exceeds addressable capacity",
            BG_STATUS_CAPACITY_OVERFLOW);
    }
    const std::size_t mesh_work = mesh_point_count * (stage_count + 1U);
    const std::size_t particle_work = atom_count * 256U;
    if (particle_work >
            std::numeric_limits<std::size_t>::max() - mesh_work ||
        mesh_work + particle_work > kMaxEvaluationWorkUnits) {
        return typed_failure(
            error, BG_PARTICLE_MESH_RECIPROCAL_ERROR_CAPACITY_EXCEEDED,
            "particle-mesh evaluation work exceeds 16000000",
            BG_STATUS_CAPACITY_OVERFLOW);
    }
    return BG_STATUS_OK;
}

bg_status validate_parameters(
    const bg_particle_mesh_reciprocal_parameters_v1 &parameters,
    bg_particle_mesh_reciprocal_error_v1 *error) {
    static_assert(sizeof(bg_particle_mesh_reciprocal_parameters_v1) == 112U);
    bg_status status = validate_header(
        parameters.struct_size, sizeof(parameters), parameters.abi_version,
        "bg_particle_mesh_reciprocal_parameters_v1");
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (parameters.reserved0 != UINT32_C(0) ||
        parameters.reserved1 != UINT32_C(0) ||
        !reserved_is_zero(parameters.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "particle-mesh reciprocal parameters reserved fields must be zero");
    }
    status = validate_unit_system(parameters.unit_system);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (parameters.atom_count == 0U) {
        return typed_failure(
            error, BG_PARTICLE_MESH_RECIPROCAL_ERROR_EMPTY_SYSTEM,
            "at least one particle is required");
    }
    if (parameters.atom_count > kMaxAtomCount) {
        return typed_failure(
            error, BG_PARTICLE_MESH_RECIPROCAL_ERROR_CAPACITY_EXCEEDED,
            "particle count exceeds 4096", BG_STATUS_CAPACITY_OVERFLOW);
    }
    for (const double length : parameters.cell_lengths_angstrom) {
        if (!in_range(length, kMinCellLength, kMaxCellLength)) {
            return typed_failure(
                error, BG_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_CELL,
                "cell lengths must lie in [1e-6,1e9] angstrom");
        }
    }
    std::array<double, 3> sorted_lengths{
        parameters.cell_lengths_angstrom[0],
        parameters.cell_lengths_angstrom[1],
        parameters.cell_lengths_angstrom[2]};
    std::sort(sorted_lengths.begin(), sorted_lengths.end());
    const double volume =
        (sorted_lengths[0] * sorted_lengths[2]) * sorted_lengths[1];
    if (!std::isfinite(volume) || volume <= 0.0) {
        return typed_failure(
            error, BG_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_CELL,
            "cell volume must be finite and positive");
    }
    if (!in_range(parameters.alpha_per_angstrom, kMinAlpha, kMaxAlpha) ||
        !in_range(parameters.dielectric, kMinDielectric, kMaxDielectric)) {
        return typed_failure(
            error, BG_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_PARAMETER,
            "alpha and dielectric lie outside the supported numeric envelope");
    }
    std::array<std::uint32_t, 3> mesh{};
    for (std::size_t axis = 0U; axis < 3U; ++axis) {
        const std::uint32_t dimension = parameters.mesh_dimensions[axis];
        if (dimension < 4U || dimension > 128U ||
            (dimension & (dimension - 1U)) != 0U) {
            return typed_failure(
                error, BG_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_MESH,
                "mesh dimensions must be powers of two in [4,128]");
        }
        mesh[axis] = dimension;
    }
    return validate_work_limit(
        static_cast<std::size_t>(parameters.atom_count), mesh, error);
}

bg_status validate_energy_output(
    const bg_particle_mesh_reciprocal_energy_v1 &energy) {
    static_assert(sizeof(bg_particle_mesh_reciprocal_energy_v1) == 56U);
    bg_status status = validate_header(
        energy.struct_size, sizeof(energy), energy.abi_version,
        "bg_particle_mesh_reciprocal_energy_v1");
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
            "particle-mesh reciprocal energy reserved fields must be zero");
    }
    return BG_STATUS_OK;
}

bg_status validate_force_output_header(
    const bg_particle_mesh_reciprocal_force_soa_v1 &forces,
    std::size_t atom_count) {
    static_assert(sizeof(bg_particle_mesh_reciprocal_force_soa_v1) == 88U);
    bg_status status = validate_header(
        forces.struct_size, sizeof(forces), forces.abi_version,
        "bg_particle_mesh_reciprocal_force_soa_v1");
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
            "particle-mesh reciprocal force reserved fields must be zero");
    }
    if (forces.atom_capacity < atom_count) {
        return fail(
            BG_STATUS_BUFFER_TOO_SMALL,
            "particle-mesh reciprocal force capacity is smaller than atom count");
    }
    if (atom_count > 0U &&
        (forces.x_kcal_per_mol_angstrom == nullptr ||
         forces.y_kcal_per_mol_angstrom == nullptr ||
         forces.z_kcal_per_mol_angstrom == nullptr)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "non-empty particle-mesh reciprocal force output requires three channels");
    }
    if (!pointer_is_aligned(forces.x_kcal_per_mol_angstrom) ||
        !pointer_is_aligned(forces.y_kcal_per_mol_angstrom) ||
        !pointer_is_aligned(forces.z_kcal_per_mol_angstrom)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "particle-mesh reciprocal force channels must be naturally aligned");
    }
    return BG_STATUS_OK;
}

bg_status validate_create_descriptor_overlap(
    const bg_particle_mesh_reciprocal_parameters_v1 *parameters,
    bg_particle_mesh_reciprocal_model_v1 **model_output,
    const bg_particle_mesh_reciprocal_error_v1 *error) noexcept {
    ByteRange error_range;
    if (!make_byte_range(error, sizeof(*error), &error_range)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "particle-mesh reciprocal create error range is not representable");
    }
    std::array<ByteRange, 2> prior{};
    std::size_t count = 0U;
    if (parameters != nullptr) {
        ByteRange range;
        if (!make_byte_range(parameters, sizeof(*parameters), &range) ||
            ranges_overlap(range, error_range)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "particle-mesh reciprocal create descriptors must not overlap");
        }
        prior[count++] = range;
    }
    if (model_output != nullptr) {
        ByteRange range;
        if (!make_byte_range(model_output, sizeof(*model_output), &range) ||
            counted_range_overlaps(
                model_output, 1U, sizeof(*model_output), error_range) ||
            any_overlap(range, prior.data(), count)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "particle-mesh reciprocal create descriptors must not overlap");
        }
    }
    return BG_STATUS_OK;
}

bg_status append_range(
    const void *pointer,
    std::size_t bytes,
    std::array<ByteRange, 20> *ranges,
    std::size_t *count,
    const char *detail) noexcept {
    ByteRange candidate;
    if (!make_byte_range(pointer, bytes, &candidate) ||
        any_overlap(candidate, ranges->data(), *count)) {
        return fail(BG_STATUS_INVALID_ARGUMENT, detail);
    }
    (*ranges)[(*count)++] = candidate;
    return BG_STATUS_OK;
}

bg_status validate_evaluation_overlap(
    const bg_context *context,
    const bg_system *system,
    const bg_particle_mesh_reciprocal_model_v1 *model,
    const bg_particle_mesh_reciprocal_energy_v1 *energy,
    const bg_particle_mesh_reciprocal_force_soa_v1 *forces,
    const bg_particle_mesh_reciprocal_error_v1 *error) noexcept {
    std::array<ByteRange, 20> ranges{};
    std::size_t count = 0U;
    constexpr const char *detail =
        "particle-mesh reciprocal borrowed inputs, outputs, and descriptors must not overlap";
    bg_status status = append_range(
        context, sizeof(*context), &ranges, &count, detail);
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = append_range(system, sizeof(*system), &ranges, &count, detail);
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = append_range(model, sizeof(*model), &ranges, &count, detail);
    if (status != BG_STATUS_OK) {
        return status;
    }
    const std::size_t atom_count = system->position_x.size();
    if (atom_count > 0U &&
        atom_count <= std::numeric_limits<std::size_t>::max() / sizeof(double)) {
        const std::size_t bytes = atom_count * sizeof(double);
        const std::array<const double *, 8> inputs{
            system->position_x.data(), system->position_y.data(),
            system->position_z.data(), system->velocity_x.data(),
            system->velocity_y.data(), system->velocity_z.data(),
            system->mass.data(), system->charge.data()};
        for (const double *input : inputs) {
            status = append_range(
                input, bytes, &ranges, &count, detail);
            if (status != BG_STATUS_OK) {
                return status;
            }
        }
    }
    status = append_range(error, sizeof(*error), &ranges, &count, detail);
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = append_range(energy, sizeof(*energy), &ranges, &count, detail);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (forces == nullptr) {
        return BG_STATUS_OK;
    }
    status = append_range(forces, sizeof(*forces), &ranges, &count, detail);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (model->atom_count >
        std::numeric_limits<std::size_t>::max() / sizeof(double)) {
        return fail(BG_STATUS_INVALID_ARGUMENT, detail);
    }
    const std::size_t force_bytes = model->atom_count * sizeof(double);
    const std::array<const double *, 3> outputs{
        forces->x_kcal_per_mol_angstrom,
        forces->y_kcal_per_mol_angstrom,
        forces->z_kcal_per_mol_angstrom};
    for (const double *output : outputs) {
        status = append_range(
            output, force_bytes, &ranges, &count, detail);
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
    const bg_particle_mesh_reciprocal_model_v1 *model,
    const bg_particle_mesh_reciprocal_energy_v1 *energy,
    const bg_particle_mesh_reciprocal_force_soa_v1 *forces,
    const bg_particle_mesh_reciprocal_error_v1 *error) noexcept {
    constexpr const char *detail =
        "particle-mesh reciprocal typed error must not overlap borrowed or output storage";
    ByteRange error_range;
    if (!make_byte_range(error, sizeof(*error), &error_range)) {
        return fail(BG_STATUS_INVALID_ARGUMENT, detail);
    }
    const std::array<std::pair<const void *, std::size_t>, 5> fixed{{
        {context, context == nullptr ? 0U : sizeof(*context)},
        {system, system == nullptr ? 0U : sizeof(*system)},
        {model, model == nullptr ? 0U : sizeof(*model)},
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
    if (forces != nullptr) {
        if (forces->atom_capacity >
            static_cast<std::uint64_t>(
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

bg_status status_for_typed_error(
    bg_particle_mesh_reciprocal_error_code code) noexcept {
    if (code == BG_PARTICLE_MESH_RECIPROCAL_ERROR_CAPACITY_EXCEEDED) {
        return BG_STATUS_CAPACITY_OVERFLOW;
    }
    if (code == BG_PARTICLE_MESH_RECIPROCAL_ERROR_NON_NEUTRAL_SYSTEM ||
        code == BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONFINITE_RESULT) {
        return BG_STATUS_NUMERICAL_ERROR;
    }
    return BG_STATUS_INVALID_ARGUMENT;
}

}  // namespace
}  // namespace betelgeuze::native::particle_mesh_reciprocal

extern "C" BG_API std::uint32_t BG_CALL
bg_particle_mesh_reciprocal_abi_version(void) BG_NOEXCEPT {
    return BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION;
}

extern "C" BG_API std::uint32_t BG_CALL
bg_particle_mesh_reciprocal_abi_version_major(void) BG_NOEXCEPT {
    return BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION_MAJOR;
}

extern "C" BG_API std::uint32_t BG_CALL
bg_particle_mesh_reciprocal_abi_version_minor(void) BG_NOEXCEPT {
    return BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION_MINOR;
}

extern "C" BG_API const char *BG_CALL
bg_particle_mesh_reciprocal_abi_version_string(void) BG_NOEXCEPT {
    return "1.0.0";
}

extern "C" BG_API bg_status BG_CALL
bg_particle_mesh_reciprocal_parameters_v1_init(
    bg_particle_mesh_reciprocal_parameters_v1 *parameters,
    std::size_t caller_struct_size,
    std::uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::particle_mesh_reciprocal;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer(
            parameters, caller_struct_size, sizeof(*parameters),
            caller_abi_version,
            "bg_particle_mesh_reciprocal_parameters_v1");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *parameters = bg_particle_mesh_reciprocal_parameters_v1{};
        parameters->struct_size =
            static_cast<std::uint32_t>(sizeof(*parameters));
        parameters->abi_version =
            BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION;
        parameters->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        parameters->alpha_per_angstrom = 0.3;
        parameters->mesh_dimensions[0] = 16U;
        parameters->mesh_dimensions[1] = 16U;
        parameters->mesh_dimensions[2] = 16U;
        parameters->dielectric = 1.0;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL
bg_particle_mesh_reciprocal_energy_v1_init(
    bg_particle_mesh_reciprocal_energy_v1 *energy,
    std::size_t caller_struct_size,
    std::uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::particle_mesh_reciprocal;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer(
            energy, caller_struct_size, sizeof(*energy), caller_abi_version,
            "bg_particle_mesh_reciprocal_energy_v1");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *energy = bg_particle_mesh_reciprocal_energy_v1{};
        energy->struct_size = static_cast<std::uint32_t>(sizeof(*energy));
        energy->abi_version = BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION;
        energy->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL
bg_particle_mesh_reciprocal_force_soa_v1_init(
    bg_particle_mesh_reciprocal_force_soa_v1 *forces,
    std::size_t caller_struct_size,
    std::uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::particle_mesh_reciprocal;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer(
            forces, caller_struct_size, sizeof(*forces), caller_abi_version,
            "bg_particle_mesh_reciprocal_force_soa_v1");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *forces = bg_particle_mesh_reciprocal_force_soa_v1{};
        forces->struct_size = static_cast<std::uint32_t>(sizeof(*forces));
        forces->abi_version = BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION;
        forces->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL
bg_particle_mesh_reciprocal_error_v1_init(
    bg_particle_mesh_reciprocal_error_v1 *error,
    std::size_t caller_struct_size,
    std::uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::particle_mesh_reciprocal;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer(
            error, caller_struct_size, sizeof(*error), caller_abi_version,
            "bg_particle_mesh_reciprocal_error_v1");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *error = bg_particle_mesh_reciprocal_error_v1{};
        error->struct_size = static_cast<std::uint32_t>(sizeof(*error));
        error->abi_version = BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL
bg_particle_mesh_reciprocal_model_v1_create(
    const bg_particle_mesh_reciprocal_parameters_v1 *parameters,
    bg_particle_mesh_reciprocal_model_v1 **out_model,
    bg_particle_mesh_reciprocal_error_v1 *out_error) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::particle_mesh_reciprocal;
    return guarded_status([&]() -> bg_status {
        if (out_error == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "particle-mesh reciprocal typed error must not be null");
        }
        bg_status status =
            validate_create_descriptor_overlap(
                parameters, out_model, out_error);
        if (status != BG_STATUS_OK) {
            return status;
        }
        if (out_model != nullptr) {
            *out_model = nullptr;
        }
        status = validate_error_descriptor(*out_error);
        if (status != BG_STATUS_OK) {
            return status;
        }
        clear_error(out_error);
        if (parameters == nullptr || out_model == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "particle-mesh reciprocal parameters and model output must not be null");
        }
        status = validate_parameters(*parameters, out_error);
        if (status != BG_STATUS_OK) {
            return status;
        }
        auto model =
            std::make_unique<bg_particle_mesh_reciprocal_model_v1>();
        model->unit_system = parameters->unit_system;
        model->atom_count =
            static_cast<std::size_t>(parameters->atom_count);
        std::copy_n(
            parameters->cell_lengths_angstrom, 3U,
            model->cell_lengths_angstrom.begin());
        model->alpha_per_angstrom = parameters->alpha_per_angstrom;
        std::copy_n(
            parameters->mesh_dimensions, 3U,
            model->mesh_dimensions.begin());
        model->dielectric = parameters->dielectric;
        *out_model = model.release();
        return BG_STATUS_OK;
    });
}

extern "C" BG_API void BG_CALL
bg_particle_mesh_reciprocal_model_v1_destroy(
    bg_particle_mesh_reciprocal_model_v1 *model) BG_NOEXCEPT {
    delete model;
}

extern "C" BG_API bg_status BG_CALL
bg_particle_mesh_reciprocal_model_v1_get_atom_count(
    const bg_particle_mesh_reciprocal_model_v1 *model,
    std::uint64_t *atom_count) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::particle_mesh_reciprocal;
    return guarded_status([&]() -> bg_status {
        if (model == nullptr || atom_count == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "particle-mesh reciprocal model and atom-count output must not be null");
        }
        ByteRange model_range;
        ByteRange output_range;
        if (!make_byte_range(model, sizeof(*model), &model_range) ||
            !make_byte_range(atom_count, sizeof(*atom_count), &output_range) ||
            ranges_overlap(model_range, output_range)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "particle-mesh reciprocal model and atom-count output must not overlap");
        }
        *atom_count = static_cast<std::uint64_t>(model->atom_count);
        return BG_STATUS_OK;
    });
}

extern "C" BG_API const char *BG_CALL
bg_particle_mesh_reciprocal_model_v1_profile_id(void) BG_NOEXCEPT {
    return betelgeuze::native::particle_mesh_reciprocal::kProfileId;
}

extern "C" BG_API bg_status BG_CALL
bg_context_evaluate_particle_mesh_reciprocal_v1(
    const bg_context *context,
    const bg_system *system,
    const bg_particle_mesh_reciprocal_model_v1 *model,
    bg_particle_mesh_reciprocal_energy_v1 *out_energy,
    bg_particle_mesh_reciprocal_force_soa_v1 *out_forces,
    bg_particle_mesh_reciprocal_error_v1 *out_error) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::particle_mesh_reciprocal;
    return guarded_status([&]() -> bg_status {
        if (context == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "particle-mesh reciprocal context must not be null");
        }
        switch (context->requested_backend) {
            case BG_BACKEND_CPP_CPU_REFERENCE:
            case BG_BACKEND_RUST_CPU:
                break;
            case BG_BACKEND_AUTO:
            case BG_BACKEND_HIP_SAFE:
            case BG_BACKEND_HIP_FAST:
            default:
                return fail(
                    BG_STATUS_UNSUPPORTED_BACKEND,
                    "particle-mesh reciprocal execution supports only explicit CPU backends and never falls back");
        }
        if (out_error == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "particle-mesh reciprocal typed error must not be null");
        }
        if (system == nullptr || model == nullptr || out_energy == nullptr) {
            bg_status status = validate_required_null_error_write_safety(
                context, system, model, out_energy, out_forces, out_error);
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
                "particle-mesh reciprocal system, model, and energy must not be null");
        }
        bg_status status = validate_evaluation_overlap(
            context, system, model, out_energy, out_forces, out_error);
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
            status = validate_force_output_header(
                *out_forces, model->atom_count);
            if (status != BG_STATUS_OK) {
                return status;
            }
        }
        if (context->unit_system != system->unit_system ||
            context->unit_system != model->unit_system ||
            context->unit_system != out_energy->unit_system ||
            (out_forces != nullptr &&
             context->unit_system != out_forces->unit_system)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "particle-mesh reciprocal context, system, model, and outputs must use matching units");
        }

        Evaluation evaluation;
        Error typed_error;
        if (context->backend == BG_BACKEND_CPP_CPU_REFERENCE) {
            status = cpp_cpu::evaluate(
                *system, *model, out_forces != nullptr, &evaluation,
                &typed_error);
        } else {
            status = rust_cpu::evaluate(
                *system, *model, out_forces != nullptr, &evaluation,
                &typed_error);
        }
        if (status != BG_STATUS_OK) {
            if (typed_error.code !=
                BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONE) {
                commit_error(
                    out_error, typed_error.code,
                    std::string_view{
                        typed_error.detail.data(),
                        typed_error.detail.size()});
                return status_for_typed_error(typed_error.code);
            }
            return status;
        }
        if (evaluation.forces.size() !=
            (out_forces == nullptr ? 0U : model->atom_count)) {
            return fail(
                BG_STATUS_INTERNAL_ERROR,
                "particle-mesh reciprocal evaluator returned an invalid force count");
        }
        bg_particle_mesh_reciprocal_energy_v1 committed_energy =
            *out_energy;
        committed_energy.reciprocal_space_kcal_per_mol =
            evaluation.reciprocal_space_kcal_per_mol;
        if (out_forces != nullptr) {
            for (std::size_t atom = 0U; atom < model->atom_count; ++atom) {
                out_forces->x_kcal_per_mol_angstrom[atom] =
                    evaluation.forces[atom][0];
                out_forces->y_kcal_per_mol_angstrom[atom] =
                    evaluation.forces[atom][1];
                out_forces->z_kcal_per_mol_angstrom[atom] =
                    evaluation.forces[atom][2];
            }
            out_forces->atom_count =
                static_cast<std::uint64_t>(model->atom_count);
        }
        *out_energy = committed_energy;
        return BG_STATUS_OK;
    });
}
