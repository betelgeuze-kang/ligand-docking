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
constexpr std::size_t kAtoms = 4;
constexpr std::size_t kMovesPerSlot = BG_DOCKING_TORSION_V7_MAX_MOVES;
constexpr std::size_t kCoordinates = kSlots * kAtoms;
constexpr std::size_t kMoves = kSlots * kMovesPerSlot;

struct ContextFixture final {
    std::array<double, 2> receptor_x = {2.0, 20.0};
    std::array<double, 2> receptor_y = {1.0, 20.0};
    std::array<double, 2> receptor_z = {0.0, 20.0};
    std::array<double, 2> receptor_radii = {1.0, 1.0};
    std::array<double, kAtoms> ligand_radii = {1.0, 1.0, 1.0, 1.0};
    std::array<int32_t, kAtoms> parents = {-1, 0, 1, 2};
    std::array<uint64_t, 1> rotors = {2};
    std::array<uint64_t, 3> internal_i = {0, 0, 1};
    std::array<uint64_t, 3> internal_j = {2, 3, 3};

    bg_docking_torsion_v7_context_soa_v1 descriptor() const {
        bg_docking_torsion_v7_context_soa_v1 value{};
        assert(
            bg_docking_torsion_v7_context_soa_v1_init(&value) ==
            BG_STATUS_OK);
        value.receptor_atom_count = receptor_x.size();
        value.ligand_atom_count = ligand_radii.size();
        value.rotor_count = rotors.size();
        value.internal_pair_count = internal_i.size();
        value.receptor_x_angstrom = receptor_x.data();
        value.receptor_y_angstrom = receptor_y.data();
        value.receptor_z_angstrom = receptor_z.data();
        value.receptor_vdw_radius_angstrom = receptor_radii.data();
        value.ligand_vdw_radius_angstrom = ligand_radii.data();
        value.pocket_center_angstrom[0] = 1.5;
        value.pocket_center_angstrom[1] = 0.0;
        value.pocket_center_angstrom[2] = 0.0;
        value.parent_atom_index = parents.data();
        value.rotatable_child_atom_index = rotors.data();
        value.internal_pair_atom_i = internal_i.data();
        value.internal_pair_atom_j = internal_j.data();
        value.minimum_selected_final_receptor_penalty = 0.0;
        value.maximum_selected_final_receptor_penalty = 1'000'000.0;
        return value;
    }
};

struct BatchFixture final {
    std::array<bg_docking_torsion_v7_candidate_state, kSlots> states{};
    std::array<uint8_t, kSlots> eligible{};
    std::array<uint64_t, kSlots> max_steps{};
    std::array<uint64_t, kSlots> baseline_steps{};
    std::array<double, kCoordinates> source_x{};
    std::array<double, kCoordinates> source_y{};
    std::array<double, kCoordinates> source_z{};
    std::array<double, kCoordinates> baseline_x{};
    std::array<double, kCoordinates> baseline_y{};
    std::array<double, kCoordinates> baseline_z{};
    std::array<double, kCoordinates> baseline_angles{};

    BatchFixture() {
        states.fill(BG_DOCKING_TORSION_V7_CANDIDATE_INACTIVE);
        for (std::size_t slot = 0; slot < kSlots; ++slot) {
            const std::size_t start = slot * kAtoms;
            const std::array<double, kAtoms> x = {0.0, 1.0, 2.0, 2.0};
            const std::array<double, kAtoms> y = {0.0, 0.0, 0.0, 1.0};
            std::copy(x.begin(), x.end(), source_x.begin() +
                                             static_cast<std::ptrdiff_t>(start));
            std::copy(y.begin(), y.end(), source_y.begin() +
                                             static_cast<std::ptrdiff_t>(start));
        }
        baseline_x = source_x;
        baseline_y = source_y;
        baseline_z = source_z;
        states[0] = BG_DOCKING_TORSION_V7_CANDIDATE_REFINE;
        eligible[0] = UINT8_C(1);
        max_steps[0] = UINT64_C(4);
    }

