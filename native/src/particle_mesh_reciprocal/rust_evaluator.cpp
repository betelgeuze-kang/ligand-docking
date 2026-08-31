#include "rust_evaluator.hpp"

#include "../internal.hpp"
#include "rust_provider.h"

#include <cmath>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <type_traits>
#include <utility>
#include <vector>

namespace betelgeuze::native::particle_mesh_reciprocal::rust_cpu {
namespace {

constexpr std::size_t kMaxAtomCount = 4'096U;

static_assert(std::is_nothrow_move_assignable_v<Evaluation>);
static_assert(std::is_nothrow_swappable_v<decltype(Evaluation{}.forces)>);
static_assert(std::is_nothrow_copy_assignable_v<std::array<double, 3>>);

template <typename Value>
const Value *data_or_null(const std::vector<Value> &values) noexcept {
    return values.empty() ? nullptr : values.data();
}

bg_status normalize_provider_status(std::int32_t status) noexcept {
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

bool provider_code_is_valid(std::int32_t code) noexcept {
    return code >= BG_RUST_PARTICLE_MESH_RECIPROCAL_ERROR_NONE &&
           code <= BG_RUST_PARTICLE_MESH_RECIPROCAL_ERROR_NONFINITE_RESULT;
}

class EvaluationForceStorageRollback final {
  public:
    EvaluationForceStorageRollback(
        Evaluation *output,
        Evaluation *candidate,
        bool enabled) noexcept
        : output_(enabled ? output : nullptr),
          candidate_(enabled ? candidate : nullptr) {
        if (output_ != nullptr) {
            candidate_->forces.swap(output_->forces);
        }
    }

    EvaluationForceStorageRollback(
        const EvaluationForceStorageRollback &) = delete;
    EvaluationForceStorageRollback &operator=(
        const EvaluationForceStorageRollback &) = delete;

    ~EvaluationForceStorageRollback() noexcept {
        if (output_ != nullptr) {
            candidate_->forces.swap(output_->forces);
        }
    }

    void commit() noexcept {
        output_ = nullptr;
        candidate_ = nullptr;
    }

  private:
    Evaluation *output_;
    Evaluation *candidate_;
};

}  // namespace

ProviderForceScratch::~ProviderForceScratch() noexcept {
    bg_rust_particle_mesh_reciprocal_particle_assignment_scratch_destroy_v1(
        &particle_assignment_scratch);
    bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_destroy_v1(
        &neutrality_sort_scratch);
    bg_rust_particle_mesh_reciprocal_workspace_destroy_v1(
        &reciprocal_workspace);
}

static bg_status evaluate_impl(
    const bg_system &system,
    const bg_particle_mesh_reciprocal_model_v1 &model,
    bool compute_forces,
    bool reuse_force_storage,
    ProviderForceScratch *provider_force_scratch,
    Evaluation *out_evaluation,
    ProviderForceSourceResult *out_provider_force_source_result,
    Error *out_error) {
    static_assert(
        std::is_standard_layout_v<
            bg_rust_particle_mesh_reciprocal_system_v1>);
    static_assert(
        std::is_standard_layout_v<
            bg_rust_particle_mesh_reciprocal_model_v1>);
    static_assert(
        std::is_standard_layout_v<
            bg_rust_particle_mesh_reciprocal_energy_v1>);
    static_assert(
        std::is_standard_layout_v<
            bg_rust_particle_mesh_reciprocal_force_output_v1>);
    static_assert(
        std::is_standard_layout_v<
            bg_rust_particle_mesh_reciprocal_workspace_v1>);
    static_assert(
        std::is_standard_layout_v<
            bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_v1>);
    static_assert(
        std::is_standard_layout_v<
            bg_rust_particle_mesh_reciprocal_particle_assignment_scratch_v1>);
    static_assert(
        std::is_standard_layout_v<
            bg_rust_particle_mesh_reciprocal_error_v1>);
    static_assert(
        sizeof(bg_rust_particle_mesh_reciprocal_system_v1) == 80U);
    static_assert(
        sizeof(bg_rust_particle_mesh_reciprocal_model_v1) == 96U);
    static_assert(
        sizeof(bg_rust_particle_mesh_reciprocal_energy_v1) == 48U);
    static_assert(
        sizeof(bg_rust_particle_mesh_reciprocal_force_output_v1) == 72U);
    static_assert(
        sizeof(bg_rust_particle_mesh_reciprocal_workspace_v1) == 72U);
    static_assert(
        alignof(bg_rust_particle_mesh_reciprocal_workspace_v1) == 8U);
    static_assert(
        offsetof(bg_rust_particle_mesh_reciprocal_workspace_v1, struct_size) ==
        0U);
    static_assert(
        offsetof(bg_rust_particle_mesh_reciprocal_workspace_v1, abi_version) ==
        4U);
    static_assert(
        offsetof(bg_rust_particle_mesh_reciprocal_workspace_v1, state) == 8U);
    static_assert(
        offsetof(bg_rust_particle_mesh_reciprocal_workspace_v1, reserved0) ==
        12U);
    static_assert(
        offsetof(bg_rust_particle_mesh_reciprocal_workspace_v1, storage) ==
        16U);
    static_assert(
        offsetof(bg_rust_particle_mesh_reciprocal_workspace_v1, length) ==
        24U);
    static_assert(
        offsetof(bg_rust_particle_mesh_reciprocal_workspace_v1, capacity) ==
        32U);
    static_assert(
        offsetof(bg_rust_particle_mesh_reciprocal_workspace_v1, reserved) ==
        40U);
    static_assert(
        sizeof(
            bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_v1) ==
        72U);
    static_assert(
        alignof(
            bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_v1) ==
        8U);
    static_assert(
        offsetof(
            bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_v1,
            struct_size) == 0U);
    static_assert(
        offsetof(
            bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_v1,
            abi_version) == 4U);
    static_assert(
        offsetof(
            bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_v1,
            state) == 8U);
    static_assert(
        offsetof(
            bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_v1,
            reserved0) == 12U);
    static_assert(
        offsetof(
            bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_v1,
            storage) == 16U);
    static_assert(
        offsetof(
            bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_v1,
            length) == 24U);
    static_assert(
        offsetof(
            bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_v1,
            capacity) == 32U);
    static_assert(
        offsetof(
            bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_v1,
            reserved) == 40U);
    static_assert(
        sizeof(
            bg_rust_particle_mesh_reciprocal_particle_assignment_scratch_v1) ==
        72U);
    static_assert(
        alignof(
            bg_rust_particle_mesh_reciprocal_particle_assignment_scratch_v1) ==
        8U);
    static_assert(
        offsetof(
            bg_rust_particle_mesh_reciprocal_particle_assignment_scratch_v1,
            struct_size) == 0U);
    static_assert(
        offsetof(
            bg_rust_particle_mesh_reciprocal_particle_assignment_scratch_v1,
            abi_version) == 4U);
    static_assert(
        offsetof(
            bg_rust_particle_mesh_reciprocal_particle_assignment_scratch_v1,
            state) == 8U);
    static_assert(
        offsetof(
            bg_rust_particle_mesh_reciprocal_particle_assignment_scratch_v1,
            reserved0) == 12U);
    static_assert(
        offsetof(
            bg_rust_particle_mesh_reciprocal_particle_assignment_scratch_v1,
            storage) == 16U);
    static_assert(
        offsetof(
            bg_rust_particle_mesh_reciprocal_particle_assignment_scratch_v1,
            logical_length_bytes) == 24U);
    static_assert(
        offsetof(
            bg_rust_particle_mesh_reciprocal_particle_assignment_scratch_v1,
            allocation_capacity_bytes) == 32U);
    static_assert(
        offsetof(
            bg_rust_particle_mesh_reciprocal_particle_assignment_scratch_v1,
            reserved) == 40U);
    static_assert(
        BG_RUST_PARTICLE_MESH_RECIPROCAL_WORKSPACE_STATE_EMPTY ==
        UINT32_C(0));
    static_assert(
        BG_RUST_PARTICLE_MESH_RECIPROCAL_WORKSPACE_STATE_READY ==
        UINT32_C(0x52575331));
    static_assert(
        BG_RUST_PARTICLE_MESH_RECIPROCAL_WORKSPACE_STATE_LEASED ==
        UINT32_C(0x4c455331));
    static_assert(
        BG_RUST_PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_STATE_EMPTY ==
        UINT32_C(0));
    static_assert(
        BG_RUST_PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_STATE_READY ==
        UINT32_C(0x4e535331));
    static_assert(
        BG_RUST_PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_STATE_LEASED ==
        UINT32_C(0x4e534c31));
    static_assert(!std::is_copy_constructible_v<ProviderForceScratch>);
    static_assert(!std::is_copy_assignable_v<ProviderForceScratch>);
    static_assert(!std::is_move_constructible_v<ProviderForceScratch>);
    static_assert(!std::is_move_assignable_v<ProviderForceScratch>);
    static_assert(
        sizeof(bg_rust_particle_mesh_reciprocal_error_v1) == 304U);
#define BG_ASSERT_PMR_CODE(name)                                          \
    static_assert(                                                       \
        static_cast<std::int32_t>(                                      \
            BG_RUST_PARTICLE_MESH_RECIPROCAL_ERROR_##name) ==           \
        static_cast<std::int32_t>(                                      \
            BG_PARTICLE_MESH_RECIPROCAL_ERROR_##name))
    BG_ASSERT_PMR_CODE(NONE);
    BG_ASSERT_PMR_CODE(EMPTY_SYSTEM);
    BG_ASSERT_PMR_CODE(CAPACITY_EXCEEDED);
    BG_ASSERT_PMR_CODE(CHARGE_COUNT_MISMATCH);
    BG_ASSERT_PMR_CODE(NONFINITE_COORDINATE);
    BG_ASSERT_PMR_CODE(NONFINITE_CHARGE);
    BG_ASSERT_PMR_CODE(NON_NEUTRAL_SYSTEM);
    BG_ASSERT_PMR_CODE(INVALID_CELL);
    BG_ASSERT_PMR_CODE(INVALID_PARAMETER);
    BG_ASSERT_PMR_CODE(INVALID_MESH);
    BG_ASSERT_PMR_CODE(NONFINITE_RESULT);
#undef BG_ASSERT_PMR_CODE

    if (out_error == nullptr ||
        ((out_evaluation == nullptr) ==
         (out_provider_force_source_result == nullptr))) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "Rust particle-mesh reciprocal evaluation requires exactly one evaluation or provider-force-source result output and a non-null error output");
    }
    *out_error = Error{};
    if (out_provider_force_source_result != nullptr &&
        (!compute_forces || !reuse_force_storage)) {
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "Rust particle-mesh reciprocal provider-force source requires reusable force-producing evaluation");
    }
    if (reuse_force_storage && provider_force_scratch == nullptr) {
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "Rust particle-mesh reciprocal reusable provider-force scratch must not be null");
    }
    const std::size_t atom_count = system.position_x.size();
    if (atom_count == 0U) {
        out_error->code =
            BG_PARTICLE_MESH_RECIPROCAL_ERROR_EMPTY_SYSTEM;
        out_error->detail = "at least one particle is required";
        return BG_STATUS_INVALID_ARGUMENT;
    }
    if (atom_count > kMaxAtomCount) {
        out_error->code =
            BG_PARTICLE_MESH_RECIPROCAL_ERROR_CAPACITY_EXCEEDED;
        out_error->detail = "particle count exceeds 4096";
        return BG_STATUS_CAPACITY_OVERFLOW;
    }
    if (system.position_y.size() != atom_count ||
        system.position_z.size() != atom_count ||
        system.charge.size() != atom_count ||
        model.atom_count != atom_count) {
        out_error->code =
            BG_PARTICLE_MESH_RECIPROCAL_ERROR_CHARGE_COUNT_MISMATCH;
        out_error->detail =
            "system position/charge count does not match the particle-mesh reciprocal model";
        return BG_STATUS_INVALID_ARGUMENT;
    }
    if (bg_rust_particle_mesh_reciprocal_provider_abi_version_v1() !=
        BG_RUST_PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION) {
        return fail(
            BG_STATUS_BACKEND_UNAVAILABLE,
            "Rust particle-mesh reciprocal provider ABI is unavailable or incompatible");
    }

