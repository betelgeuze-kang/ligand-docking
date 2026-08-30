#include "particle_mesh_ewald_composite_dynamics.hpp"

#include "particle_mesh_ewald_composite_evaluator.hpp"
#include "../dynamics/sha256.hpp"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <memory>
#include <string>
#include <utility>
#include <vector>

namespace betelgeuze::native::composite::dynamics {
namespace {

constexpr const char *kProfileId =
    "betelgeuze.native_particle_mesh_ewald_composite_dynamics/1.0.0";
constexpr uint32_t kEvaluatorFamily = UINT32_C(1);
constexpr uint32_t kEvaluatorSchema = UINT32_C(1);

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

bool fixed_storage_overlaps(
    const void *pointer,
    std::size_t byte_count,
    const ByteRange &output) noexcept {
    if (pointer == nullptr || byte_count == 0U) {
        return false;
    }
    ByteRange input;
    return !make_byte_range(pointer, byte_count, &input) ||
           ranges_overlap(input, output);
}

template <typename Type>
bool vector_storage_overlaps(
    const std::vector<Type> &values,
    const ByteRange &output) noexcept {
    if (values.empty()) {
        return false;
    }
    if (values.size() >
        std::numeric_limits<std::size_t>::max() / sizeof(Type)) {
        return true;
    }
    return fixed_storage_overlaps(
        values.data(), values.size() * sizeof(Type), output);
}

bool rust_reciprocal_workspace_storage_overlaps(
    const bg_rust_particle_mesh_reciprocal_workspace_v1 &workspace,
    const ByteRange &output) noexcept {
    constexpr std::size_t kElementSize =
        BG_RUST_PARTICLE_MESH_RECIPROCAL_WORKSPACE_ELEMENT_SIZE_BYTES;
    static_assert(kElementSize == 2U * sizeof(double));
    if (workspace.length > workspace.capacity) {
        return true;
    }
    if (workspace.capacity == 0U) {
        return workspace.storage != nullptr || workspace.length != 0U;
    }
    if (workspace.storage == nullptr ||
        workspace.capacity >
            std::numeric_limits<std::size_t>::max() / kElementSize) {
        return true;
    }
    return fixed_storage_overlaps(
        workspace.storage, workspace.capacity * kElementSize, output);
}

bool rust_reciprocal_neutrality_sort_scratch_storage_overlaps(
    const bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_v1 &scratch,
    const ByteRange &output) noexcept {
    constexpr std::size_t kElementSize =
        BG_RUST_PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_ELEMENT_SIZE_BYTES;
    static_assert(kElementSize == sizeof(double));
    if (scratch.length > scratch.capacity) {
        return true;
    }
    if (scratch.capacity == 0U) {
        return scratch.storage != nullptr || scratch.length != 0U;
    }
    if (scratch.storage == nullptr ||
        scratch.capacity >
            std::numeric_limits<std::size_t>::max() / kElementSize) {
        return true;
    }
    return fixed_storage_overlaps(
        scratch.storage, scratch.capacity * kElementSize, output);
}

bool counted_storage_overlaps(
    const void *pointer,
    uint64_t element_count,
    std::size_t element_size,
    const ByteRange &output) noexcept {
    if (pointer == nullptr || element_count == UINT64_C(0) ||
        element_size == 0U) {
        return false;
    }
    const std::uintptr_t begin = reinterpret_cast<std::uintptr_t>(pointer);
    if (output.end <= begin) {
        return false;
    }
    if (output.begin < begin) {
        return true;
    }
    const std::uintptr_t element_offset =
        (output.begin - begin) / element_size;
    if (element_offset > std::numeric_limits<uint64_t>::max()) {
        return false;
    }
    return element_count > static_cast<uint64_t>(element_offset);
}

bool system_storage_overlaps(
    const bg_system &system,
    const ByteRange &output) noexcept {
    return vector_storage_overlaps(system.position_x, output) ||
           vector_storage_overlaps(system.position_y, output) ||
           vector_storage_overlaps(system.position_z, output) ||
           vector_storage_overlaps(system.velocity_x, output) ||
           vector_storage_overlaps(system.velocity_y, output) ||
           vector_storage_overlaps(system.velocity_z, output) ||
           vector_storage_overlaps(system.mass, output) ||
           vector_storage_overlaps(system.charge, output);
}

bool evaluation_storage_overlaps(
    const cpu::Evaluation &evaluation,
    const ByteRange &output) noexcept {
    return vector_storage_overlaps(evaluation.force_x, output) ||
           vector_storage_overlaps(evaluation.force_y, output) ||
           vector_storage_overlaps(evaluation.force_z, output);
}

bool evaluation_storage_overlaps(
    const ewald::Evaluation &evaluation,
    const ByteRange &output) noexcept {
    return vector_storage_overlaps(evaluation.forces, output);
}

bool evaluation_storage_overlaps(
    const particle_mesh_reciprocal::Evaluation &evaluation,
    const ByteRange &output) noexcept {
    return vector_storage_overlaps(evaluation.forces, output);
}

bool forcefield_storage_overlaps(
    const bg_forcefield &forcefield,
    const ByteRange &output) noexcept {
    return vector_storage_overlaps(forcefield.sigma, output) ||
           vector_storage_overlaps(forcefield.epsilon, output) ||
           vector_storage_overlaps(forcefield.bonds.atom_i, output) ||
           vector_storage_overlaps(forcefield.bonds.atom_j, output) ||
           vector_storage_overlaps(forcefield.bonds.equilibrium, output) ||
           vector_storage_overlaps(forcefield.bonds.force_constant, output) ||
           vector_storage_overlaps(forcefield.angles.atom_i, output) ||
           vector_storage_overlaps(forcefield.angles.atom_j, output) ||
           vector_storage_overlaps(forcefield.angles.atom_k, output) ||
           vector_storage_overlaps(forcefield.angles.equilibrium, output) ||
           vector_storage_overlaps(forcefield.angles.force_constant, output) ||
           vector_storage_overlaps(forcefield.torsions.atom_i, output) ||
           vector_storage_overlaps(forcefield.torsions.atom_j, output) ||
           vector_storage_overlaps(forcefield.torsions.atom_k, output) ||
           vector_storage_overlaps(forcefield.torsions.atom_l, output) ||
           vector_storage_overlaps(forcefield.torsions.periodicity, output) ||
           vector_storage_overlaps(forcefield.torsions.phase, output) ||
           vector_storage_overlaps(forcefield.torsions.amplitude, output) ||
           vector_storage_overlaps(forcefield.exclusions, output) ||
           vector_storage_overlaps(forcefield.pair_scales, output);
}

bool model_storage_overlaps(
    const bg_direct_ewald_model_v1 &model,
    const ByteRange &output) noexcept {
    return vector_storage_overlaps(model.pair_rules, output);
}

bool constraint_storage_overlaps(
    const bg_distance_constraints_v1 &constraints,
    const ByteRange &output) noexcept {
    return counted_storage_overlaps(
               constraints.atom_i, constraints.constraint_count,
               sizeof(*constraints.atom_i), output) ||
           counted_storage_overlaps(
               constraints.atom_j, constraints.constraint_count,
               sizeof(*constraints.atom_j), output) ||
           counted_storage_overlaps(
               constraints.distance_angstrom,
               constraints.constraint_count,
               sizeof(*constraints.distance_angstrom), output);
}

bool create_input_storage_overlaps(
    const bg_system *system,
    const bg_forcefield *forcefield,
    const bg_direct_ewald_model_v1 *direct_model,
    const bg_particle_mesh_reciprocal_model_v1 *reciprocal_model,
    const bg_distance_constraints_v1 *constraints,
    const bg_simulation_options_v1 *options,
    const ByteRange &output) noexcept {
    if ((system != nullptr &&
         (fixed_storage_overlaps(system, sizeof(*system), output) ||
          system_storage_overlaps(*system, output))) ||
        (forcefield != nullptr &&
         (fixed_storage_overlaps(forcefield, sizeof(*forcefield), output) ||
          forcefield_storage_overlaps(*forcefield, output))) ||
        (direct_model != nullptr &&
         (fixed_storage_overlaps(direct_model, sizeof(*direct_model), output) ||
          model_storage_overlaps(*direct_model, output))) ||
        (reciprocal_model != nullptr &&
         fixed_storage_overlaps(reciprocal_model, sizeof(*reciprocal_model), output)) ||
        (options != nullptr &&
         fixed_storage_overlaps(options, sizeof(*options), output))) {
        return true;
    }
    return constraints != nullptr &&
           (fixed_storage_overlaps(constraints, sizeof(*constraints), output) ||
            constraint_storage_overlaps(*constraints, output));
}

bool owner_storage_overlaps(
    const bg_particle_mesh_ewald_composite_simulation_v1 &owner,
    const ByteRange &output) noexcept {
    if (fixed_storage_overlaps(&owner, sizeof(owner), output) ||
        model_storage_overlaps(owner.direct_model, output) ||
        system_storage_overlaps(owner.short_system_scratch, output) ||
        evaluation_storage_overlaps(
            owner.short_parent_evaluation_scratch, output) ||
        evaluation_storage_overlaps(
            owner.direct_parent_evaluation_scratch, output) ||
        evaluation_storage_overlaps(
            owner.reciprocal_parent_evaluation_scratch, output) ||
        vector_storage_overlaps(
            owner.rust_reciprocal_provider_force_scratch.x, output) ||
        vector_storage_overlaps(
            owner.rust_reciprocal_provider_force_scratch.y, output) ||
        vector_storage_overlaps(
            owner.rust_reciprocal_provider_force_scratch.z, output) ||
        rust_reciprocal_workspace_storage_overlaps(
            owner.rust_reciprocal_provider_force_scratch.reciprocal_workspace,
            output) ||
        rust_reciprocal_neutrality_sort_scratch_storage_overlaps(
            owner.rust_reciprocal_provider_force_scratch
                .neutrality_sort_scratch,
            output)) {
        return true;
    }
    if (owner.simulation == nullptr) {
        return false;
    }
    const bg_simulation &simulation = *owner.simulation;
    return fixed_storage_overlaps(
               &simulation, sizeof(simulation), output) ||
           system_storage_overlaps(simulation.system, output) ||
           forcefield_storage_overlaps(simulation.forcefield, output) ||
           vector_storage_overlaps(simulation.constraints, output) ||
           vector_storage_overlaps(
               simulation.force_evaluation_scratch.x, output) ||
           vector_storage_overlaps(
               simulation.force_evaluation_scratch.y, output) ||
           vector_storage_overlaps(
               simulation.force_evaluation_scratch.z, output);
}

bg_status validate_typed_error_descriptor(
    const bg_direct_ewald_error_v1 &error) noexcept {
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

void clear_typed_error(bg_direct_ewald_error_v1 *error) noexcept {
    error->code = BG_DIRECT_EWALD_ERROR_NONE;
    std::fill_n(
        error->detail,
        static_cast<std::size_t>(BG_DIRECT_EWALD_ERROR_DETAIL_CAPACITY),
        '\0');
}

void commit_typed_error(
    bg_direct_ewald_error_v1 *error,
    bg_direct_ewald_error_code code,
    const std::string &detail) noexcept {
    error->code = code;
    const std::size_t capacity =
        static_cast<std::size_t>(BG_DIRECT_EWALD_ERROR_DETAIL_CAPACITY);
    const std::size_t length = std::min(capacity - 1U, detail.size());
    std::fill_n(error->detail, capacity, '\0');
    if (length != 0U) {
        std::memcpy(error->detail, detail.data(), length);
    }
    set_last_error(error->detail);
}

bg_status validate_create_outputs(
    const bg_system *system,
    const bg_forcefield *forcefield,
    const bg_direct_ewald_model_v1 *direct_model,
    const bg_particle_mesh_reciprocal_model_v1 *reciprocal_model,
    const bg_distance_constraints_v1 *constraints,
    const bg_simulation_options_v1 *options,
    bg_particle_mesh_ewald_composite_simulation_v1 **out_simulation,
    bg_direct_ewald_error_v1 *out_error) noexcept {
    if (out_error == nullptr || !pointer_is_aligned(out_error)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "particle-mesh composite dynamics typed-error output must be non-null and naturally aligned");
    }
    bg_status status = validate_typed_error_descriptor(*out_error);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (out_simulation != nullptr && !pointer_is_aligned(out_simulation)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "particle-mesh composite dynamics owner output must be naturally aligned");
    }

