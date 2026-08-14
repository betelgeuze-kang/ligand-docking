#include "betelgeuze/engine.h"
#include "internal.hpp"

#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <string_view>
#include <tuple>
#include <type_traits>
#include <utility>
#include <vector>

namespace {

constexpr std::size_t kAtoms = 4;
constexpr std::size_t kSlots = BG_DOCKING_FIXED64_CANDIDATE_COUNT;
constexpr std::size_t kCoordinates = kAtoms * kSlots;
constexpr std::size_t kMoves =
    kSlots * BG_DOCKING_TORSION_V7_MAX_MOVES;
constexpr std::size_t kFeatureCount = BG_DOCKING_FIXED64_FEATURE_KIND_COUNT;
constexpr std::array<uint32_t, 4> kRetainedIndices = {36, 45, 54, 63};
constexpr std::array<const char *, kFeatureCount> kFeatureReceipts = {
    "a4a9abe5385a5d950cc97fb3d6d17786e89f701fbaf0f536c7625cdb324a196c",
    "c5c7e1de6b795c4bbb48d3dd9e16d542af74992ae8b6a6c00c6469e2bc2c0d71",
    "91f058ffdfe22f1ac9109dedcf4613bd31d5b75cd7c935cb470e77360de5ac34",
    "6a141b8dff96c9203e272a8323908794e3326a653f384b44353cf4ee00b5ebca",
    "e2d39cb1d8ce38251fb647d013ffbe950e0380b0b91c6b8573c7b8ac0feda250",
    "7355e212bc8b602ebc010672ed24b28c6b0522f774403d0869f8b2054a48ffc7",
    "ff451a99520fa7861bb09059c6cb4d68b904ad894b9ec48c956d4fbabbaa6cfd",
    "bbf3b947353fccbb9630ce0fb1c052d0f708d40da73aee7fb6425a73c53b8836",
    "4e575a9d21486a700c15a4447df1c5aad6d7888ef31eabe9996b703477bc2785",
    "b21dc24325877d05045de061985c49b61859bd5164f70923e55f0bcba9a2abc9",
    "38dca0ef30fec0feabb58c167206e90e9b3f99f01d451850f38c2d89954c27f7",
    "9f440529e7ad7c91e047dabffde0f0a8ff58896ac37b9350584328353f37a766",
};

uint8_t hex_digit(char value) {
    if (value >= '0' && value <= '9') return static_cast<uint8_t>(value - '0');
    if (value >= 'a' && value <= 'f') {
        return static_cast<uint8_t>(10 + value - 'a');
    }
    assert(false);
    return 0;
}

void parse_digest(const char *hex, uint8_t (&output)[32]) {
    const std::string_view value(hex);
    assert(value.size() == 64);
    for (std::size_t index = 0; index < 32; ++index) {
        output[index] = static_cast<uint8_t>(
            (hex_digit(value[index * 2]) << 4U) |
            hex_digit(value[index * 2 + 1]));
    }
}

template <std::size_t Count>
void fill_digest(uint8_t (&digest)[Count], uint8_t marker) {
    static_assert(Count == 32);
    std::fill(std::begin(digest), std::end(digest), marker);
}

template <typename Type>
std::array<unsigned char, sizeof(Type)> object_bytes(const Type &value) {
    static_assert(std::is_trivially_copyable<Type>::value);
    std::array<unsigned char, sizeof(Type)> result{};
    std::memcpy(result.data(), &value, result.size());
    return result;
}

bool digest_present(const uint8_t (&digest)[32]) {
    return std::any_of(
        std::begin(digest), std::end(digest),
        [](uint8_t value) { return value != UINT8_C(0); });
}

void fill_source_evidence(
    bg_docking_fixed64_source_evidence_v1 *source,
    uint8_t marker) {
    fill_digest(source->receipt_sha256, marker);
    fill_digest(
        source->proposal_sha256,
        static_cast<uint8_t>(marker + UINT8_C(64)));
    parse_digest(
        "ab01e8fe2a0e14b958827e710f1d262de82a886b279563aae8cedc946ef533c8",
        source->coordinate_sha256);
}

struct Fixture final {
    std::array<double, kCoordinates> source_x = {0.0, 1.0, 0.0, 0.0};
    std::array<double, kCoordinates> source_y = {0.0, 0.0, 1.0, 0.0};
    std::array<double, kCoordinates> source_z = {0.0, 0.0, 0.0, 1.0001};
    std::array<double, kAtoms> receptor_x = {4.0, 3.5, 4.0, 4.0};
    std::array<double, kAtoms> receptor_y = {0.0, 0.0, 1.0, 0.0};
    std::array<double, kAtoms> receptor_z = {0.0, 0.0, 0.0, 1.0002};
    std::array<double, kAtoms> ligand_radii = {1.5, 1.5, 1.5, 1.5};
    std::array<double, kAtoms> receptor_radii = {1.5, 1.5, 1.5, 1.5};
    std::array<uint8_t, kAtoms> heavy_mask = {1, 1, 1, 1};
    std::array<double, kAtoms> receptor_charge = {-0.5, 0.2, 0.3, 0.0};
    std::array<double, kAtoms> receptor_epsilon = {0.2, 0.18, 0.05, 0.25};
    std::array<uint8_t, kAtoms> receptor_hydrophobic = {0, 0, 0, 1};
    std::array<uint8_t, kAtoms> receptor_acceptor = {1, 0, 0, 0};
    std::array<double, kAtoms> ligand_charge = {0.2, 0.25, -0.45, 0.0};
    std::array<double, kAtoms> ligand_epsilon = {0.18, 0.05, 0.2, 0.25};
    std::array<uint8_t, kAtoms> ligand_hydrophobic = {0, 0, 0, 1};
    std::array<uint8_t, kAtoms> ligand_acceptor = {0, 0, 1, 1};
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
    std::array<bg_docking_rigid_refinement_candidate_mode, kSlots>
        refinement_modes{};
    std::array<uint64_t, kSlots> rigid_steps{};
    std::array<uint8_t, kSlots> torsion_eligible{};
    std::array<uint64_t, kSlots> torsion_steps{};
    std::array<double, kCoordinates> baseline_angles{};
    std::array<bg_docking_fixed64_atomic_feature_evidence_v1, kFeatureCount>
        atomic_features{};
    std::array<bg_docking_fixed64_feature_geometry_row_v1, kFeatureCount>
        feature_rows{};
    std::vector<uint64_t> feature_indices;
    std::array<bg_docking_fixed64_indexed_source_evidence_v1, 24>
        v7_evidence{};
    std::array<bg_docking_fixed64_conformer_source_evidence_v1, 7>
        conformer_evidence{};
    std::array<bg_docking_fixed64_indexed_source_evidence_v1, 4>
        retained_evidence{};
    std::array<bg_docking_fixed64_indexed_coordinate_source_v1, 24>
        v7_sources{};
    std::array<bg_docking_fixed64_conformer_coordinate_source_v1, 7>
        conformer_sources{};
    std::array<bg_docking_fixed64_indexed_coordinate_source_v1, 4>
        retained_sources{};
    bg_docking_fixed64_coordinate_source_v1 exact_source{};
    bg_docking_fixed64_allocation_input_v1 allocation{};

    Fixture() {
        assert(bg_docking_fixed64_allocation_input_v1_init(&allocation) ==
               BG_STATUS_OK);
        fill_digest(allocation.exact_v11_source.source_receipt_sha256, 0x10);
        fill_digest(allocation.exact_v11_source.proposal_sha256, 0x11);
        parse_digest(
            "ab01e8fe2a0e14b958827e710f1d262de82a886b279563aae8cedc946ef533c8",
            allocation.exact_v11_source.ligand_coordinate_sha256);
        parse_digest(
            "fc1a4a36a926d55049f0d6d06d3f61328f59ed6860899712dec2df39c6832ef5",
            allocation.exact_v11_source.receptor_coordinate_sha256);
        fill_digest(
            allocation.exact_v11_source.prepared_ligand_topology_sha256,
            0x72);
        fill_digest(
            allocation.exact_v11_source.prepared_receptor_topology_sha256,
            0x71);
        parse_digest(
            "142a64fce99277370fc239fbbb59e85aee8c8c9472a6eb394231b8bff31981f6",
            allocation.exact_v11_source.ligand_vdw_radii_sha256);
        parse_digest(
            "47db80b60571a69d0c98dca872f4c6ab561bb7ce179e4300d440639b234015dc",
            allocation.exact_v11_source.ligand_heavy_atom_mask_sha256);
        parse_digest(
            "142a64fce99277370fc239fbbb59e85aee8c8c9472a6eb394231b8bff31981f6",
            allocation.exact_v11_source.receptor_vdw_radii_sha256);
        std::copy_n(
            allocation.exact_v11_source.source_receipt_sha256, 32,
            exact_source.source.receipt_sha256);
        std::copy_n(
            allocation.exact_v11_source.proposal_sha256, 32,
            exact_source.source.proposal_sha256);
        std::copy_n(
            allocation.exact_v11_source.ligand_coordinate_sha256, 32,
            exact_source.source.coordinate_sha256);
        exact_source.ligand_atom_count = kAtoms;
        exact_source.x_angstrom = source_x.data();
        exact_source.y_angstrom = source_y.data();
        exact_source.z_angstrom = source_z.data();

        const std::array<std::vector<uint64_t>, kFeatureCount> indices = {
            std::vector<uint64_t>{0, 1}, std::vector<uint64_t>{2},
            std::vector<uint64_t>{0, 1}, std::vector<uint64_t>{2},
            std::vector<uint64_t>{1}, std::vector<uint64_t>{2},
            std::vector<uint64_t>{1}, std::vector<uint64_t>{2},
            std::vector<uint64_t>{0, 1, 2},
            std::vector<uint64_t>{0, 2, 3},
            std::vector<uint64_t>{0, 1, 2, 3},
            std::vector<uint64_t>{0, 1, 2, 3},
        };
        for (std::size_t index = 0; index < kFeatureCount; ++index) {
            auto &atomic = atomic_features[index];
            atomic.kind = static_cast<bg_docking_fixed64_feature_kind>(index);
            fill_digest(
                atomic.receipt_sha256,
                static_cast<uint8_t>(0x40U + index));
            auto &geometry = feature_rows[index];
            geometry.kind = atomic.kind;
            std::copy_n(
                atomic.receipt_sha256, 32,
                geometry.allocation_feature_receipt_sha256);
            geometry.atom_index_offset = feature_indices.size();
            geometry.atom_index_count = indices[index].size();
            feature_indices.insert(
                feature_indices.end(), indices[index].begin(),
                indices[index].end());
            parse_digest(
                kFeatureReceipts[index],
                geometry.feature_geometry_receipt_sha256);
        }
        for (std::size_t index = 0; index < v7_evidence.size(); ++index) {
            v7_evidence[index].source_index = static_cast<uint32_t>(index);
            fill_source_evidence(
                &v7_evidence[index].source,
                static_cast<uint8_t>(1U + index));
            v7_sources[index].source_index = static_cast<uint32_t>(index);
            assign_payload(v7_evidence[index].source, &v7_sources[index].payload);
        }
        for (std::size_t index = 0; index < conformer_evidence.size(); ++index) {
            const auto rank = static_cast<uint8_t>(index + 2U);
            conformer_evidence[index].rank = rank;
            fill_source_evidence(
                &conformer_evidence[index].source,
                static_cast<uint8_t>(32U + rank));
            conformer_sources[index].rank = rank;
            assign_payload(
                conformer_evidence[index].source,
                &conformer_sources[index].payload);
        }
        for (std::size_t index = 0; index < retained_evidence.size(); ++index) {
            retained_evidence[index].source_index = kRetainedIndices[index];
            fill_source_evidence(
                &retained_evidence[index].source,
                static_cast<uint8_t>(48U + index));
            retained_sources[index].source_index = kRetainedIndices[index];
            assign_payload(
                retained_evidence[index].source,
                &retained_sources[index].payload);
        }
        allocation.atomic_feature_count = atomic_features.size();
        allocation.atomic_features = atomic_features.data();
        allocation.v7_control_source_count = v7_evidence.size();
        allocation.v7_control_sources = v7_evidence.data();
        allocation.conformer_source_count = conformer_evidence.size();
        allocation.conformer_sources = conformer_evidence.data();
        allocation.retained_source_count = retained_evidence.size();
        allocation.retained_sources = retained_evidence.data();
        for (std::size_t slot = 0; slot < kSlots; ++slot) {
            switch (slot % 4U) {
                case 0:
                    refinement_modes[slot] =
                        BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION;
                    break;
                case 1:
                    refinement_modes[slot] =
                        BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V3_TRANSLATION_ROTATION;
                    break;
                case 2:
                    refinement_modes[slot] =
                        BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V2_LANE;
                    torsion_eligible[slot] = UINT8_C(1);
                    torsion_steps[slot] = 4;
                    break;
                default:
                    refinement_modes[slot] =
                        BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V3_LANE;
                    torsion_eligible[slot] = UINT8_C(1);
                    torsion_steps[slot] = 4;
                    break;
            }
            rigid_steps[slot] = 4;
        }
    }