    bg_rust_particle_mesh_reciprocal_system_v1 provider_system{};
    provider_system.struct_size =
        static_cast<std::uint32_t>(sizeof(provider_system));
    provider_system.abi_version =
        BG_RUST_PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION;
    provider_system.atom_count = atom_count;
    provider_system.position_x = data_or_null(system.position_x);
    provider_system.position_y = data_or_null(system.position_y);
    provider_system.position_z = data_or_null(system.position_z);
    provider_system.charge = data_or_null(system.charge);

    bg_rust_particle_mesh_reciprocal_model_v1 provider_model{};
    provider_model.struct_size =
        static_cast<std::uint32_t>(sizeof(provider_model));
    provider_model.abi_version =
        BG_RUST_PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION;
    for (std::size_t axis = 0U; axis < 3U; ++axis) {
        provider_model.cell_lengths_angstrom[axis] =
            model.cell_lengths_angstrom[axis];
        provider_model.mesh_dimensions[axis] = model.mesh_dimensions[axis];
    }
    provider_model.alpha_per_angstrom = model.alpha_per_angstrom;
    provider_model.dielectric = model.dielectric;

    bg_rust_particle_mesh_reciprocal_energy_v1 provider_energy{};
    provider_energy.struct_size =
        static_cast<std::uint32_t>(sizeof(provider_energy));
    provider_energy.abi_version =
        BG_RUST_PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION;

