#include "../internal.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <memory>
#include <new>
#include <stdexcept>
#include <utility>
#include <vector>

namespace betelgeuze::native::docking::refinement_pipeline {

constexpr std::size_t kCandidateCount =
    BG_DOCKING_FIXED64_CANDIDATE_COUNT;
constexpr std::size_t kMovesPerCandidate =
    BG_DOCKING_TORSION_V7_MAX_MOVES;

struct MemoryRange final {
    const void *pointer = nullptr;
    std::size_t size = 0;
};

struct Quaternion final {
    double x = 0.0;
    double y = 0.0;
    double z = 0.0;
    double w = 0.0;
};

[[nodiscard]] bool ranges_overlap(
    const MemoryRange &left,
    const MemoryRange &right) noexcept {
    if (left.pointer == nullptr || right.pointer == nullptr ||
        left.size == 0 || right.size == 0) {
        return false;
    }
    const auto left_begin = reinterpret_cast<std::uintptr_t>(left.pointer);
    const auto right_begin = reinterpret_cast<std::uintptr_t>(right.pointer);
    if (left_begin > std::numeric_limits<std::uintptr_t>::max() - left.size ||
        right_begin > std::numeric_limits<std::uintptr_t>::max() - right.size) {
        return true;
    }
    return left_begin < right_begin + right.size &&
           right_begin < left_begin + left.size;
}

template <typename Type>
[[nodiscard]] bg_status require_channel(
    const Type *pointer,
    std::size_t count,
    const char *message) noexcept {
    if (count != 0 && (pointer == nullptr || !pointer_is_aligned(pointer))) {
        return fail(BG_STATUS_INVALID_ARGUMENT, message);
    }
    return BG_STATUS_OK;
}

template <typename Type>
void add_range(
    std::vector<MemoryRange> *ranges,
    const Type *pointer,
    std::size_t count) {
    if (pointer == nullptr || count == 0) {
        return;
    }
    if (count > std::numeric_limits<std::size_t>::max() / sizeof(Type)) {
        throw std::length_error("fixed64 refinement range overflows");
    }
    ranges->push_back({pointer, count * sizeof(Type)});
}

[[nodiscard]] std::size_t checked_range_count(uint64_t count) {
    if (count > std::numeric_limits<std::size_t>::max()) {
        throw std::length_error("fixed64 refinement range count overflows");
    }
    return static_cast<std::size_t>(count);
}

[[nodiscard]] bool channels_equal(
    const double *left,
    const double *right,
    std::size_t count) noexcept {
    for (std::size_t index = 0; index < count; ++index) {
        if (left[index] != right[index]) {
            return false;
        }
    }
    return true;
}

[[nodiscard]] bg_status validate_component_binding(
    const bg_context &context,
    const bg_docking_rigid_refinement_context_soa_v1 &rigid,
    const bg_docking_torsion_v7_context_soa_v1 &torsion,
    const bg_docking_scorer_v1_context_soa_v1 &scorer,
    const bg_docking_pose_validity_context_soa_v1 &validity) noexcept {
    if (rigid.unit_system != context.unit_system ||
        torsion.unit_system != context.unit_system ||
        scorer.unit_system != context.unit_system ||
        validity.unit_system != context.unit_system ||
        rigid.receptor_atom_count != torsion.receptor_atom_count ||
        rigid.receptor_atom_count != scorer.receptor_atom_count ||
        rigid.receptor_atom_count != validity.receptor_atom_count ||
        rigid.ligand_atom_count != torsion.ligand_atom_count ||
        rigid.ligand_atom_count != scorer.ligand_atom_count ||
        rigid.ligand_atom_count != validity.ligand_atom_count ||
        rigid.ligand_atom_count == 0) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 refinement component units or atom denominators are cross-wired");
    }
    const auto receptor_count =
        static_cast<std::size_t>(rigid.receptor_atom_count);
    const auto ligand_count =
        static_cast<std::size_t>(rigid.ligand_atom_count);
    const std::array<std::pair<const double *, const double *>, 4>
        rigid_scorer_receptor = {{
            {rigid.receptor_x_angstrom, scorer.receptor_x_angstrom},
            {rigid.receptor_y_angstrom, scorer.receptor_y_angstrom},
            {rigid.receptor_z_angstrom, scorer.receptor_z_angstrom},
            {rigid.receptor_vdw_radius_angstrom,
             scorer.receptor_vdw_radius_angstrom},
        }};
    const std::array<std::pair<const double *, const double *>, 4>
        torsion_scorer_receptor = {{
            {torsion.receptor_x_angstrom, scorer.receptor_x_angstrom},
            {torsion.receptor_y_angstrom, scorer.receptor_y_angstrom},
            {torsion.receptor_z_angstrom, scorer.receptor_z_angstrom},
            {torsion.receptor_vdw_radius_angstrom,
             scorer.receptor_vdw_radius_angstrom},
        }};
    for (const auto &[left, right] : rigid_scorer_receptor) {
        if (!channels_equal(left, right, receptor_count)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 refinement rigid receptor is cross-wired");
        }
    }
    for (const auto &[left, right] : torsion_scorer_receptor) {
        if (!channels_equal(left, right, receptor_count)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 refinement torsion receptor is cross-wired");
        }
    }
    if (!channels_equal(
            rigid.ligand_vdw_radius_angstrom,
            scorer.ligand_vdw_radius_angstrom,
            ligand_count) ||
        !channels_equal(
            torsion.ligand_vdw_radius_angstrom,
            scorer.ligand_vdw_radius_angstrom,
            ligand_count) ||
        !channels_equal(
            validity.ligand_vdw_radius_angstrom,
            scorer.ligand_vdw_radius_angstrom,
            ligand_count)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 refinement ligand radii are cross-wired");
    }
    if (!channels_equal(
            rigid.pocket_center_angstrom,
            scorer.pocket_center_angstrom,
            3) ||
        !channels_equal(
            torsion.pocket_center_angstrom,
            scorer.pocket_center_angstrom,
            3) ||
        rigid.pocket_radius_angstrom != scorer.pocket_radius_angstrom ||
        validity.pocket_radius_angstrom != scorer.pocket_radius_angstrom) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 refinement pocket declaration is cross-wired");
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status validate_create_output_range(
    const bg_context &context,
    const bg_docking_rigid_refinement_context_soa_v1 &rigid,
    const bg_docking_torsion_v7_context_soa_v1 &torsion,
    const bg_docking_scorer_v1_context_soa_v1 &scorer,
    const bg_docking_pose_validity_context_soa_v1 &validity,
    bg_docking_fixed64_refinement_pipeline_v1 **out_pipeline) noexcept {
    try {
        std::vector<MemoryRange> inputs;
        inputs.reserve(61);
        add_range(&inputs, &context, 1);
        add_range(&inputs, &rigid, 1);
        add_range(&inputs, &torsion, 1);
        add_range(&inputs, &scorer, 1);
        add_range(&inputs, &validity, 1);

        const auto rigid_receptor_count =
            checked_range_count(rigid.receptor_atom_count);
        const auto rigid_ligand_count =
            checked_range_count(rigid.ligand_atom_count);
        add_range(&inputs, rigid.receptor_x_angstrom, rigid_receptor_count);
        add_range(&inputs, rigid.receptor_y_angstrom, rigid_receptor_count);
        add_range(&inputs, rigid.receptor_z_angstrom, rigid_receptor_count);
        add_range(
            &inputs, rigid.receptor_vdw_radius_angstrom, rigid_receptor_count);
        add_range(
            &inputs, rigid.ligand_vdw_radius_angstrom, rigid_ligand_count);

        const auto torsion_receptor_count =
            checked_range_count(torsion.receptor_atom_count);
        const auto torsion_ligand_count =
            checked_range_count(torsion.ligand_atom_count);
        const auto torsion_rotor_count =
            checked_range_count(torsion.rotor_count);
        const auto torsion_internal_pair_count =
            checked_range_count(torsion.internal_pair_count);
        add_range(&inputs, torsion.receptor_x_angstrom, torsion_receptor_count);
        add_range(&inputs, torsion.receptor_y_angstrom, torsion_receptor_count);
        add_range(&inputs, torsion.receptor_z_angstrom, torsion_receptor_count);
        add_range(
            &inputs,
            torsion.receptor_vdw_radius_angstrom,
            torsion_receptor_count);
        add_range(
            &inputs, torsion.ligand_vdw_radius_angstrom, torsion_ligand_count);
        add_range(&inputs, torsion.parent_atom_index, torsion_ligand_count);
        add_range(
            &inputs, torsion.rotatable_child_atom_index, torsion_rotor_count);
        add_range(
            &inputs,
            torsion.internal_pair_atom_i,
            torsion_internal_pair_count);
        add_range(
            &inputs,
            torsion.internal_pair_atom_j,
            torsion_internal_pair_count);

        const auto scorer_receptor_count =
            checked_range_count(scorer.receptor_atom_count);
        const auto scorer_ligand_count =
            checked_range_count(scorer.ligand_atom_count);
        const auto scorer_receptor_donor_count =
            checked_range_count(scorer.receptor_donor_count);
        const auto scorer_ligand_donor_count =
            checked_range_count(scorer.ligand_donor_count);
        const auto scorer_exclusion_count =
            checked_range_count(scorer.ligand_exclusion_count);
        const auto scorer_rotor_count =
            checked_range_count(scorer.rotor_count);
        add_range(&inputs, scorer.receptor_x_angstrom, scorer_receptor_count);
        add_range(&inputs, scorer.receptor_y_angstrom, scorer_receptor_count);
        add_range(&inputs, scorer.receptor_z_angstrom, scorer_receptor_count);
        add_range(
            &inputs,
            scorer.receptor_charge_elementary,
            scorer_receptor_count);
        add_range(
            &inputs,
            scorer.receptor_vdw_radius_angstrom,
            scorer_receptor_count);
        add_range(
            &inputs,
            scorer.receptor_epsilon_kcal_per_mol,
            scorer_receptor_count);
        add_range(
            &inputs, scorer.receptor_hydrophobic, scorer_receptor_count);
        add_range(&inputs, scorer.receptor_acceptor, scorer_receptor_count);
        add_range(
            &inputs,
            scorer.ligand_reference_x_angstrom,
            scorer_ligand_count);
        add_range(
            &inputs,
            scorer.ligand_reference_y_angstrom,
            scorer_ligand_count);
        add_range(
            &inputs,
            scorer.ligand_reference_z_angstrom,
            scorer_ligand_count);
        add_range(
            &inputs,
            scorer.ligand_charge_elementary,
            scorer_ligand_count);
        add_range(
            &inputs,
            scorer.ligand_vdw_radius_angstrom,
            scorer_ligand_count);
        add_range(
            &inputs,
            scorer.ligand_epsilon_kcal_per_mol,
            scorer_ligand_count);
        add_range(&inputs, scorer.ligand_hydrophobic, scorer_ligand_count);
        add_range(&inputs, scorer.ligand_acceptor, scorer_ligand_count);
        add_range(
            &inputs,
            scorer.receptor_donor_atom_index,
            scorer_receptor_donor_count);
        add_range(
            &inputs,
            scorer.receptor_hydrogen_atom_index,
            scorer_receptor_donor_count);
        add_range(
            &inputs,
            scorer.ligand_donor_atom_index,
            scorer_ligand_donor_count);
        add_range(
            &inputs,
            scorer.ligand_hydrogen_atom_index,
            scorer_ligand_donor_count);
        add_range(
            &inputs,
            scorer.ligand_exclusion_atom_i,
            scorer_exclusion_count);
        add_range(
            &inputs,
            scorer.ligand_exclusion_atom_j,
            scorer_exclusion_count);
        add_range(&inputs, scorer.rotor_atom_i, scorer_rotor_count);
        add_range(&inputs, scorer.rotor_atom_j, scorer_rotor_count);
        add_range(&inputs, scorer.rotor_atom_k, scorer_rotor_count);
        add_range(&inputs, scorer.rotor_atom_l, scorer_rotor_count);

        const auto validity_receptor_count =
            checked_range_count(validity.receptor_atom_count);
        const auto validity_ligand_count =
            checked_range_count(validity.ligand_atom_count);
        const auto validity_bond_count =
            checked_range_count(validity.bond_count);
        const auto validity_exclusion_count =
            checked_range_count(validity.ligand_exclusion_count);
        const auto validity_chirality_count =
            checked_range_count(validity.chirality_center_count);
        add_range(
            &inputs, validity.receptor_x_angstrom, validity_receptor_count);
        add_range(
            &inputs, validity.receptor_y_angstrom, validity_receptor_count);
        add_range(
            &inputs, validity.receptor_z_angstrom, validity_receptor_count);
        add_range(
            &inputs,
            validity.receptor_vdw_radius_angstrom,
            validity_receptor_count);
        add_range(
            &inputs,
            validity.ligand_reference_x_angstrom,
            validity_ligand_count);
        add_range(
            &inputs,
            validity.ligand_reference_y_angstrom,
            validity_ligand_count);
        add_range(
            &inputs,
            validity.ligand_reference_z_angstrom,
            validity_ligand_count);
        add_range(
            &inputs,
            validity.ligand_vdw_radius_angstrom,
            validity_ligand_count);
        add_range(&inputs, validity.bond_atom_i, validity_bond_count);
        add_range(&inputs, validity.bond_atom_j, validity_bond_count);
        add_range(
            &inputs,
            validity.ligand_exclusion_atom_i,
            validity_exclusion_count);
        add_range(
            &inputs,
            validity.ligand_exclusion_atom_j,
            validity_exclusion_count);
        add_range(
            &inputs,
            validity.chirality_center_atom,
            validity_chirality_count);
        add_range(
            &inputs, validity.chirality_atom_i, validity_chirality_count);
        add_range(
            &inputs, validity.chirality_atom_j, validity_chirality_count);
        add_range(
            &inputs, validity.chirality_atom_k, validity_chirality_count);

        const MemoryRange output{out_pipeline, sizeof(*out_pipeline)};
        for (const MemoryRange &input : inputs) {
            if (ranges_overlap(output, input)) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "fixed64 refinement pipeline handle output overlaps a create input");
            }
        }
        return BG_STATUS_OK;
    } catch (const std::bad_alloc &) {
        return fail(
            BG_STATUS_OUT_OF_MEMORY,
            "fixed64 refinement create range validation ran out of memory");
    } catch (const std::length_error &) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "fixed64 refinement create range denominator overflows");
    }
}