    void assign_payload(
        const bg_docking_fixed64_source_evidence_v1 &evidence,
        bg_docking_fixed64_coordinate_source_v1 *payload) {
        payload->source = evidence;
        payload->ligand_atom_count = kAtoms;
        payload->x_angstrom = source_x.data();
        payload->y_angstrom = source_y.data();
        payload->z_angstrom = source_z.data();
    }
};

bg_context *make_context(bg_backend backend) {
    uint8_t available = 0;
    assert(bg_backend_is_available(backend, 0, &available) == BG_STATUS_OK);
    if (available == 0) return nullptr;
    bg_context_options options{};
    assert(bg_context_options_init(&options) == BG_STATUS_OK);
    options.backend = backend;
    bg_context *context = nullptr;
    assert(bg_context_create(&options, &context) == BG_STATUS_OK);
    return context;
}

bg_docking_geometric_admission_context_soa_v1 make_admission_descriptor(
    const Fixture &fixture,
    std::array<double, 3> pocket_center = {0.0, 0.0, 0.0},
    uint64_t ligand_atom_count = kAtoms) {
    bg_docking_geometric_admission_context_soa_v1 descriptor{};
    assert(bg_docking_geometric_admission_context_soa_v1_init(&descriptor) ==
           BG_STATUS_OK);
    descriptor.receptor_atom_count = kAtoms;
    descriptor.ligand_atom_count = ligand_atom_count;
    descriptor.receptor_x_angstrom = fixture.receptor_x.data();
    descriptor.receptor_y_angstrom = fixture.receptor_y.data();
    descriptor.receptor_z_angstrom = fixture.receptor_z.data();
    descriptor.receptor_vdw_radius_angstrom = fixture.receptor_radii.data();
    descriptor.ligand_vdw_radius_angstrom = fixture.ligand_radii.data();
    descriptor.ligand_heavy_atom_mask = fixture.heavy_mask.data();
    std::copy(
        pocket_center.begin(), pocket_center.end(),
        descriptor.pocket_center_angstrom);
    descriptor.pocket_radius_angstrom = 10.0;
    descriptor.hard_rejection_minimum_vdw_ratio = 0.55;
    descriptor.max_batch_exact_pair_evaluations = UINT64_C(16'777'216);
    fill_digest(descriptor.authority_input_receipt_sha256, 0x70);
    fill_digest(descriptor.receptor_system_sha256, 0x71);
    fill_digest(descriptor.ligand_system_sha256, 0x72);
    fill_digest(descriptor.backend_receipt_sha256, 0x73);
    return descriptor;
}

bg_docking_geometric_admission_v1 *make_admission(
    const Fixture &fixture,
    bg_context *context,
    std::array<double, 3> pocket_center = {0.0, 0.0, 0.0},
    uint64_t ligand_atom_count = kAtoms) {
    const auto descriptor = make_admission_descriptor(
        fixture, pocket_center, ligand_atom_count);
    bg_docking_geometric_admission_v1 *admission = nullptr;
    assert(bg_docking_geometric_admission_v1_create(
               context, &descriptor, &admission) == BG_STATUS_OK);
    return admission;
}

bg_docking_rigid_refinement_context_soa_v1 make_rigid_descriptor(
    const Fixture &fixture) {
    bg_docking_rigid_refinement_context_soa_v1 value{};
    assert(bg_docking_rigid_refinement_context_soa_v1_init(&value) ==
           BG_STATUS_OK);
    value.receptor_atom_count = kAtoms;
    value.ligand_atom_count = kAtoms;
    value.receptor_x_angstrom = fixture.receptor_x.data();
    value.receptor_y_angstrom = fixture.receptor_y.data();
    value.receptor_z_angstrom = fixture.receptor_z.data();
    value.receptor_vdw_radius_angstrom = fixture.receptor_radii.data();
    value.ligand_vdw_radius_angstrom = fixture.ligand_radii.data();
    value.pocket_radius_angstrom = 10.0;
    return value;
}

bg_docking_torsion_v7_context_soa_v1 make_torsion_descriptor(
    const Fixture &fixture) {
    bg_docking_torsion_v7_context_soa_v1 value{};
    assert(bg_docking_torsion_v7_context_soa_v1_init(&value) == BG_STATUS_OK);
    value.receptor_atom_count = kAtoms;
    value.ligand_atom_count = kAtoms;
    value.rotor_count = fixture.rotatable_child.size();
    value.internal_pair_count = fixture.internal_i.size();
    value.receptor_x_angstrom = fixture.receptor_x.data();
    value.receptor_y_angstrom = fixture.receptor_y.data();
    value.receptor_z_angstrom = fixture.receptor_z.data();
    value.receptor_vdw_radius_angstrom = fixture.receptor_radii.data();
    value.ligand_vdw_radius_angstrom = fixture.ligand_radii.data();
    value.parent_atom_index = fixture.parent.data();
    value.rotatable_child_atom_index = fixture.rotatable_child.data();
    value.internal_pair_atom_i = fixture.internal_i.data();
    value.internal_pair_atom_j = fixture.internal_j.data();
    value.minimum_selected_final_receptor_penalty = 0.0;
    value.maximum_selected_final_receptor_penalty = 1'000'000.0;
    return value;
}

bg_docking_scorer_v1_context_soa_v1 make_scorer_descriptor(
    const Fixture &fixture) {
    bg_docking_scorer_v1_context_soa_v1 value{};
    assert(bg_docking_scorer_v1_context_soa_v1_init(&value) == BG_STATUS_OK);
    value.receptor_atom_count = kAtoms;
    value.ligand_atom_count = kAtoms;
    value.receptor_x_angstrom = fixture.receptor_x.data();
    value.receptor_y_angstrom = fixture.receptor_y.data();
    value.receptor_z_angstrom = fixture.receptor_z.data();
    value.receptor_charge_elementary = fixture.receptor_charge.data();
    value.receptor_vdw_radius_angstrom = fixture.receptor_radii.data();
    value.receptor_epsilon_kcal_per_mol = fixture.receptor_epsilon.data();
    value.receptor_hydrophobic = fixture.receptor_hydrophobic.data();
    value.receptor_acceptor = fixture.receptor_acceptor.data();
    value.ligand_reference_x_angstrom = fixture.source_x.data();
    value.ligand_reference_y_angstrom = fixture.source_y.data();
    value.ligand_reference_z_angstrom = fixture.source_z.data();
    value.ligand_charge_elementary = fixture.ligand_charge.data();
    value.ligand_vdw_radius_angstrom = fixture.ligand_radii.data();
    value.ligand_epsilon_kcal_per_mol = fixture.ligand_epsilon.data();
    value.ligand_hydrophobic = fixture.ligand_hydrophobic.data();
    value.ligand_acceptor = fixture.ligand_acceptor.data();
    value.receptor_donor_count = fixture.receptor_donor.size();
    value.receptor_donor_atom_index = fixture.receptor_donor.data();
    value.receptor_hydrogen_atom_index = fixture.receptor_hydrogen.data();
    value.ligand_donor_count = fixture.ligand_donor.size();
    value.ligand_donor_atom_index = fixture.ligand_donor.data();
    value.ligand_hydrogen_atom_index = fixture.ligand_hydrogen.data();
    value.ligand_exclusion_count = fixture.exclusion_i.size();
    value.ligand_exclusion_atom_i = fixture.exclusion_i.data();
    value.ligand_exclusion_atom_j = fixture.exclusion_j.data();
    value.rotor_count = fixture.scorer_rotor_i.size();
    value.rotor_atom_i = fixture.scorer_rotor_i.data();
    value.rotor_atom_j = fixture.scorer_rotor_j.data();
    value.rotor_atom_k = fixture.scorer_rotor_k.data();
    value.rotor_atom_l = fixture.scorer_rotor_l.data();
    value.pocket_radius_angstrom = 10.0;
    fill_digest(value.authority_input_receipt_sha256, 0x70);
    fill_digest(value.receptor_system_sha256, 0x71);
    fill_digest(value.ligand_system_sha256, 0x72);
    fill_digest(value.backend_receipt_sha256, 0x73);
    return value;
}

bg_docking_pose_validity_context_soa_v1 make_validity_descriptor(
    const Fixture &fixture) {
    bg_docking_pose_validity_context_soa_v1 value{};
    assert(bg_docking_pose_validity_context_soa_v1_init(&value) ==
           BG_STATUS_OK);
    value.receptor_atom_count = kAtoms;
    value.ligand_atom_count = kAtoms;
    value.receptor_x_angstrom = fixture.receptor_x.data();
    value.receptor_y_angstrom = fixture.receptor_y.data();
    value.receptor_z_angstrom = fixture.receptor_z.data();
    value.receptor_vdw_radius_angstrom = fixture.receptor_radii.data();
    value.ligand_reference_x_angstrom = fixture.source_x.data();
    value.ligand_reference_y_angstrom = fixture.source_y.data();
    value.ligand_reference_z_angstrom = fixture.source_z.data();
    value.ligand_vdw_radius_angstrom = fixture.ligand_radii.data();
    value.bond_count = fixture.bond_i.size();
    value.bond_atom_i = fixture.bond_i.data();
    value.bond_atom_j = fixture.bond_j.data();
    value.ligand_exclusion_count = fixture.exclusion_i.size();
    value.ligand_exclusion_atom_i = fixture.exclusion_i.data();
    value.ligand_exclusion_atom_j = fixture.exclusion_j.data();
    value.pocket_radius_angstrom = 10.0;
    fill_digest(value.authority_input_receipt_sha256, 0x70);
    fill_digest(value.receptor_system_sha256, 0x71);
    fill_digest(value.ligand_system_sha256, 0x72);
    fill_digest(value.scorer_context_receipt_sha256, 0x74);
    fill_digest(value.backend_receipt_sha256, 0x73);
    fill_digest(value.contact_policy_sha256, 0x75);
    return value;
}

bg_docking_fixed64_producer_input_v1 make_input(const Fixture &fixture) {
    bg_docking_fixed64_producer_input_v1 input{};
    assert(bg_docking_fixed64_producer_input_v1_init(&input) == BG_STATUS_OK);
    input.allocation_input = &fixture.allocation;
    input.exact_v11_source = &fixture.exact_source;
    input.v7_control_source_count = fixture.v7_sources.size();
    input.v7_control_sources = fixture.v7_sources.data();
    input.conformer_source_count = fixture.conformer_sources.size();
    input.conformer_sources = fixture.conformer_sources.data();
    input.retained_source_count = fixture.retained_sources.size();
    input.retained_sources = fixture.retained_sources.data();
    input.feature_geometry_count = fixture.feature_rows.size();
    input.feature_geometry_rows = fixture.feature_rows.data();
    input.feature_atom_index_count = fixture.feature_indices.size();
    input.feature_atom_indices = fixture.feature_indices.data();
    parse_digest(
        "0f93ce2e442cdcdd01d8c6e0840f09c485a17b0169f66a341355797877981ea2",
        input.feature_geometry_inventory_sha256);
    input.pocket_normal[2] = 1.0;
    return input;
}

struct Batch final {
    std::array<bg_docking_fixed64_producer_row_v1, kSlots> rows{};
    std::array<double, kCoordinates> x{};
    std::array<double, kCoordinates> y{};
    std::array<double, kCoordinates> z{};
    bg_docking_fixed64_producer_output_v1 output{};
};

struct CompletePipelineResult final {
    Batch producer{};
    std::array<bg_docking_rigid_refinement_row_v1, kSlots> rigid_rows{};
    std::array<std::array<double, kCoordinates>, 12> rigid_coordinates{};
    std::array<bg_docking_torsion_v7_row_v1, kSlots> torsion_rows{};
    std::array<bg_docking_torsion_v7_move_v1, kMoves> torsion_moves{};
    std::array<std::array<double, kCoordinates>, 8> torsion_coordinates{};
    std::array<bg_docking_scorer_v1_row_v1, kSlots> scorer_rows{};
    std::array<bg_docking_pose_validity_row_v1, kSlots> validity_rows{};
    std::array<bg_docking_stable_top_k_row_v1, kSlots> ranking_rows{};
    std::array<uint32_t, kSlots> primary_indices{};
    std::array<uint32_t, kSlots> valid_indices{};
    std::array<bg_docking_rmsd_cluster_row_v1, kSlots> cluster_rows{};
    std::array<uint32_t, kSlots> representatives{};
    std::array<uint32_t, BG_DOCKING_STABLE_TOP_K_LIMIT> cluster_top_k{};
    std::array<bg_docking_fixed64_refinement_row_v1, kSlots>
        refinement_rows{};
    std::array<std::array<double, kCoordinates>, 3> final_coordinates{};
    std::array<std::array<double, kSlots>, 4> final_quaternions{};
    std::array<bg_docking_fixed64_pipeline_row_v1, kSlots> rows{};
    bg_docking_fixed64_pipeline_output_v1 output{};
    std::array<bg_docking_geometric_admission_row_v1, kSlots>
        post_admission_rows{};
    bg_docking_geometric_admission_output_v1 post_admission_output{};
    std::array<bg_docking_fixed64_pipeline_row_v2, kSlots> rows_v2{};
    bg_docking_fixed64_pipeline_output_v2 output_v2{};
};

bg_docking_fixed64_pipeline_v1 *make_complete_pipeline(
    const Fixture &fixture,
    bg_context *context) {
    const auto admission = make_admission_descriptor(fixture);
    const auto rigid = make_rigid_descriptor(fixture);
    const auto torsion = make_torsion_descriptor(fixture);
    const auto scorer = make_scorer_descriptor(fixture);
    const auto validity = make_validity_descriptor(fixture);
    bg_docking_fixed64_pipeline_v1 *pipeline = nullptr;
    assert(bg_docking_fixed64_pipeline_v1_create(
               context,
               &admission,
               &rigid,
               &torsion,
               &scorer,
               &validity,
               &pipeline) == BG_STATUS_OK);
    assert(pipeline != nullptr);
    return pipeline;
}

bg_docking_fixed64_pipeline_v2 *make_complete_pipeline_v2(
    const Fixture &fixture,
    bg_context *context,
    double torsion_internal_overlap_weight = 1.0,
    double torsion_receptor_overlap_scale = 1.0) {
    const auto admission = make_admission_descriptor(fixture);
    const auto rigid = make_rigid_descriptor(fixture);
    auto torsion = make_torsion_descriptor(fixture);
    torsion.internal_overlap_weight = torsion_internal_overlap_weight;
    torsion.receptor_overlap_scale = torsion_receptor_overlap_scale;
    const auto scorer = make_scorer_descriptor(fixture);
    auto validity = make_validity_descriptor(fixture);
    const double maximum_radius = std::max(
        *std::max_element(
            fixture.receptor_radii.begin(), fixture.receptor_radii.end()),
        *std::max_element(
            fixture.ligand_radii.begin(), fixture.ligand_radii.end()));
    validity.contact_cell_size_angstrom = std::max(
        validity.contact_cell_size_angstrom,
        2.0 * maximum_radius * validity.severe_overlap_scale);
    bg_docking_fixed64_pipeline_v2 *pipeline = nullptr;
    const bg_status status = bg_docking_fixed64_pipeline_v2_create(
        context,
        &admission,
        &rigid,
        &torsion,
        &scorer,
        &validity,
        &pipeline);
    if (status != BG_STATUS_OK) {
        std::fprintf(
            stderr,
            "complete pipeline v2 create failed: %s\n",
            bg_last_error_message());
    }
    assert(status == BG_STATUS_OK);
    assert(pipeline != nullptr);
    return pipeline;
}

bg_docking_fixed64_pipeline_v1 *make_single_atom_complete_pipeline(
    const Fixture &fixture,
    bg_context *context) {
    auto admission = make_admission_descriptor(fixture);
    auto rigid = make_rigid_descriptor(fixture);
    auto torsion = make_torsion_descriptor(fixture);
    auto scorer = make_scorer_descriptor(fixture);
    auto validity = make_validity_descriptor(fixture);
    admission.ligand_atom_count = 1;
    rigid.ligand_atom_count = 1;
    torsion.ligand_atom_count = 1;
    torsion.rotor_count = 0;
    torsion.rotatable_child_atom_index = nullptr;
    torsion.internal_pair_count = 0;
    torsion.internal_pair_atom_i = nullptr;
    torsion.internal_pair_atom_j = nullptr;
    scorer.ligand_atom_count = 1;
    scorer.ligand_donor_count = 0;
    scorer.ligand_donor_atom_index = nullptr;
    scorer.ligand_hydrogen_atom_index = nullptr;
    scorer.ligand_exclusion_count = 0;
    scorer.ligand_exclusion_atom_i = nullptr;
    scorer.ligand_exclusion_atom_j = nullptr;
    scorer.rotor_count = 0;
    scorer.rotor_atom_i = nullptr;
    scorer.rotor_atom_j = nullptr;
    scorer.rotor_atom_k = nullptr;
    scorer.rotor_atom_l = nullptr;
    validity.ligand_atom_count = 1;
    validity.bond_count = 0;
    validity.bond_atom_i = nullptr;
    validity.bond_atom_j = nullptr;
    validity.ligand_exclusion_count = 0;
    validity.ligand_exclusion_atom_i = nullptr;
    validity.ligand_exclusion_atom_j = nullptr;
    validity.chirality_center_count = 0;
    validity.chirality_center_atom = nullptr;
    validity.chirality_atom_i = nullptr;
    validity.chirality_atom_j = nullptr;
    validity.chirality_atom_k = nullptr;
    bg_docking_fixed64_pipeline_v1 *pipeline = nullptr;
    assert(bg_docking_fixed64_pipeline_v1_create(
               context,
               &admission,
               &rigid,
               &torsion,
               &scorer,
               &validity,
               &pipeline) == BG_STATUS_OK);
    assert(pipeline != nullptr);
    return pipeline;
}

bg_status run_complete_pipeline_into(
    bg_context *context,
    bg_docking_fixed64_pipeline_v1 *pipeline,
    const Fixture &fixture,
    CompletePipelineResult *result,
    bool overlap_summary_rows = false,
    bool overlap_downstream_with_source = false,
    bool overlap_summary_with_pipeline = false,
    const bg_docking_fixed64_producer_input_v1 *producer_input_override =
        nullptr,
    bool repeat_same_output_descriptors = false) {
    const auto default_producer_input = make_input(fixture);
    bg_docking_fixed64_pipeline_input_v1 input{};
    assert(bg_docking_fixed64_pipeline_input_v1_init(&input) == BG_STATUS_OK);
    input.producer_input = producer_input_override == nullptr
        ? &default_producer_input
        : producer_input_override;
    input.rmsd_threshold_angstrom = 1.5;
    input.candidate_mode = fixture.refinement_modes.data();
    input.rigid_max_steps = fixture.rigid_steps.data();
    input.proposal_is_torsion_eligible = fixture.torsion_eligible.data();
    input.torsion_max_steps = fixture.torsion_steps.data();
    input.baseline_torsion_angles_radians = fixture.baseline_angles.data();
    fill_digest(input.predeclared_refinement_policy_sha256, 0x76);
    const uint64_t output_coordinate_count =
        input.producer_input->exact_v11_source->ligand_atom_count * kSlots;

    auto &producer = result->producer.output;
    bg_docking_rigid_refinement_output_v1 rigid{};
    bg_docking_torsion_v7_output_v1 torsion{};
    bg_docking_scorer_v1_output_v1 scorer{};
    bg_docking_pose_validity_output_v1 validity{};
    bg_docking_stable_top_k_output_v1 ranking{};
    bg_docking_rmsd_cluster_output_v1 cluster{};
    bg_docking_fixed64_refinement_output_v1 refinement{};
    assert(bg_docking_fixed64_producer_output_v1_init(&producer) ==
           BG_STATUS_OK);
    assert(bg_docking_rigid_refinement_output_v1_init(&rigid) == BG_STATUS_OK);
    assert(bg_docking_torsion_v7_output_v1_init(&torsion) == BG_STATUS_OK);
    assert(bg_docking_scorer_v1_output_v1_init(&scorer) == BG_STATUS_OK);
    assert(bg_docking_pose_validity_output_v1_init(&validity) == BG_STATUS_OK);
    assert(bg_docking_stable_top_k_output_v1_init(&ranking) == BG_STATUS_OK);
    assert(bg_docking_rmsd_cluster_output_v1_init(&cluster) == BG_STATUS_OK);
    assert(bg_docking_fixed64_refinement_output_v1_init(&refinement) ==
           BG_STATUS_OK);
    assert(bg_docking_fixed64_pipeline_output_v1_init(&result->output) ==
           BG_STATUS_OK);

    producer.row_capacity = kSlots;
    producer.coordinate_capacity = output_coordinate_count;
    producer.rows = result->producer.rows.data();
    producer.x_angstrom = result->producer.x.data();
    producer.y_angstrom = result->producer.y.data();
    producer.z_angstrom = result->producer.z.data();
    rigid.row_capacity = kSlots;
    rigid.coordinate_capacity = output_coordinate_count;
    rigid.rows = result->rigid_rows.data();
    rigid.selected_x_angstrom = overlap_downstream_with_source
        ? const_cast<double *>(fixture.source_x.data())
        : result->rigid_coordinates[0].data();
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
    torsion.coordinate_capacity = output_coordinate_count;
    torsion.rows = result->torsion_rows.data();
    torsion.moves = result->torsion_moves.data();
    torsion.optimized_x_angstrom = result->torsion_coordinates[0].data();
    torsion.optimized_y_angstrom = result->torsion_coordinates[1].data();
    torsion.optimized_z_angstrom = result->torsion_coordinates[2].data();
    torsion.optimized_torsion_angles_radians =
        result->torsion_coordinates[3].data();
    torsion.final_x_angstrom = result->torsion_coordinates[4].data();
    torsion.final_y_angstrom = result->torsion_coordinates[5].data();
    torsion.final_z_angstrom = result->torsion_coordinates[6].data();
    torsion.final_torsion_angles_radians =
        result->torsion_coordinates[7].data();
    scorer.row_capacity = kSlots;
    scorer.rows = result->scorer_rows.data();
    validity.row_capacity = kSlots;
    validity.rows = result->validity_rows.data();
    ranking.row_capacity = kSlots;
    ranking.primary_index_capacity = kSlots;
    ranking.valid_index_capacity = kSlots;
    ranking.rows = result->ranking_rows.data();
    ranking.primary_slot_indices = result->primary_indices.data();
    ranking.valid_slot_indices = result->valid_indices.data();
    cluster.row_capacity = kSlots;
    cluster.representative_index_capacity = kSlots;
    cluster.top_k_index_capacity = BG_DOCKING_STABLE_TOP_K_LIMIT;
    cluster.rows = result->cluster_rows.data();
    cluster.representative_slot_indices = result->representatives.data();
    cluster.top_k_slot_indices = result->cluster_top_k.data();
    refinement.row_capacity = kSlots;
    refinement.coordinate_capacity = output_coordinate_count;
    refinement.quaternion_capacity = kSlots;
    refinement.rows = result->refinement_rows.data();
    refinement.final_x_angstrom = result->final_coordinates[0].data();
    refinement.final_y_angstrom = result->final_coordinates[1].data();
    refinement.final_z_angstrom = result->final_coordinates[2].data();
    refinement.final_quaternion_x = result->final_quaternions[0].data();
    refinement.final_quaternion_y = result->final_quaternions[1].data();
    refinement.final_quaternion_z = result->final_quaternions[2].data();
    refinement.final_quaternion_w = result->final_quaternions[3].data();
    result->output.row_capacity = kSlots;
    result->output.rows = overlap_summary_rows
        ? reinterpret_cast<bg_docking_fixed64_pipeline_row_v1 *>(
              result->producer.rows.data())
        : overlap_summary_with_pipeline
            ? reinterpret_cast<bg_docking_fixed64_pipeline_row_v1 *>(pipeline)
            : result->rows.data();
    const auto run = [&]() {
        return bg_docking_fixed64_pipeline_v1_run(
            context,
            pipeline,
            &input,
            &producer,
            &rigid,
            &torsion,
            &scorer,
            &validity,
            &ranking,
            &cluster,
            &refinement,
            &result->output);
    };
    const bg_status first_status = run();
    if (first_status != BG_STATUS_OK || !repeat_same_output_descriptors) {
        return first_status;
    }
    const auto first_rows = result->rows;
    std::array<uint8_t, 32> first_pipeline_receipt{};
    std::copy_n(
        result->output.pipeline_batch_receipt_sha256,
        first_pipeline_receipt.size(),
        first_pipeline_receipt.begin());
    const bg_status repeated_status = run();
    if (repeated_status == BG_STATUS_OK) {
        assert(std::memcmp(
                   first_rows.data(), result->rows.data(),
                   sizeof(first_rows)) == 0);
        assert(std::memcmp(
                   first_pipeline_receipt.data(),
                   result->output.pipeline_batch_receipt_sha256,
                   first_pipeline_receipt.size()) == 0);
    }
    return repeated_status;
}

struct CompletePipelineV2RunOptions {
    bool repeat_same_output_descriptors = false;
    bool omit_post_admission_policy = false;
    bool undersize_rigid_rows = false;
    bool undersize_pipeline_rows = false;
    bool overlap_pipeline_rows_with_producer = false;
    bool overlap_rigid_x_with_source = false;
    bool overlap_pipeline_rows_with_handle = false;
};

bg_status run_complete_pipeline_v2_into(
    bg_context *context,
    bg_docking_fixed64_pipeline_v2 *pipeline,
    const Fixture &fixture,
    CompletePipelineResult *result,
    CompletePipelineV2RunOptions options = {}) {
    const auto producer_input = make_input(fixture);
    bg_docking_fixed64_pipeline_input_v2 input{};
    assert(bg_docking_fixed64_pipeline_input_v2_init(&input) == BG_STATUS_OK);
    input.producer_input = &producer_input;
    input.rmsd_threshold_angstrom = 1.5;
    input.candidate_mode = fixture.refinement_modes.data();
    input.rigid_max_steps = fixture.rigid_steps.data();
    input.proposal_is_torsion_eligible = fixture.torsion_eligible.data();
    input.torsion_max_steps = fixture.torsion_steps.data();
    input.baseline_torsion_angles_radians = fixture.baseline_angles.data();
    fill_digest(input.predeclared_refinement_policy_sha256, 0x76);
    if (!options.omit_post_admission_policy) {
        fill_digest(
            input.predeclared_post_refinement_admission_policy_sha256, 0x77);
    }
    const uint64_t coordinate_count =
        producer_input.exact_v11_source->ligand_atom_count * kSlots;

    auto &producer = result->producer.output;
    bg_docking_rigid_refinement_output_v1 rigid{};
    bg_docking_torsion_v7_output_v1 torsion{};
    bg_docking_fixed64_refinement_output_v1 refinement{};
    auto &post_admission = result->post_admission_output;
    bg_docking_scorer_v1_output_v1 scorer{};
    bg_docking_pose_validity_output_v1 validity{};
    bg_docking_stable_top_k_output_v1 ranking{};
    bg_docking_rmsd_cluster_output_v1 cluster{};
    assert(bg_docking_fixed64_producer_output_v1_init(&producer) ==
           BG_STATUS_OK);
    assert(bg_docking_rigid_refinement_output_v1_init(&rigid) == BG_STATUS_OK);
    assert(bg_docking_torsion_v7_output_v1_init(&torsion) == BG_STATUS_OK);
    assert(bg_docking_fixed64_refinement_output_v1_init(&refinement) ==
           BG_STATUS_OK);
    assert(bg_docking_geometric_admission_output_v1_init(&post_admission) ==
           BG_STATUS_OK);
    assert(bg_docking_scorer_v1_output_v1_init(&scorer) == BG_STATUS_OK);
    assert(bg_docking_pose_validity_output_v1_init(&validity) == BG_STATUS_OK);
    assert(bg_docking_stable_top_k_output_v1_init(&ranking) == BG_STATUS_OK);
    assert(bg_docking_rmsd_cluster_output_v1_init(&cluster) == BG_STATUS_OK);
    assert(bg_docking_fixed64_pipeline_output_v2_init(&result->output_v2) ==
           BG_STATUS_OK);

    producer.row_capacity = kSlots;
    producer.coordinate_capacity = coordinate_count;
    producer.rows = result->producer.rows.data();
    producer.x_angstrom = result->producer.x.data();
    producer.y_angstrom = result->producer.y.data();
    producer.z_angstrom = result->producer.z.data();
    rigid.row_capacity = options.undersize_rigid_rows ? kSlots - 1 : kSlots;
    rigid.coordinate_capacity = coordinate_count;
    rigid.rows = result->rigid_rows.data();
    rigid.selected_x_angstrom = options.overlap_rigid_x_with_source
        ? const_cast<double *>(fixture.source_x.data())
        : result->rigid_coordinates[0].data();
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
    torsion.coordinate_capacity = coordinate_count;
    torsion.rows = result->torsion_rows.data();
    torsion.moves = result->torsion_moves.data();
    torsion.optimized_x_angstrom = result->torsion_coordinates[0].data();
    torsion.optimized_y_angstrom = result->torsion_coordinates[1].data();
    torsion.optimized_z_angstrom = result->torsion_coordinates[2].data();
    torsion.optimized_torsion_angles_radians =
        result->torsion_coordinates[3].data();
    torsion.final_x_angstrom = result->torsion_coordinates[4].data();
    torsion.final_y_angstrom = result->torsion_coordinates[5].data();
    torsion.final_z_angstrom = result->torsion_coordinates[6].data();
    torsion.final_torsion_angles_radians =
        result->torsion_coordinates[7].data();
    refinement.row_capacity = kSlots;
    refinement.coordinate_capacity = coordinate_count;
    refinement.quaternion_capacity = kSlots;
    refinement.rows = result->refinement_rows.data();
    refinement.final_x_angstrom = result->final_coordinates[0].data();
    refinement.final_y_angstrom = result->final_coordinates[1].data();
    refinement.final_z_angstrom = result->final_coordinates[2].data();
    refinement.final_quaternion_x = result->final_quaternions[0].data();
    refinement.final_quaternion_y = result->final_quaternions[1].data();
    refinement.final_quaternion_z = result->final_quaternions[2].data();
    refinement.final_quaternion_w = result->final_quaternions[3].data();
    post_admission.row_capacity = kSlots;
    post_admission.rows = result->post_admission_rows.data();
    scorer.row_capacity = kSlots;
    scorer.rows = result->scorer_rows.data();
    validity.row_capacity = kSlots;
    validity.rows = result->validity_rows.data();
    ranking.row_capacity = kSlots;
    ranking.primary_index_capacity = kSlots;
    ranking.valid_index_capacity = kSlots;
    ranking.rows = result->ranking_rows.data();
    ranking.primary_slot_indices = result->primary_indices.data();
    ranking.valid_slot_indices = result->valid_indices.data();
    cluster.row_capacity = kSlots;
    cluster.representative_index_capacity = kSlots;
    cluster.top_k_index_capacity = BG_DOCKING_STABLE_TOP_K_LIMIT;
    cluster.rows = result->cluster_rows.data();
    cluster.representative_slot_indices = result->representatives.data();
    cluster.top_k_slot_indices = result->cluster_top_k.data();
    result->output_v2.row_capacity = options.undersize_pipeline_rows
        ? kSlots - 1
        : kSlots;
    result->output_v2.rows = options.overlap_pipeline_rows_with_producer
        ? reinterpret_cast<bg_docking_fixed64_pipeline_row_v2 *>(
              result->producer.rows.data())
        : options.overlap_pipeline_rows_with_handle
            ? reinterpret_cast<bg_docking_fixed64_pipeline_row_v2 *>(pipeline)
            : result->rows_v2.data();
    const auto run = [&]() {
        return bg_docking_fixed64_pipeline_v2_run(
            context,
            pipeline,
            &input,
            &producer,
            &rigid,
            &torsion,
            &refinement,
            &post_admission,
            &scorer,
            &validity,
            &ranking,
            &cluster,
            &result->output_v2);
    };
    static_assert(std::is_trivially_copyable<CompletePipelineResult>::value);
    const CompletePipelineResult before_first_run = *result;
    const bg_status first_status = run();
    if (first_status != BG_STATUS_OK) {
        assert(std::memcmp(
                   &before_first_run,
                   result,
                   sizeof(before_first_run)) == 0);
        return first_status;
    }
    if (!options.repeat_same_output_descriptors) {
        return first_status;
    }
    const CompletePipelineResult first_result = *result;
    const bg_status repeated_status = run();
    if (repeated_status == BG_STATUS_OK) {
        assert(std::memcmp(
                   &first_result,
                   result,
                   sizeof(first_result)) == 0);
    }
    return repeated_status;
}

Batch produce(
    bg_context *context,
    bg_docking_geometric_admission_v1 *admission,
    const bg_docking_fixed64_producer_input_v1 &input) {
    Batch batch{};
    assert(bg_docking_fixed64_producer_output_v1_init(&batch.output) ==
           BG_STATUS_OK);
    batch.output.row_capacity = batch.rows.size();
    batch.output.coordinate_capacity = batch.x.size();
    batch.output.rows = batch.rows.data();
    batch.output.x_angstrom = batch.x.data();
    batch.output.y_angstrom = batch.y.data();
    batch.output.z_angstrom = batch.z.data();
    const bg_status status = bg_docking_fixed64_producer_v1_run(
        context, admission, &input, &batch.output);
    if (status != BG_STATUS_OK) {
        bg_backend backend = BG_BACKEND_AUTO;
        assert(bg_context_get_backend(context, &backend) == BG_STATUS_OK);
        std::fprintf(
            stderr, "producer backend %d failed: %s\n", backend,
            bg_last_error_message());
    }
    assert(status == BG_STATUS_OK);
    return batch;
}

void assert_authority_false(const bg_docking_fixed64_producer_output_v1 &out) {
    assert(out.result_dependent_input_consumed == 0);
    assert(out.fallback_allowed == 0);
    assert(out.multi_anchor_consumed == 0);
    assert(out.denominator_preserved == 1);
    assert(out.molecular_execution_authorized == 0);
    assert(out.reservation_authorized == 0);
    assert(out.benchmark_execution_authorized == 0);
    assert(out.existing_rank_auto_change_authorized == 0);
    assert(out.customer_pose_emission_authorized == 0);
    assert(out.production_claim_authorized == 0);
    assert(out.scientific_claim_authorized == 0);
}

void assert_complete(const Batch &batch, bg_backend backend) {
    assert(std::strcmp(
               bg_docking_fixed64_producer_v1_profile_id(),
               "betelgeuze.engine_v2_mixed64_native_fixed64_producer/1.1.2") == 0);
    assert(batch.output.row_count == kSlots);
    assert(batch.output.coordinate_count == kCoordinates);
    assert(batch.output.generated_count == kSlots);
    assert(batch.output.typed_failure_count == 0);
    assert(batch.output.backend == backend);
    assert_authority_false(batch.output);
    assert(digest_present(batch.output.allocation_inventory_sha256));
    assert(digest_present(batch.output.allocation_receipt_sha256));
    assert(digest_present(batch.output.source_bundle_receipt_sha256));
    assert(digest_present(
        batch.output.geometric_admission_batch_receipt_sha256));
    assert(digest_present(batch.output.producer_batch_receipt_sha256));
    std::size_t severe = 0;
    for (std::size_t slot = 0; slot < kSlots; ++slot) {
        const auto &row = batch.rows[slot];
        assert(row.slot_index == slot);
        assert(row.status == BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED);
        assert(row.failure_code == BG_DOCKING_FIXED64_PRODUCER_FAILURE_NONE);
        assert(row.backend == backend);
        assert(row.ligand_atom_count == kAtoms);
        assert(row.coordinate_offset == slot * kAtoms);
        assert(row.coordinates_available == 1);
        assert(row.source_identity_verified == 1);
        assert(row.allocation_identity_verified == 1);
        assert(row.geometric_identity_verified == 1);
        assert(row.denominator_preserved == 1);
        assert(row.result_dependent_input_consumed == 0);
        assert(row.fallback_allowed == 0);
        assert(row.multi_anchor_consumed == 0);
        assert(row.molecular_execution_authorized == 0);
        assert(row.reservation_authorized == 0);
        assert(row.benchmark_execution_authorized == 0);
        assert(row.existing_rank_auto_change_authorized == 0);
        assert(row.customer_pose_emission_authorized == 0);
        assert(row.production_claim_authorized == 0);
        assert(row.scientific_claim_authorized == 0);
        assert(digest_present(row.allocation_slot_receipt_sha256));
        assert(digest_present(row.source_payload_receipt_sha256));
        assert(digest_present(row.source_proposal_sha256));
        assert(digest_present(row.source_coordinate_sha256));
        assert(digest_present(row.placement_receipt_sha256));
        assert(digest_present(row.output_proposal_sha256));
        assert(digest_present(row.output_coordinate_sha256));
        assert(digest_present(row.row_receipt_sha256));
        assert(row.geometric_admission.slot_index == slot);
        assert(row.geometric_admission.status ==
               BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED);
        assert(row.geometric_admission.exact_pair_count == kAtoms * kAtoms);
        assert(digest_present(row.geometric_admission.row_receipt_sha256));
        if (row.steric_precheck_passed == 0) ++severe;
        const auto expected_kind = slot < 24 || slot >= 60
            ? BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_EXACT_PASSTHROUGH
            : (slot < 44
                   ? BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_INDEXED_SO3
                   : BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_SINGLE_ANCHOR);
        assert(row.placement_kind == expected_kind);
        const double quaternion_norm = std::hypot(
            std::hypot(
                row.placement_quaternion_x,
                row.placement_quaternion_y),
            std::hypot(
                row.placement_quaternion_z,
                row.placement_quaternion_w));
        assert(std::abs(quaternion_norm - 1.0) <= 1.0e-8);
        if (expected_kind ==
            BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_EXACT_PASSTHROUGH) {
            assert(row.placement_quaternion_x == 0.0);
            assert(row.placement_quaternion_y == 0.0);
            assert(row.placement_quaternion_z == 0.0);
            assert(row.placement_quaternion_w == 1.0);
        }
    }
    assert(severe > 0);
}

void assert_coordinate_parity(
    const Batch &reference, const Batch &observed, double tolerance) {
    for (std::size_t index = 0; index < kCoordinates; ++index) {
        for (const auto &[left, right] : {
                 std::pair{reference.x[index], observed.x[index]},
                 std::pair{reference.y[index], observed.y[index]},
                 std::pair{reference.z[index], observed.z[index]},
             }) {
            const double scale =
                std::max({1.0, std::abs(left), std::abs(right)});
            assert(std::abs(left - right) <= tolerance * scale);
        }
    }
    for (std::size_t slot = 0; slot < kSlots; ++slot) {
        assert(reference.rows[slot].steric_precheck_passed ==
               observed.rows[slot].steric_precheck_passed);
        assert(reference.rows[slot].geometric_admission.decision ==
               observed.rows[slot].geometric_admission.decision);
        for (const auto &[left, right] : {
                 std::pair{
                     reference.rows[slot].placement_quaternion_x,
                     observed.rows[slot].placement_quaternion_x},
                 std::pair{
                     reference.rows[slot].placement_quaternion_y,
                     observed.rows[slot].placement_quaternion_y},
                 std::pair{
                     reference.rows[slot].placement_quaternion_z,
                     observed.rows[slot].placement_quaternion_z},
                 std::pair{
                     reference.rows[slot].placement_quaternion_w,
                     observed.rows[slot].placement_quaternion_w},
             }) {
            assert(std::abs(left - right) <= tolerance);
        }
    }
}

void test_exact64_repeat_and_backend_parity() {
    const Fixture fixture;
    const auto input = make_input(fixture);
    bg_context *cpp = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    assert(cpp != nullptr);
    auto *cpp_admission = make_admission(fixture, cpp);
    const Batch cpp_first = produce(cpp, cpp_admission, input);
    const Batch cpp_repeat = produce(cpp, cpp_admission, input);
    assert_complete(cpp_first, BG_BACKEND_CPP_CPU_REFERENCE);
    assert(cpp_first.x == cpp_repeat.x);
    assert(cpp_first.y == cpp_repeat.y);
    assert(cpp_first.z == cpp_repeat.z);
    assert(std::memcmp(
               cpp_first.rows.data(), cpp_repeat.rows.data(),
               sizeof(cpp_first.rows)) == 0);
    for (const bg_backend backend : {
             BG_BACKEND_RUST_CPU, BG_BACKEND_HIP_SAFE, BG_BACKEND_HIP_FAST}) {
        bg_context *context = make_context(backend);
        if (context == nullptr) continue;
        auto *admission = make_admission(fixture, context);
        const Batch observed = produce(context, admission, input);
        const Batch repeated = produce(context, admission, input);
        assert_complete(observed, backend);
        assert(observed.x == repeated.x);
        assert(observed.y == repeated.y);
        assert(observed.z == repeated.z);
        assert_coordinate_parity(
            cpp_first, observed,
            backend == BG_BACKEND_RUST_CPU ? 2.0e-12 : 2.0e-9);
        bg_docking_geometric_admission_v1_destroy(admission);
        bg_context_destroy(context);
    }
    bg_docking_geometric_admission_v1_destroy(cpp_admission);
    bg_context_destroy(cpp);
}

void test_missing_source_is_typed_and_zero_filled() {
    const Fixture fixture;
    auto input = make_input(fixture);
    input.v7_control_source_count = fixture.v7_sources.size() - 1;
    bg_context *context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    assert(context != nullptr);
    auto *admission = make_admission(fixture, context);
    const Batch batch = produce(context, admission, input);
    assert(batch.output.generated_count == 63);
    assert(batch.output.typed_failure_count == 1);
    const auto &row = batch.rows[23];
    assert(row.status == BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE);
    assert(row.failure_code ==
           BG_DOCKING_FIXED64_PRODUCER_FAILURE_SOURCE_NOT_AVAILABLE);
    assert(row.coordinates_available == 0);
    assert(row.placement_quaternion_x == 0.0);
    assert(row.placement_quaternion_y == 0.0);
    assert(row.placement_quaternion_z == 0.0);
    assert(row.placement_quaternion_w == 0.0);
    assert(row.source_identity_verified == 0);
    assert(row.geometric_identity_verified == 1);
    assert(row.geometric_admission.status ==
           BG_DOCKING_GEOMETRIC_ADMISSION_ROW_UPSTREAM_FAILURE);
    for (std::size_t atom = 0; atom < kAtoms; ++atom) {
        const std::size_t offset = 23 * kAtoms + atom;
        assert(batch.x[offset] == 0.0);
        assert(batch.y[offset] == 0.0);
        assert(batch.z[offset] == 0.0);
    }
    assert(digest_present(row.row_receipt_sha256));
    assert_authority_false(batch.output);
    bg_docking_geometric_admission_v1_destroy(admission);
    bg_context_destroy(context);
}

void test_missing_feature_allocation_preserves_denominator() {
    Fixture fixture;
    fixture.allocation.atomic_feature_count = 0;
    fixture.allocation.atomic_features = nullptr;
    auto input = make_input(fixture);
    input.feature_geometry_count = 0;
    input.feature_geometry_rows = nullptr;
    input.feature_atom_index_count = 0;
    input.feature_atom_indices = nullptr;
    std::fill(
        std::begin(input.feature_geometry_inventory_sha256),
        std::end(input.feature_geometry_inventory_sha256), UINT8_C(0));
    bg_context *context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    assert(context != nullptr);
    auto *admission = make_admission(fixture, context);
    const Batch batch = produce(context, admission, input);
    assert(batch.output.generated_count == 48);
    assert(batch.output.typed_failure_count == 16);
    for (std::size_t slot = 44; slot < 60; ++slot) {
        const auto &row = batch.rows[slot];
        assert(row.status == BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE);
        assert(row.failure_code ==
               BG_DOCKING_FIXED64_PRODUCER_FAILURE_ALLOCATION_INELIGIBLE);
        assert(row.source_identity_verified == 1);
        assert(digest_present(row.source_payload_receipt_sha256));
        assert(digest_present(row.source_proposal_sha256));
        assert(digest_present(row.source_coordinate_sha256));
        assert(row.geometric_admission.status ==
               BG_DOCKING_GEOMETRIC_ADMISSION_ROW_UPSTREAM_FAILURE);
        assert(row.denominator_preserved == 1);
    }
    assert_authority_false(batch.output);
    bg_docking_geometric_admission_v1_destroy(admission);
    bg_context_destroy(context);
}

void test_partial_feature_geometry_only_fails_affected_slots() {
    const Fixture fixture;
    auto input = make_input(fixture);
    input.feature_geometry_count = kFeatureCount - 1;
    input.feature_atom_index_count =
        fixture.feature_rows.back().atom_index_offset;
    parse_digest(
        "bde1cd992227894f7c0a8827ba738b3e13c59d7ade8ece6fd0c5e9dd24ea43c1",
        input.feature_geometry_inventory_sha256);
    bg_context *context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    assert(context != nullptr);
    auto *admission = make_admission(fixture, context);
    const Batch batch = produce(context, admission, input);
    assert(batch.output.generated_count == 62);
    assert(batch.output.typed_failure_count == 2);
    for (std::size_t slot = 0; slot < kSlots; ++slot) {
        const auto &row = batch.rows[slot];
        if (slot == 58 || slot == 59) {
            assert(row.status ==
                   BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE);
            assert(row.failure_code ==
                   BG_DOCKING_FIXED64_PRODUCER_FAILURE_FEATURE_GEOMETRY_NOT_AVAILABLE);
            assert(row.coordinates_available == 0);
            assert(row.source_identity_verified == 1);
            assert(row.denominator_preserved == 1);
            assert(row.geometric_admission.status ==
                   BG_DOCKING_GEOMETRIC_ADMISSION_ROW_UPSTREAM_FAILURE);
        } else {
            assert(row.status == BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED);
            assert(row.coordinates_available == 1);
        }
        assert(digest_present(row.row_receipt_sha256));
    }
    assert_authority_false(batch.output);
    bg_docking_geometric_admission_v1_destroy(admission);
    bg_context_destroy(context);
}

void test_equal_cross_kind_receipt_cannot_mask_missing_ligand_geometry() {
    Fixture fixture;
    std::copy_n(
        fixture.atomic_features[0].receipt_sha256,
        32,
        fixture.atomic_features[3].receipt_sha256);
    std::array<bg_docking_fixed64_feature_geometry_row_v1, kFeatureCount - 1>
        feature_rows{};
    std::vector<uint64_t> feature_indices;
    for (std::size_t source = 1; source < kFeatureCount; ++source) {
        auto &target = feature_rows[source - 1];
        target = fixture.feature_rows[source];
        target.atom_index_offset = feature_indices.size();
        const auto first = static_cast<std::size_t>(
            fixture.feature_rows[source].atom_index_offset);
        const auto count = static_cast<std::size_t>(
            fixture.feature_rows[source].atom_index_count);
        feature_indices.insert(
            feature_indices.end(),
            fixture.feature_indices.data() + first,
            fixture.feature_indices.data() + first + count);
    }
    std::copy_n(
        fixture.atomic_features[0].receipt_sha256,
        32,
        feature_rows[2].allocation_feature_receipt_sha256);
    parse_digest(
        "d32faa67a5d4759e5c9e5679207a2b87f94a9ce1877f64a342970c552931fd84",
        feature_rows[2].feature_geometry_receipt_sha256);

    auto input = make_input(fixture);
    input.feature_geometry_count = feature_rows.size();
    input.feature_geometry_rows = feature_rows.data();
    input.feature_atom_index_count = feature_indices.size();
    input.feature_atom_indices = feature_indices.data();
    parse_digest(
        "2c7036e5304e5be45b38e3161fed44471392b168db2669c7675b26ce15f27981",
        input.feature_geometry_inventory_sha256);
    bg_context *context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    assert(context != nullptr);
    auto *admission = make_admission(fixture, context);
    const Batch batch = produce(context, admission, input);
    assert(batch.output.generated_count == 60);
    assert(batch.output.typed_failure_count == 4);
    for (std::size_t slot = 0; slot < kSlots; ++slot) {
        const auto &row = batch.rows[slot];
        if (slot >= 44 && slot < 48) {
            assert(row.status ==
                   BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE);
            assert(row.failure_code ==
                   BG_DOCKING_FIXED64_PRODUCER_FAILURE_FEATURE_GEOMETRY_NOT_AVAILABLE);
            assert(row.source_identity_verified == UINT8_C(1));
            assert(row.coordinates_available == UINT8_C(0));
        } else {
            assert(row.status == BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED);
        }
        assert(row.geometric_identity_verified == UINT8_C(1));
        assert(digest_present(row.row_receipt_sha256));
    }
    assert_authority_false(batch.output);
    bg_docking_geometric_admission_v1_destroy(admission);
    bg_context_destroy(context);
}

void test_single_atom_ligand_preserves_all_fixed64_rows() {
    Fixture fixture;
    fixture.allocation.atomic_feature_count = 0;
    fixture.allocation.atomic_features = nullptr;
    parse_digest(
        "70c6f2b5446c0652d7bbc81537a0ac8a93553e961ecb3c2c40fee2620de1545b",
        fixture.allocation.exact_v11_source.ligand_coordinate_sha256);
    parse_digest(
        "d4379c8a5c7b2291893bd45b047e8736168136002dd646b705a735875a947919",
        fixture.allocation.exact_v11_source.ligand_vdw_radii_sha256);
    parse_digest(
        "49e14fc025f4768dc72e02fe53803e4cd9906d5dc7c89c1f7b08c6fb39b9223a",
        fixture.allocation.exact_v11_source.ligand_heavy_atom_mask_sha256);
    fixture.exact_source.ligand_atom_count = 1;
    std::copy_n(
        fixture.allocation.exact_v11_source.ligand_coordinate_sha256,
        32,
        fixture.exact_source.source.coordinate_sha256);
    for (std::size_t index = 0; index < fixture.v7_evidence.size(); ++index) {
        fixture.v7_sources[index].payload.ligand_atom_count = 1;
        std::copy_n(
            fixture.allocation.exact_v11_source.ligand_coordinate_sha256,
            32,
            fixture.v7_evidence[index].source.coordinate_sha256);
        std::copy_n(
            fixture.allocation.exact_v11_source.ligand_coordinate_sha256,
            32,
            fixture.v7_sources[index].payload.source.coordinate_sha256);
    }
    for (std::size_t index = 0; index < fixture.conformer_evidence.size();
         ++index) {
        fixture.conformer_sources[index].payload.ligand_atom_count = 1;
        std::copy_n(
            fixture.allocation.exact_v11_source.ligand_coordinate_sha256,
            32,
            fixture.conformer_evidence[index].source.coordinate_sha256);
        std::copy_n(
            fixture.allocation.exact_v11_source.ligand_coordinate_sha256,
            32,
            fixture.conformer_sources[index].payload.source.coordinate_sha256);
    }
    for (std::size_t index = 0; index < fixture.retained_evidence.size();
         ++index) {
        fixture.retained_sources[index].payload.ligand_atom_count = 1;
        std::copy_n(
            fixture.allocation.exact_v11_source.ligand_coordinate_sha256,
            32,
            fixture.retained_evidence[index].source.coordinate_sha256);
        std::copy_n(
            fixture.allocation.exact_v11_source.ligand_coordinate_sha256,
            32,
            fixture.retained_sources[index].payload.source.coordinate_sha256);
    }

    auto input = make_input(fixture);
    input.feature_geometry_count = 0;
    input.feature_geometry_rows = nullptr;
    input.feature_atom_index_count = 0;
    input.feature_atom_indices = nullptr;
    std::fill(
        std::begin(input.feature_geometry_inventory_sha256),
        std::end(input.feature_geometry_inventory_sha256),
        UINT8_C(0));

    bg_context *context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    assert(context != nullptr);
    auto *admission = make_admission(fixture, context, {0.0, 0.0, 0.0}, 1);
    const Batch batch = produce(context, admission, input);
    assert(batch.output.row_count == kSlots);
    assert(batch.output.coordinate_count == kSlots);
    assert(batch.output.generated_count == 28);
    assert(batch.output.typed_failure_count == 36);
    for (std::size_t slot = 0; slot < kSlots; ++slot) {
        const auto &row = batch.rows[slot];
        assert(row.slot_index == slot);
        assert(row.ligand_atom_count == 1);
        assert(row.coordinate_offset == slot);
        assert(row.denominator_preserved == UINT8_C(1));
        assert(row.geometric_identity_verified == UINT8_C(1));
        assert(digest_present(row.row_receipt_sha256));
        if (slot < 24 || slot >= 60) {
            assert(row.status == BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED);
            assert(row.coordinates_available == UINT8_C(1));
        } else {
            assert(row.status ==
                   BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE);
            assert(row.coordinates_available == UINT8_C(0));
        }
    }
    assert_authority_false(batch.output);
    bg_docking_geometric_admission_v1_destroy(admission);
    bg_context_destroy(context);
}

void test_ready_anchor_without_geometry_is_typed() {
    const Fixture fixture;
    auto input = make_input(fixture);
    input.feature_geometry_count = 0;
    input.feature_geometry_rows = nullptr;
    input.feature_atom_index_count = 0;
    input.feature_atom_indices = nullptr;
    std::fill(
        std::begin(input.feature_geometry_inventory_sha256),
        std::end(input.feature_geometry_inventory_sha256), UINT8_C(0));
    bg_context *context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    assert(context != nullptr);
    auto *admission = make_admission(fixture, context);
    const Batch batch = produce(context, admission, input);
    assert(batch.output.generated_count == 48);
    assert(batch.output.typed_failure_count == 16);
    for (std::size_t slot = 44; slot < 60; ++slot) {
        const auto &row = batch.rows[slot];
        assert(row.status == BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE);
        assert(row.failure_code ==
               BG_DOCKING_FIXED64_PRODUCER_FAILURE_FEATURE_GEOMETRY_NOT_AVAILABLE);
        assert(row.placement_kind ==
               BG_DOCKING_FIXED64_PRODUCER_PLACEMENT_SINGLE_ANCHOR);
        assert(row.source_identity_verified == 1);
        assert(row.coordinates_available == 0);
        assert(row.placement_quaternion_x == 0.0);
        assert(row.placement_quaternion_y == 0.0);
        assert(row.placement_quaternion_z == 0.0);
        assert(row.placement_quaternion_w == 0.0);
        assert(row.geometric_admission.status ==
               BG_DOCKING_GEOMETRIC_ADMISSION_ROW_UPSTREAM_FAILURE);
        assert(digest_present(row.row_receipt_sha256));
    }
    assert_authority_false(batch.output);
    bg_docking_geometric_admission_v1_destroy(admission);
    bg_context_destroy(context);
}

void test_component_typed_failure_is_retained() {
    const Fixture fixture;
    const auto input = make_input(fixture);
    for (const bg_backend backend : {
             BG_BACKEND_CPP_CPU_REFERENCE, BG_BACKEND_RUST_CPU,
             BG_BACKEND_HIP_SAFE, BG_BACKEND_HIP_FAST}) {
        bg_context *context = make_context(backend);
        if (context == nullptr) continue;
        auto *admission = make_admission(
            fixture, context,
            {fixture.receptor_x[2], fixture.receptor_y[2],
             fixture.receptor_z[2]});
        const Batch batch = produce(context, admission, input);
        assert(batch.output.row_count == kSlots);
        assert(batch.output.generated_count < kSlots);
        assert(batch.output.generated_count + batch.output.typed_failure_count ==
               kSlots);
        bool found = false;
        for (std::size_t slot = 44; slot < 60; ++slot) {
            const auto &row = batch.rows[slot];
            if (row.failure_code !=
                BG_DOCKING_FIXED64_PRODUCER_FAILURE_SINGLE_ANCHOR_TYPED_FAILURE) {
                continue;
            }
            found = true;
            assert(row.coordinates_available == 0);
            assert(row.placement_quaternion_x == 0.0);
            assert(row.placement_quaternion_y == 0.0);
            assert(row.placement_quaternion_z == 0.0);
            assert(row.placement_quaternion_w == 0.0);
            assert(row.component_failure_code != 0);
            assert(row.geometric_admission.status ==
                   BG_DOCKING_GEOMETRIC_ADMISSION_ROW_UPSTREAM_FAILURE);
            assert(row.denominator_preserved == 1);
        }
        assert(found);
        assert_authority_false(batch.output);
        bg_docking_geometric_admission_v1_destroy(admission);
        bg_context_destroy(context);
    }
}

void test_invalid_input_capacity_and_alias_are_transactional() {
    Fixture fixture;
    auto input = make_input(fixture);
    bg_context *context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    assert(context != nullptr);
    auto *admission = make_admission(fixture, context);
    Batch batch{};
    assert(bg_docking_fixed64_producer_output_v1_init(&batch.output) ==
           BG_STATUS_OK);
    batch.output.row_capacity = kSlots;
    batch.output.coordinate_capacity = kCoordinates - 1;
    batch.output.rows = batch.rows.data();
    batch.output.x_angstrom = batch.x.data();
    batch.output.y_angstrom = batch.y.data();
    batch.output.z_angstrom = batch.z.data();
    std::fill(batch.x.begin(), batch.x.end(), 91.0);
    std::fill(batch.y.begin(), batch.y.end(), 81.0);
    std::fill(batch.z.begin(), batch.z.end(), 71.0);
    std::memset(batch.rows.data(), 0xA5, sizeof(batch.rows));
    const auto output_before = object_bytes(batch.output);
    const auto rows_before = batch.rows;
    const auto x_before = batch.x;
    assert(bg_docking_fixed64_producer_v1_run(
               context, admission, &input, &batch.output) ==
           BG_STATUS_BUFFER_TOO_SMALL);
    assert(object_bytes(batch.output) == output_before);
    assert(std::memcmp(
               batch.rows.data(), rows_before.data(), sizeof(batch.rows)) == 0);
    assert(batch.x == x_before);

    batch.output.coordinate_capacity = kCoordinates;
    batch.output.x_angstrom = fixture.source_x.data();
    const auto alias_before = object_bytes(batch.output);
    const auto source_before = fixture.source_x;
    assert(bg_docking_fixed64_producer_v1_run(
               context, admission, &input, &batch.output) ==
           BG_STATUS_INVALID_ARGUMENT);
    assert(object_bytes(batch.output) == alias_before);
    assert(fixture.source_x == source_before);

    batch.output.x_angstrom = batch.x.data();
    input.feature_geometry_inventory_sha256[0] ^= UINT8_C(1);
    const auto crosswire_before = object_bytes(batch.output);
    assert(bg_docking_fixed64_producer_v1_run(
               context, admission, &input, &batch.output) ==
           BG_STATUS_INVALID_ARGUMENT);
    assert(object_bytes(batch.output) == crosswire_before);
    assert(std::memcmp(
               batch.rows.data(), rows_before.data(), sizeof(batch.rows)) == 0);
    assert(batch.x == x_before);
    bg_docking_geometric_admission_v1_destroy(admission);
    bg_context_destroy(context);
}

void test_oversized_source_count_is_rejected_before_narrowing() {
    const Fixture fixture;
    auto input = make_input(fixture);
    input.v7_control_source_count = UINT64_MAX;
    bg_context *context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    assert(context != nullptr);
    auto *admission = make_admission(fixture, context);
    Batch batch{};
    assert(bg_docking_fixed64_producer_output_v1_init(&batch.output) ==
           BG_STATUS_OK);
    batch.output.row_capacity = batch.rows.size();
    batch.output.coordinate_capacity = batch.x.size();
    batch.output.rows = batch.rows.data();
    batch.output.x_angstrom = batch.x.data();
    batch.output.y_angstrom = batch.y.data();
    batch.output.z_angstrom = batch.z.data();
    std::memset(batch.rows.data(), 0xA5, sizeof(batch.rows));
    std::fill(batch.x.begin(), batch.x.end(), 91.0);
    std::fill(batch.y.begin(), batch.y.end(), 81.0);
    std::fill(batch.z.begin(), batch.z.end(), 71.0);
    const auto output_before = object_bytes(batch.output);
    const auto rows_before = batch.rows;
    const auto x_before = batch.x;
    const auto y_before = batch.y;
    const auto z_before = batch.z;
    assert(bg_docking_fixed64_producer_v1_run(
               context, admission, &input, &batch.output) ==
           BG_STATUS_CAPACITY_OVERFLOW);
    assert(object_bytes(batch.output) == output_before);
    assert(std::memcmp(
               batch.rows.data(), rows_before.data(), sizeof(batch.rows)) == 0);
    assert(batch.x == x_before && batch.y == y_before && batch.z == z_before);
    bg_docking_geometric_admission_v1_destroy(admission);
    bg_context_destroy(context);
}

void assert_complete_pipeline_authority_false(
    const bg_docking_fixed64_pipeline_output_v1 &output) {
    assert(output.result_dependent_input_consumed == UINT8_C(0));
    assert(output.fallback_allowed == UINT8_C(0));
    assert(output.denominator_preserved == UINT8_C(1));
    assert(output.molecular_execution_authorized == UINT8_C(0));
    assert(output.reservation_authorized == UINT8_C(0));
    assert(output.benchmark_execution_authorized == UINT8_C(0));
    assert(output.existing_rank_auto_change_authorized == UINT8_C(0));
    assert(output.customer_pose_emission_authorized == UINT8_C(0));
    assert(output.production_claim_authorized == UINT8_C(0));
    assert(output.scientific_claim_authorized == UINT8_C(0));
}

CompletePipelineResult run_complete_pipeline(
    bg_backend backend,
    const Fixture &fixture) {
    bg_context *context = make_context(backend);
    assert(context != nullptr);
    auto *pipeline = make_complete_pipeline(fixture, context);
    bg_backend observed = BG_BACKEND_AUTO;
    assert(bg_docking_fixed64_pipeline_v1_get_backend(pipeline, &observed) ==
           BG_STATUS_OK);
    assert(observed == backend);
    CompletePipelineResult result{};
    const bg_status status =
        run_complete_pipeline_into(context, pipeline, fixture, &result);
    if (status != BG_STATUS_OK) {
        std::fprintf(
            stderr,
            "complete pipeline backend %d failed: %s\n",
            backend,
            bg_last_error_message());
    }
    assert(status == BG_STATUS_OK);
    bg_docking_fixed64_pipeline_v1_destroy(pipeline);
    bg_context_destroy(context);
    return result;
}

void assert_complete_pipeline_v2_authority_false(
    const CompletePipelineResult &result) {
    const auto &output = result.output_v2;
    assert(output.result_dependent_input_consumed == UINT8_C(0));
    assert(output.fallback_allowed == UINT8_C(0));
    assert(output.denominator_preserved == UINT8_C(1));
    assert(output.molecular_execution_authorized == UINT8_C(0));
    assert(output.reservation_authorized == UINT8_C(0));
    assert(output.benchmark_execution_authorized == UINT8_C(0));
    assert(output.existing_rank_auto_change_authorized == UINT8_C(0));
    assert(output.customer_pose_emission_authorized == UINT8_C(0));
    assert(output.production_claim_authorized == UINT8_C(0));
    assert(output.scientific_claim_authorized == UINT8_C(0));
    assert_authority_false(result.producer.output);
    const auto &post = result.post_admission_output;
    assert(post.molecular_execution_authorized == UINT8_C(0));
    assert(post.reservation_authorized == UINT8_C(0));
    assert(post.benchmark_execution_authorized == UINT8_C(0));
    assert(post.existing_rank_auto_change_authorized == UINT8_C(0));
    assert(post.customer_pose_emission_authorized == UINT8_C(0));
    assert(post.production_claim_authorized == UINT8_C(0));
    assert(post.scientific_claim_authorized == UINT8_C(0));
}

CompletePipelineResult run_complete_pipeline_v2(
    bg_backend backend,
    const Fixture &fixture,
    double torsion_internal_overlap_weight = 1.0,
    double torsion_receptor_overlap_scale = 1.0) {
    bg_context *context = make_context(backend);
    assert(context != nullptr);
    auto *pipeline = make_complete_pipeline_v2(
        fixture,
        context,
        torsion_internal_overlap_weight,
        torsion_receptor_overlap_scale);
    bg_backend observed = BG_BACKEND_AUTO;
    assert(bg_docking_fixed64_pipeline_v2_get_backend(pipeline, &observed) ==
           BG_STATUS_OK);
    assert(observed == backend);
    CompletePipelineResult result{};
    const bg_status status =
        run_complete_pipeline_v2_into(context, pipeline, fixture, &result);
    if (status != BG_STATUS_OK) {
        std::fprintf(
            stderr,
            "complete pipeline v2 backend %d failed: %s\n",
            backend,
            bg_last_error_message());
    }
    assert(status == BG_STATUS_OK);
    bg_docking_fixed64_pipeline_v2_destroy(pipeline);
    bg_context_destroy(context);
    return result;
}

void assert_numeric_parity(double left, double right, double tolerance) {
    assert(std::isfinite(left));
    assert(std::isfinite(right));
    const double scale = std::max({1.0, std::abs(left), std::abs(right)});
    assert(std::abs(left - right) <= tolerance * scale);
}

void assert_complete_pipeline_v2_evidence(
    const CompletePipelineResult &result,
    bg_backend backend) {
    const auto &output = result.output_v2;
    const auto &post_output = result.post_admission_output;
    assert(output.row_count == kSlots);
    assert(output.backend == backend);
    assert(output.unit_system == BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);
    assert(result.producer.output.row_count == kSlots);
    assert(post_output.row_count == kSlots);
    assert(post_output.unit_system == BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL);
    assert(output.generated_count == result.producer.output.generated_count);
    assert(output.initial_admitted_count <= output.generated_count);
    assert(
        output.refined_count ==
        output.post_admitted_count + output.post_rejected_count);
    assert(output.scored_count == output.post_admitted_count);
    assert_complete_pipeline_v2_authority_false(result);
    assert(digest_present(output.allocation_receipt_sha256));
    assert(digest_present(output.source_bundle_receipt_sha256));
    assert(digest_present(output.admission_context_receipt_sha256));
    assert(digest_present(output.refinement_context_receipt_sha256));
    assert(digest_present(output.scorer_context_receipt_sha256));
    assert(digest_present(output.validity_context_receipt_sha256));
    assert(digest_present(output.component_binding_receipt_sha256));
    assert(digest_present(output.producer_batch_receipt_sha256));
    assert(digest_present(output.refinement_policy_receipt_sha256));
    assert(digest_present(output.refinement_batch_receipt_sha256));
    assert(digest_present(output.post_admission_policy_receipt_sha256));
    assert(digest_present(output.post_admission_batch_receipt_sha256));
    assert(digest_present(output.scorer_batch_receipt_sha256));
    assert(digest_present(output.validity_batch_receipt_sha256));
    assert(digest_present(output.ranking_batch_receipt_sha256));
    assert(digest_present(output.cluster_batch_receipt_sha256));
    assert(digest_present(output.pipeline_batch_receipt_sha256));
    assert(digest_present(post_output.batch_receipt_sha256));
    assert(std::memcmp(
               output.post_admission_batch_receipt_sha256,
               post_output.batch_receipt_sha256,
               32) == 0);

    uint64_t initial_admitted = 0;
    uint64_t refined = 0;
    uint64_t post_admitted = 0;
    uint64_t post_rejected = 0;
    uint64_t scored = 0;
    uint64_t valid = 0;
    uint64_t clusters = 0;
    for (std::size_t slot = 0; slot < kSlots; ++slot) {
        const auto &summary = result.rows_v2[slot];
        const auto &producer = result.producer.rows[slot];
        const auto &refinement = result.refinement_rows[slot];
        const auto &post = result.post_admission_rows[slot];
        const auto &scorer = result.scorer_rows[slot];
        const auto &validity = result.validity_rows[slot];
        const auto &ranking = result.ranking_rows[slot];
        const auto &cluster = result.cluster_rows[slot];
        assert(summary.slot_index == slot);
        assert(producer.slot_index == slot);
        assert(refinement.slot_index == slot);
        assert(post.slot_index == slot);
        assert(scorer.slot_index == slot);
        assert(validity.slot_index == slot);
        assert(ranking.slot_index == slot);
        assert(cluster.slot_index == slot);
        assert(summary.producer_status == producer.status);
        assert(summary.producer_failure_code == producer.failure_code);
        assert(
            summary.initial_admission_decision ==
            producer.geometric_admission.decision);
        assert(summary.refinement_status == refinement.status);
        assert(
            summary.refinement_failure_stage ==
            refinement.failure_stage);
        assert(summary.post_admission_status == post.status);
        assert(summary.post_admission_failure_code == post.failure_code);
        assert(summary.post_admission_decision == post.decision);
        assert(summary.post_admission_rank_eligible == post.rank_eligible);
        assert(summary.scorer_status == scorer.status);
        assert(summary.scorer_failure_code == scorer.failure_code);
        assert(summary.validity_status == validity.status);
        assert(summary.validity_failure_code == validity.failure_code);
        assert(summary.stable_rank == ranking.stable_rank);
        assert(summary.stable_valid_rank == ranking.stable_valid_rank);
        assert(summary.cluster_status == cluster.status);
        assert(summary.cluster_id == cluster.cluster_id);
        assert(summary.cluster_rank == cluster.cluster_rank);
        assert(summary.top_k_rank == cluster.top_k_rank);
        assert(digest_present(summary.producer_row_receipt_sha256));
        assert(digest_present(summary.refinement_evidence_sha256));
        assert(digest_present(summary.post_admission_row_receipt_sha256));
        assert(digest_present(summary.scorer_evidence_sha256));
        assert(digest_present(summary.validity_evidence_sha256));
        assert(digest_present(summary.ranking_evidence_sha256));
        assert(digest_present(summary.cluster_evidence_sha256));
        assert(digest_present(summary.row_receipt_sha256));
        assert(std::memcmp(
                   summary.post_admission_row_receipt_sha256,
                   post.row_receipt_sha256,
                   32) == 0);
        if (summary.initial_admission_decision ==
            BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED) {
            ++initial_admitted;
        }
        const bool coordinate_ready =
            refinement.status ==
                BG_DOCKING_FIXED64_REFINEMENT_ROW_COORDINATE_READY &&
            refinement.coordinate_available == UINT8_C(1);
        if (coordinate_ready) {
            ++refined;
            assert(digest_present(summary.final_coordinate_sha256));
            assert(post.status == BG_DOCKING_GEOMETRIC_ADMISSION_ROW_EVALUATED);
            assert(
                post.failure_code ==
                BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_NONE);
            assert(post.ligand_atom_count == kAtoms);
            assert(post.receptor_atom_count == kAtoms);
            assert(post.exact_pair_count == kAtoms * kAtoms);
            assert(std::isfinite(post.raw_minimum_distance_angstrom));
            assert(std::isfinite(post.minimum_vdw_surface_gap_angstrom));
            assert(std::isfinite(post.minimum_vdw_ratio));
            assert(std::isfinite(post.sphere_overlap_proxy_angstrom3));
            assert(std::isfinite(post.pocket_escape_angstrom));
            const bool admitted =
                post.decision ==
                    BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED &&
                post.rank_eligible == UINT8_C(1);
            if (admitted) {
                ++post_admitted;
                assert(
                    refinement.downstream_candidate_state ==
                    BG_DOCKING_SCORER_V1_CANDIDATE_ACTIVE);
                assert(scorer.status == BG_DOCKING_SCORER_V1_ROW_SCORED);
                assert(scorer.failure_code == BG_DOCKING_SCORER_V1_FAILURE_NONE);
                assert(ranking.rank_eligible == UINT8_C(1));
                assert(ranking.stable_rank != UINT32_C(0));
            } else {
                ++post_rejected;
                assert(
                    post.decision ==
                    BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_SEVERE_PENETRATION_REJECTED);
                assert(post.rank_eligible == UINT8_C(0));
                assert(
                    refinement.downstream_candidate_state ==
                    BG_DOCKING_SCORER_V1_CANDIDATE_INACTIVE);
                assert(scorer.status == BG_DOCKING_SCORER_V1_ROW_TYPED_FAILURE);
                assert(
                    scorer.failure_code ==
                    BG_DOCKING_SCORER_V1_FAILURE_UPSTREAM_NOT_ADMITTED);
                assert(
                    validity.status ==
                    BG_DOCKING_POSE_VALIDITY_ROW_UPSTREAM_SCORER_FAILURE);
                assert(
                    validity.failure_code ==
                    BG_DOCKING_POSE_VALIDITY_FAILURE_UPSTREAM_SCORER);
                assert(ranking.rank_eligible == UINT8_C(0));
                assert(ranking.valid_rank_eligible == UINT8_C(0));
                assert(ranking.stable_rank == UINT32_C(0));
                assert(ranking.stable_valid_rank == UINT32_C(0));
                assert(!digest_present(ranking.coordinate_sha256));
                assert(
                    cluster.status ==
                    BG_DOCKING_RMSD_CLUSTER_ROW_UPSTREAM_NOT_VALID);
                assert(cluster.cluster_eligible == UINT8_C(0));
            }
        } else {
            assert(!digest_present(summary.final_coordinate_sha256));
            assert(
                post.status ==
                BG_DOCKING_GEOMETRIC_ADMISSION_ROW_UPSTREAM_FAILURE);
            assert(
                post.failure_code ==
                BG_DOCKING_GEOMETRIC_ADMISSION_FAILURE_UPSTREAM_NOT_AVAILABLE);
            assert(
                post.decision ==
                BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_NOT_EVALUATED);
            assert(post.rank_eligible == UINT8_C(0));
            assert(
                scorer.failure_code ==
                BG_DOCKING_SCORER_V1_FAILURE_UPSTREAM_NOT_ADMITTED);
            assert(ranking.rank_eligible == UINT8_C(0));
            assert(ranking.stable_rank == UINT32_C(0));
            assert(!digest_present(ranking.coordinate_sha256));
        }
        if (scorer.status == BG_DOCKING_SCORER_V1_ROW_SCORED) ++scored;
        if (validity.status == BG_DOCKING_POSE_VALIDITY_ROW_EVALUATED &&
            validity.blocker_mask == UINT32_C(0)) {
            ++valid;
        }
        if (cluster.representative == UINT8_C(1)) ++clusters;
    }
    assert(initial_admitted == output.initial_admitted_count);
    assert(refined == output.refined_count);
    assert(post_admitted == output.post_admitted_count);
    assert(post_rejected == output.post_rejected_count);
    assert(scored == output.scored_count);
    assert(valid == output.valid_count);
    assert(clusters == output.cluster_count);
}

void assert_complete_pipeline_v2_parity(
    const CompletePipelineResult &reference,
    const CompletePipelineResult &observed,
    double tolerance) {
    const auto &left_output = reference.output_v2;
    const auto &right_output = observed.output_v2;
    assert(left_output.row_count == right_output.row_count);
    assert(left_output.generated_count == right_output.generated_count);
    assert(
        left_output.initial_admitted_count ==
        right_output.initial_admitted_count);
    assert(left_output.refined_count == right_output.refined_count);
    assert(
        left_output.post_admitted_count ==
        right_output.post_admitted_count);
    assert(
        left_output.post_rejected_count ==
        right_output.post_rejected_count);
    assert(left_output.scored_count == right_output.scored_count);
    assert(left_output.valid_count == right_output.valid_count);
    assert(left_output.cluster_count == right_output.cluster_count);
    for (std::size_t slot = 0; slot < kSlots; ++slot) {
        const auto &left = reference.rows_v2[slot];
        const auto &right = observed.rows_v2[slot];
        assert(left.slot_index == right.slot_index);
        assert(left.producer_status == right.producer_status);
        assert(left.producer_failure_code == right.producer_failure_code);
        assert(left.initial_admission_decision == right.initial_admission_decision);
        assert(left.requested_refinement_mode == right.requested_refinement_mode);
        assert(left.effective_refinement_mode == right.effective_refinement_mode);
        assert(left.refinement_status == right.refinement_status);
        assert(left.refinement_failure_stage == right.refinement_failure_stage);
        assert(left.post_admission_status == right.post_admission_status);
        assert(
            left.post_admission_failure_code ==
            right.post_admission_failure_code);
        assert(left.post_admission_decision == right.post_admission_decision);
        assert(
            left.post_admission_rank_eligible ==
            right.post_admission_rank_eligible);
        assert(left.scorer_status == right.scorer_status);
        assert(left.scorer_failure_code == right.scorer_failure_code);
        assert(left.validity_status == right.validity_status);
        assert(left.validity_failure_code == right.validity_failure_code);
        assert(left.stable_rank == right.stable_rank);
        assert(left.stable_valid_rank == right.stable_valid_rank);
        assert(left.cluster_status == right.cluster_status);
        assert(left.cluster_id == right.cluster_id);
        assert(left.cluster_rank == right.cluster_rank);
        assert(left.top_k_rank == right.top_k_rank);

        const auto &left_post = reference.post_admission_rows[slot];
        const auto &right_post = observed.post_admission_rows[slot];
        assert(left_post.status == right_post.status);
        assert(left_post.failure_code == right_post.failure_code);
        assert(left_post.decision == right_post.decision);
        assert(left_post.rank_eligible == right_post.rank_eligible);
        assert(left_post.ligand_atom_count == right_post.ligand_atom_count);
        assert(left_post.receptor_atom_count == right_post.receptor_atom_count);
        assert(left_post.exact_pair_count == right_post.exact_pair_count);
        assert(
            left_post.penetration_pair_count ==
            right_post.penetration_pair_count);
        assert(
            left_post.unique_ligand_penetration_atom_count ==
            right_post.unique_ligand_penetration_atom_count);
        assert(
            left_post.unique_ligand_heavy_atom_penetration_count ==
            right_post.unique_ligand_heavy_atom_penetration_count);
        for (const auto &[lhs, rhs] : {
                 std::pair{
                     left_post.raw_minimum_distance_angstrom,
                     right_post.raw_minimum_distance_angstrom},
                 std::pair{
                     left_post.minimum_vdw_surface_gap_angstrom,
                     right_post.minimum_vdw_surface_gap_angstrom},
                 std::pair{
                     left_post.minimum_vdw_ratio,
                     right_post.minimum_vdw_ratio},
                 std::pair{
                     left_post.sphere_overlap_proxy_angstrom3,
                     right_post.sphere_overlap_proxy_angstrom3},
                 std::pair{
                     left_post.pocket_escape_angstrom,
                     right_post.pocket_escape_angstrom},
             }) {
            assert_numeric_parity(lhs, rhs, tolerance);
        }

        const auto &left_scorer = reference.scorer_rows[slot];
        const auto &right_scorer = observed.scorer_rows[slot];
        assert(left_scorer.status == right_scorer.status);
        assert(left_scorer.failure_code == right_scorer.failure_code);
        for (std::size_t term = 0; term < BG_DOCKING_SCORER_V1_TERM_COUNT;
             ++term) {
            assert_numeric_parity(
                left_scorer.weighted_terms[term],
                right_scorer.weighted_terms[term],
                tolerance);
        }
        assert_numeric_parity(
            left_scorer.total_score,
            right_scorer.total_score,
            tolerance);
        assert(
            left_scorer.receptor_candidate_pair_count ==
            right_scorer.receptor_candidate_pair_count);
        assert(left_scorer.ligand_pair_count == right_scorer.ligand_pair_count);
        assert(left_scorer.hbond_count == right_scorer.hbond_count);
        assert(
            left_scorer.hydrophobic_contact_count ==
            right_scorer.hydrophobic_contact_count);
        assert(
            left_scorer.buried_polar_count ==
            right_scorer.buried_polar_count);

        const auto &left_validity = reference.validity_rows[slot];
        const auto &right_validity = observed.validity_rows[slot];
        assert(left_validity.status == right_validity.status);
        assert(left_validity.failure_code == right_validity.failure_code);
        assert(
            left_validity.upstream_scorer_failure_code ==
            right_validity.upstream_scorer_failure_code);
        assert(
            left_validity.passed_check_mask ==
            right_validity.passed_check_mask);
        assert(left_validity.blocker_mask == right_validity.blocker_mask);
        assert(left_validity.observed_count == right_validity.observed_count);
        assert(left_validity.atom_count == right_validity.atom_count);
        assert(
            left_validity.evaluated_ligand_nonbonded_pair_count ==
            right_validity.evaluated_ligand_nonbonded_pair_count);
        assert(
            left_validity.excluded_ligand_pair_count ==
            right_validity.excluded_ligand_pair_count);
        assert(
            left_validity.evaluated_receptor_ligand_pair_count ==
            right_validity.evaluated_receptor_ligand_pair_count);
        assert(
            left_validity.declared_chirality_center_count ==
            right_validity.declared_chirality_center_count);
        assert(
            left_validity.element_vdw_ligand_pair_count ==
            right_validity.element_vdw_ligand_pair_count);
        assert(
            left_validity.element_vdw_ligand_severe_overlap_count ==
            right_validity.element_vdw_ligand_severe_overlap_count);
        assert(
            left_validity.element_vdw_receptor_candidate_pair_count ==
            right_validity.element_vdw_receptor_candidate_pair_count);
        assert(
            left_validity.element_vdw_receptor_full_cartesian_pair_count ==
            right_validity.element_vdw_receptor_full_cartesian_pair_count);
        assert(
            left_validity.element_vdw_receptor_cell_count ==
            right_validity.element_vdw_receptor_cell_count);
        assert(
            left_validity.element_vdw_receptor_severe_overlap_count ==
            right_validity.element_vdw_receptor_severe_overlap_count);
        for (const auto &[lhs, rhs] : {
                 std::pair{
                     left_validity.rotation_orthogonality_max_error,
                     right_validity.rotation_orthogonality_max_error},
                 std::pair{
                     left_validity.rotation_determinant,
                     right_validity.rotation_determinant},
                 std::pair{
                     left_validity.max_bond_length_delta_angstrom,
                     right_validity.max_bond_length_delta_angstrom},
                 std::pair{
                     left_validity.minimum_ligand_nonbonded_distance_angstrom,
                     right_validity.minimum_ligand_nonbonded_distance_angstrom},
                 std::pair{
                     left_validity.minimum_receptor_ligand_distance_angstrom,
                     right_validity.minimum_receptor_ligand_distance_angstrom},
                 std::pair{
                     left_validity.minimum_declared_chiral_volume,
                     right_validity.minimum_declared_chiral_volume},
                 std::pair{
                     left_validity.maximum_pocket_center_distance_angstrom,
                     right_validity.maximum_pocket_center_distance_angstrom},
                 std::pair{
                     left_validity.element_vdw_ligand_minimum_distance_angstrom,
                     right_validity.element_vdw_ligand_minimum_distance_angstrom},
                 std::pair{
                     left_validity.element_vdw_ligand_minimum_ratio,
                     right_validity.element_vdw_ligand_minimum_ratio},
                 std::pair{
                     left_validity.element_vdw_receptor_minimum_distance_angstrom,
                     right_validity.element_vdw_receptor_minimum_distance_angstrom},
                 std::pair{
                     left_validity.element_vdw_receptor_minimum_ratio,
                     right_validity.element_vdw_receptor_minimum_ratio},
             }) {
            assert_numeric_parity(lhs, rhs, tolerance);
        }
        for (std::size_t axis = 0; axis < 3; ++axis) {
            for (std::size_t atom = 0; atom < kAtoms; ++atom) {
                const std::size_t index = slot * kAtoms + atom;
                assert_numeric_parity(
                    reference.final_coordinates[axis][index],
                    observed.final_coordinates[axis][index],
                    tolerance);
            }
        }
    }
}

void assert_complete_pipeline_parity(
    const CompletePipelineResult &reference,
    const CompletePipelineResult &observed,
    double tolerance) {
    assert(reference.output.row_count == observed.output.row_count);
    assert(reference.output.generated_count == observed.output.generated_count);
    assert(
        reference.output.initial_admitted_count ==
        observed.output.initial_admitted_count);
    assert(reference.output.refined_count == observed.output.refined_count);
    assert(reference.output.scored_count == observed.output.scored_count);
    assert(reference.output.valid_count == observed.output.valid_count);
    assert(reference.output.cluster_count == observed.output.cluster_count);
    for (std::size_t slot = 0; slot < kSlots; ++slot) {
        const auto &left = reference.rows[slot];
        const auto &right = observed.rows[slot];
        assert(left.slot_index == slot);
        assert(left.producer_status == right.producer_status);
        assert(left.producer_failure_code == right.producer_failure_code);
        assert(left.initial_admission_decision == right.initial_admission_decision);
        assert(left.requested_refinement_mode == right.requested_refinement_mode);
        assert(left.effective_refinement_mode == right.effective_refinement_mode);
        assert(left.refinement_status == right.refinement_status);
        assert(left.refinement_failure_stage == right.refinement_failure_stage);
        assert(left.scorer_status == right.scorer_status);
        assert(left.scorer_failure_code == right.scorer_failure_code);
        assert(left.validity_status == right.validity_status);
        assert(left.validity_failure_code == right.validity_failure_code);
        assert(left.stable_rank == right.stable_rank);
        assert(left.stable_valid_rank == right.stable_valid_rank);
        assert(left.cluster_status == right.cluster_status);
        assert(left.cluster_id == right.cluster_id);
        assert(left.cluster_rank == right.cluster_rank);
        assert(left.top_k_rank == right.top_k_rank);
        assert(digest_present(left.producer_row_receipt_sha256));
        assert(digest_present(left.refinement_evidence_sha256));
        assert(digest_present(left.scorer_evidence_sha256));
        assert(digest_present(left.validity_evidence_sha256));
        assert(digest_present(left.ranking_evidence_sha256));
        assert(digest_present(left.cluster_evidence_sha256));
        assert(digest_present(left.row_receipt_sha256));
        for (std::size_t axis = 0; axis < 3; ++axis) {
            for (std::size_t atom = 0; atom < kAtoms; ++atom) {
                const std::size_t index = slot * kAtoms + atom;
                const double lhs = reference.final_coordinates[axis][index];
                const double rhs = observed.final_coordinates[axis][index];
                const double scale = std::max({1.0, std::abs(lhs), std::abs(rhs)});
                assert(std::abs(lhs - rhs) <= tolerance * scale);
            }
        }
    }
}

void test_complete_pipeline_exact64_repeat_and_backend_parity() {
    const Fixture fixture;
    assert(std::strcmp(
               bg_docking_fixed64_pipeline_v1_profile_id(),
               "betelgeuze.engine_v2_native_fixed64_complete_pipeline/1.0.0") ==
           0);
    const auto reference =
        run_complete_pipeline(BG_BACKEND_CPP_CPU_REFERENCE, fixture);
    bg_context *reuse_context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    assert(reuse_context != nullptr);
    auto *reused_pipeline = make_complete_pipeline(fixture, reuse_context);
    CompletePipelineResult reused{};
    assert(run_complete_pipeline_into(
               reuse_context,
               reused_pipeline,
               fixture,
               &reused,
               false,
               false,
               false,
               nullptr,
               true) == BG_STATUS_OK);
    bg_docking_fixed64_pipeline_v1_destroy(reused_pipeline);
    bg_context_destroy(reuse_context);
    const auto repeated =
        run_complete_pipeline(BG_BACKEND_CPP_CPU_REFERENCE, fixture);
    assert(reference.output.row_count == kSlots);
    assert(reference.output.generated_count == kSlots);
    assert(reference.output.generated_count <= reference.output.row_count);
    assert_complete_pipeline_authority_false(reference.output);
    assert(digest_present(reference.output.allocation_receipt_sha256));
    assert(digest_present(reference.output.source_bundle_receipt_sha256));
    assert(digest_present(reference.output.admission_context_receipt_sha256));
    assert(digest_present(reference.output.refinement_context_receipt_sha256));
    assert(digest_present(reference.output.scorer_context_receipt_sha256));
    assert(digest_present(reference.output.validity_context_receipt_sha256));
    assert(digest_present(reference.output.component_binding_receipt_sha256));
    assert(digest_present(reference.output.producer_batch_receipt_sha256));
    assert(digest_present(reference.output.refinement_policy_receipt_sha256));
    assert(digest_present(reference.output.refinement_batch_receipt_sha256));
    assert(digest_present(reference.output.scorer_batch_receipt_sha256));
    assert(digest_present(reference.output.validity_batch_receipt_sha256));
    assert(digest_present(reference.output.ranking_batch_receipt_sha256));
    assert(digest_present(reference.output.cluster_batch_receipt_sha256));
    assert(digest_present(reference.output.pipeline_batch_receipt_sha256));
    assert(std::memcmp(
               reference.rows.data(),
               repeated.rows.data(),
               sizeof(reference.rows)) == 0);
    assert(std::memcmp(
               reference.output.pipeline_batch_receipt_sha256,
               repeated.output.pipeline_batch_receipt_sha256,
               32) == 0);
    for (const bg_backend backend : {
             BG_BACKEND_RUST_CPU, BG_BACKEND_HIP_SAFE, BG_BACKEND_HIP_FAST}) {
        bg_context *availability = make_context(backend);
        if (availability == nullptr) continue;
        bg_context_destroy(availability);
        const auto observed = run_complete_pipeline(backend, fixture);
        assert_complete_pipeline_authority_false(observed.output);
        assert_complete_pipeline_parity(
            reference,
            observed,
            backend == BG_BACKEND_RUST_CPU ? 4.0e-12 : 8.0e-9);
    }
}

void test_complete_pipeline_v2_post_admission_exact64_repeat_and_cpu_parity() {
    Fixture fixture;
    fixture.ligand_radii[3] = 5.1059;
    parse_digest(
        "a8cabad229ff09acc8d2df8e0ed620afc6e1956953aafbd7e8f57cb7a3af0416",
        fixture.allocation.exact_v11_source.ligand_vdw_radii_sha256);
    std::fill(
        fixture.refinement_modes.begin(),
        fixture.refinement_modes.end(),
        BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V3_LANE);
    std::fill(
        fixture.rigid_steps.begin(), fixture.rigid_steps.end(), UINT64_C(1));
    std::fill(
        fixture.torsion_eligible.begin(),
        fixture.torsion_eligible.end(),
        UINT8_C(1));
    std::fill(
        fixture.torsion_steps.begin(), fixture.torsion_steps.end(), UINT64_C(4));
    assert(std::strcmp(
               bg_docking_fixed64_pipeline_v2_profile_id(),
               "betelgeuze.engine_v2_native_fixed64_complete_pipeline/2.0.0") ==
           0);
    const auto reference =
        run_complete_pipeline_v2(
            BG_BACKEND_CPP_CPU_REFERENCE, fixture, 1.0e6, 0.55);
    assert_complete_pipeline_v2_evidence(
        reference, BG_BACKEND_CPP_CPU_REFERENCE);
    assert(reference.output_v2.post_rejected_count > UINT64_C(0));
    constexpr std::size_t kPostRejectedFixtureSlot = 40;
    assert(
        reference.producer.rows[kPostRejectedFixtureSlot]
            .geometric_admission.decision ==
        BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_ACCEPTED);
    assert(
        reference.post_admission_rows[kPostRejectedFixtureSlot].decision ==
        BG_DOCKING_GEOMETRIC_ADMISSION_DECISION_SEVERE_PENETRATION_REJECTED);

    bg_context *reuse_context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    assert(reuse_context != nullptr);
    auto *reused_pipeline =
        make_complete_pipeline_v2(fixture, reuse_context, 1.0e6, 0.55);
    assert(reused_pipeline->workspace.successful_run_count == UINT64_C(0));
    assert(
        reused_pipeline->workspace.coordinate_capacity_growth_count ==
        UINT64_C(0));
    assert(reused_pipeline->workspace.provisioned_coordinate_count == 0);
    CompletePipelineResult reused{};
    assert(run_complete_pipeline_v2_into(
               reuse_context,
               reused_pipeline,
               fixture,
               &reused) == BG_STATUS_OK);
    assert(reused_pipeline->workspace.successful_run_count == UINT64_C(1));
    assert(
        reused_pipeline->workspace.coordinate_capacity_growth_count ==
        UINT64_C(1));
    assert(
        reused_pipeline->workspace.provisioned_coordinate_count ==
        kCoordinates);
    const double *const producer_x_workspace =
        reused_pipeline->workspace.producer_x.data();
    const double *const producer_y_workspace =
        reused_pipeline->workspace.producer_y.data();
    const double *const producer_z_workspace =
        reused_pipeline->workspace.producer_z.data();
    std::array<const double *, 12> rigid_workspace{};
    std::array<const double *, 8> torsion_workspace{};
    std::array<const double *, 3> final_workspace{};
    for (std::size_t index = 0; index < rigid_workspace.size(); ++index) {
        rigid_workspace[index] =
            reused_pipeline->workspace.rigid_coordinates[index].data();
    }
    for (std::size_t index = 0; index < torsion_workspace.size(); ++index) {
        torsion_workspace[index] =
            reused_pipeline->workspace.torsion_coordinates[index].data();
    }
    for (std::size_t index = 0; index < final_workspace.size(); ++index) {
        final_workspace[index] =
            reused_pipeline->workspace.final_coordinates[index].data();
    }
    const CompletePipelineResult first_reused = reused;
    const auto poison = [](auto &buffers) {
        for (auto &buffer : buffers) {
            std::fill(
                buffer.begin(),
                buffer.end(),
                std::numeric_limits<double>::quiet_NaN());
        }
    };
    std::fill(
        reused_pipeline->workspace.producer_x.begin(),
        reused_pipeline->workspace.producer_x.end(),
        std::numeric_limits<double>::quiet_NaN());
    std::fill(
        reused_pipeline->workspace.producer_y.begin(),
        reused_pipeline->workspace.producer_y.end(),
        std::numeric_limits<double>::quiet_NaN());
    std::fill(
        reused_pipeline->workspace.producer_z.begin(),
        reused_pipeline->workspace.producer_z.end(),
        std::numeric_limits<double>::quiet_NaN());
    poison(reused_pipeline->workspace.rigid_coordinates);
    poison(reused_pipeline->workspace.torsion_coordinates);
    poison(reused_pipeline->workspace.final_coordinates);
    CompletePipelineV2RunOptions repeat_options{};
    repeat_options.repeat_same_output_descriptors = true;
    assert(run_complete_pipeline_v2_into(
               reuse_context,
               reused_pipeline,
               fixture,
               &reused,
               repeat_options) == BG_STATUS_OK);
    assert(std::memcmp(
               &first_reused, &reused, sizeof(first_reused)) == 0);
    assert(reused_pipeline->workspace.successful_run_count == UINT64_C(3));
    assert(
        reused_pipeline->workspace.coordinate_capacity_growth_count ==
        UINT64_C(1));
    assert(
        reused_pipeline->workspace.provisioned_coordinate_count ==
        kCoordinates);
    assert(reused_pipeline->workspace.producer_x.data() == producer_x_workspace);
    assert(reused_pipeline->workspace.producer_y.data() == producer_y_workspace);
    assert(reused_pipeline->workspace.producer_z.data() == producer_z_workspace);
    for (std::size_t index = 0; index < rigid_workspace.size(); ++index) {
        assert(
            reused_pipeline->workspace.rigid_coordinates[index].data() ==
            rigid_workspace[index]);
    }
    for (std::size_t index = 0; index < torsion_workspace.size(); ++index) {
        assert(
            reused_pipeline->workspace.torsion_coordinates[index].data() ==
            torsion_workspace[index]);
    }
    for (std::size_t index = 0; index < final_workspace.size(); ++index) {
        assert(
            reused_pipeline->workspace.final_coordinates[index].data() ==
            final_workspace[index]);
    }
    bg_docking_fixed64_pipeline_v2_destroy(reused_pipeline);
    bg_context_destroy(reuse_context);

    const auto repeated =
        run_complete_pipeline_v2(
            BG_BACKEND_CPP_CPU_REFERENCE, fixture, 1.0e6, 0.55);
    assert(std::memcmp(
               reference.rows_v2.data(),
               repeated.rows_v2.data(),
               sizeof(reference.rows_v2)) == 0);
    assert(std::memcmp(
               reference.post_admission_rows.data(),
               repeated.post_admission_rows.data(),
               sizeof(reference.post_admission_rows)) == 0);
    assert(reference.final_coordinates == repeated.final_coordinates);
    assert(reference.final_quaternions == repeated.final_quaternions);
    assert(std::memcmp(
               reference.output_v2.pipeline_batch_receipt_sha256,
               repeated.output_v2.pipeline_batch_receipt_sha256,
               32) == 0);

    const auto rust =
        run_complete_pipeline_v2(BG_BACKEND_RUST_CPU, fixture, 1.0e6, 0.55);
    assert_complete_pipeline_v2_evidence(rust, BG_BACKEND_RUST_CPU);
    assert_complete_pipeline_v2_parity(reference, rust, 4.0e-12);
}

void test_complete_pipeline_v2_invalid_input_and_alias_are_transactional() {
    Fixture fixture;
    bg_context *context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    assert(context != nullptr);
    auto *pipeline = make_complete_pipeline_v2(fixture, context);
    const auto source_before = fixture.source_x;

    const auto expect_rejected = [&](CompletePipelineV2RunOptions options,
                                     bg_status expected_status) {
        CompletePipelineResult rejected{};
        rejected.producer.rows[0].slot_index = UINT32_MAX;
        rejected.post_admission_rows[0].slot_index = UINT32_MAX;
        rejected.rows_v2[0].slot_index = UINT32_MAX;
        assert(run_complete_pipeline_v2_into(
                   context,
                   pipeline,
                   fixture,
                   &rejected,
                   options) == expected_status);
        assert(rejected.producer.output.row_count == 0);
        assert(rejected.post_admission_output.row_count == 0);
        assert(rejected.output_v2.row_count == 0);
        assert(rejected.producer.rows[0].slot_index == UINT32_MAX);
        assert(rejected.post_admission_rows[0].slot_index == UINT32_MAX);
        assert(rejected.rows_v2[0].slot_index == UINT32_MAX);
        assert(fixture.source_x == source_before);
        bg_backend intact_backend = BG_BACKEND_AUTO;
        assert(bg_docking_fixed64_pipeline_v2_get_backend(
                   pipeline, &intact_backend) == BG_STATUS_OK);
        assert(intact_backend == BG_BACKEND_CPP_CPU_REFERENCE);
        assert(pipeline->workspace.successful_run_count == UINT64_C(0));
        assert(
            pipeline->workspace.coordinate_capacity_growth_count ==
            UINT64_C(0));
        assert(pipeline->workspace.provisioned_coordinate_count == 0);
        assert(pipeline->workspace.producer_x.empty());
        assert(pipeline->workspace.producer_y.empty());
        assert(pipeline->workspace.producer_z.empty());
        assert(std::all_of(
            pipeline->workspace.rigid_coordinates.begin(),
            pipeline->workspace.rigid_coordinates.end(),
            [](const auto &buffer) { return buffer.empty(); }));
        assert(std::all_of(
            pipeline->workspace.torsion_coordinates.begin(),
            pipeline->workspace.torsion_coordinates.end(),
            [](const auto &buffer) { return buffer.empty(); }));
        assert(std::all_of(
            pipeline->workspace.final_coordinates.begin(),
            pipeline->workspace.final_coordinates.end(),
            [](const auto &buffer) { return buffer.empty(); }));
    };

    CompletePipelineV2RunOptions options{};
    options.omit_post_admission_policy = true;
    expect_rejected(options, BG_STATUS_INVALID_ARGUMENT);

    options = {};
    options.undersize_rigid_rows = true;
    expect_rejected(options, BG_STATUS_BUFFER_TOO_SMALL);

    options = {};
    options.undersize_pipeline_rows = true;
    expect_rejected(options, BG_STATUS_BUFFER_TOO_SMALL);

    options = {};
    options.overlap_pipeline_rows_with_producer = true;
    expect_rejected(options, BG_STATUS_INVALID_ARGUMENT);

    options = {};
    options.overlap_rigid_x_with_source = true;
    expect_rejected(options, BG_STATUS_INVALID_ARGUMENT);

    options = {};
    options.overlap_pipeline_rows_with_handle = true;
    expect_rejected(options, BG_STATUS_INVALID_ARGUMENT);

    assert(bg_docking_fixed64_pipeline_v2_get_backend(
               pipeline,
               reinterpret_cast<bg_backend *>(pipeline)) ==
           BG_STATUS_INVALID_ARGUMENT);
    bg_backend intact_backend = BG_BACKEND_AUTO;
    alignas(void *) std::array<std::byte, sizeof(void *) + 1>
        misaligned_pipeline_storage{};
    const auto *misaligned_pipeline =
        reinterpret_cast<const bg_docking_fixed64_pipeline_v2 *>(
            misaligned_pipeline_storage.data() + 1);
    assert(bg_docking_fixed64_pipeline_v2_get_backend(
               misaligned_pipeline, &intact_backend) ==
           BG_STATUS_INVALID_ARGUMENT);
    assert(bg_docking_fixed64_pipeline_v2_get_backend(
               pipeline, &intact_backend) == BG_STATUS_OK);
    assert(intact_backend == BG_BACKEND_CPP_CPU_REFERENCE);
    bg_docking_fixed64_pipeline_v2_destroy(pipeline);
    bg_context_destroy(context);
}

void test_complete_pipeline_single_atom_preserves_denominator() {
    Fixture fixture;
    fixture.allocation.atomic_feature_count = 0;
    fixture.allocation.atomic_features = nullptr;
    parse_digest(
        "70c6f2b5446c0652d7bbc81537a0ac8a93553e961ecb3c2c40fee2620de1545b",
        fixture.allocation.exact_v11_source.ligand_coordinate_sha256);
    parse_digest(
        "d4379c8a5c7b2291893bd45b047e8736168136002dd646b705a735875a947919",
        fixture.allocation.exact_v11_source.ligand_vdw_radii_sha256);
    parse_digest(
        "49e14fc025f4768dc72e02fe53803e4cd9906d5dc7c89c1f7b08c6fb39b9223a",
        fixture.allocation.exact_v11_source.ligand_heavy_atom_mask_sha256);
    fixture.exact_source.ligand_atom_count = 1;
    std::copy_n(
        fixture.allocation.exact_v11_source.ligand_coordinate_sha256,
        32,
        fixture.exact_source.source.coordinate_sha256);
    for (std::size_t index = 0; index < fixture.v7_evidence.size(); ++index) {
        fixture.v7_sources[index].payload.ligand_atom_count = 1;
        std::copy_n(
            fixture.allocation.exact_v11_source.ligand_coordinate_sha256,
            32,
            fixture.v7_evidence[index].source.coordinate_sha256);
        std::copy_n(
            fixture.allocation.exact_v11_source.ligand_coordinate_sha256,
            32,
            fixture.v7_sources[index].payload.source.coordinate_sha256);
    }
    for (std::size_t index = 0; index < fixture.conformer_evidence.size();
         ++index) {
        fixture.conformer_sources[index].payload.ligand_atom_count = 1;
        std::copy_n(
            fixture.allocation.exact_v11_source.ligand_coordinate_sha256,
            32,
            fixture.conformer_evidence[index].source.coordinate_sha256);
        std::copy_n(
            fixture.allocation.exact_v11_source.ligand_coordinate_sha256,
            32,
            fixture.conformer_sources[index].payload.source.coordinate_sha256);
    }
    for (std::size_t index = 0; index < fixture.retained_evidence.size();
         ++index) {
        fixture.retained_sources[index].payload.ligand_atom_count = 1;
        std::copy_n(
            fixture.allocation.exact_v11_source.ligand_coordinate_sha256,
            32,
            fixture.retained_evidence[index].source.coordinate_sha256);
        std::copy_n(
            fixture.allocation.exact_v11_source.ligand_coordinate_sha256,
            32,
            fixture.retained_sources[index].payload.source.coordinate_sha256);
    }
    std::fill(
        fixture.refinement_modes.begin(),
        fixture.refinement_modes.end(),
        BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V2_TRANSLATION);
    std::fill(
        fixture.torsion_eligible.begin(), fixture.torsion_eligible.end(),
        UINT8_C(0));
    std::fill(
        fixture.torsion_steps.begin(), fixture.torsion_steps.end(),
        UINT64_C(0));

    auto producer_input = make_input(fixture);
    producer_input.feature_geometry_count = 0;
    producer_input.feature_geometry_rows = nullptr;
    producer_input.feature_atom_index_count = 0;
    producer_input.feature_atom_indices = nullptr;
    std::fill(
        std::begin(producer_input.feature_geometry_inventory_sha256),
        std::end(producer_input.feature_geometry_inventory_sha256),
        UINT8_C(0));

    for (const bg_backend backend : {
             BG_BACKEND_CPP_CPU_REFERENCE, BG_BACKEND_RUST_CPU,
             BG_BACKEND_HIP_SAFE, BG_BACKEND_HIP_FAST}) {
        bg_context *context = make_context(backend);
        if (context == nullptr) continue;
        auto *pipeline = make_single_atom_complete_pipeline(fixture, context);
        CompletePipelineResult result{};
        const bg_status status = run_complete_pipeline_into(
            context,
            pipeline,
            fixture,
            &result,
            false,
            false,
            false,
            &producer_input);
        if (status != BG_STATUS_OK) {
            std::fprintf(
                stderr,
                "single-atom complete pipeline backend %d failed: %s\n",
                backend,
                bg_last_error_message());
        }
        assert(status == BG_STATUS_OK);
        assert(result.output.row_count == kSlots);
        assert(result.output.generated_count == 28);
        assert(result.producer.output.row_count == kSlots);
        assert(result.producer.output.coordinate_count == kSlots);
        assert(result.producer.output.generated_count == 28);
        assert(result.producer.output.typed_failure_count == 36);
        assert(result.output.refined_count <= 28);
        assert(result.output.scored_count <= 28);
        assert(result.output.valid_count <= 28);
        assert_complete_pipeline_authority_false(result.output);
        for (std::size_t slot = 0; slot < kSlots; ++slot) {
            const auto &producer_row = result.producer.rows[slot];
            const auto &row = result.rows[slot];
            assert(producer_row.slot_index == slot);
            assert(producer_row.ligand_atom_count == 1);
            assert(producer_row.coordinate_offset == slot);
            assert(producer_row.denominator_preserved == UINT8_C(1));
            assert(row.slot_index == slot);
            assert(row.producer_status == producer_row.status);
            assert(row.producer_failure_code == producer_row.failure_code);
            assert(digest_present(row.producer_row_receipt_sha256));
            assert(digest_present(row.refinement_evidence_sha256));
            assert(digest_present(row.scorer_evidence_sha256));
            assert(digest_present(row.validity_evidence_sha256));
            assert(digest_present(row.ranking_evidence_sha256));
            assert(digest_present(row.cluster_evidence_sha256));
            assert(digest_present(row.row_receipt_sha256));
            if (slot < 24 || slot >= 60) {
                assert(producer_row.status ==
                       BG_DOCKING_FIXED64_PRODUCER_ROW_GENERATED);
            } else {
                assert(producer_row.status ==
                       BG_DOCKING_FIXED64_PRODUCER_ROW_TYPED_FAILURE);
                assert(row.effective_refinement_mode ==
                       BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_INACTIVE);
            }
        }
        bg_docking_fixed64_pipeline_v1_destroy(pipeline);
        bg_context_destroy(context);
    }
}

void test_complete_pipeline_context_receipts_bind_configuration() {
    Fixture fixture;
    const auto reference =
        run_complete_pipeline(BG_BACKEND_CPP_CPU_REFERENCE, fixture);
    bg_context *context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    assert(context != nullptr);
    const auto admission = make_admission_descriptor(fixture);
    const auto rigid = make_rigid_descriptor(fixture);
    const auto torsion = make_torsion_descriptor(fixture);
    auto scorer = make_scorer_descriptor(fixture);
    auto validity = make_validity_descriptor(fixture);
    scorer.backend_receipt_sha256[0] ^= UINT8_C(1);
    validity.backend_receipt_sha256[0] ^= UINT8_C(2);
    bg_docking_fixed64_pipeline_v1 *pipeline = nullptr;
    assert(bg_docking_fixed64_pipeline_v1_create(
               context,
               &admission,
               &rigid,
               &torsion,
               &scorer,
               &validity,
               &pipeline) == BG_STATUS_OK);
    CompletePipelineResult observed{};
    assert(run_complete_pipeline_into(
               context, pipeline, fixture, &observed) == BG_STATUS_OK);
    assert(std::memcmp(
               reference.output.admission_context_receipt_sha256,
               observed.output.admission_context_receipt_sha256,
               32) == 0);
    assert(std::memcmp(
               reference.output.refinement_context_receipt_sha256,
               observed.output.refinement_context_receipt_sha256,
               32) == 0);
    assert(std::memcmp(
               reference.output.scorer_context_receipt_sha256,
               observed.output.scorer_context_receipt_sha256,
               32) != 0);
    assert(std::memcmp(
               reference.output.validity_context_receipt_sha256,
               observed.output.validity_context_receipt_sha256,
               32) != 0);
    assert(std::memcmp(
               reference.output.component_binding_receipt_sha256,
               observed.output.component_binding_receipt_sha256,
               32) != 0);
    assert(std::memcmp(
               reference.output.producer_batch_receipt_sha256,
               observed.output.producer_batch_receipt_sha256,
               32) == 0);
    assert(std::memcmp(
               reference.output.pipeline_batch_receipt_sha256,
               observed.output.pipeline_batch_receipt_sha256,
               32) != 0);
    assert(std::memcmp(
               reference.rows[0].row_receipt_sha256,
               observed.rows[0].row_receipt_sha256,
               32) != 0);
    bg_docking_fixed64_pipeline_v1_destroy(pipeline);
    bg_context_destroy(context);
}

void test_complete_pipeline_create_and_run_fail_closed() {
    Fixture fixture;
    bg_context *context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);
    assert(context != nullptr);
    auto admission = make_admission_descriptor(fixture);
    auto rigid = make_rigid_descriptor(fixture);
    auto torsion = make_torsion_descriptor(fixture);
    auto scorer = make_scorer_descriptor(fixture);
    auto validity = make_validity_descriptor(fixture);
    auto short_admission = admission;
    --short_admission.struct_size;
    auto *header_sentinel = reinterpret_cast<bg_docking_fixed64_pipeline_v1 *>(
        static_cast<uintptr_t>(1));
    assert(bg_docking_fixed64_pipeline_v1_create(
               context,
               &short_admission,
               &rigid,
               &torsion,
               &scorer,
               &validity,
               &header_sentinel) == BG_STATUS_ABI_MISMATCH);
    assert(
        header_sentinel ==
        reinterpret_cast<bg_docking_fixed64_pipeline_v1 *>(
            static_cast<uintptr_t>(1)));
    const double receptor_before = fixture.receptor_x[0];
    auto **alias = reinterpret_cast<bg_docking_fixed64_pipeline_v1 **>(
        fixture.receptor_x.data());
    assert(bg_docking_fixed64_pipeline_v1_create(
               context,
               &admission,
               &rigid,
               &torsion,
               &scorer,
               &validity,
               alias) == BG_STATUS_INVALID_ARGUMENT);
    assert(fixture.receptor_x[0] == receptor_before);

