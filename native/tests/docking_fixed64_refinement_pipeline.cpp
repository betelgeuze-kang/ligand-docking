#include "betelgeuze/engine.h"

#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>

namespace {

constexpr std::size_t kSlots = BG_DOCKING_FIXED64_CANDIDATE_COUNT;
constexpr std::size_t kAtoms = 4;
constexpr std::size_t kCoordinates = kSlots * kAtoms;
constexpr std::size_t kMoves =
    kSlots * BG_DOCKING_TORSION_V7_MAX_MOVES;

struct Fixture final {
    std::array<double, 4> receptor_x = {5.0, 6.0, 5.5, 7.0};
    std::array<double, 4> receptor_y = {0.0, 2.0, -2.0, 1.0};
    std::array<double, 4> receptor_z = {0.0, 0.0, 1.0, -1.0};
    std::array<double, 4> receptor_charge = {-0.5, 0.2, 0.3, 0.0};
    std::array<double, 4> receptor_radius = {1.2, 1.2, 1.2, 1.2};
    std::array<double, 4> receptor_epsilon = {0.2, 0.18, 0.05, 0.25};
    std::array<uint8_t, 4> receptor_hydrophobic = {0, 0, 0, 1};
    std::array<uint8_t, 4> receptor_acceptor = {1, 0, 0, 0};

    std::array<double, 4> ligand_x = {0.0, 0.0, 1.0, 1.0};
    std::array<double, 4> ligand_y = {1.0, 0.0, 0.0, 1.0};
    std::array<double, 4> ligand_z = {0.0, 0.0, 0.0, 1.0};
    std::array<double, 4> ligand_charge = {0.2, 0.25, -0.45, 0.0};
    std::array<double, 4> ligand_radius = {0.7, 0.7, 0.7, 0.7};
    std::array<double, 4> ligand_epsilon = {0.18, 0.05, 0.2, 0.25};
    std::array<uint8_t, 4> ligand_hydrophobic = {0, 0, 0, 1};
    std::array<uint8_t, 4> ligand_acceptor = {0, 0, 1, 1};

    std::array<uint64_t, 1> receptor_donor = {0};
    std::array<uint64_t, 1> receptor_hydrogen = {1};
    std::array<uint64_t, 1> ligand_donor = {0};
    std::array<uint64_t, 1> ligand_hydrogen = {1};
    std::array<uint64_t, 3> bond_i = {0, 1, 2};
    std::array<uint64_t, 3> bond_j = {1, 2, 3};
    std::array<uint64_t, 3> exclusion_i = {0, 1, 2};
    std::array<uint64_t, 3> exclusion_j = {1, 2, 3};
    std::array<uint64_t, 1> scorer_rotor_i = {0};
    std::array<uint64_t, 1> scorer_rotor_j = {1};
    std::array<uint64_t, 1> scorer_rotor_k = {2};
    std::array<uint64_t, 1> scorer_rotor_l = {3};
    std::array<int32_t, kAtoms> parent = {-1, 0, 1, 2};
    std::array<uint64_t, 1> rotatable_child = {2};
    std::array<uint64_t, 3> internal_i = {0, 0, 1};
    std::array<uint64_t, 3> internal_j = {2, 3, 3};

    std::array<bg_docking_rigid_refinement_candidate_mode, kSlots> modes{};
    std::array<uint64_t, kSlots> rigid_steps{};
    std::array<uint8_t, kSlots> torsion_eligible{};
    std::array<uint64_t, kSlots> torsion_steps{};
    std::array<double, kCoordinates> source_x{};
    std::array<double, kCoordinates> source_y{};
    std::array<double, kCoordinates> source_z{};
    std::array<double, kCoordinates> baseline_angles{};
    std::array<double, kSlots> quaternion_x{};
    std::array<double, kSlots> quaternion_y{};
    std::array<double, kSlots> quaternion_z{};
    std::array<double, kSlots> quaternion_w{};

    Fixture() {
        modes.fill(BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_INACTIVE);
        quaternion_w.fill(1.0);
        for (std::size_t slot = 0; slot < kSlots; ++slot) {
            const double translation = slot == 1 ? 0.2 : 0.0;
            for (std::size_t atom = 0; atom < kAtoms; ++atom) {
                const std::size_t index = slot * kAtoms + atom;
                source_x[index] = ligand_x[atom] + translation;
                source_y[index] = ligand_y[atom];
                source_z[index] = ligand_z[atom];
            }
        }
        modes[0] = BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION;
        modes[1] =
            BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V3_LANE;
        modes[2] =
            BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V3_TRANSLATION_ROTATION;
        modes[3] =
            BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V2_LANE;
        rigid_steps[0] = 4;
        rigid_steps[1] = 4;
        rigid_steps[2] = 4;
        rigid_steps[3] = 4;
        torsion_eligible[1] = UINT8_C(1);
        torsion_steps[1] = 4;
        torsion_eligible[3] = UINT8_C(1);
        torsion_steps[3] = 4;
        baseline_angles[3 * kAtoms] =
            std::numeric_limits<double>::quiet_NaN();
    }

