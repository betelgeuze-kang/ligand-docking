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
constexpr std::size_t kAtoms = 3;
constexpr std::size_t kCoordinates = kSlots * kAtoms;

struct ContextFixture final {
    std::array<double, 2> receptor_x = {6.0, 8.0};
    std::array<double, 2> receptor_y = {0.0, 0.5};
    std::array<double, 2> receptor_z = {0.0, 0.0};
    std::array<double, 2> receptor_radii = {1.7, 1.7};
    std::array<double, kAtoms> ligand_radii = {1.6, 1.6, 1.6};

    bg_docking_rigid_refinement_context_soa_v1 descriptor() const {
        bg_docking_rigid_refinement_context_soa_v1 value{};
        assert(
            bg_docking_rigid_refinement_context_soa_v1_init(&value) ==
            BG_STATUS_OK);
        value.receptor_atom_count = receptor_x.size();
        value.ligand_atom_count = ligand_radii.size();
        value.receptor_x_angstrom = receptor_x.data();
        value.receptor_y_angstrom = receptor_y.data();
        value.receptor_z_angstrom = receptor_z.data();
        value.receptor_vdw_radius_angstrom = receptor_radii.data();
        value.ligand_vdw_radius_angstrom = ligand_radii.data();
        value.pocket_radius_angstrom = 8.0;
        return value;
    }
};

struct BatchFixture final {
    std::array<bg_docking_rigid_refinement_candidate_mode, kSlots> modes{};
    std::array<uint64_t, kSlots> max_steps{};
    std::array<double, kCoordinates> x{};
    std::array<double, kCoordinates> y{};
    std::array<double, kCoordinates> z{};

    BatchFixture() {
        modes.fill(BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_INACTIVE);
        max_steps.fill(UINT64_C(8));
        for (std::size_t slot = 0; slot < kSlots; ++slot) {
            const std::size_t offset = slot * kAtoms;
            x[offset] = 0.0;
            x[offset + 1] = 0.0;
            x[offset + 2] = 0.0;
            y[offset] = -0.7;
            y[offset + 1] = 0.0;
            y[offset + 2] = 0.7;
        }
        modes[0] = BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION;
        modes[1] =
            BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V3_TRANSLATION_ROTATION;
        modes[2] =
            BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V2_LANE;
        for (std::size_t slot = 0; slot < 3; ++slot) {
            const std::size_t offset = slot * kAtoms;
            x[offset] = 6.1;
            x[offset + 1] = 6.1;
            x[offset + 2] = 6.1;
        }
        modes[3] =
            BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V3_LANE;
        modes[4] = 99;
        modes[5] = BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION;
        x[5 * kAtoms] = std::numeric_limits<double>::quiet_NaN();
    }

    bg_docking_rigid_refinement_candidate_batch_soa_v1 descriptor() const {
        bg_docking_rigid_refinement_candidate_batch_soa_v1 value{};
        assert(
            bg_docking_rigid_refinement_candidate_batch_soa_v1_init(&value) ==
            BG_STATUS_OK);
        value.ligand_atom_count = kAtoms;
        value.candidate_mode = modes.data();
        value.max_steps = max_steps.data();
        value.x_angstrom = x.data();
        value.y_angstrom = y.data();
        value.z_angstrom = z.data();
        return value;
    }
};

struct OutputStorage final {
    std::array<bg_docking_rigid_refinement_row_v1, kSlots> rows{};
    std::array<double, kCoordinates> selected_x{};
    std::array<double, kCoordinates> selected_y{};
    std::array<double, kCoordinates> selected_z{};
    std::array<double, kCoordinates> comparison_x{};
    std::array<double, kCoordinates> comparison_y{};
    std::array<double, kCoordinates> comparison_z{};
    std::array<double, kCoordinates> baseline_x{};
    std::array<double, kCoordinates> baseline_y{};
    std::array<double, kCoordinates> baseline_z{};
    std::array<double, kCoordinates> clearance_x{};
    std::array<double, kCoordinates> clearance_y{};
    std::array<double, kCoordinates> clearance_z{};