    const auto expect_validity_crosswire_rejected =
        [&](const bg_docking_pose_validity_context_soa_v1 &crosswired) {
            auto *candidate =
                reinterpret_cast<bg_docking_fixed64_pipeline_v1 *>(
                    static_cast<uintptr_t>(1));
            assert(bg_docking_fixed64_pipeline_v1_create(
                       context,
                       &admission,
                       &rigid,
                       &torsion,
                       &scorer,
                       &crosswired,
                       &candidate) == BG_STATUS_INVALID_ARGUMENT);
            assert(candidate == nullptr);
        };

    auto different_receptor_x = fixture.receptor_x;
    different_receptor_x[0] += 0.125;
    auto crosswired_validity = validity;
    crosswired_validity.receptor_x_angstrom = different_receptor_x.data();
    expect_validity_crosswire_rejected(crosswired_validity);

    auto different_ligand_reference_x = fixture.source_x;
    different_ligand_reference_x[0] += 0.125;
    crosswired_validity = validity;
    crosswired_validity.ligand_reference_x_angstrom =
        different_ligand_reference_x.data();
    expect_validity_crosswire_rejected(crosswired_validity);

    crosswired_validity = validity;
    crosswired_validity.pocket_center_angstrom[0] += 0.125;
    expect_validity_crosswire_rejected(crosswired_validity);