    bg_docking_scorer_v1_context_soa_v1 scorer() const {
        bg_docking_scorer_v1_context_soa_v1 value{};
        assert(bg_docking_scorer_v1_context_soa_v1_init(&value) == BG_STATUS_OK);
        value.receptor_atom_count = receptor_x.size();
        value.ligand_atom_count = ligand_x.size();
        value.receptor_x_angstrom = receptor_x.data();
        value.receptor_y_angstrom = receptor_y.data();
        value.receptor_z_angstrom = receptor_z.data();
        value.receptor_charge_elementary = receptor_charge.data();
        value.receptor_vdw_radius_angstrom = receptor_radius.data();
        value.receptor_epsilon_kcal_per_mol = receptor_epsilon.data();
        value.receptor_hydrophobic = receptor_hydrophobic.data();
        value.receptor_acceptor = receptor_acceptor.data();
        value.ligand_reference_x_angstrom = ligand_x.data();
        value.ligand_reference_y_angstrom = ligand_y.data();
        value.ligand_reference_z_angstrom = ligand_z.data();
        value.ligand_charge_elementary = ligand_charge.data();
        value.ligand_vdw_radius_angstrom = ligand_radius.data();
        value.ligand_epsilon_kcal_per_mol = ligand_epsilon.data();
        value.ligand_hydrophobic = ligand_hydrophobic.data();
        value.ligand_acceptor = ligand_acceptor.data();
        value.receptor_donor_count = receptor_donor.size();
        value.receptor_donor_atom_index = receptor_donor.data();
        value.receptor_hydrogen_atom_index = receptor_hydrogen.data();
        value.ligand_donor_count = ligand_donor.size();
        value.ligand_donor_atom_index = ligand_donor.data();
        value.ligand_hydrogen_atom_index = ligand_hydrogen.data();
        value.ligand_exclusion_count = exclusion_i.size();
        value.ligand_exclusion_atom_i = exclusion_i.data();
        value.ligand_exclusion_atom_j = exclusion_j.data();
        value.rotor_count = scorer_rotor_i.size();
        value.rotor_atom_i = scorer_rotor_i.data();
        value.rotor_atom_j = scorer_rotor_j.data();
        value.rotor_atom_k = scorer_rotor_k.data();
        value.rotor_atom_l = scorer_rotor_l.data();
        value.pocket_center_angstrom[0] = 0.5;
        value.pocket_center_angstrom[1] = 0.5;
        value.pocket_center_angstrom[2] = 0.5;
        value.pocket_radius_angstrom = 20.0;
        std::fill_n(value.authority_input_receipt_sha256, 32, UINT8_C(0x11));
        std::fill_n(value.receptor_system_sha256, 32, UINT8_C(0x22));
        std::fill_n(value.ligand_system_sha256, 32, UINT8_C(0x33));
        std::fill_n(value.backend_receipt_sha256, 32, UINT8_C(0x44));
        return value;
    }

    bg_docking_pose_validity_context_soa_v1 validity() const {
        bg_docking_pose_validity_context_soa_v1 value{};
        assert(bg_docking_pose_validity_context_soa_v1_init(&value) == BG_STATUS_OK);
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
        value.pocket_center_angstrom[0] = 0.5;
        value.pocket_center_angstrom[1] = 0.5;
        value.pocket_center_angstrom[2] = 0.5;
        value.pocket_radius_angstrom = 20.0;
        std::fill_n(value.authority_input_receipt_sha256, 32, UINT8_C(0x11));
        std::fill_n(value.receptor_system_sha256, 32, UINT8_C(0x22));
        std::fill_n(value.ligand_system_sha256, 32, UINT8_C(0x33));
        std::fill_n(value.scorer_context_receipt_sha256, 32, UINT8_C(0x44));
        std::fill_n(value.backend_receipt_sha256, 32, UINT8_C(0x55));
        std::fill_n(value.contact_policy_sha256, 32, UINT8_C(0x66));
        return value;
    }

