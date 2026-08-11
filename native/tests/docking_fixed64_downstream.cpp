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
constexpr std::size_t kLigandAtoms = 4;
constexpr std::array<uint8_t, 32> kSlotZeroCoordinateSha256 = {
    UINT8_C(0xab), UINT8_C(0xf8), UINT8_C(0xaa), UINT8_C(0x81),
    UINT8_C(0x88), UINT8_C(0xd9), UINT8_C(0x5d), UINT8_C(0x99),
    UINT8_C(0x3d), UINT8_C(0x1a), UINT8_C(0x97), UINT8_C(0x08),
    UINT8_C(0xc7), UINT8_C(0x75), UINT8_C(0xe5), UINT8_C(0x72),
    UINT8_C(0xee), UINT8_C(0x8b), UINT8_C(0xe6), UINT8_C(0xa8),
    UINT8_C(0xbf), UINT8_C(0xfb), UINT8_C(0xcf), UINT8_C(0x7b),
    UINT8_C(0xf4), UINT8_C(0x0f), UINT8_C(0xa0), UINT8_C(0x9b),
    UINT8_C(0x56), UINT8_C(0x3c), UINT8_C(0x1d), UINT8_C(0x8a),
};

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
    std::array<uint64_t, 1> rotor_i = {0};
    std::array<uint64_t, 1> rotor_j = {1};
    std::array<uint64_t, 1> rotor_k = {2};
    std::array<uint64_t, 1> rotor_l = {3};

    std::array<bg_docking_scorer_v1_candidate_state, kSlots> states{};
    std::array<double, kSlots> quaternion_x{};
    std::array<double, kSlots> quaternion_y{};
    std::array<double, kSlots> quaternion_z{};
    std::array<double, kSlots> quaternion_w{};
    std::array<double, kSlots * kLigandAtoms> candidate_x{};
    std::array<double, kSlots * kLigandAtoms> candidate_y{};
    std::array<double, kSlots * kLigandAtoms> candidate_z{};

    Fixture() {
        states.fill(BG_DOCKING_SCORER_V1_CANDIDATE_INACTIVE);
        quaternion_w.fill(1.0);
        for (std::size_t slot = 0; slot < kSlots; ++slot) {
            const double translation = slot == 1 ? 0.25 : 0.0;
            for (std::size_t atom = 0; atom < kLigandAtoms; ++atom) {
                const std::size_t offset = slot * kLigandAtoms + atom;
                candidate_x[offset] = ligand_x[atom] + translation;
                candidate_y[offset] = ligand_y[atom];
                candidate_z[offset] = ligand_z[atom];
            }
        }
        states[0] = BG_DOCKING_SCORER_V1_CANDIDATE_ACTIVE;
        states[1] = BG_DOCKING_SCORER_V1_CANDIDATE_ACTIVE;
        states[2] = BG_DOCKING_SCORER_V1_CANDIDATE_ACTIVE;
        candidate_x[2 * kLigandAtoms] =
            std::numeric_limits<double>::quiet_NaN();
    }

    bg_docking_scorer_v1_context_soa_v1 scorer_descriptor(
        uint64_t maximum_receptor_pairs = 0) const {
        bg_docking_scorer_v1_context_soa_v1 value{};
        assert(
            bg_docking_scorer_v1_context_soa_v1_init(&value) ==
            BG_STATUS_OK);
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
        value.rotor_count = rotor_i.size();
        value.rotor_atom_i = rotor_i.data();
        value.rotor_atom_j = rotor_j.data();
        value.rotor_atom_k = rotor_k.data();
        value.rotor_atom_l = rotor_l.data();
        value.pocket_center_angstrom[0] = 0.5;
        value.pocket_center_angstrom[1] = 0.5;
        value.pocket_center_angstrom[2] = 0.5;
        value.pocket_radius_angstrom = 20.0;
        if (maximum_receptor_pairs != 0) {
            value.max_receptor_candidate_pairs = maximum_receptor_pairs;
        }
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

    bg_docking_pose_validity_context_soa_v1 validity_descriptor() const {
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
        value.pocket_center_angstrom[0] = 0.5;
        value.pocket_center_angstrom[1] = 0.5;
        value.pocket_center_angstrom[2] = 0.5;
        value.pocket_radius_angstrom = 20.0;
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

    bg_docking_scorer_v1_candidate_batch_soa_v1 batch() const {
        bg_docking_scorer_v1_candidate_batch_soa_v1 value{};
        assert(
            bg_docking_scorer_v1_candidate_batch_soa_v1_init(&value) ==
            BG_STATUS_OK);
        value.ligand_atom_count = kLigandAtoms;
        value.candidate_state = states.data();
        value.x_angstrom = candidate_x.data();
        value.y_angstrom = candidate_y.data();
        value.z_angstrom = candidate_z.data();
        return value;
    }
};

struct Result final {
    std::array<bg_docking_scorer_v1_row_v1, kSlots> scorer{};
    std::array<bg_docking_pose_validity_row_v1, kSlots> validity{};
    std::array<bg_docking_stable_top_k_row_v1, kSlots> ranking{};
    std::array<uint32_t, kSlots> primary{};
    std::array<uint32_t, kSlots> valid{};
    uint64_t scorer_count = 0;
    uint64_t validity_count = 0;
    uint64_t ranking_count = 0;
    uint64_t primary_count = 0;
    uint64_t valid_count = 0;
    uint8_t existing_rank_auto_change_authorized = UINT8_C(1);
    uint8_t customer_pose_emission_authorized = UINT8_C(1);
    uint8_t production_claim_authorized = UINT8_C(1);
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

bg_docking_fixed64_downstream_v1 *create_pipeline(
    bg_context *context,
    const Fixture &fixture,
    uint64_t maximum_receptor_pairs = 0) {
    const auto scorer =
        fixture.scorer_descriptor(maximum_receptor_pairs);
    const auto validity = fixture.validity_descriptor();
    bg_docking_fixed64_downstream_v1 *pipeline = nullptr;
    assert(
        bg_docking_fixed64_downstream_v1_create(
            context, &scorer, &validity, &pipeline) == BG_STATUS_OK);
    assert(pipeline != nullptr);
    return pipeline;
}

Result run(
    bg_context *context,
    bg_docking_fixed64_downstream_v1 *pipeline,
    const Fixture &fixture) {
    const auto batch = fixture.batch();
    Result result{};
    bg_docking_scorer_v1_output_v1 scorer{};
    bg_docking_pose_validity_output_v1 validity{};
    bg_docking_stable_top_k_output_v1 ranking{};
    assert(bg_docking_scorer_v1_output_v1_init(&scorer) == BG_STATUS_OK);
    assert(
        bg_docking_pose_validity_output_v1_init(&validity) ==
        BG_STATUS_OK);
    assert(
        bg_docking_stable_top_k_output_v1_init(&ranking) ==
        BG_STATUS_OK);
    scorer.row_capacity = kSlots;
    scorer.rows = result.scorer.data();
    validity.row_capacity = kSlots;
    validity.rows = result.validity.data();
    ranking.row_capacity = kSlots;
    ranking.primary_index_capacity = kSlots;
    ranking.valid_index_capacity = kSlots;
    ranking.rows = result.ranking.data();
    ranking.primary_slot_indices = result.primary.data();
    ranking.valid_slot_indices = result.valid.data();
    ranking.existing_rank_auto_change_authorized = UINT8_C(1);
    ranking.customer_pose_emission_authorized = UINT8_C(1);
    ranking.production_claim_authorized = UINT8_C(1);
    assert(
        bg_docking_fixed64_downstream_v1_run(
            context,
            pipeline,
            &batch,
            fixture.quaternion_x.data(),
            fixture.quaternion_y.data(),
            fixture.quaternion_z.data(),
            fixture.quaternion_w.data(),
            &scorer,
            &validity,
            &ranking) == BG_STATUS_OK);
    result.scorer_count = scorer.row_count;
    result.validity_count = validity.row_count;
    result.ranking_count = ranking.row_count;
    result.primary_count = ranking.primary_index_count;
    result.valid_count = ranking.valid_index_count;
    result.existing_rank_auto_change_authorized =
        ranking.existing_rank_auto_change_authorized;
    result.customer_pose_emission_authorized =
        ranking.customer_pose_emission_authorized;
    result.production_claim_authorized =
        ranking.production_claim_authorized;
    return result;
}

bool close_with_tolerance(double left, double right, double tolerance) {
    const double scale = std::max({1.0, std::abs(left), std::abs(right)});
    return std::abs(left - right) <= tolerance * scale;
}

void assert_scorer_parity(
    const bg_docking_scorer_v1_row_v1 &left,
    const bg_docking_scorer_v1_row_v1 &right,
    double tolerance) {
    assert(left.slot_index == right.slot_index);
    assert(left.status == right.status);
    assert(left.failure_code == right.failure_code);
    assert(
        left.receptor_candidate_pair_count ==
        right.receptor_candidate_pair_count);
    assert(left.ligand_pair_count == right.ligand_pair_count);
    assert(left.hbond_count == right.hbond_count);
    assert(
        left.hydrophobic_contact_count ==
        right.hydrophobic_contact_count);
    assert(left.buried_polar_count == right.buried_polar_count);
    for (std::size_t term = 0;
         term < BG_DOCKING_SCORER_V1_TERM_COUNT;
         ++term) {
        assert(close_with_tolerance(
            left.weighted_terms[term], right.weighted_terms[term], tolerance));
    }
    assert(close_with_tolerance(
        left.total_score, right.total_score, tolerance));
}

void assert_validity_parity(
    const bg_docking_pose_validity_row_v1 &left,
    const bg_docking_pose_validity_row_v1 &right,
    double tolerance) {
    assert(left.slot_index == right.slot_index);
    assert(left.status == right.status);
    assert(left.failure_code == right.failure_code);
    assert(
        left.upstream_scorer_failure_code ==
        right.upstream_scorer_failure_code);
    assert(left.passed_check_mask == right.passed_check_mask);
    assert(left.blocker_mask == right.blocker_mask);
    assert(left.observed_count == right.observed_count);
    assert(left.atom_count == right.atom_count);
    assert(
        left.evaluated_ligand_nonbonded_pair_count ==
        right.evaluated_ligand_nonbonded_pair_count);
    assert(
        left.excluded_ligand_pair_count ==
        right.excluded_ligand_pair_count);
    assert(
        left.evaluated_receptor_ligand_pair_count ==
        right.evaluated_receptor_ligand_pair_count);
    assert(
        left.declared_chirality_center_count ==
        right.declared_chirality_center_count);
    assert(
        left.element_vdw_ligand_pair_count ==
        right.element_vdw_ligand_pair_count);
    assert(
        left.element_vdw_ligand_severe_overlap_count ==
        right.element_vdw_ligand_severe_overlap_count);
    assert(
        left.element_vdw_receptor_candidate_pair_count ==
        right.element_vdw_receptor_candidate_pair_count);
    assert(
        left.element_vdw_receptor_full_cartesian_pair_count ==
        right.element_vdw_receptor_full_cartesian_pair_count);
    assert(
        left.element_vdw_receptor_cell_count ==
        right.element_vdw_receptor_cell_count);
    assert(
        left.element_vdw_receptor_severe_overlap_count ==
        right.element_vdw_receptor_severe_overlap_count);
    const std::array<std::pair<double, double>, 11> measurements = {{
        {left.rotation_orthogonality_max_error,
         right.rotation_orthogonality_max_error},
        {left.rotation_determinant, right.rotation_determinant},
        {left.max_bond_length_delta_angstrom,
         right.max_bond_length_delta_angstrom},
        {left.minimum_ligand_nonbonded_distance_angstrom,
         right.minimum_ligand_nonbonded_distance_angstrom},
        {left.minimum_receptor_ligand_distance_angstrom,
         right.minimum_receptor_ligand_distance_angstrom},
        {left.minimum_declared_chiral_volume,
         right.minimum_declared_chiral_volume},
        {left.maximum_pocket_center_distance_angstrom,
         right.maximum_pocket_center_distance_angstrom},
        {left.element_vdw_ligand_minimum_distance_angstrom,
         right.element_vdw_ligand_minimum_distance_angstrom},
        {left.element_vdw_ligand_minimum_ratio,
         right.element_vdw_ligand_minimum_ratio},
        {left.element_vdw_receptor_minimum_distance_angstrom,
         right.element_vdw_receptor_minimum_distance_angstrom},
        {left.element_vdw_receptor_minimum_ratio,
         right.element_vdw_receptor_minimum_ratio},
    }};
    for (const auto &[observed, expected] : measurements) {
        assert(close_with_tolerance(observed, expected, tolerance));
    }
}

void assert_result_parity(
    const Result &observed,
    const Result &reference,
    double tolerance) {
    assert(observed.scorer_count == reference.scorer_count);
    assert(observed.validity_count == reference.validity_count);
    assert(observed.ranking_count == reference.ranking_count);
    assert(observed.primary_count == reference.primary_count);
    assert(observed.valid_count == reference.valid_count);
    assert(observed.primary == reference.primary);
    assert(observed.valid == reference.valid);
    for (std::size_t slot = 0; slot < kSlots; ++slot) {
        assert_scorer_parity(
            observed.scorer[slot], reference.scorer[slot], tolerance);
        assert_validity_parity(
            observed.validity[slot], reference.validity[slot], tolerance);
        const auto &left = observed.ranking[slot];
        const auto &right = reference.ranking[slot];
        assert(left.slot_index == right.slot_index);
        assert(left.rank_eligible == right.rank_eligible);
        assert(left.valid_rank_eligible == right.valid_rank_eligible);
        assert(left.stable_rank == right.stable_rank);
        assert(left.stable_valid_rank == right.stable_valid_rank);
        assert(close_with_tolerance(
            left.total_score, right.total_score, tolerance));
        assert(
            std::memcmp(
                left.coordinate_sha256,
                right.coordinate_sha256,
                sizeof(left.coordinate_sha256)) == 0);
    }
    assert(observed.existing_rank_auto_change_authorized == UINT8_C(0));
    assert(observed.customer_pose_emission_authorized == UINT8_C(0));
    assert(observed.production_claim_authorized == UINT8_C(0));
}

void assert_result_exact(const Result &left, const Result &right) {
    assert(
        std::memcmp(
            left.scorer.data(), right.scorer.data(), sizeof(left.scorer)) ==
        0);
    assert(
        std::memcmp(
            left.validity.data(),
            right.validity.data(),
            sizeof(left.validity)) == 0);
    assert(
        std::memcmp(
            left.ranking.data(),
            right.ranking.data(),
            sizeof(left.ranking)) == 0);
    assert(left.primary == right.primary);
    assert(left.valid == right.valid);
    assert(left.scorer_count == right.scorer_count);
    assert(left.validity_count == right.validity_count);
    assert(left.ranking_count == right.ranking_count);
    assert(left.primary_count == right.primary_count);
    assert(left.valid_count == right.valid_count);
    assert(
        left.existing_rank_auto_change_authorized ==
        right.existing_rank_auto_change_authorized);
    assert(
        left.customer_pose_emission_authorized ==
        right.customer_pose_emission_authorized);
    assert(
        left.production_claim_authorized ==
        right.production_claim_authorized);
}

void test_cpu_composition_repeat_stability_and_fixed64_evidence() {
    const Fixture fixture;
    bg_context *cpp_context = create_context(BG_BACKEND_CPP_CPU_REFERENCE);
    bg_context *rust_context = create_context(BG_BACKEND_RUST_CPU);
    bg_docking_fixed64_downstream_v1 *cpp_pipeline =
        create_pipeline(cpp_context, fixture);
    bg_docking_fixed64_downstream_v1 *rust_pipeline =
        create_pipeline(rust_context, fixture);

    bg_backend backend = BG_BACKEND_AUTO;
    assert(
        bg_docking_fixed64_downstream_v1_get_backend(
            cpp_pipeline, &backend) == BG_STATUS_OK);
    assert(backend == BG_BACKEND_CPP_CPU_REFERENCE);
    assert(
        bg_docking_fixed64_downstream_v1_get_backend(
            rust_pipeline, &backend) == BG_STATUS_OK);
    assert(backend == BG_BACKEND_RUST_CPU);

    const Result cpp = run(cpp_context, cpp_pipeline, fixture);
    const Result rust = run(rust_context, rust_pipeline, fixture);
    const Result rust_repeat = run(rust_context, rust_pipeline, fixture);
    assert_result_exact(rust, rust_repeat);
    assert_result_parity(cpp, rust, 2.0e-12);
    assert(rust.scorer_count == kSlots);
    assert(rust.validity_count == kSlots);
    assert(rust.ranking_count == kSlots);
    assert(rust.primary_count == 2);
    assert(rust.valid_count == 2);
    assert(rust.scorer[0].status == BG_DOCKING_SCORER_V1_ROW_SCORED);
    assert(rust.scorer[1].status == BG_DOCKING_SCORER_V1_ROW_SCORED);
    assert(
        rust.scorer[2].failure_code ==
        BG_DOCKING_SCORER_V1_FAILURE_INVALID_CANDIDATE_COORDINATES);
    assert(
        rust.validity[2].status ==
        BG_DOCKING_POSE_VALIDITY_ROW_UPSTREAM_SCORER_FAILURE);
    assert(
        rust.validity[2].upstream_scorer_failure_code ==
        rust.scorer[2].failure_code);
    assert(rust.ranking[2].rank_eligible == UINT8_C(0));
    assert(
        rust.scorer[3].failure_code ==
        BG_DOCKING_SCORER_V1_FAILURE_UPSTREAM_NOT_ADMITTED);
    assert(rust.ranking[3].rank_eligible == UINT8_C(0));
    assert(std::any_of(
        std::begin(rust.ranking[0].coordinate_sha256),
        std::end(rust.ranking[0].coordinate_sha256),
        [](uint8_t value) { return value != UINT8_C(0); }));
    assert(
        std::memcmp(
            rust.ranking[0].coordinate_sha256,
            kSlotZeroCoordinateSha256.data(),
            kSlotZeroCoordinateSha256.size()) == 0);

    bg_docking_fixed64_downstream_v1_destroy(cpp_pipeline);
    bg_docking_fixed64_downstream_v1_destroy(rust_pipeline);
    bg_context_destroy(cpp_context);
    bg_context_destroy(rust_context);
}

void test_cross_wiring_rejected_and_outputs_are_transactional() {
    Fixture fixture;
    bg_context *context = create_context(BG_BACKEND_RUST_CPU);
    const auto scorer_descriptor = fixture.scorer_descriptor();
    auto validity_descriptor = fixture.validity_descriptor();
    auto **context_alias =
        reinterpret_cast<bg_docking_fixed64_downstream_v1 **>(context);
    assert(
        bg_docking_fixed64_downstream_v1_create(
            context,
            &scorer_descriptor,
            &validity_descriptor,
            context_alias) == BG_STATUS_INVALID_ARGUMENT);
    bg_backend context_backend = BG_BACKEND_AUTO;
    assert(
        bg_context_get_backend(context, &context_backend) == BG_STATUS_OK);
    assert(context_backend == BG_BACKEND_RUST_CPU);

    auto cross_wired_receptor = fixture.receptor_x;
    cross_wired_receptor[0] += 0.01;
    validity_descriptor.receptor_x_angstrom = cross_wired_receptor.data();
    bg_docking_fixed64_downstream_v1 *rejected =
        reinterpret_cast<bg_docking_fixed64_downstream_v1 *>(
            static_cast<uintptr_t>(1));
    assert(
        bg_docking_fixed64_downstream_v1_create(
            context,
            &scorer_descriptor,
            &validity_descriptor,
            &rejected) == BG_STATUS_INVALID_ARGUMENT);
    assert(rejected == nullptr);

    bg_docking_fixed64_downstream_v1 *pipeline =
        create_pipeline(context, fixture);
    auto invalid_states = fixture.states;
    invalid_states[0] = 99;
    auto batch = fixture.batch();
    batch.candidate_state = invalid_states.data();

    std::array<bg_docking_scorer_v1_row_v1, kSlots> scorer_rows{};
    std::array<bg_docking_pose_validity_row_v1, kSlots> validity_rows{};
    std::array<bg_docking_stable_top_k_row_v1, kSlots> ranking_rows{};
    std::array<uint32_t, kSlots> primary{};
    std::array<uint32_t, kSlots> valid{};
    std::memset(scorer_rows.data(), 0x5a, sizeof(scorer_rows));
    std::memset(validity_rows.data(), 0x5a, sizeof(validity_rows));
    std::memset(ranking_rows.data(), 0x5a, sizeof(ranking_rows));
    primary.fill(UINT32_C(0x5a5a5a5a));
    valid.fill(UINT32_C(0x5a5a5a5a));
    const auto scorer_before = scorer_rows;
    const auto validity_before = validity_rows;
    const auto ranking_before = ranking_rows;
    const auto primary_before = primary;
    const auto valid_before = valid;

    bg_docking_scorer_v1_output_v1 scorer_output{};
    bg_docking_pose_validity_output_v1 validity_output{};
    bg_docking_stable_top_k_output_v1 ranking_output{};
    assert(
        bg_docking_scorer_v1_output_v1_init(&scorer_output) ==
        BG_STATUS_OK);
    assert(
        bg_docking_pose_validity_output_v1_init(&validity_output) ==
        BG_STATUS_OK);
    assert(
        bg_docking_stable_top_k_output_v1_init(&ranking_output) ==
        BG_STATUS_OK);
    scorer_output.row_capacity = kSlots;
    scorer_output.row_count = 17;
    scorer_output.rows = scorer_rows.data();
    validity_output.row_capacity = kSlots;
    validity_output.row_count = 18;
    validity_output.rows = validity_rows.data();
    ranking_output.row_capacity = kSlots;
    ranking_output.row_count = 19;
    ranking_output.primary_index_capacity = kSlots;
    ranking_output.primary_index_count = 20;
    ranking_output.valid_index_capacity = kSlots;
    ranking_output.valid_index_count = 21;
    ranking_output.rows = ranking_rows.data();
    ranking_output.primary_slot_indices = primary.data();
    ranking_output.valid_slot_indices = valid.data();
    ranking_output.existing_rank_auto_change_authorized = UINT8_C(1);
    ranking_output.customer_pose_emission_authorized = UINT8_C(1);
    ranking_output.production_claim_authorized = UINT8_C(1);
    assert(
        bg_docking_fixed64_downstream_v1_run(
            context,
            pipeline,
            &batch,
            fixture.quaternion_x.data(),
            fixture.quaternion_y.data(),
            fixture.quaternion_z.data(),
            fixture.quaternion_w.data(),
            &scorer_output,
            &validity_output,
            &ranking_output) == BG_STATUS_INVALID_ARGUMENT);
    assert(
        std::memcmp(
            scorer_rows.data(),
            scorer_before.data(),
            sizeof(scorer_rows)) == 0);
    assert(
        std::memcmp(
            validity_rows.data(),
            validity_before.data(),
            sizeof(validity_rows)) == 0);
    assert(
        std::memcmp(
            ranking_rows.data(),
            ranking_before.data(),
            sizeof(ranking_rows)) == 0);
    assert(primary == primary_before);
    assert(valid == valid_before);
    assert(scorer_output.row_count == 17);
    assert(validity_output.row_count == 18);
    assert(ranking_output.row_count == 19);
    assert(ranking_output.primary_index_count == 20);
    assert(ranking_output.valid_index_count == 21);
    assert(
        ranking_output.existing_rank_auto_change_authorized ==
        UINT8_C(1));
    assert(ranking_output.customer_pose_emission_authorized == UINT8_C(1));
    assert(ranking_output.production_claim_authorized == UINT8_C(1));

    const auto valid_batch = fixture.batch();
    auto *const scorer_rows_pointer = scorer_output.rows;
    scorer_output.rows =
        reinterpret_cast<bg_docking_scorer_v1_row_v1 *>(pipeline);
    assert(
        bg_docking_fixed64_downstream_v1_run(
            context,
            pipeline,
            &valid_batch,
            fixture.quaternion_x.data(),
            fixture.quaternion_y.data(),
            fixture.quaternion_z.data(),
            fixture.quaternion_w.data(),
            &scorer_output,
            &validity_output,
            &ranking_output) == BG_STATUS_INVALID_ARGUMENT);
    assert(scorer_output.row_count == 17);
    bg_backend pipeline_backend = BG_BACKEND_AUTO;
    assert(
        bg_docking_fixed64_downstream_v1_get_backend(
            pipeline, &pipeline_backend) == BG_STATUS_OK);
    assert(pipeline_backend == BG_BACKEND_RUST_CPU);
    scorer_output.rows = scorer_rows_pointer;

    validity_output.rows =
        reinterpret_cast<bg_docking_pose_validity_row_v1 *>(
            &scorer_output);
    assert(
        bg_docking_fixed64_downstream_v1_run(
            context,
            pipeline,
            &valid_batch,
            fixture.quaternion_x.data(),
            fixture.quaternion_y.data(),
            fixture.quaternion_z.data(),
            fixture.quaternion_w.data(),
            &scorer_output,
            &validity_output,
            &ranking_output) == BG_STATUS_INVALID_ARGUMENT);
    assert(scorer_output.row_count == 17);
    assert(ranking_output.row_count == 19);

    bg_docking_fixed64_downstream_v1_destroy(pipeline);
    bg_context_destroy(context);
}

void test_capacity_failure_is_candidate_local_and_preserves_pairs() {
    const Fixture fixture;
    bg_context *cpp_context = create_context(BG_BACKEND_CPP_CPU_REFERENCE);
    bg_context *rust_context = create_context(BG_BACKEND_RUST_CPU);
    bg_docking_fixed64_downstream_v1 *cpp_pipeline =
        create_pipeline(cpp_context, fixture, 1);
    bg_docking_fixed64_downstream_v1 *rust_pipeline =
        create_pipeline(rust_context, fixture, 1);

    const Result cpp = run(cpp_context, cpp_pipeline, fixture);
    const Result rust = run(rust_context, rust_pipeline, fixture);
    assert_result_parity(cpp, rust, 2.0e-12);
    assert(rust.scorer_count == kSlots);
    assert(rust.validity_count == kSlots);
    assert(rust.ranking_count == kSlots);
    assert(rust.primary_count == 0);
    assert(rust.valid_count == 0);
    for (const std::size_t slot : {std::size_t{0}, std::size_t{1}}) {
        assert(
            rust.scorer[slot].failure_code ==
            BG_DOCKING_SCORER_V1_FAILURE_RECEPTOR_PAIR_CAPACITY);
        assert(rust.scorer[slot].receptor_candidate_pair_count == 2);
        assert(rust.scorer[slot].ligand_pair_count == 0);
        assert(
            rust.validity[slot].status ==
            BG_DOCKING_POSE_VALIDITY_ROW_UPSTREAM_SCORER_FAILURE);
        assert(
            rust.validity[slot].upstream_scorer_failure_code ==
            BG_DOCKING_SCORER_V1_FAILURE_RECEPTOR_PAIR_CAPACITY);
        assert(rust.ranking[slot].rank_eligible == UINT8_C(0));
        assert(rust.ranking[slot].stable_rank == 0);
    }

    bg_docking_fixed64_downstream_v1_destroy(cpp_pipeline);
    bg_docking_fixed64_downstream_v1_destroy(rust_pipeline);
    bg_context_destroy(cpp_context);
    bg_context_destroy(rust_context);
}

void test_hip_parity_when_available(
    bg_backend backend,
    uint64_t maximum_receptor_pairs = 0) {
    uint8_t available = UINT8_C(0);
    assert(bg_backend_is_available(backend, 0, &available) == BG_STATUS_OK);
    if (available == UINT8_C(0)) {
        return;
    }
    const Fixture fixture;
    bg_context *rust_context = create_context(BG_BACKEND_RUST_CPU);
    bg_context *hip_context = create_context(backend);
    bg_docking_fixed64_downstream_v1 *rust_pipeline =
        create_pipeline(
            rust_context, fixture, maximum_receptor_pairs);
    bg_docking_fixed64_downstream_v1 *hip_pipeline =
        create_pipeline(hip_context, fixture, maximum_receptor_pairs);
    const Result rust = run(rust_context, rust_pipeline, fixture);
    const Result hip = run(hip_context, hip_pipeline, fixture);
    const Result hip_repeat = run(hip_context, hip_pipeline, fixture);
    assert_result_exact(hip, hip_repeat);
    assert_result_parity(hip, rust, 1.0e-10);
    bg_docking_fixed64_downstream_v1_destroy(rust_pipeline);
    bg_docking_fixed64_downstream_v1_destroy(hip_pipeline);
    bg_context_destroy(rust_context);
    bg_context_destroy(hip_context);
}

}  // namespace

int main() {
    test_cpu_composition_repeat_stability_and_fixed64_evidence();
    test_cross_wiring_rejected_and_outputs_are_transactional();
    test_capacity_failure_is_candidate_local_and_preserves_pairs();
    test_hip_parity_when_available(BG_BACKEND_HIP_SAFE);
    test_hip_parity_when_available(BG_BACKEND_HIP_FAST);
    test_hip_parity_when_available(BG_BACKEND_HIP_SAFE, 1);
    test_hip_parity_when_available(BG_BACKEND_HIP_FAST, 1);
    return 0;
}
