#include "../dynamics/sha256.hpp"
#include "../internal.hpp"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <memory>
#include <utility>

namespace betelgeuze::native::docking::downstream {
namespace {

constexpr std::size_t kCandidateCount =
    BG_DOCKING_FIXED64_CANDIDATE_COUNT;
constexpr std::size_t kDigestSize = 32;
constexpr std::size_t kMaximumLigandAtomCount = 512;
constexpr std::size_t kMaximumReceptorAtomCount = 4096;
constexpr char kCoordinateHashDomain[] =
    "betelgeuze.fixed64_coordinates/native-v1";

struct LocalOutputs final {
    std::array<bg_docking_scorer_v1_row_v1, kCandidateCount> scorer_rows{};
    std::array<bg_docking_pose_validity_row_v1, kCandidateCount>
        validity_rows{};
    std::array<bg_docking_stable_top_k_row_v1, kCandidateCount>
        ranking_rows{};
    std::array<uint32_t, kCandidateCount> primary_slot_indices{};
    std::array<uint32_t, kCandidateCount> valid_slot_indices{};
    std::array<uint8_t, kCandidateCount * kDigestSize>
        coordinate_sha256{};
    uint64_t primary_count = 0;
    uint64_t valid_count = 0;
};

[[nodiscard]] bool digest_equal(
    const uint8_t (&left)[kDigestSize],
    const uint8_t (&right)[kDigestSize]) noexcept {
    return std::memcmp(left, right, kDigestSize) == 0;
}

[[nodiscard]] bool double_channels_equal(
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

[[nodiscard]] bool index_channels_equal(
    const uint64_t *left,
    const uint64_t *right,
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
    const bg_docking_scorer_v1_context_soa_v1 &scorer,
    const bg_docking_pose_validity_context_soa_v1 &validity) noexcept {
    if (scorer.unit_system != context.unit_system ||
        validity.unit_system != context.unit_system ||
        scorer.receptor_atom_count != validity.receptor_atom_count ||
        scorer.ligand_atom_count != validity.ligand_atom_count ||
        scorer.ligand_atom_count == 0 ||
        scorer.ligand_atom_count > kMaximumLigandAtomCount) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 downstream component units or atom denominators are cross-wired");
    }
    if (!digest_equal(
            scorer.authority_input_receipt_sha256,
            validity.authority_input_receipt_sha256) ||
        !digest_equal(
            scorer.receptor_system_sha256,
            validity.receptor_system_sha256) ||
        !digest_equal(
            scorer.ligand_system_sha256,
            validity.ligand_system_sha256)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 downstream component identity digests are cross-wired");
    }

    const auto receptor_count =
        static_cast<std::size_t>(scorer.receptor_atom_count);
    const auto ligand_count =
        static_cast<std::size_t>(scorer.ligand_atom_count);
    const std::array<std::pair<const double *, const double *>, 4>
        receptor_channels = {{
            {scorer.receptor_x_angstrom, validity.receptor_x_angstrom},
            {scorer.receptor_y_angstrom, validity.receptor_y_angstrom},
            {scorer.receptor_z_angstrom, validity.receptor_z_angstrom},
            {scorer.receptor_vdw_radius_angstrom,
             validity.receptor_vdw_radius_angstrom},
        }};
    const std::array<std::pair<const double *, const double *>, 4>
        ligand_channels = {{
            {scorer.ligand_reference_x_angstrom,
             validity.ligand_reference_x_angstrom},
            {scorer.ligand_reference_y_angstrom,
             validity.ligand_reference_y_angstrom},
            {scorer.ligand_reference_z_angstrom,
             validity.ligand_reference_z_angstrom},
            {scorer.ligand_vdw_radius_angstrom,
             validity.ligand_vdw_radius_angstrom},
        }};
    for (const auto &[left, right] : receptor_channels) {
        if (!double_channels_equal(left, right, receptor_count)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 downstream receptor numerical systems are cross-wired");
        }
    }
    for (const auto &[left, right] : ligand_channels) {
        if (!double_channels_equal(left, right, ligand_count)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 downstream ligand numerical systems are cross-wired");
        }
    }
    if (scorer.pocket_radius_angstrom != validity.pocket_radius_angstrom ||
        !double_channels_equal(
            scorer.pocket_center_angstrom,
            validity.pocket_center_angstrom,
            3)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 downstream pocket declarations are cross-wired");
    }
    if (scorer.ligand_exclusion_count !=
            validity.ligand_exclusion_count ||
        !index_channels_equal(
            scorer.ligand_exclusion_atom_i,
            validity.ligand_exclusion_atom_i,
            static_cast<std::size_t>(scorer.ligand_exclusion_count)) ||
        !index_channels_equal(
            scorer.ligand_exclusion_atom_j,
            validity.ligand_exclusion_atom_j,
            static_cast<std::size_t>(scorer.ligand_exclusion_count))) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 downstream ligand exclusions are cross-wired");
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bool ranges_overlap(
    const void *left,
    std::size_t left_size,
    const void *right,
    std::size_t right_size) noexcept {
    if (left == nullptr || right == nullptr || left_size == 0 ||
        right_size == 0) {
        return false;
    }
    const uintptr_t left_begin = reinterpret_cast<uintptr_t>(left);
    const uintptr_t right_begin = reinterpret_cast<uintptr_t>(right);
    if (left_begin > std::numeric_limits<uintptr_t>::max() - left_size ||
        right_begin > std::numeric_limits<uintptr_t>::max() - right_size) {
        return true;
    }
    return left_begin < right_begin + right_size &&
           right_begin < left_begin + left_size;
}

[[nodiscard]] bg_status validate_create_output_range(
    const bg_context &context,
    const bg_docking_scorer_v1_context_soa_v1 &scorer,
    const bg_docking_pose_validity_context_soa_v1 &validity,
    bg_docking_fixed64_downstream_v1 **out_pipeline) noexcept {
    if (scorer.receptor_atom_count == 0 ||
        scorer.receptor_atom_count > kMaximumReceptorAtomCount ||
        scorer.ligand_atom_count == 0 ||
        scorer.ligand_atom_count > kMaximumLigandAtomCount ||
        scorer.receptor_donor_count > scorer.receptor_atom_count ||
        scorer.ligand_donor_count > scorer.ligand_atom_count ||
        scorer.rotor_count > scorer.ligand_atom_count ||
        validity.receptor_atom_count == 0 ||
        validity.receptor_atom_count > kMaximumReceptorAtomCount ||
        validity.ligand_atom_count == 0 ||
        validity.ligand_atom_count > kMaximumLigandAtomCount) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "fixed64 downstream create denominator is outside native bounds");
    }
    const uint64_t scorer_maximum_pairs =
        scorer.ligand_atom_count * (scorer.ligand_atom_count - 1U) / 2U;
    const uint64_t validity_maximum_pairs =
        validity.ligand_atom_count * (validity.ligand_atom_count - 1U) / 2U;
    if (scorer.ligand_exclusion_count > scorer_maximum_pairs ||
        validity.bond_count > validity_maximum_pairs ||
        validity.ligand_exclusion_count > validity_maximum_pairs ||
        validity.chirality_center_count > validity.ligand_atom_count) {
        return fail(
            BG_STATUS_CAPACITY_OVERFLOW,
            "fixed64 downstream create topology denominator is impossible");
    }