    bg_docking_rigid_refinement_context_soa_v1 rigid() const {
        bg_docking_rigid_refinement_context_soa_v1 value{};
        assert(bg_docking_rigid_refinement_context_soa_v1_init(&value) == BG_STATUS_OK);
        value.receptor_atom_count = receptor_x.size();
        value.ligand_atom_count = ligand_x.size();
        value.receptor_x_angstrom = receptor_x.data();
        value.receptor_y_angstrom = receptor_y.data();
        value.receptor_z_angstrom = receptor_z.data();
        value.receptor_vdw_radius_angstrom = receptor_radius.data();
        value.ligand_vdw_radius_angstrom = ligand_radius.data();
        value.pocket_center_angstrom[0] = 0.5;
        value.pocket_center_angstrom[1] = 0.5;
        value.pocket_center_angstrom[2] = 0.5;
        value.pocket_radius_angstrom = 20.0;
        return value;
    }

    bg_docking_torsion_v7_context_soa_v1 torsion() const {
        bg_docking_torsion_v7_context_soa_v1 value{};
        assert(bg_docking_torsion_v7_context_soa_v1_init(&value) == BG_STATUS_OK);
        value.receptor_atom_count = receptor_x.size();
        value.ligand_atom_count = ligand_x.size();
        value.rotor_count = rotatable_child.size();
        value.internal_pair_count = internal_i.size();
        value.receptor_x_angstrom = receptor_x.data();
        value.receptor_y_angstrom = receptor_y.data();
        value.receptor_z_angstrom = receptor_z.data();
        value.receptor_vdw_radius_angstrom = receptor_radius.data();
        value.ligand_vdw_radius_angstrom = ligand_radius.data();
        value.pocket_center_angstrom[0] = 0.5;
        value.pocket_center_angstrom[1] = 0.5;
        value.pocket_center_angstrom[2] = 0.5;
        value.parent_atom_index = parent.data();
        value.rotatable_child_atom_index = rotatable_child.data();
        value.internal_pair_atom_i = internal_i.data();
        value.internal_pair_atom_j = internal_j.data();
        value.minimum_selected_final_receptor_penalty = 0.0;
        value.maximum_selected_final_receptor_penalty = 1'000'000.0;
        return value;
    }