    explicit OutputStorage(double sentinel = 97.0) {
        bg_docking_rigid_refinement_row_v1 row{};
        row.slot_index = UINT32_MAX;
        row.status = 93;
        rows.fill(row);
        selected_x.fill(sentinel);
        selected_y.fill(sentinel);
        selected_z.fill(sentinel);
        comparison_x.fill(sentinel);
        comparison_y.fill(sentinel);
        comparison_z.fill(sentinel);
        baseline_x.fill(sentinel);
        baseline_y.fill(sentinel);
        baseline_z.fill(sentinel);
        clearance_x.fill(sentinel);
        clearance_y.fill(sentinel);
        clearance_z.fill(sentinel);
    }

    bg_docking_rigid_refinement_output_v1 descriptor() {
        bg_docking_rigid_refinement_output_v1 value{};
        assert(
            bg_docking_rigid_refinement_output_v1_init(&value) ==
            BG_STATUS_OK);
        value.row_capacity = rows.size();
        value.coordinate_capacity = selected_x.size();
        value.rows = rows.data();
        value.selected_x_angstrom = selected_x.data();
        value.selected_y_angstrom = selected_y.data();
        value.selected_z_angstrom = selected_z.data();
        value.comparison_v2_x_angstrom = comparison_x.data();
        value.comparison_v2_y_angstrom = comparison_y.data();
        value.comparison_v2_z_angstrom = comparison_z.data();
        value.baseline_v3_x_angstrom = baseline_x.data();
        value.baseline_v3_y_angstrom = baseline_y.data();
        value.baseline_v3_z_angstrom = baseline_z.data();
        value.clearance_v4_x_angstrom = clearance_x.data();
        value.clearance_v4_y_angstrom = clearance_y.data();
        value.clearance_v4_z_angstrom = clearance_z.data();
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

bg_docking_rigid_refinement *create_refiner(
    bg_context *context,
    const bg_docking_rigid_refinement_context_soa_v1 &descriptor) {
    bg_docking_rigid_refinement *refiner = nullptr;
    assert(
        bg_docking_rigid_refinement_create(context, &descriptor, &refiner) ==
        BG_STATUS_OK);
    assert(refiner != nullptr);
    return refiner;
}

bool close(double left, double right) {
    const double scale = std::max({1.0, std::abs(left), std::abs(right)});
    return std::abs(left - right) <= 8.0e-12 * scale;
}

void assert_evidence_parity(
    const bg_docking_rigid_refinement_evidence_v1 &left,
    const bg_docking_rigid_refinement_evidence_v1 &right) {
    assert(left.profile == right.profile);
    assert(left.available == right.available);
    assert(left.accepted_steps == right.accepted_steps);
    assert(left.accepted_translation_steps == right.accepted_translation_steps);
    assert(left.accepted_rotation_steps == right.accepted_rotation_steps);
    assert(
        left.line_search_evaluation_count ==
        right.line_search_evaluation_count);
    assert(
        left.fallback_direction_step_count ==
        right.fallback_direction_step_count);
    const std::array<std::pair<double, double>, 12> values = {{
        {left.initial_penalty, right.initial_penalty},
        {left.final_penalty, right.final_penalty},
        {left.total_translation_angstrom[0], right.total_translation_angstrom[0]},
        {left.total_translation_angstrom[1], right.total_translation_angstrom[1]},
        {left.total_translation_angstrom[2], right.total_translation_angstrom[2]},
        {left.total_rotation_vector_radians[0],
         right.total_rotation_vector_radians[0]},
        {left.total_rotation_vector_radians[1],
         right.total_rotation_vector_radians[1]},
        {left.total_rotation_vector_radians[2],
         right.total_rotation_vector_radians[2]},
        {left.total_rotation_path_radians, right.total_rotation_path_radians},
        {left.initial_centroid_offset_angstrom,
         right.initial_centroid_offset_angstrom},
        {left.final_centroid_offset_angstrom,
         right.final_centroid_offset_angstrom},
        {left.maximum_centroid_offset_angstrom,
         right.maximum_centroid_offset_angstrom},
    }};
    for (const auto &value : values) {
        assert(close(value.first, value.second));
    }
}

void assert_parity(const OutputStorage &left, const OutputStorage &right) {
    for (std::size_t slot = 0; slot < kSlots; ++slot) {
        const auto &left_row = left.rows[slot];
        const auto &right_row = right.rows[slot];
        assert(left_row.slot_index == right_row.slot_index);
        assert(left_row.status == right_row.status);
        assert(left_row.failure_code == right_row.failure_code);
        assert(left_row.candidate_mode == right_row.candidate_mode);
        assert(left_row.selected_profile == right_row.selected_profile);
        assert(
            left_row.baseline_duplicate_of_v2 ==
            right_row.baseline_duplicate_of_v2);
        assert(left_row.clearance_evaluated == right_row.clearance_evaluated);
        assert(left_row.clearance_selected == right_row.clearance_selected);
        assert_evidence_parity(left_row.selected, right_row.selected);
        assert_evidence_parity(left_row.comparison_v2, right_row.comparison_v2);
        assert_evidence_parity(left_row.baseline_v3, right_row.baseline_v3);
        assert_evidence_parity(left_row.clearance_v4, right_row.clearance_v4);
    }
    const std::array<const std::array<double, kCoordinates> *, 12> left_channels = {
        &left.selected_x,
        &left.selected_y,
        &left.selected_z,
        &left.comparison_x,
        &left.comparison_y,
        &left.comparison_z,
        &left.baseline_x,
        &left.baseline_y,
        &left.baseline_z,
        &left.clearance_x,
        &left.clearance_y,
        &left.clearance_z,
    };
    const std::array<const std::array<double, kCoordinates> *, 12> right_channels = {
        &right.selected_x,
        &right.selected_y,
        &right.selected_z,
        &right.comparison_x,
        &right.comparison_y,
        &right.comparison_z,
        &right.baseline_x,
        &right.baseline_y,
        &right.baseline_z,
        &right.clearance_x,
        &right.clearance_y,
        &right.clearance_z,
    };
    for (std::size_t channel = 0; channel < left_channels.size(); ++channel) {
        for (std::size_t index = 0; index < kCoordinates; ++index) {
            assert(close(
                (*left_channels[channel])[index],
                (*right_channels[channel])[index]));
        }
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
    bg_docking_rigid_refinement *rust_refiner =
        create_refiner(rust_context, context_descriptor);
    bg_docking_rigid_refinement *hip_refiner =
        create_refiner(hip_context, context_descriptor);

    bg_backend observed_backend = BG_BACKEND_CPP_CPU_REFERENCE;
    assert(
        bg_docking_rigid_refinement_get_backend(
            hip_refiner, &observed_backend) == BG_STATUS_OK);
    assert(observed_backend == backend);

    context_fixture.receptor_x.fill(-1'000.0);
    context_fixture.receptor_radii.fill(99.0);
    context_fixture.ligand_radii.fill(99.0);

    BatchFixture batch_fixture;
    const auto batch = batch_fixture.descriptor();
    OutputStorage rust_output;
    OutputStorage hip_output;
    OutputStorage repeated_hip_output;
    auto rust_descriptor = rust_output.descriptor();
    auto hip_descriptor = hip_output.descriptor();
    auto repeated_hip_descriptor = repeated_hip_output.descriptor();
    assert(
        bg_docking_rigid_refinement_fixed64(
            rust_context, rust_refiner, &batch, &rust_descriptor) ==
        BG_STATUS_OK);
    assert(
        bg_docking_rigid_refinement_fixed64(
            hip_context, hip_refiner, &batch, &hip_descriptor) ==
        BG_STATUS_OK);
    assert(
        bg_docking_rigid_refinement_fixed64(
            hip_context, hip_refiner, &batch, &repeated_hip_descriptor) ==
        BG_STATUS_OK);
    assert(hip_descriptor.row_count == kSlots);
    assert(hip_descriptor.coordinate_count == kCoordinates);
    assert(hip_descriptor.molecular_execution_authorized == UINT8_C(0));
    assert(
        hip_descriptor.existing_rank_auto_change_authorized == UINT8_C(0));
    assert(hip_descriptor.customer_pose_emission_authorized == UINT8_C(0));
    assert(hip_descriptor.production_claim_authorized == UINT8_C(0));
    assert_parity(rust_output, hip_output);
    assert_parity(hip_output, repeated_hip_output);

    bg_docking_rigid_refinement_destroy(hip_refiner);
    bg_docking_rigid_refinement_destroy(rust_refiner);
    bg_context_destroy(hip_context);
    bg_context_destroy(rust_context);
}

void test_v3_rotation_path_when_device_is_available(bg_backend backend) {
    uint8_t available = UINT8_C(0);
    assert(bg_backend_is_available(backend, 0, &available) == BG_STATUS_OK);
    if (available == UINT8_C(0)) {
        return;
    }

    const std::array<double, 2> receptor_x = {-2.0, 2.0};
    const std::array<double, 2> receptor_y = {0.2, -0.2};
    const std::array<double, 2> receptor_z = {0.0, 0.0};
    const std::array<double, 2> receptor_radii = {1.7, 1.7};
    const std::array<double, kAtoms> ligand_radii = {1.7, 1.7, 1.7};
    bg_docking_rigid_refinement_context_soa_v1 context_descriptor{};
    assert(
        bg_docking_rigid_refinement_context_soa_v1_init(
            &context_descriptor) == BG_STATUS_OK);
    context_descriptor.receptor_atom_count = receptor_x.size();
    context_descriptor.ligand_atom_count = ligand_radii.size();
    context_descriptor.receptor_x_angstrom = receptor_x.data();
    context_descriptor.receptor_y_angstrom = receptor_y.data();
    context_descriptor.receptor_z_angstrom = receptor_z.data();
    context_descriptor.receptor_vdw_radius_angstrom = receptor_radii.data();
    context_descriptor.ligand_vdw_radius_angstrom = ligand_radii.data();
    context_descriptor.pocket_radius_angstrom = 8.0;
    context_descriptor.v3.v2.maximum_step_angstrom =
        context_descriptor.v3.v2.minimum_step_angstrom;
    context_descriptor.v3.v2.maximum_total_translation_angstrom =
        context_descriptor.v3.v2.minimum_step_angstrom;

    std::array<bg_docking_rigid_refinement_candidate_mode, kSlots> modes{};
    std::array<uint64_t, kSlots> max_steps{};
    std::array<double, kCoordinates> x{};
    std::array<double, kCoordinates> y{};
    std::array<double, kCoordinates> z{};
    modes.fill(BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_INACTIVE);
    max_steps.fill(UINT64_C(8));
    modes[0] =
        BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V3_TRANSLATION_ROTATION;
    for (std::size_t slot = 0; slot < kSlots; ++slot) {
        x[slot * kAtoms] = -2.0;
        x[slot * kAtoms + 1] = 0.0;
        x[slot * kAtoms + 2] = 2.0;
    }
    bg_docking_rigid_refinement_candidate_batch_soa_v1 batch{};
    assert(
        bg_docking_rigid_refinement_candidate_batch_soa_v1_init(&batch) ==
        BG_STATUS_OK);
    batch.ligand_atom_count = kAtoms;
    batch.candidate_mode = modes.data();
    batch.max_steps = max_steps.data();
    batch.x_angstrom = x.data();
    batch.y_angstrom = y.data();
    batch.z_angstrom = z.data();

    bg_context *rust_context = create_context(BG_BACKEND_RUST_CPU);
    bg_context *hip_context = create_context(backend);
    bg_docking_rigid_refinement *rust_refiner =
        create_refiner(rust_context, context_descriptor);
    bg_docking_rigid_refinement *hip_refiner =
        create_refiner(hip_context, context_descriptor);
    OutputStorage rust_output;
    OutputStorage hip_output;
    auto rust_descriptor = rust_output.descriptor();
    auto hip_descriptor = hip_output.descriptor();
    assert(
        bg_docking_rigid_refinement_fixed64(
            rust_context, rust_refiner, &batch, &rust_descriptor) ==
        BG_STATUS_OK);
    assert(
        bg_docking_rigid_refinement_fixed64(
            hip_context, hip_refiner, &batch, &hip_descriptor) ==
        BG_STATUS_OK);
    assert(rust_output.rows[0].selected.accepted_rotation_steps > 0);
    assert_parity(rust_output, hip_output);

    bg_docking_rigid_refinement_destroy(hip_refiner);
    bg_docking_rigid_refinement_destroy(rust_refiner);
    bg_context_destroy(hip_context);
    bg_context_destroy(rust_context);
}

void test_fixed64_total_pair_work_is_bounded_before_provider_execution() {
    auto run = [](std::size_t receptor_count, bg_status expected_status) {
        std::vector<double> receptor_x(receptor_count, 1'000.0);
        std::vector<double> receptor_y(receptor_count, 0.0);
        std::vector<double> receptor_z(receptor_count, 0.0);
        std::vector<double> receptor_radii(receptor_count, 1.7);
        const std::array<double, kAtoms> ligand_radii = {1.6, 1.6, 1.6};
        bg_docking_rigid_refinement_context_soa_v1 descriptor{};
        assert(
            bg_docking_rigid_refinement_context_soa_v1_init(&descriptor) ==
            BG_STATUS_OK);
        descriptor.receptor_atom_count = receptor_count;
        descriptor.ligand_atom_count = ligand_radii.size();
        descriptor.receptor_x_angstrom = receptor_x.data();
        descriptor.receptor_y_angstrom = receptor_y.data();
        descriptor.receptor_z_angstrom = receptor_z.data();
        descriptor.receptor_vdw_radius_angstrom = receptor_radii.data();
        descriptor.ligand_vdw_radius_angstrom = ligand_radii.data();
        descriptor.pocket_radius_angstrom = 8.0;

        bg_context *context = create_context(BG_BACKEND_CPP_CPU_REFERENCE);
        bg_docking_rigid_refinement *refiner =
            create_refiner(context, descriptor);
        BatchFixture batch_fixture;
        batch_fixture.modes.fill(
            BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V3_LANE);
        batch_fixture.max_steps.fill(UINT64_C(128));
        batch_fixture.x.fill(0.0);
        batch_fixture.y.fill(0.0);
        batch_fixture.z.fill(0.0);
        const auto batch = batch_fixture.descriptor();
        OutputStorage output_storage(53.0);
        auto output = output_storage.descriptor();
        const bg_status observed = bg_docking_rigid_refinement_fixed64(
            context, refiner, &batch, &output);
        assert(observed == expected_status);
        if (expected_status == BG_STATUS_CAPACITY_OVERFLOW) {
            assert(output.row_count == 0);
            assert(output.coordinate_count == 0);
            assert(output_storage.rows[0].slot_index == UINT32_MAX);
            assert(output_storage.selected_x[0] == 53.0);
        } else {
            assert(output.row_count == kSlots);
            assert(output.coordinate_count == kCoordinates);
        }
        bg_docking_rigid_refinement_destroy(refiner);
        bg_context_destroy(context);
    };

    run(181, BG_STATUS_OK);
    run(182, BG_STATUS_CAPACITY_OVERFLOW);
}

}  // namespace

int main() {
    ContextFixture context_fixture;
    const auto descriptor = context_fixture.descriptor();
    bg_context *cpp_context = create_context(BG_BACKEND_CPP_CPU_REFERENCE);
    bg_context *rust_context = create_context(BG_BACKEND_RUST_CPU);

    const auto receptor_x_before = context_fixture.receptor_x;
    auto **const channel_alias =
        reinterpret_cast<bg_docking_rigid_refinement **>(
            context_fixture.receptor_x.data());
    assert(
        bg_docking_rigid_refinement_create(
            cpp_context, &descriptor, channel_alias) ==
        BG_STATUS_INVALID_ARGUMENT);
    assert(context_fixture.receptor_x == receptor_x_before);

    auto descriptor_copy = descriptor;
    const auto descriptor_before = descriptor_copy;
    auto **const descriptor_alias =
        reinterpret_cast<bg_docking_rigid_refinement **>(&descriptor_copy);
    assert(
        bg_docking_rigid_refinement_create(
            cpp_context, &descriptor_copy, descriptor_alias) ==
        BG_STATUS_INVALID_ARGUMENT);
    assert(
        std::memcmp(
            &descriptor_copy, &descriptor_before, sizeof(descriptor_copy)) ==
        0);

    bg_docking_rigid_refinement *cpp_refiner =
        create_refiner(cpp_context, descriptor);
    bg_docking_rigid_refinement *rust_refiner =
        create_refiner(rust_context, descriptor);
    assert(
        bg_docking_rigid_refinement_get_backend(
            cpp_refiner, reinterpret_cast<bg_backend *>(cpp_refiner)) ==
        BG_STATUS_INVALID_ARGUMENT);

    context_fixture.receptor_x.fill(-1'000.0);
    context_fixture.receptor_radii.fill(99.0);
    context_fixture.ligand_radii.fill(99.0);

    BatchFixture batch_fixture;
    const auto batch = batch_fixture.descriptor();
    OutputStorage cpp_output;
    OutputStorage rust_output;
    auto cpp_descriptor = cpp_output.descriptor();
    auto rust_descriptor = rust_output.descriptor();
    assert(
        bg_docking_rigid_refinement_fixed64(
            cpp_context, cpp_refiner, &batch, &cpp_descriptor) ==
        BG_STATUS_OK);
    assert(
        bg_docking_rigid_refinement_fixed64(
            rust_context, rust_refiner, &batch, &rust_descriptor) ==
        BG_STATUS_OK);
    assert(cpp_descriptor.row_count == kSlots);
    assert(cpp_descriptor.coordinate_count == kCoordinates);
    assert(cpp_descriptor.molecular_execution_authorized == 0);
    assert(cpp_descriptor.existing_rank_auto_change_authorized == 0);
    assert(cpp_descriptor.customer_pose_emission_authorized == 0);
    assert(cpp_descriptor.production_claim_authorized == 0);
    assert(cpp_output.rows[0].status == BG_DOCKING_RIGID_REFINEMENT_ROW_REFINED);
    assert(
        cpp_output.rows[3].selected_profile ==
        BG_DOCKING_RIGID_REFINEMENT_PROFILE_V6_CLEARANCE_V4);
    assert(cpp_output.rows[3].comparison_v2.available == 1);
    assert(cpp_output.rows[3].baseline_v3.available == 1);
    assert(cpp_output.rows[3].clearance_v4.available == 1);
    assert(
        cpp_output.rows[4].failure_code ==
        BG_DOCKING_RIGID_REFINEMENT_FAILURE_INVALID_INPUT);
    assert(
        cpp_output.rows[5].failure_code ==
        BG_DOCKING_RIGID_REFINEMENT_FAILURE_NONFINITE_INPUT);
    assert(
        cpp_output.rows[6].failure_code ==
        BG_DOCKING_RIGID_REFINEMENT_FAILURE_UPSTREAM_NOT_ELIGIBLE);
    assert_parity(cpp_output, rust_output);

    OutputStorage transactional(41.0);
    auto invalid_output = transactional.descriptor();
    invalid_output.row_capacity = kSlots - 1;
    assert(
        bg_docking_rigid_refinement_fixed64(
            cpp_context, cpp_refiner, &batch, &invalid_output) ==
        BG_STATUS_INVALID_ARGUMENT);
    assert(transactional.rows[0].slot_index == UINT32_MAX);
    assert(transactional.selected_x[0] == 41.0);

    OutputStorage descriptor_alias_storage(43.0);
    auto descriptor_alias_output = descriptor_alias_storage.descriptor();
    descriptor_alias_output.rows =
        reinterpret_cast<bg_docking_rigid_refinement_row_v1 *>(
            &descriptor_alias_output);
    const auto descriptor_alias_before = descriptor_alias_output;
    assert(
        bg_docking_rigid_refinement_fixed64(
            cpp_context,
            cpp_refiner,
            &batch,
            &descriptor_alias_output) == BG_STATUS_INVALID_ARGUMENT);
    assert(
        std::memcmp(
            &descriptor_alias_output,
            &descriptor_alias_before,
            sizeof(descriptor_alias_output)) == 0);
    assert(descriptor_alias_storage.selected_x[0] == 43.0);

    OutputStorage batch_alias_storage(47.0);
    auto batch_alias_output = batch_alias_storage.descriptor();
    auto batch_alias = batch;
    batch_alias_output.rows =
        reinterpret_cast<bg_docking_rigid_refinement_row_v1 *>(
            &batch_alias);
    const auto batch_alias_before = batch_alias;
    assert(
        bg_docking_rigid_refinement_fixed64(
            cpp_context,
            cpp_refiner,
            &batch_alias,
            &batch_alias_output) == BG_STATUS_INVALID_ARGUMENT);
    assert(
        std::memcmp(
            &batch_alias, &batch_alias_before, sizeof(batch_alias)) == 0);
    assert(batch_alias_storage.selected_x[0] == 47.0);

    OutputStorage handle_alias_storage(49.0);
    auto handle_alias_output = handle_alias_storage.descriptor();
    handle_alias_output.rows =
        reinterpret_cast<bg_docking_rigid_refinement_row_v1 *>(cpp_refiner);
    assert(
        bg_docking_rigid_refinement_fixed64(
            cpp_context,
            cpp_refiner,
            &batch,
            &handle_alias_output) == BG_STATUS_INVALID_ARGUMENT);
    bg_backend observed_backend = BG_BACKEND_AUTO;
    assert(
        bg_docking_rigid_refinement_get_backend(
            cpp_refiner, &observed_backend) == BG_STATUS_OK);
    assert(observed_backend == BG_BACKEND_CPP_CPU_REFERENCE);

    handle_alias_output.rows =
        reinterpret_cast<bg_docking_rigid_refinement_row_v1 *>(cpp_context);
    assert(
        bg_docking_rigid_refinement_fixed64(
            cpp_context,
            cpp_refiner,
            &batch,
            &handle_alias_output) == BG_STATUS_INVALID_ARGUMENT);
    bg_backend context_backend = BG_BACKEND_AUTO;
    assert(
        bg_context_get_backend(cpp_context, &context_backend) == BG_STATUS_OK);
    assert(context_backend == BG_BACKEND_CPP_CPU_REFERENCE);

    assert(
        bg_docking_rigid_refinement_fixed64(
            cpp_context, rust_refiner, &batch, &cpp_descriptor) ==
        BG_STATUS_INVALID_ARGUMENT);

    bg_docking_rigid_refinement_destroy(rust_refiner);
    bg_docking_rigid_refinement_destroy(cpp_refiner);
    bg_context_destroy(rust_context);
    bg_context_destroy(cpp_context);
    test_hip_parity_when_device_is_available(BG_BACKEND_HIP_SAFE);
    test_hip_parity_when_device_is_available(BG_BACKEND_HIP_FAST);
    test_v3_rotation_path_when_device_is_available(BG_BACKEND_HIP_SAFE);
    test_v3_rotation_path_when_device_is_available(BG_BACKEND_HIP_FAST);
    test_fixed64_total_pair_work_is_bounded_before_provider_execution();
    return 0;
}
