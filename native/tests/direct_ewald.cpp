#define BG_DISABLE_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#define BG_DISABLE_DIRECT_EWALD_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#include "betelgeuze/direct_ewald.h"

#include "../src/internal.hpp"

#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <string>
#include <utility>

namespace {

struct Context final {
    bg_context *value = nullptr;
    Context() = default;
    Context(const Context &) = delete;
    Context &operator=(const Context &) = delete;
    Context(Context &&other) noexcept : value(std::exchange(other.value, nullptr)) {}
    Context &operator=(Context &&) = delete;
    ~Context() { bg_context_destroy(value); }
};

struct System final {
    bg_system *value = nullptr;
    System() = default;
    System(const System &) = delete;
    System &operator=(const System &) = delete;
    System(System &&other) noexcept : value(std::exchange(other.value, nullptr)) {}
    System &operator=(System &&) = delete;
    ~System() { bg_system_destroy(value); }
};

struct Model final {
    bg_direct_ewald_model_v1 *value = nullptr;
    Model() = default;
    Model(const Model &) = delete;
    Model &operator=(const Model &) = delete;
    Model(Model &&other) noexcept : value(std::exchange(other.value, nullptr)) {}
    Model &operator=(Model &&) = delete;
    ~Model() { bg_direct_ewald_model_v1_destroy(value); }
};

struct Fixture final {
    std::array<double, 4> x{{1.25, 5.1, 10.2, 15.4}};
    std::array<double, 4> y{{2.5, 3.2, 12.3, 17.1}};
    std::array<double, 4> z{{3.75, 8.4, 7.7, 19.3}};
    std::array<double, 4> mass{{1.0, 1.0, 1.0, 1.0}};
    std::array<double, 4> charge{{
        0.7, -0.4, -0.6, 0.30000000000000004}};
    std::array<uint64_t, 1> exclusion_i{{0}};
    std::array<uint64_t, 1> exclusion_j{{1}};
    std::array<uint64_t, 1> scale_i{{2}};
    std::array<uint64_t, 1> scale_j{{3}};
    std::array<double, 1> scales{{0.5}};
};

struct Result final {
    bg_direct_ewald_energy_components_v1 energy{};
    std::array<double, 4> force_x{};
    std::array<double, 4> force_y{};
    std::array<double, 4> force_z{};
};

double from_bits(uint64_t raw) noexcept {
    double value = 0.0;
    static_assert(sizeof(value) == sizeof(raw));
    std::memcpy(&value, &raw, sizeof(value));
    return value;
}

uint64_t to_bits(double value) noexcept {
    uint64_t raw = 0;
    std::memcpy(&raw, &value, sizeof(raw));
    return raw;
}

bool near_reference(double observed, uint64_t expected_bits) noexcept {
    const double expected = from_bits(expected_bits);
    const double scale = std::max(1.0, std::abs(expected));
    return std::abs(observed - expected) <= 5.0e-12 * scale;
}

void init_error(bg_direct_ewald_error_v1 *error) {
    assert(bg_direct_ewald_error_v1_init(
               error, sizeof(*error), BG_DIRECT_EWALD_ABI_VERSION) ==
           BG_STATUS_OK);
}

template <typename Descriptor, typename Initializer>
void verify_initializer_transactionality(Initializer initializer) {
    Descriptor descriptor{};
    std::memset(&descriptor, 0x5a, sizeof(descriptor));
    std::array<unsigned char, sizeof(Descriptor)> before{};
    std::memcpy(before.data(), &descriptor, sizeof(descriptor));
    assert(initializer(
               &descriptor, sizeof(descriptor) - 1U,
               BG_DIRECT_EWALD_ABI_VERSION) == BG_STATUS_ABI_MISMATCH);
    assert(std::memcmp(&descriptor, before.data(), sizeof(descriptor)) == 0);
    assert(initializer(&descriptor, sizeof(descriptor), UINT32_C(99)) ==
           BG_STATUS_ABI_MISMATCH);
    assert(std::memcmp(&descriptor, before.data(), sizeof(descriptor)) == 0);
    assert(initializer(
               &descriptor, sizeof(descriptor),
               BG_DIRECT_EWALD_ABI_VERSION) == BG_STATUS_OK);
    assert(descriptor.struct_size == sizeof(descriptor));
    assert(descriptor.abi_version == BG_DIRECT_EWALD_ABI_VERSION);
}

bg_direct_ewald_parameters_v1 fixture_parameters(const Fixture &fixture) {
    bg_direct_ewald_parameters_v1 parameters{};
    assert(bg_direct_ewald_parameters_v1_init(
               &parameters, sizeof(parameters),
               BG_DIRECT_EWALD_ABI_VERSION) == BG_STATUS_OK);
    parameters.atom_count = 4;
    parameters.cell_lengths_angstrom[0] = 18.0;
    parameters.cell_lengths_angstrom[1] = 20.0;
    parameters.cell_lengths_angstrom[2] = 22.0;
    parameters.alpha_per_angstrom = 0.31;
    parameters.real_space_cutoff_angstrom = 8.9;
    parameters.reciprocal_max_indices[0] = 5;
    parameters.reciprocal_max_indices[1] = 5;
    parameters.reciprocal_max_indices[2] = 5;
    parameters.dielectric = 1.0;
    parameters.minimum_pair_distance_angstrom = 1.0e-8;
    parameters.exclusion_count = fixture.exclusion_i.size();
    parameters.exclusion_atom_i = fixture.exclusion_i.data();
    parameters.exclusion_atom_j = fixture.exclusion_j.data();
    parameters.pair_scale_count = fixture.scale_i.size();
    parameters.pair_scale_atom_i = fixture.scale_i.data();
    parameters.pair_scale_atom_j = fixture.scale_j.data();
    parameters.pair_scale_coulomb = fixture.scales.data();
    return parameters;
}

Context make_context(bg_backend backend) {
    bg_context_options options{};
    assert(bg_context_options_init(
               &options, sizeof(options), BG_ABI_VERSION) == BG_STATUS_OK);
    options.backend = backend;
    Context context;
    assert(bg_context_create(&options, &context.value) == BG_STATUS_OK);
    return context;
}

template <std::size_t Size>
System make_system(
    const std::array<double, Size> &x,
    const std::array<double, Size> &y,
    const std::array<double, Size> &z,
    const std::array<double, Size> &mass,
    const std::array<double, Size> &charge) {
    bg_particle_soa particles{};
    assert(bg_particle_soa_init(
               &particles, sizeof(particles), BG_ABI_VERSION) ==
           BG_STATUS_OK);
    particles.particle_count = static_cast<uint64_t>(x.size());
    particles.position_x_angstrom = x.data();
    particles.position_y_angstrom = y.data();
    particles.position_z_angstrom = z.data();
    particles.mass_dalton = mass.data();
    particles.charge_elementary = charge.data();
    System system;
    assert(bg_system_create(&particles, &system.value) == BG_STATUS_OK);
    return system;
}

bg_direct_ewald_parameters_v1 two_atom_parameters() {
    bg_direct_ewald_parameters_v1 parameters{};
    assert(bg_direct_ewald_parameters_v1_init(
               &parameters, sizeof(parameters),
               BG_DIRECT_EWALD_ABI_VERSION) == BG_STATUS_OK);
    parameters.atom_count = 2;
    parameters.cell_lengths_angstrom[0] = 10.0;
    parameters.cell_lengths_angstrom[1] = 10.0;
    parameters.cell_lengths_angstrom[2] = 10.0;
    parameters.alpha_per_angstrom = 1.0;
    parameters.real_space_cutoff_angstrom = 2.0;
    parameters.reciprocal_max_indices[0] = 1;
    parameters.reciprocal_max_indices[1] = 1;
    parameters.reciprocal_max_indices[2] = 1;
    parameters.dielectric = 1.0;
    parameters.minimum_pair_distance_angstrom = 1.0e-8;
    return parameters;
}

Model make_model(const bg_direct_ewald_parameters_v1 &parameters) {
    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    Model model;
    assert(bg_direct_ewald_model_v1_create(
               &parameters, &model.value, &error) == BG_STATUS_OK);
    assert(error.code == BG_DIRECT_EWALD_ERROR_NONE);
    return model;
}

Result evaluate(
    const bg_context *context,
    const bg_system *system,
    const bg_direct_ewald_model_v1 *model) {
    Result result;
    assert(bg_direct_ewald_energy_components_v1_init(
               &result.energy, sizeof(result.energy),
               BG_DIRECT_EWALD_ABI_VERSION) == BG_STATUS_OK);
    bg_direct_ewald_force_soa_v1 forces{};
    assert(bg_direct_ewald_force_soa_v1_init(
               &forces, sizeof(forces), BG_DIRECT_EWALD_ABI_VERSION) ==
           BG_STATUS_OK);
    forces.atom_capacity = result.force_x.size();
    forces.x_kcal_per_mol_angstrom = result.force_x.data();
    forces.y_kcal_per_mol_angstrom = result.force_y.data();
    forces.z_kcal_per_mol_angstrom = result.force_z.data();
    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    assert(bg_context_evaluate_direct_ewald_v1(
               context, system, model, &result.energy, &forces, &error) ==
           BG_STATUS_OK);
    assert(error.code == BG_DIRECT_EWALD_ERROR_NONE);
    assert(error.detail[0] == '\0');
    assert(forces.atom_count == 4);
    return result;
}

void verify_abi_identity_and_initializer_transactionality() {
    assert(bg_direct_ewald_abi_version() == 1);
    assert(bg_direct_ewald_abi_version_major() == 1);
    assert(bg_direct_ewald_abi_version_minor() == 0);
    assert(std::string(bg_direct_ewald_abi_version_string()) == "1.0.0");
    assert(std::string(bg_direct_ewald_model_v1_profile_id()) ==
           "betelgeuze.native_direct_ewald/1.0.0");

    verify_initializer_transactionality<bg_direct_ewald_parameters_v1>(
        bg_direct_ewald_parameters_v1_init);
    verify_initializer_transactionality<
        bg_direct_ewald_energy_components_v1>(
        bg_direct_ewald_energy_components_v1_init);
    verify_initializer_transactionality<bg_direct_ewald_force_soa_v1>(
        bg_direct_ewald_force_soa_v1_init);
    verify_initializer_transactionality<bg_direct_ewald_error_v1>(
        bg_direct_ewald_error_v1_init);
}

void verify_frozen_fixture_and_deep_ownership() {
    Fixture fixture;
    const Context context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    const System system = make_system(
        fixture.x, fixture.y, fixture.z, fixture.mass, fixture.charge);
    bg_direct_ewald_parameters_v1 parameters = fixture_parameters(fixture);
    const Model model = make_model(parameters);

    uint64_t atom_count = 0;
    assert(bg_direct_ewald_model_v1_get_atom_count(
               model.value, &atom_count) == BG_STATUS_OK);
    assert(atom_count == 4);

    parameters.cell_lengths_angstrom[0] = 1.0;
    fixture.exclusion_i[0] = 3;
    fixture.exclusion_j[0] = 2;
    fixture.scale_i[0] = 0;
    fixture.scale_j[0] = 1;
    fixture.scales[0] = 1.0;

    const Result first = evaluate(context.value, system.value, model.value);
    const Result second = evaluate(context.value, system.value, model.value);
    assert(near_reference(
        first.energy.real_space_kcal_per_mol, UINT64_C(0xbfbe3560505c8b5a)));
    assert(near_reference(
        first.energy.reciprocal_space_kcal_per_mol,
        UINT64_C(0x404421fcc22858dd)));
    assert(near_reference(
        first.energy.self_kcal_per_mol, UINT64_C(0xc04ff151251cf865)));
    assert(near_reference(
        first.energy.pair_correction_kcal_per_mol,
        UINT64_C(0x4031acb81f3a00d4)));
    assert(near_reference(
        first.energy.total_kcal_per_mol, UINT64_C(0xc01840981bfe6b20)));
    const std::array<uint64_t, 12> expected_forces{{
        UINT64_C(0xbf94b039bd76cc80), UINT64_C(0x3fd6aa0d9171ed72),
        UINT64_C(0x3fe65887b557df96), UINT64_C(0xbf96a2ad5015fb00),
        UINT64_C(0xbfcb27e290ac16a8), UINT64_C(0x3fc7b0e06de81818),
        UINT64_C(0x3fd04eaa3c83bf1c), UINT64_C(0x3fc860259fdc0bfa),
        UINT64_C(0xbfd48c1a95311f4a), UINT64_C(0xbfcb32f79755e5ae),
        UINT64_C(0xbfd5462f1909e822), UINT64_C(0xbfe1feb2863955fd)}};
    for (std::size_t atom = 0; atom < 4; ++atom) {
        assert(near_reference(first.force_x[atom], expected_forces[atom * 3U]));
        assert(near_reference(
            first.force_y[atom], expected_forces[atom * 3U + 1U]));
        assert(near_reference(
            first.force_z[atom], expected_forces[atom * 3U + 2U]));
    }
    assert(to_bits(first.energy.real_space_kcal_per_mol) ==
           to_bits(second.energy.real_space_kcal_per_mol));
    assert(to_bits(first.energy.reciprocal_space_kcal_per_mol) ==
           to_bits(second.energy.reciprocal_space_kcal_per_mol));
    assert(to_bits(first.energy.self_kcal_per_mol) ==
           to_bits(second.energy.self_kcal_per_mol));
    assert(to_bits(first.energy.pair_correction_kcal_per_mol) ==
           to_bits(second.energy.pair_correction_kcal_per_mol));
    assert(to_bits(first.energy.total_kcal_per_mol) ==
           to_bits(second.energy.total_kcal_per_mol));
    for (std::size_t atom = 0; atom < 4; ++atom) {
        assert(to_bits(first.force_x[atom]) == to_bits(second.force_x[atom]));
        assert(to_bits(first.force_y[atom]) == to_bits(second.force_y[atom]));
        assert(to_bits(first.force_z[atom]) == to_bits(second.force_z[atom]));
    }
}

void verify_rust_cpp_cpu_parity() {
    Fixture fixture;
    const System system = make_system(
        fixture.x, fixture.y, fixture.z, fixture.mass, fixture.charge);
    const Model model = make_model(fixture_parameters(fixture));
    const Context cpp_context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    const Context rust_context = make_context(BG_BACKEND_RUST_CPU);
    const Result cpp_result =
        evaluate(cpp_context.value, system.value, model.value);
    const Result rust_result =
        evaluate(rust_context.value, system.value, model.value);
    const Result rust_repeat =
        evaluate(rust_context.value, system.value, model.value);

    const std::array<uint64_t, 5> expected_energy{{
        UINT64_C(0xbfbe3560505c8b5a), UINT64_C(0x404421fcc22858dd),
        UINT64_C(0xc04ff151251cf865), UINT64_C(0x4031acb81f3a00d4),
        UINT64_C(0xc01840981bfe6b20)}};
    const std::array<double, 5> cpp_energy{{
        cpp_result.energy.real_space_kcal_per_mol,
        cpp_result.energy.reciprocal_space_kcal_per_mol,
        cpp_result.energy.self_kcal_per_mol,
        cpp_result.energy.pair_correction_kcal_per_mol,
        cpp_result.energy.total_kcal_per_mol}};
    const std::array<double, 5> rust_energy{{
        rust_result.energy.real_space_kcal_per_mol,
        rust_result.energy.reciprocal_space_kcal_per_mol,
        rust_result.energy.self_kcal_per_mol,
        rust_result.energy.pair_correction_kcal_per_mol,
        rust_result.energy.total_kcal_per_mol}};
    const std::array<double, 5> rust_repeat_energy{{
        rust_repeat.energy.real_space_kcal_per_mol,
        rust_repeat.energy.reciprocal_space_kcal_per_mol,
        rust_repeat.energy.self_kcal_per_mol,
        rust_repeat.energy.pair_correction_kcal_per_mol,
        rust_repeat.energy.total_kcal_per_mol}};
    for (std::size_t index = 0; index < expected_energy.size(); ++index) {
        assert(to_bits(rust_energy[index]) == expected_energy[index]);
        assert(to_bits(rust_energy[index]) == to_bits(rust_repeat_energy[index]));
        const double scale = std::max(1.0, std::abs(rust_energy[index]));
        assert(std::abs(cpp_energy[index] - rust_energy[index]) <=
               5.0e-12 * scale);
    }
    for (std::size_t atom = 0; atom < 4; ++atom) {
        const std::array<double, 3> cpp_force{{
            cpp_result.force_x[atom], cpp_result.force_y[atom],
            cpp_result.force_z[atom]}};
        const std::array<double, 3> rust_force{{
            rust_result.force_x[atom], rust_result.force_y[atom],
            rust_result.force_z[atom]}};
        const std::array<double, 3> rust_repeat_force{{
            rust_repeat.force_x[atom], rust_repeat.force_y[atom],
            rust_repeat.force_z[atom]}};
        for (std::size_t axis = 0; axis < 3; ++axis) {
            assert(to_bits(rust_force[axis]) ==
                   to_bits(rust_repeat_force[axis]));
            const double scale = std::max(1.0, std::abs(rust_force[axis]));
            assert(std::abs(cpp_force[axis] - rust_force[axis]) <=
                   5.0e-12 * scale);
        }
    }
}

bg_status try_create(
    bg_direct_ewald_parameters_v1 *parameters,
    bg_direct_ewald_error_code expected_code) {
    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    bg_direct_ewald_model_v1 *raw_model = nullptr;
    const bg_status status = bg_direct_ewald_model_v1_create(
        parameters, &raw_model, &error);
    assert(status != BG_STATUS_OK);
    assert(raw_model == nullptr);
    assert(error.code == expected_code);
    assert(error.detail[0] != '\0');
    return status;
}

void verify_model_validation_errors() {
    Fixture fixture;
    bg_direct_ewald_parameters_v1 parameters = fixture_parameters(fixture);

    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    error.code = BG_DIRECT_EWALD_ERROR_NON_NEUTRAL_SYSTEM;
    std::memcpy(error.detail, "stale", sizeof("stale"));
    bg_direct_ewald_model_v1 *raw_model =
        reinterpret_cast<bg_direct_ewald_model_v1 *>(
            static_cast<std::uintptr_t>(1));
    assert(bg_direct_ewald_model_v1_create(
               nullptr, &raw_model, &error) == BG_STATUS_INVALID_ARGUMENT);
    assert(raw_model == nullptr);
    assert(error.code == BG_DIRECT_EWALD_ERROR_NONE);
    assert(error.detail[0] == '\0');

    parameters = fixture_parameters(fixture);
    init_error(&error);
    error.code = BG_DIRECT_EWALD_ERROR_NON_NEUTRAL_SYSTEM;
    std::memcpy(error.detail, "stale", sizeof("stale"));
    assert(bg_direct_ewald_model_v1_create(
               &parameters, nullptr, &error) == BG_STATUS_INVALID_ARGUMENT);
    assert(error.code == BG_DIRECT_EWALD_ERROR_NONE);
    assert(error.detail[0] == '\0');

    parameters = fixture_parameters(fixture);
    init_error(&error);
    const bg_direct_ewald_parameters_v1 parameters_before = parameters;
    const bg_direct_ewald_error_v1 error_before = error;
    assert(bg_direct_ewald_model_v1_create(
               &parameters,
               reinterpret_cast<bg_direct_ewald_model_v1 **>(&parameters),
               &error) == BG_STATUS_INVALID_ARGUMENT);
    assert(std::memcmp(
               &parameters, &parameters_before, sizeof(parameters)) == 0);
    assert(std::memcmp(&error, &error_before, sizeof(error)) == 0);

    parameters = fixture_parameters(fixture);
    init_error(&error);
    const bg_direct_ewald_parameters_v1 alias_parameters_before = parameters;
    const bg_direct_ewald_error_v1 alias_error_before = error;
    assert(bg_direct_ewald_model_v1_create(
               &parameters,
               reinterpret_cast<bg_direct_ewald_model_v1 **>(&error),
               &error) == BG_STATUS_INVALID_ARGUMENT);
    assert(std::memcmp(
               &parameters, &alias_parameters_before, sizeof(parameters)) ==
           0);
    assert(std::memcmp(&error, &alias_error_before, sizeof(error)) == 0);

    auto verify_pair_rule_channel_alias = [](std::size_t channel_index) {
        Fixture alias_fixture;
        bg_direct_ewald_parameters_v1 alias_parameters =
            fixture_parameters(alias_fixture);
        bg_direct_ewald_error_v1 alias_error{};
        init_error(&alias_error);
        const Fixture fixture_before = alias_fixture;
        const bg_direct_ewald_parameters_v1 parameters_before =
            alias_parameters;
        const bg_direct_ewald_error_v1 error_before = alias_error;
        const std::array<void *, 5> channels{{
            alias_fixture.exclusion_i.data(),
            alias_fixture.exclusion_j.data(),
            alias_fixture.scale_i.data(),
            alias_fixture.scale_j.data(),
            alias_fixture.scales.data(),
        }};
        assert(bg_direct_ewald_model_v1_create(
                   &alias_parameters,
                   reinterpret_cast<bg_direct_ewald_model_v1 **>(
                       channels[channel_index]),
                   &alias_error) == BG_STATUS_INVALID_ARGUMENT);
        assert(std::memcmp(
                   &alias_parameters, &parameters_before,
                   sizeof(alias_parameters)) == 0);
        assert(std::memcmp(&alias_error, &error_before, sizeof(alias_error)) ==
               0);
        assert(alias_fixture.exclusion_i == fixture_before.exclusion_i);
        assert(alias_fixture.exclusion_j == fixture_before.exclusion_j);
        assert(alias_fixture.scale_i == fixture_before.scale_i);
        assert(alias_fixture.scale_j == fixture_before.scale_j);
        assert(alias_fixture.scales == fixture_before.scales);
    };
    for (std::size_t channel_index = 0; channel_index < 5;
         ++channel_index) {
        verify_pair_rule_channel_alias(channel_index);
    }

    std::array<uint64_t, 2> interior_exclusion_i{{0, 2}};
    std::array<uint64_t, 2> interior_exclusion_j{{1, 3}};
    parameters = fixture_parameters(fixture);
    parameters.exclusion_count = interior_exclusion_i.size();
    parameters.exclusion_atom_i = interior_exclusion_i.data();
    parameters.exclusion_atom_j = interior_exclusion_j.data();
    parameters.pair_scale_count = 0;
    const auto interior_exclusion_i_before = interior_exclusion_i;
    const auto interior_exclusion_j_before = interior_exclusion_j;
    init_error(&error);
    const bg_direct_ewald_error_v1 interior_error_before = error;
    assert(bg_direct_ewald_model_v1_create(
               &parameters,
               reinterpret_cast<bg_direct_ewald_model_v1 **>(
                   &interior_exclusion_i[1]),
               &error) == BG_STATUS_INVALID_ARGUMENT);
    assert(interior_exclusion_i == interior_exclusion_i_before);
    assert(interior_exclusion_j == interior_exclusion_j_before);
    assert(std::memcmp(
               &error, &interior_error_before, sizeof(error)) == 0);

    bg_direct_ewald_error_v1 channel_error{};
    init_error(&channel_error);
    parameters = fixture_parameters(fixture);
    parameters.exclusion_atom_i = &channel_error.reserved[0];
    const bg_direct_ewald_error_v1 error_channel_before = channel_error;
    const bg_direct_ewald_parameters_v1 error_alias_parameters_before =
        parameters;
    raw_model = reinterpret_cast<bg_direct_ewald_model_v1 *>(
        static_cast<std::uintptr_t>(1));
    assert(bg_direct_ewald_model_v1_create(
               &parameters, &raw_model, &channel_error) ==
           BG_STATUS_INVALID_ARGUMENT);
    assert(raw_model == reinterpret_cast<bg_direct_ewald_model_v1 *>(
                            static_cast<std::uintptr_t>(1)));
    assert(std::memcmp(
               &parameters, &error_alias_parameters_before,
               sizeof(parameters)) == 0);
    assert(std::memcmp(
               &channel_error, &error_channel_before,
               sizeof(channel_error)) == 0);

    parameters = fixture_parameters(fixture);
    parameters.exclusion_atom_i = nullptr;
    init_error(&error);
    error.code = BG_DIRECT_EWALD_ERROR_NON_NEUTRAL_SYSTEM;
    std::memcpy(error.detail, "stale", sizeof("stale"));
    raw_model = reinterpret_cast<bg_direct_ewald_model_v1 *>(
        static_cast<std::uintptr_t>(1));
    assert(bg_direct_ewald_model_v1_create(
               &parameters, &raw_model, &error) == BG_STATUS_INVALID_ARGUMENT);
    assert(raw_model == nullptr);
    assert(error.code == BG_DIRECT_EWALD_ERROR_NONE);
    assert(error.detail[0] == '\0');

    parameters = fixture_parameters(fixture);
    parameters.exclusion_count = UINT64_MAX;
    init_error(&error);
    raw_model = reinterpret_cast<bg_direct_ewald_model_v1 *>(
        static_cast<std::uintptr_t>(1));
    assert(bg_direct_ewald_model_v1_create(
               &parameters, &raw_model, &error) ==
           BG_STATUS_CAPACITY_OVERFLOW);
    assert(raw_model == nullptr);
    assert(error.code == BG_DIRECT_EWALD_ERROR_CAPACITY_EXCEEDED);
    assert(error.detail[0] != '\0');

    parameters = fixture_parameters(fixture);
    parameters.atom_count = 0;
    assert(try_create(&parameters, BG_DIRECT_EWALD_ERROR_EMPTY_SYSTEM) ==
           BG_STATUS_INVALID_ARGUMENT);

    parameters = fixture_parameters(fixture);
    parameters.cell_lengths_angstrom[0] = 0.0;
    assert(try_create(&parameters, BG_DIRECT_EWALD_ERROR_INVALID_CELL) ==
           BG_STATUS_INVALID_ARGUMENT);

    parameters = fixture_parameters(fixture);
    parameters.real_space_cutoff_angstrom = 9.0;
    assert(try_create(
               &parameters,
               BG_DIRECT_EWALD_ERROR_CUTOFF_VIOLATES_MINIMUM_IMAGE) ==
           BG_STATUS_INVALID_ARGUMENT);

    parameters = fixture_parameters(fixture);
    fixture.exclusion_j[0] = 0;
    assert(try_create(
               &parameters, BG_DIRECT_EWALD_ERROR_REPEATED_ATOM_INDEX) ==
           BG_STATUS_INVALID_ARGUMENT);

    fixture.exclusion_j[0] = 1;
    parameters = fixture_parameters(fixture);
    fixture.scale_i[0] = 1;
    fixture.scale_j[0] = 0;
    assert(try_create(
               &parameters, BG_DIRECT_EWALD_ERROR_CONFLICTING_PAIR_RULE) ==
           BG_STATUS_INVALID_ARGUMENT);

    fixture.scale_i[0] = 2;
    fixture.scale_j[0] = 3;
    parameters = fixture_parameters(fixture);
    fixture.scale_j[0] = 9;
    assert(try_create(
               &parameters, BG_DIRECT_EWALD_ERROR_ATOM_INDEX_OUT_OF_RANGE) ==
           BG_STATUS_INVALID_ARGUMENT);
}

void verify_evaluation_transactionality_and_typed_errors() {
    Fixture fixture;
    const Context context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    const Model model = make_model(fixture_parameters(fixture));
    fixture.charge[3] = 0.31;
    const System nonneutral = make_system(
        fixture.x, fixture.y, fixture.z, fixture.mass, fixture.charge);

    bg_direct_ewald_energy_components_v1 energy{};
    assert(bg_direct_ewald_energy_components_v1_init(
               &energy, sizeof(energy), BG_DIRECT_EWALD_ABI_VERSION) ==
           BG_STATUS_OK);
    energy.real_space_kcal_per_mol = 101.0;
    energy.reciprocal_space_kcal_per_mol = 102.0;
    energy.self_kcal_per_mol = 103.0;
    energy.pair_correction_kcal_per_mol = 104.0;
    energy.total_kcal_per_mol = 105.0;
    const bg_direct_ewald_energy_components_v1 energy_before = energy;
    std::array<double, 4> force_x{{11.0, 12.0, 13.0, 14.0}};
    std::array<double, 4> force_y{{21.0, 22.0, 23.0, 24.0}};
    std::array<double, 4> force_z{{31.0, 32.0, 33.0, 34.0}};
    const auto force_x_before = force_x;
    const auto force_y_before = force_y;
    const auto force_z_before = force_z;
    bg_direct_ewald_force_soa_v1 forces{};
    assert(bg_direct_ewald_force_soa_v1_init(
               &forces, sizeof(forces), BG_DIRECT_EWALD_ABI_VERSION) ==
           BG_STATUS_OK);
    forces.atom_capacity = 4;
    forces.atom_count = UINT64_C(99);
    forces.x_kcal_per_mol_angstrom = force_x.data();
    forces.y_kcal_per_mol_angstrom = force_y.data();
    forces.z_kcal_per_mol_angstrom = force_z.data();
    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    assert(bg_context_evaluate_direct_ewald_v1(
               context.value, nonneutral.value, model.value, &energy, &forces,
               &error) == BG_STATUS_NUMERICAL_ERROR);
    assert(error.code == BG_DIRECT_EWALD_ERROR_NON_NEUTRAL_SYSTEM);
    assert(std::memcmp(&energy, &energy_before, sizeof(energy)) == 0);
    assert(force_x == force_x_before);
    assert(force_y == force_y_before);
    assert(force_z == force_z_before);
    assert(forces.atom_count == UINT64_C(99));

    auto verify_mandatory_null_clears_error = [&](const bg_context *candidate_context,
                                                   const bg_system *candidate_system,
                                                   const bg_direct_ewald_model_v1 *candidate_model,
                                                   bg_direct_ewald_energy_components_v1 *candidate_energy) {
        assert(error.code == BG_DIRECT_EWALD_ERROR_NON_NEUTRAL_SYSTEM);
        assert(bg_context_evaluate_direct_ewald_v1(
                   candidate_context, candidate_system, candidate_model,
                   candidate_energy, &forces, &error) ==
               BG_STATUS_INVALID_ARGUMENT);
        assert(error.code == BG_DIRECT_EWALD_ERROR_NONE);
        assert(error.detail[0] == '\0');
        assert(std::memcmp(&energy, &energy_before, sizeof(energy)) == 0);
        assert(force_x == force_x_before);
        assert(force_y == force_y_before);
        assert(force_z == force_z_before);
        assert(forces.atom_count == UINT64_C(99));
        assert(bg_context_evaluate_direct_ewald_v1(
                   context.value, nonneutral.value, model.value, &energy,
                   &forces, &error) == BG_STATUS_NUMERICAL_ERROR);
        assert(error.code == BG_DIRECT_EWALD_ERROR_NON_NEUTRAL_SYSTEM);
    };
    verify_mandatory_null_clears_error(
        nullptr, nonneutral.value, model.value, &energy);
    verify_mandatory_null_clears_error(
        context.value, nullptr, model.value, &energy);
    verify_mandatory_null_clears_error(
        context.value, nonneutral.value, nullptr, &energy);
    verify_mandatory_null_clears_error(
        context.value, nonneutral.value, model.value, nullptr);

    fixture.charge[3] = 0.30000000000000004;
    const System neutral = make_system(
        fixture.x, fixture.y, fixture.z, fixture.mass, fixture.charge);
    forces.atom_capacity = 3;
    assert(bg_context_evaluate_direct_ewald_v1(
               context.value, neutral.value, model.value, &energy, &forces,
               &error) == BG_STATUS_BUFFER_TOO_SMALL);
    assert(error.code == BG_DIRECT_EWALD_ERROR_NONE);
    assert(error.detail[0] == '\0');
    assert(std::memcmp(&energy, &energy_before, sizeof(energy)) == 0);
    assert(force_x == force_x_before);

    Fixture close_fixture;
    close_fixture.x[1] = close_fixture.x[0] + 1.0e-9;
    close_fixture.y[1] = close_fixture.y[0];
    close_fixture.z[1] = close_fixture.z[0];
    const System close_system = make_system(
        close_fixture.x, close_fixture.y, close_fixture.z,
        close_fixture.mass, close_fixture.charge);
    forces.atom_capacity = 4;
    init_error(&error);
    assert(bg_context_evaluate_direct_ewald_v1(
               context.value, close_system.value, model.value, &energy,
               &forces, &error) == BG_STATUS_NUMERICAL_ERROR);
    assert(error.code == BG_DIRECT_EWALD_ERROR_PAIR_BELOW_MINIMUM_DISTANCE);
    assert(std::memcmp(&energy, &energy_before, sizeof(energy)) == 0);
    assert(force_x == force_x_before);
}

bg_direct_ewald_error_code evaluate_typed_failure(
    const bg_context *context,
    const bg_system *system,
    const bg_direct_ewald_model_v1 *model,
    bg_status expected_status = BG_STATUS_NUMERICAL_ERROR) {
    bg_direct_ewald_energy_components_v1 energy{};
    assert(bg_direct_ewald_energy_components_v1_init(
               &energy, sizeof(energy), BG_DIRECT_EWALD_ABI_VERSION) ==
           BG_STATUS_OK);
    energy.total_kcal_per_mol = 77.0;
    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    assert(bg_context_evaluate_direct_ewald_v1(
               context, system, model, &energy, nullptr, &error) ==
           expected_status);
    assert(energy.total_kcal_per_mol == 77.0);
    assert(error.code != BG_DIRECT_EWALD_ERROR_NONE);
    assert(error.detail[0] != '\0');
    return error.code;
}

void verify_numeric_error_parity() {
    const Context cpp_context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    const Context rust_context = make_context(BG_BACKEND_RUST_CPU);
    const std::array<double, 2> zeros{{0.0, 0.0}};
    const std::array<double, 2> mass{{1.0, 1.0}};

    auto verify = [&](const std::array<double, 2> &x,
                      const std::array<double, 2> &y,
                      const std::array<double, 2> &z,
                      const std::array<double, 2> &charge,
                      const bg_direct_ewald_parameters_v1 &parameters,
                      bg_direct_ewald_error_code expected) {
        const System system = make_system(x, y, z, mass, charge);
        const Model model = make_model(parameters);
        assert(evaluate_typed_failure(
                   cpp_context.value, system.value, model.value) == expected);
        assert(evaluate_typed_failure(
                   rust_context.value, system.value, model.value) == expected);
    };

    const std::array<double, 2> unit_charges{{1.0, -1.0}};
    bg_direct_ewald_parameters_v1 parameters = two_atom_parameters();
    verify(
        {{0.0, 2.0}}, zeros, zeros, unit_charges, parameters,
        BG_DIRECT_EWALD_ERROR_AMBIGUOUS_REAL_SPACE_CUTOFF);

    parameters = two_atom_parameters();
    parameters.minimum_pair_distance_angstrom = 0.25;
    verify(
        {{0.0, 0.25}}, zeros, zeros, unit_charges, parameters,
        BG_DIRECT_EWALD_ERROR_AMBIGUOUS_MINIMUM_PAIR_DISTANCE);

    std::array<uint64_t, 1> exclusion_i{{0}};
    std::array<uint64_t, 1> exclusion_j{{1}};
    parameters = two_atom_parameters();
    parameters.cell_lengths_angstrom[1] = 12.0;
    parameters.cell_lengths_angstrom[2] = 14.0;
    parameters.real_space_cutoff_angstrom = 4.9;
    parameters.exclusion_count = 1;
    parameters.exclusion_atom_i = exclusion_i.data();
    parameters.exclusion_atom_j = exclusion_j.data();
    verify(
        {{0.0, 5.0}}, {{1.0, 1.0}}, {{1.0, 1.0}}, unit_charges,
        parameters, BG_DIRECT_EWALD_ERROR_AMBIGUOUS_PAIR_CORRECTION_IMAGE);

    parameters = two_atom_parameters();
    parameters.cell_lengths_angstrom[0] = 3.0;
    parameters.cell_lengths_angstrom[1] = 3.0;
    parameters.cell_lengths_angstrom[2] = 3.0;
    parameters.alpha_per_angstrom = 27.4;
    parameters.real_space_cutoff_angstrom = 1.1;
    parameters.dielectric = 1.0e-12;
    verify(
        {{0.0, 1.0}}, zeros, zeros, {{16.0, -16.0}}, parameters,
        BG_DIRECT_EWALD_ERROR_DAMPING_UNDERFLOW);

    parameters = two_atom_parameters();
    parameters.cell_lengths_angstrom[0] = 1.0;
    parameters.cell_lengths_angstrom[1] = 1.0;
    parameters.cell_lengths_angstrom[2] = 1.0e9;
    parameters.real_space_cutoff_angstrom = 0.2;
    parameters.dielectric = 1.0e-12;
    verify(
        {{0.0, 0.3}}, zeros, {{0.0, 1.0e-317}}, {{16.0, -16.0}},
        parameters, BG_DIRECT_EWALD_ERROR_PHASE_UNDERFLOW);

    std::array<double, 50> large_x{};
    std::array<double, 50> large_y{};
    std::array<double, 50> large_z{};
    std::array<double, 50> large_mass{};
    std::array<double, 50> nonneutral_charge{};
    large_mass.fill(1.0);
    nonneutral_charge.fill(1.0);
    parameters = two_atom_parameters();
    parameters.atom_count = 50;
    parameters.reciprocal_max_indices[0] = 14;
    parameters.reciprocal_max_indices[1] = 26;
    parameters.reciprocal_max_indices[2] = 32;
    const System high_work_nonneutral = make_system(
        large_x, large_y, large_z, large_mass, nonneutral_charge);
    const Model high_work_model = make_model(parameters);
    assert(evaluate_typed_failure(
               cpp_context.value, high_work_nonneutral.value,
               high_work_model.value) ==
           BG_DIRECT_EWALD_ERROR_NON_NEUTRAL_SYSTEM);
    assert(evaluate_typed_failure(
               rust_context.value, high_work_nonneutral.value,
               high_work_model.value) ==
           BG_DIRECT_EWALD_ERROR_NON_NEUTRAL_SYSTEM);

    for (std::size_t atom = 0; atom < nonneutral_charge.size(); ++atom) {
        nonneutral_charge[atom] = atom % 2U == 0U ? 1.0 : -1.0;
    }
    const System high_work_neutral = make_system(
        large_x, large_y, large_z, large_mass, nonneutral_charge);
    assert(evaluate_typed_failure(
               cpp_context.value, high_work_neutral.value,
               high_work_model.value, BG_STATUS_CAPACITY_OVERFLOW) ==
           BG_DIRECT_EWALD_ERROR_CAPACITY_EXCEEDED);
    assert(evaluate_typed_failure(
               rust_context.value, high_work_neutral.value,
               high_work_model.value, BG_STATUS_CAPACITY_OVERFLOW) ==
           BG_DIRECT_EWALD_ERROR_CAPACITY_EXCEEDED);

    const std::array<double, 0> empty{};
    const System empty_system = make_system(empty, empty, empty, empty, empty);
    const Model two_atom_model = make_model(two_atom_parameters());
    assert(evaluate_typed_failure(
               cpp_context.value, empty_system.value, two_atom_model.value,
               BG_STATUS_INVALID_ARGUMENT) ==
           BG_DIRECT_EWALD_ERROR_EMPTY_SYSTEM);
    assert(evaluate_typed_failure(
               rust_context.value, empty_system.value, two_atom_model.value,
               BG_STATUS_INVALID_ARGUMENT) ==
           BG_DIRECT_EWALD_ERROR_EMPTY_SYSTEM);

    std::array<double, 3> mismatch_x{};
    std::array<double, 3> mismatch_mass{};
    std::array<double, 3> mismatch_charge{{1.0, -1.0, 0.0}};
    mismatch_mass.fill(1.0);
    const System mismatched_system = make_system(
        mismatch_x, mismatch_x, mismatch_x, mismatch_mass, mismatch_charge);
    assert(evaluate_typed_failure(
               cpp_context.value, mismatched_system.value,
               two_atom_model.value, BG_STATUS_INVALID_ARGUMENT) ==
           BG_DIRECT_EWALD_ERROR_CHARGE_COUNT_MISMATCH);
    assert(evaluate_typed_failure(
               rust_context.value, mismatched_system.value,
               two_atom_model.value, BG_STATUS_INVALID_ARGUMENT) ==
           BG_DIRECT_EWALD_ERROR_CHARGE_COUNT_MISMATCH);

    std::array<double, 4097> over_capacity_positions{};
    std::array<double, 4097> over_capacity_mass{};
    std::array<double, 4097> over_capacity_charge{};
    over_capacity_mass.fill(1.0);
    over_capacity_charge.fill(1.0);
    const System over_capacity_system = make_system(
        over_capacity_positions, over_capacity_positions,
        over_capacity_positions, over_capacity_mass, over_capacity_charge);
    assert(evaluate_typed_failure(
               cpp_context.value, over_capacity_system.value,
               two_atom_model.value, BG_STATUS_CAPACITY_OVERFLOW) ==
           BG_DIRECT_EWALD_ERROR_CAPACITY_EXCEEDED);
    assert(evaluate_typed_failure(
               rust_context.value, over_capacity_system.value,
               two_atom_model.value, BG_STATUS_CAPACITY_OVERFLOW) ==
           BG_DIRECT_EWALD_ERROR_CAPACITY_EXCEEDED);
}

void verify_hip_fails_closed_without_device_execution() {
    Fixture fixture;
    const System system = make_system(
        fixture.x, fixture.y, fixture.z, fixture.mass, fixture.charge);
    const Model model = make_model(fixture_parameters(fixture));
    bg_context fake_context{};
    fake_context.backend = BG_BACKEND_HIP_SAFE;
    fake_context.unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
    Result result;
    assert(bg_direct_ewald_energy_components_v1_init(
               &result.energy, sizeof(result.energy),
               BG_DIRECT_EWALD_ABI_VERSION) == BG_STATUS_OK);
    bg_direct_ewald_error_v1 error{};
    init_error(&error);
    assert(bg_context_evaluate_direct_ewald_v1(
               &fake_context, system.value, model.value, &result.energy,
               nullptr, &error) == BG_STATUS_UNSUPPORTED_BACKEND);
    assert(error.code == BG_DIRECT_EWALD_ERROR_NONE);
}

}  // namespace

int main() {
    verify_abi_identity_and_initializer_transactionality();
    verify_frozen_fixture_and_deep_ownership();
    verify_rust_cpp_cpu_parity();
    verify_model_validation_errors();
    verify_evaluation_transactionality_and_typed_errors();
    verify_numeric_error_parity();
    verify_hip_fails_closed_without_device_execution();
    return 0;
}