    crosswired_validity = validity;
    crosswired_validity.authority_input_receipt_sha256[0] ^= UINT8_C(1);
    expect_validity_crosswire_rejected(crosswired_validity);
    crosswired_validity = validity;
    crosswired_validity.receptor_system_sha256[0] ^= UINT8_C(1);
    expect_validity_crosswire_rejected(crosswired_validity);
    crosswired_validity = validity;
    crosswired_validity.ligand_system_sha256[0] ^= UINT8_C(1);
    expect_validity_crosswire_rejected(crosswired_validity);

    scorer.authority_input_receipt_sha256[0] ^= UINT8_C(1);
    auto *cross_wired = reinterpret_cast<bg_docking_fixed64_pipeline_v1 *>(
        static_cast<uintptr_t>(1));
    assert(bg_docking_fixed64_pipeline_v1_create(
               context,
               &admission,
               &rigid,
               &torsion,
               &scorer,
               &validity,
               &cross_wired) == BG_STATUS_INVALID_ARGUMENT);
    assert(cross_wired == nullptr);

    auto *pipeline = make_complete_pipeline(fixture, context);
    assert(bg_docking_fixed64_pipeline_v1_get_backend(
               pipeline, reinterpret_cast<bg_backend *>(pipeline)) ==
           BG_STATUS_INVALID_ARGUMENT);