    bg_docking_torsion_v7_candidate_batch_soa_v1 descriptor() const {
        bg_docking_torsion_v7_candidate_batch_soa_v1 value{};
        assert(
            bg_docking_torsion_v7_candidate_batch_soa_v1_init(&value) ==
            BG_STATUS_OK);
        value.ligand_atom_count = kAtoms;
        value.candidate_state = states.data();
        value.proposal_is_torsion_eligible = eligible.data();
        value.max_steps = max_steps.data();
        value.baseline_v6_accepted_steps = baseline_steps.data();
        value.source_x_angstrom = source_x.data();
        value.source_y_angstrom = source_y.data();
        value.source_z_angstrom = source_z.data();
        value.baseline_v6_x_angstrom = baseline_x.data();
        value.baseline_v6_y_angstrom = baseline_y.data();
        value.baseline_v6_z_angstrom = baseline_z.data();
        value.baseline_v6_torsion_angles_radians = baseline_angles.data();
        return value;
    }
};

struct OutputStorage final {
    std::array<bg_docking_torsion_v7_row_v1, kSlots> rows{};
    std::array<bg_docking_torsion_v7_move_v1, kMoves> moves{};
    std::array<double, kCoordinates> optimized_x{};
    std::array<double, kCoordinates> optimized_y{};
    std::array<double, kCoordinates> optimized_z{};
    std::array<double, kCoordinates> optimized_angles{};
    std::array<double, kCoordinates> final_x{};
    std::array<double, kCoordinates> final_y{};
    std::array<double, kCoordinates> final_z{};
    std::array<double, kCoordinates> final_angles{};

    explicit OutputStorage(double sentinel = 97.0) {
        bg_docking_torsion_v7_row_v1 row{};
        row.slot_index = UINT32_MAX;
        row.status = 93;
        rows.fill(row);
        bg_docking_torsion_v7_move_v1 movement{};
        movement.slot_index = UINT32_MAX;
        movement.evaluated = UINT8_C(95);
        moves.fill(movement);
        optimized_x.fill(sentinel);
        optimized_y.fill(sentinel);
        optimized_z.fill(sentinel);
        optimized_angles.fill(sentinel);
        final_x.fill(sentinel);
        final_y.fill(sentinel);
        final_z.fill(sentinel);
        final_angles.fill(sentinel);
    }