    ByteRange error_range;
    if (!make_byte_range(out_error, sizeof(*out_error), &error_range)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "particle-mesh composite dynamics output byte range is not representable");
    }
    if (create_input_storage_overlaps(
            system, forcefield, direct_model, reciprocal_model, constraints, options, error_range)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "particle-mesh composite dynamics typed-error output must not overlap borrowed inputs");
    }
    if (out_simulation != nullptr) {
        ByteRange owner_range;
        if (!make_byte_range(
                out_simulation, sizeof(*out_simulation), &owner_range) ||
            ranges_overlap(owner_range, error_range) ||
            create_input_storage_overlaps(
                system, forcefield, direct_model, reciprocal_model, constraints, options,
                owner_range)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "particle-mesh composite dynamics owner output must not overlap another output or borrowed input");
        }
    }
    return BG_STATUS_OK;
}

bg_status validate_report_descriptor(
    const bg_dynamics_report_v1 &report) noexcept {
    bg_status status = validate_descriptor_header(
        report.struct_size,
        sizeof(report),
        report.abi_version,
        "bg_dynamics_report_v1 struct_size does not match ABI v1",
        "bg_dynamics_report_v1 abi_version does not match the native library");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = validate_unit_system(report.unit_system);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (report.reserved0 != UINT32_C(0) ||
        !reserved_is_zero(report.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "bg_dynamics_report_v1 reserved fields must be zero");
    }
    return BG_STATUS_OK;
}