void destroy_components(
    bg_docking_fixed64_refinement_pipeline_v1 *pipeline) noexcept {
    if (pipeline == nullptr) {
        return;
    }
    bg_docking_fixed64_downstream_v1_destroy(pipeline->downstream);
    bg_docking_torsion_v7_destroy(pipeline->torsion);
    bg_docking_rigid_refinement_destroy(pipeline->rigid);
    pipeline->downstream = nullptr;
    pipeline->torsion = nullptr;
    pipeline->rigid = nullptr;
}

[[nodiscard]] bg_status validate_input(
    const bg_docking_fixed64_refinement_pipeline_v1 &pipeline,
    const bg_docking_fixed64_refinement_input_v1 &input,
    std::size_t *coordinate_count) noexcept {
    bg_status status = validate_descriptor_header(
        input.struct_size,
        sizeof(input),
        input.abi_version,
        "fixed64 refinement input size does not match ABI v1",
        "fixed64 refinement input ABI version does not match");
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (input.candidate_count != kCandidateCount ||
        input.ligand_atom_count != pipeline.ligand_atom_count ||
        input.unit_system != pipeline.unit_system || input.reserved0 != 0 ||
        !std::isfinite(input.rmsd_threshold_angstrom) ||
        input.rmsd_threshold_angstrom <= 0.0 ||
        !reserved_is_zero(input.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 refinement input denominator, units, RMSD threshold, or reserved fields are invalid");
    }
    std::size_t ligand_count = 0;
    status = checked_element_count(
        input.ligand_atom_count,
        sizeof(double),
        "fixed64 refinement ligand denominator overflows",
        &ligand_count);
    if (status != BG_STATUS_OK ||
        ligand_count >
            std::numeric_limits<std::size_t>::max() / kCandidateCount) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "fixed64 refinement coordinate denominator overflows");
    }
    *coordinate_count = ligand_count * kCandidateCount;