    bg_docking_torsion_v7_output_v1 descriptor() {
        bg_docking_torsion_v7_output_v1 value{};
        assert(bg_docking_torsion_v7_output_v1_init(&value) == BG_STATUS_OK);
        value.row_capacity = rows.size();
        value.move_capacity = moves.size();
        value.coordinate_capacity = optimized_x.size();
        value.rows = rows.data();
        value.moves = moves.data();
        value.optimized_x_angstrom = optimized_x.data();
        value.optimized_y_angstrom = optimized_y.data();
        value.optimized_z_angstrom = optimized_z.data();
        value.optimized_torsion_angles_radians = optimized_angles.data();
        value.final_x_angstrom = final_x.data();
        value.final_y_angstrom = final_y.data();
        value.final_z_angstrom = final_z.data();
        value.final_torsion_angles_radians = final_angles.data();
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

bg_docking_torsion_v7 *create_refiner(
    bg_context *context,
    const bg_docking_torsion_v7_context_soa_v1 &descriptor) {
    bg_docking_torsion_v7 *refiner = nullptr;
    assert(
        bg_docking_torsion_v7_create(context, &descriptor, &refiner) ==
        BG_STATUS_OK);
    assert(refiner != nullptr);
    return refiner;
}

bool close_with_tolerance(double left, double right, double tolerance) {
    const double scale = std::max({1.0, std::abs(left), std::abs(right)});
    return std::abs(left - right) <= tolerance * scale;
}

void assert_row_parity(
    const bg_docking_torsion_v7_row_v1 &left,
    const bg_docking_torsion_v7_row_v1 &right) {
    assert(left.slot_index == right.slot_index);
    assert(left.status == right.status);
    assert(left.failure_code == right.failure_code);
    assert(left.skip_reason == right.skip_reason);
    assert(left.selection_reason == right.selection_reason);
    assert(left.selection_window_reachable == right.selection_window_reachable);
    assert(
        left.evaluation_stopped_after_selection_window_became_unreachable ==
        right.evaluation_stopped_after_selection_window_became_unreachable);
    assert(left.torsion_evaluated == right.torsion_evaluated);
    assert(left.torsion_variant_available == right.torsion_variant_available);
    assert(left.torsion_selected == right.torsion_selected);
    assert(left.torsion_step_budget == right.torsion_step_budget);
    assert(
        left.fixed_objective_evaluation_count ==
        right.fixed_objective_evaluation_count);
    assert(
        left.torsion_trial_objective_evaluation_count ==
        right.torsion_trial_objective_evaluation_count);
    assert(left.evaluated_torsion_steps == right.evaluated_torsion_steps);
    assert(left.accepted_torsion_steps == right.accepted_torsion_steps);
    assert(
        left.baseline_v6_accepted_steps == right.baseline_v6_accepted_steps);
    const std::array<std::pair<double, double>, 14> values = {{
        {left.source_receptor_penalty, right.source_receptor_penalty},
        {left.source_internal_penalty, right.source_internal_penalty},
        {left.source_combined_penalty, right.source_combined_penalty},
        {left.baseline_receptor_penalty, right.baseline_receptor_penalty},
        {left.baseline_internal_penalty, right.baseline_internal_penalty},
        {left.baseline_combined_penalty, right.baseline_combined_penalty},
        {left.optimized_receptor_penalty, right.optimized_receptor_penalty},
        {left.optimized_internal_penalty, right.optimized_internal_penalty},
        {left.optimized_combined_penalty, right.optimized_combined_penalty},
        {left.final_receptor_penalty, right.final_receptor_penalty},
        {left.final_internal_penalty, right.final_internal_penalty},
        {left.final_combined_penalty, right.final_combined_penalty},
        {left.evaluated_total_torsion_path_radians,
         right.evaluated_total_torsion_path_radians},
        {left.accepted_total_torsion_path_radians,
         right.accepted_total_torsion_path_radians},
    }};
    for (const auto &value : values) {
        assert(close_with_tolerance(value.first, value.second, 4.0e-12));
    }
}

void assert_move_parity(
    const bg_docking_torsion_v7_move_v1 &left,
    const bg_docking_torsion_v7_move_v1 &right) {
    assert(left.slot_index == right.slot_index);
    assert(left.move_index == right.move_index);
    assert(left.evaluated == right.evaluated);
    assert(left.selected == right.selected);
    assert(
        left.rotatable_child_atom_index == right.rotatable_child_atom_index);
    assert(close_with_tolerance(left.delta_radians, right.delta_radians, 4.0e-12));
    assert(close_with_tolerance(
        left.receptor_penalty, right.receptor_penalty, 4.0e-12));
    assert(close_with_tolerance(
        left.internal_penalty, right.internal_penalty, 4.0e-12));
    assert(close_with_tolerance(
        left.combined_penalty, right.combined_penalty, 4.0e-12));
}

void assert_coordinate_parity(
    const OutputStorage &left,
    const OutputStorage &right) {
    const std::array<const std::array<double, kCoordinates> *, 8> left_values = {
        &left.optimized_x,
        &left.optimized_y,
        &left.optimized_z,
        &left.optimized_angles,
        &left.final_x,
        &left.final_y,
        &left.final_z,
        &left.final_angles,
    };
    const std::array<const std::array<double, kCoordinates> *, 8> right_values = {
        &right.optimized_x,
        &right.optimized_y,
        &right.optimized_z,
        &right.optimized_angles,
        &right.final_x,
        &right.final_y,
        &right.final_z,
        &right.final_angles,
    };
    for (std::size_t channel = 0; channel < left_values.size(); ++channel) {
        for (std::size_t index = 0; index < kCoordinates; ++index) {
            assert(close_with_tolerance(
                (*left_values[channel])[index],
                (*right_values[channel])[index],
                4.0e-12));
        }
    }
}

void assert_success_metadata(
    const bg_docking_torsion_v7_output_v1 &output) {
    assert(output.row_count == kSlots);
    assert(output.move_count == kMoves);
    assert(output.coordinate_count == kCoordinates);
    assert(output.molecular_execution_authorized == 0);
    assert(output.existing_rank_auto_change_authorized == 0);
    assert(output.customer_pose_emission_authorized == 0);
    assert(output.production_claim_authorized == 0);
}

void refine(
    bg_context *context,
    bg_docking_torsion_v7 *refiner,
    const bg_docking_torsion_v7_candidate_batch_soa_v1 &batch,
    OutputStorage *storage,
    bg_docking_torsion_v7_output_v1 *output) {
    assert(storage != nullptr);
    assert(output != nullptr);
    assert(
        bg_docking_torsion_v7_refine_fixed64(
            context, refiner, &batch, output) == BG_STATUS_OK);
    assert_success_metadata(*output);
}

void test_cpu_parity_fixed64_and_context_deep_copy() {
    ContextFixture context_fixture;
    const auto descriptor = context_fixture.descriptor();
    bg_context *cpp_context = create_context(BG_BACKEND_CPP_CPU_REFERENCE);
    bg_context *rust_context = create_context(BG_BACKEND_RUST_CPU);
    bg_docking_torsion_v7 *cpp_refiner =
        create_refiner(cpp_context, descriptor);
    bg_docking_torsion_v7 *rust_refiner =
        create_refiner(rust_context, descriptor);

    bg_backend observed = BG_BACKEND_AUTO;
    assert(
        bg_docking_torsion_v7_get_backend(cpp_refiner, &observed) ==
        BG_STATUS_OK);
    assert(observed == BG_BACKEND_CPP_CPU_REFERENCE);
    assert(
        bg_docking_torsion_v7_get_backend(rust_refiner, &observed) ==
        BG_STATUS_OK);
    assert(observed == BG_BACKEND_RUST_CPU);

    context_fixture.parents[0] = 0;
    context_fixture.receptor_x[0] =
        std::numeric_limits<double>::quiet_NaN();
    context_fixture.ligand_radii[0] =
        std::numeric_limits<double>::quiet_NaN();

    BatchFixture batch_fixture;
    const auto batch = batch_fixture.descriptor();
    OutputStorage cpp_storage;
    OutputStorage rust_storage;
    auto cpp_output = cpp_storage.descriptor();
    auto rust_output = rust_storage.descriptor();
    cpp_output.molecular_execution_authorized = UINT8_C(1);
    cpp_output.existing_rank_auto_change_authorized = UINT8_C(1);
    cpp_output.customer_pose_emission_authorized = UINT8_C(1);
    cpp_output.production_claim_authorized = UINT8_C(1);
    rust_output.molecular_execution_authorized = UINT8_C(1);
    rust_output.existing_rank_auto_change_authorized = UINT8_C(1);
    rust_output.customer_pose_emission_authorized = UINT8_C(1);
    rust_output.production_claim_authorized = UINT8_C(1);
    refine(cpp_context, cpp_refiner, batch, &cpp_storage, &cpp_output);
    refine(rust_context, rust_refiner, batch, &rust_storage, &rust_output);

    for (std::size_t slot = 0; slot < kSlots; ++slot) {
        assert_row_parity(cpp_storage.rows[slot], rust_storage.rows[slot]);
    }
    for (std::size_t index = 0; index < kMoves; ++index) {
        assert_move_parity(cpp_storage.moves[index], rust_storage.moves[index]);
    }
    assert_coordinate_parity(cpp_storage, rust_storage);
    assert(
        cpp_storage.rows[0].status == BG_DOCKING_TORSION_V7_ROW_REFINED);
    assert(cpp_storage.rows[0].torsion_evaluated == UINT8_C(1));
    assert(cpp_storage.rows[0].torsion_variant_available == UINT8_C(1));
    assert(cpp_storage.rows[0].torsion_selected == UINT8_C(1));
    assert(cpp_storage.rows[0].evaluated_torsion_steps == UINT64_C(4));
    assert(cpp_storage.rows[0].accepted_torsion_steps == UINT64_C(4));
    assert(
        cpp_storage.rows[0].optimized_combined_penalty <
        cpp_storage.rows[0].baseline_combined_penalty);
    assert(
        cpp_storage.rows[1].status ==
        BG_DOCKING_TORSION_V7_ROW_TYPED_FAILURE);
    assert(
        cpp_storage.rows[1].failure_code ==
        BG_DOCKING_TORSION_V7_FAILURE_UPSTREAM_NOT_ELIGIBLE);
    assert(
        std::count_if(
            cpp_storage.moves.begin(),
            cpp_storage.moves.end(),
            [](const bg_docking_torsion_v7_move_v1 &movement) {
                return movement.evaluated == UINT8_C(1);
            }) == 4);
    for (std::size_t atom = 0; atom < kAtoms; ++atom) {
        assert(cpp_storage.optimized_x[atom] == cpp_storage.final_x[atom]);
        assert(cpp_storage.optimized_y[atom] == cpp_storage.final_y[atom]);
        assert(cpp_storage.optimized_z[atom] == cpp_storage.final_z[atom]);
    }
    assert(!std::equal(
        cpp_storage.final_y.begin(),
        cpp_storage.final_y.begin() + static_cast<std::ptrdiff_t>(kAtoms),
        batch_fixture.baseline_y.begin()));

    OutputStorage rust_repeat_storage;
    auto rust_repeat_output = rust_repeat_storage.descriptor();
    refine(
        rust_context,
        rust_refiner,
        batch,
        &rust_repeat_storage,
        &rust_repeat_output);
    for (std::size_t slot = 0; slot < kSlots; ++slot) {
        assert_row_parity(
            rust_storage.rows[slot], rust_repeat_storage.rows[slot]);
    }
    for (std::size_t index = 0; index < kMoves; ++index) {
        assert_move_parity(
            rust_storage.moves[index], rust_repeat_storage.moves[index]);
    }
    assert_coordinate_parity(rust_storage, rust_repeat_storage);

    bg_docking_torsion_v7_destroy(cpp_refiner);
    bg_docking_torsion_v7_destroy(rust_refiner);
    bg_context_destroy(cpp_context);
    bg_context_destroy(rust_context);
}

void test_candidate_local_failure_preserves_denominator() {
    ContextFixture context_fixture;
    BatchFixture batch_fixture;
    batch_fixture.eligible[0] = UINT8_C(2);
    const auto context_descriptor = context_fixture.descriptor();
    const auto batch = batch_fixture.descriptor();
    bg_context *cpp_context = create_context(BG_BACKEND_CPP_CPU_REFERENCE);
    bg_context *rust_context = create_context(BG_BACKEND_RUST_CPU);
    bg_docking_torsion_v7 *cpp_refiner =
        create_refiner(cpp_context, context_descriptor);
    bg_docking_torsion_v7 *rust_refiner =
        create_refiner(rust_context, context_descriptor);
    OutputStorage cpp_storage;
    OutputStorage rust_storage;
    auto cpp_output = cpp_storage.descriptor();
    auto rust_output = rust_storage.descriptor();
    refine(cpp_context, cpp_refiner, batch, &cpp_storage, &cpp_output);
    refine(rust_context, rust_refiner, batch, &rust_storage, &rust_output);
    for (std::size_t slot = 0; slot < kSlots; ++slot) {
        assert_row_parity(cpp_storage.rows[slot], rust_storage.rows[slot]);
        assert(
            cpp_storage.rows[slot].status ==
            BG_DOCKING_TORSION_V7_ROW_TYPED_FAILURE);
    }
    assert(
        cpp_storage.rows[0].failure_code ==
        BG_DOCKING_TORSION_V7_FAILURE_INVALID_INPUT);
    assert(
        cpp_storage.rows[1].failure_code ==
        BG_DOCKING_TORSION_V7_FAILURE_UPSTREAM_NOT_ELIGIBLE);

    bg_docking_torsion_v7_destroy(cpp_refiner);
    bg_docking_torsion_v7_destroy(rust_refiner);
    bg_context_destroy(cpp_context);
    bg_context_destroy(rust_context);
}

void test_failures_are_transactional_and_cross_wiring_is_rejected() {
    ContextFixture context_fixture;
    BatchFixture batch_fixture;
    const auto context_descriptor = context_fixture.descriptor();
    auto batch = batch_fixture.descriptor();
    bg_context *cpp_context = create_context(BG_BACKEND_CPP_CPU_REFERENCE);
    bg_context *rust_context = create_context(BG_BACKEND_RUST_CPU);
    bg_docking_torsion_v7 *cpp_refiner =
        create_refiner(cpp_context, context_descriptor);

    OutputStorage malformed_storage(101.0);
    auto malformed_output = malformed_storage.descriptor();
    malformed_output.row_count = UINT64_C(701);
    malformed_output.move_count = UINT64_C(702);
    malformed_output.coordinate_count = UINT64_C(703);
    malformed_output.molecular_execution_authorized = UINT8_C(1);
    malformed_output.existing_rank_auto_change_authorized = UINT8_C(1);
    malformed_output.customer_pose_emission_authorized = UINT8_C(1);
    malformed_output.production_claim_authorized = UINT8_C(1);
    batch.candidate_count = kSlots - 1;
    assert(
        bg_docking_torsion_v7_refine_fixed64(
            cpp_context, cpp_refiner, &batch, &malformed_output) ==
        BG_STATUS_INVALID_ARGUMENT);
    assert(malformed_output.row_count == UINT64_C(701));
    assert(malformed_output.move_count == UINT64_C(702));
    assert(malformed_output.coordinate_count == UINT64_C(703));
    assert(malformed_output.molecular_execution_authorized == UINT8_C(1));
    assert(
        malformed_output.existing_rank_auto_change_authorized == UINT8_C(1));
    assert(malformed_output.customer_pose_emission_authorized == UINT8_C(1));
    assert(malformed_output.production_claim_authorized == UINT8_C(1));
    assert(malformed_storage.rows[0].slot_index == UINT32_MAX);
    assert(malformed_storage.rows[0].status == 93);
    assert(malformed_storage.moves[0].evaluated == UINT8_C(95));
    assert(std::all_of(
        malformed_storage.optimized_x.begin(),
        malformed_storage.optimized_x.end(),
        [](double value) { return value == 101.0; }));
    assert(std::all_of(
        malformed_storage.final_angles.begin(),
        malformed_storage.final_angles.end(),
        [](double value) { return value == 101.0; }));

    batch = batch_fixture.descriptor();
    OutputStorage cross_wired_storage(103.0);
    auto cross_wired_output = cross_wired_storage.descriptor();
    cross_wired_output.row_count = UINT64_C(801);
    assert(
        bg_docking_torsion_v7_refine_fixed64(
            rust_context, cpp_refiner, &batch, &cross_wired_output) ==
        BG_STATUS_INVALID_ARGUMENT);
    assert(cross_wired_output.row_count == UINT64_C(801));
    assert(cross_wired_storage.rows[0].slot_index == UINT32_MAX);
    assert(cross_wired_storage.optimized_x[0] == 103.0);

    batch = batch_fixture.descriptor();
    OutputStorage descriptor_alias_storage(107.0);
    auto descriptor_alias_output = descriptor_alias_storage.descriptor();
    descriptor_alias_output.rows =
        reinterpret_cast<bg_docking_torsion_v7_row_v1 *>(
            &descriptor_alias_output);
    const auto descriptor_alias_before = descriptor_alias_output;
    assert(
        bg_docking_torsion_v7_refine_fixed64(
            cpp_context,
            cpp_refiner,
            &batch,
            &descriptor_alias_output) == BG_STATUS_INVALID_ARGUMENT);
    assert(
        std::memcmp(
            &descriptor_alias_output,
            &descriptor_alias_before,
            sizeof(descriptor_alias_output)) == 0);
    assert(descriptor_alias_storage.moves[0].evaluated == UINT8_C(95));
    assert(descriptor_alias_storage.optimized_x[0] == 107.0);

    bg_docking_torsion_v7_destroy(cpp_refiner);
    bg_context_destroy(cpp_context);
    bg_context_destroy(rust_context);
}

void test_create_and_handle_aliasing_preserve_inputs() {
    ContextFixture context_fixture;
    BatchFixture batch_fixture;
    auto context_descriptor = context_fixture.descriptor();
    auto batch = batch_fixture.descriptor();
    bg_context *context = create_context(BG_BACKEND_CPP_CPU_REFERENCE);

    const auto receptor_x_before = context_fixture.receptor_x;
    auto **const channel_alias = reinterpret_cast<bg_docking_torsion_v7 **>(
        context_fixture.receptor_x.data());
    assert(
        bg_docking_torsion_v7_create(
            context, &context_descriptor, channel_alias) ==
        BG_STATUS_INVALID_ARGUMENT);
    assert(context_fixture.receptor_x == receptor_x_before);

    const auto context_descriptor_before = context_descriptor;
    auto **const descriptor_alias = reinterpret_cast<bg_docking_torsion_v7 **>(
        &context_descriptor);
    assert(
        bg_docking_torsion_v7_create(
            context, &context_descriptor, descriptor_alias) ==
        BG_STATUS_INVALID_ARGUMENT);
    assert(
        std::memcmp(
            &context_descriptor,
            &context_descriptor_before,
            sizeof(context_descriptor)) == 0);

    alignas(bg_docking_torsion_v7 *)
        std::array<std::byte, sizeof(bg_docking_torsion_v7 *) + 1>
            misaligned_storage{};
    auto **const misaligned = reinterpret_cast<bg_docking_torsion_v7 **>(
        misaligned_storage.data() + 1);
    assert(
        bg_docking_torsion_v7_create(
            context, &context_descriptor, misaligned) ==
        BG_STATUS_INVALID_ARGUMENT);

    bg_docking_torsion_v7 *refiner =
        create_refiner(context, context_descriptor);
    assert(
        bg_docking_torsion_v7_get_backend(
            refiner, reinterpret_cast<bg_backend *>(refiner)) ==
        BG_STATUS_INVALID_ARGUMENT);
    bg_backend observed = BG_BACKEND_AUTO;
    assert(
        bg_docking_torsion_v7_get_backend(refiner, &observed) ==
        BG_STATUS_OK);
    assert(observed == BG_BACKEND_CPP_CPU_REFERENCE);

    OutputStorage storage(109.0);
    auto output = storage.descriptor();
    output.row_count = UINT64_C(901);
    output.rows = reinterpret_cast<bg_docking_torsion_v7_row_v1 *>(refiner);
    assert(
        bg_docking_torsion_v7_refine_fixed64(
            context, refiner, &batch, &output) ==
        BG_STATUS_INVALID_ARGUMENT);
    assert(output.row_count == UINT64_C(901));
    assert(
        bg_docking_torsion_v7_get_backend(refiner, &observed) ==
        BG_STATUS_OK);

    output.rows = reinterpret_cast<bg_docking_torsion_v7_row_v1 *>(context);
    assert(
        bg_docking_torsion_v7_refine_fixed64(
            context, refiner, &batch, &output) ==
        BG_STATUS_INVALID_ARGUMENT);
    bg_backend context_backend = BG_BACKEND_AUTO;
    assert(
        bg_context_get_backend(context, &context_backend) == BG_STATUS_OK);
    assert(context_backend == BG_BACKEND_CPP_CPU_REFERENCE);

    const auto batch_before = batch;
    output.rows = reinterpret_cast<bg_docking_torsion_v7_row_v1 *>(&batch);
    assert(
        bg_docking_torsion_v7_refine_fixed64(
            context, refiner, &batch, &output) ==
        BG_STATUS_INVALID_ARGUMENT);
    assert(std::memcmp(&batch, &batch_before, sizeof(batch)) == 0);

    bg_docking_torsion_v7_destroy(refiner);
    bg_context_destroy(context);
}

void test_context_pair_bound_and_coordinate_free_validation() {
    ContextFixture fixture;
    auto excessive_pairs = fixture.descriptor();
    excessive_pairs.internal_pair_count = UINT64_C(7);

    for (const bg_backend backend :
         {BG_BACKEND_CPP_CPU_REFERENCE, BG_BACKEND_RUST_CPU}) {
        bg_context *context = create_context(backend);
        bg_docking_torsion_v7 *refiner = nullptr;
        assert(
            bg_docking_torsion_v7_create(
                context, &excessive_pairs, &refiner) ==
            BG_STATUS_CAPACITY_OVERFLOW);
        assert(refiner == nullptr);
        bg_context_destroy(context);
    }

    auto large_weight = fixture.descriptor();
    large_weight.internal_overlap_weight =
        std::numeric_limits<double>::max();
    for (const bg_backend backend :
         {BG_BACKEND_CPP_CPU_REFERENCE, BG_BACKEND_RUST_CPU}) {
        bg_context *context = create_context(backend);
        bg_docking_torsion_v7 *refiner =
            create_refiner(context, large_weight);
        bg_docking_torsion_v7_destroy(refiner);
        bg_context_destroy(context);
    }
}

void test_hip_parity_when_device_is_available(bg_backend backend) {
    uint8_t available = UINT8_C(0);
    assert(bg_backend_is_available(backend, 0, &available) == BG_STATUS_OK);
    if (available == UINT8_C(0)) {
        return;
    }

    ContextFixture context_fixture;
    const auto context_descriptor = context_fixture.descriptor();
    bg_context *rust_context = create_context(BG_BACKEND_RUST_CPU);
    bg_context *hip_context = create_context(backend);
    bg_docking_torsion_v7 *rust_refiner =
        create_refiner(rust_context, context_descriptor);
    bg_docking_torsion_v7 *hip_refiner =
        create_refiner(hip_context, context_descriptor);

    bg_backend observed = BG_BACKEND_AUTO;
    assert(
        bg_docking_torsion_v7_get_backend(hip_refiner, &observed) ==
        BG_STATUS_OK);
    assert(observed == backend);

    context_fixture.parents[0] = 0;
    context_fixture.receptor_x[0] =
        std::numeric_limits<double>::quiet_NaN();
    context_fixture.ligand_radii[0] =
        std::numeric_limits<double>::quiet_NaN();

    BatchFixture batch_fixture;
    batch_fixture.states[1] = BG_DOCKING_TORSION_V7_CANDIDATE_REFINE;
    batch_fixture.eligible[1] = UINT8_C(2);
    const auto batch = batch_fixture.descriptor();
    OutputStorage rust_storage;
    OutputStorage hip_storage;
    OutputStorage hip_repeat_storage;
    auto rust_output = rust_storage.descriptor();
    auto hip_output = hip_storage.descriptor();
    auto hip_repeat_output = hip_repeat_storage.descriptor();
    refine(
        rust_context,
        rust_refiner,
        batch,
        &rust_storage,
        &rust_output);
    refine(hip_context, hip_refiner, batch, &hip_storage, &hip_output);
    refine(
        hip_context,
        hip_refiner,
        batch,
        &hip_repeat_storage,
        &hip_repeat_output);

    for (std::size_t slot = 0; slot < kSlots; ++slot) {
        assert_row_parity(rust_storage.rows[slot], hip_storage.rows[slot]);
        assert_row_parity(
            hip_storage.rows[slot], hip_repeat_storage.rows[slot]);
    }
    for (std::size_t index = 0; index < kMoves; ++index) {
        assert_move_parity(
            rust_storage.moves[index], hip_storage.moves[index]);
        assert_move_parity(
            hip_storage.moves[index], hip_repeat_storage.moves[index]);
    }
    assert_coordinate_parity(rust_storage, hip_storage);
    assert_coordinate_parity(hip_storage, hip_repeat_storage);
    assert(
        hip_storage.rows[1].failure_code ==
        BG_DOCKING_TORSION_V7_FAILURE_INVALID_INPUT);

    bg_docking_torsion_v7_destroy(rust_refiner);
    bg_docking_torsion_v7_destroy(hip_refiner);
    bg_context_destroy(rust_context);
    bg_context_destroy(hip_context);
}

}  // namespace

int main() {
    static_assert(
        std::is_standard_layout_v<bg_docking_torsion_v7_context_soa_v1>);
    static_assert(std::is_standard_layout_v<
                  bg_docking_torsion_v7_candidate_batch_soa_v1>);
    static_assert(std::is_standard_layout_v<bg_docking_torsion_v7_row_v1>);
    static_assert(std::is_standard_layout_v<bg_docking_torsion_v7_move_v1>);
    static_assert(std::is_standard_layout_v<bg_docking_torsion_v7_output_v1>);
    static_assert(noexcept(bg_docking_torsion_v7_destroy(nullptr)));
    test_cpu_parity_fixed64_and_context_deep_copy();
    test_candidate_local_failure_preserves_denominator();
    test_failures_are_transactional_and_cross_wiring_is_rejected();
    test_create_and_handle_aliasing_preserve_inputs();
    test_context_pair_bound_and_coordinate_free_validation();
    test_hip_parity_when_device_is_available(BG_BACKEND_HIP_SAFE);
    test_hip_parity_when_device_is_available(BG_BACKEND_HIP_FAST);
    return 0;
}