    const auto scorer_receptor_count =
        static_cast<std::size_t>(scorer.receptor_atom_count);
    const auto scorer_ligand_count =
        static_cast<std::size_t>(scorer.ligand_atom_count);
    const auto scorer_receptor_donor_count =
        static_cast<std::size_t>(scorer.receptor_donor_count);
    const auto scorer_ligand_donor_count =
        static_cast<std::size_t>(scorer.ligand_donor_count);
    const auto scorer_exclusion_count =
        static_cast<std::size_t>(scorer.ligand_exclusion_count);
    const auto scorer_rotor_count =
        static_cast<std::size_t>(scorer.rotor_count);
    const auto validity_receptor_count =
        static_cast<std::size_t>(validity.receptor_atom_count);
    const auto validity_ligand_count =
        static_cast<std::size_t>(validity.ligand_atom_count);
    const auto validity_bond_count =
        static_cast<std::size_t>(validity.bond_count);
    const auto validity_exclusion_count =
        static_cast<std::size_t>(validity.ligand_exclusion_count);
    const auto validity_chirality_count =
        static_cast<std::size_t>(validity.chirality_center_count);

    const std::array<std::pair<const void *, std::size_t>, 45> inputs = {{
        {&context, sizeof(context)},
        {&scorer, sizeof(scorer)},
        {&validity, sizeof(validity)},
        {scorer.receptor_x_angstrom,
         scorer_receptor_count * sizeof(*scorer.receptor_x_angstrom)},
        {scorer.receptor_y_angstrom,
         scorer_receptor_count * sizeof(*scorer.receptor_y_angstrom)},
        {scorer.receptor_z_angstrom,
         scorer_receptor_count * sizeof(*scorer.receptor_z_angstrom)},
        {scorer.receptor_charge_elementary,
         scorer_receptor_count * sizeof(*scorer.receptor_charge_elementary)},
        {scorer.receptor_vdw_radius_angstrom,
         scorer_receptor_count * sizeof(*scorer.receptor_vdw_radius_angstrom)},
        {scorer.receptor_epsilon_kcal_per_mol,
         scorer_receptor_count * sizeof(*scorer.receptor_epsilon_kcal_per_mol)},
        {scorer.receptor_hydrophobic,
         scorer_receptor_count * sizeof(*scorer.receptor_hydrophobic)},
        {scorer.receptor_acceptor,
         scorer_receptor_count * sizeof(*scorer.receptor_acceptor)},
        {scorer.ligand_reference_x_angstrom,
         scorer_ligand_count * sizeof(*scorer.ligand_reference_x_angstrom)},
        {scorer.ligand_reference_y_angstrom,
         scorer_ligand_count * sizeof(*scorer.ligand_reference_y_angstrom)},
        {scorer.ligand_reference_z_angstrom,
         scorer_ligand_count * sizeof(*scorer.ligand_reference_z_angstrom)},
        {scorer.ligand_charge_elementary,
         scorer_ligand_count * sizeof(*scorer.ligand_charge_elementary)},
        {scorer.ligand_vdw_radius_angstrom,
         scorer_ligand_count * sizeof(*scorer.ligand_vdw_radius_angstrom)},
        {scorer.ligand_epsilon_kcal_per_mol,
         scorer_ligand_count * sizeof(*scorer.ligand_epsilon_kcal_per_mol)},
        {scorer.ligand_hydrophobic,
         scorer_ligand_count * sizeof(*scorer.ligand_hydrophobic)},
        {scorer.ligand_acceptor,
         scorer_ligand_count * sizeof(*scorer.ligand_acceptor)},
        {scorer.receptor_donor_atom_index,
         scorer_receptor_donor_count * sizeof(*scorer.receptor_donor_atom_index)},
        {scorer.receptor_hydrogen_atom_index,
         scorer_receptor_donor_count * sizeof(*scorer.receptor_hydrogen_atom_index)},
        {scorer.ligand_donor_atom_index,
         scorer_ligand_donor_count * sizeof(*scorer.ligand_donor_atom_index)},
        {scorer.ligand_hydrogen_atom_index,
         scorer_ligand_donor_count * sizeof(*scorer.ligand_hydrogen_atom_index)},
        {scorer.ligand_exclusion_atom_i,
         scorer_exclusion_count * sizeof(*scorer.ligand_exclusion_atom_i)},
        {scorer.ligand_exclusion_atom_j,
         scorer_exclusion_count * sizeof(*scorer.ligand_exclusion_atom_j)},
        {scorer.rotor_atom_i,
         scorer_rotor_count * sizeof(*scorer.rotor_atom_i)},
        {scorer.rotor_atom_j,
         scorer_rotor_count * sizeof(*scorer.rotor_atom_j)},
        {scorer.rotor_atom_k,
         scorer_rotor_count * sizeof(*scorer.rotor_atom_k)},
        {scorer.rotor_atom_l,
         scorer_rotor_count * sizeof(*scorer.rotor_atom_l)},
        {validity.receptor_x_angstrom,
         validity_receptor_count * sizeof(*validity.receptor_x_angstrom)},
        {validity.receptor_y_angstrom,
         validity_receptor_count * sizeof(*validity.receptor_y_angstrom)},
        {validity.receptor_z_angstrom,
         validity_receptor_count * sizeof(*validity.receptor_z_angstrom)},
        {validity.receptor_vdw_radius_angstrom,
         validity_receptor_count * sizeof(*validity.receptor_vdw_radius_angstrom)},
        {validity.ligand_reference_x_angstrom,
         validity_ligand_count * sizeof(*validity.ligand_reference_x_angstrom)},
        {validity.ligand_reference_y_angstrom,
         validity_ligand_count * sizeof(*validity.ligand_reference_y_angstrom)},
        {validity.ligand_reference_z_angstrom,
         validity_ligand_count * sizeof(*validity.ligand_reference_z_angstrom)},
        {validity.ligand_vdw_radius_angstrom,
         validity_ligand_count * sizeof(*validity.ligand_vdw_radius_angstrom)},
        {validity.bond_atom_i,
         validity_bond_count * sizeof(*validity.bond_atom_i)},
        {validity.bond_atom_j,
         validity_bond_count * sizeof(*validity.bond_atom_j)},
        {validity.ligand_exclusion_atom_i,
         validity_exclusion_count * sizeof(*validity.ligand_exclusion_atom_i)},
        {validity.ligand_exclusion_atom_j,
         validity_exclusion_count * sizeof(*validity.ligand_exclusion_atom_j)},
        {validity.chirality_center_atom,
         validity_chirality_count * sizeof(*validity.chirality_center_atom)},
        {validity.chirality_atom_i,
         validity_chirality_count * sizeof(*validity.chirality_atom_i)},
        {validity.chirality_atom_j,
         validity_chirality_count * sizeof(*validity.chirality_atom_j)},
        {validity.chirality_atom_k,
         validity_chirality_count * sizeof(*validity.chirality_atom_k)},
    }};
    for (const auto &input : inputs) {
        if (ranges_overlap(
                out_pipeline,
                sizeof(*out_pipeline),
                input.first,
                input.second)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 downstream handle output overlaps a create input");
        }
    }
    return BG_STATUS_OK;
}

[[nodiscard]] bg_status validate_outputs(
    const bg_context &context,
    const bg_docking_fixed64_downstream_v1 &pipeline,
    const bg_docking_scorer_v1_candidate_batch_soa_v1 &candidates,
    const double *quaternion_x,
    const double *quaternion_y,
    const double *quaternion_z,
    const double *quaternion_w,
    const bg_docking_scorer_v1_output_v1 &scorer,
    const bg_docking_pose_validity_output_v1 &validity,
    const bg_docking_stable_top_k_output_v1 &ranking) noexcept {
    bg_status status = validate_descriptor_header(
        scorer.struct_size,
        sizeof(scorer),
        scorer.abi_version,
        "fixed64 downstream scorer output size does not match ABI v1",
        "fixed64 downstream scorer output ABI version does not match");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = validate_descriptor_header(
        validity.struct_size,
        sizeof(validity),
        validity.abi_version,
        "fixed64 downstream validity output size does not match ABI v1",
        "fixed64 downstream validity output ABI version does not match");
    if (status != BG_STATUS_OK) {
        return status;
    }
    status = validate_descriptor_header(
        ranking.struct_size,
        sizeof(ranking),
        ranking.abi_version,
        "fixed64 downstream ranking output size does not match ABI v1",
        "fixed64 downstream ranking output ABI version does not match");
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (scorer.unit_system != pipeline.unit_system ||
        validity.unit_system != pipeline.unit_system ||
        ranking.unit_system != pipeline.unit_system ||
        scorer.reserved0 != 0 || validity.reserved0 != 0 ||
        ranking.reserved0 != 0 || ranking.reserved1 != 0 ||
        ranking.reserved2 != 0 || !reserved_is_zero(scorer.reserved) ||
        !reserved_is_zero(validity.reserved) ||
        !reserved_is_zero(ranking.reserved)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 downstream output units or reserved fields are invalid");
    }
    if (scorer.row_capacity < kCandidateCount ||
        validity.row_capacity < kCandidateCount ||
        ranking.row_capacity < kCandidateCount ||
        ranking.primary_index_capacity < kCandidateCount ||
        ranking.valid_index_capacity < kCandidateCount ||
        scorer.rows == nullptr || validity.rows == nullptr ||
        ranking.rows == nullptr ||
        ranking.primary_slot_indices == nullptr ||
        ranking.valid_slot_indices == nullptr ||
        !pointer_is_aligned(scorer.rows) ||
        !pointer_is_aligned(validity.rows) ||
        !pointer_is_aligned(ranking.rows) ||
        !pointer_is_aligned(ranking.primary_slot_indices) ||
        !pointer_is_aligned(ranking.valid_slot_indices)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 downstream output channel or capacity is invalid");
    }
    if (quaternion_x == nullptr || quaternion_y == nullptr ||
        quaternion_z == nullptr || quaternion_w == nullptr ||
        !pointer_is_aligned(quaternion_x) ||
        !pointer_is_aligned(quaternion_y) ||
        !pointer_is_aligned(quaternion_z) ||
        !pointer_is_aligned(quaternion_w)) {
        return fail(
            BG_STATUS_INVALID_ARGUMENT,
            "fixed64 downstream quaternion channel is null or misaligned");
    }

    const auto ligand_count =
        static_cast<std::size_t>(pipeline.ligand_atom_count);
    const std::size_t coordinate_count = kCandidateCount * ligand_count;
    const std::array<std::pair<const void *, std::size_t>, 14> inputs = {{
        {&context, sizeof(context)},
        {&pipeline, sizeof(pipeline)},
        {pipeline.scorer, sizeof(*pipeline.scorer)},
        {pipeline.validity, sizeof(*pipeline.validity)},
        {pipeline.ranker, sizeof(*pipeline.ranker)},
        {&candidates, sizeof(candidates)},
        {candidates.candidate_state,
         kCandidateCount *
             sizeof(bg_docking_scorer_v1_candidate_state)},
        {candidates.x_angstrom, coordinate_count * sizeof(double)},
        {candidates.y_angstrom, coordinate_count * sizeof(double)},
        {candidates.z_angstrom, coordinate_count * sizeof(double)},
        {quaternion_x, kCandidateCount * sizeof(double)},
        {quaternion_y, kCandidateCount * sizeof(double)},
        {quaternion_z, kCandidateCount * sizeof(double)},
        {quaternion_w, kCandidateCount * sizeof(double)},
    }};
    const std::array<std::pair<const void *, std::size_t>, 8> outputs = {{
        {&scorer, sizeof(scorer)},
        {&validity, sizeof(validity)},
        {&ranking, sizeof(ranking)},
        {scorer.rows,
         kCandidateCount * sizeof(bg_docking_scorer_v1_row_v1)},
        {validity.rows,
         kCandidateCount * sizeof(bg_docking_pose_validity_row_v1)},
        {ranking.rows,
         kCandidateCount * sizeof(bg_docking_stable_top_k_row_v1)},
        {ranking.primary_slot_indices,
         kCandidateCount * sizeof(uint32_t)},
        {ranking.valid_slot_indices,
         kCandidateCount * sizeof(uint32_t)},
    }};
    for (std::size_t first = 0; first < outputs.size(); ++first) {
        for (std::size_t second = first + 1; second < outputs.size();
             ++second) {
            if (ranges_overlap(
                    outputs[first].first,
                    outputs[first].second,
                    outputs[second].first,
                    outputs[second].second)) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "fixed64 downstream output buffers overlap");
            }
        }
        for (const auto &input : inputs) {
            if (ranges_overlap(
                    outputs[first].first,
                    outputs[first].second,
                    input.first,
                    input.second)) {
                return fail(
                    BG_STATUS_INVALID_ARGUMENT,
                    "fixed64 downstream input and output buffers overlap");
            }
        }
    }
    return BG_STATUS_OK;
}