bg_status validate_integrate_outputs(
    const bg_context *context,
    const bg_particle_mesh_ewald_composite_simulation_v1 *simulation,
    bg_dynamics_report_v1 *out_report,
    bg_direct_ewald_error_v1 *out_error) noexcept {
    if (out_error == nullptr || !pointer_is_aligned(out_error)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "particle-mesh composite dynamics typed-error output must be non-null and naturally aligned");
    }
    if (out_report != nullptr && !pointer_is_aligned(out_report)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "particle-mesh composite dynamics report output must be naturally aligned");
    }

    ByteRange error_range;
    if (!make_byte_range(out_error, sizeof(*out_error), &error_range)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "particle-mesh composite dynamics output byte range is not representable");
    }
    if ((context != nullptr && fixed_storage_overlaps(
             context, sizeof(*context), error_range)) ||
        (simulation != nullptr &&
         owner_storage_overlaps(*simulation, error_range))) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "particle-mesh composite dynamics typed-error output must not overlap an input owner");
    }
    if (out_report != nullptr) {
        ByteRange report_range;
        if (!make_byte_range(out_report, sizeof(*out_report), &report_range) ||
            ranges_overlap(report_range, error_range) ||
            (context != nullptr && fixed_storage_overlaps(
                 context, sizeof(*context), report_range)) ||
            (simulation != nullptr &&
             owner_storage_overlaps(*simulation, report_range))) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "particle-mesh composite dynamics report output must not overlap another output or input owner");
        }
    }

    bg_status status = validate_typed_error_descriptor(*out_error);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (out_report != nullptr) {
        status = validate_report_descriptor(*out_report);
        if (status != BG_STATUS_OK) {
            return status;
        }
    }
    return BG_STATUS_OK;
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
            bg_simulation::DynamicStateScratch &scratch =
                simulation_->dynamic_state_scratch;
            scratch.position_x = simulation_->system.position_x;
            scratch.position_y = simulation_->system.position_y;
            scratch.position_z = simulation_->system.position_z;
            scratch.velocity_x = simulation_->system.velocity_x;
            scratch.velocity_y = simulation_->system.velocity_y;
            scratch.velocity_z = simulation_->system.velocity_z;
        }
    }

    DynamicStateRollback(const DynamicStateRollback &) = delete;
    DynamicStateRollback &operator=(const DynamicStateRollback &) = delete;

    ~DynamicStateRollback() noexcept {
        if (committed_) {
            return;
        }
        if (snapshot_particle_channels_) {
            const bg_simulation::DynamicStateScratch &scratch =
                simulation_->dynamic_state_scratch;
            restore_channel(scratch.position_x, &simulation_->system.position_x);
            restore_channel(scratch.position_y, &simulation_->system.position_y);
            restore_channel(scratch.position_z, &simulation_->system.position_z);
            restore_channel(scratch.velocity_x, &simulation_->system.velocity_x);
            restore_channel(scratch.velocity_y, &simulation_->system.velocity_y);
            restore_channel(scratch.velocity_z, &simulation_->system.velocity_z);
        }
        simulation_->absolute_step = absolute_step_;
        std::shared_ptr<const bg_simulation::NeighborListCacheData>
            failed_neighbor_list_data =
                std::move(simulation_->neighbor_list_cache.data);
        if (failed_neighbor_list_data.get() != neighbor_list_data_.get()) {
            auto failed_publication = std::const_pointer_cast<
                bg_simulation::NeighborListCacheData>(
                std::move(failed_neighbor_list_data));
            bool retained = false;
            for (auto &candidate :
                 simulation_->neighbor_list_cache.publication_scratch) {
                if (candidate.get() == neighbor_list_data_.get()) {
                    candidate = std::move(failed_publication);
                    retained = true;
                    break;
                }
            }
            if (!retained) {
                for (auto &candidate :
                     simulation_->neighbor_list_cache.publication_scratch) {
                    if (candidate == nullptr) {
                        candidate = std::move(failed_publication);
                        retained = true;
                        break;
                    }
                }
            }
            if (!retained) {
                simulation_->neighbor_list_cache.publication_scratch.front() =
                    std::move(failed_publication);
            }
        }
        simulation_->neighbor_list_cache.data = std::move(neighbor_list_data_);
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
    bool committed_ = false;
};