    Evaluation candidate;
    EvaluationForceStorageRollback evaluation_force_storage_rollback{
        out_evaluation, &candidate,
        compute_forces && reuse_force_storage && out_evaluation != nullptr};
    std::optional<ProviderForceScratch> local_provider_force_scratch;
    ProviderForceScratch &active_provider_force_scratch =
        reuse_force_storage ? *provider_force_scratch
                            : local_provider_force_scratch.emplace();

    bg_rust_particle_mesh_reciprocal_error_v1 provider_error{};
    provider_error.struct_size =
        static_cast<std::uint32_t>(sizeof(provider_error));
    provider_error.abi_version =
        BG_RUST_PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION;
    std::int32_t raw_status;
    if (compute_forces) {
        bg_rust_particle_mesh_reciprocal_force_output_v1 provider_forces{};
        active_provider_force_scratch.x.resize(atom_count);
        active_provider_force_scratch.y.resize(atom_count);
        active_provider_force_scratch.z.resize(atom_count);
        provider_forces.struct_size =
            static_cast<std::uint32_t>(sizeof(provider_forces));
        provider_forces.abi_version =
            BG_RUST_PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION;
        provider_forces.capacity = atom_count;
        provider_forces.x = active_provider_force_scratch.x.data();
        provider_forces.y = active_provider_force_scratch.y.data();
        provider_forces.z = active_provider_force_scratch.z.data();
        raw_status = bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_and_neutrality_sort_scratch_and_particle_assignment_scratch_v1(
            &provider_system, &provider_model,
            &active_provider_force_scratch.reciprocal_workspace,
            &active_provider_force_scratch.neutrality_sort_scratch,
            &active_provider_force_scratch.particle_assignment_scratch,
            &provider_energy, &provider_forces, &provider_error);
    } else {
        raw_status =
            bg_rust_particle_mesh_reciprocal_evaluate_energy_with_workspace_and_neutrality_sort_scratch_and_particle_assignment_scratch_v1(
                &provider_system, &provider_model,
                &active_provider_force_scratch.reciprocal_workspace,
                &active_provider_force_scratch.neutrality_sort_scratch,
                &active_provider_force_scratch.particle_assignment_scratch,
                &provider_energy, &provider_error);
    }
    const bg_status status = normalize_provider_status(raw_status);
    provider_error.detail[
        BG_RUST_PARTICLE_MESH_RECIPROCAL_ERROR_CAPACITY - 1U] = '\0';
    if (status != BG_STATUS_OK) {
        if (!provider_code_is_valid(provider_error.typed_code)) {
            return fail(
                BG_STATUS_INTERNAL_ERROR,
                "Rust particle-mesh reciprocal provider returned an unknown typed error code");
        }
        if (provider_error.typed_code !=
            BG_RUST_PARTICLE_MESH_RECIPROCAL_ERROR_NONE) {
            out_error->code =
                static_cast<bg_particle_mesh_reciprocal_error_code>(
                    provider_error.typed_code);
            out_error->detail = provider_error.detail;
            return status;
        }
        const char *detail = provider_error.detail[0] == '\0'
                                 ? "Rust particle-mesh reciprocal provider failed without a diagnostic"
                                 : provider_error.detail;
        return fail(status, detail);
    }
    if (provider_error.typed_code !=
        BG_RUST_PARTICLE_MESH_RECIPROCAL_ERROR_NONE) {
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "Rust particle-mesh reciprocal provider returned a typed error on success");
    }
    if (!std::isfinite(provider_energy.reciprocal_space_kcal_per_mol)) {
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "Rust particle-mesh reciprocal provider returned non-finite energy on success");
    }
    candidate.reciprocal_space_kcal_per_mol =
        provider_energy.reciprocal_space_kcal_per_mol;
    if (compute_forces) {
        for (std::size_t atom = 0U; atom < atom_count; ++atom) {
            if (!std::isfinite(active_provider_force_scratch.x[atom]) ||
                !std::isfinite(active_provider_force_scratch.y[atom]) ||
                !std::isfinite(active_provider_force_scratch.z[atom])) {
                return fail(
                    BG_STATUS_INTERNAL_ERROR,
                    "Rust particle-mesh reciprocal provider returned non-finite force on success");
            }
        }
        if (out_evaluation != nullptr) {
            candidate.forces.resize(atom_count);
            for (std::size_t atom = 0U; atom < atom_count; ++atom) {
                candidate.forces[atom] = {
                    active_provider_force_scratch.x[atom],
                    active_provider_force_scratch.y[atom],
                    active_provider_force_scratch.z[atom]};
            }
        }
    }
    if (out_evaluation != nullptr) {
        evaluation_force_storage_rollback.commit();
        *out_evaluation = std::move(candidate);
    } else {
        *out_provider_force_source_result = ProviderForceSourceResult{
            candidate.reciprocal_space_kcal_per_mol};
    }
    return BG_STATUS_OK;
}

bg_status evaluate(
    const bg_system &system,
    const bg_particle_mesh_reciprocal_model_v1 &model,
    bool compute_forces,
    Evaluation *out_evaluation,
    Error *out_error) {
    return evaluate_impl(
        system, model, compute_forces, false, nullptr, out_evaluation, nullptr,
        out_error);
}

bg_status evaluate_reusing_force_storage(
    const bg_system &system,
    const bg_particle_mesh_reciprocal_model_v1 &model,
    bool compute_forces,
    ProviderForceScratch *provider_force_scratch,
    Evaluation *out_evaluation,
    Error *out_error) {
    return evaluate_impl(
        system, model, compute_forces, true, provider_force_scratch,
        out_evaluation, nullptr, out_error);
}

bg_status evaluate_reusing_provider_force_storage(
    const bg_system &system,
    const bg_particle_mesh_reciprocal_model_v1 &model,
    ProviderForceScratch *provider_force_scratch,
    ProviderForceSourceResult *out_result,
    Error *out_error) {
    return evaluate_impl(
        system, model, true, true, provider_force_scratch, nullptr,
        out_result, out_error);
}

}  // namespace betelgeuze::native::particle_mesh_reciprocal::rust_cpu