void hash_u64_be(
    dynamics::Sha256 *hash,
    uint64_t value) noexcept {
    std::array<uint8_t, 8> bytes{};
    for (std::size_t index = 0; index < bytes.size(); ++index) {
        bytes[index] = static_cast<uint8_t>(
            value >> static_cast<uint32_t>((bytes.size() - 1U - index) * 8U));
    }
    hash->update(bytes.data(), bytes.size());
}

void hash_double_be(
    dynamics::Sha256 *hash,
    double value) noexcept {
    uint64_t bits = UINT64_C(0);
    static_assert(sizeof(bits) == sizeof(value));
    std::memcpy(&bits, &value, sizeof(bits));
    if (value == 0.0) {
        bits = UINT64_C(0);
    }
    hash_u64_be(hash, bits);
}

[[nodiscard]] std::array<uint8_t, kDigestSize> coordinate_digest(
    const bg_docking_scorer_v1_candidate_batch_soa_v1 &candidates,
    std::size_t ligand_count,
    std::size_t slot) noexcept {
    dynamics::Sha256 hash;
    constexpr std::size_t domain_size = sizeof(kCoordinateHashDomain) - 1U;
    hash_u64_be(&hash, domain_size);
    hash.update(
        reinterpret_cast<const uint8_t *>(kCoordinateHashDomain),
        domain_size);
    hash_u64_be(&hash, ligand_count);
    const std::size_t offset = slot * ligand_count;
    for (std::size_t atom = 0; atom < ligand_count; ++atom) {
        hash_double_be(&hash, candidates.x_angstrom[offset + atom]);
        hash_double_be(&hash, candidates.y_angstrom[offset + atom]);
        hash_double_be(&hash, candidates.z_angstrom[offset + atom]);
    }
    return hash.finish();
}