struct ProviderState final {
    bg_particle_mesh_ewald_composite_simulation_v1 *owner = nullptr;
    bg_direct_ewald_error_v1 *typed_error = nullptr;
};

bg_status evaluate_composite_provider(
    const bg_context &context,
    bg_simulation *simulation,
    const bg_system &system,
    bool compute_forces,
    void *state,
    cpu::Evaluation *out_evaluation) {
    if (state == nullptr || out_evaluation == nullptr) {
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "particle-mesh composite dynamics force-provider state or output is null");
    }
    auto *provider = static_cast<ProviderState *>(state);
    if (provider->owner == nullptr || provider->typed_error == nullptr ||
        provider->owner->simulation.get() != simulation) {
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "particle-mesh composite dynamics force-provider owner is inconsistent");
    }

    particle_mesh_ewald_composite::Evaluation combined;
    bg_direct_ewald_error_v1 local_error{};
    local_error.struct_size = static_cast<uint32_t>(sizeof(local_error));
    local_error.abi_version = BG_DIRECT_EWALD_ABI_VERSION;
    const bg_status status = particle_mesh_ewald_composite::evaluate_prevalidated(
        context.backend, system, simulation->forcefield,
        provider->owner->direct_model, provider->owner->reciprocal_model,
        &provider->owner->short_system_scratch,
        &provider->owner->short_parent_evaluation_scratch,
        &simulation->rust_cpu_forcefield_validated,
        &provider->owner->direct_parent_evaluation_scratch,
        &provider->owner->reciprocal_parent_evaluation_scratch,
        &provider->owner->rust_reciprocal_provider_force_scratch,
        compute_forces ? out_evaluation : nullptr, compute_forces,
        &combined, &local_error);
    if (status != BG_STATUS_OK) {
        if (local_error.code != BG_DIRECT_EWALD_ERROR_NONE) {
            *provider->typed_error = local_error;
        }
        return status;
    }

    bg_energy_components_v1 committed_energy{};
    committed_energy.struct_size =
        static_cast<uint32_t>(sizeof(committed_energy));
    committed_energy.abi_version = BG_ABI_VERSION;
    committed_energy.unit_system = simulation->system.unit_system;
    committed_energy.harmonic_bond_kcal_per_mol =
        combined.short_harmonic_bond;
    committed_energy.harmonic_angle_kcal_per_mol =
        combined.short_harmonic_angle;
    committed_energy.periodic_torsion_kcal_per_mol =
        combined.short_periodic_torsion;
    committed_energy.lennard_jones_kcal_per_mol =
        combined.short_lennard_jones;
    committed_energy.coulomb_kcal_per_mol = combined.pme_total;
    committed_energy.total_kcal_per_mol = combined.total;
    out_evaluation->energy = committed_energy;
    return BG_STATUS_OK;
}

