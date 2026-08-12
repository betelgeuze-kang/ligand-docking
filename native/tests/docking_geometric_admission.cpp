#include "betelgeuze/engine.h"

#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <vector>

namespace {

constexpr std::size_t kSlots = BG_DOCKING_FIXED64_CANDIDATE_COUNT;
constexpr std::size_t kLigandAtoms = 1;

struct Fixture final {
    std::array<double, 1> receptor_x = {0.0};
    std::array<double, 1> receptor_y = {0.0};
    std::array<double, 1> receptor_z = {0.0};
    std::array<double, 1> receptor_radius = {1.0};
    std::array<double, 1> ligand_radius = {1.0};
    std::array<uint8_t, 1> ligand_heavy = {UINT8_C(1)};
    std::array<bg_docking_geometric_admission_candidate_state, kSlots>
        states{};
    std::array<double, kSlots * kLigandAtoms> x{};
    std::array<double, kSlots * kLigandAtoms> y{};
    std::array<double, kSlots * kLigandAtoms> z{};

    Fixture() {
        states.fill(
            BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_UPSTREAM_FAILURE);
        x.fill(5.0);
        y.fill(0.0);
        z.fill(0.0);
        states[0] = BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_EVALUATE;
        x[0] = 1.1;  // exact minimum_vdw_ratio == 0.55: admitted
        states[1] = BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_EVALUATE;
        x[1] = 1.0;  // severe penetration
        states[2] = BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_EVALUATE;
        x[2] = 4.0;  // no penetration
        states[3] = BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_EVALUATE;
        x[3] = std::numeric_limits<double>::quiet_NaN();
    }

    bg_docking_geometric_admission_context_soa_v1 descriptor() const {
        bg_docking_geometric_admission_context_soa_v1 value{};
        assert(
            bg_docking_geometric_admission_context_soa_v1_init(&value) ==
            BG_STATUS_OK);
        value.receptor_atom_count = receptor_x.size();
        value.ligand_atom_count = ligand_radius.size();
        value.receptor_x_angstrom = receptor_x.data();
        value.receptor_y_angstrom = receptor_y.data();
        value.receptor_z_angstrom = receptor_z.data();
        value.receptor_vdw_radius_angstrom = receptor_radius.data();
        value.ligand_vdw_radius_angstrom = ligand_radius.data();
        value.ligand_heavy_atom_mask = ligand_heavy.data();
        value.pocket_center_angstrom[0] = 0.0;
        value.pocket_center_angstrom[1] = 0.0;
        value.pocket_center_angstrom[2] = 0.0;
        value.pocket_radius_angstrom = 10.0;
        std::fill(
            std::begin(value.authority_input_receipt_sha256),
            std::end(value.authority_input_receipt_sha256),
            UINT8_C(0x11));
        std::fill(
            std::begin(value.receptor_system_sha256),
            std::end(value.receptor_system_sha256),
            UINT8_C(0x22));
        std::fill(
            std::begin(value.ligand_system_sha256),
            std::end(value.ligand_system_sha256),
            UINT8_C(0x33));
        std::fill(
            std::begin(value.backend_receipt_sha256),
            std::end(value.backend_receipt_sha256),
            UINT8_C(0x44));
        return value;
    }

