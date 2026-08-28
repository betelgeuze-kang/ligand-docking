#if !defined(BG_DISABLE_DESCRIPTOR_INIT_CONVENIENCE_MACROS)
#  define BG_DISABLE_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#endif
#if !defined(BG_DISABLE_DIRECT_EWALD_DESCRIPTOR_INIT_CONVENIENCE_MACROS)
#  define BG_DISABLE_DIRECT_EWALD_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#endif
#if !defined(BG_DISABLE_DIRECT_EWALD_COMPOSITE_DESCRIPTOR_INIT_CONVENIENCE_MACROS)
#  define BG_DISABLE_DIRECT_EWALD_COMPOSITE_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#endif
#include "betelgeuze/direct_ewald_composite.h"

#include "evaluator.hpp"
#include "../cpu/evaluator.hpp"
#include "../ewald/cpp_evaluator.hpp"
#include "../ewald/model.hpp"
#include "../ewald/rust_evaluator.hpp"
#include "../internal.hpp"
#include "../rust/evaluator.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <string>
#include <utility>
#include <vector>

namespace betelgeuze::native::composite {
namespace {

constexpr const char *kProfileId =
    "betelgeuze.native_direct_ewald_composite/1.0.0";

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
    const std::uintptr_t begin = reinterpret_cast<std::uintptr_t>(pointer);
    if (byte_count > std::numeric_limits<std::uintptr_t>::max() - begin) {
        return false;
    }
    *out_range = ByteRange{begin, begin + byte_count};
    return true;
}

bool ranges_overlap(const ByteRange &left, const ByteRange &right) noexcept {
    return left.begin < right.end && right.begin < left.end;
}

bg_status validate_composite_header(
    uint32_t observed_size,
    std::size_t expected_size,
    uint32_t observed_version,
    const char *name) {
    if (expected_size > std::numeric_limits<uint32_t>::max() ||
        observed_size != static_cast<uint32_t>(expected_size)) {
        const std::string message = std::string(name) +
            " struct_size does not match direct-Ewald composite ABI 1.0";
        return fail(BG_STATUS_ABI_MISMATCH, message.c_str());
    }
    if (observed_version != BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION) {
        const std::string message = std::string(name) +
            " abi_version does not match direct-Ewald composite ABI 1.0";
        return fail(BG_STATUS_ABI_MISMATCH, message.c_str());
    }
    return BG_STATUS_OK;
}

bg_status validate_composite_initializer(
    const void *descriptor,
    std::size_t caller_size,
    std::size_t native_size,
    uint32_t caller_version,
    const char *name) {
    if (descriptor == nullptr) {
        const std::string message = std::string(name) +
            " pointer must not be null";
        return fail(BG_STATUS_INVALID_ARGUMENT, message.c_str());
    }
    if (caller_size != native_size ||
        native_size > std::numeric_limits<uint32_t>::max()) {
        const std::string message = std::string(name) +
            " initializer size does not match direct-Ewald composite ABI 1.0";
        return fail(BG_STATUS_ABI_MISMATCH, message.c_str());
    }
    if (caller_version != BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION) {
        const std::string message = std::string(name) +
            " initializer version does not match direct-Ewald composite ABI 1.0";
        return fail(BG_STATUS_ABI_MISMATCH, message.c_str());
    }
    return BG_STATUS_OK;
}

bg_status validate_error_descriptor(const bg_direct_ewald_error_v1 &error) {
    if (error.struct_size !=
            static_cast<uint32_t>(sizeof(bg_direct_ewald_error_v1)) ||
        error.abi_version != BG_DIRECT_EWALD_ABI_VERSION) {
        return fail(
            BG_STATUS_ABI_MISMATCH,
            "typed error does not match direct-Ewald ABI 1.0");
    }
    if (error.reserved0 != UINT32_C(0) ||
        !reserved_is_zero(error.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "direct-Ewald typed-error reserved fields must be zero");
    }
    return BG_STATUS_OK;
}

void clear_error(bg_direct_ewald_error_v1 *error) noexcept {
    error->code = BG_DIRECT_EWALD_ERROR_NONE;
    std::fill_n(
        error->detail,
        static_cast<std::size_t>(BG_DIRECT_EWALD_ERROR_DETAIL_CAPACITY), '\0');
}

void commit_error(
    bg_direct_ewald_error_v1 *error,
    bg_direct_ewald_error_code code,
    const std::string &detail) noexcept {
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

bg_status status_for_typed_error(bg_direct_ewald_error_code code) noexcept {
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

bg_status validate_descriptor_overlap(
    const bg_direct_ewald_composite_energy_components_v1 *energy,
    const bg_direct_ewald_composite_force_soa_v1 *forces,
    const bg_direct_ewald_error_v1 *error) noexcept {
    ByteRange error_range;
    if (!make_byte_range(error, sizeof(*error), &error_range)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "composite output descriptor byte ranges are not representable");
    }
    ByteRange energy_range;
    const bool has_energy = energy != nullptr;
    if (has_energy &&
        (!make_byte_range(energy, sizeof(*energy), &energy_range) ||
         ranges_overlap(energy_range, error_range))) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "composite energy and typed-error descriptors must not overlap");
    }
    if (forces != nullptr) {
        ByteRange force_range;
        if (!make_byte_range(forces, sizeof(*forces), &force_range) ||
            (has_energy && ranges_overlap(force_range, energy_range)) ||
            ranges_overlap(force_range, error_range)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "composite output descriptors must not overlap");
        }
    }
    return BG_STATUS_OK;
}

