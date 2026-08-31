#include "../src/internal.hpp"
#include "../src/particle_mesh_reciprocal/rust_evaluator.hpp"

#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <string>
#include <vector>

namespace betelgeuze::native {

// The standalone adapter test links the production evaluator translation unit
// without the product library. Keep its header-defined diagnostic boundary
// private to the test instead of exporting a product hook.
thread_local std::array<char, kLastErrorCapacity> last_error{};

}  // namespace betelgeuze::native

namespace {

namespace reciprocal = betelgeuze::native::particle_mesh_reciprocal;
namespace rust_cpu =
    betelgeuze::native::particle_mesh_reciprocal::rust_cpu;

constexpr std::size_t kAtomCount = 2U;
constexpr double kProviderEnergy = -17.125;
constexpr std::array<std::array<double, 3>, kAtomCount> kProviderForces{{
    {{1.25, 3.5, -4.75}},
    {{-2.25, 5.5, 6.125}},
}};

struct FakeProviderState final {
    std::size_t abi_calls = 0U;
    std::size_t public_calls = 0U;
    std::size_t direct_calls = 0U;
    std::size_t workspace_calls = 0U;
    std::size_t energy_workspace_calls = 0U;
    std::size_t energy_workspace_neutrality_calls = 0U;
    std::size_t energy_all_scratch_calls = 0U;
    std::size_t triple_calls = 0U;
    std::uint8_t last_public_compute_forces = UINT8_C(0xff);
    bool descriptor_violation = false;
    bool force_output_failure_pending = false;
    bool force_output_failure_consumed = false;
    bool direct_observed_pending_failure = false;
    bool force_channels_written = false;
    bool return_late_numerical_error = false;
    bool return_late_energy_numerical_error = false;
    bool return_nonfinite_energy_on_success = false;
    bool return_nonfinite_force_on_success = false;
    bool late_failure_channels_written = false;
    bool all_scratch_descriptors_were_empty = false;
    bool all_scratch_descriptors_were_distinct = false;
    std::size_t workspace_destroy_calls = 0U;
    std::size_t neutrality_sort_scratch_destroy_calls = 0U;
    std::size_t particle_assignment_scratch_destroy_calls = 0U;
    bool matching_workspace_destroyed = false;
    bool matching_neutrality_sort_scratch_destroyed = false;
    bool matching_particle_assignment_scratch_destroyed = false;
    bool destroyed_workspace_was_empty = false;
    bool destroyed_neutrality_sort_scratch_was_empty = false;
    bool destroyed_particle_assignment_scratch_was_empty = false;
    bg_rust_particle_mesh_reciprocal_workspace_v1 *last_workspace = nullptr;
    bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_v1
        *last_neutrality_sort_scratch = nullptr;
    bg_rust_particle_mesh_reciprocal_particle_assignment_scratch_v1
        *last_particle_assignment_scratch = nullptr;
};

FakeProviderState fake_provider;

[[noreturn]] void fail_test(const char *message) {
    std::fprintf(stderr, "%s\n", message);
    std::exit(EXIT_FAILURE);
}

void require(bool condition, const char *message) {
    if (!condition) {
        fail_test(message);
    }
}

std::uint64_t bits(double value) noexcept {
    std::uint64_t result = 0U;
    static_assert(sizeof(result) == sizeof(value));
    std::memcpy(&result, &value, sizeof(result));
    return result;
}

void reset_fake_provider() noexcept {
    fake_provider = FakeProviderState{};
}

bool reserved_words_are_zero(const std::uint64_t (&values)[4]) noexcept {
    for (const std::uint64_t value : values) {
        if (value != 0U) {
            return false;
        }
    }
    return true;
}

bool workspace_descriptor_is_empty(
    const bg_rust_particle_mesh_reciprocal_workspace_v1 *workspace) noexcept {
    return workspace != nullptr && workspace->struct_size == 0U &&
           workspace->abi_version == 0U &&
           workspace->state ==
               BG_RUST_PARTICLE_MESH_RECIPROCAL_WORKSPACE_STATE_EMPTY &&
           workspace->reserved0 == 0U && workspace->storage == nullptr &&
           workspace->length == 0U && workspace->capacity == 0U &&
           reserved_words_are_zero(workspace->reserved);
}

bool neutrality_sort_scratch_descriptor_is_empty(
    const bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_v1
        *scratch) noexcept {
    return scratch != nullptr && scratch->struct_size == 0U &&
           scratch->abi_version == 0U &&
           scratch->state ==
               BG_RUST_PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_STATE_EMPTY &&
           scratch->reserved0 == 0U && scratch->storage == nullptr &&
           scratch->length == 0U && scratch->capacity == 0U &&
           reserved_words_are_zero(scratch->reserved);
}

bool particle_assignment_scratch_descriptor_is_empty(
    const bg_rust_particle_mesh_reciprocal_particle_assignment_scratch_v1
        *scratch) noexcept {
    return scratch != nullptr && scratch->struct_size == 0U &&
           scratch->abi_version == 0U &&
           scratch->state == UINT32_C(0) &&
           scratch->reserved0 == 0U && scratch->storage == nullptr &&
           scratch->logical_length_bytes == 0U &&
           scratch->allocation_capacity_bytes == 0U &&
           reserved_words_are_zero(scratch->reserved);
}

bool common_descriptors_are_valid(
    const bg_rust_particle_mesh_reciprocal_system_v1 *system,
    const bg_rust_particle_mesh_reciprocal_model_v1 *model,
    const bg_rust_particle_mesh_reciprocal_energy_v1 *energy,
    const bg_rust_particle_mesh_reciprocal_error_v1 *error) noexcept {
    return system != nullptr && model != nullptr && energy != nullptr &&
           error != nullptr &&
           system->struct_size == sizeof(*system) &&
           system->abi_version ==
               BG_RUST_PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION &&
           system->atom_count == kAtomCount &&
           system->position_x != nullptr && system->position_y != nullptr &&
           system->position_z != nullptr && system->charge != nullptr &&
           reserved_words_are_zero(system->reserved) &&
           model->struct_size == sizeof(*model) &&
           model->abi_version ==
               BG_RUST_PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION &&
           model->reserved0 == 0U &&
           reserved_words_are_zero(model->reserved) &&
           energy->struct_size == sizeof(*energy) &&
           energy->abi_version ==
               BG_RUST_PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION &&
           reserved_words_are_zero(energy->reserved) &&
           error->struct_size == sizeof(*error) &&
           error->abi_version ==
               BG_RUST_PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION &&
           error->reserved0 == 0U &&
           reserved_words_are_zero(error->reserved);
}

bool force_descriptor_is_valid(
    const bg_rust_particle_mesh_reciprocal_force_output_v1 *forces) noexcept {
    return forces != nullptr && forces->struct_size == sizeof(*forces) &&
           forces->abi_version ==
               BG_RUST_PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION &&
           forces->capacity >= kAtomCount && forces->x != nullptr &&
           forces->y != nullptr && forces->z != nullptr &&
           reserved_words_are_zero(forces->reserved);
}

void clear_provider_error(
    bg_rust_particle_mesh_reciprocal_error_v1 *error) noexcept {
    error->typed_code = BG_RUST_PARTICLE_MESH_RECIPROCAL_ERROR_NONE;
    error->reserved0 = 0U;
    std::memset(error->detail, 0, sizeof(error->detail));
    for (std::uint64_t &reserved : error->reserved) {
        reserved = 0U;
    }
}

std::int32_t write_provider_success(
    const bg_rust_particle_mesh_reciprocal_system_v1 *system,
    const bg_rust_particle_mesh_reciprocal_model_v1 *model,
    bg_rust_particle_mesh_reciprocal_energy_v1 *energy,
    bg_rust_particle_mesh_reciprocal_force_output_v1 *forces,
    bg_rust_particle_mesh_reciprocal_error_v1 *error) noexcept {
    if (!common_descriptors_are_valid(system, model, energy, error) ||
        (forces != nullptr && !force_descriptor_is_valid(forces))) {
        fake_provider.descriptor_violation = true;
        return BG_STATUS_INTERNAL_ERROR;
    }
    energy->reciprocal_space_kcal_per_mol = kProviderEnergy;
    clear_provider_error(error);
    if (forces == nullptr) {
        return BG_STATUS_OK;
    }
    for (std::size_t atom = 0U; atom < kAtomCount; ++atom) {
        forces->x[atom] = kProviderForces[atom][0];
        forces->y[atom] = kProviderForces[atom][1];
        forces->z[atom] = kProviderForces[atom][2];
    }
    fake_provider.force_channels_written = true;
    return BG_STATUS_OK;
}

std::int32_t write_provider_late_numerical_failure(
    const bg_rust_particle_mesh_reciprocal_system_v1 *system,
    const bg_rust_particle_mesh_reciprocal_model_v1 *model,
    bg_rust_particle_mesh_reciprocal_energy_v1 *energy,
    bg_rust_particle_mesh_reciprocal_force_output_v1 *forces,
    bg_rust_particle_mesh_reciprocal_error_v1 *error) noexcept {
    if (!common_descriptors_are_valid(system, model, energy, error) ||
        !force_descriptor_is_valid(forces)) {
        fake_provider.descriptor_violation = true;
        return BG_STATUS_INTERNAL_ERROR;
    }
    for (std::size_t atom = 0U; atom < kAtomCount; ++atom) {
        forces->x[atom] = kProviderForces[atom][0];
        forces->y[atom] = kProviderForces[atom][1];
        forces->z[atom] = kProviderForces[atom][2];
    }
    fake_provider.force_channels_written = true;
    fake_provider.late_failure_channels_written = true;
    clear_provider_error(error);
    error->typed_code =
        BG_RUST_PARTICLE_MESH_RECIPROCAL_ERROR_NONFINITE_RESULT;
    const char detail[] = "particle-mesh reciprocal result is not finite";
    static_assert(sizeof(detail) <= sizeof(error->detail));
    std::memcpy(error->detail, detail, sizeof(detail));
    return BG_STATUS_NUMERICAL_ERROR;
}

void require_only_stateless_energy_all_scratch_route() {
    require(fake_provider.abi_calls == 1U,
            "stateless energy all-scratch adapter did not perform one ABI query");
    require(fake_provider.public_calls == 0U &&
                fake_provider.direct_calls == 0U &&
                fake_provider.workspace_calls == 0U &&
                fake_provider.energy_workspace_calls == 0U &&
                fake_provider.energy_workspace_neutrality_calls == 0U &&
                fake_provider.energy_all_scratch_calls == 1U &&
                fake_provider.triple_calls == 0U,
            "stateless energy adapter selected the wrong Rust provider entry");
}

void require_only_stateless_all_scratch_force_route() {
    require(fake_provider.abi_calls == 1U,
            "stateless all-scratch adapter did not perform one ABI query");
    require(fake_provider.public_calls == 0U &&
                fake_provider.direct_calls == 0U &&
                fake_provider.workspace_calls == 0U &&
                fake_provider.energy_workspace_calls == 0U &&
                fake_provider.energy_workspace_neutrality_calls == 0U &&
                fake_provider.energy_all_scratch_calls == 0U &&
                fake_provider.triple_calls == 1U,
            "stateless forceful adapter selected the wrong Rust provider entry");
}

void require_stateless_all_scratch_lifecycle() {
    require(fake_provider.all_scratch_descriptors_were_empty,
            "stateless adapter did not supply initially EMPTY scratch descriptors");
    require(fake_provider.all_scratch_descriptors_were_distinct,
            "stateless adapter aliased call-local scratch descriptors");
    require(fake_provider.workspace_destroy_calls == 1U &&
                fake_provider.neutrality_sort_scratch_destroy_calls == 1U &&
                fake_provider.particle_assignment_scratch_destroy_calls == 1U,
            "stateless adapter did not destroy each call-local scratch descriptor exactly once");
    require(fake_provider.matching_workspace_destroyed &&
                fake_provider.matching_neutrality_sort_scratch_destroyed &&
                fake_provider.matching_particle_assignment_scratch_destroyed,
            "stateless adapter destroyed different scratch descriptors");
    require(fake_provider.destroyed_workspace_was_empty &&
                fake_provider.destroyed_neutrality_sort_scratch_was_empty &&
                fake_provider.destroyed_particle_assignment_scratch_was_empty,
            "stateless adapter changed empty scratch descriptors before destruction");
}

void require_no_reusable_provider_scratch_destruction() {
    require(fake_provider.workspace_destroy_calls == 0U &&
                fake_provider.neutrality_sort_scratch_destroy_calls == 0U &&
                fake_provider.particle_assignment_scratch_destroy_calls == 0U,
            "reusable adapter destroyed provider scratch before external owner scope exit");
}

void require_reusable_provider_scratch_destroyed_after_owner_scope() {
    require(fake_provider.workspace_destroy_calls == 1U &&
                fake_provider.neutrality_sort_scratch_destroy_calls == 1U &&
                fake_provider.particle_assignment_scratch_destroy_calls == 1U,
            "external reusable provider scratch was not destroyed exactly once");
    require(fake_provider.matching_workspace_destroyed &&
                fake_provider.matching_neutrality_sort_scratch_destroyed &&
                fake_provider.matching_particle_assignment_scratch_destroyed,
            "external reusable provider scratch destruction did not match its owner");
}

void require_only_energy_all_scratch_route() {
    require(fake_provider.abi_calls == 1U,
            "energy-workspace adapter did not perform one ABI query");
    require(fake_provider.public_calls == 0U &&
                fake_provider.direct_calls == 0U &&
                fake_provider.workspace_calls == 0U &&
                fake_provider.energy_workspace_calls == 0U &&
                fake_provider.energy_workspace_neutrality_calls == 0U &&
                fake_provider.energy_all_scratch_calls == 1U &&
                fake_provider.triple_calls == 0U,
            "reusable energy-only adapter did not select the all-scratch provider entry");
}

void require_only_all_scratch_force_route() {
    require(fake_provider.abi_calls == 1U,
            "all-scratch force adapter did not perform one ABI query");
    require(fake_provider.public_calls == 0U &&
                fake_provider.direct_calls == 0U &&
                fake_provider.workspace_calls == 0U &&
                fake_provider.energy_workspace_calls == 0U &&
                fake_provider.energy_workspace_neutrality_calls == 0U &&
                fake_provider.energy_all_scratch_calls == 0U &&
                fake_provider.triple_calls == 1U,
            "all-scratch force adapter selected the wrong Rust provider entry");
}

bg_system make_system() {
    bg_system system;
    system.position_x = {1.25, 5.1};
    system.position_y = {2.5, 3.2};
    system.position_z = {3.75, 8.4};
    system.charge = {0.5, -0.5};
    return system;
}

bg_particle_mesh_reciprocal_model_v1 make_model() {
    bg_particle_mesh_reciprocal_model_v1 model;
    model.atom_count = kAtomCount;
    model.cell_lengths_angstrom = {{18.0, 20.0, 22.0}};
    model.alpha_per_angstrom = 0.31;
    model.mesh_dimensions = {{4U, 4U, 4U}};
    model.dielectric = 1.0;
    return model;
}

void require_provider_evaluation_bits(const reciprocal::Evaluation &value) {
    require(bits(value.reciprocal_space_kcal_per_mol) ==
                bits(kProviderEnergy),
            "adapter changed fake-provider energy bits");
    require(value.forces.size() == kAtomCount,
            "adapter returned the wrong force count");
    for (std::size_t atom = 0U; atom < kAtomCount; ++atom) {
        for (std::size_t axis = 0U; axis < 3U; ++axis) {
            require(bits(value.forces[atom][axis]) ==
                        bits(kProviderForces[atom][axis]),
                    "adapter changed fake-provider force bits");
        }
    }
}

void require_provider_scratch_bits(
    const rust_cpu::ProviderForceScratch &scratch) {
    require(scratch.x.size() == kAtomCount &&
                scratch.y.size() == kAtomCount &&
                scratch.z.size() == kAtomCount,
            "provider force scratch had the wrong shape");
    for (std::size_t atom = 0U; atom < kAtomCount; ++atom) {
        require(bits(scratch.x[atom]) == bits(kProviderForces[atom][0]) &&
                    bits(scratch.y[atom]) ==
                        bits(kProviderForces[atom][1]) &&
                    bits(scratch.z[atom]) == bits(kProviderForces[atom][2]),
                "provider force scratch changed fake-provider bits");
    }
}

struct EvaluationSnapshot final {
    std::uint64_t energy_bits = 0U;
    std::vector<std::array<std::uint64_t, 3>> force_bits;
    const void *force_storage = nullptr;
    std::size_t force_capacity = 0U;
};

EvaluationSnapshot snapshot(const reciprocal::Evaluation &value) {
    EvaluationSnapshot result;
    result.energy_bits = bits(value.reciprocal_space_kcal_per_mol);
    result.force_storage = value.forces.data();
    result.force_capacity = value.forces.capacity();
    result.force_bits.reserve(value.forces.size());
    for (const auto &force : value.forces) {
        result.force_bits.push_back(
            {{bits(force[0]), bits(force[1]), bits(force[2])}});
    }
    return result;
}

void require_same_snapshot(
    const reciprocal::Evaluation &value,
    const EvaluationSnapshot &expected) {
    require(bits(value.reciprocal_space_kcal_per_mol) == expected.energy_bits,
            "failed adapter evaluation changed sentinel energy bits");
    require(value.forces.data() == expected.force_storage &&
                value.forces.capacity() == expected.force_capacity &&
                value.forces.size() == expected.force_bits.size(),
            "failed adapter evaluation changed sentinel force storage");
    for (std::size_t atom = 0U; atom < value.forces.size(); ++atom) {
        for (std::size_t axis = 0U; axis < 3U; ++axis) {
            require(bits(value.forces[atom][axis]) ==
                        expected.force_bits[atom][axis],
                    "failed adapter evaluation changed sentinel force bits");
        }
    }
}

void verify_stateless_energy_all_scratch_branch_and_transactionality() {
    reset_fake_provider();
    fake_provider.force_output_failure_pending = true;
    const bg_system system = make_system();
    const auto model = make_model();
    reciprocal::Evaluation output;
    output.reciprocal_space_kcal_per_mol = 701.0;
    output.forces = {{{801.0, 802.0, 803.0}}};
    reciprocal::Error error{
        BG_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_PARAMETER,
        "stale energy-only error"};

    require(rust_cpu::evaluate(system, model, false, &output, &error) ==
                BG_STATUS_OK,
            "energy-only Rust adapter evaluation failed");
    require_only_stateless_energy_all_scratch_route();
    require_stateless_all_scratch_lifecycle();
    require(fake_provider.force_output_failure_pending &&
                !fake_provider.force_output_failure_consumed,
            "energy-only adapter consumed the force-output allocation failure");
    require(!fake_provider.force_channels_written,
            "energy-only adapter supplied force channels");
    require(bits(output.reciprocal_space_kcal_per_mol) ==
                bits(kProviderEnergy) &&
                output.forces.empty(),
            "energy-only adapter returned the wrong output bits or shape");
    require(error.code == BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONE &&
                error.detail.empty(),
            "energy-only adapter retained a stale typed error");
    require(!fake_provider.descriptor_violation,
            "energy-only adapter supplied malformed provider descriptors");

    reset_fake_provider();
    fake_provider.return_late_energy_numerical_error = true;
    output.reciprocal_space_kcal_per_mol = 901.0;
    output.forces = {
        {{911.0, 912.0, 913.0}},
        {{921.0, 922.0, 923.0}},
        {{931.0, 932.0, 933.0}},
    };
    const EvaluationSnapshot late_before = snapshot(output);
    error = reciprocal::Error{
        BG_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_PARAMETER,
        "stale stateless energy late-failure error"};
    require(rust_cpu::evaluate(system, model, false, &output, &error) ==
                BG_STATUS_NUMERICAL_ERROR,
            "adapter changed a late stateless energy all-scratch failure");
    require_only_stateless_energy_all_scratch_route();
    require_stateless_all_scratch_lifecycle();
    require_same_snapshot(output, late_before);
    require(error.code ==
                    BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONFINITE_RESULT &&
                error.detail ==
                    "particle-mesh reciprocal energy is not finite",
            "stateless energy adapter did not propagate typed failure");
    require(!fake_provider.descriptor_violation,
            "failed stateless energy adapter supplied malformed descriptors");

    reset_fake_provider();
    fake_provider.return_nonfinite_energy_on_success = true;
    output.reciprocal_space_kcal_per_mol = 941.0;
    output.forces = {
        {{951.0, 952.0, 953.0}},
        {{961.0, 962.0, 963.0}},
        {{971.0, 972.0, 973.0}},
    };
    const EvaluationSnapshot nonfinite_before = snapshot(output);
    error = reciprocal::Error{
        BG_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_PARAMETER,
        "stale non-finite stateless energy error"};
    require(rust_cpu::evaluate(system, model, false, &output, &error) ==
                BG_STATUS_INTERNAL_ERROR,
            "adapter accepted non-finite stateless energy on provider success");
    require_only_stateless_energy_all_scratch_route();
    require_stateless_all_scratch_lifecycle();
    require_same_snapshot(output, nonfinite_before);
    require(error.code == BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONE &&
                error.detail.empty(),
            "non-finite stateless energy success fabricated a typed error");
    require(!fake_provider.descriptor_violation,
            "non-finite stateless energy adapter supplied malformed descriptors");
}

void verify_nonreuse_forceful_all_scratch_branch_and_transactional_peer() {
    reset_fake_provider();
    fake_provider.force_output_failure_pending = true;
    const bg_system system = make_system();
    const auto model = make_model();
    reciprocal::Evaluation output;
    reciprocal::Error error;

    require(rust_cpu::evaluate(system, model, true, &output, &error) ==
                BG_STATUS_OK,
            "non-reuse forceful Rust adapter evaluation failed");
    require_only_stateless_all_scratch_force_route();
    require_stateless_all_scratch_lifecycle();
    require(fake_provider.force_output_failure_pending &&
                !fake_provider.force_output_failure_consumed,
            "stateless all-scratch entry consumed the force-output allocation failure");
    require(fake_provider.force_channels_written,
            "stateless all-scratch entry did not write call-local SoA channels");
    require_provider_evaluation_bits(output);
    require(error.code == BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONE &&
                error.detail.empty(),
            "successful stateless all-scratch evaluation returned a typed error");
    require(!fake_provider.descriptor_violation,
            "stateless all-scratch adapter supplied malformed provider descriptors");

    double force_x[kAtomCount] = {901.0, 902.0};
    double force_y[kAtomCount] = {903.0, 904.0};
    double force_z[kAtomCount] = {905.0, 906.0};
    bg_rust_particle_mesh_reciprocal_system_v1 raw_system{
        static_cast<std::uint32_t>(
            sizeof(bg_rust_particle_mesh_reciprocal_system_v1)),
        BG_RUST_PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION,
        kAtomCount,
        system.position_x.data(),
        system.position_y.data(),
        system.position_z.data(),
        system.charge.data(),
        {0U, 0U, 0U, 0U}};
    bg_rust_particle_mesh_reciprocal_model_v1 raw_model{
        static_cast<std::uint32_t>(
            sizeof(bg_rust_particle_mesh_reciprocal_model_v1)),
        BG_RUST_PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION,
        {18.0, 20.0, 22.0},
        0.31,
        {4U, 4U, 4U},
        0U,
        1.0,
        {0U, 0U, 0U, 0U}};
    bg_rust_particle_mesh_reciprocal_energy_v1 raw_energy{
        static_cast<std::uint32_t>(
            sizeof(bg_rust_particle_mesh_reciprocal_energy_v1)),
        BG_RUST_PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION,
        907.0,
        {0U, 0U, 0U, 0U}};
    bg_rust_particle_mesh_reciprocal_force_output_v1 raw_forces{
        static_cast<std::uint32_t>(
            sizeof(bg_rust_particle_mesh_reciprocal_force_output_v1)),
        BG_RUST_PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION,
        kAtomCount,
        force_x,
        force_y,
        force_z,
        {0U, 0U, 0U, 0U}};
    bg_rust_particle_mesh_reciprocal_error_v1 raw_error{
        static_cast<std::uint32_t>(
            sizeof(bg_rust_particle_mesh_reciprocal_error_v1)),
        BG_RUST_PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION,
        BG_RUST_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_PARAMETER,
        0U,
        {},
        {0U, 0U, 0U, 0U}};
    std::memset(raw_error.detail, 'S', sizeof(raw_error.detail));

    require(bg_rust_particle_mesh_reciprocal_evaluate_v1(
                &raw_system, &raw_model, UINT8_C(1), &raw_energy,
                &raw_forces, &raw_error) == BG_STATUS_OUT_OF_MEMORY,
            "transactional raw provider did not consume ForceOutput failure");
    require(!fake_provider.force_output_failure_pending &&
                fake_provider.force_output_failure_consumed,
            "transactional raw provider left ForceOutput failure pending");
    require(bits(raw_energy.reciprocal_space_kcal_per_mol) == bits(907.0),
            "transactional raw failure changed energy sentinel bits");
    require(bits(force_x[0]) == bits(901.0) &&
                bits(force_x[1]) == bits(902.0) &&
                bits(force_y[0]) == bits(903.0) &&
                bits(force_y[1]) == bits(904.0) &&
                bits(force_z[0]) == bits(905.0) &&
                bits(force_z[1]) == bits(906.0),
            "transactional raw failure changed force sentinel bits");
    require(raw_error.typed_code ==
                    BG_RUST_PARTICLE_MESH_RECIPROCAL_ERROR_NONE &&
                std::strcmp(raw_error.detail,
                            "particle force-output allocation failed") == 0,
            "transactional raw failure returned the wrong diagnostic");
}

void verify_late_stateless_all_scratch_failure_preserves_adapter_output() {
    reset_fake_provider();
    fake_provider.return_late_numerical_error = true;
    const bg_system system = make_system();
    const auto model = make_model();
    reciprocal::Evaluation output;
    output.reciprocal_space_kcal_per_mol = 1'001.0;
    output.forces = {
        {{1'101.0, 1'102.0, 1'103.0}},
        {{1'201.0, 1'202.0, 1'203.0}},
        {{1'301.0, 1'302.0, 1'303.0}},
    };
    const EvaluationSnapshot before = snapshot(output);
    reciprocal::Error error{
        BG_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_PARAMETER,
        "stale late-failure error"};

    require(rust_cpu::evaluate(system, model, true, &output, &error) ==
                BG_STATUS_NUMERICAL_ERROR,
            "adapter changed a late stateless all-scratch numerical failure");
    require_only_stateless_all_scratch_force_route();
    require_stateless_all_scratch_lifecycle();
    require(fake_provider.force_channels_written &&
                fake_provider.late_failure_channels_written,
            "late-failure fake did not write disposable SoA channels");
    require_same_snapshot(output, before);
    require(error.code ==
                    BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONFINITE_RESULT &&
                error.detail ==
                    "particle-mesh reciprocal result is not finite",
            "adapter did not propagate the late stateless all-scratch typed error");
}

void verify_nonfinite_stateless_all_scratch_success_preserves_adapter_output() {
    reset_fake_provider();
    fake_provider.return_nonfinite_force_on_success = true;
    const bg_system system = make_system();
    const auto model = make_model();
    reciprocal::Evaluation output;
    output.reciprocal_space_kcal_per_mol = 1'311.0;
    output.forces = {
        {{1'321.0, 1'322.0, 1'323.0}},
        {{1'331.0, 1'332.0, 1'333.0}},
        {{1'341.0, 1'342.0, 1'343.0}},
    };
    const EvaluationSnapshot before = snapshot(output);
    reciprocal::Error error{
        BG_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_PARAMETER,
        "stale non-finite stateless all-scratch error"};

    require(rust_cpu::evaluate(system, model, true, &output, &error) ==
                BG_STATUS_INTERNAL_ERROR,
            "adapter accepted a non-finite stateless all-scratch force on provider success");
    require_only_stateless_all_scratch_force_route();
    require_stateless_all_scratch_lifecycle();
    require(fake_provider.force_channels_written &&
                !fake_provider.late_failure_channels_written,
            "non-finite stateless success fake did not write call-local scratch normally");
    require_same_snapshot(output, before);
    require(error.code == BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONE &&
                error.detail.empty(),
            "non-finite stateless provider success fabricated a typed error");
    require(!fake_provider.descriptor_violation,
            "non-finite stateless all-scratch adapter supplied malformed descriptors");
}

void verify_reusable_forceful_all_scratch_branch_and_transactionality() {
    reset_fake_provider();
    fake_provider.force_output_failure_pending = true;
    const bg_system system = make_system();
    const auto model = make_model();
    {
        rust_cpu::ProviderForceScratch scratch;
        reciprocal::Evaluation output;
        output.forces = {
            {{1'401.0, 1'402.0, 1'403.0}},
            {{1'501.0, 1'502.0, 1'503.0}},
        };
        reciprocal::Error error;

        require(rust_cpu::evaluate_reusing_force_storage(
                    system, model, true, &scratch, &output, &error) ==
                    BG_STATUS_OK,
                "reusable forceful Rust adapter evaluation failed");
        require_only_all_scratch_force_route();
        require(fake_provider.last_workspace == &scratch.reciprocal_workspace &&
                    fake_provider.last_neutrality_sort_scratch ==
                        &scratch.neutrality_sort_scratch &&
                    fake_provider.last_particle_assignment_scratch ==
                        &scratch.particle_assignment_scratch,
                "reusable forceful adapter supplied the wrong scratch owner");
        require(fake_provider.force_output_failure_pending &&
                    !fake_provider.force_output_failure_consumed,
                "all-scratch provider entry consumed ForceOutput failure");
        require_provider_evaluation_bits(output);
        require_provider_scratch_bits(scratch);
        require(error.code == BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONE &&
                    error.detail.empty(),
                "successful reusable forceful evaluation returned a typed error");
        require(!fake_provider.descriptor_violation,
                "all-scratch adapter supplied malformed provider descriptors");
        require_no_reusable_provider_scratch_destruction();

        reset_fake_provider();
        fake_provider.force_output_failure_pending = true;
        fake_provider.return_late_numerical_error = true;
        scratch.x = {1'701.0, 1'702.0};
        scratch.y = {1'801.0, 1'802.0};
        scratch.z = {1'901.0, 1'902.0};
        output.reciprocal_space_kcal_per_mol = 2'001.0;
        output.forces = {
            {{2'101.0, 2'102.0, 2'103.0}},
            {{2'201.0, 2'202.0, 2'203.0}},
            {{2'301.0, 2'302.0, 2'303.0}},
        };
        const EvaluationSnapshot before = snapshot(output);
        error = reciprocal::Error{
            BG_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_PARAMETER,
            "stale reusable forceful error"};
        require(rust_cpu::evaluate_reusing_force_storage(
                    system, model, true, &scratch, &output, &error) ==
                    BG_STATUS_NUMERICAL_ERROR,
                "adapter changed reusable forceful typed failure");
        require_only_all_scratch_force_route();
        require(fake_provider.last_workspace == &scratch.reciprocal_workspace &&
                    fake_provider.last_neutrality_sort_scratch ==
                        &scratch.neutrality_sort_scratch &&
                    fake_provider.last_particle_assignment_scratch ==
                        &scratch.particle_assignment_scratch,
                "failed reusable forceful route lost scratch ownership");
        require(fake_provider.force_output_failure_pending &&
                    !fake_provider.force_output_failure_consumed,
                "failed all-scratch force route consumed ForceOutput failure");
        require(fake_provider.force_channels_written &&
                    fake_provider.late_failure_channels_written,
                "late reusable forceful failure did not write derived scratch");
        require_same_snapshot(output, before);
        require(error.code ==
                        BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONFINITE_RESULT &&
                    error.detail ==
                        "particle-mesh reciprocal result is not finite",
                "reusable forceful adapter did not propagate typed failure");
        require_provider_scratch_bits(scratch);
        require(!fake_provider.descriptor_violation,
                "failed all-scratch adapter supplied malformed provider descriptors");
        require_no_reusable_provider_scratch_destruction();

        reset_fake_provider();
        fake_provider.force_output_failure_pending = true;
        fake_provider.return_nonfinite_force_on_success = true;
        scratch.x = {3'101.0, 3'102.0};
        scratch.y = {3'201.0, 3'202.0};
        scratch.z = {3'301.0, 3'302.0};
        output.reciprocal_space_kcal_per_mol = 3'401.0;
        output.forces = {
            {{3'501.0, 3'502.0, 3'503.0}},
            {{3'601.0, 3'602.0, 3'603.0}},
            {{3'701.0, 3'702.0, 3'703.0}},
        };
        const EvaluationSnapshot nonfinite_before = snapshot(output);
        error = reciprocal::Error{
            BG_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_PARAMETER,
            "stale non-finite reusable forceful error"};
        require(rust_cpu::evaluate_reusing_force_storage(
                    system, model, true, &scratch, &output, &error) ==
                    BG_STATUS_INTERNAL_ERROR,
                "adapter accepted a non-finite force on provider success");
        require_only_all_scratch_force_route();
        require(fake_provider.last_workspace == &scratch.reciprocal_workspace &&
                    fake_provider.last_neutrality_sort_scratch ==
                        &scratch.neutrality_sort_scratch &&
                    fake_provider.last_particle_assignment_scratch ==
                        &scratch.particle_assignment_scratch,
                "non-finite reusable forceful route lost scratch ownership");
        require(fake_provider.force_output_failure_pending &&
                    !fake_provider.force_output_failure_consumed,
                "non-finite all-scratch force route consumed ForceOutput failure");
        require(fake_provider.force_channels_written &&
                    !fake_provider.late_failure_channels_written,
                "non-finite success fake did not write derived scratch normally");
        require_same_snapshot(output, nonfinite_before);
        require(scratch.x.size() == kAtomCount &&
                    scratch.y.size() == kAtomCount &&
                    scratch.z.size() == kAtomCount &&
                    bits(scratch.x[0]) == bits(kProviderForces[0][0]) &&
                    bits(scratch.x[1]) == bits(kProviderForces[1][0]) &&
                    bits(scratch.y[0]) == bits(kProviderForces[0][1]) &&
                    bits(scratch.y[1]) == bits(kProviderForces[1][1]) &&
                    bits(scratch.z[0]) == bits(kProviderForces[0][2]) &&
                    std::isnan(scratch.z.back()),
                "non-finite success did not remain confined to derived scratch");
        require(error.code == BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONE &&
                    error.detail.empty(),
                "non-finite provider success fabricated a typed error");
        require(!fake_provider.descriptor_violation,
                "non-finite all-scratch adapter supplied malformed descriptors");
        require_no_reusable_provider_scratch_destruction();
    }
    require_reusable_provider_scratch_destroyed_after_owner_scope();
}

void verify_reusable_energy_workspace_branch_and_transactionality() {
    const bg_system system = make_system();
    const auto model = make_model();
    reset_fake_provider();
    {
        rust_cpu::ProviderForceScratch scratch;
        scratch.x = {2'001.0, 2'002.0};
        scratch.y = {2'101.0};
        scratch.z = {2'201.0, 2'202.0, 2'203.0};
        const auto x = scratch.x;
        const auto y = scratch.y;
        const auto z = scratch.z;

        reciprocal::Evaluation output;
        output.reciprocal_space_kcal_per_mol = 2'301.0;
        output.forces = {{{2'401.0, 2'402.0, 2'403.0}}};
        reciprocal::Error error;
        require(rust_cpu::evaluate_reusing_force_storage(
                    system, model, false, &scratch, &output, &error) ==
                    BG_STATUS_OK,
                "reusable energy-only Rust adapter evaluation failed");
        require_only_energy_all_scratch_route();
        require(fake_provider.last_workspace == &scratch.reciprocal_workspace &&
                    fake_provider.last_neutrality_sort_scratch ==
                        &scratch.neutrality_sort_scratch &&
                    fake_provider.last_particle_assignment_scratch ==
                        &scratch.particle_assignment_scratch,
                "reusable energy-only adapter supplied the wrong scratch owner");
        require(bits(output.reciprocal_space_kcal_per_mol) ==
                        bits(kProviderEnergy) &&
                    output.forces.empty(),
                "reusable energy-only adapter returned the wrong result");
        require(scratch.x == x && scratch.y == y && scratch.z == z,
                "reusable energy-only adapter or fake provider touched force storage");
        require_no_reusable_provider_scratch_destruction();

        reset_fake_provider();
        fake_provider.return_late_energy_numerical_error = true;
        output.reciprocal_space_kcal_per_mol = 2'501.0;
        output.forces = {{{2'601.0, 2'602.0, 2'603.0}}};
        const EvaluationSnapshot before = snapshot(output);
        require(rust_cpu::evaluate_reusing_force_storage(
                    system, model, false, &scratch, &output, &error) ==
                    BG_STATUS_NUMERICAL_ERROR,
                "adapter changed reusable energy-only typed failure");
        require_only_energy_all_scratch_route();
        require(fake_provider.last_workspace == &scratch.reciprocal_workspace &&
                    fake_provider.last_neutrality_sort_scratch ==
                        &scratch.neutrality_sort_scratch &&
                    fake_provider.last_particle_assignment_scratch ==
                        &scratch.particle_assignment_scratch,
                "failed reusable energy-only route lost scratch ownership");
        require_same_snapshot(output, before);
        require(error.code ==
                        BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONFINITE_RESULT &&
                    error.detail ==
                        "particle-mesh reciprocal energy is not finite",
                "reusable energy-only adapter did not propagate typed failure");
        require(scratch.x == x && scratch.y == y && scratch.z == z,
                "failed reusable energy-only route or fake provider touched force storage");
        require_no_reusable_provider_scratch_destruction();
    }
    require_reusable_provider_scratch_destroyed_after_owner_scope();
}

void verify_reusable_energy_requires_scratch_owner() {
    reset_fake_provider();
    const bg_system system = make_system();
    const auto model = make_model();
    reciprocal::Evaluation output;
    output.reciprocal_space_kcal_per_mol = 2'701.0;
    output.forces = {{{2'801.0, 2'802.0, 2'803.0}}};
    const EvaluationSnapshot before = snapshot(output);
    reciprocal::Error error;
    require(rust_cpu::evaluate_reusing_force_storage(
                system, model, false, nullptr, &output, &error) ==
                BG_STATUS_INTERNAL_ERROR,
            "reusable energy-only adapter accepted a null scratch owner");
    require(fake_provider.abi_calls == 0U &&
                fake_provider.public_calls == 0U &&
                fake_provider.direct_calls == 0U &&
                fake_provider.workspace_calls == 0U &&
                fake_provider.energy_workspace_calls == 0U &&
                fake_provider.energy_workspace_neutrality_calls == 0U &&
                fake_provider.energy_all_scratch_calls == 0U &&
                fake_provider.triple_calls == 0U,
            "null reusable energy scratch reached the fake provider");
    require_same_snapshot(output, before);
}

void verify_provider_force_source_triple_branch() {
    reset_fake_provider();
    fake_provider.force_output_failure_pending = true;
    const bg_system system = make_system();
    const auto model = make_model();
    {
        rust_cpu::ProviderForceScratch scratch;
        rust_cpu::ProviderForceSourceResult output{1'601.0};
        reciprocal::Error error;

        require(rust_cpu::evaluate_reusing_provider_force_storage(
                    system, model, &scratch, &output, &error) == BG_STATUS_OK,
                "provider-force-source Rust adapter evaluation failed");
        require_only_all_scratch_force_route();
        require(fake_provider.last_workspace == &scratch.reciprocal_workspace &&
                    fake_provider.last_neutrality_sort_scratch ==
                        &scratch.neutrality_sort_scratch &&
                    fake_provider.last_particle_assignment_scratch ==
                        &scratch.particle_assignment_scratch,
                "provider-force-source adapter supplied the wrong scratch owner");
        require(fake_provider.force_output_failure_pending &&
                    !fake_provider.force_output_failure_consumed,
                "triple provider entry consumed ForceOutput failure");
        require(bits(output.reciprocal_space_kcal_per_mol) ==
                    bits(kProviderEnergy),
                "provider-force-source adapter changed energy bits");
        require_provider_scratch_bits(scratch);
        require(!fake_provider.descriptor_violation,
                "triple adapter supplied malformed provider descriptors");
        require_no_reusable_provider_scratch_destruction();
    }
    require_reusable_provider_scratch_destroyed_after_owner_scope();
}

void verify_cpp_lane_remains_provider_independent() {
    reset_fake_provider();
    fake_provider.force_output_failure_pending = true;
    const bg_system system = make_system();
    const auto model = make_model();
    reciprocal::Evaluation output;
    reciprocal::Error error;

    require(reciprocal::cpp_cpu::evaluate(
                system, model, true, &output, &error) == BG_STATUS_OK,
            "C++ reciprocal evaluator failed in adapter branch test");
    require(fake_provider.abi_calls == 0U &&
                fake_provider.public_calls == 0U &&
                fake_provider.direct_calls == 0U &&
                fake_provider.workspace_calls == 0U &&
                fake_provider.energy_workspace_calls == 0U &&
                fake_provider.energy_workspace_neutrality_calls == 0U &&
                fake_provider.energy_all_scratch_calls == 0U &&
                fake_provider.triple_calls == 0U,
            "C++ reciprocal evaluator entered a Rust provider branch");
    require(fake_provider.force_output_failure_pending &&
                !fake_provider.force_output_failure_consumed,
            "C++ reciprocal evaluator consumed Rust ForceOutput failure");
    require(std::isfinite(output.reciprocal_space_kcal_per_mol) &&
                output.forces.size() == kAtomCount,
            "C++ reciprocal evaluator returned an invalid result shape");
    require(error.code == BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONE &&
                error.detail.empty(),
            "C++ reciprocal evaluator returned a typed error on success");
}

}  // namespace

extern "C" std::uint32_t
bg_rust_particle_mesh_reciprocal_provider_abi_version_v1(void) {
    ++fake_provider.abi_calls;
    return BG_RUST_PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION;
}

extern "C" std::int32_t bg_rust_particle_mesh_reciprocal_evaluate_v1(
    const bg_rust_particle_mesh_reciprocal_system_v1 *system,
    const bg_rust_particle_mesh_reciprocal_model_v1 *model,
    std::uint8_t compute_forces,
    bg_rust_particle_mesh_reciprocal_energy_v1 *out_energy,
    bg_rust_particle_mesh_reciprocal_force_output_v1 *out_forces,
    bg_rust_particle_mesh_reciprocal_error_v1 *out_error) {
    ++fake_provider.public_calls;
    fake_provider.last_public_compute_forces = compute_forces;
    if (compute_forces == UINT8_C(1) &&
        fake_provider.force_output_failure_pending) {
        if (!common_descriptors_are_valid(
                system, model, out_energy, out_error) ||
            !force_descriptor_is_valid(out_forces)) {
            fake_provider.descriptor_violation = true;
            return BG_STATUS_INTERNAL_ERROR;
        }
        fake_provider.force_output_failure_pending = false;
        fake_provider.force_output_failure_consumed = true;
        clear_provider_error(out_error);
        const char detail[] = "particle force-output allocation failed";
        static_assert(sizeof(detail) <= sizeof(out_error->detail));
        std::memcpy(out_error->detail, detail, sizeof(detail));
        return BG_STATUS_OUT_OF_MEMORY;
    }
    if (compute_forces == UINT8_C(0) && out_forces != nullptr) {
        fake_provider.descriptor_violation = true;
        return BG_STATUS_INTERNAL_ERROR;
    }
    return write_provider_success(
        system, model, out_energy,
        compute_forces == UINT8_C(0) ? nullptr : out_forces, out_error);
}

extern "C" std::int32_t
bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_v1(
    const bg_rust_particle_mesh_reciprocal_system_v1 *system,
    const bg_rust_particle_mesh_reciprocal_model_v1 *model,
    bg_rust_particle_mesh_reciprocal_energy_v1 *out_energy,
    bg_rust_particle_mesh_reciprocal_force_output_v1 *out_forces,
    bg_rust_particle_mesh_reciprocal_error_v1 *out_error) {
    ++fake_provider.direct_calls;
    fake_provider.direct_observed_pending_failure =
        fake_provider.force_output_failure_pending;
    if (fake_provider.return_late_numerical_error) {
        return write_provider_late_numerical_failure(
            system, model, out_energy, out_forces, out_error);
    }
    return write_provider_success(
        system, model, out_energy, out_forces, out_error);
}

extern "C" std::int32_t
bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_v1(
    const bg_rust_particle_mesh_reciprocal_system_v1 *system,
    const bg_rust_particle_mesh_reciprocal_model_v1 *model,
    bg_rust_particle_mesh_reciprocal_workspace_v1 *workspace,
    bg_rust_particle_mesh_reciprocal_energy_v1 *out_energy,
    bg_rust_particle_mesh_reciprocal_force_output_v1 *out_forces,
    bg_rust_particle_mesh_reciprocal_error_v1 *out_error) {
    ++fake_provider.workspace_calls;
    fake_provider.last_workspace = workspace;
    return write_provider_success(
        system, model, out_energy, out_forces, out_error);
}

extern "C" std::int32_t
bg_rust_particle_mesh_reciprocal_evaluate_energy_with_workspace_v1(
    const bg_rust_particle_mesh_reciprocal_system_v1 *system,
    const bg_rust_particle_mesh_reciprocal_model_v1 *model,
    bg_rust_particle_mesh_reciprocal_workspace_v1 *workspace,
    bg_rust_particle_mesh_reciprocal_energy_v1 *out_energy,
    bg_rust_particle_mesh_reciprocal_error_v1 *out_error) {
    ++fake_provider.energy_workspace_calls;
    fake_provider.last_workspace = workspace;
    if (workspace == nullptr ||
        !common_descriptors_are_valid(system, model, out_energy, out_error)) {
        fake_provider.descriptor_violation = true;
        return BG_STATUS_INTERNAL_ERROR;
    }
    if (fake_provider.return_late_energy_numerical_error) {
        out_energy->reciprocal_space_kcal_per_mol = kProviderEnergy;
        clear_provider_error(out_error);
        out_error->typed_code =
            BG_RUST_PARTICLE_MESH_RECIPROCAL_ERROR_NONFINITE_RESULT;
        const char detail[] = "particle-mesh reciprocal energy is not finite";
        static_assert(sizeof(detail) <= sizeof(out_error->detail));
        std::memcpy(out_error->detail, detail, sizeof(detail));
        return BG_STATUS_NUMERICAL_ERROR;
    }
    return write_provider_success(system, model, out_energy, nullptr, out_error);
}

extern "C" std::int32_t
bg_rust_particle_mesh_reciprocal_evaluate_energy_with_workspace_and_neutrality_sort_scratch_v1(
    const bg_rust_particle_mesh_reciprocal_system_v1 *system,
    const bg_rust_particle_mesh_reciprocal_model_v1 *model,
    bg_rust_particle_mesh_reciprocal_workspace_v1 *workspace,
    bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_v1
        *neutrality_sort_scratch,
    bg_rust_particle_mesh_reciprocal_energy_v1 *out_energy,
    bg_rust_particle_mesh_reciprocal_error_v1 *out_error) {
    ++fake_provider.energy_workspace_neutrality_calls;
    fake_provider.last_workspace = workspace;
    fake_provider.last_neutrality_sort_scratch = neutrality_sort_scratch;
    if (workspace == nullptr || neutrality_sort_scratch == nullptr ||
        !common_descriptors_are_valid(system, model, out_energy, out_error)) {
        fake_provider.descriptor_violation = true;
        return BG_STATUS_INTERNAL_ERROR;
    }
    if (fake_provider.return_late_energy_numerical_error) {
        out_energy->reciprocal_space_kcal_per_mol = kProviderEnergy;
        clear_provider_error(out_error);
        out_error->typed_code =
            BG_RUST_PARTICLE_MESH_RECIPROCAL_ERROR_NONFINITE_RESULT;
        const char detail[] = "particle-mesh reciprocal energy is not finite";
        static_assert(sizeof(detail) <= sizeof(out_error->detail));
        std::memcpy(out_error->detail, detail, sizeof(detail));
        return BG_STATUS_NUMERICAL_ERROR;
    }
    return write_provider_success(system, model, out_energy, nullptr, out_error);
}

extern "C" std::int32_t
bg_rust_particle_mesh_reciprocal_evaluate_energy_with_workspace_and_neutrality_sort_scratch_and_particle_assignment_scratch_v1(
    const bg_rust_particle_mesh_reciprocal_system_v1 *system,
    const bg_rust_particle_mesh_reciprocal_model_v1 *model,
    bg_rust_particle_mesh_reciprocal_workspace_v1 *workspace,
    bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_v1
        *neutrality_sort_scratch,
    bg_rust_particle_mesh_reciprocal_particle_assignment_scratch_v1
        *particle_assignment_scratch,
    bg_rust_particle_mesh_reciprocal_energy_v1 *out_energy,
    bg_rust_particle_mesh_reciprocal_error_v1 *out_error) {
    ++fake_provider.energy_all_scratch_calls;
    fake_provider.last_workspace = workspace;
    fake_provider.last_neutrality_sort_scratch = neutrality_sort_scratch;
    fake_provider.last_particle_assignment_scratch =
        particle_assignment_scratch;
    fake_provider.all_scratch_descriptors_were_empty =
        workspace_descriptor_is_empty(workspace) &&
        neutrality_sort_scratch_descriptor_is_empty(neutrality_sort_scratch) &&
        particle_assignment_scratch_descriptor_is_empty(
            particle_assignment_scratch);
    fake_provider.all_scratch_descriptors_were_distinct =
        static_cast<const void *>(workspace) !=
            static_cast<const void *>(neutrality_sort_scratch) &&
        static_cast<const void *>(workspace) !=
            static_cast<const void *>(particle_assignment_scratch) &&
        static_cast<const void *>(neutrality_sort_scratch) !=
            static_cast<const void *>(particle_assignment_scratch);
    if (workspace == nullptr || neutrality_sort_scratch == nullptr ||
        particle_assignment_scratch == nullptr ||
        !common_descriptors_are_valid(system, model, out_energy, out_error)) {
        fake_provider.descriptor_violation = true;
        return BG_STATUS_INTERNAL_ERROR;
    }
    if (fake_provider.return_late_energy_numerical_error) {
        out_energy->reciprocal_space_kcal_per_mol = kProviderEnergy;
        clear_provider_error(out_error);
        out_error->typed_code =
            BG_RUST_PARTICLE_MESH_RECIPROCAL_ERROR_NONFINITE_RESULT;
        const char detail[] = "particle-mesh reciprocal energy is not finite";
        static_assert(sizeof(detail) <= sizeof(out_error->detail));
        std::memcpy(out_error->detail, detail, sizeof(detail));
        return BG_STATUS_NUMERICAL_ERROR;
    }
    if (fake_provider.return_nonfinite_energy_on_success) {
        const std::int32_t status = write_provider_success(
            system, model, out_energy, nullptr, out_error);
        if (status != BG_STATUS_OK) {
            return status;
        }
        out_energy->reciprocal_space_kcal_per_mol =
            std::numeric_limits<double>::quiet_NaN();
        return status;
    }
    return write_provider_success(system, model, out_energy, nullptr, out_error);
}

extern "C" std::int32_t
bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_and_neutrality_sort_scratch_and_particle_assignment_scratch_v1(
    const bg_rust_particle_mesh_reciprocal_system_v1 *system,
    const bg_rust_particle_mesh_reciprocal_model_v1 *model,
    bg_rust_particle_mesh_reciprocal_workspace_v1 *workspace,
    bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_v1
        *neutrality_sort_scratch,
    bg_rust_particle_mesh_reciprocal_particle_assignment_scratch_v1
        *particle_assignment_scratch,
    bg_rust_particle_mesh_reciprocal_energy_v1 *out_energy,
    bg_rust_particle_mesh_reciprocal_force_output_v1 *out_forces,
    bg_rust_particle_mesh_reciprocal_error_v1 *out_error) {
    ++fake_provider.triple_calls;
    fake_provider.last_workspace = workspace;
    fake_provider.last_neutrality_sort_scratch = neutrality_sort_scratch;
    fake_provider.last_particle_assignment_scratch =
        particle_assignment_scratch;
    fake_provider.all_scratch_descriptors_were_empty =
        workspace_descriptor_is_empty(workspace) &&
        neutrality_sort_scratch_descriptor_is_empty(neutrality_sort_scratch) &&
        particle_assignment_scratch_descriptor_is_empty(
            particle_assignment_scratch);
    fake_provider.all_scratch_descriptors_were_distinct =
        static_cast<const void *>(workspace) !=
            static_cast<const void *>(neutrality_sort_scratch) &&
        static_cast<const void *>(workspace) !=
            static_cast<const void *>(particle_assignment_scratch) &&
        static_cast<const void *>(neutrality_sort_scratch) !=
            static_cast<const void *>(particle_assignment_scratch);
    if (workspace == nullptr || neutrality_sort_scratch == nullptr ||
        particle_assignment_scratch == nullptr) {
        fake_provider.descriptor_violation = true;
        return BG_STATUS_INTERNAL_ERROR;
    }
    if (fake_provider.return_late_numerical_error) {
        return write_provider_late_numerical_failure(
            system, model, out_energy, out_forces, out_error);
    }
    if (fake_provider.return_nonfinite_force_on_success) {
        const std::int32_t status = write_provider_success(
            system, model, out_energy, out_forces, out_error);
        if (status != BG_STATUS_OK) {
            return status;
        }
        out_forces->z[kAtomCount - 1U] =
            std::numeric_limits<double>::quiet_NaN();
        return status;
    }
    return write_provider_success(
        system, model, out_energy, out_forces, out_error);
}

extern "C" void bg_rust_particle_mesh_reciprocal_workspace_destroy_v1(
    bg_rust_particle_mesh_reciprocal_workspace_v1 *workspace) {
    ++fake_provider.workspace_destroy_calls;
    fake_provider.matching_workspace_destroyed =
        workspace == fake_provider.last_workspace;
    fake_provider.destroyed_workspace_was_empty =
        workspace_descriptor_is_empty(workspace);
    if (workspace != nullptr) {
        *workspace = bg_rust_particle_mesh_reciprocal_workspace_v1{};
    }
}

extern "C" void
bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_destroy_v1(
    bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_v1
        *neutrality_sort_scratch) {
    ++fake_provider.neutrality_sort_scratch_destroy_calls;
    fake_provider.matching_neutrality_sort_scratch_destroyed =
        neutrality_sort_scratch ==
        fake_provider.last_neutrality_sort_scratch;
    fake_provider.destroyed_neutrality_sort_scratch_was_empty =
        neutrality_sort_scratch_descriptor_is_empty(neutrality_sort_scratch);
    if (neutrality_sort_scratch != nullptr) {
        *neutrality_sort_scratch =
            bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_v1{};
    }
}

extern "C" void
bg_rust_particle_mesh_reciprocal_particle_assignment_scratch_destroy_v1(
    bg_rust_particle_mesh_reciprocal_particle_assignment_scratch_v1
        *particle_assignment_scratch) {
    ++fake_provider.particle_assignment_scratch_destroy_calls;
    fake_provider.matching_particle_assignment_scratch_destroyed =
        particle_assignment_scratch ==
        fake_provider.last_particle_assignment_scratch;
    fake_provider.destroyed_particle_assignment_scratch_was_empty =
        particle_assignment_scratch_descriptor_is_empty(
            particle_assignment_scratch);
    if (particle_assignment_scratch != nullptr) {
        *particle_assignment_scratch =
            bg_rust_particle_mesh_reciprocal_particle_assignment_scratch_v1{};
    }
}

int main() {
    static_assert(
        BG_RUST_PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION == UINT32_C(1));
    verify_stateless_energy_all_scratch_branch_and_transactionality();
    verify_nonreuse_forceful_all_scratch_branch_and_transactional_peer();
    verify_late_stateless_all_scratch_failure_preserves_adapter_output();
    verify_nonfinite_stateless_all_scratch_success_preserves_adapter_output();
    verify_reusable_forceful_all_scratch_branch_and_transactionality();
    verify_reusable_energy_workspace_branch_and_transactionality();
    verify_reusable_energy_requires_scratch_owner();
    verify_provider_force_source_triple_branch();
    verify_cpp_lane_remains_provider_independent();
    std::puts("particle-mesh reciprocal Rust adapter transactionality tests passed");
    return EXIT_SUCCESS;
}
