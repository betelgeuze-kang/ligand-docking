#include "../src/internal.hpp"
#include "../src/particle_mesh_reciprocal/rust_evaluator.hpp"

#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
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
    std::size_t triple_calls = 0U;
    std::uint8_t last_public_compute_forces = UINT8_C(0xff);
    bool descriptor_violation = false;
    bool force_output_failure_pending = false;
    bool force_output_failure_consumed = false;
    bool direct_observed_pending_failure = false;
    bool force_channels_written = false;
    bool return_late_numerical_error = false;
    bool late_failure_channels_written = false;
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

void require_only_public_route() {
    require(fake_provider.abi_calls == 1U,
            "energy-only adapter did not perform one ABI query");
    require(fake_provider.public_calls == 1U &&
                fake_provider.direct_calls == 0U &&
                fake_provider.workspace_calls == 0U &&
                fake_provider.triple_calls == 0U,
            "energy-only adapter selected the wrong Rust provider entry");
}

void require_only_direct_route() {
    require(fake_provider.abi_calls == 1U,
            "direct adapter did not perform one ABI query");
    require(fake_provider.public_calls == 0U &&
                fake_provider.direct_calls == 1U &&
                fake_provider.workspace_calls == 0U &&
                fake_provider.triple_calls == 0U,
            "non-reuse forceful adapter selected the wrong Rust provider entry");
}

void require_only_workspace_route() {
    require(fake_provider.abi_calls == 1U,
            "workspace adapter did not perform one ABI query");
    require(fake_provider.public_calls == 0U &&
                fake_provider.direct_calls == 0U &&
                fake_provider.workspace_calls == 1U &&
                fake_provider.triple_calls == 0U,
            "reusable forceful adapter selected the wrong Rust provider entry");
}

void require_only_triple_route() {
    require(fake_provider.abi_calls == 1U,
            "provider-force-source adapter did not perform one ABI query");
    require(fake_provider.public_calls == 0U &&
                fake_provider.direct_calls == 0U &&
                fake_provider.workspace_calls == 0U &&
                fake_provider.triple_calls == 1U,
            "provider-force-source adapter selected the wrong Rust provider entry");
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

void verify_energy_only_public_branch() {
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
    require_only_public_route();
    require(fake_provider.last_public_compute_forces == UINT8_C(0),
            "energy-only adapter enabled provider force computation");
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
}

void verify_nonreuse_forceful_direct_branch_and_transactional_peer() {
    reset_fake_provider();
    fake_provider.force_output_failure_pending = true;
    const bg_system system = make_system();
    const auto model = make_model();
    reciprocal::Evaluation output;
    reciprocal::Error error;

    require(rust_cpu::evaluate(system, model, true, &output, &error) ==
                BG_STATUS_OK,
            "non-reuse forceful Rust adapter evaluation failed");
    require_only_direct_route();
    require(fake_provider.direct_observed_pending_failure &&
                fake_provider.force_output_failure_pending &&
                !fake_provider.force_output_failure_consumed,
            "direct provider entry consumed the force-output allocation failure");
    require(fake_provider.force_channels_written,
            "direct provider entry did not write caller-owned SoA channels");
    require_provider_evaluation_bits(output);
    require(error.code == BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONE &&
                error.detail.empty(),
            "successful direct adapter evaluation returned a typed error");
    require(!fake_provider.descriptor_violation,
            "direct adapter supplied malformed provider descriptors");

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

void verify_late_direct_failure_preserves_adapter_output() {
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
            "adapter changed a late direct-provider numerical failure");
    require_only_direct_route();
    require(fake_provider.force_channels_written &&
                fake_provider.late_failure_channels_written,
            "late-failure fake did not write disposable SoA channels");
    require_same_snapshot(output, before);
    require(error.code ==
                    BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONFINITE_RESULT &&
                error.detail ==
                    "particle-mesh reciprocal result is not finite",
            "adapter did not propagate the late direct-provider typed error");
}

void verify_reusable_forceful_workspace_branch() {
    reset_fake_provider();
    fake_provider.force_output_failure_pending = true;
    const bg_system system = make_system();
    const auto model = make_model();
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
    require_only_workspace_route();
    require(fake_provider.last_workspace == &scratch.reciprocal_workspace,
            "reusable forceful adapter supplied the wrong workspace owner");
    require(fake_provider.force_output_failure_pending &&
                !fake_provider.force_output_failure_consumed,
            "workspace provider entry consumed ForceOutput failure");
    require_provider_evaluation_bits(output);
    require_provider_scratch_bits(scratch);
    require(!fake_provider.descriptor_violation,
            "workspace adapter supplied malformed provider descriptors");
}

void verify_provider_force_source_triple_branch() {
    reset_fake_provider();
    fake_provider.force_output_failure_pending = true;
    const bg_system system = make_system();
    const auto model = make_model();
    rust_cpu::ProviderForceScratch scratch;
    rust_cpu::ProviderForceSourceResult output{1'601.0};
    reciprocal::Error error;

    require(rust_cpu::evaluate_reusing_provider_force_storage(
                system, model, &scratch, &output, &error) == BG_STATUS_OK,
            "provider-force-source Rust adapter evaluation failed");
    require_only_triple_route();
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
    return write_provider_success(
        system, model, out_energy, out_forces, out_error);
}

extern "C" void bg_rust_particle_mesh_reciprocal_workspace_destroy_v1(
    bg_rust_particle_mesh_reciprocal_workspace_v1 *workspace) {
    if (workspace != nullptr) {
        *workspace = bg_rust_particle_mesh_reciprocal_workspace_v1{};
    }
}

extern "C" void
bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_destroy_v1(
    bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_v1
        *neutrality_sort_scratch) {
    if (neutrality_sort_scratch != nullptr) {
        *neutrality_sort_scratch =
            bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_v1{};
    }
}

extern "C" void
bg_rust_particle_mesh_reciprocal_particle_assignment_scratch_destroy_v1(
    bg_rust_particle_mesh_reciprocal_particle_assignment_scratch_v1
        *particle_assignment_scratch) {
    if (particle_assignment_scratch != nullptr) {
        *particle_assignment_scratch =
            bg_rust_particle_mesh_reciprocal_particle_assignment_scratch_v1{};
    }
}

int main() {
    static_assert(
        BG_RUST_PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION == UINT32_C(1));
    verify_energy_only_public_branch();
    verify_nonreuse_forceful_direct_branch_and_transactional_peer();
    verify_late_direct_failure_preserves_adapter_output();
    verify_reusable_forceful_workspace_branch();
    verify_provider_force_source_triple_branch();
    verify_cpp_lane_remains_provider_independent();
    std::puts("particle-mesh reciprocal Rust adapter transactionality tests passed");
    return EXIT_SUCCESS;
}