bg_status validate_energy_output(
    const bg_direct_ewald_composite_energy_components_v1 &energy) {
    bg_status status = validate_composite_header(
        energy.struct_size, sizeof(energy), energy.abi_version,
        "bg_direct_ewald_composite_energy_components_v1");
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
            "composite energy reserved fields must be zero");
    }
    return BG_STATUS_OK;
}

bg_status validate_force_output_descriptor(
    const bg_direct_ewald_composite_force_soa_v1 &forces) {
    bg_status status = validate_composite_header(
        forces.struct_size, sizeof(forces), forces.abi_version,
        "bg_direct_ewald_composite_force_soa_v1");
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
            "composite force reserved fields must be zero");
    }
    if (forces.atom_capacity > 0U &&
        (forces.x_kcal_per_mol_angstrom == nullptr ||
         forces.y_kcal_per_mol_angstrom == nullptr ||
         forces.z_kcal_per_mol_angstrom == nullptr)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "non-empty composite force output requires three channels");
    }
    if (!pointer_is_aligned(forces.x_kcal_per_mol_angstrom) ||
        !pointer_is_aligned(forces.y_kcal_per_mol_angstrom) ||
        !pointer_is_aligned(forces.z_kcal_per_mol_angstrom)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "composite force channels must be naturally aligned");
    }
    const uint64_t maximum_capacity = static_cast<uint64_t>(
        std::numeric_limits<std::size_t>::max() / sizeof(double));
    if (forces.atom_capacity > maximum_capacity) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "composite force byte span exceeds addressable size");
    }
    return BG_STATUS_OK;
}

bg_status validate_force_output_spans(
    const bg_direct_ewald_composite_force_soa_v1 &forces,
    const bg_direct_ewald_composite_energy_components_v1 *energy,
    const bg_direct_ewald_error_v1 *error,
    std::size_t span_count) {
    if (span_count == 0U) {
        return BG_STATUS_OK;
    }
    if (span_count > std::numeric_limits<std::size_t>::max() / sizeof(double)) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "composite force byte span exceeds addressable size");
    }
    const std::size_t bytes = span_count * sizeof(double);
    std::array<ByteRange, 6> ranges{};
    std::size_t range_count = 0U;
    const auto add_range = [&](const void *pointer, std::size_t range_bytes) {
        if (!make_byte_range(
                pointer, range_bytes, &ranges[range_count])) {
            return false;
        }
        ++range_count;
        return true;
    };
    if (!add_range(forces.x_kcal_per_mol_angstrom, bytes) ||
        !add_range(forces.y_kcal_per_mol_angstrom, bytes) ||
        !add_range(forces.z_kcal_per_mol_angstrom, bytes) ||
        !add_range(&forces, sizeof(forces)) ||
        (energy != nullptr && !add_range(energy, sizeof(*energy))) ||
        !add_range(error, sizeof(*error))) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "composite output byte ranges are not representable");
    }
    for (std::size_t left = 0; left < range_count; ++left) {
        for (std::size_t right = left + 1U; right < range_count; ++right) {
            if (ranges_overlap(ranges[left], ranges[right])) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "composite output channels/descriptors must not overlap");
            }
        }
    }
    return BG_STATUS_OK;
}