    const auto expect_producer_topology_crosswire_rejected =
        [&](bool crosswire_ligand) {
            auto producer_input = make_input(fixture);
            auto allocation = fixture.allocation;
            if (crosswire_ligand) {
                allocation.exact_v11_source
                    .prepared_ligand_topology_sha256[0] ^= UINT8_C(1);
            } else {
                allocation.exact_v11_source
                    .prepared_receptor_topology_sha256[0] ^= UINT8_C(1);
            }
            producer_input.allocation_input = &allocation;
            CompletePipelineResult rejected{};
            assert(run_complete_pipeline_into(
                       context,
                       pipeline,
                       fixture,
                       &rejected,
                       false,
                       false,
                       false,
                       &producer_input) == BG_STATUS_INVALID_ARGUMENT);
            assert(rejected.producer.output.row_count == 0);
            assert(rejected.output.row_count == 0);
            assert(rejected.rows[0].slot_index == 0);
        };
    expect_producer_topology_crosswire_rejected(true);
    expect_producer_topology_crosswire_rejected(false);

    CompletePipelineResult result{};
    result.producer.rows[0].slot_index = UINT32_MAX;
    result.rows[0].slot_index = UINT32_MAX;
    assert(run_complete_pipeline_into(
               context,
               pipeline,
               fixture,
               &result,
               true) == BG_STATUS_INVALID_ARGUMENT);
    assert(result.producer.output.row_count == 0);
    assert(result.output.row_count == 0);
    assert(result.producer.rows[0].slot_index == UINT32_MAX);
    assert(result.rows[0].slot_index == UINT32_MAX);