bg_status validate_particle_view_descriptor(
    const bg_particle_soa_view &view) noexcept {
    const bg_status status = validate_descriptor_header(
        view.struct_size,
        sizeof(view),
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

}  // namespace

std::array<uint8_t, 32> compute_static_fingerprint(
    const bg_particle_mesh_ewald_composite_simulation_v1 &owner) noexcept {
    betelgeuze::native::dynamics::Sha256 hash;
    constexpr uint8_t tag[] = {
        'B', 'G', '-', 'P', 'M', 'E', 'D', '-', 'S', 'T', 'A', 'T', 'I',
        'C', '-', '1'};
    hash.update(tag, sizeof(tag));
    betelgeuze::native::dynamics::hash_u32(&hash, kEvaluatorFamily);
    betelgeuze::native::dynamics::hash_u32(&hash, kEvaluatorSchema);
    if (owner.simulation == nullptr) {
        return hash.finish();
    }
    const std::array<uint8_t, 32> legacy =
        betelgeuze::native::dynamics::compute_static_fingerprint(
            *owner.simulation);
    hash.update(legacy.data(), legacy.size());

    const bg_direct_ewald_model_v1 &model = owner.direct_model;
    betelgeuze::native::dynamics::hash_u32(
        &hash, static_cast<uint32_t>(model.unit_system));
    betelgeuze::native::dynamics::hash_u64(
        &hash, static_cast<uint64_t>(model.atom_count));
    for (const double length : model.cell_lengths_angstrom) {
        betelgeuze::native::dynamics::hash_double(&hash, length);
    }
    betelgeuze::native::dynamics::hash_double(
        &hash, model.alpha_per_angstrom);
    betelgeuze::native::dynamics::hash_double(
        &hash, model.real_space_cutoff_angstrom);
    betelgeuze::native::dynamics::hash_double(&hash, model.dielectric);
    betelgeuze::native::dynamics::hash_double(
        &hash, model.minimum_pair_distance_angstrom);
    betelgeuze::native::dynamics::hash_u64(
        &hash, static_cast<uint64_t>(model.pair_rules.size()));
    for (const ewald::PairRule &rule : model.pair_rules) {
        betelgeuze::native::dynamics::hash_u64(
            &hash, static_cast<uint64_t>(rule.atom_i));
        betelgeuze::native::dynamics::hash_u64(
            &hash, static_cast<uint64_t>(rule.atom_j));
        betelgeuze::native::dynamics::hash_double(
            &hash, rule.coulomb_scale);
        betelgeuze::native::dynamics::hash_u32(
            &hash, rule.is_exclusion ? UINT32_C(1) : UINT32_C(0));
    }
    const bg_particle_mesh_reciprocal_model_v1 &reciprocal =
        owner.reciprocal_model;
    betelgeuze::native::dynamics::hash_u32(
        &hash, static_cast<uint32_t>(reciprocal.unit_system));
    betelgeuze::native::dynamics::hash_u64(
        &hash, static_cast<uint64_t>(reciprocal.atom_count));
    for (const double length : reciprocal.cell_lengths_angstrom) {
        betelgeuze::native::dynamics::hash_double(&hash, length);
    }
    betelgeuze::native::dynamics::hash_double(
        &hash, reciprocal.alpha_per_angstrom);
    for (const uint32_t dimension : reciprocal.mesh_dimensions) {
        betelgeuze::native::dynamics::hash_u32(&hash, dimension);
    }
    betelgeuze::native::dynamics::hash_double(&hash, reciprocal.dielectric);
    return hash.finish();
}

bg_status validate_owner_invariant(
    const bg_particle_mesh_ewald_composite_simulation_v1 &owner) {
    if (owner.simulation == nullptr) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "particle-mesh composite dynamics owner contains no Engine simulation");
    }
    const bg_simulation &simulation = *owner.simulation;
    if (simulation.integrator != BG_INTEGRATOR_VELOCITY_VERLET) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "particle-mesh composite dynamics owner must use Velocity Verlet");
    }
    bg_status status = particle_mesh_ewald_composite::validate_static_compatibility(
        simulation.system, simulation.forcefield, owner.direct_model, owner.reciprocal_model);
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (simulation.static_fingerprint !=
        betelgeuze::native::dynamics::compute_static_fingerprint(simulation)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "particle-mesh composite dynamics legacy static fingerprint is inconsistent");
    }
    if (owner.static_fingerprint != compute_static_fingerprint(owner)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "particle-mesh composite dynamics static fingerprint is inconsistent");
    }
    return BG_STATUS_OK;
}

}  // namespace betelgeuze::native::composite::dynamics