bg_status validate_force_output_capacity(
    const bg_direct_ewald_composite_force_soa_v1 &forces,
    std::size_t atom_count) {
    if (forces.atom_capacity < static_cast<uint64_t>(atom_count)) {
        return fail(
            BG_STATUS_BUFFER_TOO_SMALL,
            "composite force capacity is smaller than atom count");
    }
    return BG_STATUS_OK;
}

bool double_bits_equal(double left, double right) noexcept {
    uint64_t left_bits = 0;
    uint64_t right_bits = 0;
    std::memcpy(&left_bits, &left, sizeof(left_bits));
    std::memcpy(&right_bits, &right, sizeof(right_bits));
    return left_bits == right_bits;
}

bool system_storage_is_consistent(const bg_system &system) noexcept {
    const std::size_t count = system.position_x.size();
    return system.position_y.size() == count &&
           system.position_z.size() == count &&
           system.velocity_x.size() == count &&
           system.velocity_y.size() == count &&
           system.velocity_z.size() == count &&
           system.mass.size() == count && system.charge.size() == count;
}

bg_status validate_output_system_disjoint(
    const bg_system &system,
    const bg_direct_ewald_composite_energy_components_v1 &energy,
    const bg_direct_ewald_composite_force_soa_v1 *forces,
    const bg_direct_ewald_error_v1 &error) {
    std::array<ByteRange, 6> outputs{};
    std::size_t output_count = 0U;
    const auto add_output = [&](const void *pointer, std::size_t bytes) {
        if (!make_byte_range(
                pointer, bytes, &outputs[output_count])) {
            return false;
        }
        ++output_count;
        return true;
    };
    if (!add_output(&energy, sizeof(energy)) ||
        !add_output(&error, sizeof(error))) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "composite output descriptor byte ranges are not representable");
    }
    if (forces != nullptr) {
        const std::size_t atom_count = system.position_x.size();
        if (atom_count >
            std::numeric_limits<std::size_t>::max() / sizeof(double)) {
            return fail(
                BG_STATUS_CAPACITY_OVERFLOW,
                "composite force byte span exceeds addressable size");
        }
        const std::size_t bytes = atom_count * sizeof(double);
        if (!add_output(forces, sizeof(*forces)) ||
            (atom_count > 0U &&
             (!add_output(forces->x_kcal_per_mol_angstrom, bytes) ||
              !add_output(forces->y_kcal_per_mol_angstrom, bytes) ||
              !add_output(forces->z_kcal_per_mol_angstrom, bytes)))) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "composite output byte ranges are not representable");
        }
    }

    const std::array<const std::vector<double> *, 8> system_channels{{
        &system.position_x,
        &system.position_y,
        &system.position_z,
        &system.velocity_x,
        &system.velocity_y,
        &system.velocity_z,
        &system.mass,
        &system.charge,
    }};
    for (const std::vector<double> *channel : system_channels) {
        if (channel->empty()) {
            continue;
        }
        ByteRange input;
        if (!make_byte_range(
                channel->data(), channel->size() * sizeof(double), &input)) {
            return fail(
                BG_STATUS_INTERNAL_ERROR,
                "borrowed system byte range is not representable");
        }
        for (std::size_t index = 0; index < output_count; ++index) {
            if (ranges_overlap(input, outputs[index])) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "composite outputs must not overlap borrowed system storage");
            }
        }
    }
    return BG_STATUS_OK;
}

bool pair_matches(
    const ewald::PairRule &observed,
    const bg_forcefield::Pair &expected) noexcept {
    return observed.atom_i == expected.atom_i &&
           observed.atom_j == expected.atom_j;
}