#define BG_REQUIRE_REFINEMENT_INPUT(pointer, count, message)                \
    do {                                                                    \
        status = require_channel((pointer), (count), (message));            \
        if (status != BG_STATUS_OK) {                                       \
            return status;                                                  \
        }                                                                   \
    } while (false)
    BG_REQUIRE_REFINEMENT_INPUT(
        input.candidate_mode,
        kCandidateCount,
        "fixed64 refinement candidate-mode channel is null or misaligned");
    BG_REQUIRE_REFINEMENT_INPUT(
        input.rigid_max_steps,
        kCandidateCount,
        "fixed64 refinement rigid-step channel is null or misaligned");
    BG_REQUIRE_REFINEMENT_INPUT(
        input.proposal_is_torsion_eligible,
        kCandidateCount,
        "fixed64 refinement torsion-eligibility channel is null or misaligned");
    BG_REQUIRE_REFINEMENT_INPUT(
        input.torsion_max_steps,
        kCandidateCount,
        "fixed64 refinement torsion-step channel is null or misaligned");
    BG_REQUIRE_REFINEMENT_INPUT(
        input.source_x_angstrom,
        *coordinate_count,
        "fixed64 refinement source x channel is null or misaligned");
    BG_REQUIRE_REFINEMENT_INPUT(
        input.source_y_angstrom,
        *coordinate_count,
        "fixed64 refinement source y channel is null or misaligned");
    BG_REQUIRE_REFINEMENT_INPUT(
        input.source_z_angstrom,
        *coordinate_count,
        "fixed64 refinement source z channel is null or misaligned");
    BG_REQUIRE_REFINEMENT_INPUT(
        input.baseline_torsion_angles_radians,
        *coordinate_count,
        "fixed64 refinement torsion-angle channel is null or misaligned");
    BG_REQUIRE_REFINEMENT_INPUT(
        input.source_quaternion_x,
        kCandidateCount,
        "fixed64 refinement quaternion x channel is null or misaligned");
    BG_REQUIRE_REFINEMENT_INPUT(
        input.source_quaternion_y,
        kCandidateCount,
        "fixed64 refinement quaternion y channel is null or misaligned");
    BG_REQUIRE_REFINEMENT_INPUT(
        input.source_quaternion_z,
        kCandidateCount,
        "fixed64 refinement quaternion z channel is null or misaligned");
    BG_REQUIRE_REFINEMENT_INPUT(
        input.source_quaternion_w,
        kCandidateCount,
        "fixed64 refinement quaternion w channel is null or misaligned");