extern "C" BG_API uint32_t BG_CALL
bg_particle_mesh_ewald_composite_dynamics_abi_version(void) BG_NOEXCEPT {
    return BG_PARTICLE_MESH_EWALD_COMPOSITE_DYNAMICS_ABI_VERSION;
}

extern "C" BG_API uint32_t BG_CALL
bg_particle_mesh_ewald_composite_dynamics_abi_version_major(void) BG_NOEXCEPT {
    return BG_PARTICLE_MESH_EWALD_COMPOSITE_DYNAMICS_ABI_VERSION_MAJOR;
}

extern "C" BG_API uint32_t BG_CALL
bg_particle_mesh_ewald_composite_dynamics_abi_version_minor(void) BG_NOEXCEPT {
    return BG_PARTICLE_MESH_EWALD_COMPOSITE_DYNAMICS_ABI_VERSION_MINOR;
}

extern "C" BG_API const char *BG_CALL
bg_particle_mesh_ewald_composite_dynamics_abi_version_string(void) BG_NOEXCEPT {
    return "1.0.0";
}

extern "C" BG_API const char *BG_CALL
bg_particle_mesh_ewald_composite_dynamics_v1_profile_id(void) BG_NOEXCEPT {
    return betelgeuze::native::composite::dynamics::kProfileId;
}