bg_status validate_pair_rule_projection(
    const bg_forcefield &forcefield,
    const bg_direct_ewald_model_v1 &model) {
    if (forcefield.exclusions.size() >
        std::numeric_limits<std::size_t>::max() -
            forcefield.pair_scales.size() ||
        model.pair_rules.size() !=
            forcefield.exclusions.size() + forcefield.pair_scales.size()) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "force-field and direct-Ewald pair-rule counts must match exactly");
    }
    std::size_t exclusion = 0;
    std::size_t scale = 0;
    std::size_t model_row = 0;
    while (exclusion < forcefield.exclusions.size() ||
           scale < forcefield.pair_scales.size()) {
        const bool take_exclusion =
            scale == forcefield.pair_scales.size() ||
            (exclusion < forcefield.exclusions.size() &&
             forcefield.exclusions[exclusion] <
                 forcefield.pair_scales[scale].pair);
        const ewald::PairRule &observed = model.pair_rules[model_row];
        if (take_exclusion) {
            if (!observed.is_exclusion ||
                !pair_matches(observed, forcefield.exclusions[exclusion]) ||
                !double_bits_equal(observed.coulomb_scale, 0.0)) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "direct-Ewald exclusion provenance must match the force field");
            }
            ++exclusion;
        } else {
            const bg_forcefield::PairScale &expected =
                forcefield.pair_scales[scale];
            if (observed.is_exclusion ||
                !pair_matches(observed, expected.pair) ||
                !double_bits_equal(
                    observed.coulomb_scale, expected.coulomb)) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "direct-Ewald Coulomb pair scales must match the force field");
            }
            ++scale;
        }
        ++model_row;
    }
    return BG_STATUS_OK;
}

bg_status validate_compatible_storage_and_pair_rules(
    const bg_system &system,
    const bg_forcefield &forcefield,
    const bg_direct_ewald_model_v1 &model) {
    if (!system_storage_is_consistent(system)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "composite system particle storage is inconsistent");
    }
    const std::size_t atom_count = system.position_x.size();
    if (forcefield.atom_count != atom_count || model.atom_count != atom_count) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "composite system, force field, and model atom counts must match");
    }
    if (forcefield.periodic_axes_mask != BG_PERIODIC_AXES_ALL) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "composite force field must be periodic on all three axes");
    }
    for (std::size_t axis = 0; axis < 3U; ++axis) {
        if (!double_bits_equal(
                forcefield.cell_lengths[axis],
                model.cell_lengths_angstrom[axis])) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "composite force-field and model cell bits must match");
        }
    }
    return validate_pair_rule_projection(forcefield, model);
}

bool short_energy_is_valid(const cpu::Evaluation &evaluation) noexcept {
    const bg_energy_components_v1 &energy = evaluation.energy;
    const std::array<double, 6> values{{
        energy.harmonic_bond_kcal_per_mol,
        energy.harmonic_angle_kcal_per_mol,
        energy.periodic_torsion_kcal_per_mol,
        energy.lennard_jones_kcal_per_mol,
        energy.coulomb_kcal_per_mol,
        energy.total_kcal_per_mol,
    }};
    if (std::any_of(values.begin(), values.end(), [](double value) {
            return !std::isfinite(value);
        })) {
        return false;
    }
    const double short_total =
        energy.harmonic_bond_kcal_per_mol +
        energy.harmonic_angle_kcal_per_mol +
        energy.periodic_torsion_kcal_per_mol +
        energy.lennard_jones_kcal_per_mol +
        energy.coulomb_kcal_per_mol;
    return double_bits_equal(short_total, energy.total_kcal_per_mol) &&
           double_bits_equal(energy.coulomb_kcal_per_mol, 0.0);
}

bool ewald_energy_is_valid(const ewald::Evaluation &evaluation) noexcept {
    const std::array<double, 5> values{{
        evaluation.energy.real_space,
        evaluation.energy.reciprocal_space,
        evaluation.energy.self,
        evaluation.energy.pair_correction,
        evaluation.energy.total(),
    }};
    return std::none_of(values.begin(), values.end(), [](double value) {
        return !std::isfinite(value);
    });
}

}  // namespace

bg_status validate_static_compatibility(
    const bg_system &system,
    const bg_forcefield &forcefield,
    const bg_direct_ewald_model_v1 &model) {
    if (system.unit_system != forcefield.unit_system ||
        system.unit_system != model.unit_system) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "composite system, force field, and model units must match");
    }
    return validate_compatible_storage_and_pair_rules(
        system, forcefield, model);
}

