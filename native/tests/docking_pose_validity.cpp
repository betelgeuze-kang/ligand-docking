#include "betelgeuze/engine.h"

#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <type_traits>

namespace {

constexpr std::size_t kSlots = BG_DOCKING_FIXED64_CANDIDATE_COUNT;
constexpr std::size_t kLigandAtoms = 4;

struct Fixture final {
    std::array<double, 2> receptor_x = {5.0, 6.0};
    std::array<double, 2> receptor_y = {0.0, 0.0};
    std::array<double, 2> receptor_z = {0.0, 0.0};
    std::array<double, 2> receptor_radius = {1.5, 1.5};
    std::array<double, 4> ligand_x = {0.0, 0.0, 1.0, 1.0};
    std::array<double, 4> ligand_y = {1.0, 0.0, 0.0, 1.0};
    std::array<double, 4> ligand_z = {0.0, 0.0, 0.0, 1.0};
    std::array<double, 4> ligand_radius = {0.7, 0.7, 0.7, 0.7};
    std::array<uint64_t, 3> bond_i = {0, 1, 2};
    std::array<uint64_t, 3> bond_j = {1, 2, 3};
    std::array<uint64_t, 3> exclusion_i = {0, 1, 2};
    std::array<uint64_t, 3> exclusion_j = {1, 2, 3};
    std::array<uint64_t, 1> chirality_center = {0};
    std::array<uint64_t, 1> chirality_i = {1};
    std::array<uint64_t, 1> chirality_j = {2};
    std::array<uint64_t, 1> chirality_k = {3};

    std::array<bg_docking_pose_validity_candidate_state, kSlots> states{};
    std::array<bg_docking_scorer_v1_failure, kSlots> upstream{};
    std::array<double, kSlots> quaternion_x{};
    std::array<double, kSlots> quaternion_y{};
    std::array<double, kSlots> quaternion_z{};
    std::array<double, kSlots> quaternion_w{};
    std::array<double, kSlots * kLigandAtoms> candidate_x{};
    std::array<double, kSlots * kLigandAtoms> candidate_y{};
    std::array<double, kSlots * kLigandAtoms> candidate_z{};

    Fixture() {
        states.fill(
            BG_DOCKING_POSE_VALIDITY_CANDIDATE_UPSTREAM_FAILURE);
        upstream.fill(
            BG_DOCKING_SCORER_V1_FAILURE_UPSTREAM_NOT_ADMITTED);
        quaternion_w.fill(1.0);
        for (std::size_t slot = 0; slot < kSlots; ++slot) {
            for (std::size_t atom = 0; atom < kLigandAtoms; ++atom) {
                const std::size_t offset = slot * kLigandAtoms + atom;
                candidate_x[offset] = ligand_x[atom];
                candidate_y[offset] = ligand_y[atom];
                candidate_z[offset] = ligand_z[atom];
            }
        }
        for (std::size_t slot = 0; slot < 3; ++slot) {
            states[slot] = BG_DOCKING_POSE_VALIDITY_CANDIDATE_EVALUATE;
            upstream[slot] = BG_DOCKING_SCORER_V1_FAILURE_NONE;
        }
        quaternion_x[1] = 1.0;
        candidate_x[2 * kLigandAtoms] =
            std::numeric_limits<double>::quiet_NaN();
    }