    CompletePipelineResult source_overlap{};
    const auto source_before = fixture.source_x;
    assert(run_complete_pipeline_into(
               context,
               pipeline,
               fixture,
               &source_overlap,
               false,
               true) == BG_STATUS_INVALID_ARGUMENT);
    assert(source_overlap.producer.output.row_count == 0);
    assert(source_overlap.output.row_count == 0);
    assert(fixture.source_x == source_before);

    CompletePipelineResult handle_overlap{};
    assert(run_complete_pipeline_into(
               context,
               pipeline,
               fixture,
               &handle_overlap,
               false,
               false,
               true) == BG_STATUS_INVALID_ARGUMENT);
    bg_backend intact_backend = BG_BACKEND_AUTO;
    assert(bg_docking_fixed64_pipeline_v1_get_backend(
               pipeline, &intact_backend) == BG_STATUS_OK);
    assert(intact_backend == BG_BACKEND_CPP_CPU_REFERENCE);
    bg_docking_fixed64_pipeline_v1_destroy(pipeline);
    bg_context_destroy(context);
}

}  // namespace

int main(int argc, char **argv) {
    if (argc == 2 &&
        std::strcmp(argv[1], "--complete-pipeline") == 0) {
        test_complete_pipeline_exact64_repeat_and_backend_parity();
        test_complete_pipeline_v2_post_admission_exact64_repeat_and_cpu_parity();
        test_complete_pipeline_v2_invalid_input_and_alias_are_transactional();
        test_complete_pipeline_single_atom_preserves_denominator();
        test_complete_pipeline_context_receipts_bind_configuration();
        test_complete_pipeline_create_and_run_fail_closed();
        return 0;
    }
    assert(argc == 1);
    test_exact64_repeat_and_backend_parity();
    test_missing_source_is_typed_and_zero_filled();
    test_missing_feature_allocation_preserves_denominator();
    test_partial_feature_geometry_only_fails_affected_slots();
    test_equal_cross_kind_receipt_cannot_mask_missing_ligand_geometry();
    test_single_atom_ligand_preserves_all_fixed64_rows();
    test_ready_anchor_without_geometry_is_typed();
    test_component_typed_failure_is_retained();
    test_invalid_input_capacity_and_alias_are_transactional();
    test_oversized_source_count_is_rejected_before_narrowing();
    return 0;
}