bg_status validate_handle_compatibility(
    const bg_context &context,
    const bg_system &system,
    const bg_forcefield &forcefield,
    const bg_direct_ewald_model_v1 &model) {
    if (context.unit_system != system.unit_system ||
        context.unit_system != forcefield.unit_system ||
        context.unit_system != model.unit_system) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "composite context, system, force field, and model units must match");
    }
    return validate_compatible_storage_and_pair_rules(
        system, forcefield, model);
}

bg_status evaluate_prevalidated(
    const bg_context &context,
    const bg_system &system,
    const bg_forcefield &forcefield,
    const bg_direct_ewald_model_v1 &model,
    bool compute_forces,
    Evaluation *out_evaluation,
    ewald::Error *out_error) {
    if (out_evaluation == nullptr || out_error == nullptr) {
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "composite evaluation or typed-error output is null");
    }
    *out_error = ewald::Error{};
    switch (context.backend) {
        case BG_BACKEND_CPP_CPU_REFERENCE:
        case BG_BACKEND_RUST_CPU:
            break;
        case BG_BACKEND_HIP_SAFE:
        case BG_BACKEND_HIP_FAST:
            return fail(
                BG_STATUS_UNSUPPORTED_BACKEND,
                "direct-Ewald composite HIP execution is unsupported and CPU fallback is forbidden");
        default:
            return fail(
                BG_STATUS_UNSUPPORTED_BACKEND,
                "selected backend has no direct-Ewald composite evaluator");
    }

    bg_system short_system = system;
    std::fill(short_system.charge.begin(), short_system.charge.end(), 0.0);

    cpu::Evaluation short_evaluation;
    bg_status status = BG_STATUS_OK;
    if (context.backend == BG_BACKEND_CPP_CPU_REFERENCE) {
        status = cpu::evaluate(
            short_system, forcefield, compute_forces, &short_evaluation);
    } else {
        status = rust_cpu::evaluate(
            short_system, forcefield, compute_forces, &short_evaluation);
    }
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (!short_energy_is_valid(short_evaluation)) {
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "short-range composite parent returned inconsistent energy");
    }

    ewald::Evaluation ewald_evaluation;
    if (context.backend == BG_BACKEND_CPP_CPU_REFERENCE) {
        status = ewald::cpp_cpu::evaluate(
            system, model, compute_forces, &ewald_evaluation, out_error);
    } else {
        status = ewald::rust_cpu::evaluate(
            system, model, compute_forces, &ewald_evaluation, out_error);
    }
    if (status != BG_STATUS_OK) {
        return out_error->code == BG_DIRECT_EWALD_ERROR_NONE
                   ? status
                   : status_for_typed_error(out_error->code);
    }
    if (out_error->code != BG_DIRECT_EWALD_ERROR_NONE ||
        !ewald_energy_is_valid(ewald_evaluation)) {
        *out_error = ewald::Error{};
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "direct-Ewald composite parent returned inconsistent energy or error state");
    }

    const double ewald_total = ewald_evaluation.energy.total();
    const double total =
        short_evaluation.energy.total_kcal_per_mol + ewald_total;
    if (!std::isfinite(total)) {
        return fail(
            BG_STATUS_NUMERICAL_ERROR,
            "composite total energy is not finite");
    }

    Evaluation candidate;
    if (compute_forces) {
        const std::size_t atom_count = model.atom_count;
        if (short_evaluation.force_x.size() != atom_count ||
            short_evaluation.force_y.size() != atom_count ||
            short_evaluation.force_z.size() != atom_count ||
            ewald_evaluation.forces.size() != atom_count) {
            return fail(
                BG_STATUS_INTERNAL_ERROR,
                "composite parent force counts are inconsistent");
        }
        candidate.forces.resize(atom_count);
        for (std::size_t atom = 0; atom < atom_count; ++atom) {
            candidate.forces[atom] = {{
                short_evaluation.force_x[atom] +
                    ewald_evaluation.forces[atom][0],
                short_evaluation.force_y[atom] +
                    ewald_evaluation.forces[atom][1],
                short_evaluation.force_z[atom] +
                    ewald_evaluation.forces[atom][2],
            }};
            if (std::any_of(
                    candidate.forces[atom].begin(),
                    candidate.forces[atom].end(),
                    [](double value) { return !std::isfinite(value); })) {
                return fail(
                    BG_STATUS_NUMERICAL_ERROR,
                    "a composite force component is not finite");
            }
        }
    }

    candidate.energy.short_harmonic_bond =
        short_evaluation.energy.harmonic_bond_kcal_per_mol;
    candidate.energy.short_harmonic_angle =
        short_evaluation.energy.harmonic_angle_kcal_per_mol;
    candidate.energy.short_periodic_torsion =
        short_evaluation.energy.periodic_torsion_kcal_per_mol;
    candidate.energy.short_lennard_jones =
        short_evaluation.energy.lennard_jones_kcal_per_mol;
    candidate.energy.short_coulomb =
        short_evaluation.energy.coulomb_kcal_per_mol;
    candidate.energy.short_total =
        short_evaluation.energy.total_kcal_per_mol;
    candidate.energy.ewald_real_space = ewald_evaluation.energy.real_space;
    candidate.energy.ewald_reciprocal_space =
        ewald_evaluation.energy.reciprocal_space;
    candidate.energy.ewald_self = ewald_evaluation.energy.self;
    candidate.energy.ewald_pair_correction =
        ewald_evaluation.energy.pair_correction;
    candidate.energy.ewald_total = ewald_total;
    candidate.energy.total = total;
    *out_evaluation = std::move(candidate);
    return BG_STATUS_OK;
}

}  // namespace betelgeuze::native::composite