extern "C" BG_API bg_status BG_CALL
bg_particle_mesh_ewald_composite_simulation_v1_create(
    const bg_system *system,
    const bg_forcefield *forcefield,
    const bg_direct_ewald_model_v1 *direct_model,
    const bg_particle_mesh_reciprocal_model_v1 *reciprocal_model,
    const bg_distance_constraints_v1 *constraints,
    const bg_simulation_options_v1 *options,
    bg_particle_mesh_ewald_composite_simulation_v1 **out_simulation,
    bg_direct_ewald_error_v1 *out_error) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::composite;
    using namespace betelgeuze::native::composite::dynamics;
    return guarded_status([&]() -> bg_status {
        bg_status status = validate_create_outputs(
            system, forcefield, direct_model, reciprocal_model, constraints, options,
            out_simulation, out_error);
        if (status != BG_STATUS_OK) {
            return status;
        }
        if (out_simulation != nullptr) {
            *out_simulation = nullptr;
        }
        clear_typed_error(out_error);

        if (system == nullptr || forcefield == nullptr || direct_model == nullptr || reciprocal_model == nullptr ||
            options == nullptr || out_simulation == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "system, forcefield, direct_model, reciprocal_model, options, and owner output must not be null");
        }
        bg_simulation *legacy_raw = nullptr;
        status = bg_simulation_create(
            system, forcefield, constraints, options, &legacy_raw);
        if (status != BG_STATUS_OK) {
            return status;
        }
        std::unique_ptr<bg_simulation> legacy(legacy_raw);
        if (legacy->integrator != BG_INTEGRATOR_VELOCITY_VERLET) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "particle-mesh composite dynamics supports only Velocity Verlet");
        }
        auto candidate =
            std::make_unique<bg_particle_mesh_ewald_composite_simulation_v1>();
        candidate->simulation = std::move(legacy);
        candidate->direct_model = *direct_model;
        candidate->reciprocal_model = *reciprocal_model;

        status = particle_mesh_ewald_composite::validate_static_compatibility(
            candidate->simulation->system,
            candidate->simulation->forcefield,
            candidate->direct_model, candidate->reciprocal_model);
        if (status != BG_STATUS_OK) {
            return status;
        }
        candidate->short_system_scratch = candidate->simulation->system;
        std::fill(
            candidate->short_system_scratch.charge.begin(),
            candidate->short_system_scratch.charge.end(),
            0.0);

        bg_context validation_context{};
        validation_context.backend = BG_BACKEND_CPP_CPU_REFERENCE;
        validation_context.unit_system =
            candidate->simulation->system.unit_system;
        validation_context.device_ordinal = INT32_C(0);
        particle_mesh_ewald_composite::Evaluation initial_evaluation;
        bg_direct_ewald_error_v1 initial_error{};
        initial_error.struct_size = static_cast<uint32_t>(sizeof(initial_error));
        initial_error.abi_version = BG_DIRECT_EWALD_ABI_VERSION;
        status = particle_mesh_ewald_composite::evaluate_prevalidated(
            validation_context.backend, candidate->simulation->system,
            candidate->simulation->forcefield, candidate->direct_model,
            candidate->reciprocal_model, &candidate->short_system_scratch,
            &candidate->short_parent_evaluation_scratch,
            &candidate->simulation->rust_cpu_forcefield_validated,
            &candidate->direct_parent_evaluation_scratch,
            &candidate->reciprocal_parent_evaluation_scratch,
            &candidate->rust_reciprocal_provider_force_scratch, nullptr,
            false, &initial_evaluation, &initial_error);
        if (status != BG_STATUS_OK) {
            if (initial_error.code != BG_DIRECT_EWALD_ERROR_NONE) {
                commit_typed_error(
                    out_error, initial_error.code, initial_error.detail);
            }
            return status;
        }
        candidate->static_fingerprint = compute_static_fingerprint(*candidate);
        *out_simulation = candidate.release();
        return BG_STATUS_OK;
    });
}

extern "C" BG_API void BG_CALL
bg_particle_mesh_ewald_composite_simulation_v1_destroy(
    bg_particle_mesh_ewald_composite_simulation_v1 *simulation) BG_NOEXCEPT {
    delete simulation;
}