[[nodiscard]] bool digest_is_zero(
    const std::array<uint8_t, kDigestSize> &digest) noexcept {
    return std::all_of(
        digest.begin(), digest.end(), [](uint8_t value) {
            return value == UINT8_C(0);
        });
}

void destroy_components(bg_docking_fixed64_downstream_v1 *pipeline) noexcept {
    if (pipeline == nullptr) {
        return;
    }
    bg_docking_stable_top_k_v1_destroy(pipeline->ranker);
    bg_docking_pose_validity_v1_destroy(pipeline->validity);
    bg_docking_scorer_v1_destroy(pipeline->scorer);
    pipeline->ranker = nullptr;
    pipeline->validity = nullptr;
    pipeline->scorer = nullptr;
}

}  // namespace

std::array<uint8_t, 32> coordinate_digest_for_composition(
    const bg_docking_scorer_v1_candidate_batch_soa_v1 &candidates,
    std::size_t ligand_count,
    std::size_t slot) noexcept {
    return coordinate_digest(candidates, ligand_count, slot);
}

}  // namespace betelgeuze::native::docking::downstream

extern "C" BG_API bg_status BG_CALL
bg_docking_fixed64_downstream_v1_create(
    const bg_context *context,
    const bg_docking_scorer_v1_context_soa_v1 *scorer_descriptor,
    const bg_docking_pose_validity_context_soa_v1 *validity_descriptor,
    bg_docking_fixed64_downstream_v1 **out_pipeline) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::docking::downstream;
    return guarded_status([&]() -> bg_status {
        if (context == nullptr || scorer_descriptor == nullptr ||
            validity_descriptor == nullptr || out_pipeline == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 downstream create inputs and output must not be null");
        }
        if (!pointer_is_aligned(context) ||
            !pointer_is_aligned(scorer_descriptor) ||
            !pointer_is_aligned(validity_descriptor) ||
            !pointer_is_aligned(out_pipeline)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 downstream create inputs or output are misaligned");
        }
        bg_status status = validate_descriptor_header(
            scorer_descriptor->struct_size,
            sizeof(*scorer_descriptor),
            scorer_descriptor->abi_version,
            "fixed64 downstream scorer descriptor size does not match ABI v1",
            "fixed64 downstream scorer descriptor ABI version does not match");
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = validate_descriptor_header(
            validity_descriptor->struct_size,
            sizeof(*validity_descriptor),
            validity_descriptor->abi_version,
            "fixed64 downstream validity descriptor size does not match ABI v1",
            "fixed64 downstream validity descriptor ABI version does not match");
        if (status != BG_STATUS_OK) {
            return status;
        }
        const bg_status output_status = validate_create_output_range(
            *context,
            *scorer_descriptor,
            *validity_descriptor,
            out_pipeline);
        if (output_status != BG_STATUS_OK) {
            return output_status;
        }
        *out_pipeline = nullptr;

        auto pipeline =
            std::make_unique<bg_docking_fixed64_downstream_v1>();
        pipeline->backend = context->backend;
        pipeline->unit_system = context->unit_system;
        pipeline->device_ordinal = context->device_ordinal;
        pipeline->ligand_atom_count = scorer_descriptor->ligand_atom_count;

        status = bg_docking_scorer_v1_create(
            context, scorer_descriptor, &pipeline->scorer);
        if (status != BG_STATUS_OK) {
            return status;
        }
        status = bg_docking_pose_validity_v1_create(
            context, validity_descriptor, &pipeline->validity);
        if (status != BG_STATUS_OK) {
            destroy_components(pipeline.get());
            return status;
        }
        status = validate_component_binding(
            *context, *scorer_descriptor, *validity_descriptor);
        if (status != BG_STATUS_OK) {
            destroy_components(pipeline.get());
            return status;
        }
        status = bg_docking_stable_top_k_v1_create(
            context, &pipeline->ranker);
        if (status != BG_STATUS_OK) {
            destroy_components(pipeline.get());
            return status;
        }
        *out_pipeline = pipeline.release();
        return BG_STATUS_OK;
    });
}