    bg_docking_pose_validity_context_soa_v1 context_descriptor(
        uint64_t max_cross_checks = 1'000'000) const {
        bg_docking_pose_validity_context_soa_v1 value{};
        assert(
            bg_docking_pose_validity_context_soa_v1_init(&value) ==
            BG_STATUS_OK);
        value.receptor_atom_count = receptor_x.size();
        value.ligand_atom_count = ligand_x.size();
        value.receptor_x_angstrom = receptor_x.data();
        value.receptor_y_angstrom = receptor_y.data();
        value.receptor_z_angstrom = receptor_z.data();
        value.receptor_vdw_radius_angstrom = receptor_radius.data();
        value.ligand_reference_x_angstrom = ligand_x.data();
        value.ligand_reference_y_angstrom = ligand_y.data();
        value.ligand_reference_z_angstrom = ligand_z.data();
        value.ligand_vdw_radius_angstrom = ligand_radius.data();
        value.bond_count = bond_i.size();
        value.bond_atom_i = bond_i.data();
        value.bond_atom_j = bond_j.data();
        value.ligand_exclusion_count = exclusion_i.size();
        value.ligand_exclusion_atom_i = exclusion_i.data();
        value.ligand_exclusion_atom_j = exclusion_j.data();
        value.chirality_center_count = chirality_center.size();
        value.chirality_center_atom = chirality_center.data();
        value.chirality_atom_i = chirality_i.data();
        value.chirality_atom_j = chirality_j.data();
        value.chirality_atom_k = chirality_k.data();
        value.pocket_center_angstrom[0] = 0.0;
        value.pocket_center_angstrom[1] = 0.0;
        value.pocket_center_angstrom[2] = 0.0;
        value.pocket_radius_angstrom = 20.0;
        value.max_cross_checks = max_cross_checks;
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
            std::begin(value.scorer_context_receipt_sha256),
            std::end(value.scorer_context_receipt_sha256),
            UINT8_C(0x44));
        std::fill(
            std::begin(value.backend_receipt_sha256),
            std::end(value.backend_receipt_sha256),
            UINT8_C(0x55));
        std::fill(
            std::begin(value.contact_policy_sha256),
            std::end(value.contact_policy_sha256),
            UINT8_C(0x66));
        return value;
    }

    bg_docking_pose_validity_candidate_batch_soa_v1 batch() const {
        bg_docking_pose_validity_candidate_batch_soa_v1 value{};
        assert(
            bg_docking_pose_validity_candidate_batch_soa_v1_init(&value) ==
            BG_STATUS_OK);
        value.ligand_atom_count = kLigandAtoms;
        value.candidate_state = states.data();
        value.upstream_scorer_failure_code = upstream.data();
        value.quaternion_x = quaternion_x.data();
        value.quaternion_y = quaternion_y.data();
        value.quaternion_z = quaternion_z.data();
        value.quaternion_w = quaternion_w.data();
        value.x_angstrom = candidate_x.data();
        value.y_angstrom = candidate_y.data();
        value.z_angstrom = candidate_z.data();
        return value;
    }
};

bg_context *create_context(bg_backend backend) {
    bg_context_options options{};
    assert(bg_context_options_init(&options) == BG_STATUS_OK);
    options.backend = backend;
    bg_context *context = nullptr;
    assert(bg_context_create(&options, &context) == BG_STATUS_OK);
    assert(context != nullptr);
    return context;
}

bg_docking_pose_validity_v1 *create_validity(
    bg_context *context,
    const bg_docking_pose_validity_context_soa_v1 &descriptor) {
    bg_docking_pose_validity_v1 *validity = nullptr;
    assert(
        bg_docking_pose_validity_v1_create(
            context, &descriptor, &validity) == BG_STATUS_OK);
    assert(validity != nullptr);
    return validity;
}

std::array<bg_docking_pose_validity_row_v1, kSlots> evaluate(
    bg_context *context,
    bg_docking_pose_validity_v1 *validity,
    const bg_docking_pose_validity_candidate_batch_soa_v1 &batch) {
    std::array<bg_docking_pose_validity_row_v1, kSlots> rows{};
    bg_docking_pose_validity_output_v1 output{};
    assert(bg_docking_pose_validity_output_v1_init(&output) == BG_STATUS_OK);
    output.row_capacity = rows.size();
    output.rows = rows.data();
    assert(
        bg_docking_pose_validity_v1_evaluate_fixed64(
            context, validity, &batch, &output) == BG_STATUS_OK);
    assert(output.row_count == rows.size());
    return rows;
}

bool close_with_tolerance(double left, double right, double tolerance) {
    const double scale = std::max({1.0, std::abs(left), std::abs(right)});
    return std::abs(left - right) <= tolerance * scale;
}