    bg_docking_fixed64_refinement_input_v1 input() const {
        bg_docking_fixed64_refinement_input_v1 value{};
        assert(bg_docking_fixed64_refinement_input_v1_init(&value) == BG_STATUS_OK);
        value.ligand_atom_count = kAtoms;
        value.rmsd_threshold_angstrom = 1.5;
        value.candidate_mode = modes.data();
        value.rigid_max_steps = rigid_steps.data();
        value.proposal_is_torsion_eligible = torsion_eligible.data();
        value.torsion_max_steps = torsion_steps.data();
        value.source_x_angstrom = source_x.data();
        value.source_y_angstrom = source_y.data();
        value.source_z_angstrom = source_z.data();
        value.baseline_torsion_angles_radians = baseline_angles.data();
        value.source_quaternion_x = quaternion_x.data();
        value.source_quaternion_y = quaternion_y.data();
        value.source_quaternion_z = quaternion_z.data();
        value.source_quaternion_w = quaternion_w.data();
        return value;
    }
};

struct Result final {
    std::array<bg_docking_rigid_refinement_row_v1, kSlots> rigid_rows{};
    std::array<std::array<double, kCoordinates>, 12> rigid_coordinates{};
    std::array<bg_docking_torsion_v7_row_v1, kSlots> torsion_rows{};
    std::array<bg_docking_torsion_v7_move_v1, kMoves> torsion_moves{};
    std::array<std::array<double, kCoordinates>, 8> torsion_coordinates{};
    std::array<bg_docking_scorer_v1_row_v1, kSlots> scorer_rows{};
    std::array<bg_docking_pose_validity_row_v1, kSlots> validity_rows{};
    std::array<bg_docking_stable_top_k_row_v1, kSlots> ranking_rows{};
    std::array<uint32_t, kSlots> primary{};
    std::array<uint32_t, kSlots> valid{};
    std::array<bg_docking_rmsd_cluster_row_v1, kSlots> cluster_rows{};
    std::array<uint32_t, kSlots> representatives{};
    std::array<uint32_t, BG_DOCKING_STABLE_TOP_K_LIMIT> cluster_top_k{};
    std::array<bg_docking_fixed64_refinement_row_v1, kSlots> pipeline_rows{};
    std::array<std::array<double, kCoordinates>, 3> final_coordinates{};
    std::array<std::array<double, kSlots>, 4> final_quaternions{};
    uint64_t rigid_count = 0;
    uint64_t torsion_count = 0;
    uint64_t scorer_count = 0;
    uint64_t validity_count = 0;
    uint64_t ranking_count = 0;
    uint64_t cluster_count = 0;
    uint64_t pipeline_count = 0;
    uint64_t primary_count = 0;
    uint64_t valid_count = 0;
    uint64_t representative_count = 0;
    uint64_t cluster_top_k_count = 0;
};

bg_context *create_context(bg_backend backend) {
    bg_context_options options{};
    assert(bg_context_options_init(&options) == BG_STATUS_OK);
    options.backend = backend;
    bg_context *context = nullptr;
    assert(bg_context_create(&options, &context) == BG_STATUS_OK);
    return context;
}

bg_docking_fixed64_refinement_pipeline_v1 *create_pipeline(
    bg_context *context,
    const Fixture &fixture) {
    auto rigid = fixture.rigid();
    auto torsion = fixture.torsion();
    auto scorer = fixture.scorer();
    auto validity = fixture.validity();
    bg_docking_fixed64_refinement_pipeline_v1 *pipeline = nullptr;
    assert(
        bg_docking_fixed64_refinement_pipeline_v1_create(
            context,
            &rigid,
            &torsion,
            &scorer,
            &validity,
            &pipeline) == BG_STATUS_OK);
    assert(pipeline != nullptr);
    return pipeline;
}

bg_status run_into(
    bg_context *context,
    bg_docking_fixed64_refinement_pipeline_v1 *pipeline,
    const Fixture &fixture,
    Result *result,
    bool overlap_final_x = false,
    bool overlap_cluster_rows = false) {
    auto input = fixture.input();
    bg_docking_rigid_refinement_output_v1 rigid{};
    bg_docking_torsion_v7_output_v1 torsion{};
    bg_docking_scorer_v1_output_v1 scorer{};
    bg_docking_pose_validity_output_v1 validity{};
    bg_docking_stable_top_k_output_v1 ranking{};
    bg_docking_rmsd_cluster_output_v1 cluster{};
    bg_docking_fixed64_refinement_output_v1 output{};
    assert(bg_docking_rigid_refinement_output_v1_init(&rigid) == BG_STATUS_OK);
    assert(bg_docking_torsion_v7_output_v1_init(&torsion) == BG_STATUS_OK);
    assert(bg_docking_scorer_v1_output_v1_init(&scorer) == BG_STATUS_OK);
    assert(bg_docking_pose_validity_output_v1_init(&validity) == BG_STATUS_OK);
    assert(bg_docking_stable_top_k_output_v1_init(&ranking) == BG_STATUS_OK);
    assert(bg_docking_rmsd_cluster_output_v1_init(&cluster) == BG_STATUS_OK);
    assert(bg_docking_fixed64_refinement_output_v1_init(&output) == BG_STATUS_OK);
    rigid.row_capacity = kSlots;
    rigid.coordinate_capacity = kCoordinates;
    rigid.rows = result->rigid_rows.data();
    rigid.selected_x_angstrom = result->rigid_coordinates[0].data();
    rigid.selected_y_angstrom = result->rigid_coordinates[1].data();
    rigid.selected_z_angstrom = result->rigid_coordinates[2].data();
    rigid.comparison_v2_x_angstrom = result->rigid_coordinates[3].data();
    rigid.comparison_v2_y_angstrom = result->rigid_coordinates[4].data();
    rigid.comparison_v2_z_angstrom = result->rigid_coordinates[5].data();
    rigid.baseline_v3_x_angstrom = result->rigid_coordinates[6].data();
    rigid.baseline_v3_y_angstrom = result->rigid_coordinates[7].data();
    rigid.baseline_v3_z_angstrom = result->rigid_coordinates[8].data();
    rigid.clearance_v4_x_angstrom = result->rigid_coordinates[9].data();
    rigid.clearance_v4_y_angstrom = result->rigid_coordinates[10].data();
    rigid.clearance_v4_z_angstrom = result->rigid_coordinates[11].data();
    torsion.row_capacity = kSlots;
    torsion.move_capacity = kMoves;
    torsion.coordinate_capacity = kCoordinates;
    torsion.rows = result->torsion_rows.data();
    torsion.moves = result->torsion_moves.data();
    torsion.optimized_x_angstrom = result->torsion_coordinates[0].data();
    torsion.optimized_y_angstrom = result->torsion_coordinates[1].data();
    torsion.optimized_z_angstrom = result->torsion_coordinates[2].data();
    torsion.optimized_torsion_angles_radians = result->torsion_coordinates[3].data();
    torsion.final_x_angstrom = result->torsion_coordinates[4].data();
    torsion.final_y_angstrom = result->torsion_coordinates[5].data();
    torsion.final_z_angstrom = result->torsion_coordinates[6].data();
    torsion.final_torsion_angles_radians = result->torsion_coordinates[7].data();
    scorer.row_capacity = kSlots;
    scorer.rows = result->scorer_rows.data();
    validity.row_capacity = kSlots;
    validity.rows = result->validity_rows.data();
    ranking.row_capacity = kSlots;
    ranking.primary_index_capacity = kSlots;
    ranking.valid_index_capacity = kSlots;
    ranking.rows = result->ranking_rows.data();
    ranking.primary_slot_indices = result->primary.data();
    ranking.valid_slot_indices = result->valid.data();
    cluster.row_capacity = kSlots;
    cluster.representative_index_capacity = kSlots;
    cluster.top_k_index_capacity = BG_DOCKING_STABLE_TOP_K_LIMIT;
    cluster.rows = overlap_cluster_rows
        ? reinterpret_cast<bg_docking_rmsd_cluster_row_v1 *>(
              result->ranking_rows.data())
        : result->cluster_rows.data();
    cluster.representative_slot_indices = result->representatives.data();
    cluster.top_k_slot_indices = result->cluster_top_k.data();
    output.row_capacity = kSlots;
    output.coordinate_capacity = kCoordinates;
    output.quaternion_capacity = kSlots;
    output.rows = result->pipeline_rows.data();
    output.final_x_angstrom = overlap_final_x
        ? const_cast<double *>(fixture.source_x.data())
        : result->final_coordinates[0].data();
    output.final_y_angstrom = result->final_coordinates[1].data();
    output.final_z_angstrom = result->final_coordinates[2].data();
    output.final_quaternion_x = result->final_quaternions[0].data();
    output.final_quaternion_y = result->final_quaternions[1].data();
    output.final_quaternion_z = result->final_quaternions[2].data();
    output.final_quaternion_w = result->final_quaternions[3].data();
    const bg_status status = bg_docking_fixed64_refinement_pipeline_v1_run(
        context,
        pipeline,
        &input,
        &rigid,
        &torsion,
        &scorer,
        &validity,
        &ranking,
        &cluster,
        &output);
    result->rigid_count = rigid.row_count;
    result->torsion_count = torsion.row_count;
    result->scorer_count = scorer.row_count;
    result->validity_count = validity.row_count;
    result->ranking_count = ranking.row_count;
    result->cluster_count = cluster.row_count;
    result->pipeline_count = output.row_count;
    result->primary_count = ranking.primary_index_count;
    result->valid_count = ranking.valid_index_count;
    result->representative_count = cluster.representative_index_count;
    result->cluster_top_k_count = cluster.top_k_index_count;
    assert(output.molecular_execution_authorized == UINT8_C(0));
    assert(output.reservation_authorized == UINT8_C(0));
    assert(output.benchmark_execution_authorized == UINT8_C(0));
    assert(output.existing_rank_auto_change_authorized == UINT8_C(0));
    assert(output.customer_pose_emission_authorized == UINT8_C(0));
    assert(output.production_claim_authorized == UINT8_C(0));
    assert(cluster.existing_rank_auto_change_authorized == UINT8_C(0));
    assert(cluster.customer_pose_emission_authorized == UINT8_C(0));
    assert(cluster.production_claim_authorized == UINT8_C(0));
    return status;
}

Result run(bg_backend backend, const Fixture &fixture) {
    bg_context *context = create_context(backend);
    auto *pipeline = create_pipeline(context, fixture);
    bg_backend observed = BG_BACKEND_AUTO;
    assert(
        bg_docking_fixed64_refinement_pipeline_v1_get_backend(
            pipeline, &observed) == BG_STATUS_OK);
    assert(observed == backend);
    Result result{};
    assert(run_into(context, pipeline, fixture, &result) == BG_STATUS_OK);
    bg_docking_fixed64_refinement_pipeline_v1_destroy(pipeline);
    bg_context_destroy(context);
    return result;
}

bool close(double left, double right, double tolerance) {
    const double scale = std::max({1.0, std::abs(left), std::abs(right)});
    return std::abs(left - right) <= tolerance * scale;
}

void assert_parity(const Result &left, const Result &right, double tolerance) {
    assert(left.rigid_count == right.rigid_count);
    assert(left.torsion_count == right.torsion_count);
    assert(left.scorer_count == right.scorer_count);
    assert(left.validity_count == right.validity_count);
    assert(left.ranking_count == right.ranking_count);
    assert(left.cluster_count == right.cluster_count);
    assert(left.pipeline_count == right.pipeline_count);
    assert(left.primary_count == right.primary_count);
    assert(left.valid_count == right.valid_count);
    assert(left.representative_count == right.representative_count);
    assert(left.cluster_top_k_count == right.cluster_top_k_count);
    for (std::size_t slot = 0; slot < kSlots; ++slot) {
        assert(left.pipeline_rows[slot].slot_index == slot);
        assert(left.pipeline_rows[slot].status == right.pipeline_rows[slot].status);
        assert(
            left.pipeline_rows[slot].failure_stage ==
            right.pipeline_rows[slot].failure_stage);
        assert(
            left.pipeline_rows[slot].coordinate_origin ==
            right.pipeline_rows[slot].coordinate_origin);
        assert(
            left.pipeline_rows[slot].downstream_candidate_state ==
            right.pipeline_rows[slot].downstream_candidate_state);
        assert(
            std::memcmp(
                left.pipeline_rows[slot].coordinate_sha256,
                right.pipeline_rows[slot].coordinate_sha256,
                32) == 0);
        assert(left.cluster_rows[slot].status == right.cluster_rows[slot].status);
        assert(
            left.cluster_rows[slot].cluster_eligible ==
            right.cluster_rows[slot].cluster_eligible);
        assert(
            left.cluster_rows[slot].representative ==
            right.cluster_rows[slot].representative);
        assert(
            left.cluster_rows[slot].stable_valid_rank ==
            right.cluster_rows[slot].stable_valid_rank);
        assert(
            left.cluster_rows[slot].cluster_id ==
            right.cluster_rows[slot].cluster_id);
        assert(
            left.cluster_rows[slot].representative_slot_index ==
            right.cluster_rows[slot].representative_slot_index);
        assert(
            left.cluster_rows[slot].cluster_rank ==
            right.cluster_rows[slot].cluster_rank);
        assert(
            left.cluster_rows[slot].top_k_rank ==
            right.cluster_rows[slot].top_k_rank);
        assert(close(
            left.cluster_rows[slot].direct_rmsd_to_representative_angstrom,
            right.cluster_rows[slot].direct_rmsd_to_representative_angstrom,
            tolerance));
        assert(
            std::memcmp(
                left.cluster_rows[slot].coordinate_sha256,
                right.cluster_rows[slot].coordinate_sha256,
                32) == 0);
        for (std::size_t axis = 0; axis < 4; ++axis) {
            assert(close(
                left.final_quaternions[axis][slot],
                right.final_quaternions[axis][slot],
                tolerance));
        }
    }
    for (std::size_t index = 0; index < left.representative_count; ++index) {
        assert(left.representatives[index] == right.representatives[index]);
    }
    for (std::size_t index = 0; index < left.cluster_top_k_count; ++index) {
        assert(left.cluster_top_k[index] == right.cluster_top_k[index]);
    }
    for (std::size_t axis = 0; axis < 3; ++axis) {
        for (std::size_t index = 0; index < kCoordinates; ++index) {
            assert(close(
                left.final_coordinates[axis][index],
                right.final_coordinates[axis][index],
                tolerance));
        }
    }
}

void test_fixed64_flow_and_cpu_parity() {
    const Fixture fixture;
    const Result cpp = run(BG_BACKEND_CPP_CPU_REFERENCE, fixture);
    const Result rust = run(BG_BACKEND_RUST_CPU, fixture);
    assert(cpp.pipeline_count == kSlots);
    assert(cpp.rigid_count == kSlots);
    assert(cpp.torsion_count == kSlots);
    assert(cpp.scorer_count == kSlots);
    assert(cpp.validity_count == kSlots);
    assert(cpp.ranking_count == kSlots);
    assert(cpp.cluster_count == kSlots);
    assert(cpp.cluster_rows[3].status ==
           BG_DOCKING_RMSD_CLUSTER_ROW_UPSTREAM_NOT_VALID);
    assert(cpp.pipeline_rows[0].status ==
           BG_DOCKING_FIXED64_REFINEMENT_ROW_COORDINATE_READY);
    assert(cpp.pipeline_rows[0].coordinate_origin ==
           BG_DOCKING_FIXED64_REFINEMENT_COORDINATE_RIGID_SELECTED);
    assert(cpp.pipeline_rows[1].status ==
           BG_DOCKING_FIXED64_REFINEMENT_ROW_COORDINATE_READY);
    assert(cpp.pipeline_rows[1].coordinate_origin ==
           BG_DOCKING_FIXED64_REFINEMENT_COORDINATE_TORSION_V7_FINAL);
    assert(cpp.pipeline_rows[1].torsion_v7_applicable == UINT8_C(1));
    assert(cpp.pipeline_rows[2].status ==
           BG_DOCKING_FIXED64_REFINEMENT_ROW_COORDINATE_READY);
    assert(cpp.rigid_rows[3].status ==
           BG_DOCKING_RIGID_REFINEMENT_ROW_REFINED);
    assert(cpp.pipeline_rows[3].status ==
           BG_DOCKING_FIXED64_REFINEMENT_ROW_TYPED_FAILURE);
    assert(cpp.pipeline_rows[3].failure_stage ==
           BG_DOCKING_FIXED64_REFINEMENT_FAILURE_STAGE_TORSION_V7);
    assert(cpp.pipeline_rows[3].torsion_v7_failure_code ==
           BG_DOCKING_TORSION_V7_FAILURE_INVALID_INPUT);
    assert(cpp.pipeline_rows[3].coordinate_available == UINT8_C(0));
    assert(cpp.scorer_rows[3].status ==
           BG_DOCKING_SCORER_V1_ROW_TYPED_FAILURE);
    assert(cpp.scorer_rows[3].failure_code ==
           BG_DOCKING_SCORER_V1_FAILURE_UPSTREAM_NOT_ADMITTED);
    assert(cpp.validity_rows[3].status ==
           BG_DOCKING_POSE_VALIDITY_ROW_UPSTREAM_SCORER_FAILURE);
    assert(cpp.ranking_rows[3].rank_eligible == UINT8_C(0));
    assert(cpp.ranking_rows[3].valid_rank_eligible == UINT8_C(0));
    for (const uint8_t byte : cpp.pipeline_rows[3].coordinate_sha256) {
        assert(byte == UINT8_C(0));
    }
    for (std::size_t slot = 4; slot < kSlots; ++slot) {
        assert(cpp.pipeline_rows[slot].status ==
               BG_DOCKING_FIXED64_REFINEMENT_ROW_TYPED_FAILURE);
        assert(cpp.pipeline_rows[slot].failure_stage ==
               BG_DOCKING_FIXED64_REFINEMENT_FAILURE_STAGE_RIGID);
        assert(cpp.pipeline_rows[slot].coordinate_available == UINT8_C(0));
    }
    assert_parity(cpp, rust, 4.0e-12);
}

void test_cross_wiring_and_transactionality_fail_closed() {
    Fixture fixture;
    bg_context *context = create_context(BG_BACKEND_CPP_CPU_REFERENCE);
    auto rigid = fixture.rigid();
    auto torsion = fixture.torsion();
    auto scorer = fixture.scorer();
    auto validity = fixture.validity();
    std::array<double, 4> cross_wired_receptor = fixture.receptor_x;
    cross_wired_receptor[0] += 0.25;
    torsion.receptor_x_angstrom = cross_wired_receptor.data();
    bg_docking_fixed64_refinement_pipeline_v1 *rejected = nullptr;
    assert(
        bg_docking_fixed64_refinement_pipeline_v1_create(
            context,
            &rigid,
            &torsion,
            &scorer,
            &validity,
            &rejected) == BG_STATUS_INVALID_ARGUMENT);
    assert(rejected == nullptr);

    torsion = fixture.torsion();
    const double receptor_x_before = fixture.receptor_x[0];
    auto **channel_alias =
        reinterpret_cast<bg_docking_fixed64_refinement_pipeline_v1 **>(
            fixture.receptor_x.data());
    assert(
        bg_docking_fixed64_refinement_pipeline_v1_create(
            context,
            &rigid,
            &torsion,
            &scorer,
            &validity,
            channel_alias) == BG_STATUS_INVALID_ARGUMENT);
    assert(fixture.receptor_x[0] == receptor_x_before);

    const auto rigid_before = rigid;
    auto **descriptor_alias =
        reinterpret_cast<bg_docking_fixed64_refinement_pipeline_v1 **>(&rigid);
    assert(
        bg_docking_fixed64_refinement_pipeline_v1_create(
            context,
            &rigid,
            &torsion,
            &scorer,
            &validity,
            descriptor_alias) == BG_STATUS_INVALID_ARGUMENT);
    assert(std::memcmp(&rigid, &rigid_before, sizeof(rigid)) == 0);

    alignas(void *) std::array<std::byte, sizeof(void *) + 1> misaligned{};
    auto **misaligned_output =
        reinterpret_cast<bg_docking_fixed64_refinement_pipeline_v1 **>(
            misaligned.data() + 1);
    assert(
        bg_docking_fixed64_refinement_pipeline_v1_create(
            context,
            &rigid,
            &torsion,
            &scorer,
            &validity,
            misaligned_output) == BG_STATUS_INVALID_ARGUMENT);

    auto *pipeline = create_pipeline(context, fixture);
    assert(
        bg_docking_fixed64_refinement_pipeline_v1_get_backend(
            pipeline, reinterpret_cast<bg_backend *>(pipeline)) ==
        BG_STATUS_INVALID_ARGUMENT);
    bg_backend observed = BG_BACKEND_AUTO;
    assert(
        bg_docking_fixed64_refinement_pipeline_v1_get_backend(
            pipeline, &observed) == BG_STATUS_OK);
    assert(observed == BG_BACKEND_CPP_CPU_REFERENCE);
    Result result{};
    result.pipeline_rows[0].slot_index = UINT32_MAX;
    result.cluster_rows[0].slot_index = UINT32_MAX;
    result.final_coordinates[0].fill(91.0);
    assert(
        run_into(context, pipeline, fixture, &result, true) ==
        BG_STATUS_INVALID_ARGUMENT);
    assert(result.rigid_count == 0);
    assert(result.torsion_count == 0);
    assert(result.scorer_count == 0);
    assert(result.validity_count == 0);
    assert(result.ranking_count == 0);
    assert(result.cluster_count == 0);
    assert(result.pipeline_count == 0);
    assert(result.representative_count == 0);
    assert(result.cluster_top_k_count == 0);
    assert(result.pipeline_rows[0].slot_index == UINT32_MAX);
    assert(result.cluster_rows[0].slot_index == UINT32_MAX);
    assert(result.final_coordinates[0][0] == 91.0);

    Result cluster_overlap{};
    cluster_overlap.ranking_rows[0].slot_index = UINT32_MAX;
    assert(
        run_into(
            context,
            pipeline,
            fixture,
            &cluster_overlap,
            false,
            true) == BG_STATUS_INVALID_ARGUMENT);
    assert(cluster_overlap.ranking_count == 0);
    assert(cluster_overlap.cluster_count == 0);
    assert(cluster_overlap.pipeline_count == 0);
    assert(cluster_overlap.ranking_rows[0].slot_index == UINT32_MAX);
    bg_docking_fixed64_refinement_pipeline_v1_destroy(pipeline);
    bg_context_destroy(context);
}

void test_success_zeroes_index_tails() {
    const Fixture fixture;
    bg_context *context = create_context(BG_BACKEND_CPP_CPU_REFERENCE);
    auto *pipeline = create_pipeline(context, fixture);
    Result result{};
    result.primary.fill(UINT32_MAX);
    result.valid.fill(UINT32_MAX);
    result.representatives.fill(UINT32_MAX);
    result.cluster_top_k.fill(UINT32_MAX);
    assert(run_into(context, pipeline, fixture, &result) == BG_STATUS_OK);
    assert(result.primary_count < result.primary.size());
    assert(result.valid_count < result.valid.size());
    assert(result.representative_count < result.representatives.size());
    assert(result.cluster_top_k_count < result.cluster_top_k.size());
    for (std::size_t index = result.primary_count; index < result.primary.size();
         ++index) {
        assert(result.primary[index] == 0U);
    }
    for (std::size_t index = result.valid_count; index < result.valid.size();
         ++index) {
        assert(result.valid[index] == 0U);
    }
    for (std::size_t index = result.representative_count;
         index < result.representatives.size();
         ++index) {
        assert(result.representatives[index] == 0U);
    }
    for (std::size_t index = result.cluster_top_k_count;
         index < result.cluster_top_k.size();
         ++index) {
        assert(result.cluster_top_k[index] == 0U);
    }
    bg_docking_fixed64_refinement_pipeline_v1_destroy(pipeline);
    bg_context_destroy(context);
}

void test_optional_hip_parity() {
    const Fixture fixture;
    const Result reference = run(BG_BACKEND_CPP_CPU_REFERENCE, fixture);
    for (const bg_backend backend : {BG_BACKEND_HIP_SAFE, BG_BACKEND_HIP_FAST}) {
        uint8_t available = UINT8_C(0);
        assert(bg_backend_is_available(backend, 0, &available) == BG_STATUS_OK);
        if (available == UINT8_C(1)) {
            assert_parity(run(backend, fixture), reference, 8.0e-11);
        }
    }
}

}  // namespace

int main() {
    test_fixed64_flow_and_cpu_parity();
    test_cross_wiring_and_transactionality_fail_closed();
    test_success_zeroes_index_tails();
    test_optional_hip_parity();
    return 0;
}
