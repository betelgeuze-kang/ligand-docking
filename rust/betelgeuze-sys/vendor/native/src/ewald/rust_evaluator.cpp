#include "rust_evaluator.hpp"

#include "../internal.hpp"
#include "rust_provider.h"

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <type_traits>
#include <utility>
#include <vector>

namespace betelgeuze::native::ewald::rust_cpu {
namespace {

constexpr std::size_t kMaxAtomCount = 4'096;

template <typename Value>
const Value *data_or_null(const std::vector<Value> &values) noexcept {
    return values.empty() ? nullptr : values.data();
}

bg_status normalize_provider_status(int32_t status) noexcept {
    switch (status) {
        case BG_STATUS_OK:
        case BG_STATUS_INVALID_ARGUMENT:
        case BG_STATUS_ABI_MISMATCH:
        case BG_STATUS_UNSUPPORTED_BACKEND:
        case BG_STATUS_BACKEND_UNAVAILABLE:
        case BG_STATUS_OUT_OF_MEMORY:
        case BG_STATUS_CAPACITY_OVERFLOW:
        case BG_STATUS_BUFFER_TOO_SMALL:
        case BG_STATUS_BACKEND_ERROR:
        case BG_STATUS_INTERNAL_ERROR:
        case BG_STATUS_NUMERICAL_ERROR:
            return status;
        default:
            return BG_STATUS_INTERNAL_ERROR;
    }
}

bool provider_code_is_valid(int32_t code) noexcept {
    return code >= BG_RUST_DIRECT_EWALD_ERROR_NONE &&
           code <= BG_RUST_DIRECT_EWALD_ERROR_NONFINITE_RESULT;
}

}  // namespace

static bg_status evaluate_impl(
    const bg_system &system,
    const bg_direct_ewald_model_v1 &model,
    bool compute_forces,
    bool reuse_force_storage,
    Evaluation *out_evaluation,
    Error *out_error) {
    static_assert(std::is_standard_layout_v<bg_rust_direct_ewald_system_v1>);
    static_assert(std::is_standard_layout_v<bg_rust_direct_ewald_pair_rule_v1>);
    static_assert(std::is_standard_layout_v<bg_rust_direct_ewald_model_v1>);
    static_assert(std::is_standard_layout_v<bg_rust_direct_ewald_energy_v1>);
    static_assert(
        std::is_standard_layout_v<bg_rust_direct_ewald_force_output_v1>);
    static_assert(std::is_standard_layout_v<bg_rust_direct_ewald_error_v1>);
    static_assert(sizeof(bg_rust_direct_ewald_system_v1) == 80U);
    static_assert(sizeof(bg_rust_direct_ewald_pair_rule_v1) == 40U);
    static_assert(sizeof(bg_rust_direct_ewald_model_v1) == 128U);
    static_assert(sizeof(bg_rust_direct_ewald_energy_v1) == 80U);
    static_assert(sizeof(bg_rust_direct_ewald_force_output_v1) == 72U);
    static_assert(sizeof(bg_rust_direct_ewald_error_v1) == 304U);
#define BG_ASSERT_DIRECT_EWALD_CODE(name)                                  \
    static_assert(                                                        \
        static_cast<int32_t>(BG_RUST_DIRECT_EWALD_ERROR_##name) ==        \
        static_cast<int32_t>(BG_DIRECT_EWALD_ERROR_##name))
    BG_ASSERT_DIRECT_EWALD_CODE(NONE);
    BG_ASSERT_DIRECT_EWALD_CODE(EMPTY_SYSTEM);
    BG_ASSERT_DIRECT_EWALD_CODE(CAPACITY_EXCEEDED);
    BG_ASSERT_DIRECT_EWALD_CODE(CHARGE_COUNT_MISMATCH);
    BG_ASSERT_DIRECT_EWALD_CODE(NONFINITE_COORDINATE);
    BG_ASSERT_DIRECT_EWALD_CODE(NONFINITE_CHARGE);
    BG_ASSERT_DIRECT_EWALD_CODE(NON_NEUTRAL_SYSTEM);
    BG_ASSERT_DIRECT_EWALD_CODE(INVALID_CELL);
    BG_ASSERT_DIRECT_EWALD_CODE(CUTOFF_VIOLATES_MINIMUM_IMAGE);
    BG_ASSERT_DIRECT_EWALD_CODE(INVALID_PARAMETER);
    BG_ASSERT_DIRECT_EWALD_CODE(ATOM_INDEX_OUT_OF_RANGE);
    BG_ASSERT_DIRECT_EWALD_CODE(REPEATED_ATOM_INDEX);
    BG_ASSERT_DIRECT_EWALD_CODE(DUPLICATE_PAIR_RULE);
    BG_ASSERT_DIRECT_EWALD_CODE(CONFLICTING_PAIR_RULE);
    BG_ASSERT_DIRECT_EWALD_CODE(AMBIGUOUS_PAIR_CORRECTION_IMAGE);
    BG_ASSERT_DIRECT_EWALD_CODE(AMBIGUOUS_REAL_SPACE_CUTOFF);
    BG_ASSERT_DIRECT_EWALD_CODE(AMBIGUOUS_MINIMUM_PAIR_DISTANCE);
    BG_ASSERT_DIRECT_EWALD_CODE(PAIR_BELOW_MINIMUM_DISTANCE);
    BG_ASSERT_DIRECT_EWALD_CODE(DAMPING_UNDERFLOW);
    BG_ASSERT_DIRECT_EWALD_CODE(PHASE_UNDERFLOW);
    BG_ASSERT_DIRECT_EWALD_CODE(NONFINITE_RESULT);
#undef BG_ASSERT_DIRECT_EWALD_CODE

    if (out_evaluation == nullptr || out_error == nullptr) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "Rust direct-Ewald evaluation and error outputs must not be null");
    }
    *out_error = Error{};
    if (bg_rust_direct_ewald_provider_abi_version_v1() !=
        BG_RUST_DIRECT_EWALD_PROVIDER_ABI_VERSION) {
        return fail(
            BG_STATUS_BACKEND_UNAVAILABLE,
            "Rust direct-Ewald provider ABI is unavailable or incompatible");
    }
    const std::size_t atom_count = system.position_x.size();
    if (system.position_y.size() != atom_count ||
        system.position_z.size() != atom_count ||
        system.charge.size() != atom_count ||
        (atom_count > 0U && atom_count <= kMaxAtomCount &&
         model.atom_count != atom_count)) {
        out_error->code = BG_DIRECT_EWALD_ERROR_CHARGE_COUNT_MISMATCH;
        out_error->detail =
            "system position/charge count does not match the Ewald model";
        return BG_STATUS_INVALID_ARGUMENT;
    }

    bg_rust_direct_ewald_system_v1 provider_system{};
    provider_system.struct_size =
        static_cast<uint32_t>(sizeof(provider_system));
    provider_system.abi_version = BG_RUST_DIRECT_EWALD_PROVIDER_ABI_VERSION;
    provider_system.atom_count = atom_count;
    provider_system.position_x = data_or_null(system.position_x);
    provider_system.position_y = data_or_null(system.position_y);
    provider_system.position_z = data_or_null(system.position_z);
    provider_system.charge = data_or_null(system.charge);

    std::vector<bg_rust_direct_ewald_pair_rule_v1> provider_pair_rules;
    provider_pair_rules.reserve(model.pair_rules.size());
    for (const PairRule &rule : model.pair_rules) {
        bg_rust_direct_ewald_pair_rule_v1 provider_rule{};
        provider_rule.atom_i = rule.atom_i;
        provider_rule.atom_j = rule.atom_j;
        provider_rule.coulomb_scale = rule.coulomb_scale;
        provider_pair_rules.push_back(provider_rule);
    }

    bg_rust_direct_ewald_model_v1 provider_model{};
    provider_model.struct_size = static_cast<uint32_t>(sizeof(provider_model));
    provider_model.abi_version = BG_RUST_DIRECT_EWALD_PROVIDER_ABI_VERSION;
    for (std::size_t axis = 0; axis < 3; ++axis) {
        provider_model.cell_lengths_angstrom[axis] =
            model.cell_lengths_angstrom[axis];
        provider_model.reciprocal_max_indices[axis] =
            model.reciprocal_max_indices[axis];
    }
    provider_model.alpha_per_angstrom = model.alpha_per_angstrom;
    provider_model.real_space_cutoff_angstrom =
        model.real_space_cutoff_angstrom;
    provider_model.dielectric = model.dielectric;
    provider_model.minimum_pair_distance_angstrom =
        model.minimum_pair_distance_angstrom;
    provider_model.pair_rule_count = provider_pair_rules.size();
    provider_model.pair_rules = data_or_null(provider_pair_rules);

    bg_rust_direct_ewald_energy_v1 provider_energy{};
    provider_energy.struct_size = static_cast<uint32_t>(sizeof(provider_energy));
    provider_energy.abi_version = BG_RUST_DIRECT_EWALD_PROVIDER_ABI_VERSION;

    Evaluation candidate;
    if (compute_forces && reuse_force_storage) {
        candidate.forces.swap(out_evaluation->forces);
    }
    bg_rust_direct_ewald_force_output_v1 provider_forces{};
    bg_rust_direct_ewald_force_output_v1 *provider_force_pointer = nullptr;
    std::vector<double> force_x;
    std::vector<double> force_y;
    std::vector<double> force_z;
    if (compute_forces) {
        force_x.resize(atom_count);
        force_y.resize(atom_count);
        force_z.resize(atom_count);
        provider_forces.struct_size =
            static_cast<uint32_t>(sizeof(provider_forces));
        provider_forces.abi_version =
            BG_RUST_DIRECT_EWALD_PROVIDER_ABI_VERSION;
        provider_forces.capacity = atom_count;
        provider_forces.x = force_x.data();
        provider_forces.y = force_y.data();
        provider_forces.z = force_z.data();
        provider_force_pointer = &provider_forces;
    }

    bg_rust_direct_ewald_error_v1 provider_error{};
    provider_error.struct_size = static_cast<uint32_t>(sizeof(provider_error));
    provider_error.abi_version = BG_RUST_DIRECT_EWALD_PROVIDER_ABI_VERSION;

    const int32_t raw_status = bg_rust_direct_ewald_evaluate_v1(
        &provider_system, &provider_model, compute_forces ? UINT8_C(1) : UINT8_C(0),
        &provider_energy, provider_force_pointer, &provider_error);
    const bg_status status = normalize_provider_status(raw_status);
    provider_error.detail[BG_RUST_DIRECT_EWALD_ERROR_CAPACITY - 1U] = '\0';
    if (status != BG_STATUS_OK) {
        if (!provider_code_is_valid(provider_error.typed_code)) {
            return fail(
                BG_STATUS_INTERNAL_ERROR,
                "Rust direct-Ewald provider returned an unknown typed error code");
        }
        if (provider_error.typed_code != BG_RUST_DIRECT_EWALD_ERROR_NONE) {
            out_error->code =
                static_cast<bg_direct_ewald_error_code>(provider_error.typed_code);
            out_error->detail = provider_error.detail;
            return status;
        }
        const char *detail = provider_error.detail[0] == '\0'
                                 ? "Rust direct-Ewald provider failed without a diagnostic"
                                 : provider_error.detail;
        return fail(status, detail);
    }
    if (provider_error.typed_code != BG_RUST_DIRECT_EWALD_ERROR_NONE) {
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "Rust direct-Ewald provider returned a typed error on success");
    }

    candidate.energy.real_space = provider_energy.real_space_kcal_per_mol;
    candidate.energy.reciprocal_space =
        provider_energy.reciprocal_space_kcal_per_mol;
    candidate.energy.self = provider_energy.self_kcal_per_mol;
    candidate.energy.pair_correction =
        provider_energy.pair_correction_kcal_per_mol;
    if (candidate.energy.total() != provider_energy.total_kcal_per_mol) {
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "Rust direct-Ewald provider returned an inconsistent total energy");
    }
    if (compute_forces) {
        candidate.forces.resize(atom_count);
        for (std::size_t atom = 0; atom < atom_count; ++atom) {
            candidate.forces[atom] = {
                force_x[atom], force_y[atom], force_z[atom]};
        }
    }
    *out_evaluation = std::move(candidate);
    return BG_STATUS_OK;
}

bg_status evaluate(
    const bg_system &system,
    const bg_direct_ewald_model_v1 &model,
    bool compute_forces,
    Evaluation *out_evaluation,
    Error *out_error) {
    return evaluate_impl(
        system, model, compute_forces, false, out_evaluation, out_error);
}

bg_status evaluate_reusing_force_storage(
    const bg_system &system,
    const bg_direct_ewald_model_v1 &model,
    bool compute_forces,
    Evaluation *out_evaluation,
    Error *out_error) {
    return evaluate_impl(
        system, model, compute_forces, true, out_evaluation, out_error);
}

}  // namespace betelgeuze::native::ewald::rust_cpu