void assert_row_parity(
    const bg_docking_pose_validity_row_v1 &cpp,
    const bg_docking_pose_validity_row_v1 &rust) {
    assert(cpp.slot_index == rust.slot_index);
    assert(cpp.status == rust.status);
    assert(cpp.failure_code == rust.failure_code);
    assert(
        cpp.upstream_scorer_failure_code ==
        rust.upstream_scorer_failure_code);
    assert(cpp.passed_check_mask == rust.passed_check_mask);
    assert(cpp.blocker_mask == rust.blocker_mask);
    assert(cpp.observed_count == rust.observed_count);
    assert(cpp.atom_count == rust.atom_count);
    assert(
        cpp.evaluated_ligand_nonbonded_pair_count ==
        rust.evaluated_ligand_nonbonded_pair_count);
    assert(
        cpp.excluded_ligand_pair_count == rust.excluded_ligand_pair_count);
    assert(
        cpp.evaluated_receptor_ligand_pair_count ==
        rust.evaluated_receptor_ligand_pair_count);
    assert(
        cpp.declared_chirality_center_count ==
        rust.declared_chirality_center_count);
    assert(
        cpp.element_vdw_ligand_pair_count ==
        rust.element_vdw_ligand_pair_count);
    assert(
        cpp.element_vdw_ligand_severe_overlap_count ==
        rust.element_vdw_ligand_severe_overlap_count);
    assert(
        cpp.element_vdw_receptor_candidate_pair_count ==
        rust.element_vdw_receptor_candidate_pair_count);
    assert(
        cpp.element_vdw_receptor_full_cartesian_pair_count ==
        rust.element_vdw_receptor_full_cartesian_pair_count);
    assert(
        cpp.element_vdw_receptor_cell_count ==
        rust.element_vdw_receptor_cell_count);
    assert(
        cpp.element_vdw_receptor_severe_overlap_count ==
        rust.element_vdw_receptor_severe_overlap_count);
    const std::array<std::pair<double, double>, 11> values = {{
        {cpp.rotation_orthogonality_max_error,
         rust.rotation_orthogonality_max_error},
        {cpp.rotation_determinant, rust.rotation_determinant},
        {cpp.max_bond_length_delta_angstrom,
         rust.max_bond_length_delta_angstrom},
        {cpp.minimum_ligand_nonbonded_distance_angstrom,
         rust.minimum_ligand_nonbonded_distance_angstrom},
        {cpp.minimum_receptor_ligand_distance_angstrom,
         rust.minimum_receptor_ligand_distance_angstrom},
        {cpp.minimum_declared_chiral_volume,
         rust.minimum_declared_chiral_volume},
        {cpp.maximum_pocket_center_distance_angstrom,
         rust.maximum_pocket_center_distance_angstrom},
        {cpp.element_vdw_ligand_minimum_distance_angstrom,
         rust.element_vdw_ligand_minimum_distance_angstrom},
        {cpp.element_vdw_ligand_minimum_ratio,
         rust.element_vdw_ligand_minimum_ratio},
        {cpp.element_vdw_receptor_minimum_distance_angstrom,
         rust.element_vdw_receptor_minimum_distance_angstrom},
        {cpp.element_vdw_receptor_minimum_ratio,
         rust.element_vdw_receptor_minimum_ratio},
    }};
    for (const auto &[left, right] : values) {
        assert(close_with_tolerance(left, right, 2.0e-12));
    }
}

void test_cpu_parity_repeat_stability_and_failure_preservation() {
    const Fixture fixture;
    const auto descriptor = fixture.context_descriptor();
    const auto batch = fixture.batch();
    bg_context *cpp_context = create_context(BG_BACKEND_CPP_CPU_REFERENCE);
    bg_context *rust_context = create_context(BG_BACKEND_RUST_CPU);
    bg_docking_pose_validity_v1 *cpp_validity =
        create_validity(cpp_context, descriptor);
    bg_docking_pose_validity_v1 *rust_validity =
        create_validity(rust_context, descriptor);

    bg_backend backend = BG_BACKEND_AUTO;
    assert(
        bg_docking_pose_validity_v1_get_backend(cpp_validity, &backend) ==
        BG_STATUS_OK);
    assert(backend == BG_BACKEND_CPP_CPU_REFERENCE);
    assert(
        bg_docking_pose_validity_v1_get_backend(rust_validity, &backend) ==
        BG_STATUS_OK);
    assert(backend == BG_BACKEND_RUST_CPU);

    const auto cpp_rows = evaluate(cpp_context, cpp_validity, batch);
    const auto rust_rows = evaluate(rust_context, rust_validity, batch);
    const auto rust_repeat = evaluate(rust_context, rust_validity, batch);
    assert(
        std::memcmp(
            rust_rows.data(), rust_repeat.data(), sizeof(rust_rows)) == 0);
    for (std::size_t slot = 0; slot < kSlots; ++slot) {
        assert_row_parity(cpp_rows[slot], rust_rows[slot]);
    }
    assert(
        rust_rows[0].status == BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED);
    assert(
        rust_rows[0].passed_check_mask ==
        BG_DOCKING_POSE_VALIDITY_CHECK_ALL);
    assert(
        rust_rows[1].status == BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED);
    assert(
        (rust_rows[1].blocker_mask &
         BG_DOCKING_POSE_VALIDITY_CHECK_PROPER_ROTATION) != 0);
    assert(
        rust_rows[2].failure_code ==
        BG_DOCKING_POSE_VALIDITY_FAILURE_INVALID_CANDIDATE_COORDINATES);
    assert(
        rust_rows[3].status ==
        BG_DOCKING_POSE_VALIDITY_ROW_UPSTREAM_SCORER_FAILURE);

    bg_docking_pose_validity_v1_destroy(cpp_validity);
    bg_docking_pose_validity_v1_destroy(rust_validity);
    bg_context_destroy(cpp_context);
    bg_context_destroy(rust_context);
}