extern "C" BG_API bg_status BG_CALL
bg_particle_mesh_ewald_composite_simulation_v1_get_particles(
    const bg_particle_mesh_ewald_composite_simulation_v1 *simulation,
    bg_particle_soa_view *out_view) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::composite::dynamics;
    return guarded_status([&]() -> bg_status {
        if (out_view == nullptr || !pointer_is_aligned(out_view)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "particle view output must be non-null and naturally aligned");
        }
        ByteRange view_range;
        if (simulation != nullptr &&
            (!make_byte_range(out_view, sizeof(*out_view), &view_range) ||
             owner_storage_overlaps(*simulation, view_range))) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "particle view output must not overlap particle-mesh composite dynamics owner storage");
        }
        bg_status status = validate_particle_view_descriptor(*out_view);
        if (status != BG_STATUS_OK) {
            return status;
        }
        if (simulation == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "particle-mesh composite dynamics simulation must not be null");
        }
        status = validate_owner_invariant(*simulation);
        if (status != BG_STATUS_OK) {
            return status;
        }
        return bg_simulation_get_particles(
            simulation->simulation.get(), out_view);
    });
}

extern "C" BG_API bg_status BG_CALL
bg_particle_mesh_ewald_composite_simulation_v1_get_absolute_step(
    const bg_particle_mesh_ewald_composite_simulation_v1 *simulation,
    uint64_t *absolute_step) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::composite::dynamics;
    return guarded_status([&]() -> bg_status {
        if (absolute_step == nullptr || !pointer_is_aligned(absolute_step)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "absolute_step output must be non-null and naturally aligned");
        }
        if (simulation == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "particle-mesh composite dynamics simulation must not be null");
        }
        ByteRange step_range;
        if (!make_byte_range(
                absolute_step, sizeof(*absolute_step), &step_range) ||
            owner_storage_overlaps(*simulation, step_range)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "absolute_step output must not overlap particle-mesh composite dynamics owner storage");
        }
        bg_status status = validate_owner_invariant(*simulation);
        if (status != BG_STATUS_OK) {
            return status;
        }
        return bg_simulation_get_absolute_step(
            simulation->simulation.get(), absolute_step);
    });
}

extern "C" BG_API bg_status BG_CALL
bg_context_integrate_particle_mesh_ewald_composite_v1(
    const bg_context *context,
    bg_particle_mesh_ewald_composite_simulation_v1 *simulation,
    uint64_t step_count,
    bg_dynamics_report_v1 *out_report,
    bg_direct_ewald_error_v1 *out_error) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::composite::dynamics;
    return guarded_status([&]() -> bg_status {
        bg_status status = validate_integrate_outputs(
            context, simulation, out_report, out_error);
        if (status != BG_STATUS_OK) {
            return status;
        }
        clear_typed_error(out_error);
        if (context == nullptr || simulation == nullptr ||
            out_report == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "context, particle-mesh composite simulation, and dynamics report must not be null");
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
                    "particle-mesh Ewald composite dynamics supports only explicitly requested CPU backends");
        }
        if (context->backend != context->requested_backend) {
            return fail(
                BG_STATUS_ABI_MISMATCH,
                "particle-mesh Ewald composite dynamics requested and resolved CPU backends must match");
        }
        status = validate_owner_invariant(*simulation);
        if (status != BG_STATUS_OK) {
            return status;
        }
        bg_simulation *legacy = simulation->simulation.get();
        if (context->unit_system != legacy->system.unit_system) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "context and particle-mesh composite dynamics simulation units must match");
        }
        if (step_count > UINT64_MAX - legacy->absolute_step) {
            return fail(
                BG_STATUS_CAPACITY_OVERFLOW,
                "absolute dynamics step would overflow uint64");
        }

        DynamicStateRollback rollback(
            legacy, step_count != UINT64_C(0));
        bg_dynamics_report_v1 report = *out_report;
        bg_direct_ewald_error_v1 typed_error{};
        typed_error.struct_size = static_cast<uint32_t>(sizeof(typed_error));
        typed_error.abi_version = BG_DIRECT_EWALD_ABI_VERSION;
        ProviderState provider_state{simulation, &typed_error};
        const betelgeuze::native::dynamics::ForceProvider provider{
            &evaluate_composite_provider, &provider_state};
        status = betelgeuze::native::dynamics::integrate(
            *context, provider, step_count, legacy, &report);
        if (status != BG_STATUS_OK) {
            if (typed_error.code != BG_DIRECT_EWALD_ERROR_NONE) {
                commit_typed_error(
                    out_error, typed_error.code, typed_error.detail);
            }
            return status;
        }
        if (typed_error.code != BG_DIRECT_EWALD_ERROR_NONE) {
            return fail(
                BG_STATUS_INTERNAL_ERROR,
                "successful particle-mesh composite dynamics integration retained a typed error");
        }
        rollback.commit();
        *out_report = report;
        return BG_STATUS_OK;
    });
}