extern "C" BG_API void BG_CALL
bg_docking_fixed64_downstream_v1_destroy(
    bg_docking_fixed64_downstream_v1 *pipeline) BG_NOEXCEPT {
    using namespace betelgeuze::native::docking::downstream;
    destroy_components(pipeline);
    delete pipeline;
}

extern "C" BG_API bg_status BG_CALL
bg_docking_fixed64_downstream_v1_get_backend(
    const bg_docking_fixed64_downstream_v1 *pipeline,
    bg_backend *backend) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::docking::downstream;
    return guarded_status([&]() -> bg_status {
        if (pipeline == nullptr || backend == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 downstream handle and backend output must not be null");
        }
        if (!pointer_is_aligned(pipeline) || !pointer_is_aligned(backend)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 downstream handle or backend output is misaligned");
        }
        if (ranges_overlap(
                pipeline,
                sizeof(*pipeline),
                backend,
                sizeof(*backend))) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 downstream backend output overlaps its handle");
        }
        *backend = pipeline->backend;
        return BG_STATUS_OK;
    });
}

extern "C" BG_API bg_status BG_CALL
bg_docking_fixed64_downstream_v1_run(
    const bg_context *context,
    const bg_docking_fixed64_downstream_v1 *pipeline,
    const bg_docking_scorer_v1_candidate_batch_soa_v1 *candidates,
    const double *quaternion_x,
    const double *quaternion_y,
    const double *quaternion_z,
    const double *quaternion_w,
    bg_docking_scorer_v1_output_v1 *scorer_output,
    bg_docking_pose_validity_output_v1 *validity_output,
    bg_docking_stable_top_k_output_v1 *ranking_output) BG_NOEXCEPT {
    using namespace betelgeuze::native;
    using namespace betelgeuze::native::docking::downstream;
    return guarded_status([&]() -> bg_status {
        if (context == nullptr || pipeline == nullptr ||
            candidates == nullptr || scorer_output == nullptr ||
            validity_output == nullptr || ranking_output == nullptr) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 downstream run inputs and outputs must not be null");
        }
        if (!pointer_is_aligned(context) || !pointer_is_aligned(pipeline) ||
            !pointer_is_aligned(candidates) ||
            !pointer_is_aligned(scorer_output) ||
            !pointer_is_aligned(validity_output) ||
            !pointer_is_aligned(ranking_output)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 downstream run descriptors or handles are misaligned");
        }
        bg_status status = validate_descriptor_header(
            candidates->struct_size,
            sizeof(*candidates),
            candidates->abi_version,
            "fixed64 downstream candidate descriptor size does not match ABI v1",
            "fixed64 downstream candidate descriptor ABI version does not match");
        if (status != BG_STATUS_OK) {
            return status;
        }
        if (context->backend != pipeline->backend ||
            context->unit_system != pipeline->unit_system ||
            context->device_ordinal != pipeline->device_ordinal ||
            candidates->candidate_count != kCandidateCount ||
            candidates->ligand_atom_count != pipeline->ligand_atom_count ||
            candidates->unit_system != pipeline->unit_system ||
            candidates->reserved0 != 0 ||
            !reserved_is_zero(candidates->reserved)) {
            return fail(
                BG_STATUS_INVALID_ARGUMENT,
                "fixed64 downstream handle, context, denominator, or units are cross-wired");
        }
        status = validate_outputs(
            *context,
            *pipeline,
            *candidates,
            quaternion_x,
            quaternion_y,
            quaternion_z,
            quaternion_w,
            *scorer_output,
            *validity_output,
            *ranking_output);
        if (status != BG_STATUS_OK) {
            return status;
        }

        LocalOutputs local{};
        bg_docking_scorer_v1_output_v1 local_scorer{};
        local_scorer.struct_size = sizeof(local_scorer);
        local_scorer.abi_version = BG_ABI_VERSION;
        local_scorer.row_capacity = kCandidateCount;
        local_scorer.unit_system = pipeline->unit_system;
        local_scorer.rows = local.scorer_rows.data();
        status = bg_docking_scorer_v1_score_fixed64(
            context, pipeline->scorer, candidates, &local_scorer);
        if (status != BG_STATUS_OK) {
            return status;
        }

        std::array<bg_docking_pose_validity_candidate_state,
                   kCandidateCount>
            validity_state{};
        std::array<bg_docking_scorer_v1_failure, kCandidateCount>
            upstream_failure{};
        const auto ligand_count =
            static_cast<std::size_t>(pipeline->ligand_atom_count);
        for (std::size_t slot = 0; slot < kCandidateCount; ++slot) {
            const auto &row = local.scorer_rows[slot];
            if (row.status == BG_DOCKING_SCORER_V1_ROW_SCORED) {
                validity_state[slot] =
                    BG_DOCKING_POSE_VALIDITY_CANDIDATE_EVALUATE;
                upstream_failure[slot] =
                    BG_DOCKING_SCORER_V1_FAILURE_NONE;
                const auto digest =
                    coordinate_digest(*candidates, ligand_count, slot);
                if (digest_is_zero(digest)) {
                    return fail(
                        BG_STATUS_INTERNAL_ERROR,
                        "fixed64 downstream derived an all-zero coordinate SHA-256");
                }
                std::copy(
                    digest.begin(),
                    digest.end(),
                    local.coordinate_sha256.begin() +
                        static_cast<std::ptrdiff_t>(slot * kDigestSize));
            } else {
                validity_state[slot] =
                    BG_DOCKING_POSE_VALIDITY_CANDIDATE_UPSTREAM_FAILURE;
                upstream_failure[slot] = row.failure_code;
            }
        }

        bg_docking_pose_validity_candidate_batch_soa_v1 validity_batch{};
        validity_batch.struct_size = sizeof(validity_batch);
        validity_batch.abi_version = BG_ABI_VERSION;
        validity_batch.candidate_count = kCandidateCount;
        validity_batch.ligand_atom_count = pipeline->ligand_atom_count;
        validity_batch.unit_system = pipeline->unit_system;
        validity_batch.candidate_state = validity_state.data();
        validity_batch.upstream_scorer_failure_code =
            upstream_failure.data();
        validity_batch.quaternion_x = quaternion_x;
        validity_batch.quaternion_y = quaternion_y;
        validity_batch.quaternion_z = quaternion_z;
        validity_batch.quaternion_w = quaternion_w;
        validity_batch.x_angstrom = candidates->x_angstrom;
        validity_batch.y_angstrom = candidates->y_angstrom;
        validity_batch.z_angstrom = candidates->z_angstrom;

        bg_docking_pose_validity_output_v1 local_validity{};
        local_validity.struct_size = sizeof(local_validity);
        local_validity.abi_version = BG_ABI_VERSION;
        local_validity.row_capacity = kCandidateCount;
        local_validity.unit_system = pipeline->unit_system;
        local_validity.rows = local.validity_rows.data();
        status = bg_docking_pose_validity_v1_evaluate_fixed64(
            context,
            pipeline->validity,
            &validity_batch,
            &local_validity);
        if (status != BG_STATUS_OK) {
            return status;
        }

        bg_docking_stable_top_k_input_v1 ranking_input{};
        ranking_input.struct_size = sizeof(ranking_input);
        ranking_input.abi_version = BG_ABI_VERSION;
        ranking_input.candidate_count = kCandidateCount;
        ranking_input.top_k_limit = BG_DOCKING_STABLE_TOP_K_LIMIT;
        ranking_input.unit_system = pipeline->unit_system;
        ranking_input.scorer_rows = local.scorer_rows.data();
        ranking_input.validity_rows = local.validity_rows.data();
        ranking_input.coordinate_sha256 = local.coordinate_sha256.data();

        bg_docking_stable_top_k_output_v1 local_ranking{};
        local_ranking.struct_size = sizeof(local_ranking);
        local_ranking.abi_version = BG_ABI_VERSION;
        local_ranking.row_capacity = kCandidateCount;
        local_ranking.primary_index_capacity = kCandidateCount;
        local_ranking.valid_index_capacity = kCandidateCount;
        local_ranking.unit_system = pipeline->unit_system;
        local_ranking.rows = local.ranking_rows.data();
        local_ranking.primary_slot_indices =
            local.primary_slot_indices.data();
        local_ranking.valid_slot_indices =
            local.valid_slot_indices.data();
        status = bg_docking_stable_top_k_v1_rank_fixed64(
            context,
            pipeline->ranker,
            &ranking_input,
            &local_ranking);
        if (status != BG_STATUS_OK) {
            return status;
        }
        local.primary_count = local_ranking.primary_index_count;
        local.valid_count = local_ranking.valid_index_count;

        std::memcpy(
            scorer_output->rows,
            local.scorer_rows.data(),
            sizeof(local.scorer_rows));
        std::memcpy(
            validity_output->rows,
            local.validity_rows.data(),
            sizeof(local.validity_rows));
        std::memcpy(
            ranking_output->rows,
            local.ranking_rows.data(),
            sizeof(local.ranking_rows));
        std::memcpy(
            ranking_output->primary_slot_indices,
            local.primary_slot_indices.data(),
            sizeof(local.primary_slot_indices));
        std::memcpy(
            ranking_output->valid_slot_indices,
            local.valid_slot_indices.data(),
            sizeof(local.valid_slot_indices));
        scorer_output->row_count = kCandidateCount;
        validity_output->row_count = kCandidateCount;
        ranking_output->row_count = kCandidateCount;
        ranking_output->primary_index_count = local.primary_count;
        ranking_output->valid_index_count = local.valid_count;
        ranking_output->existing_rank_auto_change_authorized = UINT8_C(0);
        ranking_output->customer_pose_emission_authorized = UINT8_C(0);
        ranking_output->production_claim_authorized = UINT8_C(0);
        return BG_STATUS_OK;
    });
}
