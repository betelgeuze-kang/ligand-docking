#define BG_DISABLE_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#define BG_DISABLE_DIRECT_EWALD_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#define BG_DISABLE_PARTICLE_MESH_RECIPROCAL_DESCRIPTOR_INIT_CONVENIENCE_MACROS
#include "betelgeuze/direct_ewald.h"
#include "betelgeuze/particle_mesh_reciprocal.h"

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
#include <string_view>
#include <utility>
#include <vector>

namespace {

constexpr char kLiteralTypedFailure[] = "literal typed failure";
constexpr std::string_view kLiteralTypedFailureView{
    kLiteralTypedFailure, sizeof(kLiteralTypedFailure) - 1U};
static_assert(
    kLiteralTypedFailureView.size() == sizeof(kLiteralTypedFailure) - 1U);

struct Context final {
    bg_context *value = nullptr;
    Context() = default;
    Context(const Context &) = delete;
    Context &operator=(const Context &) = delete;
    Context(Context &&other) noexcept
        : value(std::exchange(other.value, nullptr)) {}
    Context &operator=(Context &&) = delete;
    ~Context() { bg_context_destroy(value); }
};

struct System final {
    bg_system *value = nullptr;
    System() = default;
    System(const System &) = delete;
    System &operator=(const System &) = delete;
    System(System &&other) noexcept
        : value(std::exchange(other.value, nullptr)) {}
    System &operator=(System &&) = delete;
    ~System() { bg_system_destroy(value); }
};

struct Model final {
    bg_particle_mesh_reciprocal_model_v1 *value = nullptr;
    Model() = default;
    Model(const Model &) = delete;
    Model &operator=(const Model &) = delete;
    Model(Model &&other) noexcept
        : value(std::exchange(other.value, nullptr)) {}
    Model &operator=(Model &&) = delete;
    ~Model() { bg_particle_mesh_reciprocal_model_v1_destroy(value); }
};

struct DirectModel final {
    bg_direct_ewald_model_v1 *value = nullptr;
    DirectModel() = default;
    DirectModel(const DirectModel &) = delete;
    DirectModel &operator=(const DirectModel &) = delete;
    DirectModel(DirectModel &&other) noexcept
        : value(std::exchange(other.value, nullptr)) {}
    DirectModel &operator=(DirectModel &&) = delete;
    ~DirectModel() { bg_direct_ewald_model_v1_destroy(value); }
};

struct Fixture final {
    std::array<double, 4> x{{1.25, 5.1, 10.2, 15.4}};
    std::array<double, 4> y{{2.5, 3.2, 12.3, 17.1}};
    std::array<double, 4> z{{3.75, 8.4, 7.7, 19.3}};
    std::array<double, 4> mass{{1.0, 1.0, 1.0, 1.0}};
    std::array<double, 4> charge{{
        0.7, -0.4, -0.6, 0.30000000000000004}};
};

struct Result final {
    bg_particle_mesh_reciprocal_energy_v1 energy{};
    std::vector<double> force_x;
    std::vector<double> force_y;
    std::vector<double> force_z;
};

Result evaluate_fixture_variant(
    bg_backend backend,
    const std::array<double, 4> &x,
    const std::array<double, 4> &y,
    const std::array<double, 4> &z,
    const std::array<double, 4> &charge,
    std::uint32_t mesh = 16U);

constexpr std::array<std::uint64_t, 13> kFrozenBits{{
    UINT64_C(0x40441de71e7a685d),
    UINT64_C(0x3ff7abf233cae3fe),
    UINT64_C(0x3fe3f50c6800dce2),
    UINT64_C(0x4003a5fe62912de6),
    UINT64_C(0xbff82153b58fe4a2),
    UINT64_C(0xbfdf03fd220eaedd),
    UINT64_C(0xbff996032fc40900),
    UINT64_C(0x3fd5c06e1da10cd7),
    UINT64_C(0x3fcf508ce37d6938),
    UINT64_C(0xbfdf6cb861fdf624),
    UINT64_C(0xbfd2c72283b8727e),
    UINT64_C(0xbfda223bfc4695cd),
    UINT64_C(0xbfd9e0699f282115)}};

std::uint64_t to_bits(double value) noexcept {
    std::uint64_t result = 0U;
    std::memcpy(&result, &value, sizeof(result));
    return result;
}

double from_bits(std::uint64_t raw) noexcept {
    double result = 0.0;
    std::memcpy(&result, &raw, sizeof(result));
    return result;
}

bool close(double observed, double expected, double tolerance) noexcept {
    const double scale = 1.0 + std::max(std::abs(observed), std::abs(expected));
    return std::abs(observed - expected) <= tolerance * scale;
}

bool relative_close(
    double observed,
    double expected,
    double tolerance) noexcept {
    return std::abs(observed - expected) <=
           tolerance * std::max(std::abs(observed), std::abs(expected));
}

void init_error(bg_particle_mesh_reciprocal_error_v1 *error) {
    assert(bg_particle_mesh_reciprocal_error_v1_init(
               error, sizeof(*error),
               BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION) == BG_STATUS_OK);
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
    particles.particle_count = Size;
    particles.position_x_angstrom = x.data();
    particles.position_y_angstrom = y.data();
    particles.position_z_angstrom = z.data();
    particles.mass_dalton = mass.data();
    particles.charge_elementary = charge.data();
    System system;
    assert(bg_system_create(&particles, &system.value) == BG_STATUS_OK);
    return system;
}

bg_particle_mesh_reciprocal_parameters_v1 fixture_parameters(
    std::uint32_t mesh_dimension = 16U) {
    bg_particle_mesh_reciprocal_parameters_v1 parameters{};
    assert(bg_particle_mesh_reciprocal_parameters_v1_init(
               &parameters, sizeof(parameters),
               BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION) == BG_STATUS_OK);
    parameters.atom_count = 4U;
    parameters.cell_lengths_angstrom[0] = 18.0;
    parameters.cell_lengths_angstrom[1] = 20.0;
    parameters.cell_lengths_angstrom[2] = 22.0;
    parameters.alpha_per_angstrom = 0.31;
    parameters.mesh_dimensions[0] = mesh_dimension;
    parameters.mesh_dimensions[1] = mesh_dimension;
    parameters.mesh_dimensions[2] = mesh_dimension;
    parameters.dielectric = 1.0;
    return parameters;
}

Model make_model(
    const bg_particle_mesh_reciprocal_parameters_v1 &parameters) {
    bg_particle_mesh_reciprocal_error_v1 error{};
    init_error(&error);
    Model model;
    assert(bg_particle_mesh_reciprocal_model_v1_create(
               &parameters, &model.value, &error) == BG_STATUS_OK);
    assert(error.code == BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONE);
    return model;
}

Result evaluate(
    const bg_context *context,
    const bg_system *system,
    const bg_particle_mesh_reciprocal_model_v1 *model,
    std::size_t atom_count,
    bool compute_forces = true) {
    Result result;
    assert(bg_particle_mesh_reciprocal_energy_v1_init(
               &result.energy, sizeof(result.energy),
               BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION) == BG_STATUS_OK);
    bg_particle_mesh_reciprocal_force_soa_v1 forces{};
    bg_particle_mesh_reciprocal_force_soa_v1 *force_pointer = nullptr;
    if (compute_forces) {
        result.force_x.resize(atom_count);
        result.force_y.resize(atom_count);
        result.force_z.resize(atom_count);
        assert(bg_particle_mesh_reciprocal_force_soa_v1_init(
                   &forces, sizeof(forces),
                   BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION) ==
               BG_STATUS_OK);
        forces.atom_capacity = atom_count;
        forces.x_kcal_per_mol_angstrom = result.force_x.data();
        forces.y_kcal_per_mol_angstrom = result.force_y.data();
        forces.z_kcal_per_mol_angstrom = result.force_z.data();
        force_pointer = &forces;
    }
    bg_particle_mesh_reciprocal_error_v1 error{};
    init_error(&error);
    assert(bg_context_evaluate_particle_mesh_reciprocal_v1(
               context, system, model, &result.energy, force_pointer,
               &error) == BG_STATUS_OK);
    assert(error.code == BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONE);
    assert(error.detail[0] == '\0');
    if (compute_forces) {
        assert(forces.atom_count == atom_count);
    }
    return result;
}

template <typename Descriptor, typename Initializer>
void verify_initializer_transactionality(Initializer initializer) {
    Descriptor descriptor{};
    std::memset(&descriptor, 0x5a, sizeof(descriptor));
    std::array<unsigned char, sizeof(Descriptor)> before{};
    std::memcpy(before.data(), &descriptor, sizeof(descriptor));
    assert(initializer(
               &descriptor, sizeof(descriptor) - 1U,
               BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION) ==
           BG_STATUS_ABI_MISMATCH);
    assert(std::memcmp(&descriptor, before.data(), sizeof(descriptor)) == 0);
    assert(initializer(&descriptor, sizeof(descriptor), UINT32_C(99)) ==
           BG_STATUS_ABI_MISMATCH);
    assert(std::memcmp(&descriptor, before.data(), sizeof(descriptor)) == 0);
    assert(initializer(
               &descriptor, sizeof(descriptor),
               BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION) == BG_STATUS_OK);
}

void verify_abi_layout_and_initializers() {
    static_assert(sizeof(bg_particle_mesh_reciprocal_parameters_v1) == 112U);
    static_assert(sizeof(bg_particle_mesh_reciprocal_energy_v1) == 56U);
    static_assert(sizeof(bg_particle_mesh_reciprocal_force_soa_v1) == 88U);
    static_assert(sizeof(bg_particle_mesh_reciprocal_error_v1) == 304U);
    static_assert(offsetof(
                      bg_particle_mesh_reciprocal_parameters_v1,
                      mesh_dimensions) == 56U);
    assert(bg_particle_mesh_reciprocal_abi_version() == 1U);
    assert(bg_particle_mesh_reciprocal_abi_version_major() == 1U);
    assert(bg_particle_mesh_reciprocal_abi_version_minor() == 0U);
    assert(std::string(bg_particle_mesh_reciprocal_abi_version_string()) ==
           "1.0.0");
    assert(std::string(
               bg_particle_mesh_reciprocal_model_v1_profile_id()) ==
           "betelgeuze.native_particle_mesh_reciprocal/1.0.0");
    assert(BG_PARTICLE_MESH_RECIPROCAL_CARDINAL_B_SPLINE_ORDER == 4U);

    verify_initializer_transactionality<bg_particle_mesh_reciprocal_parameters_v1>(
        bg_particle_mesh_reciprocal_parameters_v1_init);
    verify_initializer_transactionality<
        bg_particle_mesh_reciprocal_energy_v1>(
        bg_particle_mesh_reciprocal_energy_v1_init);
    verify_initializer_transactionality<bg_particle_mesh_reciprocal_force_soa_v1>(
        bg_particle_mesh_reciprocal_force_soa_v1_init);
    verify_initializer_transactionality<bg_particle_mesh_reciprocal_error_v1>(
        bg_particle_mesh_reciprocal_error_v1_init);
}

void verify_frozen_fixture_and_deep_ownership() {
    Fixture fixture;
    const System system = make_system(
        fixture.x, fixture.y, fixture.z, fixture.mass, fixture.charge);
    auto parameters = fixture_parameters();
    const Model model = make_model(parameters);
    std::uint64_t atom_count = 0U;
    assert(bg_particle_mesh_reciprocal_model_v1_get_atom_count(
               model.value, &atom_count) == BG_STATUS_OK);
    assert(atom_count == 4U);

    parameters.atom_count = 2U;
    parameters.cell_lengths_angstrom[0] = 1.0;
    parameters.alpha_per_angstrom = 1.0;
    parameters.mesh_dimensions[0] = 4U;
    parameters.dielectric = 2.0;

    const std::array<bg_backend, 2> lanes{
        BG_BACKEND_CPP_CPU_REFERENCE, BG_BACKEND_RUST_CPU};
    std::array<Result, 2> results;
    for (std::size_t lane = 0U; lane < lanes.size(); ++lane) {
        const Context context = make_context(lanes[lane]);
        results[lane] = evaluate(
            context.value, system.value, model.value, fixture.x.size());
        const Result repeated = evaluate(
            context.value, system.value, model.value, fixture.x.size());
        assert(to_bits(results[lane].energy.reciprocal_space_kcal_per_mol) ==
               to_bits(repeated.energy.reciprocal_space_kcal_per_mol));
        for (std::size_t atom = 0U; atom < fixture.x.size(); ++atom) {
            assert(to_bits(results[lane].force_x[atom]) ==
                   to_bits(repeated.force_x[atom]));
            assert(to_bits(results[lane].force_y[atom]) ==
                   to_bits(repeated.force_y[atom]));
            assert(to_bits(results[lane].force_z[atom]) ==
                   to_bits(repeated.force_z[atom]));
        }
    }

    assert(to_bits(results[1].energy.reciprocal_space_kcal_per_mol) ==
           kFrozenBits[0]);
    std::size_t frozen = 1U;
    for (std::size_t atom = 0U; atom < fixture.x.size(); ++atom) {
        for (const double value : {results[1].force_x[atom],
                                   results[1].force_y[atom],
                                   results[1].force_z[atom]}) {
            assert(to_bits(value) == kFrozenBits[frozen++]);
        }
    }
    assert(close(
        results[0].energy.reciprocal_space_kcal_per_mol,
        from_bits(kFrozenBits[0]), 5.0e-12));
    frozen = 1U;
    for (std::size_t atom = 0U; atom < fixture.x.size(); ++atom) {
        for (const double value : {results[0].force_x[atom],
                                   results[0].force_y[atom],
                                   results[0].force_z[atom]}) {
            assert(close(value, from_bits(kFrozenBits[frozen++]), 5.0e-12));
        }
    }

    for (std::size_t lane = 0U; lane < lanes.size(); ++lane) {
        const Context context = make_context(lanes[lane]);
        const Result energy_only = evaluate(
            context.value, system.value, model.value, fixture.x.size(),
            false);
        assert(to_bits(energy_only.energy.reciprocal_space_kcal_per_mol) ==
               to_bits(results[lane].energy.reciprocal_space_kcal_per_mol));
        assert(energy_only.force_x.empty());
    }
}

void verify_rust_cpp_cpu_parity() {
    Fixture fixture;
    const Result cpp = evaluate_fixture_variant(
        BG_BACKEND_CPP_CPU_REFERENCE, fixture.x, fixture.y, fixture.z,
        fixture.charge);
    const Result rust = evaluate_fixture_variant(
        BG_BACKEND_RUST_CPU, fixture.x, fixture.y, fixture.z,
        fixture.charge);
    assert(close(
        cpp.energy.reciprocal_space_kcal_per_mol,
        rust.energy.reciprocal_space_kcal_per_mol, 5.0e-12));
    for (std::size_t atom = 0U; atom < fixture.x.size(); ++atom) {
        assert(close(cpp.force_x[atom], rust.force_x[atom], 5.0e-12));
        assert(close(cpp.force_y[atom], rust.force_y[atom], 5.0e-12));
        assert(close(cpp.force_z[atom], rust.force_z[atom], 5.0e-12));
    }
}

void verify_evaluation_transactionality_and_typed_errors() {
    Fixture fixture;
    const Context context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    const Model model = make_model(fixture_parameters());
    System system = make_system(
        fixture.x, fixture.y, fixture.z, fixture.mass, fixture.charge);

    bg_particle_mesh_reciprocal_energy_v1 energy{};
    assert(bg_particle_mesh_reciprocal_energy_v1_init(
               &energy, sizeof(energy),
               BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION) == BG_STATUS_OK);
    energy.reciprocal_space_kcal_per_mol = 913.25;
    std::array<double, 4> x{{91.0, 92.0, 93.0, 94.0}};
    std::array<double, 4> y{{81.0, 82.0, 83.0, 84.0}};
    std::array<double, 4> z{{71.0, 72.0, 73.0, 74.0}};
    bg_particle_mesh_reciprocal_force_soa_v1 forces{};
    assert(bg_particle_mesh_reciprocal_force_soa_v1_init(
               &forces, sizeof(forces),
               BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION) == BG_STATUS_OK);
    forces.atom_capacity = 4U;
    forces.atom_count = 77U;
    forces.x_kcal_per_mol_angstrom = x.data();
    forces.y_kcal_per_mol_angstrom = y.data();
    forces.z_kcal_per_mol_angstrom = z.data();
    const auto energy_before = energy;
    const auto forces_before = forces;
    const auto x_before = x;
    const auto y_before = y;
    const auto z_before = z;
    bg_particle_mesh_reciprocal_error_v1 error{};
    init_error(&error);

    system.value->charge[0] += 0.25;
    assert(bg_context_evaluate_particle_mesh_reciprocal_v1(
               context.value, system.value, model.value, &energy, &forces,
               &error) == BG_STATUS_NUMERICAL_ERROR);
    assert(error.code ==
           BG_PARTICLE_MESH_RECIPROCAL_ERROR_NON_NEUTRAL_SYSTEM);
    assert(std::memcmp(&energy, &energy_before, sizeof(energy)) == 0);
    assert(std::memcmp(&forces, &forces_before, sizeof(forces)) == 0);
    assert(x == x_before && y == y_before && z == z_before);

    system.value->position_z[3] =
        std::numeric_limits<double>::quiet_NaN();
    system.value->charge[0] = std::numeric_limits<double>::infinity();
    init_error(&error);
    assert(bg_context_evaluate_particle_mesh_reciprocal_v1(
               context.value, system.value, model.value, &energy, &forces,
               &error) == BG_STATUS_INVALID_ARGUMENT);
    assert(error.code ==
           BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONFINITE_COORDINATE);

    system.value->position_z[3] = fixture.z[3];
    init_error(&error);
    assert(bg_context_evaluate_particle_mesh_reciprocal_v1(
               context.value, system.value, model.value, &energy, &forces,
               &error) == BG_STATUS_INVALID_ARGUMENT);
    assert(error.code ==
           BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONFINITE_CHARGE);
}

void verify_oversized_system_capacity_precedence() {
    constexpr std::size_t kOversizedAtomCount = 4'097U;
    std::array<double, kOversizedAtomCount> x{};
    std::array<double, kOversizedAtomCount> y{};
    std::array<double, kOversizedAtomCount> z{};
    std::array<double, kOversizedAtomCount> mass{};
    std::array<double, kOversizedAtomCount> charge{};
    mass.fill(1.0);
    const System system = make_system(x, y, z, mass, charge);
    const Model model = make_model(fixture_parameters());

    for (const bg_backend backend :
         {BG_BACKEND_CPP_CPU_REFERENCE, BG_BACKEND_RUST_CPU}) {
        const Context context = make_context(backend);
        bg_particle_mesh_reciprocal_energy_v1 energy{};
        assert(bg_particle_mesh_reciprocal_energy_v1_init(
                   &energy, sizeof(energy),
                   BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION) ==
               BG_STATUS_OK);
        energy.reciprocal_space_kcal_per_mol = 913.25;

        std::array<double, 4> force_x{{91.0, 92.0, 93.0, 94.0}};
        std::array<double, 4> force_y{{81.0, 82.0, 83.0, 84.0}};
        std::array<double, 4> force_z{{71.0, 72.0, 73.0, 74.0}};
        bg_particle_mesh_reciprocal_force_soa_v1 forces{};
        assert(bg_particle_mesh_reciprocal_force_soa_v1_init(
                   &forces, sizeof(forces),
                   BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION) ==
               BG_STATUS_OK);
        forces.atom_capacity = 4U;
        forces.atom_count = 77U;
        forces.x_kcal_per_mol_angstrom = force_x.data();
        forces.y_kcal_per_mol_angstrom = force_y.data();
        forces.z_kcal_per_mol_angstrom = force_z.data();

        bg_particle_mesh_reciprocal_error_v1 error{};
        init_error(&error);
        error.code = BG_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_MESH;
        std::strcpy(error.detail, "stale");
        const auto energy_before = energy;
        const auto forces_before = forces;
        const auto force_x_before = force_x;
        const auto force_y_before = force_y;
        const auto force_z_before = force_z;

        assert(bg_context_evaluate_particle_mesh_reciprocal_v1(
                   context.value, system.value, model.value, &energy,
                   &forces, &error) == BG_STATUS_CAPACITY_OVERFLOW);
        assert(error.code ==
               BG_PARTICLE_MESH_RECIPROCAL_ERROR_CAPACITY_EXCEEDED);
        assert(std::strcmp(error.detail, "particle count exceeds 4096") ==
               0);
        assert(error.struct_size == sizeof(error));
        assert(error.abi_version ==
               BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION);
        assert(error.reserved0 == 0U);
        assert(std::all_of(
            std::begin(error.reserved), std::end(error.reserved),
            [](std::uint64_t value) { return value == 0U; }));
        assert(std::memcmp(&energy, &energy_before, sizeof(energy)) == 0);
        assert(std::memcmp(&forces, &forces_before, sizeof(forces)) == 0);
        assert(force_x == force_x_before);
        assert(force_y == force_y_before);
        assert(force_z == force_z_before);
    }
}

void verify_mandatory_null_clears_error() {
    Fixture fixture;
    const Context context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    const Model model = make_model(fixture_parameters());
    bg_particle_mesh_reciprocal_energy_v1 energy{};
    assert(bg_particle_mesh_reciprocal_energy_v1_init(
               &energy, sizeof(energy),
               BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION) == BG_STATUS_OK);
    bg_particle_mesh_reciprocal_error_v1 error{};
    init_error(&error);
    error.code = BG_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_MESH;
    std::strcpy(error.detail, "stale");
    assert(bg_context_evaluate_particle_mesh_reciprocal_v1(
               context.value, nullptr, model.value, &energy, nullptr,
               &error) == BG_STATUS_INVALID_ARGUMENT);
    assert(error.code == BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONE);
    assert(error.detail[0] == '\0');

    const System system = make_system(
        fixture.x, fixture.y, fixture.z, fixture.mass, fixture.charge);
    bg_particle_mesh_reciprocal_force_soa_v1 forces{};
    assert(bg_particle_mesh_reciprocal_force_soa_v1_init(
               &forces, sizeof(forces),
               BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION) == BG_STATUS_OK);
    std::array<double, 4> x{};
    std::array<double, 4> y{};
    std::array<double, 4> z{};
    forces.atom_capacity = 3U;
    forces.x_kcal_per_mol_angstrom = x.data();
    forces.y_kcal_per_mol_angstrom = y.data();
    forces.z_kcal_per_mol_angstrom = z.data();
    error.code = BG_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_MESH;
    std::strcpy(error.detail, "stale");
    const bg_status status =
        bg_context_evaluate_particle_mesh_reciprocal_v1(
            context.value, system.value, model.value, &energy, &forces,
            &error);
    assert(status == BG_STATUS_BUFFER_TOO_SMALL);
    assert(error.code == BG_PARTICLE_MESH_RECIPROCAL_ERROR_NONE);
    assert(error.detail[0] == '\0');
}

void verify_required_null_alias_suppresses_error_write() {
    Fixture fixture;
    const Context context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    const System system = make_system(
        fixture.x, fixture.y, fixture.z, fixture.mass, fixture.charge);
    bg_particle_mesh_reciprocal_energy_v1 energy{};
    assert(bg_particle_mesh_reciprocal_energy_v1_init(
               &energy, sizeof(energy),
               BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION) == BG_STATUS_OK);

    std::array<double, 4> output_x{};
    std::array<double, 4> output_y{};
    std::array<double, 4> output_z{};
    bg_particle_mesh_reciprocal_force_soa_v1 forces{};
    assert(bg_particle_mesh_reciprocal_force_soa_v1_init(
               &forces, sizeof(forces),
               BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION) == BG_STATUS_OK);
    forces.atom_capacity = 4U;
    forces.x_kcal_per_mol_angstrom = output_x.data();
    forces.y_kcal_per_mol_angstrom = output_y.data();
    forces.z_kcal_per_mol_angstrom = output_z.data();

    const std::vector<double> input_before = system.value->position_x;
    auto *input_alias_error =
        reinterpret_cast<bg_particle_mesh_reciprocal_error_v1 *>(
            system.value->position_x.data());
    assert(bg_context_evaluate_particle_mesh_reciprocal_v1(
               context.value, system.value, nullptr, &energy, &forces,
               input_alias_error) == BG_STATUS_INVALID_ARGUMENT);
    assert(system.value->position_x == input_before);

    bg_particle_mesh_reciprocal_error_v1 error{};
    init_error(&error);
    error.code = BG_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_MESH;
    std::strcpy(error.detail, "preserve force alias");
    std::array<unsigned char, sizeof(error)> error_before{};
    std::memcpy(error_before.data(), &error, sizeof(error));
    forces.x_kcal_per_mol_angstrom = reinterpret_cast<double *>(&error);
    assert(bg_context_evaluate_particle_mesh_reciprocal_v1(
               context.value, system.value, nullptr, &energy, &forces,
               &error) == BG_STATUS_INVALID_ARGUMENT);
    assert(std::memcmp(&error, error_before.data(), sizeof(error)) == 0);

    alignas(bg_particle_mesh_reciprocal_error_v1)
        std::array<unsigned char,
                   sizeof(bg_particle_mesh_reciprocal_error_v1)> shared{};
    const auto shared_before = shared;
    auto *shared_energy =
        reinterpret_cast<bg_particle_mesh_reciprocal_energy_v1 *>(
            shared.data());
    auto *shared_error =
        reinterpret_cast<bg_particle_mesh_reciprocal_error_v1 *>(
            shared.data());
    assert(bg_context_evaluate_particle_mesh_reciprocal_v1(
               context.value, system.value, nullptr, shared_energy,
               nullptr, shared_error) == BG_STATUS_INVALID_ARGUMENT);
    assert(shared == shared_before);
}

void assert_create_typed_failure(
    bg_particle_mesh_reciprocal_parameters_v1 parameters,
    bg_status expected_status,
    bg_particle_mesh_reciprocal_error_code expected_code) {
    bg_particle_mesh_reciprocal_error_v1 error{};
    init_error(&error);
    auto *sentinel = reinterpret_cast<bg_particle_mesh_reciprocal_model_v1 *>(
        static_cast<std::uintptr_t>(1U));
    assert(bg_particle_mesh_reciprocal_model_v1_create(
               &parameters, &sentinel, &error) == expected_status);
    assert(sentinel == nullptr);
    assert(error.code == expected_code);
    assert(error.detail[0] != '\0');
}

void verify_static_validation_and_work_cap() {
    auto parameters = fixture_parameters(4U);
    parameters.atom_count = 0U;
    assert_create_typed_failure(
        parameters, BG_STATUS_INVALID_ARGUMENT,
        BG_PARTICLE_MESH_RECIPROCAL_ERROR_EMPTY_SYSTEM);

    parameters = fixture_parameters(4U);
    parameters.atom_count = 4'097U;
    assert_create_typed_failure(
        parameters, BG_STATUS_CAPACITY_OVERFLOW,
        BG_PARTICLE_MESH_RECIPROCAL_ERROR_CAPACITY_EXCEEDED);

    parameters = fixture_parameters(4U);
    parameters.cell_lengths_angstrom[1] = 0.0;
    assert_create_typed_failure(
        parameters, BG_STATUS_INVALID_ARGUMENT,
        BG_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_CELL);

    parameters = fixture_parameters(4U);
    parameters.alpha_per_angstrom = 0.0;
    assert_create_typed_failure(
        parameters, BG_STATUS_INVALID_ARGUMENT,
        BG_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_PARAMETER);

    parameters = fixture_parameters(4U);
    parameters.mesh_dimensions[1] = 6U;
    assert_create_typed_failure(
        parameters, BG_STATUS_INVALID_ARGUMENT,
        BG_PARTICLE_MESH_RECIPROCAL_ERROR_INVALID_MESH);

    parameters = fixture_parameters(128U);
    assert_create_typed_failure(
        parameters, BG_STATUS_CAPACITY_OVERFLOW,
        BG_PARTICLE_MESH_RECIPROCAL_ERROR_CAPACITY_EXCEEDED);

    parameters = fixture_parameters(4U);
    parameters.mesh_dimensions[0] = 64U;
    parameters.mesh_dimensions[1] = 128U;
    parameters.mesh_dimensions[2] = 128U;
    assert_create_typed_failure(
        parameters, BG_STATUS_CAPACITY_OVERFLOW,
        BG_PARTICLE_MESH_RECIPROCAL_ERROR_CAPACITY_EXCEEDED);
}

void verify_alias_rejection() {
    Fixture fixture;
    const Context context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    const System system = make_system(
        fixture.x, fixture.y, fixture.z, fixture.mass, fixture.charge);
    const Model model = make_model(fixture_parameters());
    bg_particle_mesh_reciprocal_energy_v1 energy{};
    assert(bg_particle_mesh_reciprocal_energy_v1_init(
               &energy, sizeof(energy),
               BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION) == BG_STATUS_OK);
    bg_particle_mesh_reciprocal_error_v1 error{};
    init_error(&error);

    std::array<double, 4> output_x{};
    std::array<double, 4> output_y{};
    std::array<double, 4> output_z{};
    bg_particle_mesh_reciprocal_force_soa_v1 forces{};
    assert(bg_particle_mesh_reciprocal_force_soa_v1_init(
               &forces, sizeof(forces),
               BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION) == BG_STATUS_OK);
    forces.atom_capacity = 4U;
    forces.x_kcal_per_mol_angstrom = output_x.data();
    forces.y_kcal_per_mol_angstrom = output_y.data();
    forces.z_kcal_per_mol_angstrom = output_z.data();

    forces.x_kcal_per_mol_angstrom = system.value->position_x.data();
    assert(bg_context_evaluate_particle_mesh_reciprocal_v1(
               context.value, system.value, model.value, &energy, &forces,
               &error) == BG_STATUS_INVALID_ARGUMENT);
    forces.x_kcal_per_mol_angstrom = output_x.data();

    forces.y_kcal_per_mol_angstrom = output_x.data();
    assert(bg_context_evaluate_particle_mesh_reciprocal_v1(
               context.value, system.value, model.value, &energy, &forces,
               &error) == BG_STATUS_INVALID_ARGUMENT);
    forces.y_kcal_per_mol_angstrom = output_y.data();

    forces.x_kcal_per_mol_angstrom = reinterpret_cast<double *>(&forces);
    assert(bg_context_evaluate_particle_mesh_reciprocal_v1(
               context.value, system.value, model.value, &energy, &forces,
               &error) == BG_STATUS_INVALID_ARGUMENT);
    forces.x_kcal_per_mol_angstrom = output_x.data();

    auto *aliased_error =
        reinterpret_cast<bg_particle_mesh_reciprocal_error_v1 *>(
            system.value->position_x.data());
    assert(bg_context_evaluate_particle_mesh_reciprocal_v1(
               context.value, system.value, model.value, &energy, &forces,
               aliased_error) == BG_STATUS_INVALID_ARGUMENT);

    alignas(bg_particle_mesh_reciprocal_error_v1)
        std::array<unsigned char, 304> shared{};
    auto *shared_energy =
        reinterpret_cast<bg_particle_mesh_reciprocal_energy_v1 *>(
            shared.data());
    auto *shared_error =
        reinterpret_cast<bg_particle_mesh_reciprocal_error_v1 *>(
            shared.data());
    assert(bg_context_evaluate_particle_mesh_reciprocal_v1(
               context.value, system.value, model.value, shared_energy,
               nullptr, shared_error) == BG_STATUS_INVALID_ARGUMENT);

    bg_particle_mesh_reciprocal_parameters_v1 parameters =
        fixture_parameters();
    init_error(&error);
    std::array<unsigned char, sizeof(parameters)> alias_parameters_before{};
    std::array<unsigned char, sizeof(error)> alias_error_before{};
    std::memcpy(
        alias_parameters_before.data(), &parameters, sizeof(parameters));
    std::memcpy(alias_error_before.data(), &error, sizeof(error));
    auto **aliased_model_output =
        reinterpret_cast<bg_particle_mesh_reciprocal_model_v1 **>(
            &parameters);
    assert(bg_particle_mesh_reciprocal_model_v1_create(
               &parameters, aliased_model_output, &error) ==
           BG_STATUS_INVALID_ARGUMENT);
    assert(std::memcmp(
               &parameters, alias_parameters_before.data(),
               sizeof(parameters)) == 0);
    assert(std::memcmp(
               &error, alias_error_before.data(), sizeof(error)) == 0);
}

void verify_hip_fails_closed_without_device_execution() {
    {
        const Context context = make_context(BG_BACKEND_AUTO);
        const auto *bad_system = reinterpret_cast<const bg_system *>(
            static_cast<std::uintptr_t>(1U));
        const auto *bad_model =
            reinterpret_cast<const bg_particle_mesh_reciprocal_model_v1 *>(
                static_cast<std::uintptr_t>(1U));
        auto *bad_energy =
            reinterpret_cast<bg_particle_mesh_reciprocal_energy_v1 *>(
                static_cast<std::uintptr_t>(1U));
        auto *bad_error =
            reinterpret_cast<bg_particle_mesh_reciprocal_error_v1 *>(
                static_cast<std::uintptr_t>(1U));
        assert(bg_context_evaluate_particle_mesh_reciprocal_v1(
                   context.value, bad_system, bad_model, bad_energy, nullptr,
                   bad_error) == BG_STATUS_UNSUPPORTED_BACKEND);
    }
    for (const bg_backend backend :
         {BG_BACKEND_HIP_FAST, BG_BACKEND_HIP_SAFE}) {
        bg_context fake{};
        fake.requested_backend = backend;
        fake.backend = backend;
        const auto *bad_system = reinterpret_cast<const bg_system *>(
            static_cast<std::uintptr_t>(1U));
        const auto *bad_model =
            reinterpret_cast<const bg_particle_mesh_reciprocal_model_v1 *>(
                static_cast<std::uintptr_t>(1U));
        auto *bad_energy =
            reinterpret_cast<bg_particle_mesh_reciprocal_energy_v1 *>(
                static_cast<std::uintptr_t>(1U));
        auto *bad_error =
            reinterpret_cast<bg_particle_mesh_reciprocal_error_v1 *>(
                static_cast<std::uintptr_t>(1U));
        assert(bg_context_evaluate_particle_mesh_reciprocal_v1(
                   &fake, bad_system, bad_model, bad_energy, nullptr,
                   bad_error) == BG_STATUS_UNSUPPORTED_BACKEND);
    }
}

Result evaluate_fixture_variant(
    bg_backend backend,
    const std::array<double, 4> &x,
    const std::array<double, 4> &y,
    const std::array<double, 4> &z,
    const std::array<double, 4> &charge,
    std::uint32_t mesh) {
    const std::array<double, 4> mass{{1.0, 1.0, 1.0, 1.0}};
    const Context context = make_context(backend);
    const System system = make_system(x, y, z, mass, charge);
    const Model model = make_model(fixture_parameters(mesh));
    return evaluate(context.value, system.value, model.value, x.size());
}

void verify_periodicity_permutation_and_charge_inversion() {
    Fixture fixture;
    for (const bg_backend backend :
         {BG_BACKEND_CPP_CPU_REFERENCE, BG_BACKEND_RUST_CPU}) {
        const Result baseline = evaluate_fixture_variant(
            backend, fixture.x, fixture.y, fixture.z, fixture.charge);
        auto imaged_x = fixture.x;
        auto imaged_y = fixture.y;
        auto imaged_z = fixture.z;
        imaged_x[0] += 36.0;
        imaged_y[1] -= 60.0;
        imaged_z[2] += 22.0;
        const Result imaged = evaluate_fixture_variant(
            backend, imaged_x, imaged_y, imaged_z, fixture.charge);
        assert(close(
            imaged.energy.reciprocal_space_kcal_per_mol,
            baseline.energy.reciprocal_space_kcal_per_mol, 8.0e-12));

        const std::array<std::size_t, 4> order{{3U, 1U, 0U, 2U}};
        std::array<double, 4> permuted_x{};
        std::array<double, 4> permuted_y{};
        std::array<double, 4> permuted_z{};
        std::array<double, 4> permuted_charge{};
        for (std::size_t atom = 0U; atom < order.size(); ++atom) {
            permuted_x[atom] = fixture.x[order[atom]];
            permuted_y[atom] = fixture.y[order[atom]];
            permuted_z[atom] = fixture.z[order[atom]];
            permuted_charge[atom] = fixture.charge[order[atom]];
        }
        const Result permuted = evaluate_fixture_variant(
            backend, permuted_x, permuted_y, permuted_z,
            permuted_charge);
        assert(close(
            permuted.energy.reciprocal_space_kcal_per_mol,
            baseline.energy.reciprocal_space_kcal_per_mol, 3.0e-12));
        for (std::size_t atom = 0U; atom < order.size(); ++atom) {
            assert(close(
                permuted.force_x[atom], baseline.force_x[order[atom]],
                5.0e-12));
            assert(close(
                permuted.force_y[atom], baseline.force_y[order[atom]],
                5.0e-12));
            assert(close(
                permuted.force_z[atom], baseline.force_z[order[atom]],
                5.0e-12));
        }

        auto inverted_charge = fixture.charge;
        for (double &charge : inverted_charge) {
            charge = -charge;
        }
        const Result inverted = evaluate_fixture_variant(
            backend, fixture.x, fixture.y, fixture.z, inverted_charge);
        assert(close(
            inverted.energy.reciprocal_space_kcal_per_mol,
            baseline.energy.reciprocal_space_kcal_per_mol, 1.0e-15));
        for (std::size_t atom = 0U; atom < order.size(); ++atom) {
            assert(close(
                inverted.force_x[atom], baseline.force_x[atom], 1.0e-15));
            assert(close(
                inverted.force_y[atom], baseline.force_y[atom], 1.0e-15));
            assert(close(
                inverted.force_z[atom], baseline.force_z[atom], 1.0e-15));
        }
    }
}

void verify_analytic_force_finite_differences() {
    Fixture fixture;
    constexpr double step = 1.0e-5;
    for (const bg_backend backend :
         {BG_BACKEND_CPP_CPU_REFERENCE, BG_BACKEND_RUST_CPU}) {
        const Result baseline = evaluate_fixture_variant(
            backend, fixture.x, fixture.y, fixture.z, fixture.charge);
        for (std::size_t atom = 0U; atom < fixture.x.size(); ++atom) {
            for (std::size_t axis = 0U; axis < 3U; ++axis) {
                auto minus_x = fixture.x;
                auto minus_y = fixture.y;
                auto minus_z = fixture.z;
                auto plus_x = fixture.x;
                auto plus_y = fixture.y;
                auto plus_z = fixture.z;
                std::array<std::array<double, 4> *, 3> minus{
                    &minus_x, &minus_y, &minus_z};
                std::array<std::array<double, 4> *, 3> plus{
                    &plus_x, &plus_y, &plus_z};
                (*minus[axis])[atom] -= step;
                (*plus[axis])[atom] += step;
                const Result minus_result = evaluate_fixture_variant(
                    backend, minus_x, minus_y, minus_z, fixture.charge);
                const Result plus_result = evaluate_fixture_variant(
                    backend, plus_x, plus_y, plus_z, fixture.charge);
                const double finite_difference =
                    -(plus_result.energy.reciprocal_space_kcal_per_mol -
                      minus_result.energy.reciprocal_space_kcal_per_mol) /
                    (2.0 * step);
                const std::array<const std::vector<double> *, 3> forces{
                    &baseline.force_x, &baseline.force_y, &baseline.force_z};
                assert(close(
                    (*forces[axis])[atom], finite_difference, 2.0e-7));
            }
        }
    }
}

double direct_reciprocal_energy(
    const bg_context *context,
    const bg_system *system,
    const bg_direct_ewald_model_v1 *model) {
    bg_direct_ewald_energy_components_v1 energy{};
    assert(bg_direct_ewald_energy_components_v1_init(
               &energy, sizeof(energy), BG_DIRECT_EWALD_ABI_VERSION) ==
           BG_STATUS_OK);
    bg_direct_ewald_error_v1 error{};
    assert(bg_direct_ewald_error_v1_init(
               &error, sizeof(error), BG_DIRECT_EWALD_ABI_VERSION) ==
           BG_STATUS_OK);
    assert(bg_context_evaluate_direct_ewald_v1(
               context, system, model, &energy, nullptr, &error) ==
           BG_STATUS_OK);
    return energy.reciprocal_space_kcal_per_mol;
}

void verify_mesh_refinement_observation() {
    Fixture fixture;
    const Context context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    const System system = make_system(
        fixture.x, fixture.y, fixture.z, fixture.mass, fixture.charge);
    bg_direct_ewald_parameters_v1 direct_parameters{};
    assert(bg_direct_ewald_parameters_v1_init(
               &direct_parameters, sizeof(direct_parameters),
               BG_DIRECT_EWALD_ABI_VERSION) == BG_STATUS_OK);
    direct_parameters.atom_count = 4U;
    direct_parameters.cell_lengths_angstrom[0] = 18.0;
    direct_parameters.cell_lengths_angstrom[1] = 20.0;
    direct_parameters.cell_lengths_angstrom[2] = 22.0;
    direct_parameters.alpha_per_angstrom = 0.31;
    direct_parameters.real_space_cutoff_angstrom = 1.0e-7;
    direct_parameters.reciprocal_max_indices[0] = 9;
    direct_parameters.reciprocal_max_indices[1] = 9;
    direct_parameters.reciprocal_max_indices[2] = 9;
    direct_parameters.dielectric = 1.0;
    direct_parameters.minimum_pair_distance_angstrom = 1.0e-8;
    bg_direct_ewald_error_v1 error{};
    assert(bg_direct_ewald_error_v1_init(
               &error, sizeof(error), BG_DIRECT_EWALD_ABI_VERSION) ==
           BG_STATUS_OK);
    DirectModel direct_model;
    assert(bg_direct_ewald_model_v1_create(
               &direct_parameters, &direct_model.value, &error) ==
           BG_STATUS_OK);
    const double direct = direct_reciprocal_energy(
        context.value, system.value, direct_model.value);
    std::array<double, 3> errors{};
    const std::array<std::uint32_t, 3> meshes{{8U, 16U, 32U}};
    for (std::size_t index = 0U; index < meshes.size(); ++index) {
        const Model model = make_model(fixture_parameters(meshes[index]));
        const Result result = evaluate(
            context.value, system.value, model.value, fixture.x.size(),
            false);
        errors[index] = std::abs(
            result.energy.reciprocal_space_kcal_per_mol - direct);
    }
    assert(errors[1] < errors[0]);
    assert(errors[2] < errors[1]);
    assert(errors[2] < 2.0e-3);
}

template <std::size_t Size>
Result evaluate_custom(
    bg_backend backend,
    const std::array<double, Size> &x,
    const std::array<double, Size> &y,
    const std::array<double, Size> &z,
    const std::array<double, Size> &charge,
    const std::array<double, 3> &cell,
    double alpha,
    double dielectric) {
    std::array<double, Size> mass{};
    mass.fill(1.0);
    const Context context = make_context(backend);
    const System system = make_system(x, y, z, mass, charge);
    bg_particle_mesh_reciprocal_parameters_v1 parameters{};
    assert(bg_particle_mesh_reciprocal_parameters_v1_init(
               &parameters, sizeof(parameters),
               BG_PARTICLE_MESH_RECIPROCAL_ABI_VERSION) == BG_STATUS_OK);
    parameters.atom_count = Size;
    std::copy(cell.begin(), cell.end(), parameters.cell_lengths_angstrom);
    parameters.alpha_per_angstrom = alpha;
    parameters.mesh_dimensions[0] = 4U;
    parameters.mesh_dimensions[1] = 4U;
    parameters.mesh_dimensions[2] = 4U;
    parameters.dielectric = dielectric;
    const Model model = make_model(parameters);
    return evaluate(context.value, system.value, model.value, Size);
}

void verify_underflow_rescue_and_numeric_parity() {
    for (const bg_backend backend :
         {BG_BACKEND_CPP_CPU_REFERENCE, BG_BACKEND_RUST_CPU}) {
        const std::array<double, 2> zero{{0.0, 0.0}};
        const Result no_charge = evaluate_custom(
            backend, std::array<double, 2>{{1.0, 4.0}},
            std::array<double, 2>{{2.0, 5.0}},
            std::array<double, 2>{{3.0, 6.0}}, zero,
            std::array<double, 3>{{10.0, 12.0, 14.0}}, 0.3, 1.0);
        assert(to_bits(no_charge.energy.reciprocal_space_kcal_per_mol) == 0U);
        for (std::size_t atom = 0U; atom < 2U; ++atom) {
            assert(no_charge.force_x[atom] == 0.0);
            assert(no_charge.force_y[atom] == 0.0);
            assert(no_charge.force_z[atom] == 0.0);
        }

        const std::array<double, 2> x{{0.0, 4.0e8}};
        const std::array<double, 2> y{{0.0, 0.0}};
        const std::array<double, 2> z{{0.0, 0.0}};
        const std::array<double, 2> charge{{16.0, -16.0}};
        const Result rescued = evaluate_custom(
            backend, x, y, z, charge,
            std::array<double, 3>{{1.0e9, 1.0e-6, 1.0e-6}},
            1.15e-10, 1.0e-12);
        assert(std::isnormal(
            rescued.energy.reciprocal_space_kcal_per_mol));
        assert(rescued.energy.reciprocal_space_kcal_per_mol > 0.0);
        assert(std::isnormal(rescued.force_x[1]));
        assert(rescued.force_x[1] < 0.0);
        assert(relative_close(
            rescued.energy.reciprocal_space_kcal_per_mol,
            7.4746417761e-287, 2.0e-7));
        assert(relative_close(
            rescued.force_x[1], -1.6999574664e-295, 2.0e-7));

        const std::array<double, 2> tiny_x{{0.0, 4.0e-7}};
        const Result force_only = evaluate_custom(
            backend, tiny_x, y, z, charge,
            std::array<double, 3>{{1.0e-6, 1.0e-6, 1.0e-6}},
            1.15e5, 1.0e12);
        assert(to_bits(force_only.energy.reciprocal_space_kcal_per_mol) ==
               0U);
        assert(std::fpclassify(force_only.force_x[1]) == FP_SUBNORMAL);
        assert(force_only.force_x[1] < 0.0);

        const Result bit_one = evaluate_custom(
            backend, tiny_x, y, z, charge,
            std::array<double, 3>{{1.0e-6, 1.0e-6, 1.0e-6}},
            1.15e5, 2.5e10);
        if (backend == BG_BACKEND_RUST_CPU) {
            assert(to_bits(bit_one.energy.reciprocal_space_kcal_per_mol) ==
                   1U);
        } else {
            assert(bit_one.energy.reciprocal_space_kcal_per_mol > 0.0);
            assert(std::fpclassify(
                       bit_one.energy.reciprocal_space_kcal_per_mol) ==
                   FP_SUBNORMAL);
        }
    }
}

void verify_frozen_fixture_and_lane_repeatability() {
    verify_frozen_fixture_and_deep_ownership();
}

void verify_transactional_failures_and_typed_precedence() {
    verify_evaluation_transactionality_and_typed_errors();
    verify_oversized_system_capacity_precedence();
    verify_mandatory_null_clears_error();
    verify_required_null_alias_suppresses_error_write();
}

void verify_alias_rejection_and_fail_closed_backends() {
    verify_alias_rejection();
    verify_hip_fails_closed_without_device_execution();
}

void verify_zero_charge_and_underflow_rescue() {
    verify_underflow_rescue_and_numeric_parity();
}

}  // namespace

int main() {
    verify_abi_layout_and_initializers();
    verify_frozen_fixture_and_lane_repeatability();
    verify_rust_cpp_cpu_parity();
    verify_transactional_failures_and_typed_precedence();
    verify_static_validation_and_work_cap();
    verify_alias_rejection_and_fail_closed_backends();
    verify_periodicity_permutation_and_charge_inversion();
    verify_analytic_force_finite_differences();
    verify_mesh_refinement_observation();
    verify_zero_charge_and_underflow_rescue();
    return 0;
}