#undef BG_REQUIRE_REFINEMENT_INPUT
    for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
        if (input.proposal_is_torsion_eligible[slot] > UINT8_C(1)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 refinement torsion eligibility must be zero or one");
        }
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status validate_pipeline_output(
    const bg_docking_fixed64_refinement_pipeline_v1 &pipeline,
    bg_docking_fixed64_refinement_output_v1 &output,
    std::size_t coordinate_count) noexcept {
    bg_status status = validate_descriptor_header(
        output.struct_size,
        sizeof(output),
        output.abi_version,
        "fixed64 refinement output size does not match ABI v1",
        "fixed64 refinement output ABI version does not match");
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (output.row_capacity != kCandidateCount ||
        output.coordinate_capacity != coordinate_count ||
        output.quaternion_capacity != kCandidateCount ||
        output.unit_system != pipeline.unit_system || output.reserved0 != 0 ||
        output.molecular_execution_authorized != 0 ||
        output.reservation_authorized != 0 ||
        output.benchmark_execution_authorized != 0 ||
        output.existing_rank_auto_change_authorized != 0 ||
        output.customer_pose_emission_authorized != 0 ||
        output.production_claim_authorized != 0 || output.reserved1[0] != 0 ||
        output.reserved1[1] != 0 || !reserved_is_zero(output.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 refinement output capacity, units, authority, or reserved fields are invalid");
    }
#define BG_REQUIRE_REFINEMENT_OUTPUT(pointer, count, message)               \
    do {                                                                    \
        status = require_channel((pointer), (count), (message));            \
        if (status != BG_STATUS_OK) {                                       \
            return status;                                                  \
        }                                                                   \
    } while (false)
    BG_REQUIRE_REFINEMENT_OUTPUT(
        output.rows,
        kCandidateCount,
        "fixed64 refinement output row channel is null or misaligned");
    BG_REQUIRE_REFINEMENT_OUTPUT(
        output.final_x_angstrom,
        coordinate_count,
        "fixed64 refinement final x channel is null or misaligned");
    BG_REQUIRE_REFINEMENT_OUTPUT(
        output.final_y_angstrom,
        coordinate_count,
        "fixed64 refinement final y channel is null or misaligned");
    BG_REQUIRE_REFINEMENT_OUTPUT(
        output.final_z_angstrom,
        coordinate_count,
        "fixed64 refinement final z channel is null or misaligned");
    BG_REQUIRE_REFINEMENT_OUTPUT(
        output.final_quaternion_x,
        kCandidateCount,
        "fixed64 refinement final quaternion x channel is null or misaligned");
    BG_REQUIRE_REFINEMENT_OUTPUT(
        output.final_quaternion_y,
        kCandidateCount,
        "fixed64 refinement final quaternion y channel is null or misaligned");
    BG_REQUIRE_REFINEMENT_OUTPUT(
        output.final_quaternion_z,
        kCandidateCount,
        "fixed64 refinement final quaternion z channel is null or misaligned");
    BG_REQUIRE_REFINEMENT_OUTPUT(
        output.final_quaternion_w,
        kCandidateCount,
        "fixed64 refinement final quaternion w channel is null or misaligned");
#undef BG_REQUIRE_REFINEMENT_OUTPUT
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status validate_component_outputs(
    const bg_docking_fixed64_refinement_pipeline_v1 &pipeline,
    std::size_t coordinate_count,
    bg_docking_rigid_refinement_output_v1 &rigid,
    bg_docking_torsion_v7_output_v1 &torsion,
    bg_docking_scorer_v1_output_v1 &scorer,
    bg_docking_pose_validity_output_v1 &validity,
    bg_docking_stable_top_k_output_v1 &ranking) noexcept {
    const auto unit = pipeline.unit_system;
    if (validate_descriptor_header(
            rigid.struct_size,
            sizeof(rigid),
            rigid.abi_version,
            "fixed64 refinement rigid output size does not match ABI v1",
            "fixed64 refinement rigid output ABI version does not match") !=
            BG_STATUS_OK ||
        validate_descriptor_header(
            torsion.struct_size,
            sizeof(torsion),
            torsion.abi_version,
            "fixed64 refinement torsion output size does not match ABI v1",
            "fixed64 refinement torsion output ABI version does not match") !=
            BG_STATUS_OK ||
        validate_descriptor_header(
            scorer.struct_size,
            sizeof(scorer),
            scorer.abi_version,
            "fixed64 refinement scorer output size does not match ABI v1",
            "fixed64 refinement scorer output ABI version does not match") !=
            BG_STATUS_OK ||
        validate_descriptor_header(
            validity.struct_size,
            sizeof(validity),
            validity.abi_version,
            "fixed64 refinement validity output size does not match ABI v1",
            "fixed64 refinement validity output ABI version does not match") !=
            BG_STATUS_OK ||
        validate_descriptor_header(
            ranking.struct_size,
            sizeof(ranking),
            ranking.abi_version,
            "fixed64 refinement ranking output size does not match ABI v1",
            "fixed64 refinement ranking output ABI version does not match") !=
            BG_STATUS_OK) {
        return BG_STATUS_ABI_MISMATCH;
    }
    if (rigid.row_capacity != kCandidateCount ||
        rigid.coordinate_capacity != coordinate_count ||
        rigid.unit_system != unit || torsion.row_capacity != kCandidateCount ||
        torsion.move_capacity != kCandidateCount * kMovesPerCandidate ||
        torsion.coordinate_capacity != coordinate_count ||
        torsion.unit_system != unit || scorer.row_capacity != kCandidateCount ||
        scorer.unit_system != unit || validity.row_capacity != kCandidateCount ||
        validity.unit_system != unit || ranking.row_capacity != kCandidateCount ||
        ranking.primary_index_capacity != kCandidateCount ||
        ranking.valid_index_capacity != kCandidateCount ||
        ranking.unit_system != unit) {
        return fail(
            BG_STATUS_BUFFER_TOO_SMALL,
            "fixed64 refinement component output capacities are not exact");
    }
    const bool authority_nonzero =
        rigid.molecular_execution_authorized != 0 ||
        rigid.existing_rank_auto_change_authorized != 0 ||
        rigid.customer_pose_emission_authorized != 0 ||
        rigid.production_claim_authorized != 0 ||
        torsion.molecular_execution_authorized != 0 ||
        torsion.existing_rank_auto_change_authorized != 0 ||
        torsion.customer_pose_emission_authorized != 0 ||
        torsion.production_claim_authorized != 0 ||
        ranking.existing_rank_auto_change_authorized != 0 ||
        ranking.customer_pose_emission_authorized != 0 ||
        ranking.production_claim_authorized != 0;
    if (authority_nonzero || rigid.reserved0 != 0 || rigid.reserved1 != 0 ||
        torsion.reserved0 != 0 || torsion.reserved1 != 0 ||
        scorer.reserved0 != 0 || validity.reserved0 != 0 ||
        ranking.reserved0 != 0 || ranking.reserved1 != 0 ||
        ranking.reserved2 != 0 || !reserved_is_zero(rigid.reserved) ||
        !reserved_is_zero(torsion.reserved) ||
        !reserved_is_zero(scorer.reserved) ||
        !reserved_is_zero(validity.reserved) ||
        !reserved_is_zero(ranking.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 refinement component output authority or reserved fields are invalid");
    }
    bg_status status = BG_STATUS_OK;
#define BG_REQUIRE_COMPONENT_OUTPUT(pointer, count, message)                \
    do {                                                                    \
        status = require_channel((pointer), (count), (message));            \
        if (status != BG_STATUS_OK) {                                       \
            return status;                                                  \
        }                                                                   \
    } while (false)
    BG_REQUIRE_COMPONENT_OUTPUT(rigid.rows, kCandidateCount, "rigid rows are null");
    const std::array<double *, 12> rigid_coordinates = {
        rigid.selected_x_angstrom,       rigid.selected_y_angstrom,
        rigid.selected_z_angstrom,       rigid.comparison_v2_x_angstrom,
        rigid.comparison_v2_y_angstrom,  rigid.comparison_v2_z_angstrom,
        rigid.baseline_v3_x_angstrom,    rigid.baseline_v3_y_angstrom,
        rigid.baseline_v3_z_angstrom,    rigid.clearance_v4_x_angstrom,
        rigid.clearance_v4_y_angstrom,   rigid.clearance_v4_z_angstrom,
    };
    for (double *pointer : rigid_coordinates) {
        BG_REQUIRE_COMPONENT_OUTPUT(pointer, coordinate_count, "rigid coordinate output is null");
    }
    BG_REQUIRE_COMPONENT_OUTPUT(torsion.rows, kCandidateCount, "torsion rows are null");
    BG_REQUIRE_COMPONENT_OUTPUT(
        torsion.moves,
        kCandidateCount * kMovesPerCandidate,
        "torsion moves are null");
    const std::array<double *, 8> torsion_coordinates = {
        torsion.optimized_x_angstrom,
        torsion.optimized_y_angstrom,
        torsion.optimized_z_angstrom,
        torsion.optimized_torsion_angles_radians,
        torsion.final_x_angstrom,
        torsion.final_y_angstrom,
        torsion.final_z_angstrom,
        torsion.final_torsion_angles_radians,
    };
    for (double *pointer : torsion_coordinates) {
        BG_REQUIRE_COMPONENT_OUTPUT(pointer, coordinate_count, "torsion coordinate output is null");
    }
    BG_REQUIRE_COMPONENT_OUTPUT(scorer.rows, kCandidateCount, "scorer rows are null");
    BG_REQUIRE_COMPONENT_OUTPUT(validity.rows, kCandidateCount, "validity rows are null");
    BG_REQUIRE_COMPONENT_OUTPUT(ranking.rows, kCandidateCount, "ranking rows are null");
    BG_REQUIRE_COMPONENT_OUTPUT(
        ranking.primary_slot_indices,
        kCandidateCount,
        "primary ranking indices are null");
    BG_REQUIRE_COMPONENT_OUTPUT(
        ranking.valid_slot_indices,
        kCandidateCount,
        "valid ranking indices are null");
#undef BG_REQUIRE_COMPONENT_OUTPUT
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status validate_cluster_output(
    const bg_docking_fixed64_refinement_pipeline_v1 &pipeline,
    bg_docking_rmsd_cluster_output_v1 &output) noexcept {
    bg_status status = validate_descriptor_header(
        output.struct_size,
        sizeof(output),
        output.abi_version,
        "fixed64 refinement cluster output size does not match ABI v1",
        "fixed64 refinement cluster output ABI version does not match");
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (output.row_capacity != kCandidateCount ||
        output.representative_index_capacity != kCandidateCount ||
        output.top_k_index_capacity != BG_DOCKING_STABLE_TOP_K_LIMIT ||
        output.unit_system != pipeline.unit_system || output.reserved0 != 0 ||
        output.existing_rank_auto_change_authorized != 0 ||
        output.customer_pose_emission_authorized != 0 ||
        output.production_claim_authorized != 0 || output.reserved1 != 0 ||
        output.reserved2 != 0 || !reserved_is_zero(output.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 refinement cluster output capacity, units, authority, or reserved fields are invalid");
    }
    status = require_channel(
        output.rows,
        kCandidateCount,
        "fixed64 refinement cluster rows are null or misaligned");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = require_channel(
        output.representative_slot_indices,
        kCandidateCount,
        "fixed64 refinement cluster representatives are null or misaligned");
    if (status != BG_STATUS_OK) {
        return status;
    }
    return require_channel(
        output.top_k_slot_indices,
        BG_DOCKING_STABLE_TOP_K_LIMIT,
        "fixed64 refinement cluster Top-K indices are null or misaligned");
}

[[nodiscard]] bg_status validate_no_overlap(
    const bg_context &context,
    const bg_docking_fixed64_refinement_pipeline_v1 &pipeline,
    const bg_docking_fixed64_refinement_input_v1 &input,
    std::size_t coordinate_count,
    bg_docking_rigid_refinement_output_v1 &rigid,
    bg_docking_torsion_v7_output_v1 &torsion,
    bg_docking_scorer_v1_output_v1 &scorer,
    bg_docking_pose_validity_output_v1 &validity,
    bg_docking_stable_top_k_output_v1 &ranking,
    bg_docking_rmsd_cluster_output_v1 &cluster,
    bg_docking_fixed64_refinement_output_v1 &output) {
    std::vector<MemoryRange> inputs;
    std::vector<MemoryRange> outputs;
    inputs.reserve(18);
    outputs.reserve(44);
    add_range(&inputs, &context, 1);
    add_range(&inputs, &pipeline, 1);
    add_range(&inputs, &input, 1);
    add_range(&inputs, input.candidate_mode, kCandidateCount);
    add_range(&inputs, input.rigid_max_steps, kCandidateCount);
    add_range(
        &inputs, input.proposal_is_torsion_eligible, kCandidateCount);
    add_range(&inputs, input.torsion_max_steps, kCandidateCount);
    add_range(&inputs, input.source_x_angstrom, coordinate_count);
    add_range(&inputs, input.source_y_angstrom, coordinate_count);
    add_range(&inputs, input.source_z_angstrom, coordinate_count);
    add_range(
        &inputs, input.baseline_torsion_angles_radians, coordinate_count);
    add_range(&inputs, input.source_quaternion_x, kCandidateCount);
    add_range(&inputs, input.source_quaternion_y, kCandidateCount);
    add_range(&inputs, input.source_quaternion_z, kCandidateCount);
    add_range(&inputs, input.source_quaternion_w, kCandidateCount);

    add_range(&outputs, &rigid, 1);
    add_range(&outputs, rigid.rows, kCandidateCount);
    const std::array<double *, 12> rigid_coordinates = {
        rigid.selected_x_angstrom,       rigid.selected_y_angstrom,
        rigid.selected_z_angstrom,       rigid.comparison_v2_x_angstrom,
        rigid.comparison_v2_y_angstrom,  rigid.comparison_v2_z_angstrom,
        rigid.baseline_v3_x_angstrom,    rigid.baseline_v3_y_angstrom,
        rigid.baseline_v3_z_angstrom,    rigid.clearance_v4_x_angstrom,
        rigid.clearance_v4_y_angstrom,   rigid.clearance_v4_z_angstrom,
    };
    for (double *pointer : rigid_coordinates) {
        add_range(&outputs, pointer, coordinate_count);
    }
    add_range(&outputs, &torsion, 1);
    add_range(&outputs, torsion.rows, kCandidateCount);
    add_range(
        &outputs,
        torsion.moves,
        kCandidateCount * kMovesPerCandidate);
    const std::array<double *, 8> torsion_coordinates = {
        torsion.optimized_x_angstrom,
        torsion.optimized_y_angstrom,
        torsion.optimized_z_angstrom,
        torsion.optimized_torsion_angles_radians,
        torsion.final_x_angstrom,
        torsion.final_y_angstrom,
        torsion.final_z_angstrom,
        torsion.final_torsion_angles_radians,
    };
    for (double *pointer : torsion_coordinates) {
        add_range(&outputs, pointer, coordinate_count);
    }
    add_range(&outputs, &scorer, 1);
    add_range(&outputs, scorer.rows, kCandidateCount);
    add_range(&outputs, &validity, 1);
    add_range(&outputs, validity.rows, kCandidateCount);
    add_range(&outputs, &ranking, 1);
    add_range(&outputs, ranking.rows, kCandidateCount);
    add_range(&outputs, ranking.primary_slot_indices, kCandidateCount);
    add_range(&outputs, ranking.valid_slot_indices, kCandidateCount);
    add_range(&outputs, &cluster, 1);
    add_range(&outputs, cluster.rows, kCandidateCount);
    add_range(
        &outputs, cluster.representative_slot_indices, kCandidateCount);
    add_range(
        &outputs,
        cluster.top_k_slot_indices,
        BG_DOCKING_STABLE_TOP_K_LIMIT);
    add_range(&outputs, &output, 1);
    add_range(&outputs, output.rows, kCandidateCount);
    add_range(&outputs, output.final_x_angstrom, coordinate_count);
    add_range(&outputs, output.final_y_angstrom, coordinate_count);
    add_range(&outputs, output.final_z_angstrom, coordinate_count);
    add_range(&outputs, output.final_quaternion_x, kCandidateCount);
    add_range(&outputs, output.final_quaternion_y, kCandidateCount);
    add_range(&outputs, output.final_quaternion_z, kCandidateCount);
    add_range(&outputs, output.final_quaternion_w, kCandidateCount);
    for (std::size_t left = 0; left < outputs.size(); ++left) {
        for (std::size_t right = left + 1; right < outputs.size(); ++right) {
            if (ranges_overlap(outputs[left], outputs[right])) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "fixed64 refinement output buffers overlap");
            }
        }
        for (const MemoryRange &input_range : inputs) {
            if (ranges_overlap(outputs[left], input_range)) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "fixed64 refinement input and output buffers overlap");
            }
        }
    }
    return BG_STATUS_OK;
}

[[nodiscard]] Quaternion compose_quaternion(
    Quaternion source,
    const double rotation_vector[3]) noexcept {
    const double angle = std::sqrt(
        rotation_vector[0] * rotation_vector[0] +
        rotation_vector[1] * rotation_vector[1] +
        rotation_vector[2] * rotation_vector[2]);
    if (angle == 0.0) {
        return source;
    }
    if (!std::isfinite(angle)) {
        const double quiet = std::numeric_limits<double>::quiet_NaN();
        return {quiet, quiet, quiet, quiet};
    }
    const double scale = std::sin(0.5 * angle) / angle;
    const Quaternion delta{
        rotation_vector[0] * scale,
        rotation_vector[1] * scale,
        rotation_vector[2] * scale,
        std::cos(0.5 * angle),
    };
    Quaternion result{
        delta.w * source.x + delta.x * source.w + delta.y * source.z -
            delta.z * source.y,
        delta.w * source.y - delta.x * source.z + delta.y * source.w +
            delta.z * source.x,
        delta.w * source.z + delta.x * source.y - delta.y * source.x +
            delta.z * source.w,
        delta.w * source.w - delta.x * source.x - delta.y * source.y -
            delta.z * source.z,
    };
    if (result.x == 0.0) result.x = 0.0;
    if (result.y == 0.0) result.y = 0.0;
    if (result.z == 0.0) result.z = 0.0;
    if (result.w == 0.0) result.w = 0.0;
    return result;
}

template <typename Type>
void copy_values(Type *destination, const Type *source, std::size_t count) {
    std::copy_n(source, count, destination);
}

}  // namespace betelgeuze::native::docking::refinement_pipeline