extern "C" BG_API uint32_t BG_CALL
bg_direct_ewald_composite_abi_version(void) BG_NOEXCEPT {
    return BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION;
}

extern "C" BG_API uint32_t BG_CALL
bg_direct_ewald_composite_abi_version_major(void) BG_NOEXCEPT {
    return BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION_MAJOR;
}

extern "C" BG_API uint32_t BG_CALL
bg_direct_ewald_composite_abi_version_minor(void) BG_NOEXCEPT {
    return BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION_MINOR;
}

extern "C" BG_API const char *BG_CALL
bg_direct_ewald_composite_abi_version_string(void) BG_NOEXCEPT {
    return "1.0.0";
}

extern "C" BG_API bg_status BG_CALL
bg_direct_ewald_composite_energy_components_v1_init(
    bg_direct_ewald_composite_energy_components_v1 *energy,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::composite;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_composite_initializer(
            energy, caller_struct_size, sizeof(*energy), caller_abi_version,
            "bg_direct_ewald_composite_energy_components_v1");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *energy = bg_direct_ewald_composite_energy_components_v1{};
        energy->struct_size = static_cast<uint32_t>(sizeof(*energy));
        energy->abi_version = BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION;
        energy->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL
bg_direct_ewald_composite_force_soa_v1_init(
    bg_direct_ewald_composite_force_soa_v1 *forces,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::composite;
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_composite_initializer(
            forces, caller_struct_size, sizeof(*forces), caller_abi_version,
            "bg_direct_ewald_composite_force_soa_v1");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *forces = bg_direct_ewald_composite_force_soa_v1{};
        forces->struct_size = static_cast<uint32_t>(sizeof(*forces));
        forces->abi_version = BG_DIRECT_EWALD_COMPOSITE_ABI_VERSION;
        forces->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API const char *BG_CALL
bg_direct_ewald_composite_v1_profile_id(void) BG_NOEXCEPT {
    return betelgeuze::native::composite::kProfileId;
}

extern "C" BG_API bg_status BG_CALL
bg_context_evaluate_direct_ewald_composite_v1(
    const bg_context *context,
    const bg_system *system,
    const bg_forcefield *forcefield,
    const bg_direct_ewald_model_v1 *model,
    bg_direct_ewald_composite_energy_components_v1 *out_energy,
    bg_direct_ewald_composite_force_soa_v1 *out_forces,
    bg_direct_ewald_error_v1 *out_error) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::composite;
    return guarded_status([&]() -> bg_status {
        if (out_error == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "composite typed error must not be null");
        }
        bg_status status = validate_error_descriptor(*out_error);
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = validate_descriptor_overlap(out_energy, out_forces, out_error);
        if (status != BG_STATUS_OK) {
            return status;
        }
        if (out_energy != nullptr) {
            status = validate_energy_output(*out_energy);
            if (status != BG_STATUS_OK) {
                return status;
            }
        }
        if (out_forces != nullptr) {
            status = validate_force_output_descriptor(
                *out_forces);
            if (status != BG_STATUS_OK) {
                return status;
            }
        }
        if (context == nullptr || system == nullptr || forcefield == nullptr ||
            model == nullptr || out_energy == nullptr) {
            if (out_forces != nullptr) {
                status = validate_force_output_spans(
                    *out_forces, out_energy, out_error,
                    static_cast<std::size_t>(out_forces->atom_capacity));
                if (status != BG_STATUS_OK) {
                    return status;
                }
            }
            clear_error(out_error);
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "composite context, system, force field, model, and energy must not be null");
        }
        if (out_forces != nullptr) {
            status = validate_force_output_capacity(
                *out_forces, model->atom_count);
            if (status != BG_STATUS_OK) {
                return status;
            }
            status = validate_force_output_spans(
                *out_forces, out_energy, out_error, model->atom_count);
            if (status != BG_STATUS_OK) {
                return status;
            }
        }
        status = validate_output_system_disjoint(
            *system, *out_energy, out_forces, *out_error);
        if (status != BG_STATUS_OK) {
            return status;
        }
        clear_error(out_error);
        status = validate_handle_compatibility(
            *context, *system, *forcefield, *model);
        if (status != BG_STATUS_OK) {
            return status;
        }
        const bool compute_forces = out_forces != nullptr;
        Evaluation evaluation;
        ewald::Error typed_error;
        status = evaluate_prevalidated(
            *context, *system, *forcefield, *model, compute_forces,
            &evaluation, &typed_error);
        if (status != BG_STATUS_OK) {
            if (typed_error.code != BG_DIRECT_EWALD_ERROR_NONE) {
                commit_error(out_error, typed_error.code, typed_error.detail);
            }
            return status;
        }

        bg_direct_ewald_composite_energy_components_v1 committed_energy =
            *out_energy;
        committed_energy.short_harmonic_bond_kcal_per_mol =
            evaluation.energy.short_harmonic_bond;
        committed_energy.short_harmonic_angle_kcal_per_mol =
            evaluation.energy.short_harmonic_angle;
        committed_energy.short_periodic_torsion_kcal_per_mol =
            evaluation.energy.short_periodic_torsion;
        committed_energy.short_lennard_jones_kcal_per_mol =
            evaluation.energy.short_lennard_jones;
        committed_energy.short_coulomb_kcal_per_mol =
            evaluation.energy.short_coulomb;
        committed_energy.short_total_kcal_per_mol =
            evaluation.energy.short_total;
        committed_energy.ewald_real_space_kcal_per_mol =
            evaluation.energy.ewald_real_space;
        committed_energy.ewald_reciprocal_space_kcal_per_mol =
            evaluation.energy.ewald_reciprocal_space;
        committed_energy.ewald_self_kcal_per_mol =
            evaluation.energy.ewald_self;
        committed_energy.ewald_pair_correction_kcal_per_mol =
            evaluation.energy.ewald_pair_correction;
        committed_energy.ewald_total_kcal_per_mol =
            evaluation.energy.ewald_total;
        committed_energy.total_kcal_per_mol = evaluation.energy.total;

        if (compute_forces) {
            for (std::size_t atom = 0; atom < model->atom_count; ++atom) {
                out_forces->x_kcal_per_mol_angstrom[atom] =
                    evaluation.forces[atom][0];
                out_forces->y_kcal_per_mol_angstrom[atom] =
                    evaluation.forces[atom][1];
                out_forces->z_kcal_per_mol_angstrom[atom] =
                    evaluation.forces[atom][2];
            }
            out_forces->atom_count = static_cast<uint64_t>(model->atom_count);
        }
        *out_energy = committed_energy;
        return BG_STATUS_OK;
    });
}