    bg_docking_geometric_admission_candidate_batch_soa_v1 batch() const {
        bg_docking_geometric_admission_candidate_batch_soa_v1 value{};
        assert(
            bg_docking_geometric_admission_candidate_batch_soa_v1_init(
                &value) == BG_STATUS_OK);
        value.ligand_atom_count = kLigandAtoms;
        value.candidate_state = states.data();
        value.x_angstrom = x.data();
        value.y_angstrom = y.data();
        value.z_angstrom = z.data();
        return value;
    }
};

bg_context *create_context(bg_backend backend) {
    bg_context_options options{};
    assert(bg_context_options_init(&options) == BG_STATUS_OK);
    options.backend = backend;
    options.device_ordinal = 0;
    bg_context *context = nullptr;
    assert(bg_context_create(&options, &context) == BG_STATUS_OK);
    assert(context != nullptr);
    return context;
}

bg_docking_geometric_admission_v1 *create_admission(
    bg_context *context,
    const bg_docking_geometric_admission_context_soa_v1 &descriptor) {
    bg_docking_geometric_admission_v1 *admission = nullptr;
    assert(
        bg_docking_geometric_admission_v1_create(
            context, &descriptor, &admission) == BG_STATUS_OK);
    assert(admission != nullptr);
    return admission;
}

struct Evaluation final {
    std::array<bg_docking_geometric_admission_row_v1, kSlots> rows{};
    bg_docking_geometric_admission_output_v1 output{};
};

Evaluation evaluate(
    bg_context *context,
    bg_docking_geometric_admission_v1 *admission,
    const bg_docking_geometric_admission_candidate_batch_soa_v1 &batch) {
    Evaluation value{};
    assert(
        bg_docking_geometric_admission_output_v1_init(&value.output) ==
        BG_STATUS_OK);
    value.output.row_capacity = value.rows.size();
    value.output.rows = value.rows.data();
    assert(
        bg_docking_geometric_admission_v1_evaluate_fixed64(
            context, admission, &batch, &value.output) == BG_STATUS_OK);
    assert(value.output.row_count == value.rows.size());
    assert(value.output.molecular_execution_authorized == 0);
    assert(value.output.reservation_authorized == 0);
    assert(value.output.benchmark_execution_authorized == 0);
    assert(value.output.existing_rank_auto_change_authorized == 0);
    assert(value.output.customer_pose_emission_authorized == 0);
    assert(value.output.production_claim_authorized == 0);
    assert(value.output.scientific_claim_authorized == 0);
    return value;
}

bool close_with_tolerance(double left, double right, double tolerance) {
    const double scale = std::max({1.0, std::abs(left), std::abs(right)});
    return std::abs(left - right) <= tolerance * scale;
}

void assert_row_parity(
    const bg_docking_geometric_admission_row_v1 &observed,
    const bg_docking_geometric_admission_row_v1 &reference,
    double tolerance) {
    assert(observed.slot_index == reference.slot_index);
    assert(observed.status == reference.status);
    assert(observed.failure_code == reference.failure_code);
    assert(observed.decision == reference.decision);
    assert(observed.rank_eligible == reference.rank_eligible);
    assert(observed.ligand_atom_count == reference.ligand_atom_count);
    assert(observed.receptor_atom_count == reference.receptor_atom_count);
    assert(observed.exact_pair_count == reference.exact_pair_count);
    assert(observed.penetration_pair_count == reference.penetration_pair_count);
    assert(
        observed.unique_ligand_penetration_atom_count ==
        reference.unique_ligand_penetration_atom_count);
    assert(
        observed.unique_ligand_heavy_atom_penetration_count ==
        reference.unique_ligand_heavy_atom_penetration_count);
    assert(close_with_tolerance(
        observed.raw_minimum_distance_angstrom,
        reference.raw_minimum_distance_angstrom,
        tolerance));
    assert(close_with_tolerance(
        observed.minimum_vdw_surface_gap_angstrom,
        reference.minimum_vdw_surface_gap_angstrom,
        tolerance));
    assert(close_with_tolerance(
        observed.minimum_vdw_ratio,
        reference.minimum_vdw_ratio,
        tolerance));
    assert(close_with_tolerance(
        observed.sphere_overlap_proxy_angstrom3,
        reference.sphere_overlap_proxy_angstrom3,
        tolerance));
    assert(close_with_tolerance(
        observed.pocket_escape_angstrom,
        reference.pocket_escape_angstrom,
        tolerance));
}

void assert_expected_rows(
    const std::array<bg_docking_geometric_admission_row_v1, kSlots> &rows) {
    assert(rows[0].status == BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED);
    assert(rows[0].decision == BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED);
    assert(rows[0].rank_eligible == 1);
    assert(rows[0].minimum_vdw_ratio == 0.55);
    assert(rows[0].exact_pair_count == 1);
    assert(rows[0].penetration_pair_count == 1);
    assert(rows[0].unique_ligand_penetration_atom_count == 1);
    assert(rows[0].unique_ligand_heavy_atom_penetration_count == 1);

    assert(rows[1].status == BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED);
    assert(
        rows[1].decision ==
        BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_SEVERE_PENETRATION_REJECTED);
    assert(rows[1].rank_eligible == 0);
    assert(rows[2].decision == BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED);
    assert(rows[2].penetration_pair_count == 0);
    assert(rows[3].status == BG_DOCKING_GEOMETRIC_ADMISSION_ROW_TYPED_FAILURE);
    assert(
        rows[3].failure_code ==
        BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_INVALID_CANDIDATE_COORDINATES);
    for (std::size_t slot = 4; slot < kSlots; ++slot) {
        assert(
            rows[slot].status ==
            BG_DOCKING_GEOMETRIC_ADMISSION_ROW_UPSTREAM_FAILURE);
        assert(
            rows[slot].failure_code ==
            BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_UPSTREAM_NOT_AVAILABLE);
    }
}

void test_cpu_parity_deep_copy_and_threshold_boundary() {
    Fixture fixture;
    const auto descriptor = fixture.descriptor();
    const auto batch = fixture.batch();
    bg_context *cpp_context = create_context(BG_BACKEND_CPP_CPU_REFERENCE);
    bg_context *rust_context = create_context(BG_BACKEND_RUST_CPU);
    auto *cpp_admission = create_admission(cpp_context, descriptor);
    auto *rust_admission = create_admission(rust_context, descriptor);
    const Evaluation cpp = evaluate(cpp_context, cpp_admission, batch);
    const Evaluation rust = evaluate(rust_context, rust_admission, batch);
    const Evaluation rust_repeat = evaluate(rust_context, rust_admission, batch);
    assert(
        std::memcmp(
            rust.rows.data(), rust_repeat.rows.data(), sizeof(rust.rows)) == 0);
    for (std::size_t slot = 0; slot < kSlots; ++slot) {
        assert_row_parity(rust.rows[slot], cpp.rows[slot], 2.0e-12);
    }
    assert_expected_rows(cpp.rows);

    fixture.receptor_x[0] = 999.0;
    fixture.receptor_radius[0] = 9.0;
    fixture.ligand_radius[0] = 9.0;
    fixture.ligand_heavy[0] = 0;
    const Evaluation cpp_after_mutation =
        evaluate(cpp_context, cpp_admission, batch);
    const Evaluation rust_after_mutation =
        evaluate(rust_context, rust_admission, batch);
    assert(
        std::memcmp(
            cpp.rows.data(),
            cpp_after_mutation.rows.data(),
            sizeof(cpp.rows)) == 0);
    assert(
        std::memcmp(
            rust.rows.data(),
            rust_after_mutation.rows.data(),
            sizeof(rust.rows)) == 0);

    bg_docking_geometric_admission_v1_destroy(cpp_admission);
    bg_docking_geometric_admission_v1_destroy(rust_admission);
    bg_context_destroy(cpp_context);
    bg_context_destroy(rust_context);
}

void test_invalid_output_and_aliasing_are_transactional() {
    Fixture fixture;
    const auto descriptor = fixture.descriptor();
    auto batch = fixture.batch();
    bg_context *context = create_context(BG_BACKEND_RUST_CPU);
    auto *admission = create_admission(context, descriptor);

    std::array<bg_docking_geometric_admission_row_v1, kSlots> rows{};
    std::memset(rows.data(), 0xA5, sizeof(rows));
    const auto before = rows;
    bg_docking_geometric_admission_output_v1 output{};
    assert(bg_docking_geometric_admission_output_v1_init(&output) == BG_STATUS_OK);
    output.row_capacity = rows.size();
    output.row_count = 17;
    output.rows = rows.data();
    output.production_claim_authorized = 1;
    assert(
        bg_docking_geometric_admission_v1_evaluate_fixed64(
            context, admission, &batch, &output) ==
        BG_STATUS_INVALID_ARGUMENT);
    assert(output.row_count == 17);
    assert(std::memcmp(rows.data(), before.data(), sizeof(rows)) == 0);

    alignas(bg_docking_geometric_admission_row_v1)
        std::array<std::byte, sizeof(rows)> shared{};
    auto *const shared_x = reinterpret_cast<double *>(shared.data());
    for (std::size_t index = 0; index < kSlots * kLigandAtoms; ++index) {
        shared_x[index] = fixture.x[index];
    }
    const auto shared_before = shared;
    batch.x_angstrom = shared_x;
    assert(bg_docking_geometric_admission_output_v1_init(&output) == BG_STATUS_OK);
    output.row_capacity = kSlots;
    output.row_count = 9;
    output.rows = reinterpret_cast<bg_docking_geometric_admission_row_v1 *>(
        shared.data());
    assert(
        bg_docking_geometric_admission_v1_evaluate_fixed64(
            context, admission, &batch, &output) ==
        BG_STATUS_INVALID_ARGUMENT);
    assert(output.row_count == 9);
    assert(shared == shared_before);

    bg_docking_geometric_admission_v1_destroy(admission);
    bg_context_destroy(context);
}

void test_create_and_handle_aliasing_preserve_inputs() {
    Fixture fixture;
    auto descriptor = fixture.descriptor();
    bg_context *context = create_context(BG_BACKEND_RUST_CPU);

    const auto receptor_x_before = fixture.receptor_x;
    auto **const channel_alias =
        reinterpret_cast<bg_docking_geometric_admission_v1 **>(
            fixture.receptor_x.data());
    assert(
        bg_docking_geometric_admission_v1_create(
            context, &descriptor, channel_alias) ==
        BG_STATUS_INVALID_ARGUMENT);
    assert(fixture.receptor_x == receptor_x_before);

    const auto descriptor_before = descriptor;
    auto **const descriptor_alias =
        reinterpret_cast<bg_docking_geometric_admission_v1 **>(
            &descriptor);
    assert(
        bg_docking_geometric_admission_v1_create(
            context, &descriptor, descriptor_alias) ==
        BG_STATUS_INVALID_ARGUMENT);
    assert(
        std::memcmp(
            &descriptor,
            &descriptor_before,
            sizeof(descriptor)) == 0);

    alignas(bg_docking_geometric_admission_v1 *)
        std::array<std::byte,
                   sizeof(bg_docking_geometric_admission_v1 *) + 1>
            misaligned_storage{};
    auto **const misaligned =
        reinterpret_cast<bg_docking_geometric_admission_v1 **>(
            misaligned_storage.data() + 1);
    assert(
        bg_docking_geometric_admission_v1_create(
            context, &descriptor, misaligned) ==
        BG_STATUS_INVALID_ARGUMENT);

    auto *admission = create_admission(context, descriptor);
    assert(
        bg_docking_geometric_admission_v1_get_backend(
            admission, reinterpret_cast<bg_backend *>(admission)) ==
        BG_STATUS_INVALID_ARGUMENT);
    bg_backend observed = BG_BACKEND_AUTO;
    assert(
        bg_docking_geometric_admission_v1_get_backend(
            admission, &observed) == BG_STATUS_OK);
    assert(observed == BG_BACKEND_RUST_CPU);

    const auto batch = fixture.batch();
    bg_docking_geometric_admission_output_v1 output{};
    assert(
        bg_docking_geometric_admission_output_v1_init(&output) ==
        BG_STATUS_OK);
    output.row_capacity = kSlots;
    output.row_count = 23;
    output.rows =
        reinterpret_cast<bg_docking_geometric_admission_row_v1 *>(
            admission);
    assert(
        bg_docking_geometric_admission_v1_evaluate_fixed64(
            context, admission, &batch, &output) ==
        BG_STATUS_INVALID_ARGUMENT);
    assert(output.row_count == 23);
    assert(
        bg_docking_geometric_admission_v1_get_backend(
            admission, &observed) == BG_STATUS_OK);

    output.rows =
        reinterpret_cast<bg_docking_geometric_admission_row_v1 *>(context);
    assert(
        bg_docking_geometric_admission_v1_evaluate_fixed64(
            context, admission, &batch, &output) ==
        BG_STATUS_INVALID_ARGUMENT);
    bg_backend context_backend = BG_BACKEND_AUTO;
    assert(
        bg_context_get_backend(context, &context_backend) == BG_STATUS_OK);
    assert(context_backend == BG_BACKEND_RUST_CPU);

    bg_docking_geometric_admission_v1_destroy(admission);
    bg_context_destroy(context);
}

void test_pair_budget_is_fail_closed_for_both_cpu_backends() {
    constexpr std::size_t kLargeLigand = 512;
    constexpr std::size_t kLargeReceptor = 513;
    std::vector<double> receptor_x(kLargeReceptor, 20.0);
    std::vector<double> receptor_y(kLargeReceptor, 0.0);
    std::vector<double> receptor_z(kLargeReceptor, 0.0);
    std::vector<double> receptor_radius(kLargeReceptor, 1.0);
    std::vector<double> ligand_radius(kLargeLigand, 1.0);
    std::vector<uint8_t> ligand_heavy(kLargeLigand, UINT8_C(1));
    std::array<bg_docking_geometric_admission_candidate_state, kSlots> states{};
    states.fill(BG_DOCKING_GEOMETRIC_ADMISSION_CANDIDATE_EVALUATE);
    std::vector<double> x(kSlots * kLargeLigand, 0.0);
    std::vector<double> y(kSlots * kLargeLigand, 0.0);
    std::vector<double> z(kSlots * kLargeLigand, 0.0);

    bg_docking_geometric_admission_context_soa_v1 descriptor{};
    assert(
        bg_docking_geometric_admission_context_soa_v1_init(&descriptor) ==
        BG_STATUS_OK);
    descriptor.receptor_atom_count = kLargeReceptor;
    descriptor.ligand_atom_count = kLargeLigand;
    descriptor.receptor_x_angstrom = receptor_x.data();
    descriptor.receptor_y_angstrom = receptor_y.data();
    descriptor.receptor_z_angstrom = receptor_z.data();
    descriptor.receptor_vdw_radius_angstrom = receptor_radius.data();
    descriptor.ligand_vdw_radius_angstrom = ligand_radius.data();
    descriptor.ligand_heavy_atom_mask = ligand_heavy.data();
    descriptor.pocket_radius_angstrom = 100.0;
    std::fill(
        std::begin(descriptor.authority_input_receipt_sha256),
        std::end(descriptor.authority_input_receipt_sha256),
        UINT8_C(1));
    std::fill(
        std::begin(descriptor.receptor_system_sha256),
        std::end(descriptor.receptor_system_sha256),
        UINT8_C(2));
    std::fill(
        std::begin(descriptor.ligand_system_sha256),
        std::end(descriptor.ligand_system_sha256),
        UINT8_C(3));
    std::fill(
        std::begin(descriptor.backend_receipt_sha256),
        std::end(descriptor.backend_receipt_sha256),
        UINT8_C(4));
    bg_docking_geometric_admission_candidate_batch_soa_v1 batch{};
    assert(
        bg_docking_geometric_admission_candidate_batch_soa_v1_init(&batch) ==
        BG_STATUS_OK);
    batch.ligand_atom_count = kLargeLigand;
    batch.candidate_state = states.data();
    batch.x_angstrom = x.data();
    batch.y_angstrom = y.data();
    batch.z_angstrom = z.data();
    std::array<bg_docking_geometric_admission_row_v1, kSlots> rows{};
    bg_docking_geometric_admission_output_v1 output{};
    assert(bg_docking_geometric_admission_output_v1_init(&output) == BG_STATUS_OK);
    output.row_capacity = rows.size();
    output.rows = rows.data();
    for (const bg_backend backend :
         {BG_BACKEND_CPP_CPU_REFERENCE, BG_BACKEND_RUST_CPU}) {
        bg_context *context = create_context(backend);
        auto *admission = create_admission(context, descriptor);
        assert(
            bg_docking_geometric_admission_v1_evaluate_fixed64(
                context, admission, &batch, &output) ==
            BG_STATUS_CAPACITY_OVERFLOW);
        assert(output.row_count == 0);
        bg_docking_geometric_admission_v1_destroy(admission);
        bg_context_destroy(context);
    }
}

void test_available_hip_lanes_match_cpu_and_repeat_bitwise() {
    Fixture fixture;
    const auto descriptor = fixture.descriptor();
    const auto batch = fixture.batch();
    bg_context *reference_context = create_context(BG_BACKEND_CPP_CPU_REFERENCE);
    auto *reference_admission =
        create_admission(reference_context, descriptor);
    const Evaluation reference =
        evaluate(reference_context, reference_admission, batch);
    for (const bg_backend backend : {BG_BACKEND_HIP_SAFE, BG_BACKEND_HIP_FAST}) {
        uint8_t available = 0;
        assert(bg_backend_is_available(backend, 0, &available) == BG_STATUS_OK);
        if (available == 0) {
            continue;
        }
        bg_context *context = create_context(backend);
        auto *admission = create_admission(context, descriptor);
        bg_backend observed = BG_BACKEND_AUTO;
        assert(
            bg_docking_geometric_admission_v1_get_backend(
                admission, &observed) == BG_STATUS_OK);
        assert(observed == backend);
        const Evaluation first = evaluate(context, admission, batch);
        const Evaluation second = evaluate(context, admission, batch);
        assert(
            std::memcmp(
                first.rows.data(), second.rows.data(), sizeof(first.rows)) ==
            0);
        for (std::size_t slot = 0; slot < kSlots; ++slot) {
            assert_row_parity(first.rows[slot], reference.rows[slot], 2.0e-11);
        }
        bg_docking_geometric_admission_v1_destroy(admission);
        bg_context_destroy(context);
    }
    bg_docking_geometric_admission_v1_destroy(reference_admission);
    bg_context_destroy(reference_context);
}

void test_policy_and_identity_fail_closed() {
    Fixture fixture;
    bg_context *context = create_context(BG_BACKEND_RUST_CPU);
    auto descriptor = fixture.descriptor();
    descriptor.hard_rejection_minimum_vdw_ratio = 0.56;
    bg_docking_geometric_admission_v1 *admission = nullptr;
    assert(
        bg_docking_geometric_admission_v1_create(
            context, &descriptor, &admission) == BG_STATUS_INVALID_ARGUMENT);
    assert(admission == nullptr);
    descriptor = fixture.descriptor();
    std::fill(
        std::begin(descriptor.backend_receipt_sha256),
        std::end(descriptor.backend_receipt_sha256),
        UINT8_C(0));
    assert(
        bg_docking_geometric_admission_v1_create(
            context, &descriptor, &admission) == BG_STATUS_INVALID_ARGUMENT);
    assert(admission == nullptr);
    bg_context_destroy(context);
}

}  // namespace

int main() {
    test_cpu_parity_deep_copy_and_threshold_boundary();
    test_invalid_output_and_aliasing_are_transactional();
    test_create_and_handle_aliasing_preserve_inputs();
    test_pair_budget_is_fail_closed_for_both_cpu_backends();
    test_available_hip_lanes_match_cpu_and_repeat_bitwise();
    test_policy_and_identity_fail_closed();
    return 0;
}