using betelgeuze::native::fail;
using betelgeuze::native::guarded_status;
using betelgeuze::native::pointer_is_aligned;
using betelgeuze::native::validate_initializer_compatibility;

extern "C" BG_API bg_status BG_CALL
bg_docking_fixed64_refinement_input_v1_init(
    bg_docking_fixed64_refinement_input_v1 *input,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            input,
            caller_struct_size,
            sizeof(bg_docking_fixed64_refinement_input_v1),
            caller_abi_version,
            "fixed64 refinement input initializer pointer is null",
            "fixed64 refinement input initializer size does not match",
            "fixed64 refinement input initializer ABI version does not match");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *input = bg_docking_fixed64_refinement_input_v1{};
        input->struct_size = static_cast<uint32_t>(sizeof(*input));
        input->abi_version = BG_ABI_VERSION;
        input->candidate_count = BG_DOCKING_FIXED64_CANDIDATE_COUNT;
        input->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL
bg_docking_fixed64_refinement_output_v1_init(
    bg_docking_fixed64_refinement_output_v1 *output,
    size_t caller_struct_size,
    uint32_t caller_abi_version) BG_NOEXCEPT {
    return guarded_status([&]() -> bg_status {
        const bg_status status = validate_initializer_compatibility(
            output,
            caller_struct_size,
            sizeof(bg_docking_fixed64_refinement_output_v1),
            caller_abi_version,
            "fixed64 refinement output initializer pointer is null",
            "fixed64 refinement output initializer size does not match",
            "fixed64 refinement output initializer ABI version does not match");
        if (status != BG_STATUS_OK) {
            return status;
        }
        *output = bg_docking_fixed64_refinement_output_v1{};
        output->struct_size = static_cast<uint32_t>(sizeof(*output));
        output->abi_version = BG_ABI_VERSION;
        output->unit_system = BG_UNIT_SYSTEM_ANGSTROM_KCAL_MOL;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL
bg_docking_fixed64_refinement_pipeline_v1_create(
    const bg_context *context,
    const bg_docking_rigid_refinement_context_soa_v1 *rigid_descriptor,
    const bg_docking_torsion_v7_context_soa_v1 *torsion_descriptor,
    const bg_docking_scorer_v1_context_soa_v1 *scorer_descriptor,
    const bg_docking_pose_validity_context_soa_v1 *validity_descriptor,
    bg_docking_fixed64_refinement_pipeline_v1 **out_pipeline) BG_NOEXCEPT {
    using namespace betelgeuze::native::docking::refinement_pipeline;
    return guarded_status([&]() -> bg_status {
        if (context == nullptr || rigid_descriptor == nullptr ||
            torsion_descriptor == nullptr || scorer_descriptor == nullptr ||
            validity_descriptor == nullptr || out_pipeline == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 refinement pipeline create inputs and output must not be null");
        }
        if (!pointer_is_aligned(context) ||
            !pointer_is_aligned(rigid_descriptor) ||
            !pointer_is_aligned(torsion_descriptor) ||
            !pointer_is_aligned(scorer_descriptor) ||
            !pointer_is_aligned(validity_descriptor) ||
            !pointer_is_aligned(out_pipeline)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 refinement pipeline create pointers are misaligned");
        }
        bg_status status = validate_create_output_range(
            *context,
            *rigid_descriptor,
            *torsion_descriptor,
            *scorer_descriptor,
            *validity_descriptor,
            out_pipeline);
        if (status != BG_STATUS_OK) {
            return status;
        }
        *out_pipeline = nullptr;
        auto pipeline =
            std::make_unique<bg_docking_fixed64_refinement_pipeline_v1>();
        pipeline->backend = context->backend;
        pipeline->unit_system = context->unit_system;
        pipeline->device_ordinal = context->device_ordinal;
        pipeline->ligand_atom_count = rigid_descriptor->ligand_atom_count;
        status = bg_docking_rigid_refinement_create(
            context, rigid_descriptor, &pipeline->rigid);
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = bg_docking_torsion_v7_create(
            context, torsion_descriptor, &pipeline->torsion);
        if (status != BG_STATUS_OK) {
            destroy_components(pipeline.get());
            return status;
        }
        status = bg_docking_fixed64_downstream_v1_create(
            context,
            scorer_descriptor,
            validity_descriptor,
            &pipeline->downstream);
        if (status != BG_STATUS_OK) {
            destroy_components(pipeline.get());
            return status;
        }
        status = validate_component_binding(
            *context,
            *rigid_descriptor,
            *torsion_descriptor,
            *scorer_descriptor,
            *validity_descriptor);
        if (status != BG_STATUS_OK) {
            destroy_components(pipeline.get());
            return status;
        }
        *out_pipeline = pipeline.release();
        return BG_STATUS_OK;
    });
}

extern "C" BG_API void BG_CALL
bg_docking_fixed64_refinement_pipeline_v1_destroy(
    bg_docking_fixed64_refinement_pipeline_v1 *pipeline) BG_NOEXCEPT {
    using namespace betelgeuze::native::docking::refinement_pipeline;
    destroy_components(pipeline);
    delete pipeline;
}

extern "C" BG_API bg_status BG_CALL
bg_docking_fixed64_refinement_pipeline_v1_get_backend(
    const bg_docking_fixed64_refinement_pipeline_v1 *pipeline,
    bg_backend *backend) BG_NOEXCEPT {
    using namespace betelgeuze::native::docking::refinement_pipeline;
    return guarded_status([&]() -> bg_status {
        if (pipeline == nullptr || backend == nullptr ||
            !pointer_is_aligned(pipeline) || !pointer_is_aligned(backend)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 refinement pipeline handle and backend output are invalid");
        }
        if (ranges_overlap(
                {pipeline, sizeof(*pipeline)},
                {backend, sizeof(*backend)})) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 refinement backend output overlaps the pipeline handle");
        }
        *backend = pipeline->backend;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL
bg_docking_fixed64_refinement_pipeline_v1_run(
    const bg_context *context,
    const bg_docking_fixed64_refinement_pipeline_v1 *pipeline,
    const bg_docking_fixed64_refinement_input_v1 *input,
    bg_docking_rigid_refinement_output_v1 *rigid_output,
    bg_docking_torsion_v7_output_v1 *torsion_output,
    bg_docking_scorer_v1_output_v1 *scorer_output,
    bg_docking_pose_validity_output_v1 *validity_output,
    bg_docking_stable_top_k_output_v1 *ranking_output,
    bg_docking_rmsd_cluster_output_v1 *cluster_output,
    bg_docking_fixed64_refinement_output_v1 *pipeline_output) BG_NOEXCEPT {
    using namespace betelgeuze::native::docking::refinement_pipeline;
    return guarded_status([&]() -> bg_status {
        if (context == nullptr || pipeline == nullptr || input == nullptr ||
            rigid_output == nullptr || torsion_output == nullptr ||
            scorer_output == nullptr || validity_output == nullptr ||
            ranking_output == nullptr || cluster_output == nullptr ||
            pipeline_output == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 refinement pipeline run inputs and outputs must not be null");
        }
        if (!pointer_is_aligned(context) || !pointer_is_aligned(pipeline) ||
            !pointer_is_aligned(input) || !pointer_is_aligned(rigid_output) ||
            !pointer_is_aligned(torsion_output) ||
            !pointer_is_aligned(scorer_output) ||
            !pointer_is_aligned(validity_output) ||
            !pointer_is_aligned(ranking_output) ||
            !pointer_is_aligned(cluster_output) ||
            !pointer_is_aligned(pipeline_output)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 refinement pipeline run descriptors are misaligned");
        }
        if (context->backend != pipeline->backend ||
            context->unit_system != pipeline->unit_system ||
            context->device_ordinal != pipeline->device_ordinal ||
            pipeline->rigid == nullptr || pipeline->torsion == nullptr ||
            pipeline->downstream == nullptr ||
            pipeline->downstream->ranker == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 refinement pipeline handle is cross-wired or invalid");
        }
        std::size_t coordinate_count = 0;
        bg_status status = validate_input(*pipeline, *input, &coordinate_count);
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = validate_component_outputs(
            *pipeline,
            coordinate_count,
            *rigid_output,
            *torsion_output,
            *scorer_output,
            *validity_output,
            *ranking_output);
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = validate_cluster_output(*pipeline, *cluster_output);
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = validate_pipeline_output(
            *pipeline, *pipeline_output, coordinate_count);
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = validate_no_overlap(
            *context,
            *pipeline,
            *input,
            coordinate_count,
            *rigid_output,
            *torsion_output,
            *scorer_output,
            *validity_output,
            *ranking_output,
            *cluster_output,
            *pipeline_output);
        if (status != BG_STATUS_OK) {
            return status;
        }

        std::array<bg_docking_rigid_refinement_row_v1, kCandidateCount>
            rigid_rows{};
        std::array<std::vector<double>, 12> rigid_coordinates;
        for (auto &values : rigid_coordinates) {
            values.resize(coordinate_count);
        }
        bg_docking_rigid_refinement_output_v1 local_rigid{};
        status = bg_docking_rigid_refinement_output_v1_init(
            &local_rigid, sizeof(local_rigid), BG_ABI_VERSION);
        if (status != BG_STATUS_OK) return status;
        local_rigid.row_capacity = kCandidateCount;
        local_rigid.coordinate_capacity = coordinate_count;
        local_rigid.rows = rigid_rows.data();
        local_rigid.selected_x_angstrom = rigid_coordinates[0].data();
        local_rigid.selected_y_angstrom = rigid_coordinates[1].data();
        local_rigid.selected_z_angstrom = rigid_coordinates[2].data();
        local_rigid.comparison_v2_x_angstrom = rigid_coordinates[3].data();
        local_rigid.comparison_v2_y_angstrom = rigid_coordinates[4].data();
        local_rigid.comparison_v2_z_angstrom = rigid_coordinates[5].data();
        local_rigid.baseline_v3_x_angstrom = rigid_coordinates[6].data();
        local_rigid.baseline_v3_y_angstrom = rigid_coordinates[7].data();
        local_rigid.baseline_v3_z_angstrom = rigid_coordinates[8].data();
        local_rigid.clearance_v4_x_angstrom = rigid_coordinates[9].data();
        local_rigid.clearance_v4_y_angstrom = rigid_coordinates[10].data();
        local_rigid.clearance_v4_z_angstrom = rigid_coordinates[11].data();
        bg_docking_rigid_refinement_candidate_batch_soa_v1 rigid_batch{};
        status = bg_docking_rigid_refinement_candidate_batch_soa_v1_init(
            &rigid_batch, sizeof(rigid_batch), BG_ABI_VERSION);
        if (status != BG_STATUS_OK) return status;
        rigid_batch.ligand_atom_count = input->ligand_atom_count;
        rigid_batch.candidate_mode = input->candidate_mode;
        rigid_batch.max_steps = input->rigid_max_steps;
        rigid_batch.x_angstrom = input->source_x_angstrom;
        rigid_batch.y_angstrom = input->source_y_angstrom;
        rigid_batch.z_angstrom = input->source_z_angstrom;
        status = bg_docking_rigid_refinement_fixed64(
            context, pipeline->rigid, &rigid_batch, &local_rigid);
        if (status != BG_STATUS_OK) {
            return status;
        }

        std::array<bg_docking_torsion_v7_candidate_state, kCandidateCount>
            torsion_states{};
        std::array<uint64_t, kCandidateCount> baseline_steps{};
        for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
            const auto mode = input->candidate_mode[slot];
            const bool v6_mode =
                mode ==
                    BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V2_LANE ||
                mode ==
                    BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V3_LANE;
            if (rigid_rows[slot].status ==
                    BG_DOCKING_RIGID_REFINEMENT_ROW_REFINED &&
                v6_mode) {
                torsion_states[slot] = BG_DOCKING_TORSION_V7_CANDIDATE_REFINE;
                baseline_steps[slot] = rigid_rows[slot].selected.accepted_steps;
            }
        }
        std::array<bg_docking_torsion_v7_row_v1, kCandidateCount>
            torsion_rows{};
        std::array<bg_docking_torsion_v7_move_v1,
                   kCandidateCount * kMovesPerCandidate>
            torsion_moves{};
        std::array<std::vector<double>, 8> torsion_coordinates;
        for (auto &values : torsion_coordinates) {
            values.resize(coordinate_count);
        }
        bg_docking_torsion_v7_output_v1 local_torsion{};
        status = bg_docking_torsion_v7_output_v1_init(
            &local_torsion, sizeof(local_torsion), BG_ABI_VERSION);
        if (status != BG_STATUS_OK) return status;
        local_torsion.row_capacity = kCandidateCount;
        local_torsion.move_capacity = torsion_moves.size();
        local_torsion.coordinate_capacity = coordinate_count;
        local_torsion.rows = torsion_rows.data();
        local_torsion.moves = torsion_moves.data();
        local_torsion.optimized_x_angstrom = torsion_coordinates[0].data();
        local_torsion.optimized_y_angstrom = torsion_coordinates[1].data();
        local_torsion.optimized_z_angstrom = torsion_coordinates[2].data();
        local_torsion.optimized_torsion_angles_radians =
            torsion_coordinates[3].data();
        local_torsion.final_x_angstrom = torsion_coordinates[4].data();
        local_torsion.final_y_angstrom = torsion_coordinates[5].data();
        local_torsion.final_z_angstrom = torsion_coordinates[6].data();
        local_torsion.final_torsion_angles_radians =
            torsion_coordinates[7].data();
        bg_docking_torsion_v7_candidate_batch_soa_v1 torsion_batch{};
        status = bg_docking_torsion_v7_candidate_batch_soa_v1_init(
            &torsion_batch, sizeof(torsion_batch), BG_ABI_VERSION);
        if (status != BG_STATUS_OK) return status;
        torsion_batch.ligand_atom_count = input->ligand_atom_count;
        torsion_batch.candidate_state = torsion_states.data();
        torsion_batch.proposal_is_torsion_eligible =
            input->proposal_is_torsion_eligible;
        torsion_batch.max_steps = input->torsion_max_steps;
        torsion_batch.baseline_v6_accepted_steps = baseline_steps.data();
        torsion_batch.source_x_angstrom = input->source_x_angstrom;
        torsion_batch.source_y_angstrom = input->source_y_angstrom;
        torsion_batch.source_z_angstrom = input->source_z_angstrom;
        torsion_batch.baseline_v6_x_angstrom = rigid_coordinates[0].data();
        torsion_batch.baseline_v6_y_angstrom = rigid_coordinates[1].data();
        torsion_batch.baseline_v6_z_angstrom = rigid_coordinates[2].data();
        torsion_batch.baseline_v6_torsion_angles_radians =
            input->baseline_torsion_angles_radians;
        status = bg_docking_torsion_v7_refine_fixed64(
            context, pipeline->torsion, &torsion_batch, &local_torsion);
        if (status != BG_STATUS_OK) {
            return status;
        }

        std::array<bg_docking_fixed64_refinement_row_v1, kCandidateCount>
            pipeline_rows{};
        std::array<bg_docking_scorer_v1_candidate_state, kCandidateCount>
            downstream_states{};
        std::array<std::vector<double>, 3> final_coordinates;
        for (auto &values : final_coordinates) {
            values.resize(coordinate_count);
        }
        std::array<std::array<double, kCandidateCount>, 4> final_quaternions{};
        const auto ligand_count =
            static_cast<std::size_t>(input->ligand_atom_count);
        for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
            auto &row = pipeline_rows[slot];
            row.slot_index = static_cast<uint32_t>(slot);
            row.rigid_failure_code = rigid_rows[slot].failure_code;
            row.selected_rigid_profile = rigid_rows[slot].selected_profile;
            const bool rigid_ready =
                rigid_rows[slot].status ==
                BG_DOCKING_RIGID_REFINEMENT_ROW_REFINED;
            const bool v6_mode =
                input->candidate_mode[slot] ==
                    BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V2_LANE ||
                input->candidate_mode[slot] ==
                    BG_DOCKING_RIGID_REFINEMENT_CANDIDATE_V6_BASELINE_V3_LANE;
            row.torsion_v7_applicable =
                static_cast<uint8_t>(rigid_ready && v6_mode);
            const double *selected_x = nullptr;
            const double *selected_y = nullptr;
            const double *selected_z = nullptr;
            if (!rigid_ready) {
                row.status = BG_DOCKING_FIXED64_REFINEMENT_ROW_TYPED_FAILURE;
                row.failure_stage =
                    BG_DOCKING_FIXED64_REFINEMENT_FAILURE_STAGE_RIGID;
            } else if (v6_mode &&
                       torsion_rows[slot].status !=
                           BG_DOCKING_TORSION_V7_ROW_REFINED) {
                row.status = BG_DOCKING_FIXED64_REFINEMENT_ROW_TYPED_FAILURE;
                row.failure_stage =
                    BG_DOCKING_FIXED64_REFINEMENT_FAILURE_STAGE_TORSION_V7;
                row.torsion_v7_failure_code = torsion_rows[slot].failure_code;
            } else {
                row.status =
                    BG_DOCKING_FIXED64_REFINEMENT_ROW_COORDINATE_READY;
                row.failure_stage =
                    BG_DOCKING_FIXED64_REFINEMENT_FAILURE_STAGE_NONE;
                row.coordinate_available = UINT8_C(1);
                row.downstream_candidate_state =
                    BG_DOCKING_SCORER_V1_CANDIDATE_ACTIVE;
                downstream_states[slot] =
                    BG_DOCKING_SCORER_V1_CANDIDATE_ACTIVE;
                if (v6_mode) {
                    row.coordinate_origin =
                        BG_DOCKING_FIXED64_REFINEMENT_COORDINATE_TORSION_V7_FINAL;
                    row.torsion_v7_selected =
                        torsion_rows[slot].torsion_selected;
                    selected_x = torsion_coordinates[4].data();
                    selected_y = torsion_coordinates[5].data();
                    selected_z = torsion_coordinates[6].data();
                } else {
                    row.coordinate_origin =
                        BG_DOCKING_FIXED64_REFINEMENT_COORDINATE_RIGID_SELECTED;
                    selected_x = rigid_coordinates[0].data();
                    selected_y = rigid_coordinates[1].data();
                    selected_z = rigid_coordinates[2].data();
                }
                const std::size_t begin = slot * ligand_count;
                std::copy_n(
                    selected_x + begin,
                    ligand_count,
                    final_coordinates[0].data() + begin);
                std::copy_n(
                    selected_y + begin,
                    ligand_count,
                    final_coordinates[1].data() + begin);
                std::copy_n(
                    selected_z + begin,
                    ligand_count,
                    final_coordinates[2].data() + begin);
                const Quaternion final = compose_quaternion(
                    {
                        input->source_quaternion_x[slot],
                        input->source_quaternion_y[slot],
                        input->source_quaternion_z[slot],
                        input->source_quaternion_w[slot],
                    },
                    rigid_rows[slot].selected.total_rotation_vector_radians);
                final_quaternions[0][slot] = final.x;
                final_quaternions[1][slot] = final.y;
                final_quaternions[2][slot] = final.z;
                final_quaternions[3][slot] = final.w;
            }
        }

        std::array<bg_docking_scorer_v1_row_v1, kCandidateCount> scorer_rows{};
        bg_docking_scorer_v1_output_v1 local_scorer{};
        status = bg_docking_scorer_v1_output_v1_init(
            &local_scorer, sizeof(local_scorer), BG_ABI_VERSION);
        if (status != BG_STATUS_OK) return status;
        local_scorer.row_capacity = kCandidateCount;
        local_scorer.rows = scorer_rows.data();
        std::array<bg_docking_pose_validity_row_v1, kCandidateCount>
            validity_rows{};
        bg_docking_pose_validity_output_v1 local_validity{};
        status = bg_docking_pose_validity_output_v1_init(
            &local_validity, sizeof(local_validity), BG_ABI_VERSION);
        if (status != BG_STATUS_OK) return status;
        local_validity.row_capacity = kCandidateCount;
        local_validity.rows = validity_rows.data();
        std::array<bg_docking_stable_top_k_row_v1, kCandidateCount>
            ranking_rows{};
        std::array<uint32_t, kCandidateCount> primary_indices{};
        std::array<uint32_t, kCandidateCount> valid_indices{};
        bg_docking_stable_top_k_output_v1 local_ranking{};
        status = bg_docking_stable_top_k_output_v1_init(
            &local_ranking, sizeof(local_ranking), BG_ABI_VERSION);
        if (status != BG_STATUS_OK) return status;
        local_ranking.row_capacity = kCandidateCount;
        local_ranking.primary_index_capacity = kCandidateCount;
        local_ranking.valid_index_capacity = kCandidateCount;
        local_ranking.rows = ranking_rows.data();
        local_ranking.primary_slot_indices = primary_indices.data();
        local_ranking.valid_slot_indices = valid_indices.data();
        bg_docking_scorer_v1_candidate_batch_soa_v1 downstream_batch{};
        status = bg_docking_scorer_v1_candidate_batch_soa_v1_init(
            &downstream_batch, sizeof(downstream_batch), BG_ABI_VERSION);
        if (status != BG_STATUS_OK) return status;
        downstream_batch.ligand_atom_count = input->ligand_atom_count;
        downstream_batch.candidate_state = downstream_states.data();
        downstream_batch.x_angstrom = final_coordinates[0].data();
        downstream_batch.y_angstrom = final_coordinates[1].data();
        downstream_batch.z_angstrom = final_coordinates[2].data();
        status = bg_docking_fixed64_downstream_v1_run(
            context,
            pipeline->downstream,
            &downstream_batch,
            final_quaternions[0].data(),
            final_quaternions[1].data(),
            final_quaternions[2].data(),
            final_quaternions[3].data(),
            &local_scorer,
            &local_validity,
            &local_ranking);
        if (status != BG_STATUS_OK) {
            return status;
        }

        std::array<bg_docking_rmsd_cluster_row_v1, kCandidateCount>
            cluster_rows{};
        std::array<uint32_t, kCandidateCount> representative_indices{};
        std::array<uint32_t, BG_DOCKING_STABLE_TOP_K_LIMIT>
            cluster_top_k_indices{};
        bg_docking_rmsd_cluster_output_v1 local_cluster{};
        status = bg_docking_rmsd_cluster_output_v1_init(
            &local_cluster, sizeof(local_cluster), BG_ABI_VERSION);
        if (status != BG_STATUS_OK) return status;
        local_cluster.row_capacity = kCandidateCount;
        local_cluster.representative_index_capacity = kCandidateCount;
        local_cluster.top_k_index_capacity = BG_DOCKING_STABLE_TOP_K_LIMIT;
        local_cluster.rows = cluster_rows.data();
        local_cluster.representative_slot_indices =
            representative_indices.data();
        local_cluster.top_k_slot_indices = cluster_top_k_indices.data();
        bg_docking_rmsd_cluster_input_v1 cluster_input{};
        status = bg_docking_rmsd_cluster_input_v1_init(
            &cluster_input, sizeof(cluster_input), BG_ABI_VERSION);
        if (status != BG_STATUS_OK) return status;
        cluster_input.candidate_count = kCandidateCount;
        cluster_input.ligand_atom_count = input->ligand_atom_count;
        cluster_input.valid_index_count = local_ranking.valid_index_count;
        cluster_input.top_k_limit = BG_DOCKING_STABLE_TOP_K_LIMIT;
        cluster_input.rmsd_threshold_angstrom =
            input->rmsd_threshold_angstrom;
        cluster_input.ranking_rows = ranking_rows.data();
        cluster_input.valid_slot_indices = valid_indices.data();
        cluster_input.x_angstrom = final_coordinates[0].data();
        cluster_input.y_angstrom = final_coordinates[1].data();
        cluster_input.z_angstrom = final_coordinates[2].data();
        status = bg_docking_stable_top_k_v1_cluster_direct_rmsd_fixed64(
            context,
            pipeline->downstream->ranker,
            &cluster_input,
            &local_cluster);
        if (status != BG_STATUS_OK) {
            return status;
        }
        for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
            std::copy_n(
                ranking_rows[slot].coordinate_sha256,
                32,
                pipeline_rows[slot].coordinate_sha256);
        }

        copy_values(rigid_output->rows, rigid_rows.data(), kCandidateCount);
        const std::array<double *, 12> rigid_destinations = {
            rigid_output->selected_x_angstrom,
            rigid_output->selected_y_angstrom,
            rigid_output->selected_z_angstrom,
            rigid_output->comparison_v2_x_angstrom,
            rigid_output->comparison_v2_y_angstrom,
            rigid_output->comparison_v2_z_angstrom,
            rigid_output->baseline_v3_x_angstrom,
            rigid_output->baseline_v3_y_angstrom,
            rigid_output->baseline_v3_z_angstrom,
            rigid_output->clearance_v4_x_angstrom,
            rigid_output->clearance_v4_y_angstrom,
            rigid_output->clearance_v4_z_angstrom,
        };
        for (std::size_t index = 0; index < rigid_destinations.size(); ++index) {
            copy_values(
                rigid_destinations[index],
                rigid_coordinates[index].data(),
                coordinate_count);
        }
        rigid_output->row_count = kCandidateCount;
        rigid_output->coordinate_count = coordinate_count;

        copy_values(torsion_output->rows, torsion_rows.data(), kCandidateCount);
        copy_values(
            torsion_output->moves,
            torsion_moves.data(),
            torsion_moves.size());
        const std::array<double *, 8> torsion_destinations = {
            torsion_output->optimized_x_angstrom,
            torsion_output->optimized_y_angstrom,
            torsion_output->optimized_z_angstrom,
            torsion_output->optimized_torsion_angles_radians,
            torsion_output->final_x_angstrom,
            torsion_output->final_y_angstrom,
            torsion_output->final_z_angstrom,
            torsion_output->final_torsion_angles_radians,
        };
        for (std::size_t index = 0; index < torsion_destinations.size(); ++index) {
            copy_values(
                torsion_destinations[index],
                torsion_coordinates[index].data(),
                coordinate_count);
        }
        torsion_output->row_count = kCandidateCount;
        torsion_output->move_count = torsion_moves.size();
        torsion_output->coordinate_count = coordinate_count;

        copy_values(scorer_output->rows, scorer_rows.data(), kCandidateCount);
        scorer_output->row_count = kCandidateCount;
        copy_values(validity_output->rows, validity_rows.data(), kCandidateCount);
        validity_output->row_count = kCandidateCount;
        copy_values(ranking_output->rows, ranking_rows.data(), kCandidateCount);
        copy_values(
            ranking_output->primary_slot_indices,
            primary_indices.data(),
            kCandidateCount);
        copy_values(
            ranking_output->valid_slot_indices,
            valid_indices.data(),
            kCandidateCount);
        ranking_output->row_count = kCandidateCount;
        ranking_output->primary_index_count = local_ranking.primary_index_count;
        ranking_output->valid_index_count = local_ranking.valid_index_count;

        copy_values(cluster_output->rows, cluster_rows.data(), kCandidateCount);
        copy_values(
            cluster_output->representative_slot_indices,
            representative_indices.data(),
            kCandidateCount);
        copy_values(
            cluster_output->top_k_slot_indices,
            cluster_top_k_indices.data(),
            BG_DOCKING_STABLE_TOP_K_LIMIT);
        cluster_output->row_count = kCandidateCount;
        cluster_output->representative_index_count =
            local_cluster.representative_index_count;
        cluster_output->top_k_index_count = local_cluster.top_k_index_count;

        copy_values(pipeline_output->rows, pipeline_rows.data(), kCandidateCount);
        copy_values(
            pipeline_output->final_x_angstrom,
            final_coordinates[0].data(),
            coordinate_count);
        copy_values(
            pipeline_output->final_y_angstrom,
            final_coordinates[1].data(),
            coordinate_count);
        copy_values(
            pipeline_output->final_z_angstrom,
            final_coordinates[2].data(),
            coordinate_count);
        copy_values(
            pipeline_output->final_quaternion_x,
            final_quaternions[0].data(),
            kCandidateCount);
        copy_values(
            pipeline_output->final_quaternion_y,
            final_quaternions[1].data(),
            kCandidateCount);
        copy_values(
            pipeline_output->final_quaternion_z,
            final_quaternions[2].data(),
            kCandidateCount);
        copy_values(
            pipeline_output->final_quaternion_w,
            final_quaternions[3].data(),
            kCandidateCount);
        pipeline_output->row_count = kCandidateCount;
        pipeline_output->coordinate_count = coordinate_count;
        pipeline_output->quaternion_count = kCandidateCount;
        return BG_STATUS_OK;
    });
}