void test_candidate_capacity_and_transactional_rejection() {
    const Fixture fixture;
    const auto descriptor = fixture.context_descriptor(1);
    auto batch = fixture.batch();
    bg_context *cpp_context = create_context(BG_BACKEND_CPP_CPU_REFERENCE);
    bg_context *rust_context = create_context(BG_BACKEND_RUST_CPU);
    bg_docking_pose_validity_v1 *cpp_validity =
        create_validity(cpp_context, descriptor);
    bg_docking_pose_validity_v1 *rust_validity =
        create_validity(rust_context, descriptor);
    const auto cpp_rows = evaluate(cpp_context, cpp_validity, batch);
    const auto rust_rows = evaluate(rust_context, rust_validity, batch);
    for (std::size_t slot = 0; slot < kSlots; ++slot) {
        assert_row_parity(cpp_rows[slot], rust_rows[slot]);
    }
    assert(
        rust_rows[0].failure_code ==
        BG_DOCKING_POSE_VALIDITY_FAILURE_RECEPTOR_CROSS_CAPACITY);

    std::array<bg_docking_pose_validity_row_v1, kSlots> sentinel{};
    std::memset(sentinel.data(), 0x5a, sizeof(sentinel));
    const auto before = sentinel;
    bg_docking_pose_validity_output_v1 output{};
    assert(bg_docking_pose_validity_output_v1_init(&output) == BG_STATUS_OK);
    output.row_capacity = sentinel.size();
    output.row_count = 17;
    output.rows = sentinel.data();
    auto invalid_states = fixture.states;
    invalid_states[0] = 99;
    batch.candidate_state = invalid_states.data();
    assert(
        bg_docking_pose_validity_v1_evaluate_fixed64(
            rust_context, rust_validity, &batch, &output) ==
        BG_STATUS_INVALID_ARGUMENT);
    assert(output.row_count == 17);
    assert(std::memcmp(sentinel.data(), before.data(), sizeof(before)) == 0);

    const auto valid_batch = fixture.batch();
    assert(
        bg_docking_pose_validity_v1_evaluate_fixed64(
            cpp_context, rust_validity, &valid_batch, &output) ==
        BG_STATUS_INVALID_ARGUMENT);
    bg_docking_pose_validity_v1_destroy(cpp_validity);
    bg_docking_pose_validity_v1_destroy(rust_validity);
    bg_context_destroy(cpp_context);
    bg_context_destroy(rust_context);
}

}  // namespace

int main() {
    static_assert(std::is_standard_layout_v<
                  bg_docking_pose_validity_context_soa_v1>);
    static_assert(std::is_standard_layout_v<
                  bg_docking_pose_validity_candidate_batch_soa_v1>);
    static_assert(
        std::is_standard_layout_v<bg_docking_pose_validity_row_v1>);
    static_assert(
        std::is_standard_layout_v<bg_docking_pose_validity_output_v1>);
    test_cpu_parity_repeat_stability_and_failure_preservation();
    test_candidate_capacity_and_transactional_rejection();
    return 0;
}
